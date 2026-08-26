#!/usr/bin/env python3
"""Composite, read-only contracts for the real Enterprise Judgment V2 lane.

The module composes the existing historical risk-set runner and V3 enterprise
model.  It owns neither a fact store nor a decision ledger.  Its two frozen
pre-outcome objects are deliberately modest:

* ``EnterpriseJudgmentEpisode`` -- one company at one cutoff, with local
  evidence ceilings and outcome cells;
* ``IndustryLearningBlock`` -- a longitudinal, multi-company orchestration of
  those episodes.

An outcome settlement is a third, separately validated object.  It cannot
rewrite the frozen episode or block, and it cannot create method, CJO,
valuation, report, or investment permission.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any

try:
    from scripts import enterprise_judgment_v3 as v3
    from scripts import judgment_historical_training as history
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_v3 as v3
    import judgment_historical_training as history


EPISODE_SCHEMA_VERSION = "enterprise-judgment-episode.v2"
BLOCK_SCHEMA_VERSION = "industry-learning-block.v1"
SETTLEMENT_SCHEMA_VERSION = "enterprise-judgment-feedback-settlement.v1"
PROBE_SCHEMA_VERSION = "enterprise-judgment-mechanism-probe.v1"
PRE_OUTCOME_FREEZE_SCHEMA_VERSION = "enterprise-judgment-pre-outcome-freeze.v1"
ROUND2_ELIGIBILITY_SCHEMA_VERSION = "enterprise-judgment-round2-eligibility-register.v1"
ROUND2_SELECTION_SCHEMA_VERSION = "enterprise-judgment-round2-transition-selection.v1"
TRANSFER_APPLICATION_SCHEMA_VERSION = "enterprise-judgment-transfer-application-receipt.v1"
CONTINUATION_SETTLEMENT_SCHEMA_VERSION = "enterprise-judgment-continuation-feedback-settlement.v1"
TRANSFER_REVIEW_SCHEMA_VERSION = "enterprise-judgment-transfer-application-review.v1"
ROUND2_COMPLETION_SCHEMA_VERSION = "enterprise-judgment-round2-completion-receipt.v1"
ROUND3_SELECTION_SCHEMA_VERSION = "enterprise-judgment-round3-method-transfer-selection.v1"
ROUND3_SETTLEMENT_SCHEMA_VERSION = "enterprise-judgment-round3-feedback-settlement.v1"
ROUND3_REVIEW_SCHEMA_VERSION = "enterprise-judgment-round3-transfer-review.v1"
ROUND3_VALIDATION_SCHEMA_VERSION = "enterprise-judgment-round3-transfer-validation.v1"

CELL_STATES = {"OBSERVED", "INFERRED", "UNKNOWN", "EVIDENCE_INELIGIBLE", "NOT_APPLICABLE", "MEASUREMENT_MISMATCH"}
PREOUTCOME_CELL_STATES = CELL_STATES - {"MEASUREMENT_MISMATCH"}
PREOUTCOME_OUTCOME_CELL_STATES = {"UNSETTLED", "NOT_APPLICABLE"}
ADMISSION_LEVELS = {"E0_CONTEXT", "E1_RECONSTRUCTION", "E2_MECHANISM_PROBE"}
OUTCOME_DIMENSIONS = {"CUSTOMER", "OPERATIONS", "COMPETITION", "CASH", "CAPITAL_RETURN", "LEVERAGE", "PERMANENT_LOSS"}
DECISION_OBSERVATION_STATES = {"NOT_STARTED", "MATERIAL_DECISION_OBSERVED", "NO_MATERIAL_DECISION_OBSERVED", "INSUFFICIENT_EVIDENCE"}
ALLOWED_EPISODE_OUTPUTS = ["STATE_VIEW", "DECISION_VIEW", "MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"]
ALLOWED_BLOCK_OUTPUTS = ["INDUSTRY_CONTEXT", "TEACHING_ONLY", "MECHANISM_CANDIDATE", "RESEARCH_AGENDA"]
ALLOWED_SETTLEMENT_OUTPUTS = ["FEEDBACK_READ_MODEL", "RESEARCH_AGENDA"]
ALLOWED_PROBE_OUTPUTS = ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"]
ALLOWED_ELIGIBILITY_OUTPUTS = ["PRE_OUTCOME_SELECTION_ONLY"]
ALLOWED_APPLICATION_OUTPUTS = ["RESEARCH_AGENDA", "TRANSFER_CANDIDATE_PENDING_REVIEW"]
ALLOWED_TRANSFER_REVIEW_OUTPUTS = ["TRANSFER_CANDIDATE_CREATED", "RESEARCH_AGENDA"]
ALLOWED_ROUND2_COMPLETION_OUTPUTS = ["REAL_FEEDBACK_TURN_2_COMPLETED", "TRANSFER_CANDIDATE_CREATED"]
ALLOWED_ROUND3_SELECTION_OUTPUTS = ["PRE_OUTCOME_METHOD_APPLICATION_ONLY"]
ALLOWED_ROUND3_REVIEW_OUTPUTS = ["METHOD_TRANSFER_REVIEW_ONLY"]
ALLOWED_ROUND3_VALIDATION_OUTPUTS = ["TRANSFER_VALIDATED", "PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY"]

_ROLE_KEYS = {"judgment_owner_id", "independent_challenger_id", "outcome_custodian_id"}
_EPISODE_KEYS = {
    "schema_version", "episode_id", "company_id", "issuer_id", "company_cluster_id", "cutoff_at",
    "admission_level", "industry_block_id", "risk_set_snapshot_ref", "source_packet_ref",
    "responsibility_boundary", "enterprise_system_model_ref", "management_decision_observation",
    "lifecycle_state", "question_set", "claims", "evidence_coverage", "feedback_loops",
    "mechanism_threads", "outcome_cells", "roles", "object_class", "claim_class", "allowed_outputs",
}
_SNAPSHOT_REF_KEYS = {"universe_id", "cutoff_at", "company_id"}
_RECEIPT_REF_KEYS = {"receipt_id", "receipt_version"}
_BOUNDARY_KEYS = {"responsibility_unit_id", "perimeter_id", "arena_id"}
_MODEL_REF_KEYS = {"model_id", "version"}
_DECISION_OBSERVATION_KEYS = {"status", "reviewed_source_refs", "materiality_scope", "next_discriminating_evidence"}
_QUESTION_KEYS = {"question_id", "role", "question", "claim_ids"}
_CLAIM_KEYS = {"claim_id", "question_id", "domain", "statement", "cell_status", "admission_level", "evidence_refs", "dependent_outcome_cell_ids"}
_COVERAGE_KEYS = {"cell_id", "status", "evidence_refs", "boundary_note"}
_LOOP_KEYS = {"loop_id", "domains", "node_ids", "edge_ids", "evidence_refs", "selection_rationale"}
_THREAD_KEYS = {"thread_id", "role", "anchor_kind", "responsibility_unit_id", "arena_id", "claim_ids", "hypotheses", "diagnostic_matrix", "evidence_refs", "observation_clock", "outcome_cell_ids", "evidence_ceiling", "permitted_conclusion"}
_HYPOTHESIS_KEYS = {"hypothesis_id", "role", "statement"}
_DIAGNOSTIC_KEYS = {"diagnostic_id", "h_a_expectation", "h_b_expectation", "status"}
_OUTCOME_CELL_KEYS = {"outcome_cell_id", "dimension", "status", "measurement_contract"}
_MEASUREMENT_KEYS = {"contract_id", "definition", "window_start", "window_end", "allowed_source_types", "prohibited_proxies", "outcome_custodian_id"}
_BLOCK_KEYS = {
    "schema_version", "block_id", "industry_id", "competitive_arena_id", "history_series_ref", "cutoffs",
    "industry_epoch_map", "company_archetype_map", "episode_roster", "decision_heterogeneity_matrix",
    "conditional_mechanism_synthesis", "unresolved_questions", "next_sampling_decision", "transition_roster",
    "company_cutoff_transition_roster", "company_cluster_map", "e1_selection_rule", "model_memory_status",
    "roles", "object_class", "claim_class", "allowed_outputs",
}
_SERIES_REF_KEYS = {"series_id", "h1_receipt_ref"}
_EPOCH_KEYS = {"epoch_id", "cutoff_at", "statement", "status", "evidence_refs"}
_ARCHETYPE_KEYS = {"company_id", "archetype_id", "condition", "evidence_refs", "boundary_status"}
_ROSTER_KEYS = {"episode_id", "company_id", "company_cluster_id", "cutoff_at", "admission_level"}
_HETEROGENEITY_KEYS = {"company_id", "company_conditions", "feasible_alternatives", "decision_state", "execution_state", "adaptation_state", "external_conditions", "evidence_ceiling"}
_SYNTHESIS_KEYS = {"synthesis_id", "when", "decision", "mechanism", "observed_as", "unless", "counterexamples", "evidence_ceiling", "evidence_refs"}
_QUESTION_AGENDA_KEYS = {"question_id", "question", "materiality", "next_evidence", "status"}
_NEXT_SAMPLING_KEYS = {"decision", "rationale", "next_company_cutoff_refs"}
_CLUSTER_KEYS = {"company_id", "company_cluster_id"}
_E1_SELECTION_KEYS = {"selection_rule_id", "criterion", "prohibited_selection_inputs"}
_TRANSITION_KEYS = {"rank", "transition_id", "episode_id", "company_id", "cutoff_at", "outcome_cell_ids", "next_cutoff_at", "outcome_access_status"}
_COMPANY_CUTOFF_TRANSITION_KEYS = {"rank", "transition_id", "company_id", "company_cluster_id", "cutoff_at", "next_cutoff_at", "outcome_access_status"}
_SETTLEMENT_KEYS = {"schema_version", "settlement_id", "block_id", "pre_outcome_freeze_ref", "frozen_transition_rank", "transition_id", "company_id", "cutoff_at", "outcome_custodian_id", "source_receipt", "observations", "next_cutoff_agenda_delta", "original_episode_immutable", "object_class", "claim_class", "allowed_outputs"}
_SOURCE_RECEIPT_KEYS = {"source_ref", "published_on", "official_url", "source_type", "custodian_access", "availability_precision"}
_OBSERVATION_KEYS = {"outcome_cell_id", "status", "reported_value", "summary", "source_ref"}
_AGENDA_DELTA_KEYS = {"target_cutoff_at", "change_id", "change_type", "statement", "reason"}
_PROBE_KEYS = {
    "schema_version", "probe_id", "episode_id", "company_id", "issuer_id", "cutoff_at",
    "thread_id", "anchor_kind", "responsibility_unit_id", "arena_id", "claim_ids", "hypothesis_ids",
    "diagnostic_matrix", "direct_evidence_refs", "outcome_cell_ids", "outcome_access",
    "action_effect_authority", "roles", "object_class", "claim_class", "allowed_outputs",
}
_PROBE_DIAGNOSTIC_KEYS = {"diagnostic_id", "diagnostic_kind", "h_a_prediction", "h_b_prediction"}
_PRE_OUTCOME_FREEZE_KEYS = {"schema_version", "freeze_id", "block_id", "pre_outcome_block_commit", "company_cutoff_transition_ids", "outcome_transition_ids", "object_class", "claim_class", "allowed_outputs"}
_ELIGIBILITY_REGISTER_KEYS = {"schema_version", "register_id", "block_id", "pre_outcome_freeze_ref", "selection_policy", "completed_feedback_settlement_ids", "entries", "first_eligible_target_binding", "roles", "object_class", "claim_class", "allowed_outputs"}
_ELIGIBILITY_ENTRY_KEYS = {"rank", "transition_id", "company_id", "company_cluster_id", "cutoff_at", "next_cutoff_at", "disposition", "reviewed_source_refs", "rationale"}
_ELIGIBILITY_TARGET_BINDING_KEYS = {"transition_id", "target_episode_id", "outcome_cell_ids"}
_ROUND2_SELECTION_KEYS = {"schema_version", "selection_id", "block_id", "pre_outcome_freeze_ref", "eligibility_register_ref", "selection_policy", "completed_company_cutoff_transition_ids", "ineligible_prior_rows", "selected_transition_id", "selected_rank", "company_id", "company_cluster_id", "cutoff_at", "next_cutoff_at", "target_episode_id", "outcome_cell_ids", "cutoff_visible_evidence_refs", "outcome_access_status", "roles", "object_class", "claim_class", "allowed_outputs"}
_INELIGIBLE_ROW_KEYS = {"rank", "transition_id", "reason"}
_APPLICATION_KEYS = {"schema_version", "application_id", "block_id", "pre_outcome_freeze_ref", "selection_ref", "source_feedback_id", "source_observation_cell_id", "source_agenda_change_id", "learned_rule_id", "target_episode_id", "baseline_before_learning", "enhanced_after_learning", "field_delta", "target_outcome_access", "frozen_before_outcome_access", "roles", "object_class", "claim_class", "allowed_outputs"}
_APPLICATION_FIELD_KEYS = {"field_id", "dimension", "definition", "claim_ids", "measurement_gate"}
_FIELD_DELTA_KEYS = {"field_id", "change_kind", "baseline_gate", "enhanced_gate", "reason_ref", "materiality"}
_CONTINUATION_SETTLEMENT_KEYS = {"schema_version", "settlement_id", "application_ref", "selection_ref", "company_id", "cutoff_at", "outcome_custodian_id", "source_receipt", "observations", "next_cutoff_agenda_delta", "original_episode_immutable", "object_class", "claim_class", "allowed_outputs"}
_TRANSFER_REVIEW_KEYS = {"schema_version", "review_id", "application_ref", "source_feedback_id", "continuation_settlement_id", "reviewer_id", "verdict", "materiality_statement", "causal_trace_statement", "prohibited_conclusion", "transfer_status", "allowed_outputs", "object_class", "claim_class"}
_ROUND2_COMPLETION_KEYS = {"schema_version", "completion_id", "block_id", "settlement_id", "review_id", "feedback_turn_status", "transfer_status", "object_class", "claim_class", "allowed_outputs"}
_ROUND2_CHAIN_KEYS = {
    "eligibility_register", "selection", "target_models", "target_episode", "application",
    "continuation_settlement", "review", "completion", "source_feedback_settlement",
}
_ROUND3_SELECTION_KEYS = {
    "schema_version", "selection_id", "block_id", "pre_outcome_freeze_ref", "round2_completion_ref",
    "selection_policy", "completed_company_ids", "selected_transition_id", "selected_rank", "company_id",
    "company_cluster_id", "cutoff_at", "next_cutoff_at", "target_episode_id", "outcome_cell_ids",
    "pre_outcome_source_refs", "outcome_access_status", "roles", "object_class", "claim_class", "allowed_outputs",
}
_ROUND3_SETTLEMENT_KEYS = {
    "schema_version", "settlement_id", "application_ref", "selection_ref", "company_id", "cutoff_at",
    "outcome_custodian_id", "method_rule_id", "research_order", "perimeter_assessment", "source_receipt",
    "observations", "next_cutoff_agenda_delta", "original_episode_immutable", "object_class", "claim_class",
    "allowed_outputs",
}
_PERIMETER_ASSESSMENT_KEYS = {"status", "statement", "evidence_refs"}
_ROUND3_REVIEW_KEYS = {
    "schema_version", "review_id", "application_ref", "feedback_ref", "prior_review_ref", "reviewer_id",
    "review_scope", "verdict", "research_order_changed", "rule_unchanged", "materiality_statement",
    "prohibited_conclusion", "object_class", "claim_class", "allowed_outputs",
}
_ROUND3_VALIDATION_KEYS = {
    "schema_version", "validation_id", "method_rule_id", "source_feedback_ref", "round2_application_ref",
    "round2_review_ref", "round2_completion_ref", "round3_selection_ref", "round3_application_ref",
    "round3_settlement_ref", "round3_review_ref", "transfer_status", "authority_scope", "denied_authorities",
    "object_class", "claim_class", "allowed_outputs",
}
_FORBIDDEN_KEYS = {
    "price", "market_price", "share_price", "stock_price", "entry_price", "valuation", "valuation_result",
    "expectation_gap", "buyband", "buy_band", "investment_instruction", "portfolio_action", "position",
    "return", "return_result", "training_score", "method_freeze", "cjo", "forecast_probability",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str], *, required: set[str] | None = None) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, path + "_must_be_object")
        return item
    for key in sorted(set(item).difference(allowed)):
        _add(findings, f"{path}_contains_unapproved_field:{key}")
    for key in sorted((allowed if required is None else required).difference(item)):
        _add(findings, f"{path}_missing_required_field:{key}")
    return item


def _required_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        _add(findings, f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        _add(findings, path + "_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        _add(findings, path + "_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _add(findings, path + "_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _date(value: Any, path: str, findings: list[str]) -> date | None:
    if not _text(value):
        _add(findings, path + "_must_be_iso8601_date")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        _add(findings, path + "_must_be_iso8601_date")
        return None


def _ids(value: Any, path: str, findings: list[str], *, required: bool = True) -> list[str]:
    values = _items(value)
    if required and not values:
        _add(findings, path + "_required")
    result: list[str] = []
    for index, raw in enumerate(values):
        if not _text(raw):
            _add(findings, f"{path}[{index}]_must_be_nonempty_text")
        elif str(raw) in result:
            _add(findings, f"{path}[{index}]_duplicate")
        else:
            result.append(str(raw))
    return result


def _forbidden_paths(value: Any, path: str) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            child = f"{path}.{key}"
            if (
                lowered in _FORBIDDEN_KEYS or lowered.startswith("actual_") or (lowered.startswith("settlement_") and lowered != "settlement_id")
                or lowered.endswith("_market_price") or lowered.endswith("_share_price")
            ):
                paths.append(child)
            else:
                paths.extend(_forbidden_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _source_catalog(h1_package: Any) -> dict[str, dict[str, Any]]:
    return {
        entry.get("source_id"): entry
        for entry in map(_mapping, _items(_mapping(h1_package).get("static_pdf_sources")))
        if _text(entry.get("source_id"))
    }


def _source_before_cutoff(source: dict[str, Any], cutoff: datetime) -> bool:
    try:
        published = date.fromisoformat(str(source.get("published_at")))
    except ValueError:
        return False
    return published < cutoff.date()


def _validate_source_refs(
    refs: list[str], *, catalog: dict[str, dict[str, Any]], company_id: str, boundary: dict[str, Any], cutoff: datetime | None,
    path: str, findings: list[str],
) -> None:
    for ref in refs:
        source = _mapping(catalog.get(ref))
        if not source:
            _add(findings, path + ".source_ref_not_in_h1:" + ref)
            continue
        if source.get("issuer_id") != boundary.get("issuer_id"):
            _add(findings, path + ".source_issuer_mismatch:" + ref)
        if source.get("responsibility_unit_id") != boundary.get("responsibility_unit_id") or source.get("perimeter_id") != boundary.get("perimeter_id"):
            _add(findings, path + ".source_responsibility_boundary_mismatch:" + ref)
        if cutoff is not None and not _source_before_cutoff(source, cutoff):
            _add(findings, path + ".source_not_cutoff_visible:" + ref)


def _validate_roles(value: Any, *, expected: dict[str, Any] | None, path: str, findings: list[str]) -> dict[str, Any]:
    roles = _closed(value, _ROLE_KEYS, path, findings)
    values = [_required_text(roles, field, path, findings) for field in _ROLE_KEYS]
    if len(set(item for item in values if item)) != len(_ROLE_KEYS):
        _add(findings, path + ".roles_must_be_independent")
    if expected is not None and roles != expected:
        _add(findings, path + ".roles_must_match_bound_object")
    return roles


def _history_binding(series: Any, h1_package: Any, findings: list[str]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    validation = history.validate_industry_history_series(series)
    for finding in validation["findings"]:
        _add(findings, "history_series:" + finding)
    h1_result = history.build_industry_history_series_from_h1(
        h1_package,
        h1_receipt_ref=_mapping(_mapping(series).get("h1_receipt_ref")),
    )
    # The supplied series may include declared, cutoff-visible lifecycle data;
    # it need not byte-equal the bare H1 projection.  Both validation paths are
    # required, while identity fields below bind its actual series.
    for finding in h1_result["findings"]:
        _add(findings, "h1_package:" + finding)
    return _mapping(series), _source_catalog(h1_package)


def _snapshot_for(series: dict[str, Any], cutoff_at: str) -> dict[str, Any]:
    for snapshot in map(_mapping, _items(series.get("snapshots"))):
        if snapshot.get("cutoff_at") == cutoff_at:
            return snapshot
    return {}


def _validate_episode_structure(
    item: dict[str, Any], *, catalog: dict[str, dict[str, Any]], series: dict[str, Any], bound_models: dict[str, Any], findings: list[str],
) -> None:
    for field in ("episode_id", "company_id", "issuer_id", "company_cluster_id", "industry_block_id"):
        _required_text(item, field, "episode", findings)
    cutoff = _instant(item.get("cutoff_at"), "episode.cutoff_at", findings)
    level = item.get("admission_level")
    if level not in ADMISSION_LEVELS:
        _add(findings, "episode.admission_level_invalid")
    if level == "E2_MECHANISM_PROBE":
        _add(findings, "episode.e2_must_be_compiled_as_a_bound_mechanism_probe")
    if item.get("schema_version") != EPISODE_SCHEMA_VERSION:
        _add(findings, "episode.schema_version_invalid")
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_EPISODE":
        _add(findings, "episode.object_class_invalid")
    if item.get("claim_class") != "CUTOFF_ENTERPRISE_RECONSTRUCTION":
        _add(findings, "episode.claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_EPISODE_OUTPUTS:
        _add(findings, "episode.allowed_outputs_must_remain_read_only_training_views")

    snapshot_ref = _closed(item.get("risk_set_snapshot_ref"), _SNAPSHOT_REF_KEYS, "episode.risk_set_snapshot_ref", findings)
    snapshot = _snapshot_for(series, str(item.get("cutoff_at")))
    if not snapshot:
        _add(findings, "episode.risk_set_snapshot_ref_cutoff_unknown")
    elif snapshot_ref != {"universe_id": snapshot.get("universe_id"), "cutoff_at": snapshot.get("cutoff_at"), "company_id": item.get("company_id")}:
        _add(findings, "episode.risk_set_snapshot_ref_must_match_bound_history_snapshot")
    member = next((entry for entry in map(_mapping, _items(snapshot.get("members"))) if entry.get("company_id") == item.get("company_id")), {})
    if not member:
        _add(findings, "episode.company_must_be_in_bound_cutoff_risk_set")

    source_ref = _closed(item.get("source_packet_ref"), _RECEIPT_REF_KEYS, "episode.source_packet_ref", findings)
    if source_ref != _mapping(series.get("h1_receipt_ref")):
        _add(findings, "episode.source_packet_ref_must_match_history_h1_receipt")
    boundary = _closed(item.get("responsibility_boundary"), _BOUNDARY_KEYS, "episode.responsibility_boundary", findings)
    boundary_with_issuer = {**boundary, "issuer_id": item.get("issuer_id")}
    for field, expected in (
        ("issuer_id", member.get("issuer_id")),
        ("responsibility_unit_id", member.get("responsibility_unit_id")),
        ("perimeter_id", member.get("perimeter_id")),
    ):
        actual = item.get(field) if field == "issuer_id" else boundary.get(field)
        if actual != expected:
            _add(findings, "episode.responsibility_boundary_must_match_bound_risk_member")

    model_ref = item.get("enterprise_system_model_ref")
    if level == "E0_CONTEXT":
        if model_ref not in (None, {}):
            _add(findings, "episode.e0_context_cannot_claim_enterprise_model_reconstruction")
    else:
        model_ref = _closed(model_ref, _MODEL_REF_KEYS, "episode.enterprise_system_model_ref", findings)
        model = _mapping(bound_models.get(model_ref.get("model_id")))
        if not model:
            _add(findings, "episode.enterprise_system_model_ref_must_bind_supplied_model")
        else:
            validation = v3.validate_enterprise_system_model(model)
            for finding in validation["findings"]:
                _add(findings, "enterprise_system_model:" + finding)
            if model_ref != {"model_id": model.get("model_id"), "version": model.get("version")}:
                _add(findings, "episode.enterprise_system_model_ref_must_match_bound_model")
            if model.get("company_id") != item.get("issuer_id") or model.get("as_of") != item.get("cutoff_at"):
                _add(findings, "episode.enterprise_system_model_must_match_company_and_cutoff")
            if boundary.get("responsibility_unit_id") not in _items(model.get("responsibility_unit_ids")) or boundary.get("arena_id") not in _items(model.get("competitive_arena_ids")):
                _add(findings, "episode.enterprise_system_model_must_cover_responsibility_boundary_and_arena")
            for component in _items(model.get("nodes")) + _items(model.get("edges")):
                refs = [str(_mapping(source).get("ref")) for source in _items(_mapping(component).get("evidence")) if _text(_mapping(source).get("ref"))]
                _validate_source_refs(refs, catalog=catalog, company_id=str(item.get("company_id")), boundary=boundary_with_issuer, cutoff=cutoff, path="episode.enterprise_system_model.evidence", findings=findings)

    decision = _closed(item.get("management_decision_observation"), _DECISION_OBSERVATION_KEYS, "episode.management_decision_observation", findings)
    if decision.get("status") not in DECISION_OBSERVATION_STATES:
        _add(findings, "episode.management_decision_observation.status_invalid")
    reviewed_refs = _ids(decision.get("reviewed_source_refs"), "episode.management_decision_observation.reviewed_source_refs", findings, required=decision.get("status") != "NOT_STARTED")
    _validate_source_refs(reviewed_refs, catalog=catalog, company_id=str(item.get("company_id")), boundary=boundary_with_issuer, cutoff=cutoff, path="episode.management_decision_observation", findings=findings)
    for field in ("materiality_scope", "next_discriminating_evidence"):
        _required_text(decision, field, "episode.management_decision_observation", findings)

    questions = [_closed(raw, _QUESTION_KEYS, f"episode.question_set[{index}]", findings) for index, raw in enumerate(_items(item.get("question_set")))]
    if not 3 <= len(questions) <= 5:
        _add(findings, "episode.question_set_must_contain_one_primary_and_two_to_four_supporting_questions")
    question_ids: set[str] = set()
    primary_questions = 0
    for index, question in enumerate(questions):
        question_id = _required_text(question, "question_id", f"episode.question_set[{index}]", findings)
        if question_id in question_ids:
            _add(findings, f"episode.question_set[{index}].question_id_duplicate")
        question_ids.add(question_id)
        if question.get("role") not in {"PRIMARY", "SUPPORTING"}:
            _add(findings, f"episode.question_set[{index}].role_invalid")
        primary_questions += question.get("role") == "PRIMARY"
        _required_text(question, "question", f"episode.question_set[{index}]", findings)
        _ids(question.get("claim_ids"), f"episode.question_set[{index}].claim_ids", findings)
    if primary_questions != 1:
        _add(findings, "episode.question_set_must_have_exactly_one_primary_question")

    cells = [_closed(raw, _OUTCOME_CELL_KEYS, f"episode.outcome_cells[{index}]", findings) for index, raw in enumerate(_items(item.get("outcome_cells")))]
    cell_ids: set[str] = set()
    dimensions: set[str] = set()
    for index, cell in enumerate(cells):
        cell_id = _required_text(cell, "outcome_cell_id", f"episode.outcome_cells[{index}]", findings)
        if cell_id in cell_ids:
            _add(findings, f"episode.outcome_cells[{index}].outcome_cell_id_duplicate")
        cell_ids.add(cell_id)
        dimension = cell.get("dimension")
        dimensions.add(str(dimension))
        if dimension not in OUTCOME_DIMENSIONS:
            _add(findings, f"episode.outcome_cells[{index}].dimension_invalid")
        if cell.get("status") not in PREOUTCOME_OUTCOME_CELL_STATES:
            _add(findings, f"episode.outcome_cells[{index}].pre_outcome_status_invalid")
        measurement = _closed(cell.get("measurement_contract"), _MEASUREMENT_KEYS, f"episode.outcome_cells[{index}].measurement_contract", findings)
        for field in {"contract_id", "definition", "window_start", "window_end", "outcome_custodian_id"}:
            _required_text(measurement, field, f"episode.outcome_cells[{index}].measurement_contract", findings)
        _ids(measurement.get("allowed_source_types"), f"episode.outcome_cells[{index}].measurement_contract.allowed_source_types", findings)
        _ids(measurement.get("prohibited_proxies"), f"episode.outcome_cells[{index}].measurement_contract.prohibited_proxies", findings)
        start = _instant(measurement.get("window_start"), f"episode.outcome_cells[{index}].measurement_contract.window_start", findings)
        end = _instant(measurement.get("window_end"), f"episode.outcome_cells[{index}].measurement_contract.window_end", findings)
        if cutoff is not None and start is not None and start <= cutoff:
            _add(findings, f"episode.outcome_cells[{index}].measurement_contract.window_start_must_be_after_cutoff")
        if start is not None and end is not None and end <= start:
            _add(findings, f"episode.outcome_cells[{index}].measurement_contract.window_end_must_follow_start")
    if dimensions != OUTCOME_DIMENSIONS:
        _add(findings, "episode.outcome_cells_must_cover_each_required_dimension_once")

    claims = [_closed(raw, _CLAIM_KEYS, f"episode.claims[{index}]", findings) for index, raw in enumerate(_items(item.get("claims")))]
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        claim_id = _required_text(claim, "claim_id", f"episode.claims[{index}]", findings)
        if claim_id in claim_ids:
            _add(findings, f"episode.claims[{index}].claim_id_duplicate")
        claim_ids.add(claim_id)
        if claim.get("question_id") not in question_ids:
            _add(findings, f"episode.claims[{index}].question_id_unknown")
        if claim.get("domain") not in OUTCOME_DIMENSIONS | {"ORGANIZATION", "LIFECYCLE"}:
            _add(findings, f"episode.claims[{index}].domain_invalid")
        _required_text(claim, "statement", f"episode.claims[{index}]", findings)
        if claim.get("cell_status") not in PREOUTCOME_CELL_STATES or claim.get("admission_level") not in ADMISSION_LEVELS:
            _add(findings, f"episode.claims[{index}].status_or_admission_invalid")
        refs = _ids(claim.get("evidence_refs"), f"episode.claims[{index}].evidence_refs", findings, required=claim.get("cell_status") in {"OBSERVED", "INFERRED", "EVIDENCE_INELIGIBLE"})
        _validate_source_refs(refs, catalog=catalog, company_id=str(item.get("company_id")), boundary=boundary_with_issuer, cutoff=cutoff, path=f"episode.claims[{index}]", findings=findings)
        if any(cell_id not in cell_ids for cell_id in _ids(claim.get("dependent_outcome_cell_ids"), f"episode.claims[{index}].dependent_outcome_cell_ids", findings, required=False)):
            _add(findings, f"episode.claims[{index}].dependent_outcome_cell_ids_unknown")
    for question in questions:
        if any(claim_id not in claim_ids for claim_id in _items(question.get("claim_ids"))):
            _add(findings, "episode.question_set_references_unknown_claim")

    coverage = [_closed(raw, _COVERAGE_KEYS, f"episode.evidence_coverage[{index}]", findings) for index, raw in enumerate(_items(item.get("evidence_coverage")))]
    coverage_ids: set[str] = set()
    for index, entry in enumerate(coverage):
        coverage_id = _required_text(entry, "cell_id", f"episode.evidence_coverage[{index}]", findings)
        coverage_ids.add(coverage_id)
        if entry.get("status") not in PREOUTCOME_CELL_STATES:
            _add(findings, f"episode.evidence_coverage[{index}].status_invalid")
        refs = _ids(entry.get("evidence_refs"), f"episode.evidence_coverage[{index}].evidence_refs", findings, required=entry.get("status") in {"OBSERVED", "INFERRED", "EVIDENCE_INELIGIBLE"})
        _validate_source_refs(refs, catalog=catalog, company_id=str(item.get("company_id")), boundary=boundary_with_issuer, cutoff=cutoff, path=f"episode.evidence_coverage[{index}]", findings=findings)
        _required_text(entry, "boundary_note", f"episode.evidence_coverage[{index}]", findings)
    if coverage_ids != OUTCOME_DIMENSIONS:
        _add(findings, "episode.evidence_coverage_must_localize_each_required_dimension")

    loops = [_closed(raw, _LOOP_KEYS, f"episode.feedback_loops[{index}]", findings) for index, raw in enumerate(_items(item.get("feedback_loops")))]
    if level == "E1_RECONSTRUCTION" and not 2 <= len(loops) <= 3:
        _add(findings, "episode.e1_requires_two_to_three_material_feedback_loops")
    for index, loop in enumerate(loops):
        _required_text(loop, "loop_id", f"episode.feedback_loops[{index}]", findings)
        _ids(loop.get("domains"), f"episode.feedback_loops[{index}].domains", findings)
        _ids(loop.get("node_ids"), f"episode.feedback_loops[{index}].node_ids", findings)
        _ids(loop.get("edge_ids"), f"episode.feedback_loops[{index}].edge_ids", findings)
        refs = _ids(loop.get("evidence_refs"), f"episode.feedback_loops[{index}].evidence_refs", findings)
        _validate_source_refs(refs, catalog=catalog, company_id=str(item.get("company_id")), boundary=boundary_with_issuer, cutoff=cutoff, path=f"episode.feedback_loops[{index}]", findings=findings)
        _required_text(loop, "selection_rationale", f"episode.feedback_loops[{index}]", findings)

    threads = [_closed(raw, _THREAD_KEYS, f"episode.mechanism_threads[{index}]", findings, required=_THREAD_KEYS - {"diagnostic_matrix"}) for index, raw in enumerate(_items(item.get("mechanism_threads")))]
    thread_primary_count = 0
    for index, thread in enumerate(threads):
        _required_text(thread, "thread_id", f"episode.mechanism_threads[{index}]", findings)
        if thread.get("role") not in {"PRIMARY", "SUPPORTING"}:
            _add(findings, f"episode.mechanism_threads[{index}].role_invalid")
        thread_primary_count += thread.get("role") == "PRIMARY"
        if thread.get("anchor_kind") not in {"STATE_TRANSMISSION", "MANAGEMENT_DECISION"}:
            _add(findings, f"episode.mechanism_threads[{index}].anchor_kind_invalid")
        if (thread.get("responsibility_unit_id"), thread.get("arena_id")) != (boundary.get("responsibility_unit_id"), boundary.get("arena_id")):
            _add(findings, f"episode.mechanism_threads[{index}].responsibility_boundary_mismatch")
        if thread.get("anchor_kind") == "MANAGEMENT_DECISION" and decision.get("status") != "MATERIAL_DECISION_OBSERVED":
            _add(findings, f"episode.mechanism_threads[{index}].management_action_requires_material_decision_observation")
        if thread.get("anchor_kind") == "STATE_TRANSMISSION" and thread.get("permitted_conclusion") != "TEACHING_ONLY":
            _add(findings, f"episode.mechanism_threads[{index}].state_transmission_must_remain_teaching_only")
        if thread.get("evidence_ceiling") not in {"CONTEXT_ONLY", "TEACHING_ONLY", "MECHANISM_CANDIDATE"} or thread.get("permitted_conclusion") != "TEACHING_ONLY":
            _add(findings, f"episode.mechanism_threads[{index}].permission_ceiling_invalid")
        if any(claim_id not in claim_ids for claim_id in _ids(thread.get("claim_ids"), f"episode.mechanism_threads[{index}].claim_ids", findings)):
            _add(findings, f"episode.mechanism_threads[{index}].claim_ids_unknown")
        refs = _ids(thread.get("evidence_refs"), f"episode.mechanism_threads[{index}].evidence_refs", findings)
        _validate_source_refs(refs, catalog=catalog, company_id=str(item.get("company_id")), boundary=boundary_with_issuer, cutoff=cutoff, path=f"episode.mechanism_threads[{index}]", findings=findings)
        _required_text(thread, "observation_clock", f"episode.mechanism_threads[{index}]", findings)
        if any(cell_id not in cell_ids for cell_id in _ids(thread.get("outcome_cell_ids"), f"episode.mechanism_threads[{index}].outcome_cell_ids", findings)):
            _add(findings, f"episode.mechanism_threads[{index}].outcome_cell_ids_unknown")
        hypotheses = [_closed(raw, _HYPOTHESIS_KEYS, f"episode.mechanism_threads[{index}].hypotheses[{subindex}]", findings) for subindex, raw in enumerate(_items(thread.get("hypotheses")))]
        if len(hypotheses) != 2 or {item.get("role") for item in hypotheses} != {"H_A", "H_B"}:
            _add(findings, f"episode.mechanism_threads[{index}].hypotheses_must_contain_h_a_and_h_b")
        if len({str(hypothesis.get("statement")) for hypothesis in hypotheses}) != 2:
            _add(findings, f"episode.mechanism_threads[{index}].hypotheses_must_be_distinct")
        diagnostics = [_closed(raw, _DIAGNOSTIC_KEYS, f"episode.mechanism_threads[{index}].diagnostic_matrix[{subindex}]", findings) for subindex, raw in enumerate(_items(thread.get("diagnostic_matrix")))]
        for subindex, diagnostic in enumerate(diagnostics):
            for field in _DIAGNOSTIC_KEYS:
                _required_text(diagnostic, field, f"episode.mechanism_threads[{index}].diagnostic_matrix[{subindex}]", findings)
            if diagnostic.get("status") != "UNSETTLED":
                _add(findings, f"episode.mechanism_threads[{index}].diagnostic_matrix[{subindex}].pre_outcome_status_must_remain_unsettled")
            if diagnostic.get("h_a_expectation") == diagnostic.get("h_b_expectation"):
                _add(findings, f"episode.mechanism_threads[{index}].diagnostic_matrix[{subindex}].hypotheses_must_discriminate")
    if threads and thread_primary_count != 1:
        _add(findings, "episode.mechanism_threads_must_have_exactly_one_primary")

    lifecycle = _mapping(item.get("lifecycle_state"))
    if lifecycle.get("risk_status") != member.get("risk_status"):
        _add(findings, "episode.lifecycle_state_must_match_bound_risk_set_status")
    _validate_roles(item.get("roles"), expected=None, path="episode.roles", findings=findings)
    for path in _forbidden_paths(item, "episode"):
        _add(findings, "episode.forbidden_field:" + path)


def validate_enterprise_judgment_episode(
    episode: Any, *, history_series: Any, h1_package: Any, enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    """Validate a cutoff-safe E0/E1/E2 composite without writing canonical state."""
    findings: list[str] = []
    series, catalog = _history_binding(history_series, h1_package, findings)
    item = _closed(episode, _EPISODE_KEYS, "episode", findings)
    models = {entry.get("model_id"): entry for entry in map(_mapping, enterprise_models or []) if _text(entry.get("model_id"))}
    _validate_episode_structure(item, catalog=catalog, series=series, bound_models=models, findings=findings)
    return {"valid": not findings, "findings": findings, "episode": deepcopy(item) if not findings else None}


def compile_enterprise_judgment_episode(
    episode: Any, *, history_series: Any, h1_package: Any, enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    """Project local claim permissions; a bad cell cannot erase other claims."""
    validation = validate_enterprise_judgment_episode(episode, history_series=history_series, h1_package=h1_package, enterprise_models=enterprise_models)
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "episode_read_model": None}
    item = _mapping(episode)
    cells = {entry["outcome_cell_id"]: entry for entry in map(_mapping, _items(item["outcome_cells"]))}
    rows = []
    for claim in map(_mapping, _items(item["claims"])):
        blockers = []
        if claim["cell_status"] in {"UNKNOWN", "EVIDENCE_INELIGIBLE", "NOT_APPLICABLE"}:
            blockers.append({"kind": "CLAIM_STATUS", "ref": claim["cell_status"]})
        for cell_id in claim["dependent_outcome_cell_ids"]:
            if cells[cell_id]["status"] in {"UNSETTLED", "NOT_APPLICABLE"}:
                blockers.append({"kind": "OUTCOME_CELL", "ref": cell_id})
        outputs = ["RESEARCH_AGENDA"] if blockers else list(ALLOWED_EPISODE_OUTPUTS)
        rows.append({"claim_id": claim["claim_id"], "admission_level": claim["admission_level"], "allowed_outputs": outputs, "blocked_by": blockers})
    return {"valid": True, "findings": [], "episode_read_model": {"episode_id": item["episode_id"], "company_id": item["company_id"], "cutoff_at": item["cutoff_at"], "claim_output_matrix": rows, "investment_authorization": "NOT_AUTHORIZED"}}


def validate_mechanism_probe(
    probe: Any, *, episode: Any, history_series: Any, h1_package: Any, enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    """Validate J2 as a bound, pre-outcome probe rather than free text.

    E2 is represented by this narrow companion object.  An E1 episode can
    carry teaching threads without becoming an action-effect or Comparative
    object.  The binding below prevents a writer from upgrading one such
    thread merely by restating H-A/H-B in prose.
    """
    findings: list[str] = []
    episode_result = validate_enterprise_judgment_episode(
        episode, history_series=history_series, h1_package=h1_package, enterprise_models=enterprise_models,
    )
    for finding in episode_result["findings"]:
        _add(findings, "episode:" + finding)
    series, catalog = _history_binding(history_series, h1_package, findings)
    item = _closed(probe, _PROBE_KEYS, "mechanism_probe", findings)
    if item.get("schema_version") != PROBE_SCHEMA_VERSION:
        _add(findings, "mechanism_probe.schema_version_invalid")
    for field in ("probe_id", "episode_id", "company_id", "issuer_id", "cutoff_at", "thread_id", "responsibility_unit_id", "arena_id"):
        _required_text(item, field, "mechanism_probe", findings)
    if item.get("object_class") != "MECHANISM_PROBE" or item.get("claim_class") != "LOCAL_PRE_OUTCOME_MECHANISM_TEST":
        _add(findings, "mechanism_probe.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_PROBE_OUTPUTS:
        _add(findings, "mechanism_probe.allowed_outputs_must_remain_teaching_only")
    if item.get("outcome_access") != "NONE":
        _add(findings, "mechanism_probe.outcome_access_must_remain_none")
    episode_item = _mapping(episode)
    if any(item.get(field) != episode_item.get(field) for field in ("episode_id", "company_id", "issuer_id", "cutoff_at")):
        _add(findings, "mechanism_probe.identity_must_match_bound_episode")
    boundary = _mapping(episode_item.get("responsibility_boundary"))
    if (item.get("responsibility_unit_id"), item.get("arena_id")) != (boundary.get("responsibility_unit_id"), boundary.get("arena_id")):
        _add(findings, "mechanism_probe.responsibility_boundary_must_match_bound_episode")
    thread = next((raw for raw in map(_mapping, _items(episode_item.get("mechanism_threads"))) if raw.get("thread_id") == item.get("thread_id")), {})
    if not thread:
        _add(findings, "mechanism_probe.thread_must_match_bound_episode")
    else:
        if item.get("anchor_kind") != thread.get("anchor_kind"):
            _add(findings, "mechanism_probe.anchor_kind_must_match_bound_thread")
        if _ids(item.get("claim_ids"), "mechanism_probe.claim_ids", findings) != _items(thread.get("claim_ids")):
            _add(findings, "mechanism_probe.claim_ids_must_match_bound_thread")
        expected_hypotheses = [entry.get("hypothesis_id") for entry in map(_mapping, _items(thread.get("hypotheses")))]
        if _ids(item.get("hypothesis_ids"), "mechanism_probe.hypothesis_ids", findings) != expected_hypotheses:
            _add(findings, "mechanism_probe.hypothesis_ids_must_match_bound_thread")
        if _ids(item.get("outcome_cell_ids"), "mechanism_probe.outcome_cell_ids", findings) != _items(thread.get("outcome_cell_ids")):
            _add(findings, "mechanism_probe.outcome_cells_must_match_bound_thread")
    direct_refs = _ids(item.get("direct_evidence_refs"), "mechanism_probe.direct_evidence_refs", findings)
    probe_boundary = {"issuer_id": item.get("issuer_id"), "responsibility_unit_id": item.get("responsibility_unit_id"), "perimeter_id": boundary.get("perimeter_id")}
    _validate_source_refs(direct_refs, catalog=catalog, company_id=str(item.get("company_id")), boundary=probe_boundary, cutoff=_instant(item.get("cutoff_at"), "mechanism_probe.cutoff_at", findings), path="mechanism_probe.direct_evidence_refs", findings=findings)
    if thread and not set(direct_refs).issubset(set(_items(thread.get("evidence_refs")))):
        _add(findings, "mechanism_probe.direct_evidence_must_be_bound_thread_evidence")
    diagnostics = [_closed(raw, _PROBE_DIAGNOSTIC_KEYS, f"mechanism_probe.diagnostic_matrix[{index}]", findings) for index, raw in enumerate(_items(item.get("diagnostic_matrix")))]
    if not diagnostics:
        _add(findings, "mechanism_probe.diagnostic_matrix_required")
    for index, diagnostic in enumerate(diagnostics):
        for field in _PROBE_DIAGNOSTIC_KEYS:
            _required_text(diagnostic, field, f"mechanism_probe.diagnostic_matrix[{index}]", findings)
        if diagnostic.get("diagnostic_kind") not in {"EARLY_DIAGNOSTIC", "TERMINAL_OUTCOME"}:
            _add(findings, f"mechanism_probe.diagnostic_matrix[{index}].kind_invalid")
        if diagnostic.get("h_a_prediction") == diagnostic.get("h_b_prediction"):
            _add(findings, f"mechanism_probe.diagnostic_matrix[{index}].hypotheses_must_discriminate")
    decision_status = _mapping(episode_item.get("management_decision_observation")).get("status")
    if item.get("anchor_kind") == "MANAGEMENT_DECISION":
        if decision_status != "MATERIAL_DECISION_OBSERVED" or item.get("action_effect_authority") != "LOCAL_ONLY":
            _add(findings, "mechanism_probe.management_action_requires_observed_decision_and_local_authority")
    elif item.get("anchor_kind") == "STATE_TRANSMISSION":
        if item.get("action_effect_authority") != "NONE":
            _add(findings, "mechanism_probe.state_transmission_must_not_claim_action_effect")
    else:
        _add(findings, "mechanism_probe.anchor_kind_invalid")
    _validate_roles(item.get("roles"), expected=_mapping(episode_item.get("roles")), path="mechanism_probe.roles", findings=findings)
    for path in _forbidden_paths(item, "mechanism_probe"):
        _add(findings, "mechanism_probe.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "mechanism_probe": deepcopy(item) if not findings else None}


def compile_mechanism_probe(
    probe: Any, *, episode: Any, history_series: Any, h1_package: Any, enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    validation = validate_mechanism_probe(
        probe, episode=episode, history_series=history_series, h1_package=h1_package, enterprise_models=enterprise_models,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "mechanism_probe_read_model": None}
    item = _mapping(probe)
    return {"valid": True, "findings": [], "mechanism_probe_read_model": {
        "probe_id": item["probe_id"], "episode_id": item["episode_id"], "thread_id": item["thread_id"],
        "allowed_outputs": list(ALLOWED_PROBE_OUTPUTS), "action_effect_authority": item["action_effect_authority"],
        "investment_authorization": "NOT_AUTHORIZED",
    }}


def validate_industry_learning_block(
    block: Any, *, history_series: Any, h1_package: Any, episodes: list[Any], enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    """Validate an IndustryLearningBlock as an aggregation of exact episodes."""
    findings: list[str] = []
    series, catalog = _history_binding(history_series, h1_package, findings)
    item = _closed(block, _BLOCK_KEYS, "industry_block", findings)
    if item.get("schema_version") != BLOCK_SCHEMA_VERSION:
        _add(findings, "industry_block.schema_version_invalid")
    for field in ("block_id", "industry_id", "competitive_arena_id"):
        _required_text(item, field, "industry_block", findings)
    if item.get("object_class") != "INDUSTRY_LEARNING_BLOCK" or item.get("claim_class") != "CONDITIONAL_INDUSTRY_TEACHING":
        _add(findings, "industry_block.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_BLOCK_OUTPUTS:
        _add(findings, "industry_block.allowed_outputs_must_remain_context_teaching_and_agenda")
    if item.get("model_memory_status") != "MODEL_MEMORY_MITIGATED":
        _add(findings, "industry_block.model_memory_status_must_remain_mitigated")
    series_ref = _closed(item.get("history_series_ref"), _SERIES_REF_KEYS, "industry_block.history_series_ref", findings)
    if series_ref != {"series_id": series.get("series_id"), "h1_receipt_ref": _mapping(series.get("h1_receipt_ref"))}:
        _add(findings, "industry_block.history_series_ref_must_match_bound_history_series")
    cutoffs = _ids(item.get("cutoffs"), "industry_block.cutoffs", findings)
    if cutoffs != _items(series.get("cutoffs")):
        _add(findings, "industry_block.cutoffs_must_exactly_match_bound_history_series")

    clusters = [_closed(raw, _CLUSTER_KEYS, f"industry_block.company_cluster_map[{index}]", findings) for index, raw in enumerate(_items(item.get("company_cluster_map")))]
    cluster_by_company: dict[str, str] = {}
    cluster_ids: set[str] = set()
    for index, cluster in enumerate(clusters):
        company_id = _required_text(cluster, "company_id", f"industry_block.company_cluster_map[{index}]", findings)
        cluster_id = _required_text(cluster, "company_cluster_id", f"industry_block.company_cluster_map[{index}]", findings)
        if company_id in cluster_by_company or cluster_id in cluster_ids:
            _add(findings, f"industry_block.company_cluster_map[{index}].company_or_cluster_duplicate")
        cluster_by_company[company_id] = cluster_id
        cluster_ids.add(cluster_id)
    selection_rule = _closed(item.get("e1_selection_rule"), _E1_SELECTION_KEYS, "industry_block.e1_selection_rule", findings)
    for field in _E1_SELECTION_KEYS:
        _required_text(selection_rule, field, "industry_block.e1_selection_rule", findings)
    if selection_rule.get("criterion") != "CUTOFF_VISIBLE_MATERIALITY_STATE_DIFFERENCE_AND_FIELD_COVERAGE":
        _add(findings, "industry_block.e1_selection_rule.criterion_invalid")
    if selection_rule.get("prohibited_selection_inputs") != "POST_CUTOFF_RESULTS_OR_EASE_OF_PASSING":
        _add(findings, "industry_block.e1_selection_rule.prohibited_inputs_invalid")

    models = list(enterprise_models or [])
    bound_episodes: dict[str, dict[str, Any]] = {}
    for index, raw_episode in enumerate(episodes):
        validation = validate_enterprise_judgment_episode(raw_episode, history_series=series, h1_package=h1_package, enterprise_models=models)
        for finding in validation["findings"]:
            _add(findings, f"episodes[{index}]:" + finding)
        episode = _mapping(raw_episode)
        if validation["valid"]:
            bound_episodes[episode["episode_id"]] = episode

    epochs = [_closed(raw, _EPOCH_KEYS, f"industry_block.industry_epoch_map[{index}]", findings) for index, raw in enumerate(_items(item.get("industry_epoch_map")))]
    if len(epochs) != len(cutoffs):
        _add(findings, "industry_block.industry_epoch_map_must_cover_each_cutoff")
    epoch_cutoffs: set[str] = set()
    for index, epoch in enumerate(epochs):
        _required_text(epoch, "epoch_id", f"industry_block.industry_epoch_map[{index}]", findings)
        cutoff = _required_text(epoch, "cutoff_at", f"industry_block.industry_epoch_map[{index}]", findings)
        epoch_cutoffs.add(cutoff)
        _required_text(epoch, "statement", f"industry_block.industry_epoch_map[{index}]", findings)
        if epoch.get("status") not in PREOUTCOME_CELL_STATES:
            _add(findings, f"industry_block.industry_epoch_map[{index}].status_invalid")
        refs = _ids(epoch.get("evidence_refs"), f"industry_block.industry_epoch_map[{index}].evidence_refs", findings, required=epoch.get("status") in {"OBSERVED", "INFERRED"})
        snapshot = _snapshot_for(series, cutoff)
        if not snapshot:
            _add(findings, f"industry_block.industry_epoch_map[{index}].cutoff_unknown")
        for ref in refs:
            source = _mapping(catalog.get(ref))
            if not source or (snapshot and not _source_before_cutoff(source, _instant(cutoff, "industry_block.epoch.cutoff_at", findings) or datetime.max.replace(tzinfo=timezone.utc))):
                _add(findings, f"industry_block.industry_epoch_map[{index}].source_not_cutoff_visible")
    if epoch_cutoffs != set(cutoffs):
        _add(findings, "industry_block.industry_epoch_map_cutoffs_must_match_block_cutoffs")

    archetypes = [_closed(raw, _ARCHETYPE_KEYS, f"industry_block.company_archetype_map[{index}]", findings) for index, raw in enumerate(_items(item.get("company_archetype_map")))]
    all_companies = {entry.get("company_id") for snapshot in map(_mapping, _items(series.get("snapshots"))) for entry in map(_mapping, _items(snapshot.get("members")))}
    if set(cluster_by_company) != all_companies:
        _add(findings, "industry_block.company_cluster_map_must_preserve_all_h1_companies")
    archetype_companies: set[str] = set()
    last_cutoff = _instant(cutoffs[-1], "industry_block.cutoffs[-1]", findings) if cutoffs else None
    for index, archetype in enumerate(archetypes):
        company_id = _required_text(archetype, "company_id", f"industry_block.company_archetype_map[{index}]", findings)
        archetype_companies.add(company_id)
        for field in ("archetype_id", "condition", "boundary_status"):
            _required_text(archetype, field, f"industry_block.company_archetype_map[{index}]", findings)
        refs = _ids(archetype.get("evidence_refs"), f"industry_block.company_archetype_map[{index}].evidence_refs", findings)
        member = next((entry for snapshot in map(_mapping, _items(series.get("snapshots"))) for entry in map(_mapping, _items(snapshot.get("members"))) if entry.get("company_id") == company_id), {})
        boundary = {"issuer_id": member.get("issuer_id"), "responsibility_unit_id": member.get("responsibility_unit_id"), "perimeter_id": member.get("perimeter_id")}
        _validate_source_refs(refs, catalog=catalog, company_id=company_id, boundary=boundary, cutoff=last_cutoff, path=f"industry_block.company_archetype_map[{index}]", findings=findings)
    if archetype_companies != all_companies:
        _add(findings, "industry_block.company_archetype_map_must_preserve_all_h1_companies")

    roster = [_closed(raw, _ROSTER_KEYS, f"industry_block.episode_roster[{index}]", findings) for index, raw in enumerate(_items(item.get("episode_roster")))]
    roster_ids: set[str] = set()
    for index, entry in enumerate(roster):
        episode_id = _required_text(entry, "episode_id", f"industry_block.episode_roster[{index}]", findings)
        roster_ids.add(episode_id)
        bound = _mapping(bound_episodes.get(episode_id))
        if not bound or any(entry.get(field) != bound.get(field) for field in ("company_id", "company_cluster_id", "cutoff_at", "admission_level")):
            _add(findings, f"industry_block.episode_roster[{index}].must_match_bound_episode")
        elif entry.get("company_cluster_id") != cluster_by_company.get(entry.get("company_id")):
            _add(findings, f"industry_block.episode_roster[{index}].company_cluster_must_match_block_map")
    if set(bound_episodes) != roster_ids:
        _add(findings, "industry_block.episode_roster_must_exactly_list_bound_episodes")
    if len({entry.get("company_id") for entry in roster if entry.get("admission_level") == "E1_RECONSTRUCTION"}) < 2 or len({entry.get("cutoff_at") for entry in roster if entry.get("admission_level") == "E1_RECONSTRUCTION"}) < 2:
        _add(findings, "industry_block.e1_roster_requires_cross_company_and_longitudinal_variation")

    heterogeneity = [_closed(raw, _HETEROGENEITY_KEYS, f"industry_block.decision_heterogeneity_matrix[{index}]", findings) for index, raw in enumerate(_items(item.get("decision_heterogeneity_matrix")))]
    heterogeneity_companies: set[str] = set()
    for index, entry in enumerate(heterogeneity):
        company_id = _required_text(entry, "company_id", f"industry_block.decision_heterogeneity_matrix[{index}]", findings)
        heterogeneity_companies.add(company_id)
        for field in _HETEROGENEITY_KEYS - {"company_id"}:
            _required_text(entry, field, f"industry_block.decision_heterogeneity_matrix[{index}]", findings)
        if entry.get("evidence_ceiling") not in {"CONTEXT_ONLY", "TEACHING_ONLY", "MECHANISM_CANDIDATE"}:
            _add(findings, f"industry_block.decision_heterogeneity_matrix[{index}].evidence_ceiling_invalid")
    if heterogeneity_companies != all_companies:
        _add(findings, "industry_block.decision_heterogeneity_matrix_must_preserve_all_h1_companies")

    syntheses = [_closed(raw, _SYNTHESIS_KEYS, f"industry_block.conditional_mechanism_synthesis[{index}]", findings) for index, raw in enumerate(_items(item.get("conditional_mechanism_synthesis")))]
    if not syntheses:
        _add(findings, "industry_block.conditional_mechanism_synthesis_required")
    for index, synthesis in enumerate(syntheses):
        for field in _SYNTHESIS_KEYS - {"evidence_refs"}:
            _required_text(synthesis, field, f"industry_block.conditional_mechanism_synthesis[{index}]", findings)
        if synthesis.get("evidence_ceiling") not in {"CONTEXT_ONLY", "TEACHING_ONLY", "MECHANISM_CANDIDATE"}:
            _add(findings, f"industry_block.conditional_mechanism_synthesis[{index}].evidence_ceiling_invalid")
        if synthesis.get("evidence_ceiling") == "MECHANISM_CANDIDATE":
            _add(findings, f"industry_block.conditional_mechanism_synthesis[{index}].cannot_upgrade_without_e2_settlement")
        _ids(synthesis.get("evidence_refs"), f"industry_block.conditional_mechanism_synthesis[{index}].evidence_refs", findings, required=False)

    agenda = [_closed(raw, _QUESTION_AGENDA_KEYS, f"industry_block.unresolved_questions[{index}]", findings) for index, raw in enumerate(_items(item.get("unresolved_questions")))]
    if not agenda:
        _add(findings, "industry_block.unresolved_questions_required")
    for index, question in enumerate(agenda):
        for field in _QUESTION_AGENDA_KEYS:
            _required_text(question, field, f"industry_block.unresolved_questions[{index}]", findings)
    next_sampling = _closed(item.get("next_sampling_decision"), _NEXT_SAMPLING_KEYS, "industry_block.next_sampling_decision", findings)
    for field in ("decision", "rationale"):
        _required_text(next_sampling, field, "industry_block.next_sampling_decision", findings)
    _ids(next_sampling.get("next_company_cutoff_refs"), "industry_block.next_sampling_decision.next_company_cutoff_refs", findings)

    company_cutoff_roster = [_closed(raw, _COMPANY_CUTOFF_TRANSITION_KEYS, f"industry_block.company_cutoff_transition_roster[{index}]", findings) for index, raw in enumerate(_items(item.get("company_cutoff_transition_roster")))]
    expected_company_cutoffs = {
        (company_id, cluster_by_company.get(company_id), cutoffs[index], cutoffs[index + 1])
        for company_id in all_companies
        for index in range(max(0, len(cutoffs) - 2))
    }
    seen_company_cutoffs: set[tuple[Any, Any, Any, Any]] = set()
    company_cutoff_ranks: list[int] = []
    for index, transition in enumerate(company_cutoff_roster):
        rank = transition.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            _add(findings, f"industry_block.company_cutoff_transition_roster[{index}].rank_must_be_positive_integer")
        else:
            company_cutoff_ranks.append(rank)
        _required_text(transition, "transition_id", f"industry_block.company_cutoff_transition_roster[{index}]", findings)
        transition_tuple = (transition.get("company_id"), transition.get("company_cluster_id"), transition.get("cutoff_at"), transition.get("next_cutoff_at"))
        seen_company_cutoffs.add(transition_tuple)
        if transition.get("outcome_access_status") != "SEALED":
            _add(findings, f"industry_block.company_cutoff_transition_roster[{index}].outcome_access_must_remain_sealed")
    if seen_company_cutoffs != expected_company_cutoffs:
        _add(findings, "industry_block.company_cutoff_transition_roster_must_preserve_all_h1_company_cutoff_transitions")
    if company_cutoff_ranks != list(range(1, len(company_cutoff_roster) + 1)):
        _add(findings, "industry_block.company_cutoff_transition_roster_must_preserve_predeclared_order")

    transitions = [_closed(raw, _TRANSITION_KEYS, f"industry_block.transition_roster[{index}]", findings) for index, raw in enumerate(_items(item.get("transition_roster")))]
    if not transitions:
        _add(findings, "industry_block.transition_roster_required_before_outcome_access")
    seen_transition_ids: set[str] = set()
    transition_ranks: list[int] = []
    for index, transition in enumerate(transitions):
        rank = transition.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            _add(findings, f"industry_block.transition_roster[{index}].rank_must_be_positive_integer")
        else:
            transition_ranks.append(rank)
        transition_id = _required_text(transition, "transition_id", f"industry_block.transition_roster[{index}]", findings)
        if transition_id in seen_transition_ids:
            _add(findings, f"industry_block.transition_roster[{index}].transition_id_duplicate")
        seen_transition_ids.add(transition_id)
        episode = _mapping(bound_episodes.get(transition.get("episode_id")))
        if not episode or any(transition.get(field) != episode.get(field) for field in ("company_id", "cutoff_at")):
            _add(findings, f"industry_block.transition_roster[{index}].must_match_bound_episode")
        episode_cells = {entry.get("outcome_cell_id") for entry in map(_mapping, _items(episode.get("outcome_cells")))}
        if any(cell_id not in episode_cells for cell_id in _ids(transition.get("outcome_cell_ids"), f"industry_block.transition_roster[{index}].outcome_cell_ids", findings)):
            _add(findings, f"industry_block.transition_roster[{index}].outcome_cell_ids_unknown")
        cutoff = _instant(transition.get("cutoff_at"), f"industry_block.transition_roster[{index}].cutoff_at", findings)
        next_cutoff = _instant(transition.get("next_cutoff_at"), f"industry_block.transition_roster[{index}].next_cutoff_at", findings)
        if cutoff is not None and next_cutoff is not None and next_cutoff <= cutoff:
            _add(findings, f"industry_block.transition_roster[{index}].next_cutoff_must_follow_episode_cutoff")
        if transition.get("next_cutoff_at") not in cutoffs:
            _add(findings, f"industry_block.transition_roster[{index}].next_cutoff_must_belong_to_block")
        if transition.get("outcome_access_status") != "SEALED":
            _add(findings, f"industry_block.transition_roster[{index}].outcome_access_must_remain_sealed")
        if (transition.get("company_id"), cluster_by_company.get(transition.get("company_id")), transition.get("cutoff_at"), transition.get("next_cutoff_at")) not in seen_company_cutoffs:
            _add(findings, f"industry_block.transition_roster[{index}].must_be_drawn_from_frozen_company_cutoff_roster")
    if transition_ranks != list(range(1, len(transitions) + 1)):
        _add(findings, "industry_block.transition_roster_must_preserve_predeclared_order")

    roles = _validate_roles(item.get("roles"), expected=None, path="industry_block.roles", findings=findings)
    for episode in bound_episodes.values():
        if _mapping(episode.get("roles")) != roles:
            _add(findings, "industry_block.roles_must_match_all_bound_episodes")
    for path in _forbidden_paths(item, "industry_block"):
        _add(findings, "industry_block.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "industry_learning_block": deepcopy(item) if not findings else None}


def compile_industry_learning_block(
    block: Any, *, history_series: Any, h1_package: Any, episodes: list[Any], enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    validation = validate_industry_learning_block(block, history_series=history_series, h1_package=h1_package, episodes=episodes, enterprise_models=enterprise_models)
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "industry_learning_read_model": None}
    item = _mapping(block)
    return {"valid": True, "findings": [], "industry_learning_read_model": {"block_id": item["block_id"], "industry_id": item["industry_id"], "cutoffs": list(item["cutoffs"]), "episode_ids": [entry["episode_id"] for entry in item["episode_roster"]], "allowed_outputs": list(ALLOWED_BLOCK_OUTPUTS), "investment_authorization": "NOT_AUTHORIZED"}}


def compile_outcome_custodian_brief(
    block: Any, episode: Any, transition_id: str,
) -> dict[str, Any]:
    """Project only the contract-matched outcome work for an independent custodian.

    Deliberately absent: hypotheses, mechanism threads, forecasts, comparative
    identities, prices, valuation, and every investment object.  The caller
    must separately validate the frozen block before relying on this brief.
    """
    block_item, episode_item = _mapping(block), _mapping(episode)
    transition = next((entry for entry in map(_mapping, _items(block_item.get("transition_roster"))) if entry.get("transition_id") == transition_id), {})
    if not transition or transition.get("episode_id") != episode_item.get("episode_id"):
        return {"valid": False, "findings": ["outcome_custodian_brief.transition_must_match_episode"], "outcome_custodian_brief": None}
    cells = {
        entry.get("outcome_cell_id"): entry
        for entry in map(_mapping, _items(episode_item.get("outcome_cells")))
    }
    selected = [cells[cell_id] for cell_id in _items(transition.get("outcome_cell_ids")) if cell_id in cells]
    if len(selected) != len(_items(transition.get("outcome_cell_ids"))):
        return {"valid": False, "findings": ["outcome_custodian_brief.transition_cells_unknown"], "outcome_custodian_brief": None}
    return {"valid": True, "findings": [], "outcome_custodian_brief": {
        "block_id": block_item.get("block_id"), "transition_id": transition_id,
        "company_id": episode_item.get("company_id"), "issuer_id": episode_item.get("issuer_id"),
        "cutoff_at": episode_item.get("cutoff_at"),
        "responsibility_boundary": deepcopy(_mapping(episode_item.get("responsibility_boundary"))),
        "outcome_custodian_id": _mapping(block_item.get("roles")).get("outcome_custodian_id"),
        "outcome_cells": [{
            "outcome_cell_id": cell.get("outcome_cell_id"), "dimension": cell.get("dimension"),
            "measurement_contract": deepcopy(_mapping(cell.get("measurement_contract"))),
        } for cell in selected],
        "outcome_access_status": transition.get("outcome_access_status"),
        "investment_authorization": "NOT_AUTHORIZED",
    }}


def validate_pre_outcome_roster_freeze(freeze: Any, *, block: Any) -> dict[str, Any]:
    """Bind later custody work to the exact pre-outcome roster projection.

    This is a human-auditable revision reference plus ordered identifiers, not
    a second fact store or a checksum.  It gives an offline validator a stable
    object against which to reject a reordered-and-renumbered live block.
    """
    findings: list[str] = []
    item = _closed(freeze, _PRE_OUTCOME_FREEZE_KEYS, "pre_outcome_roster_freeze", findings)
    if item.get("schema_version") != PRE_OUTCOME_FREEZE_SCHEMA_VERSION:
        _add(findings, "pre_outcome_roster_freeze.schema_version_invalid")
    for field in ("freeze_id", "block_id", "pre_outcome_block_commit"):
        _required_text(item, field, "pre_outcome_roster_freeze", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_PRE_OUTCOME_FREEZE" or item.get("claim_class") != "ROSTER_IMMUTABILITY_BINDING":
        _add(findings, "pre_outcome_roster_freeze.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ["OUTCOME_CUSTODY_ONLY"]:
        _add(findings, "pre_outcome_roster_freeze.allowed_outputs_invalid")
    block_item = _mapping(block)
    if item.get("block_id") != block_item.get("block_id"):
        _add(findings, "pre_outcome_roster_freeze.block_must_match")
    company_ids = _ids(item.get("company_cutoff_transition_ids"), "pre_outcome_roster_freeze.company_cutoff_transition_ids", findings)
    outcome_ids = _ids(item.get("outcome_transition_ids"), "pre_outcome_roster_freeze.outcome_transition_ids", findings)
    if company_ids != [entry.get("transition_id") for entry in map(_mapping, _items(block_item.get("company_cutoff_transition_roster")))]:
        _add(findings, "pre_outcome_roster_freeze.company_cutoff_order_must_match_frozen_projection")
    if outcome_ids != [entry.get("transition_id") for entry in map(_mapping, _items(block_item.get("transition_roster")))]:
        _add(findings, "pre_outcome_roster_freeze.outcome_order_must_match_frozen_projection")
    return {"valid": not findings, "findings": findings, "pre_outcome_roster_freeze": deepcopy(item) if not findings else None}


def validate_feedback_settlement(
    settlement: Any, *, block: Any, pre_outcome_roster_freeze: Any, history_series: Any, h1_package: Any, episodes: list[Any], enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    """Validate a separately-accessed feedback turn and its agenda change."""
    findings: list[str] = []
    block_validation = validate_industry_learning_block(block, history_series=history_series, h1_package=h1_package, episodes=episodes, enterprise_models=enterprise_models)
    for finding in block_validation["findings"]:
        _add(findings, "industry_block:" + finding)
    freeze_validation = validate_pre_outcome_roster_freeze(pre_outcome_roster_freeze, block=block)
    for finding in freeze_validation["findings"]:
        _add(findings, "pre_outcome_roster_freeze:" + finding)
    block_item = _mapping(block)
    freeze_item = _mapping(pre_outcome_roster_freeze)
    item = _closed(settlement, _SETTLEMENT_KEYS, "feedback_settlement", findings)
    if item.get("schema_version") != SETTLEMENT_SCHEMA_VERSION:
        _add(findings, "feedback_settlement.schema_version_invalid")
    for field in ("settlement_id", "block_id", "pre_outcome_freeze_ref", "transition_id", "company_id", "cutoff_at", "outcome_custodian_id"):
        _required_text(item, field, "feedback_settlement", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_FEEDBACK_SETTLEMENT" or item.get("claim_class") != "CONTRACT_MATCHED_PREQUENTIAL_FEEDBACK":
        _add(findings, "feedback_settlement.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_SETTLEMENT_OUTPUTS:
        _add(findings, "feedback_settlement.allowed_outputs_invalid")
    if item.get("original_episode_immutable") is not True:
        _add(findings, "feedback_settlement.must_preserve_original_episode_immutable")
    if item.get("pre_outcome_freeze_ref") != freeze_item.get("freeze_id"):
        _add(findings, "feedback_settlement.must_reference_bound_pre_outcome_roster_freeze")
    transition = next((entry for entry in map(_mapping, _items(block_item.get("transition_roster"))) if entry.get("transition_id") == item.get("transition_id")), {})
    if not transition or item.get("block_id") != block_item.get("block_id") or any(item.get(field) != transition.get(field) for field in ("company_id", "cutoff_at")):
        _add(findings, "feedback_settlement.must_match_frozen_block_transition")
    if item.get("frozen_transition_rank") != transition.get("rank"):
        _add(findings, "feedback_settlement.frozen_transition_rank_must_match_pre_outcome_projection")
    if item.get("outcome_custodian_id") != _mapping(block_item.get("roles")).get("outcome_custodian_id"):
        _add(findings, "feedback_settlement.custodian_must_match_frozen_roles")
    episode_by_id = {entry.get("episode_id"): entry for entry in map(_mapping, episodes)}
    episode = _mapping(episode_by_id.get(transition.get("episode_id")))
    receipt = _closed(item.get("source_receipt"), _SOURCE_RECEIPT_KEYS, "feedback_settlement.source_receipt", findings)
    for field in _SOURCE_RECEIPT_KEYS:
        _required_text(receipt, field, "feedback_settlement.source_receipt", findings)
    cutoff = _instant(item.get("cutoff_at"), "feedback_settlement.cutoff_at", findings)
    published = _date(receipt.get("published_on"), "feedback_settlement.source_receipt.published_on", findings)
    if cutoff is not None and published is not None and published <= cutoff.date():
        _add(findings, "feedback_settlement.source_receipt_must_be_post_cutoff")
    if receipt.get("custodian_access") != "OUTCOME_ONLY":
        _add(findings, "feedback_settlement.source_receipt_must_be_outcome_only")
    if receipt.get("availability_precision") != "DATE":
        _add(findings, "feedback_settlement.source_receipt_must_preserve_date_precision")
    catalog_source = _mapping(_source_catalog(h1_package).get(receipt.get("source_ref")))
    if not catalog_source:
        _add(findings, "feedback_settlement.source_receipt_source_must_be_declared_h1_static_source")
    elif any(catalog_source.get(source_field) != receipt.get(receipt_field) for source_field, receipt_field in (
        ("published_at", "published_on"), ("url", "official_url"), ("source_type", "source_type"),
    )):
        _add(findings, "feedback_settlement.source_receipt_must_match_declared_static_source")
    elif catalog_source.get("issuer_id") != episode.get("issuer_id") or catalog_source.get("responsibility_unit_id") != _mapping(episode.get("responsibility_boundary")).get("responsibility_unit_id") or catalog_source.get("perimeter_id") != _mapping(episode.get("responsibility_boundary")).get("perimeter_id"):
        _add(findings, "feedback_settlement.source_receipt_responsibility_boundary_mismatch")
    allowed_cells = {entry.get("outcome_cell_id"): entry for entry in map(_mapping, _items(episode.get("outcome_cells")))}
    observations = [_closed(raw, _OBSERVATION_KEYS, f"feedback_settlement.observations[{index}]", findings) for index, raw in enumerate(_items(item.get("observations")))]
    if not observations:
        _add(findings, "feedback_settlement.observations_required")
    observed_cell_ids: list[str] = []
    matched = 0
    for index, observation in enumerate(observations):
        cell_id = _required_text(observation, "outcome_cell_id", f"feedback_settlement.observations[{index}]", findings)
        if cell_id not in set(_items(transition.get("outcome_cell_ids"))) or cell_id not in allowed_cells:
            _add(findings, f"feedback_settlement.observations[{index}].cell_not_in_frozen_transition")
        if observation.get("status") not in {"OBSERVED", "MEASUREMENT_MISMATCH", "CENSORED", "UNKNOWN", "NOT_DIAGNOSTIC"}:
            _add(findings, f"feedback_settlement.observations[{index}].status_invalid")
        _required_text(observation, "summary", f"feedback_settlement.observations[{index}]", findings)
        if observation.get("source_ref") != receipt.get("source_ref"):
            _add(findings, f"feedback_settlement.observations[{index}].source_must_match_custodian_receipt")
        if observation.get("status") == "OBSERVED" and observation.get("reported_value") in {None, ""}:
            _add(findings, f"feedback_settlement.observations[{index}].observed_status_requires_reported_value")
        cell = _mapping(allowed_cells.get(cell_id))
        contract = _mapping(cell.get("measurement_contract"))
        if receipt.get("source_type") not in _items(contract.get("allowed_source_types")):
            _add(findings, f"feedback_settlement.observations[{index}].source_type_not_allowed_by_frozen_measurement_contract")
        end = _instant(contract.get("window_end"), f"feedback_settlement.observations[{index}].measurement_contract.window_end", findings)
        if published is not None and end is not None and published > end.date():
            _add(findings, f"feedback_settlement.observations[{index}].source_must_be_within_frozen_measurement_window")
        observed_cell_ids.append(cell_id)
        matched += observation.get("status") == "OBSERVED"
    if observed_cell_ids != _items(transition.get("outcome_cell_ids")) or len(set(observed_cell_ids)) != len(observed_cell_ids):
        _add(findings, "feedback_settlement.observations_must_exactly_match_frozen_transition_cells")
    delta = [_closed(raw, _AGENDA_DELTA_KEYS, f"feedback_settlement.next_cutoff_agenda_delta[{index}]", findings) for index, raw in enumerate(_items(item.get("next_cutoff_agenda_delta")))]
    if not delta:
        _add(findings, "feedback_settlement.next_cutoff_agenda_delta_required")
    for index, change in enumerate(delta):
        for field in _AGENDA_DELTA_KEYS:
            _required_text(change, field, f"feedback_settlement.next_cutoff_agenda_delta[{index}]", findings)
        if change.get("target_cutoff_at") != transition.get("next_cutoff_at"):
            _add(findings, f"feedback_settlement.next_cutoff_agenda_delta[{index}].target_must_match_frozen_transition")
        if change.get("change_type") not in {"ADD_QUESTION", "CHANGE_EVIDENCE_ORDER", "ADD_BOUNDARY", "RETAIN_UNKNOWN"}:
            _add(findings, f"feedback_settlement.next_cutoff_agenda_delta[{index}].change_type_invalid")
    if matched and not delta:
        _add(findings, "feedback_settlement.material_observation_must_change_next_agenda")
    for path in _forbidden_paths(item, "feedback_settlement"):
        _add(findings, "feedback_settlement.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "feedback_settlement": deepcopy(item) if not findings else None}


def compile_feedback_read_model(
    settlement: Any, *, block: Any, pre_outcome_roster_freeze: Any, history_series: Any, h1_package: Any, episodes: list[Any], enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    """Project post-outcome effects locally without modifying the E0/E1 record."""
    validation = validate_feedback_settlement(
        settlement, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        history_series=history_series, h1_package=h1_package, episodes=episodes, enterprise_models=enterprise_models,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "feedback_read_model": None}
    block_item, settlement_item = _mapping(block), _mapping(settlement)
    transition = next((entry for entry in map(_mapping, _items(block_item.get("transition_roster"))) if entry.get("transition_id") == settlement_item.get("transition_id")), {})
    episode = next((entry for entry in map(_mapping, episodes) if entry.get("episode_id") == transition.get("episode_id")), {})
    episode_result = compile_enterprise_judgment_episode(
        episode, history_series=history_series, h1_package=h1_package, enterprise_models=enterprise_models,
    )
    if not episode_result["valid"]:
        return {"valid": False, "findings": ["feedback_read_model:bound_episode_invalid", *episode_result["findings"]], "feedback_read_model": None}
    outcome_status = {entry.get("outcome_cell_id"): entry.get("status") for entry in map(_mapping, _items(settlement_item.get("observations")))}
    non_diagnostic = {"MEASUREMENT_MISMATCH", "CENSORED", "UNKNOWN", "NOT_DIAGNOSTIC"}
    thread_rows = []
    claim_blockers: dict[str, list[dict[str, str]]] = {}
    for thread in map(_mapping, _items(_mapping(episode).get("mechanism_threads"))):
        blockers = [
            {"kind": "OUTCOME_SETTLEMENT", "ref": cell_id, "status": str(outcome_status[cell_id])}
            for cell_id in _items(thread.get("outcome_cell_ids"))
            if outcome_status.get(cell_id) in non_diagnostic
        ]
        for claim_id in _items(thread.get("claim_ids")):
            claim_blockers.setdefault(claim_id, []).extend(blockers)
        thread_rows.append({
            "thread_id": thread.get("thread_id"), "outcome_cell_ids": list(_items(thread.get("outcome_cell_ids"))),
            "allowed_outputs": ["RESEARCH_AGENDA"] if blockers else list(ALLOWED_PROBE_OUTPUTS), "blocked_by": blockers,
        })
    claim_rows = []
    for row in _items(_mapping(episode_result.get("episode_read_model")).get("claim_output_matrix")):
        item = _mapping(row)
        blockers = list(_items(item.get("blocked_by"))) + claim_blockers.get(item.get("claim_id"), [])
        claim_rows.append({
            "claim_id": item.get("claim_id"), "admission_level": item.get("admission_level"),
            "allowed_outputs": ["RESEARCH_AGENDA"] if blockers else list(_items(item.get("allowed_outputs"))),
            "blocked_by": blockers,
        })
    return {"valid": True, "findings": [], "feedback_read_model": {
        "settlement_id": settlement_item.get("settlement_id"), "episode_id": _mapping(episode).get("episode_id"),
        "claim_output_matrix": claim_rows, "thread_output_matrix": thread_rows,
        "original_episode_immutable": True, "investment_authorization": "NOT_AUTHORIZED",
    }}


def validate_round2_eligibility_register(
    register: Any, *, block: Any, pre_outcome_roster_freeze: Any, history_series: Any, h1_package: Any,
    completed_feedback_settlements: list[Any], source_block_episodes: list[Any], source_models: list[Any],
) -> dict[str, Any]:
    """Freeze source-bound eligibility for every roster row before round-two outcome access."""
    findings: list[str] = []
    freeze_result = validate_pre_outcome_roster_freeze(pre_outcome_roster_freeze, block=block)
    for finding in freeze_result["findings"]:
        _add(findings, "pre_outcome_roster_freeze:" + finding)
    item, block_item = _closed(register, _ELIGIBILITY_REGISTER_KEYS, "round2_eligibility_register", findings), _mapping(block)
    if item.get("schema_version") != ROUND2_ELIGIBILITY_SCHEMA_VERSION:
        _add(findings, "round2_eligibility_register.schema_version_invalid")
    for field in ("register_id", "block_id", "pre_outcome_freeze_ref", "selection_policy"):
        _required_text(item, field, "round2_eligibility_register", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND2_ELIGIBILITY_REGISTER" or item.get("claim_class") != "SOURCE_BOUND_ROSTER_ELIGIBILITY" or item.get("allowed_outputs") != ALLOWED_ELIGIBILITY_OUTPUTS:
        _add(findings, "round2_eligibility_register.object_or_permission_invalid")
    if item.get("block_id") != block_item.get("block_id") or item.get("pre_outcome_freeze_ref") != _mapping(pre_outcome_roster_freeze).get("freeze_id"):
        _add(findings, "round2_eligibility_register.must_bind_frozen_block_and_roster")
    if item.get("selection_policy") != "EARLIEST_UNSETTLED_FROZEN_ROW_AFTER_COMPLETED_QUEUE_WITH_UNSEEN_COMPANY_AND_CUTOFF_VISIBLE_LIFECYCLE_CONDITION":
        _add(findings, "round2_eligibility_register.policy_invalid")
    roster = list(map(_mapping, _items(block_item.get("company_cutoff_transition_roster"))))
    by_id = {entry.get("transition_id"): entry for entry in roster}
    derived_completed: list[str] = []
    derived_feedback_ids: list[tuple[int, str]] = []
    for index, settlement in enumerate(completed_feedback_settlements):
        settlement_result = validate_feedback_settlement(
            settlement, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
            history_series=history_series, h1_package=h1_package, episodes=source_block_episodes,
            enterprise_models=source_models,
        )
        for finding in settlement_result["findings"]:
            _add(findings, f"round2_selection.completed_feedback_settlements[{index}]:" + finding)
        settlement_item = _mapping(settlement)
        matching_rows = [
            entry for entry in roster
            if entry.get("company_id") == settlement_item.get("company_id")
            and entry.get("cutoff_at") == settlement_item.get("cutoff_at")
        ]
        if len(matching_rows) != 1:
            _add(findings, f"round2_eligibility_register.completed_feedback_settlements[{index}].must_map_to_one_frozen_row")
        elif matching_rows[0].get("transition_id") not in derived_completed:
            derived_completed.append(str(matching_rows[0].get("transition_id")))
            derived_feedback_ids.append((int(matching_rows[0].get("rank")), str(settlement_item.get("settlement_id"))))
    derived_completed.sort(key=lambda transition_id: int(_mapping(by_id.get(transition_id)).get("rank", 0)))
    derived_feedback_ids.sort()
    feedback_ids = _ids(item.get("completed_feedback_settlement_ids"), "round2_eligibility_register.completed_feedback_settlement_ids", findings)
    if feedback_ids != [feedback_id for _, feedback_id in derived_feedback_ids]:
        _add(findings, "round2_eligibility_register.completed_feedback_must_equal_actual_prior_feedback_projection")
    entries = [_closed(raw, _ELIGIBILITY_ENTRY_KEYS, f"round2_eligibility_register.entries[{index}]", findings) for index, raw in enumerate(_items(item.get("entries")))]
    expected_tuples = [
        (entry.get("rank"), entry.get("transition_id"), entry.get("company_id"), entry.get("company_cluster_id"), entry.get("cutoff_at"), entry.get("next_cutoff_at"))
        for entry in roster
    ]
    actual_tuples = [
        (entry.get("rank"), entry.get("transition_id"), entry.get("company_id"), entry.get("company_cluster_id"), entry.get("cutoff_at"), entry.get("next_cutoff_at"))
        for entry in entries
    ]
    if actual_tuples != expected_tuples:
        _add(findings, "round2_eligibility_register.entries_must_exactly_cover_frozen_roster_in_order")
    dispositions = {
        "COMPLETED_FEEDBACK", "EXCLUDED_COMPLETED_COMPANY",
        "EXCLUDED_NO_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION",
        "ELIGIBLE_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION", "NOT_REVIEWED_AFTER_FIRST_ELIGIBLE",
    }
    catalog = _source_catalog(h1_package)
    completed_companies = {by_id[transition_id].get("company_id") for transition_id in derived_completed if transition_id in by_id}
    eligible_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        disposition = entry.get("disposition")
        _required_text(entry, "disposition", f"round2_eligibility_register.entries[{index}]", findings)
        _required_text(entry, "rationale", f"round2_eligibility_register.entries[{index}]", findings)
        if disposition not in dispositions:
            _add(findings, f"round2_eligibility_register.entries[{index}].disposition_invalid")
        refs = _ids(
            entry.get("reviewed_source_refs"), f"round2_eligibility_register.entries[{index}].reviewed_source_refs", findings,
            required=disposition in {"EXCLUDED_NO_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION", "ELIGIBLE_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION"},
        )
        try:
            cutoff_day = date.fromisoformat(str(entry.get("cutoff_at"))[:10])
        except ValueError:
            _add(findings, f"round2_eligibility_register.entries[{index}].cutoff_at_must_start_with_iso8601_date")
            cutoff_day = None
        for ref in refs:
            source = _mapping(catalog.get(ref))
            try:
                published_day = date.fromisoformat(str(source.get("published_at")))
            except ValueError:
                published_day = None
            if not source or source.get("issuer_id") != f"ISSUER:{entry.get('company_id')}" or (cutoff_day is not None and (published_day is None or published_day >= cutoff_day)):
                _add(findings, f"round2_eligibility_register.entries[{index}].source_must_match_company_and_cutoff")
        transition_id = entry.get("transition_id")
        if disposition == "COMPLETED_FEEDBACK" and transition_id not in derived_completed:
            _add(findings, f"round2_eligibility_register.entries[{index}].completed_disposition_must_match_actual_feedback")
        if disposition != "COMPLETED_FEEDBACK" and transition_id in derived_completed:
            _add(findings, f"round2_eligibility_register.entries[{index}].actual_feedback_must_be_marked_completed")
        if disposition == "EXCLUDED_COMPLETED_COMPANY" and entry.get("company_id") not in completed_companies:
            _add(findings, f"round2_eligibility_register.entries[{index}].completed_company_exclusion_invalid")
        if disposition == "ELIGIBLE_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION":
            eligible_entries.append(entry)
    if len(eligible_entries) != 1:
        _add(findings, "round2_eligibility_register.must_name_exactly_one_first_eligible_row")
    first_eligible = eligible_entries[0] if len(eligible_entries) == 1 else {}
    if first_eligible:
        first_rank = first_eligible.get("rank")
        for entry in entries:
            if isinstance(entry.get("rank"), int) and entry["rank"] < first_rank and entry.get("disposition") in {"ELIGIBLE_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION", "NOT_REVIEWED_AFTER_FIRST_ELIGIBLE"}:
                _add(findings, "round2_eligibility_register.each_earlier_row_must_have_a_valid_exclusion")
        for entry in entries:
            if isinstance(entry.get("rank"), int) and entry["rank"] > first_rank and entry.get("disposition") != "NOT_REVIEWED_AFTER_FIRST_ELIGIBLE":
                _add(findings, "round2_eligibility_register.rows_after_first_eligible_must_not_drive_selection")
    binding = _closed(item.get("first_eligible_target_binding"), _ELIGIBILITY_TARGET_BINDING_KEYS, "round2_eligibility_register.first_eligible_target_binding", findings)
    for field in ("transition_id", "target_episode_id"):
        _required_text(binding, field, "round2_eligibility_register.first_eligible_target_binding", findings)
    _ids(binding.get("outcome_cell_ids"), "round2_eligibility_register.first_eligible_target_binding.outcome_cell_ids", findings)
    if binding.get("transition_id") != first_eligible.get("transition_id"):
        _add(findings, "round2_eligibility_register.target_binding_must_match_first_eligible_row")
    _validate_roles(item.get("roles"), expected=None, path="round2_eligibility_register.roles", findings=findings)
    for path in _forbidden_paths(item, "round2_eligibility_register"):
        _add(findings, "round2_eligibility_register.forbidden_field:" + path)
    return {
        "valid": not findings, "findings": findings,
        "round2_eligibility_register": deepcopy(item) if not findings else None,
        "derived_completed_transition_ids": derived_completed,
    }


def validate_round2_transition_selection(
    selection: Any, *, eligibility_register: Any, block: Any, pre_outcome_roster_freeze: Any, history_series: Any, h1_package: Any,
    completed_feedback_settlements: list[Any], source_block_episodes: list[Any], source_models: list[Any],
) -> dict[str, Any]:
    """Derive the round-two selection from the frozen source-bound eligibility register."""
    findings: list[str] = []
    register_result = validate_round2_eligibility_register(
        eligibility_register, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        history_series=history_series, h1_package=h1_package,
        completed_feedback_settlements=completed_feedback_settlements,
        source_block_episodes=source_block_episodes, source_models=source_models,
    )
    for finding in register_result["findings"]:
        _add(findings, "round2_eligibility_register:" + finding)
    item, block_item, register_item = (
        _closed(selection, _ROUND2_SELECTION_KEYS, "round2_selection", findings), _mapping(block), _mapping(eligibility_register),
    )
    if item.get("schema_version") != ROUND2_SELECTION_SCHEMA_VERSION:
        _add(findings, "round2_selection.schema_version_invalid")
    for field in ("selection_id", "block_id", "pre_outcome_freeze_ref", "eligibility_register_ref", "selection_policy", "selected_transition_id", "company_id", "company_cluster_id", "cutoff_at", "next_cutoff_at", "target_episode_id"):
        _required_text(item, field, "round2_selection", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND2_TRANSITION_SELECTION" or item.get("claim_class") != "OUTCOME_BLIND_ROSTER_CONTINUATION":
        _add(findings, "round2_selection.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ["PRE_OUTCOME_APPLICATION_ONLY"] or item.get("outcome_access_status") != "SEALED":
        _add(findings, "round2_selection.permissions_invalid")
    if item.get("block_id") != block_item.get("block_id") or item.get("pre_outcome_freeze_ref") != _mapping(pre_outcome_roster_freeze).get("freeze_id") or item.get("eligibility_register_ref") != register_item.get("register_id"):
        _add(findings, "round2_selection.must_bind_frozen_block_roster_and_eligibility_register")
    if item.get("selection_policy") != register_item.get("selection_policy"):
        _add(findings, "round2_selection.policy_must_match_eligibility_register")
    roster = list(map(_mapping, _items(block_item.get("company_cutoff_transition_roster"))))
    by_id = {entry.get("transition_id"): entry for entry in roster}
    completed = _ids(item.get("completed_company_cutoff_transition_ids"), "round2_selection.completed_company_cutoff_transition_ids", findings)
    derived_completed = _items(register_result.get("derived_completed_transition_ids"))
    if completed != derived_completed:
        _add(findings, "round2_selection.completed_transitions_must_equal_actual_prior_feedback_projection")
    if any(transition_id not in by_id for transition_id in completed):
        _add(findings, "round2_selection.completed_transition_not_in_frozen_roster")
    selected = _mapping(by_id.get(item.get("selected_transition_id")))
    if not selected or any(item.get(field) != selected.get(field) for field in ("company_id", "company_cluster_id", "cutoff_at", "next_cutoff_at")) or item.get("selected_rank") != selected.get("rank"):
        _add(findings, "round2_selection.selected_tuple_must_match_frozen_roster")
    if selected.get("transition_id") in completed:
        _add(findings, "round2_selection.selected_transition_must_be_unsettled")
    completed_companies = {by_id[transition_id].get("company_id") for transition_id in completed if transition_id in by_id}
    if selected.get("company_id") in completed_companies:
        _add(findings, "round2_selection.target_company_must_differ_from_completed_feedback_companies")
    prior_rows = [_closed(raw, _INELIGIBLE_ROW_KEYS, f"round2_selection.ineligible_prior_rows[{index}]", findings) for index, raw in enumerate(_items(item.get("ineligible_prior_rows")))]
    reason_by_disposition = {
        "EXCLUDED_COMPLETED_COMPANY": "SAME_COMPANY_AS_COMPLETED_FEEDBACK",
        "EXCLUDED_NO_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION": "NO_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION",
    }
    register_entries = list(map(_mapping, _items(register_item.get("entries"))))
    expected_prior = [
        (entry.get("rank"), entry.get("transition_id"), reason_by_disposition.get(entry.get("disposition")))
        for entry in register_entries
        if isinstance(entry.get("rank"), int) and entry["rank"] < selected.get("rank", 0)
        and entry.get("disposition") in reason_by_disposition
    ]
    if [(entry.get("rank"), entry.get("transition_id"), entry.get("reason")) for entry in prior_rows] != expected_prior:
        _add(findings, "round2_selection.must_account_for_every_earlier_unsettled_row")
    for index, entry in enumerate(prior_rows):
        _required_text(entry, "reason", f"round2_selection.ineligible_prior_rows[{index}]", findings)
        if entry.get("reason") not in {"SAME_COMPANY_AS_COMPLETED_FEEDBACK", "NO_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION"}:
            _add(findings, f"round2_selection.ineligible_prior_rows[{index}].reason_invalid")
    binding = _mapping(register_item.get("first_eligible_target_binding"))
    first_entry = next((entry for entry in register_entries if entry.get("transition_id") == binding.get("transition_id")), {})
    source_refs = _ids(item.get("cutoff_visible_evidence_refs"), "round2_selection.cutoff_visible_evidence_refs", findings)
    if item.get("selected_transition_id") != binding.get("transition_id") or item.get("target_episode_id") != binding.get("target_episode_id") or _items(item.get("outcome_cell_ids")) != _items(binding.get("outcome_cell_ids")) or source_refs != _items(first_entry.get("reviewed_source_refs")):
        _add(findings, "round2_selection.must_be_exact_derivation_of_first_eligible_binding")
    _validate_roles(item.get("roles"), expected=_mapping(register_item.get("roles")), path="round2_selection.roles", findings=findings)
    for path in _forbidden_paths(item, "round2_selection"):
        _add(findings, "round2_selection.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "round2_selection": deepcopy(item) if not findings else None}


def _validate_application_fields(item: dict[str, Any], *, target_episode: dict[str, Any], source_agenda_change_id: str, findings: list[str]) -> None:
    baseline = [_closed(raw, _APPLICATION_FIELD_KEYS, f"transfer_application.baseline_before_learning[{index}]", findings) for index, raw in enumerate(_items(item.get("baseline_before_learning")))]
    enhanced = [_closed(raw, _APPLICATION_FIELD_KEYS, f"transfer_application.enhanced_after_learning[{index}]", findings) for index, raw in enumerate(_items(item.get("enhanced_after_learning")))]
    if not baseline or len(baseline) != len(enhanced):
        _add(findings, "transfer_application.baseline_and_enhanced_fields_must_be_nonempty_and_aligned")
    target_claim_ids = {entry.get("claim_id") for entry in map(_mapping, _items(target_episode.get("claims")))}
    baseline_by_id = {entry.get("field_id"): entry for entry in baseline}
    baseline_ids = [entry.get("field_id") for entry in baseline]
    enhanced_ids = [entry.get("field_id") for entry in enhanced]
    if len(set(baseline_ids)) != len(baseline_ids) or enhanced_ids != baseline_ids:
        _add(findings, "transfer_application.fields_must_preserve_unique_baseline_order")
    for index, before in enumerate(baseline):
        for field in _APPLICATION_FIELD_KEYS:
            if field == "claim_ids":
                _ids(before.get(field), f"transfer_application.baseline_before_learning[{index}].{field}", findings)
            else:
                _required_text(before, field, f"transfer_application.baseline_before_learning[{index}]", findings)
        if before.get("measurement_gate") != "NO_PERIMETER_BRIDGE_GATE":
            _add(findings, f"transfer_application.baseline_before_learning[{index}].baseline_gate_invalid")
        if any(claim_id not in target_claim_ids for claim_id in _items(before.get("claim_ids"))):
            _add(findings, f"transfer_application.baseline_before_learning[{index}].claim_unknown_in_target_episode")
    for index, after in enumerate(enhanced):
        before = _mapping(baseline_by_id.get(after.get("field_id")))
        if not before:
            _add(findings, f"transfer_application.enhanced_after_learning[{index}].field_not_in_baseline")
            continue
        if any(after.get(field) != before.get(field) for field in _APPLICATION_FIELD_KEYS - {"measurement_gate"}):
            _add(findings, f"transfer_application.enhanced_after_learning[{index}].may_only_add_measurement_gate")
        if after.get("measurement_gate") != "REQUIRE_PERIMETER_BRIDGE_BEFORE_INTERPRETING_SAME_BOUNDARY_FIELD":
            _add(findings, f"transfer_application.enhanced_after_learning[{index}].enhanced_gate_invalid")
    deltas = [_closed(raw, _FIELD_DELTA_KEYS, f"transfer_application.field_delta[{index}]", findings) for index, raw in enumerate(_items(item.get("field_delta")))]
    if [entry.get("field_id") for entry in deltas] != baseline_ids:
        _add(findings, "transfer_application.field_delta_must_cover_each_changed_field_once")
    for index, delta in enumerate(deltas):
        for field in _FIELD_DELTA_KEYS:
            _required_text(delta, field, f"transfer_application.field_delta[{index}]", findings)
        if delta.get("change_kind") != "ADD_MEASUREMENT_GATE" or delta.get("baseline_gate") != "NO_PERIMETER_BRIDGE_GATE" or delta.get("enhanced_gate") != "REQUIRE_PERIMETER_BRIDGE_BEFORE_INTERPRETING_SAME_BOUNDARY_FIELD" or delta.get("reason_ref") != source_agenda_change_id:
            _add(findings, f"transfer_application.field_delta[{index}].must_be_perimeter_first_change_from_source_agenda")


def validate_transfer_application_receipt(
    application: Any, *, selection: Any, eligibility_register: Any, block: Any, pre_outcome_roster_freeze: Any, target_episode: Any, target_models: list[Any],
    history_series: Any, h1_package: Any, source_feedback_settlement: Any, source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Validate a cross-company measurement-method application before target outcome access."""
    findings: list[str] = []
    selection_result = validate_round2_transition_selection(
        selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        history_series=history_series, h1_package=h1_package,
        completed_feedback_settlements=completed_feedback_settlements,
        source_block_episodes=source_block_episodes, source_models=source_models,
    )
    for finding in selection_result["findings"]:
        _add(findings, "round2_selection:" + finding)
    source_result = validate_feedback_settlement(
        source_feedback_settlement, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        history_series=history_series, h1_package=h1_package, episodes=source_block_episodes, enterprise_models=source_models,
    )
    for finding in source_result["findings"]:
        _add(findings, "source_feedback_settlement:" + finding)
    target_result = validate_enterprise_judgment_episode(target_episode, history_series=history_series, h1_package=h1_package, enterprise_models=target_models)
    for finding in target_result["findings"]:
        _add(findings, "target_episode:" + finding)
    item, target_item, selection_item, source_item = _closed(application, _APPLICATION_KEYS, "transfer_application", findings), _mapping(target_episode), _mapping(selection), _mapping(source_feedback_settlement)
    if item.get("schema_version") != TRANSFER_APPLICATION_SCHEMA_VERSION:
        _add(findings, "transfer_application.schema_version_invalid")
    for field in ("application_id", "block_id", "pre_outcome_freeze_ref", "selection_ref", "source_feedback_id", "source_observation_cell_id", "source_agenda_change_id", "learned_rule_id", "target_episode_id", "target_outcome_access"):
        _required_text(item, field, "transfer_application", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_TRANSFER_APPLICATION" or item.get("claim_class") != "CROSS_COMPANY_MEASUREMENT_METHOD_APPLICATION" or item.get("allowed_outputs") != ALLOWED_APPLICATION_OUTPUTS:
        _add(findings, "transfer_application.object_or_permission_invalid")
    if item.get("block_id") != _mapping(block).get("block_id") or item.get("pre_outcome_freeze_ref") != _mapping(pre_outcome_roster_freeze).get("freeze_id") or item.get("selection_ref") != selection_item.get("selection_id") or item.get("target_episode_id") != target_item.get("episode_id"):
        _add(findings, "transfer_application.bindings_must_match_frozen_target")
    source_observation = next((entry for entry in map(_mapping, _items(source_item.get("observations"))) if entry.get("outcome_cell_id") == item.get("source_observation_cell_id")), {})
    source_delta = next((entry for entry in map(_mapping, _items(source_item.get("next_cutoff_agenda_delta"))) if entry.get("change_id") == item.get("source_agenda_change_id")), {})
    if item.get("source_feedback_id") != source_item.get("settlement_id") or not source_observation or source_observation.get("status") != "MEASUREMENT_MISMATCH" or not source_delta or source_delta.get("change_type") != "ADD_BOUNDARY":
        _add(findings, "transfer_application.source_must_be_real_mismatch_with_boundary_agenda_change")
    if item.get("learned_rule_id") != "PERIMETER_FIRST_MEASUREMENT_GATE" or item.get("target_outcome_access") != "SEALED" or item.get("frozen_before_outcome_access") is not True:
        _add(findings, "transfer_application.must_remain_pre_outcome_perimeter_first_method_change")
    if target_item.get("company_id") == source_item.get("company_id") or target_item.get("company_id") != selection_item.get("company_id") or target_item.get("cutoff_at") != selection_item.get("cutoff_at"):
        _add(findings, "transfer_application.target_must_be_different_company_and_match_selection")
    _validate_application_fields(item, target_episode=target_item, source_agenda_change_id=str(item.get("source_agenda_change_id")), findings=findings)
    roles = _validate_roles(item.get("roles"), expected=None, path="transfer_application.roles", findings=findings)
    if roles.get("judgment_owner_id") != _mapping(target_item.get("roles")).get("judgment_owner_id") or roles.get("outcome_custodian_id") != _mapping(target_item.get("roles")).get("outcome_custodian_id"):
        _add(findings, "transfer_application.owner_and_custodian_must_match_target_episode")
    for path in _forbidden_paths(item, "transfer_application"):
        _add(findings, "transfer_application.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "transfer_application": deepcopy(item) if not findings else None}


def validate_continuation_feedback_settlement(
    settlement: Any, *, application: Any, selection: Any, eligibility_register: Any, block: Any, pre_outcome_roster_freeze: Any, target_episode: Any,
    target_models: list[Any], history_series: Any, h1_package: Any, source_feedback_settlement: Any,
    source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Settle the selected round-two cell while retaining the original block unchanged."""
    findings: list[str] = []
    application_result = validate_transfer_application_receipt(
        application, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        target_episode=target_episode, target_models=target_models, history_series=history_series, h1_package=h1_package,
        source_feedback_settlement=source_feedback_settlement, source_block_episodes=source_block_episodes, source_models=source_models,
        completed_feedback_settlements=completed_feedback_settlements,
    )
    for finding in application_result["findings"]:
        _add(findings, "transfer_application:" + finding)
    item, app, selection_item, episode = _closed(settlement, _CONTINUATION_SETTLEMENT_KEYS, "continuation_feedback_settlement", findings), _mapping(application), _mapping(selection), _mapping(target_episode)
    if item.get("schema_version") != CONTINUATION_SETTLEMENT_SCHEMA_VERSION:
        _add(findings, "continuation_feedback_settlement.schema_version_invalid")
    for field in ("settlement_id", "application_ref", "selection_ref", "company_id", "cutoff_at", "outcome_custodian_id"):
        _required_text(item, field, "continuation_feedback_settlement", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_CONTINUATION_FEEDBACK_SETTLEMENT" or item.get("claim_class") != "CONTRACT_MATCHED_PREQUENTIAL_FEEDBACK" or item.get("allowed_outputs") != ALLOWED_SETTLEMENT_OUTPUTS:
        _add(findings, "continuation_feedback_settlement.object_or_permission_invalid")
    if item.get("original_episode_immutable") is not True:
        _add(findings, "continuation_feedback_settlement.must_preserve_original_episode_immutable")
    if item.get("application_ref") != app.get("application_id") or item.get("selection_ref") != selection_item.get("selection_id") or item.get("company_id") != episode.get("company_id") or item.get("cutoff_at") != episode.get("cutoff_at") or item.get("outcome_custodian_id") != _mapping(episode.get("roles")).get("outcome_custodian_id"):
        _add(findings, "continuation_feedback_settlement.must_match_frozen_application_and_target")
    receipt = _closed(item.get("source_receipt"), _SOURCE_RECEIPT_KEYS, "continuation_feedback_settlement.source_receipt", findings)
    for field in _SOURCE_RECEIPT_KEYS:
        _required_text(receipt, field, "continuation_feedback_settlement.source_receipt", findings)
    cutoff = _instant(item.get("cutoff_at"), "continuation_feedback_settlement.cutoff_at", findings)
    published = _date(receipt.get("published_on"), "continuation_feedback_settlement.source_receipt.published_on", findings)
    if cutoff is not None and published is not None and published <= cutoff.date():
        _add(findings, "continuation_feedback_settlement.source_must_be_post_cutoff")
    if receipt.get("custodian_access") != "OUTCOME_ONLY" or receipt.get("availability_precision") != "DATE":
        _add(findings, "continuation_feedback_settlement.source_receipt_access_or_precision_invalid")
    catalog_source = _mapping(_source_catalog(h1_package).get(receipt.get("source_ref")))
    if not catalog_source or any(catalog_source.get(source_field) != receipt.get(receipt_field) for source_field, receipt_field in (("published_at", "published_on"), ("url", "official_url"), ("source_type", "source_type"))):
        _add(findings, "continuation_feedback_settlement.source_receipt_must_match_declared_static_source")
    elif catalog_source.get("issuer_id") != episode.get("issuer_id") or catalog_source.get("responsibility_unit_id") != _mapping(episode.get("responsibility_boundary")).get("responsibility_unit_id") or catalog_source.get("perimeter_id") != _mapping(episode.get("responsibility_boundary")).get("perimeter_id"):
        _add(findings, "continuation_feedback_settlement.source_responsibility_boundary_mismatch")
    allowed_cells = {entry.get("outcome_cell_id"): entry for entry in map(_mapping, _items(episode.get("outcome_cells")))}
    selected_cells = _items(selection_item.get("outcome_cell_ids"))
    observations = [_closed(raw, _OBSERVATION_KEYS, f"continuation_feedback_settlement.observations[{index}]", findings) for index, raw in enumerate(_items(item.get("observations")))]
    seen_cells: list[str] = []
    for index, observation in enumerate(observations):
        cell_id = _required_text(observation, "outcome_cell_id", f"continuation_feedback_settlement.observations[{index}]", findings)
        if cell_id not in selected_cells or cell_id not in allowed_cells:
            _add(findings, f"continuation_feedback_settlement.observations[{index}].cell_not_in_frozen_selection")
        if observation.get("status") not in {"OBSERVED", "MEASUREMENT_MISMATCH", "CENSORED", "UNKNOWN", "NOT_DIAGNOSTIC"}:
            _add(findings, f"continuation_feedback_settlement.observations[{index}].status_invalid")
        if observation.get("source_ref") != receipt.get("source_ref"):
            _add(findings, f"continuation_feedback_settlement.observations[{index}].source_must_match_receipt")
        _required_text(observation, "summary", f"continuation_feedback_settlement.observations[{index}]", findings)
        if observation.get("status") == "OBSERVED" and observation.get("reported_value") in {None, ""}:
            _add(findings, f"continuation_feedback_settlement.observations[{index}].observed_requires_reported_value")
        contract = _mapping(_mapping(allowed_cells.get(cell_id)).get("measurement_contract"))
        if receipt.get("source_type") not in _items(contract.get("allowed_source_types")):
            _add(findings, f"continuation_feedback_settlement.observations[{index}].source_type_not_allowed")
        end = _instant(contract.get("window_end"), f"continuation_feedback_settlement.observations[{index}].window_end", findings)
        if published is not None and end is not None and published > end.date():
            _add(findings, f"continuation_feedback_settlement.observations[{index}].source_outside_measurement_window")
        seen_cells.append(cell_id)
    if seen_cells != selected_cells or len(set(seen_cells)) != len(seen_cells):
        _add(findings, "continuation_feedback_settlement.observations_must_exactly_match_selected_cells")
    delta = [_closed(raw, _AGENDA_DELTA_KEYS, f"continuation_feedback_settlement.next_cutoff_agenda_delta[{index}]", findings) for index, raw in enumerate(_items(item.get("next_cutoff_agenda_delta")))]
    if not delta:
        _add(findings, "continuation_feedback_settlement.next_cutoff_agenda_delta_required")
    for index, change in enumerate(delta):
        for field in _AGENDA_DELTA_KEYS:
            _required_text(change, field, f"continuation_feedback_settlement.next_cutoff_agenda_delta[{index}]", findings)
        if change.get("target_cutoff_at") != selection_item.get("next_cutoff_at") or change.get("change_type") not in {"ADD_QUESTION", "CHANGE_EVIDENCE_ORDER", "ADD_BOUNDARY", "RETAIN_UNKNOWN"}:
            _add(findings, f"continuation_feedback_settlement.next_cutoff_agenda_delta[{index}].invalid_target_or_type")
    for path in _forbidden_paths(item, "continuation_feedback_settlement"):
        _add(findings, "continuation_feedback_settlement.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "continuation_feedback_settlement": deepcopy(item) if not findings else None}


def compile_continuation_feedback_read_model(
    settlement: Any, *, application: Any, selection: Any, eligibility_register: Any, block: Any, pre_outcome_roster_freeze: Any, target_episode: Any,
    target_models: list[Any], history_series: Any, h1_package: Any, source_feedback_settlement: Any,
    source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    validation = validate_continuation_feedback_settlement(
        settlement, application=application, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        target_episode=target_episode, target_models=target_models, history_series=history_series, h1_package=h1_package,
        source_feedback_settlement=source_feedback_settlement, source_block_episodes=source_block_episodes, source_models=source_models,
        completed_feedback_settlements=completed_feedback_settlements,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "continuation_feedback_read_model": None}
    episode_result = compile_enterprise_judgment_episode(target_episode, history_series=history_series, h1_package=h1_package, enterprise_models=target_models)
    statuses = {entry.get("outcome_cell_id"): entry.get("status") for entry in map(_mapping, _items(_mapping(settlement).get("observations")))}
    non_diagnostic = {"MEASUREMENT_MISMATCH", "CENSORED", "UNKNOWN", "NOT_DIAGNOSTIC"}
    thread_blockers: dict[str, list[dict[str, str]]] = {}
    for thread in map(_mapping, _items(_mapping(target_episode).get("mechanism_threads"))):
        blockers = [{"kind": "OUTCOME_SETTLEMENT", "ref": cell_id, "status": str(statuses[cell_id])} for cell_id in _items(thread.get("outcome_cell_ids")) if statuses.get(cell_id) in non_diagnostic]
        for claim_id in _items(thread.get("claim_ids")):
            thread_blockers.setdefault(claim_id, []).extend(blockers)
    claim_rows = []
    for row in _items(_mapping(episode_result.get("episode_read_model")).get("claim_output_matrix")):
        base = _mapping(row)
        blockers = list(_items(base.get("blocked_by"))) + thread_blockers.get(base.get("claim_id"), [])
        claim_rows.append({"claim_id": base.get("claim_id"), "admission_level": base.get("admission_level"), "allowed_outputs": ["RESEARCH_AGENDA"] if blockers else list(_items(base.get("allowed_outputs"))), "blocked_by": blockers})
    return {"valid": True, "findings": [], "continuation_feedback_read_model": {"settlement_id": _mapping(settlement).get("settlement_id"), "episode_id": _mapping(target_episode).get("episode_id"), "claim_output_matrix": claim_rows, "original_episode_immutable": True, "investment_authorization": "NOT_AUTHORIZED"}}


def validate_transfer_application_review(
    review: Any, *, application: Any, continuation_settlement: Any, selection: Any, eligibility_register: Any, block: Any, pre_outcome_roster_freeze: Any,
    target_episode: Any, target_models: list[Any], history_series: Any, h1_package: Any, source_feedback_settlement: Any,
    source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Independent adjudication of method transfer, explicitly not enterprise transfer."""
    findings: list[str] = []
    continuation_result = validate_continuation_feedback_settlement(
        continuation_settlement, application=application, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        target_episode=target_episode, target_models=target_models, history_series=history_series, h1_package=h1_package,
        source_feedback_settlement=source_feedback_settlement, source_block_episodes=source_block_episodes, source_models=source_models,
        completed_feedback_settlements=completed_feedback_settlements,
    )
    for finding in continuation_result["findings"]:
        _add(findings, "continuation_feedback_settlement:" + finding)
    item, app, source = _closed(review, _TRANSFER_REVIEW_KEYS, "transfer_application_review", findings), _mapping(application), _mapping(source_feedback_settlement)
    if item.get("schema_version") != TRANSFER_REVIEW_SCHEMA_VERSION:
        _add(findings, "transfer_application_review.schema_version_invalid")
    for field in ("review_id", "application_ref", "source_feedback_id", "continuation_settlement_id", "reviewer_id", "verdict", "materiality_statement", "causal_trace_statement", "prohibited_conclusion", "transfer_status"):
        _required_text(item, field, "transfer_application_review", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_TRANSFER_APPLICATION_REVIEW" or item.get("claim_class") != "INDEPENDENT_METHOD_TRANSFER_ADJUDICATION" or item.get("allowed_outputs") != ALLOWED_TRANSFER_REVIEW_OUTPUTS:
        _add(findings, "transfer_application_review.object_or_permission_invalid")
    if item.get("application_ref") != app.get("application_id") or item.get("source_feedback_id") != source.get("settlement_id") or item.get("continuation_settlement_id") != _mapping(continuation_settlement).get("settlement_id"):
        _add(findings, "transfer_application_review.bindings_must_match_inputs")
    application_roles = _mapping(app.get("roles"))
    if item.get("reviewer_id") in set(application_roles.values()):
        _add(findings, "transfer_application_review.reviewer_must_be_independent")
    if item.get("verdict") != "MATERIAL_METHOD_CHANGE_CAUSALLY_ATTRIBUTABLE" or item.get("transfer_status") != "TRANSFER_CANDIDATE_CREATED":
        _add(findings, "transfer_application_review.verdict_or_status_invalid")
    if item.get("prohibited_conclusion") != "NO_ENTERPRISE_PERFORMANCE_ACTION_CAUSALITY_OR_INVESTMENT_CONCLUSION":
        _add(findings, "transfer_application_review.must_deny_enterprise_and_investment_conclusion")
    for path in _forbidden_paths(item, "transfer_application_review"):
        _add(findings, "transfer_application_review.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "transfer_application_review": deepcopy(item) if not findings else None}


def validate_round2_completion_receipt(
    completion: Any, *, review: Any, application: Any, continuation_settlement: Any, selection: Any, eligibility_register: Any, block: Any,
    pre_outcome_roster_freeze: Any, target_episode: Any, target_models: list[Any], history_series: Any, h1_package: Any,
    source_feedback_settlement: Any, source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Allow the two narrow round-two statuses only after their bound evidence exists."""
    findings: list[str] = []
    review_result = validate_transfer_application_review(
        review, application=application, continuation_settlement=continuation_settlement, selection=selection, eligibility_register=eligibility_register,
        block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze, target_episode=target_episode,
        target_models=target_models, history_series=history_series, h1_package=h1_package,
        source_feedback_settlement=source_feedback_settlement, source_block_episodes=source_block_episodes,
        source_models=source_models, completed_feedback_settlements=completed_feedback_settlements,
    )
    for finding in review_result["findings"]:
        _add(findings, "transfer_application_review:" + finding)
    item, block_item, review_item, settlement_item = (
        _closed(completion, _ROUND2_COMPLETION_KEYS, "round2_completion", findings), _mapping(block),
        _mapping(review), _mapping(continuation_settlement),
    )
    if item.get("schema_version") != ROUND2_COMPLETION_SCHEMA_VERSION:
        _add(findings, "round2_completion.schema_version_invalid")
    for field in ("completion_id", "block_id", "settlement_id", "review_id", "feedback_turn_status", "transfer_status"):
        _required_text(item, field, "round2_completion", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND2_COMPLETION_RECEIPT" or item.get("claim_class") != "FEEDBACK_TURN_AND_TRANSFER_STATUS" or item.get("allowed_outputs") != ALLOWED_ROUND2_COMPLETION_OUTPUTS:
        _add(findings, "round2_completion.object_or_permission_invalid")
    if item.get("block_id") != block_item.get("block_id") or item.get("settlement_id") != settlement_item.get("settlement_id") or item.get("review_id") != review_item.get("review_id"):
        _add(findings, "round2_completion.bindings_must_match_settlement_and_review")
    if item.get("feedback_turn_status") != "REAL_FEEDBACK_TURN_2_COMPLETED" or item.get("transfer_status") != "TRANSFER_CANDIDATE_CREATED":
        _add(findings, "round2_completion.statuses_must_remain_narrow")
    for path in _forbidden_paths(item, "round2_completion"):
        _add(findings, "round2_completion.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "round2_completion": deepcopy(item) if not findings else None}


def _validate_round2_chain_for_round3(
    round2_chain: Any, *, block: Any, pre_outcome_roster_freeze: Any, history_series: Any, h1_package: Any,
    source_block_episodes: list[Any], source_models: list[Any], completed_feedback_settlements: list[Any],
) -> tuple[dict[str, Any], list[str]]:
    findings: list[str] = []
    chain = _closed(round2_chain, _ROUND2_CHAIN_KEYS, "round3.round2_chain", findings)
    result = validate_round2_completion_receipt(
        chain.get("completion"), review=chain.get("review"), application=chain.get("application"),
        continuation_settlement=chain.get("continuation_settlement"), selection=chain.get("selection"),
        eligibility_register=chain.get("eligibility_register"), block=block,
        pre_outcome_roster_freeze=pre_outcome_roster_freeze, target_episode=chain.get("target_episode"),
        target_models=_items(chain.get("target_models")), history_series=history_series, h1_package=h1_package,
        source_feedback_settlement=chain.get("source_feedback_settlement"), source_block_episodes=source_block_episodes,
        source_models=source_models, completed_feedback_settlements=completed_feedback_settlements,
    )
    for finding in result["findings"]:
        _add(findings, "round3.round2_chain:" + finding)
    return chain, findings


def validate_round3_method_transfer_selection(
    selection: Any, *, round2_chain: Any, block: Any, pre_outcome_roster_freeze: Any, history_series: Any,
    h1_package: Any, source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Select the earliest unseen company without screening for an outcome feature."""
    chain, findings = _validate_round2_chain_for_round3(
        round2_chain, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        history_series=history_series, h1_package=h1_package, source_block_episodes=source_block_episodes,
        source_models=source_models, completed_feedback_settlements=completed_feedback_settlements,
    )
    item = _closed(selection, _ROUND3_SELECTION_KEYS, "round3_selection", findings)
    if item.get("schema_version") != ROUND3_SELECTION_SCHEMA_VERSION:
        _add(findings, "round3_selection.schema_version_invalid")
    for field in (
        "selection_id", "block_id", "pre_outcome_freeze_ref", "round2_completion_ref", "selection_policy",
        "selected_transition_id", "company_id", "company_cluster_id", "cutoff_at", "next_cutoff_at",
        "target_episode_id", "outcome_access_status",
    ):
        _required_text(item, field, "round3_selection", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND3_METHOD_TRANSFER_SELECTION" or item.get("claim_class") != "OUTCOME_BLIND_UNIVERSAL_METHOD_APPLICATION":
        _add(findings, "round3_selection.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_ROUND3_SELECTION_OUTPUTS or item.get("outcome_access_status") != "SEALED":
        _add(findings, "round3_selection.permissions_invalid")
    expected_policy = "EARLIEST_UNSETTLED_FROZEN_ROW_WITH_UNSEEN_COMPANY_NO_OUTCOME_FEATURE_FILTER"
    if item.get("selection_policy") != expected_policy:
        _add(findings, "round3_selection.policy_must_not_screen_lifecycle_or_outcome_features")
    if (
        item.get("block_id") != _mapping(block).get("block_id")
        or item.get("pre_outcome_freeze_ref") != _mapping(pre_outcome_roster_freeze).get("freeze_id")
        or item.get("round2_completion_ref") != _mapping(chain.get("completion")).get("completion_id")
    ):
        _add(findings, "round3_selection.must_bind_frozen_roster_and_round2_completion")

    roster = list(map(_mapping, _items(_mapping(block).get("company_cutoff_transition_roster"))))
    settled = [*map(_mapping, completed_feedback_settlements), _mapping(chain.get("continuation_settlement"))]
    completed_companies = {entry.get("company_id") for entry in settled if _text(entry.get("company_id"))}
    first_rank_by_company = {
        company_id: min(int(row.get("rank", 0)) for row in roster if row.get("company_id") == company_id)
        for company_id in completed_companies
    }
    derived_company_ids = sorted(completed_companies, key=lambda company_id: first_rank_by_company[company_id])
    if _items(item.get("completed_company_ids")) != derived_company_ids:
        _add(findings, "round3_selection.completed_companies_must_equal_prior_feedback_projection")
    expected = next((row for row in roster if row.get("company_id") not in completed_companies), {})
    expected_selection = {
        "selected_transition_id": expected.get("transition_id"),
        "selected_rank": expected.get("rank"),
        "company_id": expected.get("company_id"),
        "company_cluster_id": expected.get("company_cluster_id"),
        "cutoff_at": expected.get("cutoff_at"),
        "next_cutoff_at": expected.get("next_cutoff_at"),
    }
    if not expected or any(item.get(field) != value for field, value in expected_selection.items()):
        _add(findings, "round3_selection.must_mechanically_choose_earliest_unseen_frozen_row")
    if expected.get("outcome_access_status") != "SEALED":
        _add(findings, "round3_selection.frozen_row_must_remain_sealed")

    outcome_cell_ids = _ids(item.get("outcome_cell_ids"), "round3_selection.outcome_cell_ids", findings)
    expected_cells = [
        f"CELL:{str(expected.get('company_id', '')).split(':')[-1]}:{str(expected.get('cutoff_at', ''))[:10].replace('-', '')}:OPERATIONS",
        f"CELL:{str(expected.get('company_id', '')).split(':')[-1]}:{str(expected.get('cutoff_at', ''))[:10].replace('-', '')}:CASH",
    ]
    if outcome_cell_ids != expected_cells:
        _add(findings, "round3_selection.must_freeze_operating_and_cash_cells_in_order")
    refs = _ids(item.get("pre_outcome_source_refs"), "round3_selection.pre_outcome_source_refs", findings)
    snapshot = _snapshot_for(_mapping(history_series), str(item.get("cutoff_at")))
    member = next((entry for entry in map(_mapping, _items(snapshot.get("members"))) if entry.get("company_id") == item.get("company_id")), {})
    boundary = {
        "issuer_id": member.get("issuer_id"), "responsibility_unit_id": member.get("responsibility_unit_id"),
        "perimeter_id": member.get("perimeter_id"),
    }
    _validate_source_refs(
        refs, catalog=_source_catalog(h1_package), company_id=str(item.get("company_id")), boundary=boundary,
        cutoff=_instant(item.get("cutoff_at"), "round3_selection.cutoff_at", findings),
        path="round3_selection.pre_outcome_source_refs", findings=findings,
    )
    _validate_roles(item.get("roles"), expected=_mapping(_mapping(chain.get("application")).get("roles")), path="round3_selection.roles", findings=findings)
    for path in _forbidden_paths(item, "round3_selection"):
        _add(findings, "round3_selection.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "round3_selection": deepcopy(item) if not findings else None}


def _method_application_signature(application: Any) -> tuple[Any, ...]:
    item = _mapping(application)
    baseline = tuple(
        (entry.get("dimension"), entry.get("definition"), entry.get("measurement_gate"))
        for entry in map(_mapping, _items(item.get("baseline_before_learning")))
    )
    enhanced = tuple(
        (entry.get("dimension"), entry.get("definition"), entry.get("measurement_gate"))
        for entry in map(_mapping, _items(item.get("enhanced_after_learning")))
    )
    deltas = tuple(
        (
            entry.get("change_kind"), entry.get("baseline_gate"), entry.get("enhanced_gate"),
            entry.get("reason_ref"), entry.get("materiality"),
        )
        for entry in map(_mapping, _items(item.get("field_delta")))
    )
    return item.get("learned_rule_id"), baseline, enhanced, deltas


def validate_round3_transfer_application_receipt(
    application: Any, *, selection: Any, round2_chain: Any, block: Any, pre_outcome_roster_freeze: Any,
    target_episode: Any, target_models: list[Any], history_series: Any, h1_package: Any,
    source_block_episodes: list[Any], source_models: list[Any], completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Apply the unchanged perimeter-first rule to the mechanically selected company."""
    selection_result = validate_round3_method_transfer_selection(
        selection, round2_chain=round2_chain, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        history_series=history_series, h1_package=h1_package, source_block_episodes=source_block_episodes,
        source_models=source_models, completed_feedback_settlements=completed_feedback_settlements,
    )
    findings = ["round3_selection:" + finding for finding in selection_result["findings"]]
    chain = _mapping(round2_chain)
    source_feedback = _mapping(chain.get("source_feedback_settlement"))
    source_result = validate_feedback_settlement(
        source_feedback, block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze,
        history_series=history_series, h1_package=h1_package, episodes=source_block_episodes,
        enterprise_models=source_models,
    )
    for finding in source_result["findings"]:
        _add(findings, "round3.source_feedback_settlement:" + finding)
    target_result = validate_enterprise_judgment_episode(
        target_episode, history_series=history_series, h1_package=h1_package, enterprise_models=target_models,
    )
    for finding in target_result["findings"]:
        _add(findings, "round3.target_episode:" + finding)

    item = _closed(application, _APPLICATION_KEYS, "round3_transfer_application", findings)
    target = _mapping(target_episode)
    selected = _mapping(selection)
    if item.get("schema_version") != TRANSFER_APPLICATION_SCHEMA_VERSION:
        _add(findings, "round3_transfer_application.schema_version_invalid")
    for field in (
        "application_id", "block_id", "pre_outcome_freeze_ref", "selection_ref", "source_feedback_id",
        "source_observation_cell_id", "source_agenda_change_id", "learned_rule_id", "target_episode_id",
        "target_outcome_access",
    ):
        _required_text(item, field, "round3_transfer_application", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_TRANSFER_APPLICATION" or item.get("claim_class") != "CROSS_COMPANY_MEASUREMENT_METHOD_APPLICATION" or item.get("allowed_outputs") != ALLOWED_APPLICATION_OUTPUTS:
        _add(findings, "round3_transfer_application.object_or_permission_invalid")
    if (
        item.get("block_id") != _mapping(block).get("block_id")
        or item.get("pre_outcome_freeze_ref") != _mapping(pre_outcome_roster_freeze).get("freeze_id")
        or item.get("selection_ref") != selected.get("selection_id")
        or item.get("target_episode_id") != target.get("episode_id")
    ):
        _add(findings, "round3_transfer_application.bindings_must_match_frozen_target")
    source_observation = next((entry for entry in map(_mapping, _items(source_feedback.get("observations"))) if entry.get("outcome_cell_id") == item.get("source_observation_cell_id")), {})
    source_delta = next((entry for entry in map(_mapping, _items(source_feedback.get("next_cutoff_agenda_delta"))) if entry.get("change_id") == item.get("source_agenda_change_id")), {})
    if (
        item.get("source_feedback_id") != source_feedback.get("settlement_id")
        or source_observation.get("status") != "MEASUREMENT_MISMATCH"
        or source_delta.get("change_type") != "ADD_BOUNDARY"
    ):
        _add(findings, "round3_transfer_application.source_must_remain_original_boundary_mismatch")
    if item.get("target_outcome_access") != "SEALED" or item.get("frozen_before_outcome_access") is not True:
        _add(findings, "round3_transfer_application.must_be_frozen_before_outcome")
    if target.get("company_id") != selected.get("company_id") or target.get("cutoff_at") != selected.get("cutoff_at"):
        _add(findings, "round3_transfer_application.target_must_match_mechanical_selection")
    selected_cells = _items(selected.get("outcome_cell_ids"))
    target_cells = {entry.get("outcome_cell_id"): entry.get("dimension") for entry in map(_mapping, _items(target.get("outcome_cells")))}
    if [target_cells.get(cell_id) for cell_id in selected_cells] != ["OPERATIONS", "CASH"]:
        _add(findings, "round3_transfer_application.must_bind_same_basis_operating_and_cash_cells")
    _validate_application_fields(item, target_episode=target, source_agenda_change_id=str(item.get("source_agenda_change_id")), findings=findings)
    if _method_application_signature(item) != _method_application_signature(chain.get("application")):
        _add(findings, "round3_transfer_application.perimeter_first_rule_must_be_semantically_unchanged")
    roles = _validate_roles(item.get("roles"), expected=_mapping(target.get("roles")), path="round3_transfer_application.roles", findings=findings)
    if roles.get("outcome_custodian_id") != _mapping(target.get("roles")).get("outcome_custodian_id"):
        _add(findings, "round3_transfer_application.custodian_must_match_target_episode")
    for path in _forbidden_paths(item, "round3_transfer_application"):
        _add(findings, "round3_transfer_application.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "round3_transfer_application": deepcopy(item) if not findings else None}


def validate_round3_feedback_settlement(
    settlement: Any, *, application: Any, selection: Any, round2_chain: Any, block: Any,
    pre_outcome_roster_freeze: Any, target_episode: Any, target_models: list[Any], history_series: Any,
    h1_package: Any, source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Execute perimeter-first in the frozen order, accepting stable and mismatch outcomes."""
    application_result = validate_round3_transfer_application_receipt(
        application, selection=selection, round2_chain=round2_chain, block=block,
        pre_outcome_roster_freeze=pre_outcome_roster_freeze, target_episode=target_episode,
        target_models=target_models, history_series=history_series, h1_package=h1_package,
        source_block_episodes=source_block_episodes, source_models=source_models,
        completed_feedback_settlements=completed_feedback_settlements,
    )
    findings = ["round3_transfer_application:" + finding for finding in application_result["findings"]]
    item = _closed(settlement, _ROUND3_SETTLEMENT_KEYS, "round3_settlement", findings)
    app = _mapping(application)
    selected = _mapping(selection)
    episode = _mapping(target_episode)
    if item.get("schema_version") != ROUND3_SETTLEMENT_SCHEMA_VERSION:
        _add(findings, "round3_settlement.schema_version_invalid")
    for field in (
        "settlement_id", "application_ref", "selection_ref", "company_id", "cutoff_at",
        "outcome_custodian_id", "method_rule_id",
    ):
        _required_text(item, field, "round3_settlement", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND3_FEEDBACK_SETTLEMENT" or item.get("claim_class") != "CONTRACT_MATCHED_METHOD_ORDER_FEEDBACK" or item.get("allowed_outputs") != ALLOWED_SETTLEMENT_OUTPUTS:
        _add(findings, "round3_settlement.object_or_permission_invalid")
    if item.get("original_episode_immutable") is not True:
        _add(findings, "round3_settlement.must_preserve_original_episode")
    if (
        item.get("application_ref") != app.get("application_id")
        or item.get("selection_ref") != selected.get("selection_id")
        or item.get("company_id") != episode.get("company_id")
        or item.get("cutoff_at") != episode.get("cutoff_at")
        or item.get("outcome_custodian_id") != _mapping(episode.get("roles")).get("outcome_custodian_id")
        or item.get("method_rule_id") != "PERIMETER_FIRST_MEASUREMENT_GATE"
    ):
        _add(findings, "round3_settlement.must_match_frozen_application_target_and_method")
    expected_order = [
        "CHECK_LISTED_CONSOLIDATED_PERIMETER",
        "ASSESS_COMMON_BASIS_OR_BRIDGE",
        "READ_FROZEN_OPERATING_AND_CASH_FIELDS_IF_COMPARABLE",
    ]
    if _items(item.get("research_order")) != expected_order:
        _add(findings, "round3_settlement.must_execute_perimeter_before_fields")

    receipt = _closed(item.get("source_receipt"), _SOURCE_RECEIPT_KEYS, "round3_settlement.source_receipt", findings)
    for field in _SOURCE_RECEIPT_KEYS:
        _required_text(receipt, field, "round3_settlement.source_receipt", findings)
    cutoff = _instant(item.get("cutoff_at"), "round3_settlement.cutoff_at", findings)
    published = _date(receipt.get("published_on"), "round3_settlement.source_receipt.published_on", findings)
    if cutoff is not None and published is not None and published <= cutoff.date():
        _add(findings, "round3_settlement.source_must_be_post_cutoff")
    if receipt.get("custodian_access") != "OUTCOME_ONLY" or receipt.get("availability_precision") != "DATE":
        _add(findings, "round3_settlement.source_access_or_precision_invalid")
    catalog_source = _mapping(_source_catalog(h1_package).get(receipt.get("source_ref")))
    if not catalog_source or any(
        catalog_source.get(source_field) != receipt.get(receipt_field)
        for source_field, receipt_field in (("published_at", "published_on"), ("url", "official_url"), ("source_type", "source_type"))
    ):
        _add(findings, "round3_settlement.source_must_match_h1_static_catalog")
    elif (
        catalog_source.get("issuer_id") != episode.get("issuer_id")
        or catalog_source.get("responsibility_unit_id") != _mapping(episode.get("responsibility_boundary")).get("responsibility_unit_id")
        or catalog_source.get("perimeter_id") != _mapping(episode.get("responsibility_boundary")).get("perimeter_id")
    ):
        _add(findings, "round3_settlement.source_boundary_mismatch")

    perimeter = _closed(item.get("perimeter_assessment"), _PERIMETER_ASSESSMENT_KEYS, "round3_settlement.perimeter_assessment", findings)
    perimeter_status = perimeter.get("status")
    if perimeter_status not in {"STABLE", "CHANGED_WITH_BRIDGE", "CHANGED_WITHOUT_BRIDGE"}:
        _add(findings, "round3_settlement.perimeter_status_invalid")
    _required_text(perimeter, "statement", "round3_settlement.perimeter_assessment", findings)
    perimeter_refs = _ids(perimeter.get("evidence_refs"), "round3_settlement.perimeter_assessment.evidence_refs", findings)
    if perimeter_refs != [receipt.get("source_ref")]:
        _add(findings, "round3_settlement.perimeter_must_be_checked_from_outcome_source_first")

    selected_cells = _items(selected.get("outcome_cell_ids"))
    allowed_cells = {entry.get("outcome_cell_id"): entry for entry in map(_mapping, _items(episode.get("outcome_cells")))}
    observations = [
        _closed(raw, _OBSERVATION_KEYS, f"round3_settlement.observations[{index}]", findings)
        for index, raw in enumerate(_items(item.get("observations")))
    ]
    if [entry.get("outcome_cell_id") for entry in observations] != selected_cells:
        _add(findings, "round3_settlement.observations_must_match_frozen_operating_cash_order")
    for index, observation in enumerate(observations):
        cell_id = observation.get("outcome_cell_id")
        if cell_id not in allowed_cells:
            _add(findings, f"round3_settlement.observations[{index}].cell_not_frozen")
        _required_text(observation, "summary", f"round3_settlement.observations[{index}]", findings)
        if observation.get("source_ref") != receipt.get("source_ref"):
            _add(findings, f"round3_settlement.observations[{index}].source_must_match_receipt")
        if perimeter_status == "CHANGED_WITHOUT_BRIDGE":
            if observation.get("status") != "MEASUREMENT_MISMATCH" or not _text(observation.get("reported_value")):
                _add(findings, f"round3_settlement.observations[{index}].unbridged_change_requires_local_mismatch")
        elif observation.get("status") != "OBSERVED" or not _text(observation.get("reported_value")):
            _add(findings, f"round3_settlement.observations[{index}].comparable_perimeter_requires_field_read")
        contract = _mapping(_mapping(allowed_cells.get(cell_id)).get("measurement_contract"))
        if receipt.get("source_type") not in _items(contract.get("allowed_source_types")):
            _add(findings, f"round3_settlement.observations[{index}].source_type_not_allowed")
        window_end = _instant(contract.get("window_end"), f"round3_settlement.observations[{index}].window_end", findings)
        if published is not None and window_end is not None and published > window_end.date():
            _add(findings, f"round3_settlement.observations[{index}].source_outside_window")

    deltas = [
        _closed(raw, _AGENDA_DELTA_KEYS, f"round3_settlement.next_cutoff_agenda_delta[{index}]", findings)
        for index, raw in enumerate(_items(item.get("next_cutoff_agenda_delta")))
    ]
    if not deltas:
        _add(findings, "round3_settlement.next_cutoff_agenda_required")
    for index, delta in enumerate(deltas):
        for field in _AGENDA_DELTA_KEYS:
            _required_text(delta, field, f"round3_settlement.next_cutoff_agenda_delta[{index}]", findings)
        if delta.get("target_cutoff_at") != selected.get("next_cutoff_at") or delta.get("change_type") not in {"CHANGE_EVIDENCE_ORDER", "ADD_BOUNDARY", "RETAIN_UNKNOWN"}:
            _add(findings, f"round3_settlement.next_cutoff_agenda_delta[{index}].invalid")
    for path in _forbidden_paths(item, "round3_settlement"):
        _add(findings, "round3_settlement.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "round3_settlement": deepcopy(item) if not findings else None}


def validate_round3_transfer_review(
    review: Any, *, settlement: Any, application: Any, selection: Any, round2_chain: Any, block: Any,
    pre_outcome_roster_freeze: Any, target_episode: Any, target_models: list[Any], history_series: Any,
    h1_package: Any, source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Review only whether the unchanged method changed research order a second time."""
    settlement_result = validate_round3_feedback_settlement(
        settlement, application=application, selection=selection, round2_chain=round2_chain, block=block,
        pre_outcome_roster_freeze=pre_outcome_roster_freeze, target_episode=target_episode,
        target_models=target_models, history_series=history_series, h1_package=h1_package,
        source_block_episodes=source_block_episodes, source_models=source_models,
        completed_feedback_settlements=completed_feedback_settlements,
    )
    findings = ["round3_settlement:" + finding for finding in settlement_result["findings"]]
    item = _closed(review, _ROUND3_REVIEW_KEYS, "round3_review", findings)
    app = _mapping(application)
    prior_review = _mapping(_mapping(round2_chain).get("review"))
    if item.get("schema_version") != ROUND3_REVIEW_SCHEMA_VERSION:
        _add(findings, "round3_review.schema_version_invalid")
    for field in (
        "review_id", "application_ref", "feedback_ref", "prior_review_ref", "reviewer_id", "review_scope",
        "verdict", "materiality_statement", "prohibited_conclusion",
    ):
        _required_text(item, field, "round3_review", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND3_TRANSFER_REVIEW" or item.get("claim_class") != "INDEPENDENT_RESEARCH_ORDER_ADJUDICATION" or item.get("allowed_outputs") != ALLOWED_ROUND3_REVIEW_OUTPUTS:
        _add(findings, "round3_review.object_or_permission_invalid")
    if (
        item.get("application_ref") != app.get("application_id")
        or item.get("feedback_ref") != _mapping(settlement).get("settlement_id")
        or item.get("prior_review_ref") != prior_review.get("review_id")
    ):
        _add(findings, "round3_review.bindings_must_match_two_applications")
    role_ids = set(_mapping(app.get("roles")).values())
    if item.get("reviewer_id") in role_ids:
        _add(findings, "round3_review.reviewer_must_be_independent")
    if item.get("review_scope") != "SECOND_CROSS_COMPANY_RESEARCH_ORDER_CHANGE_ONLY":
        _add(findings, "round3_review.scope_must_remain_method_order_only")
    if (
        item.get("verdict") != "SECOND_CROSS_COMPANY_RESEARCH_ORDER_CHANGE_CONFIRMED"
        or item.get("research_order_changed") is not True
        or item.get("rule_unchanged") is not True
    ):
        _add(findings, "round3_review.verdict_requires_changed_order_and_unchanged_rule")
    if item.get("prohibited_conclusion") != "NO_ENTERPRISE_PERFORMANCE_ACTION_CAUSALITY_CJO_VALUATION_REPORT_OR_INVESTMENT_CONCLUSION":
        _add(findings, "round3_review.must_deny_enterprise_and_investment_conclusions")
    if _method_application_signature(app) != _method_application_signature(_mapping(round2_chain).get("application")):
        _add(findings, "round3_review.rule_was_not_unchanged")
    for path in _forbidden_paths(item, "round3_review"):
        _add(findings, "round3_review.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "round3_review": deepcopy(item) if not findings else None}


def validate_round3_transfer_validation(
    validation: Any, *, review: Any, settlement: Any, application: Any, selection: Any, round2_chain: Any,
    block: Any, pre_outcome_roster_freeze: Any, target_episode: Any, target_models: list[Any],
    history_series: Any, h1_package: Any, source_block_episodes: list[Any], source_models: list[Any],
    completed_feedback_settlements: list[Any],
) -> dict[str, Any]:
    """Grant only the narrow perimeter-first measurement-method authority."""
    review_result = validate_round3_transfer_review(
        review, settlement=settlement, application=application, selection=selection, round2_chain=round2_chain,
        block=block, pre_outcome_roster_freeze=pre_outcome_roster_freeze, target_episode=target_episode,
        target_models=target_models, history_series=history_series, h1_package=h1_package,
        source_block_episodes=source_block_episodes, source_models=source_models,
        completed_feedback_settlements=completed_feedback_settlements,
    )
    findings = ["round3_review:" + finding for finding in review_result["findings"]]
    item = _closed(validation, _ROUND3_VALIDATION_KEYS, "round3_validation", findings)
    chain = _mapping(round2_chain)
    source_feedback = _mapping(chain.get("source_feedback_settlement"))
    source_observation = next((entry for entry in map(_mapping, _items(source_feedback.get("observations"))) if entry.get("status") == "MEASUREMENT_MISMATCH"), {})
    if item.get("schema_version") != ROUND3_VALIDATION_SCHEMA_VERSION:
        _add(findings, "round3_validation.schema_version_invalid")
    for field in _ROUND3_VALIDATION_KEYS - {"denied_authorities", "allowed_outputs"}:
        _required_text(item, field, "round3_validation", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND3_TRANSFER_VALIDATION" or item.get("claim_class") != "NARROW_MEASUREMENT_METHOD_AUTHORITY" or item.get("allowed_outputs") != ALLOWED_ROUND3_VALIDATION_OUTPUTS:
        _add(findings, "round3_validation.object_or_permission_invalid")
    expected_bindings = {
        "source_feedback_ref": source_feedback.get("settlement_id"),
        "round2_application_ref": _mapping(chain.get("application")).get("application_id"),
        "round2_review_ref": _mapping(chain.get("review")).get("review_id"),
        "round2_completion_ref": _mapping(chain.get("completion")).get("completion_id"),
        "round3_selection_ref": _mapping(selection).get("selection_id"),
        "round3_application_ref": _mapping(application).get("application_id"),
        "round3_settlement_ref": _mapping(settlement).get("settlement_id"),
        "round3_review_ref": _mapping(review).get("review_id"),
    }
    if any(item.get(field) != value for field, value in expected_bindings.items()):
        _add(findings, "round3_validation.must_bind_complete_source_two_application_review_chain")
    if not source_observation or not _mapping(application).get("frozen_before_outcome_access"):
        _add(findings, "round3_validation.requires_material_misread_and_preoutcome_freeze")
    if item.get("method_rule_id") != "PERIMETER_FIRST_MEASUREMENT_GATE" or item.get("transfer_status") != "TRANSFER_VALIDATED" or item.get("authority_scope") != "PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY":
        _add(findings, "round3_validation.status_or_authority_scope_invalid")
    denied = [
        "ENTERPRISE_JUDGMENT", "COMPARATIVE", "METHOD_WIDE_RELEASE", "CJO", "VALUATION", "REPORT",
        "INVESTMENT_AUTHORIZATION", "R-61", "R-103",
    ]
    if _items(item.get("denied_authorities")) != denied:
        _add(findings, "round3_validation.denied_authorities_must_remain_complete")
    for path in _forbidden_paths(item, "round3_validation"):
        _add(findings, "round3_validation.forbidden_field:" + path)
    return {"valid": not findings, "findings": findings, "round3_validation": deepcopy(item) if not findings else None}
