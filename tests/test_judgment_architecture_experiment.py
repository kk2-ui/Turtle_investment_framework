from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.judgment_architecture_experiment import (
    ArchitectureExperimentError,
    aggregate_architecture_experiment,
    derive_blind_quality_result,
    freeze_architecture_experiment_plan,
    prepare_architecture_experiment_plan,
    validate_architecture_experiment_plan,
)


def _arm(suffix: str, condition: str) -> dict:
    short = "control" if condition == "COMPANY_ONLY" else "enhanced"
    return {
        "condition": condition,
        "case_id": f"HBTCASE:{suffix}:{short}",
        "freeze_id": f"FREEZE:{suffix}:{short}",
        "claim_id": f"HBTCLM:{suffix}:{short}",
        "forward_judgment_id": f"FJ:{suffix}:{short}",
        "report_artifact_ref": f"reports/{suffix}/{short}.html",
        "company_evidence_package_ref": f"evidence/{suffix}/pit-package.json",
        "author_agent_id": f"author-{suffix}-{short}",
        "author_context_id": f"context-{suffix}-{short}",
        "frozen_at": "2026-08-20T08:00:00+00:00",
        "other_arm_access_before_freeze": False,
        "industry_mechanism_refs": [] if condition == "COMPANY_ONLY" else ["IKM:demand-reset"],
        "macro_scenario_refs": [],
    }


def _unit(
    suffix: str, holdout_axis: str, *, judgment: str = "owner-cash",
    material_object: str = "OWNER_CASH",
) -> dict:
    unit = {
        "paired_unit_id": "JAXUNIT:" + suffix + ":" + judgment,
        "report_pair_id": "JAXREPORT:" + suffix,
        "company_id": "COMPANY:" + suffix,
        "company_cluster_id": "CLUSTER:" + suffix,
        "period_cluster_id": "PERIOD:FY2026",
        "information_cutoff": "2026-08-19T23:59:59+00:00",
        "holdout_axis": holdout_axis,
        "material_judgment_object": material_object,
        "outcome_contract": {
            "outcome_target_id": "OUTCOME:" + suffix + ":" + judgment,
            "source_contract_ref": "contracts/official-filing-only.json",
            "measurement_contract_ref": "contracts/owner-cash.json",
            "outcome_not_before": "2027-03-31T00:00:00+00:00",
            "simple_baseline": {
                "baseline_id": "BASELINE:" + suffix + ":" + judgment,
                "method": "SAME_BASIS_CARRY_FORWARD",
                "prediction_ref": "predictions/" + suffix + "/" + judgment + "-baseline.json",
            },
        },
        "arms": {
            "company_only": _arm(suffix, "COMPANY_ONLY"),
            "industry_macro_enhanced": _arm(suffix, "INDUSTRY_MACRO_ENHANCED"),
        },
        "blind_packets": {
            "blind_a_packet_ref": "blind/" + suffix + "/a.md",
            "blind_b_packet_ref": "blind/" + suffix + "/b.md",
        },
    }
    for arm in unit["arms"].values():
        arm["claim_id"] += ":" + judgment
        arm["forward_judgment_id"] += ":" + judgment
    return unit


def _plan() -> dict:
    units = []
    for suffix, holdout_axis in (
        ("alpha", "UNSEEN_COMPANY"),
        ("bravo", "UNSEEN_COMPANY"),
        ("charlie", "UNSEEN_TIME"),
        ("delta", "UNSEEN_TIME"),
    ):
        units.extend([
            _unit(suffix, holdout_axis),
            _unit(
                suffix, holdout_axis, judgment="normalized-earnings",
                material_object="NORMALIZED_EARNINGS",
            ),
            _unit(
                suffix, holdout_axis, judgment="permanent-loss",
                material_object="PERMANENT_LOSS",
            ),
        ])
    return prepare_architecture_experiment_plan({
        "experiment_id": "JAX:paired-golden-research-v1",
        "protocol": {
            "comparison_unit": "PAIRED_MATERIAL_JUDGMENT",
            "control_condition": "COMPANY_ONLY",
            "treatment_condition": "INDUSTRY_MACRO_ENHANCED",
            "report_standard": "SAME_GOLDEN_STANDARD",
            "company_evidence": "SAME_CUTOFF_AND_PACKAGE",
            "arm_isolation": "FREEZE_BEFORE_CROSS_ARM_ACCESS",
            "quality_review": "BLIND_SEPARATE_FROM_OUTCOME",
            "outcome_boundary": "NON_PRICE_OPERATING_ONLY",
            "retention": "RETAIN_ALL_PAIRED_UNITS_AND_UNRESOLVED",
        },
        "readiness_contract": {
            "minimum_independent_company_clusters_for_domain_comparison": 2,
            "minimum_unseen_company_clusters": 2,
            "minimum_unseen_time_company_clusters": 2,
        },
        "paired_units": units,
    }, preregistered_at="2026-08-18T08:00:00+00:00")


def _feedback(unit: dict, arm_key: str, outcome: str, *, increment: str = "JUDGMENT_BETTER") -> dict:
    arm = unit["arms"][arm_key]
    pending = outcome == "PENDING"
    card = {
        "claim_id": arm["claim_id"],
        "forward_judgment_id": arm["forward_judgment_id"],
        "settlement_status": "PARTIAL" if pending else "CALCULATED",
        "judgment_outcome": {"status": "NOT_EVALUATED" if pending else outcome},
        "baseline": (
            {"status": "NOT_EVALUATED"}
            if pending
            else {"baseline_id": unit["outcome_contract"]["simple_baseline"]["baseline_id"]}
        ),
        "increment_vs_baseline": "NOT_EVALUATED" if pending else increment,
        "selection_learning": {
            "admission_status": "SELECTION_ADMITTED",
            "outcome": "NOT_EVALUATED" if pending else "SUPPORTS_SELECTED",
        },
        "actual_observation": (
            None
            if pending
            else {
                "observation_id": "OBS:" + unit["paired_unit_id"],
                "metric": "owner_cash",
                "value": 100.0,
                "unit": "CNYm",
                "source_ids": ["DOC:official-result"],
                "comparability_status": "COMPARABLE",
            }
        ),
    }
    return {
        "schema_version": "judgment-feedback-card.v2",
        "case_id": arm["case_id"],
        "freeze_id": arm["freeze_id"],
        "settlement_id": "SETTLEMENT:" + unit["paired_unit_id"] + ":" + arm_key,
        "investment_return": "SEPARATE_NOT_INCLUDED",
        "cards": [card],
    }


def _all_feedbacks(plan: dict, outcomes: list[tuple[str, str]]) -> list[dict]:
    feedbacks = []
    for unit, (control, treatment) in zip(plan["paired_units"], outcomes, strict=True):
        feedbacks.append(_feedback(unit, "company_only", control))
        feedbacks.append(_feedback(unit, "industry_macro_enhanced", treatment))
    return feedbacks


def _blind_review(unit: dict) -> dict:
    return {
        "schema_version": "judgment-architecture-blind-review.v1",
        "experiment_id": "JAX:paired-golden-research-v1",
        "report_pair_id": unit["report_pair_id"],
        "review_id": "JAXREVIEW:" + unit["report_pair_id"],
        "reviewer_id": "blind-reviewer",
        "reviewer_context_id": "blind-review-context",
        "submitted_at": "2026-08-23T08:00:00+00:00",
        "independence": {
            "did_not_author_either_arm": True,
            "had_no_arm_mapping_before_submission": True,
            "no_outcome_seen": True,
            "reviewer_context_isolated": True,
        },
        "blind_assessments": {
            "BLIND_A": {
                "packet_ref": unit["blind_packets"]["blind_a_packet_ref"],
                "golden_standard_status": "MEETS_GOLDEN_STANDARD",
                "material_findings": ["The causal chain distinguishes the decisive operating alternatives."],
            },
            "BLIND_B": {
                "packet_ref": unit["blind_packets"]["blind_b_packet_ref"],
                "golden_standard_status": "MEETS_GOLDEN_STANDARD",
                "material_findings": ["The company evidence is complete but the boundary conditions are narrower."],
            },
        },
        "pre_unblinding_verdict": {
            "preferred_packet": "BLIND_A",
            "material_difference": True,
            "basis": "Blind A materially improves mechanism discrimination while preserving the same evidence boundary.",
        },
    }


def _unblinding(unit: dict) -> dict:
    return {
        "schema_version": "judgment-architecture-unblinding.v1",
        "experiment_id": "JAX:paired-golden-research-v1",
        "report_pair_id": unit["report_pair_id"],
        "review_id": "JAXREVIEW:" + unit["report_pair_id"],
        "unblinded_at": "2026-08-24T08:00:00+00:00",
        "mapping": {
            "BLIND_A": {
                "condition": "INDUSTRY_MACRO_ENHANCED",
                "report_artifact_ref": unit["arms"]["industry_macro_enhanced"]["report_artifact_ref"],
            },
            "BLIND_B": {
                "condition": "COMPANY_ONLY",
                "report_artifact_ref": unit["arms"]["company_only"]["report_artifact_ref"],
            },
        },
    }


def test_plan_preregisters_same_evidence_gold_standard_and_independent_frozen_arms() -> None:
    result = validate_architecture_experiment_plan(_plan())

    assert result["state"] == "REVIEWABLE"
    assert result["holdout_coverage"]["UNSEEN_COMPANY"]["units"] == 6
    assert result["holdout_coverage"]["UNSEEN_TIME"]["units"] == 6


def test_one_report_pair_can_carry_multiple_judgment_units_without_faking_quality_samples() -> None:
    plan = _plan()
    validation = validate_architecture_experiment_plan(plan)
    assert validation["state"] == "REVIEWABLE"

    quality = derive_blind_quality_result(
        plan, _blind_review(plan["paired_units"][0]), _unblinding(plan["paired_units"][0]),
    )
    feedbacks = _all_feedbacks(plan, [("MET", "MET")] * 12)
    result = aggregate_architecture_experiment(plan, feedbacks, quality_results=[quality])
    assert result["cohort_accounting"]["paired_judgment_units"] == 12
    assert result["blind_quality_review"]["planned_report_pairs"] == 4
    assert result["blind_quality_review"]["reviewed_report_pairs"] == 1


def test_plan_rejects_too_few_judgments_duplicate_targets_or_relabelled_reports() -> None:
    plan = _plan()
    plan["paired_units"] = [
        unit for unit in plan["paired_units"]
        if unit["report_pair_id"] != "JAXREPORT:alpha" or unit["material_judgment_object"] == "OWNER_CASH"
    ]
    plan = prepare_architecture_experiment_plan(plan, preregistered_at="2026-08-18T08:00:00+00:00")
    result = validate_architecture_experiment_plan(plan)
    assert (
        "report_pair_material_judgment_count_out_of_range:JAXREPORT:alpha:count=1;required=3-5"
        in result["invalid_findings"]
    )

    plan = _plan()
    plan["paired_units"][1]["outcome_contract"]["outcome_target_id"] = (
        plan["paired_units"][0]["outcome_contract"]["outcome_target_id"]
    )
    plan = prepare_architecture_experiment_plan(plan, preregistered_at="2026-08-18T08:00:00+00:00")
    result = validate_architecture_experiment_plan(plan)
    assert any("outcome_target_reused_within_report_pair" in item for item in result["invalid_findings"])

    plan = _plan()
    alpha = plan["paired_units"][0]
    for bravo in plan["paired_units"][3:6]:
        bravo["arms"]["company_only"]["case_id"] = alpha["arms"]["company_only"]["case_id"]
        bravo["arms"]["company_only"]["freeze_id"] = alpha["arms"]["company_only"]["freeze_id"]
        bravo["arms"]["company_only"]["report_artifact_ref"] = alpha["arms"]["company_only"]["report_artifact_ref"]
    plan = prepare_architecture_experiment_plan(plan, preregistered_at="2026-08-18T08:00:00+00:00")
    result = validate_architecture_experiment_plan(plan)
    assert any("reused_across_report_pairs" in item for item in result["invalid_findings"])


def test_plan_rejects_cross_arm_contamination_fake_independence_and_post_outcome_freeze() -> None:
    plan = _plan()
    unit = plan["paired_units"][0]
    unit["arms"]["company_only"]["industry_mechanism_refs"] = ["IKM:leaked"]
    unit["arms"]["industry_macro_enhanced"]["author_context_id"] = unit["arms"]["company_only"]["author_context_id"]
    unit["arms"]["industry_macro_enhanced"]["frozen_at"] = "2027-04-01T00:00:00+00:00"
    plan = prepare_architecture_experiment_plan(plan, preregistered_at="2026-08-18T08:00:00+00:00")

    result = validate_architecture_experiment_plan(plan)

    assert result["state"] == "INVALID"
    assert "paired_units[0]:arms:company_only:company_only_arm_contains_industry_or_macro_refs" in result["invalid_findings"]
    assert "paired_units[0]:arms:author_context_must_be_disjoint" in result["invalid_findings"]
    assert "paired_units[0]:arms:industry_macro_enhanced:arm_not_frozen_before_outcome_window" in result["invalid_findings"]


def test_freeze_refuses_a_plan_created_after_an_arm_was_already_frozen() -> None:
    draft = _plan()
    draft.pop("freeze")

    with pytest.raises(ArchitectureExperimentError, match="arm_frozen_before_preregistration"):
        freeze_architecture_experiment_plan(
            draft, preregistered_at="2026-08-21T08:00:00+00:00",
        )


def test_plan_fingerprint_rejects_removing_a_paired_holdout_unit_after_freeze() -> None:
    plan = _plan()
    plan["paired_units"].pop()

    result = validate_architecture_experiment_plan(plan)

    assert result["state"] == "INVALID"
    assert "freeze_fingerprint_mismatch" in result["invalid_findings"]

    plan = _plan()
    plan["freeze"]["preregistered_at"] = "2026-08-17T08:00:00+00:00"
    result = validate_architecture_experiment_plan(plan)
    assert "freeze_fingerprint_mismatch" in result["invalid_findings"]


def test_blind_quality_is_derived_only_after_submission_and_unblinding() -> None:
    plan = _plan()
    unit = plan["paired_units"][0]

    result = derive_blind_quality_result(plan, _blind_review(unit), _unblinding(unit))

    assert result["quality_result"] == "MATERIAL_IMPROVEMENT"
    assert "operating" in result["interpretation_boundary"]


def test_blind_review_rejects_an_author_reviewer_or_a_leaked_arm_identity() -> None:
    plan = _plan()
    unit = plan["paired_units"][0]
    review = _blind_review(unit)
    review["reviewer_id"] = unit["arms"]["company_only"]["author_agent_id"]
    with pytest.raises(ArchitectureExperimentError, match="reviewer_not_disjoint"):
        derive_blind_quality_result(plan, review, _unblinding(unit))

    review = _blind_review(unit)
    review["pre_unblinding_verdict"]["basis"] += " It appears to be COMPANY_ONLY."
    with pytest.raises(ArchitectureExperimentError, match="contains_arm_identity"):
        derive_blind_quality_result(plan, review, _unblinding(unit))


def test_blind_review_cannot_pass_a_below_gold_arm_or_unblind_before_submission() -> None:
    plan = _plan()
    unit = plan["paired_units"][0]
    review = _blind_review(unit)
    review["blind_assessments"]["BLIND_B"]["golden_standard_status"] = "BELOW_GOLDEN_STANDARD"
    with pytest.raises(ArchitectureExperimentError, match="both_arms_must_meet_golden_standard"):
        derive_blind_quality_result(plan, review, _unblinding(unit))

    unblinding = _unblinding(unit)
    unblinding["unblinded_at"] = review["submitted_at"]
    with pytest.raises(ArchitectureExperimentError, match="unblinding_must_follow"):
        derive_blind_quality_result(plan, _blind_review(unit), unblinding)


def test_aggregation_retains_all_pair_results_baselines_and_dual_holdout_coverage() -> None:
    plan = _plan()
    feedbacks = _all_feedbacks(plan, [
        *(("MISSED", "MET"),) * 3,
        *(("MET", "MISSED"),) * 3,
        *(("MET", "MET"),) * 3,
        *(("MISSED", "MISSED"),) * 3,
    ])
    quality = derive_blind_quality_result(
        plan, _blind_review(plan["paired_units"][0]), _unblinding(plan["paired_units"][0]),
    )

    result = aggregate_architecture_experiment(plan, feedbacks, quality_results=[quality])

    assert result["state"] == "DUAL_HOLDOUT_COMPARISON_READY"
    counts = result["cohort_accounting"]["operating_pair_result_counts"]
    assert counts["ENHANCED_ONLY_MET"] == 3
    assert counts["COMPANY_ONLY_ONLY_MET"] == 3
    assert counts["BOTH_MET"] == 3
    assert counts["BOTH_MISSED"] == 3
    assert result["cohort_accounting"]["paired_judgment_units"] == 12
    assert result["blind_quality_review"]["quality_result_counts"]["MATERIAL_IMPROVEMENT"] == 1
    assert result["blind_quality_review"]["reviewed_report_pairs"] == 1
    assert result["method_claim"] == "NOT_ESTABLISHED_REQUIRES_INDEPENDENT_REVIEW"
    assert "score" in result["interpretation_boundary"]
    assert "win_rate" not in result


def test_aggregation_keeps_pending_and_not_comparable_pairs_in_the_denominator() -> None:
    plan = _plan()
    feedbacks = _all_feedbacks(plan, [
        ("PENDING", "PENDING"), *(("MET", "MET"),) * 11,
    ])
    result = aggregate_architecture_experiment(plan, feedbacks)
    assert result["state"] == "PENDING_FROZEN_OUTCOMES"
    assert result["cohort_accounting"]["operating_pair_result_counts"]["PENDING"] == 1
    assert result["cohort_accounting"]["paired_judgment_units"] == 12

    feedbacks = _all_feedbacks(plan, [("MET", "MET")] * 12)
    feedbacks[0]["cards"][0]["selection_learning"] = {
        "admission_status": "SELECTION_ADMITTED",
        "outcome": "NOT_DIAGNOSTIC",
        "reason_code": "MEASUREMENT_MISMATCH",
    }
    result = aggregate_architecture_experiment(plan, feedbacks)
    assert result["cohort_accounting"]["operating_pair_result_counts"]["NOT_COMPARABLE"] == 1
    assert result["cohort_accounting"]["paired_judgment_units"] == 12


def test_aggregation_rejects_different_actual_observations_or_a_missing_arm() -> None:
    plan = _plan()
    feedbacks = _all_feedbacks(plan, [("MET", "MET")] * 12)
    feedbacks[1]["cards"][0]["actual_observation"]["value"] = 101.0
    with pytest.raises(ArchitectureExperimentError, match="paired_outcome_observation_mismatch"):
        aggregate_architecture_experiment(plan, feedbacks)

    with pytest.raises(ArchitectureExperimentError, match="planned_feedback_card_missing"):
        aggregate_architecture_experiment(plan, feedbacks[:-1])


def test_plan_rejects_price_probability_or_a_single_score_field() -> None:
    plan = _plan()
    plan["score"] = 0.8
    plan = prepare_architecture_experiment_plan(plan, preregistered_at="2026-08-18T08:00:00+00:00")

    result = validate_architecture_experiment_plan(plan)

    assert result["state"] == "INVALID"
    assert "unsupported_field:score" in result["invalid_findings"]
    assert "price_return_probability_or_score_field_forbidden:score" in result["invalid_findings"]
