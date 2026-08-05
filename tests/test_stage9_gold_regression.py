from __future__ import annotations

import json
from pathlib import Path

from scripts.research_plan import CHAPTER_RESEARCH_SPECS, build_research_plan, topic_presence
from scripts.legacy_reference_regression import compare_chapter_sets, evaluate_from_config
from scripts.report_completion import evaluate_report_completion
from scripts.turtle_agent.tools.read_tools import read_report_contract_pack


def _chapter_text(idx: int) -> str:
    topics = CHAPTER_RESEARCH_SPECS[idx]["topics"]
    topic_text = "。".join(topic["keywords"][0] for topic in topics)
    rows = "\n".join(
        f"如果指标{i}=12.5%，因此说明{topic_text}存在可验证机制与反证，情景推导=基准+压力。[source: compute_bundle.json]"
        for i in range(35)
    )
    return f"## Ch{idx} 测试\n\n### 结论\n\n### 分析\n\n### 证据与出处\n\n{rows}\n"


def _write_set(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for idx in range(15):
        (directory / f"_ch{idx:02d}.md").write_text(_chapter_text(idx), encoding="utf-8")


def test_research_plan_routes_primary_sections_and_latest_years(tmp_path: Path) -> None:
    (tmp_path / "2024_年报.md").write_text("annual", encoding="utf-8")
    (tmp_path / "2025_年报.md").write_text("annual", encoding="utf-8")

    plan = build_research_plan(str(tmp_path), [6, 8])

    assert plan["chapters"]["6"]["primary_sections"] == ["STMT", "NOTES"]
    assert plan["chapters"]["8"]["primary_sections"] == ["GOV", "NOTES"]
    assert plan["chapters"]["8"]["preferred_fiscal_years"] == [2025, 2024]
    assert any("反证" in item for item in plan["chapters"]["8"]["completion_checklist"])


def test_contract_pack_includes_question_led_research_plan(tmp_path: Path) -> None:
    result = read_report_contract_pack(output_dir=str(tmp_path), chapter_indexes=[8])

    assert result["ok"] is True
    chapter_plan = result["chapters"]["8"]["research_plan"]
    assert chapter_plan["primary_sections"] == ["GOV", "NOTES"]
    assert len(chapter_plan["research_questions"]) >= 4
    assert {item["id"] for item in chapter_plan["reasoning_examples"]} == {
        "causal_chain", "counter_evidence",
    }
    assert all("旧报告" not in item["pattern"] for item in chapter_plan["reasoning_examples"])


def test_topic_presence_uses_stable_topic_identities() -> None:
    presence = topic_presence("董事会正在规划接班，同时员工持股计划约束激励。", 8)

    assert presence["control"] is True
    assert presence["incentive"] is True
    assert presence["related"] is False


def test_legacy_reference_passes_identical_sets_and_warns_on_hard_text_drop(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    candidate = tmp_path / "candidate"
    _write_set(gold)
    _write_set(candidate)

    same = compare_chapter_sets(candidate, gold)
    assert same["status"] == "PASS"

    (candidate / "_ch06.md").write_text("## Ch6 财务表现\n\n资本配置。", encoding="utf-8")
    regressed = compare_chapter_sets(candidate, gold)
    assert regressed["status"] == "WARN"
    assert regressed["failed_chapters"] == []
    assert 6 in regressed["warning_chapters"]


def test_configured_regression_persists_machine_and_human_reports(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    output = tmp_path / "000651_candidate"
    _write_set(gold)
    _write_set(output / "chapters")
    (output / "analysis_contract.json").write_text(
        json.dumps({"ts_code": "000651.SZ"}), encoding="utf-8"
    )
    config = tmp_path / "semantic.json"
    config.write_text(json.dumps({
        "enabled": True,
        "references": {"000651": {"name": "historical reference", "chapter_dir": str(gold)}},
    }), encoding="utf-8")

    result = evaluate_from_config(output, config)

    assert result["status"] == "PASS"
    assert (output / "legacy_reference_regression.json").exists()
    assert "历史参考防退化" in (output / "legacy_reference_regression.md").read_text(encoding="utf-8")


def test_completion_contract_blocks_only_legacy_core_fact_loss(tmp_path: Path, monkeypatch) -> None:
    import scripts.legacy_reference_regression as legacy_reference_regression

    monkeypatch.setattr(
        legacy_reference_regression,
        "evaluate_from_config",
        lambda output_dir: {"status": "FAIL", "core_fact_failures": ["fact.revenue:missing_without_sourced_change_reason"]},
    )

    result = evaluate_report_completion("draft", str(tmp_path))

    assert any("Legacy core facts" in item for item in result.blocking_findings)
    assert result.validators["legacy_reference_regression"]["status"] == "FAIL"
