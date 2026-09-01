from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.enterprise_underwriting_episode import (
    compile_underwriting_projections,
    derive_component_decision_summary,
    derive_economic_derivation_summary,
    render_underwriting_readout,
)
from scripts.enterprise_underwriting_training import (
    COMPONENT_DECISION_INTERFACE,
    CONTRACT_SCHEMA,
    DOWNSTREAM_BUNDLE_SCHEMA,
    ECONOMIC_DERIVATION_INTERFACE,
    LEGACY_FROZEN_CONTRACT_REFS,
    PRIMARY_PRODUCT,
    SUBAGENT_TASK_SCHEMA,
    build_fresh_subagent_task,
    build_training_agent_messages,
    build_training_contract,
    compile_price_free_downstream_bundle,
    materialize_fresh_subagent_episode,
    run_training_agent,
    main,
    run_fresh_subagent_response,
    validate_training_contract,
    validate_training_episode,
    validate_fresh_subagent_response,
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
COURSE2B_ROOT = (
    ROOT
    / "docs/development/research/training_campaigns"
    / "ENTERPRISE_UNDERWRITING_COURSE_2B_CN000672_20180430"
)
REPORT_AUTONOMY_2X2_ROOT = (
    ROOT
    / "docs/development/research/training_campaigns"
    / "ENTERPRISE_UNDERWRITING_REPORT_AUTONOMY_2X2_CN000935_20180430"
)


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


def _economic_derivation() -> dict:
    return {
        "schema_version": "enterprise-underwriting-economic-derivation.v1",
        "normal_earnings_bridge": {
            "basis": {
                "metric": "after-tax normalized operating earnings",
                "currency": "RMB",
                "unit": "RMB_m",
                "tax_basis": "AFTER_TAX",
                "earnings_claim_scope": "ENTERPRISE_OPERATING",
                "operating_perimeter": "Domestic mature cement operations",
                "as_of": "2023-12-31",
            },
            "rows": [
                {
                    "row_id": "NEB:CORE",
                    "component_id": "DOMESTIC_CORE_NORMAL_EARNINGS",
                    "row_role": "REFERENCE_EARNINGS",
                    "direction": "ADD",
                    "quantification": {
                        "status": "BOUNDED", "range_low": 8000.0, "range_high": 10000.0,
                    },
                    "evidence_ids": ["CONCH-E1", "CONCH-E3"],
                    "economic_reason": "国内成熟核心按中周期量价与成本形成正常盈利范围",
                },
                {
                    "row_id": "NEB:INCREMENTAL",
                    "component_id": "DOMESTIC_INCREMENTAL_ASSET_RETURN",
                    "row_role": "NORMALIZATION_ADJUSTMENT",
                    "direction": "ADD",
                    "quantification": {
                        "status": "UNKNOWN",
                        "reason": "新增项目没有同责任边界利润与资本回收数据",
                        "conservative_treatment": "不把新增设计产能当作基准盈利",
                    },
                    "evidence_ids": ["CONCH-E4"],
                    "economic_reason": "新增国内资产盈利尚未被证明",
                },
                {
                    "row_id": "NEB:OVERSEAS",
                    "component_id": "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION",
                    "row_role": "NORMALIZATION_ADJUSTMENT",
                    "direction": "ADD",
                    "quantification": {
                        "status": "BOUNDED", "range_low": 500.0, "range_high": 900.0,
                    },
                    "evidence_ids": ["CONCH-E3"],
                    "economic_reason": "海外与产业链只作为组合缓冲",
                },
            ],
        },
        "driver_sensitivity_specs": [
            {
                "sensitivity_id": "SENS:REGIONAL_PRICE",
                "component_ids": ["DOMESTIC_CORE_NORMAL_EARNINGS"],
                "responsibility_boundary": "Domestic mature cement operations",
                "metric": "regional cement price index",
                "unit": "index",
                "horizon": "FY2026",
                "input_cases": {
                    "mode": "BOUNDED_RANGE",
                    "range": {
                        "value_or_range": {"range_low": 90.0, "range_high": 105.0},
                        "basis": "区域价格的可辩护范围",
                        "evidence_ids": ["CONCH-E1", "CONCH-E3"],
                    },
                },
                "transmission": {
                    "normal_earnings": {
                        "status": "DIRECT", "basis": "售价经吨毛利改变正常盈利",
                        "delta": {
                            "status": "BOUNDED", "range_low": -2000.0,
                            "range_high": 2000.0, "unit": "RMB_m",
                            "magnitude_evidence": {
                                "evidence_ids": ["CONCH-E2"],
                                "component_ids": [
                                    "DOMESTIC_CORE_NORMAL_EARNINGS"
                                ],
                                "responsibility_boundary": (
                                    "Domestic mature cement operations"
                                ),
                                "driver_metric": "regional cement price index",
                                "driver_unit": "index",
                                "horizon": "FY2026",
                                "affected_axis": "normal_earnings",
                                "delta_unit": "RMB_m",
                                "calculation_binding": {
                                    "calculation_id": (
                                        "CALC:REGIONAL_PRICE_TO_DOMESTIC_EARNINGS"
                                    ),
                                    "expression": (
                                        "price-index case delta times responsibility-"
                                        "matched normalized volume and unit-margin bridge"
                                    ),
                                    "input_evidence_ids": ["CONCH-E2"],
                                },
                            },
                        },
                    },
                    "owner_cash": {
                        "status": "UNKNOWN", "basis": "维护资本与现金可达性尚未闭合",
                        "delta": {
                            "status": "UNKNOWN",
                            "reason": "维护资本与现金可达性没有同口径敏感性",
                            "conservative_treatment": "不把正常盈利变化等同于普通股现金",
                        },
                    },
                    "valuation_route_ids": ["EPV"],
                },
                "reversal_observation_refs": ["#/reversal_observations/0"],
            }
        ],
    }


def _episode_with_derivation() -> dict:
    episode = _episode()
    evidence = next(
        item for item in episode["evidence_trace"]
        if item["evidence_id"] == "CONCH-E2"
    )
    evidence["sensitivity_magnitude_observation"] = {
        "component_ids": ["DOMESTIC_CORE_NORMAL_EARNINGS"],
        "responsibility_boundary": "Domestic mature cement operations",
        "driver_metric": "regional cement price index",
        "driver_unit": "index",
        "horizon": "FY2026",
        "affected_axes": ["normal_earnings"],
        "delta_unit": "RMB_m",
        "calculation_inputs": ["CONCH-E2"],
    }
    episode["economic_derivation"] = _economic_derivation()
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    return episode


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
    assert contract["schema_version"] == CONTRACT_SCHEMA
    assert contract["component_decision_interface"] == COMPONENT_DECISION_INTERFACE
    assert validate_training_contract(contract)["state"] == "REVIEWABLE"


def test_current_contract_requires_component_decisions_and_only_frozen_legacy_replays() -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    without_decisions = deepcopy(episode)
    del without_decisions["component_decisions"]
    del without_decisions["component_decision_summary"]

    findings = validate_training_episode(contract, without_decisions)["findings"]

    assert "binding.component_decisions_required_by_contract" in findings
    legacy = deepcopy(contract)
    legacy["schema_version"] = "enterprise-underwriting-training-contract.v1"
    del legacy["component_decision_interface"]
    fake_findings = validate_training_contract(legacy)["findings"]
    assert "contract.legacy_v1_payload_differs_from_frozen_contract" in fake_findings

    frozen_legacy = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert validate_training_contract(frozen_legacy)["state"] == "REVIEWABLE"
    assert validate_training_episode(frozen_legacy, without_decisions)["state"] == "REVIEWABLE"
    compile_price_free_downstream_bundle(frozen_legacy, without_decisions)
    with pytest.raises(ValueError, match="legacy_v1_replay_only"):
        build_fresh_subagent_task(frozen_legacy)
    with pytest.raises(ValueError, match="legacy_v1_replay_only"):
        run_training_agent(
            frozen_legacy,
            output_dir=ROOT / "unused-legacy-run",
            episode_generator=lambda _messages: without_decisions,
            source_materials=[],
        )

    unregistered = deepcopy(frozen_legacy)
    unregistered["contract_id"] = "UWTRAIN:UNREGISTERED:LEGACY:V1"
    assert "contract.legacy_v1_not_registered_for_frozen_replay" in (
        validate_training_contract(unregistered)["findings"]
    )


def test_optional_derivation_interface_is_backward_compatible_and_requires_derivation_only_when_present() -> None:
    legacy_current = _worked_contract()
    assert "economic_derivation_interface" not in legacy_current
    assert validate_training_episode(legacy_current, _episode())["state"] == "REVIEWABLE"

    contract = build_training_contract(
        contract_id="UWTRAIN:CN600585:20240501:WORKED:DERIVATION",
        training_track="WORKED_CASE",
        company_id=_episode()["company_id"],
        company_name=_episode()["company_name"],
        cutoff_at=_episode()["cutoff_at"],
        allowed_sources=_allowed_episode_sources(_episode()),
        feedback_clocks=_feedback_clocks(),
        economic_derivation_interface=ECONOMIC_DERIVATION_INTERFACE,
    )
    assert contract["economic_derivation_interface"] == ECONOMIC_DERIVATION_INTERFACE
    assert validate_training_contract(contract)["state"] == "REVIEWABLE"
    findings = validate_training_episode(contract, _episode())["findings"]
    assert "binding.economic_derivation_required_by_contract" in findings
    assert validate_training_episode(contract, _episode_with_derivation())[
        "state"
    ] == "REVIEWABLE"

    invalid = deepcopy(contract)
    invalid["economic_derivation_interface"]["completion_basis"] = "PROSE_ONLY"
    assert "contract.economic_derivation_interface_invalid" in (
        validate_training_contract(invalid)["findings"]
    )


def test_derivation_contract_prompt_requires_price_free_bridge_and_sensitivity() -> None:
    contract = _worked_contract()
    contract["economic_derivation_interface"] = deepcopy(
        ECONOMIC_DERIVATION_INTERFACE
    )
    messages = build_training_agent_messages(contract, source_materials=[])
    prompt = messages[0]["content"]
    assert "economic_derivation" in prompt
    assert "normal_earnings_bridge" in prompt
    assert "driver_sensitivity_specs" in prompt
    assert "exactly one REFERENCE_EARNINGS baseline" in prompt
    assert "Adjustments cannot create an authorized earnings range" in prompt
    assert "signed BOUNDED delta range that includes zero" in prompt
    assert "structured magnitude_evidence" in prompt
    assert "sensitivity_magnitude_observation" in prompt
    assert "PRESERVED [0,0] may remain" in prompt
    assert "cannot\nbe upgraded to DIRECT" in prompt
    assert "value, return, or action results" in prompt


def test_derivation_v2_contract_requires_bounded_delta_magnitude_evidence() -> None:
    contract = _worked_contract()
    contract["economic_derivation_interface"] = deepcopy(
        ECONOMIC_DERIVATION_INTERFACE
    )
    episode = _episode_with_derivation()

    assert validate_training_episode(contract, episode)["state"] == "REVIEWABLE"

    missing_magnitude = deepcopy(episode)
    del missing_magnitude["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]["delta"]["magnitude_evidence"]
    missing_magnitude["economic_derivation_summary"] = (
        derive_economic_derivation_summary(missing_magnitude)
    )
    findings = validate_training_episode(contract, missing_magnitude)["findings"]
    assert any(
        item.endswith("delta.magnitude_evidence.required_for_bounded_delta")
        for item in findings
    )


@pytest.mark.parametrize(
    ("version", "label"),
    [
        ("v3", "A00_BASELINE"),
        ("v3", "A01_INDUSTRY_ONLY"),
        ("v3", "A10_EXPERT_ONLY"),
        ("v4", "A00_BASELINE"),
        ("v4", "A01_INDUSTRY_ONLY"),
        ("v4", "A10_EXPERT_ONLY"),
        ("v4", "A11_COMBINED"),
    ],
)
def test_frozen_derivation_v1_raw_response_remains_read_only_replayable(
    version: str, label: str,
) -> None:
    contract_path = REPORT_AUTONOMY_2X2_ROOT / (
        f"contracts_{version}/CN000935_{label}_CONTRACT.json"
    )
    response_path = REPORT_AUTONOMY_2X2_ROOT / (
        f"raw_agent_responses_{version}/{label}_EPISODE_RESPONSE.json"
    )
    original_text = response_path.read_text(encoding="utf-8")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    raw = json.loads(original_text)

    assert validate_training_contract(contract)["state"] == "REVIEWABLE"
    assert validate_training_episode(contract, raw)["state"] == "INVALID"
    assert validate_fresh_subagent_response(contract, raw)["state"] == "REVIEWABLE"
    assert response_path.read_text(encoding="utf-8") == original_text
    with pytest.raises(ValueError, match="derivation_interface_v1_replay_only"):
        build_fresh_subagent_task(contract)


def test_training_run_persists_compiler_owned_derivation_summary(
    tmp_path: Path,
) -> None:
    episode = _episode_with_derivation()
    raw_agent_episode = deepcopy(episode)
    del raw_agent_episode["economic_derivation_summary"]
    contract = _worked_contract(episode)
    contract["economic_derivation_interface"] = deepcopy(
        ECONOMIC_DERIVATION_INTERFACE
    )
    materials = [
        {
            "source_id": item["source_id"],
            "source_ref": item["source_ref"],
            "content": "Cutoff-safe source material.",
        }
        for item in contract["allowed_sources"]
    ]

    run_training_agent(
        contract,
        output_dir=tmp_path,
        episode_generator=lambda _messages: raw_agent_episode,
        source_materials=materials,
    )

    persisted = json.loads(
        (tmp_path / "enterprise_underwriting_episode.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["economic_derivation_summary"] == (
        derive_economic_derivation_summary(persisted)
    )


def test_legacy_replay_registry_names_only_exact_contract_objects() -> None:
    assert LEGACY_FROZEN_CONTRACT_REFS
    assert all("/contracts/" in ref or ref.endswith("_TRAINING_CONTRACT_V1.json") for ref in LEGACY_FROZEN_CONTRACT_REFS.values())
    for contract_id, reference in LEGACY_FROZEN_CONTRACT_REFS.items():
        payload = json.loads((ROOT / reference).read_text(encoding="utf-8"))
        assert payload["contract_id"] == contract_id
        assert payload["schema_version"] == "enterprise-underwriting-training-contract.v1"
        assert validate_training_contract(payload)["state"] == "REVIEWABLE"


@pytest.mark.parametrize("arm", ["baseline", "enhanced"])
def test_frozen_course2b_v1_replay_remains_identical_to_stored_products(
    arm: str,
) -> None:
    label = arm.upper()
    contract = json.loads(
        (COURSE2B_ROOT / f"contracts/CN000672_COURSE2B_{label}_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    episode = json.loads(
        (COURSE2B_ROOT / f"arms/{arm}/enterprise_underwriting_episode.json").read_text(
            encoding="utf-8"
        )
    )
    stored_bundle = json.loads(
        (COURSE2B_ROOT / f"arms/{arm}/enterprise_underwriting_downstream_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    stored_readout = (
        COURSE2B_ROOT / f"arms/{arm}/investor_readout.md"
    ).read_text(encoding="utf-8")

    assert compile_price_free_downstream_bundle(contract, episode) == stored_bundle
    assert render_underwriting_readout(episode) == stored_readout


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
    contract["schema_version"] = CONTRACT_SCHEMA
    contract["component_decision_interface"] = deepcopy(COMPONENT_DECISION_INTERFACE)
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
    assert "cash-light merely because capex is low" in messages[0]["content"]


def test_current_training_prompt_makes_downstream_component_semantics_the_decision() -> None:
    contract = _worked_contract()
    materials = [
        {
            "source_id": item["source_id"],
            "source_ref": item["source_ref"],
            "content": "Source material.",
        }
        for item in contract["allowed_sources"]
    ]

    prompt = build_training_agent_messages(contract, source_materials=materials)[0]["content"]

    assert "exactly one entry for every" in prompt
    assert "whether it forms an owner-cash" in prompt
    assert "range, how it changes financing pressure" in prompt
    assert "label cannot substitute for them" in prompt
    assert "valuation_route_bindings" in prompt
    assert "one unrelated primary" in prompt
    assert "route_component_requirements" in prompt
    assert "optional component may remain excluded" in prompt


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
    raw_fresh = deepcopy(episode)
    raw_fresh.pop("component_decision_summary")
    raw_fresh_path = tmp_path / "fresh-response.json"
    raw_fresh_path.write_text(
        json.dumps(raw_fresh, ensure_ascii=False), encoding="utf-8"
    )
    assert main([
        "validate-fresh-response", str(contract_path), str(raw_fresh_path),
    ]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "REVIEWABLE"
    assert main(["compile-bundle", str(contract_path), str(episode_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == DOWNSTREAM_BUNDLE_SCHEMA
    assert payload["primary_training_product"]["object_type"] == "EnterpriseUnderwritingEpisode"


def test_formal_training_run_invokes_agent_and_only_then_persists_complete_episode(
    tmp_path: Path,
) -> None:
    episode = _episode()
    raw_agent_episode = deepcopy(episode)
    del raw_agent_episode["component_decision_summary"]
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
        return deepcopy(raw_agent_episode)

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
    assert persisted == materialize_fresh_subagent_episode(raw_agent_episode)
    assert persisted["component_decision_summary"] == (
        derive_component_decision_summary(persisted["component_decisions"])
    )
    assert "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION_VALUE" in persisted[
        "value_route"
    ]["excluded_routes"]
    assert (tmp_path / "enterprise_underwriting_downstream_bundle.json").is_file()


def test_fresh_materialization_is_narrow_and_preserves_exact_compiler_summaries() -> None:
    contract = _worked_contract()
    contract["economic_derivation_interface"] = deepcopy(
        ECONOMIC_DERIVATION_INTERFACE
    )
    raw = _episode_with_derivation()
    raw.pop("component_decision_summary")
    raw.pop("economic_derivation_summary")
    original = deepcopy(raw)

    materialized = materialize_fresh_subagent_episode(raw)

    assert raw == original
    assert validate_training_episode(contract, raw)["state"] == "INVALID"
    assert validate_fresh_subagent_response(contract, raw)["state"] == "REVIEWABLE"
    assert materialized["component_decision_summary"] == (
        derive_component_decision_summary(materialized["component_decisions"])
    )
    assert materialized["economic_derivation_summary"] == (
        derive_economic_derivation_summary(materialized)
    )
    assert materialized["value_route"]["excluded_routes"] == [
        "CAPACITY_GROWTH_VALUE_AS_PRIMARY",
        "ONE_PERIOD_OCF_MINUS_CAPEX_AS_OWNER_CASH",
        "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION_VALUE",
        "ORDINARY_SHARE_OWNER_CASH_VALUE",
    ]
    assert "RETURN_DECOMPOSITION" not in materialized["value_route"][
        "excluded_routes"
    ]


def test_fresh_materialization_only_canonicalizes_unknown_delta_status() -> None:
    contract = _worked_contract()
    contract["economic_derivation_interface"] = deepcopy(
        ECONOMIC_DERIVATION_INTERFACE
    )
    raw = _episode_with_derivation()
    raw.pop("component_decision_summary")
    raw.pop("economic_derivation_summary")
    normal = raw["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]
    normal["delta"] = deepcopy(
        raw["economic_derivation"]["driver_sensitivity_specs"][0][
            "transmission"
        ]["owner_cash"]["delta"]
    )
    normal["status"] = "DIRECT"

    assert any(
        item.endswith("delta.unknown_requires_unknown_transmission")
        for item in validate_training_episode(contract, raw)["findings"]
    )
    materialized = materialize_fresh_subagent_episode(raw)
    assert materialized["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]["status"] == "UNKNOWN"
    assert validate_fresh_subagent_response(contract, raw)["state"] == "REVIEWABLE"

    malformed = deepcopy(raw)
    malformed["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"] = {
        "status": "UNKNOWN",
        "basis": "错误的有界输入不得被物化为未知输入",
        "delta": {
            "status": "BOUNDED",
            "range_low": -1.0,
            "range_high": 1.0,
            "unit": "RMB_m",
        },
    }
    assert any(
        item.endswith("delta.bounded_conflicts_with_unknown_transmission")
        for item in validate_fresh_subagent_response(contract, malformed)["findings"]
    )


def test_fresh_materialization_does_not_resolve_active_excluded_route_conflicts() -> None:
    contract = _worked_contract()
    raw = _episode()
    raw.pop("component_decision_summary")
    raw["value_route"]["excluded_routes"].append("RETURN_DECOMPOSITION")

    materialized = materialize_fresh_subagent_episode(raw)

    assert materialized["value_route"]["excluded_routes"].count(
        "RETURN_DECOMPOSITION"
    ) == 1
    assert "episode:value_route.route_cannot_be_active_and_excluded:RETURN_DECOMPOSITION" in (
        validate_fresh_subagent_response(contract, raw)["findings"]
    )


def test_v3_raw_response_is_read_only_regression_input_for_fresh_materialization() -> None:
    contract_path = REPORT_AUTONOMY_2X2_ROOT / (
        "contracts_v3/CN000935_A01_INDUSTRY_ONLY_CONTRACT.json"
    )
    response_path = REPORT_AUTONOMY_2X2_ROOT / (
        "raw_agent_responses_v3/A01_INDUSTRY_ONLY_EPISODE_RESPONSE.json"
    )
    original_text = response_path.read_text(encoding="utf-8")
    raw = json.loads(original_text)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert validate_training_episode(contract, raw)["state"] == "INVALID"
    assert validate_fresh_subagent_response(contract, raw)["state"] == "REVIEWABLE"
    assert response_path.read_text(encoding="utf-8") == original_text


def test_fresh_codex_subagent_is_the_default_formal_orchestration_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    episode = _episode()
    contract = _worked_contract(episode)
    contract_path = tmp_path / "contract.json"
    task_path = tmp_path / "fresh-task.json"
    response_path = tmp_path / "fresh-response.json"
    output_dir = tmp_path / "completed"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    response_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")

    task = build_fresh_subagent_task(contract)
    assert task["schema_version"] == SUBAGENT_TASK_SCHEMA
    assert task["required_context"] == "fork_turns=none"
    assert task["execution_mode"] == "CODEX_FRESH_SUBAGENT"
    assert "only product is one complete EnterpriseUnderwritingEpisode" in task["messages"][0]["content"]

    assert main([
        "render-subagent-task", str(contract_path), "--output", str(task_path),
    ]) == 0
    render_receipt = json.loads(capsys.readouterr().out)
    assert render_receipt["state"] == "FRESH_SUBAGENT_TASK_READY"
    assert json.loads(task_path.read_text(encoding="utf-8")) == task

    assert main([
        "run", str(contract_path), "--agent-response", str(response_path),
        "--output-dir", str(output_dir),
    ]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["state"] == "TRAINING_EPISODE_COMPLETED"
    assert receipt["execution_mode"] == "CODEX_FRESH_SUBAGENT"
    assert receipt["completion_basis"] == (
        "FRESH_CODEX_SUBAGENT_GENERATED_COMPLETE_EPISODE_VALIDATED"
    )
    assert json.loads(
        (output_dir / "enterprise_underwriting_episode.json").read_text(encoding="utf-8")
    ) == materialize_fresh_subagent_episode(episode)


def test_compile_reader_brief_is_a_one_way_validated_episode_projection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    episode = _episode()
    episode_path = tmp_path / "episode.json"
    brief_path = tmp_path / "reader-brief.json"
    episode_path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")

    assert main([
        "compile-reader-brief", str(episode_path), "--output", str(brief_path),
    ]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["state"] == "READER_BRIEF_COMPILED"
    assert receipt["brief_path"] == str(brief_path.resolve())
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    assert brief["company_name"] == episode["company_name"]
    assert brief["central_judgment"] == episode["underwriting_thesis"]["central_path"]


def test_fresh_task_embeds_contract_bound_schema_for_v2_derivation() -> None:
    frozen_schema = json.loads(
        (ROOT / "schemas/enterprise_underwriting_episode_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    tasks = []
    for arm in ("A00", "A10", "A01", "A11"):
        contract = _blind_contract()
        contract["contract_id"] = f"UWTRAIN:SYNTHETIC:{arm}:V2"
        if arm in {"A01", "A11"}:
            contract["economic_derivation_interface"] = deepcopy(
                ECONOMIC_DERIVATION_INTERFACE
            )
        tasks.append(build_fresh_subagent_task(contract))

    delivered_schemas = [task["response_contract"]["episode_json_schema"] for task in tasks]
    assert delivered_schemas[:2] == [frozen_schema] * 2
    for schema in delivered_schemas[2:]:
        assert schema["$defs"]["driver_sensitivity_spec"]["required"] == [
            "sensitivity_id", "component_ids", "metric", "unit", "horizon",
            "input_cases", "transmission", "reversal_observation_refs",
            "responsibility_boundary",
        ]
    assert frozen_schema["properties"]["schema_version"]["const"] == (
        "enterprise-underwriting-episode.v2"
    )
    assert frozen_schema["properties"]["component_decisions"]["items"] == {
        "$ref": "#/$defs/component_decision"
    }
    assert frozen_schema["properties"]["economic_derivation"] == {
        "$ref": "#/$defs/economic_derivation"
    }
    assert frozen_schema["$defs"]["economic_derivation"]["required"] == [
        "schema_version",
        "normal_earnings_bridge",
        "driver_sensitivity_specs",
    ]
    assert "responsibility_boundary" not in frozen_schema[
        "$defs"
    ]["driver_sensitivity_spec"]["required"]
    assert frozen_schema["$defs"]["driver_sensitivity_spec"]["properties"][
        "responsibility_boundary"
    ] == {"$ref": "#/$defs/non_empty_string"}
    assert frozen_schema["$defs"]["sensitivity_delta_attribution"]["oneOf"][0][
        "properties"
    ]["magnitude_evidence"] == {
        "$ref": "#/$defs/sensitivity_delta_magnitude_evidence"
    }
    assert frozen_schema["$defs"]["evidence_trace_item"]["properties"][
        "sensitivity_magnitude_observation"
    ] == {"$ref": "#/$defs/sensitivity_magnitude_observation"}
    assert frozen_schema["$defs"]["sensitivity_magnitude_observation"][
        "required"
    ] == [
        "component_ids", "responsibility_boundary", "driver_metric",
        "driver_unit", "horizon", "affected_axes", "delta_unit",
        "calculation_inputs",
    ]
    assert frozen_schema["additionalProperties"] is False
    assert frozen_schema["dependentRequired"]["economic_derivation"] == [
        "component_decisions",
    ]
    assert "component_decision_summary" not in frozen_schema.get(
        "dependentRequired", {}
    ).get("component_decisions", [])
    assert frozen_schema["properties"]["evidence_trace"]["items"] == {
        "$ref": "#/$defs/evidence_trace_item"
    }
    assert frozen_schema["$defs"]["evidence_trace_item"]["required"] == [
        "evidence_id", "source_ref", "locator", "scope", "used_for",
    ]
    assert frozen_schema["$defs"]["evidence_trace_item"][
        "additionalProperties"
    ] is False
    assert frozen_schema["$defs"]["existing_object_ref"]["required"] == [
        "kind", "ref", "role",
    ]
    assert frozen_schema["$defs"]["underwriting_thesis"][
        "additionalProperties"
    ] is False
    assert "monitoring" in frozen_schema["$defs"]["underwriting_thesis"][
        "required"
    ]

    response_contract = tasks[2]["response_contract"]
    requirements = "\n".join(response_contract["schema_requirements"])
    assert response_contract["schema_authority"] == (
        "CONTRACT_BOUND_EXECUTION_EPISODE_JSON_SCHEMA"
    )
    assert "required" in requirements
    assert "enum and const" in requirements
    assert "additionalProperties is false" in requirements
    semantic_requirements = "\n".join(
        response_contract["semantic_requirements"]
    )
    assert "Copy industry_future_thesis.strongest_rival verbatim" in (
        semantic_requirements
    )
    assert "scope, and used_for" in semantic_requirements
    assert "kind, ref, and role" in semantic_requirements
    assert "valuation_use is derived from route bindings" in semantic_requirements
    assert "primary, corroborative, stress, or excluded route" in semantic_requirements
    assert "normal_earnings_use is not NOT_APPLICABLE" in semantic_requirements
    assert "UNKNOWN uses an UNKNOWN delta" in semantic_requirements
    assert "separate calculation-bound magnitude evidence" in semantic_requirements
    assert "canonical evidence_trace sensitivity_magnitude_observation" in (
        semantic_requirements
    )
    assert "binding uses match route roles" in semantic_requirements
    assert "Every driver sensitivity itself must include" in tasks[2]["messages"][0]["content"]
    assert "only derives" in semantic_requirements
    assert "does not supply economics" in semantic_requirements
    assert "response_contract.episode_json_schema" in tasks[0]["messages"][0][
        "content"
    ]


def test_v2_fresh_task_boundary_requirement_matches_binding_validator() -> None:
    contract = _blind_contract()
    contract["economic_derivation_interface"] = deepcopy(
        ECONOMIC_DERIVATION_INTERFACE
    )
    task = build_fresh_subagent_task(contract)
    required = task["response_contract"]["episode_json_schema"]["$defs"][
        "driver_sensitivity_spec"
    ]["required"]
    assert "responsibility_boundary" in required

    episode = _episode_with_derivation()
    del episode["economic_derivation"]["driver_sensitivity_specs"][0][
        "responsibility_boundary"
    ]
    missing_boundary = validate_training_episode(contract, episode)["findings"]
    assert any(
        item.endswith("responsibility_boundary_required_by_interface_v2")
        for item in missing_boundary
    )

    episode["economic_derivation"]["driver_sensitivity_specs"][0][
        "responsibility_boundary"
    ] = "Domestic mature cement operations"
    present_boundary = validate_training_episode(contract, episode)["findings"]
    assert not any(
        item.endswith("responsibility_boundary_required_by_interface_v2")
        for item in present_boundary
    )


def test_schema_conforming_mock_response_passes_existing_fresh_binding(
    tmp_path: Path,
) -> None:
    completed_response = _episode_with_derivation()
    agent_response = deepcopy(completed_response)
    agent_response.pop("component_decision_summary")
    agent_response.pop("economic_derivation_summary")
    contract = _worked_contract(completed_response)
    contract["economic_derivation_interface"] = deepcopy(
        ECONOMIC_DERIVATION_INTERFACE
    )

    frozen_schema = json.loads(
        (ROOT / "schemas/enterprise_underwriting_episode_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    try:
        import jsonschema
    except ModuleNotFoundError:
        pass
    else:
        jsonschema.Draft202012Validator(frozen_schema).validate(agent_response)
    receipt = run_fresh_subagent_response(
        contract,
        agent_response=agent_response,
        output_dir=tmp_path,
    )

    assert receipt["state"] == "TRAINING_EPISODE_COMPLETED"
    assert receipt["execution_mode"] == "CODEX_FRESH_SUBAGENT"
    assert json.loads(
        (tmp_path / "enterprise_underwriting_episode.json").read_text(
            encoding="utf-8"
        )
    ) == materialize_fresh_subagent_episode(agent_response)


def test_subagent_finalizer_rejects_partial_or_unbound_response(tmp_path: Path) -> None:
    contract = _worked_contract()
    with pytest.raises(ValueError, match="training_agent_episode_invalid"):
        run_fresh_subagent_response(
            contract,
            agent_response={"schema_version": "legacy-training-lane.v1"},
            output_dir=tmp_path,
        )

    assert not (tmp_path / "enterprise_underwriting_episode.json").exists()


def test_external_provider_is_explicit_not_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    parser = __import__(
        "scripts.enterprise_underwriting_training", fromlist=["_parser"]
    )._parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "contract.json", "--output-dir", "out"])

    parsed = parser.parse_args([
        "run", "contract.json", "--output-dir", "out", "--provider", "anthropic",
    ])
    assert parsed.provider == "anthropic"
    assert parsed.agent_response is None

    with pytest.raises(SystemExit):
        parser.parse_args([
            "run", "contract.json", "--output-dir", "out",
            "--agent-response", "response.json", "--provider", "anthropic",
        ])

    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps(_worked_contract(), ensure_ascii=False), encoding="utf-8"
    )
    assert main([
        "run", str(contract_path), "--output-dir", str(tmp_path / "out"),
        "--agent-response", str(tmp_path / "response.json"), "--model", "named-model",
    ]) == 1
    error = json.loads(capsys.readouterr().out)
    assert error["findings"] == ["--model requires explicit --provider"]


def test_documented_direct_script_entrypoint_can_start_without_pythonpath() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/enterprise_underwriting_training.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0
    assert "render-subagent-task" in completed.stdout


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
