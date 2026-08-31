#!/usr/bin/env python3
"""Bind role-bound industry observations to frozen Turtle source packages.

This is intentionally a composition layer.  It does not download data,
re-interpret industry observations, or make a company, cash, valuation or
investment conclusion.  Government context uses the existing
``industry_context_acquisition`` package; official issuer / counterparty
disclosures use the existing Phase 10 package.  The sole new job is proving
that an accepted receipt observation points at one of those materialized,
pre-cutoff source records.
"""

from __future__ import annotations

from copy import deepcopy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.industry_context_acquisition import validate_official_context_source_package
    from scripts.industry_experience_acquisition import (
        validate_industry_evidence_acquisition_plan,
        validate_industry_evidence_acquisition_receipt,
    )
    from scripts.phase10_acquisition import MANIFEST_SCHEMA_VERSION, _package_relative_path, _resolve_package_path
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from industry_context_acquisition import validate_official_context_source_package  # type: ignore[no-redef]
    from industry_experience_acquisition import (  # type: ignore[no-redef]
        validate_industry_evidence_acquisition_plan,
        validate_industry_evidence_acquisition_receipt,
    )
    from phase10_acquisition import MANIFEST_SCHEMA_VERSION, _package_relative_path, _resolve_package_path  # type: ignore[no-redef]


BINDING_SCHEMA_VERSION = "industry-evidence-source-binding.v1"
DEFAULT_BINDING_OUTPUT_NAME = "industry_evidence_source_binding.json"
_PACKAGE_KINDS = {"OFFICIAL_CONTEXT_SOURCE_PACKAGE", "PHASE10_SOURCE_PACKAGE"}
_CONTEXT_SOURCE_ROLES = {"OFFICIAL_STATISTICS", "REGULATORY_DISCLOSURE"}
_PHASE10_EXTERNAL_ROLES = {
    "COMPETITOR_DISCLOSURE", "SUPPLIER_OR_CUSTOMER_DISCLOSURE", "REGULATORY_DISCLOSURE",
}
_BINDING_FIELDS = {
    "observation_id", "task_id", "source_ref", "package_id", "package_source_id",
}
_PACKAGE_DESCRIPTOR_FIELDS = {"package_id", "kind", "package_ref", "package_root_ref"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _instant(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    if len(text) == 10:
        try:
            return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _same_publication_time(package_value: Any, observation_value: Any) -> bool:
    """Match exactly when both carry timestamps; date-only packages match date."""
    package_text, observation_text = _text(package_value), _text(observation_value)
    if len(package_text) == 10:
        return package_text == observation_text[:10]
    package_time, observation_time = _instant(package_text), _instant(observation_text)
    return package_time is not None and package_time == observation_time


def _safe_ref(root: Path, value: Any, *, file_required: bool) -> Path | None:
    text = _text(value).replace("\\", "/")
    if not text or text.startswith("/") or ".." in Path(text).parts:
        return None
    candidate = (root / text).resolve()
    if candidate != root and root not in candidate.parents:
        return None
    if file_required and not candidate.is_file():
        return None
    if not file_required and not candidate.is_dir():
        return None
    return candidate


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _context_package_sources(package: dict[str, Any], package_root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    result = validate_official_context_source_package(package)
    findings = ["context_package:" + item for item in result["invalid_findings"]]
    if result["state"] != "REVIEWABLE":
        findings.extend("context_package:" + item for item in result["incomplete_findings"])
        return {}, findings
    sources: dict[str, dict[str, Any]] = {}
    for source in _items(package.get("sources")):
        source_value = _mapping(source)
        source_id = _text(source_value.get("source_id"))
        raw_path = _package_relative_path(source_value.get("package_path"))
        if not source_id or raw_path is None:
            findings.append("context_package:source_identity_or_path_invalid:" + source_id)
            continue
        try:
            present = _resolve_package_path(package_root, raw_path, field="source.package_path").is_file()
        except ValueError:
            present = False
        if not present:
            findings.append("context_package:raw_source_missing:" + source_id)
            continue
        sources[source_id] = source_value
    return sources, findings


def _phase10_package_sources(package: dict[str, Any], package_root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    findings: list[str] = []
    if package.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return {}, ["phase10_package:schema_version_invalid"]
    source_package = _mapping(package.get("source_package"))
    if source_package.get("status") != "COMPLETE":
        return {}, ["phase10_package:not_complete"]
    sources: dict[str, dict[str, Any]] = {}
    for source in _items(package.get("sources")):
        source_value = _mapping(source)
        source_id = _text(source_value.get("source_id"))
        status = _text(source_value.get("package_acquisition_status"))
        raw_path = _package_relative_path(source_value.get("package_path"))
        if not source_id or status not in {"ADMITTED_PACKAGE", "LICENSED_EXPORT_PRESENT"} or raw_path is None:
            findings.append("phase10_package:source_not_materialized:" + source_id)
            continue
        try:
            raw_present = _resolve_package_path(package_root, raw_path, field="source.package_path").is_file()
            reader_path = _package_relative_path(source_value.get("reader_text_path"))
            reader_present = reader_path is None or _resolve_package_path(
                package_root, reader_path, field="source.reader_text_path",
            ).is_file()
        except ValueError:
            raw_present, reader_present = False, False
        if not raw_present or not reader_present:
            findings.append("phase10_package:raw_or_reader_missing:" + source_id)
            continue
        sources[source_id] = source_value
    return sources, findings


def _package_sources(descriptor: dict[str, Any], root: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    package_path = _safe_ref(root, descriptor.get("package_ref"), file_required=True)
    package_root = _safe_ref(root, descriptor.get("package_root_ref"), file_required=False)
    package_id = _text(descriptor.get("package_id"))
    if package_path is None or package_root is None:
        return {}, ["package_reference_missing_or_outside_root:" + package_id]
    package = _read_json(package_path)
    if package is None:
        return {}, ["package_json_invalid:" + package_id]
    if descriptor.get("kind") == "OFFICIAL_CONTEXT_SOURCE_PACKAGE":
        return _context_package_sources(package, package_root)
    if descriptor.get("kind") == "PHASE10_SOURCE_PACKAGE":
        return _phase10_package_sources(package, package_root)
    return {}, ["package_kind_invalid:" + package_id]


def _receipt_observations(receipt: Mapping[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for task_receipt in _items(receipt.get("task_receipts")):
        task_value = _mapping(task_receipt)
        task_id = _text(task_value.get("task_id"))
        for observation in _items(task_value.get("observations")):
            observation_value = _mapping(observation)
            observation_id = _text(observation_value.get("observation_id"))
            if observation_id:
                result[observation_id] = (task_id, observation_value)
    return result


def _source_url(source: Mapping[str, Any]) -> str:
    return _text(source.get("source_url")) or _text(source.get("url"))


def validate_industry_evidence_source_binding(
    binding: Any,
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    artifact_root: str | Path,
) -> dict[str, Any]:
    """Require every accepted receipt observation to resolve to local source text."""
    findings: list[str] = []
    value = _mapping(binding)
    if value.get("schema_version") != BINDING_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    required = {
        "schema_version", "binding_id", "plan_id", "plan_ref", "receipt_ref", "company_identity",
        "binding_status", "source_packages", "observation_source_bindings", "use_policy",
    }
    if set(value) != required:
        findings.append("fields_invalid")
    if validate_industry_evidence_acquisition_plan(plan).get("state") != "REVIEWABLE":
        findings.append("plan_not_reviewable")
    if validate_industry_evidence_acquisition_receipt(receipt, plan).get("state") != "REVIEWABLE":
        findings.append("receipt_not_reviewable")
    if _text(value.get("plan_id")) != _text(plan.get("plan_id")):
        findings.append("plan_id_mismatch")
    if value.get("company_identity") != plan.get("company_identity"):
        findings.append("company_identity_mismatch")
    if value.get("binding_status") != "READY":
        findings.append("binding_status_invalid")
    policy = _mapping(value.get("use_policy"))
    if policy.get("company_transmission_still_required") is not True:
        findings.append("company_transmission_requirement_missing")
    if policy.get("cannot_establish") != [
        "COMPANY_FACT_WITHOUT_TARGET_COMPANY_EVIDENCE", "OWNER_CASH_VALUE",
        "VALUATION_PARAMETER", "INVESTMENT_ACTION",
    ]:
        findings.append("use_policy_boundary_invalid")

    root = Path(artifact_root).expanduser().resolve()
    descriptors = _items(value.get("source_packages"))
    package_sources: dict[str, dict[str, dict[str, Any]]] = {}
    package_kinds: dict[str, str] = {}
    for index, raw_descriptor in enumerate(descriptors):
        descriptor = _mapping(raw_descriptor)
        path = f"source_packages[{index}]"
        if set(descriptor) != _PACKAGE_DESCRIPTOR_FIELDS:
            findings.append(path + ".fields_invalid")
            continue
        package_id = _text(descriptor.get("package_id"))
        if not package_id or package_id in package_sources:
            findings.append(path + ".package_id_missing_or_duplicate")
            continue
        if descriptor.get("kind") not in _PACKAGE_KINDS:
            findings.append(path + ".kind_invalid")
            continue
        sources, package_findings = _package_sources(descriptor, root)
        if package_findings:
            findings.extend(path + "." + item for item in package_findings)
            continue
        package_sources[package_id] = sources
        package_kinds[package_id] = _text(descriptor.get("kind"))

    expected_observations = _receipt_observations(receipt)
    bindings = _items(value.get("observation_source_bindings"))
    bound_ids: set[str] = set()
    for index, raw_binding in enumerate(bindings):
        item = _mapping(raw_binding)
        path = f"observation_source_bindings[{index}]"
        if set(item) != _BINDING_FIELDS:
            findings.append(path + ".fields_invalid")
            continue
        observation_id = _text(item.get("observation_id"))
        if not observation_id or observation_id in bound_ids:
            findings.append(path + ".observation_id_missing_or_duplicate")
            continue
        bound_ids.add(observation_id)
        expected = expected_observations.get(observation_id)
        if expected is None:
            findings.append(path + ".observation_not_in_receipt")
            continue
        task_id, observation = expected
        if _text(item.get("task_id")) != task_id:
            findings.append(path + ".task_id_mismatch")
        if _text(item.get("source_ref")) != _text(observation.get("source_ref")):
            findings.append(path + ".source_ref_mismatch")
        package_id = _text(item.get("package_id"))
        source = package_sources.get(package_id, {}).get(_text(item.get("package_source_id")))
        if source is None:
            findings.append(path + ".package_source_not_materialized")
            continue
        if _source_url(source) != _text(observation.get("source_url")):
            findings.append(path + ".source_url_mismatch")
        if not _same_publication_time(source.get("published_at"), observation.get("published_at")):
            findings.append(path + ".published_at_mismatch")
        source_role = _text(observation.get("source_role"))
        package_kind = package_kinds.get(package_id)
        if package_kind == "OFFICIAL_CONTEXT_SOURCE_PACKAGE" and source_role not in _CONTEXT_SOURCE_ROLES:
            findings.append(path + ".official_context_role_not_permitted")
        if package_kind == "PHASE10_SOURCE_PACKAGE":
            provenance = _mapping(source.get("source_role_provenance"))
            declared_role = _text(provenance.get("relative_role"))
            if declared_role and declared_role != source_role:
                findings.append(path + ".phase10_source_role_provenance_mismatch")
            elif source_role in _PHASE10_EXTERNAL_ROLES and declared_role != source_role:
                findings.append(path + ".phase10_source_role_provenance_mismatch")

    if set(expected_observations) != bound_ids:
        findings.append("receipt_observation_coverage_mismatch")
    return {
        "schema_version": "industry-evidence-source-binding-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def build_industry_evidence_source_binding(
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    plan_ref: str,
    receipt_ref: str,
    source_packages: Iterable[Mapping[str, Any]],
    observation_source_bindings: Iterable[Mapping[str, Any]],
    artifact_root: str | Path,
) -> dict[str, Any]:
    """Create a report-local, path-bound composition from existing packages."""
    payload = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "binding_id": "IESB:" + _text(plan.get("plan_id")),
        "plan_id": _text(plan.get("plan_id")),
        "plan_ref": _text(plan_ref),
        "receipt_ref": _text(receipt_ref),
        "company_identity": deepcopy(_mapping(plan.get("company_identity"))),
        "binding_status": "READY",
        "source_packages": [deepcopy(dict(item)) for item in source_packages],
        "observation_source_bindings": [deepcopy(dict(item)) for item in observation_source_bindings],
        "use_policy": {
            "company_transmission_still_required": True,
            "cannot_establish": [
                "COMPANY_FACT_WITHOUT_TARGET_COMPANY_EVIDENCE", "OWNER_CASH_VALUE",
                "VALUATION_PARAMETER", "INVESTMENT_ACTION",
            ],
        },
    }
    result = validate_industry_evidence_source_binding(
        payload, plan, receipt, artifact_root=artifact_root,
    )
    if result["state"] != "REVIEWABLE":
        raise ValueError("industry_evidence_source_binding_invalid:" + ",".join(result["findings"]))
    return payload
