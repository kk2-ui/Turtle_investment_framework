import json
from pathlib import Path

from scripts.evidence_citation import (
    MIN_EVIDENCE_COVERAGE_RATIO,
    EvidenceRegistry,
    validate_evidence_coverage,
)
from scripts.quality_gate import _check_dps_consistency
from scripts.source_list_builder import build_source_list
from scripts.turtle_agent.tools.write_tools import _extract_sources, _run_quality_checks
from scripts.report_audit import _classify_metric
from scripts.citation_verifier import _collect_gross_margin_candidates, _is_scenario_claim


def _registry(tmp_path: Path) -> EvidenceRegistry:
    for name in (
        "compute_bundle.json", "industry_context.json", "governance.json",
        "segments.json", "2025_年报.md",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    registry = EvidenceRegistry()
    registry.register_from_output_dir(str(tmp_path))
    return registry


def test_compound_anchor_resolves_to_canonical_sources(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    text = (
        "股息率7.68%。[source: compute_ddm factor4.dividend_identity + 2025年报末期股息]\n"
        "同行中位3.32%。[source: get_peer_comparison + Ch7]\n"
        "治理折价成立。[source: governance.json 存款协议 + 自行推导]"
    )

    assert registry.extract_canonical_sources(text) == [
        "2025_年报.md",
        "compute_bundle.json",
        "governance.json",
        "industry_context.json",
        "report_derivation",
        "report_internal",
    ]
    assert registry.validate_anchors(text) == []


def test_industry_context_stem_resolves_to_json_source(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    canonical, unresolved = registry.canonicalize_anchor("industry_context")

    assert canonical == ["industry_context.json"]
    assert unresolved == []


def test_pdf_style_annual_anchor_resolves_to_seeded_markdown_twin(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    canonical, unresolved = registry.canonicalize_anchor("2025_年报.pdf MDA p.10")

    assert canonical == ["2025_年报.md"]
    assert unresolved == []


def test_natural_chinese_annual_anchor_resolves_to_seeded_markdown_twin(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    canonical, unresolved = registry.canonicalize_anchor(
        "2025年年报 GOV p5; p68 关联方存款373.77M; derivation"
    )

    assert canonical == ["2025_年报.md", "report_derivation"]
    assert unresolved == []


def test_semicolon_field_continuations_inherit_the_leading_source(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    canonical, unresolved = registry.canonicalize_anchor(
        "2025_年报.pdf STMT p.86 货币资金1105.5; 应收账款159.9; 存货281.8"
    )
    assert canonical == ["2025_年报.md"]
    assert unresolved == []


def test_semicolon_does_not_hide_unknown_prose_source(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    _, unresolved = registry.canonicalize_anchor(
        "2025_年报.pdf STMT p.86 货币资金1105.5; mysterious_blog"
    )
    assert unresolved == ["mysterious_blog"]


def test_global_benchmark_tool_resolves_to_industry_context(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    canonical, unresolved = registry.canonicalize_anchor("get_global_benchmarks")

    assert canonical == ["industry_context.json"]
    assert unresolved == []


def test_dated_web_domain_is_canonical_public_research(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    canonical, unresolved = registry.canonicalize_anchor(
        "第一财经 格力渠道调整 yicai.com 2025-12-06"
    )

    assert canonical == ["public_market_research"]


def test_named_publication_is_canonical_public_research(tmp_path: Path) -> None:
    registry = EvidenceRegistry()
    registry.register_from_output_dir(str(tmp_path))
    canonical, unresolved = registry.canonicalize_anchor("新浪财经/奥维云网")
    assert canonical == ["public_market_research"]
    assert unresolved == []


def test_verified_structured_evidence_ids_resolve_but_invented_ids_do_not(
    tmp_path: Path,
) -> None:
    (tmp_path / "fact_observations.json").write_text(json.dumps({
        "observations": [
            {"observation_id": "OBS:verified", "status": "VERIFIED"},
            {"observation_id": "OBS:candidate", "status": "CANDIDATE"},
        ]
    }), encoding="utf-8")
    (tmp_path / "calculation_observations.json").write_text(json.dumps({
        "calculations": [
            {"calculation_id": "CALC:verified", "status": "VERIFIED"},
        ]
    }), encoding="utf-8")
    registry = EvidenceRegistry()
    registry.register_from_output_dir(str(tmp_path))

    assert registry.canonicalize_anchor("OBS:verified") == (["OBS:verified"], [])
    assert registry.canonicalize_anchor("CALC:verified") == (["CALC:verified"], [])
    assert registry.canonicalize_anchor("OBS:candidate") == ([], ["OBS:candidate"])
    assert registry.canonicalize_anchor("OBS:invented") == ([], ["OBS:invented"])


def test_source_list_uses_canonical_identities_not_claim_strings(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    text = "结论。[source: compute_gg gg_base=6.2% + Ch12 V_final + 自行推导]"

    source_list = build_source_list(text, registry)

    assert "compute_bundle.json" in source_list
    assert "report_internal" in source_list
    assert "report_derivation" in source_list
    assert "未知来源" not in source_list
    assert "gg_base=6.2%" not in source_list


def test_evidence_coverage_counts_numeric_claim_lines_not_every_number(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    text = "\n".join([
        "收入100M、利润20M、毛利率20%。[source: compute_bundle.json]",
        "DPS 0.145 RMB、股价2.02 HKD、股息率7.68%。[source: compute_ddm]",
    ])

    coverage = validate_evidence_coverage(text, registry)

    assert coverage["number_tokens"] == 6
    assert coverage["number_claims"] == 2
    assert coverage["coverage_ratio"] == 1.0
    assert MIN_EVIDENCE_COVERAGE_RATIO == 0.45
    assert coverage["unknown_sources"] == 0
    assert coverage["status"] == "PASS"


def test_table_level_source_does_not_fail_a_global_anchor_ratio(tmp_path: Path) -> None:
    (tmp_path / "2025_年报.md").write_text("# FY2025", encoding="utf-8")
    table = "\n".join(
        ["| 年度 | 指标 |", "|---|---:|"]
        + [f"| {2015 + idx} | {100 + idx}亿元 |" for idx in range(10)]
        + ["[table-source: 2025_年报.md]"]
    )
    report = (
        "## 投资要点概览\n当前判断。\n"
        + "\n".join(f"## Ch{idx} 标题" for idx in range(1, 15))
        + "\n"
        + table
        + "\n## 来源清单\n"
    )

    coverage = validate_evidence_coverage(report, _registry(tmp_path))
    quality = _run_quality_checks(report, str(tmp_path))

    assert coverage["coverage_ratio"] == 0.1
    assert coverage["status"] == "WARN"
    assert quality["passed"] is True
    assert any("仅诊断" in item for item in quality["warnings"])


def test_historical_dps_series_is_not_a_consistency_failure() -> None:
    text = "DPS序列：FY2023 0.171、FY2024 0.155、FY2025 0.145；当前DPS=0.145。"
    conflict = "当前DPS=0.145；最新DPS=0.200。"

    assert _check_dps_consistency(text) is True
    assert _check_dps_consistency(conflict) is False


def test_footnotes_store_canonical_sources(tmp_path: Path) -> None:
    _registry(tmp_path)
    rendered = _extract_sources(
        "结论。[source: compute_gg gg_base=6.2% + Ch12 + 自行推导]",
        str(tmp_path),
    )

    assert "[source:" not in rendered
    assert "`compute_bundle.json; report_internal; report_derivation`" in rendered
    payload = __import__("json").loads((tmp_path / "_sources.json").read_text(encoding="utf-8"))
    assert payload[0]["canonical_sources"] == [
        "compute_bundle.json", "report_internal", "report_derivation",
    ]


def test_discounted_pbase_keeps_distinct_metric_identity() -> None:
    field, tags = _classify_metric(
        "P_base折价（-25%）",
        "| P_base折价（-25%） | 46.05 | 含25%保护折扣的P_base |",
    )

    assert field == "P_BASE_DISCOUNTED"
    assert "discounted" in tags


def test_protected_pbase_keeps_discounted_metric_identity() -> None:
    field, tags = _classify_metric(
        "P_base(25%保护)",
        "| P_base(25%保护) | 46.1 | +23.5% |",
    )

    assert field == "P_BASE_DISCOUNTED"
    assert "discounted" in tags


def test_unprotected_pbase_keeps_base_metric_identity() -> None:
    field, tags = _classify_metric(
        "P_base(无保护)",
        "| P_base(无保护) | 61.4 | GG=II时公允价 |",
    )

    assert field == "P_BASE"
    assert "undiscounted" in tags


def test_gross_margin_candidates_include_structured_and_quoted_disclosures() -> None:
    data = {
        "segments": [{"gross_margin_pct": 22.6}],
        "highlights": ["整体毛利率 14.19%，同比下降0.23pp"],
    }

    candidates = _collect_gross_margin_candidates(data, "segments.json")

    assert any(value == 22.6 for value, _ in candidates)
    assert any(value == 14.19 for value, _ in candidates)
    assert _is_scenario_claim("若毛利率跌至10%，进入悲观情景") is True
    assert _is_scenario_claim("FY2025毛利率14.19%") is False
