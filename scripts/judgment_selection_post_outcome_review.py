#!/usr/bin/env python3
"""Validate an append-only independent review of a settled selection episode.

This receipt is intentionally not a learning decision and has no database or
program-state side effect.  It only establishes whether a settled outcome may
be handed to a separate method-learning gate.  In particular, a mixed or
non-diagnostic settlement is recorded as a boundary, never converted into a
directional method result.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


REVIEW_SCHEMA_VERSION = "judgment-selection-post-outcome-review.v1"
VALIDATION_SCHEMA_VERSION = "judgment-selection-post-outcome-review-validation.v1"
FEEDBACK_SCHEMA_VERSION = "judgment-selection-feedback-card.v1"
OUTCOME_SCHEMA_VERSION = "judgment-selection-outcome.v1"

ROOT_CAUSE_CLASSES = {
    "DATA_COVERAGE",
    "ACQUISITION_MODULE",
    "REASONING",
    "MODEL",
    "WRITING",
}
REVIEW_STATUSES = {"INDEPENDENTLY_ACCEPTED_POST_OUTCOME", "REVISION_REQUIRED"}
REVIEW_VERDICTS = {
    "MIXED_MECHANISM_BOUNDARY",
    "NOT_DIAGNOSTIC_MEASUREMENT_BOUNDARY",
    "COMPARISON_RECORDED_PENDING_SEPARATE_LEARNING_REVIEW",
    "OUTCOME_REVIEW_REJECTED",
}
PROHIBITED_OUTPUTS = {
    "directionality",
    "directional_learning",
    "selection_direction",
    "selection_accuracy",
    "accuracy",
    "probability",
    "win_rate",
    "valuation",
    "target_price",
    "expected_return",
    "investment_return",
    "security_return",
    "portfolio_conclusion",
}
_FORBIDDEN_KEY_TOKENS = (
    "direction",
    "accuracy",
    "probability",
    "win_rate",
    "valuation",
    "target_price",
    "expected_return",
    "investment_return",
    "security_return",
    "portfolio_return",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _forbidden_key_paths(value: Any, *, path: str = "review") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if any(token in key_text for token in _FORBIDDEN_KEY_TOKENS):
                findings.append(child_path + ":prohibited_directionality_or_performance_output")
            findings.extend(_forbidden_key_paths(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_forbidden_key_paths(child, path=f"{path}[{index}]"))
    return findings


def _expected_review_verdict(joint_verdict: str) -> str | None:
    if joint_verdict == "MIXED":
        return "MIXED_MECHANISM_BOUNDARY"
    if joint_verdict == "NOT_DIAGNOSTIC":
        return "NOT_DIAGNOSTIC_MEASUREMENT_BOUNDARY"
    if joint_verdict in {"A_ONLY", "B_ONLY"}:
        return "COMPARISON_RECORDED_PENDING_SEPARATE_LEARNING_REVIEW"
    return None


def validate_selection_post_outcome_review(
    review: dict[str, Any], *, frozen_case: dict[str, Any], outcome: dict[str, Any],
    feedback: dict[str, Any], pre_outcome_review: dict[str, Any],
    resolution_amendment: dict[str, Any], outcome_ref: str | None = None,
    feedback_ref: str | None = None,
) -> dict[str, Any]:
    """Return a pure, side-effect-free validation receipt for a post-outcome review."""

    findings: list[str] = []
    if not isinstance(review, dict):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "state": "INVALID",
            "findings": ["review_not_object"],
        }
    if not all(isinstance(item, dict) for item in (
        frozen_case, outcome, feedback, pre_outcome_review, resolution_amendment,
    )):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "state": "INVALID",
            "findings": ["bound_artifact_not_object"],
        }

    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in (
        "review_id", "case_id", "freeze_id", "settlement_id", "outcome_ref", "feedback_ref",
        "reviewer_id", "economic_impact",
    ):
        if not _text(review.get(field)):
            findings.append(field + "_missing")
    if not _text(review.get("review_id")).startswith("JSELPOSTREVIEW:"):
        findings.append("review_id_invalid")

    if outcome.get("schema_version") != OUTCOME_SCHEMA_VERSION:
        findings.append("outcome_schema_invalid")
    if feedback.get("schema_version") != FEEDBACK_SCHEMA_VERSION:
        findings.append("feedback_schema_invalid")
    if frozen_case.get("case_id") != outcome.get("case_id") or outcome.get("case_id") != feedback.get("case_id"):
        findings.append("bound_case_identity_mismatch")
    if frozen_case.get("freeze_id") != outcome.get("freeze_id") or outcome.get("freeze_id") != feedback.get("freeze_id"):
        findings.append("bound_freeze_identity_mismatch")
    if outcome.get("settlement_id") != feedback.get("settlement_id"):
        findings.append("bound_settlement_identity_mismatch")
    for field, bound in (
        ("case_id", outcome.get("case_id")),
        ("freeze_id", outcome.get("freeze_id")),
        ("settlement_id", outcome.get("settlement_id")),
    ):
        if review.get(field) != bound:
            findings.append("review_" + field + "_mismatch")
    if outcome_ref is not None and review.get("outcome_ref") != outcome_ref:
        findings.append("outcome_ref_mismatch")
    if feedback_ref is not None and review.get("feedback_ref") != feedback_ref:
        findings.append("feedback_ref_mismatch")

    reviewed_at = _time(review.get("reviewed_at"))
    recorded_at = _time(review.get("recorded_at"))
    settlement_at = _time(outcome.get("settlement_as_of"))
    if reviewed_at is None:
        findings.append("reviewed_at_invalid")
    elif settlement_at is None or reviewed_at < settlement_at:
        findings.append("reviewed_before_settlement")
    if recorded_at is None:
        findings.append("recorded_at_invalid")
    elif reviewed_at is not None and recorded_at < reviewed_at:
        findings.append("recorded_before_review")

    reviewer_id = _text(review.get("reviewer_id"))
    role_ids = {
        _text(resolution_amendment.get("selector_id")),
        _text(pre_outcome_review.get("reviewer_id")),
        _text(resolution_amendment.get("author_id")),
        _text(outcome.get("custodian_id")),
    }
    role_ids.discard("")
    if not reviewer_id or reviewer_id in role_ids:
        findings.append("post_outcome_reviewer_not_independent")
    attestation = review.get("independence_attestation")
    if not isinstance(attestation, dict) or attestation.get("independent") is not True:
        findings.append("independence_attestation_invalid")
    else:
        excluded = attestation.get("excluded_role_ids")
        if not isinstance(excluded, list) or set(excluded) != role_ids or len(excluded) != len(role_ids):
            findings.append("independence_attestation_role_set_mismatch")

    joint = feedback.get("joint_comparison")
    feedback_joint_verdict = joint.get("overall_verdict") if isinstance(joint, dict) else None
    review_joint_verdict = review.get("joint_selection_verdict")
    if feedback_joint_verdict not in {"A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"}:
        findings.append("feedback_joint_selection_verdict_invalid")
    if review_joint_verdict != feedback_joint_verdict:
        findings.append("review_joint_selection_verdict_mismatch")
    review_status = review.get("review_status")
    review_verdict = review.get("review_verdict")
    if review_status not in REVIEW_STATUSES:
        findings.append("review_status_invalid")
    if review_verdict not in REVIEW_VERDICTS:
        findings.append("review_verdict_invalid")
    expected = _expected_review_verdict(_text(feedback_joint_verdict))
    if review_status == "INDEPENDENTLY_ACCEPTED_POST_OUTCOME" and review_verdict != expected:
        findings.append("accepted_review_verdict_must_preserve_joint_boundary")
    if review_status == "REVISION_REQUIRED" and review_verdict != "OUTCOME_REVIEW_REJECTED":
        findings.append("revision_required_verdict_invalid")
    if review.get("learning_authorization") != "NONE":
        findings.append("learning_authorization_must_remain_none")

    root_causes = review.get("root_cause_classes")
    if not isinstance(root_causes, list) or not root_causes or any(item not in ROOT_CAUSE_CLASSES for item in root_causes):
        findings.append("root_cause_classes_invalid")
    elif len(set(root_causes)) != len(root_causes):
        findings.append("root_cause_classes_duplicate")
    for field in ("missing_facts", "prohibited_assumptions", "executable_remediation", "acceptance_criteria"):
        values = review.get(field)
        if not isinstance(values, list) or (field != "missing_facts" and not values) or not all(_text(value) for value in values):
            findings.append(field + "_invalid")

    prohibited = review.get("prohibited_outputs")
    if not isinstance(prohibited, list) or set(prohibited) != PROHIBITED_OUTPUTS or len(prohibited) != len(PROHIBITED_OUTPUTS):
        findings.append("prohibited_outputs_must_match_contract")
    findings.extend(_forbidden_key_paths(review))

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "INVALID" if findings else "REVIEWABLE",
        "findings": findings,
    }
