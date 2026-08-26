#!/usr/bin/env python3
"""Closed, outcome-free A1 receipts for action-first Comparative discovery.

This is deliberately a small control surface between candidate discovery and
the existing H1/H2/V5 machinery.  It proves only that a curator has supplied
one materially implemented operating action using cutoff-before, page-level
official static PDFs.  Its sole output is an action-blind comparator
recruitment brief; it cannot select peers, create an H2 package, access
outcomes, or grant any learning, CJO, report, valuation, or investment right.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any, Iterable


SCHEMA_VERSION = "judgment-selection-action-first-candidate-receipt.v1"
BRIEF_SCHEMA_VERSION = "judgment-selection-comparator-recruitment-brief.v1"

COMPARATOR_RECRUITMENT_BRIEF = "COMPARATOR_RECRUITMENT_BRIEF"
NO_METHOD_TRANSFER_RIGHTS = "NO_METHOD_TRANSFER_RIGHTS"
IMPLEMENTED_MATERIAL = "IMPLEMENTED_MATERIAL"
OFFICIAL_STATIC_FINALPAGE_PDF = "OFFICIAL_STATIC_FINALPAGE_PDF"
TIMESTAMP = "TIMESTAMP"

SUPPORTED_TOPOLOGIES = {"CUSTOMER_RESPONSE", "COST_RESTRUCTURING"}
SOURCE_SUPPORTS = {"IMPLEMENTATION", "MATERIALITY", "HYPOTHESIS", "RIVAL"}

_RECEIPT_KEYS = {
    "schema_version",
    "receipt_id",
    "receipt_version",
    "candidate_id",
    "company_id",
    "issuer_id",
    "responsibility_unit_id",
    "perimeter_id",
    "cutoff_at",
    "arena_family",
    "mechanism_topology",
    "action",
    "hypotheses",
    "static_sources",
    "allowed_outputs",
    "method_transfer_rights",
}
_ACTION_KEYS = {
    "action_id",
    "implemented_at",
    "implementation_status",
    "implemented_material_action",
    "responsibility_unit_id",
    "perimeter_id",
    "source_ids",
}
_HYPOTHESES_KEYS = {"h_a", "h_b", "strongest_rival"}
_HYPOTHESIS_KEYS = {"hypothesis_id", "mechanism", "source_ids"}
_RIVAL_KEYS = {"hypothesis_id", "explanation", "source_ids"}
_SOURCE_KEYS = {
    "source_id",
    "official_artifact_id",
    "source_url",
    "source_type",
    "availability_precision",
    "published_at",
    "issuer_id",
    "responsibility_unit_id",
    "perimeter_id",
    "page",
    "supports",
}
_FORBIDDEN_FIELD_NAMES = {
    "h2",
    "h2_receipt",
    "peer",
    "peers",
    "peer_panel",
    "panel",
    "final_panel",
    "comparator_panel",
    "outcome",
    "outcomes",
    "outcome_value",
    "outcome_source",
    "result",
    "results",
    "settlement",
    "price",
    "price_snapshot",
    "return",
    "returns",
    "valuation",
    "expectation_gap",
    "buy_band",
    "cjo",
    "report",
    "learning",
    "learning_note",
    "investment",
    "investment_permission",
    "method",
    "method_release",
    "forecast",
    "r103",
}
_STATIC_FINALPAGE_URL = re.compile(
    r"^https://static\.cninfo\.com\.cn/finalpage/(\d{4}-\d{2}-\d{2})/[^/?#\s]+\.PDF$"
)


class ActionFirstCandidateError(ValueError):
    """Raised when a caller asks the brief builder to consume an invalid receipt."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
        return {}
    item = value
    for field in sorted(set(item).difference(allowed)):
        findings.append(f"{path}_contains_unapproved_field:{field}")
    for field in sorted(allowed.difference(item)):
        findings.append(f"{path}_missing_required_field:{field}")
    return item


def _require_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        findings.append(f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _positive_integer(value: Any, path: str, findings: list[str]) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        findings.append(f"{path}_must_be_positive_integer")
        return None
    return value


def _require_instant(item: dict[str, Any], field: str, path: str, findings: list[str]) -> datetime | None:
    parsed = _instant(item.get(field))
    if parsed is None:
        findings.append(f"{path}.{field}_must_be_timezone_aware_iso8601")
    return parsed


def _source_references(
    value: Any,
    *,
    path: str,
    available_source_ids: set[str],
    findings: list[str],
) -> list[str]:
    references = _items(value)
    if not references:
        findings.append(f"{path}_must_reference_static_source")
        return []
    if any(not _text(source_id) for source_id in references):
        findings.append(f"{path}_source_identity_invalid")
        return []
    normalized = [str(source_id).strip() for source_id in references]
    if len(normalized) != len(set(normalized)):
        findings.append(f"{path}_source_identity_duplicate")
    missing = sorted(set(normalized).difference(available_source_ids))
    if missing:
        findings.append(f"{path}_references_unknown_static_source")
    return normalized


def _walk_field_names(value: Any, path: str = "receipt") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, nested in value.items():
            child = f"{path}.{key}"
            yield child, str(key)
            yield from _walk_field_names(nested, child)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_field_names(nested, f"{path}[{index}]")


def _reject_forbidden_fields(receipt: Any, findings: list[str]) -> None:
    for path, field in _walk_field_names(receipt):
        if field.lower() in _FORBIDDEN_FIELD_NAMES:
            findings.append(f"receipt_contains_forbidden_field:{field}")


def _validate_source(
    raw: Any,
    *,
    index: int,
    issuer_id: str,
    responsibility_unit_id: str,
    perimeter_id: str,
    cutoff: datetime | None,
    findings: list[str],
) -> tuple[str, set[str]]:
    path = f"static_sources[{index}]"
    source = _closed(raw, _SOURCE_KEYS, path, findings)
    source_id = _require_text(source, "source_id", path, findings)
    _require_text(source, "official_artifact_id", path, findings)
    source_url = _require_text(source, "source_url", path, findings)
    for field in ("issuer_id", "responsibility_unit_id", "perimeter_id"):
        _require_text(source, field, path, findings)
    _positive_integer(source.get("page"), f"{path}.page", findings)

    if source.get("source_type") != OFFICIAL_STATIC_FINALPAGE_PDF:
        findings.append(f"{path}.source_type_must_be_official_static_finalpage_pdf")
    if source.get("availability_precision") != TIMESTAMP:
        findings.append(f"{path}.availability_precision_must_be_timestamp")
    source_time = _require_instant(source, "published_at", path, findings)
    url_match = _STATIC_FINALPAGE_URL.fullmatch(source_url) if source_url else None
    if url_match is None:
        findings.append(f"{path}.source_url_must_be_static_cninfo_finalpage_pdf")
    elif source_time is not None and source_time.date().isoformat() != url_match.group(1):
        findings.append(f"{path}.source_url_date_must_match_published_at")
    if cutoff is not None and source_time is not None and source_time >= cutoff:
        findings.append(f"{path}.published_at_must_strictly_precede_cutoff")

    if source.get("issuer_id") != issuer_id:
        findings.append(f"{path}.issuer_id_must_match_receipt")
    if source.get("responsibility_unit_id") != responsibility_unit_id:
        findings.append(f"{path}.responsibility_unit_id_must_match_receipt")
    if source.get("perimeter_id") != perimeter_id:
        findings.append(f"{path}.perimeter_id_must_match_receipt")

    supports_raw = _items(source.get("supports"))
    if not supports_raw or any(not _text(value) for value in supports_raw):
        findings.append(f"{path}.supports_must_be_nonempty_known_values")
        return source_id, set()
    supports = {str(value).strip() for value in supports_raw}
    if len(supports) != len(supports_raw) or not supports.issubset(SOURCE_SUPPORTS):
        findings.append(f"{path}.supports_must_be_nonempty_known_values")
    return source_id, supports


def _validate_hypothesis(
    raw: Any,
    *,
    path: str,
    available_source_ids: set[str],
    source_supports: dict[str, set[str]],
    findings: list[str],
) -> str:
    hypothesis = _closed(raw, _HYPOTHESIS_KEYS, path, findings)
    hypothesis_id = _require_text(hypothesis, "hypothesis_id", path, findings)
    _require_text(hypothesis, "mechanism", path, findings)
    source_ids = _source_references(
        hypothesis.get("source_ids"), path=f"{path}.source_ids", available_source_ids=available_source_ids, findings=findings,
    )
    resolved_supports = set().union(*(source_supports.get(source_id, set()) for source_id in source_ids))
    if "HYPOTHESIS" not in resolved_supports:
        findings.append(f"{path}.source_ids_must_include_hypothesis_evidence")
    return hypothesis_id


def _validate_rival(
    raw: Any,
    *,
    expected_hypothesis_id: str,
    available_source_ids: set[str],
    source_supports: dict[str, set[str]],
    findings: list[str],
) -> None:
    path = "hypotheses.strongest_rival"
    rival = _closed(raw, _RIVAL_KEYS, path, findings)
    rival_id = _require_text(rival, "hypothesis_id", path, findings)
    _require_text(rival, "explanation", path, findings)
    source_ids = _source_references(
        rival.get("source_ids"), path=f"{path}.source_ids", available_source_ids=available_source_ids, findings=findings,
    )
    resolved_supports = set().union(*(source_supports.get(source_id, set()) for source_id in source_ids))
    if "RIVAL" not in resolved_supports:
        findings.append(f"{path}.source_ids_must_include_rival_evidence")
    if rival_id and expected_hypothesis_id and rival_id != expected_hypothesis_id:
        findings.append("hypotheses.strongest_rival_must_bind_h_b")


def validate_action_first_candidate_receipt(value: Any) -> dict[str, Any]:
    """Validate one closed, implemented-action A1 receipt without side effects."""
    findings: list[str] = []
    receipt = _closed(value, _RECEIPT_KEYS, "receipt", findings)
    _reject_forbidden_fields(value, findings)

    if receipt.get("schema_version") != SCHEMA_VERSION:
        findings.append("receipt.schema_version_invalid")
    for field in (
        "receipt_id", "candidate_id", "company_id", "issuer_id", "responsibility_unit_id", "perimeter_id", "arena_family",
    ):
        _require_text(receipt, field, "receipt", findings)
    _positive_integer(receipt.get("receipt_version"), "receipt.receipt_version", findings)
    cutoff = _require_instant(receipt, "cutoff_at", "receipt", findings)
    if receipt.get("mechanism_topology") not in SUPPORTED_TOPOLOGIES:
        findings.append("receipt.mechanism_topology_not_supported")
    if receipt.get("allowed_outputs") != [COMPARATOR_RECRUITMENT_BRIEF]:
        findings.append("receipt.allowed_outputs_must_be_comparator_recruitment_brief_only")
    if receipt.get("method_transfer_rights") != NO_METHOD_TRANSFER_RIGHTS:
        findings.append("receipt.method_transfer_rights_must_be_no_method_transfer_rights")

    issuer_id = str(receipt.get("issuer_id", "")).strip()
    responsibility_unit_id = str(receipt.get("responsibility_unit_id", "")).strip()
    perimeter_id = str(receipt.get("perimeter_id", "")).strip()
    sources = _items(receipt.get("static_sources"))
    if not sources:
        findings.append("receipt.static_sources_must_be_nonempty")
    source_ids: list[str] = []
    source_supports: dict[str, set[str]] = {}
    for index, source in enumerate(sources):
        source_id, supports = _validate_source(
            source,
            index=index,
            issuer_id=issuer_id,
            responsibility_unit_id=responsibility_unit_id,
            perimeter_id=perimeter_id,
            cutoff=cutoff,
            findings=findings,
        )
        if source_id:
            source_ids.append(source_id)
            source_supports[source_id] = supports
    if len(source_ids) != len(set(source_ids)):
        findings.append("receipt.static_source_ids_must_be_unique")
    available_source_ids = set(source_ids)

    action = _closed(receipt.get("action"), _ACTION_KEYS, "action", findings)
    _require_text(action, "action_id", "action", findings)
    implemented_at = _require_instant(action, "implemented_at", "action", findings)
    if cutoff is not None and implemented_at is not None and implemented_at >= cutoff:
        findings.append("action.implemented_at_must_strictly_precede_cutoff")
    if action.get("implementation_status") != IMPLEMENTED_MATERIAL:
        findings.append("action.implementation_status_must_be_implemented_material")
    _require_text(action, "implemented_material_action", "action", findings)
    if action.get("responsibility_unit_id") != responsibility_unit_id:
        findings.append("action.responsibility_unit_id_must_match_receipt")
    if action.get("perimeter_id") != perimeter_id:
        findings.append("action.perimeter_id_must_match_receipt")
    action_source_ids = _source_references(
        action.get("source_ids"), path="action.source_ids", available_source_ids=available_source_ids, findings=findings,
    )
    resolved_action_supports = set().union(*(source_supports.get(source_id, set()) for source_id in action_source_ids))
    if "IMPLEMENTATION" not in resolved_action_supports:
        findings.append("action.source_ids_must_include_implementation_evidence")
    if "MATERIALITY" not in resolved_action_supports:
        findings.append("action.source_ids_must_include_materiality_evidence")

    hypotheses = _closed(receipt.get("hypotheses"), _HYPOTHESES_KEYS, "hypotheses", findings)
    h_a_id = _validate_hypothesis(
        hypotheses.get("h_a"), path="hypotheses.h_a", available_source_ids=available_source_ids,
        source_supports=source_supports, findings=findings,
    )
    h_b_id = _validate_hypothesis(
        hypotheses.get("h_b"), path="hypotheses.h_b", available_source_ids=available_source_ids,
        source_supports=source_supports, findings=findings,
    )
    if h_a_id and h_b_id and h_a_id == h_b_id:
        findings.append("hypotheses.h_a_and_h_b_must_be_distinct")
    _validate_rival(
        hypotheses.get("strongest_rival"), expected_hypothesis_id=h_b_id,
        available_source_ids=available_source_ids, source_supports=source_supports, findings=findings,
    )

    return {"valid": not findings, "findings": findings, "candidate_receipt": deepcopy(receipt)}


def build_comparator_recruitment_brief(value: Any) -> dict[str, Any]:
    """Derive the only A1 output, without target/action/source/hypothesis leakage."""
    result = validate_action_first_candidate_receipt(value)
    if not result["valid"]:
        raise ActionFirstCandidateError("; ".join(result["findings"]))
    receipt = result["candidate_receipt"]
    topology = receipt["mechanism_topology"]
    d2_or_cost_condition = (
        "CUTOFF_BEFORE_CUSTOMER_RESPONSE_HISTORY_REQUIRED"
        if topology == "CUSTOMER_RESPONSE"
        else "CUTOFF_BEFORE_COST_DRIVER_HISTORY_REQUIRED"
    )
    return {
        "schema_version": BRIEF_SCHEMA_VERSION,
        "cutoff_at": receipt["cutoff_at"],
        "arena_family": receipt["arena_family"],
        "mechanism_topology": topology,
        "required_carrier_identity": {
            "issuer_id": receipt["issuer_id"],
            "responsibility_unit_id": receipt["responsibility_unit_id"],
            "perimeter_id": receipt["perimeter_id"],
        },
        "static_evidence_conditions": [
            "OFFICIAL_STATIC_FINALPAGE_PDF_ONLY",
            "TIMESTAMPED_SOURCE_STRICTLY_BEFORE_CUTOFF",
            "PAGE_LEVEL_CARRIER_IDENTITY_REQUIRED",
        ],
        "d2_or_cost_conditions": [
            d2_or_cost_condition,
            "SAME_OR_EXPLICITLY_BRIDGED_RESPONSIBILITY_UNIT_REQUIRED",
        ],
        "d3_d4_conditions": [
            "CUTOFF_BEFORE_RECURRING_D3_FIELD_HISTORY_REQUIRED",
            "CUTOFF_BEFORE_RECURRING_D4_FIELD_HISTORY_REQUIRED",
            "SAME_OR_EXPLICITLY_BRIDGED_PERIMETER_REQUIRED",
        ],
        "control_conditions": [
            "MECHANISM_COMPATIBLE_ARENA_MEMBERSHIP_REQUIRED",
            "NO_POST_CUTOFF_MATERIAL",
            "NO_OUTCOME_PRICE_RETURN_OR_VALUATION_ACCESS",
            "NO_FINAL_PEER_OR_PANEL_SELECTION",
        ],
    }
