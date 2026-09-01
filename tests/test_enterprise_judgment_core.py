from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import enterprise_judgment_core as core
from scripts import enterprise_judgment_quantitative_adapter as quant
from scripts import enterprise_underwriting_episode as underwriting
from scripts import judgment_generation_handoff as generation_handoff


def _source_package(*, cash_eligibility: str = "ELIGIBLE", future_source: bool = False) -> dict:
    cash_available_at = "2026-01-02T00:00:00+00:00" if future_source else "2025-11-15T00:00:00+00:00"
    sources = [
        {
            "source_ref": "SRC:PLAN",
            "source_type": "OFFICIAL_ANNOUNCEMENT",
            "locator": "synthetic plan §1",
            "available_at": "2025-01-10T00:00:00+00:00",
            "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": ["UNIT:GROUP", "UNIT:BUSINESS"],
        },
        {
            "source_ref": "SRC:IMPLEMENTATION",
            "source_type": "OFFICIAL_ANNOUNCEMENT",
            "locator": "synthetic implementation §2",
            "available_at": "2025-03-15T00:00:00+00:00",
            "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": ["UNIT:BUSINESS"],
        },
        {
            "source_ref": "SRC:OPERATING",
            "source_type": "OFFICIAL_FILING",
            "locator": "synthetic operating disclosure §3",
            "available_at": "2025-10-31T00:00:00+00:00",
            "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": ["UNIT:BUSINESS"],
        },
        {
            "source_ref": "SRC:CASH",
            "source_type": "OFFICIAL_FILING",
            "locator": "synthetic cash disclosure §4",
            "available_at": cash_available_at,
            "eligibility": cash_eligibility,
            "responsibility_boundary_ids": ["UNIT:GROUP", "UNIT:BUSINESS"],
            **(
                {"boundary_note": "The source cannot isolate owner cash for the responsibility unit."}
                if cash_eligibility == "EVIDENCE_INELIGIBLE"
                else {}
            ),
        },
    ]
    return {
        "source_package_id": "SP:SYNTHETIC:2025",
        "company_id": "COMPANY:SYNTHETIC",
        "cutoff_at": "2025-12-31T23:59:59+00:00",
        "method_version": "enterprise-core-method.v1",
        "sources": sources,
    }


def _model(*, owner_cash_direction: str = "IMPROVES", source_package: dict | None = None) -> dict:
    package = source_package or _source_package()
    return {
        "schema_version": core.ENTERPRISE_SYSTEM_MODEL_VERSION,
        "model_id": "ESM:SYNTHETIC",
        "company_id": "COMPANY:SYNTHETIC",
        "version": "1",
        "cutoff_at": package["cutoff_at"],
        "method_version": package["method_version"],
        "source_package_id": package["source_package_id"],
        "responsibility_units": [
            {
                "unit_id": "UNIT:GROUP",
                "unit_type": "COMPANY",
                "parent_unit_id": None,
                "accounting_perimeter": "consolidated group",
                "decision_scope": "board and group capital allocation",
                "economic_carrier": "ordinary-share consolidated economics",
                "measurement_surface": "group filing",
                "legal_entity_ids": ["LEGAL:PARENT"],
            },
            {
                "unit_id": "UNIT:BUSINESS",
                "unit_type": "BUSINESS_UNIT",
                "parent_unit_id": "UNIT:GROUP",
                "accounting_perimeter": "reported operating segment",
                "decision_scope": "business-unit management",
                "economic_carrier": "customer cohort and installed capacity",
                "measurement_surface": "segment operating and cash bridge",
                "legal_entity_ids": ["LEGAL:SUBSIDIARY"],
            },
        ],
        "arenas": [
            {
                "arena_id": "ARENA:CORE",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "product_or_service_scope": "synthetic core service",
                "customer_task": "reduce customer processing time",
                "competition_mechanism": "retention and unit-cost competition",
                "window": "FY2025",
                "competitor_or_alternative_refs": ["ALT:INTERNAL_PROCESS"],
                "evidence_refs": ["SRC:OPERATING"],
            }
        ],
        "operating_variables": [
            {
                "variable_id": "VAR:CUSTOMER_RETENTION",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "name": "customer retention",
                "observation_state": "OBSERVED",
                "evidence_refs": ["SRC:OPERATING"],
            },
            {
                "variable_id": "VAR:UNIT_ECONOMICS",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "name": "unit economics",
                "observation_state": "OBSERVED",
                "evidence_refs": ["SRC:OPERATING"],
            },
            {
                "variable_id": "VAR:OWNER_CASH",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "name": "owner-cash conversion",
                "observation_state": "OBSERVED",
                "evidence_refs": ["SRC:CASH"],
            },
            {
                "variable_id": "VAR:LOSS_RISK",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "name": "permanent-loss exposure",
                "observation_state": "INFERRED",
                "evidence_refs": ["SRC:CASH"],
            },
        ],
        "mechanisms": [
            {
                "mechanism_id": "MECH:CUSTOMER_TO_EARNINGS",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "description": "implemented service reset changes retention and unit economics",
                "reasoning_kind": "INFERENCE",
                "from_variable_ids": ["VAR:CUSTOMER_RETENTION"],
                "to_variable_ids": ["VAR:UNIT_ECONOMICS"],
                "management_decision_ids": ["DEC:RESET"],
                "evidence_refs": ["SRC:OPERATING"],
            },
            {
                "mechanism_id": "MECH:EARNINGS_TO_CASH",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "description": "unit economics and capital burden transmit separately to owner cash",
                "reasoning_kind": "INFERENCE",
                "from_variable_ids": ["VAR:UNIT_ECONOMICS"],
                "to_variable_ids": ["VAR:OWNER_CASH"],
                "management_decision_ids": ["DEC:RESET"],
                "evidence_refs": ["SRC:CASH"],
            },
            {
                "mechanism_id": "MECH:CASH_TO_LOSS",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "description": "cash burden changes refinancing and permanent-loss exposure",
                "reasoning_kind": "INFERENCE",
                "from_variable_ids": ["VAR:OWNER_CASH"],
                "to_variable_ids": ["VAR:LOSS_RISK"],
                "management_decision_ids": ["DEC:RESET"],
                "evidence_refs": ["SRC:CASH"],
            },
        ],
        "financial_transmissions": [
            {
                "transmission_id": "TX:NORMAL_EARNINGS",
                "mechanism_id": "MECH:CUSTOMER_TO_EARNINGS",
                "layer": "NORMAL_EARNINGS",
                "direction": "IMPROVES",
                "description": "retention supports normalized operating earnings",
                "evidence_refs": ["SRC:OPERATING"],
            },
            {
                "transmission_id": "TX:OWNER_CASH",
                "mechanism_id": "MECH:EARNINGS_TO_CASH",
                "layer": "OWNER_CASH",
                "direction": owner_cash_direction,
                "description": "working capital and capital burden determine owner-cash conversion",
                "evidence_refs": ["SRC:CASH"],
            },
            {
                "transmission_id": "TX:PERMANENT_LOSS",
                "mechanism_id": "MECH:CASH_TO_LOSS",
                "layer": "PERMANENT_LOSS",
                "direction": "IMPROVES" if owner_cash_direction == "IMPROVES" else "DETERIORATES",
                "description": "cash resilience changes permanent-loss exposure",
                "evidence_refs": ["SRC:CASH"],
            },
        ],
        "operating_states": [
            {
                "state_id": "STATE:PRE",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "observed_at": "2025-03-31T00:00:00+00:00",
                "variable_states": {"VAR:CUSTOMER_RETENTION": "BASELINE", "VAR:OWNER_CASH": "BASELINE"},
                "evidence_refs": ["SRC:IMPLEMENTATION"],
            },
            {
                "state_id": "STATE:POST",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "observed_at": "2025-11-30T00:00:00+00:00",
                "variable_states": {"VAR:CUSTOMER_RETENTION": "IMPROVED", "VAR:OWNER_CASH": owner_cash_direction},
                "evidence_refs": ["SRC:OPERATING", "SRC:CASH"],
            },
        ],
        "state_changes": [
            {
                "change_id": "CHANGE:RESET",
                "from_state_id": "STATE:PRE",
                "to_state_id": "STATE:POST",
                "mechanism_ids": ["MECH:CUSTOMER_TO_EARNINGS", "MECH:EARNINGS_TO_CASH"],
                "management_decision_ids": ["DEC:RESET"],
                "evidence_refs": ["SRC:OPERATING", "SRC:CASH"],
            }
        ],
    }


def _ledger() -> dict:
    return {
        "schema_version": core.MANAGEMENT_DECISION_LEDGER_VERSION,
        "ledger_id": "MDL:SYNTHETIC",
        "company_id": "COMPANY:SYNTHETIC",
        "created_at": "2025-01-05T00:00:00+00:00",
        "append_policy": "EVENT_SUFFIX_ONLY",
        "events": [
            {
                "event_id": "MDE:1",
                "sequence": 1,
                "decision_id": "DEC:RESET",
                "event_type": "DECISION_RECORDED",
                "recorded_at": "2025-01-05T00:00:00+00:00",
                "effective_at": "2025-01-05T00:00:00+00:00",
                "status": "PLANNED",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "arena_id": "ARENA:CORE",
                "responsible_party": "business-unit chief executive",
                "problem_statement": "customer retention is weakening",
                "expected_mechanism_ids": ["MECH:CUSTOMER_TO_EARNINGS", "MECH:EARNINGS_TO_CASH"],
                "strongest_counterargument": "common demand recovery could explain later improvement",
                "observable_signal_ids": ["SIGNAL:RETENTION", "SIGNAL:CASH_CONVERSION", "SIGNAL:CAPITAL_BURDEN"],
                "financial_transmission_ids": ["TX:NORMAL_EARNINGS", "TX:OWNER_CASH", "TX:PERMANENT_LOSS"],
                "unknowns": ["cash timing", "customer counterfactual"],
                "evidence_refs": [],
            },
            {
                "event_id": "MDE:2",
                "sequence": 2,
                "decision_id": "DEC:RESET",
                "event_type": "STATUS_CHANGED",
                "recorded_at": "2025-02-01T00:00:00+00:00",
                "effective_at": "2025-02-01T00:00:00+00:00",
                "from_status": "PLANNED",
                "to_status": "COMMITTED",
                "rationale": "resources were formally committed",
                "evidence_refs": ["SRC:PLAN"],
            },
            {
                "event_id": "MDE:3",
                "sequence": 3,
                "decision_id": "DEC:RESET",
                "event_type": "STATUS_CHANGED",
                "recorded_at": "2025-03-20T00:00:00+00:00",
                "effective_at": "2025-03-15T00:00:00+00:00",
                "from_status": "COMMITTED",
                "to_status": "IMPLEMENTED",
                "rationale": "the operating reset entered service",
                "evidence_refs": ["SRC:IMPLEMENTATION"],
            },
        ],
    }


def _judgment_input(*, resolution: str = "PRIMARY", central: bool = True, cash_evidence_state: str = "SUPPORTED") -> dict:
    return {
        "candidate_id": "CAND:SYNTHETIC:2025",
        "judgment_owner_id": "JUDGMENT_OWNER:ONE",
        "compiled_at": "2026-01-02T00:00:00+00:00",
        "resolution": resolution,
        "central_path": (
            {
                "claim": "The implemented reset improves the operating engine and its cash transmission.",
                "trace_ids": ["TRACE:OPERATING", "TRACE:CASH", "TRACE:LOSS"],
            }
            if central else {}
        ),
        "forward_judgments": [
            {
                "judgment_id": "FJ:RETENTION",
                "claim": "Retention will remain above the pre-reset state.",
                "horizon": "12M",
                "observable_condition": "same-boundary official retention disclosure",
                "evidence_state": "SUPPORTED",
                "direction": "IMPROVES",
                "status": "OPEN",
                "trace_ids": ["TRACE:OPERATING"],
            },
            {
                "judgment_id": "FJ:CASH",
                "claim": "Operating improvement will reach owner cash after capital burden.",
                "horizon": "24M",
                "observable_condition": "same-boundary owner-cash bridge",
                "evidence_state": cash_evidence_state,
                "direction": "UNKNOWN" if cash_evidence_state == "EVIDENCE_INELIGIBLE" else "IMPROVES",
                "status": "UNKNOWN" if cash_evidence_state == "EVIDENCE_INELIGIBLE" else "OPEN",
                "trace_ids": ["TRACE:CASH"],
            },
            {
                "judgment_id": "FJ:LOSS",
                "claim": "Permanent-loss exposure remains unresolved until refinancing risk is observed.",
                "horizon": "36M",
                "observable_condition": "maturity and accessible-cash bridge",
                "evidence_state": (
                    "EVIDENCE_INELIGIBLE"
                    if cash_evidence_state == "EVIDENCE_INELIGIBLE"
                    else "MODEL_UNCERTAIN"
                ),
                "direction": "UNKNOWN",
                "status": "UNKNOWN",
                "trace_ids": ["TRACE:LOSS"],
            },
        ],
        "key_driver_ids": ["VAR:CUSTOMER_RETENTION", "VAR:OWNER_CASH"],
        "strongest_counterargument": {
            "claim": "Common demand recovery rather than the reset may explain retention.",
            "trace_ids": ["TRACE:OPERATING"],
        },
        "unknowns": [
            {
                "unknown_id": "UNK:COUNTERFACTUAL",
                "description": "The common-demand counterfactual is not isolated.",
                "conservative_treatment": "Do not attribute the full improvement to management.",
                "closing_evidence": "same-arena untreated cohort",
            }
        ],
        "monitoring_contract": {
            "contract_id": "MON:SYNTHETIC",
            "signals": [
                {"signal_id": "SIGNAL:RETENTION", "source_class": "OFFICIAL_FILING", "frequency": "ANNUAL"},
                {"signal_id": "SIGNAL:CASH_CONVERSION", "source_class": "OFFICIAL_FILING", "frequency": "ANNUAL"},
            ],
        },
        "traceability": [
            {
                "trace_id": "TRACE:OPERATING",
                "source_ref": "SRC:OPERATING",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "mechanism_id": "MECH:CUSTOMER_TO_EARNINGS",
                "reasoning_kind": "INFERENCE",
                "financial_transmission_ids": ["TX:NORMAL_EARNINGS"],
            },
            {
                "trace_id": "TRACE:CASH",
                "source_ref": "SRC:CASH",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "mechanism_id": "MECH:EARNINGS_TO_CASH",
                "reasoning_kind": "INFERENCE",
                "financial_transmission_ids": ["TX:OWNER_CASH"],
            },
            {
                "trace_id": "TRACE:LOSS",
                "source_ref": "SRC:CASH",
                "responsibility_unit_id": "UNIT:BUSINESS",
                "mechanism_id": "MECH:CASH_TO_LOSS",
                "reasoning_kind": "INFERENCE",
                "financial_transmission_ids": ["TX:PERMANENT_LOSS"],
            },
        ],
    }


def _underwriting_episode() -> dict:
    judgment = _judgment_input()
    central_path = judgment["central_path"]["claim"]
    strongest_rival = judgment["strongest_counterargument"]["claim"]
    reversal_observations = [
        "Same-arena untreated cohorts recover equally.",
        "Owner cash does not follow the operating improvement.",
    ]
    source_ref = "SRC:OPERATING"
    return {
        "schema_version": underwriting.EPISODE_SCHEMA,
        "episode_id": "EUE:COMPANY:SYNTHETIC:2025:BLIND:V1",
        "company_id": "COMPANY:SYNTHETIC",
        "company_name": "Synthetic Company",
        "cutoff_at": "2025-12-31T23:59:59+00:00",
        "sample_identity": "BLIND_REPLAY",
        "decision_frame": "Underwrite survival, normalized economics and permanent loss before price.",
        "underwriting_route": "OPERATING_FRANCHISE_WITH_CASH_CROSS_CHECK",
        "situation_model": {
            "summary": "A selective demand regime tests whether the service reset changes retention rather than appearances.",
            "industry_future_thesis": {
                "horizon": "Three to five years",
                "most_likely_regime": "Customer demand remains selective and rewards measurable processing gains.",
                "profit_pool_transmission": "Retention and unit cost determine which providers retain the profit pool.",
                "company_exposure": "The company is directly exposed to selective customer demand through retention and processing economics.",
                "adaptation": "The company reset service delivery and exposed retention to the new process.",
                "normal_economics": "Retention must pass through unit economics and capital burden before normalized earnings and owner cash improve.",
                "permanent_loss": "Repeated capital burden without owner-cash conversion can turn an operating reset into permanent loss.",
                "valuation_treatment": "Do not pay for unobserved cash conversion or assume the reset caused all recovery.",
                "strongest_rival": strongest_rival,
                "reversal_observations": reversal_observations,
            },
        },
        "business_position": "The company competes through customer retention and processing unit economics.",
        "survival_case": "No immediate survival failure is observed, but cash transmission remains material.",
        "adaptation_case": "Management committed and implemented the service reset; exposure is observed but causality remains bounded.",
        "normalization_case": "Normalized economics improve only if retained customers support unit economics after capital burden.",
        "permanent_loss_map": "Failure to convert the reset into owner cash can turn recurring capital burden into permanent loss.",
        "value_route": {
            "primary_routes": ["EPV"],
            "excluded_routes": ["UNOBSERVED_GROWTH_CAPITALIZATION"],
            "route_reasoning": "Use normalized earnings and owner-cash evidence; exclude unsupported growth.",
            "valuation_model_roles": {
                "primary": ["EPV"],
                "corroborative": ["RETURN_DECOMPOSITION"],
                "stress": ["NAV"],
            },
        },
        "strongest_rival": strongest_rival,
        "reversal_observations": reversal_observations,
        "component_treatments": [
            {
                "component_id": "CORE_OPERATING_RESET",
                "treatment": "CONDITIONALLY_UNDERWRITE",
                "reason": "Retention evidence supports the operating path while the counterfactual remains open.",
                "investment_consequence": "Normalize the core conditionally and do not attribute all recovery to management.",
                "promotion_or_resolution_condition": "Observe a same-arena untreated cohort and owner-cash bridge.",
                "evidence_ids": ["UW:E1"],
            }
        ],
        "evidence_trace": [
            {
                "evidence_id": "UW:E1",
                "source_ref": source_ref,
                "locator": "_judgment_input synthetic fixture",
                "scope": "Synthetic current-company operating and cash mechanism",
                "used_for": "Bind the complete underwriting thesis to the formal CJO fixture",
            }
        ],
        "existing_object_refs": [
            {
                "kind": "CJO_TEST_FIXTURE",
                "ref": "tests/test_enterprise_judgment_core.py",
                "role": "Existing source package, enterprise model, ledger and judgment input",
            }
        ],
        "underwriting_thesis": {
            "thesis_id": "UWT:COMPANY:SYNTHETIC:2025:V1",
            "central_path": central_path,
            "normal_earnings_treatment": "Conditionally underwrite improved retention and unit economics.",
            "owner_cash_treatment": "Keep owner cash conditional until the same-boundary capital bridge closes.",
            "permanent_loss_treatment": "Treat recurring capital burden without cash conversion as the loss path.",
            "value_route_treatment": "Use EPV only on normalized economics and exclude unsupported growth.",
            "economic_directions": {
                "normal_earnings": "IMPROVES",
                "owner_cash": "IMPROVES",
                "permanent_loss": "DETERIORATES",
            },
            "strongest_rival": strongest_rival,
            "monitoring": "Monitor retention, unit economics, owner cash and the untreated cohort.",
        },
        "investment_treatment": "BLIND_REPLAY_PRICE_FREE: no value, price, BuyBand or action is authorized.",
    }


def _review(candidate: dict, *, reviewer_id: str = "INDEPENDENT_REVIEWER:TWO") -> dict:
    return {
        "schema_version": core.CJO_REVIEW_VERSION,
        "review_id": "REVIEW:CJO:SYNTHETIC",
        "candidate_id": candidate["candidate_id"],
        "company_id": candidate["company_id"],
        "cutoff_at": candidate["cutoff_at"],
        "method_version": candidate["method_version"],
        "reviewer_id": reviewer_id,
        "reviewed_at": "2026-01-03T00:00:00+00:00",
        "decision": "ACCEPTED",
        "material_findings": [],
        "accepted_criteria": [
            "TRACEABILITY", "UNKNOWN_PRESERVATION", "COUNTERARGUMENT",
            "FINANCIAL_TRANSMISSION", "PIT_CUTOFF", "AUTHORITY_BOUNDARY",
        ],
    }


def _frozen_cjo(*, owner_cash_direction: str = "IMPROVES") -> dict:
    package = _source_package()
    candidate = core.compile_cjo_candidate(
        model=_model(owner_cash_direction=owner_cash_direction, source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(resolution="MIXED" if owner_cash_direction != "IMPROVES" else "PRIMARY"),
    )
    return core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))


def _refresh_reviewed_reader_projection(frozen: dict) -> None:
    frozen["independent_review_receipt"]["reviewed_reader_projection"] = {
        "enterprise_system_ref": deepcopy(frozen["enterprise_system_ref"]),
        "management_decision_ledger_ref": deepcopy(
            frozen["management_decision_ledger_ref"]
        ),
    }


def _overlay_input(price: float) -> dict:
    return {
        "mode": "SYNTHETIC",
        "base_normalized_earnings": 100.0,
        "base_owner_cash": 80.0,
        "share_count": 10.0,
        "required_return": 0.10,
        "market_price": price,
        "price_as_of": "2026-01-05T00:00:00+00:00",
        "horizon_years": 5,
        "annual_distribution": 0.5,
        "driver_adjustments": [
            {"driver_id": "VAR:CUSTOMER_RETENTION", "normalized_earnings_delta": 10.0, "owner_cash_delta": 4.0},
            {"driver_id": "VAR:OWNER_CASH", "normalized_earnings_delta": 0.0, "owner_cash_delta": 6.0},
        ],
    }


def test_enterprise_model_compiles_to_independently_frozen_cjo() -> None:
    package = _source_package()
    model = _model(source_package=package)
    ledger = _ledger()
    assert core.validate_enterprise_system_model(model, source_package=package)["state"] == "VALID"
    assert core.validate_management_decision_ledger(ledger, source_package=package)["state"] == "VALID"

    candidate = core.compile_cjo_candidate(
        model=model, ledger=ledger, source_package=package, judgment_input=_judgment_input(),
    )
    assert candidate["state"] == "REVIEW_READY"
    assert candidate["authority"]["canonical"] is False
    frozen = core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))

    assert core.validate_frozen_cjo(frozen)["state"] == "VALID"
    assert frozen["state"] == "FROZEN"
    assert frozen["authority"]["canonical"] is True
    assert frozen["authority"]["investment_authorization"] is False


def test_complete_underwriting_episode_is_bound_through_candidate_freeze_and_synthesis() -> None:
    package = _source_package()
    episode = _underwriting_episode()
    expected = underwriting.project_price_free_underwriting_thesis(episode)
    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(),
        underwriting_episode=episode,
    )

    assert candidate["underwriting_thesis_projection"] == expected
    assert candidate["authority"]["report_read_allowed"] is False
    frozen = core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))
    assert core.validate_frozen_cjo(frozen)["state"] == "VALID"
    assert frozen["underwriting_thesis_projection"] == expected
    assert (
        frozen["independent_review_receipt"]["reviewed_reader_projection"]
        ["underwriting_thesis_projection"]
        == expected
    )
    synthesis = core.project_frozen_cjo_to_judgment_synthesis(frozen)
    assert synthesis["underwriting_thesis_projection"] == expected
    assert synthesis["frozen_cjo"]["underwriting_thesis_projection"] == expected


def test_episode_deterministically_owns_cjo_earnings_cash_and_loss_directions() -> None:
    package = _source_package()
    episode = _underwriting_episode()
    episode["underwriting_thesis"]["economic_directions"] = {
        "normal_earnings": "DETERIORATES",
        "owner_cash": "DETERIORATES",
        "permanent_loss": "DETERIORATES",
    }
    candidate = core.compile_cjo_candidate(
        model=_model(owner_cash_direction="IMPROVES", source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(),
        underwriting_episode=episode,
    )

    assert candidate["normal_earnings_transmission"]["direction"] == "DETERIORATES"
    assert candidate["owner_cash_transmission"]["direction"] == "DETERIORATES"
    assert {item["direction"] for item in candidate["permanent_loss_paths"]} == {
        "DETERIORATES"
    }
    assert {
        item["layer"]: item["direction"]
        for item in candidate["enterprise_system_ref"]["financial_transmissions"]
    } == {
        "NORMAL_EARNINGS": "DETERIORATES",
        "OWNER_CASH": "DETERIORATES",
        "PERMANENT_LOSS": "DETERIORATES",
    }
    frozen = core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))
    assert core.validate_frozen_cjo(frozen)["state"] == "VALID"

    top_level_tamper = deepcopy(frozen)
    top_level_tamper["owner_cash_transmission"]["direction"] = "IMPROVES"
    validation = core.validate_frozen_cjo(top_level_tamper)
    assert validation["state"] == "INVALID"
    assert any(
        "underwriting_thesis_projection_owner_cash_direction_mismatch" in item
        for item in validation["findings"]
    )

    nested_tamper = deepcopy(frozen)
    next(
        item
        for item in nested_tamper["enterprise_system_ref"]["financial_transmissions"]
        if item["transmission_id"] == "TX:OWNER_CASH"
    )["direction"] = "IMPROVES"
    nested_validation = core.validate_frozen_cjo(nested_tamper)
    assert nested_validation["state"] == "INVALID"
    assert any(
        "owner_cash_enterprise_transmission_direction_mismatch:TX:OWNER_CASH" in item
        for item in nested_validation["findings"]
    )


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ("company", "underwriting_thesis_projection_company_id_mismatch"),
        ("cutoff", "underwriting_thesis_projection_cutoff_mismatch"),
        ("central", "underwriting_thesis_projection_central_path_mismatch"),
        ("rival", "underwriting_thesis_projection_strongest_rival_mismatch"),
    ],
)
def test_underwriting_episode_must_match_formal_cjo_identity_and_narrative_claims(
    mutation: str, finding: str,
) -> None:
    package = _source_package()
    episode = _underwriting_episode()
    if mutation == "company":
        episode["company_id"] = "COMPANY:OTHER"
    elif mutation == "cutoff":
        episode["cutoff_at"] = "2025-12-30T23:59:59+00:00"
    elif mutation == "central":
        episode["underwriting_thesis"]["central_path"] = "A different company story."
    else:
        episode["strongest_rival"] = "A different strongest rival."
        episode["underwriting_thesis"]["strongest_rival"] = episode["strongest_rival"]
        episode["situation_model"]["industry_future_thesis"]["strongest_rival"] = episode["strongest_rival"]

    with pytest.raises(core.EnterpriseJudgmentCoreError, match=finding):
        core.compile_cjo_candidate(
            model=_model(source_package=package),
            ledger=_ledger(),
            source_package=package,
            judgment_input=_judgment_input(),
            underwriting_episode=episode,
        )


def test_reviewed_underwriting_projection_cannot_change_after_freeze() -> None:
    package = _source_package()
    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(),
        underwriting_episode=_underwriting_episode(),
    )
    frozen = core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))
    frozen["underwriting_thesis_projection"]["situation_model"][
        "industry_future_thesis"
    ]["most_likely_regime"] = "A post-review regime rewrite."

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert "frozen_cjo.reviewed_reader_projection_mutated" in validation["findings"]


def test_cjo_rejects_a_second_top_level_industry_story() -> None:
    package = _source_package()
    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(),
        underwriting_episode=_underwriting_episode(),
    )
    projection = candidate["underwriting_thesis_projection"]
    projection["industry_future_thesis"] = deepcopy(
        projection["situation_model"]["industry_future_thesis"]
    )
    projection["industry_future_thesis"]["most_likely_regime"] = (
        "A conflicting broad recovery story."
    )

    validation = core.validate_cjo_candidate(candidate)

    assert validation["state"] == "INVALID"
    assert (
        "cjo_candidate.underwriting_thesis_projection."
        "legacy_top_level_industry_future_thesis_not_allowed"
    ) in validation["findings"]


def test_underwriting_episode_cannot_put_price_inside_frozen_thesis() -> None:
    package = _source_package()
    episode = _underwriting_episode()
    episode["underwriting_thesis"]["price"] = 42.0

    with pytest.raises(
        core.EnterpriseJudgmentCoreError,
        match="underwriting_thesis.price_boundary",
    ):
        core.compile_cjo_candidate(
            model=_model(source_package=package),
            ledger=_ledger(),
            source_package=package,
            judgment_input=_judgment_input(),
            underwriting_episode=episode,
        )


def test_blind_underwriting_evidence_must_come_from_the_cjo_source_package() -> None:
    package = _source_package()
    episode = _underwriting_episode()
    episode["evidence_trace"][0]["source_ref"] = "SRC:OUTSIDE-PACKAGE"

    with pytest.raises(
        core.EnterpriseJudgmentCoreError,
        match="underwriting_episode_evidence_not_in_source_package",
    ):
        core.compile_cjo_candidate(
            model=_model(source_package=package),
            ledger=_ledger(),
            source_package=package,
            judgment_input=_judgment_input(),
            underwriting_episode=episode,
        )


def test_every_central_judgment_trace_has_source_boundary_mechanism_reasoning_and_financial_transmission() -> None:
    frozen = _frozen_cjo()
    trace_by_id = {item["trace_id"]: item for item in frozen["traceability"]}
    for trace_id in frozen["central_path"]["trace_ids"]:
        trace = trace_by_id[trace_id]
        assert trace["source_ref"]
        assert trace["responsibility_unit_id"] == "UNIT:BUSINESS"
        assert trace["mechanism_id"]
        assert trace["reasoning_kind"] in {"OBSERVATION", "INFERENCE"}
        assert trace["financial_transmission_ids"]


def test_append_only_ledger_preserves_history_and_distinguishes_plan_commitment_implementation_and_exposure() -> None:
    package = _source_package()
    ledger = _ledger()
    exposed = core.append_management_decision_event(
        ledger,
        {
            "event_id": "MDE:4",
            "sequence": 4,
            "decision_id": "DEC:RESET",
            "event_type": "STATUS_CHANGED",
            "recorded_at": "2025-11-20T00:00:00+00:00",
            "effective_at": "2025-11-15T00:00:00+00:00",
            "from_status": "IMPLEMENTED",
            "to_status": "EXPOSED",
            "rationale": "the implemented decision reached an observable operating window",
            "evidence_refs": ["SRC:CASH"],
        },
        source_package=package,
    )
    assert [item.get("status") or item.get("to_status") for item in exposed["events"]] == [
        "PLANNED", "COMMITTED", "IMPLEMENTED", "EXPOSED",
    ]
    assert ledger["events"] == exposed["events"][:3]
    mutated = deepcopy(exposed)
    mutated["events"][0]["problem_statement"] = "rewritten after outcome"
    result = core.validate_ledger_extension(ledger, mutated, source_package=package)
    assert result["state"] == "INVALID"
    assert "management_decision_ledger.history_mutated" in result["findings"]


def test_announced_plan_is_not_implemented_or_realized() -> None:
    package = _source_package()
    plan_only = _ledger()
    plan_only["events"] = plan_only["events"][:1]
    result = core.validate_management_decision_ledger(plan_only, source_package=package)
    assert result["decision_snapshots"]["DEC:RESET"]["status"] == "PLANNED"
    assert result["decision_snapshots"]["DEC:RESET"]["status"] not in {"IMPLEMENTED", "REALIZED"}
    plan_only["events"].append({
        "event_id": "MDE:2",
        "sequence": 2,
        "decision_id": "DEC:RESET",
        "event_type": "STATUS_CHANGED",
        "recorded_at": "2025-10-31T00:00:00+00:00",
        "effective_at": "2025-10-31T00:00:00+00:00",
        "from_status": "PLANNED",
        "to_status": "REALIZED",
        "rationale": "an announced plan was incorrectly treated as an outcome",
        "evidence_refs": ["SRC:OPERATING"],
    })
    invalid = core.validate_management_decision_ledger(plan_only, source_package=package)
    assert "management_decision_ledger.events[1].status_transition_invalid" in invalid["findings"]


def test_insufficient_evidence_preserves_no_primary_instead_of_manufacturing_path() -> None:
    package = _source_package(cash_eligibility="EVIDENCE_INELIGIBLE")
    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(cash_evidence_state="EVIDENCE_INELIGIBLE"),
    )
    assert candidate["resolution"] == "NO_PRIMARY"
    assert candidate["central_path"] == {}
    assert candidate["forward_judgments"][1]["status"] == "UNKNOWN"
    assert "DETERIORATES" not in json.dumps(candidate["forward_judgments"][1], ensure_ascii=False)


def test_ineligible_cash_trace_does_not_erase_an_operating_only_central_path() -> None:
    package = _source_package(cash_eligibility="EVIDENCE_INELIGIBLE")
    judgment = _judgment_input(cash_evidence_state="EVIDENCE_INELIGIBLE")
    judgment["central_path"] = {
        "claim": "Retention evidence supports the operating reset; cash realization remains separate.",
        "trace_ids": ["TRACE:OPERATING"],
    }
    judgment["forward_judgments"][2].update({
        "evidence_state": "EVIDENCE_INELIGIBLE", "direction": "UNKNOWN", "status": "UNKNOWN",
    })

    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package), ledger=_ledger(),
        source_package=package, judgment_input=judgment,
    )

    assert candidate["resolution"] == "PRIMARY"
    assert candidate["central_path"]["trace_ids"] == ["TRACE:OPERATING"]
    assert candidate["normal_earnings_transmission"]["direction"] == "IMPROVES"
    assert candidate["owner_cash_transmission"]["direction"] == "UNKNOWN"
    assert candidate["forward_judgments"][1]["evidence_state"] == "EVIDENCE_INELIGIBLE"


def test_supported_operating_path_stays_primary_when_cash_and_loss_axes_are_unknown() -> None:
    package = _source_package()
    model = _model(owner_cash_direction="UNKNOWN", source_package=package)
    next(
        item for item in model["financial_transmissions"]
        if item["transmission_id"] == "TX:PERMANENT_LOSS"
    )["direction"] = "UNKNOWN"
    judgment = _judgment_input()
    judgment["central_path"]["claim"] = (
        "The implemented reset improves retention and normalized unit economics; "
        "owner cash and permanent loss remain separate unresolved axes."
    )
    judgment["forward_judgments"][1].update({
        "evidence_state": "MODEL_UNCERTAIN", "direction": "UNKNOWN", "status": "UNKNOWN",
    })

    candidate = core.compile_cjo_candidate(
        model=model, ledger=_ledger(), source_package=package, judgment_input=judgment,
    )

    assert candidate["resolution"] == "PRIMARY"
    assert candidate["central_path"]["trace_ids"] == ["TRACE:OPERATING", "TRACE:CASH", "TRACE:LOSS"]
    assert candidate["normal_earnings_transmission"]["direction"] == "IMPROVES"
    assert candidate["owner_cash_transmission"]["direction"] == "UNKNOWN"
    assert candidate["permanent_loss_paths"][0]["direction"] == "UNKNOWN"
    assert candidate["forward_judgments"][1]["status"] == "UNKNOWN"
    assert candidate["forward_judgments"][2]["status"] == "UNKNOWN"


def test_no_primary_can_freeze_with_three_monitorable_judgments() -> None:
    package = _source_package()
    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(resolution="NO_PRIMARY", central=False),
    )
    frozen = core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))
    assert frozen["resolution"] == "NO_PRIMARY"
    assert frozen["central_path"] == {}
    assert len(frozen["forward_judgments"]) == 3


def test_operating_improvement_with_owner_cash_deterioration_preserves_separate_axes() -> None:
    package = _source_package()
    model = _model(owner_cash_direction="DETERIORATES", source_package=package)
    judgment = _judgment_input(resolution="PRIMARY")
    candidate = core.compile_cjo_candidate(
        model=model, ledger=_ledger(), source_package=package, judgment_input=judgment,
    )
    assert candidate["resolution"] == "PRIMARY"
    assert candidate["normal_earnings_transmission"]["direction"] == "IMPROVES"
    assert candidate["owner_cash_transmission"]["direction"] == "DETERIORATES"
    frozen = core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))
    assert frozen["resolution"] == "PRIMARY"
    assert frozen["owner_cash_transmission"]["direction"] == "DETERIORATES"


def test_different_prices_change_only_overlay_not_frozen_enterprise_judgment() -> None:
    frozen = _frozen_cjo()
    before = deepcopy(frozen)
    low = quant.compile_synthetic_quantitative_overlay(
        frozen_cjo=frozen, overlay_input=_overlay_input(30.0),
    )
    high = quant.compile_synthetic_quantitative_overlay(
        frozen_cjo=frozen, overlay_input=_overlay_input(90.0),
    )
    assert frozen == before
    assert low["cjo_ref"] == high["cjo_ref"]
    assert low["enterprise_case"] == high["enterprise_case"]
    assert low["price_overlay"]["expectation_gap"] != high["price_overlay"]["expectation_gap"]
    assert low["authority"]["investment_action_authorized"] is False


def test_forecast_and_training_can_only_create_candidate_amendment() -> None:
    frozen = _frozen_cjo()
    before = deepcopy(frozen)
    amendment = core.compile_candidate_amendment(
        frozen_cjo=frozen,
        amendment_id="AMEND:FORECAST:1",
        origin="FORECAST",
        proposed_at="2026-01-10T00:00:00+00:00",
        proposals=[{
            "target": "monitoring_contract.signals",
            "proposed_change": "add same-boundary churn disclosure",
            "rationale": "forecast settlement exposed a coverage gap",
        }],
    )
    assert amendment["status"] == "CANDIDATE_ONLY"
    assert amendment["authority"]["may_modify_frozen_cjo"] is False
    assert frozen == before


def test_self_review_cannot_freeze() -> None:
    package = _source_package()
    candidate = core.compile_cjo_candidate(
        model=_model(source_package=package), ledger=_ledger(), source_package=package,
        judgment_input=_judgment_input(),
    )
    with pytest.raises(core.EnterpriseJudgmentCoreError, match="author_cannot_self_sign"):
        core.freeze_cjo(
            candidate=candidate,
            independent_review=_review(candidate, reviewer_id=candidate["judgment_owner_id"]),
        )


def test_frozen_cjo_is_read_by_judgment_synthesis_and_report_handoff(tmp_path: Path) -> None:
    frozen = _frozen_cjo()
    cjo_path = tmp_path / "canonical" / "frozen_cjo.json"
    cjo_path.parent.mkdir()
    cjo_path.write_text(json.dumps(frozen, ensure_ascii=False), encoding="utf-8")
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "analysis_contract.json").write_text(json.dumps({
        "report_id": "COMPANY:SYNTHETIC",
        "company_id": "COMPANY:SYNTHETIC",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": "2025-12-31",
        "canonical_judgment_refs": {"frozen_cjo_ref": str(cjo_path)},
    }), encoding="utf-8")

    synthesis = generation_handoff.build_judgment_generation_handoff(
        report_dir, "JUDGMENT_SYNTHESIS", frozen_cjo_path=cjo_path,
    )
    validation = generation_handoff.validate_judgment_generation_handoff(
        synthesis, output_dir=report_dir,
    )
    report_handoff = core.build_report_handoff(frozen)

    assert validation["state"] == "READY"
    assert synthesis["projection"]["frozen_cjo"]["cjo_id"] == frozen["cjo_id"]
    assert any(item["role"] == "FROZEN_CJO" for item in synthesis["source_refs"])
    assert report_handoff["authority"]["report_use"] == "REPORT_USE_NOT_RELEASED"
    assert report_handoff["authority"]["publication_authorization"] is False


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    [
        ("arena", "customer_task", "post-outcome customer success rewritten after review"),
        ("state", "variable_states", {"VAR:CUSTOMER_RETENTION": "POST_OUTCOME_WIN"}),
        ("decision", "problem_statement", "post-outcome success rewritten as the original problem"),
    ],
)
def test_frozen_reader_projection_cannot_change_after_independent_review(
    section: str, field: str, replacement: object,
) -> None:
    frozen = _frozen_cjo()
    if section == "arena":
        target = frozen["enterprise_system_ref"]["arenas"][0]
    elif section == "state":
        target = frozen["enterprise_system_ref"]["operating_states"][0]
    else:
        target = frozen["management_decision_ledger_ref"]["decisions"][0]
    target[field] = replacement

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert "frozen_cjo.reviewed_reader_projection_mutated" in validation["findings"]


def test_old_v1_reader_projection_omissions_remain_valid() -> None:
    frozen = _frozen_cjo()
    frozen["independent_review_receipt"].pop("reviewed_reader_projection")
    for field in ("arenas", "operating_variables", "operating_states", "state_changes"):
        frozen["enterprise_system_ref"].pop(field)
    frozen["management_decision_ledger_ref"].pop("events")

    assert core.validate_frozen_cjo(frozen)["state"] == "VALID"


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    [
        ("arena", "customer_task", "post-outcome customer success"),
        ("state", "variable_states", {"VAR:CUSTOMER_RETENTION": "POST_OUTCOME_WIN"}),
        ("decision", "problem_statement", "post-outcome rewritten problem"),
    ],
)
def test_new_shape_cannot_drop_review_copy_to_hide_projection_mutation(
    section: str, field: str, replacement: object,
) -> None:
    frozen = _frozen_cjo()
    frozen["independent_review_receipt"].pop("reviewed_reader_projection")
    if section == "arena":
        target = frozen["enterprise_system_ref"]["arenas"][0]
    elif section == "state":
        target = frozen["enterprise_system_ref"]["operating_states"][0]
    else:
        target = frozen["management_decision_ledger_ref"]["decisions"][0]
    target[field] = replacement

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert (
        "frozen_cjo.reviewed_reader_projection_missing_for_new_shape"
        in validation["findings"]
    )


def test_new_projection_inference_mechanism_may_have_no_direct_evidence() -> None:
    frozen = _frozen_cjo()
    mechanism = frozen["enterprise_system_ref"]["mechanisms"][0]
    mechanism["reasoning_kind"] = "INFERENCE"
    mechanism["evidence_refs"] = []
    _refresh_reviewed_reader_projection(frozen)

    assert core.validate_frozen_cjo(frozen)["state"] == "VALID"


def test_new_projection_observation_mechanism_requires_direct_evidence() -> None:
    frozen = _frozen_cjo()
    mechanism = frozen["enterprise_system_ref"]["mechanisms"][0]
    mechanism["reasoning_kind"] = "OBSERVATION"
    mechanism["evidence_refs"] = []
    _refresh_reviewed_reader_projection(frozen)

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert any("evidence_refs_missing" in item for item in validation["findings"])


@pytest.mark.parametrize("direction", ["UNKNOWN", "NONE"])
def test_new_projection_unknown_or_none_transmission_may_have_no_direct_evidence(
    direction: str,
) -> None:
    frozen = _frozen_cjo()
    transmission = frozen["enterprise_system_ref"]["financial_transmissions"][1]
    transmission["direction"] = direction
    transmission["evidence_refs"] = []
    frozen["owner_cash_transmission"]["direction"] = direction
    _refresh_reviewed_reader_projection(frozen)

    assert core.validate_frozen_cjo(frozen)["state"] == "VALID"


def test_new_projection_directional_transmission_requires_direct_evidence() -> None:
    frozen = _frozen_cjo()
    transmission = frozen["enterprise_system_ref"]["financial_transmissions"][1]
    transmission["evidence_refs"] = []
    _refresh_reviewed_reader_projection(frozen)

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert any("evidence_refs_missing" in item for item in validation["findings"])


@pytest.mark.parametrize("projection", ["inference_mechanism", "unknown_transmission"])
def test_optional_projection_evidence_is_still_validated_when_present(
    projection: str,
) -> None:
    frozen = _frozen_cjo()
    if projection == "inference_mechanism":
        target = frozen["enterprise_system_ref"]["mechanisms"][0]
        target["reasoning_kind"] = "INFERENCE"
    else:
        target = frozen["enterprise_system_ref"]["financial_transmissions"][1]
        target["direction"] = "UNKNOWN"
        frozen["owner_cash_transmission"]["direction"] = "UNKNOWN"
    target["evidence_refs"] = ["SRC:UNKNOWN"]
    _refresh_reviewed_reader_projection(frozen)

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert any("evidence_refs[0]_unknown" in item for item in validation["findings"])


def test_event_projection_alone_still_requires_reviewed_projection() -> None:
    frozen = _frozen_cjo()
    frozen["independent_review_receipt"].pop("reviewed_reader_projection")
    for field in ("arenas", "operating_variables", "operating_states", "state_changes"):
        frozen["enterprise_system_ref"].pop(field)

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert (
        "frozen_cjo.reviewed_reader_projection_missing_for_new_shape"
        in validation["findings"]
    )


@pytest.mark.parametrize("mutation", ["arena_scope", "state_cutoff", "event_source"])
def test_frozen_reader_projection_is_directly_revalidated(mutation: str) -> None:
    frozen = _frozen_cjo()
    # Remove the direct reviewed copy to prove structural validation is not
    # merely reporting the review comparison.
    frozen["independent_review_receipt"].pop("reviewed_reader_projection")
    if mutation == "arena_scope":
        frozen["enterprise_system_ref"]["arenas"][0]["responsibility_unit_id"] = "UNIT:UNKNOWN"
    elif mutation == "state_cutoff":
        frozen["enterprise_system_ref"]["operating_states"][0]["observed_at"] = (
            "2026-01-01T00:00:00+00:00"
        )
    else:
        frozen["management_decision_ledger_ref"]["events"][1]["evidence_refs"] = ["SRC:UNKNOWN"]

    validation = core.validate_frozen_cjo(frozen)

    assert validation["state"] == "INVALID"
    assert any(
        token in item
        for item in validation["findings"]
        for token in (
            "responsibility_unit_unknown", "observed_at_after_cutoff_or_invalid",
            "unknown_source_ref", "snapshot_event_mismatch",
        )
    )


def test_post_cutoff_source_cannot_enter_historical_cjo() -> None:
    package = _source_package(future_source=True)
    source_validation = core.validate_source_package(package)
    assert source_validation["state"] == "INVALID"
    assert "source_package.sources[3].after_cutoff" in source_validation["findings"]
    with pytest.raises(core.EnterpriseJudgmentCoreError, match="after_cutoff"):
        core.compile_cjo_candidate(
            model=_model(source_package=package), ledger=_ledger(), source_package=package,
            judgment_input=_judgment_input(),
        )


def test_model_uncertain_cannot_be_written_as_deterministic_forward_judgment() -> None:
    package = _source_package()
    judgment = _judgment_input()
    judgment["forward_judgments"][2]["direction"] = "DETERIORATES"
    judgment["forward_judgments"][2]["status"] = "OPEN"
    with pytest.raises(core.EnterpriseJudgmentCoreError, match="uncertain_or_ineligible_must_remain_unknown"):
        core.compile_cjo_candidate(
            model=_model(source_package=package), ledger=_ledger(), source_package=package,
            judgment_input=judgment,
        )


def test_price_and_valuation_fields_are_rejected_from_enterprise_truth() -> None:
    package = _source_package()
    model = _model(source_package=package)
    model["operating_states"][0]["market_price"] = 42.0
    result = core.validate_enterprise_system_model(model, source_package=package)
    assert result["state"] == "INVALID"
    assert any("forbidden_price" in item for item in result["findings"])
