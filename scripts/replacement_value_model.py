#!/usr/bin/env python3
"""Deterministic going-concern replacement-value model.

The model rebuilds the operating capability of a viable enterprise from
evidence-bound component ranges, then bridges the recognized enterprise range
to ordinary common equity.  Liquidation value and EPV remain separate
references: neither is added to, nor averaged with, replacement value.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


SCHEMA_VERSION = "replacement-value-model.v1"
RESULT_SCHEMA_VERSION = "replacement-value-model-result.v1"
READER_SCHEMA_VERSION = "replacement-value-reader-conclusions.v1"

COMPONENT_TYPES = {
    "CUSTOMER_RELATIONSHIP",
    "REGIONAL_OPERATING_ORGANIZATION",
    "CUSTOMER_ACQUISITION_CHANNEL",
    "FULFILLMENT_OR_PROJECT_TRACK_RECORD",
    "PROJECT_STARTUP_WORKING_CAPITAL",
    "OTHER_FUNCTIONAL_ASSET",
}
ESTIMATE_STATUSES = {"BOUNDED", "SCENARIO_ONLY", "UNKNOWN"}
RECOGNITION_STATUSES = {"RECOGNIZED", "SCENARIO_ONLY", "EXCLUDED", "UNKNOWN"}
CALCULATION_METHODS = {
    "DIRECT_RANGE",
    "SUM_OF_INPUT_RANGES",
    "PRODUCT_OF_INPUT_RANGES",
    "UNAVAILABLE",
}
RECOGNITION_METHODS = {"FULL", "FRACTION_OF_ESTIMATED_RANGE", "NOT_APPLICABLE"}
DOUBLE_COUNT_TREATMENTS = {
    "NOT_INCLUDED",
    "NETTED",
    "ALREADY_INCLUDED_EXCLUDED",
    "UNKNOWN_SCENARIO_ONLY",
}
SYNTHESIS_RULE = "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE"
LIQUIDATION_USE = "SEPARATE_STRESS_REFERENCE_NEVER_ADD"

_TOP_LEVEL_FIELDS = {
    "schema_version",
    "model_id",
    "company_id",
    "model_context",
    "basis",
    "components",
    "claims_bridge",
    "liquidation_floor_reference",
    "epv_cross_check",
}
_MODEL_CONTEXT_FIELDS = {"purpose", "method_fixture_id", "parameter_transfer_policy"}
_BASIS_FIELDS = {
    "valuation_basis", "value_scope", "economic_entity", "operating_perimeter",
    "ordinary_share_claim_scope", "currency", "unit", "as_of",
}
_COMPONENT_FIELDS = {
    "component_id", "component_type", "economic_function", "estimate_status",
    "calculation", "recognition", "uncertainty_treatment", "double_count_treatment",
}
_CALCULATION_FIELDS = {"method", "output_unit", "inputs"}
_INPUT_FIELDS = {
    "input_id", "metric", "range_low", "range_high", "unit", "basis",
    "evidence_ids", "parameter_scope",
}
_RECOGNITION_FIELDS = {"status", "method", "fraction_low", "fraction_high", "reason"}
_UNCERTAINTY_FIELDS = {"boundary", "investor_consequence", "promotion_evidence"}
_DOUBLE_COUNT_FIELDS = {
    "balance_sheet_working_capital", "epv_maintenance_need", "explanation",
}
_CLAIMS_FIELDS = {
    "non_operating_assets", "debt", "minority_interest", "other_priority_claims",
    "other_adjustments", "shares_outstanding",
}
_LIQUIDATION_FIELDS = {
    "status", "model_id", "value_scope", "currency", "as_of", "per_share_low",
    "per_share_high", "reason", "use",
}
_EPV_FIELDS = {
    "status", "model_id", "economic_entity", "operating_perimeter",
    "ordinary_share_claim_scope", "value_scope", "currency", "unit", "as_of",
    "equity_value_low", "equity_value_high", "shares_outstanding", "per_share_low",
    "per_share_high", "reason", "synthesis_rule",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _same(left: Any, right: Any, *, tolerance: float = 1e-9) -> bool:
    left_number = _number(left)
    right_number = _number(right)
    if left_number is None or right_number is None:
        return False
    return math.isclose(left_number, right_number, rel_tol=tolerance, abs_tol=tolerance)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _reject_unknown_fields(
    value: dict[str, Any], allowed: set[str], prefix: str, findings: list[str]
) -> None:
    findings.extend(prefix + ":unknown_field:" + field for field in sorted(set(value) - allowed))


def _range(
    value: Any,
    *,
    prefix: str,
    findings: list[str],
    nonnegative: bool,
) -> tuple[float, float] | None:
    item = _mapping(value)
    _reject_unknown_fields(item, {"range_low", "range_high"}, prefix, findings)
    low = _number(item.get("range_low"))
    high = _number(item.get("range_high"))
    if low is None or high is None or low > high or (nonnegative and low < 0):
        findings.append(prefix + ":range_invalid")
        return None
    return low, high


def _component_estimated_range(component: dict[str, Any]) -> tuple[float, float] | None:
    calculation = _mapping(component.get("calculation"))
    method = calculation.get("method")
    inputs = [_mapping(item) for item in _items(calculation.get("inputs"))]
    ranges = [
        (_number(item.get("range_low")), _number(item.get("range_high")))
        for item in inputs
    ]
    if method == "UNAVAILABLE" or not ranges or any(None in item for item in ranges):
        return None
    if method == "DIRECT_RANGE":
        return float(ranges[0][0]), float(ranges[0][1])
    if method == "SUM_OF_INPUT_RANGES":
        return (
            sum(float(item[0]) for item in ranges),
            sum(float(item[1]) for item in ranges),
        )
    if method == "PRODUCT_OF_INPUT_RANGES":
        low = 1.0
        high = 1.0
        for input_low, input_high in ranges:
            low *= float(input_low)
            high *= float(input_high)
        return low, high
    return None


def _component_recognized_range(
    component: dict[str, Any], estimated: tuple[float, float] | None
) -> tuple[float, float] | None:
    recognition = _mapping(component.get("recognition"))
    if recognition.get("status") != "RECOGNIZED" or estimated is None:
        return None
    if recognition.get("method") == "FULL":
        return estimated
    if recognition.get("method") == "FRACTION_OF_ESTIMATED_RANGE":
        fraction_low = _number(recognition.get("fraction_low"))
        fraction_high = _number(recognition.get("fraction_high"))
        if fraction_low is None or fraction_high is None:
            return None
        return estimated[0] * fraction_low, estimated[1] * fraction_high
    return None


def _validate_model_context(value: Any, findings: list[str]) -> str:
    context = _mapping(value)
    _reject_unknown_fields(context, _MODEL_CONTEXT_FIELDS, "model_context", findings)
    purpose = str(context.get("purpose") or "")
    policy = str(context.get("parameter_transfer_policy") or "")
    if purpose not in {"COMPANY_ANALYSIS", "METHOD_FIXTURE"}:
        findings.append("model_context:purpose_invalid")
        return purpose
    if purpose == "METHOD_FIXTURE":
        if not _text(context.get("method_fixture_id")):
            findings.append("model_context:method_fixture_id_missing")
        if policy != "METHOD_FIXTURE_PARAMETERS_NON_TRANSFERABLE":
            findings.append("model_context:method_fixture_parameters_must_be_non_transferable")
    else:
        if context.get("method_fixture_id") not in {None, ""}:
            findings.append("model_context:method_fixture_id_forbidden_for_company_analysis")
        if policy != "COMPANY_SPECIFIC_EVIDENCE_ONLY":
            findings.append("model_context:company_parameter_policy_invalid")
    return purpose


def _validate_basis(value: Any, findings: list[str]) -> dict[str, Any]:
    basis = _mapping(value)
    _reject_unknown_fields(basis, _BASIS_FIELDS, "basis", findings)
    if basis.get("valuation_basis") != "GOING_CONCERN_REPLACEMENT":
        findings.append("basis:valuation_basis_invalid")
    if basis.get("value_scope") != "enterprise":
        findings.append("basis:value_scope_must_be_enterprise")
    for field in (
        "economic_entity",
        "operating_perimeter",
        "ordinary_share_claim_scope",
        "currency",
        "unit",
        "as_of",
    ):
        if not _text(basis.get(field)):
            findings.append("basis:" + field + "_missing")
    return basis


def _validate_uncertainty(value: Any, prefix: str, findings: list[str]) -> None:
    treatment = _mapping(value)
    _reject_unknown_fields(treatment, _UNCERTAINTY_FIELDS, prefix + ":uncertainty", findings)
    for field in ("boundary", "investor_consequence", "promotion_evidence"):
        if not _text(treatment.get(field)):
            findings.append(prefix + ":uncertainty_" + field + "_missing")


def _validate_component(
    component: Any,
    *,
    index: int,
    purpose: str,
    basis: dict[str, Any],
    seen_ids: set[str],
    seen_types: set[str],
    findings: list[str],
) -> None:
    item = _mapping(component)
    prefix = f"components[{index}]"
    _reject_unknown_fields(item, _COMPONENT_FIELDS, prefix, findings)
    component_id = str(item.get("component_id") or "")
    if not component_id or component_id in seen_ids:
        findings.append(prefix + ":component_id_missing_or_duplicate")
    else:
        seen_ids.add(component_id)
        prefix = component_id
    component_type = str(item.get("component_type") or "")
    if component_type not in COMPONENT_TYPES:
        findings.append(prefix + ":component_type_invalid")
    elif component_type in seen_types:
        findings.append(prefix + ":component_type_duplicate")
    else:
        seen_types.add(component_type)
    if not _text(item.get("economic_function")):
        findings.append(prefix + ":economic_function_missing")

    estimate_status = str(item.get("estimate_status") or "")
    if estimate_status not in ESTIMATE_STATUSES:
        findings.append(prefix + ":estimate_status_invalid")
    calculation = _mapping(item.get("calculation"))
    _reject_unknown_fields(calculation, _CALCULATION_FIELDS, prefix + ":calculation", findings)
    method = str(calculation.get("method") or "")
    if method not in CALCULATION_METHODS:
        findings.append(prefix + ":calculation_method_invalid")
    if calculation.get("output_unit") != basis.get("unit"):
        findings.append(prefix + ":calculation_output_unit_basis_mismatch")
    inputs = _items(calculation.get("inputs"))
    if method == "DIRECT_RANGE" and len(inputs) != 1:
        findings.append(prefix + ":direct_range_requires_one_input")
    if method in {"SUM_OF_INPUT_RANGES", "PRODUCT_OF_INPUT_RANGES"} and len(inputs) < 2:
        findings.append(prefix + ":calculation_requires_multiple_inputs")
    if method == "UNAVAILABLE" and inputs:
        findings.append(prefix + ":unavailable_calculation_must_not_have_numeric_inputs")
    if estimate_status == "UNKNOWN" and method != "UNAVAILABLE":
        findings.append(prefix + ":unknown_must_not_have_computed_range")
    if estimate_status != "UNKNOWN" and method == "UNAVAILABLE":
        findings.append(prefix + ":bounded_or_scenario_component_requires_range")

    seen_input_ids: set[str] = set()
    for input_index, raw_input in enumerate(inputs):
        model_input = _mapping(raw_input)
        input_prefix = f"{prefix}:inputs[{input_index}]"
        _reject_unknown_fields(model_input, _INPUT_FIELDS, input_prefix, findings)
        input_id = str(model_input.get("input_id") or "")
        if not input_id or input_id in seen_input_ids:
            findings.append(input_prefix + ":input_id_missing_or_duplicate")
        else:
            seen_input_ids.add(input_id)
        for field in ("metric", "unit", "basis"):
            if not _text(model_input.get(field)):
                findings.append(input_prefix + ":" + field + "_missing")
        low = _number(model_input.get("range_low"))
        high = _number(model_input.get("range_high"))
        if low is None or high is None or low < 0 or low > high:
            findings.append(input_prefix + ":range_invalid")
        evidence_ids = _items(model_input.get("evidence_ids"))
        if not evidence_ids or any(not _text(evidence_id) for evidence_id in evidence_ids):
            findings.append(input_prefix + ":evidence_ids_missing")
        parameter_scope = model_input.get("parameter_scope")
        if purpose == "COMPANY_ANALYSIS":
            if parameter_scope != "COMPANY_SPECIFIC":
                findings.append(input_prefix + ":method_fixture_parameter_in_company_model")
            if any(not str(evidence_id).startswith("OBS:") for evidence_id in evidence_ids):
                findings.append(input_prefix + ":company_input_requires_verified_observation")
        elif purpose == "METHOD_FIXTURE":
            if parameter_scope != "METHOD_FIXTURE_ONLY":
                findings.append(input_prefix + ":fixture_parameter_scope_invalid")
            if any(not str(evidence_id).startswith("METHOD:") for evidence_id in evidence_ids):
                findings.append(input_prefix + ":fixture_input_requires_method_evidence_identity")

    recognition = _mapping(item.get("recognition"))
    _reject_unknown_fields(recognition, _RECOGNITION_FIELDS, prefix + ":recognition", findings)
    recognition_status = str(recognition.get("status") or "")
    recognition_method = str(recognition.get("method") or "")
    if recognition_status not in RECOGNITION_STATUSES:
        findings.append(prefix + ":recognition_status_invalid")
    if recognition_method not in RECOGNITION_METHODS:
        findings.append(prefix + ":recognition_method_invalid")
    if not _text(recognition.get("reason")):
        findings.append(prefix + ":recognition_reason_missing")

    fraction_low = _number(recognition.get("fraction_low"))
    fraction_high = _number(recognition.get("fraction_high"))
    if recognition_status == "RECOGNIZED":
        if estimate_status != "BOUNDED":
            findings.append(prefix + ":only_bounded_component_can_be_recognized")
        if recognition_method == "FRACTION_OF_ESTIMATED_RANGE":
            if (
                fraction_low is None
                or fraction_high is None
                or fraction_low < 0
                or fraction_low > fraction_high
                or fraction_high > 1
            ):
                findings.append(prefix + ":recognition_fraction_invalid")
        elif recognition_method == "FULL":
            if fraction_low is not None or fraction_high is not None:
                findings.append(prefix + ":full_recognition_must_not_have_fraction")
        else:
            findings.append(prefix + ":recognized_component_method_invalid")
    else:
        if recognition_method != "NOT_APPLICABLE":
            findings.append(prefix + ":unrecognized_component_method_must_be_not_applicable")
        if fraction_low is not None or fraction_high is not None:
            findings.append(prefix + ":unrecognized_component_must_not_have_fraction")

    if estimate_status == "UNKNOWN":
        if recognition_status != "UNKNOWN":
            findings.append(prefix + ":unknown_estimate_must_remain_unknown")
        _validate_uncertainty(item.get("uncertainty_treatment"), prefix, findings)
    elif estimate_status == "SCENARIO_ONLY":
        if recognition_status != "SCENARIO_ONLY":
            findings.append(prefix + ":scenario_estimate_cannot_enter_recognized_value")
        _validate_uncertainty(item.get("uncertainty_treatment"), prefix, findings)
    elif recognition_status == "SCENARIO_ONLY":
        _validate_uncertainty(item.get("uncertainty_treatment"), prefix, findings)

    estimated = _component_estimated_range(item)
    recognized = _component_recognized_range(item, estimated)
    if estimate_status != "UNKNOWN" and estimated is None:
        findings.append(prefix + ":component_range_not_computable")
    if recognition_status == "RECOGNIZED" and recognized is None:
        findings.append(prefix + ":recognized_range_not_computable")
    elif recognized is not None and recognized[0] > recognized[1]:
        findings.append(prefix + ":recognized_range_invalid")

    double_count = _mapping(item.get("double_count_treatment"))
    if component_type == "PROJECT_STARTUP_WORKING_CAPITAL":
        _reject_unknown_fields(double_count, _DOUBLE_COUNT_FIELDS, prefix + ":double_count", findings)
        for field in ("balance_sheet_working_capital", "epv_maintenance_need"):
            if double_count.get(field) not in DOUBLE_COUNT_TREATMENTS:
                findings.append(prefix + ":double_count_" + field + "_missing_or_invalid")
        if not _text(double_count.get("explanation")):
            findings.append(prefix + ":double_count_explanation_missing")
        treatments = {
            double_count.get("balance_sheet_working_capital"),
            double_count.get("epv_maintenance_need"),
        }
        if "ALREADY_INCLUDED_EXCLUDED" in treatments and recognition_status != "EXCLUDED":
            findings.append(prefix + ":already_included_working_capital_must_be_excluded")
        if "UNKNOWN_SCENARIO_ONLY" in treatments and recognition_status not in {
            "SCENARIO_ONLY",
            "UNKNOWN",
        }:
            findings.append(prefix + ":unknown_working_capital_overlap_cannot_be_recognized")


def _validate_claims_bridge(value: Any, findings: list[str]) -> dict[str, Any]:
    bridge = _mapping(value)
    _reject_unknown_fields(bridge, _CLAIMS_FIELDS, "claims_bridge", findings)
    for field in (
        "non_operating_assets",
        "debt",
        "minority_interest",
        "other_priority_claims",
    ):
        _range(bridge.get(field), prefix="claims_bridge:" + field, findings=findings, nonnegative=True)
    _range(
        bridge.get("other_adjustments"),
        prefix="claims_bridge:other_adjustments",
        findings=findings,
        nonnegative=False,
    )
    shares = _number(bridge.get("shares_outstanding"))
    if shares is None or shares <= 0:
        findings.append("claims_bridge:shares_outstanding_invalid")
    return bridge


def _validate_liquidation_reference(
    value: Any, *, basis: dict[str, Any], findings: list[str]
) -> None:
    reference = _mapping(value)
    _reject_unknown_fields(reference, _LIQUIDATION_FIELDS, "liquidation_floor_reference", findings)
    status = str(reference.get("status") or "")
    if status not in {"AVAILABLE", "UNAVAILABLE"}:
        findings.append("liquidation_floor_reference:status_invalid")
    if reference.get("use") != LIQUIDATION_USE:
        findings.append("liquidation_floor_reference:must_remain_separate")
    if status == "AVAILABLE":
        for field in ("model_id", "currency", "as_of"):
            if not _text(reference.get(field)):
                findings.append("liquidation_floor_reference:" + field + "_missing")
        if reference.get("value_scope") != "ordinary_common_equity_per_share":
            findings.append("liquidation_floor_reference:value_scope_invalid")
        low = _number(reference.get("per_share_low"))
        high = _number(reference.get("per_share_high"))
        if low is None or high is None or low > high:
            findings.append("liquidation_floor_reference:per_share_range_invalid")
        if reference.get("currency") != basis.get("currency"):
            findings.append("liquidation_floor_reference:currency_mismatch")
    elif status == "UNAVAILABLE" and not _text(reference.get("reason")):
        findings.append("liquidation_floor_reference:unavailable_reason_missing")


def _validate_epv_cross_check(
    value: Any,
    *,
    basis: dict[str, Any],
    claims_bridge: dict[str, Any],
    findings: list[str],
) -> None:
    cross_check = _mapping(value)
    _reject_unknown_fields(cross_check, _EPV_FIELDS, "epv_cross_check", findings)
    status = str(cross_check.get("status") or "")
    if status not in {"COMPARABLE", "NOT_COMPARABLE", "UNAVAILABLE"}:
        findings.append("epv_cross_check:status_invalid")
    if cross_check.get("synthesis_rule") != SYNTHESIS_RULE:
        findings.append("epv_cross_check:replacement_and_epv_must_never_be_added_or_averaged")
    if status != "COMPARABLE":
        if not _text(cross_check.get("reason")):
            findings.append("epv_cross_check:noncomparable_reason_missing")
        return

    for field in (
        "model_id",
        "economic_entity",
        "operating_perimeter",
        "ordinary_share_claim_scope",
        "currency",
        "unit",
        "as_of",
    ):
        if not _text(cross_check.get(field)):
            findings.append("epv_cross_check:" + field + "_missing")
    if cross_check.get("value_scope") != "ordinary_common_equity":
        findings.append("epv_cross_check:value_scope_invalid")
    for field in (
        "economic_entity",
        "operating_perimeter",
        "ordinary_share_claim_scope",
        "currency",
        "unit",
        "as_of",
    ):
        if cross_check.get(field) != basis.get(field):
            findings.append("epv_cross_check:basis_mismatch:" + field)

    equity_low = _number(cross_check.get("equity_value_low"))
    equity_high = _number(cross_check.get("equity_value_high"))
    shares = _number(cross_check.get("shares_outstanding"))
    per_share_low = _number(cross_check.get("per_share_low"))
    per_share_high = _number(cross_check.get("per_share_high"))
    if equity_low is None or equity_high is None or equity_low > equity_high:
        findings.append("epv_cross_check:equity_range_invalid")
    if shares is None or shares <= 0:
        findings.append("epv_cross_check:shares_outstanding_invalid")
    elif not _same(shares, claims_bridge.get("shares_outstanding")):
        findings.append("epv_cross_check:shares_outstanding_mismatch")
    if per_share_low is None or per_share_high is None or per_share_low > per_share_high:
        findings.append("epv_cross_check:per_share_range_invalid")
    elif equity_low is not None and equity_high is not None and shares is not None and shares > 0:
        if not _same(per_share_low, equity_low / shares) or not _same(
            per_share_high, equity_high / shares
        ):
            findings.append("epv_cross_check:per_share_arithmetic_mismatch")


def validate_replacement_value_model(payload: Any) -> dict[str, Any]:
    """Validate evidence, range, recognition, claims and comparison contracts."""
    value = _mapping(payload)
    findings: list[str] = []
    if not isinstance(payload, dict):
        findings.append("model_not_object")
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    unknown_fields = sorted(set(value) - _TOP_LEVEL_FIELDS)
    findings.extend("unknown_top_level_field:" + field for field in unknown_fields)
    for field in ("model_id", "company_id"):
        if not _text(value.get(field)):
            findings.append(field + "_missing")

    purpose = _validate_model_context(value.get("model_context"), findings)
    basis = _validate_basis(value.get("basis"), findings)
    components = _items(value.get("components"))
    if not components:
        findings.append("components_missing")
    seen_ids: set[str] = set()
    seen_types: set[str] = set()
    for index, component in enumerate(components):
        _validate_component(
            component,
            index=index,
            purpose=purpose,
            basis=basis,
            seen_ids=seen_ids,
            seen_types=seen_types,
            findings=findings,
        )
    if purpose == "COMPANY_ANALYSIS":
        findings.extend(
            "components:required_component_type_missing:" + component_type
            for component_type in sorted(COMPONENT_TYPES - seen_types)
        )
    claims_bridge = _validate_claims_bridge(value.get("claims_bridge"), findings)
    _validate_liquidation_reference(
        value.get("liquidation_floor_reference"), basis=basis, findings=findings
    )
    _validate_epv_cross_check(
        value.get("epv_cross_check"),
        basis=basis,
        claims_bridge=claims_bridge,
        findings=findings,
    )
    findings = _unique(findings)
    return {
        "schema_version": "replacement-value-model-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
    }


def _required_range(value: Any) -> tuple[float, float]:
    item = _mapping(value)
    return float(item["range_low"]), float(item["range_high"])


def _comparison_relationship(
    replacement: tuple[float, float], epv: tuple[float, float]
) -> str:
    if replacement[1] < epv[0]:
        return "REPLACEMENT_BELOW_EPV"
    if replacement[0] > epv[1]:
        return "REPLACEMENT_ABOVE_EPV"
    return "OVERLAPS"


def compute_replacement_value_model(payload: Any) -> dict[str, Any]:
    """Compute a replacement range without combining it with liquidation or EPV."""
    validation = validate_replacement_value_model(payload)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("replacement_value_model_invalid:" + ",".join(validation["findings"]))
    value = _mapping(payload)
    component_results: list[dict[str, Any]] = []
    recognized_ranges: list[tuple[float, float]] = []
    unknown_ids: list[str] = []
    scenario_ids: list[str] = []
    excluded_ids: list[str] = []
    for component in value["components"]:
        item = _mapping(component)
        estimated = _component_estimated_range(item)
        recognized = _component_recognized_range(item, estimated)
        recognition_status = item["recognition"]["status"]
        evidence_ids = _unique(
            [
                str(evidence_id)
                for model_input in item["calculation"]["inputs"]
                for evidence_id in model_input["evidence_ids"]
            ]
        )
        result = {
            "component_id": item["component_id"],
            "component_type": item["component_type"],
            "estimate_status": item["estimate_status"],
            "estimated_range": (
                {"range_low": estimated[0], "range_high": estimated[1]}
                if estimated is not None
                else None
            ),
            "recognition_status": recognition_status,
            "recognized_range": (
                {"range_low": recognized[0], "range_high": recognized[1]}
                if recognized is not None
                else None
            ),
            "evidence_ids": evidence_ids,
        }
        if item.get("double_count_treatment") is not None:
            result["double_count_treatment"] = deepcopy(item["double_count_treatment"])
        component_results.append(result)
        if recognized is not None:
            recognized_ranges.append(recognized)
        if recognition_status == "UNKNOWN":
            unknown_ids.append(item["component_id"])
        elif recognition_status == "SCENARIO_ONLY":
            scenario_ids.append(item["component_id"])
        elif recognition_status == "EXCLUDED":
            excluded_ids.append(item["component_id"])

    gross_low = sum(item[0] for item in recognized_ranges)
    gross_high = sum(item[1] for item in recognized_ranges)
    bridge = value["claims_bridge"]
    non_operating_assets = _required_range(bridge["non_operating_assets"])
    debt = _required_range(bridge["debt"])
    minority_interest = _required_range(bridge["minority_interest"])
    other_priority_claims = _required_range(bridge["other_priority_claims"])
    other_adjustments = _required_range(bridge["other_adjustments"])
    # A component deliberately excluded because its economic cost is already
    # present elsewhere in the claims bridge is a resolved zero *increment*.
    # It must not be confused with an unknown or scenario-only component: the
    # former would wrongly suppress a complete going-concern range forever.
    full_scope = not unknown_ids and not scenario_ids
    equity_low: float | None = None
    equity_high: float | None = None
    if full_scope:
        equity_low = (
            gross_low
            + non_operating_assets[0]
            - debt[1]
            - minority_interest[1]
            - other_priority_claims[1]
            + other_adjustments[0]
        )
        equity_high = (
            gross_high
            + non_operating_assets[1]
            - debt[0]
            - minority_interest[0]
            - other_priority_claims[0]
            + other_adjustments[1]
        )
    shares = float(bridge["shares_outstanding"])
    per_share = (
        (equity_low / shares, equity_high / shares)
        if equity_low is not None and equity_high is not None
        else None
    )

    epv = value["epv_cross_check"]
    epv_result: dict[str, Any] = {
        "status": epv["status"],
        "synthesis_rule": SYNTHESIS_RULE,
        "relationship": "NOT_COMPARABLE",
    }
    if epv["status"] == "COMPARABLE" and full_scope:
        epv_range = (float(epv["equity_value_low"]), float(epv["equity_value_high"]))
        epv_result.update(
            {
                "model_id": epv["model_id"],
                "epv_equity_range": {
                    "range_low": epv_range[0],
                    "range_high": epv_range[1],
                },
                "epv_per_share_range": {
                    "range_low": float(epv["per_share_low"]),
                    "range_high": float(epv["per_share_high"]),
                },
                "relationship": _comparison_relationship((equity_low, equity_high), epv_range),
            }
        )
    elif epv["status"] == "COMPARABLE" and not full_scope:
        epv_result.update(
            {
                "model_id": epv["model_id"],
                "epv_equity_range": {
                    "range_low": float(epv["equity_value_low"]),
                    "range_high": float(epv["equity_value_high"]),
                },
                "epv_per_share_range": {
                    "range_low": float(epv["per_share_low"]),
                    "range_high": float(epv["per_share_high"]),
                },
                "relationship": "REPLACEMENT_SCOPE_INCOMPLETE",
                "reason": "The company-level going-concern replacement range is incomplete.",
            }
        )
    else:
        epv_result["reason"] = epv["reason"]

    recognized_scope = (
        "PARTIAL_RECOGNIZED_COMPONENTS"
        if unknown_ids or scenario_ids
        else "ALL_SUBMITTED_COMPONENTS_RECOGNIZED"
    )
    economic_conclusion = {
        "replacement_value_role": "GOING_CONCERN_REPLACEMENT_RANGE",
        "recognized_scope": recognized_scope,
        "replacement_range_status": "AVAILABLE" if full_scope else "INCOMPLETE",
        "claims_bridge_status": (
            "APPLIED_TO_COMPLETE_REPLACEMENT_RANGE"
            if full_scope
            else "NOT_APPLIED_TO_INCOMPLETE_REPLACEMENT_SCOPE"
        ),
        "epv_comparability": epv_result["status"],
        "replacement_vs_epv": epv_result["relationship"],
        "liquidation_floor_role": "SEPARATE_STRESS_REFERENCE",
        "synthesis_rule": SYNTHESIS_RULE,
        "investor_use": (
            "Use overlap or divergence to assess protection, impairment, excess capacity or franchise; "
            "never add or average replacement value and EPV."
        ),
    }

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "model_id": value["model_id"],
        "company_id": value["company_id"],
        "model_context": deepcopy(value["model_context"]),
        "basis": deepcopy(value["basis"]),
        "component_results": component_results,
        "gross_recognized_replacement_range": {
            "range_low": gross_low,
            "range_high": gross_high,
        },
        "claims_bridge": deepcopy(bridge),
        "ordinary_common_equity_range": (
            {"range_low": equity_low, "range_high": equity_high}
            if full_scope else None
        ),
        "per_share_range": (
            {"range_low": per_share[0], "range_high": per_share[1]}
            if per_share is not None else None
        ),
        "unknown_component_ids": unknown_ids,
        "scenario_only_component_ids": scenario_ids,
        "excluded_component_ids": excluded_ids,
        "liquidation_floor_reference": deepcopy(value["liquidation_floor_reference"]),
        "epv_cross_check": epv_result,
        "economic_conclusion": economic_conclusion,
        "synthesis_rule": SYNTHESIS_RULE,
    }


def _display_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _display_range(value: dict[str, Any]) -> str:
    return _display_number(float(value["range_low"])) + "–" + _display_number(
        float(value["range_high"])
    )


def project_replacement_value_reader_conclusions(result: Any) -> dict[str, Any]:
    """Translate a company result into plain investor-facing conclusions.

    Method fixtures deliberately have no reader projection: their parameters
    demonstrate a method and are not evidence for a current company.
    """
    value = _mapping(result)
    if value.get("schema_version") != RESULT_SCHEMA_VERSION:
        raise ValueError("replacement_value_result_invalid")
    if _mapping(value.get("model_context")).get("purpose") == "METHOD_FIXTURE":
        raise ValueError("method_fixture_has_no_company_reader_conclusion")
    basis = _mapping(value.get("basis"))
    currency = str(basis.get("currency") or "")
    unit = str(basis.get("unit") or "")
    conclusion = _mapping(value.get("economic_conclusion"))
    complete_range = conclusion.get("replacement_range_status") == "AVAILABLE"
    if complete_range:
        conclusions = [
            (
                "按持续经营重建口径，已获证据认可的经营能力重置成本为"
                f"{currency} {_display_range(value['gross_recognized_replacement_range'])} {unit}；"
                "这不是清算价值。"
            ),
            (
                "扣除债务、少数股东及其他优先索取权并加入非经营资产后，"
                f"普通股对应区间为{currency} {_display_range(value['ordinary_common_equity_range'])} {unit}，"
                f"即每股{currency} {_display_range(value['per_share_range'])}。"
            ),
        ]
    else:
        conclusions = [
            (
                "现有证据只能形成若干持续经营重建成本的逐项锚点，尚不能形成公司级重置价值区间；"
                "债务、少数股东和非经营资产桥因此没有被套到一个不完整的经营能力总额上。"
            )
        ]
        scenario_rows = [
            item
            for item in _items(value.get("component_results"))
            if _mapping(item).get("recognition_status") == "SCENARIO_ONLY"
            and isinstance(_mapping(item).get("estimated_range"), dict)
        ]
        if scenario_rows:
            labels = {
                "CUSTOMER_RELATIONSHIP": "客户关系",
                "REGIONAL_OPERATING_ORGANIZATION": "区域组织",
                "CUSTOMER_ACQUISITION_CHANNEL": "获客渠道",
                "FULFILLMENT_OR_PROJECT_TRACK_RECORD": "履约记录",
                "PROJECT_STARTUP_WORKING_CAPITAL": "项目启动营运资本",
                "OTHER_FUNCTIONAL_ASSET": "其他功能资产",
            }
            anchors = "；".join(
                labels.get(str(_mapping(item).get("component_type") or ""), "重建要素")
                + "为"
                + currency
                + " "
                + _display_range(_mapping(_mapping(item).get("estimated_range")))
                + " "
                + unit
                for item in scenario_rows
            )
            conclusions.append(
                "当前仅作情景观察的成本锚为：" + anchors + "；它们不构成完整公司价值。"
            )
    unknown_ids = _items(value.get("unknown_component_ids"))
    if unknown_ids:
        conclusions.append(
            f"另有{len(unknown_ids)}项重建要素仍无法可靠定界；它们没有被当作零或精确中点，"
            "因此当前不提供普通股每股重置价值。"
        )

    liquidation = _mapping(value.get("liquidation_floor_reference"))
    if liquidation.get("status") == "AVAILABLE":
        conclusions.append(
            "清算压力底另行为每股"
            f"{liquidation['currency']} {_display_number(float(liquidation['per_share_low']))}–"
            f"{_display_number(float(liquidation['per_share_high']))}；它只检验下行，"
            "不与持续经营重置价值相加。"
        )
    else:
        conclusions.append(
            "清算压力底尚不能可靠定界，原因是"
            + str(liquidation.get("reason") or "公开证据不足")
            + "；这不改变持续经营重置价值的独立身份。"
        )

    epv = _mapping(value.get("epv_cross_check"))
    if (
        epv.get("status") == "COMPARABLE"
        and epv.get("relationship") != "REPLACEMENT_SCOPE_INCOMPLETE"
    ):
        relationship = {
            "OVERLAPS": "两者区间重叠",
            "REPLACEMENT_BELOW_EPV": "重置价值低于盈利能力价值",
            "REPLACEMENT_ABOVE_EPV": "重置价值高于盈利能力价值",
        }[str(epv["relationship"])]
        conclusions.append(
            "在相同实体、币种、日期和普通股索取权口径下，"
            f"EPV每股区间为{currency} {_display_range(epv['epv_per_share_range'])}，{relationship}。"
            "两条路线只用于交叉核验，不相加，也不平均。"
        )
    elif epv.get("relationship") == "REPLACEMENT_SCOPE_INCOMPLETE":
        conclusions.append(
            "EPV的实体、币种、日期和普通股索取权口径已经对齐，但公司级重置范围仍不完整，"
            "所以当前不能比较两条价值下限，也不能形成共同保护价格。"
        )
    else:
        conclusions.append(
            "当前重置价值与EPV尚不具备同口径比较条件："
            + str(epv.get("reason") or "比较基础不完整")
            + "。在口径桥完成前，两者既不相加，也不平均。"
        )
    return {
        "schema_version": READER_SCHEMA_VERSION,
        "source_model_id": value["model_id"],
        "reader_conclusions": conclusions,
    }


__all__ = [
    "COMPONENT_TYPES",
    "LIQUIDATION_USE",
    "SCHEMA_VERSION",
    "SYNTHESIS_RULE",
    "compute_replacement_value_model",
    "project_replacement_value_reader_conclusions",
    "validate_replacement_value_model",
]
