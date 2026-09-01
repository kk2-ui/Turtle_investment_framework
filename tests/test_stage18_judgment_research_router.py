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


def _fragile(claim: str, *, evidence: str | None = None) -> dict:
    return {
        "claim": claim,
        "why_fragile": "当前来源不足以区分该主张与最强替代解释。",
        "needed_evidence": evidence or claim,
        "decision_consequence": "该事实若反转会改变公司判断、估值方向或当前动作。",
    }


def test_routes_governance_gap_without_company_hardcoding(tmp_path: Path) -> None:
    _case(tmp_path, [{
        "claim": "外部股东能够取得留存现金",
        "why_fragile": "现有材料不能证明资金能够由外部股东取得",
        "needed_evidence": "董事会资本配置、关联交易、分红与回购记录",
        "decision_consequence": "证据会改变资产价值和仓位",
    }], [])
    plan = build_judgment_research_plan(tmp_path)
    task = plan["tasks"][0]
    assert task["route"] == "governance_and_value_realization"
    assert task["required_tools"] == ["search_report", "read_section"]
    assert task["mutation_scope"]["chapters"] == [0, 3, 9, 12, 14]


def test_routes_peer_base_rate_and_operating_rebuild_as_distinct_work(tmp_path: Path) -> None:
    _case(tmp_path, [
        _fragile("同类公司历史兑现结果能否支持当前判断", evidence="同类公司历史兑现结果与行业基准率分布"),
        _fragile("正常化利润是否被分部结构扭曲", evidence="正常化利润的分部收入、毛利率和费用率重建"),
    ], [])
    plan = build_judgment_research_plan(tmp_path)
    routes = {item["route"] for item in plan["tasks"]}
    assert "peer_and_base_rate" in routes
    assert "operating_model_rebuild" in routes


def test_contract_route_prefers_primary_terms_and_regulation(tmp_path: Path) -> None:
    _case(tmp_path, [_fragile("受限存款是否能由普通股股东取得", evidence="存款协议的期限、提前支取、担保和监管条款")], [])
    task = build_judgment_research_plan(tmp_path)["tasks"][0]
    assert task["route"] == "contract_and_regulation"
    assert "contract_or_agreement" in task["required_source_types"]
    assert task["stopping_rule"]["unavailable_is_a_valid_outcome"] is True


def test_execution_is_bounded_and_cannot_request_report_wide_rewrite(tmp_path: Path) -> None:
    _case(tmp_path, [_fragile(f"材料经营主张{idx}", evidence=f"区分经营主张{idx}的原始证据") for idx in range(9)], [], verdict="FRAGILE")
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
    _case(tmp_path, [_fragile("控制权安排是否改变现金可达性", evidence="需要核验的原始资料")], [])
    plan = build_judgment_research_plan(tmp_path)
    plan["tasks"][0]["mutation_scope"]["chapters"] = list(range(15))
    result = validate_judgment_research_plan(plan)
    assert result["state"] == "INVALID"
    assert any("chapter_scope_too_broad" in item for item in result["invalid_findings"])


def test_structured_finding_and_independent_review_policies_are_mandatory(tmp_path: Path) -> None:
    _case(tmp_path, [_fragile("控制权安排是否改变现金可达性", evidence="需要核验的原始资料")], [])
    plan = build_judgment_research_plan(tmp_path)
    plan["execution_policy"].pop("structured_findings_required")
    plan["execution_policy"].pop("independent_synthesis_context")
    result = validate_judgment_research_plan(plan)
    assert "structured_findings_policy_missing" in result["invalid_findings"]
    assert "independent_synthesis_policy_missing" in result["invalid_findings"]


def test_persisted_plan_is_diagnostic_and_tool_is_discoverable(tmp_path: Path) -> None:
    _case(tmp_path, [_fragile("治理事件是否改变价值兑现", evidence="市场参与者在治理事件前后的估值反应")], [])
    result = persist_judgment_research_plan(tmp_path)
    assert result["written"] is True
    evaluated = evaluate_output_judgment_research_plan(tmp_path)
    assert evaluated["state"] == "READY" and evaluated["blocking"] is False
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")
    assert "plan_judgment_research" in registry.list_tools()


def test_missing_information_alone_does_not_create_repeat_research(tmp_path: Path) -> None:
    _case(tmp_path, [], ["客户留存率未披露", "下一年度分部利润尚不可见"])

    plan = build_judgment_research_plan(tmp_path)

    assert plan["state"] == "NO_ACTION"
    assert plan["tasks"] == []
    assert plan["execution_queue"] == []


def test_incomplete_fragile_leap_does_not_create_a_research_reward(tmp_path: Path) -> None:
    _case(tmp_path, [{
        "claim": "外部股东能够取得留存现金",
        "why_fragile": "现有材料不能证明资金能够由外部股东取得",
        "needed_evidence": "董事会资本配置、关联交易、分红与回购记录",
    }], [])

    plan = build_judgment_research_plan(tmp_path)

    assert plan["state"] == "NO_ACTION"
    assert plan["tasks"] == []


def test_company_judgment_fragile_uses_judgment_consequence_and_excludes_investment_ledgers(tmp_path: Path) -> None:
    _case(tmp_path, [{
        "claim": "分部毛利下降来自核心客户流失",
        "why_fragile": "合并收入无法区分核心客户流失与产品组合变化",
        "needed_evidence": "责任匹配的分部客户留存、收入和毛利桥",
        "judgment_consequence": "若客户留存反转，应下调正常盈利并提高永久损失风险",
    }], [])
    review = json.loads((tmp_path / "judgment_review.json").read_text(encoding="utf-8"))
    review["analysis_purpose"] = "COMPANY_JUDGMENT_ONLY"
    _write(tmp_path / "judgment_review.json", review)

    plan = build_judgment_research_plan(tmp_path)
    task = plan["tasks"][0]

    assert task["why_it_matters"] == "若客户留存反转，应下调正常盈利并提高永久损失风险"
    assert task["priority"] == "critical"
    assert "decision" not in task["mutation_scope"]["ledgers"]
    assert "valuation_model" not in task["mutation_scope"]["ledgers"]
