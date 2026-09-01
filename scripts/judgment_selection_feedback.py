#!/usr/bin/env python3
"""Validate and project a frozen selection-development outcome.

This module is intentionally pure: it reads no files, writes no database, and
does not acquire outcomes.  The caller must supply the independently frozen
case, measurement contract, control registration, and a custodian-produced
outcome.  Directional verdicts are derived only where the frozen contract
contains both primary and rival comparison rules.
"""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime
from typing import Any

try:
    from scripts.judgment_selection_peer import (
        conjunct_absolute_and_peer_verdict,
        peer_relative_card_observation,
        validate_peer_contract_binding,
        validate_peer_relative_outcome,
    )
except ModuleNotFoundError:
    from judgment_selection_peer import (
        conjunct_absolute_and_peer_verdict,
        peer_relative_card_observation,
        validate_peer_contract_binding,
        validate_peer_relative_outcome,
    )


OUTCOME_SCHEMA_VERSION = "judgment-selection-outcome.v1"
VALIDATION_SCHEMA_VERSION = "judgment-selection-outcome-validation.v1"
FEEDBACK_SCHEMA_VERSION = "judgment-selection-feedback-card.v1"
AMENDMENT_SCHEMA_VERSION = "judgment-selection-resolution-amendment.v1"
AMENDMENT_REVIEW_SCHEMA_VERSION = "judgment-selection-resolution-amendment-review.v1"
ACTIVATION_SCHEMA_VERSION = "judgment-selection-resolution-activation.v1"

SELECTION_STATUSES = {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH", "NOT_DIAGNOSTIC"}
SELECTION_VERDICTS = {"A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"}
REQUIRED_STAGE_IDS = (
    "D1_IMPLEMENTATION",
    "D2_CUSTOMER_ABSORPTION",
    "D3_UNIT_ECONOMICS",
    "D4_WORKING_CAPITAL_AND_CASH",
    "D5_CAPITAL_RETURN",
)
SELECTION_STAGE_ORDERS = (
    REQUIRED_STAGE_IDS,
    (
        "D1_IMPLEMENTATION",
        "D2_CUSTOMER_ABSORPTION",
        "D3_PRODUCT_VOLUME",
        "D3_UNIT_ECONOMICS",
        "D4_WORKING_CAPITAL_AND_CASH",
        "D5_CAPITAL_RETURN",
    ),
)
ALLOWED_STAGE_IDS = set().union(*SELECTION_STAGE_ORDERS)
STAGE_CLOCKS = {
    "D1_IMPLEMENTATION": "D1",
    "D2_CUSTOMER_ABSORPTION": "D2",
    "D3_PRODUCT_VOLUME": "D3",
    "D3_UNIT_ECONOMICS": "D3",
    "D4_WORKING_CAPITAL_AND_CASH": "D4",
    "D5_CAPITAL_RETURN": "D5",
}
PROHIBITED_OUTPUTS = (
    "selection_accuracy",
    "probability",
    "win_rate",
    "investment_return",
    "security_return",
    "portfolio_conclusion",
)
CALLER_VERDICT_KEYS = {
    "selection_verdict",
    "signal_verdict",
    "comparison_verdict",
    "hit",
    "miss",
    "binary_outcome",
    "binary_verdict",
    "selection_hit_miss",
    "probability",
    "win_rate",
    "investment_return",
    "security_return",
    "portfolio_conclusion",
}


class SelectionFeedbackError(ValueError):
    """Raised when selection feedback would depart from frozen identities."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _forbidden_key_paths(value: Any, *, path: str = "outcome") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in CALLER_VERDICT_KEYS:
                findings.append(child + ":caller_supplied_verdict_or_prohibited_output")
            findings.extend(_forbidden_key_paths(item, path=child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_key_paths(item, path=f"{path}[{index}]"))
    return findings


def _artifact_maps(
    frozen_case: dict[str, Any], measurement_contract: dict[str, Any], registration: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    findings: list[str] = []
    if not isinstance(frozen_case, dict):
        return [], {}, {}, {}, ["frozen_case_not_object"]
    if not isinstance(measurement_contract, dict):
        return [], {}, {}, {}, ["measurement_contract_not_object"]
    if not isinstance(registration, dict):
        return [], {}, {}, {}, ["registration_not_object"]

    case_id = _text(frozen_case.get("case_id"))
    freeze_id = _text(frozen_case.get("freeze_id"))
    if not case_id:
        findings.append("frozen_case.case_id_missing")
    if not freeze_id:
        findings.append("frozen_case.freeze_id_missing")
    if frozen_case.get("selection_status") != "SELECTION_ADMITTED":
        findings.append("frozen_case.selection_status_must_be_selection_admitted")
    if measurement_contract.get("schema_version") != "judgment-selection-measurement-contract.v1":
        findings.append("measurement_contract.schema_version_invalid")
    if measurement_contract.get("case_id") != case_id:
        findings.append("measurement_contract.case_id_mismatch")
    if measurement_contract.get("freeze_id") != freeze_id:
        findings.append("measurement_contract.freeze_id_mismatch")
    if measurement_contract.get("selection_status") != "SELECTION_ADMITTED":
        findings.append("measurement_contract.selection_status_must_be_selection_admitted")
    if registration.get("episode_id") != case_id:
        findings.append("registration.episode_id_mismatch")
    if registration.get("selection_status") != "SELECTION_ADMITTED":
        findings.append("registration.selection_status_must_be_selection_admitted")
    if registration.get("learning_eligibility") != "SELECTION_METHOD_ELIGIBLE":
        findings.append("registration.learning_eligibility_invalid")

    items = registration.get("feedback_items")
    if not isinstance(items, list):
        findings.append("registration.feedback_items_must_contain_five_or_six_claims")
        items = []
    elif len(items) not in {5, 6}:
        findings.append("registration.feedback_items_must_contain_five_or_six_claims")
    registered_claim_ids: list[str] = []
    registration_by_claim: dict[str, dict[str, Any]] = {}
    stage_ids: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            findings.append(f"registration.feedback_items[{index}]:not_object")
            continue
        claim_id = _text(item.get("claim_id"))
        stage_id = _text(item.get("stage_id"))
        if not claim_id:
            findings.append(f"registration.feedback_items[{index}]:claim_id_missing")
        if stage_id not in ALLOWED_STAGE_IDS:
            findings.append(f"registration.feedback_items[{index}]:stage_id_invalid")
        registered_claim_ids.append(claim_id)
        stage_ids.append(stage_id)
        registration_by_claim[claim_id] = item
    if _duplicates(registered_claim_ids):
        findings.append("registration.claim_ids_duplicate")
    stage_order = tuple(stage_ids)
    if _duplicates(stage_ids) or stage_order not in SELECTION_STAGE_ORDERS:
        findings.append("registration.stage_ids_must_follow_ordered_five_layer_selection_topology")

    rules = measurement_contract.get("measurement_rules")
    if not isinstance(rules, list):
        findings.append("measurement_contract.measurement_rules_must_match_registered_claim_count")
        rules = []
    elif len(rules) != len(items):
        findings.append("measurement_contract.measurement_rules_must_match_registered_claim_count")
    rule_by_predicate: dict[str, dict[str, Any]] = {}
    rule_predicate_ids: list[str] = []
    rule_clocks: list[str] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            findings.append(f"measurement_contract.measurement_rules[{index}]:not_object")
            continue
        predicate_id = _text(rule.get("predicate_id"))
        clock = _text(rule.get("clock"))
        if not predicate_id:
            findings.append(f"measurement_contract.measurement_rules[{index}]:predicate_id_missing")
        if clock not in {"D1", "D2", "D3", "D4", "D5"}:
            findings.append(f"measurement_contract.measurement_rules[{index}]:clock_invalid")
        if not _text(rule.get("required_observation")):
            findings.append(f"measurement_contract.measurement_rules[{index}]:required_observation_missing")
        prohibited = rule.get("prohibited_substitutes")
        if not isinstance(prohibited, list) or not prohibited or not all(_text(item) for item in prohibited):
            findings.append(f"measurement_contract.measurement_rules[{index}]:prohibited_substitutes_invalid")
        if predicate_id in rule_by_predicate:
            findings.append("measurement_contract.predicate_ids_duplicate")
        rule_predicate_ids.append(predicate_id)
        rule_clocks.append(clock)
        rule_by_predicate[predicate_id] = rule
    expected_clocks = [STAGE_CLOCKS[stage_id] for stage_id in stage_ids if stage_id in STAGE_CLOCKS]
    if stage_order in SELECTION_STAGE_ORDERS and rule_clocks != expected_clocks:
        findings.append("measurement_contract.clock_shape_invalid")
    d5_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("clock") == "D5"]
    if d5_rules:
        diagnostic = d5_rules[0].get("diagnostic_mode")
        if not isinstance(diagnostic, dict) or diagnostic.get("state") != "CONTINUOUS_UNKNOWN_NO_SELECTION_HIT_MISS":
            findings.append("measurement_contract.d5_must_be_continuous_no_selection_hit_miss")
        if any(key in d5_rules[0] for key in ("primary_test", "rival_test", "selection_test")):
            findings.append("measurement_contract.d5_binary_rule_prohibited")
    admission = frozen_case.get("selection_admission_contract")
    if isinstance(admission, dict) \
            and admission.get("version") == "JUDGMENT_SELECTION_ADMISSION_V4" \
            and admission.get("mechanism_topology") == "COST_RESTRUCTURING_CHAIN":
        d2_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("clock") == "D2"]
        if len(d2_rules) != 1 or any(
            key in d2_rules[0] for key in ("primary_test", "rival_test", "selection_test", "baseline_prediction")
        ):
            findings.append("measurement_contract.cost_restructuring_d2_must_remain_non_voter")

    predictions = frozen_case.get("frozen_prediction_order")
    if not isinstance(predictions, list):
        findings.append("frozen_case.predictions_must_match_registered_claim_count")
        predictions = []
    elif len(predictions) != len(items):
        findings.append("frozen_case.predictions_must_match_registered_claim_count")
    prediction_predicate_ids = [
        _text(item.get("predicate_id")) for item in predictions if isinstance(item, dict)
    ]
    prediction_stage_ids = [
        _text(item.get("stage")) for item in predictions if isinstance(item, dict)
    ]
    prediction_by_predicate = {
        _text(item.get("predicate_id")): item
        for item in predictions
        if isinstance(item, dict) and _text(item.get("predicate_id"))
    }
    if len(prediction_by_predicate) != len(prediction_predicate_ids):
        findings.append("frozen_case.predicate_ids_duplicate_or_missing")
    if prediction_stage_ids != stage_ids:
        findings.append("frozen_case.prediction_stages_must_match_registered_selection_topology")
    if rule_predicate_ids != prediction_predicate_ids:
        findings.append("measurement_contract.predicate_order_must_match_frozen_case")
    if set(prediction_by_predicate) != set(rule_by_predicate):
        findings.append("frozen_case.predicates_do_not_match_measurement_contract")
    if not isinstance(frozen_case.get("rival_hypothesis_pair"), dict):
        findings.append("frozen_case.rival_hypothesis_pair_missing")
    if not isinstance(frozen_case.get("fair_simple_baseline"), dict):
        findings.append("frozen_case.fair_simple_baseline_missing")
    return registered_claim_ids, registration_by_claim, rule_by_predicate, prediction_by_predicate, findings


def _frozen_claim_predicate_bindings(
    registrations: dict[str, dict[str, Any]], rules: dict[str, dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Bind claims to the exact stage identities frozen before outcome access."""
    bindings: dict[str, str] = {}
    for claim_id, registration in registrations.items():
        stage_id = _text(registration.get("stage_id"))
        candidates = [
            predicate_id for predicate_id, prediction in predictions.items()
            if prediction.get("stage") == stage_id
            and predicate_id in rules
            and rules[predicate_id].get("clock") == STAGE_CLOCKS.get(stage_id)
        ]
        if len(candidates) == 1:
            bindings[claim_id] = candidates[0]
    return bindings


def validate_selection_resolution_amendment(
    resolution_amendment: dict[str, Any], *, frozen_case: dict[str, Any],
    measurement_contract: dict[str, Any], registration: dict[str, Any],
) -> dict[str, Any]:
    """Validate the append-only, pre-outcome joint-resolution rules."""
    registered_ids, registrations, rules, predictions, findings = _artifact_maps(
        frozen_case, measurement_contract, registration,
    )
    claim_predicates = _frozen_claim_predicate_bindings(registrations, rules, predictions)
    if not isinstance(resolution_amendment, dict):
        return {
            "schema_version": "judgment-selection-resolution-amendment-validation.v1",
            "state": "INVALID",
            "findings": findings + ["resolution_amendment_not_object"],
        }
    if resolution_amendment.get("schema_version") != AMENDMENT_SCHEMA_VERSION:
        findings.append("resolution_amendment.schema_version_invalid")
    if resolution_amendment.get("case_id") != frozen_case.get("case_id"):
        findings.append("resolution_amendment.case_id_mismatch")
    if resolution_amendment.get("freeze_id") != frozen_case.get("freeze_id"):
        findings.append("resolution_amendment.freeze_id_mismatch")
    if resolution_amendment.get("amendment_status") != "CANDIDATE_PENDING_INDEPENDENT_REVIEW":
        findings.append("resolution_amendment.status_invalid")
    author_id = _text(resolution_amendment.get("author_id"))
    selector_id = _text(resolution_amendment.get("selector_id"))
    if not author_id:
        findings.append("resolution_amendment.author_id_missing")
    if not selector_id:
        findings.append("resolution_amendment.selector_id_missing")
    if author_id and selector_id and author_id == selector_id:
        findings.append("resolution_amendment.author_and_selector_must_be_distinct")
    if resolution_amendment.get("append_only_scope") != "RESOLUTION_RULES_ONLY_NO_FROZEN_PREDICTION_OR_MEASUREMENT_CHANGE":
        findings.append("resolution_amendment.append_only_scope_invalid")
    if resolution_amendment.get("amended_artifacts") != [
        "01_case_freeze.json", "03_outcome_acquisition_contract.json", "04_measurement_contract.json",
    ]:
        findings.append("resolution_amendment.amended_artifacts_invalid")
    if resolution_amendment.get("pre_outcome_review_ref") != "02_independent_pre_outcome_review.json":
        findings.append("resolution_amendment.pre_outcome_review_ref_invalid")
    if resolution_amendment.get("registered_claim_ids") != registered_ids:
        findings.append("resolution_amendment.registered_claim_ids_mismatch")
    if resolution_amendment.get("independent_review_required") is not True:
        findings.append("resolution_amendment.independent_review_required_must_be_true")
    if resolution_amendment.get("execution_authorized") is not False:
        findings.append("resolution_amendment.execution_must_remain_unauthorized")
    created_at = _parse_datetime(resolution_amendment.get("created_at"))
    cutoff_at = _parse_datetime(frozen_case.get("cutoff_at"))
    if created_at is None:
        findings.append("resolution_amendment.created_at_invalid")
    elif cutoff_at and created_at <= cutoff_at:
        findings.append("resolution_amendment.created_at_not_after_cutoff")

    joint = resolution_amendment.get("joint_selection_resolution")
    central_claim_ids: list[str] = []
    if not isinstance(joint, dict):
        findings.append("resolution_amendment.joint_selection_resolution_missing")
    else:
        central_claim_ids = joint.get("input_claim_ids") if isinstance(joint.get("input_claim_ids"), list) else []
        central_predicate_ids = joint.get("input_predicate_ids") if isinstance(joint.get("input_predicate_ids"), list) else []
        expected_central_claims = [
            claim_id for claim_id in registered_ids
            if (registrations.get(claim_id) or {}).get("stage_id") in {"D3_UNIT_ECONOMICS", "D4_WORKING_CAPITAL_AND_CASH"}
        ]
        directional_predicates = [
            predicate_id for predicate_id, rule in rules.items()
            if isinstance(rule.get("primary_test"), dict) and isinstance(rule.get("rival_test"), dict)
        ]
        if central_claim_ids != expected_central_claims:
            findings.append("resolution_amendment.central_claim_ids_mismatch")
        if central_predicate_ids != directional_predicates:
            findings.append("resolution_amendment.central_predicate_ids_mismatch")
        if joint.get("mapping_key_order") != central_claim_ids:
            findings.append("resolution_amendment.mapping_key_order_mismatch")
        vocabulary = joint.get("input_verdict_vocabulary")
        if not isinstance(vocabulary, list) or set(vocabulary) != SELECTION_VERDICTS or len(vocabulary) != len(SELECTION_VERDICTS):
            findings.append("resolution_amendment.input_verdict_vocabulary_invalid")
            vocabulary = []
        mapping = joint.get("mapping")
        expected_keys = {f"{left}|{right}" for left in vocabulary for right in vocabulary}
        if not isinstance(mapping, dict) or set(mapping) != expected_keys:
            findings.append("resolution_amendment.joint_mapping_incomplete")
        else:
            for key, verdict in mapping.items():
                left, right = key.split("|", 1)
                expected = (
                    "NOT_DIAGNOSTIC"
                    if "NOT_DIAGNOSTIC" in {left, right}
                    else left
                    if left == right and left in {"A_ONLY", "B_ONLY"}
                    else "MIXED"
                )
                if verdict != expected:
                    findings.append("resolution_amendment.joint_mapping_rule_invalid:" + key)

    baseline = resolution_amendment.get("simple_baseline_resolution")
    if not isinstance(baseline, dict):
        findings.append("resolution_amendment.simple_baseline_resolution_missing")
    else:
        expected_baseline_claims = [
            claim_id for claim_id in registered_ids
            if (registrations.get(claim_id) or {}).get("stage_id") != "D5_CAPITAL_RETURN"
            and isinstance(rules.get(claim_predicates.get(claim_id, "")), dict)
            and (
                rules[claim_predicates[claim_id]].get("baseline_prediction") or {}
            ).get("operator") == "EQUAL_POINT_FORECAST"
        ]
        if not expected_baseline_claims:
            findings.append("resolution_amendment.frozen_point_baseline_count_invalid")
        if baseline.get("input_claim_ids") != expected_baseline_claims:
            findings.append("resolution_amendment.baseline_claim_ids_mismatch")
        identities = baseline.get("point_identities")
        if not isinstance(identities, list) or len(identities) != len(expected_baseline_claims):
            findings.append("resolution_amendment.baseline_point_identities_invalid")
            identities = []
        identity_claim_ids: list[str] = []
        for index, identity in enumerate(identities):
            prefix = f"resolution_amendment.baseline_point_identities[{index}]"
            if not isinstance(identity, dict):
                findings.append(prefix + ":not_object")
                continue
            claim_id = _text(identity.get("claim_id"))
            predicate_id = _text(identity.get("predicate_id"))
            identity_claim_ids.append(claim_id)
            expected_predicate_id = claim_predicates.get(claim_id)
            rule = rules.get(expected_predicate_id or "")
            frozen_point = rule.get("baseline_prediction") if isinstance(rule, dict) else None
            if claim_id not in expected_baseline_claims:
                findings.append(prefix + ":claim_id_invalid")
            if not isinstance(frozen_point, dict):
                findings.append(prefix + ":predicate_has_no_frozen_point_baseline")
            elif (
                predicate_id != expected_predicate_id
                or identity.get("point_value") != frozen_point.get("value")
                or identity.get("unit") != frozen_point.get("unit")
                or frozen_point.get("operator") != "EQUAL_POINT_FORECAST"
            ):
                findings.append(prefix + ":point_identity_mismatch")
        if identity_claim_ids != expected_baseline_claims:
            findings.append("resolution_amendment.baseline_point_order_mismatch")
        loss = baseline.get("loss_function")
        if not isinstance(loss, dict) or (
            loss.get("name") != "MEAN_ABSOLUTE_RELATIVE_POINT_LOSS"
            or loss.get("component") != {
                "operator": "ABSOLUTE_RELATIVE_ERROR",
                "denominator": "ABS_POINT_VALUE",
            }
            or loss.get("aggregate") != {
                "operator": "ARITHMETIC_MEAN",
                "weights": "EQUAL_COMPONENT_WEIGHT",
            }
            or loss.get("rounding") != "NONE_BEFORE_RESOLUTION"
        ):
            findings.append("resolution_amendment.baseline_loss_function_invalid")
        resolution_rule = baseline.get("resolution_rule")
        expected_resolution_rule = {
            "zero_loss": {"state": "ZERO_BASELINE_POINT_LOSS", "operator": "EQUALS", "value": 0.0},
            "positive_loss": {"state": "BASELINE_POINT_LOSS", "operator": "GREATER_THAN", "value": 0.0},
            "non_diagnostic": {
                "state": "NOT_DIAGNOSTIC",
                "input_statuses": ["UNKNOWN", "MEASUREMENT_MISMATCH", "NOT_DIAGNOSTIC"],
                "require_all_inputs_observed": True,
            },
        }
        if resolution_rule != expected_resolution_rule:
            findings.append("resolution_amendment.baseline_resolution_rule_invalid")

    expected_diagnostic = [claim_id for claim_id in registered_ids if claim_id not in central_claim_ids]
    diagnostic_rows = resolution_amendment.get("diagnostic_only_claims")
    diagnostic_ids = [
        _text(item.get("claim_id")) for item in diagnostic_rows or [] if isinstance(item, dict)
    ] if isinstance(diagnostic_rows, list) else []
    if diagnostic_ids != expected_diagnostic or any(not _text(item.get("reason")) for item in diagnostic_rows or [] if isinstance(item, dict)):
        findings.append("resolution_amendment.diagnostic_only_claims_mismatch")
    if set(claim_predicates) != set(registered_ids) or set(claim_predicates.values()) != set(rules):
        findings.append("resolution_amendment.claim_predicate_bindings_incomplete")
    joint_claims = (joint or {}).get("input_claim_ids") if isinstance(joint, dict) else []
    joint_predicates = (joint or {}).get("input_predicate_ids") if isinstance(joint, dict) else []
    for claim_id, predicate_id in zip(joint_claims or [], joint_predicates or [], strict=False):
        if claim_predicates.get(claim_id) != predicate_id:
            findings.append("resolution_amendment.claim_predicate_binding_conflict:" + _text(claim_id))
    for identity in (baseline or {}).get("point_identities") or [] if isinstance(baseline, dict) else []:
        if isinstance(identity, dict) and claim_predicates.get(_text(identity.get("claim_id"))) != identity.get("predicate_id"):
            findings.append("resolution_amendment.claim_predicate_binding_conflict:" + _text(identity.get("claim_id")))
    status = resolution_amendment.get("status_preservation")
    if not isinstance(status, dict) or set(status.get("allowed") or []) != SELECTION_STATUSES:
        findings.append("resolution_amendment.status_preservation_invalid")
    firewall = resolution_amendment.get("outcome_firewall_attestation")
    if not isinstance(firewall, dict) or firewall.get("post_cutoff_metadata_access") != "NONE" or firewall.get("post_cutoff_body_access") != "NONE":
        findings.append("resolution_amendment.outcome_firewall_invalid")
    return {
        "schema_version": "judgment-selection-resolution-amendment-validation.v1",
        "state": "INVALID" if findings else "CANDIDATE_REVIEWABLE",
        "findings": findings,
    }


def validate_selection_resolution_activation(
    resolution_amendment: dict[str, Any], amendment_review_receipt: dict[str, Any],
    activation_receipt: dict[str, Any], *, outcome: dict[str, Any],
) -> dict[str, Any]:
    """Require independent pre-access review and explicit execution activation."""
    findings: list[str] = []
    if not isinstance(amendment_review_receipt, dict):
        findings.append("amendment_review_receipt_not_object")
        amendment_review_receipt = {}
    if amendment_review_receipt.get("schema_version") != AMENDMENT_REVIEW_SCHEMA_VERSION:
        findings.append("amendment_review_receipt.schema_version_invalid")
    for field in ("case_id", "freeze_id", "amendment_id", "author_id", "selector_id"):
        expected_field = "amendment_id" if field == "amendment_id" else field
        if amendment_review_receipt.get(field) != resolution_amendment.get(expected_field):
            findings.append("amendment_review_receipt." + field + "_mismatch")
    if amendment_review_receipt.get("status") != "INDEPENDENTLY_ACCEPTED_PRE_OUTCOME":
        findings.append("amendment_review_receipt.status_not_accepted")
    if not _text(amendment_review_receipt.get("review_id")):
        findings.append("amendment_review_receipt.review_id_missing")
    reviewer_id = _text(amendment_review_receipt.get("reviewer_id"))
    author_id = _text(resolution_amendment.get("author_id"))
    selector_id = _text(resolution_amendment.get("selector_id"))
    if not reviewer_id:
        findings.append("amendment_review_receipt.reviewer_id_missing")
    if reviewer_id in {author_id, selector_id}:
        findings.append("amendment_review_receipt.reviewer_not_independent")
    if amendment_review_receipt.get("reviewed_amendment") != resolution_amendment:
        findings.append("amendment_review_receipt.snapshot_mismatch")

    if not isinstance(activation_receipt, dict):
        findings.append("activation_receipt_not_object")
        activation_receipt = {}
    if activation_receipt.get("schema_version") != ACTIVATION_SCHEMA_VERSION:
        findings.append("activation_receipt.schema_version_invalid")
    for field in ("case_id", "freeze_id", "amendment_id"):
        if activation_receipt.get(field) != resolution_amendment.get(field):
            findings.append("activation_receipt." + field + "_mismatch")
    if activation_receipt.get("amendment_review_id") != amendment_review_receipt.get("review_id"):
        findings.append("activation_receipt.amendment_review_id_mismatch")
    if activation_receipt.get("activation_status") != "ACTIVE_FOR_OUTCOME_SETTLEMENT":
        findings.append("activation_receipt.status_not_active")
    if not _text(activation_receipt.get("activation_id")):
        findings.append("activation_receipt.activation_id_missing")
    if activation_receipt.get("activation_source") != "CONTROL_DB_RECONSTRUCTED":
        findings.append("activation_receipt.source_not_canonical_control_db")
    expected_activation = {
        "program_state": "ACTIVE",
        "program_reservation_status": "REGISTERED",
        "feedback_control_registration_status": "REGISTERED",
        "outcome_release_status": "RELEASED_TO_INDEPENDENT_CUSTODIAN",
    }
    for field, expected in expected_activation.items():
        if activation_receipt.get(field) != expected:
            findings.append("activation_receipt." + field + "_invalid")
    if activation_receipt.get("registered_claim_ids") != resolution_amendment.get("registered_claim_ids"):
        findings.append("activation_receipt.registered_claim_ids_mismatch")
    for field in ("program_id", "training_episode_id", "outcome_release_event_id"):
        if not _text(activation_receipt.get(field)):
            findings.append("activation_receipt." + field + "_missing")
    program_event_id = _text(activation_receipt.get("program_reservation_event_id"))
    if not program_event_id.startswith("JTAE:"):
        findings.append("activation_receipt.program_reservation_event_id_invalid")
    registration_events = activation_receipt.get("feedback_control_registration_event_ids")
    expected_claim_ids = resolution_amendment.get("registered_claim_ids")
    if not isinstance(registration_events, dict) or list(registration_events) != expected_claim_ids:
        findings.append("activation_receipt.feedback_control_registration_event_ids_mismatch")
    elif (
        not all(_text(event_id) for event_id in registration_events.values())
        or len(set(registration_events.values())) != len(registration_events)
    ):
        findings.append("activation_receipt.feedback_control_registration_event_ids_invalid")
    custodian_id = _text(activation_receipt.get("custodian_id"))
    if not custodian_id:
        findings.append("activation_receipt.custodian_id_missing")
    if len({author_id, selector_id, reviewer_id, custodian_id}) != 4:
        findings.append("activation_receipt.author_selector_reviewer_custodian_must_be_distinct")
    for field, expected in (
        ("activation_id", activation_receipt.get("activation_id")),
        ("amendment_review_id", amendment_review_receipt.get("review_id")),
        ("custodian_id", custodian_id),
    ):
        if outcome.get(field) != expected:
            findings.append("outcome." + field + "_mismatch")

    clock_values = {
        "amendment_created_at": resolution_amendment.get("created_at"),
        "reviewed_at": amendment_review_receipt.get("reviewed_at"),
        "recorded_at": amendment_review_receipt.get("recorded_at"),
        "activated_at": activation_receipt.get("activated_at"),
        "activation_recorded_at": activation_receipt.get("recorded_at"),
        "first_outcome_accessed_at": outcome.get("first_outcome_accessed_at"),
        "settlement_as_of": outcome.get("settlement_as_of"),
    }
    clocks = {name: _parse_datetime(value) for name, value in clock_values.items()}
    for name, value in clocks.items():
        if value is None:
            findings.append(f"{name}_invalid")
    if all(value is not None for value in clocks.values()):
        ordered = [
            clocks["amendment_created_at"], clocks["reviewed_at"], clocks["recorded_at"],
            clocks["activated_at"], clocks["activation_recorded_at"],
            clocks["first_outcome_accessed_at"], clocks["settlement_as_of"],
        ]
        if any(left > right for left, right in zip(ordered, ordered[1:])):
            findings.append("amendment_review_activation_outcome_clock_order_invalid")
    return {
        "schema_version": "judgment-selection-resolution-activation-validation.v1",
        "state": "INVALID" if findings else "ACTIVATED",
        "findings": findings,
    }


def validate_selection_outcome(
    outcome: dict[str, Any], *, frozen_case: dict[str, Any],
    measurement_contract: dict[str, Any], registration: dict[str, Any],
    resolution_amendment: dict[str, Any],
    amendment_review_receipt: dict[str, Any], activation_receipt: dict[str, Any],
    source_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one custodian-produced selection outcome against frozen inputs."""
    registered_ids, registrations, rules, predictions, findings = _artifact_maps(
        frozen_case, measurement_contract, registration,
    )
    amendment_validation = validate_selection_resolution_amendment(
        resolution_amendment, frozen_case=frozen_case,
        measurement_contract=measurement_contract, registration=registration,
    )
    findings.extend("resolution_amendment:" + item for item in amendment_validation["findings"])
    if amendment_validation["state"] != "CANDIDATE_REVIEWABLE":
        findings.append("resolution_amendment:not_a_reviewable_candidate")
    activation_validation = validate_selection_resolution_activation(
        resolution_amendment, amendment_review_receipt, activation_receipt,
        outcome=outcome if isinstance(outcome, dict) else {},
    )
    findings.extend("resolution_activation:" + item for item in activation_validation["findings"])
    amendment_predicates = _frozen_claim_predicate_bindings(registrations, rules, predictions)
    if not isinstance(outcome, dict):
        return {"schema_version": VALIDATION_SCHEMA_VERSION, "state": "INVALID", "findings": findings + ["outcome_not_object"]}
    if outcome.get("schema_version") != OUTCOME_SCHEMA_VERSION:
        findings.append("outcome.schema_version_invalid")
    case_id = _text(frozen_case.get("case_id"))
    freeze_id = _text(frozen_case.get("freeze_id"))
    for field, expected in (("case_id", case_id), ("freeze_id", freeze_id)):
        if outcome.get(field) != expected:
            findings.append(f"outcome.{field}_mismatch")
    for field in ("settlement_id", "settlement_as_of", "first_outcome_accessed_at"):
        if not _text(outcome.get(field)):
            findings.append(f"outcome.{field}_missing")
    if outcome.get("selection_status") != "SELECTION_ADMITTED":
        findings.append("outcome.selection_status_must_be_selection_admitted")

    cutoff_at = _parse_datetime(frozen_case.get("cutoff_at"))
    settlement_at = _parse_datetime(outcome.get("settlement_as_of"))
    first_access_at = _parse_datetime(outcome.get("first_outcome_accessed_at"))
    if settlement_at is None:
        findings.append("outcome.settlement_as_of_invalid")
    if first_access_at is None:
        findings.append("outcome.first_outcome_accessed_at_invalid")
    if cutoff_at is None:
        findings.append("frozen_case.cutoff_at_invalid")
    if cutoff_at and first_access_at and first_access_at <= cutoff_at:
        findings.append("outcome.first_outcome_accessed_at_not_after_cutoff")
    if settlement_at and first_access_at and settlement_at < first_access_at:
        findings.append("outcome.settlement_as_of_before_first_access")

    identity = outcome.get("measurement_contract_identity")
    if not isinstance(identity, dict):
        findings.append("outcome.measurement_contract_identity_missing")
    else:
        for field, expected in (
            ("schema_version", measurement_contract.get("schema_version")),
            ("case_id", case_id),
            ("freeze_id", freeze_id),
        ):
            if identity.get(field) != expected:
                findings.append(f"outcome.measurement_contract_identity.{field}_mismatch")
    if outcome.get("registered_claim_ids") != registered_ids:
        findings.append("outcome.registered_claim_ids_mismatch")

    prohibited_outputs = outcome.get("prohibited_outputs")
    if not isinstance(prohibited_outputs, list) or not set(PROHIBITED_OUTPUTS).issubset(set(prohibited_outputs)):
        findings.append("outcome.prohibited_outputs_incomplete")
    findings.extend(_forbidden_key_paths({key: value for key, value in outcome.items() if key != "prohibited_outputs"}))

    claims = outcome.get("claims")
    if not isinstance(claims, list) or len(claims) != len(registered_ids):
        findings.append(
            "outcome.claims_must_contain_six_registered_claims"
            if len(registered_ids) == 6
            else "outcome.claims_must_contain_five_registered_claims"
        )
        claims = []
    outcome_claim_ids = [_text(claim.get("claim_id")) for claim in claims if isinstance(claim, dict)]
    if outcome_claim_ids != registered_ids:
        findings.append("outcome.claim_order_or_identity_mismatch")
    if _duplicates(outcome_claim_ids):
        findings.append("outcome.claim_ids_duplicate")

    used_predicates: list[str] = []
    for index, claim in enumerate(claims):
        prefix = f"outcome.claims[{index}]"
        if not isinstance(claim, dict):
            findings.append(prefix + ":not_object")
            continue
        claim_id = _text(claim.get("claim_id"))
        registration_item = registrations.get(claim_id)
        if registration_item is None:
            findings.append(prefix + ":claim_not_registered")
            continue
        stage_id = _text(claim.get("stage_id"))
        if stage_id != registration_item.get("stage_id"):
            findings.append(prefix + ":stage_id_mismatch")
        predicate_id = _text(claim.get("predicate_id"))
        rule = rules.get(predicate_id)
        if rule is None:
            findings.append(prefix + ":predicate_not_in_measurement_contract")
            continue
        if amendment_predicates.get(claim_id) != predicate_id:
            findings.append(prefix + ":predicate_does_not_match_resolution_amendment")
        used_predicates.append(predicate_id)
        if rule.get("clock") != STAGE_CLOCKS.get(stage_id):
            findings.append(prefix + ":predicate_clock_does_not_match_stage")
        prediction = predictions.get(predicate_id)
        if prediction is None:
            findings.append(prefix + ":predicate_not_in_frozen_case")

        status = claim.get("status")
        if status not in SELECTION_STATUSES:
            findings.append(prefix + ":status_invalid")
        source_ids = claim.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids or not all(_text(item) for item in source_ids):
            findings.append(prefix + ":source_ids_missing_or_invalid")
        elif len(source_ids) != len(set(source_ids)):
            findings.append(prefix + ":source_ids_duplicate")
        required_scope = rule.get("required_observation")
        if claim.get("measurement_scope") != required_scope:
            findings.append(prefix + ":measurement_scope_does_not_match_frozen_contract")
        prohibited = rule.get("prohibited_substitutes")
        if claim.get("prohibited_substitutes") != prohibited:
            findings.append(prefix + ":prohibited_substitutes_do_not_match_frozen_contract")

        if status == "OBSERVED":
            measured = _text(claim.get("observed_measurement"))
            if not measured:
                findings.append(prefix + ":observed_measurement_missing")
            elif measured.casefold() in {_text(item).casefold() for item in prohibited or []}:
                findings.append(prefix + ":uses_prohibited_substitute")
            elif measured != required_scope:
                findings.append(prefix + ":observed_measurement_not_required_scope")
            if not _text(claim.get("observation_summary")):
                findings.append(prefix + ":observation_summary_missing")
            comparison_rules = [rule.get(name) for name in ("primary_test", "rival_test", "baseline_prediction") if isinstance(rule.get(name), dict)]
            if comparison_rules:
                value = _number(claim.get("observed_value"))
                if value is None:
                    findings.append(prefix + ":numeric_value_required_for_frozen_comparison")
                units = {_text(item.get("unit")) for item in comparison_rules}
                if len(units) != 1 or claim.get("observed_unit") not in units:
                    findings.append(prefix + ":observed_unit_does_not_match_frozen_comparison")
            elif "observed_value" in claim and _number(claim.get("observed_value")) is None:
                findings.append(prefix + ":observed_value_invalid")
        else:
            if not _text(claim.get("resolution_reason")):
                findings.append(prefix + ":resolution_reason_missing")
            if "observed_value" in claim or "observed_unit" in claim:
                findings.append(prefix + ":non_observed_status_cannot_carry_scored_value")

        if stage_id == "D2_CUSTOMER_ABSORPTION" and any(key in claim for key in CALLER_VERDICT_KEYS):
            findings.append(prefix + ":d2_volume_cannot_be_selection_hit")
        if stage_id == "D5_CAPITAL_RETURN":
            if any(key in claim for key in CALLER_VERDICT_KEYS | {"threshold", "selection_test"}):
                findings.append(prefix + ":d5_continuous_read_cannot_be_binary")
            if any(isinstance(rule.get(name), dict) for name in ("primary_test", "rival_test", "selection_test")):
                findings.append(prefix + ":d5_frozen_contract_cannot_produce_selection_verdict")

    if set(used_predicates) != set(rules) or len(used_predicates) != len(set(used_predicates)):
        findings.append(
            "outcome.predicates_must_match_six_frozen_rules_once"
            if len(rules) == 6
            else "outcome.predicates_must_match_five_frozen_rules_once"
        )
    if source_contract is not None or isinstance(frozen_case.get("peer_panel_observability"), dict):
        if not isinstance(source_contract, dict):
            findings.append("peer_binding.source_contract_required_for_v4")
        else:
            findings.extend(validate_peer_contract_binding(
                frozen_case, source_contract, measurement_contract,
            ))
            _, peer_findings = validate_peer_relative_outcome(
                outcome,
                candidate=frozen_case,
                source_contract=source_contract,
                measurement_contract=measurement_contract,
            )
            findings.extend(peer_findings)
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "INVALID" if findings else "REVIEWABLE",
        "findings": findings,
    }


def _evaluate_rule(rule: dict[str, Any] | None, *, value: Any, unit: Any) -> dict[str, Any]:
    if not isinstance(rule, dict):
        return {"status": "NO_FROZEN_RULE"}
    observed = _number(value)
    target = _number(rule.get("value"))
    if observed is None or target is None or unit != rule.get("unit"):
        raise SelectionFeedbackError("validated comparison value no longer matches its frozen rule")
    operator = rule.get("operator")
    matched = {
        "GREATER_THAN": observed > target,
        "GREATER_THAN_OR_EQUAL": observed >= target,
        "LESS_THAN": observed < target,
        "LESS_THAN_OR_EQUAL": observed <= target,
        "EQUALS": observed == target,
        "EQUAL_POINT_FORECAST": observed == target,
    }.get(operator)
    if matched is None:
        raise SelectionFeedbackError("frozen comparison operator is unsupported")
    return {
        "status": "MET" if matched else "MISSED",
        "operator": operator,
        "target_value": target,
        "observed_value": observed,
        "unit": unit,
    }


def _selection_verdict(primary: dict[str, Any], rival: dict[str, Any], *, observation_status: str) -> str:
    if observation_status != "OBSERVED" or primary.get("status") == "NO_FROZEN_RULE" or rival.get("status") == "NO_FROZEN_RULE":
        return "NOT_DIAGNOSTIC"
    primary_met = primary.get("status") == "MET"
    rival_met = rival.get("status") == "MET"
    if primary_met and not rival_met:
        return "A_ONLY"
    if rival_met and not primary_met:
        return "B_ONLY"
    if primary_met and rival_met:
        return "MIXED"
    return "NOT_DIAGNOSTIC"


def resolve_joint_selection(
    resolution_amendment: dict[str, Any], per_item_verdicts: dict[str, str],
) -> dict[str, str]:
    """Resolve the central pair exclusively through the amendment mapping."""
    joint = resolution_amendment.get("joint_selection_resolution")
    if not isinstance(joint, dict):
        raise SelectionFeedbackError("resolution amendment has no joint mapping")
    order = joint.get("mapping_key_order")
    mapping = joint.get("mapping")
    if not isinstance(order, list) or not isinstance(mapping, dict):
        raise SelectionFeedbackError("resolution amendment joint mapping is malformed")
    try:
        key = "|".join(per_item_verdicts[claim_id] for claim_id in order)
    except KeyError as exc:
        raise SelectionFeedbackError("joint resolution is missing a central claim verdict") from exc
    verdict = mapping.get(key)
    if verdict not in SELECTION_VERDICTS:
        raise SelectionFeedbackError("resolution amendment produced an invalid overall verdict")
    return {"mapping_key": key, "overall_verdict": verdict}


def build_selection_feedback(
    outcome: dict[str, Any], *, frozen_case: dict[str, Any],
    measurement_contract: dict[str, Any], registration: dict[str, Any],
    resolution_amendment: dict[str, Any],
    amendment_review_receipt: dict[str, Any], activation_receipt: dict[str, Any],
    source_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build claim feedback and an amendment-derived joint verdict, never a score."""
    validation = validate_selection_outcome(
        outcome, frozen_case=frozen_case,
        measurement_contract=measurement_contract, registration=registration,
        resolution_amendment=resolution_amendment,
        amendment_review_receipt=amendment_review_receipt,
        activation_receipt=activation_receipt,
        source_contract=source_contract,
    )
    if validation["state"] != "REVIEWABLE":
        raise SelectionFeedbackError("invalid selection outcome: " + "; ".join(validation["findings"]))
    registered_ids, registrations, rules, predictions, artifact_findings = _artifact_maps(
        frozen_case, measurement_contract, registration,
    )
    if artifact_findings:
        raise SelectionFeedbackError("invalid frozen artifacts: " + "; ".join(artifact_findings))
    outcome_by_claim = {item["claim_id"]: item for item in outcome["claims"]}
    peer_derived: dict[str, dict[str, Any]] = {}
    if source_contract is not None:
        peer_derived, peer_findings = validate_peer_relative_outcome(
            outcome,
            candidate=frozen_case,
            source_contract=source_contract,
            measurement_contract=measurement_contract,
        )
        if peer_findings:
            raise SelectionFeedbackError("invalid V4 peer outcome: " + "; ".join(peer_findings))
    pair = frozen_case["rival_hypothesis_pair"]
    primary_hypothesis = pair["primary_hypothesis"]
    rival_hypothesis = pair["strongest_rival"]
    baseline = frozen_case["fair_simple_baseline"]

    cards: list[dict[str, Any]] = []
    central_claim_ids: list[str] = []
    diagnostic_claim_ids: list[str] = []
    for claim_id in registered_ids:
        claim = outcome_by_claim[claim_id]
        rule = rules[claim["predicate_id"]]
        prediction = predictions[claim["predicate_id"]]
        if claim["status"] == "OBSERVED":
            primary_result = _evaluate_rule(rule.get("primary_test"), value=claim.get("observed_value"), unit=claim.get("observed_unit"))
            rival_result = _evaluate_rule(rule.get("rival_test"), value=claim.get("observed_value"), unit=claim.get("observed_unit"))
            baseline_result = _evaluate_rule(rule.get("baseline_prediction"), value=claim.get("observed_value"), unit=claim.get("observed_unit"))
        else:
            preserved = {"status": claim["status"], "reason": claim["resolution_reason"]}
            primary_result = deepcopy(preserved)
            rival_result = deepcopy(preserved)
            baseline_result = deepcopy(preserved)
        absolute_verdict = _selection_verdict(primary_result, rival_result, observation_status=claim["status"])
        peer_relative: dict[str, Any] | None = None
        verdict = absolute_verdict
        if registrations[claim_id]["stage_id"] in peer_derived:
            derived = peer_derived[registrations[claim_id]["stage_id"]]
            peer_primary, peer_rival, peer_verdict = peer_relative_card_observation(
                rule, derived=derived, evaluate_rule=_evaluate_rule,
            )
            verdict = conjunct_absolute_and_peer_verdict(absolute_verdict, peer_verdict)
            peer_relative = {
                "frozen_rule": deepcopy(rule.get("peer_relative_test")),
                "target_scalar": derived["target_scalar"],
                "target_margin_reference": derived["target_margin_reference"],
                "target_margin_outcome": derived["target_margin_outcome"],
                "target_delta": derived["target_delta"],
                "peer_deltas": deepcopy(derived["peer_deltas"]),
                "median_peer_delta": derived["median_peer_delta"],
                "relative_delta_vs_peer_median": derived["relative_delta_vs_peer_median"],
                "unit": "ratio",
                "primary_result": peer_primary,
                "rival_result": peer_rival,
                "verdict": peer_verdict,
                "derivation": "RAW_SOURCE_BACKED_FIELDS_RECOMPUTED_NO_CALLER_SUPPLIED_PEER_VERDICT",
            }
        if verdict not in SELECTION_VERDICTS:
            raise SelectionFeedbackError("derived selection verdict is outside the frozen vocabulary")
        has_directional_pair = isinstance(rule.get("primary_test"), dict) and isinstance(rule.get("rival_test"), dict)
        (central_claim_ids if has_directional_pair else diagnostic_claim_ids).append(claim_id)
        cards.append({
            "claim_id": claim_id,
            "predicate_id": claim["predicate_id"],
            "stage_id": registrations[claim_id]["stage_id"],
            "observation": {
                "status": claim["status"],
                "source_ids": deepcopy(claim["source_ids"]),
                "measurement_scope": claim["measurement_scope"],
                "prohibited_substitutes": deepcopy(claim["prohibited_substitutes"]),
                "summary": claim.get("observation_summary") or claim.get("resolution_reason"),
                "value": claim.get("observed_value"),
                "unit": claim.get("observed_unit"),
            },
            "comparison": {
                "primary_hypothesis": {
                    "hypothesis_id": primary_hypothesis["hypothesis_id"],
                    "frozen_prediction": prediction.get("primary_prediction"),
                    "frozen_rule": deepcopy(rule.get("primary_test")),
                    "result": primary_result,
                },
                "strongest_rival": {
                    "hypothesis_id": rival_hypothesis["hypothesis_id"],
                    "frozen_prediction": prediction.get("rival_prediction"),
                    "frozen_rule": deepcopy(rule.get("rival_test")),
                    "result": rival_result,
                },
                "simple_baseline": {
                    "baseline_id": baseline["baseline_id"],
                    "frozen_prediction": prediction.get("baseline_prediction"),
                    "frozen_rule": deepcopy(rule.get("baseline_prediction")),
                    "result": baseline_result,
                },
                "absolute_verdict": absolute_verdict,
                "peer_relative": peer_relative,
                "verdict": verdict,
                "role": "CENTRAL_DISCRIMINATOR" if has_directional_pair else "DIAGNOSTIC_ONLY",
                "derivation": (
                    "FROZEN_ABSOLUTE_AND_PEER_RELATIVE_RULES_CONJOINED_NO_CALLER_SUPPLIED_WINNER"
                    if peer_relative is not None
                    else "FROZEN_RULES_ONLY_NO_CALLER_SUPPLIED_WINNER"
                ),
            },
        })

    per_item_verdicts = {card["claim_id"]: card["comparison"]["verdict"] for card in cards}
    joint_resolution = resolve_joint_selection(resolution_amendment, per_item_verdicts)
    mapping_key = joint_resolution["mapping_key"]
    overall_verdict = joint_resolution["overall_verdict"]

    baseline_contract = resolution_amendment["simple_baseline_resolution"]
    baseline_loss_contract = baseline_contract["loss_function"]
    baseline_rule = baseline_contract["resolution_rule"]
    baseline_components: list[dict[str, Any]] = []
    baseline_input_statuses: dict[str, str] = {}
    for identity in baseline_contract["point_identities"]:
        claim = outcome_by_claim[identity["claim_id"]]
        baseline_input_statuses[identity["claim_id"]] = claim["status"]
        if claim["status"] != "OBSERVED":
            continue
        observed = _number(claim.get("observed_value"))
        point = _number(identity.get("point_value"))
        if observed is None or point is None or point == 0 or claim.get("observed_unit") != identity.get("unit"):
            raise SelectionFeedbackError("validated baseline point input no longer matches the amendment")
        baseline_components.append({
            "claim_id": identity["claim_id"],
            "predicate_id": identity["predicate_id"],
            "observed_value": observed,
            "point_value": point,
            "unit": identity["unit"],
            "absolute_relative_point_loss": abs(observed - point) / abs(point),
        })
    if len(baseline_components) != len(baseline_contract["point_identities"]):
        baseline_resolution = {
            "state": baseline_rule["non_diagnostic"]["state"],
            "input_statuses": baseline_input_statuses,
            "component_losses": baseline_components,
            "aggregate_loss": None,
        }
    else:
        aggregate_loss = sum(item["absolute_relative_point_loss"] for item in baseline_components) / len(baseline_components)
        baseline_resolution = {
            "state": (
                baseline_rule["zero_loss"]["state"]
                if aggregate_loss == baseline_rule["zero_loss"]["value"]
                else baseline_rule["positive_loss"]["state"]
            ),
            "input_statuses": baseline_input_statuses,
            "component_losses": baseline_components,
            "aggregate_loss": aggregate_loss,
        }

    return {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "case_id": outcome["case_id"],
        "freeze_id": outcome["freeze_id"],
        "settlement_id": outcome["settlement_id"],
        "settlement_as_of": outcome["settlement_as_of"],
        "first_outcome_accessed_at": outcome["first_outcome_accessed_at"],
        "activation_id": outcome["activation_id"],
        "amendment_review_id": outcome["amendment_review_id"],
        "custodian_id": outcome["custodian_id"],
        "selection_status": "SELECTION_ADMITTED",
        "primary_hypothesis_id": primary_hypothesis["hypothesis_id"],
        "strongest_rival_id": rival_hypothesis["hypothesis_id"],
        "simple_baseline_id": baseline["baseline_id"],
        "cards": cards,
        "joint_comparison": {
            "resolution_amendment_id": resolution_amendment["amendment_id"],
            "resolution_amendment_status": resolution_amendment["amendment_status"],
            "amendment_review_id": amendment_review_receipt["review_id"],
            "activation_id": activation_receipt["activation_id"],
            "central_discriminator_claim_ids": central_claim_ids,
            "diagnostic_only_claim_ids": diagnostic_claim_ids,
            "per_item_verdicts": per_item_verdicts,
            "mapping_key": mapping_key,
            "overall_verdict": overall_verdict,
            "derivation": "APPEND_ONLY_RESOLUTION_AMENDMENT_MAPPING_ONLY",
            "aggregation": "NO_WIN_RATE_PROBABILITY_OR_AUTOMATIC_METHOD_UPDATE",
        },
        "simple_baseline_resolution": {
            "resolution_amendment_id": resolution_amendment["amendment_id"],
            "loss_function": baseline_loss_contract["name"],
            **baseline_resolution,
            "selection_effect": "SEPARATE_COMPARATOR_CANNOT_CHANGE_OVERALL_VERDICT",
        },
        "control_activation_lineage": {
            "activation_source": activation_receipt["activation_source"],
            "program_id": activation_receipt["program_id"],
            "training_episode_id": activation_receipt["training_episode_id"],
            "program_reservation_event_id": activation_receipt["program_reservation_event_id"],
            "feedback_control_registration_event_ids": deepcopy(activation_receipt["feedback_control_registration_event_ids"]),
            "outcome_release_event_id": activation_receipt["outcome_release_event_id"],
            "activated_at": activation_receipt["activated_at"],
            "recorded_at": activation_receipt["recorded_at"],
        },
        "learning_scope": "SELECTION_METHOD_DEVELOPMENT_PENDING_INDEPENDENT_REVIEW",
        "prohibited_outputs": list(PROHIBITED_OUTPUTS),
    }
