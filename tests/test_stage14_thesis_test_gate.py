from __future__ import annotations

import json
from pathlib import Path

from scripts.report_completion import evaluate_report_completion
from scripts.thesis_test_gate import build_thesis_test_ledger, bind_thesis_test_references, evaluate_output_thesis_test, initialize_thesis_test_policy, persist_thesis_test_ledger, promote_reviewable_thesis_test, thesis_test_fingerprint, validate_thesis_test_ledger
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
    return {"test_id": "test.core", "thesis_claim_id": "claim.core", "primary_explanation": "留存下降只是项目组合短期波动", "strongest_alternative": "竞争加剧导致客户结构性流失", "alternative_evidence_ids": ["ev.alternative"], "discriminating_observations": [{"observation_id": "obs.retention", "metric": "同口径续约率", "availability": "每半年业绩公告后", "primary_prediction": "滚动续约率恢复至90%以上", "alternative_prediction": "滚动续约率持续低于85%", "update_rule": "连续两期低于阈值则提高替代解释概率", "threshold_id": "th.reduce"}], "probability_set_id": "prob.core", "primary_scenario_id": "primary", "alternative_scenario_id": "alternative", "flip_condition": {"threshold_id": "th.exit", "basis": "审计或监管信号否决信息可靠性", "window": "一经披露立即触发"}, "valuation_after_flip": 30.0, "position_after_flip": 0.0, "action_after_flip": "exit", "decision_entry_ids": ["vfinal", "exit"], "chapters": [9, 14]}


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
        ("fj.retention", "INDUSTRY_STRUCTURE", "same_scope_retention", "AT_LEAST", 90.0, "th.reduce"),
        ("fj.owner_cash", "OWNER_CASH", "owner_cash_index", "RANGE", None, "th.reduce"),
        ("fj.value", "VALUATION", "intrinsic_value_per_share", "AT_LEAST", 45.0, "th.buy"),
    ]
    for judgment_id, materiality, metric, operator, value, signal in specs:
        prediction = {
            "metric": metric,
            "operator": operator,
            "unit": "%" if metric == "same_scope_retention" else "index" if metric == "owner_cash_index" else "RMB/share",
            "horizon": "FY2029",
            "resolution_due": "2029-12-31",
        }
        if operator == "RANGE":
            prediction.update({"range_low": 95.0, "range_high": 105.0})
        else:
            prediction["value"] = value
        judgments.append({
            "judgment_id": judgment_id,
            "statement": f"{metric}在FY2029达到冻结目标。",
            "materiality": materiality,
            "claim_id": "claim.core",
            "competitive_test_id": "test.core",
            "probability_set_id": "prob.core",
            "scenario_id": "primary",
            "evidence_ids": ["ev.primary"],
            "leading_signal_threshold_ids": [signal],
            "falsifier": "连续两期落入结构性流失阈值则该判断失败。",
            "prediction": prediction,
            "observable_outcome": {
                "measurement_basis": "公司定期报告同口径披露",
                "measurement_rule": "使用首次正式披露的FY2029数值与冻结阈值比较",
                "measurement_period": {"kind": "REPORTING_PERIOD", "start": "2029-01-01", "end": "2029-12-31"},
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
    return build_thesis_test_ledger(
        output, [_test()], thresholds, [probabilities],
        central_path=central_path, forward_judgments=judgments,
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


def test_forward_judgments_must_reach_value_and_expected_return_identities(tmp_path: Path) -> None:
    payload = _forward_payload(tmp_path, freeze=False)
    for judgment in payload["forward_judgments"]:
        judgment["decision_entry_ids"] = ["vfinal"]
    result = validate_thesis_test_ledger(
        payload, output_dir=tmp_path, report_text=_forward_report(),
        enforced=True, forward_judgment_required=True,
    )
    assert "forward_judgment_decision_link_missing:expected_return" in result["forward_judgment_incomplete_findings"]


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
    assert "discrimination_target" in threshold_properties
    assert "estimates" in probability_properties
    assert "selected_scenario_id" in params["central_path"]["properties"]
    assert "observable_outcome" in params["forward_judgments"]["items"]["properties"]


def test_old_output_without_policy_remains_skip(tmp_path: Path) -> None:
    assert evaluate_output_thesis_test(tmp_path, persist=False)["state"] == "SKIP"


def test_thesis_test_tool_is_auto_discoverable() -> None:
    registry = ToolRegistry(); registry.auto_discover("turtle_agent.tools.write_tools")
    assert "write_thesis_test_ledger" in registry.list_tools()


def test_thesis_failure_routes_relevant_chapters() -> None:
    completion = {"blocking_findings": ["Thesis test: INCOMPLETE: thesis_test_missing"]}
    assert _repair_targets_from_completion(completion) == (14, 0)
