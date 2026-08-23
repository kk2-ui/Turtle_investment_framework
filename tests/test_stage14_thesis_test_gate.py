from __future__ import annotations

import json
import math
from copy import deepcopy
from itertools import product
from pathlib import Path

from scripts.report_completion import evaluate_report_completion
from scripts.historical_backtest import _pair_allows_each_side_to_win as hbt_pair_allows_each_side_to_win
from scripts.phase10_backtest_case_adapter import build_calibration_ledger_from_forward_judgments
from scripts.thesis_test_gate import FORWARD_JUDGMENT_CONTRACT_VERSION, INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION, _pair_allows_each_side_to_win, _prediction_is_met_at, build_thesis_test_ledger, bind_thesis_test_references, evaluate_output_thesis_test, initialize_thesis_test_policy, persist_thesis_test_ledger, promote_reviewable_thesis_test, thesis_test_fingerprint, validate_thesis_test_ledger
from scripts.turtle_agent.run import _repair_targets_from_completion
from scripts.turtle_agent.tool_registry import ToolRegistry


DECISIONS = {
    "vfinal": ("valuation.v_final", 50.0),
    "ggbase": ("return.gg.base", 7.0),
    "buy": ("trigger.buy", "price<=40"),
    "reduce": ("trigger.reduce", "retention<85"),
    "exit": ("trigger.exit", "audit_flag=1"),
}


def _prepare(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True); (output / "compute_bundle.json").write_text("{}", encoding="utf-8")
    (output / "decision_ledger.json").write_text(json.dumps({"entries": [{"entry_id": eid, "metric_id": metric, "value": value, "status": "active"} for eid, (metric, value) in DECISIONS.items()]}), encoding="utf-8")
    (output / "claim_evidence.json").write_text(json.dumps({"claims": [{"claim_id": "claim.core", "raw_facts": [{"evidence_id": "ev.primary", "support_type": "supports"}, {"evidence_id": "ev.alternative", "support_type": "contradicts"}]}]}), encoding="utf-8")


def _threshold(tid: str, decision_id: str, *, action: str, target: str = "test.core", value: float = 85.0, chapters: list[int] | None = None) -> dict:
    return {"threshold_id": tid, "metric": tid, "current_value": 90.0, "threshold_value": value, "unit": "%", "operator": "<", "basis_type": "historical_volatility", "basis_description": "五年波动区间与模型翻转点共同确定", "source_ids": ["compute_bundle.json"], "observation_frequency": "quarterly", "window": "rolling four quarters", "aggregation": "rolling_average", "seasonal_adjustment": "not_needed", "accounting_definition": "同口径续约客户/到期客户", "precision": {"justified_decimals": 1, "basis": "原始披露精度为0.1pct"}, "discrimination_target": target, "action": action, "decision_entry_ids": [decision_id], "chapters": list(chapters or [9])}


def _probabilities() -> dict:
    return {"set_id": "prob.core", "mutually_exclusive": True, "collectively_exhaustive": True, "chapters": [9], "estimates": [
        {"scenario_id": "primary", "label": "需求暂时放缓", "kind": "analyst_subjective", "value": 0.6, "interval": [0.5, 0.7], "basis": "经营数据与竞争格局综合判断", "source_ids": ["compute_bundle.json"], "as_of": "2026-08-02"},
        {"scenario_id": "alternative", "label": "结构性流失", "kind": "analyst_subjective", "value": 0.4, "interval": [0.3, 0.5], "basis": "替代证据与基准率综合判断", "source_ids": ["compute_bundle.json"], "as_of": "2026-08-02"},
    ]}


def _test() -> dict:
    return {"test_id": "test.core", "thesis_claim_id": "claim.core", "primary_explanation": "留存下降只是项目组合短期波动", "strongest_alternative": "竞争加剧导致客户结构性流失", "alternative_evidence_ids": ["ev.alternative"], "discriminating_observations": [{"observation_id": "obs.retention", "metric": "同口径续约率", "availability": "每半年业绩公告后", "primary_prediction": "滚动续约率恢复至90%以上", "alternative_prediction": "滚动续约率持续低于85%", "update_rule": "连续两期低于阈值则提高替代解释概率", "diagnosticity": {"primary_likelihood": "HIGH", "alternative_likelihood": "LOW", "rationale": "若只是项目组合短期波动，项目重排结束后留存恢复更常见；若竞争造成结构性流失，持续低位更应被观察到。"}, "threshold_id": "th.reduce"}], "probability_set_id": "prob.core", "primary_scenario_id": "primary", "alternative_scenario_id": "alternative", "flip_condition": {"threshold_id": "th.exit", "basis": "审计或监管信号否决信息可靠性", "window": "一经披露立即触发"}, "valuation_after_flip": 30.0, "position_after_flip": 0.0, "action_after_flip": "exit", "decision_entry_ids": ["vfinal", "exit"], "chapters": [9, 14]}


def _report() -> str:
    return "\n\n".join([
        "## Ch9 风险\n[thesis-test: test.core] [probability: prob.core] [threshold: th.reduce] [threshold: th.exit]",
        "## Ch13 执行\n[threshold: th.buy]",
        "## Ch14 决策\n[thesis-test: test.core]",
    ])


def _payload(output: Path, *, freeze: bool = True) -> dict:
    _prepare(output)
    thresholds = [_threshold("th.buy", "buy", action="buy", target="decision_rule", value=40.0, chapters=[13]), _threshold("th.reduce", "reduce", action="reduce"), _threshold("th.exit", "exit", action="exit", value=1.0)]
    return build_thesis_test_ledger(output, [_test()], thresholds, [_probabilities()], change_reason="initial competitive test", freeze=freeze)


def _industry_architecture(
    signal_id: str = "RHPSIG:fj.retention",
    causal_edge_id: str = "RHPEDGE:retention-vs-erosion:primary-retention-to-revenue",
) -> dict:
    unknown = {
        "status": "UNKNOWN",
        "statement": "当前PIT材料不足以确认该行业架构要素。",
        "unknown_reason": "尚无同口径的外部行业接口或利润池资料。",
        "conservative_treatment": "不把该要素当作主机制支持，只保留为外部取证问题。",
    }
    return {
        "division_of_labour": dict(unknown),
        "interface_control": dict(unknown),
        "co_specialized_assets": dict(unknown),
        "factor_mobility": dict(unknown),
        "appropriation_node": dict(unknown),
        "interface_discriminator": {
            "signal_id": signal_id,
            "causal_edge_id": causal_edge_id,
            "mechanism_edge": "渠道接口控制会先改变同口径客户留存，再影响收入和现金传导。",
            "why_discriminating": "两条竞争机制对留存方向给出不同的预注册谓词。",
        },
        "minimal_external_query": {
            "question": "同口径渠道接口的议价权是否向零售平台或安装服务网络迁移？",
            "metric": "同口径渠道费率、终端价格实现和品牌全渠道份额的连续方向",
            "allowed_source_classes": ["LICENSED_INDUSTRY_DATA", "SUPPLIER_OR_CUSTOMER_DISCLOSURE"],
            "why_required": "公司留存和线上排名不能单独识别接口控制或价值攫取位置。",
        },
    }


def _causal_trace(
    *,
    edge_namespace: str = "retention-vs-erosion",
    early_signal_id: str = "RHPSIG:fj.retention",
    terminal_signal_ids: tuple[str, ...] = ("RHPSIG:fj.owner_cash", "RHPSIG:fj.value"),
    rival_chain_id: str = "mechanism.erosion_to_cash",
) -> list[dict]:
    trace = [{
        "edge_id": f"RHPEDGE:{edge_namespace}:primary-retention-to-revenue", "mechanism_side": "PRIMARY",
        "mechanism_chain_id": "mechanism.retention_to_cash",
        "from_state": "同口径客户留存恢复", "to_state": "收入与毛利回到正常区间",
        "why_diagnostic": "主机制认为留存恢复必须先于收入和毛利的改善。",
        "status": "TESTABLE", "linked_discriminator_ids": [early_signal_id],
    }, {
        "edge_id": f"RHPEDGE:{edge_namespace}:rival-retention-to-unit-economics", "mechanism_side": "RIVAL",
        "mechanism_chain_id": rival_chain_id,
        "from_state": "同口径客户持续流失", "to_state": "单位经济性恶化",
        "why_diagnostic": "反方认为留存弱势会在价格实现或费用中首先显现。",
        "status": "TESTABLE", "linked_discriminator_ids": [early_signal_id],
    }]
    for index, signal_id in enumerate(terminal_signal_ids, start=1):
        trace.extend([{
            "edge_id": f"RHPEDGE:{edge_namespace}:primary-terminal-{index}", "mechanism_side": "PRIMARY",
            "mechanism_chain_id": "mechanism.retention_to_cash",
            "from_state": "收入与毛利正常化", "to_state": f"终局经营观察{index}",
            "why_diagnostic": "主机制必须把前期经营改善传导到其预注册的终局观察。",
            "status": "TESTABLE", "linked_discriminator_ids": [signal_id],
        }, {
            "edge_id": f"RHPEDGE:{edge_namespace}:rival-terminal-{index}", "mechanism_side": "RIVAL",
            "mechanism_chain_id": rival_chain_id,
            "from_state": "单位经济性恶化", "to_state": f"终局经营观察{index}",
            "why_diagnostic": "反方必须把竞争压力传导到其预注册的终局观察。",
            "status": "TESTABLE", "linked_discriminator_ids": [signal_id],
        }])
    return trace


def _forward_payload(output: Path, *, freeze: bool = True) -> dict:
    _prepare(output)
    (output / "valuation_model.json").write_text(json.dumps({
        "models": [{"model_id": "M001", "status": "active"}],
    }), encoding="utf-8")
    thresholds = [
        _threshold("th.buy", "buy", action="buy", target="decision_rule", value=40.0, chapters=[13]),
        _threshold("th.reduce", "reduce", action="reduce"),
        _threshold("th.exit", "exit", action="exit", value=1.0),
    ]
    probabilities = _probabilities()
    probabilities["resolution_due"] = "2029-12-31"
    probabilities["outcome_scope"] = "TERMINAL_OPERATING_OUTCOME"
    probabilities["horizon_years"] = 3
    probabilities["outcome_space_definition"] = "未来三年公司核心经营地位和现金创造能力的互斥终局。"
    for estimate in probabilities["estimates"]:
        estimate["scenario_role"] = "TERMINAL_OUTCOME"
    mechanism_chains = [{
        "chain_id": "mechanism.retention_to_cash",
        "probability_set_id": "prob.core",
        "scenario_id": "primary",
        "mechanism": "客户留存稳定先支撑收入和毛利，再经由营运资本回收转化为owner cash。",
        "leading_signal_threshold_ids": ["th.reduce"],
        "transmission": {
            "normalized_earnings": {"direction": "stable", "basis": "留存稳定使收入与毛利回到正常区间"},
            "owner_cash": {"direction": "stable", "basis": "正常盈利与营运资本回收共同稳定owner cash"},
            "valuation": {"direction": "range", "basis": "稳定owner cash进入M001估值区间"},
            "expected_return": {"direction": "range", "basis": "稳定owner cash与当前价共同约束条件回报"},
        },
        "decision_entry_ids": ["vfinal", "ggbase"],
    }, {
        "chain_id": "mechanism.erosion_to_cash",
        "probability_set_id": "prob.core",
        "scenario_id": "alternative",
        "mechanism": "竞争流失先压低留存和单位经济性，再通过营运资本与现金转化拖累owner cash。",
        "leading_signal_threshold_ids": ["th.reduce"],
        "transmission": {
            "normalized_earnings": {"direction": "decrease", "basis": "持续流失压低收入和毛利"},
            "owner_cash": {"direction": "decrease", "basis": "现金转化无法抵消收入和毛利恶化"},
            "valuation": {"direction": "decrease", "basis": "较低owner cash压低估值"},
            "expected_return": {"direction": "decrease", "basis": "较低价值压低条件回报"},
        },
        "decision_entry_ids": ["vfinal", "ggbase"],
    }]
    central_path = {
        "path_id": "path.core",
        "statement": "未来三年需求只是阶段性放缓，核心客户留存恢复，正常化盈利与owner cash大致稳定。",
        "as_of": "2026-08-02",
        "horizon_years": 3,
        "probability_set_id": "prob.core",
        "selected_scenario_id": "primary",
        "competing_scenario_id": "alternative",
        "why_more_likely": "现有同口径续约证据更符合项目组合波动，结构性流失尚未解释客户回流信号。",
        "competitive_test_ids": ["test.core"],
        "chapters": [0, 14],
    }
    judgments = []
    specs = [
        ("fj.retention", "INDUSTRY_STRUCTURE", "same_scope_retention", "AT_LEAST", 90.0, "th.reduce", "FY2027H1", "2027-08-02"),
        ("fj.owner_cash", "OWNER_CASH", "owner_cash_index", "RANGE", None, "th.reduce", "FY2029", "2029-12-31"),
        ("fj.value", "VALUATION", "intrinsic_value_per_share", "AT_LEAST", 45.0, "th.buy", "FY2029", "2029-12-31"),
    ]
    for judgment_id, materiality, metric, operator, value, signal, horizon, resolution_due in specs:
        prediction = {
            "metric": metric,
            "operator": operator,
            "unit": "%" if metric == "same_scope_retention" else "index" if metric == "owner_cash_index" else "RMB/share",
            "horizon": horizon,
            "resolution_due": resolution_due,
        }
        if operator == "RANGE":
            prediction.update({"range_low": 95.0, "range_high": 105.0})
        else:
            prediction["value"] = value
        baseline_prediction = dict(prediction)
        baseline_value = 100.0 if operator == "RANGE" else value
        if operator == "RANGE":
            baseline_prediction.update({"range_low": baseline_value, "range_high": baseline_value})
        judgments.append({
            "judgment_id": judgment_id,
            "statement": f"{metric}在{horizon}达到冻结目标。",
            "materiality": materiality,
            "claim_id": "claim.core",
            "competitive_test_id": "test.core",
            "probability_set_id": "prob.core",
            "scenario_id": "primary",
            "mechanism_chain_ids": ["mechanism.retention_to_cash"],
            "evidence_ids": ["ev.primary"],
            "leading_signal_threshold_ids": [signal],
            "falsifier": "连续两期落入结构性流失阈值则该判断失败。",
            "prediction": prediction,
            "baseline": {
                "baseline_id": "baseline." + judgment_id,
                "method": "CARRY_FORWARD",
                "statement": f"以最近可见的同口径 {metric} 持续作为不含行业机制的简单挑战预测。",
                "scope_conditions": "只使用截止日前同口径官方披露；不读取价格、估值倍数或结果期信息。",
                "input_evidence_ids": ["ev.primary"],
                "calculation": {
                    "formula_id": "LAST_OBSERVED_VALUE",
                    "inputs": [{
                        "evidence_id": "ev.primary", "role": "LAST_OBSERVED", "value": baseline_value,
                        "unit": prediction["unit"],
                    }],
                },
                "prediction": baseline_prediction,
            },
            "settlement_contract": {
                "calibration_claim_id": "HBTCLM:" + judgment_id,
                "materiality": {
                    "INDUSTRY_STRUCTURE": "CENTRAL_THESIS",
                    "NORMALIZED_EARNINGS": "CENTRAL_THESIS",
                    "OWNER_CASH": "RETURN",
                }.get(materiality, materiality),
                "source_ids": ["AR:TEST:2026"],
                "threshold": {
                    "metric": metric,
                    "operator": "AT_MOST",
                    "value": 95.0 if operator == "RANGE" else value,
                    "unit": "%" if metric == "same_scope_retention" else "index" if metric == "owner_cash_index" else "RMB/share",
                    "consequence": "重新计算机制链、估值和动作。",
                },
                "observation_window": (
                    {
                        "opens_after": "2026-08-02T00:00:00+08:00",
                        "closes_at": "2027-08-02T18:00:00+08:00",
                    }
                    if judgment_id == "fj.retention" else {
                        "opens_after": "2027-08-03T00:00:00+08:00",
                        "closes_at": "2029-12-31T18:00:00+08:00",
                    }
                ),
            },
            "observable_outcome": {
                "measurement_basis": "公司定期报告同口径披露",
                "measurement_rule": f"使用首次正式披露的{horizon}数值与冻结阈值比较",
                "measurement_period": {"kind": "REPORTING_PERIOD", "start": horizon[2:6] + "-01-01", "end": horizon[2:6] + ("-06-30" if horizon.endswith("H1") else "-12-31")},
                "allowed_source_types": ["ANNUAL_REPORT", "EXCHANGE_ANNOUNCEMENT"],
                "settlement_version_policy": "INITIAL_DISCLOSURE",
            },
            "transmission": {
                "normalized_earnings": {"direction": "stable", "basis": "留存稳定使收入与毛利回到正常区间"},
                "owner_cash": {"direction": "stable", "basis": "正常盈利与营运资本回收共同稳定owner cash"},
                "valuation": {"direction": "range", "basis": "稳定owner cash进入M001估值区间"},
                "expected_return": {"direction": "range", "basis": "估值区间与当前价共同约束预期回报"},
            },
            "valuation_model_ids": ["M001"],
            "decision_entry_ids": ["vfinal", "ggbase"],
        })
    rival_predictions = {
        "fj.retention": {"metric": "same_scope_retention", "operator": "AT_MOST", "value": 85.0, "unit": "%", "horizon": "FY2027H1", "resolution_due": "2027-08-02"},
        "fj.owner_cash": {"metric": "owner_cash_index", "operator": "RANGE", "range_low": 70.0, "range_high": 85.0, "unit": "index", "horizon": "FY2029", "resolution_due": "2029-12-31"},
        "fj.value": {"metric": "intrinsic_value_per_share", "operator": "AT_MOST", "value": 35.0, "unit": "RMB/share", "horizon": "FY2029", "resolution_due": "2029-12-31"},
    }
    stages = {"fj.retention": "EARLY_MECHANISM", "fj.owner_cash": "TERMINAL_OPERATING", "fj.value": "TERMINAL_OPERATING"}
    for index, judgment in enumerate(judgments, start=1):
        judgment["rival_hypothesis_pair_id"] = "RHP:retention-vs-erosion"
        judgment["rival_signal_id"] = "RHPSIG:" + judgment["judgment_id"]
    rival_pairs = [{
        "pair_id": "RHP:retention-vs-erosion",
        "competitive_test_id": "test.core",
        "primary_mechanism_chain_id": "mechanism.retention_to_cash",
        "rival_mechanism_chain_id": "mechanism.erosion_to_cash",
        "common_fact_evidence_ids": ["ev.primary", "ev.alternative"],
        "critical_assumptions": [{
            "assumption_id": "RHPASM:retention-service-persistence", "mechanism_side": "PRIMARY",
            "statement": "同口径客户留存恢复足以使收入和毛利恢复常态。",
            "why_necessary": "若留存恢复不能传导到收入和毛利，主机制的现金路径不成立。",
            "status": "TESTABLE", "linked_discriminator_ids": ["RHPSIG:fj.retention"],
        }, {
            "assumption_id": "RHPASM:erosion-persistence", "mechanism_side": "RIVAL",
            "statement": "持续留存流失将压低同口径收入和单位经济性。",
            "why_necessary": "若流失不改变收入或单位经济性，竞争侵蚀不能解释终局现金恶化。",
            "status": "VERIFIED", "evidence_ids": ["ev.alternative"],
        }],
        "causal_trace": _causal_trace(),
        "discriminators": [{
            "signal_id": "RHPSIG:" + judgment["judgment_id"],
            "sequence": index,
            "stage": stages[judgment["judgment_id"]],
            "forward_judgment_id": judgment["judgment_id"],
            "primary_prediction": judgment["prediction"],
            "rival_prediction": rival_predictions[judgment["judgment_id"]],
        } for index, judgment in enumerate(judgments, start=1)],
    }]
    analogy_cards = [{
        "card_id": "ATC:retention-vs-erosion",
        "target_pair_id": "RHP:retention-vs-erosion",
        "source_case_id": "operating_transition",
        "target_state_vector": [
            {"dimension": "customer_retention", "state": "weakening_but_not_resolved"},
            {"dimension": "unit_economics", "state": "stable_pending_cash_test"},
            {"dimension": "cash_conversion", "state": "requires_terminal_observation"},
        ],
        "structural_mapping": [{
            "source_driver": "customer choice", "target_driver": "same-scope retention",
            "intermediate_variable": "revenue and gross-margin persistence", "operating_outcome": "owner cash stability",
        }],
        "mismatch_dimensions": [{"dimension": "channel_power", "treatment": "do not transfer the historical case conclusion without the pair signals"}],
        "application_rule": {
            "when_to_apply": "仅当目标公司同口径客户留存先于收入与现金变化、且 pair 信号可结算时迁移该关系。",
            "when_not_to_apply": "若渠道权力或客户替代边界不同，或留存与现金没有同方向传导，则停止迁移。",
        },
        "invalidation_conditions": [{"signal_id": "RHPSIG:fj.retention", "condition": "retention remains below the rival threshold", "effect": "treat the analogy as structurally broken"}],
        "support_role": "QUESTION_ONLY",
        "strongest_near_miss": {"status": "UNKNOWN_NO_QUALIFIED_EPISODE", "unknown_reason": "No PIT episode with an observed opposite outcome is available yet.", "conservative_treatment": "Use this card only to generate discriminators; do not use it as central-path support."},
        "linked_discriminator_ids": ["RHPSIG:fj.retention", "RHPSIG:fj.owner_cash", "RHPSIG:fj.value"],
        "industry_architecture": _industry_architecture(),
        "settlement_rule": "DERIVE_FROM_PAIR_SIGNALS_ONLY",
    }]
    return build_thesis_test_ledger(
        output, [_test()], thresholds, [probabilities],
        central_path=central_path, mechanism_chains=mechanism_chains,
        forward_judgments=judgments, rival_hypothesis_pairs=rival_pairs,
        analogy_transfer_cards=analogy_cards,
        change_reason="freeze selected path and forward judgments", freeze=freeze,
    )


def _forward_report() -> str:
    return "\n\n".join([
        "## Ch0 投资要点\n[central-path: path.core]",
        "## Ch9 风险\n[thesis-test: test.core] [probability: prob.core] [threshold: th.reduce] [threshold: th.exit]",
        "## Ch13 执行\n[threshold: th.buy]",
        "## Ch14 决策\n[central-path: path.core] [thesis-test: test.core]",
    ])


def _validate(path: Path, payload: dict, *, enforced: bool = True) -> dict:
    return validate_thesis_test_ledger(payload, output_dir=path, report_text=_report(), enforced=enforced)


def _attach_company_judgment_predecessor(output: Path, payload: dict) -> None:
    predecessor = {
        "schema_version": "company-judgment-predecessor.v1",
        "source": {
            "snapshot_fingerprint": "cjo-snapshot-fingerprint",
            "thesis_sha256": "cjo-thesis-sha256",
        },
        "central_path": deepcopy(payload["central_path"]),
        "forward_judgments": deepcopy(payload["forward_judgments"]),
        "mechanism_chains": deepcopy(payload["mechanism_chains"]),
    }
    (output / "company_judgment_predecessor.json").write_text(
        json.dumps(predecessor, ensure_ascii=False), encoding="utf-8",
    )
    payload["company_judgment_lineage"] = {
        "predecessor_snapshot_fingerprint": "cjo-snapshot-fingerprint",
        "predecessor_thesis_sha256": "cjo-thesis-sha256",
        "central_path_id": payload["central_path"]["path_id"],
        "forward_judgment_ids": sorted(item["judgment_id"] for item in payload["forward_judgments"]),
    }
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)


def _attach_complete_company_judgment_predecessor(output: Path, payload: dict) -> dict:
    selection_admission = {"status": "NO_PRIMARY", "reason": "同 cutoff 没有合格的选择对照"}
    predecessor = {
        "schema_version": "company-judgment-predecessor.v2",
        "identity": {"status": "G1J_COMPLETE", "missing_components": []},
        "source": {
            "snapshot_fingerprint": "complete-cjo-snapshot-fingerprint",
            "thesis_sha256": "complete-cjo-thesis-sha256",
            "financial_driver_bridge_sha256": "complete-cjo-fdb-sha256",
        },
        "central_path": deepcopy(payload["central_path"]),
        "forward_judgments": deepcopy(payload["forward_judgments"]),
        "mechanism_chains": deepcopy(payload["mechanism_chains"]),
        "rival_hypothesis_pairs": deepcopy(payload["rival_hypothesis_pairs"]),
        "analogy_transfer_cards": deepcopy(payload["analogy_transfer_cards"]),
        "selection_admission": selection_admission,
        "financial_driver_bridge": {"drivers": [], "allocation_events": []},
    }
    (output / "company_judgment_predecessor.json").write_text(
        json.dumps(predecessor, ensure_ascii=False), encoding="utf-8",
    )
    payload["company_judgment_lineage"] = {
        "predecessor_snapshot_fingerprint": "complete-cjo-snapshot-fingerprint",
        "predecessor_thesis_sha256": "complete-cjo-thesis-sha256",
        "predecessor_completeness_status": "G1J_COMPLETE",
        "predecessor_financial_driver_bridge_sha256": "complete-cjo-fdb-sha256",
        "central_path_id": payload["central_path"]["path_id"],
        "forward_judgment_ids": sorted(item["judgment_id"] for item in payload["forward_judgments"]),
        "rival_hypothesis_pair_ids": sorted(item["pair_id"] for item in payload["rival_hypothesis_pairs"]),
        "analogy_transfer_card_ids": sorted(item["card_id"] for item in payload["analogy_transfer_cards"]),
        "selection_admission": deepcopy(selection_admission),
    }
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    return predecessor


def test_valid_thesis_test_reaches_decision_ready(tmp_path: Path) -> None:
    assert _validate(tmp_path, _payload(tmp_path))["state"] == "DECISION_READY"


def test_required_forward_judgment_contract_reaches_decision_ready(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path)
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert result["state"] == "DECISION_READY"
    assert result["forward_judgment_state"] == "DECISION_READY"
    assert result["forward_judgment_count"] == 3


def test_investment_thesis_must_inherit_the_frozen_company_judgment_path(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path)
    _attach_company_judgment_predecessor(tmp_path, payload)

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        company_judgment_lineage_required=True,
    )

    assert result["state"] == "DECISION_READY"
    assert result["company_judgment_lineage_required"] is True


def test_investment_thesis_rejects_rewriting_a_frozen_company_fj(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    _attach_company_judgment_predecessor(tmp_path, payload)
    payload["forward_judgments"][0]["prediction"]["value"] = 91.0

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        company_judgment_lineage_required=True,
    )

    assert result["state"] == "INVALID"
    assert "company_judgment_lineage_forward_judgment_rewritten:fj.retention" in result["invalid_findings"]


def test_complete_company_judgment_lineage_preserves_pairs_cards_and_selection(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path)
    _attach_complete_company_judgment_predecessor(tmp_path, payload)

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        company_judgment_lineage_required=True,
    )

    assert result["state"] == "DECISION_READY"


def test_complete_company_judgment_lineage_rejects_rewritten_pair_or_card(tmp_path: Path) -> None:
    pair_payload = _forward_payload(tmp_path / "pair", freeze=False)
    _attach_complete_company_judgment_predecessor(tmp_path / "pair", pair_payload)
    pair_payload["rival_hypothesis_pairs"][0]["causal_trace"][0]["status"] = "UNKNOWN"
    pair_result = validate_thesis_test_ledger(
        pair_payload, output_dir=tmp_path / "pair", report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        company_judgment_lineage_required=True,
    )
    assert (
        "company_judgment_lineage_rival_hypothesis_pair_rewritten:RHP:retention-vs-erosion"
        in pair_result["invalid_findings"]
    )

    discriminator_payload = _forward_payload(tmp_path / "discriminator", freeze=False)
    _attach_complete_company_judgment_predecessor(tmp_path / "discriminator", discriminator_payload)
    discriminator_payload["rival_hypothesis_pairs"][0]["discriminators"][0]["rival_prediction"]["value"] = 1.0
    discriminator_result = validate_thesis_test_ledger(
        discriminator_payload, output_dir=tmp_path / "discriminator", report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        company_judgment_lineage_required=True,
    )
    assert (
        "company_judgment_lineage_rival_hypothesis_pair_rewritten:RHP:retention-vs-erosion"
        in discriminator_result["invalid_findings"]
    )

    card_payload = _forward_payload(tmp_path / "card", freeze=False)
    _attach_complete_company_judgment_predecessor(tmp_path / "card", card_payload)
    card_payload["analogy_transfer_cards"][0]["application_rule"]["when_to_apply"] = "改写迁移边界"
    card_result = validate_thesis_test_ledger(
        card_payload, output_dir=tmp_path / "card", report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        company_judgment_lineage_required=True,
    )
    assert (
        "company_judgment_lineage_analogy_transfer_card_rewritten:ATC:retention-vs-erosion"
        in card_result["invalid_findings"]
    )


def test_complete_company_judgment_lineage_rejects_missing_extra_and_selection_mismatch(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    _attach_complete_company_judgment_predecessor(tmp_path, payload)
    removed_pair = payload["rival_hypothesis_pairs"].pop(0)
    missing_pair_id = removed_pair["pair_id"]
    extra_pair = deepcopy(removed_pair)
    extra_pair["pair_id"] = "RHP:extra"
    payload["rival_hypothesis_pairs"].append(extra_pair)
    removed_card = payload["analogy_transfer_cards"].pop(0)
    missing_card_id = removed_card["card_id"]
    extra_card = deepcopy(removed_card)
    extra_card["card_id"] = "ATC:extra"
    payload["analogy_transfer_cards"].append(extra_card)
    payload["company_judgment_lineage"]["selection_admission"]["status"] = "SELECTION_ADMITTED"

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        company_judgment_lineage_required=True,
    )

    assert f"company_judgment_lineage_rival_hypothesis_pair_missing:{missing_pair_id}" in result["invalid_findings"]
    assert "company_judgment_lineage_rival_hypothesis_pair_extra:RHP:extra" in result["invalid_findings"]
    assert f"company_judgment_lineage_analogy_transfer_card_missing:{missing_card_id}" in result["invalid_findings"]
    assert "company_judgment_lineage_analogy_transfer_card_extra:ATC:extra" in result["invalid_findings"]
    assert "company_judgment_lineage_selection_admission_mismatch" in result["invalid_findings"]


def test_build_thesis_ledger_copies_complete_predecessor_lineage_receipts(tmp_path: Path) -> None:
    original = _forward_payload(tmp_path, freeze=False)
    predecessor = _attach_complete_company_judgment_predecessor(tmp_path, original)

    rebuilt = build_thesis_test_ledger(
        tmp_path,
        original["competitive_tests"], original["thresholds"], original["probability_sets"],
        central_path=original["central_path"], mechanism_chains=original["mechanism_chains"],
        forward_judgments=original["forward_judgments"],
        rival_hypothesis_pairs=original["rival_hypothesis_pairs"],
        analogy_transfer_cards=original["analogy_transfer_cards"],
        change_reason="bind complete predecessor", freeze=False,
    )

    lineage = rebuilt["company_judgment_lineage"]
    assert lineage["predecessor_completeness_status"] == "G1J_COMPLETE"
    assert lineage["predecessor_financial_driver_bridge_sha256"] == "complete-cjo-fdb-sha256"
    assert lineage["selection_admission"] == predecessor["selection_admission"]
    assert lineage["rival_hypothesis_pair_ids"] == ["RHP:retention-vs-erosion"]
    assert lineage["analogy_transfer_card_ids"] == ["ATC:retention-vs-erosion"]


def test_sensitivity_without_selected_central_path_cannot_pass_forward_gate(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload.pop("central_path")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, forward_judgment_required=True,
    )
    assert result["forward_judgment_state"] == "INCOMPLETE"
    assert "central_path_missing" in result["forward_judgment_incomplete_findings"]


def test_central_path_must_select_the_most_likely_scenario(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["central_path"]["selected_scenario_id"] = "alternative"
    payload["central_path"]["competing_scenario_id"] = "primary"
    payload["competitive_tests"][0]["primary_scenario_id"] = "alternative"
    payload["competitive_tests"][0]["alternative_scenario_id"] = "primary"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, forward_judgment_required=True,
    )
    assert "central_path:selected_scenario_not_most_likely" in result["forward_judgment_invalid_findings"]


def test_forward_gate_requires_three_to_five_settleable_judgments(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["forward_judgments"] = payload["forward_judgments"][:2]
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, forward_judgment_required=True,
    )
    assert result["forward_judgment_state"] == "INCOMPLETE"
    assert "forward_judgments_fewer_than_3" in result["forward_judgment_incomplete_findings"]


def test_forward_judgment_must_link_outcome_model_and_decision(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    judgment = payload["forward_judgments"][0]
    judgment["observable_outcome"].pop("measurement_rule")
    judgment["valuation_model_ids"] = ["M404"]
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, forward_judgment_required=True,
    )
    assert result["forward_judgment_state"] == "INVALID"
    assert any("unknown_valuation_model:M404" in item for item in result["forward_judgment_invalid_findings"])
    assert any("measurement_rule_missing" in item for item in result["forward_judgment_incomplete_findings"])


def test_company_judgment_forward_loop_freezes_operating_mechanisms_without_investment_bindings(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["analysis_purpose"] = "COMPANY_JUDGMENT_ONLY"
    for threshold in payload["thresholds"]:
        threshold.pop("action", None)
        threshold.pop("decision_entry_ids", None)
        if threshold["discrimination_target"] == "decision_rule":
            threshold["discrimination_target"] = "test.core"
    test = payload["competitive_tests"][0]
    for key in ("valuation_after_flip", "position_after_flip", "action_after_flip", "decision_entry_ids"):
        test.pop(key, None)
    for chain in payload["mechanism_chains"]:
        chain["transmission"].pop("valuation", None)
        chain["transmission"].pop("expected_return", None)
        chain.pop("decision_entry_ids", None)
    for judgment in payload["forward_judgments"]:
        judgment["transmission"].pop("valuation", None)
        judgment["transmission"].pop("expected_return", None)
        judgment.pop("valuation_model_ids", None)
        judgment.pop("decision_entry_ids", None)
        if judgment["settlement_contract"]["materiality"] in {"VALUATION", "RETURN"}:
            judgment["settlement_contract"]["materiality"] = "CENTRAL_THESIS"
    operating = next(item for item in payload["forward_judgments"] if item["judgment_id"] == "fj.value")
    operating["materiality"] = "NORMALIZED_EARNINGS"
    operating["statement"] = "normalized earnings index reaches the frozen operating target."
    operating["prediction"] = {
        "metric": "normalized_earnings_index", "operator": "AT_LEAST", "value": 95.0,
        "unit": "index", "horizon": "FY2029", "resolution_due": "2029-12-31",
    }
    operating["baseline"]["statement"] = "The last observed normalized earnings index is the simple frozen challenger."
    operating["baseline"]["prediction"] = dict(operating["prediction"])
    operating["baseline"]["calculation"]["inputs"][0].update({"value": 95.0, "unit": "index"})
    operating["settlement_contract"]["threshold"].update({
        "metric": "normalized_earnings_index", "operator": "AT_MOST", "value": 95.0,
        "unit": "index", "consequence": "Reassess the operating mechanism only.",
    })
    operating["observable_outcome"]["measurement_rule"] = "Use the first official FY2029 normalized earnings index disclosure."
    pair = payload["rival_hypothesis_pairs"][0]
    discriminator = next(item for item in pair["discriminators"] if item["forward_judgment_id"] == "fj.value")
    discriminator["primary_prediction"] = dict(operating["prediction"])
    discriminator["rival_prediction"] = {
        "metric": "normalized_earnings_index", "operator": "AT_MOST", "value": 80.0,
        "unit": "index", "horizon": "FY2029", "resolution_due": "2029-12-31",
    }

    validation = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)
    assert validation["state"] == "REVIEWABLE"
    assert validation["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert validation["selection_admission"] == {"status": "NOT_SELECTION_ELIGIBLE"}


def test_company_judgment_forward_loop_rejects_investment_bindings(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["analysis_purpose"] = "COMPANY_JUDGMENT_ONLY"
    validation = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)
    assert "test.core:company_judgment_cannot_carry_investment_flip" in validation["invalid_findings"]
    assert "mechanism.retention_to_cash:company_judgment_cannot_carry_decision" in validation["forward_judgment_invalid_findings"]
    assert "fj.retention:company_judgment_cannot_carry_investment_binding" in validation["forward_judgment_invalid_findings"]


def _selection_ready_company_judgment_payload(tmp_path: Path) -> dict:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["analysis_purpose"] = "COMPANY_JUDGMENT_ONLY"
    for threshold in payload["thresholds"]:
        threshold.pop("action", None)
        threshold.pop("decision_entry_ids", None)
        if threshold["discrimination_target"] == "decision_rule":
            threshold["discrimination_target"] = "test.core"
    test = payload["competitive_tests"][0]
    for key in ("valuation_after_flip", "position_after_flip", "action_after_flip", "decision_entry_ids"):
        test.pop(key, None)
    for chain in payload["mechanism_chains"]:
        chain["transmission"].pop("valuation", None)
        chain["transmission"].pop("expected_return", None)
        chain.pop("decision_entry_ids", None)
    for judgment in payload["forward_judgments"]:
        judgment["transmission"].pop("valuation", None)
        judgment["transmission"].pop("expected_return", None)
        judgment.pop("valuation_model_ids", None)
        judgment.pop("decision_entry_ids", None)
        if judgment["settlement_contract"]["materiality"] in {"VALUATION", "RETURN"}:
            judgment["settlement_contract"]["materiality"] = "CENTRAL_THESIS"
    operating = next(item for item in payload["forward_judgments"] if item["judgment_id"] == "fj.value")
    operating["materiality"] = "NORMALIZED_EARNINGS"
    operating["statement"] = "normalized earnings index reaches the frozen operating target."
    operating["prediction"] = {
        "metric": "normalized_earnings_index", "operator": "AT_LEAST", "value": 95.0,
        "unit": "index", "horizon": "FY2029", "resolution_due": "2029-12-31",
    }
    operating["baseline"]["statement"] = "The last observed normalized earnings index is the simple frozen challenger."
    operating["baseline"]["prediction"] = dict(operating["prediction"])
    operating["baseline"]["calculation"]["inputs"][0].update({"value": 95.0, "unit": "index"})
    operating["settlement_contract"]["threshold"].update({
        "metric": "normalized_earnings_index", "operator": "AT_MOST", "value": 95.0,
        "unit": "index", "consequence": "Reassess the operating mechanism only.",
    })
    operating["observable_outcome"]["measurement_rule"] = "Use the first official FY2029 normalized earnings index disclosure."
    discriminator = next(
        item for item in payload["rival_hypothesis_pairs"][0]["discriminators"]
        if item["forward_judgment_id"] == "fj.value"
    )
    discriminator["primary_prediction"] = dict(operating["prediction"])
    discriminator["rival_prediction"] = {
        "metric": "normalized_earnings_index", "operator": "AT_MOST", "value": 80.0,
        "unit": "index", "horizon": "FY2029", "resolution_due": "2029-12-31",
    }
    return payload


def _no_probability_company_judgment_payload(
    tmp_path: Path, *, selection_status: str,
) -> dict:
    """Freeze CJO mechanism signals without inventing scenario weights."""
    payload = _selection_ready_company_judgment_payload(tmp_path)
    payload["probability_mode"] = "NO_PROBABILITY"
    payload["probability_sets"] = []
    for test in payload["competitive_tests"]:
        test.pop("probability_set_id", None)
    for chain in payload["mechanism_chains"]:
        chain.pop("probability_set_id", None)
    for judgment in payload["forward_judgments"]:
        judgment.pop("probability_set_id", None)
        judgment["prediction"]["as_of"] = "2026-08-02"
    judgments_by_id = {item["judgment_id"]: item for item in payload["forward_judgments"]}
    for discriminator in payload["rival_hypothesis_pairs"][0]["discriminators"]:
        discriminator["primary_prediction"] = judgments_by_id[discriminator["forward_judgment_id"]]["prediction"]

    if selection_status == "NO_PRIMARY":
        payload.pop("central_path", None)
        payload["selection_admission"] = {
            "status": "NO_PRIMARY",
            "candidate_scenario_ids": ["primary", "alternative"],
            "strongest_rival_scenario_id": "alternative",
            "strongest_rival_not_selected_reason": "两条机制仍以同一组可结算信号竞争，当前没有可排除共同事实解释的方向性观察。",
            "rival_hypothesis_pair_id": "RHP:retention-vs-erosion",
            "no_primary_reason": "截止日前缺少能够让任一机制优于对手的方向性经营事实。",
        }
    elif selection_status == "SELECTION_ADMITTED":
        evidence_path = tmp_path / "claim_evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["claims"][0]["raw_facts"].append({
            "evidence_id": "ev.directional", "source_id": "DOC:company-q2",
            "source_group_id": "company-quarterly-disclosure", "fact": "同口径安装完成率回升。",
            "authority": "company_filing", "claim_distance": "raw_data",
            "published_at": "2026-07-20", "data_as_of": "2026-06-30",
            "direct_support": True, "support_type": "supports", "basis_match": "exact",
            "conflict_of_interest": "company disclosure",
        })
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        payload["rival_hypothesis_pairs"][0]["causal_trace"].append({
            "edge_id": "RHPEDGE:selection-primary-installation-to-retention", "mechanism_side": "PRIMARY",
            "mechanism_chain_id": "mechanism.retention_to_cash",
            "from_state": "同口径安装完成率改善", "to_state": "客户留存首先恢复",
            "why_diagnostic": "当前经营观察是主机制留存恢复之前的已验证箭头。",
            "status": "VERIFIED", "evidence_ids": ["ev.directional"],
        })
        central = payload["central_path"]
        central.pop("probability_set_id", None)
        central.pop("why_more_likely", None)
        central["selection_basis"] = "完成率先回升进入主机制的已验证箭头，而反方不能同样解释该顺序。"
        retention = next(item for item in payload["forward_judgments"] if item["judgment_id"] == "fj.retention")
        retention["baseline"]["prediction"]["value"] = 89.0
        retention["baseline"]["calculation"]["inputs"][0]["value"] = 89.0
        retention["observable_outcome"]["metric_reconstruction_contract"] = {
            "source_targets": [{
                "source_type": "EXCHANGE_ANNOUNCEMENT", "file_scope": "FY2027 H1 results announcement",
                "reported_label": "same-scope retention", "reported_locator": "Operating KPI table / customer retention",
            }],
            "prohibited_substitutes": ["total revenue", "management narrative", "different customer cohort"],
            "definition_change_action": "MEASUREMENT_MISMATCH",
        }
        retention["observable_outcome"]["conversion_rule"] = {
            "rule_id": "HBTCONV:retention-percent-to-percent", "raw_unit": "%",
            "converted_unit": "%", "multiplier": 1.0,
        }
        payload["selection_admission"] = {
            "status": "SELECTION_ADMITTED",
            "candidate_scenario_ids": ["primary", "alternative"],
            "strongest_rival_scenario_id": "alternative",
            "strongest_rival_not_selected_reason": "竞争侵蚀仍可解释共同留存压力，但不能同样解释安装完成率在价格实现未改善时回升。",
            "rival_hypothesis_pair_id": "RHP:retention-vs-erosion",
            "selection_forward_judgment_ids": ["fj.retention"],
            "selection_evidence": [{
                "evidence_id": "ev.directional", "source_id": "DOC:company-q2",
                "source_group_id": "company-quarterly-disclosure", "supports_scenario_id": "primary",
                "directional_reason": "完成率先回升符合项目组合恢复，而非持续性客户流失。",
                "why_rival_cannot_equally_explain": "若结构性流失主导，完成率回升不应在同一观察窗先于留存改善出现。",
                "distortion_downgrade": "若后续口径改变或单一渠道驱动，降为 MECHANISM_SIGNAL_PROBE / NO_PRIMARY。",
                "forward_judgment_id": "fj.retention",
                "primary_causal_edge_id": "RHPEDGE:selection-primary-installation-to-retention",
                "leading_threshold_id": "th.reduce",
            }],
        }
    else:
        raise AssertionError("unsupported CJO probability test mode")
    payload["lifecycle"] = "decision_ready"
    payload["freeze"]["frozen"] = True
    payload["freeze"]["frozen_at"] = "2026-08-02T00:00:00+00:00"
    payload["freeze"]["forward_judgment_contract_version"] = FORWARD_JUDGMENT_CONTRACT_VERSION
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    return payload


def _enable_industry_architecture_provenance(payload: dict) -> None:
    payload["freeze"]["industry_architecture_provenance_contract_version"] = (
        INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION
    )
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)


def _add_licensed_industry_architecture_evidence(tmp_path: Path, payload: dict) -> dict:
    """Add one PIT-projected provider fact with the real source identity chain."""
    document_id = "DOC:CN-SZ:000651:licensed_industry_data:2026-03-31:avc-test"
    provider_source_id = "AVC:000651:CHANNEL:2026Q1:ORIGINAL"
    evidence_path = tmp_path / "claim_evidence.json"
    claim_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    claim_evidence["claims"][0]["raw_facts"].append({
        "evidence_id": "ev.industry-architecture", "source_id": document_id,
        "source_group_id": "avc-channel-panel-2026q1",
        "fact": "零售渠道面板显示品牌、平台与安装服务商的渠道费率口径按相同映射连续披露。",
        "authority": "industry_data", "claim_distance": "raw_data",
        "published_at": "2026-04-18", "data_as_of": "2026-03-31",
        "direct_support": True, "support_type": "supports", "basis_match": "exact",
        "conflict_of_interest": "independent licensed industry provider",
    })
    evidence_path.write_text(json.dumps(claim_evidence), encoding="utf-8")
    (tmp_path / "document_manifest.json").write_text(json.dumps({
        "schema_version": "document-manifest.v1",
        "documents": [{
            "doc_id": document_id, "doc_type": "licensed_industry_data",
            "authority": "industry_data", "source_id": provider_source_id,
            "source_version": "AVC-2026Q1-v1", "revision_policy": "ORIGINAL_VINTAGE",
        }],
    }), encoding="utf-8")
    architecture = payload["analogy_transfer_cards"][0]["industry_architecture"]
    architecture["division_of_labour"] = {
        "status": "VERIFIED",
        "statement": "渠道、平台和安装服务商的可比费率接口由独立面板以同一映射连续记录。",
        "evidence_ids": ["ev.industry-architecture"],
        "source_classes": ["LICENSED_INDUSTRY_DATA"],
        "evidence_bindings": [{
            "evidence_id": "ev.industry-architecture", "source_id": document_id,
            "canonical_source_id": provider_source_id,
            "source_class": "LICENSED_INDUSTRY_DATA",
        }],
    }
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    return architecture["division_of_labour"]


def _external_role_provenance(*, role: str, source_id: str, publisher_id: str, subject_id: str = "ENTITY:TARGET") -> dict:
    return {
        "schema_version": "phase10-source-role-provenance.v1",
        "publisher_entity": {
            "entity_id": publisher_id,
            "legal_name": publisher_id + " legal display",
            "entity_kind": "REGULATOR" if role == "REGULATORY_DISCLOSURE" else "OPERATING_ENTITY",
        },
        "subject_entity": {
            "entity_id": subject_id,
            "legal_name": "Target Company legal display",
            "entity_kind": "OPERATING_ENTITY",
        },
        "relative_role": role,
        "scope": {
            "scope_id": "SCOPE:CN:ROOM_AC:2026",
            "product_or_service": "room air conditioner retail and installation",
            "geography": "China mainland",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
        "role_basis": {
            "source_id": source_id,
            "locator": "p. 12 / named market and counterparty scope",
            "basis_kind": (
                "REGULATORY_PRIMARY_INSTRUMENT"
                if role == "REGULATORY_DISCLOSURE" else "PUBLISHER_PRIMARY_DISCLOSURE"
            ),
        },
    }


def _add_external_role_architecture_evidence(tmp_path: Path, payload: dict) -> dict:
    """Build three external roles from projected source contracts, never prose labels."""
    role_rows = [
        ("division_of_labour", "COMPETITOR_DISCLOSURE", "PIT:COMPETITOR:FY2026", "ENTITY:COMPETITOR"),
        ("interface_control", "SUPPLIER_OR_CUSTOMER_DISCLOSURE", "PIT:CUSTOMER:FY2026", "ENTITY:CUSTOMER"),
        ("appropriation_node", "REGULATORY_DISCLOSURE", "PIT:REGULATOR:INSTRUMENT", "REGULATOR:CN:MARKET"),
    ]
    evidence_path = tmp_path / "claim_evidence.json"
    claim_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    documents: list[dict] = []
    projections: list[dict] = []
    observations: list[dict] = []
    architecture = payload["analogy_transfer_cards"][0]["industry_architecture"]
    for index, (element_name, role, source_id, publisher_id) in enumerate(role_rows, start=1):
        document_id = f"DOC:EXT:{index}"
        evidence_id = f"ev.external-role-{index}"
        observation_id = f"OBS:external-role-{index}"
        provenance = _external_role_provenance(
            role=role, source_id=source_id, publisher_id=publisher_id,
        )
        claim_evidence["claims"][0]["raw_facts"].append({
            "evidence_id": evidence_id, "observation_id": observation_id,
            "source_id": document_id, "source_group_id": source_id,
            "fact": "可读取的一阶披露在冻结范围内记录发布者、对象及其市场关系。",
            "authority": "other_official", "claim_distance": "direct_statement",
            "published_at": "2026-06-30", "data_as_of": "2026-06-30",
            "direct_support": True, "support_type": "supports", "basis_match": "exact",
            "conflict_of_interest": "external publisher; role is bounded by its own primary disclosure",
        })
        documents.append({
            "doc_id": document_id, "doc_type": "other_official", "authority": "other_official",
            "source_id": source_id, "source_version": "original-v1", "revision_policy": "ORIGINAL_VINTAGE",
            "source_role_provenance": deepcopy(provenance),
        })
        projections.append({
            "source_id": source_id, "source_version": "original-v1", "revision_policy": "ORIGINAL_VINTAGE",
            "source_type": "OTHER_OFFICIAL", "admission_status": "ADMITTED",
            "source_role_provenance": deepcopy(provenance),
        })
        observations.append({"observation_id": observation_id, "doc_id": document_id, "status": "VERIFIED"})
        architecture[element_name] = {
            "status": "VERIFIED",
            "statement": "该结构要素只使用冻结的外部发布者角色契约及其可读一阶定位。",
            "evidence_ids": [evidence_id], "source_classes": [role],
            "evidence_bindings": [{"evidence_id": evidence_id, "source_id": document_id, "source_class": role}],
        }
    evidence_path.write_text(json.dumps(claim_evidence), encoding="utf-8")
    (tmp_path / "document_manifest.json").write_text(json.dumps({
        "schema_version": "document-manifest.v1", "documents": documents,
    }), encoding="utf-8")
    (tmp_path / "fact_observations.json").write_text(json.dumps({"observations": observations}), encoding="utf-8")
    (tmp_path / "pit_source_provenance.json").write_text(json.dumps({
        "schema_version": "phase10-pit-source-provenance-projection.v1", "sources": projections,
    }), encoding="utf-8")
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    return {"documents": documents, "projections": projections}


def _no_probability_cjo_report(*, selected: bool) -> str:
    sections = [
        "## Ch9 竞争机制\n[thesis-test: test.core] [threshold: th.reduce] [threshold: th.exit]",
        "## Ch13 监测\n[threshold: th.buy]",
        "## Ch14 公司判断\n[thesis-test: test.core]",
    ]
    if selected:
        sections.insert(0, "## Ch0 公司判断\n[central-path: path.core]")
        sections[-1] += "\n[central-path: path.core]"
    return "\n\n".join(sections)


def test_cjo_selection_admission_accepts_one_directional_company_fact_without_external_confirmation(tmp_path: Path) -> None:
    payload = _selection_ready_company_judgment_payload(tmp_path)
    evidence_path = tmp_path / "claim_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["claims"][0]["raw_facts"].append({
        "evidence_id": "ev.directional", "source_id": "DOC:company-q2",
        "source_group_id": "company-quarterly-disclosure", "fact": "同口径安装完成率回升。",
        "authority": "company_filing", "claim_distance": "raw_data",
        "published_at": "2026-07-20", "data_as_of": "2026-06-30",
        "direct_support": True, "support_type": "supports", "basis_match": "exact",
        "conflict_of_interest": "company disclosure",
    })
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    payload["rival_hypothesis_pairs"][0]["causal_trace"].append({
        "edge_id": "RHPEDGE:selection-primary-installation-to-retention", "mechanism_side": "PRIMARY",
        "mechanism_chain_id": "mechanism.retention_to_cash",
        "from_state": "同口径安装完成率改善", "to_state": "客户留存首先恢复",
        "why_diagnostic": "该当前经营观察是主路径中留存恢复之前的已验证箭头。",
        "status": "VERIFIED", "evidence_ids": ["ev.directional"],
    })
    retention = next(item for item in payload["forward_judgments"] if item["judgment_id"] == "fj.retention")
    retention["baseline"]["prediction"]["value"] = 89.0
    retention["baseline"]["calculation"]["inputs"][0]["value"] = 89.0
    retention["observable_outcome"]["metric_reconstruction_contract"] = {
        "source_targets": [{
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "file_scope": "FY2027 H1 results announcement",
            "reported_label": "same-scope retention",
            "reported_locator": "Operating KPI table / customer retention",
        }],
        "prohibited_substitutes": ["total revenue", "management narrative", "different customer cohort"],
        "definition_change_action": "MEASUREMENT_MISMATCH",
    }
    retention["observable_outcome"]["conversion_rule"] = {
        "rule_id": "HBTCONV:retention-percent-to-percent",
        "raw_unit": retention["prediction"]["unit"],
        "converted_unit": retention["prediction"]["unit"],
        "multiplier": 1.0,
    }
    payload["selection_admission"] = {
        "status": "SELECTION_ADMITTED",
        "candidate_scenario_ids": ["primary", "alternative"],
        "strongest_rival_scenario_id": "alternative",
        "strongest_rival_not_selected_reason": "竞争侵蚀仍可解释共同留存压力，但无法同样解释安装完成率在价格实现未改善时回升。",
        "rival_hypothesis_pair_id": "RHP:retention-vs-erosion",
        "selection_forward_judgment_ids": ["fj.retention"],
        "selection_evidence": [{
            "evidence_id": "ev.directional", "source_id": "DOC:company-q2",
            "source_group_id": "company-quarterly-disclosure", "supports_scenario_id": "primary",
            "directional_reason": "完成率先回升符合项目组合恢复，而非持续性客户流失。",
            "why_rival_cannot_equally_explain": "若结构性流失主导，完成率回升不应在同一观察窗先于留存改善出现。",
            "distortion_downgrade": "若后续口径改变或单一渠道驱动，降为 MECHANISM_SIGNAL_PROBE / NO_PRIMARY。",
            "forward_judgment_id": "fj.retention",
            "primary_causal_edge_id": "RHPEDGE:selection-primary-installation-to-retention",
            "leading_threshold_id": "th.reduce",
        }],
    }

    validation = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)

    assert validation["state"] == "REVIEWABLE"
    assert validation["selection_admission"] == {"status": "SELECTION_ADMITTED"}

    retention["observable_outcome"].pop("metric_reconstruction_contract")
    missing_contract = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)
    assert missing_contract["state"] == "INCOMPLETE"
    assert (
        "selection_admission:fj.retention:observable_outcome:metric_reconstruction_contract_missing"
        in missing_contract["selection_admission_incomplete_findings"]
    )


def test_cjo_selection_admission_requires_a_real_early_mechanism_sequence(tmp_path: Path) -> None:
    payload = _selection_ready_company_judgment_payload(tmp_path)
    evidence_path = tmp_path / "claim_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["claims"][0]["raw_facts"].append({
        "evidence_id": "ev.directional", "source_id": "DOC:company-q2",
        "source_group_id": "company-quarterly-disclosure", "fact": "同口径安装完成率回升。",
        "authority": "company_filing", "claim_distance": "raw_data",
        "published_at": "2026-07-20", "data_as_of": "2026-06-30",
        "direct_support": True, "support_type": "supports", "basis_match": "exact",
        "conflict_of_interest": "company disclosure",
    })
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    retention = next(item for item in payload["forward_judgments"] if item["judgment_id"] == "fj.retention")
    retention["baseline"]["prediction"]["value"] = 89.0
    retention["baseline"]["calculation"]["inputs"][0]["value"] = 89.0
    retention["observable_outcome"]["metric_reconstruction_contract"] = {
        "source_targets": [{
            "source_type": "EXCHANGE_ANNOUNCEMENT", "file_scope": "FY2027 H1 results announcement",
            "reported_label": "same-scope retention",
            "reported_locator": "Operating KPI table / customer retention",
        }],
        "prohibited_substitutes": ["total revenue", "management narrative", "different customer cohort"],
        "definition_change_action": "MEASUREMENT_MISMATCH",
    }
    retention["observable_outcome"]["conversion_rule"] = {
        "rule_id": "HBTCONV:retention-percent-to-percent",
        "raw_unit": "%", "converted_unit": "%", "multiplier": 1.0,
    }
    pair = payload["rival_hypothesis_pairs"][0]
    pair["causal_trace"].append({
        "edge_id": "RHPEDGE:selection-primary-installation-to-retention", "mechanism_side": "PRIMARY",
        "mechanism_chain_id": "mechanism.retention_to_cash",
        "from_state": "同口径安装完成率改善", "to_state": "客户留存首先恢复",
        "why_diagnostic": "当前经营观察在主路径中先于留存恢复。",
        "status": "VERIFIED", "evidence_ids": ["ev.directional"],
    })
    payload["selection_admission"] = {
        "status": "SELECTION_ADMITTED",
        "candidate_scenario_ids": ["primary", "alternative"],
        "strongest_rival_scenario_id": "alternative",
        "strongest_rival_not_selected_reason": "完成率改善连入主路径的早期留存信号。",
        "rival_hypothesis_pair_id": "RHP:retention-vs-erosion",
        "selection_forward_judgment_ids": ["fj.retention"],
        "selection_evidence": [{
            "evidence_id": "ev.directional", "source_id": "DOC:company-q2",
            "source_group_id": "company-quarterly-disclosure", "supports_scenario_id": "primary",
            "directional_reason": "完成率先回升符合项目组合恢复。",
            "why_rival_cannot_equally_explain": "持续流失不能同样预期该早期留存分叉。",
            "distortion_downgrade": "口径改变或单一渠道驱动则降级。",
            "forward_judgment_id": "fj.retention",
            "primary_causal_edge_id": "RHPEDGE:selection-primary-installation-to-retention",
            "leading_threshold_id": "th.reduce",
        }],
    }

    assert validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)["state"] == "REVIEWABLE"

    terminal = deepcopy(payload)
    terminal["selection_admission"]["selection_forward_judgment_ids"] = ["fj.owner_cash"]
    terminal["selection_admission"]["selection_evidence"][0]["forward_judgment_id"] = "fj.owner_cash"
    terminal_result = validate_thesis_test_ledger(terminal, output_dir=tmp_path, enforced=False)
    assert (
        "selection_admission:selection_evidence[0]:forward_judgment_not_early_mechanism"
        in terminal_result["selection_admission_invalid_findings"]
    )

    wrong_edge = deepcopy(payload)
    wrong_edge["selection_admission"]["selection_evidence"][0]["primary_causal_edge_id"] = "RHPEDGE:retention-vs-erosion:primary-retention-to-revenue"
    wrong_edge_result = validate_thesis_test_ledger(wrong_edge, output_dir=tmp_path, enforced=False)
    assert (
        "selection_admission:selection_evidence[0]:primary_causal_edge_not_primary_verified"
        in wrong_edge_result["selection_admission_invalid_findings"]
    )

    untested_early_signal = deepcopy(payload)
    next(
        edge for edge in untested_early_signal["rival_hypothesis_pairs"][0]["causal_trace"]
        if edge["edge_id"] == "RHPEDGE:retention-vs-erosion:primary-retention-to-revenue"
    )["linked_discriminator_ids"] = ["RHPSIG:fj.owner_cash"]
    untested_result = validate_thesis_test_ledger(untested_early_signal, output_dir=tmp_path, enforced=False)
    assert (
        "selection_admission:selection_evidence[0]:primary_early_signal_not_testable"
        in untested_result["selection_admission_invalid_findings"]
    )

    one_sided_threshold = deepcopy(payload)
    next(
        chain for chain in one_sided_threshold["mechanism_chains"]
        if chain["chain_id"] == "mechanism.erosion_to_cash"
    )["leading_signal_threshold_ids"] = ["th.exit"]
    one_sided_result = validate_thesis_test_ledger(one_sided_threshold, output_dir=tmp_path, enforced=False)
    assert (
        "selection_admission:selection_evidence[0]:leading_threshold_not_rival_mechanism_signal"
        in one_sided_result["selection_admission_invalid_findings"]
    )


def test_cjo_selection_admission_rejects_common_fact_and_identical_baseline(tmp_path: Path) -> None:
    payload = _selection_ready_company_judgment_payload(tmp_path)
    payload["selection_admission"] = {
        "status": "SELECTION_ADMITTED",
        "candidate_scenario_ids": ["primary", "alternative"],
        "strongest_rival_scenario_id": "alternative",
        "strongest_rival_not_selected_reason": "已处理竞争侵蚀反方。",
        "rival_hypothesis_pair_id": "RHP:retention-vs-erosion",
        "selection_forward_judgment_ids": ["fj.retention"],
        "selection_evidence": [{
            "evidence_id": "ev.primary", "source_id": "DOC:common",
            "source_group_id": "common-source", "supports_scenario_id": "primary",
            "directional_reason": "误把共同事实当方向性事实。",
            "why_rival_cannot_equally_explain": "没有有效解释。",
            "distortion_downgrade": "降级。",
        }],
    }

    validation = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)

    assert validation["state"] == "INVALID"
    assert "selection_admission:selection_evidence[0]:common_fact_cannot_be_selection_evidence" in validation["selection_admission_invalid_findings"]
    assert "selection_admission:fj.retention:baseline_prediction_not_distinct" in validation["selection_admission_invalid_findings"]


def test_cjo_can_freeze_no_primary_without_blocking_ordinary_mechanism_research(tmp_path: Path) -> None:
    payload = _selection_ready_company_judgment_payload(tmp_path)
    payload["selection_admission"] = {
        "status": "NO_PRIMARY",
        "candidate_scenario_ids": ["primary", "alternative"],
        "strongest_rival_scenario_id": "alternative",
        "strongest_rival_not_selected_reason": "反方保留为同一组可结算信号的竞争解释。",
        "rival_hypothesis_pair_id": "RHP:retention-vs-erosion",
        "no_primary_reason": "截止日前没有能排除共同事实解释的方向性经营观察。",
    }

    validation = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)

    assert validation["state"] == "REVIEWABLE"
    assert validation["selection_admission"] == {"status": "NO_PRIMARY"}


def test_enforced_cjo_no_probability_no_primary_keeps_fj_pair_and_hbt_projection(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")

    validation = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert validation["state"] == "DECISION_READY"
    assert validation["forward_judgment_state"] == "DECISION_READY"
    assert validation["selection_admission"] == {"status": "NO_PRIMARY"}
    assert payload["probability_sets"] == []
    initialize_thesis_test_policy(
        tmp_path, run_id="cjo-no-probability", enforced=True, monitoring_required=True,
        forward_judgment_required=True, rival_hypothesis_pair_required=True,
    )
    persisted = persist_thesis_test_ledger(
        tmp_path, payload, report_text=_no_probability_cjo_report(selected=False),
    )
    assert persisted["written"] is True
    assert evaluate_output_thesis_test(
        tmp_path, report_text=_no_probability_cjo_report(selected=False), persist=False,
    )["state"] == "DECISION_READY"
    projected = build_calibration_ledger_from_forward_judgments(
        payload, simulation_cutoff="2026-08-02", known_source_ids={"AR:TEST:2026"},
    )
    assert len(projected["claims"]) == 3
    assert projected["selection_admission"] == {"status": "NO_PRIMARY", **payload["selection_admission"]}


def test_enforced_cjo_no_probability_selection_admitted_uses_p24_not_numeric_weights(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="SELECTION_ADMITTED")

    validation = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=True),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert validation["state"] == "DECISION_READY"
    assert validation["selection_admission"] == {"status": "SELECTION_ADMITTED"}
    assert "probability_set_id" not in payload["central_path"]
    assert "why_more_likely" not in payload["central_path"]


def test_cjo_selection_register_binding_is_optional_but_must_be_a_complete_canonical_receipt(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="SELECTION_ADMITTED")
    payload["selection_admission"]["selection_register_binding"] = {
        "register_id": "CSR:retail-cohort", "register_fingerprint": "a" * 64,
        "selection_entry_id": "CSRSEL:retail-alpha", "company_id": "COMPANY:alpha",
        "company_cluster_id": "COMPANY:alpha",
    }
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)

    valid = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=True),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert valid["state"] == "DECISION_READY"

    payload["selection_admission"]["selection_register_binding"]["register_fingerprint"] = "not-a-fingerprint"
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    invalid = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=True),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert invalid["state"] == "INVALID"
    assert "selection_admission:selection_register_binding_register_fingerprint_invalid" in invalid["invalid_findings"]


def test_cjo_no_primary_may_freeze_a_selection_register_receipt_for_l5_coverage_only(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")
    payload["selection_admission"]["selection_register_binding"] = {
        "register_id": "CSR:retail-cohort", "register_fingerprint": "a" * 64,
        "selection_entry_id": "CSRSEL:retail-delta", "company_id": "COMPANY:delta",
        "company_cluster_id": "COMPANY:delta",
    }
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)

    validation = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert validation["state"] == "DECISION_READY"


def test_new_cjo_architecture_verified_element_requires_canonical_external_source(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")
    _enable_industry_architecture_provenance(payload)
    _add_licensed_industry_architecture_evidence(tmp_path, payload)

    valid = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert valid["state"] == "DECISION_READY"
    assert payload["freeze"]["industry_architecture_provenance_contract_version"] == (
        INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION
    )

    forged_class = deepcopy(payload)
    forged_element = forged_class["analogy_transfer_cards"][0]["industry_architecture"]["division_of_labour"]
    forged_element["source_classes"] = ["COMPETITOR_DISCLOSURE"]
    forged_element["evidence_bindings"][0]["source_class"] = "COMPETITOR_DISCLOSURE"
    forged_class["freeze"]["fingerprint"] = thesis_test_fingerprint(forged_class)
    forged_result = validate_thesis_test_ledger(
        forged_class, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert (
        "ATC:retention-vs-erosion.industry_architecture.division_of_labour:"
        "evidence_bindings[0]:source_class_does_not_match_document"
        in forged_result["analogy_transfer_card_invalid_findings"]
    )

    mismatched_source = deepcopy(payload)
    mismatched_element = mismatched_source["analogy_transfer_cards"][0]["industry_architecture"]["division_of_labour"]
    mismatched_element["evidence_bindings"][0]["source_id"] = "DOC:FORGED:SOURCE"
    mismatched_source["freeze"]["fingerprint"] = thesis_test_fingerprint(mismatched_source)
    mismatched_result = validate_thesis_test_ledger(
        mismatched_source, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert (
        "ATC:retention-vs-erosion.industry_architecture.division_of_labour:"
        "evidence_bindings[0]:source_id_does_not_match_evidence"
        in mismatched_result["analogy_transfer_card_invalid_findings"]
    )

    forged_provider_source = deepcopy(payload)
    forged_provider_element = forged_provider_source["analogy_transfer_cards"][0]["industry_architecture"]["division_of_labour"]
    forged_provider_element["evidence_bindings"][0]["canonical_source_id"] = "AVC:FORGED:SOURCE"
    forged_provider_source["freeze"]["fingerprint"] = thesis_test_fingerprint(forged_provider_source)
    forged_provider_result = validate_thesis_test_ledger(
        forged_provider_source, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert (
        "ATC:retention-vs-erosion.industry_architecture.division_of_labour:"
        "evidence_bindings[0]:canonical_source_id_does_not_match_document"
        in forged_provider_result["analogy_transfer_card_invalid_findings"]
    )


def test_new_cjo_architecture_unknown_does_not_require_external_source(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")
    _enable_industry_architecture_provenance(payload)

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert result["state"] == "DECISION_READY"
    assert result["analogy_transfer_card_state"] == "DECISION_READY"


def test_new_cjo_architecture_accepts_only_three_complete_projected_external_roles(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")
    _enable_industry_architecture_provenance(payload)
    _add_external_role_architecture_evidence(tmp_path, payload)

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert result["state"] == "DECISION_READY"
    assert result["analogy_transfer_card_state"] == "DECISION_READY"


def test_new_cjo_architecture_external_roles_reject_missing_contract_scope_and_projection_tampering(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")
    _enable_industry_architecture_provenance(payload)
    _add_external_role_architecture_evidence(tmp_path, payload)
    document_path = tmp_path / "document_manifest.json"
    projection_path = tmp_path / "pit_source_provenance.json"

    def validate() -> dict:
        payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
        return validate_thesis_test_ledger(
            payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
            enforced=True, monitoring_required=True, forward_judgment_required=True,
            rival_hypothesis_pair_required=True,
        )

    missing_entity = json.loads(document_path.read_text(encoding="utf-8"))
    missing_entity["documents"][0]["source_role_provenance"].pop("publisher_entity")
    document_path.write_text(json.dumps(missing_entity), encoding="utf-8")
    result = validate()
    assert any("publisher_entity_missing" in item for item in result["analogy_transfer_card_incomplete_findings"])

    _add_external_role_architecture_evidence(tmp_path, payload)
    missing_basis_document = json.loads(document_path.read_text(encoding="utf-8"))
    missing_basis = json.loads(projection_path.read_text(encoding="utf-8"))
    missing_basis_document["documents"][0]["source_role_provenance"].pop("role_basis")
    missing_basis["sources"][0]["source_role_provenance"].pop("role_basis")
    document_path.write_text(json.dumps(missing_basis_document), encoding="utf-8")
    projection_path.write_text(json.dumps(missing_basis), encoding="utf-8")
    result = validate()
    assert any("role_basis_missing" in item for item in result["analogy_transfer_card_incomplete_findings"])

    _add_external_role_architecture_evidence(tmp_path, payload)
    missing_scope = json.loads(document_path.read_text(encoding="utf-8"))
    missing_scope["documents"][0]["source_role_provenance"].pop("scope")
    mirrored_projection = json.loads(projection_path.read_text(encoding="utf-8"))
    mirrored_projection["sources"][0]["source_role_provenance"].pop("scope")
    document_path.write_text(json.dumps(missing_scope), encoding="utf-8")
    projection_path.write_text(json.dumps(mirrored_projection), encoding="utf-8")
    result = validate()
    assert any("scope_missing" in item for item in result["analogy_transfer_card_incomplete_findings"])

    _add_external_role_architecture_evidence(tmp_path, payload)
    tampered_document = json.loads(document_path.read_text(encoding="utf-8"))
    tampered_document["documents"][0]["source_version"] = "forged-v2"
    document_path.write_text(json.dumps(tampered_document), encoding="utf-8")
    result = validate()
    assert any("document_source_version_does_not_match_pit_source" in item for item in result["analogy_transfer_card_invalid_findings"])

    _add_external_role_architecture_evidence(tmp_path, payload)
    payload["analogy_transfer_cards"][0]["industry_architecture"]["division_of_labour"]["source_classes"] = ["SUPPLIER_OR_CUSTOMER_DISCLOSURE"]
    payload["analogy_transfer_cards"][0]["industry_architecture"]["division_of_labour"]["evidence_bindings"][0]["source_class"] = "SUPPLIER_OR_CUSTOMER_DISCLOSURE"
    result = validate()
    assert any("source_class_does_not_match_document" in item for item in result["analogy_transfer_card_invalid_findings"])


def test_new_cjo_architecture_other_official_self_ir_never_becomes_regulatory_by_label(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")
    _enable_industry_architecture_provenance(payload)
    _add_external_role_architecture_evidence(tmp_path, payload)
    document_path = tmp_path / "document_manifest.json"
    projection_path = tmp_path / "pit_source_provenance.json"
    documents = json.loads(document_path.read_text(encoding="utf-8"))
    projections = json.loads(projection_path.read_text(encoding="utf-8"))
    documents["documents"][2].pop("source_role_provenance")
    projections["sources"][2]["source_role_provenance"] = None
    document_path.write_text(json.dumps(documents), encoding="utf-8")
    projection_path.write_text(json.dumps(projections), encoding="utf-8")
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert any("source_class_not_canonical" in item for item in result["analogy_transfer_card_invalid_findings"])


def test_p29_freeze_contract_is_scoped_to_new_cjo_architecture_cards(tmp_path: Path) -> None:
    new_architecture_card = build_thesis_test_ledger(
        tmp_path, [], [], [], analysis_purpose="COMPANY_JUDGMENT_ONLY",
        analogy_transfer_cards=[{"industry_architecture": {}}],
        change_reason="freeze a new CJO industry architecture experiment", freeze=True,
    )
    ordinary_cjo = build_thesis_test_ledger(
        tmp_path, [], [], [], analysis_purpose="COMPANY_JUDGMENT_ONLY",
        change_reason="freeze ordinary CJO mechanism research", freeze=True,
    )

    assert new_architecture_card["freeze"]["industry_architecture_provenance_contract_version"] == (
        INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION
    )
    assert "industry_architecture_provenance_contract_version" not in ordinary_cjo["freeze"]


def test_cjo_no_probability_rejects_probability_objects_or_ids(tmp_path: Path) -> None:
    payload = _no_probability_company_judgment_payload(tmp_path, selection_status="NO_PRIMARY")
    payload["probability_sets"] = [_probabilities()]
    payload["competitive_tests"][0]["probability_set_id"] = "prob.core"

    validation = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_no_probability_cjo_report(selected=False),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert validation["state"] == "INVALID"
    assert "company_judgment_no_probability_probability_sets_forbidden" in validation["invalid_findings"]
    assert "test.core:company_judgment_no_probability_set_id_forbidden" in validation["invalid_findings"]


def test_cjo_qualified_probability_rejects_missing_empirical_qualification(tmp_path: Path) -> None:
    payload = _selection_ready_company_judgment_payload(tmp_path)
    payload["probability_mode"] = "QUALIFIED_PROBABILITY"

    validation = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)

    assert validation["state"] == "INVALID"
    assert "company_judgment_probability_qualification_missing" in validation["incomplete_findings"]
    assert any(
        item.endswith("company_judgment_qualified_probability_requires_empirical_kind")
        for item in validation["invalid_findings"]
    )


def test_cjo_qualified_probability_accepts_traceable_external_frequency_basis(tmp_path: Path) -> None:
    payload = _selection_ready_company_judgment_payload(tmp_path)
    evidence_path = tmp_path / "claim_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["claims"][0]["raw_facts"].append({
        "evidence_id": "ev.external-frequency", "source_id": "DOC:industry-panel",
        "source_group_id": "licensed-industry-panel", "fact": "同定义样本中 36/60 个已结算 episode 达成终局结果。",
        "authority": "licensed_industry_data", "claim_distance": "raw_data",
        "published_at": "2026-07-15", "data_as_of": "2026-06-30",
        "direct_support": True, "support_type": "context", "basis_match": "exact",
        "conflict_of_interest": "independent provider",
    })
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    payload["probability_mode"] = "QUALIFIED_PROBABILITY"
    payload["probability_qualification"] = {
        "event_definition": "三年内同口径客户留存恢复并形成可观测 owner-cash 结果。",
        "calibration_plan": "在同定义独立样本到期后按冻结 outcome 计算 Brier 与校准曲线。",
        "as_of": "2026-08-02",
        "external_frequency_evidence_ids": ["ev.external-frequency"],
        "external_frequency_definition": "独立提供商按相同客户 cohort、三年窗口和终局定义统计的已结算比例。",
    }
    for estimate in payload["probability_sets"][0]["estimates"]:
        estimate["kind"] = "frequency"

    validation = validate_thesis_test_ledger(payload, output_dir=tmp_path, enforced=False)

    assert validation["state"] == "REVIEWABLE"


def test_forward_judgments_must_reach_value_and_expected_return_identities(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    for judgment in payload["forward_judgments"]:
        judgment["decision_entry_ids"] = ["vfinal"]
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, forward_judgment_required=True,
    )
    assert "forward_judgment_decision_link_missing:expected_return" in result["forward_judgment_incomplete_findings"]


def test_declared_mechanism_cannot_be_used_as_a_terminal_central_path_scenario(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["probability_sets"][0]["estimates"][0]["scenario_role"] = "MECHANISM"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert "prob.core.estimates[0]:scenario_role_not_terminal_outcome" in result["forward_judgment_invalid_findings"]


def test_forward_judgments_must_bind_a_mechanism_chain(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["forward_judgments"][0].pop("mechanism_chain_ids")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert "fj.retention:mechanism_chain_ids_missing" in result["forward_judgment_incomplete_findings"]


def test_forward_judgments_require_a_comparable_frozen_baseline(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["forward_judgments"][0].pop("baseline")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert "fj.retention:baseline_missing" in result["forward_judgment_incomplete_findings"]


def test_forward_judgment_baseline_cannot_change_the_settlement_target(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["forward_judgments"][0]["baseline"]["prediction"]["unit"] = "RMB/share"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert "fj.retention:baseline_prediction_unit_does_not_match_judgment" in result["forward_judgment_invalid_findings"]


def test_forward_judgment_baseline_must_reconcile_to_its_frozen_simple_rule(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["forward_judgments"][0]["baseline"]["calculation"]["inputs"][0]["value"] = 80.0
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert "fj.retention:baseline_carry_forward_value_does_not_match_input" in result["forward_judgment_invalid_findings"]


def test_forward_judgment_requires_a_lossless_settlement_contract(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["forward_judgments"][0].pop("settlement_contract")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert "fj.retention:settlement_contract_missing" in result["forward_judgment_incomplete_findings"]


def test_forward_judgments_freeze_a_rival_pair_and_non_price_analogy_card(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )

    assert result["state"] == "REVIEWABLE"
    assert result["rival_hypothesis_pair_state"] == "DECISION_READY"
    assert result["analogy_transfer_card_state"] == "DECISION_READY"


def test_forward_judgment_can_preregister_a_versioned_industry_operating_source(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    outcome = payload["forward_judgments"][0]["observable_outcome"]
    outcome["allowed_source_types"] = ["LICENSED_INDUSTRY_DATA"]
    outcome["industry_measurement_inference"] = "WITHIN_PROVIDER_RELATIVE_CHANGE"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )

    assert result["state"] == "REVIEWABLE"


def test_new_frozen_industry_fj_requires_a_stable_series_contract(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    judgment = payload["forward_judgments"][0]
    outcome = judgment["observable_outcome"]
    outcome["allowed_source_types"] = ["LICENSED_INDUSTRY_DATA"]
    outcome["industry_measurement_inference"] = "WITHIN_PROVIDER_RELATIVE_CHANGE"
    payload["freeze"]["frozen"] = True
    # Existing frozen artifacts predate the P27 contract marker and remain
    # readable; only newly produced freezes carry the marker below.
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    assert validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )["state"] == "DECISION_READY"
    payload["freeze"]["forward_judgment_contract_version"] = FORWARD_JUDGMENT_CONTRACT_VERSION
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)

    missing = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert "fj.retention:observable_outcome:licensed_industry_series_contract_missing" in missing["incomplete_findings"]

    judgment["settlement_contract"]["source_ids"] = ["AVC:TEST:AC:2026:ORIGINAL"]
    outcome["licensed_industry_series_contract"] = {
        "pre_cutoff_source_id": "AVC:TEST:AC:2026:ORIGINAL",
        "provider_id": "AVC", "dataset_id": "room-air-conditioner-retail-tracker",
        "metric_id": judgment["prediction"]["metric"], "semantic": "RETAIL_SELL_OUT",
        "geography": "中国大陆国内零售市场", "product_mapping_id": "AVC-ROOM-AC-v1",
        "channel_mapping_id": "AVC-RETAIL-v1", "brand_mapping_id": "AVC-GREE-v1",
        "denominator_mapping_id": "AVC-ALL-BRANDS-v1",
    }
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    assert validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )["state"] == "DECISION_READY"


def test_forward_judgment_rejects_a_directional_vendor_sensor_as_a_numeric_settlement_source(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    outcome = payload["forward_judgments"][0]["observable_outcome"]
    outcome["allowed_source_types"] = ["LICENSED_INDUSTRY_DATA"]
    outcome["industry_measurement_inference"] = "DIRECTIONAL_SENSOR_ONLY"

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )

    assert result["state"] == "INVALID"
    assert "fj.retention:industry_measurement_inference_not_quantitative" in result["invalid_findings"]


def test_new_g1j_policy_requires_pair_and_card_but_legacy_policy_does_not(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload.pop("rival_hypothesis_pairs")
    payload.pop("analogy_transfer_cards")

    legacy = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )
    assert legacy["state"] == "REVIEWABLE"
    assert legacy["rival_hypothesis_pair_state"] == "SKIP"

    g1j = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert g1j["state"] == "INCOMPLETE"
    assert "rival_hypothesis_pairs_required_for_forward_judgment" in g1j["rival_hypothesis_pair_incomplete_findings"]
    assert "analogy_transfer_cards_required_for_forward_judgment" in g1j["analogy_transfer_card_incomplete_findings"]


def test_new_g1j_policy_accepts_complete_pair_and_card(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "REVIEWABLE"
    assert result["rival_hypothesis_pair_required"] is True


def test_new_g1j_policy_forbids_unverified_near_miss_as_primary_support(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    card = payload["analogy_transfer_cards"][0]
    card["support_role"] = "PRIMARY_SUPPORT"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INVALID"
    assert "ATC:retention-vs-erosion:unknown_near_miss_cannot_be_primary_support" in result["analogy_transfer_card_invalid_findings"]


def test_new_g1j_policy_requires_identity_for_verified_near_miss(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    card = payload["analogy_transfer_cards"][0]
    card["support_role"] = "PRIMARY_SUPPORT"
    card["strongest_near_miss"] = {
        "status": "VERIFIED_EPISODE",
        "case_id": "not-a-case",
        "episode_id": "MEP:historical-near-miss",
        "outcome_event_id": "CASEEV:historical-near-miss",
        "structural_break": "A different customer alternative made the apparent analogue fail.",
        "source_reference": "CASEEV:historical-near-miss",
    }
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INVALID"
    assert "ATC:retention-vs-erosion:strongest_near_miss_case_id_invalid" in result["analogy_transfer_card_invalid_findings"]


def test_new_g1j_policy_requires_verified_near_miss_to_exist_in_case_library(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    card = payload["analogy_transfer_cards"][0]
    card["support_role"] = "PRIMARY_SUPPORT"
    card["strongest_near_miss"] = {
        "status": "VERIFIED_EPISODE",
        "case_id": "CASE:missing-near-miss",
        "episode_id": "MEP:missing-near-miss",
        "outcome_event_id": "CASEEV:missing-near-miss",
        "structural_break": "A different customer alternative made the apparent analogue fail.",
        "source_reference": "CASEEV:missing-near-miss",
    }
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True, case_library_dir=tmp_path / "empty-library",
    )
    assert result["state"] == "INVALID"
    assert "ATC:retention-vs-erosion:strongest_near_miss_case_not_registered" in result["analogy_transfer_card_invalid_findings"]


def test_rival_pair_requires_each_side_to_expose_a_critical_assumption(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["rival_hypothesis_pairs"][0].pop("critical_assumptions")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INCOMPLETE"
    assert "RHP:retention-vs-erosion:critical_assumptions_missing" in result["rival_hypothesis_pair_incomplete_findings"]


def test_selected_path_cannot_rely_on_unknown_critical_assumption(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    assumption = payload["rival_hypothesis_pairs"][0]["critical_assumptions"][0]
    assumption.update({"status": "UNKNOWN", "conservative_treatment": "Do not select the primary mechanism until an equivalent discriminator is available."})
    assumption.pop("linked_discriminator_ids")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INCOMPLETE"
    assert "RHP:retention-vs-erosion:selected_primary_critical_assumption_unknown" in result["rival_hypothesis_pair_incomplete_findings"]


def test_rival_pair_requires_a_stepwise_causal_trace(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["rival_hypothesis_pairs"][0].pop("causal_trace")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INVALID"
    assert "RHP:retention-vs-erosion:causal_trace_missing" in result["rival_hypothesis_pair_incomplete_findings"]
    assert (
        "ATC:retention-vs-erosion:industry_architecture_causal_edge_not_in_target_pair"
        in result["analogy_transfer_card_invalid_findings"]
    )


def test_rival_pair_rejects_a_nested_predicate_that_can_never_support_the_rival(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    signal = payload["rival_hypothesis_pairs"][0]["discriminators"][0]
    signal["rival_prediction"] = {
        "metric": "same_scope_retention", "operator": "AT_LEAST", "value": 95.0,
        "unit": "%", "horizon": "FY2027H1", "resolution_due": "2027-08-02",
    }

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert result["state"] == "INVALID"
    assert (
        "RHP:retention-vs-erosion.discriminators[0]:predictions_do_not_allow_both_sides_to_win"
        in result["rival_hypothesis_pair_invalid_findings"]
    )


def test_pair_predicate_gate_matches_the_settlement_logic_across_point_and_range_shapes() -> None:
    point_predictions = [
        {"operator": operator, "value": value}
        for operator, value in product(("AT_LEAST", "AT_MOST", "EQUALS"), (-1.0, 0.0, 1.0))
    ]
    range_predictions = [
        {"operator": "RANGE", "range_low": low, "range_high": high}
        for low, high in product((-1.0, 0.0, 1.0), repeat=2)
        if low <= high
    ]
    predictions = [*point_predictions, *range_predictions]

    for primary, rival in product(predictions, repeat=2):
        boundaries = sorted({
            *([primary["value"]] if "value" in primary else [primary["range_low"], primary["range_high"]]),
            *([rival["value"]] if "value" in rival else [rival["range_low"], rival["range_high"]]),
        })
        candidates = {boundaries[0] - 1.0, boundaries[-1] + 1.0, *boundaries}
        candidates.update(math.nextafter(boundary, -math.inf) for boundary in boundaries)
        candidates.update(math.nextafter(boundary, math.inf) for boundary in boundaries)
        candidates.update((left + right) / 2 for left, right in zip(boundaries, boundaries[1:]))
        expected = any(
            _prediction_is_met_at(primary, value) and not _prediction_is_met_at(rival, value)
            for value in candidates
        ) and any(
            _prediction_is_met_at(rival, value) and not _prediction_is_met_at(primary, value)
            for value in candidates
        )

        assert _pair_allows_each_side_to_win(primary, rival) is expected
        assert hbt_pair_allows_each_side_to_win(primary, rival) is expected


def test_causal_trace_cannot_link_the_wrong_pair_or_chain(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    edge = payload["rival_hypothesis_pairs"][0]["causal_trace"][0]
    edge["mechanism_chain_id"] = "mechanism.erosion_to_cash"
    edge["linked_discriminator_ids"] = ["RHPSIG:not-this-pair"]
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INVALID"
    findings = result["rival_hypothesis_pair_invalid_findings"]
    assert "RHP:retention-vs-erosion.causal_trace[0]:mechanism_chain_side_mismatch" in findings
    assert "RHP:retention-vs-erosion.causal_trace[0]:unknown_or_cross_pair_discriminator:RHPSIG:not-this-pair" in findings


def test_rival_pair_requires_every_frozen_signal_to_test_both_causal_traces(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    for edge in payload["rival_hypothesis_pairs"][0]["causal_trace"]:
        if edge.get("status") == "TESTABLE":
            edge["linked_discriminator_ids"] = [
                signal_id for signal_id in edge["linked_discriminator_ids"]
                if signal_id != "RHPSIG:fj.owner_cash"
            ]
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert result["state"] == "INCOMPLETE"
    findings = result["rival_hypothesis_pair_incomplete_findings"]
    assert "RHP:retention-vs-erosion:causal_trace_primary_signal_unlinked:RHPSIG:fj.owner_cash" in findings
    assert "RHP:retention-vs-erosion:causal_trace_rival_signal_unlinked:RHPSIG:fj.owner_cash" in findings


def test_material_third_explanation_can_use_a_second_pair_without_forcing_a_binary_universe(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    probabilities = payload["probability_sets"][0]["estimates"]
    probabilities[0]["value"] = 0.5; probabilities[0]["interval"] = [0.4, 0.6]
    probabilities[1]["value"] = 0.3; probabilities[1]["interval"] = [0.2, 0.4]
    probabilities.append({
        "scenario_id": "composition", "label": "产品组合变化而非留存机制主导",
        "kind": "analyst_subjective", "value": 0.2, "interval": [0.1, 0.3],
        "basis": "现有事实无法排除产品结构变化。", "source_ids": ["compute_bundle.json"],
        "as_of": "2026-08-02", "scenario_role": "TERMINAL_OUTCOME",
    })
    composition_chain = deepcopy(payload["mechanism_chains"][1])
    composition_chain.update({
        "chain_id": "mechanism.composition_to_cash", "scenario_id": "composition",
        "mechanism": "产品组合变化先改变留存表象和毛利，再以现金转换检验是否形成真实 owner cash。",
    })
    payload["mechanism_chains"].append(composition_chain)

    extra_judgments = []
    for source, judgment_id, horizon, due, stage in (
        (payload["forward_judgments"][0], "fj.composition_early", "FY2027H1", "2027-08-02", "EARLY_MECHANISM"),
        (payload["forward_judgments"][1], "fj.composition_terminal", "FY2029", "2029-12-31", "TERMINAL_OPERATING"),
    ):
        judgment = deepcopy(source)
        judgment["judgment_id"] = judgment_id
        judgment["statement"] = "产品组合解释的 " + judgment["statement"]
        judgment["rival_hypothesis_pair_id"] = "RHP:retention-vs-composition"
        judgment["rival_signal_id"] = "RHPSIG:" + judgment_id
        judgment["mechanism_chain_ids"] = ["mechanism.retention_to_cash"]
        judgment["prediction"]["horizon"] = horizon; judgment["prediction"]["resolution_due"] = due
        judgment["baseline"]["baseline_id"] = "baseline." + judgment_id
        judgment["baseline"]["prediction"]["horizon"] = horizon; judgment["baseline"]["prediction"]["resolution_due"] = due
        judgment["settlement_contract"]["calibration_claim_id"] = "HBTCLM:" + judgment_id
        if stage == "EARLY_MECHANISM":
            judgment["observable_outcome"]["measurement_period"] = {
                "kind": "REPORTING_PERIOD", "start": "2027-01-01", "end": "2027-06-30",
            }
        extra_judgments.append(judgment)
    payload["forward_judgments"].extend(extra_judgments)

    composition_pair = {
        "pair_id": "RHP:retention-vs-composition", "competitive_test_id": "test.core",
        "primary_mechanism_chain_id": "mechanism.retention_to_cash",
        "rival_mechanism_chain_id": "mechanism.composition_to_cash",
        "common_fact_evidence_ids": ["ev.primary", "ev.alternative"],
        "critical_assumptions": [{
            "assumption_id": "RHPASM:retention-vs-composition-primary", "mechanism_side": "PRIMARY",
            "statement": "留存而非产品结构仍是主要的经营驱动。",
            "why_necessary": "否则该 pair 的主机制不能解释利润与现金的后续变化。",
            "status": "TESTABLE", "linked_discriminator_ids": ["RHPSIG:fj.composition_early"],
        }, {
            "assumption_id": "RHPASM:retention-vs-composition-rival", "mechanism_side": "RIVAL",
            "statement": "产品组合可在不改变客户留存的情况下解释经营变化。",
            "why_necessary": "否则第三种解释只是把原有竞争机制改写成新名称。",
            "status": "VERIFIED", "evidence_ids": ["ev.alternative"],
        }],
        "causal_trace": _causal_trace(
            edge_namespace="retention-vs-composition",
            early_signal_id="RHPSIG:fj.composition_early",
            terminal_signal_ids=("RHPSIG:fj.composition_terminal",),
            rival_chain_id="mechanism.composition_to_cash",
        ),
        "discriminators": [{
            "signal_id": "RHPSIG:fj.composition_early", "sequence": 1, "stage": "EARLY_MECHANISM",
            "forward_judgment_id": "fj.composition_early",
            "primary_prediction": extra_judgments[0]["prediction"],
            "rival_prediction": {"metric": "same_scope_retention", "operator": "AT_MOST", "value": 87.0, "unit": "%", "horizon": "FY2027H1", "resolution_due": "2027-08-02"},
        }, {
            "signal_id": "RHPSIG:fj.composition_terminal", "sequence": 2, "stage": "TERMINAL_OPERATING",
            "forward_judgment_id": "fj.composition_terminal",
            "primary_prediction": extra_judgments[1]["prediction"],
            "rival_prediction": {"metric": "owner_cash_index", "operator": "RANGE", "range_low": 80.0, "range_high": 90.0, "unit": "index", "horizon": "FY2029", "resolution_due": "2029-12-31"},
        }],
    }
    payload["rival_hypothesis_pairs"].append(composition_pair)
    composition_card = deepcopy(payload["analogy_transfer_cards"][0])
    composition_card.update({
        "card_id": "ATC:retention-vs-composition", "target_pair_id": composition_pair["pair_id"],
        "source_case_id": "technology_transition",
        "invalidation_conditions": [{
            "signal_id": "RHPSIG:fj.composition_early", "condition": "留存与组合的预期分叉未出现",
            "effect": "把第三种解释保留为未判别而非裁决主机制",
        }],
        "linked_discriminator_ids": ["RHPSIG:fj.composition_early", "RHPSIG:fj.composition_terminal"],
        "industry_architecture": _industry_architecture(
            "RHPSIG:fj.composition_early",
            "RHPEDGE:retention-vs-composition:primary-retention-to-revenue",
        ),
    })
    payload["analogy_transfer_cards"].append(composition_card)
    payload["freeze"] = {"frozen": True, "frozen_at": "2026-08-02T00:00:00+08:00", "fingerprint": ""}
    payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "DECISION_READY"
    assert result["forward_judgment_count"] == 5
    assert result["rival_hypothesis_pair_state"] == "DECISION_READY"


def test_rival_pair_rejects_identical_predictions_or_missing_common_fact(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    signal = payload["rival_hypothesis_pairs"][0]["discriminators"][0]
    signal["rival_prediction"] = dict(signal["primary_prediction"])
    payload["rival_hypothesis_pairs"][0]["common_fact_evidence_ids"] = []
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )

    assert "RHP:retention-vs-erosion:common_fact_evidence_ids_missing" in result["rival_hypothesis_pair_incomplete_findings"]
    assert "RHP:retention-vs-erosion.discriminators[0]:predictions_not_discriminating" in result["rival_hypothesis_pair_invalid_findings"]


def test_rival_pair_requires_ordered_early_and_terminal_signals(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["rival_hypothesis_pairs"][0]["discriminators"][1]["sequence"] = 1
    payload["rival_hypothesis_pairs"][0]["discriminators"][0]["stage"] = "TERMINAL_OPERATING"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )

    findings = result["rival_hypothesis_pair_invalid_findings"]
    assert "RHP:retention-vs-erosion:discriminator_sequence_not_contiguous" in findings
    assert "RHP:retention-vs-erosion:early_mechanism_signal_missing" in findings


def test_rival_pair_requires_its_signal_due_dates_to_follow_the_frozen_sequence(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    terminal = next(item for item in payload["forward_judgments"] if item["judgment_id"] == "fj.owner_cash")
    terminal["prediction"]["resolution_due"] = "2027-08-02"
    terminal["baseline"]["prediction"]["resolution_due"] = "2027-08-02"
    pair_terminal = payload["rival_hypothesis_pairs"][0]["discriminators"][1]
    pair_terminal["primary_prediction"]["resolution_due"] = "2027-08-02"
    pair_terminal["rival_prediction"]["resolution_due"] = "2027-08-02"

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )

    assert (
        "RHP:retention-vs-erosion:early_signal_resolution_due_not_before_terminal_signal"
        in result["rival_hypothesis_pair_invalid_findings"]
    )


def test_analogy_card_requires_near_miss_and_cannot_become_a_valuation_input(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    card = payload["analogy_transfer_cards"][0]
    card.pop("strongest_near_miss")
    card["valuation_input"] = "not permitted"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, monitoring_required=True, forward_judgment_required=True,
    )

    assert "ATC:retention-vs-erosion:strongest_near_miss_missing" in result["analogy_transfer_card_incomplete_findings"]
    assert "ATC:retention-vs-erosion:forbidden_price_probability_or_valuation_field" in result["analogy_transfer_card_invalid_findings"]


def test_analogy_card_requires_a_structural_application_rule(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["analogy_transfer_cards"][0].pop("application_rule")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INCOMPLETE"
    assert "ATC:retention-vs-erosion:application_rule_missing" in result["analogy_transfer_card_incomplete_findings"]


def test_industry_architecture_requires_a_linked_pair_discriminator(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["analogy_transfer_cards"][0]["industry_architecture"]["interface_discriminator"]["signal_id"] = "RHPSIG:not-linked"
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INVALID"
    assert "ATC:retention-vs-erosion:industry_architecture_discriminator_not_linked_to_card" in result["analogy_transfer_card_invalid_findings"]


def test_industry_architecture_unknown_requires_conservative_treatment(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["analogy_transfer_cards"][0]["industry_architecture"]["interface_control"].pop("conservative_treatment")
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert result["state"] == "INCOMPLETE"
    assert "ATC:retention-vs-erosion.industry_architecture.interface_control:unknown_conservative_treatment_missing" in result["analogy_transfer_card_incomplete_findings"]


def test_industry_architecture_requires_own_early_industry_structure_discriminator(tmp_path: Path) -> None:
    terminal_payload = _forward_payload(tmp_path, freeze=False)
    terminal_payload["analogy_transfer_cards"][0]["industry_architecture"]["interface_discriminator"]["signal_id"] = "RHPSIG:fj.owner_cash"
    terminal_result = validate_thesis_test_ledger(
        terminal_payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert terminal_result["state"] == "INVALID"
    assert "ATC:retention-vs-erosion:industry_architecture_discriminator_not_early_mechanism" in terminal_result["analogy_transfer_card_invalid_findings"]

    materiality_payload = _forward_payload(tmp_path, freeze=False)
    materiality_payload["forward_judgments"][0]["materiality"] = "OWNER_CASH"
    materiality_result = validate_thesis_test_ledger(
        materiality_payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    assert materiality_result["state"] == "INVALID"
    assert "ATC:retention-vs-erosion:industry_architecture_discriminator_not_industry_structure" in materiality_result["analogy_transfer_card_invalid_findings"]


def test_industry_architecture_requires_a_frozen_target_pair_causal_edge(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    payload["analogy_transfer_cards"][0]["industry_architecture"]["interface_discriminator"]["causal_edge_id"] = "RHPEDGE:not-in-this-pair"

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert result["state"] == "INVALID"
    assert "ATC:retention-vs-erosion:industry_architecture_causal_edge_not_in_target_pair" in result["analogy_transfer_card_invalid_findings"]


def test_industry_architecture_card_cannot_link_another_pairs_signal(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    detached_pair = deepcopy(payload["rival_hypothesis_pairs"][0])
    detached_pair["pair_id"] = "RHP:detached"
    detached_pair["discriminators"] = []
    payload["rival_hypothesis_pairs"].append(detached_pair)
    payload["analogy_transfer_cards"][0]["target_pair_id"] = "RHP:detached"

    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(), enforced=True,
        monitoring_required=True, forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )

    assert result["state"] == "INVALID"
    findings = result["analogy_transfer_card_invalid_findings"]
    assert "ATC:retention-vs-erosion:linked_discriminator_not_in_target_pair" in findings
    assert "ATC:retention-vs-erosion:industry_architecture_discriminator_not_in_target_pair" in findings


def test_malformed_nested_thesis_returns_findings_not_exception(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    payload["probability_sets"] = ["broken"]
    payload["competitive_tests"][0]["flip_condition"] = "broken"

    result = _validate(tmp_path, payload)

    assert result["state"] == "INVALID"
    assert "probability_sets[0]:not_object" in result["invalid_findings"]
    assert any("flip_condition_invalid" in item for item in result["invalid_findings"])


def test_alternative_must_be_genuinely_competitive(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["strongest_alternative"] = payload["competitive_tests"][0]["primary_explanation"]
    assert any("alternative_not_competitive" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_thesis_and_alternative_evidence_ids_must_exist(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["thesis_claim_id"] = "claim.unknown"
    assert any("unknown_thesis_claim" in x for x in _validate(tmp_path, payload)["invalid_findings"])
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["alternative_evidence_ids"] = ["ev.unknown"]
    assert any("unknown_alternative_evidence" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_alternative_evidence_must_actually_challenge_primary(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["alternative_evidence_ids"] = ["ev.primary"]
    assert any("alternative_evidence_does_not_support_alternative" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_observation_predictions_must_discriminate(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); obs = payload["competitive_tests"][0]["discriminating_observations"][0]; obs["alternative_prediction"] = obs["primary_prediction"]
    assert any("predictions_not_discriminating" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_forward_observation_requires_asymmetric_diagnosticity(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    diagnosticity = payload["competitive_tests"][0]["discriminating_observations"][0]["diagnosticity"]
    diagnosticity["alternative_likelihood"] = diagnosticity["primary_likelihood"]
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, forward_judgment_required=True,
    )
    assert "test.core.observations[0]:diagnosticity_not_asymmetric" in result["forward_judgment_invalid_findings"]


def test_observation_and_flip_thresholds_must_exist(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["discriminating_observations"][0]["threshold_id"] = "th.unknown"
    assert any("unknown_threshold" in x for x in _validate(tmp_path, payload)["invalid_findings"])
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["flip_condition"]["threshold_id"] = "th.unknown"
    assert any("flip_threshold_unknown" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_flip_must_map_to_valuation_position_and_action(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["valuation_after_flip"] = "unknown"
    assert any("valuation_after_flip_invalid" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_threshold_requires_valid_basis_and_source(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["thresholds"][0]["basis_type"] = "gut_feeling"; payload["thresholds"][0]["source_ids"] = ["invented_source"]
    result = _validate(tmp_path, payload)
    assert any("basis_type_invalid" in x for x in result["invalid_findings"])
    assert any("source_unresolved" in x for x in result["invalid_findings"])


def test_threshold_precision_cannot_exceed_its_basis(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["thresholds"][1]["threshold_value"] = 85.123
    assert any("pseudo_precision" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_threshold_requires_window_aggregation_seasonality_and_definition(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); threshold = payload["thresholds"][1]; threshold["aggregation"] = "whenever"; threshold["seasonal_adjustment"] = ""
    result = _validate(tmp_path, payload)
    assert any("aggregation_invalid" in x for x in result["invalid_findings"])
    assert any("seasonal_adjustment_missing" in x for x in result["incomplete_findings"])


def test_expert_judgment_threshold_is_visible_warning(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["thresholds"][1]["basis_type"] = "expert_judgment"
    assert any("expert_judgment_threshold" in x for x in _validate(tmp_path, payload)["warnings"])


def test_all_decision_triggers_need_justified_thresholds(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["thresholds"] = payload["thresholds"][1:]
    result = _validate(tmp_path, payload)
    assert "decision_trigger_threshold_missing:trigger.buy" in result["incomplete_findings"]


def test_threshold_action_must_match_decision_trigger(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["thresholds"][0]["action"] = "exit"
    assert any("action_decision_trigger_mismatch" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_probability_scenarios_must_be_mece(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["probability_sets"][0]["mutually_exclusive"] = False
    assert any("not_mutually_exclusive" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_probability_scenarios_must_map_to_both_explanations(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["competitive_tests"][0]["alternative_scenario_id"] = "primary"
    result = _validate(tmp_path, payload)
    assert any("scenario_mapping_not_distinct" in x for x in result["invalid_findings"])


def test_probabilities_must_sum_to_one(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["probability_sets"][0]["estimates"][0]["value"] = 0.8
    assert any("probabilities_not_sum_to_one" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_subjective_probability_must_admit_uncertainty(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); estimate = payload["probability_sets"][0]["estimates"][0]; estimate["value"] = 0.6123; estimate["interval"] = [0.61, 0.62]
    result = _validate(tmp_path, payload)
    assert any("subjective_false_precision" in x for x in result["invalid_findings"])
    assert any("subjective_probability_overprecise" in x for x in result["invalid_findings"])


def test_frequency_probability_requires_empirical_source(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); estimate = payload["probability_sets"][0]["estimates"][0]; estimate["kind"] = "frequency"; estimate["source_ids"] = []
    assert any("empirical_source_missing" in x for x in _validate(tmp_path, payload)["incomplete_findings"])


def test_probability_interval_must_contain_estimate(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["probability_sets"][0]["estimates"][0]["interval"] = [0.1, 0.2]
    assert any("interval_inconsistent" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_report_anchors_are_bidirectionally_validated(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    report = "## Ch9 风险\n[thesis-test: unknown] [threshold: unknown] [probability: unknown]"
    result = validate_thesis_test_ledger(payload, output_dir=tmp_path, report_text=report, enforced=True)
    assert any("reference_missing" in x for x in result["incomplete_findings"])
    assert any("unknown_test_reference" in x for x in result["invalid_findings"])


def test_valid_thesis_is_bound_then_frozen_without_llm_chapter_rewrite(tmp_path: Path) -> None:
    initialize_thesis_test_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path, freeze=False)
    chapters = tmp_path / "chapters"; chapters.mkdir()
    for idx in (9, 13, 14):
        (chapters / f"_ch{idx:02d}.md").write_text(f"## Ch{idx} 正文\n原有分析", encoding="utf-8")
    report = "\n".join(path.read_text(encoding="utf-8") for path in sorted(chapters.glob("_ch*.md")))
    first = persist_thesis_test_ledger(tmp_path, payload, report_text=report)
    assert first["written"] is True and first["validation"]["state"] == "INCOMPLETE"
    assert bind_thesis_test_references(tmp_path, payload)["anchors_inserted"] >= 5
    rebound = "\n".join(path.read_text(encoding="utf-8") for path in sorted(chapters.glob("_ch*.md")))
    promoted = promote_reviewable_thesis_test(tmp_path, report_text=rebound)
    assert promoted["promoted"] is True
    assert evaluate_output_thesis_test(tmp_path, report_text=rebound, persist=False)["state"] == "DECISION_READY"


def test_frozen_thesis_test_rejects_drift(tmp_path: Path) -> None:
    initialize_thesis_test_policy(tmp_path, run_id="run", enforced=True); original = _payload(tmp_path)
    assert persist_thesis_test_ledger(tmp_path, original, report_text=_report())["written"] is True
    changed = _payload(tmp_path); changed["competitive_tests"][0]["strongest_alternative"] = "被静默改写的解释"
    changed = build_thesis_test_ledger(tmp_path, changed["competitive_tests"], changed["thresholds"], changed["probability_sets"], change_reason="attempted drift", freeze=True)
    result = persist_thesis_test_ledger(tmp_path, changed, report_text=_report())
    assert result["written"] is False and result["thesis_test_frozen"] is True


def test_explicit_frozen_update_repairs_stale_fingerprint_without_semantic_drift(
    tmp_path: Path,
) -> None:
    initialize_thesis_test_policy(tmp_path, run_id="run", enforced=True)
    original = _payload(tmp_path)
    assert persist_thesis_test_ledger(tmp_path, original, report_text=_report())["written"] is True
    stale = json.loads((tmp_path / "thesis_test.json").read_text())
    stale["freeze"]["fingerprint"] = "stale"
    (tmp_path / "thesis_test.json").write_text(json.dumps(stale), encoding="utf-8")
    repaired = json.loads(json.dumps(stale))
    repaired["freeze"]["fingerprint"] = thesis_test_fingerprint(repaired)

    result = persist_thesis_test_ledger(
        tmp_path, repaired, report_text=_report(), allow_frozen_update=True,
    )

    assert result["written"] is True
    assert result["diff"]["status"] == "METADATA_REPAIRED"
    assert evaluate_output_thesis_test(
        tmp_path, report_text=_report(), persist=False,
    )["state"] == "DECISION_READY"


def test_new_policy_missing_ledger_maps_completion_to_incomplete(tmp_path: Path) -> None:
    initialize_thesis_test_policy(tmp_path, run_id="run", enforced=True)
    assert evaluate_output_thesis_test(tmp_path, persist=False)["state"] == "INCOMPLETE"
    completion = evaluate_report_completion("draft", str(tmp_path))
    assert completion.status == "INCOMPLETE" and completion.validators["thesis_test"]["state"] == "INCOMPLETE"


def test_invalid_thesis_test_maps_completion_to_invalid(tmp_path: Path) -> None:
    initialize_thesis_test_policy(tmp_path, run_id="run", enforced=True); payload = _payload(tmp_path); payload["probability_sets"][0]["estimates"][0]["value"] = 0.9
    (tmp_path / "thesis_test.json").write_text(json.dumps(payload), encoding="utf-8")
    assert evaluate_report_completion(_report(), str(tmp_path)).status == "INVALID"


def test_invalid_thesis_candidate_is_preserved_for_deterministic_repair(tmp_path: Path) -> None:
    initialize_thesis_test_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path, freeze=False)
    payload["competitive_tests"][0]["discriminating_observations"][0]["threshold_id"] = "missing"
    result = persist_thesis_test_ledger(tmp_path, payload, report_text=_report())
    assert result["written"] is False
    preserved = json.loads((tmp_path / "thesis_test_last_rejected.json").read_text(encoding="utf-8"))
    assert preserved["competitive_tests"][0]["test_id"] == "test.core"


def test_thesis_writer_exposes_nested_schema_to_provider() -> None:
    from scripts.turtle_agent.tools.write_tools import write_thesis_test_ledger
    params = write_thesis_test_ledger._tool_meta["parameters"]
    test_properties = params["competitive_tests"]["items"]["properties"]
    threshold_properties = params["thresholds"]["items"]["properties"]
    probability_properties = params["probability_sets"]["items"]["properties"]
    assert "discriminating_observations" in test_properties
    observation_properties = test_properties["discriminating_observations"]["items"]["properties"]
    assert "diagnosticity" in observation_properties
    assert "diagnosticity" in test_properties["discriminating_observations"]["items"]["required"]
    assert "discrimination_target" in threshold_properties
    assert "estimates" in probability_properties
    assert "outcome_scope" in probability_properties
    assert "mechanism_chains" in params
    assert "selected_scenario_id" in params["central_path"]["properties"]
    assert "selection_admission" in params
    assert "selection_register_binding" in params["selection_admission"]["properties"]
    selection_evidence = params["selection_admission"]["properties"]["selection_evidence"]["items"]
    assert "source_group_id" in selection_evidence["properties"]
    for field in ("forward_judgment_id", "primary_causal_edge_id", "leading_threshold_id"):
        assert field in selection_evidence["properties"]
        assert field in selection_evidence["required"]
    assert "mechanism_chain_ids" in params["forward_judgments"]["items"]["properties"]
    assert "financial_driver_ids" in params["forward_judgments"]["items"]["properties"]
    assert "baseline" in params["forward_judgments"]["items"]["properties"]
    baseline = params["forward_judgments"]["items"]["properties"]["baseline"]
    assert "calculation" in baseline["properties"]
    assert "calculation" in baseline["required"]
    assert "settlement_contract" in params["forward_judgments"]["items"]["properties"]
    assert "observable_outcome" in params["forward_judgments"]["items"]["properties"]
    source_types = params["forward_judgments"]["items"]["properties"]["observable_outcome"]["properties"]["allowed_source_types"]["items"]["enum"]
    assert "LICENSED_INDUSTRY_DATA" in source_types
    assert params["forward_judgments"]["items"]["properties"]["observable_outcome"]["properties"]["industry_measurement_inference"]["enum"] == ["WITHIN_PROVIDER_RELATIVE_CHANGE", "LEVEL_WITH_STATED_LIMITS"]
    series_contract = params["forward_judgments"]["items"]["properties"]["observable_outcome"]["properties"]["licensed_industry_series_contract"]
    assert "pre_cutoff_source_id" in series_contract["required"]
    assert "denominator_mapping_id" in series_contract["required"]
    assert "rival_hypothesis_pairs" in params
    assert "analogy_transfer_cards" in params
    assert "rival_prediction" in params["rival_hypothesis_pairs"]["items"]["properties"]["discriminators"]["items"]["properties"]
    trace = params["rival_hypothesis_pairs"]["items"]["properties"]["causal_trace"]
    assert "why_diagnostic" in trace["items"]["properties"]
    assert "causal_trace" in params["rival_hypothesis_pairs"]["items"]["required"]
    assert params["analogy_transfer_cards"]["items"]["properties"]["settlement_rule"]["enum"] == ["DERIVE_FROM_PAIR_SIGNALS_ONLY"]
    architecture = params["analogy_transfer_cards"]["items"]["properties"]["industry_architecture"]
    assert "appropriation_node" in architecture["required"]
    assert "minimal_external_query" in architecture["properties"]
    assert "causal_edge_id" in architecture["properties"]["interface_discriminator"]["required"]
    architecture_element = architecture["properties"]["division_of_labour"]
    assert "evidence_bindings" in architecture_element["properties"]
    assert "canonical_source_id" in architecture_element["properties"]["evidence_bindings"]["items"]["properties"]
    assert "application_rule" in params["analogy_transfer_cards"]["items"]["required"]


def test_old_output_without_policy_remains_skip(tmp_path: Path) -> None:
    assert evaluate_output_thesis_test(tmp_path, persist=False)["state"] == "SKIP"


def test_thesis_test_tool_is_auto_discoverable() -> None:
    registry = ToolRegistry(); registry.auto_discover("turtle_agent.tools.write_tools")
    assert "write_thesis_test_ledger" in registry.list_tools()


def test_thesis_failure_routes_relevant_chapters() -> None:
    completion = {"blocking_findings": ["Thesis test: INCOMPLETE: thesis_test_missing"]}
    assert _repair_targets_from_completion(completion) == (14, 0)
