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
    from scripts import judgment_training_decision_contract as contract_module
except ModuleNotFoundError:  # pragma: no cover
    import judgment_training_decision_contract as contract_module


PAIRING_SCHEMA_VERSION = "turtle-decision-utility-pairing.v1"
EVALUATION_SCHEMA_VERSION = "turtle-decision-utility-evaluation.v1"
CONTROL_PAIRING_SCHEMA_VERSION = "turtle-decision-utility-control-pairing.v1"
CONTROL_EVALUATION_SCHEMA_VERSION = "turtle-decision-utility-control-evaluation.v1"
ALLOWED_OUTPUTS = ["DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"]
DIMENSIONS = ["PERMANENT_LOSS_GUARDRAIL", "OWNER_CASH_ACCESS", "KEY_UNKNOWN_DISCOVERY", "RESEARCH_COST"]

_PAIRING_KEYS = {"schema_version", "pairing_id", "decision_contract_ref", "baseline", "enhanced", "frozen_at", "object_class", "claim_class", "allowed_outputs"}
_REF_KEYS = {"contract_id", "contract_version"}
_DECISION_KEYS = {"method_id", "decision_status", "material_unknown_ids", "evidence_budget_id", "source_packet_refs", "research_cost_hours"}
_EVALUATION_KEYS = {"schema_version", "evaluation_id", "pairing_id", "evaluated_at", "reviewer_id", "outcome_settlement_ref", "dimension_findings", "holdout", "object_class", "claim_class", "allowed_outputs"}
_FINDING_KEYS = {"dimension_id", "baseline_assessment", "enhanced_assessment", "rationale"}
_HOLDOUT_KEYS = {"training_company_ids", "holdout_company_ids", "training_cutoff_through", "holdout_cutoff_from"}
_CONTROL_PAIRING_KEYS = {
    "schema_version", "pairing_id", "forecast_id", "forecast_pairing_id", "decision_contract_ref",
    "baseline", "enhanced", "frozen_at", "object_class", "claim_class", "allowed_outputs",
}
_CONTROL_EVALUATION_KEYS = {
    "schema_version", "evaluation_id", "pairing_id", "forecast_paired_evaluation_id", "evaluated_at",
    "reviewer_id", "dimension_findings", "object_class", "claim_class", "allowed_outputs",
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

def _decision(value: Any, path: str, budget: dict[str, Any], findings: list[str]) -> dict[str, Any]:
    item = _closed(value, _DECISION_KEYS, path, findings)
    if not _text(item.get("method_id")): findings.append(f"{path}.method_id_required")
    if item.get("decision_status") not in {"PASS", "WATCH", "RESEARCH", "CONDITIONAL_BUYBAND"}: findings.append(f"{path}.decision_status_invalid")
    if not isinstance(item.get("material_unknown_ids"), list) or any(not _text(x) for x in item.get("material_unknown_ids", [])): findings.append(f"{path}.material_unknown_ids_invalid")
    if item.get("evidence_budget_id") != budget.get("evidence_budget_id") or item.get("source_packet_refs") != budget.get("source_packet_refs"):
        findings.append(f"{path}.must_use_same_frozen_evidence_budget")
    cost = item.get("research_cost_hours")
    if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0: findings.append(f"{path}.research_cost_hours_invalid")
    return item

def validate_decision_utility_pairing(pairing: Any, *, contract: Any) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(pairing, _PAIRING_KEYS, "decision_utility_pairing", findings)
    if item.get("schema_version") != PAIRING_SCHEMA_VERSION: findings.append("decision_utility_pairing.schema_version_invalid")
    if item.get("object_class") != "DECISION_UTILITY_PAIRING" or item.get("claim_class") != "SAME_CONTRACT_METHOD_ABLATION": findings.append("decision_utility_pairing.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS: findings.append("decision_utility_pairing.outputs_must_remain_evaluation_only")
    if not _text(item.get("pairing_id")): findings.append("decision_utility_pairing.pairing_id_required")
    result = contract_module.validate_training_decision_contract(contract)
    findings.extend("decision_contract:" + x for x in result["findings"])
    contract_item = _mapping(contract)
    ref = _closed(item.get("decision_contract_ref"), _REF_KEYS, "decision_utility_pairing.decision_contract_ref", findings)
    if ref != {"contract_id": contract_item.get("contract_id"), "contract_version": contract_item.get("contract_version")}:
        findings.append("decision_utility_pairing.contract_reference_must_match")
    budget = _mapping(contract_item.get("evidence_budget"))
    baseline, enhanced = _decision(item.get("baseline"), "decision_utility_pairing.baseline", budget, findings), _decision(item.get("enhanced"), "decision_utility_pairing.enhanced", budget, findings)
    if baseline.get("method_id") == enhanced.get("method_id"): findings.append("decision_utility_pairing.methods_must_differ")
    _instant(item.get("frozen_at"), "decision_utility_pairing.frozen_at", findings)
    return {"valid": not findings, "findings": findings, "pairing": deepcopy(item) if not findings else None}

def validate_decision_utility_evaluation(evaluation: Any, *, pairing: Any, contract: Any) -> dict[str, Any]:
    pair = validate_decision_utility_pairing(pairing, contract=contract)
    findings = ["pairing:" + x for x in pair["findings"]]
    item = _closed(evaluation, _EVALUATION_KEYS, "decision_utility_evaluation", findings)
    if item.get("schema_version") != EVALUATION_SCHEMA_VERSION: findings.append("decision_utility_evaluation.schema_version_invalid")
    if item.get("pairing_id") != _mapping(pairing).get("pairing_id"): findings.append("decision_utility_evaluation.pairing_id_must_match")
    if item.get("object_class") != "DECISION_UTILITY_EVALUATION" or item.get("claim_class") != "MATERIAL_DECISION_UTILITY_REVIEW": findings.append("decision_utility_evaluation.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS: findings.append("decision_utility_evaluation.outputs_must_remain_evaluation_only")
    if not _text(item.get("evaluation_id")) or not _text(item.get("reviewer_id")) or not _text(item.get("outcome_settlement_ref")): findings.append("decision_utility_evaluation.identity_or_outcome_ref_missing")
    evaluated, frozen = _instant(item.get("evaluated_at"), "decision_utility_evaluation.evaluated_at", findings), _instant(_mapping(pairing).get("frozen_at"), "decision_utility_pairing.frozen_at", findings)
    if evaluated and frozen and evaluated < frozen: findings.append("decision_utility_evaluation.must_follow_pairing_freeze")
    contract_roles = _mapping(contract).get("roles") if isinstance(_mapping(contract).get("roles"), dict) else {}
    if item.get("reviewer_id") in set(contract_roles.values()): findings.append("decision_utility_evaluation.reviewer_must_be_independent_of_contract_roles")
    seen: set[str] = set()
    for index, raw in enumerate(_items(item.get("dimension_findings"))):
        finding = _closed(raw, _FINDING_KEYS, f"decision_utility_evaluation.dimension_findings[{index}]", findings)
        dimension = finding.get("dimension_id")
        if dimension not in DIMENSIONS or dimension in seen: findings.append(f"decision_utility_evaluation.dimension_findings[{index}].dimension_invalid_or_duplicate")
        seen.add(str(dimension))
        for field in ("baseline_assessment", "enhanced_assessment"):
            if finding.get(field) not in {"AVOIDED_ERROR", "MATERIAL_IMPROVEMENT", "NO_DIFFERENCE", "UNKNOWN", "NOT_DIAGNOSTIC"}: findings.append(f"decision_utility_evaluation.dimension_findings[{index}].{field}_invalid")
        if not _text(finding.get("rationale")): findings.append(f"decision_utility_evaluation.dimension_findings[{index}].rationale_required")
    if seen != set(DIMENSIONS): findings.append("decision_utility_evaluation.must_cover_each_material_dimension_once")
    holdout = _closed(item.get("holdout"), _HOLDOUT_KEYS, "decision_utility_evaluation.holdout", findings)
    train, held = set(_items(holdout.get("training_company_ids"))), set(_items(holdout.get("holdout_company_ids")))
    if not train or not held or train & held: findings.append("decision_utility_evaluation.holdout_company_axis_invalid")
    before, after = _instant(holdout.get("training_cutoff_through"), "decision_utility_evaluation.holdout.training_cutoff_through", findings), _instant(holdout.get("holdout_cutoff_from"), "decision_utility_evaluation.holdout.holdout_cutoff_from", findings)
    if before and after and before >= after: findings.append("decision_utility_evaluation.holdout_time_axis_invalid")
    return {"valid": not findings, "findings": findings, "learning_authorization": "CANDIDATE_ONLY" if not findings else "NONE"}


def validate_decision_utility_control_pairing(
    pairing: Any, *, forecast: Any, forecast_pairing: Any, contract: Any,
) -> dict[str, Any]:
    """Validate a production pairing against immutable forecast control artifacts.

    The existing v1 objects remain useful for fixture-only design exercises.
    A control-plane pairing is deliberately different: it can only cite the
    pre-outcome Forecast Pairing V3 that already owns the frozen
    company-and-time outcome-window binding.
    """
    findings: list[str] = []
    item = _closed(pairing, _CONTROL_PAIRING_KEYS, "decision_utility_control_pairing", findings)
    frozen = _mapping(forecast)
    forecast_pair = _mapping(forecast_pairing)
    contract_item = _mapping(contract)

    if item.get("schema_version") != CONTROL_PAIRING_SCHEMA_VERSION:
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

    budget = _mapping(contract_item.get("evidence_budget"))
    baseline = _decision(item.get("baseline"), "decision_utility_control_pairing.baseline", budget, findings)
    enhanced = _decision(item.get("enhanced"), "decision_utility_control_pairing.enhanced", budget, findings)
    if baseline.get("method_id") != forecast_pair.get("baseline_method_id"):
        findings.append("decision_utility_control_pairing.baseline_method_must_match_forecast_pairing")
    if enhanced.get("method_id") != forecast_pair.get("enhanced_method_id"):
        findings.append("decision_utility_control_pairing.enhanced_method_must_match_forecast_pairing")
    if baseline.get("method_id") == enhanced.get("method_id"):
        findings.append("decision_utility_control_pairing.methods_must_differ")
    _instant(item.get("frozen_at"), "decision_utility_control_pairing.frozen_at", findings)
    return {
        "valid": not findings,
        "findings": findings,
        "pairing": deepcopy(item) if not findings else None,
        "learning_authorization": "CANDIDATE_ONLY" if not findings else "NONE",
    }


def validate_decision_utility_control_evaluation(
    evaluation: Any, *, pairing: Any, forecast: Any, forecast_pairing: Any,
    forecast_paired_evaluation: Any, contract: Any,
) -> dict[str, Any]:
    """Validate an independent decision review from exact persisted outcomes.

    The input intentionally has no caller-authored settlement reference or
    holdout.  Both are resolved from the immutable Forecast Pairing V3 and
    its registered paired evaluation by the control plane.
    """
    pairing_result = validate_decision_utility_control_pairing(
        pairing, forecast=forecast, forecast_pairing=forecast_pairing, contract=contract,
    )
    findings = ["pairing:" + finding for finding in pairing_result["findings"]]
    item = _closed(evaluation, _CONTROL_EVALUATION_KEYS, "decision_utility_control_evaluation", findings)
    paired = _mapping(forecast_paired_evaluation)
    contract_item = _mapping(contract)

    if item.get("schema_version") != CONTROL_EVALUATION_SCHEMA_VERSION:
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
    for index, raw in enumerate(_items(item.get("dimension_findings"))):
        finding = _closed(raw, _FINDING_KEYS, f"decision_utility_control_evaluation.dimension_findings[{index}]", findings)
        dimension = finding.get("dimension_id")
        if dimension not in DIMENSIONS or dimension in seen:
            findings.append(f"decision_utility_control_evaluation.dimension_findings[{index}].dimension_invalid_or_duplicate")
        seen.add(str(dimension))
        for field in ("baseline_assessment", "enhanced_assessment"):
            if finding.get(field) not in {"AVOIDED_ERROR", "MATERIAL_IMPROVEMENT", "NO_DIFFERENCE", "UNKNOWN", "NOT_DIAGNOSTIC"}:
                findings.append(f"decision_utility_control_evaluation.dimension_findings[{index}].{field}_invalid")
        if not _text(finding.get("rationale")):
            findings.append(f"decision_utility_control_evaluation.dimension_findings[{index}].rationale_required")
    if seen != set(DIMENSIONS):
        findings.append("decision_utility_control_evaluation.must_cover_each_material_dimension_once")
    return {
        "valid": not findings,
        "findings": findings,
        "evaluation": deepcopy(item) if not findings else None,
        "learning_authorization": "CANDIDATE_ONLY" if not findings else "NONE",
    }
