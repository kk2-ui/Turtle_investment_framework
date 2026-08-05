"""Grid trading strategy — cycle record management for 网格交易.

Port of Android GridCycleRecordDao + TradeLedgerService grid methods.
Tracks sell→buy cycles with profit calculation.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from niangao.db import get_db, _DB_PATH


@dataclass
class GridCycleResult:
    cycle_id: int
    stock_code: str
    sell_price: float
    sell_shares: int
    sell_proceeds_cny: float
    planned_buy_price: float | None
    is_open: bool  # waiting for buy-back


@dataclass
class GridBuyResult:
    cycle_id: int
    stock_code: str
    buy_price: float
    buy_shares: int
    profit: float
    is_success: bool


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── Cycle CRUD ────────────────────────────────────────────────────────

def record_grid_sell(
    *,
    stock_code: str,
    sell_price: float,
    sell_shares: int,
    sell_proceeds_cny: float,
    planned_buy_price: float | None = None,
    db_path: str = _DB_PATH,
    db: sqlite3.Connection | None = None,
) -> GridCycleResult:
    """Record a grid sell, creating an open cycle waiting for buy-back.

    Call AFTER record_sell() in trade_ledger.
    """
    if sell_price <= 0 or sell_shares <= 0 or sell_proceeds_cny <= 0:
        raise ValueError("sell_price, sell_shares, sell_proceeds_cny must be > 0")

    own_db = db is None
    db = db or get_db(db_path)
    try:
        now = _now_ms()
        cur = db.execute(
            """INSERT INTO grid_cycle_record
               (stock_code, sell_price, sell_shares, sell_proceeds_cny, planned_buy_price, completed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (stock_code, sell_price, sell_shares, sell_proceeds_cny, planned_buy_price, now),
        )
        if own_db:
            db.commit()
        return GridCycleResult(
            cycle_id=cur.lastrowid,
            stock_code=stock_code,
            sell_price=sell_price,
            sell_shares=sell_shares,
            sell_proceeds_cny=sell_proceeds_cny,
            planned_buy_price=planned_buy_price,
            is_open=True,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        if own_db:
            db.close()


def record_grid_buy(
    *,
    cycle_id: int,
    buy_price: float,
    buy_shares: int,
    db_path: str = _DB_PATH,
    db: sqlite3.Connection | None = None,
) -> GridBuyResult:
    """Record a grid buy-back, completing an open cycle.

    Computes profit = sell_proceeds * (buy_shares / sell_shares) - buy_price * buy_shares.
    Call AFTER record_buy() in trade_ledger.
    """
    if buy_price <= 0 or buy_shares <= 0:
        raise ValueError("buy_price and buy_shares must be > 0")

    own_db = db is None
    db = db or get_db(db_path)
    try:
        cycle = db.execute(
            "SELECT * FROM grid_cycle_record WHERE id = ?", (cycle_id,),
        ).fetchone()
        if cycle is None:
            raise ValueError(f"Grid cycle {cycle_id} not found")
        cycle = dict(cycle)
        if cycle["buy_price"] is not None:
            raise ValueError(f"Grid cycle {cycle_id} already closed")

        # Profit proportional to shares bought back
        if cycle["sell_shares"] > 0:
            profit = (cycle["sell_proceeds_cny"] * buy_shares / cycle["sell_shares"]) - (buy_price * buy_shares)
        else:
            profit = 0.0

        now = _now_ms()
        db.execute(
            """UPDATE grid_cycle_record
               SET buy_price = ?, buy_shares = ?, profit = ?, is_success = ?, completed_at = ?
               WHERE id = ?""",
            (buy_price, buy_shares, profit, 1 if profit > 0 else 0, now, cycle_id),
        )

        # Note: grid profit stays in grid_cycle_record.profit only.
        # Do NOT write to watchlist.cumulative_div — that field is per-share dividend,
        # and mixing grid profit into it corrupts effective_cost and P&L calculations.

        if own_db:
            db.commit()
        return GridBuyResult(
            cycle_id=cycle_id,
            stock_code=cycle["stock_code"],
            buy_price=buy_price,
            buy_shares=buy_shares,
            profit=profit,
            is_success=profit > 0,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        if own_db:
            db.close()


def list_open_cycles(
    stock_code: str | None = None,
    db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """List open (unfilled) grid cycles, optionally filtered by stock."""
    db = get_db(db_path)
    try:
        if stock_code:
            rows = db.execute(
                "SELECT * FROM grid_cycle_record WHERE stock_code = ? AND buy_price IS NULL ORDER BY completed_at DESC",
                (stock_code,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM grid_cycle_record WHERE buy_price IS NULL ORDER BY completed_at DESC",
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def list_cycles(
    stock_code: str | None = None,
    limit: int = 50,
    db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """List all grid cycles, newest first."""
    db = get_db(db_path)
    try:
        if stock_code:
            rows = db.execute(
                "SELECT * FROM grid_cycle_record WHERE stock_code = ? ORDER BY completed_at DESC LIMIT ?",
                (stock_code, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM grid_cycle_record ORDER BY completed_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_cycle(cycle_id: int, db_path: str = _DB_PATH) -> dict[str, Any] | None:
    """Get a single cycle by ID."""
    db = get_db(db_path)
    try:
        row = db.execute("SELECT * FROM grid_cycle_record WHERE id = ?", (cycle_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def delete_cycle(cycle_id: int, db_path: str = _DB_PATH) -> bool:
    """Delete a cycle record. Only allowed for open cycles."""
    db = get_db(db_path)
    try:
        cycle = db.execute("SELECT * FROM grid_cycle_record WHERE id = ?", (cycle_id,)).fetchone()
        if cycle is None:
            return False
        cycle = dict(cycle)
        if cycle["buy_price"] is not None:
            raise ValueError(f"Cannot delete closed cycle {cycle_id}")
        db.execute("DELETE FROM grid_cycle_record WHERE id = ?", (cycle_id,))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Grid stats ────────────────────────────────────────────────────────

def grid_summary(
    stock_code: str | None = None,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Grid trading summary: open cycles, total profit, success rate."""
    db = get_db(db_path)
    try:
        where = "WHERE stock_code = ?" if stock_code else ""
        params = (stock_code,) if stock_code else ()

        total = db.execute(
            f"SELECT COUNT(*) FROM grid_cycle_record {where}", params,
        ).fetchone()[0]
        open_count = db.execute(
            f"SELECT COUNT(*) FROM grid_cycle_record {where} {'AND' if stock_code else 'WHERE'} buy_price IS NULL",
            params,
        ).fetchone()[0]
        closed_count = total - open_count
        total_profit = db.execute(
            f"SELECT COALESCE(SUM(profit), 0) FROM grid_cycle_record {where} {'AND' if stock_code else 'WHERE'} buy_price IS NOT NULL",
            params,
        ).fetchone()[0]
        success_count = db.execute(
            f"SELECT COUNT(*) FROM grid_cycle_record {where} {'AND' if stock_code else 'WHERE'} is_success = 1",
            params,
        ).fetchone()[0]

        return {
            "total_cycles": total,
            "open_cycles": open_count,
            "closed_cycles": closed_count,
            "total_profit_cny": total_profit,
            "success_count": success_count,
            "success_rate": success_count / closed_count if closed_count > 0 else 0,
        }
    finally:
        db.close()


# ── Grid strategy config ──────────────────────────────────────────────

def get_grid_config(ts_code: str, db_path: str = _DB_PATH) -> dict[str, Any]:
    """Get grid strategy configuration for a stock."""
    db = get_db(db_path)
    try:
        row = db.execute("SELECT * FROM grid_strategy WHERE ts_code = ?", (ts_code,)).fetchone()
        if row:
            return dict(row)
        # Return defaults
        return {"ts_code": ts_code, "enabled": 1, "step_mode": "FIXED", "grid_step": 0.05,
                "trade_percent": 0.10, "trade_mode": "FIXED"}
    finally:
        db.close()


def save_grid_config(ts_code: str, db_path: str = _DB_PATH, **kwargs) -> None:
    """Update grid strategy config. Auto-creates row if missing."""
    db = get_db(db_path)
    try:
        existing = db.execute("SELECT ts_code FROM grid_strategy WHERE ts_code = ?", (ts_code,)).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            db.execute(f"UPDATE grid_strategy SET {sets}, updated_at = datetime('now') WHERE ts_code = ?",
                       tuple(kwargs.values()) + (ts_code,))
        else:
            fields = ["ts_code"] + list(kwargs.keys())
            db.execute(f"INSERT INTO grid_strategy ({', '.join(fields)}) VALUES ({', '.join('?'*len(fields))})",
                       [ts_code] + list(kwargs.values()))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def is_grid_eligible(ts_code: str, db_path: str = _DB_PATH) -> dict[str, Any]:
    """Check if a stock is eligible for grid trading (profit rate >= 30%)."""
    db = get_db(db_path)
    try:
        stock = dict(db.execute("SELECT * FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone())
        avg_cost = stock.get("avg_cost") or 0
        cumulative_div = stock.get("cumulative_div") or 0
        live_price = stock.get("live_price") or 0
        current_hold = stock.get("current_hold") or 0

        effective_cost = max(avg_cost - cumulative_div, 0.01)
        profit_rate = (live_price - effective_cost) / effective_cost if effective_cost > 0 else 0
        eligible = profit_rate >= 0.30 and current_hold > 0

        return {
            "ts_code": ts_code,
            "eligible": eligible,
            "profit_rate": round(profit_rate * 100, 2),
            "effective_cost": round(effective_cost, 2),
            "live_price": live_price,
            "current_hold": current_hold,
        }
    except Exception:
        return {"ts_code": ts_code, "eligible": False, "note": "Stock not found or error"}
    finally:
        db.close()


def calculate_grid_levels(ts_code: str, db_path: str = _DB_PATH) -> dict[str, Any]:
    """Generate grid sell/buy levels for a stock."""
    db = get_db(db_path)
    try:
        stock = dict(db.execute("SELECT * FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone())
        cfg = get_grid_config(ts_code, db_path)
        my_valuation = stock.get("my_valuation") or stock.get("turtle_valuation") or 0
        live_price = stock.get("live_price") or 0
        current_hold = stock.get("current_hold") or 0

        if my_valuation <= 0 or live_price <= 0 or current_hold <= 0:
            return {"ts_code": ts_code, "levels": [], "note": "Missing valuation/price/holdings"}

        step = cfg.get("grid_step", 0.05)
        upper = my_valuation
        lower = my_valuation * 0.60
        anchor = live_price

        sell_levels = []
        price = anchor * (1 + step)
        while price < upper * 1.1:
            sell_levels.append({"price": round(price, 2), "type": "GRID_SELL", "shares": int(current_hold * cfg.get("trade_percent", 0.10))})
            price *= (1 + step)

        buy_levels = []
        price = anchor * (1 - step)
        while price > lower:
            buy_levels.append({"price": round(price, 2), "type": "GRID_BUY", "shares": int(current_hold * cfg.get("trade_percent", 0.10))})
            price *= (1 - step)

        return {
            "ts_code": ts_code,
            "anchor": round(anchor, 2),
            "upper": round(upper, 2),
            "lower": round(lower, 2),
            "step_pct": round(step * 100, 2),
            "sell_levels": sell_levels,
            "buy_levels": buy_levels,
            "config": cfg,
        }
    except Exception as e:
        return {"ts_code": ts_code, "levels": [], "error": str(e)}
    finally:
        db.close()
