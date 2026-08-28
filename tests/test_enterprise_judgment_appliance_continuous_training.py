from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_appliance_continuous_training as training


ROOT = Path(__file__).resolve().parents[1]
ROUND10 = ROOT / "docs" / "development" / "research" / "industry_learning_blocks" / "CN_APPLIANCE_ROUND10_V2_POSTOUTCOME"
ARTIFACT = ROOT / "docs" / "development" / "research" / "industry_learning_blocks" / "CN_APPLIANCE_CONTINUOUS_TRAINING_V1" / "CN002032_20180930_PREOUTCOME_FREEZE_RECEIPT.json"


def _round10_inputs():
    return (
        json.loads((ROUND10 / "02_external_method_review.json").read_text()),
        json.loads((ROUND10 / "03_batch_completion_receipt.json").read_text()),
    )


def _objects():
    review, completion = _round10_inputs()
    candidate = training.build_curriculum_candidate(review, completion)
    roster = training.build_roster()
    episode = training.build_preoutcome_episode(candidate, roster)
    return candidate, roster, episode


def test_round10_negative_result_compiles_one_future_only_curriculum_candidate():
    candidate, _, _ = _objects()
    result = training.validate_curriculum_candidate(candidate)
    assert result["valid"], result["findings"]
    assert candidate["round10_conclusion_preserved"] == "NO_MATERIAL_UTILITY"
    assert candidate["automatic_method_advantage_count"] == 0
    assert candidate["rights"] == training.RIGHTS


def test_roster_uses_role_company_cutoff_exposure_not_company_blacklist():
    _, roster, _ = _objects()
    result = training.validate_roster(roster)
    assert result["valid"], result["findings"]
    first = roster["candidate_order"][0]
    assert roster["selection_basis"] == "ROLE_X_COMPANY_X_CUTOFF_ACTUAL_INPUT_EXPOSURE"
    assert roster["company_level_blacklist_policy"].startswith("PROHIBITED")
    assert first["company_id"] == "CN:002032"
    assert first["cutoff_at"] == training.CUTOFF_AT
    assert first["actual_input_exposure"] == "CUTOFF_BEFORE_SOURCE_ONLY"
    assert first["preoutcome_role_ids"] == [training.CURATOR_ID, training.FORECASTER_ID]
    assert first["role_independence"] == "SEQUENTIAL_FUNCTIONAL_PARTITION_NOT_HOLDOUT"


def test_supor_episode_freezes_product_boundary_and_existing_minimal_contracts():
    candidate, roster, episode = _objects()
    result = training.validate_preoutcome_episode(episode, curriculum_candidate=candidate, roster=roster)
    assert result["valid"], result["findings"]
    assert episode["fair_baseline"]["fact_refs"] == episode["cumulative_enhanced"]["fact_refs"]
    assert episode["fair_baseline"]["treatment"] == "CONTINUE_OPERATING_UNDERWRITING"
    assert episode["cumulative_enhanced"]["treatment"] == "CONDITIONAL_PRODUCT_QUALITY_UNDERWRITING"
    metrics = [row["measurement_contract"]["metric_id"] for row in episode["minimal_field_chains"]]
    assert metrics == [
        "CONSOLIDATED_REVENUE_RMB",
        "PRODUCT_REVENUE_RMB:电锅类",
        "CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
    ]
    assert episode["outcome_access"] == {"authorized": False, "content_read": False, "custodian_started": False}
    assert episode["rights"] == training.RIGHTS


def test_product_boundary_or_outcome_contamination_rejects_without_widening_other_fields():
    candidate, roster, episode = _objects()
    drift = deepcopy(episode)
    drift["minimal_field_chains"][1]["measurement_contract"]["responsibility_boundary"] = "LISTED_ISSUER_CONSOLIDATED:CN002032"
    result = training.validate_preoutcome_episode(drift, curriculum_candidate=candidate, roster=roster)
    assert not result["valid"]
    assert any("responsibility_boundary" in finding for finding in result["findings"])

    contaminated = deepcopy(episode)
    contaminated["outcome_label"] = "INCREASE"
    result = training.validate_preoutcome_episode(contaminated, curriculum_candidate=candidate, roster=roster)
    assert not result["valid"]
    assert any("outcome_label_forbidden_preoutcome" in finding for finding in result["findings"])


def test_committed_freeze_receipt_matches_canonical_episode_identity():
    candidate, roster, episode = _objects()
    receipt = json.loads(ARTIFACT.read_text())
    assert receipt["episode_id"] == episode["episode_id"]
    assert receipt["curriculum_candidate_id"] == candidate["curriculum_candidate_id"]
    assert receipt["roster_id"] == roster["roster_id"]
    assert receipt["company_id"] == episode["company_id"]
    assert receipt["cutoff_at"] == episode["cutoff_at"]
    assert receipt["source_id"] == episode["source_packet"]["source"]["source_id"]
    assert receipt["field_contract_ids"] == [
        row["measurement_contract"]["measurement_contract_id"]
        for row in episode["minimal_field_chains"]
    ]
    assert receipt["predicted_directions"] == {
        row["measurement_contract"]["metric_id"]: row["prediction"]["predicted_direction"]
        for row in episode["minimal_field_chains"]
    }
    assert receipt["outcome_access"] == episode["outcome_access"]
    assert receipt["rights"] == training.RIGHTS
