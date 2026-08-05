#!/usr/bin/env python3
"""Seed an isolated Phase 08 candidate from verified, pre-writing inputs only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "acceptance-candidate-seed.v1"
EXACT_INPUTS = {
    "analysis_contract.json", "compute_bundle.json", "financial_trends.json", "industry_context.json",
    "mda.json", "segments.json", "risks.json", "governance.json", "audit.json",
    "moat_assessment.json", "capex_classification.json", "earnings_quality.json",
    "data_discount.json", "governance_tension.json", "qualitative_summary.json",
    "data_pack_market.md", "data_pack_report.md", "valuation_computed.md",
    "_technical_snapshot.json", "_technical_appendix.md",
}
RAW_PATTERN = re.compile(
    r"^(?:[A-Za-z0-9.]+_)?20\d{2}_(?:年报|中报)(?:[^/]*)\.(?:pdf|md)$|"
    r"^(?:page_map|pdf_sections|pdf_read_status)_?20\d{2}.*\.json$"
)
FORBIDDEN_NAMES = {
    "completion_report.json", "publication_snapshot.json", "run_manifest.json",
    "decision_ledger.json", "claim_evidence.json", "valuation_model.json", "thesis_test.json",
    "insight_ledger.json", "judgment_review.json", "research_execution.json",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed_candidate(source: str | Path, target: str | Path) -> dict[str, Any]:
    source_path = Path(source).resolve()
    target_path = Path(target).resolve()
    if not source_path.is_dir():
        raise ValueError("source directory missing")
    if target_path.exists() and any(target_path.iterdir()):
        raise ValueError("target must be absent or empty; existing candidate is never overwritten")
    if source_path == target_path or source_path in target_path.parents:
        raise ValueError("target cannot be source or nested inside source")
    selected: list[Path] = []
    for path in sorted(source_path.iterdir()):
        if not path.is_file() or path.name in FORBIDDEN_NAMES:
            continue
        if path.name in EXACT_INPUTS or RAW_PATTERN.match(path.name):
            selected.append(path)
    if "analysis_contract.json" not in {path.name for path in selected}:
        raise ValueError("analysis_contract.json missing from source")
    if "compute_bundle.json" not in {path.name for path in selected}:
        raise ValueError("compute_bundle.json missing from source")
    target_path.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for path in selected:
        destination = target_path / path.name
        shutil.copy2(path, destination)
        files.append({
            "name": path.name, "sha256": _hash(destination), "size_bytes": destination.stat().st_size,
            "role": "pre_writing_input",
        })
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_dir": str(source_path),
        "target_dir": str(target_path),
        "created_at": _now(),
        "policy": {
            "prior_reports_copied": False,
            "prior_chapters_copied": False,
            "prior_decision_ledgers_copied": False,
            "raw_filings_preserved": True,
        },
        "files": files,
    }
    (target_path / "acceptance_candidate_seed.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed isolated Phase 08 report candidate")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args(argv)
    result = seed_candidate(args.source, args.target)
    print(json.dumps({"target": result["target_dir"], "file_count": len(result["files"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
