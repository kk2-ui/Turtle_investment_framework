#!/usr/bin/env python3
"""Production builder for outcome-blind, cell-local mechanism training turns."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

try:
    from scripts import enterprise_judgment_forecast_projection as forecast_projection
    from scripts import enterprise_judgment_mechanism as mechanism
    from scripts import enterprise_judgment_reconstruction_registry as reconstruction_registry
    from scripts import enterprise_judgment_training_control_plane as training_control
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_forecast_projection as forecast_projection
    import enterprise_judgment_mechanism as mechanism
    import enterprise_judgment_reconstruction_registry as reconstruction_registry
    import enterprise_judgment_training_control_plane as training_control


PACKAGE_SCHEMA_VERSION = "enterprise-real-mechanism-preoutcome-package.v2"
PACKAGE_SCHEMA_VERSION_V3 = "enterprise-real-mechanism-preoutcome-package.v3"
CONTRACT_SCHEMA_VERSION = "enterprise-outcome-measurement-contract.v2"
CONTRACT_SCHEMA_VERSION_V3 = "enterprise-outcome-measurement-contract.v3"
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
    "access_state", "custodian_access", "issuer_id", "report_period_end",
    "availability_precision", "source_available_at", "source_available_date",
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
_CLOCK_KEYS = {"clock_kind", "flow_period", "balance_as_of", "event_window"}
_FLOW_KEYS = {"period_start", "period_end", "fiscal_period"}
_BALANCE_KEYS = {"as_of", "fiscal_period"}
_EVENT_KEYS = {"event_start", "event_end", "window_name"}
_V3_RAW_LOCATOR_KEYS = {"table_or_note", "line_item", "period_column"}
_V3_CELL_KEYS = _CELL_KEYS | {"measurement_clock", "raw_input_fields"}
_V3_RAW_INPUT_KEYS = {"field_id", "role", "unit", "measurement_clock", "locator"}
_V3_MULTI_SOURCE_RAW_INPUT_KEYS = _V3_RAW_INPUT_KEYS | {"source_id"}
_V3_FORMULA_KEYS = {"operator", "input_field_ids", "expression", "unit_conversions", "zero_baseline_rule"}
_V3_MULTI_SOURCE_FORMULA_KEYS = _V3_FORMULA_KEYS | {"input_coefficients"}
_V3_UNIT_CONVERSION_KEYS = {"field_id", "from_unit", "to_unit", "scale"}
_V3_INPUT_COEFFICIENT_KEYS = {"field_id", "coefficient"}
_V3_CONTRACT_KEYS = _CONTRACT_KEYS | {"freeze_state", "contract_frozen_at", "clock_policy"}
_V3_MULTI_SOURCE_CONTRACT_KEYS = (
    _V3_CONTRACT_KEYS - {"source_access"}
) | {"source_accesses"}
_V3_SOURCE_ACCESS_KEYS = _SOURCE_ACCESS_KEYS | {
    "authorization_receipt_id", "issuer_id", "report_period_end",
    "availability_precision", "source_available_at", "source_available_date",
}
_V3_COMPONENT_BOUNDARY_KEYS = _BOUNDARY_KEYS | {"component_role", "component_id"}
ENTERPRISE_COMPONENT_ROLES = {
    "MATURE_CORE",
    "NON_CORE_REAL_ESTATE",
    "NAMED_GROWTH_COHORT",
}
ENTERPRISE_RAW_FIELD_ROLES = {
    # Legacy V3 roles remain valid for every already-frozen contract.
    "OUTCOME", "BASELINE", "NUMERATOR", "DENOMINATOR", "EVENT",
    # Source-bearing company/capital responsibility fields.
    "CAPEX_CLASS", "PROJECT_COMMITMENT", "PROJECT_REMAINING_COMMITMENT",
    "OPERATING_CASH_FLOW", "MAINTENANCE_CAPEX", "GROWTH_CAPEX",
    "OCF_RECONCILIATION_ADJUSTMENT", "OWNER_CASH_ADJUSTMENT",
    "CAPACITY", "PRODUCTION", "SALES_VOLUME", "CUSTOMER_ABSORPTION",
    "UNIT_ECONOMICS", "CASH_COLLECTIONS", "DEBT",
    "CASH_RETURN_NUMERATOR", "INVESTED_CAPITAL_DENOMINATOR",
    # Operating-NWC and deterministic reconciliation roles.
    "OPENING_STOCK", "CLOSING_STOCK",
    "OPENING_ACCOUNTS_RECEIVABLE", "OPENING_PREPAYMENTS", "OPENING_INVENTORY",
    "OPENING_ACCOUNTS_PAYABLE", "OPENING_CUSTOMER_ADVANCES",
    "ENDING_ACCOUNTS_RECEIVABLE", "ENDING_PREPAYMENTS", "ENDING_INVENTORY",
    "ENDING_ACCOUNTS_PAYABLE", "ENDING_CUSTOMER_ADVANCES",
    "OPERATING_REVENUE", "OPERATING_COST", "TAXES_AND_SURCHARGES",
    "SELLING_EXPENSE", "ADMINISTRATIVE_EXPENSE",
    "CASH_LONG_LIVED_ASSET_ACQUISITION",
    "RECONCILIATION_COMPONENT", "RECONCILIATION_TOTAL",
}
ENTERPRISE_DETERMINISTIC_FORMULAS = {
    "RAW_VALUE", "EVENT_BOOLEAN", "RATIO_CHANGE", "DIFFERENCE", "PERCENT_CHANGE",
    "SUM", "SIGNED_STOCK_DELTA", "COMPONENT_TO_TOTAL_RECONCILIATION",
    "OWNER_CASH", "INVESTED_CAPITAL_RETURN",
}
_V3_BALANCE_RAW_FIELD_ROLES = {
    "OPENING_STOCK", "CLOSING_STOCK",
    "OPENING_ACCOUNTS_RECEIVABLE", "OPENING_PREPAYMENTS", "OPENING_INVENTORY",
    "OPENING_ACCOUNTS_PAYABLE", "OPENING_CUSTOMER_ADVANCES",
    "ENDING_ACCOUNTS_RECEIVABLE", "ENDING_PREPAYMENTS", "ENDING_INVENTORY",
    "ENDING_ACCOUNTS_PAYABLE", "ENDING_CUSTOMER_ADVANCES",
    "DEBT", "INVESTED_CAPITAL_DENOMINATOR",
}
_V3_SIGNED_SUM_NEGATIVE_ROLES = {
    "PROJECT_REMAINING_COMMITMENT",
    "OPERATING_COST",
    "TAXES_AND_SURCHARGES",
    "SELLING_EXPENSE",
    "ADMINISTRATIVE_EXPENSE",
    "OPENING_ACCOUNTS_PAYABLE",
    "OPENING_CUSTOMER_ADVANCES",
    "ENDING_ACCOUNTS_PAYABLE",
    "ENDING_CUSTOMER_ADVANCES",
}
_V3_SIGNED_SUM_ROLE_PATTERNS = (
    (
        "OPERATING_REVENUE",
        "OPERATING_COST",
        "TAXES_AND_SURCHARGES",
        "SELLING_EXPENSE",
        "ADMINISTRATIVE_EXPENSE",
    ),
    ("PROJECT_COMMITMENT", "PROJECT_REMAINING_COMMITMENT"),
    (
        "OPENING_ACCOUNTS_RECEIVABLE",
        "OPENING_PREPAYMENTS",
        "OPENING_INVENTORY",
        "OPENING_ACCOUNTS_PAYABLE",
        "OPENING_CUSTOMER_ADVANCES",
    ),
    (
        "ENDING_ACCOUNTS_RECEIVABLE",
        "ENDING_PREPAYMENTS",
        "ENDING_INVENTORY",
        "ENDING_ACCOUNTS_PAYABLE",
        "ENDING_CUSTOMER_ADVANCES",
    ),
)
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


def validate_superseding_adjudication(
    adjudication: Any, *, block: Any, roster_freeze: Any,
) -> dict[str, Any]:
    """Validate the complete post-outcome quarantine before it affects selection."""
    findings: list[str] = []
    root_keys = {
        "schema_version", "adjudication_id", "supersedes", "adjudication_status",
        "outcome_access_confirmed", "permanent_no_refreeze", "training_admission",
        "invalidated_claims", "specific_attribution_correction", "independent_review_findings",
        "retained_post_outcome_data", "active_training_projection", "rights", "object_class",
        "claim_class", "allowed_outputs",
    }
    item = _closed(adjudication, root_keys, "superseding_adjudication", findings)
    if item.get("schema_version") != _ADJUDICATION_SCHEMA:
        findings.append("superseding_adjudication.schema_version_invalid")
    if not _text(item.get("adjudication_id")):
        findings.append("superseding_adjudication.adjudication_id_required")
    supersedes = _closed(
        item.get("supersedes"), {"commit", "artifact_ref", "transition_id", "selected_rank"},
        "superseding_adjudication.supersedes", findings,
    )
    block_item, freeze_item = _mapping(block), _mapping(roster_freeze)
    roster = [_mapping(row) for row in _items(block_item.get("company_cutoff_transition_roster"))]
    frozen_ids = _items(freeze_item.get("company_cutoff_transition_ids"))
    if block_item.get("block_id") != freeze_item.get("block_id"):
        findings.append("superseding_adjudication.block_must_match_roster_freeze")
    if [row.get("transition_id") for row in roster] != frozen_ids:
        findings.append("superseding_adjudication.roster_must_match_immutable_freeze")
    transition = next((row for row in roster if row.get("transition_id") == supersedes.get("transition_id")), {})
    if not transition or supersedes.get("selected_rank") != transition.get("rank"):
        findings.append("superseding_adjudication.transition_and_rank_must_match_frozen_roster")
    if not _text(supersedes.get("commit")) or not _text(supersedes.get("artifact_ref")):
        findings.append("superseding_adjudication.superseded_commit_and_artifact_required")
    if (
        item.get("adjudication_status") != "CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY"
        or item.get("outcome_access_confirmed") is not True
        or item.get("permanent_no_refreeze") is not True
        or item.get("training_admission") != "DENIED"
    ):
        findings.append("superseding_adjudication.quarantine_disposition_invalid")
    invalidated = _items(item.get("invalidated_claims"))
    required_invalidated = {
        "ALL_NINE_CELL_SETTLEMENT_LABELS", "LOCAL_H_A_SUPPORTED_WITHOUT_ACTION_ATTRIBUTION",
        "FORECAST_OBSERVED_DIRECTION", "FORECAST_OBSERVED_VALUE",
        "REAL_CELL_LEVEL_MECHANISM_FEEDBACK_COMPLETED", "MECHANISM_FEEDBACK",
    }
    if set(invalidated) != required_invalidated or len(invalidated) != len(required_invalidated):
        findings.append("superseding_adjudication.invalidated_claims_incomplete")
    if not _text(item.get("specific_attribution_correction")):
        findings.append("superseding_adjudication.specific_attribution_correction_required")
    review_keys = {
        "finding_id", "priority", "root_cause_class", "why_below_standard", "economic_impact",
        "missing_facts", "prohibited_assumption", "executable_remediation", "acceptance_criteria",
    }
    reviews = [_closed(raw, review_keys, f"superseding_adjudication.independent_review_findings[{index}]", findings)
               for index, raw in enumerate(_items(item.get("independent_review_findings")))]
    if len(reviews) != 3:
        findings.append("superseding_adjudication.three_independent_findings_required")
    for index, review in enumerate(reviews):
        path = f"superseding_adjudication.independent_review_findings[{index}]"
        if review.get("priority") not in {"P1", "P2"} or review.get("root_cause_class") not in {"MODEL", "REASONING"}:
            findings.append(path + ".priority_or_root_cause_invalid")
        for field in review_keys - {"missing_facts"}:
            if not _text(review.get(field)):
                findings.append(f"{path}.{field}_required")
        if not _items(review.get("missing_facts")) or any(not _text(value) for value in _items(review.get("missing_facts"))):
            findings.append(path + ".missing_facts_required")
    retained = _closed(
        item.get("retained_post_outcome_data"),
        {"source_ref", "retention_reason", "retained_classes", "prohibited_uses"},
        "superseding_adjudication.retained_post_outcome_data", findings,
    )
    if not _text(retained.get("source_ref")) or not _text(retained.get("retention_reason")):
        findings.append("superseding_adjudication.retained_source_and_reason_required")
    if retained.get("retained_classes") != ["POST_OUTCOME_TEACHING", "DATA_COVERAGE"]:
        findings.append("superseding_adjudication.retained_classes_invalid")
    required_prohibited = {
        "DIRECTIONAL_LEARNING", "FORECAST_SCORING", "MANAGEMENT_EXECUTION_LABEL",
        "ACTION_EFFECT_ATTRIBUTION", "ENTERPRISE_LEARNING_CANDIDATE", "METHOD_TRANSFER",
    }
    if set(_items(retained.get("prohibited_uses"))) != required_prohibited:
        findings.append("superseding_adjudication.prohibited_uses_incomplete")
    active = _closed(
        item.get("active_training_projection"),
        {"transition_status", "allowed_outputs", "cell_settlements", "forecast_settlements", "mechanism_feedback", "enterprise_learning_status"},
        "superseding_adjudication.active_training_projection", findings,
    )
    if (
        active.get("transition_status") != "CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY"
        or active.get("allowed_outputs") != ["POST_OUTCOME_TEACHING", "DATA_COVERAGE", "RESEARCH_AGENDA"]
        or active.get("cell_settlements") != []
        or active.get("forecast_settlements") != []
        or active.get("mechanism_feedback") is not None
        or active.get("enterprise_learning_status") != "DENIED"
    ):
        findings.append("superseding_adjudication.active_projection_must_remain_quarantined")
    expected_rights = {**_RIGHTS, "mechanism_feedback": "NOT_AUTHORIZED"}
    if item.get("rights") != expected_rights:
        findings.append("superseding_adjudication.rights_invalid")
    if (
        item.get("object_class") != "ENTERPRISE_MECHANISM_FEEDBACK_SUPERSEDING_ADJUDICATION"
        or item.get("claim_class") != "CONTRACT_INSUFFICIENCY_AND_POST_OUTCOME_QUARANTINE"
        or item.get("allowed_outputs") != ["POST_OUTCOME_TEACHING", "DATA_COVERAGE", "RESEARCH_AGENDA"]
    ):
        findings.append("superseding_adjudication.object_claim_or_outputs_invalid")
    return {
        "valid": not findings,
        "findings": findings,
        "adjudication": deepcopy(item) if not findings else None,
        "bound_transition": deepcopy(transition) if not findings else None,
    }


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
    if _mapping(contract).get("schema_version") == CONTRACT_SCHEMA_VERSION_V3:
        return validate_outcome_measurement_contract_v3(contract)
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
    source_url = _text(source_access.get("official_url"))
    parsed_url = urlparse(source_url or "")
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc.casefold() not in {"static.cninfo.com.cn", "static.sse.com.cn"}
        or not parsed_url.path.casefold().endswith(".pdf")
    ):
        findings.append("measurement_contract.source_access.official_url_must_be_static_official_pdf")
    if source_access.get("source_type") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
        findings.append("measurement_contract.source_access.source_type_invalid")
    if source_access.get("issuer_id") != "ISSUER:" + str(item.get("company_id")):
        findings.append("measurement_contract.source_access.issuer_id_must_match_company")
    expected_period = _text(window.get("period_end"))
    expected_period = expected_period[:10] if expected_period else None
    if source_access.get("report_period_end") != expected_period:
        findings.append("measurement_contract.source_access.report_period_must_match_outcome_window")
    precision = source_access.get("availability_precision")
    if precision == "TIMESTAMP":
        available = _instant(
            source_access.get("source_available_at"),
            "measurement_contract.source_access.source_available_at", findings,
        )
        if source_access.get("source_available_date") is not None:
            findings.append("measurement_contract.source_access.timestamp_cannot_include_date")
        if cutoff and available and available <= cutoff:
            findings.append("measurement_contract.source_access.availability_must_follow_cutoff")
    elif precision == "DATE_ONLY":
        available_day: Any = None
        try:
            available_day = datetime.fromisoformat(str(source_access.get("source_available_date"))).date()
        except (TypeError, ValueError):
            findings.append("measurement_contract.source_access.source_available_date_invalid")
        if source_access.get("source_available_at") is not None:
            findings.append("measurement_contract.source_access.date_only_cannot_include_timestamp")
        if cutoff and available_day and available_day <= cutoff.date():
            findings.append("measurement_contract.source_access.availability_must_follow_cutoff")
    else:
        findings.append("measurement_contract.source_access.availability_precision_invalid")

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


def _validate_v3_clock(clock: Any, *, path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(clock)
    if set(item).difference(_CLOCK_KEYS):
        findings.append(f"{path}.extra:{','.join(sorted(set(item).difference(_CLOCK_KEYS)))}")
    if "clock_kind" not in item:
        findings.append(path + ".clock_kind_required")
    kind = item.get("clock_kind")
    if kind == "FLOW_PERIOD":
        flow = _mapping(item.get("flow_period"))
        if set(flow).difference(_FLOW_KEYS):
            findings.append(f"{path}.flow_period.extra:{','.join(sorted(set(flow).difference(_FLOW_KEYS)))}")
        if not _text(flow.get("period_start")) or not _text(flow.get("period_end")) or not _text(flow.get("fiscal_period")):
            findings.append(path + ".flow_period_incomplete")
        if item.get("balance_as_of") is not None or item.get("event_window") is not None:
            findings.append(path + ".flow_period_cannot_include_balance_or_event_clock")
    elif kind == "BALANCE_AS_OF":
        balance = _mapping(item.get("balance_as_of"))
        if set(balance).difference(_BALANCE_KEYS):
            findings.append(f"{path}.balance_as_of.extra:{','.join(sorted(set(balance).difference(_BALANCE_KEYS)))}")
        if not _text(balance.get("as_of")) or not _text(balance.get("fiscal_period")):
            findings.append(path + ".balance_as_of_incomplete")
        if item.get("flow_period") is not None or item.get("event_window") is not None:
            findings.append(path + ".balance_as_of_cannot_include_flow_or_event_clock")
    elif kind == "EVENT_WINDOW":
        event = _mapping(item.get("event_window"))
        if set(event).difference(_EVENT_KEYS):
            findings.append(f"{path}.event_window.extra:{','.join(sorted(set(event).difference(_EVENT_KEYS)))}")
        if not all(_text(event.get(key)) for key in _EVENT_KEYS):
            findings.append(path + ".event_window_incomplete")
        if item.get("flow_period") is not None or item.get("balance_as_of") is not None:
            findings.append(path + ".event_window_cannot_include_flow_or_balance_clock")
    else:
        findings.append(path + ".clock_kind_invalid")
    return item


def _clock_date(clock: dict[str, Any], key: str) -> str | None:
    value = _mapping(clock.get(key)).get("period_end") if key == "flow_period" else _mapping(clock.get(key)).get("as_of")
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return None


def _event_end(clock: dict[str, Any]) -> str | None:
    value = _mapping(clock.get("event_window")).get("event_end")
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


def _event_start(clock: dict[str, Any]) -> str | None:
    value = _mapping(clock.get("event_window")).get("event_start")
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


def _clock_period_end(clock: dict[str, Any]) -> str | None:
    """Return the frozen report-period boundary carried by a raw clock."""
    kind = clock.get("clock_kind")
    if kind == "FLOW_PERIOD":
        value = _mapping(clock.get("flow_period")).get("period_end")
    elif kind == "BALANCE_AS_OF":
        value = _mapping(clock.get("balance_as_of")).get("as_of")
    elif kind == "EVENT_WINDOW":
        value = _mapping(clock.get("event_window")).get("event_end")
    else:
        value = None
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


def _validate_v3_source_access(
    source_access: Any,
    *,
    path: str,
    company_id: Any,
    cutoff: datetime | None,
    findings: list[str],
    expected_report_period: str | None = None,
    strict_availability: bool = True,
) -> dict[str, Any]:
    """Validate one frozen official report identity without selecting a source."""
    source = _closed(source_access, _V3_SOURCE_ACCESS_KEYS, path, findings)
    if not _text(source.get("authorization_receipt_id")):
        findings.append(path + ".authorization_receipt_id_required")
    if source.get("access_state") != "SEALED_UNTIL_PREOUTCOME_COMMIT":
        findings.append(path + ".outcome_source_must_be_sealed")
    if source.get("published_after_cutoff") is not True or source.get("custodian_access") != "OUTCOME_ONLY":
        findings.append(path + ".outcome_source_access_invalid")
    source_url = _text(source.get("official_url"))
    parsed_url = urlparse(source_url or "")
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc.casefold() not in {"static.cninfo.com.cn", "static.sse.com.cn"}
        or not parsed_url.path.casefold().endswith(".pdf")
    ):
        findings.append(path + ".official_url_must_be_static_official_pdf")
    if source.get("source_type") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
        findings.append(path + ".source_type_invalid")
    if source.get("issuer_id") != "ISSUER:" + str(company_id):
        findings.append(path + ".issuer_id_must_match_company")
    report_period = _text(source.get("report_period_end"))
    try:
        datetime.fromisoformat(report_period).date()
    except (TypeError, ValueError):
        findings.append(path + ".report_period_end_invalid")
    if expected_report_period is not None and report_period != expected_report_period:
        findings.append(path + ".report_period_must_match_outcome_window")
    if strict_availability:
        precision = source.get("availability_precision")
        if precision == "TIMESTAMP":
            available = _instant(source.get("source_available_at"), path + ".source_available_at", findings)
            if source.get("source_available_date") is not None:
                findings.append(path + ".timestamp_cannot_include_date")
            if cutoff and available and available <= cutoff:
                findings.append(path + ".availability_must_follow_cutoff")
        elif precision == "DATE_ONLY":
            available_day: Any = None
            try:
                available_day = datetime.fromisoformat(str(source.get("source_available_date"))).date()
            except (TypeError, ValueError):
                findings.append(path + ".source_available_date_invalid")
            if source.get("source_available_at") is not None:
                findings.append(path + ".date_only_cannot_include_timestamp")
            if cutoff and available_day and available_day <= cutoff.date():
                findings.append(path + ".availability_must_follow_cutoff")
        else:
            findings.append(path + ".availability_precision_invalid")
    return source


def _validate_v3_enhanced_formula_roles(
    operator: Any,
    raw_inputs: list[dict[str, Any]],
    conversions: list[dict[str, Any]],
    coefficients: list[dict[str, Any]],
    *,
    output_unit: Any,
    path: str,
    findings: list[str],
) -> None:
    """Freeze input order, unit magnitude, and explicit arithmetic signs."""
    roles = [raw.get("role") for raw in raw_inputs]
    if operator == "RAW_VALUE":
        if len(roles) != 1 or roles == ["EVENT"]:
            findings.append(path + ".raw_value_requires_one_numeric_input")
    elif operator == "EVENT_BOOLEAN":
        if roles != ["EVENT"]:
            findings.append(path + ".event_boolean_requires_one_event_input")
    elif operator == "SUM":
        if not roles or "EVENT" in roles:
            findings.append(path + ".sum_requires_numeric_inputs")
    elif operator == "SIGNED_STOCK_DELTA":
        if roles != ["OPENING_STOCK", "CLOSING_STOCK"]:
            findings.append(path + ".signed_stock_delta_requires_opening_then_closing")
    elif operator == "COMPONENT_TO_TOTAL_RECONCILIATION":
        if len(roles) < 2 or roles[-1] != "RECONCILIATION_TOTAL" or any(
            role != "RECONCILIATION_COMPONENT" for role in roles[:-1]
        ):
            findings.append(path + ".component_reconciliation_requires_components_then_total")
    elif operator == "OWNER_CASH":
        if len(roles) < 2 or roles[:2] != ["OPERATING_CASH_FLOW", "MAINTENANCE_CAPEX"] or any(
            role not in {"OCF_RECONCILIATION_ADJUSTMENT", "OWNER_CASH_ADJUSTMENT"}
            for role in roles[2:]
        ):
            findings.append(path + ".owner_cash_requires_ocf_maintenance_capex_then_signed_adjustments")
    elif operator == "INVESTED_CAPITAL_RETURN":
        if roles != ["CASH_RETURN_NUMERATOR", "INVESTED_CAPITAL_DENOMINATOR"]:
            findings.append(path + ".invested_capital_return_requires_numerator_then_denominator")
    elif operator == "PERCENT_CHANGE":
        if len(roles) != 2 or "EVENT" in roles:
            findings.append(path + ".percent_change_requires_two_numeric_inputs")
    elif operator == "RATIO_CHANGE":
        if len(roles) != 4 or "EVENT" in roles:
            findings.append(path + ".ratio_change_requires_four_numeric_inputs")
    elif operator == "DIFFERENCE":
        if len(roles) not in {2, 4} or "EVENT" in roles:
            findings.append(path + ".difference_requires_two_or_four_numeric_inputs")

    parsed_coefficients: list[Decimal] = []
    for index, (raw_input, conversion) in enumerate(
        zip(raw_inputs, conversions, strict=False)
    ):
        conversion_path = f"{path}.unit_conversions[{index}]"
        if conversion.get("from_unit") != raw_input.get("unit"):
            findings.append(conversion_path + ".from_unit_must_match_raw_input")
        if conversion.get("to_unit") != output_unit:
            findings.append(conversion_path + ".to_unit_must_match_cell_unit")
        try:
            magnitude = Decimal(str(conversion.get("scale")))
        except InvalidOperation:
            magnitude = Decimal("NaN")
        if not magnitude.is_finite() or magnitude <= 0:
            findings.append(conversion_path + ".scale_must_be_positive_finite")
        elif operator == "EVENT_BOOLEAN" and magnitude != 1:
            findings.append(conversion_path + ".event_scale_must_equal_one")
    for index, coefficient_binding in enumerate(coefficients):
        coefficient_path = f"{path}.input_coefficients[{index}]"
        try:
            coefficient = Decimal(str(coefficient_binding.get("coefficient")))
        except InvalidOperation:
            coefficient = Decimal("NaN")
        parsed_coefficients.append(coefficient)
        if not coefficient.is_finite() or coefficient not in {Decimal("-1"), Decimal("1")}:
            findings.append(coefficient_path + ".coefficient_must_be_plus_or_minus_one")
    if operator == "SUM" and len(parsed_coefficients) == len(roles):
        signed_families = [
            pattern
            for pattern in _V3_SIGNED_SUM_ROLE_PATTERNS
            if set(pattern).intersection(roles)
        ]
        if signed_families and not any(tuple(roles) == pattern for pattern in signed_families):
            findings.append(path + ".signed_sum_raw_role_pattern_invalid")
        for index, (role, coefficient) in enumerate(zip(roles, parsed_coefficients, strict=True)):
            expected = Decimal("-1") if role in _V3_SIGNED_SUM_NEGATIVE_ROLES else Decimal("1")
            if coefficient != expected:
                findings.append(
                    f"{path}.input_coefficients[{index}].coefficient_must_match_raw_role"
                )
    elif operator != "SUM" and any(coefficient != 1 for coefficient in parsed_coefficients):
        findings.append(path + ".intrinsically_signed_operator_requires_positive_coefficients")


def validate_outcome_measurement_contract_v3(contract: Any) -> dict[str, Any]:
    """Validate the v3 atomic contract with independent measurement clocks.

    A v3 contract is frozen before outcome access.  It records raw source
    fields for derived metrics, so a later adapter cannot replace a ratio or
    margin with a convenient year-over-year number.
    """
    findings: list[str] = []
    contract_value = _mapping(contract)
    multi_source = "source_accesses" in contract_value
    root_keys = _V3_MULTI_SOURCE_CONTRACT_KEYS if multi_source else _V3_CONTRACT_KEYS
    item = _closed(contract, root_keys, "measurement_contract", findings)
    if item.get("schema_version") != CONTRACT_SCHEMA_VERSION_V3:
        findings.append("measurement_contract.schema_version_invalid")
    if item.get("freeze_state") != "PRE_OUTCOME_FROZEN":
        findings.append("measurement_contract.freeze_state_must_be_pre_outcome_frozen")
    if not _text(item.get("contract_frozen_at")):
        findings.append("measurement_contract.contract_frozen_at_required")
    if item.get("clock_policy") != "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK":
        findings.append("measurement_contract.clock_policy_invalid")
    for field in ("contract_set_id", "package_ref", "company_id", "cutoff_at"):
        if not _text(item.get(field)):
            findings.append(f"measurement_contract.{field}_required")
    cutoff = _instant(item.get("cutoff_at"), "measurement_contract.cutoff_at", findings)
    frozen_at = _instant(item.get("contract_frozen_at"), "measurement_contract.contract_frozen_at", findings)
    if cutoff and frozen_at and frozen_at <= cutoff:
        findings.append("measurement_contract.contract_frozen_at_must_follow_cutoff")
    window = _closed(item.get("outcome_window"), _WINDOW_KEYS, "measurement_contract.outcome_window", findings)
    period_start = _instant(window.get("period_start"), "measurement_contract.outcome_window.period_start", findings)
    period_end = _instant(window.get("period_end"), "measurement_contract.outcome_window.period_end", findings)
    due_at = _instant(window.get("settlement_due_at"), "measurement_contract.outcome_window.settlement_due_at", findings)
    if period_start and period_end and period_end <= period_start:
        findings.append("measurement_contract.outcome_window_order_invalid")
    if period_end and due_at and due_at <= period_end:
        findings.append("measurement_contract.settlement_due_must_follow_period_end")
    source_accesses: list[dict[str, Any]] = []
    if multi_source:
        raw_accesses = _items(item.get("source_accesses"))
        if not raw_accesses:
            findings.append("measurement_contract.source_accesses_required")
        for source_index, raw_source in enumerate(raw_accesses):
            source_accesses.append(_validate_v3_source_access(
                raw_source,
                path=f"measurement_contract.source_accesses[{source_index}]",
                company_id=item.get("company_id"),
                cutoff=cutoff,
                findings=findings,
            ))
        source_ids = [_text(source.get("source_id")) for source in source_accesses]
        if "" in source_ids or len(source_ids) != len(set(source_ids)):
            findings.append("measurement_contract.source_access_ids_must_be_unique")
        authorization_receipts = {
            _text(source.get("authorization_receipt_id")) for source in source_accesses
        }
        if "" in authorization_receipts or len(authorization_receipts) != 1:
            findings.append("measurement_contract.source_accesses_require_one_set_authorization_receipt")
        window_start = period_start.date().isoformat() if period_start else None
        window_end = period_end.date().isoformat() if period_end else None
        for source_index, source in enumerate(source_accesses):
            report_period = _text(source.get("report_period_end"))
            if window_start and window_end and not (window_start <= report_period <= window_end):
                findings.append(
                    f"measurement_contract.source_accesses[{source_index}].report_period_outside_outcome_window"
                )
    else:
        expected_period = period_end.date().isoformat() if period_end else None
        source_accesses = [_validate_v3_source_access(
            item.get("source_access"),
            path="measurement_contract.source_access",
            company_id=item.get("company_id"),
            cutoff=cutoff,
            findings=findings,
            expected_report_period=expected_period,
            strict_availability=False,
        )]
    source_access_by_id = {
        _text(source.get("source_id")): source for source in source_accesses
        if _text(source.get("source_id"))
    }

    cells = [_closed(raw, _V3_CELL_KEYS, f"measurement_contract.atomic_cells[{index}]", findings)
             for index, raw in enumerate(_items(item.get("atomic_cells")))]
    cell_ids = [_text(cell.get("cell_id")) for cell in cells]
    if not cells or "" in cell_ids or len(cell_ids) != len(set(cell_ids)):
        findings.append("measurement_contract.atomic_cell_ids_must_be_unique")
    outcome_field_ids: list[str] = []
    component_bindings: dict[str, tuple[Any, Any, Any]] = {}
    raw_field_bindings: dict[str, dict[str, Any]] = {}
    for index, cell in enumerate(cells):
        path = f"measurement_contract.atomic_cells[{index}]"
        if cell.get("layer") not in _LAYERS:
            findings.append(f"{path}.layer_invalid")
        if not _text(cell.get("thread_id")) or not _text(cell.get("prohibited_inference")):
            findings.append(f"{path}.thread_and_prohibited_inference_required")
        cell_period = _closed(cell.get("outcome_period"), _WINDOW_KEYS - {"settlement_due_at"}, path + ".outcome_period", findings)
        if not all(_text(cell_period.get(key)) for key in _WINDOW_KEYS - {"settlement_due_at"}):
            findings.append(f"{path}.outcome_period_incomplete")
        _validate_v3_clock(cell.get("measurement_clock"), path=path + ".measurement_clock", findings=findings)
        boundary_keys = _V3_COMPONENT_BOUNDARY_KEYS if multi_source else _BOUNDARY_KEYS
        boundary = _closed(cell.get("responsibility_boundary"), boundary_keys, path + ".responsibility_boundary", findings)
        if not all(_text(boundary.get(key)) for key in boundary_keys):
            findings.append(f"{path}.responsibility_boundary_incomplete")
        if multi_source and boundary.get("component_role") not in ENTERPRISE_COMPONENT_ROLES:
            findings.append(f"{path}.responsibility_boundary.component_role_invalid")
        if multi_source:
            component_id = _text(boundary.get("component_id"))
            component_binding = (
                boundary.get("component_role"),
                boundary.get("responsibility_unit_id"),
                boundary.get("perimeter_id"),
            )
            if component_id:
                frozen_binding = component_bindings.setdefault(component_id, component_binding)
                if frozen_binding != component_binding:
                    findings.append(
                        f"{path}.responsibility_boundary.component_id_identity_conflict"
                    )
        field = _closed(cell.get("field_identity"), _FIELD_KEYS, path + ".field_identity", findings)
        outcome_field_id = _text(field.get("outcome_field_id"))
        outcome_field_ids.append(outcome_field_id)
        if not outcome_field_id or not all(_text(field.get(key)) for key in _FIELD_KEYS - {"baseline_field_id"}):
            findings.append(f"{path}.field_identity_incomplete")
        unit = _closed(cell.get("unit"), _UNIT_KEYS, path + ".unit", findings)
        if not all(_text(unit.get(key)) for key in _UNIT_KEYS):
            findings.append(f"{path}.unit_incomplete")
        raw_keys = _V3_MULTI_SOURCE_RAW_INPUT_KEYS if multi_source else _V3_RAW_INPUT_KEYS
        raw_inputs = [_closed(raw, raw_keys, f"{path}.raw_input_fields[{raw_index}]", findings)
                      for raw_index, raw in enumerate(_items(cell.get("raw_input_fields")))]
        raw_ids = [_text(raw.get("field_id")) for raw in raw_inputs]
        if not raw_inputs or "" in raw_ids or len(raw_ids) != len(set(raw_ids)):
            findings.append(f"{path}.raw_input_fields_must_be_unique")
        for raw_index, raw in enumerate(raw_inputs):
            raw_path = f"{path}.raw_input_fields[{raw_index}]"
            if raw.get("role") not in ENTERPRISE_RAW_FIELD_ROLES:
                findings.append(f"{raw_path}.role_invalid")
            if multi_source and raw.get("source_id") not in source_access_by_id:
                findings.append(f"{raw_path}.source_id_must_match_frozen_source_access")
            if not _text(raw.get("unit")):
                findings.append(f"{raw_path}.unit_required")
            locator = _closed(raw.get("locator"), _V3_RAW_LOCATOR_KEYS, raw_path + ".locator", findings)
            if not all(_text(locator.get(key)) for key in _V3_RAW_LOCATOR_KEYS):
                findings.append(raw_path + ".locator_incomplete")
            _validate_v3_clock(raw.get("measurement_clock"), path=raw_path + ".measurement_clock", findings=findings)
            raw_clock = _mapping(raw.get("measurement_clock"))
            raw_field_id = _text(raw.get("field_id"))
            if multi_source and raw_field_id:
                semantic_binding = {
                    "source_id": raw.get("source_id"),
                    "measurement_clock": deepcopy(raw.get("measurement_clock")),
                    "locator": deepcopy(raw.get("locator")),
                    "unit": raw.get("unit"),
                    "raw_field_role": raw.get("role"),
                    "responsibility_boundary": deepcopy(boundary),
                }
                frozen_binding = raw_field_bindings.setdefault(raw_field_id, semantic_binding)
                if frozen_binding != semantic_binding:
                    findings.append(raw_path + ".raw_field_id_semantic_binding_conflict")
            fiscal_match = re.search(r":FY(\d{4}):", raw_field_id)
            fiscal_year = fiscal_match.group(1) if fiscal_match else None
            if raw.get("role") == "EVENT":
                if raw_clock.get("clock_kind") != "EVENT_WINDOW":
                    findings.append(raw_path + ".event_role_requires_event_window")
                start = _event_start(raw_clock)
                end = _event_end(raw_clock)
                if start is None or end is None or (cutoff and start <= cutoff.date().isoformat()) or (period_end and end > period_end.date().isoformat()):
                    findings.append(raw_path + ".event_window_must_follow_cutoff_and_end_in_outcome_window")
            else:
                expected_kind = (
                    "BALANCE_AS_OF"
                    if raw.get("role") in _V3_BALANCE_RAW_FIELD_ROLES
                    or (not multi_source and cell.get("layer") in {"WORKING_CAPITAL", "FINANCING"})
                    else "FLOW_PERIOD"
                )
                if raw_clock.get("clock_kind") != expected_kind:
                    findings.append(raw_path + ".raw_role_clock_kind_mismatch")
                if fiscal_year:
                    expected_end = f"{fiscal_year}-12-31"
                    actual_end = _clock_date(raw_clock, "balance_as_of" if expected_kind == "BALANCE_AS_OF" else "flow_period")
                    if actual_end != expected_end:
                        findings.append(raw_path + ".raw_fiscal_period_does_not_match_field_identity")
            expected_period_column = (
                f"{_event_start(raw_clock)}..{_event_end(raw_clock)}"
                if raw_clock.get("clock_kind") == "EVENT_WINDOW"
                else _mapping(raw_clock.get("flow_period") or raw_clock.get("balance_as_of")).get("fiscal_period")
                or _mapping(raw_clock.get("balance_as_of")).get("as_of")
            )
            field_identity = _mapping(cell.get("field_identity"))
            if not multi_source and locator.get("table_or_note") != field_identity.get("table_or_note"):
                findings.append(raw_path + ".locator.table_or_note_must_match_frozen_field_identity")
            if not multi_source and locator.get("line_item") != field_identity.get("line_item"):
                findings.append(raw_path + ".locator.line_item_must_match_frozen_field_identity")
            if locator.get("period_column") != expected_period_column:
                findings.append(raw_path + ".locator.period_column_must_match_measurement_clock")
            if multi_source and raw.get("role") != "EVENT":
                source = source_access_by_id.get(_text(raw.get("source_id")), {})
                raw_period_end = _clock_period_end(raw_clock)
                source_period_end = source.get("report_period_end")
                if raw_period_end is None or not isinstance(source_period_end, str) or raw_period_end > source_period_end:
                    findings.append(raw_path + ".clock_period_cannot_follow_frozen_source_report")
        formula_keys = _V3_MULTI_SOURCE_FORMULA_KEYS if multi_source else _V3_FORMULA_KEYS
        formula = _closed(cell.get("formula"), formula_keys, path + ".formula", findings)
        if formula.get("operator") not in ENTERPRISE_DETERMINISTIC_FORMULAS:
            findings.append(f"{path}.formula.operator_invalid")
        input_ids = [_text(value) for value in _items(formula.get("input_field_ids"))]
        if input_ids != raw_ids or not _text(formula.get("expression")) or not _text(formula.get("zero_baseline_rule")):
            findings.append(f"{path}.formula_must_bind_raw_input_fields")
        conversions = [_closed(raw, _V3_UNIT_CONVERSION_KEYS, f"{path}.formula.unit_conversions[{conversion_index}]", findings)
                       for conversion_index, raw in enumerate(_items(formula.get("unit_conversions")))]
        if [conversion.get("field_id") for conversion in conversions] != raw_ids:
            findings.append(f"{path}.formula.unit_conversions_must_cover_raw_inputs_in_order")
        for conversion in conversions:
            if not all(_text(conversion.get(key)) for key in ("field_id", "from_unit", "to_unit", "scale")):
                findings.append(f"{path}.formula.unit_conversion_incomplete")
        if multi_source:
            coefficients = [
                _closed(
                    raw,
                    _V3_INPUT_COEFFICIENT_KEYS,
                    f"{path}.formula.input_coefficients[{coefficient_index}]",
                    findings,
                )
                for coefficient_index, raw in enumerate(
                    _items(formula.get("input_coefficients"))
                )
            ]
            if [coefficient.get("field_id") for coefficient in coefficients] != raw_ids:
                findings.append(
                    f"{path}.formula.input_coefficients_must_cover_raw_inputs_in_order"
                )
            for coefficient in coefficients:
                if not all(
                    _text(coefficient.get(key)) for key in ("field_id", "coefficient")
                ):
                    findings.append(f"{path}.formula.input_coefficient_incomplete")
            _validate_v3_enhanced_formula_roles(
                formula.get("operator"),
                raw_inputs,
                conversions,
                coefficients,
                output_unit=unit.get("kind"),
                path=path + ".formula",
                findings=findings,
            )
        labels = _closed(cell.get("label_rule"), _LABEL_KEYS, path + ".label_rule", findings)
        label_type = labels.get("type")
        if label_type not in _LABEL_SEQUENCES or labels.get("ordered_labels") != _LABEL_SEQUENCES.get(label_type):
            findings.append(f"{path}.label_rule_invalid_or_order_not_frozen")
        if label_type == "EVENT_PRESENCE" and formula.get("operator") != "EVENT_BOOLEAN":
            findings.append(f"{path}.event_formula_operator_invalid")
        if label_type != "EVENT_PRESENCE":
            if not isinstance(labels.get("decrease_lte"), (int, float)) or not isinstance(labels.get("increase_gte"), (int, float)) or labels["decrease_lte"] >= labels["increase_gte"]:
                findings.append(f"{path}.direction_thresholds_invalid")
        conflict = _closed(cell.get("conflict_rule"), _CONFLICT_KEYS, path + ".conflict_rule", findings)
        if set(conflict.values()) != {"MEASUREMENT_MISMATCH"}:
            findings.append(f"{path}.conflict_rule_must_resolve_to_mismatch")
        unknown = _closed(cell.get("unknown_rule"), _UNKNOWN_KEYS, path + ".unknown_rule", findings)
        if unknown.get("label") != "UNKNOWN" or not _items(unknown.get("conditions")):
            findings.append(f"{path}.unknown_rule_invalid")
        mismatch = _closed(cell.get("mismatch_rule"), _MISMATCH_KEYS, path + ".mismatch_rule", findings)
        if mismatch.get("label") != "MEASUREMENT_MISMATCH" or mismatch.get("propagation") != "LOCAL_ONLY" or _items(mismatch.get("dependent_cell_ids")):
            findings.append(f"{path}.mismatch_must_be_sibling_local")
        if not _items(mismatch.get("conditions")):
            findings.append(f"{path}.mismatch_conditions_required")
        if _items(cell.get("allowed_source_types")) != ["OFFICIAL_AUDITED_ANNUAL_REPORT"]:
            findings.append(f"{path}.allowed_source_types_invalid")
    if "" in outcome_field_ids or len(outcome_field_ids) != len(set(outcome_field_ids)):
        findings.append("measurement_contract.outcome_field_ids_must_be_unique")
    combination_rules = [_closed(raw, _COMBINATION_KEYS, f"measurement_contract.thread_combination_rules[{index}]", findings)
                         for index, raw in enumerate(_items(item.get("thread_combination_rules")))]
    for index, rule in enumerate(combination_rules):
        path = f"measurement_contract.thread_combination_rules[{index}]"
        ids = [_text(value) for value in _items(rule.get("input_cell_ids"))]
        if not ids or any(value not in cell_ids for value in ids) or rule.get("evaluation_order") != ids:
            findings.append(f"{path}.input_cells_or_evaluation_order_invalid")
        if not _text(rule.get("rule")) or not _text(rule.get("conflict_rule")) or rule.get("authorization") != "TEACHING_ONLY_NO_CAUSAL_UPGRADE":
            findings.append(f"{path}.combination_rule_invalid")
    if item.get("rights") != _RIGHTS:
        findings.append("measurement_contract.rights_invalid")
    if item.get("allowed_outputs") != ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"]:
        findings.append("measurement_contract.allowed_outputs_invalid")
    return {"valid": not findings, "findings": findings, "contract": deepcopy(item) if not findings else None}


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
    if item.get("schema_version") not in {PACKAGE_SCHEMA_VERSION, PACKAGE_SCHEMA_VERSION_V3}:
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


def validate_canonical_preoutcome_package(
    package: Any,
    *,
    roster_freeze_ref: dict[str, Any],
    receipt_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate production input only after canonical ID resolution."""
    try:
        bundle, receipts = training_control.resolve_canonical_selection_inputs(roster_freeze_ref, receipt_refs)
    except training_control.TrainingControlPlaneError as exc:
        return {"valid": False, "findings": [exc.code + ":" + exc.detail], "package": None, "derived_selection": None}
    result = validate_preoutcome_package(
        package,
        block=bundle["block"],
        roster_freeze=bundle["roster_freeze"],
        receipts=receipts,
    )
    if result["valid"] and _mapping(package).get("selection", {}).get("source_roster_ref") != roster_freeze_ref.get("freeze_id"):
        result["valid"] = False
        result["findings"].append("preoutcome_package.selection.source_roster_ref_must_be_canonical_freeze_id")
        result["package"] = None
    return result


def register_and_project_preoutcome_package(
    package: Any,
    *,
    roster_freeze_ref: dict[str, Any],
    receipt_refs: list[dict[str, Any]],
    frozen_at: str,
) -> dict[str, Any]:
    """Resolve canonical IDs, register J1, then call public Frozen-J1 J2/J3 APIs."""
    validation = validate_canonical_preoutcome_package(
        package,
        roster_freeze_ref=roster_freeze_ref,
        receipt_refs=receipt_refs,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "control_plane_receipt": None}
    item = validation["package"]
    reconstruction_ref = {
        "reconstruction_id": item["reconstruction_spec"]["reconstruction_id"],
        "schema_version": "enterprise-judgment-reconstruction.v1",
    }
    try:
        canonical_conn, frozen_bundle = reconstruction_registry.reconstruction.resolve_canonical_frozen_reconstruction(
            reconstruction_ref
        )
    except reconstruction_registry.reconstruction.FrozenReconstructionRegistryError as exc:
        if exc.code not in {
            "frozen_reconstruction_registry_not_initialized",
            "frozen_reconstruction_not_registered",
            "canonical_frozen_reconstruction_registry_unavailable",
        }:
            return {"valid": False, "findings": ["j1:" + exc.code], "control_plane_receipt": None}
        registration = reconstruction_registry.register_canonical_from_artifacts(
            source_packet_receipt=item["source_packet_receipt"],
            decision_contract=item["decision_contract"],
            enterprise_model=item["enterprise_system_model"],
            decision_ledger=item["management_decision_ledger"],
            spec=item["reconstruction_spec"],
            frozen_at=frozen_at,
        )
    else:
        canonical_conn.close()
        expected_inputs = {
            "spec": item["reconstruction_spec"],
            "source_packet_receipt": item["source_packet_receipt"],
            "enterprise_model": item["enterprise_system_model"],
            "decision_ledger": item["management_decision_ledger"],
            "decision_contract": item["decision_contract"],
        }
        stored_inputs = _mapping(frozen_bundle.get("reconstruction_inputs"))
        if any(stored_inputs.get(key) != value for key, value in expected_inputs.items()):
            return {"valid": False, "findings": ["j1:canonical_inputs_do_not_match_package"], "control_plane_receipt": None}
        registration = {
            "frozen": True,
            **reconstruction_ref,
            "idempotent": True,
            "registry_role": "CANONICAL_FROZEN_J1_CONTROL_PLANE",
        }
    try:
        measurement_registration = training_control.register_measurement_contract(
            item["outcome_measurement_contract"], frozen_at=frozen_at,
        )
    except training_control.TrainingControlPlaneError as exc:
        return {"valid": False, "findings": ["measurement_contract:" + exc.code], "control_plane_receipt": None}
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
            "canonical_selection_inputs": {
                "roster_freeze_ref": deepcopy(roster_freeze_ref),
                "receipt_refs": deepcopy(receipt_refs),
                "control_plane": training_control.canonical_control_plane_path(),
            },
            "canonical_j1_registration": registration,
            "canonical_measurement_contract_registration": measurement_registration,
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
    parser.add_argument("--roster-freeze-id", required=True)
    parser.add_argument("--receipt-ref", action="append", required=True, help="canonical receipt ID@version")
    parser.add_argument("--frozen-at", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    package = _read(args.package)
    receipt_refs: list[dict[str, Any]] = []
    for raw_ref in args.receipt_ref:
        receipt_id, separator, raw_version = raw_ref.rpartition("@")
        if not separator or not raw_version.isdigit():
            parser.error("--receipt-ref must use RECEIPT_ID@VERSION")
        receipt_refs.append({"receipt_id": receipt_id, "receipt_version": int(raw_version)})
    if args.validate_only:
        result = validate_canonical_preoutcome_package(
            package,
            roster_freeze_ref={"freeze_id": args.roster_freeze_id},
            receipt_refs=receipt_refs,
        )
    else:
        result = register_and_project_preoutcome_package(
            package,
            roster_freeze_ref={"freeze_id": args.roster_freeze_id},
            receipt_refs=receipt_refs,
            frozen_at=args.frozen_at,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
