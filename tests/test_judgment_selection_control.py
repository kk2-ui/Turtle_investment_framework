from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from scripts import judgment_feedback_control as jfc
from scripts import judgment_selection_candidate as jsc
from scripts import judgment_selection_discovery as discovery


CASE_ID = "SELECTIONCASE:SYNTHETIC:CONTROL"
FREEZE_ID = "JFREEZE:SYNTHETIC:CONTROL"
CLAIM_STAGES = (
    ("SYN:D1", "D1_IMPLEMENTATION", "SYN-P-D1"),
    ("SYN:D2", "D2_CUSTOMER_ABSORPTION", "SYN-P-D2"),
    ("SYN:D3A", "D3_PRODUCT_VOLUME", "SYN-P-D3A"),
    ("SYN:D3B", "D3_UNIT_ECONOMICS", "SYN-P-D3B"),
    ("SYN:D4", "D4_WORKING_CAPITAL_AND_CASH", "SYN-P-D4"),
    ("SYN:D5", "D5_CAPITAL_RETURN", "SYN-P-D5"),
)
FIVE_CLAIM_STAGES = tuple(
    item for item in CLAIM_STAGES if item[1] != "D3_PRODUCT_VOLUME"
)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jfc,
        "_now_dt",
        lambda: datetime.fromisoformat("2027-01-16T12:00:00-08:00"),
    )


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _candidate(claim_stages: tuple = CLAIM_STAGES) -> dict:
    predictions = [
        {
            "predicate_id": predicate_id,
            "stage": stage_id,
            "primary_prediction": "Synthetic primary prediction.",
            "rival_prediction": "Synthetic rival prediction.",
            "baseline_prediction": "Synthetic simple baseline.",
        }
        for _, stage_id, predicate_id in claim_stages
    ]
    candidate = {
        "schema_version": "judgment-selection-candidate.v1",
        "case_id": CASE_ID,
        "experiment_id": "SYNTHETIC-CONTROL-EPISODE",
        "company_id": "CN:SYNTHETIC",
        "company_cluster_id": "COMPANY:SYNTHETIC",
        "responsibility_unit_id": "UNIT:SYNTHETIC",
        "industry_id": "INDUSTRY:SYNTHETIC",
        "freeze_id": FREEZE_ID,
        "decisive_question": "Which synthetic mechanism explains the operating outcome?",
        "cutoff_at": "2020-12-31T23:59:59+08:00",
        "freeze_recorded_at": "2026-08-20T23:00:00+08:00",
        "training_role": "HISTORICAL_SELECTION_CANDIDATE",
        "program_lane": "HISTORICAL_TRAINING",
        "provenance_role": "HISTORICAL_SELF_REPLAY",
        "probability_mode": "NO_PROBABILITY",
        "selection_status": "SELECTION_ADMITTED",
        "selection_effective_gate": "PENDING_INDEPENDENT_PRE_OUTCOME_REVIEW",
        "learning_eligibility": "NONE_PENDING_REVIEW",
        "registration_status": "NOT_REGISTERED",
        "candidate_verdict": "PROPOSED_PRIMARY_PENDING_INDEPENDENT_REVIEW",
        "cutoff_before_facts": [{
            "fact_id": "SYN-F1",
            "statement": "Synthetic cutoff fact.",
            "selection_classification": "DECISIVE",
            "source_ids": ["SYNTHETIC:PRE-CUTOFF:1"],
        }],
        "rival_hypothesis_pair": {
            "primary_hypothesis": {
                "hypothesis_id": "SYN-H-A",
                "name": "Primary",
                "mechanism": "Synthetic primary mechanism.",
                "role": "SELECTED_PRIMARY",
            },
            "strongest_rival": {
                "hypothesis_id": "SYN-H-B",
                "name": "Rival",
                "mechanism": "Synthetic rival mechanism.",
                "role": "STRONGEST_RIVAL",
            },
            "selection_basis": {
                "directional_preference": "SYN-H-A",
                "why_not_common": "Synthetic differentiator.",
                "why_rival_remains_live": "Synthetic rival remains falsifiable.",
            },
        },
        "fair_simple_baseline": {
            "baseline_id": "SYN-BASELINE",
            "rule": "Last observed point.",
            "selection_use": "FAIR_COMPARISON",
            "formulae": {"volume": "100 tonnes", "margin": "12 percent"},
        },
        "frozen_prediction_order": predictions,
        "measurement_boundary": {
            clock: "Synthetic same-unit boundary." for clock in ("D1", "D2", "D3", "D4", "D5")
        },
        "outcome_access_attestation": {
            "state": "PIT_OUTCOME_SEALED",
            "metadata_leakage_detected": False,
            "outcome_acquisition_authorized": False,
            "attestation": "No post-cutoff outcome was accessed.",
        },
    }
    return candidate


def _candidate_review(candidate: dict) -> dict:
    return {
        "schema_version": "judgment-selection-review-receipt.v1",
        "receipt_id": "SYN-CANDIDATE-REVIEW",
        "case_id": CASE_ID,
        "reviewer_id": "synthetic-independent-candidate-reviewer",
        "selection_scope": "SYNTHETIC_SELECTION",
        "reviewed_at": "2026-08-21T00:00:00+08:00",
        "verdict": "SELECTION_ADMITTED_PRE_OUTCOME",
        "outcome_body_access": "UNREAD_AND_PROHIBITED",
        "outcome_metadata_access": "NONE",
        "reviewed_artifacts": ["case.json"],
        "review_answers": {
            "directional_preference_without_prohibited_inputs": "YES",
            "strongest_rival_preserved": "YES",
            "fair_baseline_distinct": "YES",
            "responsibility_unit_and_unknown_boundary": "YES",
            "golden_report_materiality": "YES",
        },
        "accepted_selection_basis": {
            "primary_hypothesis_id": candidate["rival_hypothesis_pair"]["primary_hypothesis"]["hypothesis_id"],
            "strongest_rival_id": candidate["rival_hypothesis_pair"]["strongest_rival"]["hypothesis_id"],
            "simple_baseline_id": candidate["fair_simple_baseline"]["baseline_id"],
        },
        "admission_boundary": {"does_not_grant": ["method win", "probability", "investment return"]},
    }


def _v3_cash_transmission_candidate() -> dict:
    candidate = _candidate()
    candidate["selection_admission_contract"] = {
        "version": jsc.CASH_TRANSMISSION_ADMISSION_VERSION,
        "customer_absorption_requirement": {
            "required": True,
            "trigger": jsc.CUSTOMER_ABSORPTION_REQUIRED_TRIGGER,
            "rationale": "The selected H-A requires an independently observable customer response.",
        },
        "cash_transmission_requirement": {
            "required": True,
            "trigger": jsc.CASH_TRANSMISSION_REQUIRED_TRIGGER,
            "rationale": "The selected H-A claims that operating improvement reaches normal owner cash.",
        },
    }
    boundary = {
        "responsibility_unit_id": candidate["responsibility_unit_id"],
        "perimeter_id": "CONSOLIDATED_ISSUER",
        "unit": "RMB",
    }
    repetitions = [
        {
            "period_end": period_end,
            "published_at": published_at,
            "source_id": source_id,
            "field_ref": "official annual-report income, balance-sheet or cash-flow line",
        }
        for period_end, published_at, source_id in (
            ("2017-12-31", "2018-03-30", "SYNTHETIC:OFFICIAL:2017"),
            ("2018-12-31", "2019-03-30", "SYNTHETIC:OFFICIAL:2018"),
            ("2019-12-31", "2020-03-30", "SYNTHETIC:OFFICIAL:2019"),
        )
    ]
    legs = []
    for leg_id, clock, stage in jsc.CASH_TRANSMISSION_LEGS:
        legs.append({
            "leg_id": leg_id,
            "clock": clock,
            "stage": stage,
            "hypothesis_signs": {
                "H_A": "FAVOURABLE_TO_NORMAL_OWNER_CASH",
                "H_B": "ADVERSE_TO_NORMAL_OWNER_CASH",
            },
            "official_field_identity": {
                "field_id": f"SYN-{leg_id}",
                "definition": f"Synthetic recurring {leg_id.lower()} identity.",
                "source_class": "OFFICIAL_DISCLOSURE",
                "formula_or_field": "Synthetic official disclosure field or frozen formula.",
            },
            "boundary": deepcopy(boundary),
            "cutoff_before_repetitions": deepcopy(repetitions),
        })
    candidate["cash_transmission_observability"] = {
        "gate_version": jsc.CASH_TRANSMISSION_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "failure_disposition": jsc.CASH_TRANSMISSION_NO_PRIMARY,
        "d3_d4_substitution_prohibited": True,
        "common_boundary": boundary,
        "transmission_legs": legs,
        "d3_to_d4_linkage": {
            "d3_predicate_id": "SYN-P-D3B",
            "d4_predicate_id": "SYN-P-D4",
        },
        "d4_formula": {
            "formula_id": "SYN-OWNER-CASH",
            "formula": "OCF - capex/restructuring cash - positive cash working-capital release.",
            "positive_working_capital_release_treatment": "SUBTRACT_POSITIVE_RELEASE",
            "capex_restructuring_cash_treatment": "SUBTRACT_OBSERVED_CASH_NEVER_ASSUME_ZERO",
        },
        "materiality_anchors": {
            "D3_UNIT_ECONOMICS": {
                "stage": "D3_UNIT_ECONOMICS",
                "predicate_id": "SYN-P-D3B",
                "anchor_id": "SYN-D3-NORMAL-PROFIT-ANCHOR",
                "anchor_statement": "Synthetic recurring normal operating contribution hurdle.",
                "source_ids": ["SYNTHETIC:OFFICIAL:2019"],
                "primary_threshold": {"operator": "GREATER_THAN_OR_EQUAL", "value": 100.0, "unit": "RMB"},
                "rival_threshold": {"operator": "LESS_THAN_OR_EQUAL", "value": 80.0, "unit": "RMB"},
            },
            "D4_WORKING_CAPITAL_AND_CASH": {
                "stage": "D4_WORKING_CAPITAL_AND_CASH",
                "predicate_id": "SYN-P-D4",
                "anchor_id": "SYN-D4-NORMAL-OWNER-CASH-ANCHOR",
                "anchor_statement": "Synthetic normal owner-cash hurdle after conservative cash deductions.",
                "source_ids": ["SYNTHETIC:OFFICIAL:2019"],
                "primary_threshold": {"operator": "GREATER_THAN_OR_EQUAL", "value": 90.0, "unit": "RMB"},
                "rival_threshold": {"operator": "LESS_THAN_OR_EQUAL", "value": 70.0, "unit": "RMB"},
            },
        },
    }
    candidate["customer_absorption_observability"] = {
        "gate_version": jsc.CASH_TRANSMISSION_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "d2_predicate_id": "SYN-P-D2",
        "failure_disposition": jsc.CUSTOMER_ABSORPTION_NO_PRIMARY,
        "observation_kind": "UNITS_SOLD",
        "not_mechanically_changed_by_action": True,
        "prohibited_substitutes": [
            "REVENUE_ALONE_WHEN_PRICE_OR_MIX_ACTION",
            "ANNOUNCED_OR_DESIGN_CAPACITY_AS_ACTUAL_DEMAND",
        ],
        "boundary": deepcopy(boundary),
        "official_field_identity": {
            "field_id": "SYN-CUSTOMER-UNITS",
            "definition": "Synthetic recurring units sold to customers.",
            "source_class": "OFFICIAL_DISCLOSURE",
            "formula_or_field": "Official annual-report units sold field.",
        },
        "hypothesis_signs": {
            "H_A": "CUSTOMER_RESPONSE_SUPPORTS_PRIMARY",
            "H_B": "CUSTOMER_RESPONSE_SUPPORTS_RIVAL",
        },
        "cutoff_before_repetitions": deepcopy(repetitions),
    }
    return candidate


def _v3_cash_transmission_review(candidate: dict) -> dict:
    review = _candidate_review(candidate)
    review["review_answers"]["customer_absorption_independently_observable"] = (
        "YES: units sold are recurrently disclosed on the same consolidated issuer boundary and are not"
        " mechanically changed by the selected action."
    )
    review["review_answers"]["cash_transmission_recurrently_observable"] = (
        "YES: D3 contribution, cash working capital and capex/restructuring cash are"
        " independently recurring on the same consolidated issuer boundary."
    )
    review["cash_transmission_admission"] = {
        "gate_version": jsc.CASH_TRANSMISSION_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "verdict": "RECURRINGLY_OBSERVABLE_PRE_OUTCOME",
        "verified_leg_ids": list(jsc._CASH_TRANSMISSION_LEG_IDS),
        "d3_d4_substitution_prohibited": True,
        "review_conclusion": "D3 is not a substitute for D4; all three cash-transmission legs recur before cutoff.",
    }
    review["customer_absorption_admission"] = {
        "gate_version": jsc.CASH_TRANSMISSION_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "d2_predicate_id": "SYN-P-D2",
        "verdict": "INDEPENDENTLY_OBSERVABLE_PRE_OUTCOME",
        "not_mechanically_changed_by_action": True,
        "review_conclusion": "Customer units are independent of a price or capacity announcement and recur before cutoff.",
    }
    return review


def _v4_annual_observation(
    period_end: str, published_at: str, source_id: str, issuer_id: str, d3_value: float, d4_value: float,
) -> dict:
    def field(field_name: str, value: float) -> dict:
        return {
            "value": value,
            "unit": "RMB",
            "source_id": source_id,
            "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
            "issuer_id": issuer_id,
            "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
            "period_end": period_end,
            "published_at": published_at,
            "field_ref": f"Official annual report {period_end} {field_name}.",
        }
    revenue = 1_000.0
    d3_raw_values = {
        "operating_revenue_rmb": revenue,
        "operating_cost_rmb": 900.0 - d3_value,
        "taxes_and_surcharges_rmb": 20.0,
        "selling_expense_rmb": 30.0,
        "administrative_expense_rmb": 50.0,
    }
    d4_raw_values = {
        "operating_cash_flow_rmb": d4_value + 100.0,
        "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb": 100.0,
        "opening_accounts_receivable_rmb": 10.0,
        "opening_prepayments_rmb": 0.0,
        "opening_inventory_rmb": 0.0,
        "opening_accounts_payable_rmb": 0.0,
        "opening_customer_advances_rmb": 0.0,
        "ending_accounts_receivable_rmb": 10.0,
        "ending_prepayments_rmb": 0.0,
        "ending_inventory_rmb": 0.0,
        "ending_accounts_payable_rmb": 0.0,
        "ending_customer_advances_rmb": 0.0,
    }
    return {
        "period_end": period_end,
        "reporting_frequency": "ANNUAL",
        "d3_formula_id": "SYN-OPERATING_CONTRIBUTION",
        "d4_formula_id": "SYN-OWNER-CASH",
        "d3_raw_fields": {name: field(name, value) for name, value in d3_raw_values.items()},
        "d4_raw_fields": {name: field(name, value) for name, value in d4_raw_values.items()},
    }


def _v4_comparability_register(
    observations: list[dict], *, issuer_id: str, boundary: dict,
) -> dict:
    period_ends = [item["period_end"] for item in observations]

    def evidence(period_end: str) -> list[dict]:
        source = observations[period_ends.index(period_end)]["d3_raw_fields"]["operating_revenue_rmb"]
        return [{
            "source_id": source["source_id"],
            "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
            "issuer_id": issuer_id,
            "perimeter_id": boundary["perimeter_id"],
            "responsibility_unit_id": boundary["responsibility_unit_id"],
            "unit": boundary["unit"],
            "published_at": source["published_at"],
            "field_ref": "Annual-report comparability review for " + period_end,
        }]

    return {
        "verdict": "COMPARABLE_PRE_ACTION_WINDOW",
        "reviewed_period_ends": period_ends,
        "dimensions": [
            {
                "dimension_id": dimension,
                "period_statuses": [
                    {"period_end": period_end, "status": "COMPARABLE", "evidence": evidence(period_end)}
                    for period_end in period_ends
                ],
            }
            for dimension in jsc.V4_COMPARABILITY_DIMENSIONS
        ],
        "material_breaks_excluded_from_window": [],
    }


def _v4_discovery_binding(candidate: dict) -> dict:
    """Build the separate cohort-first discovery packet for the V4 fixture."""
    panel = candidate["peer_panel_observability"]
    target = panel["target"]
    action = candidate["cash_transmission_observability"]["materiality_anchors"]["action_exposure"]
    d2 = candidate["customer_absorption_observability"]

    def evidence(source_id: str, member: dict, *, published_at: str, control: bool = False) -> dict:
        item = {
            "source_id": source_id,
            "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
            "issuer_id": member["issuer_id"],
            "perimeter_id": member["boundary"]["perimeter_id"],
            "responsibility_unit_id": member["responsibility_unit_id"],
            "unit": member["boundary"]["unit"],
            "published_at": published_at,
            "field_ref": f"{member['company_id']} {source_id}, PDF p12",
        }
        if control:
            item["observed_control_group_id"] = member["control_group_id"]
        return item

    members = [target, *panel["peers"]]
    members.append({
        "company_id": "CN:SYNTHETIC-PEER-4",
        "issuer_id": "ISSUER:CN:SYNTHETIC-PEER-4",
        "control_group_id": "CONTROL_GROUP:CN:SYNTHETIC-PEER-4",
        "responsibility_unit_id": "UNIT:SYNTHETIC-PEER-4",
        "boundary": {
            "responsibility_unit_id": "UNIT:SYNTHETIC-PEER-4",
            "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
            "unit": "RMB",
        },
        "industry_id": candidate["industry_id"],
    })
    cohort_members = []
    for member in members:
        cohort_members.append({
            "company_id": member["company_id"],
            "issuer_id": member["issuer_id"],
            "responsibility_unit_id": member["responsibility_unit_id"],
            "control_group_id": member["control_group_id"],
            "industry_id": candidate["industry_id"],
            "boundary": deepcopy(member["boundary"]),
            "industry_business_evidence": [evidence("COHORT:INDUSTRY:" + member["company_id"], member, published_at="2020-03-30")],
            "control_group_evidence": [evidence("COHORT:CONTROL:" + member["company_id"], member, published_at="2020-03-30", control=True)],
            "final_peer_panel_disposition": "PENDING_ACTION_WINDOW_REVIEW",
            "final_peer_panel_rationale": "Stage 0 source availability does not determine final peer eligibility.",
            "d2_field_availability": {
                "field_id": "COHORT:UNITS_SOLD",
                "definition": "Annual customer units sold.",
                "repetitions": [
                    {"period_end": period_end, "evidence": [evidence(
                        f"COHORT:D2:{member['company_id']}:{period_end}", member, published_at=published_at,
                    )]}
                    for period_end, published_at in (
                        ("2017-12-31", "2018-03-30"),
                        ("2018-12-31", "2019-03-30"),
                        ("2019-12-31", "2020-03-30"),
                    )
                ],
            },
            "annual_d3_d4_availability": [
                {"period_end": period_end, "evidence": [evidence(
                    f"COHORT:ANNUAL:{member['company_id']}:{period_end}", member, published_at=published_at,
                )]}
                for period_end, published_at in (
                    ("2015-12-31", "2016-03-30"),
                    ("2016-12-31", "2017-03-30"),
                    ("2017-12-31", "2018-03-30"),
                    ("2018-12-31", "2019-03-30"),
                    ("2019-12-31", "2020-03-30"),
                )
            ],
        })
    cohort = {
        "schema_version": jsc.V4_COHORT_FEASIBILITY_SCHEMA_VERSION,
        "cohort_id": "COHORT:SYNTHETIC:20200630",
        "industry_id": candidate["industry_id"],
        "selection_as_of": "2020-06-30",
        "universe": {
            "universe_id": "SYNTHETIC:LISTED:20200630",
            "membership_rule": "All five eligible listed synthetic issuers at the cutoff-before cohort date.",
            "cohort_scope": "PRE_ACTION_DISCLOSURE_FEASIBILITY_SAMPLE",
            "not_final_peer_universe": True,
            "listed_company_ids": [member["company_id"] for member in members],
        },
        "members": cohort_members,
    }
    primary = candidate["rival_hypothesis_pair"]["primary_hypothesis"]
    rival = candidate["rival_hypothesis_pair"]["strongest_rival"]
    binding = {
        "schema_version": jsc.V4_DISCOVERY_BINDING_SCHEMA_VERSION,
        "manifest": {
            "schema_version": "judgment-selection-discovery-manifest.v1",
            "manifest_id": "DISCOVERY:SYNTHETIC:NETWORK:20201231",
            "mechanism_topology": candidate["selection_admission_contract"]["mechanism_topology"],
            "cutoff_at": candidate["cutoff_at"],
            "candidate_identity": {
                "company_id": candidate["company_id"],
                "issuer_id": target["issuer_id"],
                "responsibility_unit_id": candidate["responsibility_unit_id"],
                "industry_id": candidate["industry_id"],
                "common_boundary": deepcopy(target["boundary"]),
            },
            "cohort_feasibility_record": cohort,
            "action": {
                "action_id": action["action_id"],
                "action_statement": action["action_statement"],
                "action_scope": "CANDIDATE_COMMON_BOUNDARY",
                "economic_character": "COMMERCIAL_COMPETITIVE_DECISION",
                "economic_action_type": action["economic_action_type"],
                "action_state": action["action_state"],
                "implemented_or_incurred_at": action["implemented_or_incurred_at"],
                "boundary": deepcopy(action["boundary"]),
                "issuer_scope_bridge": deepcopy(action["issuer_scope_bridge"]),
                "decision_specificity": deepcopy(action["decision_specificity"]),
                "explicitly_immaterial": action["explicitly_immaterial"],
                "implementation_evidence": deepcopy(action["implementation_evidence"]),
                "exposure": {
                    "kind": action["exposure"]["kind"],
                    "actual_basis": action["exposure"]["actual_basis"],
                    "evidence": deepcopy(action["exposure"]["evidence"]),
                },
            },
            "cutoff_before_facts": [
                {"fact_id": "FACT:PRIMARY", "statement": "The action is implemented on the common boundary.", "evidence": deepcopy(action["implementation_evidence"])},
                {
                    "fact_id": "FACT:RIVAL", "statement": "The rival operating mechanism remains live before cutoff.",
                    "evidence_scope": "D2_COMMON_RESPONSIBILITY_PERIMETER",
                    "evidence": [deepcopy(d2["cutoff_before_repetitions"][0]["raw_observation"]["evidence"])],
                },
            ],
            "hypothesis_pair": {
                "decisive_question": candidate["decisive_question"],
                "primary": {
                    "hypothesis_id": primary["hypothesis_id"], "mechanism": primary["mechanism"],
                    "pre_outcome_rationale": "The actual action and recurrent customer measure remain available.",
                    "supporting_fact_ids": ["FACT:PRIMARY"],
                },
                "strongest_rival": {
                    "hypothesis_id": rival["hypothesis_id"], "mechanism": rival["mechanism"],
                    "pre_outcome_rationale": "Customer outcomes can still support the rival before result access.",
                    "live_before_cutoff": True, "supporting_fact_ids": ["FACT:RIVAL"],
                },
                "selection_basis": {
                    "directional_preference": primary["hypothesis_id"],
                    "why_not_common": candidate["rival_hypothesis_pair"]["selection_basis"]["why_not_common"],
                    "why_rival_remains_live": candidate["rival_hypothesis_pair"]["selection_basis"]["why_rival_remains_live"],
                },
            },
            "d2_observability": {
                "primary_hypothesis_id": d2["primary_hypothesis_id"],
                "observation_kind": d2["observation_kind"],
                "not_mechanically_changed_by_action": d2["not_mechanically_changed_by_action"],
                "boundary": deepcopy(d2["boundary"]),
                "field_id": d2["official_field_identity"]["field_id"],
                "repetitions": [
                    {"period_end": item["period_end"], "field_ref": item["field_ref"], "evidence": [deepcopy(item["raw_observation"]["evidence"])]}
                    for item in d2["cutoff_before_repetitions"]
                ],
            },
            "source_firewall": {
                "outcome_body_access": "UNREAD_AND_PROHIBITED",
                "outcome_metadata_access": "NONE",
                "post_cutoff_sources_prohibited": True,
                "curator_attestation": "Synthetic cutoff-only source package; no outcome source accessed.",
                "discovery_entry": {
                    "kind": discovery.KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF,
                    "issuer_code_or_name_submitted_to_cninfo_fulltext": False,
                    "cninfo_issuer_stock_or_detail_page_opened": False,
                    "post_identification_access": discovery.POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY,
                    "static_pdf_sources": [
                        {
                            "url": "https://static.cninfo.com.cn/finalpage/2020-10-15/SYNTHETIC-ACTION.PDF",
                            "source_id": action["implementation_evidence"][0]["source_id"],
                        },
                        {
                            "url": "https://static.cninfo.com.cn/finalpage/2020-03-30/SYNTHETIC-D2.PDF",
                            "source_id": d2["cutoff_before_repetitions"][0]["raw_observation"]["evidence"]["source_id"],
                        },
                    ],
                },
            },
        },
    }
    def source_ids(value: object) -> set[str]:
        if isinstance(value, dict):
            own = {str(value["source_id"])} if isinstance(value.get("source_id"), str) else set()
            return own.union(*(source_ids(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(source_ids(item) for item in value)) if value else set()
        return set()
    manifest = binding["manifest"]
    if candidate["selection_admission_contract"]["mechanism_topology"] == jsc.V4_COST_RESTRUCTURING_CHAIN:
        driver = candidate["cost_driver_observability"]
        manifest.pop("d2_observability")
        manifest["cost_driver_observability"] = {
            "primary_hypothesis_id": driver["primary_hypothesis_id"],
            "observation_kind": driver["observation_kind"],
            "boundary": deepcopy(driver["boundary"]),
            "field_id": driver["official_field_identity"]["field_id"],
            "repetitions": [
                {
                    "period_end": item["period_end"],
                    "field_ref": item["field_ref"],
                    "evidence": deepcopy(item["raw_observation"]["evidence"]),
                }
                for item in driver["cutoff_before_repetitions"]
            ],
        }
        manifest["cutoff_before_facts"][1] = {
            "fact_id": "FACT:RIVAL",
            "statement": "The recurrent cost driver leaves the rival operating mechanism live before cutoff.",
            "evidence_scope": "COST_COMMON_RESPONSIBILITY_PERIMETER",
            "evidence": deepcopy(driver["cutoff_before_repetitions"][0]["raw_observation"]["evidence"]),
        }
        manifest["source_firewall"]["discovery_entry"]["static_pdf_sources"][1] = {
            "url": "https://static.cninfo.com.cn/finalpage/2020-03-30/SYNTHETIC-COST.PDF",
            "source_id": driver["cutoff_before_repetitions"][0]["raw_observation"]["evidence"][0]["source_id"],
        }
    allowed_source_ids = sorted(source_ids({
        key: value for key, value in manifest.items() if key != "source_firewall"
    }))
    manifest["source_firewall"]["access_receipt"] = {
        "schema_version": "phase10-pit-runner-attestation.v1",
        "runner": "phase10_pit_runner",
        "assurance_level": "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS",
        "state": "REVIEWABLE",
        "cutoff_at": manifest["cutoff_at"],
        "allowed_source_ids": allowed_source_ids,
        "source_allowlist": [
            {"source_id": source_id, "published_at": "2020-10-15"}
            for source_id in allowed_source_ids
        ],
    }

    # H1 deliberately contains only the arena/member feasibility packet.  H2
    # separately declares every static PDF used by one action screen, then the
    # production validator projects the legacy manifest internally.
    stage0 = deepcopy(cohort)
    stage0.update({
        "schema_version": discovery.STAGE0_STATIC_PACKAGE_SCHEMA_VERSION,
        "selection_as_of": "2020-06-30T23:59:59+08:00",
        "cohort_eligibility_as_of": "2020-06-30T23:59:59+08:00",
        "arena_family": "SYNTHETIC_DOMESTIC_OPERATING_ARENA",
        "mechanism_topology": (
            "CUSTOMER_RESPONSE"
            if manifest["mechanism_topology"] == jsc.V4_CUSTOMER_RESPONSE_CHAIN
            else "COST_RESTRUCTURING"
        ),
        "entry_kind": discovery.CURATOR_SUPPLIED_STATIC_PDF_PACKAGE,
        "current_admission_assessment": {
            "status": discovery.FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE,
            "reason": "Five independent synthetic issuers form one source-defined arena.",
        },
        "curator_attestation": {
            "curator_id": "CURATOR:SYNTHETIC:H1-H2",
            "issuer_code_or_name_submitted_to_cninfo_fulltext": False,
            "cninfo_issuer_stock_or_detail_page_opened": False,
            "post_identification_access": discovery.POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY,
            "post_cutoff_metadata_or_body_read": False,
        },
        "competitive_arena": {
            "competitive_arena_id": "ARENA:SYNTHETIC:DOMESTIC",
            "market_scope_type": "NATIONAL",
            "product_or_service_scope": "Synthetic operating product.",
            "geographic_scope": "Synthetic domestic customer market.",
            "customer_end_market_scope": "Synthetic industrial customers.",
            "evidence": [],
        },
        "static_pdf_sources": [],
    })
    h1_sources: dict[str, dict] = {}
    h1_periods: dict[str, str] = {}
    for member in stage0["members"]:
        member["competitive_arena_id"] = stage0["competitive_arena"]["competitive_arena_id"]
        member["carrier_identity_source_ids"] = [member["industry_business_evidence"][0]["source_id"]]
        for record in member["d2_field_availability"]["repetitions"]:
            for evidence_record in record["evidence"]:
                h1_periods[evidence_record["source_id"]] = record["period_end"]
        for record in member["annual_d3_d4_availability"]:
            for evidence_record in record["evidence"]:
                h1_periods[evidence_record["source_id"]] = record["period_end"]
        for evidence_record in discovery._stage0_evidence_records(member):
            h1_sources.setdefault(evidence_record["source_id"], {
                "source_id": evidence_record["source_id"],
                "url": f"https://static.cninfo.com.cn/finalpage/2020-03-30/{len(h1_sources) + 1}.PDF",
                "published_at": evidence_record["published_at"],
                "source_type": evidence_record["source_type"],
                "period_end": h1_periods.get(evidence_record["source_id"], "2019-12-31"),
                "field_refs": [],
                "issuer_id": evidence_record["issuer_id"],
                "responsibility_unit_id": evidence_record["responsibility_unit_id"],
                "perimeter_id": evidence_record["perimeter_id"],
                "unit": evidence_record["unit"],
            })["field_refs"].append(evidence_record["field_ref"])
    # H1 is a fixed catalogue, not an appendable source reserve.  Bind every
    # annual/control/market/comparability citation to one of the existing H1
    # member PDFs; only new action-screen and D2 inputs may be H2 declarations.
    def bind_h1_citation(citation: dict, source_id: str) -> None:
        source = h1_sources[source_id]
        citation.update({
            "source_id": source_id,
            "source_type": source["source_type"],
            "issuer_id": source["issuer_id"],
            "perimeter_id": source["perimeter_id"],
            "published_at": source["published_at"],
        })
        if "responsibility_unit_id" in citation:
            citation["responsibility_unit_id"] = source["responsibility_unit_id"]
        if "unit" in citation:
            citation["unit"] = source["unit"]
        page_ref = f"{source_id}: PDF p12"
        citation["field_ref"] = page_ref
        if page_ref not in source["field_refs"]:
            source["field_refs"].append(page_ref)

    def annual_source_id(member: dict, period_end: str) -> str:
        return f"COHORT:ANNUAL:{member['company_id']}:{period_end}"

    def bind_h1_member(member: dict) -> None:
        bind_h1_citation(
            member["control_group_evidence"][0], "COHORT:CONTROL:" + member["company_id"],
        )
        bind_h1_citation(
            member["market_exposure"]["evidence"][0], "COHORT:INDUSTRY:" + member["company_id"],
        )
        for observation in member["annual_d3_d4_raw_observations"]:
            source_id = annual_source_id(member, observation["period_end"])
            for section in ("d3_raw_fields", "d4_raw_fields"):
                for raw in observation[section].values():
                    bind_h1_citation(raw, source_id)
        for dimension in member["comparability_register"]["dimensions"]:
            for status in dimension["period_statuses"]:
                for evidence_record in status["evidence"]:
                    bind_h1_citation(evidence_record, annual_source_id(member, status["period_end"]))

    bind_h1_member(target)
    for peer in panel["peers"]:
        bind_h1_member(peer)
    for leg in candidate["cash_transmission_observability"]["transmission_legs"]:
        for repetition in leg["cutoff_before_repetitions"]:
            source_id = annual_source_id(target, repetition["period_end"])
            source = h1_sources[source_id]
            repetition.update({
                "source_id": source_id,
                "published_at": source["published_at"],
                "field_ref": f"{source_id}: PDF p12",
            })
            if repetition["field_ref"] not in source["field_refs"]:
                source["field_refs"].append(repetition["field_ref"])
    for anchor_name in ("D3_UNIT_ECONOMICS", "D4_WORKING_CAPITAL_AND_CASH"):
        anchor = candidate["cash_transmission_observability"]["materiality_anchors"].get(anchor_name)
        if isinstance(anchor, dict) and isinstance(anchor.get("source_ids"), list):
            anchor["source_ids"] = [
                annual_source_id(target, "2015-12-31"),
                annual_source_id(target, "2019-12-31"),
            ]
    if candidate["selection_admission_contract"]["mechanism_topology"] == jsc.V4_COST_RESTRUCTURING_CHAIN:
        for repetition in candidate["cost_driver_observability"]["cutoff_before_repetitions"]:
            source_id = annual_source_id(target, repetition["period_end"])
            raw = repetition["raw_observation"]["evidence"][0]
            bind_h1_citation(raw, source_id)
            repetition.update({
                "source_id": source_id,
                "published_at": raw["published_at"],
                "field_ref": raw["field_ref"],
            })
    stage0["competitive_arena"]["evidence"] = [
        deepcopy(stage0["members"][0]["industry_business_evidence"][0]),
    ]
    stage0["static_pdf_sources"] = list(h1_sources.values())

    extension = {
        "schema_version": discovery.ACTION_SCREEN_STATIC_EXTENSION_SCHEMA_VERSION,
        "screen_id": "H2:SYNTHETIC:NETWORK:20201231",
        "stage0_cohort_id": stage0["cohort_id"],
        "stage0_selection_as_of": stage0["selection_as_of"],
        "curator_id": stage0["curator_attestation"]["curator_id"],
        "cutoff_at": manifest["cutoff_at"],
        "mechanism_topology": manifest["mechanism_topology"],
        "candidate_identity": deepcopy(manifest["candidate_identity"]),
        "static_pdf_sources": [],
        "source_firewall_attestation": {
            "outcome_body_access": "UNREAD_AND_PROHIBITED",
            "outcome_metadata_access": "NONE",
            "post_cutoff_sources_prohibited": True,
        },
        "action": deepcopy(manifest["action"]),
        "cutoff_before_facts": deepcopy(manifest["cutoff_before_facts"]),
        "hypothesis_pair": deepcopy(manifest["hypothesis_pair"]),
        **({"d2_observability": deepcopy(manifest["d2_observability"])} if "d2_observability" in manifest else {}),
        **({"cost_driver_observability": deepcopy(manifest["cost_driver_observability"])} if "cost_driver_observability" in manifest else {}),
    }
    h2_sources: dict[str, dict] = {}

    def bind_h2_static_pdf(value: object) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("source_id"), str) and isinstance(value.get("field_ref"), str):
                source_id = value["source_id"]
                page_ref = f"{source_id}: PDF p12"
                if source_id in h1_sources:
                    source = h1_sources[source_id]
                    # Reusing a frozen H1 PDF must retain its declared page
                    # identity.  Do not replace it with a convenient new
                    # page label while constructing the synthetic H2 screen.
                    value["field_ref"] = source["field_refs"][0]
                else:
                    value["field_ref"] = page_ref
                    h2_sources.setdefault(source_id, {
                        "source_id": source_id,
                        "url": f"https://static.cninfo.com.cn/finalpage/2020-10-15/{len(h2_sources) + 1}.PDF",
                        "published_at": value["published_at"],
                        "source_type": value["source_type"],
                        "field_refs": [],
                        "issuer_id": value["issuer_id"],
                        "responsibility_unit_id": value["responsibility_unit_id"],
                        "perimeter_id": value["perimeter_id"],
                        "unit": value["unit"],
                    })["field_refs"].append(page_ref)
            for nested in value.values():
                bind_h2_static_pdf(nested)
        elif isinstance(value, list):
            for nested in value:
                bind_h2_static_pdf(nested)

    for field in ("action", "cutoff_before_facts", "hypothesis_pair", "d2_observability", "cost_driver_observability"):
        if field in extension:
            bind_h2_static_pdf(extension[field])
    extension["static_pdf_sources"] = list(h2_sources.values())
    # The H2 extension is copied into the binding and its page anchors become
    # authoritative.  Align the candidate's modeled action/D2-or-cost
    # citations with those exact declarations; raw annual and panel citations
    # were already bound above by H1.
    all_static_sources = {**h1_sources, **h2_sources}

    def align_static_citation(citation: dict) -> None:
        source = all_static_sources.get(citation.get("source_id"))
        if source is not None:
            citation["field_ref"] = source["field_refs"][0]

    for field in ("issuer_scope_bridge", "decision_specificity"):
        for evidence_record in action[field]["evidence"]:
            align_static_citation(evidence_record)
    for evidence_record in action["implementation_evidence"]:
        align_static_citation(evidence_record)
    for evidence_record in action["exposure"]["evidence"]:
        align_static_citation(evidence_record)
    for component in candidate["cash_transmission_observability"].get("d4_cash_bridge_coverage", {}).get("components", []):
        for evidence_record in component.get("evidence", []):
            align_static_citation(evidence_record)
    if "customer_absorption_observability" in candidate:
        for repetition in candidate["customer_absorption_observability"]["cutoff_before_repetitions"]:
            raw = repetition["raw_observation"]["evidence"]
            align_static_citation(raw)
            repetition["field_ref"] = raw["field_ref"]
    if "cost_driver_observability" in candidate:
        for repetition in candidate["cost_driver_observability"]["cutoff_before_repetitions"]:
            for evidence_record in repetition["raw_observation"]["evidence"]:
                align_static_citation(evidence_record)
                repetition["field_ref"] = evidence_record["field_ref"]
    candidate["cutoff_before_facts"] = [
        {
            "fact_id": fact["fact_id"],
            "statement": fact["statement"],
            "selection_classification": "DECISIVE",
            "source_ids": [item["source_id"] for item in fact["evidence"]],
            "evidence": deepcopy(fact["evidence"]),
            **({"evidence_scope": fact["evidence_scope"]} if "evidence_scope" in fact else {}),
        }
        for fact in extension["cutoff_before_facts"]
    ]
    return {
        "schema_version": jsc.V4_DISCOVERY_BINDING_SCHEMA_VERSION,
        "stage0_static_package": stage0,
        "action_screen_extension": extension,
    }


def _v4_peer_panel_candidate() -> dict:
    """A fully pre-outcome V4 packet with a mechanically reproducible step.

    Target D3 [100,110,120,130,140] and D4 [50,60,70,80,90] both have a
    median absolute deviation of 10.  The fixed scaled-MAD step is therefore
    14.826, not an analyst chosen 5% or a D3-to-cash conversion.
    """
    candidate = _v3_cash_transmission_candidate()
    candidate["selection_admission_contract"]["version"] = jsc.PEER_PANEL_ADMISSION_VERSION
    candidate["selection_admission_contract"]["mechanism_topology"] = jsc.V4_CUSTOMER_RESPONSE_CHAIN
    boundary = {
        "responsibility_unit_id": candidate["responsibility_unit_id"],
        "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
        "unit": "RMB",
    }
    target_issuer_id = "ISSUER:CN:SYNTHETIC"
    candidate["cash_transmission_observability"]["gate_version"] = jsc.PEER_PANEL_ADMISSION_VERSION
    candidate["cash_transmission_observability"]["common_boundary"] = deepcopy(boundary)
    for leg in candidate["cash_transmission_observability"]["transmission_legs"]:
        leg["boundary"] = deepcopy(boundary)
    candidate["customer_absorption_observability"]["gate_version"] = jsc.PEER_PANEL_ADMISSION_VERSION
    d2_boundary = {
        "responsibility_unit_id": candidate["responsibility_unit_id"],
        "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
        "unit": "TONNES",
    }
    candidate["customer_absorption_observability"]["boundary"] = deepcopy(d2_boundary)
    candidate["customer_absorption_observability"]["official_field_identity"]["definition"] = (
        "Annual tonnes sold to end customers on the listed consolidated issuer boundary."
    )
    for index, repetition in enumerate(candidate["customer_absorption_observability"]["cutoff_before_repetitions"]):
        repetition["raw_observation"] = {
            "value": 100.0 + index * 10.0,
            "unit": "TONNES",
            "definition": candidate["customer_absorption_observability"]["official_field_identity"]["definition"],
            "channel_position": "END_CUSTOMER",
            "evidence": {
                "source_id": repetition["source_id"],
                "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                "issuer_id": target_issuer_id,
                "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                "responsibility_unit_id": candidate["responsibility_unit_id"],
                "unit": "TONNES",
                "published_at": repetition["published_at"],
                "field_ref": repetition["field_ref"],
            },
        }

    target_history = [
        _v4_annual_observation(
            period_end, published_at, source_id, target_issuer_id, d3_value, d4_value,
        )
        for period_end, published_at, source_id, d3_value, d4_value in (
            ("2015-12-31", "2016-03-30", "SYNTHETIC:TARGET:2015", 100.0, 50.0),
            ("2016-12-31", "2017-03-30", "SYNTHETIC:TARGET:2016", 110.0, 60.0),
            ("2017-12-31", "2018-03-30", "SYNTHETIC:TARGET:2017", 120.0, 70.0),
            ("2018-12-31", "2019-03-30", "SYNTHETIC:TARGET:2018", 130.0, 80.0),
            ("2019-12-31", "2020-03-30", "SYNTHETIC:TARGET:2019", 140.0, 90.0),
        )
    ]
    peers = []
    for peer_number, values in enumerate(((80.0, 40.0), (90.0, 45.0), (95.0, 55.0)), start=1):
        company_id = f"CN:SYNTHETIC-PEER-{peer_number}"
        issuer_id = f"ISSUER:{company_id}"
        peer_boundary = {
            "responsibility_unit_id": f"UNIT:SYNTHETIC-PEER-{peer_number}",
            "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
            "unit": "RMB",
        }
        peers.append({
            "company_id": company_id,
            "industry_id": candidate["industry_id"],
            "responsibility_unit_id": peer_boundary["responsibility_unit_id"],
            "boundary": peer_boundary,
            "annual_d3_d4_raw_observations": [
                _v4_annual_observation(
                    period_end, published_at, f"SYNTHETIC:PEER-{peer_number}:{year}", issuer_id,
                    d3_base + increment, d4_base + increment,
                )
                for period_end, published_at, year, increment in (
                    ("2017-12-31", "2018-03-30", "2017", 0.0),
                    ("2018-12-31", "2019-03-30", "2018", 5.0),
                    ("2019-12-31", "2020-03-30", "2019", 10.0),
                )
                for d3_base, d4_base in [values]
            ],
        })
    peer_order = [candidate["company_id"], *[peer["company_id"] for peer in peers]]
    market_context = {
        "market_id": "MARKET:SYNTHETIC:DOMESTIC",
        "product_or_service_scope": "Synthetic core operating product.",
        "geographic_scope": "Domestic synthetic market.",
        "customer_end_market_scope": "Synthetic industrial customers.",
        "same_exogenous_shock_required": True,
    }

    def market_exposure(member: dict) -> dict:
        return {
            **{key: value for key, value in market_context.items() if key != "same_exogenous_shock_required"},
            "evidence": [{
                "source_id": "SYNTHETIC:MARKET:" + member["company_id"],
                "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                "issuer_id": member["issuer_id"],
                "perimeter_id": member["boundary"]["perimeter_id"],
                "responsibility_unit_id": member["responsibility_unit_id"],
                "unit": member["boundary"]["unit"],
                "published_at": "2020-03-30",
                "field_ref": "Official annual-report product, geography and customer-market exposure.",
            }],
        }

    candidate["peer_panel_observability"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "failure_disposition": jsc.PEER_PANEL_NO_PRIMARY,
        "panel_contract_id": "SYN-V4-PANEL-001",
        "same_industry_requirement": "TARGET_AND_ALL_PEERS_MATCH_CANDIDATE_INDUSTRY",
        "common_market_context": market_context,
        "frozen_panel": {
            "frozen_order": peer_order,
            "universe": {
                "universe_id": "SYN-V4-INDUSTRY-UNIVERSE-20200630",
                "industry_id": candidate["industry_id"],
                "as_of": "2020-06-30",
                "membership_rule": "All listed synthetic same-industry issuers available at cutoff.",
                "eligible_company_ids": peer_order,
            },
            "exclusions": [],
            "no_replacement": True,
            "replacement_policy": "NO_REPLACEMENT",
        },
        "relative_method": {
            "method": jsc.V4_PEER_RELATIVE_METHOD,
            "reference_period_end": "2019-12-31",
            "unit": "ratio",
            "conjunction": "D3_AND_D4",
        },
        "target": {
            "company_id": candidate["company_id"],
            "issuer_id": target_issuer_id,
            "control_group_id": "CONTROL_GROUP:TARGET",
            "control_group_evidence": [{
                "source_id": "SYNTHETIC:TARGET:CONTROL",
                "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                "issuer_id": target_issuer_id,
                "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                "published_at": "2020-03-30",
                "field_ref": "Official annual-report control group disclosure.",
                "observed_control_group_id": "CONTROL_GROUP:TARGET",
            }],
            "responsibility_unit_id": candidate["responsibility_unit_id"],
            "boundary": deepcopy(boundary),
            "market_exposure": market_exposure({
                "company_id": candidate["company_id"], "issuer_id": target_issuer_id,
                "responsibility_unit_id": candidate["responsibility_unit_id"], "boundary": boundary,
            }),
            "annual_d3_d4_raw_observations": target_history,
            "comparability_register": _v4_comparability_register(
                target_history, issuer_id=target_issuer_id, boundary=boundary,
            ),
        },
        "peers": [
            {
                **peer,
                "issuer_id": f"ISSUER:{peer['company_id']}",
                "control_group_id": f"CONTROL_GROUP:{peer['company_id']}",
                "control_group_evidence": [{
                    "source_id": f"SYNTHETIC:{peer['company_id']}:CONTROL",
                    "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                    "issuer_id": f"ISSUER:{peer['company_id']}",
                    "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                    "published_at": "2020-03-30",
                    "field_ref": "Official annual-report control group disclosure.",
                    "observed_control_group_id": f"CONTROL_GROUP:{peer['company_id']}",
                }],
                "market_exposure": market_exposure({
                    "company_id": peer["company_id"], "issuer_id": f"ISSUER:{peer['company_id']}",
                    "responsibility_unit_id": peer["responsibility_unit_id"], "boundary": peer["boundary"],
                }),
                "comparability_register": _v4_comparability_register(
                    peer["annual_d3_d4_raw_observations"],
                    issuer_id=f"ISSUER:{peer['company_id']}", boundary=peer["boundary"],
                ),
            }
            for peer in peers
        ],
    }
    scaled_step = 14.826
    candidate["cash_transmission_observability"]["materiality_anchors"] = {
        "action_exposure": {
            "action_id": "SYN-V4-ACTION-IMPLEMENTED",
            "action_statement": "Synthetic actual cash restructuring payment is already incurred.",
            "action_state": jsc.V4_ACTION_IMPLEMENTED,
            "economic_action_type": "OPERATING_NETWORK_RESTRUCTURING",
            "implemented_or_incurred_at": "2020-09-30",
            "boundary": deepcopy(boundary),
            "issuer_scope_bridge": {
                "outcome_scope": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                "action_scope_relation": "ISSUER_WIDE_OPERATING_DECISION",
                "issuer_level_mechanism_only": True,
                "evidence": [{
                    "source_id": "SYNTHETIC:ACTION:ISSUER-SCOPE",
                    "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                    "issuer_id": target_issuer_id,
                    "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                    "responsibility_unit_id": candidate["responsibility_unit_id"],
                    "unit": "RMB",
                    "published_at": "2020-10-15",
                    "field_ref": "Official disclosure confirming issuer-wide operating scope.",
                }],
            },
            "decision_specificity": {
                "decision_class": "DISCRETIONARY_OPERATING_DECISION",
                "incremental_to_maintenance_or_mandated_baseline": True,
                "evidence": [{
                    "source_id": "SYNTHETIC:ACTION:INCREMENTAL",
                    "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                    "issuer_id": target_issuer_id,
                    "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                    "responsibility_unit_id": candidate["responsibility_unit_id"],
                    "unit": "RMB",
                    "published_at": "2020-10-15",
                    "field_ref": "Official disclosure confirms discretionary incremental operating action.",
                }],
            },
            "explicitly_immaterial": False,
            "implementation_evidence": [{
                "source_id": "SYNTHETIC:ACTION:IMPLEMENTED",
                "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                "issuer_id": target_issuer_id,
                "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                "responsibility_unit_id": candidate["responsibility_unit_id"],
                "unit": "RMB",
                "published_at": "2020-10-15",
                "field_ref": "Official disclosure of cash payment already made.",
            }],
            "prohibited_substitutes": [
                "FORECAST", "DESIGN_CAPACITY", "CIP", "LOANS", "POST_CUTOFF",
            ],
            "exposure": {
                "kind": "ACTUAL_CASH_OR_RECOGNIZED_ASSET",
                "actual_basis": "ACTUAL_CASH_PAID",
                "amount": 20.0,
                "unit": "RMB",
                "evidence": [{
                    "source_id": "SYNTHETIC:ACTION:CASH-PAID",
                    "source_type": jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT,
                    "issuer_id": target_issuer_id,
                    "perimeter_id": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
                    "responsibility_unit_id": candidate["responsibility_unit_id"],
                    "unit": "RMB",
                    "published_at": "2020-10-15",
                    "field_ref": "Official cash-payment field.",
                }],
            },
        },
        "D3_UNIT_ECONOMICS": {
            "stage": "D3_UNIT_ECONOMICS",
            "predicate_id": "SYN-P-D3B",
            "anchor_id": "SYN-V4-D3-SCALED-MAD",
            "anchor_statement": "Target D3 scaled-MAD from five raw pre-action annual observations.",
            "source_ids": ["SYNTHETIC:TARGET:2015", "SYNTHETIC:TARGET:2019"],
            "frozen_target_reference_period_end": "2019-12-31",
            "baseline_value": 140.0,
            "calculation": {
                "method": jsc.V4_SCALED_MAD_METHOD,
                "scale": jsc.V4_SCALED_MAD_SCALE,
                "input_clock": "D3",
                "conversion_mapping_prohibited": True,
                "median": 120.0,
                "median_absolute_deviation": 10.0,
                "absolute_step": scaled_step,
            },
            "relative_peer_threshold": {
                "formula": jsc.V4_RELATIVE_STEP_FORMULA,
                "target_reference_period_end": "2019-12-31",
                "target_reference_revenue": 1_000.0,
                "target_absolute_ratio_step": 0.014826,
                "common_preaction_period_ends": ["2017-12-31", "2018-12-31", "2019-12-31"],
                "relative_delta_median": -0.005,
                "relative_delta_median_absolute_deviation": 0.005,
                "peer_preaction_relative_scaled_mad": 0.007413,
                "relative_ratio_step": 0.014826,
                "unit": "ratio",
            },
            "primary_threshold": {"operator": "GREATER_THAN_OR_EQUAL", "value": 154.826, "unit": "RMB"},
            "rival_threshold": {"operator": "LESS_THAN_OR_EQUAL", "value": 125.174, "unit": "RMB"},
        },
        "D4_WORKING_CAPITAL_AND_CASH": {
            "stage": "D4_WORKING_CAPITAL_AND_CASH",
            "predicate_id": "SYN-P-D4",
            "anchor_id": "SYN-V4-D4-SCALED-MAD",
            "anchor_statement": "Target D4 scaled-MAD from five raw pre-action annual observations.",
            "source_ids": ["SYNTHETIC:TARGET:2015", "SYNTHETIC:TARGET:2019"],
            "frozen_target_reference_period_end": "2019-12-31",
            "baseline_value": 90.0,
            "calculation": {
                "method": jsc.V4_SCALED_MAD_METHOD,
                "scale": jsc.V4_SCALED_MAD_SCALE,
                "input_clock": "D4",
                "conversion_mapping_prohibited": True,
                "median": 70.0,
                "median_absolute_deviation": 10.0,
                "absolute_step": scaled_step,
            },
            "relative_peer_threshold": {
                "formula": jsc.V4_RELATIVE_STEP_FORMULA,
                "target_reference_period_end": "2019-12-31",
                "target_reference_revenue": 1_000.0,
                "target_absolute_ratio_step": 0.014826,
                "common_preaction_period_ends": ["2017-12-31", "2018-12-31", "2019-12-31"],
                "relative_delta_median": -0.005,
                "relative_delta_median_absolute_deviation": 0.005,
                "peer_preaction_relative_scaled_mad": 0.007413,
                "relative_ratio_step": 0.014826,
                "unit": "ratio",
            },
            "primary_threshold": {"operator": "GREATER_THAN_OR_EQUAL", "value": 104.826, "unit": "RMB"},
            "rival_threshold": {"operator": "LESS_THAN_OR_EQUAL", "value": 75.174, "unit": "RMB"},
        },
    }
    candidate["cash_transmission_observability"]["d4_cash_bridge_coverage"] = {
        "verdict": "COMPLETE_PRE_OUTCOME",
        "accounting_perimeter": jsc.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER,
        "reviewed_period_ends": sorted(item["period_end"] for item in target_history),
        "components": [
            {"component_id": "OPERATING_CASH_FLOW", "treatment": "INCLUDED_FROM_FROZEN_D4_RAW_FIELDS"},
            {"component_id": "LONG_LIVED_ASSET_CASH", "treatment": "INCLUDED_FROM_FROZEN_D4_RAW_FIELDS"},
            {"component_id": "CASH_WORKING_CAPITAL", "treatment": "INCLUDED_FROM_FROZEN_D4_RAW_FIELDS"},
            {
                "component_id": "ACTION_RELATED_CASH",
                "treatment": "OBSERVED_AND_DEDUCTED",
                "evidence": deepcopy(candidate["cash_transmission_observability"]["materiality_anchors"]["action_exposure"]["exposure"]["evidence"]),
            },
        ],
        "unmodeled_material_cash_items": [],
    }
    candidate["discovery_binding"] = _v4_discovery_binding(candidate)
    return candidate


def _v4_cost_restructuring_candidate() -> dict:
    candidate = _v4_peer_panel_candidate()
    contract = candidate["selection_admission_contract"]
    contract["mechanism_topology"] = jsc.V4_COST_RESTRUCTURING_CHAIN
    contract["customer_absorption_requirement"] = {
        "required": False,
        "trigger": jsc.CUSTOMER_ABSORPTION_NOT_REQUIRED_TRIGGER,
        "rationale": "The selected mechanism is an issuer-wide cost restructuring; it does not claim customer absorption.",
    }
    boundary = candidate["cash_transmission_observability"]["common_boundary"]
    target = candidate["peer_panel_observability"]["target"]
    repetitions = []
    for observation in target["annual_d3_d4_raw_observations"][-3:]:
        raw = observation["d3_raw_fields"]["operating_cost_rmb"]
        repetitions.append({
            "period_end": observation["period_end"],
            "published_at": raw["published_at"],
            "source_id": raw["source_id"],
            "field_ref": "Official annual report unit-input-cost measure.",
            "raw_observation": {
                "value": raw["value"],
                "unit": "RMB",
                "definition": "Issuer-wide recurring unit input-cost measure.",
                "evidence": [{
                    "source_id": raw["source_id"],
                    "source_type": raw["source_type"],
                    "issuer_id": raw["issuer_id"],
                    "perimeter_id": raw["perimeter_id"],
                    "responsibility_unit_id": boundary["responsibility_unit_id"],
                    "unit": "RMB",
                    "published_at": raw["published_at"],
                    "field_ref": "Official annual report cost field.",
                }],
            },
        })
    candidate["cost_driver_observability"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "d3_predicate_id": "SYN-P-D3B",
        "failure_disposition": jsc.V4_COST_DRIVER_NO_PRIMARY,
        "observation_kind": "FIXED_COST_ABSORPTION",
        "boundary": deepcopy(boundary),
        "official_field_identity": {
            "field_id": "SYN-UNIT-INPUT-COST",
            "definition": "Issuer-wide recurring unit input-cost measure.",
            "source_class": "OFFICIAL_DISCLOSURE",
            "formula_or_field": "Official annual-report cost field.",
        },
        "hypothesis_signs": {
            "H_A": "COST_DRIVER_SUPPORTS_PRIMARY",
            "H_B": "COST_DRIVER_SUPPORTS_RIVAL",
        },
        "cutoff_before_repetitions": repetitions,
    }
    candidate["d2_non_voter_contract"] = {
        "d2_predicate_id": "SYN-P-D2",
        "verdict": "NOT_CAUSALLY_CENTRAL_PRE_OUTCOME",
        "customer_absorption_conclusion_prohibited": True,
    }
    candidate["discovery_binding"] = _v4_discovery_binding(candidate)
    candidate.pop("customer_absorption_observability")
    return candidate


def _v4_peer_panel_review(candidate: dict) -> dict:
    review = _v3_cash_transmission_review(candidate)
    review["cash_transmission_admission"]["gate_version"] = jsc.PEER_PANEL_ADMISSION_VERSION
    review["customer_absorption_admission"]["gate_version"] = jsc.PEER_PANEL_ADMISSION_VERSION
    review["review_answers"].update({
        "v4_action_same_boundary_implemented": "YES: the actual cash action is implemented before cutoff on the target common boundary.",
        "v4_action_issuer_scope_and_decision_specificity_confirmed": "YES: the action is issuer-wide and discretionary incremental rather than a maintenance or mandated substitute.",
        "v4_materiality_thresholds_exactly_recomputed": "YES: both scaled-MAD steps and baseline plus/minus thresholds recompute exactly.",
        "v4_d3_d4_independent_no_conversion": "YES: D3 and D4 use their respective historical raw series with no conversion mapping.",
        "v4_peer_panel_recurrently_observable_no_replacement": "YES: fixed same-industry panel, annual recurrences and no-replacement contract were checked.",
        "v4_peer_business_and_market_exposure_confirmed": "YES: every frozen member has source-bearing exposure to the same product, geography and customer market before the action.",
        "v4_pre_action_structural_comparability_confirmed": "YES: each selected target and peer annual window was source-checked for scope, presentation and operating-perimeter continuity.",
        "v4_d4_cash_bridge_complete_no_unmodeled_material_cash": "YES: the frozen owner-cash bridge contains all material cash legs and treats action-related cash explicitly.",
    })
    review["v4_materiality_admission"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "action_id": "SYN-V4-ACTION-IMPLEMENTED",
        "reference_period_end": "2019-12-31",
        "verdict": "MECHANICALLY_MATERIAL_PRE_OUTCOME",
        "same_candidate_common_boundary_confirmed": True,
        "implemented_or_irrevocably_incurred_confirmed": True,
        "issuer_scope_bridge_confirmed": True,
        "decision_specific_incremental_exposure_confirmed": True,
        "qualified_action_exposure_confirmed": True,
        "action_exposure_at_least_d3_step_confirmed": True,
        "d3_step_exactly_recomputed": True,
        "d4_step_exactly_recomputed": True,
        "d3_d4_independent_no_conversion": True,
        "review_conclusion": "The action is material enough to admit a training case, without inferring D3-to-D4 causal conversion.",
    }
    review["peer_panel_admission"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "verified_panel_contract_id": candidate["peer_panel_observability"]["panel_contract_id"],
        "verified_frozen_order": candidate["peer_panel_observability"]["frozen_panel"]["frozen_order"],
        "verdict": "FIXED_PANEL_RECURRENTLY_OBSERVABLE_PRE_OUTCOME",
        "same_industry_confirmed": True,
        "common_market_exposure_confirmed": True,
        "target_pre_action_d3_d4_recurrence_confirmed": True,
        "peer_annual_d3_d4_recurrence_confirmed": True,
        "no_replacement_confirmed": True,
        "review_conclusion": "The target and fixed peer panel satisfy recurrent annual D3/D4 observability before outcome access.",
    }
    review["v4_comparability_admission"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "panel_contract_id": candidate["peer_panel_observability"]["panel_contract_id"],
        "verdict": "COMPARABLE_PRE_ACTION_WINDOW_CONFIRMED",
        "target_window_source_checked": True,
        "peer_windows_source_checked": True,
        "material_breaks_excluded_from_selected_windows": True,
        "review_conclusion": "Each selected annual window remains comparable on the required source-bearing dimensions.",
    }
    review["v4_d4_cash_bridge_admission"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "action_id": candidate["cash_transmission_observability"]["materiality_anchors"]["action_exposure"]["action_id"],
        "verdict": "COMPLETE_PRE_OUTCOME",
        "operating_cash_flow_raw_fields_checked": True,
        "long_lived_asset_cash_raw_fields_checked": True,
        "cash_working_capital_raw_fields_checked": True,
        "action_related_cash_observed_or_source_confirmed_not_applicable": True,
        "unmodeled_material_cash_items_absent": True,
        "review_conclusion": "The D4 cash bridge is complete for the permitted operating topology and has no unmodeled material cash item.",
    }
    return review


def _v4_cost_restructuring_review(candidate: dict) -> dict:
    review = _v4_peer_panel_review(candidate)
    review["customer_absorption_admission"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "verdict": "NOT_CAUSALLY_CENTRAL_PRE_OUTCOME",
        "review_conclusion": "This cost restructuring makes no customer-absorption conclusion.",
    }
    review["review_answers"]["v4_cost_driver_recurrently_observable_and_d2_non_voter"] = (
        "YES: cost-driver histories recur on the common boundary and D2 is explicitly a non-voter."
    )
    review["review_answers"]["customer_absorption_non_requirement_justified"] = (
        "YES: the registered mechanism is a cost restructuring and does not assert customer absorption."
    )
    review["v4_cost_driver_admission"] = {
        "gate_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "primary_hypothesis_id": "SYN-H-A",
        "d3_predicate_id": "SYN-P-D3B",
        "verdict": "COST_DRIVER_RECURRENTLY_OBSERVABLE_PRE_OUTCOME",
        "d2_customer_absorption_conclusion_prohibited": True,
        "cost_driver_same_common_boundary_confirmed": True,
        "review_conclusion": "The cost driver is recurrent and the measurement does not infer customer absorption.",
    }
    return review


def _v4_peer_contract_bundles(candidate: dict) -> tuple[dict, dict]:
    """Return the complete V4 source/measurement panel used at registration.

    This deliberately mirrors the candidate's raw pre-action series instead
    of creating a second, hand-maintained history.  It gives the registration
    regression a genuine candidate/source/measurement binding to test.
    """
    panel = candidate["peer_panel_observability"]
    order = deepcopy(panel["frozen_panel"]["frozen_order"])
    method = deepcopy(panel["relative_method"])
    candidate_members = [panel["target"], *panel["peers"]]
    cash = candidate["cash_transmission_observability"]
    d3_formula_id = next(
        leg["official_field_identity"]["field_id"]
        for leg in cash["transmission_legs"]
        if leg["leg_id"] == "OPERATING_CONTRIBUTION"
    )
    d4_formula_id = cash["d4_formula"]["formula_id"]
    raw_field_names = (
        "operating_revenue_rmb", "operating_cost_rmb", "taxes_and_surcharges_rmb",
        "selling_expense_rmb", "administrative_expense_rmb", "operating_cash_flow_rmb",
        "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb",
        "opening_accounts_receivable_rmb", "opening_prepayments_rmb", "opening_inventory_rmb",
        "opening_accounts_payable_rmb", "opening_customer_advances_rmb",
        "ending_accounts_receivable_rmb", "ending_prepayments_rmb", "ending_inventory_rmb",
        "ending_accounts_payable_rmb", "ending_customer_advances_rmb",
    )

    def reference_row(member: dict) -> dict:
        return next(
            row for row in member["annual_d3_d4_raw_observations"]
            if row["period_end"] == method["reference_period_end"]
        )

    def source_outcome(member: dict) -> dict:
        return {
            "period_end": "2020-12-31",
            "d3_formula_id": d3_formula_id,
            "d4_formula_id": d4_formula_id,
            "fields": {
                field_name: {
                    "allowed_source_types": [jsc.V4_OFFICIAL_AUDITED_ANNUAL_REPORT],
                    "issuer_id": member["issuer_id"],
                    "perimeter_id": member["boundary"]["perimeter_id"],
                    "field_ref": f"{member['company_id']}:outcome:{field_name}",
                }
                for field_name in raw_field_names
            },
        }

    source_members = []
    measurement_members = []
    for member in candidate_members:
        reference = reference_row(member)
        outcome_contract = source_outcome(member)
        reference_fields = {
            **reference["d3_raw_fields"], **reference["d4_raw_fields"],
        }
        reference_contract = {
            "period_end": reference["period_end"],
            "d3_formula_id": reference["d3_formula_id"],
            "d4_formula_id": reference["d4_formula_id"],
            "reference_revenue": reference["d3_raw_fields"]["operating_revenue_rmb"]["value"],
            "fields": deepcopy(reference_fields),
        }
        shared_identity = {
            "company_id": member["company_id"],
            "issuer_id": member["issuer_id"],
            "control_group_id": member["control_group_id"],
            "control_group_evidence": deepcopy(member["control_group_evidence"]),
            "responsibility_unit_id": member["responsibility_unit_id"],
            "perimeter_id": member["boundary"]["perimeter_id"],
            "pre_action_history": deepcopy(member["annual_d3_d4_raw_observations"]),
        }
        source_members.append({
            **shared_identity,
            "reference": reference_contract,
            "outcome": deepcopy(outcome_contract),
        })
        measurement_members.append({
            **shared_identity,
            "reference": {
                key: deepcopy(value) for key, value in reference_contract.items()
                if key != "fields"
            },
            "outcome": deepcopy(outcome_contract),
        })
    source = _source_contract()
    source["peer_relative_acquisition"] = {
        "panel_contract_id": panel["panel_contract_id"],
        "frozen_order": order,
        "relative_method": method,
        "outcome_period_end": "2020-12-31",
        "members": source_members,
    }
    measurement = _measurement_contract()
    measurement["peer_relative_measurement"] = {
        "panel_contract_id": panel["panel_contract_id"],
        "frozen_order": deepcopy(order),
        "relative_method": deepcopy(method),
        "outcome_period_end": "2020-12-31",
        "members": measurement_members,
    }
    anchors = cash["materiality_anchors"]
    for rule in measurement["measurement_rules"]:
        if rule["predicate_id"] not in {"SYN-P-D3B", "SYN-P-D4"}:
            continue
        stage_id = (
            "D3_UNIT_ECONOMICS"
            if rule["predicate_id"] == "SYN-P-D3B"
            else "D4_WORKING_CAPITAL_AND_CASH"
        )
        anchor = anchors[stage_id]
        formula_id = d3_formula_id if stage_id == "D3_UNIT_ECONOMICS" else d4_formula_id
        rule["formula_id"] = formula_id
        rule["primary_test"] = deepcopy(anchor["primary_threshold"])
        rule["rival_test"] = deepcopy(anchor["rival_threshold"])
        rule["peer_relative_test"] = {
            "method": jsc.V4_PEER_RELATIVE_METHOD,
            "unit": "ratio",
            "conjunction": "D3_AND_D4",
            "formula_id": formula_id,
            "primary_test": {
                "operator": "GREATER_THAN_OR_EQUAL",
                "value": anchor["relative_peer_threshold"]["relative_ratio_step"],
                "unit": "ratio",
            },
            "rival_test": {
                "operator": "LESS_THAN_OR_EQUAL",
                "value": -anchor["relative_peer_threshold"]["relative_ratio_step"],
                "unit": "ratio",
            },
        }
    return source, measurement


@pytest.mark.parametrize(
    "claim_stages", [FIVE_CLAIM_STAGES, CLAIM_STAGES], ids=["five_claim", "six_claim"],
)
def test_selection_candidate_accepts_only_the_ordered_five_or_six_stage_contract(
    claim_stages: tuple,
) -> None:
    result = jsc.validate_selection_candidate(_candidate(claim_stages))

    assert result["state"] == "REVIEWABLE"
    assert result["findings"] == []


@pytest.mark.parametrize(
    "mutation", ["missing_d3_unit", "wrong_order", "arbitrary_d3_stage"],
)
def test_selection_candidate_rejects_invalid_stage_topology_before_review(
    mutation: str,
) -> None:
    candidate = _candidate()
    predictions = candidate["frozen_prediction_order"]
    if mutation == "missing_d3_unit":
        candidate["frozen_prediction_order"] = [
            item for item in predictions if item["stage"] != "D3_UNIT_ECONOMICS"
        ]
    elif mutation == "wrong_order":
        predictions[1], predictions[2] = predictions[2], predictions[1]
    else:
        predictions[3]["stage"] = "D3_MARGIN"

    candidate_result = jsc.validate_selection_candidate(candidate)
    review_result = jsc.validate_selection_review(
        _candidate_review(candidate), candidate=candidate,
    )

    assert candidate_result["state"] == "INVALID"
    assert "frozen_prediction_order_stage_topology_invalid" in candidate_result["findings"]
    assert review_result["state"] == "INVALID"
    assert "candidate_not_reviewable" in review_result["findings"]


@pytest.mark.parametrize(
    ("field", "value", "finding"),
    [
        ("provenance_role", "HISTORICAL_TEACHING", "provenance_role_invalid"),
        ("selection_status", "NO_PRIMARY", "selection_status_invalid"),
        ("probability_mode", "SUBJECTIVE", "probability_mode_invalid"),
    ],
)
def test_selection_candidate_rejects_inconsistent_training_identity(
    field: str, value: str, finding: str,
) -> None:
    candidate = _candidate()
    candidate[field] = value

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert finding in result["findings"]


def test_legacy_r104_candidate_remains_reviewable_without_retroactive_v3_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    experiment = root / "docs/development/research/experiments/R-104_chongqing_beer_network_pruning_unit_economics_20160430"
    candidate = json.loads((experiment / "01_case_freeze.json").read_text(encoding="utf-8"))
    review = json.loads((experiment / "02_independent_pre_outcome_review.json").read_text(encoding="utf-8"))

    assert "selection_admission_contract" not in candidate
    assert jsc.validate_selection_candidate(candidate) == {
        "schema_version": "judgment-selection-candidate-validation.v1",
        "state": "REVIEWABLE",
        "admission_state": "PENDING_INDEPENDENT_REVIEW",
        "findings": [],
    }
    assert jsc.validate_selection_review(review, candidate=candidate)["state"] == "REVIEWABLE"


def test_v3_cash_transmission_gate_admits_only_recurrent_d3_to_d4_evidence() -> None:
    candidate = _v3_cash_transmission_candidate()
    review = _v3_cash_transmission_review(candidate)

    assert jsc.validate_selection_candidate(candidate) == {
        "schema_version": "judgment-selection-candidate-validation.v1",
        "state": "REVIEWABLE",
        "admission_state": "PENDING_INDEPENDENT_REVIEW",
        "findings": [],
    }
    assert jsc.validate_selection_review(review, candidate=candidate)["state"] == "REVIEWABLE"


def test_v3_customer_absorption_can_use_physical_units_on_the_same_perimeter() -> None:
    candidate = _v3_cash_transmission_candidate()
    candidate["customer_absorption_observability"]["boundary"]["unit"] = "TONNES"
    review = _v3_cash_transmission_review(candidate)

    assert jsc.validate_selection_candidate(candidate)["state"] == "REVIEWABLE"
    assert jsc.validate_selection_review(review, candidate=candidate)["state"] == "REVIEWABLE"


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ("missing_repetition", "cash_transmission_leg_capex_restructuring_cash_not_recurrently_observable"),
        ("d3_substitutes_d4", "cash_transmission_leg_operating_contribution_identity_invalid"),
        ("assume_capex_zero", "cash_transmission_capex_restructuring_cash_assumption_invalid"),
        ("shared_anchors", "cash_transmission_d3_d4_materiality_anchors_not_independent"),
        ("revenue_only_d2", "customer_absorption_observation_kind_invalid"),
    ],
)
def test_v3_cash_transmission_gate_fails_to_no_primary_on_material_observability_break(
    mutation: str, finding: str,
) -> None:
    candidate = _v3_cash_transmission_candidate()
    observability = candidate["cash_transmission_observability"]
    if mutation == "missing_repetition":
        observability["transmission_legs"][2]["cutoff_before_repetitions"].pop()
    elif mutation == "d3_substitutes_d4":
        observability["transmission_legs"][0].update({
            "clock": "D4", "stage": "D4_WORKING_CAPITAL_AND_CASH",
        })
    elif mutation == "assume_capex_zero":
        observability["d4_formula"]["capex_restructuring_cash_treatment"] = "ASSUME_ZERO"
    elif mutation == "shared_anchors":
        observability["materiality_anchors"]["D4_WORKING_CAPITAL_AND_CASH"]["anchor_id"] = (
            observability["materiality_anchors"]["D3_UNIT_ECONOMICS"]["anchor_id"]
        )
    else:
        candidate["customer_absorption_observability"].update({
            "observation_kind": "REVENUE",
            "not_mechanically_changed_by_action": False,
        })

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert finding in result["findings"]


def test_v3_cash_transmission_gate_requires_independent_pre_outcome_reviewer_attestation() -> None:
    candidate = _v3_cash_transmission_candidate()
    review = _candidate_review(candidate)

    result = jsc.validate_selection_review(review, candidate=candidate)

    assert result["state"] == "INVALID"
    assert "independent_review_answers_incomplete" in result["findings"]
    assert "cash_transmission_independent_review_missing" in result["findings"]


def test_v4_candidate_admits_fixed_peer_panel_and_mechanical_materiality() -> None:
    candidate = _v4_peer_panel_candidate()
    review = _v4_peer_panel_review(candidate)

    assert jsc.validate_selection_candidate(candidate) == {
        "schema_version": "judgment-selection-candidate-validation.v1",
        "state": "REVIEWABLE",
        "admission_state": "PENDING_INDEPENDENT_REVIEW",
        "findings": [],
    }
    assert jsc.validate_selection_review(review, candidate=candidate)["state"] == "REVIEWABLE"


def test_v4_candidate_rejects_two_independent_comparators() -> None:
    """V4 retains one target plus three independent peers for a relative claim."""
    candidate = _v4_peer_panel_candidate()
    panel = candidate["peer_panel_observability"]
    panel["peers"] = panel["peers"][:2]
    frozen_order = [candidate["company_id"], *[peer["company_id"] for peer in panel["peers"]]]
    panel["frozen_panel"]["frozen_order"] = frozen_order
    panel["frozen_panel"]["universe"]["eligible_company_ids"] = frozen_order

    result = jsc.validate_selection_candidate(candidate)
    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert "v4_peer_panel_peer_count_must_be_three_to_seven" in result["findings"]


def test_v4_candidate_rejects_one_comparator_panel() -> None:
    candidate = _v4_peer_panel_candidate()
    panel = candidate["peer_panel_observability"]
    panel["peers"] = panel["peers"][:1]
    frozen_order = [candidate["company_id"], *[peer["company_id"] for peer in panel["peers"]]]
    panel["frozen_panel"]["frozen_order"] = frozen_order
    panel["frozen_panel"]["universe"]["eligible_company_ids"] = frozen_order

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert "v4_peer_panel_peer_count_must_be_three_to_seven" in result["findings"]


def test_cement_h1_known_break_exclusions_leave_insufficient_v4_capacity() -> None:
    """The three pending carriers remain useful but cannot freeze a V4 panel.

    H1 remains a reviewable source/universe receipt.  Its two known breaks are
    not silently reintroduced merely to meet the target-plus-three-peer
    comparative topology.
    """
    root = Path(__file__).resolve().parents[1]
    package_path = root / (
        "docs/development/research/cohorts/"
        "COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"
    )
    cement_h1 = json.loads(package_path.read_text(encoding="utf-8"))

    assert discovery.validate_stage0_static_source_package(cement_h1)["state"] == (
        discovery.STAGE0_FEASIBILITY_REVIEWABLE
    )
    excluded = [
        member["company_id"]
        for member in cement_h1["members"]
        if member["final_peer_panel_disposition"] == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    ]
    pending = [
        member["company_id"]
        for member in cement_h1["members"]
        if member["final_peer_panel_disposition"] == "PENDING_ACTION_WINDOW_REVIEW"
    ]

    assert excluded == ["CN:600801", "CN:000401"]
    assert pending == ["CN:600585", "CN:600425", "CN:600802"]
    assert len(pending) == 3
    assert len(pending) < 1 + 3  # V4 requires one target plus three peers.

    candidate = _v4_peer_panel_candidate()
    panel = candidate["peer_panel_observability"]
    panel["peers"] = panel["peers"][:len(pending) - 1]
    frozen = panel["frozen_panel"]
    frozen_order = [candidate["company_id"], *[peer["company_id"] for peer in panel["peers"]]]
    frozen["frozen_order"] = frozen_order
    frozen["universe"]["eligible_company_ids"] = frozen_order
    frozen["exclusions"] = []

    result = jsc.validate_selection_candidate(candidate)
    assert result["state"] == "INVALID"
    assert "v4_peer_panel_peer_count_must_be_three_to_seven" in result["findings"]


def test_v4_peer_relative_noise_calibration_can_exceed_target_only_materiality_step() -> None:
    target = {
        "2017-12-31": {"d3_value": 100.0, "d4_value": 100.0, "reference_revenue": 1_000.0},
        "2018-12-31": {"d3_value": 101.0, "d4_value": 101.0, "reference_revenue": 1_000.0},
        "2019-12-31": {"d3_value": 102.0, "d4_value": 102.0, "reference_revenue": 1_000.0},
        "2020-12-31": {"d3_value": 99.0, "d4_value": 99.0, "reference_revenue": 1_000.0},
        "2021-12-31": {"d3_value": 100.0, "d4_value": 100.0, "reference_revenue": 1_000.0},
    }
    peers = [
        {
            "2019-12-31": {"d3_value": 100.0, "d4_value": 100.0, "reference_revenue": 1_000.0},
            "2020-12-31": {"d3_value": 130.0, "d4_value": 130.0, "reference_revenue": 1_000.0},
            "2021-12-31": {"d3_value": 80.0, "d4_value": 80.0, "reference_revenue": 1_000.0},
        },
        {
            "2019-12-31": {"d3_value": 100.0, "d4_value": 100.0, "reference_revenue": 1_000.0},
            "2020-12-31": {"d3_value": 120.0, "d4_value": 120.0, "reference_revenue": 1_000.0},
            "2021-12-31": {"d3_value": 70.0, "d4_value": 70.0, "reference_revenue": 1_000.0},
        },
        {
            "2019-12-31": {"d3_value": 100.0, "d4_value": 100.0, "reference_revenue": 1_000.0},
            "2020-12-31": {"d3_value": 110.0, "d4_value": 110.0, "reference_revenue": 1_000.0},
            "2021-12-31": {"d3_value": 60.0, "d4_value": 60.0, "reference_revenue": 1_000.0},
        },
    ]

    findings, calibration = jsc._v4_peer_relative_preaction_calibration(
        target_observations=target,
        peer_observations=peers,
        stage="D3_UNIT_ECONOMICS",
        reference_period_end="2019-12-31",
    )

    assert findings == []
    assert calibration is not None
    assert calibration["peer_preaction_relative_scaled_mad"] > 0.01
    assert calibration["peer_preaction_relative_scaled_mad"] > (1.4826 / 1_000.0)


def test_v4_cost_restructuring_chain_admits_a_source_bearing_cost_driver_without_claiming_customer_absorption() -> None:
    candidate = _v4_cost_restructuring_candidate()
    review = _v4_cost_restructuring_review(candidate)

    assert jsc.validate_selection_candidate(candidate)["state"] == "REVIEWABLE"
    assert jsc.validate_selection_review(review, candidate=candidate)["state"] == "REVIEWABLE"

    candidate["d2_non_voter_contract"]["customer_absorption_conclusion_prohibited"] = False
    result = jsc.validate_selection_candidate(candidate)
    assert result["admission_state"] == "NO_PRIMARY"
    assert "v4_cost_driver_d2_non_voter_contract_invalid" in result["findings"]


def test_v4_candidate_accepts_only_h1_h2_declared_pre_outcome_raw_sources() -> None:
    candidate = _v4_peer_panel_candidate()

    assert jsc.validate_selection_candidate(candidate) == {
        "schema_version": "judgment-selection-candidate-validation.v1",
        "state": "REVIEWABLE",
        "admission_state": "PENDING_INDEPENDENT_REVIEW",
        "findings": [],
    }


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (
            "target_source_id",
            "peer_panel_observability.target.annual_d3_d4_raw_observations[0]."
            "d3_raw_fields.operating_revenue_rmb_source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "target_page",
            "peer_panel_observability.target.annual_d3_d4_raw_observations[0]."
            "d3_raw_fields.operating_revenue_rmb_field_ref_not_declared_static_pdf_page",
        ),
        (
            "target_h2_action_pdf",
            "peer_panel_observability.target.annual_d3_d4_raw_observations[0]."
            "d3_raw_fields.operating_revenue_rmb_must_cite_h1_annual_static_pdf",
        ),
        (
            "peer_source_id",
            "peer_panel_observability.peers[0].annual_d3_d4_raw_observations[0]."
            "d4_raw_fields.operating_cash_flow_rmb_source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "peer_publication_time",
            "peer_panel_observability.peers[0].annual_d3_d4_raw_observations[0]."
            "d4_raw_fields.operating_cash_flow_rmb_published_at_does_not_match_declared_static_pdf_identity",
        ),
    ],
)
def test_v4_candidate_rejects_target_and_peer_raw_citations_outside_static_source_map(
    mutation: str, finding: str,
) -> None:
    candidate = _v4_peer_panel_candidate()
    target_raw = candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"][0][
        "d3_raw_fields"
    ]["operating_revenue_rmb"]
    peer_raw = candidate["peer_panel_observability"]["peers"][0]["annual_d3_d4_raw_observations"][0][
        "d4_raw_fields"
    ]["operating_cash_flow_rmb"]
    if mutation == "target_source_id":
        target_raw["source_id"] = "SYNTHETIC:UNDECLARED:TARGET:RAW"
    elif mutation == "target_page":
        target_raw["field_ref"] = "SYNTHETIC:TARGET:UNDECLARED PDF p12"
    elif mutation == "target_h2_action_pdf":
        source = next(
            item for item in candidate["discovery_binding"]["action_screen_extension"]["static_pdf_sources"]
            if item["source_id"] == "SYNTHETIC:ACTION:IMPLEMENTED"
        )
        target_raw.update({
            field: source[field]
            for field in ("source_id", "source_type", "issuer_id", "perimeter_id", "unit", "published_at")
        })
        target_raw["field_ref"] = source["field_refs"][0]
    elif mutation == "peer_source_id":
        peer_raw["source_id"] = "SYNTHETIC:UNDECLARED:PEER:RAW"
    else:
        peer_raw["published_at"] = "2020-03-31"

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert finding in result["findings"]


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (
            "control",
            "peer_panel_observability.target.control_group_evidence[0]_"
            "source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "comparability",
            "peer_panel_observability.target.comparability_register.dimensions[0]."
            "period_statuses[0].evidence[0]_source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "action",
            "cash_transmission_observability.materiality_anchors.action_exposure."
            "implementation_evidence[0]_source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "cash_bridge",
            "cash_transmission_observability.d4_cash_bridge_coverage.components[3].evidence[0]_"
            "source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "facts",
            "cutoff_before_facts[0].source_ids[0]_source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "d2",
            "customer_absorption_observability.cutoff_before_repetitions[0].raw_observation.evidence_"
            "source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
        (
            "cost",
            "cost_driver_observability.cutoff_before_repetitions[0].raw_observation.evidence[0]_"
            "source_id_not_declared_in_h1_h2_static_pdf_map",
        ),
    ],
)
def test_v4_candidate_closes_each_modeled_pre_outcome_citation_class(
    mutation: str, finding: str,
) -> None:
    candidate = _v4_cost_restructuring_candidate() if mutation == "cost" else _v4_peer_panel_candidate()
    panel = candidate["peer_panel_observability"]
    cash = candidate["cash_transmission_observability"]
    if mutation == "control":
        citation = panel["target"]["control_group_evidence"][0]
    elif mutation == "comparability":
        citation = panel["target"]["comparability_register"]["dimensions"][0]["period_statuses"][0]["evidence"][0]
    elif mutation == "action":
        citation = cash["materiality_anchors"]["action_exposure"]["implementation_evidence"][0]
    elif mutation == "cash_bridge":
        citation = cash["d4_cash_bridge_coverage"]["components"][3]["evidence"][0]
    elif mutation == "facts":
        candidate["cutoff_before_facts"][0]["source_ids"][0] = "SYNTHETIC:UNDECLARED:FACT"
        citation = None
    elif mutation == "d2":
        citation = candidate["customer_absorption_observability"]["cutoff_before_repetitions"][0][
            "raw_observation"
        ]["evidence"]
    else:
        citation = candidate["cost_driver_observability"]["cutoff_before_repetitions"][0][
            "raw_observation"
        ]["evidence"][0]
    if citation is not None:
        citation["source_id"] = "SYNTHETIC:UNDECLARED:" + mutation.upper()

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert finding in result["findings"]


@pytest.mark.parametrize(
    ("evidence_path", "finding"),
    [
        ("implementation", "v4_discovery_binding_action_evidence_mismatch"),
        ("issuer_scope_bridge", "v4_discovery_binding_action_scope_bridge_mismatch"),
        ("decision_specificity", "v4_discovery_binding_action_decision_specificity_mismatch"),
        ("exposure", "v4_discovery_binding_action_exposure_mismatch"),
    ],
)
def test_v4_candidate_rejects_action_evidence_from_another_declared_page_of_the_same_h2_pdf(
    evidence_path: str, finding: str,
) -> None:
    candidate = _v4_peer_panel_candidate()
    action = candidate["cash_transmission_observability"]["materiality_anchors"]["action_exposure"]
    if evidence_path == "implementation":
        citation = action["implementation_evidence"][0]
    elif evidence_path == "issuer_scope_bridge":
        citation = action["issuer_scope_bridge"]["evidence"][0]
    elif evidence_path == "decision_specificity":
        citation = action["decision_specificity"]["evidence"][0]
    else:
        citation = action["exposure"]["evidence"][0]
    source = next(
        item for item in candidate["discovery_binding"]["action_screen_extension"]["static_pdf_sources"]
        if item["source_id"] == citation["source_id"]
    )
    alternate_page = source["field_refs"][0].replace("p12", "p13")
    source["field_refs"].append(alternate_page)
    citation["field_ref"] = alternate_page

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert finding in result["findings"]


def test_v4_candidate_rejects_action_statement_rewritten_against_h2_screen() -> None:
    candidate = _v4_peer_panel_candidate()
    candidate["cash_transmission_observability"]["materiality_anchors"]["action_exposure"][
        "action_statement"
    ] = "The issuer expanded a new network rather than closing the disclosed obsolete network."

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert "v4_discovery_binding_action_identity_mismatch" in result["findings"]


@pytest.mark.parametrize(
    "candidate_field",
    ("price_delta_field_ref", "preaction_actual_units_field_ref"),
)
def test_v4_candidate_rejects_price_action_field_reference_rewritten_against_h2_screen(
    candidate_field: str,
) -> None:
    candidate = _v4_peer_panel_candidate()
    candidate_exposure = candidate["cash_transmission_observability"]["materiality_anchors"][
        "action_exposure"
    ]["exposure"]
    candidate_exposure.pop("actual_basis")
    candidate_exposure.update({
        "kind": "IMPLEMENTED_NET_PRICE_DELTA_X_PREACTION_ACTUAL_UNITS",
        "amount": 100.0,
        "implemented_net_price_delta": 2.0,
        "preaction_actual_units": 50.0,
        "price_delta_field_ref": "H2:PRICE:FIELD",
        "preaction_actual_units_field_ref": "H2:UNITS:FIELD",
    })
    screen_exposure = candidate["discovery_binding"]["action_screen_extension"]["action"]["exposure"]
    screen_exposure.pop("actual_basis")
    screen_exposure.update({
        "kind": "IMPLEMENTED_NET_PRICE_DELTA_X_PREACTION_ACTUAL_UNITS",
        "implemented_net_price_delta_field_ref": "H2:PRICE:FIELD",
        "preaction_actual_units_field_ref": "H2:UNITS:FIELD",
    })
    candidate_exposure[candidate_field] = "CANDIDATE:DRIFTED:FIELD"

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert "v4_discovery_binding_action_exposure_mismatch" in result["findings"]


def test_v4_candidate_rejects_cutoff_fact_rebound_to_an_h1_pdf() -> None:
    candidate = _v4_peer_panel_candidate()
    fact = candidate["cutoff_before_facts"][0]
    source = next(
        item for item in candidate["discovery_binding"]["stage0_static_package"]["static_pdf_sources"]
        if item["source_id"] == "COHORT:ANNUAL:CN:SYNTHETIC:2019-12-31"
    )
    fact["source_ids"] = [source["source_id"]]
    fact["evidence"] = [{
        key: source[key]
        for key in (
            "source_id", "source_type", "issuer_id", "perimeter_id",
            "responsibility_unit_id", "unit", "published_at",
        )
    } | {"field_ref": source["field_refs"][0]}]

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert "v4_discovery_binding_cutoff_before_facts_mismatch" in result["findings"]
    assert not any("cutoff_before_facts[0].source_ids[0]_source_id_not_declared" in item for item in result["findings"])


@pytest.mark.parametrize(
    ("topology", "finding"),
    [
        ("customer", "v4_discovery_binding_d2_repetition_citation_mismatch:2017-12-31"),
        ("cost", "v4_discovery_binding_cost_driver_repetition_citation_mismatch:2017-12-31"),
    ],
)
def test_v4_candidate_rejects_d2_or_cost_raw_evidence_rebound_to_another_h2_period(
    topology: str, finding: str,
) -> None:
    candidate = _v4_cost_restructuring_candidate() if topology == "cost" else _v4_peer_panel_candidate()
    observability = (
        candidate["cost_driver_observability"]
        if topology == "cost"
        else candidate["customer_absorption_observability"]
    )
    repetitions = observability["cutoff_before_repetitions"]
    first_raw = repetitions[0]["raw_observation"]
    first_raw["evidence"] = deepcopy(repetitions[1]["raw_observation"]["evidence"])

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert finding in result["findings"]


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ("missing_h1", "v4_discovery_binding_stage0_static_package_missing"),
        ("missing_h2", "v4_discovery_binding_action_screen_extension_missing"),
        ("legacy_manifest_only", "v4_discovery_binding_stage0_static_package_missing"),
    ],
)
def test_v4_candidate_cannot_admit_a_legacy_triage_manifest_without_h1_and_h2(
    mutation: str, finding: str,
) -> None:
    candidate = _v4_peer_panel_candidate()
    binding = candidate["discovery_binding"]
    if mutation == "missing_h1":
        binding.pop("stage0_static_package")
    elif mutation == "missing_h2":
        binding.pop("action_screen_extension")
    else:
        binding["manifest"] = {
            "schema_version": discovery.MANIFEST_SCHEMA_VERSION,
            "manifest_id": "LEGACY:ONLY",
        }
        binding.pop("stage0_static_package")
        binding.pop("action_screen_extension")

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert finding in result["findings"]


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ("arbitrary_threshold", "v4_d3_materiality_primary_threshold_not_baseline_plus_or_minus_exact_step"),
        ("plan", "v4_action_not_implemented_or_irrevocably_incurred"),
        ("forecast", "v4_action_exposure_not_actual_cash_or_recognized_asset"),
        ("immaterial", "v4_action_explicitly_immaterial"),
        ("wrong_boundary", "v4_action_boundary_mismatch"),
        ("narrow_action_scope", "v4_action_issuer_scope_bridge_invalid"),
        ("maintenance_substitute", "v4_action_decision_specificity_invalid"),
        ("too_few_target_periods", "v4_target_d3_d4_history_not_recurrently_observable"),
        ("too_few_peer_periods", "v4_peer_panel_peer[0]_d3_d4_history_not_recurrently_observable"),
        ("d3_substitutes_d4", "v4_d4_materiality_input_clock_not_independent"),
        ("unverified", "v4_target_d3_d4_history[0].d3_raw_fields.operating_revenue_rmb_source_type_not_official_audited_annual_report"),
        ("unverified_action", "v4_action_implementation_evidence[0]_source_type_not_official"),
        ("wrong_action_boundary", "v4_action_exposure_evidence[0]_boundary_mismatch"),
        ("wrong_issuer", "v4_target_d3_d4_history[0].d3_raw_fields.operating_revenue_rmb_issuer_or_perimeter_mismatch"),
        ("wrong_perimeter", "v4_target_d3_d4_history[0].d4_raw_fields.operating_cash_flow_rmb_issuer_or_perimeter_mismatch"),
        ("bare_d4", "v4_target_d3_d4_history[0]_identity_invalid"),
        ("unrelated_formula", "v4_target_d3_d4_history[0]_frozen_d3_d4_formula_identity_mismatch"),
        ("post_action_disclosure", "v4_target_d3_d4_history[4].d3_raw_fields.operating_revenue_rmb_not_disclosed_before_action"),
        ("peer_post_action_control", "v4_peer_panel_peer[0]_control_group_evidence[0]_not_disclosed_before_action"),
        ("peer_post_action_history", "v4_peer_panel_peer[0]_d3_d4_history[2].d3_raw_fields.operating_revenue_rmb_not_disclosed_before_action"),
        ("peer_missing_common_reference", "v4_peer_panel_reference_period_not_common_to_all_members"),
        ("d2_channel_inventory", "v4_customer_absorption_kind_not_direct_customer_measure"),
        ("d2_raw_definition_drift", "v4_customer_absorption_repetition[1]_raw_definition_drift"),
        ("discovery_action_drift", "v4_discovery_binding_action_identity_mismatch"),
        ("discovery_d2_drift", "v4_discovery_binding_d2_identity_mismatch"),
        ("discovery_cohort_after_action", "v4_discovery_binding.invalid:action_screen_extension.invalid:cohort_selection_as_of_not_before_action"),
        ("discovery_cohort_currently_insufficient", "v4_discovery_binding.invalid:stage0_static_package.invalid:current_admission_assessment.status:must_equal_feasible_for_h1_static_source_package"),
        ("same_control_peer", "v4_peer_panel_control_group_not_independent"),
        ("peer_market_mismatch", "v4_peer_panel_peer[0]_market_exposure_identity_mismatch"),
        ("control_evidence_mismatch", "v4_peer_panel_target_control_group_evidence[0]_control_group_mismatch"),
        ("relative_step_drift", "v4_d3_materiality_relative_peer_threshold_not_exactly_derived"),
        ("peer_noise_step_drift", "v4_d3_materiality_relative_peer_threshold_not_exactly_derived"),
        ("structural_break", "v4_target_comparability_dimension[0]_period[0]_not_comparable"),
        ("unmodeled_action_cash", "v4_d4_cash_bridge_unmodeled_material_item_present"),
        ("capital_allocation_action", "v4_action_type_not_supported_by_operating_cash_bridge"),
    ],
)
def test_v4_candidate_returns_no_primary_for_materiality_or_panel_attack(
    mutation: str, finding: str,
) -> None:
    candidate = _v4_peer_panel_candidate()
    anchors = candidate["cash_transmission_observability"]["materiality_anchors"]
    action = anchors["action_exposure"]
    if mutation == "arbitrary_threshold":
        anchors["D3_UNIT_ECONOMICS"]["primary_threshold"]["value"] += 1.0
    elif mutation == "plan":
        action["action_state"] = "PLANNED"
    elif mutation == "forecast":
        action["exposure"]["actual_basis"] = "FORECAST"
    elif mutation == "immaterial":
        action["explicitly_immaterial"] = True
    elif mutation == "wrong_boundary":
        action["boundary"]["perimeter_id"] = "SEGMENT_ONLY"
    elif mutation == "narrow_action_scope":
        action["issuer_scope_bridge"]["action_scope_relation"] = "PROJECT_ONLY"
    elif mutation == "maintenance_substitute":
        action["decision_specificity"]["incremental_to_maintenance_or_mandated_baseline"] = False
    elif mutation == "too_few_target_periods":
        candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"].pop()
    elif mutation == "too_few_peer_periods":
        candidate["peer_panel_observability"]["peers"][0]["annual_d3_d4_raw_observations"].pop()
    elif mutation == "unverified":
        candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"][0][
            "d3_raw_fields"
        ]["operating_revenue_rmb"]["source_type"] = "UNVERIFIED"
    elif mutation == "unverified_action":
        action["implementation_evidence"][0]["source_type"] = "UNVERIFIED"
    elif mutation == "wrong_action_boundary":
        action["exposure"]["evidence"][0]["responsibility_unit_id"] = "UNIT:WRONG"
    elif mutation == "wrong_issuer":
        candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"][0][
            "d3_raw_fields"
        ]["operating_revenue_rmb"]["issuer_id"] = "ISSUER:WRONG"
    elif mutation == "wrong_perimeter":
        candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"][0][
            "d4_raw_fields"
        ]["operating_cash_flow_rmb"]["perimeter_id"] = "PARENT_ONLY"
    elif mutation == "bare_d4":
        observation = candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"][0]
        observation.pop("d4_raw_fields")
        observation["d4_value"] = 50.0
    elif mutation == "unrelated_formula":
        candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"][0][
            "d4_formula_id"
        ] = "UNRELATED_CASH_SERIES"
    elif mutation == "post_action_disclosure":
        candidate["peer_panel_observability"]["target"]["annual_d3_d4_raw_observations"][4][
            "d3_raw_fields"
        ]["operating_revenue_rmb"]["published_at"] = "2020-10-15"
    elif mutation == "peer_post_action_control":
        candidate["peer_panel_observability"]["peers"][0]["control_group_evidence"][0]["published_at"] = "2020-10-15"
    elif mutation == "peer_post_action_history":
        candidate["peer_panel_observability"]["peers"][0]["annual_d3_d4_raw_observations"][2][
            "d3_raw_fields"
        ]["operating_revenue_rmb"]["published_at"] = "2020-10-15"
    elif mutation == "peer_missing_common_reference":
        candidate["peer_panel_observability"]["peers"][0]["annual_d3_d4_raw_observations"][2]["period_end"] = "2019-11-30"
        for raw_fields in (
            candidate["peer_panel_observability"]["peers"][0]["annual_d3_d4_raw_observations"][2]["d3_raw_fields"],
            candidate["peer_panel_observability"]["peers"][0]["annual_d3_d4_raw_observations"][2]["d4_raw_fields"],
        ):
            for raw in raw_fields.values():
                raw["period_end"] = "2019-11-30"
    elif mutation == "d2_channel_inventory":
        candidate["customer_absorption_observability"]["observation_kind"] = "CHANNEL_INVENTORY"
    elif mutation == "d2_raw_definition_drift":
        candidate["customer_absorption_observability"]["cutoff_before_repetitions"][1]["raw_observation"][
            "definition"
        ] = "Different inventory definition."
    elif mutation == "discovery_action_drift":
        action["action_id"] = "SYN-V4-ACTION-SWAPPED"
    elif mutation == "discovery_d2_drift":
        candidate["customer_absorption_observability"]["official_field_identity"]["field_id"] = "SYN-D2-SWAPPED"
    elif mutation == "discovery_cohort_after_action":
        stage0 = candidate["discovery_binding"]["stage0_static_package"]
        stage0["selection_as_of"] = "2020-10-15T23:59:59+08:00"
        stage0["cohort_eligibility_as_of"] = "2020-10-15T23:59:59+08:00"
        candidate["discovery_binding"]["action_screen_extension"]["stage0_selection_as_of"] = "2020-10-15T23:59:59+08:00"
    elif mutation == "discovery_cohort_currently_insufficient":
        candidate["discovery_binding"]["stage0_static_package"]["current_admission_assessment"] = {
            "status": "INSUFFICIENT_FOR_V4_FINAL_PANEL",
        }
    elif mutation == "same_control_peer":
        candidate["peer_panel_observability"]["peers"][0]["control_group_id"] = candidate[
            "peer_panel_observability"
        ]["target"]["control_group_id"]
    elif mutation == "peer_market_mismatch":
        candidate["peer_panel_observability"]["peers"][0]["market_exposure"][
            "geographic_scope"
        ] = "Different market"
    elif mutation == "control_evidence_mismatch":
        candidate["peer_panel_observability"]["target"]["control_group_evidence"][0][
            "observed_control_group_id"
        ] = "CONTROL_GROUP:UNRELATED"
    elif mutation == "relative_step_drift":
        anchors["D3_UNIT_ECONOMICS"]["relative_peer_threshold"]["relative_ratio_step"] += 0.01
    elif mutation == "peer_noise_step_drift":
        anchors["D3_UNIT_ECONOMICS"]["relative_peer_threshold"][
            "peer_preaction_relative_scaled_mad"
        ] += 0.01
    elif mutation == "structural_break":
        candidate["peer_panel_observability"]["target"]["comparability_register"]["dimensions"][0][
            "period_statuses"
        ][0]["status"] = "MATERIAL_BREAK"
    elif mutation == "unmodeled_action_cash":
        candidate["cash_transmission_observability"]["d4_cash_bridge_coverage"][
            "unmodeled_material_cash_items"
        ] = ["ACQUISITION_CASH"]
    elif mutation == "capital_allocation_action":
        action["economic_action_type"] = "BUSINESS_COMBINATION"
    else:
        anchors["D4_WORKING_CAPITAL_AND_CASH"]["calculation"]["input_clock"] = "D3"

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert finding in result["findings"]


def test_v4_action_screen_rejects_a_final_peer_append_before_panel_review() -> None:
    candidate = _v4_peer_panel_candidate()
    candidate["discovery_binding"]["action_screen_extension"]["final_peer"] = "CN:SYNTHETIC-PEER-4"

    result = jsc.validate_selection_candidate(candidate)

    assert result["state"] == "INVALID"
    assert result["admission_state"] == "NO_PRIMARY"
    assert "v4_discovery_binding.invalid:action_screen_extension:contains_unapproved_information" in result["findings"]


def test_v4_review_requires_independent_action_recomputation_and_panel_attestation() -> None:
    candidate = _v4_peer_panel_candidate()
    review = _v3_cash_transmission_review(candidate)
    review["cash_transmission_admission"]["gate_version"] = jsc.PEER_PANEL_ADMISSION_VERSION
    review["customer_absorption_admission"]["gate_version"] = jsc.PEER_PANEL_ADMISSION_VERSION

    result = jsc.validate_selection_review(review, candidate=candidate)

    assert result["state"] == "INVALID"
    assert "independent_review_answers_incomplete" in result["findings"]
    assert "v4_materiality_independent_review_missing" in result["findings"]
    assert "v4_peer_panel_independent_review_missing" in result["findings"]


def _measurement_contract(claim_stages: tuple = CLAIM_STAGES) -> dict:
    rules = [
        {
            "predicate_id": "SYN-P-D1", "clock": "D1",
            "required_observation": "same-unit implementation",
            "prohibited_substitutes": ["announcement"],
        },
        {
            "predicate_id": "SYN-P-D2", "clock": "D2",
            "required_observation": "same-unit customer absorption",
            "prohibited_substitutes": ["industry demand"],
        },
        {
            "predicate_id": "SYN-P-D3A", "clock": "D3",
            "required_observation": "same-unit product volume",
            "prohibited_substitutes": ["group volume"],
            "baseline_prediction": {
                "operator": "EQUAL_POINT_FORECAST", "value": 100.0, "unit": "tonnes",
            },
        },
        {
            "predicate_id": "SYN-P-D3B", "clock": "D3",
            "required_observation": "same-unit gross margin",
            "prohibited_substitutes": ["group margin"],
            "primary_test": {"operator": "GREATER_THAN_OR_EQUAL", "value": 10.0, "unit": "percent"},
            "rival_test": {"operator": "LESS_THAN", "value": 10.0, "unit": "percent"},
            "baseline_prediction": {
                "operator": "EQUAL_POINT_FORECAST", "value": 12.0, "unit": "percent",
            },
        },
        {
            "predicate_id": "SYN-P-D4", "clock": "D4",
            "required_observation": "same-unit attributable cash",
            "prohibited_substitutes": ["group cash"],
            "primary_test": {"operator": "GREATER_THAN", "value": 0.0, "unit": "RMB"},
            "rival_test": {"operator": "LESS_THAN_OR_EQUAL", "value": 0.0, "unit": "RMB"},
        },
        {
            "predicate_id": "SYN-P-D5", "clock": "D5",
            "required_observation": "same-unit capital return",
            "prohibited_substitutes": ["security return"],
            "diagnostic_mode": {"state": "CONTINUOUS_UNKNOWN_NO_SELECTION_HIT_MISS"},
        },
    ]
    predicate_ids = {predicate_id for _, _, predicate_id in claim_stages}
    return {
        "schema_version": "judgment-selection-measurement-contract.v1",
        "case_id": CASE_ID,
        "freeze_id": FREEZE_ID,
        "selection_status": "SELECTION_ADMITTED",
        "measurement_rules": [
            rule for rule in rules if rule["predicate_id"] in predicate_ids
        ],
    }


def _source_contract(claim_stages: tuple = CLAIM_STAGES) -> dict:
    return {
        "schema_version": "judgment-outcome-acquisition-contract.v1",
        "case_id": CASE_ID,
        "company_id": "CN:SYNTHETIC",
        "cutoff_at": "2020-12-31T23:59:59+08:00",
        "clocks": [
            {"claim_id": claim_id, "stage_id": stage_id}
            for claim_id, stage_id, _ in claim_stages
        ],
    }


def _joint_mapping() -> dict[str, str]:
    verdicts = ("A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC")
    return {
        f"{left}|{right}": (
            "NOT_DIAGNOSTIC"
            if "NOT_DIAGNOSTIC" in {left, right}
            else left
            if left == right and left in {"A_ONLY", "B_ONLY"}
            else "MIXED"
        )
        for left in verdicts
        for right in verdicts
    }


def _resolution(claim_stages: tuple = CLAIM_STAGES) -> dict:
    claim_ids = [claim_id for claim_id, _, _ in claim_stages]
    point_identities = [
        {
            "claim_id": claim_id,
            "predicate_id": predicate_id,
            "point_value": 100.0 if stage_id == "D3_PRODUCT_VOLUME" else 12.0,
            "unit": "tonnes" if stage_id == "D3_PRODUCT_VOLUME" else "percent",
        }
        for claim_id, stage_id, predicate_id in claim_stages
        if stage_id in {"D3_PRODUCT_VOLUME", "D3_UNIT_ECONOMICS"}
    ]
    return {
        "schema_version": "judgment-selection-resolution-amendment.v1",
        "amendment_id": "SYN-AMENDMENT-V1",
        "case_id": CASE_ID,
        "freeze_id": FREEZE_ID,
        "created_at": "2026-08-21T02:00:00+08:00",
        "author_id": "synthetic-amendment-author",
        "selector_id": "synthetic-selector",
        "amendment_status": "CANDIDATE_PENDING_INDEPENDENT_REVIEW",
        "append_only_scope": "RESOLUTION_RULES_ONLY_NO_FROZEN_PREDICTION_OR_MEASUREMENT_CHANGE",
        "amended_artifacts": [
            "01_case_freeze.json", "03_outcome_acquisition_contract.json", "04_measurement_contract.json",
        ],
        "pre_outcome_review_ref": "02_independent_pre_outcome_review.json",
        "registered_claim_ids": claim_ids,
        "independent_review_required": True,
        "execution_authorized": False,
        "joint_selection_resolution": {
            "input_claim_ids": ["SYN:D3B", "SYN:D4"],
            "input_predicate_ids": ["SYN-P-D3B", "SYN-P-D4"],
            "mapping_key_order": ["SYN:D3B", "SYN:D4"],
            "input_verdict_vocabulary": ["A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"],
            "mapping": _joint_mapping(),
        },
        "simple_baseline_resolution": {
            "input_claim_ids": [item["claim_id"] for item in point_identities],
            "point_identities": point_identities,
            "loss_function": {
                "name": "MEAN_ABSOLUTE_RELATIVE_POINT_LOSS",
                "component": {"operator": "ABSOLUTE_RELATIVE_ERROR", "denominator": "ABS_POINT_VALUE"},
                "aggregate": {"operator": "ARITHMETIC_MEAN", "weights": "EQUAL_COMPONENT_WEIGHT"},
                "rounding": "NONE_BEFORE_RESOLUTION",
            },
            "resolution_rule": {
                "zero_loss": {"state": "ZERO_BASELINE_POINT_LOSS", "operator": "EQUALS", "value": 0.0},
                "positive_loss": {"state": "BASELINE_POINT_LOSS", "operator": "GREATER_THAN", "value": 0.0},
                "non_diagnostic": {
                    "state": "NOT_DIAGNOSTIC",
                    "input_statuses": ["UNKNOWN", "MEASUREMENT_MISMATCH", "NOT_DIAGNOSTIC"],
                    "require_all_inputs_observed": True,
                },
            },
        },
        "diagnostic_only_claims": [
            {"claim_id": claim_id, "reason": "Synthetic diagnostic-only clock."}
            for claim_id in claim_ids if claim_id not in {"SYN:D3B", "SYN:D4"}
        ],
        "status_preservation": {
            "allowed": ["OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH", "NOT_DIAGNOSTIC"],
        },
        "outcome_firewall_attestation": {
            "post_cutoff_metadata_access": "NONE",
            "post_cutoff_body_access": "NONE",
        },
    }


def _resolution_review(resolution: dict) -> dict:
    return {
        "schema_version": "judgment-selection-resolution-amendment-review.v1",
        "review_id": "SYN-AMENDMENT-REVIEW-V1",
        "case_id": CASE_ID,
        "freeze_id": FREEZE_ID,
        "amendment_id": resolution["amendment_id"],
        "author_id": resolution["author_id"],
        "selector_id": resolution["selector_id"],
        "reviewer_id": "synthetic-independent-resolution-reviewer",
        "reviewed_at": "2026-08-21T03:00:00+08:00",
        "recorded_at": "2026-08-21T04:00:00+08:00",
        "status": "INDEPENDENTLY_ACCEPTED_PRE_OUTCOME",
        "reviewed_amendment": deepcopy(resolution),
    }


def _seed_training(
    conn: sqlite3.Connection, tmp_path: Path, *, state: str,
    claim_stages: tuple = CLAIM_STAGES,
) -> dict[str, Path | dict]:
    conn.executescript(
        """
        CREATE TABLE judgment_training_programs (
          program_id TEXT PRIMARY KEY, program_state TEXT NOT NULL, method_version TEXT NOT NULL,
          method_scope TEXT NOT NULL, required_selection_admission_version TEXT,
          registered_at TEXT NOT NULL, method_frozen_at TEXT,
          method_freeze_recorded_at TEXT, sampling_policy_json TEXT NOT NULL, contract_ref TEXT NOT NULL
        );
        CREATE TABLE judgment_training_episodes (
          training_episode_id TEXT PRIMARY KEY, program_id TEXT NOT NULL, case_id TEXT NOT NULL UNIQUE,
          company_id TEXT NOT NULL, company_cluster_id TEXT NOT NULL, industry_id TEXT NOT NULL,
          decision_domain TEXT NOT NULL, cutoff_at TEXT NOT NULL, outcome_not_before TEXT NOT NULL,
          lane TEXT NOT NULL, provenance_role TEXT NOT NULL, outcome_access TEXT NOT NULL,
          holdout_axis TEXT, artifacts_json TEXT NOT NULL
        );
        CREATE TABLE judgment_training_artifact_events (
          artifact_event_id INTEGER PRIMARY KEY AUTOINCREMENT, training_episode_id TEXT NOT NULL,
          artifact_kind TEXT NOT NULL, artifact_ref TEXT NOT NULL, recorded_at TEXT NOT NULL,
          content_json TEXT, content_text TEXT, UNIQUE(training_episode_id, artifact_kind)
        );
        """
    )
    candidate = _candidate(claim_stages)
    candidate_review = _candidate_review(candidate)
    resolution = _resolution(claim_stages)
    paths = {
        "program": _write_json(tmp_path / "program.json", {}),
        "case": _write_json(tmp_path / "case.json", candidate),
        "candidate_review": _write_json(tmp_path / "candidate_review.json", candidate_review),
        "source": _write_json(tmp_path / "source.json", _source_contract(claim_stages)),
        "measurement": _write_json(
            tmp_path / "measurement.json", _measurement_contract(claim_stages),
        ),
        "resolution": _write_json(tmp_path / "resolution.json", resolution),
        "resolution_review": _write_json(tmp_path / "resolution_review.json", _resolution_review(resolution)),
    }
    conn.execute(
        "INSERT INTO judgment_training_programs VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL, ?, ?)",
        ("SYN-PROGRAM", state, "synthetic-v1", "SELECTION_AND_BOUNDARY",
         "2026-08-20T20:00:00+08:00", "{}", str(paths["program"])),
    )
    conn.execute(
        """INSERT INTO judgment_training_episodes VALUES
           (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
        (
            "SYN-EPISODE", "SYN-PROGRAM", CASE_ID, "CN:SYNTHETIC", "COMPANY:SYNTHETIC",
            "INDUSTRY:SYNTHETIC", "OPERATING_OUTCOME", "2020-12-31T23:59:59+08:00",
            "2022-05-01T00:00:00+08:00", "HISTORICAL_TRAINING", "HISTORICAL_SELF_REPLAY",
            "PIT_OUTCOME_SEALED", "{}",
        ),
    )
    conn.executemany(
        """INSERT INTO judgment_training_artifact_events
           (training_episode_id, artifact_kind, artifact_ref, recorded_at, content_json, content_text)
           VALUES (?, ?, ?, ?, ?, NULL)""",
        [
            ("SYN-EPISODE", "case_ref", str(paths["case"]), "2026-08-21T01:00:00+08:00", json.dumps(candidate, sort_keys=True)),
            ("SYN-EPISODE", "selection_review_ref", str(paths["candidate_review"]), "2026-08-21T01:00:00+08:00", json.dumps(candidate_review, sort_keys=True)),
        ],
    )
    conn.commit()
    return {**paths, "candidate": candidate, "resolution_payload": resolution}


def _manifest(
    paths: dict[str, Path | dict], claim_stages: tuple = CLAIM_STAGES,
) -> dict:
    return {
        "schema_version": jfc.REGISTRATION_SCHEMA_VERSION,
        "episode_id": CASE_ID,
        "company_id": "CN:SYNTHETIC",
        "frozen_at": "2020-12-31T23:59:59+08:00",
        "episode_class": "JUDGMENT_SELECTION_EPISODE",
        "selection_status": "SELECTION_ADMITTED",
        "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
        "program_lane": "HISTORICAL_TRAINING",
        "outcome_access": "PIT_OUTCOME_SEALED",
        "training_program_ref": str(paths["program"]),
        "selection_resolution_ref": str(paths["resolution"]),
        "selection_resolution_review_ref": str(paths["resolution_review"]),
        "selection_outcome_custodian_id": "synthetic-independent-outcome-custodian",
        "feedback_items": [
            {
                "claim_id": claim_id,
                "stage_id": stage_id,
                "source_kind": "SYNTHETIC_OFFICIAL_DISCLOSURE",
                "source_ref": f"SYNTHETIC:{claim_id}",
                "eligible_at": "2023-05-01T00:00:00+08:00",
                "settlement_version_policy": "INITIAL_DISCLOSURE",
                "frozen_artifact_ref": str(paths["case"]),
                "source_contract_ref": str(paths["source"]),
                "measurement_contract_ref": str(paths["measurement"]),
            }
            for claim_id, stage_id, _ in claim_stages
        ],
    }


def _registered(
    tmp_path: Path, *, state: str = "ACTIVE", claim_stages: tuple = CLAIM_STAGES,
) -> tuple[sqlite3.Connection, dict[str, Path | dict]]:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state=state, claim_stages=claim_stages)
    jfc.register_manifest(
        conn, _manifest(paths, claim_stages), registered_at="2026-08-21T05:00:00+08:00",
    )
    return conn, paths


def test_v4_control_registration_rejects_frozen_source_panel_member_reordering(
    tmp_path: Path,
) -> None:
    """Registration, not just settlement, must bind the ordered peer panel."""
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state="ACTIVE")
    candidate = _v4_peer_panel_candidate()
    review = _v4_peer_panel_review(candidate)
    source, measurement = _v4_peer_contract_bundles(candidate)
    source["peer_relative_acquisition"]["members"][1], source["peer_relative_acquisition"]["members"][2] = (
        source["peer_relative_acquisition"]["members"][2], source["peer_relative_acquisition"]["members"][1],
    )
    for key, value in (("case", candidate), ("candidate_review", review), ("source", source), ("measurement", measurement)):
        _write_json(paths[key], value)  # type: ignore[arg-type]
    conn.execute(
        "UPDATE judgment_training_artifact_events SET content_json = ? WHERE artifact_kind = 'case_ref'",
        (json.dumps(candidate, sort_keys=True),),
    )
    conn.execute(
        "UPDATE judgment_training_artifact_events SET content_json = ? WHERE artifact_kind = 'selection_review_ref'",
        (json.dumps(review, sort_keys=True),),
    )
    conn.execute(
        "UPDATE judgment_training_programs SET required_selection_admission_version = ? WHERE program_id = 'SYN-PROGRAM'",
        (jsc.PEER_PANEL_ADMISSION_VERSION,),
    )
    conn.commit()

    with pytest.raises(jfc.ControlPlaneError) as raised:
        jfc.register_manifest(
            conn, _manifest(paths), registered_at="2026-08-21T05:00:00+08:00",
        )

    assert raised.value.code == "selection_peer_contract_binding_invalid"
    assert "peer_binding.source_contract_member_order_mismatch" in raised.value.detail


def _write_v4_control_artifacts(
    conn: sqlite3.Connection, paths: dict[str, Path | dict], *,
    candidate: dict, source: dict, measurement: dict,
) -> None:
    """Replace only synthetic test artifacts with one internally-bound V4 set."""
    review = _v4_peer_panel_review(candidate)
    # V4 D3 is a recomputed RMB operating-contribution scalar, so the legacy
    # percentage baseline is not a legal point forecast.  The unchanged D3A
    # point is still enough to exercise resolution registration.
    d3_rule = next(
        rule for rule in measurement["measurement_rules"]
        if rule["predicate_id"] == "SYN-P-D3B"
    )
    d3_rule.pop("baseline_prediction", None)
    resolution = _resolution()
    resolution["simple_baseline_resolution"]["input_claim_ids"] = ["SYN:D3A"]
    resolution["simple_baseline_resolution"]["point_identities"] = [
        item for item in resolution["simple_baseline_resolution"]["point_identities"]
        if item["claim_id"] == "SYN:D3A"
    ]
    resolution_review = _resolution_review(resolution)
    for key, value in (
        ("case", candidate),
        ("candidate_review", review),
        ("source", source),
        ("measurement", measurement),
        ("resolution", resolution),
        ("resolution_review", resolution_review),
    ):
        _write_json(paths[key], value)  # type: ignore[arg-type]
    conn.execute(
        "UPDATE judgment_training_artifact_events SET content_json = ? WHERE artifact_kind = 'case_ref'",
        (json.dumps(candidate, sort_keys=True),),
    )
    conn.execute(
        "UPDATE judgment_training_artifact_events SET content_json = ? WHERE artifact_kind = 'selection_review_ref'",
        (json.dumps(review, sort_keys=True),),
    )
    conn.execute(
        "UPDATE judgment_training_programs SET required_selection_admission_version = ? WHERE program_id = 'SYN-PROGRAM'",
        (jsc.PEER_PANEL_ADMISSION_VERSION,),
    )
    conn.commit()


def _registered_v4_transfer_target(
    conn: sqlite3.Connection, tmp_path: Path,
) -> tuple[dict, dict[str, Path | str]]:
    """Create a later program's sealed V4 target for transfer-gate tests."""
    candidate = json.loads(
        json.dumps(_v4_peer_panel_candidate()).replace("SYNTHETIC", "TARGET")
    )
    candidate["freeze_recorded_at"] = "2026-08-22T12:00:00+08:00"
    case_path = _write_json(tmp_path / "target_case.json", candidate)
    review = _v4_peer_panel_review(candidate)
    review["case_id"] = candidate["case_id"]
    review["reviewed_at"] = "2026-08-22T13:00:00+08:00"
    review["reviewed_artifacts"] = [str(case_path)]
    review_path = _write_json(tmp_path / "target_review.json", review)
    program_path = _write_json(tmp_path / "target_program.json", {"fixture": True})
    target_program_id = "SYN-TARGET-PROGRAM"
    target_episode_id = candidate["experiment_id"]
    conn.execute(
        """INSERT INTO judgment_training_programs
               (program_id, program_state, method_version, method_scope,
                required_selection_admission_version, registered_at,
                method_frozen_at, method_freeze_recorded_at,
                sampling_policy_json, contract_ref)
               VALUES (?, 'ACTIVE', 'synthetic-v4', 'SELECTION_AND_BOUNDARY', ?,
                       ?, NULL, NULL, '{}', ?)""",
        (
            target_program_id, jsc.PEER_PANEL_ADMISSION_VERSION,
            "2026-08-22T12:30:00+08:00", str(program_path),
        ),
    )
    conn.execute(
        """INSERT INTO judgment_training_episodes VALUES
               (?, ?, ?, ?, ?, ?, ?, ?, ?, 'HISTORICAL_TRAINING',
                'HISTORICAL_SELF_REPLAY', 'PIT_OUTCOME_SEALED', NULL, '{}')""",
        (
            target_episode_id, target_program_id, candidate["case_id"],
            candidate["company_id"], candidate["company_cluster_id"],
            candidate["industry_id"], "OPERATING_OUTCOME", candidate["cutoff_at"],
            "2022-05-01T00:00:00+08:00",
        ),
    )
    conn.executemany(
        """INSERT INTO judgment_training_artifact_events
               (training_episode_id, artifact_kind, artifact_ref, recorded_at, content_json, content_text)
               VALUES (?, ?, ?, ?, ?, NULL)""",
        [
            (target_episode_id, "case_ref", str(case_path), candidate["freeze_recorded_at"], json.dumps(candidate, sort_keys=True)),
            (target_episode_id, "selection_review_ref", str(review_path), "2026-08-22T13:30:00+08:00", json.dumps(review, sort_keys=True)),
        ],
    )
    conn.commit()
    return candidate, {
        "program_id": target_program_id,
        "candidate": case_path,
        "review": review_path,
    }


def test_v4_transfer_requires_a_later_registered_sealed_candidate(
    tmp_path: Path,
) -> None:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state="ACTIVE")
    source_candidate = _v4_peer_panel_candidate()
    source, measurement = _v4_peer_contract_bundles(source_candidate)
    _write_v4_control_artifacts(
        conn, paths, candidate=source_candidate, source=source, measurement=measurement,
    )
    target_candidate, target = _registered_v4_transfer_target(conn, tmp_path)
    source_claim = {
        "episode_id": CASE_ID,
        "company_id": "CN:SYNTHETIC",
        "training_program_ref": str(paths["program"]),
    }
    payload = {
        "target_program_id": target["program_id"],
        "target_training_episode_id": target_candidate["experiment_id"],
        "target_case_id": target_candidate["case_id"],
        "target_episode_id": target_candidate["experiment_id"],
        "target_company_id": target_candidate["company_id"],
        "target_company_cluster_id": target_candidate["company_cluster_id"],
        "target_candidate_ref": str(target["candidate"]),
        "target_selection_review_ref": str(target["review"]),
        "target_selection_admission_version": jsc.PEER_PANEL_ADMISSION_VERSION,
        "target_frozen_artifact_ref": str(target["candidate"]),
        "target_freeze_id": target_candidate["freeze_id"],
        "target_frozen_at": target_candidate["freeze_recorded_at"],
    }

    jfc._validate_registered_v4_transfer_target(
        conn, source_claim, payload,
        source_note_effective_at=datetime.fromisoformat("2026-08-22T11:00:00+08:00"),
        effective_at=datetime.fromisoformat("2026-08-22T15:00:00+08:00"),
    )

    payload["target_candidate_ref"] = str(tmp_path / "unregistered_target.json")
    with pytest.raises(jfc.ControlPlaneError) as raised:
        jfc._validate_registered_v4_transfer_target(
            conn, source_claim, payload,
            source_note_effective_at=datetime.fromisoformat("2026-08-22T11:00:00+08:00"),
            effective_at=datetime.fromisoformat("2026-08-22T15:00:00+08:00"),
        )
    assert raised.value.code == "learning_target_candidate_ref_mismatch"


def test_v4_control_registration_accepts_the_complete_synthetic_peer_contract(
    tmp_path: Path,
) -> None:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state="ACTIVE")
    candidate = _v4_peer_panel_candidate()
    source, measurement = _v4_peer_contract_bundles(candidate)
    _write_v4_control_artifacts(
        conn, paths, candidate=candidate, source=source, measurement=measurement,
    )

    receipt = jfc.register_manifest(
        conn, _manifest(paths), registered_at="2026-08-21T05:00:00+08:00",
    )

    assert len(receipt["registered"]) == len(CLAIM_STAGES)
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == len(CLAIM_STAGES)


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (
            lambda source, measurement: source["peer_relative_acquisition"].__setitem__(
                "outcome_period_end", "2020-09-29",
            ),
            "peer_binding.source_contract_outcome_period_before_action",
        ),
        (
            lambda source, measurement: source["peer_relative_acquisition"]["members"][0]["outcome"]["fields"].pop(
                "operating_revenue_rmb",
            ),
            "peer_binding.source_contract_outcome_raw_field_set_invalid:CN:SYNTHETIC",
        ),
        (
            lambda source, measurement: measurement["peer_relative_measurement"]["members"][1]["outcome"]["fields"].pop(
                "operating_cost_rmb",
            ),
            "peer_binding.measurement_contract_outcome_raw_field_set_invalid:CN:SYNTHETIC-PEER-1",
        ),
        (
            lambda source, measurement: measurement["peer_relative_measurement"].__setitem__(
                "outcome_period_end", "2021-12-31",
            ),
            "peer_binding.source_measurement_outcome_period_mismatch",
        ),
        (
            lambda source, measurement: next(
                rule for rule in measurement["measurement_rules"]
                if rule["predicate_id"] == "SYN-P-D3B"
            )["primary_test"].__setitem__("value", 999_999.0),
            "peer_binding.measurement_contract_absolute_rule_not_candidate_anchor:D3_UNIT_ECONOMICS",
        ),
        (
            lambda source, measurement: next(
                rule for rule in measurement["measurement_rules"]
                if rule["predicate_id"] == "SYN-P-D4"
            )["peer_relative_test"]["primary_test"].__setitem__("value", 99.0),
            "peer_binding.measurement_contract_peer_relative_test_invalid:D4_WORKING_CAPITAL_AND_CASH",
        ),
        (
            lambda source, measurement: source["peer_relative_acquisition"]["members"][0]["reference"].__setitem__(
                "reference_revenue", 999.0,
            ),
            "peer_binding.source_contract_reference_identity_mismatch:CN:SYNTHETIC",
        ),
        (
            lambda source, measurement: next(
                rule for rule in measurement["measurement_rules"]
                if rule["predicate_id"] == "SYN-P-D4"
            ).__setitem__(
                "formula_id",
                next(
                    rule["formula_id"] for rule in measurement["measurement_rules"]
                    if rule["predicate_id"] == "SYN-P-D3B"
                ),
            ),
            "peer_binding.measurement_contract_absolute_rule_not_candidate_anchor:D4_WORKING_CAPITAL_AND_CASH",
        ),
        (
            lambda source, measurement: source["peer_relative_acquisition"]["members"][1].__setitem__(
                "issuer_id", "ISSUER:REPLACED",
            ),
            "peer_binding.source_contract_member_identity_mismatch:CN:SYNTHETIC-PEER-1",
        ),
        (
            lambda source, measurement: source["peer_relative_acquisition"]["members"][1].__setitem__(
                "control_group_id", source["peer_relative_acquisition"]["members"][0]["control_group_id"],
            ),
            "peer_binding.source_contract_member_identity_mismatch:CN:SYNTHETIC-PEER-1",
        ),
        (
            lambda source, measurement: source["peer_relative_acquisition"]["members"][1].__setitem__(
                "control_group_evidence", [],
            ),
            "peer_binding.source_contract_control_group_evidence_mismatch:CN:SYNTHETIC-PEER-1",
        ),
    ],
)
def test_v4_control_registration_rejects_threshold_reference_formula_issuer_or_control_drift(
    tmp_path: Path, mutation, finding: str,
) -> None:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state="ACTIVE")
    candidate = _v4_peer_panel_candidate()
    source, measurement = _v4_peer_contract_bundles(candidate)
    mutation(source, measurement)
    _write_v4_control_artifacts(
        conn, paths, candidate=candidate, source=source, measurement=measurement,
    )

    with pytest.raises(jfc.ControlPlaneError) as raised:
        jfc.register_manifest(
            conn, _manifest(paths), registered_at="2026-08-21T05:00:00+08:00",
        )

    assert raised.value.code == "selection_peer_contract_binding_invalid"
    assert finding in raised.value.detail


def _activation(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT payload_json FROM judgment_feedback_events WHERE event_type = 'OUTCOME_RELEASE_AUTHORIZED'"
    ).fetchone()
    return json.loads(row["payload_json"])["activation_snapshot"]


def _outcome(activation: dict, claim_stages: tuple = CLAIM_STAGES) -> dict:
    measurement = _measurement_contract(claim_stages)
    rules = {item["predicate_id"]: item for item in measurement["measurement_rules"]}
    values = {
        "D3_PRODUCT_VOLUME": (110.0, "tonnes"),
        "D3_UNIT_ECONOMICS": (12.0, "percent"),
        "D4_WORKING_CAPITAL_AND_CASH": (10.0, "RMB"),
    }
    claims = []
    for claim_id, stage_id, predicate_id in claim_stages:
        rule = rules[predicate_id]
        claim = {
            "claim_id": claim_id,
            "predicate_id": predicate_id,
            "stage_id": stage_id,
            "status": "OBSERVED",
            "source_ids": [f"SYNTHETIC:OFFICIAL:{claim_id}"],
            "measurement_scope": rule["required_observation"],
            "prohibited_substitutes": deepcopy(rule["prohibited_substitutes"]),
            "observed_measurement": rule["required_observation"],
            "observation_summary": "Synthetic observation.",
        }
        if stage_id in values:
            claim["observed_value"], claim["observed_unit"] = values[stage_id]
        claims.append(claim)
    return {
        "schema_version": "judgment-selection-outcome.v1",
        "case_id": CASE_ID,
        "freeze_id": FREEZE_ID,
        "settlement_id": "SYN-SETTLEMENT-V1",
        "settlement_as_of": "2026-08-26T23:59:59+08:00",
        "first_outcome_accessed_at": "2026-08-21T06:00:00+08:00",
        "activation_id": activation["activation_id"],
        "amendment_review_id": activation["amendment_review_id"],
        "custodian_id": activation["custodian_id"],
        "selection_status": "SELECTION_ADMITTED",
        "measurement_contract_identity": {
            "schema_version": measurement["schema_version"],
            "case_id": CASE_ID,
            "freeze_id": FREEZE_ID,
        },
        "registered_claim_ids": [claim_id for claim_id, _, _ in claim_stages],
        "claims": claims,
        "prohibited_outputs": [
            "selection_accuracy", "probability", "win_rate", "investment_return",
            "security_return", "portfolio_conclusion",
        ],
    }


def _outcome_event_count(conn: sqlite3.Connection) -> int:
    placeholders = ",".join("?" for _ in (jfc.OUTCOME_PIPELINE_EVENTS | jfc.OUTCOME_EVENTS))
    return conn.execute(
        f"SELECT COUNT(*) FROM judgment_feedback_events WHERE event_type IN ({placeholders})",
        tuple(jfc.OUTCOME_PIPELINE_EVENTS | jfc.OUTCOME_EVENTS),
    ).fetchone()[0]


def test_draft_program_cannot_register_selection_claims(tmp_path: Path) -> None:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state="DRAFT")

    with pytest.raises(jfc.ControlPlaneError, match="DRAFT training programs"):
        jfc.register_manifest(conn, _manifest(paths), registered_at="2026-08-21T05:00:00+08:00")

    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 0


def test_selection_registration_requires_review_and_all_six_claims(tmp_path: Path) -> None:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state="ACTIVE")
    conn.execute(
        "DELETE FROM judgment_training_artifact_events WHERE artifact_kind = 'selection_review_ref'"
    )
    conn.commit()
    manifest = _manifest(paths)

    with pytest.raises(jfc.ControlPlaneError) as missing_review:
        jfc.register_manifest(conn, manifest, registered_at="2026-08-21T05:00:00+08:00")
    assert missing_review.value.code == "selection_review_required"
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 0

    review = _candidate_review(paths["candidate"])
    conn.execute(
        """INSERT INTO judgment_training_artifact_events
           (training_episode_id, artifact_kind, artifact_ref, recorded_at, content_json, content_text)
           VALUES (?, 'selection_review_ref', ?, ?, ?, NULL)""",
        (
            "SYN-EPISODE", str(paths["candidate_review"]), "2026-08-21T01:00:00+08:00",
            json.dumps(review, sort_keys=True),
        ),
    )
    conn.commit()
    manifest["feedback_items"].pop()
    with pytest.raises(jfc.ControlPlaneError) as incomplete:
        jfc.register_manifest(conn, manifest, registered_at="2026-08-21T05:00:00+08:00")
    assert incomplete.value.code == "selection_feedback_claim_bundle_invalid"
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 0


@pytest.mark.parametrize("mutation", ["swap", "drop_required_layer"])
def test_selection_registration_rejects_illegal_order_or_missing_required_layer(
    tmp_path: Path, mutation: str,
) -> None:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    paths = _seed_training(conn, tmp_path, state="ACTIVE")
    manifest = _manifest(paths)
    if mutation == "swap":
        manifest["feedback_items"][2], manifest["feedback_items"][3] = (
            manifest["feedback_items"][3], manifest["feedback_items"][2]
        )
    else:
        manifest["feedback_items"] = [
            item for item in manifest["feedback_items"]
            if item["stage_id"] != "D4_WORKING_CAPITAL_AND_CASH"
        ]

    with pytest.raises(jfc.ControlPlaneError) as invalid:
        jfc.register_manifest(
            conn, manifest, registered_at="2026-08-21T05:00:00+08:00",
        )

    assert invalid.value.code == "selection_feedback_claim_bundle_invalid"
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 0


def test_non_selection_claims_cannot_enter_selection_settlement(tmp_path: Path) -> None:
    conn = jfc.connect(tmp_path / "control.db")
    jfc.initialize(conn)
    frozen = _write_json(tmp_path / "generic_freeze.json", {})
    source = _write_json(tmp_path / "generic_source.json", {})
    measurement = _write_json(tmp_path / "generic_measurement.json", {})
    manifest = {
        "schema_version": jfc.REGISTRATION_SCHEMA_VERSION,
        "episode_id": "GENERIC:NO-PRIMARY",
        "company_id": "CN:GENERIC",
        "frozen_at": "2020-12-31T23:59:59+08:00",
        "episode_class": "MECHANISM_SIGNAL_PROBE",
        "selection_status": "NO_PRIMARY",
        "learning_eligibility": "MECHANISM_SETTLEMENT_ONLY",
        "feedback_items": [
            {
                "claim_id": f"GENERIC:{index}",
                "stage_id": stage_id,
                "source_kind": "SYNTHETIC",
                "source_ref": f"SYNTHETIC:{index}",
                "eligible_at": "2023-05-01T00:00:00+08:00",
                "settlement_version_policy": "INITIAL_DISCLOSURE",
                "frozen_artifact_ref": str(frozen),
                "source_contract_ref": str(source),
                "measurement_contract_ref": str(measurement),
            }
            for index, stage_id in enumerate(jfc.SELECTION_STAGE_IDS, start=1)
        ],
    }
    jfc.register_manifest(conn, manifest, registered_at="2026-08-21T05:00:00+08:00")

    with pytest.raises(jfc.ControlPlaneError) as blocked:
        jfc.run_selection_settlement(
            conn,
            case_id="GENERIC:NO-PRIMARY",
            outcome_ref=tmp_path / "never-read.json",
            event_root=tmp_path / "events",
        )

    assert blocked.value.code == "selection_settlement_identity_invalid"
    assert _outcome_event_count(conn) == 0


def test_selection_settlement_uses_db_snapshots_and_writes_all_six_chains(tmp_path: Path) -> None:
    conn, paths = _registered(tmp_path)
    activation = _activation(conn)
    outcome_path = _write_json(tmp_path / "custodian_outcome.json", _outcome(activation))
    for field in ("source", "measurement", "resolution", "resolution_review"):
        _write_json(paths[field], {"tampered_after_registration": True})

    result = jfc.run_selection_settlement(
        conn, case_id=CASE_ID, outcome_ref=outcome_path, event_root=tmp_path / "events",
    )

    assert result["status"] == "SETTLED"
    assert result["idempotent"] is False
    assert len(result["events"]) == 6
    assert _outcome_event_count(conn) == 30
    counts = dict(conn.execute(
        """SELECT event_type, COUNT(*) AS count FROM judgment_feedback_events
            WHERE event_type IN ('ACQUISITION_STARTED', 'OUTCOME_PACKAGE_READY', 'READ_ATTESTED',
                                 'OUTCOME_EXTRACTED', 'CLAIM_SETTLED', 'MEASUREMENT_MISMATCH')
            GROUP BY event_type"""
    ).fetchall())
    assert counts == {
        "ACQUISITION_STARTED": 6,
        "CLAIM_SETTLED": 6,
        "OUTCOME_EXTRACTED": 6,
        "OUTCOME_PACKAGE_READY": 6,
        "READ_ATTESTED": 6,
    }
    repeat = jfc.run_selection_settlement(
        conn, case_id=CASE_ID, outcome_ref=outcome_path, event_root=tmp_path / "events",
    )
    assert repeat["idempotent"] is True
    assert _outcome_event_count(conn) == 30


def test_selection_settlement_accepts_ordered_five_claim_bundle_and_one_point_baseline(
    tmp_path: Path,
) -> None:
    conn, _ = _registered(tmp_path, claim_stages=FIVE_CLAIM_STAGES)
    activation = _activation(conn)
    outcome_path = _write_json(
        tmp_path / "five_claim_custodian_outcome.json",
        _outcome(activation, FIVE_CLAIM_STAGES),
    )

    result = jfc.run_selection_settlement(
        conn, case_id=CASE_ID, outcome_ref=outcome_path, event_root=tmp_path / "events",
    )
    feedback = json.loads(Path(result["feedback_ref"]).read_text(encoding="utf-8"))

    assert result["status"] == "SETTLED"
    assert len(result["events"]) == 5
    assert _outcome_event_count(conn) == 25
    assert [card["stage_id"] for card in feedback["cards"]] == [
        stage_id for _, stage_id, _ in FIVE_CLAIM_STAGES
    ]
    assert [
        item["claim_id"]
        for item in feedback["simple_baseline_resolution"]["component_losses"]
    ] == ["SYN:D3B"]
    assert feedback["joint_comparison"]["central_discriminator_claim_ids"] == [
        "SYN:D3B", "SYN:D4",
    ]


def test_caller_verdict_is_rejected_without_any_outcome_event(tmp_path: Path) -> None:
    conn, _ = _registered(tmp_path)
    outcome = _outcome(_activation(conn))
    outcome["selection_verdict"] = "A_ONLY"
    outcome_path = _write_json(tmp_path / "custodian_outcome.json", outcome)

    with pytest.raises(jfc.ControlPlaneError, match="caller_supplied_verdict"):
        jfc.run_selection_settlement(
            conn, case_id=CASE_ID, outcome_ref=outcome_path, event_root=tmp_path / "events",
        )

    assert _outcome_event_count(conn) == 0


def test_inconsistent_registered_snapshot_blocks_before_outcome_events(tmp_path: Path) -> None:
    conn, _ = _registered(tmp_path)
    event = conn.execute(
        """SELECT event_id, payload_json FROM judgment_feedback_events
            WHERE event_type = 'CLAIM_REGISTERED' ORDER BY event_id LIMIT 1"""
    ).fetchone()
    payload = json.loads(event["payload_json"])
    payload["measurement_contract_snapshot"]["freeze_id"] = "JFREEZE:TAMPERED"
    conn.execute(
        "UPDATE judgment_feedback_events SET payload_json = ? WHERE event_id = ?",
        (json.dumps(payload, sort_keys=True), event["event_id"]),
    )
    conn.commit()
    outcome_path = _write_json(tmp_path / "custodian_outcome.json", _outcome(_activation(conn)))

    with pytest.raises(jfc.ControlPlaneError, match="do not retain one identical frozen selection packet"):
        jfc.run_selection_settlement(
            conn, case_id=CASE_ID, outcome_ref=outcome_path, event_root=tmp_path / "events",
        )

    assert _outcome_event_count(conn) == 0


def test_selection_event_batch_rolls_back_on_insert_failure(tmp_path: Path) -> None:
    conn, _ = _registered(tmp_path)
    outcome_path = _write_json(tmp_path / "custodian_outcome.json", _outcome(_activation(conn)))
    conn.execute(
        """CREATE TRIGGER synthetic_abort_selection_batch
           BEFORE INSERT ON judgment_feedback_events
           WHEN NEW.event_type = 'CLAIM_SETTLED' AND NEW.feedback_item_id LIKE '%SYN:D5%'
           BEGIN SELECT RAISE(ABORT, 'synthetic batch failure'); END"""
    )

    with pytest.raises(sqlite3.IntegrityError, match="synthetic batch failure"):
        jfc.run_selection_settlement(
            conn, case_id=CASE_ID, outcome_ref=outcome_path, event_root=tmp_path / "events",
        )

    assert _outcome_event_count(conn) == 0


def test_settle_selection_cli_has_no_verdict_or_activation_arguments() -> None:
    parser = jfc._parser()
    selection = next(action for action in parser._actions if action.dest == "command")
    subparser = selection.choices["settle-selection"]
    option_strings = {option for action in subparser._actions for option in action.option_strings}

    assert "--verdict" not in option_strings
    assert "--settlement-verdict" not in option_strings
    assert "--activation" not in option_strings
    assert {"--db", "--case-id", "--outcome", "--event-root"} <= option_strings
