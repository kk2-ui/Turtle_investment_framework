from pathlib import Path

from scripts.turtle_agent.tools.calc_tools import compute_data_quality


def test_empty_packet_does_not_create_negative_valuation_direction(tmp_path: Path) -> None:
    result = compute_data_quality(str(tmp_path))

    assert result["completeness_pct"] == 0.0
    assert result["automatic_discount_pct"] == 0.0
    assert result["discount_recommendation"] == "0% automatic point-estimate adjustment"
    assert "不自动降低估值中枢" in result["confidence_treatment"]
    assert "15-25%" not in result["summary"]


def test_complete_packet_does_not_create_unearned_valuation_premium(tmp_path: Path) -> None:
    expected_files = [
        "compute_bundle.json",
        "financial_trends.json",
        "industry_context.json",
        "mda.json",
        "segments.json",
        "risks.json",
        "governance.json",
        "audit.json",
        "moat_assessment.json",
        "capex_classification.json",
        "earnings_quality.json",
        "data_discount.json",
    ]
    for name in expected_files:
        (tmp_path / name).write_text("{}", encoding="utf-8")

    result = compute_data_quality(str(tmp_path))

    assert result["completeness_pct"] == 100.0
    assert result["automatic_discount_pct"] == 0.0
    assert "不因完整性本身增加估值溢价" in result["confidence_treatment"]
