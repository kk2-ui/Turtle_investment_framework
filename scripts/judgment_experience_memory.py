#!/usr/bin/env python3
"""Condition-bound experience retrieval for enterprise-judgment research.

This module is deliberately a thin projection layer.  It turns reviewed
Teaching or feedback material into source-side, versioned experience records;
then it lets a pre-outcome target retrieve and explicitly accept or reject an
experience.  It does not own company facts, LearningNotes, CJO values,
valuation, or a second target-card schema.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


JUDGMENT_EXPERIENCE_RECORD_SCHEMA = "judgment-experience-record.v1"
EXPERIENCE_RETRIEVAL_PACK_SCHEMA = "experience-retrieval-pack.v1"
EXPERIENCE_INVOCATION_RECEIPT_SCHEMA = "experience-invocation-receipt.v1"
EXPERIENCE_FEEDBACK_EVENT_SCHEMA = "experience-feedback-event.v1"
EXPERIENCE_REGISTRY_SCHEMA = "judgment-experience-registry.v1"

SOURCE_KINDS = {"TEACHING", "BLIND_FEEDBACK", "LEARNING_NOTE", "CONDITIONAL_MECHANISM", "COMPARATIVE"}
# ``MECHANISM_CANDIDATE`` and ``TEACHING_ONLY`` are the vocabulary emitted by
# the existing Enterprise/J2 read models.  V1 accepts them as source evidence
# ceilings, but normalizes their *authority* for structural filtering.  This
# is compatibility with an existing read model, not a new evidence tier.
EVIDENCE_CEILINGS = {
    "CONTEXT_ONLY", "TEACHING", "TEACHING_ONLY", "MECHANISM",
    "MECHANISM_CANDIDATE", "COMPARATIVE", "TRANSFERRED",
}
EVIDENCE_CEILING_LEVELS = {
    "CONTEXT_ONLY": 0,
    "TEACHING": 1,
    "TEACHING_ONLY": 1,
    "MECHANISM": 2,
    "MECHANISM_CANDIDATE": 2,
    "COMPARATIVE": 3,
    "TRANSFERRED": 4,
}
RECORD_STATUSES = {"DRAFT", "RETRIEVAL_READY", "BOUNDED", "RETIRED"}
RETRIEVAL_ROLES = {"PRIMARY_ANALOG", "STRONGEST_NEAR_MISS", "BOUNDARY_RECORD"}
INVOCATION_STATES = {"RETRIEVED_NOT_APPLIED", "APPLIED_PREOUTCOME", "REJECTED_AS_MISMATCH"}
FEEDBACK_STATUSES = {
    "SUPPORTED", "BOUNDARY_EXPOSED", "MISAPPLIED", "NOT_DIAGNOSTIC", "MEASUREMENT_BLOCKED", "RETIRED",
}
PREOUTCOME_ACCESS_STATES = {"SEALED", "NOT_YET_RELEASED", "PREOUTCOME_ONLY"}
ECONOMIC_FAILURE_LOCI = {"STATE", "DECISION", "MEASUREMENT", "MECHANISM", "TRANSMISSION", "ENVIRONMENT"}
FORBIDDEN_TOP_LEVEL_FIELDS = {"actual", "outcome", "price", "valuation", "buyband", "investment_action", "probability"}
TARGET_CONTROL_SCHEMA = "judgment-experience-preoutcome-control.v1"


class JudgmentExperienceError(ValueError):
    """Raised when a record would overreach its source or target boundary."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _findings_result(findings: list[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(findings))
    return {
        "schema_version": "judgment-experience-validation.v1",
        "state": "REVIEWABLE" if not unique else "INVALID",
        "findings": unique,
    }


def _iso_timestamp(value: Any, field: str, findings: list[str]) -> None:
    raw = _text(value)
    if not raw:
        findings.append(field + "_missing")
        return
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        findings.append(field + "_invalid")


def _parse_timestamp(value: Any, field: str) -> datetime:
    raw = _text(value)
    if not raw:
        raise JudgmentExperienceError(field + "_missing")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise JudgmentExperienceError(field + "_invalid") from exc
    if parsed.tzinfo is None:
        raise JudgmentExperienceError(field + "_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _canonical_company_cluster_id(company_id: Any) -> str:
    """Match the curriculum's canonical ``COMPANY:CNxxxxxx`` identity."""
    raw = _text(company_id).upper()
    if raw.startswith("COMPANY:"):
        raw = raw.removeprefix("COMPANY:")
    raw = raw.replace(":", "")
    if not raw:
        return ""
    return "COMPANY:" + raw


def _same_company_cluster(left: Any, right: Any) -> bool:
    return bool(_text(left)) and _text(left).upper() == _text(right).upper()


def _valid_company_cluster_id(value: Any) -> bool:
    return _text(value).upper().startswith("COMPANY:") and len(_text(value)) > len("COMPANY:")


def _repository_path(reference: Any) -> Path | None:
    """Resolve repository-relative artifacts without treating a URL as proof."""
    text = _text(reference).split("#", 1)[0]
    if not text or "://" in text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    root = Path(__file__).resolve().parents[1]
    resolved = root / candidate
    return resolved if resolved.is_file() else None


def _read_json_reference(reference: Any) -> dict[str, Any] | None:
    path = _repository_path(reference)
    if path is None or path.suffix.lower() != ".json":
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _ceiling_allows(*, permitted: Any, source: Any) -> bool:
    return (
        _text(permitted) in EVIDENCE_CEILING_LEVELS
        and _text(source) in EVIDENCE_CEILING_LEVELS
        and EVIDENCE_CEILING_LEVELS[_text(source)] <= EVIDENCE_CEILING_LEVELS[_text(permitted)]
    )


def _required(payload: dict[str, Any], fields: tuple[str, ...], prefix: str, findings: list[str]) -> None:
    for field in fields:
        if not _text(payload.get(field)):
            findings.append(prefix + field + "_missing")


def _text_list(value: Any, field: str, findings: list[str], *, minimum: int = 1) -> list[str]:
    if not isinstance(value, list):
        findings.append(field + "_not_list")
        return []
    result = [_text(item) for item in value if _text(item)]
    if len(result) < minimum:
        findings.append(field + "_missing")
    return result


def _forbidden_fields(payload: dict[str, Any], findings: list[str], *, prefix: str = "") -> None:
    for key, value in payload.items():
        lower = str(key).lower()
        if lower in FORBIDDEN_TOP_LEVEL_FIELDS:
            findings.append(prefix + "forbidden_" + lower + "_field")
        if isinstance(value, dict):
            _forbidden_fields(value, findings, prefix=prefix + str(key) + ".")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _forbidden_fields(item, findings, prefix=prefix + str(key) + ".")


def _validate_structural_key(value: Any, findings: list[str], *, prefix: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        findings.append(prefix + "structural_key_not_object")
        return {}
    _required(value, ("lifecycle", "industry_epoch", "competitive_arena", "responsibility_boundary"), prefix, findings)
    _text_list(value.get("mechanism_kinds"), prefix + "mechanism_kinds", findings)
    _text_list(value.get("company_constraints"), prefix + "company_constraints", findings)
    return value


def validate_judgment_experience_record(record: Any) -> dict[str, Any]:
    """Validate a source-side record without interpreting it as a target fact."""
    findings: list[str] = []
    if not isinstance(record, dict):
        return _findings_result(["record_not_object"])
    if record.get("schema_version") != JUDGMENT_EXPERIENCE_RECORD_SCHEMA:
        findings.append("schema_version_invalid")
    _required(record, ("record_id", "source_case_id", "source_company_id", "source_company_cluster_id", "status", "source_kind", "evidence_ceiling", "proposition", "strongest_rival", "decision_or_no_action", "mechanism_chain", "investor_relevance"), "", findings)
    if not _text(record.get("record_id")).startswith("JER:"):
        findings.append("record_id_invalid")
    if record.get("source_kind") not in SOURCE_KINDS:
        findings.append("source_kind_invalid")
    if record.get("status") not in RECORD_STATUSES:
        findings.append("status_invalid")
    if record.get("evidence_ceiling") not in EVIDENCE_CEILINGS:
        findings.append("evidence_ceiling_invalid")
    if not isinstance(record.get("version"), int) or record.get("version", 0) < 1:
        findings.append("version_invalid")
    if not _valid_company_cluster_id(record.get("source_company_cluster_id")):
        findings.append("source_company_cluster_id_invalid")
    _iso_timestamp(record.get("recorded_at"), "recorded_at", findings)
    _text_list(record.get("source_refs"), "source_refs", findings)
    _text_list(record.get("review_refs"), "review_refs", findings)
    _text_list(record.get("observable_signals"), "observable_signals", findings)
    _text_list(record.get("apply_when"), "apply_when", findings)
    _text_list(record.get("do_not_apply_when"), "do_not_apply_when", findings)
    _text_list(record.get("retrieval_roles"), "retrieval_roles", findings)
    for role in record.get("retrieval_roles") or []:
        if role not in RETRIEVAL_ROLES:
            findings.append("retrieval_role_invalid")
    _validate_structural_key(record.get("structural_key"), findings, prefix="")
    loci = _text_list(record.get("economic_failure_loci"), "economic_failure_loci", findings)
    if any(item not in ECONOMIC_FAILURE_LOCI for item in loci):
        findings.append("economic_failure_locus_invalid")
    feedback_refs = record.get("feedback_event_refs", [])
    if not isinstance(feedback_refs, list) or any(not _text(value) for value in feedback_refs):
        findings.append("feedback_event_refs_invalid")
    _forbidden_fields(record, findings)
    return _findings_result(findings)


def compile_teaching_experience_record(
    teaching_case: dict[str, Any],
    *,
    record_id: str,
    recorded_at: str,
    structural_key: dict[str, Any],
    retrieval_roles: list[str],
    economic_failure_loci: list[str],
    apply_when: list[str],
    do_not_apply_when: list[str],
) -> dict[str, Any]:
    """Compile an existing reviewed curriculum lesson; never mine new facts."""
    if teaching_case.get("track") != "TEACHING" or teaching_case.get("status") != "CURATED":
        raise JudgmentExperienceError("only curated Teaching cases may compile a Teaching experience record")
    lesson = teaching_case.get("lesson")
    if not isinstance(lesson, dict):
        raise JudgmentExperienceError("Teaching case has no curated lesson")
    artifacts = teaching_case.get("artifact_refs") if isinstance(teaching_case.get("artifact_refs"), dict) else {}
    review_ref = _text(artifacts.get("postoutcome_review_ref"))
    if not review_ref:
        raise JudgmentExperienceError("Teaching case lacks independent post-outcome review reference")
    record = {
        "schema_version": JUDGMENT_EXPERIENCE_RECORD_SCHEMA,
        "record_id": record_id,
        "version": 1,
        "status": "RETRIEVAL_READY",
        "source_kind": "TEACHING",
        "source_case_id": teaching_case.get("case_id"),
        "source_company_id": teaching_case.get("company_id"),
        "source_company_cluster_id": _canonical_company_cluster_id(teaching_case.get("company_id")),
        "source_refs": deepcopy(teaching_case.get("source_refs") or []),
        "review_refs": [review_ref],
        "evidence_ceiling": "TEACHING",
        "proposition": lesson.get("mechanism_lesson"),
        "structural_key": deepcopy(structural_key),
        "decision_or_no_action": lesson.get("management_choice_or_no_action"),
        "mechanism_chain": " -> ".join([
            _text(lesson.get("state_and_constraint")),
            _text(lesson.get("customer_or_operating_response")),
            _text(lesson.get("cash_or_capital_result")),
        ]),
        "observable_signals": [lesson.get("transfer_question")],
        "strongest_rival": lesson.get("strongest_rival"),
        "apply_when": list(apply_when),
        "do_not_apply_when": list(do_not_apply_when),
        "investor_relevance": lesson.get("investor_treatment"),
        "retrieval_roles": list(retrieval_roles),
        "economic_failure_loci": list(economic_failure_loci),
        "feedback_event_refs": [],
        "recorded_at": recorded_at,
    }
    validation = validate_judgment_experience_record(record)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("compiled Teaching record invalid: " + ", ".join(validation["findings"]))
    return record


def compile_feedback_experience_record(
    feedback_receipt: dict[str, Any],
    *,
    record_id: str,
    source_case_id: str,
    source_refs: list[str],
    review_refs: list[str],
    recorded_at: str,
    proposition: str,
    structural_key: dict[str, Any],
    decision_or_no_action: str,
    mechanism_chain: str,
    observable_signals: list[str],
    strongest_rival: str,
    apply_when: list[str],
    do_not_apply_when: list[str],
    investor_relevance: str,
    retrieval_roles: list[str],
    economic_failure_loci: list[str],
) -> dict[str, Any]:
    """Compile a reviewed Blind feedback receipt without copying its outcome facts.

    The resulting record carries a conditional research question.  It does not
    carry the settled values, the source company's judgment, or a target
    conclusion.  The receipt remains the only outcome-bearing source.
    """
    candidate = feedback_receipt.get("candidate") if isinstance(feedback_receipt.get("candidate"), dict) else {}
    review = feedback_receipt.get("independent_post_outcome_review") if isinstance(feedback_receipt.get("independent_post_outcome_review"), dict) else {}
    if feedback_receipt.get("status") != "COMPLETED" or _text(review.get("verdict")).upper() != "ACCEPT":
        raise JudgmentExperienceError("only completed independently accepted feedback may compile a feedback experience record")
    if not _text(candidate.get("security_id")):
        raise JudgmentExperienceError("feedback receipt lacks source company identity")
    record = {
        "schema_version": JUDGMENT_EXPERIENCE_RECORD_SCHEMA,
        "record_id": record_id,
        "version": 1,
        "status": "RETRIEVAL_READY",
        "source_kind": "BLIND_FEEDBACK",
        "source_case_id": source_case_id,
        "source_company_id": candidate["security_id"],
        "source_company_cluster_id": _canonical_company_cluster_id(candidate["security_id"]),
        "source_refs": list(source_refs),
        "review_refs": list(review_refs),
        "evidence_ceiling": "MECHANISM",
        "proposition": _text(proposition),
        "structural_key": deepcopy(structural_key),
        "decision_or_no_action": _text(decision_or_no_action),
        "mechanism_chain": _text(mechanism_chain),
        "observable_signals": list(observable_signals),
        "strongest_rival": _text(strongest_rival),
        "apply_when": list(apply_when),
        "do_not_apply_when": list(do_not_apply_when),
        "investor_relevance": _text(investor_relevance),
        "retrieval_roles": list(retrieval_roles),
        "economic_failure_loci": list(economic_failure_loci),
        "feedback_event_refs": [source_refs[-1]] if source_refs else [],
        "recorded_at": recorded_at,
    }
    validation = validate_judgment_experience_record(record)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("compiled feedback record invalid: " + ", ".join(validation["findings"]))
    return record


def _validate_existing_source_identity(source_identity: dict[str, Any]) -> dict[str, Any]:
    """Read an existing object instead of trusting a caller-supplied label.

    V1 does not need these adapters for its minimal vertical slice, but when a
    LearningNote, ConditionalMechanism or Comparative object is registered it
    must be an actual repository object with an actual independent review
    reference.  This prevents a free-form paragraph from being promoted into
    a retrievable experience.
    """
    findings: list[str] = []
    source_kind = _text(source_identity.get("source_kind"))
    source_ref = source_identity.get("canonical_source_ref")
    source = _read_json_reference(source_ref)
    if source is None:
        return _findings_result(["canonical_source_missing_or_unreadable"])
    review_ref = source_identity.get("canonical_review_ref")
    if _repository_path(review_ref) is None:
        findings.append("canonical_review_missing_or_unreadable")
    if source_kind == "LEARNING_NOTE":
        if source.get("schema_version") != "judgment-learning-note.v1":
            findings.append("learning_note_schema_invalid")
        if source.get("case_id") != source_identity.get("source_case_id"):
            findings.append("learning_note_case_identity_mismatch")
        if _canonical_company_cluster_id(source.get("company_cluster_id")) != _canonical_company_cluster_id(source_identity.get("source_company_cluster_id")):
            findings.append("learning_note_company_cluster_mismatch")
        if not _text(source.get("feedback_ref")):
            findings.append("learning_note_feedback_ref_missing")
    elif source_kind == "CONDITIONAL_MECHANISM":
        syntheses = source.get("conditional_mechanism_synthesis")
        synthesis_id = _text(source_identity.get("canonical_synthesis_id"))
        if not isinstance(syntheses, list) or not synthesis_id:
            findings.append("conditional_mechanism_identity_missing")
        else:
            matched = next((item for item in syntheses if isinstance(item, dict) and item.get("synthesis_id") == synthesis_id), None)
            if matched is None:
                findings.append("conditional_mechanism_not_found")
            elif matched.get("evidence_ceiling") not in {"TEACHING_ONLY", "MECHANISM_CANDIDATE"}:
                findings.append("conditional_mechanism_evidence_ceiling_not_retrievable")
            elif _text(source_identity.get("evidence_ceiling")) != _text(matched.get("evidence_ceiling")):
                findings.append("conditional_mechanism_evidence_ceiling_mismatch")
    elif source_kind == "COMPARATIVE":
        review = source.get("independent_review") if isinstance(source.get("independent_review"), dict) else {}
        if "COMPARATIVE" not in _text(source.get("artifact_type")).upper():
            findings.append("comparative_artifact_type_invalid")
        if _text(review.get("verdict")).upper() not in {"ACCEPT", "PASS"}:
            findings.append("comparative_independent_review_not_accepted")
    else:
        findings.append("source_identity_kind_not_supported")
    return _findings_result(findings)


def compile_existing_source_experience_record(
    source_identity: dict[str, Any],
    *,
    record_id: str,
    recorded_at: str,
    proposition: str,
    structural_key: dict[str, Any],
    decision_or_no_action: str,
    mechanism_chain: str,
    observable_signals: list[str],
    strongest_rival: str,
    apply_when: list[str],
    do_not_apply_when: list[str],
    investor_relevance: str,
    retrieval_roles: list[str],
    economic_failure_loci: list[str],
) -> dict[str, Any]:
    """Compile an already reviewed LearningNote or mechanism synthesis by reference.

    ``source_identity`` is an adapter input, not a new canonical store.  It
    makes the existing object's type, identity, review, and source references
    explicit before the generic conditional experience is compiled.
    """
    required = (
        "source_kind", "source_case_id", "source_company_id", "source_company_cluster_id",
        "source_refs", "review_refs", "evidence_ceiling", "canonical_source_ref", "canonical_review_ref",
    )
    missing = [field for field in required if not source_identity.get(field)]
    if missing:
        raise JudgmentExperienceError("source_identity_missing:" + ",".join(missing))
    source_kind = _text(source_identity.get("source_kind"))
    if source_kind not in {"LEARNING_NOTE", "CONDITIONAL_MECHANISM", "COMPARATIVE"}:
        raise JudgmentExperienceError("source_identity_kind_not_supported_by_generic_compiler")
    source_validation = _validate_existing_source_identity(source_identity)
    if source_validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("canonical_source_invalid:" + ",".join(source_validation["findings"]))
    record = {
        "schema_version": JUDGMENT_EXPERIENCE_RECORD_SCHEMA,
        "record_id": record_id,
        "version": 1,
        "status": "RETRIEVAL_READY",
        "source_kind": source_kind,
        "source_case_id": _text(source_identity["source_case_id"]),
        "source_company_id": _text(source_identity["source_company_id"]),
        "source_company_cluster_id": _canonical_company_cluster_id(source_identity["source_company_cluster_id"]),
        "source_refs": list(source_identity["source_refs"]),
        "review_refs": list(source_identity["review_refs"]),
        "evidence_ceiling": _text(source_identity["evidence_ceiling"]),
        "proposition": _text(proposition),
        "structural_key": deepcopy(structural_key),
        "decision_or_no_action": _text(decision_or_no_action),
        "mechanism_chain": _text(mechanism_chain),
        "observable_signals": list(observable_signals),
        "strongest_rival": _text(strongest_rival),
        "apply_when": list(apply_when),
        "do_not_apply_when": list(do_not_apply_when),
        "investor_relevance": _text(investor_relevance),
        "retrieval_roles": list(retrieval_roles),
        "economic_failure_loci": list(economic_failure_loci),
        "feedback_event_refs": list(source_identity.get("feedback_event_refs") or []),
        "recorded_at": recorded_at,
    }
    validation = validate_judgment_experience_record(record)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("compiled existing-source record invalid: " + ", ".join(validation["findings"]))
    return record


def _validate_target_context(target: Any) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(target, dict):
        return _findings_result(["target_not_object"])
    allowed = {
        "case_id", "company_id", "company_cluster_id", "cutoff_at", "outcome_access_state",
        "structural_key", "primary_question", "strongest_rival", "permitted_evidence_ceiling",
        "preoutcome_control_ref",
    }
    unexpected = sorted(set(target) - allowed)
    if unexpected:
        findings.append("target_contains_unapproved_field:" + ",".join(unexpected))
    _required(target, ("case_id", "company_id", "company_cluster_id", "cutoff_at", "outcome_access_state", "primary_question", "strongest_rival", "permitted_evidence_ceiling", "preoutcome_control_ref"), "", findings)
    _iso_timestamp(target.get("cutoff_at"), "cutoff_at", findings)
    if target.get("outcome_access_state") not in PREOUTCOME_ACCESS_STATES:
        findings.append("target_outcome_access_not_preoutcome")
    if target.get("permitted_evidence_ceiling") not in EVIDENCE_CEILINGS:
        findings.append("target_evidence_ceiling_invalid")
    if not _valid_company_cluster_id(target.get("company_cluster_id")):
        findings.append("target_company_cluster_id_invalid")
    control = _read_json_reference(target.get("preoutcome_control_ref"))
    if control is None:
        findings.append("target_preoutcome_control_missing_or_unreadable")
    else:
        if control.get("schema_version") != TARGET_CONTROL_SCHEMA:
            findings.append("target_preoutcome_control_schema_invalid")
        if control.get("state") != "PREOUTCOME_FROZEN_SEALED":
            findings.append("target_preoutcome_control_not_sealed")
        for field in ("case_id", "company_id", "company_cluster_id", "cutoff_at"):
            if control.get(field) != target.get(field):
                findings.append("target_preoutcome_control_" + field + "_mismatch")
        if control.get("outcome_access_state") != target.get("outcome_access_state"):
            findings.append("target_preoutcome_control_outcome_access_mismatch")
        _iso_timestamp(control.get("frozen_at"), "target_preoutcome_control_frozen_at", findings)
        for field in ("source_packet_ref", "judgment_freeze_ref", "independent_preoutcome_review_ref"):
            if _repository_path(control.get(field)) is None:
                findings.append("target_preoutcome_control_" + field + "_missing_or_unreadable")
    _validate_structural_key(target.get("structural_key"), findings, prefix="target_")
    return _findings_result(findings)


def _structural_fit(record: dict[str, Any], target: dict[str, Any]) -> tuple[str, int, list[str]]:
    source = record["structural_key"]
    current = target["structural_key"]
    mechanisms = set(source["mechanism_kinds"]) & set(current["mechanism_kinds"])
    same_lifecycle = source["lifecycle"] == current["lifecycle"]
    same_epoch = source["industry_epoch"] == current["industry_epoch"]
    same_arena = source["competitive_arena"] == current["competitive_arena"]
    same_boundary = source["responsibility_boundary"] == current["responsibility_boundary"]
    shared_constraints = set(source["company_constraints"]) & set(current["company_constraints"])
    reasons = [
        "mechanism=" + ",".join(sorted(mechanisms)) if mechanisms else "mechanism_mismatch",
        "lifecycle_match" if same_lifecycle else "lifecycle_mismatch",
        "arena_match" if same_arena else "arena_mismatch",
        "responsibility_boundary_match" if same_boundary else "responsibility_boundary_mismatch",
        "constraints=" + ",".join(sorted(shared_constraints)) if shared_constraints else "constraints_mismatch",
    ]
    if not mechanisms:
        return "NO_MATCH", 0, reasons
    score = len(mechanisms) * 10 + int(same_lifecycle) * 4 + int(same_epoch) * 2 + int(same_arena) * 4 + int(same_boundary) * 5 + len(shared_constraints)
    if same_lifecycle and same_arena and same_boundary and shared_constraints:
        return "PRIMARY_ELIGIBLE", score, reasons
    if same_boundary:
        return "NEAR_MISS_ELIGIBLE", score, reasons
    return "BOUNDARY_ONLY", score, reasons


def _latest_records_by_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose one authoritative version before retrieval.

    A later ``RETIRED`` or ``BOUNDED`` version is a correction to the source
    experience, not an additional candidate alongside the older wording.
    """
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        validation = validate_judgment_experience_record(record)
        if validation["state"] != "REVIEWABLE":
            continue
        record_id = _text(record.get("record_id"))
        previous = latest.get(record_id)
        if previous is None or int(record["version"]) > int(previous["version"]):
            latest[record_id] = record
    return [latest[record_id] for record_id in sorted(latest)]


def build_experience_retrieval_pack(
    *, pack_id: str, target: dict[str, Any], records: list[dict[str, Any]], retrieved_at: str,
) -> dict[str, Any]:
    """Return at most a primary analog, a near miss, and a boundary record."""
    target_validation = _validate_target_context(target)
    if target_validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("target context invalid: " + ", ".join(target_validation["findings"]))
    _iso_findings: list[str] = []
    _iso_timestamp(retrieved_at, "retrieved_at", _iso_findings)
    if _iso_findings:
        raise JudgmentExperienceError("retrieved_at_invalid")
    if not _text(pack_id).startswith("ERP:"):
        raise JudgmentExperienceError("pack_id_invalid")
    candidates: list[dict[str, Any]] = []
    for record in _latest_records_by_id(records):
        if record.get("status") not in {"RETRIEVAL_READY", "BOUNDED"}:
            continue
        if _same_company_cluster(record.get("source_company_cluster_id"), target.get("company_cluster_id")):
            continue
        if not _ceiling_allows(
            permitted=target.get("permitted_evidence_ceiling"), source=record.get("evidence_ceiling"),
        ):
            continue
        fit, score, reasons = _structural_fit(record, target)
        if fit == "NO_MATCH":
            continue
        candidates.append({
            "record_id": record["record_id"], "record_version": record["version"],
            "source_case_id": record["source_case_id"], "fit": fit, "score": score,
            "reasons": reasons, "roles": deepcopy(record["retrieval_roles"]),
            "evidence_ceiling": record["evidence_ceiling"],
            # This is deliberately a question-shaped projection.  It gives
            # the judgment owner the mechanism and its rival without carrying
            # the source outcome into the target company.
            "guidance": {
                "proposition": record["proposition"],
                "apply_when": deepcopy(record["apply_when"]),
                "do_not_apply_when": deepcopy(record["do_not_apply_when"]),
                "strongest_rival": record["strongest_rival"],
                "observable_signals": deepcopy(record["observable_signals"]),
                "investor_relevance": record["investor_relevance"],
            },
        })
    candidates.sort(key=lambda item: (-item["score"], item["record_id"]))
    selected: list[dict[str, Any]] = []
    primary = next((item for item in candidates if item["fit"] == "PRIMARY_ELIGIBLE" and "PRIMARY_ANALOG" in item["roles"]), None)
    if primary:
        selected.append({**primary, "role": "PRIMARY_ANALOG"})
    near_miss = next((item for item in candidates if item is not primary and item["fit"] in {"PRIMARY_ELIGIBLE", "NEAR_MISS_ELIGIBLE"} and "STRONGEST_NEAR_MISS" in item["roles"]), None)
    if near_miss:
        selected.append({**near_miss, "role": "STRONGEST_NEAR_MISS"})
    boundary = next((item for item in candidates if item is not primary and item is not near_miss and item["fit"] == "BOUNDARY_ONLY" and "BOUNDARY_RECORD" in item["roles"]), None)
    if boundary:
        selected.append({**boundary, "role": "BOUNDARY_RECORD"})
    return {
        "schema_version": EXPERIENCE_RETRIEVAL_PACK_SCHEMA,
        "pack_id": pack_id,
        "target": deepcopy(target),
        "retrieved_at": retrieved_at,
        "status": "RETRIEVAL_READY" if selected else "NO_APPLICABLE_EXPERIENCE",
        "candidates": selected,
        "not_an_answer": "Retrieved experience may change questions, rival checks, evidence order, or a conditional treatment; it is not a target-company fact or conclusion.",
    }


def validate_experience_retrieval_pack(pack: Any) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(pack, dict):
        return _findings_result(["retrieval_pack_not_object"])
    if pack.get("schema_version") != EXPERIENCE_RETRIEVAL_PACK_SCHEMA:
        findings.append("schema_version_invalid")
    if not _text(pack.get("pack_id")).startswith("ERP:"):
        findings.append("pack_id_invalid")
    _iso_timestamp(pack.get("retrieved_at"), "retrieved_at", findings)
    target_validation = _validate_target_context(pack.get("target"))
    findings.extend("target:" + item for item in target_validation["findings"])
    candidates = pack.get("candidates")
    if not isinstance(candidates, list):
        findings.append("candidates_not_list")
        candidates = []
    if pack.get("status") == "NO_APPLICABLE_EXPERIENCE" and candidates:
        findings.append("no_applicable_experience_cannot_have_candidates")
    if pack.get("status") == "RETRIEVAL_READY" and not candidates:
        findings.append("retrieval_ready_requires_candidate")
    roles = [item.get("role") for item in candidates if isinstance(item, dict)]
    if len(roles) != len(set(roles)) or any(role not in RETRIEVAL_ROLES for role in roles):
        findings.append("candidate_roles_invalid")
    for item in candidates:
        if not isinstance(item, dict):
            findings.append("candidate_not_object")
            continue
        _required(item, ("record_id", "record_version", "source_case_id", "fit", "role"), "candidate:", findings)
        if item.get("source_case_id") == (pack.get("target") or {}).get("case_id"):
            findings.append("source_target_case_identity_not_separate")
        guidance = item.get("guidance")
        if not isinstance(guidance, dict):
            findings.append("candidate_guidance_missing")
        else:
            _required(guidance, ("proposition", "strongest_rival", "investor_relevance"), "candidate:guidance_", findings)
            for field in ("apply_when", "do_not_apply_when", "observable_signals"):
                _text_list(guidance.get(field), "candidate:guidance_" + field, findings)
    record_ids = [item.get("record_id") for item in candidates if isinstance(item, dict)]
    if len(record_ids) != len(set(record_ids)):
        findings.append("candidate_record_id_duplicate")
    return _findings_result(findings)


def _contains_forbidden_investment_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            any(token in str(key).lower() for token in ("valuation", "buyband", "price", "probability", "cjo_value"))
            or _contains_forbidden_investment_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_investment_field(item) for item in value)
    return False


def build_experience_invocation_receipt(
    *, invocation_id: str, retrieval_pack: dict[str, Any], record: dict[str, Any],
    state: str, structural_match: str, mismatch_dimensions: list[str], accepted_transfer: list[str],
    rejected_transfer: list[str], changed_question_refs: list[str], changed_evidence_priority: list[str],
    changed_rival_or_discriminator_refs: list[str], changed_investor_treatment: str,
    frozen_at: str,
) -> dict[str, Any]:
    """Freeze what a target did with a retrieval before it can see an outcome."""
    pack_validation = validate_experience_retrieval_pack(retrieval_pack)
    record_validation = validate_judgment_experience_record(record)
    if pack_validation["state"] != "REVIEWABLE" or record_validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("retrieval pack or source record invalid")
    if state not in INVOCATION_STATES or not _text(invocation_id).startswith("EIR:"):
        raise JudgmentExperienceError("invocation_identity_or_state_invalid")
    target = retrieval_pack["target"]
    if _same_company_cluster(record.get("source_company_cluster_id"), target.get("company_cluster_id")):
        raise JudgmentExperienceError("source_target_company_cluster_not_separate")
    candidate = next((
        item for item in retrieval_pack["candidates"]
        if item.get("record_id") == record.get("record_id") and item.get("record_version") == record.get("version")
    ), None)
    if candidate is None:
        raise JudgmentExperienceError("record_version_not_present_in_retrieval_pack")
    retrieved_at = _parse_timestamp(retrieval_pack.get("retrieved_at"), "retrieved_at")
    frozen_timestamp = _parse_timestamp(frozen_at, "frozen_at")
    control = _read_json_reference(target.get("preoutcome_control_ref"))
    if control is None:
        raise JudgmentExperienceError("target_preoutcome_control_missing_or_unreadable")
    control_frozen_at = _parse_timestamp(control.get("frozen_at"), "target_preoutcome_control_frozen_at")
    if frozen_timestamp < retrieved_at:
        raise JudgmentExperienceError("invocation_freeze_precedes_retrieval")
    if retrieved_at < control_frozen_at:
        raise JudgmentExperienceError("retrieval_precedes_target_preoutcome_control_freeze")
    changes = {
        "changed_question_refs": list(changed_question_refs),
        "changed_evidence_priority": list(changed_evidence_priority),
        "changed_rival_or_discriminator_refs": list(changed_rival_or_discriminator_refs),
        "changed_investor_treatment": _text(changed_investor_treatment),
    }
    if _contains_forbidden_investment_field(changes):
        raise JudgmentExperienceError("experience_cannot_write_cjo_or_investment_value")
    if state == "APPLIED_PREOUTCOME" and not any(
        value for value in changes.values() if value not in ([], "")
    ):
        raise JudgmentExperienceError("applied_invocation_requires_material_research_treatment_change")
    if state == "APPLIED_PREOUTCOME" and not _text_list(accepted_transfer, "accepted_transfer", [], minimum=1):
        raise JudgmentExperienceError("applied_invocation_requires_accepted_transfer")
    if state == "APPLIED_PREOUTCOME" and not _text_list(rejected_transfer, "rejected_transfer", [], minimum=1):
        raise JudgmentExperienceError("applied_invocation_requires_rejected_transfer")
    if state != "APPLIED_PREOUTCOME" and any(value for value in changes.values() if value not in ([], "")):
        raise JudgmentExperienceError("unapplied_invocation_cannot_claim_treatment_change")
    receipt = {
        "schema_version": EXPERIENCE_INVOCATION_RECEIPT_SCHEMA,
        "invocation_id": invocation_id,
        "retrieval_pack_id": retrieval_pack["pack_id"],
        "record_id": record["record_id"],
        "record_version": record["version"],
        "target_case_id": target["case_id"],
        "target_company_id": target["company_id"],
        "target_company_cluster_id": target["company_cluster_id"],
        "cutoff_at": target["cutoff_at"],
        "preoutcome_control_ref": target["preoutcome_control_ref"],
        "retrieved_at": retrieval_pack["retrieved_at"],
        "state": state,
        "structural_match": _text(structural_match),
        "mismatch_dimensions": list(mismatch_dimensions),
        "accepted_transfer": list(accepted_transfer),
        "rejected_transfer": list(rejected_transfer),
        **changes,
        "retrieval_role": candidate["role"],
        "projected_analogy_transfer_card_id": None,
        "frozen_at": frozen_at,
        "outcome_access_state": target["outcome_access_state"],
    }
    validation = validate_experience_invocation_receipt(receipt)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("invocation receipt invalid: " + ", ".join(validation["findings"]))
    return receipt


def validate_experience_invocation_receipt(receipt: Any) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(receipt, dict):
        return _findings_result(["invocation_receipt_not_object"])
    if receipt.get("schema_version") != EXPERIENCE_INVOCATION_RECEIPT_SCHEMA:
        findings.append("schema_version_invalid")
    _required(receipt, ("invocation_id", "retrieval_pack_id", "record_id", "target_case_id", "target_company_id", "target_company_cluster_id", "cutoff_at", "state", "structural_match", "frozen_at", "outcome_access_state", "preoutcome_control_ref", "retrieved_at"), "", findings)
    if not _text(receipt.get("invocation_id")).startswith("EIR:"):
        findings.append("invocation_id_invalid")
    if receipt.get("state") not in INVOCATION_STATES:
        findings.append("invocation_state_invalid")
    if receipt.get("outcome_access_state") not in PREOUTCOME_ACCESS_STATES:
        findings.append("outcome_access_not_preoutcome")
    _iso_timestamp(receipt.get("cutoff_at"), "cutoff_at", findings)
    _iso_timestamp(receipt.get("frozen_at"), "frozen_at", findings)
    _iso_timestamp(receipt.get("retrieved_at"), "retrieved_at", findings)
    if not _valid_company_cluster_id(receipt.get("target_company_cluster_id")):
        findings.append("target_company_cluster_id_invalid")
    try:
        if _parse_timestamp(receipt.get("frozen_at"), "frozen_at") < _parse_timestamp(receipt.get("retrieved_at"), "retrieved_at"):
            findings.append("invocation_freeze_precedes_retrieval")
    except JudgmentExperienceError:
        pass
    control = _read_json_reference(receipt.get("preoutcome_control_ref"))
    if control is None:
        findings.append("invocation_preoutcome_control_missing_or_unreadable")
    elif (
        control.get("schema_version") != TARGET_CONTROL_SCHEMA
        or control.get("state") != "PREOUTCOME_FROZEN_SEALED"
        or control.get("case_id") != receipt.get("target_case_id")
        or control.get("company_id") != receipt.get("target_company_id")
        or control.get("company_cluster_id") != receipt.get("target_company_cluster_id")
        or control.get("cutoff_at") != receipt.get("cutoff_at")
        or control.get("outcome_access_state") != receipt.get("outcome_access_state")
    ):
        findings.append("invocation_preoutcome_control_does_not_match_target")
    for field in ("mismatch_dimensions", "accepted_transfer", "rejected_transfer", "changed_question_refs", "changed_evidence_priority", "changed_rival_or_discriminator_refs"):
        if not isinstance(receipt.get(field), list):
            findings.append(field + "_not_list")
    changes = [
        receipt.get("changed_question_refs") or [], receipt.get("changed_evidence_priority") or [],
        receipt.get("changed_rival_or_discriminator_refs") or [], _text(receipt.get("changed_investor_treatment")),
    ]
    if receipt.get("state") == "APPLIED_PREOUTCOME" and not any(changes):
        findings.append("applied_invocation_requires_treatment_change")
    if receipt.get("state") == "APPLIED_PREOUTCOME":
        _text_list(receipt.get("accepted_transfer"), "accepted_transfer", findings)
        _text_list(receipt.get("rejected_transfer"), "rejected_transfer", findings)
    if receipt.get("state") != "APPLIED_PREOUTCOME" and any(changes):
        findings.append("unapplied_invocation_cannot_have_treatment_change")
    card_id = receipt.get("projected_analogy_transfer_card_id")
    if receipt.get("state") != "APPLIED_PREOUTCOME" and card_id is not None:
        findings.append("unapplied_invocation_cannot_project_card")
    if card_id is not None and not _text(card_id).startswith("ATC:"):
        findings.append("projected_card_id_invalid")
    if _contains_forbidden_investment_field(receipt):
        findings.append("experience_cannot_write_cjo_or_investment_value")
    return _findings_result(findings)


def project_existing_analogy_transfer_card(
    receipt: dict[str, Any], record: dict[str, Any], target_card: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind an applied receipt to the repository's existing target-card shape."""
    receipt_validation = validate_experience_invocation_receipt(receipt)
    record_validation = validate_judgment_experience_record(record)
    if receipt_validation["state"] != "REVIEWABLE" or record_validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("cannot project from invalid invocation or record")
    if receipt.get("state") != "APPLIED_PREOUTCOME":
        raise JudgmentExperienceError("only applied invocation may project an analogy transfer card")
    required = {
        "card_id", "target_pair_id", "target_state_vector", "structural_mapping", "mismatch_dimensions",
        "application_rule", "invalidation_conditions", "strongest_near_miss", "linked_discriminator_ids",
    }
    missing = sorted(field for field in required if field not in target_card)
    if missing:
        raise JudgmentExperienceError("existing_analogy_transfer_card_fields_missing:" + ",".join(missing))
    card = deepcopy(target_card)
    if not _text(card.get("card_id")).startswith("ATC:"):
        raise JudgmentExperienceError("existing_analogy_transfer_card_id_invalid")
    if card.get("source_case_id") not in (None, "", record.get("source_case_id")):
        raise JudgmentExperienceError("existing_analogy_transfer_card_source_conflicts_with_record")
    card["source_case_id"] = record["source_case_id"]
    card["settlement_rule"] = "DERIVE_FROM_PAIR_SIGNALS_ONLY"
    if _contains_forbidden_investment_field(card):
        raise JudgmentExperienceError("analogy_transfer_card_contains_forbidden_investment_field")
    projected = deepcopy(receipt)
    projected["projected_analogy_transfer_card_id"] = card["card_id"]
    validation = validate_experience_invocation_receipt(projected)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("projected invocation invalid")
    return projected, card


def build_experience_feedback_event(
    *, event_id: str, receipt: dict[str, Any], status: str, feedback_ref: str,
    review_ref: str, recorded_at: str, explanation: str, economic_failure_loci: list[str],
) -> dict[str, Any]:
    """Append a target outcome interpretation without rewriting its invocation."""
    receipt_validation = validate_experience_invocation_receipt(receipt)
    if receipt_validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("cannot record feedback for invalid invocation")
    if receipt.get("state") != "APPLIED_PREOUTCOME":
        raise JudgmentExperienceError("only_applied_preoutcome_invocation_may_receive_experience_feedback")
    if status not in FEEDBACK_STATUSES or not _text(event_id).startswith("EFE:"):
        raise JudgmentExperienceError("experience_feedback_identity_or_status_invalid")
    if _repository_path(feedback_ref) is None or _repository_path(review_ref) is None:
        raise JudgmentExperienceError("experience_feedback_requires_existing_settlement_and_independent_review_refs")
    if _parse_timestamp(recorded_at, "recorded_at") <= _parse_timestamp(receipt.get("frozen_at"), "receipt.frozen_at"):
        raise JudgmentExperienceError("experience_feedback_must_follow_preoutcome_freeze")
    if status == "MEASUREMENT_BLOCKED" and "MEASUREMENT" not in economic_failure_loci:
        raise JudgmentExperienceError("measurement_blocked_requires_measurement_locus")
    if status != "MEASUREMENT_BLOCKED" and "MEASUREMENT" in economic_failure_loci and len(economic_failure_loci) == 1:
        raise JudgmentExperienceError("measurement_locus_cannot_be_misreported_as_enterprise_failure")
    event = {
        "schema_version": EXPERIENCE_FEEDBACK_EVENT_SCHEMA,
        "event_id": event_id,
        "invocation_id": receipt["invocation_id"],
        "record_id": receipt["record_id"],
        "record_version": receipt["record_version"],
        "target_case_id": receipt["target_case_id"],
        "status": status,
        "feedback_ref": _text(feedback_ref),
        "review_ref": _text(review_ref),
        "recorded_at": recorded_at,
        "explanation": _text(explanation),
        "economic_failure_loci": list(economic_failure_loci),
    }
    validation = validate_experience_feedback_event(event)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("feedback event invalid: " + ", ".join(validation["findings"]))
    return event


def validate_experience_feedback_event(event: Any) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(event, dict):
        return _findings_result(["experience_feedback_event_not_object"])
    if event.get("schema_version") != EXPERIENCE_FEEDBACK_EVENT_SCHEMA:
        findings.append("schema_version_invalid")
    _required(event, ("event_id", "invocation_id", "record_id", "target_case_id", "status", "feedback_ref", "review_ref", "recorded_at", "explanation"), "", findings)
    if not _text(event.get("event_id")).startswith("EFE:"):
        findings.append("event_id_invalid")
    if event.get("status") not in FEEDBACK_STATUSES:
        findings.append("feedback_status_invalid")
    _iso_timestamp(event.get("recorded_at"), "recorded_at", findings)
    for field in ("feedback_ref", "review_ref"):
        if _repository_path(event.get(field)) is None:
            findings.append(field + "_missing_or_unreadable")
    loci = _text_list(event.get("economic_failure_loci"), "economic_failure_loci", findings)
    if any(item not in ECONOMIC_FAILURE_LOCI for item in loci):
        findings.append("economic_failure_locus_invalid")
    if event.get("status") == "MEASUREMENT_BLOCKED" and loci != ["MEASUREMENT"]:
        findings.append("measurement_blocked_must_remain_local")
    if _contains_forbidden_investment_field(event):
        findings.append("experience_feedback_cannot_write_investment_value")
    return _findings_result(findings)


def version_record_after_feedback(
    record: dict[str, Any], event: dict[str, Any], *, receipt: dict[str, Any], recorded_at: str,
    apply_when: list[str] | None = None, do_not_apply_when: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new source record version; the original object remains intact."""
    record_validation = validate_judgment_experience_record(record)
    event_validation = validate_experience_feedback_event(event)
    receipt_validation = validate_experience_invocation_receipt(receipt)
    if (
        record_validation["state"] != "REVIEWABLE"
        or event_validation["state"] != "REVIEWABLE"
        or receipt_validation["state"] != "REVIEWABLE"
    ):
        raise JudgmentExperienceError("cannot version invalid experience record or event")
    if receipt.get("state") != "APPLIED_PREOUTCOME":
        raise JudgmentExperienceError("only_applied_preoutcome_invocation_may_version_experience_record")
    if any(
        left != right for left, right in (
            (event.get("invocation_id"), receipt.get("invocation_id")),
            (event.get("record_id"), receipt.get("record_id")),
            (event.get("record_version"), receipt.get("record_version")),
            (event.get("target_case_id"), receipt.get("target_case_id")),
            (receipt.get("record_id"), record.get("record_id")),
            (receipt.get("record_version"), record.get("version")),
        )
    ):
        raise JudgmentExperienceError("feedback_event_receipt_record_binding_invalid")
    if _parse_timestamp(event.get("recorded_at"), "event.recorded_at") <= _parse_timestamp(receipt.get("frozen_at"), "receipt.frozen_at"):
        raise JudgmentExperienceError("feedback_event_precedes_or_equals_invocation_freeze")
    if event.get("record_id") != record.get("record_id") or event.get("record_version") != record.get("version"):
        raise JudgmentExperienceError("feedback_event_not_bound_to_record_version")
    next_record = deepcopy(record)
    next_record["version"] = int(record["version"]) + 1
    next_record["recorded_at"] = recorded_at
    next_record["feedback_event_refs"] = [*record.get("feedback_event_refs", []), event["event_id"]]
    if event["status"] in {"BOUNDARY_EXPOSED", "MISAPPLIED"}:
        next_record["status"] = "BOUNDED"
        if do_not_apply_when:
            next_record["do_not_apply_when"] = [*record["do_not_apply_when"], *do_not_apply_when]
    elif event["status"] == "RETIRED":
        next_record["status"] = "RETIRED"
    if apply_when:
        next_record["apply_when"] = list(apply_when)
    validation = validate_judgment_experience_record(next_record)
    if validation["state"] != "REVIEWABLE":
        raise JudgmentExperienceError("versioned record invalid: " + ", ".join(validation["findings"]))
    return next_record


def append_experience_feedback(
    registry: dict[str, Any], *, record: dict[str, Any], event: dict[str, Any], receipt: dict[str, Any], updated_record: dict[str, Any],
) -> dict[str, Any]:
    """Append a feedback event and a derived record version without mutation."""
    if registry.get("schema_version") != EXPERIENCE_REGISTRY_SCHEMA:
        raise JudgmentExperienceError("experience_registry_schema_invalid")
    records = registry.get("records")
    events = registry.get("feedback_events")
    if not isinstance(records, list) or not isinstance(events, list):
        raise JudgmentExperienceError("experience_registry_collections_invalid")
    receipts = registry.get("invocation_receipts", [])
    if not isinstance(receipts, list):
        raise JudgmentExperienceError("experience_registry_invocation_receipts_invalid")
    expected = version_record_after_feedback(record, event, receipt=receipt, recorded_at=updated_record.get("recorded_at"))
    if expected != updated_record:
        raise JudgmentExperienceError("updated_record_not_exact_feedback_derived_version")
    if any(item.get("event_id") == event.get("event_id") for item in events if isinstance(item, dict)):
        raise JudgmentExperienceError("experience_feedback_event_already_recorded")
    if any(
        item.get("record_id") == updated_record.get("record_id") and item.get("version") == updated_record.get("version")
        for item in records if isinstance(item, dict)
    ):
        raise JudgmentExperienceError("experience_record_version_already_recorded")
    if not any(item == record for item in records if isinstance(item, dict)):
        raise JudgmentExperienceError("original_record_not_preserved_in_registry")
    if any(item.get("invocation_id") == receipt.get("invocation_id") for item in receipts if isinstance(item, dict)):
        raise JudgmentExperienceError("experience_invocation_already_recorded")
    result = deepcopy(registry)
    result["records"].append(deepcopy(updated_record))
    result["feedback_events"].append(deepcopy(event))
    result.setdefault("invocation_receipts", []).append(deepcopy(receipt))
    return result


def validate_experience_registry(registry: Any) -> dict[str, Any]:
    """Validate the registry as a projection of immutable source references."""
    findings: list[str] = []
    if not isinstance(registry, dict):
        return _findings_result(["experience_registry_not_object"])
    if registry.get("schema_version") != EXPERIENCE_REGISTRY_SCHEMA:
        findings.append("experience_registry_schema_invalid")
    records = registry.get("records")
    events = registry.get("feedback_events")
    receipts = registry.get("invocation_receipts", [])
    if not isinstance(records, list):
        findings.append("experience_registry_records_not_list")
        records = []
    if not isinstance(events, list):
        findings.append("experience_registry_feedback_events_not_list")
        events = []
    if not isinstance(receipts, list):
        findings.append("experience_registry_invocation_receipts_not_list")
        receipts = []
    identities: set[tuple[str, int]] = set()
    for record in records:
        validation = validate_judgment_experience_record(record)
        findings.extend("record:" + item for item in validation["findings"])
        if isinstance(record, dict):
            identity = (_text(record.get("record_id")), record.get("version"))
            if identity in identities:
                findings.append("experience_registry_record_version_duplicate")
            identities.add(identity)
    records_by_identity = {
        (_text(record.get("record_id")), record.get("version")): record
        for record in records if isinstance(record, dict)
    }
    receipts_by_id: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        validation = validate_experience_invocation_receipt(receipt)
        findings.extend("receipt:" + item for item in validation["findings"])
        if isinstance(receipt, dict):
            invocation_id = _text(receipt.get("invocation_id"))
            if invocation_id in receipts_by_id:
                findings.append("experience_registry_invocation_duplicate")
            receipts_by_id[invocation_id] = receipt
    for event in events:
        validation = validate_experience_feedback_event(event)
        findings.extend("event:" + item for item in validation["findings"])
        if not isinstance(event, dict):
            continue
        receipt = receipts_by_id.get(_text(event.get("invocation_id")))
        original = records_by_identity.get((_text(event.get("record_id")), event.get("record_version")))
        if receipt is None or original is None:
            findings.append("experience_registry_feedback_missing_invocation_or_original_record")
            continue
        next_record = records_by_identity.get((_text(event.get("record_id")), int(event.get("record_version") or 0) + 1))
        if next_record is None:
            findings.append("experience_registry_feedback_next_record_missing")
            continue
        try:
            derived = version_record_after_feedback(original, event, receipt=receipt, recorded_at=next_record.get("recorded_at"))
        except JudgmentExperienceError as exc:
            findings.append("experience_registry_feedback_binding_invalid:" + str(exc))
        else:
            if derived != next_record:
                findings.append("experience_registry_feedback_next_record_not_derived")
    by_id: dict[str, list[int]] = {}
    for record_id, version in identities:
        by_id.setdefault(record_id, []).append(version)
    for record_id, versions in by_id.items():
        if sorted(versions) != list(range(1, max(versions) + 1)):
            findings.append("experience_registry_record_versions_not_contiguous:" + record_id)
    return _findings_result(findings)
