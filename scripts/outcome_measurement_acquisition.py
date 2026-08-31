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
PAGE_EXTRACTION_RECEIPT_SCHEMA_VERSION = "enterprise-page-extraction-receipt.v1"
ENTERPRISE_CONTRACT_KIND = "ENTERPRISE_V3"
_PDF_PAGE_BREAK = "\f"
_NUMBER = re.compile(r"(?<![\d,])(?:-?\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)(?![\d,])")
_UNIT = re.compile(r"单\s*位\s*[:：]\s*(人民币)?\s*(元|万元|百万元|亿元)")
_STATIC_HOSTS = {"static.cninfo.com.cn", "static.sse.com.cn"}

PageReader = Callable[[Path], list[str]]

_V4_ROLE_FIELD_MAP = {
    "OPERATING_REVENUE": "operating_revenue_rmb",
    "OPERATING_COST": "operating_cost_rmb",
    "TAXES_AND_SURCHARGES": "taxes_and_surcharges_rmb",
    "SELLING_EXPENSE": "selling_expense_rmb",
    "ADMINISTRATIVE_EXPENSE": "administrative_expense_rmb",
    "OPERATING_CASH_FLOW": "operating_cash_flow_rmb",
    "CASH_LONG_LIVED_ASSET_ACQUISITION": "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb",
    "OPENING_ACCOUNTS_RECEIVABLE": "opening_accounts_receivable_rmb",
    "OPENING_PREPAYMENTS": "opening_prepayments_rmb",
    "OPENING_INVENTORY": "opening_inventory_rmb",
    "OPENING_ACCOUNTS_PAYABLE": "opening_accounts_payable_rmb",
    "OPENING_CUSTOMER_ADVANCES": "opening_customer_advances_rmb",
    "ENDING_ACCOUNTS_RECEIVABLE": "ending_accounts_receivable_rmb",
    "ENDING_PREPAYMENTS": "ending_prepayments_rmb",
    "ENDING_INVENTORY": "ending_inventory_rmb",
    "ENDING_ACCOUNTS_PAYABLE": "ending_accounts_payable_rmb",
    "ENDING_CUSTOMER_ADVANCES": "ending_customer_advances_rmb",
}
_WORKING_CAPITAL_OPENING_ROLES = (
    "OPENING_ACCOUNTS_RECEIVABLE", "OPENING_PREPAYMENTS", "OPENING_INVENTORY",
    "OPENING_ACCOUNTS_PAYABLE", "OPENING_CUSTOMER_ADVANCES",
)
_WORKING_CAPITAL_ENDING_ROLES = (
    "ENDING_ACCOUNTS_RECEIVABLE", "ENDING_PREPAYMENTS", "ENDING_INVENTORY",
    "ENDING_ACCOUNTS_PAYABLE", "ENDING_CUSTOMER_ADVANCES",
)
_CASH_NORMALIZATION_ROLES = {
    "OPERATING_CASH_FLOW", "MAINTENANCE_CAPEX", "OCF_RECONCILIATION_ADJUSTMENT",
    "OWNER_CASH_ADJUSTMENT", *_WORKING_CAPITAL_OPENING_ROLES, *_WORKING_CAPITAL_ENDING_ROLES,
}
_CAPITAL_ALLOCATION_ROLES = {
    "CAPEX_CLASS", "PROJECT_COMMITMENT", "PROJECT_REMAINING_COMMITMENT",
    "GROWTH_CAPEX", "CAPACITY", "PRODUCTION", "SALES_VOLUME", "CUSTOMER_ABSORPTION",
    "UNIT_ECONOMICS", "CASH_COLLECTIONS", "DEBT", "CASH_RETURN_NUMERATOR",
    "INVESTED_CAPITAL_DENOMINATOR",
}


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


def _enterprise_source_accesses(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the frozen Enterprise source set while preserving legacy V3."""
    if isinstance(contract.get("source_accesses"), list):
        return [deepcopy(item) for item in contract["source_accesses"] if isinstance(item, dict)]
    source = contract.get("source_access")
    return [deepcopy(source)] if isinstance(source, dict) else []


def _enterprise_source_access_by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(source.get("source_id")): source
        for source in _enterprise_source_accesses(contract)
        if _text(source.get("source_id"))
    }


def _enterprise_authorization_receipt_id(contract: dict[str, Any]) -> str | None:
    receipt_ids = {
        str(source.get("authorization_receipt_id"))
        for source in _enterprise_source_accesses(contract)
        if _text(source.get("authorization_receipt_id"))
    }
    return next(iter(receipt_ids)) if len(receipt_ids) == 1 else None


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
    multi_source = isinstance(contract.get("source_accesses"), list)
    required = {
        "schema_version", "authorization_receipt_id", "measurement_contract_ref", "company_id",
        "custodian_id", "source_ids" if multi_source else "source_id", "authorized", "content_read",
    }
    findings: list[str] = []
    if set(item) != required:
        findings.append("enterprise_authorization_shape_invalid")
    if item.get("schema_version") != ENTERPRISE_AUTHORIZATION_SCHEMA_VERSION:
        findings.append("enterprise_authorization_schema_invalid")
    if item.get("authorization_receipt_id") != _enterprise_authorization_receipt_id(contract):
        findings.append("enterprise_authorization_receipt_mismatch")
    if item.get("measurement_contract_ref") != _reference(contract):
        findings.append("enterprise_authorization_contract_ref_mismatch")
    if item.get("company_id") != contract.get("company_id"):
        findings.append("enterprise_authorization_company_mismatch")
    if not _text(item.get("custodian_id")):
        findings.append("enterprise_authorization_custodian_required")
    if multi_source:
        expected_source_ids = [
            str(source.get("source_id")) for source in _enterprise_source_accesses(contract)
        ]
        if item.get("source_ids") != expected_source_ids or len(expected_source_ids) != len(set(expected_source_ids)):
            findings.append("enterprise_authorization_source_set_mismatch")
    elif item.get("source_id") != _mapping(contract.get("source_access")).get("source_id"):
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
    enterprise_sources = (
        _enterprise_source_access_by_id(contract)
        if contract_kind == ENTERPRISE_CONTRACT_KIND else {}
    )
    multi_source_enterprise = isinstance(contract.get("source_accesses"), list)
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
        if not multi_source_enterprise and expected_report_period is not None and document.get("report_period_end") != expected_report_period:
            findings.append(f"{path}_report_period_must_match_enterprise_outcome_source")
        if contract_kind == ENTERPRISE_CONTRACT_KIND and authorization is not None:
            frozen_source = enterprise_sources.get(str(document.get("source_id")))
            if frozen_source is None:
                findings.append(f"{path}_source_id_must_match_enterprise_authorization")
            else:
                for source_field in ("source_url", "issuer_id", "report_period_end"):
                    if document.get(source_field) != frozen_source.get(
                        "official_url" if source_field == "source_url" else source_field
                    ):
                        findings.append(f"{path}_{source_field}_must_match_enterprise_contract")
                if _canonical_source_type(document.get("official_source_type")) != _canonical_source_type(frozen_source.get("source_type")):
                    findings.append(f"{path}_official_source_type_must_match_enterprise_contract")
            if multi_source_enterprise:
                if document.get("source_id") not in _items(authorization.get("source_ids")):
                    findings.append(f"{path}_source_id_must_match_enterprise_authorization")
            elif document.get("source_id") != authorization.get("source_id"):
                findings.append(f"{path}_source_id_must_match_enterprise_authorization")
        elif contract_kind == ENTERPRISE_CONTRACT_KIND and _canonical_source_type(document.get("official_source_type")) != expected_source_type:
            findings.append(f"{path}_official_source_type_must_match_enterprise_contract")
        documents.append(deepcopy(document))
    if not documents:
        findings.append("inventory_documents_must_be_nonempty")
    if multi_source_enterprise and source_ids != set(enterprise_sources):
        findings.append("inventory_documents_must_exactly_cover_frozen_enterprise_source_set")
    return {"valid": not findings, "findings": findings, "inventory": deepcopy(item) if not findings else None}


def _pdf_pages(local_path: Path) -> list[str]:
    completed = subprocess.run(
        ["pdftotext", "-layout", str(local_path), "-"],
        check=True, capture_output=True, text=True,
    )
    pages = completed.stdout.split(_PDF_PAGE_BREAK)
    return pages[:-1] if pages and not pages[-1].strip() else pages


def _receipt_decimal(token: Any) -> Decimal | None:
    if not isinstance(token, str) or not token.strip():
        return None
    cleaned = token.strip().replace(",", "").replace("，", "")
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1]
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _evaluate_page_value_expression(expression: Any) -> Decimal | bool | None:
    item = _mapping(expression)
    operator = item.get("operator")
    tokens = _items(item.get("tokens"))
    if operator == "BOOLEAN_TOKEN_PRESENCE" and tokens and all(
        isinstance(token, str) and token.strip() for token in tokens
    ):
        return True
    values = [_receipt_decimal(token) for token in tokens]
    if any(value is None for value in values):
        return None
    numeric = [value for value in values if value is not None]
    multiplier = _receipt_decimal(item.get("multiplier", "1"))
    if multiplier is None:
        return None
    if operator == "SCALED_TOKEN" and len(numeric) == 1:
        return numeric[0] * multiplier
    if operator == "DIFFERENCE_SCALED_TOKENS" and len(numeric) == 2:
        return (numeric[0] - numeric[1]) * multiplier
    if operator == "RATIO_TOKENS" and len(numeric) == 2 and numeric[1] != 0:
        return (numeric[0] / numeric[1]) * multiplier
    if operator == "GROSS_MARGIN_TOKENS" and len(numeric) == 2 and numeric[0] != 0:
        return ((numeric[0] - numeric[1]) / numeric[0]) * multiplier
    return None


def validate_page_bound_enterprise_field_records(
    field_records: Any,
    page_extraction_receipts: Any,
    *,
    measurement_contract: Any,
    inventory: Any,
    page_reader: PageReader = _pdf_pages,
) -> dict[str, Any]:
    """Verify every scored raw value against text extracted from its cited PDF page.

    Custodian field records remain the acquisition input, while these receipts
    provide the missing mechanical bridge to the source page.  The expression
    language is deliberately small: it supports direct scaling, subtraction,
    and ratios without guessing table semantics or nearby values.
    """
    contract = _mapping(measurement_contract)
    records = _items(field_records)
    receipts = _items(page_extraction_receipts)
    documents = {
        document.get("source_id"): document
        for document in _items(_mapping(inventory).get("documents"))
        if isinstance(document, dict) and _text(document.get("source_id"))
    }
    frozen_fields = {
        raw.get("field_id"): (cell, raw)
        for cell in _items(contract.get("atomic_cells"))
        if isinstance(cell, dict)
        for raw in _items(cell.get("raw_input_fields"))
        if isinstance(raw, dict) and _text(raw.get("field_id"))
    }
    observed = [record for record in records if _mapping(record).get("status") == "OBSERVED"]
    expected_ids = [record.get("field_id") for record in observed]
    supplied_ids = [receipt.get("field_id") for receipt in receipts if isinstance(receipt, dict)]
    findings: list[str] = []
    if supplied_ids != expected_ids or len(set(supplied_ids)) != len(expected_ids):
        findings.append("page_extraction_receipts_must_cover_observed_fields_in_order")
    page_cache: dict[str, list[str]] = {}
    required_keys = {
        "schema_version", "receipt_id", "field_id", "source_id", "pdf_page",
        "unit", "anchor_tokens", "value_expression", "object_class", "claim_class",
    }
    for index, receipt_value in enumerate(receipts):
        path = f"page_extraction_receipts[{index}]"
        receipt = _mapping(receipt_value)
        if frozenset(receipt) not in {
            frozenset(required_keys), frozenset(required_keys | {"supporting_pdf_pages"}),
        }:
            findings.append(f"{path}_shape_invalid")
            continue
        if receipt.get("schema_version") != PAGE_EXTRACTION_RECEIPT_SCHEMA_VERSION:
            findings.append(f"{path}_schema_version_invalid")
        if receipt.get("object_class") != "ENTERPRISE_PAGE_EXTRACTION_RECEIPT" or receipt.get("claim_class") != "PDF_PAGE_VALUE_BINDING_ONLY":
            findings.append(f"{path}_object_or_claim_class_invalid")
        if not _text(receipt.get("receipt_id")):
            findings.append(f"{path}_receipt_id_required")
        field_id = receipt.get("field_id")
        if field_id not in frozen_fields or index >= len(observed):
            findings.append(f"{path}_field_not_frozen_or_unexpected")
            continue
        record = _mapping(observed[index])
        cell, raw_field = frozen_fields[field_id]
        source = _mapping(record.get("source"))
        if record.get("cell_id") != cell.get("cell_id") or record.get("field_id") != raw_field.get("field_id"):
            findings.append(f"{path}_record_identity_mismatch")
        if record.get("unit") != raw_field.get("unit") or receipt.get("unit") != raw_field.get("unit"):
            findings.append(f"{path}_unit_must_match_frozen_field")
        if source.get("source_id") != receipt.get("source_id") or source.get("pdf_page") != receipt.get("pdf_page"):
            findings.append(f"{path}_source_or_page_mismatch")
        document = documents.get(receipt.get("source_id"))
        if document is None:
            findings.append(f"{path}_source_not_registered")
            continue
        local_path = Path(str(document.get("local_pdf_path", "")))
        cache_key = str(local_path)
        if cache_key not in page_cache:
            try:
                page_cache[cache_key] = page_reader(local_path)
            except (OSError, subprocess.SubprocessError):
                findings.append(f"{path}_pdf_text_extraction_failed")
                continue
        page_number = receipt.get("pdf_page")
        pages = page_cache[cache_key]
        if not isinstance(page_number, int) or page_number < 1 or page_number > len(pages):
            findings.append(f"{path}_pdf_page_invalid")
            continue
        supporting = receipt.get("supporting_pdf_pages", [])
        if (
            not isinstance(supporting, list)
            or any(not isinstance(page, int) or isinstance(page, bool) for page in supporting)
            or len(set(supporting)) != len(supporting)
            or page_number in supporting
            or any(page < 1 or page > len(pages) for page in supporting)
        ):
            findings.append(f"{path}_supporting_pdf_pages_invalid")
            continue
        page_text = re.sub(
            r"\s+", "", "\n".join(pages[page - 1] for page in [page_number, *supporting]),
        )
        anchors = _items(receipt.get("anchor_tokens"))
        expression = _mapping(receipt.get("value_expression"))
        expression_tokens = _items(expression.get("tokens"))
        if not anchors or any(
            not isinstance(token, str) or re.sub(r"\s+", "", token) not in page_text
            for token in anchors + expression_tokens
        ):
            findings.append(f"{path}_declared_tokens_not_found_on_pdf_page")
        derived = _evaluate_page_value_expression(expression)
        raw_value = record.get("raw_value")
        if isinstance(derived, bool):
            if not isinstance(raw_value, bool) or raw_value is not derived:
                findings.append(f"{path}_raw_value_not_derived_from_pdf_page")
            continue
        if derived is None or isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            findings.append(f"{path}_value_expression_invalid")
            continue
        observed_value = Decimal(str(raw_value))
        tolerance = Decimal("1e-12") * max(Decimal(1), abs(derived))
        if abs(observed_value - derived) > tolerance:
            findings.append(f"{path}_raw_value_not_derived_from_pdf_page")
    return {
        "valid": not findings,
        "findings": findings,
        "verified_field_ids": expected_ids if not findings else [],
    }


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
            "continuation_pages": 1,
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
    for prefix, markers in (
        ("SEGMENT_REVENUE_RMB:", ("分部报告", "分部信息", "分部")),
        ("PRODUCT_REVENUE_RMB:", ("营业收入构成",)),
    ):
        if source_field_id.startswith(prefix) and _text(source_field_id[len(prefix):]):
            return {
                "statement_kind": "SEGMENT_OR_PRODUCT_OPERATIONAL_DATA", "scope": "CONSOLIDATED",
                "markers": markers, "labels": (source_field_id[len(prefix):],),
                **({"value_columns": (0, 2)} if prefix == "PRODUCT_REVENUE_RMB:" else {}),
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
    seen_pages: set[int] = set()
    for marker_index, page in enumerate(pages):
        if not any(marker in page for marker in spec["markers"]):
            continue
        marker_unit = _page_unit_scale(page)
        continuation_pages = int(spec.get("continuation_pages", 0))
        for target_index in range(marker_index, min(len(pages), marker_index + continuation_pages + 1)):
            page_number = target_index + 1
            if page_number in seen_pages:
                continue
            target_page = pages[target_index]
            # A new statement heading starts a new table and cannot be treated
            # as a continuation of the prior consolidated statement.
            if target_index > marker_index and re.search(r"(?:母公司|合并).*(?:利润表|资产负债表|现金流量表)", target_page):
                break
            lines = target_page.splitlines()
            for position, line in enumerate(lines):
                if not any(label in line for label in spec["labels"]):
                    continue
                candidate = " ".join(lines[position:position + 3])
                values = _numeric_values(candidate)
                if len(values) >= 2:
                    # Accounting note identifiers precede the actual current
                    # and comparative columns.  The two right-most numeric
                    # tokens are used only in a table selected by the explicit
                    # catalogue marker above.
                    columns = spec.get("value_columns")
                    if isinstance(columns, tuple) and len(columns) == 2:
                        if max(columns) >= len(values):
                            continue
                        current, comparative = values[columns[0]], values[columns[1]]
                    else:
                        current, comparative = values[-2], values[-1]
                    matches.append((
                        page_number, candidate, current, comparative,
                        _page_unit_scale(target_page) or marker_unit,
                    ))
                    seen_pages.add(page_number)
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
    frozen_source_id = _text(raw_field.get("source_id"))
    candidates = [
        document for document in documents
        if frozen_source_id is None or document.get("source_id") == frozen_source_id
    ]
    if not candidates:
        return {
            **base, "status": "UNKNOWN", "reason": "NO_AUTHORIZED_ANNUAL_REPORT_FOR_ENTERPRISE_CONTRACT",
            "sources_considered": [],
        }
    rows: list[tuple[dict[str, Any], int, str, str]] = []
    for document in candidates:
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
            "sources_considered": [_source_identity(document) for document in candidates],
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
    source["custodian_locator"] = deepcopy(raw_field["locator"])
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
        frozen_source_id = _text(raw_field.get("source_id"))
        source_id = _text(source.get("source_id"))
        candidates = [
            document for document in documents
            if document.get("source_id") == (frozen_source_id or source_id)
        ]
        if not candidates:
            findings.append("field_record_source_document_missing")
        else:
            document = candidates[0]
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
            actual_locator = _mapping(source.get("custodian_locator"))
            if isinstance(contract.get("source_accesses"), list):
                if actual_locator != locator:
                    findings.append(
                        "field_record_source_custodian_locator_must_match_frozen_locator"
                    )
            elif set(actual_locator) != {"table_or_note", "line_item", "period_column"} or any(
                not _text(actual_locator.get(key))
                for key in ("table_or_note", "line_item", "period_column")
            ):
                findings.append("field_record_source_custodian_locator_invalid")
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


def _convert_enterprise_raw_value(
    frozen_raw: dict[str, Any], observation: dict[str, Any], conversion: dict[str, Any],
    *, consumer_amount: bool, positive_magnitude: bool = False,
) -> tuple[Decimal | bool, str]:
    """Apply one frozen conversion without inventing a missing raw amount.

    Multi-source contracts separate a positive unit-conversion magnitude from
    the formula coefficient.  Legacy V3 conversions may still carry their
    historical signed scale; consumer facts continue to receive only its
    magnitude so existing downstream role semantics remain unchanged.
    """
    if conversion.get("field_id") != frozen_raw.get("field_id"):
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_unit_conversion_identity_invalid")
    if (
        conversion.get("from_unit") != frozen_raw.get("unit")
        or conversion.get("from_unit") != observation.get("unit")
    ):
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_source_unit_mismatch")
    converted_unit = _text(conversion.get("to_unit"))
    if converted_unit is None:
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_destination_unit_invalid")
    try:
        scale = Decimal(str(conversion.get("scale")))
    except InvalidOperation as exc:
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_unit_scale_invalid") from exc
    if not scale.is_finite() or scale == 0 or (positive_magnitude and scale < 0):
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_unit_scale_invalid")
    value = observation.get("raw_value")
    if isinstance(value, bool):
        if frozen_raw.get("role") != "EVENT" or abs(scale) != 1:
            raise OutcomeMeasurementAcquisitionError("enterprise_event_unit_conversion_invalid")
        return value, converted_unit
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_raw_value_invalid")
    multiplier = scale if positive_magnitude else (abs(scale) if consumer_amount else scale)
    return Decimal(str(value)) * multiplier, converted_unit


def execute_enterprise_deterministic_formula(
    cell: dict[str, Any], raw_field_observations: list[dict[str, Any]],
) -> bool | float:
    """Execute a frozen Enterprise formula without substituting missing fields.

    This construction helper intentionally lives beside acquisition.  It
    supports the legacy V3 operators plus the reusable company/capital bridge
    operators; settlement authority remains outside this module.
    """
    frozen_raws = _items(cell.get("raw_input_fields"))
    by_id = {
        str(item.get("field_id")): item for item in raw_field_observations
        if isinstance(item, dict) and _text(item.get("field_id"))
    }
    input_ids = _items(_mapping(cell.get("formula")).get("input_field_ids"))
    if input_ids != [raw.get("field_id") for raw in frozen_raws] or set(by_id) != set(input_ids):
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_raw_input_coverage_invalid")
    if any(by_id[str(field_id)].get("status") != "OBSERVED" for field_id in input_ids):
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_requires_observed_raw_inputs")
    formula = _mapping(cell.get("formula"))
    conversions = _items(formula.get("unit_conversions"))
    if [item.get("field_id") for item in conversions if isinstance(item, dict)] != input_ids:
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_unit_conversion_order_invalid")

    coefficient_bindings = _items(formula.get("input_coefficients"))
    explicit_coefficients = "input_coefficients" in formula
    converted = [
        _convert_enterprise_raw_value(
            frozen_raw, by_id[str(frozen_raw["field_id"])], conversion,
            consumer_amount=False,
            positive_magnitude=explicit_coefficients,
        )[0]
        for frozen_raw, conversion in zip(frozen_raws, conversions, strict=True)
    ]

    operator = formula.get("operator")
    coefficients: list[Decimal] | None = None
    if explicit_coefficients:
        if [
            item.get("field_id") for item in coefficient_bindings if isinstance(item, dict)
        ] != input_ids:
            raise OutcomeMeasurementAcquisitionError(
                "enterprise_formula_coefficient_coverage_invalid"
            )
        coefficients = []
        for coefficient_binding in coefficient_bindings:
            try:
                coefficient = Decimal(str(coefficient_binding.get("coefficient")))
            except InvalidOperation as exc:
                raise OutcomeMeasurementAcquisitionError(
                    "enterprise_formula_coefficient_invalid"
                ) from exc
            if not coefficient.is_finite() or coefficient not in {Decimal("-1"), Decimal("1")}:
                raise OutcomeMeasurementAcquisitionError("enterprise_formula_coefficient_invalid")
            coefficients.append(coefficient)
        if operator != "SUM" and any(coefficient != 1 for coefficient in coefficients):
            raise OutcomeMeasurementAcquisitionError(
                "enterprise_intrinsically_signed_formula_coefficient_invalid"
            )
    if operator == "EVENT_BOOLEAN":
        if len(converted) != 1 or not isinstance(converted[0], bool):
            raise OutcomeMeasurementAcquisitionError("enterprise_event_formula_requires_one_boolean")
        return converted[0]
    if any(isinstance(value, bool) for value in converted):
        raise OutcomeMeasurementAcquisitionError("enterprise_numeric_formula_cannot_use_boolean")
    numeric = [value for value in converted if isinstance(value, Decimal)]
    if operator == "RAW_VALUE":
        if len(numeric) != 1:
            raise OutcomeMeasurementAcquisitionError("enterprise_raw_value_formula_requires_one_input")
        result = numeric[0]
    elif operator == "SUM":
        result = (
            sum(
                (value * coefficient for value, coefficient in zip(numeric, coefficients, strict=True)),
                Decimal("0"),
            )
            if coefficients is not None
            else sum(numeric, Decimal("0"))
        )
    elif operator == "SIGNED_STOCK_DELTA":
        if len(numeric) != 2:
            raise OutcomeMeasurementAcquisitionError("enterprise_signed_stock_delta_input_count_invalid")
        result = numeric[1] - numeric[0]
    elif operator == "COMPONENT_TO_TOTAL_RECONCILIATION":
        if len(numeric) < 2:
            raise OutcomeMeasurementAcquisitionError("enterprise_component_reconciliation_input_count_invalid")
        result = sum(numeric[:-1], Decimal("0")) - numeric[-1]
    elif operator == "OWNER_CASH":
        if len(numeric) < 2:
            raise OutcomeMeasurementAcquisitionError("enterprise_owner_cash_input_count_invalid")
        result = numeric[0] - numeric[1] + sum(numeric[2:], Decimal("0"))
    elif operator == "INVESTED_CAPITAL_RETURN":
        if len(numeric) != 2 or numeric[1] == 0:
            raise OutcomeMeasurementAcquisitionError("enterprise_invested_capital_return_zero_or_invalid_denominator")
        result = numeric[0] / numeric[1]
    elif operator == "PERCENT_CHANGE":
        if len(numeric) != 2 or numeric[0] == 0:
            raise OutcomeMeasurementAcquisitionError("enterprise_percent_change_zero_or_invalid_baseline")
        result = (numeric[1] - numeric[0]) / abs(numeric[0])
    elif operator == "RATIO_CHANGE":
        if len(numeric) != 4 or numeric[1] == 0 or numeric[3] == 0:
            raise OutcomeMeasurementAcquisitionError("enterprise_ratio_change_zero_or_invalid_denominator")
        baseline_ratio = numeric[0] / numeric[1]
        if baseline_ratio == 0:
            raise OutcomeMeasurementAcquisitionError("enterprise_ratio_change_zero_baseline_ratio")
        result = ((numeric[2] / numeric[3]) - baseline_ratio) / abs(baseline_ratio)
    elif operator == "DIFFERENCE":
        if len(numeric) == 2:
            result = numeric[1] - numeric[0]
        elif len(numeric) == 4:
            if numeric[0] == 0 or numeric[2] == 0:
                raise OutcomeMeasurementAcquisitionError("enterprise_difference_zero_revenue_denominator")
            result = ((numeric[2] - numeric[3]) / numeric[2]) - ((numeric[0] - numeric[1]) / numeric[0])
        else:
            raise OutcomeMeasurementAcquisitionError("enterprise_difference_input_count_invalid")
    else:
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_operator_unsupported")
    if not result.is_finite():
        raise OutcomeMeasurementAcquisitionError("enterprise_formula_result_not_finite")
    return float(result)


def _enterprise_evidence_id(
    contract: dict[str, Any], *, source_id: Any, component_id: Any, field_id: Any,
) -> str:
    """Return a stable evidence identity when one fact supports several cells."""
    return (
        f"ENTERPRISE_RAW:{contract.get('contract_set_id')}:{source_id}:"
        f"{component_id}:{field_id}"
    )


def _frozen_identity(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _frozen_identity(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_frozen_identity(item) for item in value)
    return value


def _deduplicate_enterprise_raw_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Collapse exact cross-cell fact reuse and surface contradictory reuse."""
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        identity = (
            record.get("component_role"),
            record.get("component_id"),
            record.get("responsibility_unit_id"),
            record.get("perimeter_id"),
            record.get("raw_field_role"),
            record.get("field_id"),
            _frozen_identity(record.get("measurement_clock")),
        )
        grouped.setdefault(identity, []).append(record)

    deduplicated: list[dict[str, Any]] = []
    conflicting_cells: set[str] = set()
    comparison_keys = {
        "status", "unit", "value", "source", "reason", "period_end", "locator",
    }
    for occurrences in grouped.values():
        first = occurrences[0]
        first_payload = {
            key: _frozen_identity(first.get(key)) for key in comparison_keys
        }
        if all(
            {key: _frozen_identity(item.get(key)) for key in comparison_keys} == first_payload
            for item in occurrences[1:]
        ):
            deduplicated.append(first)
            continue
        conflicting_cells.update(str(item.get("cell_id")) for item in occurrences)
        mismatch = deepcopy(first)
        mismatch.update(
            status="MEASUREMENT_MISMATCH",
            reason="CONFLICTING_DUPLICATE_SOURCE_BOUND_RAW_FACT",
        )
        for key in ("value", "source", "observation_id"):
            mismatch.pop(key, None)
        deduplicated.append(mismatch)
    return deduplicated, conflicting_cells


def project_enterprise_acquisition_consumers(
    measurement_contract: Any,
    acquisition_result: Any,
    *,
    outcome_access_authorization: Any,
    v4_formula_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Project observed Enterprise fields to existing consumer input boundaries.

    The projection is deliberately partial: it emits source-bearing model
    inputs, not a normalized working-capital model, V4 candidate, or financial
    driver judgment.  Missing and mismatched raw fields remain local and are
    never converted to zero.
    """
    contract_kind, contract, cells = _contract_context(measurement_contract)
    if contract_kind != ENTERPRISE_CONTRACT_KIND:
        raise OutcomeMeasurementAcquisitionError("consumer_projection_requires_enterprise_v3_contract")
    validation = _validate_enterprise_acquisition_result(
        acquisition_result,
        measurement_contract=contract,
        outcome_access_authorization=outcome_access_authorization,
    )
    if not validation["valid"]:
        raise OutcomeMeasurementAcquisitionError(
            "enterprise_acquisition_result_invalid: " + "; ".join(validation["findings"])
        )
    result = validation["result"]
    by_cell = {item["measurement_id"]: item for item in result["observations"]}
    source_accesses = _enterprise_source_access_by_id(contract)
    enhanced = isinstance(contract.get("source_accesses"), list)

    constructed_cells: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []
    for cell in cells:
        observation = by_cell[cell["cell_id"]]
        boundary = _mapping(cell.get("responsibility_boundary"))
        formula = _mapping(cell.get("formula"))
        cell_status = observation["status"]
        construction: dict[str, Any] = {
            "cell_id": cell["cell_id"],
            "status": cell_status,
            "component_role": boundary.get("component_role"),
            "component_id": boundary.get("component_id"),
            "formula_operator": formula.get("operator"),
            "mismatch_propagation": "LOCAL_ONLY",
        }
        if cell_status == "OBSERVED":
            try:
                construction["computed_value"] = execute_enterprise_deterministic_formula(
                    cell, observation["raw_field_observations"],
                )
            except OutcomeMeasurementAcquisitionError as exc:
                construction.update(status="MEASUREMENT_MISMATCH", reason=str(exc))
        else:
            construction["reason"] = observation.get("reason")
        constructed_cells.append(construction)

        acquired_by_id = {
            item["field_id"]: item for item in observation["raw_field_observations"]
        }
        conversions_by_id = {
            item.get("field_id"): item
            for item in _items(formula.get("unit_conversions"))
            if isinstance(item, dict)
        }
        for frozen_raw in cell["raw_input_fields"]:
            acquired = acquired_by_id[frozen_raw["field_id"]]
            source = _mapping(acquired.get("source"))
            source_id = _text(frozen_raw.get("source_id")) or _text(source.get("source_id"))
            frozen_source = source_accesses.get(str(source_id), {})
            period_end = (
                source.get("report_period_end")
                or frozen_source.get("report_period_end")
                or _enterprise_report_period(contract)
            )
            record: dict[str, Any] = {
                "cell_id": cell["cell_id"],
                "field_id": frozen_raw["field_id"],
                "raw_field_role": frozen_raw.get("role"),
                "status": acquired["status"],
                "component_role": boundary.get("component_role"),
                "component_id": boundary.get("component_id"),
                "responsibility_unit_id": boundary.get("responsibility_unit_id"),
                "perimeter_id": boundary.get("perimeter_id"),
                "measurement_clock": deepcopy(frozen_raw.get("measurement_clock")),
                "locator": deepcopy(frozen_raw.get("locator")),
                "period_start": _mapping(cell.get("outcome_period")).get("period_start", "")[:10],
                "period_end": period_end,
                "unit": frozen_raw["unit"],
            }
            if acquired["status"] == "OBSERVED":
                try:
                    converted_value, converted_unit = _convert_enterprise_raw_value(
                        frozen_raw,
                        acquired,
                        _mapping(conversions_by_id.get(frozen_raw["field_id"])),
                        consumer_amount=True,
                        positive_magnitude="input_coefficients" in formula,
                    )
                    if frozen_raw.get("role") in _V4_ROLE_FIELD_MAP and converted_unit != "RMB":
                        raise OutcomeMeasurementAcquisitionError(
                            "enterprise_consumer_destination_unit_must_be_rmb"
                        )
                    record.update(
                        value=(
                            converted_value
                            if isinstance(converted_value, bool)
                            else float(converted_value)
                        ),
                        unit=converted_unit,
                        source=deepcopy(source),
                        observation_id=_enterprise_evidence_id(
                            contract,
                            source_id=source_id,
                            component_id=boundary.get("component_id"),
                            field_id=frozen_raw["field_id"],
                        ),
                    )
                except OutcomeMeasurementAcquisitionError as exc:
                    record.update(status="MEASUREMENT_MISMATCH", reason=str(exc))
                    construction.update(status="MEASUREMENT_MISMATCH", reason=str(exc))
                    construction.pop("computed_value", None)
            else:
                record["reason"] = acquired.get("reason")
            raw_records.append(record)

    raw_records, conflicting_cell_ids = _deduplicate_enterprise_raw_records(raw_records)
    observation_ids = [
        str(record["observation_id"])
        for record in raw_records
        if record.get("status") == "OBSERVED" and record.get("observation_id") is not None
    ]
    if len(observation_ids) != len(set(observation_ids)):
        raise OutcomeMeasurementAcquisitionError(
            "enterprise_consumer_projection_observation_ids_must_be_unique"
        )
    for construction in constructed_cells:
        if construction["cell_id"] in conflicting_cell_ids:
            construction.update(
                status="MEASUREMENT_MISMATCH",
                reason="CONFLICTING_DUPLICATE_SOURCE_BOUND_RAW_FACT",
            )
            construction.pop("computed_value", None)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in raw_records:
        key = (
            str(record.get("component_role") or ""),
            str(record.get("component_id") or ""),
            str(record.get("period_end") or ""),
        )
        grouped.setdefault(key, []).append(record)

    working_capital_inputs: list[dict[str, Any]] = []
    working_capital_unresolved: list[dict[str, Any]] = []
    v4_inputs: list[dict[str, Any]] = []
    v4_unresolved: list[dict[str, Any]] = []
    cash_groups: list[dict[str, Any]] = []
    allocation_groups: list[dict[str, Any]] = []
    formula_binding = v4_formula_ids if isinstance(v4_formula_ids, dict) else {}
    for (component_role, component_id, period_end), records in sorted(grouped.items()):
        by_role: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_role.setdefault(str(record.get("raw_field_role")), []).append(record)

        wc_roles = set(_WORKING_CAPITAL_OPENING_ROLES + _WORKING_CAPITAL_ENDING_ROLES)
        if wc_roles.intersection(by_role):
            unresolved_roles = [
                role for role in sorted(wc_roles)
                if len(by_role.get(role, [])) != 1 or by_role[role][0]["status"] != "OBSERVED"
            ]
            if unresolved_roles:
                working_capital_unresolved.append({
                    "component_role": component_role,
                    "component_id": component_id,
                    "period_end": period_end,
                    "status": "MEASUREMENT_MISMATCH" if any(
                        any(item["status"] == "MEASUREMENT_MISMATCH" for item in by_role.get(role, []))
                        for role in unresolved_roles
                    ) else "UNKNOWN",
                    "unresolved_roles": unresolved_roles,
                })
            else:
                value = lambda role: float(by_role[role][0]["value"])
                opening = sum(value(role) for role in _WORKING_CAPITAL_OPENING_ROLES[:3]) - sum(
                    value(role) for role in _WORKING_CAPITAL_OPENING_ROLES[3:]
                )
                closing = sum(value(role) for role in _WORKING_CAPITAL_ENDING_ROLES[:3]) - sum(
                    value(role) for role in _WORKING_CAPITAL_ENDING_ROLES[3:]
                )
                evidence_ids = [
                    by_role[role][0]["observation_id"]
                    for role in _WORKING_CAPITAL_OPENING_ROLES + _WORKING_CAPITAL_ENDING_ROLES
                ]
                period_start = next((str(item.get("period_start")) for item in records if item.get("period_start")), "")
                working_capital_inputs.append({
                    "component_role": component_role,
                    "component_id": component_id,
                    "period": {
                        "period_id": f"{component_id}:{period_end}",
                        "period_start": period_start,
                        "period_end": period_end,
                        "disclosure_mode": "NET_MOVEMENT_ONLY",
                        "net_movement_observation": {
                            "opening_net_stock": opening,
                            "closing_net_stock": closing,
                            "observed_cash_capital_charge": closing - opening,
                            "evidence_ids": evidence_ids,
                        },
                    },
                })

        required_v4_roles = set(_V4_ROLE_FIELD_MAP)
        if required_v4_roles.intersection(by_role):
            unresolved_roles = [
                role for role in sorted(required_v4_roles)
                if len(by_role.get(role, [])) != 1 or by_role[role][0]["status"] != "OBSERVED"
            ]
            formula_ids_valid = all(_text(formula_binding.get(key)) for key in ("d3_formula_id", "d4_formula_id"))
            if unresolved_roles or not formula_ids_valid:
                v4_unresolved.append({
                    "component_role": component_role,
                    "component_id": component_id,
                    "period_end": period_end,
                    "status": "UNKNOWN" if not unresolved_roles or not any(
                        any(item["status"] == "MEASUREMENT_MISMATCH" for item in by_role.get(role, []))
                        for role in unresolved_roles
                    ) else "MEASUREMENT_MISMATCH",
                    "unresolved_roles": unresolved_roles,
                    "reason": None if formula_ids_valid else "V4_FORMULA_BINDING_REQUIRED",
                })
            else:
                def v4_field(role: str) -> dict[str, Any]:
                    record = by_role[role][0]
                    source = record["source"]
                    return {
                        "source_id": source["source_id"],
                        "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
                        "issuer_id": source["issuer_id"],
                        "perimeter_id": record["perimeter_id"],
                        "published_at": source.get("source_available_at") or source.get("source_available_date"),
                        "field_ref": source["field_ref"],
                        "period_end": period_end,
                        "unit": record["unit"],
                        "value": record["value"],
                    }
                v4_inputs.append({
                    "component_role": component_role,
                    "component_id": component_id,
                    "observation": {
                        "period_end": period_end,
                        "reporting_frequency": "ANNUAL",
                        "d3_formula_id": formula_binding["d3_formula_id"],
                        "d4_formula_id": formula_binding["d4_formula_id"],
                        "d3_raw_fields": {
                            field_name: v4_field(role)
                            for role, field_name in _V4_ROLE_FIELD_MAP.items()
                            if field_name in {
                                "operating_revenue_rmb", "operating_cost_rmb", "taxes_and_surcharges_rmb",
                                "selling_expense_rmb", "administrative_expense_rmb",
                            }
                        },
                        "d4_raw_fields": {
                            field_name: v4_field(role)
                            for role, field_name in _V4_ROLE_FIELD_MAP.items()
                            if field_name not in {
                                "operating_revenue_rmb", "operating_cost_rmb", "taxes_and_surcharges_rmb",
                                "selling_expense_rmb", "administrative_expense_rmb",
                            }
                        },
                    },
                })

        cash_ids = {
            role: [item["observation_id"] for item in items if item["status"] == "OBSERVED"]
            for role, items in by_role.items() if role in _CASH_NORMALIZATION_ROLES
        }
        if cash_ids:
            cash_groups.append({
                "component_role": component_role, "component_id": component_id,
                "period_end": period_end, "observation_ids_by_role": cash_ids,
            })
        allocation_ids = {
            role: [item["observation_id"] for item in items if item["status"] == "OBSERVED"]
            for role, items in by_role.items() if role in _CAPITAL_ALLOCATION_ROLES
        }
        if allocation_ids:
            allocation_groups.append({
                "component_role": component_role, "component_id": component_id,
                "period_end": period_end, "observation_ids_by_role": allocation_ids,
            })

    verified_observations = [
        {
            "observation_id": record["observation_id"],
            "status": "VERIFIED",
            "component_role": record["component_role"],
            "component_id": record["component_id"],
            "raw_field_role": record["raw_field_role"],
            "period_end": record["period_end"],
            "unit": record["unit"],
            "value": record["value"],
            "source": deepcopy(record["source"]),
        }
        for record in raw_records if record["status"] == "OBSERVED"
    ]
    unresolved_raw_fields = [
        {key: deepcopy(record.get(key)) for key in (
            "cell_id", "field_id", "raw_field_role", "status", "component_role",
            "component_id", "period_end", "reason",
        )}
        for record in raw_records if record["status"] != "OBSERVED"
    ]
    return {
        "schema_version": "enterprise-acquisition-consumer-projection.v1",
        "measurement_contract_ref": _reference(contract),
        "company_id": contract.get("company_id"),
        "multi_source_contract": enhanced,
        "constructed_cells": constructed_cells,
        "working_capital_model_inputs": {
            "period_fragments": working_capital_inputs,
            "unresolved_periods": working_capital_unresolved,
        },
        "v4_inputs": {
            "annual_d3_d4_raw_observations": v4_inputs,
            "unresolved_periods": v4_unresolved,
        },
        "financial_driver_inputs": {
            "verified_observations": verified_observations,
            "cash_normalization_observation_groups": cash_groups,
            "capital_allocation_observation_groups": allocation_groups,
            "unresolved_raw_fields": unresolved_raw_fields,
        },
        "rights": {
            "working_capital_model_completion": "NOT_AUTHORIZED",
            "v4_candidate_admission": "NOT_AUTHORIZED",
            "financial_driver_judgment": "NOT_AUTHORIZED",
            "valuation": "NOT_AUTHORIZED",
            "investment": "NOT_AUTHORIZED",
        },
        "allowed_outputs": ["CONSUMER_INPUTS_ONLY", "RESEARCH_AGENDA"],
    }


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
    source_accesses = _enterprise_source_access_by_id(contract)
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
                frozen_source_id = _text(frozen_raw.get("source_id")) or _text(source.get("source_id"))
                source_access = source_accesses.get(str(frozen_source_id), {})
                if source.get("source_id") != source_access.get("source_id") or source.get("source_url") != source_access.get("official_url"):
                    findings.append(raw_path + ".source_must_match_authorized_identity")
                if not _is_static_official_pdf(source.get("source_url")):
                    findings.append(raw_path + ".source_url_must_be_static_official_pdf")
                if source.get("issuer_id") != "ISSUER:" + str(contract.get("company_id")):
                    findings.append(raw_path + ".source_issuer_must_match_contract_company")
                if source.get("report_period_end") != source_access.get("report_period_end"):
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
                actual_locator = _mapping(source.get("custodian_locator"))
                if isinstance(contract.get("source_accesses"), list):
                    if actual_locator != locator:
                        findings.append(
                            raw_path + ".source_custodian_locator_must_match_frozen_raw_input"
                        )
                elif set(actual_locator) != {"table_or_note", "line_item", "period_column"} or any(
                    not _text(actual_locator.get(locator_key))
                    for locator_key in ("table_or_note", "line_item", "period_column")
                ):
                    findings.append(raw_path + ".source_custodian_locator_invalid")
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
