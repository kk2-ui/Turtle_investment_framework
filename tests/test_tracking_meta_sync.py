import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from turtle_agent.run import (  # noqa: E402
    ArtifactClass,
    _extract_tracking_meta_from_report,
    _materialize_tracking_outputs,
)


def test_extract_tracking_meta_prefers_comparison_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "sample"
    output_dir.mkdir()

    contract = {
        "report_type": "q1",
        "fiscal_year": 2026,
        "period_end": "2026-03-31",
        "change_classification": "pending",
        "comparison_summary": "(待 Agent 填写)",
        "tracking": {
            "report_type": "q1",
            "fiscal_year": 2026,
            "period_end": "2026-03-31",
            "metric_comparison_basis": "yoy",
            "change_classification": "pending",
            "comparison_summary": "(待 Agent 填写)",
        },
        "run_meta": {
            "report_type": "q1",
            "fiscal_year": 2026,
            "period_end": "2026-03-31",
            "metric_comparison_basis": "yoy",
            "change_classification": "pending",
            "comparison_summary": "(待 Agent 填写)",
        },
    }
    (output_dir / "analysis_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "_comparison.json").write_text(
        json.dumps(
            {
                "comparison": {
                    "revenue_yoy": "+8.2%",
                    "gross_margin_delta": "+2.3pp",
                    "np_yoy": "+5.1%",
                    "ocf_yoy": "-5%",
                    "key_changes": ["毛利率连续改善", "OCF短期下降"],
                    "change_classification": "cyclical",
                    "thesis_impact": "强化",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        "## 投资要点概览\n\n**变化归因**：pending\n",
        encoding="utf-8",
    )

    _extract_tracking_meta_from_report(str(output_dir), str(output_dir / "report.md"))

    updated = json.loads((output_dir / "analysis_contract.json").read_text(encoding="utf-8"))
    assert updated["change_classification"] == "cyclical"
    assert updated["tracking"]["change_classification"] == "cyclical"
    assert updated["run_meta"]["change_classification"] == "cyclical"
    assert "营收+8.2%" in updated["comparison_summary"]
    assert "thesis=强化" in updated["comparison_summary"]
    assert updated["comparison_summary"] == updated["tracking"]["comparison_summary"]
    assert updated["comparison_summary"] == updated["run_meta"]["comparison_summary"]


def test_validation_only_never_materializes_tracking_or_latest_aliases(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    reports = output / "reports"
    drafts = reports / "drafts"
    drafts.mkdir(parents=True)
    (output / "analysis_contract.json").write_text(
        json.dumps({
            "report_type": "annual", "fiscal_year": 2025,
            "period_end": "2025-12-31",
        }),
        encoding="utf-8",
    )
    (output / "compute_bundle.json").write_text("{}", encoding="utf-8")
    formal = reports / "最新_分析报告_v13.md"
    formal.write_text("old formal", encoding="utf-8")
    draft = drafts / "000001_分析报告_v13_draft.md"
    draft.write_text("new candidate", encoding="utf-8")
    diagnostics: dict = {}

    result = _materialize_tracking_outputs(
        str(output), str(draft), diagnostics, artifact_class=ArtifactClass.DRAFT,
    )

    assert result == str(draft)
    assert formal.read_text(encoding="utf-8") == "old formal"
    assert not (reports / "2025_年报_分析报告_v13.md").exists()
    assert not (output / "analysis_contract.latest.json").exists()
    assert diagnostics["tracking"]["formal_outputs_unchanged"] is True
    assert diagnostics["tracking"]["artifact_class"] == "DRAFT"
