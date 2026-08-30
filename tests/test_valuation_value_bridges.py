from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.valuation_value_bridges import (
    compile_valuation_value_bridges,
    validate_valuation_value_bridge_input,
    validate_valuation_value_bridges,
)
from scripts.valuation_archetypes import resolve_valuation_archetype


ROOT = Path(__file__).resolve().parents[1]


def _facts(*fact_ids: str) -> list[dict[str, str]]:
    return [{"fact_id": fact_id, "status": "VERIFIED"} for fact_id in fact_ids]


def _role_bindings(component_type: str, source_fact_id: str) -> list[dict[str, object]]:
    card = resolve_valuation_archetype("property_service", "v1")
    spec = next(
        item for item in card["required_component_specs"]
        if item["component_type"] == component_type
    )
    return [
        {"role": role, "source_fact_ids": [source_fact_id]}
        for role in spec["required_evidence_roles"]
    ]


def _cash_input() -> dict:
    fact_ids = ["F:ID", "F:CASH", "F:P1", "F:P2", "F:P3", "F:E1", "F:E2", "F:E3", "F:FUTURE", "F:AR", "F:CONTINUITY"]
    periods = []
    for year, special, dividend, period_fact, event_fact in (
        ("2023", 7, 10, "F:P1", "F:E1"),
        ("2024", 14, 20, "F:P2", "F:E2"),
        ("2025", 21, 30, "F:P3", "F:E3"),
    ):
        periods.append(
            {
                "period_id": year,
                "period_start": f"{year}-01-01",
                "period_end": f"{year}-12-31",
                "opening_position_as_of": f"{year}-01-01",
                "comparable": True,
                "opening_existing_excess_cash": 70,
                "retained_cash_generated": 50,
                "ordinary_dividend": dividend,
                "extraordinary_events": [
                    {
                        "event_type": "special_dividend",
                        "event_date": f"{year}-06-30",
                        "observed_at": f"{year}-12-31",
                        "amount": special,
                        "funding_source_identity": "existing_excess_cash",
                        "source_fact_ids": [event_fact],
                    }
                ],
                "source_fact_ids": [period_fact],
            }
        )
    return {
        "schema_version": "cash-accessibility-input.v1",
        "model_id": "CASH:BRIDGE-TEST",
        "company_id": "TEST.HK",
        "cutoff_at": "2025-12-31",
        "position_as_of": "2025-12-31",
        "currency": "RMB",
        "unit": "million",
        "identity_source_fact_ids": ["F:ID"],
        "verified_facts": _facts(*fact_ids),
        "entity_cash_rows": [
            {
                "entity_id": "parent",
                "entity_kind": "parent",
                "gross_cash": 100,
                "restricted_or_regulatory_cash": 10,
                "operating_liquidity_requirement": 20,
                "ordinary_share_economic_interest": 1,
                "transfer_tax_friction_rate": 0,
                "source_fact_ids": ["F:CASH"],
            }
        ],
        "realization_periods": periods,
        "realization_applicability": {
            "existing_excess_cash": {
                "cash_control_continuity": True,
                "upstream_mechanism_continuity": True,
                "extraordinary_distribution_policy_continuity": True,
                "capital_need_continuity": True,
                "source_fact_ids": ["F:CONTINUITY"],
            },
            "future_retained_cash": {
                "cash_control_continuity": True,
                "ordinary_distribution_policy_continuity": True,
                "capital_need_continuity": True,
                "source_fact_ids": ["F:CONTINUITY"],
            },
        },
        "future_retained_cash": {
            "projected_amount": 80,
            "legal_upper_bound_rate": 0.8,
            "source_fact_ids": ["F:FUTURE"],
        },
        "related_party_receivables": [
            {
                "receivable_id": "AR:1",
                "gross_amount": 100,
                "ecl_allowance": 10,
                "post_position_collections": 20,
                "aging_bucket": "current",
                "recovery_mechanism_id": "AR:STANDARD",
                "recovery_cohorts": [],
                "prospective_applicability": {
                    "same_recovery_mechanism": None,
                    "same_counterparty_control": None,
                    "same_settlement_terms": None,
                    "source_fact_ids": [],
                },
                "source_fact_ids": ["F:AR"],
            }
        ],
        "valuation_destinations": [
            {"component_id": "legal_cash_accessibility", "valuation_destination": "legal_accessibility_ceiling_only"},
            {"component_id": "existing_excess_cash_realization", "valuation_destination": "equity_value_existing_excess_cash"},
            {"component_id": "future_retained_cash_realization", "valuation_destination": "operating_value_future_retained_cash"},
            {"component_id": "related_party_receivable_realization", "valuation_destination": "equity_value_related_party_receivable"},
        ],
    }


def _replacement_input() -> dict:
    def covered_component(component_id: str, component_type: str) -> dict:
        item = {
            "component_id": component_id,
            "component_type": component_type,
            "economic_function": "Close the synthetic full-scope replacement fixture.",
            "estimate_status": "BOUNDED",
            "calculation": {
                "method": "DIRECT_RANGE",
                "output_unit": "RMB_m",
                "inputs": [{
                    "input_id": component_id + "-cost",
                    "metric": component_id + "_replacement_cost",
                    "range_low": 0,
                    "range_high": 0,
                    "unit": "RMB_m",
                    "basis": "Synthetic company-specific zero-cost boundary for bridge arithmetic.",
                    "evidence_ids": ["OBS:" + component_id.upper()],
                    "parameter_scope": "COMPANY_SPECIFIC",
                }],
            },
            "recognition": {
                "status": "RECOGNIZED",
                "method": "FULL",
                "reason": "The synthetic bridge fixture explicitly bounds this component.",
            },
            "evidence_role_bindings": _role_bindings(
                component_type, "OBS:" + component_id.upper()
            ),
        }
        if component_type == "PROJECT_STARTUP_WORKING_CAPITAL":
            item["double_count_treatment"] = {
                "balance_sheet_working_capital": "NOT_INCLUDED",
                "epv_maintenance_need": "NOT_INCLUDED",
                "explanation": "The synthetic zero boundary is not present in either destination.",
            }
        return item

    return {
        "schema_version": "replacement-value-model.v1",
        "model_id": "RVM:BRIDGE-TEST",
        "company_id": "TEST.HK",
        "model_context": {
            "purpose": "COMPANY_ANALYSIS",
            "valuation_archetype_id": "property_service",
            "valuation_archetype_version": "v1",
            "parameter_transfer_policy": "COMPANY_SPECIFIC_EVIDENCE_ONLY",
        },
        "basis": {
            "valuation_basis": "GOING_CONCERN_REPLACEMENT",
            "value_scope": "enterprise",
            "economic_entity": "Listed consolidated operating group",
            "operating_perimeter": "Continuing property-service operations",
            "ordinary_share_claim_scope": "Listed ordinary common shares",
            "currency": "RMB",
            "unit": "RMB_m",
            "as_of": "2025-12-31",
        },
        "components": [
            {
                "component_id": "customer-book",
                "component_type": "CUSTOMER_RELATIONSHIP",
                "economic_function": "Rebuild the retained customer and contract base.",
                "estimate_status": "BOUNDED",
                "calculation": {
                    "method": "DIRECT_RANGE",
                    "output_unit": "RMB_m",
                    "inputs": [
                        {
                            "input_id": "customer-cost",
                            "metric": "incremental_customer_rebuild_cost",
                            "range_low": 100,
                            "range_high": 120,
                            "unit": "RMB_m",
                            "basis": "Verified company-specific acquisition and retention evidence.",
                            "evidence_ids": ["OBS:CUSTOMER-COST"],
                            "parameter_scope": "COMPANY_SPECIFIC",
                        }
                    ],
                },
                "recognition": {
                    "status": "RECOGNIZED",
                    "method": "FULL",
                    "reason": "The observed rebuild range is recognized.",
                },
                "evidence_role_bindings": _role_bindings(
                    "CUSTOMER_RELATIONSHIP", "OBS:CUSTOMER-COST"
                ),
            },
            covered_component("regional-organization", "REGIONAL_OPERATING_ORGANIZATION"),
            covered_component("acquisition-channel", "CUSTOMER_ACQUISITION_CHANNEL"),
            covered_component("delivery-record", "FULFILLMENT_OR_PROJECT_TRACK_RECORD"),
            covered_component("startup-working-capital", "PROJECT_STARTUP_WORKING_CAPITAL"),
            covered_component("other-functional-assets", "OTHER_FUNCTIONAL_ASSET"),
        ],
        "claims_bridge": {
            "non_operating_assets": {"range_low": 20, "range_high": 20},
            "debt": {"range_low": 40, "range_high": 40},
            "minority_interest": {"range_low": 0, "range_high": 0},
            "other_priority_claims": {"range_low": 0, "range_high": 0},
            "other_adjustments": {"range_low": 0, "range_high": 0},
            "shares_outstanding": 100,
            "source_fact_ids": [
                "OBS:CLAIMS:NON_OPERATING_ASSETS",
                "OBS:CLAIMS:DEBT",
                "OBS:CLAIMS:MINORITY_INTEREST",
                "OBS:CLAIMS:OTHER_PRIORITY_CLAIMS",
                "OBS:CLAIMS:OTHER_ADJUSTMENTS",
                "OBS:CLAIMS:SHARES",
            ],
        },
        "liquidation_floor_reference": {
            "status": "AVAILABLE",
            "model_id": "NAV:FLOOR",
            "value_scope": "ordinary_common_equity_per_share",
            "currency": "RMB",
            "as_of": "2025-12-31",
            "per_share_low": 0.30,
            "per_share_high": 0.40,
            "use": "SEPARATE_STRESS_REFERENCE_NEVER_ADD",
            "source_fact_ids": [
                "CALC:NAV:FLOOR:LOW",
                "CALC:NAV:FLOOR:HIGH",
            ],
        },
        "epv_cross_check": {
            "status": "COMPARABLE",
            "model_id": "EPV:NORMALIZED",
            "economic_entity": "Listed consolidated operating group",
            "operating_perimeter": "Continuing property-service operations",
            "ordinary_share_claim_scope": "Listed ordinary common shares",
            "value_scope": "ordinary_common_equity",
            "currency": "RMB",
            "unit": "RMB_m",
            "as_of": "2025-12-31",
            "equity_value_low": 90,
            "equity_value_high": 110,
            "shares_outstanding": 100,
            "per_share_low": 0.90,
            "per_share_high": 1.10,
            "synthesis_rule": "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE",
            "source_fact_ids": [
                "CALC:EPV:EQUITY:LOW",
                "CALC:EPV:EQUITY:HIGH",
                "OBS:CLAIMS:SHARES",
                "CALC:EPV:PER_SHARE:LOW",
                "CALC:EPV:PER_SHARE:HIGH",
            ],
        },
    }


def _working_capital_input(*, unknown: bool = False) -> dict:
    normalization = {
        "method": "UNKNOWN" if unknown else "OBSERVED_STEADY_CHARGE",
        "adopted_endpoint": "UNKNOWN" if unknown else "EXACT",
        "adopted_value": None if unknown else 10,
        "rationale": (
            "Attribution remains unresolved."
            if unknown
            else "Observed mature-cohort rolling capital is the steady-state charge."
        ),
        "evidence_ids": ["OBS:WC:NORMALIZATION"],
    }
    return {
        "schema_version": "working-capital-model.v1",
        "model_id": "WCM:BRIDGE-TEST",
        "company_id": "TEST.HK",
        "basis": {
            "economic_entity": "Listed consolidated operating group",
            "operating_perimeter": "Continuing property-service operations",
            "ordinary_share_claim_scope": "Listed ordinary common shares",
            "currency": "RMB",
            "unit": "RMB_m",
            "as_of": "2025-12-31",
        },
        "periods": [
            {
                "period_id": "FY2025",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "owner_cash_input": {
                    "basis": "REPORTED_OCF",
                    "metric": "reported_operating_cash_flow",
                    "base_metric_amount": 100,
                    "maintenance_capex": 10,
                    "other_owner_adjustments": 0,
                    "working_capital_application": "ALREADY_REFLECTED_IN_BASE",
                    "permanent_loss_application": "INCLUDED_IN_STOCK_FLOW_CHARGE",
                    "evidence_ids": ["OBS:OWNER:CASH:BASE"],
                },
                "cohorts": [
                    {
                        "cohort_id": "mature-book",
                        "role": "UNATTRIBUTED" if unknown else "STEADY_ROLLING",
                        "opening_net_stock": 20,
                        "growth_launch_additions": 0,
                        "steady_rollover_additions": 30,
                        "cash_collections_and_settlements": 20,
                        "permanent_losses": 2,
                        "noncash_scope_change": 0,
                        "closing_net_stock": 28,
                        "loss_treatment": "RECURRING_EXPECTED",
                        "normalization": normalization,
                        "evidence_ids": ["OBS:WC:MATURE"],
                    }
                ],
            }
        ],
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


def _ordinary_distribution_input() -> dict:
    fact_ids = ["OBS:EARNINGS", "OBS:DISTRIBUTION", "OBS:FRICTION"]
    return {
        "schema_version": "ordinary-distribution-input.v1",
        "model_id": "DIST:02669:2025",
        "company_id": "02669.HK",
        "cutoff_at": "2026-08-11",
        "position_as_of": "2025-12-31",
        "currency": "RMB",
        "unit": "RMB_m",
        "verified_facts": [
            {"fact_id": fact_id, "status": "VERIFIED"} for fact_id in fact_ids
        ],
        "input_fact_ids": fact_ids,
        "normalized_ordinary_share_operating_earnings": 896.9796304399521,
        "ordinary_distribution_rate": 0.35,
        "distribution_tax_and_collection_friction_rate": 0.1027,
        "fixed_collection_cost": 3.28396046,
    }


def _bridge_input(
    *,
    cash: bool = True,
    replacement: bool = True,
    working_capital: bool = False,
    ordinary_distribution: bool = False,
) -> dict:
    payload: dict = {"schema_version": "valuation-value-bridges-input.v1"}
    if cash:
        payload["cash_accessibility"] = {
            "model_input": _cash_input(),
            "valuation_context": {
                "company_id": "TEST.HK",
                "operating_model_id": "dcf.fcff.base",
                "position_as_of": "2025-12-31",
                "ordinary_share_claim_scope": "Listed ordinary common shares",
                "valuation_currency": "HKD",
                "fx_source_per_valuation_currency": 2,
                "shares": 10,
            },
        }
    if replacement:
        payload["replacement_value"] = {"model_input": _replacement_input()}
    if working_capital:
        payload["working_capital"] = {"model_input": _working_capital_input()}
    if ordinary_distribution:
        payload["ordinary_distribution"] = {
            "model_input": _ordinary_distribution_input()
        }
    return payload


def test_schema_closes_input_output_and_numeric_claims() -> None:
    schema = json.loads((ROOT / "schemas/valuation_value_bridges.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["bridgeInput"]["additionalProperties"] is False
    assert schema["$defs"]["numericClaim"]["additionalProperties"] is False
    assert schema["$defs"]["readerSlot"]["additionalProperties"] is False


def test_cash_bridge_computes_per_share_recognition_and_future_retention_rate() -> None:
    compiled = compile_valuation_value_bridges(_bridge_input(replacement=False))
    cash = compiled["valuation_projection"]["cash_accessibility"]

    assert cash["existing_excess_cash"]["per_share_range"] == {
        "low": pytest.approx(0.35),
        "base": pytest.approx(0.70),
        "high": pytest.approx(1.05),
    }
    assert cash["existing_excess_cash"]["adopted_per_share"] == pytest.approx(0.70)
    assert cash["related_party_receivables"]["adopted_per_share"] == pytest.approx(1.0)
    assert cash["future_retained_cash"]["realization_rate_range"] == {
        "low": 0.2,
        "base": 0.4,
        "high": 0.6,
    }
    assert cash["future_retained_cash"]["adopted_realization_rate"] == 0.4
    assert validate_valuation_value_bridges(compiled)["state"] == "VALID"


def test_replacement_projection_preserves_per_share_scope_and_epv_cross_check() -> None:
    compiled = compile_valuation_value_bridges(_bridge_input(cash=False))
    replacement = compiled["valuation_projection"]["replacement_value"]

    assert replacement["per_share_range"] == {"range_low": 0.8, "range_high": 1.0}
    assert replacement["epv_cross_check"]["relationship"] == "OVERLAPS"
    assert replacement["epv_cross_check"]["synthesis_rule"] == (
        "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE"
    )
    assert replacement["joint_protection_price_ceiling"] == {
        "value": 0.8,
        "currency": "RMB",
        "scope": "Listed ordinary common shares",
        "as_of": "2025-12-31",
        "meaning": "highest_price_covered_by_both_independent_lower_bounds",
        "reason": "",
    }
    assert replacement["basis"]["ordinary_share_claim_scope"] == "Listed ordinary common shares"


def test_models_are_optional_but_at_least_one_valid_model_is_required() -> None:
    assert validate_valuation_value_bridge_input(_bridge_input(cash=True, replacement=False))["state"] == "VALID"
    assert validate_valuation_value_bridge_input(_bridge_input(cash=False, replacement=True))["state"] == "VALID"
    assert validate_valuation_value_bridge_input(
        _bridge_input(cash=False, replacement=False, working_capital=True)
    )["state"] == "VALID"
    assert validate_valuation_value_bridge_input(
        _bridge_input(
            cash=False,
            replacement=False,
            ordinary_distribution=True,
        )
    )["state"] == "VALID"
    empty = {"schema_version": "valuation-value-bridges-input.v1"}
    assert "at_least_one_model_required" in validate_valuation_value_bridge_input(empty)["findings"]

    unknown = _bridge_input(cash=False, replacement=True)
    unknown["free_value"] = 99
    assert "$:unknown_field:free_value" in validate_valuation_value_bridge_input(unknown)["findings"]


@pytest.mark.parametrize(
    ("field", "mutate"),
    [
        (
            "result",
            lambda value: value["cash_accessibility"]["existing_excess_cash_realization"].__setitem__("adopted_value", 999),
        ),
        (
            "valuation_projection",
            lambda value: value["cash_accessibility"]["existing_excess_cash"].__setitem__("adopted_per_share", 999),
        ),
        ("reader_conclusions", lambda value: value.append("自由重抄一个未经模型支持的结论。")),
        ("numeric_claims", lambda value: value[0].__setitem__("selected_value", 999)),
        ("reader_slots", lambda value: value.append({"sentence": "自由重抄。"})),
    ],
)
def test_output_validation_recomputes_and_rejects_every_tampered_projection(field: str, mutate) -> None:
    compiled = compile_valuation_value_bridges(_bridge_input())
    changed = deepcopy(compiled)
    mutate(changed[field])

    validation = validate_valuation_value_bridges(changed)

    assert validation["state"] == "INVALID"
    assert field + "_not_deterministic_projection" in validation["findings"]


def test_combined_reader_and_numeric_outputs_are_model_derived_not_audit_language() -> None:
    compiled = compile_valuation_value_bridges(_bridge_input())
    text = "\n".join(slot["sentence"] for slot in compiled["reader_slots"])
    metrics = {claim["metric"] for claim in compiled["numeric_claims"]}

    assert "存量超额现金计入每股HKD0.7" in text
    assert "关联方应收只计已收回金额" in text
    assert "不相加也不平均" in text
    assert "共同保护的最高价格为每股RMB0.8" in text
    assert "DATA_COVERAGE" not in text
    assert {
        "recognized_existing_excess_cash_per_share",
        "recognized_related_party_receivable_per_share",
        "future_retained_cash_realization_rate",
        "going_concern_replacement_value_per_share",
        "epv_cross_check_per_share",
        "joint_protection_price_ceiling",
    } <= metrics


def test_after_tax_distribution_claim_and_reader_slot_are_code_generated() -> None:
    payload = _bridge_input(
        cash=False,
        replacement=False,
        ordinary_distribution=True,
    )

    compiled = compile_valuation_value_bridges(payload)

    result = compiled["result"]["ordinary_distribution"]
    assert result["after_tax_common_distribution"] == 278.41697737781914
    assert compiled["numeric_claims"] == [
        {
            "claim_id": "distribution.after_tax_common",
            "source_model_id": "DIST:02669:2025",
            "metric": "AFTER_TAX_COMMON_DISTRIBUTION",
            "range_low": 278.41697737781914,
            "range_high": 278.41697737781914,
            "selected_value": 278.41697737781914,
            "currency": "RMB",
            "unit": "RMB_m",
            "as_of": "2025-12-31",
            "scope": "ordinary_common_equity_distribution",
        }
    ]
    assert compiled["reader_slots"] == [
        {
            "slot_id": "after_tax_common_distribution",
            "claim_id": "distribution.after_tax_common",
            "metric": "AFTER_TAX_COMMON_DISTRIBUTION",
            "target_chapter": 12,
            "display_variants": {
                "million_3dp": "RMB278.417百万元",
                "hundred_million_3dp_approx": "约RMB2.784亿元",
            },
            "sentence": (
                "税费和收取摩擦后的普通股分配为RMB278.417百万元，"
                "即约RMB2.784亿元。"
            ),
        }
    ]
    assert validate_valuation_value_bridges(compiled)["state"] == "VALID"


def test_distribution_bridge_rejects_copied_result_and_unsupported_reader_unit() -> None:
    payload = _bridge_input(
        cash=False,
        replacement=False,
        ordinary_distribution=True,
    )
    payload["ordinary_distribution"]["model_input"][
        "after_tax_common_distribution"
    ] = 278.41697737781914
    payload["ordinary_distribution"]["model_input"]["unit"] = "yuan"

    findings = validate_valuation_value_bridge_input(payload)["findings"]

    assert (
        "ordinary_distribution:model_input:$:unknown_field:"
        "after_tax_common_distribution"
    ) in findings
    assert "ordinary_distribution:reader_unit_not_supported" in findings


def test_models_from_different_company_or_position_cannot_share_one_bridge() -> None:
    payload = _bridge_input(
        cash=True,
        replacement=False,
        ordinary_distribution=True,
    )
    distribution = payload["ordinary_distribution"]["model_input"]
    distribution["company_id"] = "OTHER.HK"
    distribution["position_as_of"] = "2024-12-31"

    findings = validate_valuation_value_bridge_input(payload)["findings"]

    assert "model_identity_mismatch:company_id" in findings
    assert "model_identity_mismatch:position_as_of" in findings


def test_joint_protection_ceiling_is_null_when_epv_is_not_comparable() -> None:
    payload = _bridge_input(cash=False)
    epv = payload["replacement_value"]["model_input"]["epv_cross_check"]
    epv.clear()
    epv.update({
        "status": "NOT_COMPARABLE",
        "reason": "Ordinary-share claim scopes differ.",
        "synthesis_rule": "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE",
    })

    compiled = compile_valuation_value_bridges(payload)
    ceiling = compiled["valuation_projection"]["replacement_value"]["joint_protection_price_ceiling"]

    assert ceiling["value"] is None
    assert ceiling["reason"] == "EPV_NOT_COMPARABLE"
    assert not any(
        claim["metric"] == "joint_protection_price_ceiling"
        for claim in compiled["numeric_claims"]
    )


def test_working_capital_bridge_projects_reference_owner_earnings_treatment() -> None:
    payload = _bridge_input(cash=False, replacement=False, working_capital=True)
    compiled = compile_valuation_value_bridges(payload)
    projection = compiled["valuation_projection"]["working_capital"]
    treatment = projection["owner_earnings_valuation_treatment"]

    assert treatment["reference_period_id"] == "FY2025"
    assert treatment["recurring_steady_state_charge_range"] == {
        "range_low": 10,
        "range_high": 10,
    }
    assert treatment["adopted_recurring_charge"] == 10
    assert treatment["adopted_recurring_endpoint"] == "EXACT"
    assert treatment["normalized_owner_cash_range"] == {
        "range_low": 90,
        "range_high": 90,
    }
    assert treatment["adopted_normalized_owner_cash"] == 90
    assert treatment["epv_working_capital_treatment"] == "STEADY_RECURRING_ONLY"
    assert projection["double_count_flags"] == {
        "working_capital_deducted_twice": False,
        "permanent_loss_deducted_twice": False,
        "continuing_epv_and_runoff_release_combined": False,
    }
    claims = {claim["metric"]: claim for claim in compiled["numeric_claims"]}
    assert claims["recurring_working_capital_owner_earnings_charge"]["selected_value"] == 10
    assert claims["normalized_owner_cash_for_valuation"] == {
        "claim_id": "working_capital.normalized_owner_cash.FY2025",
        "source_model_id": "WCM:BRIDGE-TEST",
        "metric": "normalized_owner_cash_for_valuation",
        "range_low": 90,
        "range_high": 90,
        "selected_value": 90,
        "currency": "RMB",
        "unit": "RMB_m",
        "as_of": "2025-12-31",
        "scope": "Listed ordinary common shares",
    }
    assert validate_valuation_value_bridges(compiled)["state"] == "VALID"


def test_working_capital_unknown_stays_null_without_midpoint_zero_or_numeric_claim() -> None:
    payload = _bridge_input(cash=False, replacement=False, working_capital=True)
    payload["working_capital"]["model_input"] = _working_capital_input(unknown=True)

    compiled = compile_valuation_value_bridges(payload)
    projection = compiled["valuation_projection"]["working_capital"]
    treatment = projection["owner_earnings_valuation_treatment"]

    assert treatment["normalization_status"] == "UNKNOWN"
    assert treatment["recurring_steady_state_charge_range"] is None
    assert treatment["adopted_recurring_charge"] is None
    assert treatment["adopted_recurring_endpoint"] == "UNKNOWN"
    assert treatment["normalized_owner_cash_range"] is None
    assert treatment["adopted_normalized_owner_cash"] is None
    assert not any(
        claim["metric"]
        in {
            "recurring_working_capital_owner_earnings_charge",
            "normalized_owner_cash_for_valuation",
        }
        for claim in compiled["numeric_claims"]
    )
    assert "不采用固定比例永久扣减" in "\n".join(
        slot["sentence"] for slot in compiled["reader_slots"]
    )
    assert validate_valuation_value_bridges(compiled)["state"] == "VALID"


def test_net_movement_working_capital_projects_observation_without_valuation_attribution() -> None:
    payload = _bridge_input(cash=False, replacement=False, working_capital=True)
    model_input = payload["working_capital"]["model_input"]
    period = model_input["periods"][0]
    period["disclosure_mode"] = "NET_MOVEMENT_ONLY"
    period.pop("cohorts")
    period["net_movement_observation"] = {
        "opening_net_stock": 20,
        "closing_net_stock": 30,
        "observed_cash_capital_charge": 10,
        "evidence_ids": ["OBS:WC:FY2025:NET-MOVEMENT"],
    }

    compiled = compile_valuation_value_bridges(payload)
    result = compiled["result"]["working_capital"]["reference_period_result"]
    treatment = compiled["valuation_projection"]["working_capital"][
        "owner_earnings_valuation_treatment"
    ]
    claims = {claim["metric"]: claim for claim in compiled["numeric_claims"]}
    slot = next(
        item
        for item in compiled["reader_slots"]
        if item["slot_id"] == "working_capital_normalization_summary"
    )

    assert result["stock_flow_reconciliation"]["actual_cash_capital_charge"] == 10
    assert treatment["normalization_status"] == "UNKNOWN"
    assert treatment["recurring_steady_state_charge_range"] is None
    assert treatment["adopted_recurring_charge"] is None
    assert treatment["normalized_owner_cash_range"] is None
    assert treatment["adopted_normalized_owner_cash"] is None
    assert claims["observed_working_capital_cash_capital_charge"]["selected_value"] == 10
    assert "recurring_working_capital_owner_earnings_charge" not in claims
    assert "normalized_owner_cash_for_valuation" not in claims
    assert slot["display_variants"] == {
        "reference_period": "FY2025",
        "observed_cash_capital_movement": "RMB10百万元",
        "movement_direction": "净占用",
    }
    assert "新项目启动投入与稳态负担" in slot["sentence"]
    assert "不能据此把其中固定比例永久扣减" in slot["sentence"]
    assert "主估值不采用50%之类的预设" in slot["sentence"]
    assert validate_valuation_value_bridges(compiled)["state"] == "VALID"


def test_working_capital_runoff_never_emits_continuing_valuation_claim_or_language() -> None:
    payload = _bridge_input(cash=False, replacement=False, working_capital=True)
    model_input = payload["working_capital"]["model_input"]
    cohort = model_input["periods"][0]["cohorts"][0]
    cohort.update(
        {
            "role": "RUNOFF_OR_SETTLEMENT",
            "opening_net_stock": 20,
            "growth_launch_additions": 0,
            "steady_rollover_additions": 0,
            "cash_collections_and_settlements": 20,
            "permanent_losses": 0,
            "noncash_scope_change": 0,
            "closing_net_stock": 0,
            "loss_treatment": "NO_LOSS",
            "normalization": {
                "method": "NOT_APPLICABLE",
                "adopted_endpoint": "EXACT",
                "adopted_value": 0,
                "rationale": "The identified cohort is being collected and not renewed.",
                "evidence_ids": ["OBS:WC:RUNOFF"],
            },
        }
    )
    model_input["valuation_treatment"].update(
        {
            "epv_use": "NOT_USED",
            "epv_working_capital_treatment": "NOT_APPLICABLE",
            "terminal_route": "RUNOFF_OR_LIQUIDATION",
            "terminal_owner_cash_source": "STOCK_RELEASE_ONLY",
            "terminal_working_capital_treatment": "STOCK_RELEASE_ONLY",
            "stock_release_cohort_ids": ["mature-book"],
        }
    )

    compiled = compile_valuation_value_bridges(payload)
    projection = compiled["valuation_projection"]["working_capital"]
    reader_text = "\n".join(slot["sentence"] for slot in compiled["reader_slots"])

    assert projection["owner_earnings_valuation_treatment"]["terminal_route"] == (
        "RUNOFF_OR_LIQUIDATION"
    )
    assert projection["owner_earnings_valuation_treatment"][
        "terminal_owner_cash_source"
    ] == "STOCK_RELEASE_ONLY"
    assert not any(
        claim["metric"] == "normalized_owner_cash_for_valuation"
        for claim in compiled["numeric_claims"]
    )
    assert "用于持续经营估值" not in reader_text
    assert "仅作为历史经济诊断" in reader_text
    assert "不将该现金流资本化为持续经营价值" in reader_text
    assert validate_valuation_value_bridges(compiled)["state"] == "VALID"


def test_internal_control_tokens_cannot_enter_reader_projection() -> None:
    payload = _bridge_input(cash=False, replacement=True, working_capital=False)
    payload["replacement_value"]["model_input"]["epv_cross_check"] = {
        "status": "NOT_COMPARABLE",
        "reason": "PRIMARY_ROUTE_UNKNOWN / DATA_COVERAGE / P_LONG",
        "synthesis_rule": "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE",
    }

    compiled = compile_valuation_value_bridges(payload)
    reader_text = "\n".join(slot["sentence"] for slot in compiled["reader_slots"])
    assert "PRIMARY_ROUTE_UNKNOWN" not in reader_text
    assert "DATA_COVERAGE" not in reader_text
    assert "P_LONG" not in reader_text
