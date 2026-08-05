"""Stock/watchlist service — CRUD operations on watchlist table.

Port of Android StockDao / StockRepository semantics for the canonical portfolio.db.
Manages stock metadata, position tracking, and watchlist membership.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from niangao.db import get_db, _DB_PATH, _normalize_invest_code


class StockError(RuntimeError):
    """Raised when a stock operation cannot complete."""


@dataclass
class StockSnapshot:
    ts_code: str
    invest_code: str | None
    name: str
    market: str
    current_hold: int
    avg_cost: float | None
    live_price: float | None
    invest_status: str
    cumulative_div: float
    invest_logic: str | None
    my_valuation: float | None
    turtle_valuation: float | None
    sector: str | None
    stock_type: str | None
    hold_limit_pct: float | None
    mth_enabled: bool
    account_id: int


# ── CRUD ─────────────────────────────────────────────────────────────

def upsert_stock(
    *,
    ts_code: str,
    name: str = "",
    market: str = "",
    invest_code: str = "",
    invest_status: str = "WATCHING",
    current_hold: int = 0,
    avg_cost: float = 0.0,
    hold_limit_pct: float = 0.05,
    annual_div_per_share: float = 0.0,
    invest_logic: str = "",
    my_valuation: float = 0.0,
    turtle_valuation: float = 0.0,
    live_price: float = 0.0,
    sector: str = "",
    stock_type: str = "",
    pe: float | None = None,
    pb: float | None = None,
    debt_ratio: float | None = None,
    fcf_yield: float | None = None,
    mth_enabled: bool = False,
    mth_cycle: int = 1,
    lock_reserve: bool = True,
    cumulative_div: float = 0.0,
    dividend_tax_rate: float = 0.0,
    account_id: int = 1,
    db_path: str = _DB_PATH,
) -> None:
    """Create or update a stock in the watchlist.

    Args:
        ts_code: Turtle stock code (e.g. "00506.HK")
        name: Display name
        market: Market flag ("H", "A", or auto-detected from ts_code)
        invest_code: Android invest code (e.g. "hk00506"). Auto-derived if empty.
        invest_status: One of WATCHING, HOLDING, CLEARED
        ... (other fields map directly to watchlist columns)
    """
    if not ts_code or "." not in ts_code:
        raise StockError(f"ts_code must be a valid Turtle code (e.g. '00506.HK'), got '{ts_code}'")

    # Auto-derive market if not provided
    if not market:
        if ".HK" in ts_code:
            market = "H"
        elif ".SH" in ts_code or ".SZ" in ts_code:
            market = "A"

    # Auto-derive invest_code
    if not invest_code:
        invest_code = ts_code
        if ".HK" in invest_code:
            invest_code = "hk" + invest_code.replace(".HK", "")
        elif ".SZ" in invest_code:
            invest_code = "sz" + invest_code.replace(".SZ", "")
        elif ".SH" in invest_code:
            invest_code = "sh" + invest_code.replace(".SH", "")

    db = get_db(db_path)
    try:
        db.execute(
            """INSERT OR REPLACE INTO watchlist (
                ts_code, invest_code, name, market, in_invest, invest_status,
                current_hold, avg_cost, hold_limit_pct, annual_div_per_share,
                invest_logic, my_valuation, turtle_valuation, live_price,
                sector, stock_type, pe, pb, debt_ratio, fcf_yield,
                mth_enabled, mth_cycle, lock_reserve, cumulative_div,
                dividend_tax_rate, account_id, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                ts_code, invest_code, name, market, invest_status,
                current_hold, avg_cost, hold_limit_pct, annual_div_per_share,
                invest_logic[:500] if invest_logic else "", my_valuation, turtle_valuation, live_price,
                sector, stock_type, pe, pb, debt_ratio, fcf_yield,
                1 if mth_enabled else 0, mth_cycle, 1 if lock_reserve else 0, cumulative_div,
                dividend_tax_rate, account_id,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_stock(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> StockSnapshot | None:
    """Get a single stock by ts_code."""
    db = get_db(db_path)
    try:
        row = db.execute("SELECT * FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone()
        if row is None:
            return None
        r = dict(row)
        return StockSnapshot(
            ts_code=r["ts_code"],
            invest_code=r.get("invest_code"),
            name=r.get("name") or "",
            market=r.get("market") or "",
            current_hold=r.get("current_hold") or 0,
            avg_cost=r.get("avg_cost"),
            live_price=r.get("live_price"),
            invest_status=r.get("invest_status") or "WATCHING",
            cumulative_div=r.get("cumulative_div") or 0.0,
            invest_logic=r.get("invest_logic"),
            my_valuation=r.get("my_valuation"),
            turtle_valuation=r.get("turtle_valuation"),
            sector=r.get("sector"),
            stock_type=r.get("stock_type"),
            hold_limit_pct=r.get("hold_limit_pct"),
            mth_enabled=bool(r.get("mth_enabled")),
            account_id=r.get("account_id") or 1,
        )
    finally:
        db.close()


def find_by_invest_code(invest_code: str, db_path: str = _DB_PATH) -> StockSnapshot | None:
    """Find a stock by Android invest code (e.g. 'hk00506')."""
    ts_code = _normalize_invest_code(invest_code)
    return get_stock(ts_code, db_path)


def update_status(
    ts_code: str,
    invest_status: str,
    db_path: str = _DB_PATH,
) -> None:
    """Update a stock's invest status (WATCHING → HOLDING → CLEARED)."""
    db = get_db(db_path)
    try:
        db.execute(
            "UPDATE watchlist SET invest_status = ?, updated_at = datetime('now') WHERE ts_code = ?",
            (invest_status, ts_code),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_live_price(
    ts_code: str,
    live_price: float,
    db_path: str = _DB_PATH,
) -> None:
    """Update the live (streaming) price for a stock."""
    db = get_db(db_path)
    try:
        db.execute(
            "UPDATE watchlist SET live_price = ?, updated_at = datetime('now') WHERE ts_code = ?",
            (live_price, ts_code),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def batch_update_prices(
    prices: dict[str, float],
    db_path: str = _DB_PATH,
) -> int:
    """Update live prices for multiple stocks at once. Returns count updated."""
    db = get_db(db_path)
    count = 0
    try:
        for ts_code, price in prices.items():
            cur = db.execute(
                "UPDATE watchlist SET live_price = ?, updated_at = datetime('now') WHERE ts_code = ?",
                (price, ts_code),
            )
            count += cur.rowcount
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return count


def update_valuation(
    ts_code: str,
    my_valuation: float | None = None,
    turtle_valuation: float | None = None,
    invest_logic: str | None = None,
    db_path: str = _DB_PATH,
) -> None:
    """Update manual or Turtle valuation for a stock."""
    db = get_db(db_path)
    try:
        sets: list[str] = []
        params: list[Any] = []
        if my_valuation is not None:
            sets.append("my_valuation = ?")
            params.append(my_valuation)
        if turtle_valuation is not None:
            sets.append("turtle_valuation = ?")
            params.append(turtle_valuation)
        if invest_logic is not None:
            sets.append("invest_logic = ?")
            params.append(invest_logic[:500])
        if not sets:
            return
        sets.append("updated_at = datetime('now')")
        params.append(ts_code)
        db.execute(f"UPDATE watchlist SET {', '.join(sets)} WHERE ts_code = ?", tuple(params))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_watchlist(
    *,
    holding_only: bool = False,
    watching_only: bool = False,
    account_id: int | None = None,
    db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """List all stocks in the watchlist, with optional filters."""
    db = get_db(db_path)
    try:
        where: list[str] = []
        params: list[Any] = []
        if holding_only:
            where.append("COALESCE(current_hold, 0) > 0")
        if watching_only:
            where.append("COALESCE(current_hold, 0) = 0 AND invest_status = 'WATCHING'")
        if account_id is not None:
            where.append("account_id = ?")
            params.append(account_id)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = db.execute(
            f"SELECT * FROM watchlist {clause} ORDER BY COALESCE(current_hold, 0) DESC, name",
            tuple(params),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def remove_from_watchlist(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> bool:
    """Remove a stock from the watchlist. Returns True if deleted."""
    db = get_db(db_path)
    try:
        cur = db.execute("DELETE FROM watchlist WHERE ts_code = ?", (ts_code,))
        deleted = cur.rowcount > 0
        db.commit()
        return deleted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_holding_summary(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Return a summary of current holdings."""
    db = get_db(db_path)
    try:
        total = db.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        holding = db.execute(
            "SELECT COUNT(*) FROM watchlist WHERE COALESCE(current_hold, 0) > 0"
        ).fetchone()[0]
        watching = db.execute(
            "SELECT COUNT(*) FROM watchlist WHERE COALESCE(current_hold, 0) = 0 AND invest_status = 'WATCHING'"
        ).fetchone()[0]
        cleared = db.execute(
            "SELECT COUNT(*) FROM watchlist WHERE invest_status = 'CLEARED'"
        ).fetchone()[0]
        total_value = db.execute(
            "SELECT COALESCE(SUM(COALESCE(current_hold,0) * COALESCE(live_price,0)), 0) FROM watchlist"
        ).fetchone()[0]
        return {
            "total": total,
            "holding": holding,
            "watching": watching,
            "cleared": cleared,
            "total_market_value_cny": total_value,
        }
    finally:
        db.close()
