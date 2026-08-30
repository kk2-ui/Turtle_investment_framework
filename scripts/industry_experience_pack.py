#!/usr/bin/env python3
"""Validate a versioned Industry Experience Pack without copying its facts.

The Pack is a release manifest over existing IndustryLearningBlock,
IndustryUnderwritingContext, mechanism, case, and feedback artifacts.  This
module validates references and derives the maximum maturity supported by the
manifest.  It does not acquire evidence, rewrite source objects, or form a
target-company judgment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.industry_underwriting_context import validate_industry_underwriting_context
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from industry_underwriting_context import validate_industry_underwriting_context


SCHEMA_VERSION = "industry-experience-pack.v1"
VALIDATION_SCHEMA_VERSION = "industry-experience-pack-validation.v1"
MATURITY_ORDER = ("DRAFT", "TRAINING_READY", "TRANSFER_CANDIDATE", "RELEASED")
SOURCE_KINDS = {
    "INDUSTRY_LEARNING_BLOCK",
    "INDUSTRY_UNDERWRITING_CONTEXT",
    "OFFICIAL_INDUSTRY_OBSERVATION",
    "INDUSTRY_MECHANISM",
    "WORKED_CASE",
    "NEAR_MISS_OR_FAILURE",
    "FEEDBACK_OR_REVIEW",
}
COMPANY_ROLES = {
    "CENTRAL",
    "HETEROGENEOUS",
    "FAILURE_OR_NEAR_MISS",
    "SHARED_SHOCK_DIVERGENCE",
}
ROOT_FIELDS = {
    "schema_version",
    "pack_id",
    "industry_id",
    "version",
    "state",
    "knowledge_cutoff_at",
    "source_objects",
    "current_synthesis",
    "role_coverage",
    "settlement_plan",
    "transfer_reviews",
    "next_sampling_decision",
    "revision",
    "boundary",
}
SOURCE_FIELDS = {
    "kind", "object_id", "ref", "available_at", "knowledge_role", "use_status",
}
KNOWLEDGE_ROLES = {
    "CUTOFF_SAFE_EVIDENCE",
    "CUTOFF_SAFE_PROJECTION",
    "TRAINING_MEMORY",
    "REPLAY_AUDIT_ONLY",
}
SYNTHESIS_FIELDS = {
    "central_industry_path",
    "strongest_rival",
    "profit_pool_transmission",
    "scope_conditions",
    "break_conditions",
    "source_refs",
    "evidence_ceiling",
}
ROLE_COVERAGE_FIELDS = {"company_paths", "structural_epochs", "shared_shock_comparisons"}
SETTLEMENT_FIELDS = {"industry_claims", "company_transmission_claims"}
COMPANY_PATH_FIELDS = {"company_id", "archetype_id", "roles", "source_refs"}
EPOCH_FIELDS = {"epoch_id", "cutoff_at", "source_refs"}
SHARED_SHOCK_FIELDS = {"shock", "company_ids", "discriminator", "source_refs"}
SETTLEMENT_CLAIM_FIELDS = {"claim_id", "claim", "measurement_sources", "unresolved_treatment"}
NEXT_SAMPLE_FIELDS = {
    "question",
    "discriminator",
    "if_central_supported",
    "if_rival_supported",
    "unaffected_claims",
    "candidate_company_or_epoch_refs",
}
REVISION_FIELDS = {"prior_pack_ref", "revision_class", "change_summary"}
BOUNDARY = {
    "creates_fact_store": False,
    "establishes_target_company_facts": False,
    "grants_valuation_or_investment_authority": False,
    "replay_proves_agent_capability": False,
}
_ROOT = Path(__file__).resolve().parents[1]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _instant(value: Any) -> datetime | None:
    candidate = _text(value)
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _closed(value: Any, expected: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not item:
        findings.append(path + ".must_be_object")
        return {}
    extra = sorted(set(item) - expected)
    missing = sorted(expected - set(item))
    if extra:
        findings.append(path + ".unexpected_fields:" + ",".join(extra))
    if missing:
        findings.append(path + ".missing_fields:" + ",".join(missing))
    return item


def _strings(value: Any) -> list[str]:
    return [_text(item) for item in _items(value) if _text(item)]


def _path(reference: Any, *, root: Path) -> Path | None:
    ref = _text(reference).split("#", 1)[0]
    if not ref or "://" in ref:
        return None
    candidate = Path(ref).expanduser()
    return candidate if candidate.is_absolute() else root / candidate


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return _mapping(value)


def _source_validation(
    sources: list[Any], *, root: Path, industry_id: str, cutoff: datetime | None,
    findings: list[str], gaps: list[str],
) -> tuple[set[str], set[str]]:
    object_ids: set[str] = set()
    kinds: set[str] = set()
    refs: set[str] = set()
    for index, raw in enumerate(sources):
        path = f"source_objects[{index}]"
        item = _closed(raw, SOURCE_FIELDS, path, findings)
        kind = item.get("kind")
        if kind not in SOURCE_KINDS:
            findings.append(path + ".kind_invalid")
        object_id = _text(item.get("object_id"))
        if not object_id or object_id in object_ids:
            findings.append(path + ".object_id_missing_or_duplicate")
        else:
            object_ids.add(object_id)
        ref = _text(item.get("ref"))
        if not ref or ref in refs:
            findings.append(path + ".ref_missing_or_duplicate")
            continue
        refs.add(ref)
        available = _instant(item.get("available_at"))
        if available is None:
            findings.append(path + ".available_at_invalid")
        knowledge_role = item.get("knowledge_role")
        if knowledge_role not in KNOWLEDGE_ROLES:
            findings.append(path + ".knowledge_role_invalid")
        elif knowledge_role in {"CUTOFF_SAFE_EVIDENCE", "CUTOFF_SAFE_PROJECTION"}:
            if cutoff is not None and available is not None and available > cutoff:
                findings.append(path + ".cutoff_safe_source_available_after_pack_cutoff")
        elif item.get("use_status") != "BOUNDARY_ONLY":
            findings.append(path + ".non_cutoff_source_must_be_boundary_only")
        if (
            kind in SOURCE_KINDS
            and knowledge_role in {"CUTOFF_SAFE_EVIDENCE", "CUTOFF_SAFE_PROJECTION"}
            and item.get("use_status") == "INCLUDED"
        ):
            kinds.add(str(kind))
        if item.get("use_status") not in {"INCLUDED", "BOUNDARY_ONLY", "SUPERSEDED"}:
            findings.append(path + ".use_status_invalid")
        source_path = _path(ref, root=root)
        if source_path is None or not source_path.is_file():
            findings.append(path + ".ref_not_resolvable")
            continue
        if kind not in {"INDUSTRY_LEARNING_BLOCK", "INDUSTRY_UNDERWRITING_CONTEXT"}:
            continue
        payload = _read_json(source_path)
        if not payload:
            findings.append(path + ".json_source_invalid")
            continue
        if kind == "INDUSTRY_LEARNING_BLOCK":
            if payload.get("schema_version") not in {
                "industry-learning-block.v1", "industry-learning-block.v2",
            }:
                findings.append(path + ".learning_block_schema_invalid")
            if payload.get("industry_id") != industry_id:
                findings.append(path + ".learning_block_industry_mismatch")
            block_cutoffs = [_instant(item) for item in _items(payload.get("cutoffs"))]
            if cutoff is not None and any(item and item > cutoff for item in block_cutoffs):
                findings.append(path + ".learning_block_after_pack_cutoff")
        elif kind == "INDUSTRY_UNDERWRITING_CONTEXT":
            result = validate_industry_underwriting_context(payload)
            if result["state"] != "REVIEWABLE":
                findings.append(path + ".industry_context_invalid")
            context_cutoff = _instant(_mapping(payload.get("knowledge_time")).get("cutoff_at"))
            if cutoff is not None and context_cutoff is not None and context_cutoff > cutoff:
                findings.append(path + ".industry_context_after_pack_cutoff")
            if payload.get("context_status") == "BOUNDED":
                gaps.append("industry_context_is_bounded")
    return kinds, refs


def _training_ready_gaps(value: dict[str, Any], kinds: set[str]) -> list[str]:
    gaps: list[str] = []
    if "INDUSTRY_LEARNING_BLOCK" not in kinds:
        gaps.append("learning_block_missing")
    if "INDUSTRY_UNDERWRITING_CONTEXT" not in kinds:
        gaps.append("industry_context_missing")
    if "OFFICIAL_INDUSTRY_OBSERVATION" not in kinds:
        gaps.append("official_industry_observation_missing")

    synthesis = _mapping(value.get("current_synthesis"))
    for field in ("central_industry_path", "strongest_rival", "profit_pool_transmission"):
        if not _text(synthesis.get(field)):
            gaps.append("current_synthesis." + field + "_missing")
    if not _strings(synthesis.get("break_conditions")):
        gaps.append("current_synthesis.break_conditions_missing")

    coverage = _mapping(value.get("role_coverage"))
    company_paths = [_mapping(item) for item in _items(coverage.get("company_paths"))]
    company_ids = {_text(item.get("company_id")) for item in company_paths if _text(item.get("company_id"))}
    roles = {
        role
        for item in company_paths
        for role in _strings(item.get("roles"))
        if role in COMPANY_ROLES
    }
    if len(company_ids) < 4:
        gaps.append("four_independent_company_paths_required")
    missing_roles = sorted(COMPANY_ROLES - roles)
    if missing_roles:
        gaps.append("company_roles_missing:" + ",".join(missing_roles))
    epochs = [_mapping(item) for item in _items(coverage.get("structural_epochs"))]
    if len({_text(item.get("epoch_id")) for item in epochs if _text(item.get("epoch_id"))}) < 2:
        gaps.append("two_structural_epochs_required")
    if not _items(coverage.get("shared_shock_comparisons")):
        gaps.append("shared_shock_comparison_missing")

    settlement = _mapping(value.get("settlement_plan"))
    if not _items(settlement.get("industry_claims")):
        gaps.append("industry_settlement_claim_missing")
    if not _items(settlement.get("company_transmission_claims")):
        gaps.append("company_transmission_settlement_claim_missing")

    next_sample = _mapping(value.get("next_sampling_decision"))
    for field in NEXT_SAMPLE_FIELDS:
        field_value = next_sample.get(field)
        if field in {"unaffected_claims", "candidate_company_or_epoch_refs"}:
            if not _strings(field_value):
                gaps.append("next_sampling_decision." + field + "_missing")
        elif not _text(field_value):
            gaps.append("next_sampling_decision." + field + "_missing")
    return gaps


def _derived_state(value: dict[str, Any], training_gaps: list[str]) -> str:
    if training_gaps:
        return "DRAFT"
    reviews = [_mapping(item) for item in _items(value.get("transfer_reviews"))]
    material_axes = {
        _text(item.get("axis"))
        for item in reviews
        if item.get("independent") is True and item.get("verdict") == "MATERIAL_UTILITY"
    }
    if {"COMPANY_HOLDOUT", "TIME_HOLDOUT"} <= material_axes:
        return "RELEASED"
    if material_axes:
        return "TRANSFER_CANDIDATE"
    return "TRAINING_READY"


def validate_industry_experience_pack(payload: Any, *, root: str | Path | None = None) -> dict[str, Any]:
    """Return structural validity, evidence-derived maturity, and actionable gaps."""
    value = _mapping(payload)
    findings: list[str] = []
    gaps: list[str] = []
    if not value:
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "state": "INVALID",
            "declared_state": None,
            "derived_state": "DRAFT",
            "findings": ["pack.must_be_object"],
            "training_readiness_gaps": [],
        }
    _closed(value, ROOT_FIELDS, "pack", findings)
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("pack.schema_version_invalid")
    for field in ("pack_id", "industry_id"):
        if not _text(value.get(field)):
            findings.append("pack." + field + "_missing")
    if not isinstance(value.get("version"), int) or value.get("version", 0) < 1:
        findings.append("pack.version_invalid")
    declared_state = value.get("state")
    if declared_state not in MATURITY_ORDER:
        findings.append("pack.state_invalid")
    cutoff = _instant(value.get("knowledge_cutoff_at"))
    if cutoff is None:
        findings.append("pack.knowledge_cutoff_at_invalid")

    source_root = Path(root).resolve() if root is not None else _ROOT
    sources = _items(value.get("source_objects"))
    if not sources:
        findings.append("pack.source_objects_missing")
    kinds, source_refs = _source_validation(
        sources,
        root=source_root,
        industry_id=_text(value.get("industry_id")),
        cutoff=cutoff,
        findings=findings,
        gaps=gaps,
    )

    synthesis = _closed(value.get("current_synthesis"), SYNTHESIS_FIELDS, "current_synthesis", findings)
    for field in ("central_industry_path", "strongest_rival", "profit_pool_transmission"):
        if not _text(synthesis.get(field)):
            findings.append("current_synthesis." + field + "_missing")
    for field in ("scope_conditions", "break_conditions"):
        if not _strings(synthesis.get(field)):
            findings.append("current_synthesis." + field + "_missing")
    if synthesis.get("evidence_ceiling") not in {
        "RESEARCH_AGENDA", "TEACHING_ONLY", "TRAINING_CONTEXT", "TRANSFER_CANDIDATE", "RELEASED",
    }:
        findings.append("current_synthesis.evidence_ceiling_invalid")
    synthesis_refs = _strings(synthesis.get("source_refs"))
    if not synthesis_refs:
        findings.append("current_synthesis.source_refs_missing")
    for ref in synthesis_refs:
        if ref not in source_refs:
            findings.append("current_synthesis.source_ref_not_bound:" + ref)

    coverage = _closed(value.get("role_coverage"), ROLE_COVERAGE_FIELDS, "role_coverage", findings)
    for index, raw in enumerate(_items(coverage.get("company_paths"))):
        item = _closed(raw, COMPANY_PATH_FIELDS, f"role_coverage.company_paths[{index}]", findings)
        if not _text(item.get("company_id")) or not _text(item.get("archetype_id")):
            findings.append(f"role_coverage.company_paths[{index}].identity_missing")
        roles = _strings(item.get("roles"))
        if not roles or not set(roles) <= COMPANY_ROLES:
            findings.append(f"role_coverage.company_paths[{index}].roles_invalid")
        item_refs = _strings(item.get("source_refs"))
        if not item_refs:
            findings.append(f"role_coverage.company_paths[{index}].source_refs_missing")
        for ref in item_refs:
            if ref not in source_refs:
                findings.append(f"role_coverage.company_paths[{index}].source_ref_not_bound:" + ref)
    for index, raw in enumerate(_items(coverage.get("structural_epochs"))):
        item = _closed(raw, EPOCH_FIELDS, f"role_coverage.structural_epochs[{index}]", findings)
        if not _text(item.get("epoch_id")) or _instant(item.get("cutoff_at")) is None:
            findings.append(f"role_coverage.structural_epochs[{index}].identity_or_cutoff_invalid")
        epoch_refs = _strings(item.get("source_refs"))
        if not epoch_refs:
            findings.append(f"role_coverage.structural_epochs[{index}].source_refs_missing")
        for ref in epoch_refs:
            if ref not in source_refs:
                findings.append(f"role_coverage.structural_epochs[{index}].source_ref_not_bound:" + ref)
    for index, raw in enumerate(_items(coverage.get("shared_shock_comparisons"))):
        item = _closed(
            raw, SHARED_SHOCK_FIELDS,
            f"role_coverage.shared_shock_comparisons[{index}]", findings,
        )
        if len(set(_strings(item.get("company_ids")))) < 2:
            findings.append(f"role_coverage.shared_shock_comparisons[{index}].requires_two_companies")
        if not _text(item.get("shock")) or not _text(item.get("discriminator")):
            findings.append(f"role_coverage.shared_shock_comparisons[{index}].judgment_missing")
        shock_refs = _strings(item.get("source_refs"))
        if not shock_refs:
            findings.append(f"role_coverage.shared_shock_comparisons[{index}].source_refs_missing")
        for ref in shock_refs:
            if ref not in source_refs:
                findings.append(f"role_coverage.shared_shock_comparisons[{index}].source_ref_not_bound:" + ref)

    settlement = _closed(value.get("settlement_plan"), SETTLEMENT_FIELDS, "settlement_plan", findings)
    claim_ids: set[str] = set()
    for lane in ("industry_claims", "company_transmission_claims"):
        for index, raw in enumerate(_items(settlement.get(lane))):
            path = f"settlement_plan.{lane}[{index}]"
            item = _closed(raw, SETTLEMENT_CLAIM_FIELDS, path, findings)
            claim_id = _text(item.get("claim_id"))
            if not claim_id or claim_id in claim_ids:
                findings.append(path + ".claim_id_missing_or_duplicate")
            else:
                claim_ids.add(claim_id)
            for field in ("claim", "unresolved_treatment"):
                if not _text(item.get(field)):
                    findings.append(path + "." + field + "_missing")
            if not _strings(item.get("measurement_sources")):
                findings.append(path + ".measurement_sources_missing")
    review_ids: set[str] = set()
    for index, raw in enumerate(_items(value.get("transfer_reviews"))):
        path = f"transfer_reviews[{index}]"
        item = _closed(
            raw, {"review_id", "axis", "verdict", "independent", "ref"}, path, findings,
        )
        review_id = _text(item.get("review_id"))
        if not review_id or review_id in review_ids:
            findings.append(path + ".review_id_missing_or_duplicate")
        else:
            review_ids.add(review_id)
        if item.get("axis") not in {"COMPANY_HOLDOUT", "TIME_HOLDOUT"}:
            findings.append(path + ".axis_invalid")
        if item.get("verdict") not in {
            "MATERIAL_UTILITY", "NO_MATERIAL_UTILITY", "WORSE", "INCONCLUSIVE_DATA",
        }:
            findings.append(path + ".verdict_invalid")
        if not isinstance(item.get("independent"), bool):
            findings.append(path + ".independent_must_be_boolean")
        review_path = _path(item.get("ref"), root=source_root)
        if review_path is None or not review_path.is_file():
            findings.append(path + ".ref_not_resolvable")
    next_sample = _closed(
        value.get("next_sampling_decision"), NEXT_SAMPLE_FIELDS,
        "next_sampling_decision", findings,
    )
    for field in NEXT_SAMPLE_FIELDS:
        if field in {"unaffected_claims", "candidate_company_or_epoch_refs"}:
            if not _strings(next_sample.get(field)):
                findings.append("next_sampling_decision." + field + "_missing")
        elif not _text(next_sample.get(field)):
            findings.append("next_sampling_decision." + field + "_missing")
    revision = _closed(value.get("revision"), REVISION_FIELDS, "revision", findings)
    if revision.get("revision_class") not in {
        "INITIAL", "SUPPORT", "NARROW", "BREAK", "NEW_ARCHETYPE", "ACQUISITION_GAP",
    }:
        findings.append("revision.revision_class_invalid")
    if not _text(revision.get("change_summary")):
        findings.append("revision.change_summary_missing")
    if _mapping(value.get("boundary")) != BOUNDARY:
        findings.append("pack.boundary_must_preserve_non_authoritative_manifest_role")

    training_gaps = list(dict.fromkeys([*gaps, *_training_ready_gaps(value, kinds)]))
    derived_state = _derived_state(value, training_gaps)
    if declared_state in MATURITY_ORDER and MATURITY_ORDER.index(declared_state) > MATURITY_ORDER.index(derived_state):
        findings.append("pack.declared_state_exceeds_evidence:" + derived_state)

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "declared_state": declared_state,
        "derived_state": derived_state,
        "findings": list(dict.fromkeys(findings)),
        "training_readiness_gaps": training_gaps,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a versioned Industry Experience Pack")
    parser.add_argument("pack", help="Industry Experience Pack JSON file")
    parser.add_argument("--root", default=str(_ROOT), help="Repository root for resolving refs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    path = Path(args.pack).expanduser()
    payload = _read_json(path)
    result = validate_industry_experience_pack(payload, root=args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "REVIEWABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
