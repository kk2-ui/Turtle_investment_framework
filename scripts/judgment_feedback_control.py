#!/usr/bin/env python3
"""Persistent control plane for frozen judgment-feedback claims.

This module intentionally does not decide a company outcome, diagnose a
mechanism, or rewrite a frozen prediction.  It registers already-frozen
claim/stage contracts, keeps an append-only control-event history, and derives
the due inbox from that history.  Outcome acquisition, extraction, settlement,
feedback and learning remain adapters to their respective modules.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "judgment-feedback-control.v1"
REGISTRATION_SCHEMA_VERSION = "judgment-feedback-control-registration.v1"
TIME_STATES = {"WAITING", "DUE", "OVERDUE", "CLOSED"}
EVIDENCE_STATES = {"EMPTY", "ACQUIRING", "BLOCKED", "PACKAGE_READY", "READ_ATTESTED", "EXTRACTED"}
SETTLEMENT_STATES = {"UNSETTLED", "A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC", "MEASUREMENT_MISMATCH"}
LEARNING_STATES = {"NONE", "DIAGNOSIS_PENDING", "NOTE_READY", "APPLICATION_PENDING", "APPLIED", "REPLICATION_PENDING", "CLOSED"}
SETTLEMENT_POLICIES = {"INITIAL_DISCLOSURE", "LATEST_OFFICIAL_AS_OF_EVALUATION"}
EVENT_TYPES = {
    "CLAIM_REGISTERED",
    "ACQUISITION_STARTED",
    "ACQUISITION_BLOCKED",
    "OUTCOME_PACKAGE_READY",
    "READ_ATTESTED",
    "OUTCOME_EXTRACTED",
    "CLAIM_SETTLED",
    "MEASUREMENT_MISMATCH",
    "OUTCOME_EXPOSURE_BREACH",
    "DIAGNOSIS_ACCEPTED",
    "LEARNING_NOTE_READY",
    "LEARNING_APPLIED",
    "REPLICATION_ACCEPTED",
    "CLOSED",
}
EPISTEMIC_FAILURE_LOCI = {"STATE", "DECISION", "MEASUREMENT", "MECHANISM", "TRANSMISSION", "ENVIRONMENT"}
DELIVERY_ROOT_CAUSES = {"DATA_COVERAGE", "ACQUISITION_MODULE", "REASONING", "MODEL", "WRITING"}
OUTCOME_EVENTS = {"CLAIM_SETTLED", "MEASUREMENT_MISMATCH"}


class ControlPlaneError(ValueError):
    """A business-rule failure that callers can present without a traceback."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: Any, *, field: str, allow_date: bool = False) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError("time_missing", f"{field} is required")
    candidate = value.strip()
    if allow_date and len(candidate) == 10:
        candidate = f"{candidate}T00:00:00+00:00"
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ControlPlaneError("time_invalid", f"{field} must be ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ControlPlaneError("time_timezone_missing", f"{field} must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError("field_missing", f"{field} is required")
    return value.strip()


def _reference_path(reference: str) -> Path:
    return Path(reference.split("#", 1)[0]).expanduser()


def _require_artifact(reference: str, *, field: str) -> str:
    text = _required_text({field: reference}, field)
    if not _reference_path(text).is_file():
        raise ControlPlaneError("artifact_missing", f"{field} does not resolve to a file: {text}")
    return text


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads(value: str) -> Any:
    return json.loads(value)


def _feedback_item_id(episode_id: str, claim_id: str, stage_id: str) -> str:
    return f"FBI:{episode_id}:{claim_id}:{stage_id}"


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS judgment_feedback_claims (
          feedback_item_id TEXT PRIMARY KEY,
          episode_id TEXT NOT NULL,
          claim_id TEXT NOT NULL,
          stage_id TEXT NOT NULL,
          company_id TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          frozen_at TEXT NOT NULL,
          eligible_at TEXT NOT NULL,
          overdue_at TEXT,
          settlement_version_policy TEXT NOT NULL,
          frozen_artifact_ref TEXT NOT NULL,
          source_contract_ref TEXT NOT NULL,
          measurement_contract_ref TEXT NOT NULL,
          registered_at TEXT NOT NULL,
          UNIQUE (episode_id, claim_id, stage_id)
        );
        CREATE TABLE IF NOT EXISTS judgment_feedback_events (
          event_id TEXT PRIMARY KEY,
          feedback_item_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          effective_at TEXT NOT NULL,
          recorded_at TEXT NOT NULL,
          actor_role TEXT NOT NULL,
          actor_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL UNIQUE,
          artifact_refs_json TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          FOREIGN KEY (feedback_item_id) REFERENCES judgment_feedback_claims(feedback_item_id)
        );
        CREATE INDEX IF NOT EXISTS idx_judgment_feedback_events_item_time
          ON judgment_feedback_events(feedback_item_id, effective_at, recorded_at);
        """
    )
    conn.commit()


def _claim_fields(item: dict[str, Any], *, manifest: dict[str, Any], registered_at: str) -> dict[str, str | None]:
    episode_id = _required_text(item, "episode_id") if item.get("episode_id") else _required_text(manifest, "episode_id")
    company_id = _required_text(item, "company_id") if item.get("company_id") else _required_text(manifest, "company_id")
    claim_id = _required_text(item, "claim_id")
    stage_id = _required_text(item, "stage_id")
    source_kind = _required_text(item, "source_kind")
    source_ref = _required_text(item, "source_ref")
    frozen_at = _iso(_parse_time(item.get("frozen_at") or manifest.get("frozen_at"), field="frozen_at"))
    eligible_at = _iso(_parse_time(item.get("eligible_at"), field="eligible_at"))
    overdue_raw = item.get("overdue_at")
    overdue_at = _iso(_parse_time(overdue_raw, field="overdue_at")) if overdue_raw else None
    if _parse_time(eligible_at, field="eligible_at") < _parse_time(frozen_at, field="frozen_at"):
        raise ControlPlaneError("eligible_before_freeze", "eligible_at cannot precede frozen_at")
    if overdue_at and _parse_time(overdue_at, field="overdue_at") <= _parse_time(eligible_at, field="eligible_at"):
        raise ControlPlaneError("overdue_before_eligible", "overdue_at must be after eligible_at")
    policy = _required_text(item, "settlement_version_policy").upper()
    if policy not in SETTLEMENT_POLICIES:
        raise ControlPlaneError("settlement_version_policy_invalid", f"unsupported settlement_version_policy: {policy}")
    return {
        "feedback_item_id": _feedback_item_id(episode_id, claim_id, stage_id),
        "episode_id": episode_id,
        "claim_id": claim_id,
        "stage_id": stage_id,
        "company_id": company_id,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "frozen_at": frozen_at,
        "eligible_at": eligible_at,
        "overdue_at": overdue_at,
        "settlement_version_policy": policy,
        "frozen_artifact_ref": _require_artifact(_required_text(item, "frozen_artifact_ref"), field="frozen_artifact_ref"),
        "source_contract_ref": _require_artifact(_required_text(item, "source_contract_ref"), field="source_contract_ref"),
        "measurement_contract_ref": _require_artifact(_required_text(item, "measurement_contract_ref"), field="measurement_contract_ref"),
        "registered_at": registered_at,
    }


def _expand_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept only explicit structured stages; never infer a contract from Markdown."""
    direct = manifest.get("feedback_items")
    if isinstance(direct, list):
        return [deepcopy(item) for item in direct]
    claims = manifest.get("claims")
    if not isinstance(claims, list):
        raise ControlPlaneError("feedback_items_missing", "registration requires feedback_items or claims[].stages")
    expanded: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ControlPlaneError("claim_invalid", "each claims entry must be an object")
        claim_id = _required_text(claim, "claim_id")
        stages = claim.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ControlPlaneError("claim_stages_missing", f"claim {claim_id} requires stages")
        for stage in stages:
            if not isinstance(stage, dict):
                raise ControlPlaneError("stage_invalid", f"claim {claim_id} stage must be an object")
            row = deepcopy(stage)
            row["claim_id"] = claim_id
            for shared in ("episode_id", "company_id", "frozen_at"):
                if shared not in row and shared in claim:
                    row[shared] = claim[shared]
            expanded.append(row)
    return expanded


def register_manifest(conn: sqlite3.Connection, manifest: dict[str, Any], *, registered_at: str | None = None) -> dict[str, Any]:
    if manifest.get("schema_version") != REGISTRATION_SCHEMA_VERSION:
        raise ControlPlaneError("registration_schema_invalid", f"expected schema_version {REGISTRATION_SCHEMA_VERSION}")
    registered_at = _iso(_parse_time(registered_at or _now(), field="registered_at"))
    rows = [_claim_fields(item, manifest=manifest, registered_at=registered_at) for item in _expand_manifest(manifest)]
    if not rows:
        raise ControlPlaneError("feedback_items_empty", "registration requires at least one feedback item")
    seen = {row["feedback_item_id"] for row in rows}
    if len(seen) != len(rows):
        raise ControlPlaneError("feedback_item_duplicate", "one manifest cannot register the same episode/claim/stage twice")
    results: list[dict[str, Any]] = []
    columns = tuple(rows[0]) if rows else ()
    with conn:
        for row in rows:
            existing = conn.execute("SELECT * FROM judgment_feedback_claims WHERE feedback_item_id = ?", (row["feedback_item_id"],)).fetchone()
            if existing:
                comparable = {column: existing[column] for column in columns if column != "registered_at"}
                intended = {column: row[column] for column in columns if column != "registered_at"}
                if comparable != intended:
                    raise ControlPlaneError("claim_registration_conflict", f"immutable claim differs: {row['feedback_item_id']}")
                results.append({"feedback_item_id": row["feedback_item_id"], "registered": False, "idempotent": True})
                continue
            conn.execute(
                f"INSERT INTO judgment_feedback_claims ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
            conn.execute(
                """INSERT INTO judgment_feedback_events
                   (event_id, feedback_item_id, event_type, effective_at, recorded_at, actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
                   VALUES (?, ?, 'CLAIM_REGISTERED', ?, ?, 'SYSTEM', 'judgment_feedback_control', ?, ?, ?)""",
                (
                    f"JFE:REGISTERED:{row['feedback_item_id']}",
                    row["feedback_item_id"],
                    row["frozen_at"],
                    registered_at,
                    f"CLAIM_REGISTERED:{row['feedback_item_id']}",
                    _json([row["frozen_artifact_ref"], row["source_contract_ref"], row["measurement_contract_ref"]]),
                    _json({"registration_schema_version": REGISTRATION_SCHEMA_VERSION}),
                ),
            )
            results.append({"feedback_item_id": row["feedback_item_id"], "registered": True, "idempotent": False})
    return {"schema_version": SCHEMA_VERSION, "registered": results}


def _events(conn: sqlite3.Connection, feedback_item_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM judgment_feedback_events WHERE feedback_item_id = ? ORDER BY effective_at, recorded_at, event_id",
        (feedback_item_id,),
    ).fetchall()
    return [{**dict(row), "artifact_refs": _loads(row["artifact_refs_json"]), "payload": _loads(row["payload_json"])} for row in rows]


def _claim(conn: sqlite3.Connection, feedback_item_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM judgment_feedback_claims WHERE feedback_item_id = ?", (feedback_item_id,)).fetchone()
    if not row:
        raise ControlPlaneError("feedback_item_unknown", f"unknown feedback_item_id: {feedback_item_id}")
    return dict(row)


def _event_exists(events: Iterable[dict[str, Any]], event_type: str) -> bool:
    return any(event["event_type"] == event_type for event in events)


def _last(events: Iterable[dict[str, Any]], event_types: set[str]) -> dict[str, Any] | None:
    found = [event for event in events if event["event_type"] in event_types]
    return found[-1] if found else None


def _last_effective_no_later_than(
    events: Iterable[dict[str, Any]], event_types: set[str], effective_at: datetime,
) -> dict[str, Any] | None:
    found = [
        event for event in events
        if event["event_type"] in event_types
        and _parse_time(event["effective_at"], field="prior_event.effective_at") <= effective_at
    ]
    return found[-1] if found else None


def _settlement_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["event_type"] in OUTCOME_EVENTS]


def _event_by_id(events: Iterable[dict[str, Any]], event_id: str) -> dict[str, Any] | None:
    return next((event for event in events if event["event_id"] == event_id), None)


def _validate_diagnosis(payload: dict[str, Any]) -> None:
    locus = _required_text(payload, "epistemic_failure_locus").upper()
    root = _required_text(payload, "delivery_root_cause").upper()
    if locus not in EPISTEMIC_FAILURE_LOCI:
        raise ControlPlaneError("epistemic_failure_locus_invalid", f"unknown epistemic_failure_locus: {locus}")
    if root not in DELIVERY_ROOT_CAUSES:
        raise ControlPlaneError("delivery_root_cause_invalid", f"unknown delivery_root_cause: {root}")
    for field in ("economic_impact", "missing_facts", "prohibited_assumptions", "executable_remediation", "acceptance_criteria"):
        _required_text(payload, field)


def _validate_learning_application(claim: dict[str, Any], payload: dict[str, Any], *, effective_at: datetime) -> None:
    scope = _required_text(payload, "application_scope").upper()
    if scope not in {"COMPANY_FOLLOWUP", "METHOD_TRANSFER"}:
        raise ControlPlaneError("application_scope_invalid", f"unknown application_scope: {scope}")
    target_episode_id = _required_text(payload, "target_episode_id")
    target_company_id = _required_text(payload, "target_company_id")
    target_artifact = _require_artifact(_required_text(payload, "target_frozen_artifact_ref"), field="target_frozen_artifact_ref")
    target_frozen_at = _parse_time(payload.get("target_frozen_at"), field="target_frozen_at")
    if target_frozen_at > effective_at:
        raise ControlPlaneError("learning_target_not_frozen", f"target frozen artifact is later than learning application: {target_artifact}")
    _required_text(payload, "changed_field_ref")
    _required_text(payload, "before_method_meaning")
    _required_text(payload, "after_method_meaning")
    _required_text(payload, "change_reason")
    reviewer = _required_text(payload, "reviewer_id")
    target_author = _required_text(payload, "target_author_id")
    if reviewer == target_author:
        raise ControlPlaneError("reviewer_not_independent", "reviewer_id must differ from target_author_id")
    if _required_text(payload, "reviewer_acceptance").upper() != "ACCEPTED":
        raise ControlPlaneError("reviewer_acceptance_missing", "reviewer_acceptance must be ACCEPTED")
    if scope == "METHOD_TRANSFER" and target_company_id == claim["company_id"]:
        raise ControlPlaneError("method_transfer_same_company", "METHOD_TRANSFER requires a different company")
    if target_episode_id == claim["episode_id"] and scope == "METHOD_TRANSFER":
        raise ControlPlaneError("method_transfer_same_episode", "METHOD_TRANSFER requires a different episode")


def _validate_transition(claim: dict[str, Any], events: list[dict[str, Any]], event: dict[str, Any]) -> None:
    event_type = event["event_type"]
    effective_at = _parse_time(event["effective_at"], field="effective_at")
    eligible_at = _parse_time(claim["eligible_at"], field="eligible_at")
    payload = event["payload"]
    if event_type not in EVENT_TYPES:
        raise ControlPlaneError("event_type_invalid", f"unsupported event_type: {event_type}")
    if event_type == "CLAIM_REGISTERED":
        raise ControlPlaneError("claim_registered_via_manifest_only", "CLAIM_REGISTERED is created only by register-experiment")
    if effective_at < _parse_time(claim["frozen_at"], field="frozen_at"):
        raise ControlPlaneError("event_before_freeze", f"{event_type} cannot predate the frozen claim")
    if event_type in {"ACQUISITION_STARTED", "ACQUISITION_BLOCKED", "OUTCOME_PACKAGE_READY", "READ_ATTESTED", "OUTCOME_EXTRACTED", "CLAIM_SETTLED", "MEASUREMENT_MISMATCH"} and effective_at < eligible_at:
        raise ControlPlaneError("outcome_before_eligible", f"{event_type} cannot be recorded before eligible_at")
    if _event_exists(events, "CLOSED"):
        raise ControlPlaneError("claim_closed", "closed feedback items do not accept new events")
    if event_type == "OUTCOME_PACKAGE_READY" and not _last_effective_no_later_than(events, {"ACQUISITION_STARTED"}, effective_at):
        raise ControlPlaneError("acquisition_required", "OUTCOME_PACKAGE_READY requires ACQUISITION_STARTED")
    if event_type == "READ_ATTESTED" and not _last_effective_no_later_than(events, {"OUTCOME_PACKAGE_READY"}, effective_at):
        raise ControlPlaneError("outcome_package_required", "READ_ATTESTED requires OUTCOME_PACKAGE_READY")
    if event_type == "OUTCOME_EXTRACTED" and not _last_effective_no_later_than(events, {"READ_ATTESTED"}, effective_at):
        raise ControlPlaneError("reader_attestation_required", "OUTCOME_EXTRACTED requires READ_ATTESTED")
    if event_type in OUTCOME_EVENTS:
        if not _last_effective_no_later_than(events, {"OUTCOME_EXTRACTED"}, effective_at):
            raise ControlPlaneError("outcome_extraction_required", f"{event_type} requires OUTCOME_EXTRACTED")
        previous = _settlement_events(events)
        policy = claim["settlement_version_policy"]
        if policy == "INITIAL_DISCLOSURE" and previous:
            raise ControlPlaneError("initial_settlement_already_recorded", "INITIAL_DISCLOSURE accepts only one settlement")
        version = payload.get("settlement_version")
        if policy == "LATEST_OFFICIAL_AS_OF_EVALUATION":
            if not isinstance(version, int) or version < 1:
                raise ControlPlaneError("settlement_version_missing", "LATEST_OFFICIAL_AS_OF_EVALUATION requires integer settlement_version")
            if version != len(previous) + 1:
                raise ControlPlaneError("settlement_version_nonsequential", "settlement_version must increase by one")
            if version > 1 and payload.get("supersedes_event_id") != previous[-1]["event_id"]:
                raise ControlPlaneError("settlement_supersedes_missing", "later settlement must reference prior settlement event")
        if event_type == "CLAIM_SETTLED":
            verdict = _required_text(payload, "settlement_verdict").upper()
            if verdict not in SETTLEMENT_STATES - {"UNSETTLED", "MEASUREMENT_MISMATCH"}:
                raise ControlPlaneError("settlement_verdict_invalid", f"unsupported settlement_verdict: {verdict}")
    if event_type == "DIAGNOSIS_ACCEPTED":
        settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, effective_at)
        if not settlement:
            raise ControlPlaneError("settlement_required", "DIAGNOSIS_ACCEPTED requires a settlement")
        if payload.get("settlement_event_id") != settlement["event_id"]:
            raise ControlPlaneError("diagnosis_settlement_link_invalid", "diagnosis must bind the latest settlement event")
        _validate_diagnosis(payload)
    if event_type == "LEARNING_NOTE_READY":
        if _event_exists(events, "OUTCOME_EXPOSURE_BREACH"):
            raise ControlPlaneError("learning_blocked_by_exposure_breach", "outcome exposure breach blocks learning")
        diagnosis = _last_effective_no_later_than(events, {"DIAGNOSIS_ACCEPTED"}, effective_at)
        if not diagnosis or payload.get("diagnosis_event_id") != diagnosis["event_id"]:
            raise ControlPlaneError("diagnosis_required", "LEARNING_NOTE_READY requires the accepted diagnosis")
        latest_settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, effective_at)
        if not latest_settlement or diagnosis["payload"].get("settlement_event_id") != latest_settlement["event_id"]:
            raise ControlPlaneError("diagnosis_stale_for_settlement", "LEARNING_NOTE_READY requires a diagnosis of the latest settlement version")
        state = _derived_states(claim, events)["settlement_state"]
        if state in {"NOT_DIAGNOSTIC", "MEASUREMENT_MISMATCH", "UNSETTLED"}:
            raise ControlPlaneError("learning_not_diagnostic", "NOT_DIAGNOSTIC or MEASUREMENT_MISMATCH cannot create method learning")
        _require_artifact(_required_text(payload, "learning_note_ref"), field="learning_note_ref")
    if event_type == "LEARNING_APPLIED":
        if _event_exists(events, "OUTCOME_EXPOSURE_BREACH"):
            raise ControlPlaneError("learning_blocked_by_exposure_breach", "outcome exposure breach blocks learning")
        note = _last_effective_no_later_than(events, {"LEARNING_NOTE_READY"}, effective_at)
        if not note or payload.get("learning_note_event_id") != note["event_id"]:
            raise ControlPlaneError("learning_note_required", "LEARNING_APPLIED requires the learning note event")
        diagnosis = _event_by_id(events, str(note["payload"].get("diagnosis_event_id") or ""))
        latest_settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, effective_at)
        if not diagnosis or not latest_settlement or diagnosis["payload"].get("settlement_event_id") != latest_settlement["event_id"]:
            raise ControlPlaneError("learning_note_stale_for_settlement", "LEARNING_APPLIED requires a note on the latest settlement version")
        _validate_learning_application(claim, payload, effective_at=effective_at)
    if event_type == "REPLICATION_ACCEPTED":
        application = _last_effective_no_later_than(events, {"LEARNING_APPLIED"}, effective_at)
        if not application or payload.get("learning_application_event_id") != application["event_id"]:
            raise ControlPlaneError("learning_application_required", "REPLICATION_ACCEPTED requires a learning application")
        _required_text(payload, "replication_settlement_event_id")
        _required_text(payload, "reviewer_id")
        if _required_text(payload, "reviewer_acceptance").upper() != "ACCEPTED":
            raise ControlPlaneError("reviewer_acceptance_missing", "reviewer_acceptance must be ACCEPTED")
    if event_type == "CLOSED":
        if not (_last_effective_no_later_than(events, OUTCOME_EVENTS | {"OUTCOME_EXPOSURE_BREACH"}, effective_at)):
            raise ControlPlaneError("close_requires_outcome_or_breach", "CLOSED requires an outcome settlement or an exposure breach")
        _required_text(payload, "closure_reason")


def append_event(conn: sqlite3.Connection, event: dict[str, Any], *, recorded_at: str | None = None) -> dict[str, Any]:
    feedback_item_id = _required_text(event, "feedback_item_id")
    event_type = _required_text(event, "event_type").upper()
    effective_at = _iso(_parse_time(event.get("effective_at"), field="effective_at"))
    actor_role = _required_text(event, "actor_role")
    actor_id = _required_text(event, "actor_id")
    idempotency_key = _required_text(event, "idempotency_key")
    artifact_refs = event.get("artifact_refs", [])
    payload = event.get("payload", {})
    if not isinstance(artifact_refs, list):
        raise ControlPlaneError("artifact_refs_invalid", "artifact_refs must be a list")
    if not isinstance(payload, dict):
        raise ControlPlaneError("payload_invalid", "payload must be an object")
    event_id = str(event.get("event_id") or f"JFE:{uuid.uuid4()}")
    record = {
        "event_id": event_id,
        "feedback_item_id": feedback_item_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "recorded_at": _iso(_parse_time(recorded_at or event.get("recorded_at") or _now(), field="recorded_at")),
        "actor_role": actor_role,
        "actor_id": actor_id,
        "idempotency_key": idempotency_key,
        "artifact_refs": artifact_refs,
        "payload": payload,
    }
    claim = _claim(conn, feedback_item_id)
    existing = conn.execute("SELECT * FROM judgment_feedback_events WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
    comparison = {
        "feedback_item_id": feedback_item_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "actor_role": actor_role,
        "actor_id": actor_id,
        "artifact_refs_json": _json(artifact_refs),
        "payload_json": _json(payload),
    }
    if existing:
        existing_data = dict(existing)
        if all(existing_data[key] == value for key, value in comparison.items()):
            return {"schema_version": SCHEMA_VERSION, "event_id": existing["event_id"], "idempotent": True}
        raise ControlPlaneError("idempotency_conflict", f"idempotency_key already used with different content: {idempotency_key}")
    events = _events(conn, feedback_item_id)
    _validate_transition(claim, events, record)
    with conn:
        conn.execute(
            """INSERT INTO judgment_feedback_events
               (event_id, feedback_item_id, event_type, effective_at, recorded_at, actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
               VALUES (:event_id, :feedback_item_id, :event_type, :effective_at, :recorded_at, :actor_role, :actor_id, :idempotency_key, :artifact_refs_json, :payload_json)""",
            {**record, "artifact_refs_json": _json(artifact_refs), "payload_json": _json(payload)},
        )
    return {"schema_version": SCHEMA_VERSION, "event_id": event_id, "idempotent": False}


def _derived_states(claim: dict[str, Any], events: list[dict[str, Any]], *, as_of: datetime | None = None) -> dict[str, str]:
    as_of = as_of or datetime.now(timezone.utc)
    if _event_exists(events, "CLOSED"):
        time_state = "CLOSED"
    elif as_of < _parse_time(claim["eligible_at"], field="eligible_at"):
        time_state = "WAITING"
    elif claim.get("overdue_at") and as_of > _parse_time(claim["overdue_at"], field="overdue_at") and not _event_exists(events, "OUTCOME_EXTRACTED"):
        time_state = "OVERDUE"
    else:
        time_state = "DUE"
    if _event_exists(events, "OUTCOME_EXTRACTED"):
        evidence_state = "EXTRACTED"
    elif _event_exists(events, "READ_ATTESTED"):
        evidence_state = "READ_ATTESTED"
    elif _event_exists(events, "OUTCOME_PACKAGE_READY"):
        evidence_state = "PACKAGE_READY"
    elif _event_exists(events, "ACQUISITION_BLOCKED"):
        evidence_state = "BLOCKED"
    elif _event_exists(events, "ACQUISITION_STARTED"):
        evidence_state = "ACQUIRING"
    else:
        evidence_state = "EMPTY"
    settlement = _last(events, OUTCOME_EVENTS)
    if not settlement:
        settlement_state = "UNSETTLED"
    elif settlement["event_type"] == "MEASUREMENT_MISMATCH":
        settlement_state = "MEASUREMENT_MISMATCH"
    else:
        settlement_state = str(settlement["payload"].get("settlement_verdict") or "UNSETTLED").upper()
    if _event_exists(events, "CLOSED"):
        learning_state = "CLOSED"
    elif _event_exists(events, "REPLICATION_ACCEPTED"):
        learning_state = "CLOSED"
    elif _event_exists(events, "LEARNING_APPLIED"):
        learning_state = "REPLICATION_PENDING"
    elif _event_exists(events, "LEARNING_NOTE_READY"):
        learning_state = "APPLICATION_PENDING"
    elif _event_exists(events, "DIAGNOSIS_ACCEPTED"):
        learning_state = "NOTE_READY"
    elif settlement_state not in {"UNSETTLED", "NOT_DIAGNOSTIC", "MEASUREMENT_MISMATCH"}:
        learning_state = "DIAGNOSIS_PENDING"
    else:
        learning_state = "NONE"
    return {
        "time_state": time_state,
        "evidence_state": evidence_state,
        "settlement_state": settlement_state,
        "learning_state": learning_state,
    }


def _priority(states: dict[str, str], claim: dict[str, Any], *, as_of: datetime, due_soon_days: int) -> str:
    if states["time_state"] == "CLOSED":
        return "DONE"
    if states["time_state"] == "OVERDUE" and states["evidence_state"] != "EXTRACTED":
        return "P0"
    if states["time_state"] in {"DUE", "OVERDUE"} and states["evidence_state"] in {"EMPTY", "ACQUIRING", "BLOCKED"}:
        return "P1"
    if states["evidence_state"] in {"PACKAGE_READY", "READ_ATTESTED", "EXTRACTED"} and states["settlement_state"] == "UNSETTLED":
        return "P2"
    if states["learning_state"] == "DIAGNOSIS_PENDING":
        return "P3"
    if states["learning_state"] == "APPLICATION_PENDING":
        return "P4"
    if states["learning_state"] == "REPLICATION_PENDING":
        return "P5"
    if states["time_state"] == "WAITING" and _parse_time(claim["eligible_at"], field="eligible_at") <= as_of + timedelta(days=due_soon_days):
        return "P6"
    return "WAITING"


def reconcile(conn: sqlite3.Connection, *, as_of: str, due_soon_days: int = 7) -> dict[str, Any]:
    as_of_dt = _parse_time(as_of, field="as_of", allow_date=True)
    if due_soon_days < 0:
        raise ControlPlaneError("due_soon_days_invalid", "due_soon_days cannot be negative")
    rows = conn.execute("SELECT * FROM judgment_feedback_claims ORDER BY eligible_at, feedback_item_id").fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        claim = dict(row)
        events = _events(conn, claim["feedback_item_id"])
        states = _derived_states(claim, events, as_of=as_of_dt)
        items.append({
            "feedback_item_id": claim["feedback_item_id"],
            "episode_id": claim["episode_id"],
            "claim_id": claim["claim_id"],
            "stage_id": claim["stage_id"],
            "company_id": claim["company_id"],
            "eligible_at": claim["eligible_at"],
            "overdue_at": claim["overdue_at"],
            "priority": _priority(states, claim, as_of=as_of_dt, due_soon_days=due_soon_days),
            **states,
        })
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6, "WAITING": 7, "DONE": 8}
    items.sort(key=lambda item: (priority_rank[item["priority"]], item["eligible_at"], item["feedback_item_id"]))
    return {"schema_version": SCHEMA_VERSION, "as_of": _iso(as_of_dt), "due_soon_days": due_soon_days, "items": items}


def show(conn: sqlite3.Connection, feedback_item_id: str, *, as_of: str | None = None) -> dict[str, Any]:
    claim = _claim(conn, feedback_item_id)
    events = _events(conn, feedback_item_id)
    as_of_dt = _parse_time(as_of, field="as_of", allow_date=True) if as_of else datetime.now(timezone.utc)
    states = _derived_states(claim, events, as_of=as_of_dt)
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": _iso(as_of_dt),
        "claim": claim,
        "states": states,
        "events": [{key: value for key, value in event.items() if key not in {"artifact_refs_json", "payload_json"}} for event in events],
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlPlaneError("json_read_failed", f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ControlPlaneError("json_object_required", f"{path} must contain a JSON object")
    return data


def _resolve_manifest_artifact_refs(manifest: dict[str, Any], directory: Path) -> dict[str, Any]:
    """Resolve explicit local artifact references relative to the experiment only."""
    resolved = deepcopy(manifest)
    def resolve_item(item: dict[str, Any]) -> None:
        for field in ("frozen_artifact_ref", "source_contract_ref", "measurement_contract_ref"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            raw_path, separator, pointer = value.partition("#")
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = directory / path
            item[field] = f"{path.resolve()}{separator}{pointer}" if separator else str(path.resolve())
    if isinstance(resolved.get("feedback_items"), list):
        for item in resolved["feedback_items"]:
            if isinstance(item, dict):
                resolve_item(item)
    else:
        claims = resolved.get("claims")
        if isinstance(claims, list):
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                for stage in claim.get("stages", []):
                    if not isinstance(stage, dict):
                        continue
                    resolve_item(stage)
    return resolved


def _command_init(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
    finally:
        conn.close()
    return {"schema_version": SCHEMA_VERSION, "status": "READY", "db": str(Path(args.db))}


def _command_register(args: argparse.Namespace) -> dict[str, Any]:
    directory = Path(args.experiment_dir)
    manifest_path = directory / "judgment_feedback_control.json"
    if not manifest_path.is_file():
        raise ControlPlaneError("experiment_control_manifest_missing", f"expected structured manifest: {manifest_path}")
    conn = connect(args.db)
    try:
        initialize(conn)
        return register_manifest(
            conn,
            _resolve_manifest_artifact_refs(_read_json(manifest_path), directory),
            registered_at=args.registered_at,
        )
    finally:
        conn.close()


def _command_reconcile(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return reconcile(conn, as_of=args.as_of, due_soon_days=args.due_soon_days)
    finally:
        conn.close()


def _command_append(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return append_event(conn, _read_json(Path(args.input)), recorded_at=args.recorded_at)
    finally:
        conn.close()


def _command_show(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return show(conn, args.feedback_item_id, as_of=args.as_of)
    finally:
        conn.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Judgment feedback control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create control-plane tables in the existing database")
    init.add_argument("--db", required=True)
    init.set_defaults(handler=_command_init)
    register = sub.add_parser("register-experiment", help="register an explicit frozen structured contract")
    register.add_argument("--db", required=True)
    register.add_argument("--experiment-dir", required=True)
    register.add_argument("--registered-at")
    register.set_defaults(handler=_command_register)
    reconcile_cmd = sub.add_parser("reconcile", help="derive the feedback inbox without writing events")
    reconcile_cmd.add_argument("--db", required=True)
    reconcile_cmd.add_argument("--as-of", required=True)
    reconcile_cmd.add_argument("--due-soon-days", type=int, default=7)
    reconcile_cmd.set_defaults(handler=_command_reconcile)
    inbox = sub.add_parser("inbox", help="alias for reconcile")
    inbox.add_argument("--db", required=True)
    inbox.add_argument("--as-of", required=True)
    inbox.add_argument("--due-soon-days", type=int, default=7)
    inbox.set_defaults(handler=_command_reconcile)
    append = sub.add_parser("append-event", help="append one validated control event")
    append.add_argument("--db", required=True)
    append.add_argument("--input", required=True)
    append.add_argument("--recorded-at")
    append.set_defaults(handler=_command_append)
    show_cmd = sub.add_parser("show", help="show one item and its derived state")
    show_cmd.add_argument("--db", required=True)
    show_cmd.add_argument("--feedback-item-id", required=True)
    show_cmd.add_argument("--as-of")
    show_cmd.set_defaults(handler=_command_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = args.handler(args)
    except ControlPlaneError as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "ERROR", "code": exc.code, "detail": exc.detail}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
