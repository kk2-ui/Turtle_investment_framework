import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from boundary_validator import ZONE_J_SCHEMAS, validate_file  # noqa: E402
import zone_j_agent  # noqa: E402
from turtle_agent.tools.phase_tools import extract_zone_j  # noqa: E402
from zone_j_agent import (  # noqa: E402
    _validate_param_wrapper,
    build_context,
    validate_economic_discount_semantics,
)


def test_boundary_validator_accepts_wrapped_moat_params_without_moat_rating():
    data = {
        "moat_evidence": [
            {
                "type": "brand",
                "evidence": "brand strength",
                "quote": "quoted evidence",
                "durability": "5年以上",
            }
        ],
        "b_penalty_final": {
            "value": 0.2,
            "rationale": "low-quality segment exists",
            "evidence_ref": ["segments.json:1"],
            "confidence": "medium",
        },
        "g_base": {
            "value": 2.0,
            "rationale": "mature business",
            "evidence_ref": ["mda.json:2"],
            "confidence": "medium",
        },
        "g_scenarios": {"pessimistic": 1.0, "base": 2.0, "optimistic": 3.0},
        "value_trap_signals": ["margin compression"],
    }

    errors = validate_file(data, ZONE_J_SCHEMAS["moat_assessment.json"], "moat_assessment.json")

    assert errors == []


def test_boundary_validator_accepts_wrapped_data_discount_param():
    data = {
        "discount_factors": [
            {"factor": "data gap", "discount_pct": 10, "rationale": "missing note facts"}
        ],
        "total_discount_pct": {
            "value": 15,
            "rationale": "combined effect",
            "evidence_ref": ["audit.json:1"],
            "confidence": "low",
        },
        "confidence_by_section": {
            "factor2": "medium",
            "factor3_aa": "low",
            "factor3_gg": "low",
            "factor4_ddm": "medium",
        },
    }

    errors = validate_file(data, ZONE_J_SCHEMAS["data_discount.json"], "data_discount.json")

    assert errors == []


def test_zone_j_agent_wrapper_validation_requires_evidence_ref_and_confidence():
    data = {
        "total_discount_pct": {
            "value": 15,
            "rationale": "combined effect",
            "evidence_ref": ["audit.json:1"],
            "confidence": "low",
        }
    }

    assert _validate_param_wrapper(data, "total_discount_pct") == []


def test_zone_j_agent_wrapper_validation_accepts_legacy_numeric():
    data = {"total_discount_pct": 15}

    assert _validate_param_wrapper(data, "total_discount_pct") == []


def test_data_quality_missing_inputs_lower_confidence_without_fixed_discount(tmp_path):
    context = build_context("data_quality", str(tmp_path), "000001.SZ")

    hint = context["_degraded"]["hint"]
    assert "扩大估值区间" in hint
    assert "total_discount_pct.value=0" in hint
    assert "默认15%" not in hint


def test_governance_summary_keeps_raw_discount_strings_as_unverified_candidates():
    text = zone_j_agent._format_qualitative_context({
        "ch8_governance": {
            "governance_rating": "mixed",
            "key_concerns": ["controller capital allocation"],
            "data_discount_signals": ["客户集中度未披露"],
        },
    })

    assert "待验证经济损失候选（裸字符串不进入折价" in text
    assert "已观察经济损失载体" not in text


def test_governance_missing_inputs_do_not_create_governance_haircut(tmp_path):
    context = build_context("governance_tension", str(tmp_path), "000001.SZ")

    hint = context["_degraded"]["hint"]
    assert "governance_discount.additional_discount_pct=0" in hint
    assert "不得从缺失" in hint


def test_unified_zone_j_runtime_sends_materialized_lilu_prompt(tmp_path, monkeypatch):
    stock_dir = tmp_path / "000001_示例公司"
    stock_dir.mkdir()
    captured: list[str] = []

    class _Response:
        content = '{"discount_basis":"observed_economic_carrier_v1","total_discount_pct":{"value":0,"rationale":"no observed loss carrier","evidence_ref":["audit.json"],"confidence":"low"}}'

    class _Client:
        def chat_with_retry(self, *, messages, temperature):
            captured.append(messages[0]["content"])
            return _Response()

    monkeypatch.setattr(
        zone_j_agent,
        "AGENTS",
        {"data_quality": dict(zone_j_agent.AGENTS["data_quality"])},
    )

    result = extract_zone_j("000001.SZ", str(stock_dir), _Client())

    assert result["ok"] is True
    assert len(captured) == 1
    assert "示例公司" in captured[0]
    assert "缺失本身没有方向" in captured[0]
    assert "financial_trends.json" in captured[0]
    assert "默认15%" not in captured[0]


def test_unified_zone_j_runtime_regenerates_legacy_data_discount(tmp_path, monkeypatch):
    stock_dir = tmp_path / "000001_示例公司"
    stock_dir.mkdir()
    (stock_dir / "data_discount.json").write_text(
        '{"total_discount_pct":15}', encoding="utf-8"
    )
    calls = 0

    class _Response:
        content = '{"discount_basis":"observed_economic_carrier_v1","total_discount_pct":{"value":0,"rationale":"no observed loss carrier","evidence_ref":["audit.json"],"confidence":"low"}}'

    class _Client:
        def chat_with_retry(self, *, messages, temperature):
            nonlocal calls
            calls += 1
            return _Response()

    monkeypatch.setattr(
        zone_j_agent,
        "AGENTS",
        {"data_quality": dict(zone_j_agent.AGENTS["data_quality"])},
    )

    result = extract_zone_j("000001.SZ", str(stock_dir), _Client())

    assert result["ok"] is True
    assert calls == 1
    regenerated = __import__("json").loads(
        (stock_dir / "data_discount.json").read_text(encoding="utf-8")
    )
    assert regenerated["discount_basis"] == "observed_economic_carrier_v1"

    reused = extract_zone_j("000001.SZ", str(stock_dir), _Client())
    assert reused["ok"] is True
    assert reused["results"][0]["skipped"] is True
    assert calls == 1


def test_unified_zone_j_runtime_rejects_nonzero_missing_disclosure_haircut_without_carrier(
    tmp_path, monkeypatch,
):
    stock_dir = tmp_path / "000001_示例公司"
    stock_dir.mkdir()
    calls = 0

    class _Response:
        content = '{"discount_basis":"observed_economic_carrier_v1","total_discount_pct":{"value":8,"rationale":"missing disclosure","evidence_ref":["audit.json"],"confidence":"low"}}'

    class _Client:
        def chat_with_retry(self, *, messages, temperature):
            nonlocal calls
            calls += 1
            return _Response()

    monkeypatch.setattr(
        zone_j_agent,
        "AGENTS",
        {"data_quality": dict(zone_j_agent.AGENTS["data_quality"])},
    )

    result = extract_zone_j("000001.SZ", str(stock_dir), _Client())

    assert result["ok"] is False
    assert calls == 2
    assert not (stock_dir / "data_discount.json").exists()


def test_unified_zone_j_runtime_regenerates_legacy_governance_discount(tmp_path, monkeypatch):
    stock_dir = tmp_path / "000001_示例公司"
    stock_dir.mkdir()
    (stock_dir / "governance_tension.json").write_text(
        '{"governance_discount":5}', encoding="utf-8"
    )
    calls = 0

    class _Response:
        content = '{"discount_basis":"observed_economic_carrier_v1","governance_discount":{"additional_discount_pct":0,"economic_carrier":{"status":"NOT_OBSERVED"}}}'

    class _Client:
        def chat_with_retry(self, *, messages, temperature):
            nonlocal calls
            calls += 1
            return _Response()

    monkeypatch.setattr(
        zone_j_agent,
        "AGENTS",
        {"governance_tension": dict(zone_j_agent.AGENTS["governance_tension"])},
    )

    regenerated = extract_zone_j("000001.SZ", str(stock_dir), _Client())
    reused = extract_zone_j("000001.SZ", str(stock_dir), _Client())

    assert regenerated["ok"] is True
    assert reused["results"][0]["skipped"] is True
    assert calls == 1


def test_governance_discount_rejects_unknown_sentinel_carrier():
    data = {
        "discount_basis": "observed_economic_carrier_v1",
        "governance_discount": {
            "additional_discount_pct": 5,
            "economic_carrier": {
                "status": "OBSERVED",
                "responsibility_unit": "UNKNOWN",
                "amount_or_range": "NOT_OBSERVED",
                "period": "UNKNOWN",
                "cash_transmission": "UNKNOWN",
                "evidence_ref": ["UNKNOWN"],
            },
        },
    }

    assert validate_economic_discount_semantics("governance_tension", data)


def test_data_quality_nonzero_discount_requires_observed_economic_carrier():
    data = {
        "discount_basis": "observed_economic_carrier_v1",
        "total_discount_pct": {
            "value": 8,
            "rationale": "some disclosures are missing",
            "evidence_ref": ["audit.json"],
            "confidence": "low",
        },
    }

    assert validate_economic_discount_semantics("data_quality", data) == [
        "MISSING: observed total_discount_pct economic_carrier"
    ]


def test_data_quality_nonzero_discount_accepts_complete_observed_cash_carrier():
    data = {
        "discount_basis": "observed_economic_carrier_v1",
        "total_discount_pct": {
            "value": 8,
            "rationale": "controller affiliate cash occupation",
            "evidence_ref": ["audit.json:related_party"],
            "confidence": "high",
            "economic_carrier": {
                "status": "OBSERVED",
                "responsibility_unit": "listed parent",
                "amount_or_range": "RMB 500m",
                "period": "FY2024",
                "cash_transmission": "cash unavailable to ordinary shareholders",
                "evidence_ref": ["audit.json:related_party"],
            },
        },
    }

    assert validate_economic_discount_semantics("data_quality", data) == []


def test_governance_discount_rejects_out_of_range_haircut():
    data = {
        "discount_basis": "observed_economic_carrier_v1",
        "governance_discount": {"additional_discount_pct": 49},
    }

    assert validate_economic_discount_semantics("governance_tension", data) == [
        "RANGE: governance_discount.additional_discount_pct must be 0..10"
    ]
