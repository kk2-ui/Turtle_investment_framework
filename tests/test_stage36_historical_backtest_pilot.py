from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.historical_backtest import (
    CASE_SCHEMA_VERSION,
    SETTLEMENT_SCHEMA_VERSION,
    build_pilot_experiment,
    validate_case,
    validate_experiment,
    validate_pilot,
    validate_settlement,
)


def _case() -> dict:
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "case_id": "HBTCASE:TEST",
        "experiment_id": "HBT:test",
        "company_code": "00506.HK",
        "simulation_cutoff": "2021-08-31T18:00:00+08:00",
        "report_freeze": {
            "frozen_at": "2021-08-31T19:00:00+08:00",
            "evidence_cutoff": "2021-08-31T18:00:00+08:00",
            "settlement_locked": True,
            "report_status": "FROZEN",
        },
        "route": "LONG_TERM_OWNER",
        "forecast": {
            "horizon_years": 5,
            "terminal_handling": "NO_REQUIRED_EXIT",
            "cash_flow_basis": "普通股股东税后现金和认可留存",
        },
        "sources": [{
            "source_id": "AR:00506:2020",
            "source_type": "ANNUAL_REPORT",
            "published_at": "2021-03-25",
            "data_as_of": "2020-12-31",
            "source_version": "annual-report-original-2020",
            "revision_published_at": None,
            "revision_policy": "ORIGINAL_VINTAGE",
            "admissible": True,
        }],
        "inputs": [{
            "name": "normal_owner_earnings",
            "value": 0.2,
            "input_role": "JUDGMENT",
            "source_ids": ["AR:00506:2020"],
        }],
        "taxes_fees_fx": {
            "tax_rate": 0.1,
            "transaction_fee_rate": 0.001,
            "dividend_tax_rate": 0.1,
            "base_currency": "HKD",
            "fx_rule": "仅在报告冻结时使用历史可见汇率",
        },
        "price_identity": {
            "primary_route": "LONG_TERM_OWNER",
            "primary_price_identity": "P_LONG",
            "prices": [{"identity": "P_LONG", "currency": "HKD", "value": 2.0, "meaning": "达到目标长期所有者回报的条件价格"}],
        },
        "status": "FROZEN",
    }


def _settlement() -> dict:
    return {
        "schema_version": SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": "HBTSET:TEST:2022",
        "experiment_id": "HBT:test",
        "case_id": "HBTCASE:TEST",
        "settlement_as_of": "2022-08-31T18:00:00+08:00",
        "actual_outcomes": {
            "published_at": "2022-03-25",
            "currency": "HKD",
            "cash_flows": [{"date": "2022-05-10", "amount": 0.1}],
            "operating_observations": [{"metric": "revenue", "value": 100}],
        },
        "report_coverage": {
            "status": "PARTIAL",
            "supported_claim_count": 8,
            "unsupported_claim_count": 2,
            "unknowns_preserved": True,
            "notes": ["覆盖度不与投资结果合并"],
        },
        "model_forecast_error": {
            "status": "CALCULATED",
            "metrics": [{"name": "owner_cash_error", "forecast": 0.2, "actual": 0.18}],
            "notes": ["只评价冻结报告已声明的预测"],
        },
        "investment_return_outcome": {
            "status": "CALCULATED",
            "action": "BUY",
            "total_return": 0.08,
            "benchmark_return": 0.03,
            "currency": "HKD",
            "notes": ["含现金股息和费用"],
        },
        "status": "REVIEWABLE",
    }


def test_current_candidate_pilot_is_explicitly_empty_and_does_not_unlock_g3() -> None:
    experiment = build_pilot_experiment()
    result = validate_experiment(experiment)
    assert result["state"] == "REVIEWABLE"
    assert experiment["universe"]["eligible_case_count"] == 0
    assert len(experiment["universe"]["cases"]) == 9
    assert experiment["framework"]["golden_gate_state"] == "G3_NOT_READY"
    assert validate_pilot()["pilot_is_empty"] is True


def test_future_source_and_current_restated_value_are_blocked() -> None:
    case = _case()
    case["sources"][0]["published_at"] = "2022-03-25"
    result = validate_case(case)
    assert result["state"] == "INVALID"
    assert "sources[0]:future_published_at" in result["invalid_findings"]

    case = _case()
    case["sources"][0]["revision_policy"] = "CURRENT_RESTATED_ONLY"
    result = validate_case(case)
    assert "sources[0]:current_restated_data_not_admissible" in result["invalid_findings"]


def test_frozen_inputs_cannot_contain_hindsight_and_route_price_identity_is_checked() -> None:
    case = _case()
    case["inputs"][0]["actual_outcome"] = 0.3
    result = validate_case(case)
    assert result["state"] == "INVALID"
    assert any(item.startswith("future_field_in_frozen_input") for item in result["invalid_findings"])

    case = _case()
    case["price_identity"]["primary_price_identity"] = "P_XIRR"
    result = validate_case(case)
    assert "long_term_route_requires_p_long_primary" in result["invalid_findings"]


def test_fixed_market_terminal_price_cannot_be_primary_without_independent_evidence() -> None:
    case = _case()
    case["route"] = "FINITE_XIRR"
    case["forecast"] = {
        "horizon_years": 5,
        "terminal_handling": "MARKET_EXIT",
        "cash_flow_basis": "税费后现金流",
        "independent_terminal_evidence": False,
    }
    case["price_identity"] = {
        "primary_route": "FINITE_XIRR",
        "primary_price_identity": "P_XIRR",
        "prices": [{"identity": "P_XIRR", "currency": "HKD", "value": 2, "meaning": "条件价"}],
    }
    result = validate_case(case)
    assert "fixed_market_terminal_price_cannot_be_primary_without_independent_evidence" in result["invalid_findings"]


def test_settlement_keeps_coverage_model_and_investment_dimensions_separate() -> None:
    case = _case()
    settlement = _settlement()
    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"

    combined = deepcopy(settlement)
    combined["score"] = {"combined_score": 0.8}
    result = validate_settlement(combined, case=case)
    assert result["state"] == "INVALID"
    assert "combined_score_forbidden" in result["invalid_findings"]


def test_settlement_before_cutoff_is_lookahead() -> None:
    settlement = _settlement()
    settlement["settlement_as_of"] = "2021-08-31T17:00:00+08:00"
    result = validate_settlement(settlement, case=_case())
    assert "settlement_must_follow_report_cutoff" in result["invalid_findings"]


def test_checked_in_pilot_config_matches_builder() -> None:
    path = Path(__file__).parents[1] / "config" / "historical_backtest_pilot.v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert validate_experiment(payload)["state"] == "REVIEWABLE"
    assert payload["universe"]["eligible_case_count"] == 0
