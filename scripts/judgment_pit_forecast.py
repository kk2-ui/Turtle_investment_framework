#!/usr/bin/env python3
"""PIT company-state forecasting controls, separate from causal-action V5.

This module governs the ordinary historical-training question: using only the
company state visible at a cutoff, how is its operating quality, cash formation
and permanent-loss risk expected to evolve?  It is deliberately a pure,
offline contract.  It does not obtain sources, outcomes, H2 actions, prices,
R-103 material, CJO authority, or any investment action.

V5 continues to own the much narrower ``did an action cause an outcome?``
question.  A forecast may later inform a CJO only through an independently
authorised valuation epoch; this module never grants that permission.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import math
import re
from typing import Any


FORECAST_EPOCH_ID = "TURTLE_PIT_COMPANY_FORECAST_EPOCH_V1"
FORECAST_EPOCH_ID_V2 = "TURTLE_PIT_COMPANY_FORECAST_EPOCH_V2"
FORECAST_EPOCH_ID_V3 = "TURTLE_PIT_COMPANY_FORECAST_EPOCH_V3"
FORECAST_EPOCH_ID_V4 = "TURTLE_PIT_COMPANY_FORECAST_EPOCH_V4"
FORECAST_EPOCH_ID_V5 = "TURTLE_PIT_COMPANY_FORECAST_EPOCH_V5"
FORECAST_EPOCH_ID_V6 = "TURTLE_PIT_COMPANY_FORECAST_EPOCH_V6"
FORECAST_SCHEMA_VERSION = "turtle-pit-company-state-forecast.v1"
FORECAST_SCHEMA_VERSION_V2 = "turtle-pit-company-state-forecast.v2"
FORECAST_SCHEMA_VERSION_V3 = "turtle-pit-company-state-forecast.v3"
FORECAST_SCHEMA_VERSION_V4 = "turtle-pit-company-state-forecast.v4"
FORECAST_SCHEMA_VERSION_V5 = "turtle-pit-company-state-forecast.v5"
FORECAST_SCHEMA_VERSION_V6 = "turtle-pit-company-state-forecast.v6"
TOURNAMENT_SCHEMA_VERSION = "turtle-relative-trajectory-tournament.v1"
SETTLEMENT_SCHEMA_VERSION = "turtle-pit-forecast-settlement.v1"
SETTLEMENT_SCHEMA_VERSION_V2 = "turtle-pit-forecast-settlement.v2"
OUTCOME_ACCESS_SCHEMA_VERSION = "turtle-pit-forecast-outcome-access-authorization.v1"
OUTCOME_ACCESS_SCHEMA_VERSION_V2 = "turtle-pit-forecast-outcome-access-authorization.v2"
OUTCOME_ACCESS_SCHEMA_VERSION_V3 = "turtle-pit-forecast-outcome-access-authorization.v3"
OUTCOME_MEASUREMENT_CONTRACT_SCHEMA_VERSION = "turtle-pit-forecast-outcome-measurement-contract.v1"
FORECAST_ACQUISITION_SCOPE_SCHEMA_VERSION = "turtle-pit-forecast-acquisition-scope.v1"
OUTCOME_OBSERVATION_RECEIPT_SCHEMA_VERSION = "turtle-pit-forecast-outcome-observation-receipt.v1"
PREFORCAST_EVIDENCE_RECEIPT_SCHEMA_VERSION = "turtle-pit-preforecast-evidence-receipt.v1"
CURATOR_FIELD_EXTRACTION_SCHEMA_VERSION = "preforecast-curator-field-extraction.v1"
SHADOW_SCHEMA_VERSION = "turtle-prospective-shadow-episode.v1"
SHADOW_SCHEMA_VERSION_V2 = "turtle-prospective-shadow-episode.v2"
SHADOW_SCHEMA_VERSION_V3 = "turtle-prospective-shadow-episode.v3"
PAIRING_SCHEMA_VERSION = "turtle-pit-forecast-pairing.v1"
PAIRING_SCHEMA_VERSION_V2 = "turtle-pit-forecast-pairing.v2"
PAIRING_SCHEMA_VERSION_V3 = "turtle-pit-forecast-pairing.v3"
PAIRED_EVALUATION_SCHEMA_VERSION = "turtle-pit-forecast-paired-evaluation.v1"
ATTRIBUTION_SCHEMA_VERSION = "turtle-pit-forecast-error-attribution.v1"

FORECAST_DIMENSIONS = (
    "NORMAL_EARNINGS",
    "ROIC_OR_OPERATING_MARGIN",
    "CASH_CONVERSION_AND_CAPEX_BURDEN",
    "LEVERAGE_AND_FINANCIAL_RESILIENCE",
    "COMPETITIVE_POSITION",
    "PERMANENT_LOSS_RISK",
)
FORECAST_WINDOWS = ("ONE_YEAR", "THREE_YEAR", "FIVE_YEAR")
ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS = {FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}
MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS = {
    FORECAST_SCHEMA_VERSION_V3, FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6,
}
CONTRACT_FIRST_FORECAST_SCHEMA_VERSIONS = {
    FORECAST_SCHEMA_VERSION_V2, FORECAST_SCHEMA_VERSION_V3, FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5,
    FORECAST_SCHEMA_VERSION_V6,
}
EVIDENCE_STATUSES = {"MODEL_UNCERTAIN", "EVIDENCE_INELIGIBLE"}
NON_RISK_LABELS = ("DETERIORATE", "STABLE", "IMPROVE")
RISK_LABELS = ("LOW", "BASELINE", "HIGH")
SETTLEMENT_STATUSES = {
    "OBSERVED", "CENSORED", "UNKNOWN", "NOT_DIAGNOSTIC", "MEASUREMENT_MISMATCH", "EVIDENCE_INELIGIBLE",
}
OUTCOME_OBSERVATION_STATUSES = {"OBSERVED_MEASUREMENT", "MEASUREMENT_MISMATCH"}
OUTCOME_ACCESS_ALLOWED_OUTPUTS = ["FORECAST_OUTCOME_ACQUISITION_ONLY"]
DIRECT_FORECAST_LEARNING_SCOPES = {
    "CALIBRATION", "COVERAGE", "STATE_DEFINITION", "UNCERTAINTY_POLICY", "BASELINE_PERFORMANCE",
}
CANDIDATE_FORECAST_LEARNING_SCOPES = {"EVIDENCE_PRIORITY", "RIVAL_HYPOTHESIS_METHOD"}
FORECAST_LEARNING_SCOPES = DIRECT_FORECAST_LEARNING_SCOPES | CANDIDATE_FORECAST_LEARNING_SCOPES | {"NOT_DIAGNOSTIC"}
FORECAST_FAILURE_LOCI = {
    "CALIBRATION", "COVERAGE", "STATE_DEFINITION", "UNCERTAINTY", "BASELINE_PERFORMANCE",
    "EVIDENCE_PRIORITY", "RIVAL_HYPOTHESIS_METHOD", "OUTCOME_MEASUREMENT",
}
PAGE_REFERENCE = re.compile(r"\bp(?:age)?\.?\s*\d+\b", re.IGNORECASE)

_FORECAST_KEYS = {
    "schema_version", "forecast_id", "forecast_epoch_id", "company_id", "issuer_id", "subject_id", "cutoff_at",
    "forecast_windows", "source_packet_refs", "model_memory_mitigation", "dimensions", "object_class",
    "claim_class", "allowed_outputs", "decision_contract_ref", "outcome_measurement_contract_ref",
    "applied_policy_change_ids", "preforecast_evidence_receipt_ref", "forecast_acquisition_scope_ref",
    "forecast_method_ref",
}
_DECISION_CONTRACT_REF_KEYS = {"contract_id", "contract_version"}
_OUTCOME_MEASUREMENT_CONTRACT_REF_KEYS = {"measurement_contract_id", "measurement_contract_version"}
_FORECAST_ACQUISITION_SCOPE_REF_KEYS = {"scope_id", "scope_version"}
_PREFORCAST_EVIDENCE_RECEIPT_REF_KEYS = {"evidence_receipt_id", "evidence_receipt_version"}
_FORECAST_METHOD_REF_KEYS = {"program_id", "method_version", "method_frozen_at", "method_freeze_recorded_at"}
_MITIGATION_KEYS = {
    "mode", "isolated_forecaster_id", "known_outcome_access", "price_access", "post_cutoff_access",
    "network_route", "notes",
}
_DIMENSION_KEYS = {
    "dimension_id", "evidence_status", "evidence_refs", "forecast_by_window", "rationale", "measurement_gaps",
}
_EVIDENCE_REF_KEYS = {"source_id", "published_at", "field_ref", "field_id"}
_PREFORCAST_EVIDENCE_RECEIPT_KEYS = {
    "schema_version", "evidence_receipt_id", "evidence_receipt_version", "h1_source_packet_ref", "company_id",
    "issuer_id", "cutoff_at", "curator_id", "fields", "object_class", "claim_class", "allowed_outputs",
}
_PREFORCAST_EVIDENCE_FIELD_KEYS = {
    "field_id", "source_id", "source_url", "source_type", "published_at", "period_end", "issuer_id", "responsibility_unit_id",
    "perimeter_id", "unit", "field_ref", "numeric_value", "label",
}
_CURATOR_FIELD_EXTRACTION_KEYS = {"schema_version", "shape", "records", "unavailable_records"}
_CURATOR_FIELD_EXTRACTION_SHAPE_KEYS = {"record_fields", "additional_record_fields_permitted"}
_CURATOR_FIELD_EXTRACTION_RECORD_KEYS = {
    "source_id", "source_url", "published_at", "period_end", "issuer_id", "responsibility_unit_id", "perimeter_id",
    "unit", "field_id", "pdf_page_reference", "numeric_value", "label_zh",
}
_MEASUREMENT_GAP_KEYS = {"measurement_id", "reason", "evidence_refs"}
_WINDOW_FORECAST_KEYS = {
    "window_id", "baseline_reference", "probabilities", "event_statement", "event_occurs_probability",
}
_PROBABILITY_KEYS = {"label", "probability"}
_TOURNAMENT_KEYS = {
    "schema_version", "tournament_id", "forecast_epoch_id", "cutoff_at", "universe_id", "source_packet_refs",
    "ranked_company_ids", "forecast_ids", "dimension_rankings", "object_class", "claim_class", "allowed_outputs",
}
_RANKING_KEYS = {"dimension_id", "ordered_company_ids", "unranked_company_ids", "rationale"}
_SETTLEMENT_KEYS = {
    "schema_version", "settlement_id", "forecast_id", "company_id", "cutoff_at", "settled_at", "custodian_id",
    "outcome_access_authorized", "dimension_settlements", "object_class", "claim_class", "allowed_outputs",
    "outcome_measurement_contract_ref",
}
_OUTCOME_ACCESS_KEYS = {
    "schema_version", "authorization_id", "forecast_id", "company_id", "cutoff_at", "custodian_id", "authorized_at",
    "outcome_windows", "object_class", "claim_class", "allowed_outputs", "outcome_measurement_contract_ref",
    "forecast_acquisition_scope_ref",
}
_DIMENSION_SETTLEMENT_KEYS = {
    "dimension_id", "window_id", "status", "realized_label", "outcome_source", "realized_measurement",
    "outcome_observation_ref",
}
_OUTCOME_SOURCE_KEYS = {"source_id", "source_available_at", "field_ref"}
_OUTCOME_SOURCE_KEYS_V2 = _OUTCOME_SOURCE_KEYS | {
    "source_url", "source_field_id", "official_source_type", "issuer_id", "responsibility_boundary", "unit", "outcome_period_end",
    "source_available_date", "source_available_precision",
}
_REALIZED_MEASUREMENT_KEYS = {
    "measurement_id", "measurement_kind", "numeric_value", "boolean_value", "unit",
    "outcome_period_end", "responsibility_boundary", "source_components",
}
_OUTCOME_SOURCE_COMPONENT_KEYS = {
    "source_id", "source_url", "source_available_at", "field_id", "field_ref", "official_source_type", "numeric_value",
    "issuer_id", "responsibility_boundary", "unit", "outcome_period_end", "source_available_date", "source_available_precision",
}
_OUTCOME_SOURCE_V2_REQUIRED_KEYS = _OUTCOME_SOURCE_KEYS_V2 - {"source_available_at", "source_available_date", "source_available_precision"}
_OUTCOME_SOURCE_COMPONENT_REQUIRED_KEYS = _OUTCOME_SOURCE_COMPONENT_KEYS - {"source_available_at", "source_available_date", "source_available_precision"}
_OUTCOME_MEASUREMENT_CONTRACT_KEYS = {
    "schema_version", "measurement_contract_id", "measurement_contract_version", "decision_contract_ref",
    "company_id", "issuer_id", "cutoff_at", "custodian_id", "applied_policy_change_ids", "cells",
    "object_class", "claim_class", "allowed_outputs",
}
_FORECAST_ACQUISITION_SCOPE_KEYS = {
    "schema_version", "scope_id", "scope_version", "decision_contract_ref", "outcome_measurement_contract_ref",
    "company_id", "issuer_id", "cutoff_at", "custodian_id", "cells", "object_class", "claim_class", "allowed_outputs",
}
_FORECAST_ACQUISITION_SCOPE_CELL_KEYS = {"dimension_id", "window_id", "measurement_id"}
_OUTCOME_MEASUREMENT_CELL_KEYS = {
    "dimension_id", "window_id", "measurement_id", "measurement_kind", "outcome_period_end",
    "responsibility_boundary", "unit", "official_source_type", "source_field_id", "metric_definition",
    "measurement_formula", "mismatch_rules",
    "lower_threshold", "upper_threshold", "label_order", "event_definition",
}
_MEASUREMENT_FORMULA_KEYS = {
    "formula_kind", "value_field_id", "numerator_field_id", "denominator_field_id",
}
_OUTCOME_OBSERVATION_REF_KEYS = {"observation_id"}
_OUTCOME_OBSERVATION_RECEIPT_KEYS = {
    "schema_version", "observation_id", "forecast_id", "outcome_measurement_contract_ref", "company_id", "issuer_id",
    "cutoff_at", "custodian_id", "observed_at", "dimension_id", "window_id", "outcome_source",
    "observation_status", "realized_measurement", "mismatch_rule", "mismatch_detail", "object_class", "claim_class",
    "allowed_outputs",
}
_PAIRING_KEYS = {
    "schema_version", "pairing_id", "forecast_id", "company_id", "cutoff_at", "task_contract_ref",
    "evidence_budget_id", "source_packet_refs", "baseline_method_id", "enhanced_method_id", "baseline_cells",
    "object_class", "claim_class", "allowed_outputs",
    "holdout_binding",
}
_BASELINE_CELL_KEYS = {"dimension_id", "window_id", "probabilities", "event_statement", "event_occurs_probability"}
_PAIRED_EVALUATION_KEYS = {
    "schema_version", "evaluation_id", "pairing_id", "forecast_id", "settlement_id", "evaluated_at",
    "object_class", "claim_class", "allowed_outputs",
}
_ATTRIBUTION_KEYS = {
    "schema_version", "attribution_id", "forecast_id", "settlement_id", "attributed_at", "reviewer_id",
    "learning_scope", "disposition", "failure_locus", "cell_refs", "policy_change", "paired_evaluation_id",
    "holdout", "object_class", "claim_class", "allowed_outputs",
}
_CELL_REF_KEYS = {"dimension_id", "window_id"}
_POLICY_CHANGE_KEYS = {"change_id", "statement", "effective_from_cutoff_at"}
_HOLDOUT_KEYS = {
    "training_company_ids", "holdout_company_ids", "training_cutoff_through", "holdout_cutoff_from",
}
_HOLDOUT_BINDING_KEYS = {
    "program_id", "method_version", "holdout_training_episode_id", "company_id", "company_cluster_id",
    "cutoff_at", "outcome_not_before", "method_frozen_at", "method_freeze_recorded_at", "evaluated_cells",
}
_HOLDOUT_BINDING_V3_KEYS = _HOLDOUT_BINDING_KEYS | {
    "outcome_window_ends_at", "training_company_cluster_ids", "training_outcome_windows",
}
_HOLDOUT_BINDING_REQUEST_KEYS = {"program_id", "holdout_training_episode_id", "evaluated_cell_refs"}
_HOLDOUT_BINDING_CELL_KEYS = {"dimension_id", "window_id", "outcome_period_end"}
_HOLDOUT_TRAINING_WINDOW_KEYS = {
    "training_episode_id", "company_cluster_id", "opens_after", "closes_at",
}
_SHADOW_KEYS = {
    "schema_version", "shadow_episode_id", "forecast_epoch_id", "company_id", "issuer_id", "cutoff_at",
    "forecast_id", "outcome_windows", "custodian_id", "status", "object_class", "claim_class", "allowed_outputs",
}
_FORECAST_SHADOW_KEYS = _SHADOW_KEYS | {
    "decision_contract_ref", "outcome_measurement_contract_ref",
    "preforecast_evidence_receipt_ref", "forecast_acquisition_scope_ref", "resolution_calendar",
}
_SHADOW_RESOLUTION_KEYS = {"window_id", "resolution_due_at"}
_SIGNAL_SHADOW_KEYS = {
    "schema_version", "shadow_episode_id", "source_freeze_ref", "company_id", "cutoff_at", "outcome_windows",
    "custodian_id", "status", "object_class", "claim_class", "allowed_outputs",
}
_SIGNAL_SHADOW_FREEZE_KEYS = {"freeze_id", "freeze_path", "cutoff_at", "frozen_at", "allowed_source_ids"}
_SIGNAL_SHADOW_WINDOW_KEYS = {"signal_id", "metric", "window_label", "resolution_due_at"}

ISOLATED_SUBMISSION_SCHEMA_VERSION = "turtle-pit-company-forecast-submission.v1"
_ISOLATED_SUBMISSION_KEYS = {
    "schema_version", "pilot_id", "cutoff_at", "model_memory_mitigation", "source_packet_ref", "companies", "relative_tournament",
}
_ISOLATED_MITIGATION_KEYS = {
    "status", "curator", "network_access", "outcome_access", "results_access", "price_access", "prohibited_materials", "allowed_evidence_rule",
}
_ISOLATED_PACKET_KEYS = {"path", "cohort_id", "use_limit"}
_ISOLATED_COMPANY_KEYS = {"company_id", "panel_disposition", "verified_cutoff_state", "forecast_dimensions"}
_ISOLATED_STATE_KEYS = {"statement", "evidence"}
_ISOLATED_EVIDENCE_KEYS = {"source_id", "publication_date", "pdf_page_ref", "field_ref"}
_ISOLATED_DIMENSION_KEYS = {
    "status", "event", "horizons", "evidence", "reason", "cash_conversion", "capex_burden",
}
_ISOLATED_HORIZON_KEYS = {"years_forward", "probability"}
_ISOLATED_TOURNAMENT_KEYS = {
    "status", "eligible_company_ids", "excluded_lifecycle_boundary_company_ids", "dimensions",
}
_ISOLATED_TOURNAMENT_DIMENSION_KEYS = {"ranking", "unranked_company_ids", "status", "status_note", "reason", "ranking_direction", "evidence"}

_ISOLATED_DIMENSION_MAP = {
    "normal_earnings": "NORMAL_EARNINGS",
    "roic_or_operating_margin": "ROIC_OR_OPERATING_MARGIN",
    "leverage_or_financial_resilience": "LEVERAGE_AND_FINANCIAL_RESILIENCE",
    "competitive_position": "COMPETITIVE_POSITION",
    "permanent_loss_risk": "PERMANENT_LOSS_RISK",
}
_ISOLATED_TOURNAMENT_DIMENSION_MAP = {
    "normal_earnings_persistence": "NORMAL_EARNINGS",
    "operating_margin_trajectory": "ROIC_OR_OPERATING_MARGIN",
    "cash_conversion_and_capex_burden": "CASH_CONVERSION_AND_CAPEX_BURDEN",
    "financial_resilience": "LEVERAGE_AND_FINANCIAL_RESILIENCE",
    "competitive_position": "COMPETITIVE_POSITION",
    "permanent_loss_risk": "PERMANENT_LOSS_RISK",
}


def _result(findings: list[str], **payload: Any) -> dict[str, Any]:
    return {"valid": not findings, "findings": findings, **payload}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _closed(
    value: Any, allowed: set[str], path: str, findings: list[str], *, required: set[str] | None = None,
) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
        return item
    unexpected = sorted(set(item).difference(allowed))
    if unexpected:
        findings.extend(f"{path}_contains_unapproved_field:{field}" for field in unexpected)
    missing = sorted((allowed if required is None else required).difference(item))
    if missing:
        findings.extend(f"{path}_missing_required_field:{field}" for field in missing)
    return item


def _require_text(value: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    raw = value.get(field)
    if not _text(raw):
        findings.append(f"{path}.{field}_required")
        return ""
    return str(raw).strip()


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


def _source_date(value: Any, path: str, findings: list[str]) -> date | None:
    if not _text(value):
        findings.append(f"{path}_must_be_iso_date_or_datetime")
        return None
    raw = str(value)
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        findings.append(f"{path}_must_be_iso_date_or_datetime")
        return None


def _outcome_source_availability(
    source: dict[str, Any], path: str, findings: list[str],
) -> tuple[datetime | None, date | None]:
    """Resolve an exact timestamp or a conservative date-only availability bound.

    Older receipts retain their timestamp-only shape.  Static exchange records
    that canonically expose only a publication date may use ``DATE_ONLY``;
    later chronology checks then require a strictly later calendar day instead
    of inventing an intraday publication time.
    """
    precision = source.get("source_available_precision")
    if precision is None:
        return _instant(source.get("source_available_at"), path + ".source_available_at", findings), None
    if precision == "TIMESTAMP":
        if source.get("source_available_date") is not None:
            findings.append(path + ".timestamp_cannot_include_source_available_date")
        return _instant(source.get("source_available_at"), path + ".source_available_at", findings), None
    if precision == "DATE_ONLY":
        if source.get("source_available_at") is not None:
            findings.append(path + ".date_only_cannot_include_source_available_at")
        return None, _source_date(source.get("source_available_date"), path + ".source_available_date", findings)
    findings.append(path + ".source_available_precision_invalid")
    return None, None


def _source_follows_cutoff(source_at: datetime | None, source_day: date | None, cutoff: datetime) -> bool:
    return source_at > cutoff if source_at is not None else source_day is not None and source_day > cutoff.date()


def _source_precedes_receipt(source_at: datetime | None, source_day: date | None, receipt_at: datetime) -> bool:
    return source_at <= receipt_at if source_at is not None else source_day is not None and source_day < receipt_at.date()


def _reference(value: Any, path: str, findings: list[str]) -> tuple[str, int] | None:
    item = _mapping(value)
    unexpected = sorted(set(item).difference({"receipt_id", "receipt_version"}))
    if unexpected:
        findings.extend(f"{path}_contains_unapproved_field:{field}" for field in unexpected)
    receipt_id = _require_text(item, "receipt_id", path, findings)
    version = item.get("receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.receipt_version_must_be_positive_integer")
        return None
    return (receipt_id, version) if receipt_id else None


def _decision_contract_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _DECISION_CONTRACT_REF_KEYS, path, findings)
    contract_id = _require_text(item, "contract_id", path, findings)
    version = item.get("contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.contract_version_must_be_positive_integer")
        return None
    return {"contract_id": contract_id, "contract_version": version} if contract_id else None


def _outcome_measurement_contract_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _OUTCOME_MEASUREMENT_CONTRACT_REF_KEYS, path, findings)
    contract_id = _require_text(item, "measurement_contract_id", path, findings)
    version = item.get("measurement_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.measurement_contract_version_must_be_positive_integer")
        return None
    return {"measurement_contract_id": contract_id, "measurement_contract_version": version} if contract_id else None


def _forecast_acquisition_scope_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _FORECAST_ACQUISITION_SCOPE_REF_KEYS, path, findings)
    scope_id = _require_text(item, "scope_id", path, findings)
    version = item.get("scope_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.scope_version_must_be_positive_integer")
        return None
    return {"scope_id": scope_id, "scope_version": version} if scope_id else None


def _preforecast_evidence_receipt_reference(value: Any, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _PREFORCAST_EVIDENCE_RECEIPT_REF_KEYS, path, findings)
    receipt_id = _require_text(item, "evidence_receipt_id", path, findings)
    version = item.get("evidence_receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.evidence_receipt_version_must_be_positive_integer")
        return None
    return {"evidence_receipt_id": receipt_id, "evidence_receipt_version": version} if receipt_id else None


def _measurement_kind_for_forecast_window(window: Any) -> str | None:
    item = _mapping(window)
    if "probabilities" in item:
        return "ORDINAL_THRESHOLD"
    if "event_statement" in item and "event_occurs_probability" in item:
        return "BINARY_EVENT"
    return None


def _measurement_contract_cell_index(contract: Any) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(cell.get("dimension_id")), str(cell.get("window_id"))): cell
        for cell in _items(_mapping(contract).get("cells")) if isinstance(cell, dict)
    }


def _measurement_formula(
    value: Any, *, path: str, findings: list[str], required: bool,
) -> dict[str, Any] | None:
    if value is None:
        if required:
            findings.append(f"{path}_required")
        return None
    item = _closed(
        value, _MEASUREMENT_FORMULA_KEYS, path, findings,
        required={"formula_kind"},
    )
    kind = item.get("formula_kind")
    if kind == "DIRECT_NUMERIC":
        _require_text(item, "value_field_id", path, findings)
        for field in ("numerator_field_id", "denominator_field_id"):
            if item.get(field) is not None:
                findings.append(f"{path}.direct_numeric_cannot_include_{field}")
    elif kind == "RATIO":
        numerator = _require_text(item, "numerator_field_id", path, findings)
        denominator = _require_text(item, "denominator_field_id", path, findings)
        if numerator and denominator and numerator == denominator:
            findings.append(f"{path}.ratio_fields_must_differ")
        if item.get("value_field_id") is not None:
            findings.append(f"{path}.ratio_cannot_include_value_field_id")
    else:
        findings.append(f"{path}.formula_kind_invalid")
    return item


def validate_forecast_outcome_measurement_contract(contract: Any) -> dict[str, Any]:
    """Freeze custodian-readable outcome definitions before the forecast exists.

    This object deliberately contains no probabilities, forecast rationale,
    outcome source IDs, prices, or realised values.  It is the contract that
    turns a later official field into one, and only one, forecast-cell label.
    """
    findings: list[str] = []
    item = _closed(contract, _OUTCOME_MEASUREMENT_CONTRACT_KEYS, "measurement_contract", findings)
    if item.get("schema_version") != OUTCOME_MEASUREMENT_CONTRACT_SCHEMA_VERSION:
        findings.append("measurement_contract.schema_version_invalid")
    _require_text(item, "measurement_contract_id", "measurement_contract", findings)
    version = item.get("measurement_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("measurement_contract.measurement_contract_version_must_be_positive_integer")
    _decision_contract_reference(item.get("decision_contract_ref"), "measurement_contract.decision_contract_ref", findings)
    _require_text(item, "company_id", "measurement_contract", findings)
    _require_text(item, "issuer_id", "measurement_contract", findings)
    cutoff = _instant(item.get("cutoff_at"), "measurement_contract.cutoff_at", findings)
    _require_text(item, "custodian_id", "measurement_contract", findings)
    policy_ids = item.get("applied_policy_change_ids")
    if not isinstance(policy_ids, list) or any(not _text(policy_id) for policy_id in policy_ids) or len(set(policy_ids)) != len(policy_ids):
        findings.append("measurement_contract.applied_policy_change_ids_must_be_unique_text_list")
    if item.get("object_class") != "FORECAST_OUTCOME_MEASUREMENT_CONTRACT":
        findings.append("measurement_contract.object_class_invalid")
    if item.get("claim_class") != "PRE_OUTCOME_SETTLEMENT_DEFINITION":
        findings.append("measurement_contract.claim_class_invalid")
    if item.get("allowed_outputs") != OUTCOME_ACCESS_ALLOWED_OUTPUTS:
        findings.append("measurement_contract.allowed_outputs_must_remain_custodian_acquisition_only")

    expected_keys = {(dimension_id, window_id) for dimension_id in FORECAST_DIMENSIONS for window_id in FORECAST_WINDOWS}
    seen: set[tuple[str, str]] = set()
    window_periods: dict[str, date] = {}
    for index, raw in enumerate(_items(item.get("cells"))):
        cell = _closed(
            raw, _OUTCOME_MEASUREMENT_CELL_KEYS, f"measurement_contract.cells[{index}]", findings,
            required={
                "dimension_id", "window_id", "measurement_id", "measurement_kind", "outcome_period_end",
                "responsibility_boundary", "unit", "official_source_type", "source_field_id", "metric_definition",
                "mismatch_rules",
            },
        )
        dimension_id, window_id = cell.get("dimension_id"), cell.get("window_id")
        key = (str(dimension_id), str(window_id))
        if dimension_id not in FORECAST_DIMENSIONS or window_id not in FORECAST_WINDOWS or key in seen:
            findings.append(f"measurement_contract.cells[{index}].dimension_or_window_invalid_or_duplicate")
            continue
        seen.add(key)
        _require_text(cell, "measurement_id", f"measurement_contract.cells[{index}]", findings)
        kind = cell.get("measurement_kind")
        if kind not in {"ORDINAL_THRESHOLD", "BINARY_EVENT"}:
            findings.append(f"measurement_contract.cells[{index}].measurement_kind_invalid")
        period_end = _source_date(cell.get("outcome_period_end"), f"measurement_contract.cells[{index}].outcome_period_end", findings)
        if cutoff and period_end and period_end <= cutoff.date():
            findings.append(f"measurement_contract.cells[{index}].outcome_period_end_must_follow_cutoff")
        if period_end:
            existing_period = window_periods.setdefault(str(window_id), period_end)
            if existing_period != period_end:
                findings.append(f"measurement_contract.cells[{index}].window_must_have_one_shared_outcome_period_end")
        for field in ("responsibility_boundary", "unit", "source_field_id", "metric_definition"):
            _require_text(cell, field, f"measurement_contract.cells[{index}]", findings)
        if cell.get("official_source_type") != "OFFICIAL_ANNUAL_REPORT":
            findings.append(f"measurement_contract.cells[{index}].official_source_type_must_be_annual_report")
        rules = _items(cell.get("mismatch_rules"))
        if not rules or any(not _text(rule) for rule in rules):
            findings.append(f"measurement_contract.cells[{index}].mismatch_rules_must_be_nonempty_text_list")
        if kind == "ORDINAL_THRESHOLD":
            _measurement_formula(
                cell.get("measurement_formula"), path=f"measurement_contract.cells[{index}].measurement_formula",
                findings=findings, required=True,
            )
            labels = _items(cell.get("label_order"))
            if labels != list(_labels_for(str(dimension_id))):
                findings.append(f"measurement_contract.cells[{index}].label_order_must_match_frozen_dimension_labels")
            lower, upper = cell.get("lower_threshold"), cell.get("upper_threshold")
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in (lower, upper)) or float(lower) >= float(upper):
                findings.append(f"measurement_contract.cells[{index}].ordinal_thresholds_invalid")
            if cell.get("event_definition") is not None:
                findings.append(f"measurement_contract.cells[{index}].ordinal_contract_cannot_include_event_definition")
        elif kind == "BINARY_EVENT":
            _require_text(cell, "event_definition", f"measurement_contract.cells[{index}]", findings)
            for field in ("lower_threshold", "upper_threshold", "label_order", "measurement_formula"):
                if cell.get(field) is not None:
                    findings.append(f"measurement_contract.cells[{index}].binary_contract_cannot_include_{field}")
    if seen != expected_keys:
        findings.append("measurement_contract.must_define_each_dimension_and_window_once")
    if set(window_periods) == set(FORECAST_WINDOWS):
        if not (window_periods["ONE_YEAR"] < window_periods["THREE_YEAR"] < window_periods["FIVE_YEAR"]):
            findings.append("measurement_contract.window_period_ends_must_increase_one_three_five")
    return _result(findings, measurement_contract=deepcopy(item) if not findings else None)


def validate_forecast_acquisition_scope(scope: Any, *, measurement_contract: Any) -> dict[str, Any]:
    """Validate the custodian-readable collection scope before a Forecast V5.

    This is deliberately not a forecast and cannot contain probabilities,
    rationales, realised values, prices, or outcome sources.  It states exactly
    which already-defined Measurement Contract cells the independent custodian
    may later collect.  A V5 forecast must subsequently prove its
    ``MODEL_UNCERTAIN`` dimensions match this immutable scope.
    """
    findings: list[str] = []
    item = _closed(
        scope, _FORECAST_ACQUISITION_SCOPE_KEYS, "acquisition_scope", findings,
        required=_FORECAST_ACQUISITION_SCOPE_KEYS,
    )
    contract_validation = validate_forecast_outcome_measurement_contract(measurement_contract)
    findings.extend(f"acquisition_scope.measurement_contract:{finding}" for finding in contract_validation["findings"])
    contract = _mapping(contract_validation.get("measurement_contract"))
    if item.get("schema_version") != FORECAST_ACQUISITION_SCOPE_SCHEMA_VERSION:
        findings.append("acquisition_scope.schema_version_invalid")
    _require_text(item, "scope_id", "acquisition_scope", findings)
    version = item.get("scope_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("acquisition_scope.scope_version_must_be_positive_integer")
    decision_ref = _decision_contract_reference(item.get("decision_contract_ref"), "acquisition_scope.decision_contract_ref", findings)
    measurement_ref = _outcome_measurement_contract_reference(
        item.get("outcome_measurement_contract_ref"), "acquisition_scope.outcome_measurement_contract_ref", findings,
    )
    if contract:
        expected_measurement_ref = {
            "measurement_contract_id": contract.get("measurement_contract_id"),
            "measurement_contract_version": contract.get("measurement_contract_version"),
        }
        if measurement_ref and measurement_ref != expected_measurement_ref:
            findings.append("acquisition_scope.measurement_contract_ref_must_match_frozen_contract")
        if decision_ref and decision_ref != contract.get("decision_contract_ref"):
            findings.append("acquisition_scope.decision_contract_ref_must_match_measurement_contract")
        for field in ("company_id", "issuer_id", "cutoff_at", "custodian_id"):
            if item.get(field) != contract.get(field):
                findings.append(f"acquisition_scope.{field}_must_match_measurement_contract")
    for field in ("company_id", "issuer_id", "custodian_id"):
        _require_text(item, field, "acquisition_scope", findings)
    _instant(item.get("cutoff_at"), "acquisition_scope.cutoff_at", findings)
    if item.get("object_class") != "FORECAST_ACQUISITION_SCOPE":
        findings.append("acquisition_scope.object_class_invalid")
    if item.get("claim_class") != "PRE_OUTCOME_CUSTODIAN_COLLECTION_SCOPE":
        findings.append("acquisition_scope.claim_class_invalid")
    if item.get("allowed_outputs") != OUTCOME_ACCESS_ALLOWED_OUTPUTS:
        findings.append("acquisition_scope.allowed_outputs_must_remain_custodian_acquisition_only")

    contract_cells = _measurement_contract_cell_index(contract)
    seen: set[tuple[str, str]] = set()
    by_dimension: dict[str, set[str]] = {}
    for index, raw in enumerate(_items(item.get("cells"))):
        cell = _closed(
            raw, _FORECAST_ACQUISITION_SCOPE_CELL_KEYS, f"acquisition_scope.cells[{index}]", findings,
            required=_FORECAST_ACQUISITION_SCOPE_CELL_KEYS,
        )
        dimension_id, window_id = cell.get("dimension_id"), cell.get("window_id")
        key = (str(dimension_id), str(window_id))
        if dimension_id not in FORECAST_DIMENSIONS or window_id not in FORECAST_WINDOWS or key in seen:
            findings.append(f"acquisition_scope.cells[{index}].dimension_or_window_invalid_or_duplicate")
            continue
        seen.add(key)
        by_dimension.setdefault(str(dimension_id), set()).add(str(window_id))
        frozen_cell = contract_cells.get(key)
        if frozen_cell is None:
            findings.append(f"acquisition_scope.cells[{index}].cell_not_in_measurement_contract")
        elif cell.get("measurement_id") != frozen_cell.get("measurement_id"):
            findings.append(f"acquisition_scope.cells[{index}].measurement_id_must_match_measurement_contract")
    if not seen:
        findings.append("acquisition_scope.cells_must_not_be_empty")
    for dimension_id, windows in by_dimension.items():
        if windows != set(FORECAST_WINDOWS):
            findings.append(f"acquisition_scope.{dimension_id}_must_collect_all_forecast_windows")
    return _result(findings, acquisition_scope=deepcopy(item) if not findings else None)


def validate_forecast_outcome_observation_receipt(
    receipt: Any, *, forecast: Any, measurement_contract: Any, acquisition_scope: Any | None = None,
) -> dict[str, Any]:
    """Validate one custodian-extracted field before it can enter settlement.

    The receipt is the sole place a raw post-cutoff value enters this epoch.
    A settlement references the immutable receipt; it never re-declares an
    issuer, source field, perimeter, unit, period, or value.
    """
    findings: list[str] = []
    item = _closed(
        receipt, _OUTCOME_OBSERVATION_RECEIPT_KEYS, "outcome_observation", findings,
        required=_OUTCOME_OBSERVATION_RECEIPT_KEYS - {"realized_measurement", "mismatch_rule", "mismatch_detail"},
    )
    frozen = _mapping(forecast)
    contract = _mapping(measurement_contract)
    if item.get("schema_version") != OUTCOME_OBSERVATION_RECEIPT_SCHEMA_VERSION:
        findings.append("outcome_observation.schema_version_invalid")
    _require_text(item, "observation_id", "outcome_observation", findings)
    for field in ("forecast_id", "company_id", "issuer_id", "cutoff_at"):
        if item.get(field) != frozen.get(field):
            findings.append(f"outcome_observation.{field}_must_match_frozen_forecast")
    ref = _outcome_measurement_contract_reference(
        item.get("outcome_measurement_contract_ref"), "outcome_observation.outcome_measurement_contract_ref", findings,
    )
    expected_ref = {
        "measurement_contract_id": contract.get("measurement_contract_id"),
        "measurement_contract_version": contract.get("measurement_contract_version"),
    }
    if ref and ref != expected_ref:
        findings.append("outcome_observation.measurement_contract_must_match_registered_contract")
    _require_text(item, "custodian_id", "outcome_observation", findings)
    observed_at = _instant(item.get("observed_at"), "outcome_observation.observed_at", findings)
    dimension_id, window_id = item.get("dimension_id"), item.get("window_id")
    key = (str(dimension_id), str(window_id))
    forecast_dimension = next(
        (
            candidate for candidate in _items(frozen.get("dimensions"))
            if _mapping(candidate).get("dimension_id") == dimension_id
        ),
        None,
    )
    if _mapping(forecast_dimension).get("evidence_status") != "MODEL_UNCERTAIN":
        findings.append("outcome_observation.cannot_observe_unforecast_dimension")
    if frozen.get("schema_version") in ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        scope_validation = validate_forecast_acquisition_scope(acquisition_scope, measurement_contract=contract)
        findings.extend(f"outcome_observation.acquisition_scope:{finding}" for finding in scope_validation["findings"])
        scope_cells = {
            (str(entry.get("dimension_id")), str(entry.get("window_id")))
            for entry in _items(_mapping(scope_validation.get("acquisition_scope")).get("cells"))
            if isinstance(entry, dict)
        }
        if key not in scope_cells:
            findings.append("outcome_observation.cell_not_in_frozen_acquisition_scope")
    cell = _measurement_contract_cell_index(contract).get(key)
    if cell is None:
        findings.append("outcome_observation.cell_not_in_measurement_contract")
    observation_status = item.get("observation_status")
    if observation_status not in OUTCOME_OBSERVATION_STATUSES:
        findings.append("outcome_observation.observation_status_invalid")
    materialized = {
        "outcome_source": item.get("outcome_source"),
        "realized_measurement": item.get("realized_measurement"),
        "realized_label": None,
        "issuer_id": frozen.get("issuer_id"),
    }
    if cell is not None and observation_status == "OBSERVED_MEASUREMENT":
        if item.get("mismatch_rule") is not None or item.get("mismatch_detail") is not None:
            findings.append("outcome_observation.observed_measurement_cannot_claim_mismatch")
        _validate_v3_realized_measurement(
            materialized, cell=cell, path="outcome_observation", findings=findings, require_label=False,
            expected_issuer_id=frozen.get("issuer_id"),
        )
    elif cell is not None and observation_status == "MEASUREMENT_MISMATCH":
        if item.get("realized_measurement") is not None:
            findings.append("outcome_observation.measurement_mismatch_cannot_claim_realized_measurement")
        mismatch_rule = _require_text(item, "mismatch_rule", "outcome_observation", findings)
        _require_text(item, "mismatch_detail", "outcome_observation", findings)
        if mismatch_rule and mismatch_rule not in _items(cell.get("mismatch_rules")):
            findings.append("outcome_observation.mismatch_rule_must_be_frozen_in_measurement_contract")
        source = _closed(
            item.get("outcome_source"), _OUTCOME_SOURCE_KEYS_V2, "outcome_observation.outcome_source", findings,
            required=_OUTCOME_SOURCE_V2_REQUIRED_KEYS,
        )
        _require_text(source, "source_id", "outcome_observation.outcome_source", findings)
        source_url = _require_text(source, "source_url", "outcome_observation.outcome_source", findings)
        if source_url and not source_url.startswith("https://"):
            findings.append("outcome_observation.outcome_source.source_url_must_be_https_official_artifact")
        field_ref = _require_text(source, "field_ref", "outcome_observation.outcome_source", findings)
        if field_ref and not PAGE_REFERENCE.search(field_ref):
            findings.append("outcome_observation.outcome_source.field_ref_must_be_paged_reference")
        if source.get("official_source_type") != cell.get("official_source_type"):
            findings.append("outcome_observation.outcome_source.official_source_type_must_match_measurement_contract")
    source = _mapping(item.get("outcome_source"))
    source_at, source_day = _outcome_source_availability(source, "outcome_observation.outcome_source", findings)
    cutoff = _instant(frozen.get("cutoff_at"), "forecast.cutoff_at", findings)
    if cutoff and not _source_follows_cutoff(source_at, source_day, cutoff):
        findings.append("outcome_observation.source_must_follow_forecast_cutoff")
    if observed_at and not _source_precedes_receipt(source_at, source_day, observed_at):
        findings.append("outcome_observation.source_cannot_follow_observation_receipt")
    if observation_status == "OBSERVED_MEASUREMENT":
        measurement = _mapping(item.get("realized_measurement"))
        for component_index, raw_component in enumerate(_items(measurement.get("source_components"))):
            component = _mapping(raw_component)
            component_at, component_day = _outcome_source_availability(
                component,
                f"outcome_observation.realized_measurement.source_components[{component_index}]", findings,
            )
            if cutoff and not _source_follows_cutoff(component_at, component_day, cutoff):
                findings.append(f"outcome_observation.realized_measurement.source_components[{component_index}].source_must_follow_forecast_cutoff")
            if observed_at and not _source_precedes_receipt(component_at, component_day, observed_at):
                findings.append(f"outcome_observation.realized_measurement.source_components[{component_index}].source_cannot_follow_observation_receipt")
    if item.get("object_class") != "FORECAST_OUTCOME_OBSERVATION_RECEIPT":
        findings.append("outcome_observation.object_class_invalid")
    if item.get("claim_class") != "CUSTODIAN_EXTRACTED_OUTCOME_FIELD":
        findings.append("outcome_observation.claim_class_invalid")
    if item.get("allowed_outputs") != OUTCOME_ACCESS_ALLOWED_OUTPUTS:
        findings.append("outcome_observation.allowed_outputs_must_remain_custodian_acquisition_only")
    return _result(findings, observation_receipt=deepcopy(item) if not findings else None)


def _h1_source_index(stage0_package: Any, findings: list[str]) -> dict[str, dict[str, Any]]:
    package = _mapping(stage0_package)
    sources: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_items(package.get("static_pdf_sources"))):
        source = _mapping(raw)
        source_id = source.get("source_id")
        if not _text(source_id) or source_id in sources:
            findings.append(f"h1.static_pdf_sources[{index}].source_id_missing_or_duplicate")
            continue
        sources[str(source_id)] = source
    if not sources:
        findings.append("h1.static_pdf_sources_required")
    return sources


def _page_numbers(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {match.group(1) for match in re.finditer(r"\bp(?:age)?\.?\s*(\d+)\b", value, re.IGNORECASE)}


def validate_preforecast_evidence_receipt(
    receipt: Any, *, stage0_package: Any, h1_source_packet_ref: Any,
) -> dict[str, Any]:
    """Validate a curator-only extraction from an already-frozen H1 static packet.

    The receipt carries cutoff-visible raw fields, not a forecast or a result.
    It can make a later Forecast V4 evidence-bearing, but cannot amend H1,
    create an outcome authorization, or convey CJO/valuation authority.
    """
    findings: list[str] = []
    item = _closed(receipt, _PREFORCAST_EVIDENCE_RECEIPT_KEYS, "preforecast_evidence", findings)
    if item.get("schema_version") != PREFORCAST_EVIDENCE_RECEIPT_SCHEMA_VERSION:
        findings.append("preforecast_evidence.schema_version_invalid")
    _require_text(item, "evidence_receipt_id", "preforecast_evidence", findings)
    version = item.get("evidence_receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("preforecast_evidence.evidence_receipt_version_must_be_positive_integer")
    expected_ref = _mapping(h1_source_packet_ref)
    actual_ref = _reference(item.get("h1_source_packet_ref"), "preforecast_evidence.h1_source_packet_ref", findings)
    if actual_ref is not None and actual_ref != (expected_ref.get("receipt_id"), expected_ref.get("receipt_version")):
        findings.append("preforecast_evidence.h1_source_packet_must_match_frozen_risk_set")
    company_id = _require_text(item, "company_id", "preforecast_evidence", findings)
    issuer_id = _require_text(item, "issuer_id", "preforecast_evidence", findings)
    cutoff = _instant(item.get("cutoff_at"), "preforecast_evidence.cutoff_at", findings)
    _require_text(item, "curator_id", "preforecast_evidence", findings)
    package = _mapping(stage0_package)
    package_cutoff = _instant(package.get("selection_as_of"), "h1.selection_as_of", findings)
    if cutoff and package_cutoff and cutoff != package_cutoff:
        findings.append("preforecast_evidence.cutoff_at_must_match_h1_static_receipt")
    if company_id and issuer_id:
        members = [_mapping(raw) for raw in _items(package.get("members"))]
        if not any(member.get("company_id") == company_id and member.get("issuer_id") == issuer_id for member in members):
            findings.append("preforecast_evidence.company_and_issuer_must_match_h1_risk_set_member")
    source_index = _h1_source_index(stage0_package, findings)
    fields = _items(item.get("fields"))
    if not fields:
        findings.append("preforecast_evidence.fields_must_be_nonempty_list")
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(fields):
        field = _closed(raw, _PREFORCAST_EVIDENCE_FIELD_KEYS, f"preforecast_evidence.fields[{index}]", findings)
        field_id = _require_text(field, "field_id", f"preforecast_evidence.fields[{index}]", findings)
        source_id = _require_text(field, "source_id", f"preforecast_evidence.fields[{index}]", findings)
        key = (source_id, field_id)
        if key in seen:
            findings.append(f"preforecast_evidence.fields[{index}].source_id_and_field_id_must_not_repeat")
        seen.add(key)
        source = source_index.get(source_id)
        if source is None:
            findings.append(f"preforecast_evidence.fields[{index}].source_id_not_in_h1_static_packet")
            continue
        for field_name in ("issuer_id", "responsibility_unit_id", "perimeter_id", "period_end"):
            if field.get(field_name) != source.get(field_name):
                findings.append(f"preforecast_evidence.fields[{index}].{field_name}_must_match_h1_static_source")
        if field.get("issuer_id") != issuer_id:
            findings.append(f"preforecast_evidence.fields[{index}].issuer_id_must_match_receipt")
        if field.get("source_url") != source.get("url"):
            findings.append(f"preforecast_evidence.fields[{index}].source_url_must_match_h1_static_source")
        if field.get("source_type") != source.get("source_type"):
            findings.append(f"preforecast_evidence.fields[{index}].source_type_must_match_h1_static_source")
        if field.get("published_at") != source.get("published_at"):
            findings.append(f"preforecast_evidence.fields[{index}].published_at_must_match_h1_static_source")
        published = _source_date(field.get("published_at"), f"preforecast_evidence.fields[{index}].published_at", findings)
        if cutoff and published and published >= cutoff.date():
            findings.append(f"preforecast_evidence.fields[{index}].source_must_be_strictly_before_cutoff")
        field_ref = _require_text(field, "field_ref", f"preforecast_evidence.fields[{index}]", findings)
        pages = _page_numbers(field_ref)
        if not pages:
            findings.append(f"preforecast_evidence.fields[{index}].field_ref_must_be_paged_pdf_reference")
        _require_text(field, "unit", f"preforecast_evidence.fields[{index}]", findings)
        numeric = field.get("numeric_value")
        if not isinstance(numeric, (int, float)) or isinstance(numeric, bool):
            findings.append(f"preforecast_evidence.fields[{index}].numeric_value_required")
        _require_text(field, "label", f"preforecast_evidence.fields[{index}]", findings)
    if item.get("object_class") != "PIT_PREFORCAST_EVIDENCE_RECEIPT":
        findings.append("preforecast_evidence.object_class_invalid")
    if item.get("claim_class") != "CUTOFF_VISIBLE_FIELD_OBSERVATION":
        findings.append("preforecast_evidence.claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVIDENCE_ONLY"]:
        findings.append("preforecast_evidence.allowed_outputs_must_remain_evidence_only")
    return _result(findings, evidence_receipt=deepcopy(item) if not findings else None)


def compile_preforecast_evidence_receipt(
    extraction: Any, *, evidence_receipt_id: str, evidence_receipt_version: int, h1_source_packet_ref: dict[str, Any],
    company_id: str, issuer_id: str, cutoff_at: str, curator_id: str, stage0_package: Any,
) -> dict[str, Any]:
    """Normalize an independent curator's closed raw-field submission.

    The curator reports only field-level facts from already declared H1 PDFs.
    The controller adds the receipt identity; it cannot create, change, or
    supplement a source artifact.  H1 is an artifact allowlist, not an
    exhaustive index of every page inside each admitted annual-report PDF.
    """
    findings: list[str] = []
    item = _closed(extraction, _CURATOR_FIELD_EXTRACTION_KEYS, "curator_extraction", findings)
    if item.get("schema_version") != CURATOR_FIELD_EXTRACTION_SCHEMA_VERSION:
        findings.append("curator_extraction.schema_version_invalid")
    shape = _closed(item.get("shape"), _CURATOR_FIELD_EXTRACTION_SHAPE_KEYS, "curator_extraction.shape", findings)
    declared_record_fields = shape.get("record_fields")
    if not isinstance(declared_record_fields, list) or set(declared_record_fields) != _CURATOR_FIELD_EXTRACTION_RECORD_KEYS or len(declared_record_fields) != len(_CURATOR_FIELD_EXTRACTION_RECORD_KEYS):
        findings.append("curator_extraction.shape.record_fields_must_match_closed_contract")
    if shape.get("additional_record_fields_permitted") is not False:
        findings.append("curator_extraction.shape.additional_record_fields_must_be_false")
    if item.get("unavailable_records") != []:
        findings.append("curator_extraction.unavailable_records_must_be_explicitly_empty_in_v1")
    source_index = _h1_source_index(stage0_package, findings)
    fields: list[dict[str, Any]] = []
    records = _items(item.get("records"))
    if not records:
        findings.append("curator_extraction.records_must_be_nonempty_list")
    for index, raw in enumerate(records):
        record = _closed(raw, _CURATOR_FIELD_EXTRACTION_RECORD_KEYS, f"curator_extraction.records[{index}]", findings)
        source_id = _require_text(record, "source_id", f"curator_extraction.records[{index}]", findings)
        source = source_index.get(source_id)
        if source is None:
            findings.append(f"curator_extraction.records[{index}].source_id_not_in_h1_static_packet")
            continue
        for field_name in ("source_url", "published_at", "period_end", "issuer_id", "responsibility_unit_id", "perimeter_id"):
            if record.get(field_name) != source.get("url" if field_name == "source_url" else field_name):
                findings.append(f"curator_extraction.records[{index}].{field_name}_must_match_h1_static_source")
        _require_text(record, "unit", f"curator_extraction.records[{index}]", findings)
        _require_text(record, "field_id", f"curator_extraction.records[{index}]", findings)
        field_ref = _require_text(record, "pdf_page_reference", f"curator_extraction.records[{index}]", findings)
        if field_ref and not _page_numbers(field_ref):
            findings.append(f"curator_extraction.records[{index}].pdf_page_reference_must_be_paged_pdf_reference")
        numeric = record.get("numeric_value")
        if not isinstance(numeric, (int, float)) or isinstance(numeric, bool):
            findings.append(f"curator_extraction.records[{index}].numeric_value_required")
        _require_text(record, "label_zh", f"curator_extraction.records[{index}]", findings)
        fields.append({
            "field_id": record.get("field_id"), "source_id": source_id, "source_url": record.get("source_url"),
            "source_type": source.get("source_type"), "published_at": record.get("published_at"),
            "period_end": record.get("period_end"), "issuer_id": record.get("issuer_id"),
            "responsibility_unit_id": record.get("responsibility_unit_id"), "perimeter_id": record.get("perimeter_id"),
            "unit": record.get("unit"), "field_ref": record.get("pdf_page_reference"),
            "numeric_value": numeric, "label": record.get("label_zh"),
        })
    receipt = {
        "schema_version": PREFORCAST_EVIDENCE_RECEIPT_SCHEMA_VERSION,
        "evidence_receipt_id": evidence_receipt_id,
        "evidence_receipt_version": evidence_receipt_version,
        "h1_source_packet_ref": deepcopy(h1_source_packet_ref),
        "company_id": company_id,
        "issuer_id": issuer_id,
        "cutoff_at": cutoff_at,
        "curator_id": curator_id,
        "fields": fields,
        "object_class": "PIT_PREFORCAST_EVIDENCE_RECEIPT",
        "claim_class": "CUTOFF_VISIBLE_FIELD_OBSERVATION",
        "allowed_outputs": ["FORECAST_EVIDENCE_ONLY"],
    }
    receipt_validation = validate_preforecast_evidence_receipt(
        receipt, stage0_package=stage0_package, h1_source_packet_ref=h1_source_packet_ref,
    )
    findings.extend(f"curator_extraction.receipt:{finding}" for finding in receipt_validation["findings"])
    return _result(findings, evidence_receipt=receipt_validation.get("evidence_receipt") if not findings else None)


def _universe_member(universe_snapshot: Any, company_id: str, findings: list[str]) -> dict[str, Any] | None:
    snapshot = _mapping(universe_snapshot)
    matches = [
        _mapping(raw) for raw in _items(snapshot.get("members"))
        if _mapping(raw).get("company_id") == company_id
    ]
    if len(matches) != 1:
        findings.append("forecast.company_must_belong_to_cutoff_risk_set")
        return None
    return matches[0]


def _labels_for(dimension_id: str) -> tuple[str, ...]:
    return RISK_LABELS if dimension_id == "PERMANENT_LOSS_RISK" else NON_RISK_LABELS


def _validate_probability_vector(value: Any, labels: tuple[str, ...], path: str, findings: list[str]) -> None:
    entries = _items(value)
    by_label: dict[str, float] = {}
    for index, raw in enumerate(entries):
        item = _closed(raw, _PROBABILITY_KEYS, f"{path}[{index}]", findings)
        label = item.get("label")
        probability = item.get("probability")
        if label not in labels or label in by_label:
            findings.append(f"{path}[{index}].label_invalid_or_duplicate")
            continue
        if not isinstance(probability, (int, float)) or isinstance(probability, bool) or not 0.0 <= float(probability) <= 1.0:
            findings.append(f"{path}[{index}].probability_must_be_unit_interval")
            continue
        by_label[str(label)] = float(probability)
    if set(by_label) != set(labels):
        findings.append(f"{path}_must_cover_ordered_outcomes")
    elif not math.isclose(sum(by_label.values()), 1.0, rel_tol=0.0, abs_tol=1e-6):
        findings.append(f"{path}_must_sum_to_one")


def _window_forecast_kind(value: Any, *, dimension_id: str, path: str, findings: list[str]) -> str | None:
    entry = _closed(value, _WINDOW_FORECAST_KEYS, path, findings, required={"window_id", "baseline_reference"})
    _require_text(entry, "baseline_reference", path, findings)
    has_ordinal = "probabilities" in entry
    has_binary = "event_statement" in entry or "event_occurs_probability" in entry
    if has_ordinal == has_binary:
        findings.append(f"{path}_must_declare_exactly_one_probability_contract")
        return None
    if has_ordinal:
        _validate_probability_vector(
            entry.get("probabilities"), _labels_for(dimension_id), f"{path}.probabilities", findings,
        )
        return "ORDINAL"
    _require_text(entry, "event_statement", path, findings)
    probability = entry.get("event_occurs_probability")
    if not isinstance(probability, (int, float)) or isinstance(probability, bool) or not 0.0 <= float(probability) <= 1.0:
        findings.append(f"{path}.event_occurs_probability_must_be_unit_interval")
        return None
    return "BINARY"


def _validate_evidence_refs(
    value: Any, *, path: str, source_index: dict[str, dict[str, Any]], issuer_id: str, cutoff: datetime | None,
    findings: list[str], preforecast_field_index: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> list[str]:
    refs = _items(value)
    source_fields: list[tuple[str, str]] = []
    if not refs:
        findings.append(f"{path}_nonempty_list_required")
    for index, raw in enumerate(refs):
        item = _closed(
            raw, _EVIDENCE_REF_KEYS, f"{path}[{index}]", findings,
            required=_EVIDENCE_REF_KEYS if preforecast_field_index is not None else _EVIDENCE_REF_KEYS - {"field_id"},
        )
        source_id = _require_text(item, "source_id", f"{path}[{index}]", findings)
        published = _source_date(item.get("published_at"), f"{path}[{index}].published_at", findings)
        field_ref = _require_text(item, "field_ref", f"{path}[{index}]", findings)
        if field_ref and not PAGE_REFERENCE.search(field_ref):
            findings.append(f"{path}[{index}].field_ref_must_be_paged_pdf_reference")
        source = source_index.get(source_id)
        if source is None:
            findings.append(f"{path}[{index}].source_id_not_in_h1_static_packet")
        else:
            if source.get("issuer_id") != issuer_id:
                findings.append(f"{path}[{index}].source_issuer_must_match_forecast_company")
            declared = _source_date(source.get("published_at"), f"h1.source:{source_id}.published_at", findings)
            if published and declared and published != declared:
                findings.append(f"{path}[{index}].published_at_must_match_h1_source")
            field_id = item.get("field_id")
            frozen_field = preforecast_field_index.get((source_id, field_id)) if preforecast_field_index is not None else None
            if preforecast_field_index is not None and frozen_field is None:
                findings.append(f"{path}[{index}].field_id_not_in_frozen_preforecast_receipt")
            elif preforecast_field_index is not None and field_ref != frozen_field.get("field_ref"):
                findings.append(f"{path}[{index}].field_ref_must_match_frozen_preforecast_receipt")
            elif preforecast_field_index is None and field_ref and field_ref not in _items(source.get("field_refs")):
                findings.append(f"{path}[{index}].field_ref_must_match_h1_declared_pdf_page")
            if cutoff and declared and declared >= cutoff.date():
                findings.append(f"{path}[{index}].source_must_be_strictly_before_forecast_cutoff")
        source_fields.append((source_id, str(item.get("field_id")) if preforecast_field_index is not None else field_ref))
    if len(source_fields) != len(set(source_fields)):
        findings.append(f"{path}.source_id_and_field_ref_must_not_repeat")
    return [source_id for source_id, _ in source_fields]


def _validate_measurement_gaps(
    value: Any, *, path: str, source_index: dict[str, dict[str, Any]], issuer_id: str, cutoff: datetime | None,
    findings: list[str], preforecast_field_index: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> None:
    if value is None:
        return
    gaps = _items(value)
    if not gaps:
        findings.append(f"{path}_must_be_nonempty_list_when_declared")
        return
    seen: set[str] = set()
    for index, raw in enumerate(gaps):
        item = _closed(raw, _MEASUREMENT_GAP_KEYS, f"{path}[{index}]", findings)
        measurement_id = _require_text(item, "measurement_id", f"{path}[{index}]", findings)
        if measurement_id in seen:
            findings.append(f"{path}[{index}].measurement_id_must_not_repeat")
        seen.add(measurement_id)
        _require_text(item, "reason", f"{path}[{index}]", findings)
        _validate_evidence_refs(
            item.get("evidence_refs"), path=f"{path}[{index}].evidence_refs", source_index=source_index,
            issuer_id=issuer_id, cutoff=cutoff, findings=findings, preforecast_field_index=preforecast_field_index,
        )


def validate_company_state_forecast(
    forecast: Any, *, universe_snapshot: Any, stage0_package: Any, preforecast_evidence_receipt: Any | None = None,
    forecast_acquisition_scope: Any | None = None, outcome_measurement_contract: Any | None = None,
) -> dict[str, Any]:
    """Validate one frozen company-state forecast against an H1 risk set.

    A forecast is always either a genuine uncertain probability distribution or
    an explicit acquisition-coverage abstention; it cannot be an unscored empty
    answer.  No outcome fields are accepted in this shape.
    """
    findings: list[str] = []
    item = _closed(
        forecast, _FORECAST_KEYS, "forecast", findings,
        required=_FORECAST_KEYS - {
            "decision_contract_ref", "outcome_measurement_contract_ref", "applied_policy_change_ids",
            "preforecast_evidence_receipt_ref", "forecast_acquisition_scope_ref", "forecast_method_ref",
        },
    )
    schema_version = item.get("schema_version")
    epoch_id = item.get("forecast_epoch_id")
    if (schema_version, epoch_id) not in {
        (FORECAST_SCHEMA_VERSION, FORECAST_EPOCH_ID),
        (FORECAST_SCHEMA_VERSION_V2, FORECAST_EPOCH_ID_V2),
        (FORECAST_SCHEMA_VERSION_V3, FORECAST_EPOCH_ID_V3),
        (FORECAST_SCHEMA_VERSION_V4, FORECAST_EPOCH_ID_V4),
        (FORECAST_SCHEMA_VERSION_V5, FORECAST_EPOCH_ID_V5),
        (FORECAST_SCHEMA_VERSION_V6, FORECAST_EPOCH_ID_V6),
    }:
        findings.append("forecast.schema_version_invalid")
    if schema_version == FORECAST_SCHEMA_VERSION:
        if item.get("decision_contract_ref") is not None:
            findings.append("forecast.v1_cannot_retrofit_decision_contract")
        if any(item.get(field) is not None for field in (
            "outcome_measurement_contract_ref", "applied_policy_change_ids", "preforecast_evidence_receipt_ref",
            "forecast_acquisition_scope_ref",
        )):
            findings.append("forecast.v1_cannot_retrofit_measurement_contract")
    if schema_version in {FORECAST_SCHEMA_VERSION_V2, FORECAST_SCHEMA_VERSION_V3, FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        contract_ref = _closed(
            item.get("decision_contract_ref"), _DECISION_CONTRACT_REF_KEYS,
            "forecast.decision_contract_ref", findings,
        )
        _require_text(contract_ref, "contract_id", "forecast.decision_contract_ref", findings)
        version = contract_ref.get("contract_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            findings.append("forecast.decision_contract_ref.contract_version_must_be_positive_integer")
    if schema_version == FORECAST_SCHEMA_VERSION_V2:
        if any(item.get(field) is not None for field in (
            "outcome_measurement_contract_ref", "applied_policy_change_ids", "preforecast_evidence_receipt_ref",
            "forecast_acquisition_scope_ref",
        )):
            findings.append("forecast.v2_cannot_retrofit_measurement_contract")
    if schema_version in {FORECAST_SCHEMA_VERSION_V3, FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        _outcome_measurement_contract_reference(
            item.get("outcome_measurement_contract_ref"), "forecast.outcome_measurement_contract_ref", findings,
        )
        policy_ids = item.get("applied_policy_change_ids")
        if not isinstance(policy_ids, list) or any(not _text(policy_id) for policy_id in policy_ids) or len(set(policy_ids)) != len(policy_ids):
            findings.append("forecast.applied_policy_change_ids_must_be_unique_text_list")
    if schema_version == FORECAST_SCHEMA_VERSION_V3 and (
        item.get("preforecast_evidence_receipt_ref") is not None or item.get("forecast_acquisition_scope_ref") is not None
    ):
        findings.append("forecast.v3_cannot_retrofit_preforecast_evidence_receipt")
    if schema_version == FORECAST_SCHEMA_VERSION_V4 and item.get("forecast_acquisition_scope_ref") is not None:
        findings.append("forecast.v4_cannot_retrofit_acquisition_scope")
    if schema_version in {FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        _preforecast_evidence_receipt_reference(
            item.get("preforecast_evidence_receipt_ref"), "forecast.preforecast_evidence_receipt_ref", findings,
        )
    if schema_version in {FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        _forecast_acquisition_scope_reference(
            item.get("forecast_acquisition_scope_ref"), "forecast.forecast_acquisition_scope_ref", findings,
        )
    if schema_version == FORECAST_SCHEMA_VERSION_V6:
        method_ref = _closed(item.get("forecast_method_ref"), _FORECAST_METHOD_REF_KEYS, "forecast.forecast_method_ref", findings)
        _require_text(method_ref, "program_id", "forecast.forecast_method_ref", findings)
        _require_text(method_ref, "method_version", "forecast.forecast_method_ref", findings)
        method_frozen = _instant(method_ref.get("method_frozen_at"), "forecast.forecast_method_ref.method_frozen_at", findings)
        method_recorded = _instant(method_ref.get("method_freeze_recorded_at"), "forecast.forecast_method_ref.method_freeze_recorded_at", findings)
        if method_frozen and method_recorded and method_frozen > method_recorded:
            findings.append("forecast.forecast_method_ref.freeze_time_order_invalid")
    elif item.get("forecast_method_ref") is not None:
        findings.append("forecast.v1_v5_cannot_retrofit_method_identity")
    forecast_id = _require_text(item, "forecast_id", "forecast", findings)
    company_id = _require_text(item, "company_id", "forecast", findings)
    issuer_id = _require_text(item, "issuer_id", "forecast", findings)
    subject_id = _require_text(item, "subject_id", "forecast", findings)
    cutoff = _instant(item.get("cutoff_at"), "forecast.cutoff_at", findings)
    if item.get("object_class") != "PIT_COMPANY_STATE_FORECAST":
        findings.append("forecast.object_class_invalid")
    if item.get("claim_class") != "PROSPECTIVE_STATE_TRAJECTORY":
        findings.append("forecast.claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"]:
        findings.append("forecast.allowed_outputs_must_remain_evaluation_only")

    member = _universe_member(universe_snapshot, company_id, findings) if company_id else None
    snapshot = _mapping(universe_snapshot)
    snapshot_cutoff = _instant(snapshot.get("cutoff_at"), "universe.cutoff_at", findings)
    if cutoff and snapshot_cutoff and cutoff != snapshot_cutoff:
        findings.append("forecast.cutoff_at_must_match_risk_set_snapshot")
    h1_cutoff = _instant(_mapping(stage0_package).get("selection_as_of"), "h1.selection_as_of", findings)
    if cutoff and h1_cutoff and cutoff != h1_cutoff:
        findings.append("forecast.cutoff_at_must_match_h1_static_receipt")
    if member:
        if member.get("issuer_id") != issuer_id:
            findings.append("forecast.issuer_id_must_match_risk_set_member")
        if member.get("subject_id") != subject_id:
            findings.append("forecast.subject_id_must_match_risk_set_member")
        if member.get("risk_status") not in {"IN_RISK_SET", "UNKNOWN", "CENSORED"}:
            findings.append("forecast.risk_set_member_not_eligible")

    packet_refs = _items(item.get("source_packet_refs"))
    if len(packet_refs) != 1:
        findings.append("forecast.must_reference_exactly_one_h1_source_packet")
    else:
        _reference(packet_refs[0], "forecast.source_packet_refs[0]", findings)
        if packet_refs[0] not in _items(snapshot.get("source_packet_refs")):
            findings.append("forecast.source_packet_must_match_risk_set_h1_receipt")

    mitigation = _closed(item.get("model_memory_mitigation"), _MITIGATION_KEYS, "forecast.model_memory_mitigation", findings)
    if mitigation.get("mode") != "MODEL_MEMORY_MITIGATED":
        findings.append("forecast.memory_mitigation_mode_required")
    _require_text(mitigation, "isolated_forecaster_id", "forecast.model_memory_mitigation", findings)
    for field in ("known_outcome_access", "price_access", "post_cutoff_access"):
        if mitigation.get(field) != "NONE":
            findings.append(f"forecast.model_memory_mitigation.{field}_must_be_none")
    if mitigation.get("network_route") != "H1_DECLARED_STATIC_PDF_ONLY":
        findings.append("forecast.model_memory_mitigation.network_route_invalid")
    _require_text(mitigation, "notes", "forecast.model_memory_mitigation", findings)

    windows = _items(item.get("forecast_windows"))
    if windows != list(FORECAST_WINDOWS):
        findings.append("forecast.windows_must_be_one_three_five_year_in_order")

    source_index = _h1_source_index(stage0_package, findings)
    preforecast_fields: set[tuple[str, str]] = set()
    preforecast_field_index: dict[tuple[str, str], dict[str, Any]] | None = None
    if schema_version in {FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        receipt_validation = validate_preforecast_evidence_receipt(
            preforecast_evidence_receipt, stage0_package=stage0_package,
            h1_source_packet_ref=packet_refs[0] if len(packet_refs) == 1 else {},
        )
        findings.extend(f"forecast.preforecast_evidence:{finding}" for finding in receipt_validation["findings"])
        receipt = _mapping(receipt_validation.get("evidence_receipt"))
        if receipt:
            for field in ("company_id", "issuer_id", "cutoff_at"):
                if receipt.get(field) != item.get(field):
                    findings.append(f"forecast.preforecast_evidence.{field}_must_match_forecast")
            expected_receipt_ref = {
                "evidence_receipt_id": receipt.get("evidence_receipt_id"),
                "evidence_receipt_version": receipt.get("evidence_receipt_version"),
            }
            actual_receipt_ref = _preforecast_evidence_receipt_reference(
                item.get("preforecast_evidence_receipt_ref"), "forecast.preforecast_evidence_receipt_ref", findings,
            )
            if actual_receipt_ref is not None and actual_receipt_ref != expected_receipt_ref:
                findings.append("forecast.preforecast_evidence_receipt_ref_must_match_frozen_receipt")
            if receipt.get("curator_id") == mitigation.get("isolated_forecaster_id"):
                findings.append("forecast.preforecast_curator_must_be_independent_from_isolated_forecaster")
            preforecast_field_index = {
                (str(field.get("source_id")), str(field.get("field_id"))): field
                for field in _items(receipt.get("fields")) if isinstance(field, dict)
            }
            preforecast_fields = set(preforecast_field_index)
    acquisition_scope_cells: set[tuple[str, str]] | None = None
    if schema_version in {FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        if not isinstance(forecast_acquisition_scope, dict):
            findings.append("forecast.v5_requires_frozen_acquisition_scope")
        scope_validation = validate_forecast_acquisition_scope(
            forecast_acquisition_scope, measurement_contract=outcome_measurement_contract,
        )
        findings.extend(f"forecast.acquisition_scope:{finding}" for finding in scope_validation["findings"])
        scope = _mapping(scope_validation.get("acquisition_scope"))
        scope_ref = _forecast_acquisition_scope_reference(
            item.get("forecast_acquisition_scope_ref"), "forecast.forecast_acquisition_scope_ref", findings,
        )
        expected_scope_ref = {"scope_id": scope.get("scope_id"), "scope_version": scope.get("scope_version")}
        if scope_ref is not None and scope_ref != expected_scope_ref:
            findings.append("forecast.forecast_acquisition_scope_ref_must_match_frozen_scope")
        for field in ("company_id", "issuer_id", "cutoff_at"):
            if scope.get(field) != item.get(field):
                findings.append(f"forecast.acquisition_scope.{field}_must_match_forecast")
        acquisition_scope_cells = {
            (str(entry.get("dimension_id")), str(entry.get("window_id")))
            for entry in _items(scope.get("cells")) if isinstance(entry, dict)
        }
    dimensions = _items(item.get("dimensions"))
    by_dimension: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(dimensions):
        dimension = _closed(
            raw, _DIMENSION_KEYS, f"forecast.dimensions[{index}]", findings,
            required=_DIMENSION_KEYS - {"measurement_gaps"},
        )
        dimension_id = dimension.get("dimension_id")
        if dimension_id not in FORECAST_DIMENSIONS or dimension_id in by_dimension:
            findings.append(f"forecast.dimensions[{index}].dimension_id_invalid_or_duplicate")
            continue
        by_dimension[str(dimension_id)] = dimension
        evidence_status = dimension.get("evidence_status")
        if evidence_status not in EVIDENCE_STATUSES:
            findings.append(f"forecast.dimensions[{index}].evidence_status_invalid")
        _require_text(dimension, "rationale", f"forecast.dimensions[{index}]", findings)
        _validate_evidence_refs(
            dimension.get("evidence_refs"), path=f"forecast.dimensions[{index}].evidence_refs",
            source_index=source_index, issuer_id=issuer_id, cutoff=cutoff, findings=findings,
            preforecast_field_index=preforecast_field_index,
        )
        _validate_measurement_gaps(
            dimension.get("measurement_gaps"), path=f"forecast.dimensions[{index}].measurement_gaps",
            source_index=source_index, issuer_id=issuer_id, cutoff=cutoff, findings=findings,
            preforecast_field_index=preforecast_field_index,
        )
        window_forecasts = _items(dimension.get("forecast_by_window"))
        if evidence_status == "EVIDENCE_INELIGIBLE":
            if window_forecasts:
                findings.append(f"forecast.dimensions[{index}].ineligible_dimension_cannot_emit_prediction")
            if schema_version in {FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6} and acquisition_scope_cells is not None:
                expected_scope_cells = {(str(dimension_id), window_id) for window_id in FORECAST_WINDOWS}
                if expected_scope_cells.intersection(acquisition_scope_cells):
                    findings.append(f"forecast.dimensions[{index}].acquisition_scope_cannot_collect_evidence_ineligible_dimension")
            continue
        if schema_version in {FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
            dimension_fields = [
                (str(reference.get("source_id")), str(reference.get("field_id")))
                for reference in _items(dimension.get("evidence_refs")) if isinstance(reference, dict)
            ]
            if not dimension_fields or any(not _text(reference.get("field_id")) for reference in _items(dimension.get("evidence_refs")) if isinstance(reference, dict)):
                findings.append(f"forecast.dimensions[{index}].model_uncertain_dimension_requires_preforecast_field_refs")
            for source_field in dimension_fields:
                if source_field not in preforecast_fields:
                    findings.append(f"forecast.dimensions[{index}].preforecast_field_not_in_frozen_receipt")
        if len(window_forecasts) != len(FORECAST_WINDOWS):
            findings.append(f"forecast.dimensions[{index}].model_uncertain_dimension_must_cover_all_windows")
        seen_windows: set[str] = set()
        for window_index, window_raw in enumerate(window_forecasts):
            entry = _mapping(window_raw)
            window_id = entry.get("window_id")
            if window_id not in FORECAST_WINDOWS or window_id in seen_windows:
                findings.append(f"forecast.dimensions[{index}].forecast_by_window[{window_index}].window_id_invalid_or_duplicate")
            seen_windows.add(str(window_id))
            _window_forecast_kind(
                window_raw, dimension_id=str(dimension_id),
                path=f"forecast.dimensions[{index}].forecast_by_window[{window_index}]", findings=findings,
            )
        if evidence_status == "MODEL_UNCERTAIN" and set(seen_windows) != set(FORECAST_WINDOWS):
            findings.append(f"forecast.dimensions[{index}].model_uncertain_windows_incomplete")
        if schema_version in {FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6} and acquisition_scope_cells is not None:
            expected_scope_cells = {(str(dimension_id), window_id) for window_id in FORECAST_WINDOWS}
            if evidence_status == "MODEL_UNCERTAIN" and not expected_scope_cells.issubset(acquisition_scope_cells):
                findings.append(f"forecast.dimensions[{index}].acquisition_scope_must_cover_each_model_uncertain_window")
    if set(by_dimension) != set(FORECAST_DIMENSIONS):
        findings.append("forecast.must_cover_each_state_dimension_exactly_once")
    return _result(findings, forecast=deepcopy(item) if not findings else None, forecast_id=forecast_id or None)


def _isolated_evidence_refs(value: Any, *, path: str, findings: list[str]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for index, raw in enumerate(_items(value)):
        item = _closed(raw, _ISOLATED_EVIDENCE_KEYS, f"{path}[{index}]", findings)
        source_id = _require_text(item, "source_id", f"{path}[{index}]", findings)
        published_at = _require_text(item, "publication_date", f"{path}[{index}]", findings)
        _require_text(item, "pdf_page_ref", f"{path}[{index}]", findings)
        field_ref = _require_text(item, "field_ref", f"{path}[{index}]", findings)
        if source_id and published_at and field_ref:
            refs.append({"source_id": source_id, "published_at": published_at, "field_ref": field_ref})
    if not refs:
        findings.append(f"{path}_requires_static_pdf_evidence")
    return refs


def _isolated_binary_dimension(
    raw: Any, *, dimension_id: str, path: str, findings: list[str], measurement_gaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    item = _closed(raw, _ISOLATED_DIMENSION_KEYS, path, findings, required={"status", "evidence"})
    status = item.get("status")
    refs = _isolated_evidence_refs(item.get("evidence"), path=f"{path}.evidence", findings=findings)
    result: dict[str, Any] = {
        "dimension_id": dimension_id,
        "evidence_status": status,
        "evidence_refs": refs,
        "forecast_by_window": [],
        "rationale": str(item.get("event") or item.get("reason") or ""),
    }
    if measurement_gaps:
        result["measurement_gaps"] = measurement_gaps
    if status == "EVIDENCE_INELIGIBLE":
        _require_text(item, "reason", path, findings)
        return result
    if status != "MODEL_UNCERTAIN":
        findings.append(f"{path}.status_must_be_model_uncertain_or_evidence_ineligible")
        return result
    event = _require_text(item, "event", path, findings)
    horizons = _items(item.get("horizons"))
    expected_years = (1, 3, 5)
    if [ _mapping(value).get("years_forward") for value in horizons ] != list(expected_years):
        findings.append(f"{path}.horizons_must_cover_one_three_five_year_in_order")
    for index, horizon in enumerate(horizons):
        entry = _closed(horizon, _ISOLATED_HORIZON_KEYS, f"{path}.horizons[{index}]", findings)
        probability = entry.get("probability")
        if not isinstance(probability, (int, float)) or isinstance(probability, bool) or not 0.0 <= float(probability) <= 1.0:
            findings.append(f"{path}.horizons[{index}].probability_must_be_unit_interval")
            continue
        year = entry.get("years_forward")
        if year not in expected_years:
            continue
        result["forecast_by_window"].append({
            "window_id": {1: "ONE_YEAR", 3: "THREE_YEAR", 5: "FIVE_YEAR"}[year],
            "baseline_reference": "Cutoff-visible issuer state; later outcome is not consumed.",
            "event_statement": event,
            "event_occurs_probability": float(probability),
        })
    return result


def compile_isolated_forecast_submission(
    submission: Any, *, universe_snapshot: Any, stage0_package: Any, h1_receipt_ref: dict[str, Any],
    decision_contract_refs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile an isolated curator submission without changing its probabilities.

    The submission is an evidence-bearing human/agent handoff, whereas frozen
    per-company forecasts use the canonical forecast schema.  Compilation only
    converts its one-event probabilities into binary Brier contracts and binds
    every cited static PDF/page to H1; it never fills an ineligible dimension,
    infers an outcome, or creates a causal claim.
    """
    findings: list[str] = []
    item = _closed(submission, _ISOLATED_SUBMISSION_KEYS, "isolated_submission", findings)
    if item.get("schema_version") != ISOLATED_SUBMISSION_SCHEMA_VERSION:
        findings.append("isolated_submission.schema_version_invalid")
    pilot_id = _require_text(item, "pilot_id", "isolated_submission", findings)
    cutoff = _instant(item.get("cutoff_at"), "isolated_submission.cutoff_at", findings)
    snapshot = _mapping(universe_snapshot)
    if cutoff != _instant(snapshot.get("cutoff_at"), "universe.cutoff_at", findings):
        findings.append("isolated_submission.cutoff_must_match_h1_risk_set")

    mitigation = _closed(item.get("model_memory_mitigation"), _ISOLATED_MITIGATION_KEYS, "isolated_submission.model_memory_mitigation", findings)
    if mitigation.get("status") != "MODEL_MEMORY_MITIGATED":
        findings.append("isolated_submission.model_memory_mitigation_required")
    curator_id = _require_text(mitigation, "curator", "isolated_submission.model_memory_mitigation", findings)
    for field in ("network_access", "outcome_access", "results_access", "price_access"):
        if mitigation.get(field) != "NONE":
            findings.append(f"isolated_submission.model_memory_mitigation.{field}_must_be_none")
    if not isinstance(mitigation.get("prohibited_materials"), list) or not isinstance(mitigation.get("allowed_evidence_rule"), str):
        findings.append("isolated_submission.model_memory_mitigation.prohibited_materials_and_rule_required")

    packet = _closed(item.get("source_packet_ref"), _ISOLATED_PACKET_KEYS, "isolated_submission.source_packet_ref", findings)
    if packet.get("cohort_id") != _mapping(stage0_package).get("cohort_id"):
        findings.append("isolated_submission.source_packet_must_match_h1_cohort")
    _require_text(packet, "path", "isolated_submission.source_packet_ref", findings)
    _require_text(packet, "use_limit", "isolated_submission.source_packet_ref", findings)
    reference_tuple = _reference(h1_receipt_ref, "h1_receipt_ref", findings)
    if reference_tuple is None:
        return _result(findings)
    reference = {"receipt_id": reference_tuple[0], "receipt_version": reference_tuple[1]}

    raw_companies = _items(item.get("companies"))
    snapshot_members = {str(_mapping(member).get("company_id")): _mapping(member) for member in _items(snapshot.get("members"))}
    package_members = {str(_mapping(member).get("company_id")): _mapping(member) for member in _items(_mapping(stage0_package).get("members"))}
    if decision_contract_refs is not None:
        if not isinstance(decision_contract_refs, dict) or set(decision_contract_refs) != set(snapshot_members):
            findings.append("isolated_submission.decision_contract_refs_must_cover_h1_risk_set_exactly_once")
    if set(_mapping(company).get("company_id") for company in raw_companies) != set(snapshot_members):
        findings.append("isolated_submission.must_cover_h1_risk_set_companies_exactly_once")
    compiled_forecasts: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_companies):
        company = _closed(raw, _ISOLATED_COMPANY_KEYS, f"isolated_submission.companies[{index}]", findings)
        company_id = _require_text(company, "company_id", f"isolated_submission.companies[{index}]", findings)
        member = snapshot_members.get(company_id, {})
        package_member = package_members.get(company_id, {})
        if not member or not package_member:
            findings.append(f"isolated_submission.companies[{index}].company_must_belong_to_h1_risk_set")
            continue
        expected_disposition = package_member.get("final_peer_panel_disposition")
        allowed_disposition = "PENDING_ACTION_WINDOW_REVIEW" if expected_disposition == "PENDING_ACTION_WINDOW_REVIEW" else "LIFECYCLE_BOUNDARY_ONLY"
        if company.get("panel_disposition") != allowed_disposition:
            findings.append(f"isolated_submission.companies[{index}].panel_disposition_must_match_h1_boundary")
        states = _items(company.get("verified_cutoff_state"))
        if not states:
            findings.append(f"isolated_submission.companies[{index}].verified_cutoff_state_required")
        for state_index, state_raw in enumerate(states):
            state = _closed(state_raw, _ISOLATED_STATE_KEYS, f"isolated_submission.companies[{index}].verified_cutoff_state[{state_index}]", findings)
            _require_text(state, "statement", f"isolated_submission.companies[{index}].verified_cutoff_state[{state_index}]", findings)
            _isolated_evidence_refs(state.get("evidence"), path=f"isolated_submission.companies[{index}].verified_cutoff_state[{state_index}].evidence", findings=findings)
        raw_dimensions = _mapping(company.get("forecast_dimensions"))
        expected_raw_dimensions = set(_ISOLATED_DIMENSION_MAP).union({"cash_conversion_and_capex_burden"})
        if set(raw_dimensions) != expected_raw_dimensions:
            findings.append(f"isolated_submission.companies[{index}].forecast_dimensions_must_cover_six_dimensions")
        dimensions: list[dict[str, Any]] = []
        for raw_name, canonical_id in _ISOLATED_DIMENSION_MAP.items():
            dimensions.append(_isolated_binary_dimension(
                raw_dimensions.get(raw_name), dimension_id=canonical_id,
                path=f"isolated_submission.companies[{index}].forecast_dimensions.{raw_name}", findings=findings,
            ))
        raw_cash = _mapping(raw_dimensions.get("cash_conversion_and_capex_burden"))
        cash_path = f"isolated_submission.companies[{index}].forecast_dimensions.cash_conversion_and_capex_burden"
        if raw_cash.get("status") == "EVIDENCE_INELIGIBLE":
            dimensions.append(_isolated_binary_dimension(
                raw_cash, dimension_id="CASH_CONVERSION_AND_CAPEX_BURDEN", path=cash_path, findings=findings,
            ))
        else:
            cash = _closed(raw_cash, _ISOLATED_DIMENSION_KEYS, cash_path, findings, required={"cash_conversion", "capex_burden"})
            capex = _isolated_binary_dimension(
                cash.get("capex_burden"), dimension_id="CAPEX_BURDEN",
                path=f"{cash_path}.capex_burden", findings=findings,
            )
            measurement_gaps: list[dict[str, Any]] = []
            if capex.get("evidence_status") != "EVIDENCE_INELIGIBLE":
                findings.append(f"isolated_submission.companies[{index}].capex_burden_must_remain_explicit_coverage_gap_in_v1")
            else:
                measurement_gaps.append({
                    "measurement_id": "CAPEX_BURDEN",
                    "reason": capex.get("rationale"),
                    "evidence_refs": capex.get("evidence_refs"),
                })
            dimensions.append(_isolated_binary_dimension(
                cash.get("cash_conversion"), dimension_id="CASH_CONVERSION_AND_CAPEX_BURDEN",
                path=f"{cash_path}.cash_conversion", findings=findings, measurement_gaps=measurement_gaps,
            ))
        contract_ref = None
        if decision_contract_refs is not None:
            contract_ref = _decision_contract_reference(
                decision_contract_refs.get(company_id),
                f"isolated_submission.decision_contract_refs.{company_id}",
                findings,
            )
        is_v2 = decision_contract_refs is not None
        forecast = {
            "schema_version": FORECAST_SCHEMA_VERSION_V2 if is_v2 else FORECAST_SCHEMA_VERSION,
            "forecast_id": f"FORECAST:{pilot_id}:{company_id}:V2" if is_v2 else f"FORECAST:{pilot_id}:{company_id}",
            "forecast_epoch_id": FORECAST_EPOCH_ID_V2 if is_v2 else FORECAST_EPOCH_ID,
            "company_id": company_id,
            "issuer_id": member.get("issuer_id"),
            "subject_id": member.get("subject_id"),
            "cutoff_at": snapshot.get("cutoff_at"),
            "forecast_windows": list(FORECAST_WINDOWS),
            "source_packet_refs": [reference],
            "model_memory_mitigation": {
                "mode": "MODEL_MEMORY_MITIGATED", "isolated_forecaster_id": curator_id,
                "known_outcome_access": "NONE", "price_access": "NONE", "post_cutoff_access": "NONE",
                "network_route": "H1_DECLARED_STATIC_PDF_ONLY", "notes": mitigation.get("allowed_evidence_rule"),
            },
            "dimensions": dimensions,
            "object_class": "PIT_COMPANY_STATE_FORECAST",
            "claim_class": "PROSPECTIVE_STATE_TRAJECTORY",
            "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
        }
        if contract_ref is not None:
            forecast["decision_contract_ref"] = contract_ref
        compiled_forecasts.append(forecast)

    for forecast in compiled_forecasts:
        validation = validate_company_state_forecast(forecast, universe_snapshot=universe_snapshot, stage0_package=stage0_package)
        findings.extend(f"compiled:{forecast.get('company_id')}:{finding}" for finding in validation["findings"])
    return _result(findings, forecasts=compiled_forecasts if not findings else [])


def validate_relative_trajectory_tournament(
    tournament: Any, *, forecasts: list[dict[str, Any]], universe_snapshot: Any, stage0_package: Any,
) -> dict[str, Any]:
    """Validate a dimension-specific reference ranking, never a causal control."""
    findings: list[str] = []
    item = _closed(tournament, _TOURNAMENT_KEYS, "tournament", findings)
    if item.get("schema_version") != TOURNAMENT_SCHEMA_VERSION:
        findings.append("tournament.schema_version_invalid")
    if item.get("forecast_epoch_id") not in {
        FORECAST_EPOCH_ID, FORECAST_EPOCH_ID_V2, FORECAST_EPOCH_ID_V3, FORECAST_EPOCH_ID_V4, FORECAST_EPOCH_ID_V5, FORECAST_EPOCH_ID_V6,
    }:
        findings.append("tournament.epoch_invalid")
    _require_text(item, "tournament_id", "tournament", findings)
    cutoff = _instant(item.get("cutoff_at"), "tournament.cutoff_at", findings)
    snapshot = _mapping(universe_snapshot)
    snapshot_cutoff = _instant(snapshot.get("cutoff_at"), "universe.cutoff_at", findings)
    if cutoff and snapshot_cutoff and cutoff != snapshot_cutoff:
        findings.append("tournament.cutoff_must_match_risk_set_snapshot")
    if item.get("universe_id") != snapshot.get("universe_id"):
        findings.append("tournament.universe_id_must_match_risk_set_snapshot")
    if item.get("object_class") != "RELATIVE_TRAJECTORY_TOURNAMENT":
        findings.append("tournament.object_class_invalid")
    if item.get("claim_class") != "RELATIVE_TRAJECTORY_REFERENCE":
        findings.append("tournament.claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"]:
        findings.append("tournament.allowed_outputs_must_remain_evaluation_only")

    if item.get("universe_id") != snapshot.get("universe_id"):
        findings.append("tournament.universe_id_must_match_cutoff_risk_set")
    if item.get("source_packet_refs") != snapshot.get("source_packet_refs"):
        findings.append("tournament.source_packet_refs_must_match_cutoff_risk_set")
    if _instant(item.get("cutoff_at"), "tournament.cutoff_at", findings) != _instant(snapshot.get("cutoff_at"), "universe.cutoff_at", findings):
        findings.append("tournament.cutoff_at_must_match_cutoff_risk_set")

    company_ids = _items(item.get("ranked_company_ids"))
    if len(company_ids) < 2 or any(not _text(value) for value in company_ids) or len(set(company_ids)) != len(company_ids):
        findings.append("tournament.ranked_company_ids_invalid")
    risk_companies = {str(_mapping(member).get("company_id")) for member in _items(snapshot.get("members"))}
    if not set(company_ids).issubset(risk_companies):
        findings.append("tournament.company_must_belong_to_cutoff_risk_set")
    eligible_reference_companies = {
        str(_mapping(member).get("company_id"))
        for member in _items(_mapping(stage0_package).get("members"))
        if _mapping(member).get("final_peer_panel_disposition") == "PENDING_ACTION_WINDOW_REVIEW"
    }
    if not eligible_reference_companies:
        findings.append("tournament.h1_pending_reference_companies_required")
    elif not set(company_ids).issubset(eligible_reference_companies):
        findings.append("tournament.scope_or_control_break_cannot_enter_relative_reference")
    forecast_by_id = {forecast.get("forecast_id"): forecast for forecast in forecasts if isinstance(forecast, dict)}
    forecast_ids = _items(item.get("forecast_ids"))
    if len(forecast_ids) != len(company_ids) or len(set(forecast_ids)) != len(forecast_ids):
        findings.append("tournament.forecast_ids_must_match_ranked_companies")
    covered_companies: set[str] = set()
    for forecast_id in forecast_ids:
        forecast = forecast_by_id.get(forecast_id)
        if forecast is None:
            findings.append("tournament.forecast_id_not_supplied")
            continue
        if forecast.get("company_id") not in company_ids or forecast.get("cutoff_at") != item.get("cutoff_at"):
            findings.append("tournament.forecast_identity_or_cutoff_mismatch")
        if forecast.get("forecast_epoch_id") != item.get("forecast_epoch_id"):
            findings.append("tournament.forecasts_must_match_tournament_epoch")
        covered_companies.add(str(forecast.get("company_id")))
    if set(company_ids) != covered_companies:
        findings.append("tournament.forecasts_must_cover_ranked_companies_exactly")

    rankings = _items(item.get("dimension_rankings"))
    by_dimension: set[str] = set()
    for index, raw in enumerate(rankings):
        ranking = _closed(raw, _RANKING_KEYS, f"tournament.dimension_rankings[{index}]", findings)
        dimension_id = ranking.get("dimension_id")
        if dimension_id not in FORECAST_DIMENSIONS or dimension_id in by_dimension:
            findings.append(f"tournament.dimension_rankings[{index}].dimension_id_invalid_or_duplicate")
            continue
        by_dimension.add(str(dimension_id))
        ordered = _items(ranking.get("ordered_company_ids"))
        unranked = _items(ranking.get("unranked_company_ids"))
        if any(company not in company_ids for company in ordered + unranked) or len(set(ordered + unranked)) != len(company_ids) or set(ordered + unranked) != set(company_ids):
            findings.append(f"tournament.dimension_rankings[{index}].must_account_for_each_company_once")
        if ordered and len(ordered) < 2:
            findings.append(f"tournament.dimension_rankings[{index}].requires_at_least_two_ranked_companies")
        for company_id in ordered:
            forecast = next(
                (candidate for candidate in forecasts if candidate.get("company_id") == company_id), None,
            )
            dimension = next(
                (candidate for candidate in _items(_mapping(forecast).get("dimensions"))
                 if _mapping(candidate).get("dimension_id") == dimension_id),
                None,
            )
            if _mapping(dimension).get("evidence_status") != "MODEL_UNCERTAIN":
                findings.append(
                    f"tournament.dimension_rankings[{index}].ordered_company_requires_model_uncertain_dimension"
                )
        _require_text(ranking, "rationale", f"tournament.dimension_rankings[{index}]", findings)
    if set(by_dimension) != set(FORECAST_DIMENSIONS):
        findings.append("tournament.must_rank_each_dimension_without_overall_winner")
    return _result(findings, tournament=deepcopy(item) if not findings else None)


def compile_isolated_relative_tournament(
    submission: Any, *, forecasts: list[dict[str, Any]], universe_snapshot: Any, stage0_package: Any, h1_receipt_ref: dict[str, Any],
) -> dict[str, Any]:
    """Compile the isolated pilot's reference-only ranking without inventing ranks.

    A missing/common-basis dimension is represented by every eligible company
    in ``unranked_company_ids``.  It is not converted into a strict ordering.
    """
    findings: list[str] = []
    submission_item = _mapping(submission)
    pilot_id = _require_text(submission_item, "pilot_id", "isolated_submission", findings)
    raw = _closed(submission_item.get("relative_tournament"), _ISOLATED_TOURNAMENT_KEYS, "isolated_submission.relative_tournament", findings)
    if raw.get("status") != "MODEL_UNCERTAIN":
        findings.append("isolated_submission.relative_tournament.status_must_be_model_uncertain")
    eligible = _items(raw.get("eligible_company_ids"))
    excluded = _items(raw.get("excluded_lifecycle_boundary_company_ids"))
    h1_members = _items(_mapping(stage0_package).get("members"))
    expected_eligible = [
        _mapping(member).get("company_id") for member in h1_members
        if _mapping(member).get("final_peer_panel_disposition") == "PENDING_ACTION_WINDOW_REVIEW"
    ]
    expected_excluded = [
        _mapping(member).get("company_id") for member in h1_members
        if _mapping(member).get("final_peer_panel_disposition") != "PENDING_ACTION_WINDOW_REVIEW"
    ]
    if eligible != expected_eligible:
        findings.append("isolated_submission.relative_tournament.eligible_companies_must_match_h1_pending_members")
    if set(excluded) != set(expected_excluded):
        findings.append("isolated_submission.relative_tournament.excluded_companies_must_match_h1_boundary_members")
    raw_dimensions = _mapping(raw.get("dimensions"))
    if set(raw_dimensions) != set(_ISOLATED_TOURNAMENT_DIMENSION_MAP):
        findings.append("isolated_submission.relative_tournament.must_cover_six_dimensions")
    rankings: list[dict[str, Any]] = []
    for raw_name, canonical_id in _ISOLATED_TOURNAMENT_DIMENSION_MAP.items():
        detail = _closed(
            raw_dimensions.get(raw_name), _ISOLATED_TOURNAMENT_DIMENSION_KEYS,
            f"isolated_submission.relative_tournament.dimensions.{raw_name}", findings,
            required={"ranking", "evidence"},
        )
        raw_ranking = detail.get("ranking")
        if raw_ranking is None:
            ordered: list[str] = []
            unranked = list(eligible)
        else:
            ordered = _items(raw_ranking)
            unranked = _items(detail.get("unranked_company_ids"))
            if not unranked:
                unranked = [company_id for company_id in eligible if company_id not in ordered]
        if any(company_id not in eligible for company_id in ordered + unranked):
            findings.append(f"isolated_submission.relative_tournament.dimensions.{raw_name}.ranking_must_only_use_pending_companies")
        if set(ordered + unranked) != set(eligible) or len(set(ordered + unranked)) != len(eligible):
            findings.append(f"isolated_submission.relative_tournament.dimensions.{raw_name}.ranking_must_account_for_each_eligible_company_once")
        _isolated_evidence_refs(
            detail.get("evidence"), path=f"isolated_submission.relative_tournament.dimensions.{raw_name}.evidence", findings=findings,
        )
        rationale = detail.get("status_note") or detail.get("reason") or detail.get("ranking_direction")
        if not _text(rationale):
            rationale = "Reference-only ordering from the isolated cutoff forecast; it is neither a causal control nor an overall winner."
        rankings.append({
            "dimension_id": canonical_id,
            "ordered_company_ids": ordered,
            "unranked_company_ids": unranked,
            "rationale": rationale,
        })
    reference_tuple = _reference(h1_receipt_ref, "h1_receipt_ref", findings)
    reference = {"receipt_id": reference_tuple[0], "receipt_version": reference_tuple[1]} if reference_tuple else None
    snapshot = _mapping(universe_snapshot)
    forecast_epochs = {forecast.get("forecast_epoch_id") for forecast in forecasts}
    if len(forecast_epochs) != 1:
        findings.append("isolated_submission.tournament_forecasts_must_share_one_epoch")
    forecast_epoch_id = next(iter(forecast_epochs), FORECAST_EPOCH_ID)
    is_v2 = forecast_epoch_id == FORECAST_EPOCH_ID_V2
    tournament = {
        "schema_version": TOURNAMENT_SCHEMA_VERSION,
        "tournament_id": f"TOURNAMENT:{pilot_id}:V2" if is_v2 else f"TOURNAMENT:{pilot_id}",
        "forecast_epoch_id": forecast_epoch_id,
        "cutoff_at": snapshot.get("cutoff_at"),
        "universe_id": snapshot.get("universe_id"),
        "source_packet_refs": [reference] if reference else [],
        "ranked_company_ids": list(eligible),
        "forecast_ids": [forecast.get("forecast_id") for forecast in forecasts if forecast.get("company_id") in eligible],
        "dimension_rankings": rankings,
        "object_class": "RELATIVE_TRAJECTORY_TOURNAMENT",
        "claim_class": "RELATIVE_TRAJECTORY_REFERENCE",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }
    validation = validate_relative_trajectory_tournament(
        tournament, forecasts=forecasts, universe_snapshot=universe_snapshot, stage0_package=stage0_package,
    )
    findings.extend(f"compiled_tournament:{finding}" for finding in validation["findings"])
    return _result(findings, tournament=tournament if not findings else None)


def _probability_map(window: dict[str, Any]) -> dict[str, float]:
    return {str(item["label"]): float(item["probability"]) for item in _items(window.get("probabilities"))}


def _score(probabilities: dict[str, float], labels: tuple[str, ...], realized: str) -> dict[str, float]:
    brier = sum((probabilities[label] - (1.0 if label == realized else 0.0)) ** 2 for label in labels)
    cumulative_probability = 0.0
    rps = 0.0
    realized_index = labels.index(realized)
    for index, label in enumerate(labels[:-1]):
        cumulative_probability += probabilities[label]
        rps += (cumulative_probability - (1.0 if index >= realized_index else 0.0)) ** 2
    return {"brier": brier, "ranked_probability_score": rps / max(len(labels) - 1, 1)}


def _binary_score(probability: float, realized: bool) -> dict[str, float]:
    return {"brier": (probability - (1.0 if realized else 0.0)) ** 2}


def validate_forecast_outcome_access_authorization(
    authorization: Any, *, forecast: Any, acquisition_scope: Any | None = None,
    measurement_contract: Any | None = None,
) -> dict[str, Any]:
    """Validate a custodian-only read permission without accepting any outcome facts."""
    findings: list[str] = []
    item = _closed(
        authorization, _OUTCOME_ACCESS_KEYS, "outcome_access", findings,
        required=_OUTCOME_ACCESS_KEYS - {"outcome_measurement_contract_ref", "forecast_acquisition_scope_ref"},
    )
    frozen = _mapping(forecast)
    schema_version = item.get("schema_version")
    expected_schema = (
        OUTCOME_ACCESS_SCHEMA_VERSION_V3 if frozen.get("schema_version") in ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS
        else OUTCOME_ACCESS_SCHEMA_VERSION_V2 if frozen.get("schema_version") in MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS
        else OUTCOME_ACCESS_SCHEMA_VERSION
    )
    if schema_version != expected_schema:
        findings.append("outcome_access.schema_version_invalid")
    _require_text(item, "authorization_id", "outcome_access", findings)
    for field in ("forecast_id", "company_id", "cutoff_at"):
        if item.get(field) != frozen.get(field):
            findings.append(f"outcome_access.{field}_must_match_frozen_forecast")
    _require_text(item, "custodian_id", "outcome_access", findings)
    _instant(item.get("authorized_at"), "outcome_access.authorized_at", findings)
    if item.get("outcome_windows") != list(FORECAST_WINDOWS):
        findings.append("outcome_access.outcome_windows_must_match_frozen_forecast")
    if schema_version == OUTCOME_ACCESS_SCHEMA_VERSION:
        if item.get("outcome_measurement_contract_ref") is not None or item.get("forecast_acquisition_scope_ref") is not None:
            findings.append("outcome_access.v1_cannot_retrofit_measurement_contract")
    elif schema_version == OUTCOME_ACCESS_SCHEMA_VERSION_V2:
        ref = _outcome_measurement_contract_reference(
            item.get("outcome_measurement_contract_ref"), "outcome_access.outcome_measurement_contract_ref", findings,
        )
        if ref and ref != frozen.get("outcome_measurement_contract_ref"):
            findings.append("outcome_access.measurement_contract_must_match_frozen_forecast")
        if item.get("forecast_acquisition_scope_ref") is not None:
            findings.append("outcome_access.v2_cannot_retrofit_acquisition_scope")
    elif schema_version == OUTCOME_ACCESS_SCHEMA_VERSION_V3:
        ref = _outcome_measurement_contract_reference(
            item.get("outcome_measurement_contract_ref"), "outcome_access.outcome_measurement_contract_ref", findings,
        )
        if ref and ref != frozen.get("outcome_measurement_contract_ref"):
            findings.append("outcome_access.measurement_contract_must_match_frozen_forecast")
        scope_validation = validate_forecast_acquisition_scope(
            acquisition_scope, measurement_contract=measurement_contract,
        )
        findings.extend(f"outcome_access.acquisition_scope:{finding}" for finding in scope_validation["findings"])
        scope = _mapping(scope_validation.get("acquisition_scope"))
        scope_ref = _forecast_acquisition_scope_reference(
            item.get("forecast_acquisition_scope_ref"), "outcome_access.forecast_acquisition_scope_ref", findings,
        )
        if scope_ref and scope_ref != frozen.get("forecast_acquisition_scope_ref"):
            findings.append("outcome_access.acquisition_scope_must_match_frozen_forecast")
        if scope_ref and scope_ref != {"scope_id": scope.get("scope_id"), "scope_version": scope.get("scope_version")}:
            findings.append("outcome_access.acquisition_scope_must_match_registered_scope")
    if item.get("object_class") != "FORECAST_OUTCOME_ACCESS_AUTHORIZATION":
        findings.append("outcome_access.object_class_invalid")
    if item.get("claim_class") != "CUSTODIAN_ONLY_OUTCOME_ACQUISITION":
        findings.append("outcome_access.claim_class_invalid")
    if item.get("allowed_outputs") != OUTCOME_ACCESS_ALLOWED_OUTPUTS:
        findings.append("outcome_access.allowed_outputs_must_remain_acquisition_only")
    return _result(findings, authorization=deepcopy(item) if not findings else None)


def _validate_v3_realized_measurement(
    entry: dict[str, Any], *, cell: dict[str, Any], path: str, findings: list[str], require_label: bool = True,
    expected_issuer_id: Any = None,
) -> None:
    source = _closed(
        entry.get("outcome_source"), _OUTCOME_SOURCE_KEYS_V2, f"{path}.outcome_source", findings,
        required=_OUTCOME_SOURCE_V2_REQUIRED_KEYS,
    )
    _require_text(source, "source_id", f"{path}.outcome_source", findings)
    source_url = _require_text(source, "source_url", f"{path}.outcome_source", findings)
    if source_url and not source_url.startswith("https://"):
        findings.append(f"{path}.outcome_source.source_url_must_be_https_official_artifact")
    _outcome_source_availability(source, f"{path}.outcome_source", findings)
    field_ref = _require_text(source, "field_ref", f"{path}.outcome_source", findings)
    if field_ref and not PAGE_REFERENCE.search(field_ref):
        findings.append(f"{path}.outcome_source.field_ref_must_be_paged_reference")
    if source.get("source_field_id") != cell.get("source_field_id"):
        findings.append(f"{path}.outcome_source.source_field_id_must_match_measurement_contract")
    if source.get("official_source_type") != cell.get("official_source_type"):
        findings.append(f"{path}.outcome_source.official_source_type_must_match_measurement_contract")
    if source.get("issuer_id") != expected_issuer_id:
        findings.append(f"{path}.outcome_source.issuer_id_must_match_frozen_forecast")
    for field in ("responsibility_boundary", "unit", "outcome_period_end"):
        if source.get(field) != cell.get(field):
            findings.append(f"{path}.outcome_source.{field}_must_match_measurement_contract")
    measured = _closed(
        entry.get("realized_measurement"), _REALIZED_MEASUREMENT_KEYS, f"{path}.realized_measurement", findings,
        required={"measurement_id", "measurement_kind", "unit", "outcome_period_end", "responsibility_boundary"},
    )
    if measured.get("measurement_id") != cell.get("measurement_id"):
        findings.append(f"{path}.realized_measurement.measurement_id_must_match_measurement_contract")
    kind = cell.get("measurement_kind")
    if measured.get("measurement_kind") != kind:
        findings.append(f"{path}.realized_measurement.measurement_kind_must_match_measurement_contract")
    if measured.get("unit") != cell.get("unit"):
        findings.append(f"{path}.realized_measurement.unit_must_match_measurement_contract")
    if measured.get("outcome_period_end") != cell.get("outcome_period_end"):
        findings.append(f"{path}.realized_measurement.outcome_period_end_must_match_measurement_contract")
    if measured.get("responsibility_boundary") != cell.get("responsibility_boundary"):
        findings.append(f"{path}.realized_measurement.responsibility_boundary_must_match_measurement_contract")
    if kind == "ORDINAL_THRESHOLD":
        value = measured.get("numeric_value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            findings.append(f"{path}.realized_measurement.numeric_value_required")
            return
        if measured.get("boolean_value") is not None:
            findings.append(f"{path}.realized_measurement.ordinal_cannot_include_boolean_value")
        formula = _measurement_formula(
            cell.get("measurement_formula"), path=f"{path}.measurement_formula", findings=findings, required=True,
        )
        components: dict[str, dict[str, Any]] = {}
        for component_index, raw_component in enumerate(_items(measured.get("source_components"))):
            component = _closed(
                raw_component, _OUTCOME_SOURCE_COMPONENT_KEYS,
                f"{path}.realized_measurement.source_components[{component_index}]", findings,
                required=_OUTCOME_SOURCE_COMPONENT_REQUIRED_KEYS,
            )
            field_id = _require_text(
                component, "field_id", f"{path}.realized_measurement.source_components[{component_index}]", findings,
            )
            _require_text(component, "source_id", f"{path}.realized_measurement.source_components[{component_index}]", findings)
            component_url = _require_text(
                component, "source_url", f"{path}.realized_measurement.source_components[{component_index}]", findings,
            )
            if component_url and not component_url.startswith("https://"):
                findings.append(
                    f"{path}.realized_measurement.source_components[{component_index}].source_url_must_be_https_official_artifact"
                )
            _outcome_source_availability(
                component, f"{path}.realized_measurement.source_components[{component_index}]", findings,
            )
            field_ref = _require_text(
                component, "field_ref", f"{path}.realized_measurement.source_components[{component_index}]", findings)
            if field_ref and not PAGE_REFERENCE.search(field_ref):
                findings.append(f"{path}.realized_measurement.source_components[{component_index}].field_ref_must_be_paged_reference")
            if component.get("official_source_type") != cell.get("official_source_type"):
                findings.append(f"{path}.realized_measurement.source_components[{component_index}].official_source_type_must_match_measurement_contract")
            if component.get("issuer_id") != expected_issuer_id:
                findings.append(f"{path}.realized_measurement.source_components[{component_index}].issuer_id_must_match_frozen_forecast")
            for field in ("responsibility_boundary", "unit", "outcome_period_end"):
                if component.get(field) != cell.get(field):
                    findings.append(
                        f"{path}.realized_measurement.source_components[{component_index}].{field}_must_match_measurement_contract"
                    )
            component_value = component.get("numeric_value")
            if not isinstance(component_value, (int, float)) or isinstance(component_value, bool):
                findings.append(f"{path}.realized_measurement.source_components[{component_index}].numeric_value_required")
            if not field_id or field_id in components:
                findings.append(f"{path}.realized_measurement.source_components[{component_index}].field_id_missing_or_duplicate")
            else:
                components[field_id] = component
        if formula is not None:
            formula_kind = formula.get("formula_kind")
            if formula_kind == "DIRECT_NUMERIC":
                expected_fields = [formula.get("value_field_id")]
            elif formula_kind == "RATIO":
                expected_fields = [formula.get("numerator_field_id"), formula.get("denominator_field_id")]
            else:
                expected_fields = []
            expected_set = {field for field in expected_fields if _text(field)}
            if set(components) != expected_set:
                findings.append(f"{path}.realized_measurement.source_components_must_match_measurement_formula")
            elif all(isinstance(components[field].get("numeric_value"), (int, float)) and not isinstance(components[field].get("numeric_value"), bool) for field in expected_set):
                if formula_kind == "DIRECT_NUMERIC":
                    implied_value = float(components[str(formula["value_field_id"])]["numeric_value"])
                else:
                    denominator = float(components[str(formula["denominator_field_id"])]["numeric_value"])
                    if denominator == 0.0:
                        findings.append(f"{path}.realized_measurement.formula_denominator_must_be_nonzero")
                        implied_value = None
                    else:
                        implied_value = float(components[str(formula["numerator_field_id"])]["numeric_value"]) / denominator
                if implied_value is not None and not math.isclose(float(value), implied_value, rel_tol=1e-9, abs_tol=1e-12):
                    findings.append(f"{path}.realized_measurement.numeric_value_must_follow_measurement_formula")
        lower, upper = float(cell["lower_threshold"]), float(cell["upper_threshold"])
        labels = _items(cell.get("label_order"))
        implied = labels[0] if float(value) < lower else labels[2] if float(value) > upper else labels[1]
        if require_label and entry.get("realized_label") != implied:
            findings.append(f"{path}.realized_label_must_follow_measurement_contract_thresholds")
    elif kind == "BINARY_EVENT":
        value = measured.get("boolean_value")
        if not isinstance(value, bool):
            findings.append(f"{path}.realized_measurement.boolean_value_required")
            return
        if measured.get("numeric_value") is not None:
            findings.append(f"{path}.realized_measurement.binary_cannot_include_numeric_value")
        if require_label and entry.get("realized_label") is not value:
            findings.append(f"{path}.realized_label_must_match_binary_measurement")


def settle_company_state_forecast(
    forecast: Any, settlement: Any, *, measurement_contract: Any | None = None,
    observation_receipts: dict[str, Any] | None = None, acquisition_scope: Any | None = None,
) -> dict[str, Any]:
    """Settle an immutable forecast by dimension; never produce a composite score."""
    findings: list[str] = []
    frozen = _mapping(forecast)
    item = _closed(
        settlement, _SETTLEMENT_KEYS, "settlement", findings,
        required=_SETTLEMENT_KEYS - {"outcome_measurement_contract_ref"},
    )
    is_v3_forecast = frozen.get("schema_version") in MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS
    observation_by_id = observation_receipts if isinstance(observation_receipts, dict) else {}
    expected_schema = SETTLEMENT_SCHEMA_VERSION_V2 if is_v3_forecast else SETTLEMENT_SCHEMA_VERSION
    if item.get("schema_version") != expected_schema:
        findings.append("settlement.schema_version_invalid")
    measurement_cells: dict[tuple[str, str], dict[str, Any]] = {}
    if is_v3_forecast:
        contract_validation = validate_forecast_outcome_measurement_contract(measurement_contract)
        findings.extend(f"settlement.measurement_contract:{finding}" for finding in contract_validation["findings"])
        contract_item = _mapping(contract_validation.get("measurement_contract"))
        contract_ref = _outcome_measurement_contract_reference(
            item.get("outcome_measurement_contract_ref"), "settlement.outcome_measurement_contract_ref", findings,
        )
        if contract_ref and contract_ref != frozen.get("outcome_measurement_contract_ref"):
            findings.append("settlement.measurement_contract_must_match_frozen_forecast")
        if contract_ref and contract_ref != {
            "measurement_contract_id": contract_item.get("measurement_contract_id"),
            "measurement_contract_version": contract_item.get("measurement_contract_version"),
        }:
            findings.append("settlement.measurement_contract_must_match_registered_contract")
        measurement_cells = _measurement_contract_cell_index(contract_item)
    elif item.get("outcome_measurement_contract_ref") is not None:
        findings.append("settlement.v1_cannot_retrofit_measurement_contract")
    for field, expected in (("forecast_id", frozen.get("forecast_id")), ("company_id", frozen.get("company_id")), ("cutoff_at", frozen.get("cutoff_at"))):
        if item.get(field) != expected:
            findings.append(f"settlement.{field}_must_match_frozen_forecast")
    _require_text(item, "settlement_id", "settlement", findings)
    _instant(item.get("settled_at"), "settlement.settled_at", findings)
    _require_text(item, "custodian_id", "settlement", findings)
    if item.get("outcome_access_authorized") is not True:
        findings.append("settlement.outcome_access_must_be_authorized_by_custodian")
    if item.get("object_class") != "FORECAST_SETTLEMENT":
        findings.append("settlement.object_class_invalid")
    if item.get("claim_class") != "PREQUENTIAL_FEEDBACK":
        findings.append("settlement.claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"]:
        findings.append("settlement.allowed_outputs_must_remain_evaluation_only")
    cutoff = _instant(frozen.get("cutoff_at"), "forecast.cutoff_at", findings)
    settled_at = _instant(item.get("settled_at"), "settlement.settled_at", findings)
    frozen_dimensions = {item.get("dimension_id"): item for item in _items(frozen.get("dimensions")) if isinstance(item, dict)}
    expected_keys = {
        (dimension_id, window_id)
        for dimension_id in FORECAST_DIMENSIONS for window_id in FORECAST_WINDOWS
    }
    results: list[dict[str, Any]] = []
    actual_keys: set[tuple[str, str]] = set()
    for index, raw in enumerate(_items(item.get("dimension_settlements"))):
        entry = _closed(
            raw, _DIMENSION_SETTLEMENT_KEYS, f"settlement.dimension_settlements[{index}]", findings,
            required=_DIMENSION_SETTLEMENT_KEYS - {"outcome_source", "realized_measurement", "outcome_observation_ref"},
        )
        dimension_id = entry.get("dimension_id")
        window_id = entry.get("window_id")
        key = (str(dimension_id), str(window_id))
        if dimension_id not in FORECAST_DIMENSIONS or window_id not in FORECAST_WINDOWS or key in actual_keys:
            findings.append(f"settlement.dimension_settlements[{index}].dimension_or_window_invalid_or_duplicate")
            continue
        actual_keys.add(key)
        status = entry.get("status")
        if status not in SETTLEMENT_STATUSES:
            findings.append(f"settlement.dimension_settlements[{index}].status_invalid")
            continue
        frozen_dimension = _mapping(frozen_dimensions.get(dimension_id))
        evidence_status = frozen_dimension.get("evidence_status")
        realized = entry.get("realized_label")
        if status == "EVIDENCE_INELIGIBLE":
            if evidence_status != "EVIDENCE_INELIGIBLE" or realized is not None:
                findings.append(f"settlement.dimension_settlements[{index}].ineligible_status_must_match_frozen_coverage_gap")
            results.append({"dimension_id": dimension_id, "window_id": window_id, "status": status, "score": None})
            continue
        if evidence_status != "MODEL_UNCERTAIN":
            findings.append(f"settlement.dimension_settlements[{index}].cannot_settle_unforecast_dimension")
        if status == "MEASUREMENT_MISMATCH":
            if is_v3_forecast:
                cell = measurement_cells.get(key)
                if cell is None:
                    findings.append(f"settlement.dimension_settlements[{index}].measurement_contract_cell_missing")
                if entry.get("outcome_source") is not None or entry.get("realized_measurement") is not None:
                    findings.append(f"settlement.dimension_settlements[{index}].v3_must_reference_observation_not_redeclare_raw_field")
                observation_ref = _closed(
                    entry.get("outcome_observation_ref"), _OUTCOME_OBSERVATION_REF_KEYS,
                    f"settlement.dimension_settlements[{index}].outcome_observation_ref", findings,
                )
                observation_id = _require_text(
                    observation_ref, "observation_id", f"settlement.dimension_settlements[{index}].outcome_observation_ref", findings,
                )
                receipt = _mapping(observation_by_id.get(observation_id))
                if not receipt:
                    findings.append(f"settlement.dimension_settlements[{index}].observation_receipt_not_registered")
                else:
                    receipt_validation = validate_forecast_outcome_observation_receipt(
                        receipt, forecast=frozen, measurement_contract=measurement_contract,
                        acquisition_scope=acquisition_scope,
                    )
                    findings.extend(f"settlement.dimension_settlements[{index}].observation:{finding}" for finding in receipt_validation["findings"])
                    receipt_observed_at = _instant(
                        receipt.get("observed_at"), f"settlement.dimension_settlements[{index}].observation.observed_at", findings,
                    )
                    if settled_at and receipt_observed_at and receipt_observed_at > settled_at:
                        findings.append(f"settlement.dimension_settlements[{index}].observation_receipt_cannot_follow_settlement")
                    if receipt.get("dimension_id") != dimension_id or receipt.get("window_id") != window_id:
                        findings.append(f"settlement.dimension_settlements[{index}].observation_receipt_cell_mismatch")
                    if receipt.get("observation_status") != "MEASUREMENT_MISMATCH":
                        findings.append(f"settlement.dimension_settlements[{index}].observation_receipt_must_record_measurement_mismatch")
            if realized is not None:
                findings.append(f"settlement.dimension_settlements[{index}].nonobserved_status_cannot_claim_realized_label")
            results.append({"dimension_id": dimension_id, "window_id": window_id, "status": status, "score": None})
            continue
        if status == "OBSERVED":
            if not is_v3_forecast:
                findings.append(f"settlement.dimension_settlements[{index}].legacy_forecast_must_remain_unscored")
            if not is_v3_forecast and entry.get("realized_measurement") is not None:
                findings.append(f"settlement.dimension_settlements[{index}].v1_cannot_include_realized_measurement")
            cell = measurement_cells.get(key) if is_v3_forecast else None
            observation_entry = entry
            if is_v3_forecast and cell is None:
                findings.append(f"settlement.dimension_settlements[{index}].measurement_contract_cell_missing")
            if is_v3_forecast:
                if entry.get("outcome_source") is not None or entry.get("realized_measurement") is not None:
                    findings.append(f"settlement.dimension_settlements[{index}].v3_must_reference_observation_not_redeclare_raw_field")
                observation_ref = _closed(
                    entry.get("outcome_observation_ref"), _OUTCOME_OBSERVATION_REF_KEYS,
                    f"settlement.dimension_settlements[{index}].outcome_observation_ref", findings,
                )
                observation_id = _require_text(
                    observation_ref, "observation_id", f"settlement.dimension_settlements[{index}].outcome_observation_ref", findings,
                )
                receipt = _mapping(observation_by_id.get(observation_id))
                if not receipt:
                    findings.append(f"settlement.dimension_settlements[{index}].observation_receipt_not_registered")
                else:
                    receipt_validation = validate_forecast_outcome_observation_receipt(
                        receipt, forecast=frozen, measurement_contract=measurement_contract,
                        acquisition_scope=acquisition_scope,
                    )
                    findings.extend(f"settlement.dimension_settlements[{index}].observation:{finding}" for finding in receipt_validation["findings"])
                    receipt_observed_at = _instant(
                        receipt.get("observed_at"), f"settlement.dimension_settlements[{index}].observation.observed_at", findings,
                    )
                    if settled_at and receipt_observed_at and receipt_observed_at > settled_at:
                        findings.append(f"settlement.dimension_settlements[{index}].observation_receipt_cannot_follow_settlement")
                    if receipt.get("dimension_id") != dimension_id or receipt.get("window_id") != window_id:
                        findings.append(f"settlement.dimension_settlements[{index}].observation_receipt_cell_mismatch")
                    observation_entry = {**entry, "outcome_source": receipt.get("outcome_source"), "realized_measurement": receipt.get("realized_measurement")}
            source_keys = _OUTCOME_SOURCE_KEYS_V2 if is_v3_forecast else _OUTCOME_SOURCE_KEYS
            source = _closed(
                observation_entry.get("outcome_source"), source_keys,
                f"settlement.dimension_settlements[{index}].outcome_source", findings,
                required=_OUTCOME_SOURCE_V2_REQUIRED_KEYS if is_v3_forecast else None,
            )
            source_id = _require_text(source, "source_id", f"settlement.dimension_settlements[{index}].outcome_source", findings)
            if is_v3_forecast:
                source_at, source_day = _outcome_source_availability(
                    source, f"settlement.dimension_settlements[{index}].outcome_source", findings,
                )
            else:
                source_at = _instant(source.get("source_available_at"), f"settlement.dimension_settlements[{index}].outcome_source.source_available_at", findings)
                source_day = None
            field_ref = _require_text(source, "field_ref", f"settlement.dimension_settlements[{index}].outcome_source", findings)
            if field_ref and not PAGE_REFERENCE.search(field_ref):
                findings.append(f"settlement.dimension_settlements[{index}].outcome_source.field_ref_must_be_paged_reference")
            if cutoff and not _source_follows_cutoff(source_at, source_day, cutoff):
                findings.append(f"settlement.dimension_settlements[{index}].outcome_source_must_follow_forecast_cutoff")
            if settled_at and not _source_precedes_receipt(source_at, source_day, settled_at):
                findings.append(f"settlement.dimension_settlements[{index}].outcome_source_cannot_follow_settlement")
            window = next((candidate for candidate in _items(frozen_dimension.get("forecast_by_window")) if _mapping(candidate).get("window_id") == window_id), None)
            if isinstance(window, dict) and source_id:
                if is_v3_forecast and cell is not None:
                    kind = _measurement_kind_for_forecast_window(window)
                    if cell.get("measurement_kind") != kind:
                        findings.append(f"settlement.dimension_settlements[{index}].measurement_kind_must_match_frozen_forecast_window")
                    _validate_v3_realized_measurement(
                        observation_entry, cell=cell, path=f"settlement.dimension_settlements[{index}]", findings=findings,
                        expected_issuer_id=frozen.get("issuer_id"),
                    )
                if "probabilities" in window:
                    labels = _labels_for(str(dimension_id))
                    if realized not in labels:
                        findings.append(f"settlement.dimension_settlements[{index}].realized_label_invalid")
                    else:
                        results.append({
                            "dimension_id": dimension_id, "window_id": window_id, "status": status,
                            "score": _score(_probability_map(window), labels, str(realized)),
                        })
                else:
                    if not isinstance(realized, bool):
                        findings.append(f"settlement.dimension_settlements[{index}].binary_event_requires_boolean_realized_label")
                    else:
                        results.append({
                            "dimension_id": dimension_id, "window_id": window_id, "status": status,
                            "score": _binary_score(float(window.get("event_occurs_probability", 0.0)), realized),
                        })
            continue
        if not is_v3_forecast and entry.get("realized_measurement") is not None:
            findings.append(f"settlement.dimension_settlements[{index}].v1_cannot_include_realized_measurement")
        if realized is not None:
            findings.append(f"settlement.dimension_settlements[{index}].nonobserved_status_cannot_claim_realized_label")
        results.append({"dimension_id": dimension_id, "window_id": window_id, "status": status, "score": None})
    if actual_keys != expected_keys:
        findings.append("settlement.must_account_for_every_frozen_dimension_and_window")
    eligible = sum(1 for dimension in frozen_dimensions.values() if dimension.get("evidence_status") == "MODEL_UNCERTAIN") * len(FORECAST_WINDOWS)
    observed = sum(1 for result in results if result["status"] == "OBSERVED")
    return _result(
        findings,
        settlement=deepcopy(item) if not findings else None,
        dimension_scores=results if not findings else [],
        coverage={
            "eligible_forecast_cells": eligible,
            "observed_scored_cells": observed,
            "selective_coverage": observed / eligible if eligible else None,
            "evidence_ineligible_cells": len(expected_keys) - eligible,
        } if not findings else None,
    )


def _forecast_cell_index(forecast: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(dimension.get("dimension_id")), str(window.get("window_id"))): window
        for dimension in _items(forecast.get("dimensions"))
        if _mapping(dimension).get("evidence_status") == "MODEL_UNCERTAIN"
        for window in _items(_mapping(dimension).get("forecast_by_window"))
        if isinstance(window, dict)
    }


def _unique_expected_label(window: dict[str, Any]) -> str | bool | None:
    probabilities = _items(window.get("probabilities"))
    if probabilities:
        highest = max(float(item.get("probability", 0.0)) for item in probabilities if isinstance(item, dict))
        modal = [
            str(item.get("label")) for item in probabilities
            if isinstance(item, dict) and float(item.get("probability", 0.0)) == highest
        ]
        return modal[0] if len(modal) == 1 else None
    probability = window.get("event_occurs_probability")
    if not isinstance(probability, (int, float)) or isinstance(probability, bool) or float(probability) == 0.5:
        return None
    return float(probability) > 0.5


def _realized_probability(window: dict[str, Any], realized: Any) -> float | None:
    probabilities = _items(window.get("probabilities"))
    if probabilities:
        for item in probabilities:
            if isinstance(item, dict) and item.get("label") == realized:
                return float(item.get("probability", 0.0))
        return None
    probability = window.get("event_occurs_probability")
    if not isinstance(probability, (int, float)) or isinstance(probability, bool) or not isinstance(realized, bool):
        return None
    return float(probability) if realized else 1.0 - float(probability)


def _direct_error_signatures(
    scope: str, refs: list[tuple[str, str]], *, forecast: dict[str, Any], settlement: dict[str, Any],
    pairing: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Derive cell-local direct feedback from frozen predictions and settled labels."""
    findings: list[str] = []
    signatures: list[dict[str, Any]] = []
    forecast_cells = _forecast_cell_index(forecast)
    settlement_cells = {
        (str(entry.get("dimension_id")), str(entry.get("window_id"))): entry
        for entry in _items(settlement.get("dimension_settlements")) if isinstance(entry, dict)
    }
    baseline_cells = {
        (str(entry.get("dimension_id")), str(entry.get("window_id"))): entry
        for entry in _items(_mapping(pairing).get("baseline_cells")) if isinstance(entry, dict)
    }
    if scope == "STATE_DEFINITION":
        return [], ["attribution.state_definition_not_mechanically_diagnostic"]
    for dimension_id, window_id in refs:
        cell = _mapping(settlement_cells.get((dimension_id, window_id)))
        if scope == "COVERAGE":
            if cell.get("status") == "MEASUREMENT_MISMATCH":
                signatures.append({
                    "dimension_id": dimension_id,
                    "window_id": window_id,
                    "expected_label": "CONTRACT_MATCHED_MEASUREMENT",
                    "realized_label": "MEASUREMENT_MISMATCH",
                    "error_kind": "MEASUREMENT_MISMATCH",
                })
            continue
        if cell.get("status") != "OBSERVED":
            continue
        window = _mapping(forecast_cells.get((dimension_id, window_id)))
        expected = _unique_expected_label(window)
        realized = cell.get("realized_label")
        signature = {
            "dimension_id": dimension_id,
            "window_id": window_id,
            "expected_label": expected,
            "realized_label": realized,
        }
        if scope == "CALIBRATION":
            if expected is None or expected == realized:
                findings.append("attribution.calibration_requires_directional_class_miss")
                continue
            signatures.append({**signature, "error_kind": "DIRECTIONAL_CLASS_MISS"})
        elif scope == "UNCERTAINTY_POLICY":
            if expected is None or _realized_probability(window, realized) != 0.0:
                findings.append("attribution.uncertainty_policy_requires_contradicted_certainty")
                continue
            signatures.append({**signature, "error_kind": "REALIZED_LABEL_ASSIGNED_ZERO_PROBABILITY"})
        elif scope == "BASELINE_PERFORMANCE":
            baseline_window = _mapping(baseline_cells.get((dimension_id, window_id)))
            baseline_expected = _unique_expected_label(baseline_window)
            baseline_score = _baseline_score(
                baseline_window, window, dimension_id=dimension_id, realized=realized,
            )
            forecast_score = (
                _score(_probability_map(window), _labels_for(dimension_id), str(realized))
                if _items(window.get("probabilities")) and isinstance(realized, str)
                else _binary_score(float(window.get("event_occurs_probability", 0.0)), realized)
                if isinstance(realized, bool)
                else None
            )
            if (
                expected is None or expected == realized or baseline_expected != realized
                or baseline_score is None or forecast_score is None
                or float(baseline_score["brier"]) >= float(forecast_score["brier"])
            ):
                findings.append("attribution.baseline_performance_requires_correct_baseline_and_forecast_directional_miss")
                continue
            signatures.append({
                **signature,
                "baseline_expected_label": baseline_expected,
                "error_kind": "BASELINE_CORRECT_FORECAST_DIRECTIONAL_MISS",
            })
    return signatures, findings


def _cell_refs(value: Any, *, path: str, findings: list[str]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(_items(value)):
        item = _closed(raw, _CELL_REF_KEYS, f"{path}[{index}]", findings)
        key = (str(item.get("dimension_id")), str(item.get("window_id")))
        if item.get("dimension_id") not in FORECAST_DIMENSIONS or item.get("window_id") not in FORECAST_WINDOWS or key in seen:
            findings.append(f"{path}[{index}].dimension_or_window_invalid_or_duplicate")
            continue
        seen.add(key)
        refs.append(key)
    if not refs:
        findings.append(f"{path}_must_be_nonempty")
    return refs


def validate_forecast_pairing(
    pairing: Any, *, forecast: Any, measurement_contract: Any | None = None,
) -> dict[str, Any]:
    """Freeze a simple baseline beside one forecast before outcomes are visible.

    The baseline is deliberately a narrowly-scoped probability contract.  It
    gives a later evidence-priority or rival-hypothesis proposal a real paired
    comparator without treating the relative result as a causal finding.
    """
    findings: list[str] = []
    item = _closed(pairing, _PAIRING_KEYS, "pairing", findings, required=_PAIRING_KEYS - {"holdout_binding"})
    frozen = _mapping(forecast)
    schema_version = item.get("schema_version")
    if schema_version not in {PAIRING_SCHEMA_VERSION, PAIRING_SCHEMA_VERSION_V2, PAIRING_SCHEMA_VERSION_V3}:
        findings.append("pairing.schema_version_invalid")
    _require_text(item, "pairing_id", "pairing", findings)
    for field in ("forecast_id", "company_id", "cutoff_at"):
        if item.get(field) != frozen.get(field):
            findings.append(f"pairing.{field}_must_match_frozen_forecast")
    _require_text(item, "task_contract_ref", "pairing", findings)
    _require_text(item, "evidence_budget_id", "pairing", findings)
    _require_text(item, "baseline_method_id", "pairing", findings)
    _require_text(item, "enhanced_method_id", "pairing", findings)
    if item.get("baseline_method_id") == item.get("enhanced_method_id"):
        findings.append("pairing.baseline_and_enhanced_method_must_differ")
    refs = _items(item.get("source_packet_refs"))
    if refs != _items(frozen.get("source_packet_refs")):
        findings.append("pairing.source_packet_refs_must_match_frozen_forecast")
    for index, ref in enumerate(refs):
        _reference(ref, f"pairing.source_packet_refs[{index}]", findings)
    if item.get("object_class") != "FORECAST_METHOD_PAIRING":
        findings.append("pairing.object_class_invalid")
    if item.get("claim_class") != "PAIRED_FORECAST_ABLATION":
        findings.append("pairing.claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"]:
        findings.append("pairing.allowed_outputs_must_remain_evaluation_only")

    forecast_cells = _forecast_cell_index(frozen)
    baseline_cells: dict[tuple[str, str], dict[str, Any]] = {}
    for index, raw in enumerate(_items(item.get("baseline_cells"))):
        cell = _closed(
            raw, _BASELINE_CELL_KEYS, f"pairing.baseline_cells[{index}]", findings,
            required={"dimension_id", "window_id"},
        )
        key = (str(cell.get("dimension_id")), str(cell.get("window_id")))
        if key not in forecast_cells or key in baseline_cells:
            findings.append(f"pairing.baseline_cells[{index}].must_match_unique_forecastable_cell")
            continue
        baseline_cells[key] = cell
        forecast_window = forecast_cells[key]
        dimension_id = key[0]
        if "probabilities" in forecast_window:
            if "event_statement" in cell or "event_occurs_probability" in cell:
                findings.append(f"pairing.baseline_cells[{index}].must_match_ordinal_forecast_contract")
            _validate_probability_vector(
                cell.get("probabilities"), _labels_for(dimension_id),
                f"pairing.baseline_cells[{index}].probabilities", findings,
            )
        else:
            if "probabilities" in cell:
                findings.append(f"pairing.baseline_cells[{index}].must_match_binary_forecast_contract")
            if cell.get("event_statement") != forecast_window.get("event_statement"):
                findings.append(f"pairing.baseline_cells[{index}].event_statement_must_match_frozen_forecast")
            probability = cell.get("event_occurs_probability")
            if not isinstance(probability, (int, float)) or isinstance(probability, bool) or not 0.0 <= float(probability) <= 1.0:
                findings.append(f"pairing.baseline_cells[{index}].event_occurs_probability_must_be_unit_interval")
    if set(baseline_cells) != set(forecast_cells):
        findings.append("pairing.baseline_cells_must_cover_every_forecastable_cell_once")
    if schema_version == PAIRING_SCHEMA_VERSION:
        if item.get("holdout_binding") is not None:
            findings.append("pairing.v1_cannot_retrofit_canonical_holdout_binding")
    elif schema_version in {PAIRING_SCHEMA_VERSION_V2, PAIRING_SCHEMA_VERSION_V3}:
        if frozen.get("schema_version") not in MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
            findings.append("pairing.v2_v3_requires_measurement_contract_forecast")
        binding_keys = (
            _HOLDOUT_BINDING_V3_KEYS
            if schema_version == PAIRING_SCHEMA_VERSION_V3 else _HOLDOUT_BINDING_KEYS
        )
        binding = _closed(item.get("holdout_binding"), binding_keys, "pairing.holdout_binding", findings)
        for field in (
            "program_id", "method_version", "holdout_training_episode_id", "company_id", "company_cluster_id",
        ):
            _require_text(binding, field, "pairing.holdout_binding", findings)
        for field in ("cutoff_at", "outcome_not_before", "method_frozen_at", "method_freeze_recorded_at"):
            _instant(binding.get(field), f"pairing.holdout_binding.{field}", findings)
        if binding.get("company_id") != frozen.get("company_id"):
            findings.append("pairing.holdout_binding.company_id_must_match_frozen_forecast")
        binding_cutoff = _instant(binding.get("cutoff_at"), "pairing.holdout_binding.cutoff_at", findings)
        forecast_cutoff = _instant(frozen.get("cutoff_at"), "forecast.cutoff_at", findings)
        if binding_cutoff and forecast_cutoff and binding_cutoff != forecast_cutoff:
            findings.append("pairing.holdout_binding.cutoff_at_must_match_frozen_forecast")
        if binding.get("method_version") != item.get("enhanced_method_id"):
            findings.append("pairing.holdout_binding.method_version_must_match_enhanced_method")
        method_frozen = _instant(binding.get("method_frozen_at"), "pairing.holdout_binding.method_frozen_at", findings)
        freeze_recorded = _instant(binding.get("method_freeze_recorded_at"), "pairing.holdout_binding.method_freeze_recorded_at", findings)
        if method_frozen and freeze_recorded and method_frozen > freeze_recorded:
            findings.append("pairing.holdout_binding.method_freeze_time_order_invalid")
        if schema_version == PAIRING_SCHEMA_VERSION_V3:
            if frozen.get("schema_version") != FORECAST_SCHEMA_VERSION_V6:
                findings.append("pairing.v3_requires_forecast_method_identity_epoch")
            holdout_opens = _instant(
                binding.get("outcome_not_before"), "pairing.holdout_binding.outcome_not_before", findings,
            )
            holdout_closes = _instant(
                binding.get("outcome_window_ends_at"),
                "pairing.holdout_binding.outcome_window_ends_at", findings,
            )
            if holdout_opens and holdout_closes and holdout_closes <= holdout_opens:
                findings.append("pairing.holdout_binding.outcome_window_must_end_after_open")
            training_clusters = _items(binding.get("training_company_cluster_ids"))
            if (
                not training_clusters
                or any(not _text(cluster) for cluster in training_clusters)
                or len(set(training_clusters)) != len(training_clusters)
            ):
                findings.append("pairing.holdout_binding.training_company_cluster_ids_invalid")
            elif binding.get("company_cluster_id") in training_clusters:
                findings.append("pairing.holdout_binding.company_cluster_must_be_unseen_in_training")
            training_windows = _items(binding.get("training_outcome_windows"))
            window_clusters: set[str] = set()
            window_episodes: set[str] = set()
            if not training_windows:
                findings.append("pairing.holdout_binding.training_outcome_windows_must_be_nonempty")
            for index, raw_window in enumerate(training_windows):
                window = _closed(
                    raw_window, _HOLDOUT_TRAINING_WINDOW_KEYS,
                    f"pairing.holdout_binding.training_outcome_windows[{index}]", findings,
                )
                episode_id = _require_text(
                    window, "training_episode_id",
                    f"pairing.holdout_binding.training_outcome_windows[{index}]", findings,
                )
                cluster_id = _require_text(
                    window, "company_cluster_id",
                    f"pairing.holdout_binding.training_outcome_windows[{index}]", findings,
                )
                if episode_id in window_episodes:
                    findings.append(
                        f"pairing.holdout_binding.training_outcome_windows[{index}].training_episode_id_must_not_repeat"
                    )
                window_episodes.add(episode_id)
                window_clusters.add(cluster_id)
                opens_after = _instant(
                    window.get("opens_after"),
                    f"pairing.holdout_binding.training_outcome_windows[{index}].opens_after", findings,
                )
                closes_at = _instant(
                    window.get("closes_at"),
                    f"pairing.holdout_binding.training_outcome_windows[{index}].closes_at", findings,
                )
                if opens_after and closes_at and closes_at <= opens_after:
                    findings.append(
                        f"pairing.holdout_binding.training_outcome_windows[{index}].must_end_after_open"
                    )
                if (
                    opens_after and closes_at and holdout_opens and holdout_closes
                    and opens_after < holdout_closes and holdout_opens < closes_at
                ):
                    findings.append(
                        f"pairing.holdout_binding.training_outcome_windows[{index}].must_not_overlap_holdout_outcome_window"
                    )
            if set(training_clusters) != window_clusters:
                findings.append("pairing.holdout_binding.training_clusters_must_match_outcome_windows")
        if frozen.get("schema_version") == FORECAST_SCHEMA_VERSION_V6:
            method_ref = _mapping(frozen.get("forecast_method_ref"))
            if binding.get("program_id") != method_ref.get("program_id"):
                findings.append("pairing.holdout_binding.program_id_must_match_forecast_method_identity")
            if binding.get("method_version") != method_ref.get("method_version"):
                findings.append("pairing.holdout_binding.method_version_must_match_forecast_method_identity")
            forecast_method_frozen = _instant(
                method_ref.get("method_frozen_at"), "forecast.forecast_method_ref.method_frozen_at", findings,
            )
            forecast_method_recorded = _instant(
                method_ref.get("method_freeze_recorded_at"),
                "forecast.forecast_method_ref.method_freeze_recorded_at", findings,
            )
            if method_frozen and forecast_method_frozen and method_frozen != forecast_method_frozen:
                findings.append("pairing.holdout_binding.method_frozen_at_must_match_forecast_method_identity")
            if freeze_recorded and forecast_method_recorded and freeze_recorded != forecast_method_recorded:
                findings.append("pairing.holdout_binding.method_freeze_recorded_at_must_match_forecast_method_identity")
        binding_cells: set[tuple[str, str]] = set()
        measurement_cells = {
            (str(cell.get("dimension_id")), str(cell.get("window_id"))): cell
            for cell in _items(_mapping(measurement_contract).get("cells")) if isinstance(cell, dict)
        }
        for index, raw in enumerate(_items(binding.get("evaluated_cells"))):
            cell = _closed(raw, _HOLDOUT_BINDING_CELL_KEYS, f"pairing.holdout_binding.evaluated_cells[{index}]", findings)
            key = (str(cell.get("dimension_id")), str(cell.get("window_id")))
            if key not in baseline_cells or key in binding_cells:
                findings.append(f"pairing.holdout_binding.evaluated_cells[{index}].must_be_unique_pre_registered_baseline_cell")
                continue
            binding_cells.add(key)
            if not _text(cell.get("outcome_period_end")):
                findings.append(f"pairing.holdout_binding.evaluated_cells[{index}].outcome_period_end_required")
            elif measurement_contract is None:
                findings.append("pairing.v2_requires_frozen_measurement_contract")
            elif cell.get("outcome_period_end") != _mapping(measurement_cells.get(key)).get("outcome_period_end"):
                findings.append(f"pairing.holdout_binding.evaluated_cells[{index}].outcome_period_end_must_match_measurement_contract")
        if not binding_cells:
            findings.append("pairing.holdout_binding.evaluated_cells_must_be_nonempty")
    return _result(findings, pairing=deepcopy(item) if not findings else None)


def _baseline_score(cell: dict[str, Any], forecast_window: dict[str, Any], *, dimension_id: str, realized: Any) -> dict[str, float] | None:
    if "probabilities" in forecast_window:
        if not isinstance(realized, str):
            return None
        return _score(_probability_map(cell), _labels_for(dimension_id), realized)
    if not isinstance(realized, bool):
        return None
    return _binary_score(float(cell.get("event_occurs_probability", 0.0)), realized)


def validate_forecast_paired_evaluation(
    evaluation: Any, *, forecast: Any, settlement: Any, pairing: Any, measurement_contract: Any | None = None,
    observation_receipts: dict[str, Any] | None = None, acquisition_scope: Any | None = None,
) -> dict[str, Any]:
    """Score a frozen baseline and enhanced forecast cell-by-cell.

    It returns per-cell score deltas only.  It deliberately does not invent a
    synthetic overall winner, a causal attribution, or an investment signal.
    """
    findings: list[str] = []
    item = _closed(evaluation, _PAIRED_EVALUATION_KEYS, "paired_evaluation", findings)
    frozen = _mapping(forecast)
    pair = _mapping(pairing)
    settled = settle_company_state_forecast(
        frozen, settlement, measurement_contract=measurement_contract, observation_receipts=observation_receipts,
        acquisition_scope=acquisition_scope,
    )
    findings.extend(f"paired_evaluation.settlement:{finding}" for finding in settled["findings"])
    if item.get("schema_version") != PAIRED_EVALUATION_SCHEMA_VERSION:
        findings.append("paired_evaluation.schema_version_invalid")
    _require_text(item, "evaluation_id", "paired_evaluation", findings)
    for field, expected in (
        ("pairing_id", pair.get("pairing_id")),
        ("forecast_id", frozen.get("forecast_id")),
        ("settlement_id", _mapping(settlement).get("settlement_id")),
    ):
        if item.get(field) != expected:
            findings.append(f"paired_evaluation.{field}_must_match_frozen_input")
    evaluated_at = _instant(item.get("evaluated_at"), "paired_evaluation.evaluated_at", findings)
    settled_at = _instant(_mapping(settlement).get("settled_at"), "settlement.settled_at", findings)
    if evaluated_at and settled_at and evaluated_at < settled_at:
        findings.append("paired_evaluation.evaluated_at_must_follow_settlement")
    if item.get("object_class") != "FORECAST_PAIRED_EVALUATION":
        findings.append("paired_evaluation.object_class_invalid")
    if item.get("claim_class") != "PAIRED_METHOD_COMPARISON":
        findings.append("paired_evaluation.claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"]:
        findings.append("paired_evaluation.allowed_outputs_must_remain_evaluation_only")
    pair_validation = validate_forecast_pairing(
        pair, forecast=frozen, measurement_contract=measurement_contract,
    )
    findings.extend(f"paired_evaluation.pairing:{finding}" for finding in pair_validation["findings"])

    baseline_cells = {
        (str(cell.get("dimension_id")), str(cell.get("window_id"))): cell
        for cell in _items(pair.get("baseline_cells")) if isinstance(cell, dict)
    }
    forecast_cells = _forecast_cell_index(frozen)
    scored = {
        (str(result.get("dimension_id")), str(result.get("window_id"))): result
        for result in settled.get("dimension_scores", []) if isinstance(result, dict)
    }
    comparisons: list[dict[str, Any]] = []
    for raw in _items(_mapping(settlement).get("dimension_settlements")):
        entry = _mapping(raw)
        key = (str(entry.get("dimension_id")), str(entry.get("window_id")))
        if entry.get("status") != "OBSERVED" or key not in baseline_cells or key not in forecast_cells:
            continue
        enhanced = _mapping(scored.get(key)).get("score")
        baseline = _baseline_score(
            baseline_cells[key], forecast_cells[key], dimension_id=key[0], realized=entry.get("realized_label"),
        )
        if not isinstance(enhanced, dict) or baseline is None:
            findings.append(f"paired_evaluation.cell:{key[0]}:{key[1]}_not_scoreable")
            continue
        comparisons.append({
            "dimension_id": key[0], "window_id": key[1],
            "baseline_score": baseline, "enhanced_score": enhanced,
            "enhanced_minus_baseline_brier": float(enhanced["brier"]) - float(baseline["brier"]),
        })
    return _result(
        findings,
        paired_evaluation=deepcopy(item) if not findings else None,
        cell_comparisons=comparisons if not findings else [],
    )


def _validate_forecast_holdout(value: Any, *, forecast: dict[str, Any], findings: list[str]) -> None:
    holdout = _closed(value, _HOLDOUT_KEYS, "attribution.holdout", findings)
    result = validate_company_time_holdout(
        training_company_ids=_items(holdout.get("training_company_ids")),
        holdout_company_ids=_items(holdout.get("holdout_company_ids")),
        training_cutoff_through=str(holdout.get("training_cutoff_through") or ""),
        holdout_cutoff_from=str(holdout.get("holdout_cutoff_from") or ""),
    )
    findings.extend(f"attribution.holdout:{finding}" for finding in result["findings"])
    if forecast.get("company_id") not in _items(holdout.get("holdout_company_ids")):
        findings.append("attribution.holdout_must_include_evaluated_company")
    cutoff = _instant(forecast.get("cutoff_at"), "forecast.cutoff_at", findings)
    holdout_from = _instant(holdout.get("holdout_cutoff_from"), "attribution.holdout.holdout_cutoff_from", findings)
    if cutoff and holdout_from and cutoff < holdout_from:
        findings.append("attribution.holdout_must_cover_evaluated_cutoff")


def validate_forecast_error_attribution(
    attribution: Any, *, forecast: Any, settlement: Any, pairing: Any | None = None, paired_evaluation: Any | None = None,
    measurement_contract: Any | None = None, observation_receipts: dict[str, Any] | None = None,
    acquisition_scope: Any | None = None,
) -> dict[str, Any]:
    """Route forecast feedback into a narrow direct policy or a non-active candidate.

    Forecast error cannot establish an operating cause.  Therefore the direct
    route is limited to calibration, coverage, state definitions, uncertainty,
    and baseline measurement.  Evidence-priority and rival-hypothesis changes
    remain candidates until a paired, double-axis-held-out evaluation exists.
    """
    findings: list[str] = []
    item = _closed(
        attribution, _ATTRIBUTION_KEYS, "attribution", findings,
        required=_ATTRIBUTION_KEYS - {"paired_evaluation_id", "holdout", "policy_change"},
    )
    frozen = _mapping(forecast)
    raw_settlement = _mapping(settlement)
    settled = settle_company_state_forecast(
        frozen, raw_settlement, measurement_contract=measurement_contract, observation_receipts=observation_receipts,
        acquisition_scope=acquisition_scope,
    )
    findings.extend(f"attribution.settlement:{finding}" for finding in settled["findings"])
    if item.get("schema_version") != ATTRIBUTION_SCHEMA_VERSION:
        findings.append("attribution.schema_version_invalid")
    _require_text(item, "attribution_id", "attribution", findings)
    for field, expected in (("forecast_id", frozen.get("forecast_id")), ("settlement_id", raw_settlement.get("settlement_id"))):
        if item.get(field) != expected:
            findings.append(f"attribution.{field}_must_match_frozen_input")
    attributed_at = _instant(item.get("attributed_at"), "attribution.attributed_at", findings)
    settled_at = _instant(raw_settlement.get("settled_at"), "settlement.settled_at", findings)
    if attributed_at and settled_at and attributed_at < settled_at:
        findings.append("attribution.attributed_at_must_follow_settlement")
    _require_text(item, "reviewer_id", "attribution", findings)
    scope = item.get("learning_scope")
    if scope not in FORECAST_LEARNING_SCOPES:
        findings.append("attribution.learning_scope_invalid")
    locus = item.get("failure_locus")
    if locus not in FORECAST_FAILURE_LOCI:
        findings.append("attribution.failure_locus_invalid")
    if item.get("object_class") != "FORECAST_ERROR_ATTRIBUTION":
        findings.append("attribution.object_class_invalid")
    if item.get("claim_class") != "FORECAST_METHOD_FEEDBACK":
        findings.append("attribution.claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_POLICY_ONLY", "RESEARCH_AGENDA"]:
        findings.append("attribution.allowed_outputs_must_exclude_cjo_report_and_investment")

    refs = _cell_refs(item.get("cell_refs"), path="attribution.cell_refs", findings=findings)
    settlement_cells = {
        (str(entry.get("dimension_id")), str(entry.get("window_id"))): entry
        for entry in _items(raw_settlement.get("dimension_settlements")) if isinstance(entry, dict)
    }
    for key in refs:
        if key not in settlement_cells:
            findings.append(f"attribution.cell_ref_not_in_settlement:{key[0]}:{key[1]}")

    disposition = item.get("disposition")
    policy_change = item.get("policy_change")
    error_signatures: list[dict[str, Any]] = []
    if scope in DIRECT_FORECAST_LEARNING_SCOPES:
        if frozen.get("schema_version") not in MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
            findings.append("attribution.legacy_forecast_cannot_emit_direct_policy")
        if disposition != "DIRECT_FORECAST_POLICY":
            findings.append("attribution.direct_scope_requires_direct_policy_disposition")
        policy = _closed(policy_change, _POLICY_CHANGE_KEYS, "attribution.policy_change", findings)
        _require_text(policy, "change_id", "attribution.policy_change", findings)
        _require_text(policy, "statement", "attribution.policy_change", findings)
        effective_at = _instant(policy.get("effective_from_cutoff_at"), "attribution.policy_change.effective_from_cutoff_at", findings)
        if attributed_at and effective_at and effective_at <= attributed_at:
            findings.append("attribution.policy_change_must_apply_only_after_attribution")
        expected_locus = {
            "CALIBRATION": "CALIBRATION", "COVERAGE": "COVERAGE", "STATE_DEFINITION": "STATE_DEFINITION",
            "UNCERTAINTY_POLICY": "UNCERTAINTY", "BASELINE_PERFORMANCE": "BASELINE_PERFORMANCE",
        }[str(scope)]
        if locus != expected_locus:
            findings.append("attribution.direct_scope_must_match_failure_locus")
        expected_status = "MEASUREMENT_MISMATCH" if scope == "COVERAGE" else "OBSERVED"
        for key in refs:
            if _mapping(settlement_cells.get(key)).get("status") != expected_status:
                findings.append("attribution.direct_scope_cell_status_not_eligible")
        if scope == "BASELINE_PERFORMANCE":
            if pairing is None or paired_evaluation is None:
                findings.append("attribution.baseline_performance_requires_paired_evaluation")
            else:
                evaluation = validate_forecast_paired_evaluation(
                    paired_evaluation, forecast=frozen, settlement=raw_settlement, pairing=pairing,
                    measurement_contract=measurement_contract, observation_receipts=observation_receipts,
                    acquisition_scope=acquisition_scope,
                )
                findings.extend(f"attribution.paired_evaluation:{finding}" for finding in evaluation["findings"])
                if item.get("paired_evaluation_id") != _mapping(paired_evaluation).get("evaluation_id"):
                    findings.append("attribution.baseline_performance_must_bind_paired_evaluation")
        if not findings:
            error_signatures, signature_findings = _direct_error_signatures(
                str(scope), refs, forecast=frozen, settlement=raw_settlement, pairing=_mapping(pairing),
            )
            findings.extend(signature_findings)
        if item.get("holdout") is not None:
            findings.append("attribution.direct_scope_must_not_claim_holdout_method_transfer")
    elif scope in CANDIDATE_FORECAST_LEARNING_SCOPES:
        if disposition != "CANDIDATE_REQUIRES_PAIRED_HOLDOUT":
            findings.append("attribution.candidate_scope_must_remain_candidate_only")
        policy = _closed(policy_change, _POLICY_CHANGE_KEYS, "attribution.policy_change", findings)
        _require_text(policy, "change_id", "attribution.policy_change", findings)
        _require_text(policy, "statement", "attribution.policy_change", findings)
        _instant(policy.get("effective_from_cutoff_at"), "attribution.policy_change.effective_from_cutoff_at", findings)
        expected_locus = "EVIDENCE_PRIORITY" if scope == "EVIDENCE_PRIORITY" else "RIVAL_HYPOTHESIS_METHOD"
        if locus != expected_locus:
            findings.append("attribution.candidate_scope_must_match_failure_locus")
        if pairing is None or paired_evaluation is None:
            findings.append("attribution.candidate_scope_requires_paired_evaluation")
        else:
            pair = _mapping(pairing)
            evaluation = validate_forecast_paired_evaluation(
                paired_evaluation, forecast=frozen, settlement=raw_settlement, pairing=pair,
                measurement_contract=measurement_contract, observation_receipts=observation_receipts,
                acquisition_scope=acquisition_scope,
            )
            findings.extend(f"attribution.paired_evaluation:{finding}" for finding in evaluation["findings"])
            if item.get("paired_evaluation_id") != _mapping(paired_evaluation).get("evaluation_id"):
                findings.append("attribution.paired_evaluation_id_must_match_evaluation")
            comparison_by_cell = {
                (str(entry.get("dimension_id")), str(entry.get("window_id"))): entry
                for entry in evaluation.get("cell_comparisons", []) if isinstance(entry, dict)
            }
            for key in refs:
                comparison = _mapping(comparison_by_cell.get(key))
                if not comparison or float(comparison.get("enhanced_minus_baseline_brier", 0.0)) >= 0.0:
                    findings.append("attribution.candidate_scope_requires_strict_paired_brier_improvement")
            if pair.get("schema_version") != PAIRING_SCHEMA_VERSION_V3:
                findings.append("attribution.candidate_scope_requires_frozen_company_time_outcome_window_binding")
            elif frozen.get("schema_version") != FORECAST_SCHEMA_VERSION_V6:
                findings.append("attribution.candidate_scope_requires_forecast_method_identity_epoch")
            else:
                binding = _mapping(pair.get("holdout_binding"))
                bound_cells = {
                    (str(cell.get("dimension_id")), str(cell.get("window_id")))
                    for cell in _items(binding.get("evaluated_cells")) if isinstance(cell, dict)
                }
                if item.get("holdout") is not None:
                    findings.append("attribution.candidate_scope_cannot_use_caller_authored_holdout")
                for key in refs:
                    if key not in bound_cells:
                        findings.append("attribution.candidate_scope_cell_must_be_pre_registered_in_canonical_holdout_binding")
    elif scope == "NOT_DIAGNOSTIC":
        if disposition != "NOT_DIAGNOSTIC":
            findings.append("attribution.not_diagnostic_must_remain_not_diagnostic")
        if policy_change is not None or item.get("paired_evaluation_id") is not None or item.get("holdout") is not None:
            findings.append("attribution.not_diagnostic_cannot_emit_learning_change")
    learning_authorization = (
        "FORECAST_POLICY_DIRECT" if scope in DIRECT_FORECAST_LEARNING_SCOPES and not findings
        else "CANDIDATE_ONLY" if scope in CANDIDATE_FORECAST_LEARNING_SCOPES and not findings
        else "NONE"
    )
    return _result(
        findings,
        attribution=deepcopy(item) if not findings else None,
        learning_authorization=learning_authorization,
        error_signatures=error_signatures if not findings else [],
    )


def validate_prequential_feedback(settlements: list[dict[str, Any]], *, next_cutoff_at: str) -> dict[str, Any]:
    """Allow feedback only when every consumed result was public before next cutoff."""
    findings: list[str] = []
    next_cutoff = _instant(next_cutoff_at, "next_cutoff_at", findings)
    for settlement_index, settlement in enumerate(settlements):
        for entry_index, entry in enumerate(_items(_mapping(settlement).get("dimension_settlements"))):
            source = _mapping(_mapping(entry).get("outcome_source"))
            if _mapping(entry).get("status") != "OBSERVED":
                continue
            source_at, source_day = _outcome_source_availability(
                source, f"settlements[{settlement_index}].dimension_settlements[{entry_index}].outcome_source", findings,
            )
            if next_cutoff and not _source_precedes_receipt(source_at, source_day, next_cutoff):
                findings.append("prequential_feedback_cannot_consume_result_not_yet_public_at_next_cutoff")
    return _result(findings)


def validate_company_time_holdout(
    *, training_company_ids: list[str], holdout_company_ids: list[str], training_cutoff_through: str, holdout_cutoff_from: str,
) -> dict[str, Any]:
    """Require both company and time separation; random row splits are invalid."""
    findings: list[str] = []
    training = set(training_company_ids)
    holdout = set(holdout_company_ids)
    if not training or not holdout or any(not _text(value) for value in training | holdout):
        findings.append("holdout.company_axes_must_be_nonempty_text_sets")
    if training.intersection(holdout):
        findings.append("holdout.company_axis_must_not_overlap_training")
    training_through = _instant(training_cutoff_through, "training_cutoff_through", findings)
    holdout_from = _instant(holdout_cutoff_from, "holdout_cutoff_from", findings)
    if training_through and holdout_from and training_through >= holdout_from:
        findings.append("holdout.time_axis_must_follow_training")
    return _result(findings)


def validate_prospective_shadow_episode(
    shadow: Any,
    *,
    forecast: Any,
    now_at: str,
    measurement_contract: Any | None = None,
    preforecast_evidence_receipt: Any | None = None,
    acquisition_scope: Any | None = None,
) -> dict[str, Any]:
    """Register a still-unresolved forecast without making it a holdout result.

    V3 is the forward CompanyStateForecast lane.  It is deliberately stricter
    than the historical V1/V2 shadow: the custodian can see only a frozen
    Decision/Measurement/evidence chain, and outcome access stays closed until
    every predeclared resolution window is due.
    """
    findings: list[str] = []
    item = _closed(shadow, _FORECAST_SHADOW_KEYS, "shadow", findings, required=_SHADOW_KEYS)
    frozen = _mapping(forecast)
    if (item.get("schema_version"), item.get("forecast_epoch_id")) not in {
        (SHADOW_SCHEMA_VERSION, FORECAST_EPOCH_ID), (SHADOW_SCHEMA_VERSION_V2, FORECAST_EPOCH_ID_V2),
        (SHADOW_SCHEMA_VERSION_V3, FORECAST_EPOCH_ID_V3),
        (SHADOW_SCHEMA_VERSION_V3, FORECAST_EPOCH_ID_V4),
        (SHADOW_SCHEMA_VERSION_V3, FORECAST_EPOCH_ID_V5),
        (SHADOW_SCHEMA_VERSION_V3, FORECAST_EPOCH_ID_V6),
    }:
        findings.append("shadow.schema_version_invalid")
    if item.get("schema_version") in {SHADOW_SCHEMA_VERSION_V2, SHADOW_SCHEMA_VERSION_V3}:
        ref = _closed(item.get("decision_contract_ref"), _DECISION_CONTRACT_REF_KEYS, "shadow.decision_contract_ref", findings)
        _require_text(ref, "contract_id", "shadow.decision_contract_ref", findings)
        if not isinstance(ref.get("contract_version"), int) or isinstance(ref.get("contract_version"), bool) or ref.get("contract_version") < 1:
            findings.append("shadow.decision_contract_ref.contract_version_must_be_positive_integer")
        if ref != frozen.get("decision_contract_ref"):
            findings.append("shadow.decision_contract_ref_must_match_frozen_forecast")
    elif item.get("decision_contract_ref") is not None:
        findings.append("shadow.v1_cannot_retrofit_decision_contract")
    for field in ("company_id", "issuer_id", "cutoff_at", "forecast_id"):
        if item.get(field) != frozen.get(field):
            findings.append(f"shadow.{field}_must_match_frozen_forecast")
    _require_text(item, "shadow_episode_id", "shadow", findings)
    _require_text(item, "custodian_id", "shadow", findings)
    if item.get("status") != "WAITING_EXTERNAL_OUTCOME":
        findings.append("shadow.status_must_be_waiting_external_outcome")
    if item.get("object_class") != "PROSPECTIVE_SHADOW_EPISODE" or item.get("claim_class") != "PREQUENTIAL_EVALUATION":
        findings.append("shadow.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVALUATION_ONLY"]:
        findings.append("shadow.allowed_outputs_must_remain_evaluation_only")
    now = _instant(now_at, "now_at", findings)
    cutoff = _instant(item.get("cutoff_at"), "shadow.cutoff_at", findings)
    if now and cutoff and cutoff >= now:
        findings.append("shadow.cutoff_must_precede_registration_time")
    windows = _items(item.get("outcome_windows"))
    if windows != list(FORECAST_WINDOWS):
        findings.append("shadow.outcome_windows_must_match_frozen_forecast")
    if item.get("schema_version") != SHADOW_SCHEMA_VERSION_V3:
        for field in ("outcome_measurement_contract_ref", "preforecast_evidence_receipt_ref", "forecast_acquisition_scope_ref", "resolution_calendar"):
            if item.get(field) is not None:
                findings.append("shadow.v1_v2_cannot_retrofit_v3_contract_fields")
        return _result(findings, shadow=deepcopy(item) if not findings else None)

    measurement_ref = _closed(
        item.get("outcome_measurement_contract_ref"), _OUTCOME_MEASUREMENT_CONTRACT_REF_KEYS,
        "shadow.outcome_measurement_contract_ref", findings,
    )
    _require_text(measurement_ref, "measurement_contract_id", "shadow.outcome_measurement_contract_ref", findings)
    if not isinstance(measurement_ref.get("measurement_contract_version"), int) or isinstance(measurement_ref.get("measurement_contract_version"), bool) or measurement_ref.get("measurement_contract_version") < 1:
        findings.append("shadow.outcome_measurement_contract_ref.measurement_contract_version_must_be_positive_integer")
    if measurement_ref != frozen.get("outcome_measurement_contract_ref"):
        findings.append("shadow.outcome_measurement_contract_ref_must_match_frozen_forecast")
    measurement = _mapping(measurement_contract)
    if not measurement:
        findings.append("shadow.v3_requires_frozen_measurement_contract")
    elif measurement_ref != {
        "measurement_contract_id": measurement.get("measurement_contract_id"),
        "measurement_contract_version": measurement.get("measurement_contract_version"),
    }:
        findings.append("shadow.outcome_measurement_contract_ref_must_match_measurement_contract")
    if measurement and item.get("custodian_id") != measurement.get("custodian_id"):
        findings.append("shadow.custodian_must_match_measurement_contract")

    if frozen.get("schema_version") in {FORECAST_SCHEMA_VERSION_V4, FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        evidence_ref = _closed(
            item.get("preforecast_evidence_receipt_ref"), _PREFORCAST_EVIDENCE_RECEIPT_REF_KEYS,
            "shadow.preforecast_evidence_receipt_ref", findings,
        )
        _require_text(evidence_ref, "evidence_receipt_id", "shadow.preforecast_evidence_receipt_ref", findings)
        if not isinstance(evidence_ref.get("evidence_receipt_version"), int) or isinstance(evidence_ref.get("evidence_receipt_version"), bool) or evidence_ref.get("evidence_receipt_version") < 1:
            findings.append("shadow.preforecast_evidence_receipt_ref.evidence_receipt_version_must_be_positive_integer")
        if evidence_ref != frozen.get("preforecast_evidence_receipt_ref"):
            findings.append("shadow.preforecast_evidence_receipt_ref_must_match_frozen_forecast")
        receipt = _mapping(preforecast_evidence_receipt)
        if not receipt:
            findings.append("shadow.v4_v5_requires_frozen_preforecast_evidence_receipt")
        elif evidence_ref != {
            "evidence_receipt_id": receipt.get("evidence_receipt_id"),
            "evidence_receipt_version": receipt.get("evidence_receipt_version"),
        }:
            findings.append("shadow.preforecast_evidence_receipt_ref_must_match_evidence_receipt")
    elif item.get("preforecast_evidence_receipt_ref") is not None:
        findings.append("shadow.v3_cannot_claim_preforecast_evidence_receipt")

    if frozen.get("schema_version") in {FORECAST_SCHEMA_VERSION_V5, FORECAST_SCHEMA_VERSION_V6}:
        scope_ref = _closed(
            item.get("forecast_acquisition_scope_ref"), _FORECAST_ACQUISITION_SCOPE_REF_KEYS,
            "shadow.forecast_acquisition_scope_ref", findings,
        )
        _require_text(scope_ref, "scope_id", "shadow.forecast_acquisition_scope_ref", findings)
        if not isinstance(scope_ref.get("scope_version"), int) or isinstance(scope_ref.get("scope_version"), bool) or scope_ref.get("scope_version") < 1:
            findings.append("shadow.forecast_acquisition_scope_ref.scope_version_must_be_positive_integer")
        if scope_ref != frozen.get("forecast_acquisition_scope_ref"):
            findings.append("shadow.forecast_acquisition_scope_ref_must_match_frozen_forecast")
        scope = _mapping(acquisition_scope)
        if not scope:
            findings.append("shadow.v5_requires_frozen_acquisition_scope")
        elif scope_ref != {"scope_id": scope.get("scope_id"), "scope_version": scope.get("scope_version")}:
            findings.append("shadow.forecast_acquisition_scope_ref_must_match_acquisition_scope")
    elif item.get("forecast_acquisition_scope_ref") is not None:
        findings.append("shadow.v3_v4_cannot_claim_acquisition_scope")

    calendar = _items(item.get("resolution_calendar"))
    if len(calendar) != len(FORECAST_WINDOWS):
        findings.append("shadow.resolution_calendar_must_cover_all_forecast_windows")
    by_window: dict[str, datetime] = {}
    for index, raw in enumerate(calendar):
        resolution = _closed(raw, _SHADOW_RESOLUTION_KEYS, f"shadow.resolution_calendar[{index}]", findings)
        window_id = resolution.get("window_id")
        if window_id not in FORECAST_WINDOWS:
            findings.append(f"shadow.resolution_calendar[{index}].window_id_invalid")
            continue
        if window_id in by_window:
            findings.append(f"shadow.resolution_calendar[{index}].window_id_must_not_repeat")
            continue
        due = _instant(resolution.get("resolution_due_at"), f"shadow.resolution_calendar[{index}].resolution_due_at", findings)
        if due is not None:
            by_window[window_id] = due
            if now and due <= now:
                findings.append("shadow.resolution_calendar_must_remain_future_at_registration")
    if set(by_window) != set(FORECAST_WINDOWS):
        findings.append("shadow.resolution_calendar_window_set_must_match_forecast")
    if measurement:
        for cell in _items(measurement.get("cells")):
            cell_map = _mapping(cell)
            window_id = cell_map.get("window_id")
            due = by_window.get(window_id)
            period_end = _source_date(
                cell_map.get("outcome_period_end"),
                f"measurement_contract.cells[{window_id}].outcome_period_end", findings,
            )
            if due and period_end and due.date() <= period_end:
                findings.append("shadow.resolution_due_at_must_follow_measurement_contract_outcome_period_end")
    return _result(findings, shadow=deepcopy(item) if not findings else None)


def validate_prospective_signal_shadow_episode(shadow: Any, *, now_at: str) -> dict[str, Any]:
    """Register a current, frozen forward signal without turning it into a CJO.

    This form is deliberately separate from a CompanyStateForecast: a
    mechanism-signal probe may have a short, non-valuation resolution calendar,
    but remains a prequential evaluation object and cannot become causal or
    investment authority.
    """
    findings: list[str] = []
    item = _closed(shadow, _SIGNAL_SHADOW_KEYS, "signal_shadow", findings)
    if item.get("schema_version") != SHADOW_SCHEMA_VERSION:
        findings.append("signal_shadow.schema_version_invalid")
    _require_text(item, "shadow_episode_id", "signal_shadow", findings)
    _require_text(item, "company_id", "signal_shadow", findings)
    cutoff = _instant(item.get("cutoff_at"), "signal_shadow.cutoff_at", findings)
    _require_text(item, "custodian_id", "signal_shadow", findings)
    if item.get("status") != "WAITING_EXTERNAL_OUTCOME":
        findings.append("signal_shadow.status_must_be_waiting_external_outcome")
    if item.get("object_class") != "PROSPECTIVE_SHADOW_EPISODE" or item.get("claim_class") != "PREQUENTIAL_EVALUATION":
        findings.append("signal_shadow.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != ["FORECAST_EVALUATION_ONLY"]:
        findings.append("signal_shadow.allowed_outputs_must_remain_evaluation_only")
    freeze = _closed(item.get("source_freeze_ref"), _SIGNAL_SHADOW_FREEZE_KEYS, "signal_shadow.source_freeze_ref", findings)
    _require_text(freeze, "freeze_id", "signal_shadow.source_freeze_ref", findings)
    _require_text(freeze, "freeze_path", "signal_shadow.source_freeze_ref", findings)
    freeze_cutoff = _instant(freeze.get("cutoff_at"), "signal_shadow.source_freeze_ref.cutoff_at", findings)
    frozen_at = _instant(freeze.get("frozen_at"), "signal_shadow.source_freeze_ref.frozen_at", findings)
    allowed_sources = _items(freeze.get("allowed_source_ids"))
    if not allowed_sources or any(not _text(value) for value in allowed_sources) or len(set(allowed_sources)) != len(allowed_sources):
        findings.append("signal_shadow.source_freeze_ref.allowed_source_ids_invalid")
    if cutoff and freeze_cutoff and cutoff != freeze_cutoff:
        findings.append("signal_shadow.cutoff_must_match_source_freeze")
    if freeze_cutoff and frozen_at and frozen_at < freeze_cutoff:
        findings.append("signal_shadow.source_freeze_must_follow_cutoff")
    now = _instant(now_at, "now_at", findings)
    if now and frozen_at and frozen_at > now:
        findings.append("signal_shadow.source_freeze_cannot_be_in_future_at_registration")
    if now and cutoff and cutoff >= now:
        findings.append("signal_shadow.cutoff_must_precede_registration_time")
    windows = _items(item.get("outcome_windows"))
    if not windows:
        findings.append("signal_shadow.outcome_windows_required")
    due_times: list[datetime] = []
    seen_signals: set[str] = set()
    for index, raw in enumerate(windows):
        window = _closed(raw, _SIGNAL_SHADOW_WINDOW_KEYS, f"signal_shadow.outcome_windows[{index}]", findings)
        signal_id = _require_text(window, "signal_id", f"signal_shadow.outcome_windows[{index}]", findings)
        if signal_id in seen_signals:
            findings.append(f"signal_shadow.outcome_windows[{index}].signal_id_must_not_repeat")
        seen_signals.add(signal_id)
        _require_text(window, "metric", f"signal_shadow.outcome_windows[{index}]", findings)
        _require_text(window, "window_label", f"signal_shadow.outcome_windows[{index}]", findings)
        due = _instant(window.get("resolution_due_at"), f"signal_shadow.outcome_windows[{index}].resolution_due_at", findings)
        if due is not None:
            due_times.append(due)
    if now and due_times and min(due_times) <= now:
        findings.append("signal_shadow.must_have_unresolved_future_window_at_registration")
    return _result(findings, shadow=deepcopy(item) if not findings else None)


def validate_prospective_signal_source_freeze(source_freeze: Any, *, now_at: str) -> dict[str, Any]:
    """Validate the immutable source allowlist that precedes a signal shadow.

    It carries only cutoff-visible source identities and may never include a
    forecast, a realised observation, price, or a downstream judgement.
    """
    findings: list[str] = []
    freeze = _closed(source_freeze, _SIGNAL_SHADOW_FREEZE_KEYS, "signal_source_freeze", findings)
    _require_text(freeze, "freeze_id", "signal_source_freeze", findings)
    _require_text(freeze, "freeze_path", "signal_source_freeze", findings)
    cutoff = _instant(freeze.get("cutoff_at"), "signal_source_freeze.cutoff_at", findings)
    frozen_at = _instant(freeze.get("frozen_at"), "signal_source_freeze.frozen_at", findings)
    now = _instant(now_at, "now_at", findings)
    sources = _items(freeze.get("allowed_source_ids"))
    if not sources or any(not _text(source_id) for source_id in sources) or len(set(sources)) != len(sources):
        findings.append("signal_source_freeze.allowed_source_ids_invalid")
    if cutoff and frozen_at and frozen_at < cutoff:
        findings.append("signal_source_freeze.must_follow_cutoff")
    if now and frozen_at and frozen_at > now:
        findings.append("signal_source_freeze.cannot_be_in_future_at_registration")
    return _result(findings, source_freeze=deepcopy(freeze) if not findings else None)
