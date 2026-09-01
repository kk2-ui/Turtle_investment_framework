from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.cash_accessibility_model import (
    _cash_factual_operands,
    _cash_operand_unit,
    _cash_path_nodes,
    compile_cash_accessibility_model,
    compute_cash_accessibility_model,
    project_reader_conclusions,
    validate_cash_accessibility_input,
    validate_cash_accessibility_model,
)


ROOT = Path(__file__).resolve().parents[1]


def _facts(*fact_ids: str) -> list[dict[str, str]]:
    return [{"fact_id": fact_id, "status": "VERIFIED"} for fact_id in fact_ids]


def _bind_to_canonical_official_facts(payload: dict) -> dict:
    """Make the cash arithmetic fixture carry an exact official-fact contract.

    The model under test does not synthesize this register.  This test helper
    is deliberately explicit about every submitted operand so mutations must
    refresh its evidence rather than silently retaining a stale VERIFIED tag.
    """
    def strip_prior(value: object) -> None:
        if isinstance(value, dict):
            refs = value.get("source_fact_ids")
            if isinstance(refs, list):
                value["source_fact_ids"] = [
                    item for item in refs
                    if not (isinstance(item, str) and item.startswith("OFFICIAL:CASH:"))
                ]
            for item in value.values():
                strip_prior(item)
        elif isinstance(value, list):
            for item in value:
                strip_prior(item)
    strip_prior(payload)
    payload.pop("official_fact_register", None)
    payload.pop("canonical_fact_bindings", None)
    cutoff = payload["cutoff_at"]
    source_date = "2025-12-30" if cutoff >= "2025-12-31" else "2017-12-30"
    observations: list[dict] = []
    bindings: list[dict] = []
    existing_ids: set[str] = set()
    operands = _cash_factual_operands(payload)
    for index, (path, operand) in enumerate(sorted(operands.items())):
        fact_id = f"OFFICIAL:CASH:{index:03d}"
        unit = _cash_operand_unit(payload, path, operand)
        observations.append({
            "fact_id": fact_id,
            "source_id": "TEST-OFFICIAL-CASH",
            "pdf_page": 7,
            "table_or_section": "Cash accessibility source table",
            "field": path,
            "period": "FY2025",
            "responsibility_boundary": "listed consolidated issuer",
            "unit": unit,
            "value": operand,
        })
        bindings.append({
            "path": path,
            "fact_id": fact_id,
            "unit": unit,
            "responsibility_boundary": "listed consolidated issuer",
        })
        nodes = _cash_path_nodes(payload, path)
        owner = next(
            (node for node in reversed(nodes) if isinstance(node.get("source_fact_ids"), list)),
            None,
        )
        leaf = path.rsplit(".", 1)[-1]
        applicability_owner = next(
            (node for node in reversed(nodes) if isinstance(node.get("source_fact_bindings"), dict)),
            None,
        )
        if applicability_owner is not None and leaf in applicability_owner["source_fact_bindings"]:
            applicability_owner["source_fact_bindings"][leaf] = fact_id
        elif owner is not None:
            owner["source_fact_ids"].append(fact_id)
        existing_ids.add(fact_id)
    # Source lists may still name a qualitative identity/context fact.  Give
    # those IDs a canonical official locator too; no value bridge binds them.
    def collect_refs(value: object) -> set[str]:
        if isinstance(value, dict):
            refs = {
                str(item) for item in value.get("source_fact_ids", [])
                if isinstance(item, str) and item
            }
            refs |= {
                str(item) for item in value.get("source_fact_bindings", {}).values()
                if isinstance(item, str) and item
            }
            for item in value.values():
                refs |= collect_refs(item)
            return refs
        if isinstance(value, list):
            return set().union(*(collect_refs(item) for item in value)) if value else set()
        return set()
    refs = collect_refs(payload) | set(payload.get("identity_source_fact_ids", []))
    for fact_id in sorted(refs - {item["fact_id"] for item in observations}):
        observations.append({
            "fact_id": fact_id,
            "source_id": "TEST-OFFICIAL-CASH",
            "pdf_page": 7,
            "table_or_section": "Cash accessibility source table",
            "field": "qualitative_context",
            "period": "FY2025",
            "responsibility_boundary": "listed consolidated issuer",
            "unit": "text",
            "value": "officially disclosed context",
        })
        existing_ids.add(fact_id)
    payload["official_fact_register"] = {
        "schema_version": "turtle-cutoff-official-fact-register.v2",
        "cutoff_at": cutoff,
        "sources": [{
            "source_id": "TEST-OFFICIAL-CASH",
            "static_url": "https://disclosure.example.gov/finalpage/cash-fixture.pdf",
            "available_at": source_date,
            "declared_pages": 20,
        }],
        "observations": observations,
    }
    payload["canonical_fact_bindings"] = bindings
    payload["verified_facts"] = _facts(*sorted(existing_ids))
    return payload


def _event(
    event_type: str,
    amount: float,
    funding: str,
    fact_id: str,
    event_date: str = "2024-06-30",
    observed_at: str = "2024-12-31",
) -> dict:
    return {
        "event_type": event_type,
        "event_date": event_date,
        "observed_at": observed_at,
        "amount": amount,
        "funding_source_identity": funding,
        "source_fact_ids": [fact_id],
    }


def _recovery_cohort(
    cohort_id: str,
    recovered: float,
    fact_id: str,
    year: int,
) -> dict:
    return {
        "cohort_id": cohort_id,
        "recovery_mechanism_id": "RP:STANDARD_SETTLEMENT",
        "period_start": f"{year}-01-01",
        "period_end": f"{year}-12-31",
        "maturity_status": "MATURED",
        "opening_gross_exposure": 100,
        "opening_ecl_allowance": 0,
        "cash_collections": recovered,
        "noncash_settlements": 0,
        "writeoffs": 100 - recovered,
        "source_fact_ids": [fact_id],
    }


def _payload() -> dict:
    fact_ids = [
        "F:IDENTITY",
        "F:PARENT",
        "F:WHOLE",
        "F:PARTIAL",
        "F:P1",
        "F:P2",
        "F:P3",
        "F:SPECIAL",
        "F:BUYBACK",
        "F:FUTURE",
        "F:RECEIVABLE",
        "F:CONTINUITY",
        "F:RP:C1",
        "F:RP:C2",
        "F:RP:C3",
    ]
    payload = {
        "schema_version": "cash-accessibility-input.v1",
        "model_id": "CASH:TEST",
        "company_id": "TEST.HK",
        "cutoff_at": "2025-12-31",
        "position_as_of": "2025-12-31",
        "currency": "RMB",
        "unit": "million",
        "identity_source_fact_ids": ["F:IDENTITY"],
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
                "source_fact_ids": ["F:PARENT"],
            },
            {
                "entity_id": "wholly_owned",
                "entity_kind": "wholly_owned_subsidiary",
                "gross_cash": 50,
                "restricted_or_regulatory_cash": 5,
                "operating_liquidity_requirement": 15,
                "ordinary_share_economic_interest": 1,
                "transfer_tax_friction_rate": 0.10,
                "source_fact_ids": ["F:WHOLE"],
            },
            {
                "entity_id": "partially_owned",
                "entity_kind": "partially_owned_subsidiary",
                "gross_cash": 100,
                "restricted_or_regulatory_cash": 0,
                "operating_liquidity_requirement": 20,
                "ordinary_share_economic_interest": 0.60,
                "transfer_tax_friction_rate": 0.05,
                "source_fact_ids": ["F:PARTIAL"],
            },
        ],
        "realization_periods": [
            {
                "period_id": "2023",
                "period_start": "2023-01-01",
                "period_end": "2023-12-31",
                "opening_position_as_of": "2023-01-01",
                "comparable": True,
                "opening_existing_excess_cash": 100,
                "retained_cash_generated": 50,
                "ordinary_dividend": 20,
                "extraordinary_events": [
                    _event(
                        "special_dividend", 10, "existing_excess_cash", "F:SPECIAL",
                        "2023-06-30", "2023-12-31",
                    )
                ],
                "source_fact_ids": ["F:P1"],
            },
            {
                "period_id": "2024",
                "period_start": "2024-01-01",
                "period_end": "2024-12-31",
                "opening_position_as_of": "2024-01-01",
                "comparable": True,
                "opening_existing_excess_cash": 100,
                "retained_cash_generated": 50,
                "ordinary_dividend": 25,
                "extraordinary_events": [],
                "source_fact_ids": ["F:P2"],
            },
            {
                "period_id": "2025",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "opening_position_as_of": "2025-01-01",
                "comparable": True,
                "opening_existing_excess_cash": 100,
                "retained_cash_generated": 50,
                "ordinary_dividend": 30,
                "extraordinary_events": [
                    _event(
                        "cancellative_net_buyback", 30, "existing_excess_cash", "F:BUYBACK",
                        "2025-06-30", "2025-12-31",
                    )
                ],
                "source_fact_ids": ["F:P3"],
            },
        ],
        "realization_applicability": {
            "existing_excess_cash": {
                "cash_control_continuity": True,
                "upstream_mechanism_continuity": True,
                "extraordinary_distribution_policy_continuity": True,
                "capital_need_continuity": True,
                "source_fact_bindings": {
                    "cash_control_continuity": "F:CONTINUITY",
                    "upstream_mechanism_continuity": "F:CONTINUITY",
                    "extraordinary_distribution_policy_continuity": "F:CONTINUITY",
                    "capital_need_continuity": "F:CONTINUITY",
                },
            },
            "future_retained_cash": {
                "cash_control_continuity": True,
                "ordinary_distribution_policy_continuity": True,
                "capital_need_continuity": True,
                "source_fact_bindings": {
                    "cash_control_continuity": "F:CONTINUITY",
                    "ordinary_distribution_policy_continuity": "F:CONTINUITY",
                    "capital_need_continuity": "F:CONTINUITY",
                },
            },
        },
        "future_retained_cash": {
            "projected_amount": 80,
            "legal_upper_bound_rate": 0.80,
            "source_fact_ids": ["F:FUTURE"],
        },
        "related_party_receivables": [
            {
                "receivable_id": "RP:1",
                "gross_amount": 100,
                "ecl_allowance": 10,
                "post_position_collections": 20,
                "aging_bucket": "current",
                "recovery_mechanism_id": "RP:STANDARD_SETTLEMENT",
                "recovery_cohorts": [
                    _recovery_cohort("RP:C1", 80, "F:RP:C1", 2023),
                    _recovery_cohort("RP:C2", 90, "F:RP:C2", 2024),
                    _recovery_cohort("RP:C3", 100, "F:RP:C3", 2025),
                ],
                "prospective_applicability": {
                    "same_recovery_mechanism": True,
                    "same_counterparty_control": True,
                    "same_settlement_terms": True,
                    "source_fact_bindings": {
                        "same_recovery_mechanism": "F:CONTINUITY",
                        "same_counterparty_control": "F:CONTINUITY",
                        "same_settlement_terms": "F:CONTINUITY",
                    },
                },
                "source_fact_ids": ["F:RECEIVABLE"],
            }
        ],
        "valuation_destinations": [
            {
                "component_id": "legal_cash_accessibility",
                "valuation_destination": "legal_accessibility_ceiling_only",
            },
            {
                "component_id": "existing_excess_cash_realization",
                "valuation_destination": "equity_value_existing_excess_cash",
            },
            {
                "component_id": "future_retained_cash_realization",
                "valuation_destination": "operating_value_future_retained_cash",
            },
            {
                "component_id": "related_party_receivable_realization",
                "valuation_destination": "equity_value_related_party_receivable",
            },
        ],
    }
    return _bind_to_canonical_official_facts(payload)


def test_entity_cash_math_separates_restrictions_nci_and_upstream_friction() -> None:
    model = compute_cash_accessibility_model(_payload())
    rows = {row["entity_id"]: row for row in model["legal_cash_accessibility"]["rows"]}

    assert rows["parent"]["legal_accessible_cash"] == 70
    assert rows["wholly_owned"]["legal_accessible_cash"] == 27
    assert rows["partially_owned"]["legal_accessible_cash"] == 45.6
    assert model["legal_cash_accessibility"]["adopted_value"] == 142.6
    assert model["existing_excess_cash_realization"]["adopted_value"] == 0
    assert model["existing_excess_cash_realization"]["conditional_amount_range"] == {
        "low": 0,
        "base": 14.26,
        "high": 42.78,
    }
    assert model["existing_excess_cash_realization"]["unrecognized_remainder"] == 99.82
    assert validate_cash_accessibility_model(model)["state"] == "VALID"


def test_diagnostic_total_is_a_ceiling_not_an_additive_cash_leaf() -> None:
    payload = _payload()
    payload["entity_cash_rows"].append({
        "entity_id": "consolidated_diagnostic",
        "entity_kind": "other",
        "gross_cash": 200,
        "restricted_or_regulatory_cash": 10,
        "operating_liquidity_requirement": 0,
        "ordinary_share_economic_interest": 1,
        "transfer_tax_friction_rate": 0,
        "aggregation_role": "DIAGNOSTIC_TOTAL",
        "cash_perimeter_id": "consolidated_group",
        "source_fact_ids": ["F:PARENT"],
    })
    _bind_to_canonical_official_facts(payload)

    legal = compute_cash_accessibility_model(payload)["legal_cash_accessibility"]

    assert legal["additive_leaf_total"] == pytest.approx(142.6)
    assert legal["diagnostic_total_ceiling"] == pytest.approx(190)
    assert legal["amount_range"] == {
        "low": pytest.approx(142.6),
        "base": pytest.approx(142.6),
        "high": pytest.approx(190),
    }
    assert legal["adopted_value"] == pytest.approx(142.6)
    assert legal["adopted_value"] != pytest.approx(190)
    assert legal["adopted_value"] != pytest.approx(332.6)
    existing = compute_cash_accessibility_model(payload)[
        "existing_excess_cash_realization"
    ]
    assert existing["legal_upper_bound"] == pytest.approx(142.6)
    assert existing["unrecognized_remainder"] == pytest.approx(190)
    diagnostic = next(
        row for row in legal["rows"]
        if row["entity_id"] == "consolidated_diagnostic"
    )
    assert diagnostic["included_in_additive_leaf_total"] is False


def test_additive_cash_perimeter_may_not_be_reused() -> None:
    payload = _payload()
    payload["entity_cash_rows"][1]["cash_perimeter_id"] = "parent"

    validation = validate_cash_accessibility_input(payload)

    assert validation["state"] == "INVALID"
    assert "entity_cash_rows[1].cash_perimeter_id_reused" in validation["findings"]


def test_realization_history_requires_an_independent_opening_position_clock() -> None:
    payload = _payload()
    payload["realization_periods"][0].pop("opening_position_as_of")

    findings = validate_cash_accessibility_input(payload)["findings"]

    assert "realization_periods[0].opening_position_as_of_invalid" in findings


def test_extraordinary_realization_requires_event_and_observation_clocks() -> None:
    payload = _payload()
    payload["realization_periods"][0]["extraordinary_events"][0].pop("event_date")

    findings = validate_cash_accessibility_input(payload)["findings"]

    assert "realization_periods[0].extraordinary_events[0].event_clock_invalid" in findings


def test_balance_sheet_position_date_can_precede_evidence_cutoff_without_losing_identity() -> None:
    payload = _payload()
    payload["cutoff_at"] = "2026-08-11"
    payload["position_as_of"] = "2025-12-31"
    _bind_to_canonical_official_facts(payload)

    model = compute_cash_accessibility_model(payload)

    assert model["cutoff_at"] == "2026-08-11"
    assert model["position_as_of"] == "2025-12-31"
    assert model["as_of"] == "2025-12-31"
    assert validate_cash_accessibility_model(model)["state"] == "VALID"


def test_missing_extraordinary_history_keeps_legal_ceiling_separate_and_adopts_zero() -> None:
    payload = _payload()
    payload["realization_periods"] = []
    _bind_to_canonical_official_facts(payload)
    model = compute_cash_accessibility_model(payload)
    existing = model["existing_excess_cash_realization"]

    assert existing["qualifying_period_count"] == 0
    assert existing["historical_observed_rate_range"] is None
    assert existing["realization_rate_range"] is None
    assert existing["amount_range"] == {"low": 0, "base": 0, "high": 0}
    assert existing["legal_upper_bound"] == 142.6
    assert existing["adopted_value"] == 0


def test_three_comparable_periods_use_median_and_include_zero_event_period() -> None:
    model = compute_cash_accessibility_model(_payload())
    existing = model["existing_excess_cash_realization"]

    assert [row["existing_cash_realization_rate"] for row in existing["history"]] == [0.1, 0, 0.3]
    assert existing["qualifying_period_count"] == 3
    assert existing["historical_observed_rate_range"] == {"low": 0, "base": 0.1, "high": 0.3}
    assert existing["realization_rate_range"] == {"low": 0, "base": 0.1, "high": 0.3}
    assert existing["adopted_realization_rate"] == 0
    assert existing["evidenced_lower_bound"] == 0

    without_zero = _payload()
    without_zero["realization_periods"].pop(1)
    _bind_to_canonical_official_facts(without_zero)
    unqualified = compute_cash_accessibility_model(without_zero)["existing_excess_cash_realization"]
    assert unqualified["qualifying_period_count"] == 2
    assert unqualified["realization_rate_range"] is None
    assert unqualified["adopted_value"] == 0


def test_three_historical_periods_do_not_become_a_forecast_without_continuity() -> None:
    payload = _payload()
    payload["realization_applicability"]["existing_excess_cash"] = {
        "cash_control_continuity": None,
        "upstream_mechanism_continuity": None,
        "extraordinary_distribution_policy_continuity": None,
        "capital_need_continuity": None,
        "source_fact_bindings": {},
    }
    _bind_to_canonical_official_facts(payload)
    existing = compute_cash_accessibility_model(payload)[
        "existing_excess_cash_realization"
    ]

    assert existing["historical_observed_rate_range"] == {
        "low": 0,
        "base": 0.1,
        "high": 0.3,
    }
    assert existing["prospective_applicability"]["status"] == "UNKNOWN"
    assert existing["realization_rate_range"] is None
    assert existing["adopted_realization_rate"] is None
    assert existing["adopted_value"] == 0


def test_evidence_state_keeps_support_invalidation_and_unknowns_separate() -> None:
    payload = _payload()
    payload["realization_applicability"]["existing_excess_cash"] = {
        "cash_control_continuity": True,
        "upstream_mechanism_continuity": False,
        "extraordinary_distribution_policy_continuity": None,
        "capital_need_continuity": True,
        "source_fact_bindings": {
            "cash_control_continuity": "F:CONTINUITY",
            "upstream_mechanism_continuity": "F:P1",
            "capital_need_continuity": "F:P3",
        },
    }
    _bind_to_canonical_official_facts(payload)

    existing = compute_cash_accessibility_model(payload)[
        "existing_excess_cash_realization"
    ]

    assert existing["conditional_amount_range"] is None
    assert existing["evidenced_lower_bound"] == 0
    binding_ids = {
        item["path"]: item["fact_id"]
        for item in payload["canonical_fact_bindings"]
    }
    evidence = existing["evidence_state"]
    assert evidence["invalidating_fact_ids"] == [binding_ids[
        "realization_applicability.existing_excess_cash.upstream_mechanism_continuity"
    ]]
    assert binding_ids[
        "realization_applicability.existing_excess_cash.cash_control_continuity"
    ] in evidence["supporting_fact_ids"]
    assert evidence["unresolved_conditions"] == [
        "extraordinary_distribution_policy_continuity"
    ]


def test_ordinary_dividends_change_future_retention_but_not_existing_cash() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    changed_payload = _payload()
    changed_payload["realization_periods"][1]["ordinary_dividend"] = 5
    _bind_to_canonical_official_facts(changed_payload)
    changed = compute_cash_accessibility_model(changed_payload)

    for field in ("realization_rate_range", "amount_range", "adopted_value"):
        assert changed["existing_excess_cash_realization"][field] == baseline["existing_excess_cash_realization"][field]
    assert changed["future_retained_cash_realization"]["adopted_value"] != baseline["future_retained_cash_realization"]["adopted_value"]


def test_cash_flow_identity_prevents_cross_disposition_reuse() -> None:
    payload = _payload()
    period = payload["realization_periods"][0]
    period["ordinary_dividend_cash_flow_id"] = "FLOW:2023:DIVIDEND"
    period["extraordinary_events"][0]["cash_flow_id"] = "FLOW:2023:DIVIDEND"
    payload["related_party_receivables"][0][
        "post_position_collection_cash_flow_id"
    ] = "FLOW:2023:DIVIDEND"

    validation = validate_cash_accessibility_input(payload)

    assert validation["state"] == "INVALID"
    assert "cash_flow_id_reused:FLOW:2023:DIVIDEND" in validation["findings"]


def test_cash_flow_identity_projects_funding_and_disposition_without_new_workflow() -> None:
    payload = _payload()
    period = payload["realization_periods"][0]
    period["ordinary_dividend_cash_flow_id"] = "FLOW:2023:ORDINARY"
    period["ordinary_dividend_funding_source_identity"] = "future_retained_cash"
    period["extraordinary_events"][0]["cash_flow_id"] = "FLOW:2023:SPECIAL"
    payload["related_party_receivables"][0][
        "post_position_collection_cash_flow_id"
    ] = "FLOW:2026:RECEIVABLE"
    _bind_to_canonical_official_facts(payload)

    model = compute_cash_accessibility_model(payload)
    history = model["existing_excess_cash_realization"]["history"][0]
    special = history["extraordinary_events"][0]
    receivable = model["related_party_receivable_realization"]["rows"][0]

    assert history["ordinary_dividend_funding_source_identity"] == "future_retained_cash"
    assert history["ordinary_dividend_disposition"] == "ordinary_dividend"
    assert special["funding_source_identity"] == "existing_excess_cash"
    assert special["cash_disposition"] == "special_dividend"
    assert receivable["post_position_collection_funding_source_identity"] == (
        "related_party_receivable"
    )
    assert receivable["post_position_collection_disposition"] == (
        "receivable_collection"
    )
    assert validate_cash_accessibility_model(model)["state"] == "VALID"


@pytest.mark.parametrize(
    ("event_type", "fact_id"),
    [
        ("special_dividend", "F:SPECIAL"),
        ("cancellative_net_buyback", "F:BUYBACK"),
    ],
)
def test_eligible_special_realization_and_buybacks_calibrate_existing_cash(
    event_type: str,
    fact_id: str,
) -> None:
    payload = _payload()
    payload["realization_periods"][1]["extraordinary_events"] = [
        _event(event_type, 20, "existing_excess_cash", fact_id)
    ]
    _bind_to_canonical_official_facts(payload)
    model = compute_cash_accessibility_model(payload)

    assert model["existing_excess_cash_realization"]["adopted_realization_rate"] == 0.1
    assert model["existing_excess_cash_realization"]["adopted_value"] == 14.26


def test_ineligible_and_unknown_funding_do_not_calibrate_existing_cash() -> None:
    debt_funded = _payload()
    debt_funded["realization_periods"][1]["extraordinary_events"] = [
        _event("special_dividend", 90, "debt_funded", "F:SPECIAL")
    ]
    _bind_to_canonical_official_facts(debt_funded)
    debt_model = compute_cash_accessibility_model(debt_funded)
    period = debt_model["existing_excess_cash_realization"]["history"][1]
    assert period["eligible_extraordinary_realization"] == 0
    assert period["existing_cash_realization_rate"] == 0

    unknown_funded = _payload()
    unknown_funded["realization_periods"][1]["extraordinary_events"] = [
        _event("special_dividend", 90, "unknown", "F:SPECIAL")
    ]
    _bind_to_canonical_official_facts(unknown_funded)
    unknown_model = compute_cash_accessibility_model(unknown_funded)
    period = unknown_model["existing_excess_cash_realization"]["history"][1]
    assert period["existing_cash_calibration_qualified"] is False
    assert unknown_model["existing_excess_cash_realization"]["qualifying_period_count"] == 2
    assert unknown_model["existing_excess_cash_realization"]["adopted_value"] == 0


def test_future_retained_cash_has_a_distinct_destination_and_calibration() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    changed_payload = _payload()
    changed_payload["future_retained_cash"]["projected_amount"] = 160
    _bind_to_canonical_official_facts(changed_payload)
    changed = compute_cash_accessibility_model(changed_payload)

    assert baseline["future_retained_cash_realization"]["adopted_realization_rate"] == 0.4
    assert baseline["future_retained_cash_realization"]["adopted_value"] == 32
    assert changed["future_retained_cash_realization"]["adopted_value"] == 64
    assert changed["existing_excess_cash_realization"] == baseline["existing_excess_cash_realization"]
    assert changed["related_party_receivable_realization"] == baseline["related_party_receivable_realization"]


def test_related_receivable_uses_only_same_mechanism_mature_cohorts() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    receivable = baseline["related_party_receivable_realization"]
    assert receivable["amount_range"] == {"low": 76, "base": 83, "high": 90}
    assert receivable["adopted_value"] == 76
    assert receivable["conditional_amount_range"] == receivable["amount_range"]
    assert receivable["unrecognized_remainder"] == 0
    assert receivable["rows"][0]["historical_observed_recovery_rate_range"] == {
        "low": 0.8,
        "base": 0.9,
        "high": 1,
    }
    assert baseline["legal_cash_accessibility"]["adopted_value"] == 142.6

    aging_only = _payload()
    aging_only["related_party_receivables"][0]["aging_bucket"] = "over_three_years"
    _bind_to_canonical_official_facts(aging_only)
    aging_model = compute_cash_accessibility_model(aging_only)
    assert aging_model["related_party_receivable_realization"]["amount_range"] == receivable["amount_range"]

    older_payload = _payload()
    older_payload["related_party_receivables"][0].update({
        "aging_bucket": "over_three_years",
        "ecl_allowance": 30,
    })
    _bind_to_canonical_official_facts(older_payload)
    older = compute_cash_accessibility_model(older_payload)
    assert older["related_party_receivable_realization"]["amount_range"] == {
        "low": 60,
        "base": 65,
        "high": 70,
    }
    for component in (
        "legal_cash_accessibility",
        "existing_excess_cash_realization",
        "future_retained_cash_realization",
    ):
        assert older[component] == baseline[component]


def test_related_receivable_without_mature_cohorts_keeps_uncollected_exposure_unknown() -> None:
    payload = _payload()
    receivable_input = payload["related_party_receivables"][0]
    receivable_input["recovery_cohorts"] = []
    receivable_input["prospective_applicability"] = {
        "same_recovery_mechanism": None,
        "same_counterparty_control": None,
        "same_settlement_terms": None,
        "source_fact_bindings": {},
    }
    _bind_to_canonical_official_facts(payload)

    receivable = compute_cash_accessibility_model(payload)[
        "related_party_receivable_realization"
    ]

    assert receivable["recovery_status"] == "UNKNOWN"
    assert receivable["amount_range"] == {"low": 20, "base": 20, "high": 20}
    assert receivable["adopted_value"] == 20
    assert receivable["unrecognized_net_exposure"] == 70
    assert receivable["rows"][0]["uncollected_recovery_rate_range"] is None


def test_receivable_conditional_high_below_one_keeps_unrecognized_remainder() -> None:
    payload = _payload()
    row = payload["related_party_receivables"][0]
    row["recovery_cohorts"] = [
        _recovery_cohort("RP:C1", 50, "F:RP:C1", 2023),
        _recovery_cohort("RP:C2", 60, "F:RP:C2", 2024),
        _recovery_cohort("RP:C3", 70, "F:RP:C3", 2025),
    ]
    _bind_to_canonical_official_facts(payload)

    receivable = compute_cash_accessibility_model(payload)[
        "related_party_receivable_realization"
    ]

    assert receivable["conditional_amount_range"] == {
        "low": pytest.approx(55),
        "base": pytest.approx(62),
        "high": pytest.approx(69),
    }
    assert receivable["evidenced_lower_bound"] == pytest.approx(55)
    assert receivable["adopted_value"] == pytest.approx(55)
    assert receivable["unrecognized_remainder"] == pytest.approx(21)
    assert receivable["unrecognized_net_exposure"] == pytest.approx(21)


def test_perturbations_change_only_the_economically_connected_outputs() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    for entity_index, field, value in (
        (0, "restricted_or_regulatory_cash", 30),
        (2, "ordinary_share_economic_interest", 0.40),
        (1, "transfer_tax_friction_rate", 0.30),
    ):
        payload = _payload()
        payload["entity_cash_rows"][entity_index][field] = value
        _bind_to_canonical_official_facts(payload)
        changed = compute_cash_accessibility_model(payload)
        assert changed["legal_cash_accessibility"] != baseline["legal_cash_accessibility"]
        assert changed["existing_excess_cash_realization"]["amount_range"] != baseline["existing_excess_cash_realization"]["amount_range"]
        assert changed["future_retained_cash_realization"] == baseline["future_retained_cash_realization"]
        assert changed["related_party_receivable_realization"] == baseline["related_party_receivable_realization"]

    collected_payload = _payload()
    collected_payload["related_party_receivables"][0]["post_position_collections"] = 40
    _bind_to_canonical_official_facts(collected_payload)
    collected = compute_cash_accessibility_model(collected_payload)
    assert collected["related_party_receivable_realization"]["adopted_value"] == 80
    for component in (
        "legal_cash_accessibility",
        "existing_excess_cash_realization",
        "future_retained_cash_realization",
    ):
        assert collected[component] == baseline[component]


def test_every_factual_row_must_reference_a_verified_fact_id() -> None:
    payload = _payload()
    payload["entity_cash_rows"][0]["source_fact_ids"] = ["F:NOT_VERIFIED"]
    result = validate_cash_accessibility_input(payload)
    assert result["state"] == "INVALID"
    assert any(
        "source_fact_ids_not_canonical_official_observation:F:NOT_VERIFIED" in item
        for item in result["findings"]
    )

    payload = _payload()
    payload["realization_periods"][0]["evidence"] = "annual report page 10"
    result = validate_cash_accessibility_input(payload)
    assert result["state"] == "INVALID"
    assert "realization_periods[0].evidence_not_allowed" in result["findings"]


def test_cash_value_cannot_be_authorized_by_a_self_declared_verified_fact() -> None:
    payload = _payload()
    payload["verified_facts"].append({
        "fact_id": "OBS:SELF-DECLARED-CASH", "status": "VERIFIED",
    })
    payload["entity_cash_rows"][0]["source_fact_ids"].append(
        "OBS:SELF-DECLARED-CASH"
    )
    binding = next(
        item for item in payload["canonical_fact_bindings"]
        if item["path"] == "entity_cash_rows[0].gross_cash"
    )
    binding["fact_id"] = "OBS:SELF-DECLARED-CASH"

    findings = validate_cash_accessibility_input(payload)["findings"]

    assert (
        "verified_facts[" in ",".join(findings)
        and "fact_id_not_canonical_official_observation:OBS:SELF-DECLARED-CASH"
        in ",".join(findings)
    )
    assert any(
        "fact_id_not_canonical_official_observation:OBS:SELF-DECLARED-CASH" in item
        for item in findings
    )


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (
            lambda payload, binding: payload["official_fact_register"]["observations"].remove(
                next(
                    item for item in payload["official_fact_register"]["observations"]
                    if item["fact_id"] == binding["fact_id"]
                )
            ),
            "fact_id_not_canonical_official_observation",
        ),
        (
            lambda payload, binding: payload["official_fact_register"]["sources"][0].update(
                available_at=payload["cutoff_at"]
            ),
            "official_fact_register:register.sources[0].available_at_not_before_cutoff",
        ),
        (
            lambda payload, binding: binding.update(
                responsibility_boundary="parent-only boundary"
            ),
            "responsibility_boundary_mismatch:entity_cash_rows[0].gross_cash",
        ),
        (
            lambda payload, binding: next(
                item for item in payload["official_fact_register"]["observations"]
                if item["fact_id"] == binding["fact_id"]
            ).update(value=101),
            "value_mismatch:entity_cash_rows[0].gross_cash",
        ),
        (
            lambda payload, binding: binding.update(unit="ratio"),
            "unit_not_compatible_with_operand:entity_cash_rows[0].gross_cash",
        ),
    ],
)
def test_cash_operands_require_a_complete_pre_cutoff_official_observation(
    mutation, finding: str,
) -> None:
    payload = _payload()
    binding = next(
        item for item in payload["canonical_fact_bindings"]
        if item["path"] == "entity_cash_rows[0].gross_cash"
    )
    mutation(payload, binding)

    findings = validate_cash_accessibility_input(payload)["findings"]

    assert any(finding in item for item in findings)


def test_duplicate_destination_or_component_reuse_is_rejected() -> None:
    duplicate_destination = _payload()
    duplicate_destination["valuation_destinations"][2]["valuation_destination"] = (
        "equity_value_existing_excess_cash"
    )
    result = validate_cash_accessibility_input(duplicate_destination)
    assert result["state"] == "INVALID"
    assert any("valuation_destination_reused" in item for item in result["findings"])

    duplicate_component = _payload()
    duplicate_component["valuation_destinations"][3] = deepcopy(
        duplicate_component["valuation_destinations"][2]
    )
    result = validate_cash_accessibility_input(duplicate_component)
    assert result["state"] == "INVALID"
    assert any("component_id_reused" in item for item in result["findings"])
    with pytest.raises(ValueError, match="cash_accessibility_input_invalid"):
        compute_cash_accessibility_model(duplicate_component)


def test_model_validator_rejects_nonmonotonic_ranges_and_ledger_reuse() -> None:
    model = compute_cash_accessibility_model(_payload())
    broken = deepcopy(model)
    broken["existing_excess_cash_realization"]["amount_range"] = {
        "low": 20,
        "base": 10,
        "high": 30,
    }
    result = validate_cash_accessibility_model(broken)
    assert result["state"] == "INVALID"
    assert any("amount_range_not_monotonic" in item for item in result["findings"])

    broken = deepcopy(model)
    broken["valuation_destination_ledger"][3]["valuation_destination"] = (
        broken["valuation_destination_ledger"][1]["valuation_destination"]
    )
    result = validate_cash_accessibility_model(broken)
    assert result["state"] == "INVALID"
    assert any("valuation_destination_reused" in item for item in result["findings"])


def test_reader_projection_is_investor_prose_not_control_plane_language() -> None:
    model = compile_cash_accessibility_model(_payload())
    conclusions = project_reader_conclusions(model)
    assert model["as_of"] == "2025-12-31"
    assert "普通股现金已证可达金额" in model["economic_conclusion"]
    assert "存量超额现金已证下限为 RMB 0.00 million" in model["economic_conclusion"]
    assert "未认可余量为 RMB 99.82 million" in model["economic_conclusion"]
    assert conclusions == model["reader_conclusions"]
    assert len(conclusions) == 4
    serialized = " ".join(conclusions)
    for token in ("schema", "VALID", "INVALID", "object_id", "P_LONG", "PRIMARY_ROUTE"):
        assert token.lower() not in serialized.lower()
    assert "已证可达金额" in serialized
    assert "关联方应收款" in serialized


def test_schema_is_parseable_and_names_the_canonical_model() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "cash_accessibility_model.schema.json").read_text(encoding="utf-8")
    )
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == "cash-accessibility-model.v1"
    existing = schema["$defs"]["existingExcessCashRealization"]
    assert {
        "evidenced_lower_bound",
        "conditional_amount_range",
        "unrecognized_remainder",
        "evidence_state",
    } <= set(existing["required"])
    assert "ordinary_dividend_cash_flow_id" in schema["$defs"][
        "realizationPeriod"
    ]["properties"]
    assert "post_position_collection_cash_flow_id" in schema["$defs"][
        "receivableRow"
    ]["properties"]
