from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.claim_evidence import build_claim_evidence_ledger, validate_claim_evidence_ledger
from scripts.decisive_question import build_decisive_question_plan, validate_decisive_question_plan
from scripts.industry_knowledge import (
    review_industry_mechanism,
    write_industry_insight_candidate,
)
from scripts.turtle_agent.tools.read_tools import read_industry_knowledge_context
from scripts.valuation_model_gate import build_valuation_model_ledger, validate_valuation_model_ledger


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _candidate(candidate_id: str, group: str, period: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "status": "CANDIDATE",
        "title": "毛利变化必须与渠道费用一起观察",
        "mechanism_key": "margin_channel_cost_offset",
        "industry_keys": ["consumer_bottling"],
        "company_id": "COMPANY:" + candidate_id,
        "corporate_group_id": group,
        "reporting_period": period,
        "insight": "毛利率变化可能被销售配送费用率抵消，不能单独外推利润。",
        "applicability_conditions": ["产品组合和渠道费用均对经营利润有材料影响"],
        "non_applicability_conditions": ["销售费用与渠道履约无关且已被单列重分类"],
        "alternative_explanations": ["一次性税项或会计分类变化造成利润变化"],
        "company_verification_fields": ["毛利率", "销售配送费用率", "产品组合", "关键包材成本"],
        "evidence": [{
            "evidence_type": "OBS",
            "reference_id": "OBS:" + candidate_id,
            "source_id": "annual-report-" + candidate_id,
            "source_group_id": "filing-" + candidate_id,
            "authority": "audited_filing",
            "published_at": "2026-03-20",
            "data_as_of": period,
            "statement": "毛利率和销售费用率均由经审计年报直接披露。",
            "direct_support": True,
        }],
    }


def _ready_mechanism(candidate_ids: list[str]) -> dict:
    return {
        "mechanism_id": "IKM:margin-channel-cost-offset",
        "author_id": "mechanism-author",
        "status": "MECHANISM_READY",
        "mechanism_key": "margin_channel_cost_offset",
        "title": "毛利与渠道费用对冲",
        "summary": "产品或投入成本引起的毛利变化，可能被销售、配送或促销效率抵消或放大。",
        "industry_keys": ["consumer_bottling"],
        "candidate_ids": candidate_ids,
        "applicability_conditions": ["渠道履约费用对利润有材料影响"],
        "non_applicability_conditions": ["仅由无关的一次性会计重分类驱动"],
        "alternative_explanations": ["税率变化或一次性补贴导致利润变化"],
        "company_verification_fields": ["毛利率", "销售配送费用率", "产品组合", "关键包材成本"],
        "prohibited_uses": ["company_fact", "valuation_parameter", "probability", "automatic_investment_conclusion"],
        "independent_review": {
            "reviewer_id": "independent-reviewer",
            "reviewed_at": "2026-08-16",
            "scope": "验证机制表述、适用边界、反例、替代解释和公司取证字段",
            "outcome": "ACCEPTED",
            "independent": True,
        },
    }


def _output_metadata(output: Path) -> None:
    observation = {
        "observation_id": "OBS:annual:operations:revenue:2025:abc123",
        "status": "VERIFIED",
        "domain": "operations",
        "fact_name": "revenue",
    }
    _write(output / "fact_observations.json", {"observations": [observation]})
    _write(output / "report_context.json", {
        "meta": {"report_id": "00506.HK", "issuer": "样本装瓶商", "context_fingerprint": "a" * 64},
        "domains": {"operations": [observation]},
        "unresolved_gaps": [],
    })
    _write(output / "analysis_contract.json", {
        "ts_code": "00506.HK",
        "industry_classification": {"l1": "食品饮料", "l2": "饮料装瓶", "peer_group": "饮料"},
    })
    _write(output / "industry_context.json", {
        "meta": {"industry_l1": "食品饮料", "industry_l2": "饮料", "industry_group": "饮料"},
    })
    _write(output / "compute_bundle.json", {})
    _write(output / "company_archetype.json", {
        "primary_archetype": {"archetype_id": "mature_cash_return"},
    })


def test_ready_mechanism_from_output_metadata_becomes_not_evidenced_question(
    tmp_path: Path, monkeypatch
) -> None:
    library = tmp_path / "industry-library"
    candidate_ids = ["IKC:a", "IKC:b", "IKC:c"]
    for candidate in (
        _candidate(candidate_ids[0], "group-a", "FY2023"),
        _candidate(candidate_ids[1], "group-b", "FY2024"),
        _candidate(candidate_ids[2], "group-c", "FY2025"),
    ):
        assert write_industry_insight_candidate(candidate, knowledge_dir=library)["written"] is True
    assert review_industry_mechanism(
        _ready_mechanism(candidate_ids), knowledge_dir=library,
    )["written"] is True
    monkeypatch.setenv("TURTLE_INDUSTRY_KNOWLEDGE_DIR", str(library))

    output = tmp_path / "output"
    output.mkdir()
    _output_metadata(output)
    plan = build_decisive_question_plan(output, persist=False)

    context = plan["industry_knowledge_context"]
    match = context["matched_mechanisms"][0]
    assert match["mechanism_id"] == "IKM:margin-channel-cost-offset"
    assert match["status"] == "MECHANISM_READY"
    assert match["company_assessment"] == "NOT_EVIDENCED"
    assert match["question_injected"] is True
    assert match["alternative_explanations"] == ["税率变化或一次性补贴导致利润变化"]
    question = next(
        item for item in plan["selected_questions"]
        if "industry_knowledge:IKM:margin-channel-cost-offset" in item["candidate_origins"]
    )
    selected_mechanism_ids = {
        str(origin).split(":", 1)[1]
        for item in plan["selected_questions"]
        for origin in item.get("candidate_origins") or []
        if str(origin).startswith("industry_knowledge:")
    }
    assert match["question_injected"] is (
        match["mechanism_id"] in selected_mechanism_ids
    )
    assert question["decision_link"]["sensitivity_basis"] == {}
    assert question["competing_explanations"][0]["current_support_observation_ids"] == []
    assert question["research_tasks"][0]["annual_report_sections"] == match["company_verification_fields"]
    assert validate_decisive_question_plan(plan, output_dir=output)["state"] == "REVIEWABLE"


def test_industry_context_cannot_become_claim_model_or_probability_input(
    tmp_path: Path, monkeypatch
) -> None:
    library = tmp_path / "industry-library"
    candidate_ids = ["IKC:a", "IKC:b", "IKC:c"]
    for candidate in (
        _candidate(candidate_ids[0], "group-a", "FY2023"),
        _candidate(candidate_ids[1], "group-b", "FY2024"),
        _candidate(candidate_ids[2], "group-c", "FY2025"),
    ):
        assert write_industry_insight_candidate(candidate, knowledge_dir=library)["written"] is True
    assert review_industry_mechanism(
        _ready_mechanism(candidate_ids), knowledge_dir=library,
    )["written"] is True
    monkeypatch.setenv("TURTLE_INDUSTRY_KNOWLEDGE_DIR", str(library))
    output = tmp_path / "output"
    output.mkdir()
    _output_metadata(output)
    plan = build_decisive_question_plan(output, persist=False)

    forbidden_contract = deepcopy(plan)
    forbidden_contract["industry_knowledge_context"]["usage_contract"]["must_not_supply"].remove("valuation_parameter")
    result = validate_decisive_question_plan(forbidden_contract, output_dir=output)
    assert "industry_knowledge_usage_contract_allows_decision_input" in result["invalid_findings"]

    prematurely_supported = deepcopy(plan)
    prematurely_supported["industry_knowledge_context"]["matched_mechanisms"][0]["company_assessment"] = "SUPPORTED"
    result = validate_decisive_question_plan(prematurely_supported, output_dir=output)
    assert any(
        item.endswith(":company_assessment_must_start_not_evidenced")
        for item in result["invalid_findings"]
    )

    model_tainted = deepcopy(plan)
    question = next(
        item for item in model_tainted["selected_questions"]
        if "industry_knowledge:IKM:margin-channel-cost-offset" in item["candidate_origins"]
    )
    question["decision_link"]["sensitivity_basis"] = {"unverified_margin_assumption": 0.01}
    result = validate_decisive_question_plan(model_tainted, output_dir=output)
    assert any(
        item.endswith(":industry_knowledge_used_as_model_input")
        for item in result["invalid_findings"]
    )


def test_memory_unavailable_does_not_block_local_canonical_industry_context(
    tmp_path: Path, monkeypatch
) -> None:
    """The public local mechanism store must work without a Tencent Memory client."""
    library = tmp_path / "industry-library"
    candidate_ids = ["IKC:a", "IKC:b", "IKC:c"]
    for candidate in (
        _candidate(candidate_ids[0], "group-a", "FY2023"),
        _candidate(candidate_ids[1], "group-b", "FY2024"),
        _candidate(candidate_ids[2], "group-c", "FY2025"),
    ):
        assert write_industry_insight_candidate(candidate, knowledge_dir=library)["written"] is True
    assert review_industry_mechanism(
        _ready_mechanism(candidate_ids), knowledge_dir=library,
    )["written"] is True
    monkeypatch.setenv("TURTLE_INDUSTRY_KNOWLEDGE_DIR", str(library))

    output = tmp_path / "output"
    output.mkdir()
    _output_metadata(output)
    # No Tencent client, credential or Memory result is installed in this test.
    # The local canonical store must still provide a bounded verification agenda.
    plan = build_decisive_question_plan(output, persist=False)
    context = plan["industry_knowledge_context"]
    assert context["validation_status"] == "AVAILABLE"
    assert context["matched_mechanisms"][0]["company_assessment"] == "NOT_EVIDENCED"
    assert "industry_knowledge_context_unavailable" not in " ".join(context["warnings"])


def test_mechanism_id_cannot_be_direct_claim_evidence_or_valuation_source(tmp_path: Path) -> None:
    """Existing canonical-anchor gates must reject a mechanism card as evidence."""
    mechanism_id = "IKM:margin-channel-cost-offset"
    claim = {
        "claim_id": "claim.margin", "claim": "毛利与渠道费用需要一并验证。", "chapters": [0],
        "raw_facts": [{
            "evidence_id": "ev.invalid-mechanism", "source_id": mechanism_id,
            "source_group_id": "industry-knowledge", "fact": "机制卡不是公司直接事实。",
            "authority": "industry_data", "claim_distance": "analysis", "published_at": "2026-08-16",
            "data_as_of": "2026-08-16", "direct_support": True, "support_type": "supports",
            "basis_match": "exact", "conflict_of_interest": "机制卡仅为研究先验。", "cross_checked_by": [],
        }],
        "reasoning_steps": ["机制卡只能提出待验证问题。"],
        "alternative_explanations": ["本公司可能不满足该机制的适用条件。"],
        "applicability_conditions": ["须有本公司直接OBS/DOC证据。"],
        "confidence": {"kind": "analyst_subjective", "value": 0.5, "basis": "尚未取得公司证据。"},
        "decision_impact": {"valuation": "不改变模型", "position": "不改变仓位", "action": "继续取证"},
        "decision_entry_ids": [],
    }
    claim_payload = build_claim_evidence_ledger(
        tmp_path, [claim], change_reason="reject mechanism as direct claim evidence", freeze=False,
    )
    claim_result = validate_claim_evidence_ledger(
        claim_payload, report_text="## Ch0 测试\n[claim: claim.margin]", output_dir=tmp_path,
    )
    assert claim_result["state"] == "INVALID"
    assert f"ev.invalid-mechanism:source_unresolved:{mechanism_id}" in claim_result["invalid_findings"]

    valuation_output = tmp_path / "valuation"
    valuation_output.mkdir()
    (valuation_output / "decision_ledger.json").write_text(
        json.dumps({"entries": [{"entry_id": "valuation.v_final@base.current"}]}), encoding="utf-8",
    )
    model = {
        "model_id": "epv.invalid-mechanism-source", "model_type": "EPV", "role": "primary", "status": "active",
        "chapters": [12], "independence_group_id": "earnings", "shared_assumption_ids": [],
        "applicability": {
            "business_fit": "operating company", "cash_flow_fit": "normalized", "capital_structure_fit": "stable",
            "payout_fit": "not_applicable", "rationale": "test only", "disqualifiers": [],
        },
        "basis": {"value_scope": "equity", "cash_flow_scope": "normalized_earnings", "currency": "RMB", "as_of": "2026-08-16", "tax_basis": "post_tax"},
        "assumptions": {"discount_rate": {"value_pct": 10.0, "kind": "cost_of_equity", "inflation_basis": "nominal", "tax_basis": "post_tax"}},
        "result": {"value_per_share": 10.0},
        "terminal_value": {"present_value": 0.0, "total_model_value": 100.0, "share_pct": 0.0},
        "sensitivity_tests": [], "source_ids": [mechanism_id],
        "decision_entry_ids": ["valuation.v_final@base.current"],
    }
    valuation_payload = build_valuation_model_ledger(
        valuation_output,
        {"business_type": "general_operating", "asset_intensity": "mixed", "valuation_route": "test", "route_reasoning": "source identity rejection test"},
        [model],
        {"action": "hold", "position_pct": 0.0, "range_low": 0.0, "range_high": 0.0, "chosen_value_per_share": 10.0, "decision_rule": "test", "divergence_explanation": "", "decision_entry_id": "valuation.v_final@base.current"},
        change_reason="reject mechanism as valuation source", freeze=False,
    )
    valuation_result = validate_valuation_model_ledger(
        valuation_payload, output_dir=valuation_output,
        report_text="## Ch12 估值\n[valuation: epv.invalid-mechanism-source]", enforced=False,
    )
    assert valuation_result["state"] == "INVALID"
    assert f"epv.invalid-mechanism-source:source_unresolved:{mechanism_id}" in valuation_result["invalid_findings"]


def test_historical_plan_without_industry_context_remains_reviewable(tmp_path: Path) -> None:
    _output_metadata(tmp_path)
    plan = build_decisive_question_plan(tmp_path, persist=False)
    plan.pop("industry_knowledge_context")
    assert validate_decisive_question_plan(plan, output_dir=tmp_path)["state"] == "REVIEWABLE"
    _write(tmp_path / "decisive_question_plan.json", plan)
    result = read_industry_knowledge_context(str(tmp_path))
    assert result["ok"] is False
    assert result["error"] == "industry_knowledge_context_not_available_for_this_plan"
