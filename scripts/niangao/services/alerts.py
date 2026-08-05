"""Alert service — alert lifecycle management for the Niangao Web backend.

Port of Android AlertRepository + PriceAlertWorker semantics.
Alert types: BUY1, BUY2, SELL, ABOVE_VAL_SELL, GRID, MTH.

Currently operates on alert_snapshot + alert_settlement tables. Full lifecycle
(create/update/complete/notes) requires expanding alert_snapshot schema to match
Android AlertEntity — see RECONCILE_BASELINE for the known gaps.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from niangao.db import get_db, _DB_PATH

# Valid alert types (matching Android)
VALID_ALERT_TYPES = frozenset({"BUY1", "BUY2", "SELL", "ABOVE_VAL_SELL", "GRID", "MTH"})


class AlertError(RuntimeError):
    """Raised when an alert operation cannot complete."""


@dataclass
class AlertResult:
    alert_id: int
    stock_code: str
    alert_type: str
    target_price: float | None
    is_active: bool
    is_triggered: bool


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── Public API ───────────────────────────────────────────────────────

def create_alert(
    *,
    stock_code: str,
    alert_type: str,
    target_price: float | None = None,
    stock_name: str = "",
    db_path: str = _DB_PATH,
) -> AlertResult:
    """Create a new active alert.

    Args:
        stock_code: Stock code (ticker, not ts_code — e.g. "00506" not "00506.HK")
        alert_type: One of BUY1, BUY2, SELL, ABOVE_VAL_SELL, GRID, MTH
        target_price: Trigger price threshold
        stock_name: Display name
        db_path: Override DB path

    Raises:
        AlertError: If alert_type is invalid.
    """
    if alert_type not in VALID_ALERT_TYPES:
        raise AlertError(
            f"Invalid alert_type '{alert_type}'. Must be one of: "
            f"{', '.join(sorted(VALID_ALERT_TYPES))}"
        )

    db = get_db(db_path)
    try:
        cur = db.execute(
            """INSERT INTO alert_snapshot (stock_code, stock_name, alert_type, target_price,
               is_active, is_triggered, current_price)
               VALUES (?, ?, ?, ?, 1, 0, NULL)""",
            (stock_code, stock_name or "", alert_type, target_price),
        )
        alert_id = cur.lastrowid
        db.commit()
        return AlertResult(
            alert_id=alert_id,
            stock_code=stock_code,
            alert_type=alert_type,
            target_price=target_price,
            is_active=True,
            is_triggered=False,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def trigger_alert(
    alert_id: int,
    current_price: float,
    db_path: str = _DB_PATH,
) -> AlertResult:
    """Mark an alert as triggered by a current price crossing the threshold."""
    db = get_db(db_path)
    try:
        row = db.execute(
            "SELECT * FROM alert_snapshot WHERE id = ?", (alert_id,),
        ).fetchone()
        if row is None:
            raise AlertError(f"Alert {alert_id} not found")
        alert = dict(row)

        db.execute(
            """UPDATE alert_snapshot
               SET is_triggered = 1, current_price = ?, synced_at = datetime('now')
               WHERE id = ?""",
            (current_price, alert_id),
        )
        db.commit()
        return AlertResult(
            alert_id=alert_id,
            stock_code=alert["stock_code"],
            alert_type=alert["alert_type"],
            target_price=alert["target_price"],
            is_active=bool(alert["is_active"]),
            is_triggered=True,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def deactivate_alert(
    alert_id: int,
    db_path: str = _DB_PATH,
) -> AlertResult:
    """Deactivate (disable) an alert without deleting it."""
    db = get_db(db_path)
    try:
        row = db.execute(
            "SELECT * FROM alert_snapshot WHERE id = ?", (alert_id,),
        ).fetchone()
        if row is None:
            raise AlertError(f"Alert {alert_id} not found")
        alert = dict(row)

        db.execute(
            "UPDATE alert_snapshot SET is_active = 0, synced_at = datetime('now') WHERE id = ?",
            (alert_id,),
        )
        db.commit()
        return AlertResult(
            alert_id=alert_id,
            stock_code=alert["stock_code"],
            alert_type=alert["alert_type"],
            target_price=alert["target_price"],
            is_active=False,
            is_triggered=bool(alert["is_triggered"]),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reactivate_alert(
    alert_id: int,
    db_path: str = _DB_PATH,
) -> AlertResult:
    """Re-activate a previously deactivated alert."""
    db = get_db(db_path)
    try:
        row = db.execute(
            "SELECT * FROM alert_snapshot WHERE id = ?", (alert_id,),
        ).fetchone()
        if row is None:
            raise AlertError(f"Alert {alert_id} not found")
        alert = dict(row)

        db.execute(
            "UPDATE alert_snapshot SET is_active = 1, is_triggered = 0, synced_at = datetime('now') WHERE id = ?",
            (alert_id,),
        )
        db.commit()
        return AlertResult(
            alert_id=alert_id,
            stock_code=alert["stock_code"],
            alert_type=alert["alert_type"],
            target_price=alert["target_price"],
            is_active=True,
            is_triggered=False,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_alert(
    alert_id: int,
    db_path: str = _DB_PATH,
) -> None:
    """Permanently delete an alert."""
    db = get_db(db_path)
    try:
        db.execute("DELETE FROM alert_snapshot WHERE id = ?", (alert_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_alerts(
    *,
    active_only: bool = False,
    alert_type: str | None = None,
    db_path: str = _DB_PATH,
) -> list[dict[str, Any]]:
    """List alerts, optionally filtered."""
    db = get_db(db_path)
    try:
        where = []
        params: list[Any] = []
        if active_only:
            where.append("is_active = 1")
        if alert_type is not None:
            where.append("alert_type = ?")
            params.append(alert_type)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = db.execute(
            f"SELECT * FROM alert_snapshot {clause} ORDER BY alert_type, target_price DESC",
            tuple(params),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def evaluate_triggers(
    stock_code: str,
    current_price: float,
    db_path: str = _DB_PATH,
) -> list[AlertResult]:
    """Check all active alerts for a stock against a current price and trigger them.

    BUY1/BUY2: trigger when current_price <= target_price (price dropped to buy zone)
    SELL/ABOVE_VAL_SELL: trigger when current_price >= target_price (price rose to sell zone)

    Returns list of newly triggered alerts.
    """
    db = get_db(db_path)
    triggered: list[AlertResult] = []
    try:
        active = db.execute(
            "SELECT * FROM alert_snapshot WHERE stock_code = ? AND is_active = 1 AND is_triggered = 0",
            (stock_code,),
        ).fetchall()

        for row in active:
            alert = dict(row)
            target = alert.get("target_price")
            if target is None or target <= 0:
                continue
            atype = alert["alert_type"]
            should_trigger = False

            if atype in ("BUY1", "BUY2", "GRID"):
                should_trigger = current_price <= target
            elif atype in ("SELL", "ABOVE_VAL_SELL", "MTH"):
                should_trigger = current_price >= target

            if should_trigger:
                db.execute(
                    """UPDATE alert_snapshot
                       SET is_triggered = 1, current_price = ?, synced_at = datetime('now')
                       WHERE id = ?""",
                    (current_price, alert["id"]),
                )
                triggered.append(AlertResult(
                    alert_id=alert["id"],
                    stock_code=stock_code,
                    alert_type=atype,
                    target_price=target,
                    is_active=bool(alert["is_active"]),
                    is_triggered=True,
                ))

        if triggered:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return triggered


def evaluate_all_triggers(
    db_path: str = _DB_PATH,
) -> dict[str, list[AlertResult]]:
    """Evaluate triggers for ALL stocks with active alerts using current live_price.

    Returns {stock_code: [triggered_alerts]}.
    """
    db = get_db(db_path)
    all_triggered: dict[str, list[AlertResult]] = {}
    try:
        # Get distinct stock_codes with active alerts and their live prices
        rows = db.execute("""
            SELECT DISTINCT a.stock_code, w.live_price
            FROM alert_snapshot a
            LEFT JOIN watchlist w ON (
                -- Match invest_code (e.g. "hk00506") or ts_code (e.g. "00506.HK")
                w.invest_code = a.stock_code
                OR w.ts_code LIKE (a.stock_code || '.%')
                OR REPLACE(REPLACE(w.ts_code, '.HK', ''), '.SZ', '') = a.stock_code
            )
            WHERE a.is_active = 1 AND a.is_triggered = 0
        """).fetchall()
        # Build a lookup: stock_code -> live_price (take the first non-None)
        price_map: dict[str, float] = {}
        for row in rows:
            sc, lp = row["stock_code"], row["live_price"]
            if sc not in price_map and lp is not None and lp > 0:
                price_map[sc] = lp

        for stock_code, current_price in price_map.items():
            triggered = evaluate_triggers(stock_code, current_price, db_path)
            if triggered:
                all_triggered[stock_code] = triggered
    finally:
        db.close()
    return all_triggered


def get_alert_summary(db_path: str = _DB_PATH) -> dict[str, Any]:
    """Return a summary of alert state."""
    db = get_db(db_path)
    try:
        total = db.execute("SELECT COUNT(*) FROM alert_snapshot").fetchone()[0]
        active = db.execute(
            "SELECT COUNT(*) FROM alert_snapshot WHERE is_active = 1"
        ).fetchone()[0]
        triggered = db.execute(
            "SELECT COUNT(*) FROM alert_snapshot WHERE is_active = 1 AND is_triggered = 1"
        ).fetchone()[0]
        by_type_rows = db.execute(
            "SELECT alert_type, COUNT(*) as n FROM alert_snapshot WHERE is_active = 1 GROUP BY alert_type"
        ).fetchall()
        by_type = {r["alert_type"]: r["n"] for r in by_type_rows}
        return {
            "total": total,
            "active": active,
            "triggered": triggered,
            "pending": active - triggered,
            "by_type": by_type,
        }
    finally:
        db.close()
