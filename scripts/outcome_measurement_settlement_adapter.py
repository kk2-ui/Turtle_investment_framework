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
from decimal import Decimal, InvalidOperation
import json
import sqlite3
from typing import Any

try:
    from scripts import judgment_pit_forecast as pit
    from scripts import judgment_pit_forecast_control_plane as control
    from scripts import enterprise_judgment_training_control_plane as enterprise_control
    from scripts import outcome_measurement_acquisition as acquisition
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_pit_forecast as pit
    import judgment_pit_forecast_control_plane as control
    import enterprise_judgment_training_control_plane as enterprise_control
    import outcome_measurement_acquisition as acquisition


class OutcomeMeasurementSettlementAdapterError(ValueError):
    """An acquisition result cannot legally enter the stored settlement lane."""


_ROUND5_ROUTE_KEYS = {
    "package_id",
    "control_receipt_id",
    "adapter_acceptance_receipt_id",
}


def _is_round5_package(contract: Any) -> bool:
    package_ref = contract.get("package_ref") if isinstance(contract, dict) else None
    return isinstance(package_ref, str) and package_ref.startswith("EMFP:")


def _validate_round5_route_binding(
    binding: Any, *, measurement_contract: dict[str, Any], required: bool,
) -> dict[str, Any] | None:
    if binding is None:
        if required:
            raise OutcomeMeasurementSettlementAdapterError(
                "enterprise_round5_canonical_entry_required"
            )
        return None
    if not isinstance(binding, dict) or set(binding) != _ROUND5_ROUTE_KEYS:
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_round5_route_binding_shape_invalid"
        )
    if any(not isinstance(value, str) or not value for value in binding.values()):
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_round5_route_binding_identity_required"
        )
    if binding["package_id"] != measurement_contract.get("package_ref"):
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_round5_route_package_mismatch"
        )
    if required:
        try:
            registered = enterprise_control.resolve_round5_route(binding["package_id"])
        except enterprise_control.TrainingControlPlaneError as exc:
            raise OutcomeMeasurementSettlementAdapterError(
                "enterprise_round5_canonical_route_unavailable:" + exc.code
            ) from exc
        expected = {**binding, "contract_set_id": measurement_contract.get("contract_set_id")}
        if registered != expected:
            raise OutcomeMeasurementSettlementAdapterError(
                "enterprise_round5_route_does_not_match_canonical_registration"
            )
    return deepcopy(binding)


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


def _finite_decimal(value: Any, *, code: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OutcomeMeasurementSettlementAdapterError(code)
    try:
        numeric = Decimal(str(value))
    except InvalidOperation as exc:  # pragma: no cover - guarded by acquisition validation
        raise OutcomeMeasurementSettlementAdapterError(code) from exc
    if not numeric.is_finite():
        raise OutcomeMeasurementSettlementAdapterError(code)
    return numeric


def execute_enterprise_formula(
    cell: dict[str, Any], raw_field_observations: list[dict[str, Any]],
) -> bool | float:
    """Execute only the five operators frozen by Enterprise Measurement V3."""
    by_id = {item["field_id"]: item for item in raw_field_observations}
    formula = cell["formula"]
    input_ids = formula["input_field_ids"]
    if set(by_id) != set(input_ids) or len(by_id) != len(input_ids):
        raise OutcomeMeasurementSettlementAdapterError("enterprise_formula_raw_input_coverage_invalid")
    conversions = formula["unit_conversions"]
    if [item.get("field_id") for item in conversions] != input_ids:
        raise OutcomeMeasurementSettlementAdapterError("enterprise_formula_unit_conversion_order_invalid")
    converted: list[Decimal | bool] = []
    for field_id, conversion in zip(input_ids, conversions, strict=True):
        observation = by_id[field_id]
        value = observation["raw_value"]
        if isinstance(value, bool):
            if conversion.get("from_unit") != observation.get("unit") or conversion.get("scale") != "1":
                raise OutcomeMeasurementSettlementAdapterError("enterprise_event_unit_conversion_invalid")
            converted.append(value)
            continue
        if conversion.get("from_unit") != observation.get("unit"):
            raise OutcomeMeasurementSettlementAdapterError("enterprise_formula_source_unit_mismatch")
        try:
            scale = Decimal(str(conversion.get("scale")))
        except InvalidOperation as exc:
            raise OutcomeMeasurementSettlementAdapterError("enterprise_formula_unit_scale_invalid") from exc
        if not scale.is_finite():
            raise OutcomeMeasurementSettlementAdapterError("enterprise_formula_unit_scale_invalid")
        converted.append(_finite_decimal(value, code="enterprise_formula_raw_value_invalid") * scale)

    operator = formula["operator"]
    if operator == "EVENT_BOOLEAN":
        if len(converted) != 1 or not isinstance(converted[0], bool):
            raise OutcomeMeasurementSettlementAdapterError("enterprise_event_formula_requires_one_boolean")
        return converted[0]
    if any(isinstance(value, bool) for value in converted):
        raise OutcomeMeasurementSettlementAdapterError("enterprise_numeric_formula_cannot_use_boolean")
    numeric = [value for value in converted if isinstance(value, Decimal)]
    if operator == "RAW_VALUE":
        if len(numeric) != 1:
            raise OutcomeMeasurementSettlementAdapterError("enterprise_raw_value_formula_requires_one_input")
        result = numeric[0]
    elif operator == "PERCENT_CHANGE":
        if len(numeric) != 2 or numeric[0] == 0:
            raise OutcomeMeasurementSettlementAdapterError("enterprise_percent_change_zero_or_invalid_baseline")
        result = (numeric[1] - numeric[0]) / abs(numeric[0])
    elif operator == "RATIO_CHANGE":
        if len(numeric) != 4 or numeric[1] == 0 or numeric[3] == 0:
            raise OutcomeMeasurementSettlementAdapterError("enterprise_ratio_change_zero_or_invalid_denominator")
        baseline_ratio = numeric[0] / numeric[1]
        if baseline_ratio == 0:
            raise OutcomeMeasurementSettlementAdapterError("enterprise_ratio_change_zero_baseline_ratio")
        result = ((numeric[2] / numeric[3]) - baseline_ratio) / abs(baseline_ratio)
    elif operator == "DIFFERENCE":
        if len(numeric) == 2:
            result = numeric[1] - numeric[0]
        elif len(numeric) == 4:
            if numeric[0] == 0 or numeric[2] == 0:
                raise OutcomeMeasurementSettlementAdapterError("enterprise_difference_zero_revenue_denominator")
            result = ((numeric[2] - numeric[3]) / numeric[2]) - ((numeric[0] - numeric[1]) / numeric[0])
        else:
            raise OutcomeMeasurementSettlementAdapterError("enterprise_difference_input_count_invalid")
    else:
        raise OutcomeMeasurementSettlementAdapterError("enterprise_formula_operator_unsupported")
    if not result.is_finite():
        raise OutcomeMeasurementSettlementAdapterError("enterprise_formula_result_not_finite")
    return float(result)


def _enterprise_label(cell: dict[str, Any], value: bool | float) -> str:
    rule = cell["label_rule"]
    if rule["type"] == "EVENT_PRESENCE":
        if not isinstance(value, bool):
            raise OutcomeMeasurementSettlementAdapterError("enterprise_event_label_requires_boolean")
        return "OBSERVED_YES" if value else "OBSERVED_NO"
    if isinstance(value, bool):
        raise OutcomeMeasurementSettlementAdapterError("enterprise_numeric_label_requires_number")
    if value <= float(rule["decrease_lte"]):
        return "OBSERVED_DECREASE"
    if value >= float(rule["increase_gte"]):
        return "OBSERVED_INCREASE"
    return "OBSERVED_STABLE"


def _settle_enterprise_acquisition_result(
    *,
    measurement_contract: dict[str, Any],
    outcome_access_authorization: dict[str, Any],
    acquisition_result: dict[str, Any],
    observed_at: str,
    settlement_id: str,
    settled_at: str,
    canonical_round5_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Settle Enterprise V3 raw fields without constructing Forecast objects."""
    route_binding = _validate_round5_route_binding(
        canonical_round5_binding,
        measurement_contract=measurement_contract,
        required=_is_round5_package(measurement_contract),
    )
    observed_timestamp = _instant(observed_at, field="observed_at")
    settled_timestamp = _instant(settled_at, field="settled_at")
    authorization_validation = acquisition.validate_enterprise_outcome_access_authorization(
        outcome_access_authorization, measurement_contract=measurement_contract,
    )
    if not authorization_validation["valid"]:
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_authorization_invalid: " + "; ".join(authorization_validation["findings"])
        )
    authorization = authorization_validation["authorization"]
    try:
        canonical_contract = enterprise_control.resolve_measurement_contract(
            measurement_contract["contract_set_id"],
        )
    except enterprise_control.TrainingControlPlaneError as exc:
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_canonical_measurement_contract_unavailable: " + exc.code,
        ) from exc
    if canonical_contract != measurement_contract:
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_measurement_contract_is_not_canonical_frozen_version",
        )
    if authorization.get("content_read") is not True:
        raise OutcomeMeasurementSettlementAdapterError("enterprise_settlement_requires_recorded_content_read")
    result_validation = acquisition.validate_acquisition_result(
        acquisition_result,
        measurement_contract=measurement_contract,
        outcome_access_authorization=authorization,
    )
    if not result_validation["valid"]:
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_acquisition_result_invalid: " + "; ".join(result_validation["findings"])
        )
    result = result_validation["result"]
    clock_validation = acquisition.validate_enterprise_settlement_clocks(
        result,
        measurement_contract=measurement_contract,
        observed_at=observed_at,
        settled_at=settled_at,
    )
    if not clock_validation["valid"]:
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_settlement_clock_invalid: " + "; ".join(clock_validation["findings"])
        )
    by_cell = {item["measurement_id"]: item for item in result["observations"]}
    cell_results: list[dict[str, Any]] = []
    raw_receipts: list[dict[str, Any]] = []
    for cell in measurement_contract["atomic_cells"]:
        observation = by_cell[cell["cell_id"]]
        status = observation["status"]
        label: str
        computed_value: bool | float | None = None
        if status == "OBSERVED":
            try:
                computed_value = execute_enterprise_formula(cell, observation["raw_field_observations"])
            except OutcomeMeasurementSettlementAdapterError as exc:
                status, label = "MEASUREMENT_MISMATCH", "MEASUREMENT_MISMATCH"
                formula_finding = str(exc)
            else:
                label = _enterprise_label(cell, computed_value)
                formula_finding = None
        elif status == "UNKNOWN":
            label, formula_finding = "UNKNOWN", None
        else:
            label, formula_finding = "MEASUREMENT_MISMATCH", None
        for raw in observation["raw_field_observations"]:
            raw_receipts.append({
                "schema_version": "enterprise-observation-receipt.v1",
                "receipt_id": f"OBS:ENTERPRISE:{settlement_id}:{cell['cell_id']}:{raw['field_id']}",
                "settlement_id": settlement_id,
                "measurement_contract_ref": deepcopy(result["measurement_contract_ref"]),
                "company_id": measurement_contract["company_id"],
                "cutoff_at": measurement_contract["cutoff_at"],
                "custodian_id": authorization["custodian_id"],
                "authorization_receipt_id": authorization["authorization_receipt_id"],
                "cell_id": cell["cell_id"],
                **deepcopy(raw),
            })
        cell_result = {
            "cell_id": cell["cell_id"],
            "status": status,
            "label": label,
            "computed_value": computed_value,
            "mismatch_propagation": "LOCAL_ONLY",
        }
        if formula_finding is not None:
            cell_result["formula_finding"] = formula_finding
        cell_results.append(cell_result)
    counts = {status: sum(row["status"] == status for row in cell_results) for status in acquisition.STATUSES}
    settlement = {
        "schema_version": "enterprise-outcome-measurement-settlement.v1",
        "settled": True,
        "settlement_id": settlement_id,
        "company_id": measurement_contract["company_id"],
        "cutoff_at": measurement_contract["cutoff_at"],
        "measurement_contract_ref": deepcopy(result["measurement_contract_ref"]),
        "authorization_receipt_id": authorization["authorization_receipt_id"],
        "custodian_id": authorization["custodian_id"],
        "observed_at": observed_timestamp,
        "settled_at": settled_timestamp,
        "cell_results": cell_results,
        "raw_observation_receipts": raw_receipts,
        "observation_receipt_ids": [receipt["receipt_id"] for receipt in raw_receipts],
        "coverage": {
            "frozen_cells": len(measurement_contract["atomic_cells"]),
            "settled_cells": len(cell_results),
            "observed_cells": counts["OBSERVED"],
            "unknown_cells": counts["UNKNOWN"],
            "measurement_mismatch_cells": counts["MEASUREMENT_MISMATCH"],
        },
        "rights": deepcopy(measurement_contract["rights"]),
        "allowed_outputs": ["ENTERPRISE_OUTCOME_SETTLEMENT_ONLY", "RESEARCH_AGENDA"],
    }
    if route_binding is not None:
        settlement["canonical_round5_binding"] = route_binding
    for receipt in raw_receipts:
        enterprise_control.register_enterprise_observation_receipt(
            receipt, registered_at=settled_timestamp,
        )
    persisted = enterprise_control.register_enterprise_settlement(
        settlement, registered_at=settled_timestamp,
    )
    settlement["persisted"] = True
    settlement["idempotent"] = persisted["idempotent"]
    return settlement


def settle_enterprise_acquisition_result(
    *,
    measurement_contract: dict[str, Any],
    outcome_access_authorization: dict[str, Any],
    acquisition_result: dict[str, Any],
    observed_at: str,
    settlement_id: str,
    settled_at: str,
) -> dict[str, Any]:
    """Settle a generic Enterprise V3 contract outside the Round 5 route.

    Round 5 contracts are package-bound and must enter through the canonical
    adapter, which supplies and records the complete route identity.
    """
    if _is_round5_package(measurement_contract):
        raise OutcomeMeasurementSettlementAdapterError(
            "enterprise_round5_requires_canonical_round5_entry"
        )
    return _settle_enterprise_acquisition_result(
        measurement_contract=measurement_contract,
        outcome_access_authorization=outcome_access_authorization,
        acquisition_result=acquisition_result,
        observed_at=observed_at,
        settlement_id=settlement_id,
        settled_at=settled_at,
    )


def register_acquisition_result(
    conn: sqlite3.Connection | None = None,
    *,
    outcome_access_authorization_id: str | None = None,
    acquisition_result: dict[str, Any],
    observed_at: str,
    settlement_id: str,
    settled_at: str,
    measurement_contract: dict[str, Any] | None = None,
    outcome_access_authorization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist acquired fields and settle them through the existing V3 engine.

    The connection supplies the already frozen Forecast, Measurement Contract,
    and custodian authorization.  Callers supply no forecast content and no
    realised label.  An acquisition result must account for every frozen cell;
    ``UNKNOWN`` simply becomes an unscored field, while a source-backed
    ``MEASUREMENT_MISMATCH`` receives the existing value-free observation
    receipt required by the settlement engine.
    """
    if measurement_contract is not None or outcome_access_authorization is not None:
        if conn is not None or outcome_access_authorization_id is not None:
            raise OutcomeMeasurementSettlementAdapterError(
                "enterprise_settlement_cannot_accept_forecast_registry_inputs"
            )
        if measurement_contract is None or outcome_access_authorization is None:
            raise OutcomeMeasurementSettlementAdapterError(
                "enterprise_settlement_requires_contract_and_authorization"
            )
        if measurement_contract.get("schema_version") == acquisition.ENTERPRISE_CONTRACT_SCHEMA_VERSION:
            raise OutcomeMeasurementSettlementAdapterError(
                "enterprise_settlement_requires_canonical_round5_identity_entry"
            )
        return settle_enterprise_acquisition_result(
            measurement_contract=measurement_contract,
            outcome_access_authorization=outcome_access_authorization,
            acquisition_result=acquisition_result,
            observed_at=observed_at,
            settlement_id=settlement_id,
            settled_at=settled_at,
        )
    if conn is None or outcome_access_authorization_id is None:
        raise OutcomeMeasurementSettlementAdapterError("forecast_settlement_requires_registry_and_authorization_id")
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
