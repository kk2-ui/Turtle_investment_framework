#!/usr/bin/env python3
"""Run a preregistered paired test of two research architectures.

The experiment asks a deliberately narrow question: when the company evidence,
cutoff, material judgment target, and golden-report standard are held fixed,
does an independently produced industry/macro-enhanced arm add useful judgment
information over a company-only arm?  Report-quality review and later operating
settlement remain separate outputs.  Neither is converted into a method score,
probability, investment return, or claim of general superiority.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


PLAN_SCHEMA_VERSION = "judgment-architecture-experiment-plan.v1"
BLIND_REVIEW_SCHEMA_VERSION = "judgment-architecture-blind-review.v1"
UNBLINDING_SCHEMA_VERSION = "judgment-architecture-unblinding.v1"
QUALITY_RESULT_SCHEMA_VERSION = "judgment-architecture-quality-result.v1"
EVALUATION_SCHEMA_VERSION = "judgment-architecture-relative-evaluation.v1"

EXPERIMENT_ID_PREFIX = "JAX:"
REPORT_PAIR_ID_PREFIX = "JAXREPORT:"
PAIRED_UNIT_ID_PREFIX = "JAXUNIT:"
ARM_CONDITIONS = {"COMPANY_ONLY", "INDUSTRY_MACRO_ENHANCED"}
HOLDOUT_AXES = {"DOMAIN_DEVELOPMENT", "UNSEEN_COMPANY", "UNSEEN_TIME"}
MATERIAL_JUDGMENT_OBJECTS = {
    "NORMALIZED_EARNINGS", "OWNER_CASH", "PERMANENT_LOSS", "CAPITAL_RETURN",
}
PAIR_OUTCOMES = {
    "ENHANCED_ONLY_MET", "COMPANY_ONLY_ONLY_MET", "BOTH_MET", "BOTH_MISSED",
    "PENDING", "NOT_COMPARABLE",
}
QUALITY_RESULTS = {"MATERIAL_IMPROVEMENT", "NO_MATERIAL_GAIN", "WORSE"}
INCREMENT_OUTCOMES = {
    "JUDGMENT_BETTER", "BASELINE_BETTER", "NO_DIRECTIONAL_INCREMENT_IDENTIFIED",
    "BASELINE_NONDISCRIMINATING", "NOT_EVALUATED",
}
SATISFIED_OUTCOMES = {"MET", "WITHIN_RANGE"}
MISSED_OUTCOMES = {"MISSED", "BELOW_RANGE", "ABOVE_RANGE"}
NONCOMPARABLE_OBSERVATION_STATES = {
    "PERIOD_MISMATCH", "SCOPE_OR_ACCOUNTING_DRIFT", "NOT_COMPARABLE",
}
FORBIDDEN_PLAN_FIELDS = {
    "price", "market_price", "valuation", "position", "action", "probability",
    "score", "accuracy", "win_rate", "investment_return", "expected_return",
}

EXPECTED_PROTOCOL = {
    "comparison_unit": "PAIRED_MATERIAL_JUDGMENT",
    "control_condition": "COMPANY_ONLY",
    "treatment_condition": "INDUSTRY_MACRO_ENHANCED",
    "report_standard": "SAME_GOLDEN_STANDARD",
    "company_evidence": "SAME_CUTOFF_AND_PACKAGE",
    "arm_isolation": "FREEZE_BEFORE_CROSS_ARM_ACCESS",
    "quality_review": "BLIND_SEPARATE_FROM_OUTCOME",
    "outcome_boundary": "NON_PRICE_OPERATING_ONLY",
    "retention": "RETAIN_ALL_PAIRED_UNITS_AND_UNRESOLVED",
}


class ArchitectureExperimentError(ValueError):
    """Raised when an experiment would break its paired or blind contract."""


def _instant(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _unsupported_fields(value: Any, allowed: set[str]) -> list[str]:
    if not isinstance(value, dict):
        return []
    return sorted(str(field) for field in value if str(field) not in allowed)


def _missing_text(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _as_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(_missing_text(item) for item in value):
        return None
    return [str(item) for item in value]


def _forbidden_field(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_PLAN_FIELDS:
                return str(key)
            nested = _forbidden_field(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = _forbidden_field(item)
            if nested:
                return nested
    return None


def _fingerprint_payload(plan: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(plan)
    freeze = payload.get("freeze")
    if isinstance(freeze, dict):
        freeze.pop("fingerprint", None)
    payload.pop("generated_at", None)
    payload.pop("updated_at", None)
    return payload


def architecture_experiment_plan_fingerprint(plan: dict[str, Any]) -> str:
    raw = json.dumps(
        _fingerprint_payload(plan), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_outcome_contract(
    contract: Any, *, prefix: str, invalid: list[str], incomplete: list[str],
) -> datetime | None:
    allowed = {
        "outcome_target_id", "source_contract_ref", "measurement_contract_ref",
        "outcome_observation_identity", "outcome_not_before", "simple_baseline",
    }
    if not isinstance(contract, dict):
        incomplete.append(prefix + ":outcome_contract_missing")
        return None
    invalid.extend(
        prefix + ":outcome_contract:unsupported_field:" + field
        for field in _unsupported_fields(contract, allowed)
    )
    for field in allowed - {"simple_baseline", "outcome_observation_identity"}:
        if _missing_text(contract.get(field)):
            incomplete.append(prefix + ":outcome_contract:" + field + "_missing")
    outcome_not_before = _instant(contract.get("outcome_not_before"))
    if outcome_not_before is None:
        invalid.append(prefix + ":outcome_contract:outcome_not_before_invalid")
    observation_identity = contract.get("outcome_observation_identity")
    if not isinstance(observation_identity, dict):
        incomplete.append(prefix + ":outcome_contract:outcome_observation_identity_missing")
    else:
        allowed_identity = {"observation_id", "metric", "unit"}
        invalid.extend(
            prefix + ":outcome_contract:outcome_observation_identity:unsupported_field:" + field
            for field in _unsupported_fields(observation_identity, allowed_identity)
        )
        for field in allowed_identity:
            if _missing_text(observation_identity.get(field)):
                incomplete.append(
                    prefix + ":outcome_contract:outcome_observation_identity:" + field + "_missing"
                )
    baseline = contract.get("simple_baseline")
    if not isinstance(baseline, dict):
        incomplete.append(prefix + ":outcome_contract:simple_baseline_missing")
    else:
        allowed_baseline = {"baseline_id", "method", "prediction_ref", "prediction"}
        invalid.extend(
            prefix + ":outcome_contract:simple_baseline:unsupported_field:" + field
            for field in _unsupported_fields(baseline, allowed_baseline)
        )
        for field in allowed_baseline - {"prediction"}:
            if _missing_text(baseline.get(field)):
                incomplete.append(prefix + ":outcome_contract:simple_baseline:" + field + "_missing")
        if not isinstance(baseline.get("prediction"), dict):
            incomplete.append(prefix + ":outcome_contract:simple_baseline:prediction_invalid")
    return outcome_not_before


def _validate_arm(
    arm: Any, *, condition: str, prefix: str, invalid: list[str], incomplete: list[str],
) -> datetime | None:
    allowed = {
        "condition", "case_id", "freeze_id", "claim_id", "forward_judgment_id",
        "report_artifact_ref", "company_evidence_package_ref", "author_agent_id",
        "author_context_id", "frozen_at", "other_arm_access_before_freeze",
        "industry_mechanism_refs", "macro_scenario_refs",
    }
    if not isinstance(arm, dict):
        incomplete.append(prefix + ":missing")
        return None
    invalid.extend(
        prefix + ":unsupported_field:" + field for field in _unsupported_fields(arm, allowed)
    )
    for field in allowed - {
        "other_arm_access_before_freeze", "industry_mechanism_refs", "macro_scenario_refs",
    }:
        if _missing_text(arm.get(field)):
            incomplete.append(prefix + ":" + field + "_missing")
    if arm.get("condition") != condition:
        invalid.append(prefix + ":condition_mismatch")
    frozen_at = _instant(arm.get("frozen_at"))
    if frozen_at is None:
        invalid.append(prefix + ":frozen_at_invalid")
    if arm.get("other_arm_access_before_freeze") is not False:
        invalid.append(prefix + ":other_arm_access_before_freeze_must_be_false")
    industry_refs = _as_string_list(arm.get("industry_mechanism_refs"))
    macro_refs = _as_string_list(arm.get("macro_scenario_refs"))
    if industry_refs is None:
        invalid.append(prefix + ":industry_mechanism_refs_invalid")
        industry_refs = []
    if macro_refs is None:
        invalid.append(prefix + ":macro_scenario_refs_invalid")
        macro_refs = []
    if condition == "COMPANY_ONLY" and (industry_refs or macro_refs):
        invalid.append(prefix + ":company_only_arm_contains_industry_or_macro_refs")
    if condition == "INDUSTRY_MACRO_ENHANCED" and not (industry_refs or macro_refs):
        incomplete.append(prefix + ":enhanced_arm_requires_industry_or_macro_ref")
    return frozen_at


def validate_architecture_experiment_plan(plan: Any) -> dict[str, Any]:
    """Validate a preregistered paired V1/V2 architecture experiment."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(plan, dict):
        return {"state": "INVALID", "invalid_findings": ["plan_not_object"], "incomplete_findings": []}
    allowed = {
        "schema_version", "experiment_id", "protocol", "readiness_contract", "paired_units", "freeze",
    }
    invalid.extend("unsupported_field:" + field for field in _unsupported_fields(plan, allowed))
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(plan.get("experiment_id") or "").startswith(EXPERIMENT_ID_PREFIX):
        incomplete.append("experiment_id_missing_or_invalid")
    forbidden = _forbidden_field(plan)
    if forbidden:
        invalid.append("price_return_probability_or_score_field_forbidden:" + forbidden)
    if plan.get("protocol") != EXPECTED_PROTOCOL:
        invalid.append("protocol_must_equal_paired_golden_nonprice_contract")

    readiness = plan.get("readiness_contract")
    expected_readiness_fields = {
        "minimum_independent_company_clusters_for_domain_comparison",
        "minimum_unseen_company_clusters",
        "minimum_unseen_time_company_clusters",
    }
    if not isinstance(readiness, dict):
        incomplete.append("readiness_contract_missing")
        readiness = {}
    else:
        invalid.extend(
            "readiness_contract:unsupported_field:" + field
            for field in _unsupported_fields(readiness, expected_readiness_fields)
        )
    for field in sorted(expected_readiness_fields):
        value = readiness.get(field)
        if not isinstance(value, int) or value < 2:
            invalid.append("readiness_contract:" + field + "_must_be_at_least_two")

    freeze = plan.get("freeze")
    preregistered_at: datetime | None = None
    if not isinstance(freeze, dict) or freeze.get("frozen") is not True:
        incomplete.append("freeze_missing")
    else:
        unsupported = _unsupported_fields(freeze, {"frozen", "preregistered_at", "fingerprint"})
        invalid.extend("freeze:unsupported_field:" + field for field in unsupported)
        preregistered_at = _instant(freeze.get("preregistered_at"))
        if preregistered_at is None:
            invalid.append("freeze_preregistered_at_invalid")
        if freeze.get("fingerprint") != architecture_experiment_plan_fingerprint(plan):
            invalid.append("freeze_fingerprint_mismatch")

    units = plan.get("paired_units") if isinstance(plan.get("paired_units"), list) else []
    if not units:
        incomplete.append("paired_units_missing")
    seen_unit_ids: set[str] = set()
    seen_arm_identities: dict[str, set[str]] = {
        field: set() for field in ("claim_id", "forward_judgment_id")
    }
    report_pair_bindings: dict[str, dict[str, Any]] = {}
    report_pair_unit_counts: dict[str, int] = {}
    report_pair_outcome_targets: dict[str, set[str]] = {}
    report_identity_owners: dict[tuple[str, str, str], str] = {}
    holdout_coverage = {axis: {"units": 0, "company_clusters": set()} for axis in HOLDOUT_AXES}
    for index, unit in enumerate(units):
        prefix = f"paired_units[{index}]"
        if not isinstance(unit, dict):
            invalid.append(prefix + ":not_object")
            continue
        allowed_unit = {
            "paired_unit_id", "report_pair_id", "company_id", "company_cluster_id", "period_cluster_id",
            "information_cutoff", "holdout_axis", "material_judgment_object",
            "outcome_contract", "arms", "blind_packets",
        }
        invalid.extend(
            prefix + ":unsupported_field:" + field
            for field in _unsupported_fields(unit, allowed_unit)
        )
        for field in {
            "paired_unit_id", "report_pair_id", "company_id", "company_cluster_id", "period_cluster_id",
            "information_cutoff",
        }:
            if _missing_text(unit.get(field)):
                incomplete.append(prefix + ":" + field + "_missing")
        unit_id = str(unit.get("paired_unit_id") or "")
        if unit_id and not unit_id.startswith(PAIRED_UNIT_ID_PREFIX):
            invalid.append(prefix + ":paired_unit_id_invalid")
        if unit_id in seen_unit_ids:
            invalid.append(prefix + ":paired_unit_id_duplicate:" + unit_id)
        seen_unit_ids.add(unit_id)
        report_pair_id = str(unit.get("report_pair_id") or "")
        if report_pair_id and not report_pair_id.startswith(REPORT_PAIR_ID_PREFIX):
            invalid.append(prefix + ":report_pair_id_invalid")
        if report_pair_id:
            report_pair_unit_counts[report_pair_id] = report_pair_unit_counts.get(report_pair_id, 0) + 1
        holdout_axis = str(unit.get("holdout_axis") or "")
        if holdout_axis not in HOLDOUT_AXES:
            invalid.append(prefix + ":holdout_axis_invalid")
        else:
            holdout_coverage[holdout_axis]["units"] += 1
            company_cluster = str(unit.get("company_cluster_id") or "")
            if company_cluster:
                holdout_coverage[holdout_axis]["company_clusters"].add(company_cluster)
        if unit.get("material_judgment_object") not in MATERIAL_JUDGMENT_OBJECTS:
            invalid.append(prefix + ":material_judgment_object_invalid")
        cutoff = _instant(unit.get("information_cutoff"))
        if cutoff is None:
            invalid.append(prefix + ":information_cutoff_invalid")
        outcome_not_before = _validate_outcome_contract(
            unit.get("outcome_contract"), prefix=prefix, invalid=invalid, incomplete=incomplete,
        )
        outcome_target_id = str((unit.get("outcome_contract") or {}).get("outcome_target_id") or "")
        if report_pair_id and outcome_target_id:
            seen_targets = report_pair_outcome_targets.setdefault(report_pair_id, set())
            if outcome_target_id in seen_targets:
                invalid.append(prefix + ":outcome_target_reused_within_report_pair:" + outcome_target_id)
            seen_targets.add(outcome_target_id)

        arms = unit.get("arms")
        if not isinstance(arms, dict):
            incomplete.append(prefix + ":arms_missing")
            arms = {}
        else:
            invalid.extend(
                prefix + ":arms:unsupported_field:" + field
                for field in _unsupported_fields(arms, {"company_only", "industry_macro_enhanced"})
            )
        control = arms.get("company_only")
        treatment = arms.get("industry_macro_enhanced")
        control_frozen_at = _validate_arm(
            control, condition="COMPANY_ONLY", prefix=prefix + ":arms:company_only",
            invalid=invalid, incomplete=incomplete,
        )
        treatment_frozen_at = _validate_arm(
            treatment, condition="INDUSTRY_MACRO_ENHANCED",
            prefix=prefix + ":arms:industry_macro_enhanced", invalid=invalid, incomplete=incomplete,
        )
        if isinstance(control, dict) and isinstance(treatment, dict):
            if control.get("company_evidence_package_ref") != treatment.get("company_evidence_package_ref"):
                invalid.append(prefix + ":arms:company_evidence_package_mismatch")
            if control.get("author_agent_id") == treatment.get("author_agent_id"):
                invalid.append(prefix + ":arms:author_agent_must_be_disjoint")
            if control.get("author_context_id") == treatment.get("author_context_id"):
                invalid.append(prefix + ":arms:author_context_must_be_disjoint")
            for field in ("case_id", "freeze_id", "claim_id", "forward_judgment_id", "report_artifact_ref"):
                left = str(control.get(field) or "")
                right = str(treatment.get(field) or "")
                if left and left == right:
                    invalid.append(prefix + ":arms:" + field + "_must_be_disjoint")
            for field in seen_arm_identities:
                left = str(control.get(field) or "")
                right = str(treatment.get(field) or "")
                for condition, value in (("company_only", left), ("industry_macro_enhanced", right)):
                    if value in seen_arm_identities[field]:
                        invalid.append(prefix + ":arms:" + condition + ":" + field + "_reused:" + value)
                    if value:
                        seen_arm_identities[field].add(value)
            if report_pair_id:
                for condition, arm in (
                    ("company_only", control), ("industry_macro_enhanced", treatment),
                ):
                    for field in ("case_id", "freeze_id", "report_artifact_ref"):
                        value = str(arm.get(field) or "")
                        identity = (condition, field, value)
                        owner = report_identity_owners.get(identity)
                        if value and owner is not None and owner != report_pair_id:
                            invalid.append(
                                prefix + ":arms:" + condition + ":" + field
                                + ":reused_across_report_pairs:" + owner + ":" + report_pair_id
                            )
                        if value:
                            report_identity_owners[identity] = report_pair_id
        for label, frozen_at in (
            ("company_only", control_frozen_at), ("industry_macro_enhanced", treatment_frozen_at),
        ):
            if preregistered_at and frozen_at and preregistered_at > frozen_at:
                invalid.append(prefix + ":arms:" + label + ":arm_frozen_before_preregistration")
            if cutoff and frozen_at and cutoff > frozen_at:
                invalid.append(prefix + ":arms:" + label + ":arm_frozen_before_information_cutoff")
            if outcome_not_before and frozen_at and frozen_at >= outcome_not_before:
                invalid.append(prefix + ":arms:" + label + ":arm_not_frozen_before_outcome_window")
        if preregistered_at and outcome_not_before and preregistered_at >= outcome_not_before:
            invalid.append(prefix + ":plan_not_preregistered_before_outcome_window")

        packets = unit.get("blind_packets")
        if not isinstance(packets, dict):
            incomplete.append(prefix + ":blind_packets_missing")
        else:
            invalid.extend(
                prefix + ":blind_packets:unsupported_field:" + field
                for field in _unsupported_fields(packets, {"blind_a_packet_ref", "blind_b_packet_ref"})
            )
            for field in ("blind_a_packet_ref", "blind_b_packet_ref"):
                if _missing_text(packets.get(field)):
                    incomplete.append(prefix + ":blind_packets:" + field + "_missing")
            if packets.get("blind_a_packet_ref") == packets.get("blind_b_packet_ref"):
                invalid.append(prefix + ":blind_packets:packet_refs_must_be_disjoint")
            if report_pair_id:
                for label, field in (
                    ("BLIND_A", "blind_a_packet_ref"), ("BLIND_B", "blind_b_packet_ref"),
                ):
                    value = str(packets.get(field) or "")
                    identity = (label, "packet_ref", value)
                    owner = report_identity_owners.get(identity)
                    if value and owner is not None and owner != report_pair_id:
                        invalid.append(
                            prefix + ":blind_packets:" + field
                            + ":reused_across_report_pairs:" + owner + ":" + report_pair_id
                        )
                    if value:
                        report_identity_owners[identity] = report_pair_id

        if report_pair_id and isinstance(control, dict) and isinstance(treatment, dict) and isinstance(packets, dict):
            report_binding = {
                "company_id": unit.get("company_id"),
                "company_cluster_id": unit.get("company_cluster_id"),
                "period_cluster_id": unit.get("period_cluster_id"),
                "information_cutoff": unit.get("information_cutoff"),
                "holdout_axis": unit.get("holdout_axis"),
                "company_only": {
                    field: control.get(field) for field in (
                        "case_id", "freeze_id", "report_artifact_ref", "company_evidence_package_ref",
                        "author_agent_id", "author_context_id", "frozen_at",
                        "industry_mechanism_refs", "macro_scenario_refs",
                    )
                },
                "industry_macro_enhanced": {
                    field: treatment.get(field) for field in (
                        "case_id", "freeze_id", "report_artifact_ref", "company_evidence_package_ref",
                        "author_agent_id", "author_context_id", "frozen_at",
                        "industry_mechanism_refs", "macro_scenario_refs",
                    )
                },
                "blind_packets": packets,
            }
            existing_binding = report_pair_bindings.get(report_pair_id)
            if existing_binding is not None and existing_binding != report_binding:
                invalid.append(prefix + ":report_pair_binding_mismatch:" + report_pair_id)
            report_pair_bindings[report_pair_id] = report_binding

    for report_pair_id, count in sorted(report_pair_unit_counts.items()):
        if count < 3 or count > 5:
            invalid.append(
                "report_pair_material_judgment_count_out_of_range:"
                f"{report_pair_id}:count={count};required=3-5"
            )

    unseen_company_clusters = holdout_coverage["UNSEEN_COMPANY"]["company_clusters"]
    unseen_time_clusters = holdout_coverage["UNSEEN_TIME"]["company_clusters"]
    overlap = sorted(unseen_company_clusters.intersection(unseen_time_clusters))
    if overlap:
        invalid.append("dual_holdout_company_clusters_must_be_disjoint:" + ",".join(overlap))

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    return {
        "state": "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "holdout_coverage": {
            axis: {
                "units": int(holdout_coverage[axis]["units"]),
                "independent_company_clusters": sorted(holdout_coverage[axis]["company_clusters"]),
            }
            for axis in sorted(HOLDOUT_AXES)
        },
    }


def prepare_architecture_experiment_plan(
    plan: dict[str, Any], *, preregistered_at: str,
) -> dict[str, Any]:
    """Attach the immutable preregistration receipt to a plan."""
    payload = deepcopy(plan)
    payload["schema_version"] = PLAN_SCHEMA_VERSION
    payload["freeze"] = {
        "frozen": True, "preregistered_at": preregistered_at, "fingerprint": "",
    }
    payload["freeze"]["fingerprint"] = architecture_experiment_plan_fingerprint(payload)
    return payload


def freeze_architecture_experiment_plan(
    plan: dict[str, Any], *, preregistered_at: str,
) -> dict[str, Any]:
    """Freeze only a complete plan whose arm identities and isolation are reviewable."""
    payload = prepare_architecture_experiment_plan(plan, preregistered_at=preregistered_at)
    validation = validate_architecture_experiment_plan(payload)
    if validation["state"] != "REVIEWABLE":
        raise ArchitectureExperimentError(
            "plan_not_reviewable:" + ",".join(
                validation["invalid_findings"] + validation["incomplete_findings"]
            )
        )
    return payload


def _report_pair_index(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    for unit in plan.get("paired_units") or []:
        if not isinstance(unit, dict):
            continue
        report_pair_id = str(unit.get("report_pair_id") or "")
        if report_pair_id and report_pair_id not in pairs:
            pairs[report_pair_id] = unit
    return pairs


def _blind_leaks_arm_identity(review: dict[str, Any], unit: dict[str, Any]) -> bool:
    serialized = json.dumps(review, ensure_ascii=False, sort_keys=True)
    forbidden_values = set(ARM_CONDITIONS)
    for arm in (unit.get("arms") or {}).values():
        if not isinstance(arm, dict):
            continue
        forbidden_values.update(
            str(arm.get(field) or "")
            for field in (
                "case_id", "freeze_id", "claim_id", "forward_judgment_id", "report_artifact_ref",
                "author_agent_id", "author_context_id",
            )
        )
    return any(value and value in serialized for value in forbidden_values)


def derive_blind_quality_result(
    plan: dict[str, Any], review: dict[str, Any], unblinding: dict[str, Any],
) -> dict[str, Any]:
    """Unblind a completed report-quality review without reading operating outcomes."""
    plan_validation = validate_architecture_experiment_plan(plan)
    if plan_validation["state"] != "REVIEWABLE":
        raise ArchitectureExperimentError("plan_not_reviewable")
    if not isinstance(review, dict) or review.get("schema_version") != BLIND_REVIEW_SCHEMA_VERSION:
        raise ArchitectureExperimentError("blind_review_schema_invalid")
    if not isinstance(unblinding, dict) or unblinding.get("schema_version") != UNBLINDING_SCHEMA_VERSION:
        raise ArchitectureExperimentError("unblinding_schema_invalid")
    expected_review_fields = {
        "schema_version", "experiment_id", "report_pair_id", "review_id", "reviewer_id",
        "reviewer_context_id", "submitted_at", "independence", "blind_assessments",
        "pre_unblinding_verdict",
    }
    if set(review) != expected_review_fields:
        raise ArchitectureExperimentError("blind_review_fields_invalid")
    expected_unblinding_fields = {
        "schema_version", "experiment_id", "report_pair_id", "review_id", "unblinded_at", "mapping",
    }
    if set(unblinding) != expected_unblinding_fields:
        raise ArchitectureExperimentError("unblinding_fields_invalid")
    experiment_id = str(plan.get("experiment_id") or "")
    if review.get("experiment_id") != experiment_id or unblinding.get("experiment_id") != experiment_id:
        raise ArchitectureExperimentError("experiment_id_mismatch")
    report_pair_id = str(review.get("report_pair_id") or "")
    if unblinding.get("report_pair_id") != report_pair_id:
        raise ArchitectureExperimentError("report_pair_id_mismatch")
    unit = _report_pair_index(plan).get(report_pair_id)
    if unit is None:
        raise ArchitectureExperimentError("report_pair_not_in_plan")
    review_id = str(review.get("review_id") or "")
    if not review_id or unblinding.get("review_id") != review_id:
        raise ArchitectureExperimentError("review_id_missing_or_mismatch")
    submitted_at = _instant(review.get("submitted_at"))
    unblinded_at = _instant(unblinding.get("unblinded_at"))
    if submitted_at is None or unblinded_at is None or unblinded_at <= submitted_at:
        raise ArchitectureExperimentError("unblinding_must_follow_review_submission")
    independence = review.get("independence")
    required_independence = {
        "did_not_author_either_arm": True,
        "had_no_arm_mapping_before_submission": True,
        "no_outcome_seen": True,
        "reviewer_context_isolated": True,
    }
    if not isinstance(independence, dict) or set(independence) != set(required_independence) or any(
        independence.get(field) is not expected for field, expected in required_independence.items()
    ):
        raise ArchitectureExperimentError("blind_review_independence_invalid")
    reviewer_id = str(review.get("reviewer_id") or "")
    reviewer_context_id = str(review.get("reviewer_context_id") or "")
    if not reviewer_id or not reviewer_context_id:
        raise ArchitectureExperimentError("blind_reviewer_identity_missing")
    for arm in (unit.get("arms") or {}).values():
        if isinstance(arm, dict) and (
            reviewer_id == arm.get("author_agent_id")
            or reviewer_context_id == arm.get("author_context_id")
        ):
            raise ArchitectureExperimentError("blind_reviewer_not_disjoint_from_arm_author")
    if _blind_leaks_arm_identity(review, unit):
        raise ArchitectureExperimentError("blind_review_contains_arm_identity")

    assessments = review.get("blind_assessments")
    packets = unit.get("blind_packets") or {}
    if not isinstance(assessments, dict) or set(assessments) != {"BLIND_A", "BLIND_B"}:
        raise ArchitectureExperimentError("blind_assessments_must_cover_a_and_b")
    expected_packet_refs = {
        "BLIND_A": packets.get("blind_a_packet_ref"),
        "BLIND_B": packets.get("blind_b_packet_ref"),
    }
    for label, expected_packet_ref in expected_packet_refs.items():
        assessment = assessments.get(label)
        if not isinstance(assessment, dict):
            raise ArchitectureExperimentError("blind_assessment_invalid:" + label)
        if set(assessment) != {"packet_ref", "golden_standard_status", "material_findings"}:
            raise ArchitectureExperimentError("blind_assessment_fields_invalid:" + label)
        if assessment.get("packet_ref") != expected_packet_ref:
            raise ArchitectureExperimentError("blind_packet_ref_mismatch:" + label)
        if assessment.get("golden_standard_status") != "MEETS_GOLDEN_STANDARD":
            raise ArchitectureExperimentError("both_arms_must_meet_golden_standard")
        findings = assessment.get("material_findings")
        if not isinstance(findings, list) or not findings or any(_missing_text(item) for item in findings):
            raise ArchitectureExperimentError("blind_material_findings_invalid:" + label)

    mapping = unblinding.get("mapping")
    if not isinstance(mapping, dict) or set(mapping) != {"BLIND_A", "BLIND_B"}:
        raise ArchitectureExperimentError("unblinding_mapping_must_cover_a_and_b")
    mapped_conditions: set[str] = set()
    treatment_label = ""
    for label, mapped in mapping.items():
        if not isinstance(mapped, dict) or set(mapped) != {"condition", "report_artifact_ref"}:
            raise ArchitectureExperimentError("unblinding_mapping_invalid:" + label)
        condition = str(mapped.get("condition") or "")
        if condition not in ARM_CONDITIONS or condition in mapped_conditions:
            raise ArchitectureExperimentError("unblinding_condition_mapping_not_bijective")
        mapped_conditions.add(condition)
        arm_key = "company_only" if condition == "COMPANY_ONLY" else "industry_macro_enhanced"
        arm = (unit.get("arms") or {}).get(arm_key) or {}
        if mapped.get("report_artifact_ref") != arm.get("report_artifact_ref"):
            raise ArchitectureExperimentError("unblinding_report_ref_mismatch:" + label)
        if condition == "INDUSTRY_MACRO_ENHANCED":
            treatment_label = label

    verdict = review.get("pre_unblinding_verdict")
    if not isinstance(verdict, dict) or set(verdict) != {"preferred_packet", "material_difference", "basis"}:
        raise ArchitectureExperimentError("pre_unblinding_verdict_invalid")
    preferred = str(verdict.get("preferred_packet") or "")
    if preferred not in {"BLIND_A", "BLIND_B", "NO_MATERIAL_DIFFERENCE"}:
        raise ArchitectureExperimentError("preferred_packet_invalid")
    if not isinstance(verdict.get("material_difference"), bool) or _missing_text(verdict.get("basis")):
        raise ArchitectureExperimentError("pre_unblinding_verdict_incomplete")
    material = bool(verdict.get("material_difference"))
    if preferred == "NO_MATERIAL_DIFFERENCE" and material:
        raise ArchitectureExperimentError("no_material_difference_verdict_cannot_be_material")
    if not material or preferred == "NO_MATERIAL_DIFFERENCE":
        quality_result = "NO_MATERIAL_GAIN"
    elif preferred == treatment_label:
        quality_result = "MATERIAL_IMPROVEMENT"
    else:
        quality_result = "WORSE"
    return {
        "schema_version": QUALITY_RESULT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "report_pair_id": report_pair_id,
        "review_id": review_id,
        "reviewer_id": reviewer_id,
        "quality_result": quality_result,
        "unblinded_at": unblinding.get("unblinded_at"),
        "interpretation_boundary": (
            "Blind report-quality comparison only. This result does not settle the frozen operating "
            "judgments and cannot override their later official outcomes."
        ),
    }


def _planned_feedback_cards(
    plan: dict[str, Any], feedbacks: list[dict[str, Any]],
) -> dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]]:
    available: dict[tuple[str, str, str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for feedback in feedbacks:
        if not isinstance(feedback, dict) or feedback.get("schema_version") != "judgment-feedback-card.v2":
            raise ArchitectureExperimentError("feedback_schema_invalid")
        if feedback.get("investment_return") not in {None, "SEPARATE_NOT_INCLUDED"}:
            raise ArchitectureExperimentError("feedback_investment_return_must_remain_separate")
        case_id = str(feedback.get("case_id") or "")
        freeze_id = str(feedback.get("freeze_id") or "")
        for card in feedback.get("cards") or []:
            if not isinstance(card, dict):
                continue
            key = (
                case_id, freeze_id, str(card.get("claim_id") or ""),
                str(card.get("forward_judgment_id") or ""),
            )
            if key in available:
                raise ArchitectureExperimentError("duplicate_feedback_card_for_arm_identity")
            available[key] = (feedback, card)
    planned: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for unit in plan.get("paired_units") or []:
        unit_id = str(unit.get("paired_unit_id") or "")
        for arm_key in ("company_only", "industry_macro_enhanced"):
            arm = (unit.get("arms") or {}).get(arm_key) or {}
            key = (
                str(arm.get("case_id") or ""), str(arm.get("freeze_id") or ""),
                str(arm.get("claim_id") or ""), str(arm.get("forward_judgment_id") or ""),
            )
            if key not in available:
                raise ArchitectureExperimentError(
                    "planned_feedback_card_missing:" + unit_id + ":" + arm_key
                )
            planned[(unit_id, arm_key)] = available[key]
    return planned


def _arm_outcome(
    unit: dict[str, Any], feedback: dict[str, Any], card: dict[str, Any], *, arm_key: str,
) -> dict[str, Any]:
    unit_id = str(unit.get("paired_unit_id") or "")
    settlement_status = str(card.get("settlement_status") or "")
    judgment = card.get("judgment_outcome") if isinstance(card.get("judgment_outcome"), dict) else {}
    selection = card.get("selection_learning") if isinstance(card.get("selection_learning"), dict) else {}
    observation = card.get("actual_observation") if isinstance(card.get("actual_observation"), dict) else None
    increment = str(card.get("increment_vs_baseline") or "")
    if increment not in INCREMENT_OUTCOMES:
        raise ArchitectureExperimentError("increment_vs_baseline_invalid:" + unit_id + ":" + arm_key)
    if (
        selection.get("reason_code") == "MEASUREMENT_MISMATCH"
        or (observation or {}).get("comparability_status") in NONCOMPARABLE_OBSERVATION_STATES
    ):
        return {
            "state": "NOT_COMPARABLE", "met": None, "settlement_id": feedback.get("settlement_id"),
            "increment_vs_baseline": increment, "observation": observation,
        }
    if settlement_status != "CALCULATED" or judgment.get("status") == "NOT_EVALUATED":
        return {
            "state": "PENDING", "met": None, "settlement_id": feedback.get("settlement_id"),
            "increment_vs_baseline": increment, "observation": None,
        }
    status = str(judgment.get("status") or "")
    if status in SATISFIED_OUTCOMES:
        met: bool | None = True
    elif status in MISSED_OUTCOMES:
        met = False
    else:
        raise ArchitectureExperimentError("judgment_outcome_invalid:" + unit_id + ":" + arm_key)
    expected_baseline_id = str(((unit.get("outcome_contract") or {}).get("simple_baseline") or {}).get("baseline_id") or "")
    baseline = card.get("baseline") if isinstance(card.get("baseline"), dict) else {}
    if baseline.get("baseline_id") != expected_baseline_id:
        raise ArchitectureExperimentError("baseline_id_mismatch:" + unit_id + ":" + arm_key)
    expected_baseline = ((unit.get("outcome_contract") or {}).get("simple_baseline") or {})
    if baseline.get("method") != expected_baseline.get("method"):
        raise ArchitectureExperimentError("baseline_method_mismatch:" + unit_id + ":" + arm_key)
    if baseline.get("prediction") != expected_baseline.get("prediction"):
        raise ArchitectureExperimentError("baseline_prediction_mismatch:" + unit_id + ":" + arm_key)
    if observation is None:
        raise ArchitectureExperimentError("calculated_arm_missing_actual_observation:" + unit_id + ":" + arm_key)
    expected_observation = ((unit.get("outcome_contract") or {}).get("outcome_observation_identity") or {})
    for field in ("observation_id", "metric", "unit"):
        if observation.get(field) != expected_observation.get(field):
            raise ArchitectureExperimentError(
                "outcome_observation_identity_mismatch:" + unit_id + ":" + arm_key + ":" + field
            )
    return {
        "state": "SETTLED", "met": met, "settlement_id": feedback.get("settlement_id"),
        "increment_vs_baseline": increment, "observation": observation,
    }


def _paired_result(control: dict[str, Any], treatment: dict[str, Any]) -> str:
    if "PENDING" in {control["state"], treatment["state"]}:
        return "PENDING"
    if "NOT_COMPARABLE" in {control["state"], treatment["state"]}:
        return "NOT_COMPARABLE"
    if treatment["met"] and not control["met"]:
        return "ENHANCED_ONLY_MET"
    if control["met"] and not treatment["met"]:
        return "COMPANY_ONLY_ONLY_MET"
    if control["met"] and treatment["met"]:
        return "BOTH_MET"
    return "BOTH_MISSED"


def aggregate_architecture_experiment(
    plan: dict[str, Any], feedbacks: list[dict[str, Any]], *,
    quality_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare all frozen pairs while retaining pending and non-comparable units."""
    validation = validate_architecture_experiment_plan(plan)
    if validation["state"] != "REVIEWABLE":
        raise ArchitectureExperimentError(
            "plan_not_reviewable:" + ",".join(
                validation["invalid_findings"] + validation["incomplete_findings"]
            )
        )
    planned = _planned_feedback_cards(plan, feedbacks)
    quality_by_report_pair: dict[str, dict[str, Any]] = {}
    for result in quality_results or []:
        if not isinstance(result, dict) or result.get("schema_version") != QUALITY_RESULT_SCHEMA_VERSION:
            raise ArchitectureExperimentError("quality_result_schema_invalid")
        if set(result) != {
            "schema_version", "experiment_id", "report_pair_id", "review_id", "reviewer_id",
            "quality_result", "unblinded_at", "interpretation_boundary",
        }:
            raise ArchitectureExperimentError("quality_result_fields_invalid")
        if result.get("experiment_id") != plan.get("experiment_id"):
            raise ArchitectureExperimentError("quality_result_experiment_id_mismatch")
        report_pair_id = str(result.get("report_pair_id") or "")
        if report_pair_id not in _report_pair_index(plan):
            raise ArchitectureExperimentError("quality_result_report_pair_not_in_plan:" + report_pair_id)
        if report_pair_id in quality_by_report_pair:
            raise ArchitectureExperimentError("quality_result_duplicate:" + report_pair_id)
        if result.get("quality_result") not in QUALITY_RESULTS:
            raise ArchitectureExperimentError("quality_result_invalid:" + report_pair_id)
        quality_by_report_pair[report_pair_id] = result

    rows: list[dict[str, Any]] = []
    outcome_counts = {outcome: 0 for outcome in sorted(PAIR_OUTCOMES)}
    increment_counts = {
        condition: {outcome: 0 for outcome in sorted(INCREMENT_OUTCOMES)}
        for condition in sorted(ARM_CONDITIONS)
    }
    holdout_rows: dict[str, list[dict[str, Any]]] = {axis: [] for axis in HOLDOUT_AXES}
    for unit in plan.get("paired_units") or []:
        unit_id = str(unit.get("paired_unit_id") or "")
        control_feedback, control_card = planned[(unit_id, "company_only")]
        treatment_feedback, treatment_card = planned[(unit_id, "industry_macro_enhanced")]
        control = _arm_outcome(
            unit, control_feedback, control_card, arm_key="company_only",
        )
        treatment = _arm_outcome(
            unit, treatment_feedback, treatment_card, arm_key="industry_macro_enhanced",
        )
        if control["state"] == treatment["state"] == "SETTLED":
            observation_fields = ("observation_id", "metric", "value", "unit", "comparability_status")
            if any(
                (control["observation"] or {}).get(field) != (treatment["observation"] or {}).get(field)
                for field in observation_fields
            ) or sorted((control["observation"] or {}).get("source_ids") or []) != sorted(
                (treatment["observation"] or {}).get("source_ids") or []
            ):
                raise ArchitectureExperimentError("paired_outcome_observation_mismatch:" + unit_id)
        pair_result = _paired_result(control, treatment)
        outcome_counts[pair_result] += 1
        increment_counts["COMPANY_ONLY"][control["increment_vs_baseline"]] += 1
        increment_counts["INDUSTRY_MACRO_ENHANCED"][treatment["increment_vs_baseline"]] += 1
        row = {
            "paired_unit_id": unit_id,
            "report_pair_id": unit.get("report_pair_id"),
            "company_cluster_id": unit.get("company_cluster_id"),
            "period_cluster_id": unit.get("period_cluster_id"),
            "holdout_axis": unit.get("holdout_axis"),
            "material_judgment_object": unit.get("material_judgment_object"),
            "operating_pair_result": pair_result,
            "arms": {
                "COMPANY_ONLY": {
                    "settlement_state": control["state"],
                    "met": control["met"],
                    "increment_vs_baseline": control["increment_vs_baseline"],
                    "settlement_id": control["settlement_id"],
                },
                "INDUSTRY_MACRO_ENHANCED": {
                    "settlement_state": treatment["state"],
                    "met": treatment["met"],
                    "increment_vs_baseline": treatment["increment_vs_baseline"],
                    "settlement_id": treatment["settlement_id"],
                },
            },
            "blind_quality_result": (
                (quality_by_report_pair.get(str(unit.get("report_pair_id") or "")) or {}).get("quality_result")
                or "NOT_REVIEWED"
            ),
        }
        rows.append(row)
        holdout_rows[str(unit.get("holdout_axis"))].append(row)

    comparable_outcomes = {
        "ENHANCED_ONLY_MET", "COMPANY_ONLY_ONLY_MET", "BOTH_MET", "BOTH_MISSED",
    }
    holdout_coverage: dict[str, dict[str, Any]] = {}
    for axis in sorted(HOLDOUT_AXES):
        axis_rows = holdout_rows[axis]
        comparable = [row for row in axis_rows if row["operating_pair_result"] in comparable_outcomes]
        holdout_coverage[axis] = {
            "planned_units": len(axis_rows),
            "resolved_units": sum(row["operating_pair_result"] != "PENDING" for row in axis_rows),
            "comparable_units": len(comparable),
            "independent_company_clusters": sorted({
                str(row["company_cluster_id"]) for row in comparable
            }),
        }
    readiness = plan["readiness_contract"]
    comparable_rows = [row for row in rows if row["operating_pair_result"] in comparable_outcomes]
    if any(row["operating_pair_result"] == "PENDING" for row in rows):
        state = "PENDING_FROZEN_OUTCOMES"
    elif (
        len(holdout_coverage["UNSEEN_COMPANY"]["independent_company_clusters"])
        >= int(readiness["minimum_unseen_company_clusters"])
        and len(holdout_coverage["UNSEEN_TIME"]["independent_company_clusters"])
        >= int(readiness["minimum_unseen_time_company_clusters"])
    ):
        state = "DUAL_HOLDOUT_COMPARISON_READY"
    elif len({str(row["company_cluster_id"]) for row in comparable_rows}) >= int(
        readiness["minimum_independent_company_clusters_for_domain_comparison"]
    ):
        state = "DOMAIN_COMPARISON_READY"
    else:
        state = "PILOT_DESCRIPTIVE_ONLY"

    quality_counts = {result: 0 for result in sorted(QUALITY_RESULTS)}
    for result in quality_by_report_pair.values():
        quality_counts[str(result["quality_result"])] += 1
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "experiment_id": plan.get("experiment_id"),
        "state": state,
        "investment_return": "SEPARATE_NOT_INCLUDED",
        "method_claim": "NOT_ESTABLISHED_REQUIRES_INDEPENDENT_REVIEW",
        "interpretation_boundary": (
            "Paired counts describe frozen non-price operating judgments. They are not a win rate, "
            "probability, score, or general-superiority claim. DUAL_HOLDOUT_COMPARISON_READY only "
            "permits an independent method review."
        ),
        "quality_outcome_separation": (
            "Blind report quality is reported separately and never overwrites operating settlement."
        ),
        "cohort_accounting": {
            "paired_judgment_units": len(rows),
            "resolved_units": sum(row["operating_pair_result"] != "PENDING" for row in rows),
            "comparable_units": len(comparable_rows),
            "independent_company_clusters": sorted({str(row["company_cluster_id"]) for row in rows}),
            "operating_pair_result_counts": outcome_counts,
            "increment_vs_simple_baseline_counts": increment_counts,
            "holdout_coverage": holdout_coverage,
        },
        "blind_quality_review": {
            "planned_report_pairs": len(_report_pair_index(plan)),
            "reviewed_report_pairs": len(quality_by_report_pair),
            "quality_result_counts": quality_counts,
        },
        "paired_units": rows,
    }
