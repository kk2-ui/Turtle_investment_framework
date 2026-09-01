#!/usr/bin/env python3
"""Persistent, append-only control boundary for historical carrier registries.

The pure helpers in :mod:`judgment_historical_training` validate artifact
shapes.  This module supplies the missing lifecycle fact: a registry state is
authoritative only when it was created from an already registered H1 receipt
and advanced through recorded events.  It deliberately does *not* loosen or
replace legacy V5 H1/H2 admission; a registry-aware V5 epoch is a later,
separate adapter.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
import uuid
from typing import Any

try:
    from scripts import judgment_historical_training as history
    from scripts import judgment_v5_control_plane as v5_control
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_historical_training as history
    import judgment_v5_control_plane as v5_control


SCHEMA_VERSION = "turtle-historical-training-control-plane.v1"
REGISTRY_TABLE = "judgment_historical_carrier_registries"
EVENT_TABLE = "judgment_historical_carrier_registry_events"
BATCH_RECEIPT_TABLE = "judgment_historical_static_peer_batch_receipts"


class HistoricalTrainingControlError(ValueError):
    """A stable error raised before any registry state is changed."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _iso(value: str, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise HistoricalTrainingControlError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoricalTrainingControlError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant")
    # Every ordering rule below is chronological, never lexical.  Persisting
    # one UTC representation also makes the database event stream auditable
    # across curators that supplied different, but equally valid, offsets.
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads(value: str) -> dict[str, Any]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - database corruption
        raise HistoricalTrainingControlError("stored_json_invalid", "stored control artifact is not valid JSON") from exc
    if not isinstance(loaded, dict):  # pragma: no cover - database corruption
        raise HistoricalTrainingControlError("stored_json_invalid", "stored control artifact must be an object")
    return loaded


def _reference(value: Any, *, field: str) -> tuple[str, int]:
    if not isinstance(value, dict) or not isinstance(value.get("receipt_id"), str) or not value["receipt_id"].strip():
        raise HistoricalTrainingControlError(f"{field}_invalid", f"{field}.receipt_id is required")
    version = value.get("receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise HistoricalTrainingControlError(f"{field}_invalid", f"{field}.receipt_version must be a positive integer")
    return value["receipt_id"], version


def initialize(conn: sqlite3.Connection) -> None:
    """Initialize only the dedicated historical-control namespace.

    V5's preselection receipts remain the sole source of H1/H2 truth.  This
    function asks V5 to initialize first so the foreign receipt references can
    be resolved; it creates no freeze, event, outcome, or legacy table row.
    """
    v5_control.initialize(conn)
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {REGISTRY_TABLE} (
                registry_id TEXT PRIMARY KEY,
                h1_receipt_id TEXT NOT NULL,
                h1_receipt_version INTEGER NOT NULL,
                universe_json TEXT NOT NULL,
                registry_json TEXT NOT NULL,
                registry_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (h1_receipt_id, h1_receipt_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {EVENT_TABLE} (
                event_id TEXT PRIMARY KEY,
                registry_id TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                event_kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                UNIQUE (registry_id, sequence_number),
                FOREIGN KEY (registry_id) REFERENCES {REGISTRY_TABLE}(registry_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {BATCH_RECEIPT_TABLE} (
                receipt_id TEXT NOT NULL,
                receipt_version INTEGER NOT NULL,
                registry_id TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                h2_receipt_id TEXT NOT NULL,
                h2_receipt_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY (receipt_id, receipt_version),
                UNIQUE (registry_id, batch_id),
                FOREIGN KEY (registry_id) REFERENCES {REGISTRY_TABLE}(registry_id)
            )"""
        )


def _preselection_row(
    conn: sqlite3.Connection, receipt_id: str, receipt_version: int, *, kind: str,
) -> sqlite3.Row:
    row = conn.execute(
        f"""SELECT * FROM {v5_control.PRESELECTION_RECEIPT_TABLE}
            WHERE receipt_id = ? AND receipt_version = ?""",
        (receipt_id, receipt_version),
    ).fetchone()
    if row is None:
        raise HistoricalTrainingControlError("preselection_receipt_not_found", "declared H1/H2 receipt is not registered")
    if row["receipt_kind"] != kind:
        raise HistoricalTrainingControlError("preselection_receipt_kind_invalid", "declared preselection receipt has the wrong kind")
    return row


def _h1_package(conn: sqlite3.Connection, reference: Any) -> tuple[sqlite3.Row, dict[str, Any]]:
    receipt_id, receipt_version = _reference(reference, field="h1_receipt_ref")
    row = _preselection_row(conn, receipt_id, receipt_version, kind=v5_control.H1_STATIC_COHORT_RECEIPT)
    payload = _loads(row["payload_json"])
    # The V5 control plane persists the validated package itself, rather than
    # the caller's H1 envelope; accepting an envelope here would accidentally
    # create a second mutable truth source.
    package = payload
    if package.get("schema_version") != "judgment-selection-stage0-static-package.v1":  # pragma: no cover - controlled writer invariant
        raise HistoricalTrainingControlError("registered_h1_payload_invalid", "registered H1 payload lacks its static package")
    return row, package


def _registry_row(conn: sqlite3.Connection, registry_id: str) -> sqlite3.Row:
    row = conn.execute(
        f"SELECT * FROM {REGISTRY_TABLE} WHERE registry_id = ?", (registry_id,),
    ).fetchone()
    if row is None:
        raise HistoricalTrainingControlError("carrier_registry_not_found", "carrier registry is not registered")
    return row


def _save_registry(
    conn: sqlite3.Connection, row: sqlite3.Row, registry: dict[str, Any], *, event_kind: str,
    payload: dict[str, Any], recorded_at: str,
) -> None:
    if _iso(recorded_at, field="recorded_at") < _iso(row["updated_at"], field="registry.updated_at"):
        raise HistoricalTrainingControlError("registry_event_time_regression", "registry events must be recorded monotonically")
    validation = history.validate_evidence_carrier_registry(registry)
    if not validation["valid"]:
        raise HistoricalTrainingControlError("carrier_registry_state_invalid", "; ".join(validation["findings"]))
    next_sequence = conn.execute(
        f"SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM {EVENT_TABLE} WHERE registry_id = ?",
        (row["registry_id"],),
    ).fetchone()[0]
    updated = conn.execute(
        f"""UPDATE {REGISTRY_TABLE}
            SET registry_json = ?, registry_state = ?, updated_at = ?
            WHERE registry_id = ? AND registry_json = ? AND updated_at = ?""",
        (
            _json(registry), registry["state"], recorded_at, row["registry_id"],
            row["registry_json"], row["updated_at"],
        ),
    )
    if updated.rowcount != 1:
        raise HistoricalTrainingControlError(
            "carrier_registry_state_conflict",
            "carrier registry changed after this transition was read; reload the canonical registry before retrying",
        )
    conn.execute(
        f"""INSERT INTO {EVENT_TABLE}
            (event_id, registry_id, sequence_number, event_kind, payload_json, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
        (f"HREG:{uuid.uuid4()}", row["registry_id"], next_sequence, event_kind, _json(payload), recorded_at),
    )


def create_registry_from_registered_h1(
    conn: sqlite3.Connection, h1_receipt_ref: dict[str, Any], *, recorded_at: str,
) -> dict[str, Any]:
    """Create the only mutable registry state from a registered immutable H1."""
    timestamp = _iso(recorded_at, field="recorded_at")
    h1_row, package = _h1_package(conn, h1_receipt_ref)
    if timestamp < _iso(h1_row["recorded_at"], field="registered_h1.recorded_at"):
        raise HistoricalTrainingControlError("registry_creation_precedes_h1_receipt", "registry cannot precede its registered H1 receipt")
    projection = history.project_stage0_h1_to_universe_and_carrier_seed(
        package,
        h1_receipt_ref={"receipt_id": h1_row["receipt_id"], "receipt_version": h1_row["receipt_version"]},
    )
    if not projection["valid"]:  # pragma: no cover - existing H1 writer invariant
        raise HistoricalTrainingControlError("registered_h1_projection_invalid", "; ".join(projection["findings"]))
    registry = projection["carrier_registry"]
    existing = conn.execute(
        f"SELECT * FROM {REGISTRY_TABLE} WHERE h1_receipt_id = ? AND h1_receipt_version = ?",
        (h1_row["receipt_id"], h1_row["receipt_version"]),
    ).fetchone()
    if existing is not None:
        if existing["registry_json"] != _json(registry):
            raise HistoricalTrainingControlError("registered_h1_registry_conflict", "registered H1 already projects to a different registry")
        return {
            "schema_version": SCHEMA_VERSION,
            "idempotent": True,
            "universe_snapshot": _loads(existing["universe_json"]),
            "carrier_registry": _loads(existing["registry_json"]),
        }
    with conn:
        conn.execute(
            f"""INSERT INTO {REGISTRY_TABLE}
                (registry_id, h1_receipt_id, h1_receipt_version, universe_json, registry_json, registry_state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (registry["registry_id"], h1_row["receipt_id"], h1_row["receipt_version"], _json(projection["universe_snapshot"]),
             _json(registry), registry["state"], timestamp, timestamp),
        )
        conn.execute(
            f"""INSERT INTO {EVENT_TABLE}
                (event_id, registry_id, sequence_number, event_kind, payload_json, recorded_at)
                VALUES (?, ?, 1, 'REGISTRY_CREATED_FROM_H1', ?, ?)""",
            (f"HREG:{uuid.uuid4()}", registry["registry_id"], _json({"h1_receipt_ref": h1_receipt_ref}), timestamp),
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "idempotent": False,
        "universe_snapshot": projection["universe_snapshot"],
        "carrier_registry": registry,
    }


def _h2_for_predicate(conn: sqlite3.Connection, row: sqlite3.Row, predicate: dict[str, Any]) -> sqlite3.Row:
    reference = predicate.get("action_screen_receipt_ref")
    h2_id, h2_version = _reference(reference, field="peer_recruitment_predicate.action_screen_receipt_ref")
    h2_row = _preselection_row(conn, h2_id, h2_version, kind=v5_control.H2_ACTION_SCREEN_RECEIPT)
    if (h2_row["parent_receipt_id"], h2_row["parent_receipt_version"]) != (
        row["h1_receipt_id"], row["h1_receipt_version"],
    ):
        raise HistoricalTrainingControlError("peer_recruitment_h2_parent_mismatch", "predicate H2 must be parented by this registry's H1")
    if _iso(predicate.get("source_cutoff_at"), field="peer_recruitment_predicate.source_cutoff_at") != _iso(
        h2_row["cutoff_at"], field="registered_h2.cutoff_at",
    ):
        raise HistoricalTrainingControlError("peer_recruitment_source_cutoff_mismatch", "peer batch cutoff must equal the registered H2 cutoff")
    if _iso(predicate.get("frozen_at"), field="peer_recruitment_predicate.frozen_at") < _iso(
        h2_row["recorded_at"], field="registered_h2.recorded_at",
    ):
        raise HistoricalTrainingControlError("peer_recruitment_predicate_precedes_h2_receipt", "predicate cannot precede its registered H2 receipt")
    return h2_row


def freeze_registered_peer_recruitment_predicate(
    conn: sqlite3.Connection, registry_id: str, predicate: dict[str, Any], *, recorded_at: str,
) -> dict[str, Any]:
    """Freeze an H2-parented recruitment rule in the registry event stream."""
    timestamp = _iso(recorded_at, field="recorded_at")
    row = _registry_row(conn, registry_id)
    registry = _loads(row["registry_json"])
    _h2_for_predicate(conn, row, predicate)
    if _iso(predicate.get("frozen_at"), field="peer_recruitment_predicate.frozen_at") != timestamp:
        raise HistoricalTrainingControlError("peer_recruitment_predicate_time_mismatch", "predicate frozen_at must equal its recorded registry event time")
    result = history.freeze_peer_recruitment_eligibility_predicate(registry, predicate)
    if not result["valid"]:
        raise HistoricalTrainingControlError("peer_recruitment_predicate_invalid", "; ".join(result["findings"]))
    with conn:
        _save_registry(conn, row, result["carrier_registry"], event_kind="PEER_RECRUITMENT_PREDICATE_FROZEN",
                       payload={"predicate": predicate}, recorded_at=timestamp)
    return {"schema_version": SCHEMA_VERSION, "carrier_registry": result["carrier_registry"]}


def register_static_peer_batch(
    conn: sqlite3.Connection, registry_id: str, batch: dict[str, Any], *, recorded_at: str,
) -> dict[str, Any]:
    """Record and append one static peer batch before registry freeze.

    The batch's own receipt reference is the persistent immutable identity.  A
    repeat with byte-for-byte equivalent canonical JSON is idempotent; a
    replacement under the same receipt ID/version is rejected.
    """
    timestamp = _iso(recorded_at, field="recorded_at")
    row = _registry_row(conn, registry_id)
    registry = _loads(row["registry_json"])
    predicate = registry.get("peer_recruitment_predicate")
    if not isinstance(predicate, dict):
        raise HistoricalTrainingControlError("peer_recruitment_predicate_not_frozen", "freeze an H2-parented predicate before registering a peer batch")
    h2_row = _h2_for_predicate(conn, row, predicate)
    receipt_id, receipt_version = _reference(batch.get("source_packet_ref"), field="peer_recruitment_batch.source_packet_ref")
    received_at = _iso(batch.get("received_at"), field="peer_recruitment_batch.received_at")
    if received_at < _iso(predicate["frozen_at"], field="peer_recruitment_predicate.frozen_at"):
        raise HistoricalTrainingControlError("peer_recruitment_batch_precedes_predicate", "batch cannot be received before the eligibility predicate is frozen")
    if received_at > timestamp:
        raise HistoricalTrainingControlError("peer_recruitment_batch_recorded_before_received", "batch cannot be recorded before it is received")
    if not isinstance(batch.get("curator_id"), str) or not batch["curator_id"].strip():
        raise HistoricalTrainingControlError("peer_recruitment_batch_curator_missing", "static peer batch must identify its curator")
    h1_row, _ = _h1_package(conn, {"receipt_id": row["h1_receipt_id"], "receipt_version": row["h1_receipt_version"]})
    if batch["curator_id"] != h1_row["curator_id"]:
        raise HistoricalTrainingControlError("peer_recruitment_batch_curator_mismatch", "peer batch curator must match the registered H1/H2 curator")
    existing = conn.execute(
        f"SELECT * FROM {BATCH_RECEIPT_TABLE} WHERE receipt_id = ? AND receipt_version = ?",
        (receipt_id, receipt_version),
    ).fetchone()
    canonical_batch = _json(batch)
    if existing is not None:
        if existing["registry_id"] != registry_id or existing["payload_json"] != canonical_batch:
            raise HistoricalTrainingControlError("peer_recruitment_batch_receipt_conflict", "peer batch receipt already records different content")
        return {"schema_version": SCHEMA_VERSION, "idempotent": True, "carrier_registry": registry}
    result = history.append_static_peer_recruitment_batch(registry, batch)
    if not result["valid"]:
        raise HistoricalTrainingControlError("peer_recruitment_batch_invalid", "; ".join(result["findings"]))
    with conn:
        conn.execute(
            f"""INSERT INTO {BATCH_RECEIPT_TABLE}
                (receipt_id, receipt_version, registry_id, batch_id, h2_receipt_id, h2_receipt_version, payload_json, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (receipt_id, receipt_version, registry_id, batch["batch_id"], h2_row["receipt_id"], h2_row["receipt_version"], canonical_batch, timestamp),
        )
        _save_registry(conn, row, result["carrier_registry"], event_kind="STATIC_PEER_BATCH_APPENDED",
                       payload={"receipt_id": receipt_id, "receipt_version": receipt_version, "batch_id": batch["batch_id"]},
                       recorded_at=timestamp)
    return {"schema_version": SCHEMA_VERSION, "idempotent": False, "carrier_registry": result["carrier_registry"]}


def resolve_registered_pending_carriers(
    conn: sqlite3.Connection, registry_id: str, resolutions: list[dict[str, Any]], *, recorded_at: str,
) -> dict[str, Any]:
    """Resolve the original pending carriers without allowing break restoration."""
    timestamp = _iso(recorded_at, field="recorded_at")
    row = _registry_row(conn, registry_id)
    result = history.resolve_pending_carrier_eligibility(_loads(row["registry_json"]), resolutions)
    if not result["valid"]:
        raise HistoricalTrainingControlError("carrier_eligibility_resolution_invalid", "; ".join(result["findings"]))
    with conn:
        _save_registry(conn, row, result["carrier_registry"], event_kind="PENDING_CARRIER_ELIGIBILITY_RESOLVED",
                       payload={"resolutions": resolutions}, recorded_at=timestamp)
    return {"schema_version": SCHEMA_VERSION, "carrier_registry": result["carrier_registry"]}


def freeze_registered_carrier_registry(
    conn: sqlite3.Connection, registry_id: str, *, recorded_at: str,
) -> dict[str, Any]:
    """Close the per-episode registry before any registry-aware comparative adapter."""
    timestamp = _iso(recorded_at, field="recorded_at")
    row = _registry_row(conn, registry_id)
    result = history.freeze_evidence_carrier_registry(_loads(row["registry_json"]), frozen_at=timestamp)
    if not result["valid"]:
        raise HistoricalTrainingControlError("carrier_registry_freeze_invalid", "; ".join(result["findings"]))
    with conn:
        _save_registry(conn, row, result["carrier_registry"], event_kind="CARRIER_REGISTRY_FROZEN",
                       payload=result["freeze_receipt"], recorded_at=timestamp)
    return {"schema_version": SCHEMA_VERSION, "carrier_registry": result["carrier_registry"], "freeze_receipt": result["freeze_receipt"]}


def load_registered_registry(conn: sqlite3.Connection, registry_id: str) -> dict[str, Any]:
    """Read the canonical database state for a registry; never accept a caller copy."""
    row = _registry_row(conn, registry_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "universe_snapshot": _loads(row["universe_json"]),
        "carrier_registry": _loads(row["registry_json"]),
        "state": row["registry_state"],
    }
