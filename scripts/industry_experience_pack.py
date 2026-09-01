#!/usr/bin/env python3
"""Validate a versioned Industry Experience Pack without copying its facts.

The Pack is a release manifest over existing IndustryLearningBlock,
IndustryUnderwritingContext, mechanism, case, and feedback artifacts.  This
module validates references and derives the maximum maturity supported by the
manifest.  It can also compile a compact, company-fact-free training memory
from a TRAINING_READY Pack and a target-cutoff Context.  It does not acquire
evidence, rewrite source objects, or form a target-company judgment.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping

try:
    from scripts.industry_underwriting_context import validate_industry_underwriting_context
    from scripts.industry_context_acquisition import (
        validate_official_context_observation_ledger,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from industry_underwriting_context import validate_industry_underwriting_context
    from industry_context_acquisition import validate_official_context_observation_ledger


SCHEMA_VERSION = "industry-experience-pack.v1"
VALIDATION_SCHEMA_VERSION = "industry-experience-pack-validation.v1"
SHARED_SHOCK_PROJECTION_SCHEMA_VERSION = "industry-shared-shock-company-projection.v1"
ISSUER_IDENTITY_CATALOG_SCHEMA_VERSION = "issuer-identity-catalog.v1"
COMPACT_MEMORY_VERSION = "compact-industry-decision-memory.v1"
MATURITY_ORDER = ("DRAFT", "TRAINING_READY", "TRANSFER_CANDIDATE", "RELEASED")
SOURCE_KINDS = {
    "INDUSTRY_LEARNING_BLOCK",
    "INDUSTRY_UNDERWRITING_CONTEXT",
    "OFFICIAL_INDUSTRY_OBSERVATION",
    "INDUSTRY_MECHANISM",
    "WORKED_CASE",
    "NEAR_MISS_OR_FAILURE",
    "FEEDBACK_OR_REVIEW",
    "ISSUER_IDENTITY_CATALOG",
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
ISSUER_IDENTITY_FIELDS = {
    "company_id",
    "security_code",
    "issuer_legal_name",
    "exact_name_quote",
    "source_id",
    "publication_date",
    "pdf_page_ref",
}
ISSUER_IDENTITY_CATALOG_FIELDS = {
    "schema_version", "catalog_id", "industry_id", "cutoff_at", "entries",
}
ISSUER_IDENTITY_CATALOG_ENTRY_FIELDS = ISSUER_IDENTITY_FIELDS | {"aliases"}
_IDENTITY_TOKEN = re.compile(r"\[\[(CN:\d{6})\|([^\[\]|]+)\]\]")
_SAFE_VERIFICATION_FIELD = re.compile(r"^[A-Za-z0-9_:\-]+$")
_ROOT = Path(__file__).resolve().parents[1]

_VERIFICATION_QUESTION_TEMPLATES = {
    "regional_price_cost_and_volume_transmission": (
        "目标公司所在 delivered market 的实现价格、销量、单位成本与利用率，"
        "是否支持行业主路径，而不是只跟随全国均值？"
    ),
    "cash_conversion_and_financing_resilience": (
        "行业利润池改善能否穿过营运资本、维护资本、受限现金与债务责任，"
        "转化为普通股股东可得的 owner cash？"
    ),
    "mature_core_vs_conditional_growth_cohorts": (
        "成熟核心、已投产 cohort、在建或终止项目是否按责任边界分开，"
        "且只有经过客户吸收、利用率、单位经济和现金回收验证的部分进入基础经济？"
    ),
    "consolidation_perimeter_continuity": (
        "并购、重组、控制权或会计口径变化是否已经建立同责任边界的 perimeter bridge，"
        "避免把合并范围变化写成经营改善？"
    ),
}

_FALLBACK_VERIFICATION_QUESTIONS = [
    "目标公司的客户、区域 delivered market 和竞争位置，是否真的暴露于行业主路径？",
    "哪些责任匹配的价格、数量、成本、份额或资本机制把行业利润池传导至正常盈利？",
    "再投资、营运资本或监管资本、融资与分配责任是否允许盈利转化为 owner cash？",
    "哪个责任单元承担下行，使行业反转能够进入永久损失和价值路线？",
]


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


def _nested_ref_path(reference: Any, *, root: Path, source_path: Path) -> Path | None:
    candidate = _path(reference, root=root)
    if candidate is None or candidate.is_file() or Path(_text(reference)).is_absolute():
        return candidate
    return source_path.parent / Path(_text(reference).split("#", 1)[0]).expanduser()


def _validate_issuer_identity_catalog(
    payload: dict[str, Any], *, industry_id: str, cutoff: datetime | None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Bind issuer names to a separately materialized official-cover catalog."""
    findings: list[str] = []
    item = _closed(payload, ISSUER_IDENTITY_CATALOG_FIELDS, "issuer_identity_catalog", findings)
    if item.get("schema_version") != ISSUER_IDENTITY_CATALOG_SCHEMA_VERSION:
        findings.append("issuer_identity_catalog.schema_version_invalid")
    if not _text(item.get("catalog_id")):
        findings.append("issuer_identity_catalog.catalog_id_missing")
    if item.get("industry_id") != industry_id:
        findings.append("issuer_identity_catalog.industry_id_mismatch")
    catalog_cutoff = _instant(item.get("cutoff_at"))
    if catalog_cutoff is None:
        findings.append("issuer_identity_catalog.cutoff_invalid")
    elif cutoff is not None and catalog_cutoff > cutoff:
        findings.append("issuer_identity_catalog.after_pack_cutoff")
    bindings: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_items(item.get("entries"))):
        path = f"issuer_identity_catalog.entries[{index}]"
        entry = _closed(raw, ISSUER_IDENTITY_CATALOG_ENTRY_FIELDS, path, findings)
        company_id = _text(entry.get("company_id"))
        security_code = _text(entry.get("security_code"))
        expected_code = company_id.removeprefix("CN:") if company_id.startswith("CN:") else ""
        source_id = _text(entry.get("source_id"))
        source_parts = source_id.split(":")
        source_code = source_parts[1] if len(source_parts) >= 2 and source_parts[0] == "CNINFO" else ""
        if not company_id or company_id in bindings:
            findings.append(path + ".company_id_missing_or_duplicate")
        if not expected_code or security_code != expected_code:
            findings.append(path + ".security_code_mismatch")
        if not source_code or source_code != security_code:
            findings.append(path + ".source_code_mismatch")
        legal_name = _text(entry.get("issuer_legal_name"))
        if not legal_name or _text(entry.get("exact_name_quote")) != legal_name:
            findings.append(path + ".legal_name_quote_mismatch")
        aliases = _strings(entry.get("aliases"))
        if not aliases or len(aliases) != len(set(aliases)):
            findings.append(path + ".aliases_missing_or_duplicate")
        if any(alias == legal_name for alias in aliases):
            findings.append(path + ".aliases_must_be_short_names")
        if not _text(entry.get("pdf_page_ref")):
            findings.append(path + ".pdf_page_ref_missing")
        published = _text(entry.get("publication_date"))
        try:
            published_date = date.fromisoformat(published)
        except ValueError:
            findings.append(path + ".publication_date_invalid")
        else:
            if cutoff is not None and published_date > cutoff.date():
                findings.append(path + ".published_after_pack_cutoff")
        if company_id and company_id not in bindings:
            bindings[company_id] = entry
    if not bindings:
        findings.append("issuer_identity_catalog.entries_missing")
    return bindings, findings


def _worked_case_company_ids(
    payload: dict[str, Any], *, cutoff: datetime | None, require_issuer_identity: bool = False,
    issuer_identity_catalog: Mapping[str, dict[str, Any]] | None = None,
) -> tuple[set[str], list[str]]:
    """Admit company responses only from a cutoff-safe multi-company case."""
    findings: list[str] = []
    if payload.get("schema_version") not in {
        "turtle-pit-company-forecast-submission.v1",
        SHARED_SHOCK_PROJECTION_SCHEMA_VERSION,
    }:
        findings.append("worked_case_schema_invalid")
    case_cutoff = _instant(payload.get("cutoff_at"))
    if case_cutoff is None:
        findings.append("worked_case_cutoff_invalid")
    elif cutoff is not None and case_cutoff > cutoff:
        findings.append("worked_case_after_pack_cutoff")
    companies = [_mapping(item) for item in _items(payload.get("companies"))]
    if not companies:
        findings.append("worked_case_companies_missing")
    company_ids: set[str] = set()
    cutoff_date = cutoff.date() if cutoff is not None else None
    for index, company in enumerate(companies):
        company_id = _text(company.get("company_id"))
        prefix = f"worked_case_companies[{index}]"
        if not company_id or company_id in company_ids:
            findings.append(prefix + ".company_id_missing_or_duplicate")
        else:
            company_ids.add(company_id)
        states = [_mapping(item) for item in _items(company.get("verified_cutoff_state"))]
        if not states:
            findings.append(prefix + ".verified_cutoff_state_missing")
            continue
        evidence_source_ids: set[str] = set()
        for state_index, state in enumerate(states):
            state_prefix = f"{prefix}.verified_cutoff_state[{state_index}]"
            if not _text(state.get("statement")):
                findings.append(state_prefix + ".statement_missing")
            evidence = [_mapping(item) for item in _items(state.get("evidence"))]
            if not evidence:
                findings.append(state_prefix + ".evidence_missing")
                continue
            for evidence_index, item in enumerate(evidence):
                evidence_prefix = f"{state_prefix}.evidence[{evidence_index}]"
                if not _text(item.get("source_id")):
                    findings.append(evidence_prefix + ".source_id_missing")
                else:
                    evidence_source_ids.add(_text(item.get("source_id")))
                if not (_text(item.get("pdf_page_ref")) or _text(item.get("field_ref"))):
                    findings.append(evidence_prefix + ".locator_missing")
                published = _text(item.get("publication_date"))
                try:
                    published_date = date.fromisoformat(published)
                except ValueError:
                    findings.append(evidence_prefix + ".publication_date_invalid")
                else:
                    if cutoff_date is not None and published_date > cutoff_date:
                        findings.append(evidence_prefix + ".published_after_pack_cutoff")
        identity = _mapping(company.get("issuer_identity"))
        if require_issuer_identity and not identity:
            findings.append(prefix + ".issuer_identity_missing")
            continue
        if identity:
            _closed(identity, ISSUER_IDENTITY_FIELDS, prefix + ".issuer_identity", findings)
            security_code = _text(identity.get("security_code"))
            expected_code = company_id.removeprefix("CN:") if company_id.startswith("CN:") else ""
            identity_source_id = _text(identity.get("source_id"))
            source_parts = identity_source_id.split(":")
            source_code = source_parts[1] if len(source_parts) >= 2 and source_parts[0] == "CNINFO" else ""
            if identity.get("company_id") != company_id:
                findings.append(prefix + ".issuer_identity.company_id_mismatch")
            if not expected_code or security_code != expected_code:
                findings.append(prefix + ".issuer_identity.security_code_mismatch")
            if not source_code or source_code != security_code:
                findings.append(prefix + ".issuer_identity.source_code_mismatch")
            if identity_source_id not in evidence_source_ids:
                findings.append(prefix + ".issuer_identity.source_not_in_verified_state")
            issuer_legal_name = _text(identity.get("issuer_legal_name"))
            if not issuer_legal_name:
                findings.append(prefix + ".issuer_identity.issuer_legal_name_missing")
            if _text(identity.get("exact_name_quote")) != issuer_legal_name:
                findings.append(prefix + ".issuer_identity.exact_name_quote_mismatch")
            if not _text(identity.get("pdf_page_ref")):
                findings.append(prefix + ".issuer_identity.pdf_page_ref_missing")
            identity_published = _text(identity.get("publication_date"))
            try:
                identity_published_date = date.fromisoformat(identity_published)
            except ValueError:
                findings.append(prefix + ".issuer_identity.publication_date_invalid")
            else:
                if cutoff_date is not None and identity_published_date > cutoff_date:
                    findings.append(prefix + ".issuer_identity.published_after_pack_cutoff")
            catalog_identity = (issuer_identity_catalog or {}).get(company_id)
            if require_issuer_identity and not catalog_identity:
                findings.append(prefix + ".issuer_identity.catalog_binding_missing")
            elif catalog_identity:
                for field in ISSUER_IDENTITY_FIELDS:
                    if identity.get(field) != catalog_identity.get(field):
                        findings.append(prefix + ".issuer_identity.catalog_mismatch:" + field)
    return company_ids, findings


def _source_validation(
    sources: list[Any], *, root: Path, industry_id: str, cutoff: datetime | None,
    findings: list[str], gaps: list[str], require_issuer_identity: bool = False,
) -> tuple[
    set[str], set[str], dict[str, str], dict[str, set[str]], dict[str, dict[str, Any]],
]:
    object_ids: set[str] = set()
    kinds: set[str] = set()
    refs: set[str] = set()
    admitted_source_kinds: dict[str, str] = {}
    admitted_source_company_ids: dict[str, set[str]] = {}
    catalog_results: dict[str, tuple[dict[str, dict[str, Any]], list[str]]] = {}
    issuer_identity_catalog: dict[str, dict[str, Any]] = {}
    for raw in sources:
        item = _mapping(raw)
        if item.get("kind") != "ISSUER_IDENTITY_CATALOG":
            continue
        ref = _text(item.get("ref"))
        source_path = _path(ref, root=root)
        if not ref or source_path is None or not source_path.is_file():
            continue
        bindings, catalog_findings = _validate_issuer_identity_catalog(
            _read_json(source_path), industry_id=industry_id, cutoff=cutoff,
        )
        catalog_results[ref] = (bindings, catalog_findings)
        for company_id, binding in bindings.items():
            if company_id in issuer_identity_catalog and issuer_identity_catalog[company_id] != binding:
                catalog_findings.append("issuer_identity_catalog.conflicting_company_binding:" + company_id)
            else:
                issuer_identity_catalog[company_id] = binding
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
        maturity_candidate = (
            kind in SOURCE_KINDS
            and knowledge_role in {"CUTOFF_SAFE_EVIDENCE", "CUTOFF_SAFE_PROJECTION"}
            and item.get("use_status") == "INCLUDED"
            and available is not None
            and (cutoff is None or available <= cutoff)
        )
        if item.get("use_status") not in {"INCLUDED", "BOUNDARY_ONLY", "SUPERSEDED"}:
            findings.append(path + ".use_status_invalid")
        source_path = _path(ref, root=root)
        if source_path is None or not source_path.is_file():
            findings.append(path + ".ref_not_resolvable")
            continue
        payload: dict[str, Any] = {}
        company_ids_for_source: set[str] = set()
        if kind in {
            "INDUSTRY_LEARNING_BLOCK",
            "INDUSTRY_UNDERWRITING_CONTEXT",
            "OFFICIAL_INDUSTRY_OBSERVATION",
        } or (kind == "WORKED_CASE" and maturity_candidate):
            payload = _read_json(source_path)
            if not payload:
                findings.append(path + ".json_source_invalid")
                maturity_candidate = False
        if kind == "INDUSTRY_LEARNING_BLOCK":
            if payload.get("schema_version") not in {
                "industry-learning-block.v1", "industry-learning-block.v2",
            }:
                findings.append(path + ".learning_block_schema_invalid")
                maturity_candidate = False
            if payload.get("industry_id") != industry_id:
                findings.append(path + ".learning_block_industry_mismatch")
                maturity_candidate = False
            block_cutoffs = [_instant(item) for item in _items(payload.get("cutoffs"))]
            if cutoff is not None and any(item and item > cutoff for item in block_cutoffs):
                findings.append(path + ".learning_block_after_pack_cutoff")
                maturity_candidate = False
        elif kind == "INDUSTRY_UNDERWRITING_CONTEXT":
            result = validate_industry_underwriting_context(payload)
            if result["state"] != "REVIEWABLE":
                findings.append(path + ".industry_context_invalid")
                maturity_candidate = False
            context_cutoff = _instant(_mapping(payload.get("knowledge_time")).get("cutoff_at"))
            if cutoff is not None and context_cutoff is not None and context_cutoff > cutoff:
                findings.append(path + ".industry_context_after_pack_cutoff")
                maturity_candidate = False
            if payload.get("context_status") == "BOUNDED":
                gaps.append("industry_context_is_bounded")
        elif kind == "OFFICIAL_INDUSTRY_OBSERVATION":
            if payload.get("industry_id") != industry_id:
                findings.append(path + ".official_observation_industry_mismatch")
                maturity_candidate = False
            ledger_cutoff = _instant(payload.get("cutoff_at"))
            if ledger_cutoff is None:
                findings.append(path + ".official_observation_cutoff_invalid")
                maturity_candidate = False
            elif cutoff is not None and ledger_cutoff > cutoff:
                findings.append(path + ".official_observation_after_pack_cutoff")
                maturity_candidate = False
            package_path = _nested_ref_path(
                payload.get("source_package_ref"), root=root, source_path=source_path,
            )
            if package_path is None or not package_path.is_file():
                findings.append(path + ".official_source_package_not_resolvable")
                maturity_candidate = False
            else:
                package = _read_json(package_path)
                result = validate_official_context_observation_ledger(
                    payload,
                    package,
                    package_root=package_path.parent,
                )
                if result["state"] != "REVIEWABLE_CONTEXT_ONLY":
                    findings.append(
                        path
                        + ".official_observation_invalid:"
                        + ",".join([
                            *result["invalid_findings"],
                            *result["incomplete_findings"],
                        ])
                    )
                    maturity_candidate = False
        elif kind == "WORKED_CASE" and maturity_candidate:
            company_ids_for_source, worked_findings = _worked_case_company_ids(
                payload,
                cutoff=cutoff,
                require_issuer_identity=require_issuer_identity,
                issuer_identity_catalog=issuer_identity_catalog,
            )
            if worked_findings:
                findings.extend(path + "." + item for item in worked_findings)
                maturity_candidate = False
        elif kind == "ISSUER_IDENTITY_CATALOG":
            bindings, catalog_findings = catalog_results.get(ref, ({}, ["catalog_not_prevalidated"]))
            if catalog_findings:
                findings.extend(path + "." + item for item in catalog_findings)
                maturity_candidate = False
            company_ids_for_source = set(bindings)
        if maturity_candidate:
            kinds.add(str(kind))
            admitted_source_kinds[ref] = str(kind)
            if kind == "INDUSTRY_LEARNING_BLOCK":
                company_records = [
                    *_items(payload.get("company_archetype_map")),
                    *_items(payload.get("members")),
                ]
                admitted_source_company_ids[ref] = {
                    _text(_mapping(record).get("company_id") or _mapping(record).get("issuer_id"))
                    for record in company_records
                    if _text(_mapping(record).get("company_id") or _mapping(record).get("issuer_id"))
                }
            elif kind == "WORKED_CASE":
                admitted_source_company_ids[ref] = company_ids_for_source
    if require_issuer_identity and not issuer_identity_catalog:
        findings.append("pack.issuer_identity_catalog_required")
    return (
        kinds, refs, admitted_source_kinds, admitted_source_company_ids,
        issuer_identity_catalog,
    )


def _training_ready_gaps(
    value: dict[str, Any],
    kinds: set[str],
    admitted_source_kinds: Mapping[str, str],
    admitted_source_company_ids: Mapping[str, set[str]],
) -> list[str]:
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
    shared_shocks = [_mapping(item) for item in _items(coverage.get("shared_shock_comparisons"))]
    if not shared_shocks:
        gaps.append("shared_shock_comparison_missing")
    else:
        eligible_shared_shock = False
        for item in shared_shocks:
            shock_company_ids = set(_strings(item.get("company_ids")))
            shock_refs = _strings(item.get("source_refs"))
            shock_kinds = {admitted_source_kinds.get(ref) for ref in shock_refs}
            worked_case_company_ids = {
                company_id
                for ref in shock_refs
                if admitted_source_kinds.get(ref) == "WORKED_CASE"
                for company_id in admitted_source_company_ids.get(ref, set())
            }
            company_evidence_bound = shock_company_ids <= worked_case_company_ids
            if (
                len(shock_company_ids) >= 4
                and shock_company_ids <= company_ids
                and "OFFICIAL_INDUSTRY_OBSERVATION" in shock_kinds
                and company_evidence_bound
            ):
                eligible_shared_shock = True
                break
        if not eligible_shared_shock:
            gaps.append("shared_shock_evidence_bundle_incomplete")

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


def _iter_text(value: Any, path: str = "") -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    if isinstance(value, str):
        texts.append((path, value))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            texts.extend(_iter_text(item, f"{path}[{index}]"))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            texts.extend(_iter_text(item, f"{path}.{key}" if path else str(key)))
    return texts


def _validate_active_issuer_mentions(
    value: dict[str, Any],
    catalog: Mapping[str, dict[str, Any]],
    findings: list[str],
) -> None:
    """Require active issuer prose to use catalog-bound ``[[id|name]]`` tokens."""
    active = {
        "current_synthesis": value.get("current_synthesis"),
        "shared_shock_comparisons": _mapping(value.get("role_coverage")).get(
            "shared_shock_comparisons"
        ),
        "settlement_plan": value.get("settlement_plan"),
        "next_sampling_decision": value.get("next_sampling_decision"),
    }
    labels: list[tuple[str, str]] = []
    for company_id, identity in catalog.items():
        legal_name = _text(identity.get("issuer_legal_name"))
        if legal_name:
            labels.append((legal_name, company_id))
        labels.extend((alias, company_id) for alias in _strings(identity.get("aliases")))
    labels.sort(key=lambda item: len(item[0]), reverse=True)
    for path, text in _iter_text(active):
        tokens = list(_IDENTITY_TOKEN.finditer(text))
        for match in tokens:
            company_id, display_name = match.groups()
            identity = catalog.get(company_id)
            permitted_names = {
                _text(_mapping(identity).get("issuer_legal_name")),
                *_strings(_mapping(identity).get("aliases")),
            }
            permitted_names.discard("")
            if not identity or display_name not in permitted_names:
                findings.append(path + ".issuer_identity_token_mismatch:" + company_id)
        unbound_text = _IDENTITY_TOKEN.sub("", text)
        for label, company_id in labels:
            if label and label in unbound_text:
                findings.append(path + ".unbound_issuer_name:" + company_id + ":" + label)
    for index, shock in enumerate(
        _items(_mapping(value.get("role_coverage")).get("shared_shock_comparisons"))
    ):
        item = _mapping(shock)
        token_ids = {
            match.group(1) for match in _IDENTITY_TOKEN.finditer(_text(item.get("discriminator")))
        }
        company_ids = set(_strings(item.get("company_ids")))
        if token_ids != company_ids:
            findings.append(
                f"role_coverage.shared_shock_comparisons[{index}]."
                "discriminator_identity_tokens_must_match_company_ids"
            )


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
    (
        kinds, source_refs, admitted_source_kinds, admitted_source_company_ids,
        issuer_identity_catalog,
    ) = _source_validation(
        sources,
        root=source_root,
        industry_id=_text(value.get("industry_id")),
        cutoff=cutoff,
        findings=findings,
        gaps=gaps,
        require_issuer_identity=isinstance(value.get("version"), int) and value["version"] >= 3,
    )
    if isinstance(value.get("version"), int) and value["version"] >= 3:
        _validate_active_issuer_mentions(value, issuer_identity_catalog, findings)

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
    covered_company_ids = {
        _text(_mapping(item).get("company_id"))
        for item in _items(coverage.get("company_paths"))
        if _text(_mapping(item).get("company_id"))
    }
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
        shared_company_ids = set(_strings(item.get("company_ids")))
        if len(shared_company_ids) < 4:
            findings.append(f"role_coverage.shared_shock_comparisons[{index}].requires_four_companies")
        if not shared_company_ids <= covered_company_ids:
            findings.append(f"role_coverage.shared_shock_comparisons[{index}].company_not_in_company_paths")
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

    training_gaps = list(dict.fromkeys([
        *gaps,
        *_training_ready_gaps(
            value,
            kinds,
            admitted_source_kinds,
            admitted_source_company_ids,
        ),
    ]))
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


def _display_token(value: Any, *, prefix: str = "") -> str:
    token = _text(value)
    if prefix and token.startswith(prefix):
        token = token[len(prefix):]
    return token.replace("_", " ").strip().lower()


def _verification_question(field: str) -> str:
    if field in _VERIFICATION_QUESTION_TEMPLATES:
        return _VERIFICATION_QUESTION_TEMPLATES[field]
    label = _display_token(field)
    return (
        f"目标公司能否用自身证据结算“{label}”，并说明它如何传导至正常盈利、"
        "owner cash、永久损失与价值路线？"
    )


def _company_identity_literals(pack: Mapping[str, Any], context: Mapping[str, Any]) -> set[str]:
    identity = _mapping(context.get("company_identity"))
    literals = {
        _text(identity.get("company_id")),
        _text(identity.get("company_name")),
    }
    pack_text = json.dumps(pack, ensure_ascii=False)
    for company_id, company_name in _IDENTITY_TOKEN.findall(pack_text):
        literals.add(company_id)
        literals.add(company_name.strip())
    for item in _items(_mapping(pack.get("role_coverage")).get("company_paths")):
        literals.add(_text(_mapping(item).get("company_id")))
    return {item for item in literals if item}


def build_compact_industry_decision_memory(
    pack: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    root: str | Path = _ROOT,
) -> dict[str, Any]:
    """Build a concise training prior without copying target-company facts.

    The full Context remains an internal compilation input. Only generic
    verification field identifiers are projected; target identity, facts,
    evidence references, peer identities, valuation parameters, and actions
    are deliberately absent from the returned memory.
    """
    pack_value = _mapping(pack)
    context_value = _mapping(context)
    pack_validation = validate_industry_experience_pack(pack_value, root=root)
    if pack_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "industry_experience_pack_invalid:"
            + ",".join(pack_validation["findings"])
        )
    derived_state = _text(pack_validation.get("derived_state"))
    if derived_state not in MATURITY_ORDER or (
        MATURITY_ORDER.index(derived_state) < MATURITY_ORDER.index("TRAINING_READY")
    ):
        raise ValueError("industry_experience_pack_not_training_ready:" + derived_state)

    context_validation = validate_industry_underwriting_context(context_value)
    if context_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "industry_underwriting_context_invalid:"
            + ",".join(context_validation["findings"])
        )

    industry_id = _text(pack_value.get("industry_id"))
    identity = _mapping(context_value.get("company_identity"))
    context_industry_ids = set(_strings(identity.get("industry_ids")))
    if not context_industry_ids:
        raise ValueError("context_industry_identity_missing")
    if industry_id not in context_industry_ids:
        raise ValueError("pack_context_industry_mismatch")

    pack_cutoff = _instant(pack_value.get("knowledge_cutoff_at"))
    context_cutoff = _instant(identity.get("cutoff_at"))
    if pack_cutoff is None or context_cutoff is None:
        raise ValueError("pack_or_context_cutoff_invalid")
    if pack_cutoff > context_cutoff:
        raise ValueError("pack_cutoff_after_target_context")

    synthesis = _mapping(pack_value.get("current_synthesis"))
    role_coverage = _mapping(pack_value.get("role_coverage"))
    archetype_roles: dict[str, set[str]] = {}
    for raw in _items(role_coverage.get("company_paths")):
        company_path = _mapping(raw)
        archetype = _text(company_path.get("archetype_id"))
        if not archetype:
            continue
        archetype_roles.setdefault(archetype, set()).update(
            _strings(company_path.get("roles"))
        )
    reference_classes = [
        {
            "archetype": _display_token(archetype, prefix="ARCHETYPE:"),
            "roles": [_display_token(role) for role in sorted(roles)],
        }
        for archetype, roles in sorted(archetype_roles.items())
    ]

    verification_fields: list[str] = []
    for raw in _items(context_value.get("company_verification_fields")):
        item = _mapping(raw)
        field = _text(item.get("field"))
        if item.get("kind") == "FIELD" and _SAFE_VERIFICATION_FIELD.fullmatch(field):
            verification_fields.append(field)
    exposure = _mapping(context_value.get("company_archetype_exposure"))
    for raw in _items(exposure.get("exposures")):
        field = _text(_mapping(raw).get("dimension"))
        if _SAFE_VERIFICATION_FIELD.fullmatch(field):
            verification_fields.append(field)
    verification_questions = [
        _verification_question(field)
        for field in dict.fromkeys(verification_fields)
    ] or list(_FALLBACK_VERIFICATION_QUESTIONS)

    memory = {
        "version": COMPACT_MEMORY_VERSION,
        "use_status": "TRAINING_MEMORY",
        "capability_status": "HYPOTHESIS_AND_RESEARCH_QUESTION_ONLY",
        "industry_id": industry_id,
        "knowledge_cutoff_at": _text(pack_value.get("knowledge_cutoff_at")),
        "main_industry_path": _text(synthesis.get("central_industry_path")),
        "strongest_rival": _text(synthesis.get("strongest_rival")),
        "company_divergence": {
            "mechanism": _text(synthesis.get("profit_pool_transmission")),
            "reference_classes": reference_classes,
        },
        "target_company_verification_questions": verification_questions,
        "reversal_observations": _strings(synthesis.get("break_conditions")),
        "boundary": (
            "This memory supplies an industry prior, rival explanation, reference classes, "
            "research questions, and reversal tests only. Target-company evidence must establish "
            "exposure and economics; the memory grants no valuation or investment authority."
        ),
    }
    rendered = json.dumps(memory, ensure_ascii=False)
    leaked = sorted(
        literal
        for literal in _company_identity_literals(pack_value, context_value)
        if literal in rendered
    )
    if leaked:
        raise ValueError("compact_memory_contains_company_identity:" + ",".join(leaked))
    return memory


def render_compact_industry_decision_memory(memory: Mapping[str, Any]) -> str:
    divergence = _mapping(memory.get("company_divergence"))
    reference_classes = _items(divergence.get("reference_classes"))
    class_lines = [
        "- " + _text(_mapping(item).get("archetype"))
        + "（" + "、".join(_strings(_mapping(item).get("roles"))) + "）"
        for item in reference_classes
    ]
    question_lines = [
        "- " + item for item in _strings(memory.get("target_company_verification_questions"))
    ]
    reversal_lines = ["- " + item for item in _strings(memory.get("reversal_observations"))]
    return "\n".join([
        "# 精简行业决策记忆",
        "",
        f"> 版本：`{_text(memory.get('version'))}`  ",
        f"> 用途：`{_text(memory.get('use_status'))}`  ",
        f"> 能力状态：`{_text(memory.get('capability_status'))}`  ",
        f"> 行业：`{_text(memory.get('industry_id'))}`  ",
        f"> 知识截止：`{_text(memory.get('knowledge_cutoff_at'))}`  ",
        "> 边界：只提供行业先验、竞争解释、参考类别、研究问题与反转测试；"
        "目标公司证据负责结算暴露和经济传导，不提供估值或投资权限。",
        "",
        "## 1. 当前行业主路径",
        "",
        _text(memory.get("main_industry_path")),
        "",
        "## 2. 最强竞争解释",
        "",
        _text(memory.get("strongest_rival")),
        "",
        "## 3. 为什么公司会分化",
        "",
        _text(divergence.get("mechanism")),
        "",
        *class_lines,
        "",
        "## 4. 目标公司必须独立验证",
        "",
        *question_lines,
        "",
        "## 5. 反转观察",
        "",
        *reversal_lines,
        "",
    ])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a versioned Industry Experience Pack")
    parser.add_argument("pack", help="Industry Experience Pack JSON file")
    parser.add_argument("--root", default=str(_ROOT), help="Repository root for resolving refs")
    parser.add_argument(
        "--context",
        default="",
        help="Optional IndustryUnderwritingContext used to compile compact training memory",
    )
    parser.add_argument(
        "--decision-memory-output",
        default="",
        help="Markdown output path; requires --context",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    path = Path(args.pack).expanduser()
    payload = _read_json(path)
    result = validate_industry_experience_pack(payload, root=args.root)
    if bool(args.context) != bool(args.decision_memory_output):
        parser.error("--context and --decision-memory-output must be supplied together")
    if args.context:
        if result["state"] != "REVIEWABLE":
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 1
        context = _read_json(Path(args.context).expanduser())
        memory = build_compact_industry_decision_memory(
            payload,
            context,
            root=args.root,
        )
        output_path = Path(args.decision_memory_output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            render_compact_industry_decision_memory(memory),
            encoding="utf-8",
        )
        result = {
            "pack_validation": result,
            "decision_memory_output": str(output_path),
            "decision_memory_version": memory["version"],
            "capability_status": memory["capability_status"],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    pack_result = result.get("pack_validation", result)
    return 0 if pack_result["state"] == "REVIEWABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
