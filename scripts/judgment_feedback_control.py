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
EPISODE_CLASSES = {"JUDGMENT_SELECTION_EPISODE", "MECHANISM_SIGNAL_PROBE", "PIPELINE_REHEARSAL"}
SELECTION_STATUSES = {"SELECTION_ADMITTED", "NO_PRIMARY"}
LEARNING_ELIGIBILITIES = {"SELECTION_METHOD_ELIGIBLE", "MECHANISM_SETTLEMENT_ONLY"}
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
OUTCOME_PIPELINE_EVENTS = {
    "ACQUISITION_STARTED", "ACQUISITION_BLOCKED", "OUTCOME_PACKAGE_READY", "READ_ATTESTED", "OUTCOME_EXTRACTED",
}


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
          episode_class TEXT NOT NULL DEFAULT 'PIPELINE_REHEARSAL',
          selection_status TEXT NOT NULL DEFAULT 'NO_PRIMARY',
          learning_eligibility TEXT NOT NULL DEFAULT 'MECHANISM_SETTLEMENT_ONLY',
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
    ):
        if name not in existing_columns:
            conn.execute(f"ALTER TABLE judgment_feedback_claims ADD COLUMN {name} {definition}")
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
    episode_class = str(item.get("episode_class") or manifest.get("episode_class") or "PIPELINE_REHEARSAL").upper()
    selection_status = str(item.get("selection_status") or manifest.get("selection_status") or "NO_PRIMARY").upper()
    learning_eligibility = str(
        item.get("learning_eligibility") or manifest.get("learning_eligibility") or "MECHANISM_SETTLEMENT_ONLY"
    ).upper()
    if episode_class not in EPISODE_CLASSES:
        raise ControlPlaneError("episode_class_invalid", f"unsupported episode_class: {episode_class}")
    if selection_status not in SELECTION_STATUSES:
        raise ControlPlaneError("selection_status_invalid", f"unsupported selection_status: {selection_status}")
    if learning_eligibility not in LEARNING_ELIGIBILITIES:
        raise ControlPlaneError("learning_eligibility_invalid", f"unsupported learning_eligibility: {learning_eligibility}")
    if selection_status == "SELECTION_ADMITTED":
        if episode_class != "JUDGMENT_SELECTION_EPISODE" or learning_eligibility != "SELECTION_METHOD_ELIGIBLE":
            raise ControlPlaneError(
                "selection_episode_metadata_inconsistent",
                "SELECTION_ADMITTED requires JUDGMENT_SELECTION_EPISODE and SELECTION_METHOD_ELIGIBLE",
            )
    elif learning_eligibility != "MECHANISM_SETTLEMENT_ONLY":
        raise ControlPlaneError(
            "no_primary_learning_not_permitted",
            "NO_PRIMARY episodes may settle mechanisms but cannot enter selection or method learning",
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
        "frozen_artifact_ref": _require_artifact(_required_text(item, "frozen_artifact_ref"), field="frozen_artifact_ref"),
        "source_contract_ref": _require_artifact(_required_text(item, "source_contract_ref"), field="source_contract_ref"),
        "measurement_contract_ref": _require_artifact(_required_text(item, "measurement_contract_ref"), field="measurement_contract_ref"),
        "episode_class": episode_class,
        "selection_status": selection_status,
        "learning_eligibility": learning_eligibility,
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
        })
    return {
        "schema_version": REGISTRATION_SCHEMA_VERSION,
        "episode_id": episode_id,
        "company_id": company_id,
        "frozen_at": frozen_at,
        "episode_class": episode_class,
        "selection_status": selection_status,
        "learning_eligibility": learning_eligibility,
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
    if event_type in {"ACQUISITION_STARTED", "ACQUISITION_BLOCKED", "OUTCOME_PACKAGE_READY", "READ_ATTESTED", "OUTCOME_EXTRACTED", "CLAIM_SETTLED", "MEASUREMENT_MISMATCH"} and effective_at < eligible_at:
        raise ControlPlaneError("outcome_before_eligible", f"{event_type} cannot be recorded before eligible_at")
    if _event_exists(events, "CLOSED"):
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
    if event_type == "DIAGNOSIS_ACCEPTED":
        settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, effective_at)
        if not settlement:
            raise ControlPlaneError("settlement_required", "DIAGNOSIS_ACCEPTED requires a settlement")
        if payload.get("settlement_event_id") != settlement["event_id"]:
            raise ControlPlaneError("diagnosis_settlement_link_invalid", "diagnosis must bind the latest settlement event")
        _validate_diagnosis(payload)
    if event_type == "LEARNING_NOTE_READY":
        if claim["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE":
            raise ControlPlaneError("learning_not_permitted_for_episode", "mechanism-only episodes cannot create a method learning note")
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
        if claim["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE":
            raise ControlPlaneError("learning_not_permitted_for_episode", "mechanism-only episodes cannot apply selection or method learning")
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
        if claim["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE":
            raise ControlPlaneError("learning_not_permitted_for_episode", "mechanism-only episodes cannot close a method replication")
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
        if not target or target["event_type"] not in OUTCOME_EVENTS:
            raise ControlPlaneError("replication_settlement_unknown", "replication_settlement_event_id must resolve to a real settled target claim")
        if target["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE":
            raise ControlPlaneError("replication_target_not_selection_eligible", "replication target must be a selection-eligible episode")
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
    _validate_transition(conn, claim, events, record)
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
    elif claim["learning_eligibility"] != "SELECTION_METHOD_ELIGIBLE":
        learning_state = "NONE"
    elif latest_application:
        learning_state = "REPLICATION_PENDING"
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
    if claim["learning_eligibility"] == "MECHANISM_SETTLEMENT_ONLY" and states["settlement_state"] != "UNSETTLED":
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


def _event_contract(claim: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = _reference_path(claim["source_contract_ref"]).resolve()
    _require_artifact(str(path), field="source_contract_ref")
    return path, _read_json(path)


def _next_settlement_version(claim: dict[str, Any], events: list[dict[str, Any]]) -> int:
    return len(_settlement_events(events)) + 1


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


def _append_adapter_event(
    conn: sqlite3.Connection, *, feedback_item_id: str, event_type: str, effective_at: str,
    actor_id: str, idempotency_key: str, artifact_refs: list[str], payload: dict[str, Any],
) -> dict[str, Any]:
    return append_event(conn, {
        "feedback_item_id": feedback_item_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "actor_role": "AUTOMATION",
        "actor_id": actor_id,
        "idempotency_key": idempotency_key,
        "artifact_refs": artifact_refs,
        "payload": payload,
    })


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
    start_payload = {"settlement_version": version, "outcome_manifest_ref": str(manifest_path), "package_root": str(Path(package_root).resolve())}
    if previous_block:
        start_payload["retry_of_event_id"] = previous_block["event_id"]
    _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_STARTED", effective_at=settled_as_of,
        actor_id=actor_id,
        idempotency_key=(
            f"ACQUISITION_STARTED:{feedback_item_id}:v{version}:{manifest_path}"
            + (f":retry:{previous_block['event_id']}" if previous_block else "")
        ),
        artifact_refs=[str(manifest_path)],
        payload=start_payload,
    )
    receipt_path = _adapter_output_path(event_root, feedback_item_id, version, "01_outcome_package_manifest.json")
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
        }
        _write_adapter_json(receipt_path, failure)
        _append_adapter_event(
            conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_BLOCKED", effective_at=settled_as_of,
            actor_id=actor_id, idempotency_key=f"ACQUISITION_BLOCKED:{feedback_item_id}:v{version}:{manifest_path}",
            artifact_refs=[str(manifest_path), str(receipt_path)],
            payload={"settlement_version": version, "package_manifest_ref": str(receipt_path), "root_cause": "ACQUISITION_MODULE"},
        )
        return {"schema_version": SCHEMA_VERSION, "status": "BLOCKED", "feedback_item_id": feedback_item_id, "receipt_ref": str(receipt_path)}
    if validation["state"] != "REVIEWABLE":
        _append_adapter_event(
            conn, feedback_item_id=feedback_item_id, event_type="ACQUISITION_BLOCKED", effective_at=settled_as_of,
            actor_id=actor_id, idempotency_key=f"ACQUISITION_BLOCKED:{feedback_item_id}:v{version}:{manifest_path}",
            artifact_refs=[str(manifest_path), str(receipt_path)],
            payload={
                "settlement_version": version, "package_manifest_ref": str(receipt_path), "root_cause": "ACQUISITION_MODULE",
                "invalid_findings": validation.get("invalid_findings") or [],
                "incomplete_findings": validation.get("incomplete_findings") or [],
            },
        )
        return {"schema_version": SCHEMA_VERSION, "status": "BLOCKED", "feedback_item_id": feedback_item_id, "receipt_ref": str(receipt_path)}
    event_result = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="OUTCOME_PACKAGE_READY", effective_at=settled_as_of,
        actor_id=actor_id, idempotency_key=f"OUTCOME_PACKAGE_READY:{feedback_item_id}:v{version}",
        artifact_refs=[str(manifest_path), str(receipt_path)],
        payload={"settlement_version": version, "package_manifest_ref": str(receipt_path), "package_root": str(Path(package_root).resolve())},
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
        payload={"settlement_version": version, "package_manifest_ref": str(manifest_path), "read_attestation_ref": str(audit_path)},
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
            "read_attestation_ref": str(attestation_path), "extraction_ref": str(extraction_path),
        },
    )
    return {"schema_version": SCHEMA_VERSION, "status": "EXTRACTED", "event": event_result}


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
    human-entered label.  Non-signal claims remain extracted rather than being
    invented into an A/B verdict.
    """
    try:
        from scripts.live_forward_signal_settlement import event_output_paths, settle_live_forward_signals
    except ModuleNotFoundError:
        from live_forward_signal_settlement import event_output_paths, settle_live_forward_signals
    claim = _claim(conn, feedback_item_id)
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


def record_learning_note(
    conn: sqlite3.Connection, *, feedback_item_id: str, feedback_ref: str | Path, learning_note_ref: str | Path,
    diagnosis_payload: dict[str, Any], effective_at: str, actor_id: str = "judgment_feedback_control",
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
    validation = validate_judgment_learning_note(_read_json(note_path), _read_json(feedback_path))
    if validation.get("state") != "REVIEWABLE":
        raise ControlPlaneError("learning_note_not_reviewable", "; ".join(validation.get("findings") or []))
    at = _iso(_parse_time(effective_at, field="effective_at"))
    events = _events(conn, feedback_item_id)
    settlement = _last_effective_no_later_than(events, OUTCOME_EVENTS, _parse_time(at, field="effective_at"))
    if not settlement:
        raise ControlPlaneError("settlement_required", "learning note requires a completed settlement")
    diagnosis_event = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="DIAGNOSIS_ACCEPTED", effective_at=at,
        actor_id=actor_id, idempotency_key=f"DIAGNOSIS_ACCEPTED:{feedback_item_id}:{settlement['event_id']}",
        artifact_refs=[str(feedback_path), str(note_path)],
        payload={"settlement_event_id": settlement["event_id"], **diagnosis_payload},
    )
    note_event = _append_adapter_event(
        conn, feedback_item_id=feedback_item_id, event_type="LEARNING_NOTE_READY", effective_at=at,
        actor_id=actor_id, idempotency_key=f"LEARNING_NOTE_READY:{feedback_item_id}:{diagnosis_event['event_id']}",
        artifact_refs=[str(feedback_path), str(note_path)],
        payload={"diagnosis_event_id": diagnosis_event["event_id"], "learning_note_ref": str(note_path)},
    )
    return {"schema_version": SCHEMA_VERSION, "status": "LEARNING_NOTE_READY", "event": note_event, "claim": claim}


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
            "target_episode_id": target_meta.get("experiment_id"), "target_company_id": target_meta.get("company_cluster_id"),
            "target_frozen_artifact_ref": str(target_path), "target_frozen_at": target_frozen_at,
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


def _command_reconcile(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.db)
    try:
        initialize(conn)
        return reconcile(conn, as_of=args.as_of, due_soon_days=args.due_soon_days)
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
