from __future__ import annotations

import json
from pathlib import Path

from scripts.real_report_acceptance import (
    PHASE10_PRODUCTION_FREEZE_CONFIG_NAME,
    PHASE10_PRODUCTION_FREEZE_PHASE,
    REQUIRED_MACHINE_GATES,
    evaluate_acceptance,
    evaluate_phase10_production_freeze_acceptance,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _production_report(output: Path) -> None:
    report = output / "reports" / "600340_分析报告_v13.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# 历史时点生产报告\n\n## 结论\n\n证据、机制、估值与动作。\n", encoding="utf-8")


def _pass_phase08_machine_gates(output: Path) -> None:
    for gate, (filename, accepted) in REQUIRED_MACHINE_GATES.items():
        key = "status" if gate in {"completion", "runtime_manifest", "absolute_quality"} else "state"
        payload = {key: sorted(accepted)[0]}
        if gate == "thesis_test":
            payload["forward_judgment_state"] = "DECISION_READY"
        _write_json(output / filename, payload)
    _write_json(output / "research_execution.json", {
        "enforced": True,
        "chapters": {
            "2": {
                "enforced": True,
                "tool_counts": {"read_section": 2},
                "fiscal_years": [2018, 2019],
                "sections": ["MDA", "STMT"],
            },
        },
    })
    _write_json(output / "judgment_review_validation.json", {
        "state": "REVIEWED", "ceiling_verdict": "COMPETENT",
    })
    _write_json(output / "judgment_review.json", {
        "ceiling_verdict": "COMPETENT", "fragile_leaps": [], "dimension_assessments": {},
    })


def test_phase10_production_freeze_uses_separate_root_and_normal_phase08_gates(tmp_path: Path) -> None:
    output = tmp_path / "historical-output"
    root = tmp_path / "phase10-acceptance"
    _production_report(output)
    _pass_phase08_machine_gates(output)

    result = evaluate_phase10_production_freeze_acceptance(
        sample_id="600340_20200427",
        company_code="600340.SH",
        output_dir=output,
        report_period="FY2019",
        acceptance_root=root,
    )

    assert result["samples"][0]["machine_status"] == "READY_FOR_BLIND_REVIEW"
    assert result["samples"][0]["hard_gates"]["passed"] is True
    config = json.loads((root / PHASE10_PRODUCTION_FREEZE_CONFIG_NAME).read_text(encoding="utf-8"))
    assert config["phase"] == PHASE10_PRODUCTION_FREEZE_PHASE
    assert config["samples"][0]["role"] == "historical_production_freeze"
    assert (root / "acceptance_baseline.json").is_file()
    rerun = evaluate_acceptance(
        root / PHASE10_PRODUCTION_FREEZE_CONFIG_NAME,
        acceptance_root=root,
        persist=False,
    )
    assert rerun["samples"][0]["machine_status"] == "READY_FOR_BLIND_REVIEW"


def test_phase10_production_freeze_blocks_any_missing_normal_v3_gate(tmp_path: Path) -> None:
    output = tmp_path / "historical-output"
    _production_report(output)
    _pass_phase08_machine_gates(output)
    _write_json(output / "claim_evidence_validation.json", {"state": "INCOMPLETE"})

    result = evaluate_phase10_production_freeze_acceptance(
        sample_id="600340_20200427",
        company_code="600340.SH",
        output_dir=output,
        report_period="FY2019",
        acceptance_root=tmp_path / "phase10-acceptance",
        persist=False,
    )

    sample = result["samples"][0]
    assert sample["machine_status"] == "TECHNICALLY_BLOCKED"
    assert "claim_evidence:INCOMPLETE" in sample["hard_gates"]["blocking"]
