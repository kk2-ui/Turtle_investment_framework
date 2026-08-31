from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.enterprise_underwriting_training import (
    CONTRACT_SCHEMA,
    build_fresh_subagent_task,
    validate_training_contract,
)
from scripts.report_autonomy_appliance_cohort_prereg_generator import (
    EXPECTED_COMPANY_IDS,
    EXPERT_CORRECTION_MEMORY_REF,
    INDUSTRY_MEMORY_REF,
    INPUT_SCHEMA,
    PREREGISTRATION_STATE,
    build_appliance_cohort_preregistration,
    main,
)
from scripts.report_autonomy_multicompany_prereg import (
    ARMS,
    validate_multicompany_preregistration,
)


_INPUT_FIXTURE = (
    Path(__file__).parent / "fixtures" / "report_autonomy_appliance_cohort_prereg_input.json"
)


def _actual_input() -> dict[str, object]:
    return json.loads(_INPUT_FIXTURE.read_text(encoding="utf-8"))


def _common_contract_projection(contract: dict[str, object]) -> dict[str, object]:
    projection = deepcopy(contract)
    projection.pop("contract_id")
    projection["allowed_sources"] = [
        source for source in projection["allowed_sources"]
        if source["time_role"] == "PRE_CUTOFF"
    ]
    return projection


def test_actual_appliance_input_generates_a_reviewable_unexecuted_register() -> None:
    preregistration = build_appliance_cohort_preregistration(_actual_input())

    validation = validate_multicompany_preregistration(preregistration)
    assert validation["state"] == "REVIEWABLE"
    assert preregistration["state"] == PREREGISTRATION_STATE
    assert preregistration["state"] == "COHORT_FROZEN"
    assert _actual_input()["schema_version"] == INPUT_SCHEMA
    assert [case["company_id"] for case in preregistration["cases"]] == list(EXPECTED_COMPANY_IDS)
    assert len(preregistration["cohort"]["candidate_universe"]) == 13
    assert [
        candidate["company_id"]
        for candidate in preregistration["cohort"]["candidate_universe"]
        if candidate["eligibility"] == "EXCLUDED"
    ] == ["CN:000521", "CN:002035", "CN:002508", "CN:603515", "CN:603868"]
    assert all(
        candidate["candidate_evidence_ref"]
        for candidate in preregistration["cohort"]["candidate_universe"]
    )
    assert len(preregistration["execution"]["cells"]) == 32
    assert "mapping" not in preregistration["anonymous_review_custody"]
    assert len(preregistration["anonymous_review_custody"]["reviewer_manifest"]) == 32
    assert all(
        item["anonymous_label"].startswith("ANON_")
        and item["anonymous_label"][5:].isalpha()
        for item in preregistration["anonymous_review_custody"]["reviewer_manifest"]
    )
    assert len(preregistration["outcome_measurements"]) == 8
    assert preregistration["outcome_access_gate"]["outcome_access_authorized"] is False
    assert all(
        len(order) == 4 and set(order) == set(ARMS)
        for order in preregistration["execution"]["schedule"]["episode_orders"].values()
    )

    for cell in preregistration["execution"]["cells"]:
        assert cell["state"] == "NOT_STARTED"
        assert cell["attempts"] == {"episode": 0, "reader_report": 0}
        assert cell["training_contract"]["schema_version"] == CONTRACT_SCHEMA
        assert validate_training_contract(cell["training_contract"])["state"] == "REVIEWABLE"
        assert cell["rendered_task"] == build_fresh_subagent_task(cell["training_contract"])


def test_public_register_exposes_only_four_opaque_labels_per_case() -> None:
    preregistration = build_appliance_cohort_preregistration(_actual_input())
    assert all(
        len([
            item["anonymous_label"]
            for item in preregistration["anonymous_review_custody"]["reviewer_manifest"]
            if item["case_id"] == case_id
        ]) == len(ARMS)
        for case_id in [f"CASE:{number:02d}" for number in range(1, 9)]
    )
    assert "arm_id" not in str(preregistration["anonymous_review_custody"]["reviewer_manifest"])


def test_each_arm_changes_only_its_predeclared_training_memory() -> None:
    preregistration = build_appliance_cohort_preregistration(_actual_input())
    first_case_id = preregistration["cases"][0]["case_id"]
    cells = {
        cell["arm_id"]: cell
        for cell in preregistration["execution"]["cells"]
        if cell["case_id"] == first_case_id
    }

    common = _common_contract_projection(cells["A00"]["training_contract"])
    assert all(
        _common_contract_projection(cells[arm_id]["training_contract"]) == common
        for arm_id in ARMS
    )
    memory_refs_by_arm = {
        arm_id: {
            source["source_ref"]
            for source in cells[arm_id]["training_contract"]["allowed_sources"]
            if source["time_role"] == "TRAINING_MEMORY"
        }
        for arm_id in ARMS
    }
    assert memory_refs_by_arm == {
        "A00": set(),
        "A01": {INDUSTRY_MEMORY_REF},
        "A10": {EXPERT_CORRECTION_MEMORY_REF},
        "A11": {INDUSTRY_MEMORY_REF, EXPERT_CORRECTION_MEMORY_REF},
    }


def test_cli_writes_the_same_deterministic_inline_register(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "nested" / "preregistration.json"
    input_path.write_text(json.dumps(_actual_input(), ensure_ascii=False), encoding="utf-8")

    assert main([str(input_path), str(output_path)]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == build_appliance_cohort_preregistration(
        _actual_input()
    )
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "REVIEWABLE"


def test_generator_rejects_a_non_declared_company_before_contract_generation() -> None:
    config = _actual_input()
    config["candidate_universe"][0]["company_id"] = "CN:999999"

    with pytest.raises(ValueError, match="must_match_declared_eight_company_ids"):
        build_appliance_cohort_preregistration(config)


def test_generator_rejects_a_semantic_anonymous_label() -> None:
    config = _actual_input()
    config["reviewer_labels_by_selection_rank"][0]["anonymous_labels"][0] = "ANON_BASELINEABCD"

    with pytest.raises(ValueError, match="anonymous_labels\\[0\\]_missing_invalid_or_duplicate"):
        build_appliance_cohort_preregistration(config)
