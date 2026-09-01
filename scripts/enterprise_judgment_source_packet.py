#!/usr/bin/env python3
"""Receipt and conservative PIT adapter for one J1 official-source packet.

Historical public filings are often available only to calendar-day precision.
The receipt preserves that limitation.  Its core-source projection uses the
end of the stated local day solely as a conservative upper bound, never as a
claimed publication timestamp.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from scripts import enterprise_judgment_core as core
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_core as core


SCHEMA_VERSION = "enterprise-judgment-source-packet-receipt.v2"
LEGACY_SCHEMA_VERSION = "enterprise-judgment-source-packet-receipt.v1"
ADAPTER_METHOD_VERSION = "enterprise-judgment-source-packet-adapter.v2"
LEGACY_ADAPTER_METHOD_VERSION = "enterprise-judgment-source-packet-adapter.v1"
ALLOWED_OUTPUTS = ["SOURCE_PACKET_READ_MODEL", "RESEARCH_AGENDA"]
FIELD_STATUSES = {"LOCATED", "UNKNOWN", "INCOMPLETE"}

_ROOT_KEYS = {
    "schema_version", "packet_id", "packet_version", "company_id", "issuer_id", "cutoff_at",
    "fields", "sources", "object_class", "claim_class", "allowed_outputs",
}
_FIELD_KEYS = {
    "field_id", "field_ref", "source_id", "status", "material_claim_ids", "locator_ids",
}
_SOURCE_KEYS = {
    "source_id", "source_type", "official_url", "published_on", "available_on",
    "availability_timezone", "eligibility", "responsibility_boundary_ids",
    "responsibility_perimeter_id", "unit", "access_mode", "locators", "boundary_note",
}
_LOCATOR_KEYS = {
    "locator_id", "field_id", "field_ref", "research_question_id", "locator",
    "page_number", "paragraph_ref",
}
_LEGACY_ROOT_KEYS = _ROOT_KEYS - {"fields"}
_LEGACY_LOCATOR_KEYS = {"research_question_id", "locator"}
_FORBIDDEN_KEYS = {
    "price", "market_price", "share_price", "stock_price", "entry_price", "valuation",
    "valuation_result", "expectation_gap", "buyband", "buy_band", "portfolio_action",
    "position", "outcome_value", "outcome_result", "actual_value", "settlement_value",
    "training_score",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str], *, required: set[str] | None = None) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, f"{path}_must_be_object")
        return item
    for field in sorted(set(item).difference(allowed)):
        _add(findings, f"{path}_contains_unapproved_field:{field}")
    for field in sorted((allowed if required is None else required).difference(item)):
        _add(findings, f"{path}_missing_required_field:{field}")
    return item


def _require_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        _add(findings, f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        _add(findings, f"{path}_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        _add(findings, f"{path}_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _add(findings, f"{path}_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _date(value: Any, path: str, findings: list[str]) -> date | None:
    if not _text(value):
        _add(findings, f"{path}_must_be_iso8601_date")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        _add(findings, f"{path}_must_be_iso8601_date")
        return None


def _local_day_end(value: Any, timezone_name: Any, path: str, findings: list[str]) -> datetime | None:
    available_on = _date(value, path, findings)
    if not _text(timezone_name):
        _add(findings, path + "_timezone_required")
        return None
    try:
        zone = ZoneInfo(str(timezone_name))
    except ZoneInfoNotFoundError:
        _add(findings, path + "_timezone_invalid")
        return None
    if available_on is None:
        return None
    return datetime.combine(available_on, time(23, 59, 59), tzinfo=zone).astimezone(timezone.utc)


def _unique_texts(
    value: Any,
    path: str,
    findings: list[str],
    *,
    required: bool = True,
) -> list[str]:
    values = _items(value)
    if required and not values:
        _add(findings, path + "_required")
    result: list[str] = []
    for index, entry in enumerate(values):
        if not _text(entry):
            _add(findings, f"{path}[{index}]_must_be_nonempty_text")
        elif str(entry) in result:
            _add(findings, f"{path}[{index}]_duplicate")
        else:
            result.append(str(entry))
    return result


def build_field_ref(packet_id: str, source_id: str, field_id: str) -> str:
    """Build the packet- and source-bound reference for one declared field."""
    return f"{packet_id}/{source_id}#{field_id}"


def _validate_static_official_url(source: dict[str, Any], path: str, findings: list[str]) -> None:
    raw_url = source.get("official_url")
    if not _text(raw_url):
        return
    parsed = urlparse(str(raw_url))
    host = (parsed.hostname or "").lower()
    source_type = str(source.get("source_type", "")).upper()
    if parsed.scheme != "https" or not host:
        _add(findings, path + ".official_url_must_be_https")
        return
    if host in {"cninfo.com.cn", "www.cninfo.com.cn"}:
        _add(findings, path + ".official_url_dynamic_cninfo_not_allowed")
    elif host.endswith(".cninfo.com.cn") and host != "static.cninfo.com.cn":
        _add(findings, path + ".official_url_dynamic_cninfo_not_allowed")
    if (host == "static.cninfo.com.cn" or "ANNUAL_REPORT" in source_type) and not parsed.path.lower().endswith(".pdf"):
        _add(findings, path + ".official_url_static_pdf_required")


def _forbidden_paths(value: Any, path: str = "source_packet_receipt") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if key_text in _FORBIDDEN_KEYS or key_text.startswith("actual_") or key_text.startswith("settlement_"):
                paths.append(child_path)
            else:
                paths.extend(_forbidden_paths(nested, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _validate_legacy_source_packet_receipt(receipt: Any) -> dict[str, Any]:
    """Validate frozen V1 receipts for read-only replay.

    V1 never acquires V2 field or locator authority. It remains usable by
    historical reconstruction, while new training packages must declare V2.
    """
    findings: list[str] = []
    item = _closed(receipt, _LEGACY_ROOT_KEYS, "source_packet_receipt", findings)
    if item.get("schema_version") != LEGACY_SCHEMA_VERSION:
        _add(findings, "source_packet_receipt.schema_version_invalid")
    for field in ("packet_id", "company_id", "issuer_id"):
        _require_text(item, field, "source_packet_receipt", findings)
    version = item.get("packet_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        _add(findings, "source_packet_receipt.packet_version_must_be_positive_integer")
    cutoff = _instant(item.get("cutoff_at"), "source_packet_receipt.cutoff_at", findings)
    if item.get("object_class") != "SOURCE_PACKET_RECEIPT":
        _add(findings, "source_packet_receipt.object_class_invalid")
    if item.get("claim_class") != "CUTOFF_ELIGIBLE_SOURCE_RECEIPT":
        _add(findings, "source_packet_receipt.claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        _add(findings, "source_packet_receipt.allowed_outputs_must_remain_read_model_and_research_agenda")
    sources = [
        _closed(
            raw,
            _SOURCE_KEYS,
            f"source_packet_receipt.sources[{index}]",
            findings,
            required=_SOURCE_KEYS - {"boundary_note"},
        )
        for index, raw in enumerate(_items(item.get("sources")))
    ]
    if not sources:
        _add(findings, "source_packet_receipt.sources_required")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        path = f"source_packet_receipt.sources[{index}]"
        source_id = _require_text(source, "source_id", path, findings)
        if source_id in source_ids:
            _add(findings, path + ".source_id_duplicate")
        source_ids.add(source_id)
        for field in (
            "source_type", "official_url", "published_on", "available_on", "availability_timezone",
            "responsibility_perimeter_id", "unit", "access_mode",
        ):
            _require_text(source, field, path, findings)
        _validate_static_official_url(source, path, findings)
        published_on = _date(source.get("published_on"), path + ".published_on", findings)
        available_on = _date(source.get("available_on"), path + ".available_on", findings)
        if published_on is not None and available_on is not None and published_on > available_on:
            _add(findings, path + ".published_on_after_available_on")
        available_at = _local_day_end(
            source.get("available_on"), source.get("availability_timezone"), path + ".available_on", findings,
        )
        if cutoff is not None and available_at is not None and available_at > cutoff:
            _add(findings, path + ".available_on_after_cutoff")
        if source.get("eligibility") not in core.SOURCE_ELIGIBILITY:
            _add(findings, path + ".eligibility_invalid")
        if source.get("access_mode") not in {"REMOTE_OFFICIAL_LOCATOR", "LOCAL_MATERIALIZED_COPY"}:
            _add(findings, path + ".access_mode_invalid")
        if source.get("eligibility") == "EVIDENCE_INELIGIBLE" and not _text(source.get("boundary_note")):
            _add(findings, path + ".boundary_note_required")
        _unique_texts(source.get("responsibility_boundary_ids"), path + ".responsibility_boundary_ids", findings)
        locators = [
            _closed(raw, _LEGACY_LOCATOR_KEYS, f"{path}.locators[{locator_index}]", findings)
            for locator_index, raw in enumerate(_items(source.get("locators")))
        ]
        if not locators:
            _add(findings, path + ".locators_required")
        for locator_index, locator in enumerate(locators):
            locator_path = f"{path}.locators[{locator_index}]"
            _require_text(locator, "research_question_id", locator_path, findings)
            _require_text(locator, "locator", locator_path, findings)
    for path in _forbidden_paths(item):
        _add(findings, "source_packet_receipt.forbidden_investment_or_outcome_field:" + path)
    valid = not findings
    return {
        "valid": valid,
        "findings": findings,
        "degradations": ["LEGACY_V1_READ_ONLY_NO_FIELD_BINDING"] if valid else [],
        "source_packet_receipt": deepcopy(item) if valid else None,
        "locator_map": {},
        "field_map": {},
    }


def validate_source_packet_receipt(receipt: Any) -> dict[str, Any]:
    """Validate one official-source receipt without creating a canonical write."""
    if _mapping(receipt).get("schema_version") == LEGACY_SCHEMA_VERSION:
        return _validate_legacy_source_packet_receipt(receipt)
    findings: list[str] = []
    degradations: list[str] = []
    item = _closed(receipt, _ROOT_KEYS, "source_packet_receipt", findings)
    if item.get("schema_version") != SCHEMA_VERSION:
        _add(findings, "source_packet_receipt.schema_version_invalid")
    for field in ("packet_id", "company_id", "issuer_id"):
        _require_text(item, field, "source_packet_receipt", findings)
    if not isinstance(item.get("packet_version"), int) or isinstance(item.get("packet_version"), bool) or item.get("packet_version") < 1:
        _add(findings, "source_packet_receipt.packet_version_must_be_positive_integer")
    cutoff = _instant(item.get("cutoff_at"), "source_packet_receipt.cutoff_at", findings)
    if item.get("object_class") != "SOURCE_PACKET_RECEIPT":
        _add(findings, "source_packet_receipt.object_class_invalid")
    if item.get("claim_class") != "CUTOFF_ELIGIBLE_SOURCE_RECEIPT":
        _add(findings, "source_packet_receipt.claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        _add(findings, "source_packet_receipt.allowed_outputs_must_remain_read_model_and_research_agenda")

    sources = [
        _closed(
            raw,
            _SOURCE_KEYS,
            f"source_packet_receipt.sources[{index}]",
            findings,
            required=_SOURCE_KEYS - {"boundary_note"},
        )
        for index, raw in enumerate(_items(item.get("sources")))
    ]
    if not sources:
        _add(findings, "source_packet_receipt.sources_required")
    source_ids: set[str] = set()
    source_by_id: dict[str, dict[str, Any]] = {}
    available_at_by_source: dict[str, datetime] = {}
    for index, source in enumerate(sources):
        path = f"source_packet_receipt.sources[{index}]"
        source_id = _require_text(source, "source_id", path, findings)
        if source_id in source_ids:
            _add(findings, path + ".source_id_duplicate")
        source_ids.add(source_id)
        if source_id:
            source_by_id[source_id] = source
        for field in (
            "source_type", "official_url", "published_on", "available_on", "availability_timezone",
            "responsibility_perimeter_id", "unit", "access_mode",
        ):
            _require_text(source, field, path, findings)
        _validate_static_official_url(source, path, findings)
        published_on = _date(source.get("published_on"), path + ".published_on", findings)
        available_on = _date(source.get("available_on"), path + ".available_on", findings)
        if published_on is not None and available_on is not None and published_on > available_on:
            _add(findings, path + ".published_on_after_available_on")
        available_at = _local_day_end(
            source.get("available_on"), source.get("availability_timezone"), path + ".available_on", findings,
        )
        if cutoff is not None and available_at is not None and available_at > cutoff:
            _add(findings, path + ".available_on_after_cutoff")
        if source_id and available_at is not None:
            available_at_by_source[source_id] = available_at
        if source.get("eligibility") not in core.SOURCE_ELIGIBILITY:
            _add(findings, path + ".eligibility_invalid")
        if source.get("access_mode") not in {"REMOTE_OFFICIAL_LOCATOR", "LOCAL_MATERIALIZED_COPY"}:
            _add(findings, path + ".access_mode_invalid")
        if source.get("eligibility") == "EVIDENCE_INELIGIBLE" and not _text(source.get("boundary_note")):
            _add(findings, path + ".boundary_note_required")
        _unique_texts(source.get("responsibility_boundary_ids"), path + ".responsibility_boundary_ids", findings)

    fields = [
        _closed(raw, _FIELD_KEYS, f"source_packet_receipt.fields[{index}]", findings)
        for index, raw in enumerate(_items(item.get("fields")))
    ]
    if not fields:
        _add(findings, "source_packet_receipt.fields_required")
    field_by_id: dict[str, dict[str, Any]] = {}
    field_refs: set[str] = set()
    declared_locator_owner: dict[str, str] = {}
    for index, field in enumerate(fields):
        path = f"source_packet_receipt.fields[{index}]"
        field_id = _require_text(field, "field_id", path, findings)
        field_ref = _require_text(field, "field_ref", path, findings)
        source_id = _require_text(field, "source_id", path, findings)
        if field_id in field_by_id:
            _add(findings, path + ".field_id_duplicate")
        elif field_id:
            field_by_id[field_id] = field
        if field_ref in field_refs:
            _add(findings, path + ".field_ref_duplicate")
        elif field_ref:
            field_refs.add(field_ref)
        if source_id and source_id not in source_by_id:
            _add(findings, path + ".source_id_not_in_packet")
        if field_id and field_ref and source_id and _text(item.get("packet_id")):
            expected_ref = build_field_ref(str(item["packet_id"]), source_id, field_id)
            if field_ref != expected_ref:
                _add(findings, path + ".field_ref_not_bound_to_packet_source_and_field")
        if field.get("status") not in FIELD_STATUSES:
            _add(findings, path + ".status_invalid")
        material_claim_ids = _unique_texts(
            field.get("material_claim_ids"), path + ".material_claim_ids", findings, required=False,
        )
        locator_ids = _unique_texts(
            field.get("locator_ids"), path + ".locator_ids", findings, required=False,
        )
        field["material_claim_ids"] = material_claim_ids
        field["locator_ids"] = locator_ids
        for locator_id in locator_ids:
            previous_owner = declared_locator_owner.get(locator_id)
            if previous_owner is not None and previous_owner != field_id:
                _add(findings, path + f".locator_id_owned_by_multiple_fields:{locator_id}")
            elif field_id:
                declared_locator_owner[locator_id] = field_id

    locator_map: dict[str, dict[str, Any]] = {}
    seen_locator_ids: set[str] = set()
    for source_index, source in enumerate(sources):
        source_path = f"source_packet_receipt.sources[{source_index}]"
        source_id = str(source.get("source_id", ""))
        for locator_index, raw_locator in enumerate(_items(source.get("locators"))):
            path = f"{source_path}.locators[{locator_index}]"
            locator = _closed(
                raw_locator,
                _LOCATOR_KEYS,
                path,
                findings,
                required=_LOCATOR_KEYS - {"page_number", "paragraph_ref"},
            )
            locator_id = _require_text(locator, "locator_id", path, findings)
            field_id = _require_text(locator, "field_id", path, findings)
            field_ref = _require_text(locator, "field_ref", path, findings)
            research_question_id = _require_text(locator, "research_question_id", path, findings)
            locator_text = _require_text(locator, "locator", path, findings)
            if locator_id in seen_locator_ids:
                _add(findings, path + ".locator_id_duplicate_in_receipt")
            elif locator_id:
                seen_locator_ids.add(locator_id)
            field = field_by_id.get(field_id)
            if field is None:
                _add(findings, path + ".field_id_dangling")
                continue
            if field.get("field_ref") != field_ref:
                _add(findings, path + ".field_ref_does_not_match_declared_field")
            if field.get("source_id") != source_id:
                _add(findings, path + ".field_cross_source_reference")
            if locator_id and locator_id not in field.get("locator_ids", []):
                _add(findings, path + ".locator_id_not_declared_by_field")

            page_number = locator.get("page_number")
            if page_number is not None and (
                not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1
            ):
                _add(findings, path + ".page_number_must_be_positive_integer")
            paragraph_ref = locator.get("paragraph_ref")
            if paragraph_ref is not None and not _text(paragraph_ref):
                _add(findings, path + ".paragraph_ref_must_be_nonempty_text")
            location_complete = (
                isinstance(page_number, int)
                and not isinstance(page_number, bool)
                and page_number >= 1
            ) or _text(paragraph_ref)
            material_claim_ids = _items(field.get("material_claim_ids"))
            if not location_complete:
                issue = path + ".page_or_paragraph_locator_missing"
                if material_claim_ids:
                    _add(findings, issue + "_for_material_claim")
                else:
                    _add(degradations, issue)
                continue
            available_at = available_at_by_source.get(source_id)
            if not locator_id or available_at is None:
                continue
            locator_map[locator_id] = {
                "locator_id": locator_id,
                "packet_id": item.get("packet_id"),
                "packet_version": item.get("packet_version"),
                "source_id": source_id,
                "field_id": field_id,
                "field_ref": field_ref,
                "research_question_id": research_question_id,
                "locator": locator_text,
                **({"page_number": page_number} if page_number is not None else {}),
                **({"paragraph_ref": str(paragraph_ref)} if _text(paragraph_ref) else {}),
                "available_at": available_at.isoformat(),
                "cutoff_at": item.get("cutoff_at"),
                "cutoff_eligible": cutoff is not None and available_at <= cutoff,
                "source_packet_member": True,
                "source_eligibility": source.get("eligibility"),
            }

    field_map: dict[str, dict[str, Any]] = {}
    for index, field in enumerate(fields):
        path = f"source_packet_receipt.fields[{index}]"
        field_id = str(field.get("field_id", ""))
        locator_ids = list(field.get("locator_ids", []))
        material_claim_ids = list(field.get("material_claim_ids", []))
        resolved_locator_ids = [locator_id for locator_id in locator_ids if locator_id in seen_locator_ids]
        usable_locator_ids = [locator_id for locator_id in locator_ids if locator_id in locator_map]
        missing_locator_ids = [locator_id for locator_id in locator_ids if locator_id not in seen_locator_ids]
        if missing_locator_ids:
            issue = path + ".locator_ids_missing_from_packet:" + ",".join(missing_locator_ids)
            if material_claim_ids:
                _add(findings, issue + ":material_claim_dependency")
            else:
                _add(degradations, issue)
        if field.get("status") in {"UNKNOWN", "INCOMPLETE"}:
            issue = path + f".field_status_{str(field.get('status')).lower()}"
            if material_claim_ids:
                _add(findings, issue + "_cannot_support_material_claim")
            else:
                _add(degradations, issue)
        if field.get("status") == "LOCATED" and not usable_locator_ids:
            issue = path + ".located_field_has_no_usable_locator"
            if material_claim_ids:
                _add(findings, issue + "_for_material_claim")
            else:
                _add(degradations, issue)
        source = source_by_id.get(str(field.get("source_id", "")), {})
        if material_claim_ids and source.get("eligibility") != "ELIGIBLE":
            _add(findings, path + ".material_claim_source_not_eligible")
        if field_id:
            field_map[field_id] = {
                "field_id": field_id,
                "field_ref": field.get("field_ref"),
                "source_id": field.get("source_id"),
                "status": field.get("status"),
                "material_claim_ids": material_claim_ids,
                "locator_ids": locator_ids,
                "resolved_locator_ids": resolved_locator_ids,
                "usable_locator_ids": usable_locator_ids,
            }
    for path in _forbidden_paths(item):
        _add(findings, "source_packet_receipt.forbidden_investment_or_outcome_field:" + path)
    valid = not findings
    return {
        "valid": valid,
        "findings": findings,
        "degradations": degradations,
        "source_packet_receipt": deepcopy(item) if valid else None,
        "locator_map": deepcopy(locator_map) if valid else {},
        "field_map": deepcopy(field_map) if valid else {},
    }


def compile_core_source_package(receipt: Any) -> dict[str, Any]:
    """Project a date-precise receipt to a conservatively timed core package."""
    validation = validate_source_packet_receipt(receipt)
    if not validation["valid"]:
        return {
            "valid": False,
            "findings": validation["findings"],
            "degradations": validation["degradations"],
            "source_package": None,
            "source_packet_read_model": None,
            "locator_map": {},
            "field_map": {},
        }
    item = _mapping(validation["source_packet_receipt"])
    legacy = item.get("schema_version") == LEGACY_SCHEMA_VERSION
    locator_map = _mapping(validation["locator_map"])
    sources: list[dict[str, Any]] = []
    precision_attestations: list[dict[str, str]] = []
    unprojected_source_ids: list[str] = []
    for source in map(_mapping, _items(item["sources"])):
        source_id = source["source_id"]
        available_at = _local_day_end(source["available_on"], source["availability_timezone"], "source_packet_receipt.sources.available_on", [])
        assert available_at is not None  # established by validation
        locators = [
            _mapping(locator)
            for locator in _items(source["locators"])
            if legacy or _mapping(locator).get("locator_id") in locator_map
        ]
        if not locators:
            unprojected_source_ids.append(source_id)
            continue
        sources.append({
            "source_ref": source_id,
            "source_type": source["source_type"],
            "locator": " | ".join(str(_mapping(locator)["locator"]) for locator in locators),
            "available_at": available_at.isoformat(),
            "eligibility": source["eligibility"],
            "responsibility_boundary_ids": list(source["responsibility_boundary_ids"]),
            **({"boundary_note": source["boundary_note"]} if source["eligibility"] == "EVIDENCE_INELIGIBLE" else {}),
        })
        precision_attestations.append({
            "source_ref": source_id,
            "published_on": source["published_on"],
            "available_on": source["available_on"],
            "availability_timezone": source["availability_timezone"],
            "core_available_at": available_at.isoformat(),
            "treatment": "CONSERVATIVE_END_OF_STATED_DAY",
        })
    if not sources:
        return {
            "valid": False,
            "findings": ["source_packet_receipt.no_usable_locators_for_core_projection"],
            "degradations": validation["degradations"],
            "source_package": None,
            "source_packet_read_model": None,
            "locator_map": deepcopy(locator_map),
            "field_map": deepcopy(validation["field_map"]),
        }
    source_package = {
        "source_package_id": item["packet_id"],
        "company_id": item["company_id"],
        "cutoff_at": item["cutoff_at"],
        "method_version": LEGACY_ADAPTER_METHOD_VERSION if legacy else ADAPTER_METHOD_VERSION,
        "sources": sources,
    }
    core_validation = core.validate_source_package(source_package)
    findings = ["source_package:" + finding for finding in core_validation["findings"]]
    if findings:
        return {
            "valid": False,
            "findings": findings,
            "degradations": validation["degradations"],
            "source_package": None,
            "source_packet_read_model": None,
            "locator_map": deepcopy(locator_map),
            "field_map": deepcopy(validation["field_map"]),
        }
    return {
        "valid": True,
        "findings": [],
        "degradations": validation["degradations"],
        "source_package": source_package,
        "locator_map": deepcopy(locator_map),
        "field_map": deepcopy(validation["field_map"]),
        "source_packet_read_model": {
            "packet_id": item["packet_id"],
            "packet_version": item["packet_version"],
            "company_id": item["company_id"],
            "issuer_id": item["issuer_id"],
            "cutoff_at": item["cutoff_at"],
            "precision_attestations": precision_attestations,
            "locator_map": deepcopy(locator_map),
            "field_map": deepcopy(validation["field_map"]),
            "degradations": list(validation["degradations"]),
            "unprojected_source_ids": unprojected_source_ids,
            "field_binding_authority": "NONE_LEGACY_V1" if legacy else "FIELD_LEVEL_V2",
            "investment_authorization": "NOT_AUTHORIZED",
        },
    }
