#!/usr/bin/env python3
"""Admit a source-bound industry observation to a report only with company proof.

The industry observation is still external context.  This small gate only
allows it to appear in a report when the same Episode contains a separately
traceable target-company primary source that confirms or contradicts the
specified transmission.  It does not add a company claim, a valuation input,
or an investment action.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

try:
    from scripts.enterprise_underwriting_episode import validate_enterprise_underwriting_episode
    from scripts.industry_evidence_source_binding import validate_industry_evidence_source_binding
    from scripts.industry_experience_acquisition import (
        validate_industry_evidence_acquisition_plan,
        validate_industry_evidence_acquisition_receipt,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from enterprise_underwriting_episode import validate_enterprise_underwriting_episode  # type: ignore[no-redef]
    from industry_evidence_source_binding import validate_industry_evidence_source_binding  # type: ignore[no-redef]
    from industry_experience_acquisition import (  # type: ignore[no-redef]
        validate_industry_evidence_acquisition_plan,
        validate_industry_evidence_acquisition_receipt,
    )


ADMISSION_SCHEMA_VERSION = "industry-evidence-report-admission.v1"
DEFAULT_ADMISSION_OUTPUT_NAME = "industry_evidence_report_admission.json"
_FIELDS = {
    "schema_version", "admission_id", "binding_ref", "episode_ref", "company_identity",
    "admission_status", "paired_observations", "use_policy",
}
_PAIR_FIELDS = {
    "observation_id", "task_id", "transmission_requirement_id",
    "industry_evidence_id", "target_company_evidence_id",
    "target_company_source_ref", "transmission_status",
}
_TARGET_SOURCE_KINDS = {
    "ISSUER_PRE_CUTOFF_SOURCE_PACKAGE", "TARGET_COMPANY_PRIMARY_SOURCE_PACKAGE",
}
# ``IEA:`` is the canonical identity issued by this module, not a prose
# convention.  Scan every occurrence in the technical surface: restricting
# the parser to an optional display marker made it possible to rely on an
# outside observation while escaping the admission gate merely by omitting
# brackets.
_REPORT_INDUSTRY_EVIDENCE_ID_RE = re.compile(
    r"\b(IEA:[A-Za-z0-9_.:@/-]+)\b",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _receipt_observations(receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    observations: dict[str, dict[str, Any]] = {}
    for task in _items(receipt.get("task_receipts")):
        for raw in _items(_mapping(task).get("observations")):
            observation = _mapping(raw)
            observation_id = _text(observation.get("observation_id"))
            if observation_id:
                observations[observation_id] = observation
    return observations


def _trace_by_id(episode: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(item.get("evidence_id")): item
        for raw in _items(episode.get("evidence_trace"))
        if (item := _mapping(raw)) and _text(item.get("evidence_id"))
    }


def _plan_tasks(plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Index the only company-transmission requirements an admission may close.

    The acquisition plan already gives every question a stable task id.  Keep
    the requirement identifier a deterministic derivation of that id instead
    of copying the question into another evidence store.
    """
    return {
        _text(item.get("task_id")): item
        for raw in _items(plan.get("tasks"))
        if (item := _mapping(raw)) and _text(item.get("task_id"))
    }


def transmission_requirement_id(task_id: Any) -> str:
    """Return the stable requirement identity for one role-bound plan task."""
    return "IETR:" + _text(task_id)


def _target_primary_source_refs(episode: Mapping[str, Any]) -> set[str]:
    return {
        _text(item.get("ref"))
        for raw in _items(episode.get("existing_object_refs"))
        if (item := _mapping(raw)) and item.get("kind") in _TARGET_SOURCE_KINDS and _text(item.get("ref"))
    }


def validate_industry_evidence_report_admission(
    admission: Any,
    binding: Mapping[str, Any],
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    episode: Mapping[str, Any],
    *,
    artifact_root: str | Path,
) -> dict[str, Any]:
    """Validate the full external-observation → company-primary-Episode closure."""
    findings: list[str] = []
    value = _mapping(admission)
    if value.get("schema_version") != ADMISSION_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if set(value) != _FIELDS:
        findings.append("fields_invalid")
    if validate_industry_evidence_acquisition_plan(plan).get("state") != "REVIEWABLE":
        findings.append("plan_not_reviewable")
    if validate_industry_evidence_acquisition_receipt(receipt, plan).get("state") != "REVIEWABLE":
        findings.append("receipt_not_reviewable")
    if validate_industry_evidence_source_binding(
        binding, plan, receipt, artifact_root=artifact_root,
    ).get("state") != "REVIEWABLE":
        findings.append("source_binding_not_reviewable")
    if validate_enterprise_underwriting_episode(episode).get("state") != "REVIEWABLE":
        findings.append("episode_not_reviewable")
    if value.get("company_identity") != plan.get("company_identity"):
        findings.append("company_identity_mismatch")
    if value.get("admission_status") != "READY":
        findings.append("admission_status_invalid")
    policy = _mapping(value.get("use_policy"))
    if policy.get("company_primary_transmission_required") is not True:
        findings.append("company_primary_transmission_requirement_missing")
    if policy.get("cannot_establish") != [
        "OWNER_CASH_VALUE", "VALUATION_PARAMETER", "INVESTMENT_ACTION",
    ]:
        findings.append("use_policy_boundary_invalid")

    observations = _receipt_observations(receipt)
    tasks = _plan_tasks(plan)
    trace_by_id = _trace_by_id(episode)
    target_sources = _target_primary_source_refs(episode)
    pairs = _items(value.get("paired_observations"))
    paired_ids: set[str] = set()
    for index, raw in enumerate(pairs):
        pair = _mapping(raw)
        path = f"paired_observations[{index}]"
        if set(pair) != _PAIR_FIELDS:
            findings.append(path + ".fields_invalid")
            continue
        observation_id = _text(pair.get("observation_id"))
        if not observation_id or observation_id in paired_ids:
            findings.append(path + ".observation_id_missing_or_duplicate")
            continue
        paired_ids.add(observation_id)
        if observation_id not in observations:
            findings.append(path + ".observation_not_in_receipt")
        task_id = _text(pair.get("task_id"))
        task = tasks.get(task_id)
        if task is None:
            findings.append(path + ".task_not_in_plan")
        expected_task_id = ""
        for candidate_task_id, receipt_task in (
            (_text(raw.get("task_id")), _mapping(raw))
            for raw in _items(receipt.get("task_receipts"))
        ):
            if observation_id in {
                _text(item.get("observation_id"))
                for item in _items(receipt_task.get("observations"))
            }:
                expected_task_id = candidate_task_id
                break
        if expected_task_id and task_id != expected_task_id:
            findings.append(path + ".task_does_not_own_observation")
        if _text(pair.get("transmission_requirement_id")) != transmission_requirement_id(task_id):
            findings.append(path + ".transmission_requirement_id_mismatch")
        expected_industry_evidence_id = "IEA:" + observation_id
        if _text(pair.get("industry_evidence_id")) != expected_industry_evidence_id:
            findings.append(path + ".industry_evidence_id_mismatch")
        if expected_industry_evidence_id not in trace_by_id:
            findings.append(path + ".industry_evidence_not_in_episode")
        company_evidence_id = _text(pair.get("target_company_evidence_id"))
        company_trace = trace_by_id.get(company_evidence_id)
        if not company_evidence_id or company_evidence_id == expected_industry_evidence_id or company_trace is None:
            findings.append(path + ".target_company_evidence_not_in_episode")
            continue
        source_ref = _text(pair.get("target_company_source_ref"))
        if source_ref != _text(company_trace.get("source_ref")):
            findings.append(path + ".target_company_source_ref_mismatch")
        if source_ref not in target_sources:
            findings.append(path + ".target_company_primary_source_not_declared")
        if task is not None and task_id not in _text(company_trace.get("used_for")):
            findings.append(path + ".target_company_trace_not_bound_to_task")
        if pair.get("transmission_status") not in {"SUPPORTED", "CONTRADICTED"}:
            findings.append(path + ".transmission_status_invalid")
    if set(observations) != paired_ids:
        findings.append("receipt_observation_pair_coverage_mismatch")
    return {
        "schema_version": "industry-evidence-report-admission-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def build_industry_evidence_report_admission(
    binding: Mapping[str, Any],
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    episode: Mapping[str, Any],
    *,
    binding_ref: str,
    episode_ref: str,
    paired_observations: Iterable[Mapping[str, Any]],
    artifact_root: str | Path,
) -> dict[str, Any]:
    """Create the report gate without copying evidence text into a new store."""
    payload = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "admission_id": "IERA:" + _text(binding.get("binding_id")),
        "binding_ref": _text(binding_ref),
        "episode_ref": _text(episode_ref),
        "company_identity": deepcopy(_mapping(plan.get("company_identity"))),
        "admission_status": "READY",
        "paired_observations": [deepcopy(dict(item)) for item in paired_observations],
        "use_policy": {
            "company_primary_transmission_required": True,
            "cannot_establish": [
                "OWNER_CASH_VALUE", "VALUATION_PARAMETER", "INVESTMENT_ACTION",
            ],
        },
    }
    result = validate_industry_evidence_report_admission(
        payload, binding, plan, receipt, episode, artifact_root=artifact_root,
    )
    if result["state"] != "REVIEWABLE":
        raise ValueError("industry_evidence_report_admission_invalid:" + ",".join(result["findings"]))
    return payload


def project_report_admitted_industry_observations(
    admission: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return only identifiers and transmission state for report consumers."""
    observations = _receipt_observations(receipt)
    return [{
        "observation_id": _text(pair.get("observation_id")),
        "task_id": _text(pair.get("task_id")),
        "transmission_requirement_id": _text(pair.get("transmission_requirement_id")),
        "industry_evidence_id": _text(pair.get("industry_evidence_id")),
        "target_company_evidence_id": _text(pair.get("target_company_evidence_id")),
        "transmission_status": _text(pair.get("transmission_status")),
        "source_role": _text(observations.get(_text(pair.get("observation_id")), {}).get("source_role")),
        "metric": _text(observations.get(_text(pair.get("observation_id")), {}).get("metric")),
        "evidence_use": _text(observations.get(_text(pair.get("observation_id")), {}).get("evidence_use")),
    } for pair in _items(admission.get("paired_observations"))]


def report_industry_evidence_ids(technical_text: Any) -> list[str]:
    """Return canonical external-industry identities named in technical prose."""
    return list(dict.fromkeys(
        match.group(1).upper()
        for match in _REPORT_INDUSTRY_EVIDENCE_ID_RE.finditer(str(technical_text or ""))
    ))


def report_industry_evidence_marker_ids(technical_text: Any) -> list[str]:
    """Backward-compatible name for the full technical identity scan.

    ``[industry-evidence: ...]`` remains a readable optional rendering, but
    it is no longer the authority boundary.  The authoritative declaration is
    a raw-fact row in the existing major-claim evidence ledger.
    """
    return report_industry_evidence_ids(technical_text)


def _structured_industry_evidence_uses(claim_ledger: Any) -> list[dict[str, str]]:
    """Extract report-use declarations from the canonical claim ledger only."""
    ledger = _mapping(claim_ledger)
    uses: list[dict[str, str]] = []
    for claim_index, raw_claim in enumerate(_items(ledger.get("claims"))):
        claim = _mapping(raw_claim)
        claim_id = _text(claim.get("claim_id")) or f"claims[{claim_index}]"
        for fact_index, raw_fact in enumerate(_items(claim.get("raw_facts"))):
            fact = _mapping(raw_fact)
            evidence_id = _text(fact.get("industry_evidence_id")).upper()
            if not evidence_id:
                continue
            uses.append({
                "claim_id": claim_id,
                "raw_fact_index": str(fact_index),
                "industry_evidence_id": evidence_id,
                "task_id": _text(fact.get("industry_task_id")),
                "transmission_requirement_id": _text(
                    fact.get("transmission_requirement_id")
                ),
            })
    return uses


def validate_report_industry_evidence_uses(
    admission: Mapping[str, Any], *, technical_text: Any, claim_ledger: Any,
) -> dict[str, Any]:
    """Close every technical IEA reference through an admitted claim record.

    A writer may choose any readable wording, including no display marker at
    all.  What it cannot choose is whether to make the usage auditable: every
    named IEA identity must be declared on a raw fact in ``claim_evidence``
    and that declaration must preserve the exact acquisition task and
    transmission requirement which admission closed.
    """
    allowed = {
        _text(item.get("industry_evidence_id")).upper(): item
        for raw in _items(admission.get("paired_observations"))
        if (item := _mapping(raw)) and _text(item.get("industry_evidence_id"))
    }
    uses = report_industry_evidence_ids(technical_text)
    declarations = _structured_industry_evidence_uses(claim_ledger)
    declared_ids = {item["industry_evidence_id"] for item in declarations}
    findings: list[str] = []
    for evidence_id in uses:
        if evidence_id not in declared_ids:
            findings.append("external_industry_evidence_use_record_missing:" + evidence_id)
    for evidence_id in sorted(declared_ids - set(uses)):
        findings.append("external_industry_evidence_use_record_not_used:" + evidence_id)
    for declaration in declarations:
        evidence_id = declaration["industry_evidence_id"]
        pair = allowed.get(evidence_id)
        prefix = (
            "industry_evidence_use_record:"
            + declaration["claim_id"] + ":" + declaration["raw_fact_index"]
        )
        if pair is None:
            findings.append("unadmitted_external_industry_evidence:" + evidence_id)
            continue
        if declaration["task_id"] != _text(pair.get("task_id")):
            findings.append(prefix + ":task_id_mismatch")
        if declaration["transmission_requirement_id"] != _text(
            pair.get("transmission_requirement_id")
        ):
            findings.append(prefix + ":transmission_requirement_id_mismatch")
    return {
        "schema_version": "industry-evidence-report-use-validation.v1",
        "state": "PASS" if not findings else "BLOCKED",
        "technical_evidence_ids": uses,
        "declared_industry_evidence_ids": sorted(declared_ids),
        "blocking_findings": findings,
    }
