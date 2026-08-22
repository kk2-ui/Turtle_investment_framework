#!/usr/bin/env python3
"""Candidate-first migration for legacy thesis monitoring deadlines.

Only a missing ``resolution_due`` may be inferred mechanically, and only from
the report period plus its next comparable disclosure window.  Competitive
explanations, probabilities, thresholds, valuation effects and actions are
protected semantic content and are never rewritten by this migration.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_documents import _atomic_write_json
    from scripts.thesis_test_gate import (
        persist_thesis_test_ledger,
        thesis_test_fingerprint,
        validate_thesis_test_ledger,
    )
except ModuleNotFoundError:
    from evidence_documents import _atomic_write_json
    from thesis_test_gate import (
        persist_thesis_test_ledger,
        thesis_test_fingerprint,
        validate_thesis_test_ledger,
    )


SCHEMA_VERSION = "thesis-test-migration.v1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _report_text(output: Path) -> str:
    chapters = sorted((output / "chapters").glob("_ch*.md"))
    return "\n\n".join(path.read_text(encoding="utf-8") for path in chapters)


def _parse_day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _inferred_due(contract: dict[str, Any], probability_set: dict[str, Any]) -> tuple[str | None, str]:
    period_end = _parse_day(contract.get("period_end"))
    estimate_days = [
        day for day in (
            _parse_day(item.get("as_of"))
            for item in probability_set.get("estimates") or [] if isinstance(item, dict)
        ) if day is not None
    ]
    if not period_end or not estimate_days or max(estimate_days) != period_end:
        return None, "prediction_as_of_not_equal_report_period_end"
    report_type = str(contract.get("report_type") or "").strip().lower()
    if report_type == "annual":
        return f"{period_end.year + 1:04d}-09-30", "next_interim_period_end_plus_three_months"
    if report_type in {"interim", "semiannual", "half_year"}:
        return f"{period_end.year + 1:04d}-04-30", "next_annual_period_end_plus_four_months"
    return None, f"unsupported_report_type:{report_type or 'missing'}"


def _protected_semantics(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    for key in ("freeze", "generated_at", "updated_at", "change_reason", "lifecycle"):
        value.pop(key, None)
    for item in value.get("probability_sets") or []:
        if isinstance(item, dict):
            item.pop("resolution_due", None)
    return value


def migrate_thesis_test(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    original = _read(output / "thesis_test.json")
    contract = _read(output / "analysis_contract.json")
    policy = _read(output / "thesis_test_policy.json")
    candidate = deepcopy(original)
    semantic_frontier: list[dict[str, Any]] = []
    safe_bindings: list[dict[str, Any]] = []

    if not original:
        semantic_frontier.append({"field": "thesis_test", "reason": "canonical_ledger_missing"})
    for item in candidate.get("probability_sets") or []:
        if not isinstance(item, dict):
            semantic_frontier.append({"field": "probability_sets", "reason": "probability_set_not_object"})
            continue
        set_id = str(item.get("set_id") or "")
        existing_due = str(item.get("resolution_due") or "").strip()
        if existing_due:
            continue
        due, basis = _inferred_due(contract, item)
        if due is None:
            semantic_frontier.append({
                "set_id": set_id, "field": "resolution_due", "reason": basis,
            })
            continue
        item["resolution_due"] = due
        safe_bindings.append({
            "set_id": set_id, "field": "resolution_due", "old": None,
            "new": due, "basis": basis,
        })

    if candidate:
        candidate["lifecycle"] = "reviewable"
        candidate["change_reason"] = (
            "Deterministic monitoring migration: add missing resolution_due from the next "
            "comparable disclosure deadline; thesis semantics and decisions unchanged."
        )
        candidate["generated_at"] = _now()
        candidate["freeze"] = {"frozen": False, "fingerprint": "", "frozen_at": None}

    report_text = _report_text(output)
    candidate_validation = validate_thesis_test_ledger(
        candidate, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
        monitoring_required=bool(policy.get("monitoring_required")),
        forward_judgment_required=bool(policy.get("forward_judgment_required")),
        rival_hypothesis_pair_required=bool(policy.get("rival_hypothesis_pair_required")),
        required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or []),
    ) if candidate else {"state": "INCOMPLETE", "status": "FAIL"}

    original_validation = validate_thesis_test_ledger(
        original, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
        monitoring_required=bool(policy.get("monitoring_required")),
        forward_judgment_required=bool(policy.get("forward_judgment_required")),
        rival_hypothesis_pair_required=bool(policy.get("rival_hypothesis_pair_required")),
        required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or []),
    ) if original else {"state": "INCOMPLETE", "status": "FAIL", "invalid_findings": []}
    allowed_original_findings = {
        f"{item.get('set_id')}:resolution_due_invalid"
        for item in original.get("probability_sets") or [] if isinstance(item, dict)
        and not str(item.get("resolution_due") or "").strip()
    }
    unexpected_invalid = sorted(
        set(original_validation.get("invalid_findings") or []) - allowed_original_findings
    )
    if unexpected_invalid or original_validation.get("incomplete_findings"):
        semantic_frontier.append({
            "field": "existing_validation_findings",
            "reason": "migration_cannot_repair_non_deadline_findings",
            "findings": [*unexpected_invalid, *(original_validation.get("incomplete_findings") or [])],
        })
    if original and candidate and _protected_semantics(original) != _protected_semantics(candidate):
        semantic_frontier.append({
            "field": "protected_semantics", "reason": "candidate_changed_non_deadline_content",
        })

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "canonical_ledger_unchanged": True,
        "source_ledger_sha256": _sha(output / "thesis_test.json"),
        "source_ledger_fingerprint": thesis_test_fingerprint(original) if original else None,
        "decision_ledger_sha256": _sha(output / "decision_ledger.json"),
        "valuation_model_sha256": _sha(output / "valuation_model.json"),
        "safe_bindings": safe_bindings,
        "migration_required": bool(safe_bindings),
        "semantic_frontier": semantic_frontier,
        "candidate_validation": candidate_validation,
    }
    if persist:
        _atomic_write_json(output / "thesis_test_migration_candidate.json", candidate)
        _atomic_write_json(output / "thesis_test_migration_report.json", report)
    return {"candidate": candidate, "report": report}


def promote_thesis_test_migration(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    original = _read(output / "thesis_test.json")
    candidate = _read(output / "thesis_test_migration_candidate.json")
    report = _read(output / "thesis_test_migration_report.json")
    if not original or not candidate or not report:
        return {"promoted": False, "error": "thesis_migration_artifacts_missing"}
    if report.get("semantic_frontier"):
        return {"promoted": False, "error": "semantic_change_requires_thesis_research"}
    if not report.get("migration_required"):
        return {"promoted": False, "already_compatible": True}
    if _sha(output / "thesis_test.json") != report.get("source_ledger_sha256"):
        return {"promoted": False, "error": "thesis_migration_candidate_stale"}
    if _sha(output / "decision_ledger.json") != report.get("decision_ledger_sha256"):
        return {"promoted": False, "error": "decision_ledger_changed_during_thesis_migration"}
    if _sha(output / "valuation_model.json") != report.get("valuation_model_sha256"):
        return {"promoted": False, "error": "valuation_model_changed_during_thesis_migration"}
    if _protected_semantics(original) != _protected_semantics(candidate):
        return {"promoted": False, "error": "protected_thesis_semantics_changed"}
    if (report.get("candidate_validation") or {}).get("state") != "REVIEWABLE":
        return {"promoted": False, "error": "thesis_migration_candidate_not_reviewable"}

    final = deepcopy(candidate)
    final["lifecycle"] = "decision_ready"
    final["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    final["freeze"]["fingerprint"] = thesis_test_fingerprint(final)
    result = persist_thesis_test_ledger(
        output, final, report_text=_report_text(output), allow_frozen_update=True,
    )
    result["promoted"] = bool(result.get("written")) and (
        (result.get("validation") or {}).get("state") == "DECISION_READY"
    )
    return result
