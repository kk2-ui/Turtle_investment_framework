from __future__ import annotations

from copy import deepcopy

from scripts import judgment_training_decision_contract as contract
from tests.test_judgment_pit_forecast import _forecast, _universe_and_h1


def _contract(forecast: dict) -> dict:
    return {
        "schema_version": contract.SCHEMA_VERSION,
        "contract_id": "DC:SYNTHETIC:FORECAST:V1",
        "contract_version": 1,
        "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"],
        "cutoff_at": forecast["cutoff_at"],
        "decision_purpose": "HISTORICAL_TRAINING",
        "holding_horizon": {"minimum_years": 1, "maximum_years": 5},
        "permanent_loss_constraints": [{
            "constraint_id": "PLC:ONE", "condition": "Loss of ordinary-share cash access or operating continuity.",
            "required_treatment": "Keep the state as a conservative risk question, not a price target.",
        }],
        "decision_flip_questions": [{
            "question_id": "DQ:ONE", "statement": "Can the cutoff-visible operating state remain viable?",
            "decision_effect": "A negative answer retains a permanent-loss guardrail.",
        }],
        "evidence_budget": {
            "evidence_budget_id": "BUDGET:SYNTHETIC:H1:V1",
            "source_packet_refs": deepcopy(forecast["source_packet_refs"]),
        },
        "price_and_opportunity_cost_policy": "PROHIBITED_FOR_HISTORICAL_TRAINING",
        "outcome_access": "NONE",
        "roles": {
            "judgment_owner_id": "SYNTHETIC:JUDGMENT_OWNER",
            "independent_challenger_id": "SYNTHETIC:CHALLENGER",
            "outcome_custodian_id": "SYNTHETIC:CUSTODIAN",
        },
        "object_class": "DECISION_CONTRACT",
        "claim_class": "EX_ANTE_DECISION_SCOPE",
        "allowed_outputs": ["CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"],
    }


def test_training_decision_contract_is_ex_ante_closed_and_matches_one_forecast() -> None:
    universe, h1 = _universe_and_h1()
    forecast = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(forecast)
    assert contract.validate_training_decision_contract(decision_contract)["valid"]
    assert contract.validate_contract_for_forecast(decision_contract, forecast)["valid"]

    contaminated = deepcopy(decision_contract)
    contaminated["market_price"] = 400.0
    result = contract.validate_training_decision_contract(contaminated)
    assert not result["valid"]
    assert "decision_contract_contains_unapproved_field:market_price" in result["findings"]

    wrong_packet = deepcopy(decision_contract)
    wrong_packet["evidence_budget"]["source_packet_refs"][0]["receipt_id"] = "H1:OTHER"
    result = contract.validate_contract_for_forecast(wrong_packet, forecast)
    assert not result["valid"]
    assert "decision_contract.source_packet_must_match_forecast" in result["findings"]

    role_conflict = deepcopy(decision_contract)
    role_conflict["roles"]["independent_challenger_id"] = role_conflict["roles"]["judgment_owner_id"]
    result = contract.validate_training_decision_contract(role_conflict)
    assert not result["valid"]
    assert "decision_contract.roles_must_be_independent" in result["findings"]
