from __future__ import annotations

from pathlib import Path

from scripts.absolute_quality_scorecard import evaluate_absolute_quality
from scripts.report_completion import evaluate_report_completion
from scripts.research_plan import CHAPTER_RESEARCH_SPECS


def _strong_chapter(idx: int) -> str:
    keywords = "、".join(topic["keywords"][0] for topic in CHAPTER_RESEARCH_SPECS[idx]["topics"])
    sections = "、".join(CHAPTER_RESEARCH_SPECS[idx]["sections"])
    body = []
    for number in range(40):
        body.append(
            f"若指标{number}=12.5%低于10.0%阈值，则下调利润与估值判断。[source: 2025_年报.md]"
            f"但替代解释若导致现金流只下降2.0%，则需反证主判断。[source: 2025_年报.md]"
            f"因为{keywords}发生12.5%的变化，因此通过经营机制传导至利润、现金流与估值决策。"
            f"[source: 2025_年报.md]原文覆盖{sections}。"
        )
    return f"## Ch{idx} 测试\n\n### 结论\n\n### 推导\n\n### 风险与反证\n\n### 证据与出处\n\n" + "\n\n".join(body)


def _write_strong_set(output: Path) -> None:
    chapters = output / "chapters"
    chapters.mkdir(parents=True)
    (output / "2025_年报.md").write_text("# 测试年报\n", encoding="utf-8")
    for idx in range(15):
        (chapters / f"_ch{idx:02d}.md").write_text(_strong_chapter(idx), encoding="utf-8")


def test_absolute_scorecard_does_not_need_historical_reference(tmp_path: Path) -> None:
    _write_strong_set(tmp_path)

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["status"] == "PASS"
    assert result["scoring_policy"] == "no_compensating_score"
    assert "average_score" not in result and "grade" not in result


def test_review_diagnostics_do_not_impersonate_hard_contract(tmp_path: Path) -> None:
    _write_strong_set(tmp_path)
    (tmp_path / "chapters" / "_ch14.md").write_text("## Ch14 综合决策\n\n结论。", encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["status"] == "PASS"
    assert result["hard_contract_status"] == "PASS"
    assert result["chapters"][14]["review_flags"]
    assert 14 in result["review_chapters"]


def test_unknown_source_is_a_hard_contract_failure(tmp_path: Path) -> None:
    _write_strong_set(tmp_path)
    chapter = tmp_path / "chapters" / "_ch14.md"
    chapter.write_text(chapter.read_text(encoding="utf-8") + "\n[source: invented_secret_database]\n", encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["status"] == "FAIL"
    assert result["critical_failed_chapters"] == [14]
    assert result["chapters"][14]["hard_failures"]


def test_enforced_research_execution_blocks_missing_primary_reads(tmp_path: Path) -> None:
    import json

    _write_strong_set(tmp_path)
    (tmp_path / "research_execution.json").write_text(json.dumps({
        "version": 1,
        "chapters": {
            "14": {"enforced": True, "missing_sections": ["RISK", "NOTES"]},
        },
    }), encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["status"] == "FAIL"
    assert "required_source_reads_missing:RISK,NOTES" in result["chapters"][14]["hard_failures"]


def test_enforced_run_blocks_missing_execution_entry(tmp_path: Path) -> None:
    import json

    _write_strong_set(tmp_path)
    (tmp_path / "research_execution.json").write_text(json.dumps({
        "version": 2,
        "run_id": "current-run",
        "enforced": True,
        "expected_chapters": [14],
        "chapters": {},
    }), encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["status"] == "FAIL"
    assert result["chapters"][14]["hard_failures"] == ["research_execution_missing"]


def test_complete_execution_entry_satisfies_hard_contract(tmp_path: Path) -> None:
    import json

    _write_strong_set(tmp_path)
    (tmp_path / "research_execution.json").write_text(json.dumps({
        "version": 2,
        "run_id": "current-run",
        "enforced": True,
        "expected_chapters": [14],
        "chapters": {
            "14": {
                "enforced": True,
                "missing_sections": [],
                "fiscal_years": [2024, 2025],
                "tool_counts": {"read_section": 4},
            },
        },
    }), encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["hard_contract_status"] == "PASS"
    assert result["chapters"][14]["hard_failures"] == []


def test_web_plan_requires_search_and_fetched_body(tmp_path: Path) -> None:
    import json

    _write_strong_set(tmp_path)
    (tmp_path / "research_execution.json").write_text(json.dumps({
        "version": 2,
        "run_id": "current-run",
        "enforced": True,
        "expected_chapters": [2],
        "chapters": {
            "2": {
                "enforced": True,
                "missing_sections": [],
                "fiscal_years": [2024, 2025],
                "tool_counts": {"read_section": 2, "web_search": 2, "web_fetch": 0},
            },
        },
    }), encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert "required_web_fetch_missing:0/1" in result["chapters"][2]["hard_failures"]


def test_one_effective_external_attempt_per_required_type_closes_research(tmp_path: Path) -> None:
    import json

    _write_strong_set(tmp_path)
    (tmp_path / "research_execution.json").write_text(json.dumps({
        "version": 3,
        "run_id": "current-run",
        "enforced": True,
        "expected_chapters": [2, 4],
        "chapters": {
            "2": {
                "enforced": True,
                "missing_sections": [],
                "fiscal_years": [2025],
                "required_fiscal_year_count": 1,
                "tool_counts": {"read_section": 2, "web_search": 1, "web_fetch": 1},
                "attempted_unavailable_tools": [],
            },
            "4": {
                "enforced": True,
                "missing_sections": [],
                "fiscal_years": [2025],
                "required_fiscal_year_count": 1,
                "tool_counts": {"read_section": 2, "search_report": 1},
                "attempted_unavailable_tools": [],
            },
        },
    }), encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["chapters"][2]["hard_failures"] == []
    assert result["chapters"][4]["hard_failures"] == []


def test_audited_external_unavailability_is_local_not_a_repeat_quota(tmp_path: Path) -> None:
    import json

    _write_strong_set(tmp_path)
    (tmp_path / "research_execution.json").write_text(json.dumps({
        "version": 3,
        "run_id": "current-run",
        "enforced": True,
        "expected_chapters": [2],
        "chapters": {
            "2": {
                "enforced": True,
                "missing_sections": [],
                "fiscal_years": [2025],
                "required_fiscal_year_count": 1,
                "tool_counts": {"read_section": 2, "web_search": 0, "web_fetch": 0},
                "attempted_unavailable_tools": ["web_search", "web_fetch"],
            },
        },
    }), encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    assert result["chapters"][2]["hard_failures"] == []


def test_keyword_stuffing_does_not_pass_research_questions(tmp_path: Path) -> None:
    _write_strong_set(tmp_path)
    keywords = " ".join(
        keyword
        for topic in CHAPTER_RESEARCH_SPECS[3]["topics"]
        for keyword in topic["keywords"]
    )
    (tmp_path / "chapters" / "_ch03.md").write_text(f"## Ch3\n\n{keywords}", encoding="utf-8")

    result = evaluate_absolute_quality(tmp_path, persist=False)

    chapter = result["chapters"][3]
    assert chapter["status"] == "PASS"
    assert chapter["closure"]["topic_coverage"] == 0
    assert chapter["closure"]["open_topics"]
    assert chapter["review_flags"]


def test_completion_contract_blocks_absolute_hard_failure(tmp_path: Path, monkeypatch) -> None:
    import scripts.absolute_quality_scorecard as scorecard

    monkeypatch.setattr(
        scorecard,
        "evaluate_absolute_quality",
        lambda output_dir: {"status": "FAIL", "failed_chapters": [9]},
    )

    result = evaluate_report_completion("draft", str(tmp_path))

    assert any("Quality hard contract" in item for item in result.blocking_findings)
    assert result.validators["absolute_quality"]["status"] == "FAIL"
