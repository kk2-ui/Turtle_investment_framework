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
import re
import sqlite3
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.judgment_selection_candidate import (
        CANDIDATE_SCHEMA_VERSION,
        PEER_PANEL_ADMISSION_VERSION,
        validate_selection_candidate,
        validate_selection_review,
    )
except ModuleNotFoundError:
    from judgment_selection_candidate import (
        CANDIDATE_SCHEMA_VERSION,
        PEER_PANEL_ADMISSION_VERSION,
        validate_selection_candidate,
        validate_selection_review,
    )


SCHEMA_VERSION = "judgment-feedback-control.v1"
REGISTRATION_SCHEMA_VERSION = "judgment-feedback-control-registration.v1"
CANDIDATE_CONDITION_SCHEMA_VERSION = "candidate-condition-due-registration.v1"
CANDIDATE_CONDITION_INBOX_SCHEMA_VERSION = "candidate-condition-due-inbox.v1"
OPERATING_OUTCOME_RECORD_SCHEMA_VERSION = "judgment-feedback-operating-outcome-record.v1"
DUE_EXECUTION_SCHEMA_VERSION = "judgment-feedback-due-execution.v1"
HOLDOUT_EVALUATION_RECEIPT_SCHEMA_VERSION = "judgment-holdout-evaluation-receipt.v1"
HOLDOUT_PRE_REVEAL_REVIEW_SCHEMA_VERSION = "judgment-holdout-pre-reveal-review-receipt.v1"
HOLDOUT_EXPOSURE_BREACH_SCHEMA_VERSION = "judgment-holdout-exposure-breach.v1"
HOLDOUT_ADMIN_CORRECTION_SCHEMA_VERSION = "judgment-holdout-administrative-prerequisite-correction.v1"
HOLDOUT_ADMIN_CORRECTION_REVIEW_SCHEMA_VERSION = "judgment-holdout-administrative-prerequisite-review.v1"
HOLDOUT_METHOD_APPLICATION_SCHEMA_VERSION = "judgment-holdout-frozen-method-application.v1"
R103_HOLDOUT_CASE_ID = "HOLDOUT:R-103:yinlun-nev-nomination-20201231"
R103_REQUIRED_METHOD_SCOPE = "SELECTION_AND_BOUNDARY"
TIME_STATES = {"WAITING", "DUE", "OVERDUE", "CLOSED"}
EVIDENCE_STATES = {"EMPTY", "ACQUIRING", "BLOCKED", "PACKAGE_READY", "READ_ATTESTED", "EXTRACTED"}
SETTLEMENT_STATES = {"UNSETTLED", "A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC", "MEASUREMENT_MISMATCH"}
LEARNING_STATES = {
    "NONE", "DIAGNOSIS_PENDING", "NOTE_READY", "MEASUREMENT_BOUNDARY_READY",
    "MIXED_MECHANISM_BOUNDARY_READY",
    "APPLICATION_PENDING", "APPLIED", "REPLICATION_PENDING", "CLOSED",
}
SETTLEMENT_POLICIES = {"INITIAL_DISCLOSURE", "LATEST_OFFICIAL_AS_OF_EVALUATION"}
EPISODE_CLASSES = {"JUDGMENT_SELECTION_EPISODE", "MECHANISM_SIGNAL_PROBE", "PIPELINE_REHEARSAL"}
SELECTION_STATUSES = {"SELECTION_ADMITTED", "NO_PRIMARY"}
LEARNING_ELIGIBILITIES = {
    "SELECTION_METHOD_ELIGIBLE", "BOUNDARY_METHOD_ELIGIBLE", "MECHANISM_SETTLEMENT_ONLY", "EVALUATION_ONLY", "TEACHING_ONLY",
}
METHOD_LEARNING_ELIGIBILITIES = {"SELECTION_METHOD_ELIGIBLE", "BOUNDARY_METHOD_ELIGIBLE"}
PROGRAM_LANES = {
    "UNASSIGNED", "HISTORICAL_TRAINING", "HISTORICAL_HOLDOUT", "HISTORICAL_TEACHING", "LIVE_SENTINEL",
}
OUTCOME_ACCESS_STATES = {"UNSPECIFIED", "PIT_OUTCOME_SEALED", "OUTCOME_EXPOSED", "NOT_YET_RELEASED"}
CANDIDATE_CONDITION_STATUSES = {"PENDING"}
CANDIDATE_CONDITION_NEXT_STEPS = {"ENUMERATE_OFFICIAL_CONDITION_SOURCE"}
CANDIDATE_CONDITION_SOURCE_KINDS = {"CNINFO_ORDINARY_ANNOUNCEMENT"}
EVENT_TYPES = {
    "CLAIM_REGISTERED",
    "OUTCOME_RELEASE_AUTHORIZED",
    "ACQUISITION_STARTED",
    "ACQUISITION_BLOCKED",
    "OUTCOME_PACKAGE_READY",
    "READ_ATTESTED",
    "OUTCOME_EXTRACTED",
    "CLAIM_SETTLED",
    "MEASUREMENT_MISMATCH",
    "OPERATING_OUTCOME_RECORDED",
    "OUTCOME_EXPOSURE_BREACH",
    "DIAGNOSIS_ACCEPTED",
    "LEARNING_NOTE_READY",
    "LEARNING_APPLIED",
    "REPLICATION_ACCEPTED",
    "HOLDOUT_EVALUATION_ACCEPTED",
    "CLOSED",
}
EPISTEMIC_FAILURE_LOCI = {"STATE", "DECISION", "MEASUREMENT", "MECHANISM", "TRANSMISSION", "ENVIRONMENT"}
DELIVERY_ROOT_CAUSES = {"DATA_COVERAGE", "ACQUISITION_MODULE", "REASONING", "MODEL", "WRITING"}
OPERATING_OUTCOME_RECORDED = "OPERATING_OUTCOME_RECORDED"
OUTCOME_EVENTS = {"CLAIM_SETTLED", "MEASUREMENT_MISMATCH", OPERATING_OUTCOME_RECORDED}
OUTCOME_PIPELINE_EVENTS = {
    "ACQUISITION_STARTED", "ACQUISITION_BLOCKED", "OUTCOME_PACKAGE_READY", "READ_ATTESTED", "OUTCOME_EXTRACTED",
}
ADAPTER_ONLY_EVENTS = OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS | {
    "HOLDOUT_EVALUATION_ACCEPTED", "OUTCOME_EXPOSURE_BREACH", "OUTCOME_RELEASE_AUTHORIZED",
}
HOLDOUT_CLOCKS = {"D1", "D2", "D3", "D4", "D5"}
REQUIRED_SELECTION_STAGE_IDS = (
    "D1_IMPLEMENTATION",
    "D2_CUSTOMER_ABSORPTION",
    "D3_UNIT_ECONOMICS",
    "D4_WORKING_CAPITAL_AND_CASH",
    "D5_CAPITAL_RETURN",
)
SELECTION_STAGE_IDS = (
    "D1_IMPLEMENTATION",
    "D2_CUSTOMER_ABSORPTION",
    "D3_PRODUCT_VOLUME",
    "D3_UNIT_ECONOMICS",
    "D4_WORKING_CAPITAL_AND_CASH",
    "D5_CAPITAL_RETURN",
)
SELECTION_STAGE_ORDERS = (REQUIRED_SELECTION_STAGE_IDS, SELECTION_STAGE_IDS)
HOLDOUT_EVALUATION_VERDICTS = {"SUPPORTED", "MIXED", "FAILED", "NOT_DIAGNOSTIC"}
HOLDOUT_PROHIBITED_RIGHT_EVENTS = {
    "DIAGNOSIS_ACCEPTED", "LEARNING_NOTE_READY", "LEARNING_APPLIED", "REPLICATION_ACCEPTED",
}
MIXED_SELECTION_BOUNDARY_SCOPE = "MIXED_MECHANISM_BOUNDARY"
SELECTION_BOUNDARY_PROHIBITED_RIGHTS = [
    "DIRECTIONAL_SELECTION_LEARNING", "METHOD_APPLICATION", "METHOD_FREEZE",
    "HOLDOUT_RELEASE", "REPORT_USE",
]


class ControlPlaneError(ValueError):
    """A business-rule failure that callers can present without a traceback."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now() -> str:
    return _iso(_now_dt())


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


def _same_artifact_reference(left: Any, right: str | Path) -> bool:
    if not str(left or "").strip() or not str(right or "").strip():
        return False
    return _reference_path(str(left)).resolve() == _reference_path(str(right)).resolve()


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


def _candidate_condition_item_id(candidate_id: str, condition_id: str) -> str:
    return f"CCI:{candidate_id}:{condition_id}"


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _identity_from_frozen_contract(reference: str) -> tuple[str, str, str] | None:
    """Recover a legacy row's learning identity from the already-frozen contract."""
    path = _reference_path(reference)
    if not path.is_file():
        return None
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pair = contract.get("mechanism_signal_pair") if isinstance(contract, dict) else None
    if not isinstance(pair, dict):
        return None
    selection_status = str(pair.get("selection_status") or "").upper()
    if selection_status not in SELECTION_STATUSES:
        return None
    if selection_status == "SELECTION_ADMITTED":
        return ("JUDGMENT_SELECTION_EPISODE", selection_status, "SELECTION_METHOD_ELIGIBLE")
    return ("MECHANISM_SIGNAL_PROBE", "NO_PRIMARY", "MECHANISM_SETTLEMENT_ONLY")


def _backfill_legacy_claim_identity(conn: sqlite3.Connection) -> None:
    """Replace only schema-default identities with their frozen-contract identity."""
    rows = conn.execute(
        """SELECT feedback_item_id, source_contract_ref
           FROM judgment_feedback_claims
           WHERE episode_class = 'PIPELINE_REHEARSAL'
             AND selection_status = 'NO_PRIMARY'
             AND learning_eligibility = 'MECHANISM_SETTLEMENT_ONLY'"""
    ).fetchall()
    for row in rows:
        identity = _identity_from_frozen_contract(str(row["source_contract_ref"]))
        if identity is None:
            continue
        conn.execute(
            """UPDATE judgment_feedback_claims
               SET episode_class = ?, selection_status = ?, learning_eligibility = ?
               WHERE feedback_item_id = ?""",
            (*identity, row["feedback_item_id"]),
        )


def _reference_fragment(reference: str) -> str:
    return reference.split("#", 1)[1] if "#" in reference else ""


def _can_rehome_live_forward_references(existing: dict[str, Any], intended: dict[str, Any]) -> bool:
    """Allow a worktree-path move only when the frozen files are identical.

    Integration moves the same frozen R05/R06/R54 files from a linked
    development worktree into the main checkout.  That operational relocation
    must not be confused with a changed claim.  We compare the actual small
    contract/freeze files directly; any unavailable or changed legacy file
    remains a normal registration conflict rather than being guessed into the
    new path.
    """
    reference_fields = {
        "source_ref", "frozen_artifact_ref", "source_contract_ref", "measurement_contract_ref",
    }
    if any(existing.get(key) != intended.get(key) for key in set(existing) - reference_fields - {"registered_at"}):
        return False
    old_contract = _reference_path(str(existing.get("source_contract_ref") or ""))
    new_contract = _reference_path(str(intended.get("source_contract_ref") or ""))
    old_freeze = _reference_path(str(existing.get("frozen_artifact_ref") or ""))
    new_freeze = _reference_path(str(intended.get("frozen_artifact_ref") or ""))
    if not all(path.is_file() for path in (old_contract, new_contract, old_freeze, new_freeze)):
        return False
    try:
        old_payload = json.loads(old_contract.read_text(encoding="utf-8"))
        new_payload = json.loads(new_contract.read_text(encoding="utf-8"))
        identical_contract = old_payload == new_payload
        identical_freeze = old_freeze.read_text(encoding="utf-8") == new_freeze.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not identical_contract or not identical_freeze:
        return False
    if old_contract.parent.name != new_contract.parent.name:
        return False
    for field in ("source_ref", "measurement_contract_ref"):
        if _reference_fragment(str(existing.get(field) or "")) != _reference_fragment(str(intended.get(field) or "")):
            return False
    return True


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
          episode_class TEXT NOT NULL DEFAULT 'PIPELINE_REHEARSAL',
          selection_status TEXT NOT NULL DEFAULT 'NO_PRIMARY',
          learning_eligibility TEXT NOT NULL DEFAULT 'MECHANISM_SETTLEMENT_ONLY',
          program_lane TEXT NOT NULL DEFAULT 'UNASSIGNED',
          outcome_access TEXT NOT NULL DEFAULT 'UNSPECIFIED',
          training_program_ref TEXT NOT NULL DEFAULT '',
          pre_reveal_review_receipt_ref TEXT NOT NULL DEFAULT '',
          pre_reveal_review_receipt_json TEXT NOT NULL DEFAULT '',
          selection_resolution_ref TEXT NOT NULL DEFAULT '',
          selection_resolution_review_ref TEXT NOT NULL DEFAULT '',
          selection_outcome_custodian_id TEXT NOT NULL DEFAULT '',
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
        CREATE TABLE IF NOT EXISTS judgment_candidate_conditions (
          candidate_condition_item_id TEXT PRIMARY KEY,
          candidate_id TEXT NOT NULL,
          condition_id TEXT NOT NULL,
          company_id TEXT NOT NULL,
          cutoff_at TEXT NOT NULL,
          due_at TEXT NOT NULL,
          official_source_query_json TEXT NOT NULL,
          next_step TEXT NOT NULL,
          status TEXT NOT NULL,
          condition_contract_ref TEXT NOT NULL,
          registered_at TEXT NOT NULL,
          UNIQUE (candidate_id, condition_id)
        );
        CREATE INDEX IF NOT EXISTS idx_judgment_candidate_conditions_due
          ON judgment_candidate_conditions(due_at, candidate_condition_item_id);
        CREATE TABLE IF NOT EXISTS judgment_holdout_admin_correction_events (
          correction_id TEXT PRIMARY KEY,
          program_id TEXT NOT NULL,
          source_program_id TEXT NOT NULL,
          training_episode_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          method_version TEXT NOT NULL,
          method_scope TEXT NOT NULL,
          method_frozen_at TEXT NOT NULL,
          method_freeze_recorded_at TEXT NOT NULL,
          method_application_event_id TEXT NOT NULL,
          independent_method_review_ref TEXT NOT NULL,
          correction_author_id TEXT NOT NULL,
          method_designer_id TEXT NOT NULL,
          r102_learner_id TEXT NOT NULL,
          future_evaluator_id TEXT NOT NULL,
          outcome_custodian_id TEXT NOT NULL,
          corrected_at TEXT NOT NULL,
          recorded_at TEXT NOT NULL,
          correction_ref TEXT NOT NULL,
          correction_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_judgment_holdout_admin_correction_binding
          ON judgment_holdout_admin_correction_events
             (program_id, source_program_id, training_episode_id, case_id, recorded_at);
        CREATE TABLE IF NOT EXISTS judgment_holdout_admin_correction_review_events (
          review_id TEXT PRIMARY KEY,
          correction_id TEXT NOT NULL,
          program_id TEXT NOT NULL,
          training_episode_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          reviewer_id TEXT NOT NULL,
          reviewed_at TEXT NOT NULL,
          recorded_at TEXT NOT NULL,
          review_ref TEXT NOT NULL,
          review_json TEXT NOT NULL,
          FOREIGN KEY (correction_id)
            REFERENCES judgment_holdout_admin_correction_events(correction_id)
        );
        CREATE INDEX IF NOT EXISTS idx_judgment_holdout_admin_review_binding
          ON judgment_holdout_admin_correction_review_events
             (correction_id, recorded_at);
        """
    )
    # The feedback control plane has already been initialized in development
    # databases.  These three columns are part of the claim identity, so add
    # them in place instead of creating a second store or a parallel registry.
    existing_columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(judgment_feedback_claims)").fetchall()
    }
    for name, definition in (
        ("episode_class", "TEXT NOT NULL DEFAULT 'PIPELINE_REHEARSAL'"),
        ("selection_status", "TEXT NOT NULL DEFAULT 'NO_PRIMARY'"),
        ("learning_eligibility", "TEXT NOT NULL DEFAULT 'MECHANISM_SETTLEMENT_ONLY'"),
        ("program_lane", "TEXT NOT NULL DEFAULT 'UNASSIGNED'"),
        ("outcome_access", "TEXT NOT NULL DEFAULT 'UNSPECIFIED'"),
        ("training_program_ref", "TEXT NOT NULL DEFAULT ''"),
        ("pre_reveal_review_receipt_ref", "TEXT NOT NULL DEFAULT ''"),
        ("pre_reveal_review_receipt_json", "TEXT NOT NULL DEFAULT ''"),
        ("selection_resolution_ref", "TEXT NOT NULL DEFAULT ''"),
        ("selection_resolution_review_ref", "TEXT NOT NULL DEFAULT ''"),
        ("selection_outcome_custodian_id", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in existing_columns:
            conn.execute(f"ALTER TABLE judgment_feedback_claims ADD COLUMN {name} {definition}")
    _backfill_legacy_claim_identity(conn)
    conn.commit()


def _admin_text(payload: dict[str, Any], field: str) -> str:
    return _required_text(payload, field)


def _admin_time(payload: dict[str, Any], field: str) -> datetime:
    return _parse_time(payload.get(field), field=field)


def _linked_holdout_context(
    conn: sqlite3.Connection, *, program_id: str, source_program_id: str,
    training_episode_id: str, case_id: str,
) -> dict[str, Any]:
    row = conn.execute(
        """SELECT target.program_id, target.program_state, target.method_version,
                  target.method_scope, target.method_frozen_at,
                  target.method_freeze_recorded_at, target.contract_ref,
                  link.source_program_id, link.source_training_episode_id,
                  link.source_case_id, link.source_freeze_ref,
                  source_episode.case_id, source_episode.lane
             FROM judgment_training_holdout_links AS link
             JOIN judgment_training_programs AS target
               ON target.program_id = link.program_id
             JOIN judgment_training_episodes AS source_episode
               ON source_episode.training_episode_id = link.source_training_episode_id
            WHERE link.program_id = ?
              AND link.source_program_id = ?
              AND link.source_training_episode_id = ?
              AND link.source_case_id = ?
              AND link.link_role = 'HISTORICAL_HOLDOUT'""",
        (program_id, source_program_id, training_episode_id, case_id),
    ).fetchone()
    if row is None:
        raise ControlPlaneError(
            "holdout_admin_link_unknown",
            "administrative correction must bind an existing linked historical holdout",
        )
    context = dict(row)
    if context["case_id"] != case_id or context["lane"] != "HISTORICAL_HOLDOUT":
        raise ControlPlaneError(
            "holdout_admin_identity_invalid",
            "administrative correction identity is not the linked historical holdout",
        )
    return context


def _method_application_event(
    conn: sqlite3.Connection, *, program_id: str, contract_ref: str,
    event_id: str,
) -> dict[str, Any]:
    row = conn.execute(
        """SELECT event.event_id, event.effective_at, event.recorded_at, event.actor_id,
                  event.payload_json, claim.feedback_item_id, claim.episode_id,
                  claim.program_lane, claim.learning_eligibility
             FROM judgment_feedback_events AS event
             JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
             JOIN judgment_training_episodes AS episode
               ON episode.case_id = claim.episode_id
            WHERE event.event_id = ?
              AND event.event_type = 'LEARNING_APPLIED'
              AND episode.program_id = ?
              AND episode.lane = 'HISTORICAL_TRAINING'
              AND claim.training_program_ref = ?
              AND claim.program_lane = 'HISTORICAL_TRAINING'
              AND claim.learning_eligibility = 'SELECTION_METHOD_ELIGIBLE'""",
        (event_id, program_id, contract_ref),
    ).fetchone()
    if row is None:
        raise ControlPlaneError(
            "holdout_admin_method_application_missing",
            "administrative correction must bind an accepted selection-method LEARNING_APPLIED event",
        )
    return dict(row)


def _method_review_context(
    reference: str, *, method_version: str,
) -> tuple[str, dict[str, Any], datetime]:
    path = _reference_path(reference).resolve()
    _require_artifact(str(path), field="independent_method_review_ref")
    receipt = _read_json(path)
    if receipt.get("schema_version") != "judgment-selection-method-freeze-review.v1":
        raise ControlPlaneError(
            "holdout_admin_method_review_schema_invalid",
            "independent_method_review_ref must use judgment-selection-method-freeze-review.v1",
        )
    if receipt.get("method_version") != method_version:
        raise ControlPlaneError(
            "holdout_admin_method_review_method_mismatch",
            "independent method review must bind the frozen selection method version",
        )
    if receipt.get("verdict") != "FROZEN_SELECTION_METHOD_ACCEPTED":
        raise ControlPlaneError(
            "holdout_admin_method_review_not_accepted",
            "independent method review must accept the frozen selection method",
        )
    _admin_text(receipt, "review_id")
    _admin_text(receipt, "reviewer_id")
    return str(path), receipt, _admin_time(receipt, "reviewed_at")


def _correction_identity(payload: dict[str, Any]) -> dict[str, str]:
    fields = (
        "correction_id", "program_id", "source_program_id", "training_episode_id",
        "case_id", "method_version", "method_scope", "method_application_event_id",
        "independent_method_review_ref", "correction_author_id", "method_designer_id",
        "r102_learner_id", "future_evaluator_id", "outcome_custodian_id",
    )
    return {field: _admin_text(payload, field) for field in fields}


def _validate_holdout_admin_correction(
    conn: sqlite3.Connection, payload: dict[str, Any], *, corrected_at: datetime,
    recorded_at: datetime,
) -> dict[str, Any]:
    if payload.get("schema_version") != HOLDOUT_ADMIN_CORRECTION_SCHEMA_VERSION:
        raise ControlPlaneError(
            "holdout_admin_correction_schema_invalid",
            f"expected schema_version {HOLDOUT_ADMIN_CORRECTION_SCHEMA_VERSION}",
        )
    identity = _correction_identity(payload)
    if identity["case_id"] != R103_HOLDOUT_CASE_ID:
        raise ControlPlaneError(
            "holdout_admin_case_invalid",
            "administrative prerequisite correction is reserved for the sealed R-103 holdout",
        )
    if payload.get("sealed_core_mutation") != "NONE":
        raise ControlPlaneError(
            "holdout_admin_sealed_core_mutation_forbidden",
            "administrative correction may not mutate the sealed holdout core",
        )
    if payload.get("outcome_body_access") != "NOT_OPENED":
        raise ControlPlaneError(
            "holdout_admin_outcome_access_invalid",
            "administrative correction must retain the sealed outcome firewall",
        )
    if payload.get("authorization_effect") != "NO_APPLICATION_CONTROL_OR_OUTCOME_REVEAL":
        raise ControlPlaneError(
            "holdout_admin_authorization_escalation",
            "administrative correction cannot authorize application, control registration or outcome reveal",
        )
    if "R-102" not in _admin_text(payload, "superseded_prerequisite"):
        raise ControlPlaneError(
            "holdout_admin_superseded_prerequisite_invalid",
            "administrative correction must name the stale R-102-specific prerequisite it supersedes",
        )
    _admin_text(payload, "replacement_prerequisite")
    if corrected_at > recorded_at:
        raise ControlPlaneError(
            "holdout_admin_correction_time_invalid",
            "corrected_at must be no later than the correction receipt recording",
        )
    context = _linked_holdout_context(
        conn,
        program_id=identity["program_id"],
        source_program_id=identity["source_program_id"],
        training_episode_id=identity["training_episode_id"],
        case_id=identity["case_id"],
    )
    if context["program_state"] != "ACTIVE":
        raise ControlPlaneError(
            "holdout_admin_program_not_active",
            "administrative correction requires the active linked selection program",
        )
    if context["method_scope"] != R103_REQUIRED_METHOD_SCOPE:
        raise ControlPlaneError(
            "holdout_admin_method_scope_mismatch",
            "R-103 can evaluate only a frozen SELECTION_AND_BOUNDARY method",
        )
    if not context["method_frozen_at"] or not context["method_freeze_recorded_at"]:
        raise ControlPlaneError(
            "holdout_admin_method_not_frozen",
            "administrative correction may be appended only after the linked selection method is frozen",
        )
    frozen_at = _parse_time(context["method_frozen_at"], field="method_frozen_at")
    freeze_recorded_at = _parse_time(
        context["method_freeze_recorded_at"], field="method_freeze_recorded_at",
    )
    if frozen_at > freeze_recorded_at or freeze_recorded_at > corrected_at:
        raise ControlPlaneError(
            "holdout_admin_freeze_time_invalid",
            "administrative correction must follow a valid recorded method freeze",
        )
    if identity["method_version"] != context["method_version"]:
        raise ControlPlaneError(
            "holdout_admin_method_version_mismatch",
            "administrative correction method_version differs from the linked frozen method",
        )
    if identity["method_scope"] != context["method_scope"]:
        raise ControlPlaneError(
            "holdout_admin_method_scope_mismatch",
            "administrative correction method_scope differs from the linked frozen method",
        )
    if _admin_time(payload, "method_frozen_at") != frozen_at or _admin_time(
        payload, "method_freeze_recorded_at",
    ) != freeze_recorded_at:
        raise ControlPlaneError(
            "holdout_admin_freeze_receipt_mismatch",
            "administrative correction must bind the database method freeze and its recorded receipt",
        )
    application_event = _method_application_event(
        conn,
        program_id=context["program_id"],
        contract_ref=context["contract_ref"],
        event_id=identity["method_application_event_id"],
    )
    application_effective = _parse_time(
        application_event["effective_at"], field="method_application.effective_at",
    )
    application_recorded = _parse_time(
        application_event["recorded_at"], field="method_application.recorded_at",
    )
    if application_effective > application_recorded or application_recorded > frozen_at:
        raise ControlPlaneError(
            "holdout_admin_method_application_time_invalid",
            "bound selection-method application must precede the frozen method",
        )
    review_path, method_review, method_reviewed_at = _method_review_context(
        identity["independent_method_review_ref"], method_version=context["method_version"],
    )
    if method_reviewed_at > frozen_at:
        raise ControlPlaneError(
            "holdout_admin_method_review_time_invalid",
            "independent method review must precede the frozen method",
        )
    return {
        **identity,
        "method_frozen_at": _iso(frozen_at),
        "method_freeze_recorded_at": _iso(freeze_recorded_at),
        "corrected_at": _iso(corrected_at),
        "method_review_path": review_path,
        "method_review": method_review,
    }


def append_holdout_admin_correction(
    conn: sqlite3.Connection, *, correction_ref: str | Path,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    path = _reference_path(str(correction_ref)).resolve()
    _require_artifact(str(path), field="correction_ref")
    payload = _read_json(path)
    now = _now_dt()
    recorded = _parse_time(recorded_at, field="recorded_at") if recorded_at else now
    if recorded > now:
        raise ControlPlaneError(
            "holdout_admin_recorded_in_future",
            "administrative correction recording cannot be later than the real current time",
        )
    corrected = _admin_time(payload, "corrected_at")
    context = _validate_holdout_admin_correction(
        conn, payload, corrected_at=corrected, recorded_at=recorded,
    )
    snapshot = _json(payload)
    existing = conn.execute(
        "SELECT * FROM judgment_holdout_admin_correction_events WHERE correction_id = ?",
        (context["correction_id"],),
    ).fetchone()
    intended = {
        "program_id": context["program_id"],
        "source_program_id": context["source_program_id"],
        "training_episode_id": context["training_episode_id"],
        "case_id": context["case_id"],
        "method_version": context["method_version"],
        "method_scope": context["method_scope"],
        "method_frozen_at": context["method_frozen_at"],
        "method_freeze_recorded_at": context["method_freeze_recorded_at"],
        "method_application_event_id": context["method_application_event_id"],
        "independent_method_review_ref": context["independent_method_review_ref"],
        "correction_author_id": context["correction_author_id"],
        "method_designer_id": context["method_designer_id"],
        "r102_learner_id": context["r102_learner_id"],
        "future_evaluator_id": context["future_evaluator_id"],
        "outcome_custodian_id": context["outcome_custodian_id"],
        "corrected_at": context["corrected_at"],
        "correction_ref": str(path),
        "correction_json": snapshot,
    }
    if existing is not None:
        if any(existing[field] != value for field, value in intended.items()):
            raise ControlPlaneError(
                "holdout_admin_correction_conflict",
                "administrative correction is append-only and its existing receipt differs",
            )
        return {
            "schema_version": HOLDOUT_ADMIN_CORRECTION_SCHEMA_VERSION,
            "status": "ADMINISTRATIVE_CORRECTION_RECORDED",
            "correction_id": context["correction_id"],
            "idempotent": True,
        }
    with conn:
        conn.execute(
            """INSERT INTO judgment_holdout_admin_correction_events
               (correction_id, program_id, source_program_id, training_episode_id, case_id,
                method_version, method_scope, method_frozen_at, method_freeze_recorded_at,
                method_application_event_id, independent_method_review_ref, correction_author_id,
                method_designer_id, r102_learner_id, future_evaluator_id, outcome_custodian_id,
                corrected_at, recorded_at, correction_ref, correction_json)
               VALUES (:correction_id, :program_id, :source_program_id, :training_episode_id,
                       :case_id, :method_version, :method_scope, :method_frozen_at,
                       :method_freeze_recorded_at, :method_application_event_id,
                       :independent_method_review_ref, :correction_author_id,
                       :method_designer_id, :r102_learner_id, :future_evaluator_id,
                       :outcome_custodian_id, :corrected_at, :recorded_at, :correction_ref,
                       :correction_json)""",
            {**intended, "correction_id": context["correction_id"], "recorded_at": _iso(recorded)},
        )
    return {
        "schema_version": HOLDOUT_ADMIN_CORRECTION_SCHEMA_VERSION,
        "status": "ADMINISTRATIVE_CORRECTION_RECORDED",
        "correction_id": context["correction_id"],
        "program_id": context["program_id"],
        "idempotent": False,
    }


def _validate_holdout_admin_review(
    correction: dict[str, Any], review: dict[str, Any], *, reviewed_at: datetime,
    recorded_at: datetime,
) -> dict[str, str]:
    if review.get("schema_version") != HOLDOUT_ADMIN_CORRECTION_REVIEW_SCHEMA_VERSION:
        raise ControlPlaneError(
            "holdout_admin_review_schema_invalid",
            f"expected schema_version {HOLDOUT_ADMIN_CORRECTION_REVIEW_SCHEMA_VERSION}",
        )
    for field in ("correction_id", "program_id", "training_episode_id", "case_id"):
        if review.get(field) != correction[field]:
            raise ControlPlaneError(
                "holdout_admin_review_identity_mismatch",
                f"administrative review {field} does not match its correction",
            )
    if review.get("reviewed_correction") != _loads(correction["correction_json"]):
        raise ControlPlaneError(
            "holdout_admin_review_snapshot_mismatch",
            "administrative review must retain the exact recorded correction snapshot",
        )
    if _reference_path(str(review.get("correction_ref") or "")).resolve() != Path(
        correction["correction_ref"],
    ).resolve():
        raise ControlPlaneError(
            "holdout_admin_review_reference_mismatch",
            "administrative review correction_ref differs from the recorded correction",
        )
    if review.get("verdict") != "ADMINISTRATIVE_PREREQUISITE_CORRECTION_ACCEPTED":
        raise ControlPlaneError(
            "holdout_admin_review_not_accepted",
            "administrative review must explicitly accept the correction",
        )
    if review.get("reviewer_acceptance") != "ACCEPTED":
        raise ControlPlaneError(
            "holdout_admin_reviewer_acceptance_missing",
            "administrative review reviewer_acceptance must be ACCEPTED",
        )
    if review.get("sealed_core_mutation") != "NONE" or review.get("outcome_body_access") != "NOT_OPENED":
        raise ControlPlaneError(
            "holdout_admin_review_firewall_invalid",
            "administrative review must preserve the sealed core and outcome firewall",
        )
    if review.get("authorization_effect") != "NO_APPLICATION_CONTROL_OR_OUTCOME_REVEAL":
        raise ControlPlaneError(
            "holdout_admin_review_authorization_escalation",
            "administrative review cannot authorize application, control registration or outcome reveal",
        )
    reviewer_id = _admin_text(review, "reviewer_id")
    independent_from = {
        correction["correction_author_id"], correction["method_designer_id"],
        correction["r102_learner_id"], correction["future_evaluator_id"],
        correction["outcome_custodian_id"],
    }
    if reviewer_id in independent_from:
        raise ControlPlaneError(
            "holdout_admin_reviewer_not_independent",
            "administrative reviewer must differ from correction author, method designer, R-102 learner, future evaluator and outcome custodian",
        )
    if reviewed_at < _parse_time(correction["corrected_at"], field="corrected_at") or reviewed_at > recorded_at:
        raise ControlPlaneError(
            "holdout_admin_review_time_invalid",
            "administrative review must follow correction and precede its receipt recording",
        )
    return {"review_id": _admin_text(review, "review_id"), "reviewer_id": reviewer_id}


def review_holdout_admin_correction(
    conn: sqlite3.Connection, *, review_ref: str | Path,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    path = _reference_path(str(review_ref)).resolve()
    _require_artifact(str(path), field="review_ref")
    review = _read_json(path)
    correction_id = _admin_text(review, "correction_id")
    correction_row = conn.execute(
        "SELECT * FROM judgment_holdout_admin_correction_events WHERE correction_id = ?",
        (correction_id,),
    ).fetchone()
    if correction_row is None:
        raise ControlPlaneError(
            "holdout_admin_correction_unknown",
            "administrative review requires an already recorded correction",
        )
    correction = dict(correction_row)
    now = _now_dt()
    recorded = _parse_time(recorded_at, field="recorded_at") if recorded_at else now
    if recorded > now:
        raise ControlPlaneError(
            "holdout_admin_review_recorded_in_future",
            "administrative review recording cannot be later than the real current time",
        )
    review_context = _validate_holdout_admin_review(
        correction, review, reviewed_at=_admin_time(review, "reviewed_at"), recorded_at=recorded,
    )
    snapshot = _json(review)
    existing = conn.execute(
        "SELECT * FROM judgment_holdout_admin_correction_review_events WHERE review_id = ?",
        (review_context["review_id"],),
    ).fetchone()
    intended = {
        "correction_id": correction_id,
        "program_id": correction["program_id"],
        "training_episode_id": correction["training_episode_id"],
        "case_id": correction["case_id"],
        "reviewer_id": review_context["reviewer_id"],
        "reviewed_at": _iso(_admin_time(review, "reviewed_at")),
        "review_ref": str(path),
        "review_json": snapshot,
    }
    if existing is not None:
        if any(existing[field] != value for field, value in intended.items()):
            raise ControlPlaneError(
                "holdout_admin_review_conflict",
                "administrative review is append-only and its existing receipt differs",
            )
        return {
            "schema_version": HOLDOUT_ADMIN_CORRECTION_REVIEW_SCHEMA_VERSION,
            "status": "ADMINISTRATIVE_CORRECTION_REVIEW_ACCEPTED",
            "review_id": review_context["review_id"],
            "idempotent": True,
        }
    with conn:
        conn.execute(
            """INSERT INTO judgment_holdout_admin_correction_review_events
               (review_id, correction_id, program_id, training_episode_id, case_id,
                reviewer_id, reviewed_at, recorded_at, review_ref, review_json)
               VALUES (:review_id, :correction_id, :program_id, :training_episode_id,
                       :case_id, :reviewer_id, :reviewed_at, :recorded_at, :review_ref,
                       :review_json)""",
            {**intended, "review_id": review_context["review_id"], "recorded_at": _iso(recorded)},
        )
    return {
        "schema_version": HOLDOUT_ADMIN_CORRECTION_REVIEW_SCHEMA_VERSION,
        "status": "ADMINISTRATIVE_CORRECTION_REVIEW_ACCEPTED",
        "review_id": review_context["review_id"],
        "correction_id": correction_id,
        "idempotent": False,
    }


def _frozen_holdout_application_context(
    reference: str, *, correction: dict[str, Any], as_of: datetime,
) -> tuple[str, dict[str, Any], datetime] | None:
    path = _reference_path(reference).resolve()
    if not path.is_file():
        return None
    try:
        payload = _read_json(path)
    except ControlPlaneError:
        return None
    required = (
        "application_id", "program_id", "source_program_id", "training_episode_id",
        "case_id", "method_version", "method_scope", "application_author_id",
    )
    if payload.get("schema_version") != HOLDOUT_METHOD_APPLICATION_SCHEMA_VERSION:
        return None
    if any(payload.get(field) != correction[field] for field in (
        "program_id", "source_program_id", "training_episode_id", "case_id",
        "method_version", "method_scope",
    )) or any(not str(payload.get(field) or "").strip() for field in required):
        return None
    if payload.get("application_author_id") != correction["future_evaluator_id"]:
        return None
    if payload.get("outcome_body_access") != "NOT_OPENED_BEFORE_CONTROL_REGISTRATION":
        return None
    try:
        method_frozen_at = _parse_time(
            payload.get("method_frozen_at"), field="application.method_frozen_at",
        )
        correction_frozen_at = _parse_time(
            correction["method_frozen_at"], field="correction.method_frozen_at",
        )
        method_freeze_recorded_at = _parse_time(
            payload.get("method_freeze_recorded_at"), field="application.method_freeze_recorded_at",
        )
        correction_freeze_recorded_at = _parse_time(
            correction["method_freeze_recorded_at"], field="correction.method_freeze_recorded_at",
        )
        applied_at = _parse_time(payload.get("applied_at"), field="application.applied_at")
    except ControlPlaneError:
        return None
    if (
        method_frozen_at != correction_frozen_at
        or method_freeze_recorded_at != correction_freeze_recorded_at
    ):
        return None
    if applied_at < _parse_time(correction["method_freeze_recorded_at"], field="method_freeze_recorded_at") or applied_at > as_of:
        return None
    claims = payload.get("claims")
    stages = [item.get("stage_id") for item in claims] if isinstance(claims, list) and all(isinstance(item, dict) for item in claims) else []
    if stages != list(REQUIRED_SELECTION_STAGE_IDS):
        return None
    if payload.get("selection_status") not in SELECTION_STATUSES:
        return None
    return str(path), payload, applied_at


def r103_linked_holdout_administrative_gate(
    conn: sqlite3.Connection, *, program_id: str, source_program_id: str,
    training_episode_id: str, case_id: str, holdout_freeze_ref: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Project the append-only R-103 overlay without changing its sealed core."""
    if case_id != R103_HOLDOUT_CASE_ID:
        return {"state": "NOT_APPLICABLE", "actionable": False, "findings": []}
    context = _linked_holdout_context(
        conn,
        program_id=program_id, source_program_id=source_program_id,
        training_episode_id=training_episode_id, case_id=case_id,
    )
    if context["method_scope"] != R103_REQUIRED_METHOD_SCOPE:
        return {
            "state": "R103_SELECTION_METHOD_SCOPE_MISMATCH",
            "actionable": True,
            "findings": ["R-103 requires the frozen SELECTION_AND_BOUNDARY scope"],
        }
    if not context["method_frozen_at"] or not context["method_freeze_recorded_at"]:
        return {"state": "WAITING_FOR_METHOD_FREEZE", "actionable": False, "findings": []}
    corrections = conn.execute(
        """SELECT * FROM judgment_holdout_admin_correction_events
             WHERE program_id = ? AND source_program_id = ?
               AND training_episode_id = ? AND case_id = ?
               AND recorded_at <= ?
             ORDER BY recorded_at DESC, correction_id DESC""",
        (program_id, source_program_id, training_episode_id, case_id, _iso(as_of)),
    ).fetchall()
    if not corrections:
        return {
            "state": "ADMINISTRATIVE_CORRECTION_REQUIRED",
            "actionable": True,
            "findings": ["sealed R-103 core retains a stale R-102-specific administrative prerequisite"],
        }
    correction = dict(corrections[0])
    reviews = conn.execute(
        """SELECT * FROM judgment_holdout_admin_correction_review_events
             WHERE correction_id = ? AND recorded_at <= ?
             ORDER BY recorded_at DESC, review_id DESC""",
        (correction["correction_id"], _iso(as_of)),
    ).fetchall()
    if not reviews:
        return {
            "state": "ADMINISTRATIVE_CORRECTION_REVIEW_REQUIRED",
            "actionable": True,
            "findings": ["the latest R-103 administrative correction lacks an independent accepted review"],
        }
    try:
        review = _read_json(_reference_path(str(reviews[0]["review_ref"])).resolve())
        _validate_holdout_admin_review(
            correction, review,
            reviewed_at=_parse_time(reviews[0]["reviewed_at"], field="reviewed_at"),
            recorded_at=_parse_time(reviews[0]["recorded_at"], field="recorded_at"),
        )
    except (ControlPlaneError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "state": "ADMINISTRATIVE_CORRECTION_REVIEW_REQUIRED",
            "actionable": True,
            "findings": [exc.code if isinstance(exc, ControlPlaneError) else "administrative_review_unreadable"],
        }
    root = _reference_path(holdout_freeze_ref).resolve().parent
    application = _frozen_holdout_application_context(
        str(root / "05_frozen_method_application_prediction.json"),
        correction=correction, as_of=as_of,
    )
    if application is None:
        return {
            "state": "FROZEN_METHOD_APPLICATION_REQUIRED",
            "actionable": True,
            "findings": ["R-103 needs a fresh isolated D1-D5 frozen-method application"],
        }
    pre_review_ref = root / "06_independent_pre_reveal_receipt.json"
    if not pre_review_ref.is_file():
        return {
            "state": "PRE_REVEAL_REVIEW_REQUIRED",
            "actionable": True,
            "findings": ["R-103 frozen-method application lacks an independent pre-reveal receipt"],
        }
    try:
        _, pre_review, reviewed_at = _validate_pre_reveal_review_receipt(
            str(pre_review_ref), episode_id=case_id, registered_at=None,
        )
        if pre_review.get("application_id") != application[1]["application_id"]:
            raise ControlPlaneError("pre_reveal_application_mismatch", "pre-reveal review must bind the frozen method application")
        if pre_review.get("reviewer_id") in {
            correction["future_evaluator_id"], correction["outcome_custodian_id"],
        } or reviewed_at < application[2] or reviewed_at > as_of:
            raise ControlPlaneError("pre_reveal_reviewer_not_independent", "pre-reveal reviewer must be independent and review after application")
    except (ControlPlaneError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, ControlPlaneError) else "pre_reveal_review_unreadable"
        return {
            "state": "PRE_REVEAL_REVIEW_REQUIRED",
            "actionable": True,
            "findings": [code],
        }
    return {
        "state": "READY_FOR_CONTROL_REGISTRATION",
        "actionable": True,
        "findings": [],
        "correction_id": correction["correction_id"],
        "application_ref": application[0],
        "pre_reveal_review_ref": str(pre_review_ref.resolve()),
        "selection_status": application[1]["selection_status"],
    }


def _validate_pre_reveal_review_receipt(
    reference: str, *, episode_id: str, registered_at: datetime | None,
) -> tuple[str, dict[str, Any], datetime]:
    path = _reference_path(reference).resolve()
    _require_artifact(str(path), field="pre_reveal_review_receipt_ref")
    receipt = _read_json(path)
    if receipt.get("schema_version") != HOLDOUT_PRE_REVEAL_REVIEW_SCHEMA_VERSION:
        raise ControlPlaneError(
            "pre_reveal_review_schema_invalid",
            f"expected schema_version {HOLDOUT_PRE_REVEAL_REVIEW_SCHEMA_VERSION}",
        )
    if receipt.get("case_id") != episode_id:
        raise ControlPlaneError("pre_reveal_review_case_mismatch", "pre-reveal review belongs to another holdout episode")
    if receipt.get("verdict") != "PRE_REVEAL_EVALUATION_CONTRACT_ACCEPTED":
        raise ControlPlaneError("pre_reveal_review_verdict_invalid", "pre-reveal review must explicitly accept the evaluation contract")
    if receipt.get("outcome_body_access") != "NOT_OPENED_BEFORE_CONTROL_REGISTRATION":
        raise ControlPlaneError(
            "pre_reveal_review_access_invalid",
            "pre-reveal review must attest NOT_OPENED_BEFORE_CONTROL_REGISTRATION",
        )
    _required_text(receipt, "receipt_id")
    _required_text(receipt, "reviewer_id")
    reviewed_at = _parse_time(receipt.get("reviewed_at"), field="pre_reveal_review.reviewed_at")
    if registered_at is not None and reviewed_at > registered_at:
        raise ControlPlaneError(
            "pre_reveal_review_after_registration",
            "pre-reveal review must be completed no later than claim registration",
        )
    return str(path), receipt, reviewed_at


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
    episode_class = str(item.get("episode_class") or manifest.get("episode_class") or "PIPELINE_REHEARSAL").upper()
    selection_status = str(item.get("selection_status") or manifest.get("selection_status") or "NO_PRIMARY").upper()
    learning_eligibility = str(
        item.get("learning_eligibility") or manifest.get("learning_eligibility") or "MECHANISM_SETTLEMENT_ONLY"
    ).upper()
    program_lane = str(item.get("program_lane") or manifest.get("program_lane") or "UNASSIGNED").upper()
    outcome_access = str(item.get("outcome_access") or manifest.get("outcome_access") or "UNSPECIFIED").upper()
    training_program_raw = str(item.get("training_program_ref") or manifest.get("training_program_ref") or "").strip()
    training_program_ref = str(Path(training_program_raw).expanduser().resolve()) if training_program_raw else ""
    pre_review_raw = str(
        item.get("pre_reveal_review_receipt_ref")
        or manifest.get("pre_reveal_review_receipt_ref")
        or ""
    ).strip()
    pre_reveal_review_receipt_ref = (
        str(Path(pre_review_raw).expanduser().resolve()) if pre_review_raw else ""
    )
    pre_reveal_review_receipt_json = ""
    resolution_raw = str(
        item.get("selection_resolution_ref")
        or manifest.get("selection_resolution_ref")
        or ""
    ).strip()
    selection_resolution_ref = str(Path(resolution_raw).expanduser().resolve()) if resolution_raw else ""
    resolution_review_raw = str(
        item.get("selection_resolution_review_ref")
        or manifest.get("selection_resolution_review_ref")
        or ""
    ).strip()
    selection_resolution_review_ref = (
        str(Path(resolution_review_raw).expanduser().resolve()) if resolution_review_raw else ""
    )
    selection_outcome_custodian_id = str(
        item.get("selection_outcome_custodian_id")
        or manifest.get("selection_outcome_custodian_id")
        or ""
    ).strip()
    frozen_artifact_ref = _require_artifact(
        _required_text(item, "frozen_artifact_ref"), field="frozen_artifact_ref",
    )
    frozen_payload = _json_artifact_payload(frozen_artifact_ref)
    is_selection_candidate = bool(
        frozen_payload and frozen_payload.get("schema_version") == CANDIDATE_SCHEMA_VERSION
    )
    if episode_class not in EPISODE_CLASSES:
        raise ControlPlaneError("episode_class_invalid", f"unsupported episode_class: {episode_class}")
    if selection_status not in SELECTION_STATUSES:
        raise ControlPlaneError("selection_status_invalid", f"unsupported selection_status: {selection_status}")
    if learning_eligibility not in LEARNING_ELIGIBILITIES:
        raise ControlPlaneError("learning_eligibility_invalid", f"unsupported learning_eligibility: {learning_eligibility}")
    if program_lane not in PROGRAM_LANES:
        raise ControlPlaneError("program_lane_invalid", f"unsupported program_lane: {program_lane}")
    if outcome_access not in OUTCOME_ACCESS_STATES:
        raise ControlPlaneError("outcome_access_invalid", f"unsupported outcome_access: {outcome_access}")
    if selection_status == "SELECTION_ADMITTED" and episode_class != "JUDGMENT_SELECTION_EPISODE":
        raise ControlPlaneError(
            "selection_episode_metadata_inconsistent",
            "SELECTION_ADMITTED requires JUDGMENT_SELECTION_EPISODE",
        )
    if program_lane == "HISTORICAL_TRAINING":
        if outcome_access != "PIT_OUTCOME_SEALED" or learning_eligibility not in {
            "SELECTION_METHOD_ELIGIBLE", "BOUNDARY_METHOD_ELIGIBLE", "MECHANISM_SETTLEMENT_ONLY",
        }:
            raise ControlPlaneError(
                "historical_training_identity_inconsistent",
                "HISTORICAL_TRAINING requires sealed PIT outcomes and training-capable eligibility",
            )
        _require_artifact(training_program_ref, field="training_program_ref")
        if selection_status == "SELECTION_ADMITTED" and is_selection_candidate:
            if learning_eligibility != "SELECTION_METHOD_ELIGIBLE":
                raise ControlPlaneError(
                    "selection_episode_metadata_inconsistent",
                    "historical SELECTION_ADMITTED claims require SELECTION_METHOD_ELIGIBLE",
                )
        elif selection_status != "SELECTION_ADMITTED" and (
            selection_resolution_ref or selection_resolution_review_ref or selection_outcome_custodian_id
        ):
            raise ControlPlaneError(
                "selection_resolution_not_permitted",
                "selection resolution, review and custodian bindings require SELECTION_ADMITTED",
            )
    elif program_lane == "HISTORICAL_HOLDOUT":
        if outcome_access != "PIT_OUTCOME_SEALED" or learning_eligibility != "EVALUATION_ONLY":
            raise ControlPlaneError(
                "historical_holdout_identity_inconsistent",
                "HISTORICAL_HOLDOUT requires sealed PIT outcomes and EVALUATION_ONLY",
            )
        _require_artifact(training_program_ref, field="training_program_ref")
        if not pre_reveal_review_receipt_ref:
            raise ControlPlaneError(
                "pre_reveal_review_receipt_missing",
                "HISTORICAL_HOLDOUT requires pre_reveal_review_receipt_ref",
            )
        _, pre_reveal_review_receipt, _ = _validate_pre_reveal_review_receipt(
            pre_reveal_review_receipt_ref,
            episode_id=episode_id,
            registered_at=_parse_time(registered_at, field="registered_at"),
        )
        pre_reveal_review_receipt_json = _json(pre_reveal_review_receipt)
    elif pre_reveal_review_receipt_ref:
        raise ControlPlaneError(
            "pre_reveal_review_receipt_not_permitted",
            "pre_reveal_review_receipt_ref is reserved for HISTORICAL_HOLDOUT",
        )
    elif selection_resolution_ref or selection_resolution_review_ref or selection_outcome_custodian_id:
        raise ControlPlaneError(
            "selection_resolution_not_permitted",
            "selection resolution, review and custodian bindings are reserved for historical selection claims",
        )
    elif program_lane == "HISTORICAL_TEACHING":
        if outcome_access != "OUTCOME_EXPOSED" or learning_eligibility != "TEACHING_ONLY" or selection_status != "NO_PRIMARY":
            raise ControlPlaneError(
                "historical_teaching_identity_inconsistent",
                "HISTORICAL_TEACHING requires exposed outcomes, NO_PRIMARY and TEACHING_ONLY",
            )
        _require_artifact(training_program_ref, field="training_program_ref")
    elif program_lane == "LIVE_SENTINEL":
        if outcome_access != "NOT_YET_RELEASED":
            raise ControlPlaneError("live_sentinel_outcome_access_invalid", "LIVE_SENTINEL requires NOT_YET_RELEASED")
        expected = "SELECTION_METHOD_ELIGIBLE" if selection_status == "SELECTION_ADMITTED" else "MECHANISM_SETTLEMENT_ONLY"
        if learning_eligibility != expected:
            raise ControlPlaneError("live_sentinel_learning_identity_invalid", f"LIVE_SENTINEL requires {expected}")
    elif selection_status == "SELECTION_ADMITTED" and learning_eligibility != "SELECTION_METHOD_ELIGIBLE":
        raise ControlPlaneError(
            "selection_episode_metadata_inconsistent",
            "unassigned SELECTION_ADMITTED episodes require SELECTION_METHOD_ELIGIBLE",
        )
    elif selection_status == "NO_PRIMARY" and learning_eligibility not in {"BOUNDARY_METHOD_ELIGIBLE", "MECHANISM_SETTLEMENT_ONLY"}:
        raise ControlPlaneError(
            "no_primary_learning_not_permitted",
            "unassigned NO_PRIMARY episodes may settle mechanisms but cannot enter method learning",
        )
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
        "frozen_artifact_ref": frozen_artifact_ref,
        "source_contract_ref": _require_artifact(_required_text(item, "source_contract_ref"), field="source_contract_ref"),
        "measurement_contract_ref": _require_artifact(_required_text(item, "measurement_contract_ref"), field="measurement_contract_ref"),
        "episode_class": episode_class,
        "selection_status": selection_status,
        "learning_eligibility": learning_eligibility,
        "program_lane": program_lane,
        "outcome_access": outcome_access,
        "training_program_ref": training_program_ref,
        "pre_reveal_review_receipt_ref": pre_reveal_review_receipt_ref,
        "pre_reveal_review_receipt_json": pre_reveal_review_receipt_json,
        "selection_resolution_ref": selection_resolution_ref,
        "selection_resolution_review_ref": selection_resolution_review_ref,
        "selection_outcome_custodian_id": selection_outcome_custodian_id,
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


def _live_forward_validation(contract: dict[str, Any]) -> dict[str, Any]:
    """Reuse the frozen outcome-contract validator; do not re-specify it here."""
    try:
        from scripts.outcome_acquisition import validate_live_forward_outcome_contract
    except ModuleNotFoundError:
        from outcome_acquisition import validate_live_forward_outcome_contract
    return validate_live_forward_outcome_contract(contract)


def _frozen_locator_path(locator: Any, *, contract_path: Path) -> Path:
    """Resolve a structured ``file:line`` locator emitted by the forward freeze."""
    if not isinstance(locator, str) or not locator.strip():
        raise ControlPlaneError("forward_freeze_locator_missing", "each signal must retain frozen_locator")
    candidate = locator.strip()
    path_text, separator, tail = candidate.rpartition(":")
    if not separator or not tail.isdigit():
        path_text = candidate
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = contract_path.parent / path
    if not path.is_file():
        raise ControlPlaneError("forward_freeze_artifact_missing", f"frozen_locator does not resolve to a file: {locator}")
    return path.resolve()


def frozen_artifact_for_live_forward_contract(contract: dict[str, Any], *, contract_path: Path) -> Path:
    """Derive the sole freeze artifact from explicit signal locators, never Markdown prose."""
    pair = contract.get("mechanism_signal_pair") if isinstance(contract.get("mechanism_signal_pair"), dict) else {}
    signals = pair.get("signals") if isinstance(pair.get("signals"), list) else []
    locations = {
        _frozen_locator_path(signal.get("frozen_locator"), contract_path=contract_path)
        for signal in signals if isinstance(signal, dict)
    }
    if len(locations) != 1:
        raise ControlPlaneError(
            "forward_freeze_artifact_ambiguous",
            "a live forward contract must have exactly one explicit frozen artifact across its signals",
        )
    return locations.pop()


def live_forward_registration_manifest(
    contract: dict[str, Any], *, contract_path: Path, frozen_artifact_ref: str | Path | None = None,
) -> dict[str, Any]:
    """Project a reviewed forward outcome contract into independent clock entries.

    The projection is deliberately mechanical: it only schedules the outcome
    contracts already frozen in ``calibration_ledger``.  It adds neither a
    forecast, a mechanism verdict, nor a selection conclusion.
    """
    validation = _live_forward_validation(contract)
    if validation.get("state") != "REVIEWABLE":
        findings = list(validation.get("invalid_findings") or []) + list(validation.get("incomplete_findings") or [])
        raise ControlPlaneError("live_forward_contract_not_reviewable", "; ".join(findings) or "contract is not reviewable")
    identity = contract.get("research_identity") if isinstance(contract.get("research_identity"), dict) else {}
    episode_id = _required_text({"episode_id": contract.get("case_id")}, "episode_id")
    company_id = _required_text({"company_id": identity.get("company_cluster_id")}, "company_id")
    frozen_at = _required_text({"frozen_at": contract.get("simulation_cutoff")}, "frozen_at")
    freeze_path = Path(frozen_artifact_ref).expanduser().resolve() if frozen_artifact_ref else frozen_artifact_for_live_forward_contract(contract, contract_path=contract_path)
    _require_artifact(str(freeze_path), field="frozen_artifact_ref")
    signal_stages = {
        str(signal.get("claim_id") or ""): str(signal.get("stage") or "")
        for signal in ((contract.get("mechanism_signal_pair") or {}).get("signals") or [])
        if isinstance(signal, dict)
    }
    pair = contract.get("mechanism_signal_pair") if isinstance(contract.get("mechanism_signal_pair"), dict) else {}
    selection_status = str(pair.get("selection_status") or "NO_PRIMARY").upper()
    if selection_status not in SELECTION_STATUSES:
        raise ControlPlaneError("selection_status_invalid", f"unsupported frozen selection_status: {selection_status}")
    episode_class = "JUDGMENT_SELECTION_EPISODE" if selection_status == "SELECTION_ADMITTED" else "MECHANISM_SIGNAL_PROBE"
    learning_eligibility = "SELECTION_METHOD_ELIGIBLE" if selection_status == "SELECTION_ADMITTED" else "MECHANISM_SETTLEMENT_ONLY"
    claims = ((contract.get("calibration_ledger") or {}).get("claims") or [])
    feedback_items: list[dict[str, Any]] = []
    contract_ref = str(contract_path.resolve())
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
        window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
        opens = _parse_time(window.get("opens_after"), field=f"claim[{index}].opens_after")
        closes = _parse_time(window.get("closes_at"), field=f"claim[{index}].closes_at")
        claim_id = _required_text(claim, "claim_id")
        stage_id = str(claim.get("operating_clock") or signal_stages.get(claim_id) or "OPERATING_OUTCOME")
        feedback_items.append({
            "claim_id": claim_id,
            "stage_id": stage_id,
            "source_kind": ",".join(str(value) for value in outcome.get("allowed_source_types") or []),
            "source_ref": f"{contract_ref}#/calibration_ledger/claims/{index}/observable_outcome",
            "eligible_at": _iso(opens + timedelta(seconds=1)),
            "overdue_at": _iso(closes),
            "settlement_version_policy": outcome.get("settlement_version_policy"),
            "frozen_artifact_ref": str(freeze_path),
            "source_contract_ref": contract_ref,
            "measurement_contract_ref": f"{contract_ref}#/calibration_ledger/claims/{index}/observable_outcome/metric_reconstruction_contract",
            "episode_class": episode_class,
            "selection_status": selection_status,
            "learning_eligibility": learning_eligibility,
            "program_lane": "LIVE_SENTINEL",
            "outcome_access": "NOT_YET_RELEASED",
        })
    return {
        "schema_version": REGISTRATION_SCHEMA_VERSION,
        "episode_id": episode_id,
        "company_id": company_id,
        "frozen_at": frozen_at,
        "episode_class": episode_class,
        "selection_status": selection_status,
        "learning_eligibility": learning_eligibility,
        "program_lane": "LIVE_SENTINEL",
        "outcome_access": "NOT_YET_RELEASED",
        "feedback_items": feedback_items,
    }


def register_live_forward_contract(
    conn: sqlite3.Connection, *, contract_path: str | Path, frozen_artifact_ref: str | Path | None = None,
    registered_at: str | None = None,
) -> dict[str, Any]:
    path = Path(contract_path).expanduser().resolve()
    manifest = live_forward_registration_manifest(
        _read_json(path), contract_path=path, frozen_artifact_ref=frozen_artifact_ref,
    )
    return register_manifest(conn, manifest, registered_at=registered_at)


def sync_live_forward_contracts(
    conn: sqlite3.Connection, *, contract_root: str | Path, registered_at: str | None = None,
) -> dict[str, Any]:
    """Register every reviewed contract once; retain bad contracts as visible issues."""
    root = Path(contract_root).expanduser()
    if not root.is_dir():
        raise ControlPlaneError("live_forward_contract_root_missing", f"contract root is missing: {root}")
    registered: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for path in sorted(root.rglob("08_outcome_acquisition_contract.json")):
        try:
            result = register_live_forward_contract(conn, contract_path=path, registered_at=registered_at)
            registered.append({"contract_path": str(path), "result": result})
        except ControlPlaneError as exc:
            issues.append({"contract_path": str(path), "code": exc.code, "detail": exc.detail})
    return {"schema_version": SCHEMA_VERSION, "registered": registered, "issues": issues}


def _expect_exact_keys(value: dict[str, Any], *, expected: set[str], context: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ControlPlaneError("candidate_condition_field_forbidden", f"{context} contains forbidden fields: {', '.join(unknown)}")
    if missing:
        raise ControlPlaneError("candidate_condition_field_missing", f"{context} is missing fields: {', '.join(missing)}")


def _candidate_condition_row(
    manifest: dict[str, Any], *, condition: dict[str, Any], condition_contract_ref: str, registered_at: str,
) -> dict[str, str]:
    _expect_exact_keys(
        condition,
        expected={"condition_id", "due_at", "official_source_query", "next_step", "status"},
        context="candidate condition",
    )
    candidate_id = _required_text(manifest, "candidate_id")
    company_id = _required_text(manifest, "company_id")
    cutoff_at = _iso(_parse_time(manifest.get("cutoff_at"), field="cutoff_at"))
    condition_id = _required_text(condition, "condition_id")
    due_at = _iso(_parse_time(condition.get("due_at"), field="due_at"))
    if _parse_time(due_at, field="due_at") < _parse_time(cutoff_at, field="cutoff_at"):
        raise ControlPlaneError("candidate_condition_due_before_cutoff", "condition due_at cannot precede cutoff_at")
    next_step = _required_text(condition, "next_step").upper()
    if next_step not in CANDIDATE_CONDITION_NEXT_STEPS:
        raise ControlPlaneError("candidate_condition_next_step_invalid", f"unsupported next_step: {next_step}")
    status = _required_text(condition, "status").upper()
    if status not in CANDIDATE_CONDITION_STATUSES:
        raise ControlPlaneError("candidate_condition_status_invalid", f"unsupported candidate status: {status}")
    query = condition.get("official_source_query")
    if not isinstance(query, dict):
        raise ControlPlaneError("candidate_condition_query_invalid", "official_source_query must be an object")
    _expect_exact_keys(
        query,
        expected={"source_kind", "issuer_code", "published_after", "required_title_terms"},
        context="official_source_query",
    )
    source_kind = _required_text(query, "source_kind").upper()
    if source_kind not in CANDIDATE_CONDITION_SOURCE_KINDS:
        raise ControlPlaneError("candidate_condition_source_kind_invalid", f"unsupported official source kind: {source_kind}")
    _required_text(query, "issuer_code")
    published_after = _iso(_parse_time(query.get("published_after"), field="official_source_query.published_after"))
    if _parse_time(published_after, field="official_source_query.published_after") < _parse_time(cutoff_at, field="cutoff_at"):
        raise ControlPlaneError(
            "candidate_condition_query_before_cutoff",
            "official_source_query.published_after cannot precede cutoff_at",
        )
    title_terms = query.get("required_title_terms")
    if not isinstance(title_terms, list) or not title_terms or any(not isinstance(term, str) or not term.strip() for term in title_terms):
        raise ControlPlaneError("candidate_condition_title_terms_invalid", "required_title_terms must be a non-empty list of text")
    return {
        "candidate_condition_item_id": _candidate_condition_item_id(candidate_id, condition_id),
        "candidate_id": candidate_id,
        "condition_id": condition_id,
        "company_id": company_id,
        "cutoff_at": cutoff_at,
        "due_at": due_at,
        "official_source_query_json": _json({
            "source_kind": source_kind,
            "issuer_code": query["issuer_code"].strip(),
            "published_after": published_after,
            "required_title_terms": [term.strip() for term in title_terms],
        }),
        "next_step": next_step,
        "status": status,
        "condition_contract_ref": condition_contract_ref,
        "registered_at": registered_at,
    }


def register_candidate_condition_contract(
    conn: sqlite3.Connection, *, contract_path: str | Path, registered_at: str | None = None,
) -> dict[str, Any]:
    path = Path(contract_path).expanduser().resolve()
    manifest = _read_json(path)
    _expect_exact_keys(
        manifest,
        expected={"schema_version", "candidate_id", "company_id", "cutoff_at", "conditions"},
        context="candidate condition contract",
    )
    if manifest.get("schema_version") != CANDIDATE_CONDITION_SCHEMA_VERSION:
        raise ControlPlaneError(
            "candidate_condition_schema_invalid",
            f"expected schema_version {CANDIDATE_CONDITION_SCHEMA_VERSION}",
        )
    conditions = manifest.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ControlPlaneError("candidate_conditions_missing", "candidate condition contract requires a non-empty conditions list")
    registered_at_iso = _iso(_parse_time(registered_at or _now(), field="registered_at"))
    rows = [
        _candidate_condition_row(
            manifest, condition=condition, condition_contract_ref=str(path), registered_at=registered_at_iso,
        )
        for condition in conditions if isinstance(condition, dict)
    ]
    if len(rows) != len(conditions):
        raise ControlPlaneError("candidate_condition_invalid", "each conditions entry must be an object")
    if len({row["candidate_condition_item_id"] for row in rows}) != len(rows):
        raise ControlPlaneError("candidate_condition_duplicate", "one contract cannot repeat a candidate condition")
    results: list[dict[str, Any]] = []
    columns = tuple(rows[0])
    with conn:
        for row in rows:
            existing = conn.execute(
                "SELECT * FROM judgment_candidate_conditions WHERE candidate_condition_item_id = ?",
                (row["candidate_condition_item_id"],),
            ).fetchone()
            if existing:
                comparable = {column: existing[column] for column in columns if column not in {"registered_at", "condition_contract_ref"}}
                intended = {column: row[column] for column in columns if column not in {"registered_at", "condition_contract_ref"}}
                if comparable != intended:
                    raise ControlPlaneError(
                        "candidate_condition_registration_conflict",
                        f"candidate condition is already registered with different frozen fields: {row['candidate_condition_item_id']}",
                    )
                rehomed = existing["condition_contract_ref"] != row["condition_contract_ref"]
                if rehomed:
                    conn.execute(
                        "UPDATE judgment_candidate_conditions SET condition_contract_ref = ? WHERE candidate_condition_item_id = ?",
                        (row["condition_contract_ref"], row["candidate_condition_item_id"]),
                    )
                results.append({
                    "candidate_condition_item_id": row["candidate_condition_item_id"],
                    "registered": False,
                    "idempotent": True,
                    "worktree_rehomed": rehomed,
                })
                continue
            conn.execute(
                f"INSERT INTO judgment_candidate_conditions ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
            results.append({"candidate_condition_item_id": row["candidate_condition_item_id"], "registered": True, "idempotent": False})
    return {"schema_version": CANDIDATE_CONDITION_INBOX_SCHEMA_VERSION, "registered": results}


def sync_candidate_condition_contracts(
    conn: sqlite3.Connection, *, contract_root: str | Path, registered_at: str | None = None,
) -> dict[str, Any]:
    root = Path(contract_root).expanduser()
    if not root.is_dir():
        raise ControlPlaneError("candidate_condition_contract_root_missing", f"candidate condition contract root is missing: {root}")
    registered: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for path in sorted(root.rglob("00_candidate_condition_contract.json")):
        try:
            result = register_candidate_condition_contract(conn, contract_path=path, registered_at=registered_at)
            registered.append({"contract_path": str(path), "result": result})
        except ControlPlaneError as exc:
            issues.append({"contract_path": str(path), "code": exc.code, "detail": exc.detail})
    return {"schema_version": CANDIDATE_CONDITION_INBOX_SCHEMA_VERSION, "registered": registered, "issues": issues}


def reconcile_candidate_conditions(conn: sqlite3.Connection, *, as_of: str) -> dict[str, Any]:
    as_of_dt = _parse_time(as_of, field="as_of", allow_date=True)
    rows = conn.execute(
        "SELECT * FROM judgment_candidate_conditions ORDER BY due_at, candidate_condition_item_id"
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        due_at = _parse_time(item["due_at"], field="due_at")
        items.append({
            "candidate_condition_item_id": item["candidate_condition_item_id"],
            "candidate_id": item["candidate_id"],
            "condition_id": item["condition_id"],
            "company_id": item["company_id"],
            "cutoff_at": item["cutoff_at"],
            "due_at": item["due_at"],
            "official_source_query": _loads(item["official_source_query_json"]),
            "next_step": item["next_step"],
            "status": item["status"],
            "time_state": "WAITING" if as_of_dt < due_at else "DUE",
        })
    return {
        "schema_version": CANDIDATE_CONDITION_INBOX_SCHEMA_VERSION,
        "as_of": _iso(as_of_dt),
        "items": items,
    }


def _json_artifact_payload(reference: str) -> dict[str, Any] | None:
    path = Path(str(reference).split("#", 1)[0]).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _selection_registration_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0]
    return {
        "schema_version": REGISTRATION_SCHEMA_VERSION,
        "episode_id": first["episode_id"],
        "company_id": first["company_id"],
        "selection_status": first["selection_status"],
        "learning_eligibility": first["learning_eligibility"],
        "feedback_items": [
            {
                field: row[field]
                for field in (
                    "claim_id", "stage_id", "source_kind", "source_ref", "frozen_at",
                    "eligible_at", "overdue_at", "settlement_version_policy",
                )
            }
            for row in rows
        ],
    }


def _validate_selection_resolution_review(
    review: dict[str, Any], *, resolution: dict[str, Any], registered_at: datetime,
) -> None:
    if review.get("schema_version") != "judgment-selection-resolution-amendment-review.v1":
        raise ControlPlaneError(
            "selection_resolution_review_schema_invalid",
            "selection resolution review uses an unsupported schema",
        )
    for field in ("case_id", "freeze_id", "amendment_id", "author_id", "selector_id"):
        if review.get(field) != resolution.get(field):
            raise ControlPlaneError(
                "selection_resolution_review_identity_mismatch",
                f"selection resolution review {field} does not match the amendment",
            )
    if review.get("status") != "INDEPENDENTLY_ACCEPTED_PRE_OUTCOME":
        raise ControlPlaneError(
            "selection_resolution_review_not_accepted",
            "selection resolution amendment requires independent pre-outcome acceptance",
        )
    if review.get("reviewed_amendment") != resolution:
        raise ControlPlaneError(
            "selection_resolution_review_snapshot_mismatch",
            "selection resolution review must retain the exact amendment snapshot",
        )
    reviewer_id = _required_text(review, "reviewer_id")
    if reviewer_id in {
        str(resolution.get("author_id") or ""),
        str(resolution.get("selector_id") or ""),
    }:
        raise ControlPlaneError(
            "selection_resolution_reviewer_not_independent",
            "selection resolution reviewer must differ from the author and selector",
        )
    reviewed_at = _parse_time(review.get("reviewed_at"), field="selection_resolution_review.reviewed_at")
    review_recorded_at = _parse_time(
        review.get("recorded_at"), field="selection_resolution_review.recorded_at",
    )
    amendment_created_at = _parse_time(
        resolution.get("created_at"), field="selection_resolution.created_at",
    )
    if not amendment_created_at <= reviewed_at <= review_recorded_at <= registered_at:
        raise ControlPlaneError(
            "selection_resolution_review_clock_invalid",
            "amendment creation, review, review recording and claim registration clocks are out of order",
        )


def _require_selection_candidate_review(
    conn: sqlite3.Connection, rows: list[dict[str, Any]], *, registered_at: datetime,
) -> dict[tuple[str, str], dict[str, Any]]:
    contexts: dict[tuple[str, str], dict[str, Any]] = {}
    checked: set[tuple[str, str]] = set()
    for row in rows:
        if (
            row.get("program_lane") != "HISTORICAL_TRAINING"
            or row.get("selection_status") != "SELECTION_ADMITTED"
        ):
            continue
        manifest_candidate = _json_artifact_payload(str(row.get("frozen_artifact_ref") or ""))
        manifest_is_candidate = bool(
            manifest_candidate
            and manifest_candidate.get("schema_version") == CANDIDATE_SCHEMA_VERSION
        )
        identity = (str(row.get("episode_id") or ""), str(row.get("training_program_ref") or ""))
        if identity in checked:
            continue
        checked.add(identity)
        try:
            episode = conn.execute(
                """SELECT episode.training_episode_id, episode.program_id,
                          episode.company_id, episode.cutoff_at,
                          program.program_state, program.required_selection_admission_version
                     FROM judgment_training_episodes AS episode
                     JOIN judgment_training_programs AS program USING (program_id)
                    WHERE episode.case_id = ?
                      AND episode.lane = 'HISTORICAL_TRAINING'
                      AND program.contract_ref = ?""",
                identity,
            ).fetchone()
        except sqlite3.Error as exc:
            if not manifest_is_candidate:
                continue
            raise ControlPlaneError(
                "selection_candidate_program_registration_required",
                "selection candidate must be registered in the training program before feedback control",
            ) from exc
        if not episode:
            if not manifest_is_candidate:
                continue
            raise ControlPlaneError(
                "selection_candidate_program_registration_required",
                "selection candidate must be registered in the training program before feedback control",
            )
        artifact_rows = conn.execute(
            """SELECT artifact_event_id, artifact_kind, artifact_ref, recorded_at, content_json
                 FROM judgment_training_artifact_events
                WHERE training_episode_id = ? AND artifact_kind IN ('case_ref', 'selection_review_ref')""",
            (episode["training_episode_id"],),
        ).fetchall()
        artifacts = {artifact["artifact_kind"]: artifact for artifact in artifact_rows}
        case_artifact = artifacts.get("case_ref")
        review_artifact = artifacts.get("selection_review_ref")
        stored_candidate = (
            json.loads(case_artifact["content_json"])
            if case_artifact and case_artifact["content_json"]
            else None
        )
        stored_is_candidate = bool(
            isinstance(stored_candidate, dict)
            and stored_candidate.get("schema_version") == CANDIDATE_SCHEMA_VERSION
        )
        if not manifest_is_candidate and not stored_is_candidate:
            continue
        if not case_artifact or not stored_is_candidate:
            raise ControlPlaneError(
                "selection_candidate_snapshot_missing",
                "registered selection candidate snapshot is missing",
            )
        candidate_result = validate_selection_candidate(stored_candidate)
        if candidate_result.get("state") != "REVIEWABLE":
            raise ControlPlaneError(
                "selection_candidate_invalid",
                "selection candidate is not reviewable: " + "; ".join(candidate_result.get("findings", [])),
            )
        admission = stored_candidate.get("selection_admission_contract")
        candidate_admission_version = admission.get("version") if isinstance(admission, dict) else None
        if episode["required_selection_admission_version"] != candidate_admission_version:
            raise ControlPlaneError(
                "selection_candidate_admission_version_mismatch",
                "selection candidate admission contract must exactly match its registered program requirement",
            )
        if not manifest_is_candidate or stored_candidate != manifest_candidate:
            raise ControlPlaneError(
                "selection_candidate_snapshot_mismatch",
                "feedback registration candidate differs from the registered frozen snapshot",
            )
        if not review_artifact or not review_artifact["content_json"]:
            raise ControlPlaneError(
                "selection_review_required",
                "selection candidate requires an accepted independent pre-outcome review",
            )
        review = json.loads(review_artifact["content_json"])
        review_result = validate_selection_review(
            review,
            candidate=stored_candidate,
            case_artifact_ref=case_artifact["artifact_ref"],
            receipt_recorded_at=review_artifact["recorded_at"],
        )
        if review_result.get("state") != "REVIEWABLE":
            raise ControlPlaneError(
                "selection_review_invalid",
                "selection review is not admissible: " + "; ".join(review_result.get("findings", [])),
            )
        if episode["program_state"] != "ACTIVE":
            raise ControlPlaneError(
                "selection_training_program_not_active",
                "DRAFT training programs cannot register historical selection outcome claims",
            )
        episode_rows = [
            item for item in rows
            if (item["episode_id"], item["training_program_ref"]) == identity
        ]
        if (
            tuple(item["stage_id"] for item in episode_rows) not in SELECTION_STAGE_ORDERS
            or any(item["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE" for item in episode_rows)
        ):
            raise ControlPlaneError(
                "selection_feedback_claim_bundle_invalid",
                "historical selection registration requires the ordered five-layer D1-D5 bundle, with optional D3 product volume",
            )
        for item in episode_rows:
            _require_artifact(
                str(item.get("selection_resolution_ref") or ""),
                field="selection_resolution_ref",
            )
            _require_artifact(
                str(item.get("selection_resolution_review_ref") or ""),
                field="selection_resolution_review_ref",
            )
            if not str(item.get("selection_outcome_custodian_id") or "").strip():
                raise ControlPlaneError(
                    "selection_outcome_custodian_missing",
                    "historical selection registration requires an independent outcome custodian",
                )
        for field in (
            "frozen_artifact_ref", "source_contract_ref", "measurement_contract_ref",
            "selection_resolution_ref", "selection_resolution_review_ref",
            "selection_outcome_custodian_id",
        ):
            if len({str(item[field]) for item in episode_rows}) != 1:
                raise ControlPlaneError(
                    "selection_registration_binding_mismatch",
                    f"all historical selection claims must share {field}",
                )
        source_contract = _read_json(_reference_path(episode_rows[0]["source_contract_ref"]).resolve())
        measurement_contract = _read_json(
            _reference_path(episode_rows[0]["measurement_contract_ref"]).resolve(),
        )
        if (
            source_contract.get("schema_version") != "judgment-outcome-acquisition-contract.v1"
            or source_contract.get("case_id") != stored_candidate.get("case_id")
            or source_contract.get("company_id") != stored_candidate.get("company_id")
            or _parse_time(source_contract.get("cutoff_at"), field="source_contract.cutoff_at")
            != _parse_time(stored_candidate.get("cutoff_at"), field="candidate.cutoff_at")
        ):
            raise ControlPlaneError(
                "selection_source_contract_identity_invalid",
                "selection source contract does not match the frozen candidate identity",
            )
        source_clocks = source_contract.get("clocks")
        if not isinstance(source_clocks, list) or [
            (item.get("claim_id"), item.get("stage_id")) for item in source_clocks
            if isinstance(item, dict)
        ] != [(item["claim_id"], item["stage_id"]) for item in episode_rows]:
            raise ControlPlaneError(
                "selection_source_contract_claims_invalid",
                "selection source contract must bind the ordered registered claims",
            )
        if (
            measurement_contract.get("schema_version") != "judgment-selection-measurement-contract.v1"
            or measurement_contract.get("case_id") != stored_candidate.get("case_id")
            or measurement_contract.get("freeze_id") != stored_candidate.get("freeze_id")
        ):
            raise ControlPlaneError(
                "selection_measurement_contract_identity_invalid",
                "selection measurement contract does not match the frozen candidate identity",
            )
        try:
            from scripts.judgment_selection_peer import validate_peer_contract_binding
        except ModuleNotFoundError:
            from judgment_selection_peer import validate_peer_contract_binding
        peer_binding_findings = validate_peer_contract_binding(
            stored_candidate, source_contract, measurement_contract,
        )
        if peer_binding_findings:
            raise ControlPlaneError(
                "selection_peer_contract_binding_invalid",
                "selection peer panel/source/measurement binding is invalid: "
                + "; ".join(peer_binding_findings),
            )
        resolution = _read_json(
            _reference_path(episode_rows[0]["selection_resolution_ref"]).resolve(),
        )
        resolution_review = _read_json(
            _reference_path(episode_rows[0]["selection_resolution_review_ref"]).resolve(),
        )
        try:
            from scripts.judgment_selection_feedback import validate_selection_resolution_amendment
        except ModuleNotFoundError:
            from judgment_selection_feedback import validate_selection_resolution_amendment
        registration_snapshot = _selection_registration_snapshot(episode_rows)
        resolution_result = validate_selection_resolution_amendment(
            resolution,
            frozen_case=stored_candidate,
            measurement_contract=measurement_contract,
            registration=registration_snapshot,
        )
        if resolution_result.get("state") != "CANDIDATE_REVIEWABLE":
            raise ControlPlaneError(
                "selection_resolution_invalid",
                "selection resolution amendment is not reviewable: "
                + "; ".join(resolution_result.get("findings", [])),
            )
        _validate_selection_resolution_review(
            resolution_review, resolution=resolution, registered_at=registered_at,
        )
        custodian_id = episode_rows[0]["selection_outcome_custodian_id"]
        if custodian_id in {
            resolution.get("author_id"), resolution.get("selector_id"),
            resolution_review.get("reviewer_id"),
        }:
            raise ControlPlaneError(
                "selection_outcome_custodian_not_independent",
                "outcome custodian must differ from the amendment author, selector and reviewer",
            )
        contexts[identity] = {
            "program_id": episode["program_id"],
            "program_state": episode["program_state"],
            "training_episode_id": episode["training_episode_id"],
            "program_reservation_event_id": f"JTAE:{case_artifact['artifact_event_id']}",
            "case_artifact_ref": case_artifact["artifact_ref"],
            "case_artifact_recorded_at": case_artifact["recorded_at"],
            "candidate": stored_candidate,
            "selection_review": review,
            "source_contract": source_contract,
            "measurement_contract": measurement_contract,
            "registration": registration_snapshot,
            "resolution": resolution,
            "resolution_review": resolution_review,
            "custodian_id": custodian_id,
            "rows": episode_rows,
        }
    return contexts


def _selection_claim_registration_payload(
    context: dict[str, Any], *, registration_event_id: str,
) -> dict[str, Any]:
    return {
        "registration_schema_version": REGISTRATION_SCHEMA_VERSION,
        "registration_event_id": registration_event_id,
        "program_id": context["program_id"],
        "program_state": context["program_state"],
        "training_episode_id": context["training_episode_id"],
        "program_reservation_event_id": context["program_reservation_event_id"],
        "frozen_case_snapshot": deepcopy(context["candidate"]),
        "selection_review_snapshot": deepcopy(context["selection_review"]),
        "source_contract_snapshot": deepcopy(context["source_contract"]),
        "measurement_contract_snapshot": deepcopy(context["measurement_contract"]),
        "registration_snapshot": deepcopy(context["registration"]),
        "selection_resolution_snapshot": deepcopy(context["resolution"]),
        "selection_resolution_review_snapshot": deepcopy(context["resolution_review"]),
        "selection_outcome_custodian_id": context["custodian_id"],
    }


def _selection_activation_snapshot(
    context: dict[str, Any], *, registered_at: str,
    registration_event_ids: dict[str, str], outcome_release_event_id: str,
) -> dict[str, Any]:
    resolution = context["resolution"]
    resolution_review = context["resolution_review"]
    return {
        "schema_version": "judgment-selection-resolution-activation.v1",
        "activation_id": f"JSELRESACT:{resolution['case_id']}:{resolution['amendment_id']}",
        "case_id": resolution["case_id"],
        "freeze_id": resolution["freeze_id"],
        "amendment_id": resolution["amendment_id"],
        "amendment_review_id": resolution_review["review_id"],
        "activated_at": registered_at,
        "recorded_at": registered_at,
        "activation_source": "CONTROL_DB_RECONSTRUCTED",
        "activation_status": "ACTIVE_FOR_OUTCOME_SETTLEMENT",
        "program_state": "ACTIVE",
        "program_reservation_status": "REGISTERED",
        "feedback_control_registration_status": "REGISTERED",
        "outcome_release_status": "RELEASED_TO_INDEPENDENT_CUSTODIAN",
        "registered_claim_ids": [
            item["claim_id"] for item in context["registration"]["feedback_items"]
        ],
        "program_id": context["program_id"],
        "training_episode_id": context["training_episode_id"],
        "program_reservation_event_id": context["program_reservation_event_id"],
        "feedback_control_registration_event_ids": registration_event_ids,
        "outcome_release_event_id": outcome_release_event_id,
        "custodian_id": context["custodian_id"],
    }


def _require_r103_linked_holdout_registration(
    conn: sqlite3.Connection, rows: list[dict[str, Any]], *, registered_at: datetime,
) -> None:
    """Do not let a hand-written holdout manifest bypass R-103's overlay gate."""
    candidates = [
        row for row in rows
        if row.get("program_lane") == "HISTORICAL_HOLDOUT"
        and row.get("episode_id") == R103_HOLDOUT_CASE_ID
    ]
    if not candidates:
        return
    bindings = {
        (str(row["training_program_ref"]), str(row["episode_id"]))
        for row in candidates
    }
    if len(bindings) != 1:
        raise ControlPlaneError(
            "r103_holdout_registration_binding_mismatch",
            "all R-103 holdout claims must bind one sealed source program contract",
        )
    source_contract_ref, case_id = next(iter(bindings))
    links = conn.execute(
        """SELECT target.program_id, target.method_frozen_at, link.source_program_id,
                  link.source_training_episode_id, link.source_freeze_ref
             FROM judgment_training_holdout_links AS link
             JOIN judgment_training_programs AS target
               ON target.program_id = link.program_id
             JOIN judgment_training_programs AS source
               ON source.program_id = link.source_program_id
            WHERE source.contract_ref = ?
              AND link.source_case_id = ?
              AND link.link_role = 'HISTORICAL_HOLDOUT'
            ORDER BY target.registered_at, target.program_id""",
        (source_contract_ref, case_id),
    ).fetchall()
    frozen = [row for row in links if row["method_frozen_at"]]
    if len(frozen) != 1:
        raise ControlPlaneError(
            "r103_linked_selection_method_not_frozen",
            "R-103 control registration requires exactly one frozen linked selection method",
        )
    link = dict(frozen[0])
    gate = r103_linked_holdout_administrative_gate(
        conn,
        program_id=link["program_id"], source_program_id=link["source_program_id"],
        training_episode_id=link["source_training_episode_id"], case_id=case_id,
        holdout_freeze_ref=link["source_freeze_ref"], as_of=registered_at,
    )
    if gate["state"] != "READY_FOR_CONTROL_REGISTRATION":
        raise ControlPlaneError(
            "r103_holdout_registration_gate_incomplete",
            "; ".join(gate.get("findings") or [gate["state"]]),
        )
    if any(
        _reference_path(str(row.get("pre_reveal_review_receipt_ref") or "")).resolve()
        != Path(gate["pre_reveal_review_ref"]).resolve()
        for row in candidates
    ):
        raise ControlPlaneError(
            "r103_pre_reveal_receipt_binding_mismatch",
            "R-103 registration must retain the reviewed frozen-method pre-reveal receipt",
        )
    if {row.get("selection_status") for row in candidates} != {gate["selection_status"]}:
        raise ControlPlaneError(
            "r103_frozen_method_application_selection_mismatch",
            "R-103 control claims must retain the frozen method-application selection status",
        )


def register_manifest(conn: sqlite3.Connection, manifest: dict[str, Any], *, registered_at: str | None = None) -> dict[str, Any]:
    if manifest.get("schema_version") != REGISTRATION_SCHEMA_VERSION:
        raise ControlPlaneError("registration_schema_invalid", f"expected schema_version {REGISTRATION_SCHEMA_VERSION}")
    now = _now_dt()
    registered_at_dt = _parse_time(registered_at or _iso(now), field="registered_at")
    if registered_at_dt > now:
        raise ControlPlaneError("registration_in_future", "registered_at cannot be later than the real current time")
    registered_at = _iso(registered_at_dt)
    rows = [_claim_fields(item, manifest=manifest, registered_at=registered_at) for item in _expand_manifest(manifest)]
    if not rows:
        raise ControlPlaneError("feedback_items_empty", "registration requires at least one feedback item")
    seen = {row["feedback_item_id"] for row in rows}
    if len(seen) != len(rows):
        raise ControlPlaneError("feedback_item_duplicate", "one manifest cannot register the same episode/claim/stage twice")
    if any(_parse_time(row["frozen_at"], field="frozen_at") > registered_at_dt for row in rows):
        raise ControlPlaneError(
            "claim_registration_effective_after_recorded",
            "CLAIM_REGISTERED effective_at cannot be later than its recorded_at",
        )
    _require_r103_linked_holdout_registration(conn, rows, registered_at=registered_at_dt)
    selection_contexts = _require_selection_candidate_review(
        conn, rows, registered_at=registered_at_dt,
    )
    results: list[dict[str, Any]] = []
    columns = tuple(rows[0]) if rows else ()
    with conn:
        for row in rows:
            existing = conn.execute("SELECT * FROM judgment_feedback_claims WHERE feedback_item_id = ?", (row["feedback_item_id"],)).fetchone()
            if existing:
                comparable = {column: existing[column] for column in columns if column != "registered_at"}
                intended = {column: row[column] for column in columns if column != "registered_at"}
                if comparable != intended:
                    if _can_rehome_live_forward_references(comparable, intended):
                        conn.execute(
                            """UPDATE judgment_feedback_claims
                               SET source_ref = ?, frozen_artifact_ref = ?, source_contract_ref = ?, measurement_contract_ref = ?
                               WHERE feedback_item_id = ?""",
                            (
                                intended["source_ref"], intended["frozen_artifact_ref"],
                                intended["source_contract_ref"], intended["measurement_contract_ref"],
                                row["feedback_item_id"],
                            ),
                        )
                        results.append({"feedback_item_id": row["feedback_item_id"], "registered": False, "idempotent": True, "worktree_rehomed": True})
                        continue
                    identity_columns = {
                        "episode_class", "selection_status", "learning_eligibility",
                        "program_lane", "outcome_access", "training_program_ref",
                    }
                    immutable_existing = {key: value for key, value in comparable.items() if key not in identity_columns}
                    immutable_intended = {key: value for key, value in intended.items() if key not in identity_columns}
                    core_fields = ("episode_class", "selection_status", "learning_eligibility")
                    program_fields = ("program_lane", "outcome_access", "training_program_ref")
                    existing_identity = tuple(comparable[key] for key in core_fields)
                    intended_identity = tuple(intended[key] for key in core_fields)
                    existing_program_identity = tuple(comparable[key] for key in program_fields)
                    intended_program_identity = tuple(intended[key] for key in program_fields)
                    frozen_identity = _identity_from_frozen_contract(str(existing["source_contract_ref"]))
                    legacy_default = ("PIPELINE_REHEARSAL", "NO_PRIMARY", "MECHANISM_SETTLEMENT_ONLY")
                    legacy_program_default = ("UNASSIGNED", "UNSPECIFIED", "")
                    core_upgrade_allowed = existing_identity == intended_identity or (
                        existing_identity == legacy_default and frozen_identity == intended_identity
                    )
                    program_upgrade_allowed = (
                        existing_program_identity == intended_program_identity
                        or existing_program_identity == legacy_program_default
                    )
                    if immutable_existing == immutable_intended and core_upgrade_allowed and program_upgrade_allowed:
                        conn.execute(
                            """UPDATE judgment_feedback_claims
                               SET episode_class = ?, selection_status = ?, learning_eligibility = ?,
                                   program_lane = ?, outcome_access = ?, training_program_ref = ?
                               WHERE feedback_item_id = ?""",
                            (*intended_identity, *intended_program_identity, row["feedback_item_id"]),
                        )
                        results.append({"feedback_item_id": row["feedback_item_id"], "registered": False, "idempotent": True, "legacy_identity_upgraded": True})
                        continue
                    raise ControlPlaneError("claim_registration_conflict", f"immutable claim differs: {row['feedback_item_id']}")
                results.append({"feedback_item_id": row["feedback_item_id"], "registered": False, "idempotent": True})
                continue
            registration_event_id = f"JFE:REGISTERED:{row['feedback_item_id']}"
            selection_context = selection_contexts.get(
                (str(row["episode_id"]), str(row["training_program_ref"])),
            )
            selection_payload = (
                _selection_claim_registration_payload(
                    selection_context, registration_event_id=registration_event_id,
                )
                if selection_context
                else None
            )
            conn.execute(
                f"INSERT INTO judgment_feedback_claims ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(row[column] for column in columns),
            )
            conn.execute(
                """INSERT INTO judgment_feedback_events
                   (event_id, feedback_item_id, event_type, effective_at, recorded_at, actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
                   VALUES (?, ?, 'CLAIM_REGISTERED', ?, ?, 'SYSTEM', 'judgment_feedback_control', ?, ?, ?)""",
                (
                    registration_event_id,
                    row["feedback_item_id"],
                    row["frozen_at"],
                    registered_at,
                    f"CLAIM_REGISTERED:{row['feedback_item_id']}",
                    _json([
                        row["frozen_artifact_ref"], row["source_contract_ref"], row["measurement_contract_ref"],
                        *([row["pre_reveal_review_receipt_ref"]] if row["pre_reveal_review_receipt_ref"] else []),
                        *(
                            [row["selection_resolution_ref"], row["selection_resolution_review_ref"]]
                            if selection_context
                            else []
                        ),
                    ]),
                    _json({
                        **(
                            selection_payload
                            if selection_payload is not None
                            else {"registration_schema_version": REGISTRATION_SCHEMA_VERSION}
                        ),
                        **(
                            {
                                "pre_reveal_review_receipt_ref": row["pre_reveal_review_receipt_ref"],
                                "pre_reveal_review_receipt_snapshot": _loads(
                                    row["pre_reveal_review_receipt_json"]
                                ),
                            }
                            if row["pre_reveal_review_receipt_json"]
                            else {}
                        ),
                    }),
                ),
            )
            results.append({"feedback_item_id": row["feedback_item_id"], "registered": True, "idempotent": False})
        for identity, context in selection_contexts.items():
            registration_event_ids = {
                item["claim_id"]: f"JFE:REGISTERED:{item['feedback_item_id']}"
                for item in context["rows"]
            }
            release_event_id = f"JFE:SELECTION_OUTCOME_RELEASE:{identity[0]}"
            activation = _selection_activation_snapshot(
                context,
                registered_at=registered_at,
                registration_event_ids=registration_event_ids,
                outcome_release_event_id=release_event_id,
            )
            anchor = context["rows"][0]
            release_record = {
                "event_id": release_event_id,
                "feedback_item_id": anchor["feedback_item_id"],
                "event_type": "OUTCOME_RELEASE_AUTHORIZED",
                "effective_at": registered_at,
                "recorded_at": registered_at,
                "actor_role": "SYSTEM",
                "actor_id": "judgment_feedback_control",
                "idempotency_key": f"OUTCOME_RELEASE_AUTHORIZED:{identity[0]}",
                "artifact_refs_json": _json([
                    anchor["selection_resolution_ref"],
                    anchor["selection_resolution_review_ref"],
                ]),
                "payload_json": _json({"activation_snapshot": activation}),
            }
            existing_release = conn.execute(
                "SELECT * FROM judgment_feedback_events WHERE idempotency_key = ?",
                (release_record["idempotency_key"],),
            ).fetchone()
            if existing_release:
                if any(existing_release[field] != value for field, value in release_record.items()):
                    raise ControlPlaneError(
                        "selection_outcome_release_conflict",
                        "immutable selection outcome release event differs from the registered activation",
                    )
            else:
                conn.execute(
                    """INSERT INTO judgment_feedback_events
                       (event_id, feedback_item_id, event_type, effective_at, recorded_at,
                        actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
                       VALUES (:event_id, :feedback_item_id, :event_type, :effective_at, :recorded_at,
                               :actor_role, :actor_id, :idempotency_key, :artifact_refs_json, :payload_json)""",
                    release_record,
                )
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


def selection_joint_feedback_verdict(
    conn: sqlite3.Connection, claim: dict[str, Any], *, effective_at: datetime,
) -> str | None:
    """Return the frozen joint result for a complete selection bundle.

    A single D3 or D4 claim can be directionally diagnostic while their
    pre-registered joint mapping is MIXED.  Learning rights therefore follow
    the immutable bundle feedback, never an individual claim's verdict.
    ``None`` means the full bundle is not yet settled; malformed completed
    bundles are rejected rather than silently treated as directional.
    """
    if (
        claim.get("selection_status") != "SELECTION_ADMITTED"
        or claim.get("learning_eligibility") != "SELECTION_METHOD_ELIGIBLE"
    ):
        return None
    rows = [dict(row) for row in conn.execute(
        """SELECT * FROM judgment_feedback_claims
             WHERE episode_id = ? AND training_program_ref = ?
             ORDER BY registered_at, feedback_item_id""",
        (claim["episode_id"], claim["training_program_ref"]),
    ).fetchall()]
    stage_ids = tuple(row["stage_id"] for row in rows)
    if (
        len(rows) not in {5, 6}
        or tuple(sorted(stage_ids)) not in {
            tuple(sorted(order)) for order in SELECTION_STAGE_ORDERS
        }
        or any(
            row["selection_status"] != "SELECTION_ADMITTED"
            or row["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE"
            for row in rows
        )
    ):
        # Older single-signal pipeline fixtures use the same broad eligibility
        # label but are not a registered selection-development bundle.  They
        # retain their existing per-claim controls; only an exact D1-D5/D3
        # bundle can enter this joint gate.
        return None
    settlements = [
        _last_effective_no_later_than(
            _events(conn, row["feedback_item_id"]), OUTCOME_EVENTS, effective_at,
        )
        for row in rows
    ]
    if any(event is None for event in settlements):
        return None
    refs = {
        str((event or {}).get("payload", {}).get("feedback_ref") or "").strip()
        for event in settlements
    }
    if len(refs) != 1 or not next(iter(refs)):
        raise ControlPlaneError(
            "selection_joint_feedback_binding_invalid",
            "a complete selection bundle must retain one shared feedback artifact",
        )
    feedback_path = _reference_path(next(iter(refs))).resolve()
    _require_artifact(str(feedback_path), field="selection_joint_feedback_ref")
    feedback = _read_json(feedback_path)
    if (
        feedback.get("schema_version") != "judgment-selection-feedback-card.v1"
        or feedback.get("case_id") != claim["episode_id"]
    ):
        raise ControlPlaneError(
            "selection_joint_feedback_identity_invalid",
            "shared feedback must be the frozen selection feedback for this episode",
        )
    cards = feedback.get("cards")
    if not isinstance(cards, list):
        raise ControlPlaneError(
            "selection_joint_feedback_cards_invalid",
            "shared selection feedback must retain one card per registered claim",
        )
    expected = {row["claim_id"]: row["stage_id"] for row in rows}
    actual = {
        str(card.get("claim_id") or ""): str(card.get("stage_id") or "")
        for card in cards if isinstance(card, dict)
    }
    if len(actual) != len(cards) or actual != expected:
        raise ControlPlaneError(
            "selection_joint_feedback_cards_invalid",
            "shared selection feedback cards do not match the registered claim bundle",
        )
    joint = feedback.get("joint_comparison")
    verdict = str(joint.get("overall_verdict") or "").upper() if isinstance(joint, dict) else ""
    if verdict not in {"A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"}:
        raise ControlPlaneError(
            "selection_joint_feedback_verdict_invalid",
            "shared selection feedback has no derived joint verdict",
        )
    return verdict


def _holdout_clock_id(claim: dict[str, Any]) -> str:
    match = re.match(r"^(D[1-5])(?:_|$)", str(claim.get("stage_id") or "").upper())
    if match is None:
        raise ControlPlaneError(
            "holdout_stage_invalid",
            "historical holdout claims must use D1-D5 stage_id prefixes",
        )
    return match.group(1)


def _holdout_claim_bundle(conn: sqlite3.Connection, claim: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [dict(row) for row in conn.execute(
        """SELECT * FROM judgment_feedback_claims
             WHERE episode_id = ? AND training_program_ref = ?
             ORDER BY stage_id, claim_id, feedback_item_id""",
        (claim["episode_id"], claim["training_program_ref"]),
    ).fetchall()]
    if len(rows) != 5:
        raise ControlPlaneError(
            "holdout_d1_d5_incomplete",
            "historical holdout evaluation requires exactly five D1-D5 claims",
        )
    by_clock: dict[str, dict[str, Any]] = {}
    for row in rows:
        if (
            row["program_lane"] != "HISTORICAL_HOLDOUT"
            or row["learning_eligibility"] != "EVALUATION_ONLY"
            or row["outcome_access"] != "PIT_OUTCOME_SEALED"
        ):
            raise ControlPlaneError(
                "holdout_evaluation_identity_invalid",
                "all D1-D5 holdout claims must remain HISTORICAL_HOLDOUT, EVALUATION_ONLY and PIT_OUTCOME_SEALED",
            )
        clock = _holdout_clock_id(row)
        if clock in by_clock:
            raise ControlPlaneError("holdout_clock_duplicate", f"historical holdout contains duplicate {clock} claims")
        by_clock[clock] = row
    if set(by_clock) != HOLDOUT_CLOCKS:
        raise ControlPlaneError("holdout_d1_d5_incomplete", "historical holdout must contain one claim for each of D1-D5")
    return by_clock


def _require_frozen_holdout_program(
    conn: sqlite3.Connection, claim: dict[str, Any], *, effective_at: datetime,
    program_id: str | None = None,
) -> dict[str, Any]:
    if claim["program_lane"] != "HISTORICAL_HOLDOUT" or claim["learning_eligibility"] != "EVALUATION_ONLY":
        raise ControlPlaneError(
            "holdout_evaluation_identity_invalid",
            "holdout evaluation requires HISTORICAL_HOLDOUT and EVALUATION_ONLY",
        )
    tables = {
        str(row["name"])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('judgment_training_programs', 'judgment_training_episodes')"
        ).fetchall()
    }
    if tables != {"judgment_training_programs", "judgment_training_episodes"}:
        raise ControlPlaneError(
            "holdout_training_program_unregistered",
            "the referenced training program must be registered in this database before holdout evaluation",
        )
    direct = conn.execute(
        """SELECT program.program_id, program.method_version, program.method_frozen_at,
                  program.method_freeze_recorded_at,
                  program.contract_ref, program.program_state,
                  episode.training_episode_id,
                  program.program_id AS source_program_id,
                  '' AS source_freeze_ref,
                  'OWN' AS holdout_relation
             FROM judgment_training_programs AS program
             JOIN judgment_training_episodes AS episode ON episode.program_id = program.program_id
            WHERE program.contract_ref = ?
              AND episode.case_id = ?
              AND episode.lane = 'HISTORICAL_HOLDOUT'""",
        (claim["training_program_ref"], claim["episode_id"]),
    ).fetchone()
    linked: list[sqlite3.Row] = []
    link_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'judgment_training_holdout_links'",
    ).fetchone()
    if link_table is not None:
        linked = conn.execute(
            """SELECT target.program_id, target.method_version, target.method_frozen_at,
                      target.method_freeze_recorded_at, target.contract_ref,
                      target.program_state, source_episode.training_episode_id,
                      link.source_program_id, link.source_freeze_ref,
                      'LINKED' AS holdout_relation
                 FROM judgment_training_holdout_links AS link
                 JOIN judgment_training_programs AS target
                   ON target.program_id = link.program_id
                 JOIN judgment_training_programs AS source_program
                   ON source_program.program_id = link.source_program_id
                 JOIN judgment_training_episodes AS source_episode
                   ON source_episode.training_episode_id = link.source_training_episode_id
                WHERE source_program.contract_ref = ?
                  AND source_episode.case_id = ?
                  AND source_episode.lane = 'HISTORICAL_HOLDOUT'
                  AND link.link_role = 'HISTORICAL_HOLDOUT'
                ORDER BY target.registered_at, target.program_id""",
            (claim["training_program_ref"], claim["episode_id"]),
        ).fetchall()
    candidates = ([direct] if direct is not None else []) + linked
    if not candidates:
        raise ControlPlaneError(
            "holdout_training_program_unregistered",
            "the holdout claim is not bound to a registered HISTORICAL_HOLDOUT episode",
        )
    if program_id:
        selected = [row for row in candidates if row["program_id"] == program_id]
        if not selected:
            raise ControlPlaneError(
                "holdout_training_program_unregistered",
                "the holdout claim is not linked to the requested training program",
            )
        row = selected[0]
    else:
        frozen_linked = [
            row for row in linked
            if row["program_state"] == "ACTIVE" and row["method_frozen_at"]
        ]
        if len(frozen_linked) > 1:
            raise ControlPlaneError(
                "holdout_training_program_ambiguous",
                "multiple frozen successor programs link this holdout; program_id is required",
            )
        row = frozen_linked[0] if frozen_linked else direct or linked[0]
    context = dict(row)
    if context.get("program_state") != "ACTIVE":
        raise ControlPlaneError(
            "holdout_training_program_not_active",
            "historical holdout evaluation requires an ACTIVE training program",
        )
    if not context.get("method_frozen_at"):
        raise ControlPlaneError(
            "holdout_method_not_frozen",
            "historical holdout outcomes cannot be opened before the registered method freeze",
        )
    if not context.get("method_freeze_recorded_at"):
        raise ControlPlaneError(
            "holdout_method_freeze_receipt_missing",
            "historical holdout evaluation requires the method freeze's real recorded-at receipt",
        )
    frozen_at = _parse_time(context["method_frozen_at"], field="method_frozen_at")
    freeze_recorded_at = _parse_time(
        context["method_freeze_recorded_at"], field="method_freeze_recorded_at",
    )
    if frozen_at > freeze_recorded_at:
        raise ControlPlaneError(
            "holdout_method_freeze_time_invalid",
            "method freeze effective_at cannot be later than its recorded_at receipt",
        )
    if effective_at < frozen_at:
        raise ControlPlaneError(
            "holdout_event_before_method_freeze",
            "historical holdout evaluation events cannot predate the registered method freeze",
        )
    event_types = sorted(OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS | {"OUTCOME_EXPOSURE_BREACH"})
    placeholders = ",".join("?" for _ in event_types)
    prior = conn.execute(
        f"""SELECT event.event_id, event.event_type, event.effective_at
                FROM judgment_feedback_events AS event
                JOIN judgment_feedback_claims AS registered USING (feedback_item_id)
               WHERE registered.episode_id = ?
                 AND registered.training_program_ref = ?
                 AND registered.program_lane = 'HISTORICAL_HOLDOUT'
                 AND event.event_type IN ({placeholders})
               ORDER BY event.effective_at, event.recorded_at, event.event_id""",
        (claim["episode_id"], claim["training_program_ref"], *event_types),
    ).fetchall()
    if any(_parse_time(item["effective_at"], field="holdout_event.effective_at") < frozen_at for item in prior):
        raise ControlPlaneError(
            "holdout_revealed_before_method_freeze",
            "a historical holdout outcome event predates the registered method freeze",
        )
    context["method_frozen_at"] = _iso(frozen_at)
    context["method_freeze_recorded_at"] = _iso(freeze_recorded_at)
    if (
        context.get("holdout_relation") == "LINKED"
        and claim.get("episode_id") == R103_HOLDOUT_CASE_ID
    ):
        gate = r103_linked_holdout_administrative_gate(
            conn,
            program_id=context["program_id"],
            source_program_id=context["source_program_id"],
            training_episode_id=context["training_episode_id"],
            case_id=claim["episode_id"],
            holdout_freeze_ref=context["source_freeze_ref"],
            as_of=effective_at,
        )
        if gate["state"] != "READY_FOR_CONTROL_REGISTRATION":
            codes = {
                "R103_SELECTION_METHOD_SCOPE_MISMATCH": "r103_selection_method_scope_mismatch",
                "ADMINISTRATIVE_CORRECTION_REQUIRED": "administrative_correction_required",
                "ADMINISTRATIVE_CORRECTION_REVIEW_REQUIRED": "administrative_correction_review_required",
                "FROZEN_METHOD_APPLICATION_REQUIRED": "frozen_method_application_required",
                "PRE_REVEAL_REVIEW_REQUIRED": "pre_reveal_review_required",
            }
            raise ControlPlaneError(
                codes.get(gate["state"], "r103_holdout_administrative_gate_invalid"),
                "; ".join(gate.get("findings") or [gate["state"]]),
            )
    return context


def _holdout_pre_reveal_context(claim: dict[str, Any]) -> dict[str, Any]:
    reference = str(claim.get("pre_reveal_review_receipt_ref") or "").strip()
    if not reference:
        raise ControlPlaneError(
            "pre_reveal_review_receipt_missing",
            "registered holdout claim has no immutable pre-reveal review receipt",
        )
    snapshot_json = str(claim.get("pre_reveal_review_receipt_json") or "").strip()
    if not snapshot_json:
        raise ControlPlaneError(
            "pre_reveal_review_snapshot_missing",
            "registered holdout claim has no immutable pre-reveal review snapshot",
        )
    try:
        registered_snapshot = _loads(snapshot_json)
    except json.JSONDecodeError as exc:
        raise ControlPlaneError(
            "pre_reveal_review_snapshot_invalid",
            "registered pre-reveal review snapshot is invalid JSON",
        ) from exc
    path, receipt, reviewed_at = _validate_pre_reveal_review_receipt(
        reference,
        episode_id=claim["episode_id"],
        registered_at=_parse_time(claim["registered_at"], field="claim.registered_at"),
    )
    if receipt != registered_snapshot:
        raise ControlPlaneError(
            "pre_reveal_review_receipt_changed",
            "pre-reveal review receipt changed after claim registration",
        )
    return {
        "path": path,
        "receipt": registered_snapshot,
        "reviewed_at": reviewed_at,
    }


def _validate_holdout_episode_temporal_contract(
    conn: sqlite3.Connection, claim: dict[str, Any], *, effective_at: datetime,
    program_id: str | None = None,
) -> dict[str, Any]:
    context = _require_frozen_holdout_program(
        conn, claim, effective_at=effective_at, program_id=program_id,
    )
    now = _now_dt()
    method_frozen_at = _parse_time(context["method_frozen_at"], field="method_frozen_at")
    method_freeze_recorded_at = _parse_time(
        context["method_freeze_recorded_at"], field="method_freeze_recorded_at",
    )
    freeze_row = conn.execute(
        """SELECT recorded_at
             FROM judgment_training_artifact_events
            WHERE training_episode_id = ? AND artifact_kind = 'freeze_ref'
            ORDER BY recorded_at
            LIMIT 1""",
        (context["training_episode_id"],),
    ).fetchone()
    if freeze_row is None:
        raise ControlPlaneError(
            "holdout_freeze_receipt_missing",
            "historical holdout evaluation requires a recorded pre-outcome freeze artifact",
        )
    holdout_freeze_recorded_at = _parse_time(
        freeze_row["recorded_at"], field="holdout_freeze.recorded_at",
    )
    if holdout_freeze_recorded_at > now:
        raise ControlPlaneError(
            "holdout_freeze_recorded_in_future",
            "holdout freeze artifact cannot be recorded in the future",
        )
    if holdout_freeze_recorded_at > method_frozen_at:
        raise ControlPlaneError(
            "holdout_freeze_after_method_freeze",
            "holdout freeze artifact must be recorded before the method freeze",
        )

    outcome_events: list[dict[str, Any]] = []
    for item in _holdout_claim_bundle(conn, claim).values():
        registered_at = _parse_time(item["registered_at"], field="claim.registered_at")
        if registered_at > now:
            raise ControlPlaneError(
                "holdout_claim_registered_in_future",
                "holdout claim registration cannot be later than the real current time",
            )
        if holdout_freeze_recorded_at > registered_at:
            raise ControlPlaneError(
                "holdout_freeze_after_claim_registration",
                "holdout freeze artifact must precede claim registration",
            )
        pre_review = _holdout_pre_reveal_context(item)
        prerequisites = {
            "holdout_freeze_recorded_at": holdout_freeze_recorded_at,
            "method_frozen_at": method_frozen_at,
            "method_freeze_recorded_at": method_freeze_recorded_at,
            "claim_registered_at": registered_at,
            "pre_reveal_reviewed_at": pre_review["reviewed_at"],
        }
        for event in _events(conn, item["feedback_item_id"]):
            if event["event_type"] == "OUTCOME_EXPOSURE_BREACH":
                raise ControlPlaneError(
                    "holdout_evaluation_blocked_by_exposure_breach",
                    "an exposure-breached holdout cannot receive evaluation acceptance",
                )
            if event["event_type"] not in OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS:
                continue
            event_effective_at = _parse_time(
                event["effective_at"], field="holdout_event.effective_at",
            )
            event_recorded_at = _parse_time(
                event["recorded_at"], field="holdout_event.recorded_at",
            )
            if event_recorded_at > now or event_effective_at > event_recorded_at:
                raise ControlPlaneError(
                    "holdout_event_time_invalid",
                    "holdout outcome events require effective_at <= recorded_at <= real current time",
                )
            first_accessed_at = _parse_time(
                (event.get("payload") or {}).get("first_outcome_accessed_at"),
                field="first_outcome_accessed_at",
            )
            late_prerequisites = sorted(
                name for name, value in prerequisites.items()
                if value > first_accessed_at
            )
            if late_prerequisites:
                raise ControlPlaneError(
                    "holdout_outcome_access_precedes_prerequisites",
                    "first outcome access predates: " + ", ".join(late_prerequisites),
                )
            if first_accessed_at > event_effective_at:
                raise ControlPlaneError(
                    "holdout_outcome_time_order_invalid",
                    "first outcome access must be no later than event effective_at",
                )
            if event_recorded_at <= max(prerequisites.values()):
                raise ControlPlaneError(
                    "holdout_outcome_recorded_before_prerequisites",
                    "holdout outcome event must be recorded after freeze, review and registration",
                )
            outcome_events.append(event)
    return {
        "context": context,
        "outcome_events": outcome_events,
        "last_outcome_recorded_at": max(
            (
                _parse_time(event["recorded_at"], field="holdout_event.recorded_at")
                for event in outcome_events
            ),
            default=None,
        ),
    }


def _validate_holdout_exposure_breach_artifact(
    path: Path, *, claim: dict[str, Any], now: datetime,
) -> dict[str, Any]:
    receipt = _read_json(path)
    if receipt.get("schema_version") != HOLDOUT_EXPOSURE_BREACH_SCHEMA_VERSION:
        raise ControlPlaneError(
            "holdout_breach_schema_invalid",
            f"expected schema_version {HOLDOUT_EXPOSURE_BREACH_SCHEMA_VERSION}",
        )
    if receipt.get("case_id") != claim["episode_id"]:
        raise ControlPlaneError("holdout_breach_case_mismatch", "exposure breach belongs to another holdout episode")
    _required_text(receipt, "breach_id")
    _required_text(receipt, "root_cause")
    _required_text(receipt, "disposition")
    first_accessed_at = _parse_time(
        receipt.get("first_outcome_accessed_at"),
        field="breach.first_outcome_accessed_at",
    )
    discovered_at = _parse_time(receipt.get("discovered_at"), field="breach.discovered_at")
    if first_accessed_at > discovered_at:
        raise ControlPlaneError(
            "holdout_breach_time_invalid",
            "first_outcome_accessed_at cannot be later than discovered_at",
        )
    if discovered_at > now:
        raise ControlPlaneError(
            "holdout_breach_discovery_in_future",
            "breach discovered_at cannot be later than the real current time",
        )
    return {
        "receipt": receipt,
        "first_outcome_accessed_at": first_accessed_at,
        "discovered_at": discovered_at,
    }


def _holdout_settlements(
    conn: sqlite3.Connection, claim: dict[str, Any], *, effective_at: datetime,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    settlements: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for clock, item in _holdout_claim_bundle(conn, claim).items():
        settlement = _last_effective_no_later_than(_events(conn, item["feedback_item_id"]), OUTCOME_EVENTS, effective_at)
        if settlement is None:
            raise ControlPlaneError(
                "holdout_claims_unsettled",
                "all D1-D5 holdout claims must be settled before accepting an evaluation receipt",
            )
        settlements[clock] = (item, settlement)
    return settlements


def _validate_holdout_evaluation_event(
    conn: sqlite3.Connection, claim: dict[str, Any], event: dict[str, Any], *, effective_at: datetime,
) -> None:
    payload = event["payload"]
    if _holdout_clock_id(claim) != "D5":
        raise ControlPlaneError("holdout_receipt_anchor_invalid", "the episode evaluation receipt must be anchored to its D5 claim")
    temporal = _validate_holdout_episode_temporal_contract(
        conn, claim, effective_at=effective_at,
        program_id=str(payload.get("program_id") or "") or None,
    )
    context = temporal["context"]
    if payload.get("receipt_schema_version") != HOLDOUT_EVALUATION_RECEIPT_SCHEMA_VERSION:
        raise ControlPlaneError("holdout_receipt_schema_invalid", "unsupported holdout evaluation receipt schema")
    _required_text(payload, "receipt_id")
    if payload.get("program_id") != context["program_id"]:
        raise ControlPlaneError("holdout_receipt_program_mismatch", "evaluation receipt belongs to another training program")
    if payload.get("training_episode_id") != context["training_episode_id"] or payload.get("case_id") != claim["episode_id"]:
        raise ControlPlaneError("holdout_receipt_episode_mismatch", "evaluation receipt belongs to another holdout episode")
    if payload.get("method_version") != context["method_version"]:
        raise ControlPlaneError("holdout_receipt_method_mismatch", "evaluation receipt must evaluate the frozen method version")
    receipt_freeze = _parse_time(payload.get("method_frozen_at"), field="method_frozen_at")
    if receipt_freeze != _parse_time(context["method_frozen_at"], field="registered_method_frozen_at"):
        raise ControlPlaneError("holdout_receipt_freeze_mismatch", "evaluation receipt method freeze does not match database truth")
    evaluated_at = _parse_time(payload.get("evaluated_at"), field="evaluated_at")
    if evaluated_at > effective_at or evaluated_at < receipt_freeze:
        raise ControlPlaneError("holdout_receipt_time_invalid", "evaluation must occur after method freeze and no later than receipt acceptance")
    last_outcome_recorded_at = temporal["last_outcome_recorded_at"]
    if last_outcome_recorded_at is None or evaluated_at < last_outcome_recorded_at:
        raise ControlPlaneError(
            "holdout_evaluation_before_outcome_recording",
            "holdout evaluation must occur after all D1-D5 outcome events were actually recorded",
        )
    verdict = _required_text(payload, "evaluation_verdict").upper()
    if verdict not in HOLDOUT_EVALUATION_VERDICTS:
        raise ControlPlaneError("holdout_evaluation_verdict_invalid", f"unsupported evaluation_verdict: {verdict}")
    author = _required_text(payload, "evaluation_author_id")
    reviewer = _required_text(payload, "reviewer_id")
    if author == reviewer:
        raise ControlPlaneError("holdout_reviewer_not_independent", "holdout reviewer must differ from the evaluation author")
    if _required_text(payload, "reviewer_acceptance").upper() != "ACCEPTED":
        raise ControlPlaneError("reviewer_acceptance_missing", "holdout reviewer_acceptance must be ACCEPTED")
    if event["actor_id"] != reviewer:
        raise ControlPlaneError("holdout_acceptance_actor_mismatch", "the accepted event actor must be the independent reviewer")

    settlements = _holdout_settlements(conn, claim, effective_at=effective_at)
    if any(
        event_record["event_type"] == "OUTCOME_EXPOSURE_BREACH"
        for item, _ in settlements.values()
        for event_record in _events(conn, item["feedback_item_id"])
    ):
        raise ControlPlaneError(
            "holdout_evaluation_blocked_by_exposure_breach",
            "an exposure-breached holdout cannot receive an evaluation acceptance",
        )
    if any(
        event_record["event_type"] in HOLDOUT_PROHIBITED_RIGHT_EVENTS
        for item, _ in settlements.values()
        for event_record in _events(conn, item["feedback_item_id"])
    ):
        raise ControlPlaneError(
            "holdout_rights_breach",
            "a holdout with diagnosis or method-learning events cannot receive an evaluation acceptance",
        )
    if evaluated_at < max(
        _parse_time(event_record["effective_at"], field="settlement.effective_at")
        for _, event_record in settlements.values()
    ):
        raise ControlPlaneError("holdout_evaluation_before_settlement", "evaluation must follow all five D1-D5 settlements")
    entries = payload.get("claim_settlements")
    if not isinstance(entries, list) or len(entries) != 5:
        raise ControlPlaneError("holdout_receipt_claims_incomplete", "evaluation receipt must reference exactly five D1-D5 settlements")
    by_clock: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ControlPlaneError("holdout_receipt_claim_invalid", "claim_settlements entries must be objects")
        clock = _required_text(entry, "clock").upper()
        if clock not in HOLDOUT_CLOCKS or clock in by_clock:
            raise ControlPlaneError("holdout_receipt_clock_invalid", "claim_settlements must contain unique D1-D5 clocks")
        by_clock[clock] = entry
    if set(by_clock) != HOLDOUT_CLOCKS:
        raise ControlPlaneError("holdout_receipt_claims_incomplete", "evaluation receipt must reference D1-D5")
    settlement_actors: set[str] = set()
    for clock, (expected_claim, expected_event) in settlements.items():
        entry = by_clock[clock]
        expected = {
            "feedback_item_id": expected_claim["feedback_item_id"],
            "claim_id": expected_claim["claim_id"],
            "stage_id": expected_claim["stage_id"],
            "settlement_event_id": expected_event["event_id"],
        }
        if any(entry.get(field) != value for field, value in expected.items()):
            raise ControlPlaneError(
                "holdout_receipt_settlement_mismatch",
                f"evaluation receipt does not bind the current {clock} settlement",
            )
        settlement_actors.add(str(expected_event["actor_id"]))
    if reviewer in settlement_actors:
        raise ControlPlaneError(
            "holdout_reviewer_not_independent",
            "holdout reviewer must differ from every D1-D5 settlement actor",
        )


def _settlement_version(claim: dict[str, Any], event: dict[str, Any]) -> int:
    """Return the version carried by an outcome-chain event.

    A latest-official settlement is a new evidence chain, not a new label on
    top of an earlier extraction.  Initial-disclosure contracts have one
    implicit chain and keep their compact legacy event shape.
    """
    if claim["settlement_version_policy"] == "INITIAL_DISCLOSURE":
        value = event["payload"].get("settlement_version", 1)
        if value != 1:
            raise ControlPlaneError("initial_settlement_version_invalid", "INITIAL_DISCLOSURE only permits settlement_version 1")
        return 1
    value = event["payload"].get("settlement_version")
    if not isinstance(value, int) or value < 1:
        raise ControlPlaneError(
            "settlement_version_missing",
            "LATEST_OFFICIAL_AS_OF_EVALUATION requires integer settlement_version on every outcome-chain event",
        )
    return value


def _last_for_version(
    events: Iterable[dict[str, Any]], event_types: set[str], version: int, *, effective_at: datetime | None = None,
) -> dict[str, Any] | None:
    found = [
        event for event in events
        if event["event_type"] in event_types and event["payload"].get("settlement_version", 1) == version
        and (effective_at is None or _parse_time(event["effective_at"], field="prior_event.effective_at") <= effective_at)
    ]
    return found[-1] if found else None


def _validate_diagnosis(payload: dict[str, Any]) -> None:
    locus = _required_text(payload, "epistemic_failure_locus").upper()
    root = _required_text(payload, "delivery_root_cause").upper()
    if locus not in EPISTEMIC_FAILURE_LOCI:
        raise ControlPlaneError("epistemic_failure_locus_invalid", f"unknown epistemic_failure_locus: {locus}")
    if root not in DELIVERY_ROOT_CAUSES:
        raise ControlPlaneError("delivery_root_cause_invalid", f"unknown delivery_root_cause: {root}")
    for field in ("economic_impact", "missing_facts", "prohibited_assumptions", "executable_remediation", "acceptance_criteria"):
        _required_text(payload, field)


def _registered_v4_source_context(
    conn: sqlite3.Connection, claim: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the source program only when this is a governed V4 transfer.

    Older standalone learning receipts remain auditable in their own lane, but
    a program that declares V4 cannot convert such a receipt into a method
    freeze.  Its transfer must land in a separately registered, still-sealed
    V4 candidate.
    """
    try:
        source = conn.execute(
            """SELECT episode.training_episode_id, episode.program_id, episode.case_id,
                      episode.company_id, episode.company_cluster_id,
                      program.contract_ref, program.required_selection_admission_version
                 FROM judgment_training_episodes AS episode
                 JOIN judgment_training_programs AS program USING (program_id)
                WHERE episode.case_id = ?
                  AND episode.lane = 'HISTORICAL_TRAINING'""",
            (claim.get("episode_id"),),
        ).fetchone()
    except sqlite3.Error:
        return None
    if source is None or not _same_artifact_reference(
        source["contract_ref"], str(claim.get("training_program_ref") or ""),
    ):
        return None
    if source["required_selection_admission_version"] != PEER_PANEL_ADMISSION_VERSION:
        return None
    return dict(source)


def _validate_registered_v4_transfer_target(
    conn: sqlite3.Connection, claim: dict[str, Any], payload: dict[str, Any], *,
    source_note_effective_at: datetime, effective_at: datetime,
) -> None:
    """Bind a V4 learning transfer to a real future candidate snapshot.

    A field appearing in an arbitrary JSON file is not an applied training
    result.  The target must have been frozen *after* the source learning note,
    independently reviewed, registered under a separate V4 program, and still
    sealed when the application is recorded.
    """
    source = _registered_v4_source_context(conn, claim)
    if source is None:
        return
    target_program_id = _required_text(payload, "target_program_id")
    target_episode_id = _required_text(payload, "target_training_episode_id")
    target_case_id = _required_text(payload, "target_case_id")
    target_candidate_ref = _required_text(payload, "target_candidate_ref")
    target_review_ref = _required_text(payload, "target_selection_review_ref")
    target_admission_version = _required_text(payload, "target_selection_admission_version")
    if target_program_id == source["program_id"]:
        raise ControlPlaneError(
            "learning_target_same_program",
            "a V4 transfer target must be a later separately registered development program",
        )
    target = conn.execute(
        """SELECT episode.*, program.program_state, program.contract_ref,
                      program.required_selection_admission_version
                 FROM judgment_training_episodes AS episode
                 JOIN judgment_training_programs AS program USING (program_id)
                WHERE episode.training_episode_id = ?
                  AND episode.program_id = ?
                  AND episode.case_id = ?""",
        (target_episode_id, target_program_id, target_case_id),
    ).fetchone()
    if target is None:
        raise ControlPlaneError(
            "learning_target_not_registered",
            "V4 transfer target must resolve to a registered historical-training episode",
        )
    if (
        target["program_state"] != "ACTIVE"
        or target["lane"] != "HISTORICAL_TRAINING"
        or target["outcome_access"] != "PIT_OUTCOME_SEALED"
        or target["required_selection_admission_version"] != PEER_PANEL_ADMISSION_VERSION
        or target_admission_version != PEER_PANEL_ADMISSION_VERSION
    ):
        raise ControlPlaneError(
            "learning_target_v4_context_invalid",
            "V4 transfer target must be active, historical, outcome-sealed and governed by V4",
        )
    if (
        target["company_id"] == source["company_id"]
        or target["company_cluster_id"] == source["company_cluster_id"]
    ):
        raise ControlPlaneError(
            "learning_target_not_cross_company",
            "V4 transfer target must be a different company and company cluster",
        )
    target_meta_checks = {
        "target_episode_id": target["training_episode_id"],
        "target_company_id": target["company_id"],
        "target_company_cluster_id": target["company_cluster_id"],
    }
    for field, expected in target_meta_checks.items():
        if _required_text(payload, field) != expected:
            raise ControlPlaneError(
                "learning_target_identity_mismatch",
                f"{field} must match the registered V4 target",
            )
    artifact_rows = conn.execute(
        """SELECT artifact_kind, artifact_ref, recorded_at, content_json
                 FROM judgment_training_artifact_events
                WHERE training_episode_id = ?
                  AND artifact_kind IN ('case_ref', 'selection_review_ref')""",
        (target_episode_id,),
    ).fetchall()
    artifacts = {row["artifact_kind"]: row for row in artifact_rows}
    case_artifact = artifacts.get("case_ref")
    review_artifact = artifacts.get("selection_review_ref")
    if not case_artifact or not case_artifact["content_json"]:
        raise ControlPlaneError("learning_target_candidate_missing", "registered V4 target has no frozen candidate snapshot")
    if not _same_artifact_reference(target_candidate_ref, case_artifact["artifact_ref"]):
        raise ControlPlaneError("learning_target_candidate_ref_mismatch", "target candidate reference differs from registered snapshot")
    if not _same_artifact_reference(payload.get("target_frozen_artifact_ref"), case_artifact["artifact_ref"]):
        raise ControlPlaneError("learning_target_freeze_ref_mismatch", "target frozen artifact must be the registered candidate snapshot")
    try:
        candidate = json.loads(case_artifact["content_json"])
    except json.JSONDecodeError as exc:
        raise ControlPlaneError("learning_target_candidate_invalid", "registered target candidate snapshot is not JSON") from exc
    validation = validate_selection_candidate(candidate)
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError(
            "learning_target_candidate_invalid",
            "registered V4 target candidate is not reviewable: " + "; ".join(validation.get("findings") or []),
        )
    if (
        candidate.get("selection_admission_contract", {}).get("version") != PEER_PANEL_ADMISSION_VERSION
        or candidate.get("case_id") != target_case_id
        or candidate.get("company_id") != target["company_id"]
        or candidate.get("company_cluster_id") != target["company_cluster_id"]
        or candidate.get("experiment_id") != target_episode_id
        or candidate.get("freeze_id") != _required_text(payload, "target_freeze_id")
    ):
        raise ControlPlaneError("learning_target_candidate_identity_mismatch", "registered V4 target candidate identity is inconsistent")
    candidate_frozen_at = _parse_time(candidate.get("freeze_recorded_at"), field="target_candidate.freeze_recorded_at")
    payload_frozen_at = _parse_time(payload.get("target_frozen_at"), field="target_frozen_at")
    if candidate_frozen_at != payload_frozen_at:
        raise ControlPlaneError("learning_target_frozen_at_mismatch", "target_frozen_at must equal the registered candidate freeze time")
    if candidate_frozen_at <= source_note_effective_at:
        raise ControlPlaneError(
            "learning_target_not_frozen_after_source_note",
            "the target candidate must freeze after the source learning note, not merely be cited retrospectively",
        )
    if candidate_frozen_at > effective_at:
        raise ControlPlaneError("learning_target_not_frozen", "target candidate freeze cannot follow the learning application")
    if not review_artifact or not review_artifact["content_json"]:
        raise ControlPlaneError("learning_target_review_missing", "registered V4 target needs an independent pre-outcome review")
    if not _same_artifact_reference(target_review_ref, review_artifact["artifact_ref"]):
        raise ControlPlaneError("learning_target_review_ref_mismatch", "target review reference differs from registered snapshot")
    try:
        review = json.loads(review_artifact["content_json"])
    except json.JSONDecodeError as exc:
        raise ControlPlaneError("learning_target_review_invalid", "registered target review snapshot is not JSON") from exc
    review_validation = validate_selection_review(
        review,
        candidate=candidate,
        case_artifact_ref=case_artifact["artifact_ref"],
        receipt_recorded_at=review_artifact["recorded_at"],
    )
    if review_validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError(
            "learning_target_review_invalid",
            "registered target review is not reviewable: " + "; ".join(review_validation.get("findings") or []),
        )
    review_recorded_at = _parse_time(review_artifact["recorded_at"], field="target_review.recorded_at")
    if review_recorded_at > effective_at:
        raise ControlPlaneError("learning_target_review_after_application", "target review must predate the learning application")
    blocked_types = sorted(OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS | {"OUTCOME_EXPOSURE_BREACH"})
    placeholders = ",".join("?" for _ in blocked_types)
    exposure = conn.execute(
        f"""SELECT event.event_id
               FROM judgment_feedback_events AS event
               JOIN judgment_feedback_claims AS target_claim USING (feedback_item_id)
              WHERE target_claim.episode_id = ?
                AND target_claim.training_program_ref = ?
                AND event.event_type IN ({placeholders})
              LIMIT 1""",
        (target_case_id, target["contract_ref"], *blocked_types),
    ).fetchone()
    if exposure is not None:
        raise ControlPlaneError(
            "learning_target_outcome_not_sealed",
            "a V4 transfer target cannot have outcome access or an outcome event before application",
        )


def _validate_learning_application(
    conn: sqlite3.Connection, claim: dict[str, Any], payload: dict[str, Any], *,
    source_note_effective_at: datetime, effective_at: datetime,
) -> None:
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
    _validate_registered_v4_transfer_target(
        conn, claim, payload,
        source_note_effective_at=source_note_effective_at,
        effective_at=effective_at,
    )


def _validate_transition(conn: sqlite3.Connection, claim: dict[str, Any], events: list[dict[str, Any]], event: dict[str, Any]) -> None:
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
    if event_type in {
        "ACQUISITION_STARTED", "ACQUISITION_BLOCKED", "OUTCOME_PACKAGE_READY", "READ_ATTESTED",
        "OUTCOME_EXTRACTED", "CLAIM_SETTLED", "MEASUREMENT_MISMATCH", OPERATING_OUTCOME_RECORDED,
    } and effective_at < eligible_at:
        raise ControlPlaneError("outcome_before_eligible", f"{event_type} cannot be recorded before eligible_at")
    if (
        claim["learning_eligibility"] == "EVALUATION_ONLY"
        and event_type in OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS
    ):
        _require_frozen_holdout_program(
            conn, claim, effective_at=effective_at,
            program_id=str(payload.get("program_id") or "") or None,
        )
        if _event_exists(events, "OUTCOME_EXPOSURE_BREACH"):
            raise ControlPlaneError(
                "holdout_outcome_blocked_by_exposure_breach",
                "an exposure-breached holdout cannot append outcome evaluation events",
            )
    if _event_exists(events, "CLOSED") and event_type != "OUTCOME_EXPOSURE_BREACH":
        raise ControlPlaneError("claim_closed", "closed feedback items do not accept new events")
    version = _settlement_version(claim, event) if event_type in OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS else None
    if event_type in OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS and claim["settlement_version_policy"] == "LATEST_OFFICIAL_AS_OF_EVALUATION":
        previous = _settlement_events(events)
        expected_version = len(previous) + 1
        if version != expected_version:
            raise ControlPlaneError(
                "outcome_chain_version_not_current",
                f"outcome-chain event must use the next unsettled version {expected_version}, not {version}",
            )
    if event_type == "OUTCOME_PACKAGE_READY" and not _last_for_version(events, {"ACQUISITION_STARTED"}, version or 1, effective_at=effective_at):
        raise ControlPlaneError("acquisition_required", "OUTCOME_PACKAGE_READY requires ACQUISITION_STARTED for the same settlement version")
    if event_type == "READ_ATTESTED" and not _last_for_version(events, {"OUTCOME_PACKAGE_READY"}, version or 1, effective_at=effective_at):
        raise ControlPlaneError("outcome_package_required", "READ_ATTESTED requires OUTCOME_PACKAGE_READY for the same settlement version")
    if event_type == "OUTCOME_EXTRACTED" and not _last_for_version(events, {"READ_ATTESTED"}, version or 1, effective_at=effective_at):
        raise ControlPlaneError("reader_attestation_required", "OUTCOME_EXTRACTED requires READ_ATTESTED for the same settlement version")
    if event_type in OUTCOME_EVENTS:
        if not _last_for_version(events, {"OUTCOME_EXTRACTED"}, version or 1, effective_at=effective_at):
            raise ControlPlaneError("outcome_extraction_required", f"{event_type} requires OUTCOME_EXTRACTED for the same settlement version")
        previous = _settlement_events(events)
        policy = claim["settlement_version_policy"]
        if policy == "INITIAL_DISCLOSURE" and previous:
            raise ControlPlaneError("initial_settlement_already_recorded", "INITIAL_DISCLOSURE accepts only one settlement")
        if policy == "LATEST_OFFICIAL_AS_OF_EVALUATION":
            if version != len(previous) + 1:
                raise ControlPlaneError("settlement_version_nonsequential", "settlement_version must increase by one")
            if version > 1 and payload.get("supersedes_event_id") != previous[-1]["event_id"]:
                raise ControlPlaneError("settlement_supersedes_missing", "later settlement must reference prior settlement event")
        if event_type == "CLAIM_SETTLED":
            verdict = _required_text(payload, "settlement_verdict").upper()
            if verdict not in SETTLEMENT_STATES - {"UNSETTLED", "MEASUREMENT_MISMATCH"}:
                raise ControlPlaneError("settlement_verdict_invalid", f"unsupported settlement_verdict: {verdict}")
        if event_type == OPERATING_OUTCOME_RECORDED:
            _require_artifact(_required_text(payload, "operating_outcome_ref"), field="operating_outcome_ref")
            if _required_text(payload, "operating_outcome_status").upper() not in {"OBSERVED", "NOT_DIAGNOSTIC"}:
                raise ControlPlaneError("operating_outcome_status_invalid", "operating outcome must be OBSERVED or NOT_DIAGNOSTIC")
    if event_type == "DIAGNOSIS_ACCEPTED":
        if claim["learning_eligibility"] == "EVALUATION_ONLY":
            raise ControlPlaneError(
                "diagnosis_not_permitted_for_evaluation_only",
                "historical holdout evaluation cannot create a diagnosis",
            )
        settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, effective_at)
        if not settlement:
            raise ControlPlaneError("settlement_required", "DIAGNOSIS_ACCEPTED requires a settlement")
        if payload.get("settlement_event_id") != settlement["event_id"]:
            raise ControlPlaneError("diagnosis_settlement_link_invalid", "diagnosis must bind the latest settlement event")
        _validate_diagnosis(payload)
        if (
            selection_joint_feedback_verdict(conn, claim, effective_at=effective_at) == "MIXED"
            and str(payload.get("diagnosis_scope") or "").upper() != MIXED_SELECTION_BOUNDARY_SCOPE
        ):
            raise ControlPlaneError(
                "mixed_selection_diagnosis_scope_invalid",
                "a mixed selection bundle may record only a non-directional mechanism-boundary diagnosis",
            )
    if event_type == "LEARNING_NOTE_READY":
        if claim["learning_eligibility"] not in METHOD_LEARNING_ELIGIBILITIES:
            raise ControlPlaneError("learning_not_permitted_for_episode", "mechanism-only, evaluation-only or teaching-only episodes cannot create method learning notes")
        if _event_exists(events, "OUTCOME_EXPOSURE_BREACH"):
            raise ControlPlaneError("learning_blocked_by_exposure_breach", "outcome exposure breach blocks learning")
        diagnosis = _last_effective_no_later_than(events, {"DIAGNOSIS_ACCEPTED"}, effective_at)
        if not diagnosis or payload.get("diagnosis_event_id") != diagnosis["event_id"]:
            raise ControlPlaneError("diagnosis_required", "LEARNING_NOTE_READY requires the accepted diagnosis")
        latest_settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, effective_at)
        if not latest_settlement or diagnosis["payload"].get("settlement_event_id") != latest_settlement["event_id"]:
            raise ControlPlaneError("diagnosis_stale_for_settlement", "LEARNING_NOTE_READY requires a diagnosis of the latest settlement version")
        state = _derived_states(claim, events)["settlement_state"]
        expected_scope = "SELECTION_METHOD" if claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE" else "BOUNDARY_OR_ABSTENTION"
        declared_scope = str(payload.get("learning_scope") or expected_scope).upper()
        if state == "UNSETTLED":
            raise ControlPlaneError("learning_not_diagnostic", "an unsettled claim cannot create learning")
        joint_verdict = selection_joint_feedback_verdict(conn, claim, effective_at=effective_at)
        if joint_verdict == "MIXED":
            note_snapshot = payload.get("learning_note_snapshot")
            feedback_snapshot = payload.get("feedback_snapshot")
            feedback_context = (
                note_snapshot.get("feedback_context")
                if isinstance(note_snapshot, dict) and isinstance(note_snapshot.get("feedback_context"), dict)
                else {}
            )
            rival_feedback = (
                feedback_context.get("rival_hypothesis_feedback")
                if isinstance(feedback_context.get("rival_hypothesis_feedback"), dict)
                else {}
            )
            if (
                declared_scope != MIXED_SELECTION_BOUNDARY_SCOPE
                or not isinstance(note_snapshot, dict)
                or note_snapshot.get("disposition") != "INSUFFICIENT_EVIDENCE"
                or rival_feedback.get("overall_verdict") != "MIXED"
                or not isinstance(feedback_snapshot, dict)
                or (feedback_snapshot.get("joint_comparison") or {}).get("overall_verdict") != "MIXED"
            ):
                raise ControlPlaneError(
                    "mixed_selection_boundary_note_invalid",
                    "mixed selection feedback permits only an INSUFFICIENT_EVIDENCE mechanism-boundary note",
                )
            if payload.get("permitted_change_targets") != [] or payload.get("prohibited_rights") != SELECTION_BOUNDARY_PROHIBITED_RIGHTS:
                raise ControlPlaneError(
                    "mixed_selection_boundary_permissions_invalid",
                    "mixed selection feedback grants no directional learning, application, freeze, holdout or report-use rights",
                )
        elif (
            claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE"
            and state in {"NOT_DIAGNOSTIC", "MEASUREMENT_MISMATCH"}
        ):
            if declared_scope != "MEASUREMENT_BOUNDARY":
                raise ControlPlaneError(
                    "learning_not_diagnostic",
                    "NOT_DIAGNOSTIC or MEASUREMENT_MISMATCH cannot create method learning; only a measurement-boundary note is permitted",
                )
            note_snapshot = payload.get("learning_note_snapshot")
            feedback_snapshot = payload.get("feedback_snapshot")
            feedback_context = (
                note_snapshot.get("feedback_context")
                if isinstance(note_snapshot, dict) and isinstance(note_snapshot.get("feedback_context"), dict)
                else {}
            )
            rival_feedback = (
                feedback_context.get("rival_hypothesis_feedback")
                if isinstance(feedback_context.get("rival_hypothesis_feedback"), dict)
                else {}
            )
            if (
                not isinstance(note_snapshot, dict)
                or note_snapshot.get("disposition") != "INSUFFICIENT_EVIDENCE"
                or "MEASUREMENT" not in set(note_snapshot.get("economic_failure_loci") or [])
                or feedback_context.get("judgment_outcome_status") != "NOT_DIAGNOSTIC"
                or rival_feedback.get("overall_verdict") != "NOT_DIAGNOSTIC"
                or not isinstance(feedback_snapshot, dict)
                or (feedback_snapshot.get("joint_comparison") or {}).get("overall_verdict") != "NOT_DIAGNOSTIC"
            ):
                raise ControlPlaneError(
                    "measurement_boundary_note_invalid",
                    "measurement-boundary learning requires an INSUFFICIENT_EVIDENCE note bound to non-diagnostic selection feedback",
                )
            if payload.get("permitted_change_targets") != [
                "CANDIDATE_OBSERVABILITY_GATE", "SOURCE_GATE",
            ]:
                raise ControlPlaneError(
                    "measurement_boundary_permissions_invalid",
                    "measurement-boundary learning may change only candidate observability and source gates",
                )
        elif declared_scope != expected_scope:
            raise ControlPlaneError("learning_scope_invalid", f"learning_scope must be {expected_scope}")
        _require_artifact(_required_text(payload, "learning_note_ref"), field="learning_note_ref")
    if event_type == "LEARNING_APPLIED":
        if claim["learning_eligibility"] not in METHOD_LEARNING_ELIGIBILITIES:
            raise ControlPlaneError("learning_not_permitted_for_episode", "mechanism-only, evaluation-only or teaching-only episodes cannot apply method learning")
        if _event_exists(events, "OUTCOME_EXPOSURE_BREACH"):
            raise ControlPlaneError("learning_blocked_by_exposure_breach", "outcome exposure breach blocks learning")
        note = _last_effective_no_later_than(events, {"LEARNING_NOTE_READY"}, effective_at)
        if not note or payload.get("learning_note_event_id") != note["event_id"]:
            raise ControlPlaneError("learning_note_required", "LEARNING_APPLIED requires the learning note event")
        if str(note["payload"].get("learning_scope") or "").upper() == "MEASUREMENT_BOUNDARY":
            raise ControlPlaneError(
                "measurement_boundary_application_prohibited",
                "measurement-boundary notes cannot create method applications, freezes, holdout rights or report-use rights",
            )
        if selection_joint_feedback_verdict(conn, claim, effective_at=effective_at) == "MIXED":
            raise ControlPlaneError(
                "mixed_selection_application_prohibited",
                "mixed selection feedback cannot create method applications, freezes, holdout rights or report-use rights",
            )
        diagnosis = _event_by_id(events, str(note["payload"].get("diagnosis_event_id") or ""))
        latest_settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, effective_at)
        if not diagnosis or not latest_settlement or diagnosis["payload"].get("settlement_event_id") != latest_settlement["event_id"]:
            raise ControlPlaneError("learning_note_stale_for_settlement", "LEARNING_APPLIED requires a note on the latest settlement version")
        expected_scope = "SELECTION_METHOD" if claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE" else "BOUNDARY_OR_ABSTENTION"
        declared_scope = str(payload.get("learning_scope") or expected_scope).upper()
        if declared_scope != expected_scope:
            raise ControlPlaneError("learning_scope_invalid", f"learning_scope must be {expected_scope}")
        _validate_learning_application(
            conn, claim, payload,
            source_note_effective_at=_parse_time(note["effective_at"], field="learning_note.effective_at"),
            effective_at=effective_at,
        )
    if event_type == "REPLICATION_ACCEPTED":
        if claim["learning_eligibility"] not in METHOD_LEARNING_ELIGIBILITIES:
            raise ControlPlaneError("learning_not_permitted_for_episode", "mechanism-only, evaluation-only or teaching-only episodes cannot close a method replication")
        application = _last_effective_no_later_than(events, {"LEARNING_APPLIED"}, effective_at)
        if not application or payload.get("learning_application_event_id") != application["event_id"]:
            raise ControlPlaneError("learning_application_required", "REPLICATION_ACCEPTED requires a learning application")
        target_event_id = _required_text(payload, "replication_settlement_event_id")
        target = conn.execute(
            """SELECT event.*, claim.episode_id, claim.company_id, claim.learning_eligibility
               FROM judgment_feedback_events AS event
               JOIN judgment_feedback_claims AS claim ON claim.feedback_item_id = event.feedback_item_id
               WHERE event.event_id = ?""",
            (target_event_id,),
        ).fetchone()
        if not target or target["event_type"] != "CLAIM_SETTLED":
            raise ControlPlaneError("replication_settlement_unknown", "replication_settlement_event_id must resolve to a real settled target claim")
        target_payload = _loads(target["payload_json"])
        target_verdict = str(target_payload.get("settlement_verdict") or "").upper()
        if claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE" and target_verdict not in {"A_ONLY", "B_ONLY", "MIXED"}:
            raise ControlPlaneError("replication_target_not_diagnostic", "selection replication target must have a diagnostic settled verdict")
        if claim["learning_eligibility"] == "BOUNDARY_METHOD_ELIGIBLE" and target_verdict not in {"A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"}:
            raise ControlPlaneError("replication_target_boundary_verdict_invalid", "boundary replication target must settle a mechanism or preserve NOT_DIAGNOSTIC")
        if target["learning_eligibility"] != claim["learning_eligibility"]:
            raise ControlPlaneError("replication_target_learning_scope_mismatch", "replication target must use the same learning eligibility")
        if (
            target["episode_id"] != application["payload"].get("target_episode_id")
            or target["company_id"] != application["payload"].get("target_company_id")
        ):
            raise ControlPlaneError("replication_target_application_mismatch", "replication settlement must belong to the learning application's intended target")
        if target["episode_id"] == claim["episode_id"] or target["company_id"] == claim["company_id"]:
            raise ControlPlaneError("replication_target_not_independent", "replication target must be from a different company and episode")
        if _parse_time(target["effective_at"], field="replication_target.effective_at") <= _parse_time(application["effective_at"], field="learning_application.effective_at"):
            raise ControlPlaneError("replication_precedes_application", "replication settlement must occur after the learning application")
        reviewer = _required_text(payload, "reviewer_id")
        if reviewer in {application["actor_id"], target["actor_id"]}:
            raise ControlPlaneError("replication_reviewer_not_independent", "replication reviewer must differ from application and target-settlement actors")
        _require_artifact(_required_text(payload, "reviewer_receipt_ref"), field="reviewer_receipt_ref")
        if _required_text(payload, "reviewer_acceptance").upper() != "ACCEPTED":
            raise ControlPlaneError("reviewer_acceptance_missing", "reviewer_acceptance must be ACCEPTED")
    if event_type == "HOLDOUT_EVALUATION_ACCEPTED":
        _validate_holdout_evaluation_event(conn, claim, event, effective_at=effective_at)
    if event_type == "CLOSED":
        if not (_last_effective_no_later_than(events, OUTCOME_EVENTS | {"OUTCOME_EXPOSURE_BREACH"}, effective_at)):
            raise ControlPlaneError("close_requires_outcome_or_breach", "CLOSED requires an outcome settlement or an exposure breach")
        _required_text(payload, "closure_reason")


def _append_event(
    conn: sqlite3.Connection, event: dict[str, Any], *, recorded_at: str | None = None,
    allow_adapter_events: bool = False,
) -> dict[str, Any]:
    feedback_item_id = _required_text(event, "feedback_item_id")
    event_type = _required_text(event, "event_type").upper()
    if event_type in ADAPTER_ONLY_EVENTS and not allow_adapter_events:
        raise ControlPlaneError(
            "outcome_event_requires_lower_adapter",
            f"{event_type} must be emitted by its lower-module adapter, not append_event()",
        )
    now = _now_dt()
    effective_at_dt = _parse_time(event.get("effective_at"), field="effective_at")
    recorded_at_dt = _parse_time(
        recorded_at or event.get("recorded_at") or _iso(now),
        field="recorded_at",
    )
    if recorded_at_dt > now:
        raise ControlPlaneError("event_recorded_in_future", "control event recorded_at cannot be later than the real current time")
    if effective_at_dt > recorded_at_dt:
        raise ControlPlaneError("event_effective_after_recorded", "control event effective_at cannot be later than recorded_at")
    effective_at = _iso(effective_at_dt)
    actor_role = _required_text(event, "actor_role")
    actor_id = _required_text(event, "actor_id")
    idempotency_key = _required_text(event, "idempotency_key")
    artifact_refs = event.get("artifact_refs", [])
    payload = event.get("payload", {})
    if not isinstance(artifact_refs, list):
        raise ControlPlaneError("artifact_refs_invalid", "artifact_refs must be a list")
    if not artifact_refs:
        raise ControlPlaneError("artifact_refs_missing", "every control event must retain at least one real artifact")
    artifact_refs = [
        _require_artifact(reference, field=f"artifact_refs[{index}]")
        for index, reference in enumerate(artifact_refs)
        if isinstance(reference, str)
    ]
    if len(artifact_refs) != len(event.get("artifact_refs", [])):
        raise ControlPlaneError("artifact_refs_invalid", "artifact_refs must contain only non-empty file references")
    if not isinstance(payload, dict):
        raise ControlPlaneError("payload_invalid", "payload must be an object")
    event_id = str(event.get("event_id") or f"JFE:{uuid.uuid4()}")
    record = {
        "event_id": event_id,
        "feedback_item_id": feedback_item_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "recorded_at": _iso(recorded_at_dt),
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
    _validate_transition(conn, claim, events, record)
    with conn:
        conn.execute(
            """INSERT INTO judgment_feedback_events
               (event_id, feedback_item_id, event_type, effective_at, recorded_at, actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
               VALUES (:event_id, :feedback_item_id, :event_type, :effective_at, :recorded_at, :actor_role, :actor_id, :idempotency_key, :artifact_refs_json, :payload_json)""",
            {**record, "artifact_refs_json": _json(artifact_refs), "payload_json": _json(payload)},
        )
    return {"schema_version": SCHEMA_VERSION, "event_id": event_id, "idempotent": False}


def append_event(conn: sqlite3.Connection, event: dict[str, Any], *, recorded_at: str | None = None) -> dict[str, Any]:
    """Append non-outcome control events through the public API.

    Outcome acquisition, reading, extraction and settlement records need their
    corresponding lower-module receipt.  Those transitions are deliberately
    unavailable to callers that merely have a file path and an event name.
    """
    return _append_event(conn, event, recorded_at=recorded_at)


def _derived_states(claim: dict[str, Any], events: list[dict[str, Any]], *, as_of: datetime | None = None) -> dict[str, str]:
    as_of = as_of or datetime.now(timezone.utc)
    if claim.get("learning_eligibility") == "EVALUATION_ONLY":
        now = _now_dt()
        visible_events = []
        for event in events:
            try:
                effective_at = _parse_time(event["effective_at"], field="event.effective_at")
                recorded_at = _parse_time(event["recorded_at"], field="event.recorded_at")
            except ControlPlaneError:
                continue
            if (
                recorded_at <= now
                and effective_at <= recorded_at
                and effective_at <= as_of
                and recorded_at <= as_of
            ):
                visible_events.append(event)
        events = visible_events
    # A later official release opens a distinct versioned chain.  Never let
    # v1's package/read/extraction make v2 appear finished.
    settlement_events = _settlement_events(events)
    latest_settlement = settlement_events[-1] if settlement_events else None
    pipeline_versions = [
        event["payload"].get("settlement_version", 1)
        for event in events if event["event_type"] in OUTCOME_PIPELINE_EVENTS
        and isinstance(event["payload"].get("settlement_version", 1), int)
    ]
    active_version = max(pipeline_versions) if pipeline_versions and max(pipeline_versions) > len(settlement_events) else (len(settlement_events) or 1)
    blocked = _last_for_version(events, {"ACQUISITION_BLOCKED"}, active_version)
    started = _last_for_version(events, {"ACQUISITION_STARTED"}, active_version)
    if _last_for_version(events, {"OUTCOME_EXTRACTED"}, active_version):
        evidence_state = "EXTRACTED"
    elif _last_for_version(events, {"READ_ATTESTED"}, active_version):
        evidence_state = "READ_ATTESTED"
    elif _last_for_version(events, {"OUTCOME_PACKAGE_READY"}, active_version):
        evidence_state = "PACKAGE_READY"
    elif blocked and not (started and started["payload"].get("retry_of_event_id") == blocked["event_id"]):
        evidence_state = "BLOCKED"
    elif started:
        evidence_state = "ACQUIRING"
    else:
        evidence_state = "EMPTY"
    if _event_exists(events, "CLOSED"):
        time_state = "CLOSED"
    elif as_of < _parse_time(claim["eligible_at"], field="eligible_at"):
        time_state = "WAITING"
    elif claim.get("overdue_at") and as_of > _parse_time(claim["overdue_at"], field="overdue_at") and evidence_state != "EXTRACTED":
        time_state = "OVERDUE"
    else:
        time_state = "DUE"
    settlement = latest_settlement
    if not settlement:
        settlement_state = "UNSETTLED"
    elif settlement["event_type"] == "MEASUREMENT_MISMATCH":
        settlement_state = "MEASUREMENT_MISMATCH"
    elif settlement["event_type"] == OPERATING_OUTCOME_RECORDED:
        settlement_state = "NOT_DIAGNOSTIC"
    else:
        settlement_state = str(settlement["payload"].get("settlement_verdict") or "UNSETTLED").upper()
    latest_diagnosis = next(
        (
            event for event in reversed(events)
            if event["event_type"] == "DIAGNOSIS_ACCEPTED"
            and settlement is not None
            and event["payload"].get("settlement_event_id") == settlement["event_id"]
        ),
        None,
    )
    latest_note = next(
        (
            event for event in reversed(events)
            if event["event_type"] == "LEARNING_NOTE_READY"
            and latest_diagnosis is not None
            and event["payload"].get("diagnosis_event_id") == latest_diagnosis["event_id"]
        ),
        None,
    )
    latest_application = next(
        (
            event for event in reversed(events)
            if event["event_type"] == "LEARNING_APPLIED"
            and latest_note is not None
            and event["payload"].get("learning_note_event_id") == latest_note["event_id"]
        ),
        None,
    )
    latest_replication = next(
        (
            event for event in reversed(events)
            if event["event_type"] == "REPLICATION_ACCEPTED"
            and latest_application is not None
            and event["payload"].get("learning_application_event_id") == latest_application["event_id"]
        ),
        None,
    )
    if _event_exists(events, "CLOSED"):
        learning_state = "CLOSED"
    elif latest_replication:
        learning_state = "CLOSED"
    elif claim["learning_eligibility"] not in METHOD_LEARNING_ELIGIBILITIES:
        learning_state = "NONE"
    elif latest_application:
        learning_state = "REPLICATION_PENDING"
    elif latest_note and str(latest_note["payload"].get("learning_scope") or "").upper() == "MEASUREMENT_BOUNDARY":
        learning_state = "MEASUREMENT_BOUNDARY_READY"
    elif latest_note and str(latest_note["payload"].get("learning_scope") or "").upper() == MIXED_SELECTION_BOUNDARY_SCOPE:
        learning_state = "MIXED_MECHANISM_BOUNDARY_READY"
    elif latest_note:
        learning_state = "APPLICATION_PENDING"
    elif latest_diagnosis:
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
    if states["learning_state"] in {"MEASUREMENT_BOUNDARY_READY", "MIXED_MECHANISM_BOUNDARY_READY"}:
        return "DONE"
    if claim["learning_eligibility"] not in METHOD_LEARNING_ELIGIBILITIES and states["settlement_state"] != "UNSETTLED":
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
            "episode_class": claim["episode_class"],
            "selection_status": claim["selection_status"],
            "learning_eligibility": claim["learning_eligibility"],
            "program_lane": claim["program_lane"],
            "outcome_access": claim["outcome_access"],
            "training_program_ref": claim["training_program_ref"],
            "pre_reveal_review_receipt_ref": claim["pre_reveal_review_receipt_ref"],
            "pre_reveal_review_receipt_json": claim["pre_reveal_review_receipt_json"],
            "registered_at": claim["registered_at"],
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


def read_learning_note_ready_event(
    db_path: str | Path, *, feedback_item_id: str, event_id: str,
    information_cutoff: str,
) -> dict[str, Any]:
    """Read one learning receipt as it was knowable at the report cutoff.

    A learning-note event is not permanently admissible merely because it was
    valid when first recorded.  A later settlement can supersede its diagnosis,
    and an outcome-exposure breach can invalidate method learning.  This read
    therefore replays the narrow event history available at ``information_cutoff``.
    """
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        return {}
    findings: list[str] = []
    cutoff_text = str(information_cutoff or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cutoff_text):
            cutoff = datetime.fromisoformat(cutoff_text).replace(
                hour=23, minute=59, second=59,
                tzinfo=timezone(timedelta(hours=8)),
            ).astimezone(timezone.utc)
        else:
            cutoff = _parse_time(cutoff_text, field="information_cutoff")
    except ControlPlaneError as exc:
        return {
            "admission_state": "BLOCKED",
            "admission_findings": [exc.code],
        }
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT event.*, claim.episode_id, claim.claim_id
               FROM judgment_feedback_events AS event
               JOIN judgment_feedback_claims AS claim
                 ON claim.feedback_item_id = event.feedback_item_id
               WHERE event.feedback_item_id = ? AND event.event_id = ?
                 AND event.event_type = 'LEARNING_NOTE_READY'""",
            (str(feedback_item_id), str(event_id)),
        ).fetchone()
        history_rows = conn.execute(
            """SELECT * FROM judgment_feedback_events
               WHERE feedback_item_id = ?
               ORDER BY effective_at, recorded_at, event_id""",
            (str(feedback_item_id),),
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    if not row:
        return {}
    value = dict(row)
    value["artifact_refs"] = _loads(value.pop("artifact_refs_json"))
    value["payload"] = _loads(value.pop("payload_json"))
    value["control_claim"] = {
        "episode_id": value.pop("episode_id"),
        "claim_id": value.pop("claim_id"),
    }
    history: list[dict[str, Any]] = []
    now = _now_dt()
    for history_row in history_rows:
        event = dict(history_row)
        try:
            effective_at = _parse_time(event.get("effective_at"), field="event.effective_at")
            recorded_at = _parse_time(event.get("recorded_at"), field="event.recorded_at")
        except ControlPlaneError:
            continue
        if effective_at <= cutoff and recorded_at <= cutoff:
            event["artifact_refs"] = _loads(event.pop("artifact_refs_json"))
            event["payload"] = _loads(event.pop("payload_json"))
            event["temporal_findings"] = [
                finding
                for invalid, finding in (
                    (effective_at > recorded_at, "event_effective_after_recorded"),
                    (recorded_at > now, "event_recorded_in_future"),
                )
                if invalid
            ]
            history.append(event)

    available_by_id = {str(event.get("event_id") or ""): event for event in history}
    selected = available_by_id.get(str(event_id))
    if selected is None:
        findings.append("learning_note_event_not_available_at_information_cutoff")
    else:
        ready_events = [
            event for event in history if event.get("event_type") == "LEARNING_NOTE_READY"
        ]
        if ready_events and ready_events[-1].get("event_id") != event_id:
            findings.append("learning_note_ready_event_not_latest_at_information_cutoff")
        diagnosis_id = str((selected.get("payload") or {}).get("diagnosis_event_id") or "")
        diagnosis = available_by_id.get(diagnosis_id)
        settlements = [event for event in history if event.get("event_type") in OUTCOME_EVENTS]
        latest_settlement = settlements[-1] if settlements else None
        dependencies = [event for event in (selected, diagnosis, latest_settlement) if event is not None]
        temporal_findings = [
            f"{finding}:{event.get('event_id')}"
            for event in dependencies
            for finding in event.get("temporal_findings", [])
        ]
        if temporal_findings:
            findings.extend(["invalid_learning_chain", *temporal_findings])
        if (
            diagnosis is None
            or latest_settlement is None
            or (diagnosis.get("payload") or {}).get("settlement_event_id")
            != latest_settlement.get("event_id")
        ):
            findings.append("learning_note_stale_for_latest_settlement_at_information_cutoff")
        if any(event.get("event_type") == "OUTCOME_EXPOSURE_BREACH" for event in history):
            findings.append("learning_note_blocked_by_exposure_breach_at_information_cutoff")
    value["admission_state"] = "REVIEWABLE" if not findings else "BLOCKED"
    value["admission_findings"] = list(dict.fromkeys(findings))
    value["admission_information_cutoff"] = cutoff.isoformat()
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlPlaneError("json_read_failed", f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ControlPlaneError("json_object_required", f"{path} must contain a JSON object")
    return data


def _event_contract(claim: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = _reference_path(claim["source_contract_ref"]).resolve()
    _require_artifact(str(path), field="source_contract_ref")
    return path, _read_json(path)


def _next_settlement_version(claim: dict[str, Any], events: list[dict[str, Any]]) -> int:
    return len(_settlement_events(events)) + 1


def _next_acquisition_attempt(events: list[dict[str, Any]], version: int) -> int:
    return 1 + sum(
        1 for event in events
        if event["event_type"] == "ACQUISITION_STARTED"
        and event["payload"].get("settlement_version", 1) == version
    )


def _adapter_output_path(event_root: str | Path, feedback_item_id: str, version: int, name: str) -> Path:
    safe_id = feedback_item_id.replace(":", "_")
    return Path(event_root).expanduser().resolve() / "feedback_control" / safe_id / f"v{version}" / name


def _selected_source_identity(manifest: dict[str, Any]) -> set[tuple[str, str, str]]:
    inventory = {
        str(item.get("source_id") or ""): item
        for item in manifest.get("inventory") or [] if isinstance(item, dict)
    }
    return {
        (source_id, str(source.get("source_version") or ""), str(source.get("published_at") or ""))
        for source_id in (str(value or "") for value in manifest.get("selected_source_ids") or [])
        if (source := inventory.get(source_id)) is not None
    }


def _blocked_acquisition_root_cause(acquired: dict[str, Any], validation: dict[str, Any]) -> str:
    """Treat a complete official zero-enumeration as unavailable data, not an adapter failure."""
    enumeration = acquired.get("enumeration") if isinstance(acquired.get("enumeration"), dict) else {}
    if (
        validation.get("state") == "INCOMPLETE"
        and not validation.get("invalid_findings")
        and enumeration.get("status") == "COMPLETE"
        and enumeration.get("source_ids") == []
        and acquired.get("inventory") == []
        and acquired.get("selected_source_ids") == []
    ):
        return "DATA_COVERAGE"
    return "ACQUISITION_MODULE"


def _write_adapter_json(path: Path, value: dict[str, Any]) -> Path:
    """Persist an adapter receipt once; a repeated execution reads the receipt.

    We deliberately avoid a second database or a shadow event record.  The
    receipt itself is the event artifact that later adapters re-open.
    """
    if path.exists():
        _read_json(path)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_immutable_adapter_json(path: Path, value: dict[str, Any]) -> Path:
    if path.exists():
        if _read_json(path) != value:
            raise ControlPlaneError(
                "selection_adapter_artifact_conflict",
                f"existing adapter artifact differs from the derived selection receipt: {path}",
            )
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _selection_control_context(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    claim_rows = [dict(row) for row in conn.execute(
        """SELECT * FROM judgment_feedback_claims
             WHERE episode_id = ?
             ORDER BY registered_at, feedback_item_id""",
        (case_id,),
    ).fetchall()]
    claim_stage_ids = [row["stage_id"] for row in claim_rows]
    if (
        len(claim_rows) not in {5, 6}
        or len(set(claim_stage_ids)) != len(claim_stage_ids)
        or frozenset(claim_stage_ids) not in {
            frozenset(order) for order in SELECTION_STAGE_ORDERS
        }
    ):
        raise ControlPlaneError(
            "selection_feedback_claim_bundle_invalid",
            "settle-selection requires the five-layer bundle with at most one optional D3 product-volume claim",
        )
    if any(
        row["program_lane"] != "HISTORICAL_TRAINING"
        or row["selection_status"] != "SELECTION_ADMITTED"
        or row["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE"
        or row["outcome_access"] != "PIT_OUTCOME_SEALED"
        for row in claim_rows
    ):
        raise ControlPlaneError(
            "selection_settlement_identity_invalid",
            "all selection claims must remain sealed HISTORICAL_TRAINING and SELECTION_METHOD_ELIGIBLE",
        )
    for field in (
        "training_program_ref", "selection_resolution_ref",
        "selection_resolution_review_ref", "selection_outcome_custodian_id",
    ):
        if len({str(row[field]) for row in claim_rows}) != 1 or not str(claim_rows[0][field]).strip():
            raise ControlPlaneError(
                "selection_registration_binding_mismatch",
                f"the registered selection claims do not share immutable {field}",
            )
    program = conn.execute(
        """SELECT program.program_id, program.program_state, program.contract_ref,
                  episode.training_episode_id
             FROM judgment_training_programs AS program
             JOIN judgment_training_episodes AS episode USING (program_id)
            WHERE episode.case_id = ?
              AND episode.lane = 'HISTORICAL_TRAINING'
              AND program.contract_ref = ?""",
        (case_id, claim_rows[0]["training_program_ref"]),
    ).fetchone()
    if program is None:
        raise ControlPlaneError(
            "selection_candidate_program_registration_required",
            "selection claims are not bound to a training episode in this database",
        )
    if program["program_state"] != "ACTIVE":
        raise ControlPlaneError(
            "selection_training_program_not_active",
            "DRAFT training programs cannot settle historical selection outcomes",
        )
    case_event = conn.execute(
        """SELECT artifact_event_id, artifact_ref, recorded_at, content_json
             FROM judgment_training_artifact_events
            WHERE training_episode_id = ? AND artifact_kind = 'case_ref'""",
        (program["training_episode_id"],),
    ).fetchone()
    if case_event is None or not case_event["content_json"]:
        raise ControlPlaneError(
            "selection_candidate_snapshot_missing",
            "selection training episode has no immutable frozen case snapshot",
        )
    registration_events: dict[str, dict[str, Any]] = {}
    snapshots: list[dict[str, Any]] = []
    for claim in claim_rows:
        event = conn.execute(
            """SELECT * FROM judgment_feedback_events
                WHERE feedback_item_id = ? AND event_type = 'CLAIM_REGISTERED'""",
            (claim["feedback_item_id"],),
        ).fetchone()
        if event is None:
            raise ControlPlaneError(
                "selection_registration_event_missing",
                "a selection claim has no immutable CLAIM_REGISTERED event",
            )
        decoded = {
            **dict(event),
            "artifact_refs": _loads(event["artifact_refs_json"]),
            "payload": _loads(event["payload_json"]),
        }
        registration_events[claim["claim_id"]] = decoded
        snapshots.append(decoded["payload"])
    required_snapshots = {
        "frozen_case_snapshot", "selection_review_snapshot", "source_contract_snapshot",
        "measurement_contract_snapshot", "registration_snapshot",
        "selection_resolution_snapshot", "selection_resolution_review_snapshot",
    }
    first_payload = snapshots[0]
    if not required_snapshots.issubset(first_payload) or any(
        any(payload.get(field) != first_payload.get(field) for field in required_snapshots)
        for payload in snapshots[1:]
    ):
        raise ControlPlaneError(
            "selection_registration_snapshot_mismatch",
            "the CLAIM_REGISTERED events do not retain one identical frozen selection packet",
        )
    candidate = _loads(case_event["content_json"])
    if candidate != first_payload["frozen_case_snapshot"]:
        raise ControlPlaneError(
            "selection_candidate_snapshot_mismatch",
            "CLAIM_REGISTERED frozen case differs from the training database snapshot",
        )
    registration = first_payload["registration_snapshot"]
    registration_items = registration.get("feedback_items") if isinstance(registration, dict) else None
    if not isinstance(registration_items, list):
        raise ControlPlaneError(
            "selection_registration_snapshot_invalid",
            "selection registration snapshot has no feedback item list",
        )
    claim_by_id = {row["claim_id"]: row for row in claim_rows}
    registered_claim_ids = [str(item.get("claim_id") or "") for item in registration_items if isinstance(item, dict)]
    registered_stage_ids = [
        str(item.get("stage_id") or "") for item in registration_items if isinstance(item, dict)
    ]
    if (
        len(registered_claim_ids) != len(claim_rows)
        or len(claim_by_id) != len(claim_rows)
        or tuple(registered_stage_ids) not in SELECTION_STAGE_ORDERS
        or set(registered_claim_ids) != set(claim_by_id)
        or any(
            claim_by_id[claim_id]["stage_id"] != registration_items[index].get("stage_id")
            for index, claim_id in enumerate(registered_claim_ids)
        )
    ):
        raise ControlPlaneError(
            "selection_registration_snapshot_invalid",
            "selection registration snapshot does not match the ordered database claims",
        )
    claims = [claim_by_id[claim_id] for claim_id in registered_claim_ids]
    ordered_registration_events = {
        claim_id: registration_events[claim_id]["event_id"] for claim_id in registered_claim_ids
    }
    for claim in claims:
        registered_event = registration_events[claim["claim_id"]]
        refs = {str(_reference_path(ref).resolve()) for ref in registered_event["artifact_refs"]}
        if (
            str(_reference_path(claim["selection_resolution_ref"]).resolve()) not in refs
            or str(_reference_path(claim["selection_resolution_review_ref"]).resolve()) not in refs
            or registered_event["payload"].get("registration_event_id") != registered_event["event_id"]
        ):
            raise ControlPlaneError(
                "selection_registered_reference_mismatch",
                "selection resolution bindings are not retained by CLAIM_REGISTERED",
            )
    release_rows = conn.execute(
        """SELECT event.* FROM judgment_feedback_events AS event
             JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
            WHERE claim.episode_id = ? AND event.event_type = 'OUTCOME_RELEASE_AUTHORIZED'""",
        (case_id,),
    ).fetchall()
    if len(release_rows) != 1:
        raise ControlPlaneError(
            "selection_outcome_release_missing",
            "selection settlement requires exactly one canonical pre-outcome release event",
        )
    release = {
        **dict(release_rows[0]),
        "artifact_refs": _loads(release_rows[0]["artifact_refs_json"]),
        "payload": _loads(release_rows[0]["payload_json"]),
    }
    context = {
        "program_id": program["program_id"],
        "program_state": program["program_state"],
        "training_episode_id": program["training_episode_id"],
        "program_reservation_event_id": f"JTAE:{case_event['artifact_event_id']}",
        "candidate": candidate,
        "selection_review": first_payload["selection_review_snapshot"],
        "source_contract": first_payload["source_contract_snapshot"],
        "measurement_contract": first_payload["measurement_contract_snapshot"],
        "registration": registration,
        "resolution": first_payload["selection_resolution_snapshot"],
        "resolution_review": first_payload["selection_resolution_review_snapshot"],
        "custodian_id": claim_rows[0]["selection_outcome_custodian_id"],
        "rows": claims,
    }
    expected_activation = _selection_activation_snapshot(
        context,
        registered_at=release["recorded_at"],
        registration_event_ids=ordered_registration_events,
        outcome_release_event_id=release["event_id"],
    )
    expected_activation["activated_at"] = release["effective_at"]
    if release["payload"].get("activation_snapshot") != expected_activation:
        raise ControlPlaneError(
            "selection_activation_snapshot_mismatch",
            "outcome release activation does not reconstruct from current canonical control rows",
        )
    context.update({
        "activation": expected_activation,
        "registration_events": registration_events,
        "outcome_release_event": release,
    })
    return context


def _append_adapter_event(
    conn: sqlite3.Connection, *, feedback_item_id: str, event_type: str, effective_at: str,
    actor_id: str, idempotency_key: str, artifact_refs: list[str], payload: dict[str, Any],
    recorded_at: str | None = None,
) -> dict[str, Any]:
    _validate_adapter_event_receipt(
        conn, feedback_item_id=feedback_item_id, event_type=event_type, artifact_refs=artifact_refs, payload=payload,
    )
    return _append_event(conn, {
        "feedback_item_id": feedback_item_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "actor_role": "AUTOMATION",
        "actor_id": actor_id,
        "idempotency_key": idempotency_key,
        "artifact_refs": artifact_refs,
        "payload": payload,
    }, recorded_at=recorded_at, allow_adapter_events=True)


def _adapter_path(payload: dict[str, Any], field: str) -> Path:
    value = _required_text(payload, field)
    path = _reference_path(value).resolve()
    _require_artifact(str(path), field=field)
    return path


def _selection_feedback_from_outcome(
    context: dict[str, Any], outcome: dict[str, Any],
) -> dict[str, Any]:
    try:
        from scripts.judgment_selection_feedback import (
            SelectionFeedbackError,
            build_selection_feedback,
            validate_selection_outcome,
        )
    except ModuleNotFoundError:
        from judgment_selection_feedback import (
            SelectionFeedbackError,
            build_selection_feedback,
            validate_selection_outcome,
        )
    validation = validate_selection_outcome(
        outcome,
        frozen_case=context["candidate"],
        measurement_contract=context["measurement_contract"],
        registration=context["registration"],
        resolution_amendment=context["resolution"],
        amendment_review_receipt=context["resolution_review"],
        activation_receipt=context["activation"],
        source_contract=context["source_contract"],
    )
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError(
            "selection_outcome_not_reviewable",
            "; ".join(validation.get("findings") or ["selection outcome validation failed"]),
        )
    try:
        return build_selection_feedback(
            outcome,
            frozen_case=context["candidate"],
            measurement_contract=context["measurement_contract"],
            registration=context["registration"],
            resolution_amendment=context["resolution"],
            amendment_review_receipt=context["resolution_review"],
            activation_receipt=context["activation"],
            source_contract=context["source_contract"],
        )
    except SelectionFeedbackError as exc:
        raise ControlPlaneError("selection_feedback_build_failed", str(exc)) from exc


def _selection_reader_receipt(
    outcome_path: Path, outcome: dict[str, Any], activation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "judgment-selection-reader-attestation.v1",
        "state": "REVIEWABLE",
        "case_id": outcome["case_id"],
        "settlement_id": outcome["settlement_id"],
        "outcome_ref": str(outcome_path),
        "activation_id": activation["activation_id"],
        "custodian_id": activation["custodian_id"],
        "source_ids": list(dict.fromkeys(
            str(source_id)
            for claim in outcome.get("claims") or [] if isinstance(claim, dict)
            for source_id in claim.get("source_ids") or []
        )),
    }


def _selection_extraction_receipt(
    outcome_path: Path, outcome: dict[str, Any], activation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "judgment-selection-extraction.v1",
        "state": "REVIEWABLE",
        "case_id": outcome["case_id"],
        "settlement_id": outcome["settlement_id"],
        "outcome_ref": str(outcome_path),
        "activation_id": activation["activation_id"],
        "claim_observations": deepcopy(outcome["claims"]),
    }


def _validate_selection_adapter_event_receipt(
    conn: sqlite3.Connection, *, claim: dict[str, Any], event_type: str,
    artifact_refs: list[str], payload: dict[str, Any],
) -> None:
    context = _selection_control_context(conn, claim["episode_id"])
    if payload.get("selection_activation_snapshot") != context["activation"]:
        raise ControlPlaneError(
            "selection_activation_not_canonical",
            "selection adapter event must retain the activation reconstructed from the control database",
        )
    outcome_path = _adapter_path(payload, "outcome_ref")
    refs = {str(_reference_path(reference).resolve()) for reference in artifact_refs}
    if str(outcome_path) not in refs:
        raise ControlPlaneError(
            "adapter_receipt_missing",
            "selection adapter event must retain its custodian outcome",
        )
    outcome = _read_json(outcome_path)
    feedback = _selection_feedback_from_outcome(context, outcome)
    if payload.get("settlement_id") != outcome.get("settlement_id"):
        raise ControlPlaneError(
            "selection_settlement_identity_mismatch",
            "selection adapter event settlement_id differs from the custodian outcome",
        )
    if event_type in {"ACQUISITION_STARTED", "OUTCOME_PACKAGE_READY"}:
        return
    reader_path = _adapter_path(payload, "read_attestation_ref")
    expected_reader = _selection_reader_receipt(
        outcome_path, outcome, context["activation"],
    )
    if _read_json(reader_path) != expected_reader or str(reader_path) not in refs:
        raise ControlPlaneError(
            "selection_reader_receipt_invalid",
            "selection READ_ATTESTED receipt does not match the custodian outcome",
        )
    if event_type == "READ_ATTESTED":
        return
    extraction_path = _adapter_path(payload, "extraction_ref")
    expected_extraction = _selection_extraction_receipt(
        outcome_path, outcome, context["activation"],
    )
    if _read_json(extraction_path) != expected_extraction or str(extraction_path) not in refs:
        raise ControlPlaneError(
            "selection_extraction_receipt_invalid",
            "selection OUTCOME_EXTRACTED receipt does not match the custodian outcome",
        )
    if event_type == "OUTCOME_EXTRACTED":
        return
    if event_type not in {"CLAIM_SETTLED", "MEASUREMENT_MISMATCH"}:
        raise ControlPlaneError(
            "selection_adapter_event_invalid",
            f"{event_type} is not a selection settlement adapter event",
        )
    feedback_path = _adapter_path(payload, "feedback_ref")
    if _read_json(feedback_path) != feedback or str(feedback_path) not in refs:
        raise ControlPlaneError(
            "selection_feedback_receipt_invalid",
            "selection settlement event does not retain the mechanically derived feedback",
        )
    card = next(
        (item for item in feedback["cards"] if item.get("claim_id") == claim["claim_id"]),
        None,
    )
    if card is None:
        raise ControlPlaneError(
            "selection_feedback_claim_missing",
            "derived selection feedback does not contain the registered claim",
        )
    observation_status = card["observation"]["status"]
    if event_type == "MEASUREMENT_MISMATCH":
        if observation_status != "MEASUREMENT_MISMATCH" or payload.get("resolution") != "NOT_DIAGNOSTIC":
            raise ControlPlaneError(
                "selection_measurement_mismatch_invalid",
                "MEASUREMENT_MISMATCH must be derived from the registered claim observation",
            )
    elif (
        observation_status == "MEASUREMENT_MISMATCH"
        or payload.get("settlement_verdict") != card["comparison"]["verdict"]
    ):
        raise ControlPlaneError(
            "selection_settlement_verdict_mismatch",
            "selection control verdict must equal the mechanically derived claim comparison",
        )


def _validate_adapter_event_receipt(
    conn: sqlite3.Connection, *, feedback_item_id: str, event_type: str,
    artifact_refs: list[str], payload: dict[str, Any],
) -> None:
    """Require a lower-module receipt at the control-plane transition boundary.

    The CLI restriction is only ergonomics.  This validation sits behind both
    the CLI and the Python adapters so a generic event with an unrelated file
    cannot be mistaken for acquisition, reading, extraction or settlement.
    """
    if event_type not in ADAPTER_ONLY_EVENTS:
        return
    claim = _claim(conn, feedback_item_id)
    refs = {str(_reference_path(reference).resolve()) for reference in artifact_refs}
    if (
        claim["program_lane"] == "HISTORICAL_TRAINING"
        and claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE"
    ):
        _validate_selection_adapter_event_receipt(
            conn,
            claim=claim,
            event_type=event_type,
            artifact_refs=artifact_refs,
            payload=payload,
        )
        return
    if claim["learning_eligibility"] == "EVALUATION_ONLY":
        if claim["program_lane"] != "HISTORICAL_HOLDOUT":
            raise ControlPlaneError(
                "holdout_evaluation_identity_invalid",
                "EVALUATION_ONLY adapter events require HISTORICAL_HOLDOUT",
            )
        if event_type == "OUTCOME_EXPOSURE_BREACH":
            breach_path = _adapter_path(payload, "breach_ref")
            if str(breach_path) not in refs:
                raise ControlPlaneError("adapter_receipt_missing", "holdout breach must retain its discovery artifact")
            validated = _validate_holdout_exposure_breach_artifact(
                breach_path, claim=claim, now=_now_dt(),
            )
            if payload.get("breach_snapshot") != validated["receipt"]:
                raise ControlPlaneError("holdout_breach_snapshot_mismatch", "breach event must retain the exact discovery artifact")
            if payload.get("first_outcome_accessed_at") != _iso(validated["first_outcome_accessed_at"]):
                raise ControlPlaneError("holdout_breach_access_time_mismatch", "breach payload must retain first outcome access time")
            return
        if event_type == "HOLDOUT_EVALUATION_ACCEPTED":
            receipt_path = _adapter_path(payload, "receipt_ref")
            if str(receipt_path) not in refs:
                raise ControlPlaneError("adapter_receipt_missing", "holdout acceptance must retain its evaluation receipt")
            receipt = _read_json(receipt_path)
            if receipt.get("schema_version") != HOLDOUT_EVALUATION_RECEIPT_SCHEMA_VERSION:
                raise ControlPlaneError("holdout_receipt_schema_invalid", "unsupported holdout evaluation receipt schema")
            field_map = {
                "receipt_id": "receipt_id",
                "program_id": "program_id",
                "training_episode_id": "training_episode_id",
                "case_id": "case_id",
                "method_version": "method_version",
                "method_frozen_at": "method_frozen_at",
                "evaluated_at": "evaluated_at",
                "evaluation_verdict": "evaluation_verdict",
                "evaluation_author_id": "evaluation_author_id",
                "reviewer_id": "reviewer_id",
                "reviewer_acceptance": "reviewer_acceptance",
                "claim_settlements": "claim_settlements",
            }
            if any(payload.get(payload_field) != receipt.get(receipt_field) for payload_field, receipt_field in field_map.items()):
                raise ControlPlaneError("holdout_receipt_payload_mismatch", "accepted event must reproduce the evaluation receipt")
            if payload.get("receipt_snapshot") != receipt:
                raise ControlPlaneError("holdout_receipt_snapshot_mismatch", "accepted event must retain the exact evaluation receipt snapshot")
            return

        try:
            from scripts.judgment_boundary_feedback import validate_boundary_outcome
        except ModuleNotFoundError:
            from judgment_boundary_feedback import validate_boundary_outcome
        _settlement_version(claim, {"payload": payload})
        if event_type == "ACQUISITION_STARTED":
            outcome_path = _adapter_path(payload, "outcome_manifest_ref")
            if str(outcome_path) not in refs:
                raise ControlPlaneError("adapter_receipt_missing", "holdout acquisition must retain its outcome manifest")
            if validate_boundary_outcome(_read_json(outcome_path)).get("state") != "REVIEWABLE":
                raise ControlPlaneError("holdout_outcome_not_reviewable", "holdout outcome manifest is not reviewable")
            outcome = _read_json(outcome_path)
            first_accessed_at = _parse_time(
                outcome.get("first_outcome_accessed_at"), field="outcome.first_outcome_accessed_at",
            )
            if payload.get("first_outcome_accessed_at") != _iso(first_accessed_at):
                raise ControlPlaneError(
                    "holdout_first_access_mismatch",
                    "holdout acquisition must retain the outcome's first access time",
                )
            pre_review = _holdout_pre_reveal_context(claim)
            if payload.get("pre_reveal_review_receipt_ref") != pre_review["path"] or pre_review["path"] not in refs:
                raise ControlPlaneError(
                    "holdout_pre_reveal_review_not_retained",
                    "holdout acquisition must retain its registered pre-reveal review receipt",
                )
            return
        if event_type in {"OUTCOME_PACKAGE_READY", "READ_ATTESTED", "OUTCOME_EXTRACTED"}:
            fields = {
                "OUTCOME_PACKAGE_READY": ("package_manifest_ref",),
                "READ_ATTESTED": ("package_manifest_ref", "read_attestation_ref"),
                "OUTCOME_EXTRACTED": ("package_manifest_ref", "read_attestation_ref", "extraction_ref"),
            }[event_type]
            paths = [_adapter_path(payload, field) for field in fields]
            if any(str(path) not in refs for path in paths):
                raise ControlPlaneError("adapter_receipt_missing", "holdout event must retain all lower-module receipts")
            if validate_boundary_outcome(_read_json(paths[0])).get("state") != "REVIEWABLE":
                raise ControlPlaneError("holdout_outcome_not_reviewable", "holdout lower receipt is not reviewable")
            return
        if event_type in {"CLAIM_SETTLED", "MEASUREMENT_MISMATCH"}:
            settlement_path = _adapter_path(payload, "settlement_ref")
            settlement = _read_json(settlement_path)
            if validate_boundary_outcome(settlement).get("state") != "REVIEWABLE":
                raise ControlPlaneError("holdout_settlement_invalid", "holdout settlement receipt is not reviewable")
            context = _require_frozen_holdout_program(
                conn,
                claim,
                effective_at=_parse_time(payload.get("settlement_as_of"), field="settlement_as_of"),
                program_id=str(payload.get("program_id") or "") or None,
            )
            current = next(
                (item for item in settlement.get("clocks") or [] if item.get("claim_id") == claim["claim_id"]),
                None,
            )
            if (
                settlement.get("case_id") != claim.get("episode_id")
                or settlement.get("freeze_id") != context["training_episode_id"]
                or current is None
                or current.get("clock") != _holdout_clock_id(claim)
            ):
                raise ControlPlaneError("holdout_settlement_identity_mismatch", "holdout settlement belongs to another frozen D1-D5 claim")
            if str(settlement_path) not in refs:
                raise ControlPlaneError("adapter_receipt_missing", "holdout settlement must retain its outcome receipt")
            return
    _, contract = _event_contract(claim)
    version = _settlement_version(claim, {"payload": payload})

    if claim["learning_eligibility"] == "BOUNDARY_METHOD_ELIGIBLE":
        # Boundary replays use a narrow, non-selection outcome contract.  They
        # still retain the same acquisition/read/extraction event chain, but
        # do not pretend to be a full historical backtest or A/B forecast.
        try:
            from scripts.judgment_boundary_feedback import build_boundary_feedback, validate_boundary_outcome
        except ModuleNotFoundError:
            from judgment_boundary_feedback import build_boundary_feedback, validate_boundary_outcome
        if event_type == "ACQUISITION_STARTED":
            outcome_path = _adapter_path(payload, "outcome_manifest_ref")
            if str(outcome_path) not in refs:
                raise ControlPlaneError("adapter_receipt_missing", "boundary acquisition must retain its outcome manifest")
            outcome = _read_json(outcome_path)
            if validate_boundary_outcome(outcome).get("state") != "REVIEWABLE":
                raise ControlPlaneError("boundary_outcome_not_reviewable", "boundary outcome manifest is not reviewable")
            return
        if event_type in {"OUTCOME_PACKAGE_READY", "READ_ATTESTED", "OUTCOME_EXTRACTED"}:
            fields = {
                "OUTCOME_PACKAGE_READY": ("package_manifest_ref",),
                "READ_ATTESTED": ("package_manifest_ref", "read_attestation_ref"),
                "OUTCOME_EXTRACTED": ("package_manifest_ref", "read_attestation_ref", "extraction_ref"),
            }[event_type]
            paths = [_adapter_path(payload, field) for field in fields]
            if any(str(path) not in refs for path in paths):
                raise ControlPlaneError("adapter_receipt_missing", "boundary event must retain all lower-module receipts")
            outcome = _read_json(paths[0])
            if validate_boundary_outcome(outcome).get("state") != "REVIEWABLE":
                raise ControlPlaneError("boundary_outcome_not_reviewable", "boundary lower receipt is not reviewable")
            return
        if event_type in {"CLAIM_SETTLED", "MEASUREMENT_MISMATCH"}:
            settlement_path = _adapter_path(payload, "settlement_ref")
            settlement = _read_json(settlement_path)
            if validate_boundary_outcome(settlement).get("state") != "REVIEWABLE":
                raise ControlPlaneError("boundary_settlement_invalid", "boundary settlement receipt is not reviewable")
            frozen_case = _read_json(_reference_path(claim["frozen_artifact_ref"]))
            expected_freeze = str(frozen_case.get("freeze_id") or "")
            if settlement.get("case_id") != claim.get("episode_id") or not expected_freeze or settlement.get("freeze_id") != expected_freeze:
                raise ControlPlaneError("boundary_settlement_identity_mismatch", "boundary settlement receipt belongs to another frozen case")
            if str(settlement_path) not in refs:
                raise ControlPlaneError("adapter_receipt_missing", "boundary settlement must retain its outcome receipt")
            return

    if event_type == "ACQUISITION_STARTED":
        manifest_path = _adapter_path(payload, "outcome_manifest_ref")
        if str(manifest_path) not in refs:
            raise ControlPlaneError("adapter_receipt_missing", "ACQUISITION_STARTED must retain its bounded outcome manifest")
        _read_json(manifest_path)
        return

    if event_type == "ACQUISITION_BLOCKED":
        receipt_path = _adapter_path(payload, "package_manifest_ref")
        if str(receipt_path) not in refs:
            raise ControlPlaneError("adapter_receipt_missing", "ACQUISITION_BLOCKED must retain its acquisition receipt")
        receipt = _read_json(receipt_path)
        if receipt.get("settlement_version") not in (None, version):
            raise ControlPlaneError("adapter_receipt_version_mismatch", "blocked acquisition receipt belongs to another settlement version")
        return

    try:
        from scripts.outcome_acquisition import read_outcome_package, validate_outcome_extraction, validate_outcome_package
    except ModuleNotFoundError:
        from outcome_acquisition import read_outcome_package, validate_outcome_extraction, validate_outcome_package

    if event_type == "OUTCOME_PACKAGE_READY":
        manifest_path = _adapter_path(payload, "package_manifest_ref")
        package_root = _required_text(payload, "package_root")
        validation = validate_outcome_package(
            _read_json(manifest_path), package_root, case=contract,
            settlement_as_of=str(payload.get("settlement_as_of") or ""),
        )
        if validation.get("state") != "REVIEWABLE":
            raise ControlPlaneError("adapter_package_not_reviewable", "OUTCOME_PACKAGE_READY requires a reviewable lower acquisition receipt")
        if str(manifest_path) not in refs:
            raise ControlPlaneError("adapter_receipt_missing", "OUTCOME_PACKAGE_READY must retain its package manifest")
        return

    if event_type == "READ_ATTESTED":
        manifest_path = _adapter_path(payload, "package_manifest_ref")
        attestation_path = _adapter_path(payload, "read_attestation_ref")
        package_root = _required_text(payload, "package_root")
        expected = read_outcome_package(
            _read_json(manifest_path), package_root, case=contract,
            settlement_as_of=str(payload.get("settlement_as_of") or ""),
        )
        if _read_json(attestation_path) != expected or expected.get("state") != "REVIEWABLE":
            raise ControlPlaneError("adapter_read_attestation_invalid", "READ_ATTESTED receipt is not the bound lower reader audit")
        if {str(manifest_path), str(attestation_path)} - refs:
            raise ControlPlaneError("adapter_receipt_missing", "READ_ATTESTED must retain package and reader receipts")
        return

    if event_type == "OUTCOME_EXTRACTED":
        manifest_path = _adapter_path(payload, "package_manifest_ref")
        attestation_path = _adapter_path(payload, "read_attestation_ref")
        extraction_path = _adapter_path(payload, "extraction_ref")
        package_root = _required_text(payload, "package_root")
        validation = validate_outcome_extraction(
            _read_json(extraction_path), manifest=_read_json(manifest_path), package_root=package_root,
            read_attestation=_read_json(attestation_path), case=contract,
            settlement_as_of=str(payload.get("settlement_as_of") or ""),
        )
        if validation.get("state") != "REVIEWABLE":
            raise ControlPlaneError("adapter_extraction_not_reviewable", "OUTCOME_EXTRACTED requires a reviewable bound extraction")
        if {str(manifest_path), str(attestation_path), str(extraction_path)} - refs:
            raise ControlPlaneError("adapter_receipt_missing", "OUTCOME_EXTRACTED must retain package, reader and extraction receipts")
        return

    if event_type == OPERATING_OUTCOME_RECORDED:
        record_path = _adapter_path(payload, "operating_outcome_ref")
        record = _read_json(record_path)
        expected = {
            "schema_version": OPERATING_OUTCOME_RECORD_SCHEMA_VERSION,
            "case_id": contract.get("case_id"),
            "freeze_id": (contract.get("report_freeze") or {}).get("freeze_id"),
            "feedback_item_id": feedback_item_id,
            "claim_id": claim["claim_id"],
            "settlement_version": version,
            "settlement_as_of": payload.get("settlement_as_of"),
        }
        if any(record.get(field) != value for field, value in expected.items()):
            raise ControlPlaneError("adapter_operating_outcome_identity_mismatch", "operating outcome receipt is not bound to this claim/version")
        if record.get("status") != payload.get("operating_outcome_status"):
            raise ControlPlaneError("adapter_operating_outcome_status_mismatch", "operating outcome status must equal its receipt")
        manifest_path = _adapter_path(record, "package_manifest_ref")
        read_path = _adapter_path(record, "read_attestation_ref")
        extraction_path = _adapter_path(record, "extraction_ref")
        package_root = _required_text(record, "package_root")
        validation = validate_outcome_extraction(
            _read_json(extraction_path), manifest=_read_json(manifest_path), package_root=package_root,
            read_attestation=_read_json(read_path), case=contract,
            settlement_as_of=str(record.get("settlement_as_of") or ""),
        )
        if validation.get("state") != "REVIEWABLE":
            raise ControlPlaneError("adapter_operating_outcome_extraction_invalid", "operating outcome must retain a reviewable bound extraction")
        if {str(record_path), str(manifest_path), str(read_path), str(extraction_path)} - refs:
            raise ControlPlaneError("adapter_receipt_missing", "operating outcome must retain its package, reader, extraction and derived receipts")
        return

    if event_type in {"CLAIM_SETTLED", "MEASUREMENT_MISMATCH"}:
        settlement_path = _adapter_path(payload, "settlement_ref")
        settlement = _read_json(settlement_path)
        if settlement.get("schema_version") != "turtle-live-forward-signal-settlement.v1" or settlement.get("state") != "REVIEWABLE":
            raise ControlPlaneError("adapter_settlement_invalid", "settlement event requires a reviewable mechanical signal settlement")
        if settlement.get("case_id") != contract.get("case_id") or settlement.get("freeze_id") != (contract.get("report_freeze") or {}).get("freeze_id"):
            raise ControlPlaneError("adapter_settlement_identity_mismatch", "settlement receipt belongs to another frozen case")
        current = next(
            (item for item in settlement.get("claim_settlements") or [] if isinstance(item, dict) and item.get("claim_id") == claim["claim_id"]),
            None,
        )
        if not current:
            raise ControlPlaneError("adapter_settlement_claim_missing", "settlement receipt does not contain this frozen claim")
        if event_type == "CLAIM_SETTLED" and payload.get("settlement_verdict") != current.get("signal_verdict"):
            raise ControlPlaneError("adapter_settlement_verdict_mismatch", "control verdict must equal the mechanical signal verdict")
        if event_type == "MEASUREMENT_MISMATCH" and not (
            current.get("status") == "NOT_CALCULABLE" and current.get("resolution") == "MEASUREMENT_MISMATCH"
        ):
            raise ControlPlaneError("adapter_measurement_mismatch_invalid", "measurement mismatch must be derived by the lower settlement")
        if str(settlement_path) not in refs:
            raise ControlPlaneError("adapter_receipt_missing", "settlement event must retain its mechanical settlement receipt")


def run_outcome_acquisition(
    conn: sqlite3.Connection, *, feedback_item_id: str, outcome_manifest_ref: str | Path,
    package_root: str | Path, event_root: str | Path, settlement_as_of: str,
    actor_id: str = "judgment_feedback_control", downloader: Any = None,
) -> dict[str, Any]:
    """Run the bounded lower acquisition module, then append its real receipt.

    The caller must supply a post-cutoff *bounded inventory*; this adapter
    never invents an issuer query from a claim.  A failed lower acquisition is
    recorded as BLOCKED and leaves the item at P1 rather than pretending a
    package exists.
    """
    try:
        from scripts.outcome_acquisition import acquire_outcome_package, validate_outcome_package
    except ModuleNotFoundError:
        from outcome_acquisition import acquire_outcome_package, validate_outcome_package
    claim = _claim(conn, feedback_item_id)
    events = _events(conn, feedback_item_id)
    version = _next_settlement_version(claim, events)
    attempt = _next_acquisition_attempt(events, version)
    manifest_path = _reference_path(str(outcome_manifest_ref)).resolve()
    _require_artifact(str(manifest_path), field="outcome_manifest_ref")
    _, contract = _event_contract(claim)
    bound_settlement_as_of = _required_text({"settlement_as_of": settlement_as_of}, "settlement_as_of")
    settled_as_of = _iso(_parse_time(bound_settlement_as_of, field="settlement_as_of"))
    ready = _last_for_version(events, {"OUTCOME_PACKAGE_READY"}, version)
    if ready:
        return {
            "schema_version": SCHEMA_VERSION, "status": "PACKAGE_ALREADY_READY", "feedback_item_id": feedback_item_id,
            "settlement_version": version, "package_manifest_ref": ready["payload"].get("package_manifest_ref"),
        }
    previous_block = _last_for_version(events, {"ACQUISITION_BLOCKED"}, version)
    start_payload = {
        "settlement_version": version, "acquisition_attempt": attempt,
        "outcome_manifest_ref": str(manifest_path), "package_root": str(Path(package_root).resolve()),
    }
    if previous_block:
        start_payload["retry_of_event_id"] = previous_block["event_id"]
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_STARTED", effective_at=settled_as_of,
        actor_id=actor_id,
        idempotency_key=(
            f"ACQUISITION_STARTED:{feedback_item_id}:v{version}:a{attempt}:{manifest_path}"
            + (f":retry:{previous_block['event_id']}" if previous_block else "")
        ),
        artifact_refs=[str(manifest_path)],
        payload=start_payload,
    )
    receipt_path = _adapter_output_path(
        event_root, feedback_item_id, version, f"attempt-{attempt:02d}/01_outcome_package_manifest.json",
    )
    try:
        acquired = acquire_outcome_package(_read_json(manifest_path), package_root, downloader=downloader)
        validation = validate_outcome_package(acquired, package_root, case=contract, settlement_as_of=bound_settlement_as_of)
        if version > 1:
            prior = _last_for_version(events, {"OUTCOME_PACKAGE_READY"}, version - 1)
            prior_ref = str((prior or {}).get("payload", {}).get("package_manifest_ref") or "")
            prior_path = _reference_path(prior_ref)
            if prior_path.is_file() and _selected_source_identity(acquired) == _selected_source_identity(_read_json(prior_path)):
                validation = {
                    "state": "INCOMPLETE",
                    "invalid_findings": [],
                    "incomplete_findings": ["latest_settlement_requires_new_selected_official_source_version"],
                }
        _write_adapter_json(receipt_path, acquired)
    except Exception as exc:
        failure = {
            "schema_version": "judgment-feedback-acquisition-receipt.v1", "state": "BLOCKED",
            "error_type": type(exc).__name__, "detail": str(exc), "settlement_version": version,
            "acquisition_attempt": attempt,
        }
        _write_adapter_json(receipt_path, failure)
        _append_adapter_event(
            conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_BLOCKED", effective_at=settled_as_of,
            actor_id=actor_id, idempotency_key=f"ACQUISITION_BLOCKED:{feedback_item_id}:v{version}:a{attempt}:{manifest_path}",
            artifact_refs=[str(manifest_path), str(receipt_path)],
            payload={
                "settlement_version": version, "acquisition_attempt": attempt,
                "package_manifest_ref": str(receipt_path), "root_cause": "ACQUISITION_MODULE",
            },
        )
        return {"schema_version": SCHEMA_VERSION, "status": "BLOCKED", "feedback_item_id": feedback_item_id, "receipt_ref": str(receipt_path)}
    if validation["state"] != "REVIEWABLE":
        root_cause = _blocked_acquisition_root_cause(acquired, validation)
        _append_adapter_event(
            conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_BLOCKED", effective_at=settled_as_of,
            actor_id=actor_id, idempotency_key=f"ACQUISITION_BLOCKED:{feedback_item_id}:v{version}:a{attempt}:{manifest_path}",
            artifact_refs=[str(manifest_path), str(receipt_path)],
            payload={
                "settlement_version": version, "acquisition_attempt": attempt,
                "package_manifest_ref": str(receipt_path), "root_cause": root_cause,
                "invalid_findings": validation.get("invalid_findings") or [],
                "incomplete_findings": validation.get("incomplete_findings") or [],
            },
        )
        return {"schema_version": SCHEMA_VERSION, "status": "BLOCKED", "feedback_item_id": feedback_item_id, "receipt_ref": str(receipt_path)}
    event_result = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_PACKAGE_READY", effective_at=settled_as_of,
        actor_id=actor_id, idempotency_key=f"OUTCOME_PACKAGE_READY:{feedback_item_id}:v{version}",
        artifact_refs=[str(manifest_path), str(receipt_path)],
        payload={
            "settlement_version": version, "acquisition_attempt": attempt,
            "package_manifest_ref": str(receipt_path), "package_root": str(Path(package_root).resolve()),
            "settlement_as_of": bound_settlement_as_of,
        },
    )
    return {
        "schema_version": SCHEMA_VERSION, "status": "PACKAGE_READY", "feedback_item_id": feedback_item_id,
        "settlement_version": version, "package_manifest_ref": str(receipt_path), "event": event_result,
    }


def record_reader_attestation(
    conn: sqlite3.Connection, *, feedback_item_id: str, package_manifest_ref: str | Path, package_root: str | Path,
    event_root: str | Path, settlement_as_of: str, actor_id: str = "judgment_feedback_control",
) -> dict[str, Any]:
    """Call the reader-aware lower module and append only a successful audit."""
    try:
        from scripts.outcome_acquisition import read_outcome_package
    except ModuleNotFoundError:
        from outcome_acquisition import read_outcome_package
    claim = _claim(conn, feedback_item_id)
    events = _events(conn, feedback_item_id)
    version = _next_settlement_version(claim, events)
    manifest_path = _reference_path(str(package_manifest_ref)).resolve()
    _require_artifact(str(manifest_path), field="package_manifest_ref")
    _, contract = _event_contract(claim)
    bound_settlement_as_of = _required_text({"settlement_as_of": settlement_as_of}, "settlement_as_of")
    settled_as_of = _iso(_parse_time(bound_settlement_as_of, field="settlement_as_of"))
    audit = read_outcome_package(_read_json(manifest_path), package_root, case=contract, settlement_as_of=bound_settlement_as_of)
    audit_path = _adapter_output_path(event_root, feedback_item_id, version, "02_reader_attestation.json")
    _write_adapter_json(audit_path, audit)
    if audit.get("state") != "REVIEWABLE":
        raise ControlPlaneError("reader_attestation_not_reviewable", "; ".join(audit.get("invalid_findings") or audit.get("incomplete_findings") or ["reader audit failed"]))
    event_result = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="READ_ATTESTED", effective_at=settled_as_of,
        actor_id=actor_id, idempotency_key=f"READ_ATTESTED:{feedback_item_id}:v{version}",
        artifact_refs=[str(manifest_path), str(audit_path)],
        payload={
            "settlement_version": version, "package_manifest_ref": str(manifest_path),
            "package_root": str(Path(package_root).resolve()), "read_attestation_ref": str(audit_path),
            "settlement_as_of": bound_settlement_as_of,
        },
    )
    return {"schema_version": SCHEMA_VERSION, "status": "READ_ATTESTED", "read_attestation_ref": str(audit_path), "event": event_result}


def record_outcome_extraction(
    conn: sqlite3.Connection, *, feedback_item_id: str, package_manifest_ref: str | Path, package_root: str | Path,
    read_attestation_ref: str | Path, extraction_ref: str | Path, settlement_as_of: str,
    actor_id: str = "judgment_feedback_control",
) -> dict[str, Any]:
    """Validate a source-bound extraction before making it an outcome event."""
    try:
        from scripts.outcome_acquisition import validate_outcome_extraction
    except ModuleNotFoundError:
        from outcome_acquisition import validate_outcome_extraction
    claim = _claim(conn, feedback_item_id)
    events = _events(conn, feedback_item_id)
    version = _next_settlement_version(claim, events)
    manifest_path = _reference_path(str(package_manifest_ref)).resolve()
    attestation_path = _reference_path(str(read_attestation_ref)).resolve()
    extraction_path = _reference_path(str(extraction_ref)).resolve()
    for field, path in (("package_manifest_ref", manifest_path), ("read_attestation_ref", attestation_path), ("extraction_ref", extraction_path)):
        _require_artifact(str(path), field=field)
    _, contract = _event_contract(claim)
    bound_settlement_as_of = _required_text({"settlement_as_of": settlement_as_of}, "settlement_as_of")
    settled_as_of = _iso(_parse_time(bound_settlement_as_of, field="settlement_as_of"))
    validation = validate_outcome_extraction(
        _read_json(extraction_path), manifest=_read_json(manifest_path), package_root=package_root,
        read_attestation=_read_json(attestation_path), case=contract, settlement_as_of=bound_settlement_as_of,
    )
    if version > 1:
        prior = _last_for_version(events, {"OUTCOME_EXTRACTED"}, version - 1)
        if prior and str(prior["payload"].get("extraction_ref") or "") == str(extraction_path):
            validation = {
                "state": "INCOMPLETE", "invalid_findings": [],
                "incomplete_findings": ["latest_settlement_requires_new_extraction_artifact"],
            }
    if validation["state"] != "REVIEWABLE":
        raise ControlPlaneError("outcome_extraction_not_reviewable", "; ".join(validation.get("invalid_findings") or validation.get("incomplete_findings") or ["extraction failed"]))
    event_result = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_EXTRACTED", effective_at=settled_as_of,
        actor_id=actor_id, idempotency_key=f"OUTCOME_EXTRACTED:{feedback_item_id}:v{version}",
        artifact_refs=[str(manifest_path), str(attestation_path), str(extraction_path)],
        payload={
            "settlement_version": version, "package_manifest_ref": str(manifest_path),
            "package_root": str(Path(package_root).resolve()), "read_attestation_ref": str(attestation_path),
            "extraction_ref": str(extraction_path), "settlement_as_of": bound_settlement_as_of,
        },
    )
    return {"schema_version": SCHEMA_VERSION, "status": "EXTRACTED", "event": event_result}


def record_operating_outcome(
    conn: sqlite3.Connection, *, feedback_item_id: str, package_manifest_ref: str | Path, package_root: str | Path,
    read_attestation_ref: str | Path, extraction_ref: str | Path, settlement_as_of: str, event_root: str | Path,
    actor_id: str = "judgment_feedback_control",
) -> dict[str, Any]:
    """Close a non-directional operating clock without inventing an A/B verdict.

    Decision implementation, cash and capital-boundary clocks are still real
    evidence.  They must complete their package→read→extraction chain, but
    they are not smuggled into selection learning merely because they lack a
    rival-pair threshold.
    """
    try:
        from scripts.outcome_acquisition import validate_outcome_extraction
    except ModuleNotFoundError:
        from outcome_acquisition import validate_outcome_extraction
    claim = _claim(conn, feedback_item_id)
    events = _events(conn, feedback_item_id)
    version = _next_settlement_version(claim, events)
    manifest_path = _reference_path(str(package_manifest_ref)).resolve()
    read_path = _reference_path(str(read_attestation_ref)).resolve()
    extraction_path = _reference_path(str(extraction_ref)).resolve()
    for field, path in (
        ("package_manifest_ref", manifest_path), ("read_attestation_ref", read_path), ("extraction_ref", extraction_path),
    ):
        _require_artifact(str(path), field=field)
    _, contract = _event_contract(claim)
    signal_claim_ids = {
        str(signal.get("claim_id") or "")
        for signal in ((contract.get("mechanism_signal_pair") or {}).get("signals") or [])
        if isinstance(signal, dict)
    }
    if claim["claim_id"] in signal_claim_ids:
        raise ControlPlaneError("operating_outcome_is_signal_claim", "directional signal claims must use run_signal_settlement")
    bound_settlement_as_of = _required_text({"settlement_as_of": settlement_as_of}, "settlement_as_of")
    settled_as_of = _iso(_parse_time(bound_settlement_as_of, field="settlement_as_of"))
    manifest, read, extraction = _read_json(manifest_path), _read_json(read_path), _read_json(extraction_path)
    validation = validate_outcome_extraction(
        extraction, manifest=manifest, package_root=package_root, read_attestation=read,
        case=contract, settlement_as_of=bound_settlement_as_of,
    )
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError(
            "operating_outcome_extraction_not_reviewable",
            "; ".join(validation.get("invalid_findings") or validation.get("incomplete_findings") or ["extraction failed"]),
        )
    observation = next(
        (item for item in extraction.get("observations") or [] if isinstance(item, dict) and item.get("claim_id") == claim["claim_id"]),
        None,
    )
    resolution = next(
        (item for item in extraction.get("non_diagnostic_resolutions") or [] if isinstance(item, dict) and item.get("claim_id") == claim["claim_id"]),
        None,
    )
    if observation is not None and resolution is not None:
        raise ControlPlaneError("operating_outcome_ambiguous", "one operating claim cannot have both observation and non-diagnostic resolution")
    if observation is None and resolution is None:
        raise ControlPlaneError("operating_outcome_claim_missing", "bound extraction does not contain this operating claim")
    status = "OBSERVED" if observation is not None else "NOT_DIAGNOSTIC"
    record = {
        "schema_version": OPERATING_OUTCOME_RECORD_SCHEMA_VERSION,
        "case_id": contract.get("case_id"), "freeze_id": (contract.get("report_freeze") or {}).get("freeze_id"),
        "feedback_item_id": feedback_item_id, "claim_id": claim["claim_id"],
        "settlement_version": version, "settlement_as_of": bound_settlement_as_of,
        "status": status,
        "observation_id": observation.get("observation_id") if observation else None,
        "resolution": resolution.get("resolution") if resolution else None,
        "package_manifest_ref": str(manifest_path), "package_root": str(Path(package_root).resolve()),
        "read_attestation_ref": str(read_path),
        "extraction_ref": str(extraction_path),
    }
    record_path = _adapter_output_path(event_root, feedback_item_id, version, "04_operating_outcome_record.json")
    _write_adapter_json(record_path, record)
    event_result = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type=OPERATING_OUTCOME_RECORDED, effective_at=settled_as_of,
        actor_id=actor_id, idempotency_key=f"OPERATING_OUTCOME_RECORDED:{feedback_item_id}:v{version}",
        artifact_refs=[str(manifest_path), str(read_path), str(extraction_path), str(record_path)],
        payload={
            "settlement_version": version, "operating_outcome_ref": str(record_path),
            "operating_outcome_status": status, "settlement_as_of": bound_settlement_as_of,
        },
    )
    return {
        "schema_version": SCHEMA_VERSION, "status": "OPERATING_OUTCOME_RECORDED",
        "operating_outcome_ref": str(record_path), "event": event_result,
    }


def _execution_path(request: dict[str, Any], *, request_path: Path, field: str, require_file: bool) -> Path:
    """Resolve a declared execution input relative to its explicit request."""
    raw = _required_text(request, field)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = request_path.parent / path
    path = path.resolve()
    if require_file:
        _require_artifact(str(path), field=field)
    return path


def execute_due_claim(
    conn: sqlite3.Connection, *, execution_request_ref: str | Path, actor_id: str = "judgment_feedback_control",
    downloader: Any = None,
) -> dict[str, Any]:
    """Run one due claim through real adapters, using only declared inputs.

    The request holds no verdict and no inferred source query.  It merely
    binds a frozen due item to an already-prepared bounded outcome inventory,
    a destination for raw/reader receipts, and (when available) the manually
    extracted observation and exposure attestation.  Therefore repeated CJO
    runs can advance real work without turning a printed inbox line into an
    ungrounded settlement.
    """
    request_path = _reference_path(str(execution_request_ref)).resolve()
    request = _read_json(request_path)
    if request.get("schema_version") != DUE_EXECUTION_SCHEMA_VERSION:
        raise ControlPlaneError("due_execution_schema_invalid", f"expected {DUE_EXECUTION_SCHEMA_VERSION}")
    feedback_item_id = _required_text(request, "feedback_item_id")
    settlement_as_of = _required_text(request, "settlement_as_of")
    claim = _claim(conn, feedback_item_id)
    if _parse_time(settlement_as_of, field="settlement_as_of") < _parse_time(claim["eligible_at"], field="eligible_at"):
        raise ControlPlaneError("due_execution_before_eligible", "due execution cannot precede the frozen eligible_at")
    state = show(conn, feedback_item_id, as_of=settlement_as_of)["states"]
    if claim["settlement_version_policy"] == "INITIAL_DISCLOSURE" and state["settlement_state"] != "UNSETTLED":
        return {
            "schema_version": SCHEMA_VERSION, "status": "SETTLEMENT_ALREADY_RECORDED",
            "feedback_item_id": feedback_item_id, "states": state,
        }

    manifest_path = _execution_path(request, request_path=request_path, field="outcome_manifest_ref", require_file=True)
    package_root = _execution_path(request, request_path=request_path, field="package_root", require_file=False)
    event_root = _execution_path(request, request_path=request_path, field="event_root", require_file=False)
    acquisition = run_outcome_acquisition(
        conn, feedback_item_id=feedback_item_id, outcome_manifest_ref=manifest_path, package_root=package_root,
        event_root=event_root, settlement_as_of=settlement_as_of, actor_id=actor_id, downloader=downloader,
    )
    if acquisition["status"] == "BLOCKED":
        return {"schema_version": SCHEMA_VERSION, "status": "BLOCKED", "feedback_item_id": feedback_item_id, "acquisition": acquisition}
    package_manifest_ref = acquisition.get("package_manifest_ref")
    if not isinstance(package_manifest_ref, str) or not package_manifest_ref:
        raise ControlPlaneError("due_execution_package_receipt_missing", "successful acquisition did not return a package receipt")
    reader = record_reader_attestation(
        conn, feedback_item_id=feedback_item_id, package_manifest_ref=package_manifest_ref, package_root=package_root,
        event_root=event_root, settlement_as_of=settlement_as_of, actor_id=actor_id,
    )
    if not isinstance(request.get("extraction_ref"), str) or not str(request.get("extraction_ref") or "").strip():
        return {
            "schema_version": SCHEMA_VERSION, "status": "EXTRACTION_INPUT_REQUIRED", "feedback_item_id": feedback_item_id,
            "acquisition": acquisition, "reader": reader,
            "remediation": "read the bounded package and provide a source-bound outcome extraction before settlement",
        }
    extraction_path = _execution_path(request, request_path=request_path, field="extraction_ref", require_file=True)
    extraction = record_outcome_extraction(
        conn, feedback_item_id=feedback_item_id, package_manifest_ref=package_manifest_ref, package_root=package_root,
        read_attestation_ref=reader["read_attestation_ref"], extraction_ref=extraction_path,
        settlement_as_of=settlement_as_of, actor_id=actor_id,
    )
    _, contract = _event_contract(claim)
    signal_claim_ids = {
        str(signal.get("claim_id") or "")
        for signal in ((contract.get("mechanism_signal_pair") or {}).get("signals") or [])
        if isinstance(signal, dict)
    }
    if claim["claim_id"] not in signal_claim_ids:
        completed = record_operating_outcome(
            conn, feedback_item_id=feedback_item_id, package_manifest_ref=package_manifest_ref, package_root=package_root,
            read_attestation_ref=reader["read_attestation_ref"], extraction_ref=extraction_path,
            settlement_as_of=settlement_as_of, event_root=event_root, actor_id=actor_id,
        )
        return {
            "schema_version": SCHEMA_VERSION, "status": "OPERATING_OUTCOME_RECORDED", "feedback_item_id": feedback_item_id,
            "acquisition": acquisition, "reader": reader, "extraction": extraction, "completion": completed,
        }
    if not isinstance(request.get("exposure_attestation_ref"), str) or not str(request.get("exposure_attestation_ref") or "").strip():
        return {
            "schema_version": SCHEMA_VERSION, "status": "EXPOSURE_ATTESTATION_REQUIRED", "feedback_item_id": feedback_item_id,
            "acquisition": acquisition, "reader": reader, "extraction": extraction,
            "remediation": "provide the bounded outcome-exposure attestation before mechanical A/B settlement",
        }
    exposure_path = _execution_path(request, request_path=request_path, field="exposure_attestation_ref", require_file=True)
    settlement_id = str(request.get("settlement_id") or f"{feedback_item_id}:v{_next_settlement_version(claim, _events(conn, feedback_item_id))}")
    settlement = run_signal_settlement(
        conn, feedback_item_id=feedback_item_id, package_manifest_ref=package_manifest_ref, package_root=package_root,
        read_attestation_ref=reader["read_attestation_ref"], exposure_attestation_ref=exposure_path,
        extraction_ref=extraction_path, settlement_id=settlement_id, settlement_as_of=settlement_as_of,
        event_root=event_root, actor_id=actor_id,
    )
    return {
        "schema_version": SCHEMA_VERSION, "status": settlement["status"], "feedback_item_id": feedback_item_id,
        "acquisition": acquisition, "reader": reader, "extraction": extraction, "settlement": settlement,
    }


def run_judgment_feedback(
    *, settlement_ref: str | Path, event_root: str | Path,
) -> dict[str, Any]:
    """Derive and persist feedback from a mechanical signal settlement."""
    try:
        from scripts.live_forward_signal_settlement import build_live_forward_judgment_feedback, event_output_paths
    except ModuleNotFoundError:
        from live_forward_signal_settlement import build_live_forward_judgment_feedback, event_output_paths
    settlement_path = _reference_path(str(settlement_ref)).resolve()
    _require_artifact(str(settlement_path), field="settlement_ref")
    settlement = _read_json(settlement_path)
    feedback = build_live_forward_judgment_feedback(settlement)
    output = event_output_paths(event_root, str(settlement.get("settlement_id") or ""))["feedback"]
    _write_adapter_json(output, feedback)
    return {"schema_version": SCHEMA_VERSION, "status": "FEEDBACK_READY", "feedback_ref": str(output), "feedback": feedback}


def run_signal_settlement(
    conn: sqlite3.Connection, *, feedback_item_id: str, package_manifest_ref: str | Path, package_root: str | Path,
    read_attestation_ref: str | Path, exposure_attestation_ref: str | Path, extraction_ref: str | Path,
    settlement_id: str, settlement_as_of: str, event_root: str | Path,
    actor_id: str = "judgment_feedback_control",
) -> dict[str, Any]:
    """Call mechanical settlement and feedback before appending a claim verdict.

    A control event is therefore evidence of completed lower work, not a
    human-entered label.  Non-signal claims complete through the same bounded
    extraction chain, but are recorded as operating observations rather than
    invented into an A/B verdict.
    """
    try:
        from scripts.live_forward_signal_settlement import event_output_paths, settle_live_forward_signals
    except ModuleNotFoundError:
        from live_forward_signal_settlement import event_output_paths, settle_live_forward_signals
    claim = _claim(conn, feedback_item_id)
    _, dispatch_contract = _event_contract(claim)
    signal_claim_ids = {
        str(signal.get("claim_id") or "")
        for signal in ((dispatch_contract.get("mechanism_signal_pair") or {}).get("signals") or [])
        if isinstance(signal, dict)
    }
    if claim["claim_id"] not in signal_claim_ids:
        return record_operating_outcome(
            conn, feedback_item_id=feedback_item_id, package_manifest_ref=package_manifest_ref, package_root=package_root,
            read_attestation_ref=read_attestation_ref, extraction_ref=extraction_ref,
            settlement_as_of=settlement_as_of, event_root=event_root, actor_id=actor_id,
        )
    events = _events(conn, feedback_item_id)
    version = _next_settlement_version(claim, events)
    manifest_path = _reference_path(str(package_manifest_ref)).resolve()
    read_path = _reference_path(str(read_attestation_ref)).resolve()
    exposure_path = _reference_path(str(exposure_attestation_ref)).resolve()
    extraction_path = _reference_path(str(extraction_ref)).resolve()
    for field, path in (
        ("package_manifest_ref", manifest_path), ("read_attestation_ref", read_path),
        ("exposure_attestation_ref", exposure_path), ("extraction_ref", extraction_path),
    ):
        _require_artifact(str(path), field=field)
    _, contract = _event_contract(claim)
    bound_settlement_as_of = _required_text({"settlement_as_of": settlement_as_of}, "settlement_as_of")
    settled_as_of = _iso(_parse_time(bound_settlement_as_of, field="settlement_as_of"))
    paths = event_output_paths(event_root, settlement_id)
    if paths["settlement"].exists():
        settlement = _read_json(paths["settlement"])
    else:
        settlement = settle_live_forward_signals(
            contract, manifest=_read_json(manifest_path), package_root=package_root,
            read_attestation=_read_json(read_path), exposure_attestation=_read_json(exposure_path),
            extraction=_read_json(extraction_path), settlement_id=settlement_id, settlement_as_of=bound_settlement_as_of,
        )
        _write_adapter_json(paths["settlement"], settlement)
    if settlement.get("state") != "REVIEWABLE":
        raise ControlPlaneError(
            "signal_settlement_not_reviewable",
            "; ".join(settlement.get("invalid_findings") or settlement.get("incomplete_findings") or ["settlement failed"]),
        )
    feedback_result = run_judgment_feedback(settlement_ref=paths["settlement"], event_root=event_root)
    current = next(
        (item for item in settlement.get("claim_settlements") or [] if isinstance(item, dict) and item.get("claim_id") == claim["claim_id"]),
        None,
    )
    if current is None or current.get("status") == "NOT_YET_DUE":
        return {
            "schema_version": SCHEMA_VERSION, "status": "SETTLEMENT_PARTIAL_FOR_OTHER_STAGE",
            "settlement_ref": str(paths["settlement"]), "feedback_ref": feedback_result["feedback_ref"],
        }
    signal_verdict = str(current.get("signal_verdict") or "").upper()
    if signal_verdict not in {"A_ONLY", "B_ONLY", "NOT_DIAGNOSTIC"}:
        raise ControlPlaneError("signal_verdict_unmapped", f"cannot map lower signal verdict: {signal_verdict}")
    if settlement.get("outcome_exposure", {}).get("status") == "OUTCOME_EXPOSURE_BREACH":
        _append_adapter_event(
            conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_EXPOSURE_BREACH", effective_at=settled_as_of,
            actor_id=actor_id, idempotency_key=f"OUTCOME_EXPOSURE_BREACH:{feedback_item_id}:v{version}",
            artifact_refs=[str(exposure_path), str(paths["settlement"])],
            payload={"settlement_version": version, "settlement_ref": str(paths["settlement"])},
        )
    event_type = (
        "MEASUREMENT_MISMATCH"
        if current.get("status") == "NOT_CALCULABLE" and current.get("resolution") == "MEASUREMENT_MISMATCH"
        else "CLAIM_SETTLED"
    )
    payload = {
        "settlement_version": version, "settlement_ref": str(paths["settlement"]),
        "feedback_ref": feedback_result["feedback_ref"], "signal_id": current.get("signal_id"),
    }
    if event_type == "CLAIM_SETTLED":
        payload["settlement_verdict"] = signal_verdict
    else:
        payload["resolution"] = "NOT_DIAGNOSTIC"
    event_result = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type=event_type, effective_at=settled_as_of,
        actor_id=actor_id, idempotency_key=f"{event_type}:{feedback_item_id}:v{version}:{settlement_id}",
        artifact_refs=[str(manifest_path), str(read_path), str(exposure_path), str(extraction_path), str(paths["settlement"]), feedback_result["feedback_ref"]],
        payload=payload,
    )
    return {
        "schema_version": SCHEMA_VERSION, "status": "SETTLED", "settlement_ref": str(paths["settlement"]),
        "feedback_ref": feedback_result["feedback_ref"], "event": event_result,
    }


def run_selection_settlement(
    conn: sqlite3.Connection, *, case_id: str, outcome_ref: str | Path,
    event_root: str | Path, actor_id: str = "judgment_selection_settlement",
) -> dict[str, Any]:
    """Settle one ordered five- or six-claim selection bundle from one custodian outcome.

    The caller supplies no verdict, review, activation or mutable contract.
    Those inputs are reconstructed from immutable rows and registration events
    in this same database before the outcome file is opened.
    """
    context = _selection_control_context(conn, _required_text({"case_id": case_id}, "case_id"))
    outcome_path = _reference_path(str(outcome_ref)).resolve()
    _require_artifact(str(outcome_path), field="outcome_ref")
    outcome = _read_json(outcome_path)
    feedback = _selection_feedback_from_outcome(context, outcome)
    settlement_id = _required_text(outcome, "settlement_id")
    settlement_at = _iso(_parse_time(outcome.get("settlement_as_of"), field="outcome.settlement_as_of"))
    recorded_at = _iso(_now_dt())
    if _parse_time(settlement_at, field="outcome.settlement_as_of") > _parse_time(recorded_at, field="recorded_at"):
        raise ControlPlaneError(
            "selection_settlement_in_future",
            "selection settlement_as_of cannot be later than its real control recording time",
        )
    if any(
        _parse_time(settlement_at, field="outcome.settlement_as_of")
        < _parse_time(claim["eligible_at"], field="eligible_at")
        for claim in context["rows"]
    ):
        raise ControlPlaneError(
            "selection_claim_not_due",
            "one or more frozen selection claims are not eligible at settlement_as_of",
        )
    existing_chains = {
        claim["claim_id"]: [
            event for event in _events(conn, claim["feedback_item_id"])
            if event["event_type"] in OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS
        ]
        for claim in context["rows"]
    }
    if any(existing_chains.values()):
        complete = all(
            len(events) == 5
            and [event["event_type"] for event in events[:4]] == [
                "ACQUISITION_STARTED", "OUTCOME_PACKAGE_READY", "READ_ATTESTED", "OUTCOME_EXTRACTED",
            ]
            and events[-1]["event_type"] in {"CLAIM_SETTLED", "MEASUREMENT_MISMATCH"}
            and events[-1]["payload"].get("settlement_id") == settlement_id
            and events[-1]["payload"].get("outcome_ref") == str(outcome_path)
            and events[-1]["payload"].get("selection_activation_snapshot") == context["activation"]
            for events in existing_chains.values()
        )
        if not complete:
            raise ControlPlaneError(
                "selection_settlement_incomplete_or_conflicting",
                "selection claims contain a partial or different outcome chain and cannot be restarted",
            )
        final_events = [events[-1] for events in existing_chains.values()]
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "SETTLED",
            "case_id": case_id,
            "settlement_id": settlement_id,
            "settlement_ref": str(outcome_path),
            "feedback_ref": final_events[0]["payload"].get("feedback_ref"),
            "activation_id": context["activation"]["activation_id"],
            "events": final_events,
            "idempotent": True,
        }

    safe_settlement_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", settlement_id).strip("_") or "selection"
    output_root = Path(event_root).expanduser().resolve() / "selection_feedback" / safe_settlement_id
    feedback_path = output_root / "feedback.json"
    reader_path = output_root / "reader_attestation.json"
    extraction_path = output_root / "extraction.json"
    reader = _selection_reader_receipt(outcome_path, outcome, context["activation"])
    extraction = _selection_extraction_receipt(outcome_path, outcome, context["activation"])
    _write_immutable_adapter_json(feedback_path, feedback)
    _write_immutable_adapter_json(reader_path, reader)
    _write_immutable_adapter_json(extraction_path, extraction)

    feedback_by_claim = {card["claim_id"]: card for card in feedback["cards"]}
    histories = {
        claim["feedback_item_id"]: _events(conn, claim["feedback_item_id"])
        for claim in context["rows"]
    }
    prepared: list[dict[str, Any]] = []
    event_specs = (
        ("ACQUISITION_STARTED", [str(outcome_path)]),
        ("OUTCOME_PACKAGE_READY", [str(outcome_path)]),
        ("READ_ATTESTED", [str(outcome_path), str(reader_path)]),
        ("OUTCOME_EXTRACTED", [str(outcome_path), str(reader_path), str(extraction_path)]),
    )
    for claim in context["rows"]:
        card = feedback_by_claim[claim["claim_id"]]
        observation_status = card["observation"]["status"]
        final_event_type = "MEASUREMENT_MISMATCH" if observation_status == "MEASUREMENT_MISMATCH" else "CLAIM_SETTLED"
        specs = list(event_specs) + [
            (
                final_event_type,
                [str(outcome_path), str(reader_path), str(extraction_path), str(feedback_path)],
            ),
        ]
        common_payload = {
            "settlement_version": 1,
            "settlement_id": settlement_id,
            "settlement_as_of": settlement_at,
            "outcome_ref": str(outcome_path),
            "selection_activation_snapshot": deepcopy(context["activation"]),
        }
        for sequence, (event_type, artifact_refs) in enumerate(specs, start=1):
            payload = deepcopy(common_payload)
            if event_type == "ACQUISITION_STARTED":
                payload["outcome_manifest_ref"] = str(outcome_path)
            elif event_type == "OUTCOME_PACKAGE_READY":
                payload.update({
                    "package_manifest_ref": str(outcome_path),
                    "package_root": str(outcome_path.parent),
                })
            elif event_type == "READ_ATTESTED":
                payload["read_attestation_ref"] = str(reader_path)
            elif event_type == "OUTCOME_EXTRACTED":
                payload.update({
                    "read_attestation_ref": str(reader_path),
                    "extraction_ref": str(extraction_path),
                })
            else:
                payload.update({
                    "read_attestation_ref": str(reader_path),
                    "extraction_ref": str(extraction_path),
                    "settlement_ref": str(outcome_path),
                    "feedback_ref": str(feedback_path),
                })
                if event_type == "CLAIM_SETTLED":
                    payload["settlement_verdict"] = card["comparison"]["verdict"]
                else:
                    payload["resolution"] = "NOT_DIAGNOSTIC"
            idempotency_key = f"SELECTION:{event_type}:{claim['feedback_item_id']}:{settlement_id}"
            event_id = f"JFE:SELECTION:{sequence:02d}:{claim['feedback_item_id']}:{settlement_id}"
            normalized_refs = [
                _require_artifact(reference, field=f"artifact_refs[{index}]")
                for index, reference in enumerate(artifact_refs)
            ]
            record = {
                "event_id": event_id,
                "feedback_item_id": claim["feedback_item_id"],
                "event_type": event_type,
                "effective_at": settlement_at,
                "recorded_at": recorded_at,
                "actor_role": "AUTOMATION",
                "actor_id": actor_id,
                "idempotency_key": idempotency_key,
                "artifact_refs": normalized_refs,
                "payload": payload,
            }
            if conn.execute(
                "SELECT 1 FROM judgment_feedback_events WHERE idempotency_key = ? OR event_id = ?",
                (idempotency_key, event_id),
            ).fetchone():
                raise ControlPlaneError(
                    "selection_event_identity_conflict",
                    "a selection event identity already exists outside the expected complete chain",
                )
            _validate_adapter_event_receipt(
                conn,
                feedback_item_id=claim["feedback_item_id"],
                event_type=event_type,
                artifact_refs=normalized_refs,
                payload=payload,
            )
            _validate_transition(
                conn, claim, histories[claim["feedback_item_id"]], record,
            )
            histories[claim["feedback_item_id"]].append(record)
            prepared.append(record)
    with conn:
        conn.executemany(
            """INSERT INTO judgment_feedback_events
               (event_id, feedback_item_id, event_type, effective_at, recorded_at,
                actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
               VALUES (:event_id, :feedback_item_id, :event_type, :effective_at, :recorded_at,
                       :actor_role, :actor_id, :idempotency_key, :artifact_refs_json, :payload_json)""",
            [
                {
                    **record,
                    "artifact_refs_json": _json(record["artifact_refs"]),
                    "payload_json": _json(record["payload"]),
                }
                for record in prepared
            ],
        )
    final_events = [event for event in prepared if event["event_type"] in OUTCOME_EVENTS]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SETTLED",
        "case_id": case_id,
        "settlement_id": settlement_id,
        "settlement_ref": str(outcome_path),
        "feedback_ref": str(feedback_path),
        "reader_attestation_ref": str(reader_path),
        "extraction_ref": str(extraction_path),
        "activation_id": context["activation"]["activation_id"],
        "events": final_events,
        "idempotent": False,
    }


def run_boundary_settlement(
    conn: sqlite3.Connection, *, feedback_item_id: str, outcome_ref: str | Path,
    event_root: str | Path, settlement_as_of: str,
    actor_id: str = "judgment_boundary_settlement",
) -> dict[str, Any]:
    """Settle one frozen NO_PRIMARY boundary claim through the five-clock chain."""
    try:
        from scripts.judgment_boundary_feedback import build_boundary_feedback, validate_boundary_outcome
    except ModuleNotFoundError:
        from judgment_boundary_feedback import build_boundary_feedback, validate_boundary_outcome
    claim = _claim(conn, feedback_item_id)
    if claim["learning_eligibility"] != "BOUNDARY_METHOD_ELIGIBLE":
        raise ControlPlaneError("boundary_settlement_identity_invalid", "boundary settlement requires BOUNDARY_METHOD_ELIGIBLE")
    outcome_path = _reference_path(str(outcome_ref)).resolve()
    _require_artifact(str(outcome_path), field="outcome_ref")
    outcome = _read_json(outcome_path)
    validation = validate_boundary_outcome(outcome)
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError("boundary_outcome_not_reviewable", "; ".join(validation.get("findings") or []))
    current = next((item for item in outcome.get("clocks") or [] if item.get("claim_id") == claim["claim_id"]), None)
    if current is None:
        raise ControlPlaneError("boundary_claim_missing", "boundary outcome does not contain this frozen clock claim")
    prior_events = _events(conn, feedback_item_id)
    prior_settlements = _settlement_events(prior_events)
    if prior_settlements:
        latest = prior_settlements[-1]
        prior_settlement_ref = str(latest.get("payload", {}).get("settlement_ref") or "")
        prior_feedback_ref = str(latest.get("payload", {}).get("feedback_ref") or "")
        if prior_settlement_ref and Path(prior_settlement_ref).resolve() != outcome_path:
            raise ControlPlaneError("boundary_settlement_conflict", "existing boundary settlement belongs to a different outcome artifact")
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "SETTLED",
            "feedback_item_id": feedback_item_id,
            "settlement_ref": prior_settlement_ref or str(outcome_path),
            "feedback_ref": prior_feedback_ref,
            "event": latest,
            "idempotent": True,
        }
    if prior_events and any(event["event_type"] in OUTCOME_PIPELINE_EVENTS for event in prior_events):
        raise ControlPlaneError("boundary_settlement_incomplete", "existing boundary outcome chain is incomplete and cannot be restarted")
    _, contract = _event_contract(claim)
    feedback_path = Path(event_root).resolve() / (str(outcome.get("settlement_id") or "boundary") + "_feedback.json")
    feedback = build_boundary_feedback(outcome)
    _write_adapter_json(feedback_path, feedback)
    reader_path = Path(event_root).resolve() / (str(outcome.get("settlement_id") or "boundary") + "_reader.json")
    extraction_path = Path(event_root).resolve() / (str(outcome.get("settlement_id") or "boundary") + "_extraction.json")
    reader = {"schema_version": "judgment-boundary-reader-attestation.v1", "outcome_ref": str(outcome_path), "state": "REVIEWABLE"}
    extraction = {"schema_version": "judgment-boundary-extraction.v1", "outcome_ref": str(outcome_path), "claim_id": claim["claim_id"], "status": current.get("status"), "state": "REVIEWABLE"}
    _write_adapter_json(reader_path, reader)
    _write_adapter_json(extraction_path, extraction)
    event_root_path = Path(event_root).resolve()
    event_root_path.mkdir(parents=True, exist_ok=True)
    artifacts = [str(outcome_path), str(feedback_path), str(claim["source_contract_ref"]), str(claim["measurement_contract_ref"])]
    at = _iso(_parse_time(settlement_as_of, field="settlement_as_of"))
    version = _next_settlement_version(claim, _events(conn, feedback_item_id))
    common = {"settlement_version": version, "settlement_as_of": at}
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_STARTED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"BOUNDARY:ACQUISITION_STARTED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts, payload={**common, "outcome_manifest_ref": str(outcome_path)},
    )
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_PACKAGE_READY", effective_at=at,
        actor_id=actor_id, idempotency_key=f"BOUNDARY:OUTCOME_PACKAGE_READY:{feedback_item_id}:v{version}",
        artifact_refs=artifacts, payload={**common, "package_manifest_ref": str(outcome_path), "package_root": str(outcome_path.parent)},
    )
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="READ_ATTESTED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"BOUNDARY:READ_ATTESTED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts + [str(reader_path)], payload={**common, "package_manifest_ref": str(outcome_path), "read_attestation_ref": str(reader_path), "package_root": str(outcome_path.parent)},
    )
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_EXTRACTED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"BOUNDARY:OUTCOME_EXTRACTED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts + [str(reader_path), str(extraction_path)], payload={**common, "package_manifest_ref": str(outcome_path), "read_attestation_ref": str(reader_path), "extraction_ref": str(extraction_path), "package_root": str(outcome_path.parent)},
    )
    event = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="CLAIM_SETTLED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"BOUNDARY:CLAIM_SETTLED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts + [str(reader_path), str(extraction_path)], payload={**common, "settlement_ref": str(outcome_path), "feedback_ref": str(feedback_path), "settlement_verdict": "NOT_DIAGNOSTIC"},
    )
    return {"schema_version": SCHEMA_VERSION, "status": "SETTLED", "feedback_item_id": feedback_item_id, "settlement_ref": str(outcome_path), "feedback_ref": str(feedback_path), "event": event}


def record_holdout_exposure_breach(
    conn: sqlite3.Connection, *, feedback_item_id: str, breach_ref: str | Path,
    actor_id: str = "judgment_holdout_exposure_audit",
) -> dict[str, Any]:
    """Record a discovered holdout leak without granting evaluation or learning rights."""
    claim = _claim(conn, feedback_item_id)
    if claim["program_lane"] != "HISTORICAL_HOLDOUT" or claim["learning_eligibility"] != "EVALUATION_ONLY":
        raise ControlPlaneError(
            "holdout_breach_identity_invalid",
            "record-holdout-exposure-breach requires HISTORICAL_HOLDOUT and EVALUATION_ONLY",
        )
    path = _reference_path(str(breach_ref)).resolve()
    _require_artifact(str(path), field="breach_ref")
    now = _now_dt()
    validated = _validate_holdout_exposure_breach_artifact(path, claim=claim, now=now)
    receipt = validated["receipt"]
    event = _append_adapter_event(
        conn,
        feedback_item_id=feedback_item_id,
        event_type="OUTCOME_EXPOSURE_BREACH",
        effective_at=_iso(validated["discovered_at"]),
        recorded_at=_iso(now),
        actor_id=actor_id,
        idempotency_key=f"HOLDOUT_EXPOSURE_BREACH:{claim['episode_id']}:{receipt.get('breach_id')}",
        artifact_refs=[str(path)],
        payload={
            "breach_ref": str(path),
            "breach_id": receipt.get("breach_id"),
            "case_id": receipt.get("case_id"),
            "first_outcome_accessed_at": _iso(validated["first_outcome_accessed_at"]),
            "discovered_at": _iso(validated["discovered_at"]),
            "root_cause": receipt.get("root_cause"),
            "disposition": receipt.get("disposition"),
            "breach_snapshot": deepcopy(receipt),
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "EXPOSURE_BREACH",
        "case_id": claim["episode_id"],
        "feedback_item_id": feedback_item_id,
        "breach_ref": str(path),
        "event": event,
    }


def run_holdout_settlement(
    conn: sqlite3.Connection, *, feedback_item_id: str, outcome_ref: str | Path,
    event_root: str | Path, settlement_as_of: str,
    actor_id: str = "judgment_holdout_settlement", program_id: str | None = None,
) -> dict[str, Any]:
    """Settle one post-freeze EVALUATION_ONLY D1-D5 holdout claim."""
    try:
        from scripts.judgment_boundary_feedback import validate_boundary_outcome
    except ModuleNotFoundError:
        from judgment_boundary_feedback import validate_boundary_outcome
    claim = _claim(conn, feedback_item_id)
    recorded_dt = _now_dt()
    at_dt = _parse_time(settlement_as_of, field="settlement_as_of")
    if at_dt > recorded_dt:
        raise ControlPlaneError(
            "holdout_settlement_effective_after_recorded",
            "holdout settlement effective time cannot be later than its real recorded time",
        )
    context = _require_frozen_holdout_program(
        conn, claim, effective_at=at_dt, program_id=program_id,
    )
    pre_review = _holdout_pre_reveal_context(claim)
    claims_by_clock = _holdout_claim_bundle(conn, claim)
    if any(
        event["event_type"] == "OUTCOME_EXPOSURE_BREACH"
        for item in claims_by_clock.values()
        for event in _events(conn, item["feedback_item_id"])
    ):
        raise ControlPlaneError(
            "holdout_outcome_blocked_by_exposure_breach",
            "an exposure-breached holdout can never resume evaluation settlement",
        )
    clock = _holdout_clock_id(claim)
    outcome_path = _reference_path(str(outcome_ref)).resolve()
    _require_artifact(str(outcome_path), field="outcome_ref")
    outcome = _read_json(outcome_path)
    validation = validate_boundary_outcome(outcome)
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError("holdout_outcome_not_reviewable", "; ".join(validation.get("findings") or []))
    if _parse_time(outcome.get("settlement_as_of"), field="outcome.settlement_as_of") != at_dt:
        raise ControlPlaneError("holdout_settlement_time_mismatch", "settlement_as_of must equal the holdout outcome receipt")
    first_accessed_at = _parse_time(
        outcome.get("first_outcome_accessed_at"),
        field="outcome.first_outcome_accessed_at",
    )
    prerequisites = {
        "method_frozen_at": _parse_time(context["method_frozen_at"], field="method_frozen_at"),
        "method_freeze_recorded_at": _parse_time(
            context["method_freeze_recorded_at"], field="method_freeze_recorded_at",
        ),
        "pre_reveal_reviewed_at": pre_review["reviewed_at"],
        "claim_registered_at": _parse_time(claim["registered_at"], field="claim.registered_at"),
    }
    late_prerequisites = sorted(
        name for name, value in prerequisites.items() if value > first_accessed_at
    )
    if late_prerequisites:
        raise ControlPlaneError(
            "holdout_outcome_access_precedes_prerequisites",
            "first outcome access predates: " + ", ".join(late_prerequisites),
        )
    if first_accessed_at > at_dt or at_dt > recorded_dt:
        raise ControlPlaneError(
            "holdout_outcome_time_order_invalid",
            "required order is first outcome access <= settlement effective <= settlement recorded",
        )
    if outcome.get("case_id") != claim["episode_id"]:
        raise ControlPlaneError("holdout_outcome_case_mismatch", "holdout outcome belongs to another episode")
    if outcome.get("freeze_id") != context["training_episode_id"]:
        raise ControlPlaneError(
            "holdout_outcome_episode_mismatch",
            "holdout outcome freeze_id must equal the registered training_episode_id",
        )
    outcome_by_clock = {
        str(item.get("clock") or ""): item
        for item in outcome.get("clocks") or []
        if isinstance(item, dict)
    }
    if any(
        outcome_by_clock.get(expected_clock, {}).get("claim_id") != expected_claim["claim_id"]
        for expected_clock, expected_claim in claims_by_clock.items()
    ):
        raise ControlPlaneError("holdout_outcome_claim_mismatch", "holdout outcome must bind the registered D1-D5 claim set")
    current = outcome_by_clock[clock]
    prior_events = _events(conn, feedback_item_id)
    prior_settlements = _settlement_events(prior_events)
    if prior_settlements:
        latest = prior_settlements[-1]
        prior_settlement_ref = str(latest.get("payload", {}).get("settlement_ref") or "")
        if prior_settlement_ref and _reference_path(prior_settlement_ref).resolve() != outcome_path:
            raise ControlPlaneError("holdout_settlement_conflict", "existing holdout settlement belongs to a different outcome artifact")
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "SETTLED",
            "feedback_item_id": feedback_item_id,
            "clock": clock,
            "settlement_ref": prior_settlement_ref or str(outcome_path),
            "event": latest,
            "idempotent": True,
        }
    if any(event["event_type"] in OUTCOME_PIPELINE_EVENTS for event in prior_events):
        raise ControlPlaneError(
            "holdout_settlement_incomplete",
            "existing holdout outcome chain is incomplete and cannot be restarted",
        )

    event_root_path = Path(event_root).expanduser().resolve()
    stem = f"{str(outcome.get('settlement_id') or 'holdout')}_{clock.lower()}"
    evaluation_path = event_root_path / f"{stem}_evaluation.json"
    reader_path = event_root_path / f"{stem}_reader.json"
    extraction_path = event_root_path / f"{stem}_extraction.json"
    observation = {
        "schema_version": "judgment-holdout-claim-observation.v1",
        "program_id": context["program_id"],
        "training_episode_id": context["training_episode_id"],
        "case_id": claim["episode_id"],
        "method_version": context["method_version"],
        "method_frozen_at": context["method_frozen_at"],
        "method_freeze_recorded_at": context["method_freeze_recorded_at"],
        "pre_reveal_contract_ref": claim["frozen_artifact_ref"],
        "pre_reveal_review_receipt_ref": pre_review["path"],
        "first_outcome_accessed_at": _iso(first_accessed_at),
        "clock": clock,
        "feedback_item_id": feedback_item_id,
        "claim_id": claim["claim_id"],
        "stage_id": claim["stage_id"],
        "settlement_id": outcome.get("settlement_id"),
        "settlement_as_of": _iso(at_dt),
        "observation": deepcopy(current),
        "learning_eligibility": "EVALUATION_ONLY",
        "prohibited_outputs": ["diagnosis", "learning_note", "learning_application", "method_change"],
    }
    reader = {
        "schema_version": "judgment-holdout-reader-attestation.v1",
        "outcome_ref": str(outcome_path),
        "clock": clock,
        "state": "REVIEWABLE",
    }
    extraction = {
        "schema_version": "judgment-holdout-extraction.v1",
        "outcome_ref": str(outcome_path),
        "feedback_item_id": feedback_item_id,
        "claim_id": claim["claim_id"],
        "clock": clock,
        "status": current.get("status"),
        "state": "REVIEWABLE",
    }
    _write_adapter_json(evaluation_path, observation)
    _write_adapter_json(reader_path, reader)
    _write_adapter_json(extraction_path, extraction)
    artifacts = [
        str(outcome_path), str(evaluation_path), str(claim["source_contract_ref"]),
        str(claim["measurement_contract_ref"]), pre_review["path"],
    ]
    at = _iso(at_dt)
    version = _next_settlement_version(claim, prior_events)
    common = {
        "program_id": context["program_id"],
        "settlement_version": version,
        "settlement_as_of": at,
        "holdout_clock": clock,
        "method_version": context["method_version"],
        "method_frozen_at": context["method_frozen_at"],
        "method_freeze_recorded_at": context["method_freeze_recorded_at"],
        "training_episode_id": context["training_episode_id"],
        "pre_reveal_review_receipt_ref": pre_review["path"],
        "first_outcome_accessed_at": _iso(first_accessed_at),
    }
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_STARTED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"HOLDOUT:ACQUISITION_STARTED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts, payload={**common, "outcome_manifest_ref": str(outcome_path)},
        recorded_at=_iso(recorded_dt),
    )
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_PACKAGE_READY", effective_at=at,
        actor_id=actor_id, idempotency_key=f"HOLDOUT:OUTCOME_PACKAGE_READY:{feedback_item_id}:v{version}",
        artifact_refs=artifacts, payload={**common, "package_manifest_ref": str(outcome_path), "package_root": str(outcome_path.parent)},
        recorded_at=_iso(recorded_dt),
    )
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="READ_ATTESTED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"HOLDOUT:READ_ATTESTED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts + [str(reader_path)],
        payload={**common, "package_manifest_ref": str(outcome_path), "read_attestation_ref": str(reader_path), "package_root": str(outcome_path.parent)},
        recorded_at=_iso(recorded_dt),
    )
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_EXTRACTED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"HOLDOUT:OUTCOME_EXTRACTED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts + [str(reader_path), str(extraction_path)],
        payload={**common, "package_manifest_ref": str(outcome_path), "read_attestation_ref": str(reader_path), "extraction_ref": str(extraction_path), "package_root": str(outcome_path.parent)},
        recorded_at=_iso(recorded_dt),
    )
    event = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="CLAIM_SETTLED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"HOLDOUT:CLAIM_SETTLED:{feedback_item_id}:v{version}",
        artifact_refs=artifacts + [str(reader_path), str(extraction_path)],
        payload={
            **common,
            "settlement_ref": str(outcome_path),
            "feedback_ref": str(evaluation_path),
            "settlement_verdict": "NOT_DIAGNOSTIC",
            "observed_status": current.get("status"),
        },
        recorded_at=_iso(recorded_dt),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SETTLED",
        "program_id": context["program_id"],
        "feedback_item_id": feedback_item_id,
        "clock": clock,
        "settlement_ref": str(outcome_path),
        "evaluation_ref": str(evaluation_path),
        "event": event,
        "idempotent": False,
    }


def accept_holdout_evaluation_receipt(
    conn: sqlite3.Connection, *, receipt_ref: str | Path, accepted_at: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Accept one independent receipt over the current D1-D5 holdout settlements."""
    receipt_path = _reference_path(str(receipt_ref)).resolve()
    _require_artifact(str(receipt_path), field="receipt_ref")
    receipt = _read_json(receipt_path)
    if receipt.get("schema_version") != HOLDOUT_EVALUATION_RECEIPT_SCHEMA_VERSION:
        raise ControlPlaneError("holdout_receipt_schema_invalid", "unsupported holdout evaluation receipt schema")
    program_id = _required_text(receipt, "program_id")
    case_id = _required_text(receipt, "case_id")
    anchor_row = conn.execute(
        """SELECT claim.*
             FROM judgment_feedback_claims AS claim
            WHERE claim.episode_id = ?
              AND claim.program_lane = 'HISTORICAL_HOLDOUT'
              AND claim.learning_eligibility = 'EVALUATION_ONLY'
            ORDER BY claim.stage_id""",
        (case_id,),
    ).fetchall()
    if not anchor_row:
        raise ControlPlaneError("holdout_receipt_episode_unknown", "evaluation receipt does not resolve to a registered holdout episode")
    claims_by_clock = _holdout_claim_bundle(conn, dict(anchor_row[0]))
    anchor = claims_by_clock["D5"]
    accepted_dt = _parse_time(accepted_at, field="accepted_at")
    context = _require_frozen_holdout_program(
        conn, anchor, effective_at=accepted_dt, program_id=program_id,
    )
    if context["program_id"] != program_id:
        raise ControlPlaneError("holdout_receipt_program_mismatch", "evaluation receipt belongs to another training program")
    settlements = _holdout_settlements(conn, anchor, effective_at=accepted_dt)
    payload = {
        "receipt_schema_version": receipt.get("schema_version"),
        "receipt_id": receipt.get("receipt_id"),
        "receipt_ref": str(receipt_path),
        "program_id": receipt.get("program_id"),
        "training_episode_id": receipt.get("training_episode_id"),
        "case_id": receipt.get("case_id"),
        "method_version": receipt.get("method_version"),
        "method_frozen_at": receipt.get("method_frozen_at"),
        "evaluated_at": receipt.get("evaluated_at"),
        "evaluation_verdict": receipt.get("evaluation_verdict"),
        "evaluation_author_id": receipt.get("evaluation_author_id"),
        "reviewer_id": receipt.get("reviewer_id"),
        "reviewer_acceptance": receipt.get("reviewer_acceptance"),
        "claim_settlements": deepcopy(receipt.get("claim_settlements")),
        "receipt_snapshot": deepcopy(receipt),
    }
    artifact_refs = [str(receipt_path)]
    for _, settlement in settlements.values():
        artifact_refs.extend(str(reference) for reference in settlement.get("artifact_refs") or [])
    artifact_refs = list(dict.fromkeys(artifact_refs))
    reviewer = _required_text(receipt, "reviewer_id")
    event = _append_adapter_event(
        conn,
        feedback_item_id=anchor["feedback_item_id"],
        event_type="HOLDOUT_EVALUATION_ACCEPTED",
        effective_at=_iso(accepted_dt),
        actor_id=actor_id or reviewer,
        idempotency_key=f"HOLDOUT_EVALUATION_ACCEPTED:{context['program_id']}:{case_id}:{receipt.get('receipt_id')}",
        artifact_refs=artifact_refs,
        payload=payload,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "EVALUATED_HOLDOUT",
        "program_id": context["program_id"],
        "training_episode_id": context["training_episode_id"],
        "case_id": case_id,
        "receipt_ref": str(receipt_path),
        "event": event,
    }


def record_learning_note(
    conn: sqlite3.Connection, *, feedback_item_id: str, feedback_ref: str | Path, learning_note_ref: str | Path,
    diagnosis_payload: dict[str, Any], effective_at: str, actor_id: str = "judgment_feedback_control",
    diagnosis_event_id: str | None = None,
) -> dict[str, Any]:
    """Validate a lower learning note before recording its accepted diagnosis link."""
    try:
        from scripts.judgment_learning import validate_judgment_learning_note
    except ModuleNotFoundError:
        from judgment_learning import validate_judgment_learning_note
    claim = _claim(conn, feedback_item_id)
    feedback_path = _reference_path(str(feedback_ref)).resolve()
    note_path = _reference_path(str(learning_note_ref)).resolve()
    _require_artifact(str(feedback_path), field="feedback_ref")
    _require_artifact(str(note_path), field="learning_note_ref")
    note = _read_json(note_path)
    feedback = _read_json(feedback_path)
    validation = validate_judgment_learning_note(note, feedback)
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError("learning_note_not_reviewable", "; ".join(validation.get("findings") or []))
    if _reference_path(str(note.get("feedback_ref") or "")).resolve() != feedback_path:
        raise ControlPlaneError(
            "learning_note_feedback_ref_mismatch",
            "learning note feedback_ref must resolve to the validated feedback artifact",
        )
    if str(note.get("case_id") or "") != str(claim.get("episode_id") or ""):
        raise ControlPlaneError("learning_note_case_mismatch", "learning note case_id must match the control-plane episode")
    if str(note.get("claim_id") or "") != str(claim.get("claim_id") or ""):
        raise ControlPlaneError("learning_note_claim_mismatch", "learning note claim_id must match the control-plane claim")
    at = _iso(_parse_time(effective_at, field="effective_at"))
    joint_verdict = (
        str((feedback.get("joint_comparison") or {}).get("overall_verdict") or "").upper()
        if isinstance(feedback.get("joint_comparison"), dict) else ""
    )
    mixed_selection_boundary = bool(
        claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE"
        and joint_verdict == "MIXED"
    )
    if mixed_selection_boundary and note.get("disposition") != "INSUFFICIENT_EVIDENCE":
        raise ControlPlaneError(
            "mixed_selection_boundary_note_invalid",
            "mixed selection feedback permits only an INSUFFICIENT_EVIDENCE mechanism-boundary note",
        )
    events = _events(conn, feedback_item_id)
    settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, _parse_time(at, field="effective_at"))
    if not settlement:
        raise ControlPlaneError("settlement_required", "learning note requires a completed settlement")
    if not _same_artifact_reference(settlement["payload"].get("feedback_ref"), feedback_path):
        raise ControlPlaneError(
            "learning_note_settlement_feedback_mismatch",
            "learning note feedback must be the feedback artifact emitted by the active settlement",
        )
    if diagnosis_event_id:
        diagnosis_event = _event_by_id(events, diagnosis_event_id)
        if (
            not diagnosis_event
            or diagnosis_event.get("event_type") != "DIAGNOSIS_ACCEPTED"
            or diagnosis_event.get("payload", {}).get("settlement_event_id") != settlement["event_id"]
        ):
            raise ControlPlaneError(
                "diagnosis_event_invalid",
                "diagnosis_event_id must resolve to the accepted diagnosis of the active settlement",
            )
    else:
        diagnosis_event = _append_adapter_event(
            conn, feedback_item_id=feedback_item_id, event_type="DIAGNOSIS_ACCEPTED", effective_at=at,
            actor_id=actor_id, idempotency_key=f"DIAGNOSIS_ACCEPTED:{feedback_item_id}:{settlement['event_id']}",
            artifact_refs=[str(feedback_path), str(note_path)],
            payload={
                "settlement_event_id": settlement["event_id"],
                **diagnosis_payload,
                **({"diagnosis_scope": MIXED_SELECTION_BOUNDARY_SCOPE} if mixed_selection_boundary else {}),
            },
        )
    measurement_selection_boundary = bool(
        claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE"
        and joint_verdict == "NOT_DIAGNOSTIC"
    )
    learning_scope = (
        MIXED_SELECTION_BOUNDARY_SCOPE
        if mixed_selection_boundary
        else "MEASUREMENT_BOUNDARY"
        if measurement_selection_boundary
        else "SELECTION_METHOD"
        if claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE"
        else "BOUNDARY_OR_ABSTENTION"
    )
    note_event = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="LEARNING_NOTE_READY", effective_at=at,
        actor_id=actor_id, idempotency_key=f"LEARNING_NOTE_READY:{feedback_item_id}:{diagnosis_event['event_id']}",
        artifact_refs=[str(feedback_path), str(note_path)],
        payload={
            "diagnosis_event_id": diagnosis_event["event_id"],
            "learning_note_ref": str(note_path),
            "learning_note_id": note.get("note_id"),
            "feedback_ref": str(feedback_path),
            "case_id": note.get("case_id"),
            "claim_id": note.get("claim_id"),
            "settlement_id": note.get("settlement_id"),
            "learning_scope": learning_scope,
            **(
                {
                    "permitted_change_targets": [
                        "CANDIDATE_OBSERVABILITY_GATE", "SOURCE_GATE",
                    ],
                    "prohibited_rights": [
                        "DIRECTIONAL_SELECTION_LEARNING", "METHOD_APPLICATION",
                        "METHOD_FREEZE", "HOLDOUT_RELEASE", "REPORT_USE",
                    ],
                }
                if measurement_selection_boundary else {}
            ),
            **(
                {
                    "permitted_change_targets": [],
                    "prohibited_rights": list(SELECTION_BOUNDARY_PROHIBITED_RIGHTS),
                }
                if mixed_selection_boundary else {}
            ),
            # The event is append-only; exact structural snapshots prevent a
            # later rewrite at the same path from changing what was admitted.
            "learning_note_snapshot": deepcopy(note),
            "feedback_snapshot": deepcopy(feedback),
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "MIXED_MECHANISM_BOUNDARY_NOTE_READY" if mixed_selection_boundary
            else "MEASUREMENT_BOUNDARY_NOTE_READY" if measurement_selection_boundary
            else "LEARNING_NOTE_READY"
        ),
        "event": note_event,
        "claim": claim,
    }


def record_learning_application(
    conn: sqlite3.Connection, *, feedback_item_id: str, application_receipt_ref: str | Path,
    note_refs: list[str | Path], method_review_ref: str | Path, target_freeze_ref: str | Path,
    target_frozen_at: str, effective_at: str, actor_id: str = "judgment_feedback_control",
) -> dict[str, Any]:
    """Validate a lower application receipt, then link its real frozen change."""
    try:
        from scripts.judgment_learning import validate_learning_application_receipt
    except ModuleNotFoundError:
        from judgment_learning import validate_learning_application_receipt
    claim = _claim(conn, feedback_item_id)
    receipt_path = _reference_path(str(application_receipt_ref)).resolve()
    review_path = _reference_path(str(method_review_ref)).resolve()
    target_path = _reference_path(str(target_freeze_ref)).resolve()
    for field, path in (("application_receipt_ref", receipt_path), ("method_review_ref", review_path), ("target_freeze_ref", target_path)):
        _require_artifact(str(path), field=field)
    resolved_notes = [_reference_path(str(reference)).resolve() for reference in note_refs]
    for index, path in enumerate(resolved_notes):
        _require_artifact(str(path), field=f"note_refs[{index}]")
    receipt, notes, review, target = _read_json(receipt_path), [_read_json(path) for path in resolved_notes], _read_json(review_path), _read_json(target_path)
    validation = validate_learning_application_receipt(receipt, notes=notes, method_review=review, target_freeze=target)
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError("learning_application_not_reviewable", "; ".join(validation.get("findings") or []))
    events = _events(conn, feedback_item_id)
    note_event = _last(events, {"LEARNING_NOTE_READY"})
    if not note_event:
        raise ControlPlaneError("learning_note_required", "application receipt requires a recorded learning note")
    current_note = _read_json(_reference_path(str(note_event["payload"].get("learning_note_ref") or "")))
    source_note_ids = {str(value) for value in receipt.get("source_note_ids") or []}
    if str(current_note.get("note_id") or "") not in source_note_ids:
        raise ControlPlaneError("application_receipt_note_mismatch", "application receipt does not apply this control item's learning note")
    applied = next(
        (item for item in receipt.get("applications") or [] if isinstance(item, dict) and item.get("note_id") == current_note.get("note_id") and item.get("disposition") == "APPLIED"),
        None,
    )
    changes = applied.get("frozen_field_changes") if isinstance(applied, dict) else []
    if not isinstance(changes, list) or not changes:
        raise ControlPlaneError("application_receipt_no_applied_change", "current note must have an APPLIED frozen-field change")
    change = changes[0]
    target_meta = receipt.get("target") if isinstance(receipt.get("target"), dict) else {}
    reviewer = receipt.get("independent_reviewer") if isinstance(receipt.get("independent_reviewer"), dict) else {}
    at = _iso(_parse_time(effective_at, field="effective_at"))
    event_result = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="LEARNING_APPLIED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"LEARNING_APPLIED:{feedback_item_id}:{receipt.get('receipt_id')}",
        artifact_refs=[str(receipt_path), str(review_path), str(target_path), *[str(path) for path in resolved_notes]],
        payload={
            "learning_note_event_id": note_event["event_id"], "application_scope": "METHOD_TRANSFER",
            "application_basis": receipt.get("application_basis"),
            "replication_requirement": receipt.get("replication_requirement"),
            "production_rights": receipt.get("production_rights"),
            "learning_scope": "SELECTION_METHOD" if claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE" else "BOUNDARY_OR_ABSTENTION",
            "target_episode_id": target_meta.get("experiment_id"),
            "target_company_id": target_meta.get("company_id") or target_meta.get("company_cluster_id"),
            "target_company_cluster_id": target_meta.get("company_cluster_id"),
            "target_frozen_artifact_ref": str(target_path), "target_frozen_at": target_frozen_at,
            "target_freeze_id": target_meta.get("freeze_id"),
            "target_program_id": target_meta.get("program_id"),
            "target_training_episode_id": target_meta.get("training_episode_id"),
            "target_case_id": target_meta.get("case_id"),
            "target_candidate_ref": target_meta.get("candidate_ref"),
            "target_selection_review_ref": target_meta.get("selection_review_ref"),
            "target_selection_admission_version": target_meta.get("selection_admission_version"),
            "changed_field_ref": change.get("json_pointer"), "before_method_meaning": str(change.get("prior_rule") or ""),
            "after_method_meaning": json.dumps(change.get("new_frozen_value"), ensure_ascii=False, sort_keys=True),
            "change_reason": (applied or {}).get("scope_rationale"),
            "reviewer_id": reviewer.get("reviewer_id"), "target_author_id": receipt.get("prepared_by"),
            "reviewer_acceptance": "ACCEPTED",
        },
    )
    return {"schema_version": SCHEMA_VERSION, "status": "LEARNING_APPLIED", "event": event_result}


def run_method_evaluation(*, note_refs: list[str | Path], output_ref: str | Path) -> dict[str, Any]:
    """Build the existing cross-company agenda; it never returns a win rate."""
    try:
        from scripts.judgment_learning import build_method_feedback_review
    except ModuleNotFoundError:
        from judgment_learning import build_method_feedback_review
    notes = []
    for index, reference in enumerate(note_refs):
        path = _reference_path(str(reference)).resolve()
        _require_artifact(str(path), field=f"note_refs[{index}]")
        notes.append(_read_json(path))
    review = build_method_feedback_review(notes)
    output = _reference_path(str(output_ref)).resolve()
    _write_adapter_json(output, review)
    return {"schema_version": SCHEMA_VERSION, "status": review.get("state"), "method_review_ref": str(output)}


def _resolve_manifest_artifact_refs(manifest: dict[str, Any], directory: Path) -> dict[str, Any]:
    """Resolve explicit local artifact references relative to the experiment only."""
    resolved = deepcopy(manifest)
    def resolve_item(item: dict[str, Any]) -> None:
        for field in (
            "frozen_artifact_ref", "source_contract_ref", "measurement_contract_ref",
            "training_program_ref", "pre_reveal_review_receipt_ref",
            "selection_resolution_ref", "selection_resolution_review_ref",
        ):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            raw_path, separator, pointer = value.partition("#")
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = directory / path
            item[field] = f"{path.resolve()}{separator}{pointer}" if separator else str(path.resolve())
    resolve_item(resolved)
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


def _command_register_live_forward(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return register_live_forward_contract(
            conn,
            contract_path=args.contract,
            frozen_artifact_ref=args.frozen_artifact,
            registered_at=args.registered_at,
        )
    finally:
        conn.close()


def _command_sync_live_forward(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return sync_live_forward_contracts(
            conn,
            contract_root=args.contract_root,
            registered_at=args.registered_at,
        )
    finally:
        conn.close()


def _command_sync_candidate_conditions(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return sync_candidate_condition_contracts(
            conn,
            contract_root=args.contract_root,
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


def _command_reconcile_candidate_conditions(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return reconcile_candidate_conditions(conn, as_of=args.as_of)
    finally:
        conn.close()


def _command_append(args: argparse.Namespace) -> dict[str, Any]:
    event = _read_json(Path(args.input))
    event_type = str(event.get("event_type") or "").upper()
    if event_type in OUTCOME_PIPELINE_EVENTS | OUTCOME_EVENTS | {"OUTCOME_EXPOSURE_BREACH"}:
        raise ControlPlaneError(
            "outcome_event_adapter_only",
            "outcome pipeline events must be emitted by their lower-module adapter, not append-event",
        )
    conn = connect(args.db)
    try:
        initialize(conn)
        return append_event(conn, event, recorded_at=args.recorded_at)
    finally:
        conn.close()


def _command_show(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return show(conn, args.feedback_item_id, as_of=args.as_of)
    finally:
        conn.close()


def _command_execute_due(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return execute_due_claim(conn, execution_request_ref=args.request, actor_id=args.actor_id)
    finally:
        conn.close()


def _command_settle_boundary(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return run_boundary_settlement(
            conn, feedback_item_id=args.feedback_item_id, outcome_ref=args.outcome,
            event_root=args.event_root, settlement_as_of=args.settlement_as_of,
        )
    finally:
        conn.close()


def _command_settle_selection(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return run_selection_settlement(
            conn,
            case_id=args.case_id,
            outcome_ref=args.outcome,
            event_root=args.event_root,
            actor_id=args.actor_id,
        )
    finally:
        conn.close()


def _command_settle_holdout(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return run_holdout_settlement(
            conn, feedback_item_id=args.feedback_item_id, outcome_ref=args.outcome,
            event_root=args.event_root, settlement_as_of=args.settlement_as_of,
            actor_id=args.actor_id, program_id=args.program_id,
        )
    finally:
        conn.close()


def _command_accept_holdout_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return accept_holdout_evaluation_receipt(
            conn, receipt_ref=args.receipt, accepted_at=args.accepted_at,
            actor_id=args.actor_id,
        )
    finally:
        conn.close()


def _command_record_holdout_exposure_breach(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return record_holdout_exposure_breach(
            conn,
            feedback_item_id=args.feedback_item_id,
            breach_ref=args.breach,
            actor_id=args.actor_id,
        )
    finally:
        conn.close()


def _command_append_holdout_admin_correction(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return append_holdout_admin_correction(
            conn, correction_ref=args.correction, recorded_at=args.recorded_at,
        )
    finally:
        conn.close()


def _command_review_holdout_admin_correction(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return review_holdout_admin_correction(
            conn, review_ref=args.review, recorded_at=args.recorded_at,
        )
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
    live = sub.add_parser("register-live-forward-contract", help="project one reviewed forward contract into the feedback inbox")
    live.add_argument("--db", required=True)
    live.add_argument("--contract", required=True)
    live.add_argument("--frozen-artifact")
    live.add_argument("--registered-at")
    live.set_defaults(handler=_command_register_live_forward)
    sync = sub.add_parser("sync-live-forward-contracts", help="register all reviewed forward contracts below an experiments root")
    sync.add_argument("--db", required=True)
    sync.add_argument("--contract-root", required=True)
    sync.add_argument("--registered-at")
    sync.set_defaults(handler=_command_sync_live_forward)
    candidate_sync = sub.add_parser(
        "sync-candidate-condition-contracts",
        help="register pending candidate conditions without creating feedback claims",
    )
    candidate_sync.add_argument("--db", required=True)
    candidate_sync.add_argument("--contract-root", required=True)
    candidate_sync.add_argument("--registered-at")
    candidate_sync.set_defaults(handler=_command_sync_candidate_conditions)
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
    candidate_inbox = sub.add_parser(
        "candidate-condition-inbox",
        help="derive pending candidate-condition reminders without executing an outcome path",
    )
    candidate_inbox.add_argument("--db", required=True)
    candidate_inbox.add_argument("--as-of", required=True)
    candidate_inbox.set_defaults(handler=_command_reconcile_candidate_conditions)
    append = sub.add_parser("append-event", help="append a reviewed non-outcome control event")
    append.add_argument("--db", required=True)
    append.add_argument("--input", required=True)
    append.add_argument("--recorded-at")
    append.set_defaults(handler=_command_append)
    show_cmd = sub.add_parser("show", help="show one item and its derived state")
    show_cmd.add_argument("--db", required=True)
    show_cmd.add_argument("--feedback-item-id", required=True)
    show_cmd.add_argument("--as-of")
    show_cmd.set_defaults(handler=_command_show)
    execute = sub.add_parser("execute-due", help="run one declared due claim through its real lower-module adapters")
    execute.add_argument("--db", required=True)
    execute.add_argument("--request", required=True)
    execute.add_argument("--actor-id", default="judgment_feedback_control")
    execute.set_defaults(handler=_command_execute_due)
    boundary = sub.add_parser("settle-boundary", help="settle one NO_PRIMARY boundary claim through the D1-D5 receipt chain")
    boundary.add_argument("--db", required=True)
    boundary.add_argument("--feedback-item-id", required=True)
    boundary.add_argument("--outcome", required=True)
    boundary.add_argument("--event-root", required=True)
    boundary.add_argument("--settlement-as-of", required=True)
    boundary.set_defaults(handler=_command_settle_boundary)
    selection_settlement = sub.add_parser(
        "settle-selection",
        help="settle one five- or six-claim selection episode from a custodian outcome",
    )
    selection_settlement.add_argument("--db", required=True)
    selection_settlement.add_argument("--case-id", required=True)
    selection_settlement.add_argument("--outcome", required=True)
    selection_settlement.add_argument("--event-root", required=True)
    selection_settlement.add_argument("--actor-id", default="judgment_selection_settlement")
    selection_settlement.set_defaults(handler=_command_settle_selection)
    holdout = sub.add_parser("settle-holdout", help="settle one post-freeze EVALUATION_ONLY D1-D5 holdout claim")
    holdout.add_argument("--db", required=True)
    holdout.add_argument("--feedback-item-id", required=True)
    holdout.add_argument("--outcome", required=True)
    holdout.add_argument("--event-root", required=True)
    holdout.add_argument("--settlement-as-of", required=True)
    holdout.add_argument(
        "--program-id",
        help="target successor program when the holdout is linked into a later program",
    )
    holdout.add_argument("--actor-id", default="judgment_holdout_settlement")
    holdout.set_defaults(handler=_command_settle_holdout)
    holdout_receipt = sub.add_parser(
        "accept-holdout-evaluation",
        help="accept an independent receipt over all five current holdout settlements",
    )
    holdout_receipt.add_argument("--db", required=True)
    holdout_receipt.add_argument("--receipt", required=True)
    holdout_receipt.add_argument("--accepted-at", required=True)
    holdout_receipt.add_argument("--actor-id")
    holdout_receipt.set_defaults(handler=_command_accept_holdout_evaluation)
    admin_correction = sub.add_parser(
        "append-holdout-admin-correction",
        help="append an R-103 post-freeze administrative prerequisite correction without mutating the sealed core",
    )
    admin_correction.add_argument("--db", required=True)
    admin_correction.add_argument("--correction", required=True)
    admin_correction.add_argument("--recorded-at")
    admin_correction.set_defaults(handler=_command_append_holdout_admin_correction)
    admin_review = sub.add_parser(
        "review-holdout-admin-correction",
        help="append an independent review of the latest R-103 administrative correction",
    )
    admin_review.add_argument("--db", required=True)
    admin_review.add_argument("--review", required=True)
    admin_review.add_argument("--recorded-at")
    admin_review.set_defaults(handler=_command_review_holdout_admin_correction)
    breach = sub.add_parser(
        "record-holdout-exposure-breach",
        help="record a real discovered holdout timing or outcome-access breach",
    )
    breach.add_argument("--db", required=True)
    breach.add_argument("--feedback-item-id", required=True)
    breach.add_argument("--breach", required=True)
    breach.add_argument("--actor-id", default="judgment_holdout_exposure_audit")
    breach.set_defaults(handler=_command_record_holdout_exposure_breach)
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
