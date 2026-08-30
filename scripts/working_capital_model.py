#!/usr/bin/env python3
"""Deterministic stock-flow bridge for working capital and owner cash.

The model separates a period's observed cash-capital movement from the charge
that belongs in normal owner cash.  It deliberately keeps growth launches,
steady rolling capital, runoff/settlement, permanent losses and non-cash scope
changes as different economic identities.

Two starting points are supported:

* ``REPORTED_OCF`` already contains the period's working-capital cash movement.
* ``ACCRUAL_EARNINGS`` does not, so the reconciled movement must be deducted.

In either case normalized owner cash is obtained by replacing the actual
period charge with the bounded steady-state charge.  A period may provide
either full cohort gross flows or only an observed net movement.  Net-only
disclosure closes the observed period cash-capital identity, but it never
manufactures growth, steady-state or runoff attribution.  Unknown attribution
stays unknown; the model never invents a midpoint.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import math
from typing import Any


SCHEMA_VERSION = "working-capital-model.v1"
VALIDATION_SCHEMA_VERSION = "working-capital-model-validation.v1"
RESULT_SCHEMA_VERSION = "working-capital-model-result.v1"

OWNER_CASH_BASES = {"REPORTED_OCF", "ACCRUAL_EARNINGS"}
DISCLOSURE_MODES = {"FULL_GROSS_FLOW", "NET_MOVEMENT_ONLY"}
WORKING_CAPITAL_APPLICATIONS = {
    "ALREADY_REFLECTED_IN_BASE",
    "DEDUCT_STOCK_FLOW_CHARGE",
}
PERMANENT_LOSS_APPLICATIONS = {
    "INCLUDED_IN_STOCK_FLOW_CHARGE",
    "DEDUCT_AGAIN",
}
COHORT_ROLES = {
    "GROWTH_LAUNCH",
    "STEADY_ROLLING",
    "RUNOFF_OR_SETTLEMENT",
    "UNATTRIBUTED",
}
LOSS_TREATMENTS = {
    "RECURRING_EXPECTED",
    "ONE_OFF_PERMANENT",
    "NO_LOSS",
    "UNKNOWN",
}
NORMALIZATION_METHODS = {
    "NOT_APPLICABLE",
    "OBSERVED_STEADY_CHARGE",
    "EVIDENCE_BOUNDED",
    "UNKNOWN",
}
ADOPTED_ENDPOINTS = {"LOW", "HIGH", "EXACT", "UNKNOWN"}
EPV_USES = {"NORMALIZED_OWNER_CASH", "NOT_USED"}
EPV_WORKING_CAPITAL_TREATMENTS = {"STEADY_RECURRING_ONLY", "NOT_APPLICABLE"}
TERMINAL_ROUTES = {"CONTINUING", "RUNOFF_OR_LIQUIDATION", "NOT_USED"}
TERMINAL_OWNER_CASH_SOURCES = {
    "NORMALIZED_OWNER_CASH",
    "STOCK_RELEASE_ONLY",
    "NOT_APPLICABLE",
}
TERMINAL_WORKING_CAPITAL_TREATMENTS = {
    "STEADY_RECURRING_AND_TERMINAL_GROWTH_ONLY",
    "STOCK_RELEASE_ONLY",
    "NOT_APPLICABLE",
}

_TOP_LEVEL_FIELDS = {
    "schema_version",
    "model_id",
    "company_id",
    "basis",
    "periods",
    "valuation_treatment",
}
_BASIS_FIELDS = {
    "economic_entity",
    "operating_perimeter",
    "ordinary_share_claim_scope",
    "currency",
    "unit",
    "as_of",
}
_PERIOD_FIELDS = {
    "period_id",
    "period_start",
    "period_end",
    "disclosure_mode",
    "owner_cash_input",
    "cohorts",
    "net_movement_observation",
}
_OWNER_CASH_FIELDS = {
    "basis",
    "metric",
    "base_metric_amount",
    "maintenance_capex",
    "other_owner_adjustments",
    "working_capital_application",
    "permanent_loss_application",
    "evidence_ids",
}
_COHORT_FIELDS = {
    "cohort_id",
    "role",
    "opening_net_stock",
    "growth_launch_additions",
    "steady_rollover_additions",
    "cash_collections_and_settlements",
    "permanent_losses",
    "noncash_scope_change",
    "closing_net_stock",
    "loss_treatment",
    "normalization",
    "evidence_ids",
}
_NET_MOVEMENT_FIELDS = {
    "opening_net_stock",
    "closing_net_stock",
    "observed_cash_capital_charge",
    "evidence_ids",
}
_NORMALIZATION_FIELDS = {
    "method",
    "recurring_charge_range",
    "bounded_observations",
    "adopted_endpoint",
    "adopted_value",
    "rationale",
    "evidence_ids",
}
_RANGE_FIELDS = {"range_low", "range_high"}
_BOUND_OBSERVATION_FIELDS = {
    "observation_id",
    "basis",
    "period_or_cohort",
    "amount",
    "evidence_ids",
}
BOUND_OBSERVATION_BASES = {
    "PROJECT_COHORT_CASH_CHARGE",
    "COMPARABLE_PERIOD_CASH_CHARGE",
    "CONTRACT_BATCH_CASH_CHARGE",
}
_VALUATION_FIELDS = {
    "reference_period_id",
    "epv_use",
    "epv_working_capital_treatment",
    "terminal_route",
    "terminal_owner_cash_source",
    "terminal_working_capital_treatment",
    "stock_release_cohort_ids",
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


def _clean(value: float) -> float:
    return 0.0 if math.isclose(value, 0.0, rel_tol=1e-12, abs_tol=1e-12) else value


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _reject_unknown_fields(
    value: dict[str, Any], allowed: set[str], prefix: str, findings: list[str]
) -> None:
    findings.extend(prefix + ":unknown_field:" + field for field in sorted(set(value) - allowed))


def _validate_text_list(value: Any, *, prefix: str, findings: list[str]) -> list[str]:
    items = _items(value)
    if not items or any(not _text(item) for item in items):
        findings.append(prefix + "_missing")
        return []
    normalized = [str(item) for item in items]
    if len(normalized) != len(set(normalized)):
        findings.append(prefix + "_duplicate")
    return normalized


def _validate_range(
    value: Any, *, prefix: str, findings: list[str]
) -> tuple[float, float] | None:
    item = _mapping(value)
    _reject_unknown_fields(item, _RANGE_FIELDS, prefix, findings)
    low = _number(item.get("range_low"))
    high = _number(item.get("range_high"))
    if low is None or high is None or low > high:
        findings.append(prefix + ":range_invalid")
        return None
    return low, high


def _cohort_actual_charge(cohort: dict[str, Any]) -> float:
    return _clean(
        float(cohort["growth_launch_additions"])
        + float(cohort["steady_rollover_additions"])
        - float(cohort["cash_collections_and_settlements"])
    )


def _cohort_delta_stock(cohort: dict[str, Any]) -> float:
    return _clean(float(cohort["closing_net_stock"]) - float(cohort["opening_net_stock"]))


def _derived_observed_recurring_charge(cohort: dict[str, Any]) -> float:
    charge = _cohort_actual_charge(cohort)
    if cohort["loss_treatment"] == "ONE_OFF_PERMANENT":
        charge -= float(cohort["permanent_losses"])
    return _clean(charge)


def _bounded_observation_values(normalization: dict[str, Any]) -> list[float]:
    return [
        float(item["amount"])
        for item in _items(normalization.get("bounded_observations"))
    ]


def _validate_normalization(
    value: Any,
    *,
    prefix: str,
    role: str,
    loss_treatment: str,
    permanent_losses: float | None,
    cohort: dict[str, Any],
    findings: list[str],
) -> tuple[float, float, float] | None:
    normalization = _mapping(value)
    _reject_unknown_fields(normalization, _NORMALIZATION_FIELDS, prefix, findings)
    method = str(normalization.get("method") or "")
    endpoint = str(normalization.get("adopted_endpoint") or "")
    adopted = _number(normalization.get("adopted_value"))
    if method not in NORMALIZATION_METHODS:
        findings.append(prefix + ":method_invalid")
        return None
    if endpoint not in ADOPTED_ENDPOINTS:
        findings.append(prefix + ":adopted_endpoint_invalid")
    if not _text(normalization.get("rationale")):
        findings.append(prefix + ":rationale_missing")
    normalization_evidence = _validate_text_list(
        normalization.get("evidence_ids"), prefix=prefix + ":evidence_ids", findings=findings
    )

    supplied_range = normalization.get("recurring_charge_range")
    bounded_observations = normalization.get("bounded_observations")
    if role in {"GROWTH_LAUNCH", "RUNOFF_OR_SETTLEMENT"}:
        if method != "NOT_APPLICABLE":
            findings.append(prefix + ":nonsteady_cohort_cannot_enter_recurring_charge")
        if supplied_range is not None:
            findings.append(prefix + ":nonsteady_recurring_range_forbidden")
        if endpoint != "EXACT" or adopted is None or not _same(adopted, 0.0):
            findings.append(prefix + ":nonsteady_adopted_charge_must_be_zero")
        return 0.0, 0.0, 0.0

    if role == "STEADY_ROLLING" and method == "NOT_APPLICABLE":
        findings.append(prefix + ":steady_cohort_requires_recurring_treatment")
        return None
    if role == "UNATTRIBUTED" and method in {
        "NOT_APPLICABLE",
        "OBSERVED_STEADY_CHARGE",
    }:
        findings.append(prefix + ":unattributed_cohort_requires_range_or_unknown")
        return None
    if method == "UNKNOWN":
        if supplied_range is not None:
            findings.append(prefix + ":unknown_must_not_have_range")
        if bounded_observations is not None:
            findings.append(prefix + ":unknown_must_not_have_bounded_observations")
        if endpoint != "UNKNOWN" or normalization.get("adopted_value") is not None:
            findings.append(prefix + ":unknown_must_not_adopt_value")
        return None
    if method == "OBSERVED_STEADY_CHARGE":
        if role != "STEADY_ROLLING":
            findings.append(prefix + ":observed_steady_method_role_invalid")
            return None
        if supplied_range is not None:
            findings.append(prefix + ":observed_steady_range_must_be_derived")
        if bounded_observations is not None:
            findings.append(prefix + ":observed_steady_bounded_observations_forbidden")
        if loss_treatment == "UNKNOWN":
            findings.append(prefix + ":unknown_loss_cannot_be_normalized_as_observed")
            return None
        expected = _derived_observed_recurring_charge(cohort)
        if endpoint != "EXACT" or adopted is None or not _same(adopted, expected):
            findings.append(prefix + ":observed_steady_adopted_value_mismatch")
        return expected, expected, expected
    if method == "EVIDENCE_BOUNDED":
        if supplied_range is not None:
            findings.append(prefix + ":manual_recurring_charge_range_forbidden")
        if normalization.get("adopted_value") is not None:
            findings.append(prefix + ":manual_adopted_value_forbidden")
        observations = _items(bounded_observations)
        if len(observations) < 2:
            findings.append(prefix + ":bounded_observations_require_two_or_more")
            return None
        observation_ids: set[str] = set()
        observation_scopes: set[str] = set()
        observation_evidence: set[str] = set()
        amounts: list[float] = []
        for index, raw_observation in enumerate(observations):
            observation = _mapping(raw_observation)
            observation_prefix = f"{prefix}:bounded_observations[{index}]"
            _reject_unknown_fields(
                observation,
                _BOUND_OBSERVATION_FIELDS,
                observation_prefix,
                findings,
            )
            observation_id = str(observation.get("observation_id") or "")
            if not observation_id or observation_id in observation_ids:
                findings.append(observation_prefix + ":observation_id_missing_or_duplicate")
            else:
                observation_ids.add(observation_id)
            basis = str(observation.get("basis") or "")
            if basis not in BOUND_OBSERVATION_BASES:
                findings.append(observation_prefix + ":basis_invalid")
            scope = str(observation.get("period_or_cohort") or "")
            if not scope or scope in observation_scopes:
                findings.append(observation_prefix + ":period_or_cohort_missing_or_duplicate")
            else:
                observation_scopes.add(scope)
            amount = _number(observation.get("amount"))
            if amount is None:
                findings.append(observation_prefix + ":amount_invalid")
            else:
                amounts.append(amount)
            refs = _validate_text_list(
                observation.get("evidence_ids"),
                prefix=observation_prefix + ":evidence_ids",
                findings=findings,
            )
            observation_evidence.update(refs)
        if len(observation_evidence) < 2:
            findings.append(prefix + ":bounded_observations_require_distinct_evidence")
        if set(normalization_evidence) != observation_evidence:
            findings.append(prefix + ":evidence_ids_must_equal_bounded_observation_evidence")
        if len(amounts) != len(observations):
            return None
        low, high = min(amounts), max(amounts)
        if role == "UNATTRIBUTED":
            if endpoint == "EXACT":
                findings.append(prefix + ":unattributed_exact_endpoint_forbidden")
            if _same(low, high):
                findings.append(prefix + ":unattributed_degenerate_range_forbidden")
        if endpoint not in {"LOW", "HIGH"}:
            findings.append(prefix + ":bounded_range_requires_named_conservative_endpoint")
        if permanent_losses and loss_treatment == "UNKNOWN" and low == high:
            findings.append(prefix + ":unknown_loss_requires_range_or_unknown_not_point")
        return low, high, high if endpoint == "HIGH" else low
    if bounded_observations is not None:
        findings.append(prefix + ":bounded_observations_method_invalid")
    return None


def _validate_cohort(
    raw: Any,
    *,
    period_id: str,
    index: int,
    seen_ids: set[str],
    findings: list[str],
) -> tuple[str, tuple[float, float, float] | None]:
    cohort = _mapping(raw)
    prefix = f"{period_id}:cohorts[{index}]"
    _reject_unknown_fields(cohort, _COHORT_FIELDS, prefix, findings)
    cohort_id = str(cohort.get("cohort_id") or "")
    if not cohort_id or cohort_id in seen_ids:
        findings.append(prefix + ":cohort_id_missing_or_duplicate")
    else:
        seen_ids.add(cohort_id)
        prefix = period_id + ":" + cohort_id
    role = str(cohort.get("role") or "")
    if role not in COHORT_ROLES:
        findings.append(prefix + ":role_invalid")
    loss_treatment = str(cohort.get("loss_treatment") or "")
    if loss_treatment not in LOSS_TREATMENTS:
        findings.append(prefix + ":loss_treatment_invalid")

    numeric_fields = (
        "opening_net_stock",
        "growth_launch_additions",
        "steady_rollover_additions",
        "cash_collections_and_settlements",
        "permanent_losses",
        "noncash_scope_change",
        "closing_net_stock",
    )
    numbers = {field: _number(cohort.get(field)) for field in numeric_fields}
    for field, number in numbers.items():
        if number is None:
            findings.append(prefix + ":" + field + "_invalid")
        elif field != "noncash_scope_change" and number < 0:
            findings.append(prefix + ":" + field + "_negative")
    _validate_text_list(cohort.get("evidence_ids"), prefix=prefix + ":evidence_ids", findings=findings)
    if any(number is None for number in numbers.values()):
        return cohort_id, None

    expected_closing = _clean(
        float(numbers["opening_net_stock"])
        + float(numbers["growth_launch_additions"])
        + float(numbers["steady_rollover_additions"])
        - float(numbers["cash_collections_and_settlements"])
        - float(numbers["permanent_losses"])
        + float(numbers["noncash_scope_change"])
    )
    if not _same(numbers["closing_net_stock"], expected_closing):
        findings.append(prefix + ":stock_flow_identity_not_closed")
    actual_charge = _cohort_actual_charge(cohort)
    identity_charge = _clean(
        _cohort_delta_stock(cohort)
        + float(numbers["permanent_losses"])
        - float(numbers["noncash_scope_change"])
    )
    if not _same(actual_charge, identity_charge):
        findings.append(prefix + ":cash_capital_charge_identity_not_closed")
    if role == "GROWTH_LAUNCH" and float(numbers["steady_rollover_additions"]) != 0:
        findings.append(prefix + ":growth_role_contains_steady_addition")
    if role == "STEADY_ROLLING" and float(numbers["growth_launch_additions"]) != 0:
        findings.append(prefix + ":steady_role_contains_growth_addition")
    if role == "RUNOFF_OR_SETTLEMENT" and (
        float(numbers["growth_launch_additions"]) != 0
        or float(numbers["steady_rollover_additions"]) != 0
    ):
        findings.append(prefix + ":runoff_role_contains_new_addition")
    if float(numbers["permanent_losses"]) == 0 and loss_treatment != "NO_LOSS":
        findings.append(prefix + ":zero_loss_requires_no_loss_treatment")
    if float(numbers["permanent_losses"]) > 0 and loss_treatment == "NO_LOSS":
        findings.append(prefix + ":nonzero_loss_requires_loss_treatment")

    normalized = _validate_normalization(
        cohort.get("normalization"),
        prefix=prefix + ":normalization",
        role=role,
        loss_treatment=loss_treatment,
        permanent_losses=numbers["permanent_losses"],
        cohort=cohort,
        findings=findings,
    )
    return cohort_id, normalized


def _validate_owner_cash_input(
    value: Any, *, period_id: str, findings: list[str]
) -> str:
    item = _mapping(value)
    prefix = period_id + ":owner_cash_input"
    _reject_unknown_fields(item, _OWNER_CASH_FIELDS, prefix, findings)
    basis = str(item.get("basis") or "")
    if basis not in OWNER_CASH_BASES:
        findings.append(prefix + ":basis_invalid")
    if not _text(item.get("metric")):
        findings.append(prefix + ":metric_missing")
    for field in ("base_metric_amount", "maintenance_capex", "other_owner_adjustments"):
        number = _number(item.get(field))
        if number is None:
            findings.append(prefix + ":" + field + "_invalid")
        elif field != "base_metric_amount" and number < 0:
            findings.append(prefix + ":" + field + "_negative")
    _validate_text_list(item.get("evidence_ids"), prefix=prefix + ":evidence_ids", findings=findings)
    application = str(item.get("working_capital_application") or "")
    if application not in WORKING_CAPITAL_APPLICATIONS:
        findings.append(prefix + ":working_capital_application_invalid")
    elif basis == "REPORTED_OCF" and application != "ALREADY_REFLECTED_IN_BASE":
        findings.append(prefix + ":reported_ocf_working_capital_deducted_twice")
    elif basis == "ACCRUAL_EARNINGS" and application != "DEDUCT_STOCK_FLOW_CHARGE":
        findings.append(prefix + ":accrual_earnings_missing_stock_flow_charge")
    loss_application = str(item.get("permanent_loss_application") or "")
    if loss_application not in PERMANENT_LOSS_APPLICATIONS:
        findings.append(prefix + ":permanent_loss_application_invalid")
    elif loss_application != "INCLUDED_IN_STOCK_FLOW_CHARGE":
        findings.append(prefix + ":permanent_loss_deducted_twice")
    return basis


def _validate_net_movement_observation(
    value: Any, *, period_id: str, findings: list[str]
) -> tuple[float, float, float] | None:
    """Validate one aggregate movement without inventing its gross composition."""
    item = _mapping(value)
    prefix = period_id + ":net_movement_observation"
    _reject_unknown_fields(item, _NET_MOVEMENT_FIELDS, prefix, findings)
    opening = _number(item.get("opening_net_stock"))
    closing = _number(item.get("closing_net_stock"))
    observed_charge = _number(item.get("observed_cash_capital_charge"))
    for field, number in (
        ("opening_net_stock", opening),
        ("closing_net_stock", closing),
        ("observed_cash_capital_charge", observed_charge),
    ):
        if number is None:
            findings.append(prefix + ":" + field + "_invalid")
    _validate_text_list(
        item.get("evidence_ids"),
        prefix=prefix + ":evidence_ids",
        findings=findings,
    )
    if opening is None or closing is None or observed_charge is None:
        return None
    delta = _clean(closing - opening)
    if not _same(observed_charge, delta):
        findings.append(prefix + ":net_movement_identity_not_closed")
    return opening, closing, observed_charge


def _validate_valuation_treatment(
    value: Any,
    *,
    period_roles: dict[str, dict[str, str]],
    findings: list[str],
) -> None:
    item = _mapping(value)
    _reject_unknown_fields(item, _VALUATION_FIELDS, "valuation_treatment", findings)
    reference_id = str(item.get("reference_period_id") or "")
    if reference_id not in period_roles:
        findings.append("valuation_treatment:reference_period_id_invalid")
    epv_use = str(item.get("epv_use") or "")
    epv_wc = str(item.get("epv_working_capital_treatment") or "")
    terminal_route = str(item.get("terminal_route") or "")
    terminal_source = str(item.get("terminal_owner_cash_source") or "")
    terminal_wc = str(item.get("terminal_working_capital_treatment") or "")
    release_ids = _items(item.get("stock_release_cohort_ids"))
    if any(not _text(value) for value in release_ids) or len(release_ids) != len(set(release_ids)):
        findings.append("valuation_treatment:stock_release_cohort_ids_invalid")
    if epv_use not in EPV_USES:
        findings.append("valuation_treatment:epv_use_invalid")
    if epv_wc not in EPV_WORKING_CAPITAL_TREATMENTS:
        findings.append("valuation_treatment:epv_working_capital_treatment_invalid")
    if epv_use == "NORMALIZED_OWNER_CASH" and epv_wc != "STEADY_RECURRING_ONLY":
        findings.append("valuation_treatment:epv_must_use_steady_recurring_charge_only")
    if epv_use == "NOT_USED" and epv_wc != "NOT_APPLICABLE":
        findings.append("valuation_treatment:unused_epv_treatment_must_be_not_applicable")
    if terminal_route not in TERMINAL_ROUTES:
        findings.append("valuation_treatment:terminal_route_invalid")
    if terminal_source not in TERMINAL_OWNER_CASH_SOURCES:
        findings.append("valuation_treatment:terminal_owner_cash_source_invalid")
    if terminal_wc not in TERMINAL_WORKING_CAPITAL_TREATMENTS:
        findings.append("valuation_treatment:terminal_working_capital_treatment_invalid")

    if terminal_route == "CONTINUING":
        if terminal_source != "NORMALIZED_OWNER_CASH":
            findings.append("valuation_treatment:continuing_terminal_requires_normalized_owner_cash")
        if terminal_wc != "STEADY_RECURRING_AND_TERMINAL_GROWTH_ONLY":
            findings.append("valuation_treatment:continuing_terminal_cannot_perpetuate_current_absorption")
        if release_ids:
            findings.append("valuation_treatment:continuing_terminal_stock_release_forbidden")
    elif terminal_route == "RUNOFF_OR_LIQUIDATION":
        if epv_use != "NOT_USED":
            findings.append("valuation_treatment:runoff_and_continuing_epv_mutually_exclusive")
        if terminal_source != "STOCK_RELEASE_ONLY" or terminal_wc != "STOCK_RELEASE_ONLY":
            findings.append("valuation_treatment:runoff_terminal_requires_stock_release_only")
        if not release_ids:
            findings.append("valuation_treatment:runoff_stock_release_cohort_ids_missing")
        roles = period_roles.get(reference_id, {})
        for cohort_id in release_ids:
            if roles.get(str(cohort_id)) != "RUNOFF_OR_SETTLEMENT":
                findings.append(
                    "valuation_treatment:stock_release_cohort_not_runoff:" + str(cohort_id)
                )
    elif terminal_route == "NOT_USED":
        if terminal_source != "NOT_APPLICABLE" or terminal_wc != "NOT_APPLICABLE":
            findings.append("valuation_treatment:unused_terminal_treatment_must_be_not_applicable")
        if release_ids:
            findings.append("valuation_treatment:unused_terminal_stock_release_forbidden")


def validate_working_capital_model(payload: Any) -> dict[str, Any]:
    """Validate economic identities, scope and anti-double-count contracts."""
    findings: list[str] = []
    value = _mapping(payload)
    _reject_unknown_fields(value, _TOP_LEVEL_FIELDS, "model", findings)
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in ("model_id", "company_id"):
        if not _text(value.get(field)):
            findings.append(field + "_missing")

    basis = _mapping(value.get("basis"))
    _reject_unknown_fields(basis, _BASIS_FIELDS, "basis", findings)
    for field in (
        "economic_entity",
        "operating_perimeter",
        "ordinary_share_claim_scope",
        "currency",
        "unit",
    ):
        if not _text(basis.get(field)):
            findings.append("basis:" + field + "_missing")
    if not _valid_date(basis.get("as_of")):
        findings.append("basis:as_of_invalid")

    periods = _items(value.get("periods"))
    if not periods:
        findings.append("periods_missing")
    seen_period_ids: set[str] = set()
    period_roles: dict[str, dict[str, str]] = {}
    prior_cohort_closing: dict[str, tuple[str, float]] = {}
    prior_net_closing: tuple[str, float] | None = None
    prior_period_end: str | None = None
    for index, raw_period in enumerate(periods):
        period = _mapping(raw_period)
        prefix = f"periods[{index}]"
        _reject_unknown_fields(period, _PERIOD_FIELDS, prefix, findings)
        period_id = str(period.get("period_id") or "")
        if not period_id or period_id in seen_period_ids:
            findings.append(prefix + ":period_id_missing_or_duplicate")
        else:
            seen_period_ids.add(period_id)
            prefix = period_id
        start = period.get("period_start")
        end = period.get("period_end")
        if not _valid_date(start) or not _valid_date(end) or str(start) > str(end):
            findings.append(prefix + ":period_dates_invalid")
        elif prior_period_end is not None and str(start) <= prior_period_end:
            findings.append(prefix + ":periods_overlap_or_out_of_order")
        else:
            prior_period_end = str(end)
        if _valid_date(end) and _valid_date(basis.get("as_of")) and str(end) > str(basis["as_of"]):
            findings.append(prefix + ":period_end_after_as_of")
        _validate_owner_cash_input(
            period.get("owner_cash_input"),
            period_id=period_id,
            findings=findings,
        )
        disclosure_mode = str(period.get("disclosure_mode") or "FULL_GROSS_FLOW")
        if disclosure_mode not in DISCLOSURE_MODES:
            findings.append(prefix + ":disclosure_mode_invalid")
        roles: dict[str, str] = {}
        if disclosure_mode == "NET_MOVEMENT_ONLY":
            prior_cohort_closing.clear()
            if "cohorts" in period:
                findings.append(prefix + ":net_movement_mode_cohorts_forbidden")
            movement = _validate_net_movement_observation(
                period.get("net_movement_observation"),
                period_id=period_id,
                findings=findings,
            )
            if movement is not None:
                opening, closing, _ = movement
                if prior_net_closing is not None:
                    prior_period_id, previous_closing = prior_net_closing
                    if not _same(opening, previous_closing):
                        findings.append(
                            period_id
                            + ":net_movement_observation:opening_not_prior_closing:"
                            + prior_period_id
                        )
                prior_net_closing = (period_id, closing)
        else:
            prior_net_closing = None
            if "net_movement_observation" in period:
                findings.append(prefix + ":full_gross_flow_net_movement_forbidden")
            cohorts = _items(period.get("cohorts"))
            if not cohorts:
                findings.append(prefix + ":cohorts_missing")
            seen_cohort_ids: set[str] = set()
            for cohort_index, raw_cohort in enumerate(cohorts):
                cohort = _mapping(raw_cohort)
                cohort_id, _ = _validate_cohort(
                    cohort,
                    period_id=period_id,
                    index=cohort_index,
                    seen_ids=seen_cohort_ids,
                    findings=findings,
                )
                roles[cohort_id] = str(cohort.get("role") or "")
                opening = _number(cohort.get("opening_net_stock"))
                if cohort_id in prior_cohort_closing and opening is not None:
                    prior_period_id, prior_closing = prior_cohort_closing[cohort_id]
                    if not _same(opening, prior_closing):
                        findings.append(
                            period_id
                            + ":"
                            + cohort_id
                            + ":opening_not_prior_closing:"
                            + prior_period_id
                        )
                closing = _number(cohort.get("closing_net_stock"))
                if cohort_id and closing is not None:
                    prior_cohort_closing[cohort_id] = (period_id, closing)
        period_roles[period_id] = roles
    _validate_valuation_treatment(
        value.get("valuation_treatment"), period_roles=period_roles, findings=findings
    )
    findings = _unique(findings)
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
    }


def _cohort_result(cohort: dict[str, Any]) -> dict[str, Any]:
    actual = _cohort_actual_charge(cohort)
    delta = _cohort_delta_stock(cohort)
    identity_charge = _clean(
        delta + float(cohort["permanent_losses"]) - float(cohort["noncash_scope_change"])
    )
    normalization = cohort["normalization"]
    method = normalization["method"]
    recurring: tuple[float, float, float] | None
    if method == "NOT_APPLICABLE":
        recurring = (0.0, 0.0, 0.0)
    elif method == "OBSERVED_STEADY_CHARGE":
        observed = _derived_observed_recurring_charge(cohort)
        recurring = (observed, observed, observed)
    elif method == "EVIDENCE_BOUNDED":
        values = _bounded_observation_values(normalization)
        low, high = min(values), max(values)
        recurring = (
            low,
            high,
            high if normalization["adopted_endpoint"] == "HIGH" else low,
        )
    else:
        recurring = None
    return {
        "cohort_id": cohort["cohort_id"],
        "role": cohort["role"],
        "loss_treatment": cohort["loss_treatment"],
        "stock_flow_reconciliation": {
            "opening_net_stock": float(cohort["opening_net_stock"]),
            "growth_launch_additions": float(cohort["growth_launch_additions"]),
            "steady_rollover_additions": float(cohort["steady_rollover_additions"]),
            "cash_collections_and_settlements": float(
                cohort["cash_collections_and_settlements"]
            ),
            "permanent_losses": float(cohort["permanent_losses"]),
            "noncash_scope_change": float(cohort["noncash_scope_change"]),
            "closing_net_stock": float(cohort["closing_net_stock"]),
            "delta_net_stock": delta,
            "actual_cash_capital_charge": actual,
            "identity_charge_from_net_stock": identity_charge,
            "identity_closed": True,
        },
        "recurring_steady_state_charge_range": (
            {"range_low": recurring[0], "range_high": recurring[1]}
            if recurring is not None
            else None
        ),
        "adopted_recurring_charge": recurring[2] if recurring is not None else None,
        "adopted_recurring_endpoint": normalization["adopted_endpoint"],
        "normalization_method": method,
        "evidence_ids": deepcopy(cohort["evidence_ids"]),
    }


def _period_result(period: dict[str, Any]) -> dict[str, Any]:
    disclosure_mode = str(period.get("disclosure_mode") or "FULL_GROSS_FLOW")
    if disclosure_mode == "NET_MOVEMENT_ONLY":
        movement = period["net_movement_observation"]
        opening = float(movement["opening_net_stock"])
        closing = float(movement["closing_net_stock"])
        actual_charge = _clean(float(movement["observed_cash_capital_charge"]))
        delta = _clean(closing - opening)
        cohort_results: list[dict[str, Any]] = []
        role_totals: dict[str, float | None] = {
            role: None for role in sorted(COHORT_ROLES)
        }
        stock_flow_reconciliation = {
            "opening_net_stock": opening,
            "closing_net_stock": closing,
            "delta_net_stock": delta,
            "observed_cash_capital_movement": actual_charge,
            "actual_cash_capital_charge": actual_charge,
            "identity_charge_from_net_stock": delta,
            "identity_closed": True,
            "charge_by_cohort_role": role_totals,
            "cash_capital_attribution_status": "UNKNOWN",
            "evidence_ids": deepcopy(movement["evidence_ids"]),
        }
        recurring_known = False
    else:
        cohort_results = [_cohort_result(cohort) for cohort in period["cohorts"]]
        actual_charge = _clean(
            sum(
                item["stock_flow_reconciliation"]["actual_cash_capital_charge"]
                for item in cohort_results
            )
        )
        role_totals = {
            role: _clean(
                sum(
                    item["stock_flow_reconciliation"]["actual_cash_capital_charge"]
                    for item in cohort_results
                    if item["role"] == role
                )
            )
            for role in sorted(COHORT_ROLES)
        }
        stock_flow_reconciliation = {
            "actual_cash_capital_charge": actual_charge,
            "charge_by_cohort_role": role_totals,
            "cash_capital_attribution_status": "ATTRIBUTED_BY_COHORT",
        }
        recurring_known = all(
            item["recurring_steady_state_charge_range"] is not None
            for item in cohort_results
        )
    base = period["owner_cash_input"]
    current = (
        float(base["base_metric_amount"])
        - float(base["maintenance_capex"])
        - float(base["other_owner_adjustments"])
    )
    if base["basis"] == "ACCRUAL_EARNINGS":
        current -= actual_charge
    current = _clean(current)
    recurring_range: dict[str, float] | None = None
    adopted_recurring: float | None = None
    adopted_endpoint = "UNKNOWN"
    normalized_range: dict[str, float] | None = None
    adopted_normalized: float | None = None
    if recurring_known:
        recurring_low = _clean(
            sum(item["recurring_steady_state_charge_range"]["range_low"] for item in cohort_results)
        )
        recurring_high = _clean(
            sum(item["recurring_steady_state_charge_range"]["range_high"] for item in cohort_results)
        )
        adopted_recurring = _clean(
            sum(float(item["adopted_recurring_charge"]) for item in cohort_results)
        )
        component_endpoints = {
            str(item["adopted_recurring_endpoint"]) for item in cohort_results
        }
        adopted_endpoint = (
            next(iter(component_endpoints))
            if len(component_endpoints) == 1
            else "COMPONENT_ENDPOINTS"
        )
        recurring_range = {"range_low": recurring_low, "range_high": recurring_high}
        normalized_range = {
            "range_low": _clean(current + actual_charge - recurring_high),
            "range_high": _clean(current + actual_charge - recurring_low),
        }
        adopted_normalized = _clean(current + actual_charge - adopted_recurring)
    return {
        "period_id": period["period_id"],
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "disclosure_mode": disclosure_mode,
        "owner_cash_basis": base["basis"],
        "cohort_results": cohort_results,
        "stock_flow_reconciliation": stock_flow_reconciliation,
        "current_owner_cash": current,
        "recurring_steady_state_charge_range": recurring_range,
        "adopted_recurring_charge": adopted_recurring,
        "adopted_recurring_endpoint": adopted_endpoint,
        "normalized_owner_cash_range": normalized_range,
        "adopted_normalized_owner_cash": adopted_normalized,
        "normalization_status": "BOUNDED" if recurring_known else "UNKNOWN",
    }


def compute_working_capital_model(payload: Any) -> dict[str, Any]:
    """Compute current and normalized owner cash after validating identities."""
    validation = validate_working_capital_model(payload)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("working_capital_model_invalid:" + ",".join(validation["findings"]))
    value = _mapping(payload)
    period_results = [_period_result(period) for period in value["periods"]]
    by_period = {item["period_id"]: item for item in period_results}
    valuation = deepcopy(value["valuation_treatment"])
    reference = by_period[valuation["reference_period_id"]]
    unknown = reference["normalization_status"] == "UNKNOWN"
    net_movement_only = reference["disclosure_mode"] == "NET_MOVEMENT_ONLY"
    terminal_route = valuation["terminal_route"]
    economic_conclusion = {
        "normal_owner_cash_status": "UNKNOWN" if unknown else "BOUNDED",
        "owner_cash_basis": reference["owner_cash_basis"],
        "observed_cash_capital_status": "OBSERVED",
        "cash_capital_attribution_status": (
            "UNKNOWN" if net_movement_only else "ATTRIBUTED_BY_COHORT"
        ),
        "normalization_scope": (
            "UNATTRIBUTED_NET_MOVEMENT_ONLY"
            if net_movement_only
            else "STEADY_ROLLING_ONLY"
        ),
        "growth_launch_treatment": (
            "UNKNOWN_NOT_INFERRED_FROM_NET_MOVEMENT"
            if net_movement_only
            else "EXCLUDE_FROM_RECURRING_CHARGE"
        ),
        "steady_rolling_treatment": (
            "UNKNOWN_NOT_INFERRED_FROM_NET_MOVEMENT"
            if net_movement_only
            else "NORMALIZE_FROM_COHORT_EVIDENCE"
        ),
        "runoff_or_settlement_treatment": (
            "UNKNOWN_NOT_INFERRED_FROM_NET_MOVEMENT"
            if net_movement_only
            else "EXCLUDE_FROM_RECURRING_CHARGE"
        ),
        "loss_treatment": "RECURRING_EXPECTED_ONLY; ONE_OFF_EXCLUDED; UNKNOWN_LOCALIZED",
        "epv_treatment": (
            "NORMALIZED_OWNER_CASH_WITH_STEADY_RECURRING_CHARGE_ONLY"
            if valuation["epv_use"] == "NORMALIZED_OWNER_CASH"
            else "NOT_USED"
        ),
        "terminal_treatment": {
            "CONTINUING": "NORMALIZED_MATURE_ECONOMICS_AND_TERMINAL_GROWTH_NEED_ONLY",
            "RUNOFF_OR_LIQUIDATION": "STOCK_RELEASE_ONLY_WITHOUT_CONTINUING_EPV",
            "NOT_USED": "NOT_USED",
        }[terminal_route],
        "investor_use": (
            (
                "Treat the net movement as an observed period cash-capital charge only. "
                "Growth-launch "
                "and steady-state attribution remain unknown, so the movement must not become a "
                "recurring charge, EPV input or terminal burden without cohort evidence."
            )
            if net_movement_only
            else (
                "Replace the period working-capital cash movement with the bounded "
                "steady-state charge; do not perpetuate launch absorption or settlement release, "
                "and do not capitalize and "
                "release the same stock."
            )
        ),
    }
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "model_id": value["model_id"],
        "company_id": value["company_id"],
        "basis": deepcopy(value["basis"]),
        "period_results": period_results,
        "reference_period_result": deepcopy(reference),
        "valuation_treatment": valuation,
        "double_count_flags": {
            "working_capital_deducted_twice": False,
            "permanent_loss_deducted_twice": False,
            "continuing_epv_and_runoff_release_combined": False,
        },
        "economic_conclusion": economic_conclusion,
    }


__all__ = [
    "ADOPTED_ENDPOINTS",
    "COHORT_ROLES",
    "DISCLOSURE_MODES",
    "LOSS_TREATMENTS",
    "OWNER_CASH_BASES",
    "RESULT_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "compute_working_capital_model",
    "validate_working_capital_model",
]
