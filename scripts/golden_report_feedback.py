#!/usr/bin/env python3
"""Route Golden Report review returns without leaking them into reader prose.

The review return is a control-plane object: it explains why a candidate is
below standard and what must change.  The reader writer consumes a different,
strictly smaller object containing only accepted economic conclusions and
plain-language writing instructions.  Keeping those two payloads separate is
the core boundary enforced here.
"""

from __future__ import annotations

import re
from typing import Any


REVIEW_SCHEMA_VERSION = "golden-report-review-return.v1"
ROUTING_SCHEMA_VERSION = "golden-report-feedback-routing.v1"

ROOT_CAUSE_CLASSES = {
    "DATA_COVERAGE",
    "ACQUISITION_MODULE",
    "REASONING",
    "MODEL",
    "WRITING",
}
UPSTREAM_CLASSES = ROOT_CAUSE_CLASSES - {"WRITING"}
REMEDIATION_STATES = {"OPEN", "ACCEPTED", "CLOSED_NON_MATERIAL"}

_OWNER_BY_CLASS = {
    "DATA_COVERAGE": "ACQUISITION_SCHEMA",
    "ACQUISITION_MODULE": "ACQUISITION_IMPLEMENTATION",
    "REASONING": "UNDERWRITING_THESIS",
    "MODEL": "DETERMINISTIC_MODEL",
    "WRITING": "READER_WRITER",
}
_OWNER_ORDER = tuple(_OWNER_BY_CLASS.values())

# These are exact control identities, not broad financial or uncertainty
# concepts.  NAV, EPV, owner cash, ordinary-language uncertainty and audited
# financial statements remain valid reader language.
_READER_CONTROL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "review_taxonomy",
        re.compile(
            r"\b(?:DATA_COVERAGE|ACQUISITION_MODULE|REASONING|MODEL|WRITING)\b"
        ),
    ),
    (
        "workflow_status",
        re.compile(
            r"\b(?:PRIMARY_ROUTE_UNKNOWN|NO_PRIMARY|DECISION_READY|REVIEWABLE|"
            r"BINDING_PENDING|SELECTION_ADMITTED|PIT_EVIDENCE_ONLY|"
            r"MECHANISM_READY|NOT_EVIDENCED|LEARNING_APPLIED)\b",
            re.I,
        ),
    ),
    (
        "internal_model_identity",
        re.compile(r"(?<![A-Za-z0-9_])P_(?:LONG|XIRR_[A-Za-z0-9_]+)\b", re.I),
    ),
    (
        "workflow_object_id",
        re.compile(
            r"(?<![A-Za-z0-9_])(?:JAX(?:REPORT|UNIT)?|FJ|RHP(?:ASM|EDGE|SIG)?|"
            r"FDB(?:DRV|EV|MON|REAL)?):[A-Za-z0-9_.:@/-]+",
            re.I,
        ),
    ),
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unique_texts(value: Any) -> bool:
    items = _items(value)
    return bool(items) and all(_text(item) for item in items) and len(set(items)) == len(items)


def validate_golden_report_review_return(review: Any) -> dict[str, Any]:
    """Validate the material review-return contract used by the dispatcher."""
    value = _mapping(review)
    findings: list[str] = []
    if value.get("schema_version") != REVIEW_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in (
        "review_id", "report_id", "candidate_ref", "reviewer_id", "reviewed_at",
    ):
        if not _text(value.get(field)):
            findings.append(field + "_missing")

    review_findings = _items(value.get("findings"))
    if not review_findings:
        findings.append("findings_missing")
    seen_ids: set[str] = set()
    required_text = ("economic_impact",)
    required_lists = (
        "affected_claims",
        "missing_facts",
        "prohibited_assumptions",
        "executable_remediation",
        "acceptance_criteria",
    )
    for index, raw in enumerate(review_findings):
        item = _mapping(raw)
        prefix = f"findings[{index}]"
        finding_id = item.get("finding_id")
        if not _text(finding_id) or finding_id in seen_ids:
            findings.append(prefix + ".finding_id_missing_or_duplicate")
        else:
            seen_ids.add(str(finding_id))
        classes = _items(item.get("root_cause_classes"))
        if (
            not classes
            or any(value not in ROOT_CAUSE_CLASSES for value in classes)
            or len(set(classes)) != len(classes)
        ):
            findings.append(prefix + ".root_cause_classes_invalid")
        if item.get("materiality") not in {"MATERIAL", "NON_MATERIAL"}:
            findings.append(prefix + ".materiality_invalid")
        for field in required_text:
            if not _text(item.get(field)):
                findings.append(prefix + "." + field + "_missing")
        for field in required_lists:
            if not _unique_texts(item.get(field)):
                findings.append(prefix + "." + field + "_missing_or_invalid")
        chapters = item.get("affected_chapters")
        if (
            not isinstance(chapters, list)
            or any(not isinstance(chapter, int) or isinstance(chapter, bool) or chapter < 0 or chapter > 14 for chapter in chapters)
            or len(set(chapters)) != len(chapters)
        ):
            findings.append(prefix + ".affected_chapters_invalid")
        state = item.get("remediation_status")
        if state not in REMEDIATION_STATES:
            findings.append(prefix + ".remediation_status_invalid")
        evidence_refs = item.get("acceptance_evidence_refs")
        if not isinstance(evidence_refs, list) or any(not _text(ref) for ref in evidence_refs):
            findings.append(prefix + ".acceptance_evidence_refs_invalid")
        if state == "ACCEPTED" and not evidence_refs:
            findings.append(prefix + ".accepted_without_evidence")
        if state == "CLOSED_NON_MATERIAL" and item.get("materiality") != "NON_MATERIAL":
            findings.append(prefix + ".material_finding_closed_as_non_material")
        guidance = item.get("reader_guidance")
        if guidance not in (None, "") and not _text(guidance):
            findings.append(prefix + ".reader_guidance_invalid")
    return {
        "schema_version": "golden-report-review-return-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def _reader_control_findings(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        forbidden_keys = {
            "root_cause_classes",
            "missing_facts",
            "prohibited_assumptions",
            "executable_remediation",
            "acceptance_criteria",
            "remediation_status",
            "acceptance_evidence_refs",
        }
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in forbidden_keys:
                findings.append("reader_control_key:" + child_path)
            findings.extend(_reader_control_findings(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_reader_control_findings(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for category, pattern in _READER_CONTROL_PATTERNS:
            if pattern.search(value):
                findings.append(f"reader_control_token:{category}:{path}")
    return findings


def compile_golden_report_feedback_route(review: Any) -> dict[str, Any]:
    """Compile review findings into dependency-ordered owner work.

    An open upstream finding can never produce a chapter target.  A pure
    writing finding may do so immediately when it supplies a plain reader
    instruction.  After upstream acceptance, the accepted reader instruction
    may flow to the writer, but the original finding body still may not.
    """
    validation = validate_golden_report_review_return(review)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("golden_report_review_return_invalid:" + ",".join(validation["findings"]))
    value = _mapping(review)
    work_by_owner: dict[str, list[str]] = {owner: [] for owner in _OWNER_ORDER}
    upstream_open: list[str] = []
    reader_ready: list[dict[str, Any]] = []
    reader_deferred: list[str] = []

    for raw in value["findings"]:
        item = _mapping(raw)
        finding_id = str(item["finding_id"])
        classes = set(item["root_cause_classes"])
        state = str(item["remediation_status"])
        if state == "OPEN":
            for cause in item["root_cause_classes"]:
                owner = _OWNER_BY_CLASS[str(cause)]
                if finding_id not in work_by_owner[owner]:
                    work_by_owner[owner].append(finding_id)

        has_upstream = bool(classes & UPSTREAM_CLASSES)
        if state == "OPEN" and has_upstream and item["materiality"] == "MATERIAL":
            upstream_open.append(finding_id)
        guidance = str(item.get("reader_guidance") or "").strip()
        direct_writing = classes == {"WRITING"} and state == "OPEN"
        accepted_upstream = has_upstream and state == "ACCEPTED"
        if guidance and (direct_writing or accepted_upstream):
            clean_findings = _reader_control_findings(guidance)
            if clean_findings:
                raise ValueError("reader_guidance_contains_control_language:" + ",".join(clean_findings))
            reader_ready.append({
                "finding_id": finding_id,
                "affected_chapters": list(item["affected_chapters"]),
                "instruction": guidance,
            })
        elif state == "OPEN" and ("WRITING" in classes or has_upstream):
            reader_deferred.append(finding_id)

    if upstream_open and reader_ready:
        reader_deferred.extend(
            str(item.get("finding_id") or "") for item in reader_ready
        )
        reader_ready = []

    execution_queue = [
        {"owner": owner, "finding_ids": ids}
        for owner, ids in work_by_owner.items()
        if ids
    ]
    chapter_targets = tuple(sorted({
        chapter
        for item in reader_ready
        for chapter in item["affected_chapters"]
    }))
    status = (
        "UPSTREAM_REPAIR_REQUIRED" if upstream_open
        else "READER_REPAIR_READY" if reader_ready
        else "NO_READER_REPAIR"
    )
    return {
        "schema_version": ROUTING_SCHEMA_VERSION,
        "review_id": value["review_id"],
        "report_id": value["report_id"],
        "candidate_ref": value["candidate_ref"],
        "status": status,
        "execution_queue": execution_queue,
        "upstream_open_finding_ids": upstream_open,
        "reader_repair": {
            "repair_targets": chapter_targets,
            "instructions": reader_ready,
            "deferred_finding_ids": list(dict.fromkeys(reader_deferred)),
        },
        "policy": (
            "Upstream findings repair acquisition, underwriting or deterministic model ownership first. "
            "Only plain accepted conclusions or pure writing instructions enter the reader writer."
        ),
    }


def route_golden_report_feedback(completion: Any) -> dict[str, Any]:
    """Read an optional structured review return embedded in completion state."""
    value = _mapping(completion)
    review = value.get("golden_report_review_return")
    if not isinstance(review, dict):
        return {
            "schema_version": ROUTING_SCHEMA_VERSION,
            "status": "NO_STRUCTURED_FEEDBACK",
            "repair_targets": None,
            "upstream_findings": [],
            "reader_findings": [],
            "reader_repair_brief": [],
        }
    route = compile_golden_report_feedback_route(review)
    reader = _mapping(route.get("reader_repair"))
    return {
        **route,
        "repair_targets": tuple(reader.get("repair_targets") or ()),
        "upstream_findings": list(route.get("upstream_open_finding_ids") or []),
        "reader_findings": [
            str(item.get("finding_id"))
            for item in _items(reader.get("instructions"))
        ],
        "reader_repair_brief": [
            {"instruction": str(item.get("instruction") or "")}
            for item in _items(reader.get("instructions"))
        ],
    }
