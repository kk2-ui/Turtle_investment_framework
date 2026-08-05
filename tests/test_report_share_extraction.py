import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from compute_bundle import _align_report_shares_with_market, _extract_report_shares_m_from_markdown  # noqa: E402


def test_extract_report_shares_requires_explicit_share_unit(tmp_path):
    report = tmp_path / "2025_年报.md"
    report.write_text(
        "\n".join(
            [
                "綜合財務狀況表",
                "股本 26(a) 6,741 6,741",
                "儲備 1,311,702 1,238,914",
            ]
        ),
        encoding="utf-8",
    )

    assert _extract_report_shares_m_from_markdown(str(report)) is None


def test_extract_report_shares_from_explicit_total_shares_line(tmp_path):
    report = tmp_path / "2025_年报.md"
    report.write_text("期末总股本 814,126,000股\n", encoding="utf-8")

    assert _extract_report_shares_m_from_markdown(str(report)) == 814.126


def test_align_report_shares_with_market_handles_thousand_share_scale():
    aligned, mode = _align_report_shares_with_market(3.28686, 3283.96046)

    assert mode == "report_x1000"
    assert aligned == 3286.86
