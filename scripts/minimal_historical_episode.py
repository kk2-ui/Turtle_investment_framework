#!/usr/bin/env python3
"""Closed objects for one minimal, fixture-only historical episode.

This namespace intentionally does not import or extend V5, V6, H1, the
training program, or any investment/report control.  It describes exactly one
company/issuer/cutoff/metric/window chain and has no method-transfer right.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import re
from typing import Any


MEASUREMENT_CONTRACT_SCHEMA_VERSION = "turtle-minimal-historical-episode-measurement-contract.v1"
STATIC_EVIDENCE_SCHEMA_VERSION = "turtle-minimal-historical-episode-static-evidence.v1"
PREDICTION_SCHEMA_VERSION = "turtle-minimal-historical-episode-prediction.v1"
OUTCOME_ACCESS_SCHEMA_VERSION = "turtle-minimal-historical-episode-outcome-access.v1"
OBSERVATION_SCHEMA_VERSION = "turtle-minimal-historical-episode-observation.v1"
SETTLEMENT_REQUEST_SCHEMA_VERSION = "turtle-minimal-historical-episode-settlement-request.v1"
SETTLEMENT_SCHEMA_VERSION = "turtle-minimal-historical-episode-settlement.v1"

WINDOW_IDS = {"ONE_YEAR", "THREE_YEAR", "FIVE_YEAR"}
DIRECTIONS = {"INCREASE", "STABLE", "DECREASE"}
OFFICIAL_STATIC_FILING = "OFFICIAL_STATIC_FILING"
NO_METHOD_TRANSFER_RIGHTS = "NO_METHOD_TRANSFER_RIGHTS"
ALLOWED_OUTPUTS = ["MECHANICAL_SETTLEMENT_ONLY"]
PAGE_REFERENCE = re.compile(r"\bp(?:age)?\.?\s*\d+\b", re.IGNORECASE)

_REFERENCE_KEYS = {"measurement_contract_id", "measurement_contract_version"}
_EVIDENCE_REFERENCE_KEYS = {"evidence_receipt_id", "evidence_receipt_version"}
_ROLE_KEYS = {"forecaster_id", "custodian_id"}
_SOURCE_KEYS = {
    "source_id", "source_url", "source_type", "published_at", "issuer_id",
    "responsibility_boundary", "unit", "field_ref", "numeric_value",
}
_OUTCOME_SOURCE_KEYS = _SOURCE_KEYS - {"published_at"} | {"source_available_at"}
_CONTRACT_KEYS = {
    "schema_version", "measurement_contract_id", "measurement_contract_version", "company_id", "issuer_id",
    "cutoff_at", "metric_id", "window_id", "outcome_period_end", "responsibility_boundary", "unit",
    "settlement_tolerance", "roles", "object_class", "claim_class", "allowed_outputs",
    "method_transfer_rights",
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


def _evidence_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _EVIDENCE_REFERENCE_KEYS, path, findings)
    receipt_id = _require_text(item, "evidence_receipt_id", path, findings)
    version = item.get("evidence_receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.evidence_receipt_version_must_be_positive_integer")
        return None
    return {"evidence_receipt_id": receipt_id, "evidence_receipt_version": version} if receipt_id else None


def _fixed_permissions(item: dict[str, Any], path: str, findings: list[str]) -> None:
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append(f"{path}.allowed_outputs_must_be_mechanical_settlement_only")
    if item.get("method_transfer_rights") != NO_METHOD_TRANSFER_RIGHTS:
        findings.append(f"{path}.method_transfer_rights_must_be_no_method_transfer_rights")


def _identity_matches_contract(
    item: dict[str, Any], contract: dict[str, Any], path: str, findings: list[str], *, fields: tuple[str, ...],
) -> None:
    for field in fields:
        if item.get(field) != contract.get(field):
            findings.append(f"{path}.{field}_must_match_measurement_contract")


def _numeric(value: Any, path: str, findings: list[str]) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        findings.append(f"{path}_must_be_numeric")
        return None
    return float(value)


def _static_source(
    value: Any, *, contract: dict[str, Any], path: str, findings: list[str],
) -> dict[str, Any]:
    source = _closed(value, _SOURCE_KEYS, path, findings)
    for field in ("source_id", "source_url", "issuer_id", "responsibility_boundary", "unit", "field_ref"):
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
    for field in ("responsibility_boundary", "unit"):
        if source.get(field) != contract.get(field):
            findings.append(f"{path}.{field}_must_match_measurement_contract")
    field_ref = source.get("field_ref")
    if _text(field_ref) and not PAGE_REFERENCE.search(str(field_ref)):
        findings.append(f"{path}.field_ref_must_include_pdf_page")
    _numeric(source.get("numeric_value"), f"{path}.numeric_value", findings)
    return source


def _outcome_source(value: Any, *, contract: dict[str, Any], path: str, findings: list[str]) -> dict[str, Any]:
    source = _closed(value, _OUTCOME_SOURCE_KEYS, path, findings)
    for field in ("source_id", "source_url", "issuer_id", "responsibility_boundary", "unit", "field_ref"):
        _require_text(source, field, path, findings)
    if source.get("source_type") != OFFICIAL_STATIC_FILING:
        findings.append(f"{path}.source_type_must_be_official_static_filing")
    source_url = source.get("source_url")
    if _text(source_url) and (not str(source_url).startswith("https://") or not str(source_url).lower().endswith(".pdf")):
        findings.append(f"{path}.source_url_must_be_https_static_pdf")
    available_at = _instant(source.get("source_available_at"), f"{path}.source_available_at", findings)
    cutoff = _instant(contract.get("cutoff_at"), "measurement_contract.cutoff_at", findings)
    outcome_period_end = _date(contract.get("outcome_period_end"), "measurement_contract.outcome_period_end", findings)
    if available_at and cutoff and available_at <= cutoff:
        findings.append(f"{path}.source_available_at_must_follow_cutoff")
    if available_at and outcome_period_end and available_at.date() <= outcome_period_end:
        findings.append(f"{path}.source_available_at_must_follow_outcome_period_end")
    if source.get("issuer_id") != contract.get("issuer_id"):
        findings.append(f"{path}.issuer_id_must_match_measurement_contract")
    for field in ("responsibility_boundary", "unit"):
        if source.get(field) != contract.get(field):
            findings.append(f"{path}.{field}_must_match_measurement_contract")
    field_ref = source.get("field_ref")
    if _text(field_ref) and not PAGE_REFERENCE.search(str(field_ref)):
        findings.append(f"{path}.field_ref_must_include_pdf_page")
    _numeric(source.get("numeric_value"), f"{path}.numeric_value", findings)
    return source


def validate_measurement_contract(contract: Any) -> dict[str, Any]:
    """Validate one company/issuer/cutoff/metric/window measurement contract."""
    findings: list[str] = []
    item = _closed(contract, _CONTRACT_KEYS, "measurement_contract", findings)
    if item.get("schema_version") != MEASUREMENT_CONTRACT_SCHEMA_VERSION:
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
    _fixed_permissions(item, "measurement_contract", findings)
    return _result(findings, measurement_contract=deepcopy(item) if not findings else None)


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


def validate_observation(observation: Any, *, measurement_contract: Any) -> dict[str, Any]:
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
    observation_result = validate_observation(observation, measurement_contract=contract)
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
