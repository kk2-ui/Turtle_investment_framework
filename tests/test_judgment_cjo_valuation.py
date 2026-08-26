from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import judgment_cjo_valuation as valuation


def _cjo(*, permission: str = "INVESTMENT_INPUT") -> dict:
    return {
        "cjo_id": "CJO:SYNTHETIC:VALUATION:V1",
        "model_id": "ESM:SYNTHETIC:VALUATION:V1",
        "state": {
            "lane": "ENTERPRISE_MODEL", "lifecycle": "FROZEN", "resolution": "SELECTIVE_SUPPORT",
            "permission": permission, "frozen_at": "2025-12-31T23:59:59+00:00",
        },
        "scope_bridge_id": "BRIDGE:SYNTHETIC:VALUATION",
        "owner_cash_bridge": {
            "status": "CLOSED", "ordinary_share_access_status": "CLOSED", "permanent_loss_status": "ASSESSED",
            "scope_bridge_id": "BRIDGE:SYNTHETIC:VALUATION", "evidence_ref": "SOURCE:SYNTHETIC:D4",
        },
        "driver_register": [{
            "driver_id": "DRIVER:SYNTHETIC:VALUATION", "responsibility_unit_id": "RU:SYNTHETIC",
            "scope_bridge_id": "BRIDGE:SYNTHETIC:VALUATION", "normalized_earnings_delta": 0.0, "owner_cash_delta": 0.0,
        }],
    }


def _snapshot(cjo: dict) -> dict:
    return {
        "schema_version": valuation.SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": "VALUATION-SNAPSHOT:SYNTHETIC:V1",
        "cjo_ref": {
            "cjo_id": cjo["cjo_id"], "model_id": cjo["model_id"], "frozen_at": cjo["state"]["frozen_at"],
        },
        "financial_contract": {
            "base_normalized_earnings": 64.0, "base_owner_cash": 50.0, "share_count": 1.0,
            "required_return": 0.10, "market_price": 400.0, "holding_years": 3, "annual_distribution": 5.0,
        },
        "outcome_contract": {
            "operating_window_ends_at": "2028-12-31T23:59:59+00:00",
            "market_window_ends_at": "2028-12-31T23:59:59+00:00",
            "settlement_policy": "SEPARATE_OPERATING_VALUE_AND_MARKET",
            "expected_dimensions": list(valuation.OUTCOME_DIMENSIONS),
        },
        "roles": {
            "valuation_owner_id": "SYNTHETIC:VALUATION:OWNER",
            "independent_challenger_id": "SYNTHETIC:VALUATION:CHALLENGER",
            "outcome_custodian_id": "SYNTHETIC:VALUATION:CUSTODIAN",
        },
        "frozen_at": "2026-01-01T00:00:00+00:00",
        "object_class": "CJO_VALUATION_RETURN_SNAPSHOT",
        "claim_class": "CJO_DERIVED_VALUATION_IDENTITY",
        "allowed_outputs": list(valuation.VALUATION_ALLOWED_OUTPUTS),
    }


def _source(name: str) -> dict:
    return {
        "source_id": f"SOURCE:SYNTHETIC:OUTCOME:{name}",
        "source_available_at": "2029-03-31T00:00:00+00:00",
        "field_ref": f"Synthetic official outcome statement p{name}.",
    }


def _settlement(snapshot: dict) -> dict:
    return {
        "schema_version": valuation.SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": "VALUATION-SETTLEMENT:SYNTHETIC:V1",
        "snapshot_id": snapshot["snapshot_id"],
        "settled_at": "2029-04-01T00:00:00+00:00",
        "outcome_custodian_id": snapshot["roles"]["outcome_custodian_id"],
        "operating_result": {
            "status": "OBSERVED",
            "normalized_earnings": {"value": 60.0, "source": _source("NORMALIZED")},
            "owner_cash": {"value": 45.0, "source": _source("OWNER-CASH")},
        },
        "permanent_loss_result": {"status": "OBSERVED_NO", "source": _source("PERMANENT-LOSS")},
        "market_result": {
            "status": "OBSERVED", "terminal_price": 450.0, "terminal_price_source": _source("PRICE"),
            "annual_cash_flows": [
                {"year_index": year, "amount": 5.0, "source": _source(f"DIVIDEND-{year}")}
                for year in range(1, 4)
            ],
        },
        "object_class": "CJO_VALUATION_RETURN_SETTLEMENT",
        "claim_class": "SEPARATE_OPERATING_VALUE_MARKET_RECONCILIATION",
        "allowed_outputs": list(valuation.VALUATION_ALLOWED_OUTPUTS),
    }


def test_cjo_valuation_snapshot_requires_investment_ready_cjo_and_preserves_propagation_identity() -> None:
    cjo = _cjo()
    snapshot = _snapshot(cjo)
    compiled = valuation.compile_valuation_return_snapshot(snapshot, cjo=cjo)

    assert compiled["propagation"]["price_implied_owner_cash"] == pytest.approx(51.585, abs=0.001)
    assert compiled["propagation"]["expectation_gap"] < 0
    assert compiled["snapshot"]["allowed_outputs"] == ["VALUATION_EVALUATION_ONLY", "RESEARCH_AGENDA"]

    teaching_cjo = _cjo(permission="TEACHING_ONLY")
    rejected = valuation.validate_valuation_return_snapshot(snapshot, cjo=teaching_cjo)
    assert not rejected["valid"]
    assert "valuation_snapshot.requires_frozen_investment_input_cjo" in rejected["findings"]

    schema = json.loads(Path("schemas/judgment_cjo_valuation.schema.json").read_text(encoding="utf-8"))
    assert schema["$defs"]["snapshot"]["additionalProperties"] is False
    assert schema["$defs"]["settlement"]["additionalProperties"] is False


def test_valuation_settlement_separates_operating_owner_cash_value_and_market_return() -> None:
    cjo = _cjo()
    snapshot = _snapshot(cjo)
    settlement = _settlement(snapshot)
    result = valuation.validate_valuation_return_settlement(settlement, snapshot=snapshot, cjo=cjo)

    assert result["valid"], result["findings"]
    assert result["operating_reconciliation"] == {
        "status": "OBSERVED",
        "expected_normalized_earnings": 64.0,
        "actual_normalized_earnings": 60.0,
        "normalized_earnings_delta": -4.0,
        "expected_owner_cash": 50.0,
        "actual_owner_cash": 45.0,
        "owner_cash_delta": -5.0,
    }
    assert result["valuation_reconciliation"]["status"] == "OBSERVED_OWNER_CASH_IDENTITY"
    assert result["valuation_reconciliation"]["owner_cash_value_delta"] < 0
    assert result["market_reconciliation"]["status"] == "OBSERVED"
    assert result["market_reconciliation"]["annualized_realized_return"] is not None
    assert result["learning_authorization"] == "CANDIDATE_ONLY"
    assert cjo == _cjo(), "price and outcome results must never rewrite the CJO"


def test_valuation_settlement_rejects_early_or_mixed_outcomes_and_keeps_censoring_explicit() -> None:
    cjo = _cjo()
    snapshot = _snapshot(cjo)
    settlement = _settlement(snapshot)

    early_source = deepcopy(settlement)
    early_source["market_result"]["terminal_price_source"]["source_available_at"] = "2025-12-31T23:59:59+00:00"
    result = valuation.validate_valuation_return_settlement(early_source, snapshot=snapshot, cjo=cjo)
    assert not result["valid"]
    assert "valuation_settlement.market_result.terminal_price_source.source_must_follow_snapshot_freeze" in result["findings"]

    mixed = deepcopy(settlement)
    mixed["operating_result"]["owner_cash"] = None
    result = valuation.validate_valuation_return_settlement(mixed, snapshot=snapshot, cjo=cjo)
    assert not result["valid"]
    assert "valuation_settlement.operating_result.owner_cash_must_be_object" in result["findings"]

    censored = deepcopy(settlement)
    censored["operating_result"] = {"status": "CENSORED", "normalized_earnings": None, "owner_cash": None}
    censored["permanent_loss_result"] = {"status": "CENSORED", "source": None}
    censored["market_result"] = {"status": "CENSORED", "terminal_price": None, "terminal_price_source": None, "annual_cash_flows": None}
    result = valuation.validate_valuation_return_settlement(censored, snapshot=snapshot, cjo=cjo)
    assert result["valid"], result["findings"]
    assert result["operating_reconciliation"] == {"status": "CENSORED"}
    assert result["valuation_reconciliation"] == {"status": "CENSORED_OWNER_CASH_IDENTITY"}
    assert result["market_reconciliation"] == {"status": "CENSORED"}
