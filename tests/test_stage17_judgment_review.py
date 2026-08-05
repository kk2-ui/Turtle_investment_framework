from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_review import (
    build_judgment_review,
    evaluate_output_judgment_review,
    persist_judgment_review,
    validate_judgment_review,
)
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.read_tools import read_structured_ledger_contract


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _dependencies(output: Path) -> None:
    _write(output / "analysis_contract.json", {"ts_code": "000001.SZ"})
    _write(output / "insight_ledger.json", {
        "report_id": "000001.SZ", "insights": [{"insight_id": "I001"}],
    })
    _write(output / "claim_evidence.json", {
        "claims": [{"raw_facts": [{"evidence_id": "E001"}, {"evidence_id": "E002"}]}],
    })
    _write(output / "decision_ledger.json", {
        "entries": [{"entry_id": "D001", "status": "active"}],
    })
    _write(output / "valuation_model.json", {"models": [{"model_id": "M001"}]})


def _payload(output: Path) -> dict:
    return build_judgment_review(
        output,
        "COMPETENT",
        "核心变量能改变估值与动作，但关键机制仍缺少一项直接外部证据，因此属于可靠但尚非卓越的研究判断。",
        {
            "insight_id": "I001",
            "why_it_matters": "该变量决定资产折价是否能够转化为股东回报。",
            "why_not_obvious": "账面现金规模本身无法回答控制权和可达性。",
            "evidence_ids": ["E001", "E002"],
            "decision_entry_ids": ["D001"],
            "valuation_model_ids": ["M001"],
        },
        ["财务趋势与分红覆盖分析可靠，但属于标准研究动作。"],
        [{
            "claim": "控制权折价会长期维持",
            "why_fragile": "现有材料没有直接证明资金不能迁移。",
            "needed_evidence": "财务公司协议、存款期限和历史资金迁移记录。",
            "decision_consequence": "若资金可自由迁移，应提高估值并改变仓位。",
        }],
        {
            "strongest_alternative": "稳定分红已经缓释资产陷阱。",
            "evidence_for_alternative": "实际派息率高于公开政策底线。",
            "discriminator": "未来分红、回购与资金迁移的连续记录。",
            "unresolved": "缺少足够长的独立资本配置样本。",
        },
        ["资金迁移条款", "同类国企物业公司的资本配置基准率"],
        {
            "without_insight": "只能得到常规高股息低估值判断。",
            "changed_values": "留存兑现率和最终价值失去可解释锚点。",
            "changed_action": "观察仓无法获得明确的升级条件。",
            "conclusion": "核心洞见对估值和动作具有实质依赖。",
        },
        {
            "question_selection": {"state": "strong", "basis": "问题直接锁定外部股东能否取得价值。"},
            "differentiation": {"state": "strong", "basis": "从现金规模推进到外部股东留存兑现率这个关键变量。"},
            "evidence_discrimination": {"state": "mixed", "basis": "报告存在支持反证，但仍然缺少资金迁移条款等直接证据。"},
            "valuation_transmission": {"state": "strong", "basis": "关键兑现率变量已经明确进入主估值模型及压力情景。"},
            "action_relevance": {"state": "strong", "basis": "判断变化会直接调整仓位和买入条件。"},
        },
        ["该评审只能依据当前输出目录内可见信息，不能证明市场共识。"],
    )


def test_complete_judgment_review_is_cross_ledger_bound(tmp_path: Path) -> None:
    _dependencies(tmp_path)
    result = persist_judgment_review(tmp_path, _payload(tmp_path))
    assert result["written"] is True
    assert result["validation"]["state"] == "REVIEWED"
    assert result["validation"]["ceiling_verdict"] == "COMPETENT"


def test_unknown_binding_invalidates_review(tmp_path: Path) -> None:
    _dependencies(tmp_path)
    payload = _payload(tmp_path)
    payload["distinctive_insight"]["valuation_model_ids"] = ["M404"]
    result = validate_judgment_review(payload, tmp_path)
    assert result["state"] == "INVALID"
    assert any("M404" in item for item in result["invalid_findings"])


def test_invalid_attempt_does_not_overwrite_canonical_review_validation(tmp_path: Path) -> None:
    _dependencies(tmp_path)
    assert persist_judgment_review(tmp_path, _payload(tmp_path))["written"] is True
    bad = _payload(tmp_path)
    bad["dimension_assessments"]["question_selection"]["state"] = "STRONG"
    result = persist_judgment_review(tmp_path, bad)
    assert result["written"] is False
    canonical = json.loads(
        (tmp_path / "judgment_review_validation.json").read_text(encoding="utf-8")
    )
    attempted = json.loads(
        (tmp_path / "judgment_review_last_attempt_validation.json").read_text(encoding="utf-8")
    )
    assert canonical["state"] == "REVIEWED"
    assert attempted["state"] == "INVALID"
    assert "dimension_assessments:question_selection:state_invalid" in attempted["invalid_findings"]


def test_judgment_contract_exposes_lowercase_dimension_enum_and_ids(tmp_path: Path) -> None:
    _dependencies(tmp_path)
    result = read_structured_ledger_contract(str(tmp_path), ledger="judgment")
    assert result["ok"] is True
    assert "strong|mixed|weak|not_assessable lowercase" in result["contract"]["dimension_assessments"]
    assert result["sequence"][-1] == "judgment"


def test_missing_review_is_visible_but_diagnostic_only(tmp_path: Path) -> None:
    _dependencies(tmp_path)
    result = evaluate_output_judgment_review(tmp_path)
    assert result["state"] == "NOT_ASSESSABLE"
    assert result["status"] == "SKIP"
    assert result["policy_note"].startswith("Judgment review is diagnostic")


def test_judgment_review_tool_is_auto_discoverable() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")
    assert "write_judgment_review" in registry.list_tools()


def test_ceiling_verdict_cannot_change_v3_lifecycle(tmp_path: Path) -> None:
    from scripts.v3_quality_report import evaluate_v3_quality

    gates = {
        name: {"state": "DECISION_READY"}
        for name in ("decision", "claim_evidence", "valuation", "thesis_test", "insight")
    }
    result = evaluate_v3_quality(
        tmp_path,
        "一段可审阅的报告正文。",
        gate_results=gates,
        judgment_review={"state": "INVALID", "ceiling_verdict": "FRAGILE"},
        persist=False,
    )
    assert result["status"] == "DECISION_READY"
    assert result["layers"]["judgment_ceiling"] == {
        "state": "INVALID", "verdict": "FRAGILE", "blocking": False,
    }
