from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_v2_training as v2
from scripts import judgment_historical_training as history


ROOT = Path(__file__).resolve().parents[1]
BLOCK_ROOT = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
H1_RECEIPT = {"receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1", "receipt_version": 1}


def _inputs() -> tuple[dict, dict, list[dict], list[dict], dict]:
    h1 = json.loads((ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json").read_text(encoding="utf-8"))
    history_result = history.build_industry_history_series_from_h1(h1, h1_receipt_ref=H1_RECEIPT)
    assert history_result["valid"], history_result["findings"]
    models = json.loads((BLOCK_ROOT / "02_enterprise_system_models.json").read_text(encoding="utf-8"))
    episodes = json.loads((BLOCK_ROOT / "01_e0_context_episodes.json").read_text(encoding="utf-8"))
    episodes += json.loads((BLOCK_ROOT / "03_enterprise_judgment_episodes.json").read_text(encoding="utf-8"))
    block = json.loads((BLOCK_ROOT / "04_industry_learning_block.json").read_text(encoding="utf-8"))
    return h1, history_result["industry_history_series"], models, episodes, block


def _pre_outcome_freeze() -> dict:
    return json.loads((BLOCK_ROOT / "04_pre_outcome_roster_freeze.json").read_text(encoding="utf-8"))


def test_real_cement_e0_e1_block_freezes_h1_risk_set_and_read_only_training_views() -> None:
    h1, series, models, episodes, block = _inputs()

    assert series["cutoffs"] == [
        "2014-04-16T00:00:00+08:00",
        "2015-04-15T00:00:00+08:00",
        "2016-04-27T00:00:00+08:00",
        "2017-04-12T00:00:00+08:00",
        "2018-04-22T00:00:00+08:00",
        "2018-04-30T23:59:59+08:00",
    ]
    assert all(len(snapshot["members"]) == 5 for snapshot in series["snapshots"])
    assert all(member["risk_status"] == "IN_RISK_SET" for snapshot in series["snapshots"] for member in snapshot["members"])

    for episode in episodes:
        result = v2.validate_enterprise_judgment_episode(episode, history_series=series, h1_package=h1, enterprise_models=models)
        assert result["valid"], result["findings"]
        read_model = v2.compile_enterprise_judgment_episode(episode, history_series=series, h1_package=h1, enterprise_models=models)
        assert read_model["valid"], read_model["findings"]
        assert read_model["episode_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"

    result = v2.compile_industry_learning_block(block, history_series=series, h1_package=h1, episodes=episodes, enterprise_models=models)
    assert result["valid"], result["findings"]
    assert result["industry_learning_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"
    assert len(block["company_cutoff_transition_roster"]) == 20
    assert {row["company_id"] for row in block["company_cutoff_transition_roster"]} == {
        "CN:600585", "CN:600801", "CN:000401", "CN:600425", "CN:600802",
    }


def test_cutoff_source_and_management_action_cannot_be_backfilled_or_promoted() -> None:
    h1, series, models, episodes, _ = _inputs()
    conch = next(episode for episode in episodes if episode["episode_id"] == "EJE:CN:600585:20170412")
    late = deepcopy(conch)
    late["claims"][0]["evidence_refs"] = ["CNINFO:600585:ANN:20180323:1204507132"]
    result = v2.validate_enterprise_judgment_episode(late, history_series=series, h1_package=h1, enterprise_models=models)
    assert not result["valid"]
    assert any("source_not_cutoff_visible" in finding for finding in result["findings"])

    action = deepcopy(conch)
    action["mechanism_threads"][0]["anchor_kind"] = "MANAGEMENT_DECISION"
    result = v2.validate_enterprise_judgment_episode(action, history_series=series, h1_package=h1, enterprise_models=models)
    assert not result["valid"]
    assert any("management_action_requires_material_decision_observation" in finding for finding in result["findings"])


def test_unsettled_outcome_cell_only_blocks_its_dependent_claim() -> None:
    h1, series, models, episodes, _ = _inputs()
    conch = deepcopy(next(episode for episode in episodes if episode["episode_id"] == "EJE:CN:600585:20170412"))
    conch["claims"][0]["dependent_outcome_cell_ids"] = ["CELL:600585:20170412:OPERATIONS"]
    result = v2.compile_enterprise_judgment_episode(conch, history_series=series, h1_package=h1, enterprise_models=models)
    assert result["valid"], result["findings"]
    rows = {row["claim_id"]: row for row in result["episode_read_model"]["claim_output_matrix"]}
    assert rows["CLAIM:600585:OPERATING"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert "STATE_VIEW" in rows["CLAIM:600585:CASH"]["allowed_outputs"]


def test_j2_probe_is_bound_to_e1_thread_and_cannot_claim_management_action() -> None:
    h1, series, models, episodes, _ = _inputs()
    huaxin = next(episode for episode in episodes if episode["episode_id"] == "EJE:CN:600801:20170412")
    probe = json.loads((BLOCK_ROOT / "06_mechanism_probe.json").read_text(encoding="utf-8"))
    result = v2.compile_mechanism_probe(probe, episode=huaxin, history_series=series, h1_package=h1, enterprise_models=models)
    assert result["valid"], result["findings"]
    assert result["mechanism_probe_read_model"]["action_effect_authority"] == "NONE"
    assert result["mechanism_probe_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"

    action = deepcopy(probe)
    action["action_effect_authority"] = "LOCAL_ONLY"
    result = v2.validate_mechanism_probe(action, episode=huaxin, history_series=series, h1_package=h1, enterprise_models=models)
    assert not result["valid"]
    assert "mechanism_probe.state_transmission_must_not_claim_action_effect" in result["findings"]

    pure_text_e2 = deepcopy(huaxin)
    pure_text_e2["admission_level"] = "E2_MECHANISM_PROBE"
    result = v2.validate_enterprise_judgment_episode(pure_text_e2, history_series=series, h1_package=h1, enterprise_models=models)
    assert not result["valid"]
    assert "episode.e2_must_be_compiled_as_a_bound_mechanism_probe" in result["findings"]


def test_independent_mismatch_settlement_is_preserved_and_changes_next_cutoff_agenda() -> None:
    h1, series, models, episodes, block = _inputs()
    freeze = _pre_outcome_freeze()
    settlement = json.loads((BLOCK_ROOT / "05_feedback_settlement_001.json").read_text(encoding="utf-8"))
    result = v2.validate_feedback_settlement(settlement, block=block, pre_outcome_roster_freeze=freeze, history_series=series, h1_package=h1, episodes=episodes, enterprise_models=models)
    assert result["valid"], result["findings"]
    assert settlement["observations"][0]["status"] == "MEASUREMENT_MISMATCH"
    assert settlement["next_cutoff_agenda_delta"][0]["change_type"] == "ADD_BOUNDARY"

    feedback = v2.compile_feedback_read_model(settlement, block=block, pre_outcome_roster_freeze=freeze, history_series=series, h1_package=h1, episodes=episodes, enterprise_models=models)
    assert feedback["valid"], feedback["findings"]
    rows = {row["claim_id"]: row for row in feedback["feedback_read_model"]["claim_output_matrix"]}
    assert rows["CLAIM:600801:PERIMETER"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert rows["CLAIM:600801:OPERATING"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert "STATE_VIEW" in rows["CLAIM:600801:CASH"]["allowed_outputs"]

    continued = json.loads((BLOCK_ROOT / "07_feedback_settlement_002.json").read_text(encoding="utf-8"))
    result = v2.validate_feedback_settlement(continued, block=block, pre_outcome_roster_freeze=freeze, history_series=series, h1_package=h1, episodes=episodes, enterprise_models=models)
    assert result["valid"], result["findings"]
    assert continued["transition_id"] == "TRN:600585:20170412:20180422:CASH"
    assert continued["observations"][0]["status"] == "OBSERVED"
    assert continued["next_cutoff_agenda_delta"][0]["change_type"] == "CHANGE_EVIDENCE_ORDER"

    substituted = deepcopy(settlement)
    substituted["source_receipt"]["source_ref"] = "CNINFO:600585:ANN:20180323:1204507132"
    result = v2.validate_feedback_settlement(substituted, block=block, pre_outcome_roster_freeze=freeze, history_series=series, h1_package=h1, episodes=episodes, enterprise_models=models)
    assert not result["valid"]
    assert "feedback_settlement.source_receipt_must_match_declared_static_source" in result["findings"]

    reordered = deepcopy(block)
    reordered["company_cutoff_transition_roster"] = list(reversed(reordered["company_cutoff_transition_roster"]))
    reordered["transition_roster"] = list(reversed(reordered["transition_roster"]))
    for index, entry in enumerate(reordered["company_cutoff_transition_roster"], start=1):
        entry["rank"] = index
    for index, entry in enumerate(reordered["transition_roster"], start=1):
        entry["rank"] = index
    result = v2.validate_feedback_settlement(settlement, block=reordered, pre_outcome_roster_freeze=freeze, history_series=series, h1_package=h1, episodes=episodes, enterprise_models=models)
    assert not result["valid"]
    assert "pre_outcome_roster_freeze:pre_outcome_roster_freeze.company_cutoff_order_must_match_frozen_projection" in result["findings"]
    assert "pre_outcome_roster_freeze:pre_outcome_roster_freeze.outcome_order_must_match_frozen_projection" in result["findings"]


def test_predeclared_company_cutoff_order_cannot_be_rewritten_and_brief_hides_hypotheses() -> None:
    h1, series, models, episodes, block = _inputs()
    reordered = deepcopy(block)
    reordered["company_cutoff_transition_roster"][0]["rank"] = 2
    result = v2.validate_industry_learning_block(reordered, history_series=series, h1_package=h1, episodes=episodes, enterprise_models=models)
    assert not result["valid"]
    assert "industry_block.company_cutoff_transition_roster_must_preserve_predeclared_order" in result["findings"]

    huaxin = next(episode for episode in episodes if episode["episode_id"] == "EJE:CN:600801:20170412")
    brief = v2.compile_outcome_custodian_brief(block, huaxin, "TRN:600801:20170412:20180422:PERIMETER")
    assert brief["valid"], brief["findings"]
    projected = brief["outcome_custodian_brief"]
    assert set(projected) == {
        "block_id", "transition_id", "company_id", "issuer_id", "cutoff_at", "responsibility_boundary",
        "outcome_custodian_id", "outcome_cells", "outcome_access_status", "investment_authorization",
    }
    assert "hypotheses" not in json.dumps(projected, ensure_ascii=False)
    # The contract may name a forbidden proxy ("market price") precisely to
    # exclude it; it must not project an actual price field or value.
    assert '"price"' not in json.dumps(projected, ensure_ascii=False).lower()
