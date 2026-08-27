from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_research_execution import (
    begin_judgment_research_task,
    complete_judgment_research_task,
    preflight_judgment_tool_call,
    record_judgment_tool_call,
)
from scripts.judgment_research_resume import (
    judgment_task_iteration_budget,
    next_judgment_research_pass,
)
from scripts.judgment_research_router import persist_judgment_research_plan
from scripts.turtle_agent.agent_loop import AgentConfig, TurtleAgent
from scripts.turtle_agent.llm_client import LlmResponse, ToolCall
from scripts.turtle_agent.tool_registry import ToolRegistry


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _setup(output: Path, *, second_task: bool = False) -> None:
    chapters = output / "chapters"
    chapters.mkdir()
    for idx in range(15):
        (chapters / f"_ch{idx:02d}.md").write_text(f"## Ch{idx}\n\n基线", encoding="utf-8")
    _write(output / "insight_ledger.json", {
        "report_id": "CASE", "insights": [{"insight_id": "I001", "chapters": [0, 8, 14]}],
    })
    _write(output / "judgment_review.json", {
        "report_id": "CASE", "ceiling_verdict": "COMPETENT",
        "verdict_basis": "缺失证据可能改变价值兑现判断。",
        "distinctive_insight": {"insight_id": "I001"},
        "fragile_leaps": [{
            "claim": "外部股东能够取得留存价值",
            "needed_evidence": "董事会资本配置、关联交易、分红与回购记录",
            "decision_consequence": "改变估值和仓位",
        }],
        "missing_information": ["同业公司历史基准率与样本分布"] if second_task else [],
        "decision_dependency": {"conclusion": "证据反转时更新决策"},
    })
    assert persist_judgment_research_plan(output)["written"] is True


def _ok() -> dict:
    return {"ok": True, "value": {
        "content": "可复核内容", "text": "可复核内容", "char_count": 5,
        "total_hits": 1, "hits": [{"text": "命中"}], "results": [{"url": "https://example.test"}],
        "peer_count_total": 1, "peers": [{"code": "PEER"}],
    }}


def _finding(task_id: str, source_id: str) -> dict:
    return {
        "schema_version": "judgment-research-finding.v1", "task_id": task_id,
        "resolution": "UNRESOLVED", "prior_claim": "原主张仍需要更多证据才能确认",
        "evidence_items": [{"source_id": source_id, "source_kind": "primary_filing", "directness": "CONTEXT", "relation": "context", "fact": "公开材料未提供具有区分力的新事实", "as_of": "2026-08-02"}],
        "strongest_alternative": "公开披露可能遗漏关键的治理安排",
        "discriminating_result": "本次材料不能区分原主张和替代解释",
        "inference": "维持原置信度并且不改变当前投资动作",
        "applicability_conditions": ["仅适用于当前公开材料检索范围"],
        "confidence_update": {"before": 0.5, "after": 0.5, "basis": "没有新增区分性证据"},
        "valuation_impact": {"state": "NONE", "basis": "没有估值输入发生变化", "changes": []},
        "action_impact": {"state": "NONE", "basis": "没有动作依据发生变化", "changes": []},
        "chapter_update": {"needed": False, "chapters": [], "reason": "正文无需更新"},
    }


def test_pending_queue_blocks_assembly_and_selects_first_fresh_task(tmp_path: Path) -> None:
    _setup(tmp_path)
    blocked = preflight_judgment_tool_call(tmp_path, "assemble_report", {})
    assert blocked["allowed"] is False
    assert "fresh_context" in blocked["error"]
    context = next_judgment_research_pass(tmp_path)
    assert context and context["task_id"] == "JR001"
    assert context["resume"] is False
    assert context["remaining_tool_calls"] == 8
    assert "assemble_report" not in context["allowed_tools"]


def test_active_task_resumes_only_remaining_tools_and_preserves_budget(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {"query": "分红"}, _ok())
    context = next_judgment_research_pass(tmp_path)
    assert context and context["resume"] is True
    assert context["successful_tools"] == ["search_report"]
    assert context["remaining_required_tools"] == ["read_section"]
    assert context["remaining_tool_calls"] == 7
    assert judgment_task_iteration_budget(context, cap=14) == 13


def test_repairable_completion_context_preserves_errors_sources_and_prior_finding(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {"query": "分红"}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {"year": 2025, "section": "GOV"}, _ok())
    bad = _finding("JR001", "human-readable-source")
    bad["chapter_update"] = {"needed": True, "chapters": [0], "reason": "需要写回"}
    rejected = complete_judgment_research_task(
        tmp_path, "JR001", "NO_DECISION_CHANGE", ["human-readable-source"],
        "第一次提交使用了错误来源身份。", bad,
    )
    assert rejected["repairable_submission"] is True
    context = next_judgment_research_pass(tmp_path)
    repair = context["completion_repair"]
    assert repair["submission_attempts"] == 1
    assert any("unknown_or_unusable_source_ids" in item for item in repair["last_submission_errors"])
    assert repair["previous_finding"]["task_id"] == "JR001"
    assert [item["source_id"] for item in repair["usable_sources"]] == [
        "JR001:S01:search_report", "JR001:S02:read_section"
    ]


def test_repair_prompt_exposes_persisted_completion_diagnostics(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {"query": "分红"}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {"year": 2025, "section": "GOV"}, _ok())
    complete_judgment_research_task(
        tmp_path, "JR001", "NO_DECISION_CHANGE", ["bad-source"],
        "错误来源身份。", _finding("JR001", "bad-source"),
    )
    registry = ToolRegistry()
    for module in ("turtle_agent.tools.read_tools", "turtle_agent.tools.write_tools"):
        registry.auto_discover(module)

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(
        code="CASE", output_dir=str(tmp_path), judgment_task_id="JR001", judgment_task_resume=True,
    ))
    prompt = agent._build_judgment_task_system_prompt()
    assert "unknown_or_unusable_source_ids" in prompt
    assert "JR001:S02:read_section" in prompt
    assert "previous_finding" in prompt


def test_completed_task_is_not_replayed_after_restart(tmp_path: Path) -> None:
    _setup(tmp_path, second_task=True)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {}, _ok())
    assert complete_judgment_research_task(
        tmp_path, "JR001", "NO_DECISION_CHANGE", ["JR001:S02:read_section"], "无决策变化",
        _finding("JR001", "JR001:S02:read_section"),
    )["completed"] is True
    context = next_judgment_research_pass(tmp_path)
    assert context and context["task_id"] == "JR002"
    assert context["resume"] is False


def test_task_prompt_and_tool_schema_exclude_full_report_context(tmp_path: Path) -> None:
    _setup(tmp_path)
    registry = ToolRegistry()
    for module in (
        "turtle_agent.tools.read_tools",
        "turtle_agent.tools.write_tools",
        "turtle_agent.tools.search_tools",
    ):
        registry.auto_discover(module)

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(
        code="CASE", output_dir=str(tmp_path), judgment_task_id="JR001"
    ))
    prompt = agent._build_judgment_task_system_prompt()
    schemas = {item["function"]["name"] for item in agent._judgment_tool_schemas()}
    assert schemas == {"begin_judgment_research_task"}
    assert "判断优先宪法" in prompt
    assert "局部经济含义" in prompt
    assert "assemble_report" not in schemas
    assert "plan_judgment_research" not in schemas
    assert "完整报告蓝图" not in prompt
    assert "不要重新分析整家公司" not in prompt  # opening task, not repeated system baggage
    assert len(prompt) < 12000


def test_full_report_prompt_inherits_judgment_first_constitution(tmp_path: Path) -> None:
    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), ToolRegistry(), AgentConfig(
        code="CASE", output_dir=str(tmp_path),
    ))
    agent._context = {
        "contract": {}, "company_name": "案例公司", "template_raw": "",
    }
    prompt = agent._build_system_prompt()
    assert "判断优先宪法" in prompt
    assert "未证实的增长选择权不进基准情景" in prompt
    assert "不等于价值为零或经营失败" in prompt


def test_v12_report_prompt_does_not_reintroduce_defensive_decision_bias(tmp_path: Path) -> None:
    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), ToolRegistry(), AgentConfig(
        code="CASE", output_dir=str(tmp_path),
    ))
    agent._context = {
        "contract": {}, "company_name": "案例公司",
        "template_raw": "Part A\n定性深度分析",
    }
    prompt = agent._build_system_prompt()
    assert "默认**保守偏空**" not in prompt
    assert "折价15%后的 GG 和 DDM" not in prompt
    assert "说不清楚 → 仓位打五折" not in prompt
    assert "答案是\"不确定\" → 决策降一级" not in prompt
    assert "必须给出概率判断**（百分比）" not in prompt
    assert "Continue→仓位加满" not in prompt
    assert "Pause→仓位减半" not in prompt
    assert "对乐观与悲观解释使用相同证据标准" in prompt
    assert "缺失本身不是固定 15% 价值毁灭" in prompt
    assert "相对旧锚稳定不得写成最新一期稳定" in prompt
    assert "项目完成只结算实施里程碑" in prompt
    assert "governance_tension=high，考虑降为 Hold" not in prompt
    assert "治理评级本身不改变 Buy/Hold/Avoid" in prompt
    assert "每定性章至少嵌入 **1 张同行/行业对比表**" not in prompt
    assert "因为同行数据缺失就跳过对比（至少做国内同行" not in prompt
    assert "每 5pp 差异调整 PE 10%" not in prompt
    assert "不得写 Pxx、不得把缺失本身当负面" in prompt
    assert "没有数据时不做机械填充，也不因此停止企业判断" in prompt
    assert "已观察经济损失载体折价" in prompt
    assert "不得写成数据缺失、资料不足或信息质量折价" in prompt


def test_active_schema_hides_mutations_until_required_routes_are_attempted(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    registry = ToolRegistry()
    for module in ("turtle_agent.tools.read_tools", "turtle_agent.tools.write_tools", "turtle_agent.tools.search_tools"):
        registry.auto_discover(module)

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(
        code="CASE", output_dir=str(tmp_path), judgment_task_id="JR001", judgment_task_resume=True,
    ))
    schemas = {item["function"]["name"] for item in agent._judgment_tool_schemas()}
    assert "complete_judgment_research_task" in schemas
    assert "search_report" in schemas and "read_section" in schemas
    assert "write_chapter" not in schemas


def test_restricted_stage_maps_only_safe_read_aliases_and_rejects_other_tools(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.read_tools")

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(
        code="CASE", output_dir=str(tmp_path), judgment_task_id="JR001", judgment_task_resume=True,
    ))
    agent._last_offered_tool_names = {"search_report"}
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="alias", name="search_annual_report", arguments={"query": "分红"},
    )]))
    ledger = json.loads((tmp_path / "judgment_research_execution.json").read_text(encoding="utf-8"))
    assert ledger["tasks"]["JR001"]["tool_calls"][0]["tool"] == "search_report"

    agent._last_offered_tool_names = {"search_report"}
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="bad", name="write_decision_ledger", arguments={},
    )]))
    result = json.loads(agent._messages[-1]["content"][0]["content"])
    assert result["value"]["error"] == "tool_not_offered_in_current_stage"
    assert result["value"]["offered_tools"] == ["search_report"]


def test_llm_failure_keeps_active_checkpoint_for_next_process(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")

    class _FailingLlm:
        model = "fake"

        def chat(self, *args, **kwargs):
            raise RuntimeError("quota exhausted")

    agent = TurtleAgent(_FailingLlm(), registry, AgentConfig(
        code="CASE", output_dir=str(tmp_path), max_iterations=1,
        judgment_task_id="JR001", judgment_task_resume=True,
    ))
    agent._messages = [{"role": "system", "content": "task"}]
    agent._run_loop()
    assert agent._loop_error == "quota exhausted"
    resumed = next_judgment_research_pass(tmp_path)
    assert resumed and resumed["task_id"] == "JR001" and resumed["resume"] is True


def test_plan_tool_requests_handoff_instead_of_same_context_execution(tmp_path: Path) -> None:
    _setup(tmp_path)
    # Remove the already generated files so this call represents the normal
    # report context creating its first queue.
    (tmp_path / "judgment_research_plan.json").unlink()
    (tmp_path / "judgment_research_execution.json").unlink()
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(code="CASE", output_dir=str(tmp_path)))
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="call-1", name="plan_judgment_research",
        arguments={"output_dir": str(tmp_path), "max_tasks_per_run": 3},
    )]))
    assert agent._judgment_handoff_requested is True
    assert preflight_judgment_tool_call(tmp_path, "assemble_report", {})["allowed"] is False


def test_exhausted_source_budget_still_exposes_scoped_writeback_tools(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {}, _ok())
    for idx in range(6):
        record_judgment_tool_call(tmp_path, "search_report", {"query": str(idx)}, _ok())
    registry = ToolRegistry()
    for module in ("turtle_agent.tools.read_tools", "turtle_agent.tools.write_tools", "turtle_agent.tools.search_tools"):
        registry.auto_discover(module)

    class _Llm:
        model = "fake"

    agent = TurtleAgent(_Llm(), registry, AgentConfig(
        code="CASE", output_dir=str(tmp_path), judgment_task_id="JR001", judgment_task_resume=True,
    ))
    schemas = {item["function"]["name"] for item in agent._judgment_tool_schemas()}
    assert "complete_judgment_research_task" in schemas
    assert "write_chapter" in schemas
    assert "read_report_contract_pack" in schemas
    assert "search_report" not in schemas
    assert "read_section" not in schemas
