from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_round6_transfer_utility as round6


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
FREEZE_AT = "2026-08-27T03:00:00+00:00"


def _load(name: str) -> dict:
    return json.loads((BLOCK_DIR / name).read_text(encoding="utf-8"))


def _context() -> dict:
    return {
        "block": _load("04_industry_learning_block.json"),
        "roster_freeze": _load("04_pre_outcome_roster_freeze.json"),
        "prior_receipts": [_load(name) for name in round6.ROUND6_PRIOR_RECEIPT_FILES],
        "source_learning_completion": _load("36_round5_real_feedback_completion_receipt.json"),
    }


def _package() -> dict:
    return round6.build_real_preoutcome_package(**_context(), frozen_at=FREEZE_AT)


def _synthetic_settlement(package: dict) -> dict:
    contract = package["outcome_measurement_contract"]
    return {
        "settlement_id": "R6SETTLE:CN600801:FY2016:TEST",
        "company_id": package["selection"]["company_id"],
        "measurement_contract_ref": {
            "measurement_contract_id": contract["contract_set_id"],
            "measurement_contract_version": 3,
        },
        "cell_results": [
            {"cell_id": cell["cell_id"], "status": "UNKNOWN", "label": "UNKNOWN"}
            for cell in contract["atomic_cells"]
        ],
    }


def _utility_review(package: dict, settlement: dict) -> dict:
    dimensions = [
        "PERMANENT_LOSS_GUARDRAIL",
        "OWNER_CASH_ACCESS",
        "KEY_UNKNOWN_DISCOVERY",
        "RESEARCH_COST",
    ]
    evaluation = {
        "schema_version": "turtle-decision-utility-evaluation.v1",
        "evaluation_id": "DUEVAL:CN600801:20160427:R6:TEST",
        "pairing_id": package["decision_utility_pairing"]["pairing_id"],
        "evaluated_at": "2026-08-27T04:00:00+00:00",
        "reviewer_id": "ROLE:CEMENT:ROUND6:UTILITY_REVIEWER",
        "outcome_settlement_ref": settlement["settlement_id"],
        "dimension_findings": [
            {
                "dimension_id": dimension,
                "baseline_assessment": "NOT_DIAGNOSTIC",
                "enhanced_assessment": "NOT_DIAGNOSTIC",
                "rationale": "Synthetic UNKNOWN cells cannot establish material utility.",
            }
            for dimension in dimensions
        ],
        "holdout": {
            "training_company_ids": ["CN:600802"],
            "holdout_company_ids": ["CN:600801"],
            "training_cutoff_through": "2015-04-15T00:00:00+08:00",
            "holdout_cutoff_from": "2016-04-27T00:00:00+08:00",
        },
        "object_class": "DECISION_UTILITY_EVALUATION",
        "claim_class": "MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": round6.REVIEW_OUTPUTS,
    }
    cell_id = settlement["cell_results"][0]["cell_id"]
    return {
        "schema_version": round6.REVIEW_SCHEMA_VERSION,
        "review_id": "R6REVIEW:CN600801:20160427:TEST",
        "package_ref": package["package_id"],
        "utility_evaluation": evaluation,
        "settlement_ref": settlement["settlement_id"],
        "reviewer_id": evaluation["reviewer_id"],
        "reviewed_at": evaluation["evaluated_at"],
        "paired_claim_findings": [{
            "dimension": "control_and_scope",
            "baseline_assessment": "The aggregate question remains unresolved.",
            "enhanced_assessment": "The split cells remain locally UNKNOWN.",
            "economic_effect": "No material decision difference can be established.",
            "supporting_cell_ids": [cell_id],
            "prohibited_inference": "Do not infer management quality or method transfer.",
        }],
        "overall_verdict": "NOT_DIAGNOSTIC",
        "investor_effect": "The synthetic result does not change an enterprise judgment.",
        "unknowns_preserved": ["decision control", "issuer-product participation"],
        "limitations": ["Synthetic test fixture only."],
        "rights": deepcopy(round6.RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_TRANSFER_UTILITY_REVIEW",
        "claim_class": "PAIRED_MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": round6.REVIEW_OUTPUTS,
    }


def test_round6_target_is_rank1_different_company_and_outcome_blind() -> None:
    result = round6.derive_transfer_target(**_context())
    assert result["valid"], result["findings"]
    selection = result["selection"]
    assert selection["selected_rank"] == 1
    assert selection["transition_id"] == "CCR:600801:20160427:20170412"
    assert selection["company_id"] == "CN:600801"
    assert selection["source_learning_company_id"] == "CN:600802"
    assert selection["selection_used_outcome"] is False
    assert selection["selection_used_source_convenience"] is False
    assert selection["method_unseen_on_target"] is True


def test_committed_preoutcome_artifacts_replay_from_the_builder() -> None:
    artifacts = round6.build_real_preoutcome_artifacts(BLOCK_DIR, frozen_at=FREEZE_AT)
    for name, expected in artifacts.items():
        assert _load(name) == expected
    receipt = artifacts["39_round6_preoutcome_validation_receipt.json"]
    assert receipt["validation_status"] == "PRE_OUTCOME_VALID"
    assert receipt["outcome_content_read"] is False
    assert receipt["outcome_source_access_state"] == "SEALED_UNTIL_PREOUTCOME_COMMIT"


def test_preoutcome_package_rejects_outcome_or_source_convenience_selection() -> None:
    package = _package()
    for field in ("selection_used_outcome", "selection_used_source_convenience"):
        changed = deepcopy(package)
        changed["selection"][field] = True
        result = round6.validate_preoutcome_package(changed, **_context())
        assert not result["valid"]
        assert "round6_preoutcome.selection_must_be_mechanically_derived" in result["findings"]


def test_baseline_and_enhanced_use_identical_evidence_but_different_questions() -> None:
    package = _package()
    baseline = package["baseline_view"]
    enhanced = package["enhanced_view"]
    budget = package["decision_contract"]["evidence_budget"]
    assert baseline["evidence_budget_id"] == enhanced["evidence_budget_id"] == budget["evidence_budget_id"]
    assert baseline["source_packet_refs"] == enhanced["source_packet_refs"] == budget["source_packet_refs"]
    assert baseline["fact_ids"] == enhanced["fact_ids"]
    assert baseline["method_id"] == round6.BASELINE_METHOD_ID
    assert enhanced["method_id"] == round6.ENHANCED_METHOD_ID
    assert baseline["expected_outcome_cell_ids"][0].endswith(":ACTION_PROGRESS")
    assert {
        "CELL:600801:20160427:DECISION_CONTROL",
        "CELL:600801:20160427:ISSUER_PRODUCT_PARTICIPATION",
        "CELL:600801:20160427:CONSOLIDATION_SCOPE",
        "CELL:600801:20160427:CUSTOMER_RESPONSE",
    }.issubset(enhanced["expected_outcome_cell_ids"])


def test_missing_or_mismatched_fields_stay_local_and_grant_no_downstream_rights() -> None:
    package = _package()
    cells = package["outcome_measurement_contract"]["atomic_cells"]
    assert all(cell["unknown_rule"]["label"] == "UNKNOWN" for cell in cells)
    assert all(cell["mismatch_rule"]["propagation"] == "LOCAL_ONLY" for cell in cells)
    assert all(cell["mismatch_rule"]["dependent_cell_ids"] == [] for cell in cells)
    assert set(package["rights"].values()) == {"NOT_AUTHORIZED"}
    assert "H2" not in json.dumps(package, ensure_ascii=False)


def test_review_contract_rejects_management_quality_or_method_transfer_overclaim() -> None:
    package = _package()
    settlement = _synthetic_settlement(package)
    review = _utility_review(package, settlement)
    assert round6.validate_utility_review(review, package=package, settlement=settlement)["valid"]

    overclaim = deepcopy(review)
    overclaim["management_quality"] = "PROVEN_HIGH"
    result = round6.validate_utility_review(overclaim, package=package, settlement=settlement)
    assert not result["valid"]
    assert "round6_review_contains_unapproved_field:management_quality" in result["findings"]

    overclaim = deepcopy(review)
    overclaim["rights"]["method_transfer"] = "AUTHORIZED"
    result = round6.validate_utility_review(overclaim, package=package, settlement=settlement)
    assert not result["valid"]
    assert "round6_review.rights_or_outputs_invalid" in result["findings"]
