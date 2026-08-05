#!/usr/bin/env python3
"""Publication-time evidence snapshot and append-only posterior calibration.

The snapshot freezes what was knowable when a report was released.  Later
observations live in a separate ledger, so posterior evaluation never rewrites
the original thesis, probabilities, thresholds or decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEDGER_FILES = {
    "decision": "decision_ledger.json",
    "claim_evidence": "claim_evidence.json",
    "valuation": "valuation_model.json",
    "thesis_test": "thesis_test.json",
    "insight": "insight_ledger.json",
}
ROUTING_CONTEXT_FILES = {
    "company_archetype": "company_archetype.json",
    "valuation_route": "valuation_route.json",
    "decision_compilation": "decision_compilation.json",
    "decision_diff": "decision_diff.json",
    "base_rate_context": "base_rate_context.json",
    "fact_observations": "fact_observations.json",
}
READY_STATES = {"DECISION_READY", "MONITORING"}
POLICY_FILES = (
    "decision_ledger_policy.json", "decision_compiler_policy.json", "claim_evidence_policy.json",
    "valuation_route_policy.json", "valuation_model_policy.json", "thesis_test_policy.json", "insight_policy.json",
    "base_rate_policy.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha_bytes(raw)


def _as_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _source_ids(ledgers: dict[str, dict[str, Any]]) -> set[str]:
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"source_id", "source_ids", "evidence_source_ids", "replacement_source_ids"}:
                    values = item if isinstance(item, list) else [item]
                    found.update(str(source).strip() for source in values if str(source).strip())
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(ledgers)
    return found


def _resolve_source(output: Path, source_id: str) -> Path | None:
    candidate = Path(source_id)
    choices = [candidate] if candidate.is_absolute() else [output / source_id, output / "data" / source_id]
    for path in choices:
        if path.is_file():
            return path
    name = candidate.name
    if not name:
        return None
    matches = [path for path in output.rglob(name) if path.is_file()]
    return sorted(matches, key=lambda item: (len(item.parts), str(item)))[0] if matches else None


def _ledger_states(output: Path, report_text: str) -> dict[str, dict[str, Any]]:
    try:
        from scripts.decision_ledger import evaluate_output_decision_ledger
        from scripts.claim_evidence import evaluate_output_claim_evidence
        from scripts.valuation_model_gate import evaluate_output_valuation_model
        from scripts.thesis_test_gate import evaluate_output_thesis_test
        from scripts.insight_ledger import evaluate_output_insight
    except ModuleNotFoundError:
        from decision_ledger import evaluate_output_decision_ledger
        from claim_evidence import evaluate_output_claim_evidence
        from valuation_model_gate import evaluate_output_valuation_model
        from thesis_test_gate import evaluate_output_thesis_test
        from insight_ledger import evaluate_output_insight
    return {
        "decision": evaluate_output_decision_ledger(output, report_text=report_text, persist=False),
        "claim_evidence": evaluate_output_claim_evidence(output, report_text=report_text, persist=False),
        "valuation": evaluate_output_valuation_model(output, report_text=report_text, persist=False),
        "thesis_test": evaluate_output_thesis_test(output, report_text=report_text, persist=False),
        "insight": evaluate_output_insight(output, report_text=report_text, persist=False),
    }


def _predictions(thesis: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pset in thesis.get("probability_sets") or []:
        if not isinstance(pset, dict):
            continue
        set_id = str(pset.get("set_id") or "")
        for estimate in pset.get("estimates") or []:
            if not isinstance(estimate, dict):
                continue
            scenario_id = str(estimate.get("scenario_id") or "")
            result.append({
                "prediction_id": f"{set_id}:{scenario_id}", "set_id": set_id,
                "scenario_id": scenario_id, "label": estimate.get("label"),
                "kind": estimate.get("kind"), "probability": estimate.get("value"),
                "interval": estimate.get("interval"), "basis": estimate.get("basis"),
                "source_ids": estimate.get("source_ids") or [], "as_of": estimate.get("as_of"),
                "resolution_due": estimate.get("resolution_due") or pset.get("resolution_due"),
            })
    return result


def _decision_summary(decision: dict[str, Any], valuation: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for entry in decision.get("entries") or []:
        if isinstance(entry, dict) and entry.get("status", "active") == "active" and entry.get("metric_id"):
            metrics[str(entry["metric_id"])] = entry.get("value")
    synthesis = valuation.get("synthesis") if isinstance(valuation.get("synthesis"), dict) else {}
    expected = _as_number(metrics.get("return.gg.base"))
    chosen = _as_number(synthesis.get("chosen_value_per_share"))
    low = _as_number(synthesis.get("range_low"))
    downside = ((low / chosen) - 1.0) * 100 if low is not None and chosen not in {None, 0.0} else None
    return {
        "canonical_metrics": metrics,
        "action": synthesis.get("action"), "position_pct": synthesis.get("position_pct"),
        "value_range": {key: synthesis.get(key) for key in ("range_low", "base", "range_high", "chosen_value_per_share")},
        "expected_return_pct": expected,
        "required_return_pct": _as_number(metrics.get("return.required")),
        "downside_scenario_pct": round(downside, 6) if downside is not None else None,
    }


def _core_fact_manifest(claim_ledger: dict[str, Any]) -> dict[str, Any]:
    facts: dict[str, dict[str, Any]] = {}
    for claim in claim_ledger.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for raw in claim.get("raw_facts") or []:
            if not isinstance(raw, dict) or not raw.get("evidence_id"):
                continue
            if not raw.get("direct_support") or raw.get("basis_match") not in {"exact", "compatible"}:
                continue
            fact_id = str(raw["evidence_id"])
            facts[fact_id] = {
                "fact_id": fact_id, "status": "verified", "identity": raw.get("fact"),
                "basis": raw.get("basis_match"), "period": raw.get("data_as_of"),
                "source_ids": [raw.get("source_id")] if raw.get("source_id") else [],
                "claim_ids": [str(claim.get("claim_id"))] if claim.get("claim_id") else [],
            }
    return {"schema_version": "core-fact-manifest.v1", "generated_at": _now(), "facts": list(facts.values())}


def create_publication_snapshot(
    output_dir: str | Path,
    report_text: str,
    *,
    validation_report_text: str | None = None,
    completion: dict[str, Any] | None = None,
    published_at: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    policies = [_load(output / filename) for filename in POLICY_FILES]
    v3_enforced = any(bool(policy.get("enforced")) for policy in policies)
    if v3_enforced:
        states = _ledger_states(output, validation_report_text if validation_report_text is not None else report_text)
        not_ready = {name: value.get("state") for name, value in states.items() if str(value.get("state")) not in READY_STATES}
        if not_ready:
            return {"written": False, "error": "publication_snapshot_requires_frozen_ready_ledgers", "gate_states": not_ready}
    else:
        states = {name: {"state": "SKIP"} for name in LEDGER_FILES}
    ledgers = {name: _load(output / filename) for name, filename in LEDGER_FILES.items() if (output / filename).is_file()}
    ledger_hashes = {
        name: _sha_file(output / filename)
        for name, filename in {**ROUTING_CONTEXT_FILES, **LEDGER_FILES}.items()
        if (output / filename).is_file()
    }
    if v3_enforced:
        core_manifest = _core_fact_manifest(ledgers.get("claim_evidence", {}))
        core_path = output / "core_fact_manifest.json"
        # Before first publication this is a deterministic derivative and may
        # be refreshed.  Once a publication snapshot exists it is immutable.
        if not dry_run and not (output / "publication_snapshot.json").exists():
            core_path.write_text(json.dumps(core_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if core_path.exists():
            ledger_hashes["core_facts"] = _sha_file(core_path)
    source_fingerprints: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for source_id in sorted(_source_ids(ledgers)):
        path = _resolve_source(output, source_id)
        if path is None:
            unresolved.append(source_id)
            continue
        stat = path.stat()
        source_fingerprints.append({
            "source_id": source_id, "path": str(path), "sha256": _sha_file(path),
            "size": stat.st_size, "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        })
    contract = _load(output / "analysis_contract.json")
    thesis = ledgers.get("thesis_test", {})
    try:
        from scripts.research_monitoring import freeze_fact_observations
    except ModuleNotFoundError:
        from research_monitoring import freeze_fact_observations
    snapshot = {
        "schema_version": "publication-snapshot.v1",
        "lifecycle": "MONITORING",
        "v3_enforced": v3_enforced,
        "legacy_compatibility": not v3_enforced,
        "report_id": str(contract.get("ts_code") or contract.get("code") or output.name),
        "run_id": str(contract.get("run_id") or ""),
        "published_at": published_at or _now(),
        "data_as_of": contract.get("data_as_of") or contract.get("analysis_date"),
        "report_sha256": _sha_bytes(report_text.encode("utf-8")),
        "ledger_sha256": ledger_hashes,
        "gate_states": {name: value.get("state") for name, value in states.items()},
        "visible_information": source_fingerprints,
        "unresolved_source_ids": unresolved,
        "predictions": _predictions(thesis),
        "thresholds": thesis.get("thresholds") or [],
        "facts": freeze_fact_observations(output),
        "decision": _decision_summary(ledgers.get("decision", {}), ledgers.get("valuation", {})),
        "completion_status": (completion or {}).get("status"),
    }
    snapshot["snapshot_fingerprint"] = _canonical_hash({key: value for key, value in snapshot.items() if key not in {"published_at", "snapshot_fingerprint"}})
    path = output / "publication_snapshot.json"
    if dry_run:
        return {
            "written": True,
            "dry_run": True,
            "path": str(path),
            "snapshot": snapshot,
        }
    existing = _load(path)
    if existing:
        if existing.get("snapshot_fingerprint") == snapshot["snapshot_fingerprint"]:
            try:
                from scripts.research_monitoring import build_monitoring_plan
            except ModuleNotFoundError:
                from research_monitoring import build_monitoring_plan
            plan = _load(output / "monitoring_plan.json") or build_monitoring_plan(output, existing, persist=True)
            return {"written": True, "idempotent": True, "path": str(path), "snapshot": existing,
                    "monitoring_plan": plan}
        conflict = {
            "schema_version": "publication-snapshot-conflict.v1", "detected_at": _now(),
            "existing_fingerprint": existing.get("snapshot_fingerprint"),
            "attempted_fingerprint": snapshot["snapshot_fingerprint"],
            "report_changed": existing.get("report_sha256") != snapshot.get("report_sha256"),
            "changed_ledgers": sorted(name for name, digest in ledger_hashes.items() if (existing.get("ledger_sha256") or {}).get(name) != digest),
        }
        (output / "publication_snapshot_conflict.json").write_text(json.dumps(conflict, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": False, "error": "published_snapshot_is_immutable", "path": str(path), "conflict": conflict}
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from scripts.research_monitoring import build_monitoring_plan
    except ModuleNotFoundError:
        from research_monitoring import build_monitoring_plan
    plan = build_monitoring_plan(output, snapshot, persist=True)
    return {"written": True, "idempotent": False, "path": str(path), "snapshot": snapshot,
            "monitoring_plan": plan}


def record_monitoring_outcomes(output_dir: str | Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    output = Path(output_dir)
    snapshot = _load(output / "publication_snapshot.json")
    if not snapshot:
        return {"written": False, "error": "publication_snapshot_missing"}
    path = output / "monitoring_ledger.json"
    ledger = _load(path) or {"schema_version": "monitoring-ledger.v1", "report_id": snapshot.get("report_id"), "events": []}
    existing = {str(item.get("event_id")): item for item in ledger.get("events") or [] if isinstance(item, dict)}
    accepted: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            return {"written": False, "error": "event_not_object"}
        event_id = str(event.get("event_id") or "").strip()
        event_type = str(event.get("event_type") or "").strip()
        if not event_id or event_type not in {"prediction_resolution", "trigger_event", "return_observation", "process_observation", "thesis_action"}:
            return {"written": False, "error": f"invalid_event:{event_id or 'missing_id'}"}
        if not str(event.get("observed_at") or "").strip() or not (event.get("source_ids") or []):
            return {"written": False, "error": f"event_requires_observed_at_and_source_ids:{event_id}"}
        old = existing.get(event_id)
        if old is not None:
            if _canonical_hash(old) == _canonical_hash(event):
                continue
            return {"written": False, "error": f"append_only_event_conflict:{event_id}"}
        ledger.setdefault("events", []).append(event)
        existing[event_id] = event
        accepted.append(event_id)
    ledger["updated_at"] = _now()
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    report = generate_calibration_report(output)
    return {"written": True, "path": str(path), "accepted_event_ids": accepted, "calibration": report}


def generate_calibration_report(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    snapshot = _load(output / "publication_snapshot.json")
    ledger = _load(output / "monitoring_ledger.json")
    events = ledger.get("events") or []
    predictions = {item.get("prediction_id"): item for item in snapshot.get("predictions") or []}
    squared_errors: list[float] = []
    for event in events:
        if event.get("event_type") != "prediction_resolution":
            continue
        prediction = predictions.get(event.get("prediction_id"))
        outcome = _as_number(event.get("outcome"))
        probability = _as_number((prediction or {}).get("probability"))
        if outcome in {0.0, 1.0} and probability is not None:
            squared_errors.append((probability - outcome) ** 2)
    returns = [event for event in events if event.get("event_type") == "return_observation"]
    expected = _as_number((snapshot.get("decision") or {}).get("expected_return_pct"))
    return_deviations = []
    downside_results = []
    predicted_downside = _as_number((snapshot.get("decision") or {}).get("downside_scenario_pct"))
    for event in returns:
        actual = _as_number(event.get("actual_total_return_pct"))
        if actual is not None and expected is not None:
            return_deviations.append(actual - expected)
        drawdown = _as_number(event.get("max_drawdown_pct"))
        if drawdown is not None and predicted_downside is not None:
            downside_results.append(drawdown >= predicted_downside)
    process = [event for event in events if event.get("event_type") == "process_observation"]
    facts_checked = sum(_as_number(item.get("facts_checked")) or 0 for item in process)
    data_errors = sum(_as_number(item.get("data_errors")) or 0 for item in process)
    params_checked = sum(_as_number(item.get("parameters_checked")) or 0 for item in process)
    conflicts = sum(_as_number(item.get("parameter_conflicts")) or 0 for item in process)
    triggers = [event for event in events if event.get("event_type") == "trigger_event"]
    actioned = [item for item in triggers if item.get("action_taken_at")]
    thesis_actions = [event for event in events if event.get("event_type") == "thesis_action"]
    flip_hours = [_as_number(item.get("hours_after_trigger")) for item in thesis_actions]
    flip_hours = [item for item in flip_hours if item is not None]
    report = {
        "schema_version": "research-calibration.v1", "generated_at": _now(),
        "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "process_calibration": {
            "data_error_rate": round(data_errors / facts_checked, 6) if facts_checked else None,
            "parameter_conflict_rate": round(conflicts / params_checked, 6) if params_checked else None,
            "facts_checked": facts_checked, "parameters_checked": params_checked,
        },
        "prediction_calibration": {
            "resolved_binary_predictions": len(squared_errors),
            "brier_score": round(sum(squared_errors) / len(squared_errors), 6) if squared_errors else None,
        },
        "trigger_effectiveness": {
            "trigger_events": len(triggers), "action_mapping_rate": round(len(actioned) / len(triggers), 6) if triggers else None,
        },
        "decision_calibration": {
            "return_observations": len(returns),
            "mean_expected_actual_return_deviation_pct": round(sum(return_deviations) / len(return_deviations), 6) if return_deviations else None,
            "downside_scenario_coverage_rate": round(sum(downside_results) / len(downside_results), 6) if downside_results else None,
            "mean_thesis_flip_hours": round(sum(flip_hours) / len(flip_hours), 3) if flip_hours else None,
        },
    }
    (output / "calibration_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Turtle V3 publication snapshot and posterior calibration")
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot"); snapshot.add_argument("--output-dir", required=True); snapshot.add_argument("--report", required=True)
    record = sub.add_parser("record"); record.add_argument("--output-dir", required=True); record.add_argument("--events", required=True)
    report = sub.add_parser("report"); report.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        result = create_publication_snapshot(args.output_dir, Path(args.report).read_text(encoding="utf-8"))
    elif args.command == "record":
        payload = json.loads(Path(args.events).read_text(encoding="utf-8")); result = record_monitoring_outcomes(args.output_dir, payload.get("events") or [])
    else:
        result = generate_calibration_report(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("written", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
