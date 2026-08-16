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
        "calibration_ledger": {
            "claims": [
                {
                    "claim_id": "HBTCLM:owner-cash",
                    "statement": "普通股每股 owner cash 在下一财年不少于 HKD0.20。",
                    "materiality": "RETURN",
                    "frozen_disposition": "PREDICTION",
                    "source_ids": ["AR:00506:2020"],
                    "prediction": {
                        "metric": "ordinary_share_owner_cash_per_share",
                        "operator": "AT_LEAST",
                        "value": 0.2,
                        "unit": "HKD/share",
                        "horizon": "FY2021 results",
                    },
                    "threshold": {
                        "metric": "ordinary_share_owner_cash_per_share",
                        "operator": "AT_MOST",
                        "value": 0.15,
                        "unit": "HKD/share",
                        "consequence": "长期回报和 P_LONG 需要下调重算。",
                    },
                    "unknown": None,
                    "counter_thesis": "渠道和包材压力使现金转化低于正常化判断。",
                    "flip_condition": "FY2021 普通股 owner cash 低于 HKD0.15/share。",
                    "observable_outcome": {
                        "metric": "ordinary_share_owner_cash_per_share",
                        "unit": "HKD/share",
                        "measurement_rule": "按下一份官方年报的经营现金、资本开支和普通股归属重新计算。",
                    },
                },
                {
                    "claim_id": "HBTCLM:minority-cash-access",
                    "statement": "子公司少数股东现金索取的实际比例尚未被官方披露闭合。",
                    "materiality": "VALUATION",
                    "frozen_disposition": "UNKNOWN",
                    "source_ids": ["AR:00506:2020"],
                    "prediction": None,
                    "threshold": None,
                    "unknown": {
                        "statement": "少数股东现金索取比例未知。",
                        "economic_impact": "可能高估普通股可得现金和长期价格。",
                        "resolution_observation": "后续年报披露的少数股东分红与现金流量资料。",
                    },
                    "counter_thesis": "少数股东分红长期接近其利润份额。",
                    "flip_condition": "官方披露证明普通股现金归属低于模型假设。",
                    "observable_outcome": {
                        "metric": "minority_cash_distribution_ratio",
                        "unit": "%",
                        "measurement_rule": "以官方年报的少数股东分红除以少数股东归属现金口径。",
                    },
                },
            ],
        },
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
        "actual_sources": [{
            "source_id": "AR:00506:2021",
            "source_type": "ANNUAL_REPORT",
            "official": True,
            "published_at": "2022-03-25",
            "source_version": "annual-report-original-2021",
            "data_as_of": "2021-12-31",
        }],
        "actual_outcomes": {
            "currency": "HKD",
            "cash_flows": [{"date": "2022-05-10", "amount": 0.1, "source_ids": ["AR:00506:2021"]}],
            "operating_observations": [{
                "claim_id": "HBTCLM:owner-cash",
                "metric": "ordinary_share_owner_cash_per_share",
                "value": 0.18,
                "unit": "HKD/share",
                "source_ids": ["AR:00506:2021"],
            }],
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
            "metrics": [{
                "claim_id": "HBTCLM:owner-cash",
                "metric": "ordinary_share_owner_cash_per_share",
                "forecast_value": 0.2,
                "actual_value": 0.18,
                "unit": "HKD/share",
                "actual_source_ids": ["AR:00506:2021"],
            }],
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


def test_calibration_ledger_binds_claims_to_frozen_sources_and_preserves_unknowns() -> None:
    case = _case()
    assert validate_case(case)["state"] == "REVIEWABLE"

    unresolved = deepcopy(case)
    unresolved["inputs"][0]["source_ids"] = ["AR:missing"]
    result = validate_case(unresolved)
    assert "inputs[0]:source_id_not_found:AR:missing" in result["invalid_findings"]

    hindsight = deepcopy(case)
    hindsight["calibration_ledger"]["claims"][0]["prediction"]["actual_value"] = 0.18
    result = validate_case(hindsight)
    assert any(item.startswith("future_field_in_frozen_input:calibration_ledger") for item in result["invalid_findings"])

    malformed_unknown = deepcopy(case)
    malformed_unknown["calibration_ledger"]["claims"][1]["threshold"] = {
        "metric": "minority_cash_distribution_ratio", "operator": "AT_LEAST", "value": 0.5,
        "unit": "%", "consequence": "not applicable",
    }
    result = validate_case(malformed_unknown)
    assert "calibration_ledger.claims[1]:unknown_cannot_carry_quantitative_prediction" in result["invalid_findings"]


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

    without_case = validate_settlement(settlement)
    assert "frozen_case_required_for_settlement_calibration" in without_case["invalid_findings"]

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


def test_settlement_requires_later_official_sources_and_cannot_rewrite_frozen_prediction() -> None:
    case = _case()
    settlement = _settlement()

    unverified = deepcopy(settlement)
    unverified["actual_outcomes"]["cash_flows"][0]["source_ids"] = ["AR:missing"]
    result = validate_settlement(unverified, case=case)
    assert "actual_outcomes.cash_flows[0]:source_id_not_found:AR:missing" in result["invalid_findings"]

    after_cutoff = deepcopy(settlement)
    after_cutoff["actual_sources"][0]["published_at"] = "2021-08-31"
    result = validate_settlement(after_cutoff, case=case)
    assert "actual_sources[0]:published_at_must_follow_report_cutoff" in result["invalid_findings"]

    source_metadata_missing = deepcopy(settlement)
    source_metadata_missing["actual_sources"][0]["official"] = False
    source_metadata_missing["actual_sources"][0]["source_version"] = ""
    result = validate_settlement(source_metadata_missing, case=case)
    assert "actual_sources[0]:official_source_required" in result["invalid_findings"]
    assert "actual_sources[0]:missing:source_version" in result["incomplete_findings"]

    rewritten = deepcopy(settlement)
    rewritten["model_forecast_error"]["metrics"][0]["forecast_value"] = 0.25
    result = validate_settlement(rewritten, case=case)
    assert "model_forecast_error.metrics[0]:forecast_value_does_not_match_frozen_prediction" in result["invalid_findings"]


def test_checked_in_pilot_config_matches_builder() -> None:
    path = Path(__file__).parents[1] / "config" / "historical_backtest_pilot.v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert validate_experiment(payload)["state"] == "REVIEWABLE"
    assert payload["universe"]["eligible_case_count"] == 0
