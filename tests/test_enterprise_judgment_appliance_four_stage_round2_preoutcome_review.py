import json
from pathlib import Path

from scripts import enterprise_judgment_appliance_continuous_training as roster_source
from scripts import enterprise_judgment_appliance_four_stage_round2 as round2


ROOT = Path(__file__).resolve().parents[1]
REVIEW = (
    ROOT
    / "docs"
    / "development"
    / "research"
    / "industry_learning_blocks"
    / "CN_APPLIANCE_FOUR_STAGE_TRAINING_V2"
    / "04_independent_preoutcome_review.json"
)


def test_round2_independent_review_authorizes_only_contract_bound_outcome_custody():
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    episode = round2.build_preoutcome_episode()
    resolution = round2.build_resolution_contract()
    roster = roster_source.build_roster()["candidate_order"]

    assert review["review_status"] == "PASS"
    assert review["reviewed_commit"] == "c25d0ea9b1dd8acbd5adaeec6a454c5fd38ee65a"
    assert review["episode_ref"] == episode["episode_id"]
    assert roster[review["roster_selection"]["fixed_position"] - 1]["company_id"] == round2.COMPANY_ID
    assert review["fairness_findings"]["same_fact_budget"] is True
    assert episode["fair_baseline"]["fact_refs"] == episode["cumulative_enhanced"]["fact_refs"]
    assert review["frozen_minimal_contract_ids"] == [
        chain["measurement_contract"]["measurement_contract_id"]
        for chain in episode["minimal_field_chains"]
    ]
    assert review["independently_reproduced_controller_counts"] == {
        "decision_contracts": 3,
        "technical_route_identities": 3,
        "measurement_contracts": 3,
        "static_evidence": 3,
        "predictions": 3,
        "outcome_access": 0,
        "source_inventories": 0,
        "observations": 0,
        "settlements": 0,
    }
    assert review["learning_rules_frozen_before_outcome"] == {
        "signed_miss_semantics": True,
        "product_relative_outperformance_threshold_percentage_points": resolution["product_relative_rule"]["outperformance_threshold_percentage_points"],
        "prior_comparative_bridge_absolute_rmb_tolerance": resolution["prior_period_bridge_rule"]["absolute_rmb_tolerance"],
        "bridge_failure_resolution": resolution["prior_period_bridge_rule"]["failure_resolution"],
        "mechanical_settlement_engine_copied": False,
        "existing_runner_and_controller_reused": True,
    }
    assert set(review["reviewer"]["distinct_from"]) == {
        round2.CURATOR_ID,
        round2.FORECASTER_ID,
        round2.CUSTODIAN_ID,
    }
    assert review["reviewer"]["reviewer_id"] not in review["reviewer"]["distinct_from"]
    assert set(review["review_execution"].values()) == {False}
    assert review["custodian_boundary"]["allowed_role"] == round2.CUSTODIAN_ID
    assert review["rights"] == round2.RIGHTS
