import json
from pathlib import Path

from judgment_generation_handoff import build_judgment_generation_handoff
from scripts.turtle_agent.run import (
    _initialize_pit_production_output,
    _refresh_report_learning_admissions,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_report_startup_persists_explainable_empty_learning_state(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "ordinary"
    output.mkdir()
    (output / "analysis_contract.json").write_text(
        json.dumps({
            "ts_code": "000651.SZ",
            "analysis_purpose": "INVESTMENT_DECISION",
            "data_as_of": "2025-12-31",
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "TURTLE_JUDGMENT_CONTROL_DB", str(tmp_path / "missing-control-plane.db"),
    )

    result = _refresh_report_learning_admissions(str(output))

    assert result["state"] == "CONTROL_PLANE_UNAVAILABLE"
    assert result["selected_count"] == 0
    contract = _read(output / "analysis_contract.json")
    assert contract["judgment_learning_admissions"] == []
    assert contract["judgment_learning_admission_status"]["state"] == "CONTROL_PLANE_UNAVAILABLE"


def test_pit_startup_refreshes_learning_against_exact_cutoff(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "pit"
    output.mkdir()
    monkeypatch.setenv(
        "TURTLE_JUDGMENT_CONTROL_DB", str(tmp_path / "missing-control-plane.db"),
    )
    cutoff = "2024-04-30T15:00:00+08:00"

    _initialize_pit_production_output(
        output_dir=str(output),
        code="000651.SZ",
        run_id="RUN:PIT:STARTUP",
        cutoff_at=cutoff,
        analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )

    contract = _read(output / "analysis_contract.json")
    assert contract["judgment_learning_admission_status"]["information_cutoff"] == cutoff
    handoff = build_judgment_generation_handoff(output, "RESEARCH_AGENDA")
    assert handoff["identity"]["information_cutoff"] == cutoff
