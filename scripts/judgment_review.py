#!/usr/bin/env python3
"""Independent, non-compensating review of a report's insight ceiling.

The review never changes publication eligibility. It makes an automated report
say what is genuinely differentiated, what is merely competent, and which leap
still prevents the work from reaching an exceptional-investor standard.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-review.v1"
VERDICTS = {"INSIGHTFUL", "COMPETENT", "FRAGILE", "NOT_ASSESSABLE"}
DIMENSION_STATES = {"strong", "mixed", "weak", "not_assessable"}
ANALYSIS_PURPOSES = {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _analysis_purpose(payload: dict[str, Any], output_dir: str | Path | None = None) -> str:
    declared = str(payload.get("analysis_purpose") or "").strip()
    if declared:
        return declared
    if output_dir is not None:
        contract = _load(Path(output_dir) / "analysis_contract.json")
        contract_purpose = str(contract.get("analysis_purpose") or "").strip()
        if contract_purpose:
            return contract_purpose
    return "INVESTMENT_DECISION"


def _ids(items: Any, key: str) -> set[str]:
    return {
        str(item.get(key)) for item in (items or [])
        if isinstance(item, dict) and item.get(key)
    }


def build_judgment_review(
    output_dir: str | Path,
    ceiling_verdict: str,
    verdict_basis: str,
    distinctive_insight: dict[str, Any],
    competent_but_conventional: list[str],
    fragile_leaps: list[dict[str, Any]],
    competitive_explanation_test: dict[str, Any],
    missing_information: list[str],
    decision_dependency: dict[str, Any],
    dimension_assessments: dict[str, Any],
    reviewer_limits: list[str],
    *,
    analysis_purpose: str | None = None,
    judgment_dependency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    insight = _load(output / "insight_ledger.json")
    contract = _load(output / "analysis_contract.json")
    purpose = str(analysis_purpose or insight.get("analysis_purpose") or contract.get("analysis_purpose") or "INVESTMENT_DECISION")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_id": str(insight.get("report_id") or contract.get("ts_code") or output.name),
        "analysis_purpose": purpose,
        "reviewer_mode": "independent_challenger",
        "ceiling_verdict": str(ceiling_verdict or "").upper(),
        "verdict_basis": str(verdict_basis or "").strip(),
        "distinctive_insight": dict(distinctive_insight or {}),
        "competent_but_conventional": list(competent_but_conventional or []),
        "fragile_leaps": list(fragile_leaps or []),
        "competitive_explanation_test": dict(competitive_explanation_test or {}),
        "missing_information": list(missing_information or []),
        "dimension_assessments": dict(dimension_assessments or {}),
        "reviewer_limits": list(reviewer_limits or []),
        "generated_at": _now(),
        "policy_note": "Diagnostic only: this verdict cannot offset or change V3 publication gates.",
    }
    if purpose == "COMPANY_JUDGMENT_ONLY":
        payload["judgment_dependency"] = dict(judgment_dependency or {})
    else:
        payload["decision_dependency"] = dict(decision_dependency or {})
    return payload


def validate_judgment_review(payload: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    invalid: list[str] = []
    incomplete: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    analysis_purpose = _analysis_purpose(payload, output_dir)
    if analysis_purpose not in ANALYSIS_PURPOSES:
        invalid.append("analysis_purpose_invalid")
    if payload.get("reviewer_mode") != "independent_challenger":
        invalid.append("reviewer_mode_invalid")
    verdict = str(payload.get("ceiling_verdict") or "").upper()
    if verdict not in VERDICTS:
        invalid.append("ceiling_verdict_invalid")
    if len(str(payload.get("verdict_basis") or "").strip()) < 30:
        incomplete.append("verdict_basis_too_thin")

    insight_ledger = _load(output / "insight_ledger.json")
    claim_ledger = _load(output / "claim_evidence.json")
    decision_ledger = _load(output / "decision_ledger.json")
    valuation_ledger = _load(output / "valuation_model.json")
    thesis_ledger = _load(output / "thesis_test.json")
    contract = _load(output / "analysis_contract.json")
    contract_purpose = str(contract.get("analysis_purpose") or "").strip()
    if contract_purpose in ANALYSIS_PURPOSES and analysis_purpose != contract_purpose:
        invalid.append("analysis_purpose_contract_mismatch")
    for label, source in (("insight", insight_ledger), ("claim_evidence", claim_ledger), ("thesis_test", thesis_ledger)):
        source_purpose = str(source.get("analysis_purpose") or "").strip()
        if source_purpose in ANALYSIS_PURPOSES and source_purpose != analysis_purpose:
            invalid.append(f"analysis_purpose_{label}_mismatch")
    insight_ids = _ids(insight_ledger.get("insights"), "insight_id")
    evidence_ids = {
        str(fact.get("evidence_id"))
        for claim in claim_ledger.get("claims") or [] if isinstance(claim, dict)
        for fact in claim.get("raw_facts") or [] if isinstance(fact, dict) and fact.get("evidence_id")
    }
    decision_ids = _ids(
        [item for item in decision_ledger.get("entries") or [] if isinstance(item, dict) and item.get("status", "active") == "active"],
        "entry_id",
    )
    model_ids = _ids(valuation_ledger.get("models"), "model_id")
    forward_judgment_ids = _ids(thesis_ledger.get("forward_judgments"), "judgment_id")

    distinctive = payload.get("distinctive_insight")
    if not isinstance(distinctive, dict):
        invalid.append("distinctive_insight_not_object")
        distinctive = {}
    for key in ("insight_id", "why_it_matters", "why_not_obvious"):
        if not str(distinctive.get(key) or "").strip():
            incomplete.append(f"distinctive_insight:{key}_missing")
    if str(distinctive.get("insight_id") or "") not in insight_ids:
        invalid.append("distinctive_insight:unknown_insight_id")
    binding_sets = [("evidence_ids", evidence_ids)]
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
        for forbidden in ("decision_entry_ids", "valuation_model_ids"):
            if forbidden in distinctive:
                invalid.append(f"distinctive_insight:company_judgment_cannot_carry_{forbidden}")
        binding_sets.append(("forward_judgment_ids", forward_judgment_ids))
    else:
        binding_sets.extend((("decision_entry_ids", decision_ids), ("valuation_model_ids", model_ids)))
    for key, known in binding_sets:
        refs = distinctive.get(key)
        if not isinstance(refs, list) or not refs:
            incomplete.append(f"distinctive_insight:{key}_missing")
            continue
        for ref in refs:
            if str(ref) not in known:
                invalid.append(f"distinctive_insight:{key}:unknown:{ref}")

    conventional = payload.get("competent_but_conventional")
    if not isinstance(conventional, list) or not any(str(item).strip() for item in conventional):
        incomplete.append("competent_but_conventional_missing")
    fragile = payload.get("fragile_leaps")
    if not isinstance(fragile, list):
        invalid.append("fragile_leaps_not_array")
        fragile = []
    for idx, item in enumerate(fragile):
        if not isinstance(item, dict):
            invalid.append(f"fragile_leaps[{idx}]:not_object")
            continue
        consequence_key = "judgment_consequence" if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else "decision_consequence"
        for key in ("claim", "why_fragile", "needed_evidence", consequence_key):
            if not str(item.get(key) or "").strip():
                incomplete.append(f"fragile_leaps[{idx}]:{key}_missing")
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY" and "decision_consequence" in item:
            invalid.append(f"fragile_leaps[{idx}]:company_judgment_cannot_carry_decision_consequence")

    competitive = payload.get("competitive_explanation_test")
    if not isinstance(competitive, dict):
        invalid.append("competitive_explanation_test_not_object")
        competitive = {}
    for key in ("strongest_alternative", "evidence_for_alternative", "discriminator", "unresolved"):
        if not str(competitive.get(key) or "").strip():
            incomplete.append(f"competitive_explanation_test:{key}_missing")

    missing = payload.get("missing_information")
    if not isinstance(missing, list):
        invalid.append("missing_information_not_array")
    dependency_key = "judgment_dependency" if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else "decision_dependency"
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY" and "decision_dependency" in payload:
        invalid.append("company_judgment_cannot_carry_decision_dependency")
    dependency = payload.get(dependency_key)
    if not isinstance(dependency, dict):
        invalid.append(dependency_key + "_not_object")
        dependency = {}
    dependency_fields = (
        ("without_insight", "changed_mechanism", "changed_normalized_earnings_or_owner_cash", "changed_monitoring_or_forward_judgment", "conclusion")
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY"
        else ("without_insight", "changed_values", "changed_action", "conclusion")
    )
    for key in dependency_fields:
        if not str(dependency.get(key) or "").strip():
            incomplete.append(f"{dependency_key}:{key}_missing")

    dimensions = payload.get("dimension_assessments")
    if not isinstance(dimensions, dict):
        invalid.append("dimension_assessments_not_object")
        dimensions = {}
    dimension_keys = (
        ("question_selection", "differentiation", "evidence_discrimination", "operating_transmission", "monitoring_relevance")
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY"
        else ("question_selection", "differentiation", "evidence_discrimination", "valuation_transmission", "action_relevance")
    )
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
        for forbidden in ("valuation_transmission", "action_relevance"):
            if forbidden in dimensions:
                invalid.append(f"dimension_assessments:company_judgment_cannot_carry_{forbidden}")
    for key in dimension_keys:
        item = dimensions.get(key)
        if not isinstance(item, dict):
            incomplete.append(f"dimension_assessments:{key}_missing")
            continue
        if item.get("state") not in DIMENSION_STATES:
            invalid.append(f"dimension_assessments:{key}:state_invalid")
        if len(str(item.get("basis") or "").strip()) < 15:
            incomplete.append(f"dimension_assessments:{key}:basis_too_thin")
    limits = payload.get("reviewer_limits")
    if not isinstance(limits, list) or not any(str(item).strip() for item in limits):
        incomplete.append("reviewer_limits_missing")

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWED"
    return {
        "schema_version": "judgment-review-validation.v1",
        "state": state,
        "status": "PASS" if state == "REVIEWED" else "FAIL",
        "ceiling_verdict": verdict if verdict in VERDICTS else "NOT_ASSESSABLE",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "analysis_purpose": analysis_purpose,
        "policy_note": "Judgment review is diagnostic and never changes publication eligibility.",
    }


def persist_judgment_review(output_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    output = Path(output_dir)
    validation = validate_judgment_review(payload, output)
    (output / "judgment_review_last_attempt_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if validation["state"] == "INVALID":
        return {
            "written": False,
            "validation": validation,
            "error": "invalid_judgment_review",
            "last_attempt_validation_path": str(
                output / "judgment_review_last_attempt_validation.json"
            ),
        }
    path = output / "judgment_review.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "judgment_review_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"written": True, "path": str(path), "validation": validation}


def evaluate_output_judgment_review(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    payload = _load(output / "judgment_review.json")
    if not payload:
        result = {
            "schema_version": "judgment-review-validation.v1",
            "state": "NOT_ASSESSABLE",
            "status": "SKIP",
            "ceiling_verdict": "NOT_ASSESSABLE",
            "invalid_findings": [],
            "incomplete_findings": ["judgment_review_missing"],
            "policy_note": "Judgment review is diagnostic and never changes publication eligibility.",
        }
    else:
        result = validate_judgment_review(payload, output)
    if persist:
        (output / "judgment_review_validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result
