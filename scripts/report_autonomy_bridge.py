#!/usr/bin/env python3
"""Derive a writer contract for the component economics in one Episode.

The bridge is a read-only data projection, not another report renderer.  It
gives the existing writer the exact reader-safe economic anchors it must retain
and lets the normal completion gate detect when a complete report omits a
material component, a normal-earnings row, or a sensitivity/reversal link.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

try:
    from scripts.enterprise_underwriting_episode import (
        compile_golden_report_reader_brief,
        validate_enterprise_underwriting_episode,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from enterprise_underwriting_episode import (  # type: ignore[no-redef]
        compile_golden_report_reader_brief,
        validate_enterprise_underwriting_episode,
    )


SCHEMA_VERSION = "enterprise-underwriting-component-reader-bridge.v1"
DEFAULT_OUTPUT_NAME = "enterprise_underwriting_component_reader_bridge.json"
_ECONOMIC_HEADINGS = {"正常盈利组件桥", "关键敏感性与翻转条件"}
_FIELDS = {
    "schema_version", "bridge_id", "identity", "episode_ref",
    "component_anchors", "economic_section_anchors", "reader_requirements", "use_policy",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _identity(episode: Mapping[str, Any]) -> dict[str, str]:
    thesis = _mapping(episode.get("underwriting_thesis"))
    return {
        "episode_id": _text(episode.get("episode_id")),
        "company_id": _text(episode.get("company_id")),
        "cutoff_at": _text(episode.get("cutoff_at")),
        "underwriting_thesis_id": _text(thesis.get("thesis_id")),
    }


def _compile_expected(
    episode: Mapping[str, Any], *, episode_ref: str, findings: list[str],
) -> dict[str, Any]:
    episode_value = deepcopy(dict(episode))
    if validate_enterprise_underwriting_episode(episode_value).get("state") != "REVIEWABLE":
        findings.append("episode_not_reviewable")
        return {}
    identity = _identity(episode_value)
    if not all(identity.values()):
        findings.append("episode_identity_incomplete")
        return {}
    brief = compile_golden_report_reader_brief(episode_value)
    component_anchors = [
        {"anchor_id": f"COMPONENT:{index + 1}", "text": _text(item)}
        for index, item in enumerate(_items(brief.get("component_judgments")))
        if _text(item)
    ]
    economic_section_anchors: list[dict[str, str]] = []
    for raw in _items(brief.get("sections")):
        section = _mapping(raw)
        heading = _text(section.get("heading"))
        if heading not in _ECONOMIC_HEADINGS:
            continue
        for index, paragraph in enumerate(_items(section.get("paragraphs"))):
            text = _text(paragraph)
            if text:
                economic_section_anchors.append({
                    "anchor_id": heading + ":" + str(index + 1),
                    "heading": heading,
                    "text": text,
                })
    if not component_anchors:
        findings.append("component_anchors_missing")
    if {item.get("heading") for item in economic_section_anchors} != _ECONOMIC_HEADINGS:
        findings.append("economic_section_anchors_incomplete")
    if findings:
        return {}
    return {
        "schema_version": SCHEMA_VERSION,
        "bridge_id": "EUCRB:" + identity["episode_id"],
        "identity": identity,
        "episode_ref": _text(episode_ref),
        "component_anchors": component_anchors,
        "economic_section_anchors": economic_section_anchors,
        "reader_requirements": {
            "all_anchors_must_appear_once": True,
            "technical_and_reader_surface": True,
            "requirement": (
                "The existing report writer must retain every supplied reader-safe anchor once. "
                "It may add company-specific explanation but may not promote conditional, excluded, "
                "scenario-only, or unresolved component treatment."
            ),
        },
        "use_policy": {
            "mode": "READER_REPORT_COMPONENT_ECONOMIC_CONSTRAINT",
            "episode_remains_authoritative": True,
            "cannot_establish": [
                "NEW_COMPANY_FACT", "VALUATION_PARAMETER", "PRICE", "INVESTMENT_ACTION",
            ],
        },
    }


def compile_component_reader_bridge(
    episode: Mapping[str, Any], *, episode_ref: str,
) -> dict[str, Any]:
    """Compile the component-economics contract an existing writer must consume."""
    findings: list[str] = []
    payload = _compile_expected(episode, episode_ref=episode_ref, findings=findings)
    if findings:
        raise ValueError("component_reader_bridge_invalid:" + ",".join(findings))
    return payload


def validate_component_reader_bridge(
    bridge: Any, episode: Mapping[str, Any], *, episode_ref: str,
) -> dict[str, Any]:
    """Prove the bridge is an exact read-only projection of its named Episode."""
    value = _mapping(bridge)
    findings: list[str] = []
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if set(value) != _FIELDS:
        findings.append("fields_invalid")
    if _text(value.get("episode_ref")) != _text(episode_ref):
        findings.append("episode_ref_mismatch")
    expected = _compile_expected(episode, episode_ref=episode_ref, findings=findings)
    if expected and value != expected:
        findings.append("not_exact_episode_derivation")
    return {
        "schema_version": "enterprise-underwriting-component-reader-bridge-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def validate_component_reader_bridge_cjo_binding(
    bridge: Mapping[str, Any], *, frozen_cjo: Any, current_company_admission: Any,
) -> dict[str, Any]:
    """Require one bridge to belong to the Frozen-CJO Episode it serves.

    Company and cutoff are necessary routing identities, but they cannot prove
    that a component bridge and a frozen company judgment made the same
    underwriting decisions.  The Frozen CJO's retained Episode projection and
    its admission receipt already carry the exact Episode and thesis identities
    needed for this narrow join.
    """
    findings: list[str] = []
    try:
        from scripts.enterprise_judgment_core import validate_frozen_cjo
        from scripts.current_company_cjo_admission import (
            validate_frozen_current_company_cjo_admission,
        )
    except ModuleNotFoundError:  # pragma: no cover - direct script execution
        from enterprise_judgment_core import validate_frozen_cjo  # type: ignore[no-redef]
        from current_company_cjo_admission import (  # type: ignore[no-redef]
            validate_frozen_current_company_cjo_admission,
        )

    frozen = _mapping(frozen_cjo)
    admission = _mapping(current_company_admission)
    if validate_frozen_cjo(frozen).get("state") != "VALID":
        findings.append("frozen_cjo_not_valid")
    if validate_frozen_current_company_cjo_admission(
        frozen_cjo=frozen,
        admission_receipt=admission,
        require_overlay=True,
    ).get("state") != "VALID":
        findings.append("current_company_admission_not_valid")

    bridge_identity = _mapping(_mapping(bridge).get("identity"))
    projection = _mapping(frozen.get("underwriting_thesis_projection"))
    primary_binding = _mapping(
        _mapping(admission.get("candidate_binding")).get("primary_binding")
    )
    for field in ("episode_id", "underwriting_thesis_id"):
        bridge_value = _text(bridge_identity.get(field))
        frozen_value = _text(projection.get(field))
        admission_value = _text(primary_binding.get(field))
        if not bridge_value or bridge_value != frozen_value:
            findings.append("bridge_frozen_cjo_" + field + "_mismatch")
        if not bridge_value or bridge_value != admission_value:
            findings.append("bridge_current_company_admission_" + field + "_mismatch")
    return {
        "schema_version": (
            "enterprise-underwriting-component-reader-cjo-binding-validation.v1"
        ),
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def validate_component_reader_anchors(
    bridge: Mapping[str, Any], *, technical_text: str, reader_text: str,
) -> dict[str, Any]:
    """Check that the existing report retains each derived anchor once per surface."""
    findings: list[str] = []
    anchors = [
        _mapping(item) for field in ("component_anchors", "economic_section_anchors")
        for item in _items(bridge.get(field))
    ]
    for anchor in anchors:
        anchor_id, text = _text(anchor.get("anchor_id")), _text(anchor.get("text"))
        if not anchor_id or not text:
            findings.append("bridge_anchor_invalid")
            continue
        technical_count = str(technical_text or "").count(text)
        reader_count = str(reader_text or "").count(text)
        if technical_count != 1:
            findings.append(f"technical_anchor_cardinality:{anchor_id}:{technical_count}")
        if reader_count != 1:
            findings.append(f"reader_anchor_cardinality:{anchor_id}:{reader_count}")
    return {
        "schema_version": "enterprise-underwriting-component-reader-anchor-validation.v1",
        "state": "PASS" if not findings else "BLOCKED",
        "blocking_findings": list(dict.fromkeys(findings)),
    }
