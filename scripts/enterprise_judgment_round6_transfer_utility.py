#!/usr/bin/env python3
"""Round 6 cross-company transfer and paired decision-utility training.

The module composes the existing source, decision-contract, utility and
Enterprise V3 measurement APIs.  It does not own another source registry or
settlement engine.  A paired package freezes two interpretations of the same
cutoff facts before outcome access; a later review may only compare those
interpretations against the canonical field-level settlement.
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
    from scripts import enterprise_judgment_source_packet as source_packet
    from scripts import enterprise_judgment_training_control_plane as enterprise_control
    from scripts import judgment_decision_utility as decision_utility
    from scripts import judgment_training_decision_contract as decision_contract
    from scripts import outcome_measurement_acquisition as measurement_acquisition
    from scripts import outcome_measurement_settlement_adapter as settlement_adapter
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_reconstruction as reconstruction
    import enterprise_judgment_real_mechanism_training as mechanism_training
    import enterprise_judgment_source_packet as source_packet
    import enterprise_judgment_training_control_plane as enterprise_control
    import judgment_decision_utility as decision_utility
    import judgment_training_decision_contract as decision_contract
    import outcome_measurement_acquisition as measurement_acquisition
    import outcome_measurement_settlement_adapter as settlement_adapter


PREOUTCOME_SCHEMA_VERSION = "enterprise-judgment-round6-transfer-utility-preoutcome.v1"
REVIEW_SCHEMA_VERSION = "enterprise-judgment-round6-transfer-utility-review.v1"
COMPLETION_SCHEMA_VERSION = "enterprise-judgment-round6-transfer-utility-completion.v1"
SELECTION_POLICY = (
    "EARLIEST_UNCONSUMED_IMMUTABLE_ROSTER_ROW_FOR_DIFFERENT_SOURCE_LEARNING_COMPANY"
)
BASELINE_METHOD_ID = "METHOD:AGGREGATE_ACTION_PROGRESS:V1"
ENHANCED_METHOD_ID = "METHOD:CONTROLLED_EXECUTION_SCOPE:V1"
PREOUTCOME_OUTPUTS = ["PAIRED_PREOUTCOME_RESEARCH", "OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"]
REVIEW_OUTPUTS = ["DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"]
COMPLETION_OUTPUTS = ["ROUND6_REAL_TRANSFER_UTILITY_COMPLETED", "RESEARCH_AGENDA"]
ROUND6_PRIOR_RECEIPT_FILES = [
    "05_feedback_settlement_001.json",
    "07_feedback_settlement_002.json",
    "13_round2_continuation_feedback_settlement.json",
    "20_round3_feedback_settlement.json",
    "25_round4_contract_insufficiency_adjudication.json",
]
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

_PREOUTCOME_KEYS = {
    "schema_version", "package_id", "selection", "source_learning_ref",
    "source_packet_receipt", "decision_contract", "shared_cutoff_facts",
    "baseline_view", "enhanced_view", "decision_utility_pairing",
    "outcome_measurement_contract", "strongest_rival", "contamination_boundary",
    "freeze_state", "frozen_at", "roles", "rights", "allowed_outputs",
}
_SELECTION_KEYS = {
    "selection_policy", "source_roster_ref", "source_learning_company_id",
    "source_learning_completion_id", "consumed_transition_ids", "selected_rank",
    "transition_id", "company_id", "company_cluster_id", "cutoff_at",
    "next_cutoff_at", "selection_used_outcome", "selection_used_source_convenience",
    "method_unseen_on_target",
}
_SOURCE_LEARNING_KEYS = {
    "completion_id", "artifact", "company_id", "cutoff_at", "accepted_feedback_scope",
}
_FACT_KEYS = {"fact_id", "domain", "statement", "evidence_refs"}
_VIEW_KEYS = {
    "method_id", "evidence_budget_id", "source_packet_refs", "fact_ids",
    "primary_question", "claim_matrix", "interpretation_rule",
    "expected_outcome_cell_ids", "prohibited_inferences",
}
_CLAIM_KEYS = {
    "claim_id", "domain", "statement", "state", "evidence_refs",
    "dependent_outcome_cell_ids", "allowed_outputs",
}
_REVIEW_KEYS = {
    "schema_version", "review_id", "package_ref", "utility_evaluation",
    "settlement_ref", "reviewer_id", "reviewed_at", "paired_claim_findings",
    "overall_verdict", "investor_effect", "unknowns_preserved", "limitations",
    "rights", "object_class", "claim_class", "allowed_outputs",
}
_PAIRED_FINDING_KEYS = {
    "dimension", "baseline_assessment", "enhanced_assessment", "economic_effect",
    "supporting_cell_ids", "prohibited_inference",
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
_PRIOR_RECEIPT_SCHEMAS = {
    "enterprise-judgment-feedback-settlement.v1",
    "enterprise-judgment-continuation-feedback-settlement.v1",
    "enterprise-judgment-round3-feedback-settlement.v1",
    "enterprise-mechanism-feedback-superseding-adjudication.v1",
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


def _forbidden_paths(value: Any, path: str = "round6") -> list[str]:
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


def _transition_for_receipt(receipt: dict[str, Any], roster: list[dict[str, Any]]) -> str:
    if receipt.get("schema_version") == "enterprise-mechanism-feedback-superseding-adjudication.v1":
        return str(_mapping(receipt.get("supersedes")).get("transition_id") or "")
    company_id = receipt.get("company_id")
    cutoff_at = receipt.get("cutoff_at")
    matching = [
        row for row in roster
        if row.get("company_id") == company_id and row.get("cutoff_at") == cutoff_at
    ]
    return str(matching[0].get("transition_id") or "") if len(matching) == 1 else ""


def derive_transfer_target(
    block: Any,
    roster_freeze: Any,
    prior_receipts: list[Any],
    *,
    source_learning_completion: Any,
) -> dict[str, Any]:
    """Choose the first unused row for a company different from the source learning."""
    findings: list[str] = []
    block_item = _mapping(block)
    freeze = _mapping(roster_freeze)
    roster = [_mapping(row) for row in _items(block_item.get("company_cutoff_transition_roster"))]
    if block_item.get("block_id") != freeze.get("block_id"):
        findings.append("round6_selection.block_must_match_roster_freeze")
    if [row.get("transition_id") for row in roster] != _items(freeze.get("company_cutoff_transition_ids")):
        findings.append("round6_selection.roster_must_match_immutable_freeze")
    if [row.get("rank") for row in roster] != list(range(1, len(roster) + 1)):
        findings.append("round6_selection.roster_ranks_must_be_contiguous")

    source = _mapping(source_learning_completion)
    if (
        source.get("schema_version") != "enterprise-judgment-round5-real-feedback-completion-receipt.v1"
        or source.get("feedback_turn_status") != "REAL_FEEDBACK_TURN_5_COMPLETED"
        or source.get("accepted_feedback_scope") != "LOCAL_ISSUER_CONTROLLED_EXECUTION_SCOPE"
        or source.get("transfer_status") != "NOT_AUTHORIZED"
    ):
        findings.append("round6_selection.source_learning_completion_invalid")
    source_company = str(source.get("company_id") or "")
    source_completion_id = str(source.get("completion_id") or "")
    if not source_company or not source_completion_id:
        findings.append("round6_selection.source_learning_identity_required")

    consumed: set[str] = set()
    for index, raw in enumerate(prior_receipts):
        receipt = _mapping(raw)
        if receipt.get("schema_version") not in _PRIOR_RECEIPT_SCHEMAS:
            findings.append(f"round6_selection.prior_receipts[{index}].schema_invalid")
            continue
        transition_id = _transition_for_receipt(receipt, roster)
        if transition_id not in {row.get("transition_id") for row in roster}:
            findings.append(f"round6_selection.prior_receipts[{index}].transition_binding_invalid")
        else:
            consumed.add(transition_id)
    source_transition = _transition_for_receipt(source, roster)
    if source_transition:
        consumed.add(source_transition)

    selected = next(
        (
            row for row in roster
            if row.get("transition_id") not in consumed
            and row.get("company_id") != source_company
        ),
        None,
    )
    if selected is None:
        findings.append("round6_selection.no_different_company_unconsumed_row")
    selection = None
    if not findings and selected is not None:
        selection = {
            "selection_policy": SELECTION_POLICY,
            "source_roster_ref": freeze.get("freeze_id"),
            "source_learning_company_id": source_company,
            "source_learning_completion_id": source_completion_id,
            "consumed_transition_ids": sorted(consumed),
            "selected_rank": selected.get("rank"),
            "transition_id": selected.get("transition_id"),
            "company_id": selected.get("company_id"),
            "company_cluster_id": selected.get("company_cluster_id"),
            "cutoff_at": selected.get("cutoff_at"),
            "next_cutoff_at": selected.get("next_cutoff_at"),
            "selection_used_outcome": False,
            "selection_used_source_convenience": False,
            "method_unseen_on_target": True,
        }
    return {"valid": not findings, "findings": findings, "selection": selection}


def _validate_view(
    value: Any,
    *,
    path: str,
    expected_method_id: str,
    fact_ids: set[str],
    source_ids: set[str],
    contract_cell_ids: set[str],
    evidence_budget: dict[str, Any],
    findings: list[str],
) -> dict[str, Any]:
    view = _closed(value, _VIEW_KEYS, path, findings)
    if view.get("method_id") != expected_method_id:
        findings.append(path + ".method_id_invalid")
    if view.get("evidence_budget_id") != evidence_budget.get("evidence_budget_id"):
        findings.append(path + ".evidence_budget_must_match_decision_contract")
    if view.get("source_packet_refs") != evidence_budget.get("source_packet_refs"):
        findings.append(path + ".source_packet_refs_must_match_decision_contract")
    if set(_items(view.get("fact_ids"))) != fact_ids or len(_items(view.get("fact_ids"))) != len(fact_ids):
        findings.append(path + ".must_use_all_and_only_shared_cutoff_facts")
    if not _text(view.get("primary_question")) or not _text(view.get("interpretation_rule")):
        findings.append(path + ".question_and_interpretation_required")
    expected_cells = _items(view.get("expected_outcome_cell_ids"))
    if not expected_cells or any(cell_id not in contract_cell_ids for cell_id in expected_cells):
        findings.append(path + ".expected_outcome_cells_invalid")
    prohibited = _items(view.get("prohibited_inferences"))
    if not prohibited or any(not _text(item) for item in prohibited):
        findings.append(path + ".prohibited_inferences_required")
    claims = [
        _closed(raw, _CLAIM_KEYS, f"{path}.claim_matrix[{index}]", findings)
        for index, raw in enumerate(_items(view.get("claim_matrix")))
    ]
    if not claims:
        findings.append(path + ".claim_matrix_required")
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        claim_path = f"{path}.claim_matrix[{index}]"
        claim_id = claim.get("claim_id")
        if not _text(claim_id) or claim_id in claim_ids:
            findings.append(claim_path + ".claim_id_invalid_or_duplicate")
        claim_ids.add(str(claim_id))
        if claim.get("domain") not in {
            "CUSTOMER", "COMPETITION", "OPERATIONS", "ORGANIZATION",
            "CAPITAL_ALLOCATION", "CASH", "PERMANENT_LOSS", "LIFECYCLE",
        }:
            findings.append(claim_path + ".domain_invalid")
        if claim.get("state") not in {"OBSERVED", "INFERRED", "UNKNOWN", "NOT_APPLICABLE"}:
            findings.append(claim_path + ".state_invalid")
        if not _text(claim.get("statement")):
            findings.append(claim_path + ".statement_required")
        if any(ref not in source_ids for ref in _items(claim.get("evidence_refs"))):
            findings.append(claim_path + ".evidence_ref_outside_frozen_packet")
        if any(cell_id not in contract_cell_ids for cell_id in _items(claim.get("dependent_outcome_cell_ids"))):
            findings.append(claim_path + ".dependent_outcome_cell_invalid")
        if claim.get("allowed_outputs") != ["RESEARCH_AGENDA"]:
            findings.append(claim_path + ".allowed_outputs_must_remain_research_agenda")
    return view


def validate_preoutcome_package(
    package: Any,
    *,
    block: Any,
    roster_freeze: Any,
    prior_receipts: list[Any],
    source_learning_completion: Any,
) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(package, _PREOUTCOME_KEYS, "round6_preoutcome", findings)
    if item.get("schema_version") != PREOUTCOME_SCHEMA_VERSION:
        findings.append("round6_preoutcome.schema_version_invalid")
    if item.get("freeze_state") != "PRE_OUTCOME_FROZEN":
        findings.append("round6_preoutcome.freeze_state_invalid")
    frozen_at = _instant(item.get("frozen_at"), "round6_preoutcome.frozen_at", findings)

    derived = derive_transfer_target(
        block, roster_freeze, prior_receipts,
        source_learning_completion=source_learning_completion,
    )
    findings.extend("selection:" + finding for finding in derived["findings"])
    selection = _closed(item.get("selection"), _SELECTION_KEYS, "round6_preoutcome.selection", findings)
    if derived["selection"] is not None and selection != derived["selection"]:
        findings.append("round6_preoutcome.selection_must_be_mechanically_derived")

    learning_ref = _closed(
        item.get("source_learning_ref"), _SOURCE_LEARNING_KEYS,
        "round6_preoutcome.source_learning_ref", findings,
    )
    source = _mapping(source_learning_completion)
    if learning_ref != {
        "completion_id": source.get("completion_id"),
        "artifact": "36_round5_real_feedback_completion_receipt.json",
        "company_id": source.get("company_id"),
        "cutoff_at": source.get("cutoff_at"),
        "accepted_feedback_scope": source.get("accepted_feedback_scope"),
    }:
        findings.append("round6_preoutcome.source_learning_ref_invalid")

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
    for component_name, component in (
        ("source_packet", source_receipt),
        ("decision_contract", decision),
        ("measurement_contract", measurement),
    ):
        if component.get("company_id") != selection.get("company_id"):
            findings.append(f"round6_preoutcome.{component_name}.company_must_match_selection")
        if component.get("cutoff_at") != selection.get("cutoff_at"):
            findings.append(f"round6_preoutcome.{component_name}.cutoff_must_match_selection")
    if measurement.get("package_ref") != item.get("package_id"):
        findings.append("round6_preoutcome.measurement_contract.package_ref_must_match")
    if str(measurement.get("package_ref") or "").startswith("EMFP:"):
        findings.append("round6_preoutcome.must_use_generic_enterprise_v3_route")
    if frozen_at is not None and measurement.get("contract_frozen_at") != frozen_at.isoformat():
        findings.append("round6_preoutcome.measurement_contract.freeze_time_must_match")

    roles = _closed(item.get("roles"), _ROLES_KEYS, "round6_preoutcome.roles", findings)
    if roles != decision.get("roles") or len(set(roles.values())) != len(_ROLES_KEYS):
        findings.append("round6_preoutcome.roles_must_match_independent_decision_contract_roles")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != PREOUTCOME_OUTPUTS:
        findings.append("round6_preoutcome.rights_or_outputs_invalid")
    if item.get("contamination_boundary") != {
        "historical_replay_status": "MODEL_MEMORY_MITIGATED",
        "repository_contains_later_summary": True,
        "score_authority": "NONE",
        "allowed_use": "DEVELOPMENT_TRANSFER_UTILITY_ONLY",
    }:
        findings.append("round6_preoutcome.contamination_boundary_invalid")
    if not _text(item.get("strongest_rival")):
        findings.append("round6_preoutcome.strongest_rival_required")

    facts = [
        _closed(raw, _FACT_KEYS, f"round6_preoutcome.shared_cutoff_facts[{index}]", findings)
        for index, raw in enumerate(_items(item.get("shared_cutoff_facts")))
    ]
    fact_ids = {str(fact.get("fact_id") or "") for fact in facts}
    if not facts or "" in fact_ids or len(fact_ids) != len(facts):
        findings.append("round6_preoutcome.shared_cutoff_fact_ids_invalid")
    source_ids = {str(source_item.get("source_id")) for source_item in _items(source_receipt.get("sources"))}
    for index, fact in enumerate(facts):
        if not _text(fact.get("statement")) or not _items(fact.get("evidence_refs")):
            findings.append(f"round6_preoutcome.shared_cutoff_facts[{index}].statement_and_evidence_required")
        if any(ref not in source_ids for ref in _items(fact.get("evidence_refs"))):
            findings.append(f"round6_preoutcome.shared_cutoff_facts[{index}].evidence_outside_source_packet")

    cell_ids = {str(cell.get("cell_id")) for cell in _items(measurement.get("atomic_cells"))}
    budget = _mapping(decision.get("evidence_budget"))
    baseline = _validate_view(
        item.get("baseline_view"), path="round6_preoutcome.baseline_view",
        expected_method_id=BASELINE_METHOD_ID, fact_ids=fact_ids, source_ids=source_ids,
        contract_cell_ids=cell_ids, evidence_budget=budget, findings=findings,
    )
    enhanced = _validate_view(
        item.get("enhanced_view"), path="round6_preoutcome.enhanced_view",
        expected_method_id=ENHANCED_METHOD_ID, fact_ids=fact_ids, source_ids=source_ids,
        contract_cell_ids=cell_ids, evidence_budget=budget, findings=findings,
    )
    pairing = _mapping(item.get("decision_utility_pairing"))
    if _mapping(pairing.get("baseline")).get("method_id") != baseline.get("method_id"):
        findings.append("round6_preoutcome.baseline_method_must_match_pairing")
    if _mapping(pairing.get("enhanced")).get("method_id") != enhanced.get("method_id"):
        findings.append("round6_preoutcome.enhanced_method_must_match_pairing")
    required_enhanced = {
        "CELL:600801:20160427:ACTION_PROGRESS",
        "CELL:600801:20160427:DECISION_CONTROL",
        "CELL:600801:20160427:ISSUER_PRODUCT_PARTICIPATION",
        "CELL:600801:20160427:CONSOLIDATION_SCOPE",
        "CELL:600801:20160427:CUSTOMER_RESPONSE",
    }
    if not required_enhanced.issubset(set(_items(enhanced.get("expected_outcome_cell_ids")))):
        findings.append("round6_preoutcome.enhanced_view_must_split_control_product_consolidation_customer_cells")
    if "CELL:600801:20160427:ACTION_PROGRESS" not in _items(baseline.get("expected_outcome_cell_ids")):
        findings.append("round6_preoutcome.baseline_view_must_freeze_aggregate_action_progress")
    if _forbidden_paths(item):
        findings.extend("round6_preoutcome.forbidden_field:" + path for path in _forbidden_paths(item))
    return {"valid": not findings, "findings": findings, "package": deepcopy(item) if not findings else None}


def validate_utility_review(
    review: Any,
    *,
    package: Any,
    settlement: Any,
) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(review, _REVIEW_KEYS, "round6_review", findings)
    if item.get("schema_version") != REVIEW_SCHEMA_VERSION:
        findings.append("round6_review.schema_version_invalid")
    package_item = _mapping(package)
    settlement_item = _mapping(settlement)
    if item.get("package_ref") != package_item.get("package_id"):
        findings.append("round6_review.package_ref_must_match")
    if item.get("settlement_ref") != settlement_item.get("settlement_id"):
        findings.append("round6_review.settlement_ref_must_match")
    if settlement_item.get("company_id") != _mapping(package_item.get("selection")).get("company_id"):
        findings.append("round6_review.settlement_company_must_match_selection")
    if settlement_item.get("measurement_contract_ref") != {
        "measurement_contract_id": _mapping(package_item.get("outcome_measurement_contract")).get("contract_set_id"),
        "measurement_contract_version": 3,
    }:
        findings.append("round6_review.settlement_contract_must_match_frozen_package")
    utility = _mapping(item.get("utility_evaluation"))
    utility_result = decision_utility.validate_decision_utility_evaluation(
        utility,
        pairing=package_item.get("decision_utility_pairing"),
        contract=package_item.get("decision_contract"),
    )
    findings.extend("utility_evaluation:" + finding for finding in utility_result["findings"])
    if utility.get("outcome_settlement_ref") != settlement_item.get("settlement_id"):
        findings.append("round6_review.utility_evaluation_settlement_ref_must_match")
    if item.get("reviewer_id") != utility.get("reviewer_id"):
        findings.append("round6_review.reviewer_must_match_utility_evaluation")
    _instant(item.get("reviewed_at"), "round6_review.reviewed_at", findings)
    if item.get("overall_verdict") not in {
        "ENHANCED_AVOIDED_MATERIAL_ERROR", "NO_MATERIAL_DIFFERENCE",
        "ENHANCED_IMPROVED_KEY_UNKNOWN", "BASELINE_BETTER", "NOT_DIAGNOSTIC",
    }:
        findings.append("round6_review.overall_verdict_invalid")
    if not _text(item.get("investor_effect")):
        findings.append("round6_review.investor_effect_required")
    if not _items(item.get("limitations")) or any(not _text(value) for value in _items(item.get("limitations"))):
        findings.append("round6_review.limitations_required")
    if not isinstance(item.get("unknowns_preserved"), list):
        findings.append("round6_review.unknowns_preserved_must_be_list")
    settled_cells = {row.get("cell_id") for row in _items(settlement_item.get("cell_results"))}
    paired = [
        _closed(raw, _PAIRED_FINDING_KEYS, f"round6_review.paired_claim_findings[{index}]", findings)
        for index, raw in enumerate(_items(item.get("paired_claim_findings")))
    ]
    if not paired:
        findings.append("round6_review.paired_claim_findings_required")
    for index, finding in enumerate(paired):
        path = f"round6_review.paired_claim_findings[{index}]"
        if not all(_text(finding.get(key)) for key in (
            "dimension", "baseline_assessment", "enhanced_assessment",
            "economic_effect", "prohibited_inference",
        )):
            findings.append(path + ".material_fields_required")
        if any(cell_id not in settled_cells for cell_id in _items(finding.get("supporting_cell_ids"))):
            findings.append(path + ".supporting_cell_not_in_settlement")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != REVIEW_OUTPUTS:
        findings.append("round6_review.rights_or_outputs_invalid")
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_TRANSFER_UTILITY_REVIEW":
        findings.append("round6_review.object_class_invalid")
    if item.get("claim_class") != "PAIRED_MATERIAL_DECISION_UTILITY_REVIEW":
        findings.append("round6_review.claim_class_invalid")
    return {"valid": not findings, "findings": findings, "review": deepcopy(item) if not findings else None}


def validate_completion_receipt(
    receipt: Any,
    *,
    package: Any,
    settlement: Any,
    review: Any,
) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(receipt, _COMPLETION_KEYS, "round6_completion", findings)
    if item.get("schema_version") != COMPLETION_SCHEMA_VERSION:
        findings.append("round6_completion.schema_version_invalid")
    package_item, settlement_item, review_item = _mapping(package), _mapping(settlement), _mapping(review)
    if item.get("package_ref") != package_item.get("package_id"):
        findings.append("round6_completion.package_ref_must_match")
    if item.get("settlement_ref") != settlement_item.get("settlement_id"):
        findings.append("round6_completion.settlement_ref_must_match")
    if item.get("review_ref") != review_item.get("review_id"):
        findings.append("round6_completion.review_ref_must_match")
    selection = _mapping(package_item.get("selection"))
    if item.get("company_id") != selection.get("company_id") or item.get("cutoff_at") != selection.get("cutoff_at"):
        findings.append("round6_completion.company_and_cutoff_must_match_selection")
    if item.get("status") != "ROUND6_REAL_TRANSFER_UTILITY_COMPLETED":
        findings.append("round6_completion.status_invalid")
    for field in ("investor_summary",):
        if not _text(item.get(field)):
            findings.append(f"round6_completion.{field}_required")
    for field in ("proved", "not_proved", "next_research_action"):
        if not _items(item.get(field)) or any(not _text(value) for value in _items(item.get(field))):
            findings.append(f"round6_completion.{field}_required")
    if item.get("rights") != RIGHTS or item.get("allowed_outputs") != COMPLETION_OUTPUTS:
        findings.append("round6_completion.rights_or_outputs_invalid")
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_ROUND6_COMPLETION_RECEIPT":
        findings.append("round6_completion.object_class_invalid")
    if item.get("claim_class") != "REAL_CROSS_COMPANY_PAIRED_UTILITY_COMPLETION":
        findings.append("round6_completion.claim_class_invalid")
    return {"valid": not findings, "findings": findings, "receipt": deepcopy(item) if not findings else None}


def _event_clock() -> dict[str, Any]:
    return {
        "clock_kind": "EVENT_WINDOW",
        "event_window": {
            "event_start": "2016-04-28",
            "event_end": "2016-12-31",
            "window_name": "POST_CUTOFF_FY2016_EVENT_WINDOW",
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
        "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:600801",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "arena_id": "ARENA:CN:CEMENT:MULTI_REGION_DELIVERED_MARKET",
        "scope_requirement": scope,
    }


def _raw(field_id: str, role: str, unit: str, clock: dict[str, Any], table: str, line: str) -> dict[str, Any]:
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


def _conversion(raw: dict[str, Any], to_unit: str) -> dict[str, str]:
    return {
        "field_id": raw["field_id"], "from_unit": raw["unit"],
        "to_unit": to_unit, "scale": "1",
    }


def _event_cell(cell_id: str, layer: str, line: str, prohibited: str) -> dict[str, Any]:
    clock = _event_clock()
    field_id = "FIELD:600801:FY2016:" + cell_id.rsplit(":", 1)[-1] + "_EVENT"
    table = "FY2016 management discussion or material investment disclosure"
    raw = _raw(field_id, "EVENT", "BOOLEAN_EVENT", clock, table, line)
    return {
        "cell_id": cell_id,
        "thread_id": "THREAD:600801:SUPPORT_TO_CONTROL",
        "layer": layer,
        "outcome_period": {
            "period_start": "2016-04-28T00:00:00+08:00",
            "period_end": "2016-12-31T23:59:59+08:00",
            "fiscal_period": "FY2016",
        },
        "measurement_clock": clock,
        "responsibility_boundary": _boundary("issuer-specific support, control, product participation and consolidation must remain distinct"),
        "field_identity": {
            "outcome_field_id": field_id, "baseline_field_id": "",
            "statement_scope": "ISSUER_COMMERCIAL_AND_CONTROL_EVENT",
            "table_or_note": table, "line_item": line, "field_kind": "DISCLOSED_EVENT",
        },
        "unit": {"kind": "EVENT", "currency": "NOT_APPLICABLE", "scale": "BOOLEAN"},
        "raw_input_fields": [raw],
        "formula": {
            "operator": "EVENT_BOOLEAN", "input_field_ids": [field_id],
            "expression": f"explicit_event({field_id})", "unit_conversions": [_conversion(raw, "BOOLEAN_EVENT")],
            "zero_baseline_rule": "NOT_APPLICABLE",
        },
        "label_rule": {
            "type": "EVENT_PRESENCE", "decrease_lte": 0, "increase_gte": 1,
            "ordered_labels": ["MEASUREMENT_MISMATCH", "OBSERVED_YES", "OBSERVED_NO", "UNKNOWN"],
        },
        "conflict_rule": {"multiple_values": "MEASUREMENT_MISMATCH", "boundary_conflict": "MEASUREMENT_MISMATCH", "period_conflict": "MEASUREMENT_MISMATCH"},
        "unknown_rule": {"conditions": ["no explicit positive or negative event evidence"], "label": "UNKNOWN"},
        "mismatch_rule": {"conditions": ["source boundary, period or event identity conflicts"], "label": "MEASUREMENT_MISMATCH", "propagation": "LOCAL_ONLY", "dependent_cell_ids": []},
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": prohibited,
    }


def _change_cell(
    cell_id: str,
    layer: str,
    table: str,
    line: str,
    unit: str,
    *,
    balance: bool = False,
    difference: bool = False,
    prohibited: str,
) -> dict[str, Any]:
    baseline_clock = _balance_clock(2015) if balance else _flow_clock(2015)
    outcome_clock = _balance_clock(2016) if balance else _flow_clock(2016)
    suffix = cell_id.rsplit(":", 1)[-1]
    baseline_id = f"FIELD:600801:FY2015:{suffix}"
    outcome_id = f"FIELD:600801:FY2016:{suffix}"
    baseline = _raw(baseline_id, "BASELINE", unit, baseline_clock, table, line)
    outcome = _raw(outcome_id, "OUTCOME", unit, outcome_clock, table, line)
    operator = "DIFFERENCE" if difference else "PERCENT_CHANGE"
    label_type = "ABSOLUTE_CHANGE_BAND" if difference else "PERCENT_CHANGE_BAND"
    threshold = 0.02 if difference else 0.05
    return {
        "cell_id": cell_id,
        "thread_id": "THREAD:600801:OPERATING_CASH_CAPITAL",
        "layer": layer,
        "outcome_period": {
            "period_start": "2016-01-01T00:00:00+08:00",
            "period_end": "2016-12-31T23:59:59+08:00",
            "fiscal_period": "FY2016",
        },
        "measurement_clock": outcome_clock,
        "responsibility_boundary": _boundary("issuer-consolidated same-definition field; action attribution prohibited"),
        "field_identity": {
            "outcome_field_id": outcome_id, "baseline_field_id": baseline_id,
            "statement_scope": "CONSOLIDATED", "table_or_note": table,
            "line_item": line, "field_kind": "AUDITED_OR_OPERATING_LINE_ITEM",
        },
        "unit": {"kind": "RATIO" if difference else "PERCENT_CHANGE", "currency": "RMB" if unit == "RMB" else "NOT_APPLICABLE", "scale": "1"},
        "raw_input_fields": [baseline, outcome],
        "formula": {
            "operator": operator,
            "input_field_ids": [baseline_id, outcome_id],
            "expression": "outcome - baseline" if difference else "(outcome - baseline) / abs(baseline)",
            "unit_conversions": [_conversion(baseline, unit), _conversion(outcome, unit)],
            "zero_baseline_rule": "NOT_APPLICABLE" if difference else "RETURN_MEASUREMENT_MISMATCH",
        },
        "label_rule": {
            "type": label_type, "decrease_lte": -threshold, "increase_gte": threshold,
            "ordered_labels": ["MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE", "OBSERVED_INCREASE", "UNKNOWN"],
        },
        "conflict_rule": {"multiple_values": "MEASUREMENT_MISMATCH", "boundary_conflict": "MEASUREMENT_MISMATCH", "period_conflict": "MEASUREMENT_MISMATCH"},
        "unknown_rule": {"conditions": ["one or more contracted raw fields absent"], "label": "UNKNOWN"},
        "mismatch_rule": {"conditions": ["scope, period, unit or unique-field conflict"], "label": "MEASUREMENT_MISMATCH", "propagation": "LOCAL_ONLY", "dependent_cell_ids": []},
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": prohibited,
    }


def build_real_preoutcome_package(
    *,
    block: dict[str, Any],
    roster_freeze: dict[str, Any],
    prior_receipts: list[dict[str, Any]],
    source_learning_completion: dict[str, Any],
    frozen_at: str,
) -> dict[str, Any]:
    """Build the fixed real Round 6 pre-outcome package from cutoff-visible facts."""
    selection_result = derive_transfer_target(
        block, roster_freeze, prior_receipts,
        source_learning_completion=source_learning_completion,
    )
    if not selection_result["valid"]:
        raise ValueError("round6 selection invalid: " + "; ".join(selection_result["findings"]))
    selection = selection_result["selection"]
    package_id = "EJTU:CN:CEMENT:600801:20160427:V1"
    source_id = "CNINFO:600801:ANN:20160331:1202113147"
    source_ref = {"receipt_id": "SP:CN600801:20160427:FY2015", "receipt_version": 1}
    roles = {
        "judgment_owner_id": "ROLE:CEMENT:ROUND6:JUDGMENT_OWNER",
        "independent_challenger_id": "ROLE:CEMENT:ROUND6:INDEPENDENT_CHALLENGER",
        "outcome_custodian_id": "ROLE:CEMENT:ROUND6:OUTCOME_CUSTODIAN",
    }
    source_receipt = {
        "schema_version": "enterprise-judgment-source-packet-receipt.v1",
        "packet_id": source_ref["receipt_id"], "packet_version": 1,
        "company_id": "CN:600801", "issuer_id": "ISSUER:CN:600801",
        "cutoff_at": "2016-04-27T00:00:00+08:00",
        "sources": [{
            "source_id": source_id,
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": "https://static.cninfo.com.cn/finalpage/2016-03-31/1202113147.PDF",
            "published_on": "2016-03-31", "available_on": "2016-03-31",
            "availability_timezone": "Asia/Shanghai", "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": ["ISSUER_CONSOLIDATED:CN:600801"],
            "responsibility_perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB", "access_mode": "REMOTE_OFFICIAL_LOCATOR",
            "locators": [
                {"research_question_id": "Q:R6:INDUSTRY_AND_OPERATING_BASELINE", "locator": "FY2015 annual report PDF pp.10-11: demand, price, digital channel, cost, volume, product economics and operating cash."},
                {"research_question_id": "Q:R6:SUPPORT_CONTROL_SCOPE", "locator": "FY2015 annual report PDF p.27: board-approved operating-support agreement for 15 Lafarge Yunnan companies and the disclosed service scope."},
                {"research_question_id": "Q:R6:PLAN_AND_CAPITAL_RESILIENCE", "locator": "FY2015 annual report PDF pp.17,50,54: 2016 operating plan, short-term debt, operating cash and cash capex."},
            ],
        }],
        "object_class": "SOURCE_PACKET_RECEIPT",
        "claim_class": "CUTOFF_ELIGIBLE_SOURCE_RECEIPT",
        "allowed_outputs": ["SOURCE_PACKET_READ_MODEL", "RESEARCH_AGENDA"],
    }
    decision = {
        "schema_version": "turtle-training-decision-contract.v1",
        "contract_id": "DC:CN600801:20160427:TRANSFER_UTILITY", "contract_version": 1,
        "company_id": "CN:600801", "issuer_id": "ISSUER:CN:600801",
        "cutoff_at": "2016-04-27T00:00:00+08:00", "decision_purpose": "HISTORICAL_TRAINING",
        "holding_horizon": {"minimum_years": 1, "maximum_years": 5},
        "permanent_loss_constraints": [{
            "constraint_id": "PLC:600801:SUPPORT_IS_NOT_CONTROL",
            "condition": "A support agreement or acquisition approval cannot be credited as issuer-controlled earnings capacity without decision control, product participation and consolidation evidence.",
            "required_treatment": "Keep control, product participation, consolidation, customer response and capital burden as separate cells; preserve UNKNOWN locally.",
        }],
        "decision_flip_questions": [
            {"question_id": "DQ:600801:SUPPORT_TO_CONTROL", "statement": "Did the 15-company support agreement become an issuer-controlled and consolidated operating scope?", "decision_effect": "Only a control-and-perimeter bridge can add the supported plants to issuer operating capacity or normal earnings."},
            {"question_id": "DQ:600801:OPERATING_CASH", "statement": "Did volume and unit economics improve without weakening operating cash, capex burden or financing resilience?", "decision_effect": "Activity growth purchased through margin, cash or debt deterioration cannot be credited as value creation."},
            {"question_id": "DQ:600801:PERMANENT_LOSS", "statement": "Did the next period reveal a direct irreversible loss or solvency event?", "decision_effect": "A one-year operating change cannot by itself establish permanent loss."},
        ],
        "evidence_budget": {"evidence_budget_id": "BUDGET:CN600801:20160427:FY2015", "source_packet_refs": [source_ref]},
        "price_and_opportunity_cost_policy": "PROHIBITED_FOR_HISTORICAL_TRAINING",
        "outcome_access": "NONE", "roles": roles,
        "object_class": "DECISION_CONTRACT", "claim_class": "EX_ANTE_DECISION_SCOPE",
        "allowed_outputs": ["CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"],
    }
    facts = [
        {"fact_id": "FACT:R6:INDUSTRY_PRESSURE", "domain": "COMPETITION", "statement": "FY2015 national cement demand fell 5.3%, industry profit fell 58%, and the issuer's cement pretax price fell RMB32 per tonne.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R6:DIGITAL_CUSTOMER_CHANNEL", "domain": "CUSTOMER", "statement": "Online orders represented 81% of issuer cement sales and core markets represented more than 80% of volume, without direct retention or market-share evidence.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R6:COST_RESPONSE", "domain": "OPERATIONS", "statement": "The issuer reported cement production cost down RMB8 per tonne or 4.4% after procurement and operating changes.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R6:SUPPORT_AGREEMENT", "domain": "ORGANIZATION", "statement": "The board approved a fee-based operating-support agreement covering industrial, technical, procurement, sales, finance, people and plant operations for 15 Lafarge Yunnan companies.", "evidence_refs": [source_id]},
        {"fact_id": "FACT:R6:FORWARD_PLAN", "domain": "CAPITAL_ALLOCATION", "statement": "The FY2016 plan targeted 7% cement-and-clinker volume growth while emphasizing cost, customer and integration initiatives; it was explicitly not a performance commitment.", "evidence_refs": [source_id]},
    ]
    cells = [
        _event_cell("CELL:600801:20160427:ACTION_PROGRESS", "IMPLEMENTED", "explicit board or regulatory approval advancing the 15-company relationship toward acquisition or integration", "Approval is not closing, control, consolidation or operating attribution."),
        _event_cell("CELL:600801:20160427:DECISION_CONTROL", "EXECUTED", "explicit issuer decision control over the 15 supported companies", "Service provision, shareholder affiliation or approval cannot substitute for actual decision control."),
        _event_cell("CELL:600801:20160427:ISSUER_PRODUCT_PARTICIPATION", "EXECUTED", "explicit issuer-product production or sales participation within the 15-company scope", "Support services or group products cannot be attributed to issuer products."),
        _event_cell("CELL:600801:20160427:CONSOLIDATION_SCOPE", "EXECUTED", "explicit inclusion of the 15-company assets in the issuer consolidated perimeter", "Approval or an agreement cannot substitute for consolidation evidence."),
        _event_cell("CELL:600801:20160427:CUSTOMER_RESPONSE", "CUSTOMER_RESPONSE", "direct issuer customer, order, retention, channel or market-share response tied to the 15-company scope", "Aggregate volume cannot substitute for direct customer response."),
        _change_cell("CELL:600801:20160427:CEMENT_CLINKER_SALES_VOLUME", "SALES_VOLUME", "production-sales-inventory analysis", "cement and clinker sales volume", "TONNE", prohibited="Volume direction is issuer state, not support-agreement or acquisition effect."),
        _change_cell("CELL:600801:20160427:CEMENT_GROSS_MARGIN", "GROSS_MARGIN", "principal business by product", "cement gross-margin ratio", "RATIO", difference=True, prohibited="Margin direction cannot be attributed to the support agreement or acquisition approval."),
        _change_cell("CELL:600801:20160427:OPERATING_CASH", "CASH", "consolidated cash-flow statement", "net cash flows from operating activities", "RMB", prohibited="Operating cash is not owner cash or acquisition-effect cash."),
        _change_cell("CELL:600801:20160427:CASH_CAPEX", "CAPITAL_BURDEN", "consolidated cash-flow statement", "cash paid to acquire and construct fixed assets, intangible assets and other long-term assets", "RMB", prohibited="Lower cash capex cannot automatically be credited as better capital allocation."),
        _change_cell("CELL:600801:20160427:SHORT_TERM_BORROWINGS", "FINANCING", "consolidated balance sheet", "short-term borrowings", "RMB", balance=True, prohibited="Debt direction alone does not establish solvency or permanent loss."),
        _event_cell("CELL:600801:20160427:DIRECT_LOSS_EVENT", "PERMANENT_LOSS", "direct issuer-level irreversible capital-loss, default, covenant or going-concern event", "The absence of one disclosed event does not prove permanent-loss risk is absent."),
    ]
    measurement = {
        "schema_version": "enterprise-outcome-measurement-contract.v3",
        "contract_set_id": "OMC:CN600801:20160427:TRANSFER_UTILITY:V3",
        "package_ref": package_id, "company_id": "CN:600801",
        "cutoff_at": "2016-04-27T00:00:00+08:00",
        "outcome_window": {
            "period_start": "2016-04-28T00:00:00+08:00",
            "period_end": "2016-12-31T23:59:59+08:00",
            "fiscal_period": "FY2016",
            "settlement_due_at": "2017-04-13T00:00:00+08:00",
        },
        "source_access": {
            "source_id": "CNINFO:600801:ANN:20170324:1203190337",
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": "https://static.cninfo.com.cn/finalpage/2017-03-24/1203190337.PDF",
            "published_after_cutoff": True, "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
            "custodian_access": "OUTCOME_ONLY", "issuer_id": "ISSUER:CN:600801",
            "report_period_end": "2016-12-31", "availability_precision": "DATE_ONLY",
            "source_available_at": None, "source_available_date": "2017-03-24",
            "authorization_receipt_id": "OAA:CN600801:20160427:FY2016:R6:V1",
        },
        "atomic_cells": cells,
        "thread_combination_rules": [
            {"rule_id": "COMBINE:600801:SUPPORT_TO_CONTROL", "thread_id": "THREAD:600801:SUPPORT_TO_CONTROL", "input_cell_ids": [cell["cell_id"] for cell in cells[:5]], "evaluation_order": [cell["cell_id"] for cell in cells[:5]], "rule": "Report each atomic label. Action progress cannot establish issuer-controlled execution unless decision control, issuer-product participation and consolidation are independently observed; customer response remains separate.", "conflict_rule": "Any local UNKNOWN or mismatch stays local and cannot be replaced by aggregate volume.", "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE"},
            {"rule_id": "COMBINE:600801:OPERATING_CASH_CAPITAL", "thread_id": "THREAD:600801:OPERATING_CASH_CAPITAL", "input_cell_ids": [cell["cell_id"] for cell in cells[5:]], "evaluation_order": [cell["cell_id"] for cell in cells[5:]], "rule": "Operating, cash, financing and loss-event cells describe issuer state only; no cell attributes an effect to the support agreement or acquisition.", "conflict_rule": "Mixed state is reported without a company score or causal label.", "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE"},
        ],
        "rights": {key: value for key, value in RIGHTS.items() if key != "method_transfer"},
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
        "freeze_state": "PRE_OUTCOME_FROZEN", "contract_frozen_at": frozen_at,
        "clock_policy": "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK",
    }
    all_fact_ids = [fact["fact_id"] for fact in facts]
    all_cells = [cell["cell_id"] for cell in cells]
    baseline_view = {
        "method_id": BASELINE_METHOD_ID,
        "evidence_budget_id": decision["evidence_budget"]["evidence_budget_id"],
        "source_packet_refs": [source_ref], "fact_ids": all_fact_ids,
        "primary_question": "Did the broad operating-support relationship make material operating progress?",
        "claim_matrix": [
            {"claim_id": "CLAIM:R6:BASELINE:ACTION_PROGRESS", "domain": "ORGANIZATION", "statement": "The signed full-function support agreement is treated as one aggregate action-progress signal; control and consolidation are not separate baseline questions.", "state": "INFERRED", "evidence_refs": [source_id], "dependent_outcome_cell_ids": [all_cells[0]], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:BASELINE:OPERATING", "domain": "OPERATIONS", "statement": "The baseline checks aggregate volume, margin and cash direction without attributing them to the support agreement.", "state": "OBSERVED", "evidence_refs": [source_id], "dependent_outcome_cell_ids": all_cells[5:9], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:BASELINE:PERMANENT_LOSS", "domain": "PERMANENT_LOSS", "statement": "Permanent loss cannot be established from the cutoff packet.", "state": "UNKNOWN", "evidence_refs": [], "dependent_outcome_cell_ids": [all_cells[-1]], "allowed_outputs": ["RESEARCH_AGENDA"]},
        ],
        "interpretation_rule": "A later formal acquisition or integration approval counts as aggregate action progress, but does not by itself authorize a causal or management-quality conclusion.",
        "expected_outcome_cell_ids": [all_cells[0], *all_cells[5:]],
        "prohibited_inferences": ["No action-effect attribution from aggregate issuer results.", "No management-quality or permanent-loss conclusion from one period."],
    }
    enhanced_view = {
        "method_id": ENHANCED_METHOD_ID,
        "evidence_budget_id": decision["evidence_budget"]["evidence_budget_id"],
        "source_packet_refs": [source_ref], "fact_ids": all_fact_ids,
        "primary_question": "Which parts of the support relationship became issuer-controlled, issuer-product-bearing, consolidated and customer-validated?",
        "claim_matrix": [
            {"claim_id": "CLAIM:R6:ENHANCED:FORMAL_SUPPORT", "domain": "ORGANIZATION", "statement": "The support agreement and its broad service scope are observed, while later action progress remains a separate outcome cell.", "state": "OBSERVED", "evidence_refs": [source_id], "dependent_outcome_cell_ids": [all_cells[0]], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:ENHANCED:CONTROL", "domain": "ORGANIZATION", "statement": "Issuer decision control over the 15 companies is unknown at cutoff.", "state": "UNKNOWN", "evidence_refs": [], "dependent_outcome_cell_ids": [all_cells[1]], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:ENHANCED:PRODUCT", "domain": "OPERATIONS", "statement": "Issuer-product participation inside the supported scope is unknown at cutoff.", "state": "UNKNOWN", "evidence_refs": [], "dependent_outcome_cell_ids": [all_cells[2]], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:ENHANCED:CONSOLIDATION", "domain": "LIFECYCLE", "statement": "The supported companies are not treated as issuer consolidated capacity without direct perimeter evidence.", "state": "UNKNOWN", "evidence_refs": [], "dependent_outcome_cell_ids": [all_cells[3]], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:ENHANCED:CUSTOMER", "domain": "CUSTOMER", "statement": "Online-order penetration is observed for the issuer, but direct customer response tied to the 15-company scope is unknown.", "state": "UNKNOWN", "evidence_refs": [source_id], "dependent_outcome_cell_ids": [all_cells[4]], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:ENHANCED:OPERATING_CASH", "domain": "CASH", "statement": "Volume, unit economics, cash, capex and financing must be read separately as issuer state.", "state": "OBSERVED", "evidence_refs": [source_id], "dependent_outcome_cell_ids": all_cells[5:10], "allowed_outputs": ["RESEARCH_AGENDA"]},
            {"claim_id": "CLAIM:R6:ENHANCED:PERMANENT_LOSS", "domain": "PERMANENT_LOSS", "statement": "Permanent loss remains unknown absent a direct event or a separate multi-period persistence contract.", "state": "UNKNOWN", "evidence_refs": [], "dependent_outcome_cell_ids": [all_cells[-1]], "allowed_outputs": ["RESEARCH_AGENDA"]},
        ],
        "interpretation_rule": "Formal progress is reported, but operating execution credit requires separate decision-control, issuer-product and consolidation evidence; customer response and issuer financial state remain independent.",
        "expected_outcome_cell_ids": all_cells,
        "prohibited_inferences": ["Approval is not closing, control, consolidation or issuer earnings capacity.", "Group or supported-company products are not issuer products without direct evidence.", "Issuer financial changes are not action effects."],
    }
    pairing = {
        "schema_version": "turtle-decision-utility-pairing.v1",
        "pairing_id": "DUPAIR:CN600801:20160427:R6:V1",
        "decision_contract_ref": {"contract_id": decision["contract_id"], "contract_version": 1},
        "baseline": {"method_id": BASELINE_METHOD_ID, "decision_status": "RESEARCH", "material_unknown_ids": ["UNKNOWN:ACTION_EFFECT", "UNKNOWN:PERMANENT_LOSS"], "evidence_budget_id": decision["evidence_budget"]["evidence_budget_id"], "source_packet_refs": [source_ref], "research_cost_hours": 0},
        "enhanced": {"method_id": ENHANCED_METHOD_ID, "decision_status": "RESEARCH", "material_unknown_ids": ["UNKNOWN:DECISION_CONTROL", "UNKNOWN:ISSUER_PRODUCT_PARTICIPATION", "UNKNOWN:CONSOLIDATION_SCOPE", "UNKNOWN:CUSTOMER_RESPONSE", "UNKNOWN:PERMANENT_LOSS"], "evidence_budget_id": decision["evidence_budget"]["evidence_budget_id"], "source_packet_refs": [source_ref], "research_cost_hours": 0},
        "frozen_at": frozen_at, "object_class": "DECISION_UTILITY_PAIRING",
        "claim_class": "SAME_CONTRACT_METHOD_ABLATION",
        "allowed_outputs": ["DECISION_UTILITY_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }
    package = {
        "schema_version": PREOUTCOME_SCHEMA_VERSION, "package_id": package_id,
        "selection": selection,
        "source_learning_ref": {"completion_id": source_learning_completion["completion_id"], "artifact": "36_round5_real_feedback_completion_receipt.json", "company_id": source_learning_completion["company_id"], "cutoff_at": source_learning_completion["cutoff_at"], "accepted_feedback_scope": source_learning_completion["accepted_feedback_scope"]},
        "source_packet_receipt": source_receipt, "decision_contract": decision,
        "shared_cutoff_facts": facts, "baseline_view": baseline_view,
        "enhanced_view": enhanced_view, "decision_utility_pairing": pairing,
        "outcome_measurement_contract": measurement,
        "strongest_rival": "The 15-company support agreement may remain fee-based service provision while industry demand, price, issuer digital sales, cost measures and unrelated assets explain later issuer results.",
        "contamination_boundary": {"historical_replay_status": "MODEL_MEMORY_MITIGATED", "repository_contains_later_summary": True, "score_authority": "NONE", "allowed_use": "DEVELOPMENT_TRANSFER_UTILITY_ONLY"},
        "freeze_state": "PRE_OUTCOME_FROZEN", "frozen_at": frozen_at,
        "roles": roles, "rights": RIGHTS, "allowed_outputs": PREOUTCOME_OUTPUTS,
    }
    validation = validate_preoutcome_package(
        package, block=block, roster_freeze=roster_freeze,
        prior_receipts=prior_receipts, source_learning_completion=source_learning_completion,
    )
    if not validation["valid"]:
        raise ValueError("round6 package invalid: " + "; ".join(validation["findings"]))
    return package


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_real_preoutcome_artifacts(block_dir: Path, *, frozen_at: str) -> dict[str, Any]:
    """Build the three committed pre-outcome artifacts from the frozen block."""
    def load(name: str) -> dict[str, Any]:
        return json.loads((block_dir / name).read_text(encoding="utf-8"))

    receipts = [load(name) for name in ROUND6_PRIOR_RECEIPT_FILES]
    source_completion = load("36_round5_real_feedback_completion_receipt.json")
    package = build_real_preoutcome_package(
        block=load("04_industry_learning_block.json"),
        roster_freeze=load("04_pre_outcome_roster_freeze.json"),
        prior_receipts=receipts,
        source_learning_completion=source_completion,
        frozen_at=frozen_at,
    )
    selection_artifact = {
        "schema_version": "enterprise-judgment-round6-transfer-selection.v1",
        "selection_id": "R6SEL:CN:CEMENT:600801:20160427:V1",
        "selection": deepcopy(package["selection"]),
        "source_learning_ref": deepcopy(package["source_learning_ref"]),
        "selection_basis": (
            "Frozen roster order after removing already consumed transitions and the "
            "Round 5 source-learning company; no outcome or source convenience was used."
        ),
        "object_class": "ENTERPRISE_JUDGMENT_TRANSFER_SELECTION",
        "claim_class": "MECHANICAL_PRE_OUTCOME_SELECTION",
        "allowed_outputs": ["PAIRED_PREOUTCOME_RESEARCH", "RESEARCH_AGENDA"],
    }
    validation = validate_preoutcome_package(
        package,
        block=load("04_industry_learning_block.json"),
        roster_freeze=load("04_pre_outcome_roster_freeze.json"),
        prior_receipts=receipts,
        source_learning_completion=source_completion,
    )
    if not validation["valid"]:
        raise ValueError("round6 preoutcome validation failed: " + "; ".join(validation["findings"]))
    contract = package["decision_contract"]
    validation_receipt = {
        "schema_version": "enterprise-judgment-round6-preoutcome-validation-receipt.v1",
        "receipt_id": "R6POVR:CN:CEMENT:600801:20160427:V1",
        "selection_ref": selection_artifact["selection_id"],
        "package_ref": package["package_id"],
        "validated_at": frozen_at,
        "validation_status": "PRE_OUTCOME_VALID",
        "mechanical_selection_confirmed": True,
        "same_evidence_budget_confirmed": True,
        "evidence_budget_id": contract["evidence_budget"]["evidence_budget_id"],
        "baseline_method_id": package["baseline_view"]["method_id"],
        "enhanced_method_id": package["enhanced_view"]["method_id"],
        "outcome_source_access_state": package["outcome_measurement_contract"]["source_access"]["access_state"],
        "outcome_content_read": False,
        "rights": deepcopy(RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_PREOUTCOME_VALIDATION_RECEIPT",
        "claim_class": "PAIRED_PREOUTCOME_FREEZE_CONFIRMATION",
        "allowed_outputs": ["PREOUTCOME_FREEZE_CONFIRMATION", "OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
    }
    return {
        "37_round6_transfer_utility_selection.json": selection_artifact,
        "38_round6_paired_preoutcome_package.json": package,
        "39_round6_preoutcome_validation_receipt.json": validation_receipt,
    }


def build_real_outcome_authorization(package: dict[str, Any]) -> dict[str, Any]:
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


def build_real_source_inventory(
    package: dict[str, Any], *, local_pdf_path: Path, registered_at: str,
) -> dict[str, Any]:
    contract = package["outcome_measurement_contract"]
    source = contract["source_access"]
    authorization = build_real_outcome_authorization(package)
    return {
        "schema_version": measurement_acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "OMINV:CN600801:FY2016:R6:V1",
        "measurement_contract_ref": authorization["measurement_contract_ref"],
        "custodian_id": authorization["custodian_id"],
        "registered_at": registered_at,
        "documents": [{
            "source_id": source["source_id"],
            "source_url": source["official_url"],
            "local_pdf_path": str(local_pdf_path),
            "issuer_id": source["issuer_id"],
            "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:600801",
            "report_period_end": source["report_period_end"],
            "official_source_type": source["source_type"],
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": (
                "FY2016 consolidated statements include the issuer and existing subsidiaries. "
                "The contracted Lafarge acquisition had not closed by year-end and was expected "
                "to enter the consolidated perimeter in 2017."
            ),
            "availability_precision": source["availability_precision"],
            "source_available_at": source["source_available_at"],
            "source_available_date": source["source_available_date"],
        }],
        "object_class": measurement_acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": measurement_acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["ENTERPRISE_OUTCOME_ACQUISITION_ONLY"],
    }


def _field_source(
    package: dict[str, Any], cell: dict[str, Any], raw: dict[str, Any],
    *, pdf_page: int, table_or_note: str, line_item: str, period_column: str,
) -> dict[str, Any]:
    source = package["outcome_measurement_contract"]["source_access"]
    frozen_locator = raw["locator"]
    return {
        "source_id": source["source_id"],
        "source_url": source["official_url"],
        "report_period_end": source["report_period_end"],
        "official_source_type": source["source_type"],
        "issuer_id": source["issuer_id"],
        "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
        "availability_precision": source["availability_precision"],
        "source_available_at": source["source_available_at"],
        "source_available_date": source["source_available_date"],
        "pdf_page": pdf_page,
        "field_ref": f"PDF p.{pdf_page}",
        "field_identity": raw["field_id"],
        "measurement_clock": deepcopy(raw["measurement_clock"]),
        "unit": raw["unit"],
        "table_or_note": frozen_locator["table_or_note"],
        "line_item": frozen_locator["line_item"],
        "period_column": frozen_locator["period_column"],
        "custodian_locator": {
            "table_or_note": table_or_note,
            "line_item": line_item,
            "period_column": period_column,
        },
    }


def build_real_custodian_field_records(package: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the page-located FY2016 records in frozen cell/raw-field order."""
    contract = package["outcome_measurement_contract"]
    observed: dict[str, tuple[Any, int, str, str, str]] = {
        "FIELD:600801:FY2016:ACTION_PROGRESS_EVENT": (
            True, 9, "Management discussion - operating development",
            "Shareholder approval completed for acquisition covering 15 cement factories",
            "FY2016 event window",
        ),
        "FIELD:600801:FY2016:DECISION_CONTROL_EVENT": (
            False, 134, "Note 11 - other related parties",
            "Supported Lafarge entities remained controlled by LafargeHolcim Ltd.",
            "As of 2016-12-31",
        ),
        "FIELD:600801:FY2016:CONSOLIDATION_SCOPE_EVENT": (
            False, 16, "Management discussion - acquisition integration risk",
            "The acquired factories were expected to enter issuer consolidation in 2017",
            "FY2016 year-end status",
        ),
        "FIELD:600801:FY2016:CEMENT_CLINKER_SALES_VOLUME": (
            52_700_000, 9, "Management discussion - principal operating results",
            "Combined cement and clinker sales volume of 52.70 million tonnes",
            "FY2016",
        ),
        "FIELD:600801:FY2016:CEMENT_GROSS_MARGIN": (
            0.2578, 10, "Principal business by industry",
            "Cement gross-margin ratio of 25.78%",
            "FY2016",
        ),
        "FIELD:600801:FY2015:OPERATING_CASH": (
            2_753_246_189, 51, "Consolidated cash-flow statement",
            "Net cash flows from operating activities",
            "Prior-period amount (FY2015)",
        ),
        "FIELD:600801:FY2016:OPERATING_CASH": (
            3_096_150_887, 51, "Consolidated cash-flow statement",
            "Net cash flows from operating activities",
            "Current-period amount (FY2016)",
        ),
        "FIELD:600801:FY2015:CASH_CAPEX": (
            1_591_631_924, 52, "Consolidated cash-flow statement",
            "Cash paid to acquire and construct fixed assets, intangible assets and other long-term assets",
            "Prior-period amount (FY2015)",
        ),
        "FIELD:600801:FY2016:CASH_CAPEX": (
            1_212_058_252, 52, "Consolidated cash-flow statement",
            "Cash paid to acquire and construct fixed assets, intangible assets and other long-term assets",
            "Current-period amount (FY2016)",
        ),
        "FIELD:600801:FY2015:SHORT_TERM_BORROWINGS": (
            1_162_000_000, 47, "Consolidated balance sheet",
            "Short-term borrowings",
            "Opening balance (2015-12-31)",
        ),
        "FIELD:600801:FY2016:SHORT_TERM_BORROWINGS": (
            904_000_000, 47, "Consolidated balance sheet",
            "Short-term borrowings",
            "Closing balance (2016-12-31)",
        ),
    }
    unknown: dict[str, tuple[str, int, str, str, str]] = {
        "FIELD:600801:FY2016:ISSUER_PRODUCT_PARTICIPATION_EVENT": (
            "The report discloses fee-based entrusted-management services but does not uniquely state issuer-product production or sales inside the supported-company scope.",
            135, "Note 11 - related-party transactions", "Entrusted-management service revenue", "FY2016",
        ),
        "FIELD:600801:FY2016:CUSTOMER_RESPONSE_EVENT": (
            "Issuer-wide projects and digital-channel activity are disclosed, but no customer response is tied to the supported-company scope.",
            9, "Management discussion - value marketing", "Issuer-wide customer and digital-channel activity", "FY2016",
        ),
        "FIELD:600801:FY2015:CEMENT_CLINKER_SALES_VOLUME": (
            "The report gives the FY2016 combined absolute volume and growth rate, but no directly disclosed FY2015 combined absolute value; it was not reverse-engineered.",
            9, "Management discussion - principal operating results", "Combined cement and clinker volume", "FY2015 comparative not directly disclosed",
        ),
        "FIELD:600801:FY2015:CEMENT_GROSS_MARGIN": (
            "The report gives FY2016 cement margin and its percentage-point change, but no directly disclosed FY2015 gross-margin ratio; it was not reverse-engineered.",
            10, "Principal business by industry", "Cement gross-margin ratio", "FY2015 comparative not directly disclosed",
        ),
        "FIELD:600801:FY2016:DIRECT_LOSS_EVENT_EVENT": (
            "The report does not uniquely disclose an issuer-level irreversible capital loss, default, covenant breach or going-concern event within the contracted event window.",
            21, "Material matters and integrity status", "No material overdue debt non-payment disclosed", "FY2016 event window",
        ),
    }
    records: list[dict[str, Any]] = []
    for cell in contract["atomic_cells"]:
        for raw in cell["raw_input_fields"]:
            base = {
                "cell_id": cell["cell_id"],
                "field_id": raw["field_id"],
                "measurement_clock": deepcopy(raw["measurement_clock"]),
                "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
                "unit": raw["unit"],
            }
            if raw["field_id"] in observed:
                value, page, table, line, period = observed[raw["field_id"]]
                records.append({
                    **base,
                    "status": "OBSERVED",
                    "raw_value": value,
                    "source": _field_source(
                        package, cell, raw, pdf_page=page,
                        table_or_note=table, line_item=line, period_column=period,
                    ),
                })
            else:
                reason, page, table, line, period = unknown[raw["field_id"]]
                source = package["outcome_measurement_contract"]["source_access"]
                records.append({
                    **base,
                    "status": "UNKNOWN",
                    "reason": reason,
                    "sources_considered": [{
                        "source_id": source["source_id"],
                        "source_url": source["official_url"],
                        "report_period_end": source["report_period_end"],
                        "official_source_type": source["source_type"],
                        "issuer_id": source["issuer_id"],
                        "source_available_date": source["source_available_date"],
                        "pdf_page": page,
                        "field_ref": f"PDF p.{page}",
                        "custodian_locator": {
                            "table_or_note": table,
                            "line_item": line,
                            "period_column": period,
                        },
                    }],
                })
    return records


def build_real_utility_review(
    package: dict[str, Any], settlement: dict[str, Any], *, reviewed_at: str,
) -> dict[str, Any]:
    reviewer_id = "ROLE:CEMENT:ROUND6:INDEPENDENT_UTILITY_REVIEWER"
    evaluation = {
        "schema_version": decision_utility.LEGACY_EVALUATION_SCHEMA_VERSION,
        "evaluation_id": "DUEVAL:CN600801:20160427:R6:V1",
        "pairing_id": package["decision_utility_pairing"]["pairing_id"],
        "evaluated_at": reviewed_at,
        "reviewer_id": reviewer_id,
        "outcome_settlement_ref": settlement["settlement_id"],
        "dimension_findings": [
            {
                "dimension_id": "PERMANENT_LOSS_GUARDRAIL",
                "baseline_assessment": "UNKNOWN",
                "enhanced_assessment": "UNKNOWN",
                "rationale": "One annual report and an UNKNOWN direct-loss event cannot establish permanent-loss absence or presence.",
            },
            {
                "dimension_id": "OWNER_CASH_ACCESS",
                "baseline_assessment": "NOT_DIAGNOSTIC",
                "enhanced_assessment": "NOT_DIAGNOSTIC",
                "rationale": "Higher operating cash and lower cash capex do not establish owner-cash accessibility or acquisition economics.",
            },
            {
                "dimension_id": "KEY_UNKNOWN_DISCOVERY",
                "baseline_assessment": "UNKNOWN",
                "enhanced_assessment": "MATERIAL_IMPROVEMENT",
                "rationale": "The enhanced view separates formal approval from issuer control, product participation, consolidation and customer response; FY2016 directly resolves control and consolidation as absent while preserving the other two unknowns.",
            },
            {
                "dimension_id": "RESEARCH_COST",
                "baseline_assessment": "NO_DIFFERENCE",
                "enhanced_assessment": "NO_DIFFERENCE",
                "rationale": "Both views used the same cutoff packet and the same outcome source; the improvement came from question structure, not additional evidence.",
            },
        ],
        "holdout": {
            "training_company_ids": ["CN:600802"],
            "holdout_company_ids": ["CN:600801"],
            "training_cutoff_through": "2015-04-15T00:00:00+08:00",
            "holdout_cutoff_from": "2016-04-27T00:00:00+08:00",
        },
        "object_class": "DECISION_UTILITY_EVALUATION",
        "claim_class": "MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": decision_utility.ALLOWED_OUTPUTS,
    }
    review = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_id": "R6REVIEW:CN600801:20160427:FY2016:V1",
        "package_ref": package["package_id"],
        "utility_evaluation": evaluation,
        "settlement_ref": settlement["settlement_id"],
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "paired_claim_findings": [
            {
                "dimension": "formal_progress_versus_control_and_consolidation",
                "baseline_assessment": "The broad baseline correctly records acquisition approval as progress but does not resolve what became issuer-controlled operating capacity.",
                "enhanced_assessment": "Approval was observed, while supported entities remained LafargeHolcim-controlled and the acquired factories were not yet consolidated at FY2016 year-end.",
                "economic_effect": "An investor must not add the factories' capacity, earnings or integration success to the FY2016 issuer merely because approval and support services existed.",
                "supporting_cell_ids": [
                    "CELL:600801:20160427:ACTION_PROGRESS",
                    "CELL:600801:20160427:DECISION_CONTROL",
                    "CELL:600801:20160427:CONSOLIDATION_SCOPE",
                ],
                "prohibited_inference": "This does not prove that the acquisition later failed or succeeded.",
            },
            {
                "dimension": "issuer_operating_state_versus_action_effect",
                "baseline_assessment": "Issuer operating cash improved while cash capex and short-term borrowings declined.",
                "enhanced_assessment": "The same directions are retained as issuer state and are not attributed to a transaction that had not closed.",
                "economic_effect": "The balance-sheet and cash direction improved near-term resilience but provides no acquisition-effect or management-quality label.",
                "supporting_cell_ids": [
                    "CELL:600801:20160427:OPERATING_CASH",
                    "CELL:600801:20160427:CASH_CAPEX",
                    "CELL:600801:20160427:SHORT_TERM_BORROWINGS",
                ],
                "prohibited_inference": "Operating cash is not owner cash, and correlation is not transaction causality.",
            },
            {
                "dimension": "product_and_customer_realization",
                "baseline_assessment": "Aggregate progress and issuer volume do not identify whose products or customers produced the observed state.",
                "enhanced_assessment": "Issuer-product participation and transaction-specific customer response remain UNKNOWN; unsupported reverse-engineering also leaves volume and margin direction locally UNKNOWN.",
                "economic_effect": "The method exposes the evidence needed before crediting commercial realization instead of filling the gap with company-wide growth.",
                "supporting_cell_ids": [
                    "CELL:600801:20160427:ISSUER_PRODUCT_PARTICIPATION",
                    "CELL:600801:20160427:CUSTOMER_RESPONSE",
                    "CELL:600801:20160427:CEMENT_CLINKER_SALES_VOLUME",
                    "CELL:600801:20160427:CEMENT_GROSS_MARGIN",
                ],
                "prohibited_inference": "UNKNOWN is not evidence of no product participation or no customer response.",
            },
        ],
        "overall_verdict": "ENHANCED_IMPROVED_KEY_UNKNOWN",
        "investor_effect": (
            "The enhanced method materially improves the enterprise boundary: FY2016 contains "
            "formal acquisition progress and fee-based support, but not issuer control or "
            "consolidation. It prevents premature attribution of capacity, cash improvement or "
            "integration quality while identifying the next evidence required."
        ),
        "unknowns_preserved": [
            "Issuer-product participation inside the supported-company scope",
            "Customer response attributable to that scope",
            "Comparable combined FY2015 volume and cement-margin raw values",
            "Permanent-loss outcome and owner-cash accessibility",
            "Post-closing integration effectiveness and management quality",
        ],
        "limitations": [
            "Repository history contains later summaries, so this is MODEL_MEMORY_MITIGATED development utility and has no holdout score authority.",
            "One company and one outcome period cannot validate method transfer.",
            "The annual report does not establish causal effects of the support or acquisition actions.",
        ],
        "rights": deepcopy(RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_TRANSFER_UTILITY_REVIEW",
        "claim_class": "PAIRED_MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": REVIEW_OUTPUTS,
    }
    validation = validate_utility_review(review, package=package, settlement=settlement)
    if not validation["valid"]:
        raise ValueError("round6 utility review invalid: " + "; ".join(validation["findings"]))
    return review


def build_real_completion_receipt(
    package: dict[str, Any], settlement: dict[str, Any], review: dict[str, Any],
) -> dict[str, Any]:
    receipt = {
        "schema_version": COMPLETION_SCHEMA_VERSION,
        "completion_id": "R6COMP:CN:CEMENT:600801:20160427:FY2016:V1",
        "package_ref": package["package_id"],
        "settlement_ref": settlement["settlement_id"],
        "review_ref": review["review_id"],
        "company_id": package["selection"]["company_id"],
        "cutoff_at": package["selection"]["cutoff_at"],
        "status": "ROUND6_REAL_TRANSFER_UTILITY_COMPLETED",
        "investor_summary": (
            "华新在 2016 年推进了拉法基资产收购审批并提供运营支持服务，但相关资产年末仍未交割、未由华新控制、未进入华新合并报表。同期华新经营现金流改善、现金资本开支和短期借款下降，只能说明华新自身状态改善，不能证明并购效果或管理层整体质量。"
        ),
        "proved": [
            "同一 FY2015 证据下，拆分控制、产品参与、并表和客户响应能够提出比总括行动进展更有投资价值的问题。",
            "FY2016 已观察到正式收购推进，但华新控制和合并范围仍未形成。",
            "经营现金流上升、现金资本开支下降、短期借款下降可独立结算，且未被错误归因于并购。",
        ],
        "not_proved": [
            "并购最终成功、协同实现或管理层执行能力优秀。",
            "支持范围内的华新产品参与、客户响应、owner cash 或永久损失结论。",
            "方法已经通过真实盲法 holdout、跨公司迁移验证或可进入 CJO、估值和报告。",
        ],
        "next_research_action": [
            "在下一 cutoff 核对实际交割日期、六个法律实体与十五家工厂的范围桥以及首次并表口径。",
            "分别寻找被并购范围的华新产品、客户、单位经济和现金证据，不用华新整体指标代替。",
            "在没有历史摘要污染的新公司和 cutoff 上重复同证据预算配对，建立真正的迁移验证。",
        ],
        "rights": deepcopy(RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_ROUND6_COMPLETION_RECEIPT",
        "claim_class": "REAL_CROSS_COMPANY_PAIRED_UTILITY_COMPLETION",
        "allowed_outputs": COMPLETION_OUTPUTS,
    }
    validation = validate_completion_receipt(
        receipt, package=package, settlement=settlement, review=review,
    )
    if not validation["valid"]:
        raise ValueError("round6 completion receipt invalid: " + "; ".join(validation["findings"]))
    return receipt


def build_real_postoutcome_artifacts(
    block_dir: Path, *, local_pdf_path: Path, registry_db: Path,
    observed_at: str, settled_at: str, reviewed_at: str,
) -> dict[str, Any]:
    """Acquire and settle the frozen Round 6 contract after outcome access."""
    package = json.loads(
        (block_dir / "38_round6_paired_preoutcome_package.json").read_text(encoding="utf-8")
    )
    contract = package["outcome_measurement_contract"]
    authorization = build_real_outcome_authorization(package)
    inventory = build_real_source_inventory(
        package, local_pdf_path=local_pdf_path, registered_at=observed_at,
    )
    records = build_real_custodian_field_records(package)
    acquisition_result = measurement_acquisition.acquire_outcome_measurements(
        contract,
        inventory,
        field_records=records,
        outcome_access_authorization=authorization,
    )
    previous_registry = reconstruction.CANONICAL_REGISTRY_PATH
    reconstruction.CANONICAL_REGISTRY_PATH = registry_db
    try:
        enterprise_control.register_measurement_contract(
            contract, frozen_at=contract["contract_frozen_at"],
        )
        settlement = settlement_adapter.settle_enterprise_acquisition_result(
            measurement_contract=contract,
            outcome_access_authorization=authorization,
            acquisition_result=acquisition_result,
            observed_at=observed_at,
            settlement_id="R6SETTLE:CN600801:20160427:FY2016:V1",
            settled_at=settled_at,
        )
    finally:
        reconstruction.CANONICAL_REGISTRY_PATH = previous_registry
    settlement.pop("persisted", None)
    settlement.pop("idempotent", None)
    review = build_real_utility_review(package, settlement, reviewed_at=reviewed_at)
    completion = build_real_completion_receipt(package, settlement, review)
    return {
        "40_round6_outcome_access_authorization.json": authorization,
        "41_round6_custodian_field_records.json": records,
        "42_round6_canonical_field_settlement.json": settlement,
        "43_round6_independent_paired_utility_review.json": review,
        "44_round6_completion_receipt.json": completion,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Round 6 transfer-utility artifacts.")
    parser.add_argument("--mode", choices=["preoutcome", "postoutcome"], default="preoutcome")
    parser.add_argument("--block-dir", required=True, type=Path)
    parser.add_argument("--frozen-at")
    parser.add_argument("--outcome-pdf", type=Path)
    parser.add_argument("--registry-db", type=Path)
    parser.add_argument("--observed-at")
    parser.add_argument("--settled-at")
    parser.add_argument("--reviewed-at")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.mode == "preoutcome":
        if not args.frozen_at:
            parser.error("--frozen-at is required in preoutcome mode")
        artifacts = build_real_preoutcome_artifacts(args.block_dir, frozen_at=args.frozen_at)
    else:
        missing = [
            name for name, value in (
                ("--outcome-pdf", args.outcome_pdf),
                ("--registry-db", args.registry_db),
                ("--observed-at", args.observed_at),
                ("--settled-at", args.settled_at),
                ("--reviewed-at", args.reviewed_at),
            )
            if value is None
        ]
        if missing:
            parser.error("postoutcome mode requires " + ", ".join(missing))
        artifacts = build_real_postoutcome_artifacts(
            args.block_dir,
            local_pdf_path=args.outcome_pdf,
            registry_db=args.registry_db,
            observed_at=args.observed_at,
            settled_at=args.settled_at,
            reviewed_at=args.reviewed_at,
        )
    if not args.check_only:
        output_dir = args.output_dir or args.block_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, artifact in artifacts.items():
            write_json(output_dir / name, artifact)
    print(json.dumps({"valid": True, "artifacts": sorted(artifacts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
