from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.insight_ledger import (
    build_insight_ledger,
    bind_insight_references,
    initialize_insight_policy,
    persist_insight_ledger,
    promote_reviewable_insight,
    render_investment_memo,
    validate_rendered_memo,
    validate_insight_ledger,
    evaluate_output_insight,
    build_insight_question_identity_migration,
    promote_insight_question_identity_migration,
    insight_fingerprint,
)
from scripts.insight_research import build_insight_research_brief
from scripts.turtle_agent.tool_registry import ToolRegistry


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _dependencies(output: Path) -> None:
    _write_json(output / "analysis_contract.json", {"ts_code": "000001.SZ"})
    _write_json(output / "claim_evidence.json", {"claims": [{"claim_id": "claim.core", "raw_facts": [{"evidence_id": "ev.sales"}, {"evidence_id": "ev.alt"}]}]})
    _write_json(output / "decision_ledger.json", {"entries": [{"entry_id": "decision.value", "status": "active"}]})
    _write_json(output / "valuation_model.json", {"models": [{"model_id": "reverse.dcf"}]})


def _payload(output: Path) -> dict:
    return build_insight_ledger(
        output, "mature_cash_return", "收入收缩究竟是周期扰动还是会永久削弱可分配现金？",
        {"anomaly": "收入下降而毛利率维持高位", "evidence_ids": ["ev.sales"], "why_it_changes_the_decision": "决定利润正常化与分红覆盖"},
        [{
            "insight_id": "insight.cash_decay", "title": "高毛利掩盖现金引擎收缩", "claim_id": "claim.core",
            "evidence_ids": ["ev.sales", "ev.alt"], "anomaly": "公司内销收入下降但格力品牌毛利率仍高",
            "mechanism": ["内销量下滑压低收入", "固定费用与渠道返利令可分配现金下降"],
            "strongest_alternative": "需求只是短周期回落", "discriminating_observation": "未来两个旺季内销数量与渠道库存是否同步修复",
            "valuation_impact": "基准情景下调正常化现金流", "action_impact": "未确认修复前只观察",
            "falsification": "连续两个旺季量价与现金转换同时恢复则撤销该判断",
            "company_specific_terms": ["内销", "格力品牌"], "decision_entry_ids": ["decision.value"], "chapters": [0, 5, 14],
        }],
        {"as_of": "2026-08-02", "current_price": 40, "method": "reverse_dcf", "implied_operating_path": "市场价格要求正常化现金流五年不下降", "assumptions": ["零净债务", "10%股权成本"], "valuation_model_ids": ["reverse.dcf"], "conclusion": "市场并未计入持续衰退", "flip_condition": "隐含现金流允许连续三年下降"},
        {"latent_value": "正常化现金流与可分配现金", "controller": "董事会及控股股东", "access_mechanism": "常规分红和注销式回购", "catalyst_required": False, "catalysts": ["分红政策兑现"], "no_catalyst_value": "只按现有分红资本化", "failure_mode": "资金转入低回报多元化", "decision_entry_ids": ["decision.value"]},
        {"strongest_case_against": "渠道变化是永久性的", "why_it_may_be_right": "替代渠道增长快于传统渠道", "evidence_ids": ["ev.alt"], "unresolved": "新渠道份额口径不可比", "decision_if_true": "下调估值并避免买入"},
        {"executive_decision": "当前不买入，等待现金引擎是否企稳。", "valuation_action": "仅在逆向估值允许结构性下滑且仍满足回报要求时建仓。", "monitoring": ["内销量", "渠道库存", "经营现金流"]},
        change_reason="initial case-calibrated analysis", freeze=True,
    )


def _cjo_dependencies(output: Path) -> None:
    _write_json(output / "analysis_contract.json", {
        "ts_code": "000001.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
    })
    _write_json(output / "claim_evidence.json", {
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "claims": [{"claim_id": "claim.core", "raw_facts": [
            {"evidence_id": "ev.sales"}, {"evidence_id": "ev.alt"},
        ]}],
    })
    _write_json(output / "thesis_test.json", {
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "forward_judgments": [{"judgment_id": "fj.owner_cash"}],
    })


def _cjo_payload(output: Path, *, freeze: bool = True) -> dict:
    return build_insight_ledger(
        output, "operating_transition", "收入收缩是短期扰动，还是会通过渠道返利永久压低经营现金？",
        {
            "anomaly": "收入下降但毛利率保持高位",
            "evidence_ids": ["ev.sales"],
            "why_it_changes_the_judgment": "它决定高毛利是否仍能转化为可持续的经营现金。",
        },
        [{
            "insight_id": "insight.cash_decay", "title": "高毛利可能掩盖现金引擎收缩",
            "claim_id": "claim.core", "evidence_ids": ["ev.sales", "ev.alt"],
            "anomaly": "内销收入下降但品牌毛利率仍高",
            "mechanism": ["内销量下滑压低收入", "固定费用与渠道返利压低经营现金转化"],
            "strongest_alternative": "需求只是短周期回落",
            "discriminating_observation": "未来两个旺季销量、渠道库存和现金转换是否同步修复",
            "operating_impact": "若返利与固定费用没有回落，正常化经营利润和 owner cash 将低于历史水平。",
            "monitoring_or_forward_judgment": "用销量、返利与经营现金转化跟踪并结算 fj.owner_cash。",
            "forward_judgment_ids": ["fj.owner_cash"],
            "falsification": "连续两个旺季量价和现金转换同时恢复则撤销该判断",
            "company_specific_terms": ["内销", "品牌"], "chapters": [0, 5, 14],
        }],
        {}, {},
        {
            "strongest_case_against": "渠道变化没有改变现金引擎，只是淡季去库存。",
            "why_it_may_be_right": "高毛利率和经营现金可能在旺季恢复。",
            "evidence_ids": ["ev.alt"], "unresolved": "渠道库存与返利缺少同口径公开序列。",
            "judgment_if_true": "应把当前收缩重判为短周期扰动，并等待下一季经营数据结算。",
        },
        {
            "executive_judgment": "当前证据支持现金引擎收缩假说，但尚不能排除短周期扰动。",
            "monitoring": ["内销量", "渠道库存", "经营现金流"],
        },
        change_reason="freeze operating mechanism and its forward settlement",
        freeze=freeze, analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )


def test_case_router_is_question_led_and_detects_mature_cash_return(tmp_path: Path) -> None:
    _write_json(tmp_path / "compute_bundle.json", {"dividend_yield_pct": 5.2, "revenue_growth": -4.0})
    _write_json(tmp_path / "analysis_contract.json", {"company_name": "成熟消费公司"})
    brief = build_insight_research_brief(tmp_path, persist=False)
    assert brief["primary_archetype"] in {"mature_cash_return", "operating_transition"}
    assert brief["decisive_question"].endswith("？")
    assert brief["required_moves"] and brief["forbidden_shortcuts"]
    assert brief["case_provenance"]["kind"] == "SYNTHESIS_PATTERN"


def test_case_router_distinguishes_named_book_case_from_synthesis_pattern(tmp_path: Path) -> None:
    _write_json(tmp_path / "analysis_contract.json", {"company_name": "芯片公司"})
    brief = build_insight_research_brief(tmp_path, persist=False)

    assert brief["primary_archetype"] == "technology_transition"
    assert brief["case_provenance"] == {
        "kind": "NAMED_BOOK_CASE",
        "source_label": "Intel",
        "scope": "ROUTING_ONLY_NOT_COMPANY_EPISODE",
    }


def test_complete_insight_ledger_is_frozen_and_cross_ledger_bound(tmp_path: Path) -> None:
    _dependencies(tmp_path); initialize_insight_policy(tmp_path, run_id="run-1", enforced=True)
    payload = _payload(tmp_path)
    report = "## Ch0 投资要点\n[insight: insight.cash_decay]\n## Ch14 综合决策\n[insight: insight.cash_decay]"
    result = persist_insight_ledger(tmp_path, payload, report_text=report)
    assert result["state"] == "DECISION_READY"
    assert (tmp_path / "insight_validation.json").exists()


def test_company_judgment_insight_freezes_operating_transmission_without_investment_fields(tmp_path: Path) -> None:
    _cjo_dependencies(tmp_path)
    initialize_insight_policy(
        tmp_path, run_id="cjo", enforced=True,
        analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )
    payload = _cjo_payload(tmp_path)
    report = "## Ch0 公司判断\n[insight: insight.cash_decay]\n## Ch14 综合判断\n[insight: insight.cash_decay]"

    result = validate_insight_ledger(payload, output_dir=tmp_path, report_text=report, enforced=True)
    memo = render_investment_memo(payload, "测试公司", "000001.SZ", "technical.md")

    assert result["state"] == "DECISION_READY"
    assert result["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert "市场隐含预期" not in memo and "估值与动作" not in memo
    assert "fj.owner_cash" in memo


def test_company_judgment_insight_rejects_valuation_placeholder(tmp_path: Path) -> None:
    _cjo_dependencies(tmp_path)
    payload = _cjo_payload(tmp_path, freeze=False)
    payload["insights"][0]["valuation_impact"] = "留空的估值占位"

    result = validate_insight_ledger(payload, output_dir=tmp_path, report_text="[insight: insight.cash_decay]")

    assert result["state"] == "INVALID"
    assert "insight.cash_decay:company_judgment_cannot_carry_valuation_impact" in result["invalid_findings"]


def test_enforced_missing_insight_ledger_is_incomplete_not_invalid(tmp_path: Path) -> None:
    initialize_insight_policy(tmp_path, run_id="run-missing", enforced=True)
    result = evaluate_output_insight(tmp_path)
    assert result["state"] == "INCOMPLETE"
    assert result["incomplete_findings"] == ["insight_ledger_missing"]


def test_legacy_frozen_insight_gets_candidate_first_question_identity_migration(tmp_path: Path) -> None:
    _dependencies(tmp_path); initialize_insight_policy(tmp_path, run_id="run-migrate", enforced=True)
    payload = _payload(tmp_path)
    payload["decisive_question"] = "账面净现金远超市值时，外部股东能通过什么路径取得留存价值？"
    payload["freeze"]["fingerprint"] = insight_fingerprint(payload)
    _write_json(tmp_path / "insight_ledger.json", payload)
    question_id = "DQ:cash_value_realization:test"
    _write_json(tmp_path / "decisive_question_plan.json", {
        "input_fingerprint": "a" * 64,
        "selected_questions": [{
            "question_id": question_id, "topic_family": "cash_value_realization",
            "question": "样本公司净现金相当于市值时，有多少能分配并兑现给外部股东？",
        }],
    })
    _write_json(tmp_path / "decisive_question_policy.json", {"enforced": True})
    chapters = tmp_path / "chapters"; chapters.mkdir()
    (chapters / "_ch00.md").write_text("[insight: insight.cash_decay]", encoding="utf-8")
    migration = build_insight_question_identity_migration(tmp_path, persist=True)
    assert migration["status"] == "READY_TO_PROMOTE"
    assert json.loads((tmp_path / "insight_ledger.json").read_text())["decisive_question"].startswith("账面")
    assert promote_insight_question_identity_migration(tmp_path)["error"] == "decisive_questions_not_ready"

    _write_json(tmp_path / "decisive_question_validation.json", {"state": "DECISION_READY"})
    promoted = promote_insight_question_identity_migration(tmp_path)
    assert promoted["promoted"] is True
    canonical = json.loads((tmp_path / "insight_ledger.json").read_text())
    assert canonical["question_basis"]["question_id"] == question_id
    recorded = json.loads(
        (tmp_path / "insight_question_identity_migration.json").read_text()
    )
    assert recorded["status"] == "PROMOTED"
    assert recorded["canonical_unchanged"] is False
    assert recorded["canonical_fingerprint"] == insight_fingerprint(canonical)
    repeated = promote_insight_question_identity_migration(tmp_path)
    assert repeated["promoted"] is False
    assert repeated["already_promoted"] is True


def test_insight_gate_rejects_multiple_only_reverse_valuation_and_price_stop(tmp_path: Path) -> None:
    _dependencies(tmp_path); payload = _payload(tmp_path)
    payload["reverse_expectations"]["method"] = "low_pe"
    payload["memo"]["monitoring"] = "股价跌破30元立即清仓"
    payload["freeze"]["fingerprint"] = "broken"
    result = validate_insight_ledger(payload, output_dir=tmp_path, report_text="[insight: insight.cash_decay]", enforced=True)
    assert "reverse_expectations:multiple_not_reverse_model" in result["invalid_findings"]
    assert "price_only_stop_rule" in result["invalid_findings"]


def test_invalid_frozen_insight_is_rejected_without_poisoning_output(tmp_path: Path) -> None:
    _dependencies(tmp_path); initialize_insight_policy(tmp_path, run_id="run-invalid", enforced=True)
    invalid = _payload(tmp_path); invalid["archetype"] = ""
    invalid["freeze"]["fingerprint"] = "bad"
    result = persist_insight_ledger(tmp_path, invalid, report_text="[insight: insight.cash_decay]")
    assert result["written"] is False
    assert result["validation"]["state"] == "INVALID"
    assert not (tmp_path / "insight_ledger.json").exists()


def test_valid_insight_is_bound_then_frozen_without_llm_chapter_rewrite(tmp_path: Path) -> None:
    _dependencies(tmp_path); initialize_insight_policy(tmp_path, run_id="run-bind", enforced=True)
    payload = _payload(tmp_path)
    payload["lifecycle"] = "reviewable"
    payload["freeze"] = {"frozen": False, "fingerprint": "", "frozen_at": None}
    chapters = tmp_path / "chapters"; chapters.mkdir()
    for idx in (0, 5, 14):
        (chapters / f"_ch{idx:02d}.md").write_text(f"## Ch{idx} 正文\n原有分析", encoding="utf-8")
    report = "\n".join(path.read_text(encoding="utf-8") for path in sorted(chapters.glob("_ch*.md")))
    first = persist_insight_ledger(tmp_path, payload, report_text=report)
    assert first["written"] is True and first["state"] == "INCOMPLETE"
    assert bind_insight_references(tmp_path, payload)["anchors_inserted"] == 3
    rebound = "\n".join(path.read_text(encoding="utf-8") for path in sorted(chapters.glob("_ch*.md")))
    promoted = promote_reviewable_insight(tmp_path, report_text=rebound)
    assert promoted["promoted"] is True
    assert evaluate_output_insight(tmp_path, report_text=rebound, persist=False)["state"] == "DECISION_READY"


def test_renderer_creates_compact_decision_layer_with_technical_link(tmp_path: Path) -> None:
    _dependencies(tmp_path); payload = _payload(tmp_path)
    memo = render_investment_memo(payload, "测试公司", "000001.SZ", "technical.md")
    assert "首要决定性问题" in memo and "市场隐含预期" in memo and "最强反方" in memo
    assert "[technical.md](technical.md)" in memo
    assert "## 监控清单" in memo and "- 内销量" in memo
    assert "ev.sales" in memo and "decision.value" in memo and "reverse.dcf" in memo
    assert "。。" not in memo and "。；" not in memo
    assert validate_rendered_memo(payload, memo, "technical.md")["status"] == "PASS"
    assert len(memo) < 10000


def test_memo_preservation_detects_dropped_decision_content(tmp_path: Path) -> None:
    _dependencies(tmp_path); payload = _payload(tmp_path)
    memo = render_investment_memo(payload, "测试公司", "000001.SZ", "technical.md")
    damaged = memo.replace("当前不买入，等待现金引擎是否企稳。", "")
    result = validate_rendered_memo(payload, damaged, "technical.md")
    assert result["status"] == "FAIL"
    assert "memo.executive_decision" in result["missing_fields"]


def test_insight_tool_is_auto_discoverable() -> None:
    registry = ToolRegistry(); registry.auto_discover("turtle_agent.tools.write_tools")
    assert "write_insight_ledger" in registry.list_tools()


def test_unified_assembly_publishes_memo_and_separate_technical_report(tmp_path: Path, monkeypatch) -> None:
    import scripts.report_completion as completion_module
    import scripts.research_calibration as calibration_module
    import scripts.turtle_agent.tools.write_tools as write_tools

    _dependencies(tmp_path)
    for idx in range(15):
        (tmp_path / f"_ch{idx:02d}.md").write_text(f"## Ch{idx} 技术底稿\n\n章节证据 [source: source{idx}.json]", encoding="utf-8")
    initialize_insight_policy(tmp_path, run_id="run-dual", enforced=True)
    _write_json(tmp_path / "insight_ledger.json", _payload(tmp_path))
    fake_completion = SimpleNamespace(status="COMPLETE", to_dict=lambda: {"status": "COMPLETE", "blocking_findings": [], "warning_findings": [], "validators": {}})
    monkeypatch.setattr(completion_module, "evaluate_report_completion", lambda *a, **k: fake_completion)
    monkeypatch.setattr(write_tools, "_run_quality_checks", lambda *a, **k: {"passed": True, "issues": [], "warnings": []})
    monkeypatch.setattr(write_tools, "_render_report_html", lambda *a, **k: None)
    monkeypatch.setattr(calibration_module, "create_publication_snapshot", lambda *a, **k: {"written": True})
    result = write_tools.assemble_report(str(tmp_path), "测试公司", "000001.SZ")
    memo = Path(result["path"]).read_text(encoding="utf-8")
    technical = Path(result["technical_report_path"]).read_text(encoding="utf-8")
    assert result["published"] is True
    assert result["memo_preservation"]["status"] == "PASS"
    assert (tmp_path / "memo_preservation_report.json").exists()
    assert "首要决定性问题" in memo and "## Ch0 技术底稿" not in memo
    assert "## Ch0 技术底稿" in technical and "## Ch14 技术底稿" in technical


def test_validation_only_materializes_matching_memo_and_technical_drafts(
    tmp_path: Path, monkeypatch,
) -> None:
    import scripts.report_completion as completion_module
    import scripts.research_calibration as calibration_module
    import scripts.turtle_agent.tools.write_tools as write_tools

    _dependencies(tmp_path)
    for idx in range(15):
        (tmp_path / f"_ch{idx:02d}.md").write_text(
            f"## Ch{idx} 技术底稿\n\n章节证据 [source: source{idx}.json]",
            encoding="utf-8",
        )
    initialize_insight_policy(tmp_path, run_id="run-draft-dual", enforced=True)
    _write_json(tmp_path / "insight_ledger.json", _payload(tmp_path))
    fake_completion = SimpleNamespace(
        status="COMPLETE",
        to_dict=lambda: {
            "status": "COMPLETE", "blocking_findings": [],
            "warning_findings": [], "validators": {},
        },
    )
    monkeypatch.setattr(completion_module, "evaluate_report_completion", lambda *a, **k: fake_completion)
    monkeypatch.setattr(write_tools, "_run_quality_checks", lambda *a, **k: {"passed": True, "issues": [], "warnings": []})
    monkeypatch.setattr(calibration_module, "create_publication_snapshot", lambda *a, **k: {"written": True})

    result = write_tools.assemble_report(
        str(tmp_path), "测试公司", "000001.SZ", validation_only=True,
    )
    memo_path = Path(result["path"])
    technical_path = Path(result["technical_report_path"])
    assert result["published"] is False and result["validated"] is True
    assert memo_path.parent.name == "drafts"
    assert technical_path.parent == memo_path.parent
    assert technical_path.name.endswith("_technical_draft.md")
    assert f"]({technical_path.name})" in memo_path.read_text(encoding="utf-8")
    assert "## Ch14 技术底稿" in technical_path.read_text(encoding="utf-8")


def test_assembly_recovers_company_name_from_report_context(tmp_path: Path, monkeypatch) -> None:
    import scripts.report_completion as completion_module
    import scripts.research_calibration as calibration_module
    import scripts.turtle_agent.tools.write_tools as write_tools

    _dependencies(tmp_path)
    _write_json(tmp_path / "report_context.json", {"meta": {"issuer": "上下文公司"}})
    for idx in range(15):
        (tmp_path / f"_ch{idx:02d}.md").write_text(
            f"## Ch{idx} 技术底稿\n\n章节证据 [source: source{idx}.json]",
            encoding="utf-8",
        )
    initialize_insight_policy(tmp_path, run_id="run-company-name", enforced=True)
    _write_json(tmp_path / "insight_ledger.json", _payload(tmp_path))
    fake_completion = SimpleNamespace(
        status="COMPLETE",
        to_dict=lambda: {
            "status": "COMPLETE", "blocking_findings": [],
            "warning_findings": [], "validators": {},
        },
    )
    monkeypatch.setattr(completion_module, "evaluate_report_completion", lambda *a, **k: fake_completion)
    monkeypatch.setattr(write_tools, "_run_quality_checks", lambda *a, **k: {"passed": True, "issues": [], "warnings": []})
    monkeypatch.setattr(calibration_module, "create_publication_snapshot", lambda *a, **k: {"written": True})

    result = write_tools.assemble_report(str(tmp_path), "", "000001.SZ", validation_only=True)
    assert Path(result["path"]).read_text(encoding="utf-8").startswith("# 上下文公司 (000001.SZ) 投资备忘录")
    assert Path(result["technical_report_path"]).read_text(encoding="utf-8").startswith(
        "# 上下文公司 (000001.SZ) 龟龟策略分析报告"
    )
