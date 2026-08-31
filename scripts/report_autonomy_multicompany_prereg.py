#!/usr/bin/env python3
"""Validate the pre-outcome control plane for one 8-case report-autonomy 2x2.

This module deliberately validates only a frozen experiment register.  It
does not select companies, render a report, read an outcome, or score an arm.
The existing enterprise-underwriting v2 validator remains the authority for
each individual arm contract; this layer makes sure thirty-two otherwise-valid
contracts still mean the same comparative experiment.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.enterprise_underwriting_training import (
        CONTRACT_SCHEMA,
        SUBAGENT_TASK_SCHEMA,
        build_fresh_subagent_task,
        validate_training_contract,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.enterprise_underwriting_training import (
        CONTRACT_SCHEMA,
        SUBAGENT_TASK_SCHEMA,
        build_fresh_subagent_task,
        validate_training_contract,
    )


SCHEMA_VERSION = "report-autonomy-multicompany-preregistration.v1"
VALIDATION_SCHEMA_VERSION = "report-autonomy-multicompany-preregistration-validation.v1"
ARMS = ("A00", "A01", "A10", "A11")
CASE_COUNT = 8
CELL_COUNT = CASE_COUNT * len(ARMS)

_ROOT_FIELDS = {
    "schema_version",
    "preregistration_id",
    "state",
    "cohort",
    "cases",
    "execution",
    "anonymous_review_custody",
    "outcome_measurements",
    "outcome_access_gate",
}
_COHORT_FIELDS = {
    "selection_policy",
    "replacement_policy",
    "replacement_records",
    "strata",
    "candidate_universe",
}
_STRATUM_FIELDS = {"stratum_id", "quota"}
_CANDIDATE_FIELDS = {
    "candidate_id",
    "company_id",
    "company_name",
    "cutoff_at",
    "stratum_id",
    "rank_in_stratum",
    "eligibility",
    "exclusion_reason",
}
_CASE_FIELDS = {
    "case_id",
    "candidate_id",
    "selection_rank",
    "company_id",
    "company_name",
    "cutoff_at",
    "stratum_id",
    "common_source_package_ref",
    "common_sources",
    "industry_memory",
    "expert_memory",
}
_SOURCE_FIELDS = {"source_id", "source_ref", "available_at", "time_role"}
_MEMORY_FIELDS = _SOURCE_FIELDS | {
    "memory_kind",
    "company_free",
    "target_company_evidence_allowed",
    "exposure_register_ref",
}
_EXECUTION_FIELDS = {
    "schema_version", "retry_policy", "cell_budget", "tool_policy", "schedule", "cells",
}
_BUDGET_FIELDS = {
    "episode_attempts",
    "reader_report_attempts",
    "max_episode_words",
    "max_reader_report_words",
    "episode_time_limit_seconds",
    "reader_report_time_limit_seconds",
}
_TOOL_POLICY = {
    "network_access": "PROHIBITED",
    "repository_browsing": "PROHIBITED",
    "parent_context_access": "PROHIBITED",
    "sibling_output_access": "PROHIBITED",
    "outcome_price_return_access": "PROHIBITED",
}
_CELL_FIELDS = {
    "case_id",
    "arm_id",
    "source_package_ref",
    "training_contract",
    "rendered_task",
    "state",
    "attempts",
    "artifact_paths",
}
_ATTEMPT_FIELDS = {"episode", "reader_report"}
_ARTIFACT_PATH_FIELDS = {
    "contract_ref",
    "rendered_task_ref",
    "raw_response_ref",
    "episode_ref",
    "reader_bridge_ref",
    "first_reader_report_ref",
    "freeze_receipt_ref",
}
_CUSTODY_FIELDS = {"mapping", "reviewer_manifest"}
_MAPPING_FIELDS = {"case_id", "arm_id", "anonymous_label", "source_package_ref"}
_MANIFEST_FIELDS = {
    "case_id",
    "anonymous_label",
    "source_package_ref",
    "episode_ref",
    "reader_bridge_ref",
    "first_reader_report_ref",
}
_MEASUREMENT_FIELDS = {
    "case_id",
    "company_id",
    "cutoff_at",
    "measurement_contract_ref",
    "outcome_window",
    "official_source_category",
    "first_complete_annual_report_rule",
    "field_boundary_rule",
    "mismatch_rule",
    "disposition_rule",
}
_OUTCOME_GATE_FIELDS = {
    "state",
    "outcome_access_authorized",
    "required_reviewer_freeze_receipts",
}

_OUTCOME_GATE_STATE = "BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN"
_CELL_STATES = {"NOT_STARTED", "EPISODE_INVALID", "FROZEN", "PAIRED_TEST_INVALID"}
_ARM_MEMORY_KINDS = {
    "A00": set(),
    "A01": {"INDUSTRY_DECISION_MEMORY"},
    "A10": {"EXPERT_CORRECTION_MEMORY"},
    "A11": {"INDUSTRY_DECISION_MEMORY", "EXPERT_CORRECTION_MEMORY"},
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(
    value: Any,
    allowed: set[str],
    path: str,
    findings: list[str],
) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, path + ".must_be_object")
        return item
    extra = sorted(set(item) - allowed)
    if extra:
        _add(findings, path + ".unexpected_fields:" + ",".join(extra))
    missing = sorted(allowed - set(item))
    if missing:
        _add(findings, path + ".missing_fields:" + ",".join(missing))
    return item


def _unique_texts(
    records: list[dict[str, Any]], field: str, path: str, findings: list[str],
) -> set[str]:
    values: set[str] = set()
    for index, record in enumerate(records):
        value = _text(record.get(field))
        if not value or value in values:
            _add(findings, f"{path}[{index}].{field}_missing_or_duplicate")
        else:
            values.add(value)
    return values


def _exact_fields(item: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    """Keep a directly comparable projection without inventing normalizers."""

    return {field: deepcopy(item.get(field)) for field in sorted(fields)}


def _expected_episode_order(rank: int) -> list[str]:
    base = list(ARMS)
    return base[((rank - 1) % 4):] + base[:((rank - 1) % 4)]


def _validate_memory(
    raw: Any,
    *,
    expected_kind: str,
    path: str,
    findings: list[str],
) -> dict[str, Any]:
    item = _closed(raw, _MEMORY_FIELDS, path, findings)
    for field in ("source_id", "source_ref", "available_at", "exposure_register_ref"):
        if not _text(item.get(field)):
            _add(findings, path + "." + field + "_required")
    if item.get("time_role") != "TRAINING_MEMORY":
        _add(findings, path + ".time_role_must_be_training_memory")
    if item.get("memory_kind") != expected_kind:
        _add(findings, path + ".memory_kind_invalid")
    if item.get("company_free") is not True:
        _add(findings, path + ".must_be_company_free")
    if item.get("target_company_evidence_allowed") is not False:
        _add(findings, path + ".target_company_evidence_must_be_prohibited")
    return item


def _validate_candidates(
    cohort: dict[str, Any], cases: list[dict[str, Any]], findings: list[str],
) -> None:
    strata = [
        _closed(item, _STRATUM_FIELDS, f"cohort.strata[{index}]", findings)
        for index, item in enumerate(_items(cohort.get("strata")))
    ]
    stratum_ids = _unique_texts(strata, "stratum_id", "cohort.strata", findings)
    quotas: dict[str, int] = {}
    for index, stratum in enumerate(strata):
        quota = stratum.get("quota")
        if not isinstance(quota, int) or isinstance(quota, bool) or quota < 1:
            _add(findings, f"cohort.strata[{index}].quota_must_be_positive_integer")
        else:
            quotas[str(stratum.get("stratum_id"))] = quota
    if sum(quotas.values()) != CASE_COUNT:
        _add(findings, "cohort.strata_quotas_must_sum_to_eight")

    candidates = [
        _closed(item, _CANDIDATE_FIELDS, f"cohort.candidate_universe[{index}]", findings)
        for index, item in enumerate(_items(cohort.get("candidate_universe")))
    ]
    candidate_ids = _unique_texts(candidates, "candidate_id", "cohort.candidate_universe", findings)
    for index, candidate in enumerate(candidates):
        for field in ("company_id", "company_name", "cutoff_at", "stratum_id"):
            if not _text(candidate.get(field)):
                _add(findings, f"cohort.candidate_universe[{index}].{field}_required")
        if candidate.get("stratum_id") not in stratum_ids:
            _add(findings, f"cohort.candidate_universe[{index}].stratum_not_registered")
        rank = candidate.get("rank_in_stratum")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            _add(findings, f"cohort.candidate_universe[{index}].rank_invalid")
        eligibility = candidate.get("eligibility")
        reason = _text(candidate.get("exclusion_reason"))
        if eligibility not in {"ELIGIBLE", "EXCLUDED"}:
            _add(findings, f"cohort.candidate_universe[{index}].eligibility_invalid")
        elif eligibility == "ELIGIBLE" and reason != "NOT_APPLICABLE":
            _add(findings, f"cohort.candidate_universe[{index}].eligible_requires_not_applicable_exclusion_reason")
        elif eligibility == "EXCLUDED" and not reason:
            _add(findings, f"cohort.candidate_universe[{index}].excluded_requires_reason")

    candidate_by_id = {
        _text(candidate.get("candidate_id")): candidate
        for candidate in candidates
        if _text(candidate.get("candidate_id"))
    }
    selected_by_stratum: dict[str, list[dict[str, Any]]] = {}
    for index, case in enumerate(cases):
        candidate = candidate_by_id.get(_text(case.get("candidate_id")))
        if candidate is None:
            _add(findings, f"cases[{index}].candidate_not_in_universe")
            continue
        if candidate.get("eligibility") != "ELIGIBLE":
            _add(findings, f"cases[{index}].candidate_not_eligible")
        for field in ("company_id", "company_name", "cutoff_at", "stratum_id"):
            if case.get(field) != candidate.get(field):
                _add(findings, f"cases[{index}].candidate_{field}_mismatch")
        selected_by_stratum.setdefault(str(case.get("stratum_id")), []).append(candidate)

    for stratum_id, quota in quotas.items():
        selected = selected_by_stratum.get(stratum_id, [])
        if len(selected) != quota:
            _add(findings, "cohort.stratum_selected_count_mismatch:" + stratum_id)
            continue
        eligible = sorted(
            (
                candidate for candidate in candidates
                if candidate.get("stratum_id") == stratum_id
                and candidate.get("eligibility") == "ELIGIBLE"
            ),
            key=lambda item: item.get("rank_in_stratum", 10**9),
        )
        selected_ids = [
            item.get("candidate_id")
            for item in sorted(selected, key=lambda item: item.get("rank_in_stratum", 10**9))
        ]
        eligible_ids = [item.get("candidate_id") for item in eligible[:quota]]
        if selected_ids != eligible_ids:
            _add(findings, "cohort.selection_must_use_first_eligible_rank:" + stratum_id)

    if len(candidate_ids) != len(candidates):
        return


def _validate_cases(bundle: dict[str, Any], findings: list[str]) -> dict[str, dict[str, Any]]:
    cohort = _closed(bundle.get("cohort"), _COHORT_FIELDS, "cohort", findings)
    if cohort.get("selection_policy") != "CUTOFF_ONLY_FIXED_STRATUM_RANK":
        _add(findings, "cohort.selection_policy_invalid")
    if cohort.get("replacement_policy") != "NO_REPLACEMENTS_AFTER_COHORT_FREEZE":
        _add(findings, "cohort.replacement_policy_invalid")
    if cohort.get("replacement_records") != []:
        _add(findings, "cohort.replacement_records_must_be_empty")

    cases = [
        _closed(item, _CASE_FIELDS, f"cases[{index}]", findings)
        for index, item in enumerate(_items(bundle.get("cases")))
    ]
    if len(cases) != CASE_COUNT:
        _add(findings, "cases.must_contain_exactly_eight")
    _unique_texts(cases, "case_id", "cases", findings)
    _unique_texts(cases, "company_id", "cases", findings)
    ranks = [case.get("selection_rank") for case in cases]
    if sorted(ranks) != list(range(1, CASE_COUNT + 1)):
        _add(findings, "cases.selection_ranks_must_be_one_through_eight")

    for index, case in enumerate(cases):
        for field in (
            "candidate_id", "company_id", "company_name", "cutoff_at",
            "stratum_id", "common_source_package_ref",
        ):
            if not _text(case.get(field)):
                _add(findings, f"cases[{index}].{field}_required")
        sources = [
            _closed(raw, _SOURCE_FIELDS, f"cases[{index}].common_sources[{source_index}]", findings)
            for source_index, raw in enumerate(_items(case.get("common_sources")))
        ]
        if not sources:
            _add(findings, f"cases[{index}].common_sources_required")
        for source_index, source in enumerate(sources):
            for field in ("source_id", "source_ref", "available_at"):
                if not _text(source.get(field)):
                    _add(findings, f"cases[{index}].common_sources[{source_index}].{field}_required")
            if source.get("time_role") != "PRE_CUTOFF":
                _add(findings, f"cases[{index}].common_sources[{source_index}].must_be_pre_cutoff")
        _unique_texts(sources, "source_id", f"cases[{index}].common_sources", findings)
        _unique_texts(sources, "source_ref", f"cases[{index}].common_sources", findings)
        _validate_memory(
            case.get("industry_memory"),
            expected_kind="INDUSTRY_DECISION_MEMORY",
            path=f"cases[{index}].industry_memory",
            findings=findings,
        )
        _validate_memory(
            case.get("expert_memory"),
            expected_kind="EXPERT_CORRECTION_MEMORY",
            path=f"cases[{index}].expert_memory",
            findings=findings,
        )

    _validate_candidates(cohort, cases, findings)
    return {
        _text(case.get("case_id")): case for case in cases if _text(case.get("case_id"))
    }


def _contract_common_projection(contract: dict[str, Any]) -> dict[str, Any]:
    projection = deepcopy(contract)
    projection.pop("contract_id", None)
    projection["allowed_sources"] = sorted(
        (
            _exact_fields(source, _SOURCE_FIELDS)
            for source in _items(contract.get("allowed_sources"))
            if _mapping(source).get("time_role") == "PRE_CUTOFF"
        ),
        key=lambda item: (str(item.get("source_id")), str(item.get("source_ref"))),
    )
    return projection


def _source_projection(items: list[Any]) -> list[dict[str, Any]]:
    return sorted(
        (_exact_fields(_mapping(item), _SOURCE_FIELDS) for item in items),
        key=lambda item: (str(item.get("source_id")), str(item.get("source_ref"))),
    )


def _validate_cells(
    bundle: dict[str, Any], cases: dict[str, dict[str, Any]], findings: list[str],
) -> None:
    execution = _closed(bundle.get("execution"), _EXECUTION_FIELDS, "execution", findings)
    if execution.get("schema_version") != CONTRACT_SCHEMA:
        _add(findings, "execution.schema_version_must_be_current_v2")
    if execution.get("retry_policy") != "NO_RETRY_OR_REWRITE":
        _add(findings, "execution.retry_policy_invalid")
    budget = _closed(execution.get("cell_budget"), _BUDGET_FIELDS, "execution.cell_budget", findings)
    for field in _BUDGET_FIELDS:
        value = budget.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            _add(findings, "execution.cell_budget." + field + "_must_be_positive_integer")
    if budget.get("episode_attempts") != 1 or budget.get("reader_report_attempts") != 1:
        _add(findings, "execution.cell_budget.must_allow_exactly_one_episode_and_report")
    if execution.get("tool_policy") != _TOOL_POLICY:
        _add(findings, "execution.tool_policy_must_match_frozen_prohibition")

    cells = [
        _closed(raw, _CELL_FIELDS, f"execution.cells[{index}]", findings)
        for index, raw in enumerate(_items(execution.get("cells")))
    ]
    if len(cells) != CELL_COUNT:
        _add(findings, "execution.cells.must_contain_exactly_thirty_two")
    cell_pairs: set[tuple[str, str]] = set()
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for index, cell in enumerate(cells):
        case_id = _text(cell.get("case_id"))
        arm_id = _text(cell.get("arm_id"))
        pair = (case_id, arm_id)
        if not case_id or arm_id not in ARMS or pair in cell_pairs:
            _add(findings, f"execution.cells[{index}].case_arm_missing_invalid_or_duplicate")
            continue
        cell_pairs.add(pair)
        case = cases.get(case_id)
        if case is None:
            _add(findings, f"execution.cells[{index}].case_not_registered")
            continue
        by_case.setdefault(case_id, {})[arm_id] = cell
        if cell.get("source_package_ref") != case.get("common_source_package_ref"):
            _add(findings, f"execution.cells[{index}].source_package_ref_mismatch")
        state = cell.get("state")
        if state not in _CELL_STATES:
            _add(findings, f"execution.cells[{index}].state_invalid")
        attempts = _closed(cell.get("attempts"), _ATTEMPT_FIELDS, f"execution.cells[{index}].attempts", findings)
        for attempt_type, count in attempts.items():
            if not isinstance(count, int) or isinstance(count, bool) or count < 0 or count > 1:
                _add(findings, f"execution.cells[{index}].attempts.{attempt_type}_must_be_zero_or_one")
        if state == "NOT_STARTED" and attempts != {"episode": 0, "reader_report": 0}:
            _add(findings, f"execution.cells[{index}].not_started_must_have_zero_attempts")
        if state == "EPISODE_INVALID" and attempts.get("episode") != 1:
            _add(findings, f"execution.cells[{index}].episode_invalid_requires_one_episode_attempt")
        if state == "FROZEN" and attempts != {"episode": 1, "reader_report": 1}:
            _add(findings, f"execution.cells[{index}].frozen_requires_one_episode_and_report")
        artifacts = _closed(cell.get("artifact_paths"), _ARTIFACT_PATH_FIELDS, f"execution.cells[{index}].artifact_paths", findings)
        for field in _ARTIFACT_PATH_FIELDS:
            if not _text(artifacts.get(field)):
                _add(findings, f"execution.cells[{index}].artifact_paths.{field}_required")

        contract = _mapping(cell.get("training_contract"))
        validation = validate_training_contract(contract)
        if validation["state"] != "REVIEWABLE":
            _add(findings, f"execution.cells[{index}].training_contract_invalid")
            for finding in validation["findings"]:
                _add(findings, f"execution.cells[{index}].training_contract:{finding}")
        for field in ("company_id", "company_name", "cutoff_at"):
            if contract.get(field) != case.get(field):
                _add(findings, f"execution.cells[{index}].training_contract_{field}_mismatch")
        if contract.get("schema_version") != CONTRACT_SCHEMA:
            _add(findings, f"execution.cells[{index}].training_contract_not_current_v2")
        if contract.get("training_track") != "BLIND_REPLAY":
            _add(findings, f"execution.cells[{index}].training_contract_must_be_blind_replay")

        actual_common_sources = _source_projection([
            source for source in _items(contract.get("allowed_sources"))
            if _mapping(source).get("time_role") == "PRE_CUTOFF"
        ])
        if actual_common_sources != _source_projection(_items(case.get("common_sources"))):
            _add(findings, f"execution.cells[{index}].common_sources_mismatch")
        actual_memory = _source_projection([
            source for source in _items(contract.get("allowed_sources"))
            if _mapping(source).get("time_role") == "TRAINING_MEMORY"
        ])
        expected_memory: list[dict[str, Any]] = []
        if "INDUSTRY_DECISION_MEMORY" in _ARM_MEMORY_KINDS[arm_id]:
            expected_memory.append(_exact_fields(_mapping(case.get("industry_memory")), _SOURCE_FIELDS))
        if "EXPERT_CORRECTION_MEMORY" in _ARM_MEMORY_KINDS[arm_id]:
            expected_memory.append(_exact_fields(_mapping(case.get("expert_memory")), _SOURCE_FIELDS))
        if actual_memory != _source_projection(expected_memory):
            _add(findings, f"execution.cells[{index}].training_memory_not_exactly_arm_declared")

        task = _mapping(cell.get("rendered_task"))
        if task.get("schema_version") != SUBAGENT_TASK_SCHEMA:
            _add(findings, f"execution.cells[{index}].rendered_task_schema_invalid")
        elif task.get("contract_id") != contract.get("contract_id"):
            _add(findings, f"execution.cells[{index}].rendered_task_contract_id_mismatch")
        try:
            expected_task = build_fresh_subagent_task(contract)
        except (OSError, ValueError) as exc:
            _add(findings, f"execution.cells[{index}].rendered_task_unrenderable:{exc}")
        else:
            if task != expected_task:
                _add(findings, f"execution.cells[{index}].rendered_task_not_exact_frozen_render")

    expected_pairs = {(case_id, arm) for case_id in cases for arm in ARMS}
    if cell_pairs != expected_pairs:
        _add(findings, "execution.cells.must_have_exactly_one_cell_for_every_case_and_arm")

    for case_id, case in cases.items():
        arms = by_case.get(case_id, {})
        if set(arms) != set(ARMS):
            continue
        reference = _contract_common_projection(_mapping(arms["A00"].get("training_contract")))
        for arm_id, cell in arms.items():
            if _contract_common_projection(_mapping(cell.get("training_contract"))) != reference:
                _add(findings, "execution.case_common_contract_mismatch:" + case_id + ":" + arm_id)
def _validate_schedule(execution: dict[str, Any], cases: dict[str, dict[str, Any]], findings: list[str]) -> None:
    schedule = _mapping(execution.get("schedule"))
    if set(schedule) != {"episode_orders", "reader_report_orders"}:
        _add(findings, "execution.schedule_fields_invalid")
        return
    episode_orders = _mapping(schedule.get("episode_orders"))
    reader_orders = _mapping(schedule.get("reader_report_orders"))
    if set(episode_orders) != set(cases) or set(reader_orders) != set(cases):
        _add(findings, "execution.schedule_must_cover_every_case_exactly_once")
    for case_id, case in cases.items():
        rank = case.get("selection_rank")
        if not isinstance(rank, int):
            continue
        expected_episode = _expected_episode_order(rank)
        expected_report = expected_episode[2:] + expected_episode[:2]
        if episode_orders.get(case_id) != expected_episode:
            _add(findings, "execution.episode_order_invalid:" + case_id)
        if reader_orders.get(case_id) != expected_report:
            _add(findings, "execution.reader_report_order_invalid:" + case_id)


def _contains_arm_identifier(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_arm_identifier(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_arm_identifier(item) for item in value)
    return isinstance(value, str) and any(arm in value for arm in ARMS)


def _validate_anonymous_custody(
    bundle: dict[str, Any], cases: dict[str, dict[str, Any]], findings: list[str],
) -> None:
    custody = _closed(bundle.get("anonymous_review_custody"), _CUSTODY_FIELDS, "anonymous_review_custody", findings)
    mapping = [
        _closed(item, _MAPPING_FIELDS, f"anonymous_review_custody.mapping[{index}]", findings)
        for index, item in enumerate(_items(custody.get("mapping")))
    ]
    if len(mapping) != CELL_COUNT:
        _add(findings, "anonymous_review_custody.mapping_must_contain_exactly_thirty_two")
    labels = _unique_texts(mapping, "anonymous_label", "anonymous_review_custody.mapping", findings)
    pairs = {(item.get("case_id"), item.get("arm_id")) for item in mapping}
    expected_pairs = {(case_id, arm) for case_id in cases for arm in ARMS}
    if pairs != expected_pairs:
        _add(findings, "anonymous_review_custody.mapping_must_be_exact_case_arm_bijection")
    for index, item in enumerate(mapping):
        case = cases.get(_text(item.get("case_id")))
        if case is not None and item.get("source_package_ref") != case.get("common_source_package_ref"):
            _add(findings, f"anonymous_review_custody.mapping[{index}].source_package_ref_mismatch")
        label = _text(item.get("anonymous_label"))
        if not label.startswith("ANON_") or _contains_arm_identifier(label):
            _add(findings, f"anonymous_review_custody.mapping[{index}].anonymous_label_invalid")

    manifest = [
        _closed(item, _MANIFEST_FIELDS, f"anonymous_review_custody.reviewer_manifest[{index}]", findings)
        for index, item in enumerate(_items(custody.get("reviewer_manifest")))
    ]
    if len(manifest) != CELL_COUNT:
        _add(findings, "anonymous_review_custody.reviewer_manifest_must_contain_exactly_thirty_two")
    manifest_pairs = {(item.get("case_id"), item.get("anonymous_label")) for item in manifest}
    expected_manifest_pairs = {(item.get("case_id"), item.get("anonymous_label")) for item in mapping}
    if manifest_pairs != expected_manifest_pairs or len(manifest_pairs) != len(manifest):
        _add(findings, "anonymous_review_custody.reviewer_manifest_must_match_mapping_exactly")
    if _contains_arm_identifier(manifest):
        _add(findings, "anonymous_review_custody.reviewer_manifest_contains_arm_identifier")
    for index, item in enumerate(manifest):
        case = cases.get(_text(item.get("case_id")))
        if case is not None and item.get("source_package_ref") != case.get("common_source_package_ref"):
            _add(findings, f"anonymous_review_custody.reviewer_manifest[{index}].source_package_ref_mismatch")
        for field in _MANIFEST_FIELDS:
            if not _text(item.get(field)):
                _add(findings, f"anonymous_review_custody.reviewer_manifest[{index}].{field}_required")
    if len(labels) != len(mapping):
        return


def _validate_outcome_gate(
    bundle: dict[str, Any], cases: dict[str, dict[str, Any]], findings: list[str],
) -> None:
    matrices = [
        _closed(item, _MEASUREMENT_FIELDS, f"outcome_measurements[{index}]", findings)
        for index, item in enumerate(_items(bundle.get("outcome_measurements")))
    ]
    if len(matrices) != CASE_COUNT:
        _add(findings, "outcome_measurements.must_contain_exactly_eight")
    case_ids = _unique_texts(matrices, "case_id", "outcome_measurements", findings)
    if case_ids != set(cases):
        _add(findings, "outcome_measurements.must_cover_every_case_exactly_once")
    for index, matrix in enumerate(matrices):
        case = cases.get(_text(matrix.get("case_id")))
        if case is None:
            continue
        for field in ("company_id", "cutoff_at"):
            if matrix.get(field) != case.get(field):
                _add(findings, f"outcome_measurements[{index}].{field}_mismatch")
        for field in _MEASUREMENT_FIELDS - {"case_id", "company_id", "cutoff_at"}:
            if not _text(matrix.get(field)):
                _add(findings, f"outcome_measurements[{index}].{field}_required")
        if matrix.get("official_source_category") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
            _add(findings, f"outcome_measurements[{index}].official_source_category_invalid")
        if matrix.get("disposition_rule") != "SUPPORTED_WEAKENED_OR_FALSIFIED_INCONCLUSIVE_DATA_NON_DISCRIMINATING":
            _add(findings, f"outcome_measurements[{index}].disposition_rule_invalid")

    gate = _closed(bundle.get("outcome_access_gate"), _OUTCOME_GATE_FIELDS, "outcome_access_gate", findings)
    if gate.get("state") != _OUTCOME_GATE_STATE:
        _add(findings, "outcome_access_gate.state_invalid")
    if gate.get("outcome_access_authorized") is not False:
        _add(findings, "outcome_access_gate.must_be_unauthorized_preoutcome")
    receipts = gate.get("required_reviewer_freeze_receipts")
    if not isinstance(receipts, list) or receipts != sorted(cases):
        _add(findings, "outcome_access_gate.must_require_every_case_reviewer_freeze")


def validate_multicompany_preregistration(bundle: Any) -> dict[str, Any]:
    """Validate the eight-case, four-arm control plane before any arm starts."""

    findings: list[str] = []
    value = _closed(bundle, _ROOT_FIELDS, "preregistration", findings)
    if value.get("schema_version") != SCHEMA_VERSION:
        _add(findings, "preregistration.schema_version_invalid")
    if not _text(value.get("preregistration_id")):
        _add(findings, "preregistration.preregistration_id_required")
    if value.get("state") != "COHORT_FROZEN":
        _add(findings, "preregistration.state_must_be_cohort_frozen")
    cases = _validate_cases(value, findings)
    _validate_cells(value, cases, findings)
    _validate_schedule(_mapping(value.get("execution")), cases, findings)
    _validate_anonymous_custody(value, cases, findings)
    _validate_outcome_gate(value, cases, findings)
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": findings,
        "case_count": len(cases),
        "expected_cell_count": CELL_COUNT,
        "authority": "PREOUTCOME_CONTROL_PLANE_ONLY_NO_UTILITY_OR_INVESTMENT_CLAIM",
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("preregistration_json_must_be_object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preregistration", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_multicompany_preregistration(_read_json(args.preregistration))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "state": "INVALID",
            "findings": [str(exc)],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "REVIEWABLE" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
