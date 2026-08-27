#!/usr/bin/env python3
"""Validate task findings and aggregate them into a decision-impact synthesis."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-research-synthesis.v1"
FINDING_VERSION = "judgment-research-finding.v1"
RESOLUTIONS = {"SUPPORTED", "CONTRADICTED", "MIXED", "UNRESOLVED", "PUBLIC_INFO_UNAVAILABLE"}
RELATIONS = {"supports", "contradicts", "context"}
SOURCE_KINDS = {"primary_filing", "official_data", "independent_dataset", "company_statement", "secondary_research", "market_data", "unknown"}
DIRECTNESS = {"DIRECT", "INDIRECT", "CONTEXT"}
IMPACT_STATES = {"NONE", "CHANGED", "UNCERTAIN"}
UNCERTAINTY_AXES = {
    "OPERATING_MECHANISM", "CUSTOMER_DEMAND", "NORMAL_EARNINGS",
    "OWNER_CASH", "PERMANENT_LOSS", "VALUATION", "ACTION",
}
CURRENT_POSITION_STATES = {
    "RETAIN_CONDITIONALLY", "NARROW_PRIOR", "EXCLUDE_FROM_BASE_CASE",
    "REVERSE_PRIOR", "RANGE_ONLY",
}
BASE_CASE_TREATMENTS = {
    "EXCLUDE", "CONDITIONAL_INCLUDE", "WIDEN_RANGE", "LOWER_CONFIDENCE",
    "RETAIN_WITHOUT_UPGRADE",
}
ECONOMIC_CONSEQUENCES = {
    "UPSIDE_WITHHELD", "DOWNSIDE_RETAINED", "RANGE_WIDENED",
    "CASH_ACCESS_DISCOUNT_RETAINED", "NORMAL_EARNINGS_CREDIT_WITHHELD",
    "ACTION_WITHHELD", "CLOSED_AXES_UNCHANGED",
}
NUMERIC_OBSERVATION_OPERATORS = {
    "ABOVE", "AT_OR_ABOVE", "BELOW", "AT_OR_BELOW",
}
LOWER_BOUND_OPERATORS = {"ABOVE", "AT_OR_ABOVE"}
UPPER_BOUND_OPERATORS = {"BELOW", "AT_OR_BELOW"}
EVENT_OBSERVATION_OPERATORS = {"OCCURS", "DOES_NOT_OCCUR"}
_DEFENSIVE_ONLY_RE = re.compile(
    r"^(?:当前|仍然|仍|所以|因此|全部|所有|相关|经济影响|本次|继续|并|且|\s)*"
    r"(?:无法(?:作出|进行)?(?:任何)?判断|(?:全部|所有).*未知|保持未知(?:并)?等待.*|"
    r"经济影响(?:仍|也)?未知(?:并)?(?:维持)?不变|等待(?:未来|后续|新的|更多|公开)*.*(?:资料|披露|信息|数据))"
    r"[。；;，,\s]*$",
    re.I,
)
_GENERIC_OBSERVATION_RE = re.compile(
    r"^(?:等待|查看|关注|取得|获取)?(?:未来|后续|下一次|新的|更多|公开|公司)*"
    r"(?:资料|披露|信息|数据|公告|文件|经营指标|相关指标|公告中的经营指标)"
    r"(?:资料|披露|信息|数据)?[。；;，,\s]*$",
    re.I,
)
_DECISION_REFERENCE_RE = re.compile(
    r"判断|结论|支持|反对|改变|调整|升级|降级|推翻|"
    r"judg(?:e)?ment|conclusion|support|oppose|change|upgrade|downgrade|reverse",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha_payload(payload: dict[str, Any]) -> str:
    stable = {
        key: value for key, value in payload.items()
        if key not in {"generated_at", "updated_at", "fingerprint"}
    }
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_judgment_research_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Normalize harmless LLM shape variation without weakening semantics."""
    value = json.loads(json.dumps(finding, ensure_ascii=False, default=str)) if isinstance(finding, dict) else {}
    conditions = value.get("applicability_conditions")
    if isinstance(conditions, str) and conditions.strip():
        value["applicability_conditions"] = [conditions.strip()]
    for field in ("valuation_impact", "action_impact"):
        impact = value.get(field)
        if not isinstance(impact, dict):
            continue
        changes = impact.get("changes")
        if isinstance(changes, str):
            text = changes.strip()
            if not text or text.lower() in {"无", "none", "n/a", "无变化"} or (
                str(impact.get("state") or "").upper() == "NONE" and text.startswith("无")
            ):
                impact["changes"] = []
            elif str(impact.get("state") or "").upper() == "CHANGED":
                impact["changes"] = [{"description": text}]
    return value


def validate_judgment_research_finding(
    finding: dict[str, Any], *, task: dict[str, Any], outcome: str, source_ids: list[str]
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if finding.get("schema_version") != FINDING_VERSION:
        invalid.append("finding_schema_version_invalid")
    if str(finding.get("task_id") or "") != str(task.get("task_id") or ""):
        invalid.append("finding_task_id_mismatch")
    if str(finding.get("prior_claim") or "").strip() != str(task.get("research_question") or "").strip():
        invalid.append("finding_prior_claim_must_match_research_task")
    resolution = str(finding.get("resolution") or "").upper()
    if resolution not in RESOLUTIONS:
        invalid.append("resolution_invalid")
    if outcome == "PUBLIC_INFO_UNAVAILABLE" and resolution != "PUBLIC_INFO_UNAVAILABLE":
        invalid.append("unavailable_outcome_resolution_mismatch")
    if outcome == "EVIDENCE_FOUND" and resolution in {"UNRESOLVED", "PUBLIC_INFO_UNAVAILABLE"}:
        invalid.append("evidence_found_resolution_mismatch")
    for key in ("prior_claim", "inference", "strongest_alternative", "discriminating_result"):
        if len(str(finding.get(key) or "").strip()) < 8:
            incomplete.append(f"{key}_too_thin")
    conditions = finding.get("applicability_conditions")
    if not isinstance(conditions, list) or not any(str(item).strip() for item in conditions):
        incomplete.append("applicability_conditions_missing")

    # An unresolved search is still a research conclusion. It must preserve
    # the best bounded judgment and state how the unknown is treated; merely
    # saying "not found, therefore unchanged" made non-judgment the cheapest
    # completion strategy.
    if resolution in {"UNRESOLVED", "PUBLIC_INFO_UNAVAILABLE"}:
        closure = finding.get("uncertainty_closure")
        if not isinstance(closure, dict):
            incomplete.append("uncertainty_closure_missing")
        else:
            if closure.get("affected_axis") not in UNCERTAINTY_AXES:
                invalid.append("uncertainty_closure:affected_axis_invalid")
            current = closure.get("current_position")
            if not isinstance(current, dict):
                incomplete.append("uncertainty_closure:current_position_missing")
            else:
                if current.get("state") not in CURRENT_POSITION_STATES:
                    invalid.append("uncertainty_closure:current_position_state_invalid")
                if task.get("origin") == "missing_information" and current.get("state") not in {
                    "NARROW_PRIOR", "EXCLUDE_FROM_BASE_CASE", "RANGE_ONLY",
                }:
                    invalid.append("uncertainty_closure:missing_information_cannot_retain_a_question")
                if str(current.get("claim_ref") or "").strip() != str(finding.get("prior_claim") or "").strip():
                    invalid.append("uncertainty_closure:current_position_claim_ref_mismatch")
                basis = str(current.get("basis") or "").strip()
                if len(basis) < 8:
                    incomplete.append("uncertainty_closure:current_position_basis_too_thin")
                elif _DEFENSIVE_ONLY_RE.fullmatch(basis):
                    invalid.append("uncertainty_closure:current_position_basis_is_non_judgment")
            treatment = closure.get("base_case_treatment")
            if not isinstance(treatment, dict):
                incomplete.append("uncertainty_closure:base_case_treatment_missing")
            else:
                if treatment.get("state") not in BASE_CASE_TREATMENTS:
                    invalid.append("uncertainty_closure:base_case_treatment_state_invalid")
                if treatment.get("economic_consequence") not in ECONOMIC_CONSEQUENCES:
                    invalid.append("uncertainty_closure:economic_consequence_invalid")
            observation = closure.get("next_observation")
            if not isinstance(observation, dict):
                incomplete.append("uncertainty_closure:next_observation_missing")
            else:
                metric = str(observation.get("metric_or_event") or "").strip()
                if len(metric) < 8:
                    incomplete.append("uncertainty_closure:next_observation_metric_or_event_too_thin")
                if metric and _GENERIC_OBSERVATION_RE.fullmatch(metric):
                    invalid.append("uncertainty_closure:next_observation_not_discriminating")
                branches: list[dict[str, str]] = []
                for field in ("supports_current", "reverses_current"):
                    branch = observation.get(field)
                    if not isinstance(branch, dict):
                        incomplete.append(f"uncertainty_closure:next_observation_{field}_missing")
                        continue
                    kind = str(branch.get("kind") or "")
                    operator = str(branch.get("operator") or "")
                    normalized_branch: dict[str, Any] = {"kind": kind, "operator": operator}
                    if kind == "NUMERIC_THRESHOLD":
                        if operator not in NUMERIC_OBSERVATION_OPERATORS:
                            invalid.append(f"uncertainty_closure:next_observation_{field}_numeric_operator_invalid")
                        raw_value = branch.get("value")
                        if not isinstance(raw_value, (int, float)) or isinstance(raw_value, bool):
                            invalid.append(f"uncertainty_closure:next_observation_{field}_numeric_value_invalid")
                        unit = str(branch.get("unit") or "").strip()
                        if not unit:
                            incomplete.append(f"uncertainty_closure:next_observation_{field}_unit_missing")
                        normalized_branch.update({"value": raw_value, "unit": unit})
                    elif kind == "EVENT":
                        if operator not in EVENT_OBSERVATION_OPERATORS:
                            invalid.append(f"uncertainty_closure:next_observation_{field}_event_operator_invalid")
                        event = str(branch.get("event_definition") or "").strip()
                        if len(event) < 4:
                            incomplete.append(f"uncertainty_closure:next_observation_{field}_event_too_thin")
                        elif _DECISION_REFERENCE_RE.search(event):
                            invalid.append(f"uncertainty_closure:next_observation_{field}_event_refers_to_judgment")
                        normalized_branch["event_definition"] = event
                    else:
                        invalid.append(f"uncertainty_closure:next_observation_{field}_kind_invalid")
                    branches.append(normalized_branch)
                if len(branches) == 2 and branches[0] == branches[1]:
                    invalid.append("uncertainty_closure:next_observation_branches_identical")
                if len(branches) == 2 and all(branch.get("kind") == "NUMERIC_THRESHOLD" for branch in branches):
                    first, second = branches
                    if first.get("unit") != second.get("unit"):
                        invalid.append("uncertainty_closure:next_observation_numeric_units_mismatch")
                    operators = {str(first.get("operator") or ""), str(second.get("operator") or "")}
                    if not (operators & LOWER_BOUND_OPERATORS and operators & UPPER_BOUND_OPERATORS):
                        invalid.append("uncertainty_closure:next_observation_numeric_branches_not_opposed")
                    else:
                        lower = first if first.get("operator") in LOWER_BOUND_OPERATORS else second
                        upper = second if lower is first else first
                        lower_value = lower.get("value")
                        upper_value = upper.get("value")
                        if isinstance(lower_value, (int, float)) and isinstance(upper_value, (int, float)):
                            overlaps = lower_value < upper_value or (
                                lower_value == upper_value
                                and lower.get("operator") == "AT_OR_ABOVE"
                                and upper.get("operator") == "AT_OR_BELOW"
                            )
                            if overlaps:
                                invalid.append("uncertainty_closure:next_observation_numeric_branches_overlap")

    declared_sources = {str(item) for item in source_ids if str(item).strip()}
    evidence = finding.get("evidence_items")
    if not isinstance(evidence, list):
        invalid.append("evidence_items_not_array")
        evidence = []
    if outcome == "EVIDENCE_FOUND" and not evidence:
        incomplete.append("evidence_found_without_evidence_items")
    for idx, item in enumerate(evidence):
        if not isinstance(item, dict):
            invalid.append(f"evidence_items[{idx}]:not_object")
            continue
        source_id = str(item.get("source_id") or "").strip()
        if not source_id:
            invalid.append(f"evidence_items[{idx}]:source_id_missing")
        elif source_id not in declared_sources:
            invalid.append(f"evidence_items[{idx}]:undeclared_source_id:{source_id}")
        if item.get("relation") not in RELATIONS:
            invalid.append(f"evidence_items[{idx}]:relation_invalid")
        if item.get("source_kind") not in SOURCE_KINDS:
            invalid.append(f"evidence_items[{idx}]:source_kind_invalid")
        if str(item.get("directness") or "").upper() not in DIRECTNESS:
            invalid.append(f"evidence_items[{idx}]:directness_invalid")
        if len(str(item.get("fact") or "").strip()) < 8:
            incomplete.append(f"evidence_items[{idx}]:fact_too_thin")
        if not str(item.get("as_of") or "").strip():
            incomplete.append(f"evidence_items[{idx}]:as_of_missing")
    relations = {str(item.get("relation")) for item in evidence if isinstance(item, dict)}
    if resolution == "SUPPORTED" and "supports" not in relations:
        invalid.append("supported_resolution_without_supporting_evidence")
    if resolution == "CONTRADICTED" and "contradicts" not in relations:
        invalid.append("contradicted_resolution_without_contradicting_evidence")
    if resolution == "MIXED" and not {"supports", "contradicts"}.issubset(relations):
        invalid.append("mixed_resolution_requires_supporting_and_contradicting_evidence")
    if outcome == "EVIDENCE_FOUND" and not any(
        isinstance(item, dict)
        and item.get("relation") in {"supports", "contradicts"}
        and str(item.get("directness") or "").upper() in {"DIRECT", "INDIRECT"}
        for item in evidence
    ):
        incomplete.append("evidence_found_without_discriminating_evidence")

    confidence = finding.get("confidence_update")
    if not isinstance(confidence, dict):
        invalid.append("confidence_update_not_object")
    else:
        confidence_values = [confidence.get("before"), confidence.get("after")]
        numeric = True
        for raw in confidence_values:
            try:
                number = float(raw)
                if not 0 <= number <= 1:
                    raise ValueError
            except (TypeError, ValueError):
                numeric = False
                break
        qualitative = all(len(str(raw or "").strip()) >= 8 for raw in confidence_values)
        if not numeric and not qualitative:
            invalid.append("confidence_update:before_after_invalid")
        if len(str(confidence.get("basis") or "").strip()) < 8:
            incomplete.append("confidence_update:basis_too_thin")

    changed_dimensions: list[str] = []
    for field in ("valuation_impact", "action_impact"):
        impact = finding.get(field)
        if not isinstance(impact, dict):
            invalid.append(f"{field}_not_object")
            continue
        state = str(impact.get("state") or "").upper()
        if state not in IMPACT_STATES:
            invalid.append(f"{field}:state_invalid")
        if len(str(impact.get("basis") or "").strip()) < 8:
            incomplete.append(f"{field}:basis_too_thin")
        changes = impact.get("changes")
        if state == "CHANGED":
            changed_dimensions.append(field)
            if not isinstance(changes, list) or not changes:
                incomplete.append(f"{field}:changes_missing")
        elif isinstance(changes, list) and changes:
            invalid.append(f"{field}:changes_present_without_changed_state")
    if outcome == "DECISION_CHANGED" and not changed_dimensions:
        invalid.append("decision_changed_without_structured_impact")
    if outcome in {"NO_DECISION_CHANGE", "PUBLIC_INFO_UNAVAILABLE"} and changed_dimensions:
        invalid.append("no_change_outcome_with_changed_impact")

    chapter_update = finding.get("chapter_update")
    scope = set((task.get("mutation_scope") or {}).get("chapters") or [])
    if not isinstance(chapter_update, dict):
        invalid.append("chapter_update_not_object")
    else:
        chapters = chapter_update.get("chapters") or []
        if any(not isinstance(idx, int) or idx not in scope for idx in chapters):
            invalid.append("chapter_update_outside_mutation_scope")
        needed = bool(chapter_update.get("needed"))
        if needed and not chapters:
            incomplete.append("chapter_update_needed_without_chapters")
        if not needed and chapters:
            invalid.append("chapter_update_chapters_present_when_not_needed")

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "VALID"
    return {
        "schema_version": "judgment-research-finding-validation.v1",
        "state": state,
        "status": "PASS" if state == "VALID" else "FAIL",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "changed_dimensions": changed_dimensions,
    }


def build_judgment_research_synthesis(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "judgment_research_plan.json")
    execution = _load(output / "judgment_research_execution.json")
    queue = [str(item) for item in execution.get("execution_queue") or []]
    rows: list[dict[str, Any]] = []
    invalid: list[str] = []
    pending: list[str] = []
    for task_id in queue:
        task = next((item for item in plan.get("tasks") or [] if isinstance(item, dict) and item.get("task_id") == task_id), {})
        entry = ((execution.get("tasks") or {}).get(task_id) or {})
        if entry.get("status") != "COMPLETE":
            pending.append(task_id)
            continue
        finding = entry.get("finding") if isinstance(entry.get("finding"), dict) else {}
        validation = validate_judgment_research_finding(
            finding, task=task, outcome=str(entry.get("outcome") or ""),
            source_ids=list(entry.get("source_ids") or []),
        )
        if validation["state"] != "VALID":
            invalid.extend(f"{task_id}:{item}" for item in validation["invalid_findings"] + validation["incomplete_findings"])
        rows.append({
            "task_id": task_id,
            "research_question": task.get("research_question"),
            "outcome": entry.get("outcome"),
            "resolution": finding.get("resolution"),
            "inference": finding.get("inference"),
            "confidence_update": finding.get("confidence_update"),
            "valuation_impact": finding.get("valuation_impact"),
            "action_impact": finding.get("action_impact"),
            "uncertainty_closure": finding.get("uncertainty_closure"),
            "chapter_update": finding.get("chapter_update"),
            "source_ids": entry.get("source_ids") or [],
        })
    changed = [row["task_id"] for row in rows if row.get("outcome") == "DECISION_CHANGED"]
    unresolved = [
        row["task_id"] for row in rows
        if row.get("resolution") in {"UNRESOLVED", "PUBLIC_INFO_UNAVAILABLE", "MIXED"}
    ]
    state = "INVALID" if invalid else "IN_PROGRESS" if pending else "AWAITING_INDEPENDENT_REVIEW" if queue else "NO_ACTION"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_id": plan.get("report_id") or output.name,
        "state": state,
        "execution_state": execution.get("state"),
        "task_findings": rows,
        "decision_changed_task_ids": changed,
        "unresolved_task_ids": unresolved,
        "pending_task_ids": pending,
        "invalid_findings": invalid,
        "independent_review": {},
        "generated_at": _now(),
    }
    payload["fingerprint"] = _sha_payload(payload)
    if persist:
        (output / "judgment_research_synthesis.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return payload


def finalize_judgment_research_synthesis(
    output_dir: str | Path,
    *,
    integrated_task_ids: list[str],
    verdict_change: dict[str, Any],
    resolved_gaps: list[str],
    remaining_gaps: list[str],
    decision_conclusion: str,
) -> dict[str, Any]:
    output = Path(output_dir)
    payload = build_judgment_research_synthesis(output, persist=False)
    queue = {row["task_id"] for row in payload.get("task_findings") or []}
    integrated = {str(item) for item in integrated_task_ids or []}
    errors: list[str] = []
    if payload.get("state") != "AWAITING_INDEPENDENT_REVIEW":
        errors.append(f"synthesis_not_reviewable:{payload.get('state')}")
    if integrated != queue:
        errors.append("independent_review_did_not_cover_all_completed_tasks")
    if not isinstance(verdict_change, dict):
        errors.append("verdict_change_not_object")
        verdict_change = {}
    for key in ("before", "after", "reason"):
        if not str(verdict_change.get(key) or "").strip():
            errors.append(f"verdict_change:{key}_missing")
    if len(str(decision_conclusion or "").strip()) < 15:
        errors.append("decision_conclusion_too_thin")
    plan = _load(output / "judgment_research_plan.json")
    review = _load(output / "judgment_review.json")
    if str(verdict_change.get("before") or "").upper() != str(plan.get("source_review_verdict") or "").upper():
        errors.append("verdict_change_before_mismatch")
    if str(verdict_change.get("after") or "").upper() != str(review.get("ceiling_verdict") or "").upper():
        errors.append("verdict_change_after_mismatch")
    if queue and not (list(resolved_gaps or []) or list(remaining_gaps or [])):
        errors.append("gap_resolution_summary_missing")
    review_text = json.dumps(review, ensure_ascii=False)
    for gap in remaining_gaps or []:
        if str(gap).strip() and str(gap).strip() not in review_text:
            errors.append("remaining_gap_not_reflected_in_judgment_review:" + str(gap).strip())
    review_validation = _load(output / "judgment_review_validation.json")
    if review_validation.get("state") != "REVIEWED":
        errors.append("updated_judgment_review_not_reviewed")
    if errors:
        return {"finalized": False, "errors": errors, "synthesis": payload}
    payload["state"] = "REVIEWED"
    payload["independent_review"] = {
        "integrated_task_ids": sorted(integrated),
        "verdict_change": verdict_change,
        "resolved_gaps": list(resolved_gaps or []),
        "remaining_gaps": list(remaining_gaps or []),
        "decision_conclusion": str(decision_conclusion).strip(),
        "reviewed_at": _now(),
    }
    payload["fingerprint"] = _sha_payload(payload)
    (output / "judgment_research_synthesis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"finalized": True, "state": "REVIEWED", "path": str(output / "judgment_research_synthesis.json")}


def evaluate_judgment_research_synthesis(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    payload = _load(output / "judgment_research_synthesis.json")
    if not payload:
        return {"state": "NOT_STARTED", "status": "SKIP", "blocking": False, "findings": []}
    state = str(payload.get("state") or "INVALID")
    findings = list(payload.get("invalid_findings") or [])
    if payload.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if str(payload.get("fingerprint") or "") != _sha_payload(payload):
        findings.append("fingerprint_mismatch")
    if state == "REVIEWED":
        review = payload.get("independent_review") or {}
        task_ids = {str(row.get("task_id")) for row in payload.get("task_findings") or [] if isinstance(row, dict)}
        integrated = {str(item) for item in review.get("integrated_task_ids") or []}
        if integrated != task_ids:
            findings.append("reviewed_task_coverage_mismatch")
        if len(str(review.get("decision_conclusion") or "").strip()) < 15:
            findings.append("reviewed_decision_conclusion_too_thin")
        if _load(output / "judgment_review_validation.json").get("state") != "REVIEWED":
            findings.append("judgment_review_validation_not_reviewed")
    if findings:
        state = "INVALID"
    return {
        "schema_version": "judgment-research-synthesis-validation.v1",
        "state": state,
        "status": "PASS" if state in {"REVIEWED", "NO_ACTION"} else "FAIL" if state == "INVALID" else "PENDING",
        "blocking": state == "INVALID",
        "findings": list(dict.fromkeys(findings)),
        "pending_task_ids": list(payload.get("pending_task_ids") or []),
    }
