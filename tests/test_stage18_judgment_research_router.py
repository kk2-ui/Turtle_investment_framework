from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_research_router import (
    build_judgment_research_plan,
    evaluate_output_judgment_research_plan,
    persist_judgment_research_plan,
    validate_judgment_research_plan,
)
from scripts.turtle_agent.tool_registry import ToolRegistry


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _case(output: Path, fragile: list[dict], missing: list[str], verdict: str = "COMPETENT") -> None:
    _write(output / "insight_ledger.json", {
        "report_id": "CASE",
        "insights": [{"insight_id": "I001", "chapters": [0, 3, 9, 12, 14]}],
    })
    _write(output / "judgment_review.json", {
        "report_id": "CASE",
        "ceiling_verdict": verdict,
        "verdict_basis": "该缺口可能改变估值与动作，需要有限且可停止的定向研究。",
        "distinctive_insight": {"insight_id": "I001"},
        "fragile_leaps": fragile,
        "missing_information": missing,
        "decision_dependency": {"conclusion": "若证据反转，估值和仓位必须更新。"},
    })


def test_routes_governance_gap_without_company_hardcoding(tmp_path: Path) -> None:
    _case(tmp_path, [{
        "claim": "外部股东能够取得留存现金",
        "needed_evidence": "董事会资本配置、关联交易、分红与回购记录",
        "decision_consequence": "证据会改变资产价值和仓位",
    }], [])
    plan = build_judgment_research_plan(tmp_path)
    task = plan["tasks"][0]
    assert task["route"] == "governance_and_value_realization"
    assert task["required_tools"] == ["search_report", "read_section"]
    assert task["mutation_scope"]["chapters"] == [0, 3, 9, 12, 14]


def test_routes_peer_base_rate_and_operating_rebuild_as_distinct_work(tmp_path: Path) -> None:
    _case(tmp_path, [], [
        "同类公司历史兑现结果与行业基准率分布",
        "正常化利润的分部收入、毛利率和费用率重建",
    ])
    plan = build_judgment_research_plan(tmp_path)
    routes = {item["route"] for item in plan["tasks"]}
    assert "peer_and_base_rate" in routes
    assert "operating_model_rebuild" in routes


def test_contract_route_prefers_primary_terms_and_regulation(tmp_path: Path) -> None:
    _case(tmp_path, [], ["存款协议的期限、提前支取、担保和监管条款"])
    task = build_judgment_research_plan(tmp_path)["tasks"][0]
    assert task["route"] == "contract_and_regulation"
    assert "contract_or_agreement" in task["required_source_types"]
    assert task["stopping_rule"]["unavailable_is_a_valid_outcome"] is True


def test_execution_is_bounded_and_cannot_request_report_wide_rewrite(tmp_path: Path) -> None:
    _case(tmp_path, [], [f"缺失信息{idx}" for idx in range(9)], verdict="FRAGILE")
    plan = build_judgment_research_plan(tmp_path, max_tasks_per_run=99)
    assert len(plan["execution_queue"]) == 3
    assert len(plan["backlog_task_ids"]) == 6
    assert all(task["stopping_rule"]["max_tool_calls"] <= 8 for task in plan["tasks"])
    assert "rewrite_all_chapters" in plan["forbidden_mutations"]
    assert "optimize_score_or_length" in plan["forbidden_mutations"]
    assert plan["execution_policy"]["structured_findings_required"] is True
    assert plan["execution_policy"]["independent_synthesis_context"] is True
    assert validate_judgment_research_plan(plan)["state"] == "READY"


def test_invalid_broad_scope_is_detected(tmp_path: Path) -> None:
    _case(tmp_path, [], ["需要核验的原始资料"])
    plan = build_judgment_research_plan(tmp_path)
    plan["tasks"][0]["mutation_scope"]["chapters"] = list(range(15))
    result = validate_judgment_research_plan(plan)
    assert result["state"] == "INVALID"
    assert any("chapter_scope_too_broad" in item for item in result["invalid_findings"])


def test_structured_finding_and_independent_review_policies_are_mandatory(tmp_path: Path) -> None:
    _case(tmp_path, [], ["需要核验的原始资料"])
    plan = build_judgment_research_plan(tmp_path)
    plan["execution_policy"].pop("structured_findings_required")
    plan["execution_policy"].pop("independent_synthesis_context")
    result = validate_judgment_research_plan(plan)
    assert "structured_findings_policy_missing" in result["invalid_findings"]
    assert "independent_synthesis_policy_missing" in result["invalid_findings"]


def test_persisted_plan_is_diagnostic_and_tool_is_discoverable(tmp_path: Path) -> None:
    _case(tmp_path, [], ["市场参与者在治理事件前后的估值反应"])
    result = persist_judgment_research_plan(tmp_path)
    assert result["written"] is True
    evaluated = evaluate_output_judgment_research_plan(tmp_path)
    assert evaluated["state"] == "READY" and evaluated["blocking"] is False
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")
    assert "plan_judgment_research" in registry.list_tools()
