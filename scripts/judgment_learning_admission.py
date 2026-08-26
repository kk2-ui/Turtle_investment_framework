#!/usr/bin/env python3
"""Select control-plane learning that is safe to expose to a report agenda."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any


SELECTION_SCHEMA_VERSION = "judgment-learning-admission-selection.v1"
ADMISSION_SCHEMA_VERSION = "judgment-learning-admission.v1"
_METHOD_ELIGIBILITIES = {
    "SELECTION_METHOD_ELIGIBLE",
    "BOUNDARY_METHOD_ELIGIBLE",
}
_PROHIBITED_LANES = {"HISTORICAL_HOLDOUT", "HISTORICAL_TEACHING"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _instant(value: Any, *, allow_date: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if allow_date and len(text) == 10:
        try:
            day = datetime.fromisoformat(text).date()
        except ValueError:
            return None
        return datetime.combine(
            day,
            time(23, 59, 59),
            tzinfo=timezone(timedelta(hours=8)),
        ).astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _contract_cutoff(contract: dict[str, Any]) -> str:
    pit = contract.get("pit_production") if isinstance(contract.get("pit_production"), dict) else {}
    return str(
        pit.get("cutoff_at")
        or contract.get("cutoff_at")
        or contract.get("pit_cutoff_at")
        or contract.get("data_as_of")
        or contract.get("analysis_date")
        or ""
    ).strip()


def default_control_plane_db() -> Path:
    configured = str(os.environ.get("TURTLE_JUDGMENT_CONTROL_DB") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(__file__).resolve().parents[1] / "stock_analysis.db").resolve()


def _json_column(value: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return None


def _artifact_bundle(references: Any) -> tuple[
    dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]
]:
    receipt: dict[str, Any] = {}
    notes: list[dict[str, Any]] = []
    review: dict[str, Any] = {}
    target: dict[str, Any] = {}
    for raw in references if isinstance(references, list) else []:
        path = Path(str(raw or "")).expanduser()
        if not path.is_file():
            continue
        value = _read_json(path.resolve())
        schema = str(value.get("schema_version") or "")
        if schema == "judgment-learning-application-receipt.v1":
            receipt = value
        elif schema == "judgment-learning-note.v2":
            notes.append(value)
        elif schema == "method-feedback-review.v1":
            review = value
        elif value.get("freeze_id") or isinstance(value.get("report_freeze"), dict):
            target = value
    return receipt, notes, review, target


def _application_is_reviewable(
    event: dict[str, Any], *, note_id: str, source_company_cluster_id: str,
) -> tuple[bool, str]:
    try:
        from scripts.judgment_learning import validate_learning_application_receipt
    except ModuleNotFoundError:
        from judgment_learning import validate_learning_application_receipt

    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if str(payload.get("application_scope") or "").upper() != "METHOD_TRANSFER":
        return False, "application_not_method_transfer"
    if str(payload.get("reviewer_acceptance") or "").upper() != "ACCEPTED":
        return False, "application_reviewer_not_accepted"
    reviewer = str(payload.get("reviewer_id") or "").strip()
    author = str(payload.get("target_author_id") or "").strip()
    source_episode = str(event.get("episode_id") or "").strip()
    target_episode = str(payload.get("target_episode_id") or "").strip()
    target_company = str(payload.get("target_company_id") or "").strip()
    if not reviewer or not author or reviewer == author:
        return False, "application_reviewer_not_independent"
    if not target_episode or target_episode == source_episode:
        return False, "application_not_cross_episode"
    if not target_company or target_company == source_company_cluster_id:
        return False, "application_not_cross_company"
    effective = _instant(event.get("effective_at"))
    recorded = _instant(event.get("recorded_at"))
    target_frozen = _instant(payload.get("target_frozen_at"))
    if (
        effective is None or recorded is None or target_frozen is None
        or target_frozen > effective or target_frozen > recorded
    ):
        return False, "application_target_temporal_order_invalid"

    receipt, notes, review, target = _artifact_bundle(event.get("artifact_refs"))
    if not receipt or not notes or not review or not target:
        return False, "application_artifact_bundle_incomplete"
    validation = validate_learning_application_receipt(
        receipt, notes=notes, method_review=review, target_freeze=target,
    )
    if validation.get("state") != "REVIEWABLE":
        return False, "application_receipt_not_reviewable"
    applied = next(
        (
            item for item in receipt.get("applications") or []
            if isinstance(item, dict)
            and str(item.get("note_id") or "") == note_id
            and item.get("disposition") == "APPLIED"
        ),
        None,
    )
    if not applied:
        return False, "learning_note_not_applied"
    receipt_review = receipt.get("independent_reviewer")
    if not isinstance(receipt_review, dict) or (
        receipt_review.get("verdict") != "CONFIRMED_FIELD_CHANGE"
        or str(receipt_review.get("reviewer_id") or "") != reviewer
    ):
        return False, "application_receipt_reviewer_mismatch"
    return True, ""


def _released_method_context(
    conn: sqlite3.Connection, application: dict[str, Any], *, cutoff: datetime,
) -> tuple[dict[str, Any] | None, str]:
    """Resolve the explicit post-holdout release backing one application."""
    program_ref = str(application.get("training_program_ref") or "").strip()
    if not program_ref:
        return None, "training_program_ref_missing"
    try:
        row = conn.execute(
            """SELECT program.program_id, program.program_state, program.method_version,
                      program.method_scope, program.method_frozen_at,
                      release.release_id, release.released_at, release.recorded_at,
                      release.release_decision, release.receipt_json
                 FROM judgment_training_programs AS program
                 JOIN judgment_training_method_releases AS release USING (program_id)
                WHERE program.contract_ref = ?""",
            (str(Path(program_ref).expanduser().resolve()),),
        ).fetchone()
    except sqlite3.Error:
        return None, "method_release_missing"
    if not row:
        return None, "method_release_missing"
    release = dict(row)
    if release.get("program_state") != "ACTIVE":
        return None, "released_program_not_active"
    if release.get("release_decision") != "METHOD_RELEASED_FOR_REPORT_USE":
        return None, "method_not_released_for_report_use"
    frozen = _instant(release.get("method_frozen_at"))
    released = _instant(release.get("released_at"))
    recorded = _instant(release.get("recorded_at"))
    if (
        frozen is None or released is None or recorded is None
        or frozen > released or released > recorded
    ):
        return None, "method_release_temporal_order_invalid"
    if released > cutoff or recorded > cutoff:
        return None, "method_release_after_information_cutoff"
    receipt = _json_column(release.get("receipt_json"))
    if not isinstance(receipt, dict):
        return None, "method_release_receipt_invalid"
    expected = {
        "release_id": release["release_id"],
        "program_id": release["program_id"],
        "method_version": release["method_version"],
        "method_scope": release["method_scope"],
        "release_decision": release["release_decision"],
    }
    if receipt.get("schema_version") != "judgment-method-report-release.v1" or any(
        receipt.get(field) != value for field, value in expected.items()
    ):
        return None, "method_release_receipt_identity_mismatch"
    if (
        _instant(receipt.get("method_frozen_at")) != frozen
        or _instant(receipt.get("released_at")) != released
    ):
        return None, "method_release_receipt_identity_mismatch"
    return {
        "program_id": release["program_id"],
        "method_version": release["method_version"],
        "method_scope": release["method_scope"],
        "method_release_id": release["release_id"],
        "method_released_at": release["released_at"],
    }, ""


def select_judgment_learning_admissions(
    control_plane_db: str | Path,
    *,
    information_cutoff: str,
) -> dict[str, Any]:
    """Return existing admission objects backed by an accepted application."""
    database = Path(control_plane_db).expanduser().resolve()
    cutoff = _instant(information_cutoff, allow_date=True)
    if cutoff is None:
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "state": "INVALID_CUTOFF",
            "information_cutoff": str(information_cutoff or ""),
            "selected_count": 0,
            "excluded_counts": {"information_cutoff_invalid": 1},
            "admissions": [],
        }
    if not database.is_file():
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "state": "CONTROL_PLANE_UNAVAILABLE",
            "information_cutoff": str(information_cutoff),
            "selected_count": 0,
            "excluded_counts": {"control_plane_db_missing": 1},
            "admissions": [],
        }

    try:
        conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT event.*, claim.episode_id, claim.claim_id, claim.company_id,
                      claim.program_lane, claim.learning_eligibility,
                      claim.training_program_ref
                 FROM judgment_feedback_events AS event
                 JOIN judgment_feedback_claims AS claim USING (feedback_item_id)
                WHERE event.event_type = 'LEARNING_APPLIED'
                ORDER BY event.recorded_at, event.effective_at, event.event_id"""
        ).fetchall()
    except sqlite3.Error:
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "state": "CONTROL_PLANE_UNAVAILABLE",
            "information_cutoff": str(information_cutoff),
            "selected_count": 0,
            "excluded_counts": {"control_plane_schema_unavailable": 1},
            "admissions": [],
        }

    try:
        from scripts.judgment_feedback_control import read_learning_note_ready_event
        from scripts.judgment_learning import validate_judgment_learning_admission
    except ModuleNotFoundError:
        from judgment_feedback_control import read_learning_note_ready_event
        from judgment_learning import validate_judgment_learning_admission

    exclusions: Counter[str] = Counter()
    selected_by_note: dict[str, tuple[datetime, dict[str, Any]]] = {}
    try:
        for row in rows:
            application = dict(row)
            lane = str(application.get("program_lane") or "").upper()
            eligibility = str(application.get("learning_eligibility") or "").upper()
            if lane in _PROHIBITED_LANES:
                exclusions["prohibited_program_lane"] += 1
                continue
            if eligibility not in _METHOD_ELIGIBILITIES:
                exclusions["learning_scope_not_method_eligible"] += 1
                continue
            effective = _instant(application.get("effective_at"))
            recorded = _instant(application.get("recorded_at"))
            if effective is None or recorded is None or effective > recorded:
                exclusions["application_temporal_order_invalid"] += 1
                continue
            if effective > cutoff or recorded > cutoff:
                exclusions["application_after_information_cutoff"] += 1
                continue
            method_release, method_release_finding = _released_method_context(
                conn, application, cutoff=cutoff,
            )
            if method_release is None:
                exclusions[method_release_finding] += 1
                continue
            application["artifact_refs"] = _json_column(
                application.pop("artifact_refs_json", "[]")
            )
            application["payload"] = _json_column(
                application.pop("payload_json", "{}")
            )
            payload = application["payload"] if isinstance(application["payload"], dict) else {}
            note_event_id = str(payload.get("learning_note_event_id") or "").strip()
            if not note_event_id:
                exclusions["learning_note_event_missing"] += 1
                continue
            note_row = conn.execute(
                """SELECT * FROM judgment_feedback_events
                    WHERE feedback_item_id = ? AND event_id = ?
                      AND event_type = 'LEARNING_NOTE_READY'""",
                (application["feedback_item_id"], note_event_id),
            ).fetchone()
            if not note_row:
                exclusions["learning_note_event_missing"] += 1
                continue
            note_event = dict(note_row)
            note_effective = _instant(note_event.get("effective_at"))
            note_recorded = _instant(note_event.get("recorded_at"))
            if note_effective is None or note_recorded is None or note_effective > note_recorded:
                exclusions["learning_note_event_temporal_order_invalid"] += 1
                continue
            note_payload = _json_column(note_event.get("payload_json"))
            if not isinstance(note_payload, dict):
                exclusions["learning_note_event_payload_invalid"] += 1
                continue
            if note_effective > effective or note_recorded > recorded:
                exclusions["learning_application_lineage_temporal_order_invalid"] += 1
                continue
            note_ref = Path(str(note_payload.get("learning_note_ref") or "")).expanduser().resolve()
            feedback_ref = Path(str(note_payload.get("feedback_ref") or "")).expanduser().resolve()
            note = _read_json(note_ref)
            feedback = _read_json(feedback_ref)
            note_id = str(note.get("note_id") or "").strip()
            if not note_id or not note or not feedback:
                exclusions["learning_artifact_missing"] += 1
                continue
            source_cluster = str(note.get("company_cluster_id") or application.get("company_id") or "")
            application_ok, application_finding = _application_is_reviewable(
                application, note_id=note_id,
                source_company_cluster_id=source_cluster,
            )
            if not application_ok:
                exclusions[application_finding] += 1
                continue
            admission = {
                "schema_version": ADMISSION_SCHEMA_VERSION,
                "learning_note_ref": str(note_ref),
                "feedback_ref": str(feedback_ref),
                "control_plane_db": str(database),
                "feedback_item_id": str(application.get("feedback_item_id") or ""),
                "learning_note_event_id": note_event_id,
                "learning_note_effective_at": str(note_event.get("effective_at") or ""),
                "application_event_id": str(application.get("event_id") or ""),
                **method_release,
            }
            control_event = read_learning_note_ready_event(
                database,
                feedback_item_id=admission["feedback_item_id"],
                event_id=note_event_id,
                information_cutoff=information_cutoff,
            )
            validation = validate_judgment_learning_admission(
                admission,
                note=note,
                feedback=feedback,
                control_event=control_event,
                information_cutoff=information_cutoff,
            )
            if validation.get("state") != "REVIEWABLE":
                exclusions["formal_admission_not_reviewable"] += 1
                continue
            prior = selected_by_note.get(note_id)
            if prior is None or recorded > prior[0]:
                selected_by_note[note_id] = (recorded, admission)
    finally:
        conn.close()

    admissions = [
        deepcopy(value[1])
        for _, value in sorted(selected_by_note.items(), key=lambda item: item[0])
    ]
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "state": "READY" if admissions else "NO_ELIGIBLE_LEARNING",
        "information_cutoff": str(information_cutoff),
        "selected_count": len(admissions),
        "excluded_counts": dict(sorted(exclusions.items())),
        "admissions": admissions,
    }


def refresh_analysis_contract_learning_admissions(
    output_dir: str | Path,
    *,
    control_plane_db: str | Path | None = None,
) -> dict[str, Any]:
    """Refresh report-local admission pointers without copying learning content."""
    output = Path(output_dir).expanduser().resolve()
    contract_path = output / "analysis_contract.json"
    contract = _read_json(contract_path)
    if not contract:
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "state": "ANALYSIS_CONTRACT_UNAVAILABLE",
            "selected_count": 0,
            "excluded_counts": {"analysis_contract_missing_or_invalid": 1},
            "admissions": [],
            "written": False,
        }
    cutoff = _contract_cutoff(contract)
    database = Path(control_plane_db).expanduser().resolve() if control_plane_db else default_control_plane_db()
    selection = select_judgment_learning_admissions(
        database,
        information_cutoff=cutoff,
    )
    status = {
        key: deepcopy(selection[key])
        for key in (
            "schema_version", "state", "information_cutoff", "selected_count",
            "excluded_counts",
        )
    }
    next_contract = deepcopy(contract)
    next_contract["judgment_learning_admissions"] = deepcopy(selection["admissions"])
    next_contract["judgment_learning_admission_status"] = status
    written = next_contract != contract
    if written:
        contract_path.write_text(
            json.dumps(next_contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {**selection, "written": written, "contract_ref": str(contract_path)}
