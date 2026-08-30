#!/usr/bin/env python3
"""Deterministic projection from the technical report to the reader artifact.

The chapter files remain the auditable working surface and therefore retain
machine bindings.  Publication needs a second view of the same narrative:
all economic prose and source anchors stay in place, while code-owned binding
syntax stays in the technical artifact.  This module performs only that
projection; it does not summarize, rewrite, or invent report content.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts.decision_compiler import (
        reader_numeric_slot_metrics,
        scan_free_reader_slot_values_text,
    )
except ModuleNotFoundError:
    from decision_compiler import (
        reader_numeric_slot_metrics,
        scan_free_reader_slot_values_text,
    )


SCHEMA_VERSION = "reader-report-surface-validation.v1"

_CONTROL_ANCHOR_RE = re.compile(
    r"\[(?:insight|decision|valuation|claim|threshold|thesis-test|probability)\s*:[^\]]+\]",
    re.I,
)
_CONTROL_COMMENT_RE = re.compile(r"<!--\s*TURTLE:[^>]*-->", re.I)
_CONTROL_LINE_RE = re.compile(
    r"^(?P<indent>\s*(?:[-*]\s*)?)(?:\*{0,2})?"
    r"(?:洞见引用|估值模型引用|绑定(?:清单)?|证据绑定|决策绑定|模型绑定)"
    r"(?:\*{0,2})?\s*[：:]\s*(?P<body>.*)$",
    re.I,
)
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_FIELD_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:insight_id|claim_id|evidence_id|observation_id|"
    r"calculation_id|decision_entry_id|model_id|source_fact_id)s?"
    r"(?![A-Za-z0-9_])",
    re.I,
)
_CANONICAL_FACT_ID_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:OBS|CALC):[A-Za-z0-9_.:@/-]+",
    re.I,
)
_BINDING_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"[A-Za-z][A-Za-z0-9_-]*(?:[.:][A-Za-z0-9_:@/-]+)+"
    r"(?![A-Za-z0-9_])",
)

_LEDGER_FILES = (
    "insight_ledger.json",
    "claim_evidence.json",
    "decision_ledger.json",
    "valuation_model.json",
    "fact_observations.json",
    "calculation_observations.json",
)
_ID_KEYS = {
    "insight_id",
    "claim_id",
    "evidence_id",
    "decision_entry_id",
    "model_id",
    "entry_id",
    "observation_id",
    "calculation_id",
    "fact_id",
}
_ID_LIST_KEYS = {
    "insight_ids",
    "claim_ids",
    "evidence_ids",
    "decision_entry_ids",
    "valuation_model_ids",
    "model_ids",
    "entry_ids",
    "observation_ids",
    "calculation_ids",
    "source_fact_ids",
    "verified_fact_ids",
    "input_observation_ids",
    "input_calculation_ids",
    "evidence_observation_ids",
    "evidence_calculation_ids",
}
_PUBLIC_MODEL_LABELS = {"NAV", "EPV", "DCF", "DDM", "SOTP", "FCFE", "FCFF"}
_SOURCE_FILENAME_RE = re.compile(
    r"(?:^|[/\\])[^/\\]+\.(?:pdf|json|md|html?|xlsx?|csv|txt)$",
    re.I,
)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _control_ids(value: Any, *, parent_key: str = "") -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            singular_identity = (
                key_text in _ID_KEYS
                or key_text.endswith("_observation_id")
                or key_text.endswith("_calculation_id")
            )
            list_identity = (
                key_text in _ID_LIST_KEYS
                or key_text.endswith("_observation_ids")
                or key_text.endswith("_calculation_ids")
            )
            if singular_identity and isinstance(item, str) and item.strip():
                result.add(item.strip())
            elif list_identity and isinstance(item, list):
                result.update(str(entry).strip() for entry in item if str(entry).strip())
            result.update(_control_ids(item, parent_key=key_text))
    elif isinstance(value, list):
        for item in value:
            result.update(_control_ids(item, parent_key=parent_key))
    return {
        item for item in result
        if item not in _PUBLIC_MODEL_LABELS
        and len(item) >= 4
        and not _SOURCE_FILENAME_RE.search(item)
    }


def known_control_ids(output_dir: str | Path) -> set[str]:
    """Return exact structured identities that must remain technical-only."""
    output = Path(output_dir)
    result: set[str] = set()
    for filename in _LEDGER_FILES:
        result.update(_control_ids(_load(output / filename)))
    return result


def _identity_present(text: str, identity: str) -> bool:
    return bool(re.search(
        r"(?<![A-Za-z0-9_])"
        + re.escape(identity)
        + r"(?![A-Za-z0-9_]|\.(?:pdf|json|md|html?|xlsx?|csv|txt)\b)",
        text,
        re.I,
    ))


def _remove_exact_identities(text: str, identities: set[str]) -> str:
    projected = str(text or "")
    for identity in sorted(identities, key=len, reverse=True):
        projected = projected.replace(identity, "")
    return _CANONICAL_FACT_ID_RE.sub("", projected)


def _project_control_line(line: str, identities: set[str]) -> str:
    """Drop a pure binding line but retain prose sharing the same line."""
    match = _CONTROL_LINE_RE.match(line)
    if match is None:
        return line.rstrip()
    parts = re.split(r"([；;])", match.group("body"), maxsplit=1)
    binding_part = _remove_exact_identities(parts[0], identities)
    # Within an explicitly labelled binding line, dotted/qualified tokens are
    # control references even when a stale ledger no longer resolves them.
    # This pattern is deliberately not applied to ordinary prose or footnotes.
    binding_part = _BINDING_TOKEN_RE.sub("", binding_part)
    binding_part = re.sub(r"^[\s/|,，;；。:：-]+", "", binding_part)
    binding_part = re.sub(r"[\s/|,，;；:：-]+$", "", binding_part)
    explanation = parts[2].strip() if len(parts) == 3 else ""
    if binding_part and explanation:
        body = binding_part + "；" + explanation
    else:
        body = binding_part or explanation
    if not body:
        return ""
    return match.group("indent") + body


def compile_reader_report_surface(
    technical_text: str,
    output_dir: str | Path | None = None,
) -> str:
    """Remove only generated control bindings, preserving the full narrative."""
    projected = _CONTROL_COMMENT_RE.sub("", str(technical_text or ""))
    projected = _CONTROL_ANCHOR_RE.sub("", projected)
    identities = known_control_ids(output_dir) if output_dir is not None else set()
    lines = [
        projected_line
        for line in projected.splitlines()
        if (projected_line := _project_control_line(line, identities))
    ]
    projected = "\n".join(lines)
    projected = re.sub(r"[ \t]+\n", "\n", projected)
    projected = re.sub(r"\n{3,}", "\n\n", projected).strip() + "\n"
    return projected


def validate_reader_report_surface(
    reader_text: str,
    narrative_source_text: str,
    output_dir: str | Path,
    *,
    technical_artifact_text: str | None = None,
    executive_text: str = "",
) -> dict[str, Any]:
    """Prove separation without treating the executive memo as the report."""
    findings: list[str] = []
    reader = str(reader_text or "")
    narrative_source = str(narrative_source_text or "")
    technical_artifact = str(
        narrative_source_text
        if technical_artifact_text is None else technical_artifact_text
    )
    executive = str(executive_text or "")
    if not reader.strip():
        findings.append("reader_surface_empty")
    if re.search(r"^#\s+.*(?:投资|公司判断)备忘录\s*$", reader, re.M):
        findings.append("reader_artifact_is_executive_memo")
    if _CONTROL_ANCHOR_RE.search(reader):
        findings.append("reader_surface_structured_binding_present")
    if _CONTROL_COMMENT_RE.search(reader):
        findings.append("reader_surface_control_comment_present")
    if _FIELD_TOKEN_RE.search(reader):
        findings.append("reader_surface_control_field_present")
    if _CANONICAL_FACT_ID_RE.search(reader):
        findings.append("reader_surface_canonical_fact_identity_present")
    if re.search(r"15\s*章审计底稿|绑定清单", reader, re.I):
        findings.append("reader_surface_internal_product_language_present")

    leaked_ids = sorted(
        identity for identity in known_control_ids(output_dir)
        if identity and _identity_present(reader, identity)
    )
    if leaked_ids:
        findings.extend("reader_surface_control_id_present:" + item for item in leaked_ids)

    # This is an exact projection contract, not a length or quality score: every
    # narrative H2 that existed in the technical report must still be present.
    technical_headings = list(dict.fromkeys(_HEADING_RE.findall(narrative_source)))
    reader_headings = set(_HEADING_RE.findall(reader))
    missing_headings = [heading for heading in technical_headings if heading not in reader_headings]
    if missing_headings:
        findings.extend("reader_surface_heading_missing:" + item for item in missing_headings)
    if technical_headings and not reader_headings:
        findings.append("reader_surface_company_narrative_missing")

    valuation = _load(Path(output_dir) / "valuation_model.json")
    value_bridges = valuation.get("value_bridge_models")
    value_bridges = value_bridges if isinstance(value_bridges, dict) else {}
    raw_slots = value_bridges.get("reader_slots")
    slots = raw_slots if isinstance(raw_slots, list) else []
    slot_metrics = reader_numeric_slot_metrics(valuation)
    slot_cardinality: list[dict[str, Any]] = []
    reader_without_owned_slots = reader
    technical_without_owned_slots = technical_artifact
    for index, raw_slot in enumerate(slots):
        slot = raw_slot if isinstance(raw_slot, dict) else {}
        slot_id = str(slot.get("slot_id") or f"reader_slots[{index}]")
        sentence = str(slot.get("sentence") or "")
        executive_sentence = sentence.rstrip("。；;，,")
        counts = {
            "reader_count": reader.count(sentence) if sentence else 0,
            "technical_count": technical_artifact.count(sentence) if sentence else 0,
            # Memo list rendering removes terminal punctuation.  It is still a
            # copied compiler-owned slot and must not evade the zero-copy rule.
            "executive_count": (
                executive.count(executive_sentence) if executive_sentence else 0
            ),
        }
        status = "PASS" if counts == {
            "reader_count": 1,
            "technical_count": 1,
            "executive_count": 0,
        } else "BLOCKED"
        slot_cardinality.append({
            "slot_id": slot_id,
            **counts,
            "status": status,
        })
        if status == "BLOCKED":
            findings.append(
                "reader_slot_artifact_cardinality_mismatch:"
                + slot_id
                + f":reader={counts['reader_count']}"
                + f":technical={counts['technical_count']}"
                + f":executive={counts['executive_count']}"
            )
        if sentence:
            # Exact cardinality proves the compiler-owned sentence is present in
            # its two allowed artifacts.  Remove one owned occurrence before the
            # semantic scan so any other rendering or amount remains visible.
            reader_without_owned_slots = reader_without_owned_slots.replace(
                sentence, "", 1,
            )
            technical_without_owned_slots = technical_without_owned_slots.replace(
                sentence, "", 1,
            )

    findings.extend(
        scan_free_reader_slot_values_text(
            reader_without_owned_slots,
            slot_metrics,
            location="reader_artifact",
        )
    )
    findings.extend(
        scan_free_reader_slot_values_text(
            technical_without_owned_slots,
            slot_metrics,
            location="technical_artifact",
        )
    )
    findings.extend(
        scan_free_reader_slot_values_text(
            executive,
            slot_metrics,
            location="executive_artifact",
        )
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "BLOCKED" if findings else "PASS",
        "blocking_findings": list(dict.fromkeys(findings)),
        "technical_heading_count": len(technical_headings),
        "reader_heading_count": len(reader_headings),
        "canonical_reader_slot_count": len(slots),
        "reader_slot_cardinality": slot_cardinality,
        "policy": "full_narrative_projection; control_bindings_technical_only; no_summary_substitution",
    }
