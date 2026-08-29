import json
from pathlib import Path

from scripts import enterprise_judgment_appliance_continuous_training as training


ROOT = Path(__file__).resolve().parents[1]
REVIEW = (
    ROOT
    / "docs"
    / "development"
    / "research"
    / "industry_learning_blocks"
    / "CN_APPLIANCE_CONTINUOUS_TRAINING_V1"
    / "CN002032_20180930_INDEPENDENT_PREOUTCOME_REVIEW.json"
)


def test_independent_review_authorizes_only_outcome_custody_for_exact_frozen_fields():
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    chains = training.build_minimal_chains()

    assert review["reviewed_commit"] == "b3ccde39121d339c273095dba671b2dc4748c09c"
    assert review["episode_ref"] == training.EPISODE_ID
    assert review["review_status"] == "PASS"
    assert review["decision"] == "OUTCOME_ONLY_CUSTODY_MAY_BE_AUTHORIZED"
    assert review["field_contract_ids"] == [
        chain["measurement_contract"]["measurement_contract_id"]
        for chain in chains
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
    assert review["custodian_contract"]["allowed_role"] == training.CUSTODIAN_ID
    assert review["outcome_content_read"] is False
    assert review["allowed_outputs"] == ["OUTCOME_ONLY_CUSTODY_AUTHORIZATION"]
    assert review["rights"] == training.RIGHTS


def test_independent_review_does_not_expose_prediction_or_grant_downstream_rights():
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    custodian = review["custodian_contract"]

    assert "PREDICTED_DIRECTION" in custodian["prohibited_inputs"]
    assert "FORECAST_REASONING" in custodian["prohibited_inputs"]
    assert "PRICE_OR_RETURN" in custodian["prohibited_inputs"]
    assert custodian["allowed_output"] == "FIELD_LEVEL_ACQUISITION_AND_MECHANICAL_SETTLEMENT_ONLY"
    assert set(review["rights"].values()) == {"NOT_AUTHORIZED"}
