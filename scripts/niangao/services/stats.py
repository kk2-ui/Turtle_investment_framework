"""Stats service — portfolio analytics parity with Android StatsViewModel.

Provides dividend yield, returns structure, sector breakdown, and portfolio-level
statistics. Data comes from portfolio.db derived tables (position_pnl, realized_pnl,
trade_record) plus watchlist.
"""

from __future__ import annotations

from typing import Any

from niangao.db import get_db, _DB_PATH


def recompute_position_pnl(db_path: str = _DB_PATH) -> int:
    """Recompute position_pnl for all current holdings. Returns row count."""
    db = get_db(db_path)
    try:
        db.execute("DELETE FROM position_pnl")
        db.execute("""
            INSERT INTO position_pnl (ts_code, invest_code, name, current_hold, avg_cost,
                live_price, market_value, unrealized_pnl, dividend_est, total_return,
                total_return_pct, updated_at)
            SELECT
                w.ts_code,
                w.invest_code,
                w.name,
                w.current_hold,
                w.avg_cost,
                w.live_price,
                COALESCE(w.current_hold, 0) * COALESCE(w.live_price, 0) AS market_value,
                (COALESCE(w.live_price, 0) - COALESCE(w.avg_cost, 0)) * COALESCE(w.current_hold, 0)
                    + COALESCE(w.cumulative_div, 0) * COALESCE(w.current_hold, 0)
                    AS unrealized_pnl,
                COALESCE(w.annual_div_per_share, 0) * COALESCE(w.current_hold, 0) AS dividend_est,
                (COALESCE(w.live_price, 0) - COALESCE(w.avg_cost, 0)) * COALESCE(w.current_hold, 0)
                    + COALESCE(w.cumulative_div, 0) * COALESCE(w.current_hold, 0)
                    AS total_return,
                CASE WHEN COALESCE(w.avg_cost, 0) > 0 AND COALESCE(w.current_hold, 0) > 0
                     THEN 100.0 * ((COALESCE(w.live_price, 0) - w.avg_cost) * w.current_hold
                           + COALESCE(w.cumulative_div, 0) * w.current_hold)
                           / (w.avg_cost * w.current_hold)
                     ELSE 0 END AS total_return_pct,
                datetime('now')
            FROM watchlist w
            WHERE COALESCE(w.current_hold, 0) > 0
        """)
        count = db.execute("SELECT COUNT(*) FROM position_pnl").fetchone()[0]
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def recompute_realized_pnl(db_path: str = _DB_PATH) -> int:
    """Recompute realized_pnl for all fully-cleared stocks. Returns row count."""
    db = get_db(db_path)
    try:
        db.execute("DELETE FROM realized_pnl")
        db.execute("""
            INSERT INTO realized_pnl (stock_code, stock_name, total_buy_amt, total_sell_amt,
                realized_pnl, updated_at)
            SELECT
                tr.stock_code,
                COALESCE(w.name, tr.stock_name, tr.stock_code) AS stock_name,
                SUM(CASE WHEN tr.trade_type = 'BUY' THEN tr.amount ELSE 0 END) AS total_buy_amt,
                SUM(CASE WHEN tr.trade_type = 'SELL' THEN tr.amount ELSE 0 END) AS total_sell_amt,
                SUM(CASE WHEN tr.trade_type = 'SELL' THEN tr.amount ELSE 0 END)
                    - SUM(CASE WHEN tr.trade_type = 'BUY' THEN tr.amount ELSE 0 END)
                    AS realized_pnl,
                datetime('now')
            FROM trade_record tr
            LEFT JOIN watchlist w ON w.ts_code = tr.stock_code
            WHERE tr.trade_type IN ('BUY', 'SELL')
            GROUP BY tr.stock_code
            HAVING COALESCE(SUM(CASE WHEN tr.trade_type IN ('BUY', 'SELL') THEN
                CASE WHEN tr.trade_type = 'BUY' THEN tr.shares ELSE -tr.shares END
            END), 0) <= 0
               AND COALESCE(
                   (SELECT current_hold FROM watchlist w2 WHERE w2.ts_code = tr.stock_code), 0
               ) <= 0
        """)
        count = db.execute("SELECT COUNT(*) FROM realized_pnl").fetchone()[0]
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def recompute_all(db_path: str = _DB_PATH) -> dict[str, int]:
    """Recompute all derived tables. Returns counts."""
    pos = recompute_position_pnl(db_path)
    real = recompute_realized_pnl(db_path)
    return {"position_pnl": pos, "realized_pnl": real}


# ── Analytics ─────────────────────────────────────────────────────────

def dividend_summary(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Dividend income summary by year and total."""
    db = get_db(db_path)
    try:
        by_year_rows = db.execute("""
            SELECT dividend_year, SUM(amount) as total, COUNT(*) as count
            FROM trade_record
            WHERE trade_type = 'DIVIDEND'
            GROUP BY dividend_year
            ORDER BY dividend_year DESC
        """).fetchall()
        by_year = {str(r["dividend_year"] or "unknown"): {"total": r["total"], "count": r["count"]}
                   for r in by_year_rows}
        total = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM trade_record WHERE trade_type = 'DIVIDEND'"
        ).fetchone()[0]
        # Estimated future annual dividends based on current holdings
        est_annual = db.execute("""
            SELECT COALESCE(SUM(w.annual_div_per_share * w.current_hold), 0)
            FROM watchlist w WHERE COALESCE(w.current_hold, 0) > 0
        """).fetchone()[0]
        return {
            "total_dividends_received": total,
            "by_year": by_year,
            "estimated_annual_dividends": est_annual,
        }
    finally:
        db.close()


def sector_breakdown(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """Portfolio sector breakdown by market value."""
    db = get_db(db_path)
    try:
        rows = db.execute("""
            SELECT
                COALESCE(NULLIF(w.sector, ''), '未分类') AS sector,
                COUNT(*) AS stock_count,
                SUM(COALESCE(w.current_hold, 0)) AS total_shares,
                SUM(COALESCE(w.current_hold, 0) * COALESCE(w.live_price, 0)) AS market_value,
                ROUND(100.0 * SUM(COALESCE(w.current_hold, 0) * COALESCE(w.live_price, 0))
                      / (SELECT COALESCE(SUM(COALESCE(current_hold,0) * COALESCE(live_price,0)), 1)
                         FROM watchlist), 1) AS weight_pct
            FROM watchlist w
            WHERE COALESCE(w.current_hold, 0) > 0
            GROUP BY sector
            ORDER BY market_value DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def account_breakdown(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """Portfolio breakdown by account."""
    db = get_db(db_path)
    try:
        rows = db.execute("""
            SELECT
                a.id AS account_id,
                a.name AS account_name,
                a.ownership_pct,
                COUNT(DISTINCT w.ts_code) AS stock_count,
                SUM(COALESCE(w.current_hold, 0) * COALESCE(w.live_price, 0)) AS stock_value,
                COALESCE(SUM(c.amount), 0) AS cash_balance
            FROM account a
            LEFT JOIN watchlist w ON w.account_id = a.id AND COALESCE(w.current_hold, 0) > 0
            LEFT JOIN cash c ON c.account_id = a.id
            GROUP BY a.id, a.name
            ORDER BY a.id
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def portfolio_returns(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Portfolio-level return metrics."""
    db = get_db(db_path)
    try:
        # Current portfolio value
        stock_value = db.execute(
            "SELECT COALESCE(SUM(COALESCE(current_hold,0) * COALESCE(live_price,0)), 0) FROM watchlist"
        ).fetchone()[0]
        total_cash = db.execute("SELECT COALESCE(SUM(amount), 0) FROM cash").fetchone()[0]
        current_wealth = stock_value + total_cash

        # Total invested (buy amounts)
        total_invested = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM trade_record WHERE trade_type = 'BUY'"
        ).fetchone()[0]
        total_divested = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM trade_record WHERE trade_type = 'SELL'"
        ).fetchone()[0]
        total_dividends = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM trade_record WHERE trade_type = 'DIVIDEND'"
        ).fetchone()[0]
        total_inflow = db.execute(
            "SELECT COALESCE(SUM(delta_cny), 0) FROM cash_flow"
        ).fetchone()[0]

        # Unrealized PnL (aggregate from position_pnl)
        unrealized = db.execute(
            "SELECT COALESCE(SUM(unrealized_pnl), 0) FROM position_pnl"
        ).fetchone()[0]

        # Realized PnL
        realized = db.execute(
            "SELECT COALESCE(SUM(realized_pnl), 0) FROM realized_pnl"
        ).fetchone()[0]

        # Latest wealth snapshot
        latest_snapshot = db.execute(
            "SELECT * FROM wealth_snapshot ORDER BY snapshot_at DESC LIMIT 1"
        ).fetchone()

        return {
            "current_wealth_cny": current_wealth,
            "stock_value_cny": stock_value,
            "cash_cny": total_cash,
            "total_invested_cny": total_invested,
            "total_divested_cny": total_divested,
            "total_dividends_cny": total_dividends,
            "total_inflow_cny": total_inflow,
            "unrealized_pnl_cny": unrealized,
            "realized_pnl_cny": realized,
            "total_pnl_cny": unrealized + realized,
            "latest_snapshot": dict(latest_snapshot) if latest_snapshot else None,
        }
    finally:
        db.close()


def stock_performance(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Per-stock performance metrics (dividend yield, PnL, cost basis)."""
    db = get_db(db_path)
    try:
        stock = db.execute("SELECT * FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone()
        if stock is None:
            return {"error": f"Stock {ts_code} not found"}

        trades = db.execute(
            "SELECT * FROM trade_record WHERE stock_code = ? ORDER BY trade_at",
            (ts_code,),
        ).fetchall()

        buys = [t for t in trades if t["trade_type"] == "BUY"]
        sells = [t for t in trades if t["trade_type"] == "SELL"]
        divs = [t for t in trades if t["trade_type"] == "DIVIDEND"]

        total_buy_amount = sum(t["amount"] for t in buys)
        total_buy_shares = sum(t["shares"] or 0 for t in buys)
        total_sell_amount = sum(t["amount"] for t in sells)
        total_sell_shares = sum(t["shares"] or 0 for t in sells)
        total_div_amount = sum(t["amount"] for t in divs)

        avg_buy_price = total_buy_amount / total_buy_shares if total_buy_shares > 0 else 0
        avg_sell_price = total_sell_amount / total_sell_shares if total_sell_shares > 0 else 0

        current = dict(stock)
        current_hold = current.get("current_hold") or 0
        live_price = current.get("live_price") or 0
        avg_cost = current.get("avg_cost") or 0

        dividend_yield = 0.0
        if avg_cost > 0 and current.get("annual_div_per_share"):
            dividend_yield = (current["annual_div_per_share"] / avg_cost) * 100

        return {
            "ts_code": ts_code,
            "name": current.get("name") or "",
            "current_hold": current_hold,
            "avg_cost": avg_cost,
            "live_price": live_price,
            "market_value": current_hold * live_price,
            "avg_buy_price": avg_buy_price,
            "avg_sell_price": avg_sell_price,
            "total_buy_amount": total_buy_amount,
            "total_sell_amount": total_sell_amount,
            "total_dividend_amount": total_div_amount,
            "realized_pnl": total_sell_amount - total_buy_amount + total_div_amount,
            "dividend_yield_pct": round(dividend_yield, 2),
            "trade_count": len(trades),
            "cumulative_div_per_share": current.get("cumulative_div") or 0,
        }
    finally:
        db.close()


# ── Phase B: Advanced analytics ──────────────────────────────────────

def monthly_dividends(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Monthly dividend breakdown with cumulative line data."""
    db = get_db(db_path)
    try:
        divs = [dict(r) for r in db.execute(
            "SELECT amount, trade_at FROM trade_record WHERE trade_type='DIVIDEND' AND amount > 0 ORDER BY trade_at"
        ).fetchall()]
        by_month: dict[str, float] = {}
        for d in divs:
            ts = d.get("trade_at", 0)
            if ts and ts > 0:
                from datetime import datetime
                dt = datetime.fromtimestamp(ts / 1000)
                key = dt.strftime("%Y-%m")
            else:
                key = "unknown"
            by_month[key] = by_month.get(key, 0) + (d["amount"] or 0)

        sorted_months = sorted(by_month.keys())
        cumulative = 0.0
        monthly_data = []
        for m in sorted_months:
            cumulative += by_month[m]
            monthly_data.append({
                "month": m,
                "amount": round(by_month[m], 2),
                "cumulative": round(cumulative, 2),
            })

        # Current year estimate
        now = __import__('datetime').datetime.now()
        this_year = str(now.year)
        ytd_actual = sum(v for k, v in by_month.items() if k.startswith(this_year))
        # Estimate from watchlist
        est = db.execute(
            "SELECT COALESCE(SUM(COALESCE(annual_div_per_share,0) * COALESCE(current_hold,0) * (1 - COALESCE(dividend_tax_rate,0))), 0) FROM watchlist WHERE COALESCE(current_hold,0) > 0"
        ).fetchone()[0]

        # Per-stock dividend contribution
        stock_divs = [dict(r) for r in db.execute("""
            SELECT stock_code, SUM(amount) as total
            FROM trade_record WHERE trade_type='DIVIDEND' AND amount > 0
            GROUP BY stock_code ORDER BY total DESC
        """).fetchall()]

        return {
            "total_received": round(sum(by_month.values()), 2),
            "monthly": monthly_data,
            "ytd_actual": round(ytd_actual, 2),
            "estimated_annual": round(est, 2),
            "stock_contributions": [{"stock_code": s["stock_code"], "total": round(s["total"], 2)} for s in stock_divs],
        }
    finally:
        db.close()


def fundamentals_trends(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Portfolio-level PE/PB/debt/FCF trends over years from fundamentals_history."""
    db = get_db(db_path)
    try:
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM fundamentals_history ORDER BY year"
        ).fetchall()]
        if not rows:
            return {"trends": [], "note": "No fundamentals_history data"}

        # Group by year, average across stocks
        by_year: dict[int, dict] = {}
        for r in rows:
            y = r.get("year")
            if not y:
                continue
            if y not in by_year:
                by_year[y] = {"pe": [], "pb": [], "debt_ratio": [], "fcf_yield": [], "count": 0}
            by_year[y]["count"] += 1
            for field in ["pe", "pb", "debt_ratio", "fcf_yield"]:
                v = r.get(field)
                if v is not None and v > 0:
                    by_year[y][field].append(v)

        trends = []
        for y in sorted(by_year.keys()):
            d = by_year[y]
            trends.append({
                "year": y,
                "stock_count": d["count"],
                "avg_pe": round(sum(d["pe"]) / len(d["pe"]), 2) if d["pe"] else None,
                "avg_pb": round(sum(d["pb"]) / len(d["pb"]), 2) if d["pb"] else None,
                "avg_debt_ratio": round(sum(d["debt_ratio"]) / len(d["debt_ratio"]), 2) if d["debt_ratio"] else None,
                "avg_fcf_yield": round(sum(d["fcf_yield"]) / len(d["fcf_yield"]), 2) if d["fcf_yield"] else None,
            })
        return {"trends": trends}
    finally:
        db.close()


def strategy_attribution(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Strategy attribution: grid profit, MTH, staged buy stats."""
    db = get_db(db_path)
    try:
        # Grid
        grid_closed = db.execute(
            "SELECT COUNT(*) as n, COALESCE(SUM(profit),0) as profit, AVG(profit) as avg FROM grid_cycle_record WHERE buy_price IS NOT NULL"
        ).fetchone()
        grid_open = db.execute(
            "SELECT COUNT(*) FROM grid_cycle_record WHERE buy_price IS NULL"
        ).fetchone()[0]
        grid_success = db.execute(
            "SELECT COUNT(*) FROM grid_cycle_record WHERE is_success=1"
        ).fetchone()[0]

        # MTH
        mth_count = db.execute(
            "SELECT COUNT(*) FROM watchlist WHERE mth_enabled=1"
        ).fetchone()[0]
        mth_stocks = [dict(r) for r in db.execute(
            "SELECT ts_code, name, mth_cycle FROM watchlist WHERE mth_enabled=1"
        ).fetchall()]

        # Staged buy
        staged_plans = db.execute("SELECT COUNT(*) FROM staged_buy_plan").fetchone()[0]
        import json as _json
        staged_rows = [dict(r) for r in db.execute("SELECT * FROM staged_buy_plan").fetchall()]
        staged_total_levels = 0
        staged_completed = 0
        for s in staged_rows:
            levels = _json.loads(s.get("levels_json", "[]"))
            staged_total_levels += len(levels)
            staged_completed += sum(1 for l in levels if l.get("completed"))

        # Total buy/sell amounts
        total_buy = db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM trade_record WHERE trade_type='BUY'"
        ).fetchone()[0]
        total_sell = db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM trade_record WHERE trade_type='SELL'"
        ).fetchone()[0]

        return {
            "grid": {
                "closed_cycles": grid_closed["n"] or 0,
                "open_cycles": grid_open,
                "total_profit": round(grid_closed["profit"] or 0, 2),
                "avg_profit": round(grid_closed["avg"] or 0, 2),
                "success_count": grid_success,
                "success_rate": round(grid_success / grid_closed["n"] * 100, 1) if grid_closed["n"] > 0 else 0,
            },
            "mth": {
                "active_stocks": mth_count,
                "stocks": mth_stocks,
            },
            "staged_buy": {
                "plans": staged_plans,
                "total_levels": staged_total_levels,
                "completed_levels": staged_completed,
                "completion_pct": round(staged_completed / staged_total_levels * 100, 1) if staged_total_levels > 0 else 0,
            },
            "trade_summary": {
                "total_buy_cny": round(total_buy, 2),
                "total_sell_cny": round(total_sell, 2),
                "net_invested": round(total_buy - total_sell, 2),
            },
        }
    finally:
        db.close()


def irr(db_path: str = _DB_PATH) -> dict[str, Any]:
    """IRR via Newton's method from wealth snapshots and cash flows.

    Uses cash_flow entries as cash events and latest wealth as terminal value.
    """
    db = get_db(db_path)
    try:
        # Cash flows: each flow_at is a timestamp, delta_cny is the amount
        flows = [dict(r) for r in db.execute(
            "SELECT flow_at, delta_cny FROM cash_flow WHERE delta_cny IS NOT NULL ORDER BY flow_at"
        ).fetchall()]

        # Latest wealth
        wealth_row = db.execute(
            "SELECT * FROM wealth_snapshot ORDER BY snapshot_at DESC LIMIT 1"
        ).fetchone()
        if not wealth_row or not flows:
            return {"irr_pct": None, "note": "Insufficient data for IRR calculation"}

        latest_wealth = wealth_row["total_wealth_cny"] or 0

        # Build cash flow series: negative = outflow (deposit), positive = inflow
        cf_series = []
        for f in flows:
            t = (f["flow_at"] or 0) / 1000.0 / 86400.0 / 365.25  # epoch ms → years
            cf_series.append((t, -f["delta_cny"]))  # delta_cny positive = cash added, so -delta = outflow for IRR

        # Add terminal value at the end
        now_days = (__import__('time').time()) / 86400.0 / 365.25
        cf_series.append((now_days, latest_wealth))

        if len(cf_series) < 2:
            return {"irr_pct": None, "note": "Need at least 2 cash flow points"}

        # Reference time = first flow
        t0 = cf_series[0][0]
        times = [t - t0 for t, _ in cf_series]
        amounts = [amt for _, amt in cf_series]

        # NPV function
        def npv(rate):
            return sum(a / ((1 + rate) ** t) for a, t in zip(amounts, times))

        # Newton's method to find IRR
        rate = 0.05  # initial guess 5%
        for _ in range(100):
            f = npv(rate)
            if abs(f) < 0.01:
                break
            # Derivative (numerical)
            df = (npv(rate + 0.0001) - f) / 0.0001
            if abs(df) < 1e-12:
                break
            rate -= f / df
            if rate < -0.99:
                rate = -0.5
            if rate > 100:
                rate = 1.0

        irr_pct = round(rate * 100, 2)

        # Annualized return from wealth snapshots
        first_row = db.execute(
            "SELECT * FROM wealth_snapshot ORDER BY snapshot_at ASC LIMIT 1"
        ).fetchone()
        ann_pct = None
        if first_row and first_row["total_wealth_cny"]:
            start_w = first_row["total_wealth_cny"]
            start_ts = (first_row["snapshot_at"] or 0) / 1000.0 / 86400.0 / 365.25
            end_ts = (wealth_row["snapshot_at"] or 0) / 1000.0 / 86400.0 / 365.25
            years = max(end_ts - start_ts, 0.001)
            ann_pct = round(((latest_wealth / start_w) ** (1 / years) - 1) * 100, 2)

        return {
            "irr_pct": irr_pct,
            "annualized_pct": ann_pct,
            "latest_wealth": round(latest_wealth, 2),
            "cash_flow_count": len(flows),
        }
    finally:
        db.close()


def detailed_returns(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Combined detailed returns: portfolio_returns + IRR + annual summaries."""
    basic = portfolio_returns(db_path)
    irr_data = irr(db_path)

    db = get_db(db_path)
    try:
        years = [dict(r) for r in db.execute(
            "SELECT * FROM annual_summary ORDER BY year"
        ).fetchall()]
        wealth_snapshots = [dict(r) for r in db.execute(
            "SELECT snapshot_at, total_wealth_cny FROM wealth_snapshot ORDER BY snapshot_at"
        ).fetchall()]
    finally:
        db.close()

    return {
        **basic,
        "irr_pct": irr_data.get("irr_pct"),
        "annualized_pct": irr_data.get("annualized_pct"),
        "annual_summaries": years,
        "wealth_series": [{"ts": s["snapshot_at"], "wealth": s["total_wealth_cny"]} for s in wealth_snapshots],
        "snapshot_count": len(wealth_snapshots),
    }
