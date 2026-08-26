from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import judgment_decision_utility as utility
from tests.test_judgment_pit_forecast import _forecast, _universe_and_h1
from tests.test_judgment_training_decision_contract import _contract


def _pairing(contract: dict) -> dict:
    budget = contract["evidence_budget"]
    def decision(method: str, status: str, unknowns: list[str], cost: float) -> dict:
        return {"method_id": method, "decision_status": status, "material_unknown_ids": unknowns, "evidence_budget_id": budget["evidence_budget_id"], "source_packet_refs": deepcopy(budget["source_packet_refs"]), "research_cost_hours": cost}
    return {"schema_version": utility.PAIRING_SCHEMA_VERSION, "pairing_id": "UTILITY:PAIR:SYNTHETIC:V1", "decision_contract_ref": {"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]}, "baseline": decision("METHOD:BASELINE", "PASS", ["UNKNOWN:CASH"], 2.0), "enhanced": decision("METHOD:ENHANCED", "RESEARCH", ["UNKNOWN:CASH", "UNKNOWN:PERMANENT_LOSS"], 3.0), "frozen_at": "2021-01-02T00:00:00+00:00", "object_class": "DECISION_UTILITY_PAIRING", "claim_class": "SAME_CONTRACT_METHOD_ABLATION", "allowed_outputs": list(utility.ALLOWED_OUTPUTS)}


def _evaluation(pairing: dict) -> dict:
    return {"schema_version": utility.EVALUATION_SCHEMA_VERSION, "evaluation_id": "UTILITY:EVAL:SYNTHETIC:V1", "pairing_id": pairing["pairing_id"], "evaluated_at": "2023-01-02T00:00:00+00:00", "reviewer_id": "SYNTHETIC:INDEPENDENT:REVIEWER", "outcome_settlement_ref": "SETTLEMENT:SYNTHETIC:V1", "dimension_findings": [{"dimension_id": dimension, "baseline_assessment": "NO_DIFFERENCE", "enhanced_assessment": "MATERIAL_IMPROVEMENT" if dimension != "RESEARCH_COST" else "NO_DIFFERENCE", "rationale": "Qualitative paired review; no aggregate score or automatic release."} for dimension in utility.DIMENSIONS], "holdout": {"training_company_ids": ["CN:TRAINING"], "holdout_company_ids": ["CN:HOLDOUT"], "training_cutoff_through": "2020-12-31T00:00:00+00:00", "holdout_cutoff_from": "2021-01-01T00:00:00+00:00"}, "object_class": "DECISION_UTILITY_EVALUATION", "claim_class": "MATERIAL_DECISION_UTILITY_REVIEW", "allowed_outputs": list(utility.ALLOWED_OUTPUTS)}


def test_same_contract_pairing_and_dual_axis_holdout_only_produce_candidate_utility_learning() -> None:
    universe, h1 = _universe_and_h1()
    contract = _contract(_forecast(universe, h1, universe["members"][0]["company_id"]))
    pairing = _pairing(contract)
    assert utility.validate_decision_utility_pairing(pairing, contract=contract)["valid"]
    result = utility.validate_decision_utility_evaluation(_evaluation(pairing), pairing=pairing, contract=contract)
    assert result["valid"], result["findings"]
    assert result["learning_authorization"] == "CANDIDATE_ONLY"
    schema = json.loads(Path("schemas/judgment_decision_utility.schema.json").read_text(encoding="utf-8"))
    assert schema["$defs"]["pairing"]["additionalProperties"] is False


def test_pairing_rejects_budget_drift_and_evaluation_rejects_missing_dimension_or_bad_holdout() -> None:
    universe, h1 = _universe_and_h1()
    contract = _contract(_forecast(universe, h1, universe["members"][0]["company_id"]))
    pairing = _pairing(contract)
    drift = deepcopy(pairing); drift["enhanced"]["evidence_budget_id"] = "OTHER"
    result = utility.validate_decision_utility_pairing(drift, contract=contract)
    assert not result["valid"] and "decision_utility_pairing.enhanced.must_use_same_frozen_evidence_budget" in result["findings"]
    evaluation = _evaluation(pairing); evaluation["dimension_findings"].pop(); evaluation["holdout"]["holdout_company_ids"] = ["CN:TRAINING"]
    result = utility.validate_decision_utility_evaluation(evaluation, pairing=pairing, contract=contract)
    assert not result["valid"]
    assert "decision_utility_evaluation.must_cover_each_material_dimension_once" in result["findings"]
    assert "decision_utility_evaluation.holdout_company_axis_invalid" in result["findings"]
