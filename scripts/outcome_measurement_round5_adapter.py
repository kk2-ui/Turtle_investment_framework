#!/usr/bin/env python3
"""Round 5 value-free custody projection over the shared outcome adapters.

The projection is the only object an independent custodian receives before
outcome access.  It contains atomic measurement contracts and the authorized
static-source identity, but no J2 hypothesis, J3 forecast direction/value, or
enterprise judgment.  Submission validation delegates to the reusable v1
acquisition module; future settlement delegates to its public v1 adapter.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

try:
    from scripts import enterprise_judgment_real_mechanism_training as training
    from scripts import enterprise_judgment_training_control_plane as enterprise_control
    from scripts import outcome_measurement_acquisition as acquisition
    from scripts import outcome_measurement_settlement_adapter as settlement_adapter
except ModuleNotFoundError:  # pragma: no cover
    import enterprise_judgment_real_mechanism_training as training
    import enterprise_judgment_training_control_plane as enterprise_control
    import outcome_measurement_acquisition as acquisition
    import outcome_measurement_settlement_adapter as settlement_adapter


SCHEMA_VERSION = "outcome-measurement-value-free-custody-projection.v1"
OBJECT_CLASS = "VALUE_FREE_OUTCOME_CUSTODY_PROJECTION"
CLAIM_CLASS = "CUSTODIAN_ATOMIC_MEASUREMENT_ONLY"
FORBIDDEN_KEYS = {
    "hypotheses", "forecast", "forecast_direction", "forecast_value", "probabilities",
    "j2", "j3", "management_decision_ledger", "cjo", "price", "valuation", "report",
}


class Round5CustodyAdapterError(ValueError):
    """A custody projection or submission violates the value-free boundary."""


ROUND5_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
)
ROUND5_ACTIVE_ARTIFACTS = {
    "package": "29_round5_v3_preoutcome_mechanism_package.json",
    "projection": "30_round5_v3_value_free_custody_projection.json",
    "control": "31_round5_v3_preoutcome_control_plane_receipt.json",
    "adapter": "32_round5_v3_adapter_acceptance_receipt.json",
}
ROUND5_ACTIVE_ARTIFACT_REFS = {
    "package": ROUND5_ACTIVE_ARTIFACTS["package"],
    "value_free_custody_projection": ROUND5_ACTIVE_ARTIFACTS["projection"],
    "preoutcome_control_receipt": ROUND5_ACTIVE_ARTIFACTS["control"],
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _forbidden(value: Any, *, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_KEYS:
                findings.append(f"{path}.{key}" if path else str(key))
            findings.extend(_forbidden(child, path=f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_forbidden(child, path=f"{path}[{index}]"))
    return findings


def _flow_clock(year: int) -> dict[str, Any]:
    return {
        "clock_kind": "FLOW_PERIOD",
        "flow_period": {
            "period_start": f"{year}-01-01",
            "period_end": f"{year}-12-31",
            "fiscal_period": f"FY{year}",
        },
    }


def _balance_clock(year: int) -> dict[str, Any]:
    return {
        "clock_kind": "BALANCE_AS_OF",
        "balance_as_of": {"as_of": f"{year}-12-31", "fiscal_period": f"FY{year}"},
    }


def _event_clock() -> dict[str, Any]:
    return {
        "clock_kind": "EVENT_WINDOW",
        "event_window": {
            "event_start": "2015-04-16",
            "event_end": "2015-12-31",
            "window_name": "POST_CUTOFF_FY2015_EVENT_WINDOW",
        },
    }


def _raw_locator(cell: dict[str, Any], clock: dict[str, Any]) -> dict[str, str]:
    field = cell["field_identity"]
    if clock["clock_kind"] == "EVENT_WINDOW":
        event = clock["event_window"]
        period_column = f"{event['event_start']}..{event['event_end']}"
    else:
        period = clock.get("flow_period") or clock.get("balance_as_of")
        period_column = period.get("fiscal_period") or period.get("as_of")
    return {
        "table_or_note": field["table_or_note"],
        "line_item": field["line_item"],
        "period_column": period_column,
    }


def _input(field_id: str, *, role: str, unit: str, clock: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "role": role,
        "unit": unit,
        "measurement_clock": deepcopy(clock),
        "locator": _raw_locator(cell, clock),
    }


def _conversion(field_id: str, unit: str) -> dict[str, str]:
    return {"field_id": field_id, "from_unit": unit, "to_unit": unit, "scale": "1"}


def _raw_contract(cell: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Bind one Round 5 cell to explicit raw fields and a complete formula."""
    cell_id = cell["cell_id"]
    field = cell["field_identity"]
    outcome_id = field["outcome_field_id"]
    baseline_id = field["baseline_field_id"]
    event = cell["label_rule"]["type"] == "EVENT_PRESENCE"
    balance = cell["layer"] in {"WORKING_CAPITAL", "FINANCING"}
    outcome_clock = _event_clock() if event else (_balance_clock(2015) if balance else _flow_clock(2015))
    baseline_clock = _balance_clock(2014) if balance else _flow_clock(2014)
    unit = cell["unit"]["scale"] if cell["unit"]["currency"] == "NOT_APPLICABLE" else cell["unit"]["currency"]

    if event:
        raw = [_input(outcome_id, role="EVENT", unit="BOOLEAN_EVENT", clock=outcome_clock, cell=cell)]
        formula = {
            "operator": "EVENT_BOOLEAN",
            "input_field_ids": [outcome_id],
            "expression": f"event := explicit_disclosure({outcome_id}) within 2015-04-16..2015-12-31",
            "unit_conversions": [_conversion(outcome_id, "BOOLEAN_EVENT")],
            "zero_baseline_rule": "NOT_APPLICABLE",
        }
        return outcome_clock, raw, formula

    derived: dict[str, tuple[list[tuple[str, str, int]], str, str]] = {
        "CELL:600802:20150415:CEMENT_REALIZED_PRICE": (
            [
                ("FIELD:600802:FY2014:CEMENT_REVENUE_RMB", "RMB", 2014),
                ("FIELD:600802:FY2014:CEMENT_SALES_VOLUME_TONNES", "TONNE", 2014),
                ("FIELD:600802:FY2015:CEMENT_REVENUE_RMB", "RMB", 2015),
                ("FIELD:600802:FY2015:CEMENT_SALES_VOLUME_TONNES", "TONNE", 2015),
            ],
            "RATIO_CHANGE",
            "((FY2015_CEMENT_REVENUE_RMB / FY2015_CEMENT_SALES_VOLUME_TONNES) - (FY2014_CEMENT_REVENUE_RMB / FY2014_CEMENT_SALES_VOLUME_TONNES)) / abs(FY2014_CEMENT_REVENUE_RMB / FY2014_CEMENT_SALES_VOLUME_TONNES)",
        ),
        "CELL:600802:20150415:CEMENT_UNIT_COST": (
            [
                ("FIELD:600802:FY2014:CEMENT_OPERATING_COST_RMB", "RMB", 2014),
                ("FIELD:600802:FY2014:CEMENT_SALES_VOLUME_TONNES", "TONNE", 2014),
                ("FIELD:600802:FY2015:CEMENT_OPERATING_COST_RMB", "RMB", 2015),
                ("FIELD:600802:FY2015:CEMENT_SALES_VOLUME_TONNES", "TONNE", 2015),
            ],
            "RATIO_CHANGE",
            "((FY2015_CEMENT_OPERATING_COST_RMB / FY2015_CEMENT_SALES_VOLUME_TONNES) - (FY2014_CEMENT_OPERATING_COST_RMB / FY2014_CEMENT_SALES_VOLUME_TONNES)) / abs(FY2014_CEMENT_OPERATING_COST_RMB / FY2014_CEMENT_SALES_VOLUME_TONNES)",
        ),
        "CELL:600802:20150415:CEMENT_GROSS_MARGIN": (
            [
                ("FIELD:600802:FY2014:CEMENT_REVENUE_RMB", "RMB", 2014),
                ("FIELD:600802:FY2014:CEMENT_OPERATING_COST_RMB", "RMB", 2014),
                ("FIELD:600802:FY2015:CEMENT_REVENUE_RMB", "RMB", 2015),
                ("FIELD:600802:FY2015:CEMENT_OPERATING_COST_RMB", "RMB", 2015),
            ],
            "DIFFERENCE",
            "((FY2015_CEMENT_REVENUE_RMB - FY2015_CEMENT_OPERATING_COST_RMB) / FY2015_CEMENT_REVENUE_RMB) - ((FY2014_CEMENT_REVENUE_RMB - FY2014_CEMENT_OPERATING_COST_RMB) / FY2014_CEMENT_REVENUE_RMB)",
        ),
    }
    if cell_id in derived:
        specifications, operator, expression = derived[cell_id]
        raw = [
            _input(
                field_id, role="BASELINE" if year == 2014 else "OUTCOME", unit=raw_unit,
                clock=_flow_clock(year), cell=cell,
            )
            for field_id, raw_unit, year in specifications
        ]
        formula = {
            "operator": operator,
            "input_field_ids": [entry["field_id"] for entry in raw],
            "expression": expression,
            "unit_conversions": [_conversion(entry["field_id"], entry["unit"]) for entry in raw],
            "zero_baseline_rule": "RETURN_MEASUREMENT_MISMATCH",
        }
        return outcome_clock, raw, formula

    raw = [
        _input(baseline_id, role="BASELINE", unit=unit, clock=baseline_clock, cell=cell),
        _input(outcome_id, role="OUTCOME", unit=unit, clock=outcome_clock, cell=cell),
    ]
    formula = {
        "operator": "PERCENT_CHANGE",
        "input_field_ids": [baseline_id, outcome_id],
        "expression": f"({outcome_id} - {baseline_id}) / abs({baseline_id})",
        "unit_conversions": [_conversion(entry["field_id"], entry["unit"]) for entry in raw],
        "zero_baseline_rule": "RETURN_MEASUREMENT_MISMATCH",
    }
    return outcome_clock, raw, formula


def build_round5_v3_package(v2_package: Any, *, frozen_at: str) -> dict[str, Any]:
    """Non-destructively supersede the v2 package before any outcome read."""
    source = _mapping(v2_package)
    if source.get("schema_version") != training.PACKAGE_SCHEMA_VERSION:
        raise Round5CustodyAdapterError("round5_v2_package_required")
    if _mapping(source.get("sealed_outcome_source")).get("outcome_content_read") is not False:
        raise Round5CustodyAdapterError("round5_outcome_must_remain_unread")
    package = deepcopy(source)
    package["schema_version"] = training.PACKAGE_SCHEMA_VERSION_V3
    package["package_id"] = "EMFP:CN:CEMENT:600802:20150415:V3"
    contract = package["outcome_measurement_contract"]
    contract.update({
        "schema_version": training.CONTRACT_SCHEMA_VERSION_V3,
        "contract_set_id": "OMC:CN600802:20150415:MECHANISM:V3",
        "package_ref": package["package_id"],
        "freeze_state": "PRE_OUTCOME_FROZEN",
        "contract_frozen_at": frozen_at,
        "clock_policy": "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK",
    })
    contract["outcome_window"] = {
        "period_start": "2015-01-01T00:00:00+08:00",
        "period_end": "2015-12-31T23:59:59+08:00",
        "fiscal_period": "FY2015",
        "settlement_due_at": "2016-04-27T00:00:00+08:00",
    }
    contract["source_access"]["authorization_receipt_id"] = "CUSTODY-AUTH:CN600802:20150415:FY2015:V3"
    contract["source_access"]["access_state"] = "SEALED_UNTIL_PREOUTCOME_COMMIT"
    contract["source_access"].update({
        "issuer_id": "ISSUER:CN:600802",
        "report_period_end": "2015-12-31",
        "availability_precision": "DATE_ONLY",
        "source_available_at": None,
        "source_available_date": "2016-04-26",
    })
    for cell in contract["atomic_cells"]:
        clock, raw_inputs, formula = _raw_contract(cell)
        cell["outcome_period"] = {
            "period_start": "2015-01-01T00:00:00+08:00",
            "period_end": "2015-12-31T23:59:59+08:00",
            "fiscal_period": "FY2015",
        }
        cell["measurement_clock"] = clock
        cell["raw_input_fields"] = raw_inputs
        cell["formula"] = formula
    contract_validation = training.validate_outcome_measurement_contract(contract)
    if not contract_validation["valid"]:
        raise Round5CustodyAdapterError("round5_v3_contract_invalid: " + "; ".join(contract_validation["findings"]))
    for outcome_cell in package["episode_manifest"]["outcome_cells"]:
        outcome_cell["measurement_contract_ref"] = "MC:" + outcome_cell["outcome_cell_id"].removeprefix("CELL:") + ":V3"
    for thread in package["forecast_projection_source"]["threads"]:
        for forecast_cell in thread["cells"]:
            reference = forecast_cell["measurement_ref"]
            reference["measurement_contract_id"] = reference["measurement_contract_id"].removesuffix(":V2") + ":V3"
            reference["measurement_contract_version"] = 3
            if isinstance(reference.get("measurement_id"), str):
                reference["measurement_id"] = reference["measurement_id"].removesuffix(":V2") + ":V3"
    package["sealed_outcome_source"]["access_state"] = "SEALED_UNTIL_PREOUTCOME_COMMIT"
    package["sealed_outcome_source"]["outcome_content_read"] = False
    return package


def build_value_free_custody_projection(package: Any) -> dict[str, Any]:
    """Project only the frozen contract and source authorization to custody."""
    item = _mapping(package)
    contract = _mapping(item.get("outcome_measurement_contract"))
    validation = training.validate_outcome_measurement_contract(contract)
    if not validation["valid"]:
        raise Round5CustodyAdapterError("measurement_contract_invalid: " + "; ".join(validation["findings"]))
    selection = _mapping(item.get("selection"))
    source_access = _mapping(contract.get("source_access"))
    cells = []
    for cell in contract["atomic_cells"]:
        cells.append({
            "cell_id": cell["cell_id"],
            "measurement_clock": deepcopy(cell["measurement_clock"]),
            "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
            "field_identity": deepcopy(cell["field_identity"]),
            "raw_input_fields": deepcopy(cell["raw_input_fields"]),
            "unit": deepcopy(cell["unit"]),
            "formula": deepcopy(cell["formula"]),
            "label_rule": deepcopy(cell["label_rule"]),
            "conflict_rule": deepcopy(cell["conflict_rule"]),
            "unknown_rule": deepcopy(cell["unknown_rule"]),
            "mismatch_rule": deepcopy(cell["mismatch_rule"]),
            "allowed_source_types": deepcopy(cell["allowed_source_types"]),
        })
    projection = acquisition.build_value_free_custody_projection(
        projection_id=f"CUSTODY:{selection.get('transition_id')}:V3",
        company_id=selection.get("company_id"),
        custodian_id=_mapping(item.get("decision_contract", {}).get("roles")).get("outcome_custodian_id"),
        cutoff_at=selection.get("cutoff_at"),
        next_cutoff_at=selection.get("next_cutoff_at"),
        measurement_contract_ref={
            "contract_set_id": contract.get("contract_set_id"),
            "contract_version": 3,
        },
        authorized_source_identity={
            "source_id": source_access.get("source_id"),
            "source_type": source_access.get("source_type"),
            "official_url": source_access.get("official_url"),
            "issuer_id": source_access.get("issuer_id"),
            "report_period_end": source_access.get("report_period_end"),
            "availability_precision": source_access.get("availability_precision"),
            "source_available_at": source_access.get("source_available_at"),
            "source_available_date": source_access.get("source_available_date"),
            "published_after_cutoff": source_access.get("published_after_cutoff"),
            "access_state": source_access.get("access_state"),
            "custodian_access": source_access.get("custodian_access"),
            "authorization_receipt_id": source_access.get("authorization_receipt_id"),
        },
        atomic_measurement_contracts=cells,
    )
    findings = _forbidden(projection)
    if findings:
        raise Round5CustodyAdapterError("value_free_projection_contains_forbidden_fields: " + ", ".join(findings))
    projection["submission_api"] = "outcome_measurement_round5_adapter.validate_canonical_custodian_submission"
    projection["settlement_api"] = "outcome_measurement_round5_adapter.settle_via_public_adapter"
    return projection


def validate_value_free_custody_projection(projection: Any, *, package: Any) -> dict[str, Any]:
    expected = build_value_free_custody_projection(package)
    if projection != expected:
        return {"valid": False, "findings": ["custody_projection_must_match_frozen_contract_projection"]}
    return {"valid": True, "findings": [], "projection": deepcopy(expected)}


def normalize_custodian_field_records(records: Any, *, projection: Any) -> list[dict[str, Any]]:
    """Translate custody-facing source names without changing a value or state.

    The custodian records where a value was actually found.  The acquisition
    protocol also needs the frozen semantic locator.  Both are retained: the
    frozen locator remains the contract binding, while ``custodian_locator``
    preserves the page-local table, line and period reported by the reader.
    """
    projected = _mapping(projection)
    contracts = projected.get("atomic_measurement_contracts")
    if not isinstance(records, list) or not isinstance(contracts, list):
        raise Round5CustodyAdapterError("custodian_field_records_or_projection_invalid")
    expected = [
        (cell["cell_id"], raw["field_id"], cell, raw)
        for cell in contracts
        for raw in cell.get("raw_input_fields", [])
    ]
    supplied = [
        (record.get("cell_id"), record.get("field_id"))
        for record in records if isinstance(record, dict)
    ]
    if supplied != [(cell_id, field_id) for cell_id, field_id, _, _ in expected]:
        raise Round5CustodyAdapterError(
            "custodian_field_records_must_cover_frozen_raw_inputs_in_order"
        )
    source_identity = _mapping(projected.get("authorized_source_identity"))
    normalized: list[dict[str, Any]] = []
    for record, (_, _, cell, raw) in zip(records, expected, strict=True):
        item = deepcopy(record)
        if item.get("measurement_clock") != raw.get("measurement_clock"):
            raise Round5CustodyAdapterError("custodian_field_record_clock_mismatch")
        if item.get("responsibility_boundary") != cell.get("responsibility_boundary"):
            raise Round5CustodyAdapterError("custodian_field_record_boundary_mismatch")
        if item.get("unit") != raw.get("unit"):
            raise Round5CustodyAdapterError("custodian_field_record_unit_mismatch")
        if item.get("status") in {"OBSERVED", "MEASUREMENT_MISMATCH"}:
            source = _mapping(item.get("source"))
            actual_locator = {
                key: source.get(key) for key in ("table_or_note", "line_item", "period_column")
            }
            if any(not isinstance(value, str) or not value.strip() for value in actual_locator.values()):
                raise Round5CustodyAdapterError("custodian_field_record_actual_locator_required")
            page = source.get("pdf_page")
            if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                raise Round5CustodyAdapterError("custodian_field_record_pdf_page_required")
            for custody_key, canonical_key in (
                ("source_id", "source_id"),
                ("source_type", "source_type"),
                ("official_url", "official_url"),
                ("issuer_id", "issuer_id"),
                ("report_period_end", "report_period_end"),
                ("availability_precision", "availability_precision"),
                ("source_available_at", "source_available_at"),
                ("source_available_date", "source_available_date"),
            ):
                if source.get(custody_key) != source_identity.get(canonical_key):
                    raise Round5CustodyAdapterError(
                        "custodian_field_record_authorized_source_mismatch:" + custody_key
                    )
            item["source"] = {
                "source_id": source_identity["source_id"],
                "source_url": source_identity["official_url"],
                "official_source_type": source_identity["source_type"],
                "issuer_id": source_identity["issuer_id"],
                "report_period_end": source_identity["report_period_end"],
                "availability_precision": source_identity["availability_precision"],
                "source_available_at": source_identity["source_available_at"],
                "source_available_date": source_identity["source_available_date"],
                "field_identity": item["field_id"],
                "measurement_clock": deepcopy(item["measurement_clock"]),
                "responsibility_boundary": deepcopy(item["responsibility_boundary"]),
                "unit": item["unit"],
                "pdf_page": page,
                "field_ref": f"PDF p.{page}",
                **deepcopy(raw["locator"]),
                "custodian_locator": actual_locator,
            }
        normalized.append(item)
    return normalized


def _read_active_artifact(name: str) -> dict[str, Any]:
    path = ROUND5_ARTIFACT_DIR / name
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Round5CustodyAdapterError("canonical_round5_artifact_unavailable:" + name) from exc
    if not isinstance(value, dict):
        raise Round5CustodyAdapterError("canonical_round5_artifact_must_be_object:" + name)
    return value


def resolve_canonical_round5_bundle(
    *, package_id: str, control_receipt_id: str, adapter_acceptance_receipt_id: str,
) -> dict[str, Any]:
    """Resolve the active Round 5 chain by identity, never by caller payload."""
    if not all(isinstance(value, str) and value for value in (
        package_id, control_receipt_id, adapter_acceptance_receipt_id,
    )):
        raise Round5CustodyAdapterError("canonical_round5_identity_required")
    package = _read_active_artifact(ROUND5_ACTIVE_ARTIFACTS["package"])
    projection = _read_active_artifact(ROUND5_ACTIVE_ARTIFACTS["projection"])
    control_receipt = _read_active_artifact(ROUND5_ACTIVE_ARTIFACTS["control"])
    adapter_receipt = _read_active_artifact(ROUND5_ACTIVE_ARTIFACTS["adapter"])
    if package.get("package_id") != package_id:
        raise Round5CustodyAdapterError("canonical_round5_package_identity_mismatch")
    if control_receipt.get("receipt_id") != control_receipt_id:
        raise Round5CustodyAdapterError("canonical_round5_control_receipt_identity_mismatch")
    if adapter_receipt.get("receipt_id") != adapter_acceptance_receipt_id:
        raise Round5CustodyAdapterError("canonical_round5_adapter_receipt_identity_mismatch")
    package_ref = _mapping(control_receipt.get("preoutcome_package_ref"))
    if package_ref.get("package_id") != package_id or package_ref.get("artifact") != ROUND5_ACTIVE_ARTIFACTS["package"]:
        raise Round5CustodyAdapterError("canonical_round5_control_package_binding_invalid")
    active_refs = _mapping(adapter_receipt.get("active_artifact_refs"))
    if active_refs != ROUND5_ACTIVE_ARTIFACT_REFS:
        raise Round5CustodyAdapterError("canonical_round5_adapter_artifact_binding_invalid")
    package_contract = _mapping(package.get("outcome_measurement_contract"))
    contract_validation = training.validate_outcome_measurement_contract(package_contract)
    if not contract_validation["valid"]:
        raise Round5CustodyAdapterError("canonical_round5_package_contract_invalid:" + ";".join(contract_validation["findings"]))
    try:
        canonical_contract = enterprise_control.resolve_measurement_contract(package_contract["contract_set_id"])
    except enterprise_control.TrainingControlPlaneError as exc:
        raise Round5CustodyAdapterError("canonical_round5_contract_unavailable:" + exc.code) from exc
    if canonical_contract != package_contract:
        raise Round5CustodyAdapterError("canonical_round5_contract_payload_mismatch")
    expected_projection = build_value_free_custody_projection(package)
    if projection != expected_projection:
        raise Round5CustodyAdapterError("canonical_round5_projection_payload_mismatch")
    if _mapping(control_receipt.get("value_free_custody")).get("artifact") != ROUND5_ACTIVE_ARTIFACTS["projection"]:
        raise Round5CustodyAdapterError("canonical_round5_control_projection_binding_invalid")
    if _mapping(control_receipt.get("canonical_measurement_contract_registration")).get("contract_set_id") != package_contract["contract_set_id"]:
        raise Round5CustodyAdapterError("canonical_round5_control_contract_binding_invalid")
    return {
        "package": package,
        "projection": projection,
        "control_receipt": control_receipt,
        "adapter_acceptance_receipt": adapter_receipt,
        "measurement_contract": deepcopy(canonical_contract),
    }


def bootstrap_canonical_round5_route() -> dict[str, Any]:
    """Register the fixed 29/31/32 route before any outcome access begins."""
    bundle = resolve_canonical_round5_bundle(
        package_id="EMFP:CN:CEMENT:600802:20150415:V3",
        control_receipt_id="EMPCPR:CN:CEMENT:600802:20150415:V3",
        adapter_acceptance_receipt_id="R5V3AR:CN600802:20150415:V1",
    )
    result = enterprise_control.bootstrap_round5_route()
    expected = {
        "package_id": bundle["package"]["package_id"],
        "control_receipt_id": bundle["control_receipt"]["receipt_id"],
        "adapter_acceptance_receipt_id": bundle["adapter_acceptance_receipt"]["receipt_id"],
        "contract_set_id": bundle["measurement_contract"]["contract_set_id"],
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise Round5CustodyAdapterError("canonical_round5_bootstrap_route_mismatch")
    return result


def validate_custodian_submission(
    submission: Any,
    *,
    projection: Any,
    measurement_contract: Any,
) -> dict[str, Any]:
    """Map a Round 5 envelope into the public contract-aware validator."""
    item = _mapping(submission)
    required = {
        "schema_version", "authorization_receipt_id", "custodian_id", "projection_id",
        "outcome_access_authorization", "acquisition_result",
    }
    findings = [f"submission.missing:{key}" for key in sorted(required - set(item))]
    if set(item).difference(required):
        findings.append("submission.contains_unapproved_fields")
    if item.get("schema_version") != "enterprise-round5-custodian-submission.v1":
        findings.append("submission.schema_version_invalid")
    if item.get("projection_id") != _mapping(projection).get("projection_id"):
        findings.append("submission.projection_id_mismatch")
    authorization = _mapping(item.get("outcome_access_authorization"))
    acquisition_result = item.get("acquisition_result")
    result = acquisition.validate_acquisition_result(
        acquisition_result,
        measurement_contract=measurement_contract,
        outcome_access_authorization=authorization,
    )
    if not result["valid"]:
        findings.extend("acquisition:" + finding for finding in result["findings"])
    source_identity = _mapping(_mapping(projection).get("authorized_source_identity"))
    if item.get("custodian_id") != _mapping(projection).get("custodian_id"):
        findings.append("submission.custodian_id_must_match_projection")
    if item.get("authorization_receipt_id") != source_identity.get("authorization_receipt_id"):
        findings.append("submission.authorization_receipt_must_match_projection")
    if authorization.get("authorization_receipt_id") != item.get("authorization_receipt_id"):
        findings.append("submission.authorization_object_must_match_receipt")
    if authorization.get("custodian_id") != item.get("custodian_id"):
        findings.append("submission.authorization_object_must_match_custodian")
    expected_contract_ref = {
        "measurement_contract_id": _mapping(projection).get("measurement_contract_ref", {}).get("contract_set_id"),
        "measurement_contract_version": _mapping(projection).get("measurement_contract_ref", {}).get("contract_version"),
    }
    if _mapping(acquisition_result).get("measurement_contract_ref") != expected_contract_ref:
        findings.append("submission.acquisition_contract_ref_must_match_projection")
    if _mapping(acquisition_result).get("custodian_id") != item.get("custodian_id"):
        findings.append("submission.acquisition_custodian_must_match_submission")
    if _forbidden(item):
        findings.append("submission_contains_forecast_or_judgment_fields")
    return {"valid": not findings, "findings": findings, "submission": deepcopy(item) if not findings else None}


def validate_canonical_custodian_submission(
    *, package_id: str, control_receipt_id: str, adapter_acceptance_receipt_id: str,
    acquisition_result: Any, outcome_access_authorization: Any,
) -> dict[str, Any]:
    """Validate a production submission after canonical identity resolution."""
    bundle = resolve_canonical_round5_bundle(
        package_id=package_id,
        control_receipt_id=control_receipt_id,
        adapter_acceptance_receipt_id=adapter_acceptance_receipt_id,
    )
    projection = bundle["projection"]
    submission = {
        "schema_version": "enterprise-round5-custodian-submission.v1",
        "authorization_receipt_id": _mapping(outcome_access_authorization).get("authorization_receipt_id"),
        "custodian_id": _mapping(outcome_access_authorization).get("custodian_id"),
        "projection_id": projection.get("projection_id"),
        "outcome_access_authorization": deepcopy(outcome_access_authorization),
        "acquisition_result": deepcopy(acquisition_result),
    }
    return validate_custodian_submission(
        submission,
        projection=projection,
        measurement_contract=bundle["measurement_contract"],
    )


def register_canonical_acquisition_result(
    *, package_id: str, control_receipt_id: str, adapter_acceptance_receipt_id: str,
    acquisition_result: Any, outcome_access_authorization: Any,
    observed_at: str, settlement_id: str, settled_at: str,
) -> dict[str, Any]:
    """Enter the public Enterprise settlement adapter using canonical IDs only."""
    bundle = resolve_canonical_round5_bundle(
        package_id=package_id,
        control_receipt_id=control_receipt_id,
        adapter_acceptance_receipt_id=adapter_acceptance_receipt_id,
    )
    validation = validate_canonical_custodian_submission(
        package_id=package_id,
        control_receipt_id=control_receipt_id,
        adapter_acceptance_receipt_id=adapter_acceptance_receipt_id,
        acquisition_result=acquisition_result,
        outcome_access_authorization=outcome_access_authorization,
    )
    if not validation["valid"]:
        raise Round5CustodyAdapterError("canonical_round5_submission_invalid:" + ";".join(validation["findings"]))
    return settlement_adapter._settle_enterprise_acquisition_result(
        measurement_contract=bundle["measurement_contract"],
        outcome_access_authorization=outcome_access_authorization,
        acquisition_result=acquisition_result,
        observed_at=observed_at,
        settlement_id=settlement_id,
        settled_at=settled_at,
        canonical_round5_binding={
            "package_id": package_id,
            "control_receipt_id": control_receipt_id,
            "adapter_acceptance_receipt_id": adapter_acceptance_receipt_id,
        },
    )


def settle_via_public_adapter(
    *, package_id: str, control_receipt_id: str, adapter_acceptance_receipt_id: str,
    acquisition_result: Any, outcome_access_authorization: Any,
    observed_at: str, settlement_id: str, settled_at: str,
) -> dict[str, Any]:
    """Settle Enterprise Round 5 only through canonical artifact identities."""
    return register_canonical_acquisition_result(
        package_id=package_id,
        control_receipt_id=control_receipt_id,
        adapter_acceptance_receipt_id=adapter_acceptance_receipt_id,
        acquisition_result=acquisition_result,
        outcome_access_authorization=outcome_access_authorization,
        observed_at=observed_at,
        settlement_id=settlement_id,
        settled_at=settled_at,
    )


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Round5CustodyAdapterError(f"{path} must contain one JSON object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-package", type=Path, required=True)
    parser.add_argument("--v3-package", type=Path, required=True)
    parser.add_argument("--custody-projection", type=Path, required=True)
    parser.add_argument("--frozen-at", required=True)
    args = parser.parse_args()
    package = build_round5_v3_package(_read(args.v2_package), frozen_at=args.frozen_at)
    custody = build_value_free_custody_projection(package)
    _write(args.v3_package, package)
    _write(args.custody_projection, custody)
    print(json.dumps({
        "package_id": package["package_id"],
        "custody_projection_id": custody["projection_id"],
        "outcome_access": custody["outcome_access"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
