#!/usr/bin/env python3
"""Canonical, evidence-bounded industry mechanism knowledge for Turtle.

This module stores reusable mechanisms separately from company insight
candidates.  It is deliberately not a fact store, valuation-input store or
probability engine.  Its only downstream role is to make the next company's
research questions more complete.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


POLICY_SCHEMA_VERSION = "industry-knowledge-policy.v1"
TAXONOMY_SCHEMA_VERSION = "industry-knowledge-taxonomy.v1"
CANDIDATE_SCHEMA_VERSION = "industry-insight-candidate.v1"
MECHANISM_SCHEMA_VERSION = "industry-mechanism.v1"
PROFILE_SCHEMA_VERSION = "company-industry-profile.v1"
CONTEXT_SCHEMA_VERSION = "industry-knowledge-context.v1"

CANDIDATE_STATUSES = {"PROPOSED", "CANDIDATE", "REJECTED"}
MECHANISM_STATUSES = {"CANDIDATE", "CORROBORATED", "MECHANISM_READY", "RETIRED", "REJECTED"}
DIRECT_EVIDENCE_TYPES = {"OBS", "DOC"}
DIRECT_AUTHORITIES = {"audited_filing", "company_filing", "official_statistics", "industry_data", "regulator"}
PROHIBITED_USES = ["company_fact", "valuation_parameter", "probability", "automatic_investment_conclusion"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY_DIR = PROJECT_ROOT / "knowledge" / "industry"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically persist a readable canonical object without identity hashes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, prefix=path.name + ".") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _default_policy() -> dict[str, Any]:
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "library_role": "research_prompt_prior_only",
        "allowed_output": ["research_question", "company_verification_field", "alternative_explanation", "applicability_warning"],
        "prohibited_uses": list(PROHIBITED_USES),
        "promotion_policy": {
            "candidate_requires_direct_evidence": True,
            "corroborated_minimum_independent_corporate_groups": 2,
            "concentrated_industry_minimum_distinct_reporting_periods": 3,
            "mechanism_ready_requires_independent_review": True,
        },
        "independence_policy": {
            "same_corporate_group_not_independent": True,
            "same_reporting_period_cannot_substitute_for_independent_review": True,
            "concentrated_industry_exception_requires_external_validity_limitation": True,
        },
    }


def _default_taxonomy() -> dict[str, Any]:
    return _read_json(DEFAULT_LIBRARY_DIR / "taxonomy.json")


def _library_dir(value: str | Path | None = None) -> Path:
    configured = str(value or os.environ.get("TURTLE_INDUSTRY_KNOWLEDGE_DIR", "")).strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_LIBRARY_DIR


def initialize_industry_knowledge(knowledge_dir: str | Path | None = None) -> dict[str, Any]:
    """Create the canonical directory layout and copy the default policy/taxonomy."""
    root = _library_dir(knowledge_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "candidates").mkdir(exist_ok=True)
    (root / "mechanisms").mkdir(exist_ok=True)
    policy_path, taxonomy_path = root / "policy.json", root / "taxonomy.json"
    created: list[str] = []
    if not policy_path.is_file():
        _write_json(policy_path, _read_json(DEFAULT_LIBRARY_DIR / "policy.json") or _default_policy())
        created.append("policy.json")
    if not taxonomy_path.is_file():
        _write_json(taxonomy_path, _default_taxonomy())
        created.append("taxonomy.json")
    return {"knowledge_dir": str(root), "created": created, "policy": _read_json(policy_path), "taxonomy": _read_json(taxonomy_path)}


def _list_objects(directory: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    if not directory.is_dir():
        return records, errors
    for path in sorted(directory.glob("*.json")):
        payload = _read_json(path)
        if not payload:
            errors.append(f"{path.name}:invalid_json")
        else:
            records.append(payload)
    return records, errors


def _as_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _schema_shape_errors(record: dict[str, Any], required: Iterable[str], prefix: str) -> list[str]:
    return [f"{prefix}:missing:{field}" for field in required if record.get(field) in (None, "", [], {})]


def _taxonomy_keys(taxonomy: dict[str, Any], field: str) -> set[str]:
    return {str(item.get("key")) for item in taxonomy.get(field) or [] if isinstance(item, dict) and item.get("key")}


def _taxonomy_matches(taxonomy: dict[str, Any], field: str, raw_values: Iterable[str]) -> list[str]:
    """Map output metadata labels to canonical taxonomy keys, without guessing facts."""
    normalized = {str(item).strip().lower() for item in raw_values if str(item).strip()}
    matched: list[str] = []
    for item in taxonomy.get(field) or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        labels = {key.lower(), str(item.get("label") or "").strip().lower()}
        labels.update(str(alias).strip().lower() for alias in item.get("aliases") or [])
        if key and labels.intersection(normalized):
            matched.append(key)
    return sorted(set(matched))


def load_company_industry_metadata(
    output_dir: str | Path, *, knowledge_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Read existing output metadata for end-to-end industry knowledge lookup.

    It does not infer company facts. It only maps a report's already-recorded
    industry labels, archetypes and decisive-question mechanism keys to the
    canonical taxonomy.
    """
    output = Path(output_dir)
    initialized = initialize_industry_knowledge(knowledge_dir)
    taxonomy = initialized["taxonomy"]
    contract = _read_json(output / "analysis_contract.json")
    industry_context = _read_json(output / "industry_context.json")
    archetype = _read_json(output / "company_archetype.json")
    questions = _read_json(output / "decisive_question_plan.json")
    sources: list[str] = []
    labels: list[str] = []
    if contract:
        sources.append("analysis_contract.json")
        classification = contract.get("industry_classification") if isinstance(contract.get("industry_classification"), dict) else {}
        labels.extend(str(classification.get(field) or "") for field in ("l1", "l2", "peer_group"))
    if industry_context:
        sources.append("industry_context.json")
        meta = industry_context.get("meta") if isinstance(industry_context.get("meta"), dict) else {}
        labels.extend(str(meta.get(field) or "") for field in ("industry_l1", "industry_l2", "industry_group"))
    archetype_ids: list[str] = []
    if archetype:
        sources.append("company_archetype.json")
        primary = archetype.get("primary_archetype") if isinstance(archetype.get("primary_archetype"), dict) else {}
        archetype_ids.extend(_as_strings([primary.get("archetype_id")]))
        archetype_ids.extend(
            str(item.get("archetype_id") or "") for item in archetype.get("secondary_archetypes") or [] if isinstance(item, dict)
        )
    mechanism_keys: list[str] = []
    if questions:
        sources.append("decisive_question_plan.json")
        mechanism_keys.extend(
            str(item.get("mechanism_key") or "") for item in questions.get("selected_questions") or [] if isinstance(item, dict)
        )
    company_id = str(contract.get("ts_code") or contract.get("code") or questions.get("report_id") or output.name)
    return {
        "company_id": company_id,
        "industry_keys": _taxonomy_matches(taxonomy, "industry_families", labels),
        "mechanism_keys": sorted(set(key for key in mechanism_keys if key in _taxonomy_keys(taxonomy, "mechanism_families"))),
        "archetype_ids": sorted(set(archetype_ids)),
        "source_metadata_files": sources,
        "unmapped_industry_labels": sorted(set(label for label in labels if label and not _taxonomy_matches(taxonomy, "industry_families", [label]))),
    }


def validate_industry_insight_candidate(
    candidate: dict[str, Any], *, taxonomy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one company insight candidate without promoting it to a mechanism."""
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(candidate.get("candidate_id") or "").startswith("IKC:"):
        invalid.append("candidate_id_invalid")
    status = str(candidate.get("status") or "")
    if status not in CANDIDATE_STATUSES:
        invalid.append("candidate_status_invalid")
    required = [
        "title", "mechanism_key", "industry_keys", "company_id", "corporate_group_id", "reporting_period", "insight",
        "applicability_conditions", "non_applicability_conditions", "alternative_explanations", "company_verification_fields", "evidence", "created_at",
    ]
    incomplete.extend(_schema_shape_errors(candidate, required, "candidate"))
    if status == "REJECTED" and not str(candidate.get("rejection_reason") or "").strip():
        incomplete.append("rejected_candidate_reason_missing")
    if taxonomy:
        known_mechanisms = _taxonomy_keys(taxonomy, "mechanism_families")
        known_industries = _taxonomy_keys(taxonomy, "industry_families")
        mechanism_key = str(candidate.get("mechanism_key") or "")
        if mechanism_key and mechanism_key not in known_mechanisms:
            invalid.append("mechanism_key_not_in_taxonomy")
        unknown_industries = sorted(set(_as_strings(candidate.get("industry_keys"))) - known_industries)
        if unknown_industries:
            warnings.append("industry_keys_not_in_taxonomy:" + ",".join(unknown_industries))
    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), list) else []
    if not evidence:
        incomplete.append("direct_obs_doc_evidence_missing")
    source_ids: set[str] = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            invalid.append(f"evidence[{index}]:not_object")
            continue
        evidence_type = str(item.get("evidence_type") or "")
        reference_id = str(item.get("reference_id") or "")
        if evidence_type not in DIRECT_EVIDENCE_TYPES:
            invalid.append(f"evidence[{index}]:not_direct_obs_or_doc")
        if not reference_id.startswith(evidence_type + ":"):
            invalid.append(f"evidence[{index}]:reference_type_mismatch")
        if item.get("direct_support") is not True:
            invalid.append(f"evidence[{index}]:direct_support_required")
        if str(item.get("authority") or "") not in DIRECT_AUTHORITIES:
            invalid.append(f"evidence[{index}]:authority_not_directly_reviewable")
        for field in ("source_id", "source_group_id", "published_at", "data_as_of", "statement"):
            if not str(item.get(field) or "").strip():
                incomplete.append(f"evidence[{index}]:missing:{field}")
        source_id = str(item.get("source_id") or "")
        if source_id and source_id in source_ids:
            warnings.append("duplicate_candidate_source_id:" + source_id)
        source_ids.add(source_id)
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": "industry-knowledge-validation.v1",
        "object_type": "candidate",
        "state": state,
        "status": "FAIL" if state == "INVALID" else "PASS",
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
        "warnings": list(dict.fromkeys(warnings)),
    }


def write_industry_insight_candidate(
    candidate: dict[str, Any], *, knowledge_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Persist an evidence-bounded company insight candidate.

    This function never creates or upgrades a mechanism card.
    """
    initialized = initialize_industry_knowledge(knowledge_dir)
    root = Path(initialized["knowledge_dir"])
    payload = deepcopy(candidate)
    payload.setdefault("schema_version", CANDIDATE_SCHEMA_VERSION)
    payload.setdefault("status", "PROPOSED")
    payload.setdefault("created_at", _now())
    validation = validate_industry_insight_candidate(payload, taxonomy=initialized["taxonomy"])
    if validation["state"] != "REVIEWABLE":
        return {"written": False, "candidate": payload, "validation": validation}
    candidate_id = str(payload.get("candidate_id") or "")
    path = root / "candidates" / (candidate_id.replace(":", "__") + ".json")
    existing = _read_json(path)
    if existing and existing != payload:
        return {"written": False, "error": "candidate_id_conflict", "candidate_id": candidate_id, "validation": validation}
    if not existing:
        _write_json(path, payload)
    return {"written": True, "idempotent": bool(existing), "candidate": payload, "validation": validation}


def _mechanism_candidate_set(
    mechanism: dict[str, Any], candidates: list[dict[str, Any]], taxonomy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    invalid: list[str] = []
    warnings: list[str] = []
    candidate_map = {str(item.get("candidate_id") or ""): item for item in candidates}
    selected: list[dict[str, Any]] = []
    for candidate_id in _as_strings(mechanism.get("candidate_ids")):
        candidate = candidate_map.get(candidate_id)
        if candidate is None:
            invalid.append("referenced_candidate_missing:" + candidate_id)
            continue
        validation = validate_industry_insight_candidate(candidate, taxonomy=taxonomy)
        if validation["state"] != "REVIEWABLE" or candidate.get("status") == "REJECTED":
            invalid.append("referenced_candidate_not_reviewable:" + candidate_id)
            continue
        if str(candidate.get("mechanism_key") or "") != str(mechanism.get("mechanism_key") or ""):
            invalid.append("candidate_mechanism_key_mismatch:" + candidate_id)
            continue
        selected.append(candidate)
    return selected, invalid, warnings


def _corroboration_assessment(
    mechanism: dict[str, Any], candidates: list[dict[str, Any]], policy: dict[str, Any],
) -> dict[str, Any]:
    """Assess cross-group corroboration with a limited concentrated-industry exception."""
    promotion = policy.get("promotion_policy") if isinstance(policy.get("promotion_policy"), dict) else {}
    required_groups = int(promotion.get("corroborated_minimum_independent_corporate_groups") or 2)
    required_periods = int(promotion.get("concentrated_industry_minimum_distinct_reporting_periods") or 3)
    by_group: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        group = str(candidate.get("corporate_group_id") or "")
        if group:
            by_group.setdefault(group, []).append(candidate)
    group_representatives = [sorted(rows, key=lambda item: str(item.get("candidate_id") or ""))[0] for _, rows in sorted(by_group.items())]
    if len(group_representatives) >= required_groups:
        return {
            "sufficient": True, "basis": "independent_corporate_groups",
            "candidate_ids": [item.get("candidate_id") for item in group_representatives],
            "independent_corporate_group_count": len(group_representatives),
            "distinct_reporting_period_count": len({str(item.get("reporting_period") or "") for item in candidates}),
            "external_validity_limited": False,
        }
    exception = mechanism.get("concentrated_industry_exception") if isinstance(mechanism.get("concentrated_industry_exception"), dict) else {}
    periods = sorted({str(item.get("reporting_period") or "") for item in candidates if str(item.get("reporting_period") or "")})
    exception_ready = (
        bool(exception.get("enabled"))
        and len(by_group) == 1
        and len(periods) >= required_periods
        and str(exception.get("rationale") or "").strip()
        and str(exception.get("external_validity_limitation") or "").strip()
    )
    return {
        "sufficient": bool(exception_ready),
        "basis": "concentrated_industry_multi_period_limited" if exception_ready else "insufficient",
        "candidate_ids": [item.get("candidate_id") for item in sorted(candidates, key=lambda item: str(item.get("candidate_id") or ""))],
        "independent_corporate_group_count": len(group_representatives),
        "distinct_reporting_period_count": len(periods),
        "external_validity_limited": bool(exception_ready),
    }


def _mechanism_ready_review_findings(mechanism: dict[str, Any], policy: dict[str, Any]) -> tuple[list[str], list[str]]:
    promotion = policy.get("promotion_policy") if isinstance(policy.get("promotion_policy"), dict) else {}
    incomplete: list[str] = []
    invalid: list[str] = []
    author_id = str(mechanism.get("author_id") or "").strip()
    if not author_id:
        incomplete.append("mechanism_ready_author_id_missing")
    if bool(promotion.get("mechanism_ready_requires_independent_review", True)):
        review = mechanism.get("independent_review") if isinstance(mechanism.get("independent_review"), dict) else {}
        if not review or review.get("independent") is not True or review.get("outcome") != "ACCEPTED":
            incomplete.append("mechanism_ready_independent_review_missing_or_not_accepted")
        else:
            for field in ("reviewer_id", "reviewed_at", "scope"):
                if not str(review.get(field) or "").strip():
                    incomplete.append("mechanism_ready_independent_review_missing:" + field)
            if author_id and str(review.get("reviewer_id") or "").strip() == author_id:
                invalid.append("mechanism_ready_reviewer_same_as_author")
    if not set(PROHIBITED_USES).issubset(set(_as_strings(mechanism.get("prohibited_uses")))):
        incomplete.append("mechanism_ready_explicit_prohibited_roles_incomplete")
    return incomplete, invalid


def review_industry_mechanism(
    mechanism: dict[str, Any] | str, *, knowledge_dir: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Review an industry mechanism against its separate candidate evidence.

    Passing a mapping validates and, by default, persists the mechanism. Passing
    an `IKM:` identifier reads and reviews an existing card without changing it.
    Promotion is explicit: an over-promoted status is rejected, and a lower
    requested status only receives a `promotion_available` warning.
    """
    initialized = initialize_industry_knowledge(knowledge_dir)
    root, policy, taxonomy = Path(initialized["knowledge_dir"]), initialized["policy"], initialized["taxonomy"]
    loaded = not isinstance(mechanism, dict)
    if loaded:
        mechanism_id = str(mechanism or "")
        mechanism = _read_json(root / "mechanisms" / (mechanism_id.replace(":", "__") + ".json"))
        if not mechanism:
            return {"written": False, "error": "mechanism_not_found", "mechanism_id": mechanism_id}
    payload = deepcopy(mechanism)
    if not loaded:
        payload.setdefault("schema_version", MECHANISM_SCHEMA_VERSION)
        payload.setdefault("status", "CANDIDATE")
        payload.setdefault("created_at", _now())
        payload.setdefault("updated_at", payload["created_at"])
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != MECHANISM_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(payload.get("mechanism_id") or "").startswith("IKM:"):
        invalid.append("mechanism_id_invalid")
    requested_status = str(payload.get("status") or "")
    if requested_status not in MECHANISM_STATUSES:
        invalid.append("mechanism_status_invalid")
    required = [
        "mechanism_key", "title", "summary", "industry_keys", "candidate_ids", "applicability_conditions",
        "non_applicability_conditions", "alternative_explanations", "company_verification_fields", "prohibited_uses", "created_at", "updated_at",
    ]
    incomplete.extend(_schema_shape_errors(payload, required, "mechanism"))
    known_mechanisms = _taxonomy_keys(taxonomy, "mechanism_families")
    if str(payload.get("mechanism_key") or "") and payload.get("mechanism_key") not in known_mechanisms:
        invalid.append("mechanism_key_not_in_taxonomy")
    candidates, candidate_errors = _list_objects(root / "candidates")
    selected_candidates, candidate_invalid, candidate_warnings = _mechanism_candidate_set(payload, candidates, taxonomy)
    invalid.extend(candidate_errors + candidate_invalid)
    warnings.extend(candidate_warnings)
    corroboration = _corroboration_assessment(payload, selected_candidates, policy)
    recommended_status = "CORROBORATED" if corroboration["sufficient"] else "CANDIDATE"
    if requested_status in {"CORROBORATED", "MECHANISM_READY"}:
        if not corroboration["sufficient"]:
            invalid.append(
                "cross_group_or_concentrated_industry_corroboration_insufficient:"
                f"groups={corroboration['independent_corporate_group_count']};periods={corroboration['distinct_reporting_period_count']}"
            )
    if requested_status == "MECHANISM_READY":
        ready_incomplete, ready_invalid = _mechanism_ready_review_findings(payload, policy)
        incomplete.extend(ready_incomplete)
        invalid.extend(ready_invalid)
        if not ready_incomplete and not ready_invalid:
            recommended_status = "MECHANISM_READY" if corroboration["sufficient"] else "CANDIDATE"
    if requested_status in {"RETIRED", "REJECTED"} and not str(payload.get("lifecycle_reason") or "").strip():
        incomplete.append("retired_or_rejected_reason_missing")
    if requested_status == "CANDIDATE" and recommended_status != "CANDIDATE":
        warnings.append("promotion_available:" + recommended_status)
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    validation = {
        "schema_version": "industry-knowledge-validation.v1", "object_type": "mechanism", "state": state,
        "status": "FAIL" if state == "INVALID" else "PASS", "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)), "warnings": list(dict.fromkeys(warnings)),
        "corroboration_basis": corroboration["basis"], "corroboration_candidate_ids": corroboration["candidate_ids"],
        "independent_corporate_group_count": corroboration["independent_corporate_group_count"],
        "distinct_reporting_period_count": corroboration["distinct_reporting_period_count"],
        "external_validity_limited": corroboration["external_validity_limited"], "recommended_status": recommended_status,
    }
    if loaded or not persist or state != "REVIEWABLE":
        return {"written": False, "mechanism": payload, "validation": validation}
    mechanism_id = str(payload.get("mechanism_id"))
    path = root / "mechanisms" / (mechanism_id.replace(":", "__") + ".json")
    existing = _read_json(path)
    if existing and existing != payload:
        return {"written": False, "error": "mechanism_id_conflict", "mechanism_id": mechanism_id, "validation": validation}
    if not existing:
        _write_json(path, payload)
    return {"written": True, "idempotent": bool(existing), "mechanism": payload, "validation": validation}


def search_industry_knowledge(
    query: str = "", *, industry_keys: Iterable[str] | None = None,
    mechanism_keys: Iterable[str] | None = None, archetype_ids: Iterable[str] | None = None,
    statuses: Iterable[str] | None = None,
    knowledge_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Search published mechanism cards. Results remain research prompts, never facts."""
    initialized = initialize_industry_knowledge(knowledge_dir)
    root = Path(initialized["knowledge_dir"])
    mechanisms, errors = _list_objects(root / "mechanisms")
    wanted_industries = set(_as_strings(industry_keys))
    wanted_mechanisms = set(_as_strings(mechanism_keys))
    wanted_archetypes = set(_as_strings(archetype_ids))
    allowed_statuses = set(_as_strings(list(statuses or ["MECHANISM_READY"])))
    words = {word for word in re.split(r"[^a-z0-9_:-]+", str(query or "").lower()) if word}
    results: list[dict[str, Any]] = []
    for mechanism in mechanisms:
        if mechanism.get("status") not in allowed_statuses:
            continue
        if wanted_industries and not wanted_industries.intersection(_as_strings(mechanism.get("industry_keys"))):
            continue
        if wanted_mechanisms and str(mechanism.get("mechanism_key") or "") not in wanted_mechanisms:
            continue
        declared_archetypes = set(_as_strings(mechanism.get("archetype_ids")))
        if wanted_archetypes and not (wanted_industries or wanted_mechanisms) and not wanted_archetypes.intersection(declared_archetypes):
            continue
        haystack = " ".join(str(mechanism.get(field) or "") for field in ("mechanism_key", "title", "summary")).lower()
        if words and not all(word in haystack for word in words):
            continue
        results.append(_public_mechanism(mechanism))
    return {
        "schema_version": "industry-knowledge-search.v1", "library_role": "research_prompt_prior_only",
        "results": sorted(results, key=lambda item: (item["mechanism_key"], item["mechanism_id"])),
        "warnings": errors, "prohibited_uses": list(PROHIBITED_USES),
    }


def _public_mechanism(mechanism: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "mechanism_id", "mechanism_key", "title", "status", "summary", "industry_keys", "applicability_conditions",
        "non_applicability_conditions", "alternative_explanations", "company_verification_fields",
        "archetype_ids",
    ]
    return {key: deepcopy(mechanism.get(key)) for key in keys}


def _company_arguments(
    company: str | dict[str, Any], industry_keys: Iterable[str] | None, mechanism_keys: Iterable[str] | None,
    knowledge_dir: str | Path | None,
) -> tuple[str, list[str], list[str], list[str], dict[str, Any] | None]:
    if isinstance(company, dict):
        company_id = str(company.get("company_id") or company.get("report_id") or company.get("ts_code") or "UNKNOWN")
        inferred_industries = company.get("industry_keys") or company.get("industries") or []
        inferred_mechanisms = company.get("mechanism_keys") or []
        inferred_archetypes = company.get("archetype_ids") or []
        metadata: dict[str, Any] | None = None
    else:
        possible_output = Path(str(company or "")).expanduser()
        if possible_output.is_dir():
            metadata = load_company_industry_metadata(possible_output, knowledge_dir=knowledge_dir)
            company_id = str(metadata["company_id"])
            inferred_industries = metadata["industry_keys"]
            inferred_mechanisms = metadata["mechanism_keys"]
            inferred_archetypes = metadata["archetype_ids"]
        else:
            company_id, inferred_industries, inferred_mechanisms, inferred_archetypes, metadata = str(company or "UNKNOWN"), [], [], [], None
    return (
        company_id,
        _as_strings(industry_keys if industry_keys is not None else inferred_industries),
        _as_strings(mechanism_keys if mechanism_keys is not None else inferred_mechanisms),
        _as_strings(inferred_archetypes),
        metadata,
    )


def build_company_industry_profile(
    company: str | dict[str, Any], *, industry_keys: Iterable[str] | None = None,
    mechanism_keys: Iterable[str] | None = None, knowledge_dir: str | Path | None = None,
    max_ready: int | None = None, max_corroborated: int = 0,
) -> dict[str, Any]:
    """Build a company-specific research profile from ready industry mechanisms."""
    company_id, industries, mechanisms, archetypes, source_metadata = _company_arguments(company, industry_keys, mechanism_keys, knowledge_dir)
    found_ready = (
        search_industry_knowledge(
            industry_keys=industries, mechanism_keys=mechanisms, archetype_ids=archetypes,
            statuses=["MECHANISM_READY"], knowledge_dir=knowledge_dir,
        )
        if industries or mechanisms or archetypes
        else {"results": [], "warnings": []}
    )
    found_corroborated = (
        search_industry_knowledge(
            industry_keys=industries, mechanism_keys=mechanisms, archetype_ids=archetypes,
            statuses=["CORROBORATED"], knowledge_dir=knowledge_dir,
        )
        if max_corroborated > 0 and (industries or mechanisms or archetypes)
        else {"results": [], "warnings": []}
    )
    ready = found_ready["results"][:max_ready] if max_ready is not None else found_ready["results"]
    corroborated = found_corroborated["results"][:max_corroborated] if max_corroborated > 0 else []
    required_fields = sorted({field for item in [*ready, *corroborated] for field in item.get("company_verification_fields") or []})
    warnings = list(found_ready["warnings"]) + list(found_corroborated["warnings"])
    if not industries and not mechanisms and not archetypes:
        warnings.append("company_industry_or_mechanism_keys_missing")
    if not ready:
        warnings.append("no_mechanism_ready_match")
    return {
        "schema_version": PROFILE_SCHEMA_VERSION, "company_id": company_id, "industry_keys": industries,
        "mechanism_keys": mechanisms, "archetype_ids": archetypes, "profile_role": "research_prompt_prior_only", "mechanisms": ready,
        "corroborated_mechanisms": corroborated, "source_metadata": source_metadata,
        "required_company_verification_fields": required_fields, "prohibited_uses": list(PROHIBITED_USES),
        "warnings": list(dict.fromkeys(warnings)),
    }


def read_industry_knowledge_context(
    company: str | dict[str, Any], *, industry_keys: Iterable[str] | None = None,
    mechanism_keys: Iterable[str] | None = None, knowledge_dir: str | Path | None = None,
    max_ready: int | None = None, max_corroborated: int = 0,
) -> dict[str, Any]:
    """Return the ready mechanisms as concrete company research questions."""
    profile = build_company_industry_profile(
        company, industry_keys=industry_keys, mechanism_keys=mechanism_keys, knowledge_dir=knowledge_dir,
        max_ready=max_ready, max_corroborated=max_corroborated,
    )
    questions: list[dict[str, Any]] = []
    for mechanism in profile["mechanisms"]:
        for field in mechanism.get("company_verification_fields") or []:
            questions.append({
                "mechanism_id": mechanism["mechanism_id"], "mechanism_key": mechanism["mechanism_key"],
                "field": field,
                "question": f"Use this company's direct OBS/DOC evidence to verify: {field}",
                "why_it_matters": mechanism["summary"],
            })
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION, "company_id": profile["company_id"], "profile": profile,
        "research_questions": questions,
        "usage_contract": {
            "can_generate_research_questions": True, "cannot_establish_company_fact": True,
            "cannot_supply_valuation_parameter": True, "cannot_supply_probability": True,
        },
        "warnings": profile["warnings"],
    }


def validate_industry_knowledge(knowledge_dir: str | Path | None = None) -> dict[str, Any]:
    """Validate policy, taxonomy, candidates and mechanisms as one library."""
    initialized = initialize_industry_knowledge(knowledge_dir)
    root, policy, taxonomy = Path(initialized["knowledge_dir"]), initialized["policy"], initialized["taxonomy"]
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        invalid.append("policy_schema_version_invalid")
    if policy.get("library_role") != "research_prompt_prior_only":
        invalid.append("policy_library_role_invalid")
    if not set(PROHIBITED_USES).issubset(set(_as_strings(policy.get("prohibited_uses")))):
        invalid.append("policy_prohibited_uses_incomplete")
    if taxonomy.get("schema_version") != TAXONOMY_SCHEMA_VERSION:
        invalid.append("taxonomy_schema_version_invalid")
    if not _taxonomy_keys(taxonomy, "industry_families") or not _taxonomy_keys(taxonomy, "mechanism_families"):
        incomplete.append("taxonomy_empty")
    candidates, candidate_errors = _list_objects(root / "candidates")
    mechanisms, mechanism_errors = _list_objects(root / "mechanisms")
    invalid.extend(candidate_errors + mechanism_errors)
    for candidate in candidates:
        result = validate_industry_insight_candidate(candidate, taxonomy=taxonomy)
        invalid.extend(f"{candidate.get('candidate_id')}:{item}" for item in result["invalid_findings"])
        incomplete.extend(f"{candidate.get('candidate_id')}:{item}" for item in result["incomplete_findings"])
        warnings.extend(f"{candidate.get('candidate_id')}:{item}" for item in result["warnings"])
    for mechanism in mechanisms:
        result = review_industry_mechanism(mechanism, knowledge_dir=root, persist=False)
        invalid.extend(f"{mechanism.get('mechanism_id')}:{item}" for item in result["validation"]["invalid_findings"])
        incomplete.extend(f"{mechanism.get('mechanism_id')}:{item}" for item in result["validation"]["incomplete_findings"])
        warnings.extend(f"{mechanism.get('mechanism_id')}:{item}" for item in result["validation"]["warnings"])
    ready = sum(1 for item in mechanisms if item.get("status") == "MECHANISM_READY")
    if not candidates:
        warnings.append("no_industry_insight_candidates")
    if not ready:
        warnings.append("no_mechanism_ready_cards")
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": "industry-knowledge-validation.v1", "state": state,
        "status": "FAIL" if state == "INVALID" else "PASS", "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)), "warnings": list(dict.fromkeys(warnings)),
        "summary": {"candidate_count": len(candidates), "mechanism_count": len(mechanisms), "mechanism_ready_count": ready},
        "knowledge_dir": str(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Turtle canonical industry mechanism knowledge base")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init"); init.add_argument("--knowledge-dir", default="")
    validate = sub.add_parser("validate"); validate.add_argument("--knowledge-dir", default="")
    search = sub.add_parser("search"); search.add_argument("--knowledge-dir", default=""); search.add_argument("--industry", action="append", default=[]); search.add_argument("--mechanism", action="append", default=[]); search.add_argument("--query", default=""); search.add_argument("--include-corroborated", action="store_true")
    profile = sub.add_parser("profile"); profile.add_argument("--knowledge-dir", default=""); profile.add_argument("--company", required=True); profile.add_argument("--industry", action="append", default=[]); profile.add_argument("--mechanism", action="append", default=[])
    args = parser.parse_args()
    root = args.knowledge_dir or None
    if args.command == "init":
        result = initialize_industry_knowledge(root)
    elif args.command == "validate":
        result = validate_industry_knowledge(root)
    elif args.command == "search":
        statuses = ["MECHANISM_READY", "CORROBORATED"] if args.include_corroborated else ["MECHANISM_READY"]
        result = search_industry_knowledge(args.query, industry_keys=args.industry, mechanism_keys=args.mechanism, statuses=statuses, knowledge_dir=root)
    else:
        result = read_industry_knowledge_context(args.company, industry_keys=args.industry, mechanism_keys=args.mechanism, knowledge_dir=root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get("state") == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
