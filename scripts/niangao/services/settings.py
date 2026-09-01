"""Settings service — key-value configuration management.

Stores settings as key-value pairs in the settings table.
Default settings are defined here and auto-seeded on first access.
"""

from __future__ import annotations

import json
from typing import Any

from niangao.db import get_db, _DB_PATH

# Default settings (seeded on first get if table is empty)
DEFAULTS = {
    "portfolio_cap_pct": "1.20",
    "commission_rate": "0.002",
    "staged_level_count": "6",
    "mth_level_count": "8",
    "bear_market_enabled": "false",
    "bear_market_discount_pct": "0.05",
    "exchange_rate_hkd": "0.93",
    "exchange_rate_usd": "7.20",
    "exchange_rate_eur": "7.80",
}


def _seed_defaults(db) -> None:
    """Insert default settings if the table is empty."""
    count = db.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    if count == 0:
        for k, v in DEFAULTS.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        db.commit()


def get_all(db_path: str = _DB_PATH) -> dict[str, str]:
    """Get all settings as a dict."""
    db = get_db(db_path)
    try:
        _seed_defaults(db)
        rows = db.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        db.close()


def get(key: str, default: str = "", db_path: str = _DB_PATH) -> str:
    """Get a single setting value."""
    db = get_db(db_path)
    try:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        db.close()


def set_(key: str, value: str, db_path: str = _DB_PATH) -> None:
    """Set a single setting value."""
    db = get_db(db_path)
    try:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, value),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_batch(updates: dict[str, str], db_path: str = _DB_PATH) -> None:
    """Update multiple settings at once."""
    db = get_db(db_path)
    try:
        for k, v in updates.items():
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                (k, str(v)),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_typed(key: str, db_path: str = _DB_PATH) -> float | bool | str:
    """Get a setting auto-converted to float/bool/str."""
    raw = get(key, "", db_path)
    if raw == "":
        return DEFAULTS.get(key, "")
    # Try float first
    try:
        return float(raw)
    except ValueError:
        pass
    # Try bool
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw
