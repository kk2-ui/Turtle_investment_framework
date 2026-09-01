from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from scripts.thesis_test_gate import (
    evaluate_output_thesis_test,
    initialize_thesis_test_policy,
)
from scripts.thesis_test_migration import (
    migrate_thesis_test,
    promote_thesis_test_migration,
)
from tests.test_stage14_thesis_test_gate import _payload, _report


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup(output: Path) -> dict:
    payload = _payload(output)
    (output / "analysis_contract.json").write_text(json.dumps({
        "ts_code": "TEST.HK", "period_end": "2026-08-02", "report_type": "annual",
    }), encoding="utf-8")
    initialize_thesis_test_policy(
        output, run_id="migration", enforced=True, monitoring_required=True,
    )
    (output / "thesis_test.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    chapters = output / "chapters"
    chapters.mkdir(exist_ok=True)
    for block in _report().split("\n\n"):
        line = block.splitlines()[0]
        index = int(line.split("Ch", 1)[1].split()[0])
        (chapters / f"_ch{index:02d}.md").write_text(block, encoding="utf-8")
    (output / "valuation_model.json").write_text("{}", encoding="utf-8")
    return payload


def test_missing_resolution_due_migrates_candidate_first_and_promotes(tmp_path: Path) -> None:
    original = _setup(tmp_path)
    canonical_before = _sha(tmp_path / "thesis_test.json")
    decision_before = _sha(tmp_path / "decision_ledger.json")
    result = migrate_thesis_test(tmp_path)

    assert _sha(tmp_path / "thesis_test.json") == canonical_before
    assert result["report"]["semantic_frontier"] == []
    assert result["report"]["candidate_validation"]["state"] == "REVIEWABLE"
    assert result["candidate"]["probability_sets"][0]["resolution_due"] == "2027-09-30"
    candidate_without_due = deepcopy(result["candidate"])
    candidate_without_due["probability_sets"][0].pop("resolution_due")
    for payload in (original, candidate_without_due):
        for key in ("freeze", "generated_at", "change_reason", "lifecycle"):
            payload.pop(key, None)
    assert candidate_without_due == original

    promoted = promote_thesis_test_migration(tmp_path)
    assert promoted["promoted"] is True
    assert evaluate_output_thesis_test(tmp_path, report_text=_report(), persist=False)["state"] == "DECISION_READY"
    assert _sha(tmp_path / "decision_ledger.json") == decision_before


def test_non_deadline_validation_failure_blocks_migration(tmp_path: Path) -> None:
    payload = _setup(tmp_path)
    payload["thresholds"][0]["threshold_value"] = "invalid"
    (tmp_path / "thesis_test.json").write_text(json.dumps(payload), encoding="utf-8")
    canonical_before = _sha(tmp_path / "thesis_test.json")

    result = migrate_thesis_test(tmp_path)

    assert result["report"]["semantic_frontier"]
    assert any(
        item.get("field") == "existing_validation_findings"
        for item in result["report"]["semantic_frontier"]
    )
    assert promote_thesis_test_migration(tmp_path)["error"] == "semantic_change_requires_thesis_research"
    assert _sha(tmp_path / "thesis_test.json") == canonical_before


def test_prediction_as_of_mismatch_requires_research(tmp_path: Path) -> None:
    payload = _setup(tmp_path)
    payload["probability_sets"][0]["estimates"][0]["as_of"] = "2026-07-31"
    payload["probability_sets"][0]["estimates"][1]["as_of"] = "2026-07-31"
    (tmp_path / "thesis_test.json").write_text(json.dumps(payload), encoding="utf-8")

    result = migrate_thesis_test(tmp_path)

    assert any(
        item.get("reason") == "prediction_as_of_not_equal_report_period_end"
        for item in result["report"]["semantic_frontier"]
    )


def test_migration_is_idempotent_after_promotion(tmp_path: Path) -> None:
    _setup(tmp_path)
    migrate_thesis_test(tmp_path)
    assert promote_thesis_test_migration(tmp_path)["promoted"] is True

    rerun = migrate_thesis_test(tmp_path)

    assert rerun["report"]["migration_required"] is False
    assert rerun["report"]["semantic_frontier"] == []
    assert promote_thesis_test_migration(tmp_path)["already_compatible"] is True


def test_unified_pipeline_runs_thesis_candidate_first_hook() -> None:
    source = (Path(__file__).parents[1] / "scripts/turtle_agent/run.py").read_text(encoding="utf-8")
    assert "migrate_thesis_test(output_dir, persist=True)" in source
    assert "promote_thesis_test_migration(output_dir)" in source
