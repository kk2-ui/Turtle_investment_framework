"""niangao.read_models — reusable read-side data assembly for dashboard/API.

API read models intentionally read the local portfolio.db only. They must not
trigger Android sync, quote refresh, or dashboard auto-refresh as a side effect
of an HTTP GET.

All heavy/dangerous imports are lazy (inside the function that needs them) so
that importing this module is cheap and side-effect-free.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from niangao.db import _DB_PATH, _normalize_invest_code, _turtle_to_invest_code
from niangao.metrics import compute_portfolio_gg
from niangao.reconcile import run_reconcile


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(_DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def _rows() -> list[dict[str, Any]]:
    db = _connect()
    try:
        rows = [dict(r) for r in db.execute("""
            SELECT a.*, w.invest_code, w.invest_status, w.current_hold, w.avg_cost AS inv_avg_cost,
                   w.hold_limit_pct AS inv_hold_limit_pct, w.annual_div_per_share AS inv_dps,
                   w.invest_logic AS inv_logic, w.my_valuation AS inv_valuation, w.live_price,
                   w.name AS wl_name, w.in_invest
            FROM analysis a LEFT JOIN watchlist w ON a.ts_code=w.ts_code
            ORDER BY a.gg_discounted DESC
        """).fetchall()]
        analyzed_codes = {r["ts_code"] for r in rows}
        unanalyzed = [dict(r) for r in db.execute("""
            SELECT w.* FROM watchlist w
            LEFT JOIN analysis a ON a.ts_code=w.ts_code
            WHERE COALESCE(w.current_hold,0) > 0 AND a.ts_code IS NULL
            ORDER BY w.current_hold DESC
        """).fetchall()]
    finally:
        db.close()

    now = datetime.now()
    for r in rows:
        r["market"] = r.get("market", "?")
        r["gg_val"] = r.get("gg_discounted") or r.get("gg_base")
        r["gg_ok"] = bool(r.get("gg_ok"))
        r["inv_holding"] = r.get("current_hold", 0) or 0
        r["inv_status"] = r.get("invest_status", "") or ""
        r["_row_type"] = "analyzed"
        at = r.get("analyzed_at", "")
        try:
            ad = datetime.fromisoformat(at.replace("Z", "+00:00").replace(" ", "T"))
            r["_days_ago"] = (now - ad.replace(tzinfo=None)).days
        except Exception:
            r["_days_ago"] = 999
        r["_stale"] = r["_days_ago"] > 30

    for u in unanalyzed:
        ts_code = u.get("ts_code")
        if ts_code in analyzed_codes:
            continue
        u.update({
            "gg_val": None,
            "gg_ok": False,
            "decision": "⚠️待分析",
            "inv_avg_cost": u.get("avg_cost", 0),
            "market": u.get("market", "?"),
            "inv_holding": u.get("current_hold", 0) or 0,
            "_row_type": "unanalyzed",
            "analyzed_at": "",
            "wl_name": u.get("name"),
            "live_price": u.get("live_price"),
        })
        rows.append(u)
    return rows


def _assets() -> dict[str, Any]:
    db = _connect()
    try:
        cash_rows = [dict(r) for r in db.execute("SELECT * FROM cash").fetchall()]
        account_rows = [dict(r) for r in db.execute("SELECT * FROM account").fetchall()]
        latest = db.execute("SELECT * FROM wealth_snapshot ORDER BY snapshot_at DESC LIMIT 1").fetchone()
        returns_row_count = db.execute("SELECT COUNT(*) FROM wealth_snapshot").fetchone()[0]
        div_received = db.execute("SELECT COALESCE(SUM(amount),0) FROM trade_record WHERE trade_type='DIVIDEND'").fetchone()[0]
        inflow = db.execute("SELECT COALESCE(SUM(delta_cny),0) FROM cash_flow").fetchone()[0]
        holding_count = db.execute("SELECT COUNT(*) FROM watchlist WHERE COALESCE(current_hold,0)>0").fetchone()[0]
        watching_count = db.execute("SELECT COUNT(*) FROM watchlist WHERE COALESCE(current_hold,0)=0 AND invest_status='WATCHING'").fetchone()[0]
        total_stock = db.execute("SELECT COALESCE(SUM(COALESCE(current_hold,0)*COALESCE(live_price,0)),0) FROM watchlist").fetchone()[0]
    finally:
        db.close()

    cash = {}
    for r in cash_rows:
        cash[r["currency"]] = cash.get(r["currency"], 0) + (r["amount"] or 0)
    latest_dict = dict(latest) if latest else {}
    current_wealth = latest_dict.get("total_wealth_cny") or (total_stock + cash.get("CNY", 0))
    return {
        "accounts": {r["id"]: r for r in account_rows},
        "cash": cash,
        "total_cash_cny": cash.get("CNY", 0) + cash.get("HKD", 0) * 0.93 + cash.get("USD", 0) * 7.2,
        "total_stock_value": total_stock,
        "total_wealth": current_wealth,
        "stock_count": len(_rows()),
        "holding_count": holding_count,
        "watching_count": watching_count,
        "returns": {
            "current_wealth": current_wealth,
            "total_dividends": div_received,
            "total_inflow": inflow,
            "snapshot_count": returns_row_count,
        },
    }


def get_overview() -> dict[str, Any]:
    rows = _rows()
    assets = _assets()
    decisions = {
        "Strong Buy": sum(1 for r in rows if r.get("decision") == "Strong Buy"),
        "Buy": sum(1 for r in rows if r.get("decision") == "Buy"),
        "Hold": sum(1 for r in rows if r.get("decision") == "Hold"),
        "Avoid": sum(1 for r in rows if r.get("decision") == "Avoid"),
        "pending": sum(1 for r in rows if r.get("decision") in ("⚠️待重分析", "⚠️待分析")),
    }
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total_rows": len(rows),
        "analyzed_total": sum(1 for r in rows if r.get("_row_type") == "analyzed"),
        "holding_count": sum(1 for r in rows if (r.get("inv_holding") or 0) > 0),
        "analyzed_holding": sum(1 for r in rows if (r.get("inv_holding") or 0) > 0 and r.get("_row_type") == "analyzed" and r.get("gg_ok")),
        "unanalyzed_holding": sum(1 for r in rows if r.get("_row_type") == "unanalyzed"),
        "stale_count": sum(1 for r in rows if r.get("_stale") and r.get("_row_type") == "analyzed"),
        "decisions": decisions,
        "portfolio_gg": compute_portfolio_gg(rows),
        "assets": assets,
    }


def get_holdings() -> dict[str, Any]:
    output = []
    for r in _rows():
        # Filter out pure residual entries: no holdings, no analysis, no trades, not in invest
        is_residual = (
            (r.get("inv_holding") or 0) == 0
            and r.get("_row_type") not in ("analyzed",)
            and (r.get("in_invest") or 0) == 0
        )
        if is_residual:
            continue
        output.append({
            "ts_code": r.get("ts_code"),
            "invest_code": r.get("invest_code"),
            "name": r.get("wl_name") or r.get("name") or "",
            "market": r.get("market") or "",
            "holding": r.get("inv_holding") or 0,
            "avg_cost": r.get("inv_avg_cost"),
            "live_price": r.get("live_price") or r.get("price"),
            "gg": r.get("gg_val"),
            "ii": r.get("ii"),
            "buy_price": r.get("buy_price"),
            "buy_star": r.get("buy_star"),
            "upside_pct": r.get("upside_pct"),
            "decision": r.get("decision"),
            "position_pct": r.get("pos_pct"),
            "analyzed_at": r.get("analyzed_at"),
            "row_type": r.get("_row_type") or "",
            "has_analysis": r.get("_row_type") == "analyzed",
        })
    return {"count": len(output), "rows": output}


_OBS_CN = {
    "ap_driven_cashflow": "应付驱动现金流",
    "dividend_unsustainable": "股息不可持续",
    "net_profit_decline": "净利润下滑",
    "low_pb_roe": "低PB低ROE",
    "business_disrupted": "商业模式受冲击",
    "management_expropriation": "管理层侵占风险",
    "margin_irreversible": "利润率不可逆下滑",
    "price_new_lows": "股价持续新低",
    "no_value_convergence": "价值不收敛",
    "major_shareholder_sells_or_audit_change": "大股东减持或审计变更",
    "fy2026_h1_margin_lt_13pct": "FY2026H1利润率<13%",
    "2yr_no_value_convergence": "2年内无价值收敛",
}

_ALERT_TYPE_CN = {
    "BUY1": "买入价 1",
    "BUY2": "买入价 2",
    "SELL": "卖出提醒",
    "ABOVE_VAL_SELL": "高于估值卖出",
    "GRID": "网格提醒",
    "MTH": "满堂红提醒",
}

_ALERT_PRIORITY = {
    "BUY1": 0,
    "BUY2": 1,
    "GRID": 2,
    "SELL": 3,
    "ABOVE_VAL_SELL": 4,
    "MTH": 5,
}


def _translate_obs(text: str | None) -> str:
    if not text:
        return ""
    out = str(text)
    for en, cn in _OBS_CN.items():
        out = out.replace(en, cn)
    out = out.replace("⚠️", "⚠").replace(",", " · ")
    return " ".join(out.split()).strip(" ·")


def _parse_batch_buy_plan(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _normalize_price(value: Any) -> float | None:
    try:
        num = float(value)
    except Exception:
        return None
    return round(num, 4)


def _infer_lot_size(stock: dict[str, Any] | None) -> int:
    market = str((stock or {}).get("market") or "").upper()
    if market in {"HK", "SH", "SZ"}:
        return 100
    return 1


def _position_limit_pct(stock: dict[str, Any] | None, analysis: dict[str, Any] | None) -> float:
    stock = stock or {}
    analysis = analysis or {}
    hold_limit = stock.get("hold_limit_pct")
    try:
        hold_limit_num = float(hold_limit)
    except Exception:
        hold_limit_num = 0.0
    if hold_limit_num > 0:
        return hold_limit_num
    pos_pct = analysis.get("pos_pct")
    try:
        pos_pct_num = float(pos_pct)
    except Exception:
        pos_pct_num = 0.0
    if pos_pct_num > 0:
        return max(min(pos_pct_num / 100.0, 0.05), 0.01)
    return 0.05


def _round_down_to_lot(shares: int, lot_size: int) -> int:
    if shares <= 0:
        return 0
    if lot_size <= 1:
        return int(shares)
    return (int(shares) // lot_size) * lot_size


def _weight_profile(level_count: int) -> list[float]:
    if level_count == 5:
        return [0.10, 0.15, 0.25, 0.25, 0.25]
    if level_count <= 0:
        return []
    return [1.0 / level_count] * level_count


def _allocate_lots(total_lots: int, weights: list[float]) -> list[int]:
    if total_lots <= 0 or not weights:
        return [0] * len(weights)
    raw = [total_lots * weight for weight in weights]
    base = [int(value) for value in raw]
    remainder = total_lots - sum(base)
    fractions = sorted(
        ((raw[idx] - base[idx], idx) for idx in range(len(weights))),
        reverse=True,
    )
    for _, idx in fractions[:remainder]:
        base[idx] += 1
    return base


def _normalize_batch_levels(batch_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    levels: list[dict[str, Any]] = []
    for idx, item in enumerate(batch_plan):
        if not isinstance(item, dict):
            continue
        price = _normalize_price(item.get("price_hkd"))
        if price is None or price <= 0:
            continue
        star_raw = item.get("star")
        try:
            star = int(star_raw)
        except Exception:
            star = idx + 1
        levels.append({
            "stage": len(levels) + 1,
            "star": star,
            "price": price,
            "action": item.get("action") or f"第 {idx + 1} 档",
            "upside_pct": item.get("upside_pct"),
        })
    levels.sort(key=lambda level: (level.get("star") or 999, -(level.get("price") or 0)))
    for idx, level in enumerate(levels):
        level["stage"] = idx + 1
    return levels


def _derive_levels_from_staged(staged: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not staged:
        return []
    raw_levels = []
    try:
        raw_levels = json.loads(staged.get("levels_json", "[]"))
    except Exception:
        raw_levels = []
    levels: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_levels):
        if not isinstance(item, dict):
            continue
        price = _normalize_price(item.get("price"))
        if price is None or price <= 0:
            continue
        levels.append({
            "stage": idx + 1,
            "star": idx + 1,
            "price": price,
            "action": f"第 {idx + 1} 档",
            "upside_pct": None,
            "completed_flag": bool(item.get("completed")),
            "skipped_flag": bool(item.get("skipped")),
            "filled_shares_flag": int(item.get("filled_shares") or 0),
            "note": item.get("note") or "",
        })
    return levels


def _build_execution_entry(execution: dict[str, Any]) -> dict[str, Any]:
    trade = execution.get("trade") or {}
    return {
        "id": execution.get("id"),
        "alert_id": execution.get("alert_id"),
        "alert_type": execution.get("alert_type"),
        "settled_price": _normalize_price(execution.get("settled_price")),
        "settled_shares": int(execution.get("settled_shares") or 0),
        "settled_amount": round(float(execution.get("settled_amount") or 0), 2),
        "source": execution.get("source") or "",
        "trade_id": trade.get("id"),
        "trade_at": trade.get("trade_at"),
    }


def _build_plan_detail(
    *,
    stock: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    staged: dict[str, Any] | None,
    executions: list[dict[str, Any]],
    total_wealth: float,
) -> dict[str, Any] | None:
    stock = stock or {}
    analysis = analysis or {}
    plan = plan or {}
    position = _build_position_summary(stock)
    batch_levels = _normalize_batch_levels(_parse_batch_buy_plan(plan.get("batch_buy_json")))
    if not batch_levels:
        batch_levels = _derive_levels_from_staged(staged)
    if not batch_levels:
        return None

    live_price = float(position.get("live_price") or 0)
    lot_size = _infer_lot_size(stock)
    level_count = len(batch_levels)
    position_limit_pct = _position_limit_pct(stock, analysis)
    cap_value = max(float(total_wealth or 0) * position_limit_pct, 0.0)
    raw_cap_shares = int(cap_value / live_price) if live_price > 0 else int(position.get("current_hold") or 0)
    cap_shares = _round_down_to_lot(raw_cap_shares, lot_size)
    current_hold = int(position.get("current_hold") or 0)
    target_shares = max(cap_shares, current_hold)
    if target_shares <= 0 and live_price > 0 and cap_value > 0:
        target_shares = lot_size
    total_lots = max(1, int(target_shares / lot_size)) if target_shares > 0 and lot_size > 0 else max(target_shares, 0)
    lots_per_level = _allocate_lots(total_lots, _weight_profile(level_count))
    planned_shares_per_level = [lots * lot_size for lots in lots_per_level]
    planned_total_shares = sum(planned_shares_per_level)
    if target_shares > 0 and planned_total_shares <= 0:
        planned_shares_per_level[-1] = lot_size
        planned_total_shares = lot_size

    execution_entries = [_build_execution_entry(execution) for execution in executions]
    levels: list[dict[str, Any]] = []
    consumed_hold = 0
    first_incomplete_idx: int | None = None
    for idx, base_level in enumerate(batch_levels):
        planned_shares = planned_shares_per_level[idx] if idx < len(planned_shares_per_level) else 0
        completed_shares = min(max(current_hold - consumed_hold, 0), planned_shares)
        consumed_hold += planned_shares
        remaining_shares = max(planned_shares - completed_shares, 0)
        actionable = live_price > 0 and live_price <= float(base_level.get("price") or 0)
        status = "已完成" if remaining_shares == 0 else ("本次建议" if first_incomplete_idx is None else ("可继续" if actionable else "等待"))
        if remaining_shares > 0 and first_incomplete_idx is None:
            first_incomplete_idx = idx
        levels.append({
            "stage": base_level.get("stage") or idx + 1,
            "star": base_level.get("star"),
            "label": f"第 {base_level.get('stage') or idx + 1} 档",
            "price": float(base_level.get("price") or 0),
            "action": base_level.get("action") or "",
            "upside_pct": base_level.get("upside_pct"),
            "planned_shares": planned_shares,
            "completed_shares": completed_shares,
            "remaining_shares": remaining_shares,
            "status": status,
            "actionable": actionable,
            "linked_executions": [],
            "note": base_level.get("note") or "",
        })

    for execution in execution_entries:
        settled_price = execution.get("settled_price")
        matched_idx = 0
        if settled_price is not None and levels:
            matched_idx = min(
                range(len(levels)),
                key=lambda idx: abs((levels[idx].get("price") or 0) - settled_price),
            )
        if levels:
            levels[matched_idx]["linked_executions"].append(execution)

    completed_levels = sum(1 for level in levels if level.get("remaining_shares") == 0)
    next_level = levels[first_incomplete_idx] if first_incomplete_idx is not None else None
    position_cap_shares = max(cap_shares, 0)
    remaining_room_shares = max(position_cap_shares - current_hold, 0)
    remaining_plan_shares = sum(level.get("remaining_shares") or 0 for level in levels)
    annual_dps = float(stock.get("annual_div_per_share") or 0)
    current_dividend_yield_pct = round(annual_dps / live_price * 100, 2) if live_price > 0 and annual_dps > 0 else 0.0
    lock_ratio = 0.20 if bool(stock.get("lock_reserve")) else 0.0
    lock_band_shares = _round_down_to_lot(int(position_cap_shares * lock_ratio), lot_size) if position_cap_shares > 0 else 0
    valuation_band_shares = max(position_cap_shares - lock_band_shares, 0)
    position_progress_pct = round(current_hold / position_cap_shares * 100, 2) if position_cap_shares > 0 else 0.0

    total_cost = current_hold * float(position.get("avg_cost") or 0)
    total_shares = current_hold
    for level in levels:
        remaining_shares = int(level.get("remaining_shares") or 0)
        if remaining_shares <= 0:
            continue
        total_cost += remaining_shares * float(level.get("price") or 0)
        total_shares += remaining_shares
    full_buy_avg_cost = round(total_cost / total_shares, 4) if total_shares > 0 else None

    return {
        "lot_size": lot_size,
        "position_limit_pct": round(position_limit_pct * 100, 2),
        "position_cap_shares": position_cap_shares,
        "position_progress_pct": position_progress_pct,
        "remaining_position_room_shares": remaining_room_shares,
        "remaining_plan_shares": remaining_plan_shares,
        "remaining_total_addable_shares": remaining_room_shares,
        "valuation_band_shares": valuation_band_shares,
        "lock_band_shares": lock_band_shares,
        "current_dividend_yield_pct": current_dividend_yield_pct,
        "suggested_shares": int(next_level.get("remaining_shares") or 0) if next_level else 0,
        "suggested_level": next_level,
        "current_level": next_level.get("stage") if next_level else level_count,
        "full_buy_avg_cost": full_buy_avg_cost,
        "full_buy_total_shares": total_shares,
        "planned_total_shares": planned_total_shares,
        "total_levels": level_count,
        "completed_levels": completed_levels,
        "remaining_levels": max(level_count - completed_levels, 0),
        "levels": levels,
    }


def _resolve_alert_stock(alert_stock_code: str, watchlist_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    raw = (alert_stock_code or "").strip()
    normalized = raw.lower()
    normalized_ts = _normalize_invest_code(raw)
    normalized_digits = "".join(ch for ch in raw if ch.isdigit())

    for row in watchlist_rows:
        ts_code = (row.get("ts_code") or "").strip()
        invest_code = (row.get("invest_code") or "").strip().lower()
        ts_digits = "".join(ch for ch in ts_code if ch.isdigit())
        if normalized == ts_code.lower():
            return row
        if invest_code and normalized == invest_code:
            return row
        if normalized_ts.lower() == ts_code.lower():
            return row
        if normalized_digits and ts_digits == normalized_digits:
            return row
    return None


def _build_position_summary(stock: dict[str, Any] | None) -> dict[str, Any]:
    if not stock:
        return {
            "current_hold": 0,
            "avg_cost": 0,
            "effective_cost": 0,
            "live_price": 0,
            "market_value": 0,
            "unrealized_pnl": 0,
            "unrealized_pnl_pct": 0,
            "account_id": 1,
        }
    current_hold = stock.get("current_hold") or 0
    avg_cost = stock.get("avg_cost") or 0
    live_price = stock.get("live_price") or 0
    cumulative_div = stock.get("cumulative_div") or 0
    effective_cost = max(avg_cost - cumulative_div, 0.01) if current_hold > 0 else max(avg_cost - cumulative_div, 0)
    market_value = current_hold * live_price
    unrealized_pnl = (live_price - effective_cost) * current_hold if current_hold > 0 else 0
    unrealized_pnl_pct = ((live_price - effective_cost) / effective_cost * 100) if effective_cost > 0 and current_hold > 0 else 0
    return {
        "current_hold": current_hold,
        "avg_cost": round(avg_cost, 4),
        "effective_cost": round(effective_cost, 4),
        "live_price": live_price,
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
        "account_id": stock.get("account_id") or 1,
    }


def _build_staged_summary(staged: dict[str, Any] | None) -> dict[str, Any] | None:
    if not staged:
        return None
    levels = json.loads(staged.get("levels_json", "[]"))
    completed = sum(1 for level in levels if level.get("completed"))
    skipped = sum(1 for level in levels if level.get("skipped"))
    recent_done = [
        {
            "level": level.get("level"),
            "price": level.get("price"),
            "filled_shares": level.get("filled_shares") or 0,
            "note": level.get("note") or "",
            "status": "completed" if level.get("completed") else "skipped",
        }
        for level in levels
        if level.get("completed") or level.get("skipped")
    ]
    recent_done.sort(key=lambda item: item.get("level") or 0, reverse=True)
    return {
        "base_price": staged.get("base_price"),
        "level_count": staged.get("level_count") or len(levels),
        "completed": completed,
        "skipped": skipped,
        "remaining": (staged.get("level_count") or len(levels)) - completed - skipped,
        "pct": round(100 * completed / max(staged.get("level_count") or len(levels) or 1, 1), 1),
        "levels": levels,
        "recent_done": recent_done[:3],
    }


def get_alerts() -> dict[str, Any]:
    db = _connect()
    try:
        active = [dict(r) for r in db.execute(
            "SELECT * FROM alert_snapshot WHERE is_active=1 AND is_triggered=0 ORDER BY stock_code, alert_type, target_price DESC"
        ).fetchall()]
        triggered = [dict(r) for r in db.execute(
            "SELECT * FROM alert_snapshot WHERE is_active=1 AND is_triggered=1 ORDER BY stock_code, alert_type, target_price DESC"
        ).fetchall()]
        watchlist_rows = [dict(r) for r in db.execute("SELECT * FROM watchlist").fetchall()]
        analysis_rows = {
            r["ts_code"]: dict(r)
            for r in db.execute("SELECT * FROM analysis").fetchall()
        }
        plan_rows = {
            r["ts_code"]: dict(r)
            for r in db.execute("SELECT * FROM investment_plan").fetchall()
        }
        staged_rows = {
            r["ts_code"]: dict(r)
            for r in db.execute("SELECT * FROM staged_buy_plan").fetchall()
        }
        settlement_rows = [dict(r) for r in db.execute(
            "SELECT * FROM alert_settlement ORDER BY id DESC"
        ).fetchall()]
        trade_rows = {
            r["id"]: dict(r)
            for r in db.execute("SELECT * FROM trade_record ORDER BY trade_at DESC, id DESC").fetchall()
        }
    finally:
        db.close()

    settlements_by_alert: dict[int, list[dict[str, Any]]] = {}
    for settlement in settlement_rows:
        alert_id = settlement.get("alert_id")
        if alert_id is None:
            continue
        trade = trade_rows.get(settlement.get("transaction_id"))
        enriched = dict(settlement)
        enriched["trade"] = trade
        settlements_by_alert.setdefault(alert_id, []).append(enriched)

    total_wealth = float(_assets().get("total_wealth") or 0)
    triggered_cards: list[dict[str, Any]] = []
    action_cards: list[dict[str, Any]] = []
    card_by_key: dict[str, dict[str, Any]] = {}

    for alert in triggered:
        stock = _resolve_alert_stock(alert.get("stock_code") or "", watchlist_rows)
        ts_code = stock.get("ts_code") if stock else _normalize_invest_code(alert.get("stock_code") or "")
        analysis = analysis_rows.get(ts_code, {})
        plan = plan_rows.get(ts_code, {})
        staged = _build_staged_summary(staged_rows.get(ts_code))
        position = _build_position_summary(stock)
        batch_plan = _parse_batch_buy_plan(plan.get("batch_buy_json"))
        card_key = ts_code or (alert.get("stock_code") or f"alert-{alert.get('id')}")

        if card_key not in card_by_key:
            name = (stock or {}).get("name") or alert.get("stock_name") or ts_code or alert.get("stock_code") or "未知标的"
            card = {
                "key": card_key,
                "ts_code": ts_code,
                "stock_code": alert.get("stock_code"),
                "stock_url": f"/app/stocks/{ts_code}" if ts_code and stock else "",
                "name": name,
                "market": (stock or {}).get("market") or "",
                "sector": (stock or {}).get("sector") or "",
                "invest_status": (stock or {}).get("invest_status") or "",
                "invest_code": (stock or {}).get("invest_code") or "",
                "alerts": [],
                "position": position,
                "analysis": {
                    "decision": analysis.get("decision"),
                    "gg": analysis.get("gg_discounted") or analysis.get("gg_base"),
                    "ii": analysis.get("ii"),
                    "upside_pct": analysis.get("upside_pct"),
                    "buy_price": analysis.get("buy_price"),
                    "buy_star": analysis.get("buy_star"),
                    "position_pct": analysis.get("pos_pct"),
                },
                "plan": {
                    "stop_loss_hkd": plan.get("stop_loss_hkd"),
                    "stop_loss_conditions": _translate_obs(plan.get("stop_loss_conditions")),
                    "observation_signals": _translate_obs(plan.get("observation_signals")),
                    "conviction": plan.get("conviction"),
                    "core_thesis": plan.get("core_thesis"),
                    "core_tension": plan.get("core_tension"),
                    "batch_plan": batch_plan,
                },
                "staged_buy": staged,
                "executions": [],
                "latest_execution": None,
                "primary_alert": None,
                "plan_detail": None,
            }
            card_by_key[card_key] = card
            triggered_cards.append(card)

        card = card_by_key[card_key]
        settlements = settlements_by_alert.get(alert.get("id"), [])
        alert_item = {
            "id": alert.get("id"),
            "stock_code": alert.get("stock_code"),
            "stock_name": alert.get("stock_name"),
            "alert_type": alert.get("alert_type"),
            "alert_type_label": _ALERT_TYPE_CN.get(alert.get("alert_type"), alert.get("alert_type") or "提醒"),
            "target_price": _normalize_price(alert.get("target_price")),
            "current_price": _normalize_price(alert.get("current_price")),
            "synced_at": alert.get("synced_at"),
            "settlements": settlements,
        }
        card["alerts"].append(alert_item)
        card["executions"].extend(settlements)

    for card in triggered_cards:
        card["alerts"].sort(key=lambda item: (item.get("alert_type") or "", -(item.get("target_price") or 0)))
        card["executions"].sort(
            key=lambda item: (
                item.get("trade", {}).get("trade_at") or 0,
                item.get("id") or 0,
            ),
            reverse=True,
        )
        card["executions"] = card["executions"][:5]
        card["latest_execution"] = card["executions"][0] if card["executions"] else None
        primary_alert = min(
            card["alerts"],
            key=lambda item: (
                _ALERT_PRIORITY.get(item.get("alert_type") or "", 99),
                item.get("target_price") or 0,
            ),
        ) if card["alerts"] else None
        card["primary_alert"] = primary_alert
        card["plan_detail"] = _build_plan_detail(
            stock=next((row for row in watchlist_rows if row.get("ts_code") == card.get("ts_code")), None),
            analysis=analysis_rows.get(card.get("ts_code") or "", {}),
            plan=plan_rows.get(card.get("ts_code") or "", {}),
            staged=staged_rows.get(card.get("ts_code") or ""),
            executions=card["executions"],
            total_wealth=total_wealth,
        )
        detail = card.get("plan_detail") or {}
        action_cards.append({
            "key": card.get("key"),
            "ts_code": card.get("ts_code"),
            "stock_code": card.get("stock_code"),
            "stock_url": card.get("stock_url"),
            "name": card.get("name"),
            "market": card.get("market"),
            "invest_status": card.get("invest_status"),
            "invest_code": card.get("invest_code"),
            "alerts": card.get("alerts", []),
            "primary_alert": primary_alert,
            "position": card.get("position", {}),
            "analysis": card.get("analysis", {}),
            "plan": card.get("plan", {}),
            "staged_buy": card.get("staged_buy"),
            "plan_detail": detail,
            "target_price": (primary_alert or {}).get("target_price"),
            "live_price": card.get("position", {}).get("live_price"),
            "suggested_shares": detail.get("suggested_shares", 0),
            "remaining_plan_shares": detail.get("remaining_plan_shares", 0),
            "remaining_position_room_shares": detail.get("remaining_position_room_shares", 0),
            "current_dividend_yield_pct": detail.get("current_dividend_yield_pct", 0),
            "position_progress_pct": detail.get("position_progress_pct", 0),
            "position_current_shares": card.get("position", {}).get("current_hold", 0),
            "position_cap_shares": detail.get("position_cap_shares", 0),
            "remaining_total_addable_shares": detail.get("remaining_total_addable_shares", 0),
            "valuation_band_shares": detail.get("valuation_band_shares", 0),
            "lock_band_shares": detail.get("lock_band_shares", 0),
            "batch_plan_summary": detail.get("levels", []),
            "executions": card.get("executions", []),
            "latest_execution": card.get("latest_execution"),
        })

    pending_alerts: list[dict[str, Any]] = []
    for alert in active:
        stock = _resolve_alert_stock(alert.get("stock_code") or "", watchlist_rows)
        ts_code = stock.get("ts_code") if stock else _normalize_invest_code(alert.get("stock_code") or "")
        analysis = analysis_rows.get(ts_code, {})
        pending_alerts.append({
            "id": alert.get("id"),
            "stock_code": alert.get("stock_code"),
            "ts_code": ts_code,
            "stock_url": f"/app/stocks/{ts_code}" if ts_code and stock else "",
            "name": (stock or {}).get("name") or alert.get("stock_name") or ts_code or alert.get("stock_code"),
            "market": (stock or {}).get("market") or "",
            "alert_type": alert.get("alert_type"),
            "alert_type_label": _ALERT_TYPE_CN.get(alert.get("alert_type"), alert.get("alert_type") or "提醒"),
            "target_price": _normalize_price(alert.get("target_price")),
            "current_price": _normalize_price(alert.get("current_price") or (stock or {}).get("live_price")),
            "decision": analysis.get("decision"),
            "gg": analysis.get("gg_discounted") or analysis.get("gg_base"),
            "holding": (stock or {}).get("current_hold") or 0,
        })

    return {
        "active_count": len(active),
        "triggered_count": len(triggered),
        "active": active,
        "triggered": triggered,
        "action_cards": action_cards,
        "triggered_cards": triggered_cards,
        "pending_alerts": pending_alerts,
        "summary": {
            "triggered_stock_count": len(action_cards),
            "triggered_alert_count": len(triggered),
            "pending_alert_count": len(active),
        },
    }


def get_transactions(limit: int = 100) -> dict[str, Any]:
    db = _connect()
    try:
        rows = [dict(r) for r in db.execute("SELECT * FROM trade_record ORDER BY trade_at DESC LIMIT ?", (limit,)).fetchall()]
    finally:
        db.close()
    return {"count": len(rows), "rows": rows}


def get_accounts() -> dict[str, Any]:
    db = _connect()
    try:
        accounts = [dict(r) for r in db.execute("SELECT * FROM account ORDER BY id").fetchall()]
        cash = [dict(r) for r in db.execute("SELECT * FROM cash ORDER BY account_id, currency").fetchall()]
    finally:
        db.close()
    return {"accounts": accounts, "cash": cash}


def get_returns() -> dict[str, Any]:
    assets = _assets()
    db = _connect()
    try:
        position_pnl = [dict(r) for r in db.execute("SELECT * FROM position_pnl ORDER BY total_return ASC").fetchall()]
        realized_pnl = [dict(r) for r in db.execute("SELECT * FROM realized_pnl ORDER BY realized_pnl ASC").fetchall()]
        dividends = [dict(r) for r in db.execute("SELECT * FROM trade_record WHERE trade_type='DIVIDEND' ORDER BY dividend_year DESC, trade_at DESC").fetchall()]
    finally:
        db.close()
    return {
        "returns": assets.get("returns", {}) if "error" not in assets else {},
        "position_pnl": position_pnl,
        "realized_pnl": realized_pnl,
        "dividends": dividends,
    }


def _export_invest_json(rows: list[dict], assets: dict | None = None) -> str:
    """Generate invest App-compatible JSON (pure transformation, no I/O)."""
    stocks_out = []
    for r in rows:
        inv_code = _turtle_to_invest_code(r["ts_code"])
        is_analyzed = r.get("_row_type") == "analyzed" and r.get("gg_ok")
        turtle_val = r.get("p_base_rmb") or r.get("buy_price") or 0
        manual_val = r.get("inv_valuation") or 0
        valuation = turtle_val if (is_analyzed and turtle_val and turtle_val > 0) else manual_val
        price = r.get("live_price") or r.get("price") or 0
        if is_analyzed:
            logic = f"Turtle GG={r.get('gg_discounted')}% II={r.get('ii')}% {r.get('decision','')}"
        else:
            logic = r.get("inv_logic") or ""
        stocks_out.append({
            "code": inv_code, "name": r.get("wl_name") or r.get("name") or "",
            "market": r.get("market", "?"),
            "myValuation": round(valuation, 4) if valuation else 0,
            "multiplier2": 1.0, "sellMultiplier": 1.0,
            "holdLimitPct": max(min((r.get("pos_pct") or 5) / 100, 0.05), 0.01) if is_analyzed else (r.get("inv_hold_limit_pct") or 0.05),
            "currentHold": r.get("inv_holding", 0),
            "avgCost": r.get("inv_avg_cost", 0) or 0,
            "annualDivPerShare": r.get("dps") or r.get("inv_dps") or 0,
            "status": "HOLDING" if (r.get("inv_holding") or 0) > 0 else "WATCHING",
            "investLogic": logic,
            "currentPrice": price,
            "turtleGG": round(r.get("gg_discounted"), 1) if (is_analyzed and r.get("gg_discounted")) else None,
            "_turtle": {
                "gg": r.get("gg_discounted"), "gg_fcfe": r.get("gg_fcfe"), "ii": r.get("ii"),
                "decision": r.get("decision"), "p_base_hkd": r.get("p_base_hkd"),
                "buy_price": r.get("buy_price"), "buy_star": r.get("buy_star"),
                "upside_pct": r.get("upside_pct"), "pos_pct": r.get("pos_pct"),
                "analyzed_at": r.get("analyzed_at", ""),
            } if is_analyzed else None,
        })
    cash_data = (assets.get("cash", {"CNY": 0, "HKD": 0, "USD": 0})
                 if (assets and "error" not in assets) else {"CNY": 0, "HKD": 0, "USD": 0})
    return json.dumps({"cash": cash_data, "stocks": stocks_out}, indent=2, ensure_ascii=False)


def get_export() -> dict[str, Any]:
    rows = _rows()
    assets = _assets()
    return json.loads(_export_invest_json(rows, assets))


def get_reconcile() -> dict[str, Any]:
    # Lazy import: _find_invest_db may try ADB pull and is only needed for reconcile
    from niangao.sync import _find_invest_db  # noqa: PLC0415
    invest_db = _find_invest_db()
    if not invest_db:
        return {"status": "ERROR", "invest_db": "", "portfolio_db": _DB_PATH, "checks": [{"name": "source", "status": "ERROR", "summary": "invest DB not found", "details": {}}]}
    return run_reconcile(invest_db, _DB_PATH)


def get_stock_detail(ts_code: str) -> dict[str, Any]:
    """Full stock detail: position, P&L, fundamentals, grid cycles, trades."""
    db = _connect()
    try:
        # Stock from watchlist
        stock = db.execute("SELECT * FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone()
        if not stock:
            return {"error": f"Stock {ts_code} not found"}

        # Also get analysis
        analysis = db.execute("SELECT * FROM analysis WHERE ts_code = ?", (ts_code,)).fetchone()
        plan = db.execute("SELECT * FROM investment_plan WHERE ts_code = ?", (ts_code,)).fetchone()

        # Trades for this stock
        trades = [dict(r) for r in db.execute(
            "SELECT * FROM trade_record WHERE stock_code = ? ORDER BY trade_at DESC LIMIT 50",
            (ts_code,),
        ).fetchall()]

        # Grid cycles
        grid_cycles = [dict(r) for r in db.execute(
            "SELECT * FROM grid_cycle_record WHERE stock_code = ? ORDER BY completed_at DESC",
            (ts_code,),
        ).fetchall()]

        # Staged buy plan
        staged = db.execute(
            "SELECT * FROM staged_buy_plan WHERE ts_code = ?", (ts_code,),
        ).fetchone()

        s = dict(stock)
        a = dict(analysis) if analysis else {}
        p = dict(plan) if plan else {}

        current_hold = s.get("current_hold") or 0
        avg_cost = s.get("avg_cost") or 0
        live_price = s.get("live_price") or 0
        cumulative_div = s.get("cumulative_div") or 0
        effective_cost = max(avg_cost - cumulative_div, 0.01)
        market_value = current_hold * live_price
        unrealized_pnl = (live_price - effective_cost) * current_hold
        annual_dps = s.get("annual_div_per_share") or 0
        dividend_tax_rate = s.get("dividend_tax_rate") or 0

        # Dividend yield
        cost_div_yield = (annual_dps / avg_cost * 100) if avg_cost > 0 and annual_dps > 0 else 0
        price_div_yield = (annual_dps / live_price * 100) if live_price > 0 and annual_dps > 0 else 0
        annual_tax_loss = annual_dps * current_hold * dividend_tax_rate if current_hold > 0 else 0

        # Grid summary
        grid_open = [c for c in grid_cycles if c.get("buy_price") is None]
        grid_closed = [c for c in grid_cycles if c.get("buy_price") is not None]
        grid_total_profit = sum(c.get("profit") or 0 for c in grid_closed)
        grid_success = sum(1 for c in grid_closed if c.get("is_success"))

        # Staged buy progress
        staged_data = None
        if staged:
            import json as _json
            st = dict(staged)
            levels = _json.loads(st.get("levels_json", "[]"))
            completed = sum(1 for l in levels if l.get("completed"))
            staged_data = {
                "base_price": st["base_price"],
                "level_count": st["level_count"],
                "levels": levels,
                "completed": completed,
                "remaining": st["level_count"] - completed,
                "pct": round(100 * completed / st["level_count"], 1),
            }

        alert_rows = [dict(r) for r in db.execute(
            "SELECT * FROM alert_snapshot WHERE stock_code IN (?, ?, ?, ?)",
            (
                s.get("invest_code") or "",
                ts_code,
                _normalize_invest_code(s.get("invest_code") or ""),
                ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", ""),
            ),
        ).fetchall()]
        alert_ids = [row.get("id") for row in alert_rows if row.get("id") is not None]
        executions: list[dict[str, Any]] = []
        if alert_ids:
            placeholders = ",".join("?" * len(alert_ids))
            settlement_query = f"SELECT * FROM alert_settlement WHERE alert_id IN ({placeholders}) ORDER BY id DESC"
            for settlement in db.execute(settlement_query, tuple(alert_ids)).fetchall():
                execution = dict(settlement)
                trade = next((t for t in trades if t.get("id") == execution.get("transaction_id")), None)
                execution["trade"] = trade
                executions.append(execution)

        total_wealth = float(_assets().get("total_wealth") or 0)
        plan_detail = _build_plan_detail(
            stock=s,
            analysis=a,
            plan=p,
            staged=dict(staged) if staged else None,
            executions=executions,
            total_wealth=total_wealth,
        )

        return {
            "ts_code": ts_code,
            "name": s.get("name") or "",
            "invest_code": s.get("invest_code") or "",
            "market": s.get("market") or "",
            "sector": s.get("sector") or "",
            "stock_type": s.get("stock_type") or "",
            "invest_status": s.get("invest_status") or "WATCHING",
            "account_id": s.get("account_id") or 1,
            # Position
            "position": {
                "current_hold": current_hold,
                "avg_cost": round(avg_cost, 4),
                "cumulative_div_per_share": round(cumulative_div, 4),
                "effective_cost": round(effective_cost, 4),
                "live_price": live_price,
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round((live_price - effective_cost) / effective_cost * 100, 2) if effective_cost > 0 and current_hold > 0 else 0,
            },
            # Dividend info
            "dividend": {
                "annual_dps": annual_dps,
                "cost_yield_pct": round(cost_div_yield, 2),
                "price_yield_pct": round(price_div_yield, 2),
                "tax_rate": dividend_tax_rate,
                "annual_tax_loss": round(annual_tax_loss, 2),
                "cumulative_div_total": round(cumulative_div * current_hold, 2),
            },
            # Fundamentals
            "fundamentals": {
                "pe": s.get("pe"),
                "pb": s.get("pb"),
                "debt_ratio": s.get("debt_ratio"),
                "fcf_yield": s.get("fcf_yield"),
                "turtle_gg": a.get("gg_discounted") or a.get("gg_base"),
                "turtle_ii": a.get("ii"),
                "turtle_decision": a.get("decision"),
                "turtle_upside_pct": a.get("upside_pct"),
                "my_valuation": s.get("my_valuation"),
                "turtle_valuation": s.get("turtle_valuation"),
                "invest_logic": s.get("invest_logic") or "",
            },
            # Grid
            "grid": {
                "mth_enabled": bool(s.get("mth_enabled")),
                "mth_cycle": s.get("mth_cycle") or 1,
                "cycles_total": len(grid_cycles),
                "open_cycles": len(grid_open),
                "closed_cycles": len(grid_closed),
                "total_profit": round(grid_total_profit, 2),
                "success_count": grid_success,
                "recent_cycles": grid_cycles[:10],
            },
            # Staged buy
            "staged_buy": staged_data,
            "staged_buy_detail": plan_detail,
            # Investment plan
            "investment_plan": {
                "stop_loss_hkd": p.get("stop_loss_hkd"),
                "stop_loss_conditions": p.get("stop_loss_conditions"),
                "stop_loss_conditions_cn": _translate_obs(p.get("stop_loss_conditions")),
                "batch_buy_json": p.get("batch_buy_json"),
                "observation_signals": p.get("observation_signals"),
                "observation_signals_cn": _translate_obs(p.get("observation_signals")),
                "core_thesis": p.get("core_thesis"),
                "conviction": p.get("conviction"),
                "business_model": p.get("business_model"),
                "recent_changes": p.get("recent_changes"),
                "core_tension": p.get("core_tension"),
            } if p else None,
            # Trades
            "trades": trades,
            "trade_count": len(trades),
            "executions": executions,
            "sources": json.loads(a.get("sources_json", "[]")) if a.get("sources_json") else [],
        }
    finally:
        db.close()


def get_stock_fundamentals(ts_code: str) -> dict[str, Any]:
    """Get fundamental history for a stock. Match by ts_code directly."""
    db = _connect()
    try:
        # Query by ts_code (the key used by the write endpoint)
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM fundamentals_history WHERE stock_id = ? ORDER BY year DESC",
            (ts_code,),
        ).fetchall()]
        return {"ts_code": ts_code, "history": rows, "count": len(rows)}
    finally:
        db.close()
