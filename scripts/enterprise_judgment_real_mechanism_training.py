#!/usr/bin/env python3
"""Production builder for outcome-blind, cell-local mechanism training turns."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from typing import Any

try:
    from scripts import enterprise_judgment_forecast_projection as forecast_projection
    from scripts import enterprise_judgment_mechanism as mechanism
    from scripts import enterprise_judgment_reconstruction_registry as reconstruction_registry
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_forecast_projection as forecast_projection
    import enterprise_judgment_mechanism as mechanism
    import enterprise_judgment_reconstruction_registry as reconstruction_registry


PACKAGE_SCHEMA_VERSION = "enterprise-real-mechanism-preoutcome-package.v2"
CONTRACT_SCHEMA_VERSION = "enterprise-outcome-measurement-contract.v2"
SELECTION_POLICY = "FIRST_RECEIPT_ELIGIBLE_IMMUTABLE_ROSTER_ROW_NO_OUTCOME_FILTER"

_COMPLETION_RECEIPT_SCHEMAS = {
    "enterprise-judgment-feedback-settlement.v1",
    "enterprise-judgment-continuation-feedback-settlement.v1",
    "enterprise-judgment-round3-feedback-settlement.v1",
}
_ADJUDICATION_SCHEMA = "enterprise-mechanism-feedback-superseding-adjudication.v1"
_PACKAGE_KEYS = {
    "schema_version", "package_id", "selection", "source_packet_receipt",
    "decision_contract", "enterprise_system_model", "management_decision_ledger",
    "reconstruction_spec", "episode_manifest", "mechanism_thread_set",
    "outcome_measurement_contract", "forecast_projection_source", "strongest_rival",
    "sealed_outcome_source", "rights", "allowed_outputs",
}
_CONTRACT_KEYS = {
    "schema_version", "contract_set_id", "package_ref", "company_id", "cutoff_at",
    "outcome_window", "source_access", "atomic_cells", "thread_combination_rules",
    "rights", "allowed_outputs",
}
_WINDOW_KEYS = {"period_start", "period_end", "fiscal_period", "settlement_due_at"}
_SOURCE_ACCESS_KEYS = {
    "source_id", "source_type", "official_url", "published_after_cutoff",
    "access_state", "custodian_access",
}
_CELL_KEYS = {
    "cell_id", "thread_id", "layer", "outcome_period", "responsibility_boundary",
    "field_identity", "unit", "formula", "label_rule", "conflict_rule",
    "unknown_rule", "mismatch_rule", "allowed_source_types", "prohibited_inference",
}
_BOUNDARY_KEYS = {
    "responsibility_unit_id", "perimeter_id", "arena_id", "scope_requirement",
}
_FIELD_KEYS = {
    "outcome_field_id", "baseline_field_id", "statement_scope", "table_or_note",
    "line_item", "field_kind",
}
_UNIT_KEYS = {"kind", "currency", "scale"}
_FORMULA_KEYS = {"operator", "input_field_ids", "expression", "zero_baseline_rule"}
_LABEL_KEYS = {"type", "decrease_lte", "increase_gte", "ordered_labels"}
_CONFLICT_KEYS = {"multiple_values", "boundary_conflict", "period_conflict"}
_UNKNOWN_KEYS = {"conditions", "label"}
_MISMATCH_KEYS = {"conditions", "label", "propagation", "dependent_cell_ids"}
_COMBINATION_KEYS = {
    "rule_id", "thread_id", "input_cell_ids", "evaluation_order", "rule",
    "conflict_rule", "authorization",
}
_LAYERS = {
    "IMPLEMENTED", "EXECUTED", "CUSTOMER_RESPONSE", "SALES_VOLUME", "PRICE",
    "UNIT_COST", "SELLING_EXPENSE", "GROSS_MARGIN", "WORKING_CAPITAL", "CASH",
    "CAPITAL_BURDEN", "FINANCING", "PERMANENT_LOSS",
}
_LABEL_SEQUENCES = {
    "EVENT_PRESENCE": ["MEASUREMENT_MISMATCH", "OBSERVED_YES", "OBSERVED_NO", "UNKNOWN"],
    "PERCENT_CHANGE_BAND": ["MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE", "OBSERVED_INCREASE", "UNKNOWN"],
    "ABSOLUTE_CHANGE_BAND": ["MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE", "OBSERVED_INCREASE", "UNKNOWN"],
}
_FORMULA_BY_LABEL = {
    "EVENT_PRESENCE": "EVENT_BOOLEAN",
    "PERCENT_CHANGE_BAND": "PERCENT_CHANGE",
    "ABSOLUTE_CHANGE_BAND": "DIFFERENCE",
}
_RIGHTS = {
    "directional_learning": "NOT_AUTHORIZED",
    "enterprise_learning": "NOT_AUTHORIZED",
    "comparative": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _closed(value: Any, keys: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    missing = keys - set(item)
    extra = set(item) - keys
    if missing:
        findings.append(f"{path}.missing:{','.join(sorted(missing))}")
    if extra:
        findings.append(f"{path}.extra:{','.join(sorted(extra))}")
    return item


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        findings.append(f"{path}.must_be_iso8601")
        return None


def _company_from_receipt(receipt: dict[str, Any]) -> str:
    company_id = _text(receipt.get("company_id"))
    if company_id:
        return company_id
    return ""


def derive_receipt_backed_selection(
    block: Any,
    roster_freeze: Any,
    receipts: list[Any],
) -> dict[str, Any]:
    """Select the first row not excluded by formal receipts or adjudication."""
    block_item = _mapping(block)
    freeze_item = _mapping(roster_freeze)
    roster = [_mapping(row) for row in _items(block_item.get("company_cutoff_transition_roster"))]
    frozen_ids = [_text(value) for value in _items(freeze_item.get("company_cutoff_transition_ids"))]
    findings: list[str] = []
    if block_item.get("block_id") != freeze_item.get("block_id"):
        findings.append("selection.block_must_match_roster_freeze")
    roster_ids = [_text(row.get("transition_id")) for row in roster]
    if roster_ids != frozen_ids:
        findings.append("selection.roster_must_match_immutable_freeze_in_order")
    if [row.get("rank") for row in roster] != list(range(1, len(roster) + 1)):
        findings.append("selection.roster_ranks_must_be_contiguous")

    completed_companies: set[str] = set()
    consumed_transitions: set[str] = set()
    receipt_refs: list[str] = []
    for index, raw in enumerate(receipts):
        receipt = _mapping(raw)
        schema = receipt.get("schema_version")
        if schema in _COMPLETION_RECEIPT_SCHEMAS:
            company_id = _company_from_receipt(receipt)
            if not company_id:
                findings.append(f"selection.receipts[{index}].completed_receipt_company_missing")
                continue
            if not _mapping(receipt.get("source_receipt")):
                findings.append(f"selection.receipts[{index}].completed_receipt_source_missing")
                continue
            completed_companies.add(company_id)
            receipt_refs.append(_text(receipt.get("settlement_id")))
            matching = [
                row for row in roster
                if row.get("company_id") == company_id and row.get("cutoff_at") == receipt.get("cutoff_at")
            ]
            if len(matching) == 1:
                consumed_transitions.add(_text(matching[0].get("transition_id")))
        elif schema == _ADJUDICATION_SCHEMA:
            supersedes = _mapping(receipt.get("supersedes"))
            transition_id = _text(supersedes.get("transition_id"))
            if (
                receipt.get("adjudication_status") != "CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY"
                or receipt.get("permanent_no_refreeze") is not True
                or transition_id not in frozen_ids
            ):
                findings.append(f"selection.receipts[{index}].adjudication_invalid")
                continue
            consumed_transitions.add(transition_id)
            receipt_refs.append(_text(receipt.get("adjudication_id")))
        else:
            findings.append(f"selection.receipts[{index}].unsupported_schema")

    selected = next(
        (
            row for row in roster
            if row.get("company_id") not in completed_companies
            and row.get("transition_id") not in consumed_transitions
        ),
        None,
    )
    if selected is None:
        findings.append("selection.no_receipt_eligible_roster_row")
    return {
        "valid": not findings,
        "findings": findings,
        "selection": None if findings or selected is None else {
            "selection_policy": SELECTION_POLICY,
            "source_roster_ref": freeze_item.get("freeze_id"),
            "receipt_refs": sorted(ref for ref in receipt_refs if ref),
            "derived_completed_company_ids": sorted(completed_companies),
            "derived_consumed_transition_ids": sorted(consumed_transitions),
            "selected_rank": selected.get("rank"),
            "transition_id": selected.get("transition_id"),
            "company_id": selected.get("company_id"),
            "company_cluster_id": selected.get("company_cluster_id"),
            "cutoff_at": selected.get("cutoff_at"),
            "next_cutoff_at": selected.get("next_cutoff_at"),
            "selection_used_outcome": False,
            "selection_used_lifecycle_label": False,
            "selection_used_source_convenience": False,
        },
    }


def validate_outcome_measurement_contract(contract: Any) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(contract, _CONTRACT_KEYS, "measurement_contract", findings)
    if item.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        findings.append("measurement_contract.schema_version_invalid")
    for field in ("contract_set_id", "package_ref", "company_id", "cutoff_at"):
        if not _text(item.get(field)):
            findings.append(f"measurement_contract.{field}_required")
    window = _closed(item.get("outcome_window"), _WINDOW_KEYS, "measurement_contract.outcome_window", findings)
    cutoff = _instant(item.get("cutoff_at"), "measurement_contract.cutoff_at", findings)
    period_start = _instant(window.get("period_start"), "measurement_contract.outcome_window.period_start", findings)
    period_end = _instant(window.get("period_end"), "measurement_contract.outcome_window.period_end", findings)
    due_at = _instant(window.get("settlement_due_at"), "measurement_contract.outcome_window.settlement_due_at", findings)
    if cutoff and period_start and period_start < cutoff:
        findings.append("measurement_contract.outcome_window_must_start_at_or_after_cutoff")
    if period_start and period_end and period_end <= period_start:
        findings.append("measurement_contract.outcome_window_order_invalid")
    if period_end and due_at and due_at <= period_end:
        findings.append("measurement_contract.settlement_due_must_follow_period_end")
    source_access = _closed(item.get("source_access"), _SOURCE_ACCESS_KEYS, "measurement_contract.source_access", findings)
    if source_access.get("access_state") != "SEALED_UNTIL_PREOUTCOME_COMMIT":
        findings.append("measurement_contract.outcome_source_must_be_sealed")
    if source_access.get("published_after_cutoff") is not True or source_access.get("custodian_access") != "OUTCOME_ONLY":
        findings.append("measurement_contract.outcome_source_access_invalid")

    cells = [_closed(raw, _CELL_KEYS, f"measurement_contract.atomic_cells[{index}]", findings) for index, raw in enumerate(_items(item.get("atomic_cells")))]
    cell_ids = [_text(cell.get("cell_id")) for cell in cells]
    if not cells or "" in cell_ids or len(cell_ids) != len(set(cell_ids)):
        findings.append("measurement_contract.atomic_cell_ids_must_be_unique")
    outcome_field_ids: list[str] = []
    for index, cell in enumerate(cells):
        path = f"measurement_contract.atomic_cells[{index}]"
        if cell.get("layer") not in _LAYERS:
            findings.append(f"{path}.layer_invalid")
        if not _text(cell.get("thread_id")) or not _text(cell.get("prohibited_inference")):
            findings.append(f"{path}.thread_and_prohibited_inference_required")
        cell_period = _closed(cell.get("outcome_period"), _WINDOW_KEYS - {"settlement_due_at"}, f"{path}.outcome_period", findings)
        if cell_period != {key: window.get(key) for key in _WINDOW_KEYS - {"settlement_due_at"}}:
            findings.append(f"{path}.outcome_period_must_match_contract_window")
        boundary = _closed(cell.get("responsibility_boundary"), _BOUNDARY_KEYS, f"{path}.responsibility_boundary", findings)
        if not all(_text(boundary.get(key)) for key in _BOUNDARY_KEYS):
            findings.append(f"{path}.responsibility_boundary_incomplete")
        field = _closed(cell.get("field_identity"), _FIELD_KEYS, f"{path}.field_identity", findings)
        outcome_field_id = _text(field.get("outcome_field_id"))
        if not outcome_field_id:
            findings.append(f"{path}.outcome_field_id_required")
        outcome_field_ids.append(outcome_field_id)
        if not all(_text(field.get(key)) for key in _FIELD_KEYS - {"baseline_field_id"}):
            findings.append(f"{path}.field_identity_incomplete")
        unit = _closed(cell.get("unit"), _UNIT_KEYS, f"{path}.unit", findings)
        if not all(_text(unit.get(key)) for key in _UNIT_KEYS):
            findings.append(f"{path}.unit_incomplete")
        formula = _closed(cell.get("formula"), _FORMULA_KEYS, f"{path}.formula", findings)
        labels = _closed(cell.get("label_rule"), _LABEL_KEYS, f"{path}.label_rule", findings)
        label_type = labels.get("type")
        if label_type not in _LABEL_SEQUENCES:
            findings.append(f"{path}.label_type_invalid")
        elif labels.get("ordered_labels") != _LABEL_SEQUENCES[label_type]:
            findings.append(f"{path}.ordered_labels_invalid")
        if formula.get("operator") != _FORMULA_BY_LABEL.get(label_type):
            findings.append(f"{path}.formula_operator_must_match_label_type")
        input_ids = [_text(value) for value in _items(formula.get("input_field_ids"))]
        expected_inputs = [outcome_field_id]
        baseline_field_id = _text(field.get("baseline_field_id"))
        if label_type != "EVENT_PRESENCE":
            if not baseline_field_id:
                findings.append(f"{path}.baseline_field_id_required")
            expected_inputs = [baseline_field_id, outcome_field_id]
            decrease = labels.get("decrease_lte")
            increase = labels.get("increase_gte")
            if not isinstance(decrease, (int, float)) or not isinstance(increase, (int, float)) or decrease >= increase:
                findings.append(f"{path}.direction_thresholds_invalid")
        elif labels.get("decrease_lte") is not None or labels.get("increase_gte") is not None:
            findings.append(f"{path}.event_thresholds_must_be_null")
        if input_ids != expected_inputs or not _text(formula.get("expression")) or not _text(formula.get("zero_baseline_rule")):
            findings.append(f"{path}.formula_identity_invalid")
        conflict = _closed(cell.get("conflict_rule"), _CONFLICT_KEYS, f"{path}.conflict_rule", findings)
        if set(conflict.values()) != {"MEASUREMENT_MISMATCH"}:
            findings.append(f"{path}.conflict_rule_must_resolve_to_mismatch")
        unknown = _closed(cell.get("unknown_rule"), _UNKNOWN_KEYS, f"{path}.unknown_rule", findings)
        if unknown.get("label") != "UNKNOWN" or not _items(unknown.get("conditions")):
            findings.append(f"{path}.unknown_rule_invalid")
        mismatch = _closed(cell.get("mismatch_rule"), _MISMATCH_KEYS, f"{path}.mismatch_rule", findings)
        if mismatch.get("label") != "MEASUREMENT_MISMATCH" or mismatch.get("propagation") != "LOCAL_ONLY":
            findings.append(f"{path}.mismatch_must_be_local")
        if _items(mismatch.get("dependent_cell_ids")):
            findings.append(f"{path}.atomic_cell_cannot_invalidate_siblings")
        if not _items(mismatch.get("conditions")):
            findings.append(f"{path}.mismatch_conditions_required")
        if _items(cell.get("allowed_source_types")) != ["OFFICIAL_AUDITED_ANNUAL_REPORT"]:
            findings.append(f"{path}.allowed_source_types_invalid")
    if "" in outcome_field_ids or len(outcome_field_ids) != len(set(outcome_field_ids)):
        findings.append("measurement_contract.outcome_field_ids_must_be_unique")

    combination_rules = [
        _closed(raw, _COMBINATION_KEYS, f"measurement_contract.thread_combination_rules[{index}]", findings)
        for index, raw in enumerate(_items(item.get("thread_combination_rules")))
    ]
    for index, rule in enumerate(combination_rules):
        path = f"measurement_contract.thread_combination_rules[{index}]"
        input_cell_ids = [_text(value) for value in _items(rule.get("input_cell_ids"))]
        if not input_cell_ids or any(cell_id not in cell_ids for cell_id in input_cell_ids):
            findings.append(f"{path}.input_cells_invalid")
        if rule.get("evaluation_order") != input_cell_ids:
            findings.append(f"{path}.evaluation_order_must_be_explicit")
        if not _text(rule.get("rule")) or not _text(rule.get("conflict_rule")):
            findings.append(f"{path}.rule_and_conflict_rule_required")
        if rule.get("authorization") != "TEACHING_ONLY_NO_CAUSAL_UPGRADE":
            findings.append(f"{path}.authorization_invalid")
    if item.get("rights") != _RIGHTS:
        findings.append("measurement_contract.rights_invalid")
    if item.get("allowed_outputs") != ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"]:
        findings.append("measurement_contract.allowed_outputs_invalid")
    return {
        "valid": not findings,
        "findings": findings,
        "contract": deepcopy(item) if not findings else None,
    }


def settle_synthetic_atomic_observations(contract: Any, observations: Any) -> dict[str, Any]:
    """Exercise deterministic labels without granting real-outcome authority."""
    validation = validate_outcome_measurement_contract(contract)
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "cell_results": []}
    supplied = _mapping(observations)
    results: list[dict[str, Any]] = []
    for cell in validation["contract"]["atomic_cells"]:
        cell_id = cell["cell_id"]
        observation = _mapping(supplied.get(cell_id))
        state = observation.get("state", "UNKNOWN")
        if state == "MEASUREMENT_MISMATCH":
            label, value = "MEASUREMENT_MISMATCH", None
        elif state == "UNKNOWN":
            label, value = "UNKNOWN", None
        elif state != "MATCHED":
            return {"valid": False, "findings": [f"observations.{cell_id}.state_invalid"], "cell_results": []}
        else:
            label_type = cell["label_rule"]["type"]
            if label_type == "EVENT_PRESENCE":
                if not isinstance(observation.get("outcome"), bool):
                    return {"valid": False, "findings": [f"observations.{cell_id}.event_must_be_boolean"], "cell_results": []}
                value = observation["outcome"]
                label = "OBSERVED_YES" if value else "OBSERVED_NO"
            else:
                baseline, outcome = observation.get("baseline"), observation.get("outcome")
                if not isinstance(baseline, (int, float)) or not isinstance(outcome, (int, float)):
                    return {"valid": False, "findings": [f"observations.{cell_id}.numeric_values_required"], "cell_results": []}
                if cell["formula"]["operator"] == "PERCENT_CHANGE":
                    if baseline == 0:
                        return {"valid": False, "findings": [f"observations.{cell_id}.zero_baseline"], "cell_results": []}
                    value = (outcome - baseline) / abs(baseline)
                else:
                    value = outcome - baseline
                if value <= cell["label_rule"]["decrease_lte"]:
                    label = "OBSERVED_DECREASE"
                elif value >= cell["label_rule"]["increase_gte"]:
                    label = "OBSERVED_INCREASE"
                else:
                    label = "OBSERVED_STABLE"
        results.append({
            "cell_id": cell_id,
            "label": label,
            "computed_value": value,
            "mismatch_propagation": "LOCAL_ONLY",
        })
    return {
        "valid": True,
        "findings": [],
        "cell_results": results,
        "rights": deepcopy(_RIGHTS),
        "allowed_outputs": ["SYNTHETIC_VALIDATION_ONLY"],
    }


def validate_preoutcome_package(
    package: Any,
    *,
    block: Any,
    roster_freeze: Any,
    receipts: list[Any],
) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(package, _PACKAGE_KEYS, "preoutcome_package", findings)
    if item.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        findings.append("preoutcome_package.schema_version_invalid")
    selection_result = derive_receipt_backed_selection(block, roster_freeze, receipts)
    if not selection_result["valid"]:
        findings.extend("selection:" + finding for finding in selection_result["findings"])
    elif item.get("selection") != selection_result["selection"]:
        findings.append("preoutcome_package.selection_must_be_receipt_derived")
    contract_result = validate_outcome_measurement_contract(item.get("outcome_measurement_contract"))
    if not contract_result["valid"]:
        findings.extend("measurement_contract:" + finding for finding in contract_result["findings"])
    selection = _mapping(item.get("selection"))
    for component_name in (
        "source_packet_receipt", "decision_contract", "enterprise_system_model",
        "management_decision_ledger", "reconstruction_spec", "episode_manifest",
    ):
        component = _mapping(item.get(component_name))
        if component.get("company_id") != selection.get("company_id"):
            findings.append(f"preoutcome_package.{component_name}.company_must_match_selection")
        if component.get("cutoff_at") != selection.get("cutoff_at") and component_name not in {"management_decision_ledger"}:
            findings.append(f"preoutcome_package.{component_name}.cutoff_must_match_selection")
    sealed = _mapping(item.get("sealed_outcome_source"))
    if sealed.get("source_id") != _mapping(item.get("outcome_measurement_contract")).get("source_access", {}).get("source_id"):
        findings.append("preoutcome_package.sealed_source_must_match_measurement_contract")
    if sealed.get("access_state") != "SEALED_UNTIL_PREOUTCOME_COMMIT" or sealed.get("outcome_content_read") is not False:
        findings.append("preoutcome_package.outcome_must_remain_sealed")
    if item.get("rights") != _RIGHTS or item.get("allowed_outputs") != ["PREOUTCOME_FREEZE", "OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"]:
        findings.append("preoutcome_package.rights_or_outputs_invalid")
    return {
        "valid": not findings,
        "findings": findings,
        "package": deepcopy(item) if not findings else None,
        "derived_selection": selection_result.get("selection"),
    }


def register_and_project_preoutcome_package(
    package: Any,
    *,
    block: Any,
    roster_freeze: Any,
    receipts: list[Any],
    frozen_at: str,
) -> dict[str, Any]:
    """Register canonical J1, then call only the public Frozen-J1 J2/J3 APIs."""
    validation = validate_preoutcome_package(
        package,
        block=block,
        roster_freeze=roster_freeze,
        receipts=receipts,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "control_plane_receipt": None}
    item = validation["package"]
    registration = reconstruction_registry.register_canonical_from_artifacts(
        source_packet_receipt=item["source_packet_receipt"],
        decision_contract=item["decision_contract"],
        enterprise_model=item["enterprise_system_model"],
        decision_ledger=item["management_decision_ledger"],
        spec=item["reconstruction_spec"],
        frozen_at=frozen_at,
    )
    reconstruction_ref = {
        "reconstruction_id": registration["reconstruction_id"],
        "schema_version": registration["schema_version"],
    }
    j2 = mechanism.compile_mechanism_thread_projection(
        item["mechanism_thread_set"],
        episode_manifest=item["episode_manifest"],
        reconstruction_ref=reconstruction_ref,
    )
    if not j2["valid"]:
        return {"valid": False, "findings": ["j2:" + finding for finding in j2["findings"]], "control_plane_receipt": None}
    j3 = forecast_projection.compile_forecast_projection(
        item["episode_manifest"],
        item["forecast_projection_source"],
        mechanism_thread_set=item["mechanism_thread_set"],
        reconstruction_ref=reconstruction_ref,
    )
    if not j3["valid"]:
        return {"valid": False, "findings": ["j3:" + finding for finding in j3["findings"]], "control_plane_receipt": None}
    return {
        "valid": True,
        "findings": [],
        "control_plane_receipt": {
            "package_id": item["package_id"],
            "selection": deepcopy(item["selection"]),
            "canonical_j1_registration": registration,
            "frozen_j1_ref": reconstruction_ref,
            "public_j2_projection": {
                "thread_set_id": j2["mechanism_thread_read_model"]["thread_set_id"],
                "valid": True,
            },
            "public_j3_projection": {
                "projection_id": j3["forecast_projection"]["projection_id"],
                "projection_state": j3["forecast_projection"]["projection_state"],
                "valid": True,
            },
            "outcome_access": "NOT_AUTHORIZED",
            "rights": deepcopy(_RIGHTS),
            "allowed_outputs": ["PREOUTCOME_CONTROL_PLANE_RECEIPT", "OUTCOME_CUSTODY_REQUEST"],
        },
    }


def _read(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--block", type=Path, required=True)
    parser.add_argument("--roster-freeze", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, action="append", required=True)
    parser.add_argument("--frozen-at", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    package = _read(args.package)
    block = _read(args.block)
    roster_freeze = _read(args.roster_freeze)
    receipts = [_read(path) for path in args.receipt]
    if args.validate_only:
        result = validate_preoutcome_package(
            package,
            block=block,
            roster_freeze=roster_freeze,
            receipts=receipts,
        )
    else:
        result = register_and_project_preoutcome_package(
            package,
            block=block,
            roster_freeze=roster_freeze,
            receipts=receipts,
            frozen_at=args.frozen_at,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
