#!/usr/bin/env python3
"""Build the single derived judgment context consumed by report generation.

The handoff is a read model, not a new source of truth.  It projects small,
role-bounded slices from report-local canonical artifacts and never writes a
handoff file.  Callers must still return to the referenced artifacts for facts,
ledger updates, review, settlement, and learning application.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import enterprise_judgment_core as enterprise_core
    from scripts import cjo_quantitative_investment_overlay as quantitative_overlay
    from scripts import current_company_cjo_admission as current_cjo_admission
    from scripts import industry_underwriting_context as industry_underwriting
except ImportError:  # pragma: no cover - direct script import fallback
    import enterprise_judgment_core as enterprise_core
    import cjo_quantitative_investment_overlay as quantitative_overlay
    import current_company_cjo_admission as current_cjo_admission
    import industry_underwriting_context as industry_underwriting


SCHEMA_VERSION = "judgment-generation-handoff.v1"
VALIDATION_SCHEMA_VERSION = "judgment-generation-handoff-validation.v1"
VIEWS = {"RESEARCH_AGENDA", "JUDGMENT_SYNTHESIS", "INVESTMENT_ENRICHMENT"}
ANALYSIS_PURPOSES = {"COMPANY_JUDGMENT_ONLY", "INVESTMENT_DECISION"}

_FORBIDDEN_EXACT_KEYS = {
    "settlement", "settlement_id", "settlement_status", "settlement_as_of", "settled_at",
    "actual", "actual_value", "actual_observation", "actual_outcomes",
    "price", "market_price", "share_price", "stock_price",
    "action", "action_after_flip", "position", "position_after_flip",
    "investment_return", "expected_return",
}
_READY_LEDGER_STATES = {"REVIEWABLE", "DECISION_READY", "MONITORING"}
_VIEW_PROJECTION_KEYS = {
    "RESEARCH_AGENDA": {
        "agenda_mode", "official_evidence", "decisive_questions", "industry_priors",
        "learning_prompts", "industry_snapshot", "industry_underwriting_context",
    },
    "JUDGMENT_SYNTHESIS": {
        "ledger_states", "claims", "financial_drivers", "allocation_events", "thesis",
        "insights", "adversarial_review",
    },
    "INVESTMENT_ENRICHMENT": {
        "company_judgment_predecessor", "valuation_route",
    },
}
_VIEW_OPTIONAL_PROJECTION_KEYS = {
    "JUDGMENT_SYNTHESIS": {"frozen_cjo"},
    "INVESTMENT_ENRICHMENT": {"quantitative_overlay"},
}
_USAGE_CONTRACT_TRUE_FIELDS = {
    "derived_read_model_only",
    "canonical_artifacts_remain_authoritative",
    "must_return_to_source_before_citation_or_mutation",
    "pre_cutoff_outcomes_prices_and_actions_forbidden",
}
CANONICAL_JUDGMENT_REFS_FIELD = "canonical_judgment_refs"
_CANONICAL_JUDGMENT_REF_FIELDS = {
    "frozen_cjo_ref", "investment_overlay_ref", "current_company_cjo_admission_ref",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _instant(value: Any, *, allow_date_cutoff: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if allow_date_cutoff and len(text) == 10:
        try:
            return datetime.fromisoformat(text).replace(
                hour=23,
                minute=59,
                second=59,
                tzinfo=timezone(timedelta(hours=8)),
            ).astimezone(timezone.utc)
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _source_ref(role: str, artifact_ref: str, pointer: str, allowed_use: str,
                validation_ref: str = "") -> dict[str, Any]:
    result = {
        "role": role,
        "artifact_ref": artifact_ref,
        "pointer": pointer,
        "allowed_use": allowed_use,
    }
    if validation_ref:
        result["validation_ref"] = validation_ref
    return result


def _is_forbidden_key(key: Any) -> bool:
    lowered = str(key).lower()
    return (
        lowered in _FORBIDDEN_EXACT_KEYS
        or lowered.startswith("actual_")
        or lowered.startswith("action_")
        or lowered.endswith("_market_price")
        or lowered.endswith("_share_price")
        or lowered.endswith("_stock_price")
    )


def _safe_projection(value: Any) -> Any:
    """Remove outcome exposure and investment-action fields from a read projection."""
    if isinstance(value, dict):
        return {
            str(key): _safe_projection(item)
            for key, item in value.items()
            if not _is_forbidden_key(key)
        }
    if isinstance(value, list):
        return [_safe_projection(item) for item in value]
    return value


def _forbidden_paths(value: Any, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if _is_forbidden_key(key):
                findings.append(path)
            else:
                findings.extend(_forbidden_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_paths(item, f"{prefix}[{index}]"))
    return findings


def _identity(contract: dict[str, Any]) -> dict[str, str]:
    report_id = str(contract.get("ts_code") or contract.get("code") or contract.get("report_id") or "").strip()
    company_id = str(contract.get("company_id") or report_id).strip()
    pit = contract.get("pit_production") if isinstance(contract.get("pit_production"), dict) else {}
    cutoff = str(
        pit.get("cutoff_at")
        or contract.get("data_as_of") or contract.get("analysis_date")
        or contract.get("cutoff_at") or contract.get("pit_cutoff_at") or ""
    ).strip()
    return {
        "report_id": report_id,
        "company_id": company_id,
        "analysis_purpose": str(contract.get("analysis_purpose") or "").strip(),
        "information_cutoff": cutoff,
    }


def _load_artifact(output: Path, name: str, *, required: bool,
                   invalid: list[str], incomplete: list[str]) -> dict[str, Any]:
    path = output / name
    if not path.is_file():
        if required:
            incomplete.append("artifact_missing:" + name)
        return {}
    value = _read_json(path)
    if not value:
        invalid.append("artifact_invalid_json_or_object:" + name)
    return value


def _identity_match(label: str, observed: Any, expected: str, invalid: list[str]) -> None:
    value = str(observed or "").strip()
    if value and expected and value != expected:
        invalid.append(f"identity_mismatch:{label}:{value}!={expected}")


def _project_question(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "question_id", "topic_family", "mechanism_key", "question", "candidate_origins",
        "base_rate_refs", "base_rate_sample_size", "competing_explanations",
        "discriminating_signals", "research_tasks", "stopping_rule", "confidence",
    )
    return _safe_projection({key: item.get(key) for key in keys if key in item})


def _project_industry_prior(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "mechanism_id", "mechanism_key", "title", "status", "match_reason",
        "company_verification_fields", "alternative_explanations", "company_assessment",
        "question_injected", "forbidden_model_role",
    )
    return {key: item.get(key) for key in keys if key in item}


def _same_company(left: Any, right: Any) -> bool:
    first = str(left or "").strip().upper()
    second = str(right or "").strip().upper()
    if not first or not second:
        return False
    if first == second:
        return True
    first_digits = "".join(char for char in first if char.isdigit())
    second_digits = "".join(char for char in second if char.isdigit())
    return (
        len(first_digits) >= 5
        and len(second_digits) >= 5
        and first_digits[-6:] == second_digits[-6:]
    )


def _project_industry_underwriting_context(
    output: Path,
    identity: dict[str, str],
    warnings: list[str],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    """Load the optional report-local industry read model without gating research."""
    path = output / industry_underwriting.DEFAULT_OUTPUT_NAME
    if not path.is_file():
        return {}, "NOT_COMPILED"
    payload = _read_json(path)
    validation = industry_underwriting.validate_industry_underwriting_context(payload)
    if validation.get("state") != "REVIEWABLE":
        warnings.extend(
            "industry_underwriting_context_excluded_invalid:" + str(item)
            for item in validation.get("findings") or []
        )
        return {}, "EXCLUDED_INVALID"

    company = payload.get("company_identity") if isinstance(payload.get("company_identity"), dict) else {}
    if not _same_company(company.get("company_id"), identity["company_id"]):
        warnings.append("industry_underwriting_context_excluded_company_mismatch")
        return {}, "EXCLUDED_IDENTITY_MISMATCH"
    report_cutoff = _instant(identity["information_cutoff"], allow_date_cutoff=True)
    knowledge = payload.get("knowledge_time") if isinstance(payload.get("knowledge_time"), dict) else {}
    context_cutoff = _instant(
        knowledge.get("cutoff_at") or company.get("cutoff_at"), allow_date_cutoff=True,
    )
    if report_cutoff is None or context_cutoff is None or context_cutoff > report_cutoff:
        warnings.append("industry_underwriting_context_excluded_cutoff_mismatch")
        return {}, "EXCLUDED_CUTOFF_MISMATCH"

    sources.append(_source_ref(
        "INDUSTRY_UNDERWRITING_CONTEXT",
        industry_underwriting.DEFAULT_OUTPUT_NAME,
        "",
        "Industry reference classes, candidate paths, peers, near misses and company-verification fields only; target-company evidence must establish exposure and economics.",
    ))
    status = str(payload.get("context_status") or "BOUNDED")
    return _safe_projection(payload), status


def _fallback_industry_context(output: Path, warnings: list[str]) -> dict[str, Any]:
    try:
        from decisive_question import build_industry_knowledge_context
    except ModuleNotFoundError:
        try:
            from scripts.decisive_question import build_industry_knowledge_context
        except ModuleNotFoundError:
            warnings.append("industry_knowledge_context_builder_unavailable")
            return {}
    context = build_industry_knowledge_context(output)
    if not isinstance(context, dict):
        warnings.append("industry_knowledge_context_invalid")
        return {}
    warnings.extend(str(item) for item in context.get("warnings") or [] if str(item).strip())
    return context


def _resolve_explicit_ref(output: Path, reference: str | Path) -> Path:
    path = Path(reference).expanduser()
    return path.resolve() if path.is_absolute() else (output / path).resolve()


def _canonical_judgment_refs(contract: dict[str, Any], invalid: list[str]) -> dict[str, str]:
    """Resolve the report contract's sole optional CJO/overlay truth bindings.

    A report may remain on the legacy ledger path while no canonical CJO is
    declared.  Once it declares this field, production reads must use exactly
    these references; callers may not substitute a path at read time.
    """
    raw = contract.get(CANONICAL_JUDGMENT_REFS_FIELD)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        invalid.append("analysis_contract.canonical_judgment_refs_invalid")
        return {}
    unexpected = sorted(set(raw) - _CANONICAL_JUDGMENT_REF_FIELDS)
    if unexpected:
        invalid.append(
            "analysis_contract.canonical_judgment_refs_unexpected_fields:" + ",".join(unexpected)
        )
    refs: dict[str, str] = {}
    for field in _CANONICAL_JUDGMENT_REF_FIELDS:
        value = raw.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            invalid.append("analysis_contract.canonical_judgment_refs." + field + "_invalid")
            continue
        refs[field] = text
    if "investment_overlay_ref" in refs:
        for required in ("frozen_cjo_ref", "current_company_cjo_admission_ref"):
            if required not in refs:
                invalid.append("analysis_contract.canonical_judgment_refs.overlay_requires_" + required)
    if "current_company_cjo_admission_ref" in refs and "frozen_cjo_ref" not in refs:
        invalid.append("analysis_contract.canonical_judgment_refs.admission_requires_frozen_cjo")
    return refs


def _validated_learning_note_refs(
    output: Path, raw_admissions: Any, *, information_cutoff: str,
) -> tuple[list[str], list[str]]:
    """Resolve only control-plane admitted learning notes for this cutoff."""
    if raw_admissions is None:
        return [], []
    if not isinstance(raw_admissions, list):
        return [], ["analysis_contract.judgment_learning_admissions_invalid"]
    try:
        from scripts.judgment_feedback_control import read_learning_note_ready_event
        from scripts.judgment_learning import validate_judgment_learning_admission
    except ModuleNotFoundError:
        from judgment_feedback_control import read_learning_note_ready_event
        from judgment_learning import validate_judgment_learning_admission
    try:
        from scripts.judgment_learning_admission import select_judgment_learning_admissions
    except ModuleNotFoundError:
        from judgment_learning_admission import select_judgment_learning_admissions

    accepted: list[str] = []
    findings: list[str] = []
    release_selections: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_admissions):
        prefix = f"judgment_learning_admissions[{index}]"
        if not isinstance(raw, dict):
            findings.append(prefix + ":formal_admission_required")
            continue
        admission = dict(raw)
        for field in ("learning_note_ref", "feedback_ref", "control_plane_db"):
            admission[field] = str(_resolve_explicit_ref(output, admission.get(field) or ""))
        database = admission["control_plane_db"]
        note = _read_json(Path(admission["learning_note_ref"]))
        feedback = _read_json(Path(admission["feedback_ref"]))
        event = read_learning_note_ready_event(
            admission["control_plane_db"],
            feedback_item_id=str(admission.get("feedback_item_id") or ""),
            event_id=str(admission.get("learning_note_event_id") or ""),
            information_cutoff=information_cutoff,
        )
        validation = validate_judgment_learning_admission(
            admission, note=note, feedback=feedback, control_event=event,
            information_cutoff=information_cutoff,
        )
        if validation.get("state") != "REVIEWABLE":
            findings.extend(
                prefix + ":" + str(item) for item in validation.get("findings") or []
            )
            continue
        if database not in release_selections:
            release_selections[database] = select_judgment_learning_admissions(
                database, information_cutoff=information_cutoff,
            )
        identity_fields = (
            "learning_note_ref", "feedback_ref", "feedback_item_id",
            "learning_note_event_id", "application_event_id", "program_id",
            "method_version", "method_scope", "method_release_id",
            "method_released_at",
        )
        released = any(
            all(str(candidate.get(field) or "") == str(admission.get(field) or "") for field in identity_fields)
            for candidate in release_selections[database].get("admissions") or []
            if isinstance(candidate, dict)
        )
        if not released:
            findings.append(prefix + ":method_not_released_for_report_use")
            continue
        accepted.append(admission["learning_note_ref"])
    return accepted, list(dict.fromkeys(findings))


def _pit_plan_knowledge_safe(output: Path, plan: dict[str, Any]) -> bool:
    industry = (
        plan.get("industry_knowledge_context")
        if isinstance(plan.get("industry_knowledge_context"), dict) else {}
    )
    availability = industry.get("availability") if isinstance(industry.get("availability"), dict) else {}
    base_rate = _read_json(output / "base_rate_context.json")
    base_availability = (
        base_rate.get("availability") if isinstance(base_rate.get("availability"), dict) else {}
    )
    mode = str(availability.get("mode") or "")
    if base_availability.get("mode") != "PIT_EVIDENCE_ONLY":
        return False
    matches = industry.get("matched_mechanisms")
    if not isinstance(matches, list):
        return False
    if mode == "PIT_EVIDENCE_ONLY":
        if matches:
            return False
        snapshot_ids: set[str] = set()
    elif mode == "PIT_PROMOTION_SNAPSHOT":
        contract = _read_json(output / "analysis_contract.json")
        pit = contract.get("pit_production") if isinstance(contract.get("pit_production"), dict) else {}
        cutoff = _instant(pit.get("cutoff_at"), allow_date_cutoff=True)
        snapshot = _instant(availability.get("knowledge_snapshot_at"), allow_date_cutoff=True)
        if cutoff is None or snapshot is None or cutoff != snapshot:
            return False
        snapshot_ids = set()
        for mechanism in matches:
            if not isinstance(mechanism, dict):
                return False
            mechanism_id = str(mechanism.get("mechanism_id") or "")
            available_at = _instant(mechanism.get("available_at"), allow_date_cutoff=True)
            if not mechanism_id or available_at is None or available_at > snapshot:
                return False
            snapshot_ids.add(mechanism_id)
    else:
        return False
    for item in plan.get("selected_questions") or []:
        if not isinstance(item, dict):
            return False
        try:
            sample_size = int(item.get("base_rate_sample_size") or 0)
        except (TypeError, ValueError):
            return False
        if item.get("base_rate_refs") or sample_size != 0:
            return False
        for origin in item.get("candidate_origins") or []:
            if str(origin).startswith("industry_knowledge:"):
                if str(origin).split(":", 1)[1] not in snapshot_ids:
                    return False
    return True


def _build_research_agenda(
    output: Path, identity: dict[str, str], learning_note_refs: list[str],
    invalid: list[str], incomplete: list[str], warnings: list[str], sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str]]:
    context = _load_artifact(
        output, "report_context.json", required=True, invalid=invalid, incomplete=incomplete,
    )
    evidence_validation = _load_artifact(
        output, "official_evidence_validation.json", required=True,
        invalid=invalid, incomplete=incomplete,
    )
    plan_path = output / "decisive_question_plan.json"
    plan = _load_artifact(
        output, "decisive_question_plan.json", required=False, invalid=invalid, incomplete=incomplete,
    ) if plan_path.is_file() else {}
    contract = _read_json(output / "analysis_contract.json")
    pit_mode = isinstance(contract.get("pit_production"), dict)
    if pit_mode:
        warnings.append("pit_global_base_rate_library_forbidden_without_case_level_admission")
    if pit_mode and plan and not _pit_plan_knowledge_safe(output, plan):
        warnings.append("pit_upstream_decisive_plan_rejected_unproven_knowledge_isolation")
        plan = {}
    decisive_validation = _load_artifact(
        output, "decisive_question_validation.json", required=True,
        invalid=invalid, incomplete=incomplete,
    ) if plan else {}
    sources.append(
        _source_ref(
            "OFFICIAL_EVIDENCE", "report_context.json", "/coverage/citable_observation_ids",
            "Evidence identity and unresolved-gap routing only; read the canonical observation before citing it.",
            "official_evidence_validation.json",
        )
    )
    if plan:
        sources.extend([
            _source_ref(
                "DECISIVE_QUESTIONS", "decisive_question_plan.json", "/selected_questions",
                "Research agenda, competing explanations, discriminators and stopping rules only.",
                "decisive_question_validation.json",
            ),
            _source_ref(
                "INDUSTRY_PRIOR", "decisive_question_plan.json", "/industry_knowledge_context/matched_mechanisms",
                "Question, alternative-explanation and issuer-verification prompt only; never issuer fact or model input.",
                "decisive_question_validation.json",
            ),
        ])

    meta = context.get("meta") if isinstance(context.get("meta"), dict) else {}
    _identity_match("report_context.report_id", meta.get("report_id") or meta.get("code"), identity["report_id"], invalid)
    _identity_match("decisive_question_plan.report_id", plan.get("report_id"), identity["report_id"], invalid)
    context_validation = context.get("validation") if isinstance(context.get("validation"), dict) else {}
    evidence_state = str(evidence_validation.get("state") or context_validation.get("state") or "")
    if context and evidence_state == "INVALID":
        invalid.append("official_evidence_invalid")
    elif context and evidence_state not in _READY_LEDGER_STATES:
        incomplete.append("official_evidence_not_reviewable")
    plan_validation = plan.get("validation") if isinstance(plan.get("validation"), dict) else {}
    if plan:
        plan_state = str(decisive_validation.get("state") or plan_validation.get("state") or "")
        if plan_state == "INVALID":
            invalid.append("decisive_question_plan_invalid")
        elif plan_state not in _READY_LEDGER_STATES:
            incomplete.append("decisive_question_plan_not_reviewable")

    selected = [item for item in plan.get("selected_questions") or [] if isinstance(item, dict)]
    if plan and not 1 <= len(selected) <= 3:
        incomplete.append("decisive_questions_must_contain_one_to_three_items")
    industry_context = (
        plan.get("industry_knowledge_context")
        if isinstance(plan.get("industry_knowledge_context"), dict)
        else _fallback_industry_context(output, warnings)
    )
    if not plan:
        warnings.append("decisive_question_plan_absent_using_cjo_safe_agenda")
        if not isinstance(contract.get("pit_production"), dict):
            sources.append(_source_ref(
                "INDUSTRY_PRIOR", "canonical:industry_knowledge", "/matched_mechanisms",
                "Canonical mechanism IDs and issuer-verification prompts only; resolve the mechanism before use.",
            ))
    matches = [item for item in industry_context.get("matched_mechanisms") or [] if isinstance(item, dict)]
    industry_availability = (
        industry_context.get("availability")
        if isinstance(industry_context.get("availability"), dict) else {}
    )
    priors = [
        _project_industry_prior(item) for item in matches
        if item.get("status") == "MECHANISM_READY" and item.get("company_assessment") == "NOT_EVIDENCED"
    ]
    excluded_count = len(matches) - len(priors)
    if excluded_count:
        warnings.append(f"industry_matches_excluded_by_ready_not_evidenced_gate:{excluded_count}")

    underwriting_context, underwriting_state = _project_industry_underwriting_context(
        output, identity, warnings, sources,
    )

    learning_prompts: list[dict[str, Any]] = []
    cutoff = _instant(identity["information_cutoff"], allow_date_cutoff=True)
    for index, reference in enumerate(learning_note_refs):
        path = _resolve_explicit_ref(output, reference)
        if not path.is_file():
            invalid.append(f"learning_note_ref_missing:{index}:{path}")
            continue
        note = _read_json(path)
        if note.get("schema_version") != "judgment-learning-note.v2":
            invalid.append(f"learning_note_schema_invalid:{index}")
            continue
        recorded_at = _instant(note.get("recorded_at"))
        if cutoff is None:
            incomplete.append("information_cutoff_required_for_learning_projection")
            continue
        if recorded_at is None:
            invalid.append(f"learning_note_recorded_at_invalid:{index}")
            continue
        if recorded_at > cutoff:
            invalid.append(f"learning_note_after_information_cutoff:{index}")
            continue
        applicability = note.get("applicability") if isinstance(note.get("applicability"), dict) else {}
        next_change = str(note.get("next_research_change") or "").strip()
        if not applicability or not next_change:
            incomplete.append(f"learning_note_projection_incomplete:{index}")
            continue
        note_id = str(note.get("note_id") or "").strip()
        if not note_id:
            invalid.append(f"learning_note_id_missing:{index}")
            continue
        learning_prompts.append({
            "note_id": note_id,
            "applicability": _safe_projection(applicability),
            "next_research_change": next_change,
            "role": "CANDIDATE_METHOD_PROMPT",
        })
        sources.append(_source_ref(
            "METHOD_PROMPT", str(path), "",
            "Candidate change to the next research task; never prior issuer fact, old outcome, or revised thesis.",
        ))

    coverage = context.get("coverage") if isinstance(context.get("coverage"), dict) else {}
    empty_states = {
        "decisive_questions": (
            "AVAILABLE" if selected else "NO_DECISIVE_PLAN_EVIDENCE_ONLY"
        ),
        "industry_priors": (
            "AVAILABLE" if priors else "PIT_EVIDENCE_ONLY"
            if pit_mode else "NO_MATCHING_MECHANISM_READY"
        ),
        "learning_prompts": "AVAILABLE" if learning_prompts else "NO_EXPLICIT_LEARNING_REFS",
        "industry_underwriting_context": underwriting_state,
    }
    return {
        "agenda_mode": (
            "DECISIVE_PLAN" if selected
            else "INDUSTRY_UNDERWRITING" if underwriting_context
            else "INDUSTRY_PRIOR_ONLY" if priors
            else "EVIDENCE_ONLY"
        ),
        "official_evidence": {
            "artifact_ref": "report_context.json",
            "validation_state": evidence_state or "UNAVAILABLE",
            "citable_observation_ids": list(coverage.get("citable_observation_ids") or []),
            "unresolved_gap_count": len(context.get("unresolved_gaps") or []),
            "conflict_count": len(context.get("conflicts") or []),
        },
        "decisive_questions": [_project_question(item) for item in selected],
        "industry_priors": priors,
        "industry_underwriting_context": underwriting_context,
        "industry_snapshot": {
            "mode": str(industry_availability.get("mode") or "CURRENT_LIBRARY"),
            "knowledge_snapshot_at": str(industry_availability.get("knowledge_snapshot_at") or ""),
            "mechanism_ids": [str(item.get("mechanism_id") or "") for item in priors],
        },
        "learning_prompts": learning_prompts,
    }, empty_states


def _ledger_state(
    output: Path, artifact_name: str, validation_name: str,
    invalid: list[str], incomplete: list[str], sources: list[dict[str, Any]], role: str,
) -> tuple[dict[str, Any], str]:
    payload = _load_artifact(
        output, artifact_name, required=True, invalid=invalid, incomplete=incomplete,
    )
    validation = _load_artifact(
        output, validation_name, required=True, invalid=invalid, incomplete=incomplete,
    )
    sources.append(_source_ref(
        role, artifact_name, "", "Structured judgment input for narrative synthesis only.", validation_name,
    ))
    state = str(validation.get("state") or validation.get("status") or "UNAVAILABLE").upper()
    invalid_findings = list(validation.get("invalid_findings") or [])
    incomplete_findings = list(validation.get("incomplete_findings") or [])
    binding_only = (
        state == "INCOMPLETE" and not invalid_findings and bool(incomplete_findings)
        and all("reference_missing" in str(item) for item in incomplete_findings)
    )
    if state == "INVALID" or invalid_findings:
        invalid.append(f"ledger_invalid:{artifact_name}")
    elif state not in _READY_LEDGER_STATES and not binding_only:
        incomplete.append(f"ledger_not_ready:{artifact_name}:{state}")
    return payload, "BINDING_PENDING" if binding_only else state


def _claim_projection(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in payload.get("claims") or []:
        if not isinstance(item, dict):
            continue
        raw_facts = [fact for fact in item.get("raw_facts") or [] if isinstance(fact, dict)]
        result.append(_safe_projection({
            "claim_id": item.get("claim_id"),
            "claim": item.get("claim"),
            "reasoning_steps": item.get("reasoning_steps") or [],
            "alternative_explanations": item.get("alternative_explanations") or [],
            "applicability_conditions": item.get("applicability_conditions") or [],
            "confidence": item.get("confidence") or {},
            "judgment_impact": item.get("judgment_impact") or {},
            "evidence_ids": [fact.get("evidence_id") for fact in raw_facts if fact.get("evidence_id")],
            "observation_ids": [fact.get("observation_id") for fact in raw_facts if fact.get("observation_id")],
        }))
    return result


def _thesis_projection(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "analysis_purpose", "lifecycle", "probability_mode", "probability_qualification",
        "central_path", "competitive_tests", "thresholds", "probability_sets", "mechanism_chains",
        "forward_judgments", "rival_hypothesis_pairs", "analogy_transfer_cards", "selection_admission",
    )
    return _safe_projection({key: payload.get(key) for key in keys if key in payload})


def _build_judgment_synthesis(
    output: Path, identity: dict[str, str], invalid: list[str], incomplete: list[str],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str]]:
    claim, claim_state = _ledger_state(
        output, "claim_evidence.json", "claim_evidence_validation.json", invalid, incomplete,
        sources, "CLAIM_EVIDENCE",
    )
    bridge, bridge_state = _ledger_state(
        output, "financial_driver_bridge.json", "financial_driver_bridge_validation.json", invalid,
        incomplete, sources, "FINANCIAL_DRIVER_BRIDGE",
    )
    thesis, thesis_state = _ledger_state(
        output, "thesis_test.json", "thesis_test_validation.json", invalid, incomplete,
        sources, "THESIS_TEST",
    )
    insight, insight_state = _ledger_state(
        output, "insight_ledger.json", "insight_validation.json", invalid, incomplete,
        sources, "INSIGHT_LEDGER",
    )
    for name, payload in (
        ("claim_evidence", claim), ("financial_driver_bridge", bridge),
        ("thesis_test", thesis), ("insight_ledger", insight),
    ):
        _identity_match(name + ".report_id", payload.get("report_id"), identity["report_id"], invalid)
        _identity_match(name + ".analysis_purpose", payload.get("analysis_purpose"), identity["analysis_purpose"], invalid)

    return {
        "ledger_states": {
            "claim_evidence": claim_state,
            "financial_driver_bridge": bridge_state,
            "thesis_test": thesis_state,
            "insight_ledger": insight_state,
        },
        "claims": _claim_projection(claim),
        "financial_drivers": _safe_projection(bridge.get("drivers") or []),
        "allocation_events": _safe_projection(bridge.get("allocation_events") or []),
        "thesis": _thesis_projection(thesis),
        "insights": _safe_projection(insight.get("insights") or []),
        "adversarial_review": _safe_projection(insight.get("adversarial_review") or {}),
    }, {
        "industry_priors": "NOT_APPLICABLE_TO_VIEW",
        "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
    }


def _build_frozen_cjo_judgment_synthesis(
    output: Path,
    frozen_cjo_path: str | Path,
    identity: dict[str, str],
    invalid: list[str],
    incomplete: list[str],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Read the independently frozen canonical CJO instead of report-local ledgers."""
    path = _resolve_explicit_ref(output, frozen_cjo_path)
    if not path.is_file():
        incomplete.append("artifact_missing:frozen_cjo:" + str(path))
        return {}, {
            "industry_priors": "NOT_APPLICABLE_TO_VIEW",
            "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
        }
    payload = _read_json(path)
    if not payload:
        invalid.append("artifact_invalid_json_or_object:frozen_cjo")
        return {}, {
            "industry_priors": "NOT_APPLICABLE_TO_VIEW",
            "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
        }
    validation = enterprise_core.validate_frozen_cjo(payload)
    if validation["state"] != "VALID":
        invalid.extend("frozen_cjo_invalid:" + item for item in validation["findings"])
        return {}, {
            "industry_priors": "NOT_APPLICABLE_TO_VIEW",
            "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
        }
    _identity_match("frozen_cjo.company_id", payload.get("company_id"), identity["company_id"], invalid)
    cjo_cutoff = str(payload.get("cutoff_at") or "")[:10]
    identity_cutoff = identity["information_cutoff"][:10]
    if cjo_cutoff and identity_cutoff and cjo_cutoff != identity_cutoff:
        invalid.append("identity_mismatch:frozen_cjo.information_cutoff")
    sources.append(_source_ref(
        "FROZEN_CJO",
        str(path),
        "",
        "Read-only canonical enterprise judgment for narrative synthesis; report prose cannot mutate or replace it.",
    ))
    try:
        projection = enterprise_core.project_frozen_cjo_to_judgment_synthesis(payload)
    except enterprise_core.EnterpriseJudgmentCoreError as exc:
        invalid.append("frozen_cjo_projection_failed:" + str(exc))
        projection = {}
    return projection, {
        "industry_priors": "NOT_APPLICABLE_TO_VIEW",
        "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
    }


def _build_investment_enrichment(
    output: Path, identity: dict[str, str], invalid: list[str], incomplete: list[str],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str]]:
    predecessor = _load_artifact(
        output, "company_judgment_predecessor.json", required=True,
        invalid=invalid, incomplete=incomplete,
    )
    route = _load_artifact(
        output, "valuation_route.json", required=True, invalid=invalid, incomplete=incomplete,
    )
    sources.extend([
        _source_ref(
            "CJO_PREDECESSOR", "company_judgment_predecessor.json", "",
            "Immutable same-company, same-cutoff operating judgment; valuation may enrich but not rewrite it.",
        ),
        _source_ref(
            "VALUATION_ROUTE", "valuation_route.json", "",
            "Model applicability and required-research route only; no price or action is supplied.",
        ),
    ])
    if identity["analysis_purpose"] != "INVESTMENT_DECISION":
        invalid.append("investment_enrichment_requires_investment_decision_purpose")
    predecessor_identity = (
        predecessor.get("identity") if isinstance(predecessor.get("identity"), dict) else {}
    )
    if predecessor and predecessor.get("schema_version") != "company-judgment-predecessor.v2":
        invalid.append("company_judgment_predecessor_schema_invalid")
    if predecessor and predecessor_identity.get("status") != "G1J_COMPLETE":
        invalid.append("company_judgment_predecessor_not_g1j_complete")
    if predecessor_identity.get("status") == "G1J_COMPLETE" and predecessor_identity.get("missing_components"):
        invalid.append("company_judgment_predecessor_complete_with_missing_components")
    source = predecessor.get("source") if isinstance(predecessor.get("source"), dict) else {}
    _identity_match("company_judgment_predecessor.report_id", source.get("report_id"), identity["report_id"], invalid)
    predecessor_cutoff = str(source.get("data_as_of") or "")[:10]
    current_cutoff = identity["information_cutoff"][:10]
    if predecessor_cutoff and current_cutoff and predecessor_cutoff != current_cutoff:
        invalid.append("identity_mismatch:company_judgment_predecessor.information_cutoff")
    _identity_match("valuation_route.report_id", route.get("report_id"), identity["report_id"], invalid)
    if predecessor:
        if not isinstance(predecessor.get("central_path"), dict) or not predecessor.get("central_path"):
            incomplete.append("company_judgment_predecessor.central_path_missing")
        if not isinstance(predecessor.get("forward_judgments"), list) or not predecessor.get("forward_judgments"):
            incomplete.append("company_judgment_predecessor.forward_judgments_missing")
        if not isinstance(predecessor.get("mechanism_chains"), list) or not predecessor.get("mechanism_chains"):
            incomplete.append("company_judgment_predecessor.mechanism_chains_missing")
        if not isinstance(predecessor.get("rival_hypothesis_pairs"), list) or not predecessor.get("rival_hypothesis_pairs"):
            incomplete.append("company_judgment_predecessor.rival_hypothesis_pairs_missing")
        if not isinstance(predecessor.get("analogy_transfer_cards"), list) or not predecessor.get("analogy_transfer_cards"):
            incomplete.append("company_judgment_predecessor.analogy_transfer_cards_missing")
        selection = predecessor.get("selection_admission")
        if not isinstance(selection, dict) or not str(selection.get("status") or "").strip():
            incomplete.append("company_judgment_predecessor.selection_admission_missing")
        elif selection.get("status") != "SELECTION_ADMITTED":
            incomplete.append(
                "investment_enrichment_requires_selection_admitted_company_judgment"
            )
        financial_bridge = predecessor.get("financial_driver_bridge")
        if not isinstance(financial_bridge, dict) or not financial_bridge:
            incomplete.append("company_judgment_predecessor.financial_driver_bridge_missing")
        else:
            _identity_match(
                "company_judgment_predecessor.financial_driver_bridge.report_id",
                financial_bridge.get("report_id"), identity["report_id"], invalid,
            )
            if financial_bridge.get("analysis_purpose") != "COMPANY_JUDGMENT_ONLY":
                invalid.append("company_judgment_predecessor.financial_driver_bridge_purpose_invalid")
            bridge_state = str(source.get("financial_driver_bridge_validation_state") or "")
            if bridge_state not in _READY_LEDGER_STATES:
                incomplete.append(
                    "company_judgment_predecessor.financial_driver_bridge_not_reviewable"
                )
    route_validation = route.get("validation") if isinstance(route.get("validation"), dict) else {}
    if route and route_validation.get("state") == "INVALID":
        invalid.append("valuation_route_invalid")
    elif route and route_validation.get("state") not in {"REVIEWABLE", "DECISION_READY", "MONITORING"}:
        incomplete.append("valuation_route_not_reviewable")

    return {
        "company_judgment_predecessor": _safe_projection({
            "source": {
                "report_id": source.get("report_id"),
                "data_as_of": source.get("data_as_of"),
                "snapshot_path": source.get("snapshot_path"),
                "thesis_path": source.get("thesis_path"),
                "thesis_validation_state": source.get("thesis_validation_state"),
                "financial_driver_bridge_path": source.get("financial_driver_bridge_path"),
                "financial_driver_bridge_validation_state": source.get(
                    "financial_driver_bridge_validation_state"
                ),
            },
            "central_path": predecessor.get("central_path") or {},
            "forward_judgments": predecessor.get("forward_judgments") or [],
            "mechanism_chains": predecessor.get("mechanism_chains") or [],
            "rival_hypothesis_pairs": predecessor.get("rival_hypothesis_pairs") or [],
            "analogy_transfer_cards": predecessor.get("analogy_transfer_cards") or [],
            "selection_admission": predecessor.get("selection_admission") or {},
            "financial_driver_bridge": predecessor.get("financial_driver_bridge") or {},
        }),
        "valuation_route": _safe_projection({
            key: route.get(key) for key in (
                "report_id", "route_id", "archetype_id", "legacy_company_profile", "models",
                "rejected_models", "synthesis_policy", "terminal_policy", "required_research",
                "reference_policy",
            ) if key in route
        }),
    }, {
        "industry_priors": "NOT_APPLICABLE_TO_VIEW",
        "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
    }


def _build_frozen_cjo_investment_enrichment(
    output: Path,
    frozen_cjo_path: str | Path,
    investment_overlay_path: str | Path,
    current_company_cjo_admission_path: str | Path,
    identity: dict[str, str],
    invalid: list[str],
    incomplete: list[str],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Project a candidate-only quantitative overlay without reopening CJO truth."""
    frozen_path = _resolve_explicit_ref(output, frozen_cjo_path)
    frozen_cjo = _read_json(frozen_path)
    if not frozen_path.is_file():
        incomplete.append("artifact_missing:frozen_cjo:" + str(frozen_path))
    elif not frozen_cjo:
        invalid.append("artifact_invalid_json_or_object:frozen_cjo")
    else:
        frozen_validation = enterprise_core.validate_frozen_cjo(frozen_cjo)
        if frozen_validation["state"] != "VALID":
            invalid.extend("frozen_cjo_invalid:" + item for item in frozen_validation["findings"])
        else:
            _identity_match("frozen_cjo.company_id", frozen_cjo.get("company_id"), identity["company_id"], invalid)
            frozen_cutoff = str(frozen_cjo.get("cutoff_at") or "")[:10]
            if frozen_cutoff and identity["information_cutoff"][:10] and frozen_cutoff != identity["information_cutoff"][:10]:
                invalid.append("identity_mismatch:frozen_cjo.information_cutoff")
            sources.append(_source_ref(
                "FROZEN_CJO", str(frozen_path), "",
                "Read-only canonical enterprise judgment bound by analysis_contract; report prose cannot mutate or replace it.",
            ))
    admission_path = _resolve_explicit_ref(output, current_company_cjo_admission_path)
    admission_receipt = _read_json(admission_path)
    if not admission_path.is_file():
        incomplete.append("artifact_missing:current_company_cjo_admission:" + str(admission_path))
    elif not admission_receipt:
        invalid.append("artifact_invalid_json_or_object:current_company_cjo_admission")
    elif frozen_cjo:
        admission_validation = current_cjo_admission.validate_frozen_current_company_cjo_admission(
            frozen_cjo=frozen_cjo,
            admission_receipt=admission_receipt,
            require_overlay=True,
        )
        if admission_validation["state"] != "VALID":
            invalid.extend(
                "current_company_cjo_admission_invalid:" + item
                for item in admission_validation["findings"]
            )
        else:
            sources.append(_source_ref(
                "CURRENT_COMPANY_CJO_ADMISSION", str(admission_path), "",
                "Read-only PRIMARY admission receipt; it binds the Frozen CJO to the driver and rival-thesis inputs actually consumed downstream.",
            ))
    path = _resolve_explicit_ref(output, investment_overlay_path)
    if not path.is_file():
        incomplete.append("artifact_missing:investment_overlay:" + str(path))
        return {}, {
            "industry_priors": "NOT_APPLICABLE_TO_VIEW",
            "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
        }
    payload = _read_json(path)
    if not payload:
        invalid.append("artifact_invalid_json_or_object:investment_overlay")
        return {}, {
            "industry_priors": "NOT_APPLICABLE_TO_VIEW",
            "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
        }
    validation = quantitative_overlay.validate_investment_overlay(payload)
    if validation["state"] != "VALID":
        invalid.extend("investment_overlay_invalid:" + item for item in validation["findings"])
        return {}, {
            "industry_priors": "NOT_APPLICABLE_TO_VIEW",
            "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
        }
    cjo_ref = payload["cjo_ref"]
    _identity_match("investment_overlay.company_id", cjo_ref.get("company_id"), identity["company_id"], invalid)
    overlay_cutoff = str(cjo_ref.get("cutoff_at") or "")[:10]
    identity_cutoff = identity["information_cutoff"][:10]
    if overlay_cutoff and identity_cutoff and overlay_cutoff != identity_cutoff:
        invalid.append("identity_mismatch:investment_overlay.information_cutoff")
    if identity["analysis_purpose"] != "INVESTMENT_DECISION":
        invalid.append("investment_enrichment_requires_investment_decision_purpose")
    if frozen_cjo:
        for field in ("cjo_id", "company_id", "cutoff_at", "method_version", "resolution"):
            if cjo_ref.get(field) != frozen_cjo.get(field):
                invalid.append("identity_mismatch:investment_overlay.frozen_cjo." + field)
    payload_admission_ref = payload.get("cjo_admission_ref") if isinstance(payload.get("cjo_admission_ref"), dict) else {}
    if payload_admission_ref != {
        "admission_id": admission_receipt.get("admission_id"),
        "status": admission_receipt.get("status"),
        "cjo_ref": deepcopy(admission_receipt.get("cjo_ref")),
    }:
        invalid.append("identity_mismatch:investment_overlay.current_company_cjo_admission")
    sources.append(_source_ref(
        "CJO_QUANTITATIVE_OVERLAY",
        str(path),
        "",
        "Read-only candidate-only valuation projection. It cannot amend the Frozen CJO, report truth, or trading authority.",
    ))
    try:
        report_projection = quantitative_overlay.build_overlay_report_projection(payload)
    except quantitative_overlay.CJOQuantitativeInvestmentOverlayError as exc:
        invalid.append("investment_overlay_projection_failed:" + str(exc))
        report_projection = {}
    return {
        "company_judgment_predecessor": {
            "source": "FROZEN_CJO",
            "cjo_id": cjo_ref["cjo_id"],
            "company_id": cjo_ref["company_id"],
            "cutoff_at": cjo_ref["cutoff_at"],
            "resolution": cjo_ref["resolution"],
            "read_only": True,
        },
        "valuation_route": {
            "overlay_id": payload["overlay_id"],
            "mode": payload["mode"],
            "valuation_method_ids": [item["method_id"] for item in payload["value_identities"]],
            "status": payload["authority"]["overlay_status"],
            "production_status": payload["authority"]["production_status"],
        },
        "quantitative_overlay": report_projection,
    }, {
        "industry_priors": "NOT_APPLICABLE_TO_VIEW",
        "learning_prompts": "NOT_APPLICABLE_TO_VIEW",
    }


def _shape_findings(handoff: Any) -> tuple[list[str], list[str]]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(handoff, dict):
        return ["handoff_not_object"], []
    if handoff.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if handoff.get("view") not in VIEWS:
        invalid.append("view_invalid")
    identity = handoff.get("identity")
    if not isinstance(identity, dict):
        incomplete.append("identity_missing")
    else:
        for field in ("report_id", "company_id", "analysis_purpose", "information_cutoff"):
            if not str(identity.get(field) or "").strip():
                incomplete.append("identity_missing:" + field)
        if identity.get("analysis_purpose") not in ANALYSIS_PURPOSES:
            invalid.append("analysis_purpose_invalid")
        if identity.get("information_cutoff") and _instant(
            identity.get("information_cutoff"), allow_date_cutoff=True,
        ) is None:
            invalid.append("information_cutoff_invalid")
    sources = handoff.get("source_refs")
    if not isinstance(sources, list) or not sources:
        incomplete.append("source_refs_missing")
    else:
        for index, item in enumerate(sources):
            if not isinstance(item, dict):
                invalid.append(f"source_refs[{index}]:not_object")
                continue
            for field in ("role", "artifact_ref", "pointer", "allowed_use"):
                if field not in item or (field != "pointer" and not str(item.get(field) or "").strip()):
                    incomplete.append(f"source_refs[{index}]:{field}_missing")
    projection = handoff.get("projection")
    if not isinstance(projection, dict):
        incomplete.append("projection_missing")
    elif handoff.get("view") in _VIEW_PROJECTION_KEYS:
        expected_keys = _VIEW_PROJECTION_KEYS[str(handoff["view"])]
        optional_keys = _VIEW_OPTIONAL_PROJECTION_KEYS.get(str(handoff["view"]), set())
        for key in sorted(expected_keys - set(projection)):
            incomplete.append("projection_missing:" + key)
        for key in sorted(set(projection) - expected_keys - optional_keys):
            invalid.append("projection_field_not_allowed_for_view:" + key)
    usage = handoff.get("usage_contract")
    if not isinstance(usage, dict):
        incomplete.append("usage_contract_missing")
    else:
        for field in sorted(_USAGE_CONTRACT_TRUE_FIELDS):
            if field not in usage:
                incomplete.append("usage_contract_missing:" + field)
            elif usage.get(field) is not True:
                invalid.append("usage_contract_must_be_true:" + field)
        for field in sorted(set(usage) - _USAGE_CONTRACT_TRUE_FIELDS):
            invalid.append("usage_contract_field_not_allowed:" + field)
    forbidden = _forbidden_paths(projection)
    invalid.extend("pre_cutoff_field_forbidden:" + path for path in forbidden)
    readiness = handoff.get("readiness")
    if not isinstance(readiness, dict):
        incomplete.append("readiness_missing")
    else:
        readiness_state = str(readiness.get("state") or "")
        if readiness_state not in {"READY", "READY_WITH_NO_PRIOR", "INCOMPLETE", "BLOCKED"}:
            invalid.append("readiness_state_invalid")
        for field in ("invalid_findings", "incomplete_findings", "warnings"):
            if not isinstance(readiness.get(field), list):
                invalid.append("readiness_field_not_array:" + field)
        if not isinstance(readiness.get("empty_states"), dict):
            invalid.append("readiness_empty_states_not_object")
        if readiness_state == "READY_WITH_NO_PRIOR" and not (
            handoff.get("view") == "RESEARCH_AGENDA"
            and isinstance(projection, dict)
            and projection.get("decisive_questions") == []
            and projection.get("industry_priors") == []
            and projection.get("industry_underwriting_context") == {}
        ):
            invalid.append("ready_with_no_prior_state_inconsistent")
    return list(dict.fromkeys(invalid)), list(dict.fromkeys(incomplete))


def validate_judgment_generation_handoff(
    handoff: Any, *, output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate one derived handoff without recomputing or persisting source truth."""
    invalid, incomplete = _shape_findings(handoff)
    if isinstance(handoff, dict):
        readiness = handoff.get("readiness") if isinstance(handoff.get("readiness"), dict) else {}
        invalid.extend(str(item) for item in readiness.get("invalid_findings") or [])
        incomplete.extend(str(item) for item in readiness.get("incomplete_findings") or [])
        if output_dir is not None:
            root = Path(output_dir).expanduser().resolve()
            for index, source in enumerate(handoff.get("source_refs") or []):
                if not isinstance(source, dict):
                    continue
                ref = Path(str(source.get("artifact_ref") or ""))
                if str(source.get("artifact_ref") or "").startswith("canonical:"):
                    continue
                path = ref if ref.is_absolute() else root / ref
                if not path.is_file():
                    incomplete.append(f"source_ref_missing:{index}:{source.get('artifact_ref')}")
                validation_ref = str(source.get("validation_ref") or "").strip()
                if validation_ref:
                    validation_path = Path(validation_ref)
                    validation_path = (
                        validation_path if validation_path.is_absolute()
                        else root / validation_path
                    )
                    if not validation_path.is_file():
                        incomplete.append(
                            f"source_validation_ref_missing:{index}:{validation_ref}"
                        )
    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "READY"
    if (
        state == "READY"
        and isinstance(handoff, dict)
        and (handoff.get("readiness") or {}).get("state") == "READY_WITH_NO_PRIOR"
    ):
        state = "READY_WITH_NO_PRIOR"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": state,
        "status": "PASS" if state in {"READY", "READY_WITH_NO_PRIOR"} else "FAIL",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "empty_states": dict((handoff or {}).get("readiness", {}).get("empty_states") or {})
        if isinstance(handoff, dict) else {},
    }


def build_judgment_generation_handoff(
    output_dir: str | Path,
    view: str,
    *,
    frozen_cjo_path: str | Path | None = None,
    investment_overlay_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build an in-memory handoff from admitted report-local artifacts."""
    output = Path(output_dir).expanduser().resolve()
    normalized_view = str(view or "").upper()
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    sources: list[dict[str, Any]] = []
    if normalized_view not in VIEWS:
        invalid.append("view_invalid:" + normalized_view)

    contract = _load_artifact(
        output, "analysis_contract.json", required=True, invalid=invalid, incomplete=incomplete,
    )
    identity = _identity(contract)
    for field in ("report_id", "company_id", "analysis_purpose", "information_cutoff"):
        if not str(identity.get(field) or "").strip():
            incomplete.append("identity_missing:" + field)
    if identity["analysis_purpose"] not in ANALYSIS_PURPOSES:
        invalid.append("analysis_purpose_invalid")
    if identity["information_cutoff"] and _instant(
        identity["information_cutoff"], allow_date_cutoff=True,
    ) is None:
        invalid.append("information_cutoff_invalid")
    canonical_judgment_refs = _canonical_judgment_refs(contract, invalid)
    bound_frozen_cjo = canonical_judgment_refs.get("frozen_cjo_ref")
    bound_overlay = canonical_judgment_refs.get("investment_overlay_ref")
    bound_current_company_admission = canonical_judgment_refs.get("current_company_cjo_admission_ref")
    if frozen_cjo_path is not None:
        if bound_frozen_cjo is None:
            invalid.append("frozen_cjo_must_be_bound_in_analysis_contract")
        elif _resolve_explicit_ref(output, frozen_cjo_path) != _resolve_explicit_ref(output, bound_frozen_cjo):
            invalid.append("frozen_cjo_path_must_match_analysis_contract")
    if investment_overlay_path is not None:
        if bound_overlay is None:
            invalid.append("investment_overlay_must_be_bound_in_analysis_contract")
        elif _resolve_explicit_ref(output, investment_overlay_path) != _resolve_explicit_ref(output, bound_overlay):
            invalid.append("investment_overlay_path_must_match_analysis_contract")
    learning_note_refs, admission_findings = _validated_learning_note_refs(
        output,
        contract.get("judgment_learning_admissions"),
        information_cutoff=identity["information_cutoff"],
    )
    invalid.extend(admission_findings)
    sources.append(_source_ref(
        "REPORT_IDENTITY", "analysis_contract.json", "",
        "Company, cutoff and analysis-purpose identity only.",
    ))

    projection: dict[str, Any] = {}
    empty_states: dict[str, str] = {}
    if normalized_view == "RESEARCH_AGENDA":
        projection, empty_states = _build_research_agenda(
            output, identity, learning_note_refs, invalid, incomplete, warnings, sources,
        )
    elif normalized_view == "JUDGMENT_SYNTHESIS":
        if bound_frozen_cjo is not None:
            projection, empty_states = _build_frozen_cjo_judgment_synthesis(
                output, bound_frozen_cjo, identity, invalid, incomplete, sources,
            )
        else:
            projection, empty_states = _build_judgment_synthesis(
                output, identity, invalid, incomplete, sources,
            )
    elif normalized_view == "INVESTMENT_ENRICHMENT":
        if (
            bound_overlay is not None
            and bound_frozen_cjo is not None
            and bound_current_company_admission is not None
        ):
            projection, empty_states = _build_frozen_cjo_investment_enrichment(
                output, bound_frozen_cjo, bound_overlay, bound_current_company_admission,
                identity, invalid, incomplete, sources,
            )
        else:
            projection, empty_states = _build_investment_enrichment(
                output, identity, invalid, incomplete, sources,
            )

    invalid.extend("pre_cutoff_field_forbidden:" + path for path in _forbidden_paths(projection))
    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "BLOCKED" if invalid else "INCOMPLETE" if incomplete else "READY"
    if (
        state == "READY"
        and normalized_view == "RESEARCH_AGENDA"
        and empty_states.get("decisive_questions") == "NO_DECISIVE_PLAN_EVIDENCE_ONLY"
        and empty_states.get("industry_priors") in {
            "NO_MATCHING_MECHANISM_READY", "PIT_EVIDENCE_ONLY",
        }
        and empty_states.get("industry_underwriting_context") in {
            "NOT_COMPILED", "EXCLUDED_INVALID", "EXCLUDED_IDENTITY_MISMATCH",
            "EXCLUDED_CUTOFF_MISMATCH",
        }
    ):
        state = "READY_WITH_NO_PRIOR"
    return {
        "schema_version": SCHEMA_VERSION,
        "view": normalized_view,
        "identity": identity,
        "source_refs": sources,
        "projection": projection,
        "usage_contract": {
            "derived_read_model_only": True,
            "canonical_artifacts_remain_authoritative": True,
            "must_return_to_source_before_citation_or_mutation": True,
            "pre_cutoff_outcomes_prices_and_actions_forbidden": True,
        },
        "readiness": {
            "state": state,
            "invalid_findings": invalid,
            "incomplete_findings": incomplete,
            "warnings": list(dict.fromkeys(warnings)),
            "empty_states": empty_states,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("read", "validate"):
        command = sub.add_parser(name)
        command.add_argument("--output-dir", required=True)
        command.add_argument("--view", required=True, choices=sorted(VIEWS))
        command.add_argument(
            "--frozen-cjo",
            help="Explicit canonical Frozen CJO path for the JUDGMENT_SYNTHESIS read-only view.",
        )
        command.add_argument(
            "--investment-overlay",
            help="Explicit candidate-only quantitative overlay for the INVESTMENT_ENRICHMENT read-only view.",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handoff = build_judgment_generation_handoff(
        args.output_dir,
        args.view,
        frozen_cjo_path=args.frozen_cjo,
        investment_overlay_path=args.investment_overlay,
    )
    result = (
        validate_judgment_generation_handoff(handoff, output_dir=args.output_dir)
        if args.command == "validate" else handoff
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    state = str((result.get("readiness") or {}).get("state") or result.get("state") or "")
    return 0 if state in {"READY", "READY_WITH_NO_PRIOR"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
