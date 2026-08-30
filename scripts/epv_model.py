#!/usr/bin/env python3
"""Deterministic earnings-power-value (EPV) owner.

The caller supplies source-bound economic operands.  This module owns every
derived normalization, tax, capitalization and enterprise-to-common-equity
calculation.  Missing material operands remain explicit and never become a
zero, a point estimate or an implied valuation range.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import math
from typing import Any


INPUT_SCHEMA_VERSION = "epv-model-input.v1"
OUTPUT_SCHEMA_VERSION = "epv-model.v1"
VALIDATION_SCHEMA_VERSION = "epv-model-validation.v1"

SYNTHESIS_RULE = "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE"

_TOP_FIELDS = {
    "schema_version", "model_id", "company_id", "cutoff_at", "basis",
    "earnings_evidence_status", "earnings_unknown_reason", "period_facts",
    "maintenance_capex", "maintenance_working_capital",
    "tax", "capitalization", "claims_bridge",
}
_BASIS_FIELDS = {
    "value_scope", "earnings_claim_scope", "economic_entity",
    "operating_perimeter", "ordinary_share_claim_scope", "currency", "unit",
    "as_of", "operating_cash_treatment", "operating_cash_component_ids",
}
_PERIOD_FIELDS = {
    "period_id", "period_start", "period_end", "metric", "basis_kind",
    "tax_basis", "amount", "amount_range", "working_capital_application",
    "observed_working_capital_charge", "source_fact_ids",
    "normalization_adjustments",
}
_PERIOD_RANGE_FIELDS = {"range_low", "range_high"}
_ADJUSTMENT_FIELDS = {
    "adjustment_id", "category", "direction", "amount", "tax_basis",
    "source_fact_ids", "economic_reason",
}
_COST_FIELDS = {
    "status", "range_low", "range_high", "tax_basis", "source_fact_ids",
    "reason", "source_model_id",
}
_TAX_FIELDS = {"status", "rate_low", "rate_high", "source_fact_ids", "reason"}
_CAP_FIELDS = {"status", "rate_low", "rate_high", "source_fact_ids", "reason"}
_CLAIMS_FIELDS = {
    "status", "bridge_mode", "non_operating_components", "debt",
    "preferred_claims", "minority_interest", "other_adjustments", "shares",
    "reason",
}
_COMPONENT_FIELDS = {
    "component_id", "kind", "range_low", "range_high", "claim_ids",
    "source_fact_ids",
}
_RANGE_FIELDS = {"range_low", "range_high", "source_fact_ids"}
_SHARES_FIELDS = {"value", "source_fact_ids"}

_BASIS_KINDS = {
    "PRE_MAINTENANCE_OWNER_EARNINGS_PRETAX",
    "PRE_MAINTENANCE_OWNER_EARNINGS_AFTER_TAX",
    "REPORTED_OCF_AFTER_TAX",
    "CANONICAL_NORMALIZED_OWNER_CASH_AFTER_TAX",
}
_ADJUSTMENT_CATEGORIES = {
    "NON_RECURRING_INCOME", "NON_RECURRING_EXPENSE",
    "ACCOUNTING_DISTORTION", "NON_OPERATING_INCOME", "OTHER_NORMALIZATION",
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


def _unknown_fields(
    value: dict[str, Any], allowed: set[str], prefix: str, findings: list[str]
) -> None:
    findings.extend(prefix + ":unknown_field:" + key for key in sorted(set(value) - allowed))


def _source_ids(value: Any, prefix: str, findings: list[str]) -> None:
    if (
        not isinstance(value, list) or not value
        or not all(_text(item) for item in value)
    ):
        findings.append(prefix + ":source_fact_ids_invalid")


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _validate_range(
    value: Any,
    prefix: str,
    findings: list[str],
    *,
    nonnegative: bool = True,
) -> tuple[float, float] | None:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(prefix + ":invalid")
        return None
    _unknown_fields(item, _RANGE_FIELDS, prefix, findings)
    low, high = _number(item.get("range_low")), _number(item.get("range_high"))
    if low is None or high is None or low > high or (nonnegative and low < 0):
        findings.append(prefix + ":range_invalid")
        return None
    _source_ids(item.get("source_fact_ids"), prefix, findings)
    return low, high


def _validate_cost(
    value: Any,
    prefix: str,
    findings: list[str],
    *,
    expected_tax_basis: str,
) -> tuple[float, float] | None:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(prefix + ":invalid")
        return None
    _unknown_fields(item, _COST_FIELDS, prefix, findings)
    status = item.get("status")
    if status not in {"BOUNDED", "UNKNOWN", "ALREADY_REFLECTED"}:
        findings.append(prefix + ":status_invalid")
        return None
    if status == "BOUNDED":
        low, high = _number(item.get("range_low")), _number(item.get("range_high"))
        if low is None or high is None or low < 0 or low > high:
            findings.append(prefix + ":range_invalid")
            return None
        if item.get("tax_basis") != expected_tax_basis:
            findings.append(prefix + ":tax_basis_mismatch")
        _source_ids(item.get("source_fact_ids"), prefix, findings)
        if _text(item.get("reason")):
            findings.append(prefix + ":bounded_reason_forbidden")
        return low, high
    if any(item.get(field) is not None for field in ("range_low", "range_high", "tax_basis")):
        findings.append(prefix + ":nonbounded_numeric_operand_forbidden")
    if status == "UNKNOWN":
        if not _text(item.get("reason")):
            findings.append(prefix + ":unknown_reason_missing")
        if item.get("source_fact_ids") is not None:
            _source_ids(item.get("source_fact_ids"), prefix, findings)
    elif not _text(item.get("reason")):
        findings.append(prefix + ":already_reflected_reason_missing")
    if status == "ALREADY_REFLECTED":
        _source_ids(item.get("source_fact_ids"), prefix, findings)
    return None


def validate_epv_model_input(payload: Any) -> dict[str, Any]:
    value = _mapping(payload)
    findings: list[str] = []
    if not isinstance(payload, dict):
        findings.append("input_not_object")
    _unknown_fields(value, _TOP_FIELDS, "$", findings)
    if value.get("schema_version") != INPUT_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in ("model_id", "company_id", "cutoff_at"):
        if not _text(value.get(field)):
            findings.append(field + "_missing")

    cutoff = _date(value.get("cutoff_at"))
    basis = _mapping(value.get("basis"))
    if not isinstance(value.get("basis"), dict):
        findings.append("basis_invalid")
    _unknown_fields(basis, _BASIS_FIELDS, "basis", findings)
    for field in (
        "value_scope", "earnings_claim_scope", "economic_entity",
        "operating_perimeter", "ordinary_share_claim_scope", "currency", "unit",
        "as_of", "operating_cash_treatment",
    ):
        if not _text(basis.get(field)):
            findings.append("basis:" + field + "_missing")
    if basis.get("value_scope") not in {"enterprise", "equity"}:
        findings.append("basis:value_scope_invalid")
    expected_claim_scope = {
        "enterprise": "ENTERPRISE_OPERATING",
        "equity": "ORDINARY_COMMON_EQUITY",
    }.get(basis.get("value_scope"))
    if expected_claim_scope and basis.get("earnings_claim_scope") != expected_claim_scope:
        findings.append("basis:earnings_claim_scope_mismatch")
    if basis.get("operating_cash_treatment") != (
        "REQUIRED_OPERATING_CASH_INCLUDED_NON_OPERATING_CASH_EXCLUDED"
    ):
        findings.append("basis:operating_cash_treatment_invalid")
    operating_cash_ids = basis.get("operating_cash_component_ids")
    if not isinstance(operating_cash_ids, list) or not all(_text(x) for x in operating_cash_ids):
        findings.append("basis:operating_cash_component_ids_invalid")
        operating_cash_ids = []
    elif len(set(operating_cash_ids)) != len(operating_cash_ids):
        findings.append("basis:operating_cash_component_ids_duplicate")
    as_of = _date(basis.get("as_of"))
    if cutoff is None:
        findings.append("cutoff_at_invalid")
    if as_of is None:
        findings.append("basis:as_of_invalid")
    elif cutoff is not None and as_of > cutoff:
        findings.append("basis:as_of_after_cutoff")

    earnings_status = value.get("earnings_evidence_status")
    if earnings_status not in {"AVAILABLE", "UNKNOWN"}:
        findings.append("earnings_evidence_status_invalid")
    periods = value.get("period_facts")
    if not isinstance(periods, list):
        findings.append("period_facts_invalid")
        periods = []
    if earnings_status == "AVAILABLE" and not periods:
        findings.append("period_facts_missing")
    if earnings_status == "UNKNOWN":
        if periods:
            findings.append("period_facts_forbidden_when_earnings_unknown")
        if not _text(value.get("earnings_unknown_reason")):
            findings.append("earnings_unknown_reason_missing")
    elif value.get("earnings_unknown_reason") is not None:
        findings.append("earnings_unknown_reason_forbidden_when_available")
    seen_periods: set[str] = set()
    basis_kinds: set[str] = set()
    tax_bases: set[str] = set()
    wc_applications: set[str] = set()
    for index, raw_period in enumerate(periods):
        prefix = f"period_facts[{index}]"
        period = _mapping(raw_period)
        if not isinstance(raw_period, dict):
            findings.append(prefix + ":invalid")
            continue
        _unknown_fields(period, _PERIOD_FIELDS, prefix, findings)
        period_id = str(period.get("period_id") or "")
        if not period_id:
            findings.append(prefix + ":period_id_missing")
        elif period_id in seen_periods:
            findings.append(prefix + ":period_id_duplicate")
        seen_periods.add(period_id)
        start, end = _date(period.get("period_start")), _date(period.get("period_end"))
        if start is None or end is None or start > end:
            findings.append(prefix + ":period_range_invalid")
        elif cutoff is not None and end > cutoff:
            findings.append(prefix + ":period_end_after_cutoff")
        if not _text(period.get("metric")):
            findings.append(prefix + ":metric_missing")
        kind = str(period.get("basis_kind") or "")
        if kind not in _BASIS_KINDS:
            findings.append(prefix + ":basis_kind_invalid")
        else:
            basis_kinds.add(kind)
        expected_tax = "PRETAX" if kind.endswith("PRETAX") else "AFTER_TAX"
        tax_basis = str(period.get("tax_basis") or "")
        if tax_basis != expected_tax:
            findings.append(prefix + ":tax_basis_kind_mismatch")
        if tax_basis:
            tax_bases.add(tax_basis)
        if kind == "CANONICAL_NORMALIZED_OWNER_CASH_AFTER_TAX":
            amount_range = _mapping(period.get("amount_range"))
            _unknown_fields(
                amount_range,
                _PERIOD_RANGE_FIELDS,
                prefix + ".amount_range",
                findings,
            )
            amount_low = _number(amount_range.get("range_low"))
            amount_high = _number(amount_range.get("range_high"))
            if amount_low is None or amount_high is None or amount_low > amount_high:
                findings.append(prefix + ":amount_range_invalid")
            if period.get("amount") is not None:
                findings.append(prefix + ":canonical_scalar_amount_forbidden")
        else:
            amount = _number(period.get("amount"))
            if amount is None:
                findings.append(prefix + ":amount_invalid")
            if period.get("amount_range") is not None:
                findings.append(prefix + ":amount_range_only_for_canonical_owner_cash")
        _source_ids(period.get("source_fact_ids"), prefix, findings)
        wc_application = str(period.get("working_capital_application") or "")
        allowed_application = {
            "REPORTED_OCF_AFTER_TAX": "CURRENT_MOVEMENT_REFLECTED",
            "CANONICAL_NORMALIZED_OWNER_CASH_AFTER_TAX": "ALREADY_NORMALIZED",
            "PRE_MAINTENANCE_OWNER_EARNINGS_PRETAX": "NOT_REFLECTED",
            "PRE_MAINTENANCE_OWNER_EARNINGS_AFTER_TAX": "NOT_REFLECTED",
        }.get(kind)
        if wc_application != allowed_application:
            findings.append(prefix + ":working_capital_application_basis_mismatch")
        if wc_application:
            wc_applications.add(wc_application)
        observed_wc = _number(period.get("observed_working_capital_charge"))
        if wc_application == "CURRENT_MOVEMENT_REFLECTED":
            if observed_wc is None:
                findings.append(prefix + ":observed_working_capital_charge_missing")
        elif period.get("observed_working_capital_charge") is not None:
            findings.append(prefix + ":observed_working_capital_charge_double_count")

        adjustments = period.get("normalization_adjustments")
        if not isinstance(adjustments, list):
            findings.append(prefix + ":normalization_adjustments_invalid")
            adjustments = []
        if kind == "CANONICAL_NORMALIZED_OWNER_CASH_AFTER_TAX" and adjustments:
            findings.append(prefix + ":canonical_owner_cash_adjustments_forbidden")
        adjustment_ids: set[str] = set()
        for adjustment_index, raw_adjustment in enumerate(adjustments):
            aprefix = prefix + f".normalization_adjustments[{adjustment_index}]"
            adjustment = _mapping(raw_adjustment)
            if not isinstance(raw_adjustment, dict):
                findings.append(aprefix + ":invalid")
                continue
            _unknown_fields(adjustment, _ADJUSTMENT_FIELDS, aprefix, findings)
            adjustment_id = str(adjustment.get("adjustment_id") or "")
            if not adjustment_id:
                findings.append(aprefix + ":adjustment_id_missing")
            elif adjustment_id in adjustment_ids:
                findings.append(aprefix + ":adjustment_id_duplicate")
            adjustment_ids.add(adjustment_id)
            if adjustment.get("category") not in _ADJUSTMENT_CATEGORIES:
                findings.append(aprefix + ":category_invalid")
            if adjustment.get("direction") not in {"ADD", "SUBTRACT"}:
                findings.append(aprefix + ":direction_invalid")
            expected_direction = {
                "NON_RECURRING_EXPENSE": "ADD",
                "NON_RECURRING_INCOME": "SUBTRACT",
                "NON_OPERATING_INCOME": "SUBTRACT",
            }.get(adjustment.get("category"))
            if expected_direction and adjustment.get("direction") != expected_direction:
                findings.append(aprefix + ":category_direction_mismatch")
            adjustment_amount = _number(adjustment.get("amount"))
            if adjustment_amount is None or adjustment_amount < 0:
                findings.append(aprefix + ":amount_must_be_nonnegative")
            if adjustment.get("tax_basis") != tax_basis:
                findings.append(aprefix + ":tax_basis_mismatch")
            if not _text(adjustment.get("economic_reason")):
                findings.append(aprefix + ":economic_reason_missing")
            _source_ids(adjustment.get("source_fact_ids"), aprefix, findings)

    if len(basis_kinds) > 1:
        findings.append("period_facts:basis_kind_mixed")
    if len(tax_bases) > 1:
        findings.append("period_facts:tax_basis_mixed")
    if len(wc_applications) > 1:
        findings.append("period_facts:working_capital_application_mixed")
    period_tax_basis = next(iter(tax_bases), "")
    # Maintenance capex and working capital are owner-cash outflows.  They do
    # not receive a second tax shield inside EPV: pretax operating earnings are
    # taxed first, then these cash investments are deducted.
    capex = _validate_cost(
        value.get("maintenance_capex"), "maintenance_capex", findings,
        expected_tax_basis="AFTER_TAX",
    )
    working_capital = _validate_cost(
        value.get("maintenance_working_capital"),
        "maintenance_working_capital", findings,
        expected_tax_basis="AFTER_TAX",
    )
    capex_status = _mapping(value.get("maintenance_capex")).get("status")
    wc_status = _mapping(value.get("maintenance_working_capital")).get("status")
    wc_application = next(iter(wc_applications), "")
    if wc_application == "ALREADY_NORMALIZED":
        if wc_status != "ALREADY_REFLECTED":
            findings.append("maintenance_working_capital:canonical_basis_requires_already_reflected")
    elif wc_status == "ALREADY_REFLECTED":
        findings.append("maintenance_working_capital:already_reflected_without_normalized_basis")
    if capex_status == "ALREADY_REFLECTED" and not all(
        kind == "CANONICAL_NORMALIZED_OWNER_CASH_AFTER_TAX" for kind in basis_kinds
    ):
        findings.append("maintenance_capex:already_reflected_without_owner_cash_basis")
    if wc_application == "CURRENT_MOVEMENT_REFLECTED" and working_capital is None and wc_status != "UNKNOWN":
        findings.append("maintenance_working_capital:ocf_replacement_range_missing")
    if wc_application == "CURRENT_MOVEMENT_REFLECTED" and wc_status == "BOUNDED":
        # The model adds back each observed movement once and then deducts the
        # bounded maintenance charge.  No separate WC adjustment category is
        # permitted because that would apply the same cash absorption twice.
        for index, period in enumerate(periods):
            for adjustment in _items(_mapping(period).get("normalization_adjustments")):
                if _mapping(adjustment).get("category") == "ACCOUNTING_DISTORTION" and "working capital" in str(_mapping(adjustment).get("economic_reason") or "").lower():
                    findings.append(f"period_facts[{index}]:working_capital_double_count_adjustment")

    tax = _mapping(value.get("tax"))
    if not isinstance(value.get("tax"), dict):
        findings.append("tax_invalid")
    _unknown_fields(tax, _TAX_FIELDS, "tax", findings)
    if period_tax_basis == "PRETAX":
        if tax.get("status") == "BOUNDED":
            low, high = _number(tax.get("rate_low")), _number(tax.get("rate_high"))
            if low is None or high is None or not (0 <= low <= high < 1):
                findings.append("tax:rate_range_invalid")
            _source_ids(tax.get("source_fact_ids"), "tax", findings)
        elif tax.get("status") == "UNKNOWN":
            if tax.get("rate_low") is not None or tax.get("rate_high") is not None:
                findings.append("tax:unknown_numeric_operand_forbidden")
            if not _text(tax.get("reason")):
                findings.append("tax:unknown_reason_missing")
        else:
            findings.append("tax:pretax_basis_requires_bounded_or_unknown_tax")
    elif period_tax_basis == "AFTER_TAX":
        if tax.get("status") != "ALREADY_REFLECTED":
            findings.append("tax:after_tax_basis_requires_already_reflected")
        if tax.get("rate_low") is not None or tax.get("rate_high") is not None:
            findings.append("tax:after_tax_rate_would_apply_tax_twice")
        if not _text(tax.get("reason")):
            findings.append("tax:already_reflected_reason_missing")
    elif tax.get("status") != "UNKNOWN":
        findings.append("tax:unknown_earnings_basis_requires_unknown_tax")
    elif not _text(tax.get("reason")):
        findings.append("tax:unknown_reason_missing")

    capitalization = _mapping(value.get("capitalization"))
    if not isinstance(value.get("capitalization"), dict):
        findings.append("capitalization_invalid")
    _unknown_fields(capitalization, _CAP_FIELDS, "capitalization", findings)
    if capitalization.get("status") not in {"BOUNDED", "UNKNOWN"}:
        findings.append("capitalization:status_invalid")
    elif capitalization.get("status") == "BOUNDED":
        low = _number(capitalization.get("rate_low"))
        high = _number(capitalization.get("rate_high"))
        if low is None or high is None or not (0 < low <= high < 1):
            findings.append("capitalization:rate_range_invalid")
        _source_ids(capitalization.get("source_fact_ids"), "capitalization", findings)
    else:
        if capitalization.get("rate_low") is not None or capitalization.get("rate_high") is not None:
            findings.append("capitalization:unknown_numeric_operand_forbidden")
        if not _text(capitalization.get("reason")):
            findings.append("capitalization:unknown_reason_missing")

    claims = _mapping(value.get("claims_bridge"))
    if not isinstance(value.get("claims_bridge"), dict):
        findings.append("claims_bridge_invalid")
    _unknown_fields(claims, _CLAIMS_FIELDS, "claims_bridge", findings)
    if claims.get("status") not in {"COMPLETE", "UNKNOWN"}:
        findings.append("claims_bridge:status_invalid")
    elif claims.get("status") == "UNKNOWN":
        if not _text(claims.get("reason")):
            findings.append("claims_bridge:unknown_reason_missing")
        for field in _CLAIMS_FIELDS - {"status", "reason"}:
            if claims.get(field) is not None:
                findings.append("claims_bridge:unknown_must_not_supply:" + field)
    else:
        expected_mode = {
            "enterprise": "ENTERPRISE_TO_ORDINARY_COMMON",
            "equity": "DIRECT_ORDINARY_COMMON",
        }.get(basis.get("value_scope"))
        if claims.get("bridge_mode") != expected_mode:
            findings.append("claims_bridge:bridge_mode_scope_mismatch")
        components = claims.get("non_operating_components")
        if not isinstance(components, list):
            findings.append("claims_bridge:non_operating_components_invalid")
            components = []
        component_ids: set[str] = set()
        nonoperating_cash_ids: set[str] = set()
        for index, raw_component in enumerate(components):
            prefix = f"claims_bridge.non_operating_components[{index}]"
            component = _mapping(raw_component)
            if not isinstance(raw_component, dict):
                findings.append(prefix + ":invalid")
                continue
            _unknown_fields(component, _COMPONENT_FIELDS, prefix, findings)
            component_id = str(component.get("component_id") or "")
            if not component_id:
                findings.append(prefix + ":component_id_missing")
            elif component_id in component_ids:
                findings.append(prefix + ":component_id_duplicate")
            component_ids.add(component_id)
            if component.get("kind") not in {"NON_OPERATING_CASH", "OTHER_NON_OPERATING_ASSET"}:
                findings.append(prefix + ":kind_invalid")
            if component.get("kind") == "NON_OPERATING_CASH":
                nonoperating_cash_ids.add(component_id)
                claim_ids = component.get("claim_ids")
                if not isinstance(claim_ids, list) or not claim_ids or not all(_text(x) for x in claim_ids):
                    findings.append(prefix + ":cash_claim_ids_invalid")
            elif component.get("claim_ids") not in (None, []):
                findings.append(prefix + ":noncash_claim_ids_forbidden")
            low, high = _number(component.get("range_low")), _number(component.get("range_high"))
            if low is None or high is None or low < 0 or low > high:
                findings.append(prefix + ":range_invalid")
            _source_ids(component.get("source_fact_ids"), prefix, findings)
        overlap = sorted(set(operating_cash_ids) & nonoperating_cash_ids)
        if overlap:
            findings.append("claims_bridge:operating_nonoperating_cash_double_count:" + ",".join(overlap))
        if basis.get("value_scope") == "enterprise":
            for field in ("debt", "preferred_claims", "minority_interest"):
                _validate_range(claims.get(field), "claims_bridge." + field, findings)
        else:
            for field in ("debt", "preferred_claims", "minority_interest"):
                if claims.get(field) is not None:
                    findings.append("claims_bridge:direct_equity_priority_bridge_forbidden:" + field)
        _validate_range(
            claims.get("other_adjustments"), "claims_bridge.other_adjustments",
            findings, nonnegative=False,
        )
        shares = _mapping(claims.get("shares"))
        if not isinstance(claims.get("shares"), dict):
            findings.append("claims_bridge.shares:invalid")
        _unknown_fields(shares, _SHARES_FIELDS, "claims_bridge.shares", findings)
        if (_number(shares.get("value")) or 0) <= 0:
            findings.append("claims_bridge.shares:value_invalid")
        _source_ids(shares.get("source_fact_ids"), "claims_bridge.shares", findings)

    findings = list(dict.fromkeys(findings))
    return {
        "schema_version": "epv-model-input-validation.v1",
        "state": "VALID" if not findings else "INVALID",
        "findings": findings,
    }


def _signed_adjustment(adjustment: dict[str, Any]) -> float:
    amount = float(adjustment["amount"])
    return amount if adjustment["direction"] == "ADD" else -amount


def _unknowns(value: dict[str, Any]) -> list[str]:
    unknown: list[str] = []
    if value.get("earnings_evidence_status") == "UNKNOWN":
        unknown.append("maintenance_owner_earnings")
    for field in ("maintenance_capex", "maintenance_working_capital"):
        if _mapping(value.get(field)).get("status") == "UNKNOWN":
            unknown.append(field)
    if _mapping(value.get("capitalization")).get("status") == "UNKNOWN":
        unknown.append("capitalization_rate")
    if _mapping(value.get("tax")).get("status") == "UNKNOWN":
        unknown.append("tax")
    if _mapping(value.get("claims_bridge")).get("status") == "UNKNOWN":
        unknown.append("claims_bridge")
    return unknown


def compute_epv_model(payload: Any) -> dict[str, Any]:
    validation = validate_epv_model_input(payload)
    if validation["state"] != "VALID":
        raise ValueError("epv_model_input_invalid:" + ",".join(validation["findings"]))
    value = _mapping(payload)
    basis = _mapping(value["basis"])
    period_results: list[dict[str, Any]] = []
    adjusted_period_lows: list[float] = []
    adjusted_period_highs: list[float] = []
    wc_application = ""
    for period in value["period_facts"]:
        adjustments = deepcopy(period["normalization_adjustments"])
        additions = sum(
            float(item["amount"]) for item in adjustments if item["direction"] == "ADD"
        )
        subtractions = sum(
            float(item["amount"]) for item in adjustments if item["direction"] == "SUBTRACT"
        )
        observed_wc = float(period.get("observed_working_capital_charge") or 0.0)
        wc_application = period["working_capital_application"]
        wc_addback = observed_wc if wc_application == "CURRENT_MOVEMENT_REFLECTED" else 0.0
        if period["basis_kind"] == "CANONICAL_NORMALIZED_OWNER_CASH_AFTER_TAX":
            amount_range = _mapping(period["amount_range"])
            adjusted_low = float(amount_range["range_low"])
            adjusted_high = float(amount_range["range_high"])
            period_result = {
                "period_id": period["period_id"],
                "reported_amount_range": deepcopy(amount_range),
                "adjustments": [],
                "adjustment_additions": 0.0,
                "adjustment_subtractions": 0.0,
                "observed_working_capital_charge_addback": 0.0,
                "pre_maintenance_normalized_range": deepcopy(amount_range),
            }
        else:
            adjusted = float(period["amount"]) + additions - subtractions + wc_addback
            adjusted_low = adjusted
            adjusted_high = adjusted
            period_result = {
                "period_id": period["period_id"],
                "reported_amount": period["amount"],
                "adjustments": adjustments,
                "adjustment_additions": additions,
                "adjustment_subtractions": subtractions,
                "observed_working_capital_charge_addback": wc_addback,
                "pre_maintenance_normalized_amount": adjusted,
            }
        adjusted_period_lows.append(adjusted_low)
        adjusted_period_highs.append(adjusted_high)
        period_results.append(period_result)

    historical_low = min(adjusted_period_lows) if adjusted_period_lows else None
    historical_high = max(adjusted_period_highs) if adjusted_period_highs else None
    capex = _mapping(value["maintenance_capex"])
    wc = _mapping(value["maintenance_working_capital"])
    capex_range = (
        (float(capex["range_low"]), float(capex["range_high"]))
        if capex["status"] == "BOUNDED" else (0.0, 0.0)
    )
    wc_range = (
        (float(wc["range_low"]), float(wc["range_high"]))
        if wc["status"] == "BOUNDED" else (0.0, 0.0)
    )
    unknown = _unknowns(value)
    tax = _mapping(value["tax"])
    if tax["status"] == "BOUNDED":
        after_tax_earnings_low = (
            historical_low * (1.0 - float(tax["rate_high"]))
            if historical_low is not None else 0.0
        )
        after_tax_earnings_high = (
            historical_high * (1.0 - float(tax["rate_low"]))
            if historical_high is not None else 0.0
        )
    else:
        after_tax_earnings_low = historical_low if historical_low is not None else 0.0
        after_tax_earnings_high = historical_high if historical_high is not None else 0.0
    owner_low = after_tax_earnings_low - capex_range[1] - wc_range[1]
    owner_high = after_tax_earnings_high - capex_range[0] - wc_range[0]
    if owner_low > owner_high:
        owner_low, owner_high = owner_high, owner_low

    capitalization = _mapping(value["capitalization"])
    claims = _mapping(value["claims_bridge"])
    comparable = not unknown
    capitalizable_owner_low = max(0.0, owner_low)
    capitalizable_owner_high = max(0.0, owner_high)

    operating_range: dict[str, float] | None = None
    equity_range: dict[str, float] | None = None
    per_share_range: dict[str, float] | None = None
    equity_bridge: dict[str, Any] | None = None
    if comparable:
        operating_low = capitalizable_owner_low / float(capitalization["rate_high"])
        operating_high = capitalizable_owner_high / float(capitalization["rate_low"])
        operating_range = {"range_low": operating_low, "range_high": operating_high}
        nonop_low = sum(float(item["range_low"]) for item in claims["non_operating_components"])
        nonop_high = sum(float(item["range_high"]) for item in claims["non_operating_components"])
        other = _mapping(claims["other_adjustments"])
        if basis["value_scope"] == "enterprise":
            debt = _mapping(claims["debt"])
            preferred = _mapping(claims["preferred_claims"])
            minority = _mapping(claims["minority_interest"])
            equity_low = (
                operating_low + nonop_low - float(debt["range_high"])
                - float(preferred["range_high"]) - float(minority["range_high"])
                + float(other["range_low"])
            )
            equity_high = (
                operating_high + nonop_high - float(debt["range_low"])
                - float(preferred["range_low"]) - float(minority["range_low"])
                + float(other["range_high"])
            )
        else:
            equity_low = operating_low + nonop_low + float(other["range_low"])
            equity_high = operating_high + nonop_high + float(other["range_high"])
        shares = float(_mapping(claims["shares"])["value"])
        equity_low = max(0.0, equity_low)
        equity_high = max(0.0, equity_high)
        equity_range = {"range_low": equity_low, "range_high": equity_high}
        per_share_range = {
            "range_low": equity_low / shares,
            "range_high": equity_high / shares,
        }
        equity_bridge = {
            "bridge_mode": claims["bridge_mode"],
            "operating_value_range": deepcopy(operating_range),
            "non_operating_components": deepcopy(claims["non_operating_components"]),
            "debt": deepcopy(claims.get("debt")),
            "preferred_claims": deepcopy(claims.get("preferred_claims")),
            "minority_interest": deepcopy(claims.get("minority_interest")),
            "other_adjustments": deepcopy(claims["other_adjustments"]),
            "ordinary_common_equity_range": deepcopy(equity_range),
            "shares": shares,
            "per_share_range": deepcopy(per_share_range),
        }

    status = "COMPARABLE" if comparable else "NOT_COMPARABLE"
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "model_id": value["model_id"],
        "company_id": value["company_id"],
        "cutoff_at": value["cutoff_at"],
        "basis": deepcopy(basis),
        "status": status,
        "normalization_bridge": {
            "period_results": period_results,
            "historical_pre_maintenance_range": {
                "range_low": historical_low,
                "range_high": historical_high,
            } if historical_low is not None else None,
            "maintenance_capex": deepcopy(capex),
            "working_capital_application": wc_application,
            "maintenance_working_capital": deepcopy(wc),
            "after_tax_earnings_before_maintenance_range": {
                "range_low": after_tax_earnings_low,
                "range_high": after_tax_earnings_high,
            } if historical_low is not None else None,
            "tax": deepcopy(tax),
        },
        "sustainable_owner_earnings_range": (
            {
                "range_low": capitalizable_owner_low,
                "range_high": capitalizable_owner_high,
            }
            if comparable else None
        ),
        "capitalization": deepcopy(capitalization),
        "operating_value_range": operating_range,
        "equity_bridge": equity_bridge,
        "ordinary_common_equity_range": equity_range,
        "per_share_range": per_share_range,
        "critical_unknowns": unknown,
        "economic_conclusion": {
            "epv_status": status,
            "reason": (
                (
                    "Source-bounded maintenance earnings do not establish positive EPV."
                    if comparable and capitalizable_owner_high == 0
                    else "All material operands are source-bounded and deterministically recomputed."
                )
                if comparable
                else "Company-level EPV remains unavailable until: " + ", ".join(unknown) + "."
            ),
            "synthesis_rule": SYNTHESIS_RULE,
        },
    }


def validate_epv_model(value: Any) -> dict[str, Any]:
    observed = _mapping(value)
    findings: list[str] = []
    if not isinstance(value, dict):
        findings.append("output_not_object")
    model_input = observed.get("model_input")
    if not isinstance(model_input, dict):
        findings.append("model_input_missing")
    else:
        validation = validate_epv_model_input(model_input)
        if validation["state"] != "VALID":
            findings.extend("model_input:" + item for item in validation["findings"])
        else:
            expected = compute_epv_model(model_input)
            if observed.get("result") != expected:
                findings.append("result_not_deterministic_projection")
    allowed = {"schema_version", "model_input", "result"}
    _unknown_fields(observed, allowed, "$", findings)
    if observed.get("schema_version") != "epv-model-envelope.v1":
        findings.append("schema_version_invalid")
    findings = list(dict.fromkeys(findings))
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "VALID" if not findings else "INVALID",
        "findings": findings,
    }


def compile_epv_model(payload: Any) -> dict[str, Any]:
    result = compute_epv_model(payload)
    return {
        "schema_version": "epv-model-envelope.v1",
        "model_input": deepcopy(payload),
        "result": result,
    }


__all__ = [
    "compile_epv_model", "compute_epv_model", "validate_epv_model",
    "validate_epv_model_input",
]
