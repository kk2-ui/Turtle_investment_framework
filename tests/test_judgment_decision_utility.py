from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_episode as episode_module
from scripts import judgment_decision_utility as utility
from scripts import judgment_training_decision_contract as contract_module


COMPANY_ID = "CN:601933"
ISSUER_ID = "SH:601933"
CUTOFF_AT = "2019-05-01T00:00:00+08:00"
BASELINE_METHOD_ID = "METHOD:RETAIL_TREND_BASELINE:V1"
ENHANCED_METHOD_ID = "METHOD:RETAIL_ENTERPRISE_ENHANCED:V1"
LOCATOR_IDS = ["LOCATOR:RETAIL:FY2018:OPERATIONS", "LOCATOR:RETAIL:FY2018:CASH"]


def _contract() -> dict:
    return {
        "schema_version": contract_module.SCHEMA_VERSION,
        "contract_id": "DC:CN601933:20190501:V1",
        "contract_version": 1,
        "company_id": COMPANY_ID,
        "issuer_id": ISSUER_ID,
        "cutoff_at": CUTOFF_AT,
        "decision_purpose": "HISTORICAL_TRAINING",
        "holding_horizon": {"minimum_years": 1, "maximum_years": 5},
        "permanent_loss_constraints": [{
            "constraint_id": "PLC:RETAIL:ONE",
            "condition": "Store economics or cash access deteriorates beyond an ordinary operating setback.",
            "required_treatment": "Keep permanent loss unknown until the declared outcome window settles.",
        }],
        "decision_flip_questions": [{
            "question_id": "DQ:RETAIL:ONE",
            "statement": "Can store expansion preserve unit economics and cash funding capacity?",
            "decision_effect": "A negative answer weakens the enterprise judgment without creating an investment action.",
        }],
        "evidence_budget": {
            "evidence_budget_id": "BUDGET:CN601933:20190501:FY2018",
            "source_packet_refs": [{"receipt_id": "SP:CN601933:FY2018", "receipt_version": 1}],
        },
        "price_and_opportunity_cost_policy": "PROHIBITED_FOR_HISTORICAL_TRAINING",
        "outcome_access": "NONE",
        "roles": {
            "judgment_owner_id": "AGENT:RETAIL:JUDGMENT",
            "independent_challenger_id": "AGENT:RETAIL:CHALLENGER",
            "outcome_custodian_id": "AGENT:RETAIL:CUSTODIAN",
        },
        "object_class": "DECISION_CONTRACT",
        "claim_class": "EX_ANTE_DECISION_SCOPE",
        "allowed_outputs": list(contract_module.HISTORICAL_ALLOWED_OUTPUTS),
    }


def _episode(contract: dict, *, role: str, method_id: str) -> dict:
    company_id = contract["company_id"]
    issuer_id = contract["issuer_id"]
    question_ids = ["CONTEXT", "ACTION", "ECONOMICS", "RISK"]
    domains = [
        "LIFECYCLE", "ORGANIZATION", "OPERATIONS", "CUSTOMER",
        "COMPETITION", "CASH", "PERMANENT_LOSS", "CAPITAL_ALLOCATION",
    ]
    states = ["OBSERVED", "UNKNOWN", "INFERRED", "UNKNOWN", "INFERRED", "OBSERVED", "UNKNOWN", "NOT_APPLICABLE"]
    claims = []
    for index, (dimension, domain, state) in enumerate(zip(utility.DIMENSIONS, domains, states, strict=True)):
        claims.append({
            "claim_id": f"CLAIM:{role}:{dimension}",
            "question_id": f"Q:{question_ids[index // 2]}",
            "method_id": method_id,
            "judgment_dimension": dimension,
            "claim_scope": {
                "issuer_ids": [issuer_id],
                "product_or_service_ids": [],
                "plant_ids": [],
                "channel_ids": ["CHANNEL:RETAIL:STORE"],
                "region_ids": ["REGION:CN:RETAIL"],
                "arena_ids": ["ARENA:CN:REGIONAL_SUPERMARKET"],
            },
            "domain": domain,
            "statement": f"{dimension} remains bounded by the FY2018 retail evidence packet.",
            "cell_status": state,
            "admission_level": "E0_CONTEXT",
            "evidence_refs": ["SP:CN601933:FY2018"] if state in {"OBSERVED", "INFERRED"} else [],
            "evidence_locator_refs": list(LOCATOR_IDS) if state in {"OBSERVED", "INFERRED"} else [],
            "dependent_outcome_cell_ids": [],
        })
    questions = []
    for question_index, question_id in enumerate(question_ids):
        questions.append({
            "question_id": f"Q:{question_id}",
            "role": "PRIMARY" if question_index == 0 else "SUPPORTING",
            "question": f"What does the cutoff evidence establish for {question_id.lower()}?",
            "claim_ids": [claim["claim_id"] for claim in claims[question_index * 2:(question_index + 1) * 2]],
        })
    return {
        "schema_version": episode_module.SCHEMA_VERSION,
        "episode_id": f"EJE:{company_id}:{role}:V1",
        "company_id": company_id,
        "issuer_id": issuer_id,
        "cutoff_at": contract["cutoff_at"],
        "decision_contract_ref": {
            "contract_id": contract["contract_id"], "contract_version": contract["contract_version"],
        },
        "component_refs": [{
            "component_type": "ENTERPRISE_CONTEXT_SNAPSHOT",
            "component_id": "CONTEXT:CN601933:20190501",
            "component_version": "1",
            "admission_level": "E0_CONTEXT",
            "read_only": True,
        }],
        "question_set": questions,
        "claims": claims,
        "mechanism_threads": [],
        "outcome_cells": [{
            "outcome_cell_id": "CELL:CN601933:FY2019:OPERATING_CASH",
            "dimension": "CASH",
            "status": "UNKNOWN",
            "measurement_contract_ref": "MC:CN601933:FY2019:OPERATING_CASH",
            "custodian_receipt_ref": "",
        }],
        "roles": deepcopy(contract["roles"]),
        "object_class": "ENTERPRISE_JUDGMENT_EPISODE_MANIFEST",
        "claim_class": "COMPOSITE_ENTERPRISE_JUDGMENT",
        "allowed_outputs": list(episode_module.ALLOWED_OUTPUTS),
    }


def _episodes(
    contract: dict, *, baseline_method_id: str = BASELINE_METHOD_ID,
    enhanced_method_id: str = ENHANCED_METHOD_ID,
) -> tuple[dict, dict]:
    return (
        _episode(contract, role="BASELINE", method_id=baseline_method_id),
        _episode(contract, role="ENHANCED", method_id=enhanced_method_id),
    )


def _pairing(
    contract: dict, baseline: dict, enhanced: dict, *, control: bool = False,
    baseline_method_id: str = BASELINE_METHOD_ID, enhanced_method_id: str = ENHANCED_METHOD_ID,
) -> dict:
    value = {
        "schema_version": utility.CONTROL_PAIRING_SCHEMA_VERSION if control else utility.PAIRING_SCHEMA_VERSION,
        "pairing_id": "UTILITY:PAIR:CN601933:20190501:V2",
        "decision_contract_ref": {
            "contract_id": contract["contract_id"], "contract_version": contract["contract_version"],
        },
        "baseline_episode_id": baseline["episode_id"],
        "enhanced_episode_id": enhanced["episode_id"],
        "baseline_method_id": baseline_method_id,
        "enhanced_method_id": enhanced_method_id,
        "baseline_research_cost_hours": 2.0,
        "enhanced_research_cost_hours": 3.5,
        "frozen_at": "2019-05-02T00:00:00+08:00",
        "object_class": "DECISION_UTILITY_PAIRING",
        "claim_class": "SAME_CONTRACT_METHOD_ABLATION",
        "allowed_outputs": list(utility.ALLOWED_OUTPUTS),
    }
    return value


def _evaluation(pairing: dict, contract: dict) -> dict:
    assessments = {
        "IMPLEMENTED_MANAGEMENT_ACTION": "UNKNOWN",
        "CUSTOMER_COMPETITION_RESPONSE": "NOT_DIAGNOSTIC",
    }
    return {
        "schema_version": utility.EVALUATION_SCHEMA_VERSION,
        "evaluation_id": "UTILITY:EVAL:CN601933:20190501:V2",
        "pairing_id": pairing["pairing_id"],
        "evaluated_at": "2020-05-02T00:00:00+08:00",
        "reviewer_id": "AGENT:RETAIL:INDEPENDENT_REVIEWER",
        "outcome_settlement_ref": "SETTLEMENT:CN601933:FY2019:V1",
        "dimension_findings": [{
            "dimension_id": dimension,
            "baseline_assessment": "NO_DIFFERENCE",
            "enhanced_assessment": assessments.get(dimension, "MATERIAL_IMPROVEMENT"),
            "supporting_cell_ids": ["CELL:CN601933:FY2019:OPERATING_CASH"],
            "rationale": "The dimension is reviewed independently; local uncertainty does not reject the pair.",
        } for dimension in utility.DIMENSIONS],
        "holdout": {
            "training_company_ids": ["CN:002697"],
            "holdout_company_ids": [contract["company_id"]],
            "training_cutoff_through": "2018-12-31T00:00:00+08:00",
            "holdout_cutoff_from": "2019-01-01T00:00:00+08:00",
        },
        "object_class": "DECISION_UTILITY_EVALUATION",
        "claim_class": "MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": list(utility.ALLOWED_OUTPUTS),
    }


def test_non_cement_pair_uses_only_validated_canonical_episode_references() -> None:
    contract = _contract()
    baseline, enhanced = _episodes(contract)
    assert episode_module.validate_episode_manifest(baseline, decision_contract=contract)["valid"]
    assert episode_module.validate_episode_manifest(enhanced, decision_contract=contract)["valid"]
    pairing = _pairing(contract, baseline, enhanced)

    result = utility.validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline, enhanced_episode=enhanced,
    )

    assert result["valid"], result["findings"]
    assert "baseline" not in pairing and "enhanced" not in pairing and "judgment_cells" not in pairing
    schema = json.loads(Path("schemas/judgment_decision_utility.schema.json").read_text(encoding="utf-8"))
    assert schema["$defs"]["pairing"]["additionalProperties"] is False
    assert "decision" not in schema["$defs"]

    legacy = deepcopy(pairing)
    legacy["baseline"] = {"judgment_cells": []}
    legacy["enhanced"] = {"judgment_cells": []}
    result = utility.validate_decision_utility_pairing(
        legacy, contract=contract, baseline_episode=baseline, enhanced_episode=enhanced,
    )
    assert not result["valid"]
    assert "decision_utility_pairing_contains_unapproved_field:baseline" in result["findings"]
    assert "decision_utility_pairing_contains_unapproved_field:enhanced" in result["findings"]


def test_pair_rejects_company_cutoff_and_frozen_evidence_locator_mismatch() -> None:
    contract = _contract()
    baseline, enhanced = _episodes(contract)
    pairing = _pairing(contract, baseline, enhanced)

    wrong_company = deepcopy(enhanced)
    wrong_company["company_id"] = "CN:002697"
    result = utility.validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline, enhanced_episode=wrong_company,
    )
    assert not result["valid"]
    assert "decision_utility_pairing.episodes_company_id_must_match" in result["findings"]

    wrong_cutoff = deepcopy(enhanced)
    wrong_cutoff["cutoff_at"] = "2019-05-02T00:00:00+08:00"
    result = utility.validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline, enhanced_episode=wrong_cutoff,
    )
    assert not result["valid"]
    assert "decision_utility_pairing.episodes_cutoff_at_must_match" in result["findings"]

    wrong_budget = deepcopy(enhanced)
    wrong_budget["claims"][0]["evidence_locator_refs"] = ["LOCATOR:UNDECLARED:FY2018"]
    result = utility.validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline, enhanced_episode=wrong_budget,
    )
    assert not result["valid"]
    assert "decision_utility_pairing.episodes_must_use_same_frozen_evidence_locator_set" in result["findings"]


def test_local_unknown_is_comparable_but_missing_dimension_or_outcome_access_is_not() -> None:
    contract = _contract()
    baseline, enhanced = _episodes(contract)
    pairing = _pairing(contract, baseline, enhanced)
    assert any(claim["cell_status"] == "UNKNOWN" for claim in enhanced["claims"])
    assert utility.validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline, enhanced_episode=enhanced,
    )["valid"]

    missing = deepcopy(enhanced)
    missing["claims"].pop()
    missing["question_set"][-1]["claim_ids"].pop()
    result = utility.validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline, enhanced_episode=missing,
    )
    assert not result["valid"]
    assert "decision_utility_pairing.enhanced_episode.must_cover_each_judgment_dimension_once" in result["findings"]

    contaminated = deepcopy(enhanced)
    contaminated["outcome_cells"][0].update({"status": "OBSERVED", "custodian_receipt_ref": "CUSTODY:FY2019"})
    result = utility.validate_decision_utility_pairing(
        pairing, contract=contract, baseline_episode=baseline, enhanced_episode=contaminated,
    )
    assert not result["valid"]
    assert "decision_utility_pairing.enhanced_episode.outcome_must_remain_sealed_before_pairing" in result["findings"]


def test_independent_review_preserves_local_unknown_and_candidate_only_authority() -> None:
    contract = _contract()
    baseline, enhanced = _episodes(contract)
    pairing = _pairing(contract, baseline, enhanced)
    evaluation = _evaluation(pairing, contract)

    result = utility.validate_decision_utility_evaluation(
        evaluation, pairing=pairing, contract=contract,
        baseline_episode=baseline, enhanced_episode=enhanced,
    )

    assert result["valid"], result["findings"]
    assert result["learning_authorization"] == "CANDIDATE_ONLY"
    assert {finding["enhanced_assessment"] for finding in evaluation["dimension_findings"]} >= {
        "UNKNOWN", "NOT_DIAGNOSTIC",
    }
    unbound = deepcopy(evaluation)
    unbound["dimension_findings"][0]["supporting_cell_ids"] = ["CELL:UNFROZEN"]
    result = utility.validate_decision_utility_evaluation(
        unbound, pairing=pairing, contract=contract,
        baseline_episode=baseline, enhanced_episode=enhanced,
    )
    assert not result["valid"]
    assert "decision_utility_evaluation.dimension_findings[0].supporting_cell_ids_invalid" in result["findings"]
    conflicted = deepcopy(evaluation)
    conflicted["reviewer_id"] = contract["roles"]["judgment_owner_id"]
    result = utility.validate_decision_utility_evaluation(
        conflicted, pairing=pairing, contract=contract,
        baseline_episode=baseline, enhanced_episode=enhanced,
    )
    assert not result["valid"]
    assert "decision_utility_evaluation.reviewer_must_be_independent_of_contract_roles" in result["findings"]
