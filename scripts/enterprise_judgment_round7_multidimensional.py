#!/usr/bin/env python3
"""Round 7 multidimensional enterprise-judgment training.

Round 7 compares an aggregate issuer-trend reading with a cumulative enterprise
judgment chain under one cutoff evidence budget.  It owns selection and paired
research semantics only.  Official outcome acquisition and cell settlement are
delegated to the existing Enterprise Measurement V3 adapters.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

try:
    from scripts import enterprise_judgment_reconstruction as reconstruction
    from scripts import enterprise_judgment_real_mechanism_training as mechanism_training
    from scripts import enterprise_judgment_round6_transfer_utility as round6
    from scripts import enterprise_judgment_source_packet as source_packet
    from scripts import enterprise_judgment_training_control_plane as enterprise_control
    from scripts import judgment_decision_utility as decision_utility
    from scripts import judgment_training_decision_contract as decision_contract
    from scripts import outcome_measurement_acquisition as measurement_acquisition
    from scripts import outcome_measurement_settlement_adapter as settlement_adapter
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_reconstruction as reconstruction
    import enterprise_judgment_real_mechanism_training as mechanism_training
    import enterprise_judgment_round6_transfer_utility as round6
    import enterprise_judgment_source_packet as source_packet
    import enterprise_judgment_training_control_plane as enterprise_control
    import judgment_decision_utility as decision_utility
    import judgment_training_decision_contract as decision_contract
    import outcome_measurement_acquisition as measurement_acquisition
    import outcome_measurement_settlement_adapter as settlement_adapter


PREOUTCOME_SCHEMA_VERSION = "enterprise-judgment-round7-multidimensional-preoutcome.v1"
REVIEW_SCHEMA_VERSION = "enterprise-judgment-round7-multidimensional-review.v1"
COMPLETION_SCHEMA_VERSION = "enterprise-judgment-round7-multidimensional-completion.v1"
SELECTION_POLICY = "EARLIEST_UNCONSUMED_IMMUTABLE_COMPANY_CUTOFF_TRANSITION"
BASELINE_METHOD_ID = "METHOD:CONSOLIDATED_TREND_AND_MANAGEMENT_NARRATIVE:V1"
ENHANCED_METHOD_ID = "METHOD:CUMULATIVE_ENTERPRISE_JUDGMENT_CHAIN:V1"
PREOUTCOME_OUTPUTS = [
    "MULTIDIMENSIONAL_PAIRED_PREOUTCOME_RESEARCH",
    "OUTCOME_CUSTODY_REQUEST",
    "RESEARCH_AGENDA",
]
REVIEW_OUTPUTS = ["MULTIDIMENSIONAL_DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"]
COMPLETION_OUTPUTS = ["ROUND7_REAL_MULTIDIMENSIONAL_FEEDBACK_COMPLETED", "RESEARCH_AGENDA"]
RIGHTS = {
    "directional_learning": "NOT_AUTHORIZED",
    "enterprise_learning": "NOT_AUTHORIZED",
    "comparative": "NOT_AUTHORIZED",
    "method_transfer": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}
MEASUREMENT_RIGHTS = {
    key: value for key, value in RIGHTS.items() if key != "method_transfer"
}
JUDGMENT_DIMENSIONS = [
    "INITIAL_CONDITIONS",
    "IMPLEMENTED_MANAGEMENT_ACTION",
    "EXECUTION",
    "CUSTOMER_COMPETITION_RESPONSE",
    "UNIT_ECONOMICS",
    "WORKING_CAPITAL_CASH_CAPITAL",
    "ADAPTATION_PERMANENT_LOSS",
    "STRONGEST_ALTERNATIVE_EXPLANATION",
]
CONSUMPTION_FILES = [
    *round6.ROUND6_PRIOR_RECEIPT_FILES,
    "36_round5_real_feedback_completion_receipt.json",
    "44_round6_completion_receipt.json",
]

_PREOUTCOME_KEYS = {
    "schema_version", "package_id", "selection", "source_packet_receipt",
    "decision_contract", "shared_cutoff_facts", "baseline_view", "enhanced_view",
    "decision_utility_pairing", "outcome_measurement_contract", "strongest_rival",
    "contamination_boundary", "freeze_state", "frozen_at", "roles", "rights",
    "allowed_outputs",
}
_SELECTION_KEYS = {
    "selection_policy", "source_roster_ref", "consumed_transition_ids",
    "selected_rank", "transition_id", "company_id", "company_cluster_id",
    "cutoff_at", "next_cutoff_at", "selection_used_outcome",
    "selection_used_source_convenience",
}
_FACT_KEYS = {"fact_id", "dimension", "statement", "evidence_refs"}
_VIEW_KEYS = {
    "method_id", "evidence_budget_id", "source_packet_refs", "fact_ids",
    "enterprise_thesis", "judgment_cells", "interpretation_rule",
    "expected_outcome_cell_ids", "prohibited_inferences",
}
_JUDGMENT_KEYS = {
    "judgment_id", "dimension", "question", "cutoff_assessment", "state",
    "evidence_refs", "dependent_outcome_cell_ids", "causal_credit",
    "next_discriminating_evidence", "claim_scope", "responsibility_boundary_ref",
}
CLAIM_SCOPES = {
    "INITIAL_CONDITIONS": "ISSUER_AND_ARENA_CONTEXT",
    "IMPLEMENTED_MANAGEMENT_ACTION": "ISSUER_IMPLEMENTED_ACTION",
    "EXECUTION": "ISSUER_EXECUTION",
    "CUSTOMER_COMPETITION_RESPONSE": "CUSTOMER_AND_COMPETITION_RESPONSE",
    "UNIT_ECONOMICS": "ISSUER_UNIT_ECONOMICS",
    "WORKING_CAPITAL_CASH_CAPITAL": "ISSUER_CASH_CAPITAL_NOT_OWNER_CASH",
    "ADAPTATION_PERMANENT_LOSS": "ISSUER_ADAPTATION_AND_ORDINARY_SHARE_LOSS_BOUNDARY",
    "STRONGEST_ALTERNATIVE_EXPLANATION": "CAUSAL_RIVAL_EXPLANATION",
}
_REVIEW_KEYS = {
    "schema_version", "review_id", "package_ref", "settlement_ref", "reviewer_id",
    "reviewed_at", "dimension_findings", "overall_verdict", "investor_effect",
    "unknowns_preserved", "limitations", "rights", "object_class", "claim_class",
    "allowed_outputs",
}
_DIMENSION_FINDING_KEYS = {
    "dimension", "baseline_assessment", "enhanced_assessment", "utility_verdict",
    "economic_effect", "supporting_cell_ids", "prohibited_inference",
}
_COMPLETION_KEYS = {
    "schema_version", "completion_id", "package_ref", "settlement_ref", "review_ref",
    "company_id", "cutoff_at", "status", "investor_summary", "proved", "not_proved",
    "next_research_action", "rights", "object_class", "claim_class", "allowed_outputs",
}
_ROLES_KEYS = {"judgment_owner_id", "independent_challenger_id", "outcome_custodian_id"}
_FORBIDDEN_KEYS = {
    "price", "market_price", "share_price", "stock_price", "return", "valuation",
    "buyband", "buy_band", "portfolio_action", "position", "investment_action",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _closed(value: Any, keys: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(path + "_must_be_object")
    for key in sorted(set(item).difference(keys)):
        findings.append(f"{path}_contains_unapproved_field:{key}")
    for key in sorted(keys.difference(item)):
        findings.append(f"{path}_missing_required_field:{key}")
    return item


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        findings.append(path + "_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        findings.append(path + "_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        findings.append(path + "_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _forbidden_paths(value: Any, path: str = "round7") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child = f"{path}.{key}"
            lowered = str(key).lower()
            if lowered == "rights":
                continue
            if lowered in _FORBIDDEN_KEYS or lowered.endswith("_price") or lowered.endswith("_return"):
                paths.append(child)
            else:
                paths.extend(_forbidden_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _transition_for_artifact(artifact: dict[str, Any], roster: list[dict[str, Any]]) -> str:
    supersedes = _mapping(artifact.get("supersedes"))
    if _text(supersedes.get("transition_id")):
        return str(supersedes["transition_id"])
    selection = _mapping(artifact.get("selection"))
    if _text(selection.get("transition_id")):
        return str(selection["transition_id"])
    company_id = artifact.get("company_id")
    cutoff_at = artifact.get("cutoff_at")
    matching = [
        row for row in roster
        if row.get("company_id") == company_id and row.get("cutoff_at") == cutoff_at
    ]
    return str(matching[0].get("transition_id") or "") if len(matching) == 1 else ""


def derive_round7_target(
    block: Any,
    roster_freeze: Any,
    consumption_artifacts: list[Any],
) -> dict[str, Any]:
    """Choose the earliest immutable roster row not proven consumed by a formal artifact."""
    findings: list[str] = []
    block_item = _mapping(block)
    freeze = _mapping(roster_freeze)
    roster = [_mapping(row) for row in _items(block_item.get("company_cutoff_transition_roster"))]
    transition_ids = [row.get("transition_id") for row in roster]
    if block_item.get("block_id") != freeze.get("block_id"):
        findings.append("round7_selection.block_must_match_roster_freeze")
    if transition_ids != _items(freeze.get("company_cutoff_transition_ids")):
        findings.append("round7_selection.roster_must_match_immutable_freeze")
    if [row.get("rank") for row in roster] != list(range(1, len(roster) + 1)):
        findings.append("round7_selection.roster_ranks_must_be_contiguous")

    allowed_schemas = round6._PRIOR_RECEIPT_SCHEMAS | {
        "enterprise-judgment-round5-real-feedback-completion-receipt.v1",
        round6.COMPLETION_SCHEMA_VERSION,
    }
    consumed: set[str] = set()
    for index, raw in enumerate(consumption_artifacts):
        artifact = _mapping(raw)
        if artifact.get("schema_version") not in allowed_schemas:
            findings.append(f"round7_selection.consumption_artifacts[{index}].schema_invalid")
            continue
        transition_id = _transition_for_artifact(artifact, roster)
        if transition_id not in set(transition_ids):
            findings.append(f"round7_selection.consumption_artifacts[{index}].transition_binding_invalid")
        else:
            consumed.add(transition_id)

    selected = next((row for row in roster if row.get("transition_id") not in consumed), None)
    if selected is None:
        findings.append("round7_selection.no_unconsumed_row")
    selection = None
    if not findings and selected is not None:
        selection = {
            "selection_policy": SELECTION_POLICY,
            "source_roster_ref": freeze.get("freeze_id"),
            "consumed_transition_ids": sorted(consumed),
            "selected_rank": selected.get("rank"),
            "transition_id": selected.get("transition_id"),
            "company_id": selected.get("company_id"),
            "company_cluster_id": selected.get("company_cluster_id"),
            "cutoff_at": selected.get("cutoff_at"),
            "next_cutoff_at": selected.get("next_cutoff_at"),
            "selection_used_outcome": False,
            "selection_used_source_convenience": False,
        }
    return {"valid": not findings, "findings": findings, "selection": selection}


def _validate_view(
    value: Any,
    *,
    path: str,
    method_id: str,
    facts: list[dict[str, Any]],
    source_ids: set[str],
    cell_ids: set[str],
    evidence_budget: dict[str, Any],
    require_cumulative_chain: bool,
    findings: list[str],
) -> dict[str, Any]:
    view = _closed(value, _VIEW_KEYS, path, findings)
    if view.get("method_id") != method_id:
        findings.append(path + ".method_id_invalid")
    if view.get("evidence_budget_id") != evidence_budget.get("evidence_budget_id"):
        findings.append(path + ".evidence_budget_must_match")
    if view.get("source_packet_refs") != evidence_budget.get("source_packet_refs"):
        findings.append(path + ".source_packet_refs_must_match")
    fact_ids = [fact.get("fact_id") for fact in facts]
    if view.get("fact_ids") != fact_ids:
        findings.append(path + ".must_use_all_shared_facts_in_frozen_order")
    if not _text(view.get("enterprise_thesis")) or not _text(view.get("interpretation_rule")):
        findings.append(path + ".thesis_and_interpretation_required")
    if set(_items(view.get("expected_outcome_cell_ids"))) != cell_ids:
        findings.append(path + ".must_cover_all_frozen_outcome_cells")
    if not _items(view.get("prohibited_inferences")):
        findings.append(path + ".prohibited_inferences_required")

    judgments = [
        _closed(raw, _JUDGMENT_KEYS, f"{path}.judgment_cells[{index}]", findings)
        for index, raw in enumerate(_items(view.get("judgment_cells")))
    ]
    seen_ids: set[str] = set()
    seen_dimensions: list[str] = []
    for index, judgment in enumerate(judgments):
        item_path = f"{path}.judgment_cells[{index}]"
        judgment_id = judgment.get("judgment_id")
        if not _text(judgment_id) or judgment_id in seen_ids:
            findings.append(item_path + ".judgment_id_invalid_or_duplicate")
        seen_ids.add(str(judgment_id))
        dimension = judgment.get("dimension")
        if dimension not in JUDGMENT_DIMENSIONS:
            findings.append(item_path + ".dimension_invalid")
        else:
            seen_dimensions.append(str(dimension))
        expected_scope = CLAIM_SCOPES.get(str(dimension))
        if judgment.get("claim_scope") != expected_scope:
            findings.append(item_path + ".claim_scope_invalid")
        if not _text(judgment.get("responsibility_boundary_ref")):
            findings.append(item_path + ".responsibility_boundary_ref_required")
        if judgment.get("state") not in {"OBSERVED", "INFERRED", "UNKNOWN", "MIXED"}:
            findings.append(item_path + ".state_invalid")
        if judgment.get("causal_credit") not in {"NONE", "PARTIAL_CANDIDATE", "UNKNOWN"}:
            findings.append(item_path + ".causal_credit_invalid")
        if dimension in {
            "CUSTOMER_COMPETITION_RESPONSE", "WORKING_CAPITAL_CASH_CAPITAL",
            "ADAPTATION_PERMANENT_LOSS", "STRONGEST_ALTERNATIVE_EXPLANATION",
        } and judgment.get("causal_credit") == "PARTIAL_CANDIDATE":
            findings.append(item_path + ".scope_cannot_receive_aggregate_causal_credit")
        for field in ("question", "cutoff_assessment", "next_discriminating_evidence"):
            if not _text(judgment.get(field)):
                findings.append(f"{item_path}.{field}_required")
        if any(ref not in source_ids for ref in _items(judgment.get("evidence_refs"))):
            findings.append(item_path + ".evidence_ref_outside_packet")
        if any(cell_id not in cell_ids for cell_id in _items(judgment.get("dependent_outcome_cell_ids"))):
            findings.append(item_path + ".dependent_outcome_cell_invalid")
    if require_cumulative_chain and seen_dimensions != JUDGMENT_DIMENSIONS:
        findings.append(path + ".must_cover_full_cumulative_chain_once_in_order")
    elif set(seen_dimensions) != set(JUDGMENT_DIMENSIONS):
        findings.append(path + ".must_cover_each_enterprise_dimension")
    return view


def validate_preoutcome_package(
    package: Any,
    *,
    block: Any,
    roster_freeze: Any,
    consumption_artifacts: list[Any],
) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(package, _PREOUTCOME_KEYS, "round7_preoutcome", findings)
    if item.get("schema_version") != PREOUTCOME_SCHEMA_VERSION:
        findings.append("round7_preoutcome.schema_version_invalid")
    if item.get("freeze_state") != "PRE_OUTCOME_FROZEN":
        findings.append("round7_preoutcome.freeze_state_invalid")
    frozen_at = _instant(item.get("frozen_at"), "round7_preoutcome.frozen_at", findings)

    derived = derive_round7_target(block, roster_freeze, consumption_artifacts)
    findings.extend("selection:" + finding for finding in derived["findings"])
    selection = _closed(item.get("selection"), _SELECTION_KEYS, "round7_preoutcome.selection", findings)
    if derived["selection"] is not None and selection != derived["selection"]:
        findings.append("round7_preoutcome.selection_must_be_mechanically_derived")

    source_result = source_packet.validate_source_packet_receipt(item.get("source_packet_receipt"))
    findings.extend("source_packet:" + finding for finding in source_result["findings"])
    contract_result = decision_contract.validate_training_decision_contract(item.get("decision_contract"))
    findings.extend("decision_contract:" + finding for finding in contract_result["findings"])
    utility_result = decision_utility.validate_decision_utility_pairing(
        item.get("decision_utility_pairing"), contract=item.get("decision_contract"),
    )
    findings.extend("decision_utility:" + finding for finding in utility_result["findings"])
    measurement_result = mechanism_training.validate_outcome_measurement_contract(
        item.get("outcome_measurement_contract")
    )
    findings.extend("measurement_contract:" + finding for finding in measurement_result["findings"])

    source_receipt = _mapping(item.get("source_packet_receipt"))
    decision = _mapping(item.get("decision_contract"))
    measurement = _mapping(item.get("outcome_measurement_contract"))
    for name, component in (
        ("source_packet", source_receipt),
        ("decision_contract", decision),
        ("measurement_contract", measurement),
    ):
        if component.get("company_id") != selection.get("company_id"):
            findings.append(f"round7_preoutcome.{name}.company_must_match_selection")
        if component.get("cutoff_at") != selection.get("cutoff_at"):
            findings.append(f"round7_preoutcome.{name}.cutoff_must_match_selection")
    if measurement.get("package_ref") != item.get("package_id"):
        findings.append("round7_preoutcome.measurement_contract.package_ref_must_match")
    if frozen_at is not None and measurement.get("contract_frozen_at") != frozen_at.isoformat():
        findings.append("round7_preoutcome.measurement_contract.freeze_time_must_match")

    roles = _closed(item.get("roles"), _ROLES_KEYS, "round7_preoutcome.roles", findings)
    if roles != decision.get("roles") or len(set(roles.values())) != len(_ROLES_KEYS):
        findings.append("round7_preoutcome.roles_must_match_and_remain_separate")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != PREOUTCOME_OUTPUTS:
        findings.append("round7_preoutcome.rights_or_outputs_invalid")
    if not _text(item.get("strongest_rival")):
        findings.append("round7_preoutcome.strongest_rival_required")
    contamination = _mapping(item.get("contamination_boundary"))
    if contamination != {
        "historical_replay_status": "MODEL_MEMORY_MITIGATED",
        "repository_contains_later_summary": True,
        "score_authority": "NONE",
        "allowed_use": "DEVELOPMENT_MULTIDIMENSIONAL_UTILITY_ONLY",
    }:
        findings.append("round7_preoutcome.contamination_boundary_invalid")

    facts = [
        _closed(raw, _FACT_KEYS, f"round7_preoutcome.shared_cutoff_facts[{index}]", findings)
        for index, raw in enumerate(_items(item.get("shared_cutoff_facts")))
    ]
    source_ids = {str(source.get("source_id")) for source in _items(source_receipt.get("sources"))}
    fact_ids: set[str] = set()
    for index, fact in enumerate(facts):
        fact_id = fact.get("fact_id")
        if not _text(fact_id) or fact_id in fact_ids:
            findings.append(f"round7_preoutcome.shared_cutoff_facts[{index}].id_invalid_or_duplicate")
        fact_ids.add(str(fact_id))
        if fact.get("dimension") not in JUDGMENT_DIMENSIONS:
            findings.append(f"round7_preoutcome.shared_cutoff_facts[{index}].dimension_invalid")
        if not _text(fact.get("statement")) or not _items(fact.get("evidence_refs")):
            findings.append(f"round7_preoutcome.shared_cutoff_facts[{index}].statement_and_evidence_required")
        if any(ref not in source_ids for ref in _items(fact.get("evidence_refs"))):
            findings.append(f"round7_preoutcome.shared_cutoff_facts[{index}].evidence_outside_packet")

    cell_ids = {str(cell.get("cell_id")) for cell in _items(measurement.get("atomic_cells"))}
    budget = _mapping(decision.get("evidence_budget"))
    baseline = _validate_view(
        item.get("baseline_view"), path="round7_preoutcome.baseline_view",
        method_id=BASELINE_METHOD_ID, facts=facts, source_ids=source_ids,
        cell_ids=cell_ids, evidence_budget=budget, require_cumulative_chain=False,
        findings=findings,
    )
    enhanced = _validate_view(
        item.get("enhanced_view"), path="round7_preoutcome.enhanced_view",
        method_id=ENHANCED_METHOD_ID, facts=facts, source_ids=source_ids,
        cell_ids=cell_ids, evidence_budget=budget, require_cumulative_chain=True,
        findings=findings,
    )
    pairing = _mapping(item.get("decision_utility_pairing"))
    if _mapping(pairing.get("baseline")).get("method_id") != baseline.get("method_id"):
        findings.append("round7_preoutcome.baseline_method_must_match_pairing")
    if _mapping(pairing.get("enhanced")).get("method_id") != enhanced.get("method_id"):
        findings.append("round7_preoutcome.enhanced_method_must_match_pairing")
    if _forbidden_paths(item):
        findings.extend("round7_preoutcome.forbidden_field:" + path for path in _forbidden_paths(item))
    return {"valid": not findings, "findings": findings, "package": deepcopy(item) if not findings else None}


def _event_clock() -> dict[str, Any]:
    return {
        "clock_kind": "EVENT_WINDOW",
        "event_window": {
            "event_start": "2014-04-17",
            "event_end": "2014-12-31",
            "window_name": "POST_CUTOFF_FY2014_EVENT_WINDOW",
        },
    }


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


def _boundary(scope: str) -> dict[str, str]:
    return {
        "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:600585",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "arena_id": "ARENA:CN:CEMENT:MULTI_REGION_DELIVERED_MARKET",
        "scope_requirement": scope,
    }


def _raw(
    field_id: str,
    role: str,
    unit: str,
    clock: dict[str, Any],
    table: str,
    line: str,
) -> dict[str, Any]:
    clock_value = _mapping(clock.get("flow_period") or clock.get("balance_as_of") or clock.get("event_window"))
    period_column = (
        f"{clock_value.get('event_start')}..{clock_value.get('event_end')}"
        if clock.get("clock_kind") == "EVENT_WINDOW"
        else str(clock_value.get("fiscal_period"))
    )
    return {
        "field_id": field_id,
        "role": role,
        "unit": unit,
        "measurement_clock": deepcopy(clock),
        "locator": {"table_or_note": table, "line_item": line, "period_column": period_column},
    }


def _conversion(raw: dict[str, Any], to_unit: str | None = None) -> dict[str, str]:
    return {
        "field_id": raw["field_id"],
        "from_unit": raw["unit"],
        "to_unit": to_unit or raw["unit"],
        "scale": "1",
    }


def _cell_base(
    *,
    cell_id: str,
    thread_id: str,
    layer: str,
    clock: dict[str, Any],
    boundary_scope: str,
    field_identity: dict[str, Any],
    unit: dict[str, str],
    raw_fields: list[dict[str, Any]],
    formula: dict[str, Any],
    label_rule: dict[str, Any],
    prohibited: str,
) -> dict[str, Any]:
    return {
        "cell_id": cell_id,
        "thread_id": thread_id,
        "layer": layer,
        "outcome_period": {
            "period_start": "2014-04-17T00:00:00+08:00",
            "period_end": "2014-12-31T23:59:59+08:00",
            "fiscal_period": "FY2014",
        },
        "measurement_clock": deepcopy(clock),
        "responsibility_boundary": _boundary(boundary_scope),
        "field_identity": field_identity,
        "unit": unit,
        "raw_input_fields": raw_fields,
        "formula": formula,
        "label_rule": label_rule,
        "conflict_rule": {
            "multiple_values": "MEASUREMENT_MISMATCH",
            "boundary_conflict": "MEASUREMENT_MISMATCH",
            "period_conflict": "MEASUREMENT_MISMATCH",
        },
        "unknown_rule": {"conditions": ["one or more contracted raw fields absent"], "label": "UNKNOWN"},
        "mismatch_rule": {
            "conditions": ["scope, period, unit or unique-field conflict"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        },
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": prohibited,
    }


def _event_cell(cell_id: str, layer: str, line: str, prohibited: str) -> dict[str, Any]:
    clock = _event_clock()
    suffix = cell_id.rsplit(":", 1)[-1]
    field_id = f"FIELD:600585:FY2014:{suffix}_EVENT"
    table = "FY2014 management discussion, project delivery or material investment disclosure"
    raw = _raw(field_id, "EVENT", "BOOLEAN_EVENT", clock, table, line)
    return _cell_base(
        cell_id=cell_id,
        thread_id="THREAD:600585:ACTION_EXECUTION_ADAPTATION",
        layer=layer,
        clock=clock,
        boundary_scope="issuer-specific implemented action and execution milestone; narrative plans are insufficient",
        field_identity={
            "outcome_field_id": field_id,
            "baseline_field_id": "",
            "statement_scope": "ISSUER_IMPLEMENTED_ACTION_EVENT",
            "table_or_note": table,
            "line_item": line,
            "field_kind": "DISCLOSED_EVENT",
        },
        unit={"kind": "EVENT", "currency": "NOT_APPLICABLE", "scale": "BOOLEAN"},
        raw_fields=[raw],
        formula={
            "operator": "EVENT_BOOLEAN",
            "input_field_ids": [field_id],
            "expression": f"explicit_event({field_id})",
            "unit_conversions": [_conversion(raw)],
            "zero_baseline_rule": "NOT_APPLICABLE",
        },
        label_rule={
            "type": "EVENT_PRESENCE",
            "decrease_lte": 0,
            "increase_gte": 1,
            "ordered_labels": ["MEASUREMENT_MISMATCH", "OBSERVED_YES", "OBSERVED_NO", "UNKNOWN"],
        },
        prohibited=prohibited,
    )


def _change_cell(
    cell_id: str,
    layer: str,
    table: str,
    line: str,
    unit: str,
    *,
    balance: bool = False,
    operator: str = "PERCENT_CHANGE",
    decrease_lte: float = -0.05,
    increase_gte: float = 0.05,
    prohibited: str,
) -> dict[str, Any]:
    suffix = cell_id.rsplit(":", 1)[-1]
    baseline_clock = _balance_clock(2013) if balance else _flow_clock(2013)
    outcome_clock = _balance_clock(2014) if balance else _flow_clock(2014)
    baseline_id = f"FIELD:600585:FY2013:{suffix}"
    outcome_id = f"FIELD:600585:FY2014:{suffix}"
    baseline = _raw(baseline_id, "BASELINE", unit, baseline_clock, table, line)
    outcome = _raw(outcome_id, "OUTCOME", unit, outcome_clock, table, line)
    expression = "outcome - baseline" if operator == "DIFFERENCE" else "(outcome - baseline) / abs(baseline)"
    return _cell_base(
        cell_id=cell_id,
        thread_id="THREAD:600585:ENTERPRISE_STATE_TRANSMISSION",
        layer=layer,
        clock=outcome_clock,
        boundary_scope="issuer-consolidated same-definition field; causal attribution prohibited",
        field_identity={
            "outcome_field_id": outcome_id,
            "baseline_field_id": baseline_id,
            "statement_scope": "CONSOLIDATED",
            "table_or_note": table,
            "line_item": line,
            "field_kind": "AUDITED_OR_OPERATING_LINE_ITEM",
        },
        unit={
            "kind": "ABSOLUTE_CHANGE" if operator == "DIFFERENCE" else "PERCENT_CHANGE",
            "currency": "RMB" if unit == "RMB" else "NOT_APPLICABLE",
            "scale": "1",
        },
        raw_fields=[baseline, outcome],
        formula={
            "operator": operator,
            "input_field_ids": [baseline_id, outcome_id],
            "expression": expression,
            "unit_conversions": [_conversion(baseline), _conversion(outcome)],
            "zero_baseline_rule": "NOT_APPLICABLE" if operator == "DIFFERENCE" else "RETURN_MEASUREMENT_MISMATCH",
        },
        label_rule={
            "type": "ABSOLUTE_CHANGE_BAND" if operator == "DIFFERENCE" else "PERCENT_CHANGE_BAND",
            "decrease_lte": decrease_lte,
            "increase_gte": increase_gte,
            "ordered_labels": [
                "MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE",
                "OBSERVED_INCREASE", "UNKNOWN",
            ],
        },
        prohibited=prohibited,
    )


def _ratio_change_cell(
    cell_id: str,
    layer: str,
    numerator_table: str,
    numerator_line: str,
    numerator_unit: str,
    denominator_table: str,
    denominator_line: str,
    denominator_unit: str,
    *,
    prohibited: str,
) -> dict[str, Any]:
    suffix = cell_id.rsplit(":", 1)[-1]
    combined_table = f"{numerator_table} / {denominator_table}"
    combined_line = f"{numerator_line} divided by {denominator_line}"
    raw_fields: list[dict[str, Any]] = []
    for year, role in ((2013, "BASELINE"), (2014, "OUTCOME")):
        clock = _flow_clock(year)
        raw_fields.extend([
            _raw(
                f"FIELD:600585:FY{year}:{suffix}_NUMERATOR", role, numerator_unit,
                clock, combined_table, combined_line,
            ),
            _raw(
                f"FIELD:600585:FY{year}:{suffix}_DENOMINATOR", role, denominator_unit,
                clock, combined_table, combined_line,
            ),
        ])
    input_ids = [raw["field_id"] for raw in raw_fields]
    return _cell_base(
        cell_id=cell_id,
        thread_id="THREAD:600585:ENTERPRISE_STATE_TRANSMISSION",
        layer=layer,
        clock=_flow_clock(2014),
        boundary_scope="issuer-consolidated ratio assembled from same-period, same-boundary raw fields",
        field_identity={
            "outcome_field_id": input_ids[2],
            "baseline_field_id": input_ids[0],
            "statement_scope": "CONSOLIDATED_DERIVED_RATIO",
            "table_or_note": combined_table,
            "line_item": combined_line,
            "field_kind": "DERIVED_RATIO_FROM_FROZEN_RAW_FIELDS",
        },
        unit={"kind": "RATIO_CHANGE", "currency": "NOT_APPLICABLE", "scale": "1"},
        raw_fields=raw_fields,
        formula={
            "operator": "RATIO_CHANGE",
            "input_field_ids": input_ids,
            "expression": "((outcome_numerator/outcome_denominator)-(baseline_numerator/baseline_denominator))/abs(baseline_ratio)",
            "unit_conversions": [_conversion(raw) for raw in raw_fields],
            "zero_baseline_rule": "RETURN_MEASUREMENT_MISMATCH",
        },
        label_rule={
            "type": "PERCENT_CHANGE_BAND",
            "decrease_lte": -0.05,
            "increase_gte": 0.05,
            "ordered_labels": [
                "MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE",
                "OBSERVED_INCREASE", "UNKNOWN",
            ],
        },
        prohibited=prohibited,
    )


def _same_period_difference_cell(
    cell_id: str,
    layer: str,
    first_table: str,
    first_line: str,
    second_table: str,
    second_line: str,
    unit: str,
    *,
    decrease_lte: float,
    increase_gte: float,
    prohibited: str,
) -> dict[str, Any]:
    suffix = cell_id.rsplit(":", 1)[-1]
    clock = _flow_clock(2014)
    combined_table = f"{first_table} / {second_table}"
    combined_line = f"{second_line} minus {first_line}"
    first = _raw(f"FIELD:600585:FY2014:{suffix}_FIRST", "BASELINE", unit, clock, combined_table, combined_line)
    second = _raw(f"FIELD:600585:FY2014:{suffix}_SECOND", "OUTCOME", unit, clock, combined_table, combined_line)
    return _cell_base(
        cell_id=cell_id,
        thread_id="THREAD:600585:MARKET_CONTEXT",
        layer=layer,
        clock=clock,
        boundary_scope="industry context and issuer state are compared descriptively, never as a causal control",
        field_identity={
            "outcome_field_id": second["field_id"],
            "baseline_field_id": first["field_id"],
            "statement_scope": "ISSUER_VERSUS_INDUSTRY_CONTEXT",
            "table_or_note": combined_table,
            "line_item": combined_line,
            "field_kind": "CONTEXTUAL_SPREAD",
        },
        unit={"kind": "ABSOLUTE_CHANGE", "currency": "NOT_APPLICABLE", "scale": "1"},
        raw_fields=[first, second],
        formula={
            "operator": "DIFFERENCE",
            "input_field_ids": [first["field_id"], second["field_id"]],
            "expression": "issuer_growth - industry_growth",
            "unit_conversions": [_conversion(first), _conversion(second)],
            "zero_baseline_rule": "NOT_APPLICABLE",
        },
        label_rule={
            "type": "ABSOLUTE_CHANGE_BAND",
            "decrease_lte": decrease_lte,
            "increase_gte": increase_gte,
            "ordered_labels": [
                "MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE",
                "OBSERVED_INCREASE", "UNKNOWN",
            ],
        },
        prohibited=prohibited,
    )


def _build_measurement_contract(package_id: str, frozen_at: str) -> dict[str, Any]:
    prefix = "CELL:600585:20140416:"
    cells = [
        _same_period_difference_cell(
            prefix + "ISSUER_VS_INDUSTRY_VOLUME_SPREAD",
            "SALES_VOLUME",
            "FY2014 macro and industry review", "national cement output growth rate",
            "FY2014 operating review", "issuer cement and clinker net sales volume growth rate",
            "RATIO", decrease_lte=-0.02, increase_gte=0.02,
            prohibited="A positive spread is not a peer-controlled market-share or moat result.",
        ),
        _event_cell(
            prefix + "IMPLEMENTED_ACTION_EVENT", "IMPLEMENTED",
            "explicit post-cutoff implementation of a capacity, acquisition, market, procurement, digital or environmental action",
            "Management narrative or a future plan is not implemented action evidence.",
        ),
        _event_cell(
            prefix + "NAMED_PLAN_MILESTONE_DELIVERED", "EXECUTED",
            "explicit post-cutoff delivery of a project or operating milestone named in the FY2013 forward plan",
            "One delivered milestone is not proof that the full plan or management team succeeded.",
        ),
        _event_cell(
            prefix + "DIRECT_CUSTOMER_RESPONSE", "CUSTOMER_RESPONSE",
            "direct customer retention, order quality, market-share, price acceptance or channel response evidence",
            "Aggregate sales volume or management assertions cannot substitute for direct customer response.",
        ),
        _change_cell(
            prefix + "CEMENT_CLINKER_SALES_VOLUME", "SALES_VOLUME",
            "production-sales-inventory analysis", "cement and clinker net sales volume", "TONNE",
            prohibited="Volume growth may come from new capacity or acquisition and is not standalone execution quality.",
        ),
        _change_cell(
            prefix + "SALES_VOLUME_PLAN_DELIVERY", "SALES_VOLUME",
            "production-sales-inventory analysis", "cement and clinker net sales volume", "TONNE",
            operator="DIFFERENCE", decrease_lte=0, increase_gte=28_000_000,
            prohibited="Meeting an aggregate volume plan does not prove organic demand, pricing power or value creation.",
        ),
        _ratio_change_cell(
            prefix + "REALIZED_REVENUE_PER_TONNE", "PRICE",
            "principal business by product", "cement and clinker principal business revenue", "RMB",
            "production-sales-inventory analysis", "cement and clinker net sales volume", "TONNE",
            prohibited="Revenue per tonne is a price-mix realization proxy, not direct customer loyalty or moat evidence.",
        ),
        _change_cell(
            prefix + "COMBINED_UNIT_COST", "UNIT_COST",
            "cement and clinker combined cost analysis", "cement and clinker combined unit cost", "RMB_PER_TONNE",
            prohibited="Unit-cost direction must be separated from coal-price movement, mix and perimeter change.",
        ),
        _change_cell(
            prefix + "COMBINED_GROSS_MARGIN", "GROSS_MARGIN",
            "principal business by product", "cement and clinker combined gross margin", "RATIO",
            operator="DIFFERENCE", decrease_lte=-0.02, increase_gte=0.02,
            prohibited="Gross-margin movement is not management effect without price, fuel, mix and scope attribution.",
        ),
        _change_cell(
            prefix + "ACCOUNTS_RECEIVABLE", "WORKING_CAPITAL",
            "consolidated balance sheet", "accounts receivable", "RMB", balance=True,
            prohibited="Receivables direction is a collection-intensity diagnostic, not direct customer quality.",
        ),
        _change_cell(
            prefix + "INVENTORY", "WORKING_CAPITAL",
            "consolidated balance sheet", "inventory", "RMB", balance=True,
            prohibited="Inventory direction cannot identify demand, production discipline or loss causally on its own.",
        ),
        _change_cell(
            prefix + "OPERATING_CASH", "CASH",
            "consolidated cash-flow statement", "net cash flows from operating activities", "RMB",
            prohibited="Operating cash is not owner cash and may include working-capital timing.",
        ),
        _change_cell(
            prefix + "CASH_CAPEX", "CAPITAL_BURDEN",
            "consolidated cash-flow statement", "cash paid to acquire and construct fixed assets, intangible assets and other long-term assets", "RMB",
            prohibited="Cash capex combines maintenance and growth and cannot be treated as destruction or owner cash by itself.",
        ),
        _ratio_change_cell(
            prefix + "OCF_TO_CASH_CAPEX", "CASH",
            "consolidated cash-flow statement", "net cash flows from operating activities", "RMB",
            "consolidated cash-flow statement", "cash paid to acquire and construct fixed assets, intangible assets and other long-term assets", "RMB",
            prohibited="OCF-to-capex is a funding-capacity diagnostic, not distributable owner cash.",
        ),
        _change_cell(
            prefix + "NET_DEBT_RATIO", "FINANCING",
            "liquidity and funding discussion", "net debt ratio", "RATIO",
            balance=True, operator="DIFFERENCE", decrease_lte=-0.03, increase_gte=0.03,
            prohibited="One-year net-debt movement does not prove solvency quality or permanent loss.",
        ),
        _event_cell(
            prefix + "ADAPTATION_ACTION_EVENT", "EXECUTED",
            "explicit post-cutoff change in operating or capital action in response to demand, price, energy cost or environmental regulation",
            "A stated intention or generic risk response is not observed adaptation.",
        ),
        _event_cell(
            prefix + "DIRECT_LOSS_EVENT", "PERMANENT_LOSS",
            "direct issuer-level irreversible capital loss, default, covenant breach or going-concern event",
            "Absence of one disclosed event does not prove permanent-loss risk is absent.",
        ),
    ]
    return {
        "schema_version": "enterprise-outcome-measurement-contract.v3",
        "contract_set_id": "OMC:CN600585:20140416:MULTIDIMENSIONAL:V3",
        "package_ref": package_id,
        "company_id": "CN:600585",
        "cutoff_at": "2014-04-16T00:00:00+08:00",
        "outcome_window": {
            "period_start": "2014-04-17T00:00:00+08:00",
            "period_end": "2014-12-31T23:59:59+08:00",
            "fiscal_period": "FY2014",
            "settlement_due_at": "2015-04-16T00:00:00+08:00",
        },
        "source_access": {
            "source_id": "CNINFO:600585:ANN:20150324:1200733224",
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": "https://static.cninfo.com.cn/finalpage/2015-03-24/1200733224.PDF",
            "published_after_cutoff": True,
            "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
            "custodian_access": "OUTCOME_ONLY",
            "issuer_id": "ISSUER:CN:600585",
            "report_period_end": "2014-12-31",
            "availability_precision": "DATE_ONLY",
            "source_available_at": None,
            "source_available_date": "2015-03-24",
            "authorization_receipt_id": "OAA:CN600585:20140416:FY2014:R7:V1",
        },
        "atomic_cells": cells,
        "thread_combination_rules": [],
        "rights": deepcopy(MEASUREMENT_RIGHTS),
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
        "freeze_state": "PRE_OUTCOME_FROZEN",
        "contract_frozen_at": frozen_at,
        "clock_policy": "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK",
    }


def _judgment(
    method: str,
    dimension: str,
    question: str,
    assessment: str,
    state: str,
    evidence_refs: list[str],
    cells: list[str],
    causal_credit: str,
    next_evidence: str,
) -> dict[str, Any]:
    return {
        "judgment_id": f"JUDGMENT:R7:{method}:{dimension}",
        "dimension": dimension,
        "question": question,
        "cutoff_assessment": assessment,
        "state": state,
        "evidence_refs": evidence_refs,
        "dependent_outcome_cell_ids": cells,
        "causal_credit": causal_credit,
        "next_discriminating_evidence": next_evidence,
        "claim_scope": CLAIM_SCOPES[dimension],
        "responsibility_boundary_ref": (
            "ARENA:CN:CEMENT:MULTI_REGION_DELIVERED_MARKET"
            if dimension in {"INITIAL_CONDITIONS", "CUSTOMER_COMPETITION_RESPONSE", "STRONGEST_ALTERNATIVE_EXPLANATION"}
            else "ISSUER_CONSOLIDATED:CN:600585"
        ),
    }


def build_real_preoutcome_package(
    *,
    block: dict[str, Any],
    roster_freeze: dict[str, Any],
    consumption_artifacts: list[dict[str, Any]],
    frozen_at: str,
) -> dict[str, Any]:
    selection_result = derive_round7_target(block, roster_freeze, consumption_artifacts)
    if not selection_result["valid"]:
        raise ValueError("round7 selection invalid: " + "; ".join(selection_result["findings"]))
    selection = selection_result["selection"]
    package_id = "EJMD:CN:CEMENT:600585:20140416:V1"
    source_id = "CNINFO:600585:ANN:20140325:63719331"
    source_ref = {"receipt_id": "SP:CN600585:20140416:FY2013", "receipt_version": 1}
    roles = {
        "judgment_owner_id": "ROLE:CEMENT:ROUND7:JUDGMENT_OWNER",
        "independent_challenger_id": "ROLE:CEMENT:ROUND7:INDEPENDENT_CHALLENGER",
        "outcome_custodian_id": "ROLE:CEMENT:ROUND7:OUTCOME_CUSTODIAN",
    }
    source_receipt = {
        "schema_version": "enterprise-judgment-source-packet-receipt.v1",
        "packet_id": source_ref["receipt_id"],
        "packet_version": 1,
        "company_id": "CN:600585",
        "issuer_id": "ISSUER:CN:600585",
        "cutoff_at": "2014-04-16T00:00:00+08:00",
        "sources": [{
            "source_id": source_id,
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": "https://static.cninfo.com.cn/finalpage/2014-03-25/63719331.PDF",
            "published_on": "2014-03-25",
            "available_on": "2014-03-25",
            "availability_timezone": "Asia/Shanghai",
            "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": ["ISSUER_CONSOLIDATED:CN:600585"],
            "responsibility_perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "access_mode": "REMOTE_OFFICIAL_LOCATOR",
            "locators": [
                {"research_question_id": "Q:R7:INITIAL_CONDITIONS", "locator": "FY2013 annual report PDF pp.6,11-13: industry demand, energy-cost exposure, scale, regional sales and product mix."},
                {"research_question_id": "Q:R7:ACTION_EXECUTION", "locator": "FY2013 annual report PDF pp.11-12,19-20: commissioned lines and mills, acquisitions, environmental retrofit, 2014 plan and named projects."},
                {"research_question_id": "Q:R7:UNIT_ECONOMICS", "locator": "FY2013 annual report PDF pp.13-14: product gross margin, combined unit cost and fuel/power cost."},
                {"research_question_id": "Q:R7:CASH_CAPITAL", "locator": "FY2013 annual report PDF pp.15-17 and audited statements: leverage, operating cash, capex and capital commitments."},
            ],
        }],
        "object_class": "SOURCE_PACKET_RECEIPT",
        "claim_class": "CUTOFF_ELIGIBLE_SOURCE_RECEIPT",
        "allowed_outputs": ["SOURCE_PACKET_READ_MODEL", "RESEARCH_AGENDA"],
    }
    decision = {
        "schema_version": "turtle-training-decision-contract.v1",
        "contract_id": "DC:CN600585:20140416:MULTIDIMENSIONAL",
        "contract_version": 1,
        "company_id": "CN:600585",
        "issuer_id": "ISSUER:CN:600585",
        "cutoff_at": "2014-04-16T00:00:00+08:00",
        "decision_purpose": "HISTORICAL_TRAINING",
        "holding_horizon": {"minimum_years": 1, "maximum_years": 5},
        "permanent_loss_constraints": [{
            "constraint_id": "PLC:600585:VOLUME_MARGIN_CASH_NOT_MANAGEMENT_EFFECT",
            "condition": "Industry demand, coal prices, new capacity and acquisitions can jointly improve reported volume, margin and cash without proving superior management or durable economics.",
            "required_treatment": "Separate initial conditions, implemented action, execution, customer response, unit economics, cash-capital burden and adaptation; preserve causal credit as UNKNOWN unless directly discriminated.",
        }],
        "decision_flip_questions": [
            {"question_id": "DQ:600585:EXTERNAL_VS_INTERNAL", "statement": "How much of the operating improvement survives after separating industry demand, fuel-cost relief, acquisitions and new capacity?", "decision_effect": "Only residual same-boundary evidence can support a stronger enterprise-quality hypothesis."},
            {"question_id": "DQ:600585:CUSTOMER_UNIT_ECONOMICS", "statement": "Did volume growth carry price-mix realization and unit economics rather than merely added capacity?", "decision_effect": "Growth without customer absorption or unit economics cannot establish a durable competitive advantage."},
            {"question_id": "DQ:600585:CASH_CAPITAL", "statement": "Did operating progress fund capex and preserve balance-sheet resilience without relying on working-capital timing?", "decision_effect": "Reported earnings that do not transmit to funding capacity have lower long-term owner value."},
            {"question_id": "DQ:600585:ADAPTATION_LOSS", "statement": "Did management adapt to demand, energy and environmental constraints without creating an irreversible capital-loss path?", "decision_effect": "Adaptation and permanent-loss risk must be assessed separately from one-year performance."},
        ],
        "evidence_budget": {
            "evidence_budget_id": "BUDGET:CN600585:20140416:FY2013",
            "source_packet_refs": [source_ref],
        },
        "price_and_opportunity_cost_policy": "PROHIBITED_FOR_HISTORICAL_TRAINING",
        "outcome_access": "NONE",
        "roles": roles,
        "object_class": "DECISION_CONTRACT",
        "claim_class": "EX_ANTE_DECISION_SCOPE",
        "allowed_outputs": ["CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"],
    }
    facts = [
        {"fact_id": "FACT:R7:INDUSTRY_TAILWIND", "dimension": "INITIAL_CONDITIONS", "statement": "FY2013 national cement output grew 9.6%, new industry investment fell 6.5%, supply-demand conditions improved and lower coal prices reduced industry production cost.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:SCALE_NETWORK", "dimension": "INITIAL_CONDITIONS", "statement": "At FY2013 year-end the issuer reported 195 million tonnes of clinker capacity, 231 million tonnes of cement capacity and a multi-region delivered-market footprint.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:IMPLEMENTED_EXPANSION", "dimension": "IMPLEMENTED_MANAGEMENT_ACTION", "statement": "During FY2013 the issuer commissioned six clinker lines, 21 cement mills and two aggregate projects, acquired two cement companies and added 11.6 million tonnes of clinker and 24.3 million tonnes of cement capacity.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:EXECUTION_OUTPUT", "dimension": "EXECUTION", "statement": "FY2013 cement-and-clinker net sales volume reached 228 million tonnes, up 21.95%, with western-region volume up 40.17% after new and acquired projects entered operation.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:MIX_AND_CUSTOMER_BOUNDARY", "dimension": "CUSTOMER_COMPETITION_RESPONSE", "statement": "The issuer reduced clinker sales mix and raised 42.5-grade cement mix while regional volume rose; the packet does not directly establish customer retention, market share or price acceptance.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:UNIT_ECONOMICS", "dimension": "UNIT_ECONOMICS", "statement": "Combined unit cost fell 8.84% to RMB158.13 per tonne and combined gross margin rose 5.42 points to 33.42%; the issuer attributed cost relief to both lower coal prices and lower coal consumption.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:CASH_AND_CAPITAL", "dimension": "WORKING_CAPITAL_CASH_CAPITAL", "statement": "Operating cash was RMB15.199 billion, disclosed capital expenditure was RMB7.505 billion and committed equipment capital was RMB10.087 billion; maintenance versus growth capital was not separated.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:BALANCE_RESILIENCE", "dimension": "ADAPTATION_PERMANENT_LOSS", "statement": "Borrowings fell to RMB6.667 billion, outstanding bonds were RMB15.5 billion and the disclosed net-debt ratio was 0.27; one year does not establish permanent-loss resilience.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:ADAPTATION_ACTIONS", "dimension": "ADAPTATION_PERMANENT_LOSS", "statement": "The issuer reported regional sales coordination, procurement scale, benchmarking and 77 completed denitration retrofits, while tighter environmental standards were expected to raise operating cost.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R7:STRONGEST_RIVAL", "dimension": "STRONGEST_ALTERNATIVE_EXPLANATION", "statement": "Industry demand growth, lower coal prices, acquisitions and newly commissioned capacity can jointly explain much of the reported growth and margin improvement without requiring superior management quality.", "evidence_refs": [source_id]},
    ]
    measurement = _build_measurement_contract(package_id, frozen_at)
    cell_ids = [cell["cell_id"] for cell in measurement["atomic_cells"]]

    by_suffix = {cell_id.rsplit(":", 1)[-1]: cell_id for cell_id in cell_ids}
    dimension_cells = {
        "INITIAL_CONDITIONS": [by_suffix["ISSUER_VS_INDUSTRY_VOLUME_SPREAD"]],
        "IMPLEMENTED_MANAGEMENT_ACTION": [by_suffix["IMPLEMENTED_ACTION_EVENT"]],
        "EXECUTION": [
            by_suffix["NAMED_PLAN_MILESTONE_DELIVERED"],
            by_suffix["CEMENT_CLINKER_SALES_VOLUME"],
            by_suffix["SALES_VOLUME_PLAN_DELIVERY"],
        ],
        "CUSTOMER_COMPETITION_RESPONSE": [
            by_suffix["DIRECT_CUSTOMER_RESPONSE"],
            by_suffix["REALIZED_REVENUE_PER_TONNE"],
        ],
        "UNIT_ECONOMICS": [
            by_suffix["COMBINED_UNIT_COST"],
            by_suffix["COMBINED_GROSS_MARGIN"],
        ],
        "WORKING_CAPITAL_CASH_CAPITAL": [
            by_suffix["ACCOUNTS_RECEIVABLE"],
            by_suffix["INVENTORY"],
            by_suffix["OPERATING_CASH"],
            by_suffix["CASH_CAPEX"],
            by_suffix["OCF_TO_CASH_CAPEX"],
        ],
        "ADAPTATION_PERMANENT_LOSS": [
            by_suffix["NET_DEBT_RATIO"],
            by_suffix["ADAPTATION_ACTION_EVENT"],
            by_suffix["DIRECT_LOSS_EVENT"],
        ],
        "STRONGEST_ALTERNATIVE_EXPLANATION": [
            by_suffix["ISSUER_VS_INDUSTRY_VOLUME_SPREAD"],
            by_suffix["COMBINED_UNIT_COST"],
            by_suffix["COMBINED_GROSS_MARGIN"],
        ],
    }
    baseline_assessments = {
        "INITIAL_CONDITIONS": ("Large scale and a broad regional footprint coincide with an improving industry backdrop.", "INFERRED", "PARTIAL_CANDIDATE"),
        "IMPLEMENTED_MANAGEMENT_ACTION": ("The management narrative reports expansion, acquisitions, marketing coordination and cost controls as one broad action set.", "OBSERVED", "PARTIAL_CANDIDATE"),
        "EXECUTION": ("Volume, profit and commissioned capacity improved together, suggesting positive aggregate execution.", "INFERRED", "PARTIAL_CANDIDATE"),
        "CUSTOMER_COMPETITION_RESPONSE": ("Regional volume and higher-grade mix are favorable operating signals, while direct customer response is unavailable.", "MIXED", "UNKNOWN"),
        "UNIT_ECONOMICS": ("Lower unit cost and higher gross margin indicate better aggregate economics.", "OBSERVED", "PARTIAL_CANDIDATE"),
        "WORKING_CAPITAL_CASH_CAPITAL": ("Operating cash exceeded disclosed capex and leverage fell, but owner cash is not measured.", "MIXED", "UNKNOWN"),
        "ADAPTATION_PERMANENT_LOSS": ("Environmental retrofit and geographic expansion suggest adaptation; permanent loss remains unknown.", "MIXED", "UNKNOWN"),
        "STRONGEST_ALTERNATIVE_EXPLANATION": ("External demand, coal prices, acquisitions and added capacity may explain a material share of the improvement.", "INFERRED", "NONE"),
    }
    enhanced_assessments = {
        "INITIAL_CONDITIONS": ("Scale, multi-region distribution and balance-sheet capacity are initial advantages, while demand growth and cheaper coal are external tailwinds that must be removed from management credit.", "MIXED", "NONE"),
        "IMPLEMENTED_MANAGEMENT_ACTION": ("Commissioned capacity, completed acquisitions, mix management, procurement and environmental retrofit are separately observed actions; the FY2014 plan is not an action.", "OBSERVED", "PARTIAL_CANDIDATE"),
        "EXECUTION": ("Physical project delivery and volume growth are observed, but acquired and new capacity prevent organic execution from being isolated.", "MIXED", "UNKNOWN"),
        "CUSTOMER_COMPETITION_RESPONSE": ("Regional volume and mix show product absorption, but customer retention, market share and price acceptance remain UNKNOWN.", "MIXED", "NONE"),
        "UNIT_ECONOMICS": ("Unit cost and margin improved, but coal-price relief, fuel efficiency, mix and perimeter contributions cannot yet be separated.", "MIXED", "NONE"),
        "WORKING_CAPITAL_CASH_CAPITAL": ("Operating cash funded disclosed capex in aggregate, but working-capital timing and maintenance-versus-growth capital prevent owner-cash attribution.", "MIXED", "NONE"),
        "ADAPTATION_PERMANENT_LOSS": ("The issuer adapted operations and environmental equipment while retaining funding capacity; persistence and irreversible-loss conditions remain UNKNOWN.", "MIXED", "NONE"),
        "STRONGEST_ALTERNATIVE_EXPLANATION": ("A joint external-and-perimeter explanation is currently at least as strong as a superior-management explanation and must be tested first.", "INFERRED", "NONE"),
    }
    questions = {
        "INITIAL_CONDITIONS": "What operating advantages and external tailwinds existed before the next observation window?",
        "IMPLEMENTED_MANAGEMENT_ACTION": "Which company-wide actions were actually implemented rather than planned or narrated?",
        "EXECUTION": "Which promised or named operating milestones were delivered, and at what perimeter?",
        "CUSTOMER_COMPETITION_RESPONSE": "Did customers absorb output with favorable price-mix and competitive response?",
        "UNIT_ECONOMICS": "Did unit economics improve after separating fuel, mix, scale and perimeter effects?",
        "WORKING_CAPITAL_CASH_CAPITAL": "Did operating progress convert into cash funding capacity after working capital and capex?",
        "ADAPTATION_PERMANENT_LOSS": "Did the company adapt without creating an irreversible capital or financing loss path?",
        "STRONGEST_ALTERNATIVE_EXPLANATION": "Can external demand, coal prices, acquisitions and new capacity explain the same outcome?",
    }
    next_evidence = {
        "INITIAL_CONDITIONS": "FY2014 industry demand and issuer-versus-industry volume spread.",
        "IMPLEMENTED_MANAGEMENT_ACTION": "Page-located post-cutoff implemented actions, excluding forward plans.",
        "EXECUTION": "Named FY2013 plan milestones and same-boundary FY2014 sales-volume delivery.",
        "CUSTOMER_COMPETITION_RESPONSE": "Direct customer or market-share evidence plus realized revenue per tonne.",
        "UNIT_ECONOMICS": "Same-definition unit cost and gross margin with external cost conditions retained.",
        "WORKING_CAPITAL_CASH_CAPITAL": "Receivable and inventory intensity, operating cash, cash capex and OCF-to-capex.",
        "ADAPTATION_PERMANENT_LOSS": "Observed adaptation, net-debt movement and direct irreversible-loss events.",
        "STRONGEST_ALTERNATIVE_EXPLANATION": "Joint reading of industry spread, unit cost, margin and capacity/perimeter disclosures.",
    }

    def make_view(method_id: str, assessments: dict[str, tuple[str, str, str]], method_label: str) -> dict[str, Any]:
        return {
            "method_id": method_id,
            "evidence_budget_id": decision["evidence_budget"]["evidence_budget_id"],
            "source_packet_refs": [source_ref],
            "fact_ids": [fact["fact_id"] for fact in facts],
            "enterprise_thesis": (
                "The FY2013 record shows a scaled operator expanding volume, margin and cash while reducing leverage; "
                + ("management execution is a plausible aggregate contributor but not established causally."
                   if method_label == "BASELINE" else
                   "the evidence does not yet distinguish external tailwinds, acquired capacity, execution skill, customer response and cash economics well enough to rate management or durability.")
            ),
            "judgment_cells": [
                _judgment(
                    method_label,
                    dimension,
                    questions[dimension],
                    assessments[dimension][0],
                    assessments[dimension][1],
                    [source_id],
                    dimension_cells[dimension],
                    assessments[dimension][2],
                    next_evidence[dimension],
                )
                for dimension in JUDGMENT_DIMENSIONS
            ],
            "interpretation_rule": (
                "Read aggregate issuer trends and management narrative together, while withholding a final management-quality conclusion."
                if method_label == "BASELINE" else
                "Read the chain in order: initial conditions -> implemented action -> execution -> customer response -> unit economics -> cash/capital -> adaptation/loss; test the strongest rival before causal credit."
            ),
            "expected_outcome_cell_ids": cell_ids,
            "prohibited_inferences": [
                "No one-year management-quality score.",
                "No action effect from issuer-wide outcome direction alone.",
                "No owner cash, moat or permanent-loss conclusion from an accounting proxy.",
            ],
        }

    baseline_view = make_view(BASELINE_METHOD_ID, baseline_assessments, "BASELINE")
    enhanced_view = make_view(ENHANCED_METHOD_ID, enhanced_assessments, "ENHANCED")
    pairing = {
        "schema_version": decision_utility.PAIRING_SCHEMA_VERSION,
        "pairing_id": "DUPAIR:CN600585:20140416:R7:V1",
        "decision_contract_ref": {"contract_id": decision["contract_id"], "contract_version": 1},
        "baseline": {
            "method_id": BASELINE_METHOD_ID,
            "decision_status": "RESEARCH",
            "material_unknown_ids": ["UNKNOWN:ACTION_EFFECT", "UNKNOWN:CUSTOMER_RESPONSE", "UNKNOWN:OWNER_CASH", "UNKNOWN:PERMANENT_LOSS"],
            "evidence_budget_id": decision["evidence_budget"]["evidence_budget_id"],
            "source_packet_refs": [source_ref],
            "research_cost_hours": 0,
        },
        "enhanced": {
            "method_id": ENHANCED_METHOD_ID,
            "decision_status": "RESEARCH",
            "material_unknown_ids": [
                "UNKNOWN:EXTERNAL_VS_INTERNAL", "UNKNOWN:ORGANIC_EXECUTION",
                "UNKNOWN:DIRECT_CUSTOMER_RESPONSE", "UNKNOWN:UNIT_ECONOMIC_ATTRIBUTION",
                "UNKNOWN:OWNER_CASH", "UNKNOWN:ADAPTATION_PERSISTENCE",
                "UNKNOWN:PERMANENT_LOSS",
            ],
            "evidence_budget_id": decision["evidence_budget"]["evidence_budget_id"],
            "source_packet_refs": [source_ref],
            "research_cost_hours": 0,
        },
        "frozen_at": frozen_at,
        "object_class": "DECISION_UTILITY_PAIRING",
        "claim_class": "SAME_CONTRACT_METHOD_ABLATION",
        "allowed_outputs": decision_utility.ALLOWED_OUTPUTS,
    }
    package = {
        "schema_version": PREOUTCOME_SCHEMA_VERSION,
        "package_id": package_id,
        "selection": selection,
        "source_packet_receipt": source_receipt,
        "decision_contract": decision,
        "shared_cutoff_facts": facts,
        "baseline_view": baseline_view,
        "enhanced_view": enhanced_view,
        "decision_utility_pairing": pairing,
        "outcome_measurement_contract": measurement,
        "strongest_rival": "Industry demand growth, coal-price relief, acquired businesses and newly commissioned capacity may jointly explain volume, margin and cash improvement without superior management or durable customer economics.",
        "contamination_boundary": {
            "historical_replay_status": "MODEL_MEMORY_MITIGATED",
            "repository_contains_later_summary": True,
            "score_authority": "NONE",
            "allowed_use": "DEVELOPMENT_MULTIDIMENSIONAL_UTILITY_ONLY",
        },
        "freeze_state": "PRE_OUTCOME_FROZEN",
        "frozen_at": frozen_at,
        "roles": roles,
        "rights": deepcopy(RIGHTS),
        "allowed_outputs": PREOUTCOME_OUTPUTS,
    }
    validation = validate_preoutcome_package(
        package,
        block=block,
        roster_freeze=roster_freeze,
        consumption_artifacts=consumption_artifacts,
    )
    if not validation["valid"]:
        raise ValueError("round7 package invalid: " + "; ".join(validation["findings"]))
    return package


def _load(block_dir: Path, name: str) -> dict[str, Any]:
    return json.loads((block_dir / name).read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_real_preoutcome_artifacts(block_dir: Path, *, frozen_at: str) -> dict[str, Any]:
    artifacts = [_load(block_dir, name) for name in CONSUMPTION_FILES]
    block = _load(block_dir, "04_industry_learning_block.json")
    freeze = _load(block_dir, "04_pre_outcome_roster_freeze.json")
    package = build_real_preoutcome_package(
        block=block,
        roster_freeze=freeze,
        consumption_artifacts=artifacts,
        frozen_at=frozen_at,
    )
    selection_artifact = {
        "schema_version": "enterprise-judgment-round7-selection.v1",
        "selection_id": "R7SEL:CN:CEMENT:600585:20140416:V1",
        "selection": deepcopy(package["selection"]),
        "selection_basis": "Frozen roster order after formal prior receipts, including Round 6 completion; outcome and source convenience were not used.",
        "object_class": "ENTERPRISE_JUDGMENT_MULTIDIMENSIONAL_SELECTION",
        "claim_class": "MECHANICAL_PRE_OUTCOME_SELECTION",
        "allowed_outputs": ["MULTIDIMENSIONAL_PAIRED_PREOUTCOME_RESEARCH", "RESEARCH_AGENDA"],
    }
    validation_receipt = {
        "schema_version": "enterprise-judgment-round7-preoutcome-validation-receipt.v1",
        "receipt_id": "R7POVR:CN:CEMENT:600585:20140416:V1",
        "selection_ref": selection_artifact["selection_id"],
        "package_ref": package["package_id"],
        "validated_at": frozen_at,
        "validation_status": "PRE_OUTCOME_VALID",
        "mechanical_selection_confirmed": True,
        "same_evidence_budget_confirmed": True,
        "full_enterprise_chain_confirmed": True,
        "judgment_dimensions": JUDGMENT_DIMENSIONS,
        "baseline_method_id": BASELINE_METHOD_ID,
        "enhanced_method_id": ENHANCED_METHOD_ID,
        "outcome_source_access_state": package["outcome_measurement_contract"]["source_access"]["access_state"],
        "outcome_content_read": False,
        "rights": deepcopy(RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_PREOUTCOME_VALIDATION_RECEIPT",
        "claim_class": "MULTIDIMENSIONAL_PAIRED_PREOUTCOME_FREEZE_CONFIRMATION",
        "allowed_outputs": ["PREOUTCOME_FREEZE_CONFIRMATION", "OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
    }
    return {
        "45_round7_multidimensional_selection.json": selection_artifact,
        "46_round7_multidimensional_preoutcome_package.json": package,
        "47_round7_preoutcome_validation_receipt.json": validation_receipt,
    }


def build_outcome_authorization(package: dict[str, Any]) -> dict[str, Any]:
    contract = package["outcome_measurement_contract"]
    source = contract["source_access"]
    return {
        "schema_version": measurement_acquisition.ENTERPRISE_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_receipt_id": source["authorization_receipt_id"],
        "measurement_contract_ref": {
            "measurement_contract_id": contract["contract_set_id"],
            "measurement_contract_version": 3,
        },
        "company_id": contract["company_id"],
        "custodian_id": package["roles"]["outcome_custodian_id"],
        "source_id": source["source_id"],
        "authorized": True,
        "content_read": True,
    }


def build_source_inventory(
    package: dict[str, Any], *, local_pdf_path: Path, registered_at: str,
) -> dict[str, Any]:
    contract = package["outcome_measurement_contract"]
    source = contract["source_access"]
    authorization = build_outcome_authorization(package)
    return {
        "schema_version": measurement_acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "OMINV:CN600585:FY2014:R7:V1",
        "measurement_contract_ref": authorization["measurement_contract_ref"],
        "custodian_id": authorization["custodian_id"],
        "registered_at": registered_at,
        "documents": [{
            "source_id": source["source_id"],
            "source_url": source["official_url"],
            "local_pdf_path": str(local_pdf_path),
            "issuer_id": source["issuer_id"],
            "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:600585",
            "report_period_end": source["report_period_end"],
            "official_source_type": source["source_type"],
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": "FY2014 issuer-consolidated original annual-report vintage; each field retains its own scope result.",
            "availability_precision": source["availability_precision"],
            "source_available_at": source["source_available_at"],
            "source_available_date": source["source_available_date"],
        }],
        "object_class": measurement_acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": measurement_acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["ENTERPRISE_OUTCOME_ACQUISITION_ONLY"],
    }


def settle_custodian_field_records(
    package: dict[str, Any],
    field_records: list[dict[str, Any]],
    *,
    local_pdf_path: Path,
    registry_db: Path,
    registered_at: str,
    observed_at: str,
    settled_at: str,
) -> dict[str, Any]:
    """Validate exact custodian records and settle them through Enterprise V3."""
    contract = package["outcome_measurement_contract"]
    authorization = build_outcome_authorization(package)
    inventory = build_source_inventory(
        package,
        local_pdf_path=local_pdf_path,
        registered_at=registered_at,
    )
    inventory_validation = measurement_acquisition.validate_registered_local_pdf_inventory(
        inventory,
        measurement_contract=contract,
        outcome_access_authorization=authorization,
    )
    if not inventory_validation["valid"]:
        raise ValueError("round7 source inventory invalid: " + "; ".join(inventory_validation["findings"]))
    acquisition_result = measurement_acquisition.acquire_outcome_measurements_from_field_records(
        contract,
        inventory,
        field_records,
        outcome_access_authorization=authorization,
    )
    previous_registry = reconstruction.CANONICAL_REGISTRY_PATH
    reconstruction.CANONICAL_REGISTRY_PATH = registry_db
    try:
        enterprise_control.register_measurement_contract(
            contract,
            frozen_at=contract["contract_frozen_at"],
        )
        settlement = settlement_adapter.settle_enterprise_acquisition_result(
            measurement_contract=contract,
            outcome_access_authorization=authorization,
            acquisition_result=acquisition_result,
            observed_at=observed_at,
            settlement_id="R7SETTLE:CN600585:20140416:FY2014:V1",
            settled_at=settled_at,
        )
    finally:
        reconstruction.CANONICAL_REGISTRY_PATH = previous_registry
    settlement.pop("persisted", None)
    settlement.pop("idempotent", None)
    return {
        "authorization": authorization,
        "inventory": inventory,
        "field_records": deepcopy(field_records),
        "settlement": settlement,
    }


def validate_review(review: Any, *, package: Any, settlement: Any) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(review, _REVIEW_KEYS, "round7_review", findings)
    package_item = _mapping(package)
    settlement_item = _mapping(settlement)
    if item.get("schema_version") != REVIEW_SCHEMA_VERSION:
        findings.append("round7_review.schema_version_invalid")
    if item.get("package_ref") != package_item.get("package_id"):
        findings.append("round7_review.package_ref_must_match")
    if item.get("settlement_ref") != settlement_item.get("settlement_id"):
        findings.append("round7_review.settlement_ref_must_match")
    if item.get("reviewer_id") in set(_mapping(package_item.get("roles")).values()):
        findings.append("round7_review.reviewer_must_be_independent")
    _instant(item.get("reviewed_at"), "round7_review.reviewed_at", findings)
    settled_ids = {row.get("cell_id") for row in _items(settlement_item.get("cell_results"))}
    seen: list[str] = []
    for index, raw in enumerate(_items(item.get("dimension_findings"))):
        finding = _closed(raw, _DIMENSION_FINDING_KEYS, f"round7_review.dimension_findings[{index}]", findings)
        dimension = finding.get("dimension")
        if dimension not in JUDGMENT_DIMENSIONS or dimension in seen:
            findings.append(f"round7_review.dimension_findings[{index}].dimension_invalid_or_duplicate")
        else:
            seen.append(str(dimension))
        if finding.get("utility_verdict") not in {"ENHANCED_BETTER", "BASELINE_BETTER", "NO_DIFFERENCE", "NOT_DIAGNOSTIC"}:
            findings.append(f"round7_review.dimension_findings[{index}].utility_verdict_invalid")
        for field in ("baseline_assessment", "enhanced_assessment", "economic_effect", "prohibited_inference"):
            if not _text(finding.get(field)):
                findings.append(f"round7_review.dimension_findings[{index}].{field}_required")
        if any(cell_id not in settled_ids for cell_id in _items(finding.get("supporting_cell_ids"))):
            findings.append(f"round7_review.dimension_findings[{index}].supporting_cell_invalid")
    if seen != JUDGMENT_DIMENSIONS:
        findings.append("round7_review.must_cover_full_chain_in_order")
    if item.get("overall_verdict") not in {
        "ENHANCED_MATERIALLY_IMPROVED_ENTERPRISE_JUDGMENT",
        "NO_MATERIAL_UTILITY_DIFFERENCE",
        "NOT_DIAGNOSTIC",
    }:
        findings.append("round7_review.overall_verdict_invalid")
    for field in ("investor_effect",):
        if not _text(item.get(field)):
            findings.append(f"round7_review.{field}_required")
    for field in ("unknowns_preserved", "limitations"):
        if not _items(item.get(field)) or any(not _text(value) for value in _items(item.get(field))):
            findings.append(f"round7_review.{field}_required")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != REVIEW_OUTPUTS:
        findings.append("round7_review.rights_or_outputs_invalid")
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_MULTIDIMENSIONAL_REVIEW":
        findings.append("round7_review.object_class_invalid")
    if item.get("claim_class") != "PAIRED_MULTIDIMENSIONAL_DECISION_UTILITY_REVIEW":
        findings.append("round7_review.claim_class_invalid")
    return {"valid": not findings, "findings": findings, "review": deepcopy(item) if not findings else None}


def validate_completion(
    receipt: Any, *, package: Any, settlement: Any, review: Any,
) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(receipt, _COMPLETION_KEYS, "round7_completion", findings)
    package_item, settlement_item, review_item = _mapping(package), _mapping(settlement), _mapping(review)
    if item.get("schema_version") != COMPLETION_SCHEMA_VERSION:
        findings.append("round7_completion.schema_version_invalid")
    if item.get("package_ref") != package_item.get("package_id"):
        findings.append("round7_completion.package_ref_must_match")
    if item.get("settlement_ref") != settlement_item.get("settlement_id"):
        findings.append("round7_completion.settlement_ref_must_match")
    if item.get("review_ref") != review_item.get("review_id"):
        findings.append("round7_completion.review_ref_must_match")
    selection = _mapping(package_item.get("selection"))
    if item.get("company_id") != selection.get("company_id") or item.get("cutoff_at") != selection.get("cutoff_at"):
        findings.append("round7_completion.company_and_cutoff_must_match")
    if item.get("status") != "ROUND7_REAL_MULTIDIMENSIONAL_FEEDBACK_COMPLETED":
        findings.append("round7_completion.status_invalid")
    if not _text(item.get("investor_summary")):
        findings.append("round7_completion.investor_summary_required")
    for field in ("proved", "not_proved", "next_research_action"):
        if not _items(item.get(field)) or any(not _text(value) for value in _items(item.get(field))):
            findings.append(f"round7_completion.{field}_required")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != COMPLETION_OUTPUTS:
        findings.append("round7_completion.rights_or_outputs_invalid")
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND7_COMPLETION_RECEIPT":
        findings.append("round7_completion.object_class_invalid")
    if item.get("claim_class") != "REAL_MULTIDIMENSIONAL_PAIRED_UTILITY_COMPLETION":
        findings.append("round7_completion.claim_class_invalid")
    return {"valid": not findings, "findings": findings, "receipt": deepcopy(item) if not findings else None}


def build_real_completion_receipt(
    package: dict[str, Any], settlement: dict[str, Any], review: dict[str, Any],
) -> dict[str, Any]:
    review_validation = validate_review(review, package=package, settlement=settlement)
    if not review_validation["valid"]:
        raise ValueError("round7 review invalid: " + "; ".join(review_validation["findings"]))
    receipt = {
        "schema_version": COMPLETION_SCHEMA_VERSION,
        "completion_id": "R7COMP:CN:CEMENT:600585:20140416:FY2014:V1",
        "package_ref": package["package_id"],
        "settlement_ref": settlement["settlement_id"],
        "review_ref": review["review_id"],
        "company_id": package["selection"]["company_id"],
        "cutoff_at": package["selection"]["cutoff_at"],
        "status": "ROUND7_REAL_MULTIDIMENSIONAL_FEEDBACK_COMPLETED",
        "investor_summary": (
            "海螺 FY2014 在行业增速放缓时仍录得更强销量、现金覆盖和更低净负债，"
            "但扩产、收购与外部成本变化尚未与企业自身能力分开；客户优势、owner cash、"
            "适应能力和永久损失结论继续保持未知。"
        ),
        "proved": [
            "同一 cutoff 与同一证据预算下，多维判断能把行业条件、已实施行动、执行、客户响应、单位经济、现金资本和永久损失边界分别保留。",
            "FY2014 公司销量增速高于行业约 7.49 个百分点，经营现金流和 OCF/现金资本开支上升，净负债率下降，同时存货上升。",
            "FY2013 毛利率口径包含骨料及石子，局部口径不匹配没有阻断其他十六个判断单元。",
        ],
        "not_proved": [
            "销量增长来自客户护城河、有机执行或管理层整体能力。",
            "经营现金改善等同普通股 owner cash，或一年的降杠杆已经排除永久损失。",
            "该方法已经通过无记忆污染的跨公司 holdout、可迁移至 CJO、估值、报告或投资动作。",
        ],
        "next_research_action": [
            "下一 cutoff 先冻结新增与收购产能、存量有机销量以及具名计划里程碑的范围桥。",
            "补充直接客户响应、同口径价格组合和水泥熟料毛利字段，不用公司总销量替代客户证据。",
            "拆分维护性与增长性资本开支，并把营运资本变化桥接到保守 owner-cash 候选。",
            "在未被后期摘要污染的不同公司和时期重复同证据预算测试，才判断是否允许方法迁移。",
        ],
        "rights": deepcopy(RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_ROUND7_COMPLETION_RECEIPT",
        "claim_class": "REAL_MULTIDIMENSIONAL_PAIRED_UTILITY_COMPLETION",
        "allowed_outputs": COMPLETION_OUTPUTS,
    }
    validation = validate_completion(
        receipt, package=package, settlement=settlement, review=review,
    )
    if not validation["valid"]:
        raise ValueError("round7 completion invalid: " + "; ".join(validation["findings"]))
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--block-dir", type=Path, required=True)
    parser.add_argument("--frozen-at", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    artifacts = build_real_preoutcome_artifacts(args.block_dir, frozen_at=args.frozen_at)
    if args.write:
        for name, artifact in artifacts.items():
            write_json(args.block_dir / name, artifact)
    print(json.dumps({"valid": True, "artifacts": list(artifacts)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
