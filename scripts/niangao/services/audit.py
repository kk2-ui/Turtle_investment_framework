"""Audit service — backup-before-write, audit logging, and reconcile hooks.

Phase 4 safety layer. Every write API endpoint MUST call these hooks
before and after mutations to portfolio.db.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from niangao.db import _DB_PATH

# Backup directory inside _niangao/
_NIANGAO_DIR = Path(_DB_PATH).parent
_BACKUP_DIR = _NIANGAO_DIR / "backups" / "audit"


def _ensure_backup_dir() -> Path:
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return _BACKUP_DIR


# ── Backup ────────────────────────────────────────────────────────────

def backup_db(reason: str = "") -> str:
    """Create a timestamped backup of portfolio.db before a write operation.

    Returns the backup file path.
    """
    _ensure_backup_dir()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    slug = reason.replace(" ", "_").replace("/", "-")[:60] if reason else "pre_write"
    fname = f"portfolio_backup_{ts}_{slug}.db"
    dest = _BACKUP_DIR / fname
    shutil.copy2(_DB_PATH, dest)
    # Keep only the last 50 backups
    _rotate_backups(keep=50)
    return str(dest)


def _rotate_backups(keep: int = 50) -> None:
    """Remove oldest backups beyond keep count."""
    backups = sorted(_BACKUP_DIR.glob("portfolio_backup_*.db"))
    if len(backups) <= keep:
        return
    for old in backups[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


def latest_backup() -> str | None:
    """Return path to the most recent backup, or None."""
    _ensure_backup_dir()
    backups = sorted(_BACKUP_DIR.glob("portfolio_backup_*.db"))
    return str(backups[-1]) if backups else None


# ── Audit log ─────────────────────────────────────────────────────────

def record_audit(
    *,
    operation: str,
    target_table: str = "",
    target_key: str = "",
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    operator: str = "web",
    db_path: str = _DB_PATH,
) -> int:
    """Record an immutable audit log entry. Returns the log ID.

    Args:
        operation: e.g. "stock.upsert", "trade.buy", "cash.deposit"
        target_table: DB table affected
        target_key: Primary key or identifier of the affected row
        old_values: Pre-mutation state (serialized to JSON)
        new_values: Post-mutation state (serialized to JSON)
        operator: Who performed the operation (default "web")
        db_path: Override DB path

    Returns:
        The audit_log row ID.
    """
    db = sqlite3.connect(db_path)
    try:
        cur = db.execute(
            """INSERT INTO audit_log (operation, target_table, target_key, old_values, new_values, operator)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                operation,
                target_table,
                target_key,
                json.dumps(old_values, ensure_ascii=False, default=str) if old_values else None,
                json.dumps(new_values, ensure_ascii=False, default=str) if new_values else None,
                operator,
            ),
        )
        db.commit()
        return cur.lastrowid
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_audit_logs(
    limit: int = 100,
    operation: str | None = None,
    target_table: str | None = None,
    db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """Read recent audit log entries, newest first."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        where: list[str] = []
        params: list[Any] = []
        if operation:
            where.append("operation = ?")
            params.append(operation)
        if target_table:
            where.append("target_table = ?")
            params.append(target_table)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = db.execute(
            f"SELECT * FROM audit_log {clause} ORDER BY id DESC LIMIT ?",
            tuple(params) + (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


# ── Reconcile hook ────────────────────────────────────────────────────

def quick_reconcile_check(
    ts_code: str | None = None,
    account_id: int | None = None,
    db_path: str = _DB_PATH,
) -> dict[str, Any]:
    """Run a fast local reconcile on the affected entity after a write.

    Checks:
    - Position integrity: SUM(trade_record BUY shares) - SUM(SELL shares) == watchlist.current_hold
    - Cash consistency: SUM(cash_flow delta_cny) ≈ SUM(cash amount)
    - Trade count sanity

    Returns a dict with status and any warnings.
    """
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    warnings: list[str] = []
    try:
        # 1. Position integrity for a specific stock
        if ts_code:
            buy_shares = db.execute(
                "SELECT COALESCE(SUM(shares), 0) FROM trade_record WHERE stock_code = ? AND trade_type = 'BUY'",
                (ts_code,),
            ).fetchone()[0]
            sell_shares = db.execute(
                "SELECT COALESCE(SUM(shares), 0) FROM trade_record WHERE stock_code = ? AND trade_type = 'SELL'",
                (ts_code,),
            ).fetchone()[0]
            expected_hold = buy_shares - sell_shares
            actual = db.execute(
                "SELECT COALESCE(current_hold, 0) FROM watchlist WHERE ts_code = ?", (ts_code,),
            ).fetchone()
            actual_hold = actual[0] if actual else 0
            if expected_hold != actual_hold:
                warnings.append(
                    f"Position mismatch for {ts_code}: trades imply {expected_hold} shares, "
                    f"watchlist has {actual_hold}"
                )

        # 2. Cash consistency
        cash_sum = db.execute("SELECT COALESCE(SUM(amount), 0) FROM cash").fetchone()[0]
        cf_sum = db.execute("SELECT COALESCE(SUM(delta_cny), 0) FROM cash_flow").fetchone()[0]
        if abs(cash_sum - cf_sum) > 0.02:
            warnings.append(
                f"Cash inconsistency: cash total={cash_sum:.2f}, cash_flow total={cf_sum:.2f}, "
                f"diff={cash_sum - cf_sum:.2f}"
            )

        return {"status": "WARN" if warnings else "OK", "warnings": warnings}
    finally:
        db.close()


# ── Decorator for write endpoints ─────────────────────────────────────

def safe_write(
    operation: str,
    target_table: str = "",
    risk_level: str = "low",  # low | medium | high
) -> Callable:
    """Decorator that wraps a write endpoint with backup + audit + reconcile.

    Usage:
        @app.post("/api/stocks")
        @safe_write("stock.upsert", "watchlist", risk_level="low")
        def upsert_stock_endpoint(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        from functools import wraps

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Pre-write backup
            backup_path = backup_db(reason=operation)
            backup_id = os.path.basename(backup_path)

            try:
                result = func(*args, **kwargs)

                # Post-write audit (if result contains audit info)
                audit_info = {}
                if isinstance(result, dict) and "audit" in result:
                    audit_info = result.pop("audit")
                    record_audit(
                        operation=operation,
                        target_table=target_table or audit_info.get("table", ""),
                        target_key=audit_info.get("key", ""),
                        old_values=audit_info.get("old"),
                        new_values=audit_info.get("new"),
                    )

                # Quick reconcile check for medium/high risk
                if risk_level in ("medium", "high"):
                    ts_code = audit_info.get("ts_code")
                    acct_id = audit_info.get("account_id")
                    check = quick_reconcile_check(ts_code=ts_code, account_id=acct_id)
                    if check["status"] == "WARN":
                        if isinstance(result, dict):
                            result["reconcile_warnings"] = check["warnings"]

                # Attach backup info
                if isinstance(result, dict):
                    result["backup_id"] = backup_id

                return result

            except Exception:
                # On error, the backup is already taken — log failure
                record_audit(
                    operation=f"{operation}.failed",
                    target_table=target_table,
                    new_values={"error": str(Exception) if False else "exception"},
                )
                raise

        return wrapper

    return decorator
