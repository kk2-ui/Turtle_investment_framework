from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import scripts.research_calibration as calibration
from scripts.legacy_reference_regression import compare_chapter_sets
from scripts.research_calibration import create_publication_snapshot, record_monitoring_outcomes
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.v3_quality_report import evaluate_expression_efficiency, evaluate_v3_quality


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _snapshot_fixture(output: Path) -> None:
    output.mkdir()
    (output / "primary.json").write_text('{"value": 1}', encoding="utf-8")
    _write_json(output / "analysis_contract.json", {"ts_code": "000001.SZ", "run_id": "run-15", "data_as_of": "2026-06-30"})
    for name in ("decision_ledger_policy.json", "claim_evidence_policy.json", "valuation_model_policy.json", "thesis_test_policy.json"):
        _write_json(output / name, {"enforced": True})
    _write_json(output / "decision_ledger.json", {"entries": [
        {"metric_id": "return.gg.base", "value": 12.0, "status": "active", "source_ids": ["primary.json"]},
        {"metric_id": "return.required", "value": 10.0, "status": "active"},
    ]})
    _write_json(output / "claim_evidence.json", {"claims": [{
        "claim_id": "claim.core", "raw_facts": [{"evidence_id": "fact.primary", "fact": "FY2025 revenue was 100",
        "source_id": "primary.json", "direct_support": True, "basis_match": "exact", "data_as_of": "2025-12-31"}]
    }]})
    _write_json(output / "valuation_model.json", {"synthesis": {"action": "buy", "position_pct": 3, "range_low": 70, "base": 100, "range_high": 120, "chosen_value_per_share": 100}})
    _write_json(output / "thesis_test.json", {
        "probability_sets": [{"set_id": "prob.core", "estimates": [
            {"scenario_id": "primary", "label": "主情景", "kind": "analyst_subjective", "value": 0.6, "interval": [0.5, 0.7], "basis": "工作假设", "source_ids": ["primary.json"], "as_of": "2026-08-02"}
        ]}],
        "thresholds": [{"threshold_id": "th.exit", "metric": "审计意见", "threshold_value": 1, "operator": ">=", "action": "exit", "source_ids": ["primary.json"]}],
    })


def _pit_snapshot_fixture(output: Path) -> tuple[str, str, Path]:
    _snapshot_fixture(output)
    document_id = "DOC:CN-SH:600340:annual_report:2019-12-31:0123456789ab"
    pit_source_id = "SSE:600340:2019-ANNUAL"
    projected = output / "pit_sources" / "SSE_600340_2019-ANNUAL" / "original.pdf"
    projected.parent.mkdir(parents=True)
    projected.write_bytes(b"official pit source")
    _write_json(output / "analysis_contract.json", {
        "ts_code": "600340.SH", "run_id": "pit-run-15", "data_as_of": "2020-04-27",
        "pit_production": {"cutoff_at": "2020-04-27T18:00:00+08:00", "source_access": "PIT_ALLOWLIST_ONLY"},
    })
    _write_json(output / "document_manifest.json", {"documents": [{
        "doc_id": document_id,
        "source_id": pit_source_id,
        "local_path": projected.relative_to(output).as_posix(),
        "acquisition_status": "PIT_LINKED_AFTER_ALLOW_READ",
    }]})
    for filename in ("decision_ledger.json", "claim_evidence.json", "thesis_test.json"):
        payload = json.loads((output / filename).read_text(encoding="utf-8"))

        def replace_sources(value: object) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"source_id", "source_ids"}:
                        value[key] = document_id if key == "source_id" else [document_id]
                    else:
                        replace_sources(item)
            elif isinstance(value, list):
                for item in value:
                    replace_sources(item)

        replace_sources(payload)
        _write_json(output / filename, payload)
    return document_id, pit_source_id, projected


def _ready_states(*args, **kwargs):
    return {name: {"state": "DECISION_READY"} for name in ("decision", "claim_evidence", "valuation", "thesis_test")}


def test_full_text_drop_is_warning_but_unexplained_core_fact_loss_fails(tmp_path: Path) -> None:
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    baseline.mkdir(); candidate.mkdir()
    _write_json(baseline / "core_fact_manifest.json", {"facts": [{
        "fact_id": "fact.revenue", "status": "verified", "identity": "FY2025 revenue",
        "canonical_value": 100, "unit": "亿元", "period": "FY2025", "source_ids": ["annual.pdf"]
    }]})
    result = compare_chapter_sets(candidate, baseline)
    assert result["status"] == "FAIL"
    assert result["core_fact_failures"] == ["fact.revenue:missing_without_sourced_change_reason"]

    _write_json(candidate / "core_fact_changes.json", {"changes": [{
        "fact_id": "fact.revenue", "change_reason": "年报重述", "replacement_source_ids": ["restatement.pdf"]
    }]})
    explained = compare_chapter_sets(candidate, baseline)
    assert explained["core_fact_status"] == "PASS"
    assert explained["status"] == "WARN"  # missing chapters remain diagnostic only


def test_publication_snapshot_requires_ready_frozen_ledgers(tmp_path: Path, monkeypatch) -> None:
    _snapshot_fixture(tmp_path / "out")
    monkeypatch.setattr(calibration, "_ledger_states", lambda *a, **k: {"decision": {"state": "INCOMPLETE"}})
    result = create_publication_snapshot(tmp_path / "out", "report")
    assert result["written"] is False
    assert result["error"] == "publication_snapshot_requires_frozen_ready_ledgers"


def test_legacy_directory_gets_minimal_snapshot_without_v3_gate(tmp_path: Path) -> None:
    output = tmp_path / "legacy"; output.mkdir()
    _write_json(output / "analysis_contract.json", {"ts_code": "000002.SZ"})
    result = create_publication_snapshot(output, "legacy final report")
    assert result["written"] is True
    assert result["snapshot"]["legacy_compatibility"] is True
    assert result["snapshot"]["gate_states"]["decision"] == "SKIP"


def test_publication_snapshot_freezes_visible_information_and_is_immutable(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "out"; _snapshot_fixture(output)
    monkeypatch.setattr(calibration, "_ledger_states", _ready_states)
    first = create_publication_snapshot(output, "final report", published_at="2026-08-02T00:00:00+00:00")
    assert first["written"] is True
    snapshot = first["snapshot"]
    assert snapshot["report_sha256"]
    assert snapshot["predictions"][0]["prediction_id"] == "prob.core:primary"
    assert snapshot["visible_information"][0]["sha256"]
    core = json.loads((output / "core_fact_manifest.json").read_text(encoding="utf-8"))
    assert core["facts"][0]["fact_id"] == "fact.primary"
    assert snapshot["ledger_sha256"]["core_facts"]
    same = create_publication_snapshot(output, "final report", published_at="2026-08-03T00:00:00+00:00")
    assert same["idempotent"] is True
    changed = create_publication_snapshot(output, "silently revised report")
    assert changed["written"] is False
    assert changed["error"] == "published_snapshot_is_immutable"
    assert (output / "publication_snapshot_conflict.json").exists()


def test_pit_publication_snapshot_resolves_document_evidence_to_allow_read_projection(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "out"
    document_id, pit_source_id, projected = _pit_snapshot_fixture(output)
    monkeypatch.setattr(calibration, "_ledger_states", _ready_states)

    result = create_publication_snapshot(output, "PIT final report")

    assert result["written"] is True
    snapshot = result["snapshot"]
    assert snapshot["unresolved_source_ids"] == []
    assert {item["source_id"] for item in snapshot["visible_information"]} == {pit_source_id}
    item = snapshot["visible_information"][0]
    assert item["evidence_source_id"] == document_id
    assert item["document_id"] == document_id
    assert item["source_provenance"] == "PIT_PROJECTED_AFTER_ALLOW_READ"
    assert Path(item["path"]) == projected.resolve()


def test_pit_publication_snapshot_rejects_document_without_allow_read_projection(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "out"
    document_id, _, _ = _pit_snapshot_fixture(output)
    manifest = json.loads((output / "document_manifest.json").read_text(encoding="utf-8"))
    manifest["documents"][0]["acquisition_status"] = "MANUAL_LINK"
    _write_json(output / "document_manifest.json", manifest)
    monkeypatch.setattr(calibration, "_ledger_states", _ready_states)

    result = create_publication_snapshot(output, "PIT final report")

    assert result["written"] is False
    assert result["error"] == "pit_production_snapshot_requires_resolved_document_projections"
    assert result["unresolved_source_ids"] == [document_id]
    assert "document_not_allow_read_projected:" + document_id in result["projection_findings"]
    assert not (output / "publication_snapshot.json").exists()


def test_publication_snapshot_dry_run_validates_without_writing_or_conflicting(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "out"; _snapshot_fixture(output)
    monkeypatch.setattr(calibration, "_ledger_states", _ready_states)
    first = create_publication_snapshot(output, "published report")
    assert first["written"] is True
    existing = (output / "publication_snapshot.json").read_text(encoding="utf-8")

    checked = create_publication_snapshot(output, "new validation report", dry_run=True)

    assert checked["written"] is True
    assert checked["dry_run"] is True
    assert (output / "publication_snapshot.json").read_text(encoding="utf-8") == existing
    assert not (output / "publication_snapshot_conflict.json").exists()


def test_append_only_outcomes_generate_process_prediction_and_decision_calibration(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "out"; _snapshot_fixture(output)
    monkeypatch.setattr(calibration, "_ledger_states", _ready_states)
    assert create_publication_snapshot(output, "final report")["written"]
    events = [
        {"event_id": "pred-1", "event_type": "prediction_resolution", "prediction_id": "prob.core:primary", "outcome": 1, "observed_at": "2027-08-02", "source_ids": ["annual-2027.pdf"]},
        {"event_id": "ret-1", "event_type": "return_observation", "actual_total_return_pct": 8, "max_drawdown_pct": -25, "observed_at": "2027-08-02", "source_ids": ["market.json"]},
        {"event_id": "proc-1", "event_type": "process_observation", "facts_checked": 100, "data_errors": 2, "parameters_checked": 20, "parameter_conflicts": 1, "observed_at": "2027-08-02", "source_ids": ["audit.json"]},
        {"event_id": "trigger-1", "event_type": "trigger_event", "threshold_id": "th.exit", "action_taken_at": "2027-07-02", "observed_at": "2027-07-01", "source_ids": ["notice.pdf"]},
        {"event_id": "flip-1", "event_type": "thesis_action", "hours_after_trigger": 24, "observed_at": "2027-07-02", "source_ids": ["decision.json"]},
    ]
    result = record_monitoring_outcomes(output, events)
    report = result["calibration"]
    assert report["prediction_calibration"]["brier_score"] == 0.16
    assert report["process_calibration"]["data_error_rate"] == 0.02
    assert report["process_calibration"]["parameter_conflict_rate"] == 0.05
    assert report["decision_calibration"]["mean_expected_actual_return_deviation_pct"] == -4.0
    assert report["decision_calibration"]["downside_scenario_coverage_rate"] == 1.0
    assert report["decision_calibration"]["mean_thesis_flip_hours"] == 24.0
    assert report["trigger_effectiveness"]["action_mapping_rate"] == 1.0
    assert record_monitoring_outcomes(output, [events[0]])["accepted_event_ids"] == []
    drifted = dict(events[0], outcome=0)
    assert record_monitoring_outcomes(output, [drifted])["error"].startswith("append_only_event_conflict")


def test_expression_is_diagnostic_and_cannot_compensate_gate_failure(tmp_path: Path) -> None:
    paragraph = "这是一个足够长的分析段落，因为现金流下降意味着核心假设需要重新验证，并明确其对估值和仓位的影响。"
    expression = evaluate_expression_efficiency("\n\n".join([paragraph] * 8))
    assert expression["status"] == "WARN" and expression["blocking"] is False
    report = evaluate_v3_quality(tmp_path, paragraph, gate_results={
        "decision": {"state": "INVALID"}, "claim_evidence": {"state": "DECISION_READY"},
        "valuation": {"state": "DECISION_READY"}, "thesis_test": {"state": "DECISION_READY"},
    })
    assert report["status"] == "INVALID"
    assert report["total_score"] is None


def test_expression_length_check_ignores_markdown_tables_but_detects_prose() -> None:
    table = "\n".join(["| 项目 | 说明 |", "|---|---|"] + [f"| {idx} | " + "数据" * 120 + " |" for idx in range(12)])
    assert evaluate_expression_efficiency(table)["metrics"]["overlong_sentence_count"] == 0
    long_prose = "\n".join(("这个分析句子" * 40) + "。" for _ in range(6))
    result = evaluate_expression_efficiency(long_prose)
    assert result["status"] == "WARN"
    assert result["metrics"]["overlong_sentence_count"] == 6


def test_monitoring_tool_is_discoverable() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")
    assert "record_research_outcomes" in registry.list_tools()


def test_formal_assembly_calls_publication_snapshot_before_publish(tmp_path: Path, monkeypatch) -> None:
    import scripts.report_completion as completion_module
    import scripts.research_calibration as calibration_module
    import scripts.turtle_agent.tools.write_tools as write_tools

    for idx in range(15):
        (tmp_path / f"_ch{idx:02d}.md").write_text(f"## Ch{idx} 测试\n\n正文 [source: source{idx}.json]", encoding="utf-8")
    fake_completion = SimpleNamespace(status="COMPLETE", to_dict=lambda: {
        "status": "COMPLETE", "blocking_findings": [], "warning_findings": [], "validators": {}
    })
    monkeypatch.setattr(completion_module, "evaluate_report_completion", lambda *a, **k: fake_completion)
    monkeypatch.setattr(write_tools, "_run_quality_checks", lambda *a, **k: {"passed": True, "issues": [], "warnings": []})
    monkeypatch.setattr(write_tools, "_render_report_html", lambda *a, **k: None)
    called = {}

    def fake_snapshot(output_dir, report_text, **kwargs):
        called["report_text"] = report_text
        called["validation_report_text"] = kwargs.get("validation_report_text")
        return {"written": True, "path": str(Path(output_dir) / "publication_snapshot.json")}

    monkeypatch.setattr(calibration_module, "create_publication_snapshot", fake_snapshot)
    result = write_tools.assemble_report(str(tmp_path), "测试公司", "000001.SZ")
    assert result["published"] is True
    assert called["report_text"]
    assert "[source:" in called["validation_report_text"]
    assert result["publication_snapshot"]["written"] is True
