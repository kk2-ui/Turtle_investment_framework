from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.decisive_question import (
    _finding_numbers,
    _numbers_supported,
    _unlabeled_inference_claims,
    build_decisive_question_findings,
    build_decisive_question_plan,
    evaluate_output_decisive_questions,
    initialize_decisive_question_policy,
    patch_decisive_question_findings,
    persist_decisive_question_findings,
    refresh_decisive_question_plan,
    rebind_decisive_findings_to_current_plan,
    validate_decisive_question_findings,
    validate_decisive_question_plan,
)
from scripts.insight_ledger import validate_insight_ledger
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.read_tools import (
    read_decisive_question_plan,
    read_structured_ledger_contract,
)
from scripts.turtle_agent.tools.write_tools import write_decisive_question_findings


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _fixture(output: Path) -> None:
    observation = {
        "observation_id": "OBS:annual:operations:revenue:2025:abc123",
        "status": "VERIFIED", "domain": "operations", "fact_name": "revenue",
    }
    _write(output / "fact_observations.json", {"observations": [observation]})
    _write(output / "report_context.json", {
        "meta": {"report_id": "CASE-1", "issuer": "样本公司", "context_fingerprint": "a" * 64},
        "domains": {"operations": [observation]}, "unresolved_gaps": [],
    })
    _write(output / "analysis_contract.json", {"ts_code": "000001.SZ", "industry": "consumer"})
    _write(output / "compute_bundle.json", {
        "market": {"price_native": 10.0},
        "factor3": {
            "gg": {"base": 7.0}, "gg_discounted": {"base": 5.2}, "gg_fcfe": {"base": 4.8},
            "net_cash_pct_mc": 65.0, "dividend_sustainability_years": 4.0,
            "error_propagation": {"gg_min": 3.0, "gg_max": 8.0},
            "lambda_sensitivity": {"reliability": "unstable"},
            "_income_raw": [
                {"end_date": "2024", "revenue": 100, "n_income_attr_p": 10},
                {"end_date": "2025", "revenue": 105, "n_income_attr_p": 7},
            ],
        },
        "factor4": {
            "II_adjusted": 5.5, "ddm_v_native": 25.0,
            "p_base": {"price_native": 12.0, "p_base_discounted_native": 8.0, "p_fcfe": {"price_native": 9.0}},
        },
    })


def _premise_test_leaves(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(_premise_test_leaves(item, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.update(_premise_test_leaves(item, f"{prefix}[{index}]"))
    else:
        result[prefix] = value
    return result


def _complete_findings(output: Path, plan: dict) -> dict:
    calculations = json.loads(
        (output / "calculation_observations.json").read_text(encoding="utf-8")
    )
    premise_calculation_ids = {
        str(item["metric_path"]): str(item["calculation_id"])
        for item in calculations.get("calculations") or []
        if item.get("tool") == "decisive_plan"
    }
    rows = []
    for question in plan["selected_questions"]:
        question_id = question["question_id"]
        premise_rows = [{
            "premise_key": key, "plan_value": value, "direction": "NEUTRAL",
            "evidence_ids": [
                "OBS:annual:operations:revenue:2025:abc123",
                premise_calculation_ids[f"{question_id}.sensitivity_basis.{key}"],
            ],
            "assessment": "计划前提已在当前证据下复核，暂不单独改变解释方向",
        } for key, value in _premise_test_leaves(question["decision_link"]["sensitivity_basis"]).items()]
        rows.append({
            "question_id": question_id, "outcome": "RESOLVED",
            "evidence_observation_ids": ["OBS:annual:operations:revenue:2025:abc123"],
            "evidence_calculation_ids": [
                premise_calculation_ids[f"{question_id}.sensitivity_basis.{key}"]
                for key in _premise_test_leaves(question["decision_link"]["sensitivity_basis"])
            ],
            "attempted_sources": ["2025年报逐页回读"],
            "signal_results": [{
                "signal_id": question["discriminating_signals"][0]["signal_id"],
                "result": "原始披露更支持解释A", "supports_explanation_id": question["competing_explanations"][0]["explanation_id"],
                "evidence_ids": ["OBS:annual:operations:revenue:2025:abc123"],
            }],
            "explanation_update": {
                "favored_explanation_id": question["competing_explanations"][0]["explanation_id"],
                "confidence_before": 0.5, "confidence_after": 0.7,
                "basis": "VERIFIED事实与区分信号方向一致",
            },
            "decision_update": {
                "valuation_impact": "维持保守基准", "position_impact": "不提高上限",
                "action": "等待价格安全边际", "changed": False, "decision_entry_ids": [],
            },
            "conclusion": "解释A得到有限支持，但仍按保守口径决策。", "unresolved": [],
            "resolution_assessment": {
                "net_support": "MIXED",
                "decision_consistency": "净证据不支持提高动作强度，维持保守决策",
                "premise_resolution": premise_rows,
            },
        })
    return build_decisive_question_findings(output, rows, change_reason="complete bounded research")


def test_plan_is_deterministic_ranked_and_bounded(tmp_path: Path) -> None:
    _fixture(tmp_path)
    first = build_decisive_question_plan(tmp_path, persist=False)
    second = build_decisive_question_plan(tmp_path, persist=False)
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert [item["question_id"] for item in first["selected_questions"]] == [item["question_id"] for item in second["selected_questions"]]
    assert 1 <= len(first["selected_questions"]) <= 3
    assert first["rejected_candidates"] and all(item["rejection_reason"] for item in first["rejected_candidates"])
    assert first["validation"]["state"] == "REVIEWABLE"


def test_known_premises_have_non_circular_direction_policies(tmp_path: Path) -> None:
    _fixture(tmp_path)
    plan = build_decisive_question_plan(tmp_path, persist=False)
    selected = {item["topic_family"]: item for item in plan["selected_questions"]}
    owner_policy = selected["owner_return_hurdle"]["decision_link"]["premise_assessment_policy"]
    assert "SUPPORTS_A" not in owner_policy["gg_discounted_pct"]["allowed_directions"]
    assert owner_policy["ii_pct"]["allowed_directions"] == ["NEUTRAL", "UNKNOWN"]
    operating_policy = selected["operating_transition"]["decision_link"]["premise_assessment_policy"]
    assert operating_policy["revenue_growth_pct"]["allowed_directions"] == ["NEUTRAL", "UNKNOWN"]


def test_plan_rejects_score_tamper_duplicate_family_and_unverified_fact(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=False)
    bad = deepcopy(plan)
    bad["selected_questions"][0]["score"]["priority"] = 0.01
    bad["selected_questions"].append(deepcopy(bad["selected_questions"][0]))
    bad["selected_questions"][0]["competing_explanations"][0]["current_support_observation_ids"] = ["OBS:unknown"]
    result = validate_decisive_question_plan(bad, output_dir=tmp_path, enforced=True)
    assert result["state"] == "INVALID"
    assert any("priority_formula_mismatch" in item for item in result["invalid_findings"])
    assert any("duplicate_selected_topic_family" in item for item in result["invalid_findings"])
    assert any("unknown_or_unverified_observation" in item for item in result["invalid_findings"])


def test_plan_rejects_fake_competition_and_non_discriminating_signal(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=False)
    bad = deepcopy(plan); question = bad["selected_questions"][0]
    question["competing_explanations"][1]["mechanism"] = question["competing_explanations"][0]["mechanism"]
    signal = question["discriminating_signals"][0]
    signal["direction_if_explanation_b"] = signal["direction_if_explanation_a"]
    result = validate_decisive_question_plan(bad, output_dir=tmp_path, enforced=True)
    assert any("explanations_not_competing" in item for item in result["invalid_findings"])
    assert any("signal_has_no_discriminating_direction" in item for item in result["invalid_findings"])


def test_enforced_policy_requires_research_findings(tmp_path: Path) -> None:
    _fixture(tmp_path)
    build_decisive_question_plan(tmp_path, persist=True)
    initialize_decisive_question_policy(tmp_path, run_id="run-1", enforced=True)
    result = evaluate_output_decisive_questions(tmp_path)
    assert result["state"] == "INCOMPLETE"
    assert result["incomplete_findings"] == ["decisive_question_findings_missing"]


def test_new_verified_evidence_warns_without_invalidating_prewrite_plan(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=False)
    context = json.loads((tmp_path / "report_context.json").read_text(encoding="utf-8"))
    context["meta"]["context_fingerprint"] = "b" * 64
    _write(tmp_path / "report_context.json", context)
    result = validate_decisive_question_plan(plan, output_dir=tmp_path, enforced=True)
    assert result["state"] == "REVIEWABLE"
    assert "input_source_changed_after_plan:report_context.json" in result["warnings"]


def test_complete_findings_promote_gate_to_decision_ready(tmp_path: Path) -> None:
    _fixture(tmp_path)
    plan = build_decisive_question_plan(tmp_path, persist=True)
    initialize_decisive_question_policy(tmp_path, run_id="run-2", enforced=True)
    written = persist_decisive_question_findings(tmp_path, _complete_findings(tmp_path, plan))
    assert written["written"] is True
    assert written["validation"]["state"] == "DECISION_READY"
    assert evaluate_output_decisive_questions(tmp_path)["state"] == "DECISION_READY"


def test_compatible_plan_refresh_rebinds_findings_without_model_rewrite(tmp_path: Path) -> None:
    _fixture(tmp_path)
    plan = build_decisive_question_plan(tmp_path, persist=True)
    persist_decisive_question_findings(tmp_path, _complete_findings(tmp_path, plan))
    refreshed = json.loads((tmp_path / "decisive_question_plan.json").read_text(encoding="utf-8"))
    refreshed["input_fingerprint"] = "f" * 64
    _write(tmp_path / "decisive_question_plan.json", refreshed)
    result = rebind_decisive_findings_to_current_plan(tmp_path)
    assert result["rebound"] is True
    rebound = json.loads((tmp_path / "decisive_question_findings.json").read_text(encoding="utf-8"))
    assert rebound["plan_input_fingerprint"] == "f" * 64
    assert result["validation"]["state"] == "DECISION_READY"


def test_compatible_plan_refresh_rebinds_calc_ids_in_nested_prose(tmp_path: Path) -> None:
    _fixture(tmp_path)
    plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    old_calculations = json.loads(
        (tmp_path / "calculation_observations.json").read_text(encoding="utf-8")
    )
    old_id = next(
        row["calculation_id"] for row in old_calculations["calculations"]
        if row["tool"] == "decisive_plan"
    )
    payload["findings"][0]["inference_audit"] = [{
        "inference_id": "I001",
        "claim": f"计划前提[{old_id}]支持保守判断",
        "supporting_evidence_ids": [old_id],
        "strongest_alternative": "该前提可能只是短期扰动",
        "discriminating_observation": "下一期原始披露",
        "decision_if_wrong": "维持仓位上限并重估",
    }]
    persist_decisive_question_findings(tmp_path, payload)
    refreshed = json.loads((tmp_path / "decisive_question_plan.json").read_text(encoding="utf-8"))
    refreshed["input_fingerprint"] = "d" * 64
    _write(tmp_path / "decisive_question_plan.json", refreshed)

    result = rebind_decisive_findings_to_current_plan(tmp_path)

    assert result["rebound"] is True
    rebound = json.loads((tmp_path / "decisive_question_findings.json").read_text(encoding="utf-8"))
    audit = rebound["findings"][0]["inference_audit"][0]
    assert old_id not in json.dumps(audit, ensure_ascii=False)
    assert audit["supporting_evidence_ids"][0].startswith("CALC:")
    assert result["validation"]["state"] == "DECISION_READY"


def test_plan_refresh_does_not_rebind_when_semantic_question_ids_changed(tmp_path: Path) -> None:
    _fixture(tmp_path)
    plan = build_decisive_question_plan(tmp_path, persist=True)
    persist_decisive_question_findings(tmp_path, _complete_findings(tmp_path, plan))
    refreshed = json.loads((tmp_path / "decisive_question_plan.json").read_text(encoding="utf-8"))
    refreshed["input_fingerprint"] = "e" * 64
    refreshed["selected_questions"] = []
    _write(tmp_path / "decisive_question_plan.json", refreshed)
    result = rebind_decisive_findings_to_current_plan(tmp_path)
    assert result["rebound"] is False
    assert result["reason"] == "semantic_identity_changed"


def test_plan_refresh_replaces_only_observation_membership_changes(tmp_path: Path) -> None:
    _fixture(tmp_path)
    old = build_decisive_question_plan(tmp_path, persist=True, enforced=True)
    replacement = {
        "observation_id": "OBS:annual:operations:revenue:2025:replacement",
        "status": "VERIFIED", "domain": "operations", "fact_name": "revenue",
    }
    _write(tmp_path / "fact_observations.json", {"observations": [replacement]})
    context = json.loads((tmp_path / "report_context.json").read_text(encoding="utf-8"))
    context["meta"]["context_fingerprint"] = "b" * 64
    context["domains"] = {"operations": [replacement]}
    _write(tmp_path / "report_context.json", context)

    result = refresh_decisive_question_plan(tmp_path, run_id="refresh", enforced=True)

    assert result["refreshed"] is True
    assert result["reason"] == "observation_membership_only"
    refreshed = json.loads((tmp_path / "decisive_question_plan.json").read_text(encoding="utf-8"))
    assert refreshed["input_fingerprint"] != old["input_fingerprint"]
    audit = json.loads((tmp_path / "decisive_question_plan_refresh.json").read_text(encoding="utf-8"))
    assert audit["removed_observation_ids"] == ["OBS:annual:operations:revenue:2025:abc123"]
    assert audit["added_observation_ids"] == ["OBS:annual:operations:revenue:2025:replacement"]
    assert refreshed["validation"]["state"] == "REVIEWABLE"


def test_plan_refresh_ignores_base_rate_context_fingerprint_only_change(tmp_path: Path) -> None:
    _fixture(tmp_path)
    old = build_decisive_question_plan(tmp_path, persist=True, enforced=True)
    base_rate = json.loads((tmp_path / "base_rate_context.json").read_text(encoding="utf-8"))
    base_rate["context_fingerprint"] = "c" * 64
    _write(tmp_path / "base_rate_context.json", base_rate)

    result = refresh_decisive_question_plan(tmp_path, run_id="refresh", enforced=True)

    assert result["refreshed"] is True
    assert result["reason"] == "observation_membership_only"
    refreshed = json.loads((tmp_path / "decisive_question_plan.json").read_text(encoding="utf-8"))
    assert refreshed["base_rate_context"]["context_fingerprint"] != old["base_rate_context"]["context_fingerprint"]
    audit = json.loads((tmp_path / "decisive_question_plan_refresh.json").read_text(encoding="utf-8"))
    assert audit["status"] == "EVIDENCE_REFRESHED"


def test_plan_refresh_preserves_old_plan_when_question_semantics_change(tmp_path: Path) -> None:
    _fixture(tmp_path)
    old = build_decisive_question_plan(tmp_path, persist=True, enforced=True)
    bundle = json.loads((tmp_path / "compute_bundle.json").read_text(encoding="utf-8"))
    bundle["factor3"]["net_cash_pct_mc"] = 5.0
    bundle["factor3"]["dividend_sustainability_years"] = 0.2
    _write(tmp_path / "compute_bundle.json", bundle)

    result = refresh_decisive_question_plan(tmp_path, run_id="refresh", enforced=True)

    assert result["refreshed"] is False
    assert result["reason"] == "semantic_change_requires_research"
    preserved = json.loads((tmp_path / "decisive_question_plan.json").read_text(encoding="utf-8"))
    assert preserved["input_fingerprint"] == old["input_fingerprint"]
    assert (tmp_path / "decisive_question_plan_candidate.json").is_file()
    audit = json.loads((tmp_path / "decisive_question_plan_refresh.json").read_text(encoding="utf-8"))
    assert audit["status"] == "SEMANTIC_CHANGE_REQUIRES_RESEARCH"


def test_unresolved_finding_cannot_increase_confidence(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    payload["findings"][0]["outcome"] = "INCONCLUSIVE"
    payload["findings"][0]["explanation_update"]["confidence_after"] = 0.8
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert result["state"] == "INVALID"
    assert any("unresolved_research_increased_confidence" in item for item in result["invalid_findings"])


def test_signal_numbers_require_direct_declared_evidence(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    payload["findings"][0]["signal_results"][0]["result"] = "收入增长99%支持解释A"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert result["state"] == "INVALID"
    assert any(
        "signal_numeric_support_mismatch:unsupported=99" in item
        for item in result["invalid_findings"]
    )


def test_human_readable_calculation_alias_is_not_a_verified_identity(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    alias = "CALC:compute_gg:gg_base=7.0"
    payload["findings"][0]["evidence_calculation_ids"] = [alias]
    payload["findings"][0]["signal_results"][0]["evidence_ids"].append(alias)
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert result["state"] == "INVALID"
    assert any("unknown_or_unverified_calculation" in item for item in result["invalid_findings"])


def test_adjacent_citation_cannot_borrow_same_number_from_another_evidence(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    observations = json.loads((tmp_path / "fact_observations.json").read_text(encoding="utf-8"))
    observations["observations"].extend([
        {"observation_id": "OBS:a", "status": "VERIFIED", "raw_value": "6.2", "normalized_value": 6.2},
        {"observation_id": "OBS:b", "status": "VERIFIED", "raw_value": "96.92", "normalized_value": 96.92},
    ])
    _write(tmp_path / "fact_observations.json", observations)
    payload = _complete_findings(tmp_path, plan)
    row = payload["findings"][0]
    row["evidence_observation_ids"].extend(["OBS:a", "OBS:b"])
    signal = row["signal_results"][0]
    signal["evidence_ids"] = ["OBS:a", "OBS:b"]
    signal["result"] = "AA GG=6.2%[OBS:a]；Normalized GG=6.2%[OBS:b]"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any(
        "citation_identity_numeric_mismatch:OBS:b=6.2" in item
        for item in result["invalid_findings"]
    )


def test_unsupported_absolute_assertion_and_dimension_mismatch_are_rejected(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    signal = payload["findings"][0]["signal_results"][0]
    signal["result"] = "收入10M远低于门槛5%，因此排除其他解释并确保回报。"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("unsupported_absolute_assertion:排除|确保" in item for item in result["invalid_findings"])
    assert any("dimensionally_invalid_comparison" in item for item in result["invalid_findings"])


def test_negative_search_and_unlabeled_inference_cannot_close_research(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    signal = payload["findings"][0]["signal_results"][0]
    signal["result"] = "年报全文未发现借款，搜索0 hits，因此表明回报可持续。"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("negative_search_presented_as_fact" in item for item in result["invalid_findings"])
    assert any("unlabeled_analyst_inference" in item for item in result["invalid_findings"])


def test_disclosed_inference_requires_concrete_unresolved_item(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    signal = payload["findings"][0]["signal_results"][0]
    signal["result"] = "[inference:I001] 当前趋势可能由结构性因素驱动。"
    payload["findings"][0]["explanation_update"]["confidence_after"] = 0.55
    payload["findings"][0]["inference_audit"] = [{
        "inference_id": "I001", "claim": "当前趋势可能由结构性因素驱动",
        "supporting_evidence_ids": ["OBS:annual:operations:revenue:2025:abc123"],
        "strongest_alternative": "行业周期造成短期波动",
        "discriminating_observation": "下一期同行与公司趋势是否分化",
        "decision_if_wrong": "维持原估值，不增加仓位",
    }]
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("disclosed_inference_requires_unresolved" in item for item in result["incomplete_findings"])
    payload["findings"][0]["unresolved"] = ["缺少同行和行业周期数据，因果归属待下一期验证"]
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert not any("disclosed_inference_requires_unresolved" in item for item in result["incomplete_findings"])
    assert not any("unlabeled_analyst_inference" in item for item in result["invalid_findings"])


def test_inference_requires_audit_identity_and_limits_confidence_jump(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    finding = payload["findings"][0]
    finding["signal_results"][0]["result"] = "趋势下行[inference:I404]。"
    finding["unresolved"] = ["缺少同行周期数据"]
    finding["explanation_update"]["confidence_after"] = 0.8
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("inference_audit_missing" in item for item in result["incomplete_findings"])
    assert any("unknown_inference_tag:I404" in item for item in result["invalid_findings"])
    assert any("inference_confidence_jump_exceeds_0.05" in item for item in result["invalid_findings"])


def test_resolution_assessment_cannot_bypass_narrative_evidence_gates(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    finding = payload["findings"][0]
    finding["resolution_assessment"]["premise_resolution"][0]["assessment"] = (
        "收入变化证明竞争格局已经结构性恶化。"
    )
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any(
        "premise_resolution[0].assessment:unlabeled_analyst_inference" in item
        for item in result["invalid_findings"]
    )


def test_epistemic_non_proof_is_not_mislabeled_as_positive_inference() -> None:
    assert _unlabeled_inference_claims(
        "净现金比例不能单独证明现金可达，也不证明管理层具有分配意愿。", []
    ) == []
    assert _unlabeled_inference_claims("净现金比例证明现金可达。", [])


def test_resolved_finding_must_settle_every_decision_sensitive_premise(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    assessment = payload["findings"][0]["resolution_assessment"]
    assessment["premise_resolution"] = assessment["premise_resolution"][:-1]
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("premise_not_resolved" in item for item in result["incomplete_findings"])


def test_premise_must_bind_exact_plan_calculation_and_obey_diagnostic_policy(tmp_path: Path) -> None:
    _fixture(tmp_path)
    bundle = json.loads((tmp_path / "compute_bundle.json").read_text(encoding="utf-8"))
    bundle["factor3"]["net_cash_pct_mc"] = 244.6
    bundle["factor3"]["dividend_sustainability_years"] = 31.8
    _write(tmp_path / "compute_bundle.json", bundle)
    plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    cash = next(
        item for item in payload["findings"]
        if item["question_id"].startswith("DQ:cash_value_realization:")
    )
    rows = {item["premise_key"]: item for item in cash["resolution_assessment"]["premise_resolution"]}
    net_cash = rows["net_cash_pct_market_cap"]
    exact_id = next(value for value in net_cash["evidence_ids"] if value.startswith("CALC:"))
    net_cash["evidence_ids"].remove(exact_id)
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("exact_decisive_plan_calculation_missing" in item for item in result["invalid_findings"])

    net_cash["evidence_ids"].append(exact_id)
    net_cash["direction"] = "SUPPORTS_B"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("direction_violates_plan_policy" in item for item in result["invalid_findings"])


def test_opposing_premises_force_mixed_net_support_and_unknown_blocks_resolution(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    rows = payload["findings"][0]["resolution_assessment"]["premise_resolution"]
    assert len(rows) >= 2
    rows[0]["direction"] = "SUPPORTS_A"
    rows[1]["direction"] = "SUPPORTS_B"
    payload["findings"][0]["resolution_assessment"]["net_support"] = "EXPLANATION_A"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("mixed_premises_require_mixed_net_support" in item for item in result["invalid_findings"])
    rows[1]["direction"] = "UNKNOWN"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any("resolved_with_unknown_decision_premise" in item for item in result["invalid_findings"])


def test_decision_values_require_active_ledger_binding(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    _write(tmp_path / "decision_ledger.json", {
        "entries": [{"entry_id": "D-GG", "status": "active", "value": 6.2}]
    })
    payload = _complete_findings(tmp_path, plan)
    payload["findings"][0]["decision_update"]["valuation_impact"] = "GG=6.2%"
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert any(
        "decision_value_missing_binding:6.2:expected_one_of=D-GG" in item
        for item in result["invalid_findings"]
    )
    payload["findings"][0]["decision_update"]["decision_entry_ids"] = ["D-GG"]
    result = validate_decisive_question_findings(payload, plan, output_dir=tmp_path)
    assert not any("decision_value_missing_binding" in item for item in result["invalid_findings"])


def test_opaque_evidence_id_digits_are_not_treated_as_claim_numbers() -> None:
    assert _finding_numbers("GG=6.2%[CALC:754c7f063ceddf03e4484a8f]") == [6.2]
    assert _finding_numbers("[OBS:2025:abc123] 年报") == []


def test_page_numbers_are_ignored_and_normalized_values_allow_display_rounding() -> None:
    assert _finding_numbers("年报p.26及第82页") == []
    assert _numbers_supported(
        "现金及等价物1,509.03M（年报p.26）",
        [{"normalized_value": 1509.025}],
    ) is True


def test_invalid_findings_persist_last_attempt_validation(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    payload = _complete_findings(tmp_path, plan)
    payload["findings"][0]["decision_update"]["changed"] = "no"
    result = persist_decisive_question_findings(tmp_path, payload)
    assert result["written"] is False
    saved = json.loads(
        (tmp_path / "decisive_question_findings_last_attempt_validation.json")
        .read_text(encoding="utf-8")
    )
    assert saved["state"] == "INVALID"
    assert any("decision_changed_not_boolean" in item for item in saved["invalid_findings"])
    assert len(saved["payload_hash"]) == 64


def test_incomplete_findings_are_attempt_only_not_canonical(tmp_path: Path) -> None:
    _fixture(tmp_path); build_decisive_question_plan(tmp_path, persist=True)
    payload = build_decisive_question_findings(tmp_path, [])
    result = persist_decisive_question_findings(tmp_path, payload)
    assert result["written"] is False
    assert result["validation"]["state"] == "INCOMPLETE"
    assert not (tmp_path / "decisive_question_findings.json").exists()
    assert not (tmp_path / "decisive_question_findings_validation.json").exists()
    attempted = json.loads(
        (tmp_path / "decisive_question_findings_last_attempt.json")
        .read_text(encoding="utf-8")
    )
    assert attempted["findings"] == []
    contract = read_structured_ledger_contract(str(tmp_path), ledger="decisive")
    resume = contract["rejected_research_resume"]
    assert resume["authority"] == "non_canonical_failed_attempt"
    assert resume["candidate"]["plan_input_fingerprint"] == payload["plan_input_fingerprint"]
    assert resume["validation"]["state"] == "INCOMPLETE"


def test_empty_last_attempt_cannot_overwrite_complete_best_rejected(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    complete = _complete_findings(tmp_path, plan)
    complete["findings"][0]["decision_update"]["changed"] = "no"
    first = persist_decisive_question_findings(tmp_path, complete)
    assert first["written"] is False
    assert first["validation"]["completed_question_ids"]

    empty = build_decisive_question_findings(tmp_path, [])
    second = persist_decisive_question_findings(tmp_path, empty)
    assert second["validation"]["completed_question_ids"] == []

    best = json.loads(
        (tmp_path / "decisive_question_findings_best_rejected.json")
        .read_text(encoding="utf-8")
    )
    assert len(best["findings"]) == len(plan["selected_questions"])
    contract = read_structured_ledger_contract(str(tmp_path), ledger="decisive")
    assert contract["rejected_research_resume"]["resume_source"] == "best_rejected"
    assert len(contract["rejected_research_resume"]["candidate"]["findings"]) == len(
        plan["selected_questions"]
    )


def test_best_rejected_is_revalidated_before_ranking(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    older = _complete_findings(tmp_path, plan)
    older["findings"][0]["decision_update"]["changed"] = "no"
    persist_decisive_question_findings(tmp_path, older)
    validation_path = tmp_path / "decisive_question_findings_best_rejected_validation.json"
    stale = json.loads(validation_path.read_text(encoding="utf-8"))
    stale["invalid_findings"] = []
    stale["incomplete_findings"] = []
    _write(validation_path, stale)

    newer = _complete_findings(tmp_path, plan)
    newer["findings"][0]["conclusion"] = "这是唯一解释。"
    result = persist_decisive_question_findings(tmp_path, newer)

    assert result["written"] is False
    refreshed = json.loads(validation_path.read_text(encoding="utf-8"))
    assert refreshed.get("validation_refreshed_at")
    best = json.loads(
        (tmp_path / "decisive_question_findings_best_rejected.json").read_text(encoding="utf-8")
    )
    assert best["findings"][0]["decision_update"]["changed"] == "no"


def test_best_rejected_prefers_fewer_total_repairs_after_completed_coverage(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    older = _complete_findings(tmp_path, plan)
    for finding in older["findings"]:
        finding.pop("resolution_assessment")
    persist_decisive_question_findings(tmp_path, older)

    newer = _complete_findings(tmp_path, plan)
    newer["findings"][0]["decision_update"]["changed"] = "no"
    persist_decisive_question_findings(tmp_path, newer)

    best = json.loads(
        (tmp_path / "decisive_question_findings_best_rejected.json").read_text(encoding="utf-8")
    )
    assert best["findings"][0]["decision_update"]["changed"] == "no"


def test_decisive_patch_mode_merges_then_revalidates_full_candidate(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    rejected = _complete_findings(tmp_path, plan)
    rejected["findings"][0]["decision_update"]["changed"] = "no"
    persist_decisive_question_findings(tmp_path, rejected)

    result = patch_decisive_question_findings(tmp_path, [{
        "question_id": rejected["findings"][0]["question_id"],
        "decision_update": {
            "valuation_impact": "维持保守基准", "position_impact": "不提高上限",
            "action": "等待价格安全边际", "changed": False, "decision_entry_ids": [],
        },
    }], change_reason="fix one field")

    assert result["written"] is True
    canonical = json.loads(
        (tmp_path / "decisive_question_findings.json").read_text(encoding="utf-8")
    )
    assert canonical["change_reason"] == "fix one field"


def test_decisive_patch_mode_accepts_premise_resolution_path_alias(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    rejected = _complete_findings(tmp_path, plan)
    valid_rows = deepcopy(
        rejected["findings"][0]["resolution_assessment"]["premise_resolution"]
    )
    rejected["findings"][0]["resolution_assessment"]["premise_resolution"][0][
        "assessment"
    ] = "收入变化证明竞争格局已经结构性恶化。"
    persist_decisive_question_findings(tmp_path, rejected)

    result = patch_decisive_question_findings(tmp_path, [{
        "question_id": rejected["findings"][0]["question_id"],
        "premise_resolution": [{
            "premise_key": valid_rows[0]["premise_key"],
            "assessment": valid_rows[0]["assessment"],
        }],
    }], change_reason="repair validator-path field")

    assert result["written"] is True
    canonical = json.loads(
        (tmp_path / "decisive_question_findings.json").read_text(encoding="utf-8")
    )
    assessment = canonical["findings"][0]["resolution_assessment"]
    assert assessment["premise_resolution"] == valid_rows
    assert assessment["net_support"] == "MIXED"
    assert assessment["decision_consistency"]


def test_decisive_premise_patch_rejects_unknown_key_and_field(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    rejected = _complete_findings(tmp_path, plan)
    rejected["findings"][0]["resolution_assessment"]["premise_resolution"][0][
        "assessment"
    ] = "收入变化证明竞争格局已经结构性恶化。"
    persist_decisive_question_findings(tmp_path, rejected)
    question_id = rejected["findings"][0]["question_id"]

    unknown_key = patch_decisive_question_findings(tmp_path, [{
        "question_id": question_id,
        "premise_resolution": [{"premise_key": "not_in_plan", "assessment": "x"}],
    }])
    assert "unknown_premise_key" in unknown_key["error"]
    unknown_field = patch_decisive_question_findings(tmp_path, [{
        "question_id": question_id,
        "premise_resolution": [{
            "premise_key": rejected["findings"][0]["resolution_assessment"]["premise_resolution"][0]["premise_key"],
            "evil": True,
        }],
    }])
    assert "unknown_fields:evil" in unknown_field["error"]


def test_decisive_patch_mode_rejects_unknown_question_and_field(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    rejected = _complete_findings(tmp_path, plan)
    rejected["findings"][0]["decision_update"]["changed"] = "no"
    persist_decisive_question_findings(tmp_path, rejected)
    assert patch_decisive_question_findings(
        tmp_path, [{"question_id": "DQ:unknown", "conclusion": "x"}]
    )["error"].startswith("finding_patches[0]:unknown_question_id")
    assert patch_decisive_question_findings(tmp_path, [{
        "question_id": rejected["findings"][0]["question_id"], "evil": True,
    }])["error"].startswith("finding_patches[0]:unknown_fields")


def test_resume_mode_accepts_safe_full_candidate_when_provider_resends_it(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    rejected = _complete_findings(tmp_path, plan)
    rejected["findings"][0]["decision_update"]["changed"] = "no"
    persist_decisive_question_findings(tmp_path, rejected)

    repaired = _complete_findings(tmp_path, plan)
    result = write_decisive_question_findings(
        str(tmp_path), findings=repaired["findings"],
        resume_best_rejected=True, change_reason="safe full resend",
    )
    assert result["written"] is True
    assert result["validation"]["state"] == "DECISION_READY"


def test_resume_mode_rejects_changes_to_questions_outside_current_frontier(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    rejected = _complete_findings(tmp_path, plan)
    rejected["findings"][0]["decision_update"]["changed"] = "no"
    persist_decisive_question_findings(tmp_path, rejected)

    resend = _complete_findings(tmp_path, plan)
    resend["findings"][1]["conclusion"] = "不应顺手修改已通过问题。"
    result = write_decisive_question_findings(
        str(tmp_path), findings=resend["findings"],
        resume_best_rejected=True, change_reason="out of frontier mutation",
    )
    assert "question_outside_current_validation_frontier" in result["error"]


def test_repairable_rejection_routes_directly_to_local_patch(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    rejected = _complete_findings(tmp_path, plan)
    rejected["findings"][0]["signal_results"][0]["result"] = "收入增长99%"
    persist_decisive_question_findings(tmp_path, rejected)

    resume = read_structured_ledger_contract(
        str(tmp_path), ledger="decisive"
    )["rejected_research_resume"]

    assert resume["recommended_mode"] == "local_patch_no_new_research"
    assert resume["repair_playbook"]["first_action"].startswith("submit finding_patches")
    assert "search_report" in resume["repair_playbook"]["do_not_call"]


def test_structured_contract_exposes_exact_decisive_ids_and_types(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    result = read_structured_ledger_contract(str(tmp_path), ledger="decisive")
    assert result["ok"] is True
    assert result["contract"]["selected_questions"] == plan["selected_questions"]
    assert "confidence_before:number" in result["contract"]["finding"]
    assert result["verified_observation_ids"] == [
        "OBS:annual:operations:revenue:2025:abc123"
    ]
    assert result["sequence"] == [
        "decision", "claim", "valuation", "thesis", "decisive", "insight", "judgment"
    ]


def test_plan_sensitivity_premises_receive_verified_atomic_identities(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    contract = read_structured_ledger_contract(str(tmp_path), ledger="decisive")
    premise_rows = [
        item for item in contract["verified_calculations"]
        if item.get("tool") == "decisive_plan"
    ]
    expected = sum(
        len(_premise_test_leaves(question["decision_link"]["sensitivity_basis"]))
        for question in plan["selected_questions"]
    )
    assert len(premise_rows) == expected
    assert all(str(item["calculation_id"]).startswith("CALC:") for item in premise_rows)


def test_read_tool_exposes_question_findings(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    persist_decisive_question_findings(tmp_path, _complete_findings(tmp_path, plan))
    result = read_decisive_question_plan(str(tmp_path))
    assert result["ok"] is True and result["findings_state"] == "DECISION_READY"
    assert all(item["research_finding"] for item in result["selected_questions"])


def test_revalidation_withholds_a_now_invalid_canonical_finding(tmp_path: Path) -> None:
    _fixture(tmp_path); plan = build_decisive_question_plan(tmp_path, persist=True)
    initialize_decisive_question_policy(tmp_path, run_id="run-revalidate", enforced=True)
    persist_decisive_question_findings(tmp_path, _complete_findings(tmp_path, plan))
    payload = json.loads(
        (tmp_path / "decisive_question_findings.json").read_text(encoding="utf-8")
    )
    payload["findings"][0]["conclusion"] = "这是唯一解释。"
    _write(tmp_path / "decisive_question_findings.json", payload)

    result = evaluate_output_decisive_questions(tmp_path, persist=True)

    assert result["state"] == "INVALID"
    readback = read_decisive_question_plan(str(tmp_path))
    assert readback["findings_state"] == "INVALID"
    assert all(item["research_finding"] is None for item in readback["selected_questions"])


def test_insight_question_must_bind_selected_id_and_exact_text(tmp_path: Path) -> None:
    _fixture(tmp_path); build_decisive_question_plan(tmp_path, persist=True)
    initialize_decisive_question_policy(tmp_path, run_id="run-3", enforced=True)
    result = validate_insight_ledger(
        {"decisive_question": "模型自由生成的另一个问题？", "question_basis": {"question_id": "DQ:not:selected"}},
        output_dir=tmp_path, report_text="", enforced=True,
    )
    assert "question_basis:question_not_selected:DQ:not:selected" in result["invalid_findings"]


def test_decisive_question_tools_are_auto_discoverable() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.read_tools")
    registry.auto_discover("turtle_agent.tools.write_tools")
    assert "read_decisive_question_plan" in registry.list_tools()
    assert "write_decisive_question_findings" in registry.list_tools()
    schema = next(
        item for item in registry.get_schemas()
        if item["function"]["name"] == "write_decisive_question_findings"
    )
    findings = schema["function"]["parameters"]["properties"]["findings"]
    assert findings["minItems"] == 1
    assert set(findings["items"]["required"]) == {
        "question_id", "outcome", "evidence_observation_ids", "evidence_calculation_ids", "attempted_sources",
        "signal_results", "explanation_update", "decision_update", "conclusion",
        "unresolved",
    }


def test_decisive_question_schemas_exist_and_parse() -> None:
    root = Path(__file__).parents[1]
    for name in ("decisive_question_plan.schema.json", "decisive_question_findings.schema.json"):
        payload = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        assert payload["$schema"].endswith("2020-12/schema")
