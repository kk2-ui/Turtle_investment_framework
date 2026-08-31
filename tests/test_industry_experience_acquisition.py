from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.enterprise_underwriting_episode import validate_enterprise_underwriting_episode
from scripts.industry_experience_acquisition import (
    build_episode_industry_evidence_binding,
    build_industry_evidence_acquisition_receipt,
    compile_industry_evidence_acquisition_plan,
    project_industry_evidence_acquisition_for_handoff,
    validate_industry_evidence_acquisition_plan,
    validate_industry_evidence_acquisition_receipt,
)
from scripts.industry_underwriting_context import compile_industry_underwriting_context
from scripts.turtle_agent.tools import read_tools, write_tools
from turtle_agent.tool_registry import ToolRegistry
from tests import test_enterprise_judgment_core as episode_fixture


ROOT = Path(__file__).resolve().parents[1]
CEMENT_BLOCK = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/04_industry_learning_block.json"
CEMENT_ARENA = ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"


def _context() -> dict:
    return compile_industry_underwriting_context(
        company={
            "company_id": "CN:600585",
            "company_name": "Anhui Conch Cement",
            "cutoff_at": "2018-04-30T23:59:59+08:00",
        },
        industry_learning_blocks=[CEMENT_BLOCK],
        competitive_arena=json.loads(CEMENT_ARENA.read_text(encoding="utf-8")),
    )


def _kind_for_role(source_role: str) -> str:
    return {
        "OFFICIAL_STATISTICS": "GOVERNMENT_STATISTIC",
        "INDUSTRY_ASSOCIATION": "INDUSTRY_ASSOCIATION_RELEASE",
        "REGULATORY_DISCLOSURE": "REGULATORY_NOTICE",
        "COMPETITOR_DISCLOSURE": "COMPETITOR_FILING",
        "SUPPLIER_OR_CUSTOMER_DISCLOSURE": "CUSTOMER_DISCLOSURE",
        "TARGET_COMPANY_DISCLOSURE": "TARGET_COMPANY_FILING",
    }[source_role]


def _completed_task(task: dict, *, outcome: str = "VERIFIED") -> dict:
    source_role = task["required_source_roles"][0]
    observations = []
    if outcome in {"VERIFIED", "CONTRADICTED"}:
        observations = [{
            "observation_id": "IEAO:" + task["task_id"],
            "source_role": source_role,
            "source_kind": _kind_for_role(source_role),
            "source_ref": "SRC:EXTERNAL:" + task["role"],
            "source_url": "https://example.com/" + task["role"].lower(),
            "publisher": "Test public publisher",
            "published_at": "2018-04-01T09:00:00+08:00",
            "available_at": "2018-04-01T09:00:00+08:00",
            "period": "FY2017",
            "locator": "Table 1",
            "metric": "Role-bound industry observation",
            "unit": "index",
            "responsibility_boundary": task["measurement_boundary"],
            "statement": "The reviewed source records the requested role-bound observation.",
            "company_transmission": task["company_transmission_to_verify"],
            "relation": "SUPPORTS" if outcome == "VERIFIED" else "CONTRADICTS",
            "evidence_use": "INDUSTRY_FUTURE_THESIS",
        }]
    return {
        "task_id": task["task_id"],
        "outcome": outcome,
        "research_summary": "Completed the role-bound research attempt.",
        "attempted_source_roles": [source_role],
        "stop_reason": "COMPLETED" if outcome != "UNKNOWN" else "PUBLIC_INFO_UNAVAILABLE",
        "observations": observations,
    }


def test_industry_context_compiles_a_role_bound_agenda_without_teacher_company_text() -> None:
    plan = compile_industry_evidence_acquisition_plan(_context())

    assert validate_industry_evidence_acquisition_plan(plan)["state"] == "REVIEWABLE"
    assert {item["role"] for item in plan["tasks"]} >= {
        "DEMAND", "SUPPLY_COMPETITION", "PRICE_COST", "CUSTOMER_CHANNEL", "COMPANY_TRANSMISSION",
    }
    serialized = json.dumps(plan, ensure_ascii=False)
    assert "Huaxin" not in serialized
    assert "Jidong" not in serialized
    assert "COMPANY_FACT_WITHOUT_TARGET_COMPANY_EVIDENCE" in plan["use_policy"]["cannot_establish"]
    assert all("target-company" in item["company_transmission_to_verify"].lower() or "本公司" in item["company_transmission_to_verify"] for item in plan["tasks"])


def test_receipt_preserves_unknown_and_yields_only_admitted_episode_trace_candidates(tmp_path: Path) -> None:
    plan = compile_industry_evidence_acquisition_plan(_context())
    task_receipts = [
        _completed_task(task, outcome="UNKNOWN" if task["role"] == "COMPANY_TRANSMISSION" else "VERIFIED")
        for task in plan["tasks"]
    ]
    receipt = build_industry_evidence_acquisition_receipt(plan, task_receipts)
    receipt_path = tmp_path / "industry_evidence_acquisition_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

    assert receipt["completion_state"] == "REVIEWABLE"
    assert validate_industry_evidence_acquisition_receipt(receipt, plan)["state"] == "REVIEWABLE"
    binding = build_episode_industry_evidence_binding(
        receipt, plan, receipt_ref=str(receipt_path),
    )
    assert binding["status"] == "READY"
    assert len(binding["evidence_trace_candidates"]) == len(plan["tasks"]) - 1
    assert all("TARGET_COMPANY" not in item["used_for"] for item in binding["evidence_trace_candidates"])
    assert all(
        set(item) == {"evidence_id", "source_ref", "locator", "scope", "used_for"}
        for item in binding["evidence_trace_candidates"]
    )

    episode = episode_fixture._underwriting_episode()
    episode["evidence_trace"].extend(binding["evidence_trace_candidates"])
    episode["existing_object_refs"].append(binding["existing_object_ref"])
    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"


def test_receipt_rejects_after_cutoff_source_and_source_role_mismatch() -> None:
    plan = compile_industry_evidence_acquisition_plan(_context())
    receipt = build_industry_evidence_acquisition_receipt(
        plan, [_completed_task(task) for task in plan["tasks"]],
    )

    after_cutoff = deepcopy(receipt)
    after_cutoff["task_receipts"][0]["observations"][0]["available_at"] = "2018-05-01T09:00:00+08:00"
    after_cutoff_result = validate_industry_evidence_acquisition_receipt(after_cutoff, plan)
    assert after_cutoff_result["state"] == "INVALID"
    assert any(item.endswith("available_at_after_cutoff") for item in after_cutoff_result["findings"])

    wrong_role = deepcopy(receipt)
    wrong_role["task_receipts"][0]["observations"][0]["source_role"] = "TARGET_COMPANY_DISCLOSURE"
    wrong_role["task_receipts"][0]["observations"][0]["source_kind"] = "TARGET_COMPANY_FILING"
    wrong_role_result = validate_industry_evidence_acquisition_receipt(wrong_role, plan)
    assert wrong_role_result["state"] == "INVALID"
    assert any(item.endswith("source_role_not_permitted") for item in wrong_role_result["findings"])

    untracked_source = deepcopy(receipt)
    untracked_source["task_receipts"][0]["observations"][0]["source_ref"] = "untracked-source"
    untracked_source_result = validate_industry_evidence_acquisition_receipt(untracked_source, plan)
    assert untracked_source_result["state"] == "INVALID"
    assert any(item.endswith("source_ref_invalid") for item in untracked_source_result["findings"])


def test_handoff_projection_keeps_task_plan_and_receipt_sources_separate_from_facts() -> None:
    plan = compile_industry_evidence_acquisition_plan(_context())
    receipt = build_industry_evidence_acquisition_receipt(
        plan, [_completed_task(task) for task in plan["tasks"]],
    )

    projection = project_industry_evidence_acquisition_for_handoff(plan, receipt)

    assert projection["receipt_state"] == "REVIEWABLE"
    assert projection["accepted_observations"]
    assert projection["episode_binding"]["status"] == "READY"
    assert all("statement" not in item for item in projection["accepted_observations"])
    assert "COMPANY_FACT_WITHOUT_TARGET_COMPANY_EVIDENCE" in projection["use_policy"]["cannot_establish"]


def test_agent_tools_expose_plan_receipt_and_read_interfaces() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.read_tools")
    registry.auto_discover("turtle_agent.tools.write_tools")

    assert {
        "read_industry_evidence_acquisition",
        "write_industry_evidence_acquisition_plan",
        "write_industry_evidence_acquisition_receipt",
    } <= set(registry.list_tools())


def test_agent_tools_persist_and_read_the_same_role_bound_receipt(tmp_path: Path) -> None:
    context = _context()
    (tmp_path / "industry_underwriting_context.json").write_text(
        json.dumps(context, ensure_ascii=False), encoding="utf-8",
    )

    plan_result = write_tools.write_industry_evidence_acquisition_plan(str(tmp_path))
    assert plan_result["ok"] is True
    plan = json.loads((tmp_path / "industry_evidence_acquisition_plan.json").read_text(encoding="utf-8"))
    receipt_result = write_tools.write_industry_evidence_acquisition_receipt(
        str(tmp_path), [_completed_task(plan["tasks"][0])],
    )
    assert receipt_result["ok"] is True
    assert receipt_result["completion_state"] == "PARTIAL"

    read_result = read_tools.read_industry_evidence_acquisition(str(tmp_path))
    assert read_result["ok"] is True
    assert read_result["receipt_state"] == "PARTIAL"
    assert Path(read_result["episode_binding"]["existing_object_ref"]["ref"]).is_file()
