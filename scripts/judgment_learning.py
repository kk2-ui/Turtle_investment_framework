#!/usr/bin/env python3
"""Record an append-only learning action from an immutable feedback card.

Settlement tells us what the frozen forward judgment observed.  It must not
rewrite that judgment.  This module records the smaller, prospective question
that follows: should this signal be retained, retired, or treated as
insufficient evidence next time, and what concrete research design changes?
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-learning-note.v2"
ADMISSION_SCHEMA_VERSION = "judgment-learning-admission.v1"
APPLICATION_RECEIPT_SCHEMA_VERSION = "judgment-learning-application-receipt.v1"
DISPOSITIONS = {"RETAIN", "RETIRE", "INSUFFICIENT_EVIDENCE"}
ROOT_CAUSE_CLASSES = {
    "DATA_COVERAGE", "ACQUISITION_MODULE", "REASONING", "MODEL", "WRITING",
}
# These are research-design locations: where the investigation failed to
# represent, acquire, or reason about the company.  They are deliberately
# separate from ``ECONOMIC_FAILURE_LOCI`` below.  A bad customer response is
# not an evidence-acquisition failure, and a bad measurement contract is not
# itself a claim that the enterprise mechanism was wrong.
ANALYSIS_FAILURE_LOCI = {
    "STATE_REPRESENTATION", "MECHANISM", "EVIDENCE_ACQUISITION",
    "FINANCIAL_TRANSMISSION", "VALUATION_DECISION",
}
ECONOMIC_FAILURE_LOCI = {
    "STATE", "DECISION", "MEASUREMENT", "MECHANISM", "TRANSMISSION", "ENVIRONMENT",
}
APPLICATION_DISPOSITIONS = {"APPLIED", "NARROWED", "INAPPLICABLE"}
FORBIDDEN_FIELDS = {
    "prediction", "baseline", "actual_observation", "mechanism_chain_ids",
    "transmission", "threshold", "probability", "valuation", "price",
    "return", "investment_return", "expected_return", "action", "position",
    "decision", "decision_entry_ids", "valuation_model_ids",
}


class JudgmentLearningError(ValueError):
    """Raised when a learning note would rewrite or misstate frozen feedback."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _required_text(value: Any, field: str, errors: list[str]) -> str:
    result = str(value or "").strip()
    if not result:
        errors.append(field + "_missing")
    return result


def _feedback_card(feedback: dict[str, Any], claim_id: str) -> dict[str, Any] | None:
    cards = feedback.get("cards")
    if not isinstance(cards, list):
        return None
    matches = [card for card in cards if isinstance(card, dict) and card.get("claim_id") == claim_id]
    return matches[0] if len(matches) == 1 else None


def build_judgment_learning_note(
    feedback: dict[str, Any],
    note_id: str,
    claim_id: str,
    disposition: str,
    state_scope: str,
    measurement_scope: str,
    learning_basis: str,
    next_research_change: str,
    *,
    feedback_ref: str,
    experiment_id: str | None = None,
    company_cluster_id: str | None = None,
    root_cause_classes: list[str] | None = None,
    failure_loci: list[str] | None = None,
    economic_failure_loci: list[str] | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build a note that cites feedback but cannot carry a revised thesis.

    The caller supplies only the action for the next research cycle.  Frozen
    claims, thresholds, observations and investment fields are deliberately
    absent: their canonical record stays in the frozen case and settlement.
    """
    note = {
        "schema_version": SCHEMA_VERSION,
        "note_id": str(note_id or "").strip(),
        "case_id": feedback.get("case_id"),
        "freeze_id": feedback.get("freeze_id"),
        "settlement_id": feedback.get("settlement_id"),
        "claim_id": str(claim_id or "").strip(),
        "feedback_ref": str(feedback_ref or "").strip(),
        "disposition": str(disposition or "").upper(),
        "applicability": {
            "state_scope": str(state_scope or "").strip(),
            "measurement_scope": str(measurement_scope or "").strip(),
        },
        "learning_basis": str(learning_basis or "").strip(),
        "next_research_change": str(next_research_change or "").strip(),
        "experiment_id": str(experiment_id or "").strip(),
        "company_cluster_id": str(company_cluster_id or "").strip(),
        "root_cause_classes": list(root_cause_classes or []),
        # ``failure_loci`` is retained as the research-design dimension.  The
        # parallel enterprise/economic dimension is explicit rather than
        # overloading similarly named values such as MECHANISM.
        "failure_loci": list(failure_loci or []),
        "economic_failure_loci": list(economic_failure_loci or []),
        "recorded_at": str(recorded_at or _now()),
        "policy_note": (
            "Append-only learning action. It does not amend the frozen judgment, "
            "its evidence, threshold, mechanism, baseline, valuation, return or action."
        ),
    }
    validation = validate_judgment_learning_note(note, feedback)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentLearningError("invalid judgment learning note: " + ", ".join(
            validation["findings"]
        ))

    card = _feedback_card(feedback, note["claim_id"])
    assert card is not None  # validated above; keeps the output field order local.
    note["feedback_context"] = {
        "forward_judgment_id": card.get("forward_judgment_id"),
        "settlement_status": card.get("settlement_status"),
        "judgment_outcome_status": (card.get("judgment_outcome") or {}).get("status"),
        "increment_vs_baseline": card.get("increment_vs_baseline"),
        "rival_hypothesis_feedback": card.get("rival_hypothesis_feedback"),
    }
    return note


def validate_judgment_learning_note(note: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any]:
    """Validate a learning action against exactly one immutable feedback card."""
    findings: list[str] = []
    if not isinstance(note, dict):
        return {
            "schema_version": "judgment-learning-note-validation.v1",
            "state": "INVALID",
            "findings": ["note_not_object"],
        }
    if note.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if feedback.get("schema_version") != "judgment-feedback-card.v2":
        findings.append("feedback_schema_version_invalid")
    note_id = _required_text(note.get("note_id"), "note_id", findings)
    if note_id and not re.fullmatch(r"LNOTE:[A-Za-z0-9._:-]+", note_id):
        findings.append("note_id_invalid")
    claim_id = _required_text(note.get("claim_id"), "claim_id", findings)
    _required_text(note.get("feedback_ref"), "feedback_ref", findings)
    for field in ("case_id", "freeze_id", "settlement_id"):
        value = _required_text(note.get(field), field, findings)
        if value and value != str(feedback.get(field) or ""):
            findings.append(field + "_feedback_mismatch")
    card = _feedback_card(feedback, claim_id)
    if card is None:
        findings.append("claim_id_not_in_feedback")
    disposition = str(note.get("disposition") or "").upper()
    if disposition not in DISPOSITIONS:
        findings.append("disposition_invalid")
    applicability = note.get("applicability")
    if not isinstance(applicability, dict):
        findings.append("applicability_not_object")
    else:
        _required_text(applicability.get("state_scope"), "state_scope", findings)
        _required_text(applicability.get("measurement_scope"), "measurement_scope", findings)
    _required_text(note.get("learning_basis"), "learning_basis", findings)
    _required_text(note.get("next_research_change"), "next_research_change", findings)
    _required_text(note.get("experiment_id"), "experiment_id", findings)
    _required_text(note.get("company_cluster_id"), "company_cluster_id", findings)
    for field in ("experiment_id", "company_cluster_id"):
        if field in feedback:
            expected = _required_text(feedback.get(field), "feedback_" + field, findings)
            if expected and note.get(field) != expected:
                findings.append(field + "_feedback_mismatch")
    _required_text(note.get("recorded_at"), "recorded_at", findings)
    root_causes = note.get("root_cause_classes")
    if not isinstance(root_causes, list):
        findings.append("root_cause_classes_not_array")
    else:
        if not root_causes:
            findings.append("root_cause_classes_missing")
        invalid_causes = sorted({str(item) for item in root_causes} - ROOT_CAUSE_CLASSES)
        if invalid_causes:
            findings.append("root_cause_classes_invalid:" + ",".join(invalid_causes))
    failure_loci = note.get("failure_loci")
    if not isinstance(failure_loci, list):
        findings.append("failure_loci_not_array")
    else:
        if not failure_loci:
            findings.append("failure_loci_missing")
        invalid_loci = sorted({str(item) for item in failure_loci} - ANALYSIS_FAILURE_LOCI)
        if invalid_loci:
            findings.append("failure_loci_invalid:" + ",".join(invalid_loci))
    economic_loci = note.get("economic_failure_loci")
    if not isinstance(economic_loci, list):
        findings.append("economic_failure_loci_not_array")
    else:
        if not economic_loci:
            findings.append("economic_failure_loci_missing")
        invalid_economic_loci = sorted({str(item) for item in economic_loci} - ECONOMIC_FAILURE_LOCI)
        if invalid_economic_loci:
            findings.append("economic_failure_loci_invalid:" + ",".join(invalid_economic_loci))
    forbidden = sorted(FORBIDDEN_FIELDS & set(note))
    if forbidden:
        findings.append("frozen_or_investment_fields_forbidden:" + ",".join(forbidden))
    if card is not None and disposition in {"RETAIN", "RETIRE"}:
        if card.get("settlement_status") != "CALCULATED":
            findings.append("retain_or_retire_requires_calculated_settlement")
        rival_feedback = card.get("rival_hypothesis_feedback")
        if isinstance(rival_feedback, dict):
            rival_state = rival_feedback.get("state")
            if rival_state != "NOT_PRESENT_IN_LEGACY_FROZEN_CASE":
                accepted = {
                    "DERIVED_FROM_FROZEN_RIVAL_SIGNAL": {"SUPPORTS_PRIMARY", "SUPPORTS_RIVAL"},
                    "DERIVED_FROM_FROZEN_HYPOTHESIS_SIGNAL": {"A_ONLY", "B_ONLY"},
                }
                if rival_state not in accepted:
                    findings.append("retain_or_retire_requires_derived_rival_signal")
                elif rival_feedback.get("signal_verdict") not in accepted[rival_state]:
                    findings.append("retain_or_retire_requires_diagnostic_rival_signal")
    return {
        "schema_version": "judgment-learning-note-validation.v1",
        "state": "INVALID" if findings else "REVIEWABLE",
        "findings": findings,
    }


def _instant(
    value: Any, field: str, findings: list[str], *, allow_date_cutoff: bool = False,
) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        findings.append(field + "_missing")
        return None
    if allow_date_cutoff and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.fromisoformat(text).replace(
            hour=23, minute=59, second=59,
            tzinfo=timezone(timedelta(hours=8)),
        ).astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        findings.append(field + "_invalid")
        return None
    if parsed.tzinfo is None:
        findings.append(field + "_timezone_missing")
        return None
    return parsed.astimezone(timezone.utc)


def _same_reference(left: Any, right: Any) -> bool:
    if not str(left or "").strip() or not str(right or "").strip():
        return False
    return Path(str(left)).expanduser().resolve() == Path(str(right)).expanduser().resolve()


def validate_judgment_learning_admission(
    admission: dict[str, Any], *, note: dict[str, Any], feedback: dict[str, Any],
    control_event: dict[str, Any], information_cutoff: str,
) -> dict[str, Any]:
    """Admit a note only through its validated feedback and control-plane event.

    The event's recorded time is checked as well as its effective time.  This
    prevents a note created after a historical cutoff from being made eligible
    merely by assigning it an earlier effective date.
    """
    findings: list[str] = []
    if not isinstance(admission, dict):
        return {
            "schema_version": "judgment-learning-admission-validation.v1",
            "state": "INVALID", "findings": ["admission_not_object"],
        }
    if admission.get("schema_version") != ADMISSION_SCHEMA_VERSION:
        findings.append("admission_schema_version_invalid")
    expected_fields = {
        "schema_version", "learning_note_ref", "feedback_ref", "control_plane_db",
        "feedback_item_id", "learning_note_event_id", "learning_note_effective_at",
    }
    unexpected_fields = sorted(set(admission) - expected_fields)
    if unexpected_fields:
        findings.append("admission_unexpected_fields:" + ",".join(unexpected_fields))
    note_ref = _required_text(admission.get("learning_note_ref"), "learning_note_ref", findings)
    feedback_ref = _required_text(admission.get("feedback_ref"), "feedback_ref", findings)
    _required_text(admission.get("control_plane_db"), "control_plane_db", findings)
    feedback_item_id = _required_text(
        admission.get("feedback_item_id"), "feedback_item_id", findings,
    )
    event_id = _required_text(
        admission.get("learning_note_event_id"), "learning_note_event_id", findings,
    )
    declared_effective_text = _required_text(
        admission.get("learning_note_effective_at"), "learning_note_effective_at", findings,
    )
    note_validation = validate_judgment_learning_note(note, feedback)
    if note_validation.get("state") != "REVIEWABLE":
        findings.extend(
            "learning_note_invalid:" + str(item)
            for item in note_validation.get("findings") or []
        )
    if feedback_ref and not _same_reference(note.get("feedback_ref"), feedback_ref):
        findings.append("learning_note_feedback_ref_mismatch")

    if not isinstance(control_event, dict) or not control_event:
        findings.append("learning_note_ready_event_missing")
        control_event = {}
    if event_id and control_event.get("event_id") != event_id:
        findings.append("learning_note_event_id_mismatch")
    if control_event.get("event_type") != "LEARNING_NOTE_READY":
        findings.append("learning_note_event_type_invalid")
    if feedback_item_id and control_event.get("feedback_item_id") != feedback_item_id:
        findings.append("learning_note_feedback_item_mismatch")
    control_claim = (
        control_event.get("control_claim")
        if isinstance(control_event.get("control_claim"), dict) else {}
    )
    if control_claim.get("episode_id") != note.get("case_id"):
        findings.append("learning_note_control_case_mismatch")
    if control_claim.get("claim_id") != note.get("claim_id"):
        findings.append("learning_note_control_claim_mismatch")
    payload = control_event.get("payload") if isinstance(control_event.get("payload"), dict) else {}
    admission_findings = control_event.get("admission_findings")
    if control_event and control_event.get("admission_state") != "REVIEWABLE":
        if isinstance(admission_findings, list) and admission_findings:
            findings.extend(str(item) for item in admission_findings)
        else:
            findings.append("learning_note_event_cutoff_replay_missing")
    if note_ref and not _same_reference(payload.get("learning_note_ref"), note_ref):
        findings.append("learning_note_event_note_ref_mismatch")
    if feedback_ref and not _same_reference(payload.get("feedback_ref"), feedback_ref):
        findings.append("learning_note_event_feedback_ref_mismatch")
    if note.get("note_id") and payload.get("learning_note_id") != note.get("note_id"):
        findings.append("learning_note_event_note_id_mismatch")
    for field in ("case_id", "claim_id", "settlement_id"):
        if payload.get(field) != note.get(field):
            findings.append("learning_note_event_" + field + "_mismatch")
    note_snapshot = payload.get("learning_note_snapshot")
    if not isinstance(note_snapshot, dict):
        findings.append("learning_note_event_snapshot_missing")
    elif note_snapshot != note:
        findings.append("learning_note_changed_after_ready_event")
    feedback_snapshot = payload.get("feedback_snapshot")
    if not isinstance(feedback_snapshot, dict):
        findings.append("learning_feedback_event_snapshot_missing")
    elif feedback_snapshot != feedback:
        findings.append("learning_feedback_changed_after_ready_event")
    artifact_refs = control_event.get("artifact_refs")
    if not isinstance(artifact_refs, list):
        findings.append("learning_note_event_artifact_refs_invalid")
    else:
        for label, reference in (("note", note_ref), ("feedback", feedback_ref)):
            if reference and not any(_same_reference(item, reference) for item in artifact_refs):
                findings.append(f"learning_note_event_{label}_artifact_missing")

    cutoff = _instant(
        information_cutoff, "information_cutoff", findings, allow_date_cutoff=True,
    )
    note_recorded = _instant(note.get("recorded_at"), "learning_note_recorded_at", findings)
    feedback_settled = _instant(
        feedback.get("settlement_as_of"), "feedback_settlement_as_of", findings,
    )
    event_effective = _instant(
        control_event.get("effective_at"), "learning_note_event_effective_at", findings,
    )
    declared_effective = _instant(
        declared_effective_text, "declared_learning_note_effective_at", findings,
    )
    event_recorded = _instant(
        control_event.get("recorded_at"), "learning_note_event_recorded_at", findings,
    )
    if cutoff is not None:
        if note_recorded is not None and note_recorded > cutoff:
            findings.append("learning_note_after_information_cutoff")
        if feedback_settled is not None and feedback_settled > cutoff:
            findings.append("learning_feedback_after_information_cutoff")
        if event_effective is not None and event_effective > cutoff:
            findings.append("learning_note_event_effective_after_information_cutoff")
        if event_recorded is not None and event_recorded > cutoff:
            findings.append("learning_note_event_recorded_after_information_cutoff")
    if (
        declared_effective is not None and event_effective is not None
        and declared_effective != event_effective
    ):
        findings.append("learning_note_event_effective_at_mismatch")
    if note_recorded is not None and event_recorded is not None and note_recorded > event_recorded:
        findings.append("learning_note_recorded_after_ready_event")
    return {
        "schema_version": "judgment-learning-admission-validation.v1",
        "state": "INVALID" if findings else "REVIEWABLE",
        "findings": list(dict.fromkeys(findings)),
    }


def build_method_feedback_review(notes: list[dict[str, Any]]) -> dict[str, Any]:
    """Prepare a human method-review agenda without inventing an accuracy score.

    A learning note says what one settled signal should change next time.  This
    review groups those immutable actions by failure locus so that recurring
    research failures become visible.  It deliberately does *not* compute a
    win rate, probability, or aggregate quality score: repeated notes from
    one company are not independent evidence of a general method effect.
    """
    if not isinstance(notes, list):
        raise JudgmentLearningError("learning notes must be a list")

    required_text_fields = (
        "note_id", "case_id", "claim_id", "disposition", "experiment_id",
        "company_cluster_id", "learning_basis", "next_research_change",
    )
    invalid: list[str] = []
    seen_note_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, note in enumerate(notes):
        label = f"notes[{index}]"
        if not isinstance(note, dict):
            invalid.append(label + ":not_object")
            continue
        if note.get("schema_version") != SCHEMA_VERSION:
            invalid.append(label + ":schema_version_invalid")
        missing = [field for field in required_text_fields if not str(note.get(field) or "").strip()]
        if missing:
            invalid.append(label + ":missing_" + ",".join(missing))
        note_id = str(note.get("note_id") or "").strip()
        if note_id and note_id in seen_note_ids:
            invalid.append(label + ":duplicate_note_id")
        seen_note_ids.add(note_id)
        for field, allowed in (
            ("root_cause_classes", ROOT_CAUSE_CLASSES),
            ("failure_loci", ANALYSIS_FAILURE_LOCI),
            ("economic_failure_loci", ECONOMIC_FAILURE_LOCI),
        ):
            value = note.get(field)
            if not isinstance(value, list) or not value:
                invalid.append(label + ":" + field + "_missing")
            elif set(map(str, value)) - allowed:
                invalid.append(label + ":" + field + "_invalid")
        normalized.append(note)
    if invalid:
        raise JudgmentLearningError("invalid learning-review input: " + ", ".join(invalid))

    company_clusters = sorted({str(note["company_cluster_id"]) for note in normalized})
    cases = sorted({str(note["case_id"]) for note in normalized})
    analysis_grouped: dict[str, list[dict[str, Any]]] = {}
    economic_grouped: dict[str, list[dict[str, Any]]] = {}
    for note in normalized:
        for locus in sorted({str(item) for item in note["failure_loci"]}):
            analysis_grouped.setdefault(locus, []).append(note)
        for locus in sorted({str(item) for item in note["economic_failure_loci"]}):
            economic_grouped.setdefault(locus, []).append(note)

    def summarize(grouped: dict[str, list[dict[str, Any]]], field: str) -> list[dict[str, Any]]:
        summaries = []
        for locus in sorted(grouped):
            group = sorted(grouped[locus], key=lambda item: str(item["note_id"]))
            summaries.append({
            field: locus,
            "note_ids": [str(item["note_id"]) for item in group],
            "case_ids": sorted({str(item["case_id"]) for item in group}),
            "company_cluster_ids": sorted({str(item["company_cluster_id"]) for item in group}),
            "experiment_ids": sorted({str(item["experiment_id"]) for item in group}),
            "root_cause_classes": sorted({str(cause) for item in group for cause in item["root_cause_classes"]}),
            "dispositions": sorted({str(item["disposition"]) for item in group}),
            "proposed_next_research_changes": [str(item["next_research_change"]) for item in group],
            })
        return summaries

    if not normalized:
        state = "NO_LEARNING_NOTES"
    elif len(company_clusters) == 1:
        state = "SINGLE_COMPANY_ACTION_ONLY"
    else:
        state = "MULTI_COMPANY_METHOD_REVIEW_REQUIRED"
    return {
        "schema_version": "method-feedback-review.v1",
        "state": state,
        "note_ids": [str(note["note_id"]) for note in sorted(normalized, key=lambda item: str(item["note_id"]))],
        "case_ids": cases,
        "company_cluster_ids": company_clusters,
        "analysis_failure_loci": summarize(analysis_grouped, "analysis_failure_locus"),
        "economic_failure_loci": summarize(economic_grouped, "economic_failure_locus"),
        "limitations": [
            "This is a human review agenda, not an accuracy, calibration, probability, or method-quality score.",
            "Different case IDs in one company cluster remain correlated and cannot establish a general method effect.",
            "A proposed change becomes a method update only when a reviewer records its scope, counterexample, and next replication.",
        ],
    }


def _json_pointer_value(payload: dict[str, Any], pointer: str) -> tuple[bool, Any]:
    """Resolve the narrow JSON-pointer subset used by a frozen ledger receipt."""
    if not pointer.startswith("/"):
        return False, None
    current: Any = payload
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False, None
    return True, current


def validate_learning_application_receipt(
    receipt: dict[str, Any], *, notes: list[dict[str, Any]], method_review: dict[str, Any], target_freeze: dict[str, Any],
) -> dict[str, Any]:
    """Verify that settled learning changed a later company's frozen inputs.

    This is intentionally an application receipt, not an automatic decision
    engine.  The reviewer records whether the proposed change is applicable;
    the validator proves the cited note/review lineage, a different company,
    and the concrete frozen values that were actually changed before outcome.
    """
    findings: list[str] = []
    if not isinstance(receipt, dict):
        return {"state": "INVALID", "findings": ["receipt_not_object"]}
    if receipt.get("schema_version") != APPLICATION_RECEIPT_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    receipt_id = _required_text(receipt.get("receipt_id"), "receipt_id", findings)
    if receipt_id and not re.fullmatch(r"LAPP:[A-Za-z0-9._:-]+", receipt_id):
        findings.append("receipt_id_invalid")
    if method_review.get("schema_version") != "method-feedback-review.v1":
        findings.append("method_review_schema_invalid")
    if method_review.get("state") != "MULTI_COMPANY_METHOD_REVIEW_REQUIRED":
        findings.append("method_review_not_cross_company")
    source_note_ids = receipt.get("source_note_ids")
    note_map = {str(note.get("note_id") or ""): note for note in notes if isinstance(note, dict)}
    review_note_ids = {str(note_id) for note_id in method_review.get("note_ids") or []}
    if not isinstance(source_note_ids, list) or not source_note_ids:
        findings.append("source_note_ids_missing")
        source_note_ids = []
    elif len({str(item) for item in source_note_ids}) != len(source_note_ids):
        findings.append("source_note_ids_duplicate")
    elif any(str(note_id) not in note_map or str(note_id) not in review_note_ids for note_id in source_note_ids):
        findings.append("source_note_not_in_method_review")
    method_decision = receipt.get("method_review_decision")
    if not isinstance(method_decision, dict):
        findings.append("method_review_decision_missing")
    else:
        _required_text(method_decision.get("decision_id"), "method_review_decision_id", findings)
        if method_decision.get("disposition") not in APPLICATION_DISPOSITIONS:
            findings.append("method_review_decision_disposition_invalid")
        _required_text(method_decision.get("rationale"), "method_review_decision_rationale", findings)
    target = receipt.get("target")
    target_cluster = ""
    if not isinstance(target, dict):
        findings.append("target_missing")
    else:
        target_cluster = _required_text(target.get("company_cluster_id"), "target_company_cluster_id", findings)
        _required_text(target.get("experiment_id"), "target_experiment_id", findings)
        freeze_id = _required_text(target.get("freeze_id"), "target_freeze_id", findings)
        target_freeze_id = str(target_freeze.get("freeze_id") or ((target_freeze.get("report_freeze") or {}).get("freeze_id")) or "")
        if freeze_id and freeze_id != target_freeze_id:
            findings.append("target_freeze_id_mismatch")
    source_clusters = {str(note_map[str(note_id)].get("company_cluster_id") or "") for note_id in source_note_ids if str(note_id) in note_map}
    if target_cluster and target_cluster in source_clusters:
        findings.append("target_company_must_differ_from_source_notes")
    applications = receipt.get("applications")
    applied_note_ids: set[str] = set()
    if not isinstance(applications, list) or not applications:
        findings.append("applications_missing")
    else:
        for index, application in enumerate(applications):
            prefix = f"applications[{index}]"
            if not isinstance(application, dict):
                findings.append(prefix + ":not_object")
                continue
            note_id = _required_text(application.get("note_id"), prefix + ":note_id", findings)
            applied_note_ids.add(note_id)
            if note_id not in {str(item) for item in source_note_ids}:
                findings.append(prefix + ":note_not_declared_source")
            disposition = application.get("disposition")
            if disposition not in APPLICATION_DISPOSITIONS:
                findings.append(prefix + ":disposition_invalid")
            _required_text(application.get("scope_rationale"), prefix + ":scope_rationale", findings)
            _required_text(application.get("counterexample_or_boundary"), prefix + ":counterexample_or_boundary", findings)
            changes = application.get("frozen_field_changes")
            if disposition == "APPLIED":
                if not isinstance(changes, list) or not changes:
                    findings.append(prefix + ":applied_requires_frozen_field_change")
                    continue
                for change_index, change in enumerate(changes):
                    change_prefix = f"{prefix}:frozen_field_changes[{change_index}]"
                    if not isinstance(change, dict):
                        findings.append(change_prefix + ":not_object")
                        continue
                    pointer = _required_text(change.get("json_pointer"), change_prefix + ":json_pointer", findings)
                    if "prior_rule" not in change or "new_frozen_value" not in change:
                        findings.append(change_prefix + ":prior_rule_or_new_value_missing")
                    found, value = _json_pointer_value(target_freeze, pointer)
                    if not found:
                        findings.append(change_prefix + ":json_pointer_not_in_target_freeze")
                    elif value != change.get("new_frozen_value"):
                        findings.append(change_prefix + ":new_value_not_in_target_freeze")
            elif changes not in (None, []):
                findings.append(prefix + ":non_applied_cannot_claim_frozen_field_change")
    if {str(item) for item in source_note_ids} != applied_note_ids:
        findings.append("every_source_note_requires_explicit_application_disposition")
    review = receipt.get("independent_reviewer")
    preparer = str(receipt.get("prepared_by") or "").strip()
    if not preparer:
        findings.append("prepared_by_missing")
    if not isinstance(review, dict):
        findings.append("independent_reviewer_missing")
    else:
        reviewer_id = _required_text(review.get("reviewer_id"), "reviewer_id", findings)
        if reviewer_id and reviewer_id == preparer:
            findings.append("reviewer_must_differ_from_preparer")
        if review.get("verdict") != "CONFIRMED_FIELD_CHANGE":
            findings.append("reviewer_verdict_invalid")
        _required_text(review.get("review_note"), "review_note", findings)
    return {"state": "INVALID" if findings else "REVIEWABLE", "findings": findings}


def persist_learning_application_receipt(
    output_dir: str | Path, receipt: dict[str, Any], *, notes: list[dict[str, Any]], method_review: dict[str, Any], target_freeze: dict[str, Any],
) -> dict[str, Any]:
    """Persist a validated receipt once; later outcome work cannot overwrite it."""
    validation = validate_learning_application_receipt(
        receipt, notes=notes, method_review=method_review, target_freeze=target_freeze,
    )
    if validation["state"] != "REVIEWABLE":
        return {"written": False, "validation": validation, "error": "invalid_learning_application_receipt"}
    receipts_dir = Path(output_dir) / "learning_application_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    path = receipts_dir / (str(receipt["receipt_id"]).replace(":", "_") + ".json")
    if path.exists():
        return {"written": False, "validation": validation, "error": "learning_application_receipt_already_exists", "path": str(path)}
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "path": str(path), "validation": validation}


def persist_judgment_learning_note(
    output_dir: str | Path,
    note: dict[str, Any],
    feedback: dict[str, Any],
) -> dict[str, Any]:
    """Append a validated note; an existing note ID is never overwritten."""
    validation = validate_judgment_learning_note(note, feedback)
    if validation["state"] != "REVIEWABLE":
        return {"written": False, "validation": validation, "error": "invalid_learning_note"}
    note_id = str(note["note_id"])
    notes_dir = Path(output_dir) / "judgment_learning_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / (note_id.replace(":", "_") + ".json")
    if path.exists():
        return {
            "written": False,
            "validation": validation,
            "error": "learning_note_already_exists",
            "path": str(path),
        }
    path.write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "path": str(path), "validation": validation}
