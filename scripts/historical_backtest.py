#!/usr/bin/env python3
"""Validation primitives for the Phase 10 point-in-time backtest pilot.

This module intentionally does not run stock models or tune prices.  It makes
the experiment boundary executable: a frozen report can only use admissible
historical vintages, and later settlement must keep report coverage, model
error and investment outcome as separate ledgers.
"""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_SCHEMA_VERSION = "historical-backtest-experiment.v1"
CASE_SCHEMA_VERSION = "historical-backtest-case.v1"
SETTLEMENT_SCHEMA_VERSION = "historical-backtest-settlement.v1"

ROUTES = {"LONG_TERM_OWNER", "FINITE_XIRR", "DUAL"}
PRIMARY_PRICE_IDENTITIES = {"P_LONG", "P_XIRR", "P_LEGAL", "P_BUSINESS_VALUE_EXIT", "UNKNOWN"}
INVESTMENT_ACTIONS = {"BUY", "HOLD", "WAIT", "SELL", "NO_BUY", "UNKNOWN"}
FILL_STATUSES = {"FILLED", "PARTIALLY_FILLED", "NOT_FILLED", "NOT_APPLICABLE"}
EXIT_STATUSES = {"EXITED", "MARKED_TO_MARKET", "OPEN", "NOT_APPLICABLE"}
RETURN_CASH_FLOW_TYPES = {
    "ENTRY", "EXIT", "MARK_TO_MARKET", "DIVIDEND", "CORPORATE_ACTION_CASH", "CASH_ALTERNATIVE",
}
CORPORATE_ACTION_TYPES = {
    "CASH_DIVIDEND", "STOCK_SPLIT", "RIGHTS_ISSUE", "MERGER", "DELISTING", "SPINOFF", "OTHER",
}
PREDICTION_SETTLEMENT_STATUSES = {"CALCULATED", "PARTIAL", "NOT_CALCULABLE"}
UNKNOWN_SETTLEMENT_STATUSES = {
    "UNRESOLVED_AS_OF_SETTLEMENT", "PARTIALLY_RESOLVED", "RESOLVED_MATERIAL", "RESOLVED_IMMATERIAL",
}
OPERATING_COMPARABILITY_STATUSES = {
    "COMPARABLE", "CONVERTIBLE_WITH_PREREGISTERED_RULE", "PERIOD_MISMATCH",
    "SCOPE_OR_ACCOUNTING_DRIFT", "NOT_COMPARABLE", "NOT_DISCLOSED",
}
COMPARABLE_OPERATING_STATUSES = {"COMPARABLE", "CONVERTIBLE_WITH_PREREGISTERED_RULE"}
PIT_TIMEZONE = timezone(timedelta(hours=8))
OFFICIAL_SETTLEMENT_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT", "OFFICIAL_STATISTICS",
    "OFFICIAL_MARKET_DATA", "OTHER_OFFICIAL",
}
OPERATING_OBSERVATION_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT",
}
LEAKAGE_FIELDS = {
    "actual", "actual_value", "actual_outcome", "actual_outcomes", "outcome", "outcomes", "settlement",
    "settled_at", "future_price", "future_return", "realized_return", "benchmark_return",
}

PILOT_CASES = (
    ("87001.HK", "汇贤产业信托"),
    ("900936.SH", "鄂尔多斯B"),
    ("000651.SZ", "格力电器"),
    ("01522.HK", "京投交通科技"),
    ("02669.HK", "中海物业"),
    ("00506.HK", "中国食品"),
    ("00882.HK", "天津发展"),
    ("600585.SH", "海螺水泥"),
    ("601899.SH", "紫金矿业"),
)


def _date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _timestamp(value: Any, *, date_only_at_end: bool = False) -> datetime | None:
    """Parse a point-in-time value without silently discarding its clock time.

    Historical source indexes sometimes expose only a calendar day.  Treating
    that day as its end is conservative when deciding whether a source was
    available by a cutoff; execution events instead use the start of a
    date-only day, so they cannot be assumed to occur after an intraday cutoff.
    """
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 10:
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            return None
        clock_time = time.max if date_only_at_end else time.min
        return datetime.combine(parsed_date, clock_time, tzinfo=PIT_TIMEZONE)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_date_only(value: Any) -> bool:
    text = str(value or "").strip()
    return len(text) == 10 and _date(text) is not None


def _required(record: dict[str, Any], fields: Iterable[str], prefix: str) -> list[str]:
    return [f"{prefix}:missing:{field}" for field in fields if record.get(field) in (None, "", [], {})]


def _number(value: Any) -> float | None:
    """Return a finite numeric value without accepting bools as money."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _numbers_match(left: Any, right: Any) -> bool:
    lhs = _number(left)
    rhs = _number(right)
    return lhs is not None and rhs is not None and math.isclose(lhs, rhs, rel_tol=1e-9, abs_tol=1e-9)


def _nested_forbidden(value: Any, *, path: str = "") -> list[str]:
    """Find hindsight keys in model inputs without treating prose as evidence."""
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{path}.{key}" if path else str(key)
            if normalized in LEAKAGE_FIELDS:
                findings.append(f"future_field_in_frozen_input:{child_path}")
            findings.extend(_nested_forbidden(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_nested_forbidden(child, path=f"{path}[{index}]"))
    return findings


def validate_experiment(record: dict[str, Any]) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if record.get("schema_version") != EXPERIMENT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(record.get("experiment_id") or "").startswith("HBT:"):
        invalid.append("experiment_id_invalid")
    framework = record.get("framework") if isinstance(record.get("framework"), dict) else {}
    if framework.get("golden_gate_state") != "G3_NOT_READY":
        invalid.append("golden_gate_must_remain_g3_not_ready")
    policy = record.get("information_policy") if isinstance(record.get("information_policy"), dict) else {}
    expected_policy = {
        "source_rule": "published_at_and_data_as_of_must_not_exceed_cutoff",
        "current_restated_data_rule": "current_restated_values_are_ineligible_without_historical_vintage",
        "future_file_rule": "future_files_are_unreadable_before_settlement",
        "survivorship_rule": "retain_delisted_acquired_and_failed_cases_in_registered_universe",
    }
    for field, expected in expected_policy.items():
        if policy.get(field) != expected:
            invalid.append(f"information_policy:{field}_invalid")
    scoring = record.get("scoring_policy") if isinstance(record.get("scoring_policy"), dict) else {}
    if scoring.get("separate_dimensions") != ["REPORT_COVERAGE", "MODEL_FORECAST_ERROR", "INVESTMENT_RETURN_OUTCOME"]:
        invalid.append("scoring_dimensions_must_remain_separate")
    if scoring.get("no_compensating_score") is not True:
        invalid.append("compensating_score_forbidden")
    universe = record.get("universe") if isinstance(record.get("universe"), dict) else {}
    cases = universe.get("cases") if isinstance(universe.get("cases"), list) else []
    if not cases:
        incomplete.append("universe_cases_missing")
    eligible = [item for item in cases if isinstance(item, dict) and item.get("eligibility_status") == "ELIGIBLE"]
    if universe.get("eligible_case_count") != len(eligible):
        invalid.append("eligible_case_count_mismatch")
    ids: set[str] = set()
    for index, item in enumerate(cases):
        prefix = f"universe.cases[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        case_id = str(item.get("case_id") or "")
        if not case_id.startswith("HBTCASE:"):
            invalid.append(prefix + ":case_id_invalid")
        if case_id in ids:
            invalid.append(prefix + ":duplicate_case_id")
        ids.add(case_id)
        if not str(item.get("eligibility_reason") or "").strip():
            incomplete.append(prefix + ":eligibility_reason_missing")
        if item.get("eligibility_status") == "ELIGIBLE" and not item.get("route"):
            incomplete.append(prefix + ":eligible_route_missing")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def _validate_source(source: dict[str, Any], cutoff: datetime, index: int) -> tuple[list[str], list[str]]:
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = f"sources[{index}]"
    published = _timestamp(source.get("published_at"), date_only_at_end=True)
    data_as_of = _date(source.get("data_as_of"))
    revision = _timestamp(source.get("revision_published_at"), date_only_at_end=True) if source.get("revision_published_at") else None
    if published is None or data_as_of is None:
        incomplete.append(prefix + ":published_at_or_data_as_of_missing")
    else:
        if _is_date_only(source.get("published_at")) and published.astimezone(PIT_TIMEZONE).date() == cutoff.astimezone(PIT_TIMEZONE).date():
            incomplete.append(prefix + ":published_at_time_required_on_cutoff_date")
        if published > cutoff:
            invalid.append(prefix + ":future_published_at")
        if data_as_of > cutoff.date():
            invalid.append(prefix + ":future_data_as_of")
    if revision and revision > cutoff:
        invalid.append(prefix + ":future_revision")
    if source.get("revision_policy") == "CURRENT_RESTATED_ONLY":
        invalid.append(prefix + ":current_restated_data_not_admissible")
    if not str(source.get("source_version") or "").strip():
        incomplete.append(prefix + ":source_version_missing")
    if source.get("admissible") is not True:
        invalid.append(prefix + ":source_not_admissible")
    return invalid, incomplete


def _validate_source_references(
    references: Any, known_source_ids: set[str], prefix: str,
) -> tuple[list[str], list[str]]:
    """Require ledger links to resolve to the frozen source manifest."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(references, list) or not references:
        incomplete.append(prefix + ":source_ids_missing")
        return invalid, incomplete
    for source_id in references:
        source_id = str(source_id or "")
        if not source_id:
            incomplete.append(prefix + ":source_id_empty")
        elif source_id not in known_source_ids:
            invalid.append(prefix + ":source_id_not_found:" + source_id)
    return invalid, incomplete


def _validate_calibration_ledger(
    record: dict[str, Any], known_source_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Validate the frozen, claim-level calibration contract for a case."""
    invalid: list[str] = []
    incomplete: list[str] = []
    ledger = record.get("calibration_ledger") if isinstance(record.get("calibration_ledger"), dict) else {}
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    if not claims:
        incomplete.append("calibration_ledger:claims_missing")
        return invalid, incomplete
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        prefix = f"calibration_ledger.claims[{index}]"
        if not isinstance(claim, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(
            claim,
            (
                "claim_id", "statement", "materiality", "frozen_disposition", "source_ids", "counter_thesis",
                "flip_condition", "observable_outcome",
            ),
            prefix,
        ))
        for field in ("prediction", "threshold", "unknown"):
            if field not in claim:
                incomplete.append(prefix + ":missing:" + field)
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id.startswith("HBTCLM:"):
            invalid.append(prefix + ":claim_id_invalid")
        elif claim_id in claim_ids:
            invalid.append("duplicate_calibration_claim_id:" + claim_id)
        claim_ids.add(claim_id)
        if claim.get("materiality") not in {"CENTRAL_THESIS", "VALUATION", "RETURN", "PERMANENT_LOSS"}:
            invalid.append(prefix + ":materiality_invalid")
        disposition = claim.get("frozen_disposition")
        if disposition not in {"PREDICTION", "UNKNOWN"}:
            invalid.append(prefix + ":frozen_disposition_invalid")
        ref_invalid, ref_incomplete = _validate_source_references(claim.get("source_ids"), known_source_ids, prefix)
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
        outcome_prefix = prefix + ".observable_outcome"
        incomplete.extend(_required(
            outcome,
            (
                "metric", "unit", "measurement_basis", "measurement_rule", "period_start", "period_end",
                "allowed_source_types", "settlement_version_policy",
            ),
            outcome_prefix,
        ))
        period_start = _date(outcome.get("period_start"))
        period_end = _date(outcome.get("period_end"))
        if outcome.get("period_start") not in (None, "") and period_start is None:
            invalid.append(outcome_prefix + ":period_start_invalid")
        if outcome.get("period_end") not in (None, "") and period_end is None:
            invalid.append(outcome_prefix + ":period_end_invalid")
        if period_start and period_end and period_start > period_end:
            invalid.append(outcome_prefix + ":period_start_after_period_end")
        allowed_source_types = outcome.get("allowed_source_types")
        if isinstance(allowed_source_types, list):
            for source_type in allowed_source_types:
                if source_type not in OPERATING_OBSERVATION_SOURCE_TYPES:
                    invalid.append(outcome_prefix + ":allowed_source_type_invalid:" + str(source_type))
        elif allowed_source_types not in (None, ""):
            invalid.append(outcome_prefix + ":allowed_source_types_not_list")
        if outcome.get("settlement_version_policy") not in {
            "INITIAL_DISCLOSURE", "LATEST_OFFICIAL_AS_OF_EVALUATION",
        }:
            invalid.append(outcome_prefix + ":settlement_version_policy_invalid")
        if disposition == "PREDICTION":
            prediction = claim.get("prediction") if isinstance(claim.get("prediction"), dict) else {}
            threshold = claim.get("threshold") if isinstance(claim.get("threshold"), dict) else {}
            incomplete.extend(_required(prediction, ("metric", "operator", "value", "unit", "horizon"), prefix + ".prediction"))
            incomplete.extend(_required(threshold, ("metric", "operator", "value", "unit", "consequence"), prefix + ".threshold"))
            for field in ("metric", "unit"):
                if prediction.get(field) != outcome.get(field):
                    invalid.append(prefix + ".prediction:" + field + "_does_not_match_observable_outcome")
                if threshold.get(field) != outcome.get(field):
                    invalid.append(prefix + ".threshold:" + field + "_does_not_match_observable_outcome")
            if claim.get("unknown") is not None:
                invalid.append(prefix + ":prediction_cannot_carry_unknown_payload")
        elif disposition == "UNKNOWN":
            unknown = claim.get("unknown") if isinstance(claim.get("unknown"), dict) else {}
            incomplete.extend(_required(unknown, ("statement", "economic_impact", "resolution_observation"), prefix + ".unknown"))
            if claim.get("prediction") is not None or claim.get("threshold") is not None:
                invalid.append(prefix + ":unknown_cannot_carry_quantitative_prediction")
    return invalid, incomplete


def _frozen_predictions(case: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(case, dict):
        return {}
    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    return {
        str(claim.get("claim_id")): claim
        for claim in claims
        if isinstance(claim, dict) and isinstance(claim.get("prediction"), dict)
    }


def _frozen_claims(case: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(case, dict):
        return {}
    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    return {
        str(claim.get("claim_id")): claim
        for claim in claims
        if isinstance(claim, dict) and str(claim.get("claim_id") or "")
    }


def _route_findings(record: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    route = record.get("route")
    forecast = record.get("forecast") if isinstance(record.get("forecast"), dict) else {}
    price = record.get("price_identity") if isinstance(record.get("price_identity"), dict) else {}
    primary_route = price.get("primary_route")
    primary_price = price.get("primary_price_identity")
    if route not in ROUTES:
        findings.append("route_invalid")
        return findings
    horizon = forecast.get("horizon_years")
    if not isinstance(horizon, (int, float)) or horizon < 0:
        findings.append("forecast_horizon_invalid")
    if route in {"FINITE_XIRR", "DUAL"} and (not isinstance(horizon, (int, float)) or horizon <= 0):
        findings.append("finite_route_requires_positive_horizon")
    if route == "LONG_TERM_OWNER":
        if primary_route != "LONG_TERM_OWNER" or primary_price != "P_LONG":
            findings.append("long_term_route_requires_p_long_primary")
        if forecast.get("terminal_handling") not in {"NO_REQUIRED_EXIT", "DUAL_TERMINAL_PATH"}:
            findings.append("long_term_route_terminal_handling_invalid")
    elif route == "FINITE_XIRR":
        if primary_route != "FINITE_XIRR" or primary_price not in {"P_XIRR", "P_LEGAL", "P_BUSINESS_VALUE_EXIT"}:
            findings.append("finite_route_requires_finite_price_primary")
        if forecast.get("terminal_handling") not in {"BUSINESS_VALUE_EXIT", "MARKET_EXIT", "LEGAL_END"}:
            findings.append("finite_route_terminal_handling_invalid")
    else:
        if primary_route not in {"DUAL", "PRIMARY_ROUTE_UNKNOWN"}:
            findings.append("dual_route_primary_route_invalid")
        if primary_route == "PRIMARY_ROUTE_UNKNOWN" and primary_price != "UNKNOWN":
            findings.append("unknown_primary_route_requires_unknown_price")
        if forecast.get("terminal_handling") != "DUAL_TERMINAL_PATH":
            findings.append("dual_route_requires_dual_terminal_path")
    if primary_price == "P_XIRR" and forecast.get("terminal_handling") == "MARKET_EXIT" and forecast.get("independent_terminal_evidence") is not True:
        findings.append("fixed_market_terminal_price_cannot_be_primary_without_independent_evidence")
    return findings


def _frozen_price(case: dict[str, Any], identity: str) -> dict[str, Any] | None:
    price_identity = case.get("price_identity") if isinstance(case.get("price_identity"), dict) else {}
    prices = price_identity.get("prices") if isinstance(price_identity.get("prices"), list) else []
    return next(
        (price for price in prices if isinstance(price, dict) and price.get("identity") == identity),
        None,
    )


def _validate_investment_decision(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Validate the action and price identity frozen with the report.

    The field is optional for legacy frozen cases, but a settlement that claims
    an investment outcome must bind to it.  This keeps old calibration-only
    records readable while refusing to manufacture a return from them.
    """
    decision = record.get("investment_decision")
    if decision is None:
        return [], []
    if not isinstance(decision, dict):
        return ["investment_decision:not_object"], []
    invalid: list[str] = []
    incomplete = _required(decision, ("action", "price_identity", "execution_rule"), "investment_decision")
    action = decision.get("action")
    identity = str(decision.get("price_identity") or "")
    if action not in INVESTMENT_ACTIONS:
        invalid.append("investment_decision:action_invalid")
    if identity not in PRIMARY_PRICE_IDENTITIES:
        invalid.append("investment_decision:price_identity_invalid")
    elif identity == "UNKNOWN":
        if action not in {"NO_BUY", "UNKNOWN"}:
            invalid.append("investment_decision:unknown_price_identity_requires_no_buy_or_unknown_action")
    elif _frozen_price(record, identity) is None:
        invalid.append("investment_decision:price_identity_not_registered_in_frozen_case")
    return invalid, incomplete


def validate_case(record: dict[str, Any]) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if record.get("schema_version") != CASE_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    invalid.extend(_nested_forbidden(record.get("inputs", []), path="inputs"))
    invalid.extend(_nested_forbidden(record.get("calibration_ledger", {}), path="calibration_ledger"))
    simulation_cutoff = _timestamp(record.get("simulation_cutoff"))
    if simulation_cutoff is None:
        invalid.append("simulation_cutoff_invalid")
        simulation_cutoff = datetime.min.replace(tzinfo=timezone.utc)
    report_freeze = record.get("report_freeze") if isinstance(record.get("report_freeze"), dict) else {}
    if report_freeze.get("settlement_locked") is not True:
        invalid.append("settlement_must_be_locked_at_report_freeze")
    freeze_date = _timestamp(report_freeze.get("frozen_at"))
    evidence_cutoff = _timestamp(report_freeze.get("evidence_cutoff"))
    if freeze_date is None or evidence_cutoff is None:
        incomplete.append("report_freeze_dates_missing")
    elif evidence_cutoff > simulation_cutoff:
        invalid.append("evidence_cutoff_after_simulation_cutoff")
    elif freeze_date < evidence_cutoff:
        invalid.append("report_freeze_before_evidence_cutoff")
    sources = record.get("sources") if isinstance(record.get("sources"), list) else []
    if not sources:
        incomplete.append("sources_missing")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            invalid.append(f"sources[{index}]:not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if source_id in source_ids:
            invalid.append("duplicate_source_id:" + source_id)
        source_ids.add(source_id)
        current_invalid, current_incomplete = _validate_source(source, simulation_cutoff, index)
        invalid.extend(current_invalid)
        incomplete.extend(current_incomplete)
    for index, item in enumerate(record.get("inputs") or []):
        if not isinstance(item, dict):
            invalid.append(f"inputs[{index}]:not_object")
            continue
        missing = _required(item, ("name", "input_role", "source_ids"), f"inputs[{index}]")
        incomplete.extend(missing)
        if item.get("input_role") == "HISTORICAL_FACT" and not item.get("source_ids"):
            incomplete.append(f"inputs[{index}]:historical_fact_source_missing")
        ref_invalid, ref_incomplete = _validate_source_references(
            item.get("source_ids"), source_ids, f"inputs[{index}]",
        )
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
    ledger_invalid, ledger_incomplete = _validate_calibration_ledger(record, source_ids)
    invalid.extend(ledger_invalid)
    incomplete.extend(ledger_incomplete)
    decision_invalid, decision_incomplete = _validate_investment_decision(record)
    invalid.extend(decision_invalid)
    incomplete.extend(decision_incomplete)
    taxes = record.get("taxes_fees_fx") if isinstance(record.get("taxes_fees_fx"), dict) else {}
    incomplete.extend(_required(taxes, ("tax_rate", "transaction_fee_rate", "dividend_tax_rate", "base_currency", "fx_rule"), "taxes_fees_fx"))
    invalid.extend(_route_findings(record))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": list(dict.fromkeys(invalid)), "incomplete_findings": list(dict.fromkeys(incomplete))}


def _validate_actual_sources(
    record: dict[str, Any], *, cutoff: datetime | None, settlement_date: datetime | None,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Check that settlement facts have their own later official evidence."""
    sources_by_id: dict[str, dict[str, Any]] = {}
    invalid: list[str] = []
    incomplete: list[str] = []
    sources = record.get("actual_sources") if isinstance(record.get("actual_sources"), list) else []
    if not sources:
        incomplete.append("actual_sources_missing")
        return sources_by_id, invalid, incomplete
    for index, source in enumerate(sources):
        prefix = f"actual_sources[{index}]"
        if not isinstance(source, dict):
            invalid.append(prefix + ":not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id:
            incomplete.append(prefix + ":source_id_missing")
        elif source_id in sources_by_id:
            invalid.append("duplicate_actual_source_id:" + source_id)
        if source_id:
            sources_by_id[source_id] = source
        incomplete.extend(_required(source, ("source_type", "official", "published_at", "source_version"), prefix))
        if source.get("official") is not True:
            invalid.append(prefix + ":official_source_required")
        if source.get("source_type") not in OFFICIAL_SETTLEMENT_SOURCE_TYPES:
            invalid.append(prefix + ":official_source_type_invalid")
        published = _timestamp(source.get("published_at"), date_only_at_end=True)
        if published is None:
            incomplete.append(prefix + ":published_at_invalid")
        else:
            if cutoff and _is_date_only(source.get("published_at")) and published.astimezone(PIT_TIMEZONE).date() == cutoff.astimezone(PIT_TIMEZONE).date():
                incomplete.append(prefix + ":published_at_time_required_on_cutoff_date")
            if cutoff and published <= cutoff:
                invalid.append(prefix + ":published_at_must_follow_report_cutoff")
            if settlement_date and published > settlement_date:
                invalid.append(prefix + ":published_at_after_settlement")
        data_as_of = source.get("data_as_of")
        if data_as_of is not None:
            observed_date = _date(data_as_of)
            if observed_date is None:
                incomplete.append(prefix + ":data_as_of_invalid")
            elif settlement_date and observed_date > settlement_date.date():
                invalid.append(prefix + ":data_as_of_after_settlement")
    return sources_by_id, invalid, incomplete


def _validate_operating_observation(
    observation: dict[str, Any], *, prefix: str, frozen_claims: dict[str, dict[str, Any]],
    actual_sources: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Bind an observed operating result to the frozen metric, basis, period and source contract."""
    invalid: list[str] = []
    incomplete: list[str] = []
    claim_id = str(observation.get("claim_id") or "")
    claim = frozen_claims.get(claim_id)
    if claim is None:
        invalid.append(prefix + ":claim_id_not_frozen:" + claim_id)
        return invalid, incomplete
    outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
    if observation.get("comparability_status") not in OPERATING_COMPARABILITY_STATUSES:
        invalid.append(prefix + ":comparability_status_invalid")
    for field in ("metric", "unit", "measurement_basis", "period_start", "period_end"):
        if observation.get(field) != outcome.get(field):
            invalid.append(prefix + ":" + field + "_does_not_match_frozen_contract")
    allowed_source_types = outcome.get("allowed_source_types")
    if not isinstance(allowed_source_types, list) or not allowed_source_types:
        return invalid, incomplete
    for source_id in observation.get("source_ids") or []:
        source = actual_sources.get(str(source_id or ""))
        if source is None:
            continue
        source_type = source.get("source_type")
        if source_type not in allowed_source_types:
            invalid.append(prefix + ":source_type_not_allowed_for_frozen_contract:" + str(source_id))
        if source_type in {"ANNUAL_REPORT", "INTERIM_REPORT"}:
            source_period_end = _date(source.get("data_as_of"))
            observation_period_end = _date(observation.get("period_end"))
            if source_period_end is None:
                incomplete.append(prefix + ":report_source_data_as_of_missing:" + str(source_id))
            elif observation_period_end and source_period_end != observation_period_end:
                invalid.append(prefix + ":report_source_period_does_not_match_observation:" + str(source_id))
    return invalid, incomplete


def _observation_visible_at(
    observation: dict[str, Any], actual_sources: dict[str, dict[str, Any]],
) -> datetime | None:
    publication_times = [
        _timestamp(actual_sources[source_id].get("published_at"), date_only_at_end=True)
        for source_id in observation.get("source_ids") or []
        if source_id in actual_sources
    ]
    if not publication_times or any(item is None for item in publication_times):
        return None
    return max(item for item in publication_times if item is not None)


def _validate_operating_source_timeline(
    record: dict[str, Any], *, actual_sources: dict[str, dict[str, Any]],
    observations: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Require an explicit, auditable enumeration before selecting an actual."""
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = "operating_source_timeline"
    timeline = record.get(prefix) if isinstance(record.get(prefix), dict) else {}
    incomplete.extend(_required(timeline, ("enumeration_status", "source_ids"), prefix))
    status = timeline.get("enumeration_status")
    if status not in {"COMPLETE", "INCOMPLETE"}:
        invalid.append(prefix + ":enumeration_status_invalid")
    elif status == "INCOMPLETE":
        incomplete.append(prefix + ":enumeration_incomplete")
    timeline_source_ids = [str(item) for item in timeline.get("source_ids") or []]
    ref_invalid, ref_incomplete = _validate_source_references(
        timeline_source_ids, set(actual_sources), prefix,
    )
    invalid.extend(ref_invalid)
    incomplete.extend(ref_incomplete)
    operating_source_ids = {
        source_id for source_id, source in actual_sources.items()
        if source.get("source_type") in OPERATING_OBSERVATION_SOURCE_TYPES
    }
    if set(timeline_source_ids) != operating_source_ids:
        invalid.append(prefix + ":source_ids_do_not_match_enumerated_operating_sources")
    for observation_id, observation in observations.items():
        for source_id in observation.get("source_ids") or []:
            if source_id not in timeline_source_ids:
                invalid.append(prefix + ":observation_source_not_enumerated:" + observation_id + ":" + str(source_id))
    return invalid, incomplete


def _validate_claim_settlements(
    model_error: dict[str, Any], *, frozen_claims: dict[str, dict[str, Any]],
    observations: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Every frozen prediction and UNKNOWN needs an explicit settlement state."""
    statuses: dict[str, dict[str, Any]] = {}
    invalid: list[str] = []
    incomplete: list[str] = []
    entries = model_error.get("claim_settlements") if isinstance(model_error.get("claim_settlements"), list) else []
    if not entries:
        incomplete.append("model_forecast_error:claim_settlements_missing")
        return statuses, invalid, incomplete
    for index, entry in enumerate(entries):
        prefix = f"model_forecast_error.claim_settlements[{index}]"
        if not isinstance(entry, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(entry, ("claim_id", "frozen_disposition", "status"), prefix))
        if "observation_ids" not in entry or not isinstance(entry.get("observation_ids"), list):
            incomplete.append(prefix + ":missing:observation_ids")
        claim_id = str(entry.get("claim_id") or "")
        frozen = frozen_claims.get(claim_id)
        if frozen is None:
            invalid.append(prefix + ":claim_id_not_frozen:" + claim_id)
            continue
        if claim_id in statuses:
            invalid.append("duplicate_claim_settlement:" + claim_id)
            continue
        statuses[claim_id] = entry
        disposition = frozen.get("frozen_disposition")
        if entry.get("frozen_disposition") != disposition:
            invalid.append(prefix + ":frozen_disposition_does_not_match_case")
        allowed_statuses = (
            PREDICTION_SETTLEMENT_STATUSES
            if disposition == "PREDICTION"
            else UNKNOWN_SETTLEMENT_STATUSES
        )
        status = entry.get("status")
        if status not in allowed_statuses:
            invalid.append(prefix + ":status_invalid_for_frozen_disposition")
        observation_ids = entry.get("observation_ids") if isinstance(entry.get("observation_ids"), list) else []
        if disposition == "PREDICTION" and status == "CALCULATED" and not observation_ids:
            incomplete.append(prefix + ":calculated_prediction_requires_observation")
        if disposition == "UNKNOWN":
            if status == "UNRESOLVED_AS_OF_SETTLEMENT" and observation_ids:
                invalid.append(prefix + ":unresolved_unknown_cannot_reference_observation")
            elif status in UNKNOWN_SETTLEMENT_STATUSES - {"UNRESOLVED_AS_OF_SETTLEMENT"} and not observation_ids:
                incomplete.append(prefix + ":resolved_unknown_requires_observation")
        for observation_id in observation_ids:
            observation_id = str(observation_id or "")
            observation = observations.get(observation_id)
            if observation is None:
                invalid.append(prefix + ":observation_id_not_found:" + observation_id)
            elif observation.get("claim_id") != claim_id:
                invalid.append(prefix + ":observation_claim_id_mismatch:" + observation_id)
    for claim_id in frozen_claims:
        if claim_id not in statuses:
            incomplete.append("model_forecast_error.claim_settlements:missing_frozen_claim:" + claim_id)
    return statuses, invalid, incomplete


def _validate_metric_version_policy(
    metric: dict[str, Any], observation: dict[str, Any], *, frozen_claim: dict[str, Any],
    observations: dict[str, dict[str, Any]], actual_sources: dict[str, dict[str, Any]], prefix: str,
) -> list[str]:
    """Select the pre-registered first or latest comparable disclosure, never a convenient revision."""
    outcome = frozen_claim.get("observable_outcome") if isinstance(frozen_claim.get("observable_outcome"), dict) else {}
    policy = outcome.get("settlement_version_policy")
    candidates = [
        item for item in observations.values()
        if item.get("claim_id") == observation.get("claim_id")
        and item.get("metric") == observation.get("metric")
        and item.get("unit") == observation.get("unit")
        and item.get("measurement_basis") == observation.get("measurement_basis")
        and item.get("period_start") == observation.get("period_start")
        and item.get("period_end") == observation.get("period_end")
        and item.get("comparability_status") in COMPARABLE_OPERATING_STATUSES
    ]
    dated_candidates = [
        (item, _observation_visible_at(item, actual_sources)) for item in candidates
    ]
    dated_candidates = [(item, visible_at) for item, visible_at in dated_candidates if visible_at is not None]
    selected_at = _observation_visible_at(observation, actual_sources)
    if not dated_candidates or selected_at is None:
        return [prefix + ":observation_publication_timeline_incomplete"]
    required_at = (
        min(visible_at for _, visible_at in dated_candidates)
        if policy == "INITIAL_DISCLOSURE"
        else max(visible_at for _, visible_at in dated_candidates)
    )
    if selected_at != required_at:
        required = "initial" if policy == "INITIAL_DISCLOSURE" else "latest"
        return [prefix + ":does_not_use_" + required + "_disclosure_per_frozen_policy"]
    return []


def _validate_return_outcome(
    outcome: dict[str, Any],
    *,
    case: dict[str, Any] | None,
    actual_source_ids: set[str],
    actual_sources: dict[str, dict[str, Any]],
    cutoff: datetime | None,
    settlement_date: datetime | None,
) -> tuple[list[str], list[str]]:
    """Validate the small, replayable investment-return ledger.

    This deliberately models one position entry and one exit/mark.  It is
    enough to catch action/price swaps and arithmetic tampering without
    pretending to be a portfolio or order-management system.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    return_statuses = {"CALCULATED", "PARTIAL", "NOT_CALCULABLE"}
    status = outcome.get("status")
    action = outcome.get("action")
    if status not in return_statuses:
        invalid.append("investment_return_outcome:status_invalid")
    if action not in INVESTMENT_ACTIONS:
        invalid.append("investment_return_outcome:action_invalid")

    decision = case.get("investment_decision") if isinstance(case, dict) else None
    if not isinstance(decision, dict):
        invalid.append("frozen_investment_decision_required_for_return_settlement")
    else:
        expected_action = decision.get("action")
        expected_identity = decision.get("price_identity")
        expected_rule = decision.get("execution_rule")
        if action != expected_action:
            invalid.append("investment_return_outcome:action_does_not_match_frozen_action")
        if outcome.get("frozen_action") != expected_action:
            invalid.append("investment_return_outcome:frozen_action_does_not_match_case")
        if outcome.get("frozen_price_identity") != expected_identity:
            invalid.append("investment_return_outcome:frozen_price_identity_does_not_match_case")
        selected_price = _frozen_price(case, str(expected_identity or ""))
        if expected_identity != "UNKNOWN" and selected_price is None:
            invalid.append("investment_return_outcome:price_identity_not_registered_in_case")

    policy = outcome.get("taxes_fees_fx")
    if not isinstance(policy, dict):
        incomplete.append("investment_return_outcome:taxes_fees_fx_missing")
    elif isinstance(case, dict):
        frozen_policy = case.get("taxes_fees_fx") if isinstance(case.get("taxes_fees_fx"), dict) else {}
        for field in ("tax_rate", "transaction_fee_rate", "dividend_tax_rate", "base_currency", "fx_rule"):
            if field not in policy:
                incomplete.append(f"investment_return_outcome.taxes_fees_fx:missing:{field}")
            elif policy.get(field) != frozen_policy.get(field) and not (
                field in {"tax_rate", "transaction_fee_rate", "dividend_tax_rate"}
                and _numbers_match(policy.get(field), frozen_policy.get(field))
            ):
                invalid.append(f"investment_return_outcome.taxes_fees_fx:{field}_does_not_match_frozen_case")

    benchmark = outcome.get("benchmark_identity")
    benchmark_source_ids: set[str] = set()
    if not isinstance(benchmark, dict):
        incomplete.append("investment_return_outcome:benchmark_identity_missing")
    else:
        incomplete.extend(_required(
            benchmark,
            ("benchmark_id", "market", "currency", "return_basis", "calculation_rule", "source_ids"),
            "investment_return_outcome.benchmark_identity",
        ))
        benchmark_source_ids = set(str(item) for item in benchmark.get("source_ids") or [])
        ref_invalid, ref_incomplete = _validate_source_references(
            benchmark.get("source_ids"), actual_source_ids, "investment_return_outcome.benchmark_identity",
        )
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        if benchmark_source_ids and not any(
            actual_sources.get(source_id, {}).get("source_type") == "OFFICIAL_MARKET_DATA"
            for source_id in benchmark_source_ids
        ):
            invalid.append("investment_return_outcome.benchmark_identity:official_market_data_source_required")

    execution = outcome.get("execution")
    if not isinstance(execution, dict):
        incomplete.append("investment_return_outcome:execution_missing")
        execution = {}
    incomplete.extend(_required(
        execution, ("execution_rule", "fill_status", "entry", "exit"),
        "investment_return_outcome.execution",
    ))
    if isinstance(decision, dict) and execution.get("execution_rule") != decision.get("execution_rule"):
        invalid.append("investment_return_outcome.execution:rule_does_not_match_frozen_action")
    fill_status = execution.get("fill_status")
    if fill_status not in FILL_STATUSES:
        invalid.append("investment_return_outcome.execution:fill_status_invalid")
    entry = execution.get("entry") if isinstance(execution.get("entry"), dict) else {}
    exit_leg = execution.get("exit") if isinstance(execution.get("exit"), dict) else {}
    leg_fields = ("date", "price", "quantity", "currency", "source_ids")
    for leg, prefix in ((entry, "investment_return_outcome.execution.entry"), (exit_leg, "investment_return_outcome.execution.exit")):
        incomplete.extend(prefix + ":missing:" + field for field in leg_fields if field not in leg)
        if leg.get("source_ids"):
            ref_invalid, ref_incomplete = _validate_source_references(leg.get("source_ids"), actual_source_ids, prefix)
            invalid.extend(ref_invalid)
            incomplete.extend(ref_incomplete)
        leg_date = _timestamp(leg.get("date")) if leg.get("date") else None
        if leg.get("date") and leg_date is None:
            incomplete.append(prefix + ":date_invalid")
        if leg_date and cutoff and leg_date <= cutoff:
            invalid.append(prefix + ":date_must_follow_report_cutoff")
        if leg_date and settlement_date and leg_date > settlement_date:
            invalid.append(prefix + ":date_after_settlement")

    def _leg_populated(leg: dict[str, Any]) -> bool:
        return any(leg.get(field) not in (None, "", []) for field in leg_fields)

    def _require_populated(leg: dict[str, Any], prefix: str) -> None:
        for field in leg_fields:
            if leg.get(field) in (None, "", []):
                incomplete.append(prefix + ":missing_filled_" + field)
        if _number(leg.get("price")) is None or _number(leg.get("price")) <= 0:
            invalid.append(prefix + ":price_invalid")
        if _number(leg.get("quantity")) is None or _number(leg.get("quantity")) <= 0:
            invalid.append(prefix + ":quantity_invalid")

    settled_exit = exit_leg.get("status") in {"EXITED", "MARKED_TO_MARKET"}
    if fill_status in {"FILLED", "PARTIALLY_FILLED"}:
        _require_populated(entry, "investment_return_outcome.execution.entry")
        if exit_leg.get("status") not in EXIT_STATUSES:
            invalid.append("investment_return_outcome.execution.exit:status_invalid")
        elif settled_exit:
            _require_populated(exit_leg, "investment_return_outcome.execution.exit")
        elif _leg_populated(exit_leg) and exit_leg.get("status") not in {"OPEN", "NOT_APPLICABLE"}:
            invalid.append("investment_return_outcome.execution.exit:unsettled_leg_has_values")
        entry_date = _timestamp(entry.get("date"))
        exit_date = _timestamp(exit_leg.get("date"))
        if entry_date and exit_date and exit_date < entry_date:
            invalid.append("investment_return_outcome.execution.exit_before_entry")
    elif fill_status in {"NOT_FILLED", "NOT_APPLICABLE"}:
        if _leg_populated(entry) or _leg_populated(exit_leg):
            invalid.append("investment_return_outcome.execution:unfilled_position_cannot_have_entry_or_exit")
        if exit_leg.get("status") not in {None, "NOT_APPLICABLE"}:
            invalid.append("investment_return_outcome.execution:unfilled_position_exit_must_be_not_applicable")

    if isinstance(decision, dict) and decision.get("price_identity") != "UNKNOWN":
        selected_price = _frozen_price(case or {}, str(decision.get("price_identity")))
        expected_currency = selected_price.get("currency") if selected_price else None
        for leg, prefix in ((entry, "investment_return_outcome.execution.entry"), (exit_leg, "investment_return_outcome.execution.exit")):
            if expected_currency and leg.get("currency") not in (None, "", expected_currency):
                invalid.append(prefix + ":currency_does_not_match_frozen_price_identity")

    ledger = outcome.get("cash_flow_ledger")
    flows: list[dict[str, Any]] = []
    flow_ids: set[str] = set()
    if not isinstance(ledger, list):
        incomplete.append("investment_return_outcome:cash_flow_ledger_missing")
    else:
        flow_fields = ("flow_id", "date", "flow_type", "gross_amount", "tax_amount", "fee_amount", "net_amount", "currency", "fx_rate_to_base", "net_base_amount", "source_ids")
        for index, flow in enumerate(ledger):
            prefix = f"investment_return_outcome.cash_flow_ledger[{index}]"
            if not isinstance(flow, dict):
                invalid.append(prefix + ":not_object")
                continue
            flows.append(flow)
            incomplete.extend(_required(flow, flow_fields, prefix))
            flow_id = str(flow.get("flow_id") or "")
            if flow_id in flow_ids:
                invalid.append(prefix + ":duplicate_flow_id")
            flow_ids.add(flow_id)
            if flow.get("flow_type") not in RETURN_CASH_FLOW_TYPES:
                invalid.append(prefix + ":flow_type_invalid")
            refs = flow.get("source_ids")
            ref_invalid, ref_incomplete = _validate_source_references(refs, actual_source_ids, prefix)
            invalid.extend(ref_invalid)
            incomplete.extend(ref_incomplete)
            flow_date = _timestamp(flow.get("date"))
            if flow_date is None:
                incomplete.append(prefix + ":date_invalid")
            elif settlement_date and flow_date > settlement_date:
                invalid.append(prefix + ":date_after_settlement")
            gross = _number(flow.get("gross_amount"))
            tax = _number(flow.get("tax_amount"))
            fee = _number(flow.get("fee_amount"))
            net = _number(flow.get("net_amount"))
            fx_rate = _number(flow.get("fx_rate_to_base"))
            net_base = _number(flow.get("net_base_amount"))
            if tax is not None and tax < 0:
                invalid.append(prefix + ":tax_amount_negative")
            if fee is not None and fee < 0:
                invalid.append(prefix + ":fee_amount_negative")
            if fx_rate is not None and fx_rate <= 0:
                invalid.append(prefix + ":fx_rate_invalid")
            if gross is not None and tax is not None and fee is not None and net is not None and not _numbers_match(net, gross - tax - fee):
                invalid.append(prefix + ":net_amount_does_not_reconcile")
            if net is not None and fx_rate is not None and net_base is not None and not _numbers_match(net_base, net * fx_rate):
                invalid.append(prefix + ":net_base_amount_does_not_reconcile")
            if flow.get("flow_type") in {"DIVIDEND", "CORPORATE_ACTION_CASH"} and not flow.get("corporate_action_id"):
                invalid.append(prefix + ":corporate_action_link_required")

    actions = outcome.get("corporate_actions")
    action_ids: set[str] = set()
    if not isinstance(actions, list):
        incomplete.append("investment_return_outcome:corporate_actions_missing")
        actions = []
    for index, corporate_action in enumerate(actions):
        prefix = f"investment_return_outcome.corporate_actions[{index}]"
        if not isinstance(corporate_action, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(corporate_action, ("action_id", "action_type", "effective_date", "treatment", "source_ids", "cash_flow_ids"), prefix))
        action_id = str(corporate_action.get("action_id") or "")
        if action_id in action_ids:
            invalid.append(prefix + ":duplicate_action_id")
        action_ids.add(action_id)
        if corporate_action.get("action_type") not in CORPORATE_ACTION_TYPES:
            invalid.append(prefix + ":action_type_invalid")
        ref_invalid, ref_incomplete = _validate_source_references(corporate_action.get("source_ids"), actual_source_ids, prefix)
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        effective_date = _timestamp(corporate_action.get("effective_date"))
        if effective_date and settlement_date and effective_date > settlement_date:
            invalid.append(prefix + ":effective_date_after_settlement")
        linked = corporate_action.get("cash_flow_ids") if isinstance(corporate_action.get("cash_flow_ids"), list) else []
        if corporate_action.get("action_type") == "CASH_DIVIDEND" and not linked:
            incomplete.append(prefix + ":cash_dividend_flow_link_missing")
        for flow_id in linked:
            if flow_id not in flow_ids:
                invalid.append(prefix + ":cash_flow_id_not_found:" + str(flow_id))
            else:
                flow = next(item for item in flows if item.get("flow_id") == flow_id)
                if flow.get("corporate_action_id") != action_id:
                    invalid.append(prefix + ":cash_flow_link_not_bidirectional:" + str(flow_id))
    for flow in flows:
        action_id = flow.get("corporate_action_id")
        if action_id and action_id in action_ids:
            linked_action = next(item for item in actions if item.get("action_id") == action_id)
            if flow.get("flow_id") not in (linked_action.get("cash_flow_ids") or []):
                invalid.append("investment_return_outcome.cash_flow_ledger:corporate_action_link_not_bidirectional:" + str(flow.get("flow_id")))
        elif action_id:
            invalid.append("investment_return_outcome.cash_flow_ledger:corporate_action_id_not_found:" + str(action_id))

    if status == "CALCULATED":
        if fill_status not in {"FILLED", "PARTIALLY_FILLED"} or not settled_exit:
            invalid.append("investment_return_outcome:calculated_requires_filled_and_settled_execution")
        if _number(outcome.get("total_return")) is None:
            invalid.append("investment_return_outcome:total_return_must_be_numeric_when_calculated")
        entry_flows = [flow for flow in flows if flow.get("flow_type") == "ENTRY"]
        final_type = "EXIT" if exit_leg.get("status") == "EXITED" else "MARK_TO_MARKET"
        final_flows = [flow for flow in flows if flow.get("flow_type") == final_type]
        if len(entry_flows) != 1:
            invalid.append("investment_return_outcome:exactly_one_entry_cash_flow_required")
        if len(final_flows) != 1:
            invalid.append("investment_return_outcome:exactly_one_final_cash_flow_required")
        if len(entry_flows) == 1:
            entry_flow = entry_flows[0]
            if entry.get("date") != entry_flow.get("date"):
                invalid.append("investment_return_outcome:entry_cash_flow_date_mismatch")
            entry_price = _number(entry.get("price"))
            entry_quantity = _number(entry.get("quantity"))
            if entry_price is not None and entry_quantity is not None and not _numbers_match(
                entry_flow.get("gross_amount"), -entry_price * entry_quantity,
            ):
                invalid.append("investment_return_outcome:entry_cash_flow_price_quantity_mismatch")
        if len(final_flows) == 1:
            final_flow = final_flows[0]
            if exit_leg.get("date") != final_flow.get("date"):
                invalid.append("investment_return_outcome:exit_cash_flow_date_mismatch")
            exit_price = _number(exit_leg.get("price"))
            exit_quantity = _number(exit_leg.get("quantity"))
            if exit_price is not None and exit_quantity is not None and not _numbers_match(
                final_flow.get("gross_amount"), exit_price * exit_quantity,
            ):
                invalid.append("investment_return_outcome:exit_cash_flow_price_quantity_mismatch")
        if entry_flows and final_flows and _number(entry_flows[0].get("net_base_amount")) is not None:
            invested = -_number(entry_flows[0].get("net_base_amount"))
            if invested <= 0:
                invalid.append("investment_return_outcome:entry_cash_flow_must_be_negative")
            else:
                expected_return = sum(_number(flow.get("net_base_amount")) or 0.0 for flow in flows) / invested
                if not _numbers_match(outcome.get("total_return"), expected_return):
                    invalid.append("investment_return_outcome:total_return_does_not_reconcile_to_cash_flow_ledger")
    return invalid, incomplete


def validate_settlement(record: dict[str, Any], *, case: dict[str, Any] | None = None) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if record.get("schema_version") != SETTLEMENT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if case is None:
        invalid.append("frozen_case_required_for_settlement_calibration")
    else:
        case_result = validate_case(case)
        if case_result["state"] != "REVIEWABLE":
            invalid.append("frozen_case_not_reviewable")
        if record.get("case_id") != case.get("case_id"):
            invalid.append("settlement_case_id_does_not_match_frozen_case")
        if record.get("experiment_id") != case.get("experiment_id"):
            invalid.append("settlement_experiment_id_does_not_match_frozen_case")
    cutoff = _timestamp(case.get("simulation_cutoff")) if case else None
    settlement_date = _timestamp(record.get("settlement_as_of"))
    if settlement_date is None:
        invalid.append("settlement_as_of_invalid")
    elif cutoff and settlement_date <= cutoff:
        invalid.append("settlement_must_follow_report_cutoff")
    actual_sources, source_invalid, source_incomplete = _validate_actual_sources(
        record, cutoff=cutoff, settlement_date=settlement_date,
    )
    invalid.extend(source_invalid)
    incomplete.extend(source_incomplete)
    actual_sources = {
        str(source.get("source_id")): source
        for source in record.get("actual_sources", [])
        if isinstance(source, dict) and source.get("source_id")
    }
    actual_source_ids = set(actual_sources)
    actual = record.get("actual_outcomes") if isinstance(record.get("actual_outcomes"), dict) else {}
    incomplete.extend(_required(actual, ("currency", "cash_flows", "operating_observations"), "actual_outcomes"))
    for group, fields in {
        "cash_flows": ("date", "amount", "source_ids"),
        "operating_observations": (
            "observation_id", "claim_id", "metric", "value", "unit", "measurement_basis", "period_start",
            "period_end", "source_ids", "comparability_status",
        ),
    }.items():
        observations = actual.get(group) if isinstance(actual.get(group), list) else []
        for index, observation in enumerate(observations):
            prefix = f"actual_outcomes.{group}[{index}]"
            if not isinstance(observation, dict):
                invalid.append(prefix + ":not_object")
                continue
            incomplete.extend(_required(observation, fields, prefix))
            ref_invalid, ref_incomplete = _validate_source_references(
                observation.get("source_ids"), set(actual_sources), prefix,
            )
            invalid.extend(ref_invalid)
            incomplete.extend(ref_incomplete)
    for section, fields in {
        "report_coverage": ("status", "supported_claim_count", "unsupported_claim_count", "unknowns_preserved", "notes"),
        "model_forecast_error": ("status", "metrics", "notes"),
        "investment_return_outcome": ("status", "action", "total_return", "benchmark_return", "currency", "notes"),
    }.items():
        payload = record.get(section) if isinstance(record.get(section), dict) else {}
        incomplete.extend(_required(payload, fields, section))
    return_outcome = record.get("investment_return_outcome") if isinstance(record.get("investment_return_outcome"), dict) else {}
    return_invalid, return_incomplete = _validate_return_outcome(
        return_outcome,
        case=case,
        actual_source_ids=actual_source_ids,
        actual_sources=actual_sources,
        cutoff=cutoff,
        settlement_date=settlement_date,
    )
    invalid.extend(return_invalid)
    incomplete.extend(return_incomplete)
    frozen_predictions = _frozen_predictions(case)
    frozen_claims = _frozen_claims(case)
    observation_by_id: dict[str, dict[str, Any]] = {}
    for index, observation in enumerate(actual.get("operating_observations") or []):
        if not isinstance(observation, dict) or not case:
            continue
        prefix = f"actual_outcomes.operating_observations[{index}]"
        observation_id = str(observation.get("observation_id") or "")
        if not observation_id.startswith("HBTOBS:"):
            invalid.append(prefix + ":observation_id_invalid")
        elif observation_id in observation_by_id:
            invalid.append("duplicate_operating_observation_id:" + observation_id)
        else:
            observation_by_id[observation_id] = observation
        observation_invalid, observation_incomplete = _validate_operating_observation(
            observation,
            prefix=prefix,
            frozen_claims=frozen_claims,
            actual_sources=actual_sources,
        )
        invalid.extend(observation_invalid)
        incomplete.extend(observation_incomplete)
    model_error = record.get("model_forecast_error") if isinstance(record.get("model_forecast_error"), dict) else {}
    timeline_invalid, timeline_incomplete = _validate_operating_source_timeline(
        record, actual_sources=actual_sources, observations=observation_by_id,
    )
    invalid.extend(timeline_invalid)
    incomplete.extend(timeline_incomplete)
    claim_settlements, settlement_invalid, settlement_incomplete = _validate_claim_settlements(
        model_error, frozen_claims=frozen_claims, observations=observation_by_id,
    )
    invalid.extend(settlement_invalid)
    incomplete.extend(settlement_incomplete)
    metrics_by_claim: dict[str, list[dict[str, Any]]] = {}
    for index, metric in enumerate(model_error.get("metrics") or []):
        prefix = f"model_forecast_error.metrics[{index}]"
        if not isinstance(metric, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(
            metric,
            (
                "claim_id", "observation_id", "metric", "forecast_value", "actual_value", "unit",
                "actual_source_ids",
            ),
            prefix,
        ))
        ref_invalid, ref_incomplete = _validate_source_references(
            metric.get("actual_source_ids"), set(actual_sources), prefix,
        )
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        if case:
            claim_id = str(metric.get("claim_id") or "")
            metrics_by_claim.setdefault(claim_id, []).append(metric)
            frozen = frozen_predictions.get(claim_id)
            if frozen is None:
                invalid.append(prefix + ":claim_has_no_frozen_quantitative_prediction:" + claim_id)
                continue
            claim_settlement = claim_settlements.get(claim_id)
            if claim_settlement is None:
                incomplete.append(prefix + ":claim_settlement_missing")
            elif claim_settlement.get("status") != "CALCULATED":
                invalid.append(prefix + ":metric_requires_calculated_claim_settlement")
            prediction = frozen.get("prediction") if isinstance(frozen.get("prediction"), dict) else {}
            if metric.get("metric") != prediction.get("metric"):
                invalid.append(prefix + ":metric_does_not_match_frozen_prediction")
            if metric.get("forecast_value") != prediction.get("value"):
                invalid.append(prefix + ":forecast_value_does_not_match_frozen_prediction")
            observation_id = str(metric.get("observation_id") or "")
            observation = observation_by_id.get(observation_id)
            if observation is None:
                invalid.append(prefix + ":observation_id_not_found:" + observation_id)
                continue
            if metric.get("claim_id") != observation.get("claim_id"):
                invalid.append(prefix + ":claim_id_does_not_match_operating_observation")
            if metric.get("metric") != observation.get("metric"):
                invalid.append(prefix + ":metric_does_not_match_operating_observation")
            if metric.get("unit") != observation.get("unit"):
                invalid.append(prefix + ":unit_does_not_match_operating_observation")
            if metric.get("actual_value") != observation.get("value"):
                invalid.append(prefix + ":actual_value_does_not_match_operating_observation")
            if set(metric.get("actual_source_ids") or []) != set(observation.get("source_ids") or []):
                invalid.append(prefix + ":actual_source_ids_do_not_match_operating_observation")
            if observation.get("comparability_status") not in COMPARABLE_OPERATING_STATUSES:
                invalid.append(prefix + ":actual_observation_not_comparable")
            if claim_settlement is not None and observation_id not in (claim_settlement.get("observation_ids") or []):
                invalid.append(prefix + ":observation_not_registered_for_claim_settlement")
            invalid.extend(_validate_metric_version_policy(
                metric, observation, frozen_claim=frozen, observations=observation_by_id,
                actual_sources=actual_sources, prefix=prefix,
            ))
    for claim_id in frozen_predictions:
        claim_settlement = claim_settlements.get(claim_id)
        if claim_settlement is None:
            continue
        metrics = metrics_by_claim.get(claim_id, [])
        if claim_settlement.get("status") == "CALCULATED" and len(metrics) != 1:
            invalid.append("model_forecast_error.claim_settlements:" + claim_id + ":calculated_prediction_requires_exactly_one_metric")
        if model_error.get("status") == "CALCULATED" and claim_settlement.get("status") != "CALCULATED":
            invalid.append("model_forecast_error:calculated_requires_all_prediction_claims_calculated")
    forbidden = _nested_forbidden(record, path="settlement")
    # Hindsight is expected in actual_outcomes; only reject a combined score.
    if "combined_score" in json.dumps(record, ensure_ascii=False).lower() or "composite_score" in json.dumps(record, ensure_ascii=False).lower():
        invalid.append("combined_score_forbidden")
    if record.get("status") == "REVIEWABLE" and incomplete:
        invalid.append("reviewable_settlement_incomplete")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": list(dict.fromkeys(invalid)), "incomplete_findings": list(dict.fromkeys(incomplete)), "hindsight_fields_seen": len(forbidden)}


def build_pilot_experiment(*, registered_at: str = "2026-08-16T00:00:00+08:00") -> dict[str, Any]:
    """Pre-register current candidates without pretending their vintages exist."""
    cases = [
        {
            "case_id": f"HBTCASE:{code}",
            "company_code": code,
            "company_name": name,
            "eligibility_status": "INELIGIBLE_NO_HISTORICAL_VINTAGE",
            "eligibility_reason": "当前候选保存的是最新研究输出，未同时保存可验证的历史报告版本、逐源发布时间和当时市场数据，不能重建无前视信息的冻结报告。",
        }
        for code, name in PILOT_CASES
    ]
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_id": "HBT:current-candidates-pilot-v1",
        "status": "PRE_REGISTERED",
        "registered_at": registered_at,
        "framework": {
            "framework_version": "Turtle-G2-2026-08-16",
            "route_policy": "route-aware-long-owner-finite-xirr-dual",
            "golden_gate_state": "G3_NOT_READY",
        },
        "information_policy": {
            "cutoff_timezone": "Asia/Shanghai",
            "source_rule": "published_at_and_data_as_of_must_not_exceed_cutoff",
            "current_restated_data_rule": "current_restated_values_are_ineligible_without_historical_vintage",
            "future_file_rule": "future_files_are_unreadable_before_settlement",
            "survivorship_rule": "retain_delisted_acquired_and_failed_cases_in_registered_universe",
            "execution_rule": "next_tradable_price_after_frozen_report_or_preregistered_rule",
        },
        "universe": {"selection_status": "RESEARCH_PILOT", "cases": cases, "eligible_case_count": 0},
        "scoring_policy": {
            "separate_dimensions": ["REPORT_COVERAGE", "MODEL_FORECAST_ERROR", "INVESTMENT_RETURN_OUTCOME"],
            "no_compensating_score": True,
            "minimum_outcome_fields": ["cash_flows", "benchmark_return", "currency", "execution_rule"],
        },
    }


def validate_pilot(path: str | Path | None = None) -> dict[str, Any]:
    payload = build_pilot_experiment() if path is None else json.loads(Path(path).read_text(encoding="utf-8"))
    result = validate_experiment(payload)
    result["eligible_case_count"] = payload.get("universe", {}).get("eligible_case_count")
    result["pilot_is_empty"] = result["eligible_case_count"] == 0
    return result


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pilot = sub.add_parser("pilot", help="write the honest current-candidate pilot registry")
    pilot.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate", help="validate an experiment, case or settlement JSON")
    validate.add_argument("kind", choices=["experiment", "case", "settlement"])
    validate.add_argument("path", type=Path)
    validate.add_argument("--case", type=Path, help="frozen case required to cross-check a settlement")
    args = parser.parse_args()
    if args.command == "pilot":
        payload = build_pilot_experiment()
        _write(args.output, payload)
        print(json.dumps({"written": str(args.output), "eligible_case_count": 0}, ensure_ascii=False))
        return 0
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    if args.kind == "experiment":
        result = validate_experiment(payload)
    elif args.kind == "case":
        result = validate_case(payload)
    else:
        case = json.loads(args.case.read_text(encoding="utf-8")) if args.case else None
        result = validate_settlement(payload, case=case)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "REVIEWABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
