from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.replacement_value_model import (
    COMPONENT_TYPES,
    LIQUIDATION_USE,
    SYNTHESIS_RULE,
    compute_replacement_value_model,
    project_replacement_value_reader_conclusions,
    validate_replacement_value_model,
)
from scripts.valuation_archetypes import resolve_valuation_archetype


ROOT = Path(__file__).resolve().parents[1]


def _input(
    input_id: str,
    metric: str,
    low: float,
    high: float,
    unit: str,
) -> dict:
    return {
        "input_id": input_id,
        "metric": metric,
        "range_low": low,
        "range_high": high,
        "unit": unit,
        "basis": "Company-specific rebuild evidence as of the model date.",
        "evidence_ids": [f"OBS:{input_id}"],
        "parameter_scope": "COMPANY_SPECIFIC",
    }


def _uncertainty() -> dict:
    return {
        "boundary": "The public record does not bound the rebuild quantity and unit cost together.",
        "investor_consequence": "The component cannot enter recognized replacement value.",
        "promotion_evidence": "Verified cohort, ramp-time and unit-cost evidence would bound the range.",
    }


def _role_bindings(component_type: str, source_fact_id: str | None = None) -> list[dict]:
    card = resolve_valuation_archetype("property_service", "v1")
    spec = next(
        item for item in card["required_component_specs"]
        if item["component_type"] == component_type
    )
    return [
        {
            "role": role,
            "source_fact_ids": [
                source_fact_id or f"OBS:{component_type}:{role}"
            ],
        }
        for role in spec["required_evidence_roles"]
    ]


def _base_model() -> dict:
    unit = "RMB_m"
    return {
        "schema_version": "replacement-value-model.v1",
        "model_id": "RVM:PROPERTY-SERVICE:V1",
        "company_id": "TEST-PROPERTY-SERVICE",
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
            "unit": unit,
            "as_of": "2025-12-31",
        },
        "components": [
            {
                "component_id": "customer-relationships",
                "component_type": "CUSTOMER_RELATIONSHIP",
                "economic_function": "Rebuild the retained customer book and contract base.",
                "estimate_status": "BOUNDED",
                "calculation": {
                    "method": "DIRECT_RANGE",
                    "output_unit": unit,
                    "inputs": [_input("customer-cost", "incremental_customer_rebuild_cost", 100, 120, unit)],
                },
                "recognition": {
                    "status": "RECOGNIZED",
                    "method": "FULL",
                    "reason": "Verified acquisition and retention evidence bounds the rebuild cost.",
                },
                "evidence_role_bindings": _role_bindings("CUSTOMER_RELATIONSHIP"),
            },
            {
                "component_id": "regional-organization",
                "component_type": "REGIONAL_OPERATING_ORGANIZATION",
                "economic_function": "Recruit and ramp the regional operating organization.",
                "estimate_status": "UNKNOWN",
                "calculation": {"method": "UNAVAILABLE", "output_unit": unit, "inputs": []},
                "recognition": {
                    "status": "UNKNOWN",
                    "method": "NOT_APPLICABLE",
                    "reason": "Role-level hiring and ramp evidence is unavailable.",
                },
                "uncertainty_treatment": _uncertainty(),
            },
            {
                "component_id": "acquisition-channel",
                "component_type": "CUSTOMER_ACQUISITION_CHANNEL",
                "economic_function": "Rebuild tender sourcing and customer-acquisition channels.",
                "estimate_status": "SCENARIO_ONLY",
                "calculation": {
                    "method": "DIRECT_RANGE",
                    "output_unit": unit,
                    "inputs": [_input("channel-cost", "channel_rebuild_cost", 20, 40, unit)],
                },
                "recognition": {
                    "status": "SCENARIO_ONLY",
                    "method": "NOT_APPLICABLE",
                    "reason": "Conversion and retention remain insufficiently observed.",
                },
                "uncertainty_treatment": _uncertainty(),
            },
            {
                "component_id": "delivery-record",
                "component_type": "FULFILLMENT_OR_PROJECT_TRACK_RECORD",
                "economic_function": "Recreate qualifications and delivery evidence used to win work.",
                "estimate_status": "BOUNDED",
                "calculation": {
                    "method": "DIRECT_RANGE",
                    "output_unit": unit,
                    "inputs": [_input("record-cost", "qualification_rebuild_cost", 40, 60, unit)],
                },
                "recognition": {
                    "status": "RECOGNIZED",
                    "method": "FRACTION_OF_ESTIMATED_RANGE",
                    "fraction_low": 0.50,
                    "fraction_high": 0.75,
                    "reason": "Only the evidenced qualification benefit is recognized.",
                    "source_fact_ids": [
                        "OBS:delivery-record-recognition-low",
                        "OBS:delivery-record-recognition-high",
                    ],
                },
                "evidence_role_bindings": _role_bindings("FULFILLMENT_OR_PROJECT_TRACK_RECORD"),
            },
            {
                "component_id": "startup-working-capital",
                "component_type": "PROJECT_STARTUP_WORKING_CAPITAL",
                "economic_function": "Fund payroll and supplier cash before initial project collections.",
                "estimate_status": "BOUNDED",
                "calculation": {
                    "method": "DIRECT_RANGE",
                    "output_unit": unit,
                    "inputs": [_input("startup-nwc", "project_startup_net_working_capital", 30, 50, unit)],
                },
                "recognition": {
                    "status": "EXCLUDED",
                    "method": "NOT_APPLICABLE",
                    "reason": "The submitted amount is already represented in balance-sheet working capital.",
                },
                "exclusion_treatment": {
                    "destination": "BALANCE_SHEET_WORKING_CAPITAL",
                    "source_fact_ids": ["OBS:STARTUP-WORKING-CAPITAL:DESTINATION"],
                    "reason": "Verified stock-flow evidence places the same launch funding in balance-sheet working capital.",
                },
                "double_count_treatment": {
                    "balance_sheet_working_capital": "ALREADY_INCLUDED_EXCLUDED",
                    "epv_maintenance_need": "NOT_INCLUDED",
                    "explanation": "Exclude the balance-sheet overlap rather than count it a second time.",
                },
            },
            {
                "component_id": "other-functional-assets",
                "component_type": "OTHER_FUNCTIONAL_ASSET",
                "economic_function": "Rebuild other separately evidenced operating capabilities.",
                "estimate_status": "BOUNDED",
                "calculation": {
                    "method": "SUM_OF_INPUT_RANGES",
                    "output_unit": unit,
                    "inputs": [
                        _input("systems", "operating_system_rebuild_cost", 10, 20, unit),
                        _input("training", "initial_training_cost", 5, 10, unit),
                    ],
                },
                "recognition": {
                    "status": "RECOGNIZED",
                    "method": "FULL",
                    "reason": "The inputs cover distinct functional assets.",
                },
                "evidence_role_bindings": _role_bindings("OTHER_FUNCTIONAL_ASSET"),
            },
        ],
        "claims_bridge": {
            "non_operating_assets": {"range_low": 20, "range_high": 30},
            "debt": {"range_low": 40, "range_high": 50},
            "minority_interest": {"range_low": 5, "range_high": 10},
            "other_priority_claims": {"range_low": 0, "range_high": 5},
            "other_adjustments": {"range_low": -5, "range_high": 0},
            "shares_outstanding": 100,
            "source_fact_ids": [
                "OBS:claims-bridge-non-operating-assets",
                "OBS:claims-bridge-debt",
                "OBS:claims-bridge-minority-interest",
                "OBS:claims-bridge-other-priority-claims",
                "OBS:claims-bridge-other-adjustments",
                "OBS:claims-bridge-shares",
            ],
        },
        "liquidation_floor_reference": {
            "status": "AVAILABLE",
            "model_id": "NAV:LIQUIDATION:FLOOR",
            "value_scope": "ordinary_common_equity_per_share",
            "currency": "RMB",
            "as_of": "2025-12-31",
            "per_share_low": 0.30,
            "per_share_high": 0.50,
            "use": LIQUIDATION_USE,
            "source_fact_ids": [
                "OBS:liquidation-floor-low",
                "OBS:liquidation-floor-high",
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
            "unit": unit,
            "as_of": "2025-12-31",
            "equity_value_low": 80,
            "equity_value_high": 160,
            "shares_outstanding": 100,
            "per_share_low": 0.80,
            "per_share_high": 1.60,
            "synthesis_rule": SYNTHESIS_RULE,
            "source_fact_ids": [
                "CALC:epv-equity-low",
                "CALC:epv-equity-high",
                "OBS:claims-bridge-shares",
                "CALC:epv-per-share-low",
                "CALC:epv-per-share-high",
            ],
        },
    }


def _complete_model() -> dict:
    payload = _base_model()
    regional = payload["components"][1]
    regional.update({
        "estimate_status": "BOUNDED",
        "calculation": {
            "method": "DIRECT_RANGE",
            "output_unit": "RMB_m",
            "inputs": [_input("regional-cost", "regional_organization_rebuild_cost", 50, 70, "RMB_m")],
        },
        "recognition": {
            "status": "RECOGNIZED",
            "method": "FULL",
            "reason": "Verified hiring and ramp evidence bounds the regional rebuild cost.",
        },
        "evidence_role_bindings": _role_bindings("REGIONAL_OPERATING_ORGANIZATION"),
    })
    regional.pop("uncertainty_treatment", None)
    channel = payload["components"][2]
    channel["estimate_status"] = "BOUNDED"
    channel["recognition"] = {
        "status": "RECOGNIZED",
        "method": "FULL",
        "reason": "Verified channel rebuild evidence bounds the range.",
    }
    channel["evidence_role_bindings"] = _role_bindings("CUSTOMER_ACQUISITION_CHANNEL")
    channel["double_count_treatment"] = {
        "replacement_component_owner": "CUSTOMER_RELATIONSHIP",
        "replacement_component_overlap": "SEPARATE_COST_BASE",
        "source_fact_ids": ["OBS:CHANNEL:COST-BASE-SEPARATE"],
        "explanation": "Verified cost attribution separates the channel rebuild from the customer book.",
    }
    channel.pop("uncertainty_treatment", None)
    startup = payload["components"][4]
    startup["recognition"] = {
        "status": "RECOGNIZED",
        "method": "FULL",
        "reason": "The startup capital is not present in another value destination.",
    }
    startup["evidence_role_bindings"] = _role_bindings("PROJECT_STARTUP_WORKING_CAPITAL")
    startup.pop("exclusion_treatment", None)
    startup["double_count_treatment"] = {
        "balance_sheet_working_capital": "NOT_INCLUDED",
        "epv_maintenance_need": "NOT_INCLUDED",
        "explanation": "The component is included once in replacement value only.",
    }
    return payload


def _magna_method_fixture() -> dict:
    return {
        "schema_version": "replacement-value-model.v1",
        "model_id": "METHOD:MAGNA:CUSTOMER-LIST",
        "company_id": "METHOD-FIXTURE-MAGNA",
        "model_context": {
            "purpose": "METHOD_FIXTURE",
            "method_fixture_id": "MAGNA_CUSTOMER_LIST_REBUILD",
            "parameter_transfer_policy": "METHOD_FIXTURE_PARAMETERS_NON_TRANSFERABLE",
        },
        "basis": {
            "valuation_basis": "GOING_CONCERN_REPLACEMENT",
            "value_scope": "enterprise",
            "economic_entity": "Magna worked-case method perimeter",
            "operating_perimeter": "Customer-list rebuild illustration only",
            "ordinary_share_claim_scope": "Worked-case ordinary common shares",
            "currency": "USD",
            "unit": "USD_m",
            "as_of": "2009-03-01",
        },
        "components": [
            {
                "component_id": "magna-customer-list",
                "component_type": "CUSTOMER_RELATIONSHIP",
                "economic_function": "Illustrate customer-list reproduction cost from a sales base and acquisition ratio.",
                "estimate_status": "BOUNDED",
                "calculation": {
                    "method": "PRODUCT_OF_INPUT_RANGES",
                    "output_unit": "USD_m",
                    "inputs": [
                        {
                            "input_id": "magna-sales-base",
                            "metric": "sales_capacity",
                            "range_low": 24000,
                            "range_high": 24000,
                            "unit": "USD_m",
                            "basis": "Worked-case method input, not a current-company fact.",
                            "evidence_ids": ["METHOD:MAGNA:SALES_BASE"],
                            "parameter_scope": "METHOD_FIXTURE_ONLY",
                        },
                        {
                            "input_id": "magna-acquisition-ratio",
                            "metric": "customer_acquisition_cost_ratio",
                            "range_low": 0.075,
                            "range_high": 0.075,
                            "unit": "ratio",
                            "basis": "Worked-case 7.5% illustration; prohibited as a transferable parameter.",
                            "evidence_ids": ["METHOD:MAGNA:ACQUISITION_RATIO"],
                            "parameter_scope": "METHOD_FIXTURE_ONLY",
                        },
                    ],
                },
                "recognition": {
                    "status": "RECOGNIZED",
                    "method": "FULL",
                    "reason": "The method fixture reproduces the worked-case calculation only.",
                },
            }
        ],
        "claims_bridge": {
            "non_operating_assets": {"range_low": 0, "range_high": 0},
            "debt": {"range_low": 0, "range_high": 0},
            "minority_interest": {"range_low": 0, "range_high": 0},
            "other_priority_claims": {"range_low": 0, "range_high": 0},
            "other_adjustments": {"range_low": 0, "range_high": 0},
            "shares_outstanding": 100,
            "source_fact_ids": ["METHOD:MAGNA:CLAIMS"],
        },
        "liquidation_floor_reference": {
            "status": "UNAVAILABLE",
            "reason": "This method fixture isolates one reproduction-cost component.",
            "use": LIQUIDATION_USE,
        },
        "epv_cross_check": {
            "status": "UNAVAILABLE",
            "reason": "The isolated customer-list fixture is not a full enterprise-value comparison.",
            "synthesis_rule": SYNTHESIS_RULE,
        },
    }


def test_schema_defers_component_classes_to_the_versioned_valuation_archetype() -> None:
    schema = json.loads((ROOT / "schemas/replacement_value_model.schema.json").read_text())
    assert schema["$defs"]["component"]["properties"]["component_type"] == {
        "type": "string",
        "pattern": "^[A-Z][A-Z0-9_]*$",
    }
    assert COMPONENT_TYPES == {
        "CUSTOMER_RELATIONSHIP",
        "REGIONAL_OPERATING_ORGANIZATION",
        "CUSTOMER_ACQUISITION_CHANNEL",
        "FULFILLMENT_OR_PROJECT_TRACK_RECORD",
        "PROJECT_STARTUP_WORKING_CAPITAL",
        "OTHER_FUNCTIONAL_ASSET",
    }
    assert schema["additionalProperties"] is False


def test_company_model_consumes_component_types_from_its_resolved_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _base_model()
    payload["model_context"].update(
        {
            "valuation_archetype_id": "industrial_service",
            "valuation_archetype_version": "v1",
        }
    )
    payload["components"][0]["component_type"] = "PROCESS_QUALIFICATION"

    alternative = resolve_valuation_archetype("property_service", "v1")
    alternative.update(
        {
            "card_id": "VALUATION_ARCHETYPE:industrial_service:v1",
            "archetype_id": "industrial_service",
            "version": "v1",
        }
    )
    alternative["required_component_specs"][0]["component_type"] = (
        "PROCESS_QUALIFICATION"
    )

    def _resolve(archetype_id: str, version: str | None = None) -> dict:
        assert (archetype_id, version) == ("industrial_service", "v1")
        return deepcopy(alternative)

    monkeypatch.setattr("scripts.valuation_archetypes.resolve_valuation_archetype", _resolve)

    assert validate_replacement_value_model(payload)["state"] == "REVIEWABLE"


def test_partial_model_preserves_component_anchors_without_fake_per_share_range() -> None:
    payload = _base_model()
    assert validate_replacement_value_model(payload)["state"] == "REVIEWABLE"

    result = compute_replacement_value_model(payload)

    assert result["gross_recognized_replacement_range"] == {"range_low": 135.0, "range_high": 195.0}
    assert result["ordinary_common_equity_range"] is None
    assert result["per_share_range"] is None
    assert result["epv_cross_check"]["status"] == "COMPARABLE"
    assert result["epv_cross_check"]["relationship"] == "REPLACEMENT_SCOPE_INCOMPLETE"
    assert result["epv_cross_check"]["synthesis_rule"] == SYNTHESIS_RULE
    delivery_record = next(
        item for item in result["component_results"] if item["component_id"] == "delivery-record"
    )
    assert delivery_record["recognition_source_fact_ids"] == [
        "OBS:delivery-record-recognition-low",
        "OBS:delivery-record-recognition-high",
    ]
    assert result["claims_bridge"]["source_fact_ids"] == [
        "OBS:claims-bridge-non-operating-assets",
        "OBS:claims-bridge-debt",
        "OBS:claims-bridge-minority-interest",
        "OBS:claims-bridge-other-priority-claims",
        "OBS:claims-bridge-other-adjustments",
        "OBS:claims-bridge-shares",
    ]
    assert result["epv_cross_check"]["source_fact_ids"] == [
        "CALC:epv-equity-low",
        "CALC:epv-equity-high",
        "OBS:claims-bridge-shares",
        "CALC:epv-per-share-low",
        "CALC:epv-per-share-high",
    ]
    assert result["economic_conclusion"] == {
        "replacement_value_role": "GOING_CONCERN_REPLACEMENT_RANGE",
            "recognized_scope": "PARTIAL_RECOGNIZED_REQUIRED_COMPONENTS",
        "unresolved_required_component_ids": [
            "regional-organization",
            "acquisition-channel",
        ],
        "replacement_range_status": "INCOMPLETE",
        "claims_bridge_status": "NOT_APPLIED_TO_INCOMPLETE_REPLACEMENT_SCOPE",
        "epv_comparability": "COMPARABLE",
        "replacement_vs_epv": "REPLACEMENT_SCOPE_INCOMPLETE",
        "liquidation_floor_role": "SEPARATE_STRESS_REFERENCE",
        "synthesis_rule": SYNTHESIS_RULE,
        "investor_use": (
            "Use overlap or divergence to assess protection, impairment, excess capacity or franchise; "
            "never add or average replacement value and EPV."
        ),
    }


def test_complete_model_computes_company_equity_and_per_share_ranges() -> None:
    result = compute_replacement_value_model(_complete_model())

    assert result["gross_recognized_replacement_range"] == {
        "range_low": 235.0,
        "range_high": 355.0,
    }
    assert result["ordinary_common_equity_range"] == {
        "range_low": 185.0,
        "range_high": 340.0,
    }
    assert result["per_share_range"] == {"range_low": 1.85, "range_high": 3.4}
    assert result["epv_cross_check"]["relationship"] == "REPLACEMENT_ABOVE_EPV"
    assert result["economic_conclusion"]["replacement_range_status"] == "AVAILABLE"


def test_cross_component_cost_owner_changes_which_rebuild_cost_can_enter_value() -> None:
    unresolved = _complete_model()
    channel = unresolved["components"][2]
    channel.pop("double_count_treatment")

    findings = validate_replacement_value_model(unresolved)["findings"]

    assert "acquisition-channel:replacement_component_overlap_unresolved" in findings

    included = compute_replacement_value_model(_complete_model())
    already_owned = _complete_model()
    channel = already_owned["components"][2]
    channel["recognition"] = {
        "status": "EXCLUDED",
        "method": "NOT_APPLICABLE",
        "reason": "The customer relationship component already owns the same rebuild cost.",
    }
    channel.pop("evidence_role_bindings")
    channel.pop("double_count_treatment")
    channel["exclusion_treatment"] = {
        "destination": "OTHER_REPLACEMENT_COMPONENT",
        "destination_component_type": "CUSTOMER_RELATIONSHIP",
        "source_fact_ids": ["OBS:CHANNEL:CUSTOMER-BOOK-OVERLAP"],
        "reason": "Verified cost attribution places the shared spend in the customer book.",
    }
    excluded = compute_replacement_value_model(already_owned)

    assert included["gross_recognized_replacement_range"] == {
        "range_low": 235.0,
        "range_high": 355.0,
    }
    assert excluded["gross_recognized_replacement_range"] == {
        "range_low": 215.0,
        "range_high": 315.0,
    }
    assert excluded["economic_conclusion"]["replacement_range_status"] == "AVAILABLE"


def test_resolved_already_included_component_is_zero_increment_not_unknown_scope() -> None:
    payload = _complete_model()
    startup = payload["components"][4]
    startup["recognition"] = {
        "status": "EXCLUDED",
        "method": "NOT_APPLICABLE",
        "reason": "The startup capital is already represented in balance-sheet working capital.",
    }
    startup.pop("evidence_role_bindings", None)
    startup["exclusion_treatment"] = {
        "destination": "BALANCE_SHEET_WORKING_CAPITAL",
        "source_fact_ids": ["OBS:STARTUP-WORKING-CAPITAL:DESTINATION"],
        "reason": "Verified stock-flow evidence puts the same cash sequence in balance-sheet working capital.",
    }
    startup["double_count_treatment"] = {
        "balance_sheet_working_capital": "ALREADY_INCLUDED_EXCLUDED",
        "epv_maintenance_need": "NOT_INCLUDED",
        "explanation": "Exclude the resolved balance-sheet overlap rather than count it a second time.",
    }

    result = compute_replacement_value_model(payload)

    assert result["excluded_component_ids"] == ["startup-working-capital"]
    assert result["economic_conclusion"]["replacement_range_status"] == "AVAILABLE"
    assert result["ordinary_common_equity_range"] == {
        "range_low": 155.0,
        "range_high": 290.0,
    }
    assert result["per_share_range"] == {"range_low": 1.55, "range_high": 2.9}


def test_unknown_component_is_neither_zero_nor_midpoint_and_does_not_erase_known_range() -> None:
    result = compute_replacement_value_model(_base_model())
    regional = next(
        item for item in result["component_results"] if item["component_id"] == "regional-organization"
    )
    assert regional["estimated_range"] is None
    assert regional["recognized_range"] is None
    assert result["unknown_component_ids"] == ["regional-organization"]
    assert result["gross_recognized_replacement_range"]["range_low"] == 135.0

    invented_zero = _base_model()
    unknown = invented_zero["components"][1]
    unknown["calculation"] = {
        "method": "DIRECT_RANGE",
        "output_unit": "RMB_m",
        "inputs": [_input("invented-zero", "regional_rebuild_cost", 0, 0, "RMB_m")],
    }
    findings = validate_replacement_value_model(invented_zero)["findings"]
    assert "regional-organization:unknown_must_not_have_computed_range" in findings


def test_project_startup_working_capital_requires_explicit_nonduplicative_treatment() -> None:
    missing = _base_model()
    del missing["components"][4]["double_count_treatment"]
    findings = validate_replacement_value_model(missing)["findings"]
    assert any("double_count_balance_sheet_working_capital" in finding for finding in findings)

    double_counted = _base_model()
    double_counted["components"][4]["recognition"] = {
        "status": "RECOGNIZED",
        "method": "FULL",
        "reason": "Incorrectly recognize a balance-sheet amount twice.",
    }
    findings = validate_replacement_value_model(double_counted)["findings"]
    assert "startup-working-capital:already_included_working_capital_must_be_excluded" in findings


def test_recognized_component_requires_each_card_evidence_role_with_current_sources() -> None:
    missing_role = _complete_model()
    customer = missing_role["components"][0]
    customer["evidence_role_bindings"] = customer["evidence_role_bindings"][1:]

    findings = validate_replacement_value_model(missing_role)["findings"]

    assert (
        "customer-relationships:evidence_role_binding_missing_required_role:"
        "CONTRACT_POPULATION_OR_CUSTOMER_BOOK"
    ) in findings

    stale_source = _complete_model()
    stale_source["components"][0]["evidence_role_bindings"][0]["source_fact_ids"] = [
        "METHOD:NOT-A-CURRENT-FACT"
    ]
    findings = validate_replacement_value_model(stale_source)["findings"]

    assert (
        "customer-relationships:evidence_role_bindings[0]:"
        "source_fact_ids_require_current_observation_or_calculation"
    ) in findings


def test_required_excluded_component_needs_card_permitted_source_bound_destination() -> None:
    unproved = _complete_model()
    channel = unproved["components"][2]
    channel["recognition"] = {
        "status": "EXCLUDED",
        "method": "NOT_APPLICABLE",
        "reason": "The channel is already represented by the customer book.",
    }
    channel.pop("evidence_role_bindings", None)
    channel["exclusion_treatment"] = {
        "destination": "OTHER_REPLACEMENT_COMPONENT",
        "destination_component_type": "CUSTOMER_RELATIONSHIP",
        "reason": "The customer-book component owns the same capability.",
    }
    findings = validate_replacement_value_model(unproved)["findings"]
    assert "acquisition-channel:exclusion:source_fact_ids_missing" in findings

    unrecognized_destination = _complete_model()
    channel = unrecognized_destination["components"][2]
    channel["recognition"] = {
        "status": "EXCLUDED",
        "method": "NOT_APPLICABLE",
        "reason": "The channel is already represented by the customer book.",
    }
    channel.pop("evidence_role_bindings", None)
    channel["exclusion_treatment"] = {
        "destination": "OTHER_REPLACEMENT_COMPONENT",
        "destination_component_type": "CUSTOMER_RELATIONSHIP",
        "source_fact_ids": ["OBS:CHANNEL:DESTINATION"],
        "reason": "A source-bound destination is named.",
    }
    customer_destination = unrecognized_destination["components"][0]
    customer_destination["recognition"] = {
        "status": "UNKNOWN",
        "method": "NOT_APPLICABLE",
        "reason": "The customer-book range can no longer be recognized.",
    }
    findings = validate_replacement_value_model(unrecognized_destination)["findings"]
    assert (
        "acquisition-channel:exclusion_destination_component_type_must_be_recognized"
    ) in findings

    unpermitted = _complete_model()
    customer = unpermitted["components"][0]
    customer["recognition"] = {
        "status": "EXCLUDED",
        "method": "NOT_APPLICABLE",
        "reason": "Incorrectly remove the customer book from the replacement scope.",
    }
    customer.pop("evidence_role_bindings", None)
    customer["exclusion_treatment"] = {
        "destination": "OTHER_REPLACEMENT_COMPONENT",
        "destination_component_type": "OTHER_FUNCTIONAL_ASSET",
        "source_fact_ids": ["OBS:CUSTOMER-BOOK:DESTINATION"],
        "reason": "An unsupported exclusion destination is claimed.",
    }
    findings = validate_replacement_value_model(unpermitted)["findings"]
    assert "customer-relationships:exclusion_destination_not_allowed_by_valuation_archetype" in findings

    unresolved_destination = _complete_model()
    startup = unresolved_destination["components"][4]
    startup["recognition"] = {
        "status": "EXCLUDED",
        "method": "NOT_APPLICABLE",
        "reason": "The startup capital is asserted to be in working capital.",
    }
    startup.pop("evidence_role_bindings", None)
    startup["exclusion_treatment"] = {
        "destination": "BALANCE_SHEET_WORKING_CAPITAL",
        "source_fact_ids": ["OBS:STARTUP-WORKING-CAPITAL:DESTINATION"],
        "reason": "A destination is named but the double-count treatment does not affirm it.",
    }
    startup["double_count_treatment"]["balance_sheet_working_capital"] = "NOT_INCLUDED"
    findings = validate_replacement_value_model(unresolved_destination)["findings"]
    assert (
        "startup-working-capital:exclusion_destination_not_affirmed_by_double_count_treatment:"
        "BALANCE_SHEET_WORKING_CAPITAL"
    ) in findings


def test_liquidation_floor_is_a_separate_reference_and_never_changes_replacement_value() -> None:
    baseline = compute_replacement_value_model(_base_model())
    stressed = _base_model()
    stressed["liquidation_floor_reference"]["per_share_low"] = 8.0
    stressed["liquidation_floor_reference"]["per_share_high"] = 9.0
    changed = compute_replacement_value_model(stressed)

    assert changed["per_share_range"] == baseline["per_share_range"]
    assert changed["ordinary_common_equity_range"] == baseline["ordinary_common_equity_range"]
    assert changed["liquidation_floor_reference"]["use"] == LIQUIDATION_USE


def test_epv_requires_same_scope_and_forbids_addition_or_average() -> None:
    mismatched = _base_model()
    mismatched["epv_cross_check"]["currency"] = "HKD"
    findings = validate_replacement_value_model(mismatched)["findings"]
    assert "epv_cross_check:basis_mismatch:currency" in findings

    combined = _base_model()
    combined["epv_cross_check"]["synthesis_rule"] = "WEIGHTED_AVERAGE"
    findings = validate_replacement_value_model(combined)["findings"]
    assert "epv_cross_check:replacement_and_epv_must_never_be_added_or_averaged" in findings

    smuggled = _base_model()
    smuggled["epv_cross_check"]["combined_value"] = 2.0
    findings = validate_replacement_value_model(smuggled)["findings"]
    assert "epv_cross_check:unknown_field:combined_value" in findings


def test_fraction_claims_and_comparable_epv_require_declared_source_identities() -> None:
    fraction_missing = _base_model()
    del fraction_missing["components"][3]["recognition"]["source_fact_ids"]
    findings = validate_replacement_value_model(fraction_missing)["findings"]
    assert "delivery-record:recognition:source_fact_ids_missing" in findings

    claims_missing = _base_model()
    del claims_missing["claims_bridge"]["source_fact_ids"]
    findings = validate_replacement_value_model(claims_missing)["findings"]
    assert "claims_bridge:source_fact_ids_missing" in findings

    liquidation_missing = _base_model()
    del liquidation_missing["liquidation_floor_reference"]["source_fact_ids"]
    findings = validate_replacement_value_model(liquidation_missing)["findings"]
    assert "liquidation_floor_reference:source_fact_ids_missing" in findings

    epv_missing = _base_model()
    del epv_missing["epv_cross_check"]["source_fact_ids"]
    findings = validate_replacement_value_model(epv_missing)["findings"]
    assert "epv_cross_check:source_fact_ids_missing" in findings


def test_reader_projection_uses_plain_economic_conclusions_and_preserves_boundaries() -> None:
    projection = project_replacement_value_reader_conclusions(
        compute_replacement_value_model(_complete_model())
    )
    text = "\n".join(projection["reader_conclusions"])

    assert "每股RMB 1.85–3.4" in text
    assert "清算压力底" in text
    assert "只用于交叉核验，不相加，也不平均" in text
    assert "RECOGNIZED" not in text
    assert "CROSS_CHECK_ONLY" not in text


def test_magna_method_fixture_reproduces_7_5_percent_without_transfer_authority() -> None:
    fixture = _magna_method_fixture()
    result = compute_replacement_value_model(fixture)
    assert result["gross_recognized_replacement_range"] == {
        "range_low": 1800.0,
        "range_high": 1800.0,
    }
    assert result["model_context"]["parameter_transfer_policy"] == (
        "METHOD_FIXTURE_PARAMETERS_NON_TRANSFERABLE"
    )
    with pytest.raises(ValueError, match="method_fixture_has_no_company_reader_conclusion"):
        project_replacement_value_reader_conclusions(result)

    copied = deepcopy(fixture)
    copied["model_context"] = {
        "purpose": "COMPANY_ANALYSIS",
        "parameter_transfer_policy": "COMPANY_SPECIFIC_EVIDENCE_ONLY",
    }
    findings = validate_replacement_value_model(copied)["findings"]
    assert any("method_fixture_parameter_in_company_model" in finding for finding in findings)
    assert any("company_input_requires_verified_observation" in finding for finding in findings)
