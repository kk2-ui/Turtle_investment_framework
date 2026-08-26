#!/usr/bin/env python3
"""Round 5 value-free custody projection over the shared outcome adapters.

The projection is the only object an independent custodian receives before
outcome access.  It contains atomic measurement contracts and the authorized
static-source identity, but no J2 hypothesis, J3 forecast direction/value, or
enterprise judgment.  Submission validation delegates to the reusable v1
acquisition module; future settlement delegates to its public v1 adapter.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from scripts import enterprise_judgment_real_mechanism_training as training
    from scripts import outcome_measurement_acquisition as acquisition
    from scripts import outcome_measurement_settlement_adapter as settlement_adapter
except ModuleNotFoundError:  # pragma: no cover
    import enterprise_judgment_real_mechanism_training as training
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


def _input(field_id: str, *, role: str, unit: str, clock: dict[str, Any]) -> dict[str, Any]:
    return {"field_id": field_id, "role": role, "unit": unit, "measurement_clock": deepcopy(clock)}


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
        raw = [_input(outcome_id, role="EVENT", unit="BOOLEAN_EVENT", clock=outcome_clock)]
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
            _input(field_id, role="BASELINE" if year == 2014 else "OUTCOME", unit=raw_unit, clock=_flow_clock(year))
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
        _input(baseline_id, role="BASELINE", unit=unit, clock=baseline_clock),
        _input(outcome_id, role="OUTCOME", unit=unit, clock=outcome_clock),
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
    return projection


def validate_value_free_custody_projection(projection: Any, *, package: Any) -> dict[str, Any]:
    expected = build_value_free_custody_projection(package)
    if projection != expected:
        return {"valid": False, "findings": ["custody_projection_must_match_frozen_contract_projection"]}
    return {"valid": True, "findings": [], "projection": deepcopy(expected)}


def validate_custodian_submission(
    submission: Any,
    *,
    projection: Any,
) -> dict[str, Any]:
    """Validate a future value-bearing submission without settling it."""
    item = _mapping(submission)
    required = {
        "schema_version", "authorization_receipt_id", "custodian_id", "projection_id",
        "acquisition_result", "observation_receipt_bindings",
    }
    findings = [f"submission.missing:{key}" for key in sorted(required - set(item))]
    if item.get("schema_version") != "enterprise-round5-custodian-submission.v1":
        findings.append("submission.schema_version_invalid")
    if item.get("projection_id") != _mapping(projection).get("projection_id"):
        findings.append("submission.projection_id_mismatch")
    acquisition_result = item.get("acquisition_result")
    result = acquisition.validate_acquisition_result(acquisition_result)
    if not result["valid"]:
        findings.extend("acquisition:" + finding for finding in result["findings"])
    source_identity = _mapping(_mapping(projection).get("authorized_source_identity"))
    if item.get("custodian_id") != _mapping(projection).get("custodian_id"):
        findings.append("submission.custodian_id_must_match_projection")
    if item.get("authorization_receipt_id") != source_identity.get("authorization_receipt_id"):
        findings.append("submission.authorization_receipt_must_match_projection")
    expected_contract_ref = {
        "measurement_contract_id": _mapping(projection).get("measurement_contract_ref", {}).get("contract_set_id"),
        "measurement_contract_version": _mapping(projection).get("measurement_contract_ref", {}).get("contract_version"),
    }
    if _mapping(acquisition_result).get("measurement_contract_ref") != expected_contract_ref:
        findings.append("submission.acquisition_contract_ref_must_match_projection")
    if _mapping(acquisition_result).get("custodian_id") != item.get("custodian_id"):
        findings.append("submission.acquisition_custodian_must_match_submission")
    observations = {
        observation.get("measurement_id"): observation
        for observation in _mapping(acquisition_result).get("observations", [])
        if isinstance(observation, dict)
    }
    bindings = item.get("observation_receipt_bindings")
    if not isinstance(bindings, list):
        findings.append("submission.observation_receipt_bindings_must_be_list")
        bindings = []
    bound_ids: set[str] = set()
    for index, raw_binding in enumerate(bindings):
        binding = _mapping(raw_binding)
        measurement_id = binding.get("measurement_id")
        observation = observations.get(measurement_id)
        if not isinstance(measurement_id, str) or measurement_id in bound_ids or observation is None:
            findings.append(f"submission.observation_receipt_bindings[{index}].measurement_identity_invalid")
            continue
        bound_ids.add(measurement_id)
        if observation.get("status") == "UNKNOWN":
            findings.append(f"submission.observation_receipt_bindings[{index}].unknown_must_not_create_observation_receipt")
            continue
        for key, expected in (
            ("custodian_id", item.get("custodian_id")),
            ("authorization_receipt_id", item.get("authorization_receipt_id")),
            ("source_id", source_identity.get("source_id")),
            ("field_identity", observation.get("metric_id")),
            ("unit", observation.get("unit")),
        ):
            if binding.get(key) != expected:
                findings.append(f"submission.observation_receipt_bindings[{index}].{key}_mismatch")
        if not isinstance(binding.get("pdf_page"), int) or binding["pdf_page"] < 1:
            findings.append(f"submission.observation_receipt_bindings[{index}].pdf_page_required")
        if not isinstance(binding.get("measurement_clock_evidence"), dict) or not binding["measurement_clock_evidence"]:
            findings.append(f"submission.observation_receipt_bindings[{index}].measurement_clock_evidence_required")
        if not isinstance(binding.get("responsibility_boundary"), dict) or not binding["responsibility_boundary"]:
            findings.append(f"submission.observation_receipt_bindings[{index}].responsibility_boundary_required")
        if observation.get("status") == "OBSERVED" and not isinstance(binding.get("raw_value"), (int, float, bool)):
            findings.append(f"submission.observation_receipt_bindings[{index}].raw_value_required")
    expected_bound = {measurement_id for measurement_id, observation in observations.items() if observation.get("status") != "UNKNOWN"}
    if bound_ids != expected_bound:
        findings.append("submission.observation_receipt_bindings_must_cover_each_non_unknown_observation_once")
    if _forbidden(item):
        findings.append("submission_contains_forecast_or_judgment_fields")
    return {"valid": not findings, "findings": findings, "submission": deepcopy(item) if not findings else None}


def settle_via_public_adapter(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Delegate future settlement to the reusable public v1 adapter.

    This function intentionally has no Round 5 scoring logic.  It is not
    callable from the pre-outcome freeze path and is left as a named bridge so
    the custodian cannot accidentally acquire a second settlement engine.
    """
    return settlement_adapter.register_acquisition_result(*args, **kwargs)
