#!/usr/bin/env python3
"""Compose one complete, price-separated enterprise underwriting episode.

This is a small read-model layer, not a new evidence store, CJO, valuation
engine, or report pipeline.  It keeps the business judgment in one immutable
``UnderwritingThesis`` and derives three price-free views for the existing CJO,
valuation-routing, and report systems.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


EPISODE_SCHEMA = "enterprise-underwriting-episode.v1"
CJO_PROJECTION_SCHEMA = "enterprise-underwriting-cjo-candidate-projection.v1"
VALUATION_REQUEST_SCHEMA = "enterprise-underwriting-valuation-route-request.v1"
REPORT_HANDOFF_SCHEMA = "enterprise-underwriting-golden-report-handoff.v1"

SAMPLE_IDENTITIES = {"WORKED_CASE", "BLIND_REPLAY", "PROSPECTIVE_EPISODE"}
TREATMENTS = {
    "UNDERWRITE",
    "CONDITIONALLY_UNDERWRITE",
    "SCENARIO_ONLY",
    "EXCLUDE_FROM_BASE",
    "CANNOT_BOUND",
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
    return bool(text) and "://" not in text and (_ROOT / text).is_file()


def _industry_future_thesis(episode: dict[str, Any]) -> dict[str, Any]:
    situation_model = _mapping(episode.get("situation_model"))
    return _mapping(situation_model.get("industry_future_thesis"))


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

    thesis = _mapping(value.get("underwriting_thesis"))
    for field in (
        "thesis_id", "central_path", "normal_earnings_treatment", "owner_cash_treatment",
        "permanent_loss_treatment", "value_route_treatment", "strongest_rival", "monitoring",
    ):
        if not _text(thesis.get(field)):
            findings.append("underwriting_thesis." + field + "_missing")
    findings.extend("underwriting_thesis.price_boundary:" + item for item in _forbidden_paths(thesis))
    if industry_future:
        if value.get("strongest_rival") != industry_future.get("strongest_rival"):
            findings.append("strongest_rival_not_derived_from_industry_future_thesis")
        if thesis.get("strongest_rival") != industry_future.get("strongest_rival"):
            findings.append("underwriting_thesis.strongest_rival_not_derived_from_industry_future_thesis")
        if value.get("reversal_observations") != industry_future.get("reversal_observations"):
            findings.append("reversal_observations_not_derived_from_industry_future_thesis")

    value_route = _mapping(value.get("value_route"))
    for field in ("primary_routes", "excluded_routes", "route_reasoning"):
        route_value = value_route.get(field)
        if field.endswith("routes"):
            if not _items(route_value):
                findings.append("value_route." + field + "_missing")
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


def compile_underwriting_projections(episode: Any) -> dict[str, dict[str, Any]]:
    """Project one thesis into existing-consumer-shaped, price-free views."""
    value = _assert_reviewable(episode)
    thesis = deepcopy(_mapping(value["underwriting_thesis"]))
    industry_future = deepcopy(_industry_future_thesis(value))
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
        "industry_future_thesis": deepcopy(industry_future),
        "normal_earnings_treatment": thesis["normal_earnings_treatment"],
        "owner_cash_treatment": thesis["owner_cash_treatment"],
        "permanent_loss_treatment": thesis["permanent_loss_treatment"],
        "strongest_rival": industry_future["strongest_rival"],
        "monitoring": thesis["monitoring"],
        "component_treatments": deepcopy(value["component_treatments"]),
        "existing_cjo_adapter": "scripts/enterprise_judgment_core.py:compile_cjo_candidate",
        "boundary": "A projection for the existing CJO compiler; it is not a Frozen CJO and cannot authorize value, price, BuyBand, report publication, or investment action.",
    }
    valuation_request = {
        "schema_version": VALUATION_REQUEST_SCHEMA,
        "request_id": "UW-VR:" + value["episode_id"],
        **identity,
        "authority": "ROUTE_REQUEST_ONLY",
        "industry_future_thesis": deepcopy(industry_future),
        "primary_routes": deepcopy(value["value_route"]["primary_routes"]),
        "excluded_routes": deepcopy(value["value_route"]["excluded_routes"]),
        "route_reasoning": value["value_route"]["route_reasoning"],
        "normal_earnings_input_treatment": thesis["normal_earnings_treatment"],
        "owner_cash_input_treatment": thesis["owner_cash_treatment"],
        "permanent_loss_input_treatment": thesis["permanent_loss_treatment"],
        "inputs_excluded_from_base": [
            item["component_id"] for item in value["component_treatments"]
            if item["treatment"] in {"EXCLUDE_FROM_BASE", "SCENARIO_ONLY", "CANNOT_BOUND"}
        ],
        "existing_valuation_adapter": "scripts/valuation_routing.py:build_valuation_route",
        "compatibility_gap": "Existing numeric INVESTMENT_ENRICHMENT requires global SELECTION_ADMITTED. This teaching route request does not create or substitute that admission; U4 must make the restriction claim-local.",
        "boundary": "No current value, price, expected return, BuyBand, or investment action is generated.",
    }
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
        "situation_model": deepcopy(value["situation_model"]),
        "business_position": value["business_position"],
        "survival_case": value["survival_case"],
        "adaptation_case": value["adaptation_case"],
        "normalization_case": value["normalization_case"],
        "owner_cash_treatment": thesis["owner_cash_treatment"],
        "permanent_loss_map": value["permanent_loss_map"],
        "value_route": deepcopy(value["value_route"]),
        "strongest_rival": industry_future["strongest_rival"],
        "reversal_observations": deepcopy(industry_future["reversal_observations"]),
        "existing_report_adapter": "scripts/judgment_generation_handoff.py:build_judgment_generation_handoff",
        "boundary": "The Golden Report writer consumes this thesis and may not replace it with a different company story. This is a teaching handoff, not report-publication authority.",
    }
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


def render_underwriting_readout(episode: Any) -> str:
    """Render the same underwriting thesis in investor order without gate prose."""
    value = _assert_reviewable(episode)
    thesis = _mapping(value["underwriting_thesis"])
    situation_model = _mapping(value["situation_model"])
    industry_future = _industry_future_thesis(value)
    components = "\n".join(
        f"- {item['component_id']}：{item['treatment']}。{item['investment_consequence']}"
        for item in value["component_treatments"]
    )
    reversals = "\n".join(f"- {item}" for item in industry_future["reversal_observations"])
    routes = "、".join(value["value_route"]["primary_routes"])
    excluded = "、".join(value["value_route"]["excluded_routes"])
    return f"""# {value['company_name']}：{value['decision_frame']}

{thesis['central_path']}

## 行业未来与公司传导

观察时域：{industry_future['horizon']}

最可能的行业路径：{industry_future['most_likely_regime']}

利润池传导：{industry_future['profit_pool_transmission']}

公司暴露：{industry_future['company_exposure']}

适应能力：{industry_future['adaptation']}

正常经济与普通股现金：{industry_future['normal_economics']}

永久损失路径：{industry_future['permanent_loss']}

价值处理：{industry_future['valuation_treatment']}

最强竞争解释：{industry_future['strongest_rival']}

## 处境、位置与适应

{situation_model['summary']}

{value['business_position']}

{value['adaptation_case']}

## 生存、正常化与普通股现金

{value['survival_case']}

{value['normalization_case']}

正常盈利处理：{thesis['normal_earnings_treatment']}

普通股现金处理：{thesis['owner_cash_treatment']}

## 永久损失、反方与翻转

{value['permanent_loss_map']}

最强反方：{industry_future['strongest_rival']}

以下事实会改变当前处理：
{reversals}

## 承保与价值路线

{components}

价值路线：{routes}。不采用：{excluded}。

{thesis['value_route_treatment']}

当前研究处理：{value['investment_treatment']}
"""
