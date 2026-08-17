from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.turtle_agent.run import _validate_pit_production_completion
from turtle_agent.tools import pit_production_write_tools


class _Runner:
    def __init__(self, source_ids: list[str]) -> None:
        self.source_ids = source_ids

    def attestation(self) -> dict:
        return {
            "read_audit": [
                {"allowed": True, "kind": "SOURCE", "source_id": source_id}
                for source_id in self.source_ids
            ],
        }


def test_pit_production_writer_rejects_anchor_for_unread_source(tmp_path: Path) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path,
        code="600340.SH",
        run_id="pit-production-test",
        pit_runner=_Runner(["SSE:2019-ANNUAL", "SSE:2018-ANNUAL"]),
    )
    try:
        with pytest.raises(RuntimeError, match="未在本次运行实际读取"):
            pit_production_write_tools.pit_write_chapter(
                chapter_index=1,
                content="## Ch1\n[source: SSE:UNREAD]",
            )
        assert pit_production_write_tools._validate_source_anchors(
            "[source: SSE:2019-ANNUAL | SSE:2018-ANNUAL] [table-source: SSE:2019-ANNUAL]"
        ) == {"SSE:2018-ANNUAL", "SSE:2019-ANNUAL"}
        with pytest.raises(RuntimeError, match="未在本次运行实际读取"):
            pit_production_write_tools._validate_source_anchors("[table-source: SSE:UNREAD]")
    finally:
        pit_production_write_tools.clear_pit_production_writer()


def test_pit_production_contract_reads_cannot_select_an_output_directory(tmp_path: Path) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path,
        code="600340.SH",
        run_id="pit-production-test",
        pit_runner=_Runner([]),
    )
    try:
        with pytest.raises(RuntimeError, match="does not accept output_dir"):
            pit_production_write_tools.pit_read_report_contract_pack(output_dir="elsewhere")
        with pytest.raises(RuntimeError, match="does not accept template_path"):
            pit_production_write_tools.pit_read_report_contract_pack(template_path="elsewhere")
        assert "output_dir" not in pit_production_write_tools.pit_read_report_contract_pack._tool_meta["parameters"]
        assert "template_path" not in pit_production_write_tools.pit_read_report_contract_pack._tool_meta["parameters"]
        assert "output_dir" not in pit_production_write_tools.pit_read_structured_ledger_contract._tool_meta["parameters"]
    finally:
        pit_production_write_tools.clear_pit_production_writer()


def test_pit_production_writer_attests_anchors_from_final_chapters(tmp_path: Path) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path,
        code="600340.SH",
        run_id="pit-production-test",
        pit_runner=_Runner(["SSE:2019-ANNUAL", "SSE:2018-ANNUAL"]),
    )
    try:
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        (chapters / "_ch01.md").write_text(
            "## Ch1\n[source: SSE:2019-ANNUAL | SSE:2018-ANNUAL]",
            encoding="utf-8",
        )
        assert pit_production_write_tools.production_source_anchor_ids() == [
            "SSE:2018-ANNUAL", "SSE:2019-ANNUAL",
        ]
    finally:
        pit_production_write_tools.clear_pit_production_writer()


def test_pit_v3_prerequisites_refresh_only_after_verified_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path,
        code="600340.SH",
        run_id="pit-production-test",
        pit_runner=_Runner(["SSE:2019-ANNUAL"]),
    )
    try:
        assert pit_production_write_tools._refresh_pit_v3_prerequisites() == {
            "state": "WAITING_FOR_VERIFIED_PIT_FACT"
        }
        (tmp_path / "document_manifest.json").write_text("{}", encoding="utf-8")
        (tmp_path / "fact_observations.json").write_text("{}", encoding="utf-8")
        import scripts.build_report_context as report_context
        import scripts.computation_evidence as calculation_evidence
        import scripts.decisive_question as decisive_question
        import scripts.valuation_routing as valuation_routing

        monkeypatch.setattr(
            report_context, "build_verified_context",
            lambda *args, **kwargs: {"validation": {"state": "REVIEWABLE"}},
        )
        monkeypatch.setattr(
            valuation_routing, "build_company_archetype",
            lambda *args, **kwargs: {"primary_archetype": {"archetype_id": "general_operating"}},
        )
        monkeypatch.setattr(
            valuation_routing, "build_valuation_route",
            lambda *args, **kwargs: {"validation": {"state": "REVIEWABLE"}},
        )
        monkeypatch.setattr(
            decisive_question, "refresh_decisive_question_plan",
            lambda *args, **kwargs: {"plan": {"validation": {"state": "REVIEWABLE"}}},
        )
        monkeypatch.setattr(
            calculation_evidence, "build_calculation_observations",
            lambda *args, **kwargs: {"validation": {"state": "REVIEWABLE"}},
        )

        refreshed = pit_production_write_tools._refresh_pit_v3_prerequisites()
    finally:
        pit_production_write_tools.clear_pit_production_writer()

    assert refreshed == {
        "state": "REFRESHED",
        "official_evidence_state": "REVIEWABLE",
        "valuation_route_state": "REVIEWABLE",
        "decisive_question_state": "REVIEWABLE",
        "calculation_state": "REVIEWABLE",
    }


def test_pit_production_completion_requires_snapshot_and_read_bound_attestation(tmp_path: Path) -> None:
    output = tmp_path / "output"
    report = output / "reports" / "600340_分析报告_v13.md"
    report.parent.mkdir(parents=True)
    report.write_text("# PIT production report\n", encoding="utf-8")
    run_id = "600340.SH_123_456"
    (output / "completion_report.json").write_text(json.dumps({
        "status": "COMPLETE",
        "validators": {"publication_snapshot": {"written": True}},
    }), encoding="utf-8")
    (output / "publication_snapshot.json").write_text(json.dumps({
        "run_id": run_id,
        "completion_status": "COMPLETE",
        "v3_enforced": True,
    }), encoding="utf-8")
    (output / "pit_runner_attestation.json").write_text(json.dumps({
        "execution_mode": "PIT_PRODUCTION_FREEZE",
        "run_id": run_id,
        "writer": {
            "run_id": run_id,
            "final_report_path": str(report.resolve()),
            "source_anchor_ids": ["SSE:2019-ANNUAL"],
            "read_source_ids": ["SSE:2019-ANNUAL"],
        },
    }), encoding="utf-8")

    result = _validate_pit_production_completion(
        output_dir=str(output), report_path=str(report), run_id=run_id,
    )

    assert result["completion_status"] == "COMPLETE"
    assert result["report_path"] == str(report.resolve())


def test_pit_production_completion_rejects_unread_attested_anchor(tmp_path: Path) -> None:
    output = tmp_path / "output"
    report = output / "reports" / "600340_分析报告_v13.md"
    report.parent.mkdir(parents=True)
    report.write_text("# PIT production report\n", encoding="utf-8")
    run_id = "600340.SH_123_456"
    for name, payload in {
        "completion_report.json": {
            "status": "COMPLETE",
            "validators": {"publication_snapshot": {"written": True}},
        },
        "publication_snapshot.json": {
            "run_id": run_id, "completion_status": "COMPLETE", "v3_enforced": True,
        },
        "pit_runner_attestation.json": {
            "execution_mode": "PIT_PRODUCTION_FREEZE", "run_id": run_id,
            "writer": {
                "run_id": run_id, "final_report_path": str(report.resolve()),
                "source_anchor_ids": ["SSE:2019-ANNUAL"], "read_source_ids": [],
            },
        },
    }.items():
        (output / name).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="source anchors outside actual reads"):
        _validate_pit_production_completion(
            output_dir=str(output), report_path=str(report), run_id=run_id,
        )
