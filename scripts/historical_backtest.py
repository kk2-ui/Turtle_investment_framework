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
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_SCHEMA_VERSION = "historical-backtest-experiment.v1"
CASE_SCHEMA_VERSION = "historical-backtest-case.v1"
SETTLEMENT_SCHEMA_VERSION = "historical-backtest-settlement.v1"

ROUTES = {"LONG_TERM_OWNER", "FINITE_XIRR", "DUAL"}
PRIMARY_PRICE_IDENTITIES = {"P_LONG", "P_XIRR", "P_LEGAL", "P_BUSINESS_VALUE_EXIT", "UNKNOWN"}
OFFICIAL_SETTLEMENT_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT", "OFFICIAL_STATISTICS",
    "OFFICIAL_MARKET_DATA", "OTHER_OFFICIAL",
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


def _required(record: dict[str, Any], fields: Iterable[str], prefix: str) -> list[str]:
    return [f"{prefix}:missing:{field}" for field in fields if record.get(field) in (None, "", [], {})]


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


def _validate_source(source: dict[str, Any], cutoff: date, index: int) -> tuple[list[str], list[str]]:
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = f"sources[{index}]"
    published = _date(source.get("published_at"))
    data_as_of = _date(source.get("data_as_of"))
    revision = _date(source.get("revision_published_at")) if source.get("revision_published_at") else None
    if published is None or data_as_of is None:
        incomplete.append(prefix + ":published_at_or_data_as_of_missing")
    else:
        if published > cutoff:
            invalid.append(prefix + ":future_published_at")
        if data_as_of > cutoff:
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
        incomplete.extend(_required(outcome, ("metric", "unit", "measurement_rule"), prefix + ".observable_outcome"))
        if disposition == "PREDICTION":
            prediction = claim.get("prediction") if isinstance(claim.get("prediction"), dict) else {}
            threshold = claim.get("threshold") if isinstance(claim.get("threshold"), dict) else {}
            incomplete.extend(_required(prediction, ("metric", "operator", "value", "unit", "horizon"), prefix + ".prediction"))
            incomplete.extend(_required(threshold, ("metric", "operator", "value", "unit", "consequence"), prefix + ".threshold"))
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


def validate_case(record: dict[str, Any]) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if record.get("schema_version") != CASE_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    invalid.extend(_nested_forbidden(record.get("inputs", []), path="inputs"))
    invalid.extend(_nested_forbidden(record.get("calibration_ledger", {}), path="calibration_ledger"))
    simulation_cutoff = _date(record.get("simulation_cutoff"))
    if simulation_cutoff is None:
        invalid.append("simulation_cutoff_invalid")
        simulation_cutoff = date.min
    report_freeze = record.get("report_freeze") if isinstance(record.get("report_freeze"), dict) else {}
    if report_freeze.get("settlement_locked") is not True:
        invalid.append("settlement_must_be_locked_at_report_freeze")
    freeze_date = _date(report_freeze.get("frozen_at"))
    evidence_cutoff = _date(report_freeze.get("evidence_cutoff"))
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
    taxes = record.get("taxes_fees_fx") if isinstance(record.get("taxes_fees_fx"), dict) else {}
    incomplete.extend(_required(taxes, ("tax_rate", "transaction_fee_rate", "dividend_tax_rate", "base_currency", "fx_rule"), "taxes_fees_fx"))
    invalid.extend(_route_findings(record))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": list(dict.fromkeys(invalid)), "incomplete_findings": list(dict.fromkeys(incomplete))}


def _validate_actual_sources(
    record: dict[str, Any], *, cutoff: date | None, settlement_date: date | None,
) -> tuple[set[str], list[str], list[str]]:
    """Check that settlement facts have their own later official evidence."""
    source_ids: set[str] = set()
    invalid: list[str] = []
    incomplete: list[str] = []
    sources = record.get("actual_sources") if isinstance(record.get("actual_sources"), list) else []
    if not sources:
        incomplete.append("actual_sources_missing")
        return source_ids, invalid, incomplete
    for index, source in enumerate(sources):
        prefix = f"actual_sources[{index}]"
        if not isinstance(source, dict):
            invalid.append(prefix + ":not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id:
            incomplete.append(prefix + ":source_id_missing")
        elif source_id in source_ids:
            invalid.append("duplicate_actual_source_id:" + source_id)
        source_ids.add(source_id)
        incomplete.extend(_required(source, ("source_type", "official", "published_at", "source_version"), prefix))
        if source.get("official") is not True:
            invalid.append(prefix + ":official_source_required")
        if source.get("source_type") not in OFFICIAL_SETTLEMENT_SOURCE_TYPES:
            invalid.append(prefix + ":official_source_type_invalid")
        published = _date(source.get("published_at"))
        if published is None:
            incomplete.append(prefix + ":published_at_invalid")
        else:
            if cutoff and published <= cutoff:
                invalid.append(prefix + ":published_at_must_follow_report_cutoff")
            if settlement_date and published > settlement_date:
                invalid.append(prefix + ":published_at_after_settlement")
        data_as_of = source.get("data_as_of")
        if data_as_of is not None:
            observed_date = _date(data_as_of)
            if observed_date is None:
                incomplete.append(prefix + ":data_as_of_invalid")
            elif settlement_date and observed_date > settlement_date:
                invalid.append(prefix + ":data_as_of_after_settlement")
    return source_ids, invalid, incomplete


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
    cutoff = _date(case.get("simulation_cutoff")) if case else None
    settlement_date = _date(record.get("settlement_as_of"))
    if settlement_date is None:
        invalid.append("settlement_as_of_invalid")
    elif cutoff and settlement_date <= cutoff:
        invalid.append("settlement_must_follow_report_cutoff")
    actual_source_ids, source_invalid, source_incomplete = _validate_actual_sources(
        record, cutoff=cutoff, settlement_date=settlement_date,
    )
    invalid.extend(source_invalid)
    incomplete.extend(source_incomplete)
    actual = record.get("actual_outcomes") if isinstance(record.get("actual_outcomes"), dict) else {}
    incomplete.extend(_required(actual, ("currency", "cash_flows", "operating_observations"), "actual_outcomes"))
    for group, fields in {
        "cash_flows": ("date", "amount", "source_ids"),
        "operating_observations": ("claim_id", "metric", "value", "source_ids"),
    }.items():
        observations = actual.get(group) if isinstance(actual.get(group), list) else []
        for index, observation in enumerate(observations):
            prefix = f"actual_outcomes.{group}[{index}]"
            if not isinstance(observation, dict):
                invalid.append(prefix + ":not_object")
                continue
            incomplete.extend(_required(observation, fields, prefix))
            ref_invalid, ref_incomplete = _validate_source_references(
                observation.get("source_ids"), actual_source_ids, prefix,
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
    frozen_predictions = _frozen_predictions(case)
    known_claim_ids = set(frozen_predictions)
    if case:
        ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
        known_claim_ids.update(
            str(item.get("claim_id"))
            for item in ledger.get("claims", []) if isinstance(item, dict)
        )
    for index, observation in enumerate(actual.get("operating_observations") or []):
        if not isinstance(observation, dict) or not case:
            continue
        claim_id = str(observation.get("claim_id") or "")
        if claim_id not in known_claim_ids:
            invalid.append(f"actual_outcomes.operating_observations[{index}]:claim_id_not_frozen:{claim_id}")
    model_error = record.get("model_forecast_error") if isinstance(record.get("model_forecast_error"), dict) else {}
    for index, metric in enumerate(model_error.get("metrics") or []):
        prefix = f"model_forecast_error.metrics[{index}]"
        if not isinstance(metric, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(
            metric,
            ("claim_id", "metric", "forecast_value", "actual_value", "unit", "actual_source_ids"),
            prefix,
        ))
        ref_invalid, ref_incomplete = _validate_source_references(
            metric.get("actual_source_ids"), actual_source_ids, prefix,
        )
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        if case:
            claim_id = str(metric.get("claim_id") or "")
            frozen = frozen_predictions.get(claim_id)
            if frozen is None:
                invalid.append(prefix + ":claim_has_no_frozen_quantitative_prediction:" + claim_id)
                continue
            prediction = frozen.get("prediction") if isinstance(frozen.get("prediction"), dict) else {}
            if metric.get("metric") != prediction.get("metric"):
                invalid.append(prefix + ":metric_does_not_match_frozen_prediction")
            if metric.get("forecast_value") != prediction.get("value"):
                invalid.append(prefix + ":forecast_value_does_not_match_frozen_prediction")
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
