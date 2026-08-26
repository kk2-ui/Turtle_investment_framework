#!/usr/bin/env python3
"""Bind an ordinary unified report to the synthesis view it actually read."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-handoff-read-receipt.v1"
VALIDATION_SCHEMA_VERSION = "judgment-handoff-read-receipt-validation.v1"
RECEIPT_FILENAME = "judgment_handoff_read_receipt.json"
SYNTHESIS_VIEW = "JUDGMENT_SYNTHESIS"
INVESTMENT_VIEW = "INVESTMENT_ENRICHMENT"
INVESTMENT_RECEIPT_FILENAME = "investment_enrichment_read_receipt.json"

SYNTHESIS_SOURCES = (
    "analysis_contract.json",
    "claim_evidence.json",
    "claim_evidence_validation.json",
    "financial_driver_bridge.json",
    "financial_driver_bridge_validation.json",
    "thesis_test.json",
    "thesis_test_validation.json",
    "insight_ledger.json",
    "insight_validation.json",
)

RUN_POLICY_FILES = (
    "claim_evidence_policy.json",
    "financial_driver_bridge_policy.json",
    "thesis_test_policy.json",
    "insight_policy.json",
)

IDENTITY_FIELDS = (
    "report_id", "company_id", "analysis_purpose", "information_cutoff",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pit_production(output: Path) -> bool:
    contract = _read_json(output / "analysis_contract.json")
    return isinstance(contract.get("pit_production"), dict)


def _source_versions(output: Path) -> dict[str, dict[str, Any]]:
    versions: dict[str, dict[str, Any]] = {}
    for name in SYNTHESIS_SOURCES:
        path = output / name
        if not path.is_file():
            versions[name] = {"exists": False}
            continue
        stat = path.stat()
        versions[name] = {
            "exists": True,
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
    return versions


def _canonical_source_versions(output: Path, handoff: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Record contract-bound CJO/overlay files that the handoff actually read."""
    versions: dict[str, dict[str, Any]] = {}
    for source in handoff.get("source_refs") or []:
        if not isinstance(source, dict) or source.get("role") not in {
            "FROZEN_CJO", "CJO_QUANTITATIVE_OVERLAY",
        }:
            continue
        role = str(source["role"])
        ref = str(source.get("artifact_ref") or "").strip()
        path = Path(ref).expanduser()
        path = path if path.is_absolute() else output / path
        if not path.is_file():
            versions[role] = {"artifact_ref": ref, "exists": False}
            continue
        stat = path.stat()
        versions[role] = {
            "artifact_ref": ref,
            "exists": True,
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
    return versions


def _run_identity(output: Path) -> dict[str, Any]:
    policy_run_ids: dict[str, str] = {}
    enforced: dict[str, bool] = {}
    for name in RUN_POLICY_FILES:
        policy = _read_json(output / name)
        policy_run_ids[name] = str(policy.get("run_id") or "").strip()
        enforced[name] = bool(policy.get("enforced"))
    distinct = sorted({value for value in policy_run_ids.values() if value})
    return {
        "run_id": distinct[0] if len(distinct) == 1 else "",
        "policy_run_ids": policy_run_ids,
        "policy_enforced": enforced,
        "consistent": len(distinct) == 1 and all(policy_run_ids.values()),
    }


def ordinary_synthesis_receipt_required(output_dir: str | Path) -> bool:
    """Return whether the current output uses the complete unified policy set."""
    output = Path(output_dir).expanduser().resolve()
    if _pit_production(output):
        return False
    identity = _run_identity(output)
    contract = _read_json(output / "analysis_contract.json")
    refs = contract.get("canonical_judgment_refs") if isinstance(contract.get("canonical_judgment_refs"), dict) else {}
    return all(identity["policy_enforced"].values()) or bool(str(refs.get("frozen_cjo_ref") or "").strip())


def handoff_read_receipt_required(output_dir: str | Path, view: str = SYNTHESIS_VIEW) -> bool:
    output = Path(output_dir).expanduser().resolve()
    normalized_view = str(view or "").upper()
    if normalized_view == SYNTHESIS_VIEW:
        return ordinary_synthesis_receipt_required(output)
    if normalized_view != INVESTMENT_VIEW:
        return False
    contract = _read_json(output / "analysis_contract.json")
    refs = contract.get("canonical_judgment_refs") if isinstance(contract.get("canonical_judgment_refs"), dict) else {}
    return bool(str(refs.get("investment_overlay_ref") or "").strip())


def _receipt_filename(view: str) -> str:
    return RECEIPT_FILENAME if view == SYNTHESIS_VIEW else INVESTMENT_RECEIPT_FILENAME


def record_judgment_handoff_read_receipt(
    output_dir: str | Path,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    """Persist a required contract-bound report read without copying its content."""
    output = Path(output_dir).expanduser().resolve()
    view = str(handoff.get("view") or "").upper() if isinstance(handoff, dict) else ""
    if view not in {SYNTHESIS_VIEW, INVESTMENT_VIEW}:
        return {"state": "NOT_APPLICABLE", "reason": "view_does_not_require_receipt"}
    if not handoff_read_receipt_required(output, view):
        return {"state": "NOT_REQUIRED", "reason": "view_has_no_contract_bound_read_receipt"}

    readiness = handoff.get("readiness") if isinstance(handoff.get("readiness"), dict) else {}
    identity = handoff.get("identity") if isinstance(handoff.get("identity"), dict) else {}
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "view": view,
        "recorded_at": _now(),
        "required_at_read": True,
        "readiness_state": str(readiness.get("state") or ""),
        "handoff_identity": {
            field: str(identity.get(field) or "") for field in IDENTITY_FIELDS
        },
        "run_identity": _run_identity(output),
        "source_versions": _source_versions(output),
        "canonical_source_versions": _canonical_source_versions(output, handoff),
    }
    path = output / _receipt_filename(view)
    path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "state": "RECORDED",
        "path": str(path),
        "view": view,
        "readiness_state": receipt["readiness_state"],
        "run_id": receipt["run_identity"]["run_id"],
    }


def validate_judgment_handoff_read_receipt(
    output_dir: str | Path, view: str = SYNTHESIS_VIEW,
) -> dict[str, Any]:
    """Rebuild a contract-bound report view and verify it matches its last read."""
    output = Path(output_dir).expanduser().resolve()
    normalized_view = str(view or "").upper()
    if not handoff_read_receipt_required(output, normalized_view):
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "state": "NOT_REQUIRED",
            "findings": [],
        }

    findings: list[str] = []
    receipt_path = output / _receipt_filename(normalized_view)
    receipt = _read_json(receipt_path)
    if not receipt:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "state": "BLOCKED",
            "findings": [normalized_view.lower() + "_read_receipt_missing"],
            "receipt_path": str(receipt_path),
        }
    if receipt.get("schema_version") != SCHEMA_VERSION:
        findings.append("judgment_synthesis_read_receipt_schema_invalid")
    if receipt.get("view") != normalized_view:
        findings.append(normalized_view.lower() + "_read_receipt_view_invalid")
    if receipt.get("readiness_state") != "READY":
        findings.append("judgment_synthesis_read_was_not_ready")

    try:
        from scripts.judgment_generation_handoff import build_judgment_generation_handoff
    except ModuleNotFoundError:
        from judgment_generation_handoff import build_judgment_generation_handoff
    current_handoff = build_judgment_generation_handoff(output, normalized_view)
    current_readiness = str((current_handoff.get("readiness") or {}).get("state") or "")
    if current_readiness != "READY":
        findings.append("current_judgment_synthesis_not_ready:" + (current_readiness or "MISSING"))

    current_identity = current_handoff.get("identity") if isinstance(current_handoff.get("identity"), dict) else {}
    recorded_identity = receipt.get("handoff_identity") if isinstance(receipt.get("handoff_identity"), dict) else {}
    for field in IDENTITY_FIELDS:
        if str(recorded_identity.get(field) or "") != str(current_identity.get(field) or ""):
            findings.append("judgment_synthesis_identity_changed:" + field)

    current_run = _run_identity(output)
    recorded_run = receipt.get("run_identity") if isinstance(receipt.get("run_identity"), dict) else {}
    policy_run_required = all(current_run.get("policy_enforced", {}).values())
    if policy_run_required:
        if not current_run.get("consistent"):
            findings.append("current_unified_policy_run_identity_inconsistent")
        if recorded_run != current_run:
            findings.append("judgment_synthesis_run_changed_after_read")

    current_versions = _source_versions(output)
    recorded_versions = receipt.get("source_versions")
    if not isinstance(recorded_versions, dict):
        findings.append("judgment_synthesis_source_versions_missing")
    else:
        for name in SYNTHESIS_SOURCES:
            if recorded_versions.get(name) != current_versions.get(name):
                findings.append("judgment_synthesis_source_changed_after_read:" + name)

    current_canonical_versions = _canonical_source_versions(output, current_handoff)
    recorded_canonical_versions = receipt.get("canonical_source_versions")
    if not isinstance(recorded_canonical_versions, dict):
        findings.append(normalized_view.lower() + "_canonical_source_versions_missing")
    elif recorded_canonical_versions != current_canonical_versions:
        findings.append(normalized_view.lower() + "_canonical_sources_changed_after_read")

    findings = list(dict.fromkeys(findings))
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "BLOCKED" if findings else "READY",
        "findings": findings,
        "receipt_path": str(receipt_path),
        "view": normalized_view,
        "run_id": current_run.get("run_id") or "",
    }
