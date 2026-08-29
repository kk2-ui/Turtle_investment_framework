from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.enterprise_underwriting_episode import (
    compile_golden_report_reader_brief,
    validate_golden_report_reader_brief,
)
from scripts.golden_report_feedback import (
    compile_golden_report_feedback_route,
    route_golden_report_feedback,
    validate_golden_report_review_return,
)


ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "docs/development/research/enterprise_underwriting_episodes"


def _finding(
    finding_id: str,
    classes: list[str],
    *,
    status: str = "OPEN",
    guidance: str = "",
    chapters: list[int] | None = None,
) -> dict:
    item = {
        "finding_id": finding_id,
        "root_cause_classes": classes,
        "materiality": "MATERIAL",
        "affected_claims": ["reset value and earnings-power cross-check"],
        "affected_chapters": chapters if chapters is not None else [12, 14, 0],
        "economic_impact": "Could change permanent-loss protection, value and the buy decision.",
        "missing_facts": ["Replacement cost for customer relationships and operating organization"],
        "prohibited_assumptions": ["Do not add replacement value to EPV."],
        "executable_remediation": ["Repair the reusable acquisition schema before recomputing value."],
        "acceptance_criteria": ["Produce an evidence-backed replacement-value range on the same basis as EPV."],
        "remediation_status": status,
        "acceptance_evidence_refs": ["accepted/replacement_value.json"] if status == "ACCEPTED" else [],
    }
    if guidance:
        item["reader_guidance"] = guidance
    return item


def _review(findings: list[dict]) -> dict:
    return {
        "schema_version": "golden-report-review-return.v1",
        "review_id": "GRR:02669:1",
        "report_id": "02669-Q1",
        "candidate_ref": "reports/02669-Q1.candidate.md",
        "reviewer_id": "independent-investor",
        "reviewed_at": "2026-08-29T10:00:00+08:00",
        "findings": findings,
    }


def test_material_review_return_requires_economic_remediation_contract() -> None:
    review = _review([_finding("F1", ["DATA_COVERAGE", "MODEL"])])
    assert validate_golden_report_review_return(review)["state"] == "REVIEWABLE"

    broken = deepcopy(review)
    broken["findings"][0]["acceptance_criteria"] = []
    validation = validate_golden_report_review_return(broken)
    assert validation["state"] == "INVALID"
    assert "findings[0].acceptance_criteria_missing_or_invalid" in validation["findings"]


def test_upstream_findings_route_to_owners_and_never_to_chapter_rewrite() -> None:
    route = compile_golden_report_feedback_route(_review([
        _finding("F-DATA", ["DATA_COVERAGE", "MODEL"]),
        _finding("F-REASON", ["REASONING", "MODEL"]),
    ]))

    assert route["status"] == "UPSTREAM_REPAIR_REQUIRED"
    assert route["reader_repair"]["repair_targets"] == ()
    assert [item["owner"] for item in route["execution_queue"]] == [
        "ACQUISITION_SCHEMA", "UNDERWRITING_THESIS", "DETERMINISTIC_MODEL",
    ]


def test_open_upstream_work_defers_even_an_unrelated_writing_rewrite() -> None:
    route = compile_golden_report_feedback_route(_review([
        _finding("F-MODEL", ["MODEL"]),
        _finding(
            "F-COPY", ["WRITING"], chapters=[0],
            guidance="将税费后分配金额与已接纳表格保持一致。",
        ),
    ]))

    assert route["status"] == "UPSTREAM_REPAIR_REQUIRED"
    assert route["reader_repair"]["repair_targets"] == ()
    assert set(route["reader_repair"]["deferred_finding_ids"]) == {"F-MODEL", "F-COPY"}


def test_only_pure_writing_or_accepted_economic_conclusion_reaches_reader() -> None:
    route = compile_golden_report_feedback_route(_review([
        _finding(
            "F-COPY", ["WRITING"], chapters=[0],
            guidance="将税费后分配金额改为人民币2.784亿元，并与表格保持一致。",
        ),
        _finding(
            "F-MODEL", ["MODEL"], status="ACCEPTED", chapters=[12, 14, 0],
            guidance="重置价值只与盈利能力价值交叉核验，不相加；正文说明两者共同保护的价格范围。",
        ),
    ]))

    assert route["status"] == "READER_REPAIR_READY"
    assert route["reader_repair"]["repair_targets"] == (0, 12, 14)
    payload = json.dumps(route["reader_repair"]["instructions"], ensure_ascii=False)
    assert "DATA_COVERAGE" not in payload
    assert "acceptance_criteria" not in payload
    assert "economic_impact" not in payload


def test_embedded_completion_feedback_exposes_only_clean_reader_brief() -> None:
    completion = {"golden_report_review_return": _review([
        _finding(
            "F-COPY", ["WRITING"], chapters=[0],
            guidance="统一正文与表格中的税费后分配金额。",
        )
    ])}
    route = route_golden_report_feedback(completion)
    assert route["repair_targets"] == (0,)
    assert route["reader_findings"] == ["F-COPY"]
    assert route["reader_repair_brief"] == [{
        "instruction": "统一正文与表格中的税费后分配金额。",
    }]


def test_reader_guidance_cannot_smuggle_review_taxonomy_into_writer() -> None:
    with pytest.raises(ValueError, match="reader_guidance_contains_control_language"):
        compile_golden_report_feedback_route(_review([
            _finding(
                "F-COPY", ["WRITING"], chapters=[0],
                guidance="把 DATA_COVERAGE 和 PRIMARY_ROUTE_UNKNOWN 写入摘要。",
            )
        ]))


def test_reader_writer_brief_is_episode_and_accepted_conclusions_only() -> None:
    episode = json.loads(
        (EPISODES / "CN600585_20240501_WORKED_CASE_V1.json").read_text(encoding="utf-8")
    )
    brief = compile_golden_report_reader_brief(episode, accepted_conclusions=[{
        "statement": "资产重置价值与盈利能力价值给出相互独立的保护区间。",
        "basis": "两条路线使用同一索取权和货币口径，但不相加。",
        "investor_consequence": "只有两条路线均显示足够折价时，价格才具备安全边际。",
        "source_refs": ["accepted/reset-value.json", "accepted/epv.json"],
    }])

    assert validate_golden_report_reader_brief(brief)["state"] == "REVIEWABLE"
    assert "authority" not in brief
    assert "existing_report_adapter" not in json.dumps(brief, ensure_ascii=False)
    assert "root_cause_classes" not in json.dumps(brief, ensure_ascii=False)


@pytest.mark.parametrize("leak", [
    "DATA_COVERAGE requires a new acquisition pass.",
    "The current route is PRIMARY_ROUTE_UNKNOWN.",
    "Use P_LONG and P_XIRR_FIXED_TERMINAL in the reader page.",
])
def test_reader_writer_boundary_rejects_control_plane_and_model_identity(leak: str) -> None:
    episode = json.loads(
        (EPISODES / "CN600585_20240501_WORKED_CASE_V1.json").read_text(encoding="utf-8")
    )
    with pytest.raises(ValueError, match="golden_report_reader_brief_invalid"):
        compile_golden_report_reader_brief(episode, accepted_conclusions=[{
            "statement": leak,
            "basis": "A valid economic basis.",
            "investor_consequence": "A valid investor consequence.",
            "source_refs": ["accepted/value.json"],
        }])
