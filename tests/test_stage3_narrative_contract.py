from __future__ import annotations

from scripts.audit_rules import _run_programmatic_audits
from scripts.chapter_depth import (
    analyze_chapter_depth,
    depth_requirements,
    detect_data_richness,
    semantic_depth_prompt,
)
from scripts.enhanced_quality_gate import _check_content_efficiency
from scripts.report_prose import normalize_markdown_paragraphs
from scripts.turtle_agent.tools.write_tools import audit_chapter, write_chapter


def _deep_chapter(*, separate_lines: bool = True) -> str:
    paragraphs = []
    for index in range(55):
        paragraphs.append(
            f"如果指标{index}=12.5%，相比基准10.0%提高2.5pp，因此说明经营驱动可验证，"
            f"情景推导与风险判断均有数据支持。[source: compute_bundle.json]"
        )
    separator = "\n\n" if separate_lines else " "
    return "## Ch10 测试\n\n### 结论\n\n### 推导\n\n### 证据与出处\n\n" + separator.join(paragraphs)


def test_source_deepening_does_not_create_static_writing_or_citation_quotas() -> None:
    standard = depth_requirements(12, data_rich=True)
    deep = depth_requirements(12, data_rich=True, quality_profile="source_deepening")
    assert deep == standard
    assert deep["min_numeric_claim_lines"] == 0
    assert deep["min_derivation_lines"] == 0
    assert deep["min_evidence_anchors"] == 0


def test_depth_is_independent_of_sentence_line_breaks() -> None:
    split = analyze_chapter_depth(_deep_chapter(separate_lines=True), 10)
    joined = analyze_chapter_depth(_deep_chapter(separate_lines=False), 10)

    assert split["status"] == "PASS"
    assert joined["status"] == "PASS"
    assert split["metrics"]["substantive_chars"] == joined["metrics"]["substantive_chars"]


def test_line_and_number_counts_are_diagnostics_not_quality_gates() -> None:
    shallow = "## Ch1 测试\n\n### A\n\n### B\n\n" + "\n\n".join(
        f"短句{i}。" for i in range(120)
    ) + "\n\n[source: compute_bundle.json]"

    result = analyze_chapter_depth(shallow, 1)

    assert result["status"] == "PASS"
    assert result["metrics"]["analysis_lines"] == 0
    violations = _run_programmatic_audits(shallow, chapter_index=1)
    assert not any(item.rule_code == "P2" for item in violations)


def test_conservative_normalizer_preserves_structures_and_sources() -> None:
    original = """## 标题

第一句说明原因。[source: a.json]

第二句给出结论。[source: b.json]

- 列表不能合并

| 指标 | 值 |
|---|---|
| A | 1 |

GG = 6.2%
"""
    normalized = normalize_markdown_paragraphs(original)

    assert "第一句说明原因。[source: a.json] 第二句给出结论。[source: b.json]" in normalized
    assert "\n\n- 列表不能合并\n\n" in normalized
    assert "| 指标 | 值 |" in normalized
    assert "\n\nGG = 6.2%" in normalized


def test_efficiency_ignores_normal_markdown_blank_lines() -> None:
    report = "\n\n".join(
        ["## 标题"]
        + [f"主题{chr(0x4E00 + i)}具有不同判断。因为证据各异，所以结论成立。" for i in range(30)]
    )
    result = _check_content_efficiency(report)

    assert result["status"] == "PASS"


def test_normalizer_repairs_single_sentence_fragmentation() -> None:
    report = "\n\n".join(["## 标题"] + [f"这是第{i}个短句。" for i in range(30)])
    assert _check_content_efficiency(report)["status"] == "FAIL"
    normalized = normalize_markdown_paragraphs(report)
    assert _check_content_efficiency(normalized)["status"] == "PASS"


def test_audit_chapter_rejects_a_template_shell(tmp_path) -> None:
    content = "## Ch10 测试\n\n### 证据与出处\n\n[source: compute_bundle.json]"
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "_ch10.md").write_text(content, encoding="utf-8")

    audit = audit_chapter(str(tmp_path), 10)

    assert any(item["rule"] == "P2" for item in audit["violations"])


def test_generation_prompt_exposes_semantic_contract_without_line_targets() -> None:
    prompt = semantic_depth_prompt()

    assert "只防止空章和模板壳" in prompt
    assert "不设字数、数字、公式、标题数量或基础引用配额" in prompt
    assert "三个最重要判断" in prompt
    assert "2864" not in prompt
    assert "计数只用于诊断，不改变完成状态" in prompt


def test_data_rich_profile_does_not_reward_longer_chapters(tmp_path) -> None:
    for year in range(2020, 2024):
        (tmp_path / f"{year}_年报.md").write_text("primary report", encoding="utf-8")
    for name in ("mda.json", "segments.json", "risks.json", "governance.json"):
        (tmp_path / name).write_text('{"facts": [1]}', encoding="utf-8")

    assert detect_data_richness(str(tmp_path)) is True
    assert detect_data_richness(str(tmp_path / "missing")) is False
    assert depth_requirements(1, data_rich=True) == depth_requirements(1)
    assert depth_requirements(10, data_rich=True) == depth_requirements(10)
    prompt = semantic_depth_prompt(data_rich=True)
    assert "只使用会改变本章判断的材料" in prompt
    assert "不因文件更多扩大篇幅" in prompt


def test_concise_material_judgment_passes_without_padding() -> None:
    content = """## 核心判断

当前最重要的判断是：渠道恢复改善了订单吸收，但尚未证明单位经济改善。
因为销量回升同时伴随毛利承压，所以基准情景保留经营恢复，不给扩张额外价值。
若后续单位毛利和经营现金同向改善，这一判断才向上翻转。
"""

    result = analyze_chapter_depth(content, 1)

    assert result["status"] == "PASS"
    assert result["metrics"]["numeric_claim_lines"] == 0
    assert result["requirements"]["min_evidence_anchors"] == 0
    assert _run_programmatic_audits(content, chapter_index=1) == []


def test_golden_chapter_is_not_unlocked_by_a_duplicate_anchor() -> None:
    from pathlib import Path

    content = (
        Path(__file__).parents[1]
        / "quality_references/000651_gree_v13/chapters/_ch04.md"
    ).read_text(encoding="utf-8")
    original = analyze_chapter_depth(content, 4)
    duplicated = analyze_chapter_depth(
        content + "\n[source: mda.json key_operations_metrics FY2025]",
        4,
    )

    assert original["status"] == duplicated["status"] == "PASS"
    assert original["failures"] == duplicated["failures"] == []


def test_concise_existing_chapter_is_reused_without_an_800_char_gate(tmp_path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    path = chapters / "_ch01.md"
    existing = """## Ch1 核心判断

当前核心判断是渠道恢复但单位经济仍承压，因此不为扩张增加价值；若毛利与经营现金同时改善再向上翻转。
"""
    path.write_text(existing, encoding="utf-8")

    result = write_chapter(
        output_dir=str(tmp_path),
        chapter_index=1,
        title="核心判断",
        content="## Ch1 核心判断\n\n这段替代文字不应覆盖已经通过的章节。",
    )

    assert result["skipped"] is True
    assert path.read_text(encoding="utf-8") == existing


def test_numeric_traceability_is_diagnostic_and_duplicate_anchors_do_not_unlock() -> None:
    content = "## Ch9 风险\n\n### A\n\n### B\n\n" + "\n".join(
        f"风险指标{i}=12.5%，因此需要验证。[source: risks.json]" if i < 8
        else f"风险指标{i}=12.5%，因此需要验证。"
        for i in range(48)
    )

    result = analyze_chapter_depth(content, 9)

    duplicated = analyze_chapter_depth(
        content + "\n[source: risks.json]\n" * 20,
        9,
    )

    assert result["requirements"]["min_evidence_anchors"] == 0
    assert result["diagnostics"]["recommended_evidence_anchors_for_numeric_claims"] == 12
    assert result["diagnostics"]["numeric_evidence_anchor_shortfall"] == 4
    assert result["metrics"]["evidence_anchors"] == 8
    assert result["metrics"]["evidence_claim_lines"] == 48
    assert result["status"] == duplicated["status"] == "PASS"
    assert result["failures"] == duplicated["failures"] == []
