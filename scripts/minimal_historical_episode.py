#!/usr/bin/env python3
"""Closed objects for one minimal, fixture-only historical episode.

This namespace intentionally does not import or extend V5, V6, H1, the
training program, or any investment/report control.  It describes exactly one
company/issuer/cutoff/metric/window chain and has no method-transfer right.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import math
import re
from typing import Any


DECISION_CONTRACT_SCHEMA_VERSION = "turtle-minimal-historical-episode-decision-contract.v1"
TECHNICAL_ROUTE_IDENTITY_SCHEMA_VERSION = "turtle-minimal-historical-episode-technical-route-identity.v1"
# Measurement-contract v1 remains a readable historical record format.  New
# episodes must use v2: it freezes the bounded official-acquisition route
# before a forecaster can freeze a prediction.
MEASUREMENT_CONTRACT_V1_SCHEMA_VERSION = "turtle-minimal-historical-episode-measurement-contract.v1"
MEASUREMENT_CONTRACT_SCHEMA_VERSION = "turtle-minimal-historical-episode-measurement-contract.v2"
STATIC_EVIDENCE_SCHEMA_VERSION = "turtle-minimal-historical-episode-static-evidence.v1"
PREDICTION_SCHEMA_VERSION = "turtle-minimal-historical-episode-prediction.v1"
OUTCOME_ACCESS_SCHEMA_VERSION = "turtle-minimal-historical-episode-outcome-access.v1"
OUTCOME_SOURCE_INVENTORY_SCHEMA_VERSION = "turtle-minimal-historical-episode-outcome-source-inventory.v1"
OBSERVATION_SCHEMA_VERSION = "turtle-minimal-historical-episode-observation.v1"
SETTLEMENT_REQUEST_SCHEMA_VERSION = "turtle-minimal-historical-episode-settlement-request.v1"
SETTLEMENT_SCHEMA_VERSION = "turtle-minimal-historical-episode-settlement.v1"

WINDOW_IDS = {"ONE_YEAR", "THREE_YEAR", "FIVE_YEAR"}
DIRECTIONS = {"INCREASE", "STABLE", "DECREASE"}
OFFICIAL_STATIC_FILING = "OFFICIAL_STATIC_FILING"
NO_METHOD_TRANSFER_RIGHTS = "NO_METHOD_TRANSFER_RIGHTS"
ALLOWED_OUTPUTS = ["MECHANICAL_SETTLEMENT_ONLY"]
DECISION_PURPOSE = "ONE_METRIC_DIRECTIONAL_PREDICTION"
PAGE_REFERENCE = re.compile(r"\bp(?:age)?\.?\s*\d+\b", re.IGNORECASE)
PAGE_NUMBER_REFERENCE = re.compile(
    r"(?:\bpdf\s*)?\bp\.?\s*(\d+)\b|\bpage[_\s-]*(\d+)\b",
    re.IGNORECASE,
)
INVENTORY_STATUSES = {"FIELD_READY", "MEASUREMENT_MISMATCH"}
AVAILABILITY_PRECISIONS = {"DATE_ONLY", "TIMESTAMP"}
CNINFO_OUTCOME_ROUTE_PROVIDER = "CNINFO_ANNOUNCEMENT_METADATA"
CNINFO_OUTCOME_ROUTE_PROVIDER_VERSION = "phase10-cninfo-announcement-query.v1"
CNINFO_OUTCOME_ROUTE_TAB = "fulltext"
CNINFO_OUTCOME_ROUTE_CATEGORY = "ANNUAL_REPORT"
CNINFO_OUTCOME_ROUTE_URL_POLICY = "CNINFO_STATIC_FINALPAGE_PDF"
# A v2 route without this optional field keeps its historical behavior: it
# accepts a singleton original report and fails closed on a version family.
# The second value is the only opt-in that may select a revised report.
CNINFO_ANNUAL_REPORT_VERSION_POLICY_ORIGINAL_ONLY = "ORIGINAL_ONLY"
CNINFO_ANNUAL_REPORT_VERSION_POLICY_ONE_REVISED_AFTER_ORIGINAL = (
    "ONE_OFFICIAL_REVISED_VERSION_AFTER_ORIGINAL"
)
CNINFO_ANNUAL_REPORT_VERSION_POLICIES = {
    CNINFO_ANNUAL_REPORT_VERSION_POLICY_ORIGINAL_ONLY,
    CNINFO_ANNUAL_REPORT_VERSION_POLICY_ONE_REVISED_AFTER_ORIGINAL,
}
CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT = "http://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION = "cninfo-stock-map-code-orgid.v1"

_DECISION_REFERENCE_KEYS = {"decision_contract_id", "decision_contract_version"}
_REFERENCE_KEYS = {"measurement_contract_id", "measurement_contract_version"}
_EVIDENCE_REFERENCE_KEYS = {"evidence_receipt_id", "evidence_receipt_version"}
_TECHNICAL_ROUTE_IDENTITY_REFERENCE_KEYS = {"technical_route_identity_id", "technical_route_identity_version"}
_ROLE_KEYS = {"forecaster_id", "custodian_id"}
_SOURCE_KEYS = {
    "source_id", "source_url", "source_type", "published_at", "issuer_id",
    "metric_id", "responsibility_boundary", "unit", "field_ref", "numeric_value",
}
_OUTCOME_SOURCE_IDENTITY_KEYS = {
    "source_id", "source_url", "source_type", "source_available_at", "source_available_precision",
    "issuer_id", "metric_id", "measurement_period_end", "responsibility_boundary", "unit", "field_ref",
}
_OUTCOME_SOURCE_KEYS = _OUTCOME_SOURCE_IDENTITY_KEYS | {"numeric_value"}
_CONTRACT_V1_KEYS = {
    "schema_version", "measurement_contract_id", "measurement_contract_version", "company_id", "issuer_id",
    "cutoff_at", "metric_id", "window_id", "decision_contract_ref", "outcome_period_end", "responsibility_boundary", "unit",
    "settlement_tolerance", "roles", "object_class", "claim_class", "allowed_outputs",
    "method_transfer_rights",
}
_OUTCOME_ACQUISITION_ROUTE_KEYS = {
    "provider", "provider_version", "security_code", "organization_id", "tab_name",
    "announcement_category", "begin_date", "end_date", "page_size", "static_pdf_url_policy",
    "annual_report_version_policy",
}
_TECHNICAL_ROUTE_IDENTITY_KEYS = {
    "schema_version", "technical_route_identity_id", "technical_route_identity_version", "decision_contract_ref",
    "company_id", "issuer_id", "security_code", "organization_id", "resolver_endpoint", "resolver_version",
    "observed_at", "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
}
_CONTRACT_KEYS = _CONTRACT_V1_KEYS | {"technical_route_identity_ref", "outcome_acquisition_route"}
_DECISION_CONTRACT_KEYS = {
    "schema_version", "decision_contract_id", "decision_contract_version", "company_id", "issuer_id",
    "cutoff_at", "metric_id", "window_id", "decision_purpose", "roles", "object_class", "claim_class",
    "allowed_outputs", "method_transfer_rights",
}
_STATIC_EVIDENCE_KEYS = {
    "schema_version", "evidence_receipt_id", "evidence_receipt_version", "measurement_contract_ref",
    "company_id", "issuer_id", "cutoff_at", "metric_id", "window_id", "curator_id", "source",
    "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
}
_PREDICTION_KEYS = {
    "schema_version", "prediction_id", "measurement_contract_ref", "evidence_receipt_ref", "company_id",
    "issuer_id", "cutoff_at", "metric_id", "window_id", "forecaster_id", "predicted_direction",
    "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
}
_ACCESS_KEYS = {
    "schema_version", "authorization_id", "measurement_contract_ref", "custodian_id", "authorized_at",
    "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
}
_OUTCOME_SOURCE_INVENTORY_COMMON_KEYS = {
    "schema_version", "inventory_receipt_id", "measurement_contract_ref", "custodian_id", "inventoried_at",
    "status", "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
}
_OUTCOME_SOURCE_INVENTORY_READY_KEYS = _OUTCOME_SOURCE_INVENTORY_COMMON_KEYS | {"source"}
_OUTCOME_SOURCE_INVENTORY_MISMATCH_KEYS = _OUTCOME_SOURCE_INVENTORY_COMMON_KEYS | {
    "mismatch_rule", "mismatch_detail", "checked_source",
}
_OBSERVATION_KEYS = {
    "schema_version", "observation_id", "measurement_contract_ref", "company_id", "issuer_id", "cutoff_at",
    "metric_id", "window_id", "custodian_id", "observed_at", "source", "object_class", "claim_class",
    "allowed_outputs", "method_transfer_rights",
}
_SETTLEMENT_REQUEST_KEYS = {
    "schema_version", "settlement_id", "measurement_contract_ref", "custodian_id", "settled_at",
    "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
}
_SETTLEMENT_KEYS = _SETTLEMENT_REQUEST_KEYS | {"prediction_id", "observation_id", "status"}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _result(findings: list[str], **payload: Any) -> dict[str, Any]:
    return {"valid": not findings, "findings": findings, **payload}


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
        return item
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


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _date(value: Any, path: str, findings: list[str]) -> date | None:
    if not _text(value):
        findings.append(f"{path}_must_be_iso_date")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        findings.append(f"{path}_must_be_iso_date")
        return None


def _measurement_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _REFERENCE_KEYS, path, findings)
    contract_id = _require_text(item, "measurement_contract_id", path, findings)
    version = item.get("measurement_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.measurement_contract_version_must_be_positive_integer")
        return None
    return {
        "measurement_contract_id": contract_id,
        "measurement_contract_version": version,
    } if contract_id else None


def _decision_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _DECISION_REFERENCE_KEYS, path, findings)
    contract_id = _require_text(item, "decision_contract_id", path, findings)
    version = item.get("decision_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.decision_contract_version_must_be_positive_integer")
        return None
    return {
        "decision_contract_id": contract_id,
        "decision_contract_version": version,
    } if contract_id else None


def _evidence_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _EVIDENCE_REFERENCE_KEYS, path, findings)
    receipt_id = _require_text(item, "evidence_receipt_id", path, findings)
    version = item.get("evidence_receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.evidence_receipt_version_must_be_positive_integer")
        return None
    return {"evidence_receipt_id": receipt_id, "evidence_receipt_version": version} if receipt_id else None


def _technical_route_identity_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _TECHNICAL_ROUTE_IDENTITY_REFERENCE_KEYS, path, findings)
    identity_id = _require_text(item, "technical_route_identity_id", path, findings)
    version = item.get("technical_route_identity_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.technical_route_identity_version_must_be_positive_integer")
        return None
    return {
        "technical_route_identity_id": identity_id,
        "technical_route_identity_version": version,
    } if identity_id else None


def _fixed_permissions(item: dict[str, Any], path: str, findings: list[str]) -> None:
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append(f"{path}.allowed_outputs_must_be_mechanical_settlement_only")
    if item.get("method_transfer_rights") != NO_METHOD_TRANSFER_RIGHTS:
        findings.append(f"{path}.method_transfer_rights_must_be_no_method_transfer_rights")


def _identity_matches_contract(
    item: dict[str, Any], contract: dict[str, Any], path: str, findings: list[str], *, fields: tuple[str, ...],
    contract_name: str = "measurement_contract",
) -> None:
    for field in fields:
        if item.get(field) != contract.get(field):
            findings.append(f"{path}.{field}_must_match_{contract_name}")


def _numeric(value: Any, path: str, findings: list[str]) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        findings.append(f"{path}_must_be_numeric")
        return None
    number = float(value)
    if not math.isfinite(number):
        findings.append(f"{path}_must_be_finite_numeric")
        return None
    return number


def _static_source(
    value: Any, *, contract: dict[str, Any], path: str, findings: list[str],
) -> dict[str, Any]:
    source = _closed(value, _SOURCE_KEYS, path, findings)
    for field in ("source_id", "source_url", "issuer_id", "metric_id", "responsibility_boundary", "unit", "field_ref"):
        _require_text(source, field, path, findings)
    if source.get("source_type") != OFFICIAL_STATIC_FILING:
        findings.append(f"{path}.source_type_must_be_official_static_filing")
    source_url = source.get("source_url")
    if _text(source_url) and (not str(source_url).startswith("https://") or not str(source_url).lower().endswith(".pdf")):
        findings.append(f"{path}.source_url_must_be_https_static_pdf")
    published_at = _date(source.get("published_at"), f"{path}.published_at", findings)
    cutoff = _instant(contract.get("cutoff_at"), "measurement_contract.cutoff_at", findings)
    if published_at and cutoff and published_at >= cutoff.date():
        findings.append(f"{path}.published_at_must_precede_cutoff")
    if source.get("issuer_id") != contract.get("issuer_id"):
        findings.append(f"{path}.issuer_id_must_match_measurement_contract")
    for field in ("metric_id", "responsibility_boundary", "unit"):
        if source.get(field) != contract.get(field):
            findings.append(f"{path}.{field}_must_match_measurement_contract")
    field_ref = source.get("field_ref")
    if _text(field_ref) and not PAGE_REFERENCE.search(str(field_ref)):
        findings.append(f"{path}.field_ref_must_include_pdf_page")
    _numeric(source.get("numeric_value"), f"{path}.numeric_value", findings)
    return source


def _is_static_cninfo_finalpage_url(value: Any) -> bool:
    if not _text(value):
        return False
    from urllib.parse import urlparse

    parsed = urlparse(str(value))
    return (
        parsed.scheme == "https"
        and parsed.hostname == "static.cninfo.com.cn"
        and parsed.path.startswith("/finalpage/")
        and parsed.path.lower().endswith(".pdf")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


def _one_pdf_page_locator(value: Any, path: str, findings: list[str]) -> None:
    if not _text(value):
        return
    pages = {
        int(page)
        for match in PAGE_NUMBER_REFERENCE.finditer(str(value))
        for page in match.groups()
        if page is not None
    }
    if len(pages) != 1 or next(iter(pages), 0) < 1:
        findings.append(f"{path}_must_include_one_parseable_pdf_page")


def _outcome_source_identity(
    value: Any, *, contract: dict[str, Any], path: str, findings: list[str],
    require_contract_match: bool, allow_numeric_value: bool = False,
) -> dict[str, Any]:
    source = _closed(
        value, _OUTCOME_SOURCE_KEYS if allow_numeric_value else _OUTCOME_SOURCE_IDENTITY_KEYS, path, findings,
    )
    for field in (
        "source_id", "source_url", "issuer_id", "metric_id", "measurement_period_end",
        "responsibility_boundary", "unit", "field_ref", "source_available_precision",
    ):
        _require_text(source, field, path, findings)
    if source.get("source_type") != OFFICIAL_STATIC_FILING:
        findings.append(f"{path}.source_type_must_be_official_static_filing")
    if not _is_static_cninfo_finalpage_url(source.get("source_url")):
        findings.append(f"{path}.source_url_must_be_exact_static_cninfo_finalpage_pdf")
    precision = source.get("source_available_precision")
    available_at: datetime | None = None
    available_date: date | None = None
    if precision == "TIMESTAMP":
        available_at = _instant(source.get("source_available_at"), f"{path}.source_available_at", findings)
        if available_at is not None:
            available_date = available_at.date()
    elif precision == "DATE_ONLY":
        available_date = _date(source.get("source_available_at"), f"{path}.source_available_at", findings)
    else:
        findings.append(f"{path}.source_available_precision_invalid")
    _date(source.get("measurement_period_end"), f"{path}.measurement_period_end", findings)
    cutoff = _instant(contract.get("cutoff_at"), "measurement_contract.cutoff_at", findings)
    outcome_period_end = _date(contract.get("outcome_period_end"), "measurement_contract.outcome_period_end", findings)
    if available_at and cutoff and available_at <= cutoff:
        findings.append(f"{path}.source_available_at_must_follow_cutoff")
    if available_date and cutoff and available_date <= cutoff.date():
        findings.append(f"{path}.source_available_at_must_follow_cutoff")
    if available_date and outcome_period_end and available_date <= outcome_period_end:
        findings.append(f"{path}.source_available_at_must_follow_outcome_period_end")
    if require_contract_match:
        if source.get("issuer_id") != contract.get("issuer_id"):
            findings.append(f"{path}.issuer_id_must_match_measurement_contract")
        if source.get("measurement_period_end") != contract.get("outcome_period_end"):
            findings.append(f"{path}.measurement_period_end_must_match_measurement_contract_outcome_period_end")
        for field in ("metric_id", "responsibility_boundary", "unit"):
            if source.get(field) != contract.get(field):
                findings.append(f"{path}.{field}_must_match_measurement_contract")
    _one_pdf_page_locator(source.get("field_ref"), f"{path}.field_ref", findings)
    return source


def _outcome_source(value: Any, *, contract: dict[str, Any], path: str, findings: list[str]) -> dict[str, Any]:
    source = _outcome_source_identity(
        value, contract=contract, path=path, findings=findings, require_contract_match=True, allow_numeric_value=True,
    )
    _numeric(source.get("numeric_value"), f"{path}.numeric_value", findings)
    return source


def validate_decision_contract(decision_contract: Any) -> dict[str, Any]:
    """Validate the immutable, one-metric decision intent for a minimal episode."""
    findings: list[str] = []
    item = _closed(decision_contract, _DECISION_CONTRACT_KEYS, "decision_contract", findings)
    if item.get("schema_version") != DECISION_CONTRACT_SCHEMA_VERSION:
        findings.append("decision_contract.schema_version_invalid")
    _require_text(item, "decision_contract_id", "decision_contract", findings)
    version = item.get("decision_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("decision_contract.decision_contract_version_must_be_positive_integer")
    for field in ("company_id", "issuer_id", "metric_id"):
        _require_text(item, field, "decision_contract", findings)
    _instant(item.get("cutoff_at"), "decision_contract.cutoff_at", findings)
    if item.get("window_id") not in WINDOW_IDS:
        findings.append("decision_contract.window_id_invalid")
    if item.get("decision_purpose") != DECISION_PURPOSE:
        findings.append("decision_contract.decision_purpose_invalid")
    roles = _closed(item.get("roles"), _ROLE_KEYS, "decision_contract.roles", findings)
    forecaster = _require_text(roles, "forecaster_id", "decision_contract.roles", findings)
    custodian = _require_text(roles, "custodian_id", "decision_contract.roles", findings)
    if forecaster and custodian and forecaster == custodian:
        findings.append("decision_contract.roles_must_be_independent")
    if item.get("object_class") != "MINIMAL_HISTORICAL_DECISION_CONTRACT":
        findings.append("decision_contract.object_class_invalid")
    if item.get("claim_class") != "ONE_METRIC_DIRECTIONAL_DECISION_SCOPE":
        findings.append("decision_contract.claim_class_invalid")
    _fixed_permissions(item, "decision_contract", findings)
    return _result(findings, decision_contract=deepcopy(item) if not findings else None)


def validate_technical_route_identity(
    route_identity: Any, *, decision_contract: Any | None = None,
) -> dict[str, Any]:
    """Validate a code-to-orgId routing receipt with no economic evidence.

    The closed receipt intentionally cannot carry a name, title, announcement,
    PDF text, result, price, or any outcome payload. It is technical routing
    provenance only, and binds to a pre-existing frozen Decision Contract.
    """
    findings: list[str] = []
    item = _closed(route_identity, _TECHNICAL_ROUTE_IDENTITY_KEYS, "technical_route_identity", findings)
    if item.get("schema_version") != TECHNICAL_ROUTE_IDENTITY_SCHEMA_VERSION:
        findings.append("technical_route_identity.schema_version_invalid")
    _require_text(item, "technical_route_identity_id", "technical_route_identity", findings)
    version = item.get("technical_route_identity_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("technical_route_identity.technical_route_identity_version_must_be_positive_integer")
    for field in ("company_id", "issuer_id", "security_code", "organization_id", "resolver_endpoint", "resolver_version"):
        _require_text(item, field, "technical_route_identity", findings)
    security_code = str(item.get("security_code") or "").strip()
    if not re.fullmatch(r"\d{6}", security_code):
        findings.append("technical_route_identity.security_code_must_be_six_digits")
    else:
        if item.get("company_id") != f"CN:{security_code}":
            findings.append("technical_route_identity.security_code_must_match_company_id")
        if item.get("issuer_id") != f"ISSUER:CN:{security_code}":
            findings.append("technical_route_identity.security_code_must_match_issuer_id")
    if item.get("resolver_endpoint") != CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT:
        findings.append("technical_route_identity.resolver_endpoint_invalid")
    if item.get("resolver_version") != CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION:
        findings.append("technical_route_identity.resolver_version_invalid")
    _instant(item.get("observed_at"), "technical_route_identity.observed_at", findings)
    decision_ref = _decision_reference(
        item.get("decision_contract_ref"), "technical_route_identity.decision_contract_ref", findings,
    )
    if decision_contract is not None:
        decision_result = validate_decision_contract(decision_contract)
        findings.extend(f"technical_route_identity.decision_contract:{finding}" for finding in decision_result["findings"])
        decision = _mapping(decision_result.get("decision_contract"))
        if decision_ref != {
            "decision_contract_id": decision.get("decision_contract_id"),
            "decision_contract_version": decision.get("decision_contract_version"),
        }:
            findings.append("technical_route_identity.decision_contract_ref_must_match_decision_contract")
        _identity_matches_contract(
            item, decision, "technical_route_identity", findings,
            fields=("company_id", "issuer_id"), contract_name="decision_contract",
        )
    if item.get("object_class") != "MINIMAL_HISTORICAL_TECHNICAL_ROUTE_IDENTITY":
        findings.append("technical_route_identity.object_class_invalid")
    if item.get("claim_class") != "TECHNICAL_ROUTE_IDENTITY":
        findings.append("technical_route_identity.claim_class_invalid")
    _fixed_permissions(item, "technical_route_identity", findings)
    return _result(findings, technical_route_identity=deepcopy(item) if not findings else None)


def _outcome_acquisition_route(
    value: Any, *, contract: dict[str, Any], path: str, findings: list[str],
) -> dict[str, Any]:
    """Validate the exact, pre-prediction CNINFO enumeration route for v2.

    This is an acquisition identity, not outcome evidence.  It deliberately
    contains no title, result value, PDF quote, or selected source identity.
    The later custodian can only enumerate this frozen route and then apply the
    already-existing value-free FIELD_READY / MEASUREMENT_MISMATCH gate.
    """
    # ``annual_report_version_policy`` was added after the first v2 routes
    # were frozen.  It is deliberately optional so those immutable records
    # retain their singleton-original, fail-closed behavior.
    route = _mapping(value)
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
    for field in sorted(set(route).difference(_OUTCOME_ACQUISITION_ROUTE_KEYS)):
        findings.append(f"{path}_contains_unapproved_field:{field}")
    required_fields = _OUTCOME_ACQUISITION_ROUTE_KEYS - {"annual_report_version_policy"}
    for field in sorted(required_fields.difference(route)):
        findings.append(f"{path}_missing_required_field:{field}")
    for field in ("provider", "provider_version", "security_code", "organization_id", "tab_name",
                  "announcement_category", "static_pdf_url_policy"):
        _require_text(route, field, path, findings)
    if route.get("provider") != CNINFO_OUTCOME_ROUTE_PROVIDER:
        findings.append(f"{path}.provider_must_be_cninfo_announcement_metadata")
    if route.get("provider_version") != CNINFO_OUTCOME_ROUTE_PROVIDER_VERSION:
        findings.append(f"{path}.provider_version_invalid")
    if route.get("tab_name") != CNINFO_OUTCOME_ROUTE_TAB:
        findings.append(f"{path}.tab_name_must_be_fulltext")
    if route.get("announcement_category") != CNINFO_OUTCOME_ROUTE_CATEGORY:
        findings.append(f"{path}.announcement_category_must_be_annual_report")
    if route.get("static_pdf_url_policy") != CNINFO_OUTCOME_ROUTE_URL_POLICY:
        findings.append(f"{path}.static_pdf_url_policy_must_be_cninfo_static_finalpage_pdf")
    version_policy = route.get("annual_report_version_policy")
    if version_policy is not None and version_policy not in CNINFO_ANNUAL_REPORT_VERSION_POLICIES:
        findings.append(f"{path}.annual_report_version_policy_invalid")
    security_code = str(route.get("security_code") or "").strip()
    if not re.fullmatch(r"\d{6}", security_code):
        findings.append(f"{path}.security_code_must_be_six_digits")
    else:
        if contract.get("company_id") != f"CN:{security_code}":
            findings.append(f"{path}.security_code_must_match_company_id")
        if contract.get("issuer_id") != f"ISSUER:CN:{security_code}":
            findings.append(f"{path}.security_code_must_match_issuer_id")
    begin_date = _date(route.get("begin_date"), f"{path}.begin_date", findings)
    end_date = _date(route.get("end_date"), f"{path}.end_date", findings)
    if begin_date and end_date and begin_date > end_date:
        findings.append(f"{path}.begin_date_must_not_follow_end_date")
    outcome_period_end = _date(contract.get("outcome_period_end"), "measurement_contract.outcome_period_end", findings)
    if begin_date and outcome_period_end and begin_date <= outcome_period_end:
        findings.append(f"{path}.begin_date_must_follow_outcome_period_end")
    page_size = route.get("page_size")
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1 or page_size > 30:
        findings.append(f"{path}.page_size_must_be_between_1_and_30")
    return route


def validate_measurement_contract(
    contract: Any, *, decision_contract: Any | None = None, technical_route_identity: Any | None = None,
) -> dict[str, Any]:
    """Validate one company/issuer/cutoff/metric/window measurement contract."""
    findings: list[str] = []
    raw = _mapping(contract)
    schema_version = raw.get("schema_version")
    allowed_keys = _CONTRACT_V1_KEYS if schema_version == MEASUREMENT_CONTRACT_V1_SCHEMA_VERSION else _CONTRACT_KEYS
    item = _closed(contract, allowed_keys, "measurement_contract", findings)
    if schema_version not in {MEASUREMENT_CONTRACT_V1_SCHEMA_VERSION, MEASUREMENT_CONTRACT_SCHEMA_VERSION}:
        findings.append("measurement_contract.schema_version_invalid")
    _require_text(item, "measurement_contract_id", "measurement_contract", findings)
    version = item.get("measurement_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("measurement_contract.measurement_contract_version_must_be_positive_integer")
    for field in ("company_id", "issuer_id", "metric_id", "responsibility_boundary", "unit"):
        _require_text(item, field, "measurement_contract", findings)
    cutoff = _instant(item.get("cutoff_at"), "measurement_contract.cutoff_at", findings)
    outcome_period_end = _date(item.get("outcome_period_end"), "measurement_contract.outcome_period_end", findings)
    if cutoff and outcome_period_end and outcome_period_end <= cutoff.date():
        findings.append("measurement_contract.outcome_period_end_must_follow_cutoff")
    if item.get("window_id") not in WINDOW_IDS:
        findings.append("measurement_contract.window_id_invalid")
    decision_ref = _decision_reference(item.get("decision_contract_ref"), "measurement_contract.decision_contract_ref", findings)
    if decision_contract is not None:
        decision_result = validate_decision_contract(decision_contract)
        findings.extend(f"measurement_contract.decision_contract:{finding}" for finding in decision_result["findings"])
        decision = _mapping(decision_result.get("decision_contract"))
        if decision_ref != {
            "decision_contract_id": decision.get("decision_contract_id"),
            "decision_contract_version": decision.get("decision_contract_version"),
        }:
            findings.append("measurement_contract.decision_contract_ref_must_match_decision_contract")
        _identity_matches_contract(
            item, decision, "measurement_contract", findings,
            fields=("company_id", "issuer_id", "cutoff_at", "metric_id", "window_id"),
            contract_name="decision_contract",
        )
        if item.get("roles") != decision.get("roles"):
            findings.append("measurement_contract.roles_must_match_decision_contract")
    tolerance = _numeric(item.get("settlement_tolerance"), "measurement_contract.settlement_tolerance", findings)
    if tolerance is not None and tolerance < 0:
        findings.append("measurement_contract.settlement_tolerance_must_be_nonnegative")
    roles = _closed(item.get("roles"), _ROLE_KEYS, "measurement_contract.roles", findings)
    forecaster = _require_text(roles, "forecaster_id", "measurement_contract.roles", findings)
    custodian = _require_text(roles, "custodian_id", "measurement_contract.roles", findings)
    if forecaster and custodian and forecaster == custodian:
        findings.append("measurement_contract.roles_must_be_independent")
    if item.get("object_class") != "MINIMAL_HISTORICAL_MEASUREMENT_CONTRACT":
        findings.append("measurement_contract.object_class_invalid")
    if item.get("claim_class") != "ONE_METRIC_PRE_OUTCOME_SCOPE":
        findings.append("measurement_contract.claim_class_invalid")
    if schema_version == MEASUREMENT_CONTRACT_SCHEMA_VERSION:
        route = _outcome_acquisition_route(
            item.get("outcome_acquisition_route"), contract=item,
            path="measurement_contract.outcome_acquisition_route", findings=findings,
        )
        route_ref = _technical_route_identity_reference(
            item.get("technical_route_identity_ref"), "measurement_contract.technical_route_identity_ref", findings,
        )
        if technical_route_identity is not None:
            route_identity_result = validate_technical_route_identity(
                technical_route_identity, decision_contract=decision_contract,
            )
            findings.extend(
                f"measurement_contract.technical_route_identity:{finding}"
                for finding in route_identity_result["findings"]
            )
            route_identity = _mapping(route_identity_result.get("technical_route_identity"))
            if route_ref != {
                "technical_route_identity_id": route_identity.get("technical_route_identity_id"),
                "technical_route_identity_version": route_identity.get("technical_route_identity_version"),
            }:
                findings.append("measurement_contract.technical_route_identity_ref_must_match_route_identity")
            for field in ("company_id", "issuer_id"):
                if item.get(field) != route_identity.get(field):
                    findings.append(f"measurement_contract.{field}_must_match_route_identity")
            if route.get("security_code") != route_identity.get("security_code"):
                findings.append("measurement_contract.outcome_acquisition_route.security_code_must_match_route_identity")
            if route.get("organization_id") != route_identity.get("organization_id"):
                findings.append("measurement_contract.outcome_acquisition_route.organization_id_must_match_route_identity")
    _fixed_permissions(item, "measurement_contract", findings)
    return _result(findings, measurement_contract=deepcopy(item) if not findings else None)


def outcome_acquisition_route_from_measurement_contract(contract: Any) -> dict[str, Any]:
    """Return the v2 route already frozen in a valid Measurement Contract.

    Callers cannot supplement this route.  The function is intentionally the
    only supported bridge between a stored contract and the CNINFO metadata
    adapter, so a caller cannot steer post-prediction enumeration with a new
    security code, organization, date window, or source policy.
    """
    result = validate_measurement_contract(contract)
    if not result["valid"]:
        raise ValueError("measurement contract is invalid")
    payload = result["measurement_contract"]
    if payload.get("schema_version") != MEASUREMENT_CONTRACT_SCHEMA_VERSION:
        raise ValueError("measurement contract v2 outcome acquisition route is required")
    return deepcopy(payload["outcome_acquisition_route"])


def validate_static_evidence(evidence: Any, *, measurement_contract: Any) -> dict[str, Any]:
    """Validate one static official, pre-cutoff numeric observation."""
    findings: list[str] = []
    item = _closed(evidence, _STATIC_EVIDENCE_KEYS, "static_evidence", findings)
    contract_result = validate_measurement_contract(measurement_contract)
    findings.extend(f"static_evidence.measurement_contract:{finding}" for finding in contract_result["findings"])
    contract = _mapping(contract_result.get("measurement_contract"))
    if item.get("schema_version") != STATIC_EVIDENCE_SCHEMA_VERSION:
        findings.append("static_evidence.schema_version_invalid")
    _require_text(item, "evidence_receipt_id", "static_evidence", findings)
    version = item.get("evidence_receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("static_evidence.evidence_receipt_version_must_be_positive_integer")
    reference = _measurement_reference(item.get("measurement_contract_ref"), "static_evidence.measurement_contract_ref", findings)
    if contract and reference != {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }:
        findings.append("static_evidence.measurement_contract_ref_must_match_contract")
    _identity_matches_contract(
        item, contract, "static_evidence", findings,
        fields=("company_id", "issuer_id", "cutoff_at", "metric_id", "window_id"),
    )
    curator_id = _require_text(item, "curator_id", "static_evidence", findings)
    roles = _mapping(contract.get("roles"))
    if curator_id and curator_id in {roles.get("forecaster_id"), roles.get("custodian_id")}:
        findings.append("static_evidence.curator_must_be_independent_from_forecaster_and_custodian")
    _static_source(item.get("source"), contract=contract, path="static_evidence.source", findings=findings)
    if item.get("object_class") != "MINIMAL_HISTORICAL_STATIC_EVIDENCE":
        findings.append("static_evidence.object_class_invalid")
    if item.get("claim_class") != "CUTOFF_VISIBLE_OFFICIAL_FIELD":
        findings.append("static_evidence.claim_class_invalid")
    _fixed_permissions(item, "static_evidence", findings)
    return _result(findings, static_evidence=deepcopy(item) if not findings else None)


def validate_prediction(
    prediction: Any, *, measurement_contract: Any, static_evidence: Any,
) -> dict[str, Any]:
    """Validate exactly one directional prediction without a method claim."""
    findings: list[str] = []
    item = _closed(prediction, _PREDICTION_KEYS, "prediction", findings)
    contract_result = validate_measurement_contract(measurement_contract)
    findings.extend(f"prediction.measurement_contract:{finding}" for finding in contract_result["findings"])
    contract = _mapping(contract_result.get("measurement_contract"))
    evidence_result = validate_static_evidence(static_evidence, measurement_contract=contract)
    findings.extend(f"prediction.static_evidence:{finding}" for finding in evidence_result["findings"])
    evidence = _mapping(evidence_result.get("static_evidence"))
    if item.get("schema_version") != PREDICTION_SCHEMA_VERSION:
        findings.append("prediction.schema_version_invalid")
    _require_text(item, "prediction_id", "prediction", findings)
    contract_ref = _measurement_reference(item.get("measurement_contract_ref"), "prediction.measurement_contract_ref", findings)
    if contract_ref != {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }:
        findings.append("prediction.measurement_contract_ref_must_match_contract")
    evidence_ref = _evidence_reference(item.get("evidence_receipt_ref"), "prediction.evidence_receipt_ref", findings)
    if evidence_ref != {
        "evidence_receipt_id": evidence.get("evidence_receipt_id"),
        "evidence_receipt_version": evidence.get("evidence_receipt_version"),
    }:
        findings.append("prediction.evidence_receipt_ref_must_match_static_evidence")
    _identity_matches_contract(
        item, contract, "prediction", findings,
        fields=("company_id", "issuer_id", "cutoff_at", "metric_id", "window_id"),
    )
    if item.get("forecaster_id") != _mapping(contract.get("roles")).get("forecaster_id"):
        findings.append("prediction.forecaster_id_must_match_measurement_contract")
    if item.get("predicted_direction") not in DIRECTIONS:
        findings.append("prediction.predicted_direction_invalid")
    if item.get("object_class") != "MINIMAL_HISTORICAL_PREDICTION":
        findings.append("prediction.object_class_invalid")
    if item.get("claim_class") != "ONE_METRIC_DIRECTIONAL_PREDICTION":
        findings.append("prediction.claim_class_invalid")
    _fixed_permissions(item, "prediction", findings)
    return _result(findings, prediction=deepcopy(item) if not findings else None)


def validate_outcome_access(authorization: Any, *, measurement_contract: Any) -> dict[str, Any]:
    """Validate the contract-only payload sent to the independent custodian."""
    findings: list[str] = []
    item = _closed(authorization, _ACCESS_KEYS, "outcome_access", findings)
    contract_result = validate_measurement_contract(measurement_contract)
    findings.extend(f"outcome_access.measurement_contract:{finding}" for finding in contract_result["findings"])
    contract = _mapping(contract_result.get("measurement_contract"))
    if item.get("schema_version") != OUTCOME_ACCESS_SCHEMA_VERSION:
        findings.append("outcome_access.schema_version_invalid")
    _require_text(item, "authorization_id", "outcome_access", findings)
    reference = _measurement_reference(item.get("measurement_contract_ref"), "outcome_access.measurement_contract_ref", findings)
    if reference != {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }:
        findings.append("outcome_access.measurement_contract_ref_must_match_contract")
    if item.get("custodian_id") != _mapping(contract.get("roles")).get("custodian_id"):
        findings.append("outcome_access.custodian_id_must_match_measurement_contract")
    _instant(item.get("authorized_at"), "outcome_access.authorized_at", findings)
    if item.get("object_class") != "MINIMAL_HISTORICAL_OUTCOME_ACCESS":
        findings.append("outcome_access.object_class_invalid")
    if item.get("claim_class") != "CUSTODIAN_CONTRACT_ONLY_ACCESS":
        findings.append("outcome_access.claim_class_invalid")
    _fixed_permissions(item, "outcome_access", findings)
    return _result(findings, outcome_access=deepcopy(item) if not findings else None)


def validate_outcome_source_inventory(
    inventory: Any, *, measurement_contract: Any,
) -> dict[str, Any]:
    """Validate a value-free, custodian-only source readiness receipt.

    A FIELD_READY receipt identifies exactly one direct official source before
    any value or quote is permitted.  A MEASUREMENT_MISMATCH receipt records
    why no direct field can be observed without inventing a label.
    """
    findings: list[str] = []
    item = _mapping(inventory)
    if not isinstance(inventory, dict):
        findings.append("outcome_source_inventory_must_be_object")
    status = item.get("status")
    allowed = (
        _OUTCOME_SOURCE_INVENTORY_READY_KEYS
        if status == "FIELD_READY"
        else _OUTCOME_SOURCE_INVENTORY_MISMATCH_KEYS
        if status == "MEASUREMENT_MISMATCH"
        else _OUTCOME_SOURCE_INVENTORY_COMMON_KEYS
    )
    for field in sorted(set(item).difference(allowed)):
        findings.append(f"outcome_source_inventory_contains_unapproved_field:{field}")
    for field in sorted(_OUTCOME_SOURCE_INVENTORY_COMMON_KEYS.difference(item)):
        findings.append(f"outcome_source_inventory_missing_required_field:{field}")
    contract_result = validate_measurement_contract(measurement_contract)
    findings.extend(f"outcome_source_inventory.measurement_contract:{finding}" for finding in contract_result["findings"])
    contract = _mapping(contract_result.get("measurement_contract"))
    if item.get("schema_version") != OUTCOME_SOURCE_INVENTORY_SCHEMA_VERSION:
        findings.append("outcome_source_inventory.schema_version_invalid")
    _require_text(item, "inventory_receipt_id", "outcome_source_inventory", findings)
    reference = _measurement_reference(
        item.get("measurement_contract_ref"), "outcome_source_inventory.measurement_contract_ref", findings,
    )
    if reference != {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }:
        findings.append("outcome_source_inventory.measurement_contract_ref_must_match_contract")
    if item.get("custodian_id") != _mapping(contract.get("roles")).get("custodian_id"):
        findings.append("outcome_source_inventory.custodian_id_must_match_measurement_contract")
    _instant(item.get("inventoried_at"), "outcome_source_inventory.inventoried_at", findings)
    if status not in INVENTORY_STATUSES:
        findings.append("outcome_source_inventory.status_invalid")
    elif status == "FIELD_READY":
        if "source" not in item:
            findings.append("outcome_source_inventory.source_required_for_field_ready")
        _outcome_source_identity(
            item.get("source"), contract=contract, path="outcome_source_inventory.source", findings=findings,
            require_contract_match=True,
        )
    else:
        _require_text(item, "mismatch_rule", "outcome_source_inventory", findings)
        _require_text(item, "mismatch_detail", "outcome_source_inventory", findings)
        if "checked_source" in item:
            _outcome_source_identity(
                item.get("checked_source"), contract=contract,
                path="outcome_source_inventory.checked_source", findings=findings,
                require_contract_match=False,
            )
    if item.get("object_class") != "MINIMAL_HISTORICAL_OUTCOME_SOURCE_INVENTORY_RECEIPT":
        findings.append("outcome_source_inventory.object_class_invalid")
    if item.get("claim_class") != "CUSTODIAN_VALUE_FREE_SOURCE_READINESS":
        findings.append("outcome_source_inventory.claim_class_invalid")
    _fixed_permissions(item, "outcome_source_inventory", findings)
    return _result(findings, outcome_source_inventory=deepcopy(item) if not findings else None)


def _observation_matches_field_ready_inventory(
    source: dict[str, Any], inventory: dict[str, Any], findings: list[str],
) -> None:
    if inventory.get("status") != "FIELD_READY":
        findings.append("observation.outcome_source_inventory_must_be_field_ready")
        return
    inventory_source = _mapping(inventory.get("source"))
    for field in (
        "source_id", "source_url", "source_available_at", "source_available_precision", "issuer_id",
        "metric_id", "measurement_period_end", "responsibility_boundary", "unit", "field_ref",
    ):
        if source.get(field) != inventory_source.get(field):
            findings.append(f"observation.source.{field}_must_match_field_ready_inventory")


def validate_observation(
    observation: Any, *, measurement_contract: Any, outcome_source_inventory: Any,
) -> dict[str, Any]:
    """Validate one custodian-only post-cutoff metric observation."""
    findings: list[str] = []
    item = _closed(observation, _OBSERVATION_KEYS, "observation", findings)
    contract_result = validate_measurement_contract(measurement_contract)
    findings.extend(f"observation.measurement_contract:{finding}" for finding in contract_result["findings"])
    contract = _mapping(contract_result.get("measurement_contract"))
    if item.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
        findings.append("observation.schema_version_invalid")
    _require_text(item, "observation_id", "observation", findings)
    reference = _measurement_reference(item.get("measurement_contract_ref"), "observation.measurement_contract_ref", findings)
    if reference != {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }:
        findings.append("observation.measurement_contract_ref_must_match_contract")
    _identity_matches_contract(
        item, contract, "observation", findings,
        fields=("company_id", "issuer_id", "cutoff_at", "metric_id", "window_id"),
    )
    if item.get("custodian_id") != _mapping(contract.get("roles")).get("custodian_id"):
        findings.append("observation.custodian_id_must_match_measurement_contract")
    observed_at = _instant(item.get("observed_at"), "observation.observed_at", findings)
    source = _outcome_source(item.get("source"), contract=contract, path="observation.source", findings=findings)
    inventory_result = validate_outcome_source_inventory(
        outcome_source_inventory, measurement_contract=contract,
    )
    findings.extend(f"observation.outcome_source_inventory:{finding}" for finding in inventory_result["findings"])
    inventory = _mapping(inventory_result.get("outcome_source_inventory"))
    if inventory:
        _observation_matches_field_ready_inventory(source, inventory, findings)
    if source.get("source_available_precision") == "DATE_ONLY":
        source_date = _date(source.get("source_available_at"), "observation.source.source_available_at", findings)
        if observed_at and source_date and source_date > observed_at.date():
            findings.append("observation.source_cannot_follow_observation_receipt")
    elif source.get("source_available_precision") == "TIMESTAMP":
        source_at = _instant(source.get("source_available_at"), "observation.source.source_available_at", findings)
        if observed_at and source_at and source_at > observed_at:
            findings.append("observation.source_cannot_follow_observation_receipt")
    if item.get("object_class") != "MINIMAL_HISTORICAL_OUTCOME_OBSERVATION":
        findings.append("observation.object_class_invalid")
    if item.get("claim_class") != "CUSTODIAN_OBSERVED_OFFICIAL_FIELD":
        findings.append("observation.claim_class_invalid")
    _fixed_permissions(item, "observation", findings)
    return _result(findings, observation=deepcopy(item) if not findings else None)


def validate_settlement_request(request: Any, *, measurement_contract: Any) -> dict[str, Any]:
    """Validate a content-free request to mechanically settle the stored chain."""
    findings: list[str] = []
    item = _closed(request, _SETTLEMENT_REQUEST_KEYS, "settlement_request", findings)
    contract_result = validate_measurement_contract(measurement_contract)
    findings.extend(f"settlement_request.measurement_contract:{finding}" for finding in contract_result["findings"])
    contract = _mapping(contract_result.get("measurement_contract"))
    if item.get("schema_version") != SETTLEMENT_REQUEST_SCHEMA_VERSION:
        findings.append("settlement_request.schema_version_invalid")
    _require_text(item, "settlement_id", "settlement_request", findings)
    reference = _measurement_reference(item.get("measurement_contract_ref"), "settlement_request.measurement_contract_ref", findings)
    if reference != {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }:
        findings.append("settlement_request.measurement_contract_ref_must_match_contract")
    if item.get("custodian_id") != _mapping(contract.get("roles")).get("custodian_id"):
        findings.append("settlement_request.custodian_id_must_match_measurement_contract")
    _instant(item.get("settled_at"), "settlement_request.settled_at", findings)
    if item.get("object_class") != "MINIMAL_HISTORICAL_SETTLEMENT_REQUEST":
        findings.append("settlement_request.object_class_invalid")
    if item.get("claim_class") != "CUSTODIAN_MECHANICAL_SETTLEMENT_REQUEST":
        findings.append("settlement_request.claim_class_invalid")
    _fixed_permissions(item, "settlement_request", findings)
    return _result(findings, settlement_request=deepcopy(item) if not findings else None)


def mechanical_settlement(
    request: Any, *, measurement_contract: Any, static_evidence: Any, prediction: Any, observation: Any,
    outcome_source_inventory: Any,
) -> dict[str, Any]:
    """Derive MATCH/MISS from stored numeric values; caller supplies no result."""
    findings: list[str] = []
    request_result = validate_settlement_request(request, measurement_contract=measurement_contract)
    findings.extend(f"settlement:{finding}" for finding in request_result["findings"])
    contract_result = validate_measurement_contract(measurement_contract)
    findings.extend(f"settlement.measurement_contract:{finding}" for finding in contract_result["findings"])
    contract = _mapping(contract_result.get("measurement_contract"))
    evidence_result = validate_static_evidence(static_evidence, measurement_contract=contract)
    findings.extend(f"settlement.static_evidence:{finding}" for finding in evidence_result["findings"])
    prediction_result = validate_prediction(prediction, measurement_contract=contract, static_evidence=static_evidence)
    findings.extend(f"settlement.prediction:{finding}" for finding in prediction_result["findings"])
    observation_result = validate_observation(
        observation, measurement_contract=contract, outcome_source_inventory=outcome_source_inventory,
    )
    findings.extend(f"settlement.observation:{finding}" for finding in observation_result["findings"])
    if findings:
        return _result(findings, settlement=None)
    request_item = request_result["settlement_request"]
    evidence_item = evidence_result["static_evidence"]
    prediction_item = prediction_result["prediction"]
    observation_item = observation_result["observation"]
    baseline = float(evidence_item["source"]["numeric_value"])
    observed = float(observation_item["source"]["numeric_value"])
    tolerance = float(contract["settlement_tolerance"])
    if observed - baseline > tolerance:
        realised = "INCREASE"
    elif baseline - observed > tolerance:
        realised = "DECREASE"
    else:
        realised = "STABLE"
    settlement = {
        "schema_version": SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": request_item["settlement_id"],
        "measurement_contract_ref": deepcopy(request_item["measurement_contract_ref"]),
        "prediction_id": prediction_item["prediction_id"],
        "observation_id": observation_item["observation_id"],
        "custodian_id": request_item["custodian_id"],
        "settled_at": request_item["settled_at"],
        "status": "MATCH" if prediction_item["predicted_direction"] == realised else "MISS",
        "object_class": "MINIMAL_HISTORICAL_MECHANICAL_SETTLEMENT",
        "claim_class": "ONE_METRIC_MECHANICAL_RESULT",
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "method_transfer_rights": NO_METHOD_TRANSFER_RIGHTS,
    }
    return _result([], settlement=settlement)
