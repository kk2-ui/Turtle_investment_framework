from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts import judgment_selection_v5 as v5
from scripts import judgment_v5_control_plane as control
from tests.test_judgment_selection_discovery import _h2_action_screen_extension


_REVIEWED_SELECTION_FIELDS = (
    "schema_version", "candidate_id", "method_epoch_id", "selection_goal", "selection_freeze_id",
    "episode_collision_key", "sealed_at", "recorded_at", "cohort_snapshot", "action_scope",
    "scope_bridges", "competitive_arena", "external_driver_reference", "counterfactual_panel",
    "measurement_contracts", "time_contract", "outcome_contract", "materiality_and_resolution_contract",
    "source_manifest", "source_provenance", "source_firewall_receipt",
)

_V5_H1_MEMBER_IDENTITIES = {
    "ISSUER:TARGET": {
        "company_id": "CN:TARGET",
        "issuer_id": "ISSUER:TARGET",
        "responsibility_unit_id": "UNIT:TARGET",
        "control_group_id": "CONTROL:TARGET",
    },
    **{
        f"ISSUER:PEER{index}": {
            "company_id": f"CN:PEER{index}",
            "issuer_id": f"ISSUER:PEER{index}",
            "responsibility_unit_id": f"UNIT:PEER{index}",
            "control_group_id": f"CONTROL:PEER{index}",
        }
        for index in range(1, 5)
    },
}
_H2_ACTION_SOURCE_ID = "ACTION:ISSUER-SCOPE"
_SYNTHETIC_STATIC_SOURCE_BY_ID: dict[str, dict] | None = None


def _source_id(issuer_id: str, kind: str, period_end: str | None = None) -> str:
    role = issuer_id.removeprefix("ISSUER:")
    return ":".join(part for part in ("SRC", role, kind, period_end) if part)


def _refresh_reviewed_selection_contract(bundle: dict) -> None:
    bundle["independent_pre_outcome_review"]["reviewed_selection_contract"] = {
        field: deepcopy(bundle[field]) for field in _REVIEWED_SELECTION_FIELDS
    }


def _source(source_id: str, lane: str, when: str) -> dict:
    # The canonical root must reproduce identity from the registered H1/H2
    # static PDF, not just cite its caller-chosen source ID.
    static_source = _synthetic_static_source_by_id().get(source_id)
    if static_source is not None:
        published_at = static_source["published_at"]
        return {
            "source_id": source_id,
            "source_lane": lane,
            "publisher": control.STATIC_CNINFO_PUBLISHER,
            "official_artifact_id": source_id,
            "source_url": static_source["url"],
            "source_type": static_source["source_type"],
            "issuer_id": static_source["issuer_id"],
            "responsibility_unit_id": static_source["responsibility_unit_id"],
            "perimeter_id": static_source["perimeter_id"],
            "unit": static_source["unit"],
            "published_at_or_date": published_at,
            "availability_precision": "DATE_ONLY" if len(published_at) == 10 else "INTRADAY",
            "outcome_visibility": "PREOUTCOME_VISIBLE",
        }
    return {
        "source_id": source_id,
        "source_lane": lane,
        "publisher": "Synthetic official publisher",
        "official_artifact_id": f"ART:{source_id}",
        "source_url": f"https://static.cninfo.com.cn/finalpage/synthetic/{source_id}.PDF",
        "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": "ISSUER:SYNTHETIC",
        "responsibility_unit_id": "UNIT:SYNTHETIC",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "unit": "RMB",
        "published_at_or_date": when,
        "availability_precision": "INTRADAY",
        "outcome_visibility": "PREOUTCOME_VISIBLE",
    }


def _synthetic_static_source_by_id() -> dict[str, dict]:
    """Cache immutable synthetic H1/H2 declarations while returning fresh root rows."""
    global _SYNTHETIC_STATIC_SOURCE_BY_ID
    if _SYNTHETIC_STATIC_SOURCE_BY_ID is None:
        h1_receipt, h2_receipt = _synthetic_preselection_receipt_envelopes()
        declared = [
            *h1_receipt["stage0_static_package"]["static_pdf_sources"],
            *h2_receipt["action_screen_extension"]["static_pdf_sources"],
        ]
        _SYNTHETIC_STATIC_SOURCE_BY_ID = {
            source["source_id"]: source for source in declared
        }
    return _SYNTHETIC_STATIC_SOURCE_BY_ID


def _threshold(value: float = 1.0, *, operator: str = "GTE") -> dict:
    return {"operator": operator, "value": value, "unit": "RMB"}


def _metric(clock: str) -> dict:
    common = {
        "metric_id": f"METRIC:{clock}",
        "clock": clock,
        "accounting_perimeter_id": "PERIM:ISSUER",
        "carrier_or_segment_id": "CARRIER:ISSUER",
        "scope_bridge_id": "BRIDGE:ISSUER",
        "currency_and_unit": "RMB",
        "period_basis": "FISCAL_YEAR",
        "gross_or_net_definition": "same disclosed consolidated basis",
        "restatement_or_reclassification_policy": "INITIAL_ONLY",
        "baseline_observation_matrix": {"periods": ["2017", "2018", "2019", "2020"]},
        "primary_outcome_matrix": {"outcome_window_id": "OUTCOME:2021", "required_raw_cells": "predeclared"},
        "source_available_at_policy": "custodian reads only after authorization",
        "allowed_conclusion_scope": "issuer operating and cash mechanism",
        "baseline_period_id": "FY0",
        "primary_outcome_period_id": "FY1",
        "discriminability": {
            "status": "SUPPORTED",
            "primary_threshold": _threshold(10.0),
            "rival_threshold": _threshold(-10.0, operator="LTE"),
        },
    }
    if clock == "D3":
        return common | {
            "economic_construct": "OPERATING_CONTRIBUTION_AMOUNT",
            "formula_id": "D3_OPERATING_CONTRIBUTION_V1",
            "formula_and_ordered_raw_fields": ["revenue", "operating_cost"],
            "outcome_formula": {
                "formula_type": "LINEAR_COMBINATION",
                "terms": [
                    {"field_id": "revenue", "coefficient": 1.0},
                    {"field_id": "operating_cost", "coefficient": -1.0},
                ],
            },
            "raw_field_source_locators": [
                {"field_id": "revenue", "allowed_source_class": "OFFICIAL_ANNUAL_REPORT"},
                {"field_id": "operating_cost", "allowed_source_class": "OFFICIAL_ANNUAL_REPORT"},
            ],
        }
    return common | {
        "economic_construct": "CONSERVATIVE_OWNER_CASH",
        "formula_id": v5.D4_FORMULA_ID,
        "formula_and_ordered_raw_fields": list(v5.D4_REQUIRED_RAW_FIELDS),
        "raw_field_source_locators": [
            {"field_id": field_id, "allowed_source_class": "OFFICIAL_ANNUAL_REPORT"}
            for field_id in v5.D4_REQUIRED_RAW_FIELDS
        ],
        "cash_working_capital_components": sorted(v5.D4_CASH_WORKING_CAPITAL_COMPONENTS),
        "restructuring_cash_treatment": "IN_OCF_NO_ADDITIONAL_DEDUCTION",
    }


def _frozen_raw_matrix(metrics: list[dict]) -> list[dict]:
    cells: list[dict] = []
    for metric in metrics:
        for issuer_id in ("ISSUER:TARGET", "ISSUER:PEER1", "ISSUER:PEER2", "ISSUER:PEER3"):
            for period_id, role, economic_period in (
                ("FY0", "BASELINE", {"start": "2019-01-01T00:00:00+00:00", "end": "2019-12-31T00:00:00+00:00"}),
                ("FY1", "PRIMARY_OUTCOME", {"start": "2021-01-01T00:00:00+00:00", "end": "2021-12-31T00:00:00+00:00"}),
            ):
                for field_id in metric["formula_and_ordered_raw_fields"]:
                    cells.append({
                        "issuer_id": issuer_id,
                        "metric_id": metric["metric_id"],
                        "period_id": period_id,
                        "observation_role": role,
                        "field_id": field_id,
                        "economic_period": economic_period,
                        "perimeter_id": "PERIM:ISSUER",
                        "currency_and_unit": "RMB",
                        "field_locator": f"predeclared:{metric['metric_id']}:{field_id}",
                    })
    return cells


def _cohort_member(issuer: str, group: str) -> dict:
    identity = _V5_H1_MEMBER_IDENTITIES[issuer]
    assert identity["control_group_id"] == group
    return {
        "company_id": identity["company_id"],
        "issuer_id": issuer,
        "responsibility_unit_id": identity["responsibility_unit_id"],
        "control_group_id": group,
        "boundary": {
            "responsibility_unit_id": identity["responsibility_unit_id"],
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
        },
        "carrier_identity_source_ids": [_source_id(issuer, "CARRIER")],
        "d2_or_cost_field_history": [
            {
                "period_end": f"201{year}-12-31",
                "field_id": "D2_OR_COST",
                "source_id": _source_id(issuer, "D2", f"201{year}-12-31"),
            }
            for year in (7, 8, 9)
        ],
        "d3_d4_field_history": [
            {
                "period_end": f"20{year}-12-31",
                "field_id": "D3_D4",
                "source_id": _source_id(issuer, "D3D4", f"20{year}-12-31"),
            }
            for year in (15, 16, 17, 18, 19)
        ],
    }


def _root_source_manifest() -> list[dict]:
    source_ids = [_H2_ACTION_SOURCE_ID, "SRC:ARENA"]
    for issuer_id in ("ISSUER:TARGET", "ISSUER:PEER1", "ISSUER:PEER2", "ISSUER:PEER3"):
        source_ids.extend([
            _source_id(issuer_id, "CARRIER"),
            *(_source_id(issuer_id, "D2", f"201{year}-12-31") for year in (7, 8, 9)),
            *(_source_id(issuer_id, "D3D4", f"20{year}-12-31") for year in (15, 16, 17, 18, 19)),
        ])
    return [
        _source(
            source_id,
            "ACTION_STATIC" if source_id == _H2_ACTION_SOURCE_ID
            else "PUBLIC_ARENA_CONTEXT" if source_id == "SRC:ARENA"
            else "STAGE0_STATIC",
            "2020-01-01T00:00:00+00:00",
        )
        for source_id in source_ids
    ]


def _comparator(issuer: str, group: str) -> dict:
    return {
        "issuer_id": issuer,
        "control_group_id": group,
        "causal_role": "EXTERNAL_SHOCK_COMPARATOR",
        "mechanism_arena_membership": {"status": "NOT_REQUIRED", "source_ids": ["SRC:ARENA"]},
        "external_driver_reference_membership": {"status": "PROVEN", "source_ids": ["SRC:ARENA"]},
        "shared_driver_exposure": "PROVEN",
        "parallel_action": "BOUNDED_ABSENT",
        "target_action_spillover": "BOUNDED_NONINTERFERENCE",
        "eligible_for_relative_baseline": True,
        "source_ids": ["SRC:ARENA"],
    }


def _canonical_bundle(
    *,
    freeze_id: str = "V5FREEZE:one",
    collision_key: str = "COLLISION:ISSUER:TARGET:ACTION:NETWORK:CARRIER:ISSUER:OUTCOME:2021",
    predecessor_freeze_id: str | None = None,
) -> dict:
    """A real Slice-0 admitted candidate plus the four canonical root IDs."""
    metrics = [_metric("D3"), _metric("D4")]
    bundle = {
        "schema_version": v5.SCHEMA_VERSION,
        "candidate_id": "SYNV5:CANDIDATE:BASE",
        "method_epoch_id": v5.METHOD_EPOCH_ID,
        "selection_goal": "SELECTION",
        "selection_freeze_id": freeze_id,
        "episode_collision_key": collision_key,
        "sealed_at": "2021-01-01T00:00:00+00:00",
        "recorded_at": "2021-01-01T01:00:00+00:00",
        "cohort_snapshot": {
            "cohort_snapshot_id": "SYNV5:COHORT:BASE",
            "cohort_eligibility_as_of": "2020-03-31T23:59:59+00:00",
            "arena_family": "SYNTHETIC_NATIONAL_DURABLE_GOODS",
            "members": [
                _cohort_member("ISSUER:TARGET", "CONTROL:TARGET"),
                _cohort_member("ISSUER:PEER1", "CONTROL:PEER1"),
                _cohort_member("ISSUER:PEER2", "CONTROL:PEER2"),
                _cohort_member("ISSUER:PEER3", "CONTROL:PEER3"),
            ],
        },
        "action_scope": {
            "action_id": "ACTION:NETWORK",
            "focal_issuer_id": "ISSUER:TARGET",
            "mechanism_topology": "CUSTOMER_RESPONSE",
            "d2_role": "CENTRAL_VOTER",
            "decision_authority": "ISSUER_MANAGEMENT",
            "implementation_status": "IMPLEMENTED",
            "action_effective_window": {"start": "2020-04-01T00:00:00+00:00", "end_or_ongoing_status": "ONGOING"},
            "decision_observable_at": "2020-05-01T00:00:00+00:00",
            "economic_carriers": [{
                "carrier_id": "CARRIER:ISSUER",
                "functional_type": "national service and cost network",
                "legal_or_operating_owner": "ISSUER:TARGET",
                "implementation_source_ids": [_H2_ACTION_SOURCE_ID],
            }],
            "d2_observations": [{"period": year, "source_id": _H2_ACTION_SOURCE_ID} for year in (2017, 2018, 2019)],
            "h_a": {"hypothesis_id": "H:A", "mechanism": "implemented network improves contribution and cash", "central_endpoint_predictions": {"D3": "IMPROVE", "D4": "IMPROVE"}},
            "h_b": {"hypothesis_id": "H:B", "mechanism": "network does not improve contribution or cash", "central_endpoint_predictions": {"D3": "NO_IMPROVEMENT", "D4": "NO_IMPROVEMENT"}},
            "source_ids": [_H2_ACTION_SOURCE_ID],
        },
        "scope_bridges": [{
            "scope_bridge_id": "BRIDGE:ISSUER",
            "bridge_type": "IDENTITY",
            "decision_to_carrier_source_ids": [_H2_ACTION_SOURCE_ID],
            "carrier_to_perimeter_source_ids": [_H2_ACTION_SOURCE_ID],
            "carrier_perimeter_ids": ["PERIM:ISSUER"],
            "metric_perimeter_ids": ["PERIM:ISSUER"],
            "economic_rights_type": "FULLY_CONSOLIDATED",
            "action_cash_boundary": "all action-associated cash remains in consolidated cash flow",
            "permitted_conclusion_scope": "issuer operating and cash mechanism",
            "coverage_basis": "NOT_APPLICABLE_FULL_PERIMETER",
            "implementation_scope": "FULL_METRIC_PERIMETER",
            "carrier_reporting_basis": "CONSOLIDATED_ISSUER",
            "metric_reporting_basis": "CONSOLIDATED_ISSUER",
        }],
        "competitive_arena": {
            "competitive_arena_id": "ARENA:NATIONAL",
            "market_scope_type": "NATIONAL",
            "product_or_service_scope": "synthetic durable goods",
            "customer_choice_or_cost_driver": "national customer choice and input cost",
            "required_overlap_dimensions": [
                {"dimension": "PRODUCT", "relation": "REQUIRED_EQUAL", "rationale_from_mechanism": "same customer choice", "target_evidence_source_ids": ["SRC:ARENA"], "peer_evidence_source_ids": ["SRC:ARENA"]},
                {"dimension": "GEOGRAPHIC_MARKET", "relation": "NOT_REQUIRED", "rationale_from_mechanism": "provincial network need not match", "target_evidence_source_ids": ["SRC:ARENA"], "peer_evidence_source_ids": ["SRC:ARENA"]},
            ],
        },
        "external_driver_reference": {
            "external_driver_reference_id": "DRIVER:NATIONAL-DEMAND",
            "driver_description": "national demand and input-cost exposure",
            "required_exposure_dimensions": [{"dimension": "COST_DRIVER", "relation": "REQUIRED_EXPOSURE", "rationale_from_mechanism": "same input cost transmission", "target_evidence_source_ids": ["SRC:ARENA"], "peer_evidence_source_ids": ["SRC:ARENA"]}],
            "target_driver_exposure_source_ids": ["SRC:ARENA"],
        },
        "counterfactual_panel": {
            "counterfactual_panel_id": "PANEL:BASE",
            "target_issuer_id": "ISSUER:TARGET",
            "members": [
                _comparator("ISSUER:PEER1", "CONTROL:PEER1"),
                _comparator("ISSUER:PEER2", "CONTROL:PEER2"),
                _comparator("ISSUER:PEER3", "CONTROL:PEER3"),
            ],
            "non_replacement_rule": "no peer may be replaced after freeze",
        },
        "measurement_contracts": metrics,
        "time_contract": {
            "cohort_eligibility_as_of": "2020-03-31T23:59:59+00:00",
            "action_effective_window": {"start": "2020-04-01T00:00:00+00:00", "end_or_ongoing_status": "ONGOING"},
            "decision_observable_at": "2020-05-01T00:00:00+00:00",
            "research_cutoff_at": "2020-12-31T23:59:59+00:00",
            "metric_economic_periods": {
                "D3": {"start": "2021-01-01T00:00:00+00:00", "end": "2021-12-31T00:00:00+00:00"},
                "D4": {"start": "2021-01-01T00:00:00+00:00", "end": "2021-12-31T00:00:00+00:00"},
            },
            "outcome_window_id": "OUTCOME:2021",
            "minimum_decision_exposure_rule": "first full fiscal year after implementation",
        },
        "outcome_contract": {
            "frozen_raw_matrix": _frozen_raw_matrix(metrics),
            "fiscal_calendar_bridge": {"status": "NOT_REQUIRED"},
        },
        "materiality_and_resolution_contract": {
            "decision_materiality": {"status": "SUPPORTED", "evidence_source_ids": [_H2_ACTION_SOURCE_ID]},
            "d3_outcome_discriminability": {"status": "SUPPORTED", "primary_threshold": _threshold(10), "rival_threshold": _threshold(-10, operator="LTE")},
            "d4_outcome_discriminability": {"status": "SUPPORTED", "primary_threshold": _threshold(10), "rival_threshold": _threshold(-10, operator="LTE")},
            "investor_materiality": {"status": "UNKNOWN"},
        },
        "source_manifest": _root_source_manifest(),
        "source_provenance": {
            "h1": {
                "receipt_id": "SYNV5:H1:BASE",
                "receipt_version": 1,
                "cohort_id": "SYNV5:COHORT:BASE",
                "selection_as_of": "2020-03-31T23:59:59+00:00",
                "curator_id": "SYNV5:CURATOR",
            },
            "h2": {
                "receipt_id": "SYNV5:H2:NETWORK",
                "receipt_version": 1,
                "parent_receipt_id": "SYNV5:H1:BASE",
                "parent_receipt_version": 1,
                "screen_id": "H2:SYNTHETIC:NETWORK:20201231",
                "cutoff_at": "2020-12-31T23:59:59+00:00",
            },
        },
        "source_firewall_receipt": {
            "receipt_id": "SYNV5:FIREWALL:BASE",
            "researcher_id": "SYNV5:RESEARCHER",
            "attested_at": "2020-12-31T23:00:00+00:00",
            "researcher_outcome_body_access": "NONE",
            "researcher_outcome_metadata_access": "NONE",
            "outcome_access_authorized": False,
        },
        "independent_pre_outcome_review": {
            "review_id": "SYNV5:REVIEW:BASE",
            "pre_outcome_designer_id": "SYNV5:RESEARCHER",
            "reviewer_id": "SYNV5:REVIEWER",
            "reviewed_at": "2021-01-01T00:00:00+00:00",
            "verdict": "ACCEPTED",
            "reviewed_selection_contract": {},
            "reviewer_outcome_body_access": "NONE",
            "reviewer_outcome_metadata_access": "NONE",
        },
    }
    _refresh_reviewed_selection_contract(bundle)
    if predecessor_freeze_id is not None:
        bundle["predecessor_freeze_id"] = predecessor_freeze_id
    return bundle


def _authorize(freeze_id: str, *, at: str = "2021-03-01T00:00:00+00:00") -> dict:
    return {
        "selection_freeze_id": freeze_id,
        "authorization_id": f"AUTH:{freeze_id}",
        "custodian_id": "custodian-a",
        "actor_id": "reviewer-a",
        "effective_at": at,
    }


def _receipt(
    freeze_id: str, kind: str, *, receipt_id: str, at: str,
    actor_id: str = "custodian-a", payload: dict | None = None,
) -> dict:
    return {
        "selection_freeze_id": freeze_id,
        "receipt_id": receipt_id,
        "receipt_kind": kind,
        "actor_id": actor_id,
        "effective_at": at,
        "payload": payload or {},
    }


def _post_cutoff_inventory() -> list[dict]:
    return [{
        "source_id": "SYNV5:OUTCOME:2021",
        "availability_precision": "INTRADAY",
        "source_available_at": "2021-03-01T00:00:00+00:00",
    }]


def _replace_source_id(value: object, *, old: str, new: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "source_id" and nested == old:
                value[key] = new
            else:
                _replace_source_id(nested, old=old, new=new)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if item == old:
                value[index] = new
            else:
                _replace_source_id(item, old=old, new=new)


def _replace_text(value: object, mapping: dict[str, str]) -> object:
    if isinstance(value, dict):
        return {key: _replace_text(nested, mapping) for key, nested in value.items()}
    if isinstance(value, list):
        return [_replace_text(item, mapping) for item in value]
    return mapping.get(value, value) if isinstance(value, str) else value


def _relabel_stage0_and_h2_for_v5_root(stage0: dict, extension: dict) -> None:
    """Make the strict discovery fixture the exact H1 parent of this V5 root."""
    original_stage0 = deepcopy(stage0)
    original_extension = deepcopy(extension)
    original_members = list(original_stage0["members"])
    value_mapping: dict[str, str] = {}
    for original, target in zip(original_members, _V5_H1_MEMBER_IDENTITIES.values(), strict=True):
        value_mapping.update({
            original["company_id"]: target["company_id"],
            original["issuer_id"]: target["issuer_id"],
            original["responsibility_unit_id"]: target["responsibility_unit_id"],
            original["control_group_id"]: target["control_group_id"],
        })
    stage0.clear()
    stage0.update(_replace_text(original_stage0, value_mapping))
    extension.clear()
    extension.update(_replace_text(original_extension, value_mapping))

    source_id_mapping: dict[str, str] = {}
    for index, (member, target) in enumerate(zip(stage0["members"], _V5_H1_MEMBER_IDENTITIES.values(), strict=True)):
        issuer_id = target["issuer_id"]
        industry_source_id = member["industry_business_evidence"][0]["source_id"]
        source_id_mapping[industry_source_id] = "SRC:ARENA" if index == 4 else _source_id(issuer_id, "CARRIER")
        history = member.get("d2_field_availability") or member.get("cost_field_availability")
        for repetition in history["repetitions"]:
            source_id_mapping[repetition["evidence"][0]["source_id"]] = _source_id(
                issuer_id, "D2", repetition["period_end"],
            )
        for annual in member["annual_d3_d4_availability"]:
            source_id_mapping[annual["evidence"][0]["source_id"]] = _source_id(
                issuer_id, "D3D4", annual["period_end"],
            )
    for old, new in source_id_mapping.items():
        _replace_source_id(stage0, old=old, new=new)
        _replace_source_id(extension, old=old, new=new)

def _synthetic_preselection_receipt_envelopes() -> tuple[dict, dict]:
    """Build strict synthetic H1/H2 payloads that own this test root's IDs."""
    stage0, extension = _h2_action_screen_extension()
    _relabel_stage0_and_h2_for_v5_root(stage0, extension)
    selection_as_of = "2020-03-31T23:59:59+00:00"
    stage0["cohort_id"] = "SYNV5:COHORT:BASE"
    stage0["selection_as_of"] = selection_as_of
    stage0["cohort_eligibility_as_of"] = selection_as_of
    stage0["curator_attestation"]["curator_id"] = "SYNV5:CURATOR"
    extension["stage0_cohort_id"] = stage0["cohort_id"]
    extension["stage0_selection_as_of"] = selection_as_of
    extension["curator_id"] = "SYNV5:CURATOR"
    extension["cutoff_at"] = "2020-12-31T23:59:59+00:00"

    h1_receipt = {
        "receipt_id": "SYNV5:H1:BASE",
        "receipt_version": 1,
        "recorded_at": "2021-01-01T01:00:00+00:00",
        "stage0_static_package": stage0,
    }
    h2_receipt = {
        "receipt_id": "SYNV5:H2:NETWORK",
        "receipt_version": 1,
        "recorded_at": "2021-01-01T01:00:00+00:00",
        "h1_receipt_id": "SYNV5:H1:BASE",
        "h1_receipt_version": 1,
        "action_screen_extension": extension,
    }
    return h1_receipt, h2_receipt


def _register_synthetic_preselection_receipts(conn) -> None:
    h1_receipt, h2_receipt = _synthetic_preselection_receipt_envelopes()
    control.register_h1_static_cohort_receipt(conn, h1_receipt)
    control.register_h2_action_screen_receipt(conn, h2_receipt)


@pytest.fixture
def conn(tmp_path):
    connection = control.connect(tmp_path / "v5-control.db")
    control.initialize(connection)
    _register_synthetic_preselection_receipts(connection)
    yield connection
    connection.close()


def _seal(conn, bundle: dict) -> dict:
    return control.seal_freeze(conn, bundle)


def test_canonical_root_bundle_really_passes_slice0_validator() -> None:
    assert v5.validate_v5_candidate(_canonical_bundle()) == {
        "valid": True,
        "admission_status": v5.SELECTION_ADMITTED,
        "findings": [],
    }


def test_seal_rejects_bundle_without_an_accepted_independent_preoutcome_review(conn) -> None:
    bundle = _canonical_bundle()
    bundle["independent_pre_outcome_review"]["verdict"] = "REJECTED"

    result = control.seal_freeze(conn, bundle)

    assert result == {
        "sealed": False,
        "admission_status": v5.NOT_ADMITTED,
        "findings": ["review_not_accepted"],
    }
    assert conn.execute("SELECT COUNT(*) FROM judgment_v5_selection_freezes").fetchone()[0] == 0


@pytest.mark.parametrize("forbidden_custodian", ["SYNV5:RESEARCHER", "SYNV5:REVIEWER"])
def test_authorization_requires_a_custodian_distinct_from_preoutcome_roles(conn, forbidden_custodian: str) -> None:
    _seal(conn, _canonical_bundle())
    authorization = _authorize("V5FREEZE:one")
    authorization["custodian_id"] = forbidden_custodian

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.authorize_outcome_access(conn, authorization)

    assert exc_info.value.code == "outcome_custodian_role_conflict"
    assert control.status(conn, "V5FREEZE:one")["authorized"] is False


def test_initialize_creates_the_v5_receipt_and_slice1_tables(conn) -> None:
    tables = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'judgment_v5_%'"
        )
    }
    assert tables == {
        "judgment_v5_preselection_receipts",
        "judgment_v5_selection_freezes",
        "judgment_v5_events",
    }


def test_h1_h2_receipts_are_strict_parent_bound_immutable_and_idempotent(tmp_path) -> None:
    connection = control.connect(tmp_path / "v5-receipts.db")
    control.initialize(connection)
    h1_receipt, h2_receipt = _synthetic_preselection_receipt_envelopes()

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.register_h2_action_screen_receipt(connection, h2_receipt)
    assert exc_info.value.code == "preselection_receipt_not_found"

    first_h1 = control.register_h1_static_cohort_receipt(connection, h1_receipt)
    replay_h1 = control.register_h1_static_cohort_receipt(connection, deepcopy(h1_receipt))
    assert first_h1["idempotent"] is False
    assert replay_h1["idempotent"] is True

    replaced_h1 = deepcopy(h1_receipt)
    replaced_h1["stage0_static_package"]["current_admission_assessment"]["reason"] = (
        "A different H1 payload must not replace the registered receipt."
    )
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.register_h1_static_cohort_receipt(connection, replaced_h1)
    assert exc_info.value.code == "preselection_receipt_immutable_conflict"

    another_h1_id = deepcopy(h1_receipt)
    another_h1_id["receipt_id"] = "SYNV5:H1:REPLACEMENT"
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.register_h1_static_cohort_receipt(connection, another_h1_id)
    assert exc_info.value.code == "h1_receipt_natural_key_conflict"

    first_h2 = control.register_h2_action_screen_receipt(connection, h2_receipt)
    replay_h2 = control.register_h2_action_screen_receipt(connection, deepcopy(h2_receipt))
    assert first_h2["idempotent"] is False
    assert replay_h2["idempotent"] is True

    replaced_h2 = deepcopy(h2_receipt)
    replaced_h2["action_screen_extension"]["action"]["action_statement"] = (
        "A different H2 payload must not replace the registered receipt."
    )
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.register_h2_action_screen_receipt(connection, replaced_h2)
    assert exc_info.value.code == "preselection_receipt_immutable_conflict"

    another_h2_id = deepcopy(h2_receipt)
    another_h2_id["receipt_id"] = "SYNV5:H2:REPLACEMENT"
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.register_h2_action_screen_receipt(connection, another_h2_id)
    assert exc_info.value.code == "h2_receipt_natural_key_conflict"
    connection.close()


def test_preselection_receipt_cli_registers_only_the_closed_h1_then_h2_path(tmp_path, capsys) -> None:
    h1_receipt, h2_receipt = _synthetic_preselection_receipt_envelopes()
    db_path = tmp_path / "v5-receipts-cli.db"
    h1_path = tmp_path / "h1.json"
    h2_path = tmp_path / "h2.json"
    h1_path.write_text(json.dumps(h1_receipt), encoding="utf-8")
    h2_path.write_text(json.dumps(h2_receipt), encoding="utf-8")

    assert control.main(["init", "--db", str(db_path)]) == 0
    assert control.main(["register-h1-receipt", "--db", str(db_path), "--receipt", str(h1_path)]) == 0
    assert control.main(["register-h2-receipt", "--db", str(db_path), "--receipt", str(h2_path)]) == 0
    output = capsys.readouterr().out
    assert '"receipt_kind": "H1_STATIC_COHORT"' in output
    assert '"receipt_kind": "H2_ACTION_SCREEN"' in output


def test_seal_requires_registered_parented_receipts_and_closed_source_map(tmp_path) -> None:
    connection = control.connect(tmp_path / "v5-source-provenance.db")
    control.initialize(connection)
    bundle = _canonical_bundle()

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.seal_freeze(connection, bundle)
    assert exc_info.value.code == "preselection_receipt_not_found"

    _register_synthetic_preselection_receipts(connection)
    assert control.seal_freeze(connection, bundle)["sealed"] is True

    same_instants = _canonical_bundle(
        freeze_id="V5FREEZE:source-timezone",
        collision_key="COLLISION:ISSUER:TARGET:ACTION:NETWORK:CARRIER:ISSUER:OUTCOME:SOURCE-TIMEZONE",
    )
    same_instants["source_provenance"]["h1"]["selection_as_of"] = "2020-04-01T07:59:59+08:00"
    same_instants["source_provenance"]["h2"]["cutoff_at"] = "2021-01-01T07:59:59+08:00"
    _refresh_reviewed_selection_contract(same_instants)
    assert control.seal_freeze(connection, same_instants)["sealed"] is True

    outside = _canonical_bundle(
        freeze_id="V5FREEZE:source-outside",
        collision_key="COLLISION:ISSUER:TARGET:ACTION:NETWORK:CARRIER:ISSUER:OUTCOME:SOURCE-OUTSIDE",
    )
    outside["source_manifest"].append(_source("SRC:OUTSIDE", "PUBLIC_ARENA_CONTEXT", "2020-07-01T00:00:00+00:00"))
    _refresh_reviewed_selection_contract(outside)
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.seal_freeze(connection, outside)
    assert exc_info.value.code == "source_manifest_outside_registered_preselection_map"
    connection.close()


@pytest.mark.parametrize(
    ("source_id", "mutation", "expected_code"),
    [
        (
            _H2_ACTION_SOURCE_ID,
            lambda source: source.update({"official_artifact_id": "CNINFO:OTHER:ARTIFACT"}),
            "source_manifest_identity_mismatch",
        ),
        (
            _H2_ACTION_SOURCE_ID,
            lambda source: source.update({"published_at_or_date": "2020-10-14"}),
            "source_manifest_identity_mismatch",
        ),
        (
            "SRC:ARENA",
            lambda source: source.update({"source_lane": "ACTION_STATIC"}),
            "source_manifest_lane_not_authorized",
        ),
        (
            _H2_ACTION_SOURCE_ID,
            lambda source: source.update({"source_type": "OFFICIAL_NEWS_RELEASE"}),
            "source_manifest_identity_mismatch",
        ),
        (
            _H2_ACTION_SOURCE_ID,
            lambda source: source.update({"responsibility_unit_id": "UNIT:OTHER"}),
            "source_manifest_identity_mismatch",
        ),
    ],
)
def test_seal_rejects_reused_registered_source_id_with_changed_identity_or_lane(
    tmp_path, source_id: str, mutation, expected_code: str,
) -> None:
    connection = control.connect(tmp_path / "v5-source-identity.db")
    control.initialize(connection)
    _register_synthetic_preselection_receipts(connection)
    bundle = _canonical_bundle(
        freeze_id="V5FREEZE:source-identity:" + source_id,
        collision_key="COLLISION:ISSUER:TARGET:ACTION:NETWORK:CARRIER:ISSUER:OUTCOME:SOURCE-IDENTITY:" + source_id,
    )
    source = next(item for item in bundle["source_manifest"] if item["source_id"] == source_id)
    mutation(source)
    _refresh_reviewed_selection_contract(bundle)

    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.seal_freeze(connection, bundle)

    assert exc_info.value.code == expected_code
    assert connection.execute("SELECT COUNT(*) FROM judgment_v5_selection_freezes").fetchone()[0] == 0
    connection.close()


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda bundle: bundle["cohort_snapshot"].update({"arena_family": "SYNTHETIC:OTHER:ARENA"}),
            "h1_cohort_arena_family_mismatch",
        ),
        (
            lambda bundle: bundle["cohort_snapshot"]["members"][0].update({"company_id": "CN:OTHER"}),
            "h1_cohort_member_identity_mismatch",
        ),
        (
            lambda bundle: bundle["cohort_snapshot"]["members"][1].update({"control_group_id": "CONTROL:OTHER"}),
            "h1_cohort_member_identity_mismatch",
        ),
        (
            lambda bundle: bundle["cohort_snapshot"]["members"][0]["boundary"].update({"unit": "TONNES"}),
            "h1_cohort_member_boundary_mismatch",
        ),
        (
            lambda bundle: bundle["cohort_snapshot"]["members"][0]["carrier_identity_source_ids"].__setitem__(
                0, _source_id("ISSUER:PEER1", "CARRIER"),
            ),
            "h1_cohort_member_carrier_source_mismatch",
        ),
        (
            lambda bundle: bundle["cohort_snapshot"]["members"][0]["d2_or_cost_field_history"][0].update({
                "source_id": _source_id("ISSUER:PEER1", "D2", "2017-12-31"),
            }),
            "h1_cohort_member_d2_or_cost_source_mismatch",
        ),
        (
            lambda bundle: bundle["cohort_snapshot"]["members"][0]["d3_d4_field_history"][0].update({
                "source_id": _source_id("ISSUER:PEER1", "D3D4", "2016-12-31"),
            }),
            "h1_cohort_member_d3_d4_source_mismatch",
        ),
    ],
)
def test_seal_requires_exact_h1_cohort_member_projection(conn, mutation, expected_code: str) -> None:
    bundle = _canonical_bundle()
    mutation(bundle)
    _refresh_reviewed_selection_contract(bundle)

    # These variants retain a valid V5 surface: the control plane is what
    # binds an otherwise plausible root back to the immutable H1 receipt.
    assert v5.validate_v5_candidate(bundle)["admission_status"] == v5.SELECTION_ADMITTED
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.seal_freeze(conn, bundle)

    assert exc_info.value.code == expected_code
    assert conn.execute("SELECT COUNT(*) FROM judgment_v5_selection_freezes").fetchone()[0] == 0


def test_root_freeze_identity_and_times_are_required_and_cutoff_is_nested(conn) -> None:
    for field in ("selection_freeze_id", "episode_collision_key", "sealed_at", "recorded_at"):
        bundle = _canonical_bundle()
        bundle.pop(field)
        result = _seal(conn, bundle)
        assert result["sealed"] is False
        assert result["admission_status"] == v5.NOT_ADMITTED

    root_cutoff = _canonical_bundle()
    root_cutoff["research_cutoff_at"] = "2020-12-31T23:59:59+00:00"
    result = _seal(conn, root_cutoff)
    assert result["sealed"] is False
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert conn.execute("SELECT COUNT(*) FROM judgment_v5_selection_freezes").fetchone()[0] == 0


def test_no_primary_uses_real_validator_and_creates_no_freeze(conn) -> None:
    bundle = _canonical_bundle()
    bundle["measurement_contracts"] = [_metric("D3")]

    result = _seal(conn, bundle)

    assert result["sealed"] is False
    assert result["admission_status"] == v5.NO_PRIMARY
    assert conn.execute("SELECT COUNT(*) FROM judgment_v5_selection_freezes").fetchone()[0] == 0


def test_seal_and_authorization_reject_outcome_identity_before_custodian_receipt(conn) -> None:
    leaked = _canonical_bundle()
    leaked["actual_outcome_inventory"] = _post_cutoff_inventory()
    with pytest.raises(control.ControlPlaneError) as exc_info:
        _seal(conn, leaked)
    assert exc_info.value.code == "outcome_inventory_before_authorization"

    _seal(conn, _canonical_bundle())
    authorization = _authorize("V5FREEZE:one")
    authorization["actual_outcome_inventory"] = _post_cutoff_inventory()
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.authorize_outcome_access(conn, authorization)
    assert exc_info.value.code == "authorization_unexpected_field"
    assert control.status(conn, "V5FREEZE:one")["authorized"] is False


def test_authorized_package_reader_extraction_requires_derived_raw_receipts(conn) -> None:
    _seal(conn, _canonical_bundle())
    control.authorize_outcome_access(conn, _authorize("V5FREEZE:one"))
    control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "PACKAGE", receipt_id="REC:package",
        at="2021-03-01T01:00:00+00:00", payload={"actual_outcome_inventory": _post_cutoff_inventory()},
    ))
    control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "READER", receipt_id="REC:reader", at="2021-03-01T02:00:00+00:00",
    ))
    control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "EXTRACTION", receipt_id="REC:extract", at="2021-03-01T03:00:00+00:00",
    ))
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": "V5FREEZE:one", "resolution_id": "RES:one",
            "actor_id": "custodian-a", "effective_at": "2021-03-01T04:00:00+00:00",
        })
    assert exc_info.value.code == "outcome_receipts_required"
    assert control.status(conn, "V5FREEZE:one")["terminal_state"] is None


def test_pit_access_breach_is_terminal_without_inventory(conn) -> None:
    _seal(conn, _canonical_bundle())
    control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "PIT_ACCESS_BREACH", receipt_id="REC:breach",
        at="2021-01-02T00:00:00+00:00", actor_id="reviewer-a",
        payload={"detail": "reviewer saw outcome title"},
    ))

    assert control.status(conn, "V5FREEZE:one")["terminal_state"] == "PIT_ACCESS_BREACH"
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.authorize_outcome_access(conn, _authorize("V5FREEZE:one"))
    assert exc_info.value.code == "freeze_terminal"


def test_custodian_early_date_only_source_is_exposure_excluded_not_breach(conn) -> None:
    _seal(conn, _canonical_bundle())
    control.authorize_outcome_access(conn, _authorize("V5FREEZE:one"))
    result = control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "OUTCOME_PACKAGE", receipt_id="REC:early",
        at="2021-03-01T01:00:00+00:00", payload={"actual_outcome_inventory": [{
            "source_id": "SYNV5:OUTCOME:EARLY",
            "availability_precision": "DATE_ONLY",
            "source_available_at": "2020-12-31",
        }]},
    ))

    assert result["event"]["event_type"] == "EXPOSURE_EXCLUDED"
    assert control.status(conn, "V5FREEZE:one")["terminal_state"] == "EXPOSURE_EXCLUDED"


def test_missing_cell_can_only_resolve_unknown(conn) -> None:
    _seal(conn, _canonical_bundle())
    control.authorize_outcome_access(conn, _authorize("V5FREEZE:one"))
    control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "PACKAGE", receipt_id="REC:package",
        at="2021-03-01T01:00:00+00:00", payload={"actual_outcome_inventory": _post_cutoff_inventory()},
    ))
    control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "MISSING_CELL", receipt_id="REC:missing", at="2021-03-01T02:00:00+00:00",
    ))
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.resolve(conn, {
            "selection_freeze_id": "V5FREEZE:one", "resolution_id": "RES:bad",
            "resolution_status": "B_ONLY", "actor_id": "custodian-a",
            "effective_at": "2021-03-01T03:00:00+00:00",
        })
    assert exc_info.value.code == "caller_resolution_status_forbidden"
    control.resolve(conn, {
        "selection_freeze_id": "V5FREEZE:one", "resolution_id": "RES:unknown",
        "actor_id": "custodian-a",
        "effective_at": "2021-03-01T03:00:00+00:00",
        "outcome_receipts": {
            "schema_version": "judgment-v5-outcome-receipts.v1",
            "custodian_attestation": {
                "custodian_id": "custodian-a",
                "research_side_outcome_exposure": "NONE",
            },
            "raw_cells": [],
        },
    })
    assert control.status(conn, "V5FREEZE:one")["terminal_state"] == "UNKNOWN"


@pytest.mark.parametrize("receipt_kind", ["OUTCOME_READER", "OUTCOME_EXTRACTION", "MISSING_CELL"])
def test_only_the_custodian_can_read_extract_or_mark_outcome_data(conn, receipt_kind: str) -> None:
    _seal(conn, _canonical_bundle())
    control.authorize_outcome_access(conn, _authorize("V5FREEZE:one"))
    control.append_control_receipt(conn, _receipt(
        "V5FREEZE:one", "OUTCOME_PACKAGE", receipt_id="REC:package",
        at="2021-03-01T01:00:00+00:00", payload={"actual_outcome_inventory": _post_cutoff_inventory()},
    ))
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.append_control_receipt(conn, _receipt(
            "V5FREEZE:one", receipt_kind, receipt_id=f"REC:{receipt_kind}",
            at="2021-03-01T02:00:00+00:00", actor_id="SYNV5:REVIEWER",
        ))
    assert exc_info.value.code == "custodian_mismatch"
    assert receipt_kind not in control.status(conn, "V5FREEZE:one")["receipt_kinds"]


def test_collision_needs_preaccess_void_and_cannot_reuse_after_access(conn) -> None:
    _seal(conn, _canonical_bundle())
    with pytest.raises(control.ControlPlaneError) as exc_info:
        _seal(conn, _canonical_bundle(freeze_id="V5FREEZE:two"))
    assert exc_info.value.code == "collision_predecessor_required"

    control.void_pre_access_freeze(conn, "V5FREEZE:one", {
        "receipt_id": "VOID:one", "actor_id": "reviewer-a", "effective_at": "2021-01-02T00:00:00+00:00",
    })
    successor = _canonical_bundle(freeze_id="V5FREEZE:two", predecessor_freeze_id="V5FREEZE:one")
    assert _seal(conn, successor)["sealed"] is True
    control.authorize_outcome_access(conn, _authorize("V5FREEZE:two"))
    with pytest.raises(control.ControlPlaneError) as exc_info:
        _seal(conn, _canonical_bundle(
            freeze_id="V5FREEZE:three", predecessor_freeze_id="V5FREEZE:two",
        ))
    assert exc_info.value.code == "collision_reuse_forbidden"


def test_control_event_idempotency_rejects_payload_change(conn) -> None:
    _seal(conn, _canonical_bundle())
    authorization = _authorize("V5FREEZE:one")
    authorization["idempotency_key"] = "AUTH:stable"
    first = control.authorize_outcome_access(conn, authorization)
    second = control.authorize_outcome_access(conn, deepcopy(authorization))

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    changed = deepcopy(authorization)
    changed["custodian_id"] = "custodian-b"
    with pytest.raises(control.ControlPlaneError) as exc_info:
        control.authorize_outcome_access(conn, changed)
    assert exc_info.value.code == "idempotency_conflict"
