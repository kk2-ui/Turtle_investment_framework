#!/usr/bin/env python3
"""Local treatment-level evaluation for fair historical holdouts.

The contract compares what the two forecasters would *do* with the company,
not how many fields they produced or which forecast happened to be closer.
It is deliberately local to the historical curriculum and grants no method,
valuation, report, or investment authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from scripts.historical_judgment_first_draft import (
    ALL_AXES,
    derive_material_treatment_changes,
    validate_preoutcome_draft,
)
from scripts.historical_role_isolation import (
    HOLDOUT_PAIR_PACKET_SCHEMA_VERSION,
    validate_method_pack,
)


PAIR_SCHEMA_VERSION = "historical-holdout-treatment-pair.v1"
SETTLEMENT_SCHEMA_VERSION = "historical-holdout-outcome-settlement.v1"
EVALUATION_SCHEMA_VERSION = "historical-holdout-treatment-evaluation.v1"

CELL_STATUSES = {"OBSERVED", "LOCAL_UNKNOWN", "MEASUREMENT_MISMATCH"}
SUPPORTED_ARMS = {"BASELINE", "ENHANCED", "BOTH", "NEITHER", "NOT_DIAGNOSTIC"}
UTILITY_VERDICTS = {
    "MATERIAL_UTILITY_CANDIDATE",
    "NO_MATERIAL_UTILITY",
    "HARMFUL",
    "MIXED_NOT_VALIDATED",
    "NOT_DIAGNOSTIC",
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _time(value: Any) -> datetime | None:
    if not _text(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cell_axis_index(*drafts: dict[str, Any]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for draft in drafts:
        for cell in draft.get("outcome_cells", []):
            if not isinstance(cell, dict) or not _text(cell.get("cell_id")):
                continue
            index.setdefault(cell["cell_id"], set()).update(cell.get("direct_axes", []))
    return index


def build_treatment_pair(
    *,
    pair_id: str,
    frozen_at: str,
    baseline_draft: dict[str, Any],
    enhanced_draft: dict[str, Any],
    holdout_pair_packet: dict[str, Any],
    method_pack: dict[str, Any],
) -> dict[str, Any]:
    baseline_snapshot = baseline_draft.get("material_treatment_snapshot", {})
    enhanced_snapshot = enhanced_draft.get("material_treatment_snapshot", {})
    cell_ids = sorted(_cell_axis_index(baseline_draft, enhanced_draft))
    return {
        "schema_version": PAIR_SCHEMA_VERSION,
        "pair_id": pair_id,
        "episode_id": baseline_draft.get("episode_id"),
        "company_id": baseline_draft.get("company_id"),
        "cutoff_at": baseline_draft.get("cutoff_at"),
        "baseline_forecaster_id": holdout_pair_packet.get("arms", {})
        .get("baseline", {})
        .get("forecaster_id"),
        "enhanced_forecaster_id": holdout_pair_packet.get("arms", {})
        .get("enhanced", {})
        .get("forecaster_id"),
        "method_pack_id": method_pack.get("method_pack_id"),
        "method_version": method_pack.get("method_version"),
        "baseline_treatment_snapshot": deepcopy(baseline_snapshot),
        "enhanced_treatment_snapshot": deepcopy(enhanced_snapshot),
        "material_preoutcome_differences": derive_material_treatment_changes(
            baseline_snapshot, enhanced_snapshot
        ),
        "shared_outcome_cell_ids": cell_ids,
        "frozen_at": frozen_at,
        "outcome_state": "SEALED_AFTER_BOTH_ARMS_FREEZE",
        "artifact_status": "FROZEN",
        "authority": "NONE",
    }


def validate_treatment_pair(
    pair: dict[str, Any],
    *,
    baseline_draft: dict[str, Any],
    enhanced_draft: dict[str, Any],
    holdout_pair_packet: dict[str, Any],
    method_pack: dict[str, Any],
) -> list[str]:
    findings: list[str] = []
    findings.extend("baseline:" + item for item in validate_preoutcome_draft(baseline_draft))
    findings.extend("enhanced:" + item for item in validate_preoutcome_draft(enhanced_draft))
    findings.extend("method_pack:" + item for item in validate_method_pack(method_pack))
    if pair.get("schema_version") != PAIR_SCHEMA_VERSION:
        findings.append("holdout_pair.schema_version_invalid")
    if holdout_pair_packet.get("schema_version") != HOLDOUT_PAIR_PACKET_SCHEMA_VERSION:
        findings.append("holdout_pair.packet_schema_invalid")
    if not isinstance(holdout_pair_packet.get("shared_source_budget"), list) or not holdout_pair_packet.get(
        "shared_source_budget"
    ):
        findings.append("holdout_pair.shared_source_budget_missing")
    if holdout_pair_packet.get("outcome_state") != "SEALED_NOT_IN_PACKET":
        findings.append("holdout_pair.packet_outcome_not_sealed")
    if holdout_pair_packet.get("authority") != "NONE":
        findings.append("holdout_pair.packet_authority_must_be_none")
    for field in ("pair_id", "episode_id", "company_id", "cutoff_at"):
        if not _text(pair.get(field)):
            findings.append(f"holdout_pair.{field}_missing")
    for field in ("episode_id", "company_id", "cutoff_at"):
        expected = baseline_draft.get(field)
        if pair.get(field) != expected or enhanced_draft.get(field) != expected:
            findings.append(f"holdout_pair.{field}_must_match_both_arms")
        if holdout_pair_packet.get(field) != expected:
            findings.append(f"holdout_pair.{field}_must_match_packet")

    packet_arms = holdout_pair_packet.get("arms", {})
    baseline_id = packet_arms.get("baseline", {}).get("forecaster_id")
    enhanced_id = packet_arms.get("enhanced", {}).get("forecaster_id")
    if pair.get("baseline_forecaster_id") != baseline_id:
        findings.append("holdout_pair.baseline_forecaster_must_match_packet")
    if pair.get("enhanced_forecaster_id") != enhanced_id:
        findings.append("holdout_pair.enhanced_forecaster_must_match_packet")
    if not _text(baseline_id) or not _text(enhanced_id) or baseline_id == enhanced_id:
        findings.append("holdout_pair.forecasters_must_be_distinct")
    if packet_arms.get("baseline", {}).get("method_input") != {"state": "NONE"}:
        findings.append("holdout_pair.baseline_must_not_receive_method_pack")
    enhanced_method = packet_arms.get("enhanced", {}).get("method_input", {})
    if enhanced_method.get("state") != "FROZEN_GENERALIZED_METHOD_SUPPLIED":
        findings.append("holdout_pair.enhanced_method_input_missing")
    for field in ("method_pack_id", "method_version"):
        if pair.get(field) != method_pack.get(field) or enhanced_method.get(field) != method_pack.get(field):
            findings.append(f"holdout_pair.{field}_must_match_method_pack")
        if holdout_pair_packet.get(field) != method_pack.get(field):
            findings.append(f"holdout_pair.packet_{field}_must_match_method_pack")

    baseline_snapshot = baseline_draft.get("material_treatment_snapshot")
    enhanced_snapshot = enhanced_draft.get("material_treatment_snapshot")
    if pair.get("baseline_treatment_snapshot") != baseline_snapshot:
        findings.append("holdout_pair.baseline_snapshot_must_match_frozen_draft")
    if pair.get("enhanced_treatment_snapshot") != enhanced_snapshot:
        findings.append("holdout_pair.enhanced_snapshot_must_match_frozen_draft")
    expected_changes = derive_material_treatment_changes(
        baseline_snapshot or {}, enhanced_snapshot or {}
    )
    if pair.get("material_preoutcome_differences") != expected_changes:
        findings.append("holdout_pair.material_differences_inconsistent")
    expected_cells = sorted(_cell_axis_index(baseline_draft, enhanced_draft))
    if pair.get("shared_outcome_cell_ids") != expected_cells:
        findings.append("holdout_pair.outcome_cells_must_equal_arm_union")
    if not _time(pair.get("frozen_at")):
        findings.append("holdout_pair.frozen_at_invalid")
    if pair.get("outcome_state") != "SEALED_AFTER_BOTH_ARMS_FREEZE":
        findings.append("holdout_pair.outcome_must_remain_sealed")
    if pair.get("artifact_status") != "FROZEN" or pair.get("authority") != "NONE":
        findings.append("holdout_pair.status_or_authority_invalid")
    return findings


def validate_holdout_settlement(
    settlement: dict[str, Any], *, pair: dict[str, Any]
) -> list[str]:
    findings: list[str] = []
    if settlement.get("schema_version") != SETTLEMENT_SCHEMA_VERSION:
        findings.append("holdout_settlement.schema_version_invalid")
    for field in ("settlement_id", "pair_id", "episode_id", "company_id", "custodian_id"):
        if not _text(settlement.get(field)):
            findings.append(f"holdout_settlement.{field}_missing")
    for field in ("pair_id", "episode_id", "company_id"):
        if settlement.get(field) != pair.get(field):
            findings.append(f"holdout_settlement.{field}_must_match_pair")
    settled_at = _time(settlement.get("settled_at"))
    frozen_at = _time(pair.get("frozen_at"))
    if not settled_at:
        findings.append("holdout_settlement.settled_at_invalid")
    elif frozen_at and settled_at < frozen_at:
        findings.append("holdout_settlement.must_follow_pair_freeze")
    cells = settlement.get("cells")
    if not isinstance(cells, list):
        findings.append("holdout_settlement.cells_must_be_list")
        cells = []
    expected = set(pair.get("shared_outcome_cell_ids", []))
    seen: set[str] = set()
    for index, cell in enumerate(cells):
        prefix = f"holdout_settlement.cells[{index}]"
        if not isinstance(cell, dict):
            findings.append(prefix + ".must_be_object")
            continue
        cell_id = cell.get("cell_id")
        if not _text(cell_id) or cell_id in seen:
            findings.append(prefix + ".cell_id_missing_or_duplicate")
        else:
            seen.add(cell_id)
        if cell.get("status") not in CELL_STATUSES:
            findings.append(prefix + ".status_invalid")
        if not _text(cell.get("classification")) or not _text(cell.get("evidence_ref")):
            findings.append(prefix + ".classification_or_evidence_missing")
        facts = cell.get("observed_facts")
        if not isinstance(facts, list) or not any(_text(fact) for fact in facts):
            findings.append(prefix + ".observed_facts_missing")
    if seen != expected:
        findings.append("holdout_settlement.cells_must_equal_pair_union")
    if settlement.get("outcome_access") != "AFTER_PAIR_FREEZE":
        findings.append("holdout_settlement.outcome_access_invalid")
    if settlement.get("artifact_status") != "SETTLED" or settlement.get("authority") != "NONE":
        findings.append("holdout_settlement.status_or_authority_invalid")
    return findings


def compile_holdout_utility_verdict(
    *, pair: dict[str, Any], axis_assessments: list[dict[str, Any]]
) -> str:
    differences = pair.get("material_preoutcome_differences", [])
    if not differences:
        return "NO_MATERIAL_UTILITY"
    supported = {item.get("result_supported_arm") for item in axis_assessments}
    if supported == {"NOT_DIAGNOSTIC"}:
        return "NOT_DIAGNOSTIC"
    if "BASELINE" in supported and "ENHANCED" in supported:
        return "MIXED_NOT_VALIDATED"
    if "BASELINE" in supported:
        return "HARMFUL"
    if "ENHANCED" in supported:
        return "MATERIAL_UTILITY_CANDIDATE"
    return "NO_MATERIAL_UTILITY"


def validate_holdout_evaluation(
    evaluation: dict[str, Any],
    *,
    pair: dict[str, Any],
    baseline_draft: dict[str, Any],
    enhanced_draft: dict[str, Any],
    settlement: dict[str, Any],
) -> dict[str, Any]:
    findings = validate_holdout_settlement(settlement, pair=pair)
    if evaluation.get("schema_version") != EVALUATION_SCHEMA_VERSION:
        findings.append("holdout_evaluation.schema_version_invalid")
    for field in ("evaluation_id", "pair_id", "reviewer_id"):
        if not _text(evaluation.get(field)):
            findings.append(f"holdout_evaluation.{field}_missing")
    if evaluation.get("pair_id") != pair.get("pair_id"):
        findings.append("holdout_evaluation.pair_id_must_match")
    if evaluation.get("reviewer_id") in {
        pair.get("baseline_forecaster_id"),
        pair.get("enhanced_forecaster_id"),
        settlement.get("custodian_id"),
    }:
        findings.append("holdout_evaluation.reviewer_must_be_independent")
    evaluated_at = _time(evaluation.get("evaluated_at"))
    settled_at = _time(settlement.get("settled_at"))
    if not evaluated_at:
        findings.append("holdout_evaluation.evaluated_at_invalid")
    elif settled_at and evaluated_at < settled_at:
        findings.append("holdout_evaluation.must_follow_settlement")

    changed_axes = pair.get("material_preoutcome_differences", [])
    assessments = evaluation.get("axis_assessments")
    if not isinstance(assessments, list):
        findings.append("holdout_evaluation.axis_assessments_must_be_list")
        assessments = []
    seen: set[str] = set()
    settlement_cells = {
        cell.get("cell_id"): cell
        for cell in settlement.get("cells", [])
        if isinstance(cell, dict)
    }
    cell_axes = _cell_axis_index(baseline_draft, enhanced_draft)
    for index, assessment in enumerate(assessments):
        prefix = f"holdout_evaluation.axis_assessments[{index}]"
        if not isinstance(assessment, dict):
            findings.append(prefix + ".must_be_object")
            continue
        axis = assessment.get("axis")
        if axis not in ALL_AXES or axis in seen:
            findings.append(prefix + ".axis_invalid_or_duplicate")
        else:
            seen.add(axis)
        refs = assessment.get("settlement_cell_ids")
        if not isinstance(refs, list) or not refs:
            findings.append(prefix + ".settlement_cell_ids_missing")
            refs = []
        for cell_id in refs:
            if cell_id not in settlement_cells or axis not in cell_axes.get(cell_id, set()):
                findings.append(prefix + ".settlement_cell_not_bound_to_axis")
        supported_arm = assessment.get("result_supported_arm")
        if supported_arm not in SUPPORTED_ARMS:
            findings.append(prefix + ".result_supported_arm_invalid")
        statuses = {settlement_cells.get(cell_id, {}).get("status") for cell_id in refs}
        if supported_arm in {"BASELINE", "ENHANCED", "BOTH", "NEITHER"} and statuses != {"OBSERVED"}:
            findings.append(prefix + ".material_assessment_requires_observed_cells")
        for field in ("rationale", "economic_impact"):
            if not _text(assessment.get(field)):
                findings.append(f"{prefix}.{field}_missing")
    if set(changed_axes) != seen:
        findings.append("holdout_evaluation.must_assess_each_changed_axis_once")

    verdict = compile_holdout_utility_verdict(pair=pair, axis_assessments=assessments)
    if evaluation.get("overall_utility_verdict") != verdict:
        findings.append("holdout_evaluation.overall_utility_verdict_inconsistent")
    if verdict not in UTILITY_VERDICTS:
        findings.append("holdout_evaluation.overall_utility_verdict_invalid")
    if evaluation.get("artifact_status") != "EVALUATED" or evaluation.get("authority") != "NONE":
        findings.append("holdout_evaluation.status_or_authority_invalid")
    return {
        "valid": not findings,
        "findings": findings,
        "overall_utility_verdict": verdict,
        "learning_authorization": (
            "CANDIDATE_ONLY"
            if not findings and verdict == "MATERIAL_UTILITY_CANDIDATE"
            else "NONE"
        ),
        "transfer_validated": False,
    }
