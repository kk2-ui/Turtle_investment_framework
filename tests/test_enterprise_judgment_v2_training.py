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


def _round2_inputs() -> tuple[dict, dict, list[dict], list[dict], dict, dict, dict, list[dict], dict, dict, list[dict]]:
    h1, series, source_models, source_episodes, block = _inputs()
    eligibility_register = json.loads((BLOCK_ROOT / "11a_round2_eligibility_register.json").read_text(encoding="utf-8"))
    selection = json.loads((BLOCK_ROOT / "11_round2_transition_selection.json").read_text(encoding="utf-8"))
    target_models = json.loads((BLOCK_ROOT / "09_round2_enterprise_system_models.json").read_text(encoding="utf-8"))
    target_episode = json.loads((BLOCK_ROOT / "10_round2_preoutcome_episode.json").read_text(encoding="utf-8"))
    application = json.loads((BLOCK_ROOT / "12_transfer_application_receipt.json").read_text(encoding="utf-8"))
    completed = [
        json.loads((BLOCK_ROOT / "05_feedback_settlement_001.json").read_text(encoding="utf-8")),
        json.loads((BLOCK_ROOT / "07_feedback_settlement_002.json").read_text(encoding="utf-8")),
    ]
    return h1, series, source_models, source_episodes, block, eligibility_register, selection, target_models, target_episode, application, completed


def _round3_preoutcome_inputs() -> tuple[dict, dict, list[dict], list[dict], dict, list[dict], dict, dict, dict, list[dict], dict]:
    h1, series, source_models, source_episodes, block, eligibility_register, selection, target_models, target_episode, application, completed = _round2_inputs()
    round2_chain = {
        "eligibility_register": eligibility_register,
        "selection": selection,
        "target_models": target_models,
        "target_episode": target_episode,
        "application": application,
        "continuation_settlement": json.loads((BLOCK_ROOT / "13_round2_continuation_feedback_settlement.json").read_text(encoding="utf-8")),
        "review": json.loads((BLOCK_ROOT / "14_transfer_application_independent_review.json").read_text(encoding="utf-8")),
        "completion": json.loads((BLOCK_ROOT / "15_round2_completion_receipt.json").read_text(encoding="utf-8")),
        "source_feedback_settlement": completed[0],
    }
    round3_models = json.loads((BLOCK_ROOT / "17_round3_enterprise_system_models.json").read_text(encoding="utf-8"))
    round3_episode = json.loads((BLOCK_ROOT / "18_round3_preoutcome_episode.json").read_text(encoding="utf-8"))
    round3_selection = json.loads((BLOCK_ROOT / "16_round3_method_transfer_selection.json").read_text(encoding="utf-8"))
    round3_application = json.loads((BLOCK_ROOT / "19_round3_transfer_application_receipt.json").read_text(encoding="utf-8"))
    return h1, series, source_models, source_episodes, block, completed, round2_chain, round3_selection, round3_episode, round3_models, round3_application


def _synthetic_round3_settlement(perimeter_status: str = "STABLE") -> dict:
    observed = perimeter_status != "CHANGED_WITHOUT_BRIDGE"
    return {
        "schema_version": "enterprise-judgment-round3-feedback-settlement.v1",
        "settlement_id": "R3FBS:600425:20140416:SYNTHETIC",
        "application_ref": "TAR:CN:CEMENT:PERIMETER_FIRST:600425:20140416:R3:V1",
        "selection_ref": "R3SEL:CN:CEMENT:600425:20140416:V1",
        "company_id": "CN:600425",
        "cutoff_at": "2014-04-16T00:00:00+08:00",
        "outcome_custodian_id": "ROLE:CEMENT:OUTCOME_CUSTODIAN",
        "method_rule_id": "PERIMETER_FIRST_MEASUREMENT_GATE",
        "research_order": [
            "CHECK_LISTED_CONSOLIDATED_PERIMETER",
            "ASSESS_COMMON_BASIS_OR_BRIDGE",
            "READ_FROZEN_OPERATING_AND_CASH_FIELDS_IF_COMPARABLE",
        ],
        "perimeter_assessment": {
            "status": perimeter_status,
            "statement": "Synthetic validator fixture for the predeclared stable/mismatch branches.",
            "evidence_refs": ["CNINFO:600425:ANN:20150411:1200812468"],
        },
        "source_receipt": {
            "source_ref": "CNINFO:600425:ANN:20150411:1200812468",
            "published_on": "2015-04-11",
            "official_url": "https://static.cninfo.com.cn/finalpage/2015-04-11/1200812468.PDF",
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "custodian_access": "OUTCOME_ONLY",
            "availability_precision": "DATE",
        },
        "observations": [
            {
                "outcome_cell_id": "CELL:600425:20140416:OPERATIONS",
                "status": "OBSERVED" if observed else "MEASUREMENT_MISMATCH",
                "reported_value": "RMB 1" if observed else "SAME_BOUNDARY_OPERATING_NOT_ESTABLISHABLE",
                "summary": "Synthetic operating-field branch.",
                "source_ref": "CNINFO:600425:ANN:20150411:1200812468",
            },
            {
                "outcome_cell_id": "CELL:600425:20140416:CASH",
                "status": "OBSERVED" if observed else "MEASUREMENT_MISMATCH",
                "reported_value": "RMB 2" if observed else "SAME_BOUNDARY_OPERATING_CASH_NOT_ESTABLISHABLE",
                "summary": "Synthetic operating-cash branch.",
                "source_ref": "CNINFO:600425:ANN:20150411:1200812468",
            },
        ],
        "next_cutoff_agenda_delta": [{
            "target_cutoff_at": "2015-04-15T00:00:00+08:00",
            "change_id": "AGENDA:600425:20150415:SYNTHETIC",
            "change_type": "CHANGE_EVIDENCE_ORDER",
            "statement": "Keep checking perimeter before fields.",
            "reason": "Synthetic branch coverage.",
        }],
        "original_episode_immutable": True,
        "object_class": "ENTERPRISE_JUDGMENT_ROUND3_FEEDBACK_SETTLEMENT",
        "claim_class": "CONTRACT_MATCHED_METHOD_ORDER_FEEDBACK",
        "allowed_outputs": ["FEEDBACK_READ_MODEL", "RESEARCH_AGENDA"],
    }


def _synthetic_round3_review(settlement_id: str) -> dict:
    return {
        "schema_version": "enterprise-judgment-round3-transfer-review.v1",
        "review_id": "R3TRR:CN:CEMENT:600425:20140416:SYNTHETIC",
        "application_ref": "TAR:CN:CEMENT:PERIMETER_FIRST:600425:20140416:R3:V1",
        "feedback_ref": settlement_id,
        "prior_review_ref": "TRR:CN:CEMENT:PERIMETER_FIRST:000401:20170412:V1",
        "reviewer_id": "ROLE:CEMENT:ROUND3_TRANSFER_REVIEWER",
        "review_scope": "SECOND_CROSS_COMPANY_RESEARCH_ORDER_CHANGE_ONLY",
        "verdict": "SECOND_CROSS_COMPANY_RESEARCH_ORDER_CHANGE_CONFIRMED",
        "research_order_changed": True,
        "rule_unchanged": True,
        "materiality_statement": "The gate moved the boundary check ahead of both frozen fields without changing their definitions.",
        "prohibited_conclusion": "NO_ENTERPRISE_PERFORMANCE_ACTION_CAUSALITY_CJO_VALUATION_REPORT_OR_INVESTMENT_CONCLUSION",
        "object_class": "ENTERPRISE_JUDGMENT_ROUND3_TRANSFER_REVIEW",
        "claim_class": "INDEPENDENT_RESEARCH_ORDER_ADJUDICATION",
        "allowed_outputs": ["METHOD_TRANSFER_REVIEW_ONLY"],
    }


def _synthetic_round3_validation(settlement_id: str, review_id: str) -> dict:
    return {
        "schema_version": "enterprise-judgment-round3-transfer-validation.v1",
        "validation_id": "R3TV:CN:CEMENT:PERIMETER_FIRST:SYNTHETIC",
        "method_rule_id": "PERIMETER_FIRST_MEASUREMENT_GATE",
        "source_feedback_ref": "FBS:600801:20170412:001",
        "round2_application_ref": "TAR:CN:CEMENT:PERIMETER_FIRST:000401:20170412:V1",
        "round2_review_ref": "TRR:CN:CEMENT:PERIMETER_FIRST:000401:20170412:V1",
        "round2_completion_ref": "R2COMP:CN:CEMENT:000401:20170412:V1",
        "round3_selection_ref": "R3SEL:CN:CEMENT:600425:20140416:V1",
        "round3_application_ref": "TAR:CN:CEMENT:PERIMETER_FIRST:600425:20140416:R3:V1",
        "round3_settlement_ref": settlement_id,
        "round3_review_ref": review_id,
        "transfer_status": "TRANSFER_VALIDATED",
        "authority_scope": "PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY",
        "denied_authorities": [
            "ENTERPRISE_JUDGMENT", "COMPARATIVE", "METHOD_WIDE_RELEASE", "CJO", "VALUATION", "REPORT",
            "INVESTMENT_AUTHORIZATION", "R-61", "R-103",
        ],
        "object_class": "ENTERPRISE_JUDGMENT_ROUND3_TRANSFER_VALIDATION",
        "claim_class": "NARROW_MEASUREMENT_METHOD_AUTHORITY",
        "allowed_outputs": ["TRANSFER_VALIDATED", "PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY"],
    }


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


def test_round2_selection_and_cross_company_perimeter_application_are_frozen_before_outcome_access() -> None:
    # This catches outcome-guided row skipping and a transfer receipt that
    # rewrites the frozen target field rather than adding the first-round
    # perimeter measurement gate.
    h1, series, source_models, source_episodes, block, eligibility_register, selection, target_models, target_episode, application, completed = _round2_inputs()
    freeze = _pre_outcome_freeze()

    selection_result = v2.validate_round2_transition_selection(
        selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze, history_series=series, h1_package=h1,
        completed_feedback_settlements=completed, source_block_episodes=source_episodes, source_models=source_models,
    )
    assert selection_result["valid"], selection_result["findings"]
    assert selection["selected_rank"] == 12
    assert selection["company_id"] == "CN:000401"
    assert selection["outcome_access_status"] == "SEALED"

    episode_result = v2.validate_enterprise_judgment_episode(target_episode, history_series=series, h1_package=h1, enterprise_models=target_models)
    assert episode_result["valid"], episode_result["findings"]
    result = v2.validate_transfer_application_receipt(
        application, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze,
        target_episode=target_episode, target_models=target_models, history_series=series, h1_package=h1,
        source_feedback_settlement=completed[0], source_block_episodes=source_episodes, source_models=source_models,
        completed_feedback_settlements=completed,
    )
    assert result["valid"], result["findings"]
    assert application["learned_rule_id"] == "PERIMETER_FIRST_MEASUREMENT_GATE"
    assert application["enhanced_after_learning"][0]["definition"] == application["baseline_before_learning"][0]["definition"]
    assert application["field_delta"][0]["reason_ref"] == application["source_agenda_change_id"]

    skipped = deepcopy(selection)
    skipped["completed_company_cutoff_transition_ids"].append("CCR:000401:20140416:20150415")
    result = v2.validate_round2_transition_selection(
        skipped, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze, history_series=series, h1_package=h1,
        completed_feedback_settlements=completed, source_block_episodes=source_episodes, source_models=source_models,
    )
    assert not result["valid"]
    assert "round2_selection.completed_transitions_must_equal_actual_prior_feedback_projection" in result["findings"]

    mutated = deepcopy(application)
    mutated["enhanced_after_learning"][0]["definition"] = "Interpret operating cash as proof that the 2017 plan worked."
    result = v2.validate_transfer_application_receipt(
        mutated, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze,
        target_episode=target_episode, target_models=target_models, history_series=series, h1_package=h1,
        source_feedback_settlement=completed[0], source_block_episodes=source_episodes, source_models=source_models,
        completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "transfer_application.enhanced_after_learning[0].may_only_add_measurement_gate" in result["findings"]

    wrong_source = deepcopy(application)
    wrong_source["source_feedback_id"] = completed[1]["settlement_id"]
    result = v2.validate_transfer_application_receipt(
        wrong_source, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze,
        target_episode=target_episode, target_models=target_models, history_series=series, h1_package=h1,
        source_feedback_settlement=completed[1], source_block_episodes=source_episodes, source_models=source_models,
        completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "transfer_application.source_must_be_real_mismatch_with_boundary_agenda_change" in result["findings"]

    later_row = next(row for row in block["company_cutoff_transition_roster"] if row["rank"] == 13)
    later = deepcopy(selection)
    later.update({
        "selected_transition_id": later_row["transition_id"], "selected_rank": later_row["rank"],
        "company_id": later_row["company_id"], "company_cluster_id": later_row["company_cluster_id"],
        "cutoff_at": later_row["cutoff_at"], "next_cutoff_at": later_row["next_cutoff_at"],
    })
    later["ineligible_prior_rows"].append({
        "rank": 12, "transition_id": "CCR:000401:20170412:20180422",
        "reason": "NO_CUTOFF_VISIBLE_MATERIAL_LIFECYCLE_CONDITION",
    })
    result = v2.validate_round2_transition_selection(
        later, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze,
        history_series=series, h1_package=h1, completed_feedback_settlements=completed,
        source_block_episodes=source_episodes, source_models=source_models,
    )
    assert not result["valid"]
    assert "round2_selection.must_be_exact_derivation_of_first_eligible_binding" in result["findings"]


def test_second_real_feedback_settles_only_the_frozen_cash_cell_and_localizes_measurement_mismatch() -> None:
    # This catches a custodian result being bound to a different source/cell,
    # and verifies that a cash comparability failure does not erase the target
    # company's independent operating-state reconstruction.
    h1, series, source_models, source_episodes, block, eligibility_register, selection, target_models, target_episode, application, completed = _round2_inputs()
    freeze = _pre_outcome_freeze()
    settlement = json.loads((BLOCK_ROOT / "13_round2_continuation_feedback_settlement.json").read_text(encoding="utf-8"))
    result = v2.validate_continuation_feedback_settlement(
        settlement, application=application, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze,
        target_episode=target_episode, target_models=target_models, history_series=series, h1_package=h1,
        source_feedback_settlement=completed[0], source_block_episodes=source_episodes, source_models=source_models,
        completed_feedback_settlements=completed,
    )
    assert result["valid"], result["findings"]
    assert settlement["observations"] == [{
        "outcome_cell_id": "CELL:000401:20170412:CASH",
        "status": "MEASUREMENT_MISMATCH",
        "reported_value": "SAME_BOUNDARY_OPERATING_CASH_NOT_ESTABLISHABLE",
        "summary": settlement["observations"][0]["summary"],
        "source_ref": "CNINFO:000401:ANN:20180323:1204506085",
    }]

    read_model = v2.compile_continuation_feedback_read_model(
        settlement, application=application, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze,
        target_episode=target_episode, target_models=target_models, history_series=series, h1_package=h1,
        source_feedback_settlement=completed[0], source_block_episodes=source_episodes, source_models=source_models,
        completed_feedback_settlements=completed,
    )
    assert read_model["valid"], read_model["findings"]
    rows = {row["claim_id"]: row for row in read_model["continuation_feedback_read_model"]["claim_output_matrix"]}
    assert rows["CLAIM:000401:R2:PERIMETER_CASH"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert rows["CLAIM:000401:R2:CASH"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert "STATE_VIEW" in rows["CLAIM:000401:R2:OPERATING"]["allowed_outputs"]

    wrong_source = deepcopy(settlement)
    wrong_source["source_receipt"]["source_ref"] = "CNINFO:600801:ANN:20180326:1204514309"
    result = v2.validate_continuation_feedback_settlement(
        wrong_source, application=application, selection=selection, eligibility_register=eligibility_register, block=block, pre_outcome_roster_freeze=freeze,
        target_episode=target_episode, target_models=target_models, history_series=series, h1_package=h1,
        source_feedback_settlement=completed[0], source_block_episodes=source_episodes, source_models=source_models,
        completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "continuation_feedback_settlement.source_receipt_must_match_declared_static_source" in result["findings"]


def test_independent_review_creates_only_a_transfer_candidate_after_material_preoutcome_field_change() -> None:
    # This catches an application owner self-certifying transfer and prevents a
    # non-material or performance/valuation conclusion from becoming transfer
    # validation.
    h1, series, source_models, source_episodes, block, eligibility_register, selection, target_models, target_episode, application, completed = _round2_inputs()
    freeze = _pre_outcome_freeze()
    settlement = json.loads((BLOCK_ROOT / "13_round2_continuation_feedback_settlement.json").read_text(encoding="utf-8"))
    review = json.loads((BLOCK_ROOT / "14_transfer_application_independent_review.json").read_text(encoding="utf-8"))
    result = v2.validate_transfer_application_review(
        review, application=application, continuation_settlement=settlement, selection=selection, eligibility_register=eligibility_register,
        block=block, pre_outcome_roster_freeze=freeze, target_episode=target_episode, target_models=target_models,
        history_series=series, h1_package=h1, source_feedback_settlement=completed[0],
        source_block_episodes=source_episodes, source_models=source_models, completed_feedback_settlements=completed,
    )
    assert result["valid"], result["findings"]
    assert review["transfer_status"] == "TRANSFER_CANDIDATE_CREATED"
    assert review["prohibited_conclusion"] == "NO_ENTERPRISE_PERFORMANCE_ACTION_CAUSALITY_OR_INVESTMENT_CONCLUSION"

    self_review = deepcopy(review)
    self_review["reviewer_id"] = application["roles"]["judgment_owner_id"]
    result = v2.validate_transfer_application_review(
        self_review, application=application, continuation_settlement=settlement, selection=selection, eligibility_register=eligibility_register,
        block=block, pre_outcome_roster_freeze=freeze, target_episode=target_episode, target_models=target_models,
        history_series=series, h1_package=h1, source_feedback_settlement=completed[0],
        source_block_episodes=source_episodes, source_models=source_models, completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "transfer_application_review.reviewer_must_be_independent" in result["findings"]

    overclaimed = deepcopy(review)
    overclaimed["prohibited_conclusion"] = "TRANSFER_VALIDATED"
    result = v2.validate_transfer_application_review(
        overclaimed, application=application, continuation_settlement=settlement, selection=selection, eligibility_register=eligibility_register,
        block=block, pre_outcome_roster_freeze=freeze, target_episode=target_episode, target_models=target_models,
        history_series=series, h1_package=h1, source_feedback_settlement=completed[0],
        source_block_episodes=source_episodes, source_models=source_models, completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "transfer_application_review.must_deny_enterprise_and_investment_conclusion" in result["findings"]


def test_round2_completion_status_requires_both_real_feedback_and_independent_transfer_review() -> None:
    # This catches premature status marking: a continuation settlement alone
    # cannot create transfer candidacy, and candidacy cannot become validation.
    h1, series, source_models, source_episodes, block, eligibility_register, selection, target_models, target_episode, application, completed = _round2_inputs()
    freeze = _pre_outcome_freeze()
    settlement = json.loads((BLOCK_ROOT / "13_round2_continuation_feedback_settlement.json").read_text(encoding="utf-8"))
    review = json.loads((BLOCK_ROOT / "14_transfer_application_independent_review.json").read_text(encoding="utf-8"))
    completion = json.loads((BLOCK_ROOT / "15_round2_completion_receipt.json").read_text(encoding="utf-8"))
    result = v2.validate_round2_completion_receipt(
        completion, review=review, application=application, continuation_settlement=settlement, selection=selection, eligibility_register=eligibility_register,
        block=block, pre_outcome_roster_freeze=freeze, target_episode=target_episode, target_models=target_models,
        history_series=series, h1_package=h1, source_feedback_settlement=completed[0],
        source_block_episodes=source_episodes, source_models=source_models, completed_feedback_settlements=completed,
    )
    assert result["valid"], result["findings"]
    assert completion["feedback_turn_status"] == "REAL_FEEDBACK_TURN_2_COMPLETED"
    assert completion["transfer_status"] == "TRANSFER_CANDIDATE_CREATED"

    premature = deepcopy(completion)
    premature["transfer_status"] = "TRANSFER_VALIDATED"
    result = v2.validate_round2_completion_receipt(
        premature, review=review, application=application, continuation_settlement=settlement, selection=selection, eligibility_register=eligibility_register,
        block=block, pre_outcome_roster_freeze=freeze, target_episode=target_episode, target_models=target_models,
        history_series=series, h1_package=h1, source_feedback_settlement=completed[0],
        source_block_episodes=source_episodes, source_models=source_models, completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "round2_completion.statuses_must_remain_narrow" in result["findings"]


def test_round3_mechanically_selects_rank13_without_lifecycle_screening() -> None:
    h1, series, source_models, source_episodes, block, completed, round2_chain, selection, episode, target_models, application = _round3_preoutcome_inputs()
    freeze = _pre_outcome_freeze()
    result = v2.validate_round3_method_transfer_selection(
        selection, round2_chain=round2_chain, block=block, pre_outcome_roster_freeze=freeze,
        history_series=series, h1_package=h1, source_block_episodes=source_episodes,
        source_models=source_models, completed_feedback_settlements=completed,
    )
    assert result["valid"], result["findings"]
    assert (selection["selected_rank"], selection["company_id"]) == (13, "CN:600425")
    assert "LIFECYCLE" not in selection["selection_policy"]
    assert "OUTCOME_FEATURE_FILTER" in selection["selection_policy"]
    assert selection["outcome_access_status"] == "SEALED"

    later = deepcopy(selection)
    later.update({
        "selected_transition_id": "CCR:600425:20150415:20160427",
        "selected_rank": 14,
        "cutoff_at": "2015-04-15T00:00:00+08:00",
        "next_cutoff_at": "2016-04-27T00:00:00+08:00",
    })
    result = v2.validate_round3_method_transfer_selection(
        later, round2_chain=round2_chain, block=block, pre_outcome_roster_freeze=freeze,
        history_series=series, h1_package=h1, source_block_episodes=source_episodes,
        source_models=source_models, completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "round3_selection.must_mechanically_choose_earliest_unseen_frozen_row" in result["findings"]

    outcome_screened = deepcopy(selection)
    outcome_screened["lifecycle_condition"] = "KNOWN_SCOPE_CHANGE"
    result = v2.validate_round3_method_transfer_selection(
        outcome_screened, round2_chain=round2_chain, block=block, pre_outcome_roster_freeze=freeze,
        history_series=series, h1_package=h1, source_block_episodes=source_episodes,
        source_models=source_models, completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "round3_selection_contains_unapproved_field:lifecycle_condition" in result["findings"]


def test_round3_freezes_unchanged_perimeter_first_rule_before_outcome_access() -> None:
    h1, series, source_models, source_episodes, block, completed, round2_chain, selection, episode, target_models, application = _round3_preoutcome_inputs()
    freeze = _pre_outcome_freeze()
    episode_result = v2.validate_enterprise_judgment_episode(
        episode, history_series=series, h1_package=h1, enterprise_models=target_models,
    )
    assert episode_result["valid"], episode_result["findings"]
    result = v2.validate_round3_transfer_application_receipt(
        application, selection=selection, round2_chain=round2_chain, block=block,
        pre_outcome_roster_freeze=freeze, target_episode=episode, target_models=target_models,
        history_series=series, h1_package=h1, source_block_episodes=source_episodes,
        source_models=source_models, completed_feedback_settlements=completed,
    )
    assert result["valid"], result["findings"]
    assert application["learned_rule_id"] == "PERIMETER_FIRST_MEASUREMENT_GATE"
    assert application["target_outcome_access"] == "SEALED"
    assert application["frozen_before_outcome_access"] is True
    assert [cell["dimension"] for cell in application["enhanced_after_learning"]] == ["CASH", "OPERATIONS"]
    assert round2_chain["completion"]["transfer_status"] == "TRANSFER_CANDIDATE_CREATED"

    changed_rule = deepcopy(application)
    changed_rule["field_delta"][0]["materiality"] = "Company-specific rule tuned after reading FY2014."
    result = v2.validate_round3_transfer_application_receipt(
        changed_rule, selection=selection, round2_chain=round2_chain, block=block,
        pre_outcome_roster_freeze=freeze, target_episode=episode, target_models=target_models,
        history_series=series, h1_package=h1, source_block_episodes=source_episodes,
        source_models=source_models, completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert "round3_transfer_application.perimeter_first_rule_must_be_semantically_unchanged" in result["findings"]

    rewritten_round2 = deepcopy(round2_chain)
    rewritten_round2["completion"]["transfer_status"] = "TRANSFER_VALIDATED"
    result = v2.validate_round3_transfer_application_receipt(
        application, selection=selection, round2_chain=rewritten_round2, block=block,
        pre_outcome_roster_freeze=freeze, target_episode=episode, target_models=target_models,
        history_series=series, h1_package=h1, source_block_episodes=source_episodes,
        source_models=source_models, completed_feedback_settlements=completed,
    )
    assert not result["valid"]
    assert any("round2_completion.statuses_must_remain_narrow" in finding for finding in result["findings"])
    serialized = json.dumps({"selection": selection, "application": application}, sort_keys=True)
    assert "R-103" not in serialized
    assert "CJO" not in serialized
    assert "valuation" not in serialized.lower()


def test_round3_settlement_accepts_both_predeclared_stable_and_mismatch_paths() -> None:
    h1, series, source_models, source_episodes, block, completed, round2_chain, selection, episode, target_models, application = _round3_preoutcome_inputs()
    common = {
        "application": application, "selection": selection, "round2_chain": round2_chain, "block": block,
        "pre_outcome_roster_freeze": _pre_outcome_freeze(), "target_episode": episode,
        "target_models": target_models, "history_series": series, "h1_package": h1,
        "source_block_episodes": source_episodes, "source_models": source_models,
        "completed_feedback_settlements": completed,
    }
    stable = _synthetic_round3_settlement("STABLE")
    result = v2.validate_round3_feedback_settlement(stable, **common)
    assert result["valid"], result["findings"]
    mismatch = _synthetic_round3_settlement("CHANGED_WITHOUT_BRIDGE")
    result = v2.validate_round3_feedback_settlement(mismatch, **common)
    assert result["valid"], result["findings"]

    tuned = deepcopy(stable)
    tuned["research_order"].reverse()
    result = v2.validate_round3_feedback_settlement(tuned, **common)
    assert not result["valid"]
    assert "round3_settlement.must_execute_perimeter_before_fields" in result["findings"]

    inconsistent = deepcopy(stable)
    inconsistent["observations"][0]["status"] = "MEASUREMENT_MISMATCH"
    result = v2.validate_round3_feedback_settlement(inconsistent, **common)
    assert not result["valid"]
    assert "round3_settlement.observations[0].comparable_perimeter_requires_field_read" in result["findings"]


def test_real_round3_custodian_stops_before_fields_on_unbridged_perimeter_change() -> None:
    h1, series, source_models, source_episodes, block, completed, round2_chain, selection, episode, target_models, application = _round3_preoutcome_inputs()
    settlement = json.loads((BLOCK_ROOT / "20_round3_feedback_settlement.json").read_text(encoding="utf-8"))
    result = v2.validate_round3_feedback_settlement(
        settlement, application=application, selection=selection, round2_chain=round2_chain, block=block,
        pre_outcome_roster_freeze=_pre_outcome_freeze(), target_episode=episode, target_models=target_models,
        history_series=series, h1_package=h1, source_block_episodes=source_episodes,
        source_models=source_models, completed_feedback_settlements=completed,
    )
    assert result["valid"], result["findings"]
    assert settlement["perimeter_assessment"]["status"] == "CHANGED_WITHOUT_BRIDGE"
    assert [entry["status"] for entry in settlement["observations"]] == ["MEASUREMENT_MISMATCH", "MEASUREMENT_MISMATCH"]
    assert all("RMB " not in entry["reported_value"] for entry in settlement["observations"])
    assert settlement["research_order"][0] == "CHECK_LISTED_CONSOLIDATED_PERIMETER"


def test_round3_independent_review_can_grant_only_narrow_method_transfer() -> None:
    h1, series, source_models, source_episodes, block, completed, round2_chain, selection, episode, target_models, application = _round3_preoutcome_inputs()
    settlement = _synthetic_round3_settlement("STABLE")
    review = _synthetic_round3_review(settlement["settlement_id"])
    common = {
        "settlement": settlement, "application": application, "selection": selection,
        "round2_chain": round2_chain, "block": block, "pre_outcome_roster_freeze": _pre_outcome_freeze(),
        "target_episode": episode, "target_models": target_models, "history_series": series,
        "h1_package": h1, "source_block_episodes": source_episodes, "source_models": source_models,
        "completed_feedback_settlements": completed,
    }
    result = v2.validate_round3_transfer_review(review, **common)
    assert result["valid"], result["findings"]
    validation = _synthetic_round3_validation(settlement["settlement_id"], review["review_id"])
    result = v2.validate_round3_transfer_validation(validation, review=review, **common)
    assert result["valid"], result["findings"]
    assert validation["authority_scope"] == "PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY"

    self_review = deepcopy(review)
    self_review["reviewer_id"] = application["roles"]["judgment_owner_id"]
    result = v2.validate_round3_transfer_review(self_review, **common)
    assert not result["valid"]
    assert "round3_review.reviewer_must_be_independent" in result["findings"]

    overreach = deepcopy(validation)
    overreach["authority_scope"] = "ENTERPRISE_JUDGMENT"
    result = v2.validate_round3_transfer_validation(overreach, review=review, **common)
    assert not result["valid"]
    assert "round3_validation.status_or_authority_scope_invalid" in result["findings"]


def test_real_round3_review_and_validation_grant_only_perimeter_first_method() -> None:
    h1, series, source_models, source_episodes, block, completed, round2_chain, selection, episode, target_models, application = _round3_preoutcome_inputs()
    settlement = json.loads((BLOCK_ROOT / "20_round3_feedback_settlement.json").read_text(encoding="utf-8"))
    review = json.loads((BLOCK_ROOT / "21_round3_transfer_review.json").read_text(encoding="utf-8"))
    validation = json.loads((BLOCK_ROOT / "22_perimeter_first_transfer_validation.json").read_text(encoding="utf-8"))
    common = {
        "settlement": settlement, "application": application, "selection": selection,
        "round2_chain": round2_chain, "block": block, "pre_outcome_roster_freeze": _pre_outcome_freeze(),
        "target_episode": episode, "target_models": target_models, "history_series": series,
        "h1_package": h1, "source_block_episodes": source_episodes, "source_models": source_models,
        "completed_feedback_settlements": completed,
    }
    review_result = v2.validate_round3_transfer_review(review, **common)
    assert review_result["valid"], review_result["findings"]
    result = v2.validate_round3_transfer_validation(validation, review=review, **common)
    assert result["valid"], result["findings"]
    assert validation["transfer_status"] == "TRANSFER_VALIDATED"
    assert validation["authority_scope"] == "PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY"
    assert set(validation["denied_authorities"]) >= {"ENTERPRISE_JUDGMENT", "COMPARATIVE", "CJO", "VALUATION", "REPORT", "INVESTMENT_AUTHORIZATION", "R-103"}
