from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.valuation_model_gate import _validate_value_bridge_fact_bindings
from scripts.valuation_value_bridges import compile_valuation_value_bridges
from tests.test_valuation_value_bridges import _replacement_input


def _ordinary_input() -> dict:
    facts = [
        ("OBS:DIST:EARNINGS", 100.0, "RMB_m"),
        ("OBS:DIST:RATE", 0.4, "ratio"),
        ("OBS:DIST:FRICTION", 0.1, "ratio"),
        ("OBS:DIST:FIXED", 2.0, "RMB_m"),
    ]
    return {
        "schema_version": "valuation-value-bridges-input.v1",
        "canonical_fact_bindings": [
            {"path": "ordinary_distribution.model_input.normalized_ordinary_share_operating_earnings", "evidence_id": facts[0][0]},
            {"path": "ordinary_distribution.model_input.ordinary_distribution_rate", "evidence_id": facts[1][0]},
            {"path": "ordinary_distribution.model_input.distribution_tax_and_collection_friction_rate", "evidence_id": facts[2][0]},
            {"path": "ordinary_distribution.model_input.fixed_collection_cost", "evidence_id": facts[3][0]},
        ],
        "ordinary_distribution": {
            "model_input": {
                "schema_version": "ordinary-distribution-input.v1",
                "model_id": "DIST:FACT-BINDING",
                "company_id": "TEST.HK",
                "cutoff_at": "2026-08-11",
                "position_as_of": "2025-12-31",
                "currency": "RMB",
                "unit": "RMB_m",
                "verified_facts": [
                    {"fact_id": fact_id, "status": "VERIFIED"}
                    for fact_id, _, _ in facts
                ],
                "input_fact_ids": [fact_id for fact_id, _, _ in facts],
                "normalized_ordinary_share_operating_earnings": 100.0,
                "ordinary_distribution_rate": 0.4,
                "distribution_tax_and_collection_friction_rate": 0.1,
                "fixed_collection_cost": 2.0,
            }
        },
    }


def _write_verified_observations(output: Path) -> None:
    rows = [
        ("OBS:DIST:EARNINGS", 100.0, "RMB_m"),
        ("OBS:DIST:RATE", 0.4, "ratio"),
        ("OBS:DIST:FRICTION", 0.1, "ratio"),
        ("OBS:DIST:FIXED", 2.0, "RMB_m"),
    ]
    (output / "fact_observations.json").write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "observation_id": fact_id,
                        "normalized_value": value,
                        "unit": unit,
                        "currency": "RMB" if unit == "RMB_m" else None,
                        "as_of": "2025-12-31",
                        "measurement_context": {},
                        "status": "VERIFIED",
                    }
                    for fact_id, value, unit in rows
                ]
            }
        ),
        encoding="utf-8",
    )


def _validate(output: Path, bridge_input: dict) -> tuple[list[str], list[str]]:
    payload = {"value_bridge_models": compile_valuation_value_bridges(bridge_input)}
    invalid: list[str] = []
    incomplete: list[str] = []
    _validate_value_bridge_fact_bindings(
        payload, output, required=True, invalid=invalid, incomplete=incomplete
    )
    return invalid, incomplete


def _replacement_input_with_current_fact_bindings() -> tuple[
    dict,
    list[tuple[str, float, str, list[str], list[str]]],
    list[tuple[str, float, str]],
]:
    """Build a full-scope replacement fixture with every raw operand bound.

    It intentionally uses a recognition fraction, an enterprise-to-equity
    claims bridge and a comparable EPV projection: these were the numeric
    ownership gaps in the first replacement model contract.
    """
    model = deepcopy(_replacement_input())
    customer = model["components"][0]
    customer["calculation"]["inputs"][0]["evidence_ids"] = [
        "OBS:CUSTOMER-COST:LOW",
        "OBS:CUSTOMER-COST:HIGH",
    ]
    customer["recognition"] = {
        "status": "RECOGNIZED",
        "method": "FRACTION_OF_ESTIMATED_RANGE",
        "fraction_low": 0.5,
        "fraction_high": 0.75,
        "reason": "Only the independently measured retention benefit is recognized.",
        "source_fact_ids": [
            "CALC:REPLACEMENT:RECOGNITION:LOW",
            "CALC:REPLACEMENT:RECOGNITION:HIGH",
        ],
    }
    role_rows: list[tuple[str, float, str, list[str], list[str]]] = []
    for component in model["components"]:
        component_type = component["component_type"]
        for binding in component["evidence_role_bindings"]:
            role = binding["role"]
            source_id = "OBS:ROLE:" + component_type + ":" + role
            binding["source_fact_ids"] = [source_id]
            role_rows.append((source_id, 0.0, "RMB_m", [role], []))
    observation_rows = [
        ("OBS:CUSTOMER-COST:LOW", 100.0, "RMB_m", [], []),
        ("OBS:CUSTOMER-COST:HIGH", 120.0, "RMB_m", [], []),
        ("OBS:REGIONAL-ORGANIZATION", 0.0, "RMB_m", [], []),
        ("OBS:ACQUISITION-CHANNEL", 0.0, "RMB_m", [], []),
        ("OBS:DELIVERY-RECORD", 0.0, "RMB_m", [], []),
        ("OBS:STARTUP-WORKING-CAPITAL", 0.0, "RMB_m", [], []),
        ("OBS:OTHER-FUNCTIONAL-ASSETS", 0.0, "RMB_m", [], []),
        ("OBS:CLAIMS:NON_OPERATING_ASSETS", 20.0, "RMB_m", [], []),
        ("OBS:CLAIMS:DEBT", 40.0, "RMB_m", [], []),
        ("OBS:CLAIMS:MINORITY_INTEREST", 0.0, "RMB_m", [], []),
        ("OBS:CLAIMS:OTHER_PRIORITY_CLAIMS", 0.0, "RMB_m", [], []),
        ("OBS:CLAIMS:OTHER_ADJUSTMENTS", 0.0, "RMB_m", [], []),
        ("OBS:CLAIMS:SHARES", 100.0, "million_shares", [], []),
    ]
    observation_rows.extend(role_rows)
    calculation_rows = [
        ("CALC:REPLACEMENT:RECOGNITION:LOW", 0.5, "ratio"),
        ("CALC:REPLACEMENT:RECOGNITION:HIGH", 0.75, "ratio"),
        ("CALC:NAV:FLOOR:LOW", 0.3, "RMB_per_share"),
        ("CALC:NAV:FLOOR:HIGH", 0.4, "RMB_per_share"),
        ("CALC:EPV:EQUITY:LOW", 90.0, "RMB_m"),
        ("CALC:EPV:EQUITY:HIGH", 110.0, "RMB_m"),
        ("CALC:EPV:PER_SHARE:LOW", 0.9, "RMB_per_share"),
        ("CALC:EPV:PER_SHARE:HIGH", 1.1, "RMB_per_share"),
    ]

    bindings: list[dict[str, str]] = []
    def bind(path: str, evidence_id: str) -> None:
        bindings.append({"path": path, "evidence_id": evidence_id})

    base = "replacement_value.model_input"
    bind(base + ".components[0].calculation.inputs[0].range_low", "OBS:CUSTOMER-COST:LOW")
    bind(base + ".components[0].calculation.inputs[0].range_high", "OBS:CUSTOMER-COST:HIGH")
    for index, evidence_id in enumerate((
        "OBS:REGIONAL-ORGANIZATION",
        "OBS:ACQUISITION-CHANNEL",
        "OBS:DELIVERY-RECORD",
        "OBS:STARTUP-WORKING-CAPITAL",
        "OBS:OTHER-FUNCTIONAL-ASSETS",
    ), start=1):
        path = base + f".components[{index}].calculation.inputs[0]"
        bind(path + ".range_low", evidence_id)
        bind(path + ".range_high", evidence_id)
    bind(base + ".components[0].recognition.fraction_low", "CALC:REPLACEMENT:RECOGNITION:LOW")
    bind(base + ".components[0].recognition.fraction_high", "CALC:REPLACEMENT:RECOGNITION:HIGH")
    bind(base + ".liquidation_floor_reference.per_share_low", "CALC:NAV:FLOOR:LOW")
    bind(base + ".liquidation_floor_reference.per_share_high", "CALC:NAV:FLOOR:HIGH")
    for field, evidence_id in (
        ("non_operating_assets", "OBS:CLAIMS:NON_OPERATING_ASSETS"),
        ("debt", "OBS:CLAIMS:DEBT"),
        ("minority_interest", "OBS:CLAIMS:MINORITY_INTEREST"),
        ("other_priority_claims", "OBS:CLAIMS:OTHER_PRIORITY_CLAIMS"),
        ("other_adjustments", "OBS:CLAIMS:OTHER_ADJUSTMENTS"),
    ):
        path = base + ".claims_bridge." + field
        bind(path + ".range_low", evidence_id)
        bind(path + ".range_high", evidence_id)
    bind(base + ".claims_bridge.shares_outstanding", "OBS:CLAIMS:SHARES")
    for field, evidence_id in (
        ("equity_value_low", "CALC:EPV:EQUITY:LOW"),
        ("equity_value_high", "CALC:EPV:EQUITY:HIGH"),
        ("shares_outstanding", "OBS:CLAIMS:SHARES"),
        ("per_share_low", "CALC:EPV:PER_SHARE:LOW"),
        ("per_share_high", "CALC:EPV:PER_SHARE:HIGH"),
    ):
        bind(base + ".epv_cross_check." + field, evidence_id)

    return {
        "schema_version": "valuation-value-bridges-input.v1",
        "canonical_fact_bindings": bindings,
        "replacement_value": {"model_input": model},
    }, observation_rows, calculation_rows


def _write_replacement_current_registry(
    output: Path,
    observation_rows: list[tuple[str, float, str, list[str], list[str]]],
    calculation_rows: list[tuple[str, float, str]],
) -> None:
    context = {
        "economic_entity": "Listed consolidated operating group",
        "operating_perimeter": "Continuing property-service operations",
    }
    (output / "fact_observations.json").write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "observation_id": fact_id,
                        "normalized_value": value,
                        "unit": unit,
                        "currency": "RMB" if unit == "RMB_m" else None,
                        "as_of": "2025-12-31",
                        "measurement_context": context,
                        "status": "VERIFIED",
                        **(
                            {"valuation_evidence_roles": roles}
                            if roles
                            else {}
                        ),
                        **(
                            {
                                "valuation_exclusion_destinations": destinations
                            }
                            if destinations
                            else {}
                        ),
                    }
                    for fact_id, value, unit, roles, destinations in observation_rows
                ]
            }
        ),
        encoding="utf-8",
    )
    (output / "calculation_observations.json").write_text(
        json.dumps(
            {
                "calculations": [
                    {
                        "calculation_id": calculation_id,
                        "value": value,
                        "unit": unit,
                        "status": "VERIFIED",
                    }
                    for calculation_id, value, unit in calculation_rows
                ]
            }
        ),
        encoding="utf-8",
    )


def test_every_distribution_operand_is_resolved_to_current_verified_observation(
    tmp_path: Path,
) -> None:
    _write_verified_observations(tmp_path)

    invalid, incomplete = _validate(tmp_path, _ordinary_input())

    assert invalid == []
    assert incomplete == []


def test_replacement_fraction_claims_and_epv_operands_resolve_to_current_registry(
    tmp_path: Path,
) -> None:
    bridge_input, observations, calculations = _replacement_input_with_current_fact_bindings()
    _write_replacement_current_registry(tmp_path, observations, calculations)

    invalid, incomplete = _validate(tmp_path, bridge_input)

    assert invalid == []
    assert incomplete == []


def test_replacement_role_binding_requires_the_source_to_declare_that_role(
    tmp_path: Path,
) -> None:
    bridge_input, observations, calculations = _replacement_input_with_current_fact_bindings()
    customer = bridge_input["replacement_value"]["model_input"]["components"][0]
    customer["evidence_role_bindings"][0]["source_fact_ids"] = [
        "OBS:CUSTOMER-COST:LOW"
    ]
    _write_replacement_current_registry(tmp_path, observations, calculations)

    invalid, incomplete = _validate(tmp_path, bridge_input)

    assert incomplete == []
    assert any(
        "replacement_evidence_role_source_role_mismatch:customer-book:"
        "CONTRACT_POPULATION_OR_CUSTOMER_BOOK:OBS:CUSTOMER-COST:LOW"
        == finding
        for finding in invalid
    )


def test_replacement_exclusion_requires_the_source_to_declare_its_destination(
    tmp_path: Path,
) -> None:
    bridge_input, observations, calculations = _replacement_input_with_current_fact_bindings()
    channel = bridge_input["replacement_value"]["model_input"]["components"][2]
    channel["recognition"] = {
        "status": "EXCLUDED",
        "method": "NOT_APPLICABLE",
        "reason": "The channel capability is asserted to be owned by customer relationships.",
    }
    channel.pop("evidence_role_bindings", None)
    channel["exclusion_treatment"] = {
        "destination": "OTHER_REPLACEMENT_COMPONENT",
        "destination_component_type": "CUSTOMER_RELATIONSHIP",
        "source_fact_ids": ["OBS:ACQUISITION-CHANNEL"],
        "reason": "A source must directly establish that the destination owns this capability.",
    }
    _write_replacement_current_registry(tmp_path, observations, calculations)

    invalid, incomplete = _validate(tmp_path, bridge_input)

    assert incomplete == []
    assert (
        "replacement_exclusion_source_destination_mismatch:acquisition-channel:"
        "OTHER_REPLACEMENT_COMPONENT:OBS:ACQUISITION-CHANNEL"
        in invalid
    )


def test_self_declared_verified_fact_cannot_replace_current_registry_evidence(
    tmp_path: Path,
) -> None:
    _write_verified_observations(tmp_path)
    payload = _ordinary_input()
    fake = "OBS:FAKE:RATE"
    payload["ordinary_distribution"]["model_input"]["verified_facts"][1]["fact_id"] = fake
    payload["ordinary_distribution"]["model_input"]["input_fact_ids"][1] = fake
    payload["canonical_fact_bindings"][1]["evidence_id"] = fake

    invalid, incomplete = _validate(tmp_path, payload)

    assert incomplete == []
    assert any("unknown_or_unverified_evidence:" + fake in item for item in invalid)


def test_altered_operand_cannot_keep_a_real_observation_id(tmp_path: Path) -> None:
    _write_verified_observations(tmp_path)
    payload = _ordinary_input()
    payload["ordinary_distribution"]["model_input"]["fixed_collection_cost"] = 3.0

    invalid, _ = _validate(tmp_path, payload)

    assert any("numeric_value_mismatch:ordinary_distribution.model_input.fixed_collection_cost" in item for item in invalid)


def test_missing_binding_leaves_the_numeric_operand_invalid(tmp_path: Path) -> None:
    _write_verified_observations(tmp_path)
    payload = _ordinary_input()
    payload["canonical_fact_bindings"] = payload["canonical_fact_bindings"][:-1]

    invalid, _ = _validate(tmp_path, payload)

    assert "value_bridge_fact_bindings_operand_unbound:ordinary_distribution.model_input.fixed_collection_cost" in invalid
