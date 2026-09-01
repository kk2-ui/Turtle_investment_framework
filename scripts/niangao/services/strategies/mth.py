"""MTH (满堂红) strategy — cycle state management on watchlist.

Port of Android MTH logic. MTH tracks "full-house" achievement cycles:
when all staged buy levels are filled, it triggers a review/restart.

MTH state is stored directly on watchlist columns:
- mth_enabled: whether MTH is active for this stock
- mth_cycle: current cycle number
- mth_review_passed_at: last review confirmation timestamp
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from niangao.db import get_db, _DB_PATH


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── MTH state management ──────────────────────────────────────────────

def enable_mth(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Enable MTH for a stock."""
    db = get_db(db_path)
    try:
        db.execute(
            "UPDATE watchlist SET mth_enabled = 1, updated_at = datetime('now') WHERE ts_code = ?",
            (ts_code,),
        )
        db.commit()
        return {"ts_code": ts_code, "mth_enabled": True}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def disable_mth(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Disable MTH for a stock."""
    db = get_db(db_path)
    try:
        db.execute(
            "UPDATE watchlist SET mth_enabled = 0, updated_at = datetime('now') WHERE ts_code = ?",
            (ts_code,),
        )
        db.commit()
        return {"ts_code": ts_code, "mth_enabled": False}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def advance_mth_cycle(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Advance MTH to the next cycle (called after full-house achievement review)."""
    db = get_db(db_path)
    try:
        row = db.execute(
            "SELECT mth_cycle FROM watchlist WHERE ts_code = ?", (ts_code,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Stock {ts_code} not found")
        new_cycle = (row[0] or 0) + 1
        now = _now_ms()
        db.execute(
            """UPDATE watchlist
               SET mth_cycle = ?, mth_review_passed_at = ?, updated_at = datetime('now')
               WHERE ts_code = ?""",
            (new_cycle, now, ts_code),
        )
        db.commit()
        return {"ts_code": ts_code, "mth_cycle": new_cycle, "reviewed_at_ms": now}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset_mth_cycle(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Reset MTH to cycle 1 (full restart)."""
    db = get_db(db_path)
    try:
        db.execute(
            """UPDATE watchlist
               SET mth_cycle = 1, mth_review_passed_at = NULL, updated_at = datetime('now')
               WHERE ts_code = ?""",
            (ts_code,),
        )
        db.commit()
        return {"ts_code": ts_code, "mth_cycle": 1}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_mth_status(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> dict[str, Any] | None:
    """Get MTH status for a stock."""
    db = get_db(db_path)
    try:
        row = db.execute(
            "SELECT ts_code, name, mth_enabled, mth_cycle FROM watchlist WHERE ts_code = ?",
            (ts_code,),
        ).fetchone()
        if row is None:
            return None
        return {
            "ts_code": row["ts_code"],
            "name": row["name"],
            "mth_enabled": bool(row["mth_enabled"]),
            "mth_cycle": row["mth_cycle"] or 1,
        }
    finally:
        db.close()


def list_mth_stocks(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """List all stocks with MTH enabled."""
    db = get_db(db_path)
    try:
        rows = db.execute(
            """SELECT ts_code, name, mth_cycle, current_hold, live_price, avg_cost
               FROM watchlist WHERE mth_enabled = 1 ORDER BY name""",
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def generate_mth_plan(
    ts_code: str,
    level_count: int = 8,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Generate MTH fixed-cycle buy plan: N levels from anchor_price to -30%.

    Returns the plan levels and stores them for later reference.
    """
    db = get_db(db_path)
    try:
        stock = dict(db.execute("SELECT * FROM watchlist WHERE ts_code = ?", (ts_code,)).fetchone())
        my_valuation = stock.get("my_valuation") or stock.get("turtle_valuation") or 0
        live_price = stock.get("live_price") or 0

        if my_valuation <= 0:
            raise ValueError(f"No valuation for {ts_code}")

        anchor = max(my_valuation, live_price)
        step = anchor * 0.30 / max(level_count - 1, 1)
        levels = []
        for i in range(level_count):
            price = round(anchor - step * i, 2)
            levels.append({
                "level": i + 1,
                "price": max(price, 0.01),
                "triggered": live_price <= price,
                "settled": False,
                "shares": 0,
            })

        return {
            "ts_code": ts_code,
            "anchor_price": round(anchor, 2),
            "live_price": live_price,
            "level_count": level_count,
            "levels": levels,
            "triggered_count": sum(1 for l in levels if l["triggered"]),
        }
    except Exception as e:
        raise ValueError(f"MTH plan generation failed: {e}")
    finally:
        db.close()
