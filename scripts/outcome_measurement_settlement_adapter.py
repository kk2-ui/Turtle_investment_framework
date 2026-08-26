#!/usr/bin/env python3
"""Narrow bridge from field acquisition to the existing forecast settlement engine.

The adapter owns no scoring rule.  It turns a closed
``outcome-measurement-acquisition.v1`` result into the existing immutable
outcome-observation receipts and then calls the existing mechanical Forecast
V3+ settlement path.  It never accepts or returns forecast probabilities,
investment conclusions, prices, CJO data, or report content.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

try:
    from scripts import judgment_pit_forecast as pit
    from scripts import judgment_pit_forecast_control_plane as control
    from scripts import outcome_measurement_acquisition as acquisition
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_pit_forecast as pit
    import judgment_pit_forecast_control_plane as control
    import outcome_measurement_acquisition as acquisition


class OutcomeMeasurementSettlementAdapterError(ValueError):
    """An acquisition result cannot legally enter the stored settlement lane."""


def _load(payload_json: str, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(payload_json)
    except json.JSONDecodeError as exc:  # pragma: no cover - control-plane invariant
        raise OutcomeMeasurementSettlementAdapterError(code) from exc
    if not isinstance(value, dict):  # pragma: no cover - control-plane invariant
        raise OutcomeMeasurementSettlementAdapterError(code)
    return value


def _instant(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise OutcomeMeasurementSettlementAdapterError(field + "_must_be_timezone_aware")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeMeasurementSettlementAdapterError(field + "_must_be_timezone_aware") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OutcomeMeasurementSettlementAdapterError(field + "_must_be_timezone_aware")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _row(conn: sqlite3.Connection, table: str, key: str, value: str, *, code: str) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {table} WHERE {key} = ?", (value,)).fetchone()
    if row is None:
        raise OutcomeMeasurementSettlementAdapterError(code)
    return row


def _reference(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "measurement_contract_id": contract["measurement_contract_id"],
        "measurement_contract_version": contract["measurement_contract_version"],
    }


def _source_from_acquisition(
    observation: dict[str, Any], *, cell: dict[str, Any], issuer_id: str,
) -> dict[str, Any]:
    source = observation.get("source")
    if not isinstance(source, dict):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_observed_field_missing_source_identity")
    for field, expected in (
        ("issuer_id", issuer_id),
        ("responsibility_boundary", cell["responsibility_boundary"]),
        ("report_period_end", cell["outcome_period_end"]),
    ):
        if field not in source or (expected is not None and source[field] != expected):
            raise OutcomeMeasurementSettlementAdapterError("acquisition_source_" + field + "_does_not_match_measurement_contract")
    if not isinstance(source.get("source_id"), str) or not source["source_id"]:
        raise OutcomeMeasurementSettlementAdapterError("acquisition_source_id_required")
    if not isinstance(source.get("source_url"), str) or not source["source_url"].startswith("https://"):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_source_url_must_be_official_https")
    if not isinstance(source.get("field_ref"), str) or not source["field_ref"].startswith("PDF p."):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_source_field_ref_must_be_paged")
    availability_precision = source.get("availability_precision")
    outcome_source: dict[str, Any] = {
        "source_id": source["source_id"],
        "source_url": source["source_url"],
        "field_ref": source["field_ref"],
        "source_field_id": cell["source_field_id"],
        "official_source_type": cell["official_source_type"],
        "issuer_id": source["issuer_id"],
        "responsibility_boundary": cell["responsibility_boundary"],
        "unit": cell["unit"],
        "outcome_period_end": cell["outcome_period_end"],
    }
    if availability_precision == "TIMESTAMP" and isinstance(source.get("source_available_at"), str):
        outcome_source["source_available_precision"] = "TIMESTAMP"
        outcome_source["source_available_at"] = source["source_available_at"]
    elif availability_precision == "DATE_ONLY" and isinstance(source.get("source_available_date"), str):
        outcome_source["source_available_precision"] = "DATE_ONLY"
        outcome_source["source_available_date"] = source["source_available_date"]
    else:
        raise OutcomeMeasurementSettlementAdapterError("acquisition_source_availability_identity_missing")
    return outcome_source


def _direct_numeric_value(observation: dict[str, Any], *, cell: dict[str, Any]) -> float:
    formula = cell.get("measurement_formula")
    if cell.get("measurement_kind") != "ORDINAL_THRESHOLD" or not isinstance(formula, dict):
        raise OutcomeMeasurementSettlementAdapterError("adapter_supports_direct_numeric_ordinal_fields_only")
    if formula.get("formula_kind") != "DIRECT_NUMERIC" or formula.get("value_field_id") != cell.get("source_field_id"):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_field_does_not_match_frozen_direct_numeric_formula")
    value = observation.get("current_value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_observed_value_must_be_finite_numeric")
    numeric = float(value)
    if numeric != numeric or numeric in {float("inf"), float("-inf")}:
        raise OutcomeMeasurementSettlementAdapterError("acquisition_observed_value_must_be_finite_numeric")
    return numeric


def _label_for(value: float, *, cell: dict[str, Any]) -> str:
    labels = cell["label_order"]
    if value < float(cell["lower_threshold"]):
        return labels[0]
    if value > float(cell["upper_threshold"]):
        return labels[2]
    return labels[1]


def _mismatch_rule(observation: dict[str, Any], *, cell: dict[str, Any]) -> str:
    reason = observation.get("reason")
    if not isinstance(reason, str) or reason not in cell["mismatch_rules"]:
        raise OutcomeMeasurementSettlementAdapterError(
            "acquisition_mismatch_reason_must_be_frozen_measurement_contract_rule"
        )
    return reason


def register_acquisition_result(
    conn: sqlite3.Connection,
    *,
    outcome_access_authorization_id: str,
    acquisition_result: dict[str, Any],
    observed_at: str,
    settlement_id: str,
    settled_at: str,
) -> dict[str, Any]:
    """Persist acquired fields and settle them through the existing V3 engine.

    The connection supplies the already frozen Forecast, Measurement Contract,
    and custodian authorization.  Callers supply no forecast content and no
    realised label.  An acquisition result must account for every frozen cell;
    ``UNKNOWN`` simply becomes an unscored field, while a source-backed
    ``MEASUREMENT_MISMATCH`` receives the existing value-free observation
    receipt required by the settlement engine.
    """
    observed_timestamp = _instant(observed_at, field="observed_at")
    settled_timestamp = _instant(settled_at, field="settled_at")
    access_row = _row(
        conn, control.OUTCOME_ACCESS_TABLE, "authorization_id", outcome_access_authorization_id,
        code="outcome_access_authorization_not_found",
    )
    access = _load(access_row["payload_json"], code="stored_outcome_access_invalid")
    forecast_row = _row(conn, control.FORECAST_TABLE, "forecast_id", str(access.get("forecast_id") or ""), code="authorized_forecast_not_found")
    forecast = _load(forecast_row["payload_json"], code="stored_forecast_invalid")
    if forecast.get("schema_version") not in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        raise OutcomeMeasurementSettlementAdapterError("adapter_requires_measurement_contract_forecast")
    contract_ref = forecast.get("outcome_measurement_contract_ref")
    if not isinstance(contract_ref, dict):  # pragma: no cover - forecast invariant
        raise OutcomeMeasurementSettlementAdapterError("authorized_forecast_measurement_contract_ref_missing")
    contract_row = _row(
        conn, control.OUTCOME_MEASUREMENT_CONTRACT_TABLE, "measurement_contract_id",
        str(contract_ref.get("measurement_contract_id") or ""), code="measurement_contract_not_found",
    )
    contract = _load(contract_row["payload_json"], code="stored_measurement_contract_invalid")
    if contract_ref != _reference(contract):
        raise OutcomeMeasurementSettlementAdapterError("authorized_forecast_measurement_contract_version_mismatch")
    # Resolve persisted authorization before even validating caller-supplied
    # acquisition content: the result may carry realised values.
    result_validation = acquisition.validate_acquisition_result(acquisition_result)
    if not result_validation["valid"]:
        raise OutcomeMeasurementSettlementAdapterError(
            "acquisition_result_invalid: " + "; ".join(result_validation["findings"])
        )
    if acquisition_result.get("measurement_contract_ref") != _reference(contract):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_measurement_contract_ref_mismatch")
    if acquisition_result.get("custodian_id") != access.get("custodian_id"):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_custodian_must_match_authorized_outcome_access")
    if access.get("outcome_measurement_contract_ref") != _reference(contract):
        raise OutcomeMeasurementSettlementAdapterError("authorized_outcome_access_measurement_contract_mismatch")

    cells = {
        cell["measurement_id"]: cell
        for cell in contract["cells"]
    }
    acquired = {item.get("measurement_id"): item for item in acquisition_result["observations"]}
    if set(acquired) != set(cells) or len(acquired) != len(acquisition_result["observations"]):
        raise OutcomeMeasurementSettlementAdapterError("acquisition_result_must_account_for_each_frozen_measurement_once")

    forecasts = {
        dimension["dimension_id"]: dimension
        for dimension in forecast["dimensions"]
    }
    receipts: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    field_statuses: list[dict[str, str]] = []
    for cell in contract["cells"]:
        acquired_field = acquired[cell["measurement_id"]]
        expected_identity = {
            "metric_id": cell["source_field_id"],
            "metric_definition": cell["metric_definition"],
            "report_period_end": cell["outcome_period_end"],
            "unit": cell["unit"],
        }
        if any(acquired_field.get(field) != expected for field, expected in expected_identity.items()):
            raise OutcomeMeasurementSettlementAdapterError("acquisition_field_identity_does_not_match_measurement_contract")
        dimension_id, window_id = cell["dimension_id"], cell["window_id"]
        status = acquired_field["status"]
        forecast_dimension = forecasts[dimension_id]
        if forecast_dimension["evidence_status"] == "EVIDENCE_INELIGIBLE":
            if status != "UNKNOWN":
                raise OutcomeMeasurementSettlementAdapterError("acquisition_cannot_observe_frozen_evidence_ineligible_field")
            entries.append({"dimension_id": dimension_id, "window_id": window_id, "status": "EVIDENCE_INELIGIBLE", "realized_label": None})
            field_statuses.append({"measurement_id": cell["measurement_id"], "status": "EVIDENCE_INELIGIBLE"})
            continue
        if status == "UNKNOWN":
            entries.append({"dimension_id": dimension_id, "window_id": window_id, "status": "UNKNOWN", "realized_label": None})
            field_statuses.append({"measurement_id": cell["measurement_id"], "status": "UNKNOWN"})
            continue
        source = _source_from_acquisition(acquired_field, cell=cell, issuer_id=forecast["issuer_id"])
        observation_id = f"OBS:ACQUISITION:{settlement_id}:{cell['measurement_id']}"
        receipt: dict[str, Any] = {
            "schema_version": pit.OUTCOME_OBSERVATION_RECEIPT_SCHEMA_VERSION,
            "observation_id": observation_id,
            "forecast_id": forecast["forecast_id"],
            "outcome_measurement_contract_ref": _reference(contract),
            "company_id": forecast["company_id"],
            "issuer_id": forecast["issuer_id"],
            "cutoff_at": forecast["cutoff_at"],
            "custodian_id": access["custodian_id"],
            "observed_at": observed_timestamp,
            "dimension_id": dimension_id,
            "window_id": window_id,
            "outcome_source": source,
            "object_class": "FORECAST_OUTCOME_OBSERVATION_RECEIPT",
            "claim_class": "CUSTODIAN_EXTRACTED_OUTCOME_FIELD",
            "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
        }
        if status == "OBSERVED":
            value = _direct_numeric_value(acquired_field, cell=cell)
            receipt.update({
                "observation_status": "OBSERVED_MEASUREMENT",
                "realized_measurement": {
                    "measurement_id": cell["measurement_id"],
                    "measurement_kind": cell["measurement_kind"],
                    "unit": cell["unit"],
                    "outcome_period_end": cell["outcome_period_end"],
                    "responsibility_boundary": cell["responsibility_boundary"],
                    "numeric_value": value,
                    "source_components": [{
                        field: source[field]
                        for field in (
                            "source_id", "source_url", "field_ref", "official_source_type", "issuer_id",
                            "responsibility_boundary", "unit", "outcome_period_end",
                            "source_available_at", "source_available_date", "source_available_precision",
                        )
                        if field in source
                    } | {
                        "field_id": cell["source_field_id"],
                        "numeric_value": value,
                    }],
                },
            })
            entries.append({
                "dimension_id": dimension_id, "window_id": window_id, "status": "OBSERVED",
                "realized_label": _label_for(value, cell=cell), "outcome_observation_ref": {"observation_id": observation_id},
            })
        elif status == "MEASUREMENT_MISMATCH":
            receipt.update({
                "observation_status": "MEASUREMENT_MISMATCH",
                "mismatch_rule": _mismatch_rule(acquired_field, cell=cell),
                "mismatch_detail": acquired_field["reason"],
            })
            entries.append({
                "dimension_id": dimension_id, "window_id": window_id, "status": "MEASUREMENT_MISMATCH",
                "realized_label": None, "outcome_observation_ref": {"observation_id": observation_id},
            })
        else:  # result validator constrains this branch
            raise OutcomeMeasurementSettlementAdapterError("acquisition_field_status_invalid")
        receipts.append(receipt)
        field_statuses.append({"measurement_id": cell["measurement_id"], "status": status})

    settlement = {
        "schema_version": pit.SETTLEMENT_SCHEMA_VERSION_V2,
        "settlement_id": settlement_id,
        "forecast_id": forecast["forecast_id"],
        "company_id": forecast["company_id"],
        "cutoff_at": forecast["cutoff_at"],
        "settled_at": settled_timestamp,
        "custodian_id": access["custodian_id"],
        "outcome_access_authorized": True,
        "outcome_measurement_contract_ref": _reference(contract),
        "dimension_settlements": entries,
        "object_class": "FORECAST_SETTLEMENT",
        "claim_class": "PREQUENTIAL_FEEDBACK",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }
    receipt_index = {receipt["observation_id"]: receipt for receipt in receipts}
    validation = pit.settle_company_state_forecast(
        forecast, settlement, measurement_contract=contract, observation_receipts=receipt_index,
    )
    if not validation["valid"]:
        raise OutcomeMeasurementSettlementAdapterError("compiled_settlement_invalid: " + "; ".join(validation["findings"]))
    for receipt in receipts:
        control.register_forecast_outcome_observation_receipt(conn, receipt)
    settled = control.register_forecast_settlement(conn, settlement)
    return {
        "settled": settled["settled"],
        "settlement_id": settled["settlement_id"],
        "idempotent": settled["idempotent"],
        "field_statuses": field_statuses,
        "coverage": deepcopy(settled["coverage"]),
    }
