from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.enterprise_underwriting_episode import (
    compile_golden_report_reader_brief,
    compile_underwriting_projections,
    derive_component_decision_summary,
    derive_economic_derivation_summary,
    project_price_free_underwriting_thesis,
    render_underwriting_readout,
    validate_enterprise_underwriting_episode,
    validate_golden_report_reader_brief,
    validate_price_free_underwriting_thesis_projection,
    validate_underwriting_projection_bundle,
)
from scripts.valuation_value_bridges import (
    compile_valuation_value_bridges,
    validate_valuation_value_bridges,
)


ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "docs/development/research/enterprise_underwriting_episodes"
INDUSTRY_FUTURE_FIELDS = {
    "horizon",
    "most_likely_regime",
    "profit_pool_transmission",
    "company_exposure",
    "adaptation",
    "normal_economics",
    "permanent_loss",
    "valuation_treatment",
    "strongest_rival",
    "reversal_observations",
}


def _episode(name: str) -> dict:
    return json.loads((EPISODES / name).read_text(encoding="utf-8"))


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
                    "economic_reason": "新增国内资产盈利尚未被客户吸收和现金回收证明",
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
                    "economic_reason": "海外与产业链只作为尚未晋级的组合缓冲",
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
                    "mode": "LOW_BASE_HIGH",
                    "low": {
                        "value_or_range": {"value": 90.0},
                        "basis": "区域价格继续承压",
                        "evidence_ids": ["CONCH-E1"],
                    },
                    "base": {
                        "value_or_range": {"range_low": 95.0, "range_high": 100.0},
                        "basis": "中周期价格范围",
                        "evidence_ids": ["CONCH-E1", "CONCH-E3"],
                    },
                    "high": {
                        "value_or_range": {"value": 105.0},
                        "basis": "供给退出带来修复",
                        "evidence_ids": ["CONCH-E3"],
                    },
                },
                "transmission": {
                    "normal_earnings": {
                        "status": "DIRECT",
                        "basis": "区域售价经吨毛利直接改变国内核心正常盈利",
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
                        "status": "UNKNOWN",
                        "basis": "维护资本与普通股现金可达性尚未闭合",
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
    episode = _episode("CN600585_20240501_WORKED_CASE_V1.json")
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
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(
        episode
    )
    return episode


def test_worked_cases_are_reviewable_and_reuse_only_existing_sources() -> None:
    for name in ("MAGNA_200903_WORKED_CASE_V1.json", "CN600585_20240501_WORKED_CASE_V1.json"):
        episode = _episode(name)
        assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
        for evidence in episode["evidence_trace"]:
            assert (ROOT / evidence["source_ref"]).is_file()
        for reference in episode["existing_object_refs"]:
            assert (ROOT / reference["ref"]).is_file()


def test_worked_cases_own_one_structured_industry_future_thesis() -> None:
    for name in ("MAGNA_200903_WORKED_CASE_V1.json", "CN600585_20240501_WORKED_CASE_V1.json"):
        episode = _episode(name)
        industry_future = episode["situation_model"]["industry_future_thesis"]

        assert set(industry_future) == INDUSTRY_FUTURE_FIELDS
        assert episode["strongest_rival"] == industry_future["strongest_rival"]
        assert episode["underwriting_thesis"]["strongest_rival"] == industry_future["strongest_rival"]
        assert episode["reversal_observations"] == industry_future["reversal_observations"]


def test_schema_makes_industry_future_thesis_part_of_situation_model() -> None:
    schema = json.loads(
        (ROOT / "schemas/enterprise_underwriting_episode_v1.schema.json").read_text(encoding="utf-8")
    )
    situation = schema["$defs"]["situation_model"]
    industry_future = schema["$defs"]["industry_future_thesis"]

    assert schema["properties"]["schema_version"]["const"] == "enterprise-underwriting-episode.v2"
    assert situation["required"] == ["summary", "industry_future_thesis"]
    assert set(industry_future["required"]) == INDUSTRY_FUTURE_FIELDS
    assert schema["properties"]["underwriting_thesis"] == {
        "$ref": "#/$defs/underwriting_thesis"
    }
    assert "economic_directions" in schema["$defs"]["underwriting_thesis"]["required"]
    assert schema["$defs"]["value_route"]["properties"]["valuation_model_roles"]["required"] == ["primary"]
    assert "component_decisions" in schema["properties"]
    assert "component_decisions" not in schema["required"]
    assert "component_decisions" not in schema.get("dependentRequired", {})
    assert "valuation_route_bindings" in schema["$defs"][
        "component_decision"
    ]["required"]
    assert "route_component_bindings" in schema["$defs"][
        "valuation_component_route"
    ]["required"]
    assert "route_component_requirements" in schema["$defs"][
        "value_route"
    ]["properties"]
    assert "economic_derivation" in schema["properties"]
    assert "economic_derivation" not in schema["required"]
    assert schema["dependentRequired"]["economic_derivation"] == [
        "component_decisions"
    ]


def test_economic_derivation_compiles_component_uses_and_reader_safe_sections() -> None:
    episode = _episode_with_derivation()

    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
    summary = episode["economic_derivation_summary"]
    rows = {item["row_id"]: item for item in summary["normal_earnings_bridge"]["rows"]}
    assert rows["NEB:CORE"]["normal_earnings_use"] == "CONDITIONAL_RANGE"
    assert rows["NEB:INCREMENTAL"]["normal_earnings_use"] == "EXCLUDED"
    assert rows["NEB:OVERSEAS"]["normal_earnings_use"] == "SCENARIO_ONLY"
    assert summary["normal_earnings_bridge"]["conditional_range"] == {
        "status": "BOUNDED", "range_low": 8000.0, "range_high": 10000.0,
    }
    assert summary["normal_earnings_bridge"]["totals_by_use"]["EXCLUDED"] == {
        "status": "UNKNOWN", "unknown_row_ids": ["NEB:INCREMENTAL"],
    }
    sensitivity = summary["driver_sensitivities"][0]
    assert sensitivity["normal_earnings_uses"] == {
        "DOMESTIC_CORE_NORMAL_EARNINGS": "CONDITIONAL_RANGE"
    }
    assert sensitivity["owner_cash_uses"] == {
        "DOMESTIC_CORE_NORMAL_EARNINGS": "UNRESOLVED"
    }
    assert sensitivity["valuation_route_attributions"][0] == {
        "route_id": "EPV",
        "route_role": "PRIMARY",
        "component_valuation_uses": {
            "DOMESTIC_CORE_NORMAL_EARNINGS": "CONDITIONAL_PRIMARY_INPUT"
        },
    }

    projections = compile_underwriting_projections(episode)
    assert projections["valuation_route_request"]["economic_derivation"] == episode[
        "economic_derivation"
    ]
    assert projections["valuation_route_request"]["economic_derivation_summary"] == summary
    assert projections["golden_report_underwriting_handoff"][
        "economic_derivation_summary"
    ] == summary

    brief = compile_golden_report_reader_brief(episode)
    headings = [item["heading"] for item in brief["sections"]]
    assert "正常盈利组件桥" in headings
    assert "关键敏感性与翻转条件" in headings
    serialized = json.dumps(brief, ensure_ascii=False)
    assert "中周期量价与成本" in serialized
    assert "区域售价经吨毛利" in serialized
    assert "影响范围 -2000–2000 RMB_m" in serialized
    assert "影响未知" in serialized
    assert "只进入条件性价值路线" in serialized
    assert "NEB:CORE" not in serialized
    assert "SENS:REGIONAL_PRICE" not in serialized
    assert "DOMESTIC_CORE_NORMAL_EARNINGS" not in serialized


def test_bridge_rejects_duplicate_component_role_and_requires_one_reference_row() -> None:
    episode = _episode_with_derivation()
    duplicate = deepcopy(
        episode["economic_derivation"]["normal_earnings_bridge"]["rows"][0]
    )
    duplicate["row_id"] = "NEB:CORE:COPY"
    episode["economic_derivation"]["normal_earnings_bridge"]["rows"].append(
        duplicate
    )
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    findings = validate_enterprise_underwriting_episode(
        episode,
        require_bounded_sensitivity_magnitude_evidence=True,
    )["findings"]
    assert any("component_role_duplicate" in item for item in findings)
    assert any("requires_exactly_one_reference_earnings_row" in item for item in findings)

    episode = _episode_with_derivation()
    episode["economic_derivation"]["normal_earnings_bridge"]["rows"][0][
        "row_role"
    ] = "NORMALIZATION_ADJUSTMENT"
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    assert any(
        "requires_exactly_one_reference_earnings_row" in item
        for item in validate_enterprise_underwriting_episode(episode)["findings"]
    )


def test_authorized_range_cannot_be_built_from_adjustments_without_authorized_reference() -> None:
    episode = _episode_with_derivation()
    rows = episode["economic_derivation"]["normal_earnings_bridge"]["rows"]
    rows[0]["row_role"] = "NORMALIZATION_ADJUSTMENT"
    rows[2]["row_role"] = "REFERENCE_EARNINGS"
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    findings = validate_enterprise_underwriting_episode(episode)["findings"]
    assert any(
        "conditional_range_requires_conditional_reference_earnings" in item
        for item in findings
    )
    assert episode["economic_derivation_summary"]["normal_earnings_bridge"][
        "conditional_range"
    ] == {
        "status": "UNKNOWN",
        "reason": "REFERENCE_EARNINGS_NOT_AUTHORIZED_FOR_CONDITIONAL_RANGE",
    }

    episode = _episode_with_derivation()
    rows = episode["economic_derivation"]["normal_earnings_bridge"]["rows"]
    rows[0]["row_role"] = "NORMALIZATION_ADJUSTMENT"
    rows[2]["row_role"] = "REFERENCE_EARNINGS"
    core = next(
        item for item in episode["component_decisions"]
        if item["component_id"] == "DOMESTIC_CORE_NORMAL_EARNINGS"
    )
    core["normal_earnings_use"] = "BASE_RANGE"
    episode["component_decision_summary"] = derive_component_decision_summary(
        episode["component_decisions"]
    )
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    findings = validate_enterprise_underwriting_episode(episode)["findings"]
    assert any(
        "base_range_requires_base_reference_earnings" in item
        for item in findings
    )
    assert episode["economic_derivation_summary"]["normal_earnings_bridge"][
        "base_range"
    ] == {
        "status": "UNKNOWN",
        "reason": "REFERENCE_EARNINGS_NOT_AUTHORIZED_FOR_BASE_RANGE",
    }


@pytest.mark.parametrize(
    ("reference_use", "reader_label"),
    [("EXCLUDED", "排除"), ("SCENARIO_ONLY", "只进入情景")],
)
def test_reference_may_be_excluded_when_no_range_authority_exists(
    reference_use: str, reader_label: str,
) -> None:
    episode = _episode_with_derivation()
    core = next(
        item for item in episode["component_decisions"]
        if item["component_id"] == "DOMESTIC_CORE_NORMAL_EARNINGS"
    )
    core["normal_earnings_use"] = reference_use
    episode["economic_derivation"]["normal_earnings_bridge"]["rows"][0][
        "economic_reason"
    ] = "国内核心参考盈利约 8000–10000 RMB_m，但尚未获准进入范围"
    episode["component_decision_summary"] = derive_component_decision_summary(
        episode["component_decisions"]
    )
    normal = episode["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]
    normal.clear()
    normal.update({
        "status": "UNKNOWN",
        "basis": "正常盈利权限已排除",
        "delta": {
            "status": "UNKNOWN",
            "reason": "没有获准的正常盈利基线",
            "conservative_treatment": "不形成正常盈利范围",
        },
    })
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
    bridge = episode["economic_derivation_summary"]["normal_earnings_bridge"]
    assert bridge["base_range"] is None
    assert bridge["conditional_range"] is None
    serialized = json.dumps(
        compile_golden_report_reader_brief(episode), ensure_ascii=False
    )
    assert "基准范围没有获授权的组件" in serialized
    assert "含条件项范围没有获授权的组件" in serialized
    assert "基准范围勾稽为" not in serialized
    assert "含条件项范围勾稽为" not in serialized
    assert "带符号范围 8000–10000" not in serialized
    assert (
        "该组件未获授权进入读者正常盈利数值桥；组件权限："
        + reader_label
    ) in serialized
    assert "国内核心参考盈利约" not in serialized
    assert "带符号范围 500–900" not in serialized


def test_economic_derivation_use_is_only_derived_from_component_decisions() -> None:
    episode = _episode_with_derivation()
    episode["economic_derivation"]["normal_earnings_bridge"]["rows"][0][
        "normal_earnings_use"
    ] = "BASE_RANGE"
    findings = validate_enterprise_underwriting_episode(episode)["findings"]
    assert any("economic_derivation.normal_earnings_bridge.rows[0].fields_invalid" in item for item in findings)

    episode = _episode_with_derivation()
    core = next(
        item for item in episode["component_decisions"]
        if item["component_id"] == "DOMESTIC_CORE_NORMAL_EARNINGS"
    )
    core["normal_earnings_use"] = "BASE_RANGE"
    episode["component_decision_summary"] = derive_component_decision_summary(
        episode["component_decisions"]
    )
    assert "economic_derivation_summary.not_exact_deterministic_derivation" in (
        validate_enterprise_underwriting_episode(episode)["findings"]
    )
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
    assert episode["economic_derivation_summary"]["normal_earnings_bridge"][
        "base_range"
    ]["range_low"] == 8000.0


def test_unknown_normal_earnings_row_never_becomes_zero() -> None:
    episode = _episode_with_derivation()
    core = episode["economic_derivation"]["normal_earnings_bridge"]["rows"][0]
    core["quantification"] = {
        "status": "UNKNOWN",
        "reason": "同口径中周期利润无法界定",
        "conservative_treatment": "保留条件性方向，不填零或点估计",
    }
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    summary = episode["economic_derivation_summary"]["normal_earnings_bridge"]
    assert summary["conditional_range"] == {
        "status": "UNKNOWN", "unknown_row_ids": ["NEB:CORE"],
    }
    assert "range_low" not in summary["conditional_range"]
    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"


def test_bounded_range_sensitivity_is_reader_visible_without_internal_ids() -> None:
    episode = _episode_with_derivation()
    episode["economic_derivation"]["driver_sensitivity_specs"][0]["input_cases"] = {
        "mode": "BOUNDED_RANGE",
        "range": {
            "value_or_range": {"range_low": 92.0, "range_high": 103.0},
            "basis": "公开证据支持的可辩护范围",
            "evidence_ids": ["CONCH-E1", "CONCH-E3"],
        },
    }
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    brief = compile_golden_report_reader_brief(episode)
    serialized = json.dumps(brief, ensure_ascii=False)
    assert "范围 92–103" in serialized
    assert "SENS:REGIONAL_PRICE" not in serialized


@pytest.mark.parametrize(
    ("component_id", "axis"),
    [
        ("DOMESTIC_INCREMENTAL_ASSET_RETURN", "normal_earnings"),
        ("OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION", "normal_earnings"),
        ("DOMESTIC_CORE_NORMAL_EARNINGS", "owner_cash"),
    ],
)
def test_sensitivity_direct_effect_requires_component_axis_authority(
    component_id: str,
    axis: str,
) -> None:
    episode = _episode_with_derivation()
    spec = episode["economic_derivation"]["driver_sensitivity_specs"][0]
    spec["component_ids"] = [component_id]
    spec["transmission"][axis] = {
        "status": "DIRECT",
        "basis": "试图直接进入该经济轴",
        "delta": {
            "status": "BOUNDED", "range_low": -1.0,
            "range_high": 1.0, "unit": "RMB_m",
        },
    }
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    findings = validate_enterprise_underwriting_episode(episode)["findings"]
    assert any(
        f"transmission.{axis}.direct_not_authorized_by_component_decisions" in item
        for item in findings
    )


@pytest.mark.parametrize(
    ("delta", "finding"),
    [
        (
            {"status": "BOUNDED", "range_low": 1.0, "range_high": 2.0, "unit": "RMB_m"},
            "range_must_be_signed_and_include_zero",
        ),
        (
            {"status": "BOUNDED", "range_low": -2.0, "range_high": -1.0, "unit": "RMB_m"},
            "range_must_be_signed_and_include_zero",
        ),
    ],
)
def test_sensitivity_delta_range_must_include_zero(delta: dict, finding: str) -> None:
    episode = _episode_with_derivation()
    episode["economic_derivation"]["driver_sensitivity_specs"][0]["transmission"][
        "normal_earnings"
    ]["delta"] = delta
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    assert any(
        finding in item
        for item in validate_enterprise_underwriting_episode(episode)["findings"]
    )


def test_bounded_sensitivity_delta_requires_its_own_magnitude_evidence() -> None:
    episode = _episode_with_derivation()
    delta = episode["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]["delta"]
    del delta["magnitude_evidence"]
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    findings = validate_enterprise_underwriting_episode(
        episode,
        require_bounded_sensitivity_magnitude_evidence=True,
    )["findings"]
    assert any(
        item.endswith("delta.magnitude_evidence.required_for_bounded_delta")
        for item in findings
    )


@pytest.mark.parametrize(
    ("mutate", "finding"),
    [
        (
            lambda value: value.update(evidence_ids=["CONCH-E1"]),
            "cannot_reuse_driver_case_evidence",
        ),
        (
            lambda value: value.update(
                responsibility_boundary="parent-only cement operations"
            ),
            "responsibility_boundary_incompatible",
        ),
        (
            lambda value: value.update(driver_metric="national cement price index"),
            "driver_metric_incompatible",
        ),
        (
            lambda value: value.update(driver_unit="percent"),
            "driver_unit_incompatible",
        ),
        (
            lambda value: value.update(horizon="FY2027"),
            "horizon_incompatible",
        ),
        (
            lambda value: value.update(delta_unit="RMB"),
            "delta_unit_incompatible",
        ),
    ],
)
def test_bounded_delta_magnitude_evidence_must_match_its_sensitivity(
    mutate, finding: str,
) -> None:
    episode = _episode_with_derivation()
    magnitude = episode["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]["delta"]["magnitude_evidence"]
    mutate(magnitude)
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    assert any(
        item.endswith("delta.magnitude_evidence." + finding)
        for item in validate_enterprise_underwriting_episode(episode)["findings"]
    )


def test_same_component_boundary_calculation_binding_supports_bounded_delta() -> None:
    episode = _episode_with_derivation()

    assert validate_enterprise_underwriting_episode(
        episode,
        require_bounded_sensitivity_magnitude_evidence=True,
    )["state"] == "REVIEWABLE"


@pytest.mark.parametrize(
    ("mutate", "finding"),
    [
        (
            lambda value: value.update(component_ids=["OTHER_COMPONENT"]),
            "component_ids_incompatible",
        ),
        (
            lambda value: value.update(responsibility_boundary="parent only"),
            "responsibility_boundary_incompatible",
        ),
        (
            lambda value: value.update(driver_metric="national price index"),
            "driver_metric_incompatible",
        ),
        (
            lambda value: value.update(driver_unit="percent"),
            "driver_unit_incompatible",
        ),
        (
            lambda value: value.update(horizon="FY2027"),
            "horizon_incompatible",
        ),
        (
            lambda value: value.update(affected_axes=["owner_cash"]),
            "affected_axes_incompatible",
        ),
        (
            lambda value: value.update(delta_unit="RMB"),
            "delta_unit_incompatible",
        ),
        (
            lambda value: value.update(calculation_inputs=["CONCH-E3"]),
            "calculation_inputs_incompatible",
        ),
    ],
)
def test_v2_bounded_delta_must_match_trace_metadata_not_its_repeated_labels(
    mutate, finding: str,
) -> None:
    episode = _episode_with_derivation()
    trace = next(
        item for item in episode["evidence_trace"]
        if item["evidence_id"] == "CONCH-E2"
    )
    mutate(trace["sensitivity_magnitude_observation"])
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    findings = validate_enterprise_underwriting_episode(
        episode,
        require_bounded_sensitivity_magnitude_evidence=True,
    )["findings"]
    assert any(
        item.endswith("trace_metadata[CONCH-E2]." + finding)
        for item in findings
    )


def test_preserved_zero_delta_does_not_need_extra_magnitude_evidence() -> None:
    episode = _episode_with_derivation()
    normal = episode["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]
    normal["status"] = "PRESERVED"
    normal["basis"] = "该驱动不改变已经固定的正常盈利范围"
    normal["delta"] = {
        "status": "BOUNDED", "range_low": 0.0, "range_high": 0.0,
        "unit": "RMB_m",
    }
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"


def test_unknown_delta_has_no_reader_facing_direct_numeric_attribution() -> None:
    episode = _episode_with_derivation()
    normal = episode["economic_derivation"]["driver_sensitivity_specs"][0][
        "transmission"
    ]["normal_earnings"]
    normal["status"] = "UNKNOWN"
    normal["basis"] = "这段自由文字声称会直接影响正常盈利"
    normal["delta"] = {
        "status": "UNKNOWN",
        "reason": "没有同责任边界的量级计算",
        "conservative_treatment": "不形成数值归因",
    }
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
    serialized = json.dumps(
        compile_golden_report_reader_brief(episode), ensure_ascii=False,
    )
    assert "这段自由文字声称会直接影响正常盈利" not in serialized
    assert "影响未知：没有同责任边界的量级计算" in serialized
    assert "影响范围 -2000–2000 RMB_m" not in serialized


def test_sensitivity_route_requires_exact_component_binding_use_and_route_role() -> None:
    episode = _episode_with_derivation()
    spec = episode["economic_derivation"]["driver_sensitivity_specs"][0]
    spec["component_ids"] = ["CONSOLIDATED_SURVIVAL_AND_FINANCING"]
    spec["transmission"]["normal_earnings"] = {
        "status": "UNKNOWN",
        "basis": "该组件不形成正常盈利输入",
        "delta": {
            "status": "UNKNOWN", "reason": "不适用",
            "conservative_treatment": "不进入正常盈利归因",
        },
    }
    spec["transmission"]["valuation_route_ids"] = ["ASSET_VALUE"]
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    assert any(
        "route_binding_use_incompatible_with_route_role" in item
        for item in validate_enterprise_underwriting_episode(episode)["findings"]
    )


def test_excluded_sensitivity_keeps_excluded_route_semantics_in_summary_and_reader() -> None:
    episode = _episode_with_derivation()
    spec = episode["economic_derivation"]["driver_sensitivity_specs"][0]
    spec["component_ids"] = ["DOMESTIC_INCREMENTAL_ASSET_RETURN"]
    for axis in ("normal_earnings", "owner_cash"):
        spec["transmission"][axis] = {
            "status": "UNKNOWN",
            "basis": "组件权限为排除，不能直接形成影响数值",
            "delta": {
                "status": "UNKNOWN", "reason": "缺少可承保归因",
                "conservative_treatment": "维持排除",
            },
        }
    spec["transmission"]["valuation_route_ids"] = [
        "CAPACITY_GROWTH_VALUE_AS_PRIMARY"
    ]
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
    attribution = episode["economic_derivation_summary"]["driver_sensitivities"][0][
        "valuation_route_attributions"
    ][0]
    assert attribution["route_role"] == "EXCLUDED"
    assert set(attribution["component_valuation_uses"].values()) == {"EXCLUDED"}
    serialized = json.dumps(
        compile_golden_report_reader_brief(episode), ensure_ascii=False
    )
    assert "相关价值路线被排除" in serialized
    assert "进入既定价值路线" not in serialized
    assert "DOMESTIC_INCREMENTAL_ASSET_RETURN" not in serialized


def test_scenario_sensitivity_stays_scenario_only_in_summary_and_reader() -> None:
    episode = _episode_with_derivation()
    episode["value_route"]["excluded_routes"].append(
        "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION_VALUE"
    )
    spec = episode["economic_derivation"]["driver_sensitivity_specs"][0]
    spec["component_ids"] = ["OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION"]
    for axis in ("normal_earnings", "owner_cash"):
        spec["transmission"][axis] = {
            "status": "UNKNOWN",
            "basis": "组件仍只有情景或未决权限",
            "delta": {
                "status": "UNKNOWN", "reason": "缺少晋级证据",
                "conservative_treatment": "不进入基准或条件范围",
            },
        }
    spec["transmission"]["valuation_route_ids"] = [
        "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION_VALUE"
    ]
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)

    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
    sensitivity = episode["economic_derivation_summary"]["driver_sensitivities"][0]
    assert set(sensitivity["normal_earnings_uses"].values()) == {"SCENARIO_ONLY"}
    assert set(
        sensitivity["valuation_route_attributions"][0][
            "component_valuation_uses"
        ].values()
    ) == {"SCENARIO_ONLY"}
    serialized = json.dumps(
        compile_golden_report_reader_brief(episode), ensure_ascii=False
    )
    assert "只进入情景" in serialized
    assert "只保留情景价值路线，不进入基准价值" in serialized
    assert "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION" not in serialized


@pytest.mark.parametrize(
    ("mutate", "finding"),
    [
        (
            lambda value: value["normal_earnings_bridge"]["rows"][0].update(
                component_id="NOT:A:COMPONENT"
            ),
            "component_id_unknown",
        ),
        (
            lambda value: value["normal_earnings_bridge"]["rows"][0].update(
                evidence_ids=["NOT:EVIDENCE"]
            ),
            "evidence_ids_invalid",
        ),
        (
            lambda value: value["driver_sensitivity_specs"][0]["transmission"].update(
                valuation_route_ids=["NOT:A:ROUTE"]
            ),
            "valuation_route_id_unknown",
        ),
        (
            lambda value: value["driver_sensitivity_specs"][0].update(
                reversal_observation_refs=["#/reversal_observations/99"]
            ),
            "reversal_observation_ref_invalid",
        ),
    ],
)
def test_economic_derivation_references_must_resolve(mutate, finding: str) -> None:
    episode = _episode_with_derivation()
    mutate(episode["economic_derivation"])
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    assert any(
        finding in item
        for item in validate_enterprise_underwriting_episode(episode)["findings"]
    )


@pytest.mark.parametrize("forbidden_key", ["value_per_share", "expected_return", "action"])
def test_economic_derivation_remains_price_free(forbidden_key: str) -> None:
    episode = _episode_with_derivation()
    episode["economic_derivation"]["driver_sensitivity_specs"][0][forbidden_key] = 1
    episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    assert any(
        "economic_derivation.price_boundary" in item and forbidden_key in item
        for item in validate_enterprise_underwriting_episode(episode)["findings"]
    )


def test_explicit_component_decisions_are_validated_and_drive_base_exclusions() -> None:
    episode = _episode("CN600585_20240501_WORKED_CASE_V1.json")

    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
    bundle = compile_underwriting_projections(episode)
    valuation = bundle["valuation_route_request"]
    assert valuation["component_decisions"] == episode["component_decisions"]
    assert valuation["inputs_excluded_from_base"] == [
        "CONSOLIDATED_SURVIVAL_AND_FINANCING",
        "DOMESTIC_INCREMENTAL_ASSET_RETURN",
        "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION",
        "ORDINARY_SHARE_OWNER_CASH",
    ]
    assert bundle["cjo_candidate_projection"]["component_decisions"] == episode["component_decisions"]
    assert bundle["golden_report_underwriting_handoff"]["component_decisions"] == episode["component_decisions"]
    assert episode["component_decision_summary"] == derive_component_decision_summary(
        episode["component_decisions"]
    )
    assert valuation["valuation_component_route"] == episode[
        "component_decision_summary"
    ]["valuation"]
    assert bundle["golden_report_underwriting_handoff"][
        "component_economic_routes"
    ] == episode["component_decision_summary"]
    reader_brief = compile_golden_report_reader_brief(episode)
    assert all("权威经济去向" in item for item in reader_brief["component_judgments"])
    assert valuation["owner_cash_input_treatment"] != episode[
        "underwriting_thesis"
    ]["owner_cash_treatment"]
    assert "未授权形成基准或条件性 owner-cash 范围" in valuation[
        "owner_cash_input_treatment"
    ]


@pytest.mark.parametrize(
    ("component_id", "field", "replacement", "projection", "route_field"),
    [
        (
            "OVERSEAS_AND_INDUSTRIAL_CHAIN_OPTION",
            "normal_earnings_use",
            "EXCLUDED",
            "cjo_candidate_projection",
            "normal_earnings_component_route",
        ),
        (
            "ORDINARY_SHARE_OWNER_CASH",
            "owner_cash_use",
            "SCENARIO_ONLY",
            "cjo_candidate_projection",
            "owner_cash_component_route",
        ),
        (
            "DOMESTIC_CORE_NORMAL_EARNINGS",
            "financing_pressure_effect",
            "REDUCES",
            "cjo_candidate_projection",
            "financing_pressure_component_route",
        ),
        (
            "ORDINARY_SHARE_OWNER_CASH",
            "permanent_loss_use",
            "STRESS_ONLY",
            "cjo_candidate_projection",
            "permanent_loss_component_route",
        ),
        (
            "CONSOLIDATED_SURVIVAL_AND_FINANCING",
            "valuation_use",
            "STRESS_ONLY",
            "valuation_route_request",
            "valuation_component_route",
        ),
    ],
)
def test_each_component_decision_dimension_changes_its_downstream_route(
    component_id: str,
    field: str,
    replacement: str,
    projection: str,
    route_field: str,
) -> None:
    original = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    mutated = deepcopy(original)
    decision = next(
        item for item in mutated["component_decisions"]
        if item["component_id"] == component_id
    )
    decision[field] = replacement
    if field == "valuation_use":
        for binding in decision["valuation_route_bindings"]:
            binding["use"] = replacement
    mutated["component_decision_summary"] = derive_component_decision_summary(
        mutated["component_decisions"]
    )

    assert validate_enterprise_underwriting_episode(mutated)["state"] == "REVIEWABLE"
    before = compile_underwriting_projections(original)[projection][route_field]
    after = compile_underwriting_projections(mutated)[projection][route_field]
    assert after != before


def test_unrelated_primary_component_cannot_mask_an_excluded_epv_component() -> None:
    episode = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    core = next(
        item for item in episode["component_decisions"]
        if item["component_id"] == "DOMESTIC_CORE_NORMAL_EARNINGS"
    )
    for binding in core["valuation_route_bindings"]:
        if binding["route_id"] in {"EARNINGS_POWER_VALUE", "EPV"}:
            binding["use"] = "EXCLUDED"
    survival = next(
        item for item in episode["component_decisions"]
        if item["component_id"] == "CONSOLIDATED_SURVIVAL_AND_FINANCING"
    )
    survival["valuation_use"] = "PRIMARY_INPUT"
    survival["valuation_route_bindings"].extend([
        {"route_id": "EARNINGS_POWER_VALUE", "use": "PRIMARY_INPUT"},
        {"route_id": "EPV", "use": "PRIMARY_INPUT"},
    ])
    episode["component_decision_summary"] = derive_component_decision_summary(
        episode["component_decisions"]
    )

    findings = validate_enterprise_underwriting_episode(episode)["findings"]

    assert "EPV" in episode["value_route"]["valuation_model_roles"]["primary"]
    assert (
        "value_route.primary_route_required_component_ineligible:"
        "EARNINGS_POWER_VALUE:DOMESTIC_CORE_NORMAL_EARNINGS"
        in findings
    )
    assert (
        "value_route.primary_route_required_component_ineligible:"
        "EPV:DOMESTIC_CORE_NORMAL_EARNINGS"
        in findings
    )
    assert (
        "value_route.route_binding_component_not_eligible:"
        "EPV:CONSOLIDATED_SURVIVAL_AND_FINANCING"
        in findings
    )


def test_optional_excluded_component_does_not_invalidate_a_required_route() -> None:
    episode = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    requirements = {
        item["route_id"]: item
        for item in episode["value_route"]["route_component_requirements"]
    }
    return_route = requirements["RETURN_DECOMPOSITION"]

    assert return_route["required_component_ids"] == [
        "DOMESTIC_CORE_NORMAL_EARNINGS"
    ]
    assert return_route["optional_component_ids"] == [
        "DOMESTIC_INCREMENTAL_ASSET_RETURN"
    ]
    assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"


def test_component_label_cannot_silently_promote_an_excluded_input_to_base() -> None:
    episode = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    decision = next(
        item for item in episode["component_decisions"]
        if item["component_id"] == "DOMESTIC_INCREMENTAL_ASSET_RETURN"
    )
    decision["normal_earnings_use"] = "BASE_RANGE"

    findings = validate_enterprise_underwriting_episode(episode)["findings"]

    assert any("base_use_conflicts_with_component_treatment" in item for item in findings)


def test_present_component_decision_ledger_cannot_be_empty_or_partial() -> None:
    episode = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    episode["component_decisions"] = []
    assert "component_decisions.must_be_non_empty_list" in validate_enterprise_underwriting_episode(
        episode
    )["findings"]

    partial = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    partial["component_decisions"] = partial["component_decisions"][:-1]
    assert "component_decisions.must_cover_each_component_treatment_once" in (
        validate_enterprise_underwriting_episode(partial)["findings"]
    )


def test_only_primary_valuation_model_is_required() -> None:
    episode = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    episode["value_route"]["valuation_model_roles"] = {"primary": ["EPV"]}

    validation = validate_enterprise_underwriting_episode(episode)

    assert validation["state"] == "REVIEWABLE"


def test_magna_is_a_distressed_cycle_demonstration_and_not_a_conch_conclusion() -> None:
    magna = _episode("MAGNA_200903_WORKED_CASE_V1.json")
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")

    assert magna["underwriting_route"] == "DISTRESSED_CYCLICAL"
    assert "GROWTH_VALUE_AS_PRIMARY" in magna["value_route"]["excluded_routes"]
    assert magna["sample_identity"] == conch["sample_identity"] == "WORKED_CASE"
    assert magna["company_id"] != conch["company_id"]
    assert "不能复制 Magna 的恢复结论" in magna["existing_object_refs"][1]["role"]
    assert "项目级客户" in conch["component_treatments"][2]["reason"]


def test_conch_same_thesis_projects_deterministically_to_cjo_valuation_and_report_consumers() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    bundle = compile_underwriting_projections(conch)
    stored = {
        "cjo_candidate_projection": _episode_projection("CN600585_20240501_CJO_CANDIDATE_PROJECTION.json"),
        "valuation_route_request": _episode_projection("CN600585_20240501_VALUATION_ROUTE_REQUEST.json"),
        "golden_report_underwriting_handoff": _episode_projection("CN600585_20240501_GOLDEN_REPORT_UNDERWRITING_HANDOFF.json"),
    }

    assert bundle == compile_underwriting_projections(deepcopy(conch))
    assert bundle == stored
    assert validate_underwriting_projection_bundle(conch, bundle)["state"] == "REVIEWABLE"
    thesis_id = conch["underwriting_thesis"]["thesis_id"]
    assert {item["underwriting_thesis_id"] for item in bundle.values()} == {thesis_id}
    industry_future = conch["situation_model"]["industry_future_thesis"]
    projected_futures = [
        bundle["cjo_candidate_projection"]["situation_model"]["industry_future_thesis"],
        bundle["valuation_route_request"]["situation_model"]["industry_future_thesis"],
        bundle["golden_report_underwriting_handoff"]["situation_model"]["industry_future_thesis"],
    ]
    assert projected_futures == [industry_future, industry_future, industry_future]
    assert bundle["cjo_candidate_projection"]["central_path"] == bundle["golden_report_underwriting_handoff"]["central_path"]
    assert bundle["valuation_route_request"]["normal_earnings_input_treatment"] == conch["underwriting_thesis"]["normal_earnings_treatment"]
    industry = conch["situation_model"]["industry_future_thesis"]
    assert {item["situation_model"]["industry_future_thesis"]["most_likely_regime"] for item in bundle.values()} == {
        industry["most_likely_regime"]
    }


def test_industry_future_is_part_of_the_episode_and_price_free_shared_thesis() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    projection = project_price_free_underwriting_thesis(conch)

    assert projection["situation_model"]["industry_future_thesis"]["profit_pool_transmission"]
    assert projection["situation_model"]["industry_future_thesis"]["company_exposure"]
    assert "industry_future_thesis" not in projection
    assert projection["underwriting_thesis"]["owner_cash_treatment"]
    assert "investment_treatment" not in projection

    missing = deepcopy(conch)
    missing["situation_model"].pop("industry_future_thesis")
    findings = validate_enterprise_underwriting_episode(missing)["findings"]
    assert "situation_model.industry_future_thesis.horizon_missing" in findings


def test_price_free_projection_rejects_a_second_top_level_industry_story() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    projection = project_price_free_underwriting_thesis(conch)
    projection["industry_future_thesis"] = deepcopy(
        projection["situation_model"]["industry_future_thesis"]
    )
    projection["industry_future_thesis"]["most_likely_regime"] = "A conflicting broad recovery story."

    validation = validate_price_free_underwriting_thesis_projection(projection)

    assert validation["state"] == "INVALID"
    assert "legacy_top_level_industry_future_thesis_not_allowed" in validation["findings"]


def test_industry_future_thesis_cannot_be_missing_or_diverge_across_episode_views() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    missing = deepcopy(conch)
    del missing["situation_model"]["industry_future_thesis"]["profit_pool_transmission"]
    assert (
        "situation_model.industry_future_thesis.profit_pool_transmission_missing"
        in validate_enterprise_underwriting_episode(missing)["findings"]
    )

    divergent = deepcopy(conch)
    divergent["underwriting_thesis"]["strongest_rival"] = "A different report story."
    assert (
        "underwriting_thesis.strongest_rival_not_derived_from_industry_future_thesis"
        in validate_enterprise_underwriting_episode(divergent)["findings"]
    )


def _episode_projection(name: str) -> dict:
    return json.loads((EPISODES / name).read_text(encoding="utf-8"))


def test_price_facing_treatment_cannot_rewrite_the_underwriting_thesis() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    revised_price_treatment = deepcopy(conch)
    revised_price_treatment["investment_treatment"] = "A future price observation changes research priority only."

    assert compile_underwriting_projections(revised_price_treatment)["cjo_candidate_projection"]["central_path"] == conch["underwriting_thesis"]["central_path"]
    forbidden = deepcopy(conch)
    forbidden["underwriting_thesis"]["price"] = "must not become a business fact"
    findings = validate_enterprise_underwriting_episode(forbidden)["findings"]
    assert any("price_boundary" in finding for finding in findings)


def test_local_owner_cash_limit_does_not_erase_survival_or_value_route() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    treatments = {item["component_id"]: item["treatment"] for item in conch["component_treatments"]}

    assert treatments["ORDINARY_SHARE_OWNER_CASH"] == "CANNOT_BOUND"
    assert treatments["CONSOLIDATED_SURVIVAL_AND_FINANCING"] == "UNDERWRITE"
    assert treatments["DOMESTIC_INCREMENTAL_ASSET_RETURN"] == "EXCLUDE_FROM_BASE"
    assert conch["value_route"]["primary_routes"] == [
        "ASSET_VALUE", "EARNINGS_POWER_VALUE",
    ]
    assert conch["value_route"]["valuation_model_roles"]["corroborative"] == [
        "RETURN_DECOMPOSITION"
    ]


def test_readout_is_investor_facing_and_preserves_the_strongest_rival() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    rendered = render_underwriting_readout(conch)
    reader_file = (EPISODES / "CN600585_20240501_INVESTOR_READOUT.md").read_text(encoding="utf-8")

    assert "即时生存风险低" in rendered
    assert "未来3至5年" in rendered
    assert "利润池传导" in rendered
    assert "行业未来与公司传导" in rendered
    assert "供给退出慢于需求下降" in rendered
    assert "海外毛利改善" in rendered
    assert "国内新增资产不取得增量正常盈利" in rendered
    assert "DOMESTIC_INCREMENTAL_ASSET_RETURN" not in rendered
    assert "EXCLUDE_FROM_BASE" not in rendered
    assert "RESULT_KNOWN_TEACHING_ONLY" not in rendered
    assert "能穿越周期" in reader_file
    assert "新增国内资产" in reader_file
    assert "schema" not in reader_file.lower()


def test_reader_brief_whitelists_only_economic_conclusions() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    brief = compile_golden_report_reader_brief(
        conch,
        {
            "accepted": True,
            "reader_conclusions": [
                "NAV与中周期EPV给出互不相加的价值交叉检查；owner cash仍采用保守范围。"
            ],
            "raw_review": {
                "root_cause": "DATA_COVERAGE",
                "status": "CANNOT_BOUND",
                "finding_id": "FINDING:should-not-reach-writer",
            },
        },
    )
    serialized = json.dumps(brief, ensure_ascii=False)

    assert validate_golden_report_reader_brief(brief)["state"] == "REVIEWABLE"
    assert "NAV与中周期EPV" in serialized
    assert "raw_review" not in serialized
    assert "DATA_COVERAGE" not in serialized
    assert "CANNOT_BOUND" not in serialized
    assert "FINDING:should-not-reach-writer" not in serialized
    assert "component_id" not in serialized
    assert "schema_version" not in brief
    assert "accepted_conclusions" in brief


def test_reader_brief_rejects_unaccepted_or_untranslated_model_results() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")

    with pytest.raises(ValueError, match="deterministic_results_not_accepted"):
        compile_golden_report_reader_brief(
            conch,
            {"accepted": False, "reader_conclusions": ["EPV保持保守范围。"]},
        )
    with pytest.raises(ValueError, match="reader_internal_control_leak:model_identity"):
        compile_golden_report_reader_brief(
            conch,
            {"accepted": True, "reader_conclusions": ["P_LONG为3.20港元。"]},
        )


def _ordinary_distribution_bridge() -> dict:
    fact_ids = ["OBS:EARNINGS", "OBS:DISTRIBUTION", "OBS:FRICTION"]
    return compile_valuation_value_bridges(
        {
            "schema_version": "valuation-value-bridges-input.v1",
            "ordinary_distribution": {
                "model_input": {
                    "schema_version": "ordinary-distribution-input.v1",
                    "model_id": "DIST:02669:must-not-reach-writer",
                    "company_id": "02669.HK",
                    "cutoff_at": "2026-08-11",
                    "position_as_of": "2025-12-31",
                    "currency": "RMB",
                    "unit": "RMB_m",
                    "verified_facts": [
                        {"fact_id": fact_id, "status": "VERIFIED"}
                        for fact_id in fact_ids
                    ],
                    "input_fact_ids": fact_ids,
                    "normalized_ordinary_share_operating_earnings": 896.979630439952,
                    "ordinary_distribution_rate": 0.35,
                    "distribution_tax_and_collection_friction_rate": 0.1027,
                    "fixed_collection_cost": 3.28396046,
                }
            },
        }
    )


def test_value_bridge_reader_brief_exposes_only_safe_slot_surface() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    sentence = "税费和收取摩擦后的普通股分配为RMB278.417百万元，即约RMB2.784亿元。"
    bridge = _ordinary_distribution_bridge()

    brief = compile_golden_report_reader_brief(conch, bridge)
    serialized = json.dumps(brief, ensure_ascii=False)

    assert brief["deterministic_conclusions"] == [
        {"target_chapter": 12, "sentence": sentence}
    ]
    assert validate_golden_report_reader_brief(brief)["state"] == "REVIEWABLE"
    for private_value in (
        "DIST:02669:must-not-reach-writer",
        "distribution.after_tax_common",
        "AFTER_TAX_COMMON_DISTRIBUTION",
        "after_tax_common_distribution",
        "selected_value",
        "display_variants",
        "source_model_id",
    ):
        assert private_value not in serialized

    rendered = render_underwriting_readout(conch, bridge)
    assert rendered.count(sentence) == 1
    assert "target_chapter" not in rendered
    assert "AFTER_TAX_COMMON_DISTRIBUTION" not in rendered


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.__setitem__("reader_slots", []),
        lambda value: value["reader_slots"][0].__setitem__(
            "sentence",
            "税费和收取摩擦后的普通股分配为RMB278.417百万元，即约RMB2.785亿元。",
        ),
    ],
)
def test_value_bridge_reader_brief_rejects_missing_or_tampered_slot(mutate) -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    bridge = _ordinary_distribution_bridge()
    mutate(bridge)

    validation = validate_valuation_value_bridges(bridge)

    assert validation["state"] == "INVALID"
    assert "reader_slots_not_deterministic_projection" in validation["findings"]

    with pytest.raises(
        ValueError,
        match="deterministic_value_bridges_invalid:reader_slots_not_deterministic_projection",
    ):
        compile_golden_report_reader_brief(conch, bridge)
