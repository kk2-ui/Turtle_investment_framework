"""niangao.reconcile — 只读一致性检查：investor.db ↔ portfolio.db

Phase 1 starter for the Web-replaces-invest migration. This module reads the
Android invest database (or backup zip) and the local portfolio.db, then reports
row-count and aggregate differences without mutating either database.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from niangao.db import _DB_PATH, _normalize_invest_code

_ANALY_DIR = Path(__file__).resolve().parents[3]
_INVEST_DIR = _ANALY_DIR / "invest"


@dataclass
class CheckResult:
    name: str
    status: str
    summary: str
    details: dict[str, Any]


_PRICE_DRIFT_FIELDS = {"currentPrice"}


def _worst_abs(rows: list[dict[str, Any]]) -> float:
    worst = 0.0
    for row in rows:
        try:
            worst = max(worst, abs(float(row.get("android") or 0) - float(row.get("portfolio") or 0)))
        except (TypeError, ValueError):
            pass
    return worst


def _connect_readonly(path: str | Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    con = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _extract_invest_db(backup_path: str | Path) -> str:
    backup = Path(backup_path)
    if backup.suffix != ".zip":
        return str(backup)
    tmpdir = Path(tempfile.mkdtemp(prefix="niangao_reconcile_"))
    with zipfile.ZipFile(backup, "r") as zf:
        if "investor.db" not in zf.namelist():
            raise FileNotFoundError(f"investor.db not found in backup: {backup}")
        zf.extract("investor.db", tmpdir)
    return str(tmpdir / "investor.db")


def _find_latest_backup() -> str | None:
    candidates: list[Path] = []
    for directory in [Path("/tmp"), _INVEST_DIR / "backups"]:
        if directory.exists():
            candidates.extend(directory.glob("investor_backup_*.zip"))
    if not candidates:
        direct = _INVEST_DIR / "investor.db"
        return str(direct) if direct.exists() else None
    return str(sorted(candidates)[-1])


def _scalar(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = con.execute(sql, params).fetchone()
    return row[0] if row else None


def _safe_scalar(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    try:
        return _scalar(con, sql, params)
    except sqlite3.Error:
        return None


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return bool(_scalar(con, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)))


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _count(con: sqlite3.Connection, table: str, where: str = "") -> int:
    if not _table_exists(con, table):
        return 0
    sql = f"SELECT COUNT(*) FROM {_ident(table)}"
    if where:
        sql += f" WHERE {where}"
    return int(_scalar(con, sql) or 0)


def _sum(con: sqlite3.Connection, table: str, column: str, where: str = "") -> float:
    if not _table_exists(con, table):
        return 0.0
    sql = f"SELECT COALESCE(SUM({_ident(column)}),0) FROM {_ident(table)}"
    if where:
        sql += f" WHERE {where}"
    return float(_scalar(con, sql) or 0.0)


def _status(ok: bool) -> str:
    return "PASS" if ok else "WARN"


def _rounded(value: Any, digits: int = 4) -> float:
    try:
        return round(float(value or 0), digits)
    except (TypeError, ValueError):
        return 0.0


def _key_diff(left: set[tuple[Any, ...]], right: set[tuple[Any, ...]], limit: int = 30) -> dict[str, Any]:
    missing = sorted(left - right)
    extra = sorted(right - left)
    return {
        "missing_in_portfolio": [list(x) for x in missing[:limit]],
        "extra_in_portfolio": [list(x) for x in extra[:limit]],
        "missing_count": len(missing),
        "extra_count": len(extra),
        "truncated": len(missing) > limit or len(extra) > limit,
    }


def _group_tuple_counts(keys: set[tuple[Any, ...]], index: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in keys:
        value = str(key[index]) if len(key) > index else ""
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _numeric_range(keys: set[tuple[Any, ...]], index: int = 0) -> dict[str, Any]:
    vals = []
    for key in keys:
        if len(key) <= index:
            continue
        try:
            vals.append(float(key[index]))
        except (TypeError, ValueError):
            pass
    if not vals:
        return {"min": None, "max": None}
    return {"min": min(vals), "max": max(vals)}


def check_stock_watchlist(idb: sqlite3.Connection, pdb: sqlite3.Connection) -> CheckResult:
    android_total = _count(idb, "stock")
    portfolio_total = _count(pdb, "watchlist")
    android_holding = _count(idb, "stock", "currentHold > 0")
    portfolio_holding = _count(pdb, "watchlist", "current_hold > 0")

    missing: list[str] = []
    sync_mismatches: list[dict[str, Any]] = []
    quote_drifts: list[dict[str, Any]] = []
    extra_codes: list[str] = []
    extra_code_details: list[dict[str, Any]] = []
    if _table_exists(idb, "stock") and _table_exists(pdb, "watchlist"):
        android_codes = {r["code"] for r in idb.execute("SELECT code FROM stock")}
        wrows = {r["invest_code"]: dict(r) for r in pdb.execute("SELECT * FROM watchlist WHERE invest_code IS NOT NULL")}
        extra_codes = sorted([code for code in wrows if code not in android_codes])
        extra_code_details = []
        for code in extra_codes:
            prow = wrows.get(code) or {}
            ts_code = prow.get("ts_code") or _normalize_invest_code(code)
            has_analysis = bool(_safe_scalar(pdb, "SELECT 1 FROM analysis WHERE ts_code=?", (ts_code,)))
            has_trades = bool(_safe_scalar(pdb, "SELECT 1 FROM trade_record WHERE stock_code=?", (code,)))
            extra_code_details.append({
                "invest_code": code,
                "ts_code": ts_code,
                "name": prow.get("name"),
                "current_hold": prow.get("current_hold"),
                "status": prow.get("invest_status"),
                "has_analysis": has_analysis,
                "has_trades": has_trades,
            })
        for r in idb.execute("SELECT code, name, status, currentHold, avgCost, currentPrice, annualDivPerShare FROM stock"):
            ts = _normalize_invest_code(r["code"])
            prow = wrows.get(r["code"])
            if not prow:
                missing.append(r["code"])
                continue
            for a_col, p_col in [("currentHold", "current_hold"), ("avgCost", "avg_cost"), ("currentPrice", "live_price"), ("annualDivPerShare", "annual_div_per_share")]:
                av = r[a_col]
                pv = prow[p_col]
                if av is None and pv is None:
                    continue
                if abs(float(av or 0) - float(pv or 0)) > 1e-6:
                    target = quote_drifts if a_col in _PRICE_DRIFT_FIELDS else sync_mismatches
                    target.append({"code": r["code"], "ts_code": ts, "field": a_col, "android": av, "portfolio": pv})
                    break

    structural_ok = android_holding == portfolio_holding and not missing and not sync_mismatches
    status = "PASS" if structural_ok and android_total == portfolio_total and not quote_drifts else ("INFO" if structural_ok else "WARN")
    return CheckResult(
        name="stock_watchlist",
        status=status,
        summary=f"Android stock {android_total} / holding {android_holding}; portfolio watchlist {portfolio_total} / holding {portfolio_holding}; quote drifts {len(quote_drifts)}",
        details={
            "android_total": android_total,
            "portfolio_total": portfolio_total,
            "android_holding": android_holding,
            "portfolio_holding": portfolio_holding,
            "extra_portfolio_codes": extra_code_details[:20],
            "missing_in_portfolio": missing[:20],
            "sync_mismatches": sync_mismatches[:20],
            "quote_freshness_drifts": quote_drifts[:20],
            "max_quote_abs_diff": round(_worst_abs(quote_drifts), 4),
            "truncated": len(extra_codes) > 20 or len(missing) > 20 or len(sync_mismatches) > 20 or len(quote_drifts) > 20,
        },
    )


def check_transactions(idb: sqlite3.Connection, pdb: sqlite3.Connection) -> CheckResult:
    android_total = _count(idb, "transaction")
    portfolio_total = _count(pdb, "trade_record")
    android_ids = {r[0] for r in idb.execute("SELECT id FROM 'transaction'")} if _table_exists(idb, "transaction") else set()
    portfolio_ids = {r[0] for r in pdb.execute("SELECT id FROM trade_record")} if _table_exists(pdb, "trade_record") else set()
    missing_ids = sorted(android_ids - portfolio_ids)
    extra_ids = sorted(portfolio_ids - android_ids)

    by_type: dict[str, dict[str, float]] = {}
    for t in ["BUY", "SELL", "DIVIDEND"]:
        by_type[t] = {
            "android_count": _count(idb, "transaction", f"type='{t}'"),
            "portfolio_count": _count(pdb, "trade_record", f"trade_type='{t}'"),
            "android_amount": round(_sum(idb, "transaction", "amount", f"type='{t}'"), 2),
            "portfolio_amount": round(_sum(pdb, "trade_record", "amount", f"trade_type='{t}'"), 2),
        }

    totals_ok = android_total == portfolio_total and not missing_ids and not extra_ids
    amounts_ok = all(v["android_count"] == v["portfolio_count"] and abs(v["android_amount"] - v["portfolio_amount"]) < 0.01 for v in by_type.values())
    return CheckResult(
        name="transactions",
        status=_status(totals_ok and amounts_ok),
        summary=f"Android transactions {android_total}; portfolio trade_record {portfolio_total}",
        details={"by_type": by_type, "missing_ids": missing_ids[:50], "extra_ids": extra_ids[:50], "truncated": len(missing_ids) > 50 or len(extra_ids) > 50},
    )


def check_cash_accounts(idb: sqlite3.Connection, pdb: sqlite3.Connection) -> CheckResult:
    cash_mismatches: list[dict[str, Any]] = []
    if _table_exists(idb, "cash") and _table_exists(pdb, "cash"):
        pcash = {(r["currency"], r["account_id"]): r["amount"] for r in pdb.execute("SELECT currency, account_id, amount FROM cash")}
        for r in idb.execute("SELECT currency, accountId, amount FROM cash"):
            key = (r["currency"], r["accountId"])
            pv = pcash.get(key)
            if pv is None or abs(float(r["amount"] or 0) - float(pv or 0)) > 0.01:
                cash_mismatches.append({"currency": key[0], "account_id": key[1], "android": r["amount"], "portfolio": pv})

    account_mismatches: list[dict[str, Any]] = []
    if _table_exists(idb, "account") and _table_exists(pdb, "account"):
        paccounts = {r["id"]: dict(r) for r in pdb.execute("SELECT * FROM account")}
        for r in idb.execute("SELECT * FROM account"):
            p = paccounts.get(r["id"])
            if not p or r["name"] != p["name"] or abs(float(r["ownershipPct"] or 0) - float(p["ownership_pct"] or 0)) > 1e-9:
                account_mismatches.append({"id": r["id"], "android_name": r["name"], "portfolio": p})

    return CheckResult(
        name="cash_accounts",
        status=_status(not cash_mismatches and not account_mismatches),
        summary=f"cash mismatches {len(cash_mismatches)}; account mismatches {len(account_mismatches)}",
        details={"cash_mismatches": cash_mismatches[:20], "account_mismatches": account_mismatches[:20]},
    )


def check_alerts(idb: sqlite3.Connection, pdb: sqlite3.Connection) -> CheckResult:
    android_active = _count(idb, "alert", "isActive=1")
    portfolio_active = _count(pdb, "alert_snapshot", "is_active=1")
    android_triggered = _count(idb, "alert", "isActive=1 AND isTriggered=1")
    portfolio_triggered = _count(pdb, "alert_snapshot", "is_active=1 AND is_triggered=1")

    android_keys: set[tuple[Any, ...]] = set()
    portfolio_keys: set[tuple[Any, ...]] = set()
    triggered_mismatches: list[dict[str, Any]] = []
    if _table_exists(idb, "alert") and _table_exists(idb, "stock"):
        for r in idb.execute("""
            SELECT s.code, a.alertType, a.targetPrice, a.isTriggered, a.isCompleted, a.notes
            FROM alert a JOIN stock s ON a.stockId=s.id
            WHERE a.isActive=1
        """):
            key = (r["code"], r["alertType"], _rounded(r["targetPrice"]))
            android_keys.add(key)
    if _table_exists(pdb, "alert_snapshot"):
        for r in pdb.execute("SELECT stock_code, alert_type, target_price, is_triggered FROM alert_snapshot WHERE is_active=1"):
            key = (r["stock_code"], r["alert_type"], _rounded(r["target_price"]))
            portfolio_keys.add(key)
    common = android_keys & portfolio_keys
    if common and _table_exists(idb, "alert") and _table_exists(idb, "stock") and _table_exists(pdb, "alert_snapshot"):
        android_trigger_by_key = {}
        for r in idb.execute("""
            SELECT s.code, a.alertType, a.targetPrice, a.isTriggered
            FROM alert a JOIN stock s ON a.stockId=s.id
            WHERE a.isActive=1
        """):
            android_trigger_by_key[(r["code"], r["alertType"], _rounded(r["targetPrice"]))] = r["isTriggered"]
        portfolio_trigger_by_key = {}
        for r in pdb.execute("SELECT stock_code, alert_type, target_price, is_triggered FROM alert_snapshot WHERE is_active=1"):
            portfolio_trigger_by_key[(r["stock_code"], r["alert_type"], _rounded(r["target_price"]))] = r["is_triggered"]
        for key in sorted(common):
            av = int(android_trigger_by_key.get(key) or 0)
            pv = int(portfolio_trigger_by_key.get(key) or 0)
            if av != pv:
                triggered_mismatches.append({"key": list(key), "android_triggered": av, "portfolio_triggered": pv})

    key_diff = _key_diff(android_keys, portfolio_keys)
    missing_keys = android_keys - portfolio_keys
    extra_keys = portfolio_keys - android_keys
    same_stock_type_price_changed = []
    extra_by_stock_type = {(k[0], k[1]) for k in extra_keys}
    missing_by_stock_type = {(k[0], k[1]) for k in missing_keys}
    for stock_type in sorted(extra_by_stock_type & missing_by_stock_type):
        missing_prices = sorted([k[2] for k in missing_keys if (k[0], k[1]) == stock_type])
        extra_prices = sorted([k[2] for k in extra_keys if (k[0], k[1]) == stock_type])
        same_stock_type_price_changed.append({"stock_code": stock_type[0], "alert_type": stock_type[1], "android_prices": missing_prices, "portfolio_prices": extra_prices})
    ok = android_active == portfolio_active and android_triggered == portfolio_triggered and key_diff["missing_count"] == 0 and key_diff["extra_count"] == 0 and not triggered_mismatches
    return CheckResult(
        name="alerts",
        status=_status(ok),
        summary=f"active Android {android_active} / portfolio {portfolio_active}; triggered Android {android_triggered} / portfolio {portfolio_triggered}; key diff missing {key_diff['missing_count']} extra {key_diff['extra_count']}",
        details={
            "android_active": android_active,
            "portfolio_active": portfolio_active,
            "android_triggered": android_triggered,
            "portfolio_triggered": portfolio_triggered,
            "identity_key": ["stock_code", "alert_type", "target_price_rounded_4dp"],
            "key_diff": key_diff,
            "missing_by_type": _group_tuple_counts(missing_keys, 1),
            "extra_by_type": _group_tuple_counts(extra_keys, 1),
            "price_changed_same_stock_type": same_stock_type_price_changed[:30],
            "triggered_mismatches": triggered_mismatches[:30],
            "known_gaps": ["portfolio alert_snapshot does not preserve Android alert.id, isCompleted, createdAt, notes"],
        },
    )


def check_history_counts(idb: sqlite3.Connection, pdb: sqlite3.Connection) -> CheckResult:
    specs = [
        {
            "name": "portfolio_snapshot->wealth_snapshot",
            "android_sql": "SELECT timestamp FROM portfolio_snapshot",
            "portfolio_sql": "SELECT snapshot_at FROM wealth_snapshot",
        },
        {
            "name": "portfolio_year_snapshot->annual_summary",
            "android_sql": "SELECT year FROM portfolio_year_snapshot",
            "portfolio_sql": "SELECT year FROM annual_summary",
        },
        {
            "name": "price_history->price_history",
            "android_sql": "SELECT stockId, tradeDate FROM price_history",
            "portfolio_sql": "SELECT stock_id, trade_date FROM price_history",
        },
        {
            "name": "fundamentals_history->fundamentals_history",
            "android_sql": "SELECT stockId, year FROM fundamentals_history",
            "portfolio_sql": "SELECT stock_id, year FROM fundamentals_history",
        },
        {
            "name": "month_end_price->month_end_price",
            "android_sql": "SELECT stockId, yearMonth FROM month_end_price",
            "portfolio_sql": "SELECT stock_id, year_month FROM month_end_price",
        },
        {
            "name": "month_end_exchange_rate->month_end_exchange_rate",
            "android_sql": "SELECT yearMonth FROM month_end_exchange_rate",
            "portfolio_sql": "SELECT year_month FROM month_end_exchange_rate",
        },
        {
            "name": "alert_settlement->alert_settlement",
            "android_sql": "SELECT id FROM alert_settlement",
            "portfolio_sql": "SELECT id FROM alert_settlement",
        },
        {
            "name": "account_portfolio_snapshot->account_portfolio_snapshot",
            "android_sql": "SELECT timestamp, accountId FROM account_portfolio_snapshot",
            "portfolio_sql": "SELECT snapshot_at, account_id FROM account_portfolio_snapshot",
        },
        {
            "name": "external_cash_flow->cash_flow",
            "android_sql": "SELECT id FROM external_cash_flow",
            "portfolio_sql": "SELECT id FROM cash_flow",
        },
    ]
    results: dict[str, dict[str, Any]] = {}
    mismatched = []
    for spec in specs:
        try:
            android_keys = {tuple(r) for r in idb.execute(spec["android_sql"])}
            portfolio_keys = {tuple(r) for r in pdb.execute(spec["portfolio_sql"])}
        except sqlite3.Error as exc:
            results[spec["name"]] = {"error": str(exc)}
            mismatched.append(spec["name"])
            continue
        diff = _key_diff(android_keys, portfolio_keys)
        missing_keys = android_keys - portfolio_keys
        extra_keys = portfolio_keys - android_keys
        results[spec["name"]] = {
            "android": len(android_keys),
            "portfolio": len(portfolio_keys),
            **diff,
            "missing_key_range": _numeric_range(missing_keys),
            "extra_key_range": _numeric_range(extra_keys),
        }
        if diff["missing_count"] or diff["extra_count"]:
            mismatched.append(spec["name"])
    return CheckResult(
        name="history_counts",
        status=_status(not mismatched),
        summary=f"{len(specs) - len(mismatched)}/{len(specs)} history key sets match",
        details={"tables": results, "mismatched": mismatched},
    )


def check_derived_pnl(idb: sqlite3.Connection, pdb: sqlite3.Connection) -> CheckResult:
    android_holding = _count(idb, "stock", "currentHold > 0")
    position_pnl = _count(pdb, "position_pnl")
    sell_codes = _safe_scalar(pdb, "SELECT COUNT(DISTINCT stock_code) FROM trade_record WHERE trade_type='SELL'") or 0
    realized = _count(pdb, "realized_pnl")
    ok = position_pnl >= android_holding and realized <= sell_codes
    return CheckResult(
        name="derived_pnl",
        status=_status(ok),
        summary=f"position_pnl {position_pnl} vs Android holdings {android_holding}; realized_pnl {realized} vs sold codes {sell_codes}",
        details={"android_holding": android_holding, "position_pnl": position_pnl, "sold_codes": sell_codes, "realized_pnl": realized},
    )


def run_reconcile(invest_db: str, portfolio_db: str) -> dict[str, Any]:
    idb = _connect_readonly(invest_db)
    pdb = _connect_readonly(portfolio_db)
    try:
        checks = [
            check_stock_watchlist(idb, pdb),
            check_transactions(idb, pdb),
            check_cash_accounts(idb, pdb),
            check_alerts(idb, pdb),
            check_history_counts(idb, pdb),
            check_derived_pnl(idb, pdb),
        ]
    finally:
        idb.close()
        pdb.close()
    status = "PASS" if all(c.status == "PASS" for c in checks) else ("INFO" if all(c.status in {"PASS", "INFO"} for c in checks) else "WARN")
    return {"status": status, "invest_db": invest_db, "portfolio_db": portfolio_db, "checks": [asdict(c) for c in checks]}


def _print_text(report: dict[str, Any]) -> None:
    print(f"Overall: {report['status']}")
    print(f"invest_db: {report['invest_db']}")
    print(f"portfolio_db: {report['portfolio_db']}")
    for check in report["checks"]:
        print(f"- {check['status']} {check['name']}: {check['summary']}")
        if check["status"] != "PASS":
            print(json.dumps(check["details"], ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only reconcile between Android investor.db and _niangao portfolio.db")
    parser.add_argument("--invest-db", help="Path to extracted Android investor.db")
    parser.add_argument("--backup", help="Path to investor_backup_*.zip; overrides --invest-db")
    parser.add_argument("--portfolio-db", default=_DB_PATH, help="Path to _niangao/portfolio.db")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    source = args.backup or args.invest_db or _find_latest_backup()
    if not source:
        raise SystemExit("No invest DB/backup found. Pass --invest-db or --backup.")
    invest_db = _extract_invest_db(source)
    report = run_reconcile(invest_db, args.portfolio_db)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
