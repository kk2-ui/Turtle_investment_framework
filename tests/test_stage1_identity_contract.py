from pathlib import Path

import pytest

from scripts.compute_bundle import _extract_annual_report_dividend_plan, compute_factor4
from scripts.turtle_agent.tools.write_tools import (
    _check_dividend_identity,
    write_decision_manifest,
)


def test_hk_annual_report_dividend_preserves_reported_currency(tmp_path: Path) -> None:
    (tmp_path / "2025_年报.md").write_text(
        "董事会建议末期股息每股人民币 0.145元，H股股息将以港元支付。",
        encoding="utf-8",
    )

    plan = _extract_annual_report_dividend_plan(str(tmp_path))

    assert plan["final_per_share"] == pytest.approx(0.145)
    assert plan["currency"] == "RMB"


def test_factor4_normalizes_rmb_dps_to_hkd_before_yield() -> None:
    factor4 = compute_factor4(
        factor3={
            "g_adj": 2.0,
            "gg": {"base": 6.0},
            "aa_avg": {"3y": 100.0},
            "np_avg_3y": 100.0,
            "extrapolation_rating": {"overall": "medium"},
        },
        market={
            "native_currency": "HKD",
            "price_native": 2.02,
            "price_rmb": 2.02 * 0.9346,
            "mc_rmb": 1890.0,
            "shares_m": 1000.0,
            "fx": 0.9346,
        },
        params={
            "II": 5.5,
            "Q": 0.10,
            "dps_latest": 0.145,
            "dps_currency": "RMB",
            "dps_period": "FY2025",
            "dps_fy_source": "2025_年报.md",
        },
    )

    identity = factor4["dividend_identity"]
    assert identity["dps_native"] == pytest.approx(0.1551, abs=0.0001)
    assert identity["yield_pretax_pct"] == pytest.approx(7.68, abs=0.01)
    assert factor4["ddm_v_native"] == pytest.approx(4.52, abs=0.02)


def test_dividend_identity_is_a_hard_consistency_check() -> None:
    bundle = {
        "factor4": {
            "dps_yield_pretax": 7.68,
            "dividend_identity": {
                "yield_pretax_pct": 7.68,
                "price_currency": "HKD",
                "period": "FY2025",
            },
        }
    }

    failed = _check_dividend_identity("当前股息率约3.37%。", bundle)
    passed = _check_dividend_identity("当前股息率约7.68%。", bundle)

    assert failed["status"] == "FAIL"
    assert failed["contradictions"][0]["reported_yield_pct"] == 3.37
    assert passed["status"] == "PASS"


def test_peer_dividend_percentile_is_not_a_company_yield_contradiction() -> None:
    bundle = {"factor4": {"dividend_identity": {"yield_pretax_pct": 7.68}}}
    report = "| get_peer_comparison | 股息率 P57.7(3.37%)，行业中位 3.32% |"

    assert _check_dividend_identity(report, bundle)["status"] == "PASS"


def test_after_tax_dividend_claim_uses_after_tax_canonical_value() -> None:
    bundle = {"factor4": {"dividend_identity": {
        "yield_pretax_pct": 7.68,
        "yield_after_tax_pct": 6.91,
    }}}

    assert _check_dividend_identity("税后股息率6.91%。", bundle)["status"] == "PASS"
    assert _check_dividend_identity("税后股息率3.40%。", bundle)["status"] == "FAIL"


def test_decision_manifest_commits_display_identity_and_observation_position(tmp_path: Path) -> None:
    result = write_decision_manifest(
        output_dir=str(tmp_path),
        qualitative_decision="pause",
        quantitative_decision="hold",
        position_pct=1.5,
        qualitative_rationale="主业稳定但外拓质量待验证",
        quantitative_rationale="价格尚未提供足够安全边际",
    )

    manifest = result["manifest"]
    assert manifest["display_label"] == "Hold Review"
    assert manifest["decision_family"] == "Hold"
    assert manifest["position_pct"] == pytest.approx(1.5)
    assert (tmp_path / "decision_manifest.json").exists()
