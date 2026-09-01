from __future__ import annotations

from copy import deepcopy

from scripts.staged_judgment_ledger import (
    LEDGER_SCHEMA,
    compile_staged_judgment_ledger,
    validate_staged_judgment_ledger,
)
from scripts.enterprise_underwriting_training import build_training_contract
from scripts.enterprise_underwriting_training import ECONOMIC_DERIVATION_INTERFACE
from scripts.enterprise_underwriting_episode import derive_economic_derivation_summary


def _ledger() -> dict:
    surfaces = [
        ("SURVIVAL", "生存与融资缓冲可承保。", "IMPROVES", "UNDERWRITE"),
        ("BUSINESS_POSITION", "公司具备区域竞争位置。", "MIXED", "UNDERWRITE"),
        ("ADAPTATION", "管理层适应动作提供缓冲。", "MIXED", "CONDITIONALLY_UNDERWRITE"),
        ("NORMALIZATION", "正常盈利按中周期范围处理。", "MIXED", "CONDITIONALLY_UNDERWRITE"),
        ("PERMANENT_LOSS", "新增资本可能造成永久损失。", "DETERIORATES", "SCENARIO_ONLY"),
        ("VALUE_ROUTE", "采用资产与EPV交叉路线。", "NONE", "UNDERWRITE"),
        ("INDUSTRY_FUTURE", "行业需求温和收缩，利润池向低成本者集中。", "MIXED", "CONDITIONALLY_UNDERWRITE"),
        ("INVESTMENT_TREATMENT", "研究阶段等待关键证据。", "NONE", "EXCLUDE_FROM_BASE"),
    ]
    claims = [{
        "claim_id": "CLAIM:" + s,
        "surface": s,
        "statement": st,
        "direction": d,
        "mechanism": "由责任匹配证据传导。",
        "treatment": t,
        "evidence_ids": ["E1"],
        "strongest_rival": "行业恢复可能快于预期。",
        "reversal_observations": ["观察量价与现金回收。"],
        "unknown": None,
    } for s, st, d, t in surfaces]
    component = {
        "component_id": "CORE",
        "economic_scope": "MATURE_CORE_NORMAL_EARNINGS",
        "treatment": "CONDITIONALLY_UNDERWRITE",
        "normal_earnings_use": "CONDITIONAL_RANGE",
        "owner_cash_use": "UNRESOLVED",
        "financing_pressure_effect": "NEUTRAL",
        "permanent_loss_use": "CONDITIONAL_PATH",
        "valuation_use": "CONDITIONAL_PRIMARY_INPUT",
        "valuation_route_bindings": [{"route_id": "EPV", "use": "CONDITIONAL_PRIMARY_INPUT"}, {"route_id": "NO_BASE", "use": "EXCLUDED"}],
        "reason": "核心业务证据有限但可条件承保。",
        "promotion_test": "量价和单位利润恢复。",
        "invalidation_test": "持续恶化。",
        "evidence_ids": ["E1"],
    }
    return {
        "schema_version": LEDGER_SCHEMA,
        "ledger_id": "CNTEST:20240501:V1",
        "company_id": "CN:TEST",
        "company_name": "测试公司",
        "cutoff_at": "2024-05-01T00:00:00+08:00",
        "sample_identity": "WORKED_CASE",
        "status": "FROZEN",
        "decision_frame": "判断企业能否穿越周期。",
        "underwriting_route": "CYCLICAL",
        "claims": claims,
        "components": [component],
        "industry_future": {
            "horizon": "未来三年", "most_likely_regime": "需求温和收缩",
            "profit_pool_transmission": "价格传导至利润。", "company_exposure": "暴露于国内需求。",
            "adaptation": "降本与结构调整。", "normal_economics": "中周期范围。",
            "permanent_loss": "低利用率造成损失。", "valuation_treatment": "资产与EPV。",
            "strongest_rival": "行业恢复可能快于预期。", "reversal_observations": ["观察量价与现金回收。"],
        },
        "reversal_observations": ["观察量价与现金回收。"],
        "evidence_refs": [{"evidence_id": "E1", "source_ref": "SRC:TEST", "locator": "L1", "scope": "company", "used_for": "all"}],
        "diagnostics": [],
    }


def test_minimal_ledger_validates_and_is_deterministic():
    ledger = _ledger()
    assert validate_staged_judgment_ledger(ledger)["state"] == "VALID"
    contract = build_training_contract(
        contract_id="C", training_track="WORKED_CASE",
        company_id=ledger["company_id"], company_name=ledger["company_name"],
        cutoff_at=ledger["cutoff_at"],
        allowed_sources=[{"source_id":"S1", "source_ref":"SRC:TEST",
                          "available_at":"2024-05-01T00:00:00+08:00",
                          "time_role":"RESULT_KNOWN"}],
        feedback_clocks=[
            {"clock_id":"EARLY", "horizon":"EARLY_SIGNAL",
             "opens_at":"2025-05-01T00:00:00+08:00",
             "episode_claims":["INDUSTRY_AND_SITUATION"],
             "discriminating_observation":"早期经营信号"},
            {"clock_id":"LONG", "horizon":"LONG_TERM_PERMANENT_LOSS",
             "opens_at":"2027-05-01T00:00:00+08:00",
             "episode_claims":["PERMANENT_LOSS"],
             "discriminating_observation":"长期资本回报"},
        ],
    )
    source_index = {"E1":{"source_ref":"SRC:TEST", "available_at":"2024-05-01T00:00:00+08:00", "time_role":"RESULT_KNOWN"}}
    a = compile_staged_judgment_ledger(ledger, source_index, contract)["episode"]
    b = compile_staged_judgment_ledger(deepcopy(ledger), source_index, contract)["episode"]
    assert a == b
    assert a["schema_version"] == "enterprise-underwriting-episode.v2"


def test_unknown_is_local_and_price_firewall_rejects():
    ledger = _ledger()
    ledger["claims"][3]["direction"] = "UNKNOWN"
    ledger["claims"][3]["unknown"] = {"status": "UNKNOWN", "reason": "缺少数据", "conservative_treatment": "保留区间", "next_observation": "取得序列", "materiality": "MATERIAL"}
    assert validate_staged_judgment_ledger(ledger)["state"] == "VALID"
    ledger["claims"][0]["price"] = 10
    result = validate_staged_judgment_ledger(ledger)
    assert any(d["code"] == "PRICE_FIREWALL" for d in result["findings"])


def test_negative_contract_memory_duplicate_and_not_frozen():
    ledger = _ledger()
    ledger["status"] = "DRAFT"
    assert any(d["code"] == "LEDGER_NOT_FROZEN" for d in validate_staged_judgment_ledger(ledger)["findings"])
    ledger["status"] = "FROZEN"
    ledger["claims"].append(deepcopy(ledger["claims"][0]))
    assert any(d["code"] == "CLAIM_SURFACE_DUPLICATE" for d in validate_staged_judgment_ledger(ledger)["findings"])
    ledger = _ledger()
    ledger["evidence_refs"][0]["provenance"] = "TRAINING_MEMORY"
    assert any(d["code"] == "TRAINING_MEMORY_EVIDENCE_FORBIDDEN" for d in validate_staged_judgment_ledger(ledger)["findings"])


def test_v2_derivation_is_preserved_and_training_bound():
    ledger = _ledger()
    ledger["normal_earnings_bridge"] = {
        "basis": {"metric": "normalized earnings", "currency": "RMB", "unit": "RMB_m",
                  "tax_basis": "AFTER_TAX", "earnings_claim_scope": "ENTERPRISE_OPERATING",
                  "operating_perimeter": "测试核心业务", "as_of": "2024-04-30"},
        "rows": [{"row_id": "NEB:CORE", "component_id": "CORE", "row_role": "REFERENCE_EARNINGS",
                  "direction": "ADD", "quantification": {"status": "UNKNOWN", "reason": "缺少闭合序列",
                  "conservative_treatment": "保留未知"}, "evidence_ids": ["E1"],
                  "economic_reason": "核心业务正常盈利待确认"}],
    }
    ledger["driver_sensitivities"] = [{
        "sensitivity_id": "SENS:CORE", "component_ids": ["CORE"],
        "responsibility_boundary": "测试核心业务", "metric": "销量", "unit": "index", "horizon": "FY2025",
        "input_cases": {"mode": "BOUNDED_RANGE", "range": {"value_or_range": {"range_low": 90, "range_high": 110}, "basis": "历史区间", "evidence_ids": ["E1"]}},
        "transmission": {"normal_earnings": {"status": "UNKNOWN", "basis": "影响待测", "delta": {"status": "UNKNOWN", "reason": "无量化桥", "conservative_treatment": "不改变基准"}},
                          "owner_cash": {"status": "UNKNOWN", "basis": "现金可达性待测", "delta": {"status": "UNKNOWN", "reason": "无量化桥", "conservative_treatment": "不改变现金"}},
                          "valuation_route_ids": ["EPV"]},
        "reversal_observation_refs": ["#/reversal_observations/0"],
    }]
    contract = build_training_contract(
        contract_id="C:V2", training_track="WORKED_CASE", company_id=ledger["company_id"],
        company_name=ledger["company_name"], cutoff_at=ledger["cutoff_at"],
        allowed_sources=[{"source_id": "S1", "source_ref": "SRC:TEST", "available_at": "2024-05-01T00:00:00+08:00", "time_role": "RESULT_KNOWN"}],
        feedback_clocks=[{"clock_id": "a", "horizon": "EARLY_SIGNAL", "opens_at": "2025-01-01T00:00:00+08:00", "episode_claims": ["INDUSTRY_AND_SITUATION"], "discriminating_observation": "早期信号"},
                         {"clock_id": "b", "horizon": "LONG_TERM_PERMANENT_LOSS", "opens_at": "2027-01-01T00:00:00+08:00", "episode_claims": ["PERMANENT_LOSS"], "discriminating_observation": "长期回报"}],
        economic_derivation_interface=ECONOMIC_DERIVATION_INTERFACE,
    )
    source_index = {"E1": {"source_ref": "SRC:TEST", "available_at": "2024-05-01T00:00:00+08:00", "time_role": "RESULT_KNOWN"}}
    result = compile_staged_judgment_ledger(ledger, source_index, contract)
    assert result["diagnostics"]["state"] == "COMPILED"
    assert result["episode"] is not None
    assert result["episode"]["economic_derivation"]["normal_earnings_bridge"] == ledger["normal_earnings_bridge"]
    assert result["episode"]["economic_derivation_summary"] == derive_economic_derivation_summary(result["episode"])
    assert result["training_episode_validation"]["state"] == "REVIEWABLE"
