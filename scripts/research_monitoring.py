#!/usr/bin/env python3
"""Strict post-publication monitoring, trigger evaluation and calibration.

The publication snapshot is immutable.  Every later observation is appended to
JSONL and can only propose a decision review; this module never trades and never
rewrites the published thesis, thresholds, cases or decision.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable

try:
    from scripts.evidence_documents import _atomic_write_json
except ModuleNotFoundError:
    from evidence_documents import _atomic_write_json


PLAN_VERSION = "research-monitoring-plan.v2"
EVENT_VERSION = "research-monitoring-event.v2"
VALIDATION_VERSION = "research-monitoring-validation.v2"
DASHBOARD_VERSION = "research-calibration-dashboard.v2"
EVENT_TYPES = {
    "disclosure_observed", "fact_observation", "trigger_evaluation", "trigger_event",
    "prediction_resolution", "decision_review", "decision_revision",
    "return_observation", "process_observation", "thesis_action", "monitoring_failure",
}
FREQUENCY_DAYS = {"continuous": 1, "daily": 1, "monthly": 31, "quarterly": 92,
                  "semiannual": 183, "annual": 366}
LATE_TOLERANCE_DAYS = {"continuous": 1, "daily": 2, "monthly": 10, "quarterly": 45,
                       "semiannual": 60, "annual": 90}
FACT_ALIASES = {
    "整体毛利率": "overall_gross_margin_pct",
    "综合毛利率": "overall_gross_margin_pct",
    "商务物业毛利率": "commercial_property_gross_margin_pct",
    "非商务物业毛利率": "non_commercial_property_gross_margin_pct",
    "在管面积": "managed_area_m_sqm",
    "审计意见异常标志": "audit_opinion_exception_flag",
    "当前股价": "market_price_current",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _day(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _record_fingerprint(record: dict[str, Any], field: str) -> str:
    payload = deepcopy(record)
    payload.pop(field, None)
    payload.pop("recorded_at" if field == "event_fingerprint" else "created_at", None)
    if field == "plan_fingerprint":
        payload.pop("validation", None)
    return _hash(payload)


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.is_file():
        return rows, errors
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            errors.append(f"{path.name}:L{line_no}:invalid_json")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}:L{line_no}:not_object")
            continue
        rows.append(value)
    return rows, errors


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing: dict[str, dict[str, Any]] = {}
        for raw in handle.read().splitlines():
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return {"written": False, "error": "monitoring_event_ledger_corrupt_during_lock"}
            if isinstance(item, dict) and item.get("event_id"):
                existing[str(item["event_id"])] = item
        added: list[str] = []
        for row in rows:
            event_id = str(row.get("event_id") or "")
            old = existing.get(event_id)
            if old:
                if old.get("event_fingerprint") == row.get("event_fingerprint"):
                    continue
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return {"written": False, "error": "append_only_event_conflict:" + event_id}
            handle.seek(0, os.SEEK_END)
            handle.write(_canonical(row) + "\n")
            existing[event_id] = row; added.append(event_id)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"written": True, "accepted_event_ids": added}


def _minimum_observations(threshold: dict[str, Any]) -> int:
    aggregation = str(threshold.get("aggregation") or "single_period")
    window = str(threshold.get("window") or "")
    explicit = threshold.get("minimum_observations")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    match = re.search(r"(?:连续|rolling\s*)([二两三四五六七八九十\d]+)", window, re.I)
    if match:
        token = match.group(1)
        numbers = {"二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
                   "七": 7, "八": 8, "九": 9, "十": 10}
        return int(token) if token.isdigit() else numbers.get(token, 2)
    return 2 if aggregation in {"consecutive_periods", "rolling_average"} else 1


def _fact_name(metric: str) -> str | None:
    for label, name in FACT_ALIASES.items():
        if label in str(metric):
            return name
    return None


def _unit_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "pct" if text in {"%", "pct", "percentage_point", "percentage"} else text


def _source_identity(source: dict[str, Any]) -> str:
    return str(source.get("source_id") or source.get("doc_id") or "")


def freeze_fact_observations(output_dir: str | Path) -> list[dict[str, Any]]:
    payload = _load(Path(output_dir) / "fact_observations.json")
    result = []
    for item in payload.get("observations") or []:
        if not isinstance(item, dict) or item.get("status") != "VERIFIED":
            continue
        result.append({key: deepcopy(item.get(key)) for key in (
            "observation_id", "fact_name", "domain", "raw_value", "normalized_value",
            "unit", "currency", "basis", "as_of", "doc_id", "locator", "status",
        )})
    result.sort(key=lambda item: (str(item.get("fact_name")), str(item.get("as_of")),
                                  str(item.get("observation_id"))))
    return result


def build_monitoring_plan(
    output_dir: str | Path, snapshot: dict[str, Any] | None = None, *, persist: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    snapshot = snapshot or _load(output / "publication_snapshot.json")
    published = _day(snapshot.get("published_at"))
    thresholds = []
    warnings: list[str] = []
    for source in snapshot.get("thresholds") or []:
        if not isinstance(source, dict):
            continue
        frequency = str(source.get("observation_frequency") or "").lower()
        next_due = published + timedelta(days=FREQUENCY_DAYS.get(frequency, 183)) if published else None
        threshold = {
            "threshold_id": source.get("threshold_id"), "metric": source.get("metric"),
            "fact_name": source.get("fact_name") or _fact_name(str(source.get("metric") or "")),
            "fact_basis": source.get("fact_basis") or ("consolidated" if _fact_name(str(source.get("metric") or "")) == "overall_gross_margin_pct" else None),
            "current_value": source.get("current_value"), "threshold_value": source.get("threshold_value"),
            "unit": source.get("unit"), "operator": source.get("operator"),
            "basis_type": source.get("basis_type"), "basis_description": source.get("basis_description"),
            "source_ids": source.get("source_ids") or [], "accounting_definition": source.get("accounting_definition"),
            "observation_frequency": frequency, "window": source.get("window"),
            "aggregation": source.get("aggregation"), "minimum_observations": _minimum_observations(source),
            "seasonal_adjustment": source.get("seasonal_adjustment"), "precision": source.get("precision"),
            "hysteresis": source.get("hysteresis"), "outlier_policy": source.get("outlier_policy") or "require_confirmation",
            "action_after_review": source.get("action"), "decision_entry_ids": source.get("decision_entry_ids") or [],
            "next_due": next_due.isoformat() if next_due else None,
            "late_data_tolerance_days": LATE_TOLERANCE_DAYS.get(frequency, 60),
            "automatic_trade_forbidden": True,
        }
        threshold["threshold_fingerprint"] = _hash(threshold)
        if not threshold["fact_name"]:
            warnings.append("threshold_fact_mapping_missing:" + str(threshold.get("threshold_id")))
        if threshold["hysteresis"] is None and frequency in {"continuous", "daily"}:
            warnings.append("high_frequency_threshold_hysteresis_missing:" + str(threshold.get("threshold_id")))
        thresholds.append(threshold)
    predictions = []
    for source in snapshot.get("predictions") or []:
        if not isinstance(source, dict):
            continue
        item = {key: deepcopy(source.get(key)) for key in (
            "prediction_id", "set_id", "scenario_id", "label", "kind", "probability",
            "interval", "as_of", "resolution_due", "source_ids",
        )}
        if not item.get("resolution_due"):
            warnings.append("prediction_resolution_due_missing:" + str(item.get("prediction_id")))
        predictions.append(item)
    snapshot_path = output / "publication_snapshot.json"
    try:
        from scripts.base_rate_case_library import case_monitoring_tasks
    except ModuleNotFoundError:
        from base_rate_case_library import case_monitoring_tasks
    case_tasks = case_monitoring_tasks(str(snapshot.get("report_id") or ""))
    warnings.extend("case_capture_review_pending:" + str(item.get("case_id")) for item in case_tasks
                    if item.get("state") == "CANDIDATE")
    payload = {
        "schema_version": PLAN_VERSION, "created_at": _now(),
        "report_id": snapshot.get("report_id"), "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "snapshot_file_sha256": _file_hash(snapshot_path) if snapshot_path.is_file() else _hash(snapshot),
        "published_at": snapshot.get("published_at"), "data_as_of": snapshot.get("data_as_of"),
        "thresholds": thresholds, "predictions": predictions,
        "case_review_tasks": case_tasks,
        "policy": {
            "append_only_events": True, "post_publication_evidence_only": True,
            "exact_unit_and_accounting_match": True, "trigger_requires_decision_review": True,
            "automatic_trade_forbidden": True, "short_term_return_is_not_research_quality": True,
        },
        "warnings": list(dict.fromkeys(warnings)),
    }
    payload["plan_fingerprint"] = _record_fingerprint(payload, "plan_fingerprint")
    payload["validation"] = validate_monitoring_plan(payload, output_dir=output if snapshot_path.is_file() else None)
    if persist:
        _atomic_write_json(output / "monitoring_plan.json", payload)
        _atomic_write_json(output / "monitoring_validation.json", payload["validation"])
    return payload


def validate_monitoring_plan(payload: dict[str, Any], *, output_dir: str | Path | None = None) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings = list(payload.get("warnings") or [])
    if payload.get("schema_version") != PLAN_VERSION:
        invalid.append("schema_version_invalid")
    if not str(payload.get("report_id") or ""):
        invalid.append("report_id_missing")
    if payload.get("plan_fingerprint") != _record_fingerprint(payload, "plan_fingerprint"):
        invalid.append("plan_fingerprint_mismatch")
    if output_dir is not None:
        path = Path(output_dir) / "publication_snapshot.json"
        snapshot = _load(path)
        if not snapshot:
            incomplete.append("publication_snapshot_missing")
        else:
            if snapshot.get("snapshot_fingerprint") != payload.get("snapshot_fingerprint"):
                invalid.append("publication_snapshot_fingerprint_changed")
            if _file_hash(path) != payload.get("snapshot_file_sha256"):
                invalid.append("publication_snapshot_bytes_changed")
    ids: set[str] = set()
    for index, threshold in enumerate(payload.get("thresholds") or []):
        prefix = f"thresholds[{index}]"
        if not isinstance(threshold, dict):
            invalid.append(prefix + ":not_object"); continue
        tid = str(threshold.get("threshold_id") or "")
        if not tid or tid in ids:
            invalid.append(prefix + ":identity_invalid_or_duplicate")
        ids.add(tid)
        if threshold.get("threshold_fingerprint") != _hash({k: v for k, v in threshold.items() if k != "threshold_fingerprint"}):
            invalid.append(tid + ":threshold_fingerprint_mismatch")
        for field in ("metric", "unit", "operator", "accounting_definition", "window", "aggregation", "basis_description"):
            if not str(threshold.get(field) or "").strip():
                incomplete.append(tid + ":" + field + "_missing")
        if _number(threshold.get("threshold_value")) is None:
            invalid.append(tid + ":threshold_value_invalid")
        if int(threshold.get("minimum_observations") or 0) < 1:
            invalid.append(tid + ":minimum_observations_invalid")
        if not isinstance(threshold.get("late_data_tolerance_days"), int) or int(threshold.get("late_data_tolerance_days") or 0) < 0:
            incomplete.append(tid + ":late_data_tolerance_days_missing_or_invalid")
        if threshold.get("automatic_trade_forbidden") is not True:
            invalid.append(tid + ":automatic_trade_must_be_forbidden")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "MONITORING_READY"
    return {"schema_version": VALIDATION_VERSION, "state": state,
            "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
            "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings}


def prepare_monitoring_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(event)
    payload.setdefault("schema_version", EVENT_VERSION)
    payload.setdefault("recorded_at", _now())
    payload["event_fingerprint"] = _record_fingerprint(payload, "event_fingerprint")
    return payload


def _event_map(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("event_id")): item for item in events if isinstance(item, dict) and item.get("event_id")}


def validate_monitoring_event(
    event: dict[str, Any], plan: dict[str, Any], *, existing_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    existing_events = existing_events or []
    known = _event_map(existing_events)
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    event_id = str(event.get("event_id") or "")
    event_type = str(event.get("event_type") or "")
    if event.get("schema_version") != EVENT_VERSION:
        invalid.append("schema_version_invalid")
    if not event_id.startswith("MON:"):
        invalid.append("event_id_invalid")
    if event_type not in EVENT_TYPES:
        invalid.append("event_type_invalid")
    if event.get("report_id") != plan.get("report_id"):
        invalid.append("report_id_mismatch")
    if event.get("snapshot_fingerprint") != plan.get("snapshot_fingerprint"):
        invalid.append("snapshot_fingerprint_mismatch")
    observed = _day(event.get("observed_at")); published = _day(plan.get("published_at"))
    if observed is None:
        invalid.append("observed_at_invalid")
    elif published is not None and observed <= published:
        invalid.append("event_not_after_publication")
    sources = event.get("source_evidence")
    if not isinstance(sources, list) or not sources:
        incomplete.append("source_evidence_missing"); sources = []
    for index, source in enumerate(sources):
        prefix = f"source_evidence[{index}]"
        if not isinstance(source, dict) or not _source_identity(source) or len(str((source or {}).get("sha256") or "")) != 64:
            invalid.append(prefix + ":identity_or_hash_invalid"); continue
        disclosed = _day(source.get("disclosed_at"))
        if disclosed is None:
            incomplete.append(prefix + ":disclosed_at_missing")
        elif published is not None and disclosed <= published and event_type != "process_observation":
            invalid.append(prefix + ":not_post_publication")
        if observed is not None and disclosed is not None and disclosed > observed:
            invalid.append(prefix + ":source_disclosed_after_observation")
        data_as_of = _day(source.get("data_as_of"))
        if observed is not None and data_as_of is not None and data_as_of > observed:
            invalid.append(prefix + ":future_data")
    threshold_map = {str(item.get("threshold_id")): item for item in plan.get("thresholds") or [] if isinstance(item, dict)}
    prediction_map = {str(item.get("prediction_id")): item for item in plan.get("predictions") or [] if isinstance(item, dict)}
    if event_type == "disclosure_observed":
        if not str(event.get("disclosure_id") or "") or _day(event.get("data_as_of")) is None:
            incomplete.append("disclosure_identity_or_data_as_of_missing")
    elif event_type == "fact_observation":
        if str(event.get("disclosure_event_id") or "") not in known:
            invalid.append("fact_disclosure_event_missing")
        if not str(event.get("fact_name") or "") or not str(event.get("unit") or ""):
            incomplete.append("fact_identity_or_unit_missing")
        if _number(event.get("normalized_value")) is None and not str(event.get("raw_value") or ""):
            incomplete.append("fact_value_missing")
    elif event_type == "trigger_evaluation":
        threshold = threshold_map.get(str(event.get("threshold_id") or ""))
        if threshold is None:
            invalid.append("unknown_threshold_id")
        else:
            if str(event.get("unit") or "") != str(threshold.get("unit") or ""):
                invalid.append("threshold_unit_mismatch")
            if str(event.get("accounting_definition") or "") != str(threshold.get("accounting_definition") or ""):
                invalid.append("threshold_accounting_definition_mismatch")
            for observation in event.get("observations") or []:
                source_event = known.get(str((observation or {}).get("source_event_id") or ""))
                if not source_event or source_event.get("event_type") != "fact_observation":
                    invalid.append("trigger_observation_source_event_missing")
                    continue
                if _unit_key(source_event.get("unit")) != _unit_key(threshold.get("unit")):
                    invalid.append("trigger_observation_unit_mismatch")
                expected_basis = str(threshold.get("fact_basis") or "")
                if expected_basis and str(source_event.get("basis") or "") != expected_basis:
                    invalid.append("trigger_observation_basis_mismatch")
            recomputed = evaluate_threshold(threshold, event.get("observations") or [])
            if event.get("evaluation_status") != recomputed.get("evaluation_status"):
                invalid.append("trigger_evaluation_status_mismatch")
            if event.get("evaluation_fingerprint") != recomputed.get("evaluation_fingerprint"):
                invalid.append("trigger_evaluation_fingerprint_mismatch")
    elif event_type == "trigger_event":
        evaluation = known.get(str(event.get("evaluation_event_id") or ""))
        if not evaluation or evaluation.get("event_type") != "trigger_evaluation" or evaluation.get("evaluation_status") != "TRIGGERED":
            invalid.append("trigger_without_triggered_evaluation")
        if event.get("next_action") != "REASSESS":
            invalid.append("trigger_must_route_to_reassessment")
        if event.get("automatic_trade_forbidden") is not True:
            invalid.append("trigger_cannot_authorize_trade")
    elif event_type == "prediction_resolution":
        prediction = prediction_map.get(str(event.get("prediction_id") or ""))
        if prediction is None:
            invalid.append("unknown_prediction_id")
        if _number(event.get("outcome")) not in {0.0, 1.0}:
            invalid.append("binary_outcome_invalid")
        due = _day((prediction or {}).get("resolution_due"))
        if due is not None and observed is not None and observed < due and not str(event.get("early_resolution_basis") or ""):
            invalid.append("prediction_resolved_before_due")
        if due is None:
            warnings.append("prediction_due_was_missing_requires_manual_review")
        if prediction:
            set_id = str(prediction.get("set_id") or "")
            for old in existing_events:
                if old.get("event_type") != "prediction_resolution" or _number(old.get("outcome")) != 1.0:
                    continue
                old_prediction = prediction_map.get(str(old.get("prediction_id") or "")) or {}
                if set_id and str(old_prediction.get("set_id") or "") == set_id and _number(event.get("outcome")) == 1.0:
                    invalid.append("probability_set_multiple_realized_scenarios")
    elif event_type == "decision_review":
        refs = [str(value) for value in event.get("trigger_event_ids") or []]
        if not refs or any(known.get(value, {}).get("event_type") != "trigger_event" for value in refs):
            invalid.append("decision_review_trigger_link_invalid")
        if event.get("conclusion") not in {"NO_CHANGE", "CHANGE_PROPOSED", "INCONCLUSIVE"}:
            invalid.append("decision_review_conclusion_invalid")
        if not str(event.get("valuation_impact") or "") or not str(event.get("action_impact") or ""):
            incomplete.append("decision_review_impact_missing")
    elif event_type == "decision_revision":
        review = known.get(str(event.get("review_event_id") or ""))
        if not review or review.get("event_type") != "decision_review" or review.get("conclusion") != "CHANGE_PROPOSED":
            invalid.append("decision_revision_without_approved_review")
        if not str(event.get("change_reason") or "") or not str(event.get("new_action") or ""):
            incomplete.append("decision_revision_details_missing")
        if event.get("external_trade_executed") is True:
            invalid.append("monitoring_cannot_execute_external_trade")
    elif event_type == "return_observation":
        if _number(event.get("actual_total_return_pct")) is None or not event.get("window_start") or not event.get("window_end"):
            incomplete.append("return_window_or_value_missing")
        warnings.append("return_is_decision_calibration_not_research_truth")
    elif event_type == "process_observation":
        for field in ("facts_checked", "data_errors", "parameters_checked", "parameter_conflicts"):
            value = _number(event.get(field))
            if value is None or value < 0:
                invalid.append(field + "_invalid")
    elif event_type == "monitoring_failure":
        if not str(event.get("failure_code") or "") or not str(event.get("retry_after") or ""):
            incomplete.append("failure_code_or_retry_missing")
    if event.get("event_fingerprint") != _record_fingerprint(event, "event_fingerprint"):
        invalid.append("event_fingerprint_mismatch")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"schema_version": VALIDATION_VERSION, "state": state,
            "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
            "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings}


def append_monitoring_events(output_dir: str | Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "monitoring_plan.json")
    if not plan:
        return {"written": False, "error": "monitoring_plan_missing"}
    path = output / "monitoring_events.jsonl"
    existing, parse_errors = _read_jsonl(path)
    if parse_errors:
        return {"written": False, "error": "monitoring_event_ledger_corrupt", "findings": parse_errors}
    by_id = _event_map(existing)
    staged: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    for raw in events:
        event = prepare_monitoring_event(raw)
        event_id = str(event.get("event_id") or "")
        old = by_id.get(event_id)
        if old:
            if old.get("event_fingerprint") == event.get("event_fingerprint"):
                continue
            return {"written": False, "error": "append_only_event_conflict:" + event_id}
        validation = validate_monitoring_event(event, plan, existing_events=[*existing, *staged])
        validations.append(validation)
        if validation["state"] in {"INVALID", "INCOMPLETE"}:
            return {"written": False, "error": "event_validation_failed:" + event_id,
                    "validation": validation}
        staged.append(event); by_id[event_id] = event
    if staged:
        committed = _append_jsonl(path, staged)
        if not committed.get("written"):
            return committed
        accepted_ids = committed.get("accepted_event_ids") or []
    else:
        accepted_ids = []
    audit = audit_monitoring_output(output, persist=True)
    return {"written": True, "path": str(path), "accepted_event_ids": accepted_ids,
            "idempotent_count": len(events) - len(accepted_ids), "validations": validations, "audit": audit}


def _compare(value: float, operator: str, threshold: float) -> bool:
    return {"<": value < threshold, "<=": value <= threshold, ">": value > threshold,
            ">=": value >= threshold, "==": math.isclose(value, threshold),
            "changes_to": math.isclose(value, threshold)}.get(operator, False)


def evaluate_threshold(threshold: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    clean = []
    for item in observations:
        if not isinstance(item, dict) or _number(item.get("value")) is None or _day(item.get("period_end")) is None:
            continue
        clean.append({"value": float(item["value"]), "period_end": str(item["period_end"])[:10],
                      "source_event_id": item.get("source_event_id"), "outlier": bool(item.get("outlier")),
                      "confirmation_source_ids": item.get("confirmation_source_ids") or []})
    clean.sort(key=lambda item: (item["period_end"], str(item.get("source_event_id") or "")))
    minimum = int(threshold.get("minimum_observations") or 1)
    aggregation = str(threshold.get("aggregation") or "single_period")
    relevant = clean[-minimum:]
    status = "NOT_DUE"
    aggregate_value: float | None = None
    hit_count = 0
    if len(relevant) >= minimum:
        if any(item["outlier"] and not item["confirmation_source_ids"] for item in relevant):
            status = "NEEDS_CONFIRMATION"
        else:
            values = [item["value"] for item in relevant]
            target = float(threshold.get("threshold_value"))
            operator = str(threshold.get("operator") or "")
            if aggregation == "rolling_average":
                aggregate_value = mean(values); triggered = _compare(aggregate_value, operator, target)
            elif aggregation == "cumulative":
                aggregate_value = sum(values); triggered = _compare(aggregate_value, operator, target)
            elif aggregation == "consecutive_periods":
                aggregate_value = values[-1]
                hits = [_compare(value, operator, target) for value in values]
                hit_count = sum(hits); triggered = all(hits)
            else:
                aggregate_value = values[-1]; triggered = _compare(aggregate_value, operator, target)
                hit_count = int(triggered)
            status = "TRIGGERED" if triggered else "NOT_TRIGGERED"
    payload = {"evaluation_status": status, "aggregate_value": aggregate_value,
               "observation_count": len(clean), "window_observation_count": len(relevant),
               "required_observations": minimum, "hit_count": hit_count,
               "observations": relevant}
    payload["evaluation_fingerprint"] = _hash(payload)
    return payload


def _fact_key(item: dict[str, Any]) -> str:
    return f"{item.get('domain') or ''}:{item.get('fact_name') or ''}:{item.get('basis') or ''}"


def fact_differences(baseline: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous: dict[str, dict[str, Any]] = {}
    latest: dict[str, dict[str, Any]] = {}
    for target, rows in ((previous, baseline), (latest, current)):
        for item in rows:
            if not isinstance(item, dict) or item.get("status") not in {None, "VERIFIED"}:
                continue
            key = _fact_key(item)
            if key not in target or str(item.get("as_of") or "") > str(target[key].get("as_of") or ""):
                target[key] = item
    result = []
    for key, item in sorted(latest.items()):
        old = previous.get(key)
        if old and str(item.get("as_of") or "") <= str(old.get("as_of") or ""):
            continue
        old_value = (old or {}).get("normalized_value")
        new_value = item.get("normalized_value")
        classification = "NEW_FACT" if old is None else "NEW_PERIOD_CHANGED" if old_value != new_value else "NEW_PERIOD_UNCHANGED"
        result.append({"fact_key": key, "fact_name": item.get("fact_name"), "domain": item.get("domain"),
                       "basis": item.get("basis"), "unit": item.get("unit"),
                       "previous_as_of": (old or {}).get("as_of"), "previous_value": old_value,
                       "current_as_of": item.get("as_of"), "current_value": new_value,
                       "observation_id": item.get("observation_id"), "doc_id": item.get("doc_id"),
                       "classification": classification})
    return result


def record_disclosure_cycle(
    output_dir: str | Path, *, disclosure: dict[str, Any], current_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "monitoring_plan.json")
    snapshot = _load(output / "publication_snapshot.json")
    if not plan or not snapshot:
        return {"written": False, "error": "snapshot_or_monitoring_plan_missing"}
    source = {
        "source_id": disclosure.get("source_id") or disclosure.get("doc_id"),
        "sha256": disclosure.get("sha256"), "disclosed_at": disclosure.get("disclosed_at"),
        "data_as_of": disclosure.get("data_as_of"), "authority": disclosure.get("authority") or "official_filing",
    }
    suffix = _hash({"report": plan.get("report_id"), "source": source})[:16]
    disclosure_event_id = "MON:DISC:" + suffix
    common = {"report_id": plan.get("report_id"), "snapshot_fingerprint": plan.get("snapshot_fingerprint"),
              "observed_at": disclosure.get("observed_at") or disclosure.get("disclosed_at"),
              "source_evidence": [source]}
    disclosure_event = {**common, "event_id": disclosure_event_id, "event_type": "disclosure_observed",
                        "disclosure_id": disclosure.get("doc_id") or source["source_id"],
                        "data_as_of": disclosure.get("data_as_of"), "authority": source["authority"]}
    baseline_facts = snapshot.get("facts") or []
    diffs = fact_differences(baseline_facts, current_facts)
    events = [disclosure_event]
    fact_event_by_name: dict[str, dict[str, Any]] = {}
    for diff in diffs:
        fact_event_id = "MON:FACT:" + _hash({"disclosure": disclosure_event_id, "fact": diff})[:16]
        event = {**common, "event_id": fact_event_id, "event_type": "fact_observation",
                 "disclosure_event_id": disclosure_event_id, **diff,
                 "normalized_value": diff.get("current_value"), "raw_value": str(diff.get("current_value"))}
        events.append(event); fact_event_by_name[str(diff.get("fact_name"))] = event
    first = append_monitoring_events(output, events)
    if not first.get("written"):
        return first
    existing, _ = _read_jsonl(output / "monitoring_events.jsonl")
    followups: list[dict[str, Any]] = []
    trigger_ids: list[str] = []
    triggered_fact_names: set[str] = set()
    for threshold in plan.get("thresholds") or []:
        fact_name = str(threshold.get("fact_name") or "")
        fact_event = fact_event_by_name.get(fact_name)
        if not fact_event:
            continue
        history = [
            {"value": item.get("normalized_value"), "period_end": item.get("current_as_of"),
             "source_event_id": item.get("event_id")}
            for item in existing if item.get("event_type") == "fact_observation" and item.get("fact_name") == fact_name
        ]
        evaluated = evaluate_threshold(threshold, history)
        evaluation_id = "MON:EVAL:" + _hash({"threshold": threshold.get("threshold_id"), "history": history})[:16]
        evaluation = {**common, "event_id": evaluation_id, "event_type": "trigger_evaluation",
                      "threshold_id": threshold.get("threshold_id"), "unit": threshold.get("unit"),
                      "accounting_definition": threshold.get("accounting_definition"), **evaluated}
        followups.append(evaluation)
        if evaluated["evaluation_status"] == "TRIGGERED":
            trigger_id = "MON:TRIGGER:" + _hash(evaluation_id)[:16]
            followups.append({**common, "event_id": trigger_id, "event_type": "trigger_event",
                              "threshold_id": threshold.get("threshold_id"), "evaluation_event_id": evaluation_id,
                              "next_action": "REASSESS", "automatic_trade_forbidden": True,
                              "original_action_after_review": threshold.get("action_after_review")})
            trigger_ids.append(trigger_id)
            triggered_fact_names.add(fact_name)
    second = append_monitoring_events(output, followups) if followups else {"written": True, "accepted_event_ids": []}
    if not second.get("written"):
        return second
    _atomic_write_json(output / "fact_diff.json", {
        "schema_version": "monitoring-fact-diff.v2", "generated_at": _now(),
        "snapshot_fingerprint": plan.get("snapshot_fingerprint"), "disclosure_event_id": disclosure_event_id,
        "differences": diffs,
    })
    audit = audit_monitoring_output(output, persist=True)
    _atomic_write_json(output / "decision_diff_candidates.json", {
        "schema_version": "monitoring-decision-diff-candidates.v2", "generated_at": _now(),
        "snapshot_fingerprint": plan.get("snapshot_fingerprint"),
        "candidates": [{
            "fact_key": diff.get("fact_key"), "classification": diff.get("classification"),
            "previous_value": diff.get("previous_value"), "current_value": diff.get("current_value"),
            "linked_threshold_ids": [str(item.get("threshold_id")) for item in plan.get("thresholds") or []
                                     if item.get("fact_name") == diff.get("fact_name")],
            "review_state": "REASSESS_REQUIRED" if diff.get("fact_name") in triggered_fact_names else "MATERIALITY_SCREEN_REQUIRED",
            "automatic_decision_change_forbidden": True,
        } for diff in diffs if diff.get("classification") != "NEW_PERIOD_UNCHANGED"],
    })
    return {"written": True, "disclosure_event_id": disclosure_event_id, "fact_differences": diffs,
            "trigger_event_ids": trigger_ids, "accepted_event_ids": first.get("accepted_event_ids", []) + second.get("accepted_event_ids", []),
            "audit": audit}


def auto_monitor_latest_disclosure(output_dir: str | Path) -> dict[str, Any]:
    """Ingest the newest official document when its disclosure identity is complete."""
    output = Path(output_dir)
    snapshot = _load(output / "publication_snapshot.json")
    if not snapshot:
        return {"state": "NOT_PUBLISHED", "written": False, "reason": "publication_snapshot_missing"}
    plan = _load(output / "monitoring_plan.json") or build_monitoring_plan(output, snapshot, persist=True)
    manifest = _load(output / "document_manifest.json")
    cutoff = _day(snapshot.get("data_as_of"))
    candidates = [
        item for item in manifest.get("documents") or []
        if isinstance(item, dict) and item.get("authority") in {"audited_filing", "company_filing"}
        and _day(item.get("period_end")) is not None
        and (cutoff is None or _day(item.get("period_end")) > cutoff)
    ]
    if not candidates:
        return {"state": "NO_NEW_DISCLOSURE", "written": True, "report_id": plan.get("report_id")}
    document = sorted(candidates, key=lambda item: (str(item.get("period_end")), str(item.get("doc_id"))))[-1]
    if _day(document.get("published_at")) is None:
        result = {"state": "INCOMPLETE", "written": False,
                  "reason": "latest_document_disclosed_at_missing", "doc_id": document.get("doc_id")}
        _atomic_write_json(output / "monitoring_ingestion_pending.json", result)
        _atomic_write_json(output / "monitoring_alerts.json", {
            "schema_version": "monitoring-alerts.v2", "generated_at": _now(),
            "report_id": plan.get("report_id"),
            "alerts": [{"severity": "REVIEW", "finding": result["reason"], "doc_id": document.get("doc_id")}],
        })
        return result
    facts = _load(output / "fact_observations.json").get("observations") or []
    current = [item for item in facts if isinstance(item, dict) and item.get("status") == "VERIFIED"
               and str(item.get("as_of") or "") == str(document.get("period_end") or "")]
    if not current:
        result = {"state": "INCOMPLETE", "written": False,
                  "reason": "latest_document_verified_facts_missing", "doc_id": document.get("doc_id")}
        _atomic_write_json(output / "monitoring_ingestion_pending.json", result)
        _atomic_write_json(output / "monitoring_alerts.json", {
            "schema_version": "monitoring-alerts.v2", "generated_at": _now(),
            "report_id": plan.get("report_id"),
            "alerts": [{"severity": "REVIEW", "finding": result["reason"], "doc_id": document.get("doc_id")}],
        })
        return result
    return record_disclosure_cycle(output, disclosure={
        "doc_id": document.get("doc_id"), "source_id": document.get("local_path") or document.get("doc_id"),
        "sha256": document.get("sha256"), "disclosed_at": document.get("published_at"),
        "observed_at": document.get("published_at"), "data_as_of": document.get("period_end"),
        "authority": document.get("authority"),
    }, current_facts=current)


def historical_disclosure_replay(
    source_output_dir: str | Path, replay_output_dir: str | Path, *,
    baseline_as_of: str, baseline_published_at: str,
    current_as_of: str, current_published_at: str,
    fact_name: str = "overall_gross_margin_pct",
) -> dict[str, Any]:
    """Exercise a full cycle on real filings without claiming a live forecast.

    The monitoring threshold is derived only from observations available by the
    baseline cutoff.  Because there was no contemporaneous Turtle publication,
    the replay is excluded from probability and investment-performance scores.
    """
    source = Path(source_output_dir); replay = Path(replay_output_dir)
    observations = [item for item in _load(source / "fact_observations.json").get("observations") or []
                    if isinstance(item, dict) and item.get("status") == "VERIFIED" and item.get("fact_name") == fact_name]
    baseline_history = sorted([item for item in observations if str(item.get("as_of") or "") <= baseline_as_of],
                              key=lambda item: str(item.get("as_of") or ""))
    current = [item for item in observations if str(item.get("as_of") or "") == current_as_of]
    if not baseline_history or not current:
        return {"written": False, "error": "replay_fact_period_missing"}
    values = [float(item["normalized_value"]) for item in baseline_history if _number(item.get("normalized_value")) is not None]
    declines = [values[index - 1] - values[index] for index in range(1, len(values)) if values[index] < values[index - 1]]
    adverse_buffer = sorted(declines)[len(declines) // 2] if declines else max(abs(values[-1]) * 0.1, 0.1)
    threshold_value = round(values[-1] - adverse_buffer, 1)
    baseline_fact = baseline_history[-1]
    manifest = _load(source / "document_manifest.json")
    current_doc = next((item for item in manifest.get("documents") or []
                        if isinstance(item, dict) and item.get("period_end") == current_as_of
                        and item.get("authority") == "audited_filing"), None)
    if not current_doc:
        return {"written": False, "error": "replay_official_document_missing"}
    replay.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema_version": "publication-snapshot.v1", "lifecycle": "MONITORING",
        "report_id": "REPLAY:" + str((manifest.get("market") or "UNKNOWN")) + ":" + str(manifest.get("code") or source.name),
        "published_at": baseline_published_at, "data_as_of": baseline_as_of,
        "facts": [deepcopy(item) for item in baseline_history],
        "thresholds": [{
            "threshold_id": "REPLAY.TH:" + fact_name, "metric": "整体毛利率" if fact_name == "overall_gross_margin_pct" else fact_name,
            "fact_name": fact_name, "fact_basis": baseline_fact.get("basis"),
            "current_value": values[-1], "threshold_value": threshold_value,
            "unit": baseline_fact.get("unit"), "operator": "<", "basis_type": "historical_volatility",
            "basis_description": f"只使用截至{baseline_as_of}可见的{len(values)}期真实年报；阈值=基线值减历史不利变动中位数{adverse_buffer:.2f}",
            "source_ids": [str(item.get("doc_id")) for item in baseline_history],
            "accounting_definition": "consolidated gross profit/revenue", "observation_frequency": "annual",
            "window": "单一年度披露；仅用于工程演练", "aggregation": "single_period",
            "seasonal_adjustment": "not_needed", "precision": {"justified_decimals": 1, "basis": "年报原始精度与历史变动"},
            "action": "reassess", "decision_entry_ids": [],
        }],
        "predictions": [], "decision": {},
        "replay_metadata": {"historical_replay": True, "calibration_eligible": False,
                            "reason": "无当时真实Turtle发布决策；只验证披露、事实差异、阈值和队列链路"},
    }
    snapshot["snapshot_fingerprint"] = _hash({key: value for key, value in snapshot.items() if key != "snapshot_fingerprint"})
    _atomic_write_json(replay / "publication_snapshot.json", snapshot)
    plan = build_monitoring_plan(replay, snapshot, persist=True)
    cycle = record_disclosure_cycle(replay, disclosure={
        "doc_id": current_doc.get("doc_id"), "source_id": current_doc.get("local_path"),
        "sha256": current_doc.get("sha256"), "disclosed_at": current_published_at,
        "observed_at": current_published_at, "data_as_of": current_as_of,
        "authority": current_doc.get("authority"),
    }, current_facts=current)
    result = {"schema_version": "historical-monitoring-replay.v2", "written": bool(cycle.get("written")),
              "source_output_dir": str(source), "replay_output_dir": str(replay),
              "baseline_as_of": baseline_as_of, "current_as_of": current_as_of,
              "threshold_value": threshold_value, "baseline_value": values[-1],
              "current_value": current[0].get("normalized_value"), "calibration_eligible": False,
              "plan_state": (plan.get("validation") or {}).get("state"), "cycle": cycle}
    _atomic_write_json(replay / "replay_summary.json", result)
    return result


def _prediction_calibration(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    predictions = {str(item.get("prediction_id")): item for item in snapshot.get("predictions") or [] if isinstance(item, dict)}
    errors = []
    for event in events:
        if event.get("event_type") != "prediction_resolution":
            continue
        prediction = predictions.get(str(event.get("prediction_id") or "")) or {}
        probability = _number(prediction.get("probability")); outcome = _number(event.get("outcome"))
        if probability is not None and outcome in {0.0, 1.0}:
            errors.append((probability - outcome) ** 2)
    return {"resolved_binary_predictions": len(errors),
            "brier_score": round(mean(errors), 6) if errors else None,
            "brier_standard_error": round(pstdev(errors) / math.sqrt(len(errors)), 6) if len(errors) >= 2 else None,
            "uncertainty_note": "n<5，仅展示个案结果，不据此声称概率已校准" if len(errors) < 5 else "标准误仅描述已结算样本，不消除选择偏差"}


def generate_monitoring_dashboard(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    snapshot = _load(output / "publication_snapshot.json")
    plan = _load(output / "monitoring_plan.json")
    events, parse_errors = _read_jsonl(output / "monitoring_events.jsonl")
    evaluations = [item for item in events if item.get("event_type") == "trigger_evaluation"]
    triggers = [item for item in events if item.get("event_type") == "trigger_event"]
    reviews = [item for item in events if item.get("event_type") == "decision_review"]
    revisions = [item for item in events if item.get("event_type") == "decision_revision"]
    reviewed_triggers = {str(ref) for item in reviews for ref in item.get("trigger_event_ids") or []}
    pending = [str(item.get("event_id")) for item in triggers if str(item.get("event_id")) not in reviewed_triggers]
    process = [item for item in events if item.get("event_type") == "process_observation"]
    facts_checked = sum(_number(item.get("facts_checked")) or 0 for item in process)
    errors = sum(_number(item.get("data_errors")) or 0 for item in process)
    params = sum(_number(item.get("parameters_checked")) or 0 for item in process)
    conflicts = sum(_number(item.get("parameter_conflicts")) or 0 for item in process)
    returns = [item for item in events if item.get("event_type") == "return_observation"]
    expected = _number((snapshot.get("decision") or {}).get("expected_return_pct"))
    deviations = [float(item["actual_total_return_pct"]) - expected for item in returns
                  if expected is not None and _number(item.get("actual_total_return_pct")) is not None]
    result = {
        "schema_version": DASHBOARD_VERSION, "generated_at": _now(),
        "report_id": plan.get("report_id"), "snapshot_fingerprint": plan.get("snapshot_fingerprint"),
        "event_sample_size": len(events), "event_parse_errors": parse_errors,
        "prediction_calibration": _prediction_calibration(snapshot, events),
        "process_calibration": {"observations": len(process), "facts_checked": facts_checked,
                                "data_error_rate": round(errors / facts_checked, 6) if facts_checked else None,
                                "parameters_checked": params,
                                "parameter_conflict_rate": round(conflicts / params, 6) if params else None},
        "trigger_effectiveness": {"evaluations": len(evaluations),
                                  "triggered": len(triggers),
                                  "needs_confirmation": sum(item.get("evaluation_status") == "NEEDS_CONFIRMATION" for item in evaluations),
                                  "reviewed": len(reviewed_triggers), "pending_review": len(pending),
                                  "review_coverage_rate": round(len(reviewed_triggers) / len(triggers), 6) if triggers else None},
        "decision_calibration": {"revisions": len(revisions), "return_observations": len(returns),
                                 "mean_expected_actual_return_deviation_pct": round(mean(deviations), 6) if deviations else None,
                                 "quality_interpretation": "收益偏差只评价决策校准，不单独证明研究正确或错误"},
        "case_tracking": {
            "task_count": len(plan.get("case_review_tasks") or []),
            "states": {state: sum(item.get("state") == state for item in plan.get("case_review_tasks") or [])
                       for state in ("CANDIDATE", "REVIEWABLE", "RESOLVED", "ELIGIBLE", "EXCLUDED")},
            "automatic_promotion_forbidden": True,
        },
        "pending_review_trigger_ids": pending,
        "warnings": list(dict.fromkeys((plan.get("warnings") or []) + (["prediction_sample_too_small"] if _prediction_calibration(snapshot, events)["resolved_binary_predictions"] < 5 else []))),
    }
    if persist:
        _atomic_write_json(output / "calibration_dashboard.json", result)
        _atomic_write_json(output / "decision_review_queue.json", {
            "schema_version": "decision-review-queue.v2", "generated_at": _now(),
            "snapshot_fingerprint": plan.get("snapshot_fingerprint"),
            "tasks": [{"trigger_event_id": event_id, "status": "PENDING", "required_action": "REASSESS_NOT_TRADE"} for event_id in pending],
        })
    return result


def audit_monitoring_output(output_dir: str | Path, *, as_of: str | None = None, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "monitoring_plan.json")
    if not plan:
        return {"schema_version": VALIDATION_VERSION, "state": "NOT_INITIALIZED", "status": "SKIP",
                "invalid_findings": [], "incomplete_findings": [], "warnings": []}
    plan_validation = validate_monitoring_plan(plan, output_dir=output)
    events, parse_errors = _read_jsonl(output / "monitoring_events.jsonl")
    invalid = list(plan_validation["invalid_findings"]) + parse_errors
    incomplete = list(plan_validation["incomplete_findings"])
    warnings = list(plan_validation["warnings"])
    staged: list[dict[str, Any]] = []
    for event in events:
        validation = validate_monitoring_event(event, plan, existing_events=staged)
        invalid.extend(f"{event.get('event_id')}:{item}" for item in validation["invalid_findings"])
        incomplete.extend(f"{event.get('event_id')}:{item}" for item in validation["incomplete_findings"])
        warnings.extend(f"{event.get('event_id')}:{item}" for item in validation["warnings"])
        staged.append(event)
    today = _day(as_of) or date.today()
    observed_thresholds = {str(item.get("threshold_id")) for item in events if item.get("event_type") == "trigger_evaluation"}
    overdue = []
    for threshold in plan.get("thresholds") or []:
        due = _day(threshold.get("next_due")); tid = str(threshold.get("threshold_id") or "")
        tolerance = int(threshold.get("late_data_tolerance_days") or 0)
        if due and due + timedelta(days=tolerance) < today and tid not in observed_thresholds:
            overdue.append("threshold_observation_overdue:" + tid)
    for task in plan.get("case_review_tasks") or []:
        due = _day(task.get("resolution_due")); case_id = str(task.get("case_id") or "")
        if due and due < today and task.get("state") not in {"RESOLVED", "ELIGIBLE", "EXCLUDED"}:
            overdue.append("case_resolution_overdue:" + case_id)
    warnings.extend(overdue)
    dashboard = generate_monitoring_dashboard(output, persist=persist)
    if dashboard.get("pending_review_trigger_ids"):
        incomplete.extend("trigger_review_pending:" + item for item in dashboard["pending_review_trigger_ids"])
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "MONITORING"
    result = {"schema_version": VALIDATION_VERSION, "state": state,
              "status": "FAIL" if state == "INVALID" else "WARN" if state == "INCOMPLETE" else "PASS",
              "blocking_for_historical_integrity": bool(invalid),
              "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings,
              "event_count": len(events), "dashboard": dashboard}
    if persist:
        _atomic_write_json(output / "monitoring_validation.json", result)
        _atomic_write_json(output / "monitoring_alerts.json", {
            "schema_version": "monitoring-alerts.v2", "generated_at": _now(),
            "report_id": plan.get("report_id"),
            "alerts": ([{"severity": "CRITICAL", "finding": value} for value in invalid]
                       + [{"severity": "REVIEW", "finding": value} for value in incomplete]
                       + [{"severity": "WARN", "finding": value} for value in overdue]),
        })
    return result


def monitor_all(output_root: str | Path, *, as_of: str | None = None) -> dict[str, Any]:
    root = Path(output_root)
    results = []
    for snapshot_path in sorted(root.glob("*/publication_snapshot.json")):
        output = snapshot_path.parent
        plan = _load(output / "monitoring_plan.json") or build_monitoring_plan(output, persist=True)
        audit = audit_monitoring_output(output, as_of=as_of, persist=True)
        results.append({"output_dir": str(output), "report_id": plan.get("report_id"),
                        "state": audit.get("state"), "invalid": len(audit.get("invalid_findings") or []),
                        "incomplete": len(audit.get("incomplete_findings") or []),
                        "warnings": len(audit.get("warnings") or [])})
    summary = {"schema_version": "monitoring-run-summary.v2", "generated_at": _now(),
               "outputs_scanned": len(results), "invalid_outputs": sum(item["state"] == "INVALID" for item in results),
               "review_outputs": sum(item["state"] == "INCOMPLETE" for item in results), "results": results}
    _atomic_write_json(root / ".monitoring_run_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict post-publication monitoring")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan"); plan.add_argument("--output-dir", required=True)
    audit = sub.add_parser("audit"); audit.add_argument("--output-dir", required=True); audit.add_argument("--as-of", default="")
    cycle = sub.add_parser("cycle"); cycle.add_argument("--output-dir", required=True); cycle.add_argument("--disclosure", required=True); cycle.add_argument("--facts", required=True)
    scan = sub.add_parser("scan"); scan.add_argument("--output-root", default="output"); scan.add_argument("--as-of", default="")
    replay = sub.add_parser("replay"); replay.add_argument("--source-output-dir", required=True); replay.add_argument("--replay-output-dir", required=True)
    replay.add_argument("--baseline-as-of", required=True); replay.add_argument("--baseline-published-at", required=True)
    replay.add_argument("--current-as-of", required=True); replay.add_argument("--current-published-at", required=True)
    replay.add_argument("--fact-name", default="overall_gross_margin_pct")
    args = parser.parse_args()
    if args.command == "plan":
        result = build_monitoring_plan(args.output_dir)
    elif args.command == "audit":
        result = audit_monitoring_output(args.output_dir, as_of=args.as_of or None)
    elif args.command == "scan":
        result = monitor_all(args.output_root, as_of=args.as_of or None)
    elif args.command == "replay":
        result = historical_disclosure_replay(
            args.source_output_dir, args.replay_output_dir,
            baseline_as_of=args.baseline_as_of, baseline_published_at=args.baseline_published_at,
            current_as_of=args.current_as_of, current_published_at=args.current_published_at,
            fact_name=args.fact_name,
        )
    else:
        disclosure = _load(Path(args.disclosure)); facts_payload = _load(Path(args.facts))
        result = record_disclosure_cycle(args.output_dir, disclosure=disclosure,
                                         current_facts=facts_payload.get("observations") or facts_payload.get("facts") or [])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get("state") == "INVALID" or result.get("written") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
