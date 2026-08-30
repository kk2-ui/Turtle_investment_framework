from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.working_capital_model import (
    COHORT_ROLES,
    DISCLOSURE_MODES,
    RESULT_SCHEMA_VERSION,
    compute_working_capital_model,
    validate_working_capital_model,
)


ROOT = Path(__file__).resolve().parents[1]


def _normalization(
    method: str,
    *,
    adopted_endpoint: str = "EXACT",
    adopted_value: float | None = 0.0,
    low: float | None = None,
    high: float | None = None,
) -> dict:
    value = {
        "method": method,
        "adopted_endpoint": adopted_endpoint,
        "adopted_value": adopted_value,
        "rationale": "Cohort-specific evidence separates continuing capital from launch and settlement timing.",
        "evidence_ids": ["OBS:WC:NORMALIZATION"],
    }
    if method == "EVIDENCE_BOUNDED" and low is not None and high is not None:
        value["adopted_value"] = None
        value["evidence_ids"] = [
            "OBS:WC:NORMALIZATION:LOW",
            "OBS:WC:NORMALIZATION:HIGH",
        ]
        value["bounded_observations"] = [
            {
                "observation_id": "WC-BOUND-LOW",
                "basis": "PROJECT_COHORT_CASH_CHARGE",
                "period_or_cohort": "project-cohort-low",
                "amount": low,
                "evidence_ids": ["OBS:WC:NORMALIZATION:LOW"],
            },
            {
                "observation_id": "WC-BOUND-HIGH",
                "basis": "PROJECT_COHORT_CASH_CHARGE",
                "period_or_cohort": "project-cohort-high",
                "amount": high,
                "evidence_ids": ["OBS:WC:NORMALIZATION:HIGH"],
            },
        ]
    elif low is not None or high is not None:
        value["recurring_charge_range"] = {"range_low": low, "range_high": high}
    return value


def _cohort(
    *,
    cohort_id: str = "mature-book",
    role: str = "STEADY_ROLLING",
    opening: float = 20.0,
    growth: float = 0.0,
    steady: float = 30.0,
    collections: float = 20.0,
    losses: float = 2.0,
    scope_change: float = 0.0,
    closing: float = 28.0,
    loss_treatment: str = "RECURRING_EXPECTED",
    normalization: dict | None = None,
) -> dict:
    if normalization is None:
        normalization = _normalization(
            "OBSERVED_STEADY_CHARGE", adopted_value=steady + growth - collections
        )
    return {
        "cohort_id": cohort_id,
        "role": role,
        "opening_net_stock": opening,
        "growth_launch_additions": growth,
        "steady_rollover_additions": steady,
        "cash_collections_and_settlements": collections,
        "permanent_losses": losses,
        "noncash_scope_change": scope_change,
        "closing_net_stock": closing,
        "loss_treatment": loss_treatment,
        "normalization": normalization,
        "evidence_ids": [f"OBS:WC:{cohort_id}"],
    }


def _owner_cash_input(
    *,
    basis: str = "REPORTED_OCF",
    amount: float = 100.0,
    maintenance_capex: float = 10.0,
) -> dict:
    return {
        "basis": basis,
        "metric": "reported_operating_cash_flow" if basis == "REPORTED_OCF" else "accrual_earnings",
        "base_metric_amount": amount,
        "maintenance_capex": maintenance_capex,
        "other_owner_adjustments": 0.0,
        "working_capital_application": (
            "ALREADY_REFLECTED_IN_BASE"
            if basis == "REPORTED_OCF"
            else "DEDUCT_STOCK_FLOW_CHARGE"
        ),
        "permanent_loss_application": "INCLUDED_IN_STOCK_FLOW_CHARGE",
        "evidence_ids": ["OBS:OWNER:CASH:BASE"],
    }


def _period(
    cohort: dict,
    *,
    period_id: str = "FY2025",
    start: str = "2025-01-01",
    end: str = "2025-12-31",
    owner_cash_input: dict | None = None,
) -> dict:
    return {
        "period_id": period_id,
        "period_start": start,
        "period_end": end,
        "owner_cash_input": owner_cash_input or _owner_cash_input(),
        "cohorts": [cohort],
    }


def _net_movement_period(
    *,
    opening: float = 20.0,
    closing: float = 30.0,
    observed_charge: float = 10.0,
    owner_cash_input: dict | None = None,
) -> dict:
    return {
        "period_id": "FY2025",
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "disclosure_mode": "NET_MOVEMENT_ONLY",
        "owner_cash_input": owner_cash_input or _owner_cash_input(),
        "net_movement_observation": {
            "opening_net_stock": opening,
            "closing_net_stock": closing,
            "observed_cash_capital_charge": observed_charge,
            "evidence_ids": ["OBS:WC:FY2025:NET-MOVEMENT"],
        },
    }


def _base_model() -> dict:
    return {
        "schema_version": "working-capital-model.v1",
        "model_id": "WCM:PROPERTY-SERVICE:V1",
        "company_id": "TEST-PROPERTY-SERVICE",
        "basis": {
            "economic_entity": "Listed consolidated operating group",
            "operating_perimeter": "Continuing property-service operations",
            "ordinary_share_claim_scope": "Listed ordinary common shares",
            "currency": "RMB",
            "unit": "RMB_m",
            "as_of": "2025-12-31",
        },
        "periods": [_period(_cohort())],
        "valuation_treatment": {
            "reference_period_id": "FY2025",
            "epv_use": "NORMALIZED_OWNER_CASH",
            "epv_working_capital_treatment": "STEADY_RECURRING_ONLY",
            "terminal_route": "CONTINUING",
            "terminal_owner_cash_source": "NORMALIZED_OWNER_CASH",
            "terminal_working_capital_treatment": (
                "STEADY_RECURRING_AND_TERMINAL_GROWTH_ONLY"
            ),
            "stock_release_cohort_ids": [],
        },
    }


def _growth_cohort(*, cohort_id: str = "launch-2025") -> dict:
    return _cohort(
        cohort_id=cohort_id,
        role="GROWTH_LAUNCH",
        opening=0,
        growth=20,
        steady=0,
        collections=0,
        losses=0,
        closing=20,
        loss_treatment="NO_LOSS",
        normalization=_normalization("NOT_APPLICABLE", adopted_value=0),
    )


def _runoff_cohort(*, cohort_id: str = "launch-2025", opening: float = 20) -> dict:
    return _cohort(
        cohort_id=cohort_id,
        role="RUNOFF_OR_SETTLEMENT",
        opening=opening,
        growth=0,
        steady=0,
        collections=opening,
        losses=0,
        closing=0,
        loss_treatment="NO_LOSS",
        normalization=_normalization("NOT_APPLICABLE", adopted_value=0),
    )


def test_schema_is_strict_and_exposes_economic_cohort_roles() -> None:
    schema = json.loads((ROOT / "schemas/working_capital_model.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert set(schema["$defs"]["cohort"]["properties"]["role"]["enum"]) == COHORT_ROLES
    owner_basis = schema["$defs"]["owner_cash_input"]["properties"]["basis"]["enum"]
    assert set(owner_basis) == {"REPORTED_OCF", "ACCRUAL_EARNINGS"}
    disclosure_modes = schema["$defs"]["period"]["properties"]["disclosure_mode"]["enum"]
    assert set(disclosure_modes) == DISCLOSURE_MODES


def test_net_movement_only_closes_observed_charge_without_fabricated_attribution() -> None:
    payload = _base_model()
    payload["periods"] = [_net_movement_period()]

    assert validate_working_capital_model(payload)["state"] == "REVIEWABLE"

    result = compute_working_capital_model(payload)
    period = result["reference_period_result"]
    reconciliation = period["stock_flow_reconciliation"]

    assert period["disclosure_mode"] == "NET_MOVEMENT_ONLY"
    assert period["cohort_results"] == []
    assert reconciliation["opening_net_stock"] == 20
    assert reconciliation["closing_net_stock"] == 30
    assert reconciliation["delta_net_stock"] == 10
    assert reconciliation["observed_cash_capital_movement"] == 10
    assert reconciliation["actual_cash_capital_charge"] == 10
    assert reconciliation["identity_charge_from_net_stock"] == 10
    assert reconciliation["cash_capital_attribution_status"] == "UNKNOWN"
    assert set(reconciliation["charge_by_cohort_role"]) == COHORT_ROLES
    assert all(value is None for value in reconciliation["charge_by_cohort_role"].values())
    assert period["current_owner_cash"] == 90
    assert period["recurring_steady_state_charge_range"] is None
    assert period["adopted_recurring_charge"] is None
    assert period["normalized_owner_cash_range"] is None
    assert period["adopted_normalized_owner_cash"] is None
    assert period["normalization_status"] == "UNKNOWN"
    assert result["economic_conclusion"]["cash_capital_attribution_status"] == "UNKNOWN"
    assert result["economic_conclusion"]["steady_rolling_treatment"] == (
        "UNKNOWN_NOT_INFERRED_FROM_NET_MOVEMENT"
    )


def test_net_movement_only_rejects_broken_identity_and_fabricated_attribution() -> None:
    broken = _base_model()
    broken["periods"] = [_net_movement_period(observed_charge=5)]
    findings = validate_working_capital_model(broken)["findings"]
    assert "FY2025:net_movement_observation:net_movement_identity_not_closed" in findings

    fabricated = _base_model()
    fabricated["periods"] = [_net_movement_period()]
    fabricated["periods"][0]["net_movement_observation"]["growth_launch_charge"] = 6
    findings = validate_working_capital_model(fabricated)["findings"]
    assert (
        "FY2025:net_movement_observation:unknown_field:growth_launch_charge" in findings
    )
    schema = json.loads((ROOT / "schemas/working_capital_model.schema.json").read_text())
    assert schema["$defs"]["net_movement_observation"]["additionalProperties"] is False
    net_condition = schema["$defs"]["period"]["allOf"][0]
    assert net_condition["then"]["required"] == ["net_movement_observation"]
    assert net_condition["then"]["not"]["required"] == ["cohorts"]
    assert net_condition["else"]["required"] == ["cohorts"]

    parallel_cohort = _base_model()
    parallel_cohort["periods"] = [_net_movement_period()]
    parallel_cohort["periods"][0]["cohorts"] = [_growth_cohort()]
    findings = validate_working_capital_model(parallel_cohort)["findings"]
    assert "FY2025:net_movement_mode_cohorts_forbidden" in findings


def test_net_movement_only_supports_negative_net_working_capital_stock() -> None:
    payload = _base_model()
    payload["periods"] = [
        _net_movement_period(opening=-12, closing=-20, observed_charge=-8)
    ]

    assert validate_working_capital_model(payload)["state"] == "REVIEWABLE"
    result = compute_working_capital_model(payload)["reference_period_result"]
    reconciliation = result["stock_flow_reconciliation"]
    assert reconciliation["opening_net_stock"] == -12
    assert reconciliation["closing_net_stock"] == -20
    assert reconciliation["actual_cash_capital_charge"] == -8
    assert reconciliation["cash_capital_attribution_status"] == "UNKNOWN"
    assert result["adopted_recurring_charge"] is None
    schema = json.loads((ROOT / "schemas/working_capital_model.schema.json").read_text())
    observation_properties = schema["$defs"]["net_movement_observation"]["properties"]
    assert "minimum" not in observation_properties["opening_net_stock"]
    assert "minimum" not in observation_properties["closing_net_stock"]


def test_net_movement_only_can_upgrade_to_full_cohort_evidence() -> None:
    net_only = _base_model()
    net_only["periods"] = [_net_movement_period()]
    net_result = compute_working_capital_model(net_only)["reference_period_result"]
    assert net_result["normalization_status"] == "UNKNOWN"

    upgraded = deepcopy(net_only)
    period = upgraded["periods"][0]
    period["disclosure_mode"] = "FULL_GROSS_FLOW"
    period.pop("net_movement_observation")
    period["cohorts"] = [_cohort()]

    upgraded_result = compute_working_capital_model(upgraded)["reference_period_result"]
    assert upgraded_result["disclosure_mode"] == "FULL_GROSS_FLOW"
    assert upgraded_result["normalization_status"] == "BOUNDED"
    assert upgraded_result["adopted_recurring_charge"] == 10
    assert upgraded_result["adopted_normalized_owner_cash"] == 90


def test_stock_flow_identity_and_reported_ocf_owner_cash_are_machine_readable() -> None:
    payload = _base_model()
    assert validate_working_capital_model(payload)["state"] == "REVIEWABLE"

    result = compute_working_capital_model(payload)
    period = result["reference_period_result"]
    cohort = period["cohort_results"][0]
    assert result["schema_version"] == RESULT_SCHEMA_VERSION
    assert result["basis"]["currency"] == "RMB"
    assert result["basis"]["unit"] == "RMB_m"
    assert result["basis"]["as_of"] == "2025-12-31"
    assert cohort["stock_flow_reconciliation"]["delta_net_stock"] == 8.0
    assert cohort["stock_flow_reconciliation"]["actual_cash_capital_charge"] == 10.0
    assert cohort["stock_flow_reconciliation"]["identity_charge_from_net_stock"] == 10.0
    assert period["current_owner_cash"] == 90.0
    assert period["recurring_steady_state_charge_range"] == {
        "range_low": 10.0,
        "range_high": 10.0,
    }
    assert period["adopted_recurring_endpoint"] == "EXACT"
    assert period["normalized_owner_cash_range"] == {
        "range_low": 90.0,
        "range_high": 90.0,
    }
    assert result["economic_conclusion"]["normal_owner_cash_status"] == "BOUNDED"
    assert not any(result["double_count_flags"].values())


def test_same_absorption_is_normalized_differently_for_growth_and_steady_cohorts() -> None:
    growth = _base_model()
    growth["periods"][0] = _period(
        _growth_cohort(), owner_cash_input=_owner_cash_input(amount=80, maintenance_capex=0)
    )
    growth_result = compute_working_capital_model(growth)["reference_period_result"]

    steady = _base_model()
    steady["periods"][0] = _period(
        _cohort(
            opening=0,
            growth=0,
            steady=20,
            collections=0,
            losses=0,
            closing=20,
            loss_treatment="NO_LOSS",
            normalization=_normalization("OBSERVED_STEADY_CHARGE", adopted_value=20),
        ),
        owner_cash_input=_owner_cash_input(amount=80, maintenance_capex=0),
    )
    steady_result = compute_working_capital_model(steady)["reference_period_result"]

    assert growth_result["stock_flow_reconciliation"]["actual_cash_capital_charge"] == 20
    assert steady_result["stock_flow_reconciliation"]["actual_cash_capital_charge"] == 20
    assert growth_result["adopted_normalized_owner_cash"] == 100
    assert steady_result["adopted_normalized_owner_cash"] == 80


def test_growth_launch_followed_by_full_collection_does_not_create_permanent_haircut() -> None:
    payload = _base_model()
    payload["basis"]["as_of"] = "2026-12-31"
    payload["periods"] = [
        _period(
            _growth_cohort(),
            owner_cash_input=_owner_cash_input(amount=80, maintenance_capex=0),
        ),
        _period(
            _runoff_cohort(),
            period_id="FY2026",
            start="2026-01-01",
            end="2026-12-31",
            owner_cash_input=_owner_cash_input(amount=120, maintenance_capex=0),
        ),
    ]
    payload["valuation_treatment"]["reference_period_id"] = "FY2026"

    result = compute_working_capital_model(payload)
    first, second = result["period_results"]
    assert first["current_owner_cash"] == 80
    assert second["current_owner_cash"] == 120
    assert first["adopted_normalized_owner_cash"] == 100
    assert second["adopted_normalized_owner_cash"] == 100
    assert second["stock_flow_reconciliation"]["actual_cash_capital_charge"] == -20


def test_batch_collection_release_enters_current_cash_but_not_normalized_cash() -> None:
    payload = _base_model()
    payload["periods"][0] = _period(
        _runoff_cohort(cohort_id="old-batch"),
        owner_cash_input=_owner_cash_input(amount=120, maintenance_capex=0),
    )
    result = compute_working_capital_model(payload)["reference_period_result"]
    assert result["current_owner_cash"] == 120
    assert result["adopted_normalized_owner_cash"] == 100
    assert result["adopted_recurring_charge"] == 0


def test_recurring_loss_and_one_off_writeoff_have_different_future_treatment() -> None:
    recurring = _base_model()
    recurring_result = compute_working_capital_model(recurring)["reference_period_result"]

    one_off = _base_model()
    cohort = one_off["periods"][0]["cohorts"][0]
    cohort["loss_treatment"] = "ONE_OFF_PERMANENT"
    cohort["normalization"]["adopted_value"] = 8
    one_off_result = compute_working_capital_model(one_off)["reference_period_result"]

    assert recurring_result["adopted_recurring_charge"] == 10
    assert one_off_result["adopted_recurring_charge"] == 8
    assert recurring_result["adopted_normalized_owner_cash"] == 90
    assert one_off_result["adopted_normalized_owner_cash"] == 92


def test_net_stock_impairment_rejects_second_permanent_loss_deduction() -> None:
    payload = _base_model()
    payload["periods"][0]["owner_cash_input"]["permanent_loss_application"] = "DEDUCT_AGAIN"
    findings = validate_working_capital_model(payload)["findings"]
    assert "FY2025:owner_cash_input:permanent_loss_deducted_twice" in findings


def test_reported_ocf_rejects_second_working_capital_deduction() -> None:
    payload = _base_model()
    payload["periods"][0]["owner_cash_input"]["working_capital_application"] = (
        "DEDUCT_STOCK_FLOW_CHARGE"
    )
    findings = validate_working_capital_model(payload)["findings"]
    assert "FY2025:owner_cash_input:reported_ocf_working_capital_deducted_twice" in findings


def test_accrual_earnings_requires_and_applies_stock_flow_bridge() -> None:
    missing = _base_model()
    missing["periods"][0]["owner_cash_input"] = _owner_cash_input(
        basis="ACCRUAL_EARNINGS", amount=110
    )
    missing["periods"][0]["owner_cash_input"]["working_capital_application"] = (
        "ALREADY_REFLECTED_IN_BASE"
    )
    findings = validate_working_capital_model(missing)["findings"]
    assert "FY2025:owner_cash_input:accrual_earnings_missing_stock_flow_charge" in findings

    correct = _base_model()
    correct["periods"][0]["owner_cash_input"] = _owner_cash_input(
        basis="ACCRUAL_EARNINGS", amount=110
    )
    result = compute_working_capital_model(correct)["reference_period_result"]
    assert result["current_owner_cash"] == 90
    assert result["adopted_normalized_owner_cash"] == 90


def test_continuing_terminal_cannot_release_all_working_capital_stock() -> None:
    payload = _base_model()
    payload["valuation_treatment"]["stock_release_cohort_ids"] = ["mature-book"]
    findings = validate_working_capital_model(payload)["findings"]
    assert "valuation_treatment:continuing_terminal_stock_release_forbidden" in findings

    payload = _base_model()
    payload["valuation_treatment"]["terminal_working_capital_treatment"] = "STOCK_RELEASE_ONLY"
    findings = validate_working_capital_model(payload)["findings"]
    assert (
        "valuation_treatment:continuing_terminal_cannot_perpetuate_current_absorption" in findings
    )


def test_runoff_route_cannot_capitalize_continuing_epv_for_same_perimeter() -> None:
    payload = _base_model()
    payload["periods"][0] = _period(_runoff_cohort())
    payload["valuation_treatment"].update(
        {
            "terminal_route": "RUNOFF_OR_LIQUIDATION",
            "terminal_owner_cash_source": "STOCK_RELEASE_ONLY",
            "terminal_working_capital_treatment": "STOCK_RELEASE_ONLY",
            "stock_release_cohort_ids": ["launch-2025"],
        }
    )
    findings = validate_working_capital_model(payload)["findings"]
    assert "valuation_treatment:runoff_and_continuing_epv_mutually_exclusive" in findings

    payload["valuation_treatment"].update(
        {"epv_use": "NOT_USED", "epv_working_capital_treatment": "NOT_APPLICABLE"}
    )
    result = compute_working_capital_model(payload)
    assert result["economic_conclusion"]["terminal_treatment"] == (
        "STOCK_RELEASE_ONLY_WITHOUT_CONTINUING_EPV"
    )


def test_unresolved_attribution_stays_unknown_and_arbitrary_midpoint_is_rejected() -> None:
    midpoint = _base_model()
    cohort = midpoint["periods"][0]["cohorts"][0]
    cohort["role"] = "UNATTRIBUTED"
    cohort["normalization"] = _normalization(
        "EVIDENCE_BOUNDED", adopted_endpoint="LOW", adopted_value=5, low=0, high=10
    )
    cohort["normalization"]["adopted_value"] = 5
    findings = validate_working_capital_model(midpoint)["findings"]
    assert "FY2025:mature-book:normalization:manual_adopted_value_forbidden" in findings

    unknown = _base_model()
    cohort = unknown["periods"][0]["cohorts"][0]
    cohort["role"] = "UNATTRIBUTED"
    cohort["normalization"] = _normalization(
        "UNKNOWN", adopted_endpoint="UNKNOWN", adopted_value=None
    )
    result = compute_working_capital_model(unknown)
    period = result["reference_period_result"]
    assert period["recurring_steady_state_charge_range"] is None
    assert period["normalized_owner_cash_range"] is None
    assert period["adopted_normalized_owner_cash"] is None
    assert result["economic_conclusion"]["normal_owner_cash_status"] == "UNKNOWN"


def test_bounded_uncertainty_adopts_only_a_disclosed_endpoint() -> None:
    payload = _base_model()
    cohort = payload["periods"][0]["cohorts"][0]
    cohort["role"] = "UNATTRIBUTED"
    cohort["normalization"] = _normalization(
        "EVIDENCE_BOUNDED", adopted_endpoint="HIGH", adopted_value=12, low=4, high=12
    )
    result = compute_working_capital_model(payload)["reference_period_result"]
    assert result["recurring_steady_state_charge_range"] == {
        "range_low": 4,
        "range_high": 12,
    }
    assert result["adopted_recurring_charge"] == 12
    assert result["adopted_recurring_endpoint"] == "HIGH"
    assert result["normalized_owner_cash_range"] == {
        "range_low": 88,
        "range_high": 96,
    }
    assert result["adopted_normalized_owner_cash"] == 88


def test_unattributed_cohort_cannot_disguise_arbitrary_point_as_exact_range() -> None:
    payload = _base_model()
    cohort = payload["periods"][0]["cohorts"][0]
    cohort["role"] = "UNATTRIBUTED"
    cohort["normalization"] = _normalization(
        "EVIDENCE_BOUNDED", adopted_endpoint="EXACT", adopted_value=5, low=5, high=5
    )

    validation = validate_working_capital_model(payload)

    assert validation["state"] == "INVALID"
    assert "FY2025:mature-book:normalization:unattributed_exact_endpoint_forbidden" in (
        validation["findings"]
    )
    assert "FY2025:mature-book:normalization:unattributed_degenerate_range_forbidden" in (
        validation["findings"]
    )


def test_single_year_half_absorption_cannot_masquerade_as_an_evidence_bound() -> None:
    payload = _base_model()
    cohort = payload["periods"][0]["cohorts"][0]
    cohort["role"] = "UNATTRIBUTED"
    cohort["steady_rollover_additions"] = 275.426
    cohort["cash_collections_and_settlements"] = 0
    cohort["closing_net_stock"] = 293.426
    cohort["normalization"] = {
        "method": "EVIDENCE_BOUNDED",
        "recurring_charge_range": {
            "range_low": 137.713,
            "range_high": 275.426,
        },
        "adopted_endpoint": "LOW",
        "adopted_value": 137.713,
        "rationale": "Half of the single-year absorption is assumed to recur.",
        "evidence_ids": ["OBS:WC:FY2025-TOTAL"],
    }

    findings = validate_working_capital_model(payload)["findings"]

    assert "FY2025:mature-book:normalization:manual_recurring_charge_range_forbidden" in findings
    assert "FY2025:mature-book:normalization:manual_adopted_value_forbidden" in findings
    assert "FY2025:mature-book:normalization:bounded_observations_require_two_or_more" in findings


def test_unattributed_schema_forbids_exact_endpoint_even_before_custom_validation() -> None:
    schema = json.loads((ROOT / "schemas/working_capital_model.schema.json").read_text())
    unattributed_rule = schema["$defs"]["cohort"]["allOf"][1]["then"][
        "properties"
    ]["normalization"]["allOf"][2]

    assert unattributed_rule["then"]["properties"]["adopted_endpoint"]["enum"] == [
        "LOW",
        "HIGH",
    ]


def test_cohort_composition_changes_normalized_cash_when_aggregate_delta_is_constant() -> None:
    growth = _base_model()
    growth["periods"][0] = _period(
        _growth_cohort(), owner_cash_input=_owner_cash_input(amount=75, maintenance_capex=0)
    )
    steady = deepcopy(growth)
    cohort = steady["periods"][0]["cohorts"][0]
    cohort["role"] = "STEADY_ROLLING"
    cohort["growth_launch_additions"] = 0
    cohort["steady_rollover_additions"] = 20
    cohort["normalization"] = _normalization(
        "OBSERVED_STEADY_CHARGE", adopted_value=20
    )

    growth_result = compute_working_capital_model(growth)["reference_period_result"]
    steady_result = compute_working_capital_model(steady)["reference_period_result"]
    assert growth_result["cohort_results"][0]["stock_flow_reconciliation"]["delta_net_stock"] == 20
    assert steady_result["cohort_results"][0]["stock_flow_reconciliation"]["delta_net_stock"] == 20
    assert growth_result["adopted_normalized_owner_cash"] == 95
    assert steady_result["adopted_normalized_owner_cash"] == 75


def test_noncash_scope_transfer_changes_stock_delta_but_not_cash_charge() -> None:
    baseline = _base_model()
    transferred = _base_model()
    transferred_cohort = transferred["periods"][0]["cohorts"][0]
    transferred_cohort["noncash_scope_change"] = 5
    transferred_cohort["closing_net_stock"] = 33

    baseline_result = compute_working_capital_model(baseline)["reference_period_result"]
    transfer_result = compute_working_capital_model(transferred)["reference_period_result"]
    baseline_bridge = baseline_result["cohort_results"][0]["stock_flow_reconciliation"]
    transfer_bridge = transfer_result["cohort_results"][0]["stock_flow_reconciliation"]
    assert baseline_bridge["delta_net_stock"] == 8
    assert transfer_bridge["delta_net_stock"] == 13
    assert baseline_bridge["actual_cash_capital_charge"] == 10
    assert transfer_bridge["actual_cash_capital_charge"] == 10
    assert transfer_bridge["identity_charge_from_net_stock"] == 10


def test_broken_stock_flow_identity_fails_before_owner_cash_is_computed() -> None:
    payload = _base_model()
    payload["periods"][0]["cohorts"][0]["closing_net_stock"] = 29
    findings = validate_working_capital_model(payload)["findings"]
    assert "FY2025:mature-book:stock_flow_identity_not_closed" in findings
    with pytest.raises(ValueError, match="working_capital_model_invalid"):
        compute_working_capital_model(payload)
