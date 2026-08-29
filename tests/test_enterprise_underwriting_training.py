from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.enterprise_underwriting_episode import compile_underwriting_projections
from scripts.enterprise_underwriting_training import (
    DOWNSTREAM_BUNDLE_SCHEMA,
    PRIMARY_PRODUCT,
    build_training_agent_messages,
    build_training_contract,
    compile_price_free_downstream_bundle,
    run_training_agent,
    main,
    validate_training_contract,
    validate_training_episode,
)


ROOT = Path(__file__).resolve().parents[1]
EPISODE_PATH = (
    ROOT
    / "docs/development/research/enterprise_underwriting_episodes"
    / "CN600585_20240501_WORKED_CASE_V1.json"
)
CONTRACT_PATH = (
    ROOT
    / "docs/development/research/enterprise_underwriting_episodes"
    / "CN600585_20240501_TRAINING_CONTRACT_V1.json"
)
COURSE_ROOT = (
    ROOT
    / "docs/development/research/training_campaigns"
    / "ENTERPRISE_UNDERWRITING_COURSE_1_20260829"
)
COURSE_BLIND_CONTRACT_PATH = COURSE_ROOT / "contracts/CN002352_BLIND_CONTRACT.json"
COURSE_BLIND_EPISODE_PATH = COURSE_ROOT / "blind/03_CN002352/enterprise_underwriting_episode.json"


def _episode() -> dict:
    return json.loads(EPISODE_PATH.read_text(encoding="utf-8"))


def _feedback_clocks() -> list[dict]:
    return [
        {
            "clock_id": "CLOCK:EARLY",
            "horizon": "EARLY_SIGNAL",
            "opens_at": "2025-05-01T00:00:00+08:00",
            "episode_claims": [
                "INDUSTRY_AND_SITUATION",
                "BUSINESS_POSITION_AND_ADAPTATION",
            ],
            "discriminating_observation": "量价、利用率与管理层适应动作是否沿同一公司传导出现。",
        },
        {
            "clock_id": "CLOCK:LONG",
            "horizon": "LONG_TERM_PERMANENT_LOSS",
            "opens_at": "2027-05-01T00:00:00+08:00",
            "episode_claims": ["OWNER_CASH", "PERMANENT_LOSS", "VALUE_ROUTE"],
            "discriminating_observation": "维护资本、普通股现金与资产回报是否支持当前价值路线。",
        },
    ]


def _allowed_episode_sources(episode: dict) -> list[dict]:
    references = [item["source_ref"] for item in episode["evidence_trace"]]
    references.extend(item["ref"] for item in episode["existing_object_refs"])
    return [
        {
            "source_id": f"SOURCE:{index}",
            "source_ref": reference,
            "available_at": "2026-08-29T00:00:00+08:00",
            "time_role": "RESULT_KNOWN",
        }
        for index, reference in enumerate(dict.fromkeys(references), start=1)
    ]


def _worked_contract(episode: dict | None = None) -> dict:
    value = episode or _episode()
    return build_training_contract(
        contract_id="UWTRAIN:CN600585:20240501:WORKED:V1",
        training_track="WORKED_CASE",
        company_id=value["company_id"],
        company_name=value["company_name"],
        cutoff_at=value["cutoff_at"],
        allowed_sources=_allowed_episode_sources(value),
        feedback_clocks=_feedback_clocks(),
    )


def _blind_contract() -> dict:
    return build_training_contract(
        contract_id="UWTRAIN:SYNTHETIC:BLIND:V1",
        training_track="BLIND_REPLAY",
        company_id="SYNTHETIC:COMPANY",
        company_name="Synthetic Company",
        cutoff_at="2024-05-01T00:00:00+08:00",
        allowed_sources=[
            {
                "source_id": "SOURCE:PRE",
                "source_ref": "AGENTS.md",
                "available_at": "2024-04-30T00:00:00+08:00",
                "time_role": "PRE_CUTOFF",
            }
        ],
        feedback_clocks=_feedback_clocks(),
    )


@pytest.mark.parametrize(
    ("track", "sample_identity", "outcome_access"),
    [
        ("WORKED_CASE", "WORKED_CASE", "RESULT_KNOWN"),
        ("BLIND_REPLAY", "BLIND_REPLAY", "SEALED"),
        ("PROSPECTIVE", "PROSPECTIVE_EPISODE", "NOT_YET_RELEASED"),
    ],
)
def test_tracks_only_bind_episode_identity_and_outcome_access(
    track: str, sample_identity: str, outcome_access: str,
) -> None:
    contract = build_training_contract(
        contract_id=f"UWTRAIN:{track}:V1",
        training_track=track,
        company_id="SYNTHETIC:COMPANY",
        company_name="Synthetic Company",
        cutoff_at="2024-05-01T00:00:00+08:00",
        allowed_sources=[
            {
                "source_id": "SOURCE:ONE",
                "source_ref": "AGENTS.md",
                "available_at": "2024-04-30T00:00:00+08:00",
                "time_role": "PRE_CUTOFF",
            }
        ],
        feedback_clocks=_feedback_clocks(),
    )

    assert contract["sample_identity"] == sample_identity
    assert contract["outcome_access"] == outcome_access
    assert contract["primary_training_product"] == PRIMARY_PRODUCT
    assert validate_training_contract(contract)["state"] == "REVIEWABLE"


def test_blind_contract_requires_sealed_cutoff_safe_sources() -> None:
    valid = _blind_contract()
    assert validate_training_contract(valid)["state"] == "REVIEWABLE"

    exposed = deepcopy(valid)
    exposed["outcome_access"] = "RESULT_KNOWN"
    findings = validate_training_contract(exposed)["findings"]
    assert "contract.outcome_access_not_bound_to_track" in findings
    assert "contract.blind_replay_requires_sealed_outcome" in findings

    future_source = deepcopy(valid)
    future_source["allowed_sources"][0]["available_at"] = "2024-05-02T00:00:00+08:00"
    assert any(
        "available_after_cutoff" in item
        for item in validate_training_contract(future_source)["findings"]
    )


def test_blind_training_memory_changes_questions_but_cannot_be_target_evidence() -> None:
    contract = json.loads(COURSE_BLIND_CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["allowed_sources"].append({
        "source_id": "SOURCE:TRAINING_MEMORY",
        "source_ref": "AGENTS.md",
        "available_at": "2026-08-29T22:00:00+08:00",
        "time_role": "TRAINING_MEMORY",
    })

    assert validate_training_contract(contract)["state"] == "REVIEWABLE"

    episode = json.loads(COURSE_BLIND_EPISODE_PATH.read_text(encoding="utf-8"))
    episode["evidence_trace"][0]["source_ref"] = "AGENTS.md"
    findings = validate_training_episode(contract, episode)["findings"]
    assert "binding.evidence_trace[0].training_memory_not_company_evidence" in findings

    materials = [
        {
            "source_id": item["source_id"],
            "source_ref": item["source_ref"],
            "content": "Source material.",
        }
        for item in contract["allowed_sources"]
    ]
    messages = build_training_agent_messages(contract, source_materials=materials)
    assert "time_role=TRAINING_MEMORY" in messages[1]["content"]
    assert "never cite it in evidence_trace" in messages[0]["content"]
    assert "three distinct economic questions" in messages[0]["content"]
    assert "must never be renamed as maintenance capital" in messages[0]["content"]


def test_contract_requires_real_multi_clock_feedback_not_duplicate_labels() -> None:
    contract = _blind_contract()
    contract["feedback_clocks"][1]["horizon"] = "EARLY_SIGNAL"
    findings = validate_training_contract(contract)["findings"]
    assert "contract.feedback_clocks_must_use_distinct_horizons" in findings


def test_complete_episode_is_the_only_primary_product_and_local_cannot_bound_survives() -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    result = validate_training_episode(contract, episode)

    assert result["state"] == "REVIEWABLE"
    assert any(
        item["treatment"] == "CANNOT_BOUND"
        for item in episode["component_treatments"]
    )

    legacy_completion = deepcopy(episode)
    legacy_completion["outcome_cells"] = [{"cell_id": "OLD:CELL"}]
    findings = validate_training_episode(contract, legacy_completion)["findings"]
    assert any("legacy_completion_forbidden" in item for item in findings)


def test_checked_in_worked_case_enters_only_through_complete_episode_contract() -> None:
    episode = _episode()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert validate_training_contract(contract)["state"] == "REVIEWABLE"
    assert validate_training_episode(contract, episode)["state"] == "REVIEWABLE"
    bundle = compile_price_free_downstream_bundle(contract, episode)
    assert bundle["primary_training_product"] == {
        "object_type": "EnterpriseUnderwritingEpisode",
        "episode_id": episode["episode_id"],
        "underwriting_thesis_id": episode["underwriting_thesis"]["thesis_id"],
    }


def test_episode_identity_and_every_consumed_source_are_contract_bound() -> None:
    episode = _episode()
    contract = _worked_contract(episode)

    wrong_identity = deepcopy(episode)
    wrong_identity["company_id"] = "CN:OTHER"
    assert "binding.company_id_mismatch" in validate_training_episode(
        contract, wrong_identity
    )["findings"]

    missing_source = deepcopy(contract)
    missing_source["allowed_sources"] = missing_source["allowed_sources"][1:]
    findings = validate_training_episode(missing_source, episode)["findings"]
    assert any("source_not_allowed" in item for item in findings)


def test_price_free_bundle_is_an_exact_projection_not_a_second_judgment() -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    bundle = compile_price_free_downstream_bundle(contract, episode)

    assert bundle["schema_version"] == DOWNSTREAM_BUNDLE_SCHEMA
    assert bundle["primary_training_product"]["episode_id"] == episode["episode_id"]
    assert bundle["projections"] == compile_underwriting_projections(episode)
    assert bundle["boundary"] == {
        "contains_outcome_results": False,
        "contains_price_or_valuation_results": False,
        "grants_investment_authority": False,
    }


def test_price_or_return_payload_is_rejected_even_outside_underwriting_thesis() -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    episode["market_price"] = 1

    findings = validate_training_episode(contract, episode)["findings"]
    assert any("price_or_return_forbidden" in item for item in findings)


def test_cli_validates_and_compiles_without_writing_another_product(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    contract_path = tmp_path / "contract.json"
    episode_path = tmp_path / "episode.json"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")

    assert main(["validate-contract", str(contract_path)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "REVIEWABLE"
    assert main(["validate-episode", str(contract_path), str(episode_path)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "REVIEWABLE"
    assert main(["compile-bundle", str(contract_path), str(episode_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == DOWNSTREAM_BUNDLE_SCHEMA
    assert payload["primary_training_product"]["object_type"] == "EnterpriseUnderwritingEpisode"


def test_formal_training_run_invokes_agent_and_only_then_persists_complete_episode(
    tmp_path: Path,
) -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    seen: list[list[dict[str, str]]] = []
    materials = [
        {
            "source_id": item["source_id"],
            "source_ref": item["source_ref"],
            "content": "Cutoff-safe source material for the complete underwriting task.",
        }
        for item in contract["allowed_sources"]
    ]

    def generator(messages: list[dict[str, str]]) -> dict:
        seen.append(messages)
        return deepcopy(episode)

    receipt = run_training_agent(
        contract,
        output_dir=tmp_path,
        episode_generator=generator,
        source_materials=materials,
    )

    assert len(seen) == 1
    assert "only product is one complete EnterpriseUnderwritingEpisode" in seen[0][0]["content"]
    assert receipt["state"] == "TRAINING_EPISODE_COMPLETED"
    persisted = json.loads((tmp_path / "enterprise_underwriting_episode.json").read_text(encoding="utf-8"))
    assert persisted == episode
    assert (tmp_path / "enterprise_underwriting_downstream_bundle.json").is_file()


def test_partial_legacy_artifact_cannot_complete_formal_training_run(tmp_path: Path) -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    materials = [
        {
            "source_id": item["source_id"],
            "source_ref": item["source_ref"],
            "content": "Cutoff-safe source material.",
        }
        for item in contract["allowed_sources"]
    ]

    with pytest.raises(ValueError, match="training_agent_episode_invalid"):
        run_training_agent(
            contract,
            output_dir=tmp_path,
            episode_generator=lambda _messages: {
                "schema_version": "legacy-training-lane.v1",
                "axes": [{"axis": "owner_cash"}],
                "receipt_completion": "PASS",
            },
            source_materials=materials,
        )

    assert not (tmp_path / "enterprise_underwriting_episode.json").exists()
    assert not (tmp_path / "enterprise_underwriting_downstream_bundle.json").exists()
