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
LEAKAGE_FIELDS = {
    "actual", "actual_outcome", "actual_outcomes", "outcome", "outcomes", "settlement",
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
    if source.get("admissible") is not True:
        invalid.append(prefix + ":source_not_admissible")
    return invalid, incomplete


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
    taxes = record.get("taxes_fees_fx") if isinstance(record.get("taxes_fees_fx"), dict) else {}
    incomplete.extend(_required(taxes, ("tax_rate", "transaction_fee_rate", "dividend_tax_rate", "base_currency", "fx_rule"), "taxes_fees_fx"))
    invalid.extend(_route_findings(record))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": list(dict.fromkeys(invalid)), "incomplete_findings": list(dict.fromkeys(incomplete))}


def validate_settlement(record: dict[str, Any], *, case: dict[str, Any] | None = None) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if record.get("schema_version") != SETTLEMENT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    cutoff = _date(case.get("simulation_cutoff")) if case else None
    settlement_date = _date(record.get("settlement_as_of"))
    if settlement_date is None:
        invalid.append("settlement_as_of_invalid")
    elif cutoff and settlement_date <= cutoff:
        invalid.append("settlement_must_follow_report_cutoff")
    actual = record.get("actual_outcomes") if isinstance(record.get("actual_outcomes"), dict) else {}
    actual_published = _date(actual.get("published_at"))
    if actual_published is None:
        incomplete.append("actual_outcomes_published_at_missing")
    elif cutoff and actual_published <= cutoff:
        invalid.append("actual_outcomes_must_be_future_to_report")
    for section, fields in {
        "report_coverage": ("status", "supported_claim_count", "unsupported_claim_count", "unknowns_preserved", "notes"),
        "model_forecast_error": ("status", "metrics", "notes"),
        "investment_return_outcome": ("status", "action", "total_return", "benchmark_return", "currency", "notes"),
    }.items():
        payload = record.get(section) if isinstance(record.get(section), dict) else {}
        incomplete.extend(_required(payload, fields, section))
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
        result = validate_settlement(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "REVIEWABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
