from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.case_selection_register import prepare_case_selection_register
from scripts.judgment_method_evaluation import (
    MethodEvaluationError,
    aggregate_method_relative_feedback,
    freeze_method_evaluation_plan,
    prepare_method_evaluation_plan,
    validate_method_evaluation_plan,
)


def _register() -> dict:
    entries = []
    for suffix in ("alpha", "bravo", "charlie"):
        entries.append({
            "entry_id": "CSRSEL:" + suffix,
            "company_id": "COMPANY:" + suffix,
            "period_id": "FY2026",
            "information_cutoff": "2026-08-20",
            "state_vector_as_of": "2026-08-20",
            "state_vector": {"competitive_fork": "repair-vs-structural"},
            "selection_mode": "DIVERSE",
            "case_role": "THEORETICAL_EXTENSION",
            "mechanism_arrow": {
                "arrow_id": "ARROW:" + suffix,
                "from": "current competitive state",
                "to": "terminal operating outcome",
                "expected_difference": "The competing mechanisms make different terminal predictions.",
            },
            "exclusion": {"status": "INCLUDED", "reason": "Pre-outcome official disclosure supports a testable competing pair."},
            "cluster": {
                "company_id": "COMPANY:" + suffix,
                "period_cluster_id": "PERIOD:" + suffix,
                "mechanism_cluster_id": "MECHANISM:shared",
            },
            "outcome_isolation": "PIT_PRE_OUTCOME",
        })
    return prepare_case_selection_register({
        "schema_version": "case-selection-register.v1",
        "register_id": "CSR:method-comparison-cohort",
        "common_mechanism_question": "Which frozen path better explains a customer-demand reset?",
        "selection_information_cutoff": "2026-08-20",
        "universe": {
            "universe_id": "UNIV:method-comparison-cohort",
            "definition": "Three pre-outcome companies selected before the relevant result windows.",
            "as_of": "2026-08-20",
            "candidate_company_ids": ["COMPANY:alpha", "COMPANY:bravo", "COMPANY:charlie"],
            "state_vector_fields": ["competitive_fork"],
            "source_ids": ["DOC:cohort-screen"],
        },
        "entries": entries,
    })


def _plan(register: dict | None = None) -> dict:
    register = register or _register()
    units = []
    for suffix in ("alpha", "bravo", "charlie"):
        units.append({
            "episode_id": "JMEP:" + suffix,
            "selection_entry_id": "CSRSEL:" + suffix,
            "company_id": "COMPANY:" + suffix,
            "company_cluster_id": "COMPANY:" + suffix,
            "case_id": "HBTCASE:" + suffix,
            "freeze_id": "FREEZE:" + suffix,
            "claim_id": "HBTCLM:" + suffix,
            "forward_judgment_id": "FJ:" + suffix,
            "outcome_not_before": "2027-02-01",
        })
    return prepare_method_evaluation_plan({
        "plan_id": "JMEPLAN:customer-demand-2026",
        "cohort": {
            "register_id": register["register_id"],
            "register_fingerprint": register["freeze"]["fingerprint"],
            "screen_entries": [{
                "selection_entry_id": "CSRSEL:" + suffix,
                "disposition": "INCLUDED_SELECTION_EPISODE",
                "reason": "The pre-outcome primary path was admitted and has one terminal operating FJ.",
            } for suffix in ("alpha", "bravo", "charlie")],
        },
        "evaluation_units": units,
        "minimum_independent_company_clusters": 3,
        "aggregation_rule": {
            "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
            "outcome_boundary": "NON_PRICE_OPERATING_ONLY",
            "forecast_commitment": "NO_PROBABILITY",
            "unit": "ONE_SELECTED_TERMINAL_FJ_PER_INDEPENDENT_COMPANY_CLUSTER",
            "direct_comparison": "BINARY_FROZEN_PREDICATE_LOSS",
            "retention": "RETAIN_ALL_PLANNED_UNITS_AND_NONDIAGNOSTIC_OUTCOMES",
        },
    }, frozen_at="2026-08-21T08:00:00+00:00")


def _feedback(unit: dict, *, selection_outcome: str, increment: str) -> dict:
    return {
        "schema_version": "judgment-feedback-card.v2",
        "case_id": unit["case_id"],
        "freeze_id": unit["freeze_id"],
        "settlement_id": "HBTSETTLE:" + unit["episode_id"],
        "cards": [{
            "claim_id": unit["claim_id"],
            "forward_judgment_id": unit["forward_judgment_id"],
            "settlement_status": "CALCULATED" if selection_outcome != "NOT_EVALUATED" else "PARTIAL",
            "increment_vs_baseline": increment,
            "selection_learning": {
                "admission_status": "SELECTION_ADMITTED",
                "outcome": selection_outcome,
            },
            "rival_hypothesis_feedback": {
                "state": "DERIVED_FROM_FROZEN_RIVAL_SIGNAL",
                "signal_stage": "TERMINAL_OPERATING",
            },
        }],
    }


def _selected_terminal_case(unit: dict, register: dict) -> dict:
    return {
        "case_id": unit["case_id"],
        "report_freeze": {"freeze_id": unit["freeze_id"]},
        "calibration_ledger": {
            "selection_admission": {
                "status": "SELECTION_ADMITTED",
                "selection_forward_judgment_ids": [unit["forward_judgment_id"]],
                "selection_register_binding": {
                    "register_id": register["register_id"],
                    "register_fingerprint": register["freeze"]["fingerprint"],
                    "selection_entry_id": unit["selection_entry_id"],
                    "company_id": unit["company_id"],
                    "company_cluster_id": unit["company_cluster_id"],
                },
            },
            "claims": [{
                "claim_id": unit["claim_id"],
                "forward_judgment_id": unit["forward_judgment_id"],
                "observable_outcome": {
                    "observation_window": {"opens_after": "2027-02-01T08:00:00+00:00"},
                },
            }],
            "rival_hypothesis_pairs": [{
                "discriminators": [{
                    "forward_judgment_id": unit["forward_judgment_id"],
                    "stage": "TERMINAL_OPERATING",
                }],
            }],
        },
    }


def _no_primary_case(entry_id: str, register: dict, *, case_id: str, freeze_id: str) -> dict:
    entry = next(item for item in register["entries"] if item["entry_id"] == entry_id)
    return {
        "case_id": case_id,
        "report_freeze": {"freeze_id": freeze_id},
        "calibration_ledger": {
            "selection_admission": {
                "status": "NO_PRIMARY",
                "selection_register_binding": {
                    "register_id": register["register_id"],
                    "register_fingerprint": register["freeze"]["fingerprint"],
                    "selection_entry_id": entry_id,
                    "company_id": entry["company_id"],
                    "company_cluster_id": entry["cluster"]["company_id"],
                },
            },
        },
    }


def test_frozen_plan_requires_the_complete_register_screen_and_one_independent_terminal_unit_per_company() -> None:
    register = _register()
    plan = _plan(register)

    result = validate_method_evaluation_plan(
        plan,
        selection_register=register,
        frozen_cases=[_selected_terminal_case(unit, register) for unit in plan["evaluation_units"]],
    )

    assert result["state"] == "REVIEWABLE"
    assert result["independent_company_clusters"] == ["COMPANY:alpha", "COMPANY:bravo", "COMPANY:charlie"]


def test_plan_rejects_hidden_screen_omission_post_outcome_freeze_and_nonterminal_signal() -> None:
    register = _register()
    plan = _plan(register)
    plan["cohort"]["screen_entries"].pop()
    plan = prepare_method_evaluation_plan(plan, frozen_at="2027-02-01T08:00:00+00:00")
    cases = [_selected_terminal_case(unit, register) for unit in plan["evaluation_units"]]
    cases[0]["calibration_ledger"]["rival_hypothesis_pairs"][0]["discriminators"][0]["stage"] = "EARLY_MECHANISM"

    result = validate_method_evaluation_plan(plan, selection_register=register, frozen_cases=cases)

    assert result["state"] == "INVALID"
    assert "cohort_screen_entry_missing:CSRSEL:charlie" in result["invalid_findings"]
    assert "evaluation_units[0]:not_a_selected_terminal_forward_judgment" in result["invalid_findings"]
    assert "evaluation_units[0]:plan_not_frozen_before_outcome_window" in result["invalid_findings"]


def test_l5_freeze_requires_each_frozen_case_to_bind_the_same_selection_register_entry() -> None:
    register = _register()
    draft = _plan(register)
    draft.pop("freeze")
    cases = [_selected_terminal_case(unit, register) for unit in draft["evaluation_units"]]

    frozen = freeze_method_evaluation_plan(
        draft, frozen_at="2026-08-21T08:00:00+00:00",
        selection_register=register, frozen_cases=cases,
    )

    assert frozen["freeze"]["frozen"] is True
    cases[0]["calibration_ledger"]["selection_admission"]["selection_register_binding"]["selection_entry_id"] = "CSRSEL:bravo"
    result = validate_method_evaluation_plan(frozen, selection_register=register, frozen_cases=cases)
    assert result["state"] == "INVALID"
    assert "evaluation_units[0]:selection_register_binding_selection_entry_id_mismatch" in result["invalid_findings"]


def test_plan_rejects_price_probability_or_score_instead_of_nonprice_operating_contract() -> None:
    register = _register()
    plan = _plan(register)
    plan["score"] = "method win rate"
    plan = prepare_method_evaluation_plan(plan, frozen_at="2026-08-21T08:00:00+00:00")

    result = validate_method_evaluation_plan(plan, selection_register=register)

    assert result["state"] == "INVALID"
    assert "unsupported_field:score" in result["invalid_findings"]
    assert "price_return_probability_or_score_field_forbidden:score" in result["invalid_findings"]


def test_plan_fingerprint_rejects_a_later_attempt_to_shrink_the_cohort() -> None:
    register = _register()
    plan = _plan(register)
    plan["evaluation_units"].pop()

    result = validate_method_evaluation_plan(plan, selection_register=register)

    assert result["state"] == "INVALID"
    assert "freeze_fingerprint_mismatch" in result["invalid_findings"]


def test_plan_refuses_a_screened_selection_episode_without_its_terminal_evaluation_unit() -> None:
    register = _register()
    plan = _plan(register)
    plan["evaluation_units"].pop()
    plan["minimum_independent_company_clusters"] = 2
    plan = prepare_method_evaluation_plan(plan, frozen_at="2026-08-21T08:00:00+00:00")

    result = validate_method_evaluation_plan(plan, selection_register=register)

    assert result["state"] == "INVALID"
    assert "included_screen_entry_without_evaluation_unit:CSRSEL:charlie" in result["invalid_findings"]


def test_plan_rejects_the_same_company_relabelled_as_multiple_independent_clusters() -> None:
    register = _register()
    for entry in register["entries"][1:]:
        entry["company_id"] = "COMPANY:alpha"
        entry["cluster"]["company_id"] = "COMPANY:alpha"
    register = prepare_case_selection_register(register)
    plan = _plan(register)
    for unit in plan["evaluation_units"][1:]:
        unit["company_id"] = "COMPANY:alpha"
        unit["company_cluster_id"] = "COMPANY:alpha:relabelled"
    plan = prepare_method_evaluation_plan(plan, frozen_at="2026-08-21T08:00:00+00:00")

    result = validate_method_evaluation_plan(plan, selection_register=register)

    assert result["state"] == "INVALID"
    assert "evaluation_units[1]:company_id_duplicate:COMPANY:alpha" in result["invalid_findings"]
    assert "evaluation_units[1]:company_cluster_id_does_not_match_selection_register" in result["invalid_findings"]


def test_aggregation_retains_rival_win_nondiagnostic_and_baseline_tie_in_the_frozen_denominator() -> None:
    register = _register()
    plan = _plan(register)
    units = plan["evaluation_units"]
    feedbacks = [
        _feedback(units[0], selection_outcome="SUPPORTS_SELECTED", increment="JUDGMENT_BETTER"),
        _feedback(units[1], selection_outcome="SUPPORTS_RIVAL", increment="BASELINE_BETTER"),
        _feedback(units[2], selection_outcome="NOT_DIAGNOSTIC", increment="NO_DIRECTIONAL_INCREMENT_IDENTIFIED"),
    ]

    evaluation = aggregate_method_relative_feedback(plan, feedbacks, selection_register=register)

    assert evaluation["state"] == "DESCRIPTIVE_COMPARISON_READY"
    accounting = evaluation["cohort_accounting"]
    assert accounting["planned_selection_episodes"] == 3
    assert accounting["selection_outcome_counts"]["SUPPORTS_SELECTED"] == 1
    assert accounting["selection_outcome_counts"]["SUPPORTS_RIVAL"] == 1
    assert accounting["selection_outcome_counts"]["NOT_DIAGNOSTIC"] == 1
    assert accounting["increment_vs_baseline_counts"]["JUDGMENT_BETTER"] == 1
    assert accounting["increment_vs_baseline_counts"]["BASELINE_BETTER"] == 1
    assert "score" in evaluation["interpretation_boundary"]
    assert evaluation["investment_return"] == "SEPARATE_NOT_INCLUDED"


def test_aggregation_refuses_to_drop_a_frozen_episode_or_treat_an_early_signal_as_l5_feedback() -> None:
    register = _register()
    plan = _plan(register)
    units = plan["evaluation_units"]
    incomplete = [_feedback(unit, selection_outcome="SUPPORTS_SELECTED", increment="JUDGMENT_BETTER") for unit in units[:2]]

    with pytest.raises(MethodEvaluationError, match="planned_feedback_card_missing:JMEP:charlie"):
        aggregate_method_relative_feedback(plan, incomplete, selection_register=register)

    feedbacks = [_feedback(unit, selection_outcome="SUPPORTS_SELECTED", increment="JUDGMENT_BETTER") for unit in units]
    feedbacks[0]["cards"][0]["rival_hypothesis_feedback"]["signal_stage"] = "EARLY_MECHANISM"
    with pytest.raises(MethodEvaluationError, match="selection_feedback_not_from_terminal_signal:JMEP:alpha"):
        aggregate_method_relative_feedback(plan, feedbacks, selection_register=register)


def test_aggregation_retains_a_baseline_tie_and_a_pending_outcome_without_claiming_l5_ready() -> None:
    register = _register()
    plan = _plan(register)
    units = plan["evaluation_units"]
    feedbacks = [
        _feedback(units[0], selection_outcome="SUPPORTS_SELECTED", increment="JUDGMENT_BETTER"),
        _feedback(units[1], selection_outcome="BASELINE_NONDISCRIMINATING", increment="BASELINE_NONDISCRIMINATING"),
        _feedback(units[2], selection_outcome="NOT_EVALUATED", increment="NOT_EVALUATED"),
    ]

    evaluation = aggregate_method_relative_feedback(plan, feedbacks, selection_register=register)

    assert evaluation["state"] == "PENDING_FROZEN_OUTCOMES"
    accounting = evaluation["cohort_accounting"]
    assert accounting["selection_outcome_counts"]["BASELINE_NONDISCRIMINATING"] == 1
    assert accounting["selection_outcome_counts"]["NOT_EVALUATED"] == 1
    assert accounting["increment_vs_baseline_counts"]["BASELINE_NONDISCRIMINATING"] == 1
    assert accounting["increment_vs_baseline_counts"]["NOT_EVALUATED"] == 1


def test_aggregation_keeps_no_primary_visible_as_coverage_not_as_a_directional_win() -> None:
    register = _register()
    register["universe"]["candidate_company_ids"].append("COMPANY:delta")
    register["entries"].append({
        "entry_id": "CSRSEL:delta", "company_id": "COMPANY:delta", "period_id": "FY2026",
        "information_cutoff": "2026-08-20", "state_vector_as_of": "2026-08-20",
        "state_vector": {"competitive_fork": "repair-vs-structural"},
        "selection_mode": "DIVERSE", "case_role": "THEORETICAL_EXTENSION",
        "mechanism_arrow": {
            "arrow_id": "ARROW:delta", "from": "current competitive state", "to": "terminal operating outcome",
            "expected_difference": "The competing mechanisms make different terminal predictions.",
        },
        "exclusion": {"status": "EXCLUDED", "reason": "No directional pre-cutoff selection evidence."},
        "cluster": {"company_id": "COMPANY:delta", "period_cluster_id": "PERIOD:delta", "mechanism_cluster_id": "MECHANISM:shared"},
        "outcome_isolation": "PIT_PRE_OUTCOME",
    })
    register = prepare_case_selection_register(register)
    plan = _plan(register)
    plan["cohort"]["screen_entries"].append({
        "selection_entry_id": "CSRSEL:delta", "disposition": "EXCLUDED_NO_PRIMARY",
        "reason": "The frozen screen retained both mechanisms because no non-common directional fact admitted a path.",
        "no_primary_case_id": "HBTCASE:delta-no-primary", "no_primary_freeze_id": "FREEZE:delta-no-primary",
    })
    plan = prepare_method_evaluation_plan(plan, frozen_at="2026-08-21T08:00:00+00:00")
    feedbacks = [
        _feedback(unit, selection_outcome="SUPPORTS_SELECTED", increment="JUDGMENT_BETTER")
        for unit in plan["evaluation_units"]
    ]

    evaluation = aggregate_method_relative_feedback(plan, feedbacks, selection_register=register)

    coverage = evaluation["cohort_accounting"]["screen_disposition_counts"]
    assert coverage["INCLUDED_SELECTION_EPISODE"] == 3
    assert coverage["EXCLUDED_NO_PRIMARY"] == 1
    assert evaluation["cohort_accounting"]["selection_outcome_counts"]["SUPPORTS_SELECTED"] == 3
    assert "not a direction win" in evaluation["selection_coverage_boundary"]


def test_l5_freeze_requires_a_real_frozen_no_primary_receipt_for_each_abstention() -> None:
    register = _register()
    register["universe"]["candidate_company_ids"].append("COMPANY:delta")
    register["entries"].append({
        "entry_id": "CSRSEL:delta", "company_id": "COMPANY:delta", "period_id": "FY2026",
        "information_cutoff": "2026-08-20", "state_vector_as_of": "2026-08-20",
        "state_vector": {"competitive_fork": "repair-vs-structural"},
        "selection_mode": "DIVERSE", "case_role": "THEORETICAL_EXTENSION",
        "mechanism_arrow": {
            "arrow_id": "ARROW:delta", "from": "current competitive state", "to": "terminal operating outcome",
            "expected_difference": "The competing mechanisms make different terminal predictions.",
        },
        "exclusion": {"status": "EXCLUDED", "reason": "No directional pre-cutoff selection evidence."},
        "cluster": {"company_id": "COMPANY:delta", "period_cluster_id": "PERIOD:delta", "mechanism_cluster_id": "MECHANISM:shared"},
        "outcome_isolation": "PIT_PRE_OUTCOME",
    })
    register = prepare_case_selection_register(register)
    draft = _plan(register)
    draft.pop("freeze")
    draft["cohort"]["screen_entries"].append({
        "selection_entry_id": "CSRSEL:delta", "disposition": "EXCLUDED_NO_PRIMARY",
        "reason": "No pre-cutoff fact selected either mechanism.",
        "no_primary_case_id": "HBTCASE:delta-no-primary", "no_primary_freeze_id": "FREEZE:delta-no-primary",
    })
    cases = [_selected_terminal_case(unit, register) for unit in draft["evaluation_units"]]
    no_primary = _no_primary_case(
        "CSRSEL:delta", register, case_id="HBTCASE:delta-no-primary", freeze_id="FREEZE:delta-no-primary",
    )

    frozen = freeze_method_evaluation_plan(
        draft, frozen_at="2026-08-21T08:00:00+00:00",
        selection_register=register, frozen_cases=[*cases, no_primary],
    )

    assert frozen["freeze"]["frozen"] is True
    no_primary["calibration_ledger"]["selection_admission"]["status"] = "SELECTION_ADMITTED"
    result = validate_method_evaluation_plan(
        frozen, selection_register=register, frozen_cases=[*cases, no_primary],
    )
    assert result["state"] == "INVALID"
    assert "cohort.screen_entries:CSRSEL:delta:case_is_not_frozen_no_primary" in result["invalid_findings"]
