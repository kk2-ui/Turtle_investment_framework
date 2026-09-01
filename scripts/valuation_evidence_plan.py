#!/usr/bin/env python3
"""Compile route-bound valuation evidence work without inventing inputs.

The plan is a deterministic projection of the selected valuation route, one
active versioned valuation-archetype card, and the current fact-observation
registry.  It carries reusable acquisition guidance and local conclusion
boundaries.  It never copies observation values, supplies valuation
parameters, or promotes an acquisition attempt into eligible evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_documents import _atomic_write_json
    from scripts.valuation_archetypes import resolve_valuation_archetype
    from scripts.valuation_routing import load_registry, validate_valuation_route
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from evidence_documents import _atomic_write_json
    from valuation_archetypes import resolve_valuation_archetype
    from valuation_routing import load_registry, validate_valuation_route


PLAN_SCHEMA_VERSION = "valuation-evidence-plan.v1"
ATTEMPT_SCHEMA_VERSION = "valuation-evidence-attempt-receipts.v1"
PLAN_FILENAME = "valuation_evidence_plan.json"
ATTEMPT_FILENAME = "valuation_evidence_attempt_receipts.json"

EVIDENCE_STATES = {"AVAILABLE", "MISSING", "INELIGIBLE"}
ATTEMPT_OUTCOMES = {
    "EVIDENCE_FOUND",
    "PUBLIC_INFO_UNAVAILABLE",
    "INELIGIBLE_ONLY",
}
ATTEMPT_REQUIRED_FIELDS = [
    "receipt_id",
    "component_type",
    "evidence_role",
    "attempted_official_sources",
    "attempted_modules",
    "query_hints_used",
    "outcome",
    "evidence_ids",
    "completed_at",
]
PROHIBITED_VALUE_TEXT_RE = re.compile(
    r"(?:RMB|CNY|HKD|USD|人民币|港元|美元)\s*[\d,.]+"
    r"|\d+(?:\.\d+)?\s*(?:%|x|倍|million|billion|mn|bn|百万元|千万元|万元|亿元)",
    re.IGNORECASE,
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _attempt_receipt_index(
    payload: dict[str, Any], *, report_id: str, route_id: str, card_id: str,
    allowed_role_pairs: set[tuple[str, str]], observation_ids: set[str],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    """Validate the optional search receipt seam without granting evidence."""
    if not payload:
        return {}, []
    findings: list[str] = []
    if payload.get("schema_version") != ATTEMPT_SCHEMA_VERSION:
        findings.append("attempt_receipts:schema_version_invalid")
    if payload.get("report_id") != report_id:
        findings.append("attempt_receipts:report_id_mismatch")
    if payload.get("route_id") != route_id:
        findings.append("attempt_receipts:route_id_mismatch")
    if payload.get("card_id") != card_id:
        findings.append("attempt_receipts:card_id_mismatch")
    receipts = payload.get("receipts")
    if not isinstance(receipts, list):
        findings.append("attempt_receipts:not_array")
        receipts = []
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    allowed_fields = set(ATTEMPT_REQUIRED_FIELDS)
    for index, raw_receipt in enumerate(receipts):
        prefix = f"attempt_receipts[{index}]"
        receipt = _mapping(raw_receipt)
        if set(receipt) != allowed_fields:
            findings.append(prefix + ":fields_invalid")
            continue
        component_type = str(receipt.get("component_type") or "")
        evidence_role = str(receipt.get("evidence_role") or "")
        key = (component_type, evidence_role)
        if not component_type or not evidence_role:
            findings.append(prefix + ":role_identity_missing")
        elif key not in allowed_role_pairs:
            findings.append(prefix + ":role_identity_not_in_card")
        elif key in indexed:
            findings.append(prefix + ":duplicate_role_receipt")
        if not str(receipt.get("receipt_id") or "").startswith("VEA:"):
            findings.append(prefix + ":receipt_id_invalid")
        if receipt.get("outcome") not in ATTEMPT_OUTCOMES:
            findings.append(prefix + ":outcome_invalid")
        for field in (
            "attempted_official_sources",
            "attempted_modules",
            "query_hints_used",
        ):
            texts = _text_list(receipt.get(field))
            if not texts:
                findings.append(prefix + ":" + field + "_missing")
            elif any(PROHIBITED_VALUE_TEXT_RE.search(text) for text in texts):
                findings.append(prefix + ":" + field + "_contains_value_or_parameter")
        evidence_ids = receipt.get("evidence_ids")
        if not isinstance(evidence_ids, list) or any(
            not isinstance(item, str) or not item.strip() for item in evidence_ids
        ):
            findings.append(prefix + ":evidence_ids_invalid")
        else:
            outcome = receipt.get("outcome")
            if outcome in {"EVIDENCE_FOUND", "INELIGIBLE_ONLY"} and not evidence_ids:
                findings.append(prefix + ":evidence_ids_required_for_outcome")
            if any(str(item) not in observation_ids for item in evidence_ids):
                findings.append(prefix + ":evidence_id_not_in_current_registry")
        if not str(receipt.get("completed_at") or "").strip():
            findings.append(prefix + ":completed_at_missing")
        if not any(item.startswith(prefix + ":") for item in findings):
            indexed[key] = deepcopy(receipt)
    if findings:
        return {}, list(dict.fromkeys(findings))
    return indexed, []


def _role_evidence(
    observations: list[dict[str, Any]], role: str
) -> tuple[str, list[str], list[str]]:
    eligible: list[str] = []
    ineligible: list[str] = []
    for observation in observations:
        declared_roles = {
            str(item) for item in observation.get("valuation_evidence_roles") or []
        }
        if role not in declared_roles:
            continue
        observation_id = str(observation.get("observation_id") or "").strip()
        if not observation_id:
            continue
        if observation.get("status") == "VERIFIED":
            eligible.append(observation_id)
        else:
            ineligible.append(observation_id)
    eligible = sorted(set(eligible))
    ineligible = sorted(set(ineligible))
    state = "AVAILABLE" if eligible else "INELIGIBLE" if ineligible else "MISSING"
    return state, eligible, ineligible


def _attempt_projection(
    *,
    component_type: str,
    role: str,
    evidence_state: str,
    receipt: dict[str, Any] | None,
    receipts_valid: bool,
) -> dict[str, Any]:
    if evidence_state == "AVAILABLE":
        state = "NOT_REQUIRED"
    elif receipt:
        state = "RECORDED"
    elif receipts_valid:
        state = "NOT_RECORDED"
    else:
        state = "RECEIPT_REGISTRY_INVALID"
    return {
        "state": state,
        "write_target": ATTEMPT_FILENAME,
        "role_identity": {
            "component_type": component_type,
            "evidence_role": role,
        },
        "required_fields": list(ATTEMPT_REQUIRED_FIELDS),
        "receipt": deepcopy(receipt) if receipt else None,
        "rule": (
            "A receipt can close a bounded search attempt but cannot upgrade "
            "MISSING or INELIGIBLE evidence. Only a current VERIFIED observation "
            "that explicitly declares this role can make it AVAILABLE."
        ),
    }


def _not_required_plan(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_id": "VEP:" + str(route.get("route_id") or "UNBOUND") + ":NOT_REQUIRED",
        "report_id": route.get("report_id"),
        "route_id": route.get("route_id"),
        "state": "NOT_REQUIRED",
        "evidence_role_readiness": "NOT_REQUIRED",
        "model_completion": "NOT_APPLICABLE",
        "route_validation_state": _mapping(route.get("validation")).get("state"),
        "valuation_model": None,
        "valuation_archetype": None,
        "applicability": None,
        "components": [],
        "evidence_summary": {"AVAILABLE": 0, "MISSING": 0, "INELIGIBLE": 0},
        "blocked_valuation_claims": [],
        "findings": [],
        "policy": {
            "company_values_exposed": False,
            "default_haircuts_allowed": False,
            "attempt_receipt_grants_evidence": False,
            "role_inputs_ready_authority": "DETERMINISTIC_REPLACEMENT_MODEL_ONLY",
            "valuation_claim_release_owner": "REPLACEMENT_MODEL_GATE",
        },
    }


def _route_model_projection(route_model: dict[str, Any]) -> dict[str, Any]:
    return {
        key: route_model.get(key)
        for key in (
            "route_model_id",
            "model_type",
            "role",
            "value_scope",
            "cash_flow_scope",
            "valuation_archetype_id",
            "valuation_archetype_version",
        )
    }


def compile_valuation_evidence_plan(
    *,
    route: dict[str, Any],
    company_archetype: dict[str, Any],
    fact_observations: dict[str, Any] | None = None,
    attempt_receipts: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    valuation_archetype_registry_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compile one exact route/card evidence plan.

    ``AVAILABLE`` is intentionally narrow: the current observation registry
    must contain a ``VERIFIED`` observation that declares the exact evidence
    role.  Search receipts and prose in the route never satisfy that test.
    """
    route = _mapping(route)
    company_archetype = _mapping(company_archetype)
    registry = registry or load_registry()
    route_validation = validate_valuation_route(route, company_archetype, registry)
    replacement_models = [
        item for item in _items(route.get("models"))
        if isinstance(item, dict) and item.get("route_model_id") == "REPLACEMENT_VALUE"
    ]
    if not replacement_models:
        plan = _not_required_plan(route)
        plan["route_validation_state"] = route_validation["state"]
        if route_validation["state"] == "INVALID":
            plan["state"] = "INVALID"
            plan["evidence_role_readiness"] = "BLOCKED"
            plan["findings"] = list(route_validation["invalid_findings"])
        elif route_validation["state"] == "INCOMPLETE":
            plan["state"] = "INCOMPLETE"
            plan["evidence_role_readiness"] = "BLOCKED"
            plan["findings"] = list(route_validation["incomplete_findings"])
        return plan

    findings: list[str] = []
    if len(replacement_models) != 1:
        findings.append("replacement_value_route_model_count_invalid")
    route_model = replacement_models[0]
    archetype_id = str(route_model.get("valuation_archetype_id") or "")
    version = str(route_model.get("valuation_archetype_version") or "")
    try:
        card = resolve_valuation_archetype(
            archetype_id,
            version,
            registry_dir=valuation_archetype_registry_dir,
        )
    except ValueError as exc:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "plan_id": "VEP:" + str(route.get("route_id") or "UNBOUND") + ":UNRESOLVED",
            "report_id": route.get("report_id"),
            "route_id": route.get("route_id"),
            "state": "INVALID",
            "evidence_role_readiness": "BLOCKED",
            "model_completion": "NOT_EVALUATED",
            "route_validation_state": route_validation["state"],
            "valuation_model": _route_model_projection(route_model),
            "valuation_archetype": None,
            "applicability": {"state": "INVALID", "findings": [str(exc)]},
            "components": [],
            "evidence_summary": {"AVAILABLE": 0, "MISSING": 0, "INELIGIBLE": 0},
            "blocked_valuation_claims": [
                "COMPANY_LEVEL_REPLACEMENT_RANGE",
                "PER_SHARE_REPLACEMENT_VALUE",
                "JOINT_REPLACEMENT_EPV_PROTECTION_PRICE",
            ],
            "findings": [str(exc)],
            "policy": {
                "company_values_exposed": False,
                "default_haircuts_allowed": False,
                "attempt_receipt_grants_evidence": False,
                "role_inputs_ready_authority": "DETERMINISTIC_REPLACEMENT_MODEL_ONLY",
                "valuation_claim_release_owner": "REPLACEMENT_MODEL_GATE",
            },
        }
    if not card.get("evidence_role_guidance"):
        finding = "valuation_archetype_evidence_role_guidance_missing:" + card["card_id"]
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "plan_id": "VEP:" + str(route.get("route_id") or "UNBOUND") + ":" + card["card_id"],
            "report_id": route.get("report_id"),
            "route_id": route.get("route_id"),
            "state": "INVALID",
            "evidence_role_readiness": "BLOCKED",
            "model_completion": "NOT_EVALUATED",
            "route_validation_state": route_validation["state"],
            "valuation_model": _route_model_projection(route_model),
            "valuation_archetype": {
                "card_id": card["card_id"],
                "archetype_id": card["archetype_id"],
                "version": card["version"],
                "status": card["status"],
                "valuation_family": card["valuation_family"],
            },
            "applicability": {"state": "INVALID", "findings": [finding]},
            "components": [],
            "evidence_summary": {"AVAILABLE": 0, "MISSING": 0, "INELIGIBLE": 0},
            "blocked_valuation_claims": [
                "COMPANY_LEVEL_REPLACEMENT_RANGE",
                "PER_SHARE_REPLACEMENT_VALUE",
                "JOINT_REPLACEMENT_EPV_PROTECTION_PRICE",
            ],
            "findings": [finding],
            "policy": {
                "company_values_exposed": False,
                "default_haircuts_allowed": False,
                "attempt_receipt_grants_evidence": False,
                "role_inputs_ready_authority": "DETERMINISTIC_REPLACEMENT_MODEL_ONLY",
                "valuation_claim_release_owner": "REPLACEMENT_MODEL_GATE",
            },
        }

    route_state = route_validation["state"]
    applicability_state = (
        "ROUTE_BOUND"
        if route_state == "REVIEWABLE"
        else "INCOMPLETE"
        if route_state == "INCOMPLETE"
        else "INVALID"
    )
    findings.extend(route_validation["invalid_findings"])
    findings.extend(route_validation["incomplete_findings"])

    observations = [
        item for item in _items(_mapping(fact_observations).get("observations"))
        if isinstance(item, dict)
    ]
    observation_ids = {
        str(item.get("observation_id") or "") for item in observations
        if str(item.get("observation_id") or "")
    }
    allowed_role_pairs = {
        (str(component["component_type"]), str(role))
        for component in card["required_component_specs"]
        for role in component["required_evidence_roles"]
    }
    attempt_index, attempt_findings = _attempt_receipt_index(
        _mapping(attempt_receipts),
        report_id=str(route.get("report_id") or ""),
        route_id=str(route.get("route_id") or ""),
        card_id=card["card_id"],
        allowed_role_pairs=allowed_role_pairs,
        observation_ids=observation_ids,
    )
    findings.extend(attempt_findings)
    receipts_valid = not attempt_findings

    guidance = {
        str(item.get("role")): item
        for item in card["evidence_role_guidance"]
        if isinstance(item, dict)
    }
    components: list[dict[str, Any]] = []
    summary = {state: 0 for state in sorted(EVIDENCE_STATES)}
    blocked_claims: set[str] = set()
    required_role_states: list[str] = []
    for component in card["required_component_specs"]:
        component_type = str(component["component_type"])
        required_component = component.get("presence_requirement") == "REQUIRED"
        affected_claims = (
            [
                "COMPANY_LEVEL_REPLACEMENT_RANGE",
                "PER_SHARE_REPLACEMENT_VALUE",
                "JOINT_REPLACEMENT_EPV_PROTECTION_PRICE",
            ]
            if required_component
            else ["COMPONENT_RECOGNITION"]
        )
        role_plans: list[dict[str, Any]] = []
        for role in component["required_evidence_roles"]:
            role = str(role)
            role_guidance = guidance[role]
            evidence_state, eligible_ids, ineligible_ids = _role_evidence(
                observations, role
            )
            summary[evidence_state] += 1
            if required_component:
                required_role_states.append(evidence_state)
                if evidence_state != "AVAILABLE":
                    blocked_claims.update(affected_claims)
            receipt = attempt_index.get((component_type, role))
            role_plans.append({
                "evidence_role": role,
                "requiredness": "REQUIRED_FOR_COMPONENT",
                "materiality": (
                    "BLOCKS_COMPLETE_COMPANY_RANGE"
                    if required_component
                    else "LOCAL_COMPONENT_ONLY"
                ),
                "evidence_state": evidence_state,
                "eligible_observation_ids": eligible_ids,
                "ineligible_observation_ids": ineligible_ids,
                "likely_official_sources": deepcopy(
                    role_guidance["likely_official_sources"]
                ),
                "likely_acquisition_modules": deepcopy(
                    role_guidance["likely_acquisition_modules"]
                ),
                "query_hints": deepcopy(role_guidance["query_hints"]),
                "bounded_stopping_rule": role_guidance["bounded_stopping_rule"],
                "blocked_conclusion": component["unknown_semantics"],
                "affected_valuation_claims": affected_claims,
                "unknown_treatment": (
                    "NOT_UNKNOWN"
                    if evidence_state == "AVAILABLE"
                    else "PRESERVE_LOCAL_UNKNOWN"
                ),
                "attempt_receipt": _attempt_projection(
                    component_type=component_type,
                    role=role,
                    evidence_state=evidence_state,
                    receipt=receipt,
                    receipts_valid=receipts_valid,
                ),
            })
        components.append({
            "component_type": component_type,
            "requiredness": component["presence_requirement"],
            "materiality": (
                "MATERIAL_TO_COMPLETE_REPLACEMENT_RANGE"
                if required_component
                else "OPTIONAL_COMPONENT"
            ),
            "allowed_calculation_methods": deepcopy(
                component["allowed_calculation_methods"]
            ),
            "double_count_owner": component["double_count_owner"],
            "allowed_exclusion_destinations": deepcopy(
                component["allowed_exclusion_destinations"]
            ),
            "blocked_conclusion": component["unknown_semantics"],
            "affected_valuation_claims": affected_claims,
            "evidence_roles": role_plans,
        })

    if applicability_state != "ROUTE_BOUND":
        evidence_role_readiness = "BLOCKED"
        blocked_claims.update({
            "COMPANY_LEVEL_REPLACEMENT_RANGE",
            "PER_SHARE_REPLACEMENT_VALUE",
            "JOINT_REPLACEMENT_EPV_PROTECTION_PRICE",
        })
    elif all(state == "AVAILABLE" for state in required_role_states):
        evidence_role_readiness = "ROLE_INPUTS_READY"
    else:
        evidence_role_readiness = "ROLE_INPUTS_INCOMPLETE"

    # The plan can authorize entry into the deterministic model, but it never
    # evaluates component ranges, ordinary-equity scope, per-share arithmetic,
    # or the EPV comparison.  Those conclusions remain blocked until the
    # replacement-model gate validates its own canonical result.
    blocked_claims.update({
        "COMPANY_LEVEL_REPLACEMENT_RANGE",
        "PER_SHARE_REPLACEMENT_VALUE",
        "JOINT_REPLACEMENT_EPV_PROTECTION_PRICE",
    })

    state = (
        "INVALID"
        if route_state == "INVALID"
        else "INCOMPLETE"
        if route_state == "INCOMPLETE"
        else "PLAN_READY"
    )
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_id": "VEP:" + str(route.get("route_id") or "UNBOUND") + ":" + card["card_id"],
        "report_id": route.get("report_id"),
        "route_id": route.get("route_id"),
        "state": state,
        "evidence_role_readiness": evidence_role_readiness,
        "model_completion": "NOT_EVALUATED",
        "route_validation_state": route_state,
        "valuation_model": _route_model_projection(route_model),
        "valuation_archetype": {
            "card_id": card["card_id"],
            "archetype_id": card["archetype_id"],
            "version": card["version"],
            "status": card["status"],
            "valuation_family": card["valuation_family"],
        },
        "applicability": {
            "state": applicability_state,
            "required_operating_characteristics": deepcopy(
                card["applicability"]["required_operating_characteristics"]
            ),
            "required_company_conditions": deepcopy(
                card["applicability"]["required_company_conditions"]
            ),
            "non_applicability_conditions": deepcopy(
                card["applicability"]["non_applicability_conditions"]
            ),
            "rule": (
                "ROUTE_BOUND means only that a reviewable company route selected "
                "this exact active card. Missing or ineligible company evidence "
                "still blocks the affected valuation claim."
            ),
        },
        "components": components,
        "evidence_summary": summary,
        "blocked_valuation_claims": sorted(blocked_claims),
        "findings": list(dict.fromkeys(findings)),
        "policy": {
            "company_values_exposed": False,
            "default_haircuts_allowed": False,
            "attempt_receipt_grants_evidence": False,
            "role_inputs_ready_authority": "DETERMINISTIC_REPLACEMENT_MODEL_ONLY",
            "valuation_claim_release_owner": "REPLACEMENT_MODEL_GATE",
        },
    }


def build_valuation_evidence_plan(
    output_dir: str | Path,
    *,
    persist: bool = True,
    valuation_archetype_registry_dir: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    plan = compile_valuation_evidence_plan(
        route=_read_json(output / "valuation_route.json"),
        company_archetype=_read_json(output / "company_archetype.json"),
        fact_observations=_read_json(output / "fact_observations.json"),
        attempt_receipts=_read_json(output / ATTEMPT_FILENAME),
        valuation_archetype_registry_dir=valuation_archetype_registry_dir,
    )
    if persist:
        _atomic_write_json(output / PLAN_FILENAME, plan)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile a route-bound valuation evidence plan."
    )
    parser.add_argument("output_dir")
    parser.add_argument("--registry-dir")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()
    plan = build_valuation_evidence_plan(
        args.output_dir,
        persist=not args.no_persist,
        valuation_archetype_registry_dir=args.registry_dir,
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if plan["state"] not in {"INVALID"} else 2


if __name__ == "__main__":  # pragma: no cover - CLI path
    raise SystemExit(main())
