from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_research_execution import (
    begin_judgment_research_task,
    complete_judgment_research_task,
    evaluate_judgment_research_execution,
    preflight_judgment_tool_call,
    record_judgment_tool_call,
    restart_judgment_research_execution,
    retry_violated_judgment_research_task,
)
from scripts.judgment_research_router import persist_judgment_research_plan
from scripts.turtle_agent.tool_registry import ToolRegistry


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _setup(output: Path, *, missing: list[str] | None = None) -> None:
    chapters = output / "chapters"
    chapters.mkdir()
    for idx in range(15):
        (chapters / f"_ch{idx:02d}.md").write_text(f"## Ch{idx}\n\n基线内容", encoding="utf-8")
    _write(output / "insight_ledger.json", {
        "report_id": "CASE", "insights": [{"insight_id": "I001", "chapters": [0, 8, 14]}],
    })
    fragile = [{
        "claim": "外部股东能够取得留存价值",
        "why_fragile": "现有材料不能证明留存价值可以由外部股东取得",
        "needed_evidence": "董事会资本配置、关联交易、分红与回购记录",
        "decision_consequence": "证据会改变资产价值和仓位",
    }]
    fragile.extend({
        "claim": f"材料缺口会改变当前判断：{text}",
        "why_fragile": "当前证据不足以区分该主张和最强替代解释",
        "needed_evidence": text,
        "decision_consequence": "新证据会改变公司判断、估值方向或当前动作",
    } for text in (missing or []))
    _write(output / "judgment_review.json", {
        "report_id": "CASE", "ceiling_verdict": "COMPETENT",
        "verdict_basis": "治理证据仍可能改变价值兑现判断和最终仓位。",
        "distinctive_insight": {"insight_id": "I001"},
        "fragile_leaps": fragile,
        "missing_information": missing or [],
        "decision_dependency": {"conclusion": "证据反转时必须更新估值和仓位。"},
    })
    result = persist_judgment_research_plan(output, max_tasks_per_run=3)
    assert result["written"] is True


def _ok(value: object = None) -> dict:
    return {"ok": True, "value": value if value is not None else {
        "content": "可验证正文", "text": "可验证正文", "char_count": 6,
        "total_hits": 1, "hits": [{"text": "命中"}], "results": [{"url": "https://example.test"}],
        "peer_count_total": 1, "peers": [{"code": "PEER"}], "data": [{"value": 1}],
    }}


def _finding(task_id: str, source_id: str = "annual") -> dict:
    return {
        "schema_version": "judgment-research-finding.v1", "task_id": task_id,
        "resolution": "UNRESOLVED", "prior_claim": "外部股东能够取得留存价值",
        "evidence_items": [{"source_id": source_id, "source_kind": "primary_filing", "directness": "CONTEXT", "relation": "context", "fact": "公开材料没有提供具有区分力的新事实", "as_of": "2026-08-02"}],
        "strongest_alternative": "现有公开信息可能遗漏关键治理安排",
        "discriminating_result": "本次材料无法区分原主张与替代解释",
        "inference": "维持原置信度且不改变估值或投资动作",
        "applicability_conditions": ["仅适用于当前已检索的公开材料范围"],
        "confidence_update": {"before": 0.5, "after": 0.5, "basis": "没有新增区分性证据"},
        "valuation_impact": {"state": "NONE", "basis": "没有可校准的估值输入变化", "changes": []},
        "action_impact": {"state": "NONE", "basis": "没有足以改变仓位动作的新证据", "changes": []},
        "uncertainty_closure": {
            "affected_axis": "OWNER_CASH",
            "current_position": {
                "state": "EXCLUDE_FROM_BASE_CASE",
                "claim_ref": "外部股东能够取得留存价值",
                "basis": "现有公开材料没有责任匹配的上游分配与关联现金流",
            },
            "base_case_treatment": {
                "state": "EXCLUDE",
                "economic_consequence": "CASH_ACCESS_DISCOUNT_RETAINED",
            },
            "next_observation": {
                "metric_or_event": "下一份分红决议与责任匹配的关联交易现金流",
                "supports_current": {"kind": "EVENT", "operator": "DOES_NOT_OCCUR", "event_definition": "可持续上游分配且无材料关联现金流出"},
                "reverses_current": {"kind": "EVENT", "operator": "OCCURS", "event_definition": "可持续上游分配且无材料关联现金流出"},
            },
        },
        "chapter_update": {"needed": False, "chapters": [], "reason": "原正文无需变化"},
    }


def _unavailable_finding(task_id: str) -> dict:
    payload = _finding(task_id)
    payload.update({
        "resolution": "PUBLIC_INFO_UNAVAILABLE",
        "evidence_items": [],
        "discriminating_result": "所有规定来源工具均已尝试但没有取得可核验正文",
        "inference": "公开信息不可得，维持原判断并明确降低可评估性",
    })
    return payload


def test_task_must_follow_queue_and_guard_write_scope(tmp_path: Path) -> None:
    _setup(tmp_path, missing=["正常化利润的分部重建"])
    assert begin_judgment_research_task(tmp_path, "JR002")["started"] is False
    assert begin_judgment_research_task(tmp_path, "JR001")["started"] is True
    assert preflight_judgment_tool_call(tmp_path, "search_report", {"query": "分红"})["allowed"] is True
    blocked = preflight_judgment_tool_call(tmp_path, "write_chapter", {"chapter_index": 5})
    assert blocked["allowed"] is False
    assert blocked["error"] == "chapter_outside_mutation_scope:5"
    assert preflight_judgment_tool_call(tmp_path, "assemble_report", {})["allowed"] is False


def test_required_tools_and_sources_are_machine_verified(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {"query": "分红"}, _ok())
    incomplete = complete_judgment_research_task(
        tmp_path, "JR001", "EVIDENCE_FOUND", ["annual_report"], "找到分红记录"
    )
    assert incomplete["completed"] is False
    assert any("read_section" in item for item in incomplete["violations"])


def test_successful_task_records_calls_and_completes(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {"query": "资本配置"}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {"year": 2025, "section": "GOV"}, _ok())
    result = complete_judgment_research_task(
        tmp_path, "JR001", "NO_DECISION_CHANGE", ["JR001:S02:read_section"],
        "治理记录没有提供足以改变估值的新事实。",
        _finding("JR001", "JR001:S02:read_section"),
    )
    assert result["completed"] is True
    evaluation = evaluate_judgment_research_execution(tmp_path)
    assert evaluation["state"] == "COMPLETE"
    assert evaluation["completed_tasks"] == 1


def test_completion_safely_infers_the_single_active_task_id(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {"query": "资本配置"}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {"year": 2025, "section": "GOV"}, _ok())
    result = complete_judgment_research_task(
        tmp_path, "", "", ["JR001:S02:read_section"],
        "治理记录没有提供足以改变估值的新事实。",
        _finding("JR001", "JR001:S02:read_section"),
    )
    assert result["completed"] is True
    assert result["task_id"] == "JR001"
    assert result["task_id_inferred"] is True
    assert result["outcome_inferred"] is True


def test_unverifiable_builtin_web_result_does_not_satisfy_required_tool(tmp_path: Path) -> None:
    _setup(tmp_path, missing=["同业公司历史基准率与样本分布"])
    # Complete JR001 first, then the peer/base-rate task becomes active.
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {}, _ok())
    complete_judgment_research_task(tmp_path, "JR001", "NO_DECISION_CHANGE", ["JR001:S02:read_section"], "无变化", _finding("JR001", "JR001:S02:read_section"))
    begin_judgment_research_task(tmp_path, "JR002")
    record_judgment_tool_call(tmp_path, "get_peer_comparison", {}, _ok())
    record_judgment_tool_call(tmp_path, "web_search", {}, _ok())
    record_judgment_tool_call(tmp_path, "web_fetch", {}, _ok(), verifiable=False)
    result = complete_judgment_research_task(tmp_path, "JR002", "EVIDENCE_FOUND", ["peer_source"], "找到同业样本")
    assert result["completed"] is False
    assert any("web_fetch" in item for item in result["violations"])


def test_actual_hash_change_outside_scope_is_a_violation(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    (tmp_path / "chapters" / "_ch05.md").write_text("越界修改", encoding="utf-8")
    record_judgment_tool_call(tmp_path, "search_report", {}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {}, _ok())
    result = complete_judgment_research_task(tmp_path, "JR001", "NO_DECISION_CHANGE", ["JR001:S02:read_section"], "无变化", _finding("JR001", "JR001:S02:read_section"))
    assert result["completed"] is False
    assert any("chapter:5" in item for item in result["violations"])
    assert evaluate_judgment_research_execution(tmp_path)["blocking"] is True


def test_tool_budget_and_idempotent_replanning_are_enforced(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    for idx in range(8):
        record_judgment_tool_call(tmp_path, "search_report", {"query": str(idx)}, _ok())
    assert preflight_judgment_tool_call(tmp_path, "read_section", {})["error"] == "judgment_research_tool_budget_exhausted"
    # Rebuilding an identical plan must not erase the active task or its calls.
    persist_judgment_research_plan(tmp_path, max_tasks_per_run=3)
    ledger = json.loads((tmp_path / "judgment_research_execution.json").read_text(encoding="utf-8"))
    assert ledger["active_task_id"] == "JR001"
    assert len(ledger["tasks"]["JR001"]["tool_calls"]) == 8


def test_empty_source_result_is_attempted_but_not_successful_and_unavailable_can_close(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    first = record_judgment_tool_call(
        tmp_path, "search_report", {"query": "不存在"},
        {"ok": True, "value": {"total_hits": 0, "hits": []}},
    )
    record_judgment_tool_call(
        tmp_path, "read_section", {"section": "GOV"},
        {"ok": True, "value": {"text": ""}},
    )
    ledger = json.loads((tmp_path / "judgment_research_execution.json").read_text(encoding="utf-8"))
    calls = ledger["tasks"]["JR001"]["tool_calls"]
    assert first["source_id"] == "JR001:S01:search_report"
    assert first["evidence_usable"] is False
    assert all(item["executed"] is True and item["ok"] is False for item in calls)
    result = complete_judgment_research_task(
        tmp_path, "JR001", "PUBLIC_INFO_UNAVAILABLE", [],
        "规定来源均已尝试但公开信息不可得。", _unavailable_finding("JR001"),
    )
    assert result["completed"] is True


def test_unavailable_without_bounded_judgment_cannot_close_for_free(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(
        tmp_path, "search_report", {"query": "不存在"},
        {"ok": True, "value": {"total_hits": 0, "hits": []}},
    )
    record_judgment_tool_call(
        tmp_path, "read_section", {"section": "GOV"},
        {"ok": True, "value": {"text": ""}},
    )
    finding = _unavailable_finding("JR001")
    finding.pop("uncertainty_closure")
    result = complete_judgment_research_task(
        tmp_path, "JR001", "PUBLIC_INFO_UNAVAILABLE", [],
        "公开资料不可得，因此维持未知、估值与动作不变。", finding,
    )
    assert result["completed"] is False
    assert result["state"] == "ACTIVE"
    assert any("uncertainty_closure_missing" in item for item in result["violations"])


def test_final_budget_slots_are_reserved_for_unattempted_required_tools(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    for idx in range(7):
        record_judgment_tool_call(tmp_path, "search_report", {"query": str(idx)}, _ok())
    blocked = preflight_judgment_tool_call(tmp_path, "search_report", {"query": "extra"})
    assert blocked["allowed"] is False
    assert blocked["error"] == "judgment_research_budget_reserved_for_unattempted_required_tools"
    assert set(blocked["unattempted_required_tools"]) == {"read_section"}
    assert preflight_judgment_tool_call(tmp_path, "read_section", {})["allowed"] is True
    # Non-source mutation/context tools do not consume the evidence budget.
    assert preflight_judgment_tool_call(tmp_path, "read_chapter", {"chapter_index": 0})["allowed"] is True


def test_changed_plan_archives_active_execution_instead_of_silently_erasing_it(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {}, _ok())
    review = json.loads((tmp_path / "judgment_review.json").read_text(encoding="utf-8"))
    review["fragile_leaps"].append({
        "claim": "新增客户证据可能推翻当前判断",
        "why_fragile": "当前来源没有责任匹配的客户留存记录",
        "needed_evidence": "责任匹配的客户留存与订单记录",
        "decision_consequence": "若客户留存反转，估值方向和仓位必须更新",
    })
    _write(tmp_path / "judgment_review.json", review)
    persist_judgment_research_plan(tmp_path)
    archives = list((tmp_path / "judgment_research_history").glob("judgment_research_execution_*.json"))
    assert len(archives) == 1
    archived = json.loads(archives[0].read_text(encoding="utf-8"))
    assert archived["active_task_id"] == "JR001"
    assert len(archived["tasks"]["JR001"]["tool_calls"]) == 1


def test_violation_restart_requires_reason_and_archives_failed_attempt(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    # An actual mutation outside scope is a terminal, auditable violation.
    (tmp_path / "chapters" / "_ch05.md").write_text("越界修改", encoding="utf-8")
    result = complete_judgment_research_task(tmp_path, "JR001", "NO_DECISION_CHANGE", [], "失败尝试", {})
    assert result["state"] == "VIOLATION"
    assert restart_judgment_research_execution(tmp_path, reason="太短")["restarted"] is False
    restarted = restart_judgment_research_execution(
        tmp_path, reason="框架接口修复后重新执行同一研究计划",
    )
    assert restarted["restarted"] is True
    assert restarted["execution"]["state"] == "PENDING"
    archived = json.loads(Path(restarted["archive_path"]).read_text(encoding="utf-8"))
    assert archived["state"] == "VIOLATION"
    assert "框架接口修复" in archived["superseded_reason"]


def test_rejected_completion_stays_active_until_declared_writeback_is_real(tmp_path: Path) -> None:
    _setup(tmp_path)
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {}, _ok())
    finding = _finding("JR001", "JR001:S02:read_section")
    finding["chapter_update"] = {"needed": True, "chapters": [0], "reason": "新证据需要补充概览"}
    rejected = complete_judgment_research_task(
        tmp_path, "JR001", "NO_DECISION_CHANGE", ["JR001:S02:read_section"],
        "需要限定写回。", finding,
    )
    assert rejected["state"] == "ACTIVE"
    assert rejected["repairable_submission"] is True
    assert any("structured_chapter_update_mismatch" in item for item in rejected["violations"])
    ledger = json.loads((tmp_path / "judgment_research_execution.json").read_text(encoding="utf-8"))
    assert ledger["active_task_id"] == "JR001"
    (tmp_path / "chapters" / "_ch00.md").write_text("## Ch0\n\n加入新证据", encoding="utf-8")
    completed = complete_judgment_research_task(
        tmp_path, "JR001", "NO_DECISION_CHANGE", ["JR001:S02:read_section"],
        "限定写回已经完成。", finding,
    )
    assert completed["completed"] is True


def test_selective_retry_preserves_prior_completed_task(tmp_path: Path) -> None:
    _setup(tmp_path, missing=["正常化利润的分部重建"])
    begin_judgment_research_task(tmp_path, "JR001")
    record_judgment_tool_call(tmp_path, "search_report", {}, _ok())
    record_judgment_tool_call(tmp_path, "read_section", {}, _ok())
    assert complete_judgment_research_task(
        tmp_path, "JR001", "NO_DECISION_CHANGE", ["JR001:S02:read_section"],
        "第一项完成", _finding("JR001", "JR001:S02:read_section"),
    )["completed"] is True
    begin_judgment_research_task(tmp_path, "JR002")
    (tmp_path / "chapters" / "_ch05.md").write_text("越界修改", encoding="utf-8")
    violated = complete_judgment_research_task(tmp_path, "JR002", "NO_DECISION_CHANGE", [], "越界", {})
    assert violated["state"] == "VIOLATION"
    retried = retry_violated_judgment_research_task(
        tmp_path, task_id="JR002", reason="修复提交协议后只重试第二项任务",
    )
    assert retried["retried"] is True
    assert retried["preserved_completed_tasks"] == ["JR001"]
    execution = retried["execution"]
    assert execution["tasks"]["JR001"]["status"] == "COMPLETE"
    assert execution["tasks"]["JR002"]["status"] == "PENDING"


def test_execution_control_tools_are_auto_discoverable() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")
    assert "begin_judgment_research_task" in registry.list_tools()
    assert "complete_judgment_research_task" in registry.list_tools()


def test_completion_surfaces_pending_and_blocks_execution_violation(tmp_path: Path) -> None:
    from scripts.report_completion import evaluate_report_completion

    _setup(tmp_path)
    pending = evaluate_report_completion("draft", str(tmp_path))
    assert any("Judgment research pending" in item for item in pending.warning_findings)
    ledger_path = tmp_path / "judgment_research_execution.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["state"] = "VIOLATION"
    ledger["tasks"]["JR001"]["violations"] = ["mutation_outside_scope:chapter:5"]
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    violated = evaluate_report_completion("draft", str(tmp_path))
    assert any("Judgment research execution" in item for item in violated.blocking_findings)
