#!/usr/bin/env python3
"""V3 Phase E gate for competitive explanations, thresholds and probabilities."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_citation import EvidenceRegistry
except ModuleNotFoundError:
    from evidence_citation import EvidenceRegistry


SCHEMA_VERSION = "thesis-test-ledger.v1"
POLICY_VERSION = "thesis-test-policy.v1"
PROBABILITY_KINDS = {"frequency", "base_rate", "analyst_subjective", "scenario_weight"}
THRESHOLD_BASES = {"historical_volatility", "peer_benchmark", "model_sensitivity", "contractual", "accounting_regulatory", "base_rate", "expert_judgment"}
ACTIONS = {"buy", "hold", "increase", "reduce", "avoid", "exit", "reassess"}
OPERATORS = {">", ">=", "<", "<=", "==", "changes_to"}
REQUIRED_TRIGGER_METRICS = {"trigger.buy", "trigger.reduce", "trigger.exit"}
INTERNAL_EVIDENCE = {"report_internal", "report_derivation", "framework_method", "claim_evidence.json", "decision_ledger.json", "valuation_model.json", "thesis_test.json"}
_ANCHOR_PATTERNS = {
    "test": re.compile(r"\[thesis-test:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I),
    "threshold": re.compile(r"\[threshold:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I),
    "probability": re.compile(r"\[probability:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I),
}
_CHAPTER_RE = re.compile(r"^##\s+Ch(\d+)\b", re.M)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {}
    return value if isinstance(value, dict) else {}


def _canonical(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    for key in ("freeze", "generated_at", "updated_at"): value.pop(key, None)
    return value


def thesis_test_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(_canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bind_thesis_test_references(output_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    output = Path(output_dir); chapter_dir = output / "chapters"
    if not chapter_dir.is_dir(): chapter_dir = output
    additions: dict[int, list[str]] = {}
    specs = (
        ("competitive_tests", "test_id", "thesis-test", "竞争解释测试"),
        ("thresholds", "threshold_id", "threshold", "监控阈值"),
        ("probability_sets", "set_id", "probability", "情景概率"),
    )
    for collection, id_key, anchor, label in specs:
        pattern = _ANCHOR_PATTERNS["test" if anchor == "thesis-test" else anchor]
        for item in payload.get(collection) or []:
            if not isinstance(item, dict): continue
            item_id = str(item.get(id_key) or "").strip()
            if not item_id: continue
            for chapter in item.get("chapters") or []:
                if not isinstance(chapter, int): continue
                path = chapter_dir / f"_ch{chapter:02d}.md"
                if not path.is_file(): continue
                text = path.read_text(encoding="utf-8")
                if item_id in pattern.findall(text): continue
                additions.setdefault(chapter, []).append(f"- {label}引用：[{anchor}: {item_id}]")
    changed: list[int] = []
    for chapter, rows in additions.items():
        path = chapter_dir / f"_ch{chapter:02d}.md"; text = path.read_text(encoding="utf-8")
        block = "\n\n### Canonical thesis bindings\n\n" + "\n".join(rows) + "\n"
        path.write_text(text.rstrip() + block, encoding="utf-8"); changed.append(chapter)
    return {"changed_chapters": sorted(changed), "anchors_inserted": sum(map(len, additions.values()))}


def promote_reviewable_thesis_test(output_dir: str | Path, *, report_text: str) -> dict[str, Any]:
    output = Path(output_dir); payload = _read_json(output / "thesis_test.json")
    if not payload: return {"promoted": False, "error": "thesis_test_missing"}
    policy = _read_json(output / "thesis_test_policy.json")
    validation = validate_thesis_test_ledger(
        payload, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
        monitoring_required=bool(policy.get("monitoring_required")),
        required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or REQUIRED_TRIGGER_METRICS),
    )
    if validation.get("state") != "REVIEWABLE":
        return {"promoted": False, "validation": validation}
    promoted = deepcopy(payload); promoted["lifecycle"] = "decision_ready"
    promoted["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    promoted["freeze"]["fingerprint"] = thesis_test_fingerprint(promoted)
    result = persist_thesis_test_ledger(output, promoted, report_text=report_text, allow_frozen_update=True)
    result["promoted"] = bool(result.get("written")); return result


def initialize_thesis_test_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool, monitoring_required: bool = False,
) -> dict[str, Any]:
    payload = {"schema_version": POLICY_VERSION, "run_id": str(run_id), "enforced": bool(enforced),
               "required_trigger_metric_ids": sorted(REQUIRED_TRIGGER_METRICS),
               "monitoring_required": bool(monitoring_required), "created_at": _now()}
    path = Path(output_dir) / "thesis_test_policy.json"; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"); return payload


def build_thesis_test_ledger(output_dir: str | Path, competitive_tests: list[dict[str, Any]], thresholds: list[dict[str, Any]], probability_sets: list[dict[str, Any]], *, change_reason: str, freeze: bool = True) -> dict[str, Any]:
    output = Path(output_dir); contract = _read_json(output / "analysis_contract.json")
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "report_id": str(contract.get("ts_code") or contract.get("code") or output.name), "revision": 1, "lifecycle": "decision_ready" if freeze else "reviewable", "change_reason": str(change_reason or "").strip(), "competitive_tests": deepcopy(competitive_tests), "thresholds": deepcopy(thresholds), "probability_sets": deepcopy(probability_sets), "generated_at": _now()}
    payload["freeze"] = {"frozen": bool(freeze), "fingerprint": thesis_test_fingerprint(payload) if freeze else "", "frozen_at": _now() if freeze else None}
    return payload


def _chapters(report_text: str) -> dict[int, str]:
    matches = list(_CHAPTER_RE.finditer(report_text)); result: dict[int, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(report_text); result[int(match.group(1))] = report_text[match.start():end]
    return result


def _num(value: Any) -> float | None:
    try: result = float(value)
    except (TypeError, ValueError): return None
    return result if math.isfinite(result) else None


def _decimals(value: Any) -> int:
    text = str(value)
    return len(text.rstrip("0").split(".", 1)[1]) if "." in text else 0


def _ids(payload: dict[str, Any], key: str) -> set[str]:
    return {str(item.get(key)) for item in payload if isinstance(item, dict) and item.get(key)}


def validate_thesis_test_ledger(payload: dict[str, Any], *, output_dir: str | Path | None = None, report_text: str = "", enforced: bool = False, monitoring_required: bool = False, required_trigger_metric_ids: set[str] | frozenset[str] = REQUIRED_TRIGGER_METRICS) -> dict[str, Any]:
    invalid: list[str] = []; incomplete: list[str] = []; warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION: invalid.append("schema_version_invalid")
    if not str(payload.get("report_id") or "").strip(): invalid.append("report_id_missing")
    if not str(payload.get("change_reason") or "").strip(): incomplete.append("change_reason_missing")
    output = Path(output_dir) if output_dir is not None else None
    registry = EvidenceRegistry()
    if output is not None and output.is_dir(): registry.register_from_output_dir(str(output))
    claim_ledger = _read_json(output / "claim_evidence.json") if output is not None else {}
    claim_ids = _ids(claim_ledger.get("claims") or [], "claim_id")
    evidence = {str(item.get("evidence_id")): item for claim in claim_ledger.get("claims") or [] if isinstance(claim, dict) for item in claim.get("raw_facts") or [] if isinstance(item, dict) and item.get("evidence_id")}
    decisions = {str(item.get("entry_id")): item for item in (_read_json(output / "decision_ledger.json").get("entries") or []) if isinstance(item, dict) and item.get("entry_id") and item.get("status") == "active"} if output is not None else {}
    chapter_text = _chapters(report_text)

    tests = payload.get("competitive_tests"); thresholds = payload.get("thresholds"); probability_sets = payload.get("probability_sets")
    if not isinstance(tests, list): invalid.append("competitive_tests_not_array"); tests = []
    if not isinstance(thresholds, list): invalid.append("thresholds_not_array"); thresholds = []
    if not isinstance(probability_sets, list): invalid.append("probability_sets_not_array"); probability_sets = []
    if enforced and not tests: incomplete.append("competitive_test_missing")
    test_ids = _ids(tests, "test_id"); threshold_ids = _ids(thresholds, "threshold_id"); probability_ids = _ids(probability_sets, "set_id")
    for items, key, label in ((tests, "test_id", "test"), (thresholds, "threshold_id", "threshold"), (probability_sets, "set_id", "probability_set")):
        values = [str(item.get(key)) for item in items if isinstance(item, dict) and item.get(key)]
        if len(values) != len(set(values)): invalid.append("duplicate_" + label + "_id")

    for idx, pset in enumerate(probability_sets):
        prefix = f"probability_sets[{idx}]"
        if not isinstance(pset, dict): invalid.append(prefix + ":not_object"); continue
        sid = str(pset.get("set_id") or prefix)
        if pset.get("mutually_exclusive") is not True: invalid.append(f"{sid}:not_mutually_exclusive")
        if pset.get("collectively_exhaustive") is not True: invalid.append(f"{sid}:not_collectively_exhaustive")
        estimates = pset.get("estimates")
        if not isinstance(estimates, list) or len(estimates) < 2: invalid.append(f"{sid}:estimates_invalid"); estimates = []
        scenario_ids = [str(item.get("scenario_id")) for item in estimates if isinstance(item, dict)]
        if len(scenario_ids) != len(set(scenario_ids)): invalid.append(f"{sid}:duplicate_scenario_id")
        total = 0.0
        for eidx, estimate in enumerate(estimates):
            ep = f"{sid}.estimates[{eidx}]"
            if not isinstance(estimate, dict): invalid.append(ep + ":not_object"); continue
            value = _num(estimate.get("value")); kind = estimate.get("kind")
            if not str(estimate.get("scenario_id") or "").strip(): invalid.append(ep + ":scenario_id_missing")
            if not str(estimate.get("label") or "").strip(): incomplete.append(ep + ":label_missing")
            if kind not in PROBABILITY_KINDS: invalid.append(ep + ":kind_invalid")
            if value is None or not 0 <= value <= 1: invalid.append(ep + ":value_invalid")
            else: total += value
            if not str(estimate.get("basis") or "").strip(): incomplete.append(ep + ":basis_missing")
            interval = estimate.get("interval")
            if not isinstance(interval, list) or len(interval) != 2 or any(_num(v) is None for v in interval): invalid.append(ep + ":interval_invalid")
            else:
                lo, hi = float(interval[0]), float(interval[1])
                if not (0 <= lo <= hi <= 1) or (value is not None and not lo <= value <= hi): invalid.append(ep + ":interval_inconsistent")
                if kind == "analyst_subjective" and hi - lo < 0.10 and not str(estimate.get("calibration_history_id") or "").strip(): invalid.append(ep + ":subjective_false_precision")
            sources = estimate.get("source_ids") or []
            if kind in {"frequency", "base_rate"} and not sources: incomplete.append(ep + ":empirical_source_missing")
            for source in sources:
                canonical, unresolved = registry.canonicalize_anchor(str(source))
                if output is not None and (unresolved or not canonical): invalid.append(ep + f":source_unresolved:{source}")
                elif canonical and set(canonical).issubset(INTERNAL_EVIDENCE): invalid.append(ep + ":circular_internal_source")
            if kind == "analyst_subjective" and _decimals(estimate.get("value")) > 2 and not estimate.get("calibration_history_id"): invalid.append(ep + ":subjective_probability_overprecise")
            if not str(estimate.get("as_of") or "").strip(): incomplete.append(ep + ":as_of_missing")
        if estimates and not math.isclose(total, 1.0, abs_tol=0.01): invalid.append(f"{sid}:probabilities_not_sum_to_one:{total:.4f}")
        if monitoring_required:
            due = str(pset.get("resolution_due") or "").strip()
            try:
                due_date = datetime.fromisoformat(due[:10]).date()
                as_of_dates = [datetime.fromisoformat(str(item.get("as_of"))[:10]).date() for item in estimates if item.get("as_of")]
            except ValueError:
                invalid.append(f"{sid}:resolution_due_invalid")
            else:
                if not as_of_dates or due_date <= max(as_of_dates):
                    invalid.append(f"{sid}:resolution_due_not_after_prediction")
        chapters = pset.get("chapters") or []
        if not isinstance(chapters, list) or not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters): invalid.append(f"{sid}:chapters_invalid")
        elif enforced:
            for chapter in chapters:
                if sid not in _ANCHOR_PATTERNS["probability"].findall(chapter_text.get(int(chapter), "")): incomplete.append(f"probability_reference_missing:Ch{chapter}:{sid}")

    covered_trigger_metrics: set[str] = set()
    for idx, threshold in enumerate(thresholds):
        prefix = f"thresholds[{idx}]"
        if not isinstance(threshold, dict): invalid.append(prefix + ":not_object"); continue
        tid = str(threshold.get("threshold_id") or prefix)
        for key in ("metric", "unit", "operator", "basis_description", "observation_frequency", "window", "aggregation", "accounting_definition", "discrimination_target"):
            if not str(threshold.get(key) or "").strip(): incomplete.append(f"{tid}:{key}_missing")
        current, value = _num(threshold.get("current_value")), _num(threshold.get("threshold_value"))
        if current is None or value is None: invalid.append(f"{tid}:numeric_value_invalid")
        if threshold.get("basis_type") not in THRESHOLD_BASES: invalid.append(f"{tid}:basis_type_invalid")
        if threshold.get("action") not in ACTIONS: invalid.append(f"{tid}:action_invalid")
        if threshold.get("operator") not in OPERATORS: invalid.append(f"{tid}:operator_invalid")
        if threshold.get("aggregation") not in {"single_period", "rolling_average", "consecutive_periods", "cumulative"}: invalid.append(f"{tid}:aggregation_invalid")
        if threshold.get("seasonal_adjustment") not in {"adjusted", "not_needed", "unavailable"}: incomplete.append(f"{tid}:seasonal_adjustment_missing")
        precision = threshold.get("precision") or {}
        if not isinstance(precision, dict): invalid.append(f"{tid}:precision_invalid"); precision = {}
        justified = precision.get("justified_decimals")
        if not isinstance(justified, int) or justified < 0: invalid.append(f"{tid}:precision_invalid")
        elif value is not None and _decimals(threshold.get("threshold_value")) > justified: invalid.append(f"{tid}:pseudo_precision")
        if not str(precision.get("basis") or "").strip(): incomplete.append(f"{tid}:precision_basis_missing")
        if threshold.get("basis_type") == "expert_judgment":
            warnings.append(f"{tid}:expert_judgment_threshold")
            if threshold.get("decision_entry_ids") and not str(threshold.get("independent_validation") or "").strip(): incomplete.append(f"{tid}:expert_judgment_trigger_needs_validation")
        if threshold.get("discrimination_target") not in test_ids | {"decision_rule"}: invalid.append(f"{tid}:unknown_discrimination_target")
        sources = threshold.get("source_ids") or []
        if not sources: incomplete.append(f"{tid}:source_ids_missing")
        for source in sources:
            canonical, unresolved = registry.canonicalize_anchor(str(source))
            if output is not None and (unresolved or not canonical): invalid.append(f"{tid}:source_unresolved:{source}")
            elif canonical and set(canonical).issubset(INTERNAL_EVIDENCE): invalid.append(f"{tid}:circular_internal_source")
        refs = threshold.get("decision_entry_ids") or []
        if not refs: incomplete.append(f"{tid}:decision_entry_ids_missing")
        for ref in refs:
            entry = decisions.get(str(ref))
            if output is not None and entry is None: invalid.append(f"{tid}:unknown_decision_entry:{ref}")
            elif entry and entry.get("metric_id") in REQUIRED_TRIGGER_METRICS:
                metric_id = str(entry.get("metric_id")); covered_trigger_metrics.add(metric_id)
                allowed_actions = {"trigger.buy": {"buy", "increase"}, "trigger.reduce": {"reduce", "reassess"}, "trigger.exit": {"exit", "avoid"}}
                if threshold.get("action") not in allowed_actions[metric_id]: invalid.append(f"{tid}:action_decision_trigger_mismatch:{metric_id}")
        chapters = threshold.get("chapters") or []
        if not isinstance(chapters, list) or not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters): invalid.append(f"{tid}:chapters_invalid")
        elif enforced:
            for chapter in chapters:
                if tid not in _ANCHOR_PATTERNS["threshold"].findall(chapter_text.get(int(chapter), "")): incomplete.append(f"threshold_reference_missing:Ch{chapter}:{tid}")
    if enforced:
        for metric in sorted(set(required_trigger_metric_ids) - covered_trigger_metrics): incomplete.append("decision_trigger_threshold_missing:" + metric)

    for idx, test in enumerate(tests):
        prefix = f"competitive_tests[{idx}]"
        if not isinstance(test, dict): invalid.append(prefix + ":not_object"); continue
        tid = str(test.get("test_id") or prefix)
        claim_id = str(test.get("thesis_claim_id") or "")
        if output is not None and claim_id not in claim_ids: invalid.append(f"{tid}:unknown_thesis_claim:{claim_id}")
        for key in ("primary_explanation", "strongest_alternative"):
            if not str(test.get(key) or "").strip(): incomplete.append(f"{tid}:{key}_missing")
        if str(test.get("primary_explanation") or "").strip() == str(test.get("strongest_alternative") or "").strip(): invalid.append(f"{tid}:alternative_not_competitive")
        alt_evidence = test.get("alternative_evidence_ids") or []
        if not alt_evidence: incomplete.append(f"{tid}:alternative_evidence_missing")
        for eid in alt_evidence:
            if output is not None and str(eid) not in evidence: invalid.append(f"{tid}:unknown_alternative_evidence:{eid}")
            elif evidence.get(str(eid), {}).get("support_type") not in {"contradicts", "context"}: invalid.append(f"{tid}:alternative_evidence_does_not_support_alternative:{eid}")
        observations = test.get("discriminating_observations")
        if not isinstance(observations, list) or not observations: incomplete.append(f"{tid}:discriminating_observation_missing"); observations = []
        for oidx, obs in enumerate(observations):
            op = f"{tid}.observations[{oidx}]"
            if not isinstance(obs, dict): invalid.append(op + ":not_object"); continue
            for key in ("observation_id", "metric", "availability", "primary_prediction", "alternative_prediction", "update_rule"):
                if not str(obs.get(key) or "").strip(): incomplete.append(f"{op}:{key}_missing")
            if str(obs.get("primary_prediction") or "").strip() == str(obs.get("alternative_prediction") or "").strip(): invalid.append(f"{op}:predictions_not_discriminating")
            if obs.get("threshold_id") not in threshold_ids: invalid.append(f"{op}:unknown_threshold")
        probability_set_id = test.get("probability_set_id")
        if probability_set_id not in probability_ids: invalid.append(f"{tid}:unknown_probability_set")
        else:
            selected = next((
                item for item in probability_sets
                if isinstance(item, dict) and item.get("set_id") == probability_set_id
            ), {})
            scenarios = _ids(selected.get("estimates") or [], "scenario_id")
            if test.get("primary_scenario_id") not in scenarios: invalid.append(f"{tid}:primary_scenario_unknown")
            if test.get("alternative_scenario_id") not in scenarios: invalid.append(f"{tid}:alternative_scenario_unknown")
            if test.get("primary_scenario_id") == test.get("alternative_scenario_id"): invalid.append(f"{tid}:scenario_mapping_not_distinct")
        flip = test.get("flip_condition") or {}
        if not isinstance(flip, dict):
            invalid.append(f"{tid}:flip_condition_invalid")
            flip = {}
        if flip.get("threshold_id") not in threshold_ids: invalid.append(f"{tid}:flip_threshold_unknown")
        for key in ("basis", "window"):
            if not str(flip.get(key) or "").strip(): incomplete.append(f"{tid}:flip_{key}_missing")
        if _num(test.get("valuation_after_flip")) is None: invalid.append(f"{tid}:valuation_after_flip_invalid")
        if _num(test.get("position_after_flip")) is None: invalid.append(f"{tid}:position_after_flip_invalid")
        if test.get("action_after_flip") not in ACTIONS: invalid.append(f"{tid}:action_after_flip_invalid")
        refs = test.get("decision_entry_ids") or []
        if not refs: incomplete.append(f"{tid}:decision_entry_ids_missing")
        for ref in refs:
            if output is not None and str(ref) not in decisions: invalid.append(f"{tid}:unknown_decision_entry:{ref}")
        chapters = test.get("chapters") or []
        if not isinstance(chapters, list) or not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters): invalid.append(f"{tid}:chapters_invalid")
        elif enforced:
            for chapter in chapters:
                if tid not in _ANCHOR_PATTERNS["test"].findall(chapter_text.get(int(chapter), "")): incomplete.append(f"thesis_test_reference_missing:Ch{chapter}:{tid}")

    known = {"test": test_ids, "threshold": threshold_ids, "probability": probability_ids}
    for kind, pattern in _ANCHOR_PATTERNS.items():
        for ref in sorted(set(pattern.findall(report_text)) - known[kind]): invalid.append(f"unknown_{kind}_reference:{ref}")
    frozen = bool((payload.get("freeze") or {}).get("frozen"))
    if frozen and (payload.get("freeze") or {}).get("fingerprint") != thesis_test_fingerprint(payload): invalid.append("freeze_fingerprint_mismatch")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "MONITORING" if payload.get("lifecycle") == "monitoring" else "DECISION_READY" if frozen else "REVIEWABLE"
    return {"schema_version": "thesis-test-validation.v1", "state": state, "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS", "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings, "competitive_test_ids": sorted(test_ids), "threshold_ids": sorted(threshold_ids), "probability_set_ids": sorted(probability_ids), "covered_trigger_metric_ids": sorted(covered_trigger_metrics), "enforced": bool(enforced)}


def persist_thesis_test_ledger(output_dir: str | Path, payload: dict[str, Any], *, report_text: str = "", allow_frozen_update: bool = False) -> dict[str, Any]:
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True); path = output / "thesis_test.json"; diff_path = output / "thesis_test_diff.json"
    old = _read_json(path); policy = _read_json(output / "thesis_test_policy.json")
    validation = validate_thesis_test_ledger(payload, output_dir=output, report_text=report_text, enforced=bool(policy.get("enforced")), monitoring_required=bool(policy.get("monitoring_required")), required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or REQUIRED_TRIGGER_METRICS))
    if validation["state"] == "INVALID" or (validation["state"] == "INCOMPLETE" and bool((payload.get("freeze") or {}).get("frozen"))):
        # Preserve the exact structured candidate.  A validation report alone
        # cannot be repaired deterministically because it contains field paths
        # but not the submitted values.  This also prevents a fresh-context
        # model from reconstructing a large ledger and repeating the same
        # schema mistakes at additional cost.
        (output / "thesis_test_last_rejected.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "thesis_test_last_rejected_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": False, "path": str(path), "validation": validation, "error": "invalid or incomplete thesis test cannot be frozen"}
    changed = bool(old) and thesis_test_fingerprint(old) != thesis_test_fingerprint(payload)
    diff = {"schema_version": "thesis-test-diff.v1", "generated_at": _now(), "old_fingerprint": thesis_test_fingerprint(old) if old else None, "new_fingerprint": thesis_test_fingerprint(payload), "change_reason": payload.get("change_reason")}
    if old and bool((old.get("freeze") or {}).get("frozen")) and changed and not allow_frozen_update:
        diff["status"] = "REJECTED_FROZEN"; diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": False, "path": str(path), "diff_path": str(diff_path), "thesis_test_frozen": True, "validation": validation, "error": "frozen thesis test rejected update"}
    if old and not changed:
        expected = thesis_test_fingerprint(old)
        old_fingerprint_valid = (
            (old.get("freeze") or {}).get("fingerprint") == expected
        )
        supplied_fingerprint_valid = (
            (payload.get("freeze") or {}).get("fingerprint")
            == thesis_test_fingerprint(payload)
        )
        if (
            allow_frozen_update
            and not old_fingerprint_valid
            and supplied_fingerprint_valid
        ):
            diff["status"] = "METADATA_REPAIRED"
            ledger = payload
        else:
            diff["status"] = "NO_CHANGE"
            ledger = old
    else:
        diff["status"] = "APPLIED" if old else "INITIALIZED"
        ledger = payload
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"); diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": True, "path": str(path), "diff_path": str(diff_path), "ledger": ledger, "validation": validation, "diff": diff}


def evaluate_output_thesis_test(output_dir: str | Path, *, report_text: str = "", persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir); policy = _read_json(output / "thesis_test_policy.json"); ledger = _read_json(output / "thesis_test.json"); enforced = bool(policy.get("enforced"))
    if not ledger:
        state = "INCOMPLETE" if enforced else "SKIP"; result = {"schema_version": "thesis-test-validation.v1", "state": state, "status": "FAIL" if enforced else "SKIP", "invalid_findings": [], "incomplete_findings": ["thesis_test_missing"] if enforced else [], "warnings": [], "enforced": enforced, "policy": policy}
    else:
        result = validate_thesis_test_ledger(ledger, output_dir=output, report_text=report_text, enforced=enforced, monitoring_required=bool(policy.get("monitoring_required")), required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or REQUIRED_TRIGGER_METRICS)); result["policy"] = policy
    if persist: (output / "thesis_test_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
