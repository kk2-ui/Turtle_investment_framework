"""Small, shared P-23 measurement-reconstruction contract checks.

The contract is intentionally attached only to selected R-07 signals.  It
does not make an ordinary forward judgment invent a future label or locator.
"""

from __future__ import annotations

from typing import Any


MEASUREMENT_MISMATCH_ACTION = "MEASUREMENT_MISMATCH"
TARGET_FIELDS = ("source_type", "file_scope", "reported_label", "reported_locator")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def contract_findings(
    outcome: dict[str, Any], *, prefix: str, allowed_source_types: set[str],
) -> tuple[list[str], list[str]]:
    """Validate the compact P-23 contract frozen on one selected signal."""
    invalid: list[str] = []
    incomplete: list[str] = []
    contract = outcome.get("metric_reconstruction_contract")
    if not isinstance(contract, dict):
        return invalid, [prefix + ":metric_reconstruction_contract_missing"]

    targets = contract.get("source_targets")
    if not isinstance(targets, list) or not targets:
        incomplete.append(prefix + ":source_targets_missing")
        targets = []
    for index, target in enumerate(targets):
        target_prefix = f"{prefix}.source_targets[{index}]"
        if not isinstance(target, dict):
            invalid.append(target_prefix + ":not_object")
            continue
        for field in TARGET_FIELDS:
            if not _text(target.get(field)):
                incomplete.append(target_prefix + ":" + field + "_missing")
        source_type = str(target.get("source_type") or "")
        if source_type and source_type not in allowed_source_types:
            invalid.append(target_prefix + ":source_type_not_allowed_for_observable_outcome")

    prohibited = contract.get("prohibited_substitutes")
    if not isinstance(prohibited, list) or not prohibited:
        incomplete.append(prefix + ":prohibited_substitutes_missing")
    elif any(not _text(item) for item in prohibited):
        invalid.append(prefix + ":prohibited_substitutes_invalid")

    action = contract.get("definition_change_action")
    if not _text(action):
        incomplete.append(prefix + ":definition_change_action_missing")
    elif action != MEASUREMENT_MISMATCH_ACTION:
        invalid.append(prefix + ":definition_change_action_must_be_measurement_mismatch")

    conversion_rule = outcome.get("conversion_rule")
    if conversion_rule is not None:
        conversion_prefix = prefix + ".conversion_rule"
        if not isinstance(conversion_rule, dict):
            invalid.append(conversion_prefix + ":not_object")
        else:
            for field in ("rule_id", "raw_unit", "converted_unit"):
                if not _text(conversion_rule.get(field)):
                    incomplete.append(conversion_prefix + ":" + field + "_missing")
            multiplier = conversion_rule.get("multiplier")
            if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool) or multiplier <= 0:
                invalid.append(conversion_prefix + ":multiplier_invalid")
            if conversion_rule.get("converted_unit") not in (None, "") and conversion_rule.get("converted_unit") != outcome.get("unit"):
                invalid.append(conversion_prefix + ":converted_unit_does_not_match_observable_outcome")
    return invalid, incomplete


def observation_matches_contract(
    outcome: dict[str, Any], observation: dict[str, Any], actual_sources: dict[str, dict[str, Any]],
) -> bool:
    """Return whether a later comparable observation uses a frozen source target."""
    contract = outcome.get("metric_reconstruction_contract")
    if not isinstance(contract, dict):
        return True
    targets = contract.get("source_targets")
    if not isinstance(targets, list):
        return False
    source_types = {
        str(actual_sources[source_id].get("source_type") or "")
        for source_id in observation.get("source_ids") or []
        if source_id in actual_sources
    }
    for target in targets:
        if not isinstance(target, dict):
            continue
        if (
            target.get("source_type") in source_types
            and observation.get("reported_file_scope") == target.get("file_scope")
            and observation.get("reported_label") == target.get("reported_label")
            and observation.get("reported_locator") == target.get("reported_locator")
        ):
            return True
    return False


def observation_contract_findings(
    outcome: dict[str, Any], observation: dict[str, Any], actual_sources: dict[str, dict[str, Any]], *, prefix: str,
) -> tuple[list[str], list[str]]:
    """Require a comparable P-23 observation to match its frozen label/locator.

    A non-comparable observation is retained as the explicit measurement
    mismatch record.  It must not be promoted into a calculated metric, but
    it is not itself an invalid settlement.
    """
    if not isinstance(outcome.get("metric_reconstruction_contract"), dict):
        return [], []
    if observation.get("comparability_status") not in {
        "COMPARABLE", "CONVERTIBLE_WITH_PREREGISTERED_RULE",
    }:
        return [], []
    incomplete: list[str] = []
    for field in ("reported_file_scope", "reported_label", "reported_locator"):
        if not _text(observation.get(field)):
            incomplete.append(prefix + ":" + field + "_missing")
    if incomplete:
        return [], incomplete
    if not observation_matches_contract(outcome, observation, actual_sources):
        return [prefix + ":reported_disclosure_does_not_match_metric_reconstruction_contract"], []
    return [], []
