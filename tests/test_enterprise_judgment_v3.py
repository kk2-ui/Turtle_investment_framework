from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import enterprise_judgment_v3 as v3


def _units() -> list[dict]:
    return [
        {
            "unit_id": "UNIT:APPLIANCE", "accounting_perimeter": "ISSUER:APPLIANCE",
            "decision_scope": "national channel and product management",
            "economic_carrier": "national household-air-conditioner network",
            "measurement_surface": "national sell-out, contribution and cash",
        },
        {
            "unit_id": "UNIT:PLATFORM", "accounting_perimeter": "ISSUER:PLATFORM",
            "decision_scope": "platform product and monetization management",
            "economic_carrier": "multi-sided digital interface",
            "measurement_surface": "side-specific usage, monetization and service cost",
        },
    ]


def _model() -> dict:
    return {
        "model_id": "ESM:SYNTHETIC", "company_id": "ISSUER:SYNTHETIC", "version": "1",
        "as_of": "2025-12-31T23:59:59+00:00",
        "responsibility_unit_ids": ["UNIT:APPLIANCE", "UNIT:PLATFORM"],
        "competitive_arena_ids": ["ARENA:NATIONAL-APPLIANCE", "ARENA:PLATFORM"],
        "nodes": [
            {"node_id": "NODE:CHANNEL", "observation_state": "OBSERVED", "responsibility_unit_id": "UNIT:APPLIANCE", "measurement_scope_id": "SCOPE:SELL_OUT"},
            {"node_id": "NODE:CASH", "observation_state": "UNKNOWN", "responsibility_unit_id": "UNIT:APPLIANCE", "measurement_scope_id": "SCOPE:OWNER_CASH"},
            {"node_id": "NODE:USERS", "observation_state": "OBSERVED", "responsibility_unit_id": "UNIT:PLATFORM", "measurement_scope_id": "SCOPE:USER_SIDE"},
            {"node_id": "NODE:MERCHANTS", "observation_state": "UNKNOWN", "responsibility_unit_id": "UNIT:PLATFORM", "measurement_scope_id": "SCOPE:MERCHANT_SIDE"},
        ],
        "edges": [
            {"edge_id": "EDGE:CHANNEL-CASH", "from_node_id": "NODE:CHANNEL", "to_node_id": "NODE:CASH", "relationship": "cash_conversion", "actor_side": "CHANNEL", "interface": "sell-out and rebate", "cross_side_effect": "inventory changes cash timing", "measurement_scope_id": "SCOPE:OWNER_CASH", "observation_state": "UNKNOWN"},
            {"edge_id": "EDGE:USER-MERCHANT", "from_node_id": "NODE:USERS", "to_node_id": "NODE:MERCHANTS", "relationship": "cross_side_demand", "actor_side": "USER", "interface": "ad inventory and transaction interface", "cross_side_effect": "user engagement changes merchant demand", "measurement_scope_id": "SCOPE:PLATFORM", "observation_state": "INFERRED"},
        ],
    }


def _national_arena() -> dict:
    return {
        "arena_id": "ARENA:NATIONAL-APPLIANCE", "responsibility_unit_id": "UNIT:APPLIANCE",
        "product_or_service_scope": "household air conditioners", "customer_task": "household cooling",
        "competition_interface": "national brand and channel pricing", "economic_state": "national demand",
        "window": "FY2025", "required_overlap_dimensions": [
            {"dimension": "CUSTOMER_TASK", "relation": "REQUIRED_EQUAL", "rationale": "same household cooling task"},
            {"dimension": "GEOGRAPHIC_NETWORK", "relation": "NOT_REQUIRED", "rationale": "provincial networks need not match in a national market"},
        ], "members": [
            {"member_id": "ISSUER:PEER-NORTH", "role": "EXTERNAL_SHOCK_COMPARATOR", "actor_side": "BRAND", "interface": "national retail", "province_network": "north", "same_treatment_status": "ABSENT", "target_spillover_status": "BOUNDED_NONE", "overlap_evidence": [{"dimension": "CUSTOMER_TASK", "status": "PROVEN"}]},
            {"member_id": "ISSUER:PEER-SOUTH", "role": "EQUILIBRIUM_RESPONSE_WITNESS", "actor_side": "BRAND", "interface": "national retail", "province_network": "south", "overlap_evidence": [{"dimension": "CUSTOMER_TASK", "status": "PROVEN"}]},
        ],
    }


def _cement_arena(*, radius_status: str) -> dict:
    return {
        "arena_id": "ARENA:CEMENT-RADIUS", "responsibility_unit_id": "UNIT:APPLIANCE",
        "product_or_service_scope": "cement", "customer_task": "regional bulk construction supply",
        "competition_interface": "delivered-price and freight radius", "economic_state": "regional capacity utilisation",
        "window": "FY2025", "required_overlap_dimensions": [
            {"dimension": "PRODUCT", "relation": "REQUIRED_EQUAL", "rationale": "same cement product"},
            {"dimension": "TRANSPORT_RADIUS", "relation": "REQUIRED_OVERLAP", "rationale": "delivered price requires freight overlap"},
        ], "members": [
            {"member_id": "ISSUER:CEMENT-PEER", "role": "EQUILIBRIUM_RESPONSE_WITNESS", "actor_side": "PRODUCER", "interface": "delivered price", "overlap_evidence": [{"dimension": "PRODUCT", "status": "PROVEN"}, {"dimension": "TRANSPORT_RADIUS", "status": radius_status}]},
        ],
    }


def _platform_arena() -> dict:
    return {
        "arena_id": "ARENA:PLATFORM", "responsibility_unit_id": "UNIT:PLATFORM",
        "product_or_service_scope": "digital transaction and advertising interface", "customer_task": "discover, transact and monetize",
        "competition_interface": "usage-to-merchant monetization", "economic_state": "platform participation", "window": "FY2025",
        "required_overlap_dimensions": [{"dimension": "INTERFACE", "relation": "REQUIRED_EQUAL", "rationale": "each side uses the same named interface"}],
        "members": [
            {"member_id": "SIDE:USER", "role": "NOT_COMPARABLE", "actor_side": "USER", "interface": "discovery", "overlap_evidence": [{"dimension": "INTERFACE", "status": "PROVEN"}]},
            {"member_id": "SIDE:MERCHANT", "role": "NOT_COMPARABLE", "actor_side": "MERCHANT", "interface": "advertising and payment", "overlap_evidence": [{"dimension": "INTERFACE", "status": "PROVEN"}]},
            {"member_id": "SIDE:DEVELOPER", "role": "NOT_COMPARABLE", "actor_side": "DEVELOPER", "interface": "mini-program distribution", "overlap_evidence": [{"dimension": "INTERFACE", "status": "PROVEN"}]},
        ],
    }


def _frozen_cjo(*, delta: float = 0.0, frozen: bool = True) -> dict:
    return {
        "cjo_id": "CJO:SYNTHETIC",
        "state": {
            "lane": "ENTERPRISE_MODEL", "lifecycle": "FROZEN" if frozen else "REVIEW_READY",
            "resolution": "SELECTIVE_SUPPORT", "permission": "INVESTMENT_INPUT",
            **({"frozen_at": "2025-12-31T23:59:59+00:00"} if frozen else {}),
        },
        "owner_cash_bridge": {
            "status": "CLOSED", "ordinary_share_access_status": "CLOSED", "permanent_loss_status": "ASSESSED",
            "scope_bridge_id": "BRIDGE:APPLIANCE", "evidence_ref": "OBS:SYNTHETIC-D4",
        },
        "driver_register": [{
            "driver_id": "DRIVER:UNIT_ECONOMICS", "normalized_earnings_delta": delta,
            "owner_cash_delta": delta, "scope_bridge_id": "BRIDGE:APPLIANCE",
        }],
    }


def _financial_contract() -> dict:
    return {
        "base_normalized_earnings": 64.0, "base_owner_cash": 50.0,
        "share_count": 1.0, "required_return": 0.10,
        "market_price": 400.0, "holding_years": 3, "annual_distribution": 5.0,
    }


def test_schema_declares_minimal_v3_objects_without_a_platform_model_or_fourth_graph() -> None:
    schema_path = Path("schemas/enterprise_judgment_v3.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == v3.SCHEMA_VERSION
    assert {"enterprise_system_model", "responsibility_units", "competitive_arenas", "management_decision_ledger", "cjo"} <= set(schema["properties"])
    assert "platform_model" not in json.dumps(schema).lower()
    assert "fourth_graph" not in json.dumps(schema).lower()


def test_multiarena_model_preserves_platform_sides_interfaces_and_cross_side_effects() -> None:
    model = _model()
    model_result = v3.validate_enterprise_system_model(model)
    arena_result = v3.validate_competitive_arenas([_national_arena(), _platform_arena()], _units())

    assert model_result["state"] == "VALID"
    assert arena_result["state"] == "VALID"
    assert len(model["competitive_arena_ids"]) == 2
    assert {member["actor_side"] for member in _platform_arena()["members"]} == {"USER", "MERCHANT", "DEVELOPER"}


def test_national_market_does_not_require_same_province_but_regional_cement_requires_transport_overlap() -> None:
    national = v3.validate_competitive_arenas([_national_arena()], _units())
    cement_rejected = v3.validate_competitive_arenas([_cement_arena(radius_status="NOT_PROVEN")], _units())
    cement_admitted = v3.validate_competitive_arenas([_cement_arena(radius_status="PROVEN")], _units())

    assert national["state"] == "VALID"
    assert cement_rejected["state"] == "INVALID"
    assert any("TRANSPORT_RADIUS_not_proven" in item for item in cement_rejected["findings"])
    assert cement_admitted["state"] == "VALID"


@pytest.mark.parametrize("resolution", ["UNKNOWN", "MIXED", "NO_PRIMARY", "NOT_DIAGNOSTIC"])
def test_isolated_resolutions_cannot_leak_into_learning_or_investment(resolution: str) -> None:
    invalid = v3.validate_state_vector({
        "lane": "PIT", "lifecycle": "FROZEN", "resolution": resolution,
        "permission": "LEARNING_ELIGIBLE", "frozen_at": "2025-12-31T23:59:59+00:00",
    })
    valid = v3.validate_state_vector({
        "lane": "BOUNDARY", "lifecycle": "FROZEN", "resolution": resolution,
        "permission": "TEACHING_ONLY", "frozen_at": "2025-12-31T23:59:59+00:00",
    })

    assert invalid["state"] == "INVALID"
    assert "isolated_resolution_must_be_teaching_only" in invalid["findings"]
    assert valid["state"] == "VALID"


def test_state_machine_requires_frozen_directional_pit_for_learning() -> None:
    draft = {"lane": "PIT", "lifecycle": "DRAFT", "resolution": "NO_PRIMARY", "permission": "TEACHING_ONLY"}
    open_state = {"lane": "PIT", "lifecycle": "EVIDENCE_OPEN", "resolution": "NO_PRIMARY", "permission": "TEACHING_ONLY"}
    directional = {"lane": "PIT", "lifecycle": "FROZEN", "resolution": "A_ONLY", "permission": "LEARNING_ELIGIBLE", "frozen_at": "2025-12-31T23:59:59+00:00"}

    assert v3.transition_state_vector(draft, open_state)["state"] == "VALID"
    assert v3.validate_state_vector(directional)["state"] == "INVALID"
    directional["settlement_receipt"] = "SETTLEMENT:SYNTHETIC"
    directional["independent_review_receipt"] = "REVIEW:SYNTHETIC"
    assert v3.validate_state_vector(directional)["state"] == "VALID"
    assert v3.transition_state_vector(draft, directional)["state"] == "INVALID"


def test_pit_blocked_and_holdout_lanes_cannot_be_relabelled_as_consumable_inputs() -> None:
    blocked = v3.validate_state_vector({
        "lane": "PIT", "lifecycle": "REOPENED", "resolution": "PIT_BLOCKED", "permission": "TEACHING_ONLY",
    })
    remediation = v3.validate_state_vector({
        "lane": "PIT", "lifecycle": "REOPENED", "resolution": "PIT_BLOCKED", "permission": "REMEDIATION_ONLY",
    })
    holdout_leak = v3.validate_state_vector({
        "lane": "HOLDOUT", "lifecycle": "FROZEN", "resolution": "A_ONLY", "permission": "INVESTMENT_INPUT", "frozen_at": "2025-12-31T23:59:59+00:00",
    })

    assert blocked["state"] == "INVALID"
    assert remediation["state"] == "VALID"
    assert holdout_leak["state"] == "INVALID"


def _episode(*, evidence: list[dict] | None = None) -> dict:
    return {
        "episode_id": "EP:SYNTHETIC", "cutoff_at": "2025-01-01T00:00:00+00:00", "observed_at": "2025-12-31T00:00:00+00:00",
        "action_ref": "ACTION:SYNTHETIC", "responsibility_unit_id": "UNIT:APPLIANCE", "competitive_arena_id": "ARENA:NATIONAL-APPLIANCE",
        "hypothesis_registry_ref": "HREG:SYNTHETIC", "measurement_contract_ref": "MEASURE:SYNTHETIC", "ledger_decision_id": "DEC:SYNTHETIC",
        "state": {"lane": "BOUNDARY", "lifecycle": "FROZEN", "resolution": "MIXED", "permission": "TEACHING_ONLY", "frozen_at": "2025-12-31T00:00:00+00:00"}, "resolution": "MIXED",
        "declared_node_ids": ["NODE:CHANNEL", "NODE:CASH"], "declared_edge_ids": ["EDGE:CHANNEL-CASH"],
        "node_updates": [{"node_id": "NODE:CASH", "observation_state": "CONTRADICTED", **({"evidence": evidence} if evidence else {})}],
        "edge_updates": [{"edge_id": "EDGE:CHANNEL-CASH", "observation_state": "CONTRADICTED"}],
    }


def test_episode_only_updates_declared_local_model_delta() -> None:
    model = _model()
    ledger = {"ledger_id": "MDL:SYNTHETIC", "entries": [{
        "decision_id": "DEC:SYNTHETIC", "cutoff_at": "2024-12-31T00:00:00+00:00", "decision_type": "OPERATING",
        "ex_ante": {"decision_quality": "INDETERMINATE", "objective": "improve channel", "alternatives": ["hold"], "known_unknowns": ["cash timing"], "commitment": "implement"},
    }]}
    result = v3.apply_episode_delta(model, _episode(), ledger=ledger)

    updated = result["model"]
    assert updated["nodes"][1]["observation_state"] == "CONTRADICTED"
    assert updated["nodes"][2]["observation_state"] == "OBSERVED"
    assert result["local_delta"]["node_ids"] == ["NODE:CASH"]
    assert "company_quality" not in updated
    assert result["management_decision_ledger"]["entries"][0]["outcome_overlay"]["episode_id"] == "EP:SYNTHETIC"
    with pytest.raises(v3.EnterpriseJudgmentError, match="outside_declared_local_delta"):
        v3.apply_episode_delta(model, {
            "episode_id": "EP:OVERREACH", "cutoff_at": "2025-01-01T00:00:00+00:00", "observed_at": "2025-12-31T00:00:00+00:00",
            "action_ref": "ACTION:SYNTHETIC", "responsibility_unit_id": "UNIT:APPLIANCE", "competitive_arena_id": "ARENA:NATIONAL-APPLIANCE",
            "hypothesis_registry_ref": "HREG:SYNTHETIC", "measurement_contract_ref": "MEASURE:SYNTHETIC", "ledger_decision_id": "DEC:SYNTHETIC",
            "state": {"lane": "BOUNDARY", "lifecycle": "FROZEN", "resolution": "A_ONLY", "permission": "TEACHING_ONLY", "frozen_at": "2025-12-31T00:00:00+00:00"}, "resolution": "A_ONLY", "declared_node_ids": ["NODE:CHANNEL"], "declared_edge_ids": [],
            "node_updates": [{"node_id": "NODE:CASH", "observation_state": "OBSERVED"}], "edge_updates": [],
        })


def test_episode_delta_rejects_future_evidence_at_the_write_boundary() -> None:
    with pytest.raises(v3.EnterpriseJudgmentError, match="episode_delta_creates_invalid_model"):
        v3.apply_episode_delta(_model(), _episode(evidence=[{"ref": "DOC:FUTURE", "available_at": "2026-01-01T00:00:00+00:00"}]))


def test_management_ledger_separates_ex_ante_quality_from_later_outcome() -> None:
    ledger = {"ledger_id": "MDL:SYNTHETIC", "entries": [{
        "decision_id": "DEC:ONE", "cutoff_at": "2021-10-31T00:00:00+00:00", "decision_type": "CAPITAL_ALLOCATION",
        "ex_ante": {"decision_quality": "INDETERMINATE", "objective": "enter adjacent market", "alternatives": ["do nothing"], "known_unknowns": ["unit economics"], "commitment": "acquire control"},
        "outcome_overlay": {"observed_at": "2022-08-01T00:00:00+00:00", "outcome": "loss observed"},
    }]}
    assert v3.validate_management_decision_ledger(ledger)["state"] == "VALID"

    contaminated = deepcopy(ledger)
    contaminated["entries"][0]["ex_ante"]["outcome"] = "later loss"
    result = v3.validate_management_decision_ledger(contaminated)
    assert result["state"] == "INVALID"
    assert "ledger.entries[0].outcome_cannot_be_ex_ante" in result["findings"]


def test_bundle_rejects_group_cash_attached_to_an_unbridged_local_business() -> None:
    cjo = _frozen_cjo()
    cjo["model_id"] = "ESM:SYNTHETIC"
    cjo["scope_bridge_id"] = "BRIDGE:APPLIANCE"
    cjo["driver_register"][0]["responsibility_unit_id"] = "UNIT:APPLIANCE"
    bridge = {
        "scope_bridge_id": "BRIDGE:APPLIANCE", "bridge_type": "IDENTITY", "responsibility_unit_id": "UNIT:APPLIANCE",
        "decision_scope_ref": "DECISION:NATIONAL", "economic_carrier_ref": "CARRIER:NATIONAL", "measurement_surface_ref": "SCOPE:OWNER_CASH",
        "accounting_perimeter_ref": "ISSUER:APPLIANCE", "permitted_conclusion_scope": "national appliance owner cash",
    }
    bundle = {
        "schema_version": v3.SCHEMA_VERSION, "enterprise_system_model": _model(), "responsibility_units": _units(),
        "competitive_arenas": [_national_arena(), _platform_arena()], "scope_bridges": [bridge], "cjo": cjo,
        "management_decision_ledger": {"ledger_id": "MDL:SYNTHETIC", "entries": [{
            "decision_id": "DEC:SYNTHETIC", "cutoff_at": "2024-12-31T00:00:00+00:00", "decision_type": "OPERATING",
            "ex_ante": {"decision_quality": "INDETERMINATE", "objective": "improve channel", "alternatives": ["hold"], "known_unknowns": ["cash timing"], "commitment": "implement"},
        }]},
    }
    assert v3.validate_enterprise_judgment_bundle(bundle)["state"] == "VALID"
    projections = v3.project_enterprise_judgment_graphs(bundle)
    assert set(projections) == {"evidence_graph", "mechanism_graph", "investment_graph"}
    assert projections["investment_graph"]["scope_bridge_id"] == "BRIDGE:APPLIANCE"

    group_cash = deepcopy(bundle)
    group_cash["cjo"]["driver_register"][0]["responsibility_unit_id"] = "UNIT:PLATFORM"
    result = v3.validate_enterprise_judgment_bundle(group_cash)
    assert result["state"] == "INVALID"
    assert "cjo.drivers[0].responsibility_unit_does_not_match_scope_bridge" in result["findings"]

    unresolved = deepcopy(bundle)
    unresolved["cjo"]["state"] = {"lane": "ENTERPRISE_MODEL", "lifecycle": "FROZEN", "resolution": "MIXED", "permission": "TEACHING_ONLY", "frozen_at": "2025-12-31T23:59:59+00:00"}
    unresolved["cjo"]["owner_cash_bridge"]["status"] = "UNKNOWN"
    assert v3.validate_enterprise_judgment_bundle(unresolved)["state"] == "VALID"


def test_hypothesis_matrix_has_diagnosticity_but_no_score() -> None:
    registry = {
        "hypotheses": [
            {"hypothesis_id": "H:A", "status": "ACTIVE", "mechanism": "customer response"},
            {"hypothesis_id": "H:B", "status": "ACTIVE", "mechanism": "common demand shock"},
        ],
        "diagnostic_matrix": [{"diagnosticity": "COMMON", "cells": {"H:A": "COMPATIBLE", "H:B": "COMPATIBLE"}}],
    }
    assert v3.validate_hypothesis_registry(registry)["state"] == "VALID"
    registry["diagnostic_matrix"][0]["score"] = 9
    assert v3.validate_hypothesis_registry(registry)["state"] == "INVALID"


def test_research_policy_only_prioritises_material_discriminating_questions() -> None:
    high = v3.route_research_question({
        "question_id": "RQ:CASH", "materiality": "HIGH", "can_change_cjo_or_owner_cash": True,
        "diagnosticity": "DISCRIMINATING", "official_source_available": True,
    })
    background = v3.route_research_question({
        "question_id": "RQ:BACKGROUND", "materiality": "HIGH", "can_change_cjo_or_owner_cash": False,
        "diagnosticity": "DISCRIMINATING", "official_source_available": True,
    })
    common = v3.route_research_question({
        "question_id": "RQ:COMMON", "materiality": "HIGH", "can_change_cjo_or_owner_cash": True,
        "diagnosticity": "COMMON", "official_source_available": True,
    })

    assert high == {"priority": "HIGH", "findings": []}
    assert background["priority"] == "LOW"
    assert common["priority"] == "STOP"


def test_transport_rejects_surface_similarity_and_admits_only_observed_relationship_transfer() -> None:
    surface = {
        "surface_similarity": ["manufacturing", "same province"], "source_structure": [{"from_node_type": "capacity", "to_node_type": "cash", "relationship": "changes", "interface": "plant"}],
        "invariants": [{"relationship": "capacity changes cash", "rationale": "synthetic"}], "target_differences": [{"dimension": "maintenance capex", "effect": "higher"}], "moderators": [{"condition": "transport radius", "effect": "local"}],
        "required_target_observations": [{"observation_id": "OBS:UTIL", "status": "OBSERVED"}],
        "break_conditions": [{"condition": "different task", "triggered": False}], "permitted_changes": ["measurement_contract.transport_radius"],
    }
    relational = deepcopy(surface)
    relational.pop("surface_similarity")
    relational["source_structure"] = [{"from_node_type": "interface_usage", "to_node_type": "service_cost", "relationship": "changes_unit_economics", "interface": "usage billing"}]
    relational["invariants"] = [{"relationship": "interface usage changes unit economics", "rationale": "both systems expose the interface"}]

    assert v3.validate_transport_contract(surface)["state"] == "TEACHING_ONLY"
    assert v3.validate_transport_contract(relational)["state"] == "PRE_APPLICATION"


def test_frozen_cjo_drives_normalized_earnings_owner_cash_expectation_gap_and_buy_band() -> None:
    neutral = v3.compile_production_buy_band(_frozen_cjo(delta=0.0), _financial_contract())
    improved = v3.compile_production_buy_band(_frozen_cjo(delta=16.0), _financial_contract())

    assert improved["normalized_earnings"] > neutral["normalized_earnings"]
    assert improved["owner_cash"] > neutral["owner_cash"]
    assert improved["expectation_gap"] > neutral["expectation_gap"]
    assert improved["buy_band"]["upper"] > neutral["buy_band"]["upper"]
    assert neutral["price_implied_owner_cash"] == pytest.approx(51.585, abs=0.001)
    assert neutral["expectation_gap"] < 0
    assert improved["expectation_gap"] > 0
    with pytest.raises(v3.EnterpriseJudgmentError, match="requires_frozen"):
        v3.compile_production_buy_band(_frozen_cjo(frozen=False), _financial_contract())
    no_d4 = _frozen_cjo()
    no_d4["owner_cash_bridge"]["status"] = "UNKNOWN"
    with pytest.raises(v3.EnterpriseJudgmentError, match="independent_d4"):
        v3.compile_production_buy_band(no_d4, _financial_contract())
