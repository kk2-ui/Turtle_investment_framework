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
        "normal_earnings_treatment": thesis["normal_earnings_treatment"],
        "owner_cash_treatment": thesis["owner_cash_treatment"],
        "permanent_loss_treatment": thesis["permanent_loss_treatment"],
        "strongest_rival": thesis["strongest_rival"],
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
            "situation_and_route",
            "survival_and_adaptation",
            "normalization_and_owner_cash",
            "permanent_loss_and_rival",
            "value_route_and_research_treatment",
            "reversal_observations",
        ],
        "central_path": thesis["central_path"],
        "situation_model": value["situation_model"],
        "business_position": value["business_position"],
        "survival_case": value["survival_case"],
        "adaptation_case": value["adaptation_case"],
        "normalization_case": value["normalization_case"],
        "owner_cash_treatment": thesis["owner_cash_treatment"],
        "permanent_loss_map": value["permanent_loss_map"],
        "value_route": deepcopy(value["value_route"]),
        "strongest_rival": thesis["strongest_rival"],
        "reversal_observations": deepcopy(value["reversal_observations"]),
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
        elif field != "accepted_conclusions" and any(not _text(item) for item in items):
            findings.append("reader_brief." + field + "_invalid")
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
    only accepted economic conclusions.  Optional deterministic results must
    be explicitly accepted upstream and expose a small list of already
    translated ``reader_conclusions``; raw models, validations and review
    findings are never copied into the brief.
    """
    value = _assert_reviewable(episode)
    thesis = _mapping(value["underwriting_thesis"])
    deterministic_conclusions: list[str] = []
    if deterministic_results is not None:
        results = _mapping(deterministic_results)
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

    component_judgments = [
        (
            f"{item['reason']} 因此，{item['investment_consequence']} "
            f"需要重估这一处理的条件是：{item['promotion_or_resolution_condition']}"
        )
        for item in value["component_treatments"]
    ]
    brief = {
        "company_name": value["company_name"],
        "central_judgment": thesis["central_path"],
        "sections": [
            {
                "heading": "行业处境、公司位置与适应",
                "paragraphs": [
                    value["situation_model"],
                    value["business_position"],
                    value["adaptation_case"],
                ],
            },
            {
                "heading": "生存、正常盈利与普通股现金",
                "paragraphs": [
                    value["survival_case"],
                    value["normalization_case"],
                    thesis["normal_earnings_treatment"],
                    thesis["owner_cash_treatment"],
                ],
            },
            {
                "heading": "永久损失与最强反方",
                "paragraphs": [
                    value["permanent_loss_map"],
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


def render_underwriting_readout(episode: Any) -> str:
    """Render the same underwriting thesis in investor order without gate prose."""
    brief = compile_golden_report_reader_brief(episode)
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
    return f"""# {brief['company_name']}：企业承保读本

{brief['central_judgment']}

{sections}

## 各项判断的投资含义

{components}

{conclusions_block}

## 会改变判断的事实

{reversals}
"""
