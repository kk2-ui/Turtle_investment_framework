#!/usr/bin/env python3
"""Appliance-specific projection onto the V2 E0-E3 training architecture.

This module is deliberately a thin read model.  It composes the existing
appliance Industry Learning Block, its J2 reconstruction, and the reviewed
Supor R11 pre-outcome episode.  It does not create another source store,
outcome controller, Comparative validator, or settlement engine.

The four stages are progressive evidence ceilings:

* E0 -- industry/company context;
* E1 -- company operating-system reconstruction;
* E2 -- one bounded, falsifiable mechanism probe;
* E3 -- a strict comparative lab, which remains unadmitted until its own
  product-boundary estimand, panel and independent outcome contract exist.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SCHEMA_VERSION = "enterprise-judgment-appliance-four-stage.v1"
E2_RESOLUTION_SCHEMA_VERSION = "enterprise-judgment-appliance-e2-resolution-contract.v1"
PLAN_ID = "APPLIANCE:FOUR-STAGE:20170430-20180930:V1"
BLOCK_ID = "ILB:CN:APPLIANCE:NATIONAL:V1"
SUPOR_EPISODE_ID = "APPLIANCE-R11:CN002032:20180930:V1"
SUPOR_REVIEW_ID = "APPLIANCE-R11:CN002032:20180930:INDEPENDENT-PREOUTCOME-REVIEW:V1"
STAGE_ORDER = ["E0_CONTEXT", "E1_RECONSTRUCTION", "E2_MECHANISM_PROBE", "E3_COMPARATIVE_LAB"]
RIGHTS = {
    "method_transfer": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "buy_band": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}

E2_FIELD_ROLES = {
    "MHE:CONTRACT:APPLIANCE-R11:CN002032:FY2018:ISSUER_REVENUE:V1": "ISSUER_SCALE_CONTEXT",
    "MHE:CONTRACT:APPLIANCE-R11:CN002032:FY2018:ELECTRIC_POT_REVENUE:V1": "PRODUCT_BOUNDARY_DISCRIMINATOR",
    "MHE:CONTRACT:APPLIANCE-R11:CN002032:FY2018:ISSUER_OCF:V1": "ISSUER_CASH_BOUNDARY",
}

_ROOT_KEYS = {
    "schema_version", "plan_id", "industry_block_ref", "cutoffs", "risk_set",
    "stages", "next_atomic_action", "object_class", "claim_class",
    "allowed_outputs", "rights",
}
_FORBIDDEN_KEYS = {
    "price", "return", "valuation", "buy_band", "investment_action",
    "outcome_value", "settlement_value", "method_transfer_authorization",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _walk_forbidden(value: Any, path: str = "root") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child = f"{path}.{key}"
            explicit_denial = path.endswith(".rights") and nested == "NOT_AUTHORIZED"
            if str(key).casefold() in _FORBIDDEN_KEYS and not explicit_denial:
                findings.append(child + "_forbidden")
            findings.extend(_walk_forbidden(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_walk_forbidden(nested, f"{path}[{index}]")
            )
    return findings


def build_four_stage_plan(
    source_register: Any,
    j234_read_model: Any,
    supor_episode: Any,
    supor_review: Any,
) -> dict[str, Any]:
    """Build the canonical result-unseen E0-E3 appliance projection."""
    register = _mapping(source_register)
    j234 = _mapping(j234_read_model)
    episode = _mapping(supor_episode)
    review = _mapping(supor_review)

    if register.get("block_id") != BLOCK_ID or j234.get("block_id") != BLOCK_ID:
        raise ValueError("appliance_industry_block_identity_mismatch")
    if episode.get("episode_id") != SUPOR_EPISODE_ID:
        raise ValueError("supor_episode_identity_mismatch")
    if review.get("review_id") != SUPOR_REVIEW_ID or review.get("review_status") != "PASS":
        raise ValueError("supor_independent_preoutcome_review_required")
    if review.get("episode_ref") != SUPOR_EPISODE_ID or review.get("outcome_content_read") is not False:
        raise ValueError("supor_review_must_bind_result_unseen_episode")

    cutoffs = [row["cutoff_at"] for row in _items(register.get("cutoffs"))]
    universe = _items(j234.get("industry_universe"))
    existing_companies = sorted({row.get("company_id") for row in universe if _text(row.get("company_id"))})
    risk_set = [
        {
            "company_id": company_id,
            "context_source": "CN_APPLIANCE_INDUSTRY_J234_V1",
            "role": "E0_E1_EXISTING_RISK_SET",
        }
        for company_id in existing_companies
    ]
    risk_set.append({
        "company_id": "CN:002032",
        "context_source": SUPOR_EPISODE_ID,
        "role": "E0_C2_EXTENSION_AND_E1_DEEP_RECONSTRUCTION",
    })

    contracts = [
        chain["measurement_contract"]["measurement_contract_id"]
        for chain in _items(episode.get("minimal_field_chains"))
    ]
    stages = [
        {
            "stage": "E0_CONTEXT",
            "status": "FROZEN",
            "question": "What national appliance arenas, company systems and cutoff-visible boundaries exist?",
            "inputs": [
                "CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json",
                "CN_APPLIANCE_INDUSTRY_J234_V1.json",
                SUPOR_EPISODE_ID,
            ],
            "evidence_ceiling": "CONTEXT_ONLY",
            "permitted_outputs": ["STATE_VIEW", "RESEARCH_AGENDA"],
            "prohibited_claim": "THE_RISK_SET_IS_A_CAUSAL_PEER_PANEL",
        },
        {
            "stage": "E1_RECONSTRUCTION",
            "status": "FROZEN",
            "question": "How do product, channel, operating, cash and capital boundaries differ across the six systems?",
            "inputs": [episode_id for episode_id in [
                row.get("episode_id") for row in _items(j234.get("episodes"))
            ] if _text(episode_id)] + [SUPOR_EPISODE_ID],
            "evidence_ceiling": "RECONSTRUCTION_ONLY",
            "permitted_outputs": ["STATE_VIEW", "DECISION_VIEW", "RESEARCH_AGENDA"],
            "local_unknown_policy": "UNKNOWN_BLOCKS_ONLY_DEPENDENT_CLAIMS",
            "prohibited_claim": "ISSUER_GROWTH_OR_CASH_PROVES_PRODUCT_QUALITY",
        },
        {
            "stage": "E2_MECHANISM_PROBE",
            "status": "PREOUTCOME_FROZEN_AWAITING_INDEPENDENT_SETTLEMENT",
            "episode_ref": SUPOR_EPISODE_ID,
            "review_ref": SUPOR_REVIEW_ID,
            "question": "Do electric-pot product revenue, issuer revenue and issuer operating cash move in a pattern consistent with the prewritten product/channel mechanism?",
            "h_a": "Cutoff-visible product and channel execution is followed by product-boundary revenue growth without material issuer-cash deterioration.",
            "h_b": "Category demand, SEB order transfer, input costs or channel competition explain the movements without a company-specific action effect.",
            "measurement_contract_refs": contracts,
            "evidence_ceiling": "NARROW_ASSOCIATION_AND_BOUNDARY_PROBE",
            "permitted_outputs": ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
            "prohibited_claim": "THE_MANAGEMENT_ACTION_CAUSED_COMPANY_WIDE_IMPROVEMENT",
            "outcome_access": "CONTROLLER_AUTHORIZATION_REQUIRED",
        },
        {
            "stage": "E3_COMPARATIVE_LAB",
            "status": "NOT_ADMITTED_NOT_BLOCKING_E0_TO_E2",
            "question": "Against a pre-outcome product-boundary alternative, is the selected mechanism directionally stronger?",
            "missing_contracts": [
                "ONE_EXPLICIT_PRODUCT_BOUNDARY_ESTIMAND",
                "FROZEN_MECHANISM_COMPATIBLE_PANEL",
                "FAIR_BASELINE_AND_COMMON_SHOCK_BOUNDARY",
                "INDEPENDENT_COMPARATIVE_OUTCOME_CONTRACT",
            ],
            "evidence_ceiling": "NO_COMPARATIVE_AUTHORITY",
            "permitted_outputs": ["RESEARCH_AGENDA"],
            "prohibited_claim": "THE_SIX_COMPANIES_ARE_UNTREATED_CONTROLS_OR_A_RANKING_PANEL",
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": PLAN_ID,
        "industry_block_ref": BLOCK_ID,
        "cutoffs": cutoffs,
        "risk_set": risk_set,
        "stages": stages,
        "next_atomic_action": "SETTLE_E2_SUPOR_FIELDS_WITH_CONTRACT_ONLY_INDEPENDENT_CUSTODIAN",
        "object_class": "APPLIANCE_FOUR_STAGE_TRAINING_READ_MODEL",
        "claim_class": "RESULT_UNSEEN_PROGRESSIVE_EVIDENCE_CEILINGS",
        "allowed_outputs": ["STATE_VIEW", "DECISION_VIEW", "MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
        "rights": deepcopy(RIGHTS),
    }


def validate_four_stage_plan(
    plan: Any,
    *,
    source_register: Any,
    j234_read_model: Any,
    supor_episode: Any,
    supor_review: Any,
) -> dict[str, Any]:
    item = _mapping(plan)
    findings: list[str] = []
    if set(item) != _ROOT_KEYS:
        findings.append("four_stage_plan_shape_invalid")
    if item.get("schema_version") != SCHEMA_VERSION or item.get("plan_id") != PLAN_ID:
        findings.append("four_stage_plan_identity_invalid")
    try:
        canonical = build_four_stage_plan(
            source_register, j234_read_model, supor_episode, supor_review,
        )
    except ValueError as exc:
        findings.append(str(exc))
        canonical = None
    if canonical is not None and item != canonical:
        findings.append("four_stage_plan_must_equal_canonical_projection")
    stages = _items(item.get("stages"))
    if [stage.get("stage") for stage in stages if isinstance(stage, dict)] != STAGE_ORDER:
        findings.append("four_stage_order_invalid")
    if len(stages) == 4:
        e2, e3 = _mapping(stages[2]), _mapping(stages[3])
        if e2.get("status") != "PREOUTCOME_FROZEN_AWAITING_INDEPENDENT_SETTLEMENT":
            findings.append("e2_must_remain_result_unseen_before_custody")
        if e3.get("status") != "NOT_ADMITTED_NOT_BLOCKING_E0_TO_E2":
            findings.append("e3_cannot_be_admitted_without_comparative_contracts")
    risk_set = _items(item.get("risk_set"))
    if [row.get("company_id") for row in risk_set if isinstance(row, dict)] != [
        "CN:000333", "CN:000651", "CN:000921", "CN:600690", "CN:600839", "CN:002032",
    ]:
        findings.append("risk_set_must_preserve_existing_five_and_supor_extension")
    if item.get("rights") != RIGHTS:
        findings.append("downstream_rights_must_remain_closed")
    findings.extend(_walk_forbidden(item))
    return {
        "valid": not findings,
        "findings": findings,
        "four_stage_plan": deepcopy(item) if not findings else None,
    }


def compile_investor_stage_readout(plan: Any) -> dict[str, Any]:
    """Project only decision-useful stage status, never outcome or price data."""
    item = _mapping(plan)
    return {
        "plan_id": item.get("plan_id"),
        "stage_status": {
            stage.get("stage"): stage.get("status")
            for stage in _items(item.get("stages")) if isinstance(stage, dict)
        },
        "investor_learning": [
            "The national appliance universe contains different product and capital systems, not one homogeneous peer panel.",
            "Supor is reconstructed at both issuer and disclosed electric-pot boundaries before any result is opened.",
            "The pending E2 test can diagnose alignment or divergence across product growth, issuer growth and issuer cash, but cannot prove action causality.",
            "E3 remains closed until a product-specific estimand, panel, baseline and independent outcome contract exist.",
        ],
        "rights": deepcopy(RIGHTS),
    }


def build_e2_resolution_contract() -> dict[str, Any]:
    """Freeze field-local interpretation before receiving custody results."""
    return {
        "schema_version": E2_RESOLUTION_SCHEMA_VERSION,
        "resolution_contract_id": "APPLIANCE:E2:CN002032:20180930:RESOLUTION:V1",
        "episode_ref": SUPOR_EPISODE_ID,
        "field_roles": [
            {"measurement_contract_id": contract_id, "role": role}
            for contract_id, role in E2_FIELD_ROLES.items()
        ],
        "field_rules": {
            "MATCH": "SUPPORT_ONLY_THE_PREDECLARED_FIELD_EXPECTATION",
            "MISS": "WEAKEN_ONLY_THE_PREDECLARED_FIELD_EXPECTATION",
            "MEASUREMENT_MISMATCH": "FIELD_UNRESOLVED_NO_OPERATING_CONCLUSION",
            "UNKNOWN": "FIELD_UNRESOLVED_NO_OPERATING_CONCLUSION",
        },
        "combined_rules": [
            {
                "condition": "ALL_THREE_MATCH",
                "resolution": "PATTERN_CONSISTENT_WITH_H_A_NOT_CAUSAL",
            },
            {
                "condition": "PRODUCT_BOUNDARY_DISCRIMINATOR_MISS",
                "resolution": "PRODUCT_MECHANISM_EXPECTATION_WEAKENED",
            },
            {
                "condition": "ANY_FIELD_UNRESOLVED",
                "resolution": "PARTIAL_NOT_DIAGNOSTIC",
            },
            {
                "condition": "OTHER_SETTLED_PATTERN",
                "resolution": "MIXED_PATTERN_H_A_NOT_ESTABLISHED",
            },
        ],
        "evidence_ceiling": "NARROW_ASSOCIATION_AND_BOUNDARY_PROBE",
        "comparative_admission": "NOT_AUTHORIZED",
        "allowed_outputs": ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
        "rights": deepcopy(RIGHTS),
    }


def resolve_e2_terminal_statuses(statuses: Any) -> dict[str, Any]:
    """Apply the frozen field rules to value-free custody terminal statuses."""
    rows = _items(statuses)
    by_contract: dict[str, dict[str, Any]] = {}
    findings: list[str] = []
    allowed_terminal = {"MATCH", "MISS", "MEASUREMENT_MISMATCH", "UNKNOWN"}
    for index, raw in enumerate(rows):
        row = _mapping(raw)
        if set(row) != {"measurement_contract_id", "terminal_status"}:
            findings.append(f"statuses[{index}].shape_invalid")
            continue
        contract_id = row.get("measurement_contract_id")
        terminal = row.get("terminal_status")
        if contract_id not in E2_FIELD_ROLES:
            findings.append(f"statuses[{index}].contract_unknown")
        elif contract_id in by_contract:
            findings.append(f"statuses[{index}].contract_duplicate")
        elif terminal not in allowed_terminal:
            findings.append(f"statuses[{index}].terminal_status_invalid")
        else:
            by_contract[str(contract_id)] = row
    if set(by_contract) != set(E2_FIELD_ROLES):
        findings.append("statuses_must_cover_all_three_frozen_contracts")
    if findings:
        return {"valid": False, "findings": findings, "resolution": None}

    diagnostics = [
        {
            "measurement_contract_id": contract_id,
            "role": role,
            "terminal_status": by_contract[contract_id]["terminal_status"],
            "interpretation": {
                "MATCH": "FIELD_EXPECTATION_SUPPORTED_NOT_CAUSAL",
                "MISS": "FIELD_EXPECTATION_WEAKENED",
                "MEASUREMENT_MISMATCH": "FIELD_UNRESOLVED",
                "UNKNOWN": "FIELD_UNRESOLVED",
            }[by_contract[contract_id]["terminal_status"]],
        }
        for contract_id, role in E2_FIELD_ROLES.items()
    ]
    product_status = by_contract[
        "MHE:CONTRACT:APPLIANCE-R11:CN002032:FY2018:ELECTRIC_POT_REVENUE:V1"
    ]["terminal_status"]
    all_statuses = [row["terminal_status"] for row in by_contract.values()]
    if all(status == "MATCH" for status in all_statuses):
        combined = "PATTERN_CONSISTENT_WITH_H_A_NOT_CAUSAL"
    elif product_status == "MISS":
        combined = "PRODUCT_MECHANISM_EXPECTATION_WEAKENED"
    elif any(status in {"MEASUREMENT_MISMATCH", "UNKNOWN"} for status in all_statuses):
        combined = "PARTIAL_NOT_DIAGNOSTIC"
    else:
        combined = "MIXED_PATTERN_H_A_NOT_ESTABLISHED"
    return {
        "valid": True,
        "findings": [],
        "resolution": {
            "episode_ref": SUPOR_EPISODE_ID,
            "field_diagnostics": diagnostics,
            "combined_resolution": combined,
            "evidence_ceiling": "NARROW_ASSOCIATION_AND_BOUNDARY_PROBE",
            "e3_comparative_status": "NOT_ADMITTED",
            "allowed_outputs": ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
            "rights": deepcopy(RIGHTS),
        },
    }
