from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_generation_handoff import (
    build_judgment_generation_handoff,
    validate_judgment_generation_handoff,
)
from scripts.industry_experience_acquisition import (
    build_industry_evidence_acquisition_receipt,
    compile_industry_evidence_acquisition_plan,
)
from scripts.industry_underwriting_context import compile_industry_underwriting_context
from scripts.turtle_agent.tools import write_tools
from scripts.turtle_agent.tools import phase_tools


ROOT = Path(__file__).resolve().parents[1]
CEMENT_BLOCK = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/04_industry_learning_block.json"
CEMENT_ARENA = ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ready_agenda(output: Path, *, pit: bool = False) -> None:
    contract = {
        "ts_code": "02669.HK",
        "company_id": "HK:02669",
        "company_name": "中海物业",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": "2026-08-29T00:00:00+08:00",
    }
    if pit:
        contract["pit_production"] = {
            "cutoff_at": "2026-08-29T00:00:00+08:00",
            "source_access": "PIT_ALLOWLIST_ONLY",
        }
    _write(output / "analysis_contract.json", contract)
    _write(output / "report_context.json", {
        "meta": {"report_id": "02669.HK", "issuer": "中海物业"},
        "coverage": {"citable_observation_ids": ["OBS:02669:industry"]},
        "unresolved_gaps": [],
        "conflicts": [],
        "validation": {"state": "REVIEWABLE"},
    })
    _write(output / "official_evidence_validation.json", {"state": "REVIEWABLE"})


def test_bounded_industry_context_is_consumed_without_becoming_a_gate(tmp_path: Path) -> None:
    _ready_agenda(tmp_path, pit=True)
    result = write_tools.write_industry_underwriting_context(str(tmp_path))

    assert result["ok"] is True
    assert result["context_status"] == "BOUNDED"
    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")
    assert handoff["readiness"]["state"] == "READY"
    assert handoff["projection"]["agenda_mode"] == "INDUSTRY_UNDERWRITING"
    context = handoff["projection"]["industry_underwriting_context"]
    assert context["company_identity"]["company_id"] == "HK:02669"
    assert context["report_use"]["non_blocking"] is True
    assert handoff["readiness"]["empty_states"]["industry_underwriting_context"] == "BOUNDED"
    assert validate_judgment_generation_handoff(handoff, output_dir=tmp_path)["state"] == "READY"


def test_missing_industry_context_preserves_legacy_evidence_only_progress(tmp_path: Path) -> None:
    _ready_agenda(tmp_path)
    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "READY_WITH_NO_PRIOR"
    assert handoff["projection"]["industry_underwriting_context"] == {}
    assert handoff["readiness"]["empty_states"]["industry_underwriting_context"] == "NOT_COMPILED"


def test_wrong_company_context_is_excluded_but_report_research_continues(tmp_path: Path) -> None:
    _ready_agenda(tmp_path, pit=True)
    assert write_tools.write_industry_underwriting_context(str(tmp_path))["ok"] is True
    path = tmp_path / "industry_underwriting_context.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["company_identity"]["company_id"] = "HK:00001"
    _write(path, payload)

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")
    assert handoff["readiness"]["state"] == "READY_WITH_NO_PRIOR"
    assert handoff["projection"]["industry_underwriting_context"] == {}
    assert "industry_underwriting_context_excluded_company_mismatch" in handoff["readiness"]["warnings"]
    assert handoff["readiness"]["empty_states"]["industry_underwriting_context"] == "EXCLUDED_IDENTITY_MISMATCH"


def test_phase_compiler_discovers_the_target_company_industry_block(tmp_path: Path) -> None:
    _write(tmp_path / "analysis_contract.json", {
        "ts_code": "600585.SH",
        "company_id": "CN:600585",
        "company_name": "海螺水泥",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": "2018-04-30T23:59:59+08:00",
        "pit_production": {
            "cutoff_at": "2018-04-30T23:59:59+08:00",
            "source_access": "PIT_ALLOWLIST_ONLY",
        },
    })
    result = phase_tools._compile_report_industry_underwriting_context(
        code="600585.SH",
        output_dir=str(tmp_path),
        discovery_context={
            "meta": {"industry_l1": "材料", "industry_l2": "水泥", "industry_group": "水泥"},
            "comparable_peers": [],
        },
    )

    assert result["status"] in {"READY", "BOUNDED"}
    assert result["industry_learning_block_count"] >= 1
    assert result["representative_peer_count"] >= 1
    assert (tmp_path / "industry_underwriting_context.json").is_file()
    acquisition = phase_tools._compile_report_industry_evidence_acquisition_plan(
        output_dir=str(tmp_path),
    )
    assert acquisition["status"] in {"READY", "BOUNDED"}
    assert (tmp_path / "industry_evidence_acquisition_plan.json").is_file()


def test_external_industry_agenda_reaches_research_handoff_but_not_judgment_synthesis(tmp_path: Path) -> None:
    _write(tmp_path / "analysis_contract.json", {
        "ts_code": "600585.SH",
        "company_id": "CN:600585",
        "company_name": "海螺水泥",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": "2018-04-30T23:59:59+08:00",
        "pit_production": {
            "cutoff_at": "2018-04-30T23:59:59+08:00",
            "source_access": "PIT_ALLOWLIST_ONLY",
        },
    })
    _write(tmp_path / "report_context.json", {
        "meta": {"report_id": "600585.SH", "issuer": "海螺水泥"},
        "coverage": {"citable_observation_ids": []},
        "unresolved_gaps": [],
        "conflicts": [],
        "validation": {"state": "REVIEWABLE"},
    })
    _write(tmp_path / "official_evidence_validation.json", {"state": "REVIEWABLE"})
    context = compile_industry_underwriting_context(
        company={
            "company_id": "CN:600585",
            "company_name": "海螺水泥",
            "cutoff_at": "2018-04-30T23:59:59+08:00",
        },
        industry_learning_blocks=[CEMENT_BLOCK],
        competitive_arena=json.loads(CEMENT_ARENA.read_text(encoding="utf-8")),
    )
    _write(tmp_path / "industry_underwriting_context.json", context)
    plan = compile_industry_evidence_acquisition_plan(context)
    plan["source_context_ref"] = str((tmp_path / "industry_underwriting_context.json").resolve())
    _write(tmp_path / "industry_evidence_acquisition_plan.json", plan)
    task = plan["tasks"][0]
    source_role = task["required_source_roles"][0]
    source_kind = {
        "OFFICIAL_STATISTICS": "GOVERNMENT_STATISTIC",
        "INDUSTRY_ASSOCIATION": "INDUSTRY_ASSOCIATION_RELEASE",
        "REGULATORY_DISCLOSURE": "REGULATORY_NOTICE",
        "COMPETITOR_DISCLOSURE": "COMPETITOR_FILING",
        "SUPPLIER_OR_CUSTOMER_DISCLOSURE": "CUSTOMER_DISCLOSURE",
        "TARGET_COMPANY_DISCLOSURE": "TARGET_COMPANY_FILING",
    }[source_role]
    receipt = build_industry_evidence_acquisition_receipt(plan, [{
        "task_id": task["task_id"],
        "outcome": "VERIFIED",
        "research_summary": "One role-bound source was reviewed.",
        "attempted_source_roles": [source_role],
        "stop_reason": "COMPLETED",
        "observations": [{
            "observation_id": "IEAO:test",
            "source_role": source_role,
            "source_kind": source_kind,
            "source_ref": "SRC:EXTERNAL:TEST",
            "source_url": "https://example.com/source",
            "publisher": "Test publisher",
            "published_at": "2018-04-01T09:00:00+08:00",
            "available_at": "2018-04-01T09:00:00+08:00",
            "period": "FY2017",
            "locator": "Table 1",
            "metric": "Industry driver",
            "unit": "index",
            "responsibility_boundary": task["measurement_boundary"],
            "statement": "The role-bound condition was observed.",
            "company_transmission": task["company_transmission_to_verify"],
            "relation": "SUPPORTS",
            "evidence_use": "INDUSTRY_FUTURE_THESIS",
        }],
    }])
    _write(tmp_path / "industry_evidence_acquisition_receipt.json", receipt)

    agenda = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")
    acquisition = agenda["projection"]["industry_evidence_acquisition"]
    assert acquisition["plan_id"] == plan["plan_id"]
    assert acquisition["receipt_state"] == "PARTIAL"
    assert acquisition["accepted_observations"][0]["source_ref"] == "SRC:EXTERNAL:TEST"
    assert Path(acquisition["episode_binding"]["existing_object_ref"]["ref"]).is_file()
    assert agenda["readiness"]["empty_states"]["industry_evidence_acquisition"] == "RECEIPT_PARTIAL"
    assert any(item["role"] == "INDUSTRY_EVIDENCE_ACQUISITION" for item in agenda["source_refs"])
    assert validate_judgment_generation_handoff(agenda, output_dir=tmp_path)["state"] == "READY"

    synthesis = build_judgment_generation_handoff(tmp_path, "JUDGMENT_SYNTHESIS")
    assert "industry_evidence_acquisition" not in synthesis["projection"]


def test_wrong_company_external_industry_plan_is_excluded_without_blocking_research(tmp_path: Path) -> None:
    _ready_agenda(tmp_path, pit=True)
    assert write_tools.write_industry_underwriting_context(str(tmp_path))["ok"] is True
    context = json.loads((tmp_path / "industry_underwriting_context.json").read_text(encoding="utf-8"))
    plan = compile_industry_evidence_acquisition_plan(context)
    plan["company_identity"]["company_id"] = "HK:00001"
    _write(tmp_path / "industry_evidence_acquisition_plan.json", plan)

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")
    assert handoff["readiness"]["state"] == "READY"
    assert handoff["projection"]["industry_evidence_acquisition"] == {}
    assert handoff["readiness"]["empty_states"]["industry_evidence_acquisition"] == "EXCLUDED_IDENTITY_MISMATCH"
    assert "industry_evidence_acquisition_excluded_company_mismatch" in handoff["readiness"]["warnings"]
