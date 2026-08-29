from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.investor_judgment_learning_read_model import build_learning_read_model
from scripts.investor_judgment_research_agenda import (
    ResearchAgendaError,
    build_research_agenda,
    validate_research_agenda,
)


ROOT = Path(__file__).resolve().parents[1]
READ_MODEL_PATH = ROOT / "docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1.json"
AGENDA_PATH = ROOT / "docs/development/research/INVESTOR_JUDGMENT_RESEARCH_AGENDA_V1.json"
MANIFEST_PATH = ROOT / "docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1_MANIFEST.json"
POLICY_PATH = ROOT / "docs/development/research/INVESTOR_JUDGMENT_RESEARCH_AGENDA_V1_POLICY.json"


def _read_model() -> dict:
    return json.loads(READ_MODEL_PATH.read_text(encoding="utf-8"))


def _agenda(read_model: dict | None = None) -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return build_research_agenda(
        read_model or _read_model(),
        policy,
        read_model_ref=str(READ_MODEL_PATH.relative_to(ROOT)),
        policy_ref=str(POLICY_PATH.relative_to(ROOT)),
    )


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for child in value.values():
            result.update(_keys(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(_keys(child))
        return result
    return set()


def test_current_agenda_is_ready_only_for_l2_research_design() -> None:
    agenda = _agenda()

    assert validate_research_agenda(agenda) == {"valid": True, "findings": []}
    assert agenda["readiness"]["state"] == "READY_FOR_L2_RESEARCH_DESIGN"
    assert agenda["next_training_contract"]["target_level"] == "L2"
    assert agenda["allowed_outputs"] == ["RESEARCH_AGENDA_ONLY"]
    assert set(agenda["rights"].values()) == {"NOT_AUTHORIZED"}


def test_valid_lessons_are_replication_or_redesign_candidates_not_validated_rules() -> None:
    rules = _agenda()["candidate_research_rules"]

    assert {rule["source_round_id"] for rule in rules} == {"ROUND5", "ROUND6", "ROUND7", "ROUND8", "ROUND10"}
    assert {rule["status"] for rule in rules} == {
        "LOCAL_LESSON_REPLICATION_REQUIRED",
        "DEVELOPMENT_UTILITY_REPLICATION_REQUIRED",
        "NO_ADVANTAGE_REDESIGN_REQUIRED",
        "NO_MATERIAL_UTILITY_REDESIGN_REQUIRED",
    }
    assert all(rule["allowed_use"] == "NEXT_EPISODE_QUESTION_OR_ACQUISITION_DESIGN_ONLY" for rule in rules)
    assert all("validated method" in rule["prohibited_use"] for rule in rules)


def test_round8_no_advantage_is_a_caution_and_only_yields_redesign_rules() -> None:
    agenda = _agenda()

    assert [item["source_round_id"] for item in agenda["method_cautions"]] == ["ROUND8", "ROUND10"]
    assert agenda["method_cautions"][0]["status"] == "NO_ADVANTAGE_PROVED"
    round8_rules = [rule for rule in agenda["candidate_research_rules"] if rule["source_round_id"] == "ROUND8"]
    assert len(round8_rules) == 9
    assert {rule["status"] for rule in round8_rules} == {"NO_ADVANTAGE_REDESIGN_REQUIRED"}
    assert {rule["evidence_class"] for rule in round8_rules} == {
        "VALID_NEGATIVE_METHOD_OR_MEASUREMENT_LESSON"
    }


def test_round10_no_material_utility_only_yields_evidence_redesign_rules() -> None:
    agenda = _agenda()
    round10_rules = [rule for rule in agenda["candidate_research_rules"] if rule["source_round_id"] == "ROUND10"]
    round10_caution = next(item for item in agenda["method_cautions"] if item["source_round_id"] == "ROUND10")

    assert len(round10_rules) == 2
    assert {rule["status"] for rule in round10_rules} == {"NO_MATERIAL_UTILITY_REDESIGN_REQUIRED"}
    assert {rule["evidence_class"] for rule in round10_rules} == {
        "VALID_NEGATIVE_METHOD_OR_MEASUREMENT_LESSON"
    }
    assert round10_caution["status"] == "NO_MATERIAL_UTILITY"
    assert "ROUND10" not in {item["round_id"] for item in agenda["historical_company_context"]}


def test_round9_is_quarantined_and_cannot_reenter_candidate_rules() -> None:
    agenda = _agenda()

    assert [item["source_round_id"] for item in agenda["quarantined_evidence"]] == ["ROUND9"]
    quarantine = agenda["quarantined_evidence"][0]
    assert quarantine["status"] == "INVALIDATED"
    assert "METHOD_FEEDBACK_COMPLETED" in quarantine["prohibited_claims"]
    assert "ROUND9" not in {rule["source_round_id"] for rule in agenda["candidate_research_rules"]}


def test_company_findings_are_context_only_and_not_transfer_authority() -> None:
    contexts = _agenda()["historical_company_context"]

    assert len(contexts) == 5
    assert all(item["use_permission"] == "HISTORICAL_COMPANY_CONTEXT_ONLY" for item in contexts)
    assert all("Do not transfer" in item["prohibited_use"] for item in contexts)


def test_company_specific_follow_up_is_kept_out_of_cross_company_rules() -> None:
    agenda = _agenda()

    assert len(agenda["company_continuation_agenda"]) == 2
    assert {item["source_round_id"] for item in agenda["company_continuation_agenda"]} == {"ROUND6"}
    assert all(item["status"] == "COMPANY_CONTINUATION_ONLY" for item in agenda["company_continuation_agenda"])
    round6_rules = [rule for rule in agenda["candidate_research_rules"] if rule["source_round_id"] == "ROUND6"]
    assert len(round6_rules) == 1


def test_unreviewed_evidence_is_excluded_from_rules_and_context() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    round6 = next(item for item in manifest["entries"] if item["round_id"] == "ROUND6")
    round6["independent_review_artifact"] = ""
    read_model = build_learning_read_model(manifest, repo_root=ROOT, manifest_ref="fixture")

    agenda = _agenda(read_model)

    assert agenda["unreviewed_evidence"] == [{
        "round_id": "ROUND6",
        "evidence_id": "R6COMP:CN:CEMENT:600801:20160427:FY2016:V1",
        "status": "EXCLUDED_PENDING_INDEPENDENT_REVIEW",
    }]
    assert "ROUND6" not in {rule["source_round_id"] for rule in agenda["candidate_research_rules"]}
    assert "ROUND6" not in {item["round_id"] for item in agenda["historical_company_context"]}


def test_denominator_is_preserved_and_no_total_ranking_is_created() -> None:
    read_model = _read_model()
    agenda = _agenda(read_model)

    assert agenda["preserved_denominator"] == read_model["preserved_denominator"]
    assert not ({"score", "judgment_score", "total_score", "rank", "win_rate"} & _keys(agenda))
    assert agenda["aggregation_policy"] == "NO_TOTAL_RANKING_NO_METHOD_WIN_RATE"


def test_policy_cannot_move_invalidated_round9_into_candidate_rules() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    round9 = next(item for item in policy["entries"] if item["round_id"] == "ROUND9")
    round9["dispositions"][0]["disposition"] = "CANDIDATE_RESEARCH_RULE"

    with pytest.raises(ResearchAgendaError, match="invalidated_policy_disposition_invalid:ROUND9"):
        build_research_agenda(_read_model(), policy)


def test_checked_in_agenda_is_the_deterministic_projection() -> None:
    expected = json.loads(AGENDA_PATH.read_text(encoding="utf-8"))

    assert expected == _agenda()


def test_schema_keeps_output_and_investment_rights_closed() -> None:
    schema = json.loads(
        (ROOT / "schemas/investor_judgment_research_agenda.schema.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["allowed_outputs"]["const"] == ["RESEARCH_AGENDA_ONLY"]
    assert schema["properties"]["next_training_contract"]["properties"]["target_level"]["const"] == "L2"
