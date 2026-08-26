"""Synthetic V5 end-to-end tests using one immutable selection bundle.

These tests deliberately pass the exact same object through admission, the
Slice-1 control plane, and raw-matrix outcome reconstruction.  They do not
exercise real issuers, external sources, R-103, R-104, or a production DB.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pytest

from scripts import enterprise_judgment_v3 as enterprise_v3
from scripts import judgment_selection_v5 as admission
from scripts import judgment_v5_control_plane as control
from scripts.judgment_selection_v5_outcome import resolve_v5_outcome
from tests.test_judgment_selection_v5 import _bundle as _admitted_bundle
from tests.test_judgment_selection_v5 import _refresh_reviewed_selection_contract
from tests.test_judgment_v5_control_plane import _register_synthetic_preselection_receipts


def _bundle(*, freeze_id: str, topology: str = "CUSTOMER_RESPONSE") -> dict:
    bundle = deepcopy(_admitted_bundle(topology=topology))
    bundle["selection_freeze_id"] = freeze_id
    bundle["candidate_id"] = f"SYNV5:CANDIDATE:{freeze_id}"
    bundle["episode_collision_key"] = f"SYNV5:COLLISION:{freeze_id}"
    _refresh_reviewed_selection_contract(bundle)
    return bundle


@pytest.fixture
def conn(tmp_path):
    connection = control.connect(tmp_path / "v5-end-to-end.db")
    control.initialize(connection)
    _register_synthetic_preselection_receipts(connection)
    yield connection
    connection.close()


def _metrics(bundle: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    by_clock = {metric["clock"]: metric for metric in bundle["measurement_contracts"]}
    by_id = {metric["metric_id"]: metric for metric in bundle["measurement_contracts"]}
    return by_clock, by_id


def _d3_value(field_id: str, *, primary: bool, direction: str) -> float:
    if not primary:
        return {"revenue": 100.0, "operating_cost": 60.0}[field_id]
    if direction == "A":
        return {"revenue": 120.0, "operating_cost": 65.0}[field_id]
    if direction == "B":
        return {"revenue": 100.0, "operating_cost": 70.0}[field_id]
    return {"revenue": 104.0, "operating_cost": 62.0}[field_id]


def _d4_value(field_id: str, *, primary: bool, direction: str) -> float:
    ocf = 100.0
    if primary:
        ocf = {"A": 130.0, "B": 70.0}.get(direction, 102.0)
    fields = {
        "cash_from_operating_activities": ocf,
        "cash_paid_for_all_long_lived_asset_purchases": 10.0,
        "beginning_accounts_receivable": 20.0,
        "beginning_prepayments": 0.0,
        "beginning_inventory": 20.0,
        "beginning_accounts_payable": 15.0,
        "beginning_contract_liabilities_or_customer_advances": 5.0,
        "ending_accounts_receivable": 20.0,
        "ending_prepayments": 0.0,
        "ending_inventory": 20.0,
        "ending_accounts_payable": 15.0,
        "ending_contract_liabilities_or_customer_advances": 5.0,
    }
    return fields[field_id]


def _raw_receipts(
    bundle: dict,
    *,
    target_d3: str = "A",
    target_d4: str = "A",
    omit: tuple[str, str, str, str] | None = None,
) -> dict:
    by_clock, by_id = _metrics(bundle)
    target = bundle["counterfactual_panel"]["target_issuer_id"]
    cells: list[dict] = []
    for row in bundle["outcome_contract"]["frozen_raw_matrix"]:
        metric = by_id[row["metric_id"]]
        clock = metric["clock"]
        primary = row["period_id"] == metric["primary_outcome_period_id"]
        direction = (
            (target_d3 if clock == "D3" else target_d4)
            if row["issuer_id"] == target
            else "PEER"
        )
        key = (row["issuer_id"], clock, row["period_id"], row["field_id"])
        if omit == key:
            continue
        value = (
            _d3_value(row["field_id"], primary=primary, direction=direction)
            if clock == "D3"
            else _d4_value(row["field_id"], primary=primary, direction=direction)
        )
        cells.append({
            "issuer_id": row["issuer_id"],
            "clock": clock,
            "metric_id": row["metric_id"],
            "period_id": row["period_id"],
            "field_id": row["field_id"],
            "value": value,
            "source": {
                "source_id": f"SYNV5:OUTCOME:{row['issuer_id']}:{clock}:{row['period_id']}:{row['field_id']}",
                "source_available_at": (
                    "2022-04-30T08:00:00+00:00" if primary else "2020-04-30T08:00:00+00:00"
                ),
                "availability_precision": "INTRADAY",
                "filing_identity": "INITIAL",
            },
        })
    return {
        "schema_version": "judgment-v5-outcome-receipts.v1",
        "custodian_attestation": {
            "custodian_id": "SYNV5:CUSTODIAN",
            "research_side_outcome_exposure": "NONE",
        },
        "raw_cells": cells,
    }


def _authorize(conn, freeze_id: str) -> None:
    control.authorize_outcome_access(conn, {
        "selection_freeze_id": freeze_id,
        "authorization_id": f"SYNV5:AUTH:{freeze_id}",
        "custodian_id": "SYNV5:CUSTODIAN",
        "actor_id": "SYNV5:PREOUTCOME_REVIEWER",
        "effective_at": "2022-01-15T00:00:00+00:00",
    })


def _package_receipt(bundle: dict) -> dict:
    freeze_id = bundle["selection_freeze_id"]
    _by_clock, by_id = _metrics(bundle)
    inventory = []
    for row in bundle["outcome_contract"]["frozen_raw_matrix"]:
        metric = by_id[row["metric_id"]]
        if row["period_id"] != metric["primary_outcome_period_id"]:
            continue
        inventory.append({
            "source_id": f"SYNV5:OUTCOME:{row['issuer_id']}:{metric['clock']}:{row['period_id']}:{row['field_id']}",
            "source_available_at": "2022-04-30T08:00:00+00:00",
            "availability_precision": "INTRADAY",
        })
    return {
        "selection_freeze_id": freeze_id,
        "receipt_id": f"SYNV5:PACKAGE:{freeze_id}",
        "receipt_kind": "OUTCOME_PACKAGE",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T00:00:00+00:00",
        "payload": {"actual_outcome_inventory": inventory},
    }


def _append_extraction_path(conn, bundle: dict) -> None:
    freeze_id = bundle["selection_freeze_id"]
    control.append_control_receipt(conn, _package_receipt(bundle))
    control.append_control_receipt(conn, {
        "selection_freeze_id": freeze_id,
        "receipt_id": f"SYNV5:READER:{freeze_id}",
        "receipt_kind": "OUTCOME_READER",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T01:00:00+00:00",
        "payload": {},
    })
    control.append_control_receipt(conn, {
        "selection_freeze_id": freeze_id,
        "receipt_id": f"SYNV5:EXTRACTION:{freeze_id}",
        "receipt_kind": "OUTCOME_EXTRACTION",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T02:00:00+00:00",
        "payload": {},
    })


def _enterprise_prestate(bundle: dict) -> tuple[dict, dict, dict]:
    """Build a separate, offline V3 pre-state that names the V5 frozen scope.

    The objects remain separate on purpose: V5 owns the one canonical selection
    bundle, while V3 owns the enterprise/episode model that made it admissible.
    """
    cutoff = bundle["time_contract"]["research_cutoff_at"]
    action = bundle["action_scope"]
    bridge = bundle["scope_bridges"][0]
    arena = bundle["competitive_arena"]
    model = {
        "model_id": "ESM:SYNV5:TARGET",
        "company_id": action["focal_issuer_id"],
        "version": "preoutcome-1",
        "as_of": cutoff,
        "responsibility_unit_ids": ["UNIT:SYNV5:ISSUER"],
        "competitive_arena_ids": [arena["competitive_arena_id"]],
        "nodes": [
            {
                "node_id": "NODE:SYNV5:CHANNEL",
                "observation_state": "OBSERVED",
                "responsibility_unit_id": "UNIT:SYNV5:ISSUER",
                "measurement_scope_id": "SCOPE:SYNV5:D3",
            },
            {
                "node_id": "NODE:SYNV5:CASH",
                "observation_state": "UNKNOWN",
                "responsibility_unit_id": "UNIT:SYNV5:ISSUER",
                "measurement_scope_id": "SCOPE:SYNV5:D4",
            },
        ],
        "edges": [{
            "edge_id": "EDGE:SYNV5:CHANNEL-CASH",
            "from_node_id": "NODE:SYNV5:CHANNEL",
            "to_node_id": "NODE:SYNV5:CASH",
            "relationship": "cash_conversion",
            "actor_side": "ISSUER",
            "interface": "national network",
            "cross_side_effect": "network changes cash timing",
            "measurement_scope_id": "SCOPE:SYNV5:D4",
            "observation_state": "UNKNOWN",
        }],
    }
    enterprise_bundle = {
        "schema_version": enterprise_v3.SCHEMA_VERSION,
        "enterprise_system_model": model,
        "responsibility_units": [{
            "unit_id": "UNIT:SYNV5:ISSUER",
            "accounting_perimeter": bridge["metric_perimeter_ids"][0],
            "decision_scope": action["action_id"],
            "economic_carrier": action["economic_carriers"][0]["carrier_id"],
            "measurement_surface": "issuer operating contribution and owner cash",
        }],
        "competitive_arenas": [{
            "arena_id": arena["competitive_arena_id"],
            "responsibility_unit_id": "UNIT:SYNV5:ISSUER",
            "product_or_service_scope": arena["product_or_service_scope"],
            "customer_task": arena["customer_choice_or_cost_driver"],
            "competition_interface": "national customer choice",
            "economic_state": "synthetic national demand",
            "window": "PREOUTCOME",
            "required_overlap_dimensions": [{
                "dimension": "CUSTOMER_TASK",
                "relation": "REQUIRED_EQUAL",
                "rationale": "same named customer choice",
            }],
            "members": [{
                "member_id": "ISSUER:PEER1",
                "role": "EXTERNAL_SHOCK_COMPARATOR",
                "actor_side": "ISSUER",
                "interface": "national network",
                "same_treatment_status": "ABSENT",
                "target_spillover_status": "BOUNDED_NONE",
                "overlap_evidence": [{"dimension": "CUSTOMER_TASK", "status": "PROVEN"}],
            }],
        }],
        "scope_bridges": [{
            "scope_bridge_id": bridge["scope_bridge_id"],
            "bridge_type": "IDENTITY",
            "responsibility_unit_id": "UNIT:SYNV5:ISSUER",
            "decision_scope_ref": action["action_id"],
            "economic_carrier_ref": action["economic_carriers"][0]["carrier_id"],
            "measurement_surface_ref": "SCOPE:SYNV5:D4",
            "accounting_perimeter_ref": bridge["metric_perimeter_ids"][0],
            "permitted_conclusion_scope": bridge["permitted_conclusion_scope"],
        }],
        "management_decision_ledger": {
            "ledger_id": "MDL:SYNV5:TARGET",
            "entries": [{
                "decision_id": action["action_id"],
                "cutoff_at": cutoff,
                "decision_type": "OPERATING",
                "ex_ante": {
                    "decision_quality": "INDETERMINATE",
                    "objective": "improve contribution and cash",
                    "alternatives": ["hold network"],
                    "known_unknowns": ["cash transmission"],
                    "commitment": "implemented network",
                },
            }],
        },
        "cjo": {
            "cjo_id": "CJO:SYNV5:PRESTATE",
            "model_id": model["model_id"],
            "scope_bridge_id": bridge["scope_bridge_id"],
            "state": {
                "lane": "ENTERPRISE_MODEL",
                "lifecycle": "FROZEN",
                "resolution": "SELECTIVE_SUPPORT",
                "permission": "TEACHING_ONLY",
                "frozen_at": cutoff,
            },
            "owner_cash_bridge": {
                "status": "UNKNOWN",
                "scope_bridge_id": bridge["scope_bridge_id"],
            },
            "driver_register": [{
                "driver_id": "DRIVER:SYNV5:NETWORK",
                "responsibility_unit_id": "UNIT:SYNV5:ISSUER",
                "scope_bridge_id": bridge["scope_bridge_id"],
                "normalized_earnings_delta": 1.0,
                "owner_cash_delta": 0.5,
            }],
        },
    }
    hypotheses = {
        "registry_id": "HREG:SYNV5:NETWORK",
        "hypotheses": [
            {"hypothesis_id": action["h_a"]["hypothesis_id"], "status": "ACTIVE", "mechanism": action["h_a"]["mechanism"]},
            {"hypothesis_id": action["h_b"]["hypothesis_id"], "status": "ACTIVE", "mechanism": action["h_b"]["mechanism"]},
        ],
        "diagnostic_matrix": [{
            "diagnosticity": "DISCRIMINATING",
            "cells": {
                action["h_a"]["hypothesis_id"]: "EXPECTED",
                action["h_b"]["hypothesis_id"]: "CONTRADICTORY",
            },
        }],
    }
    episode = {
        "episode_id": "EP:SYNV5:PREOUTCOME",
        "cutoff_at": cutoff,
        "observed_at": cutoff,
        "action_ref": action["action_id"],
        "responsibility_unit_id": "UNIT:SYNV5:ISSUER",
        "competitive_arena_id": arena["competitive_arena_id"],
        "hypothesis_registry_ref": hypotheses["registry_id"],
        "measurement_contract_ref": bundle["selection_freeze_id"],
        "ledger_decision_id": action["action_id"],
        "state": {
            "lane": "PIT",
            "lifecycle": "FROZEN",
            "resolution": "SELECTIVE_SUPPORT",
            "permission": "TEACHING_ONLY",
            "frozen_at": cutoff,
        },
        "resolution": "SELECTIVE_SUPPORT",
        "declared_node_ids": ["NODE:SYNV5:CASH"],
        "declared_edge_ids": ["EDGE:SYNV5:CHANNEL-CASH"],
        "node_updates": [{"node_id": "NODE:SYNV5:CASH", "observation_state": "OBSERVED"}],
        "edge_updates": [{"edge_id": "EDGE:SYNV5:CHANNEL-CASH", "observation_state": "OBSERVED"}],
    }
    return enterprise_bundle, hypotheses, episode


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _v3_v5_contract_findings(enterprise_bundle: dict, hypotheses: dict, episode: dict, selection_bundle: dict) -> list[str]:
    """Test-only cross-contract assertions; no second V5 object is produced."""
    findings: list[str] = []
    v3_result = enterprise_v3.validate_enterprise_judgment_bundle(enterprise_bundle)
    if v3_result["state"] != "VALID":
        findings.extend(f"v3_bundle:{item}" for item in v3_result["findings"])
    hypothesis_result = enterprise_v3.validate_hypothesis_registry(hypotheses)
    if hypothesis_result["state"] != "VALID":
        findings.extend(f"hypotheses:{item}" for item in hypothesis_result["findings"])
    episode_result = enterprise_v3.validate_decision_episode(enterprise_bundle["enterprise_system_model"], episode)
    if episode_result["state"] != "VALID":
        findings.extend(f"episode:{item}" for item in episode_result["findings"])
    v5_result = admission.validate_v5_candidate(selection_bundle)
    if not v5_result["valid"]:
        findings.extend(f"v5_bundle:{item}" for item in v5_result["findings"])
    if findings:
        return findings

    model = enterprise_bundle["enterprise_system_model"]
    cjo = enterprise_bundle["cjo"]
    action = selection_bundle["action_scope"]
    panel = selection_bundle["counterfactual_panel"]
    v3_bridge = enterprise_bundle["scope_bridges"][0]
    v5_bridge = next(
        (item for item in selection_bundle["scope_bridges"] if item["scope_bridge_id"] == v3_bridge["scope_bridge_id"]),
        None,
    )
    if model["company_id"] != action["focal_issuer_id"] or panel["target_issuer_id"] != model["company_id"]:
        findings.append("issuer_identity_mismatch")
    if _instant(model["as_of"]) > _instant(selection_bundle["time_contract"]["research_cutoff_at"]):
        findings.append("v3_model_after_v5_cutoff")
    if cjo["model_id"] != model["model_id"] or cjo["state"]["permission"] == "INVESTMENT_INPUT":
        findings.append("cjo_is_not_preoutcome_teaching_state")
    if (
        episode["action_ref"] != action["action_id"]
        or episode["ledger_decision_id"] != action["action_id"]
        or episode["measurement_contract_ref"] != selection_bundle["selection_freeze_id"]
    ):
        findings.append("episode_action_ledger_or_freeze_mismatch")
    expected_episode_state = ("PIT", "FROZEN", "SELECTIVE_SUPPORT", "TEACHING_ONLY")
    actual_episode_state = tuple(episode["state"].get(field) for field in ("lane", "lifecycle", "resolution", "permission"))
    if actual_episode_state != expected_episode_state:
        findings.append("episode_is_not_frozen_preoutcome_teaching_state")
    hypothesis_ids = {item["hypothesis_id"] for item in hypotheses["hypotheses"]}
    if episode["hypothesis_registry_ref"] != hypotheses["registry_id"] or {
        action["h_a"]["hypothesis_id"], action["h_b"]["hypothesis_id"],
    } - hypothesis_ids:
        findings.append("hypothesis_registry_or_pair_mismatch")
    if episode["competitive_arena_id"] != selection_bundle["competitive_arena"]["competitive_arena_id"]:
        findings.append("competitive_arena_identity_mismatch")
    if v5_bridge is None:
        findings.append("scope_bridge_identity_mismatch")
        return findings
    if (
        v3_bridge["economic_carrier_ref"] != action["economic_carriers"][0]["carrier_id"]
        or v3_bridge["accounting_perimeter_ref"] not in v5_bridge["metric_perimeter_ids"]
        or v3_bridge["permitted_conclusion_scope"] != v5_bridge["permitted_conclusion_scope"]
    ):
        findings.append("scope_bridge_economic_boundary_mismatch")
    for metric in selection_bundle["measurement_contracts"]:
        if (
            metric["scope_bridge_id"] != v3_bridge["scope_bridge_id"]
            or metric["carrier_or_segment_id"] != v3_bridge["economic_carrier_ref"]
            or metric["accounting_perimeter_id"] != v3_bridge["accounting_perimeter_ref"]
            or metric["allowed_conclusion_scope"] != v3_bridge["permitted_conclusion_scope"]
        ):
            findings.append(f"{metric['clock'].lower()}_scope_or_cash_boundary_mismatch")
    return findings


@pytest.mark.parametrize(
    ("topology", "direction", "expected"),
    [
        ("CUSTOMER_RESPONSE", "A", "A_ONLY"),
        ("COST_RESTRUCTURING", "A", "A_ONLY"),
        ("CUSTOMER_RESPONSE", "B", "B_ONLY"),
    ],
)
def test_same_bundle_runs_admission_seal_authorized_raw_reconstruction_and_directional_terminal_state(
    conn, topology: str, direction: str, expected: str,
) -> None:
    freeze_id = f"SYNV5:FREEZE:{topology}:{direction}"
    bundle = _bundle(freeze_id=freeze_id, topology=topology)

    assert admission.validate_v5_candidate(bundle) == {
        "valid": True, "admission_status": "SELECTION_ADMITTED", "findings": [],
    }
    assert control.seal_freeze(conn, bundle)["sealed"] is True
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)

    outcome_receipts = _raw_receipts(bundle, target_d3=direction, target_d4=direction)
    outcome = resolve_v5_outcome(bundle, outcome_receipts)
    assert outcome["valid"] is True
    assert outcome["resolution"]["status"] == expected
    request = {
        "selection_freeze_id": freeze_id,
        "resolution_id": f"SYNV5:RESOLUTION:{freeze_id}",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T03:00:00+00:00",
        "outcome_receipts": outcome_receipts,
    }
    first = control.resolve(conn, request)
    replay = control.resolve(conn, request)
    assert replay["idempotent"] is True
    assert replay["event"]["event_id"] == first["event"]["event_id"]
    assert conn.execute(
        "SELECT COUNT(*) FROM judgment_v5_events WHERE selection_freeze_id = ? AND event_type = 'OUTCOME_RESOLVED'",
        (freeze_id,),
    ).fetchone()[0] == 1
    assert control.status(conn, freeze_id)["terminal_state"] == expected


def test_same_bundle_records_mixed_without_directional_upgrade(conn) -> None:
    freeze_id = "SYNV5:FREEZE:MIXED"
    bundle = _bundle(freeze_id=freeze_id)
    assert admission.validate_v5_candidate(bundle)["admission_status"] == "SELECTION_ADMITTED"
    control.seal_freeze(conn, bundle)
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)

    outcome_receipts = _raw_receipts(bundle, target_d3="A", target_d4="B")
    outcome = resolve_v5_outcome(bundle, outcome_receipts)
    assert outcome["resolution"]["status"] == "MIXED"
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": freeze_id,
            "resolution_id": "SYNV5:RESOLUTION:FORGED-A",
            "resolution_status": "A_ONLY",
            "actor_id": "SYNV5:CUSTODIAN",
            "effective_at": "2022-05-01T03:00:00+00:00",
            "outcome_receipts": outcome_receipts,
        })
    assert exc_info.value.code == "caller_resolution_status_forbidden"
    request = {
        "selection_freeze_id": freeze_id,
        "resolution_id": "SYNV5:RESOLUTION:MIXED",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T03:00:00+00:00",
        "outcome_receipts": outcome_receipts,
    }
    control.resolve(conn, request)
    assert control.resolve(conn, request)["idempotent"] is True
    assert control.status(conn, freeze_id)["terminal_state"] == "MIXED"


def test_resolution_rejects_raw_receipts_from_a_different_custodian(conn) -> None:
    freeze_id = "SYNV5:FREEZE:WRONG-CUSTODIAN"
    bundle = _bundle(freeze_id=freeze_id)
    control.seal_freeze(conn, bundle)
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)
    outcome_receipts = _raw_receipts(bundle, target_d3="A", target_d4="A")
    outcome_receipts["custodian_attestation"]["custodian_id"] = "SYNV5:OTHER-CUSTODIAN"

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": freeze_id,
            "resolution_id": "SYNV5:RESOLUTION:WRONG-CUSTODIAN",
            "actor_id": "SYNV5:CUSTODIAN",
            "effective_at": "2022-05-01T03:00:00+00:00",
            "outcome_receipts": outcome_receipts,
        })

    assert exc_info.value.code == "outcome_receipts_custodian_mismatch"
    assert control.status(conn, freeze_id)["terminal_state"] is None


def test_reviewer_cannot_submit_raw_outcome_receipts_for_resolution(conn) -> None:
    freeze_id = "SYNV5:FREEZE:REVIEWER-RESOLUTION"
    bundle = _bundle(freeze_id=freeze_id)
    control.seal_freeze(conn, bundle)
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)
    outcome_receipts = _raw_receipts(bundle, target_d3="A", target_d4="A")

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": freeze_id,
            "resolution_id": "SYNV5:RESOLUTION:REVIEWER",
            "actor_id": "SYNV5:REVIEWER",
            "effective_at": "2022-05-01T03:00:00+00:00",
            "outcome_receipts": outcome_receipts,
        })

    assert exc_info.value.code == "custodian_mismatch"
    assert control.status(conn, freeze_id)["terminal_state"] is None


def test_resolution_rejects_unregistered_primary_outcome_source(conn) -> None:
    freeze_id = "SYNV5:FREEZE:UNREGISTERED-SOURCE"
    bundle = _bundle(freeze_id=freeze_id)
    control.seal_freeze(conn, bundle)
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)
    outcome_receipts = _raw_receipts(bundle, target_d3="A", target_d4="A")
    primary_cell = next(
        cell for cell in outcome_receipts["raw_cells"]
        if cell["period_id"] == _metrics(bundle)[1][cell["metric_id"]]["primary_outcome_period_id"]
    )
    primary_cell["source"]["source_id"] = "SYNV5:UNREGISTERED:PRIMARY"

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": freeze_id,
            "resolution_id": "SYNV5:RESOLUTION:UNREGISTERED-SOURCE",
            "actor_id": "SYNV5:CUSTODIAN",
            "effective_at": "2022-05-01T03:00:00+00:00",
            "outcome_receipts": outcome_receipts,
        })

    assert exc_info.value.code == "outcome_source_not_in_registered_package"
    assert control.status(conn, freeze_id)["terminal_state"] is None


def test_second_outcome_package_cannot_expand_the_registered_source_set(conn) -> None:
    freeze_id = "SYNV5:FREEZE:PACKAGE-EXPANSION"
    bundle = _bundle(freeze_id=freeze_id)
    control.seal_freeze(conn, bundle)
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)
    expansion = _package_receipt(bundle)
    expansion["receipt_id"] = "SYNV5:PACKAGE:EXPANSION"
    expansion["effective_at"] = "2022-05-01T02:30:00+00:00"
    expansion["payload"]["actual_outcome_inventory"] = [{
        "source_id": "SYNV5:EXPANDED:PRIMARY",
        "source_available_at": "2022-04-30T08:00:00+00:00",
        "availability_precision": "INTRADAY",
    }]

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.append_control_receipt(conn, expansion)
    assert exc_info.value.code == "outcome_package_already_registered"

    outcome_receipts = _raw_receipts(bundle, target_d3="A", target_d4="A")
    primary_cell = next(
        cell for cell in outcome_receipts["raw_cells"]
        if cell["period_id"] == _metrics(bundle)[1][cell["metric_id"]]["primary_outcome_period_id"]
    )
    primary_cell["source"]["source_id"] = "SYNV5:EXPANDED:PRIMARY"
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": freeze_id,
            "resolution_id": "SYNV5:RESOLUTION:PACKAGE-EXPANSION",
            "actor_id": "SYNV5:CUSTODIAN",
            "effective_at": "2022-05-01T03:00:00+00:00",
            "outcome_receipts": outcome_receipts,
        })
    assert exc_info.value.code == "outcome_source_not_in_registered_package"
    assert control.status(conn, freeze_id)["terminal_state"] is None


def test_resolution_rejects_unregistered_boundary_fact_source(conn) -> None:
    freeze_id = "SYNV5:FREEZE:UNREGISTERED-BOUNDARY"
    bundle = _bundle(freeze_id=freeze_id)
    control.seal_freeze(conn, bundle)
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)
    outcome_receipts = _raw_receipts(bundle, target_d3="A", target_d4="A")
    outcome_receipts["boundary_facts"] = [{
        "boundary_kind": "SCOPE",
        "reason": "synthetic boundary receipt",
        "source": {
            "source_id": "SYNV5:UNREGISTERED:BOUNDARY",
            "source_available_at": "2022-04-30T08:00:00+00:00",
            "availability_precision": "INTRADAY",
            "filing_identity": "INITIAL",
        },
    }]

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": freeze_id,
            "resolution_id": "SYNV5:RESOLUTION:UNREGISTERED-BOUNDARY",
                "actor_id": "SYNV5:CUSTODIAN",
            "effective_at": "2022-05-01T03:00:00+00:00",
            "outcome_receipts": outcome_receipts,
        })

    assert exc_info.value.code == "outcome_source_not_in_registered_package"
    assert control.status(conn, freeze_id)["terminal_state"] is None


def test_missing_frozen_cell_resolves_unknown_and_cannot_be_promoted(conn) -> None:
    freeze_id = "SYNV5:FREEZE:UNKNOWN"
    bundle = _bundle(freeze_id=freeze_id)
    metrics, _ = _metrics(bundle)
    d4 = metrics["D4"]
    missing = (
        bundle["counterfactual_panel"]["members"][1]["issuer_id"],
        "D4",
        d4["primary_outcome_period_id"],
        "ending_inventory",
    )
    outcome_receipts = _raw_receipts(bundle, omit=missing)
    outcome = resolve_v5_outcome(bundle, outcome_receipts)
    assert outcome["resolution"]["status"] == "UNKNOWN"

    control.seal_freeze(conn, bundle)
    _authorize(conn, freeze_id)
    control.append_control_receipt(conn, _package_receipt(bundle))
    control.append_control_receipt(conn, {
        "selection_freeze_id": freeze_id,
        "receipt_id": "SYNV5:MISSING:UNKNOWN",
        "receipt_kind": "MISSING_CELL",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T01:00:00+00:00",
        "payload": {},
    })
    request = {
        "selection_freeze_id": freeze_id,
        "resolution_id": "SYNV5:RESOLUTION:UNKNOWN",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T02:00:00+00:00",
        "outcome_receipts": outcome_receipts,
    }
    control.resolve(conn, request)
    assert control.resolve(conn, request)["idempotent"] is True
    assert control.status(conn, freeze_id)["terminal_state"] == "UNKNOWN"


def test_no_primary_cannot_create_freeze_or_gain_outcome_access(conn) -> None:
    bundle = _bundle(freeze_id="SYNV5:FREEZE:NO-PRIMARY")
    bundle["action_scope"]["implementation_status"] = "PLANNED"
    _refresh_reviewed_selection_contract(bundle)

    assert admission.validate_v5_candidate(bundle)["admission_status"] == "NO_PRIMARY"
    sealed = control.seal_freeze(conn, bundle)
    assert sealed == {"sealed": False, "admission_status": "NO_PRIMARY", "findings": ["action_not_implemented"]}
    assert conn.execute("SELECT COUNT(*) FROM judgment_v5_selection_freezes").fetchone()[0] == 0


def test_v3_synthetic_prestate_binds_to_the_unchanged_v5_canonical_lifecycle(conn) -> None:
    """One offline scenario proves the contracts compose without a wrapper object."""
    freeze_id = "SYNV5:FREEZE:V3-INTEGRATION"
    bundle = _bundle(freeze_id=freeze_id)
    enterprise_bundle, hypotheses, episode = _enterprise_prestate(bundle)

    assert _v3_v5_contract_findings(enterprise_bundle, hypotheses, episode, bundle) == []
    delta = enterprise_v3.apply_episode_delta(enterprise_bundle["enterprise_system_model"], episode)
    assert delta["local_delta"] == {
        "episode_id": episode["episode_id"],
        "resolution": "SELECTIVE_SUPPORT",
        "node_ids": ["NODE:SYNV5:CASH"],
        "edge_ids": ["EDGE:SYNV5:CHANNEL-CASH"],
    }
    assert delta["model"]["nodes"][0]["observation_state"] == "OBSERVED"
    assert delta["model"]["nodes"][1]["observation_state"] == "OBSERVED"
    with pytest.raises(enterprise_v3.EnterpriseJudgmentError, match="investment_eligible_cjo"):
        enterprise_v3.compile_production_buy_band(enterprise_bundle["cjo"], {})

    assert admission.validate_v5_candidate(bundle)["admission_status"] == "SELECTION_ADMITTED"
    assert control.seal_freeze(conn, bundle)["sealed"] is True
    _authorize(conn, freeze_id)
    _append_extraction_path(conn, bundle)
    outcome_receipts = _raw_receipts(bundle, target_d3="A", target_d4="A")
    outcome = resolve_v5_outcome(bundle, outcome_receipts)
    assert outcome["resolution"]["status"] == "A_ONLY"
    control.resolve(conn, {
        "selection_freeze_id": freeze_id,
        "resolution_id": "SYNV5:RESOLUTION:V3-INTEGRATION",
        "actor_id": "SYNV5:CUSTODIAN",
        "effective_at": "2022-05-01T03:00:00+00:00",
        "outcome_receipts": outcome_receipts,
    })
    assert control.status(conn, freeze_id)["terminal_state"] == "A_ONLY"
    # V5's later result must not rewrite V3's frozen pre-outcome teaching state.
    assert enterprise_bundle["cjo"]["state"]["permission"] == "TEACHING_ONLY"


def test_v3_prestate_mismatch_stops_cross_contract_admission_before_v5_seal() -> None:
    bundle = _bundle(freeze_id="SYNV5:FREEZE:V3-MISMATCH")

    late_enterprise, late_hypotheses, late_episode = _enterprise_prestate(bundle)
    late_enterprise["enterprise_system_model"]["as_of"] = "2021-01-01T00:00:00+00:00"
    assert "v3_model_after_v5_cutoff" in _v3_v5_contract_findings(
        late_enterprise, late_hypotheses, late_episode, bundle,
    )

    blocked_enterprise, blocked_hypotheses, blocked_episode = _enterprise_prestate(bundle)
    blocked_episode["state"] = {
        "lane": "PIT", "lifecycle": "REOPENED", "resolution": "PIT_BLOCKED",
        "permission": "REMEDIATION_ONLY",
    }
    blocked_episode["resolution"] = "PIT_BLOCKED"
    assert "episode_is_not_frozen_preoutcome_teaching_state" in _v3_v5_contract_findings(
        blocked_enterprise, blocked_hypotheses, blocked_episode, bundle,
    )

    wrong_scope, wrong_hypotheses, wrong_episode = _enterprise_prestate(bundle)
    for item in wrong_scope["scope_bridges"]:
        item["scope_bridge_id"] = "BRIDGE:SYNV5:WRONG"
    wrong_scope["cjo"]["scope_bridge_id"] = "BRIDGE:SYNV5:WRONG"
    wrong_scope["cjo"]["owner_cash_bridge"]["scope_bridge_id"] = "BRIDGE:SYNV5:WRONG"
    wrong_scope["cjo"]["driver_register"][0]["scope_bridge_id"] = "BRIDGE:SYNV5:WRONG"
    assert "scope_bridge_identity_mismatch" in _v3_v5_contract_findings(
        wrong_scope, wrong_hypotheses, wrong_episode, bundle,
    )
