#!/usr/bin/env python3
"""Freeze and describe a finite, non-price L5 method-comparison cohort.

This module deliberately does *not* produce a judgment score, a probability,
or a claim that Turtle has a general advantage.  It protects the much smaller
promise needed before such a question can even be discussed: a cohort's
selection units, simple baselines, exclusions, and treatment of non-diagnostic
outcomes were fixed before the relevant operating results could be read.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from typing import Any

from scripts.case_selection_register import (
    case_selection_register_fingerprint,
    validate_case_selection_register,
)


PLAN_SCHEMA_VERSION = "judgment-method-evaluation-plan.v1"
EVALUATION_SCHEMA_VERSION = "judgment-method-relative-evaluation.v1"
PLAN_ID_PREFIX = "JMEPLAN:"
EPISODE_ID_PREFIX = "JMEP:"
SCREEN_DISPOSITIONS = {
    "INCLUDED_SELECTION_EPISODE",
    "EXCLUDED_NO_PRIMARY",
    "EXCLUDED_NONCOMPARABLE",
}
SELECTION_OUTCOMES = {
    "SUPPORTS_SELECTED",
    "SUPPORTS_RIVAL",
    "NOT_DIAGNOSTIC",
    "BASELINE_NONDISCRIMINATING",
    "NOT_EVALUATED",
}
INCREMENT_OUTCOMES = {
    "JUDGMENT_BETTER",
    "BASELINE_BETTER",
    "NO_DIRECTIONAL_INCREMENT_IDENTIFIED",
    "BASELINE_NONDISCRIMINATING",
    "NOT_EVALUATED",
}
FORBIDDEN_TERMS = {
    "price", "share_price", "market_price", "return", "expected_return",
    "investment_return", "valuation", "position", "action", "probability",
    "score", "accuracy", "win_rate",
}


class MethodEvaluationError(ValueError):
    """Raised when an L5 cohort would conceal scope or use the wrong evidence."""


def _day(value: Any) -> date | None:
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


def _unsupported_fields(value: Any, allowed: set[str]) -> list[str]:
    if not isinstance(value, dict):
        return []
    return sorted(str(field) for field in value if str(field) not in allowed)


def _fingerprint_payload(plan: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(plan)
    payload.pop("generated_at", None)
    payload.pop("updated_at", None)
    payload.pop("freeze", None)
    return payload


def method_evaluation_plan_fingerprint(plan: dict[str, Any]) -> str:
    raw = json.dumps(
        _fingerprint_payload(plan), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _claim_index(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    return {
        str(item.get("forward_judgment_id")): item
        for item in ledger.get("claims") or []
        if isinstance(item, dict) and str(item.get("forward_judgment_id") or "").strip()
    }


def _selected_terminal_judgment(case: dict[str, Any], forward_judgment_id: str) -> dict[str, Any] | None:
    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    admission = ledger.get("selection_admission") if isinstance(ledger.get("selection_admission"), dict) else {}
    selected = {
        str(item) for item in admission.get("selection_forward_judgment_ids") or []
        if str(item).strip()
    }
    if admission.get("status") != "SELECTION_ADMITTED" or forward_judgment_id not in selected:
        return None
    claims = _claim_index(case)
    claim = claims.get(forward_judgment_id)
    if claim is None:
        return None
    terminal_signals = [
        item for pair in ledger.get("rival_hypothesis_pairs") or []
        if isinstance(pair, dict)
        for item in pair.get("discriminators") or []
        if isinstance(item, dict)
        and item.get("forward_judgment_id") == forward_judgment_id
        and item.get("stage") == "TERMINAL_OPERATING"
    ]
    return claim if len(terminal_signals) == 1 else None


def _contains_forbidden_term(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_TERMS:
                return str(key)
            nested = _contains_forbidden_term(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = _contains_forbidden_term(item)
            if nested:
                return nested
    return None


def validate_method_evaluation_plan(
    plan: Any, *, selection_register: dict[str, Any] | None = None,
    frozen_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate the pre-outcome scope of one finite L5 comparison cohort."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(plan, dict):
        return {"state": "INVALID", "invalid_findings": ["plan_not_object"], "incomplete_findings": []}
    allowed = {
        "schema_version", "plan_id", "cohort", "evaluation_units", "minimum_independent_company_clusters",
        "aggregation_rule", "freeze",
    }
    invalid.extend("unsupported_field:" + field for field in _unsupported_fields(plan, allowed))
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(plan.get("plan_id") or "").startswith(PLAN_ID_PREFIX):
        incomplete.append("plan_id_missing_or_invalid")
    if _contains_forbidden_term(plan):
        invalid.append("price_return_probability_or_score_field_forbidden:" + str(_contains_forbidden_term(plan)))

    cohort = plan.get("cohort")
    cohort_fields = {"register_id", "register_fingerprint", "screen_entries"}
    if not isinstance(cohort, dict):
        incomplete.append("cohort_missing")
        cohort = {}
    else:
        invalid.extend("cohort:unsupported_field:" + field for field in _unsupported_fields(cohort, cohort_fields))
    screen_entries = cohort.get("screen_entries") if isinstance(cohort.get("screen_entries"), list) else []
    if not screen_entries:
        incomplete.append("cohort_screen_entries_missing")
    screen_by_id: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(screen_entries):
        prefix = f"cohort.screen_entries[{index}]"
        if not isinstance(entry, dict):
            invalid.append(prefix + ":not_object")
            continue
        unsupported = _unsupported_fields(entry, {
            "selection_entry_id", "disposition", "reason", "no_primary_case_id", "no_primary_freeze_id",
        })
        invalid.extend(prefix + ":unsupported_field:" + field for field in unsupported)
        entry_id = str(entry.get("selection_entry_id") or "").strip()
        if not entry_id:
            incomplete.append(prefix + ":selection_entry_id_missing")
            continue
        if entry_id in screen_by_id:
            invalid.append(prefix + ":selection_entry_id_duplicate:" + entry_id)
        screen_by_id[entry_id] = entry
        if entry.get("disposition") not in SCREEN_DISPOSITIONS:
            invalid.append(prefix + ":disposition_invalid")
        if not str(entry.get("reason") or "").strip():
            incomplete.append(prefix + ":reason_missing")
        if entry.get("disposition") == "EXCLUDED_NO_PRIMARY":
            for field in ("no_primary_case_id", "no_primary_freeze_id"):
                if not str(entry.get(field) or "").strip():
                    incomplete.append(prefix + ":" + field + "_missing")
        elif any(str(entry.get(field) or "").strip() for field in ("no_primary_case_id", "no_primary_freeze_id")):
            invalid.append(prefix + ":no_primary_case_fields_only_supported_for_excluded_no_primary")

    register_entries: dict[str, dict[str, Any]] = {}
    if selection_register is None:
        incomplete.append("selection_register_required")
    else:
        register_validation = validate_case_selection_register(selection_register)
        if register_validation.get("state") != "REVIEWABLE":
            invalid.append("selection_register_not_reviewable")
        register_id = str(selection_register.get("register_id") or "")
        fingerprint = str((selection_register.get("freeze") or {}).get("fingerprint") or "")
        if cohort.get("register_id") != register_id:
            invalid.append("cohort_register_id_mismatch")
        if cohort.get("register_fingerprint") != fingerprint:
            invalid.append("cohort_register_fingerprint_mismatch")
        if fingerprint and fingerprint != case_selection_register_fingerprint(selection_register):
            invalid.append("selection_register_fingerprint_mismatch")
        register_entries = {
            str(item.get("entry_id")): item for item in selection_register.get("entries") or []
            if isinstance(item, dict) and str(item.get("entry_id") or "").strip()
        }
        missing_screens = sorted(set(register_entries) - set(screen_by_id))
        extra_screens = sorted(set(screen_by_id) - set(register_entries))
        invalid.extend("cohort_screen_entry_missing:" + item for item in missing_screens)
        invalid.extend("cohort_screen_entry_not_in_register:" + item for item in extra_screens)
        screen_company_ids: set[str] = set()
        for entry_id in sorted(screen_by_id):
            registered = register_entries.get(entry_id)
            if registered is None:
                continue
            company_id = str(registered.get("company_id") or "")
            if company_id in screen_company_ids:
                invalid.append("cohort_screen_company_id_duplicate:" + company_id)
            screen_company_ids.add(company_id)

    units = plan.get("evaluation_units") if isinstance(plan.get("evaluation_units"), list) else []
    if not units:
        incomplete.append("evaluation_units_missing")
    unit_ids: set[str] = set()
    case_ids: set[str] = set()
    claim_ids: set[str] = set()
    company_ids: set[str] = set()
    company_clusters: set[str] = set()
    unit_selection_entry_ids: set[str] = set()
    case_index = {
        str(item.get("case_id")): item for item in frozen_cases or []
        if isinstance(item, dict) and str(item.get("case_id") or "").strip()
    }
    for index, unit in enumerate(units):
        prefix = f"evaluation_units[{index}]"
        if not isinstance(unit, dict):
            invalid.append(prefix + ":not_object")
            continue
        allowed_unit = {
            "episode_id", "selection_entry_id", "company_id", "company_cluster_id", "case_id", "freeze_id",
            "claim_id", "forward_judgment_id", "outcome_not_before",
        }
        invalid.extend(prefix + ":unsupported_field:" + field for field in _unsupported_fields(unit, allowed_unit))
        for field in allowed_unit:
            if not str(unit.get(field) or "").strip():
                incomplete.append(prefix + ":" + field + "_missing")
        episode_id = str(unit.get("episode_id") or "")
        if episode_id and not episode_id.startswith(EPISODE_ID_PREFIX):
            invalid.append(prefix + ":episode_id_invalid")
        if episode_id in unit_ids:
            invalid.append(prefix + ":episode_id_duplicate:" + episode_id)
        unit_ids.add(episode_id)
        for value, seen, label in (
            (str(unit.get("case_id") or ""), case_ids, "case_id"),
            (str(unit.get("claim_id") or ""), claim_ids, "claim_id"),
            (str(unit.get("company_id") or ""), company_ids, "company_id"),
            (str(unit.get("company_cluster_id") or ""), company_clusters, "company_cluster_id"),
        ):
            if value in seen:
                invalid.append(prefix + ":" + label + "_duplicate:" + value)
            seen.add(value)
        outcome_not_before = _day(unit.get("outcome_not_before"))
        if outcome_not_before is None:
            invalid.append(prefix + ":outcome_not_before_invalid")
        screen = screen_by_id.get(str(unit.get("selection_entry_id") or ""))
        if screen is None or screen.get("disposition") != "INCLUDED_SELECTION_EPISODE":
            invalid.append(prefix + ":selection_entry_not_included_selection_episode")
        unit_selection_entry_ids.add(str(unit.get("selection_entry_id") or ""))
        registered = register_entries.get(str(unit.get("selection_entry_id") or ""))
        if registered is not None and registered.get("company_id") != unit.get("company_id"):
            invalid.append(prefix + ":company_id_does_not_match_selection_register")
        if registered is not None and (registered.get("cluster") or {}).get("company_id") != unit.get("company_cluster_id"):
            invalid.append(prefix + ":company_cluster_id_does_not_match_selection_register")
        if frozen_cases is not None:
            case = case_index.get(str(unit.get("case_id") or ""))
            if case is None:
                invalid.append(prefix + ":frozen_case_missing")
            else:
                frozen_id = str((case.get("report_freeze") or {}).get("freeze_id") or "")
                if unit.get("freeze_id") != frozen_id:
                    invalid.append(prefix + ":freeze_id_does_not_match_frozen_case")
                claim = _selected_terminal_judgment(case, str(unit.get("forward_judgment_id") or ""))
                if claim is None:
                    invalid.append(prefix + ":not_a_selected_terminal_forward_judgment")
                elif claim.get("claim_id") != unit.get("claim_id"):
                    invalid.append(prefix + ":claim_id_does_not_match_selected_terminal_judgment")
                else:
                    window = (claim.get("observable_outcome") or {}).get("observation_window") or {}
                    opens = _day(window.get("opens_after"))
                    if opens is None or outcome_not_before != opens:
                        invalid.append(prefix + ":outcome_not_before_does_not_match_frozen_observation_window")
                admission = (case.get("calibration_ledger") or {}).get("selection_admission") or {}
                binding = admission.get("selection_register_binding") if isinstance(admission, dict) else None
                if not isinstance(binding, dict):
                    invalid.append(prefix + ":selection_register_binding_missing_from_frozen_case")
                else:
                    expected_binding = {
                        "register_id": cohort.get("register_id"),
                        "register_fingerprint": cohort.get("register_fingerprint"),
                        "selection_entry_id": unit.get("selection_entry_id"),
                        "company_id": unit.get("company_id"),
                        "company_cluster_id": unit.get("company_cluster_id"),
                    }
                    for field, expected in expected_binding.items():
                        if binding.get(field) != expected:
                            invalid.append(prefix + ":selection_register_binding_" + field + "_mismatch")

    included_screen_entry_ids = {
        entry_id for entry_id, entry in screen_by_id.items()
        if entry.get("disposition") == "INCLUDED_SELECTION_EPISODE"
    }
    for entry_id in sorted(included_screen_entry_ids - unit_selection_entry_ids):
        invalid.append("included_screen_entry_without_evaluation_unit:" + entry_id)
    for entry_id in sorted(unit_selection_entry_ids - included_screen_entry_ids):
        invalid.append("evaluation_unit_without_included_screen_entry:" + entry_id)

    if frozen_cases is not None:
        no_primary_case_ids: set[str] = set()
        for entry_id, entry in sorted(screen_by_id.items()):
            if entry.get("disposition") != "EXCLUDED_NO_PRIMARY":
                continue
            prefix = "cohort.screen_entries:" + entry_id
            case_id = str(entry.get("no_primary_case_id") or "")
            freeze_id = str(entry.get("no_primary_freeze_id") or "")
            if case_id in case_ids or case_id in no_primary_case_ids:
                invalid.append(prefix + ":no_primary_case_id_reused")
            no_primary_case_ids.add(case_id)
            case = case_index.get(case_id)
            if case is None:
                invalid.append(prefix + ":no_primary_frozen_case_missing")
                continue
            if str((case.get("report_freeze") or {}).get("freeze_id") or "") != freeze_id:
                invalid.append(prefix + ":no_primary_freeze_id_does_not_match_frozen_case")
            admission = ((case.get("calibration_ledger") or {}).get("selection_admission") or {})
            if not isinstance(admission, dict) or admission.get("status") != "NO_PRIMARY":
                invalid.append(prefix + ":case_is_not_frozen_no_primary")
                continue
            binding = admission.get("selection_register_binding")
            registered = register_entries.get(entry_id) or {}
            expected_binding = {
                "register_id": cohort.get("register_id"),
                "register_fingerprint": cohort.get("register_fingerprint"),
                "selection_entry_id": entry_id,
                "company_id": registered.get("company_id"),
                "company_cluster_id": (registered.get("cluster") or {}).get("company_id"),
            }
            if not isinstance(binding, dict):
                invalid.append(prefix + ":selection_register_binding_missing_from_frozen_case")
            else:
                for field, expected in expected_binding.items():
                    if binding.get(field) != expected:
                        invalid.append(prefix + ":selection_register_binding_" + field + "_mismatch")

    minimum = plan.get("minimum_independent_company_clusters")
    if not isinstance(minimum, int) or minimum < 2:
        invalid.append("minimum_independent_company_clusters_must_be_at_least_two")
    elif units and minimum > len(company_clusters):
        incomplete.append("minimum_independent_company_clusters_exceeds_frozen_cohort")
    rule = plan.get("aggregation_rule")
    expected_rule = {
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "outcome_boundary": "NON_PRICE_OPERATING_ONLY",
        "forecast_commitment": "NO_PROBABILITY",
        "unit": "ONE_SELECTED_TERMINAL_FJ_PER_INDEPENDENT_COMPANY_CLUSTER",
        "direct_comparison": "BINARY_FROZEN_PREDICATE_LOSS",
        "retention": "RETAIN_ALL_PLANNED_UNITS_AND_NONDIAGNOSTIC_OUTCOMES",
    }
    if rule != expected_rule:
        invalid.append("aggregation_rule_must_equal_frozen_nonprice_contract")

    freeze = plan.get("freeze")
    if not isinstance(freeze, dict) or freeze.get("frozen") is not True:
        incomplete.append("freeze_missing")
    else:
        frozen_at = _day(freeze.get("frozen_at"))
        if frozen_at is None:
            invalid.append("freeze_frozen_at_invalid")
        if freeze.get("fingerprint") != method_evaluation_plan_fingerprint(plan):
            invalid.append("freeze_fingerprint_mismatch")
        if frozen_at is not None:
            for index, unit in enumerate(units):
                outcome_not_before = _day(unit.get("outcome_not_before")) if isinstance(unit, dict) else None
                if outcome_not_before is not None and frozen_at >= outcome_not_before:
                    invalid.append(f"evaluation_units[{index}]:plan_not_frozen_before_outcome_window")

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    return {
        "state": "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "independent_company_clusters": sorted(cluster for cluster in company_clusters if cluster),
    }


def prepare_method_evaluation_plan(plan: dict[str, Any], *, frozen_at: str) -> dict[str, Any]:
    """Create the immutable plan receipt; validation still checks its inputs."""
    payload = deepcopy(plan)
    payload["schema_version"] = PLAN_SCHEMA_VERSION
    payload["freeze"] = {"frozen": True, "frozen_at": frozen_at, "fingerprint": ""}
    payload["freeze"]["fingerprint"] = method_evaluation_plan_fingerprint(payload)
    return payload


def freeze_method_evaluation_plan(
    plan: dict[str, Any], *, frozen_at: str, selection_register: dict[str, Any],
    frozen_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze an L5 plan only after its selected cases prove the same cohort link."""
    payload = prepare_method_evaluation_plan(plan, frozen_at=frozen_at)
    validation = validate_method_evaluation_plan(
        payload, selection_register=selection_register, frozen_cases=frozen_cases,
    )
    if validation["state"] != "REVIEWABLE":
        raise MethodEvaluationError("plan_not_reviewable:" + ",".join(
            validation["invalid_findings"] + validation["incomplete_findings"]
        ))
    return payload


def _planned_cards(plan: dict[str, Any], feedbacks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cards_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for feedback in feedbacks:
        if not isinstance(feedback, dict):
            raise MethodEvaluationError("feedback_not_object")
        case_id = str(feedback.get("case_id") or "")
        freeze_id = str(feedback.get("freeze_id") or "")
        for card in feedback.get("cards") or []:
            if not isinstance(card, dict):
                continue
            key = (case_id, freeze_id, str(card.get("claim_id") or ""), str(card.get("forward_judgment_id") or ""))
            if key in cards_by_key:
                raise MethodEvaluationError("duplicate_feedback_card_for_planned_identity")
            cards_by_key[key] = card
    planned: dict[str, dict[str, Any]] = {}
    for unit in plan.get("evaluation_units") or []:
        key = (
            str(unit.get("case_id") or ""), str(unit.get("freeze_id") or ""),
            str(unit.get("claim_id") or ""), str(unit.get("forward_judgment_id") or ""),
        )
        card = cards_by_key.get(key)
        if card is None:
            raise MethodEvaluationError("planned_feedback_card_missing:" + str(unit.get("episode_id") or ""))
        planned[str(unit.get("episode_id"))] = card
    return planned


def aggregate_method_relative_feedback(
    plan: dict[str, Any], feedbacks: list[dict[str, Any]], *, selection_register: dict[str, Any],
) -> dict[str, Any]:
    """Describe a complete frozen cohort without converting it to a score."""
    validation = validate_method_evaluation_plan(plan, selection_register=selection_register)
    if validation["state"] != "REVIEWABLE":
        raise MethodEvaluationError("plan_not_reviewable:" + ",".join(
            validation["invalid_findings"] + validation["incomplete_findings"]
        ))
    planned_cards = _planned_cards(plan, feedbacks)
    rows: list[dict[str, Any]] = []
    selection_counts = {outcome: 0 for outcome in sorted(SELECTION_OUTCOMES)}
    increment_counts = {outcome: 0 for outcome in sorted(INCREMENT_OUTCOMES)}
    for unit in plan.get("evaluation_units") or []:
        episode_id = str(unit.get("episode_id"))
        card = planned_cards[episode_id]
        selection = card.get("selection_learning") if isinstance(card.get("selection_learning"), dict) else {}
        selection_outcome = str(selection.get("outcome") or "")
        increment = str(card.get("increment_vs_baseline") or "")
        rival = card.get("rival_hypothesis_feedback") if isinstance(card.get("rival_hypothesis_feedback"), dict) else {}
        if selection_outcome not in SELECTION_OUTCOMES:
            raise MethodEvaluationError("selection_learning_outcome_invalid:" + episode_id)
        if increment not in INCREMENT_OUTCOMES:
            raise MethodEvaluationError("increment_vs_baseline_invalid:" + episode_id)
        if rival.get("signal_stage") != "TERMINAL_OPERATING":
            raise MethodEvaluationError("selection_feedback_not_from_terminal_signal:" + episode_id)
        if selection.get("admission_status") != "SELECTION_ADMITTED":
            raise MethodEvaluationError("selection_feedback_not_admitted:" + episode_id)
        selection_counts[selection_outcome] += 1
        increment_counts[increment] += 1
        rows.append({
            "episode_id": episode_id,
            "company_cluster_id": unit.get("company_cluster_id"),
            "selection_outcome": selection_outcome,
            "increment_vs_baseline": increment,
            "settlement_status": card.get("settlement_status"),
        })
    screen_entries = deepcopy((plan.get("cohort") or {}).get("screen_entries") or [])
    screen_disposition_counts = {disposition: 0 for disposition in sorted(SCREEN_DISPOSITIONS)}
    for entry in screen_entries:
        if isinstance(entry, dict) and entry.get("disposition") in screen_disposition_counts:
            screen_disposition_counts[entry["disposition"]] += 1
    settled_rows = [row for row in rows if row["selection_outcome"] != "NOT_EVALUATED"]
    minimum = int(plan["minimum_independent_company_clusters"])
    if len(settled_rows) < len(rows):
        state = "PENDING_FROZEN_OUTCOMES"
    elif len({str(row["company_cluster_id"]) for row in settled_rows}) < minimum:
        state = "INSUFFICIENT_INDEPENDENT_EPISODES"
    else:
        state = "DESCRIPTIVE_COMPARISON_READY"
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "plan_id": plan.get("plan_id"),
        "state": state,
        "investment_return": "SEPARATE_NOT_INCLUDED",
        "interpretation_boundary": (
            "Counts frozen operating predicates and retained non-diagnostic outcomes; it is not "
            "a probability, accuracy rate, method score, or evidence of general judgment superiority."
        ),
        "selection_coverage_boundary": (
            "The directional comparison is conditional on frozen INCLUDED_SELECTION_EPISODE units. "
            "EXCLUDED_NO_PRIMARY is an abstention/insufficient-evidence disposition, not a direction win; "
            "EXCLUDED_NONCOMPARABLE is not an unobserved prediction. These categories remain visible and "
            "must not be combined into a single method score."
        ),
        "cohort_accounting": {
            "planned_selection_episodes": len(rows),
            "settled_selection_episodes": len(settled_rows),
            "independent_company_clusters": sorted({str(row["company_cluster_id"]) for row in rows}),
            "minimum_independent_company_clusters": minimum,
            "selection_outcome_counts": selection_counts,
            "increment_vs_baseline_counts": increment_counts,
            "screen_disposition_counts": screen_disposition_counts,
            "screen_entry_dispositions": screen_entries,
        },
        "episodes": rows,
    }
