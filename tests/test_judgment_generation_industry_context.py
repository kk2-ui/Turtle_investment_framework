from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_generation_handoff import (
    build_judgment_generation_handoff,
    validate_judgment_generation_handoff,
)
from scripts.turtle_agent.tools import write_tools
from scripts.turtle_agent.tools import phase_tools


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
