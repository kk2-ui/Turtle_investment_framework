#!/usr/bin/env python3
"""Offline historical Decision Contract -> CJO teaching-mirror validator.

This module is intentionally a *projection check*, not a second CJO store or
an investment interface.  It proves that a contract-first Forecast V2 can be
translated into a frozen teaching-only V3 CJO, and that acquisition gaps remain
visible as CJO guardrails.  It never creates an Investment Overlay, normalised
earnings, owner-cash valuation, price, BuyBand, report, or learning authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

try:
    from scripts import enterprise_judgment_v3 as v3
    from scripts import judgment_pit_forecast as pit
    from scripts import judgment_training_decision_contract as decision_contract
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_v3 as v3
    import judgment_pit_forecast as pit
    import judgment_training_decision_contract as decision_contract


SCHEMA_VERSION = "turtle-training-cjo-mirror.v1"
ALLOWED_OUTPUTS = ["CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"]
OVERLAY_PROHIBITED_OUTPUTS = [
    "NORMALIZED_EARNINGS", "OWNER_CASH", "EXPECTATION_GAP", "BUYBAND", "INVESTMENT_INPUT", "REPORT_USE",
]

_ROOT_KEYS = {
    "schema_version", "mirror_id", "decision_contract_ref", "forecast_ref", "enterprise_model_ref", "cjo_ref",
    "forecast_dimension_routing", "overlay_boundary", "roles", "object_class", "claim_class", "allowed_outputs",
}
_CONTRACT_REF_KEYS = {"contract_id", "contract_version"}
_FORECAST_REF_KEYS = {"forecast_id"}
_MODEL_REF_KEYS = {"model_id", "version", "as_of"}
_CJO_REF_KEYS = {"cjo_id"}
_ROUTING_KEYS = {"dimension_id", "treatment", "question_or_guardrail"}
_OVERLAY_KEYS = {"status", "prohibited_outputs", "next_step"}
_ROLE_KEYS = {"judgment_owner_id", "independent_challenger_id"}
_TEACHING_CJO_RESOLUTIONS = {"UNKNOWN", "NO_PRIMARY", "MIXED", "SELECTIVE_SUPPORT", "NOT_DIAGNOSTIC"}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
        return item
    for field in sorted(set(item).difference(allowed)):
        findings.append(f"{path}_contains_unapproved_field:{field}")
    for field in sorted(allowed.difference(item)):
        findings.append(f"{path}_missing_required_field:{field}")
    return item


def _require_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        findings.append(f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _reference(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _closed(value, allowed, path, findings)
    for field in allowed:
        if field == "contract_version":
            version = item.get(field)
            if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                findings.append(f"{path}.contract_version_must_be_positive_integer")
        else:
            _require_text(item, field, path, findings)
    return item


def validate_training_cjo_mirror(
    mirror: Any, *, contract: Any, forecast: Any, enterprise_bundle: Any, universe_snapshot: Any, stage0_package: Any,
) -> dict[str, Any]:
    """Validate an offline teaching projection without authorising an overlay.

    The caller must separately use the forecast control plane to prove that the
    contract and Forecast V2 were persistently frozen.  This pure validator is
    deliberately unable to turn the V3 offline object into a canonical CJO.
    """
    findings: list[str] = []
    item = _closed(mirror, _ROOT_KEYS, "cjo_mirror", findings)
    if item.get("schema_version") != SCHEMA_VERSION:
        findings.append("cjo_mirror.schema_version_invalid")
    _require_text(item, "mirror_id", "cjo_mirror", findings)
    if item.get("object_class") != "HISTORICAL_CJO_TRAINING_MIRROR":
        findings.append("cjo_mirror.object_class_invalid")
    if item.get("claim_class") != "CONTRACT_FIRST_CJO_REPLAY":
        findings.append("cjo_mirror.claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append("cjo_mirror.allowed_outputs_must_exclude_overlay_report_and_investment")

    contract_ref = _reference(item.get("decision_contract_ref"), _CONTRACT_REF_KEYS, "cjo_mirror.decision_contract_ref", findings)
    forecast_ref = _reference(item.get("forecast_ref"), _FORECAST_REF_KEYS, "cjo_mirror.forecast_ref", findings)
    model_ref = _reference(item.get("enterprise_model_ref"), _MODEL_REF_KEYS, "cjo_mirror.enterprise_model_ref", findings)
    cjo_ref = _reference(item.get("cjo_ref"), _CJO_REF_KEYS, "cjo_mirror.cjo_ref", findings)

    forecast_validation = pit.validate_company_state_forecast(
        forecast, universe_snapshot=universe_snapshot, stage0_package=stage0_package,
    )
    findings.extend("forecast:" + finding for finding in forecast_validation["findings"])
    contract_validation = decision_contract.validate_contract_for_forecast(contract, forecast)
    findings.extend("decision_contract:" + finding for finding in contract_validation["findings"])
    contract_item = _mapping(contract)
    forecast_item = _mapping(forecast)
    if forecast_item.get("schema_version") != pit.FORECAST_SCHEMA_VERSION_V2 or forecast_item.get("forecast_epoch_id") != pit.FORECAST_EPOCH_ID_V2:
        findings.append("cjo_mirror.requires_contract_first_forecast_v2")
    expected_contract_ref = {
        "contract_id": contract_item.get("contract_id"), "contract_version": contract_item.get("contract_version"),
    }
    if contract_ref != expected_contract_ref or forecast_item.get("decision_contract_ref") != expected_contract_ref:
        findings.append("cjo_mirror.decision_contract_reference_must_match_forecast_v2")
    if forecast_ref.get("forecast_id") != forecast_item.get("forecast_id"):
        findings.append("cjo_mirror.forecast_reference_must_match_forecast")

    bundle_validation = v3.validate_enterprise_judgment_bundle(enterprise_bundle)
    findings.extend("enterprise_bundle:" + finding for finding in bundle_validation["findings"])
    bundle = _mapping(enterprise_bundle)
    model = _mapping(bundle.get("enterprise_system_model"))
    cjo = _mapping(bundle.get("cjo"))
    if model_ref.get("model_id") != model.get("model_id") or model_ref.get("version") != model.get("version"):
        findings.append("cjo_mirror.enterprise_model_reference_must_match_bundle")
    if cjo_ref.get("cjo_id") != cjo.get("cjo_id"):
        findings.append("cjo_mirror.cjo_reference_must_match_bundle")
    model_as_of = _instant(model.get("as_of"), "enterprise_model.as_of", findings)
    ref_as_of = _instant(model_ref.get("as_of"), "cjo_mirror.enterprise_model_ref.as_of", findings)
    cutoff = _instant(forecast_item.get("cutoff_at"), "forecast.cutoff_at", findings)
    if model_as_of is not None and cutoff is not None and model_as_of != cutoff:
        findings.append("cjo_mirror.model_as_of_must_match_forecast_cutoff")
    if ref_as_of is not None and model_as_of is not None and ref_as_of != model_as_of:
        findings.append("cjo_mirror.enterprise_model_ref_as_of_must_match_bundle")
    if model.get("company_id") != forecast_item.get("issuer_id"):
        findings.append("cjo_mirror.enterprise_model_company_must_match_forecast_issuer")
    if cjo.get("model_id") != model.get("model_id"):
        findings.append("cjo_mirror.cjo_model_must_match_enterprise_model")

    state = _mapping(cjo.get("state"))
    if not (
        state.get("lane") == "ENTERPRISE_MODEL"
        and state.get("lifecycle") == "FROZEN"
        and state.get("permission") == "TEACHING_ONLY"
        and state.get("resolution") in _TEACHING_CJO_RESOLUTIONS
    ):
        findings.append("cjo_mirror.requires_frozen_teaching_only_cjo")
    cjo_frozen_at = _instant(state.get("frozen_at"), "cjo.state.frozen_at", findings)
    if cjo_frozen_at is not None and cutoff is not None and cjo_frozen_at < cutoff:
        findings.append("cjo_mirror.cjo_must_not_freeze_before_forecast_cutoff")

    routes = _items(item.get("forecast_dimension_routing"))
    forecast_by_dimension = {
        _mapping(raw).get("dimension_id"): _mapping(raw) for raw in _items(forecast_item.get("dimensions"))
    }
    route_dimensions: set[str] = set()
    for index, raw in enumerate(routes):
        route = _closed(raw, _ROUTING_KEYS, f"cjo_mirror.forecast_dimension_routing[{index}]", findings)
        dimension_id = _require_text(route, "dimension_id", f"cjo_mirror.forecast_dimension_routing[{index}]", findings)
        if dimension_id in route_dimensions:
            findings.append("cjo_mirror.forecast_dimension_routing_must_not_repeat_dimension")
        route_dimensions.add(dimension_id)
        forecast_dimension = forecast_by_dimension.get(dimension_id, {})
        expected_treatment = {
            "MODEL_UNCERTAIN": "CJO_REVIEW_QUESTION",
            "EVIDENCE_INELIGIBLE": "CJO_UNKNOWN_GUARDRAIL",
        }.get(forecast_dimension.get("evidence_status"))
        if expected_treatment is None:
            findings.append(f"cjo_mirror.forecast_dimension_routing[{index}].dimension_not_in_forecast")
        elif route.get("treatment") != expected_treatment:
            findings.append(f"cjo_mirror.forecast_dimension_routing[{index}].treatment_must_preserve_forecast_evidence_status")
        _require_text(route, "question_or_guardrail", f"cjo_mirror.forecast_dimension_routing[{index}]", findings)
    if route_dimensions != set(pit.FORECAST_DIMENSIONS):
        findings.append("cjo_mirror.must_route_each_forecast_dimension_exactly_once")

    overlay = _closed(item.get("overlay_boundary"), _OVERLAY_KEYS, "cjo_mirror.overlay_boundary", findings)
    if overlay.get("status") != "NOT_AUTHORIZED":
        findings.append("cjo_mirror.historical_training_cannot_authorize_investment_overlay")
    if overlay.get("prohibited_outputs") != OVERLAY_PROHIBITED_OUTPUTS:
        findings.append("cjo_mirror.overlay_boundary_must_prohibit_value_price_buyband_and_report")
    if overlay.get("next_step") != "RESEARCH_AGENDA_ONLY":
        findings.append("cjo_mirror.overlay_boundary_next_step_must_remain_research_agenda")

    roles = _closed(item.get("roles"), _ROLE_KEYS, "cjo_mirror.roles", findings)
    for field in _ROLE_KEYS:
        _require_text(roles, field, "cjo_mirror.roles", findings)
    contract_roles = _mapping(contract_item.get("roles"))
    if any(roles.get(field) != contract_roles.get(field) for field in _ROLE_KEYS):
        findings.append("cjo_mirror.roles_must_match_decision_contract")

    return {"valid": not findings, "findings": findings, "cjo_mirror": deepcopy(item) if not findings else None}


def compile_minimal_teaching_bundle(
    forecast: Any, *, stage0_package: Any, cjo_frozen_at: str,
) -> dict[str, Any]:
    """Derive the smallest teaching-only V3 bundle from a frozen Forecast V2.

    This is intentionally a structural projection: H1 supplies issuer identity,
    responsibility boundary and arena vocabulary; the forecast supplies the six
    questions.  It does not invent a causal mechanism, normal earnings, owner
    cash, price, or an investment-ready CJO.
    """
    findings: list[str] = []
    forecast_item = _mapping(forecast)
    if (
        forecast_item.get("schema_version") != pit.FORECAST_SCHEMA_VERSION_V2
        or forecast_item.get("forecast_epoch_id") != pit.FORECAST_EPOCH_ID_V2
    ):
        findings.append("cjo_mirror.requires_contract_first_forecast_v2")
    cutoff = _instant(forecast_item.get("cutoff_at"), "forecast.cutoff_at", findings)
    frozen_at = _instant(cjo_frozen_at, "cjo_mirror.cjo_frozen_at", findings)
    if cutoff is not None and frozen_at is not None and frozen_at < cutoff:
        findings.append("cjo_mirror.cjo_must_not_freeze_before_forecast_cutoff")
    package = _mapping(stage0_package)
    company_id = forecast_item.get("company_id")
    member = next(
        (
            _mapping(item) for item in _items(package.get("members"))
            if _mapping(item).get("company_id") == company_id
        ),
        {},
    )
    if not member:
        findings.append("cjo_mirror.forecast_company_must_belong_to_h1_package")
    if member.get("issuer_id") != forecast_item.get("issuer_id"):
        findings.append("cjo_mirror.h1_issuer_must_match_forecast")
    responsibility_unit_id = member.get("responsibility_unit_id")
    boundary = _mapping(member.get("boundary"))
    arena_source = _mapping(package.get("competitive_arena"))
    arena_id = member.get("competitive_arena_id")
    if arena_id != arena_source.get("competitive_arena_id"):
        findings.append("cjo_mirror.h1_member_arena_must_match_package_arena")
    for field, value in (
        ("responsibility_unit_id", responsibility_unit_id),
        ("boundary.perimeter_id", boundary.get("perimeter_id")),
        ("competitive_arena_id", arena_id),
    ):
        if not _text(value):
            findings.append(f"cjo_mirror.h1_{field}_required")
    if findings:
        return {"valid": False, "findings": findings, "enterprise_bundle": None}

    forecast_id = str(forecast_item["forecast_id"])
    issuer_id = str(forecast_item["issuer_id"])
    unit_id = str(responsibility_unit_id)
    scope_bridge_id = f"BRIDGE:TEACHING:{forecast_id}"
    model_id = f"ESM:TEACHING:{forecast_id}"
    operating_node = f"NODE:TEACHING:OPERATING:{forecast_id}"
    cash_node = f"NODE:TEACHING:CASH:{forecast_id}"
    bundle = {
        "schema_version": v3.SCHEMA_VERSION,
        "enterprise_system_model": {
            "model_id": model_id,
            "company_id": issuer_id,
            "version": "1",
            "as_of": forecast_item["cutoff_at"],
            "responsibility_unit_ids": [unit_id],
            "competitive_arena_ids": [arena_id],
            "nodes": [
                {
                    "node_id": operating_node,
                    "observation_state": "OBSERVED",
                    "responsibility_unit_id": unit_id,
                    "measurement_scope_id": f"SCOPE:TEACHING:OPERATING:{forecast_id}",
                },
                {
                    "node_id": cash_node,
                    "observation_state": "UNKNOWN",
                    "responsibility_unit_id": unit_id,
                    "measurement_scope_id": f"SCOPE:TEACHING:CASH:{forecast_id}",
                },
            ],
            "edges": [{
                "edge_id": f"EDGE:TEACHING:OPERATING-CASH:{forecast_id}",
                "from_node_id": operating_node,
                "to_node_id": cash_node,
                "relationship": "operating_state_to_cash_conversion",
                "actor_side": "ISSUER_CONSOLIDATED",
                "interface": "issuer-consolidated operating and cash system",
                "cross_side_effect": "cash conversion and capital burden remain explicit forecast questions",
                "measurement_scope_id": f"SCOPE:TEACHING:CASH:{forecast_id}",
                "observation_state": "UNKNOWN",
            }],
        },
        "responsibility_units": [{
            "unit_id": unit_id,
            "accounting_perimeter": boundary["perimeter_id"],
            "decision_scope": "H1 issuer-consolidated historical forecast scope",
            "economic_carrier": str(arena_source.get("product_or_service_scope")),
            "measurement_surface": "cutoff operating state, cash conversion and permanent-loss guardrails",
        }],
        "competitive_arenas": [{
            "arena_id": arena_id,
            "responsibility_unit_id": unit_id,
            "product_or_service_scope": str(arena_source.get("product_or_service_scope")),
            "customer_task": str(arena_source.get("customer_end_market_scope")),
            "competition_interface": "H1 industry context only; no causal comparator or treatment claim",
            "economic_state": "cutoff-visible H1 industry state",
            "window": forecast_item["cutoff_at"],
            "required_overlap_dimensions": [{
                "dimension": "H1_STATIC_ARENA_FAMILY",
                "relation": "NOT_REQUIRED",
                "rationale": "teaching mirror is issuer-specific and makes no comparative causal claim",
            }],
            "members": [{
                "member_id": issuer_id,
                "role": "NOT_COMPARABLE",
                "actor_side": "ISSUER_CONSOLIDATED",
                "interface": "issuer-consolidated operating system",
                "overlap_evidence": [],
            }],
        }],
        "scope_bridges": [{
            "scope_bridge_id": scope_bridge_id,
            "bridge_type": "IDENTITY",
            "responsibility_unit_id": unit_id,
            "decision_scope_ref": "H1 issuer-consolidated historical forecast scope",
            "economic_carrier_ref": str(arena_source.get("product_or_service_scope")),
            "measurement_surface_ref": "forecast six-dimension teaching surface",
            "accounting_perimeter_ref": boundary["perimeter_id"],
            "permitted_conclusion_scope": "teaching-only issuer state questions and coverage guardrails",
        }],
        "management_decision_ledger": {
            "ledger_id": f"LEDGER:TEACHING:{forecast_id}",
            "entries": [{
                "decision_id": f"DECISION:TEACHING:{forecast_id}",
                "cutoff_at": forecast_item["cutoff_at"],
                "decision_type": "OPERATING",
                "ex_ante": {
                    "decision_quality": "INDETERMINATE",
                    "objective": "preserve cutoff-visible operating state as a training question",
                    "alternatives": ["defer any company conclusion until an independently authorised research epoch"],
                    "known_unknowns": ["owner cash access", "capital burden", "permanent-loss path"],
                    "commitment": "freeze forecast questions and coverage gaps without an investment overlay",
                },
            }],
        },
        "cjo": {
            "cjo_id": f"CJO:TEACHING:{forecast_id}",
            "model_id": model_id,
            "state": {
                "lane": "ENTERPRISE_MODEL",
                "lifecycle": "FROZEN",
                "resolution": "MIXED",
                "permission": "TEACHING_ONLY",
                "frozen_at": cjo_frozen_at,
            },
            "scope_bridge_id": scope_bridge_id,
            "owner_cash_bridge": {
                "status": "OPEN_FOR_RESEARCH_ONLY",
                "ordinary_share_access_status": "UNKNOWN",
                "permanent_loss_status": "UNKNOWN",
                "scope_bridge_id": scope_bridge_id,
                "evidence_ref": str(forecast_id),
            },
            "driver_register": [{
                "driver_id": f"DRIVER:TEACHING:OPERATING:{forecast_id}",
                "responsibility_unit_id": unit_id,
                "scope_bridge_id": scope_bridge_id,
                "normalized_earnings_delta": 0.0,
                "owner_cash_delta": 0.0,
            }],
        },
    }
    validation = v3.validate_enterprise_judgment_bundle(bundle)
    findings.extend("enterprise_bundle:" + finding for finding in validation["findings"])
    return {
        "valid": not findings,
        "findings": findings,
        "enterprise_bundle": deepcopy(bundle) if not findings else None,
    }


def compile_training_cjo_mirror(
    contract: Any, forecast: Any, *, universe_snapshot: Any, stage0_package: Any, cjo_frozen_at: str,
) -> dict[str, Any]:
    """Compile a teaching mirror from contract-first inputs without persisting a second CJO."""
    bundle_result = compile_minimal_teaching_bundle(
        forecast, stage0_package=stage0_package, cjo_frozen_at=cjo_frozen_at,
    )
    findings = list(bundle_result["findings"])
    bundle = _mapping(bundle_result.get("enterprise_bundle"))
    contract_item = _mapping(contract)
    forecast_item = _mapping(forecast)
    dimensions = [_mapping(item) for item in _items(forecast_item.get("dimensions"))]
    mirror = {
        "schema_version": SCHEMA_VERSION,
        "mirror_id": f"MIRROR:TEACHING:{forecast_item.get('forecast_id')}",
        "decision_contract_ref": deepcopy(forecast_item.get("decision_contract_ref")),
        "forecast_ref": {"forecast_id": forecast_item.get("forecast_id")},
        "enterprise_model_ref": {
            "model_id": _mapping(bundle.get("enterprise_system_model")).get("model_id"),
            "version": _mapping(bundle.get("enterprise_system_model")).get("version"),
            "as_of": _mapping(bundle.get("enterprise_system_model")).get("as_of"),
        },
        "cjo_ref": {"cjo_id": _mapping(bundle.get("cjo")).get("cjo_id")},
        "forecast_dimension_routing": [{
            "dimension_id": dimension.get("dimension_id"),
            "treatment": "CJO_REVIEW_QUESTION" if dimension.get("evidence_status") == "MODEL_UNCERTAIN" else "CJO_UNKNOWN_GUARDRAIL",
            "question_or_guardrail": "Retain the Forecast V2 dimension as a teaching question or explicit coverage guardrail; do not derive an investment overlay.",
        } for dimension in dimensions],
        "overlay_boundary": {
            "status": "NOT_AUTHORIZED",
            "prohibited_outputs": list(OVERLAY_PROHIBITED_OUTPUTS),
            "next_step": "RESEARCH_AGENDA_ONLY",
        },
        "roles": {
            "judgment_owner_id": _mapping(contract_item.get("roles")).get("judgment_owner_id"),
            "independent_challenger_id": _mapping(contract_item.get("roles")).get("independent_challenger_id"),
        },
        "object_class": "HISTORICAL_CJO_TRAINING_MIRROR",
        "claim_class": "CONTRACT_FIRST_CJO_REPLAY",
        "allowed_outputs": list(ALLOWED_OUTPUTS),
    }
    if bundle:
        validation = validate_training_cjo_mirror(
            mirror, contract=contract, forecast=forecast, enterprise_bundle=bundle,
            universe_snapshot=universe_snapshot, stage0_package=stage0_package,
        )
        findings.extend("compiled_mirror:" + finding for finding in validation["findings"])
    return {
        "valid": not findings,
        "findings": findings,
        "enterprise_bundle": deepcopy(bundle) if not findings else None,
        "cjo_mirror": deepcopy(mirror) if not findings else None,
    }
