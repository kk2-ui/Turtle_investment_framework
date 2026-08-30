from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.cash_accessibility_model import (
    compile_cash_accessibility_model,
    compute_cash_accessibility_model,
    project_reader_conclusions,
    validate_cash_accessibility_input,
    validate_cash_accessibility_model,
)


ROOT = Path(__file__).resolve().parents[1]


def _facts(*fact_ids: str) -> list[dict[str, str]]:
    return [{"fact_id": fact_id, "status": "VERIFIED"} for fact_id in fact_ids]


def _event(
    event_type: str,
    amount: float,
    funding: str,
    fact_id: str,
) -> dict:
    return {
        "event_type": event_type,
        "amount": amount,
        "funding_source_identity": funding,
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
    ]
    return {
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
                "comparable": True,
                "opening_existing_excess_cash": 100,
                "retained_cash_generated": 50,
                "ordinary_dividend": 20,
                "extraordinary_events": [
                    _event("special_dividend", 10, "existing_excess_cash", "F:SPECIAL")
                ],
                "source_fact_ids": ["F:P1"],
            },
            {
                "period_id": "2024",
                "comparable": True,
                "opening_existing_excess_cash": 100,
                "retained_cash_generated": 50,
                "ordinary_dividend": 25,
                "extraordinary_events": [],
                "source_fact_ids": ["F:P2"],
            },
            {
                "period_id": "2025",
                "comparable": True,
                "opening_existing_excess_cash": 100,
                "retained_cash_generated": 50,
                "ordinary_dividend": 30,
                "extraordinary_events": [
                    _event("cancellative_net_buyback", 30, "existing_excess_cash", "F:BUYBACK")
                ],
                "source_fact_ids": ["F:P3"],
            },
        ],
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
                "post_cutoff_collections": 20,
                "aging_bucket": "current",
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


def test_entity_cash_math_separates_restrictions_nci_and_upstream_friction() -> None:
    model = compute_cash_accessibility_model(_payload())
    rows = {row["entity_id"]: row for row in model["legal_cash_accessibility"]["rows"]}

    assert rows["parent"]["legal_accessible_cash"] == 70
    assert rows["wholly_owned"]["legal_accessible_cash"] == 27
    assert rows["partially_owned"]["legal_accessible_cash"] == 45.6
    assert model["legal_cash_accessibility"]["adopted_value"] == 142.6
    assert model["existing_excess_cash_realization"]["adopted_value"] == 14.26
    assert validate_cash_accessibility_model(model)["state"] == "VALID"


def test_balance_sheet_position_date_can_precede_evidence_cutoff_without_losing_identity() -> None:
    payload = _payload()
    payload["cutoff_at"] = "2026-08-11"
    payload["position_as_of"] = "2025-12-31"

    model = compute_cash_accessibility_model(payload)

    assert model["cutoff_at"] == "2026-08-11"
    assert model["position_as_of"] == "2025-12-31"
    assert model["as_of"] == "2025-12-31"
    assert validate_cash_accessibility_model(model)["state"] == "VALID"


def test_missing_extraordinary_history_uses_zero_to_legal_ceiling_and_adopts_zero() -> None:
    payload = _payload()
    payload["realization_periods"] = []
    model = compute_cash_accessibility_model(payload)
    existing = model["existing_excess_cash_realization"]

    assert existing["qualifying_period_count"] == 0
    assert existing["realization_rate_range"] == {"low": 0, "base": 0, "high": 1}
    assert existing["amount_range"] == {"low": 0, "base": 0, "high": 142.6}
    assert existing["adopted_value"] == 0


def test_three_comparable_periods_use_median_and_include_zero_event_period() -> None:
    model = compute_cash_accessibility_model(_payload())
    existing = model["existing_excess_cash_realization"]

    assert [row["existing_cash_realization_rate"] for row in existing["history"]] == [0.1, 0, 0.3]
    assert existing["qualifying_period_count"] == 3
    assert existing["realization_rate_range"] == {"low": 0, "base": 0.1, "high": 1}
    assert existing["adopted_realization_rate"] == 0.1

    without_zero = _payload()
    without_zero["realization_periods"].pop(1)
    unqualified = compute_cash_accessibility_model(without_zero)["existing_excess_cash_realization"]
    assert unqualified["qualifying_period_count"] == 2
    assert unqualified["adopted_value"] == 0


def test_ordinary_dividends_change_future_retention_but_not_existing_cash() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    changed_payload = _payload()
    changed_payload["realization_periods"][1]["ordinary_dividend"] = 5
    changed = compute_cash_accessibility_model(changed_payload)

    for field in ("realization_rate_range", "amount_range", "adopted_value"):
        assert changed["existing_excess_cash_realization"][field] == baseline["existing_excess_cash_realization"][field]
    assert changed["future_retained_cash_realization"]["adopted_value"] != baseline["future_retained_cash_realization"]["adopted_value"]


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
    model = compute_cash_accessibility_model(payload)

    assert model["existing_excess_cash_realization"]["adopted_realization_rate"] == 0.2
    assert model["existing_excess_cash_realization"]["adopted_value"] == 28.52


def test_ineligible_and_unknown_funding_do_not_calibrate_existing_cash() -> None:
    debt_funded = _payload()
    debt_funded["realization_periods"][1]["extraordinary_events"] = [
        _event("special_dividend", 90, "debt_funded", "F:SPECIAL")
    ]
    debt_model = compute_cash_accessibility_model(debt_funded)
    period = debt_model["existing_excess_cash_realization"]["history"][1]
    assert period["eligible_extraordinary_realization"] == 0
    assert period["existing_cash_realization_rate"] == 0

    unknown_funded = _payload()
    unknown_funded["realization_periods"][1]["extraordinary_events"] = [
        _event("special_dividend", 90, "unknown", "F:SPECIAL")
    ]
    unknown_model = compute_cash_accessibility_model(unknown_funded)
    period = unknown_model["existing_excess_cash_realization"]["history"][1]
    assert period["existing_cash_calibration_qualified"] is False
    assert unknown_model["existing_excess_cash_realization"]["qualifying_period_count"] == 2
    assert unknown_model["existing_excess_cash_realization"]["adopted_value"] == 0


def test_future_retained_cash_has_a_distinct_destination_and_calibration() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    changed_payload = _payload()
    changed_payload["future_retained_cash"]["projected_amount"] = 160
    changed = compute_cash_accessibility_model(changed_payload)

    assert baseline["future_retained_cash_realization"]["adopted_realization_rate"] == 0.5
    assert baseline["future_retained_cash_realization"]["adopted_value"] == 40
    assert changed["future_retained_cash_realization"]["adopted_value"] == 80
    assert changed["existing_excess_cash_realization"] == baseline["existing_excess_cash_realization"]
    assert changed["related_party_receivable_realization"] == baseline["related_party_receivable_realization"]


def test_related_receivable_is_not_cash_and_only_collections_are_adopted() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    receivable = baseline["related_party_receivable_realization"]
    assert receivable["amount_range"] == {"low": 20, "base": 83, "high": 90}
    assert receivable["adopted_value"] == 20
    assert baseline["legal_cash_accessibility"]["adopted_value"] == 142.6

    older_payload = _payload()
    older_payload["related_party_receivables"][0].update({
        "aging_bucket": "over_three_years",
        "ecl_allowance": 30,
    })
    older = compute_cash_accessibility_model(older_payload)
    assert older["related_party_receivable_realization"]["amount_range"] == {
        "low": 20,
        "base": 27.5,
        "high": 70,
    }
    for component in (
        "legal_cash_accessibility",
        "existing_excess_cash_realization",
        "future_retained_cash_realization",
    ):
        assert older[component] == baseline[component]


def test_perturbations_change_only_the_economically_connected_outputs() -> None:
    baseline = compute_cash_accessibility_model(_payload())
    for entity_index, field, value in (
        (0, "restricted_or_regulatory_cash", 30),
        (2, "ordinary_share_economic_interest", 0.40),
        (1, "transfer_tax_friction_rate", 0.30),
    ):
        payload = _payload()
        payload["entity_cash_rows"][entity_index][field] = value
        changed = compute_cash_accessibility_model(payload)
        assert changed["legal_cash_accessibility"] != baseline["legal_cash_accessibility"]
        assert changed["existing_excess_cash_realization"]["amount_range"] != baseline["existing_excess_cash_realization"]["amount_range"]
        assert changed["future_retained_cash_realization"] == baseline["future_retained_cash_realization"]
        assert changed["related_party_receivable_realization"] == baseline["related_party_receivable_realization"]

    collected_payload = _payload()
    collected_payload["related_party_receivables"][0]["post_cutoff_collections"] = 40
    collected = compute_cash_accessibility_model(collected_payload)
    assert collected["related_party_receivable_realization"]["adopted_value"] == 40
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
    assert any("source_fact_ids_not_verified:F:NOT_VERIFIED" in item for item in result["findings"])

    payload = _payload()
    payload["realization_periods"][0]["evidence"] = "annual report page 10"
    result = validate_cash_accessibility_input(payload)
    assert result["state"] == "INVALID"
    assert "realization_periods[0].evidence_not_allowed" in result["findings"]


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
    assert "现金法律上限" in model["economic_conclusion"]
    assert "RMB 14.26 million" in model["economic_conclusion"]
    assert conclusions == model["reader_conclusions"]
    assert len(conclusions) == 4
    serialized = " ".join(conclusions)
    for token in ("schema", "VALID", "INVALID", "object_id", "P_LONG", "PRIMARY_ROUTE"):
        assert token.lower() not in serialized.lower()
    assert "法律上限" in serialized
    assert "关联方应收款" in serialized


def test_schema_is_parseable_and_names_the_canonical_model() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "cash_accessibility_model.schema.json").read_text(encoding="utf-8")
    )
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == "cash-accessibility-model.v1"
