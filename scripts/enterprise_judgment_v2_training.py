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
_SETTLEMENT_KEYS = {"schema_version", "settlement_id", "block_id", "transition_id", "company_id", "cutoff_at", "outcome_custodian_id", "source_receipt", "observations", "next_cutoff_agenda_delta", "original_episode_immutable", "object_class", "claim_class", "allowed_outputs"}
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
                lowered in _FORBIDDEN_KEYS or lowered.startswith("actual_") or lowered.startswith("settlement_")
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


def validate_feedback_settlement(
    settlement: Any, *, block: Any, history_series: Any, h1_package: Any, episodes: list[Any], enterprise_models: list[Any] | None = None,
) -> dict[str, Any]:
    """Validate a separately-accessed feedback turn and its agenda change."""
    findings: list[str] = []
    block_validation = validate_industry_learning_block(block, history_series=history_series, h1_package=h1_package, episodes=episodes, enterprise_models=enterprise_models)
    for finding in block_validation["findings"]:
        _add(findings, "industry_block:" + finding)
    block_item = _mapping(block)
    item = _closed(settlement, _SETTLEMENT_KEYS, "feedback_settlement", findings)
    if item.get("schema_version") != SETTLEMENT_SCHEMA_VERSION:
        _add(findings, "feedback_settlement.schema_version_invalid")
    for field in ("settlement_id", "block_id", "transition_id", "company_id", "cutoff_at", "outcome_custodian_id"):
        _required_text(item, field, "feedback_settlement", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_FEEDBACK_SETTLEMENT" or item.get("claim_class") != "CONTRACT_MATCHED_PREQUENTIAL_FEEDBACK":
        _add(findings, "feedback_settlement.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_SETTLEMENT_OUTPUTS:
        _add(findings, "feedback_settlement.allowed_outputs_invalid")
    if item.get("original_episode_immutable") is not True:
        _add(findings, "feedback_settlement.must_preserve_original_episode_immutable")
    transition = next((entry for entry in map(_mapping, _items(block_item.get("transition_roster"))) if entry.get("transition_id") == item.get("transition_id")), {})
    if not transition or item.get("block_id") != block_item.get("block_id") or any(item.get(field) != transition.get(field) for field in ("company_id", "cutoff_at")):
        _add(findings, "feedback_settlement.must_match_frozen_block_transition")
    if item.get("outcome_custodian_id") != _mapping(block_item.get("roles")).get("outcome_custodian_id"):
        _add(findings, "feedback_settlement.custodian_must_match_frozen_roles")
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
    episode_by_id = {entry.get("episode_id"): entry for entry in map(_mapping, episodes)}
    episode = _mapping(episode_by_id.get(transition.get("episode_id")))
    allowed_cells = {entry.get("outcome_cell_id"): entry for entry in map(_mapping, _items(episode.get("outcome_cells")))}
    observations = [_closed(raw, _OBSERVATION_KEYS, f"feedback_settlement.observations[{index}]", findings) for index, raw in enumerate(_items(item.get("observations")))]
    if not observations:
        _add(findings, "feedback_settlement.observations_required")
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
        matched += observation.get("status") == "OBSERVED"
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
