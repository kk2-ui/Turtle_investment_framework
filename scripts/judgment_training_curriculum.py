#!/usr/bin/env python3
"""Curriculum layer for building enterprise-judgment capability at scale.

The existing judgment training program remains the strict evaluation and
method-release control plane.  This module sits before it.  It lets known-result
historical cases teach mechanisms in volume, interleaves them with blind
historical judgments, reserves genuinely independent holdouts, and keeps live
prospective cases as deployment calibration rather than the main training
engine.

Counts are planning signals, never proof of capability.  Independent sample
counts are always company-cluster counts; repeated cutoffs of one company are
useful episodes but not additional independent companies.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-capability-curriculum.v1"
VALIDATION_VERSION = "judgment-capability-curriculum-validation.v1"
STATUS_VERSION = "judgment-capability-curriculum-status.v1"

TRACKS = ("TEACHING", "BLIND_JUDGMENT", "HISTORICAL_HOLDOUT", "PROSPECTIVE")
CAPABILITY_UNITS = {
    "BUSINESS_MODEL_ECONOMICS",
    "CUSTOMER_ABSORPTION",
    "COMPETITION_AND_PRICING",
    "MANAGEMENT_DECISION_EXECUTION",
    "CAPITAL_ALLOCATION",
    "OWNER_CASH_CONVERSION",
    "PERMANENT_LOSS_AND_LIFECYCLE",
    "VALUATION_AND_ENTRY_TREATMENT",
}
CURRICULUM_STATES = {"BUILDING", "ACTIVE", "FROZEN_FOR_HOLDOUT_EVALUATION"}
TRACK_STATUSES = {
    "TEACHING": {"REGISTERED", "CURATED"},
    "BLIND_JUDGMENT": {"REGISTERED", "FROZEN", "SETTLED"},
    "HISTORICAL_HOLDOUT": {"RESERVED", "FROZEN", "EVALUATED"},
    "PROSPECTIVE": {"FROZEN", "PARTIAL_FEEDBACK", "SETTLED"},
}
TRACK_OUTCOME_ACCESS = {
    "TEACHING": {"RESULT_KNOWN"},
    "BLIND_JUDGMENT": {"SEALED", "REVEALED_AFTER_FREEZE"},
    "HISTORICAL_HOLDOUT": {"SEALED", "REVEALED_AFTER_METHOD_FREEZE"},
    "PROSPECTIVE": {"NOT_YET_RELEASED", "PARTIAL_RELEASED", "RELEASED_AFTER_FREEZE"},
}
SELECTION_EXPOSURES = {
    "RESULT_KNOWN_OR_DERIVED_VISIBLE",
    "PREOUTCOME_ONLY",
    "METADATA_ONLY",
    "UNASSESSED",
}
ROLE_ISOLATION_STATES = {
    "NOT_REQUIRED_FOR_TEACHING",
    "BLIND_PACKET_READY",
    "ROLE_ISOLATION_PROVED",
    "NOT_REQUIRED_RESULT_DOES_NOT_EXIST",
}
COMPARATIVE_MODES = {
    "NOT_REQUIRED",
    "OPTIONAL_LOCAL_LAB",
    "REQUIRED_FOR_RELATIVE_CAUSAL_CLAIM",
}
CLAIM_SCOPES = {
    "ENTERPRISE_JUDGMENT",
    "WITHIN_CASE_MECHANISM",
    "RELATIVE_CAUSAL_EFFECT",
}
HOLDOUT_AXES = {"COMPANY", "TIME", "COMPANY_AND_TIME"}

ROOT_FIELDS = {
    "schema_version",
    "curriculum_id",
    "curriculum_version",
    "state",
    "objective",
    "capacity_targets",
    "execution_policy",
    "cases",
    "teaching_candidate_pool",
}
TARGET_FIELDS = {"lower", "target", "upper"}
POLICY_FIELDS = {
    "same_company_cutoffs_count_as_independent",
    "teaching_can_use_known_results",
    "blind_requires_role_scoped_result_isolation",
    "holdout_can_influence_training",
    "prospective_wait_blocks_historical_training",
    "comparative_default",
    "teaching_cases_per_blind_cycle",
}
CASE_FIELDS = {
    "case_id",
    "company_id",
    "company_cluster_id",
    "company_name",
    "industry_id",
    "track",
    "status",
    "cutoff_at",
    "outcome_window",
    "outcome_access",
    "selection_exposure",
    "role_isolation_state",
    "primary_capability_units",
    "mechanism_focus",
    "claim_scope",
    "comparative_mode",
    "source_refs",
    "artifact_refs",
    "lesson",
    "holdout_axis",
}
WINDOW_FIELDS = {"starts_at", "ends_at"}
LESSON_FIELDS = {
    "state_and_constraint",
    "management_choice_or_no_action",
    "customer_or_operating_response",
    "cash_or_capital_result",
    "mechanism_lesson",
    "strongest_rival",
    "near_miss",
    "investor_treatment",
    "transfer_question",
}
ARTIFACT_FIELDS = {
    "preoutcome_judgment_ref",
    "settlement_ref",
    "postoutcome_review_ref",
    "investor_readout_ref",
    "lesson_ref",
    "freeze_ref",
}
TEACHING_CANDIDATE_FIELDS = {
    "candidate_id",
    "company_ids",
    "company_cluster_id",
    "company_name",
    "industry_id",
    "primary_capability_units",
    "mechanism_focus",
    "selection_exposure",
    "source_locator",
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_time(value: Any) -> datetime | None:
    if not _text(value):
        return None
    candidate = str(value).strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        findings.append(path + ".must_be_object")
        return {}
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        findings.append(path + ".unexpected_fields:" + ",".join(unexpected))
    return value


def _required_text(obj: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = obj.get(field)
    if not _text(value):
        findings.append(f"{path}.{field}_missing")
        return ""
    return str(value).strip()


def route_candidate(
    *, selection_exposure: str, outcome_exists: bool, outcome_released: bool,
) -> dict[str, Any]:
    """Route local material by role instead of permanently blacklisting a company."""

    exposure = str(selection_exposure or "").upper()
    if exposure not in SELECTION_EXPOSURES:
        return {
            "state": "INVALID",
            "allowed_tracks": [],
            "findings": ["selection_exposure_invalid"],
        }
    if exposure == "UNASSESSED":
        return {
            "state": "NEEDS_ROLE_SCOPED_EXPOSURE_REVIEW",
            "allowed_tracks": [],
            "findings": [],
        }
    if exposure == "RESULT_KNOWN_OR_DERIVED_VISIBLE":
        return {
            "state": "ROUTED",
            "allowed_tracks": ["TEACHING"],
            "findings": [],
            "reason": "Known results are useful teaching material but cannot evaluate an unseen judgment.",
        }

    allowed = ["TEACHING"]
    if outcome_exists:
        allowed.extend(["BLIND_JUDGMENT", "HISTORICAL_HOLDOUT"])
    if not outcome_released:
        allowed.append("PROSPECTIVE")
    return {
        "state": "ROUTED",
        "allowed_tracks": allowed,
        "findings": [],
        "reason": "Eligibility remains role- and cutoff-scoped; workspace presence alone is not exposure.",
    }


def _validate_window(raw: Any, *, path: str, findings: list[str]) -> tuple[datetime | None, datetime | None]:
    if raw is None:
        return None, None
    window = _closed(raw, WINDOW_FIELDS, path, findings)
    starts = _parse_time(window.get("starts_at"))
    ends = _parse_time(window.get("ends_at"))
    if starts is None:
        findings.append(path + ".starts_at_invalid")
    if ends is None:
        findings.append(path + ".ends_at_invalid")
    if starts is not None and ends is not None and ends <= starts:
        findings.append(path + ".ends_at_must_follow_starts_at")
    return starts, ends


def _validate_lesson(raw: Any, *, path: str, findings: list[str]) -> None:
    lesson = _closed(raw, LESSON_FIELDS, path, findings)
    for field in sorted(LESSON_FIELDS):
        _required_text(lesson, field, path, findings)


def _validate_case(raw: Any, *, index: int) -> tuple[list[str], dict[str, Any]]:
    findings: list[str] = []
    path = f"cases[{index}]"
    case = _closed(raw, CASE_FIELDS, path, findings)
    for field in (
        "case_id",
        "company_id",
        "company_cluster_id",
        "company_name",
        "industry_id",
        "mechanism_focus",
    ):
        _required_text(case, field, path, findings)

    cutoff = _parse_time(case.get("cutoff_at"))
    if cutoff is None:
        findings.append(path + ".cutoff_at_invalid")
    starts, _ = _validate_window(case.get("outcome_window"), path=path + ".outcome_window", findings=findings)
    if starts is not None and cutoff is not None and starts <= cutoff:
        findings.append(path + ".outcome_window_must_follow_cutoff")

    track = str(case.get("track") or "").upper()
    status = str(case.get("status") or "").upper()
    outcome_access = str(case.get("outcome_access") or "").upper()
    exposure = str(case.get("selection_exposure") or "").upper()
    isolation = str(case.get("role_isolation_state") or "").upper()
    claim_scope = str(case.get("claim_scope") or "").upper()
    comparative = str(case.get("comparative_mode") or "").upper()
    if track not in TRACKS:
        findings.append(path + ".track_invalid")
    elif status not in TRACK_STATUSES[track]:
        findings.append(path + ".status_invalid_for_track")
    if track in TRACK_OUTCOME_ACCESS and outcome_access not in TRACK_OUTCOME_ACCESS[track]:
        findings.append(path + ".outcome_access_invalid_for_track")
    if exposure not in SELECTION_EXPOSURES:
        findings.append(path + ".selection_exposure_invalid")
    if isolation not in ROLE_ISOLATION_STATES:
        findings.append(path + ".role_isolation_state_invalid")
    if claim_scope not in CLAIM_SCOPES:
        findings.append(path + ".claim_scope_invalid")
    if comparative not in COMPARATIVE_MODES:
        findings.append(path + ".comparative_mode_invalid")
    if claim_scope == "RELATIVE_CAUSAL_EFFECT" and comparative != "REQUIRED_FOR_RELATIVE_CAUSAL_CLAIM":
        findings.append(path + ".relative_causal_claim_requires_comparative")
    if claim_scope != "RELATIVE_CAUSAL_EFFECT" and comparative == "REQUIRED_FOR_RELATIVE_CAUSAL_CLAIM":
        findings.append(path + ".comparative_requirement_exceeds_claim_scope")

    units = case.get("primary_capability_units")
    if not isinstance(units, list) or not 1 <= len(units) <= 2:
        findings.append(path + ".one_or_two_primary_capability_units_required")
    elif len(set(units)) != len(units) or not set(units) <= CAPABILITY_UNITS:
        findings.append(path + ".primary_capability_units_invalid")

    sources = case.get("source_refs")
    if not isinstance(sources, list) or any(not _text(ref) for ref in sources):
        findings.append(path + ".source_refs_must_be_text_list")
        sources = []
    artifacts = _closed(case.get("artifact_refs"), ARTIFACT_FIELDS, path + ".artifact_refs", findings)
    if any(not _text(ref) for ref in artifacts.values()):
        findings.append(path + ".artifact_refs_must_be_nonempty_text")

    if track == "TEACHING":
        if outcome_access != "RESULT_KNOWN":
            findings.append(path + ".teaching_requires_result_known")
        if isolation != "NOT_REQUIRED_FOR_TEACHING":
            findings.append(path + ".teaching_must_not_claim_blind_isolation")
        if status == "CURATED":
            _validate_lesson(case.get("lesson"), path=path + ".lesson", findings=findings)
            if not sources or not artifacts:
                findings.append(path + ".curated_teaching_requires_sources_and_artifact_refs")
        elif case.get("lesson") is not None:
            findings.append(path + ".registered_teaching_cannot_claim_completed_lesson")
        if case.get("holdout_axis") is not None:
            findings.append(path + ".teaching_holdout_axis_forbidden")
    elif track == "BLIND_JUDGMENT":
        if exposure not in {"PREOUTCOME_ONLY", "METADATA_ONLY"}:
            findings.append(path + ".blind_role_cannot_have_result_exposure")
        if status in {"FROZEN", "SETTLED"} and isolation != "ROLE_ISOLATION_PROVED":
            findings.append(path + ".blind_execution_requires_proved_role_isolation")
        if status == "FROZEN" and outcome_access != "SEALED":
            findings.append(path + ".frozen_blind_outcome_must_be_sealed")
        if status == "SETTLED" and outcome_access != "REVEALED_AFTER_FREEZE":
            findings.append(path + ".settled_blind_requires_postfreeze_reveal")
        if status in {"FROZEN", "SETTLED"} and starts is None:
            findings.append(path + ".blind_outcome_window_required_before_freeze")
        required_artifacts = {"preoutcome_judgment_ref"}
        if status == "SETTLED":
            required_artifacts |= {"settlement_ref", "postoutcome_review_ref"}
        if status in {"FROZEN", "SETTLED"} and not required_artifacts <= set(artifacts):
            findings.append(path + ".blind_artifact_chain_incomplete")
        if case.get("lesson") is not None or case.get("holdout_axis") is not None:
            findings.append(path + ".blind_teaching_or_holdout_fields_forbidden")
    elif track == "HISTORICAL_HOLDOUT":
        if exposure not in {"PREOUTCOME_ONLY", "METADATA_ONLY"}:
            findings.append(path + ".holdout_role_cannot_have_result_exposure")
        if status == "RESERVED" and isolation not in {"BLIND_PACKET_READY", "ROLE_ISOLATION_PROVED"}:
            findings.append(path + ".reserved_holdout_requires_blind_packet")
        if status in {"FROZEN", "EVALUATED"} and isolation != "ROLE_ISOLATION_PROVED":
            findings.append(path + ".executed_holdout_requires_proved_role_isolation")
        if case.get("holdout_axis") not in HOLDOUT_AXES:
            findings.append(path + ".holdout_axis_invalid")
        if status in {"RESERVED", "FROZEN"} and outcome_access != "SEALED":
            findings.append(path + ".unevaluated_holdout_must_be_sealed")
        if status == "EVALUATED" and outcome_access != "REVEALED_AFTER_METHOD_FREEZE":
            findings.append(path + ".evaluated_holdout_requires_post_method_freeze_reveal")
        if starts is None:
            findings.append(path + ".holdout_outcome_window_required_at_reservation")
        required_artifacts = {"freeze_ref"}
        if status == "EVALUATED":
            required_artifacts |= {"settlement_ref", "postoutcome_review_ref"}
        if not required_artifacts <= set(artifacts):
            findings.append(path + ".holdout_artifact_chain_incomplete")
        if case.get("lesson") is not None:
            findings.append(path + ".holdout_lesson_forbidden_before_retirement")
    elif track == "PROSPECTIVE":
        if exposure not in {"PREOUTCOME_ONLY", "METADATA_ONLY"}:
            findings.append(path + ".prospective_cannot_have_future_result_exposure")
        if isolation != "NOT_REQUIRED_RESULT_DOES_NOT_EXIST":
            findings.append(path + ".prospective_role_isolation_state_invalid")
        if starts is None:
            findings.append(path + ".prospective_outcome_window_required")
        required_artifacts = {"preoutcome_judgment_ref", "freeze_ref"}
        if status == "SETTLED":
            required_artifacts |= {"settlement_ref", "postoutcome_review_ref"}
        if not required_artifacts <= set(artifacts):
            findings.append(path + ".prospective_artifact_chain_incomplete")
        if case.get("lesson") is not None or case.get("holdout_axis") is not None:
            findings.append(path + ".prospective_teaching_or_holdout_fields_forbidden")

    evidence_statuses = {
        "TEACHING": {"CURATED"},
        "BLIND_JUDGMENT": {"FROZEN", "SETTLED"},
        "HISTORICAL_HOLDOUT": {"FROZEN", "EVALUATED"},
        "PROSPECTIVE": {"FROZEN", "PARTIAL_FEEDBACK", "SETTLED"},
    }
    if track in evidence_statuses and status in evidence_statuses[track] and not sources:
        findings.append(path + ".active_or_completed_case_requires_source_refs")
    return findings, case


def _validate_teaching_candidate(raw: Any, *, index: int) -> tuple[list[str], dict[str, Any]]:
    findings: list[str] = []
    path = f"teaching_candidate_pool[{index}]"
    candidate = _closed(raw, TEACHING_CANDIDATE_FIELDS, path, findings)
    for field in (
        "candidate_id",
        "company_cluster_id",
        "company_name",
        "industry_id",
        "mechanism_focus",
        "source_locator",
    ):
        _required_text(candidate, field, path, findings)
    company_ids = candidate.get("company_ids")
    if not isinstance(company_ids, list) or not company_ids or any(not _text(item) for item in company_ids):
        findings.append(path + ".company_ids_nonempty_text_list_required")
    elif len(company_ids) != len(set(company_ids)):
        findings.append(path + ".company_ids_duplicate")
    units = candidate.get("primary_capability_units")
    if not isinstance(units, list) or not 1 <= len(units) <= 2:
        findings.append(path + ".one_or_two_primary_capability_units_required")
    elif len(units) != len(set(units)) or not set(units) <= CAPABILITY_UNITS:
        findings.append(path + ".primary_capability_units_invalid")
    if candidate.get("selection_exposure") != "RESULT_KNOWN_OR_DERIVED_VISIBLE":
        findings.append(path + ".candidate_pool_is_for_result_known_teaching_reuse")
    return findings, candidate


def validate_curriculum(curriculum: Any) -> dict[str, Any]:
    findings: list[str] = []
    root = _closed(curriculum, ROOT_FIELDS, "curriculum", findings)
    if root.get("schema_version") != SCHEMA_VERSION:
        findings.append("curriculum.schema_version_invalid")
    for field in ("curriculum_id", "curriculum_version", "objective"):
        _required_text(root, field, "curriculum", findings)
    if root.get("state") not in CURRICULUM_STATES:
        findings.append("curriculum.state_invalid")

    targets = _closed(root.get("capacity_targets"), set(TRACKS), "curriculum.capacity_targets", findings)
    if set(targets) != set(TRACKS):
        findings.append("curriculum.capacity_targets_all_tracks_required")
    for track in TRACKS:
        target = _closed(targets.get(track), TARGET_FIELDS, f"curriculum.capacity_targets.{track}", findings)
        values = [target.get(field) for field in ("lower", "target", "upper")]
        if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values):
            findings.append(f"curriculum.capacity_targets.{track}.nonnegative_integers_required")
        elif not values[0] <= values[1] <= values[2]:
            findings.append(f"curriculum.capacity_targets.{track}.range_order_invalid")

    policy = _closed(root.get("execution_policy"), POLICY_FIELDS, "curriculum.execution_policy", findings)
    expected = {
        "same_company_cutoffs_count_as_independent": False,
        "teaching_can_use_known_results": True,
        "blind_requires_role_scoped_result_isolation": True,
        "holdout_can_influence_training": False,
        "prospective_wait_blocks_historical_training": False,
        "comparative_default": "NOT_REQUIRED",
    }
    for field, value in expected.items():
        if policy.get(field) != value:
            findings.append(f"curriculum.execution_policy.{field}_invalid")
    cycle = policy.get("teaching_cases_per_blind_cycle")
    if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
        findings.append("curriculum.execution_policy.teaching_cases_per_blind_cycle_invalid")

    raw_cases = root.get("cases")
    if not isinstance(raw_cases, list):
        findings.append("curriculum.cases_must_be_array")
        raw_cases = []
    cases: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_cases):
        case_findings, case = _validate_case(raw, index=index)
        findings.extend(case_findings)
        cases.append(case)

    raw_candidates = root.get("teaching_candidate_pool")
    if not isinstance(raw_candidates, list):
        findings.append("curriculum.teaching_candidate_pool_must_be_array")
        raw_candidates = []
    candidates: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_candidates):
        candidate_findings, candidate = _validate_teaching_candidate(raw, index=index)
        findings.extend(candidate_findings)
        candidates.append(candidate)

    ids = [case.get("case_id") for case in cases if _text(case.get("case_id"))]
    if len(ids) != len(set(ids)):
        findings.append("curriculum.case_id_duplicate")
    candidate_ids = [item.get("candidate_id") for item in candidates if _text(item.get("candidate_id"))]
    if len(candidate_ids) != len(set(candidate_ids)):
        findings.append("curriculum.teaching_candidate_id_duplicate")
    company_to_cluster: dict[str, str] = {}
    for case in cases:
        company = str(case.get("company_id") or "")
        cluster = str(case.get("company_cluster_id") or "")
        if company and cluster:
            prior = company_to_cluster.setdefault(company, cluster)
            if prior != cluster:
                findings.append("curriculum.company_id_maps_to_multiple_clusters:" + company)
    case_clusters = {str(case.get("company_cluster_id") or "") for case in cases}
    candidate_clusters: set[str] = set()
    for candidate in candidates:
        cluster = str(candidate.get("company_cluster_id") or "")
        if cluster in candidate_clusters:
            findings.append("curriculum.teaching_candidate_cluster_duplicate:" + cluster)
        candidate_clusters.add(cluster)
        if cluster in case_clusters:
            findings.append("curriculum.teaching_candidate_already_registered_as_case:" + cluster)
        for company in candidate.get("company_ids") or []:
            prior = company_to_cluster.setdefault(str(company), cluster)
            if prior != cluster:
                findings.append("curriculum.company_id_maps_to_multiple_clusters:" + str(company))

    learning_clusters = {
        str(case.get("company_cluster_id"))
        for case in cases
        if case.get("track") in {"TEACHING", "BLIND_JUDGMENT"}
    }
    for index, case in enumerate(cases):
        if case.get("track") != "HISTORICAL_HOLDOUT":
            continue
        if case.get("holdout_axis") in {"COMPANY", "COMPANY_AND_TIME"} \
                and case.get("company_cluster_id") in learning_clusters:
            findings.append(f"cases[{index}].company_holdout_cluster_seen_in_training")

    return {
        "schema_version": VALIDATION_VERSION,
        "valid": not findings,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": sorted(set(findings)),
        "progress": curriculum_status(root, validate=False),
    }


def _track_complete(track: str, status: str) -> bool:
    return status == {
        "TEACHING": "CURATED",
        "BLIND_JUDGMENT": "SETTLED",
        "HISTORICAL_HOLDOUT": "EVALUATED",
        "PROSPECTIVE": "SETTLED",
    }[track]


def curriculum_status(curriculum: dict[str, Any], *, validate: bool = True) -> dict[str, Any]:
    if validate:
        result = validate_curriculum(curriculum)
        if not result["valid"]:
            return {
                "schema_version": STATUS_VERSION,
                "state": "INVALID",
                "findings": result["findings"],
            }

    cases = list(curriculum.get("cases") or [])
    candidates = list(curriculum.get("teaching_candidate_pool") or [])
    track_progress: dict[str, Any] = {}
    for track in TRACKS:
        selected = [case for case in cases if case.get("track") == track]
        clusters = {case.get("company_cluster_id") for case in selected}
        complete = [case for case in selected if _track_complete(track, str(case.get("status") or ""))]
        complete_clusters = {case.get("company_cluster_id") for case in complete}
        target = (curriculum.get("capacity_targets") or {}).get(track) or {}
        lower = int(target.get("lower") or 0)
        track_progress[track] = {
            "episode_count": len(selected),
            "independent_company_cluster_count": len(clusters),
            "completed_episode_count": len(complete),
            "completed_independent_company_cluster_count": len(complete_clusters),
            "planning_range": target,
            "capacity_state": "AT_OR_ABOVE_LOWER_RANGE" if len(complete_clusters) >= lower else "BUILDING",
        }

    coverage: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        track = str(case.get("track") or "")
        status = str(case.get("status") or "")
        if track not in TRACKS or not _track_complete(track, status):
            continue
        for unit in case.get("primary_capability_units") or []:
            coverage[str(unit)].add(str(case.get("company_cluster_id") or ""))

    teaching_pipeline_coverage: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        if case.get("track") != "TEACHING":
            continue
        for unit in case.get("primary_capability_units") or []:
            teaching_pipeline_coverage[str(unit)].add(str(case.get("company_cluster_id") or ""))
    for candidate in candidates:
        for unit in candidate.get("primary_capability_units") or []:
            teaching_pipeline_coverage[str(unit)].add(str(candidate.get("company_cluster_id") or ""))

    curated_teaching = track_progress["TEACHING"]["completed_independent_company_cluster_count"]
    settled_blind = track_progress["BLIND_JUDGMENT"]["completed_independent_company_cluster_count"]
    teaching_per_blind = int((curriculum.get("execution_policy") or {}).get("teaching_cases_per_blind_cycle") or 3)
    registered_teaching = any(
        case.get("track") == "TEACHING" and case.get("status") == "REGISTERED" for case in cases
    )
    registered_blind = any(
        case.get("track") == "BLIND_JUDGMENT" and case.get("status") == "REGISTERED" for case in cases
    )
    if curated_teaching >= (settled_blind + 1) * teaching_per_blind:
        next_action = "FREEZE_NEXT_REGISTERED_BLIND_CASE" if registered_blind else "REGISTER_NEXT_BLIND_CASE"
    elif registered_teaching:
        next_action = "CURATE_NEXT_TEACHING_CASE"
    elif candidates:
        next_action = "CURATE_NEXT_TEACHING_CANDIDATE"
    else:
        next_action = "EXPAND_TEACHING_CANDIDATE_POOL"

    return {
        "schema_version": STATUS_VERSION,
        "state": "ACTIONABLE",
        "curriculum_id": curriculum.get("curriculum_id"),
        "curriculum_version": curriculum.get("curriculum_version"),
        "track_progress": track_progress,
        "teaching_candidate_pool": {
            "candidate_count": len(candidates),
            "independent_company_cluster_count": len({
                candidate.get("company_cluster_id") for candidate in candidates
            }),
            "teaching_library_pipeline_independent_company_cluster_count": len({
                case.get("company_cluster_id")
                for case in cases
                if case.get("track") == "TEACHING"
            } | {
                candidate.get("company_cluster_id") for candidate in candidates
            }),
            "ability_evidence_count": 0,
            "allowed_track": "TEACHING_ONLY_UNTIL_ROLE_SCOPED_RESELECTION",
        },
        "capability_coverage_by_distinct_company_clusters": {
            unit: len(coverage.get(unit, set())) for unit in sorted(CAPABILITY_UNITS)
        },
        "teaching_pipeline_coverage_by_distinct_company_clusters": {
            unit: len(teaching_pipeline_coverage.get(unit, set())) for unit in sorted(CAPABILITY_UNITS)
        },
        "next_action": next_action,
        "historical_training_blocked_by_holdout_or_prospective": False,
        "comparative_is_default_entry": False,
        "capability_claim": "NOT_DEMONSTRATED_BY_CURRICULUM_COUNTS",
        "method_utility_claim": "REQUIRES_BLIND_TREATMENT_FEEDBACK_AND_INDEPENDENT_HOLDOUT",
    }


def _read(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("curriculum must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "status"):
        item = sub.add_parser(command)
        item.add_argument("curriculum")
    route = sub.add_parser("route")
    route.add_argument("selection_exposure", choices=sorted(SELECTION_EXPOSURES))
    route.add_argument("--outcome-exists", action="store_true")
    route.add_argument("--outcome-released", action="store_true")
    args = parser.parse_args()

    if args.command == "route":
        result = route_candidate(
            selection_exposure=args.selection_exposure,
            outcome_exists=args.outcome_exists,
            outcome_released=args.outcome_released,
        )
    else:
        curriculum = _read(args.curriculum)
        result = validate_curriculum(curriculum) if args.command == "validate" else curriculum_status(curriculum)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("state") not in {"INVALID"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
