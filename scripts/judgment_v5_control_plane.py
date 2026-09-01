#!/usr/bin/env python3
"""Minimal append-only control plane for V5 selection freezes.

This module deliberately owns only the control boundary around an already
validated V5 selection bundle.  Economic admission and outcome reconstruction
belong to :mod:`scripts.judgment_selection_v5`; V4, R-104 and R-103 are never
read or written here.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "judgment-v5-control-plane.v1"
FREEZE_TABLE = "judgment_v5_selection_freezes"
EVENT_TABLE = "judgment_v5_events"
PRESELECTION_RECEIPT_TABLE = "judgment_v5_preselection_receipts"

# The H1/H2 intake contract permits only static CNINFO finalpage PDFs.  A V5
# root must repeat their identity rather than treating a caller-chosen
# ``source_id`` as sufficient provenance.
STATIC_CNINFO_PUBLISHER = "CNINFO_STATIC_FINALPAGE"
_H1_PRESELECTION_LANES = {"STAGE0_STATIC", "PUBLIC_ARENA_CONTEXT"}
_H2_PRESELECTION_LANES = {"ACTION_STATIC"}
_STATIC_SOURCE_IDENTITY_FIELDS = (
    "source_id",
    "official_artifact_id",
    "source_url",
    "publisher",
    "source_type",
    "issuer_id",
    "responsibility_unit_id",
    "perimeter_id",
    "unit",
    "published_at_or_date",
    "availability_precision",
    "outcome_visibility",
)

H1_STATIC_COHORT_RECEIPT = "H1_STATIC_COHORT"
H2_ACTION_SCREEN_RECEIPT = "H2_ACTION_SCREEN"
PRESELECTION_RECEIPT_KINDS = {
    H1_STATIC_COHORT_RECEIPT,
    H2_ACTION_SCREEN_RECEIPT,
}

ADMITTED = "SELECTION_ADMITTED"
RECEIPT_KINDS = {
    "OUTCOME_PACKAGE",
    "OUTCOME_READER",
    "OUTCOME_EXTRACTION",
    "MISSING_CELL",
    "PIT_ACCESS_BREACH",
}
RECEIPT_KIND_ALIASES = {
    "PACKAGE": "OUTCOME_PACKAGE",
    "OUTCOME_PACKAGE": "OUTCOME_PACKAGE",
    "READER": "OUTCOME_READER",
    "OUTCOME_READER": "OUTCOME_READER",
    "OUTCOME_READER_ATTESTATION": "OUTCOME_READER",
    "EXTRACTION": "OUTCOME_EXTRACTION",
    "OUTCOME_EXTRACTION": "OUTCOME_EXTRACTION",
    "MISSING_CELL": "MISSING_CELL",
    "PIT_ACCESS_BREACH": "PIT_ACCESS_BREACH",
}
RESOLUTION_STATUSES = {
    "A_ONLY",
    "B_ONLY",
    "MIXED",
    "UNKNOWN",
    "NOT_DIAGNOSTIC",
    "BOUNDARY_CAPTURED",
}
TERMINAL_EVENT_TYPES = {
    "FREEZE_VOIDED_PRE_ACCESS",
    "PIT_ACCESS_BREACH",
    "EXPOSURE_EXCLUDED",
    "OUTCOME_RESOLVED",
}
OUTCOME_IDENTITY_FIELDS = {
    "actual_outcome_inventory",
    "actual_source_inventory",
    "outcome_source_inventory",
    "outcome_sources",
    "actual_outcome_source_id",
    "actual_outcome_source_title",
    "actual_outcome_source_published_at",
    "actual_outcome_metadata",
}
OUTCOME_SOURCE_METADATA_FIELDS = {
    "source_id",
    "official_artifact_id",
    "title",
    "source_title",
    "published_at",
    "published_at_or_date",
    "source_available_at",
}


class ControlPlaneError(ValueError):
    """A stable, caller-facing V5 control-plane failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite database without touching any legacy V4 namespace."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    """Create the V5 selection and immutable preselection-receipt tables."""
    with conn:
        # H1/H2 source receipts are deliberately separate from a selection
        # freeze.  A receipt establishes a closed static-PDF input; it does
        # not create an episode, expose an outcome, or authorize a seal.
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {PRESELECTION_RECEIPT_TABLE} (
                receipt_id TEXT NOT NULL,
                receipt_version INTEGER NOT NULL,
                receipt_kind TEXT NOT NULL,
                parent_receipt_id TEXT,
                parent_receipt_version INTEGER,
                cohort_id TEXT NOT NULL,
                selection_as_of TEXT NOT NULL,
                curator_id TEXT NOT NULL,
                screen_id TEXT,
                cutoff_at TEXT,
                payload_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                PRIMARY KEY (receipt_id, receipt_version),
                FOREIGN KEY (parent_receipt_id, parent_receipt_version)
                    REFERENCES {PRESELECTION_RECEIPT_TABLE}(receipt_id, receipt_version)
            )"""
        )
        conn.execute(
            f"""CREATE UNIQUE INDEX IF NOT EXISTS judgment_v5_h1_receipt_natural_key
                ON {PRESELECTION_RECEIPT_TABLE}(cohort_id, selection_as_of, curator_id)
                WHERE receipt_kind = '{H1_STATIC_COHORT_RECEIPT}'"""
        )
        conn.execute(
            f"""CREATE UNIQUE INDEX IF NOT EXISTS judgment_v5_h2_receipt_natural_key
                ON {PRESELECTION_RECEIPT_TABLE}(parent_receipt_id, parent_receipt_version, screen_id)
                WHERE receipt_kind = '{H2_ACTION_SCREEN_RECEIPT}'"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {FREEZE_TABLE} (
                selection_freeze_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                episode_collision_key TEXT NOT NULL,
                research_cutoff_at TEXT NOT NULL,
                predecessor_freeze_id TEXT,
                bundle_json TEXT NOT NULL,
                sealed_at TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                FOREIGN KEY(predecessor_freeze_id)
                    REFERENCES {FREEZE_TABLE}(selection_freeze_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {EVENT_TABLE} (
                event_id TEXT PRIMARY KEY,
                selection_freeze_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                effective_at TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(selection_freeze_id)
                    REFERENCES {FREEZE_TABLE}(selection_freeze_id)
            )"""
        )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads(value: str) -> Any:
    return json.loads(value)


def _derive_outcome_resolution(
    bundle: dict[str, Any], outcome_receipts: Any, *, authorized_custodian_id: str | None,
) -> tuple[str, list[str]]:
    """Recompute the only admissible terminal result from frozen raw receipts.

    The control plane deliberately stores no second raw-outcome corpus.  It does,
    however, require the authorized custodian's typed receipt at resolution time
    and lets the pure V5 resolver derive the status from the sealed bundle.
    """
    if not isinstance(outcome_receipts, dict):
        raise ControlPlaneError("outcome_receipts_required", "resolution requires typed outcome_receipts")
    attestation = outcome_receipts.get("custodian_attestation")
    if not isinstance(attestation, dict):
        raise ControlPlaneError("outcome_receipts_attestation_missing", "outcome_receipts requires custodian attestation")
    receipt_custodian_id = str(attestation.get("custodian_id") or "").strip()
    if not receipt_custodian_id or receipt_custodian_id != authorized_custodian_id:
        raise ControlPlaneError(
            "outcome_receipts_custodian_mismatch",
            "outcome_receipts must be attested by the authorized custodian",
        )
    try:
        from scripts.judgment_selection_v5_outcome import resolve_v5_outcome
    except ModuleNotFoundError:
        try:
            from judgment_selection_v5_outcome import resolve_v5_outcome
        except ModuleNotFoundError as exc:
            raise ControlPlaneError(
                "outcome_resolver_unavailable",
                "scripts.judgment_selection_v5_outcome.resolve_v5_outcome is required before resolution",
            ) from exc
    derived = resolve_v5_outcome(bundle, outcome_receipts)
    if not isinstance(derived, dict) or derived.get("valid") is not True:
        findings = derived.get("findings") if isinstance(derived, dict) else None
        detail = ", ".join(str(item) for item in findings) if isinstance(findings, list) else "invalid result"
        raise ControlPlaneError("outcome_reconstruction_invalid", "frozen outcome reconstruction failed: " + detail)
    resolution = derived.get("resolution")
    if not isinstance(resolution, dict):
        raise ControlPlaneError("outcome_reconstruction_invalid", "frozen outcome reconstruction returned no resolution")
    status_value = str(resolution.get("status") or "").upper()
    if status_value not in RESOLUTION_STATUSES and status_value != "EXPOSURE_EXCLUDED":
        raise ControlPlaneError("derived_resolution_status_invalid", "frozen outcome reconstruction returned an unsupported status")
    findings = derived.get("findings")
    return status_value, list(findings) if isinstance(findings, list) else []


def _registered_outcome_source_ids(state: dict[str, Any]) -> set[str]:
    """Return the exact outcome-source IDs registered by the custodian package."""
    source_ids: set[str] = set()
    for event in state["events"]:
        payload = event.get("payload")
        if (
            event.get("event_type") != "CONTROL_RECEIPT"
            or not isinstance(payload, dict)
            or payload.get("receipt_kind") != "OUTCOME_PACKAGE"
        ):
            continue
        detail = payload.get("detail")
        if not isinstance(detail, dict):
            continue
        inventory = detail.get("actual_outcome_inventory")
        if not isinstance(inventory, list):
            continue
        for source in inventory:
            if isinstance(source, dict):
                source_id = str(source.get("source_id") or "").strip()
                if source_id:
                    source_ids.add(source_id)
    return source_ids


def _require_registered_primary_sources(
    bundle: dict[str, Any], outcome_receipts: Any, *, registered_source_ids: set[str],
) -> None:
    """Bind post-outcome inputs to the custodian's registered package.

    Frozen baseline evidence remains governed by the pre-outcome bundle.  Only
    primary-outcome raw cells and post-outcome boundary facts must be sourced
    from the authorized package.
    """
    if not isinstance(outcome_receipts, dict):
        return
    outcome_contract = bundle.get("outcome_contract")
    matrix = outcome_contract.get("frozen_raw_matrix") if isinstance(outcome_contract, dict) else None
    if not isinstance(matrix, list):
        return
    primary_keys = {
        (
            str(row.get("issuer_id") or ""),
            str(row.get("metric_id") or ""),
            str(row.get("period_id") or ""),
            str(row.get("field_id") or ""),
        )
        for row in matrix
        if isinstance(row, dict) and row.get("observation_role") == "PRIMARY_OUTCOME"
    }

    def require(source: Any, *, field: str) -> None:
        if not isinstance(source, dict):
            return
        source_id = str(source.get("source_id") or "").strip()
        if source_id and source_id not in registered_source_ids:
            raise ControlPlaneError(
                "outcome_source_not_in_registered_package",
                f"{field} source_id is not registered in an authorized OUTCOME_PACKAGE: {source_id}",
            )

    raw_cells = outcome_receipts.get("raw_cells")
    if isinstance(raw_cells, list):
        for index, cell in enumerate(raw_cells):
            if not isinstance(cell, dict):
                continue
            key = (
                str(cell.get("issuer_id") or ""),
                str(cell.get("metric_id") or ""),
                str(cell.get("period_id") or ""),
                str(cell.get("field_id") or ""),
            )
            if key in primary_keys:
                require(cell.get("source"), field=f"outcome_receipts.raw_cells[{index}]")
    boundary_facts = outcome_receipts.get("boundary_facts")
    if isinstance(boundary_facts, list):
        for index, fact in enumerate(boundary_facts):
            if isinstance(fact, dict):
                require(fact.get("source"), field=f"outcome_receipts.boundary_facts[{index}]")


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError("field_missing", f"{field} is required")
    return value.strip()


def _parse_time(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError("time_missing", f"{field} is required")
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ControlPlaneError("time_invalid", f"{field} must be ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ControlPlaneError("time_timezone_missing", f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _now() -> str:
    return _iso(datetime.now(timezone.utc).replace(microsecond=0))


def _positive_integer(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ControlPlaneError("receipt_version_invalid", f"{field} must be a positive integer")
    return value


def _closed_receipt(value: Any, *, required: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ControlPlaneError("preselection_receipt_invalid", f"{name} must be an object")
    unexpected = sorted(set(value) - required)
    missing = sorted(required - set(value))
    if missing or unexpected:
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected " + ", ".join(unexpected))
        raise ControlPlaneError("preselection_receipt_shape_invalid", f"{name} receipt must be closed: " + "; ".join(detail))
    return value


def _preselection_row(
    conn: sqlite3.Connection,
    receipt_id: str,
    receipt_version: int,
    *,
    expected_kind: str | None = None,
) -> sqlite3.Row:
    row = conn.execute(
        f"""SELECT * FROM {PRESELECTION_RECEIPT_TABLE}
            WHERE receipt_id = ? AND receipt_version = ?""",
        (receipt_id, receipt_version),
    ).fetchone()
    if row is None:
        raise ControlPlaneError(
            "preselection_receipt_not_found",
            f"preselection receipt not found: {receipt_id}@{receipt_version}",
        )
    if expected_kind is not None and row["receipt_kind"] != expected_kind:
        raise ControlPlaneError(
            "preselection_receipt_kind_mismatch",
            f"{receipt_id}@{receipt_version} is not a {expected_kind} receipt",
        )
    return row


def _receipt_result(row: sqlite3.Row, *, idempotent: bool) -> dict[str, Any]:
    return {
        "registered": True,
        "receipt_id": row["receipt_id"],
        "receipt_version": row["receipt_version"],
        "receipt_kind": row["receipt_kind"],
        "idempotent": idempotent,
    }


def _register_preselection_receipt(
    conn: sqlite3.Connection,
    *,
    receipt_id: str,
    receipt_version: int,
    receipt_kind: str,
    parent_receipt_id: str | None,
    parent_receipt_version: int | None,
    cohort_id: str,
    selection_as_of: str,
    curator_id: str,
    screen_id: str | None,
    cutoff_at: str | None,
    payload: dict[str, Any],
    recorded_at: str,
    schema_version: str,
) -> dict[str, Any]:
    """Persist one closed H1/H2 payload, with exact-replay idempotency only."""
    payload_json = _json(payload)
    with conn:
        existing = conn.execute(
            f"""SELECT * FROM {PRESELECTION_RECEIPT_TABLE}
                WHERE receipt_id = ? AND receipt_version = ?""",
            (receipt_id, receipt_version),
        ).fetchone()
        if existing is not None:
            stored = {
                field: existing[field]
                for field in (
                    "receipt_kind", "parent_receipt_id", "parent_receipt_version", "cohort_id",
                    "selection_as_of", "curator_id", "screen_id", "cutoff_at", "payload_json",
                    "recorded_at", "schema_version",
                )
            }
            proposed = {
                "receipt_kind": receipt_kind,
                "parent_receipt_id": parent_receipt_id,
                "parent_receipt_version": parent_receipt_version,
                "cohort_id": cohort_id,
                "selection_as_of": selection_as_of,
                "curator_id": curator_id,
                "screen_id": screen_id,
                "cutoff_at": cutoff_at,
                "payload_json": payload_json,
                "recorded_at": recorded_at,
                "schema_version": schema_version,
            }
            if stored != proposed:
                raise ControlPlaneError(
                    "preselection_receipt_immutable_conflict",
                    "receipt_id and receipt_version already identify different immutable content",
                )
            return _receipt_result(existing, idempotent=True)

        if receipt_kind == H1_STATIC_COHORT_RECEIPT:
            duplicate = conn.execute(
                f"""SELECT receipt_id, receipt_version FROM {PRESELECTION_RECEIPT_TABLE}
                    WHERE receipt_kind = ? AND cohort_id = ? AND selection_as_of = ? AND curator_id = ?""",
                (receipt_kind, cohort_id, selection_as_of, curator_id),
            ).fetchone()
            if duplicate is not None:
                raise ControlPlaneError(
                    "h1_receipt_natural_key_conflict",
                    "the H1 cohort/time/curator tuple already has an immutable receipt",
                )
        else:
            duplicate = conn.execute(
                f"""SELECT receipt_id, receipt_version FROM {PRESELECTION_RECEIPT_TABLE}
                    WHERE receipt_kind = ? AND parent_receipt_id = ?
                    AND parent_receipt_version = ? AND screen_id = ?""",
                (receipt_kind, parent_receipt_id, parent_receipt_version, screen_id),
            ).fetchone()
            if duplicate is not None:
                raise ControlPlaneError(
                    "h2_receipt_natural_key_conflict",
                    "the registered H1 receipt already has an immutable receipt for this screen_id",
                )

        conn.execute(
            f"""INSERT INTO {PRESELECTION_RECEIPT_TABLE} (
                receipt_id, receipt_version, receipt_kind,
                parent_receipt_id, parent_receipt_version,
                cohort_id, selection_as_of, curator_id, screen_id, cutoff_at,
                payload_json, recorded_at, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                receipt_id, receipt_version, receipt_kind,
                parent_receipt_id, parent_receipt_version,
                cohort_id, selection_as_of, curator_id, screen_id, cutoff_at,
                payload_json, recorded_at, schema_version,
            ),
        )
        row = _preselection_row(conn, receipt_id, receipt_version)
    return _receipt_result(row, idempotent=False)


def register_h1_static_cohort_receipt(
    conn: sqlite3.Connection,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Validate and immutably register one strict H1 static cohort package."""
    receipt = _closed_receipt(
        receipt,
        required={"receipt_id", "receipt_version", "recorded_at", "stage0_static_package"},
        name="H1",
    )
    receipt_id = _required_text(receipt, "receipt_id")
    receipt_version = _positive_integer(receipt.get("receipt_version"), field="receipt_version")
    recorded_at = _iso(_parse_time(receipt.get("recorded_at"), field="recorded_at"))
    package = receipt.get("stage0_static_package")
    if not isinstance(package, dict):
        raise ControlPlaneError("h1_receipt_package_invalid", "stage0_static_package must be an object")
    try:
        from scripts.judgment_selection_discovery import (
            STAGE0_FEASIBILITY_REVIEWABLE,
            validate_stage0_static_source_package,
        )
    except ModuleNotFoundError:
        from judgment_selection_discovery import (  # type: ignore[no-redef]
            STAGE0_FEASIBILITY_REVIEWABLE,
            validate_stage0_static_source_package,
        )
    validated = validate_stage0_static_source_package(package)
    if validated.get("state") != STAGE0_FEASIBILITY_REVIEWABLE:
        findings = validated.get("findings")
        detail = ", ".join(str(item) for item in findings) if isinstance(findings, list) else "invalid H1 package"
        raise ControlPlaneError("h1_receipt_validation_failed", detail)
    attestation = package.get("curator_attestation")
    if not isinstance(attestation, dict):  # Defensive only for a bad validator result.
        raise ControlPlaneError("h1_receipt_validation_failed", "H1 package has no curator attestation")
    return _register_preselection_receipt(
        conn,
        receipt_id=receipt_id,
        receipt_version=receipt_version,
        receipt_kind=H1_STATIC_COHORT_RECEIPT,
        parent_receipt_id=None,
        parent_receipt_version=None,
        cohort_id=_required_text(package, "cohort_id"),
        selection_as_of=_iso(_parse_time(package.get("selection_as_of"), field="stage0_static_package.selection_as_of")),
        curator_id=_required_text(attestation, "curator_id"),
        screen_id=None,
        cutoff_at=None,
        payload=package,
        recorded_at=recorded_at,
        schema_version=_required_text(package, "schema_version"),
    )


def register_h2_action_screen_receipt(
    conn: sqlite3.Connection,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Register one H2 extension against the already immutable H1 payload."""
    receipt = _closed_receipt(
        receipt,
        required={
            "receipt_id", "receipt_version", "recorded_at", "h1_receipt_id",
            "h1_receipt_version", "action_screen_extension",
        },
        name="H2",
    )
    receipt_id = _required_text(receipt, "receipt_id")
    receipt_version = _positive_integer(receipt.get("receipt_version"), field="receipt_version")
    recorded_at = _iso(_parse_time(receipt.get("recorded_at"), field="recorded_at"))
    parent_receipt_id = _required_text(receipt, "h1_receipt_id")
    parent_receipt_version = _positive_integer(receipt.get("h1_receipt_version"), field="h1_receipt_version")
    extension = receipt.get("action_screen_extension")
    if not isinstance(extension, dict):
        raise ControlPlaneError("h2_receipt_extension_invalid", "action_screen_extension must be an object")
    parent = _preselection_row(
        conn, parent_receipt_id, parent_receipt_version, expected_kind=H1_STATIC_COHORT_RECEIPT,
    )
    stage0_package = _loads(parent["payload_json"])
    try:
        from scripts.judgment_selection_discovery import (
            ACTION_SCREEN_REVIEWABLE,
            validate_action_screen_static_extension,
        )
    except ModuleNotFoundError:
        from judgment_selection_discovery import (  # type: ignore[no-redef]
            ACTION_SCREEN_REVIEWABLE,
            validate_action_screen_static_extension,
        )
    validated = validate_action_screen_static_extension(stage0_package, extension)
    if validated.get("state") != ACTION_SCREEN_REVIEWABLE:
        findings = validated.get("findings")
        detail = ", ".join(str(item) for item in findings) if isinstance(findings, list) else "invalid H2 extension"
        raise ControlPlaneError("h2_receipt_validation_failed", detail)
    return _register_preselection_receipt(
        conn,
        receipt_id=receipt_id,
        receipt_version=receipt_version,
        receipt_kind=H2_ACTION_SCREEN_RECEIPT,
        parent_receipt_id=parent_receipt_id,
        parent_receipt_version=parent_receipt_version,
        cohort_id=parent["cohort_id"],
        selection_as_of=parent["selection_as_of"],
        curator_id=parent["curator_id"],
        screen_id=_required_text(extension, "screen_id"),
        cutoff_at=_iso(_parse_time(extension.get("cutoff_at"), field="action_screen_extension.cutoff_at")),
        payload=extension,
        recorded_at=recorded_at,
        schema_version=_required_text(extension, "schema_version"),
    )


def _static_availability_precision(published_at: str) -> str:
    """Project the package's declared date precision into V5 source identity."""
    return "DATE_ONLY" if len(published_at.strip()) == 10 else "INTRADAY"


def _preselection_static_source_map(
    h1_payload: dict[str, Any], h2_payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Project immutable H1/H2 PDF declarations into the V5 source surface.

    ``source_id`` is only a lookup key.  The returned identity contains the
    artifact URL/ID, publication precision and the source's modeled boundary,
    so a root cannot relabel a registered ID as a different document or lane.
    """
    source_map: dict[str, dict[str, Any]] = {}
    for payload, permitted_lanes in (
        (h1_payload, _H1_PRESELECTION_LANES),
        (h2_payload, _H2_PRESELECTION_LANES),
    ):
        sources = payload.get("static_pdf_sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if isinstance(source, dict):
                source_id = source.get("source_id")
                if isinstance(source_id, str) and source_id.strip():
                    published_at = source.get("published_at")
                    if not isinstance(published_at, str) or not published_at.strip():
                        raise ControlPlaneError(
                            "registered_preselection_source_identity_invalid",
                            f"registered source {source_id} has no publication time",
                        )
                    canonical = {
                        "source_id": source_id,
                        "official_artifact_id": source_id,
                        "source_url": source.get("url"),
                        "publisher": STATIC_CNINFO_PUBLISHER,
                        "source_type": source.get("source_type"),
                        "issuer_id": source.get("issuer_id"),
                        "responsibility_unit_id": source.get("responsibility_unit_id"),
                        "perimeter_id": source.get("perimeter_id"),
                        "unit": source.get("unit"),
                        "published_at_or_date": published_at,
                        "availability_precision": _static_availability_precision(published_at),
                        "outcome_visibility": "PREOUTCOME_VISIBLE",
                        "permitted_lanes": permitted_lanes,
                    }
                    existing = source_map.get(source_id)
                    if existing is not None and existing != canonical:
                        raise ControlPlaneError(
                            "registered_preselection_source_identity_conflict",
                            f"registered H1/H2 receipts redeclare source_id: {source_id}",
                        )
                    source_map[source_id] = canonical
    return source_map


def _h1_history_sources(member: dict[str, Any], *, history_name: str) -> dict[str, set[str]]:
    """Return the H1-declared static PDFs available for each field period."""
    if history_name == "d2_or_cost_field_history":
        history = member.get("d2_field_availability")
        if not isinstance(history, dict):
            history = member.get("cost_field_availability")
    else:
        history = member.get("annual_d3_d4_availability")
    repetitions = history.get("repetitions") if isinstance(history, dict) else history
    per_period: dict[str, set[str]] = {}
    if not isinstance(repetitions, list):
        return per_period
    for repetition in repetitions:
        if not isinstance(repetition, dict):
            continue
        period_end = repetition.get("period_end")
        if not isinstance(period_end, str) or not period_end.strip():
            continue
        evidence = repetition.get("evidence")
        source_ids = {
            item.get("source_id")
            for item in evidence if isinstance(item, dict)
            and isinstance(item.get("source_id"), str) and item["source_id"].strip()
        } if isinstance(evidence, list) else set()
        if source_ids:
            per_period[period_end] = source_ids
    return per_period


def _require_h1_cohort_projection(
    bundle: dict[str, Any], h1_payload: dict[str, Any], static_source_map: dict[str, dict[str, Any]],
) -> None:
    """Ensure the V5 root is a subset projection of its registered H1 cohort.

    The root intentionally narrows the H1 feasibility universe to a target
    plus candidate peers.  It may not manufacture a member, alter control or
    boundary identity, or attach another member's annual history.
    """
    cohort = bundle.get("cohort_snapshot")
    if not isinstance(cohort, dict):
        raise ControlPlaneError("h1_cohort_snapshot_missing", "selection bundle requires cohort_snapshot")
    if cohort.get("arena_family") != h1_payload.get("arena_family"):
        raise ControlPlaneError(
            "h1_cohort_arena_family_mismatch",
            "selection cohort arena_family must match the registered H1 cohort",
        )
    h1_members = {
        member.get("issuer_id"): member
        for member in h1_payload.get("members", []) if isinstance(member, dict)
        and isinstance(member.get("issuer_id"), str) and member["issuer_id"].strip()
    }
    members = cohort.get("members")
    if not isinstance(members, list):
        raise ControlPlaneError("h1_cohort_members_missing", "selection bundle cohort members must be a list")
    for member in members:
        if not isinstance(member, dict):
            raise ControlPlaneError("h1_cohort_member_invalid", "selection bundle cohort member must be an object")
        issuer_id = member.get("issuer_id")
        h1_member = h1_members.get(issuer_id) if isinstance(issuer_id, str) else None
        if h1_member is None:
            raise ControlPlaneError(
                "h1_cohort_member_not_declared",
                "selection cohort member is not a member of the registered H1 cohort: " + str(issuer_id),
            )
        for field in ("company_id", "issuer_id", "responsibility_unit_id", "control_group_id"):
            if member.get(field) != h1_member.get(field):
                raise ControlPlaneError(
                    "h1_cohort_member_identity_mismatch",
                    "selection cohort member identity differs from registered H1 member: " + str(issuer_id),
                )
        if member.get("boundary") != h1_member.get("boundary"):
            raise ControlPlaneError(
                "h1_cohort_member_boundary_mismatch",
                "selection cohort member boundary differs from registered H1 member: " + str(issuer_id),
            )

        carrier_sources = member.get("carrier_identity_source_ids")
        declared_carrier_sources = h1_member.get("carrier_identity_source_ids")
        if not isinstance(carrier_sources, list) or not isinstance(declared_carrier_sources, list) \
                or set(carrier_sources) != set(declared_carrier_sources):
            raise ControlPlaneError(
                "h1_cohort_member_carrier_source_mismatch",
                "selection carrier identity sources must match the registered H1 member: " + str(issuer_id),
            )

        for history_name, error_code in (
            ("d2_or_cost_field_history", "h1_cohort_member_d2_or_cost_source_mismatch"),
            ("d3_d4_field_history", "h1_cohort_member_d3_d4_source_mismatch"),
        ):
            declared = _h1_history_sources(h1_member, history_name=history_name)
            records = member.get(history_name)
            if not isinstance(records, list):
                raise ControlPlaneError(error_code, "selection history must be a list: " + str(issuer_id))
            for record in records:
                if not isinstance(record, dict):
                    raise ControlPlaneError(error_code, "selection history record must be an object: " + str(issuer_id))
                period_end = record.get("period_end")
                source_id = record.get("source_id")
                if source_id not in declared.get(period_end, set()):
                    raise ControlPlaneError(
                        error_code,
                        "selection history source must match the registered H1 member and period: " + str(issuer_id),
                    )

        source_ids = [
            *(item for item in carrier_sources if isinstance(item, str)),
            *(
                record.get("source_id") for history_name in ("d2_or_cost_field_history", "d3_d4_field_history")
                for record in member.get(history_name, []) if isinstance(record, dict)
                and isinstance(record.get("source_id"), str)
            ),
        ]
        if any(static_source_map.get(source_id, {}).get("issuer_id") != issuer_id for source_id in source_ids):
            raise ControlPlaneError(
                "h1_cohort_member_source_issuer_mismatch",
                "selection member source identity belongs to another registered issuer: " + str(issuer_id),
            )


def _resolve_preselection_provenance(conn: sqlite3.Connection, bundle: dict[str, Any]) -> None:
    """Bind one V5 root to the exact registered H1/H2 source receipts."""
    provenance = bundle.get("source_provenance")
    if not isinstance(provenance, dict):
        raise ControlPlaneError("source_provenance_missing", "selection bundle requires source_provenance")
    h1 = provenance.get("h1")
    h2 = provenance.get("h2")
    if not isinstance(h1, dict) or not isinstance(h2, dict):
        raise ControlPlaneError("source_provenance_invalid", "source_provenance requires H1 and H2 receipt snapshots")
    h1_id = _required_text(h1, "receipt_id")
    h1_version = _positive_integer(h1.get("receipt_version"), field="source_provenance.h1.receipt_version")
    h2_id = _required_text(h2, "receipt_id")
    h2_version = _positive_integer(h2.get("receipt_version"), field="source_provenance.h2.receipt_version")
    h1_row = _preselection_row(conn, h1_id, h1_version, expected_kind=H1_STATIC_COHORT_RECEIPT)
    h2_row = _preselection_row(conn, h2_id, h2_version, expected_kind=H2_ACTION_SCREEN_RECEIPT)
    if (h2_row["parent_receipt_id"], h2_row["parent_receipt_version"]) != (h1_id, h1_version):
        raise ControlPlaneError("source_provenance_parent_mismatch", "H2 receipt must be parented by the declared H1 receipt")

    if (
        h1.get("cohort_id") != h1_row["cohort_id"]
        or h1.get("curator_id") != h1_row["curator_id"]
        or _parse_time(h1.get("selection_as_of"), field="source_provenance.h1.selection_as_of")
        != _parse_time(h1_row["selection_as_of"], field="registered_h1.selection_as_of")
    ):
        raise ControlPlaneError("source_provenance_h1_snapshot_mismatch", "H1 receipt snapshot does not match the registered receipt")
    if (
        h2.get("parent_receipt_id") != h2_row["parent_receipt_id"]
        or h2.get("parent_receipt_version") != h2_row["parent_receipt_version"]
        or h2.get("screen_id") != h2_row["screen_id"]
        or _parse_time(h2.get("cutoff_at"), field="source_provenance.h2.cutoff_at")
        != _parse_time(h2_row["cutoff_at"], field="registered_h2.cutoff_at")
    ):
        raise ControlPlaneError("source_provenance_h2_snapshot_mismatch", "H2 receipt snapshot does not match the registered receipt")

    h1_payload = _loads(h1_row["payload_json"])
    h2_payload = _loads(h2_row["payload_json"])
    static_source_map = _preselection_static_source_map(h1_payload, h2_payload)
    _require_h1_cohort_projection(bundle, h1_payload, static_source_map)
    manifest = bundle.get("source_manifest")
    manifest_items = manifest if isinstance(manifest, list) else []
    for item in manifest_items:
        if not isinstance(item, dict):
            raise ControlPlaneError(
                "source_manifest_identity_invalid",
                "selection bundle source_manifest items must be objects",
            )
        source_id = item.get("source_id")
        source = static_source_map.get(source_id) if isinstance(source_id, str) else None
        if source is None:
            raise ControlPlaneError(
                "source_manifest_outside_registered_preselection_map",
                "selection bundle source_manifest must be a subset of the registered H1/H2 static source map",
            )
        mismatches = [
            field for field in _STATIC_SOURCE_IDENTITY_FIELDS
            if item.get(field) != source.get(field)
        ]
        if mismatches:
            raise ControlPlaneError(
                "source_manifest_identity_mismatch",
                "selection bundle source declaration must exactly match its registered static PDF: "
                + ", ".join(mismatches),
            )
        if item.get("source_lane") not in source["permitted_lanes"]:
            raise ControlPlaneError(
                "source_manifest_lane_not_authorized",
                "selection bundle source lane is not permitted by its registered H1/H2 receipt: "
                + str(source_id),
            )


def _event_time(payload: dict[str, Any], *, recorded_at: str | None) -> tuple[str, str]:
    effective = _parse_time(payload.get("effective_at"), field="effective_at")
    recorded = _parse_time(recorded_at or payload.get("recorded_at") or _iso(effective), field="recorded_at")
    if effective > recorded:
        raise ControlPlaneError("event_effective_after_recorded", "effective_at must not be after recorded_at")
    return _iso(effective), _iso(recorded)


def _event_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4()}"


def _validator() -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Load Slice-0 only when it has landed; never silently bypass it."""
    try:
        from scripts.judgment_selection_v5 import validate_v5_candidate
    except ModuleNotFoundError:
        try:
            from judgment_selection_v5 import validate_v5_candidate
        except ModuleNotFoundError as exc:
            raise ControlPlaneError(
                "candidate_validator_unavailable",
                "scripts.judgment_selection_v5.validate_v5_candidate is required before sealing",
            ) from exc
    return validate_v5_candidate


def _validate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ControlPlaneError("bundle_invalid", "selection bundle must be an object")
    result = _validator()(bundle)
    if not isinstance(result, dict):
        raise ControlPlaneError("candidate_validator_invalid_result", "candidate validator must return an object")
    if not isinstance(result.get("findings", []), list):
        raise ControlPlaneError("candidate_validator_invalid_result", "candidate validator findings must be a list")
    if not isinstance(result.get("valid"), bool):
        raise ControlPlaneError("candidate_validator_invalid_result", "candidate validator must return bool valid")
    if not isinstance(result.get("admission_status"), str) or not result["admission_status"].strip():
        raise ControlPlaneError("candidate_validator_invalid_result", "candidate validator must return admission_status")
    return result


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _forbid_pre_access_outcome_identity(payload: dict[str, Any], *, field: str) -> None:
    """Forbid actual sealed-outcome identities, while permitting static sources."""
    for node in _walk(payload):
        forbidden = sorted(OUTCOME_IDENTITY_FIELDS.intersection(node))
        if forbidden:
            raise ControlPlaneError(
                "outcome_inventory_before_authorization",
                f"{field} contains actual outcome identity field(s): {', '.join(forbidden)}",
            )
        lane = str(node.get("source_lane") or node.get("outcome_visibility") or "").upper()
        if lane == "OUTCOME_SEALED":
            metadata = sorted(OUTCOME_SOURCE_METADATA_FIELDS.intersection(node))
            if metadata:
                raise ControlPlaneError(
                    "outcome_inventory_before_authorization",
                    f"{field} exposes OUTCOME_SEALED metadata: {', '.join(metadata)}",
                )


def _freeze_row(conn: sqlite3.Connection, selection_freeze_id: str) -> sqlite3.Row:
    row = conn.execute(
        f"SELECT * FROM {FREEZE_TABLE} WHERE selection_freeze_id = ?",
        (selection_freeze_id,),
    ).fetchone()
    if row is None:
        raise ControlPlaneError("freeze_not_found", f"selection freeze not found: {selection_freeze_id}")
    return row


def _events(conn: sqlite3.Connection, selection_freeze_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""SELECT * FROM {EVENT_TABLE}
            WHERE selection_freeze_id = ?
            ORDER BY effective_at, recorded_at, event_id""",
        (selection_freeze_id,),
    ).fetchall()
    return [{**dict(row), "payload": _loads(row["payload_json"])} for row in rows]


def _state(conn: sqlite3.Connection, selection_freeze_id: str) -> dict[str, Any]:
    freeze = _freeze_row(conn, selection_freeze_id)
    events = _events(conn, selection_freeze_id)
    state = {
        "selection_freeze_id": selection_freeze_id,
        "candidate_id": freeze["candidate_id"],
        "episode_collision_key": freeze["episode_collision_key"],
        "research_cutoff_at": freeze["research_cutoff_at"],
        "predecessor_freeze_id": freeze["predecessor_freeze_id"],
        "sealed_at": freeze["sealed_at"],
        "authorized": False,
        "custodian_id": None,
        "terminal_state": None,
        "receipt_kinds": [],
        "resolution_status": None,
        "events": events,
    }
    for event in events:
        event_type = event["event_type"]
        if event_type == "OUTCOME_ACCESS_AUTHORIZED":
            state["authorized"] = True
            state["custodian_id"] = event["payload"]["custodian_id"]
        elif event_type == "CONTROL_RECEIPT":
            state["receipt_kinds"].append(event["payload"]["receipt_kind"])
        elif event_type == "OUTCOME_RESOLVED":
            state["resolution_status"] = event["payload"]["resolution_status"]
            state["terminal_state"] = event["payload"]["resolution_status"]
        elif event_type in TERMINAL_EVENT_TYPES:
            state["terminal_state"] = event_type
    return state


def _ensure_not_terminal(state: dict[str, Any]) -> None:
    if state["terminal_state"] is not None:
        raise ControlPlaneError(
            "freeze_terminal",
            f"{state['selection_freeze_id']} is terminal: {state['terminal_state']}",
        )


def _append_event(
    conn: sqlite3.Connection,
    *,
    selection_freeze_id: str,
    event_type: str,
    effective_at: str,
    recorded_at: str,
    actor_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    existing_result = _existing_event_result(
        conn,
        selection_freeze_id=selection_freeze_id,
        event_type=event_type,
        effective_at=effective_at,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    if existing_result is not None:
        return existing_result
    event = {
        "event_id": _event_id("V5EVT"),
        "selection_freeze_id": selection_freeze_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "recorded_at": recorded_at,
        "actor_id": actor_id,
        "idempotency_key": idempotency_key,
        "payload": payload,
    }
    conn.execute(
        f"""INSERT INTO {EVENT_TABLE} (
            event_id, selection_freeze_id, event_type, effective_at, recorded_at,
            actor_id, idempotency_key, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event["event_id"], event["selection_freeze_id"], event["event_type"],
            event["effective_at"], event["recorded_at"], event["actor_id"],
            event["idempotency_key"], _json(payload),
        ),
    )
    return {"event": event, "idempotent": False}


def _existing_event_result(
    conn: sqlite3.Connection,
    *,
    selection_freeze_id: str,
    event_type: str,
    effective_at: str,
    actor_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Return an exact replay before state checks can reject a terminal freeze."""
    payload_json = _json(payload)
    existing = conn.execute(
        f"SELECT * FROM {EVENT_TABLE} WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if existing is not None:
        comparable = {
            "selection_freeze_id": selection_freeze_id,
            "event_type": event_type,
            "effective_at": effective_at,
            "actor_id": actor_id,
            "payload_json": payload_json,
        }
        stored = {
            "selection_freeze_id": existing["selection_freeze_id"],
            "event_type": existing["event_type"],
            "effective_at": existing["effective_at"],
            "actor_id": existing["actor_id"],
            "payload_json": existing["payload_json"],
        }
        if stored != comparable:
            raise ControlPlaneError("idempotency_conflict", "idempotency key was reused with a different event")
        return {"event": {**dict(existing), "payload": _loads(existing["payload_json"])}, "idempotent": True}
    return None


def _selection_freeze_id(bundle: dict[str, Any]) -> str:
    return _required_text(bundle, "selection_freeze_id")


def seal_freeze(
    conn: sqlite3.Connection,
    bundle: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Validate and atomically freeze an admitted candidate bundle.

    A `NO_PRIMARY` or other non-admitted validator result is returned without a
    database write, so it cannot be mistaken for a sealed episode.
    """
    validation = _validate_bundle(bundle)
    if not validation["valid"] or validation["admission_status"] != ADMITTED:
        return {
            "sealed": False,
            "admission_status": validation["admission_status"],
            "findings": validation["findings"],
        }
    _resolve_preselection_provenance(conn, bundle)
    _forbid_pre_access_outcome_identity(bundle, field="selection bundle")
    freeze_id = _selection_freeze_id(bundle)
    candidate_id = _required_text(bundle, "candidate_id")
    collision_key = _required_text(bundle, "episode_collision_key")
    # Preserve the declared cutoff offset.  `DATE_ONLY` source availability is
    # compared with the cutoff *calendar date*, not the UTC date after an
    # offset conversion (which would turn a same-day +08:00 source into a
    # misleading later UTC date).
    if "research_cutoff_at" in bundle:
        raise ControlPlaneError(
            "research_cutoff_root_forbidden",
            "research_cutoff_at belongs only to time_contract",
        )
    time_contract = bundle.get("time_contract")
    if not isinstance(time_contract, dict):
        raise ControlPlaneError("time_contract_missing", "time_contract is required")
    cutoff = _required_text(time_contract, "research_cutoff_at")
    _parse_time(cutoff, field="research_cutoff_at")
    sealed_at = _iso(_parse_time(bundle.get("sealed_at"), field="sealed_at"))
    recorded = _iso(_parse_time(bundle.get("recorded_at"), field="recorded_at"))
    if recorded_at is not None and _parse_time(recorded_at, field="recorded_at") != _parse_time(
        recorded, field="bundle.recorded_at",
    ):
        raise ControlPlaneError(
            "recorded_at_mismatch",
            "recorded_at must be the canonical root bundle value",
        )
    if _parse_time(sealed_at, field="sealed_at") > _parse_time(recorded, field="recorded_at"):
        raise ControlPlaneError("seal_effective_after_recorded", "sealed_at must not be after recorded_at")
    predecessor = bundle.get("predecessor_freeze_id")
    if predecessor is not None and (not isinstance(predecessor, str) or not predecessor.strip()):
        raise ControlPlaneError("predecessor_invalid", "predecessor_freeze_id must be a non-empty string")
    predecessor = predecessor.strip() if isinstance(predecessor, str) else None
    bundle_json = _json(bundle)

    with conn:
        existing = conn.execute(
            f"SELECT * FROM {FREEZE_TABLE} WHERE selection_freeze_id = ?", (freeze_id,)
        ).fetchone()
        if existing is not None:
            if existing["bundle_json"] != bundle_json:
                raise ControlPlaneError("freeze_immutable_conflict", "selection_freeze_id already has a different bundle")
            return {"sealed": True, "selection_freeze_id": freeze_id, "idempotent": True}

        same_collision = conn.execute(
            f"SELECT selection_freeze_id FROM {FREEZE_TABLE} WHERE episode_collision_key = ?",
            (collision_key,),
        ).fetchall()
        if same_collision:
            if predecessor is None:
                raise ControlPlaneError("collision_predecessor_required", "same collision key requires a voided predecessor")
            predecessor_row = _freeze_row(conn, predecessor)
            if predecessor_row["episode_collision_key"] != collision_key:
                raise ControlPlaneError("collision_predecessor_mismatch", "predecessor must use the same collision key")
            predecessor_state = _state(conn, predecessor)
            if predecessor_state["terminal_state"] != "FREEZE_VOIDED_PRE_ACCESS":
                raise ControlPlaneError("collision_reuse_forbidden", "collision may be reused only after pre-access void")
            for row in same_collision:
                previous_state = _state(conn, row["selection_freeze_id"])
                if previous_state["terminal_state"] != "FREEZE_VOIDED_PRE_ACCESS":
                    raise ControlPlaneError("collision_reuse_forbidden", "collision already has a non-voided freeze")
        elif predecessor is not None:
            raise ControlPlaneError("predecessor_without_collision", "predecessor is allowed only for an existing collision")

        conn.execute(
            f"""INSERT INTO {FREEZE_TABLE} (
                selection_freeze_id, candidate_id, episode_collision_key,
                research_cutoff_at, predecessor_freeze_id, bundle_json,
                sealed_at, recorded_at, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                freeze_id, candidate_id, collision_key, cutoff, predecessor,
                bundle_json, sealed_at, recorded, SCHEMA_VERSION,
            ),
        )
    return {"sealed": True, "selection_freeze_id": freeze_id, "idempotent": False}


def authorize_outcome_access(
    conn: sqlite3.Connection,
    authorization: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Grant the named custodian outcome access without exposing inventory."""
    if not isinstance(authorization, dict):
        raise ControlPlaneError("authorization_invalid", "authorization must be an object")
    unexpected = sorted(set(authorization) - {
        "selection_freeze_id", "authorization_id", "custodian_id", "actor_id",
        "effective_at", "recorded_at", "idempotency_key",
    })
    if unexpected:
        raise ControlPlaneError(
            "authorization_unexpected_field",
            "authorization must not carry inventory or other outcome metadata: " + ", ".join(unexpected),
        )
    _forbid_pre_access_outcome_identity(authorization, field="authorization")
    freeze_id = _required_text(authorization, "selection_freeze_id")
    custodian_id = _required_text(authorization, "custodian_id")
    authorization_id = _required_text(authorization, "authorization_id")
    effective_at, recorded = _event_time(authorization, recorded_at=recorded_at)
    idempotency_key = str(authorization.get("idempotency_key") or f"AUTH:{authorization_id}").strip()
    if not idempotency_key:
        raise ControlPlaneError("field_missing", "idempotency_key is required")

    with conn:
        event_payload = {"authorization_id": authorization_id, "custodian_id": custodian_id}
        replay = _existing_event_result(
            conn,
            selection_freeze_id=freeze_id,
            event_type="OUTCOME_ACCESS_AUTHORIZED",
            effective_at=effective_at,
            actor_id=_required_text(authorization, "actor_id"),
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
        if replay is not None:
            return replay
        state = _state(conn, freeze_id)
        _ensure_not_terminal(state)
        if state["authorized"]:
            raise ControlPlaneError("outcome_access_already_authorized", "outcome access has already been authorized")
        sealed_bundle = _loads(_freeze_row(conn, freeze_id)["bundle_json"])
        review = sealed_bundle.get("independent_pre_outcome_review")
        firewall = sealed_bundle.get("source_firewall_receipt")
        review = review if isinstance(review, dict) else {}
        firewall = firewall if isinstance(firewall, dict) else {}
        protected_preoutcome_roles = {
            str(review.get("pre_outcome_designer_id") or "").strip(),
            str(review.get("reviewer_id") or "").strip(),
            str(firewall.get("researcher_id") or "").strip(),
        }
        protected_preoutcome_roles.discard("")
        if custodian_id in protected_preoutcome_roles:
            raise ControlPlaneError(
                "outcome_custodian_role_conflict",
                "outcome custodian must be distinct from the sealed pre-outcome designer and reviewer",
            )
        if _parse_time(effective_at, field="effective_at") < _parse_time(state["sealed_at"], field="sealed_at"):
            raise ControlPlaneError("authorization_before_seal", "outcome authorization must follow freeze seal")
        result = _append_event(
            conn,
            selection_freeze_id=freeze_id,
            event_type="OUTCOME_ACCESS_AUTHORIZED",
            effective_at=effective_at,
            recorded_at=recorded,
            actor_id=_required_text(authorization, "actor_id"),
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
    return result


def _normalize_receipt_kind(value: Any) -> str:
    kind = str(value or "").strip().upper()
    canonical = RECEIPT_KIND_ALIASES.get(kind)
    if canonical is None:
        raise ControlPlaneError("receipt_kind_invalid", f"unsupported receipt_kind: {value!r}")
    return canonical


def _inventory_is_early(inventory: Any, cutoff_at: str) -> bool:
    if not isinstance(inventory, list) or not inventory:
        raise ControlPlaneError("outcome_inventory_missing", "OUTCOME_PACKAGE requires non-empty actual_outcome_inventory")
    cutoff = _parse_time(cutoff_at, field="research_cutoff_at")
    cutoff_text = str(cutoff_at).strip()
    if cutoff_text.endswith("Z"):
        cutoff_text = f"{cutoff_text[:-1]}+00:00"
    # Keep the issuer/researcher's declared calendar date for DATE_ONLY
    # sources.  `_parse_time` rightly normalizes instants to UTC, but UTC is
    # not the calendar convention promised by a date-only publication.
    cutoff_calendar_date = datetime.fromisoformat(cutoff_text).date()
    for index, source in enumerate(inventory):
        if not isinstance(source, dict):
            raise ControlPlaneError("outcome_inventory_invalid", f"actual_outcome_inventory[{index}] must be an object")
        _required_text(source, "source_id")
        precision = str(source.get("availability_precision") or "INTRADAY").upper()
        available = source.get("source_available_at")
        if precision == "DATE_ONLY":
            if not isinstance(available, str) or len(available.strip()) != 10:
                raise ControlPlaneError("outcome_inventory_invalid", "DATE_ONLY source_available_at must be YYYY-MM-DD")
            try:
                available_date = datetime.fromisoformat(available.strip()).date()
            except ValueError as exc:
                raise ControlPlaneError("outcome_inventory_invalid", "DATE_ONLY source_available_at must be YYYY-MM-DD") from exc
            if available_date <= cutoff_calendar_date:
                return True
        elif precision == "INTRADAY":
            if _parse_time(available, field="source_available_at") <= cutoff:
                return True
        else:
            raise ControlPlaneError("outcome_inventory_invalid", "availability_precision must be INTRADAY or DATE_ONLY")
    return False


def append_control_receipt(
    conn: sqlite3.Connection,
    receipt: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Append a narrowly enumerated authorized outcome receipt or breach."""
    if not isinstance(receipt, dict):
        raise ControlPlaneError("receipt_invalid", "receipt must be an object")
    freeze_id = _required_text(receipt, "selection_freeze_id")
    receipt_id = _required_text(receipt, "receipt_id")
    kind = _normalize_receipt_kind(receipt.get("receipt_kind"))
    effective_at, recorded = _event_time(receipt, recorded_at=recorded_at)
    actor_id = _required_text(receipt, "actor_id")
    idempotency_key = str(receipt.get("idempotency_key") or f"RECEIPT:{receipt_id}").strip()
    if not idempotency_key:
        raise ControlPlaneError("field_missing", "idempotency_key is required")
    payload = receipt.get("payload") or {}
    if not isinstance(payload, dict):
        raise ControlPlaneError("receipt_payload_invalid", "receipt payload must be an object")
    if kind not in {"OUTCOME_PACKAGE", "PIT_ACCESS_BREACH"} and any(
        name in payload for name in OUTCOME_IDENTITY_FIELDS
    ):
        raise ControlPlaneError(
            "outcome_inventory_receipt_kind_invalid",
            "actual outcome inventory belongs only in the custodian package receipt",
        )

    with conn:
        state = _state(conn, freeze_id)
        if kind == "PIT_ACCESS_BREACH":
            event_payload = {"receipt_id": receipt_id, "receipt_kind": kind, "detail": payload}
            replay = _existing_event_result(
                conn,
                selection_freeze_id=freeze_id,
                event_type="PIT_ACCESS_BREACH",
                effective_at=effective_at,
                actor_id=actor_id,
                idempotency_key=idempotency_key,
                payload=event_payload,
            )
            if replay is not None:
                return replay
            _ensure_not_terminal(state)
            result = _append_event(
                conn,
                selection_freeze_id=freeze_id,
                event_type="PIT_ACCESS_BREACH",
                effective_at=effective_at,
                recorded_at=recorded,
                actor_id=actor_id,
                idempotency_key=idempotency_key,
                payload=event_payload,
            )
            return result
        inventory_is_early = False
        if kind == "OUTCOME_PACKAGE" and state["authorized"]:
            inventory_is_early = _inventory_is_early(
                payload.get("actual_outcome_inventory"), state["research_cutoff_at"],
            )
        event_type = "EXPOSURE_EXCLUDED" if inventory_is_early else "CONTROL_RECEIPT"
        event_payload = (
            {"receipt_id": receipt_id, "reason": "PRIMARY_OUTCOME_SOURCE_NOT_STRICTLY_POST_CUTOFF"}
            if inventory_is_early
            else {"receipt_id": receipt_id, "receipt_kind": kind, "detail": payload}
        )
        replay = _existing_event_result(
            conn,
            selection_freeze_id=freeze_id,
            event_type=event_type,
            effective_at=effective_at,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
        if replay is not None:
            return replay
        _ensure_not_terminal(state)
        if not state["authorized"]:
            raise ControlPlaneError("outcome_access_not_authorized", "outcome access must be authorized before a receipt")
        if kind in {"OUTCOME_PACKAGE", "OUTCOME_READER", "OUTCOME_EXTRACTION", "MISSING_CELL"} and actor_id != state["custodian_id"]:
            raise ControlPlaneError(
                "custodian_mismatch",
                "only the authorized custodian can package, read, extract, or mark missing outcome data",
            )
        if _parse_time(effective_at, field="effective_at") < _parse_time(
            state["events"][-1]["effective_at"], field="previous_effective_at",
        ):
            raise ControlPlaneError("receipt_backdated", "receipt cannot predate the prior control event")
        if kind == "OUTCOME_PACKAGE":
            if "OUTCOME_PACKAGE" in state["receipt_kinds"]:
                raise ControlPlaneError(
                    "outcome_package_already_registered",
                    "each freeze permits exactly one bounded OUTCOME_PACKAGE before reading or extraction",
                )
            if actor_id != state["custodian_id"]:
                raise ControlPlaneError("custodian_mismatch", "only the authorized custodian can register outcome inventory")
            if inventory_is_early:
                return _append_event(
                    conn,
                    selection_freeze_id=freeze_id,
                    event_type="EXPOSURE_EXCLUDED",
                    effective_at=effective_at,
                    recorded_at=recorded,
                    actor_id=actor_id,
                    idempotency_key=idempotency_key,
                    payload=event_payload,
                )
        elif kind == "OUTCOME_READER" and "OUTCOME_PACKAGE" not in state["receipt_kinds"]:
            raise ControlPlaneError("receipt_order_invalid", "OUTCOME_READER requires OUTCOME_PACKAGE")
        elif kind == "OUTCOME_EXTRACTION" and "OUTCOME_READER" not in state["receipt_kinds"]:
            raise ControlPlaneError("receipt_order_invalid", "OUTCOME_EXTRACTION requires OUTCOME_READER")
        elif kind == "MISSING_CELL" and "OUTCOME_PACKAGE" not in state["receipt_kinds"]:
            raise ControlPlaneError("receipt_order_invalid", "MISSING_CELL requires OUTCOME_PACKAGE")
        result = _append_event(
            conn,
            selection_freeze_id=freeze_id,
            event_type="CONTROL_RECEIPT",
            effective_at=effective_at,
            recorded_at=recorded,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
    return result


def resolve(
    conn: sqlite3.Connection,
    resolution: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Record only a status recomputed from the sealed raw-matrix contract."""
    if not isinstance(resolution, dict):
        raise ControlPlaneError("resolution_invalid", "resolution must be an object")
    freeze_id = _required_text(resolution, "selection_freeze_id")
    resolution_id = _required_text(resolution, "resolution_id")
    if "resolution_status" in resolution:
        raise ControlPlaneError(
            "caller_resolution_status_forbidden",
            "resolution_status is derived from outcome_receipts and must not be supplied by the caller",
        )
    effective_at, recorded = _event_time(resolution, recorded_at=recorded_at)
    actor_id = _required_text(resolution, "actor_id")
    idempotency_key = str(resolution.get("idempotency_key") or f"RESOLUTION:{resolution_id}").strip()
    if not idempotency_key:
        raise ControlPlaneError("field_missing", "idempotency_key is required")

    with conn:
        state = _state(conn, freeze_id)
        if not state["authorized"]:
            raise ControlPlaneError("outcome_access_not_authorized", "outcome access must be authorized before resolution")
        if actor_id != state["custodian_id"]:
            raise ControlPlaneError(
                "custodian_mismatch",
                "only the authorized custodian may submit raw outcome receipts for resolution",
            )
        receipts = set(state["receipt_kinds"])
        if "MISSING_CELL" not in receipts and "OUTCOME_EXTRACTION" not in receipts:
            raise ControlPlaneError("outcome_extraction_missing", "resolution requires OUTCOME_EXTRACTION or MISSING_CELL")
        bundle = _loads(_freeze_row(conn, freeze_id)["bundle_json"])
        _require_registered_primary_sources(
            bundle,
            resolution.get("outcome_receipts"),
            registered_source_ids=_registered_outcome_source_ids(state),
        )
        status_value, reconstruction_findings = _derive_outcome_resolution(
            bundle, resolution.get("outcome_receipts"), authorized_custodian_id=state["custodian_id"],
        )
        if "MISSING_CELL" in receipts and status_value != "UNKNOWN":
            raise ControlPlaneError("missing_cell_requires_unknown", "MISSING_CELL can resolve only as UNKNOWN")
        event_type = "EXPOSURE_EXCLUDED" if status_value == "EXPOSURE_EXCLUDED" else "OUTCOME_RESOLVED"
        event_payload = {
            "resolution_id": resolution_id,
            "resolution_status": status_value,
            "reconstruction_findings": reconstruction_findings,
        }
        replay = _existing_event_result(
            conn,
            selection_freeze_id=freeze_id,
            event_type=event_type,
            effective_at=effective_at,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
        if replay is not None:
            return replay
        _ensure_not_terminal(state)
        previous = state["events"][-1]["effective_at"]
        if _parse_time(effective_at, field="effective_at") < _parse_time(previous, field="previous_effective_at"):
            raise ControlPlaneError("resolution_backdated", "resolution cannot predate the prior control event")
        result = _append_event(
            conn,
            selection_freeze_id=freeze_id,
            event_type=event_type,
            effective_at=effective_at,
            recorded_at=recorded,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
    return result


def void_pre_access_freeze(
    conn: sqlite3.Connection,
    selection_freeze_id: str,
    void_receipt: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Terminally void a sealed freeze before any outcome access."""
    if not isinstance(void_receipt, dict):
        raise ControlPlaneError("void_receipt_invalid", "void receipt must be an object")
    freeze_id = str(selection_freeze_id or void_receipt.get("selection_freeze_id") or "").strip()
    if not freeze_id:
        raise ControlPlaneError("field_missing", "selection_freeze_id is required")
    if void_receipt.get("selection_freeze_id") not in (None, freeze_id):
        raise ControlPlaneError("void_receipt_mismatch", "void receipt freeze id does not match argument")
    receipt_id = _required_text(void_receipt, "receipt_id")
    effective_at, recorded = _event_time(void_receipt, recorded_at=recorded_at)
    actor_id = _required_text(void_receipt, "actor_id")
    idempotency_key = str(void_receipt.get("idempotency_key") or f"VOID:{receipt_id}").strip()
    if not idempotency_key:
        raise ControlPlaneError("field_missing", "idempotency_key is required")
    with conn:
        event_payload = {"receipt_id": receipt_id}
        replay = _existing_event_result(
            conn,
            selection_freeze_id=freeze_id,
            event_type="FREEZE_VOIDED_PRE_ACCESS",
            effective_at=effective_at,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
        if replay is not None:
            return replay
        state = _state(conn, freeze_id)
        _ensure_not_terminal(state)
        if state["authorized"] or state["receipt_kinds"]:
            raise ControlPlaneError("freeze_accessed_cannot_void", "only a pre-access freeze may be voided")
        if _parse_time(effective_at, field="effective_at") < _parse_time(state["sealed_at"], field="sealed_at"):
            raise ControlPlaneError("void_before_seal", "void cannot predate freeze seal")
        result = _append_event(
            conn,
            selection_freeze_id=freeze_id,
            event_type="FREEZE_VOIDED_PRE_ACCESS",
            effective_at=effective_at,
            recorded_at=recorded,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
    return result


def status(conn: sqlite3.Connection, selection_freeze_id: str) -> dict[str, Any]:
    """Return the replayed control state; this does not expose bundle outcomes."""
    state = _state(conn, selection_freeze_id)
    return {
        key: value
        for key, value in state.items()
        if key not in {"events"}
    } | {"event_count": len(state["events"])}


# Readable aliases for callers that use the longer design-document names.
seal_selection_freeze = seal_freeze
resolve_outcome = resolve


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControlPlaneError("json_read_failed", f"cannot read JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise ControlPlaneError("json_object_required", f"JSON document must be an object: {path}")
    return payload


def _print(result: dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=(
        "init", "register-h1-receipt", "register-h2-receipt", "seal-freeze",
        "authorize-outcome-access", "append-control-receipt", "resolve",
        "void-pre-access-freeze", "status",
    ))
    parser.add_argument("--db", required=True)
    parser.add_argument("--bundle")
    parser.add_argument("--authorization")
    parser.add_argument("--receipt")
    parser.add_argument("--resolution")
    parser.add_argument("--freeze-id")
    parser.add_argument("--recorded-at")
    args = parser.parse_args(argv)
    conn = connect(args.db)
    try:
        if args.command == "init":
            initialize(conn)
            _print({"initialized": True, "tables": [PRESELECTION_RECEIPT_TABLE, FREEZE_TABLE, EVENT_TABLE]})
        elif args.command == "register-h1-receipt":
            _print(register_h1_static_cohort_receipt(conn, _read_json(_required_cli(args.receipt, "--receipt"))))
        elif args.command == "register-h2-receipt":
            _print(register_h2_action_screen_receipt(conn, _read_json(_required_cli(args.receipt, "--receipt"))))
        elif args.command == "seal-freeze":
            _print(seal_freeze(conn, _read_json(_required_cli(args.bundle, "--bundle")), recorded_at=args.recorded_at))
        elif args.command == "authorize-outcome-access":
            _print(authorize_outcome_access(conn, _read_json(_required_cli(args.authorization, "--authorization")), recorded_at=args.recorded_at))
        elif args.command == "append-control-receipt":
            _print(append_control_receipt(conn, _read_json(_required_cli(args.receipt, "--receipt")), recorded_at=args.recorded_at))
        elif args.command == "resolve":
            _print(resolve(conn, _read_json(_required_cli(args.resolution, "--resolution")), recorded_at=args.recorded_at))
        elif args.command == "void-pre-access-freeze":
            _print(void_pre_access_freeze(conn, _required_cli(args.freeze_id, "--freeze-id"), _read_json(_required_cli(args.receipt, "--receipt")), recorded_at=args.recorded_at))
        else:
            _print(status(conn, _required_cli(args.freeze_id, "--freeze-id")))
    except ControlPlaneError as exc:
        print(json.dumps({"error": exc.code, "detail": exc.detail}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        conn.close()
    return 0


def _required_cli(value: str | None, name: str) -> str:
    if not value:
        raise ControlPlaneError("cli_argument_missing", f"{name} is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
