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
                        "measurement_basis": "cash_flow_from_operations less maintenance_capex attributable to ordinary shareholders divided by weighted_average_ordinary_shares",
                        "measurement_rule": "按下一份官方年报的经营现金、资本开支和普通股归属重新计算。",
                        "period_start": "2021-01-01",
                        "period_end": "2021-12-31",
                        "allowed_source_types": ["ANNUAL_REPORT", "EXCHANGE_ANNOUNCEMENT"],
                        "settlement_version_policy": "INITIAL_DISCLOSURE",
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
                        "measurement_basis": "minority_dividends_paid divided by minority_attributable_cash_measure",
                        "measurement_rule": "以官方年报的少数股东分红除以少数股东归属现金口径。",
                        "period_start": "2021-01-01",
                        "period_end": "2021-12-31",
                        "allowed_source_types": ["ANNUAL_REPORT"],
                        "settlement_version_policy": "INITIAL_DISCLOSURE",
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
        "investment_decision": {
            "action": "BUY",
            "price_identity": "P_LONG",
            "execution_rule": "冻结报告后首个可交易日以原始开盘价执行。",
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
        }, {
            "source_id": "MKT:00506:2022-08-30",
            "source_type": "OFFICIAL_MARKET_DATA",
            "official": True,
            "published_at": "2022-08-30",
            "source_version": "exchange-official-unadjusted-close-v1",
            "data_as_of": "2022-08-30",
        }],
        "operating_source_timeline": {
            "enumeration_status": "COMPLETE",
            "source_ids": ["AR:00506:2021"],
        },
        "actual_outcomes": {
            "currency": "HKD",
            "cash_flows": [{"date": "2022-05-10", "amount": 0.1, "source_ids": ["AR:00506:2021"]}],
            "operating_observations": [{
                "observation_id": "HBTOBS:owner-cash:FY2021",
                "claim_id": "HBTCLM:owner-cash",
                "metric": "ordinary_share_owner_cash_per_share",
                "value": 0.18,
                "unit": "HKD/share",
                "measurement_basis": "cash_flow_from_operations less maintenance_capex attributable to ordinary shareholders divided by weighted_average_ordinary_shares",
                "period_start": "2021-01-01",
                "period_end": "2021-12-31",
                "source_ids": ["AR:00506:2021"],
                "comparability_status": "COMPARABLE",
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
            "claim_settlements": [{
                "claim_id": "HBTCLM:owner-cash",
                "frozen_disposition": "PREDICTION",
                "status": "CALCULATED",
                "observation_ids": ["HBTOBS:owner-cash:FY2021"],
            }, {
                "claim_id": "HBTCLM:minority-cash-access",
                "frozen_disposition": "UNKNOWN",
                "status": "UNRESOLVED_AS_OF_SETTLEMENT",
                "observation_ids": [],
            }],
            "metrics": [{
                "claim_id": "HBTCLM:owner-cash",
                "observation_id": "HBTOBS:owner-cash:FY2021",
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
            "frozen_action": "BUY",
            "frozen_price_identity": "P_LONG",
            "total_return": 0.09,
            "benchmark_return": 0.03,
            "currency": "HKD",
            "notes": ["含现金股息和费用"],
            "execution": {
                "execution_rule": "冻结报告后首个可交易日以原始开盘价执行。",
                "fill_status": "FILLED",
                "entry": {
                    "date": "2021-09-01",
                    "price": 1.0,
                    "quantity": 100,
                    "currency": "HKD",
                    "source_ids": ["MKT:00506:2022-08-30"],
                },
                "exit": {
                    "status": "MARKED_TO_MARKET",
                    "date": "2022-08-30",
                    "price": 1.0,
                    "quantity": 100,
                    "currency": "HKD",
                    "source_ids": ["MKT:00506:2022-08-30"],
                },
            },
            "cash_flow_ledger": [
                {
                    "flow_id": "HBTFLW:entry",
                    "date": "2021-09-01",
                    "flow_type": "ENTRY",
                    "gross_amount": -100.0,
                    "tax_amount": 0.0,
                    "fee_amount": 0.0,
                    "net_amount": -100.0,
                    "currency": "HKD",
                    "fx_rate_to_base": 1.0,
                    "net_base_amount": -100.0,
                    "source_ids": ["MKT:00506:2022-08-30"],
                },
                {
                    "flow_id": "HBTFLW:dividend",
                    "date": "2022-05-10",
                    "flow_type": "DIVIDEND",
                    "gross_amount": 10.0,
                    "tax_amount": 1.0,
                    "fee_amount": 0.0,
                    "net_amount": 9.0,
                    "currency": "HKD",
                    "fx_rate_to_base": 1.0,
                    "net_base_amount": 9.0,
                    "corporate_action_id": "HBTCA:dividend",
                    "source_ids": ["AR:00506:2021"],
                },
                {
                    "flow_id": "HBTFLW:mark",
                    "date": "2022-08-30",
                    "flow_type": "MARK_TO_MARKET",
                    "gross_amount": 100.0,
                    "tax_amount": 0.0,
                    "fee_amount": 0.0,
                    "net_amount": 100.0,
                    "currency": "HKD",
                    "fx_rate_to_base": 1.0,
                    "net_base_amount": 100.0,
                    "source_ids": ["MKT:00506:2022-08-30"],
                },
            ],
            "corporate_actions": [{
                "action_id": "HBTCA:dividend",
                "action_type": "CASH_DIVIDEND",
                "effective_date": "2022-05-10",
                "treatment": "REFLECTED_IN_CASH_FLOW_LEDGER",
                "source_ids": ["AR:00506:2021"],
                "cash_flow_ids": ["HBTFLW:dividend"],
            }],
            "taxes_fees_fx": {
                "tax_rate": 0.1,
                "transaction_fee_rate": 0.001,
                "dividend_tax_rate": 0.1,
                "base_currency": "HKD",
                "fx_rule": "仅在报告冻结时使用历史可见汇率",
            },
            "benchmark_identity": {
                "benchmark_id": "HSI",
                "market": "HK",
                "currency": "HKD",
                "return_basis": "TOTAL_RETURN_NET",
                "calculation_rule": "与个股使用相同入场日和期末盯市日。",
                "source_ids": ["MKT:00506:2022-08-30"],
            },
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


def test_cutoff_comparisons_preserve_intraday_source_order() -> None:
    case = _case()
    case["sources"][0]["published_at"] = "2021-08-31T18:00:01+08:00"
    result = validate_case(case)
    assert "sources[0]:future_published_at" in result["invalid_findings"]

    settlement = _settlement()
    settlement["actual_sources"][0]["published_at"] = "2021-08-31T18:00:01+08:00"
    assert validate_settlement(settlement, case=_case())["state"] == "REVIEWABLE"

    ambiguous = _case()
    ambiguous["sources"][0]["published_at"] = "2021-08-31"
    result = validate_case(ambiguous)
    assert "sources[0]:published_at_time_required_on_cutoff_date" in result["incomplete_findings"]


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


def test_calibration_ledger_requires_a_period_and_accounting_basis() -> None:
    case = _case()
    del case["calibration_ledger"]["claims"][0]["observable_outcome"]["measurement_basis"]
    result = validate_case(case)
    assert "calibration_ledger.claims[0].observable_outcome:missing:measurement_basis" in result["incomplete_findings"]

    case = _case()
    case["calibration_ledger"]["claims"][0]["prediction"]["unit"] = "RMB/share"
    result = validate_case(case)
    assert "calibration_ledger.claims[0].prediction:unit_does_not_match_observable_outcome" in result["invalid_findings"]

    case = _case()
    case["calibration_ledger"]["claims"][0]["observable_outcome"]["period_start"] = "2022-01-01"
    result = validate_case(case)
    assert "calibration_ledger.claims[0].observable_outcome:period_start_after_period_end" in result["invalid_findings"]


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
    after_cutoff["actual_sources"][0]["published_at"] = "2021-08-31T18:00:00+08:00"
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


def test_settlement_rejects_operating_metric_basis_period_and_source_drift() -> None:
    case = _case()
    settlement = _settlement()

    metric_drift = deepcopy(settlement)
    metric_drift["actual_outcomes"]["operating_observations"][0]["metric"] = "reported_revenue"
    result = validate_settlement(metric_drift, case=case)
    assert "actual_outcomes.operating_observations[0]:metric_does_not_match_frozen_contract" in result["invalid_findings"]

    basis_drift = deepcopy(settlement)
    basis_drift["actual_outcomes"]["operating_observations"][0]["measurement_basis"] = "reported_net_income"
    result = validate_settlement(basis_drift, case=case)
    assert "actual_outcomes.operating_observations[0]:measurement_basis_does_not_match_frozen_contract" in result["invalid_findings"]

    period_drift = deepcopy(settlement)
    period_drift["actual_outcomes"]["operating_observations"][0]["period_end"] = "2022-12-31"
    result = validate_settlement(period_drift, case=case)
    assert "actual_outcomes.operating_observations[0]:period_end_does_not_match_frozen_contract" in result["invalid_findings"]

    source_drift = deepcopy(settlement)
    source_drift["actual_sources"][0]["source_type"] = "OFFICIAL_STATISTICS"
    result = validate_settlement(source_drift, case=case)
    assert "actual_outcomes.operating_observations[0]:source_type_not_allowed_for_frozen_contract:AR:00506:2021" in result["invalid_findings"]

    report_period_drift = deepcopy(settlement)
    report_period_drift["actual_sources"][0]["data_as_of"] = "2020-12-31"
    result = validate_settlement(report_period_drift, case=case)
    assert "actual_outcomes.operating_observations[0]:report_source_period_does_not_match_observation:AR:00506:2021" in result["invalid_findings"]


def test_convertible_observation_requires_a_frozen_replayable_rule() -> None:
    case = _case()
    settlement = _settlement()
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation["comparability_status"] = "CONVERTIBLE_WITH_PREREGISTERED_RULE"
    result = validate_settlement(settlement, case=case)
    assert "actual_outcomes.operating_observations[0]:conversion_rule_not_preregistered" in result["invalid_findings"]

    case["calibration_ledger"]["claims"][0]["observable_outcome"]["conversion_rule"] = {
        "rule_id": "HBTCONV:owner-cash-per-100-shares",
        "raw_unit": "HKD/100 shares",
        "converted_unit": "HKD/share",
        "multiplier": 0.01,
    }
    observation.update({
        "raw_value": 18.0,
        "raw_unit": "HKD/100 shares",
        "conversion_rule_id": "HBTCONV:owner-cash-per-100-shares",
    })
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"


def test_forecast_error_must_reference_the_same_operating_observation() -> None:
    case = _case()
    settlement = _settlement()
    settlement["model_forecast_error"]["metrics"][0]["actual_value"] = 0.19
    result = validate_settlement(settlement, case=case)
    assert "model_forecast_error.metrics[0]:actual_value_does_not_match_operating_observation" in result["invalid_findings"]

    settlement = _settlement()
    settlement["model_forecast_error"]["metrics"][0]["observation_id"] = "HBTOBS:missing"
    result = validate_settlement(settlement, case=case)
    assert "model_forecast_error.metrics[0]:observation_id_not_found:HBTOBS:missing" in result["invalid_findings"]


def test_settlement_requires_an_explicit_outcome_for_every_frozen_claim() -> None:
    missing_prediction = _case()
    extra_prediction = deepcopy(missing_prediction["calibration_ledger"]["claims"][0])
    extra_prediction["claim_id"] = "HBTCLM:omitted-prediction"
    missing_prediction["calibration_ledger"]["claims"].append(extra_prediction)
    result = validate_settlement(_settlement(), case=missing_prediction)
    assert result["state"] == "INVALID"
    assert "model_forecast_error.claim_settlements:missing_frozen_claim:HBTCLM:omitted-prediction" in result["incomplete_findings"]

    missing_unknown = _case()
    extra_unknown = deepcopy(missing_unknown["calibration_ledger"]["claims"][1])
    extra_unknown["claim_id"] = "HBTCLM:omitted-unknown"
    missing_unknown["calibration_ledger"]["claims"].append(extra_unknown)
    result = validate_settlement(_settlement(), case=missing_unknown)
    assert result["state"] == "INVALID"
    assert "model_forecast_error.claim_settlements:missing_frozen_claim:HBTCLM:omitted-unknown" in result["incomplete_findings"]


def test_comparable_observations_cannot_be_dropped_from_prediction_or_unknown_settlement() -> None:
    case = _case()
    dropped_prediction = deepcopy(case["calibration_ledger"]["claims"][0])
    dropped_prediction["claim_id"] = "HBTCLM:dropped-despite-observation"
    case["calibration_ledger"]["claims"].append(dropped_prediction)
    settlement = _settlement()
    observation = deepcopy(settlement["actual_outcomes"]["operating_observations"][0])
    observation.update({
        "observation_id": "HBTOBS:dropped-despite-observation",
        "claim_id": "HBTCLM:dropped-despite-observation",
        "value": 0.01,
    })
    settlement["actual_outcomes"]["operating_observations"].append(observation)
    settlement["model_forecast_error"]["claim_settlements"].append({
        "claim_id": "HBTCLM:dropped-despite-observation",
        "frozen_disposition": "PREDICTION",
        "status": "NOT_CALCULABLE",
        "observation_ids": [],
    })
    settlement["model_forecast_error"]["status"] = "PARTIAL"
    result = validate_settlement(settlement, case=case)
    assert "model_forecast_error.claim_settlements[2]:comparable_observation_requires_calculated_status" in result["invalid_findings"]
    assert "model_forecast_error.claim_settlements[2]:comparable_observation_not_registered:HBTOBS:dropped-despite-observation" in result["invalid_findings"]

    case = _case()
    settlement = _settlement()
    unknown = case["calibration_ledger"]["claims"][1]
    unknown_observation = deepcopy(settlement["actual_outcomes"]["operating_observations"][0])
    unknown_observation.update({
        "observation_id": "HBTOBS:minority-cash-access:FY2021",
        "claim_id": unknown["claim_id"],
        "metric": unknown["observable_outcome"]["metric"],
        "value": 0.4,
        "unit": unknown["observable_outcome"]["unit"],
        "measurement_basis": unknown["observable_outcome"]["measurement_basis"],
        "period_start": unknown["observable_outcome"]["period_start"],
        "period_end": unknown["observable_outcome"]["period_end"],
    })
    settlement["actual_outcomes"]["operating_observations"].append(unknown_observation)
    result = validate_settlement(settlement, case=case)
    assert "model_forecast_error.claim_settlements[1]:comparable_observation_requires_resolution_status" in result["invalid_findings"]
    assert "model_forecast_error.claim_settlements[1]:comparable_observation_not_registered:HBTOBS:minority-cash-access:FY2021" in result["invalid_findings"]


def test_initial_disclosure_policy_rejects_a_later_restatement_as_actual() -> None:
    settlement = _settlement()
    settlement["actual_sources"].append({
        "source_id": "AR:00506:2021:RESTATED",
        "source_type": "ANNUAL_REPORT",
        "official": True,
        "published_at": "2022-06-01",
        "source_version": "annual-report-restated-2021",
        "data_as_of": "2021-12-31",
    })
    settlement["operating_source_timeline"]["source_ids"].append("AR:00506:2021:RESTATED")
    restated_observation = deepcopy(settlement["actual_outcomes"]["operating_observations"][0])
    restated_observation.update({
        "observation_id": "HBTOBS:owner-cash:FY2021:restated",
        "value": 0.30,
        "source_ids": ["AR:00506:2021:RESTATED"],
    })
    settlement["actual_outcomes"]["operating_observations"].append(restated_observation)
    settlement["model_forecast_error"]["claim_settlements"][0]["observation_ids"] = [
        "HBTOBS:owner-cash:FY2021:restated",
    ]
    settlement["model_forecast_error"]["metrics"][0].update({
        "observation_id": "HBTOBS:owner-cash:FY2021:restated",
        "actual_value": 0.30,
        "actual_source_ids": ["AR:00506:2021:RESTATED"],
    })
    result = validate_settlement(settlement, case=_case())
    assert "model_forecast_error.metrics[0]:does_not_use_initial_disclosure_per_frozen_policy" in result["invalid_findings"]


def test_version_policy_requires_a_provable_order_for_same_day_disclosures() -> None:
    settlement = _settlement()
    settlement["actual_sources"].append({
        "source_id": "AR:00506:2021:SAME_DAY_REVISION",
        "source_type": "ANNUAL_REPORT",
        "official": True,
        "published_at": "2022-03-25",
        "source_version": "annual-report-revision-2021",
        "data_as_of": "2021-12-31",
    })
    settlement["operating_source_timeline"]["source_ids"].append("AR:00506:2021:SAME_DAY_REVISION")
    revision_observation = deepcopy(settlement["actual_outcomes"]["operating_observations"][0])
    revision_observation.update({
        "observation_id": "HBTOBS:owner-cash:FY2021:same-day-revision",
        "value": 0.30,
        "source_ids": ["AR:00506:2021:SAME_DAY_REVISION"],
    })
    settlement["actual_outcomes"]["operating_observations"].append(revision_observation)
    settlement["model_forecast_error"]["claim_settlements"][0]["observation_ids"] = [
        "HBTOBS:owner-cash:FY2021:same-day-revision",
    ]
    settlement["model_forecast_error"]["metrics"][0].update({
        "observation_id": "HBTOBS:owner-cash:FY2021:same-day-revision",
        "actual_value": 0.30,
        "actual_source_ids": ["AR:00506:2021:SAME_DAY_REVISION"],
    })
    result = validate_settlement(settlement, case=_case())
    assert result["state"] == "INVALID"
    assert "model_forecast_error.metrics[0]:publication_order_ambiguous" in result["incomplete_findings"]


def test_return_settlement_binds_frozen_action_price_identity_and_execution_rule() -> None:
    case = _case()

    changed_action = _settlement()
    changed_action["investment_return_outcome"]["action"] = "WAIT"
    result = validate_settlement(changed_action, case=case)
    assert "investment_return_outcome:action_does_not_match_frozen_action" in result["invalid_findings"]

    changed_price = _settlement()
    changed_price["investment_return_outcome"]["frozen_price_identity"] = "P_XIRR"
    result = validate_settlement(changed_price, case=case)
    assert "investment_return_outcome:frozen_price_identity_does_not_match_case" in result["invalid_findings"]

    changed_rule = _settlement()
    changed_rule["investment_return_outcome"]["execution"]["execution_rule"] = "等待事后最低价。"
    result = validate_settlement(changed_rule, case=case)
    assert "investment_return_outcome.execution:rule_does_not_match_frozen_action" in result["invalid_findings"]


def test_return_settlement_reconciles_cash_flows_policy_and_corporate_action_links() -> None:
    case = _case()

    changed_cash = _settlement()
    changed_cash["investment_return_outcome"]["cash_flow_ledger"][1]["net_amount"] = 10.0
    result = validate_settlement(changed_cash, case=case)
    assert "investment_return_outcome.cash_flow_ledger[1]:net_amount_does_not_reconcile" in result["invalid_findings"]

    changed_policy = _settlement()
    changed_policy["investment_return_outcome"]["taxes_fees_fx"]["dividend_tax_rate"] = 0.0
    result = validate_settlement(changed_policy, case=case)
    assert "investment_return_outcome.taxes_fees_fx:dividend_tax_rate_does_not_match_frozen_case" in result["invalid_findings"]

    broken_action_link = _settlement()
    broken_action_link["investment_return_outcome"]["corporate_actions"][0]["cash_flow_ids"] = []
    result = validate_settlement(broken_action_link, case=case)
    assert "investment_return_outcome.corporate_actions[0]:cash_dividend_flow_link_missing" in result["incomplete_findings"]
    assert "investment_return_outcome.cash_flow_ledger:corporate_action_link_not_bidirectional:HBTFLW:dividend" in result["invalid_findings"]


def test_return_settlement_requires_official_benchmark_identity_source() -> None:
    settlement = _settlement()
    settlement["investment_return_outcome"]["benchmark_identity"]["source_ids"] = ["AR:00506:2021"]
    result = validate_settlement(settlement, case=_case())
    assert "investment_return_outcome.benchmark_identity:official_market_data_source_required" in result["invalid_findings"]


def test_checked_in_pilot_config_matches_builder() -> None:
    path = Path(__file__).parents[1] / "config" / "historical_backtest_pilot.v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert validate_experiment(payload)["state"] == "REVIEWABLE"
    assert payload["universe"]["eligible_case_count"] == 0
