#!/usr/bin/env python3
"""Offline V3 enterprise-judgment control objects and synthetic validators.

This module deliberately owns no acquisition, PIT outcome access, database state, or
report rendering.  It gives the existing research stack one small typed surface for
enterprise state, management decisions, mechanism/arena boundaries, and the frozen
CJO-to-investment hand-off.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any


SCHEMA_VERSION = "enterprise-judgment-v3.v1"

LANES = {
    "ENTERPRISE_MODEL", "MANAGEMENT_DECISION", "MECHANISM_LAB", "BOUNDARY",
    "PIT", "HOLDOUT", "LIVE",
}
LIFECYCLES = {"DRAFT", "EVIDENCE_OPEN", "REVIEW_READY", "FROZEN", "REOPENED", "RETIRED"}
RESOLUTIONS = {
    "UNKNOWN", "NO_PRIMARY", "MIXED", "SELECTIVE_SUPPORT", "A_ONLY", "B_ONLY",
    "NOT_DIAGNOSTIC", "PIT_BLOCKED",
}
PERMISSIONS = {
    "TEACHING_ONLY", "LEARNING_ELIGIBLE", "EVALUATION_ONLY", "INVESTMENT_INPUT",
    "REMEDIATION_ONLY",
}
ISOLATED_RESOLUTIONS = {"UNKNOWN", "NO_PRIMARY", "MIXED", "NOT_DIAGNOSTIC"}
OBSERVATION_STATES = {"OBSERVED", "INFERRED", "UNKNOWN", "CONTRADICTED"}
OVERLAP_RELATIONS = {
    "REQUIRED_EQUAL", "REQUIRED_OVERLAP", "REQUIRED_EXPOSURE", "NOT_REQUIRED",
}
ARENA_ROLES = {
    "EXTERNAL_SHOCK_COMPARATOR", "EQUILIBRIUM_RESPONSE_WITNESS", "FALSIFIER",
    "NOT_COMPARABLE",
}
BRIDGE_TYPES = {"IDENTITY", "SEGMENT_MATCH", "QUANTIFIED_ISSUER_AGGREGATION"}
HYPOTHESIS_STATUSES = {"ACTIVE", "COMBINED", "DISPLACED", "UNRESOLVED"}
MATRIX_STATES = {"EXPECTED", "COMPATIBLE", "CONTRADICTORY", "NOT_APPLICABLE", "UNKNOWN"}
DIAGNOSTICITIES = {"DISCRIMINATING", "COMMON", "CONTRADICTORY", "NONDIAGNOSTIC"}
RESEARCH_PRIORITIES = {"HIGH", "MEDIUM", "LOW", "STOP"}


class EnterpriseJudgmentError(ValueError):
    """Raised when a caller attempts an unauthorised state or investment action."""


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _result(findings: list[str], **extra: Any) -> dict[str, Any]:
    return {"state": "VALID" if not findings else "INVALID", "findings": findings, **extra}


def validate_state_vector(state: Any) -> dict[str, Any]:
    """Validate the orthogonal lane/lifecycle/resolution/permission contract."""
    value = _mapping(state)
    findings: list[str] = []
    if set(value) - {
        "lane", "lifecycle", "resolution", "permission", "frozen_at",
        "settlement_receipt", "independent_review_receipt",
    }:
        _add(findings, "state_contains_unsupported_field")
    lane = value.get("lane")
    lifecycle = value.get("lifecycle")
    resolution = value.get("resolution")
    permission = value.get("permission")
    if lane not in LANES:
        _add(findings, "lane_invalid")
    if lifecycle not in LIFECYCLES:
        _add(findings, "lifecycle_invalid")
    if resolution not in RESOLUTIONS:
        _add(findings, "resolution_invalid")
    if permission not in PERMISSIONS:
        _add(findings, "permission_invalid")
    frozen_at = _instant(value.get("frozen_at"))
    if lifecycle == "FROZEN" and frozen_at is None:
        _add(findings, "frozen_lifecycle_requires_frozen_at")
    if lifecycle != "FROZEN" and value.get("frozen_at") is not None:
        _add(findings, "nonfrozen_lifecycle_cannot_claim_frozen_at")
    if resolution == "PIT_BLOCKED" and permission != "REMEDIATION_ONLY":
        _add(findings, "pit_blocked_requires_remediation_only")
    if permission == "REMEDIATION_ONLY" and resolution != "PIT_BLOCKED":
        _add(findings, "remediation_permission_requires_pit_blocked")
    if resolution in ISOLATED_RESOLUTIONS and not (
        permission == "TEACHING_ONLY" or (lane == "HOLDOUT" and permission == "EVALUATION_ONLY")
    ):
        _add(findings, "isolated_resolution_must_be_teaching_only")
    if permission == "LEARNING_ELIGIBLE":
        if not (lane == "PIT" and lifecycle == "FROZEN" and resolution in {"A_ONLY", "B_ONLY"}):
            _add(findings, "learning_permission_requires_frozen_directional_pit")
        if not _text(value.get("settlement_receipt")) or not _text(value.get("independent_review_receipt")):
            _add(findings, "learning_permission_requires_settlement_and_independent_review_receipts")
    if permission == "EVALUATION_ONLY" and lane != "HOLDOUT":
        _add(findings, "evaluation_permission_requires_holdout_lane")
    if lane == "HOLDOUT" and permission != "EVALUATION_ONLY":
        _add(findings, "holdout_lane_is_evaluation_only")
    if permission == "INVESTMENT_INPUT":
        if not (
            lane == "ENTERPRISE_MODEL" and lifecycle == "FROZEN"
            and resolution in {"SELECTIVE_SUPPORT", "A_ONLY", "B_ONLY"}
        ):
            _add(findings, "investment_permission_requires_frozen_directional_cjo")
    return _result(findings)


def transition_state_vector(current: Any, target: Any) -> dict[str, Any]:
    """Check a lifecycle transition without smuggling a resolution upgrade."""
    before = _mapping(current)
    after = _mapping(target)
    before_result = validate_state_vector(before)
    after_result = validate_state_vector(after)
    findings = list(before_result["findings"]) + list(after_result["findings"])
    lifecycle_edges = {
        "DRAFT": {"EVIDENCE_OPEN", "RETIRED"},
        "EVIDENCE_OPEN": {"REVIEW_READY", "RETIRED"},
        "REVIEW_READY": {"FROZEN", "EVIDENCE_OPEN", "RETIRED"},
        "FROZEN": {"REOPENED", "RETIRED"},
        "REOPENED": {"EVIDENCE_OPEN", "RETIRED"},
        "RETIRED": set(),
    }
    if before.get("lane") != after.get("lane"):
        _add(findings, "lane_is_immutable_within_object")
    if after.get("lifecycle") not in lifecycle_edges.get(before.get("lifecycle"), set()):
        _add(findings, "lifecycle_transition_invalid")
    if before.get("resolution") in ISOLATED_RESOLUTIONS and after.get("resolution") not in ISOLATED_RESOLUTIONS:
        _add(findings, "isolated_resolution_cannot_upgrade_without_new_object")
    return _result(findings)


def _validate_evidence_times(items: list[Any], as_of: datetime, prefix: str, findings: list[str]) -> None:
    for index, item in enumerate(items):
        evidence = _mapping(item).get("evidence")
        for evidence_index, ref in enumerate(_items(evidence)):
            available_at = _instant(_mapping(ref).get("available_at"))
            if available_at is None:
                _add(findings, f"{prefix}[{index}].evidence[{evidence_index}].available_at_invalid")
            elif available_at > as_of:
                _add(findings, f"{prefix}[{index}].evidence[{evidence_index}].after_model_as_of")


def validate_enterprise_system_model(model: Any) -> dict[str, Any]:
    """Validate a material, multi-arena EnterpriseSystemModel projection."""
    value = _mapping(model)
    findings: list[str] = []
    required = {"model_id", "company_id", "version", "as_of", "nodes", "edges", "responsibility_unit_ids", "competitive_arena_ids"}
    for field in sorted(required):
        if field not in value or (field not in {"nodes", "edges", "responsibility_unit_ids", "competitive_arena_ids"} and not _text(value.get(field))):
            _add(findings, f"model_{field}_missing")
    as_of = _instant(value.get("as_of"))
    if as_of is None:
        _add(findings, "model_as_of_invalid")
        as_of = datetime.min.replace(tzinfo=timezone.utc)
    nodes = [_mapping(item) for item in _items(value.get("nodes"))]
    edges = [_mapping(item) for item in _items(value.get("edges"))]
    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        node_id = node.get("node_id")
        if not _text(node_id) or node_id in node_ids:
            _add(findings, f"nodes[{index}].node_id_missing_or_duplicate")
        else:
            node_ids.add(node_id)
        if node.get("observation_state") not in OBSERVATION_STATES:
            _add(findings, f"nodes[{index}].observation_state_invalid")
        if not _text(node.get("responsibility_unit_id")) or not _text(node.get("measurement_scope_id")):
            _add(findings, f"nodes[{index}].scope_identity_missing")
    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        edge_id = edge.get("edge_id")
        if not _text(edge_id) or edge_id in edge_ids:
            _add(findings, f"edges[{index}].edge_id_missing_or_duplicate")
        else:
            edge_ids.add(edge_id)
        if edge.get("from_node_id") not in node_ids or edge.get("to_node_id") not in node_ids:
            _add(findings, f"edges[{index}].endpoint_not_in_model")
        for field in ("relationship", "actor_side", "interface", "cross_side_effect", "measurement_scope_id"):
            if not _text(edge.get(field)):
                _add(findings, f"edges[{index}].{field}_missing")
        if edge.get("observation_state") not in OBSERVATION_STATES:
            _add(findings, f"edges[{index}].observation_state_invalid")
    unit_ids = value.get("responsibility_unit_ids")
    arena_ids = value.get("competitive_arena_ids")
    if not isinstance(unit_ids, list) or not unit_ids or any(not _text(item) for item in unit_ids):
        _add(findings, "model_responsibility_unit_ids_invalid")
    if not isinstance(arena_ids, list) or not arena_ids or any(not _text(item) for item in arena_ids):
        _add(findings, "model_competitive_arena_ids_invalid")
    _validate_evidence_times(nodes, as_of, "nodes", findings)
    _validate_evidence_times(edges, as_of, "edges", findings)
    return _result(findings, node_ids=node_ids, edge_ids=edge_ids)


def validate_responsibility_units(units: Any) -> dict[str, Any]:
    """Keep accounting, decision, carrier, and measurement scope distinct."""
    findings: list[str] = []
    ids: set[str] = set()
    for index, unit in enumerate(_items(units)):
        value = _mapping(unit)
        unit_id = value.get("unit_id")
        if not _text(unit_id) or unit_id in ids:
            _add(findings, f"units[{index}].unit_id_missing_or_duplicate")
        else:
            ids.add(unit_id)
        for field in ("accounting_perimeter", "decision_scope", "economic_carrier", "measurement_surface"):
            if not _text(value.get(field)):
                _add(findings, f"units[{index}].{field}_missing")
    return _result(findings, unit_ids=ids)


def validate_scope_bridges(bridges: Any, responsibility_units: Any) -> dict[str, Any]:
    """Validate the only legal path from a decision carrier to D3/D4 measurement."""
    unit_ids = validate_responsibility_units(responsibility_units)["unit_ids"]
    findings: list[str] = []
    bridge_ids: set[str] = set()
    for index, item in enumerate(_items(bridges)):
        bridge = _mapping(item)
        bridge_id = bridge.get("scope_bridge_id")
        if not _text(bridge_id) or bridge_id in bridge_ids:
            _add(findings, f"scope_bridges[{index}].id_missing_or_duplicate")
        else:
            bridge_ids.add(bridge_id)
        if bridge.get("bridge_type") not in BRIDGE_TYPES:
            _add(findings, f"scope_bridges[{index}].type_invalid")
        if bridge.get("responsibility_unit_id") not in unit_ids:
            _add(findings, f"scope_bridges[{index}].responsibility_unit_unknown")
        for field in (
            "decision_scope_ref", "economic_carrier_ref", "measurement_surface_ref",
            "accounting_perimeter_ref", "permitted_conclusion_scope",
        ):
            if not _text(bridge.get(field)):
                _add(findings, f"scope_bridges[{index}].{field}_missing")
        if bridge.get("bridge_type") == "QUANTIFIED_ISSUER_AGGREGATION":
            coverage = bridge.get("coverage_ratio")
            if not _finite(coverage) or not 0 < float(coverage) <= 1:
                _add(findings, f"scope_bridges[{index}].coverage_ratio_invalid")
            if not _text(bridge.get("cash_attribution_ref")):
                _add(findings, f"scope_bridges[{index}].cash_attribution_ref_missing")
    return _result(findings, bridge_ids=bridge_ids)


def validate_enterprise_judgment_bundle(bundle: Any) -> dict[str, Any]:
    """Cross-check the V3 objects so group cash cannot enter a local CJO by ID alone."""
    value = _mapping(bundle)
    findings: list[str] = []
    if value.get("schema_version") != SCHEMA_VERSION:
        _add(findings, "bundle_schema_version_invalid")
    model = _mapping(value.get("enterprise_system_model"))
    units = value.get("responsibility_units")
    arenas = value.get("competitive_arenas")
    ledger = value.get("management_decision_ledger")
    model_validation = validate_enterprise_system_model(model)
    unit_validation = validate_responsibility_units(units)
    arena_validation = validate_competitive_arenas(arenas, units)
    bridge_validation = validate_scope_bridges(value.get("scope_bridges"), units)
    ledger_validation = validate_management_decision_ledger(ledger)
    for prefix, result in (
        ("model", model_validation), ("units", unit_validation), ("arenas", arena_validation),
        ("scope_bridges", bridge_validation), ("ledger", ledger_validation),
    ):
        findings.extend(prefix + ":" + item for item in result["findings"])
    if not model_validation["node_ids"]:
        return _result(findings)
    if not set(model.get("responsibility_unit_ids") or []) <= unit_validation["unit_ids"]:
        _add(findings, "model_responsibility_units_not_in_bundle")
    if not set(model.get("competitive_arena_ids") or []) <= arena_validation["arena_ids"]:
        _add(findings, "model_arenas_not_in_bundle")
    cjo = _mapping(value.get("cjo"))
    if cjo.get("model_id") != model.get("model_id"):
        _add(findings, "cjo_model_mismatch")
    cjo_state = validate_state_vector(cjo.get("state"))
    findings.extend("cjo_state:" + item for item in cjo_state["findings"])
    bridge_id = cjo.get("scope_bridge_id")
    if bridge_id not in bridge_validation["bridge_ids"]:
        _add(findings, "cjo_scope_bridge_unknown")
    bridge_by_id = {
        item.get("scope_bridge_id"): item for item in map(_mapping, _items(value.get("scope_bridges")))
    }
    bridge = bridge_by_id.get(bridge_id, {})
    for index, driver in enumerate(map(_mapping, _items(cjo.get("driver_register")))):
        if not _text(driver.get("driver_id")):
            _add(findings, f"cjo.drivers[{index}].id_missing")
        if not _finite(driver.get("normalized_earnings_delta")) or not _finite(driver.get("owner_cash_delta")):
            _add(findings, f"cjo.drivers[{index}].earnings_or_cash_delta_invalid")
        if driver.get("responsibility_unit_id") != bridge.get("responsibility_unit_id"):
            _add(findings, f"cjo.drivers[{index}].responsibility_unit_does_not_match_scope_bridge")
        if driver.get("scope_bridge_id") != bridge_id:
            _add(findings, f"cjo.drivers[{index}].scope_bridge_mismatch")
    owner_cash_bridge = _mapping(cjo.get("owner_cash_bridge"))
    if _mapping(cjo.get("state")).get("permission") == "INVESTMENT_INPUT":
        required_cash = {
            "status": "CLOSED", "ordinary_share_access_status": "CLOSED",
            "permanent_loss_status": "ASSESSED",
        }
        for field, expected in required_cash.items():
            if owner_cash_bridge.get(field) != expected:
                _add(findings, "cjo.owner_cash_bridge_" + field + "_invalid")
        if owner_cash_bridge.get("scope_bridge_id") != bridge_id or not _text(owner_cash_bridge.get("evidence_ref")):
            _add(findings, "cjo.owner_cash_bridge_scope_or_evidence_missing")
    return _result(findings)


def project_enterprise_judgment_graphs(bundle: Any) -> dict[str, Any]:
    """Produce read-only Evidence/Mechanism/Investment views from one V3 bundle.

    The views are derived data, not a fourth graph or a second canonical store.
    """
    validation = validate_enterprise_judgment_bundle(bundle)
    if validation["state"] != "VALID":
        raise EnterpriseJudgmentError("enterprise_judgment_bundle_invalid:" + ",".join(validation["findings"]))
    value = _mapping(bundle)
    model = _mapping(value["enterprise_system_model"])
    evidence = []
    for kind, items in (("NODE", model["nodes"]), ("EDGE", model["edges"])):
        for item in items:
            for ref in _items(_mapping(item).get("evidence")):
                evidence.append({"source_ref": _mapping(ref).get("ref"), "available_at": _mapping(ref).get("available_at"), "supports": kind + ":" + str(_mapping(item).get("node_id") or _mapping(item).get("edge_id"))})
    cjo = _mapping(value["cjo"])
    return {
        "evidence_graph": {"sources": evidence},
        "mechanism_graph": {"nodes": deepcopy(model["nodes"]), "edges": deepcopy(model["edges"])},
        "investment_graph": {
            "cjo_id": cjo["cjo_id"], "scope_bridge_id": cjo["scope_bridge_id"],
            "drivers": deepcopy(cjo["driver_register"]), "owner_cash_bridge": deepcopy(cjo["owner_cash_bridge"]),
        },
    }


def validate_competitive_arenas(arenas: Any, responsibility_units: Any) -> dict[str, Any]:
    """Validate mechanism-defined arenas without imposing a universal geography gate."""
    unit_ids = validate_responsibility_units(responsibility_units)["unit_ids"]
    findings: list[str] = []
    arena_ids: set[str] = set()
    for index, arena_item in enumerate(_items(arenas)):
        arena = _mapping(arena_item)
        arena_id = arena.get("arena_id")
        if not _text(arena_id) or arena_id in arena_ids:
            _add(findings, f"arenas[{index}].arena_id_missing_or_duplicate")
        else:
            arena_ids.add(arena_id)
        if arena.get("responsibility_unit_id") not in unit_ids:
            _add(findings, f"arenas[{index}].responsibility_unit_unknown")
        for field in ("product_or_service_scope", "customer_task", "competition_interface", "economic_state", "window"):
            if not _text(arena.get(field)):
                _add(findings, f"arenas[{index}].{field}_missing")
        dimensions = [_mapping(item) for item in _items(arena.get("required_overlap_dimensions"))]
        if not dimensions:
            _add(findings, f"arenas[{index}].overlap_dimensions_missing")
        dimension_by_name: dict[str, str] = {}
        for dim_index, dimension in enumerate(dimensions):
            name, relation = dimension.get("dimension"), dimension.get("relation")
            if not _text(name) or relation not in OVERLAP_RELATIONS or not _text(dimension.get("rationale")):
                _add(findings, f"arenas[{index}].dimensions[{dim_index}].invalid")
            elif name in dimension_by_name:
                _add(findings, f"arenas[{index}].dimensions[{dim_index}].duplicate")
            else:
                dimension_by_name[name] = relation
        members = [_mapping(item) for item in _items(arena.get("members"))]
        if not members:
            _add(findings, f"arenas[{index}].members_missing")
        for member_index, member in enumerate(members):
            role = member.get("role")
            if not _text(member.get("member_id")) or role not in ARENA_ROLES:
                _add(findings, f"arenas[{index}].members[{member_index}].identity_or_role_invalid")
            if not _text(member.get("actor_side")) or not _text(member.get("interface")):
                _add(findings, f"arenas[{index}].members[{member_index}].side_or_interface_missing")
            evidence = {
                _mapping(item).get("dimension"): _mapping(item).get("status")
                for item in _items(member.get("overlap_evidence"))
            }
            for name, relation in dimension_by_name.items():
                if relation != "NOT_REQUIRED" and evidence.get(name) != "PROVEN":
                    _add(findings, f"arenas[{index}].members[{member_index}].{name}_not_proven")
            if role == "EXTERNAL_SHOCK_COMPARATOR":
                if member.get("same_treatment_status") != "ABSENT" or member.get("target_spillover_status") != "BOUNDED_NONE":
                    _add(findings, f"arenas[{index}].members[{member_index}].external_comparator_contaminated")
    return _result(findings, arena_ids=arena_ids)


def validate_management_decision_ledger(ledger: Any) -> dict[str, Any]:
    """Validate append-only ex-ante decision records and later outcome overlays."""
    value = _mapping(ledger)
    findings: list[str] = []
    entries = [_mapping(item) for item in _items(value.get("entries"))]
    if not _text(value.get("ledger_id")) or not entries:
        _add(findings, "ledger_identity_or_entries_missing")
    decision_ids: set[str] = set()
    for index, entry in enumerate(entries):
        decision_id = entry.get("decision_id")
        if not _text(decision_id) or decision_id in decision_ids:
            _add(findings, f"ledger.entries[{index}].decision_id_missing_or_duplicate")
        else:
            decision_ids.add(decision_id)
        cutoff = _instant(entry.get("cutoff_at"))
        if cutoff is None:
            _add(findings, f"ledger.entries[{index}].cutoff_invalid")
        ex_ante = _mapping(entry.get("ex_ante"))
        if ex_ante.get("decision_quality") not in {"SOUND", "WEAK", "INDETERMINATE"}:
            _add(findings, f"ledger.entries[{index}].ex_ante_quality_invalid")
        for field in ("objective", "alternatives", "known_unknowns", "commitment"):
            if not ex_ante.get(field):
                _add(findings, f"ledger.entries[{index}].ex_ante_{field}_missing")
        if "outcome" in ex_ante or "outcome_overlay" in ex_ante:
            _add(findings, f"ledger.entries[{index}].outcome_cannot_be_ex_ante")
        overlay = entry.get("outcome_overlay")
        if overlay is not None:
            observed_at = _instant(_mapping(overlay).get("observed_at"))
            if observed_at is None or (cutoff is not None and observed_at <= cutoff):
                _add(findings, f"ledger.entries[{index}].outcome_overlay_time_invalid")
    return _result(findings, decision_ids=decision_ids)


def validate_hypothesis_registry(registry: Any) -> dict[str, Any]:
    """Validate a qualitative diagnostic matrix; it deliberately has no score."""
    value = _mapping(registry)
    findings: list[str] = []
    hypotheses = [_mapping(item) for item in _items(value.get("hypotheses"))]
    if len(hypotheses) < 2:
        _add(findings, "hypothesis_registry_requires_at_least_two_explanations")
    ids: set[str] = set()
    for index, hypothesis in enumerate(hypotheses):
        hypothesis_id = hypothesis.get("hypothesis_id")
        if not _text(hypothesis_id) or hypothesis_id in ids:
            _add(findings, f"hypotheses[{index}].id_missing_or_duplicate")
        else:
            ids.add(hypothesis_id)
        if hypothesis.get("status") not in HYPOTHESIS_STATUSES or not _text(hypothesis.get("mechanism")):
            _add(findings, f"hypotheses[{index}].invalid")
    for row_index, row in enumerate(_items(value.get("diagnostic_matrix"))):
        row_value = _mapping(row)
        if row_value.get("diagnosticity") not in DIAGNOSTICITIES:
            _add(findings, f"diagnostic_matrix[{row_index}].diagnosticity_invalid")
        cells = _mapping(row_value.get("cells"))
        if set(cells) != ids:
            _add(findings, f"diagnostic_matrix[{row_index}].cells_must_cover_each_hypothesis")
        if any(cell not in MATRIX_STATES for cell in cells.values()):
            _add(findings, f"diagnostic_matrix[{row_index}].cell_state_invalid")
        if "score" in row_value or "weight" in row_value:
            _add(findings, f"diagnostic_matrix[{row_index}].scoring_forbidden")
    return _result(findings)


def route_research_question(question: Any) -> dict[str, Any]:
    """Route one unresolved question by decision value, never by source volume.

    This is intentionally qualitative: no probability, score, or source-count proxy
    is accepted.  A question without a discriminating official observation stops
    rather than creating an acquisition treadmill.
    """
    value = _mapping(question)
    findings: list[str] = []
    if not _text(value.get("question_id")):
        _add(findings, "research_question_id_missing")
    if value.get("materiality") not in {"HIGH", "MEDIUM", "LOW"}:
        _add(findings, "research_materiality_invalid")
    if value.get("diagnosticity") not in DIAGNOSTICITIES:
        _add(findings, "research_diagnosticity_invalid")
    if not isinstance(value.get("can_change_cjo_or_owner_cash"), bool):
        _add(findings, "research_change_impact_invalid")
    if not isinstance(value.get("official_source_available"), bool):
        _add(findings, "research_source_availability_invalid")
    if findings:
        return {"priority": "STOP", "findings": findings}
    if not value["official_source_available"]:
        return {"priority": "STOP", "findings": ["no_discriminating_official_source_available"]}
    if not value["can_change_cjo_or_owner_cash"]:
        return {"priority": "LOW", "findings": ["cannot_change_material_judgment_or_cash"]}
    if value["diagnosticity"] != "DISCRIMINATING":
        return {"priority": "STOP", "findings": ["observation_not_hypothesis_discriminating"]}
    if value["materiality"] == "HIGH":
        return {"priority": "HIGH", "findings": []}
    return {"priority": "MEDIUM", "findings": []}


def validate_decision_episode(model: Any, episode: Any) -> dict[str, Any]:
    """Bind an episode to one local unit, arena, hypothesis, and measurement contract."""
    model_validation = validate_enterprise_system_model(model)
    findings = list(model_validation["findings"])
    value = _mapping(episode)
    required = {
        "episode_id", "cutoff_at", "observed_at", "action_ref", "responsibility_unit_id", "competitive_arena_id",
        "hypothesis_registry_ref", "measurement_contract_ref", "ledger_decision_id", "state",
        "resolution", "declared_node_ids", "declared_edge_ids", "node_updates", "edge_updates",
    }
    for field in sorted(required):
        if field not in value:
            _add(findings, f"episode_{field}_missing")
    cutoff = _instant(value.get("cutoff_at"))
    if cutoff is None:
        _add(findings, "episode_cutoff_invalid")
    observed_at = _instant(value.get("observed_at"))
    model_as_of = _instant(_mapping(model).get("as_of"))
    if observed_at is None or (cutoff is not None and observed_at < cutoff):
        _add(findings, "episode_observed_at_invalid")
    if observed_at is not None and model_as_of is not None and observed_at > model_as_of:
        _add(findings, "episode_observation_after_model_as_of")
    if value.get("responsibility_unit_id") not in set(_mapping(model).get("responsibility_unit_ids") or []):
        _add(findings, "episode_responsibility_unit_not_in_model")
    if value.get("competitive_arena_id") not in set(_mapping(model).get("competitive_arena_ids") or []):
        _add(findings, "episode_competitive_arena_not_in_model")
    state = validate_state_vector(value.get("state"))
    findings.extend("episode_state:" + item for item in state["findings"])
    if _mapping(value.get("state")).get("resolution") != value.get("resolution"):
        _add(findings, "episode_resolution_must_match_state")
    if value.get("resolution") not in RESOLUTIONS:
        _add(findings, "episode_resolution_invalid")
    return _result(findings)


def apply_episode_delta(model: Any, episode: Any, *, ledger: Any | None = None) -> dict[str, Any]:
    """Apply only a sealed episode's local node/edge changes and ledger overlay."""
    validation = validate_enterprise_system_model(model)
    if validation["state"] != "VALID":
        raise EnterpriseJudgmentError("enterprise_model_invalid:" + ",".join(validation["findings"]))
    value = _mapping(episode)
    episode_validation = validate_decision_episode(model, value)
    if episode_validation["state"] != "VALID":
        raise EnterpriseJudgmentError("decision_episode_invalid:" + ",".join(episode_validation["findings"]))
    if any(field in value for field in ("company_quality", "management_quality", "overall_conclusion")):
        raise EnterpriseJudgmentError("episode_cannot_upgrade_whole_company_conclusion")
    node_ids, edge_ids = validation["node_ids"], validation["edge_ids"]
    declared_nodes = set(_items(value.get("declared_node_ids")))
    declared_edges = set(_items(value.get("declared_edge_ids")))
    if not declared_nodes <= node_ids or not declared_edges <= edge_ids:
        raise EnterpriseJudgmentError("episode_declares_unknown_model_position")
    if declared_nodes == node_ids and declared_edges == edge_ids:
        raise EnterpriseJudgmentError("episode_cannot_declare_entire_enterprise_model")
    unit_by_node = {node["node_id"]: node["responsibility_unit_id"] for node in _mapping(model).get("nodes", [])}
    if any(unit_by_node.get(node_id) != value.get("responsibility_unit_id") for node_id in declared_nodes):
        raise EnterpriseJudgmentError("episode_delta_crosses_responsibility_unit")
    changed_nodes = {item.get("node_id") for item in map(_mapping, _items(value.get("node_updates")))}
    changed_edges = {item.get("edge_id") for item in map(_mapping, _items(value.get("edge_updates")))}
    if not changed_nodes <= declared_nodes or not changed_edges <= declared_edges:
        raise EnterpriseJudgmentError("episode_update_outside_declared_local_delta")
    updated = deepcopy(_mapping(model))
    node_update_by_id = {item["node_id"]: item for item in map(_mapping, _items(value.get("node_updates")))}
    edge_update_by_id = {item["edge_id"]: item for item in map(_mapping, _items(value.get("edge_updates")))}
    for node in updated["nodes"]:
        change = node_update_by_id.get(node["node_id"])
        if change:
            if change.get("observation_state") not in OBSERVATION_STATES:
                raise EnterpriseJudgmentError("episode_node_observation_state_invalid")
            node["observation_state"] = change["observation_state"]
            node["evidence"] = list(change.get("evidence", node.get("evidence", [])))
    for edge in updated["edges"]:
        change = edge_update_by_id.get(edge["edge_id"])
        if change:
            if change.get("observation_state") not in OBSERVATION_STATES:
                raise EnterpriseJudgmentError("episode_edge_observation_state_invalid")
            edge["observation_state"] = change["observation_state"]
            edge["evidence"] = list(change.get("evidence", edge.get("evidence", [])))
    updated["version"] = f"{updated['version']}+delta:{value['episode_id']}"
    updated.setdefault("episode_deltas", []).append({
        "episode_id": value["episode_id"], "resolution": value["resolution"],
        "node_ids": sorted(changed_nodes), "edge_ids": sorted(changed_edges),
    })
    post_validation = validate_enterprise_system_model(updated)
    if post_validation["state"] != "VALID":
        raise EnterpriseJudgmentError("episode_delta_creates_invalid_model:" + ",".join(post_validation["findings"]))
    response = {"model": updated, "local_delta": updated["episode_deltas"][-1]}
    if ledger is not None:
        ledger_validation = validate_management_decision_ledger(ledger)
        if ledger_validation["state"] != "VALID":
            raise EnterpriseJudgmentError("management_ledger_invalid:" + ",".join(ledger_validation["findings"]))
        matching = [
            entry for entry in _mapping(ledger).get("entries", [])
            if _mapping(entry).get("decision_id") == value["ledger_decision_id"]
        ]
        if len(matching) != 1:
            raise EnterpriseJudgmentError("episode_ledger_decision_not_found")
        updated_ledger = deepcopy(_mapping(ledger))
        for entry in updated_ledger["entries"]:
            if entry["decision_id"] == value["ledger_decision_id"]:
                entry["outcome_overlay"] = {
                    "observed_at": value["observed_at"], "episode_id": value["episode_id"],
                    "resolution": value["resolution"], "local_delta_ref": value["episode_id"],
                }
        response["management_decision_ledger"] = updated_ledger
    return response


def validate_transport_contract(contract: Any) -> dict[str, Any]:
    """Validate a relationship-based transfer before any target application occurs."""
    value = _mapping(contract)
    findings: list[str] = []
    forbidden = {"surface_similarity", "industry_similarity", "geography_similarity", "size_similarity"}
    if forbidden & set(value):
        _add(findings, "surface_similarity_cannot_authorize_transfer")
    required_lists = {
        "source_structure", "invariants", "target_differences", "moderators",
        "required_target_observations", "break_conditions", "permitted_changes",
    }
    for field in sorted(required_lists):
        if not _items(value.get(field)):
            _add(findings, f"transport_{field}_missing")
    for index, relation in enumerate(map(_mapping, _items(value.get("source_structure")))):
        for field in ("from_node_type", "to_node_type", "relationship", "interface"):
            if not _text(relation.get(field)):
                _add(findings, f"transport_source_structure[{index}].{field}_missing")
    for index, invariant in enumerate(map(_mapping, _items(value.get("invariants")))):
        for field in ("relationship", "rationale"):
            if not _text(invariant.get(field)):
                _add(findings, f"transport_invariants[{index}].{field}_missing")
    for index, moderator in enumerate(map(_mapping, _items(value.get("moderators")))):
        for field in ("condition", "effect"):
            if not _text(moderator.get(field)):
                _add(findings, f"transport_moderators[{index}].{field}_missing")
    required_observations = [_mapping(item) for item in _items(value.get("required_target_observations"))]
    break_conditions = [_mapping(item) for item in _items(value.get("break_conditions"))]
    if any(not _text(item.get("observation_id")) or item.get("status") != "OBSERVED" for item in required_observations):
        _add(findings, "transport_target_observation_not_yet_met")
    if any(not _text(item.get("condition")) or not isinstance(item.get("triggered"), bool) for item in break_conditions):
        _add(findings, "transport_break_condition_invalid")
    if any(item.get("triggered") is True for item in break_conditions):
        _add(findings, "transport_break_condition_triggered")
    state = "PRE_APPLICATION" if not findings else "TEACHING_ONLY"
    return {"state": state, "findings": findings}


def validate_learning_transfer(
    transfer: Any, *, notes: list[dict[str, Any]], method_review: dict[str, Any], target_freeze: dict[str, Any],
) -> dict[str, Any]:
    """Require the existing cross-company receipt before a V3 transport can transfer."""
    value = _mapping(transfer)
    findings: list[str] = []
    root_causes = value.get("root_cause_classes")
    if not isinstance(root_causes, list) or not root_causes or any(
        item not in {"DATA_COVERAGE", "ACQUISITION_MODULE", "REASONING", "MODEL", "WRITING"}
        for item in root_causes
    ):
        _add(findings, "learning_transfer_root_cause_invalid")
    for field in ("economic_impact", "prohibited_assumption", "executable_remediation"):
        if not _text(value.get(field)):
            _add(findings, "learning_transfer_" + field + "_missing")
    transport = validate_transport_contract(value.get("transport_contract"))
    findings.extend("transport:" + item for item in transport["findings"])
    if transport["state"] != "PRE_APPLICATION":
        return {"state": "TEACHING_ONLY", "findings": findings or ["transport_not_ready"]}
    try:
        from scripts.judgment_learning import validate_learning_application_receipt
        application = validate_learning_application_receipt(
            _mapping(value.get("application_receipt")), notes=notes,
            method_review=method_review, target_freeze=target_freeze,
        )
    except (ImportError, TypeError, ValueError) as exc:
        return {"state": "TEACHING_ONLY", "findings": findings + ["application_receipt_unavailable:" + str(exc)]}
    findings.extend("application_receipt:" + item for item in application["findings"])
    return {
        "state": "LEARNING_TRANSFERRED" if not findings and application["state"] == "REVIEWABLE" else "TEACHING_ONLY",
        "findings": findings,
    }


def compile_production_buy_band(cjo: Any, financial_contract: Any) -> dict[str, Any]:
    """Compile a synthetic production BuyBand only from a frozen investment-eligible CJO."""
    value = _mapping(cjo)
    state = validate_state_vector(value.get("state"))
    if state["state"] != "VALID" or _mapping(value.get("state")).get("permission") != "INVESTMENT_INPUT":
        raise EnterpriseJudgmentError("production_buy_band_requires_frozen_investment_eligible_cjo")
    drivers = [_mapping(item) for item in _items(value.get("driver_register"))]
    if not drivers:
        raise EnterpriseJudgmentError("frozen_cjo_requires_driver_register")
    owner_cash_bridge = _mapping(value.get("owner_cash_bridge"))
    required_cash_controls = {
        "status": "CLOSED", "ordinary_share_access_status": "CLOSED",
        "permanent_loss_status": "ASSESSED",
    }
    if any(owner_cash_bridge.get(field) != expected for field, expected in required_cash_controls.items()):
        raise EnterpriseJudgmentError("production_buy_band_requires_independent_d4_cash_access_and_permanent_loss_controls")
    if not _text(owner_cash_bridge.get("scope_bridge_id")) or not _text(owner_cash_bridge.get("evidence_ref")):
        raise EnterpriseJudgmentError("production_buy_band_requires_owner_cash_scope_bridge_and_evidence")
    data = _mapping(financial_contract)
    required = {
        "base_normalized_earnings", "base_owner_cash",
        "share_count", "required_return", "market_price", "holding_years", "annual_distribution",
    }
    if any(not _finite(data.get(field)) for field in required):
        raise EnterpriseJudgmentError("financial_contract_requires_finite_values")
    if data["share_count"] <= 0 or data["required_return"] <= 0 or data["holding_years"] <= 0:
        raise EnterpriseJudgmentError("financial_contract_economic_parameter_invalid")
    normalized_earnings_delta = 0.0
    owner_cash_delta = 0.0
    for driver in drivers:
        if not _finite(driver.get("normalized_earnings_delta")) or not _finite(driver.get("owner_cash_delta")):
            raise EnterpriseJudgmentError("driver_requires_independent_earnings_and_owner_cash_deltas")
        if driver.get("scope_bridge_id") != owner_cash_bridge["scope_bridge_id"]:
            raise EnterpriseJudgmentError("driver_scope_bridge_does_not_match_owner_cash_bridge")
        normalized_earnings_delta += float(driver["normalized_earnings_delta"])
        owner_cash_delta += float(driver["owner_cash_delta"])
    normalized_earnings = float(data["base_normalized_earnings"]) + normalized_earnings_delta
    owner_cash = float(data["base_owner_cash"]) + owner_cash_delta
    per_share_owner_cash = owner_cash / float(data["share_count"])
    required_return = float(data["required_return"])
    annual_distribution = float(data["annual_distribution"])
    years = int(data["holding_years"])
    terminal_value = per_share_owner_cash / required_return
    distribution_pv = sum(annual_distribution / (1 + required_return) ** year for year in range(1, years + 1))
    buy_band_upper = distribution_pv + terminal_value / (1 + required_return) ** years
    # Use the same finite-horizon identity as BuyBand.  A perpetuity shortcut
    # (price * r) would silently ignore scheduled owner distributions and can
    # reverse the stated expectation gap.
    price_implied_terminal_value = (
        float(data["market_price"]) - distribution_pv
    ) * (1 + required_return) ** years
    price_implied_owner_cash = price_implied_terminal_value * required_return
    return {
        "normalized_earnings": normalized_earnings,
        "owner_cash": owner_cash,
        "per_share_owner_cash": per_share_owner_cash,
        "expectation_gap": per_share_owner_cash - price_implied_owner_cash,
        "price_implied_owner_cash": price_implied_owner_cash,
        "buy_band": {"lower": None, "upper": buy_band_upper, "condition": "FROZEN_CJO_AND_OWNER_CASH_CONTRACT"},
    }
