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


def _reference(contract: dict[str, Any]) -> dict[str, Any]:
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
    return ["FORECAST_OUTCOME_ACQUISITION_ONLY"] if contract_kind == "FORECAST" else ["MECHANICAL_SETTLEMENT_ONLY"]


def _contract_context(contract: Any) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Normalise the project's two frozen Measurement Contract shapes.

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

    raise OutcomeMeasurementAcquisitionError(
        "measurement_contract_invalid: "
        + "; ".join(forecast_result["findings"][:3] or minimal_result["findings"][:3])
    )


def _is_static_official_pdf(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc.casefold() in _STATIC_HOSTS and parsed.path.casefold().endswith(".pdf")


def validate_registered_local_pdf_inventory(
    inventory: Any, *, measurement_contract: Any,
) -> dict[str, Any]:
    """Validate a closed, contract-bound local official-PDF inventory.

    This is a registration boundary, not a web acquisition client.  It accepts
    only already-local PDFs with static official URLs, so the reader cannot
    select a new issuer, web route, source version, or accounting period.
    """
    contract_kind, contract, _ = _contract_context(measurement_contract)
    findings: list[str] = []
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
    expected_custodian = contract.get("custodian_id") if contract_kind == "FORECAST" else _mapping(contract.get("roles")).get("custodian_id")
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
        if document.get("issuer_id") != contract.get("issuer_id"):
            findings.append(f"{path}_issuer_id_must_match_measurement_contract")
        if not _text(document.get("responsibility_boundary")):
            findings.append(f"{path}_responsibility_boundary_required")
        if _date(document.get("report_period_end")) is None:
            findings.append(f"{path}_report_period_end_invalid")
        if document.get("official_source_type") != "OFFICIAL_ANNUAL_REPORT":
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


def acquire_outcome_measurements(
    measurement_contract: Any,
    registered_pdf_inventory: Any,
    *,
    measurement_ids: list[str] | None = None,
    page_reader: PageReader = _pdf_pages,
) -> dict[str, Any]:
    """Acquire independent field observations from registered local PDFs.

    ``measurement_ids`` can only reduce the frozen contract's cells; it cannot
    introduce a field.  The call is pure and has no persistence or downstream
    settlement side effect.
    """
    contract_kind, contract, cells = _contract_context(measurement_contract)
    inventory_result = validate_registered_local_pdf_inventory(
        registered_pdf_inventory, measurement_contract=contract,
    )
    if not inventory_result["valid"]:
        raise OutcomeMeasurementAcquisitionError("registered_pdf_inventory_invalid: " + "; ".join(inventory_result["findings"]))
    inventory = inventory_result["inventory"]
    by_id = {str(cell["measurement_id"]): cell for cell in cells}
    if measurement_ids is None:
        selected = list(cells)
    else:
        if not isinstance(measurement_ids, list) or not measurement_ids or any(not _text(value) for value in measurement_ids):
            raise OutcomeMeasurementAcquisitionError("measurement_ids_must_be_nonempty_text_list_when_supplied")
        if len(set(measurement_ids)) != len(measurement_ids) or any(value not in by_id for value in measurement_ids):
            raise OutcomeMeasurementAcquisitionError("measurement_ids_must_be_unique_frozen_measurement_ids")
        selected = [by_id[value] for value in measurement_ids]
    observations = [_observe_cell(cell, documents=inventory["documents"], page_reader=page_reader) for cell in selected]
    return {
        "schema_version": SCHEMA_VERSION,
        "measurement_contract_ref": _reference(contract),
        "source_inventory_id": inventory["inventory_id"],
        "custodian_id": inventory["custodian_id"],
        "object_class": OBJECT_CLASS,
        "claim_class": CLAIM_CLASS,
        "allowed_outputs": _allowed_outputs(contract_kind),
        "observations": observations,
    }


def validate_acquisition_result(result: Any) -> dict[str, Any]:
    """Validate the narrow output shape without re-reading any PDF."""
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
