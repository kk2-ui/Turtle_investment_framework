from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts import judgment_selection_v5 as v5
from tests.test_judgment_v5_control_plane import (
    _H2_ACTION_SOURCE_ID,
    _cohort_member as _registered_h1_cohort_member,
    _root_source_manifest,
    _source as _registered_h1_source,
)


_REVIEWED_SELECTION_FIELDS = (
    "schema_version", "candidate_id", "method_epoch_id", "selection_goal", "selection_freeze_id",
    "episode_collision_key", "sealed_at", "recorded_at", "cohort_snapshot", "action_scope",
    "scope_bridges", "competitive_arena", "external_driver_reference", "counterfactual_panel",
    "measurement_contracts", "time_contract", "outcome_contract", "materiality_and_resolution_contract",
    "source_manifest", "source_provenance", "source_firewall_receipt",
)


def _refresh_reviewed_selection_contract(bundle: dict) -> None:
    bundle["independent_pre_outcome_review"]["reviewed_selection_contract"] = {
        field: deepcopy(bundle[field]) for field in _REVIEWED_SELECTION_FIELDS
    }


def _source(source_id: str, lane: str, when: str) -> dict:
    return _registered_h1_source(source_id, lane, when)


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
        "raw_field_source_locators": [],
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
    try:
        return _registered_h1_cohort_member(issuer, group)
    except KeyError:
        # Pure V5 validator tests may add a hypothetical witness.  It remains
        # syntactically closed here; a real seal must reject it against H1.
        member = _registered_h1_cohort_member("ISSUER:PEER3", "CONTROL:PEER3")
        member.update({
            "company_id": issuer.replace("ISSUER:", "CN:"),
            "issuer_id": issuer,
            "responsibility_unit_id": issuer.replace("ISSUER:", "UNIT:"),
            "control_group_id": group,
        })
        member["boundary"]["responsibility_unit_id"] = member["responsibility_unit_id"]
        return member


def _panel_member(issuer: str, group: str) -> dict:
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


def _bundle(*, topology: str = "CUSTOMER_RESPONSE", selection_goal: str = "SELECTION") -> dict:
    action = {
        "action_id": "ACTION:NETWORK",
        "focal_issuer_id": "ISSUER:TARGET",
        "mechanism_topology": topology,
        "d2_role": "CENTRAL_VOTER" if topology == "CUSTOMER_RESPONSE" else "DIAGNOSTIC_NON_VOTER",
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
        "h_a": {"hypothesis_id": "H:A", "mechanism": "implemented network improves contribution and cash", "central_endpoint_predictions": {"D3": "IMPROVE", "D4": "IMPROVE"}},
        "h_b": {"hypothesis_id": "H:B", "mechanism": "network does not improve contribution or cash", "central_endpoint_predictions": {"D3": "NO_IMPROVEMENT", "D4": "NO_IMPROVEMENT"}},
        "source_ids": [_H2_ACTION_SOURCE_ID],
    }
    if topology == "CUSTOMER_RESPONSE":
        action["d2_observations"] = [{"period": year, "source_id": _H2_ACTION_SOURCE_ID} for year in (2017, 2018, 2019)]
    else:
        action["cost_driver_observations"] = [{"period": year, "source_id": _H2_ACTION_SOURCE_ID} for year in (2017, 2018, 2019)]
    metrics = [_metric("D3"), _metric("D4")]
    bundle = {
        "schema_version": v5.SCHEMA_VERSION,
        "candidate_id": "SYNV5:CANDIDATE:BASE",
        "method_epoch_id": v5.METHOD_EPOCH_ID,
        "selection_goal": selection_goal,
        "selection_freeze_id": "SYNV5:FREEZE:BASE",
        "episode_collision_key": "SYNV5:COLLISION:TARGET:NETWORK:2021",
        "sealed_at": "2021-01-01T00:00:00+00:00",
        "recorded_at": "2021-01-01T00:01:00+00:00",
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
        "action_scope": action,
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
            "required_exposure_dimensions": [
                {"dimension": "COST_DRIVER", "relation": "REQUIRED_EXPOSURE", "rationale_from_mechanism": "same input cost transmission", "target_evidence_source_ids": ["SRC:ARENA"], "peer_evidence_source_ids": ["SRC:ARENA"]},
            ],
            "target_driver_exposure_source_ids": ["SRC:ARENA"],
        },
        "counterfactual_panel": {
            "counterfactual_panel_id": "PANEL:BASE",
            "target_issuer_id": "ISSUER:TARGET",
            "members": [
                _panel_member("ISSUER:PEER1", "CONTROL:PEER1"),
                _panel_member("ISSUER:PEER2", "CONTROL:PEER2"),
                _panel_member("ISSUER:PEER3", "CONTROL:PEER3"),
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
    return bundle


def test_v5_schema_is_machine_readable_and_declares_preoutcome_surface() -> None:
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas" / "judgment_selection_admission_v5.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema_version"]["const"] == v5.SCHEMA_VERSION
    assert schema["properties"]["method_epoch_id"]["const"] == v5.METHOD_EPOCH_ID
    assert "OUTCOME_SEALED" in schema["$defs"]["source"]["properties"]["source_lane"]["enum"]
    assert {
        "selection_freeze_id", "episode_collision_key", "sealed_at", "recorded_at", "outcome_contract",
        "source_provenance",
    } <= set(schema["required"])
    selection_requirements = schema["allOf"][0]["then"]["required"]
    assert {"independent_pre_outcome_review", "source_firewall_receipt"} <= set(selection_requirements)
    assert "source_provenance" in schema["$defs"]["reviewed_selection_contract"]["required"]
    assert {
        "source_url", "source_type", "issuer_id", "responsibility_unit_id", "perimeter_id", "unit",
    } <= set(schema["$defs"]["source"]["required"])
    assert "research_cutoff_at" not in schema["properties"]
    assert "resolution_rules" not in schema["$defs"]["metric_contract"]["properties"]


def test_wire_bundle_keeps_target_out_of_peer_members_and_freezes_identity_only_outcomes() -> None:
    bundle = _bundle()
    assert bundle["counterfactual_panel"]["target_issuer_id"] not in {
        member["issuer_id"] for member in bundle["counterfactual_panel"]["members"]
    }
    assert all("source_id" not in cell and "value" not in cell for cell in bundle["outcome_contract"]["frozen_raw_matrix"])
    assert v5.validate_v5_candidate(bundle)["admission_status"] == v5.SELECTION_ADMITTED


def test_two_external_comparators_are_admitted_in_the_two_comparator_epoch() -> None:
    bundle = _bundle()
    bundle["counterfactual_panel"]["members"] = bundle["counterfactual_panel"]["members"][:2]
    bundle["outcome_contract"]["frozen_raw_matrix"] = [
        cell for cell in bundle["outcome_contract"]["frozen_raw_matrix"]
        if cell["issuer_id"] != "ISSUER:PEER3"
    ]
    _refresh_reviewed_selection_contract(bundle)
    assert v5.validate_v5_candidate(bundle)["admission_status"] == v5.SELECTION_ADMITTED


def test_wire_contract_rejects_root_cutoff_or_missing_freeze_identity() -> None:
    root_cutoff = _bundle()
    root_cutoff["research_cutoff_at"] = root_cutoff["time_contract"]["research_cutoff_at"]
    result = v5.validate_v5_candidate(root_cutoff)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "bundle_research_cutoff_must_only_exist_in_time_contract" in result["findings"]

    no_freeze = _bundle()
    no_freeze.pop("selection_freeze_id")
    result = v5.validate_v5_candidate(no_freeze)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "bundle_selection_freeze_id_missing" in result["findings"]


def test_independent_preoutcome_review_and_no_access_receipt_are_freeze_requirements() -> None:
    missing_review = _bundle()
    missing_review.pop("independent_pre_outcome_review")
    result = v5.validate_v5_candidate(missing_review)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "review_identity_or_time_invalid" in result["findings"]

    rejected = _bundle()
    rejected["independent_pre_outcome_review"]["verdict"] = "REJECTED"
    result = v5.validate_v5_candidate(rejected)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "review_not_accepted" in result["findings"]

    self_review = _bundle()
    self_review["independent_pre_outcome_review"]["reviewer_id"] = self_review["source_firewall_receipt"]["researcher_id"]
    result = v5.validate_v5_candidate(self_review)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "reviewer_not_independent_from_researcher" in result["findings"]

    reviewer_exposed = _bundle()
    reviewer_exposed["independent_pre_outcome_review"]["reviewer_outcome_metadata_access"] = "CONFIRMED"
    result = v5.validate_v5_candidate(reviewer_exposed)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "reviewer_preoutcome_outcome_access_not_sealed" in result["findings"]

    late_review = _bundle()
    late_review["independent_pre_outcome_review"]["reviewed_at"] = "2021-01-01T00:00:01+00:00"
    result = v5.validate_v5_candidate(late_review)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "review_after_selection_freeze" in result["findings"]

    stale_binding = _bundle()
    stale_binding["action_scope"]["action_id"] = "ACTION:REPLACED"
    result = v5.validate_v5_candidate(stale_binding)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "review_binding_does_not_match_selection_freeze" in result["findings"]


def test_preoutcome_review_snapshot_rejects_material_contract_mutation() -> None:
    scenarios = {
        "d3_formula": lambda bundle: next(
            metric for metric in bundle["measurement_contracts"] if metric["clock"] == "D3"
        )["outcome_formula"]["terms"][1].update({"coefficient": -0.5}),
        "d3_threshold": lambda bundle: next(
            metric for metric in bundle["measurement_contracts"] if metric["clock"] == "D3"
        )["discriminability"]["primary_threshold"].update({"value": 12.0}),
        "panel_role": lambda bundle: bundle["counterfactual_panel"]["members"][0].update({
            "causal_role": "EQUILIBRIUM_RESPONSE_WITNESS", "eligible_for_relative_baseline": False,
        }),
        "raw_locator": lambda bundle: bundle["outcome_contract"]["frozen_raw_matrix"][0].update({
            "field_locator": "post-review:replacement",
        }),
        "scope_bridge": lambda bundle: bundle["scope_bridges"][0].update({
            "action_cash_boundary": "changed after review",
        }),
        "time_window": lambda bundle: bundle["time_contract"]["metric_economic_periods"]["D3"].update({
            "end": "2022-12-31T00:00:00+00:00",
        }),
        "collision_key": lambda bundle: bundle.update({"episode_collision_key": "SYNV5:COLLISION:REPLACED"}),
        "firewall_receipt": lambda bundle: bundle["source_firewall_receipt"].update({
            "receipt_id": "SYNV5:FIREWALL:REPLACED",
        }),
    }
    for name, mutate in scenarios.items():
        bundle = _bundle()
        mutate(bundle)
        result = v5.validate_v5_candidate(bundle)
        assert result["admission_status"] != v5.SELECTION_ADMITTED, name
        assert "review_binding_does_not_match_selection_freeze" in result["findings"], name


def test_source_provenance_requires_closed_parented_receipt_snapshots() -> None:
    missing = _bundle()
    missing.pop("source_provenance")
    result = v5.validate_v5_candidate(missing)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "source_provenance_shape_invalid" in result["findings"]

    wrong_parent = _bundle()
    wrong_parent["source_provenance"]["h2"]["parent_receipt_id"] = "SYNV5:H1:OTHER"
    _refresh_reviewed_selection_contract(wrong_parent)
    result = v5.validate_v5_candidate(wrong_parent)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "source_provenance_h2_parent_not_h1" in result["findings"]

    wrong_cohort = _bundle()
    wrong_cohort["source_provenance"]["h1"]["cohort_id"] = "SYNV5:COHORT:OTHER"
    _refresh_reviewed_selection_contract(wrong_cohort)
    result = v5.validate_v5_candidate(wrong_cohort)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "source_provenance_h1_cohort_snapshot_mismatch" in result["findings"]

    wrong_cutoff = _bundle()
    wrong_cutoff["source_provenance"]["h2"]["cutoff_at"] = "2020-12-30T23:59:59+00:00"
    _refresh_reviewed_selection_contract(wrong_cutoff)
    result = v5.validate_v5_candidate(wrong_cutoff)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "source_provenance_h2_cutoff_mismatch" in result["findings"]


def test_d3_outcome_formula_and_structural_outcome_contract_are_required() -> None:
    bundle = _bundle()
    d3 = next(metric for metric in bundle["measurement_contracts"] if metric["clock"] == "D3")
    d3["outcome_formula"]["terms"][1]["coefficient"] = 0.0
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "metric_d3_identity_invalid" in result["findings"]

    exposed = _bundle()
    exposed["outcome_contract"]["frozen_raw_matrix"][0]["source_id"] = "OUTCOME:FORBIDDEN"
    result = v5.validate_v5_candidate(exposed)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "isolation_outcome_contract_actual_source_metadata_forbidden" in result["findings"]


def test_discriminability_operators_and_units_are_canonical_wire_values() -> None:
    symbolic = _bundle()
    d3 = next(metric for metric in symbolic["measurement_contracts"] if metric["clock"] == "D3")
    d3["discriminability"]["primary_threshold"]["operator"] = ">="
    result = v5.validate_v5_candidate(symbolic)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "metric_d3_discriminability_invalid" in result["findings"]

    free_text = _bundle()
    d4 = next(metric for metric in free_text["measurement_contracts"] if metric["clock"] == "D4")
    d4["discriminability"]["rival_threshold"]["operator"] = "LESS_THAN"
    result = v5.validate_v5_candidate(free_text)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "metric_d4_discriminability_invalid" in result["findings"]

    wrong_unit = _bundle()
    d4 = next(metric for metric in wrong_unit["measurement_contracts"] if metric["clock"] == "D4")
    d4["discriminability"]["primary_threshold"]["unit"] = "USD"
    result = v5.validate_v5_candidate(wrong_unit)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "metric_d4_discriminability_invalid" in result["findings"]


def test_d4_restructuring_treatment_uses_exact_canonical_raw_field_sets() -> None:
    separate = _bundle()
    d4 = next(metric for metric in separate["measurement_contracts"] if metric["clock"] == "D4")
    d4["restructuring_cash_treatment"] = "SEPARATE_OPERATING_CASH_DEDUCTION"
    d4["formula_and_ordered_raw_fields"].append(v5.D4_RESTRUCTURING_CASH_FIELD)
    d4["raw_field_source_locators"].append({
        "field_id": v5.D4_RESTRUCTURING_CASH_FIELD,
        "allowed_source_class": "OFFICIAL_ANNUAL_REPORT",
    })
    separate["outcome_contract"]["frozen_raw_matrix"] = _frozen_raw_matrix(separate["measurement_contracts"])
    _refresh_reviewed_selection_contract(separate)
    assert v5.validate_v5_candidate(separate)["admission_status"] == v5.SELECTION_ADMITTED

    missing_cash = _bundle()
    d4 = next(metric for metric in missing_cash["measurement_contracts"] if metric["clock"] == "D4")
    d4["restructuring_cash_treatment"] = "SEPARATE_OPERATING_CASH_DEDUCTION"
    result = v5.validate_v5_candidate(missing_cash)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "metric_d4_raw_field_identity_invalid" in result["findings"]

    cannot_settle = _bundle()
    d4 = next(metric for metric in cannot_settle["measurement_contracts"] if metric["clock"] == "D4")
    d4["restructuring_cash_treatment"] = "OUT_OF_PERIMETER_CANNOT_SETTLE"
    result = v5.validate_v5_candidate(cannot_settle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "metric_d4_out_of_perimeter_restructuring_not_settleable" in result["findings"]


def test_national_customer_response_admits_without_provincial_geography_match() -> None:
    result = v5.validate_v5_candidate(_bundle())
    assert result == {"valid": True, "admission_status": v5.SELECTION_ADMITTED, "findings": []}


def test_cost_restructuring_nonvoter_d2_admits() -> None:
    result = v5.validate_v5_candidate(_bundle(topology="COST_RESTRUCTURING"))
    assert result["valid"] is True
    assert result["admission_status"] == v5.SELECTION_ADMITTED


def test_stage0_action_leak_rejects_before_action_screen() -> None:
    bundle = _bundle()
    bundle["cohort_snapshot"]["action_id"] = "ACTION:LEAK"
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.STAGE0_REJECTED
    assert "stage0_action_or_outcome_contaminated" in result["findings"]

    narrative_leak = _bundle()
    narrative_leak["cohort_snapshot"]["memo"] = "The target's later network action looks material."
    result = v5.validate_v5_candidate(narrative_leak)
    assert result["admission_status"] == v5.STAGE0_REJECTED
    assert "stage0_information_set_not_closed" in result["findings"]


def test_stage0_requires_three_independent_control_issuers() -> None:
    bundle = _bundle()
    bundle["cohort_snapshot"]["members"] = bundle["cohort_snapshot"]["members"][:2]
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.STAGE0_REJECTED
    assert "stage0_independent_three_issuer_capacity_not_met" in result["findings"]


def test_customer_topology_rejects_nonvoter_d2_and_cost_topology_requires_cost_history() -> None:
    customer = _bundle()
    customer["action_scope"]["d2_role"] = "DIAGNOSTIC_NON_VOTER"
    assert v5.validate_v5_candidate(customer)["admission_status"] == v5.NO_PRIMARY

    cost = _bundle(topology="COST_RESTRUCTURING")
    cost["action_scope"].pop("cost_driver_observations")
    assert v5.validate_v5_candidate(cost)["admission_status"] == v5.NO_PRIMARY


def test_identity_bridge_cannot_fake_issuer_coverage() -> None:
    bundle = _bundle()
    bridge = bundle["scope_bridges"][0]
    bridge["coverage_numerator"] = {"value": 100, "unit": "RMB", "period_end": "2019-12-31", "source_id": _H2_ACTION_SOURCE_ID}
    bridge["coverage_denominator"] = {"value": 100, "unit": "RMB", "period_end": "2019-12-31", "source_id": _H2_ACTION_SOURCE_ID}
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "bridge_identity_must_not_fake_coverage" in result["findings"]


def test_aggregation_bridge_requires_channel_matched_complete_quantification() -> None:
    bundle = _bundle()
    bridge = bundle["scope_bridges"][0]
    bridge.update({
        "bridge_type": "QUANTIFIED_ISSUER_AGGREGATION",
        "coverage_basis": "DELIVERABLE_CAPACITY",
        "mechanism_channel": "DELIVERABLE_CAPACITY",
        "coverage_channel": "DELIVERABLE_CAPACITY",
        "coverage_as_of": "2020-03-31",
        "coverage_numerator": {"value": 60.0, "unit": "tonnes", "period_end": "2019-12-31", "source_id": _H2_ACTION_SOURCE_ID},
        "coverage_denominator": {"value": 100.0, "unit": "RMB", "period_end": "2019-12-31", "source_id": _H2_ACTION_SOURCE_ID},
        "known_omitted_material_items": [],
        "known_other_material_changes": [],
    })
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "bridge_aggregation_quantification_invalid" in result["findings"]


def test_regional_arena_requires_actual_geographic_overlap_but_driver_comparators_need_not_be_local() -> None:
    bundle = _bundle(topology="COST_RESTRUCTURING")
    bundle["cohort_snapshot"]["members"].append(_cohort_member("ISSUER:WITNESS", "CONTROL:W"))
    bundle["competitive_arena"].update({
        "competitive_arena_id": "ARENA:REGIONAL",
        "market_scope_type": "REGIONAL",
        "required_overlap_dimensions": [{"dimension": "GEOGRAPHIC_MARKET", "relation": "REQUIRED_OVERLAP", "rationale_from_mechanism": "delivery radii overlap", "target_evidence_source_ids": ["SRC:ARENA"], "peer_evidence_source_ids": ["SRC:ARENA"]}],
    })
    bundle["counterfactual_panel"]["members"].append({
        "issuer_id": "ISSUER:WITNESS",
        "control_group_id": "CONTROL:W",
        "causal_role": "EQUILIBRIUM_RESPONSE_WITNESS",
        "mechanism_arena_membership": {"status": "PROVEN", "source_ids": ["SRC:ARENA"]},
        "external_driver_reference_membership": {"status": "NOT_REQUIRED", "source_ids": ["SRC:ARENA"]},
        "shared_driver_exposure": "UNKNOWN",
        "parallel_action": "DISCLOSED",
        "target_action_spillover": "MATERIAL_RISK",
        "eligible_for_relative_baseline": False,
        "source_ids": ["SRC:ARENA"],
    })
    _refresh_reviewed_selection_contract(bundle)
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.SELECTION_ADMITTED

    bundle["competitive_arena"]["required_overlap_dimensions"][0]["relation"] = "NOT_REQUIRED"
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "arena_regional_geographic_overlap_missing" in result["findings"]


def test_comparator_unknown_parallel_action_cannot_enter_baseline() -> None:
    bundle = _bundle()
    bundle["counterfactual_panel"]["members"][0]["parallel_action"] = "UNKNOWN"
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "panel_comparator_external_driver_or_noninterference_invalid" in result["findings"]


def test_d3_and_d4_are_independent_and_teaching_only_is_explicit() -> None:
    selection = _bundle()
    selection["measurement_contracts"] = [_metric("D3")]
    assert v5.validate_v5_candidate(selection)["admission_status"] == v5.NO_PRIMARY

    teaching = _bundle(selection_goal="TEACHING_ONLY")
    teaching["measurement_contracts"] = [_metric("D3")]
    result = v5.validate_v5_candidate(teaching)
    assert result == {"valid": False, "admission_status": v5.TEACHING_ONLY, "findings": []}


def test_teaching_only_does_not_require_a_selection_panel_or_d4_threshold() -> None:
    teaching = _bundle(selection_goal="TEACHING_ONLY")
    teaching["measurement_contracts"] = [_metric("D3")]
    teaching.pop("external_driver_reference")
    teaching.pop("counterfactual_panel")
    teaching["materiality_and_resolution_contract"].pop("d4_outcome_discriminability")
    teaching["measurement_contracts"][0].pop("discriminability")
    result = v5.validate_v5_candidate(teaching)
    assert result == {"valid": False, "admission_status": v5.TEACHING_ONLY, "findings": []}


def test_date_only_same_day_is_not_cutoff_before() -> None:
    bundle = _bundle()
    source = next(item for item in bundle["source_manifest"] if item["source_id"] == _H2_ACTION_SOURCE_ID)
    source["availability_precision"] = "DATE_ONLY"
    source["published_at_or_date"] = "2020-12-31"
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "source_not_cutoff_before" in result["findings"]


def test_seven_time_partition_rejects_action_scope_mismatch_and_nonfuture_metric_period() -> None:
    bundle = _bundle()
    bundle["time_contract"]["decision_observable_at"] = "2020-06-01T00:00:00+00:00"
    bundle["time_contract"]["metric_economic_periods"]["D4"]["start"] = "2020-04-01T00:00:00+00:00"
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "time_action_scope_identity_mismatch" in result["findings"]
    assert "time_d4_economic_period_invalid" in result["findings"]


def test_d4_identity_requires_complete_owner_cash_formula_and_cash_boundary() -> None:
    bundle = _bundle()
    d4 = next(metric for metric in bundle["measurement_contracts"] if metric["clock"] == "D4")
    d4["cash_working_capital_components"].append("cash")
    d4["restructuring_cash_treatment"] = "UNCLASSIFIED"
    result = v5.validate_v5_candidate(bundle)
    assert result["admission_status"] == v5.NO_PRIMARY
    assert "metric_d4_cash_working_capital_boundary_invalid" in result["findings"]
    assert "metric_d4_restructuring_cash_treatment_invalid" in result["findings"]


def test_investor_materiality_unknown_is_not_a_preoutcome_admission_rejection() -> None:
    result = v5.validate_v5_candidate(_bundle())
    assert result["admission_status"] == v5.SELECTION_ADMITTED


def test_legacy_holdout_and_outcome_identity_touch_are_not_admitted() -> None:
    legacy = _bundle()
    legacy["candidate_id"] = "SYNV5:R-104:FORBIDDEN"
    assert v5.validate_v5_candidate(legacy)["admission_status"] == v5.NOT_ADMITTED

    holdout = _bundle()
    holdout["candidate_id"] = "SYNV5:R103:FORBIDDEN"
    assert v5.validate_v5_candidate(holdout)["admission_status"] == v5.NOT_ADMITTED

    outcome = _bundle()
    outcome["source_manifest"].append({
        **_source("SRC:SEALED", "OUTCOME_SEALED", "2021-03-31T00:00:00+00:00"),
        "outcome_visibility": "SEALED",
    })
    result = v5.validate_v5_candidate(outcome)
    assert result["admission_status"] == v5.NOT_ADMITTED
    assert "isolation_outcome_source_identity_leak" in result["findings"]


def test_validator_is_pure_and_does_not_mutate_bundle() -> None:
    bundle = _bundle()
    before = deepcopy(bundle)
    v5.validate_v5_candidate(bundle)
    assert bundle == before
