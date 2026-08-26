#!/usr/bin/env python3
"""Validate the intentionally narrow NO_PRIMARY boundary case contract."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _time(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_boundary_case(case: dict[str, Any], *, contract_path: str | Path | None = None) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(case, dict):
        return {"schema_version": "judgment-boundary-case-validation.v1", "state": "INVALID", "findings": ["case_not_object"]}
    if case.get("schema_version") != "judgment-boundary-case.v1":
        findings.append("schema_version_invalid")
    for field in ("case_id", "experiment_id", "company_id", "company_cluster_id", "industry_id", "boundary_question"):
        if not str(case.get(field) or "").strip():
            findings.append(field + "_missing")
    if not str(case.get("case_id") or "").startswith("BOUNDARYCASE:"):
        findings.append("case_id_invalid")
    if not str(case.get("freeze_id") or "").startswith("BFREEZE:"):
        findings.append("freeze_id_invalid")
    if case.get("selection_status") != "NO_PRIMARY":
        findings.append("selection_status_must_be_no_primary")
    if not _time(case.get("cutoff_at")):
        findings.append("cutoff_at_invalid")
    facts = case.get("shared_facts")
    if not isinstance(facts, list) or not facts:
        findings.append("shared_facts_missing")
    else:
        for index, fact in enumerate(facts):
            if not isinstance(fact, dict) or not str(fact.get("statement") or "").strip() or not isinstance(fact.get("source_ids"), list) or not fact["source_ids"]:
                findings.append(f"shared_facts[{index}]_invalid")
    unknowns = case.get("unknowns")
    if not isinstance(unknowns, list) or not unknowns:
        findings.append("unknowns_missing")
    else:
        for index, unknown in enumerate(unknowns):
            if not isinstance(unknown, dict):
                findings.append(f"unknowns[{index}]_not_object")
                continue
            for field in ("statement", "economic_impact"):
                if not str(unknown.get(field) or "").strip():
                    findings.append(f"unknowns[{index}]_{field}_missing")
            if not isinstance(unknown.get("prohibited_substitutes"), list) or not unknown["prohibited_substitutes"]:
                findings.append(f"unknowns[{index}]_prohibited_substitutes_missing")
    rule = case.get("boundary_rule")
    if not isinstance(rule, dict):
        findings.append("boundary_rule_missing")
    else:
        for field in ("rule_id", "state_scope", "measurement_scope", "stop_condition"):
            if not str(rule.get(field) or "").strip():
                findings.append("boundary_rule_" + field + "_missing")
        if not isinstance(rule.get("required_fields"), list) or not rule["required_fields"]:
            findings.append("boundary_rule_required_fields_missing")
    review = case.get("independent_review")
    if not isinstance(review, dict):
        findings.append("independent_review_missing")
    else:
        for field in ("reviewer_id", "receipt_ref"):
            if not str(review.get(field) or "").strip():
                findings.append("independent_review_" + field + "_missing")
        if review.get("verdict") != "BOUNDARY_ACCEPTED":
            findings.append("independent_review_verdict_invalid")
        if not _time(review.get("reviewed_at")):
            findings.append("independent_review_reviewed_at_invalid")
        if contract_path is not None:
            receipt = Path(str(review.get("receipt_ref") or ""))
            if not receipt.is_absolute():
                receipt = Path(contract_path).resolve().parent / receipt
            if not receipt.is_file():
                findings.append("independent_review_receipt_missing")
    return {"schema_version": "judgment-boundary-case-validation.v1", "state": "INVALID" if findings else "REVIEWABLE", "findings": findings}


def read_boundary_case(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
