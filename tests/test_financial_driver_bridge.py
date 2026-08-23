from __future__ import annotations

import json
from pathlib import Path

from scripts.financial_driver_bridge import (
    build_financial_driver_bridge,
    evaluate_output_financial_driver_bridge,
    initialize_financial_driver_bridge_policy,
    persist_financial_driver_bridge,
    validate_financial_driver_bridge,
)
from scripts.report_completion import evaluate_report_completion
from scripts.turtle_agent.tools.read_tools import read_structured_ledger_contract
from scripts.turtle_agent.tools.write_tools import write_financial_driver_bridge as write_driver_bridge_tool
import scripts.research_calibration as research_calibration


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _prepare(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "fact_observations.json", {"observations": [
        {"observation_id": "OBS:online-share", "status": "VERIFIED"},
        {"observation_id": "OBS:segment-margin", "status": "VERIFIED"},
        {"observation_id": "OBS:reported-ocf", "status": "VERIFIED"},
        {"observation_id": "OBS:restricted-cash-release", "status": "VERIFIED"},
        {"observation_id": "OBS:cash-capex", "status": "VERIFIED"},
        {"observation_id": "OBS:working-capital", "status": "VERIFIED"},
        {"observation_id": "OBS:cash-accessibility", "status": "VERIFIED"},
        {"observation_id": "OBS:financial-asset-rollover", "status": "VERIFIED"},
        {"observation_id": "OBS:titanium-impairment", "status": "VERIFIED"},
    ]})
    _write(output / "valuation_model.json", {"models": [{"model_id": "EPV.primary"}, {"model_id": "RETURN.base"}]})
    _write(output / "decision_ledger.json", {"entries": [{"entry_id": "valuation.v_final"}, {"entry_id": "return.expected"}]})


def _binding(model_id: str = "EPV.primary") -> dict:
    return {"model_id": model_id, "input_id": "normalized_owner_cash", "treatment": "NORMALIZATION_ADJUSTMENT", "effect": "exclude non-recurring release from owner cash", "decision_entry_ids": ["valuation.v_final", "return.expected"]}


def _monitoring(contract_id: str, judgment_id: str) -> dict:
    return {
        "contract_id": contract_id,
        "forward_judgment_ids": [judgment_id],
        "metric": "same_scope_operating_signal",
        "unit": "index",
        "measurement_basis": "同一报告边界、同一指标定义的正式披露",
        "measurement_period": {"start": "2026-01-01", "end": "2026-12-31"},
        "allowed_source_types": ["ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT"],
        "observation_window": {"opens_after": "2026-04-30", "closes_at": "2027-08-31"},
        "comparability_rule": "口径、范围、单位和期间不一致时保持 NOT_EVALUATED，不临时转换。",
    }


def _payload(output: Path, *, analysis_purpose: str = "INVESTMENT_DECISION") -> dict:
    payload = build_financial_driver_bridge(output, [
        {"driver_id": "FDBDRV:demand", "layer": "COMPETITION_DEMAND", "statement": "线上份额是竞争位置的一个信号，不外推为全渠道份额。", "status": "OBSERVED", "observation_ids": ["OBS:online-share"], "measurement_period": {"start": "2025-01-01", "end": "2025-12-31"}, "competitive_context": {"market_definition": "中国家用空调线上零售市场", "customer_alternatives": ["其他品牌", "延后购买"], "comparison_observation_ids": ["OBS:online-share"], "scope_limit": "线上份额不代表线下或全渠道相对位置。"}, "model_bindings": [_binding()]},
        {"driver_id": "FDBDRV:margin", "layer": "UNIT_ECONOMICS", "statement": "分部利润率用于拆解而非直接替代公司毛利率。", "status": "OBSERVED", "observation_ids": ["OBS:segment-margin"], "measurement_period": {"start": "2025-01-01", "end": "2025-12-31"}, "model_bindings": [_binding()]},
        {"driver_id": "FDBDRV:cash", "layer": "CASH_CONVERSION", "statement": "经营现金流包含受限资金到期释放，须从常态 owner cash 中剔除。", "status": "OBSERVED", "observation_ids": ["OBS:reported-ocf", "OBS:restricted-cash-release", "OBS:cash-capex", "OBS:working-capital", "OBS:cash-accessibility"], "measurement_period": {"start": "2025-01-01", "end": "2025-12-31"}, "cash_normalization_contract": {"state": "NORMALIZED", "reported_cash_metric": "operating_cash_flow", "reported_cash_observation_ids": ["OBS:reported-ocf"], "maintenance_capex_treatment": "以独立、来源化的维持性资本开支判断替代总 Capex 的机械扣减。", "maintenance_capex_observation_ids": ["OBS:cash-capex"], "working_capital_treatment": "拆分维持单位销量所需与暂时性营运资本变动；未来源化的释放不加回。", "working_capital_observation_ids": ["OBS:working-capital"], "cash_accessibility_treatment": "金融子公司监管资本、受限资金与期限未明确的金融资产不作为普通股可分配现金。", "cash_accessibility_observation_ids": ["OBS:cash-accessibility"], "conservative_treatment": "缺失的调整项不作为可分配现金加回。", "adjustment_components": [{"component_id": "restricted-fund-release", "direction": "DEDUCT", "recurrence_assessment": "UNKNOWN", "observation_ids": ["OBS:restricted-cash-release"], "treatment": "从 reported OCF 中剔除未经重复性证明的受限资金释放。"}, {"component_id": "capital-expenditure", "direction": "DEDUCT", "recurrence_assessment": "RECURRING", "observation_ids": ["OBS:cash-capex"], "treatment": "以明确的维持性判断处理资本开支；不得假定为零。"}]}, "model_bindings": [_binding()]},
        {"driver_id": "FDBDRV:allocation", "layer": "CAPITAL_ALLOCATION", "statement": "金融产品滚动与项目减值分别识别，不互相替代。", "status": "OBSERVED", "observation_ids": ["OBS:financial-asset-rollover", "OBS:titanium-impairment"], "measurement_period": {"start": "2025-01-01", "end": "2025-12-31"}, "model_bindings": [_binding("RETURN.base")]},
    ], [
        {"event_id": "FDBEV:financial-products", "event_type": "FINANCIAL_ASSET_ROLLOVER", "classification": "LIQUIDITY_MANAGEMENT", "classification_basis": "披露显示主要为金融产品和大额存单滚动，尚未证明为经营再投资或价值毁损。", "decision_date": "2025-12-31", "realization_window": "随产品到期和资产负债表变动结算", "observation_ids": ["OBS:financial-asset-rollover"]},
        {"event_id": "FDBEV:titanium", "event_type": "IMPAIRMENT", "classification": "VALUE_DESTRUCTIVE_CANDIDATE", "classification_basis": "在建工程因不再建设或预期无现金流而减值；独立业务现金流和退出路径仍待核实。", "decision_date": "2025-12-31", "realization_window": "后续减值、处置或独立现金流披露", "observation_ids": ["OBS:titanium-impairment"]},
    ], report_id="000651.SZ", as_of="2026-04-30", change_reason="separate recurring owner cash from restricted-fund release", analysis_purpose=analysis_purpose)
    for driver in payload["drivers"]:
        driver["monitoring_contract"] = _monitoring(
            "FDBMON:" + driver["driver_id"].removeprefix("FDBDRV:"),
            "fj." + driver["driver_id"].removeprefix("FDBDRV:"),
        )
    for event in payload["allocation_events"]:
        event_key = event["event_id"].removeprefix("FDBEV:")
        event["realization_contract"] = {
            "contract_id": "FDBREAL:" + event_key,
            "forward_judgment_ids": ["fj." + event_key],
            "early_signal": _monitoring("FDBMON:" + event_key + ":early", "fj." + event_key),
            "terminal_outcome": _monitoring("FDBMON:" + event_key + ":terminal", "fj." + event_key),
        }
        event["realization_contract"]["terminal_outcome"]["measurement_period"] = {"start": "2027-01-01", "end": "2029-12-31"}
        event["realization_contract"]["terminal_outcome"]["observation_window"] = {"opens_after": "2030-01-01", "closes_at": "2030-08-31"}
        event["initial_commitment"] = {
            "amount": 100.0,
            "currency": "CNY million",
            "funding_source": "company cash and deposits",
            "observation_ids": list(event["observation_ids"]),
        }
        event["commitment_movement"] = {
            "movement": "ESCALATE",
            "scope": "FULL",
            "observation_date": "2026-04-30",
            "observation_ids": list(event["observation_ids"]),
            "realization_contract_id": event["realization_contract"]["contract_id"],
            "monitoring_stage": "EARLY_SIGNAL",
            "monitoring_contract_id": event["realization_contract"]["early_signal"]["contract_id"],
        }
    payload["allocation_events"][1]["commitment_movement"] = {
        "movement": "UNKNOWN",
        "scope": "UNKNOWN",
        "scope_unknown_reason": "后续披露没有说明潜在变化覆盖初始承诺的哪一部分。",
        "scope_conservative_treatment": "不把未界定的变化外推为对全部初始承诺的加码或撤退。",
        "observation_date": "2026-04-30",
        "unknown_reason": "后续独立业务资本承诺或撤退尚未在同口径公告中披露。",
        "conservative_treatment": "不把减值或期末余额当作退出、加码或现金回收；保留资本配置结论为未决。",
        "realization_contract_id": payload["allocation_events"][1]["realization_contract"]["contract_id"],
        "monitoring_stage": "EARLY_SIGNAL",
        "monitoring_contract_id": payload["allocation_events"][1]["realization_contract"]["early_signal"]["contract_id"],
    }
    return payload


def test_bridge_requires_all_four_economic_layers_and_verified_bindings(tmp_path: Path) -> None:
    _prepare(tmp_path)
    result = validate_financial_driver_bridge(_payload(tmp_path), output_dir=tmp_path)
    assert result["state"] == "REVIEWABLE"
    assert set(result["covered_layers"]) == {"COMPETITION_DEMAND", "UNIT_ECONOMICS", "CASH_CONVERSION", "CAPITAL_ALLOCATION"}


def test_company_judgment_bridge_uses_frozen_monitoring_not_model_or_trade_bindings(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path, analysis_purpose="COMPANY_JUDGMENT_ONLY")
    for driver in payload["drivers"]:
        driver.pop("model_bindings")

    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)

    assert result["state"] == "REVIEWABLE"
    assert result["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"


def test_output_evaluation_rejects_bridge_monitoring_that_is_not_in_thesis_ledger(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path, analysis_purpose="COMPANY_JUDGMENT_ONLY")
    for driver in payload["drivers"]:
        driver.pop("model_bindings")
    persist_financial_driver_bridge(tmp_path, payload)

    _write(tmp_path / "thesis_test.json", {
        "forward_judgments": [{"judgment_id": "fj.demand"}],
    })
    result = evaluate_output_financial_driver_bridge(tmp_path, persist=False)

    assert result["state"] == "INVALID"
    assert "FDBDRV:margin:forward_judgment_unbound:fj.margin" in result["invalid_findings"]
    assert "FDBEV:titanium:terminal_outcome:forward_judgment_unbound:fj.titanium" in result["invalid_findings"]


def test_output_evaluation_accepts_only_realized_thesis_judgment_ids(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path, analysis_purpose="COMPANY_JUDGMENT_ONLY")
    for driver in payload["drivers"]:
        driver.pop("model_bindings")
    persist_financial_driver_bridge(tmp_path, payload)

    _write(tmp_path / "thesis_test.json", {
        "forward_judgments": [
            {"judgment_id": judgment_id}
            for judgment_id in (
                "fj.demand", "fj.margin", "fj.cash", "fj.allocation",
                "fj.financial-products", "fj.titanium",
            )
        ],
    })

    assert evaluate_output_financial_driver_bridge(tmp_path, persist=False)["state"] == "REVIEWABLE"


def test_company_judgment_bridge_rejects_hidden_model_or_decision_binding(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path, analysis_purpose="COMPANY_JUDGMENT_ONLY")

    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)

    assert "FDBDRV:demand:company_judgment_cannot_carry_model_bindings" in result["invalid_findings"]


def test_bridge_rejects_candidate_as_economic_evidence(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path)
    payload["drivers"][2]["observation_ids"] = ["OBS:not-verified"]
    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)
    assert result["state"] == "INVALID"
    assert "unverified_observation:OBS:not-verified" in result["invalid_findings"][0]


def test_observed_competition_driver_requires_customer_choice_and_market_scope(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path)
    payload["drivers"][0].pop("competitive_context")
    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)
    assert result["state"] == "INCOMPLETE"
    assert "FDBDRV:demand:competitive_context_missing" in result["incomplete_findings"]

    payload = _payload(tmp_path)
    payload["drivers"][0]["competitive_context"]["comparison_observation_ids"] = ["OBS:not-verified"]
    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)
    assert result["state"] == "INVALID"
    assert "FDBDRV:demand:competitive_context:unverified_comparison_observation:OBS:not-verified" in result["invalid_findings"]


def test_versioned_industry_data_is_limited_to_competition_or_unit_economics_monitoring(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path)
    payload["drivers"][0]["monitoring_contract"]["allowed_source_types"] = ["LICENSED_INDUSTRY_DATA"]

    assert validate_financial_driver_bridge(payload, output_dir=tmp_path)["state"] == "REVIEWABLE"

    payload = _payload(tmp_path)
    payload["drivers"][2]["monitoring_contract"]["allowed_source_types"] = ["LICENSED_INDUSTRY_DATA"]
    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)

    assert result["state"] == "INVALID"
    assert "FDBDRV:cash:monitoring_contract:allowed_source_type_invalid" in result["invalid_findings"]


def test_unknown_driver_requires_conservative_treatment(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path)
    payload["drivers"][3].update({"status": "UNKNOWN", "observation_ids": [], "unknown_reason": "格力钛独立现金流未披露。"})
    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)
    assert result["state"] == "INCOMPLETE"
    assert "FDBDRV:allocation:conservative_treatment_missing" in result["incomplete_findings"]


def test_bridge_requires_settleable_driver_monitoring_and_allocation_realization_contracts(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path)
    payload["drivers"][0].pop("monitoring_contract")
    payload["allocation_events"][0].pop("realization_contract")

    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)
    assert result["state"] == "INCOMPLETE"
    assert "FDBDRV:demand:monitoring_contract_missing" in result["incomplete_findings"]
    assert "FDBEV:financial-products:realization_contract_missing" in result["incomplete_findings"]


def test_bridge_rejects_reused_monitoring_contracts(tmp_path: Path) -> None:
    _prepare(tmp_path)
    payload = _payload(tmp_path)
    payload["allocation_events"][1]["realization_contract"]["early_signal"]["contract_id"] = (
        payload["allocation_events"][0]["realization_contract"]["early_signal"]["contract_id"]
    )

    result = validate_financial_driver_bridge(payload, output_dir=tmp_path)

    assert result["state"] == "INVALID"
    assert "duplicate_monitoring_contract_id:FDBMON:financial-products:early" in result["invalid_findings"]


def test_policy_fails_closed_only_when_enabled(tmp_path: Path) -> None:
    assert evaluate_output_financial_driver_bridge(tmp_path, persist=False)["state"] == "SKIP"
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    assert evaluate_output_financial_driver_bridge(tmp_path, persist=False)["state"] == "INCOMPLETE"
    result = persist_financial_driver_bridge(tmp_path, _payload(tmp_path))
    assert result["validation"]["state"] == "REVIEWABLE"
    assert evaluate_output_financial_driver_bridge(tmp_path, persist=False)["state"] == "REVIEWABLE"


def test_new_policy_requires_a_source_bound_initial_commitment_and_movement(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path)
    payload["allocation_events"][0].pop("initial_commitment")
    payload["allocation_events"][1]["commitment_movement"]["monitoring_contract_id"] = "FDBMON:wrong"

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "INVALID"
    assert "FDBEV:financial-products:initial_commitment_missing" in result["validation"]["incomplete_findings"]
    assert "FDBEV:titanium:commitment_movement:monitoring_contract_id_mismatch" in result["validation"]["invalid_findings"]


def test_new_policy_requires_partial_movement_to_state_its_share_of_initial_commitment(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path)
    movement = payload["allocation_events"][0]["commitment_movement"]
    movement.update({"movement": "DEESCALATE", "scope": "PARTIAL"})

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "INVALID"
    assert "FDBEV:financial-products:commitment_movement:partial_affected_fraction_invalid" in result["validation"]["invalid_findings"]

    movement["affected_fraction_of_initial"] = 0.70
    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "REVIEWABLE"


def test_new_policy_requires_cash_to_state_whether_it_is_normal_owner_cash(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path)
    payload["drivers"][2].pop("cash_normalization_contract")

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "INCOMPLETE"
    assert "FDBDRV:cash:cash_normalization_contract_missing" in result["validation"]["incomplete_findings"]


def test_normalized_cash_must_treat_working_capital_and_cash_accessibility(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path)
    contract = payload["drivers"][2]["cash_normalization_contract"]
    contract.pop("working_capital_treatment")
    contract.pop("cash_accessibility_treatment")
    contract.pop("working_capital_observation_ids")
    contract.pop("cash_accessibility_observation_ids")

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "INCOMPLETE"
    findings = result["validation"]["incomplete_findings"]
    assert "FDBDRV:cash:cash_normalization_contract:working_capital_treatment_missing" in findings
    assert "FDBDRV:cash:cash_normalization_contract:cash_accessibility_treatment_missing" in findings
    assert "FDBDRV:cash:cash_normalization_contract:working_capital_observation_ids_missing" in findings
    assert "FDBDRV:cash:cash_normalization_contract:cash_accessibility_observation_ids_missing" in findings


def test_new_policy_allows_an_unknown_cash_normalization_without_inventing_owner_cash(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path)
    payload["drivers"][2]["cash_normalization_contract"] = {
        "state": "UNKNOWN",
        "unknown_reason": "受限资金、金融子公司资本、维持性 Capex 与营运资本尚未在同口径桥中闭合。",
        "conservative_treatment": "不把 OCF、货币资金或 OCF–Capex 用作 normal owner cash。",
    }

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "REVIEWABLE"


def test_new_policy_applies_the_same_commitment_trace_to_company_judgment_only(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path, analysis_purpose="COMPANY_JUDGMENT_ONLY")
    for driver in payload["drivers"]:
        driver.pop("model_bindings")
    payload["allocation_events"][0]["commitment_movement"].pop("observation_ids")

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "INCOMPLETE"
    assert "FDBEV:financial-products:commitment_movement:observation_ids_missing" in result["validation"]["incomplete_findings"]


def test_new_policy_preserves_an_unknown_initiating_amount_without_inventing_funding(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path)
    payload["allocation_events"][1]["initial_commitment"] = {
        "amount": "UNKNOWN",
        "unknown_reason": "历史启动投入金额和资金来源未在同口径法定披露中闭合。",
        "conservative_treatment": "不从减值或期末余额倒推累计投入、资金来源或可回收现金。",
    }

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "REVIEWABLE"


def test_new_policy_preserves_a_known_amount_when_its_funding_source_is_undisclosed(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path)
    payload["allocation_events"][1]["initial_commitment"] = {
        "amount": 1_015.33,
        "currency": "CNY million",
        "funding_source": "UNKNOWN",
        "unknown_reason": "交易公告和后续年报确认对价，但没有把该交易的资金来源逐笔归因。",
        "conservative_treatment": "保留已知投资额，不把合并货币资金或融资余额归因给本次交易。",
        "observation_ids": ["OBS:titanium-impairment"],
    }

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "REVIEWABLE"

    payload["allocation_events"][1]["initial_commitment"].pop("unknown_reason")
    result = persist_financial_driver_bridge(tmp_path, payload)
    assert "FDBEV:titanium:initial_commitment:funding_source_unknown_reason_missing" in result["validation"]["incomplete_findings"]


def test_legacy_policy_does_not_retroactively_require_the_commitment_trace(tmp_path: Path) -> None:
    _prepare(tmp_path)
    _write(tmp_path / "financial_driver_bridge_policy.json", {
        "schema_version": "financial-driver-bridge-policy.v1", "enforced": True,
    })
    payload = _payload(tmp_path)
    for event in payload["allocation_events"]:
        event.pop("initial_commitment")
        event.pop("commitment_movement")

    result = persist_financial_driver_bridge(tmp_path, payload)

    assert result["validation"]["state"] == "REVIEWABLE"


def test_legacy_policy_does_not_retroactively_require_frozen_judgment_bindings(tmp_path: Path) -> None:
    _prepare(tmp_path)
    _write(tmp_path / "financial_driver_bridge_policy.json", {
        "schema_version": "financial-driver-bridge-policy.v1", "enforced": True,
    })
    persist_financial_driver_bridge(tmp_path, _payload(tmp_path))
    _write(tmp_path / "thesis_test.json", {
        "forward_judgments": [{"judgment_id": "fj.demand"}],
    })

    assert evaluate_output_financial_driver_bridge(tmp_path, persist=False)["state"] == "REVIEWABLE"


def test_agent_writer_and_contract_expose_the_bridge_without_price_inference(tmp_path: Path) -> None:
    _prepare(tmp_path)
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    candidate = _payload(tmp_path)
    result = write_driver_bridge_tool(
        str(tmp_path),
        drivers=candidate["drivers"],
        allocation_events=candidate["allocation_events"],
        report_id="000651.SZ",
        as_of="2026-04-30",
        change_reason="connect company drivers to the existing valuation inputs",
    )
    assert result["validation"]["state"] == "REVIEWABLE"
    contract = read_structured_ledger_contract(str(tmp_path), ledger="financial_driver")
    assert contract["contract"]["rules"].startswith("Cover all four economic layers")
    assert "price" in contract["contract"]["rules"].lower()
    assert "monitoring_contract" in contract["contract"]
    assert "working_capital_observation_ids" in contract["contract"]["driver"]
    assert "cash_accessibility_observation_ids" in contract["contract"]["driver"]
    assert "realization_contract" in contract["contract"]["allocation_event"]
    assert "initial_commitment" in contract["contract"]["allocation_event"]
    assert "commitment_movement" in contract["contract"]["allocation_event"]


def test_completion_contract_blocks_an_enabled_bridge_until_it_is_written(tmp_path: Path) -> None:
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    completion = evaluate_report_completion("draft", str(tmp_path))
    assert completion.status == "INCOMPLETE"
    assert completion.validators["financial_driver_bridge"]["state"] == "INCOMPLETE"
    assert any(item.startswith("Financial driver bridge: INCOMPLETE") for item in completion.blocking_findings)


def test_enabled_financial_driver_bridge_blocks_a_pit_snapshot_before_freeze(tmp_path: Path) -> None:
    _write(tmp_path / "analysis_contract.json", {"ts_code": "TEST.SZ", "data_as_of": "2025-12-31"})
    initialize_financial_driver_bridge_policy(tmp_path, run_id="run", enforced=True)
    original = research_calibration._ledger_states
    research_calibration._ledger_states = lambda *_args, **_kwargs: {
        "decision": {"state": "DECISION_READY"},
        "claim_evidence": {"state": "DECISION_READY"},
        "valuation": {"state": "DECISION_READY"},
        "thesis_test": {"state": "DECISION_READY"},
        "insight": {"state": "DECISION_READY"},
        "financial_driver_bridge": {"state": "INCOMPLETE"},
    }
    try:
        result = research_calibration.create_publication_snapshot(tmp_path, "report", dry_run=True)
    finally:
        research_calibration._ledger_states = original
    assert result["written"] is False
    assert result["gate_states"] == {"financial_driver_bridge": "INCOMPLETE"}
