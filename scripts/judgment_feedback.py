#!/usr/bin/env python3
"""Produce task-information feedback from an immutable judgment settlement.

The card intentionally does not diagnose *why* a company judgment was wrong.
It exposes the frozen terminal path, mechanism, financial transmission,
baseline, and later official observation so that a separate review can make
that diagnosis without rewriting the original report or using the return as a
proxy for operating truth.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from scripts.historical_backtest import (
    derive_rival_hypothesis_pair_outcomes,
    validate_case,
    validate_settlement,
)
from scripts.phase10_acquisition import licensed_industry_series_matches_source


SCHEMA_VERSION = "judgment-feedback-card.v2"
ROOT_CAUSE_CLASSES = (
    "DATA_COVERAGE", "ACQUISITION_MODULE", "REASONING", "MODEL", "WRITING",
)


class JudgmentFeedbackError(ValueError):
    """Raised when a card would misrepresent a frozen case or settlement."""


def _financial_driver_context(case: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    """Expose the independently reviewed, frozen company-driver context.

    Legacy cases did not have the bridge contract.  They remain usable for
    outcome feedback, but the card must say that the four-layer diagnosis was
    unavailable rather than fabricate a retrospective driver narrative.
    """
    bridge = case.get("financial_driver_bridge")
    if bridge is None:
        return {
            "state": "NOT_PRESENT_IN_LEGACY_FROZEN_CASE",
            "reason": "The case predates the frozen financial-driver bridge contract.",
            "layers": [],
            "allocation_events": [],
        }
    if not isinstance(bridge, dict) or bridge.get("schema_version") != "frozen-financial-driver-bridge.v1":
        raise JudgmentFeedbackError("case financial-driver bridge is not a frozen bridge snapshot")
    if bridge.get("validation_state") != "REVIEWABLE":
        raise JudgmentFeedbackError("case financial-driver bridge was not reviewable at freeze")
    reviewed_bridge = (
        ((case.get("report_freeze") or {}).get("independent_review") or {}).get("frozen_case_contract") or {}
    ).get("financial_driver_bridge")
    if reviewed_bridge != bridge:
        raise JudgmentFeedbackError("case financial-driver bridge differs from the independently reviewed frozen contract")
    drivers = bridge.get("drivers")
    if not isinstance(drivers, list):
        raise JudgmentFeedbackError("frozen financial-driver bridge has no drivers")
    driver_map = {
        str(item.get("driver_id")): item
        for item in drivers
        if isinstance(item, dict) and str(item.get("driver_id") or "").strip()
    }
    linked_ids = claim.get("financial_driver_ids") or []
    if not isinstance(linked_ids, list):
        raise JudgmentFeedbackError("forward-judgment driver links are malformed")
    unknown_links = sorted(str(driver_id) for driver_id in linked_ids if str(driver_id) not in driver_map)
    if unknown_links:
        raise JudgmentFeedbackError("forward judgment references a driver absent from its frozen bridge: " + ", ".join(unknown_links))
    layers: list[dict[str, Any]] = []
    for layer in ("COMPETITION_DEMAND", "UNIT_ECONOMICS", "CASH_CONVERSION", "CAPITAL_ALLOCATION"):
        layer_drivers = [
            item for item in driver_map.values()
            if item.get("layer") == layer
        ]
        layers.append({
            "layer": layer,
            "linked_driver_ids": [str(item.get("driver_id")) for item in layer_drivers if item.get("driver_id") in linked_ids],
            "drivers": deepcopy(layer_drivers),
        })
    return {
        "state": "FROZEN_REVIEWABLE",
        "ledger_sha256": bridge.get("ledger_sha256"),
        "linked_driver_ids": deepcopy(linked_ids),
        "layers": layers,
        "allocation_events": deepcopy(bridge.get("allocation_events") or []),
    }


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _prediction_result(prediction: dict[str, Any], actual: Any) -> dict[str, Any]:
    """Evaluate a frozen point/range predicate without creating a midpoint."""
    observed = _number(actual)
    operator = prediction.get("operator")
    if observed is None:
        raise JudgmentFeedbackError("settled observation actual value is not numeric")
    if operator == "RANGE":
        low = _number(prediction.get("range_low"))
        high = _number(prediction.get("range_high"))
        if low is None or high is None or low > high:
            raise JudgmentFeedbackError("frozen range prediction is invalid")
        disposition = "BELOW_RANGE" if observed < low else "ABOVE_RANGE" if observed > high else "WITHIN_RANGE"
        return {"status": disposition, "actual_value": observed, "range_low": low, "range_high": high}
    target = _number(prediction.get("value"))
    if target is None:
        raise JudgmentFeedbackError("frozen point prediction is invalid")
    comparisons = {
        "AT_LEAST": observed >= target,
        "AT_MOST": observed <= target,
        "EQUALS": observed == target,
    }
    if operator not in comparisons:
        raise JudgmentFeedbackError("frozen prediction operator is invalid")
    return {
        "status": "MET" if comparisons[operator] else "MISSED",
        "actual_value": observed,
        "operator": operator,
        "target_value": target,
    }


def _comparable_baseline(
    baseline: dict[str, Any], prediction: dict[str, Any], actual: Any,
) -> dict[str, Any]:
    baseline_prediction = baseline.get("prediction") if isinstance(baseline.get("prediction"), dict) else {}
    for field in ("metric", "unit", "horizon", "resolution_due"):
        if baseline_prediction.get(field) != prediction.get(field):
            raise JudgmentFeedbackError("baseline no longer matches the frozen judgment target: " + field)
    result = _prediction_result(baseline_prediction, actual)
    return {
        "baseline_id": baseline.get("baseline_id"),
        "method": baseline.get("method"),
        "prediction": deepcopy(baseline_prediction),
        "outcome": result,
    }


def _comparison(judgment: dict[str, Any], baseline: dict[str, Any]) -> str:
    judgment_status = judgment.get("status")
    baseline_status = (baseline.get("outcome") or {}).get("status")
    satisfied = {"MET", "WITHIN_RANGE"}
    if judgment_status in satisfied and baseline_status not in satisfied:
        return "JUDGMENT_BETTER"
    if judgment_status not in satisfied and baseline_status in satisfied:
        return "BASELINE_BETTER"
    return "NO_DIRECTIONAL_INCREMENT_IDENTIFIED"


def _same_prediction(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    fields = (
        "metric", "operator", "unit", "horizon", "resolution_due",
        "value", "range_low", "range_high",
    )
    return all(left.get(field) == right.get(field) for field in fields)


def _increment_vs_baseline(
    judgment: dict[str, Any], baseline: dict[str, Any], prediction: dict[str, Any],
) -> str:
    """Never count an identical frozen predicate as an incremental method win."""
    baseline_prediction = baseline.get("prediction") if isinstance(baseline.get("prediction"), dict) else {}
    if _same_prediction(prediction, baseline_prediction):
        return "BASELINE_NONDISCRIMINATING"
    return _comparison(judgment, baseline)


def _selection_learning_feedback(
    selection_admission: dict[str, Any], claim: dict[str, Any], *,
    settlement_status: str, increment_vs_baseline: str,
    rival_feedback: dict[str, Any], measurement_mismatch: bool = False,
) -> dict[str, Any]:
    """Keep a valid mechanism signal separate from a valid path-choice result."""
    status = str(selection_admission.get("status") or "NOT_SELECTION_ELIGIBLE")
    if status != "SELECTION_ADMITTED":
        return {
            "admission_status": status,
            "outcome": status if status == "NO_PRIMARY" else "NOT_SELECTION_ELIGIBLE",
            "reason": "This frozen CJO did not admit the central path as an R-07 selection-learning episode.",
        }
    selected_judgments = selection_admission.get("selection_forward_judgment_ids")
    if not isinstance(selected_judgments, list) or claim.get("forward_judgment_id") not in selected_judgments:
        return {
            "admission_status": status,
            "outcome": "NOT_REGISTERED_SELECTION_SIGNAL",
            "reason": "The forward judgment was not one of the frozen signals registered for path-selection learning.",
        }
    if measurement_mismatch and settlement_status != "CALCULATED":
        return {
            "admission_status": status,
            "outcome": "NOT_DIAGNOSTIC",
            "reason_code": "MEASUREMENT_MISMATCH",
            "reason": "A later observation changed or failed the frozen metric reconstruction contract, so it cannot settle path selection.",
        }
    if settlement_status != "CALCULATED":
        return {
            "admission_status": status,
            "outcome": "NOT_EVALUATED",
            "reason": "The registered selection signal has not reached a calculated official settlement.",
        }
    if increment_vs_baseline == "BASELINE_NONDISCRIMINATING":
        return {
            "admission_status": status,
            "outcome": "BASELINE_NONDISCRIMINATING",
            "reason": "The primary path and its frozen simple baseline made the same prediction.",
        }
    comparison_state = str(rival_feedback.get("comparison_state") or "")
    outcome = {
        "PRIMARY_ONLY": "SUPPORTS_SELECTED",
        "RIVAL_ONLY": "SUPPORTS_RIVAL",
        "BOTH_MET": "NOT_DIAGNOSTIC",
        "NEITHER_MET": "NOT_DIAGNOSTIC",
    }.get(comparison_state, "NOT_DIAGNOSTIC")
    return {
        "admission_status": status,
        "outcome": outcome,
        "rival_comparison_state": comparison_state or "NOT_AVAILABLE",
    }


def _has_metric_reconstruction_mismatch(
    claim: dict[str, Any], observations: dict[str, dict[str, Any]],
    actual_sources: dict[str, dict[str, Any]],
) -> bool:
    """A selected FJ with a frozen contract may stop, but never score, on drift."""
    outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
    series_contract = outcome.get("licensed_industry_series_contract")
    if not isinstance(outcome.get("metric_reconstruction_contract"), dict) and not isinstance(series_contract, dict):
        return False
    mismatch_statuses = {"PERIOD_MISMATCH", "SCOPE_OR_ACCOUNTING_DRIFT", "NOT_COMPARABLE"}
    claim_id = str(claim.get("claim_id") or "")
    if any(
        observation.get("claim_id") == claim_id
        and observation.get("comparability_status") in mismatch_statuses
        for observation in observations.values()
    ):
        return True
    if not isinstance(series_contract, dict):
        return False
    for observation in observations.values():
        if observation.get("claim_id") != claim_id:
            continue
        source_ids = [str(source_id) for source_id in observation.get("source_ids") or []]
        series_sources = [actual_sources[source_id] for source_id in source_ids if source_id in actual_sources]
        if not series_sources or any(
            not licensed_industry_series_matches_source(series_contract, source)
            for source in series_sources
        ):
            return True
    return False


def _rival_hypothesis_feedback(
    pair_outcomes: list[dict[str, Any]], claim: dict[str, Any],
) -> dict[str, Any]:
    """Bind a feedback card to its derived rival-signal result when present.

    A historical case without paired hypotheses remains legible as legacy
    feedback. But once a frozen case carries rival-pair outcomes, the claim
    must identify its own pair and signal before a later learning action can
    call the observation informative. An early signal may be diagnostic before
    the terminal signal is due, so this does not require an overall pair winner.
    """
    if not pair_outcomes:
        return {
            "state": "NOT_PRESENT_IN_LEGACY_FROZEN_CASE",
            "reason": "The frozen case contains no rival-hypothesis pair outcomes.",
        }
    pair_id = str(claim.get("rival_hypothesis_pair_id") or "").strip()
    signal_id = str(claim.get("rival_signal_id") or "").strip()
    if not pair_id or not signal_id:
        return {
            "state": "PAIR_PRESENT_BUT_CLAIM_NOT_LINKED",
            "reason": "The frozen case has rival-pair outcomes, but this claim lacks its pair/signal identity.",
        }
    matching_pairs = [item for item in pair_outcomes if item.get("pair_id") == pair_id]
    if len(matching_pairs) != 1:
        raise JudgmentFeedbackError("claim rival-hypothesis pair cannot be resolved from frozen outcomes")
    matching_signals = [
        item for item in matching_pairs[0].get("signals") or []
        if isinstance(item, dict)
        and item.get("signal_id") == signal_id
        and item.get("claim_id") == claim.get("claim_id")
    ]
    if len(matching_signals) != 1:
        raise JudgmentFeedbackError("claim rival-hypothesis signal cannot be resolved from frozen outcomes")
    signal = matching_signals[0]
    comparison_state = signal.get("comparison_state")
    research_implication = {
        "PRIMARY_ONLY": "DIAGNOSTIC_SUPPORT_FOR_PRIMARY",
        "RIVAL_ONLY": "DIAGNOSTIC_SUPPORT_FOR_RIVAL",
        "BOTH_MET": "NON_DIAGNOSTIC_SHARED_PREDICTION_REVIEW",
        "NEITHER_MET": "MECHANISM_OR_MEASUREMENT_RESEARCH_REDIRECT",
        "NOT_YET_DUE": "AWAIT_FROZEN_OBSERVATION_WINDOW",
    }.get(comparison_state, "UNKNOWN_COMPARISON_STATE")
    return {
        "state": "DERIVED_FROM_FROZEN_RIVAL_SIGNAL",
        "pair_id": pair_id,
        "signal_id": signal_id,
        "signal_stage": signal.get("stage"),
        "signal_verdict": signal.get("verdict"),
        "comparison_state": comparison_state,
        "research_implication": research_implication,
        "pair_verdict": matching_pairs[0].get("pair_verdict"),
        "terminal_comparison_state": matching_pairs[0].get("terminal_comparison_state"),
    }


def _is_test_fixture_case(case: dict[str, Any]) -> bool:
    """Keep fixture convenience out of real post-cutoff learning.

    Production feedback must replay the strict settlement path, including the
    P-34 outcome package.  Existing direct regression fixtures have an
    explicit test mode, so retaining their lightweight construction does not
    widen a real case's accepted inputs.
    """
    freeze = case.get("report_freeze") if isinstance(case.get("report_freeze"), dict) else {}
    return freeze.get("mode") == "TEST_FIXTURE" and str(case.get("case_id") or "").startswith("HBTCASE:TEST")


def build_judgment_feedback_cards(
    case: dict[str, Any], settlement: dict[str, Any], *, allow_test_fixtures: bool | None = None,
) -> dict[str, Any]:
    """Build review-ready feedback cards from a valid frozen case and settlement.

    Only claims projected from a forward judgment are included.  Return data is
    intentionally omitted: it has a separate economic identity and must not
    decide whether an operating or mechanism judgment was correct.
    """
    detected_fixture = _is_test_fixture_case(case)
    if allow_test_fixtures is True and not detected_fixture:
        raise JudgmentFeedbackError("non-fixture feedback cannot enable test-fixture validation")
    fixture_mode = detected_fixture if allow_test_fixtures is None else bool(allow_test_fixtures)
    case_validation = validate_case(case, allow_test_fixtures=fixture_mode)
    if case_validation.get("state") != "REVIEWABLE":
        raise JudgmentFeedbackError("frozen case is not reviewable")
    settlement_validation = validate_settlement(
        settlement, case=case, allow_test_fixtures=fixture_mode,
    )
    if settlement_validation.get("state") != "REVIEWABLE":
        raise JudgmentFeedbackError("settlement is not reviewable")

    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    selection_admission = (
        ledger.get("selection_admission")
        if isinstance(ledger.get("selection_admission"), dict)
        else {"status": "NOT_SELECTION_ELIGIBLE"}
    )
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    forward_claims = [
        claim for claim in claims
        if isinstance(claim, dict) and str(claim.get("forward_judgment_id") or "").strip()
    ]
    if not forward_claims:
        raise JudgmentFeedbackError("frozen case contains no forward-judgment claims")
    pair_outcomes = derive_rival_hypothesis_pair_outcomes(case, settlement)

    model_error = settlement.get("model_forecast_error") if isinstance(settlement.get("model_forecast_error"), dict) else {}
    claim_settlements = {
        str(item.get("claim_id")): item
        for item in model_error.get("claim_settlements") or []
        if isinstance(item, dict) and item.get("claim_id")
    }
    metrics = {
        str(item.get("claim_id")): item
        for item in model_error.get("metrics") or []
        if isinstance(item, dict) and item.get("claim_id")
    }
    actual = settlement.get("actual_outcomes") if isinstance(settlement.get("actual_outcomes"), dict) else {}
    observations = {
        str(item.get("observation_id")): item
        for item in actual.get("operating_observations") or []
        if isinstance(item, dict) and item.get("observation_id")
    }
    actual_sources = {
        str(item.get("source_id")): item
        for item in settlement.get("actual_sources") or []
        if isinstance(item, dict) and str(item.get("source_id") or "").strip()
    }

    cards: list[dict[str, Any]] = []
    for claim in forward_claims:
        claim_id = str(claim.get("claim_id"))
        disposition = claim_settlements.get(claim_id)
        if disposition is None:
            raise JudgmentFeedbackError("settlement omits frozen forward-judgment claim: " + claim_id)
        settlement_status = str(disposition.get("status") or "")
        rival_feedback = _rival_hypothesis_feedback(pair_outcomes, claim)
        measurement_mismatch = _has_metric_reconstruction_mismatch(claim, observations, actual_sources)
        base_card = {
            "claim_id": claim_id,
            "forward_judgment_id": claim.get("forward_judgment_id"),
            "central_path_id": claim.get("central_path_id"),
            "statement": claim.get("statement"),
            "counter_thesis": claim.get("counter_thesis"),
            "flip_condition": claim.get("flip_condition"),
            "mechanism_chain_ids": deepcopy(claim.get("mechanism_chain_ids") or []),
            "financial_driver_context": _financial_driver_context(case, claim),
            "rival_hypothesis_feedback": rival_feedback,
            "transmission": deepcopy(claim.get("transmission") or {}),
            "settlement_status": settlement_status,
            "root_cause_review": {
                "state": "PENDING_HUMAN_REVIEW",
                "allowed_classes": list(ROOT_CAUSE_CLASSES),
                "instruction": "Classify the failed or unresolved company judgment from frozen evidence, transmission and later official observations; do not use price return as an operating root cause.",
            },
        }
        if settlement_status != "CALCULATED":
            cards.append({
                **base_card,
                "actual_observation": None,
                "judgment_outcome": {"status": "NOT_EVALUATED"},
                "baseline": {"status": "NOT_EVALUATED"},
                "increment_vs_baseline": "NOT_EVALUATED",
                "selection_learning": _selection_learning_feedback(
                    selection_admission, claim, settlement_status=settlement_status,
                    increment_vs_baseline="NOT_EVALUATED", rival_feedback=rival_feedback,
                    measurement_mismatch=measurement_mismatch,
                ),
            })
            continue
        metric = metrics.get(claim_id)
        if metric is None:
            raise JudgmentFeedbackError("calculated forward-judgment claim has no settlement metric: " + claim_id)
        observation = observations.get(str(metric.get("observation_id") or ""))
        if observation is None:
            raise JudgmentFeedbackError("calculated forward-judgment metric has no official observation: " + claim_id)
        prediction = claim.get("prediction") if isinstance(claim.get("prediction"), dict) else {}
        baseline = claim.get("baseline") if isinstance(claim.get("baseline"), dict) else {}
        if not baseline:
            raise JudgmentFeedbackError("frozen forward-judgment claim lacks its baseline: " + claim_id)
        judgment = _prediction_result(prediction, metric.get("actual_value"))
        baseline_result = _comparable_baseline(baseline, prediction, metric.get("actual_value"))
        increment_vs_baseline = _increment_vs_baseline(judgment, baseline_result, prediction)
        cards.append({
            **base_card,
            "actual_observation": {
                "observation_id": observation.get("observation_id"),
                "metric": observation.get("metric"),
                "value": observation.get("value"),
                "unit": observation.get("unit"),
                "source_ids": deepcopy(observation.get("source_ids") or []),
                "comparability_status": observation.get("comparability_status"),
            },
            "judgment_outcome": judgment,
            "baseline": baseline_result,
            "increment_vs_baseline": increment_vs_baseline,
            "selection_learning": _selection_learning_feedback(
                selection_admission, claim, settlement_status=settlement_status,
                increment_vs_baseline=increment_vs_baseline, rival_feedback=rival_feedback,
                measurement_mismatch=measurement_mismatch,
            ),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case.get("case_id"),
        "freeze_id": (case.get("report_freeze") or {}).get("freeze_id"),
        "settlement_id": settlement.get("settlement_id"),
        "settlement_as_of": settlement.get("settlement_as_of"),
        "investment_return": "SEPARATE_NOT_INCLUDED",
        "rival_hypothesis_pair_outcomes": pair_outcomes,
        "cards": cards,
    }
