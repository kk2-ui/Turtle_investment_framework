#!/usr/bin/env python3
"""Field-level acquisition from registered local official annual-report PDFs.

This module is deliberately narrower than settlement.  It reads an already
frozen Measurement Contract plus an already registered local static-PDF
inventory, then returns independent field observations.  It never receives a
forecast probability, realised label, price, CJO, report, or investment
object.  A field that cannot be mapped stays ``UNKNOWN`` or
``MEASUREMENT_MISMATCH``; it cannot stop unrelated fields in the same report.

The current catalogue covers the three consolidated financial statements and
segment/product revenue.  It is intentionally an explicit catalogue rather
than a best-effort search over arbitrary prose: the frozen contract's
``source_field_id`` is the sole instruction for what may be read.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path
import re
import subprocess
from typing import Any, Callable
from urllib.parse import urlparse

try:
    from scripts import judgment_pit_forecast as forecast
    from scripts import minimal_historical_episode as minimal
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_pit_forecast as forecast
    import minimal_historical_episode as minimal


SCHEMA_VERSION = "turtle-outcome-measurement-acquisition.v1"
INVENTORY_SCHEMA_VERSION = "turtle-outcome-measurement-static-pdf-inventory.v1"
OBJECT_CLASS = "OUTCOME_MEASUREMENT_ACQUISITION_RESULT"
INVENTORY_OBJECT_CLASS = "OUTCOME_MEASUREMENT_STATIC_PDF_INVENTORY"
CLAIM_CLASS = "CUSTODIAN_FIELD_ACQUISITION_ONLY"
INVENTORY_CLAIM_CLASS = "REGISTERED_LOCAL_OFFICIAL_ANNUAL_REPORTS_ONLY"
STATUSES = {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH"}
ENTERPRISE_CONTRACT_SCHEMA_VERSION = "enterprise-outcome-measurement-contract.v3"
ENTERPRISE_AUTHORIZATION_SCHEMA_VERSION = "enterprise-outcome-access-authorization.v1"
ENTERPRISE_CONTRACT_KIND = "ENTERPRISE_V3"
_PDF_PAGE_BREAK = "\f"
_NUMBER = re.compile(r"(?<![\d,])(?:-?\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)(?![\d,])")
_UNIT = re.compile(r"单\s*位\s*[:：]\s*(人民币)?\s*(元|万元|百万元|亿元)")
_STATIC_HOSTS = {"static.cninfo.com.cn", "static.sse.com.cn"}

PageReader = Callable[[Path], list[str]]


class OutcomeMeasurementAcquisitionError(ValueError):
    """The frozen input is not a legal local-PDF acquisition request."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _enterprise_cutoff(contract: dict[str, Any]) -> datetime | None:
    return _instant(contract.get("cutoff_at"))


def _enterprise_report_period(contract: dict[str, Any]) -> str | None:
    window = _mapping(contract.get("outcome_window"))
    period_end = window.get("period_end")
    return period_end[:10] if isinstance(period_end, str) and len(period_end) >= 10 else None


def _canonical_source_type(value: Any) -> str | None:
    source_type = _text(value)
    if source_type in {"OFFICIAL_ANNUAL_REPORT", "OFFICIAL_AUDITED_ANNUAL_REPORT"}:
        return "OFFICIAL_AUDITED_ANNUAL_REPORT"
    return source_type


def _availability_after_cutoff(document: dict[str, Any], *, cutoff: datetime, path: str) -> list[str]:
    findings: list[str] = []
    precision = document.get("availability_precision")
    if precision == "TIMESTAMP":
        available = _instant(document.get("source_available_at"))
        if available is not None and available <= cutoff:
            findings.append(path + ".source_available_must_follow_cutoff")
    elif precision == "DATE_ONLY":
        available_date = _date(document.get("source_available_date"))
        # A date-only publication has no intraday ordering.  Treat the whole
        # date as unavailable for a cutoff on that date.
        if available_date is not None and available_date <= cutoff.date():
            findings.append(path + ".source_available_date_must_follow_cutoff")
    return findings


def _source_available_before_observation(source: dict[str, Any], *, observed_at: datetime) -> bool:
    precision = source.get("availability_precision")
    if precision == "TIMESTAMP":
        available = _instant(source.get("source_available_at"))
        return available is None or observed_at <= available
    if precision == "DATE_ONLY":
        available_date = _date(source.get("source_available_date"))
        return available_date is None or observed_at.date() <= available_date
    return True


def _reference(contract: dict[str, Any]) -> dict[str, Any]:
    if contract.get("schema_version") == ENTERPRISE_CONTRACT_SCHEMA_VERSION:
        return {
            "measurement_contract_id": contract.get("contract_set_id"),
            "measurement_contract_version": 3,
        }
    return {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }


def _normalised_unit(value: Any) -> str | None:
    item = _text(value)
    if item is None:
        return None
    return {
        "RMB": "RMB", "CNY": "RMB", "人民币": "RMB", "人民币元": "RMB", "元": "RMB",
    }.get(item.upper() if item.isascii() else item, item)


def _allowed_outputs(contract_kind: str) -> list[str]:
    if contract_kind == "FORECAST":
        return ["FORECAST_OUTCOME_ACQUISITION_ONLY"]
    if contract_kind == ENTERPRISE_CONTRACT_KIND:
        return ["ENTERPRISE_OUTCOME_ACQUISITION_ONLY"]
    return ["MECHANICAL_SETTLEMENT_ONLY"]


def build_value_free_custody_projection(
    *,
    projection_id: str,
    company_id: str,
    custodian_id: str,
    cutoff_at: str,
    next_cutoff_at: str,
    measurement_contract_ref: dict[str, Any],
    authorized_source_identity: dict[str, Any],
    atomic_measurement_contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a value-free custodian view without opening any source.

    This public acquisition API intentionally accepts contract identities and
    atomic field definitions only.  It rejects forecast/judgment payloads and
    contains no local PDF path, result value, direction, probability or label.
    """
    required_source = {
        "source_id", "source_type", "official_url", "published_after_cutoff",
        "access_state", "custodian_access", "authorization_receipt_id",
        "issuer_id", "report_period_end", "availability_precision",
        "source_available_at", "source_available_date",
    }
    if not all(isinstance(value, str) and value for value in (projection_id, company_id, custodian_id, cutoff_at, next_cutoff_at)):
        raise OutcomeMeasurementAcquisitionError("custody_projection_identity_required")
    if not isinstance(measurement_contract_ref, dict) or set(measurement_contract_ref) != {"contract_set_id", "contract_version"}:
        raise OutcomeMeasurementAcquisitionError("custody_projection_contract_ref_invalid")
    if not isinstance(authorized_source_identity, dict) or set(authorized_source_identity) != required_source:
        raise OutcomeMeasurementAcquisitionError("custody_projection_source_identity_invalid")
    if authorized_source_identity.get("access_state") != "SEALED_UNTIL_PREOUTCOME_COMMIT":
        raise OutcomeMeasurementAcquisitionError("custody_projection_source_must_remain_sealed")
    if not isinstance(atomic_measurement_contracts, list) or not atomic_measurement_contracts:
        raise OutcomeMeasurementAcquisitionError("custody_projection_atomic_contracts_required")
    forbidden = {"forecast", "forecast_direction", "forecast_value", "probabilities", "hypotheses", "j2", "j3", "price", "cjo", "valuation", "report"}
    for index, cell in enumerate(atomic_measurement_contracts):
        if not isinstance(cell, dict) or forbidden.intersection(key.casefold() for key in cell):
            raise OutcomeMeasurementAcquisitionError(f"custody_projection.atomic_measurement_contracts[{index}]_contains_forbidden_field")
    return {
        "schema_version": "outcome-measurement-value-free-custody-projection.v1",
        "projection_id": projection_id,
        "company_id": company_id,
        "custodian_id": custodian_id,
        "cutoff_at": cutoff_at,
        "next_cutoff_at": next_cutoff_at,
        "measurement_contract_ref": deepcopy(measurement_contract_ref),
        "authorized_source_identity": deepcopy(authorized_source_identity),
        "atomic_measurement_contracts": deepcopy(atomic_measurement_contracts),
        "submission_api": "outcome_measurement_acquisition.validate_acquisition_result",
        "settlement_api": "outcome_measurement_settlement_adapter.register_acquisition_result",
        "outcome_access": {"authorized": False, "content_read": False, "custodian_started": False},
        "object_class": "VALUE_FREE_OUTCOME_CUSTODY_PROJECTION",
        "claim_class": "CUSTODIAN_ATOMIC_MEASUREMENT_ONLY",
        "allowed_outputs": ["CUSTODIAN_SUBMISSION_ONLY", "RESEARCH_AGENDA"],
    }


def _contract_context(contract: Any) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Normalise the project's frozen Measurement Contract shapes.

    Forecast contracts already carry independent cells.  Minimal contracts are
    one-cell contracts, so their exact identity is projected into a single
    acquisition field without widening the stored object.
    """
    forecast_result = forecast.validate_forecast_outcome_measurement_contract(contract)
    if forecast_result["valid"]:
        payload = forecast_result["measurement_contract"]
        return "FORECAST", payload, deepcopy(payload["cells"])

    minimal_result = minimal.validate_measurement_contract(contract)
    if minimal_result["valid"]:
        payload = minimal_result["measurement_contract"]
        return "MINIMAL", payload, [{
            "measurement_id": payload["metric_id"],
            "source_field_id": payload["metric_id"],
            "metric_definition": payload["metric_id"],
            "outcome_period_end": payload["outcome_period_end"],
            "responsibility_boundary": payload["responsibility_boundary"],
            "unit": payload["unit"],
            "official_source_type": "OFFICIAL_ANNUAL_REPORT",
        }]

    try:
        from scripts import enterprise_judgment_real_mechanism_training as enterprise
    except ModuleNotFoundError:  # pragma: no cover - direct script import
        import enterprise_judgment_real_mechanism_training as enterprise
    enterprise_result = enterprise.validate_outcome_measurement_contract(contract)
    if enterprise_result["valid"] and _mapping(contract).get("schema_version") == ENTERPRISE_CONTRACT_SCHEMA_VERSION:
        payload = enterprise_result["contract"]
        return ENTERPRISE_CONTRACT_KIND, payload, deepcopy(payload["atomic_cells"])

    raise OutcomeMeasurementAcquisitionError(
        "measurement_contract_invalid: "
        + "; ".join(
            forecast_result["findings"][:3]
            or minimal_result["findings"][:3]
            or enterprise_result["findings"][:3]
        )
    )


def _validate_enterprise_authorization(
    authorization: Any, *, contract: dict[str, Any], require_authorized: bool,
) -> dict[str, Any]:
    item = _mapping(authorization)
    required = {
        "schema_version", "authorization_receipt_id", "measurement_contract_ref", "company_id",
        "custodian_id", "source_id", "authorized", "content_read",
    }
    findings: list[str] = []
    if set(item) != required:
        findings.append("enterprise_authorization_shape_invalid")
    if item.get("schema_version") != ENTERPRISE_AUTHORIZATION_SCHEMA_VERSION:
        findings.append("enterprise_authorization_schema_invalid")
    if item.get("authorization_receipt_id") != _mapping(contract.get("source_access")).get("authorization_receipt_id"):
        findings.append("enterprise_authorization_receipt_mismatch")
    if item.get("measurement_contract_ref") != _reference(contract):
        findings.append("enterprise_authorization_contract_ref_mismatch")
    if item.get("company_id") != contract.get("company_id"):
        findings.append("enterprise_authorization_company_mismatch")
    if not _text(item.get("custodian_id")):
        findings.append("enterprise_authorization_custodian_required")
    if item.get("source_id") != _mapping(contract.get("source_access")).get("source_id"):
        findings.append("enterprise_authorization_source_mismatch")
    if require_authorized and item.get("authorized") is not True:
        findings.append("enterprise_outcome_access_not_authorized")
    if not isinstance(item.get("content_read"), bool):
        findings.append("enterprise_authorization_content_read_must_be_boolean")
    return {"valid": not findings, "findings": findings, "authorization": deepcopy(item) if not findings else None}


def validate_enterprise_outcome_access_authorization(
    authorization: Any, *, measurement_contract: Any, require_authorized: bool = True,
) -> dict[str, Any]:
    """Public contract-bound authorization check for acquisition and settlement."""
    contract_kind, contract, _ = _contract_context(measurement_contract)
    if contract_kind != ENTERPRISE_CONTRACT_KIND:
        return {"valid": False, "findings": ["enterprise_v3_contract_required"], "authorization": None}
    return _validate_enterprise_authorization(
        authorization, contract=contract, require_authorized=require_authorized,
    )


def _is_static_official_pdf(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc.casefold() in _STATIC_HOSTS and parsed.path.casefold().endswith(".pdf")


def validate_registered_local_pdf_inventory(
    inventory: Any, *, measurement_contract: Any, outcome_access_authorization: Any = None,
) -> dict[str, Any]:
    """Validate a closed, contract-bound local official-PDF inventory.

    This is a registration boundary, not a web acquisition client.  It accepts
    only already-local PDFs with static official URLs, so the reader cannot
    select a new issuer, web route, source version, or accounting period.
    """
    contract_kind, contract, _ = _contract_context(measurement_contract)
    findings: list[str] = []
    authorization: dict[str, Any] | None = None
    if contract_kind == ENTERPRISE_CONTRACT_KIND:
        authorization_result = _validate_enterprise_authorization(
            outcome_access_authorization, contract=contract, require_authorized=True,
        )
        findings.extend(authorization_result["findings"])
        authorization = authorization_result["authorization"]
    item = _mapping(inventory)
    allowed = {
        "schema_version", "inventory_id", "measurement_contract_ref", "custodian_id", "registered_at",
        "documents", "object_class", "claim_class", "allowed_outputs",
    }
    required = allowed
    if not isinstance(inventory, dict):
        findings.append("inventory_must_be_object")
    for field in sorted(set(item).difference(allowed)):
        findings.append(f"inventory_contains_unapproved_field:{field}")
    for field in sorted(required.difference(item)):
        findings.append(f"inventory_missing_required_field:{field}")
    if item.get("schema_version") != INVENTORY_SCHEMA_VERSION:
        findings.append("inventory_schema_version_invalid")
    if not _text(item.get("inventory_id")):
        findings.append("inventory_id_required")
    if item.get("measurement_contract_ref") != _reference(contract):
        findings.append("inventory_measurement_contract_ref_mismatch")
    if contract_kind == "FORECAST":
        expected_custodian = contract.get("custodian_id")
    elif contract_kind == ENTERPRISE_CONTRACT_KIND:
        expected_custodian = _mapping(authorization).get("custodian_id")
    else:
        expected_custodian = _mapping(contract.get("roles")).get("custodian_id")
    if item.get("custodian_id") != expected_custodian:
        findings.append("inventory_custodian_must_match_measurement_contract")
    if _instant(item.get("registered_at")) is None:
        findings.append("inventory_registered_at_must_be_timezone_aware")
    if item.get("object_class") != INVENTORY_OBJECT_CLASS:
        findings.append("inventory_object_class_invalid")
    if item.get("claim_class") != INVENTORY_CLAIM_CLASS:
        findings.append("inventory_claim_class_invalid")
    if item.get("allowed_outputs") != _allowed_outputs(contract_kind):
        findings.append("inventory_allowed_outputs_must_match_measurement_contract_lane")

    document_keys = {
        "source_id", "source_url", "local_pdf_path", "issuer_id", "responsibility_boundary",
        "report_period_end", "official_source_type", "report_scope", "currency", "revision_policy",
        "consolidation_or_restatement_note", "availability_precision", "source_available_at",
        "source_available_date",
    }
    source_ids: set[str] = set()
    documents: list[dict[str, Any]] = []
    cutoff = _enterprise_cutoff(contract) if contract_kind == ENTERPRISE_CONTRACT_KIND else None
    expected_report_period = _enterprise_report_period(contract) if contract_kind == ENTERPRISE_CONTRACT_KIND else None
    expected_source_type = _canonical_source_type(_mapping(contract.get("source_access")).get("source_type"))
    for index, raw in enumerate(_items(item.get("documents"))):
        document = _mapping(raw)
        path = f"inventory.documents[{index}]"
        for field in sorted(set(document).difference(document_keys)):
            findings.append(f"{path}_contains_unapproved_field:{field}")
        for field in sorted(document_keys.difference(document)):
            findings.append(f"{path}_missing_required_field:{field}")
        source_id = _text(document.get("source_id"))
        if source_id is None or source_id in source_ids:
            findings.append(f"{path}_source_id_missing_or_duplicate")
        else:
            source_ids.add(source_id)
        if not _is_static_official_pdf(document.get("source_url")):
            findings.append(f"{path}_source_url_must_be_static_official_pdf")
        local_path = _text(document.get("local_pdf_path"))
        if local_path is None or not Path(local_path).is_file() or Path(local_path).suffix.casefold() != ".pdf":
            findings.append(f"{path}_local_pdf_path_must_be_existing_pdf")
        elif not Path(local_path).read_bytes()[:4] == b"%PDF":
            findings.append(f"{path}_local_pdf_path_must_point_to_pdf_bytes")
        expected_issuer_id = contract.get("issuer_id")
        if contract_kind == ENTERPRISE_CONTRACT_KIND:
            expected_issuer_id = "ISSUER:" + str(contract.get("company_id"))
        if document.get("issuer_id") != expected_issuer_id:
            findings.append(f"{path}_issuer_id_must_match_measurement_contract")
        if not _text(document.get("responsibility_boundary")):
            findings.append(f"{path}_responsibility_boundary_required")
        if _date(document.get("report_period_end")) is None:
            findings.append(f"{path}_report_period_end_invalid")
        if document.get("official_source_type") != "OFFICIAL_ANNUAL_REPORT":
            if document.get("official_source_type") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
                findings.append(f"{path}_official_source_type_must_be_annual_report")
        if document.get("report_scope") != "ISSUER_FILING":
            findings.append(f"{path}_report_scope_must_be_issuer_filing")
        if _normalised_unit(document.get("currency")) is None:
            findings.append(f"{path}_currency_invalid")
        if document.get("revision_policy") != "ORIGINAL_VINTAGE":
            findings.append(f"{path}_revision_policy_must_be_original_vintage")
        if not _text(document.get("consolidation_or_restatement_note")):
            findings.append(f"{path}_consolidation_or_restatement_note_required")
        precision = document.get("availability_precision")
        if precision == "TIMESTAMP":
            if _instant(document.get("source_available_at")) is None:
                findings.append(f"{path}_timestamp_source_available_at_must_be_timezone_aware")
            if document.get("source_available_date") is not None:
                findings.append(f"{path}_timestamp_cannot_include_source_available_date")
        elif precision == "DATE_ONLY":
            if _date(document.get("source_available_date")) is None:
                findings.append(f"{path}_date_only_source_available_date_invalid")
            if document.get("source_available_at") is not None:
                findings.append(f"{path}_date_only_cannot_include_source_available_at")
        else:
            findings.append(f"{path}_availability_precision_must_be_timestamp_or_date_only")
        if cutoff is not None:
            findings.extend(_availability_after_cutoff(document, cutoff=cutoff, path=path))
        if expected_report_period is not None and document.get("report_period_end") != expected_report_period:
            findings.append(f"{path}_report_period_must_match_enterprise_outcome_source")
        if contract_kind == ENTERPRISE_CONTRACT_KIND and _canonical_source_type(document.get("official_source_type")) != expected_source_type:
            findings.append(f"{path}_official_source_type_must_match_enterprise_contract")
        if contract_kind == ENTERPRISE_CONTRACT_KIND and authorization is not None:
            if document.get("source_id") != authorization.get("source_id"):
                findings.append(f"{path}_source_id_must_match_enterprise_authorization")
            if document.get("source_url") != _mapping(contract.get("source_access")).get("official_url"):
                findings.append(f"{path}_source_url_must_match_enterprise_contract")
        documents.append(deepcopy(document))
    if not documents:
        findings.append("inventory_documents_must_be_nonempty")
    return {"valid": not findings, "findings": findings, "inventory": deepcopy(item) if not findings else None}


def _pdf_pages(local_path: Path) -> list[str]:
    completed = subprocess.run(
        ["pdftotext", "-layout", str(local_path), "-"],
        check=True, capture_output=True, text=True,
    )
    pages = completed.stdout.split(_PDF_PAGE_BREAK)
    return pages[:-1] if pages and not pages[-1].strip() else pages


def _field_spec(source_field_id: str) -> dict[str, Any] | None:
    catalogue = {
        "CONSOLIDATED_REVENUE_RMB": {
            "statement_kind": "CONSOLIDATED_INCOME_STATEMENT", "scope": "CONSOLIDATED",
            "markers": ("合并利润表", "合并损益表"), "labels": ("其中：营业收入",),
        },
        "CONSOLIDATED_TOTAL_ASSETS_RMB": {
            "statement_kind": "CONSOLIDATED_BALANCE_SHEET", "scope": "CONSOLIDATED",
            "markers": ("合并资产负债表",), "labels": ("资产总计",),
        },
        "CONSOLIDATED_OPERATING_CASH_FLOW_RMB": {
            "statement_kind": "CONSOLIDATED_CASH_FLOW_STATEMENT", "scope": "CONSOLIDATED",
            "markers": ("合并现金流量表",), "labels": ("经营活动产生的现金流量净额",),
        },
        "PARENT_REVENUE_RMB": {
            "statement_kind": "PARENT_INCOME_STATEMENT", "scope": "PARENT",
            "markers": ("母公司利润表", "母公司损益表"), "labels": ("一、营业收入",),
        },
        "PARENT_TOTAL_ASSETS_RMB": {
            "statement_kind": "PARENT_BALANCE_SHEET", "scope": "PARENT",
            "markers": ("母公司资产负债表",), "labels": ("资产总计",),
        },
        "PARENT_OPERATING_CASH_FLOW_RMB": {
            "statement_kind": "PARENT_CASH_FLOW_STATEMENT", "scope": "PARENT",
            "markers": ("母公司现金流量表",), "labels": ("经营活动产生的现金流量净额",),
        },
    }
    if source_field_id in catalogue:
        return deepcopy(catalogue[source_field_id])
    for prefix, marker in (("SEGMENT_REVENUE_RMB:", "分部"), ("PRODUCT_REVENUE_RMB:", "分产品")):
        if source_field_id.startswith(prefix) and _text(source_field_id[len(prefix):]):
            return {
                "statement_kind": "SEGMENT_OR_PRODUCT_OPERATIONAL_DATA", "scope": "CONSOLIDATED",
                "markers": (marker,), "labels": (source_field_id[len(prefix):],),
            }
    return None


def _page_unit_scale(page: str) -> tuple[str, Decimal] | None:
    match = _UNIT.search(page)
    if match is None:
        return None
    unit = match.group(2)
    return "RMB", {"元": Decimal("1"), "万元": Decimal("10000"), "百万元": Decimal("1000000"), "亿元": Decimal("100000000")}[unit]


def _numeric_values(line: str) -> list[Decimal]:
    values: list[Decimal] = []
    for token in _NUMBER.findall(line):
        try:
            value = Decimal(token.replace(",", "").replace("，", ""))
        except InvalidOperation:  # pragma: no cover - token regex constrains shape
            continue
        if value.is_finite():
            values.append(value)
    return values


def _field_rows(pages: list[str], spec: dict[str, Any]) -> list[tuple[int, str, Decimal, Decimal, tuple[str, Decimal] | None]]:
    matches: list[tuple[int, str, Decimal, Decimal, tuple[str, Decimal] | None]] = []
    for page_number, page in enumerate(pages, start=1):
        if not any(marker in page for marker in spec["markers"]):
            continue
        lines = page.splitlines()
        for position, line in enumerate(lines):
            if not any(label in line for label in spec["labels"]):
                continue
            candidate = " ".join(lines[position:position + 3])
            values = _numeric_values(candidate)
            if len(values) >= 2:
                # Accounting note identifiers precede the actual current and
                # comparative columns (for example ``附注七(42)``).  The two
                # right-most numeric tokens in the matched statement row are
                # the columns frozen by this narrow source-field catalogue.
                matches.append((page_number, candidate, values[-2], values[-1], _page_unit_scale(page)))
    return matches


def _source_identity(document: dict[str, Any], *, page_number: int | None = None) -> dict[str, Any]:
    result = {
        "source_id": document["source_id"],
        "source_url": document["source_url"],
        "report_period_end": document["report_period_end"],
        "official_source_type": document["official_source_type"],
        "issuer_id": document["issuer_id"],
        "responsibility_boundary": document["responsibility_boundary"],
        "availability_precision": document["availability_precision"],
    }
    if document["availability_precision"] == "TIMESTAMP":
        result["source_available_at"] = document["source_available_at"]
    else:
        result["source_available_date"] = document["source_available_date"]
    if page_number is not None:
        result["pdf_page"] = page_number
        result["field_ref"] = f"PDF p.{page_number}"
    return result


def _contract_requires_consolidated(cell: dict[str, Any]) -> bool:
    boundary = str(cell.get("responsibility_boundary") or "").upper()
    return "CONSOLIDATED" in boundary


def _unknown(cell: dict[str, Any], documents: list[dict[str, Any]], *, reason: str) -> dict[str, Any]:
    return {
        "measurement_id": cell["measurement_id"], "status": "UNKNOWN", "metric_id": cell["source_field_id"],
        "metric_definition": cell["metric_definition"], "report_period_end": cell["outcome_period_end"],
        "unit": cell["unit"], "currency": None, "reporting_scope": None,
        "sources_considered": [_source_identity(document) for document in documents],
        "reason": reason,
    }


def _mismatch(
    cell: dict[str, Any], document: dict[str, Any] | None, *, reason: str,
    page_number: int | None = None, statement_kind: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "measurement_id": cell["measurement_id"], "status": "MEASUREMENT_MISMATCH", "metric_id": cell["source_field_id"],
        "metric_definition": cell["metric_definition"], "report_period_end": cell["outcome_period_end"],
        "unit": cell["unit"], "currency": _normalised_unit(document.get("currency")) if document else None,
        "reporting_scope": None, "reason": reason,
    }
    if document is not None:
        result["source"] = _source_identity(document, page_number=page_number)
        result["consolidation_or_restatement_note"] = document["consolidation_or_restatement_note"]
    if statement_kind is not None:
        result["statement_kind"] = statement_kind
    return result


def _observe_cell(
    cell: dict[str, Any], *, documents: list[dict[str, Any]], page_reader: PageReader,
) -> dict[str, Any]:
    source_field_id = str(cell["source_field_id"])
    spec = _field_spec(source_field_id)
    period = str(cell["outcome_period_end"])
    candidates = [document for document in documents if document["report_period_end"] == period]
    if spec is None:
        return _unknown(cell, candidates, reason="SOURCE_FIELD_ID_NOT_SUPPORTED_BY_LOCAL_ANNUAL_REPORT_CATALOGUE")
    if not candidates:
        return _unknown(cell, [], reason="NO_REGISTERED_ANNUAL_REPORT_FOR_MEASUREMENT_PERIOD")
    all_rows: list[tuple[dict[str, Any], int, str, Decimal, Decimal, tuple[str, Decimal] | None]] = []
    for document in candidates:
        if document["responsibility_boundary"] != cell["responsibility_boundary"]:
            continue
        try:
            pages = page_reader(Path(document["local_pdf_path"]))
        except (OSError, subprocess.SubprocessError):
            return _mismatch(cell, document, reason="LOCAL_OFFICIAL_PDF_TEXT_EXTRACTION_FAILED")
        for page_number, line, current, comparative, unit_info in _field_rows(pages, spec):
            all_rows.append((document, page_number, line, current, comparative, unit_info))
    if not all_rows:
        return _unknown(cell, candidates, reason="FIELD_NOT_PRESENT_IN_REGISTERED_REPORT_STATEMENT")
    if len(all_rows) != 1:
        document, page_number, *_ = all_rows[0]
        return _mismatch(
            cell, document, page_number=page_number, statement_kind=spec["statement_kind"],
            reason="NON_UNIQUE_DIRECT_FIELD_IN_REGISTERED_REPORTS",
        )
    document, page_number, _line, current, comparative, unit_info = all_rows[0]
    if spec["scope"] != "CONSOLIDATED" and _contract_requires_consolidated(cell):
        return _mismatch(
            cell, document, page_number=page_number, statement_kind=spec["statement_kind"],
            reason="ACCOUNTING_SCOPE_MISMATCH_PARENT_FIELD_CANNOT_SETTLE_CONSOLIDATED_CONTRACT",
        )
    if unit_info is None:
        return _mismatch(
            cell, document, page_number=page_number, statement_kind=spec["statement_kind"],
            reason="UNIT_NOT_DISCLOSED_ON_LOCATED_STATEMENT_PAGE",
        )
    currency, scale = unit_info
    if _normalised_unit(cell["unit"]) != currency or _normalised_unit(document["currency"]) != currency:
        return _mismatch(
            cell, document, page_number=page_number, statement_kind=spec["statement_kind"],
            reason="UNIT_OR_CURRENCY_DOES_NOT_MATCH_FROZEN_MEASUREMENT_CONTRACT",
        )
    current_value, comparative_value = current * scale, comparative * scale
    if not current_value.is_finite() or not comparative_value.is_finite():  # defensive numeric contract, not a fallback
        return _mismatch(
            cell, document, page_number=page_number, statement_kind=spec["statement_kind"],
            reason="LOCATED_STATEMENT_VALUES_ARE_NOT_FINITE",
        )
    return {
        "measurement_id": cell["measurement_id"], "status": "OBSERVED", "metric_id": source_field_id,
        "metric_definition": cell["metric_definition"], "report_period_end": period,
        "unit": cell["unit"], "currency": currency, "reporting_scope": spec["scope"],
        "statement_kind": spec["statement_kind"], "current_value": float(current_value),
        "comparative_value": float(comparative_value), "source": _source_identity(document, page_number=page_number),
        "consolidation_or_restatement_note": document["consolidation_or_restatement_note"],
    }


def _enterprise_field_rows(
    pages: list[str], field_id: str,
) -> list[tuple[int, str, str]]:
    """Read the explicit field-id fixture format used by a registered extractor.

    Production PDF extraction may supply the same page strings after locating a
    table row.  The adapter still requires the frozen field identity verbatim;
    it never guesses a nearby line item.
    """
    rows: list[tuple[int, str, str]] = []
    for page_number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) == 3 and parts[0] == field_id:
                rows.append((page_number, parts[1], parts[2]))
    return rows


def _enterprise_raw_observation(
    raw_field: dict[str, Any], *, cell: dict[str, Any], documents: list[dict[str, Any]], page_reader: PageReader,
) -> dict[str, Any]:
    base = {
        "field_id": raw_field["field_id"],
        "measurement_clock": deepcopy(raw_field["measurement_clock"]),
        "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
        "unit": raw_field["unit"],
    }
    if not documents:
        return {
            **base, "status": "UNKNOWN", "reason": "NO_AUTHORIZED_ANNUAL_REPORT_FOR_ENTERPRISE_CONTRACT",
            "sources_considered": [],
        }
    rows: list[tuple[dict[str, Any], int, str, str]] = []
    for document in documents:
        try:
            pages = page_reader(Path(document["local_pdf_path"]))
        except (OSError, subprocess.SubprocessError):
            return {
                **base, "status": "MEASUREMENT_MISMATCH", "reason": "LOCAL_OFFICIAL_PDF_TEXT_EXTRACTION_FAILED",
                "source": _source_identity(document),
            }
        for page_number, raw_value, disclosed_unit in _enterprise_field_rows(pages, raw_field["field_id"]):
            rows.append((document, page_number, raw_value, disclosed_unit))
    if not rows:
        return {
            **base, "status": "UNKNOWN", "reason": "FROZEN_RAW_FIELD_NOT_FOUND_IN_AUTHORIZED_SOURCE",
            "sources_considered": [_source_identity(document) for document in documents],
        }
    if len(rows) != 1:
        document, page_number, *_ = rows[0]
        return {
            **base, "status": "MEASUREMENT_MISMATCH", "reason": "NON_UNIQUE_FROZEN_RAW_FIELD",
            "source": _source_identity(document, page_number=page_number),
        }
    document, page_number, value_token, disclosed_unit = rows[0]
    source = _source_identity(document, page_number=page_number)
    source["field_identity"] = raw_field["field_id"]
    source["measurement_clock"] = deepcopy(raw_field["measurement_clock"])
    source["responsibility_boundary"] = deepcopy(cell["responsibility_boundary"])
    source["unit"] = raw_field["unit"]
    source.update(deepcopy(raw_field["locator"]))
    if disclosed_unit != raw_field["unit"]:
        return {
            **base, "status": "MEASUREMENT_MISMATCH", "reason": "RAW_FIELD_UNIT_DOES_NOT_MATCH_FROZEN_CONTRACT",
            "source": source,
        }
    if raw_field.get("role") == "EVENT":
        if value_token == "EVENT_TRUE":
            value: bool | float = True
        elif value_token == "EVENT_FALSE":
            value = False
        else:
            return {
                **base, "status": "UNKNOWN", "reason": "EVENT_HAS_NO_EXPLICIT_POSITIVE_OR_NEGATIVE_EVIDENCE",
                "sources_considered": [source],
            }
    else:
        try:
            parsed = Decimal(value_token.replace(",", ""))
        except InvalidOperation:
            return {
                **base, "status": "MEASUREMENT_MISMATCH", "reason": "RAW_FIELD_VALUE_IS_NOT_NUMERIC",
                "source": source,
            }
        if not parsed.is_finite():
            return {
                **base, "status": "MEASUREMENT_MISMATCH", "reason": "RAW_FIELD_VALUE_IS_NOT_FINITE",
                "source": source,
            }
        value = float(parsed)
    return {**base, "status": "OBSERVED", "raw_value": value, "source": source}


def _observe_enterprise_cell(
    cell: dict[str, Any], *, documents: list[dict[str, Any]], page_reader: PageReader,
) -> dict[str, Any]:
    raw_observations = [
        _enterprise_raw_observation(raw, cell=cell, documents=documents, page_reader=page_reader)
        for raw in cell["raw_input_fields"]
    ]
    statuses = {item["status"] for item in raw_observations}
    if "MEASUREMENT_MISMATCH" in statuses:
        status, reason = "MEASUREMENT_MISMATCH", "ONE_OR_MORE_RAW_FIELDS_MISMATCH_THE_FROZEN_CELL"
    elif "UNKNOWN" in statuses:
        status, reason = "UNKNOWN", "ONE_OR_MORE_RAW_FIELDS_REMAIN_UNKNOWN"
    else:
        status, reason = "OBSERVED", None
    result = {
        "measurement_id": cell["cell_id"],
        "status": status,
        "raw_field_observations": raw_observations,
    }
    if reason is not None:
        result["reason"] = reason
    return result


def _validate_enterprise_field_record(
    record: Any, *, cell: dict[str, Any], raw_field: dict[str, Any],
    documents: list[dict[str, Any]], contract: dict[str, Any],
) -> dict[str, Any]:
    """Validate one custodian-located raw field record.

    This is the supported Enterprise production protocol.  The custodian may
    use any PDF tooling, but Turtle receives only a page-located record and
    verifies every identity against the frozen catalog and inventory.
    """
    item = _mapping(record)
    required = {"cell_id", "field_id", "status", "measurement_clock", "responsibility_boundary", "unit"}
    findings: list[str] = []
    if set(item).difference(required | {"raw_value", "source", "reason", "sources_considered"}):
        findings.append("field_record_contains_unapproved_field")
    if set(item).intersection(required) != required:
        findings.append("field_record_identity_incomplete")
    if item.get("cell_id") != cell["cell_id"] or item.get("field_id") != raw_field["field_id"]:
        findings.append("field_record_cell_or_field_identity_mismatch")
    if item.get("measurement_clock") != raw_field["measurement_clock"]:
        findings.append("field_record_clock_mismatch")
    if item.get("responsibility_boundary") != cell["responsibility_boundary"]:
        findings.append("field_record_boundary_mismatch")
    if item.get("unit") != raw_field["unit"]:
        findings.append("field_record_unit_mismatch")
    status = item.get("status")
    if status not in STATUSES:
        findings.append("field_record_status_invalid")
    if status == "OBSERVED":
        if set(item) != required | {"raw_value", "source"}:
            findings.append("field_record_observed_shape_invalid")
        value = item.get("raw_value")
        if raw_field.get("role") == "EVENT":
            if not isinstance(value, bool):
                findings.append("field_record_event_value_must_be_boolean")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            findings.append("field_record_numeric_value_must_be_finite")
    elif status == "UNKNOWN":
        if set(item) != required | {"reason", "sources_considered"} or not _text(item.get("reason")):
            findings.append("field_record_unknown_shape_invalid")
    elif status == "MEASUREMENT_MISMATCH":
        if set(item) != required | {"reason", "source"} or not _text(item.get("reason")):
            findings.append("field_record_mismatch_shape_invalid")

    source = _mapping(item.get("source"))
    if status in {"OBSERVED", "MEASUREMENT_MISMATCH"}:
        if not documents:
            findings.append("field_record_source_document_missing")
        else:
            document = documents[0]
            source_identity = _source_identity(document)
            for key in ("source_id", "source_url", "issuer_id", "report_period_end", "availability_precision"):
                if source.get(key) != source_identity.get(key):
                    findings.append(f"field_record_source_{key}_mismatch")
            if _canonical_source_type(source.get("official_source_type")) != _canonical_source_type(document.get("official_source_type")):
                findings.append("field_record_source_official_source_type_mismatch")
            if source.get("responsibility_boundary") != cell["responsibility_boundary"]:
                findings.append("field_record_source_boundary_mismatch")
            if source.get("field_identity") != raw_field["field_id"]:
                findings.append("field_record_source_field_identity_mismatch")
            if source.get("measurement_clock") != raw_field["measurement_clock"]:
                findings.append("field_record_source_clock_mismatch")
            if source.get("unit") != raw_field["unit"]:
                findings.append("field_record_source_unit_mismatch")
            locator = _mapping(raw_field.get("locator"))
            for key in ("table_or_note", "line_item", "period_column"):
                if source.get(key) != locator.get(key):
                    findings.append(f"field_record_source_{key}_locator_mismatch")
            page = source.get("pdf_page")
            if not isinstance(page, int) or page < 1 or source.get("field_ref") != f"PDF p.{page}":
                findings.append("field_record_source_page_binding_invalid")
            if document.get("availability_precision") == "TIMESTAMP" and source.get("source_available_at") != document.get("source_available_at"):
                findings.append("field_record_source_available_at_mismatch")
            if document.get("availability_precision") == "DATE_ONLY" and source.get("source_available_date") != document.get("source_available_date"):
                findings.append("field_record_source_available_date_mismatch")
    return {"valid": not findings, "findings": findings, "record": deepcopy(item) if not findings else None}


def acquire_outcome_measurements_from_field_records(
    measurement_contract: dict[str, Any], inventory: dict[str, Any], field_records: Any,
    *, outcome_access_authorization: Any,
) -> dict[str, Any]:
    """Build an Enterprise result from custodian-located field records.

    No PDF is opened here.  This explicit boundary means the system does not
    claim automatic PDF extraction; the public contract is strict validation
    of the custodian's 31 located records.
    """
    contract_kind, contract, cells = _contract_context(measurement_contract)
    if contract_kind != ENTERPRISE_CONTRACT_KIND:
        raise OutcomeMeasurementAcquisitionError("field_records_require_enterprise_v3_contract")
    if not isinstance(field_records, list):
        raise OutcomeMeasurementAcquisitionError("field_records_must_be_list")
    expected = [(cell["cell_id"], raw["field_id"]) for cell in cells for raw in cell["raw_input_fields"]]
    supplied = [(record.get("cell_id"), record.get("field_id")) for record in field_records if isinstance(record, dict)]
    if supplied != expected or len(supplied) != len(expected) or len(set(supplied)) != len(expected):
        raise OutcomeMeasurementAcquisitionError("field_records_must_exactly_cover_frozen_cells_and_raw_inputs_in_order")
    by_pair = {(record["cell_id"], record["field_id"]): record for record in field_records}
    observations: list[dict[str, Any]] = []
    for cell in cells:
        raw_observations: list[dict[str, Any]] = []
        for raw_field in cell["raw_input_fields"]:
            validation = _validate_enterprise_field_record(
                by_pair[(cell["cell_id"], raw_field["field_id"])],
                cell=cell, raw_field=raw_field, documents=inventory["documents"], contract=contract,
            )
            if not validation["valid"]:
                raise OutcomeMeasurementAcquisitionError(
                    "field_record_invalid: " + "; ".join(validation["findings"])
                )
            record = validation["record"]
            raw_observations.append({
                key: deepcopy(record[key])
                for key in set(record).intersection({
                    "field_id", "status", "measurement_clock", "responsibility_boundary", "unit",
                    "raw_value", "source", "reason", "sources_considered",
                })
            })
        statuses = {raw["status"] for raw in raw_observations}
        status = (
            "MEASUREMENT_MISMATCH" if "MEASUREMENT_MISMATCH" in statuses
            else "UNKNOWN" if "UNKNOWN" in statuses else "OBSERVED"
        )
        observation: dict[str, Any] = {
            "measurement_id": cell["cell_id"],
            "status": status,
            "raw_field_observations": raw_observations,
        }
        if status != "OBSERVED":
            observation["reason"] = "ONE_OR_MORE_RAW_FIELDS_REMAIN_" + status
        observations.append(observation)
    return {
        "schema_version": SCHEMA_VERSION,
        "measurement_contract_ref": _reference(contract),
        "source_inventory_id": inventory["inventory_id"],
        "custodian_id": inventory["custodian_id"],
        "object_class": OBJECT_CLASS,
        "claim_class": CLAIM_CLASS,
        "allowed_outputs": _allowed_outputs(ENTERPRISE_CONTRACT_KIND),
        "observations": observations,
        "contract_kind": ENTERPRISE_CONTRACT_KIND,
        "authorization_receipt_id": _mapping(outcome_access_authorization).get("authorization_receipt_id"),
    }


def acquire_outcome_measurements(
    measurement_contract: Any,
    registered_pdf_inventory: Any,
    *,
    measurement_ids: list[str] | None = None,
    page_reader: PageReader = _pdf_pages,
    outcome_access_authorization: Any = None,
    field_records: Any = None,
) -> dict[str, Any]:
    """Acquire independent field observations from registered local PDFs.

    ``measurement_ids`` can only reduce the frozen contract's cells; it cannot
    introduce a field.  The call is pure and has no persistence or downstream
    settlement side effect.
    """
    contract_kind, contract, cells = _contract_context(measurement_contract)
    inventory_result = validate_registered_local_pdf_inventory(
        registered_pdf_inventory,
        measurement_contract=contract,
        outcome_access_authorization=outcome_access_authorization,
    )
    if not inventory_result["valid"]:
        raise OutcomeMeasurementAcquisitionError("registered_pdf_inventory_invalid: " + "; ".join(inventory_result["findings"]))
    inventory = inventory_result["inventory"]
    id_field = "cell_id" if contract_kind == ENTERPRISE_CONTRACT_KIND else "measurement_id"
    by_id = {str(cell[id_field]): cell for cell in cells}
    if measurement_ids is None:
        selected = list(cells)
    else:
        if contract_kind == ENTERPRISE_CONTRACT_KIND:
            raise OutcomeMeasurementAcquisitionError("enterprise_acquisition_must_cover_all_frozen_cells")
        if not isinstance(measurement_ids, list) or not measurement_ids or any(not _text(value) for value in measurement_ids):
            raise OutcomeMeasurementAcquisitionError("measurement_ids_must_be_nonempty_text_list_when_supplied")
        if len(set(measurement_ids)) != len(measurement_ids) or any(value not in by_id for value in measurement_ids):
            raise OutcomeMeasurementAcquisitionError("measurement_ids_must_be_unique_frozen_measurement_ids")
        selected = [by_id[value] for value in measurement_ids]
    if contract_kind == ENTERPRISE_CONTRACT_KIND:
        if field_records is not None:
            return acquire_outcome_measurements_from_field_records(
                contract, inventory, field_records,
                outcome_access_authorization=outcome_access_authorization,
            )
        observations = [
            _observe_enterprise_cell(cell, documents=inventory["documents"], page_reader=page_reader)
            for cell in selected
        ]
    else:
        observations = [_observe_cell(cell, documents=inventory["documents"], page_reader=page_reader) for cell in selected]
    result = {
        "schema_version": SCHEMA_VERSION,
        "measurement_contract_ref": _reference(contract),
        "source_inventory_id": inventory["inventory_id"],
        "custodian_id": inventory["custodian_id"],
        "object_class": OBJECT_CLASS,
        "claim_class": CLAIM_CLASS,
        "allowed_outputs": _allowed_outputs(contract_kind),
        "observations": observations,
    }
    if contract_kind == ENTERPRISE_CONTRACT_KIND:
        authorization = _mapping(outcome_access_authorization)
        result["contract_kind"] = ENTERPRISE_CONTRACT_KIND
        result["authorization_receipt_id"] = authorization.get("authorization_receipt_id")
    return result


def _validate_enterprise_acquisition_result(
    result: Any, *, measurement_contract: Any, outcome_access_authorization: Any,
) -> dict[str, Any]:
    findings: list[str] = []
    try:
        contract_kind, contract, cells = _contract_context(measurement_contract)
    except OutcomeMeasurementAcquisitionError as exc:
        return {"valid": False, "findings": [str(exc)], "result": None}
    if contract_kind != ENTERPRISE_CONTRACT_KIND:
        return {"valid": False, "findings": ["enterprise_acquisition_requires_enterprise_v3_contract"], "result": None}
    authorization_result = _validate_enterprise_authorization(
        outcome_access_authorization, contract=contract, require_authorized=True,
    )
    findings.extend(authorization_result["findings"])
    authorization = _mapping(authorization_result.get("authorization"))
    item = _mapping(result)
    root_keys = {
        "schema_version", "measurement_contract_ref", "source_inventory_id", "custodian_id",
        "object_class", "claim_class", "allowed_outputs", "observations", "contract_kind",
        "authorization_receipt_id",
    }
    if set(item) != root_keys:
        findings.append("enterprise_acquisition_result_shape_invalid")
    if item.get("schema_version") != SCHEMA_VERSION:
        findings.append("result_schema_version_invalid")
    if item.get("object_class") != OBJECT_CLASS or item.get("claim_class") != CLAIM_CLASS:
        findings.append("result_identity_invalid")
    if item.get("measurement_contract_ref") != _reference(contract):
        findings.append("enterprise_acquisition_contract_ref_mismatch")
    if item.get("authorization_receipt_id") != authorization.get("authorization_receipt_id"):
        findings.append("enterprise_acquisition_authorization_receipt_mismatch")
    if item.get("custodian_id") != authorization.get("custodian_id"):
        findings.append("enterprise_acquisition_custodian_mismatch")
    if item.get("allowed_outputs") != _allowed_outputs(ENTERPRISE_CONTRACT_KIND):
        findings.append("enterprise_acquisition_allowed_outputs_invalid")
    observations = _items(item.get("observations"))
    by_cell: dict[str, dict[str, Any]] = {}
    for index, raw_observation in enumerate(observations):
        observation = _mapping(raw_observation)
        measurement_id = observation.get("measurement_id")
        if not isinstance(measurement_id, str) or measurement_id in by_cell:
            findings.append(f"enterprise_acquisition.observations[{index}].cell_id_missing_or_duplicate")
        else:
            by_cell[measurement_id] = observation
    expected_cell_ids = [cell["cell_id"] for cell in cells]
    if set(by_cell) != set(expected_cell_ids) or len(observations) != len(expected_cell_ids):
        findings.append("enterprise_acquisition_must_cover_each_frozen_cell_once")
    source_access = _mapping(contract.get("source_access"))
    for cell_index, cell in enumerate(cells):
        observation = _mapping(by_cell.get(cell["cell_id"]))
        path = f"enterprise_acquisition.cells[{cell_index}]"
        status = observation.get("status")
        if status not in STATUSES:
            findings.append(path + ".status_invalid")
        allowed_cell_keys = {"measurement_id", "status", "raw_field_observations"}
        if status != "OBSERVED":
            allowed_cell_keys.add("reason")
            if not _text(observation.get("reason")):
                findings.append(path + ".reason_required")
        if set(observation) != allowed_cell_keys:
            findings.append(path + ".shape_invalid")
        raw_observations = _items(observation.get("raw_field_observations"))
        by_field: dict[str, dict[str, Any]] = {}
        for raw_index, raw_value in enumerate(raw_observations):
            raw_item = _mapping(raw_value)
            field_id = raw_item.get("field_id")
            if not isinstance(field_id, str) or field_id in by_field:
                findings.append(f"{path}.raw_fields[{raw_index}].field_id_missing_or_duplicate")
            else:
                by_field[field_id] = raw_item
        frozen_raws = cell["raw_input_fields"]
        expected_raw_ids = [raw["field_id"] for raw in frozen_raws]
        if set(by_field) != set(expected_raw_ids) or len(raw_observations) != len(expected_raw_ids):
            findings.append(path + ".must_cover_each_frozen_raw_input_once")
        raw_statuses: set[str] = set()
        for raw_index, frozen_raw in enumerate(frozen_raws):
            raw_item = _mapping(by_field.get(frozen_raw["field_id"]))
            raw_path = f"{path}.raw_fields[{raw_index}]"
            raw_status = raw_item.get("status")
            raw_statuses.add(str(raw_status))
            common = {"field_id", "status", "measurement_clock", "responsibility_boundary", "unit"}
            if raw_status == "OBSERVED":
                expected_keys = common | {"raw_value", "source"}
            elif raw_status == "UNKNOWN":
                expected_keys = common | {"reason", "sources_considered"}
            elif raw_status == "MEASUREMENT_MISMATCH":
                expected_keys = common | {"reason", "source"}
            else:
                expected_keys = common
                findings.append(raw_path + ".status_invalid")
            if set(raw_item) != expected_keys:
                findings.append(raw_path + ".shape_invalid")
            for field, expected in (
                ("measurement_clock", frozen_raw["measurement_clock"]),
                ("responsibility_boundary", cell["responsibility_boundary"]),
                ("unit", frozen_raw["unit"]),
            ):
                if raw_item.get(field) != expected:
                    findings.append(f"{raw_path}.{field}_must_match_frozen_raw_input")
            if raw_status in {"OBSERVED", "MEASUREMENT_MISMATCH"}:
                value = raw_item.get("raw_value")
                if frozen_raw.get("role") == "EVENT":
                    if raw_status == "OBSERVED" and not isinstance(value, bool):
                        findings.append(raw_path + ".event_raw_value_must_be_explicit_boolean")
                elif raw_status == "OBSERVED" and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value))):
                    findings.append(raw_path + ".numeric_raw_value_must_be_finite")
                source = _mapping(raw_item.get("source"))
                if source.get("source_id") != source_access.get("source_id") or source.get("source_url") != source_access.get("official_url"):
                    findings.append(raw_path + ".source_must_match_authorized_identity")
                if not _is_static_official_pdf(source.get("source_url")):
                    findings.append(raw_path + ".source_url_must_be_static_official_pdf")
                if source.get("issuer_id") != "ISSUER:" + str(contract.get("company_id")):
                    findings.append(raw_path + ".source_issuer_must_match_contract_company")
                if source.get("report_period_end") != _enterprise_report_period(contract):
                    findings.append(raw_path + ".source_report_period_must_match_contract")
                if _canonical_source_type(source.get("official_source_type")) != _canonical_source_type(source_access.get("source_type")):
                    findings.append(raw_path + ".source_official_source_type_must_match_contract")
                precision = source.get("availability_precision")
                if precision == "TIMESTAMP":
                    if _instant(source.get("source_available_at")) is None or source.get("source_available_date") is not None:
                        findings.append(raw_path + ".source_timestamp_availability_invalid")
                elif precision == "DATE_ONLY":
                    if _date(source.get("source_available_date")) is None or source.get("source_available_at") is not None:
                        findings.append(raw_path + ".source_date_only_availability_invalid")
                else:
                    findings.append(raw_path + ".source_availability_precision_invalid")
                if source.get("field_identity") != frozen_raw["field_id"]:
                    findings.append(raw_path + ".source_field_identity_must_match_frozen_raw_input")
                if source.get("measurement_clock") != frozen_raw["measurement_clock"]:
                    findings.append(raw_path + ".source_clock_must_match_frozen_raw_input")
                if source.get("responsibility_boundary") != cell["responsibility_boundary"]:
                    findings.append(raw_path + ".source_boundary_must_match_frozen_cell")
                if source.get("unit") != frozen_raw["unit"]:
                    findings.append(raw_path + ".source_unit_must_match_frozen_raw_input")
                locator = _mapping(frozen_raw.get("locator"))
                for locator_key in ("table_or_note", "line_item", "period_column"):
                    if source.get(locator_key) != locator.get(locator_key):
                        findings.append(raw_path + f".source_{locator_key}_locator_must_match_frozen_raw_input")
                source_clock_findings = _availability_after_cutoff(
                    source, cutoff=_enterprise_cutoff(contract), path=raw_path + ".source"
                ) if _enterprise_cutoff(contract) is not None else []
                findings.extend(source_clock_findings)
                if not isinstance(source.get("pdf_page"), int) or source["pdf_page"] < 1:
                    findings.append(raw_path + ".pdf_page_required")
                if source.get("field_ref") != f"PDF p.{source.get('pdf_page')}":
                    findings.append(raw_path + ".field_ref_must_match_pdf_page")
            elif raw_status in {"UNKNOWN", "MEASUREMENT_MISMATCH"} and not _text(raw_item.get("reason")):
                findings.append(raw_path + ".reason_required")
        expected_status = (
            "MEASUREMENT_MISMATCH" if "MEASUREMENT_MISMATCH" in raw_statuses
            else "UNKNOWN" if "UNKNOWN" in raw_statuses
            else "OBSERVED"
        )
        if status != expected_status:
            findings.append(path + ".status_must_follow_raw_field_statuses")
    return {"valid": not findings, "findings": findings, "result": deepcopy(item) if not findings else None}


def validate_enterprise_settlement_clocks(
    result: Any, *, measurement_contract: Any, observed_at: Any, settled_at: Any,
) -> dict[str, Any]:
    """Check the PIT relation between cutoff, source, observation and settlement."""
    findings: list[str] = []
    contract_kind, contract, _ = _contract_context(measurement_contract)
    if contract_kind != ENTERPRISE_CONTRACT_KIND:
        return {"valid": False, "findings": ["enterprise_v3_contract_required"]}
    cutoff = _enterprise_cutoff(contract)
    observed = _instant(observed_at)
    settled = _instant(settled_at)
    if cutoff is None or observed is None or settled is None:
        findings.append("enterprise_settlement_clock_must_be_timezone_aware")
    else:
        if observed <= cutoff:
            findings.append("enterprise_observed_at_must_follow_cutoff")
        if settled <= observed:
            findings.append("enterprise_settled_at_must_follow_observed_at")
    item = _mapping(result)
    for cell_observation in _items(item.get("observations")):
        for raw in _items(_mapping(cell_observation).get("raw_field_observations")):
            source = _mapping(_mapping(raw).get("source"))
            if _mapping(raw).get("status") in {"OBSERVED", "MEASUREMENT_MISMATCH"} and observed is not None:
                if _source_available_before_observation(source, observed_at=observed):
                    findings.append("enterprise_observed_at_must_follow_source_availability")
    return {"valid": not findings, "findings": findings}


def validate_acquisition_result(
    result: Any, *, measurement_contract: Any = None, outcome_access_authorization: Any = None,
) -> dict[str, Any]:
    """Validate the narrow output shape without re-reading any PDF."""
    if _mapping(result).get("contract_kind") == ENTERPRISE_CONTRACT_KIND:
        return _validate_enterprise_acquisition_result(
            result,
            measurement_contract=measurement_contract,
            outcome_access_authorization=outcome_access_authorization,
        )
    findings: list[str] = []
    item = _mapping(result)
    allowed = {
        "schema_version", "measurement_contract_ref", "source_inventory_id", "custodian_id",
        "object_class", "claim_class", "allowed_outputs", "observations",
    }
    for field in sorted(set(item).difference(allowed)):
        findings.append(f"result_contains_unapproved_field:{field}")
    if item.get("schema_version") != SCHEMA_VERSION:
        findings.append("result_schema_version_invalid")
    if item.get("object_class") != OBJECT_CLASS or item.get("claim_class") != CLAIM_CLASS:
        findings.append("result_identity_invalid")
    observations = _items(item.get("observations"))
    if not observations:
        findings.append("result_observations_must_be_nonempty")
    for index, raw in enumerate(observations):
        observation = _mapping(raw)
        if observation.get("status") not in STATUSES:
            findings.append(f"result.observations[{index}].status_invalid")
        for field in ("measurement_id", "metric_id", "metric_definition", "report_period_end", "unit", "reason"):
            if observation.get("status") == "OBSERVED" and field == "reason":
                continue
            if field != "reason" and not _text(observation.get(field)):
                findings.append(f"result.observations[{index}].{field}_required")
        if observation.get("status") == "OBSERVED":
            for field in ("source", "statement_kind", "currency", "reporting_scope", "consolidation_or_restatement_note"):
                if field not in observation:
                    findings.append(f"result.observations[{index}].{field}_required_for_observed")
            for field in ("current_value", "comparative_value"):
                value = observation.get(field)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
                    findings.append(f"result.observations[{index}].{field}_must_be_finite_for_observed")
        elif not _text(observation.get("reason")):
            findings.append(f"result.observations[{index}].reason_required_for_nonobserved")
    return {"valid": not findings, "findings": findings, "result": deepcopy(item) if not findings else None}
