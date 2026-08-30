#!/usr/bin/env python3
"""Compose one complete, price-separated enterprise underwriting episode.

This is a small read-model layer, not a new evidence store, CJO, valuation
engine, or report pipeline.  It keeps the business judgment in one immutable
``UnderwritingThesis`` and derives three price-free views for the existing CJO,
valuation-routing, and report systems.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from scripts.reader_coverage import reader_boundary_findings


EPISODE_SCHEMA = "enterprise-underwriting-episode.v2"
THESIS_PROJECTION_SCHEMA = "enterprise-underwriting-thesis-projection.v1"
CJO_PROJECTION_SCHEMA = "enterprise-underwriting-cjo-candidate-projection.v2"
VALUATION_REQUEST_SCHEMA = "enterprise-underwriting-valuation-route-request.v2"
REPORT_HANDOFF_SCHEMA = "enterprise-underwriting-golden-report-handoff.v2"
COMPONENT_DECISION_SUMMARY_SCHEMA = "enterprise-underwriting-component-decision-summary.v1"

SAMPLE_IDENTITIES = {"WORKED_CASE", "BLIND_REPLAY", "PROSPECTIVE_EPISODE"}
TREATMENTS = {
    "UNDERWRITE",
    "CONDITIONALLY_UNDERWRITE",
    "SCENARIO_ONLY",
    "EXCLUDE_FROM_BASE",
    "CANNOT_BOUND",
}
ECONOMIC_DIRECTIONS = {"IMPROVES", "DETERIORATES", "MIXED", "UNKNOWN", "NONE"}
COMPONENT_DECISION_SCOPES = {
    "SURVIVAL_FINANCING",
    "MATURE_CORE_NORMAL_EARNINGS",
    "ORDINARY_SHARE_OWNER_CASH",
    "GROWTH_CAPITAL_RETURN",
    "NONCORE_OR_OPTIONAL_ASSET",
    "OTHER_MATERIAL_COMPONENT",
}
EARNINGS_AND_CASH_USE_ORDER = (
    "BASE_RANGE",
    "CONDITIONAL_RANGE",
    "SCENARIO_ONLY",
    "EXCLUDED",
    "UNRESOLVED",
    "NOT_APPLICABLE",
)
EARNINGS_AND_CASH_USES = set(EARNINGS_AND_CASH_USE_ORDER)
FINANCING_PRESSURE_EFFECT_ORDER = (
    "REDUCES",
    "NEUTRAL",
    "INCREASES",
    "CONDITIONAL",
    "UNRESOLVED",
    "NOT_APPLICABLE",
)
FINANCING_PRESSURE_EFFECTS = set(FINANCING_PRESSURE_EFFECT_ORDER)
PERMANENT_LOSS_USE_ORDER = (
    "BASE_PATH",
    "CONDITIONAL_PATH",
    "STRESS_ONLY",
    "EXCLUDED",
    "UNRESOLVED",
    "NOT_APPLICABLE",
)
PERMANENT_LOSS_USES = set(PERMANENT_LOSS_USE_ORDER)
VALUATION_USE_ORDER = (
    "PRIMARY_INPUT",
    "CONDITIONAL_PRIMARY_INPUT",
    "CORROBORATIVE_INPUT",
    "SCENARIO_ONLY",
    "STRESS_ONLY",
    "EXCLUDED",
    "UNRESOLVED",
    "NOT_APPLICABLE",
)
VALUATION_USES = set(VALUATION_USE_ORDER)
VALUATION_USE_AUTHORITY_PRIORITY = (
    "PRIMARY_INPUT",
    "CONDITIONAL_PRIMARY_INPUT",
    "CORROBORATIVE_INPUT",
    "SCENARIO_ONLY",
    "STRESS_ONLY",
    "UNRESOLVED",
    "EXCLUDED",
    "NOT_APPLICABLE",
)

_COMPONENT_DECISION_READER_LABELS = {
    "BASE_RANGE": "进入基准范围",
    "CONDITIONAL_RANGE": "只进入条件范围",
    "SCENARIO_ONLY": "只进入情景",
    "EXCLUDED": "排除",
    "UNRESOLVED": "尚未形成可承保范围",
    "NOT_APPLICABLE": "不适用",
    "REDUCES": "降低融资压力",
    "NEUTRAL": "不改变融资压力",
    "INCREASES": "增加融资压力",
    "CONDITIONAL": "对融资压力的影响取决于条件",
    "BASE_PATH": "进入基准永久损失路径",
    "CONDITIONAL_PATH": "进入条件性永久损失路径",
    "STRESS_ONLY": "只进入压力情景",
    "PRIMARY_INPUT": "作为主要估值输入",
    "CONDITIONAL_PRIMARY_INPUT": "只作为条件性主要估值输入",
    "CORROBORATIVE_INPUT": "只作估值交叉验证",
}

_ROOT = Path(__file__).resolve().parents[1]
_THESIS_FORBIDDEN_KEYS = {
    "price",
    "market_price",
    "share_price",
    "entry_price",
    "buyband",
    "buy_band",
    "investment_action",
    "valuation_result",
    "expected_return",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _findings(findings: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "enterprise-underwriting-episode-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in _THESIS_FORBIDDEN_KEYS:
                findings.append(child)
            else:
                findings.extend(_forbidden_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_paths(item, f"{path}[{index}]"))
    return findings


def _reference_exists(reference: Any) -> bool:
    text = str(reference or "").split("#", 1)[0].strip()
    if not text or "://" in text:
        return False
    if (_ROOT / text).is_file():
        return True
    # Production source packages use canonical source identities (for example
    # ``SRC:OPERATING``) rather than repository filenames.  Standalone Episode
    # validation accepts that identity shape; the formal CJO compiler and the
    # training contract each bind it to their actual source allowlist.
    return text.startswith(("SRC:", "OBS:", "DOC:", "CALC:", "canonical:"))


def _industry_future_thesis(episode: dict[str, Any]) -> dict[str, Any]:
    situation_model = _mapping(episode.get("situation_model"))
    return _mapping(situation_model.get("industry_future_thesis"))


def _component_use_buckets(
    component_decisions: list[Any], field: str, ordered_values: tuple[str, ...],
) -> dict[str, list[str]]:
    """Group component identities by one explicit downstream economic use."""

    buckets = {value: [] for value in ordered_values}
    for raw in component_decisions:
        item = _mapping(raw)
        component_id = item.get("component_id")
        use = item.get(field)
        if _text(component_id) and use in buckets:
            buckets[use].append(str(component_id))
    return buckets


def _first_populated_use(
    buckets: dict[str, list[str]], priority: tuple[str, ...],
) -> str:
    for use in priority:
        if buckets.get(use):
            return use
    return "NOT_APPLICABLE"


def _valuation_route_component_bindings(
    component_decisions: list[Any],
) -> list[dict[str, Any]]:
    route_index: dict[str, dict[str, list[str]]] = {}
    for raw in component_decisions:
        decision = _mapping(raw)
        component_id = decision.get("component_id")
        if not _text(component_id):
            continue
        for raw_binding in _items(decision.get("valuation_route_bindings")):
            binding = _mapping(raw_binding)
            route_id = binding.get("route_id")
            use = binding.get("use")
            if not _text(route_id) or use not in VALUATION_USES:
                continue
            buckets = route_index.setdefault(
                str(route_id), {value: [] for value in VALUATION_USE_ORDER}
            )
            buckets[str(use)].append(str(component_id))
    return [
        {"route_id": route_id, "components_by_use": route_index[route_id]}
        for route_id in sorted(route_index)
    ]


def derive_component_decision_summary(component_decisions: Any) -> dict[str, Any]:
    """Compile the decision ledger into five authoritative downstream routes.

    The prose thesis remains useful explanation.  These buckets are the
    machine-consumed authority for whether a component can enter normal
    earnings, owner cash, financing pressure, permanent-loss analysis, or a
    valuation route.  They are deliberately derived rather than independently
    authored so changing one component decision must propagate everywhere.
    """

    decisions = _items(component_decisions)
    normal = _component_use_buckets(
        decisions, "normal_earnings_use", EARNINGS_AND_CASH_USE_ORDER
    )
    owner_cash = _component_use_buckets(
        decisions, "owner_cash_use", EARNINGS_AND_CASH_USE_ORDER
    )
    financing = _component_use_buckets(
        decisions, "financing_pressure_effect", FINANCING_PRESSURE_EFFECT_ORDER
    )
    permanent_loss = _component_use_buckets(
        decisions, "permanent_loss_use", PERMANENT_LOSS_USE_ORDER
    )
    valuation = _component_use_buckets(
        decisions, "valuation_use", VALUATION_USE_ORDER
    )
    return {
        "schema_version": COMPONENT_DECISION_SUMMARY_SCHEMA,
        "normal_earnings": {
            "range_authority": _first_populated_use(
                normal,
                (
                    "BASE_RANGE", "CONDITIONAL_RANGE", "SCENARIO_ONLY",
                    "UNRESOLVED", "EXCLUDED", "NOT_APPLICABLE",
                ),
            ),
            "components_by_use": normal,
        },
        "owner_cash": {
            "range_authority": _first_populated_use(
                owner_cash,
                (
                    "BASE_RANGE", "CONDITIONAL_RANGE", "SCENARIO_ONLY",
                    "UNRESOLVED", "EXCLUDED", "NOT_APPLICABLE",
                ),
            ),
            "components_by_use": owner_cash,
        },
        "financing_pressure": {
            "active_effects": [
                effect for effect in FINANCING_PRESSURE_EFFECT_ORDER
                if financing[effect]
            ],
            "components_by_effect": financing,
        },
        "permanent_loss": {
            "path_authority": _first_populated_use(
                permanent_loss,
                (
                    "BASE_PATH", "CONDITIONAL_PATH", "STRESS_ONLY",
                    "UNRESOLVED", "EXCLUDED", "NOT_APPLICABLE",
                ),
            ),
            "components_by_use": permanent_loss,
        },
        "valuation": {
            "route_authority": _first_populated_use(
                valuation,
                VALUATION_USE_AUTHORITY_PRIORITY,
            ),
            "components_by_use": valuation,
            "route_component_bindings": _valuation_route_component_bindings(
                decisions
            ),
        },
    }


def _authoritative_thesis_treatments(
    thesis: dict[str, Any], component_decision_summary: dict[str, Any],
) -> dict[str, str]:
    """Prevent a prose treatment from outranking the component ledger."""

    if not component_decision_summary:
        return {
            "normal_earnings_treatment": str(thesis.get("normal_earnings_treatment") or ""),
            "owner_cash_treatment": str(thesis.get("owner_cash_treatment") or ""),
            "permanent_loss_treatment": str(thesis.get("permanent_loss_treatment") or ""),
        }
    normal_authority = component_decision_summary["normal_earnings"][
        "range_authority"
    ]
    owner_cash_authority = component_decision_summary["owner_cash"][
        "range_authority"
    ]
    permanent_loss_authority = component_decision_summary["permanent_loss"][
        "path_authority"
    ]
    normal = str(thesis.get("normal_earnings_treatment") or "")
    owner_cash = str(thesis.get("owner_cash_treatment") or "")
    permanent_loss = str(thesis.get("permanent_loss_treatment") or "")
    if normal_authority not in {"BASE_RANGE", "CONDITIONAL_RANGE"}:
        normal = (
            f"组件账的正常盈利权限为 {normal_authority}，未授权形成基准或条件性"
            "正常盈利范围；叙事不得将其升级为已承保盈利。"
        )
    if owner_cash_authority not in {"BASE_RANGE", "CONDITIONAL_RANGE"}:
        owner_cash = (
            f"组件账的普通股现金权限为 {owner_cash_authority}，未授权形成基准或"
            "条件性 owner-cash 范围；叙事不得把现金代理升级为已承保范围。"
        )
    if permanent_loss_authority not in {"BASE_PATH", "CONDITIONAL_PATH"}:
        permanent_loss = (
            f"组件账的永久损失权限为 {permanent_loss_authority}，未授权形成基准或"
            "条件性损失路径；仅可按该权限进入压力、未决或排除处理。"
        )
    return {
        "normal_earnings_treatment": normal,
        "owner_cash_treatment": owner_cash,
        "permanent_loss_treatment": permanent_loss,
    }


def _component_decision_findings(
    component_treatments: list[Any], component_decisions: Any,
) -> list[str]:
    """Validate explicit component-to-investment semantics when supplied.

    Historical Episodes remain readable without this additive ledger.  New
    training contracts can require it so a component label cannot masquerade
    as a different base-earnings, owner-cash, financing, loss, or value use.
    """

    if component_decisions is None:
        return []
    if not isinstance(component_decisions, list) or not component_decisions:
        return ["component_decisions.must_be_non_empty_list"]
    decisions = component_decisions
    findings: list[str] = []
    treatments = {
        _mapping(item).get("component_id"): _mapping(item).get("treatment")
        for item in component_treatments
        if _text(_mapping(item).get("component_id"))
    }
    decision_ids: set[str] = set()
    required_fields = {
        "component_id",
        "economic_scope",
        "normal_earnings_use",
        "owner_cash_use",
        "financing_pressure_effect",
        "permanent_loss_use",
        "valuation_use",
        "valuation_route_bindings",
        "promotion_test",
        "invalidation_test",
    }
    for index, raw in enumerate(decisions):
        path = f"component_decisions[{index}]"
        item = _mapping(raw)
        if set(item) != required_fields:
            findings.append(path + ".fields_invalid")
        component_id = item.get("component_id")
        if not _text(component_id) or component_id in decision_ids:
            findings.append(path + ".component_id_missing_or_duplicate")
        else:
            decision_ids.add(component_id)
        if item.get("economic_scope") not in COMPONENT_DECISION_SCOPES:
            findings.append(path + ".economic_scope_invalid")
        if item.get("normal_earnings_use") not in EARNINGS_AND_CASH_USES:
            findings.append(path + ".normal_earnings_use_invalid")
        if item.get("owner_cash_use") not in EARNINGS_AND_CASH_USES:
            findings.append(path + ".owner_cash_use_invalid")
        if item.get("financing_pressure_effect") not in FINANCING_PRESSURE_EFFECTS:
            findings.append(path + ".financing_pressure_effect_invalid")
        if item.get("permanent_loss_use") not in PERMANENT_LOSS_USES:
            findings.append(path + ".permanent_loss_use_invalid")
        if item.get("valuation_use") not in VALUATION_USES:
            findings.append(path + ".valuation_use_invalid")
        route_bindings = item.get("valuation_route_bindings")
        if not isinstance(route_bindings, list):
            findings.append(path + ".valuation_route_bindings_invalid")
            route_bindings = []
        if not route_bindings and item.get("valuation_use") != "NOT_APPLICABLE":
            findings.append(path + ".valuation_route_bindings_required_for_valuation_use")
        binding_ids: set[str] = set()
        binding_uses: set[str] = set()
        for binding_index, raw_binding in enumerate(route_bindings):
            binding_path = f"{path}.valuation_route_bindings[{binding_index}]"
            binding = _mapping(raw_binding)
            if set(binding) != {"route_id", "use"}:
                findings.append(binding_path + ".fields_invalid")
            route_id = binding.get("route_id")
            if not _text(route_id) or route_id in binding_ids:
                findings.append(binding_path + ".route_id_missing_or_duplicate")
            else:
                binding_ids.add(str(route_id))
            if binding.get("use") not in VALUATION_USES:
                findings.append(binding_path + ".use_invalid")
            else:
                binding_uses.add(str(binding["use"]))
        if binding_uses:
            aggregate_use = next(
                use for use in VALUATION_USE_AUTHORITY_PRIORITY
                if use in binding_uses
            )
            if item.get("valuation_use") != aggregate_use:
                findings.append(path + ".valuation_use_not_derived_from_route_bindings")
        for field in ("promotion_test", "invalidation_test"):
            if not _text(item.get(field)):
                findings.append(path + "." + field + "_missing")

        treatment = treatments.get(component_id)
        base_use = (
            item.get("normal_earnings_use") == "BASE_RANGE"
            or item.get("owner_cash_use") == "BASE_RANGE"
            or item.get("valuation_use") == "PRIMARY_INPUT"
        )
        if treatment in {"SCENARIO_ONLY", "EXCLUDE_FROM_BASE", "CANNOT_BOUND"} and base_use:
            findings.append(path + ".base_use_conflicts_with_component_treatment")
        if treatment == "CANNOT_BOUND" and "UNRESOLVED" not in {
            item.get("normal_earnings_use"),
            item.get("owner_cash_use"),
            item.get("financing_pressure_effect"),
            item.get("permanent_loss_use"),
            item.get("valuation_use"),
        }:
            findings.append(path + ".cannot_bound_requires_unresolved_downstream_use")
        if treatment == "CONDITIONALLY_UNDERWRITE" and not (
            item.get("normal_earnings_use") == "CONDITIONAL_RANGE"
            or item.get("owner_cash_use") == "CONDITIONAL_RANGE"
            or item.get("financing_pressure_effect") == "CONDITIONAL"
            or item.get("permanent_loss_use") == "CONDITIONAL_PATH"
            or item.get("valuation_use") == "CONDITIONAL_PRIMARY_INPUT"
        ):
            findings.append(path + ".conditional_treatment_requires_conditional_downstream_use")

    if decision_ids != set(treatments):
        findings.append("component_decisions.must_cover_each_component_treatment_once")
    return findings


def _component_decision_summary_findings(
    component_decisions: Any,
    component_decision_summary: Any,
    value_route: Any,
) -> list[str]:
    """Bind the stored summary and primary value route to the component ledger."""

    if component_decisions is None:
        return (
            ["component_decision_summary.not_allowed_without_component_decisions"]
            if component_decision_summary is not None
            else []
        )
    if not isinstance(component_decisions, list) or not component_decisions:
        return []
    expected = derive_component_decision_summary(component_decisions)
    findings: list[str] = []
    if not isinstance(component_decision_summary, dict):
        findings.append(
            "component_decision_summary.required_when_component_decisions_present"
        )
    elif component_decision_summary != expected:
        findings.append(
            "component_decision_summary.not_exact_deterministic_derivation"
        )

    route = _mapping(value_route)
    decision_ids = {
        str(_mapping(item).get("component_id"))
        for item in component_decisions
        if _text(_mapping(item).get("component_id"))
    }
    raw_requirements = route.get("route_component_requirements")
    requirements_by_route: dict[str, dict[str, list[str]]] = {}
    if not isinstance(raw_requirements, list) or not raw_requirements:
        findings.append("value_route.route_component_requirements_missing")
        raw_requirements = []
    for index, raw_requirement in enumerate(raw_requirements):
        path = f"value_route.route_component_requirements[{index}]"
        requirement = _mapping(raw_requirement)
        if set(requirement) != {
            "route_id", "required_component_ids", "optional_component_ids",
        }:
            findings.append(path + ".fields_invalid")
        route_id = requirement.get("route_id")
        if not _text(route_id) or route_id in requirements_by_route:
            findings.append(path + ".route_id_missing_or_duplicate")
            continue
        required = requirement.get("required_component_ids")
        optional = requirement.get("optional_component_ids")
        if (
            not isinstance(required, list)
            or not required
            or any(not _text(item) for item in required)
            or len(required) != len(set(required))
        ):
            findings.append(path + ".required_component_ids_invalid")
            required = []
        if (
            not isinstance(optional, list)
            or any(not _text(item) for item in optional)
            or len(optional) != len(set(optional))
        ):
            findings.append(path + ".optional_component_ids_invalid")
            optional = []
        if set(required) & set(optional):
            findings.append(path + ".required_and_optional_components_overlap")
        unknown = (set(required) | set(optional)) - decision_ids
        if unknown:
            findings.append(path + ".component_id_not_in_decision_ledger")
        requirements_by_route[str(route_id)] = {
            "required_component_ids": [str(item) for item in required],
            "optional_component_ids": [str(item) for item in optional],
        }

    route_components = {
        item["route_id"]: item["components_by_use"]
        for item in expected["valuation"]["route_component_bindings"]
    }
    for route_id, components_by_use in route_components.items():
        requirement = requirements_by_route.get(route_id)
        if requirement is None:
            findings.append(
                f"value_route.bound_route_missing_component_requirement:{route_id}"
            )
            continue
        eligible = set(requirement["required_component_ids"]) | set(
            requirement["optional_component_ids"]
        )
        bound_components = {
            component_id
            for use in VALUATION_USE_ORDER
            for component_id in _items(components_by_use.get(use))
        }
        for component_id in sorted(bound_components - eligible):
            findings.append(
                "value_route.route_binding_component_not_eligible:"
                f"{route_id}:{component_id}"
            )
    roles = _mapping(route.get("valuation_model_roles"))
    route_groups = {
        "primary": list(dict.fromkeys(
            _items(route.get("primary_routes")) + _items(roles.get("primary"))
        )),
        "corroborative": _items(roles.get("corroborative")),
        "stress": _items(roles.get("stress")),
        "excluded": _items(route.get("excluded_routes")),
    }
    allowed_uses = {
        "primary": {"PRIMARY_INPUT", "CONDITIONAL_PRIMARY_INPUT"},
        "corroborative": {
            "PRIMARY_INPUT", "CONDITIONAL_PRIMARY_INPUT", "CORROBORATIVE_INPUT",
        },
        "stress": {
            "PRIMARY_INPUT", "CONDITIONAL_PRIMARY_INPUT", "CORROBORATIVE_INPUT",
            "STRESS_ONLY",
        },
        "excluded": {
            "SCENARIO_ONLY", "EXCLUDED", "UNRESOLVED", "NOT_APPLICABLE",
        },
    }
    active_route_groups: dict[str, set[str]] = {}
    for group, route_ids in route_groups.items():
        for raw_route_id in route_ids:
            route_id = str(raw_route_id or "")
            if not route_id:
                continue
            active_route_groups.setdefault(route_id, set()).add(group)
            components_by_use = route_components.get(route_id, {})
            requirement = requirements_by_route.get(route_id)
            if requirement is None:
                findings.append(
                    f"value_route.{group}_route_missing_component_requirement:{route_id}"
                )
                continue
            if not any(
                _items(components_by_use.get(use)) for use in allowed_uses[group]
            ):
                findings.append(
                    f"value_route.{group}_route_unbound_or_ineligible:{route_id}"
                )
            eligible_components = {
                component_id
                for use in allowed_uses[group]
                for component_id in _items(components_by_use.get(use))
            }
            for component_id in requirement["required_component_ids"]:
                if component_id not in eligible_components:
                    findings.append(
                        f"value_route.{group}_route_required_component_ineligible:"
                        f"{route_id}:{component_id}"
                    )
    for route_id, groups in active_route_groups.items():
        if "excluded" in groups and len(groups) > 1:
            findings.append(
                f"value_route.route_cannot_be_active_and_excluded:{route_id}"
            )
    return findings


def validate_enterprise_underwriting_episode(episode: Any) -> dict[str, Any]:
    """Check the economic continuity and the one-way price boundary.

    The validator deliberately does not require every possible input.  An
    episode may retain a local ``CANNOT_BOUND`` component while still making a
    useful survival, normalization, permanent-loss, and valuation-route call.
    """
    value = _mapping(episode)
    findings: list[str] = []
    required = (
        "episode_id", "company_id", "company_name", "cutoff_at", "sample_identity",
        "decision_frame", "underwriting_route", "situation_model", "business_position",
        "survival_case", "adaptation_case", "normalization_case", "permanent_loss_map",
        "value_route", "strongest_rival", "reversal_observations", "component_treatments",
        "evidence_trace", "existing_object_refs", "underwriting_thesis", "investment_treatment",
    )
    if value.get("schema_version") != EPISODE_SCHEMA:
        findings.append("schema_version_invalid")
    for field in required:
        if field in {"component_treatments", "evidence_trace", "existing_object_refs", "reversal_observations"}:
            if not _items(value.get(field)):
                findings.append(field + "_missing")
        elif field == "underwriting_thesis":
            if not _mapping(value.get(field)):
                findings.append(field + "_missing")
        elif not _text(value.get(field)) and not _mapping(value.get(field)):
            findings.append(field + "_missing")
    if value.get("sample_identity") not in SAMPLE_IDENTITIES:
        findings.append("sample_identity_invalid")

    situation_model = _mapping(value.get("situation_model"))
    if not _text(situation_model.get("summary")):
        findings.append("situation_model.summary_missing")
    industry_future = _industry_future_thesis(value)
    for field in (
        "horizon", "most_likely_regime", "profit_pool_transmission", "company_exposure",
        "adaptation", "normal_economics", "permanent_loss", "valuation_treatment",
        "strongest_rival",
    ):
        if not _text(industry_future.get(field)):
            findings.append("situation_model.industry_future_thesis." + field + "_missing")
    industry_reversals = _items(industry_future.get("reversal_observations"))
    if not industry_reversals or any(not _text(item) for item in industry_reversals):
        findings.append("situation_model.industry_future_thesis.reversal_observations_invalid")
    findings.extend(
        "situation_model.industry_future_thesis.price_boundary:" + item
        for item in _forbidden_paths(industry_future)
    )

    evidence_ids: set[str] = set()
    for index, item in enumerate(_items(value.get("evidence_trace"))):
        evidence = _mapping(item)
        evidence_id = evidence.get("evidence_id")
        if not _text(evidence_id) or evidence_id in evidence_ids:
            findings.append(f"evidence_trace[{index}].evidence_id_missing_or_duplicate")
        else:
            evidence_ids.add(evidence_id)
        for field in ("source_ref", "locator", "scope", "used_for"):
            if not _text(evidence.get(field)):
                findings.append(f"evidence_trace[{index}].{field}_missing")
        if not _reference_exists(evidence.get("source_ref")):
            findings.append(f"evidence_trace[{index}].source_ref_missing")

    component_ids: set[str] = set()
    for index, item in enumerate(_items(value.get("component_treatments"))):
        component = _mapping(item)
        component_id = component.get("component_id")
        if not _text(component_id) or component_id in component_ids:
            findings.append(f"component_treatments[{index}].component_id_missing_or_duplicate")
        else:
            component_ids.add(component_id)
        if component.get("treatment") not in TREATMENTS:
            findings.append(f"component_treatments[{index}].treatment_invalid")
        for field in ("reason", "investment_consequence", "promotion_or_resolution_condition"):
            if not _text(component.get(field)):
                findings.append(f"component_treatments[{index}].{field}_missing")
        refs = _items(component.get("evidence_ids"))
        if not refs or any(ref not in evidence_ids for ref in refs):
            findings.append(f"component_treatments[{index}].evidence_ids_invalid")
    findings.extend(
        _component_decision_findings(
            _items(value.get("component_treatments")), value.get("component_decisions")
        )
    )
    findings.extend(
        _component_decision_summary_findings(
            value.get("component_decisions"),
            value.get("component_decision_summary"),
            value.get("value_route"),
        )
    )

    thesis = _mapping(value.get("underwriting_thesis"))
    for field in (
        "thesis_id", "central_path", "normal_earnings_treatment", "owner_cash_treatment",
        "permanent_loss_treatment", "value_route_treatment", "strongest_rival", "monitoring",
    ):
        if not _text(thesis.get(field)):
            findings.append("underwriting_thesis." + field + "_missing")
    directions = _mapping(thesis.get("economic_directions"))
    for field in ("normal_earnings", "owner_cash", "permanent_loss"):
        if directions.get(field) not in ECONOMIC_DIRECTIONS:
            findings.append(
                "underwriting_thesis.economic_directions." + field + "_invalid"
            )
    findings.extend("underwriting_thesis.price_boundary:" + item for item in _forbidden_paths(thesis))
    if industry_future:
        if value.get("strongest_rival") != industry_future.get("strongest_rival"):
            findings.append("strongest_rival_not_derived_from_industry_future_thesis")
        if thesis.get("strongest_rival") != industry_future.get("strongest_rival"):
            findings.append("underwriting_thesis.strongest_rival_not_derived_from_industry_future_thesis")
        if value.get("reversal_observations") != industry_future.get("reversal_observations"):
            findings.append("reversal_observations_not_derived_from_industry_future_thesis")

    value_route = _mapping(value.get("value_route"))
    for field in ("primary_routes", "excluded_routes", "route_reasoning", "valuation_model_roles"):
        route_value = value_route.get(field)
        if field.endswith("routes"):
            if not _items(route_value):
                findings.append("value_route." + field + "_missing")
        elif field == "valuation_model_roles":
            roles = _mapping(route_value)
            if not _items(roles.get("primary")):
                findings.append("value_route.valuation_model_roles_missing")
            for role in ("corroborative", "stress"):
                if role in roles and not isinstance(roles.get(role), list):
                    findings.append(
                        "value_route.valuation_model_roles." + role + "_invalid"
                    )
        elif not _text(route_value):
            findings.append("value_route." + field + "_missing")

    for index, item in enumerate(_items(value.get("existing_object_refs"))):
        reference = _mapping(item)
        for field in ("kind", "ref", "role"):
            if not _text(reference.get(field)):
                findings.append(f"existing_object_refs[{index}].{field}_missing")
        if not _reference_exists(reference.get("ref")):
            findings.append(f"existing_object_refs[{index}].ref_missing")
    return _findings(findings)


def _assert_reviewable(episode: Any) -> dict[str, Any]:
    result = validate_enterprise_underwriting_episode(episode)
    if result["state"] != "REVIEWABLE":
        raise ValueError("enterprise_underwriting_episode_invalid:" + ",".join(result["findings"]))
    return _mapping(episode)


def project_price_free_underwriting_thesis(episode: Any) -> dict[str, Any]:
    """Return the one price-free object shared by CJO, valuation and report consumers."""
    value = _assert_reviewable(episode)
    thesis = _mapping(value["underwriting_thesis"])
    projection = {
        "schema_version": THESIS_PROJECTION_SCHEMA,
        "episode_id": value["episode_id"],
        "company_id": value["company_id"],
        "cutoff_at": value["cutoff_at"],
        "sample_identity": value["sample_identity"],
        "underwriting_thesis_id": thesis["thesis_id"],
        "decision_frame": value["decision_frame"],
        "underwriting_route": value["underwriting_route"],
        "situation_model": deepcopy(value["situation_model"]),
        "business_position": value["business_position"],
        "survival_case": value["survival_case"],
        "adaptation_case": value["adaptation_case"],
        "normalization_case": value["normalization_case"],
        "permanent_loss_map": value["permanent_loss_map"],
        "value_route": deepcopy(value["value_route"]),
        "strongest_rival": value["strongest_rival"],
        "reversal_observations": deepcopy(value["reversal_observations"]),
        "component_treatments": deepcopy(value["component_treatments"]),
        "evidence_trace": deepcopy(value["evidence_trace"]),
        "underwriting_thesis": deepcopy(thesis),
    }
    if _items(value.get("component_decisions")):
        projection["component_decisions"] = deepcopy(value["component_decisions"])
        projection["component_decision_summary"] = deepcopy(
            value["component_decision_summary"]
        )
    forbidden = _forbidden_paths(projection)
    if forbidden:
        raise ValueError("price_free_underwriting_thesis_invalid:" + ",".join(forbidden))
    return projection


def validate_price_free_underwriting_thesis_projection(projection: Any) -> dict[str, Any]:
    """Validate the complete price-free object after its source Episode is absent."""
    value = _mapping(projection)
    findings: list[str] = []
    if value.get("schema_version") != THESIS_PROJECTION_SCHEMA:
        findings.append("schema_version_invalid")
    for field in (
        "episode_id", "company_id", "cutoff_at", "sample_identity",
        "underwriting_thesis_id", "decision_frame", "underwriting_route",
        "business_position", "survival_case", "adaptation_case",
        "normalization_case", "permanent_loss_map", "strongest_rival",
    ):
        if not _text(value.get(field)):
            findings.append(field + "_missing")
    for field in ("reversal_observations", "component_treatments", "evidence_trace"):
        if not _items(value.get(field)):
            findings.append(field + "_missing")
    findings.extend(
        _component_decision_findings(
            _items(value.get("component_treatments")), value.get("component_decisions")
        )
    )
    situation = _mapping(value.get("situation_model"))
    if not _text(situation.get("summary")):
        findings.append("situation_model.summary_missing")
    industry = _mapping(situation.get("industry_future_thesis"))
    for field in (
        "horizon", "most_likely_regime", "profit_pool_transmission",
        "company_exposure", "adaptation", "normal_economics",
        "permanent_loss", "valuation_treatment", "strongest_rival",
    ):
        if not _text(industry.get(field)):
            findings.append("situation_model.industry_future_thesis." + field + "_missing")
    if not _items(industry.get("reversal_observations")):
        findings.append("situation_model.industry_future_thesis.reversal_observations_missing")
    if "industry_future_thesis" in value:
        findings.append("legacy_top_level_industry_future_thesis_not_allowed")
    thesis = _mapping(value.get("underwriting_thesis"))
    for field in (
        "thesis_id", "central_path", "normal_earnings_treatment", "owner_cash_treatment",
        "permanent_loss_treatment", "value_route_treatment", "strongest_rival", "monitoring",
    ):
        if not _text(thesis.get(field)):
            findings.append("underwriting_thesis." + field + "_missing")
    directions = _mapping(thesis.get("economic_directions"))
    for field in ("normal_earnings", "owner_cash", "permanent_loss"):
        if directions.get(field) not in ECONOMIC_DIRECTIONS:
            findings.append(
                "underwriting_thesis.economic_directions." + field + "_invalid"
            )
    if thesis.get("thesis_id") != value.get("underwriting_thesis_id"):
        findings.append("underwriting_thesis_id_mismatch")
    if thesis.get("strongest_rival") != value.get("strongest_rival"):
        findings.append("strongest_rival_mismatch")
    route = _mapping(value.get("value_route"))
    findings.extend(
        _component_decision_summary_findings(
            value.get("component_decisions"),
            value.get("component_decision_summary"),
            route,
        )
    )
    if not _items(route.get("primary_routes")) or not _items(route.get("excluded_routes")):
        findings.append("value_route.routes_missing")
    if not _text(route.get("route_reasoning")):
        findings.append("value_route.route_reasoning_missing")
    roles = _mapping(route.get("valuation_model_roles"))
    if not _items(roles.get("primary")):
        findings.append("value_route.valuation_model_roles_missing")
    for role in ("corroborative", "stress"):
        if role in roles and not isinstance(roles.get(role), list):
            findings.append("value_route.valuation_model_roles." + role + "_invalid")
    findings.extend("price_boundary:" + path for path in _forbidden_paths(value))
    return _findings(findings)


def compile_underwriting_projections(episode: Any) -> dict[str, dict[str, Any]]:
    """Project one thesis into existing-consumer-shaped, price-free views."""
    value = _assert_reviewable(episode)
    price_free = project_price_free_underwriting_thesis(value)
    thesis = deepcopy(_mapping(price_free["underwriting_thesis"]))
    situation_model = deepcopy(_mapping(price_free["situation_model"]))
    industry_future = deepcopy(_mapping(situation_model["industry_future_thesis"]))
    component_decisions = deepcopy(_items(value.get("component_decisions")))
    component_decision_summary = (
        derive_component_decision_summary(component_decisions)
        if component_decisions
        else {}
    )
    authoritative_treatments = _authoritative_thesis_treatments(
        thesis, component_decision_summary
    )
    identity = {
        "episode_id": value["episode_id"],
        "company_id": value["company_id"],
        "cutoff_at": value["cutoff_at"],
        "sample_identity": value["sample_identity"],
        "underwriting_thesis_id": thesis["thesis_id"],
    }
    cjo_candidate = {
        "schema_version": CJO_PROJECTION_SCHEMA,
        "projection_id": "UW-CJO:" + value["episode_id"],
        **identity,
        "authority": "TEACHING_CANDIDATE_ONLY",
        "central_path": thesis["central_path"],
        "situation_model": deepcopy(situation_model),
        "normal_earnings_treatment": authoritative_treatments[
            "normal_earnings_treatment"
        ],
        "owner_cash_treatment": authoritative_treatments["owner_cash_treatment"],
        "permanent_loss_treatment": authoritative_treatments[
            "permanent_loss_treatment"
        ],
        "strongest_rival": industry_future["strongest_rival"],
        "monitoring": thesis["monitoring"],
        "component_treatments": deepcopy(value["component_treatments"]),
        "existing_cjo_adapter": "scripts/enterprise_judgment_core.py:compile_cjo_candidate",
        "boundary": "A projection for the existing CJO compiler; it is not a Frozen CJO and cannot authorize value, price, BuyBand, report publication, or investment action.",
    }
    if component_decisions:
        cjo_candidate["component_decisions"] = deepcopy(component_decisions)
        cjo_candidate["normal_earnings_component_route"] = deepcopy(
            component_decision_summary["normal_earnings"]
        )
        cjo_candidate["owner_cash_component_route"] = deepcopy(
            component_decision_summary["owner_cash"]
        )
        cjo_candidate["financing_pressure_component_route"] = deepcopy(
            component_decision_summary["financing_pressure"]
        )
        cjo_candidate["permanent_loss_component_route"] = deepcopy(
            component_decision_summary["permanent_loss"]
        )
    valuation_request = {
        "schema_version": VALUATION_REQUEST_SCHEMA,
        "request_id": "UW-VR:" + value["episode_id"],
        **identity,
        "authority": "ROUTE_REQUEST_ONLY",
        "situation_model": deepcopy(situation_model),
        "primary_routes": deepcopy(value["value_route"]["primary_routes"]),
        "excluded_routes": deepcopy(value["value_route"]["excluded_routes"]),
        "route_reasoning": value["value_route"]["route_reasoning"],
        "valuation_model_roles": deepcopy(value["value_route"]["valuation_model_roles"]),
        "normal_earnings_input_treatment": authoritative_treatments[
            "normal_earnings_treatment"
        ],
        "owner_cash_input_treatment": authoritative_treatments[
            "owner_cash_treatment"
        ],
        "permanent_loss_input_treatment": authoritative_treatments[
            "permanent_loss_treatment"
        ],
        "inputs_excluded_from_base": (
            [
                item["component_id"] for item in component_decisions
                if item["valuation_use"] not in {
                    "PRIMARY_INPUT", "CONDITIONAL_PRIMARY_INPUT"
                }
            ]
            if component_decisions
            else [
                item["component_id"] for item in value["component_treatments"]
                if item["treatment"] in {
                    "EXCLUDE_FROM_BASE", "SCENARIO_ONLY", "CANNOT_BOUND"
                }
            ]
        ),
        "existing_valuation_adapter": "scripts/valuation_routing.py:build_valuation_route",
        "compatibility_resolution": "Current-company underwriting may enter CJO and valuation routing through a source-bound, independently reviewed complete Episode; SELECTION_ADMITTED remains local to claims that actually depend on comparative selection or causal authority.",
        "boundary": "No current value, price, expected return, BuyBand, or investment action is generated.",
    }
    if component_decisions:
        valuation_request["component_decisions"] = deepcopy(component_decisions)
        valuation_request["valuation_component_route"] = deepcopy(
            component_decision_summary["valuation"]
        )
        valuation_request["route_component_requirements"] = deepcopy(
            value["value_route"]["route_component_requirements"]
        )
    report_handoff = {
        "schema_version": REPORT_HANDOFF_SCHEMA,
        "handoff_id": "UW-GR:" + value["episode_id"],
        **identity,
        "authority": "UNDERWRITING_HANDOFF_ONLY",
        "reader_order": [
            "central_path",
            "industry_future_transmission",
            "situation_and_route",
            "survival_and_adaptation",
            "normalization_and_owner_cash",
            "permanent_loss_and_rival",
            "value_route_and_research_treatment",
            "reversal_observations",
        ],
        "central_path": thesis["central_path"],
        "situation_model": deepcopy(situation_model),
        "business_position": value["business_position"],
        "survival_case": value["survival_case"],
        "adaptation_case": value["adaptation_case"],
        "normalization_case": value["normalization_case"],
        "owner_cash_treatment": authoritative_treatments["owner_cash_treatment"],
        "permanent_loss_map": value["permanent_loss_map"],
        "value_route": deepcopy(value["value_route"]),
        "strongest_rival": industry_future["strongest_rival"],
        "reversal_observations": deepcopy(industry_future["reversal_observations"]),
        "existing_report_adapter": "scripts/judgment_generation_handoff.py:build_judgment_generation_handoff",
        "boundary": "The Golden Report writer consumes this thesis and may not replace it with a different company story. This is a teaching handoff, not report-publication authority.",
    }
    if component_decisions:
        report_handoff["component_decisions"] = deepcopy(component_decisions)
        report_handoff["normal_earnings_treatment"] = authoritative_treatments[
            "normal_earnings_treatment"
        ]
        report_handoff["permanent_loss_treatment"] = authoritative_treatments[
            "permanent_loss_treatment"
        ]
        report_handoff["component_economic_routes"] = deepcopy(
            component_decision_summary
        )
    return {
        "cjo_candidate_projection": cjo_candidate,
        "valuation_route_request": valuation_request,
        "golden_report_underwriting_handoff": report_handoff,
    }


def validate_underwriting_projection_bundle(episode: Any, bundle: Any) -> dict[str, Any]:
    """Ensure every downstream view remains a verbatim projection of one thesis."""
    value = _assert_reviewable(episode)
    observed = _mapping(bundle)
    expected = compile_underwriting_projections(value)
    findings: list[str] = []
    if observed != expected:
        findings.append("projection_bundle_not_exact_deterministic_derivation")
    expected_identity = {
        "episode_id": value["episode_id"],
        "company_id": value["company_id"],
        "cutoff_at": value["cutoff_at"],
        "underwriting_thesis_id": value["underwriting_thesis"]["thesis_id"],
    }
    for name, item in observed.items():
        projection = _mapping(item)
        for field, expected_value in expected_identity.items():
            if projection.get(field) != expected_value:
                findings.append(name + "." + field + "_mismatch")
        findings.extend(name + ".price_boundary:" + path for path in _forbidden_paths(projection))
    return _findings(findings)


def validate_golden_report_reader_brief(brief: Any) -> dict[str, Any]:
    """Validate the deliberately small, control-plane-free writer payload."""
    value = _mapping(brief)
    findings: list[str] = []
    expected_fields = {
        "company_name",
        "central_judgment",
        "sections",
        "component_judgments",
        "reversal_observations",
        "deterministic_conclusions",
        "accepted_conclusions",
    }
    if set(value) != expected_fields:
        findings.append("reader_brief_fields_invalid")
    if not _text(value.get("company_name")):
        findings.append("reader_brief.company_name_missing")
    if not _text(value.get("central_judgment")):
        findings.append("reader_brief.central_judgment_missing")

    sections = _items(value.get("sections"))
    if not sections:
        findings.append("reader_brief.sections_missing")
    for index, item in enumerate(sections):
        section = _mapping(item)
        if set(section) != {"heading", "paragraphs"}:
            findings.append(f"reader_brief.sections[{index}].fields_invalid")
        if not _text(section.get("heading")):
            findings.append(f"reader_brief.sections[{index}].heading_missing")
        paragraphs = _items(section.get("paragraphs"))
        if not paragraphs or any(not _text(paragraph) for paragraph in paragraphs):
            findings.append(f"reader_brief.sections[{index}].paragraphs_invalid")

    for field in (
        "component_judgments",
        "reversal_observations",
        "deterministic_conclusions",
        "accepted_conclusions",
    ):
        items = value.get(field)
        if not isinstance(items, list):
            findings.append("reader_brief." + field + "_invalid")
        elif field not in {"deterministic_conclusions", "accepted_conclusions"} and any(
            not _text(item) for item in items
        ):
            findings.append("reader_brief." + field + "_invalid")
    for index, raw in enumerate(_items(value.get("deterministic_conclusions"))):
        if _text(raw):
            continue
        item = _mapping(raw)
        if set(item) != {"target_chapter", "sentence"}:
            findings.append(
                f"reader_brief.deterministic_conclusions[{index}].fields_invalid"
            )
            continue
        target_chapter = item.get("target_chapter")
        if (
            not isinstance(target_chapter, int)
            or isinstance(target_chapter, bool)
            or target_chapter < 1
        ):
            findings.append(
                f"reader_brief.deterministic_conclusions[{index}].target_chapter_invalid"
            )
        if not _text(item.get("sentence")):
            findings.append(
                f"reader_brief.deterministic_conclusions[{index}].sentence_invalid"
            )
    for index, raw in enumerate(_items(value.get("accepted_conclusions"))):
        item = _mapping(raw)
        required = {"statement", "basis", "investor_consequence", "source_refs"}
        if set(item) != required:
            findings.append(f"reader_brief.accepted_conclusions[{index}].fields_invalid")
            continue
        if any(not _text(item.get(field)) for field in required - {"source_refs"}):
            findings.append(f"reader_brief.accepted_conclusions[{index}].text_invalid")
        source_refs = _items(item.get("source_refs"))
        if not source_refs or any(not _text(ref) for ref in source_refs) or len(set(source_refs)) != len(source_refs):
            findings.append(f"reader_brief.accepted_conclusions[{index}].source_refs_invalid")

    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    findings.extend(reader_boundary_findings(serialized))
    return {
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def compile_golden_report_reader_brief(
    episode: Any,
    deterministic_results: Any = None,
    *,
    accepted_conclusions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile the only Episode payload intended for a reader writer.

    The structured Episode and its projections retain IDs, authority and
    machine treatments for deterministic consumers.  This compiler copies
    only accepted economic conclusions.  A validated value-bridge result is
    reduced to the reader-safe surface of each compiler-owned slot: target
    chapter and final sentence.  Raw numeric claims, display machinery, model
    identities, validations and review findings are never copied into the
    brief.  The older accepted ``reader_conclusions`` contract remains
    supported for deterministic producers that have not migrated to slots.
    """
    value = _assert_reviewable(episode)
    thesis = _mapping(value["underwriting_thesis"])
    component_decision_summary = (
        derive_component_decision_summary(value.get("component_decisions"))
        if _items(value.get("component_decisions"))
        else {}
    )
    authoritative_treatments = _authoritative_thesis_treatments(
        thesis, component_decision_summary
    )
    situation_model = _mapping(value["situation_model"])
    industry_future = _industry_future_thesis(value)
    deterministic_conclusions: list[str] = []
    if deterministic_results is not None:
        results = _mapping(deterministic_results)
        if results.get("schema_version") == "valuation-value-bridges.v1":
            try:
                from scripts.valuation_value_bridges import validate_valuation_value_bridges
            except ModuleNotFoundError:
                from valuation_value_bridges import validate_valuation_value_bridges
            deterministic_validation = validate_valuation_value_bridges(results)
            if deterministic_validation.get("state") != "VALID":
                raise ValueError(
                    "deterministic_value_bridges_invalid:"
                    + ",".join(deterministic_validation.get("findings") or [])
                )
            slots = results.get("reader_slots")
            if not isinstance(slots, list):
                raise ValueError("deterministic_reader_slots_invalid")
            safe_slots: list[dict[str, Any]] = []
            for index, raw_slot in enumerate(slots):
                slot = _mapping(raw_slot)
                target_chapter = slot.get("target_chapter")
                if (
                    not isinstance(target_chapter, int)
                    or isinstance(target_chapter, bool)
                    or target_chapter < 1
                    or not _text(slot.get("sentence"))
                ):
                    raise ValueError(f"deterministic_reader_slots[{index}]_invalid")
                safe_slots.append(
                    {
                        "target_chapter": target_chapter,
                        "sentence": slot["sentence"],
                    }
                )
            deterministic_conclusions = safe_slots
        else:
            conclusions = results.get("reader_conclusions")
            if results.get("accepted") is not True:
                raise ValueError("deterministic_results_not_accepted")
            if not isinstance(conclusions, list) or any(not _text(item) for item in conclusions):
                raise ValueError("deterministic_reader_conclusions_invalid")
            deterministic_conclusions = list(conclusions)

    clean_conclusions: list[dict[str, Any]] = []
    for index, raw in enumerate(accepted_conclusions or []):
        item = _mapping(raw)
        required = ("statement", "basis", "investor_consequence", "source_refs")
        if set(item) != set(required):
            raise ValueError(f"accepted_conclusions[{index}]_fields_invalid")
        if any(not _text(item.get(field)) for field in required[:-1]):
            raise ValueError(f"accepted_conclusions[{index}]_text_invalid")
        source_refs = _items(item.get("source_refs"))
        if not source_refs or any(not _text(ref) for ref in source_refs) or len(set(source_refs)) != len(source_refs):
            raise ValueError(f"accepted_conclusions[{index}]_source_refs_invalid")
        clean_conclusions.append({field: deepcopy(item[field]) for field in required})

    decisions_by_component = {
        item["component_id"]: item
        for item in _items(value.get("component_decisions"))
        if _text(_mapping(item).get("component_id"))
    }
    component_judgments: list[str] = []
    for item in value["component_treatments"]:
        judgment = (
            f"{item['reason']} 因此，{item['investment_consequence']} "
            f"需要重估这一处理的条件是：{item['promotion_or_resolution_condition']}"
        )
        decision = decisions_by_component.get(item["component_id"])
        if decision:
            label = lambda field: _COMPONENT_DECISION_READER_LABELS.get(
                str(decision[field]), str(decision[field])
            )
            judgment += (
                " 该组件的权威经济去向为："
                f"正常盈利{label('normal_earnings_use')}；"
                f"普通股现金{label('owner_cash_use')}；"
                f"{label('financing_pressure_effect')}；"
                f"永久损失{label('permanent_loss_use')}；"
                f"估值{label('valuation_use')}。"
                f"晋级检验：{decision['promotion_test']} "
                f"失效检验：{decision['invalidation_test']}"
            )
        component_judgments.append(judgment)
    brief = {
        "company_name": value["company_name"],
        "central_judgment": thesis["central_path"],
        "sections": [
            {
                "heading": "行业未来与公司传导",
                "paragraphs": [
                    f"观察时域：{industry_future['horizon']}",
                    f"最可能的行业路径：{industry_future['most_likely_regime']}",
                    f"利润池传导：{industry_future['profit_pool_transmission']}",
                    f"公司暴露：{industry_future['company_exposure']}",
                    f"适应能力：{industry_future['adaptation']}",
                    f"正常经济与普通股现金：{industry_future['normal_economics']}",
                    f"永久损失路径：{industry_future['permanent_loss']}",
                    f"价值处理：{industry_future['valuation_treatment']}",
                    f"最强竞争解释：{industry_future['strongest_rival']}",
                ],
            },
            {
                "heading": "行业处境、公司位置与适应",
                "paragraphs": [
                    situation_model["summary"],
                    value["business_position"],
                    value["adaptation_case"],
                ],
            },
            {
                "heading": "生存、正常盈利与普通股现金",
                "paragraphs": [
                    value["survival_case"],
                    value["normalization_case"],
                    authoritative_treatments["normal_earnings_treatment"],
                    authoritative_treatments["owner_cash_treatment"],
                ],
            },
            {
                "heading": "永久损失与最强反方",
                "paragraphs": [
                    (
                        authoritative_treatments["permanent_loss_treatment"]
                        if component_decision_summary
                        else value["permanent_loss_map"]
                    ),
                    thesis["strongest_rival"],
                ],
            },
            {
                "heading": "价值路线与当前处理",
                "paragraphs": [
                    value["value_route"]["route_reasoning"],
                    thesis["value_route_treatment"],
                ],
            },
        ],
        "component_judgments": component_judgments,
        "reversal_observations": deepcopy(value["reversal_observations"]),
        "deterministic_conclusions": deterministic_conclusions,
        "accepted_conclusions": clean_conclusions,
    }
    validation = validate_golden_report_reader_brief(brief)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("golden_report_reader_brief_invalid:" + ",".join(validation["findings"]))
    return brief


def render_underwriting_readout(
    episode: Any,
    deterministic_results: Any = None,
    *,
    accepted_conclusions: list[dict[str, Any]] | None = None,
) -> str:
    """Render the same underwriting thesis in investor order without gate prose."""
    brief = compile_golden_report_reader_brief(
        episode,
        deterministic_results,
        accepted_conclusions=accepted_conclusions,
    )
    sections = "\n\n".join(
        f"## {section['heading']}\n\n" + "\n\n".join(section["paragraphs"])
        for section in brief["sections"]
    )
    components = "\n".join(f"- {item}" for item in brief["component_judgments"])
    reversals = "\n".join(f"- {item}" for item in brief["reversal_observations"])
    conclusions = "\n".join(
        f"- {item['statement']} {item['investor_consequence']}"
        for item in brief["accepted_conclusions"]
    )
    conclusions_block = (
        "## 已接纳的估值与投资结论\n\n" + conclusions
        if conclusions else ""
    )
    deterministic = "\n".join(
        f"- {item['sentence'] if isinstance(item, dict) else item}"
        for item in brief["deterministic_conclusions"]
    )
    deterministic_block = (
        "## 模型确定的价值结论\n\n" + deterministic
        if deterministic else ""
    )
    return f"""# {brief['company_name']}：企业承保读本

{brief['central_judgment']}

{sections}

## 各项判断的投资含义

{components}

{deterministic_block}

{conclusions_block}

## 会改变判断的事实

{reversals}
"""
