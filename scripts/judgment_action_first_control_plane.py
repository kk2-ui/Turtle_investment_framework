#!/usr/bin/env python3
"""Append-only SQLite storage for A1 action-first candidate receipts.

The database stores the receipt exactly as validated and can replay only the
action-blind comparator recruitment brief.  It has no H1/H2/V5, outcome,
price, forecast, CJO, report, learning, or investment dependency.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

try:
    from scripts import judgment_selection_action_first as action_first
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_selection_action_first as action_first


RECEIPT_TABLE = "judgment_selection_action_first_candidate_receipts"


class ActionFirstControlPlaneError(ValueError):
    """Stable error raised before a persistent A1 state change."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):  # pragma: no cover - stored invariant
        raise ActionFirstControlPlaneError("stored_receipt_invalid", "stored receipt must be an object")
    return decoded


def _instant(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActionFirstControlPlaneError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ActionFirstControlPlaneError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ActionFirstControlPlaneError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def initialize(conn: sqlite3.Connection) -> None:
    """Create the single append-only A1 receipt table."""
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {RECEIPT_TABLE} (
                receipt_id TEXT NOT NULL,
                receipt_version INTEGER NOT NULL,
                candidate_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                issuer_id TEXT NOT NULL,
                responsibility_unit_id TEXT NOT NULL,
                perimeter_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                PRIMARY KEY (receipt_id, receipt_version),
                UNIQUE (candidate_id, company_id, issuer_id, cutoff_at)
            )"""
        )
        for operation in ("UPDATE", "DELETE"):
            conn.execute(
                f"""CREATE TRIGGER IF NOT EXISTS {RECEIPT_TABLE}_{operation.lower()}_blocked
                    BEFORE {operation} ON {RECEIPT_TABLE}
                    BEGIN
                        SELECT RAISE(ABORT, 'action-first candidate receipts are append-only');
                    END"""
            )


def register_candidate_receipt(
    conn: sqlite3.Connection, receipt: dict[str, Any], *, registered_at: str,
) -> dict[str, Any]:
    """Validate and append exactly one immutable candidate receipt."""
    timestamp = _instant(registered_at, "receipt.registered_at")
    result = action_first.validate_action_first_candidate_receipt(receipt)
    if not result["valid"]:
        raise ActionFirstControlPlaneError("candidate_receipt_invalid", "; ".join(result["findings"]))
    payload = result["candidate_receipt"]
    cutoff = _instant(payload["cutoff_at"], "receipt.cutoff_at")
    if datetime.fromisoformat(cutoff) >= datetime.fromisoformat(timestamp):
        raise ActionFirstControlPlaneError(
            "candidate_receipt_cutoff_not_before_registration",
            "candidate receipt cutoff must strictly precede registration",
        )
    encoded = _json(payload)
    identity = (payload["receipt_id"], payload["receipt_version"])
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {RECEIPT_TABLE} WHERE receipt_id = ? AND receipt_version = ?", identity,
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["registered_at"] != timestamp:
                raise ActionFirstControlPlaneError(
                    "candidate_receipt_immutable_conflict", "receipt identity already has different content",
                )
            return {
                "registered": True,
                "receipt_id": payload["receipt_id"],
                "receipt_version": payload["receipt_version"],
                "idempotent": True,
            }
        same_candidate = conn.execute(
            f"""SELECT receipt_id FROM {RECEIPT_TABLE}
                WHERE candidate_id = ? AND company_id = ? AND issuer_id = ? AND cutoff_at = ?""",
            (payload["candidate_id"], payload["company_id"], payload["issuer_id"], payload["cutoff_at"]),
        ).fetchone()
        if same_candidate is not None:
            raise ActionFirstControlPlaneError(
                "candidate_receipt_already_registered",
                "candidate identity already has an immutable receipt at this cutoff",
            )
        conn.execute(
            f"""INSERT INTO {RECEIPT_TABLE} (
                receipt_id, receipt_version, candidate_id, company_id, issuer_id,
                responsibility_unit_id, perimeter_id, cutoff_at, payload_json, registered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["receipt_id"], payload["receipt_version"], payload["candidate_id"], payload["company_id"],
                payload["issuer_id"], payload["responsibility_unit_id"], payload["perimeter_id"], payload["cutoff_at"],
                encoded, timestamp,
            ),
        )
    return {
        "registered": True,
        "receipt_id": payload["receipt_id"],
        "receipt_version": payload["receipt_version"],
        "idempotent": False,
    }


def replay_candidate_receipt(
    conn: sqlite3.Connection, *, receipt_id: str, receipt_version: int,
) -> dict[str, Any]:
    """Return the exact stored candidate payload, not a mutable live object."""
    if not isinstance(receipt_id, str) or not receipt_id.strip() or not isinstance(receipt_version, int) or isinstance(receipt_version, bool) or receipt_version < 1:
        raise ActionFirstControlPlaneError("candidate_receipt_reference_invalid", "a positive receipt identity is required")
    row = conn.execute(
        f"SELECT payload_json FROM {RECEIPT_TABLE} WHERE receipt_id = ? AND receipt_version = ?",
        (receipt_id, receipt_version),
    ).fetchone()
    if row is None:
        raise ActionFirstControlPlaneError("candidate_receipt_not_found", "candidate receipt is not registered")
    return _load(row["payload_json"])


def load_comparator_recruitment_brief(
    conn: sqlite3.Connection, *, receipt_id: str, receipt_version: int,
) -> dict[str, Any]:
    """Load the sole permitted, action-blind A1 handoff."""
    return action_first.build_comparator_recruitment_brief(
        replay_candidate_receipt(conn, receipt_id=receipt_id, receipt_version=receipt_version),
    )
