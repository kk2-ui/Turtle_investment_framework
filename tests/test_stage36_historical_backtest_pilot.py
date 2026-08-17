from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path

import scripts.historical_backtest as historical_backtest
import scripts.phase10_pit_runner as phase10_pit_runner
from scripts.phase10_acquisition import enumerate_sse_announcements
from scripts.historical_backtest import (
    CASE_SCHEMA_VERSION,
    SETTLEMENT_SCHEMA_VERSION,
    _validate_production_report_origin,
    build_pilot_experiment,
    validate_case,
    validate_experiment,
    validate_pilot,
    validate_settlement,
)
from scripts.phase10_pit_runner import PITSourcePackage
from scripts.real_report_acceptance import (
    REQUIRED_MACHINE_GATES,
    evaluate_phase10_production_freeze_acceptance,
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
            "mode": "TEST_FIXTURE",
            "freeze_id": "HBTFRZ:d705bf29a4c72fb1",
            "frozen_report": {
                "report_id": "HBTREP:TEST",
                "variant_id": "d705bf29a4c72fb1",
                "origin": {"kind": "TEST_FIXTURE"},
                "artifact_path": "tests/fixtures/historical_backtest_frozen_report.md",
                "artifact_sha256": "d705bf29a4c72fb18f6cb77c7d3834a2b130d6ff4c9c5c06b4b13b808b15bb98",
                "format": "MARKDOWN",
                "writer_id": "writer:test",
                "writer_provenance": {
                    "actor_type": "human",
                    "context_id": "writer-context:test",
                },
                "writer_status": "COMPLETE",
                "claim_ids": ["HBTCLM:owner-cash", "HBTCLM:minority-cash-access"],
                "section_markers": [
                    "## Evidence", "## Operating forecast", "## Valuation", "## Risks and unknowns", "## Decision",
                ],
            },
            "independent_review": {
                "review_id": "HBTREV:d705bf29a4c72fb1",
                "reviewed_variant_id": "d705bf29a4c72fb1",
                "reviewer_id": "reviewer:test",
                "reviewer_provenance": {
                    "actor_type": "human",
                    "context_id": "reviewer-context:test",
                },
                "independence": {
                    "did_not_generate_candidate": True,
                    "no_prior_review_seen": True,
                    "reviewer_context_isolated": True,
                    "generator_identity_disjoint": True,
                },
                "reviewed_report_sha256": "d705bf29a4c72fb18f6cb77c7d3834a2b130d6ff4c9c5c06b4b13b808b15bb98",
                "status": "PASS",
                "claim_reviews": [{
                    "claim_id": "HBTCLM:owner-cash",
                    "disposition": "SUPPORTED",
                    "source_ids": ["AR:00506:2020"],
                    "notes": ["预测、阈值和口径已冻结。"],
                }, {
                    "claim_id": "HBTCLM:minority-cash-access",
                    "disposition": "UNKNOWN_PRESERVED",
                    "source_ids": ["AR:00506:2020"],
                    "notes": ["未知及其经济影响被保留。"],
                }],
            },
            "quality_failure": None,
        },
        "credibility": {
            "model_memory_control": "UNCONTROLLED",
            "backtest_credibility": "EXPLORATORY",
            "assessment_basis": "这是用于验证冻结与结算契约的工程 replay；没有参数记忆隔离证据。",
            "control_evidence": [],
            "calibration_role": "ENGINEERING_DIAGNOSTIC_ONLY",
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
        "freeze_id": "HBTFRZ:d705bf29a4c72fb1",
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
            "status": "PASS",
            "review_id": "HBTREV:d705bf29a4c72fb1",
            "claim_reviews": [{
                "claim_id": "HBTCLM:owner-cash",
                "disposition": "SUPPORTED",
                "source_ids": ["AR:00506:2020"],
            }, {
                "claim_id": "HBTCLM:minority-cash-access",
                "disposition": "UNKNOWN_PRESERVED",
                "source_ids": ["AR:00506:2020"],
            }],
            "supported_claim_count": 1,
            "unsupported_claim_count": 0,
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
    assert experiment["universe"]["calibration_eligible_case_count"] == 0
    assert len(experiment["universe"]["cases"]) == 9
    assert experiment["framework"]["golden_gate_state"] == "G3_NOT_READY"
    assert experiment["credibility"]["model_memory_control"] == "UNCONTROLLED"
    assert experiment["credibility"]["backtest_credibility"] == "EXPLORATORY"
    assert experiment["credibility"]["calibration_role"] == "ENGINEERING_DIAGNOSTIC_ONLY"
    assert validate_pilot()["pilot_is_empty"] is True


def test_model_memory_contract_keeps_exploratory_cases_reviewable_but_rejects_unsupported_strictness() -> None:
    case = _case()
    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(_settlement(), case=case)["state"] == "REVIEWABLE"

    unsupported_strict = _case()
    unsupported_strict["credibility"].update({
        "model_memory_control": "CONTROLLED",
        "backtest_credibility": "STRICT",
        "calibration_role": "MODEL_MEMORY_CONTROLLED_CANDIDATE",
        "control_evidence": ["a free-text assertion is not evidence"],
    })
    result = validate_case(unsupported_strict)
    assert result["state"] == "INVALID"
    assert "credibility.control_evidence[0]:not_object" in result["invalid_findings"]

    no_control_evidence = _case()
    no_control_evidence["credibility"].update({
        "model_memory_control": "CONTROLLED",
        "backtest_credibility": "STRICT",
        "calibration_role": "MODEL_MEMORY_CONTROLLED_CANDIDATE",
    })
    result = validate_case(no_control_evidence)
    assert "credibility:controlled_or_mitigated_memory_requires_control_evidence" in result["invalid_findings"]

    mitigated = _case()
    mitigated["credibility"].update({
        "model_memory_control": "MITIGATED",
        "backtest_credibility": "QUALIFIED",
        "control_evidence": [{
            "evidence_id": "HBTMEM:TEST:mitigated",
            "artifact_path": "tests/fixtures/historical_backtest_model_memory_control.md",
            "artifact_sha256": "eaf9a93c721bfd117683b034a22474ffc1afcf265334d9f497bf1258b8bba10c",
            "control_level": "MITIGATION",
            "method": "公司名称和证券代码已从模型上下文删除。",
            "verifier_id": "reviewer:memory-control",
            "scope": "仅覆盖本夹具的受控回归上下文。",
        }],
    })
    assert validate_case(mitigated)["state"] == "REVIEWABLE"

    strict_candidate = deepcopy(mitigated)
    strict_candidate["credibility"].update({
        "model_memory_control": "CONTROLLED",
        "backtest_credibility": "STRICT",
        "calibration_role": "MODEL_MEMORY_CONTROLLED_CANDIDATE",
        "control_evidence": [{
            "evidence_id": "HBTMEM:TEST:controlled",
            "artifact_path": "tests/fixtures/historical_backtest_model_memory_controlled.md",
            "artifact_sha256": "45c3c44341cf07cc8f5d0aa4a279384bc0f7ee006e4d00b8c866ba2a983f716d",
            "control_level": "CONTROL",
            "method": "隔离评测模型与历史发行人训练语料。",
            "verifier_id": "reviewer:memory-control",
            "scope": "仅覆盖本夹具的受控回归上下文。",
        }],
    })
    result = validate_case(strict_candidate)
    assert result["state"] == "INCOMPLETE"
    assert "credibility:experiment_required_for_calibration_candidate" in result["incomplete_findings"]
    uncontrolled_experiment = build_pilot_experiment()
    uncontrolled_experiment["experiment_id"] = "HBT:test"
    result = validate_case(strict_candidate, experiment=uncontrolled_experiment)
    assert "credibility:model_memory_control_does_not_match_experiment" in result["invalid_findings"]

    controlled_experiment = deepcopy(uncontrolled_experiment)
    controlled_experiment["credibility"] = deepcopy(strict_candidate["credibility"])
    controlled_experiment["universe"] = {
        "selection_status": "PRE_REGISTERED",
        "eligible_case_count": 1,
        "calibration_eligible_case_count": 1,
        "cases": [{
            "case_id": "HBTCASE:TEST",
            "company_code": "00506.HK",
            "company_name": "测试公司",
            "simulation_cutoff": "2021-08-31T18:00:00+08:00",
            "eligibility_status": "ELIGIBLE",
            "eligibility_reason": "受控回归夹具。",
            "calibration_eligibility": "MODEL_MEMORY_CONTROLLED_CANDIDATE",
            "route": "LONG_TERM_OWNER",
        }],
    }
    assert validate_experiment(controlled_experiment)["state"] == "REVIEWABLE"
    assert validate_case(strict_candidate, experiment=controlled_experiment)["state"] == "REVIEWABLE"

    false_calibration_role = _case()
    false_calibration_role["credibility"]["calibration_role"] = "MODEL_MEMORY_CONTROLLED_CANDIDATE"
    result = validate_case(false_calibration_role)
    assert "credibility:calibration_role_inconsistent_with_model_memory_control" in result["invalid_findings"]

    uncontrolled_experiment["universe"]["cases"][0].update({
        "eligibility_status": "ELIGIBLE",
        "route": "LONG_TERM_OWNER",
        "calibration_eligibility": "MODEL_MEMORY_CONTROLLED_CANDIDATE",
    })
    uncontrolled_experiment["universe"]["eligible_case_count"] = 1
    uncontrolled_experiment["universe"]["calibration_eligible_case_count"] = 1
    result = validate_experiment(uncontrolled_experiment)
    assert result["state"] == "INVALID"
    assert "universe.cases[0]:experiment_model_memory_not_controlled_for_calibration" in result["invalid_findings"]


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


def test_frozen_case_requires_readable_report_and_independent_claim_review() -> None:
    missing_report = _case()
    del missing_report["report_freeze"]["frozen_report"]
    result = validate_case(missing_report)
    assert result["state"] != "REVIEWABLE"
    assert "report_freeze.frozen_report:missing:artifact_path" in result["incomplete_findings"]

    same_reviewer = _case()
    same_reviewer["report_freeze"]["independent_review"]["reviewer_id"] = "writer:test"
    result = validate_case(same_reviewer)
    assert "report_freeze.independent_review:reviewer_must_be_independent_from_writer" in result["invalid_findings"]

    same_context = _case()
    same_context["report_freeze"]["independent_review"]["reviewer_provenance"]["context_id"] = "writer-context:test"
    result = validate_case(same_context)
    assert "report_freeze.independent_review:reviewer_context_must_differ_from_writer" in result["invalid_findings"]

    thin_report = _case()
    thin_report["report_freeze"]["frozen_report"].update({
        "artifact_path": "tests/fixtures/historical_backtest_thin_report.md",
        "variant_id": "4ce31d58584a4da3",
        "artifact_sha256": "4ce31d58584a4da3b8a2c41b039cd91e25e8c170572988dc4a054133a7ca18d8",
    })
    thin_report["report_freeze"]["freeze_id"] = "HBTFRZ:4ce31d58584a4da3"
    thin_report["report_freeze"]["independent_review"]["review_id"] = "HBTREV:4ce31d58584a4da3"
    thin_report["report_freeze"]["independent_review"]["reviewed_variant_id"] = "4ce31d58584a4da3"
    thin_report["report_freeze"]["independent_review"]["reviewed_report_sha256"] = "4ce31d58584a4da3b8a2c41b039cd91e25e8c170572988dc4a054133a7ca18d8"
    result = validate_case(thin_report)
    assert result["state"] != "REVIEWABLE"
    assert "report_freeze.frozen_report:artifact_section_missing:## Evidence" in result["incomplete_findings"]

    altered_report_identity = _case()
    altered_report_identity["report_freeze"]["frozen_report"]["artifact_sha256"] = "0" * 64
    result = validate_case(altered_report_identity)
    assert "report_freeze.frozen_report:artifact_sha256_mismatch" in result["invalid_findings"]

    partial_prediction = _case()
    partial_prediction["report_freeze"]["independent_review"]["claim_reviews"][0]["disposition"] = "PARTIAL"
    result = validate_case(partial_prediction)
    assert "report_freeze.independent_review:partial_prediction_cannot_be_frozen" in result["invalid_findings"]

    quality_failure = _case()
    quality_failure["status"] = "FROZEN_WITH_QUALITY_FAILURE"
    quality_failure["report_freeze"]["report_status"] = "FROZEN_WITH_QUALITY_FAILURE"
    quality_failure["report_freeze"]["frozen_report"]["writer_status"] = "QUALITY_FAILURE"
    quality_failure["report_freeze"]["independent_review"]["status"] = "FAIL"
    quality_failure["report_freeze"]["quality_failure"] = {
        "classifications": ["DATA_COVERAGE"],
        "economic_impact": "缺少债务期限事实会影响普通股永久损失判断。",
        "missing_facts": ["截止日前的债务到期明细。"],
        "prohibited_assumptions": ["不得以当前债务重述替代历史披露。"],
        "remediation": "补全截止日前官方年报和交易所公告。",
        "acceptance_criteria": "每条债务 claim 有对应官方来源和独立审阅结论。",
    }
    result = validate_case(quality_failure)
    assert result["state"] == "INCOMPLETE"
    assert "case_frozen_with_quality_failure" in result["incomplete_findings"]


def test_report_variant_lifecycle_rejects_reused_review_identity() -> None:
    case = _case()
    new_variant = "0" * 16
    case["report_freeze"]["frozen_report"]["variant_id"] = new_variant
    case["report_freeze"]["freeze_id"] = "HBTFRZ:" + new_variant
    result = validate_case(case)
    assert "report_freeze.independent_review:reviewed_variant_id_mismatch" in result["invalid_findings"]
    assert "report_freeze.independent_review:review_id_must_bind_report_variant" in result["invalid_findings"]


def test_test_fixture_report_and_memory_evidence_cannot_enter_real_case() -> None:
    case = _case()
    result = validate_case(case, allow_test_fixtures=False)
    assert "report_freeze.frozen_report:test_fixture_requires_explicit_allowance" in result["invalid_findings"]

    case = _case()
    case["case_id"] = "HBTCASE:600340"
    result = validate_case(case)
    assert "report_freeze.frozen_report:test_fixture_forbidden_outside_test_case" in result["invalid_findings"]

    controlled = _case()
    controlled["case_id"] = "HBTCASE:600340"
    controlled["credibility"].update({
        "model_memory_control": "CONTROLLED",
        "backtest_credibility": "STRICT",
        "calibration_role": "MODEL_MEMORY_CONTROLLED_CANDIDATE",
        "control_evidence": [{
            "evidence_id": "HBTMEM:TEST:controlled",
            "artifact_path": "tests/fixtures/historical_backtest_model_memory_controlled.md",
            "artifact_sha256": "45c3c44341cf07cc8f5d0aa4a279384bc0f7ee006e4d00b8c866ba2a983f716d",
            "control_level": "CONTROL",
            "method": "隔离评测模型与历史发行人训练语料。",
            "verifier_id": "reviewer:memory-control",
            "scope": "仅覆盖本夹具的受控回归上下文。",
        }],
    })
    result = validate_case(controlled)
    assert "credibility.control_evidence[0]:test_fixture_forbidden_outside_test_namespace" in result["invalid_findings"]
    assert "credibility:controlled_memory_requires_deployment_attestation" in result["incomplete_findings"]


def test_production_report_requires_pipeline_acceptance_artifacts() -> None:
    case = _case()
    case["case_id"] = "HBTCASE:600340"
    report = case["report_freeze"]["frozen_report"]
    case["report_freeze"]["mode"] = "PRODUCTION_PIPELINE"
    report["origin"] = {
        "kind": "TURTLE_PIPELINE",
        "output_dir": "output/historical/600340",
        "acceptance_root": "output/.acceptance/phase08",
        "sample_id": "600340",
        "run_manifest_path": "output/historical/600340/run_manifest.json",
        "completion_report_path": "output/historical/600340/completion_report.json",
        "publication_snapshot_path": "output/historical/600340/publication_snapshot.json",
    }
    result = validate_case(case)
    assert "report_freeze.frozen_report.origin:acceptance_sample_not_unique" in result["invalid_findings"]
    assert "report_freeze.frozen_report.origin.pit_runner:missing:attestation_path" in result["incomplete_findings"]
    assert "report_freeze.frozen_report.origin.pit_runner:tool_boundary_not_integrated" in result["incomplete_findings"]


def test_production_origin_accepts_only_pit_production_freeze(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "repository"
    package = root / "historical" / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual" / "2020.pdf").write_bytes(b"%PDF-original")
    (package / "annual" / "2020.pages.md").write_text(
        "# AR:00506:2020\n\n"
        "- source_id: AR:00506:2020\n"
        "- source_version: annual-report-original-2020\n"
        "- content_representation: PDF_PAGE_MARKDOWN\n\n"
        "## 第 1 页\n\n历史年报正文\n",
        encoding="utf-8",
    )
    framework_root = root / "config" / "phase10_pit_framework" / "framework"
    framework_root.mkdir(parents=True)
    (framework_root / "policy.md").write_text("PIT policy", encoding="utf-8")
    monkeypatch.setattr(phase10_pit_runner, "PIT_STATIC_FRAMEWORK_ROOT", framework_root.parent)
    monkeypatch.setattr(historical_backtest, "__file__", str(root / "scripts" / "historical_backtest.py"))

    manifest = enumerate_sse_announcements([{
        "source_id": "AR:00506:2020",
        "source_version": "annual-report-original-2020",
        "source_type": "ANNUAL_REPORT",
        "title": "2020 年年度报告",
        "published_at": "2021-03-25",
        "data_as_of": "2020-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
    }], cutoff_at="2021-08-31T18:00:00+08:00", period_start="2021-01-01")
    manifest["company_code"] = "00506.HK"
    for source in [*manifest["inventory"], *manifest["sources"]]:
        source.update({
            "package_path": "annual/2020.pdf",
            "content_representation": "PDF_PAGE_MARKDOWN",
            "reader_text_path": "annual/2020.pages.md",
            "reader_text_extractor": "pdf_preprocessor.extract_all_pages",
            "reader_text_extractor_version": "phase10-pdf-page-markdown.v1",
            "reader_text_page_count": 1,
        })
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    manifest_path = root / "historical" / "source-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    runner = PITSourcePackage(
        manifest,
        package,
        case_id="HBTCASE:TEST",
        experiment_id="HBT:test",
        run_id="pit-production-test",
        manifest_path=str(manifest_path),
    )
    assert runner.state == "REVIEWABLE"
    runner.read_framework("framework/policy.md")
    runner.read_source("AR:00506:2020")

    output = root / "pipeline-output"
    report_path = output / "reports" / "00506_分析报告_v13.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Production PIT report\n", encoding="utf-8")
    report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    (output / "run_manifest.json").write_text(json.dumps({
        "run_id": "pit-production-test",
        "status": "COMPLETED",
    }), encoding="utf-8")
    (output / "completion_report.json").write_text(json.dumps({
        "status": "COMPLETE",
        "validators": {"publication_snapshot": {"written": True}},
    }), encoding="utf-8")
    (output / "publication_snapshot.json").write_text(json.dumps({
        "report_sha256": report_sha256,
        "run_id": "pit-production-test",
        "completion_status": "COMPLETE",
        "v3_enforced": True,
    }), encoding="utf-8")
    for gate, (filename, accepted) in REQUIRED_MACHINE_GATES.items():
        if gate in {"completion", "runtime_manifest"}:
            continue
        key = "status" if gate in {"completion", "runtime_manifest", "absolute_quality"} else "state"
        (output / filename).write_text(json.dumps({key: sorted(accepted)[0]}), encoding="utf-8")
    (output / "research_execution.json").write_text(json.dumps({
        "enforced": True,
        "chapters": {"2": {
            "enforced": True,
            "tool_counts": {"read_section": 2},
            "fiscal_years": [2019, 2020],
            "sections": ["MDA", "STMT"],
        }},
    }), encoding="utf-8")
    (output / "judgment_review_validation.json").write_text(json.dumps({
        "state": "REVIEWED", "ceiling_verdict": "COMPETENT",
    }), encoding="utf-8")
    (output / "judgment_review.json").write_text(json.dumps({
        "ceiling_verdict": "COMPETENT", "fragile_leaps": [], "dimension_assessments": {},
    }), encoding="utf-8")
    acceptance_root = root / "acceptance"
    acceptance = evaluate_phase10_production_freeze_acceptance(
        sample_id="00506",
        company_code="00506.HK",
        output_dir=output,
        report_period="PIT-2021-08-31",
        acceptance_root=acceptance_root,
    )
    assert acceptance["samples"][0]["machine_status"] == "READY_FOR_BLIND_REVIEW"

    attestation = runner.attestation()
    attestation.update({
        "execution_mode": "PIT_PRODUCTION_FREEZE",
        "writer": {
            "run_id": "pit-production-test",
            "case_id": "HBTCASE:TEST",
            "experiment_id": "HBT:test",
            "final_report_path": str(report_path),
            "source_anchor_ids": ["AR:00506:2020"],
            "read_source_ids": ["AR:00506:2020"],
        },
    })
    attestation_path = root / "historical" / "pit-attestation.json"
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    record = {
        "case_id": "HBTCASE:TEST",
        "experiment_id": "HBT:test",
        "company_code": "00506.HK",
        "simulation_cutoff": "2021-08-31T18:00:00+08:00",
        "report_freeze": {
            "evidence_cutoff": "2021-08-31T18:00:00+08:00",
            "report_status": "FROZEN",
        },
        "sources": [{
            "source_id": "AR:00506:2020",
            "source_version": "annual-report-original-2020",
            "published_at": "2021-03-25",
            "data_as_of": "2020-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
        }],
    }
    origin = {
        "output_dir": "pipeline-output",
        "acceptance_root": "acceptance",
        "sample_id": "00506",
        "run_manifest_path": "pipeline-output/run_manifest.json",
        "completion_report_path": "pipeline-output/completion_report.json",
        "publication_snapshot_path": "pipeline-output/publication_snapshot.json",
        "pit_runner": {
            "attestation_path": "historical/pit-attestation.json",
            "source_package_manifest_path": "historical/source-manifest.json",
            "package_root": "historical/package",
            "status": "PASS",
        },
    }
    report = {
        "artifact_path": "pipeline-output/reports/00506_分析报告_v13.md",
        "variant_id": report_sha256[:16],
    }

    invalid, incomplete = _validate_production_report_origin(
        record, report=report, artifact_sha256=report_sha256, origin=origin,
    )
    assert invalid == []
    assert incomplete == []

    config_path = acceptance_root / "phase10_production_freeze_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["phase"] = "other-phase"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    invalid, incomplete = _validate_production_report_origin(
        record, report=report, artifact_sha256=report_sha256, origin=origin,
    )
    assert "report_freeze.frozen_report.origin:phase10_acceptance_config_phase_invalid" in invalid
    assert incomplete == []
    config["phase"] = "10-production-freeze"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    attestation["writer"]["run_id"] = "different-production-run"
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    invalid, incomplete = _validate_production_report_origin(
        record, report=report, artifact_sha256=report_sha256, origin=origin,
    )
    assert "report_freeze.frozen_report.origin.pit_runner:writer_run_id_mismatch" in invalid
    assert incomplete == []

    attestation["writer"]["run_id"] = "pit-production-test"
    attestation["writer"]["source_anchor_ids"] = ["AR:missing"]
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    invalid, incomplete = _validate_production_report_origin(
        record, report=report, artifact_sha256=report_sha256, origin=origin,
    )
    assert "report_freeze.frozen_report.origin.pit_runner:writer_source_anchor_not_read" in invalid
    assert incomplete == []

    attestation["writer"]["source_anchor_ids"] = ["AR:00506:2020"]
    attestation["execution_mode"] = "PIT_WRITER"
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    invalid, incomplete = _validate_production_report_origin(
        record, report=report, artifact_sha256=report_sha256, origin=origin,
    )
    assert invalid == []
    assert "report_freeze.frozen_report.origin.pit_runner:tool_boundary_not_integrated" in incomplete


def test_production_origin_replays_pdf_page_markdown_source_reads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "repository"
    package = root / "historical" / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual" / "2019.pdf").write_bytes(b"%PDF-original")
    (package / "annual" / "2019.pages.md").write_text(
        "# AR:00506:2020\n\n"
        "- source_id: AR:00506:2020\n"
        "- source_version: annual-report-original-2020\n"
        "- content_representation: PDF_PAGE_MARKDOWN\n\n"
        "## 第 1 页\n\n历史年报正文\n",
        encoding="utf-8",
    )
    framework_root = root / "config" / "phase10_pit_framework" / "framework"
    framework_root.mkdir(parents=True)
    (framework_root / "policy.md").write_text("PIT policy", encoding="utf-8")
    monkeypatch.setattr(phase10_pit_runner, "PIT_STATIC_FRAMEWORK_ROOT", framework_root.parent)
    monkeypatch.setattr(historical_backtest, "__file__", str(root / "scripts" / "historical_backtest.py"))

    manifest = enumerate_sse_announcements([{
        "source_id": "AR:00506:2020",
        "source_version": "annual-report-original-2020",
        "source_type": "ANNUAL_REPORT",
        "title": "2020 年年度报告",
        "published_at": "2021-03-25",
        "data_as_of": "2020-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
    }], cutoff_at="2021-08-31T18:00:00+08:00", period_start="2021-01-01")
    for source in [*manifest["inventory"], *manifest["sources"]]:
        source.update({
            "package_path": "annual/2019.pdf",
            "content_representation": "PDF_PAGE_MARKDOWN",
            "reader_text_path": "annual/2019.pages.md",
            "reader_text_extractor": "pdf_preprocessor.extract_all_pages",
            "reader_text_extractor_version": "phase10-pdf-page-markdown.v1",
            "reader_text_page_count": 1,
        })
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    manifest_path = root / "historical" / "source-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    runner = PITSourcePackage(
        manifest,
        package,
        case_id="HBTCASE:TEST",
        experiment_id="HBT:test",
        run_id="pit-production-test",
        manifest_path=str(manifest_path),
    )
    assert runner.state == "REVIEWABLE"
    runner.read_source("AR:00506:2020")
    attestation_path = root / "historical" / "pit-attestation.json"
    attestation_path.write_text(json.dumps(runner.attestation()), encoding="utf-8")

    record = {
        "case_id": "HBTCASE:TEST",
        "experiment_id": "HBT:test",
        "company_code": "00506.HK",
        "simulation_cutoff": "2021-08-31T18:00:00+08:00",
        "report_freeze": {
            "evidence_cutoff": "2021-08-31T18:00:00+08:00",
            "report_status": "FROZEN",
        },
        "sources": [{
            "source_id": "AR:00506:2020",
            "source_version": "annual-report-original-2020",
            "published_at": "2021-03-25",
            "data_as_of": "2020-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
        }],
    }
    origin = {
        "output_dir": "pipeline-output",
        "acceptance_root": "acceptance",
        "sample_id": "00506",
        "run_manifest_path": "pipeline-output/run_manifest.json",
        "completion_report_path": "pipeline-output/completion_report.json",
        "publication_snapshot_path": "pipeline-output/publication_snapshot.json",
        "pit_runner": {
            "attestation_path": "historical/pit-attestation.json",
            "source_package_manifest_path": "historical/source-manifest.json",
            "package_root": "historical/package",
            "status": "PASS",
        },
    }
    invalid, _incomplete = _validate_production_report_origin(
        record,
        report={"artifact_path": "pipeline-output/report.md", "variant_id": "unused"},
        artifact_sha256="unused",
        origin=origin,
    )
    assert not any("source_path_mismatch" in finding for finding in invalid)
    assert not any("source_representation_mismatch" in finding for finding in invalid)
    assert not any("source_reader_text_path_mismatch" in finding for finding in invalid)


def test_pit_engineering_freeze_replays_writer_reads_but_cannot_settle_as_production(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "repository"
    package = root / "historical" / "package"
    (package / "annual").mkdir(parents=True)
    (package / "annual" / "2020.pdf").write_bytes(b"%PDF-original")
    (package / "annual" / "2020.pages.md").write_text(
        "# AR:00506:2020\n\n"
        "- source_id: AR:00506:2020\n"
        "- source_version: annual-report-original-2020\n"
        "- content_representation: PDF_PAGE_MARKDOWN\n\n"
        "## 第 1 页\n\n历史年报正文\n",
        encoding="utf-8",
    )
    framework_root = root / "config" / "phase10_pit_framework" / "framework"
    framework_root.mkdir(parents=True)
    (framework_root / "policy.md").write_text("PIT policy", encoding="utf-8")
    monkeypatch.setattr(phase10_pit_runner, "PIT_STATIC_FRAMEWORK_ROOT", framework_root.parent)
    monkeypatch.setattr(historical_backtest, "__file__", str(root / "scripts" / "historical_backtest.py"))

    manifest = enumerate_sse_announcements([{
        "source_id": "AR:00506:2020",
        "source_version": "annual-report-original-2020",
        "source_type": "ANNUAL_REPORT",
        "title": "2020 年年度报告",
        "published_at": "2021-03-25",
        "data_as_of": "2020-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
    }], cutoff_at="2021-08-31T18:00:00+08:00", period_start="2021-01-01")
    manifest["company_code"] = "00506.HK"
    for source in [*manifest["inventory"], *manifest["sources"]]:
        source.update({
            "package_path": "annual/2020.pdf",
            "content_representation": "PDF_PAGE_MARKDOWN",
            "reader_text_path": "annual/2020.pages.md",
            "reader_text_extractor": "pdf_preprocessor.extract_all_pages",
            "reader_text_extractor_version": "phase10-pdf-page-markdown.v1",
            "reader_text_page_count": 1,
        })
    manifest["framework_allowlist"] = [{"path": "framework/policy.md"}]
    manifest_path = root / "historical" / "source-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report_path = root / "historical" / "pit-engineering-report.md"
    report_path.write_text(
        "# PIT engineering report\n\n"
        "## Point-in-time scope\n\n"
        "HBTCASE:TEST only uses the registered source.\n\n"
        "## Evidence\n\nAR:00506:2020\n\n"
        "## Business and financial implications\n\n"
        "No production investment conclusion.\n\n"
        "## Unknowns and monitoring\n\n"
        "HBTCLM:owner-cash\nHBTCLM:minority-cash-access\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    runner = PITSourcePackage(
        manifest,
        package,
        case_id="HBTCASE:TEST",
        experiment_id="HBT:test",
        run_id="pit-engineering-test",
        manifest_path=str(manifest_path),
    )
    assert runner.state == "REVIEWABLE"
    runner.read_framework("framework/policy.md")
    runner.read_source("AR:00506:2020")
    attestation = runner.attestation()
    attestation.update({
        "execution_mode": "PIT_WRITER_TEST",
        "writer": {
            "status": "PASS",
            "report_path": str(report_path),
            "source_ids": ["AR:00506:2020"],
            "case_id": "HBTCASE:TEST",
            "experiment_id": "HBT:test",
        },
    })
    attestation_path = root / "historical" / "pit-attestation.json"
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    review_path = root / "historical" / "independent-review.md"
    review_path.write_text(
        "HBTCASE:TEST\n"
        "historical/pit-engineering-report.md\n"
        "PASS_AFTER_REPAIR_FOR_DRAFT_ONLY\n",
        encoding="utf-8",
    )

    case = _case()
    variant = digest[:16]
    case["report_freeze"].update({
        "mode": "PIT_ENGINEERING",
        "freeze_id": "HBTFRZ:" + variant,
    })
    case["report_freeze"]["frozen_report"].update({
        "report_id": "HBTREP:TEST:PIT_ENGINEERING",
        "variant_id": variant,
        "artifact_path": "historical/pit-engineering-report.md",
        "artifact_sha256": digest,
        "origin": {
            "kind": "PIT_ENGINEERING",
            "review_artifact_path": "historical/independent-review.md",
            "pit_runner": {
                "attestation_path": "historical/pit-attestation.json",
                "source_package_manifest_path": "historical/source-manifest.json",
                "package_root": "historical/package",
                "status": "PASS",
            },
        },
        "writer_provenance": {
            "actor_type": "model",
            "provider": "openai",
            "model": "gpt-5.6-terra",
            "context_id": "writer-context:test",
        },
        "section_markers": [
            "## Point-in-time scope", "## Evidence", "## Business and financial implications", "## Unknowns and monitoring",
        ],
    })
    case["report_freeze"]["independent_review"].update({
        "review_id": "HBTREV:" + variant,
        "reviewed_variant_id": variant,
        "reviewed_report_sha256": digest,
        "reviewer_provenance": {
            "actor_type": "model",
            "provider": "openai",
            "model": "gpt-5.6-terra",
            "context_id": "reviewer-context:test",
        },
    })
    result = validate_case(case)
    assert result["state"] == "REVIEWABLE", result

    quality_failure_review_path = root / "historical" / "quality-failure-review.md"
    quality_failure_review_path.write_text(
        "HBTCASE:TEST\n"
        "historical/pit-engineering-report.md\n"
        "FROZEN_WITH_QUALITY_FAILURE\n",
        encoding="utf-8",
    )
    quality_failure_case = deepcopy(case)
    quality_failure_case["status"] = "FROZEN_WITH_QUALITY_FAILURE"
    quality_failure_case["report_freeze"].update({
        "report_status": "FROZEN_WITH_QUALITY_FAILURE",
        "quality_failure": {
            "classifications": ["MODEL", "WRITING"],
            "economic_impact": "The engineering draft cannot support a production investment conclusion.",
            "missing_facts": ["Production-pipeline artifacts are unavailable."],
            "prohibited_assumptions": ["Do not infer a production decision from the engineering draft."],
            "remediation": "Integrate the PIT writer with the production report pipeline.",
            "acceptance_criteria": "A production-origin case passes its report and reviewer gates.",
        },
    })
    quality_failure_case["report_freeze"]["frozen_report"]["writer_status"] = "QUALITY_FAILURE"
    quality_failure_case["report_freeze"]["frozen_report"]["origin"]["review_artifact_path"] = "historical/quality-failure-review.md"
    quality_failure_case["report_freeze"]["independent_review"]["status"] = "FAIL"
    result = validate_case(quality_failure_case)
    assert result["state"] == "INCOMPLETE", result
    assert result["invalid_findings"] == []
    assert result["incomplete_findings"] == ["case_frozen_with_quality_failure"]

    settlement = _settlement()
    settlement.update({
        "freeze_id": "HBTFRZ:" + variant,
        "status": "INCOMPLETE",
    })
    settlement["report_coverage"]["review_id"] = "HBTREV:" + variant
    result = validate_settlement(settlement, case=case)
    assert result["state"] == "INCOMPLETE", result
    assert "engineering_freeze_settlement_diagnostic_only" in result["incomplete_findings"]

    settlement["status"] = "REVIEWABLE"
    result = validate_settlement(settlement, case=case)
    assert "engineering_freeze_cannot_produce_reviewable_settlement" in result["invalid_findings"]

    no_action_case = deepcopy(case)
    del no_action_case["investment_decision"]
    assert validate_case(no_action_case)["state"] == "REVIEWABLE"
    diagnostic = _settlement()
    diagnostic.update({
        "freeze_id": "HBTFRZ:" + variant,
        "status": "INCOMPLETE",
    })
    diagnostic["report_coverage"]["review_id"] = "HBTREV:" + variant
    diagnostic["investment_return_outcome"] = {
        "status": "NOT_CALCULABLE",
        "action": "UNKNOWN",
        "frozen_action": "UNKNOWN",
        "frozen_price_identity": "UNKNOWN",
        "total_return": None,
        "benchmark_return": None,
        "currency": "HKD",
        "notes": ["No action or market data was frozen."],
        "execution": {
            "execution_rule": "No investment action was frozen.",
            "fill_status": "NOT_APPLICABLE",
            "entry": {"date": None, "price": None, "quantity": None, "currency": None, "source_ids": []},
            "exit": {"status": "NOT_APPLICABLE", "date": None, "price": None, "quantity": None, "currency": None, "source_ids": []},
        },
        "cash_flow_ledger": [],
        "corporate_actions": [],
        "taxes_fees_fx": deepcopy(no_action_case["taxes_fees_fx"]),
        "benchmark_identity": {
            "benchmark_id": "UNAVAILABLE",
            "market": "HK",
            "currency": "HKD",
            "return_basis": "PRICE_RETURN",
            "calculation_rule": "No official benchmark data acquired.",
            "source_ids": [],
        },
    }
    result = validate_settlement(diagnostic, case=no_action_case)
    assert result["state"] == "INCOMPLETE", result
    assert "engineering_freeze_settlement_diagnostic_only" in result["incomplete_findings"]

    legacy_identity_case = deepcopy(quality_failure_case)
    legacy_identity_case["experiment_id"] = "HBT:engineering-quality-failure"
    legacy_identity_case["report_freeze"]["frozen_report"]["origin"]["legacy_attestation_experiment_id"] = "HBT:test"
    result = validate_case(legacy_identity_case)
    assert result["state"] == "INCOMPLETE", result
    assert result["invalid_findings"] == []
    assert "case_frozen_with_quality_failure" in result["incomplete_findings"]
    assert "report_freeze.frozen_report.origin.pit_runner:legacy_experiment_identity_requires_rerun" in result["incomplete_findings"]
    assert "report_freeze.frozen_report.origin.pit_runner:writer_legacy_experiment_identity_requires_rerun" in result["incomplete_findings"]


def test_case_and_settlement_require_a_canonical_hbt_experiment_id() -> None:
    case = _case()
    case["experiment_id"] = "HBTEXP:legacy"
    result = validate_case(case)
    assert "case_experiment_id_invalid" in result["invalid_findings"]

    settlement = _settlement()
    settlement["experiment_id"] = "HBTEXP:legacy"
    result = validate_settlement(settlement, case=_case())
    assert "settlement_experiment_id_invalid" in result["invalid_findings"]


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


def test_report_coverage_must_replay_the_frozen_claim_review() -> None:
    settlement = _settlement()
    settlement["report_coverage"].update({
        "supported_claim_count": 0,
        "unsupported_claim_count": 0,
    })
    result = validate_settlement(settlement, case=_case())
    assert "report_coverage:supported_claim_count_does_not_match_claim_reviews" in result["invalid_findings"]

    settlement = _settlement()
    settlement["report_coverage"]["claim_reviews"] = [
        settlement["report_coverage"]["claim_reviews"][0],
    ]
    result = validate_settlement(settlement, case=_case())
    assert "report_coverage:claim_reviews_do_not_match_frozen_review" in result["invalid_findings"]
    assert "report_coverage:claim_reviews_do_not_cover_frozen_ledger" in result["incomplete_findings"]


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

    case["calibration_ledger"]["claims"][0]["observable_outcome"]["conversion_rule"]["multiplier"] = -0.01
    result = validate_case(case)
    assert "calibration_ledger.claims[0].observable_outcome.conversion_rule:multiplier_invalid" in result["invalid_findings"]

    wrong_type_case = _case()
    wrong_type_case["calibration_ledger"]["claims"][0]["observable_outcome"]["conversion_rule"] = {
        "rule_id": 7,
        "raw_unit": "HKD/100 shares",
        "converted_unit": "HKD/share",
        "multiplier": 0.01,
    }
    result = validate_case(wrong_type_case)
    assert "calibration_ledger.claims[0].observable_outcome.conversion_rule:rule_id_invalid" in result["invalid_findings"]


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
