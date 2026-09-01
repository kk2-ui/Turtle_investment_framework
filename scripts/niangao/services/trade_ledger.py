"""Trade ledger service — BUY/SELL/DIVIDEND mutations against portfolio.db.

Port of Android TradeLedgerService.kt + PositionProjectionService.kt semantics.
All mutations run in a single SQLite transaction and are atomic.

Write endpoints MUST NOT expose these functions until audit/backup hooks and
reconcile checks are in place (Phase 4+).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from niangao.db import get_db, _DB_PATH


# ── Projection model (mirrors Android PositionProjection) ────────────

@dataclass
class PositionProjection:
    current_hold: int = 0
    avg_cost: float = 0.0
    cumulative_div_per_share: float = 0.0
    status: str = "WATCHING"  # WATCHING | HOLDING | CLEARED
    cash_delta_cny: float = 0.0


@dataclass
class LedgerResult:
    ts_code: str
    transaction_id: int
    previous_status: str
    resulting_status: str
    new_hold: int
    new_avg_cost: float
    new_cumulative_div_per_share: float = 0.0
    warnings: list[str] = field(default_factory=list)


class TradeLedgerError(RuntimeError):
    """Raised when a ledger operation cannot complete (validation, missing stock, etc)."""


# ── Position projection math (1:1 port of PositionProjectionService) ─

def _apply_buy_delta(
    current: PositionProjection,
    price: float,
    shares: int,
    amount_cny: float,
    commission_cny: float = 0.0,
) -> PositionProjection:
    if shares <= 0 or price <= 0:
        return current
    new_hold = current.current_hold + shares
    # Effective price grosses up for commission (so avgCost reflects total cost)
    gross_amount = amount_cny - commission_cny
    effective_price = price * (amount_cny / gross_amount) if gross_amount > 0 else price
    if current.current_hold == 0:
        new_avg_cost = effective_price
    else:
        new_avg_cost = (current.avg_cost * current.current_hold + effective_price * shares) / new_hold
    # Dilute cumulative dividend across the larger holding
    diluted_div = 0.0
    if current.current_hold > 0 and current.cumulative_div_per_share > 0:
        diluted_div = current.cumulative_div_per_share * current.current_hold / new_hold
    return PositionProjection(
        current_hold=new_hold,
        avg_cost=new_avg_cost,
        cumulative_div_per_share=diluted_div,
        status="HOLDING",
        cash_delta_cny=-amount_cny,
    )


def _apply_sell_delta(
    current: PositionProjection,
    price: float,
    shares: int,
    amount_cny: float,
    commission_cny: float = 0.0,
) -> PositionProjection:
    if shares <= 0 or price <= 0:
        return current
    effective_shares = min(shares, current.current_hold)
    if effective_shares <= 0:
        return current
    new_hold = max(current.current_hold - effective_shares, 0)
    # avgCost preserved through sell (Android behaviour)
    new_avg_cost = current.avg_cost
    if new_hold == 0:
        new_cumulative_div = 0.0
    else:
        effective_cost_before_sell = max(current.avg_cost - current.cumulative_div_per_share, 0.01)
        realized_pnl = (price - effective_cost_before_sell) * effective_shares
        new_cumulative_div = current.cumulative_div_per_share + realized_pnl / new_hold
    return PositionProjection(
        current_hold=new_hold,
        avg_cost=new_avg_cost,
        cumulative_div_per_share=new_cumulative_div,
        status="CLEARED" if new_hold == 0 else "HOLDING",
        cash_delta_cny=amount_cny,
    )


# ── Internal helpers ──────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_stock(db, ts_code: str) -> dict | None:
    row = db.execute("SELECT * FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone()
    return dict(row) if row else None


def _read_projection(stock: dict | None) -> PositionProjection:
    if stock is None:
        return PositionProjection()
    return PositionProjection(
        current_hold=stock.get("current_hold") or 0,
        avg_cost=stock.get("avg_cost") or 0.0,
        cumulative_div_per_share=stock.get("cumulative_div") or 0.0,
        status=stock.get("invest_status") or "WATCHING",
    )


def _upsert_stock(db, ts_code: str, name: str, projection: PositionProjection, account_id: int) -> None:
    """Write projection back to watchlist. Upserts if the stock row doesn't exist yet."""
    existing = db.execute("SELECT ts_code FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone()
    status = projection.status
    if existing:
        db.execute(
            """UPDATE watchlist
               SET current_hold = ?, avg_cost = ?, cumulative_div = ?, invest_status = ?,
                   account_id = COALESCE(account_id, ?), updated_at = datetime('now')
               WHERE ts_code = ?""",
            (projection.current_hold, projection.avg_cost, projection.cumulative_div_per_share,
             status, account_id, ts_code),
        )
    else:
        db.execute(
            """INSERT INTO watchlist (ts_code, name, current_hold, avg_cost, cumulative_div,
               invest_status, account_id, in_invest, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))""",
            (ts_code, name, projection.current_hold, projection.avg_cost,
             projection.cumulative_div_per_share, status, account_id),
        )


def _insert_trade(
    db, ts_code: str, name: str, trade_type: str, price: float, shares: int,
    amount_cny: float, commission_cny: float, note: str | None, dividend_year: int | None = None,
    settlement_ref: str | None = None,
) -> int:
    now = _now_ms()
    cur = db.execute(
        """INSERT INTO trade_record (stock_code, stock_name, trade_type, price, shares, amount,
           trade_at, dividend_year, commission, settlement_ref)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts_code, name, trade_type, price, shares, amount_cny, now, dividend_year, commission_cny,
         settlement_ref),
    )
    return cur.lastrowid


def _update_cash(db, currency: str, account_id: int, delta_cny: float) -> None:
    now = _now_ms()
    existing = db.execute(
        "SELECT amount FROM cash WHERE currency = ? AND account_id = ?",
        (currency, account_id),
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE cash SET amount = amount + ?, last_updated = ? WHERE currency = ? AND account_id = ?",
            (delta_cny, now, currency, account_id),
        )
    else:
        db.execute(
            "INSERT INTO cash (currency, account_id, amount, last_updated) VALUES (?, ?, ?, ?)",
            (currency, account_id, delta_cny, now),
        )


def _insert_cash_flow(
    db, account_id: int, currency: str, delta_amount: float, delta_cny: float, note: str,
) -> None:
    now = _now_ms()
    db.execute(
        """INSERT INTO cash_flow (account_id, currency, delta_amount, delta_cny, note, flow_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (account_id, currency, delta_amount, delta_cny, note, now),
    )


def _refresh_position_pnl(db) -> None:
    """Recompute position_pnl for all current holdings after a trade."""
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


def _refresh_realized_pnl_for_stock(db, ts_code: str) -> None:
    """Recompute realized_pnl for a single stock after a full clear-out."""
    # Check if the stock is fully cleared (no current hold)
    hold = db.execute(
        "SELECT COALESCE(current_hold, 0) FROM watchlist WHERE ts_code = ?", (ts_code,)
    ).fetchone()
    if hold and hold[0] > 0:
        return  # Still holding, nothing to realize

    total_buy = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM trade_record WHERE stock_code = ? AND trade_type = 'BUY'",
        (ts_code,),
    ).fetchone()[0]
    total_sell = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM trade_record WHERE stock_code = ? AND trade_type = 'SELL'",
        (ts_code,),
    ).fetchone()[0]
    stock_name = db.execute(
        "SELECT name FROM watchlist WHERE ts_code = ?", (ts_code,)
    ).fetchone()
    name = stock_name[0] if stock_name else ts_code
    realized = total_sell - total_buy
    db.execute(
        """INSERT OR REPLACE INTO realized_pnl (stock_code, stock_name, total_buy_amt,
           total_sell_amt, realized_pnl, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))""",
        (ts_code, name, total_buy, total_sell, realized),
    )


# ── Public API ───────────────────────────────────────────────────────

def record_buy(
    *,
    ts_code: str,
    name: str = "",
    price: float,
    shares: int,
    amount_cny: float,
    commission_cny: float = 0.0,
    note: str | None = None,
    account_id: int = 1,
    settlement_ref: str | None = None,
    db_path: str = _DB_PATH,
    db: sqlite3.Connection | None = None,
) -> LedgerResult:
    """Record a BUY transaction. Atomic: updates watchlist + trade_record + cash + cash_flow.

    Args:
        ts_code: Turtle stock code (e.g. "00506.HK")
        name: Stock display name (used if the stock isn't in watchlist yet)
        price: Per-share price (stock native currency)
        shares: Number of shares bought
        amount_cny: Total trade amount in CNY (incl. commission)
        commission_cny: Broker commission in CNY
        note: Optional note (stored in trade_record.note via cash_flow)
        account_id: Account ID (default 1 = personal)
        db_path: Override DB path (default portfolio.db)

    Raises:
        TradeLedgerError: If validation fails (price <= 0, shares <= 0, negative amount)

    Returns:
        LedgerResult with new position state and transaction ID.
    """
    if price <= 0:
        raise TradeLedgerError(f"BUY price must be > 0, got {price}")
    if shares <= 0:
        raise TradeLedgerError(f"BUY shares must be > 0, got {shares}")
    if amount_cny <= 0:
        raise TradeLedgerError(f"BUY amount_cny must be > 0, got {amount_cny}")

    own_db = db is None
    db = db or get_db(db_path)
    try:
        stock = _get_stock(db, ts_code)
        current = _read_projection(stock)
        stock_name = name or (stock.get("name") if stock else ts_code)
        prev_status = current.status

        projection = _apply_buy_delta(current, price, shares, amount_cny, commission_cny)
        _upsert_stock(db, ts_code, stock_name, projection, account_id)

        tx_id = _insert_trade(
            db, ts_code, stock_name, "BUY", price, shares, amount_cny, commission_cny, note,
            settlement_ref=settlement_ref,
        )
        _update_cash(db, "CNY", account_id, projection.cash_delta_cny)
        _insert_cash_flow(
            db, account_id, "CNY", projection.cash_delta_cny, projection.cash_delta_cny,
            note or f"买入 {ts_code} {shares}股@{price:.2f}",
        )

        _refresh_position_pnl(db)
        if own_db:
            db.commit()

        return LedgerResult(
            ts_code=ts_code,
            transaction_id=tx_id,
            previous_status=prev_status,
            resulting_status=projection.status,
            new_hold=projection.current_hold,
            new_avg_cost=projection.avg_cost,
            new_cumulative_div_per_share=projection.cumulative_div_per_share,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        if own_db:
            db.close()


def record_sell(
    *,
    ts_code: str,
    name: str = "",
    price: float,
    shares: int,
    amount_cny: float,
    commission_cny: float = 0.0,
    note: str | None = None,
    account_id: int = 1,
    db_path: str = _DB_PATH,
    db: sqlite3.Connection | None = None,
) -> LedgerResult:
    """Record a SELL transaction. Atomic.

    Args:
        ts_code: Turtle stock code
        name: Stock display name
        price: Per-share sell price
        shares: Number of shares sold
        amount_cny: Total proceeds in CNY (after commission)
        commission_cny: Broker commission in CNY
        note: Optional note
        account_id: Account ID
        db_path: Override DB path

    Raises:
        TradeLedgerError: If validation fails or stock not found / zero holding.

    Returns:
        LedgerResult. If fully cleared, realized_pnl is also refreshed.
    """
    if price <= 0:
        raise TradeLedgerError(f"SELL price must be > 0, got {price}")
    if shares <= 0:
        raise TradeLedgerError(f"SELL shares must be > 0, got {shares}")
    if amount_cny <= 0:
        raise TradeLedgerError(f"SELL amount_cny must be > 0, got {amount_cny}")

    own_db = db is None
    db = db or get_db(db_path)
    try:
        stock = _get_stock(db, ts_code)
        if stock is None:
            raise TradeLedgerError(f"Cannot sell {ts_code}: stock not in watchlist")
        current = _read_projection(stock)
        if current.current_hold <= 0:
            raise TradeLedgerError(f"Cannot sell {ts_code}: current_hold is 0")
        stock_name = name or stock.get("name") or ts_code
        prev_status = current.status
        warnings: list[str] = []
        if shares > current.current_hold:
            warnings.append(f"Sold {shares} but only held {current.current_hold}; capped")

        projection = _apply_sell_delta(current, price, shares, amount_cny, commission_cny)
        _upsert_stock(db, ts_code, stock_name, projection, account_id)

        tx_id = _insert_trade(
            db, ts_code, stock_name, "SELL", price, shares, amount_cny, commission_cny, note,
        )
        _update_cash(db, "CNY", account_id, projection.cash_delta_cny)
        flow_note = note or f"卖出 {ts_code} {shares}股@{price:.2f}"
        _insert_cash_flow(
            db, account_id, "CNY", projection.cash_delta_cny, projection.cash_delta_cny, flow_note,
        )

        if projection.current_hold == 0:
            _refresh_realized_pnl_for_stock(db, ts_code)

        _refresh_position_pnl(db)
        if own_db:
            db.commit()

        return LedgerResult(
            ts_code=ts_code,
            transaction_id=tx_id,
            previous_status=prev_status,
            resulting_status=projection.status,
            new_hold=projection.current_hold,
            new_avg_cost=projection.avg_cost,
            new_cumulative_div_per_share=projection.cumulative_div_per_share,
            warnings=warnings,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        if own_db:
            db.close()


def record_dividend(
    *,
    ts_code: str,
    amount_cny: float,
    div_per_share: float = 0.0,
    dividend_year: int | None = None,
    note: str | None = None,
    account_id: int = 1,
    stock_id: int | None = None,
    db_path: str = _DB_PATH,
) -> LedgerResult:
    """Record a DIVIDEND receipt. Atomic.

    Args:
        ts_code: Turtle stock code
        amount_cny: Total dividend amount in CNY
        div_per_share: Dividend per share (stock native currency, for cost-basis adjustment)
        dividend_year: Fiscal year the dividend belongs to (e.g. 2025)
        note: Optional note
        account_id: Account ID
        stock_id: Legacy parameter (ignored, use ts_code)
        db_path: Override DB path

    Raises:
        TradeLedgerError: If amount_cny <= 0 or stock not in watchlist.

    Returns:
        LedgerResult.
    """
    if amount_cny <= 0:
        raise TradeLedgerError(f"DIVIDEND amount_cny must be > 0, got {amount_cny}")

    db = get_db(db_path)
    try:
        stock = _get_stock(db, ts_code)
        if stock is None:
            raise TradeLedgerError(
                f"Cannot record dividend for {ts_code}: stock not in watchlist. "
                "Add the stock to watchlist first."
            )
        stock_name = stock.get("name") or ts_code
        current = _read_projection(stock)
        prev_status = current.status
        new_cumulative_div = current.cumulative_div_per_share

        if current.current_hold > 0 and div_per_share > 0:
            new_cumulative_div += div_per_share
            db.execute(
                "UPDATE watchlist SET cumulative_div = ? WHERE ts_code = ?",
                (new_cumulative_div, ts_code),
            )

        tx_id = _insert_trade(
            db, ts_code, stock_name, "DIVIDEND", 0.0, 0, amount_cny, 0.0, note,
            dividend_year=dividend_year,
        )
        _update_cash(db, "CNY", account_id, amount_cny)
        _insert_cash_flow(
            db, account_id, "CNY", amount_cny, amount_cny,
            note or f"股息 {ts_code} {dividend_year or ''}",
        )

        _refresh_position_pnl(db)
        db.commit()

        return LedgerResult(
            ts_code=ts_code,
            transaction_id=tx_id,
            previous_status=prev_status,
            resulting_status=current.status,  # dividend doesn't change status
            new_hold=current.current_hold,
            new_avg_cost=current.avg_cost,
            new_cumulative_div_per_share=new_cumulative_div,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Batch / auxiliary ────────────────────────────────────────────────

def get_trades_for_stock(
    ts_code: str, db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """Return all trade records for a stock, ordered by time (oldest first)."""
    db = get_db(db_path)
    try:
        rows = [
            dict(r) for r in db.execute(
                "SELECT * FROM trade_record WHERE stock_code = ? ORDER BY trade_at ASC, id ASC",
                (ts_code,),
            ).fetchall()
        ]
    finally:
        db.close()
    return rows


def project_from_trades(
    ts_code: str, db_path: str = _DB_PATH,
) -> PositionProjection:
    """Replay all trades for a stock from scratch to derive current position.

    This is the Python equivalent of Android
    PositionProjectionService.projectFromTransactions(). Used for
    verification/reconciliation.
    """
    trades = get_trades_for_stock(ts_code, db_path)
    projection = PositionProjection()
    for t in trades:
        ttype = t.get("trade_type", "")
        price = t.get("price") or 0.0
        shares = t.get("shares") or 0
        amount = t.get("amount") or 0.0
        commission = t.get("commission") or 0.0
        dps = t.get("div_per_share_adj") or 0.0  # may not exist in old records

        if ttype == "BUY":
            if shares > 0 and amount > 0:
                projection = _apply_buy_delta(projection, price, shares, amount, commission)
        elif ttype == "SELL":
            if shares > 0 and price > 0 and amount > 0:
                projection = _apply_sell_delta(projection, price, shares, amount, commission)
        elif ttype == "DIVIDEND":
            if projection.current_hold > 0 and dps > 0:
                projection.cumulative_div_per_share += dps

    # Final status resolution (same as Android)
    if not trades:
        projection.status = "WATCHING"
        projection.cumulative_div_per_share = 0.0
    elif projection.current_hold > 0:
        projection.status = "HOLDING"
    else:
        projection.status = "CLEARED"
        projection.cumulative_div_per_share = 0.0
    return projection
