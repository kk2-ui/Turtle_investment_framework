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


SCHEMA_VERSION = "reader-report-surface-validation.v1"

_CONTROL_ANCHOR_RE = re.compile(
    r"\[(?:insight|decision|valuation|claim|threshold|thesis-test|probability)\s*:[^\]]+\]",
    re.I,
)
_CONTROL_COMMENT_RE = re.compile(r"<!--\s*TURTLE:[^>]*-->", re.I)
_CONTROL_ONLY_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*{0,2})?"
    r"(?:洞见引用|估值模型引用|绑定(?:清单)?|证据绑定|决策绑定|模型绑定)"
    r"(?:\*{0,2})?\s*[：:].*$",
    re.I,
)
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_FIELD_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:insight_id|claim_id|evidence_id|"
    r"decision_entry_id|model_id)s?(?![A-Za-z0-9_])",
    re.I,
)

_LEDGER_FILES = (
    "insight_ledger.json",
    "claim_evidence.json",
    "decision_ledger.json",
    "valuation_model.json",
)
_ID_KEYS = {
    "insight_id",
    "claim_id",
    "evidence_id",
    "decision_entry_id",
    "model_id",
    "entry_id",
}
_ID_LIST_KEYS = {
    "insight_ids",
    "claim_ids",
    "evidence_ids",
    "decision_entry_ids",
    "valuation_model_ids",
    "model_ids",
    "entry_ids",
}
_PUBLIC_MODEL_LABELS = {"NAV", "EPV", "DCF", "DDM", "SOTP", "FCFE", "FCFF"}


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
            if key_text in _ID_KEYS and isinstance(item, str) and item.strip():
                result.add(item.strip())
            elif key_text in _ID_LIST_KEYS and isinstance(item, list):
                result.update(str(entry).strip() for entry in item if str(entry).strip())
            result.update(_control_ids(item, parent_key=key_text))
    elif isinstance(value, list):
        for item in value:
            result.update(_control_ids(item, parent_key=parent_key))
    return {
        item for item in result
        if item not in _PUBLIC_MODEL_LABELS and len(item) >= 4
    }


def known_control_ids(output_dir: str | Path) -> set[str]:
    """Return exact structured identities that must remain technical-only."""
    output = Path(output_dir)
    result: set[str] = set()
    for filename in _LEDGER_FILES:
        result.update(_control_ids(_load(output / filename)))
    return result


def compile_reader_report_surface(technical_text: str) -> str:
    """Remove only generated control bindings, preserving the full narrative."""
    projected = _CONTROL_COMMENT_RE.sub("", str(technical_text or ""))
    projected = _CONTROL_ANCHOR_RE.sub("", projected)
    lines = [
        line.rstrip()
        for line in projected.splitlines()
        if not _CONTROL_ONLY_LINE_RE.match(line)
    ]
    projected = "\n".join(lines)
    projected = re.sub(r"[ \t]+\n", "\n", projected)
    projected = re.sub(r"\n{3,}", "\n\n", projected).strip() + "\n"
    return projected


def validate_reader_report_surface(
    reader_text: str,
    technical_text: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Prove separation without treating the executive memo as the report."""
    findings: list[str] = []
    reader = str(reader_text or "")
    technical = str(technical_text or "")
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
    if re.search(r"15\s*章审计底稿|绑定清单", reader, re.I):
        findings.append("reader_surface_internal_product_language_present")

    leaked_ids = sorted(
        identity for identity in known_control_ids(output_dir)
        if identity and identity in reader
    )
    if leaked_ids:
        findings.extend("reader_surface_control_id_present:" + item for item in leaked_ids)

    # This is an exact projection contract, not a length or quality score: every
    # narrative H2 that existed in the technical report must still be present.
    technical_headings = list(dict.fromkeys(_HEADING_RE.findall(technical)))
    reader_headings = set(_HEADING_RE.findall(reader))
    missing_headings = [heading for heading in technical_headings if heading not in reader_headings]
    if missing_headings:
        findings.extend("reader_surface_heading_missing:" + item for item in missing_headings)
    if technical_headings and not reader_headings:
        findings.append("reader_surface_company_narrative_missing")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "BLOCKED" if findings else "PASS",
        "blocking_findings": list(dict.fromkeys(findings)),
        "technical_heading_count": len(technical_headings),
        "reader_heading_count": len(reader_headings),
        "policy": "full_narrative_projection; control_bindings_technical_only; no_summary_substitution",
    }

