#!/usr/bin/env python3
"""Validate a sealed historical selection candidate and its independent review."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from statistics import median
from typing import Any


CANDIDATE_SCHEMA_VERSION = "judgment-selection-candidate.v1"
REVIEW_SCHEMA_VERSION = "judgment-selection-review-receipt.v1"
CASH_TRANSMISSION_ADMISSION_VERSION = "JUDGMENT_SELECTION_ADMISSION_V3"
PEER_PANEL_ADMISSION_VERSION = "JUDGMENT_SELECTION_ADMISSION_V4"
SUPPORTED_ADMISSION_VERSIONS = (
    CASH_TRANSMISSION_ADMISSION_VERSION,
    PEER_PANEL_ADMISSION_VERSION,
)
CASH_TRANSMISSION_REQUIRED_TRIGGER = "H_A_OPERATING_IMPROVEMENT_REACHES_NORMAL_OWNER_CASH"
CASH_TRANSMISSION_NOT_REQUIRED_TRIGGER = "H_A_DOES_NOT_CLAIM_D3_TO_NORMAL_OWNER_CASH"
CASH_TRANSMISSION_NO_PRIMARY = "NO_PRIMARY_IF_ANY_LEG_NOT_RECURRENTLY_OBSERVABLE"
CUSTOMER_ABSORPTION_REQUIRED_TRIGGER = "H_A_REQUIRES_CUSTOMER_RESPONSE_OR_ABSORPTION"
CUSTOMER_ABSORPTION_NOT_REQUIRED_TRIGGER = "D2_NOT_CAUSALLY_CENTRAL_TO_H_A"
CUSTOMER_ABSORPTION_NO_PRIMARY = "NO_PRIMARY_IF_CUSTOMER_ABSORPTION_NOT_INDEPENDENTLY_OBSERVABLE"
V4_CUSTOMER_RESPONSE_CHAIN = "CUSTOMER_RESPONSE_CHAIN"
V4_COST_RESTRUCTURING_CHAIN = "COST_RESTRUCTURING_CHAIN"
V4_MECHANISM_TOPOLOGIES = {V4_CUSTOMER_RESPONSE_CHAIN, V4_COST_RESTRUCTURING_CHAIN}
V4_COST_DRIVER_NO_PRIMARY = "NO_PRIMARY_IF_COST_DRIVER_NOT_RECURRENTLY_OBSERVABLE"
V4_COST_DRIVER_KINDS = {
    "UNIT_INPUT_COST",
    "FIXED_COST_ABSORPTION",
    "ENERGY_INTENSITY",
    "LABOR_PRODUCTIVITY",
    "ASSET_UTILIZATION",
}
CUSTOMER_ABSORPTION_OBSERVATION_KINDS = (
    "UNITS_SOLD",
    "SHIPMENTS",
    "ACTIVE_CUSTOMERS",
    "CUSTOMER_REORDER_RATE",
    "CHANNEL_INVENTORY",
    "INDEPENDENT_VOLUME_PRICE_DECOMPOSITION",
)
V4_DIRECT_CUSTOMER_OBSERVATION_KINDS = {
    "UNITS_SOLD",
    "ACTIVE_CUSTOMERS",
    "CUSTOMER_REORDER_RATE",
    "INDEPENDENT_VOLUME_PRICE_DECOMPOSITION",
}
CASH_TRANSMISSION_LEGS = (
    ("OPERATING_CONTRIBUTION", "D3", "D3_UNIT_ECONOMICS"),
    ("CASH_WORKING_CAPITAL", "D4", "D4_WORKING_CAPITAL_AND_CASH"),
    ("CAPEX_RESTRUCTURING_CASH", "D4", "D4_WORKING_CAPITAL_AND_CASH"),
)
_CASH_TRANSMISSION_LEG_IDS = tuple(item[0] for item in CASH_TRANSMISSION_LEGS)
PEER_PANEL_NO_PRIMARY = "NO_PRIMARY_IF_FIXED_PEER_PANEL_OR_TARGET_HISTORY_NOT_RECURRENTLY_OBSERVABLE"
V4_ACTION_IMPLEMENTED = "IMPLEMENTED_OR_IRREVOCABLY_INCURRED"
V4_ACTION_EXPOSURE_KINDS = (
    "ACTUAL_CASH_OR_RECOGNIZED_ASSET",
    "IMPLEMENTED_NET_PRICE_DELTA_X_PREACTION_ACTUAL_UNITS",
)
V4_SCALED_MAD_METHOD = "SCALED_MEDIAN_ABSOLUTE_DEVIATION"
V4_SCALED_MAD_SCALE = 1.4826
V4_PEER_RELATIVE_METHOD = "DELTA_VS_PEER_MEDIAN"
V4_PEER_RELATIVE_UNIT = "ratio"
V4_RELATIVE_STEP_FORMULA = (
    "MAX_TARGET_ABSOLUTE_STEP_PER_REFERENCE_REVENUE_AND_"
    "PREACTION_PEER_RELATIVE_SCALED_MAD"
)
V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER = "LISTED_CONSOLIDATED_ISSUER"
V4_OFFICIAL_AUDITED_ANNUAL_REPORT = "OFFICIAL_AUDITED_ANNUAL_REPORT"
V4_OFFICIAL_DISCLOSURE = "OFFICIAL_LISTED_DISCLOSURE"
V4_ALLOWED_OPERATIONAL_ACTION_TYPES = {
    "OPERATING_NETWORK_RESTRUCTURING",
    "OPERATING_PRICE_EXECUTION",
    "OPERATING_PROCESS_EFFICIENCY",
}
V4_COMPARABILITY_DIMENSIONS = (
    "CONSOLIDATION_SCOPE",
    "ACCOUNTING_PRESENTATION",
    "OPERATING_PERIMETER",
)
V4_CASH_BRIDGE_COMPONENTS = (
    "OPERATING_CASH_FLOW",
    "LONG_LIVED_ASSET_CASH",
    "CASH_WORKING_CAPITAL",
    "ACTION_RELATED_CASH",
)
V4_COHORT_FEASIBILITY_SCHEMA_VERSION = "judgment-selection-cohort-feasibility.v1"
V4_DISCOVERY_BINDING_SCHEMA_VERSION = "judgment-selection-discovery-binding.v1"
V4_COHORT_FINAL_PEER_DISPOSITIONS = {
    "PENDING_ACTION_WINDOW_REVIEW",
    "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK",
}
V4_OFFICIAL_EVIDENCE_SOURCE_TYPES = {
    V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
    V4_OFFICIAL_DISCLOSURE,
}
V4_D3_RAW_FIELDS = (
    "operating_revenue_rmb",
    "operating_cost_rmb",
    "taxes_and_surcharges_rmb",
    "selling_expense_rmb",
    "administrative_expense_rmb",
)
V4_D4_RAW_FIELDS = (
    "operating_cash_flow_rmb",
    "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb",
    "opening_accounts_receivable_rmb",
    "opening_prepayments_rmb",
    "opening_inventory_rmb",
    "opening_accounts_payable_rmb",
    "opening_customer_advances_rmb",
    "ending_accounts_receivable_rmb",
    "ending_prepayments_rmb",
    "ending_inventory_rmb",
    "ending_accounts_payable_rmb",
    "ending_customer_advances_rmb",
)
REQUIRED_SELECTION_STAGE_IDS = (
    "D1_IMPLEMENTATION",
    "D2_CUSTOMER_ABSORPTION",
    "D3_UNIT_ECONOMICS",
    "D4_WORKING_CAPITAL_AND_CASH",
    "D5_CAPITAL_RETURN",
)
SELECTION_STAGE_ORDERS = (
    REQUIRED_SELECTION_STAGE_IDS,
    (
        "D1_IMPLEMENTATION",
        "D2_CUSTOMER_ABSORPTION",
        "D3_PRODUCT_VOLUME",
        "D3_UNIT_ECONOMICS",
        "D4_WORKING_CAPITAL_AND_CASH",
        "D5_CAPITAL_RETURN",
    ),
)


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _date_or_time(value: Any) -> datetime | None:
    """Parse a cutoff-comparable disclosure date or timezone-aware timestamp."""
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if len(candidate) == 10:
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return _time(candidate)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value \
        and value not in (float("inf"), float("-inf"))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _cash_transmission_gate_required(candidate: dict[str, Any]) -> bool:
    contract = candidate.get("selection_admission_contract")
    return isinstance(contract, dict) and contract.get("version") in SUPPORTED_ADMISSION_VERSIONS \
        and isinstance(contract.get("cash_transmission_requirement"), dict) \
        and contract["cash_transmission_requirement"].get("required") is True


def _is_v3_admission_contract(candidate: dict[str, Any]) -> bool:
    contract = candidate.get("selection_admission_contract")
    return isinstance(contract, dict) and contract.get("version") in SUPPORTED_ADMISSION_VERSIONS


def _is_v4_admission_contract(candidate: dict[str, Any]) -> bool:
    contract = candidate.get("selection_admission_contract")
    return isinstance(contract, dict) and contract.get("version") == PEER_PANEL_ADMISSION_VERSION


def _admission_version(candidate: dict[str, Any]) -> str | None:
    contract = candidate.get("selection_admission_contract")
    if not isinstance(contract, dict):
        return None
    version = contract.get("version")
    return version if isinstance(version, str) else None


def _customer_absorption_gate_required(candidate: dict[str, Any]) -> bool:
    contract = candidate.get("selection_admission_contract")
    return _is_v3_admission_contract(candidate) \
        and isinstance(contract.get("customer_absorption_requirement"), dict) \
        and contract["customer_absorption_requirement"].get("required") is True


def _v4_mechanism_topology(candidate: dict[str, Any]) -> str | None:
    contract = candidate.get("selection_admission_contract")
    if not isinstance(contract, dict) or contract.get("version") != PEER_PANEL_ADMISSION_VERSION:
        return None
    topology = contract.get("mechanism_topology")
    return topology if isinstance(topology, str) else None


def _validate_v4_cost_driver_observability(
    candidate: dict[str, Any], *, prediction_stages: dict[str, str],
    primary_hypothesis_id: str | None,
) -> tuple[list[str], bool]:
    """Validate the non-customer branch for a pure cost restructuring mechanism.

    D2 remains a diagnostic/non-voter in the universal five-layer timeline.
    This branch therefore does not relabel a cost series as customer acceptance;
    it instead requires a recurrent, source-bearing physical or efficiency
    driver before D3/D4 can be treated as a cost-restructuring test.
    """
    findings: list[str] = []
    valid = True
    driver = candidate.get("cost_driver_observability")
    if not isinstance(driver, dict):
        return ["v4_cost_driver_observability_required"], False
    if driver.get("gate_version") != PEER_PANEL_ADMISSION_VERSION \
            or driver.get("primary_hypothesis_id") != primary_hypothesis_id \
            or driver.get("failure_disposition") != V4_COST_DRIVER_NO_PRIMARY:
        findings.append("v4_cost_driver_identity_invalid")
        valid = False
    if driver.get("observation_kind") not in V4_COST_DRIVER_KINDS:
        findings.append("v4_cost_driver_kind_invalid")
        valid = False
    if prediction_stages.get(driver.get("d3_predicate_id")) != "D3_UNIT_ECONOMICS":
        findings.append("v4_cost_driver_d3_predicate_invalid")
        valid = False
    boundary = driver.get("boundary")
    cash_boundary = _dict(candidate.get("cash_transmission_observability")).get("common_boundary")
    if not _same_boundary(boundary, cash_boundary):
        findings.append("v4_cost_driver_boundary_mismatch")
        valid = False
    identity = driver.get("official_field_identity")
    if not isinstance(identity, dict) or not all(
        _text(identity.get(field)) for field in ("field_id", "definition", "source_class", "formula_or_field")
    ) or identity.get("source_class") != "OFFICIAL_DISCLOSURE":
        findings.append("v4_cost_driver_official_field_identity_invalid")
        valid = False
    signs = driver.get("hypothesis_signs")
    if not isinstance(signs, dict) or not _text(signs.get("H_A")) or not _text(signs.get("H_B")) \
            or signs.get("H_A") == signs.get("H_B"):
        findings.append("v4_cost_driver_hypothesis_signs_invalid")
        valid = False
    action = _dict(_dict(candidate.get("cash_transmission_observability")).get("materiality_anchors")).get(
        "action_exposure"
    )
    action_at = _date_or_time(_dict(action).get("implemented_or_incurred_at"))
    cutoff = _time(candidate.get("cutoff_at"))
    target = _dict(_dict(candidate.get("peer_panel_observability")).get("target"))
    issuer_id = str(target.get("issuer_id") or "")
    repetitions = driver.get("cutoff_before_repetitions")
    if not isinstance(repetitions, list) or len(repetitions) < 3:
        return findings + ["v4_cost_driver_not_recurrently_observable"], False
    periods: set[str] = set()
    definition = _dict(identity).get("definition")
    for index, repetition in enumerate(repetitions):
        prefix = f"v4_cost_driver_repetition[{index}]"
        if not isinstance(repetition, dict) or not all(
            _text(repetition.get(field)) for field in ("period_end", "published_at", "source_id", "field_ref")
        ):
            findings.append(prefix + "_identity_invalid")
            valid = False
            continue
        period_end = _date_or_time(repetition.get("period_end"))
        published_at = _date_or_time(repetition.get("published_at"))
        if period_end is None or published_at is None or cutoff is None or action_at is None \
                or period_end >= action_at or published_at >= action_at or period_end > cutoff:
            findings.append(prefix + "_not_pre_action")
            valid = False
        periods.add(str(repetition.get("period_end")))
        raw = repetition.get("raw_observation")
        if not isinstance(raw, dict) or not _finite_number(raw.get("value")) \
                or raw.get("unit") != _dict(boundary).get("unit") \
                or raw.get("definition") != definition:
            findings.append(prefix + "_raw_observation_invalid")
            valid = False
            continue
        evidence_findings, evidence_valid = _valid_v4_evidence_list(
            raw.get("evidence"), cutoff, issuer_id=issuer_id,
            perimeter_id=str(_dict(boundary).get("perimeter_id") or ""),
            prefix=prefix + "_evidence", boundary=boundary, available_before=action_at,
        )
        findings.extend(evidence_findings)
        if not evidence_valid:
            valid = False
    if len(periods) < 3:
        findings.append("v4_cost_driver_periods_not_recurrent")
        valid = False

    d2_non_voter = candidate.get("d2_non_voter_contract")
    if not isinstance(d2_non_voter, dict) \
            or d2_non_voter.get("d2_predicate_id") not in prediction_stages \
            or prediction_stages.get(d2_non_voter.get("d2_predicate_id")) != "D2_CUSTOMER_ABSORPTION" \
            or d2_non_voter.get("verdict") != "NOT_CAUSALLY_CENTRAL_PRE_OUTCOME" \
            or d2_non_voter.get("customer_absorption_conclusion_prohibited") is not True:
        findings.append("v4_cost_driver_d2_non_voter_contract_invalid")
        valid = False
    return findings, valid


def _validate_v4_customer_raw_repetitions(
    candidate: dict[str, Any], *, observability: dict[str, Any], cutoff: datetime | None,
) -> tuple[list[str], bool]:
    """Require V4 D2 to be a recurrent, source-bearing customer measure.

    A bare field name plus an analyst assertion cannot distinguish sell-through
    from a channel fill.  V4 therefore only accepts customer-facing measures
    and keeps the value, definition and channel position beside the official
    source for every pre-action period.
    """
    findings: list[str] = []
    valid = True
    if observability.get("observation_kind") not in V4_DIRECT_CUSTOMER_OBSERVATION_KINDS:
        return ["v4_customer_absorption_kind_not_direct_customer_measure"], False

    boundary = observability.get("boundary")
    identity = observability.get("official_field_identity")
    if not isinstance(boundary, dict) or not isinstance(identity, dict):
        return ["v4_customer_absorption_raw_identity_missing"], False
    action = _dict(_dict(candidate.get("cash_transmission_observability")).get("materiality_anchors")).get(
        "action_exposure"
    )
    action_at = _date_or_time(_dict(action).get("implemented_or_incurred_at"))
    if action_at is None:
        return ["v4_customer_absorption_action_time_missing"], False
    target = _dict(_dict(candidate.get("peer_panel_observability")).get("target"))

    periods: set[str] = set()
    definition = identity.get("definition")
    for index, repetition in enumerate(observability.get("cutoff_before_repetitions") or []):
        prefix = f"v4_customer_absorption_repetition[{index}]"
        if not isinstance(repetition, dict):
            findings.append(prefix + "_invalid")
            valid = False
            continue
        period_end = _date_or_time(repetition.get("period_end"))
        published_at = _date_or_time(repetition.get("published_at"))
        if period_end is None or period_end >= action_at:
            findings.append(prefix + "_not_pre_action")
            valid = False
        if published_at is None or cutoff is None or published_at > cutoff or published_at >= action_at:
            findings.append(prefix + "_not_disclosed_before_action")
            valid = False
        raw = repetition.get("raw_observation")
        if not isinstance(raw, dict) or set(raw) != {
            "value", "unit", "definition", "channel_position", "evidence",
        }:
            findings.append(prefix + "_raw_observation_invalid")
            valid = False
            continue
        if not _finite_number(raw.get("value")) or raw.get("unit") != boundary.get("unit"):
            findings.append(prefix + "_raw_value_or_unit_invalid")
            valid = False
        if raw.get("definition") != definition:
            findings.append(prefix + "_raw_definition_drift")
            valid = False
        if raw.get("channel_position") not in {
            "END_CUSTOMER", "INDEPENDENT_MARKET_PANEL", "DISCLOSED_CUSTOMER_BOOKING",
        }:
            findings.append(prefix + "_channel_position_not_customer_facing")
            valid = False
        evidence = raw.get("evidence")
        source_findings, source_valid = _valid_v4_evidence_list(
            [evidence], cutoff,
            issuer_id=str(target.get("issuer_id") or ""),
            perimeter_id=str(boundary.get("perimeter_id") or ""),
            boundary=boundary,
            prefix=prefix + ".raw_observation.evidence",
        )
        findings.extend(source_findings)
        if not source_valid:
            valid = False
        elif isinstance(evidence, dict) and evidence.get("source_id") != repetition.get("source_id"):
            findings.append(prefix + "_raw_source_id_mismatch")
            valid = False
        periods.add(str(repetition.get("period_end")))
    if len(periods) < 3:
        findings.append("v4_customer_absorption_raw_periods_not_recurrent")
        valid = False
    return findings, valid


def _validate_customer_absorption_observability(
    candidate: dict[str, Any], *, prediction_stages: dict[str, str], primary_hypothesis_id: str | None,
) -> tuple[list[str], bool]:
    """Validate that a D2 signal is independent of the decision being tested.

    Price, price-mix and capacity decisions can mechanically change a revenue
    numerator or a named capacity figure.  Those quantities do not establish
    customer absorption.  A new selection packet therefore needs a recurrent
    observable such as units, shipments, customers, channel inventory, or an
    independently disclosed volume-price decomposition on the same boundary.
    """
    contract = candidate.get("selection_admission_contract")
    if contract is None:
        return [], False
    if not isinstance(contract, dict):
        return ["selection_admission_contract_invalid"], False
    version = _admission_version(candidate)
    if version not in SUPPORTED_ADMISSION_VERSIONS:
        return ["selection_admission_contract_version_invalid"], False

    findings: list[str] = []
    force_no_primary = False
    requirement = contract.get("customer_absorption_requirement")
    if not isinstance(requirement, dict) or not isinstance(requirement.get("required"), bool):
        return ["customer_absorption_requirement_invalid"], True
    required = requirement["required"]
    expected_trigger = (
        CUSTOMER_ABSORPTION_REQUIRED_TRIGGER if required else CUSTOMER_ABSORPTION_NOT_REQUIRED_TRIGGER
    )
    if requirement.get("trigger") != expected_trigger or not _text(requirement.get("rationale")):
        findings.append("customer_absorption_requirement_trigger_invalid")

    observability = candidate.get("customer_absorption_observability")
    if not required:
        if observability is not None:
            findings.append("customer_absorption_observability_for_non_applicable_claim")
        return findings, force_no_primary
    if not isinstance(observability, dict):
        return findings + ["customer_absorption_observability_required"], True

    if observability.get("gate_version") != version:
        findings.append("customer_absorption_gate_version_invalid")
    if observability.get("primary_hypothesis_id") != primary_hypothesis_id:
        findings.append("customer_absorption_primary_hypothesis_mismatch")
    if observability.get("failure_disposition") != CUSTOMER_ABSORPTION_NO_PRIMARY:
        findings.append("customer_absorption_failure_disposition_invalid")
    predicate_id = observability.get("d2_predicate_id")
    if prediction_stages.get(predicate_id) != "D2_CUSTOMER_ABSORPTION":
        findings.append("customer_absorption_predicate_must_be_d2")
        force_no_primary = True
    if observability.get("observation_kind") not in CUSTOMER_ABSORPTION_OBSERVATION_KINDS:
        findings.append("customer_absorption_observation_kind_invalid")
        force_no_primary = True
    if observability.get("not_mechanically_changed_by_action") is not True:
        findings.append("customer_absorption_mechanical_independence_not_confirmed")
        force_no_primary = True

    prohibited = observability.get("prohibited_substitutes")
    expected_prohibitions = {
        "REVENUE_ALONE_WHEN_PRICE_OR_MIX_ACTION",
        "ANNOUNCED_OR_DESIGN_CAPACITY_AS_ACTUAL_DEMAND",
    }
    if not isinstance(prohibited, list) or set(prohibited) != expected_prohibitions:
        findings.append("customer_absorption_prohibited_substitutes_invalid")
        force_no_primary = True

    boundary = observability.get("boundary")
    boundary_fields = ("responsibility_unit_id", "perimeter_id", "unit")
    if not isinstance(boundary, dict) or any(not _text(boundary.get(field)) for field in boundary_fields):
        findings.append("customer_absorption_boundary_invalid")
        force_no_primary = True
    else:
        if boundary.get("responsibility_unit_id") != candidate.get("responsibility_unit_id"):
            findings.append("customer_absorption_responsibility_unit_mismatch")
            force_no_primary = True
        cash_boundary = candidate.get("cash_transmission_observability")
        cash_boundary = cash_boundary.get("common_boundary") if isinstance(cash_boundary, dict) else None
        # D2 may be measured in tonnes, cases or customers while D3/D4 are
        # currency measures.  The responsibility unit and consolidation
        # perimeter must match; requiring the physical unit to equal RMB would
        # make a valid independent demand signal impossible.
        if isinstance(cash_boundary, dict) and any(
            boundary.get(field) != cash_boundary.get(field)
            for field in ("responsibility_unit_id", "perimeter_id")
        ):
            findings.append("customer_absorption_cash_transmission_boundary_mismatch")
            force_no_primary = True

    identity = observability.get("official_field_identity")
    if not isinstance(identity, dict) or not all(
        _text(identity.get(field)) for field in ("field_id", "definition", "source_class", "formula_or_field")
    ) or identity.get("source_class") != "OFFICIAL_DISCLOSURE":
        findings.append("customer_absorption_official_field_identity_invalid")
        force_no_primary = True

    signs = observability.get("hypothesis_signs")
    if not isinstance(signs, dict) or not _text(signs.get("H_A")) or not _text(signs.get("H_B")) \
            or signs.get("H_A") == signs.get("H_B"):
        findings.append("customer_absorption_hypothesis_signs_invalid")
        force_no_primary = True

    cutoff = _time(candidate.get("cutoff_at"))
    repetitions = observability.get("cutoff_before_repetitions")
    if not isinstance(repetitions, list) or len(repetitions) < 3:
        return findings + ["customer_absorption_not_recurrently_observable"], True
    period_ends: set[str] = set()
    for index, repetition in enumerate(repetitions):
        prefix = f"customer_absorption_repetition[{index}]"
        if not isinstance(repetition, dict) or not all(
            _text(repetition.get(field)) for field in ("period_end", "published_at", "source_id", "field_ref")
        ):
            findings.append(prefix + "_invalid")
            force_no_primary = True
            continue
        published_at = _date_or_time(repetition.get("published_at"))
        if published_at is None or cutoff is None or published_at > cutoff:
            findings.append(prefix + "_not_before_cutoff")
            force_no_primary = True
        period_ends.add(str(repetition.get("period_end")))
    if len(period_ends) < 3:
        findings.append("customer_absorption_periods_not_recurrent")
        force_no_primary = True
    if version == PEER_PANEL_ADMISSION_VERSION:
        raw_findings, raw_valid = _validate_v4_customer_raw_repetitions(
            candidate, observability=observability, cutoff=cutoff,
        )
        findings.extend(raw_findings)
        if not raw_valid:
            force_no_primary = True
    return findings, force_no_primary


def _validate_cash_transmission_observability(
    candidate: dict[str, Any], *, prediction_stages: dict[str, str], primary_hypothesis_id: str | None,
) -> tuple[list[str], bool]:
    """Validate the v3 D3-to-D4 admission gate.

    The gate is deliberately structural.  It prevents a selection candidate
    from treating D3 accounting improvement as a substitute for normal owner
    cash, but leaves the economic judgment to the independent pre-outcome
    reviewer.  Any missing recurrent leg is a no-primary result, rather than a
    prompt to fill the gap with a favourable assumption.
    """
    findings: list[str] = []
    force_no_primary = False
    contract = candidate.get("selection_admission_contract")
    if contract is None:
        # v1 packets were sealed before this v3 admission contract existed.
        # They remain readable for audit; v3 callers must state the contract.
        return findings, force_no_primary
    if not isinstance(contract, dict):
        return ["selection_admission_contract_invalid"], force_no_primary
    version = _admission_version(candidate)
    if version not in SUPPORTED_ADMISSION_VERSIONS:
        return ["selection_admission_contract_version_invalid"], force_no_primary

    requirement = contract.get("cash_transmission_requirement")
    if not isinstance(requirement, dict) or not isinstance(requirement.get("required"), bool):
        return ["cash_transmission_requirement_invalid"], force_no_primary
    required = requirement["required"]
    expected_trigger = (
        CASH_TRANSMISSION_REQUIRED_TRIGGER if required else CASH_TRANSMISSION_NOT_REQUIRED_TRIGGER
    )
    if requirement.get("trigger") != expected_trigger or not _text(requirement.get("rationale")):
        findings.append("cash_transmission_requirement_trigger_invalid")
    observability = candidate.get("cash_transmission_observability")
    if not required:
        if observability is not None:
            findings.append("cash_transmission_observability_for_non_applicable_claim")
        return findings, force_no_primary

    if not isinstance(observability, dict):
        return findings + ["cash_transmission_observability_required"], True
    if observability.get("gate_version") != version:
        findings.append("cash_transmission_gate_version_invalid")
    if observability.get("primary_hypothesis_id") != primary_hypothesis_id:
        findings.append("cash_transmission_primary_hypothesis_mismatch")
    if observability.get("failure_disposition") != CASH_TRANSMISSION_NO_PRIMARY:
        findings.append("cash_transmission_failure_disposition_invalid")
    if observability.get("d3_d4_substitution_prohibited") is not True:
        findings.append("cash_transmission_d3_d4_substitution_not_prohibited")

    boundary = observability.get("common_boundary")
    boundary_fields = ("responsibility_unit_id", "perimeter_id", "unit")
    if not isinstance(boundary, dict) or any(not _text(boundary.get(field)) for field in boundary_fields):
        findings.append("cash_transmission_common_boundary_invalid")
    elif boundary.get("responsibility_unit_id") != candidate.get("responsibility_unit_id"):
        findings.append("cash_transmission_responsibility_unit_mismatch")

    legs = observability.get("transmission_legs")
    if not isinstance(legs, list):
        return findings + ["cash_transmission_legs_missing"], True
    leg_ids = [item.get("leg_id") if isinstance(item, dict) else None for item in legs]
    if tuple(leg_ids) != _CASH_TRANSMISSION_LEG_IDS:
        findings.append("cash_transmission_leg_topology_invalid")
        force_no_primary = True
    expected_leg_by_id = {leg_id: (clock, stage) for leg_id, clock, stage in CASH_TRANSMISSION_LEGS}
    cutoff = _time(candidate.get("cutoff_at"))
    for index, leg in enumerate(legs):
        if not isinstance(leg, dict):
            findings.append(f"cash_transmission_legs[{index}]_not_object")
            force_no_primary = True
            continue
        leg_id = leg.get("leg_id")
        expected = expected_leg_by_id.get(leg_id)
        if expected is None:
            continue
        expected_clock, expected_stage = expected
        if leg.get("clock") != expected_clock or leg.get("stage") != expected_stage:
            findings.append(f"cash_transmission_leg_{str(leg_id).lower()}_identity_invalid")
            force_no_primary = True
        signs = leg.get("hypothesis_signs")
        if not isinstance(signs, dict) or not _text(signs.get("H_A")) or not _text(signs.get("H_B")) \
                or signs.get("H_A") == signs.get("H_B"):
            findings.append(f"cash_transmission_leg_{str(leg_id).lower()}_hypothesis_signs_invalid")
            force_no_primary = True
        identity = leg.get("official_field_identity")
        if not isinstance(identity, dict) or not all(
            _text(identity.get(field)) for field in ("field_id", "definition", "source_class", "formula_or_field")
        ) or identity.get("source_class") != "OFFICIAL_DISCLOSURE":
            findings.append(f"cash_transmission_leg_{str(leg_id).lower()}_official_field_identity_invalid")
            force_no_primary = True
        leg_boundary = leg.get("boundary")
        boundary_matches = isinstance(boundary, dict) and isinstance(leg_boundary, dict) and all(
            leg_boundary.get(field) == boundary.get(field) for field in boundary_fields
        )
        if not boundary_matches:
            findings.append(f"cash_transmission_leg_{str(leg_id).lower()}_boundary_mismatch")
            force_no_primary = True
        repetitions = leg.get("cutoff_before_repetitions")
        if not isinstance(repetitions, list) or len(repetitions) < 3:
            findings.append(f"cash_transmission_leg_{str(leg_id).lower()}_not_recurrently_observable")
            force_no_primary = True
            continue
        period_ends: set[str] = set()
        for repetition_index, repetition in enumerate(repetitions):
            prefix = f"cash_transmission_leg_{str(leg_id).lower()}_repetition[{repetition_index}]"
            if not isinstance(repetition, dict) or not all(
                _text(repetition.get(field)) for field in ("period_end", "published_at", "source_id", "field_ref")
            ):
                findings.append(prefix + "_invalid")
                force_no_primary = True
                continue
            period_end = _date_or_time(repetition.get("period_end"))
            published_at = _date_or_time(repetition.get("published_at"))
            if period_end is None or published_at is None or cutoff is None \
                    or period_end > cutoff or published_at > cutoff:
                findings.append(prefix + "_not_cutoff_before")
                force_no_primary = True
            period_ends.add(str(repetition.get("period_end")))
        if len(period_ends) < 3:
            findings.append(f"cash_transmission_leg_{str(leg_id).lower()}_periods_not_recurrent")
            force_no_primary = True

    linkage = observability.get("d3_to_d4_linkage")
    if not isinstance(linkage, dict):
        findings.append("cash_transmission_d3_to_d4_linkage_missing")
        force_no_primary = True
    else:
        d3_predicate = linkage.get("d3_predicate_id")
        d4_predicate = linkage.get("d4_predicate_id")
        if prediction_stages.get(d3_predicate) != "D3_UNIT_ECONOMICS":
            findings.append("cash_transmission_d3_predicate_must_be_d3_unit_economics")
            force_no_primary = True
        if prediction_stages.get(d4_predicate) != "D4_WORKING_CAPITAL_AND_CASH":
            findings.append("cash_transmission_d4_predicate_must_be_d4_working_capital_and_cash")
            force_no_primary = True

    d4_formula = observability.get("d4_formula")
    if not isinstance(d4_formula, dict) or not all(
        _text(d4_formula.get(field)) for field in ("formula_id", "formula")
    ):
        findings.append("cash_transmission_d4_formula_invalid")
        force_no_primary = True
    else:
        if d4_formula.get("positive_working_capital_release_treatment") != "SUBTRACT_POSITIVE_RELEASE":
            findings.append("cash_transmission_positive_working_capital_release_not_subtracted")
            force_no_primary = True
        if d4_formula.get("capex_restructuring_cash_treatment") != "SUBTRACT_OBSERVED_CASH_NEVER_ASSUME_ZERO":
            findings.append("cash_transmission_capex_restructuring_cash_assumption_invalid")
            force_no_primary = True

    anchors = observability.get("materiality_anchors")
    anchor_ids: list[str] = []
    if not isinstance(anchors, dict):
        findings.append("cash_transmission_materiality_anchors_missing")
        force_no_primary = True
    else:
        for stage in ("D3_UNIT_ECONOMICS", "D4_WORKING_CAPITAL_AND_CASH"):
            anchor = anchors.get(stage)
            prefix = "cash_transmission_" + stage.lower()
            if not isinstance(anchor, dict) or anchor.get("stage") != stage or not all(
                _text(anchor.get(field)) for field in ("anchor_id", "anchor_statement", "predicate_id")
            ):
                findings.append(prefix + "_materiality_anchor_invalid")
                force_no_primary = True
                continue
            anchor_ids.append(anchor["anchor_id"])
            if prediction_stages.get(anchor.get("predicate_id")) != stage:
                findings.append(prefix + "_materiality_predicate_mismatch")
                force_no_primary = True
            source_ids = anchor.get("source_ids")
            if not isinstance(source_ids, list) or not source_ids or not all(_text(item) for item in source_ids):
                findings.append(prefix + "_materiality_sources_invalid")
                force_no_primary = True
            for threshold_name in ("primary_threshold", "rival_threshold"):
                threshold = anchor.get(threshold_name)
                threshold_valid = (
                    isinstance(threshold, dict)
                    and _text(threshold.get("operator"))
                    and _finite_number(threshold.get("value"))
                    and isinstance(boundary, dict)
                    and threshold.get("unit") == boundary.get("unit")
                )
                if not threshold_valid:
                    findings.append(prefix + f"_{threshold_name}_invalid")
                    force_no_primary = True
        if len(anchor_ids) == 2 and anchor_ids[0] == anchor_ids[1]:
            findings.append("cash_transmission_d3_d4_materiality_anchors_not_independent")
            force_no_primary = True
    return findings, force_no_primary


def _same_boundary(left: Any, right: Any) -> bool:
    """Return whether two admitted measurement boundaries are identical.

    V4 deliberately does not permit a favourable issuer, segment, currency, or
    accounting perimeter substitution between the action, the target history,
    and D3/D4.  The peer issuers have their own responsibility units, but each
    must use its listed consolidated issuer perimeter and the target must stay
    on the candidate's common D3/D4 boundary.
    """
    fields = ("responsibility_unit_id", "perimeter_id", "unit")
    return isinstance(left, dict) and isinstance(right, dict) and all(
        left.get(field) == right.get(field) for field in fields
    )


def _validate_v4_comparability_register(
    register: Any, *, period_ends: set[str], cutoff: datetime | None,
    action_at: datetime | None, issuer_id: str, boundary: dict[str, Any] | None,
    prefix: str,
) -> tuple[list[str], bool]:
    """Require a source-bearing comparable-history review for every panel member.

    The five target observations and three peer observations are only useful if
    they remain the same economic and accounting object.  This compact register
    makes the reviewer state and source each material comparison dimension for
    every selected period.  A known material break must be excluded by choosing
    a different continuous window; it may not be averaged away.
    """
    findings: list[str] = []
    valid = True
    if not isinstance(register, dict):
        return [prefix + "_missing"], False
    if register.get("verdict") != "COMPARABLE_PRE_ACTION_WINDOW":
        findings.append(prefix + "_verdict_invalid")
        valid = False
    reviewed_periods = register.get("reviewed_period_ends")
    if not isinstance(reviewed_periods, list) or set(reviewed_periods) != period_ends \
            or len(reviewed_periods) != len(period_ends):
        findings.append(prefix + "_period_coverage_invalid")
        valid = False
    dimensions = register.get("dimensions")
    if not isinstance(dimensions, list) or len(dimensions) != len(V4_COMPARABILITY_DIMENSIONS):
        return findings + [prefix + "_dimensions_invalid"], False
    seen_dimensions: set[str] = set()
    for dimension_index, dimension in enumerate(dimensions):
        item_prefix = f"{prefix}_dimension[{dimension_index}]"
        if not isinstance(dimension, dict) or dimension.get("dimension_id") not in V4_COMPARABILITY_DIMENSIONS:
            findings.append(item_prefix + "_identity_invalid")
            valid = False
            continue
        dimension_id = str(dimension["dimension_id"])
        seen_dimensions.add(dimension_id)
        statuses = dimension.get("period_statuses")
        if not isinstance(statuses, list) or len(statuses) != len(period_ends):
            findings.append(item_prefix + "_period_statuses_invalid")
            valid = False
            continue
        status_periods: set[str] = set()
        for status_index, status in enumerate(statuses):
            status_prefix = f"{item_prefix}_period[{status_index}]"
            if not isinstance(status, dict) or status.get("period_end") not in period_ends \
                    or status.get("status") != "COMPARABLE":
                findings.append(status_prefix + "_not_comparable")
                valid = False
                continue
            status_periods.add(str(status["period_end"]))
            evidence_findings, evidence_valid = _valid_v4_evidence_list(
                status.get("evidence"), cutoff, issuer_id=issuer_id,
                perimeter_id=str(_dict(boundary).get("perimeter_id") or ""),
                prefix=status_prefix + "_evidence", boundary=boundary,
                available_before=action_at,
            )
            findings.extend(evidence_findings)
            if not evidence_valid:
                valid = False
        if status_periods != period_ends:
            findings.append(item_prefix + "_period_set_invalid")
            valid = False
    if seen_dimensions != set(V4_COMPARABILITY_DIMENSIONS):
        findings.append(prefix + "_dimension_set_invalid")
        valid = False
    material_breaks = register.get("material_breaks_excluded_from_window")
    if not isinstance(material_breaks, list):
        findings.append(prefix + "_material_break_register_invalid")
        valid = False
    else:
        for index, event in enumerate(material_breaks):
            event_prefix = f"{prefix}_material_break[{index}]"
            if not isinstance(event, dict) or not _text(event.get("event_id")) \
                    or not _text(event.get("period_end")) \
                    or event.get("period_end") in period_ends:
                findings.append(event_prefix + "_invalid")
                valid = False
                continue
            evidence_findings, evidence_valid = _valid_v4_evidence_list(
                event.get("evidence"), cutoff, issuer_id=issuer_id,
                perimeter_id=str(_dict(boundary).get("perimeter_id") or ""),
                prefix=event_prefix + "_evidence", boundary=boundary,
                available_before=action_at,
            )
            findings.extend(evidence_findings)
            if not evidence_valid:
                valid = False
    return findings, valid


def _validate_v4_market_exposure(
    member: Any, *, context: Any, cutoff: datetime | None, action_at: datetime | None,
    issuer_id: str, boundary: dict[str, Any] | None, prefix: str,
) -> tuple[list[str], bool]:
    """Verify that a frozen peer is exposed to the same pre-action market.

    An `industry_id` is only a routing label.  The actual counterfactual needs
    a source-bearing common product/service, geography and customer-market
    statement for every frozen member before the action occurs.
    """
    findings: list[str] = []
    if not isinstance(context, dict) or not all(
        _text(context.get(field))
        for field in ("market_id", "product_or_service_scope", "geographic_scope", "customer_end_market_scope")
    ) or context.get("same_exogenous_shock_required") is not True:
        return [prefix + "_common_market_context_invalid"], False
    exposure = _dict(_dict(member).get("market_exposure"))
    if any(
        exposure.get(field) != context.get(field)
        for field in ("market_id", "product_or_service_scope", "geographic_scope", "customer_end_market_scope")
    ):
        return [prefix + "_market_exposure_identity_mismatch"], False
    evidence_findings, evidence_valid = _valid_v4_evidence_list(
        exposure.get("evidence"), cutoff,
        issuer_id=issuer_id,
        perimeter_id=str(_dict(boundary).get("perimeter_id") or ""),
        prefix=prefix + "_market_exposure_evidence", boundary=boundary,
        available_before=action_at,
    )
    findings.extend(evidence_findings)
    return findings, evidence_valid


def _validate_v4_cash_bridge_coverage(
    coverage: Any, *, target_observations: dict[str, dict[str, Any]],
    cutoff: datetime | None, action_at: datetime | None, issuer_id: str,
    boundary: dict[str, Any] | None, action_type: Any,
) -> tuple[list[str], bool]:
    """Ensure the owner-cash bridge is complete before a V4 case is admitted.

    V4 is intentionally limited to operating mechanisms.  It cannot use a
    company acquisition, disposal or lease reclassification as an apparent
    D3→D4 result, because the compact owner-cash formula does not identify that
    capital-allocation topology.  Within operating cases, the three formula
    components come from raw annual fields and action-related cash must be
    explicitly deducted or source-confirmed not applicable.
    """
    findings: list[str] = []
    valid = True
    if action_type not in V4_ALLOWED_OPERATIONAL_ACTION_TYPES:
        return ["v4_action_type_not_supported_by_operating_cash_bridge"], False
    if not isinstance(coverage, dict):
        return ["v4_d4_cash_bridge_coverage_missing"], False
    if coverage.get("verdict") != "COMPLETE_PRE_OUTCOME" \
            or coverage.get("accounting_perimeter") != V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER:
        findings.append("v4_d4_cash_bridge_coverage_identity_invalid")
        valid = False
    expected_periods = set(target_observations)
    if coverage.get("reviewed_period_ends") != sorted(expected_periods):
        findings.append("v4_d4_cash_bridge_period_coverage_invalid")
        valid = False
    if coverage.get("unmodeled_material_cash_items") != []:
        findings.append("v4_d4_cash_bridge_unmodeled_material_item_present")
        valid = False
    components = coverage.get("components")
    if not isinstance(components, list):
        return findings + ["v4_d4_cash_bridge_components_missing"], False
    component_map = {
        str(item.get("component_id")): item
        for item in components if isinstance(item, dict) and _text(item.get("component_id"))
    }
    if tuple(component_map) != V4_CASH_BRIDGE_COMPONENTS:
        findings.append("v4_d4_cash_bridge_component_topology_invalid")
        valid = False
    expected_treatments = {
        "OPERATING_CASH_FLOW": "INCLUDED_FROM_FROZEN_D4_RAW_FIELDS",
        "LONG_LIVED_ASSET_CASH": "INCLUDED_FROM_FROZEN_D4_RAW_FIELDS",
        "CASH_WORKING_CAPITAL": "INCLUDED_FROM_FROZEN_D4_RAW_FIELDS",
    }
    for component_id in V4_CASH_BRIDGE_COMPONENTS:
        component = component_map.get(component_id)
        if not isinstance(component, dict):
            continue
        treatment = component.get("treatment")
        if component_id in expected_treatments:
            if treatment != expected_treatments[component_id]:
                findings.append("v4_d4_cash_bridge_" + component_id.lower() + "_treatment_invalid")
                valid = False
            continue
        if treatment not in {"OBSERVED_AND_DEDUCTED", "NOT_APPLICABLE_SOURCE_CONFIRMED"}:
            findings.append("v4_d4_cash_bridge_action_related_cash_treatment_invalid")
            valid = False
        evidence_findings, evidence_valid = _valid_v4_evidence_list(
            component.get("evidence"), cutoff, issuer_id=issuer_id,
            perimeter_id=str(_dict(boundary).get("perimeter_id") or ""),
            prefix="v4_d4_cash_bridge_action_related_cash_evidence", boundary=boundary,
        )
        findings.extend(evidence_findings)
        if not evidence_valid:
            valid = False
    return findings, valid


def _valid_v4_evidence_list(
    value: Any,
    cutoff: datetime | None,
    *,
    issuer_id: str,
    perimeter_id: str,
    prefix: str,
    boundary: dict[str, Any] | None = None,
    control_group_id: str | None = None,
    available_before: datetime | None = None,
) -> tuple[list[str], bool]:
    """Validate a cutoff-before, official, same-issuer V4 evidence list.

    ``control_group_id`` turns this into a control-source check: the cited
    disclosure must name the same group as the frozen panel member, rather
    than merely carrying an arbitrary supporting-document reference.
    """
    findings: list[str] = []
    valid = True
    if not isinstance(value, list) or not value:
        return [prefix + "_missing"], False
    for index, evidence in enumerate(value):
        item_prefix = f"{prefix}[{index}]"
        if not isinstance(evidence, dict) or not all(
            _text(evidence.get(field))
            for field in ("source_id", "source_type", "issuer_id", "perimeter_id", "published_at", "field_ref")
        ):
            findings.append(item_prefix + "_invalid")
            valid = False
            continue
        if evidence.get("source_type") not in V4_OFFICIAL_EVIDENCE_SOURCE_TYPES:
            findings.append(item_prefix + "_source_type_not_official")
            valid = False
        if evidence.get("issuer_id") != issuer_id or evidence.get("perimeter_id") != perimeter_id:
            findings.append(item_prefix + "_issuer_or_perimeter_mismatch")
            valid = False
        if boundary is not None and (
            evidence.get("responsibility_unit_id") != boundary.get("responsibility_unit_id")
            or evidence.get("unit") != boundary.get("unit")
        ):
            findings.append(item_prefix + "_boundary_mismatch")
            valid = False
        if control_group_id is not None and evidence.get("observed_control_group_id") != control_group_id:
            findings.append(item_prefix + "_control_group_mismatch")
            valid = False
        published_at = _date_or_time(evidence.get("published_at"))
        if published_at is None or cutoff is None or published_at > cutoff:
            findings.append(item_prefix + "_not_cutoff_before")
            valid = False
        if available_before is not None and (published_at is None or published_at >= available_before):
            findings.append(item_prefix + "_not_disclosed_before_action")
            valid = False
    return findings, valid


def validate_v4_cohort_feasibility_record(
    record: Any,
    *,
    action_at: datetime | None,
    target_company_id: str | None = None,
    target_industry_id: str | None = None,
) -> dict[str, Any]:
    """Validate the cutoff-only, cohort-first input to a V4 discovery.

    This is intentionally an observability record, not a selection candidate:
    it proves that an industry panel existed before an action is picked, but
    contains no outcome values, peer ordering, or training authorization.
    """
    findings: list[str] = []
    if not isinstance(record, dict):
        return {"state": "INVALID", "findings": ["cohort_record_not_object"]}
    if record.get("schema_version") != V4_COHORT_FEASIBILITY_SCHEMA_VERSION:
        findings.append("cohort_schema_version_invalid")
    for field in ("cohort_id", "industry_id"):
        if not _text(record.get(field)):
            findings.append("cohort_" + field + "_missing")
    selection_as_of = _date_or_time(record.get("selection_as_of"))
    if selection_as_of is None:
        findings.append("cohort_selection_as_of_invalid")
    # Stage 0 is reviewable before an action is selected.  Once it is bound
    # into discovery, the caller supplies the actual action date and this is
    # the hard cohort-before-action gate.
    elif action_at is not None and selection_as_of >= action_at:
        findings.append("cohort_selection_as_of_not_before_action")
    if target_industry_id is not None and record.get("industry_id") != target_industry_id:
        findings.append("cohort_target_industry_mismatch")

    universe = record.get("universe")
    universe_ids: set[str] = set()
    if not isinstance(universe, dict) or not all(
        _text(universe.get(field)) for field in ("universe_id", "membership_rule")
    ):
        findings.append("cohort_universe_identity_invalid")
    else:
        # A five-company Stage-0 object establishes a disclosure-rich
        # feasibility sample.  It must not pretend to be a complete industry
        # universe; the complete eligible-universe/exclusion ledger is frozen
        # later, with a concrete action and final V4 peer panel.
        if universe.get("cohort_scope") != "PRE_ACTION_DISCLOSURE_FEASIBILITY_SAMPLE" \
                or universe.get("not_final_peer_universe") is not True:
            findings.append("cohort_universe_scope_not_pre_action_feasibility_sample")
        listed_ids = universe.get("listed_company_ids")
        if not isinstance(listed_ids, list) or len(listed_ids) < 5 or not all(_text(item) for item in listed_ids):
            findings.append("cohort_universe_requires_five_listed_issuers")
        else:
            universe_ids = set(str(item) for item in listed_ids)
            if len(universe_ids) != len(listed_ids):
                findings.append("cohort_universe_company_ids_not_unique")
    members = record.get("members")
    member_ids: list[str] = []
    controls: list[str] = []
    if not isinstance(members, list) or len(members) < 5:
        findings.append("cohort_members_requires_five_issuers")
    else:
        for index, member in enumerate(members):
            prefix = f"cohort_member[{index}]"
            if not isinstance(member, dict) or not all(
                _text(member.get(field)) for field in (
                    "company_id", "issuer_id", "responsibility_unit_id", "control_group_id", "industry_id",
                )
            ):
                findings.append(prefix + "_identity_invalid")
                continue
            member_ids.append(str(member["company_id"]))
            controls.append(str(member["control_group_id"]))
            if member.get("industry_id") != record.get("industry_id"):
                findings.append(prefix + "_industry_mismatch")
            boundary = member.get("boundary")
            if not isinstance(boundary, dict) \
                    or boundary.get("responsibility_unit_id") != member.get("responsibility_unit_id") \
                    or boundary.get("perimeter_id") != V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER:
                findings.append(prefix + "_listed_consolidated_boundary_invalid")
                continue
            for field, control_group_id in (
                ("industry_business_evidence", None),
                ("control_group_evidence", str(member["control_group_id"])),
            ):
                source_findings, source_valid = _valid_v4_evidence_list(
                    member.get(field), selection_as_of,
                    issuer_id=str(member["issuer_id"]),
                    perimeter_id=str(boundary.get("perimeter_id")),
                    boundary=boundary,
                    control_group_id=control_group_id,
                    prefix=prefix + "." + field,
                )
                findings.extend(source_findings)
                if not source_valid:
                    findings.append(prefix + "_" + field + "_invalid")
            disposition = member.get("final_peer_panel_disposition")
            if disposition not in V4_COHORT_FINAL_PEER_DISPOSITIONS \
                    or not _text(member.get("final_peer_panel_rationale")):
                findings.append(prefix + "_final_peer_panel_disposition_invalid")
            elif disposition == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK":
                source_findings, source_valid = _valid_v4_evidence_list(
                    member.get("comparability_break_evidence"), selection_as_of,
                    issuer_id=str(member["issuer_id"]),
                    perimeter_id=str(boundary.get("perimeter_id")),
                    boundary=boundary,
                    prefix=prefix + ".comparability_break_evidence",
                )
                findings.extend(source_findings)
                if not source_valid:
                    findings.append(prefix + "_comparability_break_evidence_invalid")
            d2 = member.get("d2_field_availability")
            if not isinstance(d2, dict) or not _text(d2.get("field_id")) or not _text(d2.get("definition")):
                findings.append(prefix + "_d2_availability_identity_invalid")
            else:
                repetitions = d2.get("repetitions")
                if not isinstance(repetitions, list) or len(repetitions) < 3:
                    findings.append(prefix + "_d2_availability_not_recurrent")
                else:
                    d2_periods: set[str] = set()
                    for repetition_index, repetition in enumerate(repetitions):
                        if not isinstance(repetition, dict) or not _text(repetition.get("period_end")):
                            findings.append(prefix + f"_d2_availability[{repetition_index}]_invalid")
                            continue
                        d2_periods.add(str(repetition["period_end"]))
                        source_findings, source_valid = _valid_v4_evidence_list(
                            repetition.get("evidence"), selection_as_of,
                            issuer_id=str(member["issuer_id"]),
                            perimeter_id=str(boundary.get("perimeter_id")),
                            boundary=boundary,
                            prefix=prefix + f".d2_availability[{repetition_index}].evidence",
                        )
                        findings.extend(source_findings)
                        if not source_valid:
                            findings.append(prefix + f"_d2_availability[{repetition_index}]_evidence_invalid")
                    if len(d2_periods) < 3:
                        findings.append(prefix + "_d2_availability_periods_not_distinct")
            annuals = member.get("annual_d3_d4_availability")
            if not isinstance(annuals, list) or len(annuals) < 5:
                findings.append(prefix + "_d3_d4_availability_requires_five_annuals")
            else:
                annual_periods: set[str] = set()
                for annual_index, annual in enumerate(annuals):
                    if not isinstance(annual, dict) or not _text(annual.get("period_end")):
                        findings.append(prefix + f"_annual_availability[{annual_index}]_invalid")
                        continue
                    annual_periods.add(str(annual["period_end"]))
                    source_findings, source_valid = _valid_v4_evidence_list(
                        annual.get("evidence"), selection_as_of,
                        issuer_id=str(member["issuer_id"]),
                        perimeter_id=str(boundary.get("perimeter_id")),
                        boundary=boundary,
                        prefix=prefix + f".annual_availability[{annual_index}].evidence",
                    )
                    findings.extend(source_findings)
                    if not source_valid:
                        findings.append(prefix + f"_annual_availability[{annual_index}]_evidence_invalid")
                if len(annual_periods) < 5:
                    findings.append(prefix + "_annual_availability_periods_not_distinct")
    if len(set(member_ids)) != len(member_ids) or set(member_ids) != universe_ids:
        findings.append("cohort_members_not_exact_universe")
    if len(set(controls)) != len(controls):
        findings.append("cohort_members_not_control_independent")
    if target_company_id is not None and target_company_id not in member_ids:
        findings.append("cohort_target_not_member")
    return {"state": "REVIEWABLE" if not findings else "INVALID", "findings": findings}


def _same_h2_citation_list(candidate_value: Any, screen_value: Any) -> bool:
    """Require an ordered candidate citation list to be the H2 screen record.

    A source id is not a sufficient binding: one static PDF can contain both
    the action disclosure and an unrelated field on a different page.  H2 has
    already validated its own citations against its declared PDF pages; this
    comparison prevents the later candidate from substituting another page,
    issuer identity, or publication timestamp from the same PDF catalogue.
    """
    return isinstance(candidate_value, list) and isinstance(screen_value, list) \
        and candidate_value == screen_value


def _candidate_cutoff_facts_match_h2(candidate_facts: Any, screen_facts: Any) -> bool:
    """Require V4 facts to retain the complete H2 fact citations verbatim."""
    if not isinstance(candidate_facts, list) or not isinstance(screen_facts, list) \
            or len(candidate_facts) != len(screen_facts):
        return False
    for candidate_fact, screen_fact in zip(candidate_facts, screen_facts):
        if not isinstance(candidate_fact, dict) or not isinstance(screen_fact, dict):
            return False
        expected = {
            "fact_id": screen_fact.get("fact_id"),
            "statement": screen_fact.get("statement"),
            "selection_classification": "DECISIVE",
            "source_ids": [
                evidence.get("source_id")
                for evidence in screen_fact.get("evidence", [])
                if isinstance(evidence, dict)
            ],
            "evidence": screen_fact.get("evidence"),
        }
        if "evidence_scope" in screen_fact:
            expected["evidence_scope"] = screen_fact["evidence_scope"]
        if candidate_fact != expected:
            return False
    return True


def _candidate_repetition_matches_h2(
    candidate_repetition: Any, screen_repetition: Any, raw_evidence: Any,
) -> bool:
    """Lock one candidate D2/cost raw observation to its same-period H2 cite."""
    if not isinstance(candidate_repetition, dict) or not isinstance(screen_repetition, dict):
        return False
    screen_evidence = screen_repetition.get("evidence")
    if not _same_h2_citation_list(raw_evidence, screen_evidence):
        return False
    if not isinstance(screen_evidence, list) or len(screen_evidence) != 1 \
            or not isinstance(screen_evidence[0], dict):
        return False
    citation = screen_evidence[0]
    return candidate_repetition.get("source_id") == citation.get("source_id") \
        and candidate_repetition.get("published_at") == citation.get("published_at") \
        and candidate_repetition.get("field_ref") == citation.get("field_ref")


def _h1_h2_static_source_map(
    stage0_package: dict[str, Any], action_screen_extension: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return the closed source universe already admitted by H1 and H2.

    H1 freezes the cohort's static annual-PDF catalogue; H2 can add only the
    static PDFs required for its single action screen.  The H2 validator has
    already checked source uniqueness, static-CNINFO identity and cutoff
    timing before this helper is reached, so this is an index rather than a
    second source-policy implementation.
    """
    source_map: dict[str, dict[str, Any]] = {}
    for stage, declared in (
        ("H1", stage0_package.get("static_pdf_sources")),
        ("H2", action_screen_extension.get("static_pdf_sources")),
    ):
        if not isinstance(declared, list):
            continue
        for source in declared:
            if not isinstance(source, dict) or not _text(source.get("source_id")):
                continue
            source_id = str(source["source_id"])
            source_map[source_id] = {
                **source,
                "field_refs": set(source.get("field_refs") or ()),
                "source_stage": stage,
            }
    return source_map


def _validate_h1_h2_source_id(
    source_id: Any, *, source_map: dict[str, dict[str, Any]], prefix: str, findings: list[str],
    allowed_stages: tuple[str, ...] | None = None,
) -> None:
    """Check an identifier-only citation where the modeled field has no page slot."""
    if not _text(source_id) or str(source_id) not in source_map:
        findings.append(prefix + "_source_id_not_declared_in_h1_h2_static_pdf_map")
    elif allowed_stages is not None and source_map[str(source_id)].get("source_stage") not in allowed_stages:
        findings.append(prefix + "_must_cite_h1_annual_static_pdf")


def _validate_h1_h2_static_citation(
    citation: Any,
    *,
    source_map: dict[str, dict[str, Any]],
    prefix: str,
    findings: list[str],
    issuer_id: str | None = None,
    boundary: dict[str, Any] | None = None,
    period_end: str | None = None,
    allowed_stages: tuple[str, ...] | None = None,
) -> None:
    """Bind one modeled citation to its declared static-PDF identity.

    The candidate formats differ slightly: raw D3/D4 fields omit a repeated
    responsibility-unit field while V4 evidence records include it.  The
    expected boundary fills that modeled omission and is compared with the
    declaration; every identity value that *is* carried by the citation must
    still match exactly, including the page reference and publication time.
    """
    if not isinstance(citation, dict):
        findings.append(prefix + "_citation_invalid")
        return
    source_id = citation.get("source_id")
    if not _text(source_id):
        findings.append(prefix + "_source_id_not_declared_in_h1_h2_static_pdf_map")
        return
    source = source_map.get(str(source_id))
    if source is None:
        findings.append(prefix + "_source_id_not_declared_in_h1_h2_static_pdf_map")
        return
    if allowed_stages is not None and source.get("source_stage") not in allowed_stages:
        findings.append(prefix + "_must_cite_h1_annual_static_pdf")
    field_ref = citation.get("field_ref")
    if not _text(field_ref) or str(field_ref) not in source["field_refs"]:
        findings.append(prefix + "_field_ref_not_declared_static_pdf_page")
    for field in ("source_type", "issuer_id", "perimeter_id", "responsibility_unit_id", "unit", "published_at"):
        if field in citation and citation.get(field) != source.get(field):
            findings.append(prefix + "_" + field + "_does_not_match_declared_static_pdf_identity")
    if issuer_id is not None and source.get("issuer_id") != issuer_id:
        findings.append(prefix + "_declared_static_pdf_issuer_mismatch")
    if boundary is not None:
        for field in ("responsibility_unit_id", "perimeter_id", "unit"):
            if source.get(field) != boundary.get(field):
                findings.append(prefix + "_declared_static_pdf_boundary_mismatch")
                break
    # H1 annual declarations carry the covered period.  H2 permits an action
    # disclosure without that annual-period field, so compare it only when it
    # is part of the declared source identity.
    if period_end is not None and "period_end" in source and source.get("period_end") != period_end:
        findings.append(prefix + "_declared_static_pdf_period_end_mismatch")


def _validate_h1_h2_evidence_list(
    evidence: Any,
    *, source_map: dict[str, dict[str, Any]], prefix: str, findings: list[str],
    issuer_id: str | None, boundary: dict[str, Any] | None,
    allowed_stages: tuple[str, ...] | None = None,
) -> None:
    if not isinstance(evidence, list):
        return
    for index, citation in enumerate(evidence):
        _validate_h1_h2_static_citation(
            citation, source_map=source_map, prefix=f"{prefix}[{index}]", findings=findings,
            issuer_id=issuer_id, boundary=boundary, allowed_stages=allowed_stages,
        )


def _validate_h1_h2_raw_history(
    observations: Any,
    *, source_map: dict[str, dict[str, Any]], prefix: str, findings: list[str],
    issuer_id: str | None, boundary: dict[str, Any] | None,
) -> None:
    """Bind every target/peer raw D3 and D4 input, not a derived scalar."""
    if not isinstance(observations, list):
        return
    for observation_index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            continue
        period_end = observation.get("period_end")
        for section in ("d3_raw_fields", "d4_raw_fields"):
            raw_fields = observation.get(section)
            if not isinstance(raw_fields, dict):
                continue
            for field_name, citation in raw_fields.items():
                _validate_h1_h2_static_citation(
                    citation, source_map=source_map,
                    prefix=f"{prefix}[{observation_index}].{section}.{field_name}", findings=findings,
                    issuer_id=issuer_id, boundary=boundary,
                    period_end=str(period_end) if _text(period_end) else None,
                    allowed_stages=("H1",),
                )


def _validate_h1_h2_comparability_register(
    register: Any,
    *, source_map: dict[str, dict[str, Any]], prefix: str, findings: list[str],
    issuer_id: str | None, boundary: dict[str, Any] | None,
) -> None:
    if not isinstance(register, dict):
        return
    dimensions = register.get("dimensions")
    if isinstance(dimensions, list):
        for dimension_index, dimension in enumerate(dimensions):
            if not isinstance(dimension, dict):
                continue
            statuses = dimension.get("period_statuses")
            if not isinstance(statuses, list):
                continue
            for status_index, status in enumerate(statuses):
                if isinstance(status, dict):
                    _validate_h1_h2_evidence_list(
                        status.get("evidence"), source_map=source_map,
                        prefix=f"{prefix}.dimensions[{dimension_index}].period_statuses[{status_index}].evidence",
                        findings=findings, issuer_id=issuer_id, boundary=boundary,
                        allowed_stages=("H1",),
                    )
    breaks = register.get("material_breaks_excluded_from_window")
    if isinstance(breaks, list):
        for break_index, event in enumerate(breaks):
            if isinstance(event, dict):
                _validate_h1_h2_evidence_list(
                    event.get("evidence"), source_map=source_map,
                    prefix=f"{prefix}.material_breaks_excluded_from_window[{break_index}].evidence",
                    findings=findings, issuer_id=issuer_id, boundary=boundary,
                )


def _validate_h1_h2_pre_outcome_source_binding(
    candidate: dict[str, Any], *, source_map: dict[str, dict[str, Any]],
) -> list[str]:
    """Require every modeled pre-outcome citation to stay inside H1∪H2.

    This is deliberately an explicit inventory of the V4 evidence-bearing
    fields.  It does not walk arbitrary nested JSON, and it does not create a
    runtime registry: it closes only the source paths already used to support
    action materiality, D2/cost observability, raw D3/D4, panel selection,
    comparability, cash-bridge completeness and cutoff facts.  H1 must carry
    the multi-member annual/control/market history (raw D3/D4, panel,
    comparability and D3/D4 cash history); H2 may supply the one action-screen
    source set and its target D2/cost or facts, while still being able to cite
    an already-declared H1 PDF instead of redeclaring it.
    """
    findings: list[str] = []
    panel = _dict(candidate.get("peer_panel_observability"))
    target = _dict(panel.get("target"))
    target_boundary = target.get("boundary") if isinstance(target.get("boundary"), dict) else None
    target_issuer_id = str(target.get("issuer_id")) if _text(target.get("issuer_id")) else None

    facts = candidate.get("cutoff_before_facts")
    if isinstance(facts, list):
        for fact_index, fact in enumerate(facts):
            if isinstance(fact, dict) and isinstance(fact.get("source_ids"), list):
                for source_index, source_id in enumerate(fact["source_ids"]):
                    _validate_h1_h2_source_id(
                        source_id, source_map=source_map,
                        prefix=f"cutoff_before_facts[{fact_index}].source_ids[{source_index}]", findings=findings,
                    )

    cash = _dict(candidate.get("cash_transmission_observability"))
    cash_boundary = cash.get("common_boundary") if isinstance(cash.get("common_boundary"), dict) else None
    for leg_index, leg in enumerate(cash.get("transmission_legs") if isinstance(cash.get("transmission_legs"), list) else []):
        if not isinstance(leg, dict):
            continue
        leg_boundary = leg.get("boundary") if isinstance(leg.get("boundary"), dict) else cash_boundary
        for repetition_index, repetition in enumerate(
            leg.get("cutoff_before_repetitions") if isinstance(leg.get("cutoff_before_repetitions"), list) else []
        ):
            _validate_h1_h2_static_citation(
                repetition, source_map=source_map,
                prefix=f"cash_transmission_observability.transmission_legs[{leg_index}].cutoff_before_repetitions[{repetition_index}]",
                findings=findings, issuer_id=target_issuer_id, boundary=leg_boundary,
                period_end=str(repetition.get("period_end")) if isinstance(repetition, dict) and _text(repetition.get("period_end")) else None,
                allowed_stages=("H1",),
            )
    anchors = cash.get("materiality_anchors")
    if isinstance(anchors, dict):
        for anchor_name, anchor in anchors.items():
            if not isinstance(anchor, dict):
                continue
            if isinstance(anchor.get("source_ids"), list):
                for source_index, source_id in enumerate(anchor["source_ids"]):
                    _validate_h1_h2_source_id(
                        source_id, source_map=source_map,
                        prefix=f"cash_transmission_observability.materiality_anchors.{anchor_name}.source_ids[{source_index}]",
                        findings=findings, allowed_stages=("H1",),
                    )
        action = _dict(anchors.get("action_exposure"))
        for field in ("issuer_scope_bridge", "decision_specificity"):
            _validate_h1_h2_evidence_list(
                _dict(action.get(field)).get("evidence"), source_map=source_map,
                prefix=f"cash_transmission_observability.materiality_anchors.action_exposure.{field}.evidence",
                findings=findings, issuer_id=target_issuer_id, boundary=cash_boundary,
            )
        _validate_h1_h2_evidence_list(
            action.get("implementation_evidence"), source_map=source_map,
            prefix="cash_transmission_observability.materiality_anchors.action_exposure.implementation_evidence",
            findings=findings, issuer_id=target_issuer_id, boundary=cash_boundary,
        )
        _validate_h1_h2_evidence_list(
            _dict(action.get("exposure")).get("evidence"), source_map=source_map,
            prefix="cash_transmission_observability.materiality_anchors.action_exposure.exposure.evidence",
            findings=findings, issuer_id=target_issuer_id, boundary=cash_boundary,
        )
    coverage = _dict(cash.get("d4_cash_bridge_coverage"))
    for component_index, component in enumerate(coverage.get("components") if isinstance(coverage.get("components"), list) else []):
        if isinstance(component, dict) and "evidence" in component:
            _validate_h1_h2_evidence_list(
                component.get("evidence"), source_map=source_map,
                prefix=f"cash_transmission_observability.d4_cash_bridge_coverage.components[{component_index}].evidence",
                findings=findings, issuer_id=target_issuer_id, boundary=cash_boundary,
            )

    customer = _dict(candidate.get("customer_absorption_observability"))
    customer_boundary = customer.get("boundary") if isinstance(customer.get("boundary"), dict) else None
    for repetition_index, repetition in enumerate(
        customer.get("cutoff_before_repetitions") if isinstance(customer.get("cutoff_before_repetitions"), list) else []
    ):
        _validate_h1_h2_static_citation(
            repetition, source_map=source_map,
            prefix=f"customer_absorption_observability.cutoff_before_repetitions[{repetition_index}]",
            findings=findings, issuer_id=target_issuer_id, boundary=customer_boundary,
            period_end=str(repetition.get("period_end")) if isinstance(repetition, dict) and _text(repetition.get("period_end")) else None,
        )
        if isinstance(repetition, dict):
            _validate_h1_h2_static_citation(
                _dict(repetition.get("raw_observation")).get("evidence"), source_map=source_map,
                prefix=f"customer_absorption_observability.cutoff_before_repetitions[{repetition_index}].raw_observation.evidence",
                findings=findings, issuer_id=target_issuer_id, boundary=customer_boundary,
                period_end=str(repetition.get("period_end")) if _text(repetition.get("period_end")) else None,
            )

    driver = _dict(candidate.get("cost_driver_observability"))
    driver_boundary = driver.get("boundary") if isinstance(driver.get("boundary"), dict) else cash_boundary
    for repetition_index, repetition in enumerate(
        driver.get("cutoff_before_repetitions") if isinstance(driver.get("cutoff_before_repetitions"), list) else []
    ):
        _validate_h1_h2_static_citation(
            repetition, source_map=source_map,
            prefix=f"cost_driver_observability.cutoff_before_repetitions[{repetition_index}]",
            findings=findings, issuer_id=target_issuer_id, boundary=driver_boundary,
            period_end=str(repetition.get("period_end")) if isinstance(repetition, dict) and _text(repetition.get("period_end")) else None,
        )
        if isinstance(repetition, dict):
            _validate_h1_h2_evidence_list(
                _dict(repetition.get("raw_observation")).get("evidence"), source_map=source_map,
                prefix=f"cost_driver_observability.cutoff_before_repetitions[{repetition_index}].raw_observation.evidence",
                findings=findings, issuer_id=target_issuer_id, boundary=driver_boundary,
            )

    members = [("target", target), *[
        (f"peers[{index}]", peer)
        for index, peer in enumerate(panel.get("peers") if isinstance(panel.get("peers"), list) else [])
        if isinstance(peer, dict)
    ]]
    for member_name, member in members:
        member_boundary = member.get("boundary") if isinstance(member.get("boundary"), dict) else None
        member_issuer_id = str(member.get("issuer_id")) if _text(member.get("issuer_id")) else None
        _validate_h1_h2_evidence_list(
            member.get("control_group_evidence"), source_map=source_map,
            prefix=f"peer_panel_observability.{member_name}.control_group_evidence",
            findings=findings, issuer_id=member_issuer_id, boundary=member_boundary,
            allowed_stages=("H1",),
        )
        _validate_h1_h2_evidence_list(
            _dict(member.get("market_exposure")).get("evidence"), source_map=source_map,
            prefix=f"peer_panel_observability.{member_name}.market_exposure.evidence",
            findings=findings, issuer_id=member_issuer_id, boundary=member_boundary,
            allowed_stages=("H1",),
        )
        _validate_h1_h2_raw_history(
            member.get("annual_d3_d4_raw_observations"), source_map=source_map,
            prefix=f"peer_panel_observability.{member_name}.annual_d3_d4_raw_observations",
            findings=findings, issuer_id=member_issuer_id, boundary=member_boundary,
        )
        _validate_h1_h2_comparability_register(
            member.get("comparability_register"), source_map=source_map,
            prefix=f"peer_panel_observability.{member_name}.comparability_register",
            findings=findings, issuer_id=member_issuer_id, boundary=member_boundary,
        )
    return findings


def _validate_v4_discovery_binding(candidate: dict[str, Any]) -> tuple[list[str], bool]:
    """Bind V4 to a strict H1 receipt and one closed H2 action screen.

    ``triage_selection_discovery_manifest`` remains a useful compatibility
    predicate, but it is no longer an admissible caller input.  V4 derives it
    here from the H1 static cohort and H2's one-time static-PDF screen so a
    later candidate cannot append a source, member, action or hypothesis.
    """
    findings: list[str] = []
    binding = candidate.get("discovery_binding")
    if not isinstance(binding, dict) or binding.get("schema_version") != V4_DISCOVERY_BINDING_SCHEMA_VERSION:
        return ["v4_discovery_binding_missing_or_schema_invalid"], True
    stage0_package = binding.get("stage0_static_package")
    action_screen_extension = binding.get("action_screen_extension")
    if not isinstance(stage0_package, dict):
        return ["v4_discovery_binding_stage0_static_package_missing"], True
    if not isinstance(action_screen_extension, dict):
        return ["v4_discovery_binding_action_screen_extension_missing"], True
    try:
        from scripts import judgment_selection_discovery as discovery
    except ModuleNotFoundError:  # pragma: no cover - direct-script import path
        import judgment_selection_discovery as discovery
    screen = discovery.validate_action_screen_static_extension(stage0_package, action_screen_extension)
    if screen.get("state") != discovery.ACTION_SCREEN_REVIEWABLE:
        findings.append("v4_discovery_binding_action_screen_not_reviewable")
        findings.extend("v4_discovery_binding." + str(item) for item in screen.get("findings", []))
        return findings, True
    manifest = screen.get("projected_legacy_manifest")
    if not isinstance(manifest, dict):  # Defensive only: a REVIEWABLE screen must project one manifest.
        return ["v4_discovery_binding_action_screen_projection_missing"], True

    identity = _dict(manifest.get("candidate_identity"))
    boundary = identity.get("common_boundary")
    target = _dict(_dict(candidate.get("peer_panel_observability")).get("target"))
    expected_identity = {
        "company_id": candidate.get("company_id"),
        "industry_id": candidate.get("industry_id"),
        "responsibility_unit_id": candidate.get("responsibility_unit_id"),
    }
    if any(identity.get(key) != value for key, value in expected_identity.items()) \
            or not _same_boundary(boundary, target.get("boundary")) \
            or manifest.get("cutoff_at") != candidate.get("cutoff_at"):
        findings.append("v4_discovery_binding_candidate_identity_or_cutoff_mismatch")
    cohort = _dict(manifest.get("cohort_feasibility_record"))
    cohort_members = [
        item for item in cohort.get("members") or []
        if isinstance(item, dict) and _text(item.get("company_id"))
    ]
    cohort_member_ids = {str(item["company_id"]) for item in cohort_members}
    known_material_break_ids = {
        str(item["company_id"])
        for item in cohort_members
        if item.get("final_peer_panel_disposition") == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    }
    frozen_panel = _dict(_dict(candidate.get("peer_panel_observability")).get("frozen_panel"))
    frozen_order = frozen_panel.get("frozen_order")
    if not isinstance(frozen_order, list) or not all(_text(item) for item in frozen_order) \
            or not set(str(item) for item in frozen_order).issubset(cohort_member_ids):
        findings.append("v4_discovery_binding_frozen_panel_not_from_stage0_cohort")
    else:
        for company_id in sorted(known_material_break_ids.intersection(str(item) for item in frozen_order)):
            findings.append(
                "v4_discovery_binding_known_material_scope_or_control_break_in_final_panel:" + company_id
            )
    exclusions = frozen_panel.get("exclusions")
    excluded_ids = {
        str(item.get("company_id"))
        for item in exclusions if isinstance(item, dict) and _text(item.get("company_id"))
    } if isinstance(exclusions, list) else set()
    for company_id in sorted(known_material_break_ids - excluded_ids):
        findings.append(
            "v4_discovery_binding_known_material_scope_or_control_break_missing_final_exclusion:"
            + company_id
        )

    # The action screen, rather than the legacy projection, is the canonical
    # record for every H2 citation copied into the candidate.
    action = _dict(action_screen_extension.get("action"))
    candidate_action = _dict(
        _dict(_dict(candidate.get("cash_transmission_observability")).get("materiality_anchors")).get(
            "action_exposure"
        )
    )
    if any(action.get(key) != candidate_action.get(key) for key in (
        "action_id", "action_statement", "action_state", "economic_action_type", "implemented_or_incurred_at",
    )) or not _same_boundary(action.get("boundary"), candidate_action.get("boundary")):
        findings.append("v4_discovery_binding_action_identity_mismatch")
    if not _same_h2_citation_list(
        candidate_action.get("implementation_evidence"), action.get("implementation_evidence"),
    ):
        findings.append("v4_discovery_binding_action_evidence_mismatch")
    action_scope_bridge = _dict(action.get("issuer_scope_bridge"))
    candidate_scope_bridge = _dict(candidate_action.get("issuer_scope_bridge"))
    if {key: value for key, value in action_scope_bridge.items() if key != "evidence"} != {
        key: value for key, value in candidate_scope_bridge.items() if key != "evidence"
    } or not _same_h2_citation_list(
        candidate_scope_bridge.get("evidence"), action_scope_bridge.get("evidence"),
    ):
        findings.append("v4_discovery_binding_action_scope_bridge_mismatch")
    action_specificity = _dict(action.get("decision_specificity"))
    candidate_specificity = _dict(candidate_action.get("decision_specificity"))
    if {key: value for key, value in action_specificity.items() if key != "evidence"} != {
        key: value for key, value in candidate_specificity.items() if key != "evidence"
    } or not _same_h2_citation_list(
        candidate_specificity.get("evidence"), action_specificity.get("evidence"),
    ):
        findings.append("v4_discovery_binding_action_decision_specificity_mismatch")
    action_exposure = _dict(action.get("exposure"))
    candidate_exposure = _dict(candidate_action.get("exposure"))
    if any(action_exposure.get(key) != candidate_exposure.get(key) for key in ("kind", "actual_basis")) \
            or not _same_h2_citation_list(
                candidate_exposure.get("evidence"), action_exposure.get("evidence"),
            ):
        findings.append("v4_discovery_binding_action_exposure_mismatch")
    elif action_exposure.get("kind") == "IMPLEMENTED_NET_PRICE_DELTA_X_PREACTION_ACTUAL_UNITS" \
            and (
                candidate_exposure.get("price_delta_field_ref")
                != action_exposure.get("implemented_net_price_delta_field_ref")
                or candidate_exposure.get("preaction_actual_units_field_ref")
                != action_exposure.get("preaction_actual_units_field_ref")
            ):
        findings.append("v4_discovery_binding_action_exposure_mismatch")
    if not _candidate_cutoff_facts_match_h2(
        candidate.get("cutoff_before_facts"), action_screen_extension.get("cutoff_before_facts"),
    ):
        findings.append("v4_discovery_binding_cutoff_before_facts_mismatch")

    pair = _dict(manifest.get("hypothesis_pair"))
    candidate_pair = _dict(candidate.get("rival_hypothesis_pair"))
    primary = _dict(pair.get("primary"))
    rival = _dict(pair.get("strongest_rival"))
    candidate_primary = _dict(candidate_pair.get("primary_hypothesis"))
    candidate_rival = _dict(candidate_pair.get("strongest_rival"))
    if primary.get("hypothesis_id") != candidate_primary.get("hypothesis_id") \
            or primary.get("mechanism") != candidate_primary.get("mechanism") \
            or rival.get("hypothesis_id") != candidate_rival.get("hypothesis_id") \
            or rival.get("mechanism") != candidate_rival.get("mechanism"):
        findings.append("v4_discovery_binding_hypothesis_pair_mismatch")

    topology = _v4_mechanism_topology(candidate)
    if manifest.get("mechanism_topology") != topology:
        findings.append("v4_discovery_binding_mechanism_topology_mismatch")
    if topology == V4_CUSTOMER_RESPONSE_CHAIN:
        d2 = _dict(action_screen_extension.get("d2_observability"))
        candidate_d2 = _dict(candidate.get("customer_absorption_observability"))
        if d2.get("primary_hypothesis_id") != candidate_d2.get("primary_hypothesis_id") \
                or d2.get("observation_kind") != candidate_d2.get("observation_kind") \
                or d2.get("field_id") != _dict(candidate_d2.get("official_field_identity")).get("field_id") \
                or not _same_boundary(d2.get("boundary"), candidate_d2.get("boundary")):
            findings.append("v4_discovery_binding_d2_identity_mismatch")
        manifest_repetitions = _dict_by_period(d2.get("repetitions"))
        candidate_repetitions = _dict_by_period(candidate_d2.get("cutoff_before_repetitions"))
        if set(manifest_repetitions) != set(candidate_repetitions):
            findings.append("v4_discovery_binding_d2_repetitions_mismatch")
        else:
            for period, screen_repetition in manifest_repetitions.items():
                candidate_repetition = candidate_repetitions[period]
                raw_evidence = _dict(candidate_repetition.get("raw_observation")).get("evidence")
                if not _candidate_repetition_matches_h2(
                    candidate_repetition, screen_repetition,
                    [raw_evidence] if isinstance(raw_evidence, dict) else raw_evidence,
                ):
                    findings.append("v4_discovery_binding_d2_repetition_citation_mismatch:" + period)
    elif topology == V4_COST_RESTRUCTURING_CHAIN:
        driver = _dict(action_screen_extension.get("cost_driver_observability"))
        candidate_driver = _dict(candidate.get("cost_driver_observability"))
        if driver.get("primary_hypothesis_id") != candidate_driver.get("primary_hypothesis_id") \
                or driver.get("observation_kind") != candidate_driver.get("observation_kind") \
                or driver.get("field_id") != _dict(candidate_driver.get("official_field_identity")).get("field_id") \
                or not _same_boundary(driver.get("boundary"), candidate_driver.get("boundary")):
            findings.append("v4_discovery_binding_cost_driver_identity_mismatch")
        manifest_repetitions = _dict_by_period(driver.get("repetitions"))
        candidate_repetitions = _dict_by_period(candidate_driver.get("cutoff_before_repetitions"))
        if set(manifest_repetitions) != set(candidate_repetitions):
            findings.append("v4_discovery_binding_cost_driver_repetitions_mismatch")
        else:
            for period, screen_repetition in manifest_repetitions.items():
                candidate_repetition = candidate_repetitions[period]
                raw_evidence = _dict(candidate_repetition.get("raw_observation")).get("evidence")
                if not _candidate_repetition_matches_h2(
                    candidate_repetition, screen_repetition, raw_evidence,
                ):
                    findings.append("v4_discovery_binding_cost_driver_repetition_citation_mismatch:" + period)
    findings.extend(_validate_h1_h2_pre_outcome_source_binding(
        candidate,
        source_map=_h1_h2_static_source_map(stage0_package, action_screen_extension),
    ))
    return findings, bool(findings)


def _dict_by_period(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    return {
        str(item.get("period_end")): item
        for item in value
        if isinstance(item, dict) and _text(item.get("period_end"))
    }


def _v4_raw_field_values(
    raw_fields: Any,
    *,
    expected_fields: tuple[str, ...],
    issuer_id: str,
    perimeter_id: str,
    unit: str | None,
    period_end: str,
    cutoff: datetime | None,
    prefix: str,
    available_before: datetime | None = None,
) -> tuple[dict[str, float], list[str], bool]:
    """Validate source-bearing V4 annual-report inputs and return values.

    Each D3/D4 component is independently source-bearing.  This makes the
    historical scaled-MAD inputs as auditable as the later peer outcome: no
    naked D3/D4 scalar, unofficial relay, issuer replacement, or changed cash
    formula can enter the candidate merely because it has a plausible number.
    """
    findings: list[str] = []
    values: dict[str, float] = {}
    valid = True
    if not isinstance(raw_fields, dict) or set(raw_fields) != set(expected_fields):
        return [prefix + "_field_set_invalid"], values, False
    for field_name in expected_fields:
        item_prefix = f"{prefix}.{field_name}"
        field = raw_fields.get(field_name)
        if not isinstance(field, dict) or not all(
            _text(field.get(key))
            for key in ("source_id", "source_type", "issuer_id", "perimeter_id", "published_at", "field_ref")
        ):
            findings.append(item_prefix + "_identity_invalid")
            valid = False
            continue
        value = field.get("value")
        if not _finite_number(value):
            findings.append(item_prefix + "_value_invalid")
            valid = False
        else:
            values[field_name] = float(value)
        if field.get("unit") != unit:
            findings.append(item_prefix + "_unit_mismatch")
            valid = False
        if field.get("source_type") != V4_OFFICIAL_AUDITED_ANNUAL_REPORT:
            findings.append(item_prefix + "_source_type_not_official_audited_annual_report")
            valid = False
        if field.get("issuer_id") != issuer_id or field.get("perimeter_id") != perimeter_id:
            findings.append(item_prefix + "_issuer_or_perimeter_mismatch")
            valid = False
        if field.get("period_end") != period_end:
            findings.append(item_prefix + "_period_end_mismatch")
            valid = False
        published_at = _date_or_time(field.get("published_at"))
        if published_at is None or cutoff is None or published_at > cutoff:
            findings.append(item_prefix + "_not_cutoff_before")
            valid = False
        if available_before is not None and (published_at is None or published_at >= available_before):
            findings.append(item_prefix + "_not_disclosed_before_action")
            valid = False
    return values, findings, valid


def _v4_raw_observations(
    observations: Any,
    *,
    cutoff: datetime | None,
    boundary: dict[str, Any] | None,
    issuer_id: str,
    d3_formula_id: str,
    d4_formula_id: str,
    prefix: str,
    before_action_at: datetime | None = None,
    minimum_periods: int,
) -> tuple[list[str], dict[str, dict[str, Any]], bool]:
    """Recompute annual D3/D4 observations from official raw fields.

    The returned mapping is intentionally the only input into V4's scaled-MAD
    step.  This prevents an analyst from converting D3 into D4, smoothing a
    selected set of observations, or importing a post-action value into the
    baseline volatility calculation.
    """
    findings: list[str] = []
    normalized: dict[str, dict[str, Any]] = {}
    valid = True
    expected_unit = boundary.get("unit") if isinstance(boundary, dict) else None
    expected_perimeter = boundary.get("perimeter_id") if isinstance(boundary, dict) else None
    if not isinstance(observations, list) or len(observations) < minimum_periods:
        return [prefix + "_not_recurrently_observable"], normalized, False
    for index, observation in enumerate(observations):
        item_prefix = f"{prefix}[{index}]"
        required_text = ("period_end",)
        allowed_fields = {
            "period_end", "reporting_frequency", "d3_formula_id", "d4_formula_id",
            "d3_raw_fields", "d4_raw_fields",
        }
        if not isinstance(observation, dict) or set(observation) != allowed_fields or not all(
            _text(observation.get(field)) for field in required_text
        ):
            findings.append(item_prefix + "_identity_invalid")
            valid = False
            continue
        if observation.get("reporting_frequency") != "ANNUAL":
            findings.append(item_prefix + "_not_annual")
            valid = False
        if observation.get("d3_formula_id") != d3_formula_id \
                or observation.get("d4_formula_id") != d4_formula_id:
            findings.append(item_prefix + "_frozen_d3_d4_formula_identity_mismatch")
            valid = False
        period_end = _date_or_time(observation.get("period_end"))
        if period_end is None or cutoff is None or period_end > cutoff:
            findings.append(item_prefix + "_not_cutoff_before")
            valid = False
        if before_action_at is not None and (period_end is None or period_end >= before_action_at):
            findings.append(item_prefix + "_not_pre_action")
            valid = False
        period_key = str(observation.get("period_end"))
        if period_key in normalized:
            findings.append(item_prefix + "_duplicate_period")
            valid = False
        else:
            d3_values, d3_findings, d3_valid = _v4_raw_field_values(
                observation.get("d3_raw_fields"),
                expected_fields=V4_D3_RAW_FIELDS,
                issuer_id=issuer_id,
                perimeter_id=str(expected_perimeter or ""),
                unit=expected_unit,
                period_end=period_key,
                cutoff=cutoff,
                prefix=item_prefix + ".d3_raw_fields",
                available_before=before_action_at,
            )
            d4_values, d4_findings, d4_valid = _v4_raw_field_values(
                observation.get("d4_raw_fields"),
                expected_fields=V4_D4_RAW_FIELDS,
                issuer_id=issuer_id,
                perimeter_id=str(expected_perimeter or ""),
                unit=expected_unit,
                period_end=period_key,
                cutoff=cutoff,
                prefix=item_prefix + ".d4_raw_fields",
                available_before=before_action_at,
            )
            findings.extend(d3_findings)
            findings.extend(d4_findings)
            if not d3_valid or not d4_valid:
                valid = False
                continue
            d3_value = (
                d3_values["operating_revenue_rmb"]
                - d3_values["operating_cost_rmb"]
                - d3_values["taxes_and_surcharges_rmb"]
                - d3_values["selling_expense_rmb"]
                - d3_values["administrative_expense_rmb"]
            )
            opening_cash_working_capital = (
                d4_values["opening_accounts_receivable_rmb"]
                + d4_values["opening_prepayments_rmb"]
                + d4_values["opening_inventory_rmb"]
                - d4_values["opening_accounts_payable_rmb"]
                - d4_values["opening_customer_advances_rmb"]
            )
            ending_cash_working_capital = (
                d4_values["ending_accounts_receivable_rmb"]
                + d4_values["ending_prepayments_rmb"]
                + d4_values["ending_inventory_rmb"]
                - d4_values["ending_accounts_payable_rmb"]
                - d4_values["ending_customer_advances_rmb"]
            )
            d4_value = (
                d4_values["operating_cash_flow_rmb"]
                - d4_values["cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb"]
                - max(opening_cash_working_capital - ending_cash_working_capital, 0.0)
            )
            normalized[period_key] = {
                "d3_value": d3_value,
                "d4_value": d4_value,
                "reference_revenue": d3_values["operating_revenue_rmb"],
            }
    if len(normalized) < minimum_periods:
        findings.append(prefix + "_periods_not_recurrent")
        valid = False
    else:
        ordered_periods = sorted(
            (_date_or_time(period) for period in normalized),
            key=lambda value: value or datetime.min.replace(tzinfo=timezone.utc),
        )
        if any(period is None for period in ordered_periods) or any(
            later.year != earlier.year + 1
            or (later.month, later.day) != (earlier.month, earlier.day)
            for earlier, later in zip(ordered_periods, ordered_periods[1:])
            if earlier is not None and later is not None
        ):
            findings.append(prefix + "_annual_periods_not_continuous")
            valid = False
    return findings, normalized, valid


def _scaled_mad(values: list[float]) -> tuple[float, float, float]:
    center = float(median(values))
    raw_mad = float(median([abs(value - center) for value in values]))
    return center, raw_mad, V4_SCALED_MAD_SCALE * raw_mad


def _v4_peer_relative_preaction_calibration(
    *, target_observations: dict[str, dict[str, Any]],
    peer_observations: list[dict[str, dict[str, Any]]],
    stage: str,
    reference_period_end: str | None,
) -> tuple[list[str], dict[str, Any] | None]:
    """Rebuild the action-time peer-noise band for one D3/D4 relative test.

    A target-only MAD says nothing about how much a fixed peer panel normally
    moves around the target.  The V4 relative test therefore has to clear both
    the target's own material step *and* the pre-action dispersion of the same
    target-minus-peer-median statistic used at settlement.  This is a
    calibration guard, not a significance test or a probability estimate.
    """
    findings: list[str] = []
    if stage not in {"D3_UNIT_ECONOMICS", "D4_WORKING_CAPITAL_AND_CASH"}:
        return ["v4_peer_relative_calibration_stage_invalid"], None
    if not reference_period_end or reference_period_end not in target_observations:
        return ["v4_peer_relative_calibration_reference_missing"], None
    if not peer_observations:
        return ["v4_peer_relative_calibration_peers_missing"], None

    common_periods = set(target_observations)
    for history in peer_observations:
        common_periods.intersection_update(history)
    ordered_periods = sorted(common_periods)
    if reference_period_end not in common_periods or len(ordered_periods) < 3:
        return ["v4_peer_relative_calibration_common_preaction_periods_insufficient"], None

    value_key = "d3_value" if stage == "D3_UNIT_ECONOMICS" else "d4_value"

    def margin(history: dict[str, dict[str, Any]], period_end: str) -> float | None:
        item = history.get(period_end)
        if not isinstance(item, dict):
            return None
        value = item.get(value_key)
        revenue = item.get("reference_revenue")
        if not _finite_number(value) or not _finite_number(revenue) or float(revenue) <= 0:
            return None
        return float(value) / float(revenue)

    target_reference = margin(target_observations, reference_period_end)
    if target_reference is None:
        return ["v4_peer_relative_calibration_target_reference_margin_invalid"], None
    peer_references = [margin(history, reference_period_end) for history in peer_observations]
    if any(value is None for value in peer_references):
        return ["v4_peer_relative_calibration_peer_reference_margin_invalid"], None

    relative_deltas: list[float] = []
    for period_end in ordered_periods:
        target_margin = margin(target_observations, period_end)
        peer_margins = [margin(history, period_end) for history in peer_observations]
        if target_margin is None or any(value is None for value in peer_margins):
            findings.append("v4_peer_relative_calibration_margin_invalid:" + period_end)
            continue
        peer_deltas = [
            float(current) - float(reference)
            for current, reference in zip(peer_margins, peer_references)
        ]
        relative_deltas.append((target_margin - target_reference) - float(median(peer_deltas)))
    if len(relative_deltas) != len(ordered_periods):
        return findings + ["v4_peer_relative_calibration_period_derivation_incomplete"], None
    center, raw_mad, scaled_step = _scaled_mad(relative_deltas)
    return findings, {
        "common_preaction_period_ends": ordered_periods,
        "relative_delta_median": center,
        "relative_delta_median_absolute_deviation": raw_mad,
        "peer_preaction_relative_scaled_mad": scaled_step,
    }


def _close_number(left: Any, right: float) -> bool:
    return _finite_number(left) and math.isclose(float(left), right, rel_tol=1e-9, abs_tol=1e-9)


def _validate_v4_materiality_anchor(
    anchor: Any,
    *,
    stage: str,
    predicate_stages: dict[str, str],
    target_observations: dict[str, dict[str, Any]],
    peer_observations: list[dict[str, dict[str, Any]]],
    reference_period_end: str | None,
    boundary: dict[str, Any] | None,
    prefix: str,
) -> tuple[list[str], float | None, str | None]:
    """Validate one non-substitutable V4 D3 or D4 materiality anchor."""
    findings: list[str] = []
    if not isinstance(anchor, dict):
        return [prefix + "_missing"], None, None
    if anchor.get("stage") != stage or not all(
        _text(anchor.get(field)) for field in ("anchor_id", "anchor_statement", "predicate_id")
    ):
        findings.append(prefix + "_identity_invalid")
    if predicate_stages.get(anchor.get("predicate_id")) != stage:
        findings.append(prefix + "_predicate_mismatch")
    source_ids = anchor.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids or not all(_text(item) for item in source_ids):
        findings.append(prefix + "_sources_invalid")
    if anchor.get("frozen_target_reference_period_end") != reference_period_end:
        findings.append(prefix + "_reference_period_mismatch")
    reference = target_observations.get(str(reference_period_end)) if reference_period_end else None
    if reference is None:
        findings.append(prefix + "_reference_period_not_in_target_history")
        return findings, None, anchor.get("anchor_id") if _text(anchor.get("anchor_id")) else None

    expected_clock = "D3" if stage == "D3_UNIT_ECONOMICS" else "D4"
    value_key = "d3_value" if expected_clock == "D3" else "d4_value"
    baseline = float(reference[value_key])
    reference_revenue = float(reference["reference_revenue"])
    if not _close_number(anchor.get("baseline_value"), baseline):
        findings.append(prefix + "_baseline_not_frozen_target_reference_value")
    calculation = anchor.get("calculation")
    if not isinstance(calculation, dict):
        findings.append(prefix + "_calculation_missing")
        return findings, None, anchor.get("anchor_id") if _text(anchor.get("anchor_id")) else None
    if calculation.get("method") != V4_SCALED_MAD_METHOD \
            or not _close_number(calculation.get("scale"), V4_SCALED_MAD_SCALE):
        findings.append(prefix + "_scaled_mad_method_invalid")
    if calculation.get("input_clock") != expected_clock:
        findings.append(prefix + "_input_clock_not_independent")
    if calculation.get("conversion_mapping_prohibited") is not True:
        findings.append(prefix + "_conversion_mapping_not_prohibited")
    if any(key in calculation for key in ("d3_to_d4_conversion_mapping", "cash_conversion_mapping")):
        findings.append(prefix + "_conversion_mapping_present")
    values = [float(item[value_key]) for item in target_observations.values()]
    derived_median, derived_mad, derived_step = _scaled_mad(values)
    if derived_step <= 0:
        findings.append(prefix + "_absolute_step_not_positive")
    for key, expected in (
        ("median", derived_median),
        ("median_absolute_deviation", derived_mad),
        ("absolute_step", derived_step),
    ):
        if not _close_number(calculation.get(key), expected):
            findings.append(prefix + "_" + key + "_not_exactly_recomputed")

    expected_unit = boundary.get("unit") if isinstance(boundary, dict) else None
    expected_thresholds = {
        "primary_threshold": ("GREATER_THAN_OR_EQUAL", baseline + derived_step),
        "rival_threshold": ("LESS_THAN_OR_EQUAL", baseline - derived_step),
    }
    for name, (operator, value) in expected_thresholds.items():
        threshold = anchor.get(name)
        if not isinstance(threshold, dict) or threshold.get("operator") != operator \
                or threshold.get("unit") != expected_unit or not _close_number(threshold.get("value"), value):
            findings.append(prefix + "_" + name + "_not_baseline_plus_or_minus_exact_step")
    relative_peer_threshold = anchor.get("relative_peer_threshold")
    if reference_revenue <= 0:
        findings.append(prefix + "_reference_revenue_not_positive")
    target_ratio_step = derived_step / reference_revenue if reference_revenue > 0 else None
    calibration_findings, calibration = _v4_peer_relative_preaction_calibration(
        target_observations=target_observations,
        peer_observations=peer_observations,
        stage=stage,
        reference_period_end=reference_period_end,
    )
    findings.extend(calibration_findings)
    peer_noise_step = (
        calibration.get("peer_preaction_relative_scaled_mad")
        if isinstance(calibration, dict) else None
    )
    expected_ratio_step = (
        max(target_ratio_step, float(peer_noise_step))
        if target_ratio_step is not None and _finite_number(peer_noise_step) else None
    )
    if not isinstance(relative_peer_threshold, dict) \
            or relative_peer_threshold.get("formula") != V4_RELATIVE_STEP_FORMULA \
            or relative_peer_threshold.get("target_reference_period_end") != reference_period_end \
            or relative_peer_threshold.get("unit") != V4_PEER_RELATIVE_UNIT \
            or not _close_number(relative_peer_threshold.get("target_reference_revenue"), reference_revenue) \
            or target_ratio_step is None \
            or not _close_number(relative_peer_threshold.get("target_absolute_ratio_step"), target_ratio_step) \
            or not isinstance(calibration, dict) \
            or relative_peer_threshold.get("common_preaction_period_ends") != calibration.get("common_preaction_period_ends") \
            or not _close_number(
                relative_peer_threshold.get("relative_delta_median"),
                float(calibration.get("relative_delta_median", float("nan"))),
            ) \
            or not _close_number(
                relative_peer_threshold.get("relative_delta_median_absolute_deviation"),
                float(calibration.get("relative_delta_median_absolute_deviation", float("nan"))),
            ) \
            or not _close_number(
                relative_peer_threshold.get("peer_preaction_relative_scaled_mad"),
                float(calibration.get("peer_preaction_relative_scaled_mad", float("nan"))),
            ) \
            or expected_ratio_step is None \
            or not _close_number(relative_peer_threshold.get("relative_ratio_step"), expected_ratio_step):
        findings.append(prefix + "_relative_peer_threshold_not_exactly_derived")
    return findings, derived_step, anchor.get("anchor_id") if _text(anchor.get("anchor_id")) else None


def _validate_v4_peer_panel_and_materiality(
    candidate: dict[str, Any], *, prediction_stages: dict[str, str], primary_hypothesis_id: str | None,
) -> tuple[list[str], bool]:
    """Validate V4's fixed cross-company comparison and mechanical anchors.

    This is an admission gate, not a causal model: an actual action exposure
    being at least one target D3 volatility step says only that the episode is
    economically material enough to train on.  It never converts a D3 result
    into D4 owner cash or declares the action profitable.
    """
    if not _is_v4_admission_contract(candidate):
        return [], False

    findings: list[str] = []
    force_no_primary = False
    cutoff = _time(candidate.get("cutoff_at"))
    contract = candidate.get("selection_admission_contract")
    if not isinstance(contract, dict):  # guarded above, retained for type narrowing
        return ["v4_selection_admission_contract_invalid"], True
    topology = _v4_mechanism_topology(candidate)
    if topology not in V4_MECHANISM_TOPOLOGIES:
        findings.append("v4_mechanism_topology_invalid")
        force_no_primary = True
    customer_requirement = contract.get("customer_absorption_requirement")
    expected_customer_required = topology == V4_CUSTOMER_RESPONSE_CHAIN
    expected_customer_trigger = (
        CUSTOMER_ABSORPTION_REQUIRED_TRIGGER if expected_customer_required
        else CUSTOMER_ABSORPTION_NOT_REQUIRED_TRIGGER
    )
    if not isinstance(customer_requirement, dict) \
            or customer_requirement.get("required") is not expected_customer_required \
            or customer_requirement.get("trigger") != expected_customer_trigger:
        findings.append("v4_customer_absorption_requirement_does_not_match_mechanism_topology")
        force_no_primary = True
    cash_requirement = contract.get("cash_transmission_requirement")
    if not isinstance(cash_requirement, dict) or cash_requirement.get("required") is not True \
            or cash_requirement.get("trigger") != CASH_TRANSMISSION_REQUIRED_TRIGGER:
        findings.append("v4_cash_transmission_requirement_must_remain_required")
        force_no_primary = True

    cash_observability = candidate.get("cash_transmission_observability")
    common_boundary = (
        cash_observability.get("common_boundary") if isinstance(cash_observability, dict) else None
    )
    if not isinstance(common_boundary, dict):
        return findings + ["v4_common_boundary_missing"], True
    if common_boundary.get("perimeter_id") != V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER:
        findings.append("v4_target_boundary_not_listed_consolidated_issuer")
        force_no_primary = True
    transmission_legs = cash_observability.get("transmission_legs") if isinstance(cash_observability, dict) else None
    d3_formula_id = ""
    if isinstance(transmission_legs, list):
        d3_leg = next(
            (item for item in transmission_legs if isinstance(item, dict) and item.get("leg_id") == "OPERATING_CONTRIBUTION"),
            None,
        )
        d3_identity = d3_leg.get("official_field_identity") if isinstance(d3_leg, dict) else None
        d3_formula_id = str(d3_identity.get("field_id") or "") if isinstance(d3_identity, dict) else ""
    d4_formula = cash_observability.get("d4_formula") if isinstance(cash_observability, dict) else None
    d4_formula_id = str(d4_formula.get("formula_id") or "") if isinstance(d4_formula, dict) else ""
    if not d3_formula_id or not d4_formula_id:
        findings.append("v4_frozen_d3_d4_formula_identity_missing")
        force_no_primary = True

    panel = candidate.get("peer_panel_observability")
    if not isinstance(panel, dict):
        return findings + ["v4_peer_panel_observability_required"], True
    if panel.get("gate_version") != PEER_PANEL_ADMISSION_VERSION:
        findings.append("v4_peer_panel_gate_version_invalid")
        force_no_primary = True
    if panel.get("primary_hypothesis_id") != primary_hypothesis_id:
        findings.append("v4_peer_panel_primary_hypothesis_mismatch")
        force_no_primary = True
    if panel.get("failure_disposition") != PEER_PANEL_NO_PRIMARY:
        findings.append("v4_peer_panel_failure_disposition_invalid")
        force_no_primary = True
    if not _text(panel.get("panel_contract_id")):
        findings.append("v4_peer_panel_contract_id_missing")
        force_no_primary = True
    if panel.get("same_industry_requirement") != "TARGET_AND_ALL_PEERS_MATCH_CANDIDATE_INDUSTRY":
        findings.append("v4_peer_panel_same_industry_requirement_invalid")
        force_no_primary = True
    market_context = panel.get("common_market_context")
    if not isinstance(market_context, dict):
        findings.append("v4_peer_panel_common_market_context_missing")
        force_no_primary = True

    target = panel.get("target")
    target_observations: dict[str, dict[str, Any]] = {}
    target_issuer_id = ""
    target_control_group_id = ""
    action_effective_at: datetime | None = None
    anchors = cash_observability.get("materiality_anchors") if isinstance(cash_observability, dict) else None
    action = anchors.get("action_exposure") if isinstance(anchors, dict) else None
    if isinstance(action, dict):
        action_effective_at = _date_or_time(action.get("implemented_or_incurred_at"))
    if not isinstance(target, dict):
        findings.append("v4_peer_panel_target_missing")
        force_no_primary = True
    else:
        if target.get("company_id") != candidate.get("company_id") \
                or target.get("responsibility_unit_id") != candidate.get("responsibility_unit_id") \
                or not _text(target.get("issuer_id")) \
                or not _text(target.get("control_group_id")):
            findings.append("v4_peer_panel_target_identity_mismatch")
            force_no_primary = True
        target_issuer_id = str(target.get("issuer_id") or "")
        target_control_group_id = str(target.get("control_group_id") or "")
        target_boundary = target.get("boundary")
        if not _same_boundary(target_boundary, common_boundary):
            findings.append("v4_peer_panel_target_common_boundary_mismatch")
            force_no_primary = True
        target_control_findings, target_control_valid = _valid_v4_evidence_list(
            target.get("control_group_evidence"), cutoff,
            issuer_id=target_issuer_id,
            perimeter_id=str(common_boundary.get("perimeter_id") or ""),
            prefix="v4_peer_panel_target_control_group_evidence",
            control_group_id=target_control_group_id,
            available_before=action_effective_at,
        )
        findings.extend(target_control_findings)
        if not target_control_valid:
            force_no_primary = True
        target_market_findings, target_market_valid = _validate_v4_market_exposure(
            target, context=market_context, cutoff=cutoff, action_at=action_effective_at,
            issuer_id=target_issuer_id, boundary=common_boundary,
            prefix="v4_peer_panel_target",
        )
        findings.extend(target_market_findings)
        if not target_market_valid:
            force_no_primary = True
        target_findings, target_observations, target_valid = _v4_raw_observations(
            target.get("annual_d3_d4_raw_observations"),
            cutoff=cutoff,
            boundary=common_boundary,
            issuer_id=target_issuer_id,
            d3_formula_id=d3_formula_id,
            d4_formula_id=d4_formula_id,
            prefix="v4_target_d3_d4_history",
            before_action_at=action_effective_at,
            minimum_periods=5,
        )
        findings.extend(target_findings)
        if not target_valid:
            force_no_primary = True
        comparability_findings, comparability_valid = _validate_v4_comparability_register(
            target.get("comparability_register"), period_ends=set(target_observations), cutoff=cutoff,
            action_at=action_effective_at, issuer_id=target_issuer_id, boundary=common_boundary,
            prefix="v4_target_comparability",
        )
        findings.extend(comparability_findings)
        if not comparability_valid:
            force_no_primary = True

    frozen_panel = panel.get("frozen_panel")
    peers = panel.get("peers")
    peer_company_ids: list[str] = []
    peer_issuer_ids: list[str] = []
    peer_control_group_ids: list[str] = []
    peer_observations: list[dict[str, dict[str, Any]]] = []
    if not isinstance(peers, list) or not 3 <= len(peers) <= 7:
        findings.append("v4_peer_panel_peer_count_must_be_three_to_seven")
        force_no_primary = True
    else:
        for index, peer in enumerate(peers):
            prefix = f"v4_peer_panel_peer[{index}]"
            if not isinstance(peer, dict) or not all(
                _text(peer.get(field))
                for field in ("company_id", "issuer_id", "control_group_id", "industry_id", "responsibility_unit_id")
            ):
                findings.append(prefix + "_identity_invalid")
                force_no_primary = True
                continue
            company_id = str(peer.get("company_id"))
            peer_company_ids.append(company_id)
            peer_issuer_id = str(peer.get("issuer_id") or "")
            peer_control_group_id = str(peer.get("control_group_id") or "")
            peer_issuer_ids.append(peer_issuer_id)
            peer_control_group_ids.append(peer_control_group_id)
            if peer.get("industry_id") != candidate.get("industry_id"):
                findings.append(prefix + "_industry_mismatch")
                force_no_primary = True
            peer_boundary = peer.get("boundary")
            if not isinstance(peer_boundary, dict) \
                    or peer_boundary.get("perimeter_id") != V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER \
                    or peer_boundary.get("unit") != common_boundary.get("unit"):
                findings.append(prefix + "_not_listed_consolidated_issuer_boundary")
                force_no_primary = True
            peer_control_findings, peer_control_valid = _valid_v4_evidence_list(
                peer.get("control_group_evidence"), cutoff,
                issuer_id=peer_issuer_id,
                perimeter_id=str(peer_boundary.get("perimeter_id") if isinstance(peer_boundary, dict) else ""),
                prefix=prefix + "_control_group_evidence",
                control_group_id=peer_control_group_id,
                available_before=action_effective_at,
            )
            findings.extend(peer_control_findings)
            if not peer_control_valid:
                force_no_primary = True
            peer_market_findings, peer_market_valid = _validate_v4_market_exposure(
                peer, context=market_context, cutoff=cutoff, action_at=action_effective_at,
                issuer_id=peer_issuer_id,
                boundary=peer_boundary if isinstance(peer_boundary, dict) else None,
                prefix=prefix,
            )
            findings.extend(peer_market_findings)
            if not peer_market_valid:
                force_no_primary = True
            peer_findings, peer_history, peer_valid = _v4_raw_observations(
                peer.get("annual_d3_d4_raw_observations"),
                cutoff=cutoff,
                boundary=peer_boundary if isinstance(peer_boundary, dict) else None,
                issuer_id=peer_issuer_id,
                d3_formula_id=d3_formula_id,
                d4_formula_id=d4_formula_id,
                prefix=prefix + "_d3_d4_history",
                before_action_at=action_effective_at,
                minimum_periods=3,
            )
            findings.extend(peer_findings)
            if not peer_valid:
                force_no_primary = True
            comparability_findings, comparability_valid = _validate_v4_comparability_register(
                peer.get("comparability_register"), period_ends=set(peer_history), cutoff=cutoff,
                action_at=action_effective_at, issuer_id=peer_issuer_id,
                boundary=peer_boundary if isinstance(peer_boundary, dict) else None,
                prefix=prefix + "_comparability",
            )
            findings.extend(comparability_findings)
            if not comparability_valid:
                force_no_primary = True
            if peer_history:
                peer_observations.append(peer_history)
    if len(set(peer_company_ids)) != len(peer_company_ids) or candidate.get("company_id") in peer_company_ids:
        findings.append("v4_peer_panel_peer_identity_not_unique")
        force_no_primary = True
    if target_issuer_id in peer_issuer_ids or len(set(peer_issuer_ids)) != len(peer_issuer_ids):
        findings.append("v4_peer_panel_issuer_identity_not_unique")
        force_no_primary = True
    if not target_control_group_id or target_control_group_id in peer_control_group_ids \
            or len(set(peer_control_group_ids)) != len(peer_control_group_ids):
        findings.append("v4_peer_panel_control_group_not_independent")
        force_no_primary = True

    if not isinstance(frozen_panel, dict):
        findings.append("v4_peer_panel_freeze_missing")
        force_no_primary = True
    else:
        expected_order = [candidate.get("company_id"), *peer_company_ids]
        if frozen_panel.get("frozen_order") != expected_order:
            findings.append("v4_peer_panel_frozen_order_not_exact")
            force_no_primary = True
        if frozen_panel.get("no_replacement") is not True \
                or frozen_panel.get("replacement_policy") != "NO_REPLACEMENT":
            findings.append("v4_peer_panel_replacement_not_prohibited")
            force_no_primary = True
        universe = frozen_panel.get("universe")
        if not isinstance(universe, dict) or not all(
            _text(universe.get(field)) for field in ("universe_id", "industry_id", "as_of", "membership_rule")
        ) or universe.get("industry_id") != candidate.get("industry_id"):
            findings.append("v4_peer_panel_universe_invalid")
            force_no_primary = True
        else:
            as_of = _date_or_time(universe.get("as_of"))
            eligible = universe.get("eligible_company_ids")
            if as_of is None or cutoff is None or as_of > cutoff \
                    or action_effective_at is None or as_of > action_effective_at \
                    or not isinstance(eligible, list) or not all(_text(item) for item in eligible):
                findings.append("v4_peer_panel_universe_not_action_time")
                force_no_primary = True
            exclusions = frozen_panel.get("exclusions")
            if not isinstance(exclusions, list):
                findings.append("v4_peer_panel_exclusions_missing")
                force_no_primary = True
            else:
                excluded_ids: list[str] = []
                for index, exclusion in enumerate(exclusions):
                    if not isinstance(exclusion, dict) or not _text(exclusion.get("company_id")) \
                            or not _text(exclusion.get("reason")):
                        findings.append(f"v4_peer_panel_exclusions[{index}]_invalid")
                        force_no_primary = True
                        continue
                    excluded_ids.append(str(exclusion["company_id"]))
                if len(set(excluded_ids)) != len(excluded_ids) \
                        or set(expected_order).intersection(excluded_ids) \
                        or set(eligible or ()) != set(expected_order).union(excluded_ids):
                    findings.append("v4_peer_panel_universe_exclusion_not_exact")
                    force_no_primary = True

    relative_method = panel.get("relative_method")
    reference_period_end = None
    if not isinstance(relative_method, dict):
        findings.append("v4_peer_panel_relative_method_missing")
        force_no_primary = True
    else:
        reference_period_end = relative_method.get("reference_period_end")
        if relative_method.get("method") != V4_PEER_RELATIVE_METHOD \
                or relative_method.get("conjunction") != "D3_AND_D4" \
                or relative_method.get("unit") != V4_PEER_RELATIVE_UNIT \
                or str(reference_period_end) not in target_observations:
            findings.append("v4_peer_panel_relative_method_invalid")
            force_no_primary = True
        elif any(str(reference_period_end) not in history for history in peer_observations):
            findings.append("v4_peer_panel_reference_period_not_common_to_all_members")
            force_no_primary = True

    if not isinstance(anchors, dict) or set(anchors) != {
        "action_exposure", "D3_UNIT_ECONOMICS", "D4_WORKING_CAPITAL_AND_CASH",
    }:
        findings.append("v4_materiality_anchors_topology_invalid")
        return findings, True
    action = anchors["action_exposure"]
    action_exposure_amount: float | None = None
    if not isinstance(action, dict):
        findings.append("v4_action_exposure_missing")
        force_no_primary = True
    else:
        if action.get("action_state") != V4_ACTION_IMPLEMENTED:
            findings.append("v4_action_not_implemented_or_irrevocably_incurred")
            force_no_primary = True
        if action.get("economic_action_type") not in V4_ALLOWED_OPERATIONAL_ACTION_TYPES:
            findings.append("v4_action_type_not_supported_by_operating_cash_bridge")
            force_no_primary = True
        if not _text(action.get("action_id")) or not _text(action.get("action_statement")):
            findings.append("v4_action_identity_invalid")
            force_no_primary = True
        action_effective_at = _date_or_time(action.get("implemented_or_incurred_at"))
        if action_effective_at is None or cutoff is None or action_effective_at > cutoff:
            findings.append("v4_action_not_cutoff_before")
            force_no_primary = True
        if not _same_boundary(action.get("boundary"), common_boundary) \
                or action.get("boundary", {}).get("responsibility_unit_id") != candidate.get("responsibility_unit_id"):
            findings.append("v4_action_boundary_mismatch")
            force_no_primary = True
        scope_bridge = action.get("issuer_scope_bridge")
        if not isinstance(scope_bridge, dict) \
                or scope_bridge.get("outcome_scope") != V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER \
                or scope_bridge.get("action_scope_relation") != "ISSUER_WIDE_OPERATING_DECISION" \
                or scope_bridge.get("issuer_level_mechanism_only") is not True:
            findings.append("v4_action_issuer_scope_bridge_invalid")
            force_no_primary = True
        else:
            bridge_findings, bridge_valid = _valid_v4_evidence_list(
                scope_bridge.get("evidence"), cutoff,
                issuer_id=target_issuer_id,
                perimeter_id=str(common_boundary.get("perimeter_id") or ""),
                prefix="v4_action_issuer_scope_bridge_evidence",
                boundary=common_boundary,
            )
            findings.extend(bridge_findings)
            if not bridge_valid:
                force_no_primary = True
        specificity = action.get("decision_specificity")
        if not isinstance(specificity, dict) \
                or specificity.get("decision_class") != "DISCRETIONARY_OPERATING_DECISION" \
                or specificity.get("incremental_to_maintenance_or_mandated_baseline") is not True:
            findings.append("v4_action_decision_specificity_invalid")
            force_no_primary = True
        else:
            specificity_findings, specificity_valid = _valid_v4_evidence_list(
                specificity.get("evidence"), cutoff,
                issuer_id=target_issuer_id,
                perimeter_id=str(common_boundary.get("perimeter_id") or ""),
                prefix="v4_action_decision_specificity_evidence",
                boundary=common_boundary,
            )
            findings.extend(specificity_findings)
            if not specificity_valid:
                force_no_primary = True
        if action.get("explicitly_immaterial") is not False:
            findings.append("v4_action_explicitly_immaterial")
            force_no_primary = True
        action_evidence_findings, action_evidence_valid = _valid_v4_evidence_list(
            action.get("implementation_evidence"), cutoff,
            issuer_id=target_issuer_id,
            perimeter_id=str(common_boundary.get("perimeter_id") or ""),
            prefix="v4_action_implementation_evidence",
            boundary=common_boundary,
        )
        findings.extend(action_evidence_findings)
        if not action_evidence_valid:
            force_no_primary = True
        prohibited = action.get("prohibited_substitutes")
        expected_prohibited = {
            "FORECAST", "DESIGN_CAPACITY", "CIP", "LOANS", "POST_CUTOFF",
        }
        if not isinstance(prohibited, list) or set(prohibited) != expected_prohibited:
            findings.append("v4_action_prohibited_substitutes_invalid")
            force_no_primary = True
        exposure = action.get("exposure")
        if not isinstance(exposure, dict) or exposure.get("kind") not in V4_ACTION_EXPOSURE_KINDS \
                or exposure.get("unit") != common_boundary.get("unit") \
                or not _finite_number(exposure.get("amount")) or float(exposure.get("amount")) <= 0:
            findings.append("v4_action_exposure_invalid")
            force_no_primary = True
        else:
            action_exposure_amount = float(exposure["amount"])
            exposure_findings, exposure_valid = _valid_v4_evidence_list(
                exposure.get("evidence"), cutoff,
                issuer_id=target_issuer_id,
                perimeter_id=str(common_boundary.get("perimeter_id") or ""),
                prefix="v4_action_exposure_evidence",
                boundary=common_boundary,
            )
            findings.extend(exposure_findings)
            if not exposure_valid:
                force_no_primary = True
            if exposure.get("kind") == "ACTUAL_CASH_OR_RECOGNIZED_ASSET":
                if exposure.get("actual_basis") not in {"ACTUAL_CASH_PAID", "RECOGNIZED_ASSET"}:
                    findings.append("v4_action_exposure_not_actual_cash_or_recognized_asset")
                    force_no_primary = True
            else:
                price_delta = exposure.get("implemented_net_price_delta")
                preaction_units = exposure.get("preaction_actual_units")
                if not _finite_number(price_delta) or not _finite_number(preaction_units) \
                        or not _close_number(exposure.get("amount"), float(price_delta) * float(preaction_units)) \
                        or not _text(exposure.get("price_delta_field_ref")) \
                        or not _text(exposure.get("preaction_actual_units_field_ref")):
                    findings.append("v4_action_exposure_price_delta_times_actual_units_invalid")
                    force_no_primary = True

    cash_bridge_findings, cash_bridge_valid = _validate_v4_cash_bridge_coverage(
        cash_observability.get("d4_cash_bridge_coverage") if isinstance(cash_observability, dict) else None,
        target_observations=target_observations, cutoff=cutoff, action_at=action_effective_at,
        issuer_id=target_issuer_id, boundary=common_boundary,
        action_type=action.get("economic_action_type") if isinstance(action, dict) else None,
    )
    findings.extend(cash_bridge_findings)
    if not cash_bridge_valid:
        force_no_primary = True

    d3_findings, d3_step, d3_anchor_id = _validate_v4_materiality_anchor(
        anchors["D3_UNIT_ECONOMICS"],
        stage="D3_UNIT_ECONOMICS",
        predicate_stages=prediction_stages,
        target_observations=target_observations,
        peer_observations=peer_observations,
        reference_period_end=str(reference_period_end) if reference_period_end is not None else None,
        boundary=common_boundary,
        prefix="v4_d3_materiality",
    )
    d4_findings, _, d4_anchor_id = _validate_v4_materiality_anchor(
        anchors["D4_WORKING_CAPITAL_AND_CASH"],
        stage="D4_WORKING_CAPITAL_AND_CASH",
        predicate_stages=prediction_stages,
        target_observations=target_observations,
        peer_observations=peer_observations,
        reference_period_end=str(reference_period_end) if reference_period_end is not None else None,
        boundary=common_boundary,
        prefix="v4_d4_materiality",
    )
    findings.extend(d3_findings)
    findings.extend(d4_findings)
    if d3_findings or d4_findings or d3_anchor_id == d4_anchor_id:
        if d3_anchor_id == d4_anchor_id:
            findings.append("v4_d3_d4_materiality_anchors_not_independent")
        force_no_primary = True
    if action_exposure_amount is not None and d3_step is not None and action_exposure_amount < d3_step:
        findings.append("v4_action_exposure_below_d3_materiality_step")
        force_no_primary = True

    return findings, force_no_primary


def validate_selection_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(candidate, dict):
        return {
            "schema_version": "judgment-selection-candidate-validation.v1",
            "state": "INVALID",
            "admission_state": "NOT_ADMITTED",
            "findings": ["candidate_not_object"],
        }
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in (
        "case_id", "experiment_id", "company_id", "company_cluster_id",
        "responsibility_unit_id", "industry_id", "freeze_id", "decisive_question",
    ):
        if not _text(candidate.get(field)):
            findings.append(field + "_missing")
    if not str(candidate.get("case_id") or "").startswith("SELECTIONCASE:"):
        findings.append("case_id_invalid")
    if not str(candidate.get("freeze_id") or "").startswith("JFREEZE:"):
        findings.append("freeze_id_invalid")
    if _time(candidate.get("cutoff_at")) is None:
        findings.append("cutoff_at_invalid")
    if _time(candidate.get("freeze_recorded_at")) is None:
        findings.append("freeze_recorded_at_invalid")
    if candidate.get("training_role") != "HISTORICAL_SELECTION_CANDIDATE":
        findings.append("training_role_invalid")
    if candidate.get("program_lane") != "HISTORICAL_TRAINING":
        findings.append("program_lane_invalid")
    if candidate.get("provenance_role") != "HISTORICAL_SELF_REPLAY":
        findings.append("provenance_role_invalid")
    if candidate.get("selection_status") != "SELECTION_ADMITTED":
        findings.append("selection_status_invalid")
    if candidate.get("probability_mode") != "NO_PROBABILITY":
        findings.append("probability_mode_invalid")
    if candidate.get("selection_effective_gate") != "PENDING_INDEPENDENT_PRE_OUTCOME_REVIEW":
        findings.append("selection_effective_gate_invalid")
    if candidate.get("learning_eligibility") != "NONE_PENDING_REVIEW":
        findings.append("learning_eligibility_must_remain_pending")
    if candidate.get("registration_status") != "NOT_REGISTERED":
        findings.append("registration_status_must_remain_unregistered")
    if candidate.get("candidate_verdict") != "PROPOSED_PRIMARY_PENDING_INDEPENDENT_REVIEW":
        findings.append("candidate_verdict_invalid")

    facts = candidate.get("cutoff_before_facts")
    if not isinstance(facts, list) or not facts:
        findings.append("cutoff_before_facts_missing")
    else:
        for index, fact in enumerate(facts):
            if not isinstance(fact, dict):
                findings.append(f"cutoff_before_facts[{index}]_not_object")
                continue
            if not all(_text(fact.get(field)) for field in ("fact_id", "statement", "selection_classification")):
                findings.append(f"cutoff_before_facts[{index}]_identity_invalid")
            source_ids = fact.get("source_ids")
            if not isinstance(source_ids, list) or not source_ids or not all(_text(item) for item in source_ids):
                findings.append(f"cutoff_before_facts[{index}]_source_ids_invalid")

    pair = candidate.get("rival_hypothesis_pair")
    if not isinstance(pair, dict):
        findings.append("rival_hypothesis_pair_missing")
    else:
        primary = pair.get("primary_hypothesis")
        rival = pair.get("strongest_rival")
        if not isinstance(primary, dict) or not all(
            _text(primary.get(field)) for field in ("hypothesis_id", "name", "mechanism")
        ) or primary.get("role") != "SELECTED_PRIMARY":
            findings.append("primary_hypothesis_invalid")
        if not isinstance(rival, dict) or not all(
            _text(rival.get(field)) for field in ("hypothesis_id", "name", "mechanism")
        ) or rival.get("role") != "STRONGEST_RIVAL":
            findings.append("strongest_rival_invalid")
        if isinstance(primary, dict) and isinstance(rival, dict) and primary.get("hypothesis_id") == rival.get("hypothesis_id"):
            findings.append("rival_hypothesis_ids_must_differ")
        basis = pair.get("selection_basis")
        if not isinstance(basis, dict) or not all(
            _text(basis.get(field)) for field in ("directional_preference", "why_not_common", "why_rival_remains_live")
        ):
            findings.append("selection_basis_invalid")
        elif isinstance(primary, dict) and basis.get("directional_preference") != primary.get("hypothesis_id"):
            findings.append("selection_basis_primary_mismatch")

    baseline = candidate.get("fair_simple_baseline")
    if not isinstance(baseline, dict) or not all(
        _text(baseline.get(field)) for field in ("baseline_id", "rule")
    ) or baseline.get("selection_use") != "FAIR_COMPARISON":
        findings.append("fair_simple_baseline_invalid")
    elif not isinstance(baseline.get("formulae"), dict) or not baseline["formulae"]:
        findings.append("fair_simple_baseline_formulae_missing")

    predictions = candidate.get("frozen_prediction_order")
    stages: list[str] = []
    prediction_stages: dict[str, str] = {}
    if not isinstance(predictions, list) or not predictions:
        findings.append("frozen_prediction_order_missing")
    else:
        for index, prediction in enumerate(predictions):
            if not isinstance(prediction, dict):
                findings.append(f"frozen_prediction_order[{index}]_not_object")
                continue
            if not all(
                _text(prediction.get(field))
                for field in ("predicate_id", "stage", "primary_prediction", "rival_prediction", "baseline_prediction")
            ):
                findings.append(f"frozen_prediction_order[{index}]_invalid")
            predicate_id = str(prediction.get("predicate_id") or "")
            stage = str(prediction.get("stage") or "")
            stages.append(stage)
            if predicate_id:
                prediction_stages[predicate_id] = stage
        if tuple(stages) not in SELECTION_STAGE_ORDERS:
            findings.append("frozen_prediction_order_stage_topology_invalid")

    boundary = candidate.get("measurement_boundary")
    if not isinstance(boundary, dict) or any(not _text(boundary.get(clock)) for clock in ("D1", "D2", "D3", "D4", "D5")):
        findings.append("measurement_boundary_d1_d5_required")

    attestation = candidate.get("outcome_access_attestation")
    if not isinstance(attestation, dict):
        findings.append("outcome_access_attestation_missing")
    else:
        if attestation.get("state") != "PIT_OUTCOME_SEALED":
            findings.append("outcome_access_not_sealed")
        if attestation.get("metadata_leakage_detected") is not False:
            findings.append("outcome_metadata_leakage_not_false")
        if attestation.get("outcome_acquisition_authorized") is not False:
            findings.append("outcome_acquisition_must_remain_unauthorized")
        if not _text(attestation.get("attestation")):
            findings.append("outcome_access_attestation_text_missing")

    primary_hypothesis = pair.get("primary_hypothesis") if isinstance(pair, dict) else None
    primary_hypothesis_id = (
        primary_hypothesis.get("hypothesis_id") if isinstance(primary_hypothesis, dict) else None
    )
    customer_absorption_findings, customer_absorption_no_primary = _validate_customer_absorption_observability(
        candidate,
        prediction_stages=prediction_stages,
        primary_hypothesis_id=primary_hypothesis_id,
    )
    findings.extend(customer_absorption_findings)
    cost_driver_findings: list[str] = []
    cost_driver_no_primary = False
    if _v4_mechanism_topology(candidate) == V4_COST_RESTRUCTURING_CHAIN:
        cost_driver_findings, cost_driver_valid = _validate_v4_cost_driver_observability(
            candidate, prediction_stages=prediction_stages,
            primary_hypothesis_id=primary_hypothesis_id,
        )
        cost_driver_no_primary = not cost_driver_valid
        findings.extend(cost_driver_findings)
    cash_transmission_findings, cash_transmission_no_primary = _validate_cash_transmission_observability(
        candidate,
        prediction_stages=prediction_stages,
        primary_hypothesis_id=primary_hypothesis_id,
    )
    findings.extend(cash_transmission_findings)
    v4_findings, v4_no_primary = _validate_v4_peer_panel_and_materiality(
        candidate,
        prediction_stages=prediction_stages,
        primary_hypothesis_id=primary_hypothesis_id,
    )
    findings.extend(v4_findings)
    discovery_findings: list[str] = []
    discovery_no_primary = False
    if _is_v4_admission_contract(candidate):
        discovery_findings, discovery_no_primary = _validate_v4_discovery_binding(candidate)
        findings.extend(discovery_findings)

    return {
        "schema_version": "judgment-selection-candidate-validation.v1",
        "state": "INVALID" if findings else "REVIEWABLE",
        "admission_state": (
            "NO_PRIMARY" if customer_absorption_no_primary or cost_driver_no_primary or cash_transmission_no_primary or v4_no_primary
            or discovery_no_primary else
            "NOT_ADMITTED" if findings else "PENDING_INDEPENDENT_REVIEW"
        ),
        "findings": findings,
    }


def validate_selection_review(
    review: dict[str, Any], *, candidate: dict[str, Any],
    case_artifact_ref: str | Path | None = None,
    receipt_recorded_at: str | None = None,
) -> dict[str, Any]:
    findings: list[str] = []
    candidate_result = validate_selection_candidate(candidate)
    if candidate_result["state"] != "REVIEWABLE":
        findings.append("candidate_not_reviewable")
    if not isinstance(review, dict):
        return {
            "schema_version": "judgment-selection-review-validation.v1",
            "state": "INVALID",
            "admission_state": "NOT_ADMITTED",
            "findings": ["review_not_object"],
        }
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in ("receipt_id", "case_id", "reviewer_id", "selection_scope"):
        if not _text(review.get(field)):
            findings.append(field + "_missing")
    if review.get("case_id") != candidate.get("case_id"):
        findings.append("review_case_id_mismatch")
    reviewer_id = str(review.get("reviewer_id") or "")
    if "independent" not in reviewer_id.lower():
        findings.append("independent_reviewer_required")
    reviewed_at = _time(review.get("reviewed_at"))
    freeze_recorded_at = _time(candidate.get("freeze_recorded_at"))
    if reviewed_at is None:
        findings.append("reviewed_at_invalid")
    elif freeze_recorded_at is None or reviewed_at < freeze_recorded_at:
        findings.append("reviewed_before_candidate_freeze")
    receipt_at = _time(receipt_recorded_at) if receipt_recorded_at is not None else None
    if receipt_recorded_at is not None and receipt_at is None:
        findings.append("review_receipt_recorded_at_invalid")
    elif reviewed_at is not None and receipt_at is not None and reviewed_at > receipt_at:
        findings.append("reviewed_after_receipt_recorded_at")
    if review.get("verdict") != "SELECTION_ADMITTED_PRE_OUTCOME":
        findings.append("review_verdict_invalid")
    if review.get("outcome_body_access") != "UNREAD_AND_PROHIBITED":
        findings.append("outcome_body_access_not_sealed")
    if review.get("outcome_metadata_access") != "NONE":
        findings.append("outcome_metadata_access_not_none")

    reviewed_artifacts = review.get("reviewed_artifacts")
    if not isinstance(reviewed_artifacts, list) or not reviewed_artifacts or not all(_text(item) for item in reviewed_artifacts):
        findings.append("reviewed_artifacts_invalid")
    elif case_artifact_ref is not None and Path(str(case_artifact_ref)).name not in {
        Path(str(item)).name for item in reviewed_artifacts
    }:
        findings.append("reviewed_candidate_artifact_missing")

    answers = review.get("review_answers")
    required_answers = {
        "directional_preference_without_prohibited_inputs",
        "strongest_rival_preserved",
        "fair_baseline_distinct",
        "responsibility_unit_and_unknown_boundary",
        "golden_report_materiality",
    }
    if _cash_transmission_gate_required(candidate):
        required_answers.add("cash_transmission_recurrently_observable")
    if _is_v3_admission_contract(candidate):
        required_answers.add(
            "customer_absorption_independently_observable"
            if _customer_absorption_gate_required(candidate)
            else "customer_absorption_non_requirement_justified"
        )
    if _is_v4_admission_contract(candidate):
        required_answers.update({
            "v4_action_same_boundary_implemented",
            "v4_action_issuer_scope_and_decision_specificity_confirmed",
            "v4_materiality_thresholds_exactly_recomputed",
            "v4_d3_d4_independent_no_conversion",
            "v4_peer_panel_recurrently_observable_no_replacement",
            "v4_peer_business_and_market_exposure_confirmed",
            "v4_pre_action_structural_comparability_confirmed",
            "v4_d4_cash_bridge_complete_no_unmodeled_material_cash",
        })
        if _v4_mechanism_topology(candidate) == V4_COST_RESTRUCTURING_CHAIN:
            required_answers.add("v4_cost_driver_recurrently_observable_and_d2_non_voter")
    if not isinstance(answers, dict) or any(
        not str(answers.get(field) or "").upper().startswith("YES") for field in required_answers
    ):
        findings.append("independent_review_answers_incomplete")

    accepted = review.get("accepted_selection_basis")
    pair = candidate.get("rival_hypothesis_pair") if isinstance(candidate, dict) else None
    baseline = candidate.get("fair_simple_baseline") if isinstance(candidate, dict) else None
    primary = pair.get("primary_hypothesis") if isinstance(pair, dict) else None
    rival = pair.get("strongest_rival") if isinstance(pair, dict) else None
    prediction_stages = {
        str(prediction.get("predicate_id")): str(prediction.get("stage"))
        for prediction in (candidate.get("frozen_prediction_order") or [])
        if isinstance(prediction, dict) and _text(prediction.get("predicate_id"))
    }
    if not isinstance(accepted, dict):
        findings.append("accepted_selection_basis_missing")
    else:
        expected = {
            "primary_hypothesis_id": primary.get("hypothesis_id") if isinstance(primary, dict) else None,
            "strongest_rival_id": rival.get("hypothesis_id") if isinstance(rival, dict) else None,
            "simple_baseline_id": baseline.get("baseline_id") if isinstance(baseline, dict) else None,
        }
        if any(accepted.get(field) != value for field, value in expected.items()):
            findings.append("accepted_selection_basis_mismatch")

    if _cash_transmission_gate_required(candidate):
        transmission_review = review.get("cash_transmission_admission")
        if not isinstance(transmission_review, dict):
            findings.append("cash_transmission_independent_review_missing")
        else:
            if transmission_review.get("gate_version") != _admission_version(candidate):
                findings.append("cash_transmission_independent_review_gate_version_invalid")
            if transmission_review.get("primary_hypothesis_id") != (
                primary.get("hypothesis_id") if isinstance(primary, dict) else None
            ):
                findings.append("cash_transmission_independent_review_primary_mismatch")
            if transmission_review.get("verdict") != "RECURRINGLY_OBSERVABLE_PRE_OUTCOME":
                findings.append("cash_transmission_independent_review_verdict_invalid")
            if tuple(transmission_review.get("verified_leg_ids") or ()) != _CASH_TRANSMISSION_LEG_IDS:
                findings.append("cash_transmission_independent_review_leg_coverage_invalid")
            if transmission_review.get("d3_d4_substitution_prohibited") is not True:
                findings.append("cash_transmission_independent_review_d3_d4_boundary_invalid")
            if not _text(transmission_review.get("review_conclusion")):
                findings.append("cash_transmission_independent_review_conclusion_missing")

    if _is_v3_admission_contract(candidate):
        customer_review = review.get("customer_absorption_admission")
        if not isinstance(customer_review, dict):
            findings.append("customer_absorption_independent_review_missing")
        elif _customer_absorption_gate_required(candidate):
            if customer_review.get("gate_version") != _admission_version(candidate):
                findings.append("customer_absorption_independent_review_gate_version_invalid")
            if customer_review.get("primary_hypothesis_id") != (
                primary.get("hypothesis_id") if isinstance(primary, dict) else None
            ):
                findings.append("customer_absorption_independent_review_primary_mismatch")
            if customer_review.get("d2_predicate_id") not in prediction_stages or \
                    prediction_stages.get(customer_review.get("d2_predicate_id")) != "D2_CUSTOMER_ABSORPTION":
                findings.append("customer_absorption_independent_review_predicate_invalid")
            if customer_review.get("verdict") != "INDEPENDENTLY_OBSERVABLE_PRE_OUTCOME":
                findings.append("customer_absorption_independent_review_verdict_invalid")
            if customer_review.get("not_mechanically_changed_by_action") is not True:
                findings.append("customer_absorption_independent_review_mechanical_boundary_invalid")
            if not _text(customer_review.get("review_conclusion")):
                findings.append("customer_absorption_independent_review_conclusion_missing")
        elif customer_review.get("verdict") != "NOT_CAUSALLY_CENTRAL_PRE_OUTCOME" \
                or not _text(customer_review.get("review_conclusion")):
            findings.append("customer_absorption_non_requirement_review_invalid")

    if _is_v4_admission_contract(candidate):
        cash_observability = candidate.get("cash_transmission_observability")
        anchors = cash_observability.get("materiality_anchors") if isinstance(cash_observability, dict) else None
        action = anchors.get("action_exposure") if isinstance(anchors, dict) else None
        panel = candidate.get("peer_panel_observability")
        relative_method = panel.get("relative_method") if isinstance(panel, dict) else None

        materiality_review = review.get("v4_materiality_admission")
        if not isinstance(materiality_review, dict):
            findings.append("v4_materiality_independent_review_missing")
        else:
            expected_action_id = action.get("action_id") if isinstance(action, dict) else None
            expected_reference_period = (
                relative_method.get("reference_period_end") if isinstance(relative_method, dict) else None
            )
            if materiality_review.get("gate_version") != PEER_PANEL_ADMISSION_VERSION:
                findings.append("v4_materiality_independent_review_gate_version_invalid")
            if materiality_review.get("primary_hypothesis_id") != (
                primary.get("hypothesis_id") if isinstance(primary, dict) else None
            ):
                findings.append("v4_materiality_independent_review_primary_mismatch")
            if materiality_review.get("action_id") != expected_action_id \
                    or materiality_review.get("reference_period_end") != expected_reference_period:
                findings.append("v4_materiality_independent_review_identity_mismatch")
            if materiality_review.get("verdict") != "MECHANICALLY_MATERIAL_PRE_OUTCOME":
                findings.append("v4_materiality_independent_review_verdict_invalid")
            for field in (
                "same_candidate_common_boundary_confirmed",
                "implemented_or_irrevocably_incurred_confirmed",
                "issuer_scope_bridge_confirmed",
                "decision_specific_incremental_exposure_confirmed",
                "qualified_action_exposure_confirmed",
                "action_exposure_at_least_d3_step_confirmed",
                "d3_step_exactly_recomputed",
                "d4_step_exactly_recomputed",
                "d3_d4_independent_no_conversion",
            ):
                if materiality_review.get(field) is not True:
                    findings.append("v4_materiality_independent_review_" + field + "_missing")
            if not _text(materiality_review.get("review_conclusion")):
                findings.append("v4_materiality_independent_review_conclusion_missing")

        panel_review = review.get("peer_panel_admission")
        if not isinstance(panel_review, dict):
            findings.append("v4_peer_panel_independent_review_missing")
        else:
            expected_panel_id = panel.get("panel_contract_id") if isinstance(panel, dict) else None
            expected_order = (
                panel.get("frozen_panel", {}).get("frozen_order")
                if isinstance(panel, dict) and isinstance(panel.get("frozen_panel"), dict) else None
            )
            if panel_review.get("gate_version") != PEER_PANEL_ADMISSION_VERSION:
                findings.append("v4_peer_panel_independent_review_gate_version_invalid")
            if panel_review.get("primary_hypothesis_id") != (
                primary.get("hypothesis_id") if isinstance(primary, dict) else None
            ):
                findings.append("v4_peer_panel_independent_review_primary_mismatch")
            if panel_review.get("verified_panel_contract_id") != expected_panel_id \
                    or panel_review.get("verified_frozen_order") != expected_order:
                findings.append("v4_peer_panel_independent_review_identity_mismatch")
            if panel_review.get("verdict") != "FIXED_PANEL_RECURRENTLY_OBSERVABLE_PRE_OUTCOME":
                findings.append("v4_peer_panel_independent_review_verdict_invalid")
            for field in (
                "same_industry_confirmed",
                "common_market_exposure_confirmed",
                "target_pre_action_d3_d4_recurrence_confirmed",
                "peer_annual_d3_d4_recurrence_confirmed",
                "no_replacement_confirmed",
            ):
                if panel_review.get(field) is not True:
                    findings.append("v4_peer_panel_independent_review_" + field + "_missing")
            if not _text(panel_review.get("review_conclusion")):
                findings.append("v4_peer_panel_independent_review_conclusion_missing")

        comparability_review = review.get("v4_comparability_admission")
        if not isinstance(comparability_review, dict):
            findings.append("v4_comparability_independent_review_missing")
        else:
            if comparability_review.get("gate_version") != PEER_PANEL_ADMISSION_VERSION \
                    or comparability_review.get("panel_contract_id") != (
                        panel.get("panel_contract_id") if isinstance(panel, dict) else None
                    ) \
                    or comparability_review.get("verdict") != "COMPARABLE_PRE_ACTION_WINDOW_CONFIRMED":
                findings.append("v4_comparability_independent_review_identity_or_verdict_invalid")
            for field in (
                "target_window_source_checked",
                "peer_windows_source_checked",
                "material_breaks_excluded_from_selected_windows",
            ):
                if comparability_review.get(field) is not True:
                    findings.append("v4_comparability_independent_review_" + field + "_missing")
            if not _text(comparability_review.get("review_conclusion")):
                findings.append("v4_comparability_independent_review_conclusion_missing")

        cash_bridge_review = review.get("v4_d4_cash_bridge_admission")
        if not isinstance(cash_bridge_review, dict):
            findings.append("v4_d4_cash_bridge_independent_review_missing")
        else:
            expected_action_id = action.get("action_id") if isinstance(action, dict) else None
            if cash_bridge_review.get("gate_version") != PEER_PANEL_ADMISSION_VERSION \
                    or cash_bridge_review.get("action_id") != expected_action_id \
                    or cash_bridge_review.get("verdict") != "COMPLETE_PRE_OUTCOME":
                findings.append("v4_d4_cash_bridge_independent_review_identity_or_verdict_invalid")
            for field in (
                "operating_cash_flow_raw_fields_checked",
                "long_lived_asset_cash_raw_fields_checked",
                "cash_working_capital_raw_fields_checked",
                "action_related_cash_observed_or_source_confirmed_not_applicable",
                "unmodeled_material_cash_items_absent",
            ):
                if cash_bridge_review.get(field) is not True:
                    findings.append("v4_d4_cash_bridge_independent_review_" + field + "_missing")
            if not _text(cash_bridge_review.get("review_conclusion")):
                findings.append("v4_d4_cash_bridge_independent_review_conclusion_missing")

        if _v4_mechanism_topology(candidate) == V4_COST_RESTRUCTURING_CHAIN:
            cost_review = review.get("v4_cost_driver_admission")
            driver = candidate.get("cost_driver_observability")
            if not isinstance(cost_review, dict):
                findings.append("v4_cost_driver_independent_review_missing")
            else:
                if cost_review.get("gate_version") != PEER_PANEL_ADMISSION_VERSION \
                        or cost_review.get("primary_hypothesis_id") != (
                            primary.get("hypothesis_id") if isinstance(primary, dict) else None
                        ) \
                        or cost_review.get("d3_predicate_id") != _dict(driver).get("d3_predicate_id") \
                        or cost_review.get("verdict") != "COST_DRIVER_RECURRENTLY_OBSERVABLE_PRE_OUTCOME":
                    findings.append("v4_cost_driver_independent_review_identity_or_verdict_invalid")
                if cost_review.get("d2_customer_absorption_conclusion_prohibited") is not True \
                        or cost_review.get("cost_driver_same_common_boundary_confirmed") is not True:
                    findings.append("v4_cost_driver_independent_review_boundary_missing")
                if not _text(cost_review.get("review_conclusion")):
                    findings.append("v4_cost_driver_independent_review_conclusion_missing")

    boundary = review.get("admission_boundary")
    if not isinstance(boundary, dict) or not isinstance(boundary.get("does_not_grant"), list) or not boundary["does_not_grant"]:
        findings.append("admission_boundary_missing")

    return {
        "schema_version": "judgment-selection-review-validation.v1",
        "state": "INVALID" if findings else "REVIEWABLE",
        "admission_state": "NOT_ADMITTED" if findings else "SELECTION_ADMITTED_PRE_OUTCOME",
        "findings": findings,
    }
