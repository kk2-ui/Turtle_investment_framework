"""Staged buy strategy — 分档建仓计划。

Port of Android StagedBuyPlanCalculator + StagedBuyDetailViewModel.
Generates N price levels from base_price downward, tracks completion.
"""

from __future__ import annotations

import json
from typing import Any

from niangao.db import get_db, _DB_PATH


def generate_plan(
    *,
    ts_code: str,
    base_price: float,
    level_count: int = 6,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Generate a staged buy plan with N levels from base_price downward.

    Levels are spaced evenly: each step = base_price * 0.30 / level_count.
    Level 0 = base_price, level N-1 = base_price * 0.70.
    """
    if base_price <= 0:
        raise ValueError("base_price must be > 0")
    if level_count < 3 or level_count > 10:
        raise ValueError("level_count must be 3-10")

    step = base_price * 0.30 / max(level_count - 1, 1)
    levels = []
    for i in range(level_count):
        price = round(base_price - step * i, 2)
        levels.append({
            "level": i + 1,
            "price": max(price, 0.01),
            "completed": False,
            "skipped": False,
            "filled_shares": 0,
            "note": "",
        })

    levels_json = json.dumps(levels, ensure_ascii=False)
    db = get_db(db_path)
    try:
        db.execute(
            """INSERT OR REPLACE INTO staged_buy_plan (ts_code, base_price, level_count, levels_json)
               VALUES (?, ?, ?, ?)""",
            (ts_code, base_price, level_count, levels_json),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "ts_code": ts_code,
        "base_price": base_price,
        "level_count": level_count,
        "levels": levels,
    }


def get_plan(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> dict[str, Any] | None:
    """Get staged buy plan for a stock."""
    db = get_db(db_path)
    try:
        row = db.execute(
            "SELECT * FROM staged_buy_plan WHERE ts_code = ?", (ts_code,),
        ).fetchone()
        if row is None:
            return None
        r = dict(row)
        r["levels"] = json.loads(r["levels_json"])
        # Count progress
        completed = sum(1 for l in r["levels"] if l.get("completed"))
        skipped = sum(1 for l in r["levels"] if l.get("skipped"))
        r["progress"] = {
            "completed": completed,
            "skipped": skipped,
            "remaining": r["level_count"] - completed - skipped,
            "pct": round(100 * completed / r["level_count"], 1),
        }
        return r
    finally:
        db.close()


def mark_level(
    *,
    ts_code: str,
    level_index: int,
    completed: bool = False,
    skipped: bool = False,
    filled_shares: int = 0,
    note: str = "",
    db_path: str = _DB_PATH,
) -> dict[str, Any] | None:
    """Mark a staged buy level as completed or skipped.

    level_index is 0-based (level 1 = index 0).
    """
    plan = get_plan(ts_code, db_path)
    if plan is None:
        raise ValueError(f"No staged buy plan for {ts_code}")
    if level_index < 0 or level_index >= len(plan["levels"]):
        raise ValueError(f"Level index {level_index} out of range (0-{len(plan['levels']) - 1})")

    plan["levels"][level_index]["completed"] = completed
    plan["levels"][level_index]["skipped"] = skipped
    if filled_shares:
        plan["levels"][level_index]["filled_shares"] = filled_shares
    if note:
        plan["levels"][level_index]["note"] = note

    levels_json = json.dumps(plan["levels"], ensure_ascii=False)
    db = get_db(db_path)
    try:
        db.execute(
            "UPDATE staged_buy_plan SET levels_json = ?, updated_at = datetime('now') WHERE ts_code = ?",
            (levels_json, ts_code),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return get_plan(ts_code, db_path)


def delete_plan(
    ts_code: str,
    db_path: str = _DB_PATH,
) -> bool:
    """Delete a staged buy plan."""
    db = get_db(db_path)
    try:
        cur = db.execute("DELETE FROM staged_buy_plan WHERE ts_code = ?", (ts_code,))
        deleted = cur.rowcount > 0
        db.commit()
        return deleted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_active_plans(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """List all stocks with staged buy plans that still have remaining levels."""
    db = get_db(db_path)
    try:
        rows = db.execute("SELECT * FROM staged_buy_plan ORDER BY ts_code").fetchall()
        result = []
        for row in rows:
            r = dict(row)
            r["levels"] = json.loads(r["levels_json"])
            completed = sum(1 for l in r["levels"] if l.get("completed"))
            remaining = r["level_count"] - completed
            if remaining > 0:
                r["progress_pct"] = round(100 * completed / r["level_count"], 1)
                result.append(r)
        return result
    finally:
        db.close()
