from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import enterprise_judgment_core as core
from scripts import enterprise_judgment_quantitative_adapter as quant
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


def test_operating_improvement_with_owner_cash_deterioration_stays_mixed() -> None:
    package = _source_package()
    model = _model(owner_cash_direction="DETERIORATES", source_package=package)
    judgment = _judgment_input(resolution="PRIMARY")
    candidate = core.compile_cjo_candidate(
        model=model, ledger=_ledger(), source_package=package, judgment_input=judgment,
    )
    assert candidate["resolution"] == "MIXED"
    assert candidate["normal_earnings_transmission"]["direction"] == "IMPROVES"
    assert candidate["owner_cash_transmission"]["direction"] == "DETERIORATES"
    frozen = core.freeze_cjo(candidate=candidate, independent_review=_review(candidate))
    overlay = quant.compile_synthetic_quantitative_overlay(
        frozen_cjo=frozen, overlay_input=_overlay_input(50.0),
    )
    assert overlay["price_overlay"]["status"] == "MIXED_NO_DIRECTIONAL_CONCLUSION"
    assert overlay["price_overlay"]["directional_investment_conclusion"] is None


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
