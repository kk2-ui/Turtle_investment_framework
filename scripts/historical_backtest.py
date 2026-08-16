#!/usr/bin/env python3
"""Validation primitives for the Phase 10 point-in-time backtest pilot.

This module intentionally does not run stock models or tune prices.  It makes
the experiment boundary executable: a frozen report can only use admissible
historical vintages, and later settlement must keep report coverage, model
error and investment outcome as separate ledgers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_SCHEMA_VERSION = "historical-backtest-experiment.v1"
CASE_SCHEMA_VERSION = "historical-backtest-case.v1"
SETTLEMENT_SCHEMA_VERSION = "historical-backtest-settlement.v1"
CASE_SCHEMA_VERSION_V2 = "historical-backtest-case.v2"
SETTLEMENT_SCHEMA_VERSION_V2 = "historical-backtest-settlement.v2"

ROUTES = {"LONG_TERM_OWNER", "FINITE_XIRR", "DUAL"}
PRIMARY_PRICE_IDENTITIES = {"P_LONG", "P_XIRR", "P_LEGAL", "P_BUSINESS_VALUE_EXIT", "UNKNOWN"}
INVESTMENT_ACTIONS = {"BUY", "HOLD", "WAIT", "SELL", "NO_BUY", "UNKNOWN"}
FILL_STATUSES = {"FILLED", "PARTIALLY_FILLED", "NOT_FILLED", "NOT_APPLICABLE"}
EXIT_STATUSES = {"EXITED", "MARKED_TO_MARKET", "OPEN", "NOT_APPLICABLE"}
RETURN_CASH_FLOW_TYPES = {
    "ENTRY", "EXIT", "MARK_TO_MARKET", "DIVIDEND", "CORPORATE_ACTION_CASH", "CASH_ALTERNATIVE",
}
CORPORATE_ACTION_TYPES = {
    "CASH_DIVIDEND", "STOCK_SPLIT", "RIGHTS_ISSUE", "MERGER", "DELISTING", "SPINOFF", "OTHER",
}
PREDICTION_SETTLEMENT_STATUSES = {"CALCULATED", "PARTIAL", "NOT_CALCULABLE"}
UNKNOWN_SETTLEMENT_STATUSES = {
    "UNRESOLVED_AS_OF_SETTLEMENT", "PARTIALLY_RESOLVED", "RESOLVED_MATERIAL", "RESOLVED_IMMATERIAL",
}
OPERATING_COMPARABILITY_STATUSES = {
    "COMPARABLE", "CONVERTIBLE_WITH_PREREGISTERED_RULE", "PERIOD_MISMATCH",
    "SCOPE_OR_ACCOUNTING_DRIFT", "NOT_COMPARABLE", "NOT_DISCLOSED",
}
COMPARABLE_OPERATING_STATUSES = {"COMPARABLE", "CONVERTIBLE_WITH_PREREGISTERED_RULE"}
PIT_TIMEZONE = timezone(timedelta(hours=8))
REPORT_REVIEW_DISPOSITIONS = {"SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNKNOWN_PRESERVED"}
QUALITY_FAILURE_CLASSIFICATIONS = {"DATA_COVERAGE", "ACQUISITION_MODULE", "REASONING", "MODEL", "WRITING"}
MODEL_MEMORY_CONTROLS = {"CONTROLLED", "MITIGATED", "UNCONTROLLED"}
BACKTEST_CREDIBILITIES = {"STRICT", "QUALIFIED", "EXPLORATORY"}
CALIBRATION_ROLES = {"ENGINEERING_DIAGNOSTIC_ONLY", "MODEL_MEMORY_CONTROLLED_CANDIDATE"}
MODEL_MEMORY_EXPECTATIONS = {
    "CONTROLLED": ("STRICT", "MODEL_MEMORY_CONTROLLED_CANDIDATE"),
    "MITIGATED": ("QUALIFIED", "ENGINEERING_DIAGNOSTIC_ONLY"),
    "UNCONTROLLED": ("EXPLORATORY", "ENGINEERING_DIAGNOSTIC_ONLY"),
}
REPORT_FREEZE_MODES = {"TEST_FIXTURE", "PRODUCTION_PIPELINE", "PIT_ENGINEERING"}
REPORT_ORIGIN_KINDS = {"TEST_FIXTURE", "TURTLE_PIPELINE", "PIT_ENGINEERING"}
REQUIRED_FROZEN_REPORT_SECTIONS = {
    "## Evidence", "## Operating forecast", "## Valuation", "## Risks and unknowns", "## Decision",
}
PIT_ENGINEERING_REPORT_SECTIONS = {
    "## Point-in-time scope", "## Evidence", "## Business and financial implications", "## Unknowns and monitoring",
}
REVIEWER_INDEPENDENCE_FIELDS = {
    "did_not_generate_candidate", "no_prior_review_seen", "reviewer_context_isolated", "generator_identity_disjoint",
}
OFFICIAL_SETTLEMENT_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT", "OFFICIAL_STATISTICS",
    "OFFICIAL_MARKET_DATA", "OTHER_OFFICIAL",
}
OPERATING_OBSERVATION_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT",
}
MEASUREMENT_PERIOD_KINDS = {"REPORTING_PERIOD", "EVENT_WINDOW"}
SOURCE_CONTENT_ACCESS = {"BODY_READ", "METADATA_ONLY"}
LEAKAGE_FIELDS = {
    "actual", "actual_value", "actual_outcome", "actual_outcomes", "outcome", "outcomes", "settlement",
    "settled_at", "future_price", "future_return", "realized_return", "benchmark_return",
}

PILOT_CASES = (
    ("87001.HK", "汇贤产业信托"),
    ("900936.SH", "鄂尔多斯B"),
    ("000651.SZ", "格力电器"),
    ("01522.HK", "京投交通科技"),
    ("02669.HK", "中海物业"),
    ("00506.HK", "中国食品"),
    ("00882.HK", "天津发展"),
    ("600585.SH", "海螺水泥"),
    ("601899.SH", "紫金矿业"),
)


def _date(value: Any) -> date | None:
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


def _timestamp(value: Any, *, date_only_at_end: bool = False) -> datetime | None:
    """Parse a point-in-time value without silently discarding its clock time.

    Historical source indexes sometimes expose only a calendar day.  Treating
    that day as its end is conservative when deciding whether a source was
    available by a cutoff; execution events instead use the start of a
    date-only day, so they cannot be assumed to occur after an intraday cutoff.
    """
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 10:
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            return None
        clock_time = time.max if date_only_at_end else time.min
        return datetime.combine(parsed_date, clock_time, tzinfo=PIT_TIMEZONE)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_date_only(value: Any) -> bool:
    text = str(value or "").strip()
    return len(text) == 10 and _date(text) is not None


def _is_case_v2(record: dict[str, Any] | None) -> bool:
    return isinstance(record, dict) and record.get("schema_version") == CASE_SCHEMA_VERSION_V2


def _measurement_period(outcome: dict[str, Any], *, v2: bool) -> dict[str, Any]:
    if v2:
        value = outcome.get("measurement_period")
        return value if isinstance(value, dict) else {}
    return {
        "kind": "REPORTING_PERIOD",
        "start": outcome.get("period_start"),
        "end": outcome.get("period_end"),
    }


def _required(record: dict[str, Any], fields: Iterable[str], prefix: str) -> list[str]:
    return [f"{prefix}:missing:{field}" for field in fields if record.get(field) in (None, "", [], {})]


def _number(value: Any) -> float | None:
    """Return a finite numeric value without accepting bools as money."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _numbers_match(left: Any, right: Any) -> bool:
    lhs = _number(left)
    rhs = _number(right)
    return lhs is not None and rhs is not None and math.isclose(lhs, rhs, rel_tol=1e-9, abs_tol=1e-9)


def _nested_forbidden(value: Any, *, path: str = "") -> list[str]:
    """Find hindsight keys in model inputs without treating prose as evidence."""
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{path}.{key}" if path else str(key)
            if normalized in LEAKAGE_FIELDS:
                findings.append(f"future_field_in_frozen_input:{child_path}")
            findings.extend(_nested_forbidden(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_nested_forbidden(child, path=f"{path}[{index}]"))
    return findings


def _read_repo_artifact(artifact_path: Any, *, prefix: str) -> tuple[str, str, list[str], list[str]]:
    """Read a UTF-8 artifact only from this repository and return its identity."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        return "", "", invalid, incomplete
    candidate = Path(artifact_path)
    root = Path(__file__).resolve().parents[1]
    if candidate.is_absolute():
        invalid.append(prefix + ":artifact_path_must_be_repo_relative")
        return "", "", invalid, incomplete
    resolved = (root / candidate).resolve()
    if root not in resolved.parents:
        invalid.append(prefix + ":artifact_path_outside_repository")
        return "", "", invalid, incomplete
    if not resolved.is_file():
        incomplete.append(prefix + ":artifact_missing")
        return "", "", invalid, incomplete
    raw = resolved.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        content = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        invalid.append(prefix + ":artifact_not_utf8")
        return "", digest, invalid, incomplete
    if not content:
        incomplete.append(prefix + ":artifact_empty")
    return content, digest, invalid, incomplete


def _validate_actor_provenance(provenance: Any, *, prefix: str) -> tuple[str, str, list[str], list[str]]:
    """Validate the declared identity used by a writer or independent reviewer."""
    invalid: list[str] = []
    incomplete: list[str] = []
    item = provenance if isinstance(provenance, dict) else {}
    actor_type = str(item.get("actor_type") or "")
    context_id = str(item.get("context_id") or "").strip()
    if actor_type not in {"human", "model", "hybrid"}:
        invalid.append(prefix + ":actor_type_invalid")
    if not context_id:
        incomplete.append(prefix + ":context_id_missing")
    identity = ""
    if actor_type in {"model", "hybrid"}:
        provider = str(item.get("provider") or "").strip().lower()
        model = str(item.get("model") or "").strip().lower()
        if not provider or not model:
            incomplete.append(prefix + ":model_identity_missing")
        else:
            identity = provider + ":" + model
    return context_id, identity, invalid, incomplete


def _validate_credibility(record: dict[str, Any], *, prefix: str = "credibility") -> tuple[list[str], list[str]]:
    """Keep model-memory uncertainty explicit without blocking engineering replay.

    A `STRICT` label or any calibration-candidate role is an assertion about the
    model-memory control itself, so it needs positive, inspectable evidence.
    That evidence only clears this one dimension; the separately preregistered
    sampling and holdout rules still decide whether calibration may proceed.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    credibility = record.get("credibility") if isinstance(record.get("credibility"), dict) else {}
    incomplete.extend(_required(
        credibility,
        ("model_memory_control", "backtest_credibility", "assessment_basis", "calibration_role"),
        prefix,
    ))
    if "control_evidence" not in credibility:
        incomplete.append(prefix + ":missing:control_evidence")
    memory_control = credibility.get("model_memory_control")
    credibility_level = credibility.get("backtest_credibility")
    calibration_role = credibility.get("calibration_role")
    if memory_control not in MODEL_MEMORY_CONTROLS:
        invalid.append(prefix + ":model_memory_control_invalid")
    if credibility_level not in BACKTEST_CREDIBILITIES:
        invalid.append(prefix + ":backtest_credibility_invalid")
    if calibration_role not in CALIBRATION_ROLES:
        invalid.append(prefix + ":calibration_role_invalid")
    expected = MODEL_MEMORY_EXPECTATIONS.get(memory_control)
    if expected:
        expected_credibility, expected_role = expected
        if credibility_level != expected_credibility:
            invalid.append(prefix + ":backtest_credibility_inconsistent_with_model_memory_control")
        if calibration_role != expected_role:
            invalid.append(prefix + ":calibration_role_inconsistent_with_model_memory_control")
    evidence_value = credibility.get("control_evidence")
    if evidence_value is not None and not isinstance(evidence_value, list):
        invalid.append(prefix + ":control_evidence_invalid")
    evidence = evidence_value if isinstance(evidence_value, list) else []
    if memory_control in {"CONTROLLED", "MITIGATED"} and not evidence:
        invalid.append(prefix + ":controlled_or_mitigated_memory_requires_control_evidence")
    if memory_control == "UNCONTROLLED" and evidence:
        invalid.append(prefix + ":uncontrolled_memory_cannot_claim_control_evidence")
    evidence_ids: set[str] = set()
    evidence_levels: set[str] = set()
    test_namespace = str(record.get("case_id") or record.get("experiment_id") or "") in {"HBTCASE:TEST", "HBT:test"}
    if memory_control == "CONTROLLED" and not test_namespace:
        # A repository-authored artifact cannot attest to the model/provider,
        # isolated context, and deployment boundary that a strict replay needs.
        incomplete.append(prefix + ":controlled_memory_requires_deployment_attestation")
    for index, item in enumerate(evidence):
        evidence_prefix = f"{prefix}.control_evidence[{index}]"
        if not isinstance(item, dict):
            invalid.append(evidence_prefix + ":not_object")
            continue
        incomplete.extend(_required(
            item, ("evidence_id", "artifact_path", "artifact_sha256", "control_level", "method", "verifier_id", "scope"), evidence_prefix,
        ))
        evidence_id = str(item.get("evidence_id") or "")
        if not evidence_id.startswith("HBTMEM:"):
            invalid.append(evidence_prefix + ":evidence_id_invalid")
        elif evidence_id in evidence_ids:
            invalid.append("duplicate_model_memory_evidence_id:" + evidence_id)
        evidence_ids.add(evidence_id)
        control_level = item.get("control_level")
        if control_level not in {"MITIGATION", "CONTROL"}:
            invalid.append(evidence_prefix + ":control_level_invalid")
        else:
            evidence_levels.add(control_level)
        for field in ("method", "verifier_id", "scope"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                invalid.append(evidence_prefix + ":" + field + "_invalid")
        content, digest, artifact_invalid, artifact_incomplete = _read_repo_artifact(
            item.get("artifact_path"), prefix=evidence_prefix,
        )
        invalid.extend(artifact_invalid)
        incomplete.extend(artifact_incomplete)
        artifact_path = str(item.get("artifact_path") or "")
        if artifact_path.startswith("tests/fixtures/") and not test_namespace:
            invalid.append(evidence_prefix + ":test_fixture_forbidden_outside_test_namespace")
        if not isinstance(item.get("artifact_sha256"), str) or item.get("artifact_sha256") != digest:
            invalid.append(evidence_prefix + ":artifact_sha256_mismatch")
        if content and evidence_id not in content:
            invalid.append(evidence_prefix + ":artifact_evidence_id_missing")
        if content:
            for field in ("method", "verifier_id", "scope"):
                value = str(item.get(field) or "").strip()
                if value and value not in content:
                    invalid.append(evidence_prefix + ":artifact_" + field + "_missing")
    if memory_control == "MITIGATED" and "MITIGATION" not in evidence_levels:
        invalid.append(prefix + ":mitigated_memory_requires_mitigation_evidence")
    if memory_control == "CONTROLLED" and "CONTROL" not in evidence_levels:
        invalid.append(prefix + ":controlled_memory_requires_control_evidence")
    return invalid, incomplete


def _validate_case_experiment_credibility(
    record: dict[str, Any], *, experiment: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    """Prevent a case from upgrading its model-memory credibility over its experiment."""
    invalid: list[str] = []
    incomplete: list[str] = []
    case_credibility = record.get("credibility") if isinstance(record.get("credibility"), dict) else {}
    candidate = case_credibility.get("calibration_role") == "MODEL_MEMORY_CONTROLLED_CANDIDATE"
    if experiment is None:
        if candidate:
            incomplete.append("credibility:experiment_required_for_calibration_candidate")
        return invalid, incomplete
    experiment_result = validate_experiment(experiment)
    if experiment_result["state"] != "REVIEWABLE":
        invalid.append("credibility:experiment_not_reviewable")
    if record.get("experiment_id") != experiment.get("experiment_id"):
        invalid.append("credibility:case_experiment_id_does_not_match_experiment")
    experiment_credibility = experiment.get("credibility") if isinstance(experiment.get("credibility"), dict) else {}
    for field in ("model_memory_control", "backtest_credibility", "calibration_role"):
        if case_credibility.get(field) != experiment_credibility.get(field):
            invalid.append("credibility:" + field + "_does_not_match_experiment")
    if case_credibility.get("control_evidence") != experiment_credibility.get("control_evidence"):
        invalid.append("credibility:control_evidence_does_not_match_experiment")
    if candidate:
        universe = experiment.get("universe") if isinstance(experiment.get("universe"), dict) else {}
        experiment_cases = universe.get("cases") if isinstance(universe.get("cases"), list) else []
        matching_cases = [
            item for item in experiment_cases
            if isinstance(item, dict) and item.get("case_id") == record.get("case_id")
        ]
        if len(matching_cases) != 1:
            invalid.append("credibility:calibration_candidate_not_preregistered_in_experiment")
        else:
            registered = matching_cases[0]
            for field in ("company_code", "simulation_cutoff", "route"):
                if registered.get(field) != record.get(field):
                    invalid.append("credibility:calibration_candidate_" + field + "_does_not_match_experiment")
            if registered.get("eligibility_status") != "ELIGIBLE":
                invalid.append("credibility:calibration_candidate_not_eligible_in_experiment")
            if registered.get("calibration_eligibility") != "MODEL_MEMORY_CONTROLLED_CANDIDATE":
                invalid.append("credibility:calibration_candidate_not_registered_for_calibration")
    if candidate and not experiment_result["state"] == "REVIEWABLE":
        invalid.append("credibility:calibration_candidate_requires_reviewable_experiment")
    return invalid, incomplete


def validate_experiment(record: dict[str, Any]) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if record.get("schema_version") != EXPERIMENT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(record.get("experiment_id") or "").startswith("HBT:"):
        invalid.append("experiment_id_invalid")
    framework = record.get("framework") if isinstance(record.get("framework"), dict) else {}
    if framework.get("golden_gate_state") != "G3_NOT_READY":
        invalid.append("golden_gate_must_remain_g3_not_ready")
    policy = record.get("information_policy") if isinstance(record.get("information_policy"), dict) else {}
    expected_policy = {
        "source_rule": "published_at_and_data_as_of_must_not_exceed_cutoff",
        "current_restated_data_rule": "current_restated_values_are_ineligible_without_historical_vintage",
        "future_file_rule": "future_files_are_unreadable_before_settlement",
        "survivorship_rule": "retain_delisted_acquired_and_failed_cases_in_registered_universe",
    }
    for field, expected in expected_policy.items():
        if policy.get(field) != expected:
            invalid.append(f"information_policy:{field}_invalid")
    credibility_invalid, credibility_incomplete = _validate_credibility(record)
    invalid.extend(credibility_invalid)
    incomplete.extend(credibility_incomplete)
    scoring = record.get("scoring_policy") if isinstance(record.get("scoring_policy"), dict) else {}
    if scoring.get("separate_dimensions") != ["REPORT_COVERAGE", "MODEL_FORECAST_ERROR", "INVESTMENT_RETURN_OUTCOME"]:
        invalid.append("scoring_dimensions_must_remain_separate")
    if scoring.get("no_compensating_score") is not True:
        invalid.append("compensating_score_forbidden")
    universe = record.get("universe") if isinstance(record.get("universe"), dict) else {}
    cases = universe.get("cases") if isinstance(universe.get("cases"), list) else []
    if not cases:
        incomplete.append("universe_cases_missing")
    eligible = [item for item in cases if isinstance(item, dict) and item.get("eligibility_status") == "ELIGIBLE"]
    if universe.get("eligible_case_count") != len(eligible):
        invalid.append("eligible_case_count_mismatch")
    calibration_candidates = [
        item for item in cases
        if isinstance(item, dict) and item.get("calibration_eligibility") == "MODEL_MEMORY_CONTROLLED_CANDIDATE"
    ]
    if universe.get("calibration_eligible_case_count") != len(calibration_candidates):
        invalid.append("calibration_eligible_case_count_mismatch")
    credibility = record.get("credibility") if isinstance(record.get("credibility"), dict) else {}
    experiment_can_nominate_calibration_candidates = (
        credibility.get("model_memory_control") == "CONTROLLED"
        and credibility.get("backtest_credibility") == "STRICT"
        and credibility.get("calibration_role") == "MODEL_MEMORY_CONTROLLED_CANDIDATE"
    )
    ids: set[str] = set()
    for index, item in enumerate(cases):
        prefix = f"universe.cases[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        case_id = str(item.get("case_id") or "")
        if not case_id.startswith("HBTCASE:"):
            invalid.append(prefix + ":case_id_invalid")
        if case_id in ids:
            invalid.append(prefix + ":duplicate_case_id")
        ids.add(case_id)
        if not str(item.get("eligibility_reason") or "").strip():
            incomplete.append(prefix + ":eligibility_reason_missing")
        if item.get("eligibility_status") == "ELIGIBLE" and not item.get("route"):
            incomplete.append(prefix + ":eligible_route_missing")
        if item.get("eligibility_status") == "ELIGIBLE" and not str(item.get("simulation_cutoff") or "").strip():
            incomplete.append(prefix + ":eligible_simulation_cutoff_missing")
        calibration_eligibility = item.get("calibration_eligibility")
        if calibration_eligibility not in {"NOT_ELIGIBLE_MODEL_MEMORY", "MODEL_MEMORY_CONTROLLED_CANDIDATE"}:
            invalid.append(prefix + ":calibration_eligibility_invalid")
        elif calibration_eligibility == "MODEL_MEMORY_CONTROLLED_CANDIDATE":
            if item.get("eligibility_status") != "ELIGIBLE":
                invalid.append(prefix + ":calibration_candidate_must_be_eligible")
            if not experiment_can_nominate_calibration_candidates:
                invalid.append(prefix + ":experiment_model_memory_not_controlled_for_calibration")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def _validate_source(source: dict[str, Any], cutoff: datetime, index: int) -> tuple[list[str], list[str]]:
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = f"sources[{index}]"
    published = _timestamp(source.get("published_at"), date_only_at_end=True)
    data_as_of = _date(source.get("data_as_of"))
    revision = _timestamp(source.get("revision_published_at"), date_only_at_end=True) if source.get("revision_published_at") else None
    if published is None or data_as_of is None:
        incomplete.append(prefix + ":published_at_or_data_as_of_missing")
    else:
        if _is_date_only(source.get("published_at")) and published.astimezone(PIT_TIMEZONE).date() == cutoff.astimezone(PIT_TIMEZONE).date():
            incomplete.append(prefix + ":published_at_time_required_on_cutoff_date")
        if published > cutoff:
            invalid.append(prefix + ":future_published_at")
        if data_as_of > cutoff.date():
            invalid.append(prefix + ":future_data_as_of")
    if revision and revision > cutoff:
        invalid.append(prefix + ":future_revision")
    if source.get("revision_policy") == "CURRENT_RESTATED_ONLY":
        invalid.append(prefix + ":current_restated_data_not_admissible")
    if not str(source.get("source_version") or "").strip():
        incomplete.append(prefix + ":source_version_missing")
    if source.get("admissible") is not True:
        invalid.append(prefix + ":source_not_admissible")
    return invalid, incomplete


def _validate_source_references(
    references: Any, known_source_ids: set[str], prefix: str,
) -> tuple[list[str], list[str]]:
    """Require ledger links to resolve to the frozen source manifest."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(references, list) or not references:
        incomplete.append(prefix + ":source_ids_missing")
        return invalid, incomplete
    for source_id in references:
        source_id = str(source_id or "")
        if not source_id:
            incomplete.append(prefix + ":source_id_empty")
        elif source_id not in known_source_ids:
            invalid.append(prefix + ":source_id_not_found:" + source_id)
    return invalid, incomplete


def _validate_calibration_ledger(
    record: dict[str, Any], known_source_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Validate the frozen, claim-level calibration contract for a case."""
    invalid: list[str] = []
    incomplete: list[str] = []
    case_v2 = _is_case_v2(record)
    simulation_cutoff = _timestamp(record.get("simulation_cutoff"))
    ledger = record.get("calibration_ledger") if isinstance(record.get("calibration_ledger"), dict) else {}
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    if not claims:
        incomplete.append("calibration_ledger:claims_missing")
        return invalid, incomplete
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        prefix = f"calibration_ledger.claims[{index}]"
        if not isinstance(claim, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(
            claim,
            (
                "claim_id", "statement", "materiality", "frozen_disposition", "source_ids", "counter_thesis",
                "flip_condition", "observable_outcome",
            ),
            prefix,
        ))
        for field in ("prediction", "threshold", "unknown"):
            if field not in claim:
                incomplete.append(prefix + ":missing:" + field)
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id.startswith("HBTCLM:"):
            invalid.append(prefix + ":claim_id_invalid")
        elif claim_id in claim_ids:
            invalid.append("duplicate_calibration_claim_id:" + claim_id)
        claim_ids.add(claim_id)
        if claim.get("materiality") not in {"CENTRAL_THESIS", "VALUATION", "RETURN", "PERMANENT_LOSS"}:
            invalid.append(prefix + ":materiality_invalid")
        disposition = claim.get("frozen_disposition")
        if disposition not in {"PREDICTION", "UNKNOWN"}:
            invalid.append(prefix + ":frozen_disposition_invalid")
        ref_invalid, ref_incomplete = _validate_source_references(claim.get("source_ids"), known_source_ids, prefix)
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
        outcome_prefix = prefix + ".observable_outcome"
        period_fields = ("measurement_period", "observation_window") if case_v2 else ("period_start", "period_end")
        incomplete.extend(_required(
            outcome,
            ("metric", "unit", "measurement_basis", "measurement_rule", *period_fields,
             "allowed_source_types", "settlement_version_policy"),
            outcome_prefix,
        ))
        period = _measurement_period(outcome, v2=case_v2)
        period_prefix = outcome_prefix + (".measurement_period" if case_v2 else "")
        period_start = _date(period.get("start"))
        period_end = _date(period.get("end"))
        if period.get("start") not in (None, "") and period_start is None:
            invalid.append(period_prefix + (":start_invalid" if case_v2 else ":period_start_invalid"))
        if period.get("end") not in (None, "") and period_end is None:
            invalid.append(period_prefix + (":end_invalid" if case_v2 else ":period_end_invalid"))
        if period_start and period_end and period_start > period_end:
            invalid.append(period_prefix + (":start_after_end" if case_v2 else ":period_start_after_period_end"))
        if case_v2:
            if any(field in outcome for field in ("period_start", "period_end")):
                invalid.append(outcome_prefix + ":legacy_period_fields_not_allowed")
            if period.get("kind") not in MEASUREMENT_PERIOD_KINDS:
                invalid.append(period_prefix + ":kind_invalid")
            window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
            window_prefix = outcome_prefix + ".observation_window"
            opens_after = _timestamp(window.get("opens_after"))
            closes_at = _timestamp(window.get("closes_at"))
            if window.get("opens_after") not in (None, "") and opens_after is None:
                invalid.append(window_prefix + ":opens_after_invalid")
            if window.get("closes_at") not in (None, "") and closes_at is None:
                invalid.append(window_prefix + ":closes_at_invalid")
            if opens_after and closes_at and opens_after >= closes_at:
                invalid.append(window_prefix + ":opens_after_must_precede_closes_at")
            if simulation_cutoff and opens_after and opens_after < simulation_cutoff:
                invalid.append(window_prefix + ":opens_before_simulation_cutoff")
        allowed_source_types = outcome.get("allowed_source_types")
        if isinstance(allowed_source_types, list):
            for source_type in allowed_source_types:
                if source_type not in OPERATING_OBSERVATION_SOURCE_TYPES:
                    invalid.append(outcome_prefix + ":allowed_source_type_invalid:" + str(source_type))
        elif allowed_source_types not in (None, ""):
            invalid.append(outcome_prefix + ":allowed_source_types_not_list")
        if outcome.get("settlement_version_policy") not in {
            "INITIAL_DISCLOSURE", "LATEST_OFFICIAL_AS_OF_EVALUATION",
        }:
            invalid.append(outcome_prefix + ":settlement_version_policy_invalid")
        conversion_rule = outcome.get("conversion_rule")
        if conversion_rule is not None:
            if not isinstance(conversion_rule, dict):
                invalid.append(outcome_prefix + ":conversion_rule_not_object")
            else:
                conversion_prefix = outcome_prefix + ".conversion_rule"
                incomplete.extend(_required(
                    conversion_rule, ("rule_id", "raw_unit", "converted_unit", "multiplier"), conversion_prefix,
                ))
                for field in ("rule_id", "raw_unit", "converted_unit"):
                    if not isinstance(conversion_rule.get(field), str) or not conversion_rule.get(field).strip():
                        invalid.append(conversion_prefix + ":" + field + "_invalid")
                if conversion_rule.get("converted_unit") != outcome.get("unit"):
                    invalid.append(conversion_prefix + ":converted_unit_does_not_match_observable_outcome")
                multiplier = _number(conversion_rule.get("multiplier"))
                if multiplier is None or multiplier <= 0:
                    invalid.append(conversion_prefix + ":multiplier_invalid")
        if disposition == "PREDICTION":
            prediction = claim.get("prediction") if isinstance(claim.get("prediction"), dict) else {}
            threshold = claim.get("threshold") if isinstance(claim.get("threshold"), dict) else {}
            incomplete.extend(_required(prediction, ("metric", "operator", "value", "unit", "horizon"), prefix + ".prediction"))
            incomplete.extend(_required(threshold, ("metric", "operator", "value", "unit", "consequence"), prefix + ".threshold"))
            for field in ("metric", "unit"):
                if prediction.get(field) != outcome.get(field):
                    invalid.append(prefix + ".prediction:" + field + "_does_not_match_observable_outcome")
                if threshold.get(field) != outcome.get(field):
                    invalid.append(prefix + ".threshold:" + field + "_does_not_match_observable_outcome")
            if claim.get("unknown") is not None:
                invalid.append(prefix + ":prediction_cannot_carry_unknown_payload")
        elif disposition == "UNKNOWN":
            unknown = claim.get("unknown") if isinstance(claim.get("unknown"), dict) else {}
            incomplete.extend(_required(unknown, ("statement", "economic_impact", "resolution_observation"), prefix + ".unknown"))
            if claim.get("prediction") is not None or claim.get("threshold") is not None:
                invalid.append(prefix + ":unknown_cannot_carry_quantitative_prediction")
    return invalid, incomplete


def _frozen_predictions(case: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(case, dict):
        return {}
    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    return {
        str(claim.get("claim_id")): claim
        for claim in claims
        if isinstance(claim, dict) and isinstance(claim.get("prediction"), dict)
    }


def _frozen_claims(case: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(case, dict):
        return {}
    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    return {
        str(claim.get("claim_id")): claim
        for claim in claims
        if isinstance(claim, dict) and str(claim.get("claim_id") or "")
    }


def _route_findings(record: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    route = record.get("route")
    forecast = record.get("forecast") if isinstance(record.get("forecast"), dict) else {}
    price = record.get("price_identity") if isinstance(record.get("price_identity"), dict) else {}
    primary_route = price.get("primary_route")
    primary_price = price.get("primary_price_identity")
    if route not in ROUTES:
        findings.append("route_invalid")
        return findings
    horizon = forecast.get("horizon_years")
    if not isinstance(horizon, (int, float)) or horizon < 0:
        findings.append("forecast_horizon_invalid")
    if route in {"FINITE_XIRR", "DUAL"} and (not isinstance(horizon, (int, float)) or horizon <= 0):
        findings.append("finite_route_requires_positive_horizon")
    if route == "LONG_TERM_OWNER":
        if primary_route != "LONG_TERM_OWNER" or primary_price != "P_LONG":
            findings.append("long_term_route_requires_p_long_primary")
        if forecast.get("terminal_handling") not in {"NO_REQUIRED_EXIT", "DUAL_TERMINAL_PATH"}:
            findings.append("long_term_route_terminal_handling_invalid")
    elif route == "FINITE_XIRR":
        if primary_route != "FINITE_XIRR" or primary_price not in {"P_XIRR", "P_LEGAL", "P_BUSINESS_VALUE_EXIT"}:
            findings.append("finite_route_requires_finite_price_primary")
        if forecast.get("terminal_handling") not in {"BUSINESS_VALUE_EXIT", "MARKET_EXIT", "LEGAL_END"}:
            findings.append("finite_route_terminal_handling_invalid")
    else:
        if primary_route not in {"DUAL", "PRIMARY_ROUTE_UNKNOWN"}:
            findings.append("dual_route_primary_route_invalid")
        if primary_route == "PRIMARY_ROUTE_UNKNOWN" and primary_price != "UNKNOWN":
            findings.append("unknown_primary_route_requires_unknown_price")
        if forecast.get("terminal_handling") != "DUAL_TERMINAL_PATH":
            findings.append("dual_route_requires_dual_terminal_path")
    if primary_price == "P_XIRR" and forecast.get("terminal_handling") == "MARKET_EXIT" and forecast.get("independent_terminal_evidence") is not True:
        findings.append("fixed_market_terminal_price_cannot_be_primary_without_independent_evidence")
    return findings


def _frozen_price(case: dict[str, Any], identity: str) -> dict[str, Any] | None:
    price_identity = case.get("price_identity") if isinstance(case.get("price_identity"), dict) else {}
    prices = price_identity.get("prices") if isinstance(price_identity.get("prices"), list) else []
    return next(
        (price for price in prices if isinstance(price, dict) and price.get("identity") == identity),
        None,
    )


def _validate_investment_decision(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Validate the action and price identity frozen with the report.

    The field is optional for legacy frozen cases, but a settlement that claims
    an investment outcome must bind to it.  This keeps old calibration-only
    records readable while refusing to manufacture a return from them.
    """
    decision = record.get("investment_decision")
    if decision is None:
        return [], []
    if not isinstance(decision, dict):
        return ["investment_decision:not_object"], []
    invalid: list[str] = []
    incomplete = _required(decision, ("action", "price_identity", "execution_rule"), "investment_decision")
    action = decision.get("action")
    identity = str(decision.get("price_identity") or "")
    if action not in INVESTMENT_ACTIONS:
        invalid.append("investment_decision:action_invalid")
    if identity not in PRIMARY_PRICE_IDENTITIES:
        invalid.append("investment_decision:price_identity_invalid")
    elif identity == "UNKNOWN":
        if action not in {"NO_BUY", "UNKNOWN"}:
            invalid.append("investment_decision:unknown_price_identity_requires_no_buy_or_unknown_action")
    elif _frozen_price(record, identity) is None:
        invalid.append("investment_decision:price_identity_not_registered_in_frozen_case")
    return invalid, incomplete


def _validate_production_report_origin(
    record: dict[str, Any], *, report: dict[str, Any], artifact_sha256: str, origin: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Require the unified pipeline and V3 acceptance artifacts for real cases."""
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = "report_freeze.frozen_report.origin"
    required = (
        "output_dir", "acceptance_root", "sample_id", "run_manifest_path",
        "completion_report_path", "publication_snapshot_path",
    )
    incomplete.extend(_required(origin, required, prefix))
    root = Path(__file__).resolve().parents[1]

    def repo_path(value: Any, field: str) -> Path | None:
        raw = str(value or "")
        if not raw or Path(raw).is_absolute():
            invalid.append(prefix + ":" + field + "_must_be_repo_relative")
            return None
        resolved = (root / raw).resolve()
        if root not in resolved.parents:
            invalid.append(prefix + ":" + field + "_outside_repository")
            return None
        return resolved

    def load_json(path: Path | None, field: str) -> dict[str, Any]:
        if path is None:
            return {}
        if not path.is_file():
            incomplete.append(prefix + ":" + field + "_missing")
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            invalid.append(prefix + ":" + field + "_invalid_json")
            return {}
        if not isinstance(value, dict):
            invalid.append(prefix + ":" + field + "_must_be_object")
            return {}
        return value

    def load_pit_json(path: Path | None, field: str) -> dict[str, Any]:
        payload = load_json(path, field)
        return payload

    output_dir = repo_path(origin.get("output_dir"), "output_dir")
    acceptance_root = repo_path(origin.get("acceptance_root"), "acceptance_root")
    run_manifest = repo_path(origin.get("run_manifest_path"), "run_manifest_path")
    completion = repo_path(origin.get("completion_report_path"), "completion_report_path")
    snapshot = repo_path(origin.get("publication_snapshot_path"), "publication_snapshot_path")
    expected_manifest = output_dir / "run_manifest.json" if output_dir else None
    expected_completion = output_dir / "completion_report.json" if output_dir else None
    if run_manifest and expected_manifest and run_manifest != expected_manifest:
        invalid.append(prefix + ":run_manifest_path_does_not_match_output_dir")
    if completion and expected_completion and completion != expected_completion:
        invalid.append(prefix + ":completion_report_path_does_not_match_output_dir")
    run_payload = load_json(run_manifest, "run_manifest")
    completion_payload = load_json(completion, "completion_report")
    snapshot_payload = load_json(snapshot, "publication_snapshot")
    acceptance_payload = load_json(
        acceptance_root / "acceptance_baseline.json" if acceptance_root else None,
        "acceptance_baseline",
    )
    report_status = (record.get("report_freeze") or {}).get("report_status")
    pipeline_variant: dict[str, Any] = {}
    if output_dir and output_dir.is_dir():
        try:
            from scripts.real_report_acceptance import resolve_report_variant
            pipeline_variant = resolve_report_variant(output_dir)
        except (ImportError, OSError, ValueError) as exc:
            invalid.append(prefix + ":pipeline_variant_unreadable:" + type(exc).__name__)
            pipeline_variant = {}
        pipeline_report = pipeline_variant.get("report")
        report_path = repo_path(report.get("artifact_path"), "report_artifact_path")
        if pipeline_report is None:
            incomplete.append(prefix + ":pipeline_report_missing")
        elif report_path and pipeline_report.resolve() != report_path:
            invalid.append(prefix + ":report_artifact_does_not_match_pipeline_report")
        if pipeline_variant.get("variant_id") and pipeline_variant.get("variant_id") != report.get("variant_id"):
            invalid.append(prefix + ":pipeline_variant_id_mismatch")
    pipeline_report_sha256 = pipeline_variant.get("report_sha256") if isinstance(pipeline_variant, dict) else ""
    if report_status == "FROZEN":
        if run_payload.get("status") != "COMPLETED":
            invalid.append(prefix + ":frozen_report_requires_completed_run_manifest")
        if completion_payload.get("status") not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
            invalid.append(prefix + ":frozen_report_requires_complete_pipeline")
        if not snapshot_payload:
            incomplete.append(prefix + ":publication_snapshot_missing")
    if snapshot_payload.get("report_sha256") not in {None, "", artifact_sha256}:
        invalid.append(prefix + ":publication_snapshot_report_sha256_mismatch")

    # A production report is only readable when its source-package runner has
    # recorded the same cutoff, company and admitted source identities as the
    # case.  This is a replayable declared-process boundary, not a model-memory
    # or deployment-signature claim.
    pit_prefix = prefix + ".pit_runner"
    # P10-A provides the reusable source-package gate and audit.  The current
    # turtle_agent read tools have not yet been routed through it, so an
    # attestation alone cannot establish that a production writer lacked all
    # alternate filesystem and web reads.
    incomplete.append(pit_prefix + ":tool_boundary_not_integrated")
    pit = origin.get("pit_runner") if isinstance(origin.get("pit_runner"), dict) else {}
    incomplete.extend(_required(
        pit,
        ("attestation_path", "source_package_manifest_path", "package_root", "status"),
        pit_prefix,
    ))
    pit_attestation_path = repo_path(pit.get("attestation_path"), "pit_runner_attestation_path")
    pit_manifest_path = repo_path(pit.get("source_package_manifest_path"), "source_package_manifest_path")
    pit_package_root = repo_path(pit.get("package_root"), "pit_runner_package_root")
    if pit_package_root and any(part.lower() in {"settlement", "settlements", "output", "results", "outcomes"} for part in pit_package_root.parts):
        invalid.append(pit_prefix + ":package_root_must_be_historical_input")
    pit_attestation = load_pit_json(pit_attestation_path, "pit_runner_attestation")
    pit_manifest = load_pit_json(pit_manifest_path, "source_package_manifest")
    if pit.get("status") != "PASS":
        incomplete.append(pit_prefix + ":status_not_pass")
    if pit_attestation:
        incomplete.extend(_required(
            pit_attestation,
            ("case_id", "experiment_id", "run_id", "manifest_path", "package_root", "framework_root", "framework_root_class", "cutoff_at", "allowed_source_ids", "source_allowlist", "framework_allowlist", "read_audit", "read_count", "forbidden_success_count"),
            pit_prefix + ".attestation",
        ))
        if pit_attestation.get("schema_version") != "phase10-pit-runner-attestation.v1":
            invalid.append(pit_prefix + ":attestation_schema_invalid")
        if pit_attestation.get("runner") != "phase10_pit_runner":
            invalid.append(pit_prefix + ":runner_invalid")
        if pit_attestation.get("state") != "REVIEWABLE":
            incomplete.append(pit_prefix + ":attestation_not_reviewable")
        if pit_attestation.get("assurance_level") != "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS":
            invalid.append(pit_prefix + ":assurance_level_invalid")
        static_framework_root = (root / "config" / "phase10_pit_framework").resolve()
        if pit_attestation.get("framework_root_class") != "REPOSITORY_STATIC":
            invalid.append(pit_prefix + ":framework_root_class_invalid")
        try:
            if Path(str(pit_attestation.get("framework_root") or "")).resolve() != static_framework_root:
                invalid.append(pit_prefix + ":framework_root_invalid")
        except OSError:
            invalid.append(pit_prefix + ":framework_root_invalid")
        if pit_attestation.get("company_code") != record.get("company_code"):
            invalid.append(pit_prefix + ":company_code_mismatch")
        if pit_attestation.get("case_id") != record.get("case_id"):
            invalid.append(pit_prefix + ":case_id_mismatch")
        if pit_attestation.get("experiment_id") != record.get("experiment_id"):
            invalid.append(pit_prefix + ":experiment_id_mismatch")
        if not run_payload.get("run_id"):
            incomplete.append(pit_prefix + ":pipeline_run_id_missing")
        elif pit_attestation.get("run_id") != run_payload.get("run_id"):
            invalid.append(pit_prefix + ":run_id_mismatch")
        case_cutoff = _timestamp(record.get("simulation_cutoff"))
        evidence_cutoff = _timestamp((record.get("report_freeze") or {}).get("evidence_cutoff"))
        pit_cutoff = _timestamp(pit_attestation.get("cutoff_at"))
        if case_cutoff and pit_cutoff and pit_cutoff != case_cutoff:
            invalid.append(pit_prefix + ":cutoff_mismatch")
        if evidence_cutoff and pit_cutoff and pit_cutoff != evidence_cutoff:
            invalid.append(pit_prefix + ":evidence_cutoff_mismatch")
        if pit_attestation.get("forbidden_success_count") != 0:
            invalid.append(pit_prefix + ":forbidden_read_succeeded")
        if pit_package_root:
            try:
                attested_root = Path(str(pit_attestation.get("package_root") or "")).resolve()
                if attested_root != pit_package_root.resolve():
                    invalid.append(pit_prefix + ":package_root_mismatch")
            except OSError:
                invalid.append(pit_prefix + ":package_root_invalid")
        if pit_manifest_path:
            try:
                attested_manifest = Path(str(pit_attestation.get("manifest_path") or "")).resolve()
                if attested_manifest != pit_manifest_path.resolve():
                    invalid.append(pit_prefix + ":manifest_path_mismatch")
            except OSError:
                invalid.append(pit_prefix + ":manifest_path_invalid")
        audit = pit_attestation.get("read_audit")
        if not isinstance(audit, list):
            incomplete.append(pit_prefix + ":read_audit_missing")
        else:
            allowed_ids = set(str(item) for item in (pit_attestation.get("allowed_source_ids") or []))
            allowlist = {
                str(item.get("source_id")): item
                for item in (pit_attestation.get("source_allowlist") or [])
                if isinstance(item, dict) and item.get("source_id")
            }
            if allowed_ids != set(allowlist):
                invalid.append(pit_prefix + ":source_allowlist_mismatch")
            if len(audit) != pit_attestation.get("read_count"):
                invalid.append(pit_prefix + ":read_count_mismatch")
            seen_ordinals: set[int] = set()
            allowed_read_sources: set[str] = set()
            for index, event in enumerate(audit):
                event_prefix = f"{pit_prefix}.read_audit[{index}]"
                if not isinstance(event, dict):
                    invalid.append(event_prefix + ":not_object")
                    continue
                if event.get("decision") not in {"ALLOW", "DENY"}:
                    invalid.append(event_prefix + ":decision_invalid")
                if event.get("allowed") is not (event.get("decision") == "ALLOW"):
                    invalid.append(event_prefix + ":decision_allowed_mismatch")
                ordinal = event.get("read_ordinal")
                if not isinstance(ordinal, int) or ordinal <= 0 or ordinal in seen_ordinals:
                    invalid.append(event_prefix + ":read_ordinal_invalid_or_duplicate")
                else:
                    seen_ordinals.add(ordinal)
                if event.get("phase") != "FREEZE":
                    invalid.append(event_prefix + ":phase_invalid")
                if event.get("run_id") != pit_attestation.get("run_id"):
                    invalid.append(event_prefix + ":run_id_mismatch")
                if event.get("cutoff_at") and pit_cutoff and _timestamp(event.get("cutoff_at")) != pit_cutoff:
                    invalid.append(event_prefix + ":cutoff_mismatch")
                if event.get("allowed") is True and event.get("kind") == "SOURCE":
                    source_id = str(event.get("source_id") or "")
                    registration = allowlist.get(source_id)
                    if registration is None:
                        invalid.append(event_prefix + ":source_not_allowlisted")
                    elif event.get("path") != (
                        registration.get("reader_text_path")
                        if registration.get("content_representation") == "PDF_PAGE_MARKDOWN"
                        else registration.get("package_path")
                    ):
                        invalid.append(event_prefix + ":source_path_mismatch")
                    elif event.get("representation") != registration.get("content_representation"):
                        invalid.append(event_prefix + ":source_representation_mismatch")
                    elif event.get("reader_text_path") != registration.get("reader_text_path"):
                        invalid.append(event_prefix + ":source_reader_text_path_mismatch")
                    elif any(event.get(field) != registration.get(field) for field in ("source_version", "published_at", "data_as_of")):
                        invalid.append(event_prefix + ":source_identity_mismatch")
                    elif event.get("admission_status") != "ADMITTED":
                        invalid.append(event_prefix + ":source_admission_status_invalid")
                    else:
                        allowed_read_sources.add(source_id)
                elif event.get("allowed") is True and event.get("kind") == "FRAMEWORK":
                    if event.get("path") not in set(pit_attestation.get("framework_allowlist") or []):
                        invalid.append(event_prefix + ":framework_not_allowlisted")
                elif event.get("allowed") is True and event.get("kind") not in {"FRAMEWORK"}:
                    invalid.append(event_prefix + ":forbidden_kind_allowed")
            if seen_ordinals != set(range(1, len(audit) + 1)):
                invalid.append(pit_prefix + ":read_ordinals_not_contiguous")
            case_source_ids = {
                str(source.get("source_id") or "")
                for source in (record.get("sources") or [])
                if isinstance(source, dict) and source.get("source_id")
            }
            for source_id in case_source_ids - allowed_read_sources:
                incomplete.append(pit_prefix + ":case_source_not_read:" + source_id)
    if pit_manifest:
        try:
            from scripts.phase10_acquisition import validate_source_manifest
            manifest_result = validate_source_manifest(pit_manifest)
        except (ImportError, TypeError, ValueError) as exc:
            invalid.append(pit_prefix + ":source_manifest_unreadable:" + type(exc).__name__)
            manifest_result = {"state": "INVALID"}
        if manifest_result.get("state") != "REVIEWABLE":
            incomplete.append(pit_prefix + ":source_manifest_not_reviewable")
        if pit_package_root:
            try:
                from scripts.phase10_pit_runner import PITSourcePackage
                package_check = PITSourcePackage(
                    pit_manifest,
                    pit_package_root,
                )
                if package_check.state != "REVIEWABLE":
                    incomplete.append(pit_prefix + ":source_package_not_reviewable")
            except (ImportError, OSError, ValueError) as exc:
                invalid.append(pit_prefix + ":source_package_unreadable:" + type(exc).__name__)
        manifest_ids = set(str(item) for item in (pit_manifest.get("admitted_source_ids") or []))
        attestation_ids = set(str(item) for item in (pit_attestation.get("allowed_source_ids") or []))
        if pit_attestation and manifest_ids != attestation_ids:
            invalid.append(pit_prefix + ":attestation_manifest_source_ids_mismatch")
        if pit_attestation and pit_attestation.get("source_manifest_schema_version") != pit_manifest.get("schema_version"):
            invalid.append(pit_prefix + ":source_manifest_schema_mismatch")
        if pit_manifest.get("company_code") != record.get("company_code"):
            invalid.append(pit_prefix + ":source_manifest_company_code_mismatch")
        manifest_cutoff = _timestamp(pit_manifest.get("cutoff_at"))
        case_cutoff = _timestamp(record.get("simulation_cutoff"))
        if manifest_cutoff and case_cutoff and manifest_cutoff != case_cutoff:
            invalid.append(pit_prefix + ":source_manifest_cutoff_mismatch")
        case_sources = record.get("sources") if isinstance(record.get("sources"), list) else []
        manifest_by_id = {
            str(item.get("source_id")): item
            for item in (pit_manifest.get("sources") or [])
            if isinstance(item, dict) and item.get("source_id")
        }
        attestation_by_id = {
            str(item.get("source_id")): item
            for item in (pit_attestation.get("source_allowlist") or [])
            if isinstance(item, dict) and item.get("source_id")
        }
        for source_id, registered in manifest_by_id.items():
            attested = attestation_by_id.get(source_id)
            if attested is None:
                continue
            for field in (
                "source_version", "published_at", "data_as_of", "package_path",
                "content_representation", "reader_text_path", "admission_status",
            ):
                if field == "admission_status":
                    expected = "ADMITTED"
                else:
                    expected = registered.get(field)
                if attested.get(field) != expected:
                    invalid.append(pit_prefix + f":attestation_source_{field}_mismatch:{source_id}")
        for source in case_sources:
            if not isinstance(source, dict):
                continue
            source_id = str(source.get("source_id") or "")
            registered = manifest_by_id.get(source_id)
            if registered is None:
                invalid.append(pit_prefix + ":case_source_not_admitted:" + source_id)
            else:
                for field in ("source_version", "published_at", "data_as_of", "revision_policy"):
                    if source.get(field) != registered.get(field):
                        invalid.append(pit_prefix + f":case_source_{field}_mismatch:{source_id}")
    samples = acceptance_payload.get("samples") if isinstance(acceptance_payload.get("samples"), list) else []
    matches = [item for item in samples if isinstance(item, dict) and item.get("sample_id") == origin.get("sample_id")]
    if len(matches) != 1:
        invalid.append(prefix + ":acceptance_sample_not_unique")
    else:
        sample = matches[0]
        if sample.get("report_sha256") != (pipeline_report_sha256 or artifact_sha256):
            invalid.append(prefix + ":acceptance_report_sha256_mismatch")
        if report_status == "FROZEN":
            if sample.get("machine_status") not in {"READY_FOR_BLIND_REVIEW", "BENCHMARK_CANDIDATE", "BENCHMARK_APPROVED"}:
                invalid.append(prefix + ":acceptance_machine_status_not_ready")
            if not (sample.get("hard_gates") or {}).get("passed"):
                invalid.append(prefix + ":acceptance_v3_gates_not_passed")
    return invalid, incomplete


def _validate_pit_engineering_report_origin(
    record: dict[str, Any], *, report: dict[str, Any], origin: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Validate the constrained PIT-writer path without claiming production acceptance.

    This mode is intentionally narrow: it proves that the frozen engineering
    draft and its review are bound to an admissible source package and actual
    PIT reads.  It does not substitute for the unified report pipeline, V3,
    model-memory control, or a production calibration candidate.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = "report_freeze.frozen_report.origin"
    root = Path(__file__).resolve().parents[1]

    def repo_path(value: Any, field: str) -> Path | None:
        raw = str(value or "")
        if not raw or Path(raw).is_absolute():
            invalid.append(prefix + ":" + field + "_must_be_repo_relative")
            return None
        resolved = (root / raw).resolve()
        if root not in resolved.parents:
            invalid.append(prefix + ":" + field + "_outside_repository")
            return None
        return resolved

    def load_json(path: Path | None, field: str) -> dict[str, Any]:
        if path is None:
            return {}
        if not path.is_file():
            incomplete.append(prefix + ":" + field + "_missing")
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            invalid.append(prefix + ":" + field + "_invalid_json")
            return {}
        if not isinstance(value, dict):
            invalid.append(prefix + ":" + field + "_must_be_object")
            return {}
        return value

    incomplete.extend(_required(origin, ("pit_runner", "review_artifact_path"), prefix))
    pit = origin.get("pit_runner") if isinstance(origin.get("pit_runner"), dict) else {}
    pit_prefix = prefix + ".pit_runner"
    incomplete.extend(_required(
        pit,
        ("attestation_path", "source_package_manifest_path", "package_root", "status"),
        pit_prefix,
    ))
    attestation_path = repo_path(pit.get("attestation_path"), "pit_runner_attestation_path")
    manifest_path = repo_path(pit.get("source_package_manifest_path"), "pit_runner_source_manifest_path")
    package_root = repo_path(pit.get("package_root"), "pit_runner_package_root")
    review_path = repo_path(origin.get("review_artifact_path"), "review_artifact_path")
    attestation = load_json(attestation_path, "pit_runner_attestation")
    manifest = load_json(manifest_path, "pit_runner_source_manifest")

    if pit.get("status") != "PASS":
        incomplete.append(pit_prefix + ":status_not_pass")
    if attestation:
        incomplete.extend(_required(
            attestation,
            ("case_id", "experiment_id", "run_id", "manifest_path", "package_root", "framework_root", "framework_root_class", "cutoff_at", "allowed_source_ids", "source_allowlist", "read_audit", "read_count", "forbidden_success_count", "writer", "execution_mode"),
            pit_prefix + ".attestation",
        ))
        if attestation.get("schema_version") != "phase10-pit-runner-attestation.v1":
            invalid.append(pit_prefix + ":attestation_schema_invalid")
        if attestation.get("runner") != "phase10_pit_runner":
            invalid.append(pit_prefix + ":runner_invalid")
        if attestation.get("state") != "REVIEWABLE":
            incomplete.append(pit_prefix + ":attestation_not_reviewable")
        if attestation.get("assurance_level") != "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS":
            invalid.append(pit_prefix + ":assurance_level_invalid")
        if not str(attestation.get("execution_mode") or "").startswith("PIT_WRITER"):
            invalid.append(pit_prefix + ":execution_mode_must_be_pit_writer")
        if attestation.get("company_code") != record.get("company_code"):
            invalid.append(pit_prefix + ":company_code_mismatch")
        if attestation.get("case_id") != record.get("case_id"):
            invalid.append(pit_prefix + ":case_id_mismatch")
        legacy_experiment_id = str(origin.get("legacy_attestation_experiment_id") or "")
        if attestation.get("experiment_id") != record.get("experiment_id"):
            if (
                legacy_experiment_id
                and attestation.get("experiment_id") == legacy_experiment_id
                and (record.get("report_freeze") or {}).get("report_status") == "FROZEN_WITH_QUALITY_FAILURE"
            ):
                incomplete.append(pit_prefix + ":legacy_experiment_identity_requires_rerun")
            else:
                invalid.append(pit_prefix + ":experiment_id_mismatch")
        case_cutoff = _timestamp(record.get("simulation_cutoff"))
        if case_cutoff and _timestamp(attestation.get("cutoff_at")) != case_cutoff:
            invalid.append(pit_prefix + ":cutoff_mismatch")
        if attestation.get("forbidden_success_count") != 0:
            invalid.append(pit_prefix + ":forbidden_read_succeeded")
        if package_root:
            try:
                if Path(str(attestation.get("package_root") or "")).resolve() != package_root.resolve():
                    invalid.append(pit_prefix + ":package_root_mismatch")
            except OSError:
                invalid.append(pit_prefix + ":package_root_invalid")
        if manifest_path:
            try:
                if Path(str(attestation.get("manifest_path") or "")).resolve() != manifest_path.resolve():
                    invalid.append(pit_prefix + ":manifest_path_mismatch")
            except OSError:
                invalid.append(pit_prefix + ":manifest_path_invalid")
        writer = attestation.get("writer") if isinstance(attestation.get("writer"), dict) else {}
        if writer.get("status") != "PASS":
            incomplete.append(pit_prefix + ":writer_not_pass")
        report_path = repo_path(report.get("artifact_path"), "report_artifact_path")
        try:
            if report_path and Path(str(writer.get("report_path") or "")).resolve() != report_path.resolve():
                invalid.append(pit_prefix + ":writer_report_path_mismatch")
        except OSError:
            invalid.append(pit_prefix + ":writer_report_path_invalid")
        if writer.get("case_id") != record.get("case_id"):
            invalid.append(pit_prefix + ":writer_case_id_mismatch")
        if writer.get("experiment_id") != record.get("experiment_id"):
            if (
                legacy_experiment_id
                and writer.get("experiment_id") == legacy_experiment_id
                and (record.get("report_freeze") or {}).get("report_status") == "FROZEN_WITH_QUALITY_FAILURE"
            ):
                incomplete.append(pit_prefix + ":writer_legacy_experiment_identity_requires_rerun")
            else:
                invalid.append(pit_prefix + ":writer_experiment_id_mismatch")
        case_source_ids = {
            str(source.get("source_id") or "")
            for source in (record.get("sources") or [])
            if isinstance(source, dict) and source.get("source_id")
        }
        if set(str(item) for item in (writer.get("source_ids") or [])) != case_source_ids:
            invalid.append(pit_prefix + ":writer_source_ids_do_not_match_case")
        audit = attestation.get("read_audit")
        allowed_sources: set[str] = set()
        if not isinstance(audit, list):
            incomplete.append(pit_prefix + ":read_audit_missing")
        else:
            if len(audit) != attestation.get("read_count"):
                invalid.append(pit_prefix + ":read_count_mismatch")
            for index, event in enumerate(audit):
                event_prefix = f"{pit_prefix}.read_audit[{index}]"
                if not isinstance(event, dict):
                    invalid.append(event_prefix + ":not_object")
                    continue
                if event.get("allowed") is True:
                    if event.get("kind") not in {"SOURCE", "FRAMEWORK"}:
                        invalid.append(event_prefix + ":forbidden_kind_allowed")
                    elif event.get("kind") == "SOURCE":
                        allowed_sources.add(str(event.get("source_id") or ""))
            if not case_source_ids.issubset(allowed_sources):
                incomplete.extend(
                    pit_prefix + ":case_source_not_read:" + source_id
                    for source_id in sorted(case_source_ids - allowed_sources)
                )
    if manifest:
        try:
            from scripts.phase10_acquisition import validate_source_manifest
            from scripts.phase10_pit_runner import PITSourcePackage
            manifest_result = validate_source_manifest(manifest)
            package_result = PITSourcePackage(manifest, package_root) if package_root else None
        except (ImportError, OSError, TypeError, ValueError) as exc:
            invalid.append(pit_prefix + ":source_package_unreadable:" + type(exc).__name__)
            manifest_result = {"state": "INVALID"}
            package_result = None
        if manifest_result.get("state") != "REVIEWABLE":
            incomplete.append(pit_prefix + ":source_manifest_not_reviewable")
        if package_result is None or package_result.state != "REVIEWABLE":
            incomplete.append(pit_prefix + ":source_package_not_reviewable")
        if manifest.get("company_code") != record.get("company_code"):
            invalid.append(pit_prefix + ":source_manifest_company_code_mismatch")
        if _timestamp(manifest.get("cutoff_at")) != _timestamp(record.get("simulation_cutoff")):
            invalid.append(pit_prefix + ":source_manifest_cutoff_mismatch")
        sources_by_id = {
            str(item.get("source_id") or ""): item
            for item in (manifest.get("sources") or []) if isinstance(item, dict)
        }
        for source in record.get("sources") or []:
            if not isinstance(source, dict):
                continue
            source_id = str(source.get("source_id") or "")
            registered = sources_by_id.get(source_id)
            if registered is None:
                invalid.append(pit_prefix + ":case_source_not_admitted:" + source_id)
                continue
            for field in ("source_version", "published_at", "data_as_of", "revision_policy"):
                if source.get(field) != registered.get(field):
                    invalid.append(pit_prefix + f":case_source_{field}_mismatch:" + source_id)
    review_content, _review_digest, review_invalid, review_incomplete = _read_repo_artifact(
        origin.get("review_artifact_path"), prefix=prefix + ".review_artifact",
    )
    invalid.extend(review_invalid)
    incomplete.extend(review_incomplete)
    if review_path and review_content:
        if str(record.get("case_id") or "") not in review_content:
            incomplete.append(prefix + ":review_artifact_case_id_missing")
        if str(report.get("artifact_path") or "") not in review_content:
            incomplete.append(prefix + ":review_artifact_report_path_missing")
        freeze = record.get("report_freeze") if isinstance(record.get("report_freeze"), dict) else {}
        expected_disposition = (
            "PASS_AFTER_REPAIR_FOR_DRAFT_ONLY"
            if freeze.get("report_status") == "FROZEN"
            else "FROZEN_WITH_QUALITY_FAILURE"
        )
        if expected_disposition not in review_content:
            incomplete.append(prefix + ":review_artifact_disposition_missing")
    return invalid, incomplete


def _validate_report_freeze(
    record: dict[str, Any], *, source_ids: set[str], frozen_claims: dict[str, dict[str, Any]],
    allow_test_fixtures: bool = True,
) -> tuple[list[str], list[str]]:
    """Require a readable frozen report and an independent, claim-level review."""
    invalid: list[str] = []
    incomplete: list[str] = []
    freeze = record.get("report_freeze") if isinstance(record.get("report_freeze"), dict) else {}
    prefix = "report_freeze"
    report_status = freeze.get("report_status")
    if report_status not in {"FROZEN", "FROZEN_WITH_QUALITY_FAILURE"}:
        invalid.append(prefix + ":report_status_invalid")
    if record.get("status") != report_status:
        invalid.append("case_status_does_not_match_report_freeze")

    mode = freeze.get("mode")
    if mode not in REPORT_FREEZE_MODES:
        invalid.append(prefix + ":mode_invalid")
    freeze_id = str(freeze.get("freeze_id") or "")
    if not freeze_id.startswith("HBTFRZ:"):
        invalid.append(prefix + ":freeze_id_invalid")

    report = freeze.get("frozen_report") if isinstance(freeze.get("frozen_report"), dict) else {}
    report_prefix = prefix + ".frozen_report"
    incomplete.extend(_required(
        report,
        ("report_id", "variant_id", "origin", "artifact_path", "artifact_sha256", "format", "writer_id", "writer_provenance", "writer_status", "claim_ids", "section_markers"),
        report_prefix,
    ))
    report_id = report.get("report_id")
    if not isinstance(report_id, str) or not report_id.startswith("HBTREP:"):
        invalid.append(report_prefix + ":report_id_invalid")
    if report.get("format") != "MARKDOWN":
        invalid.append(report_prefix + ":format_must_be_markdown")
    variant_id = str(report.get("variant_id") or "")
    if not re.fullmatch(r"[0-9a-f]{16}", variant_id):
        invalid.append(report_prefix + ":variant_id_invalid")
    if not isinstance(report.get("writer_id"), str) or not report.get("writer_id").strip():
        invalid.append(report_prefix + ":writer_id_invalid")
    writer_context, writer_identity, provenance_invalid, provenance_incomplete = _validate_actor_provenance(
        report.get("writer_provenance"), prefix=report_prefix + ".writer_provenance",
    )
    invalid.extend(provenance_invalid)
    incomplete.extend(provenance_incomplete)
    expected_claim_ids = set(frozen_claims)
    report_claim_ids = report.get("claim_ids") if isinstance(report.get("claim_ids"), list) else []
    normalized_report_claim_ids = [str(item or "") for item in report_claim_ids]
    if set(normalized_report_claim_ids) != expected_claim_ids or len(normalized_report_claim_ids) != len(set(normalized_report_claim_ids)):
        invalid.append(report_prefix + ":claim_ids_do_not_match_frozen_ledger")
    content, artifact_sha256, artifact_invalid, artifact_incomplete = _read_repo_artifact(
        report.get("artifact_path"), prefix=report_prefix,
    )
    invalid.extend(artifact_invalid)
    incomplete.extend(artifact_incomplete)
    if not isinstance(report.get("artifact_sha256"), str) or report.get("artifact_sha256") != artifact_sha256:
        invalid.append(report_prefix + ":artifact_sha256_mismatch")
    if mode in {"TEST_FIXTURE", "PIT_ENGINEERING"} and variant_id and artifact_sha256 and variant_id != artifact_sha256[:16]:
        invalid.append(report_prefix + ":variant_id_does_not_match_artifact")
    if variant_id and freeze_id != "HBTFRZ:" + variant_id:
        invalid.append(prefix + ":freeze_id_does_not_match_report_variant")
    origin = report.get("origin") if isinstance(report.get("origin"), dict) else {}
    origin_kind = origin.get("kind")
    if origin_kind not in REPORT_ORIGIN_KINDS:
        invalid.append(report_prefix + ":origin_kind_invalid")
    if mode == "TEST_FIXTURE" or origin_kind == "TEST_FIXTURE":
        if mode != "TEST_FIXTURE" or origin_kind != "TEST_FIXTURE":
            invalid.append(report_prefix + ":fixture_mode_and_origin_must_match")
        if record.get("case_id") != "HBTCASE:TEST":
            invalid.append(report_prefix + ":test_fixture_forbidden_outside_test_case")
        if not allow_test_fixtures:
            invalid.append(report_prefix + ":test_fixture_requires_explicit_allowance")
        if not str(report.get("artifact_path") or "").startswith("tests/fixtures/"):
            invalid.append(report_prefix + ":test_fixture_must_use_fixture_artifact")
    elif mode == "PRODUCTION_PIPELINE":
        if origin_kind != "TURTLE_PIPELINE":
            invalid.append(report_prefix + ":production_case_requires_turtle_pipeline_origin")
        origin_invalid, origin_incomplete = _validate_production_report_origin(
            record, report=report, artifact_sha256=artifact_sha256, origin=origin,
        )
        invalid.extend(origin_invalid)
        incomplete.extend(origin_incomplete)
    elif mode == "PIT_ENGINEERING":
        if origin_kind != "PIT_ENGINEERING":
            invalid.append(report_prefix + ":pit_engineering_case_requires_pit_engineering_origin")
        origin_invalid, origin_incomplete = _validate_pit_engineering_report_origin(
            record, report=report, origin=origin,
        )
        invalid.extend(origin_invalid)
        incomplete.extend(origin_incomplete)
    section_markers = report.get("section_markers") if isinstance(report.get("section_markers"), list) else []
    normalized_markers = {str(item or "") for item in section_markers}
    required_sections = PIT_ENGINEERING_REPORT_SECTIONS if mode == "PIT_ENGINEERING" else REQUIRED_FROZEN_REPORT_SECTIONS
    if not required_sections.issubset(normalized_markers) or len(normalized_markers) != len(section_markers):
        invalid.append(report_prefix + ":section_markers_incomplete")
    if content:
        if mode != "PIT_ENGINEERING" and isinstance(report_id, str) and report_id not in content:
            invalid.append(report_prefix + ":artifact_report_id_missing")
        for marker in required_sections:
            if marker not in content:
                incomplete.append(report_prefix + ":artifact_section_missing:" + marker)
        for claim_id, claim in frozen_claims.items():
            if claim_id not in content:
                invalid.append(report_prefix + ":artifact_claim_id_missing:" + claim_id)
            statement = str(claim.get("statement") or "").strip()
            if mode != "PIT_ENGINEERING" and statement and statement not in content:
                incomplete.append(report_prefix + ":artifact_claim_statement_missing:" + claim_id)

    review = freeze.get("independent_review") if isinstance(freeze.get("independent_review"), dict) else {}
    review_prefix = prefix + ".independent_review"
    incomplete.extend(_required(
        review,
        ("review_id", "reviewed_variant_id", "reviewer_id", "reviewer_provenance", "independence", "reviewed_report_sha256", "status", "claim_reviews"),
        review_prefix,
    ))
    if not isinstance(review.get("review_id"), str) or not review.get("review_id").startswith("HBTREV:"):
        invalid.append(review_prefix + ":review_id_invalid")
    if review.get("reviewed_variant_id") != variant_id:
        invalid.append(review_prefix + ":reviewed_variant_id_mismatch")
    if variant_id and review.get("review_id") != "HBTREV:" + variant_id:
        invalid.append(review_prefix + ":review_id_must_bind_report_variant")
    if not isinstance(review.get("reviewer_id"), str) or not review.get("reviewer_id").strip():
        invalid.append(review_prefix + ":reviewer_id_invalid")
    elif review.get("reviewer_id") == report.get("writer_id"):
        invalid.append(review_prefix + ":reviewer_must_be_independent_from_writer")
    reviewer_context, reviewer_identity, reviewer_invalid, reviewer_incomplete = _validate_actor_provenance(
        review.get("reviewer_provenance"), prefix=review_prefix + ".reviewer_provenance",
    )
    invalid.extend(reviewer_invalid)
    incomplete.extend(reviewer_incomplete)
    if writer_context and reviewer_context and writer_context == reviewer_context:
        invalid.append(review_prefix + ":reviewer_context_must_differ_from_writer")
    # A separate review context can use the same deployed model.  The reviewer
    # identity and isolated context are the relevant independence boundary.
    independence = review.get("independence") if isinstance(review.get("independence"), dict) else {}
    for field in REVIEWER_INDEPENDENCE_FIELDS:
        if independence.get(field) is not True:
            invalid.append(review_prefix + ":independence_" + field + "_required")
    if review.get("reviewed_report_sha256") != artifact_sha256:
        invalid.append(review_prefix + ":reviewed_report_sha256_mismatch")
    if review.get("status") not in {"PASS", "FAIL"}:
        invalid.append(review_prefix + ":status_invalid")
    reviews = review.get("claim_reviews") if isinstance(review.get("claim_reviews"), list) else []
    reviewed_claim_ids: set[str] = set()
    has_unsupported_prediction = False
    has_partial_prediction = False
    for index, claim_review in enumerate(reviews):
        claim_prefix = f"{review_prefix}.claim_reviews[{index}]"
        if not isinstance(claim_review, dict):
            invalid.append(claim_prefix + ":not_object")
            continue
        incomplete.extend(_required(claim_review, ("claim_id", "disposition", "source_ids", "notes"), claim_prefix))
        claim_id = str(claim_review.get("claim_id") or "")
        claim = frozen_claims.get(claim_id)
        if claim is None:
            invalid.append(claim_prefix + ":claim_id_not_frozen:" + claim_id)
            continue
        if claim_id in reviewed_claim_ids:
            invalid.append("duplicate_report_review_claim_id:" + claim_id)
        reviewed_claim_ids.add(claim_id)
        disposition = claim_review.get("disposition")
        if disposition not in REPORT_REVIEW_DISPOSITIONS:
            invalid.append(claim_prefix + ":disposition_invalid")
        if claim.get("frozen_disposition") == "UNKNOWN" and disposition != "UNKNOWN_PRESERVED":
            invalid.append(claim_prefix + ":unknown_claim_must_be_preserved")
        if claim.get("frozen_disposition") == "PREDICTION" and disposition == "UNKNOWN_PRESERVED":
            invalid.append(claim_prefix + ":prediction_claim_cannot_be_marked_unknown_preserved")
        if claim.get("frozen_disposition") == "PREDICTION" and disposition == "UNSUPPORTED":
            has_unsupported_prediction = True
        if claim.get("frozen_disposition") == "PREDICTION" and disposition == "PARTIAL":
            has_partial_prediction = True
        review_sources = claim_review.get("source_ids") if isinstance(claim_review.get("source_ids"), list) else []
        if set(str(item or "") for item in review_sources) != set(str(item) for item in claim.get("source_ids") or []):
            invalid.append(claim_prefix + ":source_ids_do_not_match_frozen_claim")
        ref_invalid, ref_incomplete = _validate_source_references(review_sources, source_ids, claim_prefix)
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
    if reviewed_claim_ids != expected_claim_ids:
        incomplete.append(review_prefix + ":claim_reviews_do_not_cover_frozen_ledger")

    quality_failure = freeze.get("quality_failure")
    if report_status == "FROZEN":
        if report.get("writer_status") != "COMPLETE":
            invalid.append(report_prefix + ":frozen_report_must_be_complete")
        if review.get("status") != "PASS":
            invalid.append(review_prefix + ":frozen_report_requires_pass")
        if has_unsupported_prediction:
            invalid.append(review_prefix + ":unsupported_prediction_cannot_be_frozen")
        if has_partial_prediction:
            invalid.append(review_prefix + ":partial_prediction_cannot_be_frozen")
        if quality_failure is not None:
            invalid.append(prefix + ":quality_failure_must_be_null_for_frozen_report")
    elif report_status == "FROZEN_WITH_QUALITY_FAILURE":
        if report.get("writer_status") != "QUALITY_FAILURE":
            invalid.append(report_prefix + ":quality_failure_report_status_required")
        if review.get("status") != "FAIL":
            invalid.append(review_prefix + ":quality_failure_requires_failed_review")
        if not isinstance(quality_failure, dict):
            incomplete.append(prefix + ":quality_failure_details_missing")
        else:
            failure_prefix = prefix + ".quality_failure"
            incomplete.extend(_required(
                quality_failure,
                ("classifications", "economic_impact", "missing_facts", "prohibited_assumptions", "remediation", "acceptance_criteria"),
                failure_prefix,
            ))
            classifications = quality_failure.get("classifications") if isinstance(quality_failure.get("classifications"), list) else []
            if not classifications or any(item not in QUALITY_FAILURE_CLASSIFICATIONS for item in classifications):
                invalid.append(failure_prefix + ":classifications_invalid")
    return invalid, incomplete


def _validate_report_coverage(
    coverage: dict[str, Any], *, case: dict[str, Any] | None, frozen_claims: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Bind frozen report-quality aggregates to the independent claim review."""
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = "report_coverage"
    incomplete.extend(_required(
        coverage,
        ("status", "review_id", "claim_reviews", "supported_claim_count", "unsupported_claim_count", "unknowns_preserved", "notes"),
        prefix,
    ))
    freeze = case.get("report_freeze") if isinstance(case, dict) and isinstance(case.get("report_freeze"), dict) else {}
    review = freeze.get("independent_review") if isinstance(freeze.get("independent_review"), dict) else {}
    if coverage.get("review_id") != review.get("review_id"):
        invalid.append(prefix + ":review_id_does_not_match_frozen_review")
    expected_reviews = review.get("claim_reviews") if isinstance(review.get("claim_reviews"), list) else []
    actual_reviews = coverage.get("claim_reviews") if isinstance(coverage.get("claim_reviews"), list) else []

    def normalize(rows: list[Any], row_prefix: str) -> dict[str, tuple[str, frozenset[str]]]:
        normalized: dict[str, tuple[str, frozenset[str]]] = {}
        for index, row in enumerate(rows):
            item_prefix = f"{row_prefix}[{index}]"
            if not isinstance(row, dict):
                invalid.append(item_prefix + ":not_object")
                continue
            incomplete.extend(_required(row, ("claim_id", "disposition", "source_ids"), item_prefix))
            claim_id = str(row.get("claim_id") or "")
            if claim_id not in frozen_claims:
                invalid.append(item_prefix + ":claim_id_not_frozen:" + claim_id)
                continue
            if claim_id in normalized:
                invalid.append("duplicate_report_coverage_claim_id:" + claim_id)
                continue
            disposition = row.get("disposition")
            if disposition not in REPORT_REVIEW_DISPOSITIONS:
                invalid.append(item_prefix + ":disposition_invalid")
            source_values = row.get("source_ids") if isinstance(row.get("source_ids"), list) else []
            source_set = frozenset(str(item or "") for item in source_values)
            if source_set != frozenset(str(item) for item in frozen_claims[claim_id].get("source_ids") or []):
                invalid.append(item_prefix + ":source_ids_do_not_match_frozen_claim")
            normalized[claim_id] = (str(disposition), source_set)
        return normalized

    expected = normalize(expected_reviews, prefix + ".frozen_review")
    actual = normalize(actual_reviews, prefix + ".claim_reviews")
    if actual != expected:
        invalid.append(prefix + ":claim_reviews_do_not_match_frozen_review")
    if set(actual) != set(frozen_claims):
        incomplete.append(prefix + ":claim_reviews_do_not_cover_frozen_ledger")
    supported_count = sum(1 for disposition, _ in actual.values() if disposition == "SUPPORTED")
    unsupported_count = sum(1 for disposition, _ in actual.values() if disposition == "UNSUPPORTED")
    unknowns_preserved = all(
        actual.get(claim_id, (None, frozenset()))[0] == "UNKNOWN_PRESERVED"
        for claim_id, claim in frozen_claims.items()
        if claim.get("frozen_disposition") == "UNKNOWN"
    )
    if coverage.get("supported_claim_count") != supported_count:
        invalid.append(prefix + ":supported_claim_count_does_not_match_claim_reviews")
    if coverage.get("unsupported_claim_count") != unsupported_count:
        invalid.append(prefix + ":unsupported_claim_count_does_not_match_claim_reviews")
    if coverage.get("unknowns_preserved") is not unknowns_preserved:
        invalid.append(prefix + ":unknowns_preserved_does_not_match_claim_reviews")
    expected_status = "INVALID" if unsupported_count else "PARTIAL" if any(
        disposition == "PARTIAL" for disposition, _ in actual.values()
    ) else "PASS"
    if coverage.get("status") != expected_status:
        invalid.append(prefix + ":status_does_not_match_claim_reviews")
    if freeze.get("report_status") == "FROZEN" and expected_status != "PASS":
        invalid.append(prefix + ":frozen_case_requires_pass_claim_reviews")
    return invalid, incomplete


def validate_case(
    record: dict[str, Any], *, experiment: dict[str, Any] | None = None, allow_test_fixtures: bool = True,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if record.get("schema_version") not in {CASE_SCHEMA_VERSION, CASE_SCHEMA_VERSION_V2}:
        invalid.append("schema_version_invalid")
    if not str(record.get("experiment_id") or "").startswith("HBT:"):
        invalid.append("case_experiment_id_invalid")
    invalid.extend(_nested_forbidden(record.get("inputs", []), path="inputs"))
    invalid.extend(_nested_forbidden(record.get("calibration_ledger", {}), path="calibration_ledger"))
    simulation_cutoff = _timestamp(record.get("simulation_cutoff"))
    if simulation_cutoff is None:
        invalid.append("simulation_cutoff_invalid")
        simulation_cutoff = datetime.min.replace(tzinfo=timezone.utc)
    report_freeze = record.get("report_freeze") if isinstance(record.get("report_freeze"), dict) else {}
    if report_freeze.get("settlement_locked") is not True:
        invalid.append("settlement_must_be_locked_at_report_freeze")
    freeze_date = _timestamp(report_freeze.get("frozen_at"))
    evidence_cutoff = _timestamp(report_freeze.get("evidence_cutoff"))
    if freeze_date is None or evidence_cutoff is None:
        incomplete.append("report_freeze_dates_missing")
    elif evidence_cutoff > simulation_cutoff:
        invalid.append("evidence_cutoff_after_simulation_cutoff")
    elif freeze_date < evidence_cutoff:
        invalid.append("report_freeze_before_evidence_cutoff")
    credibility_invalid, credibility_incomplete = _validate_credibility(record)
    invalid.extend(credibility_invalid)
    incomplete.extend(credibility_incomplete)
    experiment_credibility_invalid, experiment_credibility_incomplete = _validate_case_experiment_credibility(
        record, experiment=experiment,
    )
    invalid.extend(experiment_credibility_invalid)
    incomplete.extend(experiment_credibility_incomplete)
    sources = record.get("sources") if isinstance(record.get("sources"), list) else []
    if not sources:
        incomplete.append("sources_missing")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            invalid.append(f"sources[{index}]:not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if source_id in source_ids:
            invalid.append("duplicate_source_id:" + source_id)
        source_ids.add(source_id)
        current_invalid, current_incomplete = _validate_source(source, simulation_cutoff, index)
        invalid.extend(current_invalid)
        incomplete.extend(current_incomplete)
    for index, item in enumerate(record.get("inputs") or []):
        if not isinstance(item, dict):
            invalid.append(f"inputs[{index}]:not_object")
            continue
        missing = _required(item, ("name", "input_role", "source_ids"), f"inputs[{index}]")
        incomplete.extend(missing)
        if item.get("input_role") == "HISTORICAL_FACT" and not item.get("source_ids"):
            incomplete.append(f"inputs[{index}]:historical_fact_source_missing")
        ref_invalid, ref_incomplete = _validate_source_references(
            item.get("source_ids"), source_ids, f"inputs[{index}]",
        )
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
    ledger_invalid, ledger_incomplete = _validate_calibration_ledger(record, source_ids)
    invalid.extend(ledger_invalid)
    incomplete.extend(ledger_incomplete)
    report_invalid, report_incomplete = _validate_report_freeze(
        record, source_ids=source_ids, frozen_claims=_frozen_claims(record), allow_test_fixtures=allow_test_fixtures,
    )
    invalid.extend(report_invalid)
    incomplete.extend(report_incomplete)
    if report_freeze.get("report_status") == "FROZEN_WITH_QUALITY_FAILURE":
        incomplete.append("case_frozen_with_quality_failure")
    decision_invalid, decision_incomplete = _validate_investment_decision(record)
    invalid.extend(decision_invalid)
    incomplete.extend(decision_incomplete)
    taxes = record.get("taxes_fees_fx") if isinstance(record.get("taxes_fees_fx"), dict) else {}
    incomplete.extend(_required(taxes, ("tax_rate", "transaction_fee_rate", "dividend_tax_rate", "base_currency", "fx_rule"), "taxes_fees_fx"))
    invalid.extend(_route_findings(record))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": list(dict.fromkeys(invalid)), "incomplete_findings": list(dict.fromkeys(incomplete))}


def _validate_actual_sources(
    record: dict[str, Any], *, cutoff: datetime | None, settlement_date: datetime | None, require_content_access: bool,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Check that settlement facts have their own later official evidence."""
    sources_by_id: dict[str, dict[str, Any]] = {}
    invalid: list[str] = []
    incomplete: list[str] = []
    sources = record.get("actual_sources") if isinstance(record.get("actual_sources"), list) else []
    if not sources:
        incomplete.append("actual_sources_missing")
        return sources_by_id, invalid, incomplete
    for index, source in enumerate(sources):
        prefix = f"actual_sources[{index}]"
        if not isinstance(source, dict):
            invalid.append(prefix + ":not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id:
            incomplete.append(prefix + ":source_id_missing")
        elif source_id in sources_by_id:
            invalid.append("duplicate_actual_source_id:" + source_id)
        if source_id:
            sources_by_id[source_id] = source
        incomplete.extend(_required(source, ("source_type", "official", "published_at", "source_version"), prefix))
        if require_content_access:
            if source.get("content_access") in (None, ""):
                incomplete.append(prefix + ":missing:content_access")
            elif source.get("content_access") not in SOURCE_CONTENT_ACCESS:
                invalid.append(prefix + ":content_access_invalid")
        if source.get("official") is not True:
            invalid.append(prefix + ":official_source_required")
        if source.get("source_type") not in OFFICIAL_SETTLEMENT_SOURCE_TYPES:
            invalid.append(prefix + ":official_source_type_invalid")
        published = _timestamp(source.get("published_at"), date_only_at_end=True)
        if published is None:
            incomplete.append(prefix + ":published_at_invalid")
        else:
            if cutoff and _is_date_only(source.get("published_at")) and published.astimezone(PIT_TIMEZONE).date() == cutoff.astimezone(PIT_TIMEZONE).date():
                incomplete.append(prefix + ":published_at_time_required_on_cutoff_date")
            if cutoff and published <= cutoff:
                invalid.append(prefix + ":published_at_must_follow_report_cutoff")
            if settlement_date and published > settlement_date:
                invalid.append(prefix + ":published_at_after_settlement")
        data_as_of = source.get("data_as_of")
        if data_as_of is not None:
            observed_date = _date(data_as_of)
            if observed_date is None:
                incomplete.append(prefix + ":data_as_of_invalid")
            elif settlement_date and observed_date > settlement_date.date():
                invalid.append(prefix + ":data_as_of_after_settlement")
    return sources_by_id, invalid, incomplete


def _validate_operating_observation(
    observation: dict[str, Any], *, prefix: str, frozen_claims: dict[str, dict[str, Any]],
    actual_sources: dict[str, dict[str, Any]], case_v2: bool, settlement_date: datetime | None,
) -> tuple[list[str], list[str]]:
    """Bind an observed operating result to the frozen metric, basis, period and source contract."""
    invalid: list[str] = []
    incomplete: list[str] = []
    claim_id = str(observation.get("claim_id") or "")
    claim = frozen_claims.get(claim_id)
    if claim is None:
        invalid.append(prefix + ":claim_id_not_frozen:" + claim_id)
        return invalid, incomplete
    outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
    if observation.get("comparability_status") not in OPERATING_COMPARABILITY_STATUSES:
        invalid.append(prefix + ":comparability_status_invalid")
    for field in ("metric", "unit", "measurement_basis"):
        if observation.get(field) != outcome.get(field):
            invalid.append(prefix + ":" + field + "_does_not_match_frozen_contract")
    period = _measurement_period(outcome, v2=case_v2)
    if case_v2:
        if any(field in observation for field in ("period_start", "period_end")):
            invalid.append(prefix + ":legacy_period_fields_not_allowed")
        if observation.get("measurement_period") != period:
            invalid.append(prefix + ":measurement_period_does_not_match_frozen_contract")
        if period.get("kind") == "EVENT_WINDOW":
            event_period = observation.get("event_period") if isinstance(observation.get("event_period"), dict) else {}
            event_prefix = prefix + ".event_period"
            incomplete.extend(_required(event_period, ("start", "end"), event_prefix))
            event_start = _date(event_period.get("start"))
            event_end = _date(event_period.get("end"))
            frozen_start = _date(period.get("start"))
            frozen_end = _date(period.get("end"))
            if event_period.get("start") not in (None, "") and event_start is None:
                invalid.append(event_prefix + ":start_invalid")
            if event_period.get("end") not in (None, "") and event_end is None:
                invalid.append(event_prefix + ":end_invalid")
            if event_start and event_end and event_start > event_end:
                invalid.append(event_prefix + ":start_after_end")
            if frozen_start and event_start and event_start < frozen_start:
                invalid.append(event_prefix + ":starts_before_frozen_measurement_period")
            if frozen_end and event_end and event_end > frozen_end:
                invalid.append(event_prefix + ":ends_after_frozen_measurement_period")
        elif observation.get("event_period") is not None:
            invalid.append(prefix + ":event_period_only_allowed_for_event_window")
        window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
        opens_after = _timestamp(window.get("opens_after"))
        closes_at = _timestamp(window.get("closes_at"))
        if settlement_date and closes_at and closes_at > settlement_date:
            invalid.append(prefix + ":observation_window_closes_after_settlement")
    else:
        for field in ("period_start", "period_end"):
            if observation.get(field) != outcome.get(field):
                invalid.append(prefix + ":" + field + "_does_not_match_frozen_contract")
    allowed_source_types = outcome.get("allowed_source_types")
    if not isinstance(allowed_source_types, list) or not allowed_source_types:
        return invalid, incomplete
    for source_id in observation.get("source_ids") or []:
        source = actual_sources.get(str(source_id or ""))
        if source is None:
            continue
        source_type = source.get("source_type")
        if source_type not in allowed_source_types:
            invalid.append(prefix + ":source_type_not_allowed_for_frozen_contract:" + str(source_id))
        if case_v2:
            if source.get("content_access") != "BODY_READ":
                invalid.append(prefix + ":source_body_not_read:" + str(source_id))
            published_at = _timestamp(source.get("published_at"), date_only_at_end=True)
            if opens_after and published_at and published_at <= opens_after:
                invalid.append(prefix + ":source_published_before_observation_window:" + str(source_id))
            if closes_at and published_at and published_at > closes_at:
                invalid.append(prefix + ":source_published_after_observation_window:" + str(source_id))
        if period.get("kind") == "REPORTING_PERIOD" and source_type in {"ANNUAL_REPORT", "INTERIM_REPORT"}:
            source_period_end = _date(source.get("data_as_of"))
            observation_period_end = _date(period.get("end"))
            if source_period_end is None:
                incomplete.append(prefix + ":report_source_data_as_of_missing:" + str(source_id))
            elif observation_period_end and source_period_end != observation_period_end:
                invalid.append(prefix + ":report_source_period_does_not_match_observation:" + str(source_id))
    if observation.get("comparability_status") == "CONVERTIBLE_WITH_PREREGISTERED_RULE":
        conversion_rule = outcome.get("conversion_rule") if isinstance(outcome.get("conversion_rule"), dict) else None
        if conversion_rule is None:
            invalid.append(prefix + ":conversion_rule_not_preregistered")
        else:
            incomplete.extend(_required(
                observation, ("raw_value", "raw_unit", "conversion_rule_id"), prefix,
            ))
            if observation.get("conversion_rule_id") != conversion_rule.get("rule_id"):
                invalid.append(prefix + ":conversion_rule_id_does_not_match_frozen_contract")
            if observation.get("raw_unit") != conversion_rule.get("raw_unit"):
                invalid.append(prefix + ":raw_unit_does_not_match_frozen_contract")
            raw_value = _number(observation.get("raw_value"))
            converted_value = _number(observation.get("value"))
            multiplier = _number(conversion_rule.get("multiplier"))
            if raw_value is None or converted_value is None or multiplier is None:
                invalid.append(prefix + ":conversion_value_not_numeric")
            elif not _numbers_match(converted_value, raw_value * multiplier):
                invalid.append(prefix + ":converted_value_does_not_match_frozen_rule")
    return invalid, incomplete


def _observation_visible_at(
    observation: dict[str, Any], actual_sources: dict[str, dict[str, Any]],
) -> datetime | None:
    publication_times = [
        _timestamp(actual_sources[source_id].get("published_at"), date_only_at_end=True)
        for source_id in observation.get("source_ids") or []
        if source_id in actual_sources
    ]
    if not publication_times or any(item is None for item in publication_times):
        return None
    return max(item for item in publication_times if item is not None)


def _validate_operating_source_timeline(
    record: dict[str, Any], *, actual_sources: dict[str, dict[str, Any]],
    observations: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Require an explicit, auditable enumeration before selecting an actual."""
    invalid: list[str] = []
    incomplete: list[str] = []
    prefix = "operating_source_timeline"
    timeline = record.get(prefix) if isinstance(record.get(prefix), dict) else {}
    incomplete.extend(_required(timeline, ("enumeration_status", "source_ids"), prefix))
    status = timeline.get("enumeration_status")
    if status not in {"COMPLETE", "INCOMPLETE"}:
        invalid.append(prefix + ":enumeration_status_invalid")
    elif status == "INCOMPLETE":
        incomplete.append(prefix + ":enumeration_incomplete")
    timeline_source_ids = [str(item) for item in timeline.get("source_ids") or []]
    ref_invalid, ref_incomplete = _validate_source_references(
        timeline_source_ids, set(actual_sources), prefix,
    )
    invalid.extend(ref_invalid)
    incomplete.extend(ref_incomplete)
    operating_source_ids = {
        source_id for source_id, source in actual_sources.items()
        if source.get("source_type") in OPERATING_OBSERVATION_SOURCE_TYPES
    }
    if set(timeline_source_ids) != operating_source_ids:
        invalid.append(prefix + ":source_ids_do_not_match_enumerated_operating_sources")
    for observation_id, observation in observations.items():
        for source_id in observation.get("source_ids") or []:
            if source_id not in timeline_source_ids:
                invalid.append(prefix + ":observation_source_not_enumerated:" + observation_id + ":" + str(source_id))
    return invalid, incomplete


def _matching_comparable_observations(
    frozen_claim: dict[str, Any], observations: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    outcome = frozen_claim.get("observable_outcome") if isinstance(frozen_claim.get("observable_outcome"), dict) else {}
    case_v2 = isinstance(outcome.get("measurement_period"), dict)
    return {
        observation_id: observation
        for observation_id, observation in observations.items()
        if observation.get("claim_id") == frozen_claim.get("claim_id")
        and observation.get("metric") == outcome.get("metric")
        and observation.get("unit") == outcome.get("unit")
        and observation.get("measurement_basis") == outcome.get("measurement_basis")
        and (
            observation.get("measurement_period") == outcome.get("measurement_period")
            if case_v2 else (
                observation.get("period_start") == outcome.get("period_start")
                and observation.get("period_end") == outcome.get("period_end")
            )
        )
        and observation.get("comparability_status") in COMPARABLE_OPERATING_STATUSES
    }


def _validate_claim_settlements(
    model_error: dict[str, Any], *, frozen_claims: dict[str, dict[str, Any]],
    observations: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Every frozen prediction and UNKNOWN needs an explicit settlement state."""
    statuses: dict[str, dict[str, Any]] = {}
    invalid: list[str] = []
    incomplete: list[str] = []
    entries = model_error.get("claim_settlements") if isinstance(model_error.get("claim_settlements"), list) else []
    if not entries:
        incomplete.append("model_forecast_error:claim_settlements_missing")
        return statuses, invalid, incomplete
    for index, entry in enumerate(entries):
        prefix = f"model_forecast_error.claim_settlements[{index}]"
        if not isinstance(entry, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(entry, ("claim_id", "frozen_disposition", "status"), prefix))
        if "observation_ids" not in entry or not isinstance(entry.get("observation_ids"), list):
            incomplete.append(prefix + ":missing:observation_ids")
        claim_id = str(entry.get("claim_id") or "")
        frozen = frozen_claims.get(claim_id)
        if frozen is None:
            invalid.append(prefix + ":claim_id_not_frozen:" + claim_id)
            continue
        if claim_id in statuses:
            invalid.append("duplicate_claim_settlement:" + claim_id)
            continue
        statuses[claim_id] = entry
        disposition = frozen.get("frozen_disposition")
        if entry.get("frozen_disposition") != disposition:
            invalid.append(prefix + ":frozen_disposition_does_not_match_case")
        allowed_statuses = (
            PREDICTION_SETTLEMENT_STATUSES
            if disposition == "PREDICTION"
            else UNKNOWN_SETTLEMENT_STATUSES
        )
        status = entry.get("status")
        if status not in allowed_statuses:
            invalid.append(prefix + ":status_invalid_for_frozen_disposition")
        observation_ids = entry.get("observation_ids") if isinstance(entry.get("observation_ids"), list) else []
        registered_observation_ids = {str(item or "") for item in observation_ids}
        matching_observations = _matching_comparable_observations(frozen, observations)
        for observation_id in matching_observations:
            if observation_id not in registered_observation_ids:
                invalid.append(prefix + ":comparable_observation_not_registered:" + observation_id)
        if disposition == "PREDICTION" and status == "CALCULATED" and not observation_ids:
            incomplete.append(prefix + ":calculated_prediction_requires_observation")
        if disposition == "PREDICTION" and matching_observations and status != "CALCULATED":
            invalid.append(prefix + ":comparable_observation_requires_calculated_status")
        if disposition == "UNKNOWN":
            if status == "UNRESOLVED_AS_OF_SETTLEMENT" and observation_ids:
                invalid.append(prefix + ":unresolved_unknown_cannot_reference_observation")
            if status == "UNRESOLVED_AS_OF_SETTLEMENT" and matching_observations:
                invalid.append(prefix + ":comparable_observation_requires_resolution_status")
            elif status in UNKNOWN_SETTLEMENT_STATUSES - {"UNRESOLVED_AS_OF_SETTLEMENT"} and not observation_ids:
                incomplete.append(prefix + ":resolved_unknown_requires_observation")
        for observation_id in observation_ids:
            observation_id = str(observation_id or "")
            observation = observations.get(observation_id)
            if observation is None:
                invalid.append(prefix + ":observation_id_not_found:" + observation_id)
            elif observation.get("claim_id") != claim_id:
                invalid.append(prefix + ":observation_claim_id_mismatch:" + observation_id)
    for claim_id in frozen_claims:
        if claim_id not in statuses:
            incomplete.append("model_forecast_error.claim_settlements:missing_frozen_claim:" + claim_id)
    return statuses, invalid, incomplete


def _validate_metric_version_policy(
    metric: dict[str, Any], observation: dict[str, Any], *, frozen_claim: dict[str, Any],
    observations: dict[str, dict[str, Any]], actual_sources: dict[str, dict[str, Any]], prefix: str,
) -> tuple[list[str], list[str]]:
    """Select the pre-registered first or latest comparable disclosure, never a convenient revision."""
    outcome = frozen_claim.get("observable_outcome") if isinstance(frozen_claim.get("observable_outcome"), dict) else {}
    policy = outcome.get("settlement_version_policy")
    candidates = list(_matching_comparable_observations(frozen_claim, observations).values())
    dated_candidates = [
        (item, _observation_visible_at(item, actual_sources)) for item in candidates
    ]
    dated_candidates = [(item, visible_at) for item, visible_at in dated_candidates if visible_at is not None]
    selected_at = _observation_visible_at(observation, actual_sources)
    if not dated_candidates or selected_at is None:
        return [], [prefix + ":observation_publication_timeline_incomplete"]
    required_at = (
        min(visible_at for _, visible_at in dated_candidates)
        if policy == "INITIAL_DISCLOSURE"
        else max(visible_at for _, visible_at in dated_candidates)
    )
    boundary_candidates = [item for item, visible_at in dated_candidates if visible_at == required_at]
    if len(boundary_candidates) > 1:
        return [], [prefix + ":publication_order_ambiguous"]
    if selected_at != required_at:
        required = "initial" if policy == "INITIAL_DISCLOSURE" else "latest"
        return [prefix + ":does_not_use_" + required + "_disclosure_per_frozen_policy"], []
    return [], []


def _validate_return_outcome(
    outcome: dict[str, Any],
    *,
    case: dict[str, Any] | None,
    actual_source_ids: set[str],
    actual_sources: dict[str, dict[str, Any]],
    cutoff: datetime | None,
    settlement_date: datetime | None,
) -> tuple[list[str], list[str]]:
    """Validate the small, replayable investment-return ledger.

    This deliberately models one position entry and one exit/mark.  It is
    enough to catch action/price swaps and arithmetic tampering without
    pretending to be a portfolio or order-management system.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    return_statuses = {"CALCULATED", "PARTIAL", "NOT_CALCULABLE"}
    status = outcome.get("status")
    action = outcome.get("action")
    if status not in return_statuses:
        invalid.append("investment_return_outcome:status_invalid")
    if action not in INVESTMENT_ACTIONS:
        invalid.append("investment_return_outcome:action_invalid")

    freeze_mode = ((case or {}).get("report_freeze") or {}).get("mode") if isinstance(case, dict) else None
    decision = case.get("investment_decision") if isinstance(case, dict) else None
    if freeze_mode == "PIT_ENGINEERING" and not isinstance(decision, dict):
        # A constrained engineering freeze can intentionally preserve an
        # unknown action and market-data gap.  Its settlement stays diagnostic
        # at the caller, but the return ledger must still say explicitly that
        # there is no frozen action, position, cash flow, or benchmark result.
        if status != "NOT_CALCULABLE":
            invalid.append("investment_return_outcome:engineering_no_action_requires_not_calculable")
        if action != "UNKNOWN" or outcome.get("frozen_action") != "UNKNOWN":
            invalid.append("investment_return_outcome:engineering_no_action_requires_unknown_action")
        if outcome.get("frozen_price_identity") != "UNKNOWN":
            invalid.append("investment_return_outcome:engineering_no_action_requires_unknown_price_identity")
        if outcome.get("total_return") is not None or outcome.get("benchmark_return") is not None:
            invalid.append("investment_return_outcome:engineering_no_action_cannot_claim_return")
        policy = outcome.get("taxes_fees_fx") if isinstance(outcome.get("taxes_fees_fx"), dict) else {}
        frozen_policy = case.get("taxes_fees_fx") if isinstance(case.get("taxes_fees_fx"), dict) else {}
        for field in ("tax_rate", "transaction_fee_rate", "dividend_tax_rate", "base_currency", "fx_rule"):
            if field not in policy:
                incomplete.append(f"investment_return_outcome.taxes_fees_fx:missing:{field}")
            elif policy.get(field) != frozen_policy.get(field):
                invalid.append(f"investment_return_outcome.taxes_fees_fx:{field}_does_not_match_frozen_case")
        execution = outcome.get("execution") if isinstance(outcome.get("execution"), dict) else {}
        if execution.get("fill_status") != "NOT_APPLICABLE":
            invalid.append("investment_return_outcome:engineering_no_action_requires_not_applicable_execution")
        entry = execution.get("entry") if isinstance(execution.get("entry"), dict) else {}
        exit_leg = execution.get("exit") if isinstance(execution.get("exit"), dict) else {}
        if exit_leg.get("status") != "NOT_APPLICABLE":
            invalid.append("investment_return_outcome:engineering_no_action_requires_not_applicable_exit")
        for leg, prefix in ((entry, "entry"), (exit_leg, "exit")):
            if any(leg.get(field) not in (None, "", []) for field in ("date", "price", "quantity", "currency", "source_ids")):
                invalid.append("investment_return_outcome:engineering_no_action_" + prefix + "_must_be_empty")
        if outcome.get("cash_flow_ledger") not in ([], None):
            invalid.append("investment_return_outcome:engineering_no_action_cash_flows_must_be_empty")
        if outcome.get("corporate_actions") not in ([], None):
            invalid.append("investment_return_outcome:engineering_no_action_corporate_actions_must_be_empty")
        benchmark = outcome.get("benchmark_identity") if isinstance(outcome.get("benchmark_identity"), dict) else {}
        if benchmark.get("source_ids") not in ([], None):
            invalid.append("investment_return_outcome:engineering_no_action_benchmark_sources_must_be_empty")
        return invalid, incomplete
    if not isinstance(decision, dict):
        invalid.append("frozen_investment_decision_required_for_return_settlement")
    else:
        expected_action = decision.get("action")
        expected_identity = decision.get("price_identity")
        expected_rule = decision.get("execution_rule")
        if action != expected_action:
            invalid.append("investment_return_outcome:action_does_not_match_frozen_action")
        if outcome.get("frozen_action") != expected_action:
            invalid.append("investment_return_outcome:frozen_action_does_not_match_case")
        if outcome.get("frozen_price_identity") != expected_identity:
            invalid.append("investment_return_outcome:frozen_price_identity_does_not_match_case")
        selected_price = _frozen_price(case, str(expected_identity or ""))
        if expected_identity != "UNKNOWN" and selected_price is None:
            invalid.append("investment_return_outcome:price_identity_not_registered_in_case")

    policy = outcome.get("taxes_fees_fx")
    if not isinstance(policy, dict):
        incomplete.append("investment_return_outcome:taxes_fees_fx_missing")
    elif isinstance(case, dict):
        frozen_policy = case.get("taxes_fees_fx") if isinstance(case.get("taxes_fees_fx"), dict) else {}
        for field in ("tax_rate", "transaction_fee_rate", "dividend_tax_rate", "base_currency", "fx_rule"):
            if field not in policy:
                incomplete.append(f"investment_return_outcome.taxes_fees_fx:missing:{field}")
            elif policy.get(field) != frozen_policy.get(field) and not (
                field in {"tax_rate", "transaction_fee_rate", "dividend_tax_rate"}
                and _numbers_match(policy.get(field), frozen_policy.get(field))
            ):
                invalid.append(f"investment_return_outcome.taxes_fees_fx:{field}_does_not_match_frozen_case")

    benchmark = outcome.get("benchmark_identity")
    benchmark_source_ids: set[str] = set()
    if not isinstance(benchmark, dict):
        incomplete.append("investment_return_outcome:benchmark_identity_missing")
    else:
        incomplete.extend(_required(
            benchmark,
            ("benchmark_id", "market", "currency", "return_basis", "calculation_rule", "source_ids"),
            "investment_return_outcome.benchmark_identity",
        ))
        benchmark_source_ids = set(str(item) for item in benchmark.get("source_ids") or [])
        if not benchmark_source_ids:
            incomplete.append("investment_return_outcome.benchmark_identity:source_ids_missing")
        ref_invalid, ref_incomplete = _validate_source_references(
            benchmark.get("source_ids"), actual_source_ids, "investment_return_outcome.benchmark_identity",
        )
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        if benchmark_source_ids and not any(
            actual_sources.get(source_id, {}).get("source_type") == "OFFICIAL_MARKET_DATA"
            for source_id in benchmark_source_ids
        ):
            invalid.append("investment_return_outcome.benchmark_identity:official_market_data_source_required")

    execution = outcome.get("execution")
    if not isinstance(execution, dict):
        incomplete.append("investment_return_outcome:execution_missing")
        execution = {}
    incomplete.extend(_required(
        execution, ("execution_rule", "fill_status", "entry", "exit"),
        "investment_return_outcome.execution",
    ))
    if isinstance(decision, dict) and execution.get("execution_rule") != decision.get("execution_rule"):
        invalid.append("investment_return_outcome.execution:rule_does_not_match_frozen_action")
    fill_status = execution.get("fill_status")
    if fill_status not in FILL_STATUSES:
        invalid.append("investment_return_outcome.execution:fill_status_invalid")
    entry = execution.get("entry") if isinstance(execution.get("entry"), dict) else {}
    exit_leg = execution.get("exit") if isinstance(execution.get("exit"), dict) else {}
    leg_fields = ("date", "price", "quantity", "currency", "source_ids")
    for leg, prefix in ((entry, "investment_return_outcome.execution.entry"), (exit_leg, "investment_return_outcome.execution.exit")):
        incomplete.extend(prefix + ":missing:" + field for field in leg_fields if field not in leg)
        if leg.get("source_ids"):
            ref_invalid, ref_incomplete = _validate_source_references(leg.get("source_ids"), actual_source_ids, prefix)
            invalid.extend(ref_invalid)
            incomplete.extend(ref_incomplete)
        leg_date = _timestamp(leg.get("date")) if leg.get("date") else None
        if leg.get("date") and leg_date is None:
            incomplete.append(prefix + ":date_invalid")
        if leg_date and cutoff and leg_date <= cutoff:
            invalid.append(prefix + ":date_must_follow_report_cutoff")
        if leg_date and settlement_date and leg_date > settlement_date:
            invalid.append(prefix + ":date_after_settlement")

    def _leg_populated(leg: dict[str, Any]) -> bool:
        return any(leg.get(field) not in (None, "", []) for field in leg_fields)

    def _require_populated(leg: dict[str, Any], prefix: str) -> None:
        for field in leg_fields:
            if leg.get(field) in (None, "", []):
                incomplete.append(prefix + ":missing_filled_" + field)
        if _number(leg.get("price")) is None or _number(leg.get("price")) <= 0:
            invalid.append(prefix + ":price_invalid")
        if _number(leg.get("quantity")) is None or _number(leg.get("quantity")) <= 0:
            invalid.append(prefix + ":quantity_invalid")

    settled_exit = exit_leg.get("status") in {"EXITED", "MARKED_TO_MARKET"}
    if fill_status in {"FILLED", "PARTIALLY_FILLED"}:
        _require_populated(entry, "investment_return_outcome.execution.entry")
        if exit_leg.get("status") not in EXIT_STATUSES:
            invalid.append("investment_return_outcome.execution.exit:status_invalid")
        elif settled_exit:
            _require_populated(exit_leg, "investment_return_outcome.execution.exit")
        elif _leg_populated(exit_leg) and exit_leg.get("status") not in {"OPEN", "NOT_APPLICABLE"}:
            invalid.append("investment_return_outcome.execution.exit:unsettled_leg_has_values")
        entry_date = _timestamp(entry.get("date"))
        exit_date = _timestamp(exit_leg.get("date"))
        if entry_date and exit_date and exit_date < entry_date:
            invalid.append("investment_return_outcome.execution.exit_before_entry")
    elif fill_status in {"NOT_FILLED", "NOT_APPLICABLE"}:
        if _leg_populated(entry) or _leg_populated(exit_leg):
            invalid.append("investment_return_outcome.execution:unfilled_position_cannot_have_entry_or_exit")
        if exit_leg.get("status") not in {None, "NOT_APPLICABLE"}:
            invalid.append("investment_return_outcome.execution:unfilled_position_exit_must_be_not_applicable")

    if isinstance(decision, dict) and decision.get("price_identity") != "UNKNOWN":
        selected_price = _frozen_price(case or {}, str(decision.get("price_identity")))
        expected_currency = selected_price.get("currency") if selected_price else None
        for leg, prefix in ((entry, "investment_return_outcome.execution.entry"), (exit_leg, "investment_return_outcome.execution.exit")):
            if expected_currency and leg.get("currency") not in (None, "", expected_currency):
                invalid.append(prefix + ":currency_does_not_match_frozen_price_identity")

    ledger = outcome.get("cash_flow_ledger")
    flows: list[dict[str, Any]] = []
    flow_ids: set[str] = set()
    if not isinstance(ledger, list):
        incomplete.append("investment_return_outcome:cash_flow_ledger_missing")
    else:
        flow_fields = ("flow_id", "date", "flow_type", "gross_amount", "tax_amount", "fee_amount", "net_amount", "currency", "fx_rate_to_base", "net_base_amount", "source_ids")
        for index, flow in enumerate(ledger):
            prefix = f"investment_return_outcome.cash_flow_ledger[{index}]"
            if not isinstance(flow, dict):
                invalid.append(prefix + ":not_object")
                continue
            flows.append(flow)
            incomplete.extend(_required(flow, flow_fields, prefix))
            flow_id = str(flow.get("flow_id") or "")
            if flow_id in flow_ids:
                invalid.append(prefix + ":duplicate_flow_id")
            flow_ids.add(flow_id)
            if flow.get("flow_type") not in RETURN_CASH_FLOW_TYPES:
                invalid.append(prefix + ":flow_type_invalid")
            refs = flow.get("source_ids")
            ref_invalid, ref_incomplete = _validate_source_references(refs, actual_source_ids, prefix)
            invalid.extend(ref_invalid)
            incomplete.extend(ref_incomplete)
            flow_date = _timestamp(flow.get("date"))
            if flow_date is None:
                incomplete.append(prefix + ":date_invalid")
            elif settlement_date and flow_date > settlement_date:
                invalid.append(prefix + ":date_after_settlement")
            gross = _number(flow.get("gross_amount"))
            tax = _number(flow.get("tax_amount"))
            fee = _number(flow.get("fee_amount"))
            net = _number(flow.get("net_amount"))
            fx_rate = _number(flow.get("fx_rate_to_base"))
            net_base = _number(flow.get("net_base_amount"))
            if tax is not None and tax < 0:
                invalid.append(prefix + ":tax_amount_negative")
            if fee is not None and fee < 0:
                invalid.append(prefix + ":fee_amount_negative")
            if fx_rate is not None and fx_rate <= 0:
                invalid.append(prefix + ":fx_rate_invalid")
            if gross is not None and tax is not None and fee is not None and net is not None and not _numbers_match(net, gross - tax - fee):
                invalid.append(prefix + ":net_amount_does_not_reconcile")
            if net is not None and fx_rate is not None and net_base is not None and not _numbers_match(net_base, net * fx_rate):
                invalid.append(prefix + ":net_base_amount_does_not_reconcile")
            if flow.get("flow_type") in {"DIVIDEND", "CORPORATE_ACTION_CASH"} and not flow.get("corporate_action_id"):
                invalid.append(prefix + ":corporate_action_link_required")

    actions = outcome.get("corporate_actions")
    action_ids: set[str] = set()
    if not isinstance(actions, list):
        incomplete.append("investment_return_outcome:corporate_actions_missing")
        actions = []
    for index, corporate_action in enumerate(actions):
        prefix = f"investment_return_outcome.corporate_actions[{index}]"
        if not isinstance(corporate_action, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(corporate_action, ("action_id", "action_type", "effective_date", "treatment", "source_ids", "cash_flow_ids"), prefix))
        action_id = str(corporate_action.get("action_id") or "")
        if action_id in action_ids:
            invalid.append(prefix + ":duplicate_action_id")
        action_ids.add(action_id)
        if corporate_action.get("action_type") not in CORPORATE_ACTION_TYPES:
            invalid.append(prefix + ":action_type_invalid")
        ref_invalid, ref_incomplete = _validate_source_references(corporate_action.get("source_ids"), actual_source_ids, prefix)
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        effective_date = _timestamp(corporate_action.get("effective_date"))
        if effective_date and settlement_date and effective_date > settlement_date:
            invalid.append(prefix + ":effective_date_after_settlement")
        linked = corporate_action.get("cash_flow_ids") if isinstance(corporate_action.get("cash_flow_ids"), list) else []
        if corporate_action.get("action_type") == "CASH_DIVIDEND" and not linked:
            incomplete.append(prefix + ":cash_dividend_flow_link_missing")
        for flow_id in linked:
            if flow_id not in flow_ids:
                invalid.append(prefix + ":cash_flow_id_not_found:" + str(flow_id))
            else:
                flow = next(item for item in flows if item.get("flow_id") == flow_id)
                if flow.get("corporate_action_id") != action_id:
                    invalid.append(prefix + ":cash_flow_link_not_bidirectional:" + str(flow_id))
    for flow in flows:
        action_id = flow.get("corporate_action_id")
        if action_id and action_id in action_ids:
            linked_action = next(item for item in actions if item.get("action_id") == action_id)
            if flow.get("flow_id") not in (linked_action.get("cash_flow_ids") or []):
                invalid.append("investment_return_outcome.cash_flow_ledger:corporate_action_link_not_bidirectional:" + str(flow.get("flow_id")))
        elif action_id:
            invalid.append("investment_return_outcome.cash_flow_ledger:corporate_action_id_not_found:" + str(action_id))

    if status == "CALCULATED":
        if fill_status not in {"FILLED", "PARTIALLY_FILLED"} or not settled_exit:
            invalid.append("investment_return_outcome:calculated_requires_filled_and_settled_execution")
        if _number(outcome.get("total_return")) is None:
            invalid.append("investment_return_outcome:total_return_must_be_numeric_when_calculated")
        entry_flows = [flow for flow in flows if flow.get("flow_type") == "ENTRY"]
        final_type = "EXIT" if exit_leg.get("status") == "EXITED" else "MARK_TO_MARKET"
        final_flows = [flow for flow in flows if flow.get("flow_type") == final_type]
        if len(entry_flows) != 1:
            invalid.append("investment_return_outcome:exactly_one_entry_cash_flow_required")
        if len(final_flows) != 1:
            invalid.append("investment_return_outcome:exactly_one_final_cash_flow_required")
        if len(entry_flows) == 1:
            entry_flow = entry_flows[0]
            if entry.get("date") != entry_flow.get("date"):
                invalid.append("investment_return_outcome:entry_cash_flow_date_mismatch")
            entry_price = _number(entry.get("price"))
            entry_quantity = _number(entry.get("quantity"))
            if entry_price is not None and entry_quantity is not None and not _numbers_match(
                entry_flow.get("gross_amount"), -entry_price * entry_quantity,
            ):
                invalid.append("investment_return_outcome:entry_cash_flow_price_quantity_mismatch")
        if len(final_flows) == 1:
            final_flow = final_flows[0]
            if exit_leg.get("date") != final_flow.get("date"):
                invalid.append("investment_return_outcome:exit_cash_flow_date_mismatch")
            exit_price = _number(exit_leg.get("price"))
            exit_quantity = _number(exit_leg.get("quantity"))
            if exit_price is not None and exit_quantity is not None and not _numbers_match(
                final_flow.get("gross_amount"), exit_price * exit_quantity,
            ):
                invalid.append("investment_return_outcome:exit_cash_flow_price_quantity_mismatch")
        if entry_flows and final_flows and _number(entry_flows[0].get("net_base_amount")) is not None:
            invested = -_number(entry_flows[0].get("net_base_amount"))
            if invested <= 0:
                invalid.append("investment_return_outcome:entry_cash_flow_must_be_negative")
            else:
                expected_return = sum(_number(flow.get("net_base_amount")) or 0.0 for flow in flows) / invested
                if not _numbers_match(outcome.get("total_return"), expected_return):
                    invalid.append("investment_return_outcome:total_return_does_not_reconcile_to_cash_flow_ledger")
    return invalid, incomplete


def validate_settlement(
    record: dict[str, Any], *, case: dict[str, Any] | None = None, experiment: dict[str, Any] | None = None,
    allow_test_fixtures: bool = True,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    settlement_v2 = record.get("schema_version") == SETTLEMENT_SCHEMA_VERSION_V2
    if record.get("schema_version") not in {SETTLEMENT_SCHEMA_VERSION, SETTLEMENT_SCHEMA_VERSION_V2}:
        invalid.append("schema_version_invalid")
    if not str(record.get("experiment_id") or "").startswith("HBT:"):
        invalid.append("settlement_experiment_id_invalid")
    if case is None:
        invalid.append("frozen_case_required_for_settlement_calibration")
    else:
        case_v2 = _is_case_v2(case)
        if settlement_v2 != case_v2:
            invalid.append("settlement_schema_version_does_not_match_case")
        case_result = validate_case(case, experiment=experiment, allow_test_fixtures=allow_test_fixtures)
        if case_result["state"] != "REVIEWABLE":
            freeze = case.get("report_freeze") if isinstance(case.get("report_freeze"), dict) else {}
            if (
                freeze.get("mode") == "PIT_ENGINEERING"
                and freeze.get("report_status") == "FROZEN_WITH_QUALITY_FAILURE"
                and not case_result["invalid_findings"]
            ):
                incomplete.append("engineering_case_quality_failure")
            else:
                invalid.append("frozen_case_not_reviewable")
        if record.get("case_id") != case.get("case_id"):
            invalid.append("settlement_case_id_does_not_match_frozen_case")
        if record.get("experiment_id") != case.get("experiment_id"):
            invalid.append("settlement_experiment_id_does_not_match_frozen_case")
        case_freeze = (case.get("report_freeze") or {}).get("freeze_id")
        if record.get("freeze_id") != case_freeze:
            invalid.append("settlement_freeze_id_does_not_match_frozen_case")
        if (case.get("report_freeze") or {}).get("mode") == "PIT_ENGINEERING":
            # Engineering replay may retain an explicit diagnostic settlement,
            # but it must never be promoted into the production/calibration
            # result set or used as an investment-return conclusion.
            incomplete.append("engineering_freeze_settlement_diagnostic_only")
            if record.get("status") == "REVIEWABLE":
                invalid.append("engineering_freeze_cannot_produce_reviewable_settlement")
    cutoff = _timestamp(case.get("simulation_cutoff")) if case else None
    settlement_date = _timestamp(record.get("settlement_as_of"))
    if settlement_date is None:
        invalid.append("settlement_as_of_invalid")
    elif cutoff and settlement_date <= cutoff:
        invalid.append("settlement_must_follow_report_cutoff")
    actual_sources, source_invalid, source_incomplete = _validate_actual_sources(
        record, cutoff=cutoff, settlement_date=settlement_date, require_content_access=settlement_v2,
    )
    invalid.extend(source_invalid)
    incomplete.extend(source_incomplete)
    actual_sources = {
        str(source.get("source_id")): source
        for source in record.get("actual_sources", [])
        if isinstance(source, dict) and source.get("source_id")
    }
    actual_source_ids = set(actual_sources)
    actual = record.get("actual_outcomes") if isinstance(record.get("actual_outcomes"), dict) else {}
    if _is_case_v2(case) and settlement_date:
        for claim_id, claim in _frozen_claims(case).items():
            outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
            window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
            closes_at = _timestamp(window.get("closes_at"))
            if closes_at and closes_at > settlement_date:
                invalid.append("calibration_ledger.claims:" + claim_id + ":observation_window_closes_after_settlement")
    incomplete.extend(_required(actual, ("currency", "cash_flows", "operating_observations"), "actual_outcomes"))
    observation_fields = (
        "observation_id", "claim_id", "metric", "value", "unit", "measurement_basis", "measurement_period",
        "source_ids", "comparability_status",
    ) if settlement_v2 else (
        "observation_id", "claim_id", "metric", "value", "unit", "measurement_basis", "period_start",
        "period_end", "source_ids", "comparability_status",
    )
    for group, fields in {
        "cash_flows": ("date", "amount", "source_ids"),
        "operating_observations": observation_fields,
    }.items():
        observations = actual.get(group) if isinstance(actual.get(group), list) else []
        for index, observation in enumerate(observations):
            prefix = f"actual_outcomes.{group}[{index}]"
            if not isinstance(observation, dict):
                invalid.append(prefix + ":not_object")
                continue
            incomplete.extend(_required(observation, fields, prefix))
            ref_invalid, ref_incomplete = _validate_source_references(
                observation.get("source_ids"), set(actual_sources), prefix,
            )
            invalid.extend(ref_invalid)
            incomplete.extend(ref_incomplete)
    for section, fields in {
        "report_coverage": ("status", "supported_claim_count", "unsupported_claim_count", "unknowns_preserved", "notes"),
        "model_forecast_error": ("status", "metrics", "notes"),
        "investment_return_outcome": ("status", "action", "total_return", "benchmark_return", "currency", "notes"),
    }.items():
        payload = record.get(section) if isinstance(record.get(section), dict) else {}
        incomplete.extend(_required(payload, fields, section))
    return_outcome = record.get("investment_return_outcome") if isinstance(record.get("investment_return_outcome"), dict) else {}
    return_invalid, return_incomplete = _validate_return_outcome(
        return_outcome,
        case=case,
        actual_source_ids=actual_source_ids,
        actual_sources=actual_sources,
        cutoff=cutoff,
        settlement_date=settlement_date,
    )
    invalid.extend(return_invalid)
    incomplete.extend(return_incomplete)
    frozen_predictions = _frozen_predictions(case)
    frozen_claims = _frozen_claims(case)
    coverage = record.get("report_coverage") if isinstance(record.get("report_coverage"), dict) else {}
    coverage_invalid, coverage_incomplete = _validate_report_coverage(
        coverage, case=case, frozen_claims=frozen_claims,
    )
    invalid.extend(coverage_invalid)
    incomplete.extend(coverage_incomplete)
    observation_by_id: dict[str, dict[str, Any]] = {}
    for index, observation in enumerate(actual.get("operating_observations") or []):
        if not isinstance(observation, dict) or not case:
            continue
        prefix = f"actual_outcomes.operating_observations[{index}]"
        observation_id = str(observation.get("observation_id") or "")
        if not observation_id.startswith("HBTOBS:"):
            invalid.append(prefix + ":observation_id_invalid")
        elif observation_id in observation_by_id:
            invalid.append("duplicate_operating_observation_id:" + observation_id)
        else:
            observation_by_id[observation_id] = observation
        observation_invalid, observation_incomplete = _validate_operating_observation(
            observation,
            prefix=prefix,
            frozen_claims=frozen_claims,
            actual_sources=actual_sources,
            case_v2=_is_case_v2(case),
            settlement_date=settlement_date,
        )
        invalid.extend(observation_invalid)
        incomplete.extend(observation_incomplete)
    model_error = record.get("model_forecast_error") if isinstance(record.get("model_forecast_error"), dict) else {}
    timeline_invalid, timeline_incomplete = _validate_operating_source_timeline(
        record, actual_sources=actual_sources, observations=observation_by_id,
    )
    invalid.extend(timeline_invalid)
    incomplete.extend(timeline_incomplete)
    claim_settlements, settlement_invalid, settlement_incomplete = _validate_claim_settlements(
        model_error, frozen_claims=frozen_claims, observations=observation_by_id,
    )
    invalid.extend(settlement_invalid)
    incomplete.extend(settlement_incomplete)
    metrics_by_claim: dict[str, list[dict[str, Any]]] = {}
    for index, metric in enumerate(model_error.get("metrics") or []):
        prefix = f"model_forecast_error.metrics[{index}]"
        if not isinstance(metric, dict):
            invalid.append(prefix + ":not_object")
            continue
        incomplete.extend(_required(
            metric,
            (
                "claim_id", "observation_id", "metric", "forecast_value", "actual_value", "unit",
                "actual_source_ids",
            ),
            prefix,
        ))
        ref_invalid, ref_incomplete = _validate_source_references(
            metric.get("actual_source_ids"), set(actual_sources), prefix,
        )
        invalid.extend(ref_invalid)
        incomplete.extend(ref_incomplete)
        if case:
            claim_id = str(metric.get("claim_id") or "")
            metrics_by_claim.setdefault(claim_id, []).append(metric)
            frozen = frozen_predictions.get(claim_id)
            if frozen is None:
                invalid.append(prefix + ":claim_has_no_frozen_quantitative_prediction:" + claim_id)
                continue
            claim_settlement = claim_settlements.get(claim_id)
            if claim_settlement is None:
                incomplete.append(prefix + ":claim_settlement_missing")
            elif claim_settlement.get("status") != "CALCULATED":
                invalid.append(prefix + ":metric_requires_calculated_claim_settlement")
            prediction = frozen.get("prediction") if isinstance(frozen.get("prediction"), dict) else {}
            if metric.get("metric") != prediction.get("metric"):
                invalid.append(prefix + ":metric_does_not_match_frozen_prediction")
            if metric.get("forecast_value") != prediction.get("value"):
                invalid.append(prefix + ":forecast_value_does_not_match_frozen_prediction")
            observation_id = str(metric.get("observation_id") or "")
            observation = observation_by_id.get(observation_id)
            if observation is None:
                invalid.append(prefix + ":observation_id_not_found:" + observation_id)
                continue
            if metric.get("claim_id") != observation.get("claim_id"):
                invalid.append(prefix + ":claim_id_does_not_match_operating_observation")
            if metric.get("metric") != observation.get("metric"):
                invalid.append(prefix + ":metric_does_not_match_operating_observation")
            if metric.get("unit") != observation.get("unit"):
                invalid.append(prefix + ":unit_does_not_match_operating_observation")
            if metric.get("actual_value") != observation.get("value"):
                invalid.append(prefix + ":actual_value_does_not_match_operating_observation")
            if set(metric.get("actual_source_ids") or []) != set(observation.get("source_ids") or []):
                invalid.append(prefix + ":actual_source_ids_do_not_match_operating_observation")
            if observation.get("comparability_status") not in COMPARABLE_OPERATING_STATUSES:
                invalid.append(prefix + ":actual_observation_not_comparable")
            if claim_settlement is not None and observation_id not in (claim_settlement.get("observation_ids") or []):
                invalid.append(prefix + ":observation_not_registered_for_claim_settlement")
            version_invalid, version_incomplete = _validate_metric_version_policy(
                metric, observation, frozen_claim=frozen, observations=observation_by_id,
                actual_sources=actual_sources, prefix=prefix,
            )
            invalid.extend(version_invalid)
            incomplete.extend(version_incomplete)
    for claim_id in frozen_predictions:
        claim_settlement = claim_settlements.get(claim_id)
        if claim_settlement is None:
            continue
        metrics = metrics_by_claim.get(claim_id, [])
        if claim_settlement.get("status") == "CALCULATED" and len(metrics) != 1:
            invalid.append("model_forecast_error.claim_settlements:" + claim_id + ":calculated_prediction_requires_exactly_one_metric")
        if model_error.get("status") == "CALCULATED" and claim_settlement.get("status") != "CALCULATED":
            invalid.append("model_forecast_error:calculated_requires_all_prediction_claims_calculated")
    forbidden = _nested_forbidden(record, path="settlement")
    # Hindsight is expected in actual_outcomes; only reject a combined score.
    if "combined_score" in json.dumps(record, ensure_ascii=False).lower() or "composite_score" in json.dumps(record, ensure_ascii=False).lower():
        invalid.append("combined_score_forbidden")
    if record.get("status") == "REVIEWABLE" and incomplete:
        invalid.append("reviewable_settlement_incomplete")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": list(dict.fromkeys(invalid)), "incomplete_findings": list(dict.fromkeys(incomplete)), "hindsight_fields_seen": len(forbidden)}


def build_pilot_experiment(*, registered_at: str = "2026-08-16T00:00:00+08:00") -> dict[str, Any]:
    """Pre-register current candidates without pretending their vintages exist."""
    cases = [
        {
            "case_id": f"HBTCASE:{code}",
            "company_code": code,
            "company_name": name,
            "eligibility_status": "INELIGIBLE_NO_HISTORICAL_VINTAGE",
            "eligibility_reason": "当前候选保存的是最新研究输出，未同时保存可验证的历史报告版本、逐源发布时间和当时市场数据，不能重建无前视信息的冻结报告。",
            "calibration_eligibility": "NOT_ELIGIBLE_MODEL_MEMORY",
        }
        for code, name in PILOT_CASES
    ]
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_id": "HBT:current-candidates-pilot-v1",
        "status": "PRE_REGISTERED",
        "registered_at": registered_at,
        "framework": {
            "framework_version": "Turtle-G2-2026-08-16",
            "route_policy": "route-aware-long-owner-finite-xirr-dual",
            "golden_gate_state": "G3_NOT_READY",
        },
        "information_policy": {
            "cutoff_timezone": "Asia/Shanghai",
            "source_rule": "published_at_and_data_as_of_must_not_exceed_cutoff",
            "current_restated_data_rule": "current_restated_values_are_ineligible_without_historical_vintage",
            "future_file_rule": "future_files_are_unreadable_before_settlement",
            "survivorship_rule": "retain_delisted_acquired_and_failed_cases_in_registered_universe",
            "execution_rule": "next_tradable_price_after_frozen_report_or_preregistered_rule",
        },
        "credibility": {
            "model_memory_control": "UNCONTROLLED",
            "backtest_credibility": "EXPLORATORY",
            "assessment_basis": "当前模型可能在训练中见过历史发行人及其后续事件；尚无可验证的参数记忆隔离证据。",
            "control_evidence": [],
            "calibration_role": "ENGINEERING_DIAGNOSTIC_ONLY",
        },
        "universe": {
            "selection_status": "RESEARCH_PILOT",
            "cases": cases,
            "eligible_case_count": 0,
            "calibration_eligible_case_count": 0,
        },
        "scoring_policy": {
            "separate_dimensions": ["REPORT_COVERAGE", "MODEL_FORECAST_ERROR", "INVESTMENT_RETURN_OUTCOME"],
            "no_compensating_score": True,
            "minimum_outcome_fields": ["cash_flows", "benchmark_return", "currency", "execution_rule"],
        },
    }


def validate_pilot(path: str | Path | None = None) -> dict[str, Any]:
    payload = build_pilot_experiment() if path is None else json.loads(Path(path).read_text(encoding="utf-8"))
    result = validate_experiment(payload)
    result["eligible_case_count"] = payload.get("universe", {}).get("eligible_case_count")
    result["pilot_is_empty"] = result["eligible_case_count"] == 0
    return result


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pilot = sub.add_parser("pilot", help="write the honest current-candidate pilot registry")
    pilot.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate", help="validate an experiment, case or settlement JSON")
    validate.add_argument("kind", choices=["experiment", "case", "settlement"])
    validate.add_argument("path", type=Path)
    validate.add_argument("--case", type=Path, help="frozen case required to cross-check a settlement")
    validate.add_argument("--experiment", type=Path, help="registered experiment required for a calibration candidate")
    validate.add_argument("--allow-test-fixtures", action="store_true", help="allow HBTCASE:TEST regression fixtures")
    args = parser.parse_args()
    if args.command == "pilot":
        payload = build_pilot_experiment()
        _write(args.output, payload)
        print(json.dumps({"written": str(args.output), "eligible_case_count": 0}, ensure_ascii=False))
        return 0
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    experiment = json.loads(args.experiment.read_text(encoding="utf-8")) if args.experiment else None
    if args.kind == "experiment":
        result = validate_experiment(payload)
    elif args.kind == "case":
        result = validate_case(payload, experiment=experiment, allow_test_fixtures=args.allow_test_fixtures)
    else:
        case = json.loads(args.case.read_text(encoding="utf-8")) if args.case else None
        result = validate_settlement(payload, case=case, experiment=experiment, allow_test_fixtures=args.allow_test_fixtures)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "REVIEWABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
