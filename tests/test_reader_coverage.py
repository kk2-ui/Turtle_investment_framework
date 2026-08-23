from __future__ import annotations

import json
from pathlib import Path

from scripts.reader_coverage import evaluate_reader_coverage, reader_coverage_prompt


def _paragraphs() -> str:
    return "\n\n".join(
        [
            "公司提供面向客户的核心产品和服务，支付方通过定价购买，收入来自销售和持续使用。这个业务在产业链中承担服务入口角色，因此读者需要先理解客户为什么付钱以及公司怎样把服务变成收入。[source: 2025_年报.md]",
            "历史收入和利润经过周期调整后，正常盈利要扣除维持性资本开支，才能转换为普通股股东真正可得的owner earnings和自由现金流。这个现金路线解释了经营变化怎样传导到可持续回报。[source: 2024_年报.md]",
            "合并现金不等于普通股现金；需要先看现金由哪个实体控制、能否上游分配，再扣除少数股东、债务和受限资金。普通股可得分红取决于这些索取权和控制限制。[source: 2025_年报.md]",
            "估值采用正常现金流和经营价值模型，并同时展示股东回报率、当前价格、未来业务价值和期末市场价格。P_LONG是长期持有价格，P_XIRR是有限期限条件价格，二者身份不同。[source: 2025_年报.md]",
            "最强反方认为利润和现金可能继续下滑；如果债务失控或资产发生不可逆损失，就会形成永久资本毁灭。替代解释是周期恢复，后续数据可以证伪其中一条路径。[source: 2025_年报.md]",
            "投资者应跟踪利润、现金流和回款等指标；如果现金低于阈值或分派下降，就触发降级，如果经营改善达到阈值才升级判断。[source: 2025_年报.md]",
            "年报提供了主要事实，但部分实体现金限制和未来回收金额未披露，当前估值仍是区间和条件判断，未知项会限制价格和动作置信度。[source: 2025_年报.md]",
        ]
    )


def test_reader_coverage_requires_explanations_not_appendix_link(tmp_path: Path) -> None:
    result = evaluate_reader_coverage(
        "# 公司备忘录\n\n完整证据见技术附录。\n\n[技术附录](technical.md)",
        tmp_path,
        archetype="general_operating",
    )

    assert result["status"] == "BLOCKED"
    assert "topic_missing:business_mechanism" in result["blocking_findings"]
    assert "reader_source_anchor_missing" in result["blocking_findings"]


def test_reader_coverage_accepts_unknown_with_economic_boundary(tmp_path: Path) -> None:
    (tmp_path / "decision_manifest.json").write_text(
        json.dumps({"display_label": "观望", "unified_decision": "观望"}),
        encoding="utf-8",
    )
    result = evaluate_reader_coverage(_paragraphs() + "\n\n当前结论是观望。", tmp_path)

    assert result["status"] == "PASS"
    assert all(item["status"] == "PASS" for item in result["topics"].values())


def test_archetype_route_uses_asset_cash_questions(tmp_path: Path) -> None:
    text = _paragraphs().replace(
        "历史收入和利润经过周期调整后，正常盈利要扣除维持性资本开支，才能转换为普通股股东真正可得的owner earnings和自由现金流。这个现金路线解释了经营变化怎样传导到可持续回报。",
        "项目租金和出租率决定资产收入，现金回款要扣除维护资本开支、债务利息并受特许期限约束。这个NPI和可分配现金路线解释资产价值怎样到达普通股。[source: 2024_年报.md]",
    )
    result = evaluate_reader_coverage(text + "\n\n当前结论是观望。", tmp_path, archetype="utility_infrastructure")

    assert result["status"] == "PASS"
    assert result["archetype"] == "utility_infrastructure"


def test_reader_coverage_flags_stale_decision_identity(tmp_path: Path) -> None:
    (tmp_path / "decision_manifest.json").write_text(
        json.dumps({"display_label": "买入", "unified_decision": "买入"}),
        encoding="utf-8",
    )
    result = evaluate_reader_coverage(_paragraphs() + "\n\n当前结论是观望。", tmp_path)

    assert result["status"] == "BLOCKED"
    assert "decision_display_label_missing_from_reader" in result["blocking_findings"]


def test_prompt_names_unknown_and_reader_explanation() -> None:
    prompt = reader_coverage_prompt(archetype="general_operating")
    assert "UNKNOWN" in prompt
    assert "附录链接" in prompt
    assert "内部对象ID" in prompt


def test_reader_coverage_rejects_internal_workflow_status_and_object_ids(tmp_path: Path) -> None:
    leaks = {
        "MECHANISM_READY": "workflow_status",
        "NOT_EVIDENCED": "workflow_status",
        "LEARNING_APPLIED": "workflow_status",
        "READY_WITH_NO_PRIOR": "workflow_status",
        "G1J_COMPLETE": "workflow_status",
        "LEGACY_PARTIAL": "workflow_status",
        "NO_PRIMARY": "workflow_status",
        "SELECTION_ADMITTED": "workflow_status",
        "BINDING_PENDING": "workflow_status",
        "REVIEWABLE": "workflow_status",
        "DECISION_READY": "workflow_status",
        "PIT_EVIDENCE_ONLY": "workflow_status",
        "JAXREPORT:pair-a": "workflow_object_id",
        "JAXUNIT:unit-a": "workflow_object_id",
        "FJ:channel-share": "workflow_object_id",
        "RHP:primary-rival": "workflow_object_id",
        "RHPASM:assumption-a": "workflow_object_id",
        "RHPSIG:channel": "workflow_object_id",
        "FDB:cash": "workflow_object_id",
        "FDBDRV:cash": "workflow_object_id",
        "FDBEV:buyback": "workflow_object_id",
        "FDBMON:cash": "workflow_object_id",
    }

    for token, category in leaks.items():
        result = evaluate_reader_coverage(
            _paragraphs() + f"\n\n内部审计引用 {token}，其他结论不变。",
            tmp_path,
        )
        assert result["status"] == "BLOCKED", token
        assert f"reader_internal_control_leak:{category}" in result["blocking_findings"]


def test_reader_coverage_rejects_an_obvious_control_panel(tmp_path: Path) -> None:
    text = _paragraphs() + "\n\n| validation gate | status |\n|---|---|\n| thesis_test | DECISION_READY |"

    result = evaluate_reader_coverage(text, tmp_path)

    assert result["status"] == "BLOCKED"
    assert "reader_internal_control_leak:workflow_panel" in result["blocking_findings"]


def test_reader_coverage_allows_plain_language_and_does_not_scan_technical_appendix(
    tmp_path: Path,
) -> None:
    (tmp_path / "technical_appendix.md").write_text(
        "MECHANISM_READY FJ:channel RHPSIG:channel\nstatus: DECISION_READY",
        encoding="utf-8",
    )
    text = _paragraphs() + (
        "\n\n当前经营状态仍有不确定性，因此这项判断只说明渠道机制需要继续验证，"
        "不能提高报告结论的置信度。"
    )

    result = evaluate_reader_coverage(text, tmp_path)

    assert result["status"] == "PASS"
    assert not any(
        item.startswith("reader_internal_control_leak:")
        for item in result["blocking_findings"]
    )
