from __future__ import annotations

import json
from pathlib import Path

from scripts.reader_coverage import evaluate_reader_coverage, reader_coverage_prompt


def _paragraphs() -> str:
    return "\n\n".join(
        [
            "公司提供面向客户的核心产品和服务，支付方通过定价购买，收入来自销售和持续使用。这个业务在产业链中承担服务入口角色，因此读者需要先理解客户为什么付钱以及公司怎样把服务变成收入。[source: 2025_年报.md]",
            "未来五年，行业最可能从新增需求驱动转向存量竞争，因为供给仍然充足而客户更看重价格和服务，利润池将向低成本和高复购环节迁移。本公司的客户结构和核心产品直接暴露于这条主路径，管理层退出低回报合同并调整渠道后，正常盈利和owner cash更可能稳定；若调整失败，毛利和资本回报下滑会形成永久损失并压低估值。[source: 行业协会_2025.md]",
            "历史收入和利润经过周期调整后，正常盈利要扣除维持性资本开支，才能转换为普通股股东真正可得的owner earnings和自由现金流。这个现金路线解释了经营变化怎样传导到可持续回报。[source: 2024_年报.md]",
            "合并现金不等于普通股现金；需要先看现金由哪个实体控制、能否上游分配，再扣除少数股东、债务和受限资金。普通股可得分红取决于这些索取权和控制限制。[source: 2025_年报.md]",
            "估值采用正常现金流和经营价值模型，并同时展示股东回报率、当前价格、未来业务价值和期末市场价格。长期持有价格与有限期限条件价格的经济含义不同，不能混为一个价格。[source: 2025_年报.md]",
            "最强反方认为利润和现金可能继续下滑；如果债务失控或资产发生不可逆损失，就会形成永久资本毁灭。替代解释是周期恢复，后续数据可以证伪其中一条路径。[source: 2025_年报.md]",
            "投资者应跟踪利润、现金流和回款等指标；如果现金低于阈值或分派下降，就触发降级，如果经营改善达到阈值才升级判断。[source: 2025_年报.md]",
            "年报提供了主要事实，但部分实体现金限制和未来回收金额未披露，因此在责任匹配的分红或回款披露前不计入基准估值，未知项会限制owner cash、价格和动作置信度；若后续披露可上游现金则升级，否则维持折价。[source: 2025_年报.md]",
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
    boundary = result["topics"]["data_boundaries"]
    assert any(item["unknown_closure"] for item in boundary["evidence"])


def test_reader_coverage_requires_each_compiler_owned_numeric_sentence_once(
    tmp_path: Path,
) -> None:
    sentence = (
        "税费和收取摩擦后的普通股分配为RMB278.417百万元，"
        "即约RMB2.784亿元。"
    )
    (tmp_path / "valuation_model.json").write_text(
        json.dumps({
            "value_bridge_models": {
                "reader_slots": [{
                    "slot_id": "after_tax_common_distribution",
                    "metric": "AFTER_TAX_COMMON_DISTRIBUTION",
                    "sentence": sentence,
                }],
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    missing = evaluate_reader_coverage(_paragraphs(), tmp_path)
    present = evaluate_reader_coverage(_paragraphs() + "\n\n" + sentence, tmp_path)
    duplicated = evaluate_reader_coverage(
        _paragraphs() + "\n\n" + sentence + "\n\n" + sentence,
        tmp_path,
    )

    assert "reader_numeric_slot_missing:after_tax_common_distribution" in (
        missing["blocking_findings"]
    )
    assert present["status"] == "PASS"
    assert "reader_numeric_slot_duplicated:after_tax_common_distribution" in (
        duplicated["blocking_findings"]
    )


def test_industry_future_requires_a_directional_company_transmission(
    tmp_path: Path,
) -> None:
    directional = (
        "未来五年，行业最可能从新增需求驱动转向存量竞争，因为供给仍然充足而客户更看重价格和服务，"
        "利润池将向低成本和高复购环节迁移。本公司的客户结构和核心产品直接暴露于这条主路径，"
        "管理层退出低回报合同并调整渠道后，正常盈利和owner cash更可能稳定；若调整失败，"
        "毛利和资本回报下滑会形成永久损失并压低估值。[source: 行业协会_2025.md]"
    )
    trend_inventory = (
        "未来五年行业同时存在周期、结构性变化、需求、供给、竞争和价格压力。公司可以调整渠道、"
        "客户结构与产品结构，正常盈利、现金、资本回报、永久损失和估值分别放入基础、压力和有利"
        "三组情景，后续继续观察。[source: 行业协会_2025.md]"
    )

    result = evaluate_reader_coverage(
        _paragraphs().replace(directional, trend_inventory),
        tmp_path,
    )

    assert result["status"] == "BLOCKED"
    assert "topic_missing:industry_future_transmission" in result["blocking_findings"]
    assert result["topics"]["industry_future_transmission"]["status"] == "FAIL"


def test_reader_coverage_rejects_an_unknown_wall_with_one_global_source(tmp_path: Path) -> None:
    text = "\n\n".join([
        "产品、客户和收入机制全部未知，因为公司没有披露，所以无法判断业务怎样赚钱，只能等待更多资料。[source: 2025_年报.md]",
        "收入、利润、现金流和正常盈利全部未知，因为资料不足，所以无法判断，也不改变任何结论，等待以后披露。",
        "普通股、归母现金、少数股东和债务索取全部未知，因为没有资料，所以无法判断现金可达性，等待披露。",
        "估值、回报、当前价和未来价格全部未知，因为缺少输入，所以无法计算或判断，动作维持不变并等待披露。",
        "风险、反方、永久损失和替代解释全部未知，因为证据不足，所以无法判断资本是否会毁灭，等待披露。",
        "后续监控指标、阈值、升级和降级条件全部未知，因为没有信息，所以只能继续跟踪和等待新的公开资料。",
        "年报、来源、证据、假设和数据缺口全部未知，因为未披露，所以保持不确定，不对任何判断作处理。",
    ])

    result = evaluate_reader_coverage(text, tmp_path, archetype="general_operating")

    assert result["status"] == "BLOCKED"
    assert any(item.startswith("topic_missing:") for item in result["blocking_findings"])
    assert not all(item["status"] == "PASS" for item in result["topics"].values())


def test_reader_coverage_rejects_unknown_wall_with_closure_keywords(tmp_path: Path) -> None:
    topics = [
        "产品、客户与收入机制", "正常盈利与现金路线", "普通股现金可达性",
        "估值、回报与价格身份", "反方与永久损失", "监控指标与触发条件",
        "来源、假设与数据边界",
    ]
    text = "\n\n".join(
        f"{topic}全部未知，因为未披露，所以保守不给结论，owner cash与估值区间后果未知；若后续披露则升级，否则维持折价。[source: 2025_年报.md]"
        for topic in topics
    )

    result = evaluate_reader_coverage(text, tmp_path, archetype="general_operating")

    assert result["status"] == "BLOCKED"
    assert result["topics"]["business_mechanism"]["status"] == "FAIL"
    assert result["topics"]["earnings_route"]["status"] == "FAIL"


def test_local_unknown_requires_treatment_consequence_and_flip_fact(tmp_path: Path) -> None:
    text = _paragraphs().replace(
        "因此在责任匹配的分红或回款披露前不计入基准估值，未知项会限制owner cash、价格和动作置信度；若后续披露可上游现金则升级，否则维持折价。",
        "因此当前全部未知并等待后续披露。",
    )

    result = evaluate_reader_coverage(text, tmp_path)

    assert result["status"] == "BLOCKED"
    assert "topic_missing:data_boundaries" in result["blocking_findings"]


def test_local_unknown_does_not_erase_a_supported_affirmative_clause(tmp_path: Path) -> None:
    mixed_business = (
        "公司向经销商销售高端产品，客户因耐用性支付溢价，因此提价在销量稳定时转为更高收入；"
        "但客户留存率未披露，仅限制复购强度判断。[source: 2025_年报.md]"
    )
    text = _paragraphs().replace(
        "公司提供面向客户的核心产品和服务，支付方通过定价购买，收入来自销售和持续使用。这个业务在产业链中承担服务入口角色，因此读者需要先理解客户为什么付钱以及公司怎样把服务变成收入。[source: 2025_年报.md]",
        mixed_business,
    )

    result = evaluate_reader_coverage(text, tmp_path)

    assert result["status"] == "PASS"
    business = result["topics"]["business_mechanism"]
    assert business["status"] == "PASS"
    assert any(item["unknown"] for item in business["evidence"])


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
    assert "行业未来" in prompt
    assert "并列情景" in prompt
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
        "CANNOT_BOUND": "workflow_status",
        "EXCLUDE_FROM_BASE": "workflow_status",
        "RESULT_KNOWN_TEACHING_ONLY": "workflow_status",
        "DATA_COVERAGE": "review_taxonomy",
        "ACQUISITION_MODULE": "review_taxonomy",
        "REASONING": "review_taxonomy",
        "MODEL": "review_taxonomy",
        "WRITING": "review_taxonomy",
        "PRIMARY_ROUTE_UNKNOWN": "model_identity",
        "P_LONG": "model_identity",
        "P_XIRR_15Y": "model_identity",
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


def test_reader_coverage_rejects_an_obvious_review_return_panel(tmp_path: Path) -> None:
    text = _paragraphs() + "\n\nroot_cause: DATA_COVERAGE\nmissing_facts: project cash bridge"

    result = evaluate_reader_coverage(text, tmp_path)

    assert result["status"] == "BLOCKED"
    assert "reader_internal_control_leak:review_taxonomy" in result["blocking_findings"]
    assert "reader_internal_control_leak:review_panel" in result["blocking_findings"]


def test_reader_coverage_allows_plain_language_and_does_not_scan_technical_appendix(
    tmp_path: Path,
) -> None:
    (tmp_path / "technical_appendix.md").write_text(
        "MECHANISM_READY FJ:channel RHPSIG:channel\nstatus: DECISION_READY",
        encoding="utf-8",
    )
    text = _paragraphs() + (
        "\n\n当前经营状态仍有不确定性，因此这项判断只说明渠道机制需要继续验证，"
        "不能提高报告结论的置信度。NAV、EPV与owner cash仍是允许向读者解释的经济概念。"
    )

    result = evaluate_reader_coverage(text, tmp_path)

    assert result["status"] == "PASS"
    assert not any(
        item.startswith("reader_internal_control_leak:")
        for item in result["blocking_findings"]
    )
