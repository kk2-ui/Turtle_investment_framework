#!/usr/bin/env python3
"""Explicit, fingerprint-confirmed human approval for a Phase-08 gold contract."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.real_report_acceptance import GOLD_VERSION, _hash
except ModuleNotFoundError:
    from real_report_acceptance import GOLD_VERSION, _hash


CURATED_FIELDS = (
    "company_code", "report_period", "information_cutoff", "decisive_questions",
    "competitive_explanations", "required_evidence_ids", "valuation_roles",
    "decision_invariants", "known_failure_modes",
)


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def build_approval_preview(
    acceptance: dict[str, Any], draft: dict[str, Any], sample_id: str
) -> dict[str, Any]:
    sample = next(
        (item for item in acceptance.get("samples") or [] if item.get("sample_id") == sample_id),
        None,
    )
    if not isinstance(sample, dict):
        raise ValueError("sample is absent from the current acceptance baseline")
    if sample.get("machine_status") != "BENCHMARK_CANDIDATE":
        raise ValueError("only a current BENCHMARK_CANDIDATE may enter human approval")
    missing = [field for field in CURATED_FIELDS if field not in draft]
    if missing:
        raise ValueError("gold draft missing curated fields: " + ", ".join(missing))
    valid_reviews = [
        item for item in sample.get("independent_reviews") or []
        if (item.get("validation") or {}).get("status") == "VALID"
        and not item.get("duplicate_reviewer") and not item.get("fatal_findings")
    ]
    reviewer_ids = sorted({str(item.get("reviewer_id")) for item in valid_reviews if item.get("reviewer_id")})
    if len(reviewer_ids) < 2:
        raise ValueError("at least two current, independent, non-fatal reviews are required")
    contract = {
        "schema_version": GOLD_VERSION,
        "sample_id": sample_id,
        "variant_id": sample.get("variant_id"),
        "report_sha256": sample.get("report_sha256"),
        **{field: deepcopy(draft[field]) for field in CURATED_FIELDS},
        "review_ids": reviewer_ids,
        "human_approval": {"approved": False, "approved_by": "", "approved_at": ""},
    }
    preview = {
        "schema_version": "gold-approval-preview.v1",
        "sample_id": sample_id,
        "contract": contract,
    }
    preview["approval_fingerprint"] = _hash(preview)
    return preview


def approve_preview(
    preview: dict[str, Any], *, confirm_fingerprint: str, approved_by: str
) -> dict[str, Any]:
    expected = str(preview.get("approval_fingerprint") or "")
    integrity_payload = deepcopy(preview)
    integrity_payload.pop("approval_fingerprint", None)
    if not expected or _hash(integrity_payload) != expected or confirm_fingerprint != expected:
        raise ValueError("approval fingerprint mismatch; regenerate and review the preview")
    if not approved_by.strip():
        raise ValueError("approved_by is required")
    contract = deepcopy(preview["contract"])
    contract["human_approval"] = {
        "approved": True,
        "approved_by": approved_by.strip(),
        "approved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "approval_fingerprint": expected,
    }
    contract["fingerprint"] = _hash(contract)
    return contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Approve a current Phase-08 benchmark candidate")
    parser.add_argument("--acceptance-baseline", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--approved-by", default="")
    parser.add_argument("--confirm-fingerprint", default="")
    args = parser.parse_args(argv)
    preview = build_approval_preview(_load(args.acceptance_baseline), _load(args.draft), args.sample_id)
    if not args.confirm_fingerprint:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 2
    contract = approve_preview(
        preview,
        confirm_fingerprint=args.confirm_fingerprint,
        approved_by=args.approved_by,
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
