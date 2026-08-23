#!/usr/bin/env python3
"""Append-only, as-of-time base-rate case library for Turtle research."""

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
from typing import Any, Iterable

try:
    from scripts.config import get_base_rate_library_dir
    from scripts.evidence_documents import _atomic_write_json
except ModuleNotFoundError:
    from config import get_base_rate_library_dir
    from evidence_documents import _atomic_write_json


CASE_SCHEMA_VERSION = "base-rate-case.v1"
EVENT_SCHEMA_VERSION = "base-rate-case-event.v1"
CONTEXT_SCHEMA_VERSION = "base-rate-context.v1"
POLICY_SCHEMA_VERSION = "base-rate-policy.v1"
VALIDATION_SCHEMA_VERSION = "base-rate-validation.v1"
MANIFEST_SCHEMA_VERSION = "base-rate-library-manifest.v1"
MIN_EMPIRICAL_SAMPLE = 5
PROBABILITY_KINDS = {"frequency", "base_rate", "analyst_subjective", "scenario_weight"}
EVENT_TYPES = {"outcome", "eligibility_review", "exclusion"}
EPISODE_SETTLEMENT_STATUSES = {"OPEN", "SETTLED", "UNRESOLVED"}
CASE_SELECTION_OUTCOME_ISOLATIONS = {"PIT_PRE_OUTCOME", "OUTCOME_SELECTED_RESEARCH_ONLY"}
PIT_BASE_RATE_DEGRADATION = "pit_global_base_rate_library_forbidden_without_case_level_admission"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _library_dir(value: str | Path | None = None) -> Path:
    return Path(value or get_base_rate_library_dir()).resolve()


def _pit_contract(output_dir: str | Path | None) -> dict[str, Any]:
    if output_dir is None:
        return {}
    contract = _load(Path(output_dir) / "analysis_contract.json")
    pit = contract.get("pit_production")
    return {"_present": True, **pit} if isinstance(pit, dict) else {}


def _empty_pit_query(
    mechanism_key: str, archetype_ids: list[str], variable_keys: list[str],
) -> dict[str, Any]:
    return {
        "mechanism_key": mechanism_key,
        "archetype_ids": list(archetype_ids),
        "variable_keys": sorted({str(item) for item in variable_keys if str(item).strip()}),
        "eligible_sample_size": 0,
        "independent_company_sample_size": 0,
        "independence_qualified": False,
        "common_question_set_ids": [],
        "terminal_outcome_scopes": [],
        "outcome_counts": {},
        "empirical_base_rate": None,
        "eligible_cases": [],
        "warnings": [PIT_BASE_RATE_DEGRADATION, f"sample_too_small:0<{MIN_EMPIRICAL_SAMPLE}"],
    }


def _record_fingerprint(record: dict[str, Any], field: str) -> str:
    payload = deepcopy(record)
    payload.pop(field, None)
    if field == "case_fingerprint":
        payload.pop("created_at", None)
    elif field == "event_fingerprint":
        payload.pop("recorded_at", None)
    elif field == "context_fingerprint":
        payload.pop("generated_at", None)
    return _hash(payload)


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.is_file():
        return records, errors
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            errors.append(f"{path.name}:L{line_number}:invalid_json")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}:L{line_number}:not_object")
            continue
        records.append(value)
    return records, errors


def _append_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_mechanism_episode(episode: Any) -> dict[str, list[str]]:
    """Validate episode identity without manufacturing a reference-class sample.

    A base-rate case remains the append-only PIT object.  This optional
    extension makes its mechanism comparable with other company×time cases;
    it is not a second case library and does not make correlated cases
    independent observations.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(episode, dict):
        return {"invalid_findings": ["episode_not_object"], "incomplete_findings": []}
    if not str(episode.get("episode_id") or "").startswith("MEP:"):
        invalid.append("episode_id_invalid")
    for field in ("industry_regime", "common_question_set_id", "terminal_outcome_scope", "strongest_alternative_id"):
        if not str(episode.get(field) or "").strip():
            incomplete.append(field + "_missing")
    for field in ("mechanism_chain_ids", "forward_judgment_ids", "baseline_ids"):
        values = episode.get(field)
        if not isinstance(values, list) or not values or any(not str(item).strip() for item in values):
            incomplete.append(field + "_missing")
        elif len({str(item) for item in values}) != len(values):
            invalid.append(field + "_duplicate")
    bridge = episode.get("financial_driver_bridge")
    if not isinstance(bridge, dict):
        incomplete.append("financial_driver_bridge_missing")
    elif bridge.get("state") not in {"BOUND", "UNKNOWN"}:
        invalid.append("financial_driver_bridge_state_invalid")
    elif bridge.get("state") == "BOUND" and not str(bridge.get("reference") or "").strip():
        incomplete.append("financial_driver_bridge_reference_missing")
    elif bridge.get("state") == "UNKNOWN" and not str(bridge.get("conservative_treatment") or "").strip():
        incomplete.append("financial_driver_bridge_conservative_treatment_missing")
    cluster = episode.get("cluster")
    if not isinstance(cluster, dict):
        incomplete.append("cluster_missing")
    else:
        for field in ("company_id", "period_cluster_id", "mechanism_cluster_id"):
            if not str(cluster.get(field) or "").strip():
                incomplete.append("cluster_" + field + "_missing")
    if episode.get("settlement_status") not in EPISODE_SETTLEMENT_STATUSES:
        invalid.append("settlement_status_invalid")
    return {
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
    }


def validate_case(
    record: dict[str, Any], *, require_episode_identity: bool = False,
    require_case_selection_identity: bool = False,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if record.get("schema_version") != CASE_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    case_id = str(record.get("case_id") or "")
    if not case_id.startswith("CASE:"):
        invalid.append("case_id_invalid")
    cutoff = _day(record.get("information_cutoff"))
    as_of = _day(record.get("as_of"))
    if cutoff is None or as_of is None:
        invalid.append("as_of_or_cutoff_invalid")
    elif as_of > cutoff:
        invalid.append("as_of_after_information_cutoff")
    if not record.get("archetype_ids") or not record.get("mechanism_keys"):
        incomplete.append("archetype_or_mechanism_missing")
    source_capture = record.get("source_capture") if isinstance(record.get("source_capture"), dict) else {}
    if not source_capture.get("artifact_id") or not str(source_capture.get("artifact_sha256") or ""):
        incomplete.append("source_capture_missing")
    capture_identity = " ".join(
        str(source_capture.get(field) or "") for field in ("artifact_id", "artifact_kind", "path")
    ).lower()
    if "130家估值模型" in capture_identity or "valuation_reference" in capture_identity:
        invalid.append("mechanism_reference_not_case_evidence")
    if str(record.get("case_status_at_capture") or "") not in {"CANDIDATE", "REVIEWABLE"}:
        invalid.append("case_status_at_capture_invalid")
    evidence = record.get("visible_evidence")
    if not isinstance(evidence, list) or not evidence:
        incomplete.append("visible_evidence_missing")
        evidence = []
    source_ids: set[str] = set()
    source_groups: list[str] = []
    for index, item in enumerate(evidence):
        prefix = f"visible_evidence[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object"); continue
        source_id = str(item.get("source_id") or "")
        digest = str(item.get("sha256") or "")
        if not source_id or len(digest) != 64:
            invalid.append(prefix + ":identity_or_hash_invalid")
        if source_id in source_ids:
            invalid.append("duplicate_source_id:" + source_id)
        source_ids.add(source_id)
        group = str(item.get("source_group_id") or "")
        if not group:
            incomplete.append(prefix + ":source_group_missing")
        else:
            source_groups.append(group)
        disclosed = _day(item.get("disclosed_at"))
        if disclosed is None:
            incomplete.append(prefix + ":disclosed_at_unverified")
        elif cutoff is not None and disclosed > cutoff:
            invalid.append(prefix + ":future_information_leakage")
        data_as_of = _day(item.get("data_as_of"))
        if data_as_of is not None and cutoff is not None and data_as_of > cutoff:
            invalid.append(prefix + ":future_data_as_of")
    if len(set(source_groups)) < len(source_groups):
        warnings.append("duplicate_source_groups_do_not_count_as_cross_validation")
    prediction = record.get("prediction") if isinstance(record.get("prediction"), dict) else {}
    status = str(prediction.get("status") or "")
    if status not in {"NOT_ASSIGNED", "RECORDED"}:
        invalid.append("prediction_status_invalid")
    forbidden = {"outcome", "resolved", "result", "actual"}.intersection(prediction)
    if forbidden:
        invalid.append("prediction_contains_hindsight_fields:" + ",".join(sorted(forbidden)))
    outcomes = prediction.get("outcome_space")
    if not isinstance(outcomes, list) or len(outcomes) < 2:
        incomplete.append("prediction_outcome_space_incomplete")
        outcomes = []
    scenario_ids = [str(item.get("scenario_id") or "") for item in outcomes if isinstance(item, dict)]
    if len(set(scenario_ids)) != len(scenario_ids) or any(not item for item in scenario_ids):
        invalid.append("prediction_scenario_identity_invalid")
    due = _day(prediction.get("resolution_due"))
    if due is None:
        incomplete.append("prediction_resolution_due_missing")
    elif cutoff is not None and due <= cutoff:
        invalid.append("prediction_resolution_not_after_cutoff")
    if status == "RECORDED":
        kind = str(prediction.get("probability_kind") or "")
        if kind not in PROBABILITY_KINDS:
            invalid.append("probability_kind_invalid")
        probabilities = prediction.get("probabilities")
        if not isinstance(probabilities, list) or len(probabilities) != len(scenario_ids):
            incomplete.append("probabilities_missing_or_not_mece")
            probabilities = []
        total = 0.0
        for index, item in enumerate(probabilities):
            try:
                probability = float(item.get("value"))
                low, high = (float(x) for x in item.get("interval"))
            except (AttributeError, TypeError, ValueError):
                invalid.append(f"probabilities[{index}]:invalid"); continue
            if not 0 <= low <= probability <= high <= 1:
                invalid.append(f"probabilities[{index}]:interval_invalid")
            total += probability
            if str(item.get("scenario_id") or "") not in scenario_ids:
                invalid.append(f"probabilities[{index}]:unknown_scenario")
        if probabilities and not math.isclose(total, 1.0, abs_tol=1e-6):
            invalid.append("probabilities_not_sum_to_one")
        if not str(prediction.get("basis") or "").strip():
            incomplete.append("probability_basis_missing")
        predicted_at = _day(prediction.get("as_of"))
        if predicted_at is None or (cutoff is not None and predicted_at > cutoff):
            invalid.append("probability_as_of_invalid")
    comparability = record.get("comparability") if isinstance(record.get("comparability"), dict) else {}
    for field in ("population_definition", "inclusion_rule", "exclusion_rule"):
        if not str(comparability.get(field) or "").strip():
            incomplete.append("comparability_missing:" + field)
    selection = record.get("case_selection")
    if selection is None and require_case_selection_identity:
        incomplete.append("case_selection_missing")
    elif selection is not None:
        if not isinstance(selection, dict):
            invalid.append("case_selection_not_object")
        else:
            for field in ("register_id", "register_fingerprint", "entry_id"):
                if not str(selection.get(field) or "").strip():
                    incomplete.append("case_selection_" + field + "_missing")
            if not str(selection.get("register_id") or "").startswith("CSR:"):
                invalid.append("case_selection_register_id_invalid")
            if len(str(selection.get("register_fingerprint") or "")) != 64:
                invalid.append("case_selection_register_fingerprint_invalid")
            if not str(selection.get("entry_id") or "").startswith("CSRSEL:"):
                invalid.append("case_selection_entry_id_invalid")
            isolation = str(selection.get("outcome_isolation") or "")
            if isolation not in CASE_SELECTION_OUTCOME_ISOLATIONS:
                invalid.append("case_selection_outcome_isolation_invalid")
            elif isolation == "OUTCOME_SELECTED_RESEARCH_ONLY":
                invalid.append("outcome_selected_research_only_cannot_enter_forward_judgment_calibration_cohort")
    episode = record.get("episode")
    if episode is None:
        if require_episode_identity:
            incomplete.append("mechanism_episode_missing")
        else:
            warnings.append("mechanism_episode_missing")
    else:
        episode_validation = validate_mechanism_episode(episode)
        invalid.extend("mechanism_episode:" + item for item in episode_validation["invalid_findings"])
        incomplete.extend("mechanism_episode:" + item for item in episode_validation["incomplete_findings"])
    expected_fingerprint = _record_fingerprint(record, "case_fingerprint")
    if record.get("case_fingerprint") and record.get("case_fingerprint") != expected_fingerprint:
        invalid.append("case_fingerprint_mismatch")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION, "state": state,
        "status": "FAIL" if state == "INVALID" else "PASS",
        "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings,
    }


def prepare_case(record: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(record)
    payload.setdefault("schema_version", CASE_SCHEMA_VERSION)
    payload.setdefault("created_at", _now())
    payload["case_fingerprint"] = _record_fingerprint(payload, "case_fingerprint")
    return payload


def append_case(record: dict[str, Any], *, library_dir: str | Path | None = None) -> dict[str, Any]:
    root = _library_dir(library_dir)
    payload = prepare_case(record)
    validation = validate_case(payload)
    if validation["state"] == "INVALID":
        return {"written": False, "validation": validation}
    cases, errors = _read_jsonl(root / "cases.jsonl")
    existing = {str(item.get("case_id")): item for item in cases}
    old = existing.get(str(payload.get("case_id")))
    if old:
        if old.get("case_fingerprint") == payload.get("case_fingerprint"):
            return {"written": True, "idempotent": True, "case": old, "validation": validate_case(old)}
        return {"written": False, "error": "append_only_case_conflict", "case_id": payload.get("case_id")}
    if errors:
        return {"written": False, "error": "case_library_corrupt", "findings": errors}
    _append_line(root / "cases.jsonl", payload)
    refresh_library_manifest(root)
    return {"written": True, "idempotent": False, "case": payload, "validation": validation}


def validate_event(event: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(event.get("event_id") or "").startswith("CASEEV:"):
        invalid.append("event_id_invalid")
    if str(event.get("case_id") or "") != str(case.get("case_id") or ""):
        invalid.append("unknown_case_id")
    event_type = str(event.get("event_type") or "")
    if event_type not in EVENT_TYPES:
        invalid.append("event_type_invalid")
    observed = _day(event.get("observed_at"))
    cutoff = _day(case.get("information_cutoff"))
    if observed is None:
        invalid.append("observed_at_invalid")
    elif cutoff is not None and observed <= cutoff:
        invalid.append("event_not_after_information_cutoff")
    sources = event.get("source_evidence")
    if not isinstance(sources, list) or not sources:
        incomplete.append("event_source_evidence_missing")
        sources = []
    for index, source in enumerate(sources):
        disclosed = _day((source or {}).get("disclosed_at")) if isinstance(source, dict) else None
        if disclosed is None or cutoff is None or disclosed <= cutoff:
            invalid.append(f"source_evidence[{index}]:not_post_cutoff")
        if not isinstance(source, dict) or len(str(source.get("sha256") or "")) != 64:
            invalid.append(f"source_evidence[{index}]:hash_invalid")
    if event_type == "outcome":
        scenario = str(event.get("resolved_scenario_id") or "")
        allowed = {
            str(item.get("scenario_id")) for item in (case.get("prediction") or {}).get("outcome_space") or []
            if isinstance(item, dict)
        }
        if scenario not in allowed:
            invalid.append("resolved_scenario_not_in_outcome_space")
    if event_type == "eligibility_review":
        if not isinstance(event.get("approved"), bool) or not str(event.get("reviewer") or "").strip():
            invalid.append("eligibility_review_identity_invalid")
        if not str(event.get("rationale") or "").strip():
            incomplete.append("eligibility_review_rationale_missing")
    if event_type == "exclusion" and not str(event.get("reason") or "").strip():
        incomplete.append("exclusion_reason_missing")
    expected = _record_fingerprint(event, "event_fingerprint")
    if event.get("event_fingerprint") and event.get("event_fingerprint") != expected:
        invalid.append("event_fingerprint_mismatch")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": []}


def prepare_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(event)
    payload.setdefault("schema_version", EVENT_SCHEMA_VERSION)
    payload.setdefault("recorded_at", _now())
    payload["event_fingerprint"] = _record_fingerprint(payload, "event_fingerprint")
    return payload


def append_event(event: dict[str, Any], *, library_dir: str | Path | None = None) -> dict[str, Any]:
    root = _library_dir(library_dir)
    cases, case_errors = _read_jsonl(root / "cases.jsonl")
    case = next((item for item in cases if item.get("case_id") == event.get("case_id")), None)
    if case is None or case_errors:
        return {"written": False, "error": "case_missing_or_library_corrupt", "findings": case_errors}
    payload = prepare_event(event)
    validation = validate_event(payload, case)
    if validation["state"] == "INVALID":
        return {"written": False, "validation": validation}
    events, errors = _read_jsonl(root / "events.jsonl")
    old = next((item for item in events if item.get("event_id") == payload.get("event_id")), None)
    if old:
        if old.get("event_fingerprint") == payload.get("event_fingerprint"):
            return {"written": True, "idempotent": True, "event": old}
        return {"written": False, "error": "append_only_event_conflict", "event_id": payload.get("event_id")}
    if errors:
        return {"written": False, "error": "case_event_library_corrupt", "findings": errors}
    if payload.get("event_type") == "outcome" and any(
        item.get("case_id") == payload.get("case_id") and item.get("event_type") == "outcome" for item in events
    ):
        return {"written": False, "error": "case_outcome_already_recorded"}
    _append_line(root / "events.jsonl", payload)
    refresh_library_manifest(root)
    return {"written": True, "idempotent": False, "event": payload, "validation": validation}


def _case_state(case: dict[str, Any], events: Iterable[dict[str, Any]]) -> str:
    related = [item for item in events if item.get("case_id") == case.get("case_id")]
    if any(item.get("event_type") == "exclusion" for item in related):
        return "EXCLUDED"
    outcome = any(item.get("event_type") == "outcome" for item in related)
    approved = any(item.get("event_type") == "eligibility_review" and item.get("approved") is True for item in related)
    validation = validate_case(case)
    if validation["state"] == "INVALID":
        return "INVALID"
    if outcome and approved and validation["state"] == "REVIEWABLE":
        return "ELIGIBLE"
    if outcome:
        return "RESOLVED"
    return "REVIEWABLE" if validation["state"] == "REVIEWABLE" else "CANDIDATE"


def validate_verified_episode_reference(
    *, case_id: str, episode_id: str, outcome_event_id: str,
    library_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Confirm that an analogy near-miss is an actual settled case episode.

    A ``CASE:/MEP:/CASEEV:`` prefix is only an identifier shape.  Primary
    analogy support needs the append-only case, its matching episode, a valid
    recorded outcome, and a valid independent eligibility review.  This is
    deliberately not a base-rate query: a single verified near-miss remains a
    structural counterexample, not a frequency observation.
    """
    root = _library_dir(library_dir)
    cases, case_errors = _read_jsonl(root / "cases.jsonl")
    events, event_errors = _read_jsonl(root / "events.jsonl")
    invalid: list[str] = []
    if case_errors or event_errors:
        invalid.append("case_library_parse_errors")
    case = next((item for item in cases if str(item.get("case_id") or "") == case_id), None)
    if case is None:
        invalid.append("case_not_registered")
        return {"state": "INVALID", "invalid_findings": invalid}
    episode = case.get("episode") if isinstance(case.get("episode"), dict) else {}
    if str(episode.get("episode_id") or "") != episode_id:
        invalid.append("episode_not_registered_for_case")
    outcome = next((
        item for item in events
        if str(item.get("event_id") or "") == outcome_event_id
        and str(item.get("case_id") or "") == case_id
    ), None)
    if outcome is None:
        invalid.append("outcome_event_not_registered_for_case")
    elif outcome.get("event_type") != "outcome":
        invalid.append("registered_event_not_outcome")
    elif validate_event(outcome, case)["state"] != "REVIEWABLE":
        invalid.append("outcome_event_not_reviewable")
    valid_approval = any(
        item.get("event_type") == "eligibility_review"
        and item.get("approved") is True
        and validate_event(item, case)["state"] == "REVIEWABLE"
        for item in events if str(item.get("case_id") or "") == case_id
    )
    if not valid_approval:
        invalid.append("independent_eligibility_review_missing")
    case_validation = validate_case(case, require_episode_identity=True)
    if case_validation["state"] != "REVIEWABLE":
        invalid.append("case_or_episode_not_reviewable")
    if _case_state(case, events) != "ELIGIBLE":
        invalid.append("case_not_eligible_settled_episode")
    invalid = list(dict.fromkeys(invalid))
    return {
        "state": "REVIEWABLE" if not invalid else "INVALID",
        "invalid_findings": invalid,
    }


def _episode_company_id(case: dict[str, Any]) -> str | None:
    """Return the pre-registered company cluster for a mechanism episode."""
    episode = case.get("episode") if isinstance(case.get("episode"), dict) else {}
    cluster = episode.get("cluster") if isinstance(episode.get("cluster"), dict) else {}
    company_id = str(cluster.get("company_id") or "").strip()
    return company_id or None


def _episode_comparability_identity(case: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return the common question and terminal-outcome identities of an episode."""
    episode = case.get("episode") if isinstance(case.get("episode"), dict) else {}
    question_set_id = str(episode.get("common_question_set_id") or "").strip() or None
    terminal_scope = str(episode.get("terminal_outcome_scope") or "").strip() or None
    return question_set_id, terminal_scope


def library_fingerprint(cases: list[dict[str, Any]], events: list[dict[str, Any]]) -> str:
    return _hash({
        "cases": sorted(str(item.get("case_fingerprint") or "") for item in cases),
        "events": sorted(str(item.get("event_fingerprint") or "") for item in events),
    })


def query_cases(
    *, mechanism_key: str, archetype_ids: list[str], variable_keys: list[str] | None = None,
    library_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = _library_dir(library_dir)
    cases, case_errors = _read_jsonl(root / "cases.jsonl")
    events, event_errors = _read_jsonl(root / "events.jsonl")
    variables = set(variable_keys or [])
    matches: list[dict[str, Any]] = []
    for case in cases:
        if mechanism_key not in (case.get("mechanism_keys") or []):
            continue
        state = _case_state(case, events)
        if state != "ELIGIBLE":
            continue
        archetype_overlap = len(set(archetype_ids) & set(case.get("archetype_ids") or []))
        variable_overlap = len(variables & set(case.get("variable_keys") or []))
        outcome = next((item for item in events if item.get("case_id") == case.get("case_id") and item.get("event_type") == "outcome"), {})
        common_question_set_id, terminal_outcome_scope = _episode_comparability_identity(case)
        matches.append({
            "case_id": case.get("case_id"), "case_fingerprint": case.get("case_fingerprint"),
            "outcome_event_id": outcome.get("event_id"),
            "resolved_scenario_id": outcome.get("resolved_scenario_id"),
            "archetype_overlap": archetype_overlap, "variable_overlap": variable_overlap,
            "comparability": case.get("comparability"),
            "episode_cluster": deepcopy(((case.get("episode") or {}).get("cluster") or {})),
            "independent_company_id": _episode_company_id(case),
            "common_question_set_id": common_question_set_id,
            "terminal_outcome_scope": terminal_outcome_scope,
        })
    matches.sort(key=lambda item: (-item["archetype_overlap"], -item["variable_overlap"], str(item["case_id"])))
    counts: dict[str, int] = {}
    for item in matches:
        scenario = str(item.get("resolved_scenario_id") or "")
        counts[scenario] = counts.get(scenario, 0) + 1
    sample_size = len(matches)
    company_case_ids: dict[str, list[str]] = {}
    unclustered_case_ids: list[str] = []
    for item in matches:
        company_id = item.get("independent_company_id")
        case_id = str(item.get("case_id") or "")
        if not company_id:
            unclustered_case_ids.append(case_id)
            continue
        company_case_ids.setdefault(str(company_id), []).append(case_id)
    duplicated_companies = {
        company_id: case_ids for company_id, case_ids in company_case_ids.items()
        if len(case_ids) > 1
    }
    independent_company_sample_size = len(company_case_ids)
    question_set_ids = {str(item["common_question_set_id"]) for item in matches if item.get("common_question_set_id")}
    terminal_scopes = {str(item["terminal_outcome_scope"]) for item in matches if item.get("terminal_outcome_scope")}
    missing_comparability_case_ids = [
        str(item.get("case_id") or "") for item in matches
        if not item.get("common_question_set_id") or not item.get("terminal_outcome_scope")
    ]
    common_question_set_qualified = not missing_comparability_case_ids and len(question_set_ids) == 1
    terminal_outcome_scope_qualified = not missing_comparability_case_ids and len(terminal_scopes) == 1
    independence_qualified = (
        not unclustered_case_ids and not duplicated_companies
        and common_question_set_qualified and terminal_outcome_scope_qualified
    )
    empirical = (
        {key: round(value / sample_size, 6) for key, value in sorted(counts.items())}
        if sample_size >= MIN_EMPIRICAL_SAMPLE and independence_qualified else None
    )
    warnings: list[str] = []
    if sample_size < MIN_EMPIRICAL_SAMPLE:
        warnings.append(f"sample_too_small:{sample_size}<{MIN_EMPIRICAL_SAMPLE}")
    elif unclustered_case_ids:
        warnings.append("eligible_cases_missing_episode_cluster:" + ",".join(sorted(unclustered_case_ids)))
    elif duplicated_companies:
        warnings.extend(
            "correlated_company_episodes_prevent_base_rate:"
            + company_id + ":" + ",".join(sorted(case_ids))
            for company_id, case_ids in sorted(duplicated_companies.items())
        )
    if sample_size >= MIN_EMPIRICAL_SAMPLE and missing_comparability_case_ids:
        warnings.append(
            "eligible_cases_missing_common_question_or_terminal_scope:"
            + ",".join(sorted(missing_comparability_case_ids))
        )
    elif sample_size >= MIN_EMPIRICAL_SAMPLE and len(question_set_ids) > 1:
        warnings.append("mixed_common_question_sets_prevent_base_rate:" + ",".join(sorted(question_set_ids)))
    elif sample_size >= MIN_EMPIRICAL_SAMPLE and len(terminal_scopes) > 1:
        warnings.append("mixed_terminal_outcome_scopes_prevent_base_rate:" + ",".join(sorted(terminal_scopes)))
    if sample_size >= MIN_EMPIRICAL_SAMPLE and independent_company_sample_size < MIN_EMPIRICAL_SAMPLE:
        warnings.append(
            f"independent_company_sample_too_small:{independent_company_sample_size}<{MIN_EMPIRICAL_SAMPLE}"
        )
    if case_errors or event_errors:
        warnings.append("library_parse_errors")
    return {
        "mechanism_key": mechanism_key, "archetype_ids": archetype_ids,
        "variable_keys": sorted(variables), "eligible_sample_size": sample_size,
        "independent_company_sample_size": independent_company_sample_size,
        "independence_qualified": independence_qualified,
        "common_question_set_ids": sorted(question_set_ids),
        "terminal_outcome_scopes": sorted(terminal_scopes),
        "outcome_counts": counts, "empirical_base_rate": empirical,
        "eligible_cases": matches, "warnings": warnings,
    }


def build_base_rate_context(
    output_dir: str | Path, *, archetype_ids: list[str],
    questions: list[dict[str, Any]], library_dir: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    pit = _pit_contract(output_dir)
    pit_isolated = bool(pit)
    root = None if pit_isolated else _library_dir(library_dir)
    cases, case_errors = ([], []) if root is None else _read_jsonl(root / "cases.jsonl")
    events, event_errors = ([], []) if root is None else _read_jsonl(root / "events.jsonl")
    queries: dict[str, Any] = {}
    for question in questions:
        mechanism = str(question.get("mechanism_key") or "")
        variables = list((question.get("decision_link") or {}).get("affected_metric_ids") or [])
        if mechanism and mechanism not in queries:
            queries[mechanism] = (
                _empty_pit_query(mechanism, archetype_ids, variables)
                if pit_isolated else query_cases(
                    mechanism_key=mechanism, archetype_ids=archetype_ids,
                    variable_keys=variables, library_dir=root,
                )
            )
    payload = {
        "schema_version": CONTEXT_SCHEMA_VERSION, "generated_at": _now(),
        "library_path_label": "PIT_NO_ADMITTED_SNAPSHOT" if root is None else root.name,
        "library_fingerprint": library_fingerprint(cases, events),
        "archetype_ids": archetype_ids, "queries": queries,
        "availability": {
            "mode": "PIT_EVIDENCE_ONLY" if pit_isolated else "CURRENT_LIBRARY",
            "cutoff_at": str(pit.get("cutoff_at") or "") if pit_isolated else "",
            "base_rate_library": (
                "UNAVAILABLE_NO_CASE_LEVEL_ADMISSION" if pit_isolated else "AVAILABLE"
            ),
        },
        "policy": {
            "minimum_empirical_sample": MIN_EMPIRICAL_SAMPLE,
            "mechanism_match_required": True, "company_name_matching_forbidden": True,
            "base_rate_is_prior_not_company_evidence": True,
        },
        "warnings": list(dict.fromkeys(
            ([PIT_BASE_RATE_DEGRADATION] if pit_isolated else [])
            + case_errors + event_errors + [
            warning for result in queries.values() for warning in result.get("warnings") or []
        ])),
    }
    payload["context_fingerprint"] = _record_fingerprint(payload, "context_fingerprint")
    if persist:
        _atomic_write_json(Path(output_dir) / "base_rate_context.json", payload)
    return payload


def initialize_base_rate_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool,
    context: dict[str, Any] | None = None, require_episode_identity: bool = False,
    require_case_selection_identity: bool = False,
) -> dict[str, Any]:
    context = context or _load(Path(output_dir) / "base_rate_context.json")
    payload = {
        "schema_version": POLICY_SCHEMA_VERSION, "run_id": str(run_id),
        "enforced": bool(enforced), "created_at": _now(),
        "context_fingerprint": context.get("context_fingerprint"),
        "library_fingerprint_at_plan": context.get("library_fingerprint"),
        "minimum_empirical_sample": MIN_EMPIRICAL_SAMPLE,
        "require_episode_identity": bool(require_episode_identity),
        "require_case_selection_identity": bool(require_case_selection_identity),
    }
    _atomic_write_json(Path(output_dir) / "base_rate_policy.json", payload)
    return payload


def validate_base_rate_context(
    context: dict[str, Any], *, output_dir: str | Path | None = None,
    library_dir: str | Path | None = None,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = list(context.get("warnings") or [])
    if context.get("schema_version") != CONTEXT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if context.get("context_fingerprint") != _record_fingerprint(context, "context_fingerprint"):
        invalid.append("context_fingerprint_mismatch")
    queries = context.get("queries")
    if not isinstance(queries, dict):
        invalid.append("queries_not_object"); queries = {}
    pit = _pit_contract(output_dir)
    if pit:
        availability = context.get("availability") if isinstance(context.get("availability"), dict) else {}
        if availability.get("mode") != "PIT_EVIDENCE_ONLY":
            invalid.append("pit_base_rate_context_lacks_isolation_proof")
        if availability.get("base_rate_library") != "UNAVAILABLE_NO_CASE_LEVEL_ADMISSION":
            invalid.append("pit_base_rate_library_must_be_unavailable")
        cases, events, case_errors, event_errors = [], [], [], []
    else:
        cases, case_errors = _read_jsonl(_library_dir(library_dir) / "cases.jsonl")
        events, event_errors = _read_jsonl(_library_dir(library_dir) / "events.jsonl")
    invalid.extend(case_errors + event_errors)
    case_map = {str(item.get("case_id")): item for item in cases}
    eligible_ids: set[str] = set()
    for mechanism, query in queries.items():
        if not isinstance(query, dict) or str(query.get("mechanism_key") or "") != str(mechanism):
            invalid.append("query_mechanism_identity_mismatch:" + str(mechanism)); continue
        sample = int(query.get("eligible_sample_size") or 0)
        independent_sample = int(query.get("independent_company_sample_size", sample) or 0)
        refs = query.get("eligible_cases") or []
        if pit and (sample or independent_sample or refs or query.get("empirical_base_rate") is not None):
            invalid.append("pit_base_rate_query_must_be_empty:" + str(mechanism))
        if sample != len(refs):
            invalid.append("eligible_sample_count_mismatch:" + str(mechanism))
        if independent_sample < MIN_EMPIRICAL_SAMPLE and query.get("empirical_base_rate") is not None:
            invalid.append("small_sample_emitted_base_rate:" + str(mechanism))
        if independent_sample >= MIN_EMPIRICAL_SAMPLE and not isinstance(query.get("empirical_base_rate"), dict):
            incomplete.append("eligible_sample_missing_base_rate:" + str(mechanism))
        for ref in refs:
            case_id = str((ref or {}).get("case_id") or "")
            case = case_map.get(case_id)
            if case is None:
                invalid.append("referenced_case_missing:" + case_id); continue
            if case.get("case_fingerprint") != (ref or {}).get("case_fingerprint"):
                invalid.append("referenced_case_fingerprint_mismatch:" + case_id)
            if _case_state(case, events) != "ELIGIBLE":
                invalid.append("referenced_case_no_longer_eligible:" + case_id)
            eligible_ids.add(case_id)
    if output_dir is not None:
        output = Path(output_dir)
        plan = _load(output / "decisive_question_plan.json")
        planned_mechanisms = {
            str(item.get("mechanism_key")) for item in plan.get("selected_questions") or []
            if isinstance(item, dict) and item.get("mechanism_key")
        }
        missing = sorted(planned_mechanisms - set(queries))
        incomplete.extend("decisive_mechanism_not_queried:" + item for item in missing)
        thesis = _load(output / "thesis_test.json")
        for pset in thesis.get("probability_sets") or []:
            if not isinstance(pset, dict):
                continue
            for estimate in pset.get("estimates") or []:
                if not isinstance(estimate, dict) or estimate.get("kind") != "base_rate":
                    continue
                refs = {str(item) for item in estimate.get("source_ids") or []}
                if not refs or any(not item.startswith("CASE:") for item in refs):
                    invalid.append(f"{pset.get('set_id')}:base_rate_requires_case_ids")
                missing_refs = sorted(refs - eligible_ids)
                invalid.extend(f"{pset.get('set_id')}:base_rate_case_not_in_context:{item}" for item in missing_refs)
                if len(refs) < MIN_EMPIRICAL_SAMPLE:
                    invalid.append(f"{pset.get('set_id')}:base_rate_sample_too_small:{len(refs)}")
                selected_cases = [case_map.get(case_id) for case_id in refs]
                company_ids = [_episode_company_id(case) if isinstance(case, dict) else None for case in selected_cases]
                comparability_ids = [
                    _episode_comparability_identity(case) if isinstance(case, dict) else (None, None)
                    for case in selected_cases
                ]
                if any(company_id is None for company_id in company_ids):
                    invalid.append(f"{pset.get('set_id')}:base_rate_source_missing_episode_company_cluster")
                elif len(set(company_ids)) != len(company_ids):
                    invalid.append(f"{pset.get('set_id')}:base_rate_sources_not_independent_company_clusters")
                if any(question_set_id is None or terminal_scope is None for question_set_id, terminal_scope in comparability_ids):
                    invalid.append(f"{pset.get('set_id')}:base_rate_source_missing_common_question_or_terminal_scope")
                elif len({question_set_id for question_set_id, _ in comparability_ids}) != 1:
                    invalid.append(f"{pset.get('set_id')}:base_rate_sources_mixed_common_question_sets")
                elif len({terminal_scope for _, terminal_scope in comparability_ids}) != 1:
                    invalid.append(f"{pset.get('set_id')}:base_rate_sources_mixed_terminal_outcome_scopes")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION, "state": state,
        "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid, "incomplete_findings": incomplete,
        "warnings": warnings, "eligible_case_ids": sorted(eligible_ids),
    }


def evaluate_output_base_rate(
    output_dir: str | Path, *, library_dir: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _load(output / "base_rate_policy.json")
    if not policy:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION, "state": "SKIP", "status": "SKIP",
            "invalid_findings": [], "incomplete_findings": [], "warnings": [], "enforced": False,
        }
    context = _load(output / "base_rate_context.json")
    if not context:
        result = {
            "schema_version": VALIDATION_SCHEMA_VERSION, "state": "INCOMPLETE", "status": "FAIL",
            "invalid_findings": [], "incomplete_findings": ["base_rate_context_missing"], "warnings": [],
        }
    else:
        result = validate_base_rate_context(context, output_dir=output, library_dir=library_dir)
        if policy.get("context_fingerprint") != context.get("context_fingerprint"):
            result["invalid_findings"].append("policy_context_fingerprint_mismatch")
            result["state"] = "INVALID"; result["status"] = "FAIL"
        if policy.get("require_episode_identity") or policy.get("require_case_selection_identity"):
            cases = [] if _pit_contract(output) else _read_jsonl(
                _library_dir(library_dir) / "cases.jsonl"
            )[0]
            case_map = {str(item.get("case_id")): item for item in cases}
            for case_id in result.get("eligible_case_ids") or []:
                case = case_map.get(str(case_id))
                if not case:
                    continue
                episode_validation = validate_case(
                    case,
                    require_episode_identity=bool(policy.get("require_episode_identity")),
                    require_case_selection_identity=bool(policy.get("require_case_selection_identity")),
                )
                result["invalid_findings"].extend(
                    f"{case_id}:{item}" for item in episode_validation["invalid_findings"]
                )
                result["incomplete_findings"].extend(
                    f"{case_id}:{item}" for item in episode_validation["incomplete_findings"]
                )
            result["invalid_findings"] = list(dict.fromkeys(result["invalid_findings"]))
            result["incomplete_findings"] = list(dict.fromkeys(result["incomplete_findings"]))
            result["state"] = "INVALID" if result["invalid_findings"] else "INCOMPLETE" if result["incomplete_findings"] else "REVIEWABLE"
            result["status"] = "FAIL" if result["state"] in {"INVALID", "INCOMPLETE"} else "PASS"
    result["enforced"] = bool(policy.get("enforced"))
    if persist:
        _atomic_write_json(output / "base_rate_validation.json", result)
    return result


def evaluate_library(library_dir: str | Path | None = None, *, persist: bool = True) -> dict[str, Any]:
    root = _library_dir(library_dir)
    cases, case_errors = _read_jsonl(root / "cases.jsonl")
    events, event_errors = _read_jsonl(root / "events.jsonl")
    invalid = list(case_errors + event_errors)
    incomplete: list[str] = []
    warnings: list[str] = []
    states: dict[str, int] = {}
    archetypes: set[str] = set()
    mechanisms: set[str] = set()
    for case in cases:
        validation = validate_case(case)
        invalid.extend(f"{case.get('case_id')}:{item}" for item in validation["invalid_findings"])
        incomplete.extend(f"{case.get('case_id')}:{item}" for item in validation["incomplete_findings"])
        warnings.extend(f"{case.get('case_id')}:{item}" for item in validation["warnings"])
        state = _case_state(case, events)
        states[state] = states.get(state, 0) + 1
        archetypes.update(str(item) for item in case.get("archetype_ids") or [])
        mechanisms.update(str(item) for item in case.get("mechanism_keys") or [])
    case_map = {str(item.get("case_id")): item for item in cases}
    for event in events:
        case = case_map.get(str(event.get("case_id")))
        if case is None:
            invalid.append(f"{event.get('event_id')}:orphan_event")
            continue
        validation = validate_event(event, case)
        invalid.extend(f"{event.get('event_id')}:{item}" for item in validation["invalid_findings"])
        incomplete.extend(f"{event.get('event_id')}:{item}" for item in validation["incomplete_findings"])
    eligible = states.get("ELIGIBLE", 0)
    if eligible < MIN_EMPIRICAL_SAMPLE:
        warnings.append(f"eligible_sample_too_small:{eligible}<{MIN_EMPIRICAL_SAMPLE}")
    state = "INVALID" if invalid else "REVIEWABLE"
    result = {
        "schema_version": "base-rate-library-quality.v1", "generated_at": _now(),
        "state": state, "status": "FAIL" if state == "INVALID" else "PASS",
        "blocking": state == "INVALID", "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)), "warnings": list(dict.fromkeys(warnings)),
        "summary": {"case_count": len(cases), "event_count": len(events), "states": states,
                    "archetype_count": len(archetypes), "mechanism_count": len(mechanisms),
                    "eligible_case_count": eligible},
        "library_fingerprint": library_fingerprint(cases, events),
    }
    if persist:
        root.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(root / "quality_report.json", result)
    return result


def refresh_library_manifest(library_dir: str | Path | None = None) -> dict[str, Any]:
    root = _library_dir(library_dir)
    quality = evaluate_library(root, persist=True)
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION, "updated_at": _now(),
        "library_fingerprint": quality["library_fingerprint"],
        "case_count": quality["summary"]["case_count"],
        "event_count": quality["summary"]["event_count"],
        "minimum_empirical_sample": MIN_EMPIRICAL_SAMPLE,
        "policy": {"append_only": True, "hindsight_leakage_forbidden": True,
                   "mechanism_match_required": True, "company_fact_substitution_forbidden": True},
    }
    _atomic_write_json(root / "manifest.json", payload)
    return payload


def case_monitoring_tasks(
    report_id: str, *, library_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return explicit review tasks; monitoring never promotes a case in place."""
    root = _library_dir(library_dir)
    cases, _ = _read_jsonl(root / "cases.jsonl")
    events, _ = _read_jsonl(root / "events.jsonl")
    tasks: list[dict[str, Any]] = []
    requested_code = next(iter(re.findall(r"\d{5,6}", str(report_id or ""))), "")
    for case in cases:
        case_report_id = str(case.get("report_id") or "")
        case_code = next(iter(re.findall(r"\d{5,6}", case_report_id)), "")
        if case_report_id != str(report_id or "") and not (requested_code and case_code == requested_code):
            continue
        state = _case_state(case, events)
        prediction = case.get("prediction") if isinstance(case.get("prediction"), dict) else {}
        tasks.append({
            "case_id": case.get("case_id"), "case_fingerprint": case.get("case_fingerprint"),
            "state": state, "resolution_due": prediction.get("resolution_due"),
            "prediction_status": prediction.get("status"),
            "next_required_event": (
                "verify_capture_and_record_prediction" if state == "CANDIDATE"
                else "record_outcome" if state == "REVIEWABLE"
                else "independent_eligibility_review" if state == "RESOLVED"
                else None
            ),
            "automatic_promotion_forbidden": True,
        })
    return sorted(tasks, key=lambda item: str(item.get("case_id") or ""))


def build_candidate_cases_from_output(
    output_dir: str | Path, *, library_dir: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    try:
        from scripts.case_selection_register import validate_output_case_selection
    except ModuleNotFoundError:
        from case_selection_register import validate_output_case_selection
    selection_admission = validate_output_case_selection(output)
    if selection_admission.get("state") in {"INVALID", "INCOMPLETE"}:
        return {
            "written": False,
            "error": "case_selection_not_admissible_for_forward_judgment_calibration",
            "case_selection": selection_admission,
        }
    plan = _load(output / "decisive_question_plan.json")
    archetype = _load(output / "company_archetype.json")
    contract = _load(output / "analysis_contract.json")
    if not plan or not archetype:
        return {"written": False, "error": "decisive_question_plan_or_archetype_missing"}
    primary = str((archetype.get("primary_archetype") or {}).get("archetype_id") or "")
    secondary = [str(item.get("archetype_id")) for item in archetype.get("secondary_archetypes") or [] if isinstance(item, dict) and item.get("archetype_id")]
    cutoff = _day(plan.get("generated_at")) or date.today()
    as_of = _day(contract.get("data_as_of") or contract.get("analysis_date")) or cutoff
    source_hash = _file_hash(output / "decisive_question_plan.json")
    results: list[dict[str, Any]] = []
    for question in plan.get("selected_questions") or []:
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("question_id") or "")
        case_id = "CASE:" + _hash({"report": plan.get("report_id"), "question": question_id, "cutoff": cutoff.isoformat()})[:24]
        evidence = [
            {"source_id": name, "source_group_id": name, "sha256": digest,
             "disclosed_at": None, "data_as_of": as_of.isoformat()}
            for name, digest in sorted((plan.get("input_sources") or {}).items())
        ]
        outcome_space = [
            {"scenario_id": str(item.get("explanation_id") or f"scenario-{index+1}"),
             "label": item.get("label"), "mechanism": item.get("mechanism")}
            for index, item in enumerate(question.get("competing_explanations") or [])
            if isinstance(item, dict)
        ]
        record = {
            "schema_version": CASE_SCHEMA_VERSION, "case_id": case_id,
            "case_status_at_capture": "CANDIDATE", "report_id": plan.get("report_id"),
            "as_of": min(as_of, cutoff).isoformat(), "information_cutoff": cutoff.isoformat(),
            "archetype_ids": [item for item in [primary, *secondary] if item],
            "mechanism_keys": [str(question.get("mechanism_key") or "")],
            "variable_keys": list((question.get("decision_link") or {}).get("affected_metric_ids") or []),
            "decisive_question": {key: question.get(key) for key in ("question_id", "topic_family", "question")},
            "source_capture": {"kind": "decisive_question_plan_candidate", "artifact_id": str(output / "decisive_question_plan.json"), "artifact_sha256": source_hash},
            "visible_evidence": evidence,
            "prediction": {"status": "NOT_ASSIGNED", "outcome_space": outcome_space,
                           "resolution_due": (cutoff + timedelta(days=365)).isoformat()},
            "comparability": {
                "population_definition": f"{primary} companies facing {question.get('mechanism_key')}",
                "inclusion_rule": "same mechanism and as-of evidence available before outcome",
                "exclusion_rule": "hindsight leakage, incomparable accounting basis, or unverified outcome",
            },
            "extraction_notes": "候选案例只冻结当时问题结构；披露日期和概率尚未审核，不进入基准率分母。",
        }
        if selection_admission.get("state") == "REVIEWABLE":
            record["case_selection"] = {
                "register_id": selection_admission.get("register_id"),
                "register_fingerprint": selection_admission.get("register_fingerprint"),
                "entry_id": selection_admission.get("entry_id"),
                "outcome_isolation": selection_admission.get("outcome_isolation"),
            }
        results.append(append_case(record, library_dir=library_dir))
    return {"written": all(item.get("written") for item in results), "cases": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Turtle append-only base-rate case library")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit"); audit.add_argument("--library-dir", default="")
    seed = sub.add_parser("seed-output"); seed.add_argument("--output-dir", required=True); seed.add_argument("--library-dir", default="")
    query = sub.add_parser("query"); query.add_argument("--mechanism", required=True); query.add_argument("--archetype", action="append", default=[]); query.add_argument("--library-dir", default="")
    args = parser.parse_args()
    root = args.library_dir or None
    if args.command == "audit":
        result = evaluate_library(root)
    elif args.command == "seed-output":
        result = build_candidate_cases_from_output(args.output_dir, library_dir=root)
    else:
        result = query_cases(mechanism_key=args.mechanism, archetype_ids=args.archetype, library_dir=root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get("state") == "INVALID" or result.get("written") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
