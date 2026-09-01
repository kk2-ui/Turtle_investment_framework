#!/usr/bin/env python3
"""Post-cutoff operating-outcome acquisition for frozen Turtle judgments.

This module intentionally sits *after* a company-judgment freeze.  It is not
another research ledger and it does not decide a mechanism winner.  Its job is
smaller: retain the bounded result-source inventory, raw/reader copies and a
read audit, then make a settlement observation replayable from an exact quote
in that reader copy.  ``historical_backtest`` remains the only place that
compares the frozen primary/rival predicates.

An issuer's complete web archive cannot be inferred from a downloaded page.
Accordingly ``enumeration`` records the bounded official query/export that the
researcher used.  A missing or incomplete enumeration is an explicit
``INCOMPLETE`` outcome, never a convenient initial/latest disclosure.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


OUTCOME_PACKAGE_SCHEMA_VERSION = "turtle-post-cutoff-outcome-package.v1"
OUTCOME_READ_ATTESTATION_SCHEMA_VERSION = "turtle-post-cutoff-outcome-read-attestation.v1"
OUTCOME_EXTRACTION_SCHEMA_VERSION = "turtle-post-cutoff-outcome-extraction.v1"
LIVE_FORWARD_OUTCOME_CONTRACT_SCHEMA_VERSION = "turtle-live-forward-outcome-contract.v1"
LIVE_FORWARD_EXECUTION_STATUS_SCHEMA_VERSION = "turtle-live-forward-execution-status.v1"
LIVE_FORWARD_DUE_INBOX_SCHEMA_VERSION = "turtle-live-forward-due-inbox.v1"
OFFICIAL_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT",
    "OFFICIAL_STATISTICS", "OTHER_OFFICIAL",
}
LICENSED_INDUSTRY_DATA = "LICENSED_INDUSTRY_DATA"
COMPARABLE_STATUSES = {"COMPARABLE", "CONVERTIBLE_WITH_PREREGISTERED_RULE"}
NON_DIAGNOSTIC_RESOLUTIONS = {"MEASUREMENT_MISMATCH", "NOT_DISCLOSED"}
SETTLEMENT_VERSION_POLICIES = {"INITIAL_DISCLOSURE", "LATEST_OFFICIAL_AS_OF_EVALUATION"}
MECHANISM_SIGNAL_OPERATORS = {
    "GREATER_THAN", "GREATER_THAN_OR_EQUAL", "LESS_THAN", "LESS_THAN_OR_EQUAL", "EQUALS",
}
OPERATING_CLOCKS = {
    "DECISION_IMPLEMENTATION", "CUSTOMER_COMPETITOR_RESPONSE", "UNIT_ECONOMICS",
    "WORKING_CAPITAL_CASH", "CAPITAL_RETURN",
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _complementary_mechanism_predictions(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Whether two simple frozen predicates partition one numeric signal."""
    left_value, right_value = _number(left.get("value")), _number(right.get("value"))
    if left_value is None or right_value is None or left_value != right_value:
        return False
    operators = (left.get("operator"), right.get("operator"))
    return operators in {
        ("GREATER_THAN", "LESS_THAN_OR_EQUAL"),
        ("LESS_THAN_OR_EQUAL", "GREATER_THAN"),
        ("GREATER_THAN_OR_EQUAL", "LESS_THAN"),
        ("LESS_THAN", "GREATER_THAN_OR_EQUAL"),
    }


def _package_file(root: Path, value: Any) -> Path | None:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        return None
    return resolved


def _load_object(path: Path | None, *, field: str) -> tuple[dict[str, Any], list[str]]:
    if path is None or not path.is_file():
        return {}, [field + "_missing"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}, [field + "_invalid_json"]
    return (value, []) if isinstance(value, dict) else ({}, [field + "_must_be_object"])


def _source_payload(source: dict[str, Any]) -> dict[str, Any]:
    """Project the source fields that an HBT operating settlement may use."""
    return {
        field: deepcopy(source.get(field))
        for field in (
            "source_id", "source_type", "official", "published_at", "source_version",
            "data_as_of", "revision_policy", "industry_data_contract",
        )
        if field in source
    } | {"content_access": "BODY_READ"}


def _observation_payload(extraction: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields that are allowed to enter ``actual_outcomes``."""
    fields = (
        "observation_id", "claim_id", "metric", "value", "unit", "measurement_basis",
        "measurement_period", "event_period", "source_ids", "comparability_status",
        "reported_file_scope", "reported_label", "reported_locator", "raw_value",
        "raw_unit", "conversion_rule_id",
    )
    return {field: deepcopy(extraction.get(field)) for field in fields if field in extraction}


def _claim_map(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ledger = case.get("calibration_ledger") if isinstance(case.get("calibration_ledger"), dict) else {}
    return {
        str(item.get("claim_id")): item
        for item in ledger.get("claims") or []
        if isinstance(item, dict) and str(item.get("claim_id") or "")
    }


def _publisher_domains(outcome: dict[str, Any]) -> set[str]:
    if isinstance(outcome.get("publisher_domains"), list):
        return {str(item).strip() for item in outcome["publisher_domains"] if _text(item)}
    return {str(outcome.get("publisher_domain")).strip()} if _text(outcome.get("publisher_domain")) else set()


def _version_policy_findings(
    outcome: dict[str, Any], claim_id: str, source_ids: list[str], sources: dict[str, dict[str, Any]], *, prefix: str,
) -> tuple[list[str], list[str]]:
    """Select an initial/latest result only among sources eligible for this claim.

    A source merely appearing in the issuer inventory is not a candidate for a
    claim when it is outside that claim's frozen type/domain/window.  This is
    important for result archives containing a press item before the reporting
    window or a later transcript on a different issuer domain.
    """
    domains = _publisher_domains(outcome)
    allowed = set(outcome.get("allowed_source_types") or [])
    window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
    opens, closes = _timestamp(window.get("opens_after")), _timestamp(window.get("closes_at"))
    candidates: list[tuple[str, datetime]] = []
    for source_id, source in sources.items():
        claim_ids = source.get("candidate_claim_ids")
        published = _timestamp(source.get("published_at"))
        if (
            not isinstance(claim_ids, list) or claim_id not in {str(item or "") for item in claim_ids}
            or source.get("source_type") not in allowed
            or (domains and source.get("official_publisher_domain") not in domains)
            or published is None
            or (opens is not None and published <= opens)
            or (closes is not None and published > closes)
        ):
            continue
        candidates.append((source_id, published))
    if not candidates:
        return [], [prefix + ":no_eligible_enumerated_candidate_source_for_claim"]
    policy = outcome.get("settlement_version_policy")
    required_time = (
        min(published for _, published in candidates)
        if policy == "INITIAL_DISCLOSURE"
        else max(published for _, published in candidates)
    )
    selected_times = {
        _timestamp(sources[source_id].get("published_at"))
        for source_id in source_ids if source_id in sources
    }
    if selected_times != {required_time}:
        required = "initial" if policy == "INITIAL_DISCLOSURE" else "latest"
        return [prefix + ":does_not_use_" + required + "_enumerated_disclosure"], []
    return [], []


def _source_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id")): item
        for item in manifest.get("inventory") or []
        if isinstance(item, dict) and str(item.get("source_id") or "")
    }


def validate_live_forward_outcome_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the machine-readable execution companion of a forward freeze.

    It deliberately contains only the result-source/metric reconstruction
    boundary already frozen in the accompanying research card.  It has no
    outcome value, price, return, probability or mechanism-winner field.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if contract.get("schema_version") != LIVE_FORWARD_OUTCOME_CONTRACT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if contract.get("purpose") != "POST_FREEZE_EXECUTION_ONLY_NO_NEW_CURRENT_FACT_OR_PREDICTION":
        invalid.append("purpose_invalid")
    for field in ("case_id", "report_freeze", "simulation_cutoff", "calibration_ledger"):
        if contract.get(field) in (None, ""):
            incomplete.append(field + "_missing")
    if not _text(contract.get("case_id")):
        incomplete.append("case_id_invalid")
    freeze = contract.get("report_freeze") if isinstance(contract.get("report_freeze"), dict) else {}
    if not _text(freeze.get("freeze_id")):
        incomplete.append("report_freeze:freeze_id_missing")
    if _timestamp(contract.get("simulation_cutoff")) is None:
        invalid.append("simulation_cutoff_invalid")
    ledger = contract.get("calibration_ledger") if isinstance(contract.get("calibration_ledger"), dict) else {}
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    claim_clocks: list[str] = []
    if not claims:
        incomplete.append("calibration_ledger:claims_missing")
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        prefix = f"calibration_ledger.claims[{index}]"
        if not isinstance(claim, dict):
            invalid.append(prefix + ":not_object")
            continue
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id:
            incomplete.append(prefix + ":claim_id_missing")
        elif claim_id in claim_ids:
            invalid.append(prefix + ":duplicate_claim_id:" + claim_id)
        claim_ids.add(claim_id)
        clock = claim.get("operating_clock")
        if clock is not None:
            if clock not in OPERATING_CLOCKS:
                invalid.append(prefix + ":operating_clock_invalid")
            else:
                claim_clocks.append(clock)
        outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
        for field in ("metric", "unit", "measurement_basis", "measurement_period", "allowed_source_types", "publisher_domains", "observation_window", "settlement_version_policy", "metric_reconstruction_contract"):
            if outcome.get(field) in (None, ""):
                incomplete.append(prefix + ".observable_outcome:" + field + "_missing")
        if not isinstance(outcome.get("measurement_period"), dict) or not outcome["measurement_period"].get("label"):
            invalid.append(prefix + ".observable_outcome:measurement_period_invalid")
        source_types = outcome.get("allowed_source_types") if isinstance(outcome.get("allowed_source_types"), list) else []
        if not source_types or any(item not in OFFICIAL_SOURCE_TYPES | {LICENSED_INDUSTRY_DATA} for item in source_types):
            invalid.append(prefix + ".observable_outcome:allowed_source_types_invalid")
        domains = outcome.get("publisher_domains") if isinstance(outcome.get("publisher_domains"), list) else []
        if not domains or any(not _text(item) for item in domains):
            invalid.append(prefix + ".observable_outcome:publisher_domains_invalid")
        window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
        opens, closes = _timestamp(window.get("opens_after")), _timestamp(window.get("closes_at"))
        if opens is None or closes is None or opens >= closes:
            invalid.append(prefix + ".observable_outcome:observation_window_invalid")
        if outcome.get("settlement_version_policy") not in SETTLEMENT_VERSION_POLICIES:
            invalid.append(prefix + ".observable_outcome:settlement_version_policy_invalid")
        reconstruction = outcome.get("metric_reconstruction_contract") if isinstance(outcome.get("metric_reconstruction_contract"), dict) else {}
        targets = reconstruction.get("source_targets") if isinstance(reconstruction.get("source_targets"), list) else []
        if not targets:
            incomplete.append(prefix + ".observable_outcome:metric_reconstruction_contract:source_targets_missing")
        for target_index, target in enumerate(targets):
            target_prefix = prefix + f".observable_outcome.metric_reconstruction_contract.source_targets[{target_index}]"
            if not isinstance(target, dict):
                invalid.append(target_prefix + ":not_object")
                continue
            for field in ("source_type", "file_scope", "reported_label", "reported_locator", "reported_period_anchor"):
                if not _text(target.get(field)):
                    incomplete.append(target_prefix + ":" + field + "_missing")
            if target.get("source_type") not in source_types:
                invalid.append(target_prefix + ":source_type_not_allowed")
        if not isinstance(reconstruction.get("prohibited_substitutes"), list) or not reconstruction.get("prohibited_substitutes"):
            incomplete.append(prefix + ".observable_outcome:metric_reconstruction_contract:prohibited_substitutes_missing")
        if reconstruction.get("definition_change_action") != "MEASUREMENT_MISMATCH":
            invalid.append(prefix + ".observable_outcome:metric_reconstruction_contract:definition_change_action_invalid")
    pair = contract.get("mechanism_signal_pair")
    if pair is not None:
        pair_prefix = "mechanism_signal_pair"
        if not isinstance(pair, dict):
            invalid.append(pair_prefix + ":not_object")
        else:
            identity = contract.get("research_identity") if isinstance(contract.get("research_identity"), dict) else {}
            for field in ("experiment_id", "company_cluster_id"):
                if not _text(identity.get(field)):
                    incomplete.append("research_identity:" + field + "_missing")
            for field in ("pair_id", "selection_status", "hypothesis_a_id", "hypothesis_b_id", "signals"):
                if pair.get(field) in (None, ""):
                    incomplete.append(pair_prefix + ":" + field + "_missing")
            selection_status = pair.get("selection_status")
            if selection_status not in {"NO_PRIMARY", "SELECTION_ADMITTED"}:
                invalid.append(pair_prefix + ":selection_status_invalid")
            if selection_status == "SELECTION_ADMITTED":
                # A production selection still has to be justified upstream by
                # the thesis admission gate.  The execution contract retains
                # its locator and the fair baseline so post-cutoff settlement
                # cannot silently turn a mechanism-only exercise into a
                # selected judgment.
                for field in ("selection_evidence_locator", "baseline_rule"):
                    if not _text(pair.get(field)):
                        incomplete.append(pair_prefix + ":" + field + "_missing")
                if set(claim_clocks) != OPERATING_CLOCKS or len(claim_clocks) != len(OPERATING_CLOCKS):
                    incomplete.append(pair_prefix + ":five_operating_clocks_required_for_selection")
            if not _text(pair.get("hypothesis_a_id")) or not _text(pair.get("hypothesis_b_id")):
                invalid.append(pair_prefix + ":hypothesis_ids_invalid")
            elif pair.get("hypothesis_a_id") == pair.get("hypothesis_b_id"):
                invalid.append(pair_prefix + ":hypothesis_ids_must_differ")
            signals = pair.get("signals") if isinstance(pair.get("signals"), list) else []
            if not signals:
                incomplete.append(pair_prefix + ":signals_missing")
            signal_claim_ids: set[str] = set()
            signal_ids: set[str] = set()
            for signal_index, signal in enumerate(signals):
                signal_prefix = pair_prefix + f".signals[{signal_index}]"
                if not isinstance(signal, dict):
                    invalid.append(signal_prefix + ":not_object")
                    continue
                for field in ("signal_id", "claim_id", "stage", "hypothesis_a_prediction", "hypothesis_b_prediction", "frozen_locator"):
                    if signal.get(field) in (None, ""):
                        incomplete.append(signal_prefix + ":" + field + "_missing")
                signal_id = str(signal.get("signal_id") or "")
                claim_id = str(signal.get("claim_id") or "")
                if signal_id and signal_id in signal_ids:
                    invalid.append(signal_prefix + ":duplicate_signal_id:" + signal_id)
                signal_ids.add(signal_id)
                if claim_id and claim_id in signal_claim_ids:
                    invalid.append(signal_prefix + ":duplicate_claim_id:" + claim_id)
                signal_claim_ids.add(claim_id)
                if claim_id and claim_id not in claim_ids:
                    invalid.append(signal_prefix + ":claim_not_in_calibration_ledger:" + claim_id)
                if signal.get("stage") not in {"EARLY_MECHANISM", "CONTINUATION_SIGNAL"}:
                    invalid.append(signal_prefix + ":stage_invalid")
                predictions: list[dict[str, Any]] = []
                for side in ("hypothesis_a_prediction", "hypothesis_b_prediction"):
                    prediction = signal.get(side)
                    if not isinstance(prediction, dict):
                        invalid.append(signal_prefix + ":" + side + "_not_object")
                        continue
                    predictions.append(prediction)
                    if prediction.get("operator") not in MECHANISM_SIGNAL_OPERATORS:
                        invalid.append(signal_prefix + ":" + side + "_operator_invalid")
                    if _number(prediction.get("value")) is None:
                        invalid.append(signal_prefix + ":" + side + "_value_invalid")
                if len(predictions) == 2:
                    if predictions[0] == predictions[1]:
                        invalid.append(signal_prefix + ":hypothesis_predictions_must_differ")
                    elif not _complementary_mechanism_predictions(predictions[0], predictions[1]):
                        invalid.append(signal_prefix + ":hypothesis_predictions_must_partition_observation_space")
            if signals and not signal_claim_ids.issubset(claim_ids):
                invalid.append(pair_prefix + ":signal_claim_ids_must_belong_to_calibration_ledger")
            if signals and {str(signal.get("stage") or "") for signal in signals if isinstance(signal, dict)} != {"EARLY_MECHANISM", "CONTINUATION_SIGNAL"}:
                invalid.append(pair_prefix + ":requires_one_early_and_one_continuation_signal")
            elif signals:
                signal_by_stage = {
                    str(signal.get("stage")): signal for signal in signals if isinstance(signal, dict)
                }
                outcome_by_claim = {
                    str(claim.get("claim_id") or ""): claim.get("observable_outcome")
                    for claim in claims if isinstance(claim, dict)
                }
                early = outcome_by_claim.get(str((signal_by_stage.get("EARLY_MECHANISM") or {}).get("claim_id") or ""))
                continuation = outcome_by_claim.get(str((signal_by_stage.get("CONTINUATION_SIGNAL") or {}).get("claim_id") or ""))
                early_window = early.get("observation_window") if isinstance(early, dict) and isinstance(early.get("observation_window"), dict) else {}
                continuation_window = continuation.get("observation_window") if isinstance(continuation, dict) and isinstance(continuation.get("observation_window"), dict) else {}
                early_close = _timestamp(early_window.get("closes_at"))
                continuation_open = _timestamp(continuation_window.get("opens_after"))
                if early_close is None or continuation_open is None or early_close >= continuation_open:
                    invalid.append(pair_prefix + ":early_signal_must_close_before_continuation_opens")
    prohibited = {"actual", "actual_value", "price", "return", "probability", "winner", "verdict"}
    if any(key in prohibited for key in contract):
        invalid.append("post_freeze_execution_contract_carries_prohibited_outcome_or_investment_field")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def assess_live_forward_acquisition_due(
    contract: dict[str, Any], *, as_of: str,
) -> dict[str, Any]:
    """Return the next post-freeze acquisition action without reading a result.

    A forward signal is not self-executing: the result-window contract must
    become an explicit acquisition task once its frozen window opens.  This
    helper is deliberately read-only.  It neither queries an issuer archive
    nor permits an outcome, mechanism verdict, or revised prediction into the
    pre-outcome contract.
    """
    validation = validate_live_forward_outcome_contract(contract)
    invalid = list(validation["invalid_findings"])
    incomplete = list(validation["incomplete_findings"])
    timestamp = _timestamp(as_of)
    if timestamp is None:
        invalid.append("as_of_invalid")
    if invalid or incomplete:
        return {
            "schema_version": LIVE_FORWARD_EXECUTION_STATUS_SCHEMA_VERSION,
            "case_id": contract.get("case_id"),
            "freeze_id": (contract.get("report_freeze") or {}).get("freeze_id"),
            "as_of": as_of,
            "state": "INVALID" if invalid else "INCOMPLETE",
            "execution_state": "EXECUTION_STATE_UNAVAILABLE",
            "claim_actions": [],
            "invalid_findings": invalid,
            "incomplete_findings": incomplete,
        }

    actions: list[dict[str, Any]] = []
    for claim in ((contract.get("calibration_ledger") or {}).get("claims") or []):
        if not isinstance(claim, dict):
            continue
        outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
        window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
        opens = _timestamp(window.get("opens_after"))
        closes = _timestamp(window.get("closes_at"))
        # The validation above has already established both timestamps.  Keep
        # the defensive branch so this function remains safe when called with
        # a future contract validator change.
        if opens is None or closes is None:
            continue
        if timestamp <= opens:
            action = "NOT_YET_DUE"
        elif timestamp <= closes:
            action = "DUE_FOR_ACQUISITION"
        else:
            action = "OVERDUE_FOR_ACQUISITION"
        actions.append({
            "claim_id": claim.get("claim_id"),
            "operating_clock": claim.get("operating_clock"),
            "action": action,
            "opens_after": window.get("opens_after"),
            "closes_at": window.get("closes_at"),
            "required_next_step": (
                "wait_for_frozen_window" if action == "NOT_YET_DUE"
                else "enumerate_and_acquire_frozen_result_sources"
            ),
        })

    action_names = {item["action"] for item in actions}
    execution_state = (
        "OVERDUE_FOR_ACQUISITION" if "OVERDUE_FOR_ACQUISITION" in action_names
        else "DUE_FOR_ACQUISITION" if "DUE_FOR_ACQUISITION" in action_names
        else "NOT_YET_DUE"
    )
    return {
        "schema_version": LIVE_FORWARD_EXECUTION_STATUS_SCHEMA_VERSION,
        "case_id": contract.get("case_id"),
        "freeze_id": (contract.get("report_freeze") or {}).get("freeze_id"),
        "as_of": as_of,
        "state": "REVIEWABLE",
        "execution_state": execution_state,
        "claim_actions": actions,
        "invalid_findings": [],
        "incomplete_findings": [],
    }


def build_live_forward_due_inbox(contract_root: str | Path, *, as_of: str) -> dict[str, Any]:
    """Scan all frozen outcome contracts once and return the actionable inbox.

    This deliberately reads contracts only.  It does not open an issuer result
    page, so calling it at the start of a research run cannot contaminate a
    still-frozen episode.  A broken contract is kept visible as a contract
    issue instead of disappearing from the schedule.
    """
    root = Path(contract_root)
    if not root.is_dir():
        return {
            "schema_version": LIVE_FORWARD_DUE_INBOX_SCHEMA_VERSION,
            "as_of": as_of, "state": "INCOMPLETE", "contract_root": str(root),
            "actionable": [], "scheduled": [], "contract_issues": ["contract_root_missing"],
        }
    contracts = sorted(root.rglob("08_outcome_acquisition_contract.json"))
    actionable: list[dict[str, Any]] = []
    scheduled: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for path in contracts:
        relative = str(path.relative_to(root))
        try:
            contract = _load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            issues.append({"contract_path": relative, "state": "INVALID", "findings": ["contract_unreadable"]})
            continue
        status = assess_live_forward_acquisition_due(contract, as_of=as_of)
        entry = {
            "contract_path": relative,
            "case_id": status.get("case_id"), "freeze_id": status.get("freeze_id"),
            "execution_state": status.get("execution_state"), "claim_actions": status.get("claim_actions") or [],
        }
        if status.get("state") != "REVIEWABLE":
            issues.append({
                "contract_path": relative, "state": status.get("state"),
                "findings": (status.get("invalid_findings") or []) + (status.get("incomplete_findings") or []),
            })
            continue
        due_actions = [
            {**entry, "claim": action}
            for action in entry["claim_actions"]
            if action.get("action") in {"DUE_FOR_ACQUISITION", "OVERDUE_FOR_ACQUISITION"}
        ]
        if due_actions:
            actionable.extend(due_actions)
        else:
            scheduled.append(entry)
    actionable.sort(key=lambda item: (
        0 if (item.get("claim") or {}).get("action") == "OVERDUE_FOR_ACQUISITION" else 1,
        str((item.get("claim") or {}).get("closes_at") or ""), str(item.get("case_id") or ""),
    ))
    scheduled.sort(key=lambda item: (
        min((str(action.get("opens_after") or "") for action in item["claim_actions"]), default=""),
        str(item.get("case_id") or ""),
    ))
    return {
        "schema_version": LIVE_FORWARD_DUE_INBOX_SCHEMA_VERSION,
        "as_of": as_of, "state": "REVIEWABLE" if not issues else "INCOMPLETE",
        "contract_root": str(root), "contracts_scanned": len(contracts),
        "actionable": actionable, "scheduled": scheduled, "contract_issues": issues,
        "next_action": (
            "enumerate_and_acquire_frozen_result_sources" if actionable
            else "continue_pre_outcome_research_without_opening_results"
        ),
    }


def validate_outcome_package(
    manifest: dict[str, Any], package_root: str | Path, *, case: dict[str, Any], settlement_as_of: str,
) -> dict[str, Any]:
    """Validate a bounded, post-freeze result-source package without network I/O."""
    invalid: list[str] = []
    incomplete: list[str] = []
    root = Path(package_root).expanduser().resolve()
    if case.get("schema_version") == LIVE_FORWARD_OUTCOME_CONTRACT_SCHEMA_VERSION:
        contract_result = validate_live_forward_outcome_contract(case)
        invalid.extend("live_forward_contract:" + item for item in contract_result["invalid_findings"])
        incomplete.extend("live_forward_contract:" + item for item in contract_result["incomplete_findings"])
    if manifest.get("schema_version") != OUTCOME_PACKAGE_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    for field in ("outcome_package_id", "case_id", "freeze_id", "frozen_cutoff", "enumeration"):
        if not manifest.get(field):
            incomplete.append(field + "_missing")
    if manifest.get("case_id") not in (None, case.get("case_id")):
        invalid.append("case_id_does_not_match_frozen_case")
    freeze_id = ((case.get("report_freeze") or {}).get("freeze_id"))
    if manifest.get("freeze_id") not in (None, freeze_id):
        invalid.append("freeze_id_does_not_match_frozen_case")
    cutoff = _timestamp(manifest.get("frozen_cutoff"))
    case_cutoff = _timestamp(case.get("simulation_cutoff"))
    settlement = _timestamp(settlement_as_of)
    if cutoff is None:
        invalid.append("frozen_cutoff_invalid")
    elif case_cutoff and cutoff != case_cutoff:
        invalid.append("frozen_cutoff_does_not_match_frozen_case")
    if settlement is None:
        invalid.append("settlement_as_of_invalid")
    enumeration = manifest.get("enumeration") if isinstance(manifest.get("enumeration"), dict) else {}
    for field in ("status", "query_identity", "source_ids"):
        if not enumeration.get(field):
            incomplete.append("enumeration:" + field + "_missing")
    if enumeration.get("status") not in {None, "COMPLETE", "INCOMPLETE"}:
        invalid.append("enumeration:status_invalid")
    elif enumeration.get("status") == "INCOMPLETE":
        incomplete.append("enumeration_incomplete")
    if not _text(enumeration.get("query_identity")):
        incomplete.append("enumeration:query_identity_missing")
    inventory = manifest.get("inventory") if isinstance(manifest.get("inventory"), list) else []
    if not inventory:
        incomplete.append("inventory_missing")
    ids: set[str] = set()
    selected = [str(item or "") for item in manifest.get("selected_source_ids") or []]
    selected_set = set(selected)
    if not selected:
        incomplete.append("selected_source_ids_missing")
    for index, source in enumerate(inventory):
        prefix = f"inventory[{index}]"
        if not isinstance(source, dict):
            invalid.append(prefix + ":not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id:
            incomplete.append(prefix + ":source_id_missing")
        elif source_id in ids:
            invalid.append(prefix + ":duplicate_source_id:" + source_id)
        ids.add(source_id)
        for field in ("source_type", "official", "published_at", "source_version"):
            if source.get(field) in (None, ""):
                incomplete.append(prefix + ":" + field + "_missing")
        source_type = source.get("source_type")
        if source_type in OFFICIAL_SOURCE_TYPES:
            if source.get("official") is not True:
                invalid.append(prefix + ":official_source_required")
        elif source_type == LICENSED_INDUSTRY_DATA:
            if source.get("official") is not False:
                invalid.append(prefix + ":licensed_industry_source_must_be_non_official")
        else:
            invalid.append(prefix + ":source_type_invalid")
        published = _timestamp(source.get("published_at"))
        if published is None:
            invalid.append(prefix + ":published_at_invalid")
        else:
            if cutoff and published <= cutoff:
                invalid.append(prefix + ":published_at_must_follow_frozen_cutoff")
            if settlement and published > settlement:
                invalid.append(prefix + ":published_at_after_settlement")
        if source_id in selected_set:
            for field in ("package_path", "reader_text_path"):
                if source.get(field) in (None, ""):
                    incomplete.append(prefix + ":" + field + "_missing")
            raw_path = _package_file(root, source.get("package_path"))
            reader_path = _package_file(root, source.get("reader_text_path"))
            if raw_path is None:
                invalid.append(prefix + ":package_path_invalid")
            elif not raw_path.is_file():
                incomplete.append(prefix + ":raw_source_missing")
            if reader_path is None:
                invalid.append(prefix + ":reader_text_path_invalid")
            elif not reader_path.is_file():
                incomplete.append(prefix + ":reader_source_missing")
            else:
                try:
                    if not reader_path.read_text(encoding="utf-8").strip():
                        incomplete.append(prefix + ":reader_source_empty")
                except (OSError, UnicodeDecodeError):
                    invalid.append(prefix + ":reader_source_unreadable")
    enumeration_ids = [str(item or "") for item in enumeration.get("source_ids") or []]
    if inventory and (not enumeration_ids or set(enumeration_ids) != ids or len(enumeration_ids) != len(ids)):
        invalid.append("enumeration:source_ids_do_not_match_inventory")
    if selected and (len(selected) != len(set(selected)) or not selected_set.issubset(ids)):
        invalid.append("selected_source_ids_invalid")
    if manifest.get("source_package_status") not in {"COMPLETE", "INCOMPLETE"}:
        invalid.append("source_package_status_invalid")
    elif manifest.get("source_package_status") == "INCOMPLETE":
        incomplete.append("source_package_incomplete")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def acquire_outcome_package(
    manifest: dict[str, Any], package_root: str | Path, *, downloader: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """Materialize the selected post-cutoff sources with the existing reader-aware acquirer.

    The caller first retains the complete bounded inventory.  This function
    downloads/materializes only the explicitly selected sources, while keeping
    every unselected candidate in the returned manifest so an initial/latest
    choice remains reviewable.  It supports the same first-party web/PDF and
    pre-acquired licensed-export source shapes as ``phase10_acquisition``.
    """
    try:
        from scripts.phase10_acquisition import acquire_source_package
    except ModuleNotFoundError:
        # ``python scripts/judgment_feedback_control.py`` loads this module
        # from the scripts directory, where the package-qualified import is
        # unavailable.
        from phase10_acquisition import acquire_source_package

    inventory = manifest.get("inventory") if isinstance(manifest.get("inventory"), list) else []
    selected_ids = [str(item or "") for item in manifest.get("selected_source_ids") or []]
    by_id = {
        str(item.get("source_id")): deepcopy(item)
        for item in inventory if isinstance(item, dict) and item.get("source_id")
    }
    selected = [by_id[source_id] for source_id in selected_ids if source_id in by_id]
    if len(selected) != len(selected_ids):
        raise ValueError("outcome selected_source_ids must be present in inventory before acquisition")
    facade = {"inventory": list(by_id.values()), "sources": selected}
    acquired = acquire_source_package(facade, package_root, downloader=downloader)
    acquired_by_id = {
        str(item.get("source_id")): item
        for item in acquired.get("inventory") or [] if isinstance(item, dict) and item.get("source_id")
    }
    result = deepcopy(manifest)
    result["inventory"] = [acquired_by_id.get(str(item.get("source_id") or ""), item) for item in inventory]
    package = acquired.get("source_package") if isinstance(acquired.get("source_package"), dict) else {}
    result["source_package_status"] = "COMPLETE" if package.get("status") == "COMPLETE" else "INCOMPLETE"
    result["package_root"] = str(package_root)
    return result


def read_outcome_package(
    manifest: dict[str, Any], package_root: str | Path, *, case: dict[str, Any], settlement_as_of: str,
) -> dict[str, Any]:
    """Read every selected raw/reader pair and return a serializable audit."""
    validation = validate_outcome_package(manifest, package_root, case=case, settlement_as_of=settlement_as_of)
    root = Path(package_root).expanduser().resolve()
    events: list[dict[str, Any]] = []
    if validation["state"] != "REVIEWABLE":
        return {
            "schema_version": OUTCOME_READ_ATTESTATION_SCHEMA_VERSION,
            "outcome_package_id": manifest.get("outcome_package_id"),
            "state": validation["state"], "read_audit": events,
            "invalid_findings": validation["invalid_findings"],
            "incomplete_findings": validation["incomplete_findings"],
        }
    by_id = _source_by_id(manifest)
    for source_id in manifest.get("selected_source_ids") or []:
        source = by_id[str(source_id)]
        raw_path = _package_file(root, source.get("package_path"))
        reader_path = _package_file(root, source.get("reader_text_path"))
        assert raw_path is not None and reader_path is not None
        try:
            raw_path.read_bytes()
            reader_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return {
                "schema_version": OUTCOME_READ_ATTESTATION_SCHEMA_VERSION,
                "outcome_package_id": manifest.get("outcome_package_id"), "state": "INCOMPLETE",
                "read_audit": events, "invalid_findings": [],
                "incomplete_findings": ["source_read_failed:" + str(source_id) + ":" + type(exc).__name__],
            }
        events.append({
            "source_id": str(source_id), "source_version": source.get("source_version"),
            "package_path": source.get("package_path"), "reader_text_path": source.get("reader_text_path"),
            "raw_read": True, "reader_read": True,
        })
    return {
        "schema_version": OUTCOME_READ_ATTESTATION_SCHEMA_VERSION,
        "outcome_package_id": manifest.get("outcome_package_id"), "case_id": case.get("case_id"),
        "freeze_id": ((case.get("report_freeze") or {}).get("freeze_id")),
        "settlement_as_of": settlement_as_of, "state": "REVIEWABLE", "read_audit": events,
        "invalid_findings": [], "incomplete_findings": [],
    }


def _reported_number(value: Any) -> float | None:
    """Parse one disclosed number token; formatting signs and commas are harmless."""
    if not _text(value):
        return None
    match = re.search(r"(?<![0-9.])-?\d[\d,]*(?:\.\d+)?(?![0-9.])", str(value))
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _normalized_reported_text(value: Any) -> str:
    """Normalize a disclosure fragment without inventing a table parser.

    Outcome packages are reader copies of issuer releases, so table markup and
    insignificant punctuation can differ while the disclosed words and number
    remain the same.  An extraction therefore carries the exact reader
    fragment, not a locator inferred after the fact.  This normalizer only
    makes the containment check resilient to that harmless formatting.
    """
    return re.sub(r"[^\w]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def _reported_fragment_contains(fragment: Any, required: Any) -> bool:
    normalized_required = _normalized_reported_text(required)
    return bool(normalized_required) and normalized_required in _normalized_reported_text(fragment)


def validate_outcome_extraction(
    extraction: dict[str, Any], *, manifest: dict[str, Any], package_root: str | Path,
    read_attestation: dict[str, Any], case: dict[str, Any], settlement_as_of: str,
) -> dict[str, Any]:
    """Validate source-bound observation extractions before they reach HBT."""
    invalid: list[str] = []
    incomplete: list[str] = []
    package_validation = validate_outcome_package(manifest, package_root, case=case, settlement_as_of=settlement_as_of)
    if package_validation["state"] != "REVIEWABLE":
        invalid.append("outcome_package_not_reviewable")
    if extraction.get("schema_version") != OUTCOME_EXTRACTION_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    for field, expected in (
        ("outcome_package_id", manifest.get("outcome_package_id")),
        ("case_id", case.get("case_id")),
        ("freeze_id", ((case.get("report_freeze") or {}).get("freeze_id"))),
        ("settlement_as_of", settlement_as_of),
    ):
        if extraction.get(field) != expected:
            invalid.append(field + "_does_not_match_bound_artifact")
    if read_attestation.get("schema_version") != OUTCOME_READ_ATTESTATION_SCHEMA_VERSION:
        invalid.append("read_attestation_schema_invalid")
    if read_attestation.get("state") != "REVIEWABLE":
        invalid.append("read_attestation_not_reviewable")
    if read_attestation.get("outcome_package_id") != manifest.get("outcome_package_id"):
        invalid.append("read_attestation_package_mismatch")
    read_sources = {
        str(item.get("source_id"))
        for item in read_attestation.get("read_audit") or []
        if isinstance(item, dict) and item.get("raw_read") is True and item.get("reader_read") is True
    }
    by_id = _source_by_id(manifest)
    claims = _claim_map(case)
    root = Path(package_root).expanduser().resolve()
    observations = extraction.get("observations") if isinstance(extraction.get("observations"), list) else []
    resolutions = extraction.get("non_diagnostic_resolutions") if isinstance(extraction.get("non_diagnostic_resolutions"), list) else []
    if not observations and not resolutions:
        incomplete.append("observations_or_non_diagnostic_resolutions_missing")
    seen: set[str] = set()
    for index, item in enumerate(observations):
        prefix = f"observations[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        for field in (
            "observation_id", "claim_id", "metric", "value", "unit", "measurement_basis",
            "measurement_period", "source_ids", "comparability_status", "reported_label",
            "reported_locator", "reported_text", "reported_value_text",
        ):
            if item.get(field) in (None, ""):
                incomplete.append(prefix + ":" + field + "_missing")
        observation_id = str(item.get("observation_id") or "")
        if observation_id in seen:
            invalid.append(prefix + ":duplicate_observation_id:" + observation_id)
        seen.add(observation_id)
        claim = claims.get(str(item.get("claim_id") or ""))
        if claim is None:
            invalid.append(prefix + ":claim_not_frozen")
            continue
        outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
        for field in ("metric", "unit", "measurement_basis", "measurement_period"):
            if item.get(field) != outcome.get(field):
                invalid.append(prefix + ":" + field + "_does_not_match_frozen_contract")
        source_ids = [str(source_id or "") for source_id in item.get("source_ids") or []]
        if not source_ids or any(source_id not in by_id for source_id in source_ids):
            invalid.append(prefix + ":source_ids_not_in_outcome_package")
        for source_id in source_ids:
            source = by_id.get(source_id)
            if source is None:
                continue
            if source_id not in read_sources:
                invalid.append(prefix + ":source_not_read:" + source_id)
            allowed = outcome.get("allowed_source_types") if isinstance(outcome.get("allowed_source_types"), list) else []
            if source.get("source_type") not in allowed:
                invalid.append(prefix + ":source_type_not_allowed:" + source_id)
            if case.get("schema_version") == LIVE_FORWARD_OUTCOME_CONTRACT_SCHEMA_VERSION:
                candidate_claims = source.get("candidate_claim_ids")
                if not isinstance(candidate_claims, list) or str(item.get("claim_id") or "") not in {
                    str(candidate or "") for candidate in candidate_claims
                }:
                    invalid.append(prefix + ":source_not_enumerated_for_claim:" + source_id)
            publisher_domains = _publisher_domains(outcome)
            if publisher_domains:
                if source.get("official_publisher_domain") not in publisher_domains:
                    invalid.append(prefix + ":publisher_domain_does_not_match_frozen_contract:" + source_id)
            window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
            published = _timestamp(source.get("published_at"))
            opens = _timestamp(window.get("opens_after"))
            closes = _timestamp(window.get("closes_at"))
            if published and opens and published <= opens:
                invalid.append(prefix + ":source_published_before_frozen_window:" + source_id)
            if published and closes and published > closes:
                invalid.append(prefix + ":source_published_after_frozen_window:" + source_id)
            reader_path = _package_file(root, source.get("reader_text_path"))
            if reader_path and reader_path.is_file():
                try:
                    text = reader_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    text = ""
                if str(item.get("reported_text") or "") not in text:
                    invalid.append(prefix + ":reported_text_not_found_in_reader:" + source_id)
        if case.get("schema_version") == LIVE_FORWARD_OUTCOME_CONTRACT_SCHEMA_VERSION:
            policy_invalid, policy_incomplete = _version_policy_findings(
                outcome, str(item.get("claim_id") or ""), source_ids, by_id, prefix=prefix,
            )
            invalid.extend(policy_invalid)
            incomplete.extend(policy_incomplete)
        parsed = _reported_number(item.get("reported_value_text"))
        value = _number(item.get("value"))
        if parsed is None:
            invalid.append(prefix + ":reported_value_text_not_numeric")
        elif value is not None and parsed != value:
            invalid.append(prefix + ":value_does_not_match_reported_value_text")
        # The reader can contain several unrelated KPI values.  The exact
        # fragment used for extraction must itself name the frozen label and
        # contain the parsed value token; checking their independent presence
        # somewhere in the full report would still permit a wrong table row.
        if not _reported_fragment_contains(item.get("reported_text"), item.get("reported_label")):
            invalid.append(prefix + ":reported_label_not_found_in_reported_text")
        if not _reported_fragment_contains(item.get("reported_text"), item.get("reported_value_text")):
            invalid.append(prefix + ":reported_value_text_not_found_in_reported_text")
        if item.get("comparability_status") in COMPARABLE_STATUSES and value is None:
            invalid.append(prefix + ":comparable_value_not_numeric")
        reconstruction = outcome.get("metric_reconstruction_contract")
        if item.get("comparability_status") in COMPARABLE_STATUSES and isinstance(reconstruction, dict):
            targets = reconstruction.get("source_targets") if isinstance(reconstruction.get("source_targets"), list) else []
            source_types = {
                str(by_id[source_id].get("source_type") or "")
                for source_id in source_ids if source_id in by_id
            }
            target_matches = [
                target for target in targets if isinstance(target, dict)
                and target.get("source_type") in source_types
                and target.get("file_scope") == item.get("reported_file_scope")
                and target.get("reported_label") == item.get("reported_label")
                and target.get("reported_locator") == item.get("reported_locator")
            ]
            if not target_matches:
                invalid.append(prefix + ":reported_disclosure_does_not_match_frozen_metric_contract")
            # The same results table usually carries a comparison-period
            # column.  A report-level source/window cannot tell a current
            # value from that neighboring column, so live forward contracts
            # freeze a period anchor observed in the issuer's pre-cutoff
            # release format.  The extracted fragment must carry it too.
            elif any(_text(target.get("reported_period_anchor")) for target in target_matches):
                period_text = item.get("reported_period_text")
                if not _text(period_text):
                    incomplete.append(prefix + ":reported_period_text_missing")
                else:
                    if not _reported_fragment_contains(item.get("reported_text"), period_text):
                        invalid.append(prefix + ":reported_period_text_not_found_in_reported_text")
                    if not any(
                        _reported_fragment_contains(period_text, target.get("reported_period_anchor"))
                        for target in target_matches
                    ):
                        invalid.append(prefix + ":reported_period_anchor_not_found_in_reported_period_text")
    resolved_claim_ids: set[str] = set()
    for index, item in enumerate(resolutions):
        prefix = f"non_diagnostic_resolutions[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        for field in ("claim_id", "resolution", "source_ids", "reported_label", "reported_locator", "reported_text"):
            if item.get(field) in (None, ""):
                incomplete.append(prefix + ":" + field + "_missing")
        claim_id = str(item.get("claim_id") or "")
        if claim_id in resolved_claim_ids:
            invalid.append(prefix + ":duplicate_claim_resolution:" + claim_id)
        resolved_claim_ids.add(claim_id)
        if item.get("resolution") not in NON_DIAGNOSTIC_RESOLUTIONS:
            invalid.append(prefix + ":resolution_invalid")
        claim = claims.get(claim_id)
        if claim is None:
            invalid.append(prefix + ":claim_not_frozen")
            continue
        outcome = claim.get("observable_outcome") if isinstance(claim.get("observable_outcome"), dict) else {}
        source_ids = [str(source_id or "") for source_id in item.get("source_ids") or []]
        if not source_ids or any(source_id not in by_id for source_id in source_ids):
            invalid.append(prefix + ":source_ids_not_in_outcome_package")
        for source_id in source_ids:
            source = by_id.get(source_id)
            if source is None:
                continue
            if source_id not in read_sources:
                invalid.append(prefix + ":source_not_read:" + source_id)
            allowed = outcome.get("allowed_source_types") if isinstance(outcome.get("allowed_source_types"), list) else []
            if source.get("source_type") not in allowed:
                invalid.append(prefix + ":source_type_not_allowed:" + source_id)
            if case.get("schema_version") == LIVE_FORWARD_OUTCOME_CONTRACT_SCHEMA_VERSION:
                candidate_claims = source.get("candidate_claim_ids")
                if not isinstance(candidate_claims, list) or claim_id not in {str(candidate or "") for candidate in candidate_claims}:
                    invalid.append(prefix + ":source_not_enumerated_for_claim:" + source_id)
            publisher_domains = _publisher_domains(outcome)
            if publisher_domains and source.get("official_publisher_domain") not in publisher_domains:
                invalid.append(prefix + ":publisher_domain_does_not_match_frozen_contract:" + source_id)
            window = outcome.get("observation_window") if isinstance(outcome.get("observation_window"), dict) else {}
            published, opens, closes = (
                _timestamp(source.get("published_at")), _timestamp(window.get("opens_after")), _timestamp(window.get("closes_at")),
            )
            if published and opens and published <= opens:
                invalid.append(prefix + ":source_published_before_frozen_window:" + source_id)
            if published and closes and published > closes:
                invalid.append(prefix + ":source_published_after_frozen_window:" + source_id)
            reader_path = _package_file(root, source.get("reader_text_path"))
            if reader_path and reader_path.is_file():
                try:
                    text = reader_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    text = ""
                if str(item.get("reported_text") or "") not in text:
                    invalid.append(prefix + ":reported_text_not_found_in_reader:" + source_id)
        if not _reported_fragment_contains(item.get("reported_text"), item.get("reported_label")):
            invalid.append(prefix + ":reported_label_not_found_in_reported_text")
        if case.get("schema_version") == LIVE_FORWARD_OUTCOME_CONTRACT_SCHEMA_VERSION:
            policy_invalid, policy_incomplete = _version_policy_findings(
                outcome, claim_id, source_ids, by_id, prefix=prefix,
            )
            invalid.extend(policy_invalid)
            incomplete.extend(policy_incomplete)
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def validate_settlement_outcome_acquisition(
    binding: dict[str, Any], *, settlement: dict[str, Any], case: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Bind a CJO settlement's sources and observations to a result package.

    The only manually prepared payload is the extraction file.  It must have
    passed quote-in-reader validation; the settlement is then a projection of
    it rather than an independently editable calculation input.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    root = Path(__file__).resolve().parents[1]
    if not isinstance(binding, dict) or not binding:
        return [], ["outcome_acquisition_missing"]
    for field in ("package_root", "manifest_path", "read_attestation_path", "extraction_path"):
        if not _text(binding.get(field)):
            incomplete.append("outcome_acquisition:" + field + "_missing")
    def path(field: str) -> Path | None:
        raw = str(binding.get(field) or "")
        if not raw or Path(raw).is_absolute():
            invalid.append("outcome_acquisition:" + field + "_must_be_repo_relative")
            return None
        candidate = (root / raw).resolve()
        if root not in candidate.parents:
            invalid.append("outcome_acquisition:" + field + "_outside_repository")
            return None
        return candidate
    package_root = path("package_root")
    manifest, manifest_errors = _load_object(path("manifest_path"), field="outcome_acquisition:manifest")
    attestation, attestation_errors = _load_object(path("read_attestation_path"), field="outcome_acquisition:read_attestation")
    extraction, extraction_errors = _load_object(path("extraction_path"), field="outcome_acquisition:extraction")
    incomplete.extend(manifest_errors + attestation_errors + extraction_errors)
    if package_root is None or not package_root.is_dir():
        incomplete.append("outcome_acquisition:package_root_missing")
        return invalid, incomplete
    package_result = validate_outcome_package(
        manifest, package_root, case=case, settlement_as_of=str(settlement.get("settlement_as_of") or ""),
    )
    extraction_result = validate_outcome_extraction(
        extraction, manifest=manifest, package_root=package_root, read_attestation=attestation,
        case=case, settlement_as_of=str(settlement.get("settlement_as_of") or ""),
    )
    invalid.extend("outcome_acquisition:package:" + item for item in package_result["invalid_findings"])
    incomplete.extend("outcome_acquisition:package:" + item for item in package_result["incomplete_findings"])
    invalid.extend("outcome_acquisition:extraction:" + item for item in extraction_result["invalid_findings"])
    incomplete.extend("outcome_acquisition:extraction:" + item for item in extraction_result["incomplete_findings"])
    extracted_source_ids = {
        source_id for item in extraction.get("observations") or [] if isinstance(item, dict)
        for source_id in item.get("source_ids") or []
    } | {
        source_id for item in extraction.get("non_diagnostic_resolutions") or [] if isinstance(item, dict)
        for source_id in item.get("source_ids") or []
    }
    expected_sources = {
        source_id: _source_payload(source)
        for source_id, source in _source_by_id(manifest).items()
        if source_id in extracted_source_ids
    }
    settlement_sources = {
        str(source.get("source_id")): source
        for source in settlement.get("actual_sources") or []
        if isinstance(source, dict) and str(source.get("source_id") or "")
    }
    if set(settlement_sources) != set(expected_sources):
        invalid.append("outcome_acquisition:settlement_actual_sources_do_not_match_extraction")
    for source_id, expected in expected_sources.items():
        actual = settlement_sources.get(source_id, {})
        for field, value in expected.items():
            if actual.get(field) != value:
                invalid.append("outcome_acquisition:settlement_source_payload_mismatch:" + source_id + ":" + field)
    expected_observations = {
        str(item.get("observation_id")): _observation_payload(item)
        for item in extraction.get("observations") or [] if isinstance(item, dict) and item.get("observation_id")
    }
    settlement_observations = {
        str(item.get("observation_id")): item
        for item in ((settlement.get("actual_outcomes") or {}).get("operating_observations") or [])
        if isinstance(item, dict) and item.get("observation_id")
    }
    if set(settlement_observations) != set(expected_observations):
        invalid.append("outcome_acquisition:settlement_observations_do_not_match_extraction")
    for observation_id, expected in expected_observations.items():
        if settlement_observations.get(observation_id) != expected:
            invalid.append("outcome_acquisition:settlement_observation_payload_mismatch:" + observation_id)
    settlements = {
        str(item.get("claim_id")): item
        for item in ((settlement.get("model_forecast_error") or {}).get("claim_settlements") or [])
        if isinstance(item, dict) and item.get("claim_id")
    }
    for resolution in extraction.get("non_diagnostic_resolutions") or []:
        if not isinstance(resolution, dict):
            continue
        entry = settlements.get(str(resolution.get("claim_id") or ""))
        if not isinstance(entry, dict) or entry.get("status") != "NOT_CALCULABLE":
            invalid.append("outcome_acquisition:non_diagnostic_resolution_requires_not_calculable_claim:" + str(resolution.get("claim_id") or ""))
    return invalid, incomplete


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON payload must be an object")
    return value


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-package")
    validate.add_argument("manifest", type=Path)
    validate.add_argument("package_root", type=Path)
    validate.add_argument("case", type=Path)
    validate.add_argument("--settlement-as-of", required=True)
    read = sub.add_parser("read-package")
    read.add_argument("manifest", type=Path)
    read.add_argument("package_root", type=Path)
    read.add_argument("case", type=Path)
    read.add_argument("--settlement-as-of", required=True)
    read.add_argument("--attestation", type=Path, required=True)
    acquire = sub.add_parser("acquire-package")
    acquire.add_argument("manifest", type=Path)
    acquire.add_argument("package_root", type=Path)
    acquire.add_argument("--output", type=Path, required=True)
    status = sub.add_parser("execution-status")
    status.add_argument("contract", type=Path)
    status.add_argument(
        "--as-of",
        required=True,
        help="ISO-8601 timestamp with an explicit UTC offset, e.g. 2026-08-21T18:00:00+08:00",
    )
    inbox = sub.add_parser("due-inbox")
    inbox.add_argument("contract_root", type=Path)
    inbox.add_argument(
        "--as-of", required=True,
        help="ISO-8601 timestamp with an explicit UTC offset, e.g. 2026-08-21T18:00:00+08:00",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "execution-status":
        result = assess_live_forward_acquisition_due(_load_json(args.contract), as_of=args.as_of)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["state"] == "REVIEWABLE" else 1
    if args.command == "due-inbox":
        result = build_live_forward_due_inbox(args.contract_root, as_of=args.as_of)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["state"] == "REVIEWABLE" else 1
    manifest = _load_json(args.manifest)
    if args.command == "acquire-package":
        result = acquire_outcome_package(manifest, args.package_root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"written": str(args.output), "source_package_status": result.get("source_package_status")}, ensure_ascii=False))
        return 0 if result.get("source_package_status") == "COMPLETE" else 1
    case = _load_json(args.case)
    if args.command == "validate-package":
        result = validate_outcome_package(manifest, args.package_root, case=case, settlement_as_of=args.settlement_as_of)
    else:
        result = read_outcome_package(manifest, args.package_root, case=case, settlement_as_of=args.settlement_as_of)
        args.attestation.parent.mkdir(parents=True, exist_ok=True)
        args.attestation.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "REVIEWABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
