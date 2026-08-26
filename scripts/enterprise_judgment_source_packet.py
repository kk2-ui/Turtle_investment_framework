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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from scripts import enterprise_judgment_core as core
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_core as core


SCHEMA_VERSION = "enterprise-judgment-source-packet-receipt.v1"
ADAPTER_METHOD_VERSION = "enterprise-judgment-source-packet-adapter.v1"
ALLOWED_OUTPUTS = ["SOURCE_PACKET_READ_MODEL", "RESEARCH_AGENDA"]

_ROOT_KEYS = {
    "schema_version", "packet_id", "packet_version", "company_id", "issuer_id", "cutoff_at",
    "sources", "object_class", "claim_class", "allowed_outputs",
}
_SOURCE_KEYS = {
    "source_id", "source_type", "official_url", "published_on", "available_on",
    "availability_timezone", "eligibility", "responsibility_boundary_ids",
    "responsibility_perimeter_id", "unit", "access_mode", "locators", "boundary_note",
}
_LOCATOR_KEYS = {"research_question_id", "locator"}
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


def _unique_texts(value: Any, path: str, findings: list[str]) -> list[str]:
    values = _items(value)
    if not values:
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


def validate_source_packet_receipt(receipt: Any) -> dict[str, Any]:
    """Validate one official-source receipt without creating a canonical write."""
    findings: list[str] = []
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

    sources = [_closed(raw, _SOURCE_KEYS, f"source_packet_receipt.sources[{index}]", findings, required=_SOURCE_KEYS - {"boundary_note"}) for index, raw in enumerate(_items(item.get("sources")))]
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
        if not str(source.get("official_url", "")).startswith("https://"):
            _add(findings, path + ".official_url_must_be_https")
        _date(source.get("published_on"), path + ".published_on", findings)
        available_at = _local_day_end(
            source.get("available_on"), source.get("availability_timezone"), path + ".available_on", findings,
        )
        if cutoff is not None and available_at is not None and available_at > cutoff:
            _add(findings, path + ".available_on_after_cutoff")
        if source.get("eligibility") not in core.SOURCE_ELIGIBILITY:
            _add(findings, path + ".eligibility_invalid")
        if source.get("eligibility") == "EVIDENCE_INELIGIBLE" and not _text(source.get("boundary_note")):
            _add(findings, path + ".boundary_note_required")
        _unique_texts(source.get("responsibility_boundary_ids"), path + ".responsibility_boundary_ids", findings)
        locators = [_closed(locator, _LOCATOR_KEYS, f"{path}.locators[{locator_index}]", findings) for locator_index, locator in enumerate(_items(source.get("locators")))]
        if not locators:
            _add(findings, path + ".locators_required")
        for locator_index, locator in enumerate(locators):
            _require_text(locator, "research_question_id", f"{path}.locators[{locator_index}]", findings)
            _require_text(locator, "locator", f"{path}.locators[{locator_index}]", findings)
    for path in _forbidden_paths(item):
        _add(findings, "source_packet_receipt.forbidden_investment_or_outcome_field:" + path)
    return {"valid": not findings, "findings": findings, "source_packet_receipt": deepcopy(item) if not findings else None}


def compile_core_source_package(receipt: Any) -> dict[str, Any]:
    """Project a date-precise receipt to a conservatively timed core package."""
    validation = validate_source_packet_receipt(receipt)
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "source_package": None, "source_packet_read_model": None}
    item = _mapping(receipt)
    sources: list[dict[str, Any]] = []
    precision_attestations: list[dict[str, str]] = []
    for source in map(_mapping, _items(item["sources"])):
        source_id = source["source_id"]
        available_at = _local_day_end(source["available_on"], source["availability_timezone"], "source_packet_receipt.sources.available_on", [])
        assert available_at is not None  # established by validation
        locators = _items(source["locators"])
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
    source_package = {
        "source_package_id": item["packet_id"],
        "company_id": item["company_id"],
        "cutoff_at": item["cutoff_at"],
        "method_version": ADAPTER_METHOD_VERSION,
        "sources": sources,
    }
    core_validation = core.validate_source_package(source_package)
    findings = ["source_package:" + finding for finding in core_validation["findings"]]
    if findings:
        return {"valid": False, "findings": findings, "source_package": None, "source_packet_read_model": None}
    return {
        "valid": True,
        "findings": [],
        "source_package": source_package,
        "source_packet_read_model": {
            "packet_id": item["packet_id"],
            "packet_version": item["packet_version"],
            "company_id": item["company_id"],
            "issuer_id": item["issuer_id"],
            "cutoff_at": item["cutoff_at"],
            "precision_attestations": precision_attestations,
            "investment_authorization": "NOT_AUTHORIZED",
        },
    }
