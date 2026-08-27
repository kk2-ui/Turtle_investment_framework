from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_research_execution import (
    begin_judgment_research_task,
    complete_judgment_research_task,
    record_judgment_tool_call,
)
from scripts.judgment_research_router import persist_judgment_research_plan
from scripts.judgment_research_synthesis import (
    build_judgment_research_synthesis,
    evaluate_judgment_research_synthesis,
    finalize_judgment_research_synthesis,
    validate_judgment_research_finding,
)
from scripts.turtle_agent.agent_loop import AgentConfig, TurtleAgent
from scripts.turtle_agent.llm_client import LlmResponse, ToolCall
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.write_tools import finalize_judgment_research_review


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _setup(output: Path) -> dict:
    chapters = output / "chapters"
    chapters.mkdir()
    for idx in range(15):
        (chapters / f"_ch{idx:02d}.md").write_text(f"## Ch{idx}\n\n基线", encoding="utf-8")
    _write(output / "insight_ledger.json", {
        "report_id": "CASE", "insights": [{"insight_id": "I001", "chapters": [0, 8, 14]}],
    })
    _write(output / "judgment_review.json", {
        "report_id": "CASE", "ceiling_verdict": "COMPETENT",
        "verdict_basis": "治理证据仍可能改变价值兑现判断和最终仓位。",
        "distinctive_insight": {"insight_id": "I001"},
        "fragile_leaps": [{
            "claim": "外部股东可以取得留存价值", "why_fragile": "缺乏治理证据",
            "needed_evidence": "董事会资本配置、关联交易、分红与回购记录",
            "decision_consequence": "证据反转会改变估值和仓位",
        }],
        "missing_information": [],
        "decision_dependency": {"conclusion": "证据反转时必须更新估值和仓位。"},
    })
    result = persist_judgment_research_plan(output)
    return result["plan"]


def _finding(source_id: str = "JR001:S02:read_section", *, relation: str = "supports") -> dict:
    return {
        "schema_version": "judgment-research-finding.v1", "task_id": "JR001",
        "resolution": "SUPPORTED", "prior_claim": "外部股东可以取得留存价值",
        "evidence_items": [{
            "source_id": source_id, "source_kind": "primary_filing", "directness": "DIRECT", "relation": relation,
            "fact": "董事会连续三年维持明确分红并披露资本配置原则", "as_of": "2026-08-02",
        }],
        "strongest_alternative": "控股股东仍可能通过关联安排截留价值",
        "discriminating_result": "连续分红支持价值兑现但不能排除关联交易风险",
        "inference": "治理证据提高价值兑现可信度但不足以改变当前估值参数",
        "applicability_conditions": ["分红政策继续执行且关联交易没有恶化"],
        "confidence_update": {"before": 0.45, "after": 0.62, "basis": "连续三年原始披露提供直接支持"},
        "valuation_impact": {"state": "NONE", "basis": "尚不足以调整兑现折扣参数", "changes": []},
        "action_impact": {"state": "NONE", "basis": "仓位动作仍等待关联交易反证", "changes": []},
        "chapter_update": {"needed": False, "chapters": [], "reason": "新增事实先进入结构化证据链"},
    }


def _execute_success(output: Path) -> dict:
    begin_judgment_research_task(output, "JR001")
    record_judgment_tool_call(output, "search_report", {}, {"ok": True, "value": {"total_hits": 1, "hits": [1]}})
    record_judgment_tool_call(output, "read_section", {}, {"ok": True, "value": {"text": "治理正文"}})
    return complete_judgment_research_task(
        output, "JR001", "EVIDENCE_FOUND", ["JR001:S02:read_section"],
        "连续分红提高价值兑现可信度，但不改变当前决策。", _finding(),
    )


def test_finding_rejects_undeclared_source_and_false_decision_transmission(tmp_path: Path) -> None:
    plan = _setup(tmp_path)
    task = plan["tasks"][0]
    finding = _finding("other:source")
    result = validate_judgment_research_finding(
        finding, task=task, outcome="EVIDENCE_FOUND", source_ids=["annual:GOV"]
    )
    assert "evidence_items[0]:undeclared_source_id:other:source" in result["invalid_findings"]
    finding = _finding()
    finding["valuation_impact"] = {
        "state": "CHANGED", "basis": "兑现折扣已经变化",
        "changes": [{"parameter": "lambda", "before": 0.5, "after": 0.7}],
    }
    mismatch = validate_judgment_research_finding(
        finding, task=task, outcome="NO_DECISION_CHANGE", source_ids=["annual:GOV"]
    )
    assert "no_change_outcome_with_changed_impact" in mismatch["invalid_findings"]


def test_completed_task_persists_valid_finding_and_requires_independent_review(tmp_path: Path) -> None:
    _setup(tmp_path)
    result = _execute_success(tmp_path)
    assert result["completed"] is True
    assert result["synthesis_state"] == "AWAITING_INDEPENDENT_REVIEW"
    execution = json.loads((tmp_path / "judgment_research_execution.json").read_text(encoding="utf-8"))
    assert execution["tasks"]["JR001"]["finding_validation"]["state"] == "VALID"
    synthesis = build_judgment_research_synthesis(tmp_path)
    assert synthesis["task_findings"][0]["resolution"] == "SUPPORTED"
    assert synthesis["decision_changed_task_ids"] == []


def test_independent_review_must_cover_all_tasks_and_have_reviewed_ledger(tmp_path: Path) -> None:
    _setup(tmp_path)
    _execute_success(tmp_path)
    missing = finalize_judgment_research_synthesis(
        tmp_path, integrated_task_ids=[],
        verdict_change={"before": "COMPETENT", "after": "COMPETENT", "reason": "新证据有限，判断保持不变"},
        resolved_gaps=[], remaining_gaps=["关联交易仍未解决"],
        decision_conclusion="新证据不足以改变当前估值和仓位动作。",
    )
    assert missing["finalized"] is False
    assert "independent_review_did_not_cover_all_completed_tasks" in missing["errors"]
    review = json.loads((tmp_path / "judgment_review.json").read_text(encoding="utf-8"))
    review["missing_information"] = ["关联交易仍未解决"]
    _write(tmp_path / "judgment_review.json", review)
    _write(tmp_path / "judgment_review_validation.json", {"state": "REVIEWED"})
    done = finalize_judgment_research_synthesis(
        tmp_path, integrated_task_ids=["JR001"],
        verdict_change={"before": "COMPETENT", "after": "COMPETENT", "reason": "治理支持增强但关键反证仍未消除"},
        resolved_gaps=["连续分红记录"], remaining_gaps=["关联交易仍未解决"],
        decision_conclusion="研究提高价值兑现置信度，但不足以改变估值参数和仓位。",
    )
    assert done["finalized"] is True
    assert json.loads((tmp_path / "judgment_research_synthesis.json").read_text(encoding="utf-8"))["state"] == "REVIEWED"


def test_synthesis_agent_has_only_review_and_finalize_tools(tmp_path: Path) -> None:
    _setup(tmp_path)
    _execute_success(tmp_path)
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(
        code="CASE", output_dir=str(tmp_path), judgment_synthesis=True,
    ))
    schemas = {item["function"]["name"] for item in agent._judgment_synthesis_tool_schemas()}
    assert schemas == {"finalize_judgment_research_review"}
    prompt = agent._build_judgment_synthesis_system_prompt()
    assert "不能搜索、补证据或改报告" in prompt
    assert "判断优先宪法" in prompt
    assert "复核后的最佳当前综合" in prompt
    assert "未披露与非决定性 proxy 不是经营冲突或负面证据" in prompt
    assert "融资改善不自动降低客户、品牌、产品生命周期、库存吸收或资本回报风险" in prompt
    assert "概率和置信更新必须保持同一命题与风险轴" in prompt
    assert "assemble_report" not in schemas
    assert len(prompt) < 30000


def test_synthesis_tools_are_auto_discoverable(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")
    assert "finalize_judgment_research_synthesis" in registry.list_tools()
    assert "finalize_judgment_research_review" in registry.list_tools()


def test_atomic_review_copies_remaining_gaps_before_finalize(tmp_path: Path, monkeypatch) -> None:
    _setup(tmp_path)
    _execute_success(tmp_path)
    captured: dict = {}
    import scripts.judgment_review as judgment_review_module
    import scripts.judgment_research_synthesis as synthesis_module

    def fake_build(output_dir, ceiling, basis, distinctive, conventional, fragile,
                   competitive, missing, dependency, dimensions, limits):
        captured["missing"] = list(missing)
        return {"missing_information": list(missing)}

    def fake_persist(output_dir, payload):
        captured["persisted"] = payload
        return {"written": True}

    def fake_finalize(output_dir, **kwargs):
        captured["finalize"] = kwargs
        return {"finalized": True, "state": "REVIEWED"}

    monkeypatch.setattr(judgment_review_module, "build_judgment_review", fake_build)
    monkeypatch.setattr(judgment_review_module, "persist_judgment_review", fake_persist)
    monkeypatch.setattr(synthesis_module, "finalize_judgment_research_synthesis", fake_finalize)
    result = finalize_judgment_research_review(
        str(tmp_path),
        judgment_review={"missing_information": ["旧缺口"]},
        integrated_task_ids=["JR001"],
        verdict_change={"before": "COMPETENT", "after": "COMPETENT", "reason": "不变"},
        resolved_gaps=[], remaining_gaps=["JR001: 新缺口"],
        decision_conclusion="结论维持不变且保留未解决问题。",
    )
    assert result["finalized"] is True and result["atomic"] is True
    assert captured["missing"] == ["旧缺口", "JR001: 新缺口"]


def test_report_assembly_is_blocked_until_independent_synthesis_finishes(tmp_path: Path) -> None:
    _setup(tmp_path)
    _execute_success(tmp_path)
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(code="CASE", output_dir=str(tmp_path)))
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="assemble", name="assemble_report", arguments={"output_dir": str(tmp_path)},
    )]))
    payload = json.loads(agent._messages[-1]["content"][0]["content"])
    assert payload["value"]["error"] == "independent_judgment_synthesis_required_before_assembly"
    assert agent._assembled_this_pass is False


def test_reviewed_synthesis_fingerprint_detects_posthoc_tampering(tmp_path: Path) -> None:
    _setup(tmp_path)
    _execute_success(tmp_path)
    review = json.loads((tmp_path / "judgment_review.json").read_text(encoding="utf-8"))
    review["missing_information"] = ["关联交易仍未解决"]
    _write(tmp_path / "judgment_review.json", review)
    _write(tmp_path / "judgment_review_validation.json", {"state": "REVIEWED"})
    assert finalize_judgment_research_synthesis(
        tmp_path, integrated_task_ids=["JR001"],
        verdict_change={"before": "COMPETENT", "after": "COMPETENT", "reason": "关键反证仍未消除"},
        resolved_gaps=["连续分红记录"], remaining_gaps=["关联交易仍未解决"],
        decision_conclusion="研究提高置信度，但不足以改变估值和仓位动作。",
    )["finalized"] is True
    payload = json.loads((tmp_path / "judgment_research_synthesis.json").read_text(encoding="utf-8"))
    payload["independent_review"]["decision_conclusion"] = "事后篡改后的结论文本足够长"
    _write(tmp_path / "judgment_research_synthesis.json", payload)
    evaluated = evaluate_judgment_research_synthesis(tmp_path)
    assert evaluated["state"] == "INVALID"
    assert "fingerprint_mismatch" in evaluated["findings"]
