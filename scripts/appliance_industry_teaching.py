#!/usr/bin/env python3
"""Compile the China-appliance J2 read model into teaching-only drills.

This is deliberately not a forecast, scorecard, settlement adapter, or
comparative admission path.  It turns the page-bound J2 mechanism questions
already accepted by :mod:`appliance_industry_j234` into small exercises: state
the competing mechanisms, preserve the unresolved cells, and request the next
piece of evidence.  Every output stays in the existing claim-specific
``TEACHING_CASE / WITHIN_CASE_MECHANISM`` lane.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.appliance_industry_j234 import validate_appliance_j234
from scripts.judgment_historical_training import validate_claim_specific_admission


TEACHING_PACK_SCHEMA = "turtle-cn-appliance-teaching-pack.v1"
TEACHING_LEVEL = "HISTORICAL_SELF_REPLAY"
MEMORY_STATUS = "MODEL_MEMORY_MITIGATED_NOT_EVALUATION_ELIGIBLE"
ALLOWED_OUTPUTS = {"TEACHING_ONLY", "RESEARCH_AGENDA"}
PROHIBITED_OUTPUTS = {
    "FORECAST", "PROBABILITY", "OUTCOME_SETTLEMENT", "METHOD_TRANSFER",
    "METHOD_SCORE", "CJO", "VALUATION", "REPORT", "INVESTMENT",
}
_PACK_KEYS = {
    "schema_version", "training_pack_id", "block_ref", "training_level",
    "memory_status", "result_access", "allowed_outputs", "prohibited_outputs",
    "drills",
}
_BLOCK_REF_KEYS = {"block_id", "schema_version"}
_DRILL_KEYS = {
    "drill_id", "episode_id", "thread_id", "fact_cell_ids", "source_refs",
    "exercise_question", "learner_tasks", "unknown_cell_ids",
    "prohibited_substitutes",
}
_SOURCE_REF_KEYS = {"source_id", "physical_page"}
_FORBIDDEN_KEYS = {
    "price", "market_price", "stock_price", "return", "outcome", "outcome_label",
    "settlement", "forecast", "forecast_probability", "forecast_direction", "probability",
    "score", "method_score", "cjo", "valuation", "buyband", "buy_band", "investment",
    "panel", "peer_panel", "method_transfer",
}


class ApplianceTeachingError(ValueError):
    """Raised when a teaching pack escapes its J2-only boundary."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, f"{path}_must_be_object")
        return item
    for field in sorted(set(item) - allowed):
        _add(findings, f"{path}.contains_unsupported_field:{field}")
    return item


def _require(value: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    text = value.get(field)
    if not _text(text):
        _add(findings, f"{path}.{field}_required")
        return ""
    return str(text).strip()


def _forbidden_paths(value: Any, path: str) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child = f"{path}.{key}"
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_KEYS or lowered.startswith("actual_") or (
                lowered.startswith("result_") and lowered != "result_access"
            ):
                paths.append(child)
            else:
                paths.extend(_forbidden_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _source_ref_key(value: Any) -> tuple[str, int | None]:
    item = _mapping(value)
    page = item.get("physical_page")
    return str(item.get("source_id", "")), page if isinstance(page, int) and not isinstance(page, bool) else None


def _claim_admission(drill_id: str) -> dict[str, Any]:
    """Use the existing claim-specific permission model, not a new authority."""
    return {
        "schema_version": "turtle-claim-specific-admission.v1",
        "artifact_id": f"ADMISSION:{drill_id}",
        "object_class": "TEACHING_CASE",
        "claim_class": "WITHIN_CASE_MECHANISM",
        "allowed_outputs": ["TEACHING_ONLY", "RESEARCH_AGENDA"],
    }


def validate_appliance_teaching_pack(pack: Any, *, block: Any, source_register: Any) -> dict[str, Any]:
    """Validate a closed, one-drill-per-J2-episode teaching curriculum."""
    findings: list[str] = []
    j234 = validate_appliance_j234(block, source_register=source_register)
    findings.extend(f"j234:{finding}" for finding in j234["findings"])
    item = _closed(pack, _PACK_KEYS, "appliance_teaching", findings)
    if item.get("schema_version") != TEACHING_PACK_SCHEMA:
        _add(findings, "appliance_teaching.schema_version_invalid")
    _require(item, "training_pack_id", "appliance_teaching", findings)
    block_ref = _closed(item.get("block_ref"), _BLOCK_REF_KEYS, "appliance_teaching.block_ref", findings)
    block_item = _mapping(block)
    if block_ref.get("block_id") != block_item.get("block_id") or block_ref.get("schema_version") != block_item.get("schema_version"):
        _add(findings, "appliance_teaching.block_ref_mismatch")
    if item.get("training_level") != TEACHING_LEVEL:
        _add(findings, "appliance_teaching.training_level_must_be_historical_self_replay")
    if item.get("memory_status") != MEMORY_STATUS:
        _add(findings, "appliance_teaching.memory_status_must_preserve_non_evaluation_boundary")
    if item.get("result_access") != "NOT_OPENED":
        _add(findings, "appliance_teaching.result_access_must_remain_not_opened")
    if set(_items(item.get("allowed_outputs"))) != ALLOWED_OUTPUTS:
        _add(findings, "appliance_teaching.allowed_outputs_must_remain_teaching_only")
    if not PROHIBITED_OUTPUTS <= set(_items(item.get("prohibited_outputs"))):
        _add(findings, "appliance_teaching.prohibited_outputs_incomplete")
    for path in _forbidden_paths(item, "appliance_teaching"):
        _add(findings, "appliance_teaching.forbidden_field:" + path)

    episodes = {episode.get("episode_id"): episode for episode in _items(block_item.get("episodes")) if _text(_mapping(episode).get("episode_id"))}
    drills = _items(item.get("drills"))
    if len(drills) != len(episodes):
        _add(findings, "appliance_teaching.drills_must_cover_each_j2_episode_once")
    seen_drills: set[str] = set()
    seen_episodes: set[str] = set()
    for index, raw in enumerate(drills):
        path = f"appliance_teaching.drills[{index}]"
        drill = _closed(raw, _DRILL_KEYS, path, findings)
        drill_id = _require(drill, "drill_id", path, findings)
        if drill_id in seen_drills:
            _add(findings, f"{path}.drill_id_duplicate")
        seen_drills.add(drill_id)
        episode_id = _require(drill, "episode_id", path, findings)
        episode = _mapping(episodes.get(episode_id))
        if not episode:
            _add(findings, f"{path}.episode_id_unknown")
            continue
        if episode_id in seen_episodes:
            _add(findings, f"{path}.episode_id_duplicate")
        seen_episodes.add(episode_id)
        threads = {thread.get("thread_id"): thread for thread in _items(episode.get("mechanism_threads")) if _text(_mapping(thread).get("thread_id"))}
        thread = _mapping(threads.get(drill.get("thread_id")))
        if not thread:
            _add(findings, f"{path}.thread_id_unknown")
            continue
        if thread.get("evidence_ceiling") != "MECHANISM_CANDIDATE":
            _add(findings, f"{path}.thread_must_be_mechanism_candidate")
        expected_cells = set(_items(thread.get("evidence_cell_ids")))
        if set(_items(drill.get("fact_cell_ids"))) != expected_cells:
            _add(findings, f"{path}.fact_cell_ids_must_exactly_match_thread")
        cells = {cell.get("cell_id"): cell for cell in _items(episode.get("cells")) if _text(_mapping(cell).get("cell_id"))}
        expected_unknown = {cell_id for cell_id, cell in cells.items() if cell.get("observation_state") in {"UNKNOWN", "EVIDENCE_INELIGIBLE"}}
        if set(_items(drill.get("unknown_cell_ids"))) != expected_unknown:
            _add(findings, f"{path}.unknown_cell_ids_must_preserve_episode_unknowns")
        raw_refs = _items(drill.get("source_refs"))
        refs: set[tuple[str, int | None]] = set()
        for ref_index, raw_ref in enumerate(raw_refs):
            ref_path = f"{path}.source_refs[{ref_index}]"
            ref = _closed(raw_ref, _SOURCE_REF_KEYS, ref_path, findings)
            source_id = _require(ref, "source_id", ref_path, findings)
            page = ref.get("physical_page")
            if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                _add(findings, f"{ref_path}.physical_page_positive_integer_required")
            refs.add((source_id, page if isinstance(page, int) and not isinstance(page, bool) else None))
        if refs != {_source_ref_key(ref) for ref in _items(thread.get("source_refs"))}:
            _add(findings, f"{path}.source_refs_must_exactly_match_thread")
        _require(drill, "exercise_question", path, findings)
        tasks = _items(drill.get("learner_tasks"))
        if len(tasks) != 3 or not all(_text(task) for task in tasks):
            _add(findings, f"{path}.learner_tasks_must_have_three_nonempty_items")
        substitutes = _items(drill.get("prohibited_substitutes"))
        if not substitutes or not all(_text(item) for item in substitutes):
            _add(findings, f"{path}.prohibited_substitutes_required")
        admission = validate_claim_specific_admission(_claim_admission(drill_id))
        if not admission["valid"]:
            _add(findings, f"{path}.existing_teaching_admission_invalid")
    if seen_episodes != set(episodes):
        _add(findings, "appliance_teaching.drills_must_cover_each_j2_episode_once")
    return {"valid": not findings, "findings": findings, "drill_ids": sorted(seen_drills)}


def compile_appliance_teaching_pack(pack: Any, *, block: Any, source_register: Any) -> dict[str, Any]:
    """Produce learner-facing mechanism drills without outcome or investment content."""
    validation = validate_appliance_teaching_pack(pack, block=block, source_register=source_register)
    if not validation["valid"]:
        raise ApplianceTeachingError("appliance_teaching_invalid:" + ",".join(validation["findings"]))
    episodes = {episode["episode_id"]: episode for episode in _items(_mapping(block).get("episodes"))}
    compiled_drills: list[dict[str, Any]] = []
    for drill in _items(_mapping(pack).get("drills")):
        episode = episodes[drill["episode_id"]]
        thread = next(item for item in episode["mechanism_threads"] if item["thread_id"] == drill["thread_id"])
        cells = {cell["cell_id"]: cell for cell in episode["cells"]}
        compiled_drills.append({
            "drill_id": drill["drill_id"],
            "company_id": episode["company_id"],
            "cutoff_id": episode["cutoff_id"],
            "responsibility_boundary": deepcopy(episode["responsibility_boundary"]),
            "exercise_question": drill["exercise_question"],
            "common_fact_cells": [deepcopy(cells[cell_id]) for cell_id in drill["fact_cell_ids"]],
            "competing_mechanisms": {"H_A": thread["h_a"], "H_B": thread["h_b"]},
            "unknown_guardrails": [deepcopy(cells[cell_id]) for cell_id in drill["unknown_cell_ids"]],
            "learner_tasks": deepcopy(drill["learner_tasks"]),
            "prohibited_substitutes": deepcopy(drill["prohibited_substitutes"]),
            "admission": _claim_admission(drill["drill_id"]),
        })
    return {
        "training_pack_id": _mapping(pack)["training_pack_id"],
        "training_state": "READY_FOR_TEACHING_ONLY",
        "learning_authorization": "TEACHING_ONLY",
        "result_access": "NOT_OPENED",
        "evaluation_eligibility": "NOT_ELIGIBLE_MODEL_MEMORY_MITIGATED",
        "drills": compiled_drills,
        "prohibited_outputs": sorted(PROHIBITED_OUTPUTS),
    }
