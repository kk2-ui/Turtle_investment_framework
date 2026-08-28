from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_appliance_continuous_training as continuous
from scripts import enterprise_judgment_appliance_four_stage as four_stage


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "development" / "research"
R10 = RESEARCH / "industry_learning_blocks" / "CN_APPLIANCE_ROUND10_V2_POSTOUTCOME"
R11 = RESEARCH / "industry_learning_blocks" / "CN_APPLIANCE_CONTINUOUS_TRAINING_V1"
FOUR_STAGE = RESEARCH / "industry_learning_blocks" / "CN_APPLIANCE_FOUR_STAGE_TRAINING_V1"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict, dict]:
    register = _load(RESEARCH / "CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json")
    j234 = _load(RESEARCH / "CN_APPLIANCE_INDUSTRY_J234_V1.json")
    review = _load(R10 / "02_external_method_review.json")
    completion = _load(R10 / "03_batch_completion_receipt.json")
    candidate = continuous.build_curriculum_candidate(review, completion)
    roster = continuous.build_roster()
    episode = continuous.build_preoutcome_episode(candidate, roster)
    independent_review = _load(R11 / "CN002032_20180930_INDEPENDENT_PREOUTCOME_REVIEW.json")
    return register, j234, episode, independent_review


def test_appliance_four_stage_plan_matches_latest_architecture_without_fake_comparative() -> None:
    register, j234, episode, review = _inputs()
    plan = four_stage.build_four_stage_plan(register, j234, episode, review)
    result = four_stage.validate_four_stage_plan(
        plan,
        source_register=register,
        j234_read_model=j234,
        supor_episode=episode,
        supor_review=review,
    )

    assert result["valid"], result["findings"]
    assert [row["stage"] for row in plan["stages"]] == four_stage.STAGE_ORDER
    assert plan["stages"][0]["status"] == "FROZEN"
    assert plan["stages"][1]["status"] == "FROZEN"
    assert plan["stages"][2]["status"] == "PREOUTCOME_FROZEN_AWAITING_INDEPENDENT_SETTLEMENT"
    assert plan["stages"][3]["status"] == "NOT_ADMITTED_NOT_BLOCKING_E0_TO_E2"
    assert len(plan["risk_set"]) == 6
    assert len(plan["stages"][2]["measurement_contract_refs"]) == 3
    assert plan["rights"] == four_stage.RIGHTS


def test_committed_four_stage_plan_is_the_canonical_result_unseen_projection() -> None:
    register, j234, episode, review = _inputs()
    committed = _load(FOUR_STAGE / "01_preoutcome_four_stage_plan.json")
    assert committed == four_stage.build_four_stage_plan(register, j234, episode, review)


def test_local_unknowns_do_not_remove_other_companies_or_admit_comparative() -> None:
    register, j234, episode, review = _inputs()
    plan = four_stage.build_four_stage_plan(register, j234, episode, review)
    company_ids = [row["company_id"] for row in plan["risk_set"]]
    assert company_ids == [
        "CN:000333", "CN:000651", "CN:000921", "CN:600690", "CN:600839", "CN:002032",
    ]
    assert plan["stages"][1]["local_unknown_policy"] == "UNKNOWN_BLOCKS_ONLY_DEPENDENT_CLAIMS"
    assert plan["stages"][3]["permitted_outputs"] == ["RESEARCH_AGENDA"]


def test_e3_or_outcome_injection_is_rejected_before_independent_custody() -> None:
    register, j234, episode, review = _inputs()
    canonical = four_stage.build_four_stage_plan(register, j234, episode, review)

    admitted = deepcopy(canonical)
    admitted["stages"][3]["status"] = "ADMITTED"
    admitted_result = four_stage.validate_four_stage_plan(
        admitted,
        source_register=register,
        j234_read_model=j234,
        supor_episode=episode,
        supor_review=review,
    )
    assert not admitted_result["valid"]
    assert "e3_cannot_be_admitted_without_comparative_contracts" in admitted_result["findings"]

    contaminated = deepcopy(canonical)
    contaminated["stages"][2]["outcome_value"] = 1
    contaminated_result = four_stage.validate_four_stage_plan(
        contaminated,
        source_register=register,
        j234_read_model=j234,
        supor_episode=episode,
        supor_review=review,
    )
    assert not contaminated_result["valid"]
    assert any("outcome_value_forbidden" in finding for finding in contaminated_result["findings"])


def test_investor_readout_exposes_stage_limits_not_prediction_or_price() -> None:
    register, j234, episode, review = _inputs()
    plan = four_stage.build_four_stage_plan(register, j234, episode, review)
    readout = four_stage.compile_investor_stage_readout(plan)
    serialized = json.dumps(readout, ensure_ascii=False).casefold()
    assert readout["stage_status"]["E3_COMPARATIVE_LAB"] == "NOT_ADMITTED_NOT_BLOCKING_E0_TO_E2"
    assert "predicted_direction" not in serialized
    assert "market_price" not in serialized
    assert readout["rights"] == four_stage.RIGHTS
