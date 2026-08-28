#!/usr/bin/env python3
"""Same-contract baseline/enhanced decision-utility comparison.

This is a qualitative, paired evaluation: it records which material decision
dimension changed and the research cost, never a blended utility score or an
automatic method release.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

try:
    from scripts import enterprise_judgment_episode as episode_module
    from scripts import judgment_training_decision_contract as contract_module
except ModuleNotFoundError:  # pragma: no cover
    import enterprise_judgment_episode as episode_module
    import judgment_training_decision_contract as contract_module


PAIRING_SCHEMA_VERSION = "turtle-decision-utility-pairing.v3"
EVALUATION_SCHEMA_VERSION = "turtle-decision-utility-evaluation.v4"
CONTROL_PAIRING_SCHEMA_VERSION = "turtle-decision-utility-control-pairing.v3"
CONTROL_EVALUATION_SCHEMA_VERSION = "turtle-decision-utility-control-evaluation.v3"
HISTORICAL_PAIRING_SCHEMA_VERSION = "turtle-decision-utility-pairing.v2"
HISTORICAL_EVALUATION_SCHEMA_VERSION = "turtle-decision-utility-evaluation.v3"
HISTORICAL_CONTROL_PAIRING_SCHEMA_VERSION = "turtle-decision-utility-control-pairing.v2"
HISTORICAL_CONTROL_EVALUATION_SCHEMA_VERSION = "turtle-decision-utility-control-evaluation.v2"
LEGACY_PAIRING_SCHEMA_VERSION = "turtle-decision-utility-pairing.v1"
LEGACY_EVALUATION_SCHEMA_VERSION = "turtle-decision-utility-evaluation.v1"
ALLOWED_OUTPUTS = ["DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"]
DIMENSIONS = [
    "INITIAL_CONDITIONS",
    "IMPLEMENTED_MANAGEMENT_ACTION",
    "EXECUTION",
    "CUSTOMER_COMPETITION_RESPONSE",
    "UNIT_ECONOMICS",
    "WORKING_CAPITAL_CASH_CAPITAL",
    "ADAPTATION_PERMANENT_LOSS",
    "STRONGEST_ALTERNATIVE_EXPLANATION",
]
LEGACY_DIMENSIONS = ["PERMANENT_LOSS_GUARDRAIL", "OWNER_CASH_ACCESS", "KEY_UNKNOWN_DISCOVERY", "RESEARCH_COST"]

_HISTORICAL_PAIRING_KEYS = {
    "schema_version", "pairing_id", "decision_contract_ref", "baseline_episode_id",
    "enhanced_episode_id", "baseline_method_id", "enhanced_method_id",
    "baseline_research_cost_hours", "enhanced_research_cost_hours", "frozen_at",
    "object_class", "claim_class", "allowed_outputs",
}
_PAIRING_KEYS = _HISTORICAL_PAIRING_KEYS | {"artifact_status", "authority_ceiling"}
_REF_KEYS = {"contract_id", "contract_version"}
_HISTORICAL_EVALUATION_KEYS = {"schema_version", "evaluation_id", "pairing_id", "evaluated_at", "reviewer_id", "outcome_settlement_ref", "dimension_findings", "holdout", "object_class", "claim_class", "allowed_outputs"}
_EVALUATION_KEYS = _HISTORICAL_EVALUATION_KEYS | {
    "artifact_status", "authority_ceiling", "overall_utility_verdict",
}
_FINDING_KEYS = {"dimension_id", "baseline_assessment", "enhanced_assessment", "rationale"}
_EVALUATION_FINDING_KEYS = _FINDING_KEYS | {"supporting_cell_ids"}
_HOLDOUT_KEYS = {"training_company_ids", "holdout_company_ids", "training_cutoff_through", "holdout_cutoff_from"}
_HISTORICAL_CONTROL_PAIRING_KEYS = {
    "schema_version", "pairing_id", "forecast_id", "forecast_pairing_id", "decision_contract_ref",
    "baseline_episode_id", "enhanced_episode_id", "baseline_method_id", "enhanced_method_id",
    "baseline_research_cost_hours", "enhanced_research_cost_hours", "frozen_at",
    "object_class", "claim_class", "allowed_outputs",
}
_CONTROL_PAIRING_KEYS = _HISTORICAL_CONTROL_PAIRING_KEYS | {
    "artifact_status", "authority_ceiling", "outcome_support_bindings",
}
_HISTORICAL_CONTROL_EVALUATION_KEYS = {
    "schema_version", "evaluation_id", "pairing_id", "forecast_paired_evaluation_id", "evaluated_at",
    "reviewer_id", "dimension_findings", "object_class", "claim_class", "allowed_outputs",
}
_CONTROL_EVALUATION_KEYS = _HISTORICAL_CONTROL_EVALUATION_KEYS | {
    "artifact_status", "authority_ceiling", "overall_utility_verdict",
}
ASSESSMENTS = {
    "AVOIDED_ERROR", "MATERIAL_IMPROVEMENT", "NO_DIFFERENCE", "UNKNOWN",
    "NOT_DIAGNOSTIC", "HARMFUL",
}
HISTORICAL_ASSESSMENTS = ASSESSMENTS - {"HARMFUL"}
UTILITY_VERDICTS = {
    "MATERIAL_UTILITY", "NO_MATERIAL_UTILITY", "HARMFUL", "NOT_DIAGNOSTIC",
}
_FORECAST_CELL_REF_KEYS = {"dimension_id", "window_id"}
_OUTCOME_SUPPORT_BINDING_KEYS = {
    "binding_id", "dimension_id", "enhanced_outcome_cell_id", "supporting_forecast_cells",
}
_LEGACY_PAIRING_KEYS = {
    "schema_version", "pairing_id", "decision_contract_ref", "baseline", "enhanced",
    "frozen_at", "object_class", "claim_class", "allowed_outputs",
}
_LEGACY_DECISION_KEYS = {
    "method_id", "decision_status", "material_unknown_ids", "evidence_budget_id",
    "source_packet_refs", "research_cost_hours",
}


def _mapping(value: Any) -> dict[str, Any]: return value if isinstance(value, dict) else {}
def _items(value: Any) -> list[Any]: return value if isinstance(value, list) else []
def _text(value: Any) -> bool: return isinstance(value, str) and bool(value.strip())

def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict): findings.append(f"{path}_must_be_object")
    for key in sorted(set(item) - allowed): findings.append(f"{path}_contains_unapproved_field:{key}")
    for key in sorted(allowed - set(item)): findings.append(f"{path}_missing_required_field:{key}")
    return item

def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value): findings.append(f"{path}_must_be_timezone_aware_iso8601"); return None
    try: parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: findings.append(f"{path}_must_be_timezone_aware_iso8601"); return None
    if parsed.tzinfo is None or parsed.utcoffset() is None: findings.append(f"{path}_must_be_timezone_aware_iso8601"); return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)

def _research_cost(value: Any, path: str, findings: list[str]) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        findings.append(f"{path}_invalid")


def _utility_verdict(
    dimension_findings: list[dict[str, Any]],
) -> str:
    """Resolve current-schema utility without treating review prose as a delta.

    The current episode/pairing schemas can freeze evidence dependencies and
    forecast differences, but they do not carry a structured, mechanically
    comparable before/after treatment for management, owner cash, permanent
    loss, valuation direction, or the next research action.  A positive
    reviewer assessment therefore remains diagnostic only.  Observing an
    extra cell or predicting it better is not itself decision utility.
    """
    comparisons = [
        (item.get("baseline_assessment"), item.get("enhanced_assessment"))
        for item in dimension_findings
    ]
    if any(enhanced == "HARMFUL" for _, enhanced in comparisons):
        return "HARMFUL"
    material_states = {"AVOIDED_ERROR", "MATERIAL_IMPROVEMENT"}
    reviewer_material_dimensions = {
        str(item.get("dimension_id"))
        for item in dimension_findings
        if item.get("enhanced_assessment") in material_states
        and item.get("baseline_assessment") not in material_states
    }
    if reviewer_material_dimensions:
        return "NOT_DIAGNOSTIC"
    if comparisons and all(
        enhanced in {"UNKNOWN", "NOT_DIAGNOSTIC"} for _, enhanced in comparisons
    ):
        return "NOT_DIAGNOSTIC"
    return "NO_MATERIAL_UTILITY"


def _episode_dependencies_by_dimension(episode: Any) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for raw in _items(_mapping(episode).get("claims")):
        claim = _mapping(raw)
        dimension = claim.get("judgment_dimension")
        if dimension in DIMENSIONS:
            result[str(dimension)] = {
                str(cell_id) for cell_id in _items(claim.get("dependent_outcome_cell_ids"))
                if _text(cell_id)
            }
    return result


def _validate_outcome_support_bindings(
    value: Any, *, path: str, findings: list[str], baseline_episode: Any,
    enhanced_episode: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        findings.append(f"{path}_must_be_array")
        return []
    baseline_dependencies = _episode_dependencies_by_dimension(baseline_episode)
    enhanced_dependencies = _episode_dependencies_by_dimension(enhanced_episode)
    seen: set[str] = set()
    bindings: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        binding_path = f"{path}[{index}]"
        binding = _closed(raw, _OUTCOME_SUPPORT_BINDING_KEYS, binding_path, findings)
        binding_id = binding.get("binding_id")
        if not _text(binding_id) or binding_id in seen:
            findings.append(f"{binding_path}.binding_id_invalid_or_duplicate")
        seen.add(str(binding_id))
        dimension = binding.get("dimension_id")
        if dimension not in DIMENSIONS:
            findings.append(f"{binding_path}.dimension_id_invalid")
        outcome_cell_id = binding.get("enhanced_outcome_cell_id")
        if not _text(outcome_cell_id) or (
            outcome_cell_id not in enhanced_dependencies.get(str(dimension), set())
            or outcome_cell_id in baseline_dependencies.get(str(dimension), set())
        ):
            findings.append(
                f"{binding_path}.enhanced_outcome_cell_id_must_be_new_frozen_dependency"
            )
        support = _items(binding.get("supporting_forecast_cells"))
        if not support:
            findings.append(f"{binding_path}.supporting_forecast_cells_must_be_nonempty")
        refs: set[tuple[str, str]] = set()
        for ref_index, raw_ref in enumerate(support):
            ref = _closed(
                raw_ref, _FORECAST_CELL_REF_KEYS,
                f"{binding_path}.supporting_forecast_cells[{ref_index}]", findings,
            )
            dimension_id, window_id = ref.get("dimension_id"), ref.get("window_id")
            key = (str(dimension_id), str(window_id))
            if not _text(dimension_id) or not _text(window_id) or key in refs:
                findings.append(
                    f"{binding_path}.supporting_forecast_cells[{ref_index}].invalid_or_duplicate"
                )
            refs.add(key)
        bindings.append(binding)
    return bindings


def _forecast_cell_index(forecast: Any) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(dimension.get("dimension_id")), str(window.get("window_id"))): window
        for dimension in (_mapping(raw) for raw in _items(_mapping(forecast).get("dimensions")))
        for window in (_mapping(raw) for raw in _items(dimension.get("forecast_by_window")))
        if _text(dimension.get("dimension_id")) and _text(window.get("window_id"))
    }
def _legacy_decision(
    value: Any, path: str, budget: dict[str, Any], findings: list[str],
) -> dict[str, Any]:
    item = _closed(value, _LEGACY_DECISION_KEYS, path, findings)
    if not _text(item.get("method_id")):
        findings.append(f"{path}.method_id_required")
    if item.get("decision_status") not in {"PASS", "WATCH", "RESEARCH", "CONDITIONAL_BUYBAND"}:
        findings.append(f"{path}.decision_status_invalid")
    unknown_ids = item.get("material_unknown_ids")
    if not isinstance(unknown_ids, list) or any(not _text(entry) for entry in _items(unknown_ids)):
        findings.append(f"{path}.material_unknown_ids_invalid")
    if (
        item.get("evidence_budget_id") != budget.get("evidence_budget_id")
        or item.get("source_packet_refs") != budget.get("source_packet_refs")
    ):
        findings.append(f"{path}.must_use_same_frozen_evidence_budget")
    _research_cost(item.get("research_cost_hours"), f"{path}.research_cost_hours", findings)
    return item


def _validate_legacy_pairing(pairing: Any, *, contract: Any) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(pairing, _LEGACY_PAIRING_KEYS, "decision_utility_pairing", findings)
    if item.get("schema_version") != LEGACY_PAIRING_SCHEMA_VERSION:
        findings.append("decision_utility_pairing.schema_version_invalid")
    if item.get("object_class") != "DECISION_UTILITY_PAIRING" or item.get("claim_class") != "SAME_CONTRACT_METHOD_ABLATION":
        findings.append("decision_utility_pairing.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append("decision_utility_pairing.outputs_must_remain_evaluation_only")
    if not _text(item.get("pairing_id")):
        findings.append("decision_utility_pairing.pairing_id_required")
    contract_result = contract_module.validate_training_decision_contract(contract)
    findings.extend("decision_contract:" + finding for finding in contract_result["findings"])
    contract_item = _mapping(contract)
    ref = _closed(item.get("decision_contract_ref"), _REF_KEYS, "decision_utility_pairing.decision_contract_ref", findings)
    if ref != {"contract_id": contract_item.get("contract_id"), "contract_version": contract_item.get("contract_version")}:
        findings.append("decision_utility_pairing.contract_reference_must_match")
    budget = _mapping(contract_item.get("evidence_budget"))
    baseline = _legacy_decision(item.get("baseline"), "decision_utility_pairing.baseline", budget, findings)
    enhanced = _legacy_decision(item.get("enhanced"), "decision_utility_pairing.enhanced", budget, findings)
    if baseline.get("method_id") == enhanced.get("method_id"):
        findings.append("decision_utility_pairing.methods_must_differ")
    _instant(item.get("frozen_at"), "decision_utility_pairing.frozen_at", findings)
    return {
        "valid": not findings,
        "findings": findings,
        "pairing": deepcopy(item) if not findings else None,
        "artifact_status": "HISTORICAL_READ_ONLY",
        "authority_ceiling": "NONE",
        "learning_authorization": "NONE",
        "authority": "LEGACY_V1_READ_ONLY",
    }


def _validate_legacy_evaluation(evaluation: Any, *, pairing: Any, contract: Any) -> dict[str, Any]:
    pair = _validate_legacy_pairing(pairing, contract=contract)
    findings = ["pairing:" + finding for finding in pair["findings"]]
    item = _closed(evaluation, _HISTORICAL_EVALUATION_KEYS, "decision_utility_evaluation", findings)
    if item.get("schema_version") != LEGACY_EVALUATION_SCHEMA_VERSION:
        findings.append("decision_utility_evaluation.schema_version_invalid")
    if item.get("pairing_id") != _mapping(pairing).get("pairing_id"):
        findings.append("decision_utility_evaluation.pairing_id_must_match")
    if item.get("object_class") != "DECISION_UTILITY_EVALUATION" or item.get("claim_class") != "MATERIAL_DECISION_UTILITY_REVIEW":
        findings.append("decision_utility_evaluation.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append("decision_utility_evaluation.outputs_must_remain_evaluation_only")
    if not _text(item.get("evaluation_id")) or not _text(item.get("reviewer_id")) or not _text(item.get("outcome_settlement_ref")):
        findings.append("decision_utility_evaluation.identity_or_outcome_ref_missing")
    evaluated = _instant(item.get("evaluated_at"), "decision_utility_evaluation.evaluated_at", findings)
    frozen = _instant(_mapping(pairing).get("frozen_at"), "decision_utility_pairing.frozen_at", findings)
    if evaluated and frozen and evaluated < frozen:
        findings.append("decision_utility_evaluation.must_follow_pairing_freeze")
    roles = _mapping(_mapping(contract).get("roles"))
    if item.get("reviewer_id") in set(roles.values()):
        findings.append("decision_utility_evaluation.reviewer_must_be_independent_of_contract_roles")
    seen: set[str] = set()
    for index, raw in enumerate(_items(item.get("dimension_findings"))):
        finding = _closed(raw, _FINDING_KEYS, f"decision_utility_evaluation.dimension_findings[{index}]", findings)
        dimension = finding.get("dimension_id")
        if dimension not in LEGACY_DIMENSIONS or dimension in seen:
            findings.append(f"decision_utility_evaluation.dimension_findings[{index}].dimension_invalid_or_duplicate")
        seen.add(str(dimension))
        for field in ("baseline_assessment", "enhanced_assessment"):
            if finding.get(field) not in HISTORICAL_ASSESSMENTS:
                findings.append(f"decision_utility_evaluation.dimension_findings[{index}].{field}_invalid")
        if not _text(finding.get("rationale")):
            findings.append(f"decision_utility_evaluation.dimension_findings[{index}].rationale_required")
    if seen != set(LEGACY_DIMENSIONS):
        findings.append("decision_utility_evaluation.must_cover_each_material_dimension_once")
    holdout = _closed(item.get("holdout"), _HOLDOUT_KEYS, "decision_utility_evaluation.holdout", findings)
    training = set(_items(holdout.get("training_company_ids")))
    held = set(_items(holdout.get("holdout_company_ids")))
    if not training or not held or training & held:
        findings.append("decision_utility_evaluation.holdout_company_axis_invalid")
    before = _instant(holdout.get("training_cutoff_through"), "decision_utility_evaluation.holdout.training_cutoff_through", findings)
    after = _instant(holdout.get("holdout_cutoff_from"), "decision_utility_evaluation.holdout.holdout_cutoff_from", findings)
    if before and after and before >= after:
        findings.append("decision_utility_evaluation.holdout_time_axis_invalid")
    return {
        "valid": not findings,
        "findings": findings,
        "artifact_status": "HISTORICAL_READ_ONLY",
        "authority_ceiling": "NONE",
        "overall_utility_verdict": None,
        "learning_authorization": "NONE",
        "authority": "LEGACY_V1_READ_ONLY",
    }


def _episode_profile(
    value: Any, role: str, contract: Any, findings: list[str], root_path: str,
) -> dict[str, Any]:
    path = f"{root_path}.{role}_episode"
    if not isinstance(value, dict):
        findings.append(f"{path}_manifest_required")
        return {"item": {}, "method_id": None, "dimensions": set(), "locator_refs": set()}
    result = episode_module.validate_episode_manifest(value, decision_contract=contract)
    findings.extend(f"{path}:{finding}" for finding in result["findings"])
    item = _mapping(value)
    claims = [_mapping(raw) for raw in _items(item.get("claims"))]
    method_ids = {claim.get("method_id") for claim in claims if _text(claim.get("method_id"))}
    if len(method_ids) != 1:
        findings.append(f"{path}.claims_must_use_exactly_one_method_id")
    dimensions = [claim.get("judgment_dimension") for claim in claims]
    if len(dimensions) != len(DIMENSIONS) or set(dimensions) != set(DIMENSIONS):
        findings.append(f"{path}.must_cover_each_judgment_dimension_once")
    locator_refs = {
        str(locator_ref)
        for claim in claims
        for locator_ref in _items(claim.get("evidence_locator_refs"))
        if _text(locator_ref)
    }
    for cell in (_mapping(raw) for raw in _items(item.get("outcome_cells"))):
        if cell.get("status") == "OBSERVED" or _text(cell.get("custodian_receipt_ref")):
            findings.append(f"{path}.outcome_must_remain_sealed_before_pairing")
            break
    return {
        "item": item,
        "method_id": next(iter(method_ids), None),
        "dimensions": set(dimensions),
        "locator_refs": locator_refs,
    }


def _validate_episode_pair(
    item: dict[str, Any], *, contract: Any, baseline_episode: Any, enhanced_episode: Any,
    findings: list[str], path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline = _episode_profile(baseline_episode, "baseline", contract, findings, path)
    enhanced = _episode_profile(enhanced_episode, "enhanced", contract, findings, path)
    for role, profile in (("baseline", baseline), ("enhanced", enhanced)):
        episode = profile["item"]
        if item.get(f"{role}_episode_id") != episode.get("episode_id"):
            findings.append(f"{path}.{role}_episode_id_must_match_manifest")
        if item.get(f"{role}_method_id") != profile["method_id"]:
            findings.append(f"{path}.{role}_method_id_must_match_episode")
    for field in ("company_id", "issuer_id", "cutoff_at", "decision_contract_ref"):
        if baseline["item"].get(field) != enhanced["item"].get(field):
            findings.append(f"{path}.episodes_{field}_must_match")
    if baseline["locator_refs"] != enhanced["locator_refs"]:
        findings.append(f"{path}.episodes_must_use_same_frozen_evidence_locator_set")
    if baseline["method_id"] == enhanced["method_id"]:
        findings.append(f"{path}.methods_must_differ")
    return baseline, enhanced


def validate_decision_utility_pairing(
    pairing: Any, *, contract: Any, baseline_episode: Any | None = None,
    enhanced_episode: Any | None = None,
) -> dict[str, Any]:
    if _mapping(pairing).get("schema_version") == LEGACY_PAIRING_SCHEMA_VERSION:
        return _validate_legacy_pairing(pairing, contract=contract)
    findings: list[str] = []
    historical = _mapping(pairing).get("schema_version") == HISTORICAL_PAIRING_SCHEMA_VERSION
    item = _closed(
        pairing,
        _HISTORICAL_PAIRING_KEYS if historical else _PAIRING_KEYS,
        "decision_utility_pairing",
        findings,
    )
    expected_version = HISTORICAL_PAIRING_SCHEMA_VERSION if historical else PAIRING_SCHEMA_VERSION
    if item.get("schema_version") != expected_version: findings.append("decision_utility_pairing.schema_version_invalid")
    if item.get("object_class") != "DECISION_UTILITY_PAIRING" or item.get("claim_class") != "SAME_CONTRACT_METHOD_ABLATION": findings.append("decision_utility_pairing.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS: findings.append("decision_utility_pairing.outputs_must_remain_evaluation_only")
    if not _text(item.get("pairing_id")): findings.append("decision_utility_pairing.pairing_id_required")
    result = contract_module.validate_training_decision_contract(contract)
    findings.extend("decision_contract:" + x for x in result["findings"])
    contract_item = _mapping(contract)
    ref = _closed(item.get("decision_contract_ref"), _REF_KEYS, "decision_utility_pairing.decision_contract_ref", findings)
    if ref != {"contract_id": contract_item.get("contract_id"), "contract_version": contract_item.get("contract_version")}:
        findings.append("decision_utility_pairing.contract_reference_must_match")
    for field in ("baseline_episode_id", "enhanced_episode_id", "baseline_method_id", "enhanced_method_id"):
        if not _text(item.get(field)): findings.append(f"decision_utility_pairing.{field}_required")
    _research_cost(item.get("baseline_research_cost_hours"), "decision_utility_pairing.baseline_research_cost_hours", findings)
    _research_cost(item.get("enhanced_research_cost_hours"), "decision_utility_pairing.enhanced_research_cost_hours", findings)
    _validate_episode_pair(
        item, contract=contract, baseline_episode=baseline_episode, enhanced_episode=enhanced_episode,
        findings=findings, path="decision_utility_pairing",
    )
    _instant(item.get("frozen_at"), "decision_utility_pairing.frozen_at", findings)
    if not historical:
        if item.get("artifact_status") != "FROZEN":
            findings.append("decision_utility_pairing.artifact_status_must_be_frozen")
        if item.get("authority_ceiling") != "NONE":
            findings.append("decision_utility_pairing.authority_ceiling_must_be_none")
    return {
        "valid": not findings,
        "findings": findings,
        "pairing": deepcopy(item) if not findings else None,
        "artifact_status": "HISTORICAL_READ_ONLY" if historical else item.get("artifact_status"),
        "authority_ceiling": "NONE",
        "learning_authorization": "NONE",
    }

def validate_decision_utility_evaluation(
    evaluation: Any, *, pairing: Any, contract: Any, baseline_episode: Any | None = None,
    enhanced_episode: Any | None = None, outcome_settlement: Any | None = None,
) -> dict[str, Any]:
    if _mapping(pairing).get("schema_version") == LEGACY_PAIRING_SCHEMA_VERSION:
        return _validate_legacy_evaluation(evaluation, pairing=pairing, contract=contract)
    historical_pairing = _mapping(pairing).get("schema_version") == HISTORICAL_PAIRING_SCHEMA_VERSION
    historical_evaluation = _mapping(evaluation).get("schema_version") == HISTORICAL_EVALUATION_SCHEMA_VERSION
    historical = historical_pairing and historical_evaluation
    pair = validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline_episode, enhanced_episode=enhanced_episode,
    )
    findings = ["pairing:" + x for x in pair["findings"]]
    if historical_pairing != historical_evaluation:
        findings.append("decision_utility_evaluation.pairing_and_evaluation_version_epoch_mismatch")
    item = _closed(
        evaluation,
        _HISTORICAL_EVALUATION_KEYS if historical else _EVALUATION_KEYS,
        "decision_utility_evaluation",
        findings,
    )
    expected_version = HISTORICAL_EVALUATION_SCHEMA_VERSION if historical else EVALUATION_SCHEMA_VERSION
    if item.get("schema_version") != expected_version: findings.append("decision_utility_evaluation.schema_version_invalid")
    if item.get("pairing_id") != _mapping(pairing).get("pairing_id"): findings.append("decision_utility_evaluation.pairing_id_must_match")
    if item.get("object_class") != "DECISION_UTILITY_EVALUATION" or item.get("claim_class") != "MATERIAL_DECISION_UTILITY_REVIEW": findings.append("decision_utility_evaluation.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS: findings.append("decision_utility_evaluation.outputs_must_remain_evaluation_only")
    if not _text(item.get("evaluation_id")) or not _text(item.get("reviewer_id")) or not _text(item.get("outcome_settlement_ref")): findings.append("decision_utility_evaluation.identity_or_outcome_ref_missing")
    evaluated, frozen = _instant(item.get("evaluated_at"), "decision_utility_evaluation.evaluated_at", findings), _instant(_mapping(pairing).get("frozen_at"), "decision_utility_pairing.frozen_at", findings)
    if evaluated and frozen and evaluated < frozen: findings.append("decision_utility_evaluation.must_follow_pairing_freeze")
    contract_roles = _mapping(contract).get("roles") if isinstance(_mapping(contract).get("roles"), dict) else {}
    if item.get("reviewer_id") in set(contract_roles.values()): findings.append("decision_utility_evaluation.reviewer_must_be_independent_of_contract_roles")
    seen: set[str] = set()
    dimension_findings: list[dict[str, Any]] = []
    for index, raw in enumerate(_items(item.get("dimension_findings"))):
        finding = _closed(raw, _EVALUATION_FINDING_KEYS, f"decision_utility_evaluation.dimension_findings[{index}]", findings)
        dimension_findings.append(finding)
        dimension = finding.get("dimension_id")
        if dimension not in DIMENSIONS or dimension in seen: findings.append(f"decision_utility_evaluation.dimension_findings[{index}].dimension_invalid_or_duplicate")
        seen.add(str(dimension))
        for field in ("baseline_assessment", "enhanced_assessment"):
            allowed_assessments = HISTORICAL_ASSESSMENTS if historical else ASSESSMENTS
            if finding.get(field) not in allowed_assessments: findings.append(f"decision_utility_evaluation.dimension_findings[{index}].{field}_invalid")
        if not _text(finding.get("rationale")): findings.append(f"decision_utility_evaluation.dimension_findings[{index}].rationale_required")
        supporting = _items(finding.get("supporting_cell_ids"))
        allowed_cells = {
            cell.get("outcome_cell_id")
            for episode in (baseline_episode, enhanced_episode)
            for cell in _items(_mapping(episode).get("outcome_cells"))
            if isinstance(cell, dict) and _text(cell.get("outcome_cell_id"))
        } | {
            cell_id
            for episode in (baseline_episode, enhanced_episode)
            for claim in _items(_mapping(episode).get("claims"))
            if isinstance(claim, dict)
            for cell_id in _items(claim.get("dependent_outcome_cell_ids"))
            if _text(cell_id)
        }
        if not supporting or len(set(supporting)) != len(supporting) or any(
            not _text(cell_id) or cell_id not in allowed_cells for cell_id in supporting
        ):
            findings.append(f"decision_utility_evaluation.dimension_findings[{index}].supporting_cell_ids_invalid")
    if seen != set(DIMENSIONS): findings.append("decision_utility_evaluation.must_cover_each_material_dimension_once")
    holdout = _closed(item.get("holdout"), _HOLDOUT_KEYS, "decision_utility_evaluation.holdout", findings)
    train, held = set(_items(holdout.get("training_company_ids"))), set(_items(holdout.get("holdout_company_ids")))
    if not train or not held or train & held: findings.append("decision_utility_evaluation.holdout_company_axis_invalid")
    before, after = _instant(holdout.get("training_cutoff_through"), "decision_utility_evaluation.holdout.training_cutoff_through", findings), _instant(holdout.get("holdout_cutoff_from"), "decision_utility_evaluation.holdout.holdout_cutoff_from", findings)
    if before and after and before >= after: findings.append("decision_utility_evaluation.holdout_time_axis_invalid")
    verdict: str | None = None
    if not historical:
        if item.get("artifact_status") != "EVALUATED":
            findings.append("decision_utility_evaluation.artifact_status_must_be_evaluated")
        if item.get("authority_ceiling") != "CANDIDATE_ONLY":
            findings.append("decision_utility_evaluation.authority_ceiling_invalid")
        verdict = item.get("overall_utility_verdict")
        if verdict not in UTILITY_VERDICTS:
            findings.append("decision_utility_evaluation.overall_utility_verdict_invalid")
        elif verdict != _utility_verdict(dimension_findings):
            findings.append("decision_utility_evaluation.overall_utility_verdict_inconsistent")
    return {
        "valid": not findings,
        "findings": findings,
        "artifact_status": "HISTORICAL_READ_ONLY" if historical else item.get("artifact_status"),
        "authority_ceiling": "NONE" if historical else item.get("authority_ceiling"),
        "overall_utility_verdict": verdict,
        "learning_authorization": (
            "CANDIDATE_ONLY" if not findings and verdict == "MATERIAL_UTILITY" else "NONE"
        ),
    }


def validate_decision_utility_control_pairing(
    pairing: Any, *, forecast: Any, forecast_pairing: Any, contract: Any,
    baseline_episode: Any | None = None, enhanced_episode: Any | None = None,
) -> dict[str, Any]:
    """Validate a production pairing against immutable forecast control artifacts.

    The existing v1 objects remain useful for fixture-only design exercises.
    A control-plane pairing is deliberately different: it can only cite the
    pre-outcome Forecast Pairing V3 that already owns the frozen
    company-and-time outcome-window binding.
    """
    findings: list[str] = []
    historical = _mapping(pairing).get("schema_version") == HISTORICAL_CONTROL_PAIRING_SCHEMA_VERSION
    item = _closed(
        pairing,
        _HISTORICAL_CONTROL_PAIRING_KEYS if historical else _CONTROL_PAIRING_KEYS,
        "decision_utility_control_pairing",
        findings,
    )
    frozen = _mapping(forecast)
    forecast_pair = _mapping(forecast_pairing)
    contract_item = _mapping(contract)

    expected_version = (
        HISTORICAL_CONTROL_PAIRING_SCHEMA_VERSION if historical else CONTROL_PAIRING_SCHEMA_VERSION
    )
    if item.get("schema_version") != expected_version:
        findings.append("decision_utility_control_pairing.schema_version_invalid")
    if item.get("object_class") != "DECISION_UTILITY_PAIRING" or item.get("claim_class") != "SAME_CONTRACT_METHOD_ABLATION":
        findings.append("decision_utility_control_pairing.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append("decision_utility_control_pairing.outputs_must_remain_evaluation_only")
    for field in ("pairing_id", "forecast_id", "forecast_pairing_id"):
        if not _text(item.get(field)):
            findings.append(f"decision_utility_control_pairing.{field}_required")
    if item.get("forecast_id") != frozen.get("forecast_id"):
        findings.append("decision_utility_control_pairing.forecast_id_must_match_frozen_forecast")
    if frozen.get("schema_version") != "turtle-pit-company-state-forecast.v6":
        findings.append("decision_utility_control_pairing.requires_forecast_v6_method_identity")
    if item.get("forecast_pairing_id") != forecast_pair.get("pairing_id"):
        findings.append("decision_utility_control_pairing.forecast_pairing_id_must_match_registered_pairing")
    if forecast_pair.get("schema_version") != "turtle-pit-forecast-pairing.v3":
        findings.append("decision_utility_control_pairing.requires_frozen_forecast_pairing_v3")
    if forecast_pair.get("forecast_id") != frozen.get("forecast_id"):
        findings.append("decision_utility_control_pairing.forecast_pairing_must_match_frozen_forecast")
    if not isinstance(forecast_pair.get("holdout_binding"), dict):
        findings.append("decision_utility_control_pairing.requires_canonical_company_time_holdout")

    contract_result = contract_module.validate_training_decision_contract(contract_item)
    findings.extend("decision_contract:" + finding for finding in contract_result["findings"])
    expected_ref = {"contract_id": contract_item.get("contract_id"), "contract_version": contract_item.get("contract_version")}
    ref = _closed(item.get("decision_contract_ref"), _REF_KEYS, "decision_utility_control_pairing.decision_contract_ref", findings)
    if ref != expected_ref or frozen.get("decision_contract_ref") != expected_ref:
        findings.append("decision_utility_control_pairing.contract_reference_must_match_frozen_forecast")

    for field in ("baseline_episode_id", "enhanced_episode_id", "baseline_method_id", "enhanced_method_id"):
        if not _text(item.get(field)):
            findings.append(f"decision_utility_control_pairing.{field}_required")
    _research_cost(item.get("baseline_research_cost_hours"), "decision_utility_control_pairing.baseline_research_cost_hours", findings)
    _research_cost(item.get("enhanced_research_cost_hours"), "decision_utility_control_pairing.enhanced_research_cost_hours", findings)
    _validate_episode_pair(
        item, contract=contract, baseline_episode=baseline_episode, enhanced_episode=enhanced_episode,
        findings=findings, path="decision_utility_control_pairing",
    )
    if item.get("baseline_method_id") != forecast_pair.get("baseline_method_id"):
        findings.append("decision_utility_control_pairing.baseline_method_must_match_forecast_pairing")
    if item.get("enhanced_method_id") != forecast_pair.get("enhanced_method_id"):
        findings.append("decision_utility_control_pairing.enhanced_method_must_match_forecast_pairing")
    if item.get("baseline_method_id") == item.get("enhanced_method_id"):
        findings.append("decision_utility_control_pairing.methods_must_differ")
    _instant(item.get("frozen_at"), "decision_utility_control_pairing.frozen_at", findings)
    if not historical:
        support_bindings = _validate_outcome_support_bindings(
            item.get("outcome_support_bindings"),
            path="decision_utility_control_pairing.outcome_support_bindings", findings=findings,
            baseline_episode=baseline_episode, enhanced_episode=enhanced_episode,
        )
        available_cells = {
            (str(cell.get("dimension_id")), str(cell.get("window_id")))
            for cell in (_mapping(raw) for raw in _items(forecast_pair.get("baseline_cells")))
        } & set(_forecast_cell_index(frozen))
        evaluated_cells = {
            (str(cell.get("dimension_id")), str(cell.get("window_id")))
            for cell in (
                _mapping(raw)
                for raw in _items(_mapping(forecast_pair.get("holdout_binding")).get("evaluated_cells"))
            )
        }
        for index, binding in enumerate(support_bindings):
            refs = {
                (str(ref.get("dimension_id")), str(ref.get("window_id")))
                for ref in (
                    _mapping(raw) for raw in _items(binding.get("supporting_forecast_cells"))
                )
            }
            if not refs.issubset(available_cells & evaluated_cells):
                findings.append(
                    "decision_utility_control_pairing.outcome_support_bindings"
                    f"[{index}].supporting_forecast_cells_must_be_pre_registered"
                )
        if item.get("artifact_status") != "FROZEN":
            findings.append("decision_utility_control_pairing.artifact_status_must_be_frozen")
        if item.get("authority_ceiling") != "NONE":
            findings.append("decision_utility_control_pairing.authority_ceiling_must_be_none")
    return {
        "valid": not findings,
        "findings": findings,
        "pairing": deepcopy(item) if not findings else None,
        "artifact_status": "HISTORICAL_READ_ONLY" if historical else item.get("artifact_status"),
        "authority_ceiling": "NONE",
        "learning_authorization": "NONE",
    }


def validate_decision_utility_control_evaluation(
    evaluation: Any, *, pairing: Any, forecast: Any, forecast_pairing: Any,
    forecast_paired_evaluation: Any, contract: Any, baseline_episode: Any | None = None,
    enhanced_episode: Any | None = None, settlement: Any | None = None,
) -> dict[str, Any]:
    """Validate an independent decision review from exact persisted outcomes.

    The input intentionally has no caller-authored settlement reference or
    holdout.  Both are resolved from the immutable Forecast Pairing V3 and
    its registered paired evaluation by the control plane.
    """
    historical_pairing = (
        _mapping(pairing).get("schema_version") == HISTORICAL_CONTROL_PAIRING_SCHEMA_VERSION
    )
    historical_evaluation = (
        _mapping(evaluation).get("schema_version") == HISTORICAL_CONTROL_EVALUATION_SCHEMA_VERSION
    )
    historical = historical_pairing and historical_evaluation
    pairing_result = validate_decision_utility_control_pairing(
        pairing, forecast=forecast, forecast_pairing=forecast_pairing, contract=contract,
        baseline_episode=baseline_episode, enhanced_episode=enhanced_episode,
    )
    findings = ["pairing:" + finding for finding in pairing_result["findings"]]
    if historical_pairing != historical_evaluation:
        findings.append("decision_utility_control_evaluation.pairing_and_evaluation_version_epoch_mismatch")
    item = _closed(
        evaluation,
        _HISTORICAL_CONTROL_EVALUATION_KEYS if historical else _CONTROL_EVALUATION_KEYS,
        "decision_utility_control_evaluation",
        findings,
    )
    paired = _mapping(forecast_paired_evaluation)
    contract_item = _mapping(contract)

    expected_version = (
        HISTORICAL_CONTROL_EVALUATION_SCHEMA_VERSION if historical else CONTROL_EVALUATION_SCHEMA_VERSION
    )
    if item.get("schema_version") != expected_version:
        findings.append("decision_utility_control_evaluation.schema_version_invalid")
    if item.get("object_class") != "DECISION_UTILITY_EVALUATION" or item.get("claim_class") != "MATERIAL_DECISION_UTILITY_REVIEW":
        findings.append("decision_utility_control_evaluation.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append("decision_utility_control_evaluation.outputs_must_remain_evaluation_only")
    for field in ("evaluation_id", "pairing_id", "forecast_paired_evaluation_id", "reviewer_id"):
        if not _text(item.get(field)):
            findings.append(f"decision_utility_control_evaluation.{field}_required")
    if item.get("pairing_id") != _mapping(pairing).get("pairing_id"):
        findings.append("decision_utility_control_evaluation.pairing_id_must_match")
    if item.get("forecast_paired_evaluation_id") != paired.get("evaluation_id"):
        findings.append("decision_utility_control_evaluation.forecast_paired_evaluation_id_must_match")
    if paired.get("pairing_id") != _mapping(forecast_pairing).get("pairing_id"):
        findings.append("decision_utility_control_evaluation.forecast_paired_evaluation_must_match_forecast_pairing")
    if paired.get("forecast_id") != _mapping(forecast).get("forecast_id"):
        findings.append("decision_utility_control_evaluation.forecast_paired_evaluation_must_match_frozen_forecast")
    evaluated = _instant(item.get("evaluated_at"), "decision_utility_control_evaluation.evaluated_at", findings)
    paired_at = _instant(paired.get("evaluated_at"), "forecast_paired_evaluation.evaluated_at", findings)
    if evaluated and paired_at and evaluated < paired_at:
        findings.append("decision_utility_control_evaluation.must_follow_forecast_paired_evaluation")
    roles = _mapping(contract_item.get("roles"))
    if item.get("reviewer_id") in set(roles.values()):
        findings.append("decision_utility_control_evaluation.reviewer_must_be_independent_of_contract_roles")
    seen: set[str] = set()
    dimension_findings: list[dict[str, Any]] = []
    for index, raw in enumerate(_items(item.get("dimension_findings"))):
        finding = _closed(raw, _FINDING_KEYS, f"decision_utility_control_evaluation.dimension_findings[{index}]", findings)
        dimension_findings.append(finding)
        dimension = finding.get("dimension_id")
        if dimension not in DIMENSIONS or dimension in seen:
            findings.append(f"decision_utility_control_evaluation.dimension_findings[{index}].dimension_invalid_or_duplicate")
        seen.add(str(dimension))
        for field in ("baseline_assessment", "enhanced_assessment"):
            allowed_assessments = HISTORICAL_ASSESSMENTS if historical else ASSESSMENTS
            if finding.get(field) not in allowed_assessments:
                findings.append(f"decision_utility_control_evaluation.dimension_findings[{index}].{field}_invalid")
        if not _text(finding.get("rationale")):
            findings.append(f"decision_utility_control_evaluation.dimension_findings[{index}].rationale_required")
    if seen != set(DIMENSIONS):
        findings.append("decision_utility_control_evaluation.must_cover_each_material_dimension_once")
    verdict: str | None = None
    if not historical:
        if item.get("artifact_status") != "EVALUATED":
            findings.append("decision_utility_control_evaluation.artifact_status_must_be_evaluated")
        if item.get("authority_ceiling") != "CANDIDATE_ONLY":
            findings.append("decision_utility_control_evaluation.authority_ceiling_invalid")
        verdict = item.get("overall_utility_verdict")
        if verdict not in UTILITY_VERDICTS:
            findings.append("decision_utility_control_evaluation.overall_utility_verdict_invalid")
        elif verdict != _utility_verdict(dimension_findings):
            findings.append("decision_utility_control_evaluation.overall_utility_verdict_inconsistent")
    return {
        "valid": not findings,
        "findings": findings,
        "evaluation": deepcopy(item) if not findings else None,
        "artifact_status": "HISTORICAL_READ_ONLY" if historical else item.get("artifact_status"),
        "authority_ceiling": "NONE" if historical else item.get("authority_ceiling"),
        "overall_utility_verdict": verdict,
        "learning_authorization": (
            "CANDIDATE_ONLY" if not findings and verdict == "MATERIAL_UTILITY" else "NONE"
        ),
    }
