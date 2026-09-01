from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import scripts.research_calibration as calibration
from scripts.research_calibration import create_publication_snapshot
from scripts.research_monitoring import (
    append_monitoring_events,
    audit_monitoring_output,
    build_monitoring_plan,
    evaluate_threshold,
    generate_monitoring_dashboard,
    monitor_all,
    prepare_monitoring_event,
    record_disclosure_cycle,
    validate_monitoring_event,
    validate_monitoring_plan,
)
from scripts.turtle_agent.tool_registry import ToolRegistry


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _fact(value: float, as_of: str, observation_id: str) -> dict:
    return {
        "observation_id": observation_id, "fact_name": "overall_gross_margin_pct",
        "domain": "operations", "raw_value": str(value), "normalized_value": value,
        "unit": "pct", "basis": "consolidated", "as_of": as_of,
        "doc_id": "DOC:" + as_of, "status": "VERIFIED",
    }


def _snapshot(output: Path, *, threshold_value: float = 14.3, aggregation: str = "single_period") -> dict:
    output.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema_version": "publication-snapshot.v1", "report_id": "01502.HK",
        "published_at": "2025-03-27T00:00:00+00:00", "data_as_of": "2024-12-31",
        "snapshot_fingerprint": "a" * 64,
        "facts": [_fact(14.42, "2024-12-31", "OBS:2024")],
        "thresholds": [{
            "threshold_id": "TH.GM", "metric": "整体毛利率", "fact_name": "overall_gross_margin_pct",
            "fact_basis": "consolidated", "current_value": 14.42, "threshold_value": threshold_value,
            "unit": "pct", "operator": "<", "basis_type": "historical_volatility",
            "basis_description": "仅使用FY2021-FY2024趋势设定", "source_ids": ["annual-2024.pdf"],
            "accounting_definition": "consolidated gross profit/revenue", "observation_frequency": "annual",
            "window": "单一年度披露" if aggregation == "single_period" else "连续两次年度披露",
            "aggregation": aggregation, "seasonal_adjustment": "not_needed",
            "precision": {"justified_decimals": 1, "basis": "年报披露精度"},
            "action": "reassess", "decision_entry_ids": ["D014"],
        }],
        "predictions": [{"prediction_id": "PS:down", "probability": 0.3,
                         "resolution_due": "2026-03-26", "kind": "analyst_subjective"}],
        "decision": {"expected_return_pct": 6.0},
    }
    _write(output / "publication_snapshot.json", snapshot)
    return snapshot


def _source() -> list[dict]:
    return [{"source_id": "annual-2025.pdf", "sha256": "b" * 64,
             "disclosed_at": "2026-03-26", "data_as_of": "2025-12-31"}]


def _common(plan: dict) -> dict:
    return {"report_id": plan["report_id"], "snapshot_fingerprint": plan["snapshot_fingerprint"],
            "observed_at": "2026-03-26", "source_evidence": _source()}


def test_monitoring_plan_freezes_snapshot_bytes_and_threshold_contract(tmp_path: Path) -> None:
    _snapshot(tmp_path)
    plan = build_monitoring_plan(tmp_path)
    assert plan["validation"]["state"] == "MONITORING_READY"
    assert plan["thresholds"][0]["minimum_observations"] == 1
    assert plan["thresholds"][0]["automatic_trade_forbidden"] is True
    snapshot = json.loads((tmp_path / "publication_snapshot.json").read_text(encoding="utf-8"))
    snapshot["thresholds"][0]["threshold_value"] = 13.0
    _write(tmp_path / "publication_snapshot.json", snapshot)
    result = validate_monitoring_plan(plan, output_dir=tmp_path)
    assert "publication_snapshot_bytes_changed" in result["invalid_findings"]


def test_event_rejects_prepublication_source_and_future_data(tmp_path: Path) -> None:
    _snapshot(tmp_path); plan = build_monitoring_plan(tmp_path)
    event = prepare_monitoring_event({**_common(plan), "event_id": "MON:DISC:1", "event_type": "disclosure_observed",
                                      "disclosure_id": "DOC:2025", "data_as_of": "2025-12-31"})
    event["source_evidence"][0]["disclosed_at"] = "2025-03-01"
    event["event_fingerprint"] = "x" * 64
    result = validate_monitoring_event(event, plan)
    assert "source_evidence[0]:not_post_publication" in result["invalid_findings"]


def test_threshold_windows_outliers_and_consecutive_rules() -> None:
    threshold = {"threshold_value": 13.0, "operator": "<", "aggregation": "consecutive_periods", "minimum_observations": 2}
    assert evaluate_threshold(threshold, [{"value": 12.9, "period_end": "2025-06-30"}])["evaluation_status"] == "NOT_DUE"
    assert evaluate_threshold(threshold, [{"value": 12.9, "period_end": "2025-06-30"}, {"value": 12.8, "period_end": "2025-12-31"}])["evaluation_status"] == "TRIGGERED"
    outlier = evaluate_threshold(threshold, [
        {"value": 12.9, "period_end": "2025-06-30"},
        {"value": 12.8, "period_end": "2025-12-31", "outlier": True},
    ])
    assert outlier["evaluation_status"] == "NEEDS_CONFIRMATION"
    rolling = dict(threshold, aggregation="rolling_average", threshold_value=13.5)
    assert evaluate_threshold(rolling, [{"value": 13.0, "period_end": "2025-06-30"}, {"value": 13.2, "period_end": "2025-12-31"}])["aggregate_value"] == 13.1


def test_strict_event_ledger_is_append_only_and_idempotent(tmp_path: Path) -> None:
    _snapshot(tmp_path); plan = build_monitoring_plan(tmp_path)
    event = {**_common(plan), "event_id": "MON:DISC:1", "event_type": "disclosure_observed",
             "disclosure_id": "DOC:2025", "data_as_of": "2025-12-31"}
    assert append_monitoring_events(tmp_path, [event])["written"] is True
    assert append_monitoring_events(tmp_path, [event])["idempotent_count"] == 1
    changed = deepcopy(event); changed["authority"] = "media"
    assert append_monitoring_events(tmp_path, [changed])["error"].startswith("append_only_event_conflict")


def test_real_disclosure_cycle_generates_fact_diff_trigger_and_review_queue(tmp_path: Path) -> None:
    _snapshot(tmp_path, threshold_value=14.3); build_monitoring_plan(tmp_path)
    result = record_disclosure_cycle(
        tmp_path,
        disclosure={"doc_id": "DOC:2025", "source_id": "annual-2025.pdf", "sha256": "b" * 64,
                    "disclosed_at": "2026-03-26", "observed_at": "2026-03-26",
                    "data_as_of": "2025-12-31", "authority": "audited_filing"},
        current_facts=[_fact(14.19, "2025-12-31", "OBS:2025")],
    )
    assert result["written"] is True
    assert result["fact_differences"][0]["classification"] == "NEW_PERIOD_CHANGED"
    assert result["trigger_event_ids"]
    queue = json.loads((tmp_path / "decision_review_queue.json").read_text(encoding="utf-8"))
    assert queue["tasks"][0]["required_action"] == "REASSESS_NOT_TRADE"
    assert result["audit"]["state"] == "INCOMPLETE"


def test_trigger_cannot_trade_and_revision_needs_review(tmp_path: Path) -> None:
    _snapshot(tmp_path); plan = build_monitoring_plan(tmp_path)
    revision = prepare_monitoring_event({**_common(plan), "event_id": "MON:REV:1", "event_type": "decision_revision",
                                         "review_event_id": "MON:REVIEW:missing", "change_reason": "new facts",
                                         "new_action": "avoid", "external_trade_executed": True})
    result = validate_monitoring_event(revision, plan)
    assert "decision_revision_without_approved_review" in result["invalid_findings"]
    assert "monitoring_cannot_execute_external_trade" in result["invalid_findings"]


def test_trigger_review_and_revision_are_append_only_not_automatic_trade(tmp_path: Path) -> None:
    _snapshot(tmp_path, threshold_value=14.3); plan = build_monitoring_plan(tmp_path)
    cycle = record_disclosure_cycle(
        tmp_path,
        disclosure={"doc_id": "DOC:2025", "source_id": "annual-2025.pdf", "sha256": "b" * 64,
                    "disclosed_at": "2026-03-26", "observed_at": "2026-03-26", "data_as_of": "2025-12-31"},
        current_facts=[_fact(14.19, "2025-12-31", "OBS:2025")],
    )
    trigger_id = cycle["trigger_event_ids"][0]
    review = {**_common(plan), "event_id": "MON:REVIEW:1", "event_type": "decision_review",
              "trigger_event_ids": [trigger_id], "conclusion": "CHANGE_PROPOSED",
              "valuation_impact": "base value down 5%", "action_impact": "reduce only after approval"}
    assert append_monitoring_events(tmp_path, [review])["written"] is True
    revision = {**_common(plan), "event_id": "MON:REV:1", "event_type": "decision_revision",
                "review_event_id": "MON:REVIEW:1", "change_reason": "verified margin trigger",
                "new_action": "reduce", "external_trade_executed": False}
    assert append_monitoring_events(tmp_path, [revision])["written"] is True
    audit = audit_monitoring_output(tmp_path)
    assert audit["state"] == "MONITORING"
    assert audit["dashboard"]["decision_calibration"]["revisions"] == 1
    assert audit["dashboard"]["trigger_effectiveness"]["review_coverage_rate"] == 1.0


def test_prediction_dashboard_shows_sample_size_and_uncertainty(tmp_path: Path) -> None:
    _snapshot(tmp_path); plan = build_monitoring_plan(tmp_path)
    event = {**_common(plan), "event_id": "MON:PRED:1", "event_type": "prediction_resolution",
             "prediction_id": "PS:down", "outcome": 1}
    assert append_monitoring_events(tmp_path, [event])["written"] is True
    dashboard = generate_monitoring_dashboard(tmp_path)
    assert dashboard["prediction_calibration"]["resolved_binary_predictions"] == 1
    assert dashboard["prediction_calibration"]["brier_score"] == 0.49
    assert dashboard["prediction_calibration"]["brier_standard_error"] is None
    assert "n<5" in dashboard["prediction_calibration"]["uncertainty_note"]


def test_publication_snapshot_automatically_creates_monitoring_plan_and_freezes_facts(tmp_path: Path) -> None:
    output = tmp_path / "output"; output.mkdir()
    _write(output / "analysis_contract.json", {"ts_code": "TEST.HK", "data_as_of": "2025-12-31"})
    _write(output / "fact_observations.json", {"observations": [_fact(14.19, "2025-12-31", "OBS:2025")]})
    result = create_publication_snapshot(output, "report")
    assert result["written"] is True
    assert result["snapshot"]["facts"][0]["observation_id"] == "OBS:2025"
    assert (output / "monitoring_plan.json").exists()
    assert result["monitoring_plan"]["validation"]["state"] == "MONITORING_READY"


def test_batch_monitor_scan_is_observable_and_tool_is_registered(tmp_path: Path) -> None:
    output = tmp_path / "out"; _snapshot(output); build_monitoring_plan(output)
    summary = monitor_all(tmp_path, as_of="2027-01-01")
    assert summary["outputs_scanned"] == 1
    assert summary["results"][0]["warnings"] >= 1
    assert (tmp_path / ".monitoring_run_summary.json").exists()
    registry = ToolRegistry(); registry.auto_discover("turtle_agent.tools.write_tools")
    assert "append_strict_monitoring_events" in registry.list_tools()


def test_monitoring_schemas_parse() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas"
    for name in ("monitoring_plan.schema.json", "monitoring_event.schema.json", "calibration_dashboard.schema.json"):
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert payload["required"]
