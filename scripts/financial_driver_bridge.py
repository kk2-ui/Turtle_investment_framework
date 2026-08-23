#!/usr/bin/env python3
"""Evidence-bound bridge from operating drivers to valuation and decisions.

The bridge is deliberately small: it does not estimate value.  It prevents a
report from treating a financial line item as a durable economic driver unless
the observation, model use, and decision consequence are all explicit.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "financial-driver-bridge.v1"
# v3 adds a source-bound normal-owner-cash status alongside the v2
# capital-commitment trace. The bridge schema itself remains v1 because these
# are additive fields; old policy files deliberately retain their v1 behavior.
POLICY_VERSION = "financial-driver-bridge-policy.v4"
LAYERS = {
    "COMPETITION_DEMAND", "UNIT_ECONOMICS", "CASH_CONVERSION", "CAPITAL_ALLOCATION",
}
DRIVER_STATUSES = {"OBSERVED", "UNKNOWN"}
ANALYSIS_PURPOSES = {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}
BINDING_TREATMENTS = {
    "DIRECT_INPUT", "NORMALIZATION_ADJUSTMENT", "SENSITIVITY", "QUALITATIVE_GUARDRAIL",
}
ALLOCATION_EVENT_TYPES = {
    "OPERATING_CAPEX", "FINANCIAL_ASSET_ROLLOVER", "ACQUISITION", "DISPOSAL", "IMPAIRMENT",
    "DIVIDEND", "FINANCING", "OTHER",
}
ALLOCATION_CLASSIFICATIONS = {
    "OPERATING_REINVESTMENT", "LIQUIDITY_MANAGEMENT", "VALUE_DESTRUCTIVE_CANDIDATE",
    "RETURN_OF_CAPITAL", "UNRESOLVED",
}
COMMITMENT_MOVEMENTS = {"ESCALATE", "MAINTAIN", "DEESCALATE", "UNKNOWN"}
COMMITMENT_MOVEMENT_SCOPES = {"FULL", "PARTIAL", "UNKNOWN"}
COMMITMENT_MONITORING_STAGES = {"EARLY_SIGNAL", "TERMINAL_OUTCOME"}
MONITORING_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT", "OFFICIAL_STATISTICS", "OTHER_OFFICIAL",
    "LICENSED_INDUSTRY_DATA",
}
INDEPENDENT_INDUSTRY_MONITORING_LAYERS = {"COMPETITION_DEMAND", "UNIT_ECONOMICS"}
CASH_NORMALIZATION_STATES = {"NORMALIZED", "UNKNOWN", "REPORTED_CASH_STATE_ONLY"}
CASH_ADJUSTMENT_DIRECTIONS = {"ADD_BACK", "DEDUCT", "EXCLUDE"}
CASH_RECURRENCE_ASSESSMENTS = {"RECURRING", "NON_RECURRING", "UNKNOWN"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return item if isinstance(item, dict) else {}


def _write_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _valid_date(value: Any) -> bool:
    try:
        date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _policy_requires_allocation_commitment_trace(policy: dict[str, Any]) -> bool:
    """Keep old frozen policies readable while making new PIT policies strict."""
    return bool(
        policy.get("enforced")
        and policy.get("schema_version") == POLICY_VERSION
        and policy.get("allocation_commitment_trace_required") is True
    )


def _policy_requires_cash_normalization_contract(policy: dict[str, Any]) -> bool:
    """Make new production bridges state whether owner cash is truly normalized."""
    return bool(
        policy.get("enforced")
        and policy.get("schema_version") == POLICY_VERSION
        and policy.get("cash_normalization_contract_required") is True
    )


def _policy_requires_forward_judgment_binding(policy: dict[str, Any]) -> bool:
    """Apply the cross-ledger binding only to new, enforced bridge policies."""
    return bool(
        policy.get("enforced")
        and policy.get("schema_version") == POLICY_VERSION
    )


def _verified_observations(
    value: Any, *, prefix: str, observation_ids: set[str], verify_observations: bool,
    invalid: list[str], incomplete: list[str],
) -> list[str]:
    """Require explicit VERIFIED observations without inferring their economics."""
    cited = _ids(value)
    if not cited:
        incomplete.append(prefix + "_missing")
        return []
    if verify_observations:
        for observation_id in cited:
            if observation_id not in observation_ids:
                invalid.append(prefix + ":unverified_observation:" + observation_id)
    return cited


def _validate_cash_normalization_contract(
    item: dict[str, Any], *, prefix: str, observation_ids: set[str],
    verify_observations: bool, invalid: list[str], incomplete: list[str],
) -> None:
    """Prevent reported cash flow from silently becoming normal owner cash.

    This records the evidence boundary, not a calculated free-cash-flow
    number. A company may honestly remain UNKNOWN; the required conservative
    treatment then prevents OCF or a cash balance from becoming an owner-cash
    conclusion.
    """
    contract = item.get("cash_normalization_contract")
    if not isinstance(contract, dict):
        incomplete.append(prefix + "_missing")
        return
    state = str(contract.get("state") or "")
    if state not in CASH_NORMALIZATION_STATES:
        invalid.append(prefix + ":state_invalid")
        return
    if state == "UNKNOWN":
        for field in ("unknown_reason", "conservative_treatment"):
            if not str(contract.get(field) or "").strip():
                incomplete.append(prefix + ":" + field + "_missing")
        return

    for field in ("reported_cash_metric", "conservative_treatment"):
        if not str(contract.get(field) or "").strip():
            incomplete.append(prefix + ":" + field + "_missing")
    _verified_observations(
        contract.get("reported_cash_observation_ids"),
        prefix=prefix + ":reported_cash_observation_ids",
        observation_ids=observation_ids,
        verify_observations=verify_observations,
        invalid=invalid,
        incomplete=incomplete,
    )
    if state == "REPORTED_CASH_STATE_ONLY":
        return

    for field in (
        "maintenance_capex_treatment",
        "working_capital_treatment",
        "cash_accessibility_treatment",
    ):
        if not str(contract.get(field) or "").strip():
            incomplete.append(prefix + ":" + field + "_missing")
    for field in (
        "maintenance_capex_observation_ids",
        "working_capital_observation_ids",
        "cash_accessibility_observation_ids",
    ):
        _verified_observations(
            contract.get(field),
            prefix=prefix + ":" + field,
            observation_ids=observation_ids,
            verify_observations=verify_observations,
            invalid=invalid,
            incomplete=incomplete,
        )
    adjustments = contract.get("adjustment_components")
    if not isinstance(adjustments, list) or not adjustments:
        incomplete.append(prefix + ":adjustment_components_missing")
        return
    for index, adjustment in enumerate(adjustments):
        aprefix = f"{prefix}:adjustment_components[{index}]"
        if not isinstance(adjustment, dict):
            invalid.append(aprefix + ":not_object")
            continue
        if not str(adjustment.get("component_id") or "").strip():
            incomplete.append(aprefix + ":component_id_missing")
        if adjustment.get("direction") not in CASH_ADJUSTMENT_DIRECTIONS:
            invalid.append(aprefix + ":direction_invalid")
        if adjustment.get("recurrence_assessment") not in CASH_RECURRENCE_ASSESSMENTS:
            invalid.append(aprefix + ":recurrence_assessment_invalid")
        if not str(adjustment.get("treatment") or "").strip():
            incomplete.append(aprefix + ":treatment_missing")
        _verified_observations(
            adjustment.get("observation_ids"), prefix=aprefix + ":observation_ids",
            observation_ids=observation_ids, verify_observations=verify_observations,
            invalid=invalid, incomplete=incomplete,
        )


def _validate_monitoring_contract(
    contract: Any, *, prefix: str, id_prefix: str, allow_independent_industry_data: bool = False,
) -> tuple[list[str], list[str]]:
    """Keep later observation rules as structured contracts, not prose intent."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(contract, dict):
        return invalid, [prefix + "_missing"]
    contract_id = str(contract.get("contract_id") or "").strip()
    if not contract_id.startswith(id_prefix):
        invalid.append(prefix + ":contract_id_invalid")
    if not _ids(contract.get("forward_judgment_ids")):
        incomplete.append(prefix + ":forward_judgment_ids_missing")
    for field in ("metric", "unit", "measurement_basis", "comparability_rule"):
        if not str(contract.get(field) or "").strip():
            incomplete.append(prefix + ":" + field + "_missing")
    period = contract.get("measurement_period") if isinstance(contract.get("measurement_period"), dict) else {}
    if not _valid_date(period.get("start")) or not _valid_date(period.get("end")):
        invalid.append(prefix + ":measurement_period_invalid")
    elif str(period.get("start")) > str(period.get("end")):
        invalid.append(prefix + ":measurement_period_order_invalid")
    allowed_sources = contract.get("allowed_source_types")
    if not isinstance(allowed_sources, list) or not allowed_sources:
        incomplete.append(prefix + ":allowed_source_types_missing")
    else:
        permitted_sources = set(MONITORING_SOURCE_TYPES)
        if not allow_independent_industry_data:
            permitted_sources.discard("LICENSED_INDUSTRY_DATA")
        if any(str(source_type) not in permitted_sources for source_type in allowed_sources):
            invalid.append(prefix + ":allowed_source_type_invalid")
    window = contract.get("observation_window") if isinstance(contract.get("observation_window"), dict) else {}
    if not _valid_date(window.get("opens_after")) or not _valid_date(window.get("closes_at")):
        invalid.append(prefix + ":observation_window_invalid")
    elif str(window.get("opens_after")) >= str(window.get("closes_at")):
        invalid.append(prefix + ":observation_window_order_invalid")
    return invalid, incomplete


def _validate_allocation_commitment_trace(
    item: dict[str, Any],
    *,
    event_id: str,
    prefix: str,
    decision_date: Any,
    realization: dict[str, Any],
    observation_ids: set[str],
    verify_observations: bool,
    invalid: list[str],
    incomplete: list[str],
) -> None:
    """Validate the smallest auditable initiation -> movement -> outcome chain.

    This intentionally records only disclosed commitment facts and the next
    disclosed continuation, escalation, or de-escalation.  A static balance or
    ownership percentage is not itself a disclosed continuation decision.  It
    neither classifies investment quality
    from a price/return nor turns a financial-asset balance into reinvestment.
    """
    initial_prefix = f"{event_id or prefix}:initial_commitment"
    initial = item.get("initial_commitment")
    if not isinstance(initial, dict):
        incomplete.append(initial_prefix + "_missing")
    else:
        amount = initial.get("amount")
        if _is_number(amount):
            funding_source = str(initial.get("funding_source") or "").strip()
            if not funding_source:
                incomplete.append(initial_prefix + ":funding_source_missing")
            elif funding_source == "UNKNOWN":
                if not str(initial.get("unknown_reason") or "").strip():
                    incomplete.append(initial_prefix + ":funding_source_unknown_reason_missing")
                if not str(initial.get("conservative_treatment") or "").strip():
                    incomplete.append(initial_prefix + ":funding_source_conservative_treatment_missing")
            if not str(initial.get("currency") or "").strip():
                incomplete.append(initial_prefix + ":currency_missing")
            _verified_observations(
                initial.get("observation_ids"),
                prefix=initial_prefix + ":observation_ids",
                observation_ids=observation_ids,
                verify_observations=verify_observations,
                invalid=invalid,
                incomplete=incomplete,
            )
        elif amount == "UNKNOWN":
            if _ids(initial.get("observation_ids")):
                invalid.append(initial_prefix + ":unknown_cannot_cite_as_verified_amount")
            if not str(initial.get("unknown_reason") or "").strip():
                incomplete.append(initial_prefix + ":unknown_reason_missing")
            if not str(initial.get("conservative_treatment") or "").strip():
                incomplete.append(initial_prefix + ":conservative_treatment_missing")
        else:
            invalid.append(initial_prefix + ":amount_must_be_number_or_UNKNOWN")

    movement_prefix = f"{event_id or prefix}:commitment_movement"
    movement = item.get("commitment_movement")
    if not isinstance(movement, dict):
        incomplete.append(movement_prefix + "_missing")
        return
    movement_type = str(movement.get("movement") or "")
    if movement_type not in COMMITMENT_MOVEMENTS:
        invalid.append(movement_prefix + ":movement_invalid")
    movement_scope = str(movement.get("scope") or "")
    if movement_scope not in COMMITMENT_MOVEMENT_SCOPES:
        invalid.append(movement_prefix + ":scope_invalid")
    elif movement_scope == "PARTIAL":
        affected_fraction = movement.get("affected_fraction_of_initial")
        if not _is_number(affected_fraction) or not 0 < float(affected_fraction) < 1:
            invalid.append(movement_prefix + ":partial_affected_fraction_invalid")
    elif movement_scope == "FULL" and "affected_fraction_of_initial" in movement:
        invalid.append(movement_prefix + ":full_cannot_carry_partial_fraction")
    elif movement_scope == "UNKNOWN":
        if "affected_fraction_of_initial" in movement:
            invalid.append(movement_prefix + ":unknown_cannot_carry_partial_fraction")
        for field in ("scope_unknown_reason", "scope_conservative_treatment"):
            if not str(movement.get(field) or "").strip():
                incomplete.append(movement_prefix + ":" + field + "_missing")
    movement_date = movement.get("observation_date")
    if not _valid_date(movement_date):
        invalid.append(movement_prefix + ":observation_date_invalid")
    elif _valid_date(decision_date) and str(movement_date) <= str(decision_date):
        invalid.append(movement_prefix + ":observation_date_must_follow_initial_commitment")
    if movement_type == "UNKNOWN":
        if _ids(movement.get("observation_ids")):
            invalid.append(movement_prefix + ":unknown_cannot_cite_as_verified_movement")
        if not str(movement.get("unknown_reason") or "").strip():
            incomplete.append(movement_prefix + ":unknown_reason_missing")
        if not str(movement.get("conservative_treatment") or "").strip():
            incomplete.append(movement_prefix + ":conservative_treatment_missing")
    elif movement_type in COMMITMENT_MOVEMENTS:
        _verified_observations(
            movement.get("observation_ids"),
            prefix=movement_prefix + ":observation_ids",
            observation_ids=observation_ids,
            verify_observations=verify_observations,
            invalid=invalid,
            incomplete=incomplete,
        )

    linked_realization_id = str(movement.get("realization_contract_id") or "").strip()
    realization_id = str(realization.get("contract_id") or "").strip()
    if not linked_realization_id:
        incomplete.append(movement_prefix + ":realization_contract_id_missing")
    elif not realization_id:
        incomplete.append(movement_prefix + ":realization_contract_link_unavailable")
    elif linked_realization_id != realization_id:
        invalid.append(movement_prefix + ":realization_contract_id_mismatch")
    stage = str(movement.get("monitoring_stage") or "")
    if stage not in COMMITMENT_MONITORING_STAGES:
        invalid.append(movement_prefix + ":monitoring_stage_invalid")
    monitoring_id = str(movement.get("monitoring_contract_id") or "").strip()
    if not monitoring_id:
        incomplete.append(movement_prefix + ":monitoring_contract_id_missing")
    elif stage in COMMITMENT_MONITORING_STAGES:
        stage_key = "early_signal" if stage == "EARLY_SIGNAL" else "terminal_outcome"
        stage_contract = realization.get(stage_key)
        expected_monitoring_id = (
            str(stage_contract.get("contract_id") or "").strip()
            if isinstance(stage_contract, dict) else ""
        )
        if not expected_monitoring_id:
            incomplete.append(movement_prefix + ":monitoring_contract_link_unavailable")
        elif monitoring_id != expected_monitoring_id:
            invalid.append(movement_prefix + ":monitoring_contract_id_mismatch")


def _known_bindings(output: Path) -> tuple[set[str], set[str], set[str]]:
    facts = _read_object(output / "fact_observations.json")
    observation_ids = {
        str(item.get("observation_id"))
        for item in facts.get("observations") or []
        if isinstance(item, dict) and item.get("status") == "VERIFIED" and item.get("observation_id")
    }
    valuation = _read_object(output / "valuation_model.json")
    model_ids = {
        str(item.get("model_id")) for item in valuation.get("models") or []
        if isinstance(item, dict) and item.get("model_id")
    }
    decisions = _read_object(output / "decision_ledger.json")
    decision_ids = {
        str(item.get("entry_id")) for item in decisions.get("entries") or []
        if isinstance(item, dict) and item.get("entry_id")
    }
    return observation_ids, model_ids, decision_ids


def _forward_judgment_binding_findings(
    bridge: dict[str, Any], thesis: dict[str, Any],
) -> list[str]:
    """Verify that bridge monitoring contracts point to actual frozen FJs.

    The bridge is deliberately written before the thesis ledger, so this
    check belongs to output evaluation rather than initial persistence.  Once
    a thesis ledger exists, an arbitrary FJ-looking string must not keep the
    bridge eligible for a report snapshot or settlement.
    """
    known_judgment_ids = {
        str(item.get("judgment_id") or "").strip()
        for item in thesis.get("forward_judgments") or []
        if isinstance(item, dict) and str(item.get("judgment_id") or "").strip()
    }
    referenced: list[tuple[str, str]] = []

    def collect(contract: Any, prefix: str) -> None:
        if not isinstance(contract, dict):
            return
        for judgment_id in _ids(contract.get("forward_judgment_ids")):
            referenced.append((prefix, judgment_id))

    for item in bridge.get("drivers") or []:
        if isinstance(item, dict):
            collect(item.get("monitoring_contract"), str(item.get("driver_id") or "driver"))
    for item in bridge.get("allocation_events") or []:
        if not isinstance(item, dict):
            continue
        prefix = str(item.get("event_id") or "allocation_event")
        realization = item.get("realization_contract")
        collect(realization, prefix + ":realization")
        if isinstance(realization, dict):
            collect(realization.get("early_signal"), prefix + ":early_signal")
            collect(realization.get("terminal_outcome"), prefix + ":terminal_outcome")

    findings: list[str] = []
    for prefix, judgment_id in referenced:
        if judgment_id not in known_judgment_ids:
            findings.append(prefix + ":forward_judgment_unbound:" + judgment_id)

    # Monitoring remains valuable when cash is not normalized or an allocation
    # event remains unresolved. It is not a basis for choosing the central
    # path. The thesis must keep those FJs outside selection admission.
    monitoring_only: list[tuple[str, str]] = []
    for item in bridge.get("drivers") or []:
        if not isinstance(item, dict) or item.get("layer") != "CASH_CONVERSION":
            continue
        contract = item.get("cash_normalization_contract")
        if isinstance(contract, dict) and contract.get("state") != "NORMALIZED":
            for judgment_id in _ids((item.get("monitoring_contract") or {}).get("forward_judgment_ids")):
                monitoring_only.append((str(item.get("driver_id") or "driver"), judgment_id))
    for item in bridge.get("allocation_events") or []:
        if not isinstance(item, dict) or item.get("classification") != "UNRESOLVED":
            continue
        realization = item.get("realization_contract")
        if not isinstance(realization, dict):
            continue
        for judgment_id in _ids(realization.get("forward_judgment_ids")):
            monitoring_only.append((str(item.get("event_id") or "allocation_event"), judgment_id))
        for stage in ("early_signal", "terminal_outcome"):
            for judgment_id in _ids((realization.get(stage) or {}).get("forward_judgment_ids")):
                monitoring_only.append((str(item.get("event_id") or "allocation_event") + ":" + stage, judgment_id))
    selection = thesis.get("selection_admission")
    selected_judgment_ids = set(_ids((selection or {}).get("selection_forward_judgment_ids"))) if isinstance(selection, dict) else set()
    for prefix, judgment_id in monitoring_only:
        if judgment_id in selected_judgment_ids:
            findings.append(prefix + ":monitoring_only_forward_judgment_selected:" + judgment_id)
    return list(dict.fromkeys(findings))


def _frozen_thesis_validation(output: Path, thesis: dict[str, Any]) -> dict[str, Any]:
    """Revalidate frozen FJs without treating report-anchor checks as bridge checks."""
    try:
        from scripts.thesis_test_gate import validate_thesis_test_ledger
    except ModuleNotFoundError:
        from thesis_test_gate import validate_thesis_test_ledger
    validation = validate_thesis_test_ledger(
        thesis,
        output_dir=output,
        enforced=True,
        monitoring_required=True,
        forward_judgment_required=True,
        rival_hypothesis_pair_required=True,
    )
    # A bridge is produced before prose assembly, so it cannot require the
    # eventual report markers. Those markers remain a separate thesis/report
    # gate. Every other ledger, FJ, pair, and freeze failure remains binding.
    report_anchor_prefixes = (
        "central_path_reference_missing:",
        "thesis_test_reference_missing:",
        "threshold_reference_missing:",
        "probability_reference_missing:",
    )
    substantive_incomplete = [
        finding for finding in validation.get("incomplete_findings") or []
        if not str(finding).startswith(report_anchor_prefixes)
    ]
    frozen = bool((thesis.get("freeze") or {}).get("frozen"))
    if validation.get("invalid_findings"):
        state = "INVALID"
    elif substantive_incomplete or not frozen:
        state = "INCOMPLETE"
    else:
        state = "MONITORING" if thesis.get("lifecycle") == "monitoring" else "DECISION_READY"
    return {
        **validation,
        "state": state,
        "incomplete_findings": substantive_incomplete,
    }


def build_financial_driver_bridge(
    output_dir: str | Path,
    drivers: list[dict[str, Any]],
    allocation_events: list[dict[str, Any]],
    *,
    report_id: str,
    as_of: str,
    change_reason: str,
    lifecycle: str = "reviewable",
    analysis_purpose: str = "INVESTMENT_DECISION",
) -> dict[str, Any]:
    """Create a candidate bridge; validation is intentionally a separate step."""
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": str(report_id),
        "as_of": str(as_of),
        "analysis_purpose": str(analysis_purpose),
        "lifecycle": str(lifecycle),
        "change_reason": str(change_reason),
        "drivers": deepcopy(drivers),
        "allocation_events": deepcopy(allocation_events),
        "generated_at": _now(),
    }


def initialize_financial_driver_bridge_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool
) -> dict[str, Any]:
    payload = {
        "schema_version": POLICY_VERSION,
        "run_id": str(run_id),
        "enforced": bool(enforced),
        # This is intentionally policy-scoped.  Existing v1 policies and
        # bridge-only historical cases keep their prior accepted shape.
        "allocation_commitment_trace_required": bool(enforced),
        "cash_normalization_contract_required": bool(enforced),
        "created_at": _now(),
    }
    _write_object(Path(output_dir) / "financial_driver_bridge_policy.json", payload)
    return payload


def _validate_company_judgment_lineage(
    payload: dict[str, Any], *, output_dir: str | Path | None,
) -> list[str]:
    """Keep the frozen CJO operating bridge intact while valuation binds it."""
    if payload.get("analysis_purpose") != "INVESTMENT_DECISION" or output_dir is None:
        return []
    predecessor = _read_object(Path(output_dir) / "company_judgment_predecessor.json")
    identity = predecessor.get("identity") if isinstance(predecessor.get("identity"), dict) else {}
    if identity.get("status") != "G1J_COMPLETE":
        return []
    inherited_bridge = (
        predecessor.get("financial_driver_bridge")
        if isinstance(predecessor.get("financial_driver_bridge"), dict) else {}
    )
    if not inherited_bridge:
        return ["company_judgment_predecessor_financial_driver_bridge_invalid"]

    invalid: list[str] = []
    for field in ("report_id", "as_of"):
        if inherited_bridge.get(field) != payload.get(field):
            invalid.append(f"company_judgment_lineage_financial_driver_bridge_{field}_mismatch")
    inherited_drivers = {
        str(item.get("driver_id")): item
        for item in inherited_bridge.get("drivers") or []
        if isinstance(item, dict) and item.get("driver_id")
    }
    current_drivers = {
        str(item.get("driver_id")): item
        for item in payload.get("drivers") or []
        if isinstance(item, dict) and item.get("driver_id")
    }
    if not inherited_drivers:
        invalid.append("company_judgment_predecessor_financial_drivers_invalid")
    for driver_id in sorted(inherited_drivers.keys() - current_drivers.keys()):
        invalid.append(f"company_judgment_lineage_financial_driver_missing:{driver_id}")
    for driver_id in sorted(current_drivers.keys() - inherited_drivers.keys()):
        invalid.append(f"company_judgment_lineage_financial_driver_extra:{driver_id}")
    for driver_id in sorted(inherited_drivers.keys() & current_drivers.keys()):
        inherited = deepcopy(inherited_drivers[driver_id])
        current = deepcopy(current_drivers[driver_id])
        inherited.pop("model_bindings", None)
        current.pop("model_bindings", None)
        if current != inherited:
            invalid.append(f"company_judgment_lineage_financial_driver_rewritten:{driver_id}")

    inherited_events = {
        str(item.get("event_id")): item
        for item in inherited_bridge.get("allocation_events") or []
        if isinstance(item, dict) and item.get("event_id")
    }
    current_events = {
        str(item.get("event_id")): item
        for item in payload.get("allocation_events") or []
        if isinstance(item, dict) and item.get("event_id")
    }
    for event_id in sorted(inherited_events.keys() - current_events.keys()):
        invalid.append(f"company_judgment_lineage_allocation_event_missing:{event_id}")
    for event_id in sorted(current_events.keys() - inherited_events.keys()):
        invalid.append(f"company_judgment_lineage_allocation_event_extra:{event_id}")
    for event_id in sorted(inherited_events.keys() & current_events.keys()):
        if current_events[event_id] != inherited_events[event_id]:
            invalid.append(f"company_judgment_lineage_allocation_event_rewritten:{event_id}")
    return invalid


def validate_financial_driver_bridge(
    payload: dict[str, Any], *, output_dir: str | Path | None = None,
    require_allocation_commitment_trace: bool = False,
    require_cash_normalization_contract: bool = False,
) -> dict[str, Any]:
    """Validate evidence, model and decision bindings without inferring economics."""
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(payload.get("report_id") or "").strip():
        invalid.append("report_id_missing")
    if not _valid_date(payload.get("as_of")):
        invalid.append("as_of_invalid")
    if not str(payload.get("change_reason") or "").strip():
        incomplete.append("change_reason_missing")
    if payload.get("lifecycle") not in {"reviewable", "decision_ready"}:
        invalid.append("lifecycle_invalid")
    analysis_purpose = str(payload.get("analysis_purpose") or "")
    if analysis_purpose not in ANALYSIS_PURPOSES:
        invalid.append("analysis_purpose_invalid")

    observation_ids: set[str] = set()
    model_ids: set[str] = set()
    decision_ids: set[str] = set()
    if output_dir is None:
        warnings.append("external_binding_sets_not_checked")
    else:
        observation_ids, model_ids, decision_ids = _known_bindings(Path(output_dir))

    drivers = payload.get("drivers")
    if not isinstance(drivers, list):
        invalid.append("drivers_not_array")
        drivers = []
    seen_drivers: set[str] = set()
    monitoring_contract_ids: set[str] = set()
    covered_layers: set[str] = set()
    for index, item in enumerate(drivers):
        prefix = f"drivers[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        driver_id = str(item.get("driver_id") or "").strip()
        if not driver_id:
            invalid.append(prefix + ":driver_id_missing")
        elif driver_id in seen_drivers:
            invalid.append("duplicate_driver_id:" + driver_id)
        seen_drivers.add(driver_id)
        layer = str(item.get("layer") or "")
        if layer not in LAYERS:
            invalid.append(f"{driver_id or prefix}:layer_invalid")
        else:
            covered_layers.add(layer)
        if not str(item.get("statement") or "").strip():
            incomplete.append(f"{driver_id or prefix}:statement_missing")
        period = item.get("measurement_period")
        if not isinstance(period, dict) or not _valid_date(period.get("start")) or not _valid_date(period.get("end")):
            invalid.append(f"{driver_id or prefix}:measurement_period_invalid")
        elif str(period["start"]) > str(period["end"]):
            invalid.append(f"{driver_id or prefix}:measurement_period_order_invalid")
        status = str(item.get("status") or "")
        if status not in DRIVER_STATUSES:
            invalid.append(f"{driver_id or prefix}:status_invalid")
        cited = _ids(item.get("observation_ids"))
        if status == "OBSERVED":
            if not cited:
                incomplete.append(f"{driver_id or prefix}:observed_observation_ids_missing")
            elif output_dir is not None:
                for observation_id in cited:
                    if observation_id not in observation_ids:
                        invalid.append(f"{driver_id or prefix}:unverified_observation:{observation_id}")
        elif status == "UNKNOWN":
            if cited:
                invalid.append(f"{driver_id or prefix}:unknown_cannot_cite_as_observed")
            if not str(item.get("unknown_reason") or "").strip():
                incomplete.append(f"{driver_id or prefix}:unknown_reason_missing")
            if not str(item.get("conservative_treatment") or "").strip():
                incomplete.append(f"{driver_id or prefix}:conservative_treatment_missing")

        if layer == "CASH_CONVERSION" and require_cash_normalization_contract:
            _validate_cash_normalization_contract(
                item,
                prefix=f"{driver_id or prefix}:cash_normalization_contract",
                observation_ids=observation_ids,
                verify_observations=output_dir is not None,
                invalid=invalid,
                incomplete=incomplete,
            )

        monitoring_prefix = f"{driver_id or prefix}:monitoring_contract"
        monitoring = item.get("monitoring_contract")
        monitoring_invalid, monitoring_incomplete = _validate_monitoring_contract(
            monitoring,
            prefix=monitoring_prefix,
            id_prefix="FDBMON:",
            allow_independent_industry_data=layer in INDEPENDENT_INDUSTRY_MONITORING_LAYERS,
        )
        invalid.extend(monitoring_invalid)
        incomplete.extend(monitoring_incomplete)
        if isinstance(monitoring, dict):
            monitoring_id = str(monitoring.get("contract_id") or "").strip()
            if monitoring_id:
                if monitoring_id in monitoring_contract_ids:
                    invalid.append("duplicate_monitoring_contract_id:" + monitoring_id)
                monitoring_contract_ids.add(monitoring_id)

        # A company-only number is not automatically an industry mechanism.
        # An observed competition/demand driver must say what customers can
        # choose instead, which market is being compared, and why the cited
        # observation is informative within that scope.  This keeps an online
        # share or a management assertion from silently becoming a full-market
        # moat claim; an unavailable comparison remains an explicit UNKNOWN.
        if layer == "COMPETITION_DEMAND" and status == "OBSERVED":
            context = item.get("competitive_context")
            context_prefix = f"{driver_id or prefix}:competitive_context"
            if not isinstance(context, dict):
                incomplete.append(context_prefix + "_missing")
            else:
                for field in ("market_definition", "scope_limit"):
                    if not str(context.get(field) or "").strip():
                        incomplete.append(context_prefix + f":{field}_missing")
                alternatives = _ids(context.get("customer_alternatives"))
                if not alternatives:
                    incomplete.append(context_prefix + ":customer_alternatives_missing")
                comparison_ids = _ids(context.get("comparison_observation_ids"))
                if not comparison_ids:
                    incomplete.append(context_prefix + ":comparison_observation_ids_missing")
                elif output_dir is not None:
                    for observation_id in comparison_ids:
                        if observation_id not in observation_ids:
                            invalid.append(context_prefix + ":unverified_comparison_observation:" + observation_id)

        bindings = item.get("model_bindings")
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
            if bindings not in (None, []):
                invalid.append(f"{driver_id or prefix}:company_judgment_cannot_carry_model_bindings")
            bindings = []
        elif (
            layer == "CASH_CONVERSION"
            and str((item.get("cash_normalization_contract") or {}).get("state") or "") != "NORMALIZED"
        ):
            if bindings not in (None, []):
                invalid.append(f"{driver_id or prefix}:non_normalized_cash_cannot_carry_model_bindings")
            bindings = []
        elif not isinstance(bindings, list) or not bindings:
            incomplete.append(f"{driver_id or prefix}:model_bindings_missing")
            bindings = []
        for bind_index, binding in enumerate(bindings):
            bind_prefix = f"{driver_id or prefix}:model_bindings[{bind_index}]"
            if not isinstance(binding, dict):
                invalid.append(bind_prefix + ":not_object")
                continue
            model_id = str(binding.get("model_id") or "").strip()
            if not model_id:
                incomplete.append(bind_prefix + ":model_id_missing")
            elif output_dir is not None and model_id not in model_ids:
                invalid.append(bind_prefix + ":unknown_model_id:" + model_id)
            if not str(binding.get("input_id") or "").strip():
                incomplete.append(bind_prefix + ":input_id_missing")
            if binding.get("treatment") not in BINDING_TREATMENTS:
                invalid.append(bind_prefix + ":treatment_invalid")
            if not str(binding.get("effect") or "").strip():
                incomplete.append(bind_prefix + ":effect_missing")
            linked_decisions = _ids(binding.get("decision_entry_ids"))
            if not linked_decisions:
                incomplete.append(bind_prefix + ":decision_entry_ids_missing")
            elif output_dir is not None:
                for entry_id in linked_decisions:
                    if entry_id not in decision_ids:
                        invalid.append(bind_prefix + ":unknown_decision_entry_id:" + entry_id)

    missing_layers = sorted(LAYERS - covered_layers)
    if missing_layers:
        incomplete.extend("driver_layer_missing:" + layer for layer in missing_layers)

    events = payload.get("allocation_events")
    if not isinstance(events, list):
        invalid.append("allocation_events_not_array")
        events = []
    seen_events: set[str] = set()
    realization_contract_ids: set[str] = set()
    for index, item in enumerate(events):
        prefix = f"allocation_events[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        event_id = str(item.get("event_id") or "").strip()
        if not event_id:
            invalid.append(prefix + ":event_id_missing")
        elif event_id in seen_events:
            invalid.append("duplicate_allocation_event_id:" + event_id)
        seen_events.add(event_id)
        if item.get("event_type") not in ALLOCATION_EVENT_TYPES:
            invalid.append(f"{event_id or prefix}:event_type_invalid")
        if item.get("classification") not in ALLOCATION_CLASSIFICATIONS:
            invalid.append(f"{event_id or prefix}:classification_invalid")
        if not str(item.get("classification_basis") or "").strip():
            incomplete.append(f"{event_id or prefix}:classification_basis_missing")
        if not _valid_date(item.get("decision_date")):
            invalid.append(f"{event_id or prefix}:decision_date_invalid")
        if not str(item.get("realization_window") or "").strip():
            incomplete.append(f"{event_id or prefix}:realization_window_missing")
        cited = _ids(item.get("observation_ids"))
        if not cited:
            incomplete.append(f"{event_id or prefix}:observation_ids_missing")
        elif output_dir is not None:
            for observation_id in cited:
                if observation_id not in observation_ids:
                    invalid.append(f"{event_id or prefix}:unverified_observation:{observation_id}")
        if item.get("classification") == "UNRESOLVED" and not str(item.get("conservative_treatment") or "").strip():
            incomplete.append(f"{event_id or prefix}:unresolved_conservative_treatment_missing")
        realization_prefix = f"{event_id or prefix}:realization_contract"
        realization = item.get("realization_contract")
        if not isinstance(realization, dict):
            incomplete.append(realization_prefix + "_missing")
            if require_allocation_commitment_trace:
                _validate_allocation_commitment_trace(
                    item,
                    event_id=event_id,
                    prefix=prefix,
                    decision_date=item.get("decision_date"),
                    realization={},
                    observation_ids=observation_ids,
                    verify_observations=output_dir is not None,
                    invalid=invalid,
                    incomplete=incomplete,
                )
            continue
        realization_id = str(realization.get("contract_id") or "").strip()
        if not realization_id.startswith("FDBREAL:"):
            invalid.append(realization_prefix + ":contract_id_invalid")
        elif realization_id in realization_contract_ids:
            invalid.append("duplicate_realization_contract_id:" + realization_id)
        realization_contract_ids.add(realization_id)
        if item.get("classification") == "UNRESOLVED" and realization.get("monitoring_only") is not True:
            invalid.append(realization_prefix + ":unresolved_must_be_monitoring_only")
        if not _ids(realization.get("forward_judgment_ids")):
            incomplete.append(realization_prefix + ":forward_judgment_ids_missing")
        early_invalid, early_incomplete = _validate_monitoring_contract(
            realization.get("early_signal"), prefix=realization_prefix + ":early_signal", id_prefix="FDBMON:",
        )
        terminal_invalid, terminal_incomplete = _validate_monitoring_contract(
            realization.get("terminal_outcome"), prefix=realization_prefix + ":terminal_outcome", id_prefix="FDBMON:",
        )
        invalid.extend(early_invalid); incomplete.extend(early_incomplete)
        invalid.extend(terminal_invalid); incomplete.extend(terminal_incomplete)
        for stage in ("early_signal", "terminal_outcome"):
            stage_contract = realization.get(stage)
            if not isinstance(stage_contract, dict):
                continue
            monitoring_id = str(stage_contract.get("contract_id") or "").strip()
            if not monitoring_id:
                continue
            if monitoring_id in monitoring_contract_ids:
                invalid.append("duplicate_monitoring_contract_id:" + monitoring_id)
            monitoring_contract_ids.add(monitoring_id)
        early = realization.get("early_signal") if isinstance(realization.get("early_signal"), dict) else {}
        terminal = realization.get("terminal_outcome") if isinstance(realization.get("terminal_outcome"), dict) else {}
        early_period = early.get("measurement_period") if isinstance(early.get("measurement_period"), dict) else {}
        terminal_period = terminal.get("measurement_period") if isinstance(terminal.get("measurement_period"), dict) else {}
        if _valid_date(early_period.get("end")) and _valid_date(terminal_period.get("start")) and str(early_period.get("end")) >= str(terminal_period.get("start")):
            invalid.append(realization_prefix + ":terminal_period_must_follow_early_signal")
        if require_allocation_commitment_trace:
            _validate_allocation_commitment_trace(
                item,
                event_id=event_id,
                prefix=prefix,
                decision_date=item.get("decision_date"),
                realization=realization,
                observation_ids=observation_ids,
                verify_observations=output_dir is not None,
                invalid=invalid,
                incomplete=incomplete,
            )

    invalid.extend(_validate_company_judgment_lineage(payload, output_dir=output_dir))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "state": state,
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
        "warnings": list(dict.fromkeys(warnings)),
        "covered_layers": sorted(covered_layers),
        "analysis_purpose": analysis_purpose,
    }


def persist_financial_driver_bridge(
    output_dir: str | Path, payload: dict[str, Any]
) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _read_object(output / "financial_driver_bridge_policy.json")
    validation = validate_financial_driver_bridge(
        payload,
        output_dir=output,
        require_allocation_commitment_trace=_policy_requires_allocation_commitment_trace(policy),
        require_cash_normalization_contract=_policy_requires_cash_normalization_contract(policy),
    )
    written = deepcopy(payload)
    written["validation"] = validation
    _write_object(output / "financial_driver_bridge.json", written)
    return {"written": True, "payload": written, "validation": validation}


def evaluate_output_financial_driver_bridge(
    output_dir: str | Path, *, persist: bool = True
) -> dict[str, Any]:
    """Fail closed only for runs that explicitly enable this new contract."""
    output = Path(output_dir)
    policy = _read_object(output / "financial_driver_bridge_policy.json")
    if not policy:
        return {"schema_version": SCHEMA_VERSION, "state": "SKIP", "status": "SKIP", "invalid_findings": [], "incomplete_findings": [], "warnings": []}
    bridge = _read_object(output / "financial_driver_bridge.json")
    if not bridge:
        result = {"state": "INCOMPLETE", "invalid_findings": [], "incomplete_findings": ["financial_driver_bridge_missing"], "warnings": []}
    else:
        result = validate_financial_driver_bridge(
            bridge,
            output_dir=output,
            require_allocation_commitment_trace=_policy_requires_allocation_commitment_trace(policy),
            require_cash_normalization_contract=_policy_requires_cash_normalization_contract(policy),
        )
        if _policy_requires_forward_judgment_binding(policy) and result["state"] != "INVALID":
            thesis = _read_object(output / "thesis_test.json")
            if not thesis:
                result = {
                    **result,
                    "state": "INCOMPLETE",
                    "incomplete_findings": list(dict.fromkeys(
                        list(result.get("incomplete_findings") or []) + ["frozen_thesis_ledger_missing"]
                    )),
                }
            else:
                thesis_validation = _frozen_thesis_validation(output, thesis)
                thesis_state = str(thesis_validation.get("state") or "INVALID")
                if thesis_state not in {"DECISION_READY", "MONITORING"}:
                    key = "invalid_findings" if thesis_state == "INVALID" else "incomplete_findings"
                    state = "INVALID" if thesis_state == "INVALID" else "INCOMPLETE"
                    result = {
                        **result,
                        "state": state,
                        key: list(dict.fromkeys(
                            list(result.get(key) or []) + ["frozen_thesis_ledger_not_validated:" + thesis_state]
                        )),
                    }
                else:
                    binding_findings = _forward_judgment_binding_findings(bridge, thesis)
                    if binding_findings:
                        result = {
                            **result,
                            "state": "INVALID",
                            "invalid_findings": list(dict.fromkeys(
                                list(result.get("invalid_findings") or []) + binding_findings
                            )),
                        }
    result = {"schema_version": SCHEMA_VERSION, "status": result["state"], "enforced": bool(policy.get("enforced")), **result}
    if persist:
        _write_object(output / "financial_driver_bridge_validation.json", result)
    return result
