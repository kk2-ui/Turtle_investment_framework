from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.judgment_selection_post_outcome_review import (
    PROHIBITED_OUTPUTS,
    REVIEW_SCHEMA_VERSION,
    validate_selection_post_outcome_review,
)


def _bound_artifacts(joint_verdict: str = "MIXED") -> tuple[dict, dict, dict, dict, dict]:
    case = {"case_id": "SELECTIONCASE:SYNTHETIC:R104", "freeze_id": "JFREEZE:SYNTHETIC:R104"}
    outcome = {
        "schema_version": "judgment-selection-outcome.v1",
        "case_id": case["case_id"],
        "freeze_id": case["freeze_id"],
        "settlement_id": "JSELOUTCOME:SYNTHETIC:R104:V1",
        "settlement_as_of": "2026-08-24T02:59:25+00:00",
        "custodian_id": "synthetic-outcome-custodian",
    }
    feedback = {
        "schema_version": "judgment-selection-feedback-card.v1",
        "case_id": case["case_id"],
        "freeze_id": case["freeze_id"],
        "settlement_id": outcome["settlement_id"],
        "joint_comparison": {"overall_verdict": joint_verdict},
    }
    pre_outcome_review = {"reviewer_id": "synthetic-pre-outcome-reviewer"}
    amendment = {
        "selector_id": "synthetic-selector",
        "author_id": "synthetic-amendment-author",
    }
    return case, outcome, feedback, pre_outcome_review, amendment


def _review(joint_verdict: str = "MIXED") -> dict:
    _, outcome, _, pre_review, amendment = _bound_artifacts(joint_verdict)
    expected = {
        "MIXED": "MIXED_MECHANISM_BOUNDARY",
        "NOT_DIAGNOSTIC": "NOT_DIAGNOSTIC_MEASUREMENT_BOUNDARY",
        "A_ONLY": "COMPARISON_RECORDED_PENDING_SEPARATE_LEARNING_REVIEW",
        "B_ONLY": "COMPARISON_RECORDED_PENDING_SEPARATE_LEARNING_REVIEW",
    }[joint_verdict]
    excluded = [
        amendment["selector_id"], pre_review["reviewer_id"], amendment["author_id"], outcome["custodian_id"],
    ]
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_id": "JSELPOSTREVIEW:SYNTHETIC:R104:V1",
        "case_id": "SELECTIONCASE:SYNTHETIC:R104",
        "freeze_id": "JFREEZE:SYNTHETIC:R104",
        "settlement_id": outcome["settlement_id"],
        "outcome_ref": "10_independent_outcome.json",
        "feedback_ref": "selection_feedback/feedback.json",
        "reviewer_id": "synthetic-independent-post-outcome-reviewer",
        "reviewed_at": "2026-08-24T03:10:00+00:00",
        "recorded_at": "2026-08-24T03:11:00+00:00",
        "review_status": "INDEPENDENTLY_ACCEPTED_POST_OUTCOME",
        "joint_selection_verdict": joint_verdict,
        "review_verdict": expected,
        "learning_authorization": "NONE",
        "root_cause_classes": ["REASONING"],
        "economic_impact": "No claim of a method win is permitted from a single settled episode.",
        "missing_facts": ["No maintenance-capex bridge is available for the continuous D5 reading."],
        "prohibited_assumptions": ["Do not let the D3 result override the contrary D4 result."],
        "executable_remediation": ["Route any later method change through a separate learning gate."],
        "acceptance_criteria": ["Keep the joint verdict and learning_authorization NONE unchanged."],
        "independence_attestation": {"independent": True, "excluded_role_ids": excluded},
        "prohibited_outputs": sorted(PROHIBITED_OUTPUTS),
    }


def _validate(review: dict, joint_verdict: str = "MIXED") -> dict:
    case, outcome, feedback, pre_review, amendment = _bound_artifacts(joint_verdict)
    return validate_selection_post_outcome_review(
        review,
        frozen_case=case,
        outcome=outcome,
        feedback=feedback,
        pre_outcome_review=pre_review,
        resolution_amendment=amendment,
        outcome_ref="10_independent_outcome.json",
        feedback_ref="selection_feedback/feedback.json",
    )


def test_mixed_post_outcome_review_preserves_the_mechanism_boundary() -> None:
    assert _validate(_review()) == {
        "schema_version": "judgment-selection-post-outcome-review-validation.v1",
        "state": "REVIEWABLE",
        "findings": [],
    }


@pytest.mark.parametrize(
    ("joint_verdict", "review_verdict"),
    [
        ("NOT_DIAGNOSTIC", "NOT_DIAGNOSTIC_MEASUREMENT_BOUNDARY"),
        ("A_ONLY", "COMPARISON_RECORDED_PENDING_SEPARATE_LEARNING_REVIEW"),
        ("B_ONLY", "COMPARISON_RECORDED_PENDING_SEPARATE_LEARNING_REVIEW"),
    ],
)
def test_non_mixed_reviews_do_not_authorize_learning(
    joint_verdict: str, review_verdict: str,
) -> None:
    review = _review(joint_verdict)
    assert review["review_verdict"] == review_verdict
    assert _validate(review, joint_verdict)["state"] == "REVIEWABLE"


@pytest.mark.parametrize("role", [
    "synthetic-selector",
    "synthetic-pre-outcome-reviewer",
    "synthetic-amendment-author",
    "synthetic-outcome-custodian",
])
def test_reviewer_must_be_independent_from_all_outcome_roles(role: str) -> None:
    review = _review()
    review["reviewer_id"] = role

    assert "post_outcome_reviewer_not_independent" in _validate(review)["findings"]


@pytest.mark.parametrize("field", [
    "directionality",
    "selection_accuracy",
    "valuation",
    "investment_return",
])
def test_rejects_directionality_accuracy_valuation_and_return_fields(field: str) -> None:
    review = _review()
    review[field] = "forbidden"

    assert any(field in finding for finding in _validate(review)["findings"])


def test_rejects_learning_authorization_and_joint_verdict_rewrite() -> None:
    review = _review()
    review["learning_authorization"] = "DIRECTIONAL"
    review["joint_selection_verdict"] = "A_ONLY"

    findings = _validate(review)["findings"]
    assert "learning_authorization_must_remain_none" in findings
    assert "review_joint_selection_verdict_mismatch" in findings


def test_rejects_role_set_or_reference_mismatch() -> None:
    review = _review()
    review["independence_attestation"]["excluded_role_ids"].pop()
    review["feedback_ref"] = "other-feedback.json"

    findings = _validate(review)["findings"]
    assert "independence_attestation_role_set_mismatch" in findings
    assert "feedback_ref_mismatch" in findings


def test_rejects_accepted_mixed_review_that_relabels_the_boundary() -> None:
    review = _review()
    review["review_verdict"] = "COMPARISON_RECORDED_PENDING_SEPARATE_LEARNING_REVIEW"

    assert "accepted_review_verdict_must_preserve_joint_boundary" in _validate(review)["findings"]
