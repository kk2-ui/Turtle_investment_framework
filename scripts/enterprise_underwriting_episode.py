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
import math
from pathlib import Path
from typing import Any

from scripts.reader_coverage import reader_boundary_findings


EPISODE_SCHEMA = "enterprise-underwriting-episode.v2"
THESIS_PROJECTION_SCHEMA = "enterprise-underwriting-thesis-projection.v1"
CJO_PROJECTION_SCHEMA = "enterprise-underwriting-cjo-candidate-projection.v2"
VALUATION_REQUEST_SCHEMA = "enterprise-underwriting-valuation-route-request.v2"
REPORT_HANDOFF_SCHEMA = "enterprise-underwriting-golden-report-handoff.v2"
COMPONENT_DECISION_SUMMARY_SCHEMA = "enterprise-underwriting-component-decision-summary.v1"
ECONOMIC_DERIVATION_SCHEMA = "enterprise-underwriting-economic-derivation.v1"
ECONOMIC_DERIVATION_SUMMARY_SCHEMA = (
    "enterprise-underwriting-economic-derivation-summary.v1"
)

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
_DERIVATION_FORBIDDEN_KEYS = _THESIS_FORBIDDEN_KEYS | {
    "value_per_share",
    "return_pct",
    "action",
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


def _forbidden_paths(
    value: Any,
    path: str = "$",
    *,
    forbidden_keys: set[str] | None = None,
) -> list[str]:
    findings: list[str] = []
    forbidden = forbidden_keys or _THESIS_FORBIDDEN_KEYS
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in forbidden:
                findings.append(child)
            else:
                findings.extend(
                    _forbidden_paths(
                        item, child, forbidden_keys=forbidden,
                    )
                )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(
                _forbidden_paths(
                    item, f"{path}[{index}]", forbidden_keys=forbidden,
                )
            )
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


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _signed_derivation_range(row: dict[str, Any]) -> tuple[float, float] | None:
    quantification = _mapping(row.get("quantification"))
    if quantification.get("status") != "BOUNDED":
        return None
    low = _finite_number(quantification.get("range_low"))
    high = _finite_number(quantification.get("range_high"))
    if low is None or high is None or low < 0 or low > high:
        return None
    if row.get("direction") == "ADD":
        return low, high
    if row.get("direction") == "SUBTRACT":
        return -high, -low
    return None


def _summarize_derivation_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    unknown_ids = [
        str(row.get("row_id") or "")
        for row in rows
        if _mapping(row.get("quantification")).get("status") != "BOUNDED"
        or _signed_derivation_range(row) is None
    ]
    if unknown_ids:
        return {"status": "UNKNOWN", "unknown_row_ids": unknown_ids}
    ranges = [_signed_derivation_range(row) for row in rows]
    bounded = [item for item in ranges if item is not None]
    return {
        "status": "BOUNDED",
        "range_low": sum(item[0] for item in bounded),
        "range_high": sum(item[1] for item in bounded),
    }


def _reversal_index(reference: Any) -> int | None:
    prefix = "#/reversal_observations/"
    text = str(reference or "")
    if not text.startswith(prefix):
        return None
    try:
        index = int(text[len(prefix):])
    except ValueError:
        return None
    return index if index >= 0 else None


def _valuation_route_roles(episode: dict[str, Any]) -> dict[str, set[str]]:
    route = _mapping(episode.get("value_route"))
    model_roles = _mapping(route.get("valuation_model_roles"))
    groups = {
        "PRIMARY": list(dict.fromkeys(
            _items(route.get("primary_routes")) + _items(model_roles.get("primary"))
        )),
        "CORROBORATIVE": _items(model_roles.get("corroborative")),
        "STRESS": _items(model_roles.get("stress")),
        "EXCLUDED": _items(route.get("excluded_routes")),
    }
    roles: dict[str, set[str]] = {}
    for role, route_ids in groups.items():
        for route_id in route_ids:
            if _text(route_id):
                roles.setdefault(str(route_id), set()).add(role)
    return roles


def _route_role_for_use(use: str) -> str:
    if use in {"PRIMARY_INPUT", "CONDITIONAL_PRIMARY_INPUT"}:
        return "PRIMARY"
    if use == "CORROBORATIVE_INPUT":
        return "CORROBORATIVE"
    if use == "STRESS_ONLY":
        return "STRESS"
    if use in {"SCENARIO_ONLY", "EXCLUDED", "UNRESOLVED", "NOT_APPLICABLE"}:
        return "EXCLUDED"
    return "UNRESOLVED"


def derive_economic_derivation_summary(episode: Any) -> dict[str, Any]:
    """Join price-free derivation operands to the existing component authority.

    The Agent never authors BASE/CONDITIONAL/EXCLUDED on a bridge row.  Those
    uses are copied from ``component_decisions`` here, and numeric UNKNOWNs
    remain UNKNOWN rather than becoming zero.  This object is a read model, not
    a second underwriting or valuation decision.
    """

    value = _mapping(episode)
    derivation = _mapping(value.get("economic_derivation"))
    bridge = _mapping(derivation.get("normal_earnings_bridge"))
    decisions = {
        str(_mapping(item).get("component_id")): _mapping(item)
        for item in _items(value.get("component_decisions"))
        if _text(_mapping(item).get("component_id"))
    }
    enriched_rows: list[dict[str, Any]] = []
    for raw in _items(bridge.get("rows")):
        row = deepcopy(_mapping(raw))
        component_id = str(row.get("component_id") or "")
        row["normal_earnings_use"] = str(
            decisions.get(component_id, {}).get("normal_earnings_use")
            or "UNRESOLVED"
        )
        signed = _signed_derivation_range(row)
        row["signed_range"] = (
            {"range_low": signed[0], "range_high": signed[1]}
            if signed is not None else None
        )
        enriched_rows.append(row)

    rows_by_use = {
        use: [row for row in enriched_rows if row["normal_earnings_use"] == use]
        for use in EARNINGS_AND_CASH_USE_ORDER
    }
    totals_by_use = {
        use: _summarize_derivation_rows(rows_by_use[use])
        for use in EARNINGS_AND_CASH_USE_ORDER
    }
    base_rows = rows_by_use["BASE_RANGE"]
    conditional_only_rows = rows_by_use["CONDITIONAL_RANGE"]
    conditional_rows = base_rows + conditional_only_rows
    reference_rows = [
        row for row in enriched_rows if row.get("row_role") == "REFERENCE_EARNINGS"
    ]
    reference_use = (
        str(reference_rows[0].get("normal_earnings_use"))
        if len(reference_rows) == 1 else "UNRESOLVED"
    )
    if base_rows:
        base_range = (
            _summarize_derivation_rows(base_rows)
            if reference_use == "BASE_RANGE"
            else {
                "status": "UNKNOWN",
                "reason": "REFERENCE_EARNINGS_NOT_AUTHORIZED_FOR_BASE_RANGE",
            }
        )
        conditional_range = (
            _summarize_derivation_rows(conditional_rows)
            if reference_use == "BASE_RANGE"
            else {
                "status": "UNKNOWN",
                "reason": "REFERENCE_EARNINGS_NOT_AUTHORIZED_FOR_BASE_RANGE",
            }
        )
    elif conditional_only_rows:
        base_range = None
        conditional_range = (
            _summarize_derivation_rows(conditional_only_rows)
            if reference_use == "CONDITIONAL_RANGE"
            else {
                "status": "UNKNOWN",
                "reason": "REFERENCE_EARNINGS_NOT_AUTHORIZED_FOR_CONDITIONAL_RANGE",
            }
        )
    else:
        base_range = None
        conditional_range = None

    reversals = _items(value.get("reversal_observations"))
    route_roles = _valuation_route_roles(value)
    sensitivity_summaries: list[dict[str, Any]] = []
    for raw in _items(derivation.get("driver_sensitivity_specs")):
        spec = _mapping(raw)
        component_ids = [str(item) for item in _items(spec.get("component_ids"))]
        resolved_reversals: list[str] = []
        for reference in _items(spec.get("reversal_observation_refs")):
            index = _reversal_index(reference)
            if index is not None and index < len(reversals) and _text(reversals[index]):
                resolved_reversals.append(str(reversals[index]))
        transmission = _mapping(spec.get("transmission"))
        route_attributions: list[dict[str, Any]] = []
        for route_id in _items(transmission.get("valuation_route_ids")):
            component_uses: dict[str, str] = {}
            for component_id in component_ids:
                bindings = {
                    str(_mapping(item).get("route_id")): str(
                        _mapping(item).get("use") or "UNRESOLVED"
                    )
                    for item in _items(decisions.get(component_id, {}).get(
                        "valuation_route_bindings"
                    ))
                    if _text(_mapping(item).get("route_id"))
                }
                component_uses[component_id] = bindings.get(
                    str(route_id), "UNRESOLVED"
                )
            expected_roles = {
                _route_role_for_use(use) for use in component_uses.values()
            }
            role = (
                next(iter(expected_roles))
                if len(expected_roles) == 1
                else "UNRESOLVED"
            )
            if role not in route_roles.get(str(route_id), set()):
                role = "UNRESOLVED"
            route_attributions.append({
                "route_id": route_id,
                "route_role": role,
                "component_valuation_uses": component_uses,
            })
        sensitivity_summaries.append({
            "sensitivity_id": spec.get("sensitivity_id"),
            "component_ids": component_ids,
            "normal_earnings_uses": {
                component_id: str(
                    decisions.get(component_id, {}).get("normal_earnings_use")
                    or "UNRESOLVED"
                )
                for component_id in component_ids
            },
            "owner_cash_uses": {
                component_id: str(
                    decisions.get(component_id, {}).get("owner_cash_use")
                    or "UNRESOLVED"
                )
                for component_id in component_ids
            },
            "metric": spec.get("metric"),
            "unit": spec.get("unit"),
            "horizon": spec.get("horizon"),
            "input_cases": deepcopy(spec.get("input_cases")),
            "transmission": deepcopy(transmission),
            "valuation_route_attributions": route_attributions,
            "reversal_observations": resolved_reversals,
        })
    return {
        "schema_version": ECONOMIC_DERIVATION_SUMMARY_SCHEMA,
        "normal_earnings_bridge": {
            "basis": deepcopy(bridge.get("basis")),
            "rows": enriched_rows,
            "totals_by_use": totals_by_use,
            "base_range": base_range,
            "conditional_range": conditional_range,
        },
        "driver_sensitivities": sensitivity_summaries,
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


def _validate_sensitivity_case(
    value: Any,
    *,
    path: str,
    evidence_ids: set[str],
    require_range: bool = False,
) -> list[str]:
    item = _mapping(value)
    findings: list[str] = []
    if set(item) != {"value_or_range", "basis", "evidence_ids"}:
        findings.append(path + ".fields_invalid")
    if not _text(item.get("basis")):
        findings.append(path + ".basis_missing")
    refs = _items(item.get("evidence_ids"))
    if (
        not refs or len(refs) != len(set(refs))
        or any(ref not in evidence_ids for ref in refs)
    ):
        findings.append(path + ".evidence_ids_invalid")
    operand = _mapping(item.get("value_or_range"))
    if set(operand) == {"value"} and not require_range:
        if _finite_number(operand.get("value")) is None:
            findings.append(path + ".value_invalid")
    elif set(operand) == {"range_low", "range_high"}:
        low = _finite_number(operand.get("range_low"))
        high = _finite_number(operand.get("range_high"))
        if low is None or high is None or low > high:
            findings.append(path + ".range_invalid")
    else:
        findings.append(path + ".value_or_range_invalid")
    return findings


def _validate_sensitivity_delta(
    value: Any,
    *,
    path: str,
    transmission_status: Any,
    sensitivity_component_ids: list[str],
    responsibility_boundary: Any,
    driver_metric: Any,
    driver_unit: Any,
    horizon: Any,
    driver_case_evidence_ids: set[str],
    evidence_ids: set[str],
    evidence_trace_by_id: dict[str, dict[str, Any]],
    axis: str,
    require_magnitude_evidence: bool,
) -> list[str]:
    delta = _mapping(value)
    findings: list[str] = []
    status = delta.get("status")
    if status == "BOUNDED":
        allowed_fields = {
            "status", "range_low", "range_high", "unit", "magnitude_evidence",
        }
        if (
            not {"status", "range_low", "range_high", "unit"} <= set(delta)
            or set(delta) - allowed_fields
        ):
            findings.append(path + ".fields_invalid")
        low = _finite_number(delta.get("range_low"))
        high = _finite_number(delta.get("range_high"))
        if low is None or high is None or low > 0 or high < 0 or low > high:
            findings.append(path + ".range_must_be_signed_and_include_zero")
        if not _text(delta.get("unit")):
            findings.append(path + ".unit_missing")
        if transmission_status == "UNKNOWN":
            findings.append(path + ".bounded_conflicts_with_unknown_transmission")
        if transmission_status == "PRESERVED" and (low != 0 or high != 0):
            findings.append(path + ".preserved_requires_zero_delta")
        if (
            (require_magnitude_evidence and transmission_status != "PRESERVED")
            or "magnitude_evidence" in delta
        ):
            findings.extend(_validate_sensitivity_delta_magnitude_evidence(
                delta.get("magnitude_evidence"),
                path=path + ".magnitude_evidence",
                sensitivity_component_ids=sensitivity_component_ids,
                responsibility_boundary=responsibility_boundary,
                driver_metric=driver_metric,
                driver_unit=driver_unit,
                horizon=horizon,
                delta_unit=delta.get("unit"),
                axis=axis,
                driver_case_evidence_ids=driver_case_evidence_ids,
                evidence_ids=evidence_ids,
                evidence_trace_by_id=evidence_trace_by_id,
                require_trace_metadata=require_magnitude_evidence,
            ))
    elif status == "UNKNOWN":
        if set(delta) != {"status", "reason", "conservative_treatment"}:
            findings.append(path + ".fields_invalid")
        for field in ("reason", "conservative_treatment"):
            if not _text(delta.get(field)):
                findings.append(path + "." + field + "_missing")
        if transmission_status != "UNKNOWN":
            findings.append(path + ".unknown_requires_unknown_transmission")
    else:
        findings.append(path + ".status_invalid")
    return findings


def _validate_sensitivity_delta_magnitude_evidence(
    value: Any,
    *,
    path: str,
    sensitivity_component_ids: list[str],
    responsibility_boundary: Any,
    driver_metric: Any,
    driver_unit: Any,
    horizon: Any,
    delta_unit: Any,
    axis: str,
    driver_case_evidence_ids: set[str],
    evidence_ids: set[str],
    evidence_trace_by_id: dict[str, dict[str, Any]],
    require_trace_metadata: bool,
) -> list[str]:
    """Require a calculation-bound magnitude source for a non-preserved delta.

    The qualitative driver case and an already-authorized component answer different
    questions from the size of an earnings or owner-cash effect.  A bounded output
    therefore needs its own structured calculation binding, kept in the same
    component, responsibility boundary, driver metric/unit, and horizon as the
    sensitivity it supports.
    """

    magnitude = _mapping(value)
    findings: list[str] = []
    required_fields = {
        "evidence_ids", "component_ids", "responsibility_boundary",
        "driver_metric", "driver_unit", "horizon", "affected_axis",
        "delta_unit", "calculation_binding",
    }
    if not magnitude:
        return [path + ".required_for_bounded_delta"]
    if set(magnitude) != required_fields:
        findings.append(path + ".fields_invalid")

    magnitude_refs = _items(magnitude.get("evidence_ids"))
    if (
        not magnitude_refs
        or len(magnitude_refs) != len(set(magnitude_refs))
        or any(ref not in evidence_ids for ref in magnitude_refs)
    ):
        findings.append(path + ".evidence_ids_invalid")
    elif set(magnitude_refs) & driver_case_evidence_ids:
        findings.append(path + ".cannot_reuse_driver_case_evidence")

    magnitude_components = _items(magnitude.get("component_ids"))
    if (
        not magnitude_components
        or len(magnitude_components) != len(set(magnitude_components))
        or set(magnitude_components) != set(sensitivity_component_ids)
    ):
        findings.append(path + ".component_ids_must_match_sensitivity")
    if magnitude.get("responsibility_boundary") != responsibility_boundary:
        findings.append(path + ".responsibility_boundary_incompatible")
    if magnitude.get("driver_metric") != driver_metric:
        findings.append(path + ".driver_metric_incompatible")
    if magnitude.get("driver_unit") != driver_unit:
        findings.append(path + ".driver_unit_incompatible")
    if magnitude.get("horizon") != horizon:
        findings.append(path + ".horizon_incompatible")
    if magnitude.get("affected_axis") != axis:
        findings.append(path + ".affected_axis_incompatible")
    if magnitude.get("delta_unit") != delta_unit:
        findings.append(path + ".delta_unit_incompatible")

    calculation = _mapping(magnitude.get("calculation_binding"))
    calculation_fields = {"calculation_id", "expression", "input_evidence_ids"}
    if set(calculation) != calculation_fields:
        findings.append(path + ".calculation_binding.fields_invalid")
    if not _text(calculation.get("calculation_id")):
        findings.append(path + ".calculation_binding.calculation_id_missing")
    if not _text(calculation.get("expression")):
        findings.append(path + ".calculation_binding.expression_missing")
    calculation_refs = _items(calculation.get("input_evidence_ids"))
    if (
        not calculation_refs
        or len(calculation_refs) != len(set(calculation_refs))
        or any(ref not in evidence_ids for ref in calculation_refs)
    ):
        findings.append(path + ".calculation_binding.input_evidence_ids_invalid")
    elif set(calculation_refs) != set(magnitude_refs):
        findings.append(path + ".calculation_binding.input_evidence_ids_must_match")
    if require_trace_metadata:
        findings.extend(_validate_sensitivity_magnitude_trace_metadata(
            magnitude_refs,
            path=path + ".trace_metadata",
            evidence_trace_by_id=evidence_trace_by_id,
            sensitivity_component_ids=sensitivity_component_ids,
            responsibility_boundary=responsibility_boundary,
            driver_metric=driver_metric,
            driver_unit=driver_unit,
            horizon=horizon,
            axis=axis,
            delta_unit=delta_unit,
            calculation_refs=calculation_refs,
        ))
    return findings


def _validate_sensitivity_magnitude_trace_metadata(
    evidence_refs: list[Any],
    *,
    path: str,
    evidence_trace_by_id: dict[str, dict[str, Any]],
    sensitivity_component_ids: list[str],
    responsibility_boundary: Any,
    driver_metric: Any,
    driver_unit: Any,
    horizon: Any,
    axis: str,
    delta_unit: Any,
    calculation_refs: list[Any],
) -> list[str]:
    """Bind v2 sensitivity magnitude to canonical evidence-trace metadata.

    ``magnitude_evidence`` is a claim about which facts support a calculation;
    its repeated labels are not that fact.  Each cited trace entry therefore has
    to carry the component, responsibility, driver, horizon, output axis/unit,
    and input identities used by the calculation itself.
    """

    findings: list[str] = []
    required_fields = {
        "component_ids", "responsibility_boundary", "driver_metric",
        "driver_unit", "horizon", "affected_axes", "delta_unit",
        "calculation_inputs",
    }
    for evidence_id in evidence_refs:
        trace = evidence_trace_by_id.get(str(evidence_id))
        metadata = _mapping(
            trace.get("sensitivity_magnitude_observation") if trace else None
        )
        item_path = path + f"[{evidence_id}]"
        if not metadata:
            findings.append(item_path + ".required")
            continue
        if set(metadata) != required_fields:
            findings.append(item_path + ".fields_invalid")
        component_ids = _items(metadata.get("component_ids"))
        if (
            not component_ids
            or len(component_ids) != len(set(component_ids))
            or set(component_ids) != set(sensitivity_component_ids)
        ):
            findings.append(item_path + ".component_ids_incompatible")
        if metadata.get("responsibility_boundary") != responsibility_boundary:
            findings.append(item_path + ".responsibility_boundary_incompatible")
        if metadata.get("driver_metric") != driver_metric:
            findings.append(item_path + ".driver_metric_incompatible")
        if metadata.get("driver_unit") != driver_unit:
            findings.append(item_path + ".driver_unit_incompatible")
        if metadata.get("horizon") != horizon:
            findings.append(item_path + ".horizon_incompatible")
        affected_axes = _items(metadata.get("affected_axes"))
        if (
            not affected_axes
            or len(affected_axes) != len(set(affected_axes))
            or axis not in affected_axes
            or any(item not in {"normal_earnings", "owner_cash"} for item in affected_axes)
        ):
            findings.append(item_path + ".affected_axes_incompatible")
        if metadata.get("delta_unit") != delta_unit:
            findings.append(item_path + ".delta_unit_incompatible")
        trace_inputs = _items(metadata.get("calculation_inputs"))
        if (
            not trace_inputs
            or len(trace_inputs) != len(set(trace_inputs))
            or set(trace_inputs) != set(calculation_refs)
        ):
            findings.append(item_path + ".calculation_inputs_incompatible")
    return findings


def _economic_derivation_findings(
    episode: dict[str, Any],
    derivation: Any,
    stored_summary: Any,
    *,
    require_bounded_sensitivity_magnitude_evidence: bool = False,
) -> list[str]:
    if derivation is None:
        return (
            ["economic_derivation_summary.not_allowed_without_economic_derivation"]
            if stored_summary is not None else []
        )
    value = _mapping(derivation)
    findings: list[str] = []
    if set(value) != {
        "schema_version", "normal_earnings_bridge", "driver_sensitivity_specs",
    }:
        findings.append("economic_derivation.fields_invalid")
    if value.get("schema_version") != ECONOMIC_DERIVATION_SCHEMA:
        findings.append("economic_derivation.schema_version_invalid")
    if not _items(episode.get("component_decisions")):
        findings.append("economic_derivation.component_decisions_required")

    evidence_ids = {
        str(_mapping(item).get("evidence_id"))
        for item in _items(episode.get("evidence_trace"))
        if _text(_mapping(item).get("evidence_id"))
    }
    evidence_trace_by_id = {
        str(_mapping(item).get("evidence_id")): _mapping(item)
        for item in _items(episode.get("evidence_trace"))
        if _text(_mapping(item).get("evidence_id"))
    }
    decisions = {
        str(_mapping(item).get("component_id")): _mapping(item)
        for item in _items(episode.get("component_decisions"))
        if _text(_mapping(item).get("component_id"))
    }
    bridge = _mapping(value.get("normal_earnings_bridge"))
    if set(bridge) != {"basis", "rows"}:
        findings.append("economic_derivation.normal_earnings_bridge.fields_invalid")
    basis = _mapping(bridge.get("basis"))
    basis_fields = {
        "metric", "currency", "unit", "tax_basis", "earnings_claim_scope",
        "operating_perimeter", "as_of",
    }
    if set(basis) != basis_fields:
        findings.append("economic_derivation.normal_earnings_bridge.basis.fields_invalid")
    for field in basis_fields - {"tax_basis", "earnings_claim_scope"}:
        if not _text(basis.get(field)):
            findings.append(
                "economic_derivation.normal_earnings_bridge.basis."
                + field + "_missing"
            )
    if basis.get("tax_basis") not in {"PRETAX", "AFTER_TAX"}:
        findings.append("economic_derivation.normal_earnings_bridge.basis.tax_basis_invalid")
    if basis.get("earnings_claim_scope") not in {
        "ENTERPRISE_OPERATING", "ORDINARY_COMMON_EQUITY",
    }:
        findings.append(
            "economic_derivation.normal_earnings_bridge.basis.earnings_claim_scope_invalid"
        )

    rows = bridge.get("rows")
    if not isinstance(rows, list) or not rows:
        findings.append("economic_derivation.normal_earnings_bridge.rows_missing")
        rows = []
    row_ids: set[str] = set()
    component_roles: set[tuple[str, str]] = set()
    reference_earnings_count = 0
    reference_component_ids: list[str] = []
    covered_components: set[str] = set()
    row_fields = {
        "row_id", "component_id", "row_role", "direction", "quantification",
        "evidence_ids", "economic_reason",
    }
    for index, raw in enumerate(rows):
        path = f"economic_derivation.normal_earnings_bridge.rows[{index}]"
        row = _mapping(raw)
        if set(row) != row_fields:
            findings.append(path + ".fields_invalid")
        row_id = row.get("row_id")
        if not _text(row_id) or row_id in row_ids:
            findings.append(path + ".row_id_missing_or_duplicate")
        else:
            row_ids.add(str(row_id))
        component_id = str(row.get("component_id") or "")
        decision = decisions.get(component_id)
        if decision is None:
            findings.append(path + ".component_id_unknown")
        elif decision.get("normal_earnings_use") == "NOT_APPLICABLE":
            findings.append(path + ".component_not_applicable_to_normal_earnings")
        else:
            covered_components.add(component_id)
        if row.get("row_role") not in {
            "REFERENCE_EARNINGS", "NORMALIZATION_ADJUSTMENT",
        }:
            findings.append(path + ".row_role_invalid")
        else:
            row_role = str(row["row_role"])
            if row_role == "REFERENCE_EARNINGS":
                reference_earnings_count += 1
                reference_component_ids.append(component_id)
            component_role = (component_id, row_role)
            if component_role in component_roles:
                findings.append(path + ".component_role_duplicate")
            else:
                component_roles.add(component_role)
        if row.get("direction") not in {"ADD", "SUBTRACT"}:
            findings.append(path + ".direction_invalid")
        refs = _items(row.get("evidence_ids"))
        if (
            not refs or len(refs) != len(set(refs))
            or any(ref not in evidence_ids for ref in refs)
        ):
            findings.append(path + ".evidence_ids_invalid")
        if not _text(row.get("economic_reason")):
            findings.append(path + ".economic_reason_missing")
        quantification = _mapping(row.get("quantification"))
        status = quantification.get("status")
        if status == "BOUNDED":
            if set(quantification) != {"status", "range_low", "range_high"}:
                findings.append(path + ".quantification.fields_invalid")
            low = _finite_number(quantification.get("range_low"))
            high = _finite_number(quantification.get("range_high"))
            if low is None or high is None or low < 0 or low > high:
                findings.append(path + ".quantification.range_invalid")
        elif status == "UNKNOWN":
            if set(quantification) != {
                "status", "reason", "conservative_treatment",
            }:
                findings.append(path + ".quantification.fields_invalid")
            for field in ("reason", "conservative_treatment"):
                if not _text(quantification.get(field)):
                    findings.append(path + f".quantification.{field}_missing")
        else:
            findings.append(path + ".quantification.status_invalid")

    if reference_earnings_count != 1:
        findings.append(
            "economic_derivation.normal_earnings_bridge."
            "requires_exactly_one_reference_earnings_row"
        )
    reference_use = (
        decisions.get(reference_component_ids[0], {}).get("normal_earnings_use")
        if len(reference_component_ids) == 1 else None
    )
    row_uses = [
        decisions.get(str(_mapping(row).get("component_id")), {}).get(
            "normal_earnings_use"
        )
        for row in rows
    ]
    if "BASE_RANGE" in row_uses and reference_use != "BASE_RANGE":
        findings.append(
            "economic_derivation.normal_earnings_bridge."
            "base_range_requires_base_reference_earnings"
        )
    elif (
        "CONDITIONAL_RANGE" in row_uses
        and reference_use != "CONDITIONAL_RANGE"
    ):
        findings.append(
            "economic_derivation.normal_earnings_bridge."
            "conditional_range_requires_conditional_reference_earnings"
        )

    expected_components = {
        component_id for component_id, decision in decisions.items()
        if decision.get("normal_earnings_use") != "NOT_APPLICABLE"
    }
    if covered_components != expected_components:
        findings.append(
            "economic_derivation.normal_earnings_bridge.must_cover_each_"
            "normal_earnings_component"
        )

    route_roles = _valuation_route_roles(episode)
    reversals = _items(episode.get("reversal_observations"))
    specs = value.get("driver_sensitivity_specs")
    if not isinstance(specs, list) or not specs:
        findings.append("economic_derivation.driver_sensitivity_specs_missing")
        specs = []
    sensitivity_ids: set[str] = set()
    allowed_spec_fields = {
        "sensitivity_id", "component_ids", "responsibility_boundary",
        "driver_binding", "metric", "unit", "horizon", "input_cases",
        "transmission", "reversal_observation_refs",
    }
    required_spec_fields = allowed_spec_fields - {
        "driver_binding", "responsibility_boundary",
    }
    for index, raw in enumerate(specs):
        path = f"economic_derivation.driver_sensitivity_specs[{index}]"
        spec = _mapping(raw)
        if not required_spec_fields <= set(spec) or set(spec) - allowed_spec_fields:
            findings.append(path + ".fields_invalid")
        sensitivity_id = spec.get("sensitivity_id")
        if not _text(sensitivity_id) or sensitivity_id in sensitivity_ids:
            findings.append(path + ".sensitivity_id_missing_or_duplicate")
        else:
            sensitivity_ids.add(str(sensitivity_id))
        component_ids = _items(spec.get("component_ids"))
        if (
            not component_ids or len(component_ids) != len(set(component_ids))
            or any(component_id not in decisions for component_id in component_ids)
        ):
            findings.append(path + ".component_ids_invalid")
        for field in ("metric", "unit", "horizon"):
            if not _text(spec.get(field)):
                findings.append(path + "." + field + "_missing")
        if (
            require_bounded_sensitivity_magnitude_evidence
            and not _text(spec.get("responsibility_boundary"))
        ):
            findings.append(path + ".responsibility_boundary_required_by_interface_v2")
        binding = spec.get("driver_binding")
        if binding is not None:
            binding_value = _mapping(binding)
            if (
                not binding_value
                or set(binding_value) - {
                    "enterprise_variable_id", "financial_driver_id",
                }
                or any(not _text(item) for item in binding_value.values())
            ):
                findings.append(path + ".driver_binding_invalid")

        input_cases = _mapping(spec.get("input_cases"))
        mode = input_cases.get("mode")
        driver_case_evidence_ids: set[str] = set()
        if mode == "LOW_BASE_HIGH":
            if set(input_cases) != {"mode", "low", "base", "high"}:
                findings.append(path + ".input_cases.fields_invalid")
            for role in ("low", "base", "high"):
                driver_case_evidence_ids.update(
                    str(ref) for ref in _items(
                        _mapping(input_cases.get(role)).get("evidence_ids")
                    )
                )
                findings.extend(_validate_sensitivity_case(
                    input_cases.get(role), path=path + ".input_cases." + role,
                    evidence_ids=evidence_ids,
                ))
        elif mode == "BOUNDED_RANGE":
            if set(input_cases) != {"mode", "range"}:
                findings.append(path + ".input_cases.fields_invalid")
            findings.extend(_validate_sensitivity_case(
                input_cases.get("range"), path=path + ".input_cases.range",
                evidence_ids=evidence_ids, require_range=True,
            ))
            driver_case_evidence_ids.update(
                str(ref) for ref in _items(
                    _mapping(input_cases.get("range")).get("evidence_ids")
                )
            )
        else:
            findings.append(path + ".input_cases.mode_invalid")

        transmission = _mapping(spec.get("transmission"))
        if set(transmission) != {
            "normal_earnings", "owner_cash", "valuation_route_ids",
        }:
            findings.append(path + ".transmission.fields_invalid")
        for axis in ("normal_earnings", "owner_cash"):
            treatment = _mapping(transmission.get(axis))
            if set(treatment) != {"status", "basis", "delta"}:
                findings.append(path + f".transmission.{axis}.fields_invalid")
            if treatment.get("status") not in {"DIRECT", "PRESERVED", "UNKNOWN"}:
                findings.append(path + f".transmission.{axis}.status_invalid")
            if not _text(treatment.get("basis")):
                findings.append(path + f".transmission.{axis}.basis_missing")
            findings.extend(_validate_sensitivity_delta(
                treatment.get("delta"),
                path=path + f".transmission.{axis}.delta",
                transmission_status=treatment.get("status"),
                sensitivity_component_ids=[str(item) for item in component_ids],
                responsibility_boundary=spec.get("responsibility_boundary"),
                driver_metric=spec.get("metric"),
                driver_unit=spec.get("unit"),
                horizon=spec.get("horizon"),
                driver_case_evidence_ids=driver_case_evidence_ids,
                evidence_ids=evidence_ids,
                evidence_trace_by_id=evidence_trace_by_id,
                axis=axis,
                require_magnitude_evidence=(
                    require_bounded_sensitivity_magnitude_evidence
                ),
            ))
            authority_field = (
                "normal_earnings_use" if axis == "normal_earnings"
                else "owner_cash_use"
            )
            if treatment.get("status") == "DIRECT" and any(
                decisions.get(str(component_id), {}).get(authority_field)
                not in {"BASE_RANGE", "CONDITIONAL_RANGE"}
                for component_id in component_ids
            ):
                findings.append(
                    path + f".transmission.{axis}.direct_not_authorized_by_component_decisions"
                )
        sensitivity_routes = _items(transmission.get("valuation_route_ids"))
        if (
            not sensitivity_routes or len(sensitivity_routes) != len(set(sensitivity_routes))
            or any(route_id not in route_roles for route_id in sensitivity_routes)
        ):
            findings.append(path + ".transmission.valuation_route_id_unknown")
        for component_id in component_ids:
            bindings = {
                str(_mapping(item).get("route_id")): str(
                    _mapping(item).get("use") or ""
                )
                for item in _items(decisions.get(str(component_id), {}).get(
                    "valuation_route_bindings"
                ))
                if _text(_mapping(item).get("route_id"))
            }
            for route_id in sensitivity_routes:
                if route_id not in bindings:
                    findings.append(path + ".transmission.route_not_bound_to_component")
                    continue
                required_role = _route_role_for_use(bindings[route_id])
                if required_role not in route_roles.get(str(route_id), set()):
                    findings.append(
                        path + ".transmission.route_binding_use_incompatible_with_route_role"
                    )

        reversal_refs = _items(spec.get("reversal_observation_refs"))
        if not reversal_refs or len(reversal_refs) != len(set(reversal_refs)):
            findings.append(path + ".reversal_observation_refs_invalid")
        for reference in reversal_refs:
            reversal_index = _reversal_index(reference)
            if (
                reversal_index is None or reversal_index >= len(reversals)
                or not _text(reversals[reversal_index])
            ):
                findings.append(path + ".reversal_observation_ref_invalid")

    findings.extend(
        "economic_derivation.price_boundary:" + path
        for path in _forbidden_paths(
            value, forbidden_keys=_DERIVATION_FORBIDDEN_KEYS,
        )
    )
    expected_summary = derive_economic_derivation_summary(episode)
    if not isinstance(stored_summary, dict):
        findings.append("economic_derivation_summary.required_when_derivation_present")
    elif stored_summary != expected_summary:
        findings.append(
            "economic_derivation_summary.not_exact_deterministic_derivation"
        )
    return findings


def validate_enterprise_underwriting_episode(
    episode: Any,
    *,
    require_bounded_sensitivity_magnitude_evidence: bool = False,
) -> dict[str, Any]:
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
    findings.extend(
        _economic_derivation_findings(
            value,
            value.get("economic_derivation"),
            value.get("economic_derivation_summary"),
            require_bounded_sensitivity_magnitude_evidence=(
                require_bounded_sensitivity_magnitude_evidence
            ),
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
    if _mapping(value.get("economic_derivation")):
        projection["economic_derivation"] = deepcopy(value["economic_derivation"])
        projection["economic_derivation_summary"] = deepcopy(
            value["economic_derivation_summary"]
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
    findings.extend(
        _economic_derivation_findings(
            value,
            value.get("economic_derivation"),
            value.get("economic_derivation_summary"),
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
    if _mapping(value.get("economic_derivation")):
        valuation_request["economic_derivation"] = deepcopy(
            value["economic_derivation"]
        )
        valuation_request["economic_derivation_summary"] = deepcopy(
            value["economic_derivation_summary"]
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
    if _mapping(value.get("economic_derivation")):
        report_handoff["economic_derivation"] = deepcopy(
            value["economic_derivation"]
        )
        report_handoff["economic_derivation_summary"] = deepcopy(
            value["economic_derivation_summary"]
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


def _reader_number(value: Any) -> str:
    number = _finite_number(value)
    if number is None:
        return "未知"
    return str(int(number)) if number.is_integer() else format(number, "g")


def _reader_value_or_range(value: Any) -> str:
    item = _mapping(value)
    if set(item) == {"value"}:
        return _reader_number(item.get("value"))
    if set(item) == {"range_low", "range_high"}:
        return (
            _reader_number(item.get("range_low"))
            + "–"
            + _reader_number(item.get("range_high"))
        )
    return "未知"


def _reader_sensitivity_delta(value: Any) -> str:
    delta = _mapping(value)
    if delta.get("status") == "BOUNDED":
        return (
            "影响范围 "
            + _reader_number(delta.get("range_low"))
            + "–"
            + _reader_number(delta.get("range_high"))
            + " "
            + str(delta.get("unit") or "同口径单位")
        )
    return (
        f"影响未知：{delta.get('reason')}；保守处理："
        f"{delta.get('conservative_treatment')}"
    )


def _reader_sensitivity_transmission(value: Any) -> str:
    """Render only an evidenced sensitivity transmission as a direct effect.

    An UNKNOWN delta means the causal direction may remain a useful question, but
    its magnitude is not an investor-facing attribution.  In particular, do not
    repeat a free-text basis that calls it "direct" when the structured delta
    declined to quantify it.
    """

    treatment = _mapping(value)
    delta = _mapping(treatment.get("delta"))
    if treatment.get("status") == "UNKNOWN" or delta.get("status") == "UNKNOWN":
        return _reader_sensitivity_delta(delta)
    return (
        f"{treatment.get('basis')}；"
        f"{_reader_sensitivity_delta(delta)}"
    )


def _reader_component_authority(uses: Any) -> str:
    labels = list(dict.fromkeys(
        _COMPONENT_DECISION_READER_LABELS.get(str(use), str(use))
        for use in _mapping(uses).values()
    ))
    return "、".join(labels) if labels else "尚未形成权限"


def _reader_safe_authority_text(value: Any) -> str:
    text = str(value or "")
    for internal, label in _COMPONENT_DECISION_READER_LABELS.items():
        text = text.replace(internal, label)
    return text


def _reader_route_authority(attributions: Any) -> str:
    uses: list[str] = []
    for attribution in _items(attributions):
        uses.extend(
            str(use)
            for use in _mapping(_mapping(attribution).get(
                "component_valuation_uses"
            )).values()
        )
    phrases = {
        "PRIMARY_INPUT": "进入基准价值路线",
        "CONDITIONAL_PRIMARY_INPUT": "只进入条件性价值路线",
        "CORROBORATIVE_INPUT": "只进入价值交叉验证",
        "STRESS_ONLY": "只进入压力价值路线",
        "SCENARIO_ONLY": "只保留情景价值路线，不进入基准价值",
        "EXCLUDED": "相关价值路线被排除",
        "UNRESOLVED": "价值路线影响未决",
        "NOT_APPLICABLE": "不适用价值路线",
    }
    rendered = list(dict.fromkeys(phrases.get(use, "价值路线影响未决") for use in uses))
    return "、".join(rendered) if rendered else "价值路线影响未决"


def _economic_derivation_reader_sections(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Reduce the deterministic derivation to challengeable prose without IDs."""

    summary = _mapping(value.get("economic_derivation_summary"))
    if not summary:
        return []
    bridge = _mapping(summary.get("normal_earnings_bridge"))
    basis = _mapping(bridge.get("basis"))
    unit = str(basis.get("unit") or basis.get("currency") or "同口径单位")
    bridge_paragraphs = [
        (
            f"口径：{basis.get('metric')}；{basis.get('operating_perimeter')}；"
            f"截至 {basis.get('as_of')}；单位 {unit}。"
        )
    ]
    for raw in _items(bridge.get("rows")):
        row = _mapping(raw)
        use = _COMPONENT_DECISION_READER_LABELS.get(
            str(row.get("normal_earnings_use")), str(row.get("normal_earnings_use"))
        )
        quantification = _mapping(row.get("quantification"))
        if row.get("normal_earnings_use") not in {
            "BASE_RANGE", "CONDITIONAL_RANGE"
        }:
            bridge_paragraphs.append(
                f"该组件未获授权进入读者正常盈利数值桥；组件权限：{use}。"
            )
            continue
        if quantification.get("status") == "BOUNDED":
            signed = _mapping(row.get("signed_range"))
            amount = (
                _reader_number(signed.get("range_low"))
                + "–"
                + _reader_number(signed.get("range_high"))
            )
            detail = f"带符号范围 {amount} {unit}"
        else:
            detail = (
                f"数值未知：{quantification.get('reason')}；保守处理："
                f"{quantification.get('conservative_treatment')}"
            )
        bridge_paragraphs.append(
            f"{row.get('economic_reason')}；{detail}；组件权限：{use}。"
        )
    for label, field in (("基准范围", "base_range"), ("含条件项范围", "conditional_range")):
        total = _mapping(bridge.get(field))
        if total.get("status") == "BOUNDED":
            bridge_paragraphs.append(
                f"{label}勾稽为 {_reader_number(total.get('range_low'))}–"
                f"{_reader_number(total.get('range_high'))} {unit}。"
            )
        elif total.get("status") == "UNKNOWN":
            bridge_paragraphs.append(
                f"{label}仍为未知，因为至少一个纳入项尚不能界定；不得按零补齐。"
            )
        else:
            bridge_paragraphs.append(f"{label}没有获授权的组件。")

    sensitivity_paragraphs: list[str] = []
    for raw in _items(summary.get("driver_sensitivities")):
        sensitivity = _mapping(raw)
        cases = _mapping(sensitivity.get("input_cases"))
        case_texts: list[str] = []
        if cases.get("mode") == "LOW_BASE_HIGH":
            for label, field in (("低", "low"), ("基准", "base"), ("高", "high")):
                case = _mapping(cases.get(field))
                case_texts.append(
                    f"{label} {_reader_value_or_range(case.get('value_or_range'))}"
                    f"（{case.get('basis')}）"
                )
        elif cases.get("mode") == "BOUNDED_RANGE":
            case = _mapping(cases.get("range"))
            case_texts.append(
                f"范围 {_reader_value_or_range(case.get('value_or_range'))}"
                f"（{case.get('basis')}）"
            )
        transmission = _mapping(sensitivity.get("transmission"))
        normal = _mapping(transmission.get("normal_earnings"))
        owner_cash = _mapping(transmission.get("owner_cash"))
        normal_authority = _reader_component_authority(
            sensitivity.get("normal_earnings_uses")
        )
        owner_cash_authority = _reader_component_authority(
            sensitivity.get("owner_cash_uses")
        )
        route_effect = _reader_route_authority(
            sensitivity.get("valuation_route_attributions")
        )
        reversals = "；".join(
            str(item) for item in _items(sensitivity.get("reversal_observations"))
        )
        sensitivity_paragraphs.append(
            f"驱动：{sensitivity.get('metric')}（{sensitivity.get('horizon')}，"
            f"单位 {sensitivity.get('unit')}）；" + "，".join(case_texts) + "。"
            f"正常盈利传导（权限：{normal_authority}）："
            f"{_reader_sensitivity_transmission(normal)}。"
            f"普通股现金传导（权限：{owner_cash_authority}）："
            f"{_reader_sensitivity_transmission(owner_cash)}。"
            f"价值路线权限：{route_effect}；不在此生成价值、回报或行动数值。"
            f"翻转证据：{reversals}"
        )
    return [
        {"heading": "正常盈利组件桥", "paragraphs": bridge_paragraphs},
        {
            "heading": "关键敏感性与翻转条件",
            "paragraphs": sensitivity_paragraphs or ["当前没有已界定的关键驱动敏感性。"],
        },
    ]


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
    reader_treatments = {
        field: _reader_safe_authority_text(text)
        for field, text in authoritative_treatments.items()
    }
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
    sections = [
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
                reader_treatments["normal_earnings_treatment"],
                reader_treatments["owner_cash_treatment"],
            ],
        },
        {
            "heading": "永久损失与最强反方",
            "paragraphs": [
                (
                    reader_treatments["permanent_loss_treatment"]
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
    ]
    sections.extend(_economic_derivation_reader_sections(value))
    brief = {
        "company_name": value["company_name"],
        "central_judgment": thesis["central_path"],
        "sections": sections,
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
