from __future__ import annotations

from scripts.audit_rules import _run_programmatic_audits
from scripts.chapter_depth import (
    MIN_EVIDENCE_PER_NUMERIC_CLAIM,
    analyze_chapter_depth,
    depth_requirements,
    detect_data_richness,
    semantic_depth_prompt,
)
from scripts.enhanced_quality_gate import _check_content_efficiency
from scripts.report_prose import normalize_markdown_paragraphs
from scripts.turtle_agent.tools.write_tools import audit_chapter


def _deep_chapter(*, separate_lines: bool = True) -> str:
    paragraphs = []
    for index in range(55):
        paragraphs.append(
            f"如果指标{index}=12.5%，相比基准10.0%提高2.5pp，因此说明经营驱动可验证，"
            f"情景推导与风险判断均有数据支持。[source: compute_bundle.json]"
        )
    separator = "\n\n" if separate_lines else " "
    return "## Ch10 测试\n\n### 结论\n\n### 推导\n\n### 证据与出处\n\n" + separator.join(paragraphs)


def test_source_deepening_profile_raises_traceability_not_prose_quotas() -> None:
    standard = depth_requirements(12, data_rich=True)
    deep = depth_requirements(12, data_rich=True, quality_profile="source_deepening")
    assert deep["min_substantive_chars"] == standard["min_substantive_chars"]
    assert deep["min_analysis_lines"] == standard["min_analysis_lines"]
    assert deep["min_derivation_lines"] == standard["min_derivation_lines"]
    assert deep["min_evidence_anchors"] > standard["min_evidence_anchors"]


def test_depth_is_independent_of_sentence_line_breaks() -> None:
    split = analyze_chapter_depth(_deep_chapter(separate_lines=True), 10)
    joined = analyze_chapter_depth(_deep_chapter(separate_lines=False), 10)

    assert split["status"] == "PASS"
    assert joined["status"] == "PASS"
    assert split["metrics"]["substantive_chars"] == joined["metrics"]["substantive_chars"]


def test_many_short_lines_do_not_fake_depth() -> None:
    shallow = "## Ch1 测试\n\n### A\n\n### B\n\n" + "\n\n".join(
        f"短句{i}。" for i in range(120)
    ) + "\n\n[source: compute_bundle.json]"

    result = analyze_chapter_depth(shallow, 1)

    assert result["status"] == "FAIL"
    assert any(item.startswith("substantive_chars:") for item in result["failures"])
    violations = _run_programmatic_audits(shallow, chapter_index=1)
    assert any(item.rule_code == "P2" for item in violations)


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


def test_audit_chapter_uses_quantitative_identity(tmp_path) -> None:
    content = _deep_chapter(separate_lines=True)[:700] + "\n\n### 证据与出处\n"
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "_ch10.md").write_text(content, encoding="utf-8")

    audit = audit_chapter(str(tmp_path), 10)

    assert any(item["rule"] == "P2" for item in audit["violations"])


def test_generation_prompt_exposes_semantic_contract_without_line_targets() -> None:
    prompt = semantic_depth_prompt()

    assert "实质正文≥800字符" in prompt
    assert "公式/情景/推导≥6条" in prompt
    assert "Markdown 行数无关" in prompt
    assert "2864" not in prompt
    assert f"含单位数字声明行×{MIN_EVIDENCE_PER_NUMERIC_CLAIM:.0%}" in prompt


def test_data_rich_profile_requires_deeper_chapters(tmp_path) -> None:
    for year in range(2020, 2024):
        (tmp_path / f"{year}_年报.md").write_text("primary report", encoding="utf-8")
    for name in ("mda.json", "segments.json", "risks.json", "governance.json"):
        (tmp_path / name).write_text('{"facts": [1]}', encoding="utf-8")

    assert detect_data_richness(str(tmp_path)) is True
    assert detect_data_richness(str(tmp_path / "missing")) is False
    assert depth_requirements(1, data_rich=True)["min_substantive_chars"] == 1200
    assert depth_requirements(10, data_rich=True)["min_substantive_chars"] == 1600
    prompt = semantic_depth_prompt(data_rich=True)
    assert "数据丰富" in prompt
    assert "实质正文≥1200字符" in prompt
    assert "公式/情景/推导≥10条" in prompt
    assert "字符数只设防空壳下限" in prompt


def test_evidence_requirement_scales_with_numeric_claim_density() -> None:
    content = "## Ch9 风险\n\n### A\n\n### B\n\n" + "\n".join(
        f"风险指标{i}=12.5%，因此需要验证。[source: risks.json]" if i < 8
        else f"风险指标{i}=12.5%，因此需要验证。"
        for i in range(48)
    )

    result = analyze_chapter_depth(content, 9)

    assert result["requirements"]["min_evidence_anchors"] >= 12
    assert result["metrics"]["evidence_anchors"] == 8
    assert result["metrics"]["evidence_claim_lines"] == 48
    assert any(item.startswith("evidence_anchors:") for item in result["failures"])
