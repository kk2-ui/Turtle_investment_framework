#!/usr/bin/env python3
"""Deterministic cash-accessibility and realization model.

The model deliberately keeps four economic identities apart:

* legal access to cash is a ceiling, not an owner return;
* realization of cash already accumulated is calibrated only by eligible
  extraordinary distributions;
* realization of future retained cash is calibrated by ordinary dividends;
* related-party receivables remain a separate, non-cash recovery asset.

All factual input rows must cite fact IDs declared VERIFIED by the caller.
There is no free-form evidence field and no company-specific research in this
module.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import math
from statistics import median
from typing import Any, Iterable


INPUT_SCHEMA = "cash-accessibility-input.v1"
MODEL_SCHEMA = "cash-accessibility-model.v1"
INPUT_VALIDATION_SCHEMA = "cash-accessibility-input-validation.v1"
MODEL_VALIDATION_SCHEMA = "cash-accessibility-model-validation.v1"

COMPONENTS = (
    "legal_cash_accessibility",
    "existing_excess_cash_realization",
    "future_retained_cash_realization",
    "related_party_receivable_realization",
)
EXPECTED_DESTINATIONS = {
    "legal_cash_accessibility": "legal_accessibility_ceiling_only",
    "existing_excess_cash_realization": "equity_value_existing_excess_cash",
    "future_retained_cash_realization": "operating_value_future_retained_cash",
    "related_party_receivable_realization": "equity_value_related_party_receivable",
}
ENTITY_KINDS = {
    "parent",
    "wholly_owned_subsidiary",
    "partially_owned_subsidiary",
    "joint_venture",
    "other",
}
EVENT_TYPES = {"special_dividend", "cancellative_net_buyback"}
FUNDING_IDENTITIES = {
    "existing_excess_cash",
    "future_retained_cash",
    "debt_funded",
    "unknown",
}
AGING_BUCKETS = {
    "current",
    "less_than_one_year",
    "one_to_two_years",
    "two_to_three_years",
    "over_three_years",
    "unknown",
}
APPLICABILITY_CONDITIONS = {
    "existing_excess_cash": (
        "cash_control_continuity",
        "upstream_mechanism_continuity",
        "extraordinary_distribution_policy_continuity",
        "capital_need_continuity",
    ),
    "future_retained_cash": (
        "cash_control_continuity",
        "ordinary_distribution_policy_continuity",
        "capital_need_continuity",
    ),
    "related_party_receivable": (
        "same_recovery_mechanism",
        "same_counterparty_control",
        "same_settlement_terms",
    ),
}
APPLICABILITY_STATUSES = {
    "EVIDENCE_BACKED", "UNKNOWN", "DISCONTINUITY_IDENTIFIED",
}

_INPUT_ROOT_FIELDS = {
    "schema_version",
    "model_id",
    "company_id",
    "cutoff_at",
    "position_as_of",
    "currency",
    "unit",
    "identity_source_fact_ids",
    "verified_facts",
    "entity_cash_rows",
    "realization_periods",
    "realization_applicability",
    "future_retained_cash",
    "related_party_receivables",
    "valuation_destinations",
}
_IDENTITY_FIELDS = {
    "model_id", "company_id", "cutoff_at", "position_as_of", "currency", "unit",
}
_ENTITY_FIELDS = {
    "entity_id",
    "entity_kind",
    "gross_cash",
    "restricted_or_regulatory_cash",
    "operating_liquidity_requirement",
    "ordinary_share_economic_interest",
    "transfer_tax_friction_rate",
    "source_fact_ids",
}
_PERIOD_FIELDS = {
    "period_id",
    "period_start",
    "period_end",
    "opening_position_as_of",
    "comparable",
    "opening_existing_excess_cash",
    "retained_cash_generated",
    "ordinary_dividend",
    "extraordinary_events",
    "source_fact_ids",
}
_EVENT_FIELDS = {
    "event_type", "event_date", "observed_at", "amount",
    "funding_source_identity", "source_fact_ids",
}
_FUTURE_FIELDS = {"projected_amount", "legal_upper_bound_rate", "source_fact_ids"}
_RECEIVABLE_FIELDS = {
    "receivable_id",
    "gross_amount",
    "ecl_allowance",
    "post_position_collections",
    "aging_bucket",
    "recovery_mechanism_id",
    "recovery_cohorts",
    "prospective_applicability",
    "source_fact_ids",
}
_APPLICABILITY_FIELDS = {
    *APPLICABILITY_CONDITIONS["existing_excess_cash"],
    *APPLICABILITY_CONDITIONS["future_retained_cash"],
    *APPLICABILITY_CONDITIONS["related_party_receivable"],
    "source_fact_ids",
}
_RECOVERY_COHORT_FIELDS = {
    "cohort_id",
    "recovery_mechanism_id",
    "period_start",
    "period_end",
    "maturity_status",
    "opening_gross_exposure",
    "opening_ecl_allowance",
    "cash_collections",
    "noncash_settlements",
    "writeoffs",
    "source_fact_ids",
}
_DESTINATION_FIELDS = {"component_id", "valuation_destination"}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float, Decimal))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"not_a_finite_number:{value!r}") from exc


def _out(value: Decimal | int | float) -> int | float:
    rounded = _decimal(value).quantize(Decimal("0.000000000001"))
    if rounded == rounded.to_integral():
        return int(rounded)
    return float(rounded.normalize())


def _range(low: Decimal, base: Decimal, high: Decimal) -> dict[str, int | float]:
    return {"low": _out(low), "base": _out(base), "high": _out(high)}


def _numbers_equal(observed: Any, expected: Decimal | int | float) -> bool:
    """Compare at the model's twelve-decimal serialization precision."""
    return _is_number(observed) and _out(_decimal(observed)) == _out(expected)


def _validation(schema: str, findings: Iterable[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(findings))
    return {
        "schema_version": schema,
        "state": "VALID" if not unique else "INVALID",
        "findings": unique,
    }


def _unexpected_keys(
    value: Any,
    expected: set[str],
    path: str,
    findings: list[str],
) -> None:
    if not isinstance(value, dict):
        findings.append(path + "_must_be_object")
        return
    for key in sorted(set(value) - expected):
        findings.append(f"{path}.{key}_not_allowed")


def _validate_nonnegative(value: Any, path: str, findings: list[str]) -> None:
    if not _is_number(value) or _decimal(value) < 0:
        findings.append(path + "_must_be_nonnegative_number")


def _validate_rate(value: Any, path: str, findings: list[str]) -> None:
    if not _is_number(value) or not Decimal("0") <= _decimal(value) <= Decimal("1"):
        findings.append(path + "_must_be_rate_between_zero_and_one")


def _validate_refs(
    refs: Any,
    verified_ids: set[str],
    path: str,
    findings: list[str],
) -> None:
    if not isinstance(refs, list) or not refs:
        findings.append(path + "_missing")
        return
    if any(not _text(item) for item in refs):
        findings.append(path + "_invalid")
        return
    if len(set(refs)) != len(refs):
        findings.append(path + "_duplicate")
    for fact_id in refs:
        if fact_id not in verified_ids:
            findings.append(path + f"_not_verified:{fact_id}")


def _validate_optional_refs(
    refs: Any,
    verified_ids: set[str],
    path: str,
    findings: list[str],
) -> None:
    if not isinstance(refs, list):
        findings.append(path + "_must_be_array")
        return
    if any(not _text(item) for item in refs):
        findings.append(path + "_invalid")
        return
    if len(set(refs)) != len(refs):
        findings.append(path + "_duplicate")
    for fact_id in refs:
        if fact_id not in verified_ids:
            findings.append(path + f"_not_verified:{fact_id}")


def _validate_applicability_input(
    raw: Any,
    *,
    kind: str,
    verified_ids: set[str],
    path: str,
    findings: list[str],
) -> None:
    value = _mapping(raw)
    expected = set(APPLICABILITY_CONDITIONS[kind]) | {"source_fact_ids"}
    _unexpected_keys(value, expected, path, findings)
    conditions = APPLICABILITY_CONDITIONS[kind]
    observed = []
    for field in conditions:
        item = value.get(field)
        if item is not None and not isinstance(item, bool):
            findings.append(f"{path}.{field}_must_be_boolean_or_null")
        observed.append(item)
    refs = value.get("source_fact_ids")
    _validate_optional_refs(refs, verified_ids, path + ".source_fact_ids", findings)
    if any(item is not None for item in observed) and not refs:
        findings.append(path + ".source_fact_ids_missing_for_observed_continuity")


def _applicability_projection(raw: Any, *, kind: str) -> dict[str, Any]:
    value = _mapping(raw)
    conditions = {
        field: value.get(field) for field in APPLICABILITY_CONDITIONS[kind]
    }
    if any(item is False for item in conditions.values()):
        status = "DISCONTINUITY_IDENTIFIED"
    elif all(item is True for item in conditions.values()):
        status = "EVIDENCE_BACKED"
    else:
        status = "UNKNOWN"
    return {
        "status": status,
        "conditions": conditions,
        "source_fact_ids": sorted(value.get("source_fact_ids") or []),
    }


def validate_cash_accessibility_input(payload: Any) -> dict[str, Any]:
    """Validate source identity, factual references, and value destinations."""
    value = _mapping(payload)
    findings: list[str] = []
    _unexpected_keys(value, _INPUT_ROOT_FIELDS, "$", findings)
    if value.get("schema_version") != INPUT_SCHEMA:
        findings.append("schema_version_invalid")
    for field in sorted(_IDENTITY_FIELDS):
        if not _text(value.get(field)):
            findings.append(field + "_missing")
    cutoff_at: date | None = None
    try:
        cutoff_at = date.fromisoformat(str(value.get("cutoff_at") or ""))
        position_as_of = date.fromisoformat(str(value.get("position_as_of") or ""))
        if position_as_of > cutoff_at:
            findings.append("position_as_of_after_evidence_cutoff")
    except ValueError:
        findings.append("position_as_of_or_cutoff_at_invalid")

    verified_ids: set[str] = set()
    verified_facts = value.get("verified_facts")
    if not isinstance(verified_facts, list) or not verified_facts:
        findings.append("verified_facts_missing")
    else:
        for index, raw in enumerate(verified_facts):
            fact = _mapping(raw)
            _unexpected_keys(fact, {"fact_id", "status"}, f"verified_facts[{index}]", findings)
            fact_id = fact.get("fact_id")
            if not _text(fact_id) or fact_id in verified_ids:
                findings.append(f"verified_facts[{index}].fact_id_missing_or_duplicate")
            else:
                verified_ids.add(fact_id)
            if fact.get("status") != "VERIFIED":
                findings.append(f"verified_facts[{index}].status_not_verified")

    _validate_refs(
        value.get("identity_source_fact_ids"), verified_ids,
        "identity_source_fact_ids", findings,
    )

    entity_ids: set[str] = set()
    rows = value.get("entity_cash_rows")
    if not isinstance(rows, list) or not rows:
        findings.append("entity_cash_rows_missing")
    else:
        for index, raw in enumerate(rows):
            row = _mapping(raw)
            path = f"entity_cash_rows[{index}]"
            _unexpected_keys(row, _ENTITY_FIELDS, path, findings)
            entity_id = row.get("entity_id")
            if not _text(entity_id) or entity_id in entity_ids:
                findings.append(path + ".entity_id_missing_or_duplicate")
            else:
                entity_ids.add(entity_id)
            if row.get("entity_kind") not in ENTITY_KINDS:
                findings.append(path + ".entity_kind_invalid")
            for field in (
                "gross_cash",
                "restricted_or_regulatory_cash",
                "operating_liquidity_requirement",
            ):
                _validate_nonnegative(row.get(field), path + "." + field, findings)
            for field in (
                "ordinary_share_economic_interest",
                "transfer_tax_friction_rate",
            ):
                _validate_rate(row.get(field), path + "." + field, findings)
            _validate_refs(row.get("source_fact_ids"), verified_ids, path + ".source_fact_ids", findings)

    period_ids: set[str] = set()
    periods = value.get("realization_periods")
    if not isinstance(periods, list):
        findings.append("realization_periods_must_be_array")
    else:
        for index, raw in enumerate(periods):
            period = _mapping(raw)
            path = f"realization_periods[{index}]"
            _unexpected_keys(period, _PERIOD_FIELDS, path, findings)
            period_id = period.get("period_id")
            if not _text(period_id) or period_id in period_ids:
                findings.append(path + ".period_id_missing_or_duplicate")
            else:
                period_ids.add(period_id)
            period_start = period.get("period_start")
            period_end = period.get("period_end")
            opening_position_as_of = period.get("opening_position_as_of")
            start_date: date | None = None
            end_date: date | None = None
            opening_date: date | None = None
            if period_start is None or period_end is None:
                findings.append(path + ".period_bounds_missing")
            else:
                try:
                    start_date = date.fromisoformat(str(period_start))
                    end_date = date.fromisoformat(str(period_end))
                    if start_date > end_date:
                        findings.append(path + ".period_bounds_reversed")
                    if cutoff_at is not None and end_date > cutoff_at:
                        findings.append(path + ".period_end_after_evidence_cutoff")
                except (TypeError, ValueError):
                    findings.append(path + ".period_bounds_invalid")
            try:
                opening_date = date.fromisoformat(str(opening_position_as_of or ""))
            except (TypeError, ValueError):
                findings.append(path + ".opening_position_as_of_invalid")
            if (
                opening_date is not None
                and start_date is not None
                and opening_date > start_date
            ):
                findings.append(path + ".opening_position_after_period_start")
            if cutoff_at is not None and opening_date is not None and opening_date > cutoff_at:
                findings.append(path + ".opening_position_after_evidence_cutoff")
            if not isinstance(period.get("comparable"), bool):
                findings.append(path + ".comparable_must_be_boolean")
            for field in (
                "opening_existing_excess_cash",
                "retained_cash_generated",
                "ordinary_dividend",
            ):
                _validate_nonnegative(period.get(field), path + "." + field, findings)
            _validate_refs(period.get("source_fact_ids"), verified_ids, path + ".source_fact_ids", findings)
            events = period.get("extraordinary_events")
            if not isinstance(events, list):
                findings.append(path + ".extraordinary_events_must_be_array")
                continue
            for event_index, raw_event in enumerate(events):
                event = _mapping(raw_event)
                event_path = f"{path}.extraordinary_events[{event_index}]"
                _unexpected_keys(event, _EVENT_FIELDS, event_path, findings)
                if event.get("event_type") not in EVENT_TYPES:
                    findings.append(event_path + ".event_type_invalid")
                if event.get("funding_source_identity") not in FUNDING_IDENTITIES:
                    findings.append(event_path + ".funding_source_identity_invalid")
                _validate_nonnegative(event.get("amount"), event_path + ".amount", findings)
                _validate_refs(event.get("source_fact_ids"), verified_ids, event_path + ".source_fact_ids", findings)
                try:
                    event_date = date.fromisoformat(str(event.get("event_date") or ""))
                    observed_at = date.fromisoformat(str(event.get("observed_at") or ""))
                except (TypeError, ValueError):
                    findings.append(event_path + ".event_clock_invalid")
                    continue
                if event_date > observed_at:
                    findings.append(event_path + ".observed_before_event_date")
                if start_date is not None and event_date < start_date:
                    findings.append(event_path + ".event_before_period_start")
                if end_date is not None and event_date > end_date:
                    findings.append(event_path + ".event_after_period_end")
                if cutoff_at is not None and observed_at > cutoff_at:
                    findings.append(event_path + ".observed_at_after_evidence_cutoff")

    applicability = _mapping(value.get("realization_applicability"))
    _unexpected_keys(
        applicability,
        {"existing_excess_cash", "future_retained_cash"},
        "realization_applicability",
        findings,
    )
    for kind in ("existing_excess_cash", "future_retained_cash"):
        _validate_applicability_input(
            applicability.get(kind),
            kind=kind,
            verified_ids=verified_ids,
            path="realization_applicability." + kind,
            findings=findings,
        )

    future = _mapping(value.get("future_retained_cash"))
    _unexpected_keys(future, _FUTURE_FIELDS, "future_retained_cash", findings)
    _validate_nonnegative(future.get("projected_amount"), "future_retained_cash.projected_amount", findings)
    _validate_rate(future.get("legal_upper_bound_rate"), "future_retained_cash.legal_upper_bound_rate", findings)
    _validate_refs(future.get("source_fact_ids"), verified_ids, "future_retained_cash.source_fact_ids", findings)

    receivable_ids: set[str] = set()
    receivables = value.get("related_party_receivables")
    if not isinstance(receivables, list):
        findings.append("related_party_receivables_must_be_array")
    else:
        for index, raw in enumerate(receivables):
            row = _mapping(raw)
            path = f"related_party_receivables[{index}]"
            _unexpected_keys(row, _RECEIVABLE_FIELDS, path, findings)
            receivable_id = row.get("receivable_id")
            if not _text(receivable_id) or receivable_id in receivable_ids:
                findings.append(path + ".receivable_id_missing_or_duplicate")
            else:
                receivable_ids.add(receivable_id)
            for field in ("gross_amount", "ecl_allowance", "post_position_collections"):
                _validate_nonnegative(row.get(field), path + "." + field, findings)
            if _is_number(row.get("gross_amount")) and _is_number(row.get("ecl_allowance")):
                if _decimal(row["ecl_allowance"]) > _decimal(row["gross_amount"]):
                    findings.append(path + ".ecl_allowance_exceeds_gross_amount")
            if _is_number(row.get("gross_amount")) and _is_number(row.get("post_position_collections")):
                if _decimal(row["post_position_collections"]) > _decimal(row["gross_amount"]):
                    findings.append(path + ".post_position_collections_exceed_gross_amount")
            if row.get("aging_bucket") not in AGING_BUCKETS:
                findings.append(path + ".aging_bucket_invalid")
            if not _text(row.get("recovery_mechanism_id")):
                findings.append(path + ".recovery_mechanism_id_missing")
            _validate_applicability_input(
                row.get("prospective_applicability"),
                kind="related_party_receivable",
                verified_ids=verified_ids,
                path=path + ".prospective_applicability",
                findings=findings,
            )
            cohort_ids: set[str] = set()
            cohorts = row.get("recovery_cohorts")
            if not isinstance(cohorts, list):
                findings.append(path + ".recovery_cohorts_must_be_array")
            else:
                for cohort_index, raw_cohort in enumerate(cohorts):
                    cohort = _mapping(raw_cohort)
                    cohort_path = f"{path}.recovery_cohorts[{cohort_index}]"
                    _unexpected_keys(
                        cohort, _RECOVERY_COHORT_FIELDS, cohort_path, findings
                    )
                    cohort_id = cohort.get("cohort_id")
                    if not _text(cohort_id) or cohort_id in cohort_ids:
                        findings.append(cohort_path + ".cohort_id_missing_or_duplicate")
                    else:
                        cohort_ids.add(str(cohort_id))
                    if cohort.get("recovery_mechanism_id") != row.get(
                        "recovery_mechanism_id"
                    ):
                        findings.append(cohort_path + ".recovery_mechanism_mismatch")
                    if cohort.get("maturity_status") not in {"MATURED", "OPEN"}:
                        findings.append(cohort_path + ".maturity_status_invalid")
                    for field in (
                        "opening_gross_exposure",
                        "opening_ecl_allowance",
                        "cash_collections",
                        "noncash_settlements",
                        "writeoffs",
                    ):
                        _validate_nonnegative(
                            cohort.get(field), cohort_path + "." + field, findings
                        )
                    if (
                        _is_number(cohort.get("opening_gross_exposure"))
                        and _is_number(cohort.get("opening_ecl_allowance"))
                    ):
                        gross = _decimal(cohort["opening_gross_exposure"])
                        ecl = _decimal(cohort["opening_ecl_allowance"])
                        if ecl > gross:
                            findings.append(cohort_path + ".ecl_exceeds_gross")
                        if all(
                            _is_number(cohort.get(field))
                            for field in (
                                "cash_collections", "noncash_settlements", "writeoffs"
                            )
                        ):
                            resolved = sum(
                                (_decimal(cohort[field]) for field in (
                                    "cash_collections", "noncash_settlements", "writeoffs"
                                )),
                                Decimal("0"),
                            )
                            if resolved > max(Decimal("0"), gross - ecl):
                                findings.append(
                                    cohort_path + ".resolution_exceeds_opening_net_exposure"
                                )
                    try:
                        start = date.fromisoformat(str(cohort.get("period_start") or ""))
                        end = date.fromisoformat(str(cohort.get("period_end") or ""))
                        if start > end:
                            findings.append(cohort_path + ".period_bounds_reversed")
                        if cutoff_at is not None and end > cutoff_at:
                            findings.append(cohort_path + ".period_end_after_evidence_cutoff")
                    except (TypeError, ValueError):
                        findings.append(cohort_path + ".period_bounds_invalid")
                    _validate_refs(
                        cohort.get("source_fact_ids"),
                        verified_ids,
                        cohort_path + ".source_fact_ids",
                        findings,
                    )
            _validate_refs(row.get("source_fact_ids"), verified_ids, path + ".source_fact_ids", findings)

    destinations = value.get("valuation_destinations")
    seen_components: set[str] = set()
    seen_destinations: set[str] = set()
    if not isinstance(destinations, list) or len(destinations) != len(COMPONENTS):
        findings.append("valuation_destinations_must_cover_each_component_once")
    else:
        for index, raw in enumerate(destinations):
            item = _mapping(raw)
            path = f"valuation_destinations[{index}]"
            _unexpected_keys(item, _DESTINATION_FIELDS, path, findings)
            component = item.get("component_id")
            destination = item.get("valuation_destination")
            if component not in COMPONENTS:
                findings.append(path + ".component_id_invalid")
            elif component in seen_components:
                findings.append(path + ".component_id_reused")
            else:
                seen_components.add(component)
            if not _text(destination):
                findings.append(path + ".valuation_destination_missing")
            elif destination in seen_destinations:
                findings.append(path + ".valuation_destination_reused")
            else:
                seen_destinations.add(destination)
            if component in EXPECTED_DESTINATIONS and destination != EXPECTED_DESTINATIONS[component]:
                findings.append(path + ".valuation_destination_incompatible")
        if seen_components != set(COMPONENTS):
            findings.append("valuation_destinations_component_coverage_invalid")

    return _validation(INPUT_VALIDATION_SCHEMA, findings)


def _assert_valid_input(payload: Any) -> dict[str, Any]:
    validation = validate_cash_accessibility_input(payload)
    if validation["state"] != "VALID":
        raise ValueError("cash_accessibility_input_invalid:" + ",".join(validation["findings"]))
    return _mapping(payload)


def _destination_map(payload: dict[str, Any]) -> dict[str, str]:
    return {
        item["component_id"]: item["valuation_destination"]
        for item in payload["valuation_destinations"]
    }


def _historical_rate_range(
    rates: list[Decimal],
    legal_upper_bound_rate: Decimal,
) -> dict[str, int | float] | None:
    """Return an observed diagnostic only after three comparable periods."""
    if len(rates) < 3:
        return None
    bounded = [min(max(rate, Decimal("0")), legal_upper_bound_rate) for rate in rates]
    base = _decimal(median(bounded))
    return _range(min(bounded), base, max(bounded))


def compute_cash_accessibility_model(payload: Any) -> dict[str, Any]:
    """Compile one canonical model from verified, source-referenced inputs."""
    value = _assert_valid_input(payload)
    destinations = _destination_map(value)

    legal_rows: list[dict[str, Any]] = []
    legal_total = Decimal("0")
    unresolved: list[str] = []
    for row in sorted(value["entity_cash_rows"], key=lambda item: item["entity_id"]):
        gross = _decimal(row["gross_cash"])
        restricted = _decimal(row["restricted_or_regulatory_cash"])
        liquidity = _decimal(row["operating_liquidity_requirement"])
        interest = _decimal(row["ordinary_share_economic_interest"])
        friction_rate = _decimal(row["transfer_tax_friction_rate"])
        pre_ownership = max(Decimal("0"), gross - restricted - liquidity)
        attributable = pre_ownership * interest
        friction = attributable * friction_rate
        legal = max(Decimal("0"), attributable - friction)
        legal_total += legal
        if restricted + liquidity > gross:
            unresolved.append(
                f"Entity {row['entity_id']} has no legally accessible surplus after restrictions and operating liquidity."
            )
        legal_rows.append({
            "entity_id": row["entity_id"],
            "entity_kind": row["entity_kind"],
            "gross_cash": _out(gross),
            "restricted_or_regulatory_cash": _out(restricted),
            "operating_liquidity_requirement": _out(liquidity),
            "excess_cash_before_ownership": _out(pre_ownership),
            "ordinary_share_economic_interest": _out(interest),
            "ordinary_share_attributable_before_friction": _out(attributable),
            "transfer_tax_friction_rate": _out(friction_rate),
            "transfer_tax_friction_amount": _out(friction),
            "legal_accessible_cash": _out(legal),
            "source_fact_ids": sorted(row["source_fact_ids"]),
        })

    legal_component = {
        "economic_identity": "max(0, gross cash - restricted or regulatory cash - operating liquidity requirement) x ordinary-share economic interest - transfer tax or friction",
        "rows": legal_rows,
        "amount_range": _range(legal_total, legal_total, legal_total),
        "adopted_value": _out(legal_total),
        "adoption_policy": "computed_legal_ceiling_not_owner_return",
        "valuation_destination": destinations["legal_cash_accessibility"],
    }

    history: list[dict[str, Any]] = []
    existing_rates: list[Decimal] = []
    ordinary_rates: list[Decimal] = []
    for period in sorted(value["realization_periods"], key=lambda item: item["period_id"]):
        opening = _decimal(period["opening_existing_excess_cash"])
        retained = _decimal(period["retained_cash_generated"])
        ordinary = _decimal(period["ordinary_dividend"])
        eligible_amount = Decimal("0")
        has_unknown_funding = False
        events: list[dict[str, Any]] = []
        for event in period["extraordinary_events"]:
            eligible = event["funding_source_identity"] == "existing_excess_cash"
            if event["funding_source_identity"] == "unknown":
                has_unknown_funding = True
            amount = _decimal(event["amount"])
            if eligible:
                eligible_amount += amount
            events.append({
                "event_type": event["event_type"],
                "event_date": event["event_date"],
                "observed_at": event["observed_at"],
                "amount": _out(amount),
                "funding_source_identity": event["funding_source_identity"],
                "eligible_for_existing_excess_cash_calibration": eligible,
                "source_fact_ids": sorted(event["source_fact_ids"]),
            })
        existing_qualifies = bool(period["comparable"] and opening > 0 and not has_unknown_funding)
        existing_rate = min(Decimal("1"), eligible_amount / opening) if existing_qualifies else None
        if existing_rate is not None:
            existing_rates.append(existing_rate)
        ordinary_qualifies = bool(period["comparable"] and retained > 0)
        ordinary_rate = min(Decimal("1"), ordinary / retained) if ordinary_qualifies else None
        if ordinary_rate is not None:
            ordinary_rates.append(ordinary_rate)
        if has_unknown_funding:
            unresolved.append(
                f"Period {period['period_id']} has extraordinary realization with unresolved funding identity."
            )
        history_row = {
            "period_id": period["period_id"],
            "opening_position_as_of": period["opening_position_as_of"],
            "comparable": period["comparable"],
            "opening_existing_excess_cash": _out(opening),
            "retained_cash_generated": _out(retained),
            "ordinary_dividend": _out(ordinary),
            "eligible_extraordinary_realization": _out(eligible_amount),
            "existing_cash_calibration_qualified": existing_qualifies,
            "existing_cash_realization_rate": None if existing_rate is None else _out(existing_rate),
            "future_retained_cash_calibration_qualified": ordinary_qualifies,
            "ordinary_distribution_rate": None if ordinary_rate is None else _out(ordinary_rate),
            "extraordinary_events": events,
            "source_fact_ids": sorted(period["source_fact_ids"]),
        }
        history_row["period_start"] = period["period_start"]
        history_row["period_end"] = period["period_end"]
        history.append(history_row)

    realization_applicability = value["realization_applicability"]
    existing_applicability = _applicability_projection(
        realization_applicability["existing_excess_cash"],
        kind="existing_excess_cash",
    )
    existing_observed_range = _historical_rate_range(existing_rates, Decimal("1"))
    existing_rate_range = (
        existing_observed_range
        if existing_observed_range is not None
        and existing_applicability["status"] == "EVIDENCE_BACKED"
        else None
    )
    existing_adopted_rate = (
        _decimal(existing_rate_range["base"])
        if existing_rate_range is not None
        else None
    )
    if len(existing_rates) < 3:
        unresolved.append(
            "Fewer than three comparable periods establish extraordinary realization of existing excess cash."
        )
    if existing_rate_range is None:
        existing_low = existing_base = existing_high = Decimal("0")
    else:
        existing_low = legal_total * _decimal(existing_rate_range["low"])
        existing_base = legal_total * _decimal(existing_rate_range["base"])
        existing_high = legal_total * _decimal(existing_rate_range["high"])
    existing_component = {
        "legal_upper_bound": _out(legal_total),
        "qualifying_period_count": len(existing_rates),
        "required_period_count": 3,
        "calibration_method": (
            "observed_min_median_max"
            if existing_observed_range is not None
            else "insufficient_comparable_history"
        ),
        "historical_observed_rate_range": existing_observed_range,
        "prospective_applicability": existing_applicability,
        "realization_rate_range": existing_rate_range,
        "amount_range": _range(existing_low, existing_base, existing_high),
        "adopted_realization_rate": (
            None if existing_adopted_rate is None else _out(existing_adopted_rate)
        ),
        "adopted_value": _out(existing_base),
        "adoption_policy": (
            "evidence_backed_historical_rate_range"
            if existing_rate_range is not None
            else "zero_recognized_until_history_and_continuity_are_evidence_backed"
        ),
        "valuation_destination": destinations["existing_excess_cash_realization"],
        "history": history,
    }

    future_input = value["future_retained_cash"]
    future_amount = _decimal(future_input["projected_amount"])
    future_legal_rate = _decimal(future_input["legal_upper_bound_rate"])
    future_applicability = _applicability_projection(
        realization_applicability["future_retained_cash"],
        kind="future_retained_cash",
    )
    future_observed_range = _historical_rate_range(
        ordinary_rates, future_legal_rate
    )
    future_rate_range = (
        future_observed_range
        if future_observed_range is not None
        and future_applicability["status"] == "EVIDENCE_BACKED"
        else None
    )
    future_adopted_rate = (
        _decimal(future_rate_range["base"])
        if future_rate_range is not None
        else None
    )
    if len(ordinary_rates) < 3:
        unresolved.append(
            "Fewer than three comparable periods establish ordinary distribution capacity for future retained cash."
        )
    future_component = {
        "projected_retained_cash": _out(future_amount),
        "legal_upper_bound_rate": _out(future_legal_rate),
        "qualifying_period_count": len(ordinary_rates),
        "required_period_count": 3,
        "calibration_method": (
            "observed_min_median_max"
            if future_observed_range is not None
            else "insufficient_comparable_history"
        ),
        "historical_observed_rate_range": future_observed_range,
        "prospective_applicability": future_applicability,
        "realization_rate_range": future_rate_range,
        "amount_range": _range(
            Decimal("0") if future_rate_range is None else future_amount * _decimal(future_rate_range["low"]),
            Decimal("0") if future_rate_range is None else future_amount * _decimal(future_rate_range["base"]),
            Decimal("0") if future_rate_range is None else future_amount * _decimal(future_rate_range["high"]),
        ),
        "adopted_realization_rate": (
            None if future_adopted_rate is None else _out(future_adopted_rate)
        ),
        "adopted_value": _out(
            Decimal("0")
            if future_adopted_rate is None
            else future_amount * future_adopted_rate
        ),
        "adoption_policy": (
            "evidence_backed_historical_rate_range"
            if future_rate_range is not None
            else "zero_recognized_until_history_and_continuity_are_evidence_backed"
        ),
        "valuation_destination": destinations["future_retained_cash_realization"],
        "source_fact_ids": sorted(future_input["source_fact_ids"]),
    }

    receivable_rows: list[dict[str, Any]] = []
    receivable_gross = Decimal("0")
    receivable_ecl = Decimal("0")
    receivable_collections = Decimal("0")
    receivable_uncollected = Decimal("0")
    receivable_unrecognized = Decimal("0")
    receivable_low = Decimal("0")
    receivable_base = Decimal("0")
    receivable_high = Decimal("0")
    receivable_statuses: list[str] = []
    for row in sorted(value["related_party_receivables"], key=lambda item: item["receivable_id"]):
        gross = _decimal(row["gross_amount"])
        ecl = _decimal(row["ecl_allowance"])
        collections = _decimal(row["post_position_collections"])
        residual_after_ecl_and_collection = max(
            Decimal("0"), gross - ecl - collections
        )
        cohort_rows: list[dict[str, Any]] = []
        mature_rates: list[Decimal] = []
        for cohort in sorted(row["recovery_cohorts"], key=lambda item: item["cohort_id"]):
            cohort_gross = _decimal(cohort["opening_gross_exposure"])
            cohort_ecl = _decimal(cohort["opening_ecl_allowance"])
            cohort_net = max(Decimal("0"), cohort_gross - cohort_ecl)
            cohort_cash = _decimal(cohort["cash_collections"])
            cohort_noncash = _decimal(cohort["noncash_settlements"])
            cohort_writeoffs = _decimal(cohort["writeoffs"])
            recovery_rate = (
                min(Decimal("1"), (cohort_cash + cohort_noncash) / cohort_net)
                if cohort["maturity_status"] == "MATURED" and cohort_net > 0
                else None
            )
            if recovery_rate is not None:
                mature_rates.append(recovery_rate)
            cohort_rows.append({
                "cohort_id": cohort["cohort_id"],
                "recovery_mechanism_id": cohort["recovery_mechanism_id"],
                "period_start": cohort["period_start"],
                "period_end": cohort["period_end"],
                "maturity_status": cohort["maturity_status"],
                "opening_gross_exposure": _out(cohort_gross),
                "opening_ecl_allowance": _out(cohort_ecl),
                "opening_net_exposure": _out(cohort_net),
                "cash_collections": _out(cohort_cash),
                "noncash_settlements": _out(cohort_noncash),
                "writeoffs": _out(cohort_writeoffs),
                "realized_recovery_rate": (
                    None if recovery_rate is None else _out(recovery_rate)
                ),
                "source_fact_ids": sorted(cohort["source_fact_ids"]),
            })
        observed_recovery_range = _historical_rate_range(
            mature_rates, Decimal("1")
        )
        recovery_applicability = _applicability_projection(
            row["prospective_applicability"], kind="related_party_receivable"
        )
        uncollected_recovery_range = (
            observed_recovery_range
            if observed_recovery_range is not None
            and recovery_applicability["status"] == "EVIDENCE_BACKED"
            else None
        )
        if residual_after_ecl_and_collection == 0:
            recovery_status = "FULLY_COLLECTED_OR_ALLOWED"
            low = base = high = collections
            unrecognized = Decimal("0")
        elif uncollected_recovery_range is None:
            recovery_status = "UNKNOWN"
            low = base = high = collections
            unrecognized = residual_after_ecl_and_collection
            unresolved.append(
                f"Receivable {row['receivable_id']} has no evidence-backed prospective recovery rate for its uncollected net exposure."
            )
        else:
            recovery_status = "EVIDENCE_BACKED"
            low = collections + residual_after_ecl_and_collection * _decimal(
                uncollected_recovery_range["low"]
            )
            base = collections + residual_after_ecl_and_collection * _decimal(
                uncollected_recovery_range["base"]
            )
            high = collections + residual_after_ecl_and_collection * _decimal(
                uncollected_recovery_range["high"]
            )
            unrecognized = Decimal("0")
        receivable_gross += gross
        receivable_ecl += ecl
        receivable_collections += collections
        receivable_uncollected += residual_after_ecl_and_collection
        receivable_unrecognized += unrecognized
        receivable_low += low
        receivable_base += base
        receivable_high += high
        receivable_statuses.append(recovery_status)
        receivable_rows.append({
            "receivable_id": row["receivable_id"],
            "gross_amount": _out(gross),
            "ecl_allowance": _out(ecl),
            "post_position_collections": _out(collections),
            "aging_bucket": row["aging_bucket"],
            "recovery_mechanism_id": row["recovery_mechanism_id"],
            "uncollected_net_exposure": _out(residual_after_ecl_and_collection),
            "unrecognized_net_exposure": _out(unrecognized),
            "mature_cohort_count": len(mature_rates),
            "required_mature_cohort_count": 3,
            "historical_observed_recovery_rate_range": observed_recovery_range,
            "prospective_applicability": recovery_applicability,
            "uncollected_recovery_rate_range": uncollected_recovery_range,
            "recovery_status": recovery_status,
            "recovery_cohorts": cohort_rows,
            "amount_range": _range(low, base, high),
            "adopted_value": _out(base),
            "source_fact_ids": sorted(row["source_fact_ids"]),
        })
    if receivable_statuses and all(
        status == "FULLY_COLLECTED_OR_ALLOWED" for status in receivable_statuses
    ):
        component_recovery_status = "FULLY_COLLECTED_OR_ALLOWED"
    elif receivable_statuses and all(
        status in {"EVIDENCE_BACKED", "FULLY_COLLECTED_OR_ALLOWED"}
        for status in receivable_statuses
    ):
        component_recovery_status = "EVIDENCE_BACKED"
    elif any(status == "EVIDENCE_BACKED" for status in receivable_statuses):
        component_recovery_status = "PARTIAL_EVIDENCE"
    else:
        component_recovery_status = "UNKNOWN"
    receivable_component = {
        "rows": receivable_rows,
        "gross_receivables": _out(receivable_gross),
        "ecl_allowance": _out(receivable_ecl),
        "post_position_collections": _out(receivable_collections),
        "uncollected_net_exposure": _out(receivable_uncollected),
        "unrecognized_net_exposure": _out(receivable_unrecognized),
        "recovery_status": component_recovery_status,
        "amount_range": _range(receivable_low, receivable_base, receivable_high),
        "adopted_value": _out(receivable_base),
        "adoption_policy": "collections_plus_evidence_backed_same_mechanism_mature_cohorts_only",
        "valuation_destination": destinations["related_party_receivable_realization"],
    }

    components = {
        "legal_cash_accessibility": legal_component,
        "existing_excess_cash_realization": existing_component,
        "future_retained_cash_realization": future_component,
        "related_party_receivable_realization": receivable_component,
    }
    inclusion_modes = {
        "legal_cash_accessibility": "BOUND_ONLY",
        "existing_excess_cash_realization": "ADDITIVE_EQUITY_BRIDGE",
        "future_retained_cash_realization": "OPERATING_VALUE_ADJUSTMENT",
        "related_party_receivable_realization": "ADDITIVE_EQUITY_BRIDGE",
    }
    ledger = [
        {
            "component_id": component,
            "valuation_destination": destinations[component],
            "inclusion_mode": inclusion_modes[component],
            "adopted_value": components[component]["adopted_value"],
        }
        for component in COMPONENTS
    ]
    model: dict[str, Any] = {
        "schema_version": MODEL_SCHEMA,
        "model_id": value["model_id"],
        "company_id": value["company_id"],
        "cutoff_at": value["cutoff_at"],
        "position_as_of": value["position_as_of"],
        "as_of": value["position_as_of"],
        "currency": value["currency"],
        "unit": value["unit"],
        "input_fact_ids": sorted(item["fact_id"] for item in value["verified_facts"]),
        **components,
        "valuation_destination_ledger": ledger,
        "unresolved_facts": list(dict.fromkeys(unresolved)),
    }
    model["economic_conclusion"] = _economic_conclusion_unchecked(model)
    model["reader_conclusions"] = _reader_conclusions_unchecked(model)
    validation = validate_cash_accessibility_model(model)
    if validation["state"] != "VALID":
        raise AssertionError("compiled_cash_accessibility_model_invalid:" + ",".join(validation["findings"]))
    return model


compile_cash_accessibility_model = compute_cash_accessibility_model


def _component_range_findings(component: Any, path: str) -> list[str]:
    findings: list[str] = []
    value = _mapping(component)
    amount_range = _mapping(value.get("amount_range"))
    if set(amount_range) != {"low", "base", "high"}:
        findings.append(path + ".amount_range_invalid")
        return findings
    if not all(_is_number(amount_range.get(key)) for key in ("low", "base", "high")):
        findings.append(path + ".amount_range_non_numeric")
        return findings
    low, base, high = (_decimal(amount_range[key]) for key in ("low", "base", "high"))
    if low < 0 or not low <= base <= high:
        findings.append(path + ".amount_range_not_monotonic")
    if not _is_number(value.get("adopted_value")):
        findings.append(path + ".adopted_value_invalid")
    else:
        adopted = _decimal(value["adopted_value"])
        if not low <= adopted <= high:
            findings.append(path + ".adopted_value_outside_range")
    return findings


def _ranges_equal(observed: Any, expected: Any) -> bool:
    if expected is None:
        return observed is None
    value = _mapping(observed)
    expected_value = _mapping(expected)
    return set(value) == {"low", "base", "high"} and all(
        _numbers_equal(value.get(key), expected_value.get(key))
        for key in ("low", "base", "high")
    )


def _validate_applicability_projection(
    raw: Any, *, kind: str, path: str, findings: list[str]
) -> str:
    value = _mapping(raw)
    conditions = _mapping(value.get("conditions"))
    expected_fields = set(APPLICABILITY_CONDITIONS[kind])
    if set(conditions) != expected_fields:
        findings.append(path + ".conditions_invalid")
    for field in expected_fields:
        item = conditions.get(field)
        if item is not None and not isinstance(item, bool):
            findings.append(path + f".conditions.{field}_must_be_boolean_or_null")
    refs = value.get("source_fact_ids")
    if (
        not isinstance(refs, list)
        or any(not _text(ref) for ref in refs)
        or len(set(refs)) != len(refs)
    ):
        findings.append(path + ".source_fact_ids_invalid")
    if any(item is not None for item in conditions.values()) and not refs:
        findings.append(path + ".source_fact_ids_missing_for_observed_continuity")
    if any(item is False for item in conditions.values()):
        expected_status = "DISCONTINUITY_IDENTIFIED"
    elif expected_fields and all(conditions.get(field) is True for field in expected_fields):
        expected_status = "EVIDENCE_BACKED"
    else:
        expected_status = "UNKNOWN"
    if value.get("status") != expected_status:
        findings.append(path + ".status_not_deterministic")
    return expected_status


def _referenced_fact_ids(model: dict[str, Any]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    legal = _mapping(model.get("legal_cash_accessibility"))
    for index, row in enumerate(_items(legal.get("rows"))):
        for ref in _items(_mapping(row).get("source_fact_ids")):
            found.append((f"legal_cash_accessibility.rows[{index}]", ref))
    existing = _mapping(model.get("existing_excess_cash_realization"))
    for ref in _items(
        _mapping(existing.get("prospective_applicability")).get("source_fact_ids")
    ):
        found.append(("existing_excess_cash_realization.prospective_applicability", ref))
    for index, period in enumerate(_items(existing.get("history"))):
        period_map = _mapping(period)
        for ref in _items(period_map.get("source_fact_ids")):
            found.append((f"existing_excess_cash_realization.history[{index}]", ref))
        for event_index, event in enumerate(_items(period_map.get("extraordinary_events"))):
            for ref in _items(_mapping(event).get("source_fact_ids")):
                found.append((f"existing_excess_cash_realization.history[{index}].extraordinary_events[{event_index}]", ref))
    future = _mapping(model.get("future_retained_cash_realization"))
    for ref in _items(future.get("source_fact_ids")):
        found.append(("future_retained_cash_realization", ref))
    for ref in _items(
        _mapping(future.get("prospective_applicability")).get("source_fact_ids")
    ):
        found.append(("future_retained_cash_realization.prospective_applicability", ref))
    receivable = _mapping(model.get("related_party_receivable_realization"))
    for index, row in enumerate(_items(receivable.get("rows"))):
        row_map = _mapping(row)
        for ref in _items(row_map.get("source_fact_ids")):
            found.append((f"related_party_receivable_realization.rows[{index}]", ref))
        for ref in _items(
            _mapping(row_map.get("prospective_applicability")).get("source_fact_ids")
        ):
            found.append((
                f"related_party_receivable_realization.rows[{index}].prospective_applicability",
                ref,
            ))
        for cohort_index, cohort in enumerate(_items(row_map.get("recovery_cohorts"))):
            for ref in _items(_mapping(cohort).get("source_fact_ids")):
                found.append((
                    f"related_party_receivable_realization.rows[{index}].recovery_cohorts[{cohort_index}]",
                    ref,
                ))
    return found


def validate_cash_accessibility_model(model: Any) -> dict[str, Any]:
    """Validate the compiled model's identities and anti-double-count ledger."""
    value = _mapping(model)
    findings: list[str] = []
    if value.get("schema_version") != MODEL_SCHEMA:
        findings.append("schema_version_invalid")
    for field in (
        "model_id", "company_id", "cutoff_at", "position_as_of", "as_of", "currency", "unit"
    ):
        if not _text(value.get(field)):
            findings.append(field + "_missing")
    if value.get("as_of") != value.get("position_as_of"):
        findings.append("as_of_must_equal_position_as_of")
    cutoff_at: date | None = None
    try:
        cutoff_at = date.fromisoformat(str(value.get("cutoff_at") or ""))
        position_as_of = date.fromisoformat(str(value.get("position_as_of") or ""))
        if position_as_of > cutoff_at:
            findings.append("position_as_of_after_evidence_cutoff")
    except ValueError:
        findings.append("position_as_of_or_cutoff_at_invalid")
    fact_ids = value.get("input_fact_ids")
    if (
        not isinstance(fact_ids, list)
        or not fact_ids
        or any(not _text(item) for item in fact_ids)
        or len(set(fact_ids)) != len(fact_ids)
    ):
        findings.append("input_fact_ids_invalid")
        fact_id_set: set[str] = set()
    else:
        fact_id_set = set(fact_ids)
    referenced = _referenced_fact_ids(value)
    for path, ref in referenced:
        if ref not in fact_id_set:
            findings.append(path + f".source_fact_id_not_declared:{ref}")

    source_bearing_rows: list[tuple[str, dict[str, Any]]] = []
    legal_for_refs = _mapping(value.get("legal_cash_accessibility"))
    source_bearing_rows.extend(
        (f"legal_cash_accessibility.rows[{index}]", _mapping(row))
        for index, row in enumerate(_items(legal_for_refs.get("rows")))
    )
    existing_for_refs = _mapping(value.get("existing_excess_cash_realization"))
    for index, period in enumerate(_items(existing_for_refs.get("history"))):
        period_map = _mapping(period)
        source_bearing_rows.append((f"existing_excess_cash_realization.history[{index}]", period_map))
        source_bearing_rows.extend(
            (
                f"existing_excess_cash_realization.history[{index}].extraordinary_events[{event_index}]",
                _mapping(event),
            )
            for event_index, event in enumerate(_items(period_map.get("extraordinary_events")))
        )
    source_bearing_rows.append(
        ("future_retained_cash_realization", _mapping(value.get("future_retained_cash_realization")))
    )
    receivable_for_refs = _mapping(value.get("related_party_receivable_realization"))
    source_bearing_rows.extend(
        (f"related_party_receivable_realization.rows[{index}]", _mapping(row))
        for index, row in enumerate(_items(receivable_for_refs.get("rows")))
    )
    for index, row in enumerate(_items(receivable_for_refs.get("rows"))):
        row_map = _mapping(row)
        source_bearing_rows.extend(
            (
                f"related_party_receivable_realization.rows[{index}].recovery_cohorts[{cohort_index}]",
                _mapping(cohort),
            )
            for cohort_index, cohort in enumerate(_items(row_map.get("recovery_cohorts")))
        )
    for path, row in source_bearing_rows:
        refs = row.get("source_fact_ids")
        if (
            not isinstance(refs, list)
            or not refs
            or any(not _text(ref) for ref in refs)
            or len(set(refs)) != len(refs)
        ):
            findings.append(path + ".source_fact_ids_invalid")

    for component in COMPONENTS:
        findings.extend(_component_range_findings(value.get(component), component))

    legal = _mapping(value.get("legal_cash_accessibility"))
    legal_rows = _items(legal.get("rows"))
    legal_sum = Decimal("0")
    for index, raw_row in enumerate(legal_rows):
        row = _mapping(raw_row)
        numeric_fields = (
            "gross_cash",
            "restricted_or_regulatory_cash",
            "operating_liquidity_requirement",
            "excess_cash_before_ownership",
            "ordinary_share_economic_interest",
            "ordinary_share_attributable_before_friction",
            "transfer_tax_friction_rate",
            "transfer_tax_friction_amount",
            "legal_accessible_cash",
        )
        if any(not _is_number(row.get(field)) for field in numeric_fields):
            findings.append(f"legal_cash_accessibility.rows[{index}].numeric_fields_invalid")
            continue
        gross = _decimal(row["gross_cash"])
        restricted = _decimal(row["restricted_or_regulatory_cash"])
        liquidity = _decimal(row["operating_liquidity_requirement"])
        interest = _decimal(row["ordinary_share_economic_interest"])
        friction_rate = _decimal(row["transfer_tax_friction_rate"])
        expected_excess = max(Decimal("0"), gross - restricted - liquidity)
        expected_attributable = expected_excess * interest
        expected_friction = expected_attributable * friction_rate
        expected_legal = max(Decimal("0"), expected_attributable - expected_friction)
        expected_fields = {
            "excess_cash_before_ownership": expected_excess,
            "ordinary_share_attributable_before_friction": expected_attributable,
            "transfer_tax_friction_amount": expected_friction,
            "legal_accessible_cash": expected_legal,
        }
        for field, expected in expected_fields.items():
            if not _numbers_equal(row[field], expected):
                findings.append(f"legal_cash_accessibility.rows[{index}].{field}_identity_mismatch")
        legal_sum += _decimal(row["legal_accessible_cash"])
    if _is_number(legal.get("adopted_value")) and not _numbers_equal(legal["adopted_value"], legal_sum):
        findings.append("legal_cash_accessibility.row_sum_mismatch")
    if _mapping(legal.get("amount_range")) and any(
        not _numbers_equal(legal["amount_range"].get(key), legal_sum) for key in ("low", "base", "high")
    ):
        findings.append("legal_cash_accessibility.range_must_equal_computed_ceiling")

    existing = _mapping(value.get("existing_excess_cash_realization"))
    if not _is_number(existing.get("legal_upper_bound")):
        findings.append("existing_excess_cash_realization.legal_upper_bound_invalid")
        ceiling = Decimal("0")
    else:
        ceiling = _decimal(existing["legal_upper_bound"])
        if not _numbers_equal(ceiling, legal_sum):
            findings.append("existing_excess_cash_realization.legal_ceiling_mismatch")
    qualifying_existing_rates: list[Decimal] = []
    qualifying_future_rates: list[Decimal] = []
    for index, raw_period in enumerate(_items(existing.get("history"))):
        period = _mapping(raw_period)
        period_path = f"existing_excess_cash_realization.history[{index}]"
        try:
            period_start = date.fromisoformat(str(period.get("period_start") or ""))
            period_end = date.fromisoformat(str(period.get("period_end") or ""))
            opening_position = date.fromisoformat(
                str(period.get("opening_position_as_of") or "")
            )
            if period_start > period_end:
                findings.append(period_path + ".period_bounds_reversed")
            if opening_position > period_start:
                findings.append(period_path + ".opening_position_after_period_start")
            if cutoff_at is not None and opening_position > cutoff_at:
                findings.append(period_path + ".opening_position_after_evidence_cutoff")
        except (TypeError, ValueError):
            period_start = period_end = None
            findings.append(period_path + ".temporal_fields_invalid")
        if not all(
            _is_number(period.get(field))
            for field in (
                "opening_existing_excess_cash",
                "retained_cash_generated",
                "ordinary_dividend",
                "eligible_extraordinary_realization",
            )
        ) or not isinstance(period.get("comparable"), bool):
            findings.append(f"existing_excess_cash_realization.history[{index}].period_fields_invalid")
            continue
        opening = _decimal(period["opening_existing_excess_cash"])
        retained = _decimal(period["retained_cash_generated"])
        ordinary = _decimal(period["ordinary_dividend"])
        eligible_amount = Decimal("0")
        unknown_funding = False
        for event_index, raw_event in enumerate(_items(period.get("extraordinary_events"))):
            event = _mapping(raw_event)
            event_path = period_path + f".extraordinary_events[{event_index}]"
            try:
                event_date = date.fromisoformat(str(event.get("event_date") or ""))
                observed_at = date.fromisoformat(str(event.get("observed_at") or ""))
                if event_date > observed_at:
                    findings.append(event_path + ".observed_before_event_date")
                if period_start is not None and event_date < period_start:
                    findings.append(event_path + ".event_before_period_start")
                if period_end is not None and event_date > period_end:
                    findings.append(event_path + ".event_after_period_end")
                if cutoff_at is not None and observed_at > cutoff_at:
                    findings.append(event_path + ".observed_at_after_evidence_cutoff")
            except (TypeError, ValueError):
                findings.append(event_path + ".event_clock_invalid")
            if not _is_number(event.get("amount")):
                findings.append(
                    event_path + ".amount_invalid"
                )
                continue
            funding = event.get("funding_source_identity")
            expected_eligible = funding == "existing_excess_cash"
            if event.get("eligible_for_existing_excess_cash_calibration") is not expected_eligible:
                findings.append(
                    f"existing_excess_cash_realization.history[{index}].extraordinary_events[{event_index}].eligibility_mismatch"
                )
            if expected_eligible:
                eligible_amount += _decimal(event["amount"])
            if funding == "unknown":
                unknown_funding = True
        if not _numbers_equal(period["eligible_extraordinary_realization"], eligible_amount):
            findings.append(
                f"existing_excess_cash_realization.history[{index}].eligible_extraordinary_realization_mismatch"
            )
        expected_existing_qualified = bool(period["comparable"] and opening > 0 and not unknown_funding)
        if period.get("existing_cash_calibration_qualified") is not expected_existing_qualified:
            findings.append(
                f"existing_excess_cash_realization.history[{index}].existing_qualification_mismatch"
            )
        expected_existing_rate = min(Decimal("1"), eligible_amount / opening) if expected_existing_qualified else None
        observed_existing_rate = period.get("existing_cash_realization_rate")
        if expected_existing_rate is None:
            if observed_existing_rate is not None:
                findings.append(
                    f"existing_excess_cash_realization.history[{index}].existing_rate_must_be_null"
                )
        elif not _numbers_equal(observed_existing_rate, expected_existing_rate):
            findings.append(
                f"existing_excess_cash_realization.history[{index}].existing_rate_mismatch"
            )
        else:
            qualifying_existing_rates.append(expected_existing_rate)

        expected_future_qualified = bool(period["comparable"] and retained > 0)
        if period.get("future_retained_cash_calibration_qualified") is not expected_future_qualified:
            findings.append(
                f"existing_excess_cash_realization.history[{index}].future_qualification_mismatch"
            )
        expected_ordinary_rate = min(Decimal("1"), ordinary / retained) if expected_future_qualified else None
        observed_ordinary_rate = period.get("ordinary_distribution_rate")
        if expected_ordinary_rate is None:
            if observed_ordinary_rate is not None:
                findings.append(
                    f"existing_excess_cash_realization.history[{index}].ordinary_rate_must_be_null"
                )
        elif not _numbers_equal(observed_ordinary_rate, expected_ordinary_rate):
            findings.append(
                f"existing_excess_cash_realization.history[{index}].ordinary_rate_mismatch"
            )
        else:
            qualifying_future_rates.append(expected_ordinary_rate)
    if existing.get("qualifying_period_count") != len(qualifying_existing_rates):
        findings.append("existing_excess_cash_realization.qualifying_period_count_mismatch")
    existing_observed = _historical_rate_range(
        qualifying_existing_rates, Decimal("1")
    )
    if not _ranges_equal(
        existing.get("historical_observed_rate_range"), existing_observed
    ):
        findings.append(
            "existing_excess_cash_realization.historical_observed_rate_range_mismatch"
        )
    existing_status = _validate_applicability_projection(
        existing.get("prospective_applicability"),
        kind="existing_excess_cash",
        path="existing_excess_cash_realization.prospective_applicability",
        findings=findings,
    )
    expected_existing_range = (
        existing_observed
        if existing_observed is not None and existing_status == "EVIDENCE_BACKED"
        else None
    )
    if not _ranges_equal(existing.get("realization_rate_range"), expected_existing_range):
        findings.append(
            "existing_excess_cash_realization.prospective_rate_range_mismatch"
        )
    existing_amount = _mapping(existing.get("amount_range"))
    for key in ("low", "base", "high"):
        expected = (
            Decimal("0")
            if expected_existing_range is None
            else ceiling * _decimal(expected_existing_range[key])
        )
        if not _numbers_equal(existing_amount.get(key), expected):
            findings.append(
                f"existing_excess_cash_realization.{key}_arithmetic_mismatch"
            )
    expected_existing_adopted_rate = (
        None
        if expected_existing_range is None
        else expected_existing_range["base"]
    )
    if expected_existing_adopted_rate is None:
        if existing.get("adopted_realization_rate") is not None:
            findings.append(
                "existing_excess_cash_realization.unknown_adopted_rate_must_be_null"
            )
    elif not _numbers_equal(
        existing.get("adopted_realization_rate"), expected_existing_adopted_rate
    ):
        findings.append(
            "existing_excess_cash_realization.adopted_rate_mismatch"
        )

    future = _mapping(value.get("future_retained_cash_realization"))
    if future.get("qualifying_period_count") != len(qualifying_future_rates):
        findings.append("future_retained_cash_realization.qualifying_period_count_mismatch")
    legal_rate = (
        _decimal(future["legal_upper_bound_rate"])
        if _is_number(future.get("legal_upper_bound_rate"))
        else Decimal("0")
    )
    future_observed = _historical_rate_range(qualifying_future_rates, legal_rate)
    if not _ranges_equal(
        future.get("historical_observed_rate_range"), future_observed
    ):
        findings.append(
            "future_retained_cash_realization.historical_observed_rate_range_mismatch"
        )
    future_status = _validate_applicability_projection(
        future.get("prospective_applicability"),
        kind="future_retained_cash",
        path="future_retained_cash_realization.prospective_applicability",
        findings=findings,
    )
    expected_future_range = (
        future_observed
        if future_observed is not None and future_status == "EVIDENCE_BACKED"
        else None
    )
    if not _ranges_equal(future.get("realization_rate_range"), expected_future_range):
        findings.append(
            "future_retained_cash_realization.prospective_rate_range_mismatch"
        )
    projected = (
        _decimal(future["projected_retained_cash"])
        if _is_number(future.get("projected_retained_cash"))
        else Decimal("0")
    )
    future_amount = _mapping(future.get("amount_range"))
    for key in ("low", "base", "high"):
        expected = (
            Decimal("0")
            if expected_future_range is None
            else projected * _decimal(expected_future_range[key])
        )
        if not _numbers_equal(future_amount.get(key), expected):
            findings.append(
                f"future_retained_cash_realization.{key}_arithmetic_mismatch"
            )
    expected_future_adopted_rate = (
        None if expected_future_range is None else expected_future_range["base"]
    )
    if expected_future_adopted_rate is None:
        if future.get("adopted_realization_rate") is not None:
            findings.append(
                "future_retained_cash_realization.unknown_adopted_rate_must_be_null"
            )
    elif not _numbers_equal(
        future.get("adopted_realization_rate"), expected_future_adopted_rate
    ):
        findings.append("future_retained_cash_realization.adopted_rate_mismatch")

    receivable = _mapping(value.get("related_party_receivable_realization"))
    receivable_rows = _items(receivable.get("rows"))
    expected_component_statuses: list[str] = []
    for index, raw_row in enumerate(receivable_rows):
        row = _mapping(raw_row)
        if any(
            not _is_number(row.get(field))
            for field in (
                "gross_amount",
                "ecl_allowance",
                "post_position_collections",
                "uncollected_net_exposure",
                "unrecognized_net_exposure",
            )
        ) or row.get("aging_bucket") not in AGING_BUCKETS or not _text(
            row.get("recovery_mechanism_id")
        ):
            findings.append(f"related_party_receivable_realization.rows[{index}].fields_invalid")
            continue
        gross = _decimal(row["gross_amount"])
        ecl = _decimal(row["ecl_allowance"])
        collections = _decimal(row["post_position_collections"])
        residual = max(Decimal("0"), gross - ecl - collections)
        if not _numbers_equal(row.get("uncollected_net_exposure"), residual):
            findings.append(
                f"related_party_receivable_realization.rows[{index}].uncollected_net_exposure_mismatch"
            )
        mature_rates: list[Decimal] = []
        for cohort_index, raw_cohort in enumerate(_items(row.get("recovery_cohorts"))):
            cohort = _mapping(raw_cohort)
            cohort_path = (
                f"related_party_receivable_realization.rows[{index}]."
                f"recovery_cohorts[{cohort_index}]"
            )
            numeric_fields = (
                "opening_gross_exposure",
                "opening_ecl_allowance",
                "opening_net_exposure",
                "cash_collections",
                "noncash_settlements",
                "writeoffs",
            )
            if any(not _is_number(cohort.get(field)) for field in numeric_fields):
                findings.append(cohort_path + ".numeric_fields_invalid")
                continue
            if cohort.get("recovery_mechanism_id") != row.get(
                "recovery_mechanism_id"
            ):
                findings.append(cohort_path + ".recovery_mechanism_mismatch")
            cohort_gross = _decimal(cohort["opening_gross_exposure"])
            cohort_ecl = _decimal(cohort["opening_ecl_allowance"])
            cohort_net = max(Decimal("0"), cohort_gross - cohort_ecl)
            if not _numbers_equal(cohort.get("opening_net_exposure"), cohort_net):
                findings.append(cohort_path + ".opening_net_exposure_mismatch")
            try:
                cohort_start = date.fromisoformat(str(cohort.get("period_start") or ""))
                cohort_end = date.fromisoformat(str(cohort.get("period_end") or ""))
                if cohort_start > cohort_end:
                    findings.append(cohort_path + ".period_bounds_reversed")
                if cutoff_at is not None and cohort_end > cutoff_at:
                    findings.append(cohort_path + ".period_end_after_evidence_cutoff")
            except (TypeError, ValueError):
                findings.append(cohort_path + ".period_bounds_invalid")
            expected_rate = (
                min(
                    Decimal("1"),
                    (
                        _decimal(cohort["cash_collections"])
                        + _decimal(cohort["noncash_settlements"])
                    )
                    / cohort_net,
                )
                if cohort.get("maturity_status") == "MATURED" and cohort_net > 0
                else None
            )
            if expected_rate is None:
                if cohort.get("realized_recovery_rate") is not None:
                    findings.append(cohort_path + ".open_rate_must_be_null")
            elif not _numbers_equal(cohort.get("realized_recovery_rate"), expected_rate):
                findings.append(cohort_path + ".realized_recovery_rate_mismatch")
            else:
                mature_rates.append(expected_rate)
        if row.get("mature_cohort_count") != len(mature_rates):
            findings.append(
                f"related_party_receivable_realization.rows[{index}].mature_cohort_count_mismatch"
            )
        observed_recovery = _historical_rate_range(mature_rates, Decimal("1"))
        if not _ranges_equal(
            row.get("historical_observed_recovery_rate_range"), observed_recovery
        ):
            findings.append(
                f"related_party_receivable_realization.rows[{index}].historical_recovery_range_mismatch"
            )
        applicability_status = _validate_applicability_projection(
            row.get("prospective_applicability"),
            kind="related_party_receivable",
            path=(
                f"related_party_receivable_realization.rows[{index}]."
                "prospective_applicability"
            ),
            findings=findings,
        )
        expected_recovery_range = (
            observed_recovery
            if observed_recovery is not None
            and applicability_status == "EVIDENCE_BACKED"
            else None
        )
        if not _ranges_equal(
            row.get("uncollected_recovery_rate_range"), expected_recovery_range
        ):
            findings.append(
                f"related_party_receivable_realization.rows[{index}].prospective_recovery_range_mismatch"
            )
        if residual == 0:
            expected_status = "FULLY_COLLECTED_OR_ALLOWED"
            expected_range = _range(collections, collections, collections)
            expected_unrecognized = Decimal("0")
        elif expected_recovery_range is None:
            expected_status = "UNKNOWN"
            expected_range = _range(collections, collections, collections)
            expected_unrecognized = residual
        else:
            expected_status = "EVIDENCE_BACKED"
            expected_range = _range(
                collections + residual * _decimal(expected_recovery_range["low"]),
                collections + residual * _decimal(expected_recovery_range["base"]),
                collections + residual * _decimal(expected_recovery_range["high"]),
            )
            expected_unrecognized = Decimal("0")
        expected_component_statuses.append(expected_status)
        if row.get("recovery_status") != expected_status:
            findings.append(
                f"related_party_receivable_realization.rows[{index}].recovery_status_mismatch"
            )
        if not _numbers_equal(
            row.get("unrecognized_net_exposure"), expected_unrecognized
        ):
            findings.append(
                f"related_party_receivable_realization.rows[{index}].unrecognized_net_exposure_mismatch"
            )
        if not _ranges_equal(row.get("amount_range"), expected_range):
            findings.append(
                f"related_party_receivable_realization.rows[{index}].amount_range_mismatch"
            )
        if not _numbers_equal(row.get("adopted_value"), expected_range["base"]):
            findings.append(
                f"related_party_receivable_realization.rows[{index}].adopted_value_mismatch"
            )
    for field in (
        "gross_receivables",
        "ecl_allowance",
        "post_position_collections",
        "uncollected_net_exposure",
        "unrecognized_net_exposure",
    ):
        row_field = {
            "gross_receivables": "gross_amount",
            "ecl_allowance": "ecl_allowance",
            "post_position_collections": "post_position_collections",
            "uncollected_net_exposure": "uncollected_net_exposure",
            "unrecognized_net_exposure": "unrecognized_net_exposure",
        }[field]
        expected = sum((_decimal(_mapping(row).get(row_field, 0)) for row in receivable_rows), Decimal("0"))
        if not _numbers_equal(receivable.get(field), expected):
            findings.append("related_party_receivable_realization." + field + "_sum_mismatch")
    for key in ("low", "base", "high"):
        expected = sum(
            (_decimal(_mapping(_mapping(row).get("amount_range")).get(key, 0)) for row in receivable_rows),
            Decimal("0"),
        )
        if not _numbers_equal(_mapping(receivable.get("amount_range")).get(key), expected):
            findings.append(f"related_party_receivable_realization.{key}_sum_mismatch")
    if _is_number(receivable.get("adopted_value")) and _is_number(receivable.get("post_position_collections")):
        if not _numbers_equal(
            receivable["adopted_value"],
            _mapping(receivable.get("amount_range")).get("base"),
        ):
            findings.append("related_party_receivable_realization.adopted_value_mismatch")
    if expected_component_statuses and all(
        status == "FULLY_COLLECTED_OR_ALLOWED"
        for status in expected_component_statuses
    ):
        expected_component_status = "FULLY_COLLECTED_OR_ALLOWED"
    elif expected_component_statuses and all(
        status in {"EVIDENCE_BACKED", "FULLY_COLLECTED_OR_ALLOWED"}
        for status in expected_component_statuses
    ):
        expected_component_status = "EVIDENCE_BACKED"
    elif any(status == "EVIDENCE_BACKED" for status in expected_component_statuses):
        expected_component_status = "PARTIAL_EVIDENCE"
    else:
        expected_component_status = "UNKNOWN"
    if receivable.get("recovery_status") != expected_component_status:
        findings.append("related_party_receivable_realization.recovery_status_mismatch")

    ledger = value.get("valuation_destination_ledger")
    seen_components: set[str] = set()
    seen_destinations: set[str] = set()
    if not isinstance(ledger, list) or len(ledger) != len(COMPONENTS):
        findings.append("valuation_destination_ledger_must_cover_each_component_once")
    else:
        for index, raw in enumerate(ledger):
            entry = _mapping(raw)
            component = entry.get("component_id")
            destination = entry.get("valuation_destination")
            if component not in COMPONENTS:
                findings.append(f"valuation_destination_ledger[{index}].component_id_invalid")
                continue
            if component in seen_components:
                findings.append(f"valuation_destination_ledger[{index}].component_id_reused")
            seen_components.add(component)
            if destination != EXPECTED_DESTINATIONS[component]:
                findings.append(f"valuation_destination_ledger[{index}].valuation_destination_incompatible")
            if destination in seen_destinations:
                findings.append(f"valuation_destination_ledger[{index}].valuation_destination_reused")
            seen_destinations.add(destination)
            component_value = _mapping(value.get(component))
            if destination != component_value.get("valuation_destination"):
                findings.append(f"valuation_destination_ledger[{index}].component_destination_mismatch")
            if entry.get("adopted_value") != component_value.get("adopted_value"):
                findings.append(f"valuation_destination_ledger[{index}].adopted_value_mismatch")
            expected_modes = {
                "legal_cash_accessibility": "BOUND_ONLY",
                "existing_excess_cash_realization": "ADDITIVE_EQUITY_BRIDGE",
                "future_retained_cash_realization": "OPERATING_VALUE_ADJUSTMENT",
                "related_party_receivable_realization": "ADDITIVE_EQUITY_BRIDGE",
            }
            if entry.get("inclusion_mode") != expected_modes[component]:
                findings.append(f"valuation_destination_ledger[{index}].inclusion_mode_invalid")
        if seen_components != set(COMPONENTS):
            findings.append("valuation_destination_ledger_component_coverage_invalid")

    reader_conclusions = value.get("reader_conclusions")
    if not isinstance(reader_conclusions, list) or any(not _text(item) for item in reader_conclusions):
        findings.append("reader_conclusions_invalid")
    else:
        expected = _reader_conclusions_unchecked(value)
        if reader_conclusions != expected:
            findings.append("reader_conclusions_not_deterministic_projection")
        forbidden = ("schema", "VALID", "INVALID", "object_id", "P_LONG", "PRIMARY_ROUTE")
        for index, text in enumerate(reader_conclusions):
            if any(token.lower() in text.lower() for token in forbidden):
                findings.append(f"reader_conclusions[{index}]_contains_internal_language")

    economic_conclusion = value.get("economic_conclusion")
    if not _text(economic_conclusion):
        findings.append("economic_conclusion_invalid")
    elif economic_conclusion != _economic_conclusion_unchecked(value):
        findings.append("economic_conclusion_not_deterministic_projection")

    return _validation(MODEL_VALIDATION_SCHEMA, findings)


def _fmt(value: Any) -> str:
    number = _decimal(value)
    return f"{number:,.2f}"


def _economic_conclusion_unchecked(model: dict[str, Any]) -> str:
    """Project one compact, already-formatted conclusion for deterministic consumers."""
    currency = model.get("currency", "")
    unit = model.get("unit", "")
    legal = _mapping(model.get("legal_cash_accessibility"))
    existing = _mapping(model.get("existing_excess_cash_realization"))
    future = _mapping(model.get("future_retained_cash_realization"))
    receivable = _mapping(model.get("related_party_receivable_realization"))
    return (
        f"截至 {model.get('as_of', '')}，现金法律上限为 {currency} {_fmt(legal.get('adopted_value', 0))} {unit}；"
        f"存量超额现金认可值为 {currency} {_fmt(existing.get('adopted_value', 0))} {unit}，"
        f"未来留存现金认可值为 {currency} {_fmt(future.get('adopted_value', 0))} {unit}，"
        f"关联方应收款当前认可值为 {currency} {_fmt(receivable.get('adopted_value', 0))} {unit}，"
        f"其中尚无依据认可的净敞口为 {currency} {_fmt(receivable.get('unrecognized_net_exposure', 0))} {unit}。"
    )


def _reader_conclusions_unchecked(model: dict[str, Any]) -> list[str]:
    currency = model.get("currency", "")
    unit = model.get("unit", "")
    legal = _mapping(model.get("legal_cash_accessibility"))
    existing = _mapping(model.get("existing_excess_cash_realization"))
    future = _mapping(model.get("future_retained_cash_realization"))
    receivable = _mapping(model.get("related_party_receivable_realization"))
    legal_value = legal.get("adopted_value", 0)
    conclusions = [
        f"扣除受限资金、经营所需流动性、少数股东权益和上划摩擦后，普通股股东可主张的现金法律上限约为 {currency} {_fmt(legal_value)} {unit}；这只是上限，并不等于现金一定会回到股东手中。",
    ]
    if existing.get("realization_rate_range") is not None:
        conclusions.append(
            f"可比期间的特别股息和注销式净回购，加上当前现金控制、上划机制、分配政策和资本需求延续的证据，支持当前认可存量现金约 {currency} {_fmt(existing.get('adopted_value', 0))} {unit}；普通股息没有被拿来证明这笔存量现金已经实现。"
        )
    elif existing.get("qualifying_period_count", 0) >= 3:
        conclusions.append(
            f"历史非常规分配记录可以描述过去，但当前现金控制、上划机制、分配政策或资本需求是否延续仍无充分证据，因此不把历史中位数前推，存量现金当前认可为零；{currency} {_fmt(existing.get('legal_upper_bound', 0))} {unit} 仅保留为法律上限。"
        )
    else:
        conclusions.append(
            f"存量超额现金缺少至少三个可比期间的合格非常规实现记录，因此当前价值采用零；{currency} {_fmt(existing.get('legal_upper_bound', 0))} {unit} 只保留为法律上限，不构成概率区间。"
        )
    if future.get("realization_rate_range") is not None:
        conclusions.append(
            f"普通股息记录及分配政策延续证据只用于估计未来留存现金的分配能力，独立认可约 {currency} {_fmt(future.get('adopted_value', 0))} {unit}，没有与现有现金相加两次。"
        )
    elif future.get("qualifying_period_count", 0) >= 3:
        conclusions.append(
            "历史普通股息可以描述过去，但未来现金控制、普通分配政策或资本需求是否延续仍无充分证据，因此不把历史派息率自动用于未来留存现金。"
        )
    else:
        conclusions.append(
            "未来留存现金的普通分配记录仍不足，当前不认可额外价值，并与已经积累的现金保持分开。"
        )
    if receivable.get("recovery_status") in {"EVIDENCE_BACKED", "PARTIAL_EVIDENCE"}:
        conclusions.append(
            f"关联方应收款继续作为非现金回收资产单列；已收现与同一回收机制下至少三个成熟批次支持当前认可 {currency} {_fmt(receivable.get('adopted_value', 0))} {unit}，账龄标签本身没有被换算成恢复率。"
        )
    else:
        conclusions.append(
            f"关联方应收款继续作为非现金回收资产单列；当前只认可证据截止日前已收回的 {currency} {_fmt(receivable.get('post_position_collections', 0))} {unit}，其余 {currency} {_fmt(receivable.get('unrecognized_net_exposure', 0))} {unit} 保持未知，账龄标签本身不产生恢复率。"
        )
    return conclusions


def project_reader_conclusions(model: Any) -> list[str]:
    """Return investor-language conclusions without model or audit vocabulary."""
    validation = validate_cash_accessibility_model(model)
    if validation["state"] != "VALID":
        raise ValueError("cash_accessibility_model_invalid:" + ",".join(validation["findings"]))
    return deepcopy(_reader_conclusions_unchecked(_mapping(model)))


__all__ = [
    "validate_cash_accessibility_input",
    "compute_cash_accessibility_model",
    "compile_cash_accessibility_model",
    "validate_cash_accessibility_model",
    "project_reader_conclusions",
]
