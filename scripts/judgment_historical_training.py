#!/usr/bin/env python3
"""Claim-specific historical-training admission and carrier-registry controls.

This module is intentionally below the V5 comparative-selection contract.  It
keeps industry history, evidence carriers, teaching/lifecycle cases, and a
future comparative panel distinct, so a small or discontinuous cohort can
still teach without acquiring selection-learning permissions.

It is pure and offline: it neither opens a database nor reads a source,
outcome, H2 action screen, V5 freeze, R-103, or a report.  The existing V5
validator remains the only canonical admission for a comparative freeze.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
import re
from typing import Any


SCHEMA_VERSION = "turtle-historical-training-control.v1"
UNIVERSE_SCHEMA_VERSION = "turtle-industry-history-universe.v1"
LIFECYCLE_SCHEMA_VERSION = "turtle-lifecycle-event.v1"
CARRIER_REGISTRY_SCHEMA_VERSION = "turtle-evidence-carrier-registry.v1"
ADMISSION_SCHEMA_VERSION = "turtle-claim-specific-admission.v1"
HISTORY_SERIES_SCHEMA_VERSION = "turtle-industry-history-series.v1"
TEACHING_CASE_SCHEMA_VERSION = "turtle-lifecycle-teaching-case.v1"
BOUNDARY_TEACHING_CASE_SCHEMA_VERSION = "turtle-boundary-teaching-case.v1"

OBJECT_CLASSES = {
    "INDUSTRY_UNIVERSE",
    "EVIDENCE_CARRIER",
    "TEACHING_CASE",
    "LIFECYCLE_CASE",
    "COMPARATIVE_EPISODE",
    "LEARNING_EPISODE",
}
CLAIM_CLASSES = {
    "DESCRIPTIVE_STRUCTURE",
    "WITHIN_CASE_MECHANISM",
    "LIFECYCLE_TRANSITION",
    "RELATIVE_CAUSAL",
    "METHOD_GENERALIZATION",
    "INVESTMENT_DECISION_UTILITY",
}
OBSERVATION_STATUSES = {
    "OBSERVED",
    "CENSORED",
    "COMPETING_EVENT_OBSERVED",
    "UNKNOWN",
    "NOT_DIAGNOSTIC",
    "MEASUREMENT_MISMATCH",
}
LIFECYCLE_EVENT_TYPES = {
    "SURVIVED",
    "ACQUIRED",
    "MERGED_OR_PERIMETER_TRANSFERRED",
    "DELISTED_BUT_OPERATING",
    "BANKRUPTCY_FILED",
    "REORGANIZING",
    "EMERGED_FROM_REORGANIZATION",
    "RESTRUCTURING_FAILED",
    "LIQUIDATED",
    "EXITED_BUSINESS",
    "DATA_CENSORED",
    "PERIMETER_CONTINUITY_UNRESOLVED",
}
ABSORBING_SUBJECTS = {
    "LISTED_SECURITY",
    "INDEPENDENT_CONTROL",
    "ECONOMIC_ENTITY",
    "REPORTING_PERIMETER",
    "OPERATING_BUSINESS",
}
IDENTITY_KINDS = {
    "ECONOMIC_ENTITY",
    "LEGAL_ENTITY",
    "LISTED_SECURITY",
    "REPORTING_PERIMETER",
    "SUCCESSOR_ENTITY",
}
COVERAGE_STATUSES = {"ENUMERATED", "BOUNDED_PARTIAL", "UNKNOWN_COVERAGE"}
RISK_STATUSES = {"IN_RISK_SET", "EXITED", "CENSORED", "UNKNOWN"}
INFORMATION_ROLES = {"CUTOFF_VISIBLE", "POST_CUTOFF_CONTEXT", "OUTCOME"}
TEACHING_OUTCOME_KNOWLEDGE_ROLES = {"HISTORICAL_OUTCOME_KNOWN", "OUTCOME_NOT_YET_KNOWN"}
LIFECYCLE_SOURCE_TYPES = {
    "OFFICIAL_AUDITED_ANNUAL_REPORT",
    "OFFICIAL_COMPANY_DISCLOSURE",
    "OFFICIAL_EXCHANGE_DISCLOSURE",
}
REGISTRY_STATES = {"OPEN", "FROZEN"}
CARRIER_DISPOSITIONS = {
    "PENDING_ACTION_WINDOW_REVIEW",
    "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK",
    "ELIGIBLE_FOR_COMPARATIVE",
    "EXCLUDED_BY_ELIGIBILITY_PREDICATE",
}
GEOGRAPHY_REQUIREMENTS = {
    "REQUIRED_EQUAL",
    "REQUIRED_OVERLAP",
    "REQUIRED_EXPOSURE",
    "NOT_REQUIRED",
}

_RESTRICTED_OUTPUTS = {
    "SELECTION_METHOD_ELIGIBLE",
    "METHOD_FREEZE",
    "HOLDOUT_RELEASE",
    "REPORT_USE_AUTHORIZED",
    "INVESTMENT_INPUT",
}
_ALLOWED_OUTPUTS = {
    ("INDUSTRY_UNIVERSE", "DESCRIPTIVE_STRUCTURE"): {
        "INDUSTRY_CONTEXT", "RESEARCH_AGENDA",
    },
    ("EVIDENCE_CARRIER", "DESCRIPTIVE_STRUCTURE"): {"EVIDENCE_CARRIER_ONLY"},
    ("EVIDENCE_CARRIER", "WITHIN_CASE_MECHANISM"): {"EVIDENCE_CARRIER_ONLY", "RESEARCH_AGENDA"},
    ("EVIDENCE_CARRIER", "LIFECYCLE_TRANSITION"): {"EVIDENCE_CARRIER_ONLY", "LIFECYCLE_ONLY"},
    ("EVIDENCE_CARRIER", "RELATIVE_CAUSAL"): {"COMPARATIVE_INTAKE_ONLY"},
    ("TEACHING_CASE", "WITHIN_CASE_MECHANISM"): {
        "TEACHING_ONLY", "BOUNDARY_ASSET", "RESEARCH_AGENDA",
    },
    ("LIFECYCLE_CASE", "LIFECYCLE_TRANSITION"): {
        "LIFECYCLE_ONLY", "PERMANENT_LOSS_PATTERN", "RESEARCH_AGENDA",
    },
    ("COMPARATIVE_EPISODE", "RELATIVE_CAUSAL"): {"COMPARATIVE_SETTLEMENT_CANDIDATE"},
    ("LEARNING_EPISODE", "METHOD_GENERALIZATION"): {"METHOD_CANDIDATE"},
    ("LEARNING_EPISODE", "INVESTMENT_DECISION_UTILITY"): {
        "REPORT_A_B_EVALUATION_ONLY", "BUY_POINT_EVALUATION_ONLY",
    },
}

_UNIVERSE_KEYS = {
    "schema_version", "universe_id", "industry_id", "cutoff_at", "coverage_status",
    "competitive_arena", "membership_rule", "object_class", "claim_class", "allowed_outputs",
    "members", "source_packet_refs",
}
_UNIVERSE_MEMBER_KEYS = {
    "subject_id", "company_id", "issuer_id", "control_group_id", "responsibility_unit_id",
    "perimeter_id", "observation_entry_at", "risk_start_at", "risk_status", "coverage_status",
    "source_packet_refs",
}
_HISTORY_SERIES_KEYS = {
    "schema_version", "series_id", "industry_id", "h1_receipt_ref", "cutoffs",
    "snapshots", "lifecycle_events",
}
_TEACHING_CASE_KEYS = {
    "schema_version", "teaching_case_id", "subject_id", "lifecycle_event", "source_packet_refs",
    "teaching_question", "mechanism_hypothesis", "prohibited_substitutes", "outcome_knowledge_role",
    "object_class", "claim_class", "allowed_outputs",
}
_BOUNDARY_TEACHING_CASE_KEYS = {
    "schema_version", "teaching_case_id", "case_id", "freeze_id", "settlement_id", "subject_id",
    "source_artifact_refs", "teaching_question", "mechanism_hypothesis",
    "prohibited_substitutes", "boundary_disposition", "object_class", "claim_class", "allowed_outputs",
}
_BOUNDARY_ARTIFACT_REF_KEYS = {"role", "artifact_ref"}
_ARENA_KEYS = {"competitive_arena_id", "geography_requirement"}
_LIFECYCLE_KEYS = {
    "schema_version", "lifecycle_event_id", "subject_id", "event_type", "effective_at", "known_at",
    "source_available_at", "source", "information_role", "observation_status", "absorbing_for",
    "successor_subject_id", "identity_mappings", "time_origin", "observation_entry_at",
    "risk_start_at", "interval_start", "interval_stop", "covariate_as_of", "object_class",
    "claim_class", "allowed_outputs",
}
_LIFECYCLE_SOURCE_KEYS = {"source_id", "source_type", "url", "published_at", "field_ref", "source_subject_id"}
_IDENTITY_MAPPING_KEYS = {"identity_kind", "identity_id", "effective_from", "effective_through"}
_REGISTRY_KEYS = {
    "schema_version", "registry_id", "universe_id", "industry_id", "competitive_arena_id",
    "mechanism_topology", "state", "object_class", "claim_class", "allowed_outputs",
    "seed_receipt_refs", "peer_recruitment_predicate", "static_peer_batches", "carriers",
}
_CARRIER_KEYS = {
    "carrier_id", "batch_id", "company_id", "issuer_id", "control_group_id",
    "responsibility_unit_id", "perimeter_id", "unit", "disposition", "source_packet_ref",
    "static_source_ids", "eligibility_predicate_id", "seed_disposition",
}
_PREDICATE_KEYS = {
    "predicate_id", "frozen_at", "action_screen_receipt_ref", "mechanism_topology",
    "competitive_arena_id", "source_cutoff_at", "selection_rule", "requires_independent_control",
    "excludes_break_dispositions", "outcome_access_prohibited", "peer_recruitment_population",
}
_BATCH_KEYS = {
    "schema_version", "batch_id", "source_packet_ref", "eligibility_predicate_id", "received_at", "curator_id",
    "static_sources", "carrier_static_coverage", "eligibility_population", "carriers",
}
_STATIC_SOURCE_KEYS = {
    "source_id", "url", "published_at", "source_type", "issuer_id", "responsibility_unit_id",
    "perimeter_id", "unit", "period_end", "field_refs",
}
_CARRIER_STATIC_COVERAGE_KEYS = {"carrier_id", "period_end", "field_id", "source_id", "field_ref"}
_ELIGIBILITY_ROSTER_KEYS = {
    "company_id", "issuer_id", "control_group_id", "responsibility_unit_id", "perimeter_id", "unit",
    "eligibility_decision", "exclusion_reason",
}
_ADMISSION_KEYS = {
    "schema_version", "artifact_id", "object_class", "claim_class", "allowed_outputs",
    "registry_id", "target_company_id", "comparator_company_ids",
}
_PAGE_REFERENCE = re.compile(r"(?:\bp(?:age)?\.?\s*\d+|第\s*\d+\s*页)", re.IGNORECASE)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _result(findings: list[str], **payload: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not findings,
        "findings": findings,
        **payload,
    }


def _closed(mapping: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    result = _mapping(mapping)
    if not result:
        findings.append(f"{path}_must_be_object")
        return {}
    for key in sorted(set(result).difference(allowed)):
        findings.append(f"{path}_contains_unapproved_field:{key}")
    return result


def _require_text(mapping: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = mapping.get(field)
    if not _text(value):
        findings.append(f"{path}.{field}_required")
        return ""
    return str(value)


def _parse_time(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        findings.append(f"{path}_timezone_aware_iso8601_required")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        findings.append(f"{path}_timezone_aware_iso8601_required")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        findings.append(f"{path}_timezone_aware_iso8601_required")
        return None
    return parsed


def _validate_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any]:
    reference = _mapping(value)
    if not _text(reference.get("receipt_id")):
        findings.append(f"{path}.receipt_id_required")
    version = reference.get("receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.receipt_version_positive_integer_required")
    return reference


def _validate_static_source(
    value: Any, *, path: str, source_cutoff: datetime | None, findings: list[str],
) -> dict[str, Any]:
    source = _closed(value, _STATIC_SOURCE_KEYS, path, findings)
    for field in ("source_id", "url", "issuer_id", "responsibility_unit_id", "perimeter_id", "unit", "period_end"):
        _require_text(source, field, path, findings)
    url = source.get("url")
    if not (_text(url) and str(url).startswith("https://static.cninfo.com.cn/finalpage/") and str(url).endswith(".PDF")):
        findings.append(f"{path}.url_must_be_static_cninfo_finalpage_pdf")
    published_at = _parse_time(source.get("published_at"), f"{path}.published_at", findings)
    if source_cutoff and published_at and published_at >= source_cutoff:
        findings.append(f"{path}.published_at_must_be_strictly_before_predicate_cutoff")
    if source.get("source_type") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
        findings.append(f"{path}.source_type_must_be_official_audited_annual_report")
    try:
        date.fromisoformat(str(source.get("period_end")))
    except (TypeError, ValueError):
        findings.append(f"{path}.period_end_must_be_iso_date")
    field_refs = source.get("field_refs")
    if not isinstance(field_refs, list) or not field_refs or not all(_text(item) and _PAGE_REFERENCE.search(str(item)) for item in field_refs):
        findings.append(f"{path}.field_refs_must_be_nonempty_paged_pdf_references")
    return source


def _validate_admission_fields(
    artifact: dict[str, Any], *, path: str, findings: list[str],
) -> tuple[str, str, set[str]]:
    object_class = _require_text(artifact, "object_class", path, findings)
    claim_class = _require_text(artifact, "claim_class", path, findings)
    if object_class and object_class not in OBJECT_CLASSES:
        findings.append(f"{path}.object_class_invalid")
    if claim_class and claim_class not in CLAIM_CLASSES:
        findings.append(f"{path}.claim_class_invalid")

    raw_outputs = artifact.get("allowed_outputs")
    if not isinstance(raw_outputs, list) or not raw_outputs or not all(_text(item) for item in raw_outputs):
        findings.append(f"{path}.allowed_outputs_nonempty_text_list_required")
        outputs: set[str] = set()
    else:
        outputs = {str(item) for item in raw_outputs}
        if len(outputs) != len(raw_outputs):
            findings.append(f"{path}.allowed_outputs_must_not_repeat")
    permitted = _ALLOWED_OUTPUTS.get((object_class, claim_class), set())
    if object_class and claim_class and not permitted:
        findings.append(f"{path}.object_claim_pair_not_admitted")
    if outputs.difference(permitted):
        findings.append(f"{path}.allowed_outputs_not_permitted_for_claim")
    if outputs.intersection(_RESTRICTED_OUTPUTS):
        findings.append(f"{path}.allowed_outputs_cannot_grant_method_or_report_authority")
    return object_class, claim_class, outputs


def validate_industry_history_universe_snapshot(snapshot: Any) -> dict[str, Any]:
    """Validate a bounded company×cutoff history universe, not a peer panel."""
    findings: list[str] = []
    universe = _closed(snapshot, _UNIVERSE_KEYS, "universe", findings)
    if universe.get("schema_version") != UNIVERSE_SCHEMA_VERSION:
        findings.append("universe.schema_version_invalid")
    _require_text(universe, "universe_id", "universe", findings)
    _require_text(universe, "industry_id", "universe", findings)
    cutoff_at = _parse_time(universe.get("cutoff_at"), "universe.cutoff_at", findings)
    coverage_status = universe.get("coverage_status")
    if coverage_status not in COVERAGE_STATUSES:
        findings.append("universe.coverage_status_invalid")
    _require_text(universe, "membership_rule", "universe", findings)
    object_class, claim_class, _ = _validate_admission_fields(universe, path="universe", findings=findings)
    if object_class != "INDUSTRY_UNIVERSE":
        findings.append("universe.object_class_must_be_industry_universe")
    if claim_class != "DESCRIPTIVE_STRUCTURE":
        findings.append("universe.claim_class_must_be_descriptive_structure")

    arena = _closed(universe.get("competitive_arena"), _ARENA_KEYS, "universe.competitive_arena", findings)
    _require_text(arena, "competitive_arena_id", "universe.competitive_arena", findings)
    if arena.get("geography_requirement") not in GEOGRAPHY_REQUIREMENTS:
        findings.append("universe.competitive_arena.geography_requirement_invalid")

    references = _list(universe.get("source_packet_refs"))
    if not references:
        findings.append("universe.source_packet_refs_nonempty_list_required")
    for index, reference in enumerate(references):
        _validate_reference(reference, f"universe.source_packet_refs[{index}]", findings)

    seen_subjects: set[str] = set()
    members = _list(universe.get("members"))
    if not members:
        findings.append("universe.members_nonempty_list_required")
    for index, value in enumerate(members):
        path = f"universe.members[{index}]"
        member = _closed(value, _UNIVERSE_MEMBER_KEYS, path, findings)
        subject_id = _require_text(member, "subject_id", path, findings)
        for field in ("company_id", "issuer_id", "control_group_id", "responsibility_unit_id", "perimeter_id"):
            _require_text(member, field, path, findings)
        if subject_id and subject_id in seen_subjects:
            findings.append("universe.members.subject_id_must_not_repeat")
        seen_subjects.add(subject_id)
        observation_entry = _parse_time(member.get("observation_entry_at"), f"{path}.observation_entry_at", findings)
        risk_start = _parse_time(member.get("risk_start_at"), f"{path}.risk_start_at", findings)
        if observation_entry and risk_start and risk_start < observation_entry:
            findings.append(f"{path}.risk_start_at_cannot_precede_observation_entry_at")
        if risk_start and cutoff_at and risk_start > cutoff_at:
            findings.append(f"{path}.risk_start_at_cannot_follow_universe_cutoff")
        if member.get("risk_status") not in RISK_STATUSES:
            findings.append(f"{path}.risk_status_invalid")
        if member.get("coverage_status") not in COVERAGE_STATUSES:
            findings.append(f"{path}.coverage_status_invalid")
        member_refs = _list(member.get("source_packet_refs"))
        if not member_refs:
            findings.append(f"{path}.source_packet_refs_nonempty_list_required")
        for ref_index, reference in enumerate(member_refs):
            _validate_reference(reference, f"{path}.source_packet_refs[{ref_index}]", findings)
    return _result(findings)


def validate_lifecycle_event(event: Any, *, pit_cutoff_at: str | None = None) -> dict[str, Any]:
    """Validate lifecycle clocks without treating exit or censoring as a loss."""
    findings: list[str] = []
    lifecycle = _closed(event, _LIFECYCLE_KEYS, "lifecycle", findings)
    if lifecycle.get("schema_version") != LIFECYCLE_SCHEMA_VERSION:
        findings.append("lifecycle.schema_version_invalid")
    _require_text(lifecycle, "lifecycle_event_id", "lifecycle", findings)
    _require_text(lifecycle, "subject_id", "lifecycle", findings)
    if lifecycle.get("event_type") not in LIFECYCLE_EVENT_TYPES:
        findings.append("lifecycle.event_type_invalid")
    effective_at = _parse_time(lifecycle.get("effective_at"), "lifecycle.effective_at", findings)
    known_at = _parse_time(lifecycle.get("known_at"), "lifecycle.known_at", findings)
    source_available_at = _parse_time(lifecycle.get("source_available_at"), "lifecycle.source_available_at", findings)
    source = _closed(lifecycle.get("source"), _LIFECYCLE_SOURCE_KEYS, "lifecycle.source", findings)
    _require_text(source, "source_id", "lifecycle.source", findings)
    if source.get("source_type") not in LIFECYCLE_SOURCE_TYPES:
        findings.append("lifecycle.source.source_type_must_be_official")
    url = source.get("url")
    if not (_text(url) and str(url).startswith("https://static.cninfo.com.cn/finalpage/") and str(url).endswith(".PDF")):
        findings.append("lifecycle.source.url_must_be_static_cninfo_finalpage_pdf")
    published_at = _parse_time(source.get("published_at"), "lifecycle.source.published_at", findings)
    field_ref = _require_text(source, "field_ref", "lifecycle.source", findings)
    if field_ref and not _PAGE_REFERENCE.search(field_ref):
        findings.append("lifecycle.source.field_ref_must_be_paged_pdf_reference")
    if source.get("source_subject_id") != lifecycle.get("subject_id"):
        findings.append("lifecycle.source.source_subject_id_must_match_lifecycle_subject")
    if source_available_at and published_at and source_available_at != published_at:
        findings.append("lifecycle.source.published_at_must_match_source_available_at")
    if effective_at and known_at and known_at < effective_at:
        findings.append("lifecycle.known_at_cannot_precede_effective_at")
    if lifecycle.get("information_role") not in INFORMATION_ROLES:
        findings.append("lifecycle.information_role_invalid")
    if lifecycle.get("observation_status") not in OBSERVATION_STATUSES:
        findings.append("lifecycle.observation_status_invalid")
    if lifecycle.get("event_type") == "DATA_CENSORED" and lifecycle.get("observation_status") != "CENSORED":
        findings.append("lifecycle.data_censored_event_must_have_censored_observation_status")
    absorbing_for = _list(lifecycle.get("absorbing_for"))
    if not all(item in ABSORBING_SUBJECTS for item in absorbing_for):
        findings.append("lifecycle.absorbing_for_nonempty_valid_list_required")
    if lifecycle.get("event_type") == "PERIMETER_CONTINUITY_UNRESOLVED":
        if absorbing_for:
            findings.append("lifecycle.perimeter_continuity_unresolved_cannot_claim_absorbing_exit")
    elif not absorbing_for:
        findings.append("lifecycle.absorbing_for_nonempty_valid_list_required")
    if len(set(absorbing_for)) != len(absorbing_for):
        findings.append("lifecycle.absorbing_for_must_not_repeat")
    if lifecycle.get("successor_subject_id") is not None and not _text(lifecycle.get("successor_subject_id")):
        findings.append("lifecycle.successor_subject_id_must_be_text_when_present")
    identity_mappings = _list(lifecycle.get("identity_mappings"))
    identity_kinds: set[str] = set()
    if not identity_mappings:
        findings.append("lifecycle.identity_mappings_nonempty_list_required")
    for index, mapping_value in enumerate(identity_mappings):
        path = f"lifecycle.identity_mappings[{index}]"
        mapping = _closed(mapping_value, _IDENTITY_MAPPING_KEYS, path, findings)
        identity_kind = mapping.get("identity_kind")
        if identity_kind not in IDENTITY_KINDS:
            findings.append(f"{path}.identity_kind_invalid")
        elif identity_kind in identity_kinds:
            findings.append("lifecycle.identity_mappings.identity_kind_must_not_repeat")
        identity_kinds.add(str(identity_kind))
        _require_text(mapping, "identity_id", path, findings)
        effective_from = _parse_time(mapping.get("effective_from"), f"{path}.effective_from", findings)
        effective_through = _parse_time(mapping.get("effective_through"), f"{path}.effective_through", findings)
        if effective_from and effective_through and effective_through < effective_from:
            findings.append(f"{path}.effective_through_cannot_precede_effective_from")
    if not {"ECONOMIC_ENTITY", "LEGAL_ENTITY", "LISTED_SECURITY", "REPORTING_PERIMETER"}.issubset(identity_kinds):
        findings.append("lifecycle.identity_mappings_must_separate_entity_security_and_perimeter")
    time_origin = _parse_time(lifecycle.get("time_origin"), "lifecycle.time_origin", findings)
    observation_entry = _parse_time(lifecycle.get("observation_entry_at"), "lifecycle.observation_entry_at", findings)
    risk_start = _parse_time(lifecycle.get("risk_start_at"), "lifecycle.risk_start_at", findings)
    interval_start = _parse_time(lifecycle.get("interval_start"), "lifecycle.interval_start", findings)
    interval_stop = _parse_time(lifecycle.get("interval_stop"), "lifecycle.interval_stop", findings)
    covariate_as_of = _parse_time(lifecycle.get("covariate_as_of"), "lifecycle.covariate_as_of", findings)
    if time_origin and observation_entry and observation_entry < time_origin:
        findings.append("lifecycle.observation_entry_at_cannot_precede_time_origin")
    if observation_entry and risk_start and risk_start < observation_entry:
        findings.append("lifecycle.risk_start_at_cannot_precede_observation_entry_at")
    if risk_start and interval_start and interval_start < risk_start:
        findings.append("lifecycle.interval_start_cannot_precede_risk_start_at")
    if interval_start and interval_stop and interval_stop < interval_start:
        findings.append("lifecycle.interval_stop_cannot_precede_interval_start")
    if covariate_as_of and interval_start and covariate_as_of > interval_start:
        findings.append("lifecycle.covariate_as_of_cannot_follow_interval_start")
    object_class, claim_class, _ = _validate_admission_fields(lifecycle, path="lifecycle", findings=findings)
    if object_class != "LIFECYCLE_CASE":
        findings.append("lifecycle.object_class_must_be_lifecycle_case")
    if claim_class != "LIFECYCLE_TRANSITION":
        findings.append("lifecycle.claim_class_must_be_lifecycle_transition")
    cutoff_at = _parse_time(pit_cutoff_at, "lifecycle.pit_cutoff_at", findings) if pit_cutoff_at else None
    if lifecycle.get("information_role") == "CUTOFF_VISIBLE" and cutoff_at and source_available_at and source_available_at > cutoff_at:
        findings.append("lifecycle.cutoff_visible_source_cannot_follow_pit_cutoff")
    return _result(findings)


def admit_lifecycle_teaching_case(case: Any) -> dict[str, Any]:
    """Admit one traceable lifecycle case as teaching-only historical material.

    Historical outcomes are permitted here precisely because this object cannot
    enter a comparative panel, method freeze, holdout, report authorization, or
    investment input.  It records a reusable question and prohibited shortcut,
    not a directional lesson about another company.
    """
    findings: list[str] = []
    artifact = _closed(case, _TEACHING_CASE_KEYS, "teaching_case", findings)
    if artifact.get("schema_version") != TEACHING_CASE_SCHEMA_VERSION:
        findings.append("teaching_case.schema_version_invalid")
    _require_text(artifact, "teaching_case_id", "teaching_case", findings)
    subject_id = _require_text(artifact, "subject_id", "teaching_case", findings)
    _require_text(artifact, "teaching_question", "teaching_case", findings)
    _require_text(artifact, "mechanism_hypothesis", "teaching_case", findings)
    prohibited = artifact.get("prohibited_substitutes")
    if not isinstance(prohibited, list) or not prohibited or not all(_text(item) for item in prohibited):
        findings.append("teaching_case.prohibited_substitutes_nonempty_text_list_required")
    elif len(set(prohibited)) != len(prohibited):
        findings.append("teaching_case.prohibited_substitutes_must_not_repeat")
    if artifact.get("outcome_knowledge_role") not in TEACHING_OUTCOME_KNOWLEDGE_ROLES:
        findings.append("teaching_case.outcome_knowledge_role_invalid")

    references = _list(artifact.get("source_packet_refs"))
    if not references:
        findings.append("teaching_case.source_packet_refs_nonempty_list_required")
    for index, reference in enumerate(references):
        _validate_reference(reference, f"teaching_case.source_packet_refs[{index}]", findings)

    lifecycle = artifact.get("lifecycle_event")
    lifecycle_validation = validate_lifecycle_event(lifecycle)
    findings.extend(f"teaching_case.lifecycle_event.{item}" for item in lifecycle_validation["findings"])
    if isinstance(lifecycle, dict) and lifecycle.get("subject_id") != subject_id:
        findings.append("teaching_case.lifecycle_event.subject_id_must_match_case")

    object_class, claim_class, _ = _validate_admission_fields(artifact, path="teaching_case", findings=findings)
    if object_class != "TEACHING_CASE":
        findings.append("teaching_case.object_class_must_be_teaching_case")
    if claim_class != "WITHIN_CASE_MECHANISM":
        findings.append("teaching_case.claim_class_must_be_within_case_mechanism")
    return _result(findings, teaching_case=deepcopy(artifact) if not findings else None)


def project_mixed_boundary_episode_to_teaching_case(
    frozen_case: Any,
    independent_post_outcome_review: Any,
    boundary_note: Any,
    *,
    teaching_case_id: str,
    source_artifact_refs: list[dict[str, str]],
) -> dict[str, Any]:
    """Project a settled MIXED episode into a non-directional boundary asset.

    The projection deliberately requires the independent post-outcome review
    and its no-learning disposition.  It retains references and prohibitions,
    never outcome values, target prices, or a reusable winner claim.
    """
    findings: list[str] = []
    frozen = _mapping(frozen_case)
    review = _mapping(independent_post_outcome_review)
    note = _mapping(boundary_note)
    case_id = _require_text(frozen, "case_id", "frozen_case", findings)
    freeze_id = _require_text(frozen, "freeze_id", "frozen_case", findings)
    company_id = _require_text(frozen, "company_id", "frozen_case", findings)
    if review.get("schema_version") != "judgment-selection-post-outcome-review.v1":
        findings.append("boundary_review.schema_version_invalid")
    if review.get("review_status") != "INDEPENDENTLY_ACCEPTED_POST_OUTCOME":
        findings.append("boundary_review.must_be_independently_accepted_post_outcome")
    if review.get("case_id") != case_id or review.get("freeze_id") != freeze_id:
        findings.append("boundary_review.case_or_freeze_must_match_frozen_case")
    settlement_id = _require_text(review, "settlement_id", "boundary_review", findings)
    if review.get("joint_selection_verdict") != "MIXED" or review.get("review_verdict") != "MIXED_MECHANISM_BOUNDARY":
        findings.append("boundary_review.must_be_mixed_mechanism_boundary")
    if review.get("learning_authorization") != "NONE":
        findings.append("boundary_review.learning_authorization_must_be_none")
    if note.get("schema_version") != "judgment-learning-note.v2":
        findings.append("boundary_note.schema_version_invalid")
    if any(note.get(field) != expected for field, expected in (
        ("case_id", case_id), ("freeze_id", freeze_id), ("settlement_id", settlement_id),
        ("diagnosis_scope", "MIXED_MECHANISM_BOUNDARY"),
    )):
        findings.append("boundary_note.must_match_mixed_boundary_review")
    if note.get("permitted_change_targets") != []:
        findings.append("boundary_note.cannot_authorize_method_change")
    prohibited_rights = set(_list(note.get("prohibited_rights")))
    if not {"DIRECTIONAL_SELECTION_LEARNING", "METHOD_FREEZE", "HOLDOUT_RELEASE", "REPORT_USE"}.issubset(prohibited_rights):
        findings.append("boundary_note.prohibited_rights_incomplete")

    roles: set[str] = set()
    for index, raw_ref in enumerate(_list(source_artifact_refs)):
        path = f"boundary_teaching_case.source_artifact_refs[{index}]"
        artifact_ref = _closed(raw_ref, _BOUNDARY_ARTIFACT_REF_KEYS, path, findings)
        role = _require_text(artifact_ref, "role", path, findings)
        _require_text(artifact_ref, "artifact_ref", path, findings)
        roles.add(role)
    if roles != {"FROZEN_CASE", "INDEPENDENT_POST_OUTCOME_REVIEW", "BOUNDARY_NOTE"}:
        findings.append("boundary_teaching_case.source_artifact_refs_must_bind_case_review_and_note")
    if findings:
        return _result(findings)

    artifact = {
        "schema_version": BOUNDARY_TEACHING_CASE_SCHEMA_VERSION,
        "teaching_case_id": teaching_case_id,
        "case_id": case_id,
        "freeze_id": freeze_id,
        "settlement_id": settlement_id,
        "subject_id": f"ECONOMIC_ENTITY:{company_id}",
        "source_artifact_refs": deepcopy(source_artifact_refs),
        "teaching_question": "Does an observed operating improvement transmit to same-period owner cash at the frozen responsibility boundary?",
        "mechanism_hypothesis": str(note.get("learning_basis")),
        "prohibited_substitutes": deepcopy(_list(review.get("prohibited_assumptions"))),
        "boundary_disposition": "MIXED_MECHANISM_BOUNDARY",
        "object_class": "TEACHING_CASE",
        "claim_class": "WITHIN_CASE_MECHANISM",
        "allowed_outputs": ["TEACHING_ONLY", "BOUNDARY_ASSET", "RESEARCH_AGENDA"],
    }
    return _result([], teaching_case=artifact)


def validate_industry_history_series(series: Any) -> dict[str, Any]:
    """Validate a sequence of bounded universe snapshots and lifecycle facts.

    This is deliberately an industry-history artifact: it can describe who was
    observable at a cutoff and whether later observation was censored, but it
    never grants comparative, learning, report, or investment permissions.
    """
    findings: list[str] = []
    artifact = _closed(series, _HISTORY_SERIES_KEYS, "history_series", findings)
    if artifact.get("schema_version") != HISTORY_SERIES_SCHEMA_VERSION:
        findings.append("history_series.schema_version_invalid")
    _require_text(artifact, "series_id", "history_series", findings)
    _require_text(artifact, "industry_id", "history_series", findings)
    receipt_ref = _validate_reference(artifact.get("h1_receipt_ref"), "history_series.h1_receipt_ref", findings)

    cutoffs_raw = _list(artifact.get("cutoffs"))
    if not cutoffs_raw or not all(_text(item) for item in cutoffs_raw):
        findings.append("history_series.cutoffs_nonempty_timezone_aware_list_required")
    cutoffs: list[datetime] = []
    for index, value in enumerate(cutoffs_raw):
        parsed = _parse_time(value, f"history_series.cutoffs[{index}]", findings)
        if parsed is not None:
            cutoffs.append(parsed)
    if len(cutoffs) == len(cutoffs_raw):
        if any(later <= earlier for earlier, later in zip(cutoffs, cutoffs[1:])):
            findings.append("history_series.cutoffs_must_be_strictly_increasing")

    snapshots = _list(artifact.get("snapshots"))
    if len(snapshots) != len(cutoffs_raw) or not snapshots:
        findings.append("history_series.snapshots_must_match_cutoff_count")
    known_subjects: set[str] = set()
    for index, snapshot_value in enumerate(snapshots):
        validation = validate_industry_history_universe_snapshot(snapshot_value)
        findings.extend(f"history_series.snapshots[{index}].{item}" for item in validation["findings"])
        snapshot = _mapping(snapshot_value)
        if index < len(cutoffs_raw) and snapshot.get("cutoff_at") != cutoffs_raw[index]:
            findings.append(f"history_series.snapshots[{index}].cutoff_at_must_match_series_cutoff")
        if snapshot.get("industry_id") != artifact.get("industry_id"):
            findings.append(f"history_series.snapshots[{index}].industry_id_must_match_series")
        if receipt_ref and receipt_ref not in _list(snapshot.get("source_packet_refs")):
            findings.append(f"history_series.snapshots[{index}].must_reference_h1_receipt")
        known_subjects.update(str(_mapping(member).get("subject_id") or "") for member in _list(snapshot.get("members")))

    seen_event_ids: set[str] = set()
    for index, event_value in enumerate(_list(artifact.get("lifecycle_events"))):
        validation = validate_lifecycle_event(event_value)
        findings.extend(f"history_series.lifecycle_events[{index}].{item}" for item in validation["findings"])
        event = _mapping(event_value)
        event_id = str(event.get("lifecycle_event_id") or "")
        if event_id and event_id in seen_event_ids:
            findings.append("history_series.lifecycle_events.lifecycle_event_id_must_not_repeat")
        seen_event_ids.add(event_id)
        if str(event.get("subject_id") or "") not in known_subjects:
            findings.append(f"history_series.lifecycle_events[{index}].subject_must_belong_to_h1_universe")
    return _result(findings)


def _h1_source_publication_date(source: dict[str, Any], *, path: str, findings: list[str]) -> date | None:
    """Parse H1's date-granular annual-report publication timestamp.

    A static H1 receipt does not claim an intraday publication time.  The
    multi-cutoff runner therefore begins observation on the following local
    calendar day; it never assumes a same-day source was known at a cutoff.
    """
    value = source.get("published_at")
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        findings.append(f"{path}.published_at_must_be_iso_date")
        return None


def _risk_status_at_cutoff(
    events: list[dict[str, Any]], *, subject_id: str, cutoff_at: datetime,
) -> str:
    """Apply only facts visible by this cutoff; outcome/context never backfill."""
    status = "IN_RISK_SET"
    terminal = False
    visible: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for event in events:
        if event.get("subject_id") != subject_id or event.get("information_role") != "CUTOFF_VISIBLE":
            continue
        effective_at = _parse_time(event.get("effective_at"), "history_series.lifecycle_event.effective_at", [])
        source_at = _parse_time(event.get("source_available_at"), "history_series.lifecycle_event.source_available_at", [])
        if effective_at is None or source_at is None or source_at > cutoff_at or effective_at > cutoff_at:
            continue
        visible.append((effective_at, source_at, event))
    for _, _, event in sorted(visible, key=lambda row: (row[0], row[1], str(row[2].get("lifecycle_event_id") or ""))):
        observation_status = event.get("observation_status")
        if observation_status == "CENSORED":
            status = "CENSORED"
            terminal = True
        elif observation_status == "UNKNOWN":
            if not terminal:
                status = "UNKNOWN"
        elif event.get("event_type") in {"SURVIVED", "EMERGED_FROM_REORGANIZATION"} and not terminal:
            status = "IN_RISK_SET"
        elif set(_list(event.get("absorbing_for"))).intersection({
            "ECONOMIC_ENTITY", "OPERATING_BUSINESS", "REPORTING_PERIMETER", "INDEPENDENT_CONTROL",
        }):
            status = "EXITED"
            terminal = True
    return status


def build_industry_history_series_from_h1(
    stage0_package: Any,
    *,
    h1_receipt_ref: dict[str, Any],
    cutoffs: list[str] | None = None,
    lifecycle_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build company×cutoff universe snapshots from one immutable H1 receipt.

    The runner is pure and offline.  Its default cutoffs are the day after the
    last disclosed annual report for each H1 fiscal period; caller-supplied
    cutoffs are allowed only through the H1 selection cutoff.  A company enters
    only after one of *its own* declared static PDFs was already public.
    """
    findings: list[str] = []
    try:
        from scripts import judgment_selection_discovery as discovery
    except ModuleNotFoundError:  # pragma: no cover - direct script import
        import judgment_selection_discovery as discovery
    h1 = discovery.validate_stage0_static_source_package(stage0_package)
    if h1.get("state") != discovery.STAGE0_FEASIBILITY_REVIEWABLE:
        findings.append("stage0_h1_package_not_feasibility_reviewable")
        findings.extend(f"stage0_h1.{item}" for item in h1.get("findings", []))
        return _result(findings)

    package = _mapping(stage0_package)
    receipt_ref = _validate_reference(h1_receipt_ref, "h1_receipt_ref", findings)
    selection_as_of = _parse_time(package.get("selection_as_of"), "stage0_h1.selection_as_of", findings)
    sources_by_company: dict[str, list[tuple[date, dict[str, Any]]]] = {}
    source_dates_by_period: dict[str, list[date]] = {}
    declared_sources = [_mapping(source) for source in _list(package.get("static_pdf_sources"))]
    for member_index, member_value in enumerate(_list(package.get("members"))):
        member = _mapping(member_value)
        company_id = str(member.get("company_id") or "")
        boundary = _mapping(member.get("boundary"))
        dates: list[tuple[date, dict[str, Any]]] = []
        for source in declared_sources:
            if any(source.get(field) != expected for field, expected in (
                ("issuer_id", member.get("issuer_id")),
                ("responsibility_unit_id", member.get("responsibility_unit_id")),
                ("perimeter_id", boundary.get("perimeter_id")),
                ("unit", boundary.get("unit")),
            )):
                continue
            published = _h1_source_publication_date(
                source, path=f"stage0_h1.static_pdf_sources[{source.get('source_id')}]", findings=findings,
            )
            if published is None:
                continue
            dates.append((published, source))
            source_dates_by_period.setdefault(str(source.get("period_end") or ""), []).append(published)
        if not dates:
            findings.append(f"stage0_h1.members[{member_index}].requires_declared_static_carrier_source")
        sources_by_company[company_id] = dates

    raw_cutoffs: list[str]
    if cutoffs is None:
        if selection_as_of is not None:
            raw_cutoffs = []
            for period_end in sorted(source_dates_by_period):
                last_publication = max(source_dates_by_period[period_end])
                candidate = datetime.combine(last_publication + timedelta(days=1), time.min, selection_as_of.tzinfo)
                if candidate <= selection_as_of:
                    raw_cutoffs.append(candidate.isoformat())
            if not raw_cutoffs or _parse_time(raw_cutoffs[-1], "history_series.default_cutoff", findings) != selection_as_of:
                raw_cutoffs.append(selection_as_of.isoformat())
        else:
            raw_cutoffs = []
    else:
        raw_cutoffs = list(cutoffs)

    cutoff_times: list[datetime] = []
    for index, raw in enumerate(raw_cutoffs):
        parsed = _parse_time(raw, f"history_series.cutoffs[{index}]", findings)
        if parsed is not None:
            cutoff_times.append(parsed)
            if selection_as_of is not None and parsed > selection_as_of:
                findings.append(f"history_series.cutoffs[{index}]_cannot_follow_h1_selection_as_of")
    if not raw_cutoffs:
        findings.append("history_series.cutoffs_nonempty_timezone_aware_list_required")
    if len(cutoff_times) == len(raw_cutoffs) and any(later <= earlier for earlier, later in zip(cutoff_times, cutoff_times[1:])):
        findings.append("history_series.cutoffs_must_be_strictly_increasing")

    events = _list(lifecycle_events)
    validated_events: list[dict[str, Any]] = []
    for index, event_value in enumerate(events):
        event_validation = validate_lifecycle_event(event_value)
        findings.extend(f"history_series.lifecycle_events[{index}].{item}" for item in event_validation["findings"])
        validated_events.append(_mapping(event_value))
    member_subjects = {
        f"ECONOMIC_ENTITY:{_mapping(member).get('company_id')}"
        for member in _list(package.get("members"))
    }
    for index, event in enumerate(validated_events):
        if event.get("subject_id") not in member_subjects:
            findings.append(f"history_series.lifecycle_events[{index}].subject_must_belong_to_h1_universe")
    if findings:
        return _result(findings)

    reference = {"receipt_id": receipt_ref["receipt_id"], "receipt_version": receipt_ref["receipt_version"]}
    arena_id = str(_mapping(package.get("competitive_arena")).get("competitive_arena_id"))
    snapshots: list[dict[str, Any]] = []
    for cutoff in cutoff_times:
        cutoff_text = cutoff.isoformat()
        members: list[dict[str, Any]] = []
        for member_value in _list(package.get("members")):
            member = _mapping(member_value)
            company_id = str(member["company_id"])
            available_sources = [
                (published, source) for published, source in sources_by_company[company_id]
                if published < cutoff.date()
            ]
            if not available_sources:
                continue
            entry_date = min(item[0] for item in available_sources) + timedelta(days=1)
            entry_at = datetime.combine(entry_date, time.min, cutoff.tzinfo).isoformat()
            boundary = _mapping(member.get("boundary"))
            members.append({
                "subject_id": f"ECONOMIC_ENTITY:{company_id}",
                "company_id": company_id,
                "issuer_id": member["issuer_id"],
                "control_group_id": member["control_group_id"],
                "responsibility_unit_id": member["responsibility_unit_id"],
                "perimeter_id": boundary["perimeter_id"],
                "observation_entry_at": entry_at,
                "risk_start_at": entry_at,
                "risk_status": _risk_status_at_cutoff(
                    validated_events, subject_id=f"ECONOMIC_ENTITY:{company_id}", cutoff_at=cutoff,
                ),
                "coverage_status": "BOUNDED_PARTIAL",
                "source_packet_refs": [deepcopy(reference)],
            })
        snapshot = {
            "schema_version": UNIVERSE_SCHEMA_VERSION,
            "universe_id": f"UNIVERSE:{package['cohort_id']}:{cutoff_text}",
            "industry_id": package["industry_id"],
            "cutoff_at": cutoff_text,
            "coverage_status": "BOUNDED_PARTIAL",
            "competitive_arena": {
                "competitive_arena_id": arena_id,
                "geography_requirement": "REQUIRED_EXPOSURE",
            },
            "membership_rule": "Immutable H1 members with a company-specific static annual PDF published strictly before this cutoff; not a final comparative panel.",
            "object_class": "INDUSTRY_UNIVERSE",
            "claim_class": "DESCRIPTIVE_STRUCTURE",
            "allowed_outputs": ["INDUSTRY_CONTEXT", "RESEARCH_AGENDA"],
            "members": members,
            "source_packet_refs": [deepcopy(reference)],
        }
        snapshots.append(snapshot)
    series = {
        "schema_version": HISTORY_SERIES_SCHEMA_VERSION,
        "series_id": f"HISTORY_SERIES:{package['cohort_id']}:{cutoff_times[0].isoformat()}:{cutoff_times[-1].isoformat()}",
        "industry_id": package["industry_id"],
        "h1_receipt_ref": deepcopy(reference),
        "cutoffs": [item.isoformat() for item in cutoff_times],
        "snapshots": snapshots,
        "lifecycle_events": deepcopy(validated_events),
    }
    validation = validate_industry_history_series(series)
    return _result(validation["findings"], industry_history_series=series)


def _validate_predicate(value: Any, registry: dict[str, Any], findings: list[str]) -> dict[str, Any]:
    predicate = _closed(value, _PREDICATE_KEYS, "registry.peer_recruitment_predicate", findings)
    _require_text(predicate, "predicate_id", "registry.peer_recruitment_predicate", findings)
    _parse_time(predicate.get("frozen_at"), "registry.peer_recruitment_predicate.frozen_at", findings)
    _validate_reference(predicate.get("action_screen_receipt_ref"), "registry.peer_recruitment_predicate.action_screen_receipt_ref", findings)
    _parse_time(predicate.get("source_cutoff_at"), "registry.peer_recruitment_predicate.source_cutoff_at", findings)
    if predicate.get("selection_rule") != "ALL_MATCHING_PREDECLARED_ROSTER":
        findings.append("registry.peer_recruitment_predicate.selection_rule_must_include_all_matching_predeclared_roster")
    if predicate.get("mechanism_topology") != registry.get("mechanism_topology"):
        findings.append("registry.peer_recruitment_predicate.mechanism_topology_must_match_registry")
    if predicate.get("competitive_arena_id") != registry.get("competitive_arena_id"):
        findings.append("registry.peer_recruitment_predicate.competitive_arena_id_must_match_registry")
    if predicate.get("requires_independent_control") is not True:
        findings.append("registry.peer_recruitment_predicate.requires_independent_control_must_be_true")
    excluded = predicate.get("excludes_break_dispositions")
    if excluded != ["KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"]:
        findings.append("registry.peer_recruitment_predicate.must_exclude_known_material_breaks")
    if predicate.get("outcome_access_prohibited") is not True:
        findings.append("registry.peer_recruitment_predicate.outcome_access_prohibited_must_be_true")
    population = _validate_eligibility_population(
        predicate.get("peer_recruitment_population"),
        path="registry.peer_recruitment_predicate.peer_recruitment_population", findings=findings,
    )
    return predicate


def _validate_eligibility_population(
    value: Any, *, path: str, findings: list[str],
) -> dict[str, dict[str, Any]]:
    population = _list(value)
    if not population:
        findings.append(f"{path}_nonempty_list_required")
    result: dict[str, dict[str, Any]] = {}
    for index, roster_value in enumerate(population):
        roster_path = f"{path}[{index}]"
        item = _closed(roster_value, _ELIGIBILITY_ROSTER_KEYS, roster_path, findings)
        company_id = _require_text(item, "company_id", roster_path, findings)
        for field in ("issuer_id", "control_group_id", "responsibility_unit_id", "perimeter_id", "unit"):
            _require_text(item, field, roster_path, findings)
        decision = item.get("eligibility_decision")
        if decision not in {"ELIGIBLE", "EXCLUDED"}:
            findings.append(f"{roster_path}.eligibility_decision_invalid")
        if decision == "EXCLUDED" and not _text(item.get("exclusion_reason")):
            findings.append(f"{roster_path}.excluded_member_requires_reason")
        if decision == "ELIGIBLE" and item.get("exclusion_reason") is not None:
            findings.append(f"{roster_path}.eligible_member_cannot_supply_exclusion_reason")
        if company_id in result:
            findings.append(f"{path}.company_id_must_not_repeat")
        result[company_id] = item
    return result


def _validate_carrier(
    value: Any, *, path: str, known_company_ids: set[str], known_control_ids: set[str],
    require_recruited_eligibility: bool, findings: list[str],
) -> tuple[str, str]:
    carrier = _closed(value, _CARRIER_KEYS, path, findings)
    carrier_id = _require_text(carrier, "carrier_id", path, findings)
    for field in ("batch_id", "company_id", "issuer_id", "control_group_id", "responsibility_unit_id", "perimeter_id", "unit"):
        _require_text(carrier, field, path, findings)
    company_id = str(carrier.get("company_id") or "")
    control_group_id = str(carrier.get("control_group_id") or "")
    if company_id and company_id in known_company_ids:
        findings.append(f"{path}.company_id_must_be_append_only")
    if control_group_id and control_group_id in known_control_ids:
        findings.append(f"{path}.control_group_id_must_be_independent")
    if carrier.get("disposition") not in CARRIER_DISPOSITIONS:
        findings.append(f"{path}.disposition_invalid")
    seed_disposition = carrier.get("seed_disposition")
    if seed_disposition is not None and seed_disposition not in {
        "PENDING_ACTION_WINDOW_REVIEW", "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK",
    }:
        findings.append(f"{path}.seed_disposition_invalid")
    if seed_disposition == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK" \
            and carrier.get("disposition") != "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK":
        findings.append(f"{path}.known_material_break_cannot_gain_comparative_eligibility")
    if require_recruited_eligibility and carrier.get("disposition") != "ELIGIBLE_FOR_COMPARATIVE":
        findings.append(f"{path}.recruited_carrier_must_be_eligible_for_comparative")
    _validate_reference(carrier.get("source_packet_ref"), f"{path}.source_packet_ref", findings)
    source_ids = carrier.get("static_source_ids")
    if not isinstance(source_ids, list) or not source_ids or not all(_text(item) for item in source_ids):
        findings.append(f"{path}.static_source_ids_nonempty_text_list_required")
    elif len(set(source_ids)) != len(source_ids):
        findings.append(f"{path}.static_source_ids_must_not_repeat")
    if require_recruited_eligibility and not _text(carrier.get("eligibility_predicate_id")):
        findings.append(f"{path}.eligibility_predicate_id_required")
    return carrier_id, company_id


def _validate_carrier_static_coverage(
    value: Any, *, path: str, source_by_id: dict[str, dict[str, Any]],
    carriers: list[Any], findings: list[str],
) -> None:
    """Bind each recruited field identity to one immutable, paged PDF fact."""
    rows = _list(value)
    if not rows:
        findings.append(f"{path}_nonempty_list_required")
        return
    carrier_by_id = {
        str(_mapping(item).get("carrier_id") or ""): _mapping(item)
        for item in carriers
    }
    coverage_sources: dict[str, set[str]] = {carrier_id: set() for carrier_id in carrier_by_id}
    seen: set[tuple[str, str, str, str]] = set()
    for index, raw in enumerate(rows):
        row_path = f"{path}[{index}]"
        row = _closed(raw, _CARRIER_STATIC_COVERAGE_KEYS, row_path, findings)
        carrier_id = _require_text(row, "carrier_id", row_path, findings)
        period_end = _require_text(row, "period_end", row_path, findings)
        field_id = _require_text(row, "field_id", row_path, findings)
        source_id = _require_text(row, "source_id", row_path, findings)
        field_ref = _require_text(row, "field_ref", row_path, findings)
        try:
            date.fromisoformat(period_end)
        except (TypeError, ValueError):
            findings.append(f"{row_path}.period_end_must_be_iso_date")
        carrier = carrier_by_id.get(carrier_id)
        if carrier is None:
            findings.append(f"{row_path}.carrier_id_must_be_declared_by_batch")
        source = source_by_id.get(source_id)
        if source is None:
            findings.append(f"{row_path}.source_id_must_be_declared_by_batch")
        else:
            if source.get("period_end") != period_end:
                findings.append(f"{row_path}.period_end_must_match_declared_static_pdf")
            if field_ref not in _list(source.get("field_refs")):
                findings.append(f"{row_path}.field_ref_must_match_declared_static_pdf_page")
            if carrier is not None and any(
                carrier.get(field) != source.get(field)
                for field in ("issuer_id", "responsibility_unit_id", "perimeter_id", "unit")
            ):
                findings.append(f"{row_path}.source_identity_must_match_carrier")
        if carrier is not None:
            coverage_sources.setdefault(carrier_id, set()).add(source_id)
        key = (carrier_id, period_end, field_id, source_id)
        if key in seen:
            findings.append(f"{path}.carrier_period_field_source_must_not_repeat")
        seen.add(key)
    for carrier_id, carrier in carrier_by_id.items():
        if not carrier_id:
            continue
        if set(_list(carrier.get("static_source_ids"))) != coverage_sources.get(carrier_id, set()):
            findings.append(f"{path}.carrier_static_sources_must_have_field_coverage")


def validate_evidence_carrier_registry(registry: Any) -> dict[str, Any]:
    """Validate an append-only registry while it is still pre-freeze."""
    findings: list[str] = []
    artifact = _closed(registry, _REGISTRY_KEYS, "registry", findings)
    if artifact.get("schema_version") != CARRIER_REGISTRY_SCHEMA_VERSION:
        findings.append("registry.schema_version_invalid")
    for field in ("registry_id", "universe_id", "industry_id", "competitive_arena_id", "mechanism_topology"):
        _require_text(artifact, field, "registry", findings)
    if artifact.get("state") not in REGISTRY_STATES:
        findings.append("registry.state_invalid")
    object_class, claim_class, _ = _validate_admission_fields(artifact, path="registry", findings=findings)
    if object_class != "EVIDENCE_CARRIER":
        findings.append("registry.object_class_must_be_evidence_carrier")
    if claim_class != "RELATIVE_CAUSAL":
        findings.append("registry.claim_class_must_be_relative_causal")
    seed_refs = _list(artifact.get("seed_receipt_refs"))
    if not seed_refs:
        findings.append("registry.seed_receipt_refs_nonempty_list_required")
    for index, reference in enumerate(seed_refs):
        _validate_reference(reference, f"registry.seed_receipt_refs[{index}]", findings)
    predicate = artifact.get("peer_recruitment_predicate")
    if predicate is not None:
        _validate_predicate(predicate, artifact, findings)
    if artifact.get("state") == "FROZEN" and predicate is None:
        findings.append("registry.frozen_state_requires_peer_recruitment_predicate")
    static_peer_batches = _list(artifact.get("static_peer_batches"))
    if artifact.get("peer_recruitment_predicate") is None and static_peer_batches:
        findings.append("registry.static_peer_batches_require_frozen_predicate")
    batch_ids: set[str] = set()
    for index, batch_value in enumerate(static_peer_batches):
        path = f"registry.static_peer_batches[{index}]"
        batch = _closed(batch_value, _BATCH_KEYS, path, findings)
        if batch.get("schema_version") != CARRIER_REGISTRY_SCHEMA_VERSION:
            findings.append(f"{path}.schema_version_invalid")
        batch_id = _require_text(batch, "batch_id", path, findings)
        if batch_id and batch_id in batch_ids:
            findings.append("registry.static_peer_batches.batch_id_must_not_repeat")
        batch_ids.add(batch_id)
        _validate_reference(batch.get("source_packet_ref"), f"{path}.source_packet_ref", findings)
        _parse_time(batch.get("received_at"), f"{path}.received_at", findings)
        if artifact.get("peer_recruitment_predicate") is not None and batch.get("eligibility_predicate_id") != _mapping(predicate).get("predicate_id"):
            findings.append(f"{path}.eligibility_predicate_id_must_match_frozen_predicate")
        _validate_eligibility_population(batch.get("eligibility_population"), path=f"{path}.eligibility_population", findings=findings)
        cutoff = _parse_time(_mapping(predicate).get("source_cutoff_at"), f"{path}.source_cutoff_at", findings) if predicate else None
        source_ids: set[str] = set()
        for source_index, source_value in enumerate(_list(batch.get("static_sources"))):
            source_path = f"{path}.static_sources[{source_index}]"
            source = _validate_static_source(source_value, path=source_path, source_cutoff=cutoff, findings=findings)
            source_id = str(source.get("source_id") or "")
            if source_id in source_ids:
                findings.append(f"{path}.static_sources.source_id_must_not_repeat")
            source_ids.add(source_id)
        if not source_ids:
            findings.append(f"{path}.static_sources_nonempty_list_required")
    carrier_ids: set[str] = set()
    company_ids: set[str] = set()
    control_ids: set[str] = set()
    carriers = _list(artifact.get("carriers"))
    if not carriers:
        findings.append("registry.carriers_nonempty_list_required")
    for index, value in enumerate(carriers):
        path = f"registry.carriers[{index}]"
        carrier_id, company_id = _validate_carrier(
            value, path=path, known_company_ids=company_ids, known_control_ids=control_ids,
            require_recruited_eligibility=False, findings=findings,
        )
        if carrier_id and carrier_id in carrier_ids:
            findings.append("registry.carriers.carrier_id_must_not_repeat")
        carrier_ids.add(carrier_id)
        company_ids.add(company_id)
        control_ids.add(str(_mapping(value).get("control_group_id") or ""))
    if artifact.get("state") == "FROZEN" and any(
        item.get("disposition") == "PENDING_ACTION_WINDOW_REVIEW" for item in carriers
    ):
        findings.append("registry.frozen_state_cannot_retain_pending_carriers")
    batches_by_id = {
        str(_mapping(batch).get("batch_id")): _mapping(batch)
        for batch in static_peer_batches
    }
    used_by_batch: dict[str, set[str]] = {batch_id: set() for batch_id in batches_by_id}
    for index, carrier_value in enumerate(carriers):
        carrier = _mapping(carrier_value)
        batch_id = str(carrier.get("batch_id") or "")
        batch = batches_by_id.get(batch_id)
        if batch is None:
            continue  # Seed carriers are anchored by ``seed_receipt_refs``.
        path = f"registry.carriers[{index}]"
        if carrier.get("source_packet_ref") != batch.get("source_packet_ref"):
            findings.append(f"{path}.source_packet_ref_must_match_static_peer_batch")
        if carrier.get("eligibility_predicate_id") != _mapping(predicate).get("predicate_id"):
            findings.append(f"{path}.eligibility_predicate_id_must_match_frozen_predicate")
        source_by_id = {
            str(_mapping(source).get("source_id")): _mapping(source)
            for source in _list(batch.get("static_sources"))
        }
        for source_id in _list(carrier.get("static_source_ids")):
            source = source_by_id.get(str(source_id))
            if source is None:
                findings.append(f"{path}.static_source_id_must_be_declared_by_static_peer_batch")
                continue
            used_by_batch[batch_id].add(str(source_id))
            if any(carrier.get(field) != source.get(field) for field in (
                "issuer_id", "responsibility_unit_id", "perimeter_id", "unit",
            )):
                findings.append(f"{path}.static_source_identity_must_match_carrier")
    for batch_id, batch in batches_by_id.items():
        declared_ids = {
            str(_mapping(source).get("source_id"))
            for source in _list(batch.get("static_sources"))
        }
        if declared_ids.difference(used_by_batch[batch_id]):
            findings.append(f"registry.static_peer_batches[{batch_id}].static_sources_must_not_be_unused")
        _validate_carrier_static_coverage(
            batch.get("carrier_static_coverage"),
            path=f"registry.static_peer_batches[{batch_id}].carrier_static_coverage",
            source_by_id={
                str(_mapping(source).get("source_id") or ""): _mapping(source)
                for source in _list(batch.get("static_sources"))
            },
            carriers=[
                carrier for carrier in carriers
                if _mapping(carrier).get("batch_id") == batch_id
            ],
            findings=findings,
        )
    return _result(findings)


def project_stage0_h1_to_universe_and_carrier_seed(
    stage0_package: Any, *, h1_receipt_ref: dict[str, Any],
) -> dict[str, Any]:
    """Project an immutable H1 package into a bounded universe plus OPEN seed registry.

    The H1 package is left unchanged.  The projection deliberately records all
    members, including known material breaks; those breaks carry sources and
    lifecycle value but retain no comparative eligibility.
    """
    findings: list[str] = []
    try:
        from scripts import judgment_selection_discovery as discovery
    except ModuleNotFoundError:  # pragma: no cover - direct script import
        import judgment_selection_discovery as discovery
    h1 = discovery.validate_stage0_static_source_package(stage0_package)
    if h1.get("state") != discovery.STAGE0_FEASIBILITY_REVIEWABLE:
        findings.append("stage0_h1_package_not_feasibility_reviewable")
        findings.extend(f"stage0_h1.{item}" for item in h1.get("findings", []))
        return _result(findings)
    package = _mapping(stage0_package)
    receipt_ref = _validate_reference(h1_receipt_ref, "h1_receipt_ref", findings)
    if findings:
        return _result(findings)
    selection_as_of = str(package["selection_as_of"])
    cohort_id = str(package["cohort_id"])
    arena_id = str(_mapping(package.get("competitive_arena")).get("competitive_arena_id"))
    members = _list(package.get("members"))
    reference = {"receipt_id": receipt_ref["receipt_id"], "receipt_version": receipt_ref["receipt_version"]}
    universe_id = f"UNIVERSE:{cohort_id}:{selection_as_of}"
    universe_members: list[dict[str, Any]] = []
    carriers: list[dict[str, Any]] = []
    for member in members:
        item = _mapping(member)
        boundary = _mapping(item.get("boundary"))
        company_id = str(item["company_id"])
        disposition = str(item["final_peer_panel_disposition"])
        universe_members.append({
            "subject_id": f"ECONOMIC_ENTITY:{company_id}",
            "company_id": company_id,
            "issuer_id": item["issuer_id"],
            "control_group_id": item["control_group_id"],
            "responsibility_unit_id": item["responsibility_unit_id"],
            "perimeter_id": boundary["perimeter_id"],
            "observation_entry_at": selection_as_of,
            "risk_start_at": selection_as_of,
            "risk_status": "IN_RISK_SET",
            "coverage_status": "BOUNDED_PARTIAL",
            "source_packet_refs": [deepcopy(reference)],
        })
        carriers.append({
            "carrier_id": f"CARRIER:{cohort_id}:{company_id}",
            "batch_id": f"SEED:{receipt_ref['receipt_id']}@{receipt_ref['receipt_version']}",
            "company_id": company_id,
            "issuer_id": item["issuer_id"],
            "control_group_id": item["control_group_id"],
            "responsibility_unit_id": item["responsibility_unit_id"],
            "perimeter_id": boundary["perimeter_id"],
            "unit": boundary["unit"],
            "disposition": disposition,
            "source_packet_ref": deepcopy(reference),
            "static_source_ids": list(item["carrier_identity_source_ids"]),
            "eligibility_predicate_id": None,
            "seed_disposition": disposition,
        })
    universe = {
        "schema_version": UNIVERSE_SCHEMA_VERSION,
        "universe_id": universe_id,
        "industry_id": package["industry_id"],
        "cutoff_at": selection_as_of,
        "coverage_status": "BOUNDED_PARTIAL",
        "competitive_arena": {
            "competitive_arena_id": arena_id,
            "geography_requirement": "REQUIRED_EXPOSURE",
        },
        "membership_rule": "Immutable H1 static source receipt members at the stated cutoff; not a final comparative panel.",
        "object_class": "INDUSTRY_UNIVERSE",
        "claim_class": "DESCRIPTIVE_STRUCTURE",
        "allowed_outputs": ["INDUSTRY_CONTEXT", "RESEARCH_AGENDA"],
        "members": universe_members,
        "source_packet_refs": [deepcopy(reference)],
    }
    registry = {
        "schema_version": CARRIER_REGISTRY_SCHEMA_VERSION,
        "registry_id": f"REGISTRY:{cohort_id}:{selection_as_of}:RELATIVE_CAUSAL",
        "universe_id": universe_id,
        "industry_id": package["industry_id"],
        "competitive_arena_id": arena_id,
        "mechanism_topology": package["mechanism_topology"],
        "state": "OPEN",
        "object_class": "EVIDENCE_CARRIER",
        "claim_class": "RELATIVE_CAUSAL",
        "allowed_outputs": ["COMPARATIVE_INTAKE_ONLY"],
        "seed_receipt_refs": [deepcopy(reference)],
        "peer_recruitment_predicate": None,
        "static_peer_batches": [],
        "carriers": carriers,
    }
    universe_validation = validate_industry_history_universe_snapshot(universe)
    registry_validation = validate_evidence_carrier_registry(registry)
    findings.extend(f"universe.{item}" for item in universe_validation["findings"])
    findings.extend(f"registry.{item}" for item in registry_validation["findings"])
    return _result(findings, universe_snapshot=universe, carrier_registry=registry)


def freeze_peer_recruitment_eligibility_predicate(registry: Any, predicate: Any) -> dict[str, Any]:
    """Freeze the rule that will recruit every eligible static peer batch."""
    validation = validate_evidence_carrier_registry(registry)
    if not validation["valid"]:
        return _result([f"registry.{item}" for item in validation["findings"]])
    updated = deepcopy(_mapping(registry))
    if updated["state"] != "OPEN":
        return _result(["carrier_registry_not_open"])
    if updated.get("peer_recruitment_predicate") is not None:
        return _result(["peer_recruitment_eligibility_predicate_already_frozen"])
    findings: list[str] = []
    validated_predicate = _validate_predicate(predicate, updated, findings)
    carrier_company_ids = {str(item.get("company_id") or "") for item in updated["carriers"]}
    carrier_control_ids = {str(item.get("control_group_id") or "") for item in updated["carriers"]}
    for roster_item in _list(validated_predicate.get("peer_recruitment_population")):
        candidate = _mapping(roster_item)
        if str(candidate.get("company_id") or "") in carrier_company_ids:
            findings.append("registry.peer_recruitment_predicate.population_cannot_repeat_existing_carrier")
        if str(candidate.get("control_group_id") or "") in carrier_control_ids:
            findings.append("registry.peer_recruitment_predicate.population_control_must_be_independent_from_existing_carriers")
    if findings:
        return _result(findings)
    updated["peer_recruitment_predicate"] = deepcopy(validated_predicate)
    result = validate_evidence_carrier_registry(updated)
    return _result(result["findings"], carrier_registry=updated)


def append_static_peer_recruitment_batch(registry: Any, batch: Any) -> dict[str, Any]:
    """Append one already-curated static batch before, and only before, freeze."""
    validation = validate_evidence_carrier_registry(registry)
    if not validation["valid"]:
        return _result([f"registry.{item}" for item in validation["findings"]])
    updated = deepcopy(_mapping(registry))
    if updated["state"] != "OPEN":
        return _result(["carrier_registry_frozen"])
    predicate = _mapping(updated.get("peer_recruitment_predicate"))
    if not predicate:
        return _result(["peer_recruitment_eligibility_predicate_not_frozen"])

    findings: list[str] = []
    packet = _closed(batch, _BATCH_KEYS, "peer_recruitment_batch", findings)
    if packet.get("schema_version") != CARRIER_REGISTRY_SCHEMA_VERSION:
        findings.append("peer_recruitment_batch.schema_version_invalid")
    batch_id = _require_text(packet, "batch_id", "peer_recruitment_batch", findings)
    _require_text(packet, "curator_id", "peer_recruitment_batch", findings)
    _validate_reference(packet.get("source_packet_ref"), "peer_recruitment_batch.source_packet_ref", findings)
    _parse_time(packet.get("received_at"), "peer_recruitment_batch.received_at", findings)
    if packet.get("eligibility_predicate_id") != predicate.get("predicate_id"):
        findings.append("peer_recruitment_batch.eligibility_predicate_id_must_match_frozen_predicate")
    existing_batches = {str(item.get("batch_id")) for item in updated["carriers"]}
    if batch_id and batch_id in existing_batches:
        findings.append("peer_recruitment_batch.batch_id_must_be_append_only")
    static_sources = _list(packet.get("static_sources"))
    if not static_sources:
        findings.append("peer_recruitment_batch.static_sources_nonempty_list_required")
    source_cutoff = _parse_time(predicate.get("source_cutoff_at"), "peer_recruitment_batch.source_cutoff_at", findings)
    source_by_id: dict[str, dict[str, Any]] = {}
    for index, source_value in enumerate(static_sources):
        path = f"peer_recruitment_batch.static_sources[{index}]"
        source = _validate_static_source(source_value, path=path, source_cutoff=source_cutoff, findings=findings)
        source_id = str(source.get("source_id") or "")
        if source_id in source_by_id:
            findings.append("peer_recruitment_batch.static_sources.source_id_must_not_repeat")
        source_by_id[source_id] = source
    population = _validate_eligibility_population(
        packet.get("eligibility_population"), path="peer_recruitment_batch.eligibility_population", findings=findings,
    )
    frozen_population = _mapping(predicate).get("peer_recruitment_population")
    if packet.get("eligibility_population") != frozen_population:
        findings.append("peer_recruitment_batch.eligibility_population_must_exactly_match_frozen_predicate")
    carriers = _list(packet.get("carriers"))
    if not carriers:
        findings.append("peer_recruitment_batch.carriers_nonempty_list_required")
    known_company_ids = {str(item.get("company_id")) for item in updated["carriers"]}
    known_control_ids = {str(item.get("control_group_id")) for item in updated["carriers"]}
    existing_carrier_ids = {str(item.get("carrier_id")) for item in updated["carriers"]}
    new_carrier_ids: set[str] = set()
    for index, value in enumerate(carriers):
        path = f"peer_recruitment_batch.carriers[{index}]"
        carrier_id, _ = _validate_carrier(
            value, path=path, known_company_ids=known_company_ids, known_control_ids=known_control_ids,
            require_recruited_eligibility=True, findings=findings,
        )
        carrier = _mapping(value)
        if carrier_id and (carrier_id in existing_carrier_ids or carrier_id in new_carrier_ids):
            findings.append("peer_recruitment_batch.carriers.carrier_id_must_be_append_only")
        new_carrier_ids.add(carrier_id)
        if carrier.get("batch_id") != batch_id:
            findings.append(f"{path}.batch_id_must_match_batch")
        if carrier.get("eligibility_predicate_id") != predicate.get("predicate_id"):
            findings.append(f"{path}.eligibility_predicate_id_must_match_frozen_predicate")
        if carrier.get("source_packet_ref") != packet.get("source_packet_ref"):
            findings.append(f"{path}.source_packet_ref_must_match_batch")
        roster_item = population.get(str(carrier.get("company_id") or ""))
        if roster_item is None:
            findings.append(f"{path}.company_id_must_be_in_predeclared_eligibility_population")
        elif roster_item.get("eligibility_decision") != "ELIGIBLE":
            findings.append(f"{path}.company_id_must_be_eligible_in_predeclared_population")
        elif any(carrier.get(field) != roster_item.get(field) for field in (
            "issuer_id", "control_group_id", "responsibility_unit_id", "perimeter_id", "unit",
        )):
            findings.append(f"{path}.identity_must_match_predeclared_eligibility_population")
        for source_id in _list(carrier.get("static_source_ids")):
            source = source_by_id.get(str(source_id))
            if source is None:
                findings.append(f"{path}.static_source_id_must_be_declared_by_batch")
                continue
            for field in ("issuer_id", "responsibility_unit_id", "perimeter_id", "unit"):
                if carrier.get(field) != source.get(field):
                    findings.append(f"{path}.static_source_identity_must_match_carrier")
                    break
        known_company_ids.add(str(carrier.get("company_id") or ""))
        known_control_ids.add(str(carrier.get("control_group_id") or ""))
    _validate_carrier_static_coverage(
        packet.get("carrier_static_coverage"),
        path="peer_recruitment_batch.carrier_static_coverage",
        source_by_id=source_by_id,
        carriers=carriers,
        findings=findings,
    )
    used_source_ids = {
        str(source_id)
        for carrier in carriers for source_id in _list(_mapping(carrier).get("static_source_ids"))
    }
    if source_by_id and set(source_by_id).difference(used_source_ids):
        findings.append("peer_recruitment_batch.static_sources_must_not_be_unused")
    eligible_population_ids = {
        company_id for company_id, item in population.items()
        if item.get("eligibility_decision") == "ELIGIBLE"
    }
    carrier_population_ids = {str(_mapping(carrier).get("company_id") or "") for carrier in carriers}
    if carrier_population_ids != eligible_population_ids:
        findings.append("peer_recruitment_batch.carriers_must_equal_all_eligible_predeclared_population")
    if findings:
        return _result(findings)
    updated["carriers"].extend(deepcopy(carriers))
    updated["static_peer_batches"].append(deepcopy(packet))
    final_validation = validate_evidence_carrier_registry(updated)
    return _result(final_validation["findings"], carrier_registry=updated)


def resolve_pending_carrier_eligibility(registry: Any, resolutions: Any) -> dict[str, Any]:
    """Resolve every seed carrier under one already-frozen eligibility rule.

    H1's ``PENDING_ACTION_WINDOW_REVIEW`` is intentionally not a comparison
    permission.  Once an H2 screen supplies the frozen predicate, this is the
    only operation that can turn a pending carrier into either an eligible
    member or a recorded exclusion.  Identity, source receipt and order stay
    unchanged.
    """
    validation = validate_evidence_carrier_registry(registry)
    if not validation["valid"]:
        return _result([f"registry.{item}" for item in validation["findings"]])
    updated = deepcopy(_mapping(registry))
    if updated["state"] != "OPEN":
        return _result(["carrier_registry_frozen"])
    predicate = _mapping(updated.get("peer_recruitment_predicate"))
    if not predicate:
        return _result(["peer_recruitment_eligibility_predicate_not_frozen"])
    entries = _list(resolutions)
    pending = {
        str(item["carrier_id"]): item for item in updated["carriers"]
        if item.get("disposition") == "PENDING_ACTION_WINDOW_REVIEW"
    }
    findings: list[str] = []
    if len(entries) != len(pending):
        findings.append("carrier_eligibility_resolution_must_cover_every_pending_carrier")
    seen: set[str] = set()
    for index, entry_value in enumerate(entries):
        path = f"carrier_eligibility_resolution[{index}]"
        entry = _mapping(entry_value)
        allowed = {"carrier_id", "disposition", "eligibility_predicate_id"}
        if not entry:
            findings.append(f"{path}_must_be_object")
            continue
        for key in sorted(set(entry).difference(allowed)):
            findings.append(f"{path}_contains_unapproved_field:{key}")
        carrier_id = _require_text(entry, "carrier_id", path, findings)
        if carrier_id in seen:
            findings.append("carrier_eligibility_resolution.carrier_id_must_not_repeat")
        seen.add(carrier_id)
        if carrier_id not in pending:
            findings.append(f"{path}.carrier_id_must_be_pending")
        if entry.get("disposition") not in {
            "ELIGIBLE_FOR_COMPARATIVE", "EXCLUDED_BY_ELIGIBILITY_PREDICATE",
        }:
            findings.append(f"{path}.disposition_invalid")
        if entry.get("eligibility_predicate_id") != predicate.get("predicate_id"):
            findings.append(f"{path}.eligibility_predicate_id_must_match_frozen_predicate")
    if set(pending).difference(seen):
        findings.append("carrier_eligibility_resolution_missing_pending_carrier")
    if findings:
        return _result(findings)
    decisions = {str(item["carrier_id"]): item for item in entries}
    for carrier in updated["carriers"]:
        decision = decisions.get(str(carrier["carrier_id"]))
        if decision:
            carrier["disposition"] = decision["disposition"]
            carrier["eligibility_predicate_id"] = decision["eligibility_predicate_id"]
    final_validation = validate_evidence_carrier_registry(updated)
    return _result(final_validation["findings"], carrier_registry=updated)


def freeze_evidence_carrier_registry(registry: Any, *, frozen_at: str) -> dict[str, Any]:
    """Close the registry before a comparative/V5 panel can be frozen."""
    validation = validate_evidence_carrier_registry(registry)
    if not validation["valid"]:
        return _result([f"registry.{item}" for item in validation["findings"]])
    if _parse_time(frozen_at, "carrier_registry.frozen_at", []) is None:
        return _result(["carrier_registry.frozen_at_timezone_aware_iso8601_required"])
    updated = deepcopy(_mapping(registry))
    if updated["state"] != "OPEN":
        return _result(["carrier_registry_already_frozen"])
    if any(item.get("disposition") == "PENDING_ACTION_WINDOW_REVIEW" for item in updated["carriers"]):
        return _result(["carrier_registry_cannot_freeze_with_pending_carriers"])
    updated["state"] = "FROZEN"
    # ``frozen_at`` belongs to the returned receipt, not the registry shape:
    # mutating the registry into a second state-bearing source would make it
    # less suitable for an exact panel/V5 freeze projection.
    return _result([], carrier_registry=updated, freeze_receipt={
        "registry_id": updated["registry_id"], "frozen_at": frozen_at,
        "state": "FROZEN",
    })


def validate_claim_specific_admission(admission: Any, *, registry: Any | None = None) -> dict[str, Any]:
    """Check lane permissions without substituting for V5 canonical admission."""
    findings: list[str] = []
    artifact = _closed(admission, _ADMISSION_KEYS, "admission", findings)
    if artifact.get("schema_version") != ADMISSION_SCHEMA_VERSION:
        findings.append("admission.schema_version_invalid")
    _require_text(artifact, "artifact_id", "admission", findings)
    object_class, claim_class, _ = _validate_admission_fields(artifact, path="admission", findings=findings)
    registry_artifact: dict[str, Any] = {}
    if registry is not None:
        registry_result = validate_evidence_carrier_registry(registry)
        if not registry_result["valid"]:
            findings.extend(f"registry.{item}" for item in registry_result["findings"])
        else:
            registry_artifact = _mapping(registry)
            if artifact.get("registry_id") != registry_artifact.get("registry_id"):
                findings.append("admission.registry_id_must_match_registry")

    if object_class in {"TEACHING_CASE", "LIFECYCLE_CASE"}:
        if artifact.get("target_company_id") is not None or artifact.get("comparator_company_ids") is not None:
            findings.append("admission.non_comparative_case_cannot_supply_panel")
    if object_class == "COMPARATIVE_EPISODE":
        if not registry_artifact:
            findings.append("admission.comparative_episode_requires_carrier_registry")
        elif registry_artifact.get("state") != "FROZEN":
            findings.append("admission.comparative_episode_requires_frozen_carrier_registry")
        target = _require_text(artifact, "target_company_id", "admission", findings)
        comparators = artifact.get("comparator_company_ids")
        if not isinstance(comparators, list) or not 3 <= len(comparators) <= 7 or not all(_text(item) for item in comparators):
            findings.append("admission.comparative_episode_requires_three_to_seven_comparators")
        if target and isinstance(comparators, list) and target in comparators:
            findings.append("admission.target_cannot_be_comparator")
        if registry_artifact:
            eligible_ids = {
                item.get("company_id") for item in registry_artifact.get("carriers", [])
                if item.get("disposition") == "ELIGIBLE_FOR_COMPARATIVE"
            }
            panel = {target, *(_list(comparators))}
            if not panel.issubset(eligible_ids):
                findings.append("admission.comparative_panel_must_use_frozen_eligible_carriers")
    if claim_class == "RELATIVE_CAUSAL" and object_class != "COMPARATIVE_EPISODE":
        findings.append("admission.relative_causal_requires_comparative_episode")
    if not findings and object_class == "COMPARATIVE_EPISODE":
        findings.append("admission.comparative_requires_registered_registry_control_plane")
    return _result(findings, next_gate=None)
