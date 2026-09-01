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


def _ready_investment_predecessor(
    *, code: str = "600340.SH", cutoff: str = "2020-04-27",
) -> dict:
    return {
        "schema_version": "company-judgment-predecessor.v2",
        "identity": {"status": "G1J_COMPLETE", "missing_components": []},
        "source": {
            "report_id": code,
            "data_as_of": cutoff,
            "snapshot_fingerprint": "snapshot-fixture",
            "thesis_sha256": "thesis-fixture",
            "thesis_freeze_fingerprint": "freeze-fixture",
            "thesis_validation_state": "DECISION_READY",
            "financial_driver_bridge_sha256": "bridge-fixture",
            "financial_driver_bridge_validation_state": "REVIEWABLE",
            "financial_driver_bridge_embedded_validation_state": "REVIEWABLE",
            "g1j_contract": {
                "thesis_policy_schema_version": "thesis-test-policy.v3",
                "financial_driver_bridge_policy_schema_version": "financial-driver-bridge-policy.v4",
                "thesis_validation_schema_version": "thesis-test-validation.v1",
                "financial_driver_bridge_validation_schema_version": "financial-driver-bridge.v1",
            },
        },
        "central_path": {"path_id": "CP:operating"},
        "forward_judgments": [{"judgment_id": "FJ:operating"}],
        "mechanism_chains": [{"chain_id": "MC:operating"}],
        "rival_hypothesis_pairs": [{"pair_id": "RHP:operating"}],
        "analogy_transfer_cards": [{"card_id": "ATC:operating"}],
        "selection_admission": {"status": "SELECTION_ADMITTED"},
        "financial_driver_bridge": {
            "schema_version": "financial-driver-bridge.v1",
            "report_id": code,
            "as_of": cutoff,
            "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
            "drivers": [{"driver_id": "FDBDRV:operating"}],
            "validation": {"state": "REVIEWABLE"},
        },
    }


def _predecessor_contract_marker(predecessor: dict) -> dict:
    source = predecessor["source"]
    return {
        "completeness_status": "G1J_COMPLETE",
        "missing_components": [],
        "snapshot_fingerprint": source["snapshot_fingerprint"],
        "thesis_sha256": source["thesis_sha256"],
        "thesis_freeze_fingerprint": source["thesis_freeze_fingerprint"],
        "thesis_validation_state": source["thesis_validation_state"],
        "financial_driver_bridge_sha256": source["financial_driver_bridge_sha256"],
        "financial_driver_bridge_validation_state": source[
            "financial_driver_bridge_validation_state"
        ],
        "financial_driver_bridge_embedded_validation_state": source[
            "financial_driver_bridge_embedded_validation_state"
        ],
        "data_as_of": source["data_as_of"],
        "central_path_id": predecessor["central_path"]["path_id"],
        "forward_judgment_ids": ["FJ:operating"],
        "rival_hypothesis_pair_ids": ["RHP:operating"],
        "analogy_transfer_card_ids": ["ATC:operating"],
        "selection_admission_status": "SELECTION_ADMITTED",
    }


def _ready_handoff_receipts(
    *, run_id: str, analysis_purpose: str = "INVESTMENT_DECISION",
) -> dict:
    views = ["RESEARCH_AGENDA", "JUDGMENT_SYNTHESIS"]
    if analysis_purpose == "INVESTMENT_DECISION":
        views.append("INVESTMENT_ENRICHMENT")
    return {
        "schema_version": "pit-judgment-handoff-receipts.v1",
        "run_id": run_id,
        "analysis_purpose": analysis_purpose,
        "prerequisite_refresh_generation": 1,
        "view_generations": {
            "RESEARCH_AGENDA": 0,
            "JUDGMENT_SYNTHESIS": 0,
            "INVESTMENT_ENRICHMENT": 0,
        },
        "receipts": {
            view: {
                "view": view,
                "readiness_state": "READY",
                "prerequisite_refresh_generation": 1,
                "view_generation": 0,
            }
            for view in views
        },
    }


def _write_completion_fixture(
    tmp_path: Path, *, read_source_ids: list[str], run_id: str = "600340.SH_123_456",
) -> tuple[Path, Path]:
    output = tmp_path / "output"
    report = output / "reports" / "600340_分析报告_v13.md"
    report.parent.mkdir(parents=True)
    report.write_text("# PIT production report\n", encoding="utf-8")
    predecessor = _ready_investment_predecessor()
    payloads = {
        "analysis_contract.json": {
            "analysis_purpose": "INVESTMENT_DECISION",
            "ts_code": "600340.SH",
            "data_as_of": "2020-04-27",
            "company_judgment_predecessor": _predecessor_contract_marker(predecessor),
        },
        "company_judgment_predecessor.json": predecessor,
        "pit_judgment_handoff_receipts.json": _ready_handoff_receipts(run_id=run_id),
        "completion_report.json": {
            "status": "COMPLETE",
            "validators": {"publication_snapshot": {"written": True}},
        },
        "publication_snapshot.json": {
            "run_id": run_id,
            "analysis_purpose": "INVESTMENT_DECISION",
            "completion_status": "COMPLETE",
            "v3_enforced": True,
        },
        "pit_runner_attestation.json": {
            "execution_mode": "PIT_PRODUCTION_FREEZE",
            "run_id": run_id,
            "writer": {
                "run_id": run_id,
                "final_report_path": str(report.resolve()),
                "source_anchor_ids": ["SSE:2019-ANNUAL"],
                "read_source_ids": read_source_ids,
            },
        },
    }
    for name, payload in payloads.items():
        (output / name).write_text(json.dumps(payload), encoding="utf-8")
    return output, report


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
        with pytest.raises(RuntimeError, match="does not accept output_dir"):
            pit_production_write_tools.pit_read_judgment_generation_handoff(
                output_dir="elsewhere", view="RESEARCH_AGENDA",
            )
        assert "output_dir" not in pit_production_write_tools.pit_read_report_contract_pack._tool_meta["parameters"]
        assert "template_path" not in pit_production_write_tools.pit_read_report_contract_pack._tool_meta["parameters"]
        assert "output_dir" not in pit_production_write_tools.pit_read_judgment_generation_handoff._tool_meta["parameters"]
        assert "output_dir" not in pit_production_write_tools.pit_read_structured_ledger_contract._tool_meta["parameters"]
    finally:
        pit_production_write_tools.clear_pit_production_writer()


def test_pit_contract_pack_strips_ordinary_research_and_valuation_bypasses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path,
        code="600340.SH",
        run_id="pit-contract-pack",
        pit_runner=_Runner([]),
    )
    try:
        safe_agenda = {"readiness": {"state": "READY_WITH_NO_PRIOR"}}
        safe_enrichment = {"readiness": {"state": "READY"}}

        def polluted_pack(*, output_dir: str, **_: object) -> dict:
            return {
                "ok": True,
                "template": "report_template_v12.md",
                "chapter_indexes": [0],
                "chapters": {
                    "0": {
                        "title": "摘要",
                        "content": "static contract",
                        "char_count": 15,
                        "research_plan": {"future": "FUTURE_UNSAFE_TOKEN"},
                        "decisive_questions": ["FUTURE_UNSAFE_TOKEN"],
                    }
                },
                "research_plan_version": "FUTURE_UNSAFE_TOKEN",
                "insight_research_brief": {"future": "FUTURE_UNSAFE_TOKEN"},
                "decisive_question_plan": {"future": "FUTURE_UNSAFE_TOKEN"},
                "industry_knowledge_context": {"future": "FUTURE_UNSAFE_TOKEN"},
                "valuation_route": {"future": "FUTURE_UNSAFE_TOKEN"},
                "company_judgment_predecessor": {"future": "FUTURE_UNSAFE_TOKEN"},
                "official_evidence": {"state": "REVIEWABLE"},
                "judgment_generation_handoff": {
                    "research_agenda": safe_agenda,
                    "investment_enrichment": safe_enrichment,
                },
            }

        polluted_pack._tool_meta = {  # type: ignore[attr-defined]
            "name": "read_report_contract_pack",
            "description": "",
            "parameters": {
                "output_dir": {"type": "string"},
                "template_path": {"type": "string"},
            },
        }
        monkeypatch.setattr(
            pit_production_write_tools.read_tools,
            "read_report_contract_pack",
            polluted_pack,
        )
        bound = pit_production_write_tools._bind_contract_read("read_report_contract_pack")

        result = bound()

        assert "FUTURE_UNSAFE_TOKEN" not in json.dumps(result)
        assert result["chapters"]["0"] == {
            "title": "摘要", "content": "static contract", "char_count": 15,
        }
        assert set(result["judgment_generation_handoff"]) == {
            "research_agenda", "investment_enrichment",
        }
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

    assert {
        key: refreshed[key] for key in (
            "state", "official_evidence_state", "valuation_route_state",
            "decisive_question_state", "calculation_state",
        )
    } == {
        "state": "REFRESHED",
        "official_evidence_state": "REVIEWABLE",
        "valuation_route_state": "REVIEWABLE",
        "decisive_question_state": "REVIEWABLE",
        "calculation_state": "REVIEWABLE",
    }
    assert set(refreshed["judgment_generation_handoff_state"]) == {
        "research_agenda", "investment_enrichment",
    }


def test_cjo_prerequisite_refresh_surfaces_evidence_only_handoff_as_usable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path,
        code="000651.SZ",
        run_id="cjo-test",
        pit_runner=_Runner(["CNINFO:2025-ANNUAL"]),
        analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )
    try:
        empty_library = tmp_path / "industry"
        empty_library.mkdir()
        monkeypatch.setenv("TURTLE_INDUSTRY_KNOWLEDGE_DIR", str(empty_library))
        for name, payload in {
            "document_manifest.json": {},
            "fact_observations.json": {},
            "analysis_contract.json": {
                "ts_code": "000651.SZ",
                "company_id": "CN:000651",
                "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
                "data_as_of": "2025-12-31",
            },
            "report_context.json": {
                "meta": {"report_id": "000651.SZ"},
                "coverage": {"citable_observation_ids": ["OBS:gree:revenue"]},
                "unresolved_gaps": [],
                "conflicts": [],
                "validation": {"state": "REVIEWABLE"},
            },
            "official_evidence_validation.json": {"state": "REVIEWABLE"},
        }.items():
            (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
        import scripts.build_report_context as report_context

        monkeypatch.setattr(
            report_context, "build_verified_context",
            lambda *args, **kwargs: {"validation": {"state": "REVIEWABLE"}},
        )

        refreshed = pit_production_write_tools._refresh_pit_v3_prerequisites()
    finally:
        pit_production_write_tools.clear_pit_production_writer()

    assert refreshed["state"] == "REFRESHED"
    assert refreshed["decisive_question_state"] == "NO_DECISIVE_PLAN_EVIDENCE_ONLY"
    assert refreshed["judgment_generation_handoff_state"] == "READY_WITH_NO_PRIOR"
    assert refreshed["industry_prior_state"] == "NO_MATCHING_MECHANISM_READY"


def test_cjo_handoff_receipts_require_synthesis_and_refresh_invalidates_old_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path, code="000651.SZ", run_id="cjo-run",
        pit_runner=_Runner([]), analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )
    try:
        pit_production_write_tools._advance_handoff_generation(prerequisite_refresh=True)
        pit_production_write_tools._record_handoff_receipt(
            "RESEARCH_AGENDA", {"readiness": {"state": "READY_WITH_NO_PRIOR"}},
        )
        missing = pit_production_write_tools.validate_pit_handoff_receipts(
            analysis_purpose="COMPANY_JUDGMENT_ONLY", run_id="cjo-run",
        )
        assert missing["state"] == "BLOCKED"
        assert missing["findings"] == ["handoff_receipt_missing:JUDGMENT_SYNTHESIS"]
        monkeypatch.setattr(
            pit_production_write_tools, "_chapter_source_anchor_ids",
            lambda: {"CNINFO:2025-ANNUAL"},
        )
        with pytest.raises(RuntimeError, match="handoff_receipt_missing:JUDGMENT_SYNTHESIS"):
            pit_production_write_tools.pit_assemble_report(company_name="格力电器")

        pit_production_write_tools._record_handoff_receipt(
            "JUDGMENT_SYNTHESIS", {"readiness": {"state": "READY"}},
        )
        assert pit_production_write_tools.validate_pit_handoff_receipts(
            analysis_purpose="COMPANY_JUDGMENT_ONLY", run_id="cjo-run",
        )["state"] == "READY"

        pit_production_write_tools._advance_handoff_generation(prerequisite_refresh=True)
        stale = pit_production_write_tools.validate_pit_handoff_receipts(
            analysis_purpose="COMPANY_JUDGMENT_ONLY", run_id="cjo-run",
        )
        assert stale["state"] == "BLOCKED"
        assert set(stale["findings"]) == {
            "handoff_receipt_stale_after_prerequisite_refresh:RESEARCH_AGENDA",
            "handoff_receipt_stale_after_prerequisite_refresh:JUDGMENT_SYNTHESIS",
        }
    finally:
        pit_production_write_tools.clear_pit_production_writer()


def test_investment_handoff_receipts_require_investment_enrichment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path, code="600340.SH", run_id="investment-run",
        pit_runner=_Runner([]), analysis_purpose="INVESTMENT_DECISION",
    )
    try:
        pit_production_write_tools._advance_handoff_generation(prerequisite_refresh=True)
        for view in ("RESEARCH_AGENDA", "JUDGMENT_SYNTHESIS"):
            pit_production_write_tools._record_handoff_receipt(
                view, {"readiness": {"state": "READY"}},
            )
        validation = pit_production_write_tools.validate_pit_handoff_receipts(
            analysis_purpose="INVESTMENT_DECISION", run_id="investment-run",
        )
        assert validation["state"] == "BLOCKED"
        assert validation["findings"] == [
            "handoff_receipt_missing:INVESTMENT_ENRICHMENT",
        ]
        monkeypatch.setattr(
            pit_production_write_tools, "_chapter_source_anchor_ids",
            lambda: {"SSE:2019-ANNUAL"},
        )
        with pytest.raises(RuntimeError, match="handoff_receipt_missing:INVESTMENT_ENRICHMENT"):
            pit_production_write_tools.pit_assemble_report(company_name="测试公司")
    finally:
        pit_production_write_tools.clear_pit_production_writer()


@pytest.mark.parametrize("tool_name", [
    "write_claim_evidence_ledger",
    "write_financial_driver_bridge",
    "write_thesis_test_ledger",
    "write_insight_ledger",
])
def test_judgment_ledger_write_invalidates_only_synthesis_and_reread_restores_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_name: str,
) -> None:
    pit_production_write_tools.configure_pit_production_writer(
        output_dir=tmp_path / tool_name, code="600340.SH", run_id="investment-run",
        pit_runner=_Runner([]), analysis_purpose="INVESTMENT_DECISION",
    )
    try:
        pit_production_write_tools._advance_handoff_generation(prerequisite_refresh=True)
        for view in (
            "RESEARCH_AGENDA", "JUDGMENT_SYNTHESIS", "INVESTMENT_ENRICHMENT",
        ):
            pit_production_write_tools._record_handoff_receipt(
                view, {"readiness": {"state": "READY"}},
            )

        def fake_write(*, output_dir: str) -> dict:
            return {"written": True, "output_dir": output_dir}

        fake_write._tool_meta = {  # type: ignore[attr-defined]
            "name": tool_name, "description": "", "parameters": {},
        }
        monkeypatch.setattr(pit_production_write_tools.write_tools, tool_name, fake_write)
        bound_write = pit_production_write_tools._bind(tool_name)
        result = bound_write()
        validation = pit_production_write_tools.validate_pit_handoff_receipts(
            analysis_purpose="INVESTMENT_DECISION", run_id="investment-run",
        )

        assert result["pit_handoff_generation"]["view_generations"] == {
            "RESEARCH_AGENDA": 0,
            "JUDGMENT_SYNTHESIS": 1,
            "INVESTMENT_ENRICHMENT": 0,
        }
        assert validation["findings"] == [
            "handoff_receipt_stale_after_view_change:JUDGMENT_SYNTHESIS",
        ]

        pit_production_write_tools._record_handoff_receipt(
            "JUDGMENT_SYNTHESIS", {"readiness": {"state": "READY"}},
        )
        assert pit_production_write_tools.validate_pit_handoff_receipts(
            analysis_purpose="INVESTMENT_DECISION", run_id="investment-run",
        )["state"] == "READY"
    finally:
        pit_production_write_tools.clear_pit_production_writer()


def test_pit_production_completion_requires_snapshot_and_read_bound_attestation(tmp_path: Path) -> None:
    run_id = "600340.SH_123_456"
    output, report = _write_completion_fixture(
        tmp_path, read_source_ids=["SSE:2019-ANNUAL"], run_id=run_id,
    )

    result = _validate_pit_production_completion(
        output_dir=str(output), report_path=str(report), run_id=run_id,
    )

    assert result["completion_status"] == "COMPLETE"
    assert result["report_path"] == str(report.resolve())


@pytest.mark.parametrize(
    "missing_component",
    [
        "forward_judgments",
        "mechanism_chains",
        "rival_hypothesis_pairs",
        "analogy_transfer_cards",
    ],
)
def test_pit_production_completion_rechecks_full_company_judgment_predecessor(
    tmp_path: Path, missing_component: str,
) -> None:
    run_id = "600340.SH_123_456"
    output, report = _write_completion_fixture(
        tmp_path, read_source_ids=["SSE:2019-ANNUAL"], run_id=run_id,
    )
    predecessor_path = output / "company_judgment_predecessor.json"
    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    predecessor.pop(missing_component)
    predecessor_path.write_text(json.dumps(predecessor), encoding="utf-8")

    with pytest.raises(RuntimeError, match="company-judgment predecessor invalid"):
        _validate_pit_production_completion(
            output_dir=str(output), report_path=str(report), run_id=run_id,
        )


@pytest.mark.parametrize(
    "corruption",
    ["missing_map", "missing_view", "wrong_view", "negative_generation", "string_generation"],
)
def test_handoff_receipts_require_explicit_typed_view_generations(
    tmp_path: Path, corruption: str,
) -> None:
    payload = _ready_handoff_receipts(run_id="receipt-run")
    if corruption == "missing_map":
        payload.pop("view_generations")
    elif corruption == "missing_view":
        payload["view_generations"].pop("RESEARCH_AGENDA")
    elif corruption == "wrong_view":
        payload["receipts"]["RESEARCH_AGENDA"]["view"] = "JUDGMENT_SYNTHESIS"
    elif corruption == "negative_generation":
        payload["view_generations"]["RESEARCH_AGENDA"] = -1
    else:
        payload["receipts"]["RESEARCH_AGENDA"]["view_generation"] = "0"
    path = tmp_path / "pit_judgment_handoff_receipts.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    validation = pit_production_write_tools.validate_pit_handoff_receipts(
        output_dir=tmp_path,
        analysis_purpose="INVESTMENT_DECISION",
        run_id="receipt-run",
    )

    assert validation["state"] == "BLOCKED"


def test_pit_production_completion_rejects_unread_attested_anchor(tmp_path: Path) -> None:
    run_id = "600340.SH_123_456"
    output, report = _write_completion_fixture(
        tmp_path, read_source_ids=[], run_id=run_id,
    )

    with pytest.raises(RuntimeError, match="source anchors outside actual reads"):
        _validate_pit_production_completion(
            output_dir=str(output), report_path=str(report), run_id=run_id,
        )


@pytest.mark.parametrize("receipt_failure", ["missing", "stale", "wrong_run"])
def test_pit_production_completion_rejects_missing_stale_or_foreign_handoff_receipts(
    tmp_path: Path, receipt_failure: str,
) -> None:
    run_id = "600340.SH_123_456"
    output, report = _write_completion_fixture(
        tmp_path, read_source_ids=["SSE:2019-ANNUAL"], run_id=run_id,
    )
    receipt_path = output / "pit_judgment_handoff_receipts.json"
    if receipt_failure == "missing":
        receipt_path.unlink()
        expected = "handoff_receipt_schema_invalid"
    else:
        receipts = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt_failure == "stale":
            receipts["receipts"]["JUDGMENT_SYNTHESIS"][
                "prerequisite_refresh_generation"
            ] = 0
            expected = "handoff_receipt_stale_after_prerequisite_refresh:JUDGMENT_SYNTHESIS"
        else:
            receipts["run_id"] = "another-run"
            expected = "handoff_receipt_run_id_mismatch"
        receipt_path.write_text(json.dumps(receipts), encoding="utf-8")

    with pytest.raises(RuntimeError, match=expected):
        _validate_pit_production_completion(
            output_dir=str(output), report_path=str(report), run_id=run_id,
        )
