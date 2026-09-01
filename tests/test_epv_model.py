from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.epv_model import (
    compile_epv_model,
    compute_epv_model,
    validate_epv_model,
    validate_epv_model_input,
)


ROOT = Path(__file__).resolve().parents[1]


def _facts(name: str) -> list[str]:
    return ["OBS:EPV:" + name]


def _range(low: float, high: float, name: str) -> dict:
    return {"range_low": low, "range_high": high, "source_fact_ids": _facts(name)}


def _input() -> dict:
    periods = []
    for year, amount in ((2024, 100.0), (2025, 120.0)):
        periods.append({
            "period_id": f"FY{year}",
            "period_start": f"{year}-01-01",
            "period_end": f"{year}-12-31",
            "metric": "pre_maintenance_enterprise_owner_earnings",
            "basis_kind": "PRE_MAINTENANCE_OWNER_EARNINGS_PRETAX",
            "tax_basis": "PRETAX",
            "amount": amount,
            "working_capital_application": "NOT_REFLECTED",
            "source_fact_ids": _facts(f"FY{year}:BASE"),
            "normalization_adjustments": [
                {
                    "adjustment_id": f"FY{year}:ADD",
                    "category": "NON_RECURRING_EXPENSE",
                    "direction": "ADD",
                    "amount": 10.0,
                    "tax_basis": "PRETAX",
                    "source_fact_ids": _facts(f"FY{year}:ADD"),
                    "economic_reason": "Add back a verified non-recurring expense.",
                },
                {
                    "adjustment_id": f"FY{year}:SUBTRACT",
                    "category": "NON_RECURRING_INCOME",
                    "direction": "SUBTRACT",
                    "amount": 5.0,
                    "tax_basis": "PRETAX",
                    "source_fact_ids": _facts(f"FY{year}:SUBTRACT"),
                    "economic_reason": "Remove verified non-recurring income.",
                },
            ],
        })
    return {
        "schema_version": "epv-model-input.v1",
        "model_id": "EPV:TEST:2025",
        "company_id": "TEST.HK",
        "cutoff_at": "2026-03-31",
        "basis": {
            "value_scope": "enterprise",
            "earnings_claim_scope": "ENTERPRISE_OPERATING",
            "economic_entity": "Listed consolidated operating group",
            "operating_perimeter": "Continuing property-service operations",
            "ordinary_share_claim_scope": "Listed ordinary common shares",
            "currency": "RMB",
            "unit": "RMB_m",
            "as_of": "2025-12-31",
            "operating_cash_treatment": (
                "REQUIRED_OPERATING_CASH_INCLUDED_NON_OPERATING_CASH_EXCLUDED"
            ),
            "operating_cash_component_ids": ["required-operating-cash"],
        },
        "earnings_evidence_status": "AVAILABLE",
        "period_facts": periods,
        "maintenance_capex": {
            "status": "BOUNDED",
            "range_low": 10.0,
            "range_high": 15.0,
            "tax_basis": "AFTER_TAX",
            "source_fact_ids": _facts("MAINTENANCE-CAPEX"),
        },
        "maintenance_working_capital": {
            "status": "BOUNDED",
            "range_low": 5.0,
            "range_high": 10.0,
            "tax_basis": "AFTER_TAX",
            "source_fact_ids": _facts("MAINTENANCE-WC"),
            "source_model_id": "WCM:TEST:2025",
        },
        "tax": {
            "status": "BOUNDED",
            "rate_low": 0.20,
            "rate_high": 0.25,
            "source_fact_ids": _facts("TAX"),
        },
        "capitalization": {
            "status": "BOUNDED",
            "rate_low": 0.10,
            "rate_high": 0.12,
            "source_fact_ids": _facts("CAPITALIZATION"),
        },
        "claims_bridge": {
            "status": "COMPLETE",
            "bridge_mode": "ENTERPRISE_TO_ORDINARY_COMMON",
            "non_operating_components": [
                {
                    "component_id": "recognized-accessible-cash",
                    "kind": "NON_OPERATING_CASH",
                    "range_low": 20.0,
                    "range_high": 25.0,
                    "claim_ids": ["cash.existing_excess_cash_per_share"],
                    "source_fact_ids": _facts("NONOPERATING-CASH"),
                },
                {
                    "component_id": "other-nonoperating-assets",
                    "kind": "OTHER_NON_OPERATING_ASSET",
                    "range_low": 5.0,
                    "range_high": 5.0,
                    "source_fact_ids": _facts("OTHER-ASSETS"),
                },
            ],
            "debt": _range(30.0, 35.0, "DEBT"),
            "preferred_claims": _range(2.0, 2.0, "PREFERRED"),
            "minority_interest": _range(3.0, 3.0, "MINORITY"),
            "other_adjustments": _range(-1.0, 0.0, "OTHER-ADJUSTMENTS"),
            "shares": {"value": 10.0, "source_fact_ids": _facts("SHARES")},
        },
    }


def test_epv_owner_deterministically_normalizes_taxes_capitalizes_and_bridges() -> None:
    result = compute_epv_model(_input())

    assert result["status"] == "COMPARABLE"
    assert result["normalization_bridge"]["period_results"][0] == {
        "period_id": "FY2024",
        "reported_amount": 100.0,
        "adjustments": _input()["period_facts"][0]["normalization_adjustments"],
        "adjustment_additions": 10.0,
        "adjustment_subtractions": 5.0,
        "observed_working_capital_charge_addback": 0.0,
        "pre_maintenance_normalized_amount": 105.0,
    }
    assert result["sustainable_owner_earnings_range"] == {
        "range_low": pytest.approx(53.75),
        "range_high": pytest.approx(85.0),
    }
    assert result["operating_value_range"] == {
        "range_low": pytest.approx(447.9166666667),
        "range_high": pytest.approx(850.0),
    }
    assert result["ordinary_common_equity_range"] == {
        "range_low": pytest.approx(431.9166666667),
        "range_high": pytest.approx(845.0),
    }
    assert result["per_share_range"] == {
        "range_low": pytest.approx(43.1916666667),
        "range_high": pytest.approx(84.5),
    }


def test_canonical_owner_cash_range_propagates_through_epv_without_endpoint_choice() -> None:
    payload = _input()
    for period, bounds in zip(payload["period_facts"], ((80.0, 100.0), (90.0, 130.0))):
        period["basis_kind"] = "CANONICAL_NORMALIZED_OWNER_CASH_AFTER_TAX"
        period["tax_basis"] = "AFTER_TAX"
        period["working_capital_application"] = "ALREADY_NORMALIZED"
        period["amount_range"] = {
            "range_low": bounds[0],
            "range_high": bounds[1],
        }
        period.pop("amount")
        period["normalization_adjustments"] = []
    payload["maintenance_capex"] = {
        "status": "ALREADY_REFLECTED",
        "reason": "Canonical owner cash is after maintenance capex.",
        "source_fact_ids": _facts("OWNER-CASH-AFTER-CAPEX"),
    }
    payload["maintenance_working_capital"] = {
        "status": "ALREADY_REFLECTED",
        "reason": "Canonical owner cash is already normalized by WCM.",
        "source_model_id": "WCM:TEST:2025",
        "source_fact_ids": _facts("OWNER-CASH-AFTER-WC"),
    }
    payload["tax"] = {
        "status": "ALREADY_REFLECTED",
        "reason": "Canonical owner cash is after tax.",
    }

    result = compute_epv_model(payload)

    assert result["normalization_bridge"]["historical_pre_maintenance_range"] == {
        "range_low": 80.0,
        "range_high": 130.0,
    }
    assert result["sustainable_owner_earnings_range"] == {
        "range_low": 80.0,
        "range_high": 130.0,
    }
    assert result["normalization_bridge"]["period_results"][0][
        "pre_maintenance_normalized_range"
    ] == {"range_low": 80.0, "range_high": 100.0}


def test_epv_envelope_recomputes_and_rejects_any_derived_tamper() -> None:
    envelope = compile_epv_model(_input())
    assert validate_epv_model(envelope)["state"] == "VALID"

    changed = deepcopy(envelope)
    changed["result"]["equity_bridge"]["per_share_range"]["range_low"] = 99.0

    assert validate_epv_model(changed) == {
        "schema_version": "epv-model-validation.v1",
        "state": "INVALID",
        "findings": ["result_not_deterministic_projection"],
    }


def test_caller_cannot_submit_normalization_result_or_equity_bridge() -> None:
    for field in ("normalization_bridge", "result", "equity_bridge"):
        payload = _input()
        payload[field] = {"range_low": 1.0, "range_high": 2.0}
        assert "$:unknown_field:" + field in validate_epv_model_input(payload)["findings"]


def test_adjustment_sign_is_explicit_and_negative_amount_is_forbidden() -> None:
    payload = _input()
    adjustment = payload["period_facts"][0]["normalization_adjustments"][0]
    adjustment["amount"] = -10.0

    validation = validate_epv_model_input(payload)

    assert validation["state"] == "INVALID"
    assert "period_facts[0].normalization_adjustments[0]:amount_must_be_nonnegative" in validation["findings"]
    payload = _input()
    payload["period_facts"][0]["normalization_adjustments"][0][
        "direction"
    ] = "SUBTRACT"
    assert (
        "period_facts[0].normalization_adjustments[0]:category_direction_mismatch"
        in validate_epv_model_input(payload)["findings"]
    )


def test_pretax_and_after_tax_identities_cannot_be_mixed_or_taxed_twice() -> None:
    mixed = _input()
    mixed["period_facts"][1]["basis_kind"] = "PRE_MAINTENANCE_OWNER_EARNINGS_AFTER_TAX"
    mixed["period_facts"][1]["tax_basis"] = "AFTER_TAX"
    for adjustment in mixed["period_facts"][1]["normalization_adjustments"]:
        adjustment["tax_basis"] = "AFTER_TAX"
    findings = validate_epv_model_input(mixed)["findings"]
    assert "period_facts:basis_kind_mixed" in findings
    assert "period_facts:tax_basis_mixed" in findings

    after_tax = _input()
    for period in after_tax["period_facts"]:
        period["basis_kind"] = "PRE_MAINTENANCE_OWNER_EARNINGS_AFTER_TAX"
        period["tax_basis"] = "AFTER_TAX"
        for adjustment in period["normalization_adjustments"]:
            adjustment["tax_basis"] = "AFTER_TAX"
    after_tax["maintenance_capex"]["tax_basis"] = "AFTER_TAX"
    after_tax["maintenance_working_capital"]["tax_basis"] = "AFTER_TAX"
    after_tax["tax"] = {
        "status": "ALREADY_REFLECTED",
        "reason": "All period facts and maintenance operands are after tax.",
    }
    assert validate_epv_model_input(after_tax)["state"] == "VALID"
    after_tax["tax"]["rate_low"] = 0.20
    assert "tax:after_tax_rate_would_apply_tax_twice" in validate_epv_model_input(after_tax)["findings"]

    false_tax_shield = _input()
    false_tax_shield["maintenance_capex"]["tax_basis"] = "PRETAX"
    assert "maintenance_capex:tax_basis_mismatch" in validate_epv_model_input(
        false_tax_shield
    )["findings"]


def test_reported_ocf_working_capital_is_replaced_once_not_deducted_twice() -> None:
    payload = _input()
    for period, charge in zip(payload["period_facts"], (15.0, 25.0), strict=True):
        period["basis_kind"] = "REPORTED_OCF_AFTER_TAX"
        period["tax_basis"] = "AFTER_TAX"
        period["working_capital_application"] = "CURRENT_MOVEMENT_REFLECTED"
        period["observed_working_capital_charge"] = charge
        for adjustment in period["normalization_adjustments"]:
            adjustment["tax_basis"] = "AFTER_TAX"
    payload["maintenance_capex"]["tax_basis"] = "AFTER_TAX"
    payload["maintenance_working_capital"]["tax_basis"] = "AFTER_TAX"
    payload["tax"] = {
        "status": "ALREADY_REFLECTED",
        "reason": "Reported operating cash flow is after tax.",
    }

    result = compute_epv_model(payload)

    assert result["normalization_bridge"]["period_results"][0][
        "observed_working_capital_charge_addback"
    ] == 15.0
    assert result["sustainable_owner_earnings_range"] == {
        "range_low": pytest.approx(95.0),
        "range_high": pytest.approx(135.0),
    }
    payload["period_facts"][0]["working_capital_application"] = "NOT_REFLECTED"
    findings = validate_epv_model_input(payload)["findings"]
    assert "period_facts[0]:working_capital_application_basis_mismatch" in findings
    assert "period_facts[0]:observed_working_capital_charge_double_count" in findings


def test_operating_and_nonoperating_cash_component_cannot_be_included_twice() -> None:
    payload = _input()
    payload["basis"]["operating_cash_component_ids"] = ["recognized-accessible-cash"]

    findings = validate_epv_model_input(payload)["findings"]

    assert (
        "claims_bridge:operating_nonoperating_cash_double_count:recognized-accessible-cash"
        in findings
    )


@pytest.mark.parametrize(
    ("path", "unknown_value", "expected_unknown"),
    [
        (
            "maintenance_capex",
            {"status": "UNKNOWN", "reason": "Maintenance capex is not separable."},
            "maintenance_capex",
        ),
        (
            "maintenance_working_capital",
            {"status": "UNKNOWN", "reason": "Steady working capital is not separable."},
            "maintenance_working_capital",
        ),
        (
            "capitalization",
            {"status": "UNKNOWN", "reason": "No evidence-backed capitalization range."},
            "capitalization_rate",
        ),
        (
            "tax",
            {"status": "UNKNOWN", "reason": "A sustainable effective tax range is unavailable."},
            "tax",
        ),
        (
            "claims_bridge",
            {"status": "UNKNOWN", "reason": "Priority claims are not closed."},
            "claims_bridge",
        ),
    ],
)
def test_critical_unknowns_propagate_to_null_company_and_per_share_epv(
    path: str, unknown_value: dict, expected_unknown: str,
) -> None:
    payload = _input()
    payload[path] = unknown_value

    result = compute_epv_model(payload)

    assert result["status"] == "NOT_COMPARABLE"
    assert expected_unknown in result["critical_unknowns"]
    assert result["sustainable_owner_earnings_range"] is None
    assert result["operating_value_range"] is None
    assert result["ordinary_common_equity_range"] is None
    assert result["per_share_range"] is None


def test_missing_maintenance_owner_earnings_is_preserved_without_a_zero_proxy() -> None:
    payload = _input()
    payload["earnings_evidence_status"] = "UNKNOWN"
    payload["earnings_unknown_reason"] = (
        "No comparable period closes operating earnings to maintenance owner cash."
    )
    payload["period_facts"] = []
    payload["maintenance_capex"] = {
        "status": "UNKNOWN",
        "reason": "Maintenance capex is not separable.",
    }
    payload["maintenance_working_capital"] = {
        "status": "UNKNOWN",
        "reason": "Maintenance working capital is not separable.",
    }
    payload["tax"] = {
        "status": "UNKNOWN",
        "reason": "The tax basis cannot be selected before owner earnings are bounded.",
    }

    result = compute_epv_model(payload)

    assert result["status"] == "NOT_COMPARABLE"
    assert result["normalization_bridge"]["historical_pre_maintenance_range"] is None
    assert "maintenance_owner_earnings" in result["critical_unknowns"]
    assert result["sustainable_owner_earnings_range"] is None
    assert result["per_share_range"] is None


def test_exact_operating_inputs_produce_an_exact_operating_value_instead_of_unknown() -> None:
    payload = _input()
    payload["period_facts"][1]["amount"] = payload["period_facts"][0]["amount"]
    payload["maintenance_capex"]["range_high"] = payload["maintenance_capex"]["range_low"]
    payload["maintenance_working_capital"]["range_high"] = payload["maintenance_working_capital"]["range_low"]
    payload["tax"]["rate_high"] = payload["tax"]["rate_low"]
    payload["capitalization"]["rate_high"] = payload["capitalization"]["rate_low"]

    result = compute_epv_model(payload)

    assert result["status"] == "COMPARABLE"
    assert result["critical_unknowns"] == []
    assert result["operating_value_range"] == {
        "range_low": pytest.approx(690.0),
        "range_high": pytest.approx(690.0),
    }


def test_non_positive_maintenance_owner_earnings_yields_zero_epv_not_unknown() -> None:
    payload = _input()
    for period in payload["period_facts"]:
        period["amount"] = 5.0
        period["normalization_adjustments"] = []

    result = compute_epv_model(payload)

    assert result["status"] == "COMPARABLE"
    assert result["critical_unknowns"] == []
    assert result["sustainable_owner_earnings_range"] == {
        "range_low": 0.0,
        "range_high": 0.0,
    }
    assert result["operating_value_range"] == {"range_low": 0.0, "range_high": 0.0}
    assert result["per_share_range"] == {"range_low": 0.0, "range_high": 0.0}
    assert "do not establish positive EPV" in result["economic_conclusion"]["reason"]


def test_epv_schemas_are_closed_at_the_caller_boundary() -> None:
    input_schema = json.loads(
        (ROOT / "schemas/epv_model_input.schema.json").read_text(encoding="utf-8")
    )
    output_schema = json.loads(
        (ROOT / "schemas/epv_model.schema.json").read_text(encoding="utf-8")
    )
    assert input_schema["additionalProperties"] is False
    assert input_schema["$defs"]["periodFact"]["additionalProperties"] is False
    assert output_schema["additionalProperties"] is False
    assert output_schema["properties"]["result"]["additionalProperties"] is False
