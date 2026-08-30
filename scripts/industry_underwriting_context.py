#!/usr/bin/env python3
"""Compile existing industry knowledge into a report-preparation read model.

``IndustryUnderwritingContext`` is a bounded projection over existing
IndustryLearningBlock objects, the canonical industry-mechanism API, and a
company's competitive arena.  It is not a fact store, a second mechanism
library, or an underwriting conclusion.  Sparse inputs remain useful: the
compiler localizes missing context and still returns a report-consumable
object.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.industry_knowledge import read_industry_knowledge_context
    from scripts.industry_context_acquisition import (
        validate_official_context_observation_ledger,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from industry_knowledge import read_industry_knowledge_context
    from industry_context_acquisition import validate_official_context_observation_ledger


SCHEMA_VERSION = "industry-underwriting-context.v1"
VALIDATION_SCHEMA_VERSION = "industry-underwriting-context-validation.v1"
DEFAULT_OUTPUT_NAME = "industry_underwriting_context.json"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_UNKNOWN = "UNRESOLVED_FROM_AVAILABLE_CONTEXT"
_BOUNDARY_MARKERS = ("BREAK", "EXCLUDE", "MISMATCH", "INELIGIBLE", "NO_PRIMARY")
_DRIVER_KEYS = ("demand", "supply", "competition", "regulation")
_DRIVER_TERMS = {
    "demand": (
        "demand", "volume", "adoption", "replacement", "customer", "shipper",
        "property", "infrastructure", "traffic", "销量", "需求", "客户", "渗透",
    ),
    "supply": (
        "supply", "capacity", "utilization", "inventory", "input cost", "hub",
        "route density", "产能", "供给", "库存", "利用率", "成本",
    ),
    "competition": (
        "competition", "competitive", "concentration", "market share", "price",
        "channel", "rival", "service", "竞争", "集中度", "份额", "价格", "渠道",
    ),
    "regulation": (
        "regulation", "regulator", "policy", "licen", "environment", "carbon",
        "standard", "subsid", "监管", "政策", "环保", "碳", "补贴", "牌照",
    ),
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _instant(value: Any) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _relative_ref(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_input(
    value: Mapping[str, Any] | str | Path,
    *,
    kind: str,
    index: int,
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(value, Mapping):
        payload = deepcopy(dict(value))
        ref = _text(payload.get("source_object_ref")) or f"INLINE:{kind}:{index}"
    else:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        payload = _read_json(path)
        ref = _relative_ref(path)
        if not payload:
            warnings.append(f"{kind.lower()}_unreadable:{ref}")
    source = {
        "kind": kind,
        "ref": ref,
        "schema_version": _text(payload.get("schema_version")) or "UNSPECIFIED",
        "use_status": "INCLUDED" if payload else "UNREADABLE",
        "boundary": "Referenced source object remains canonical; this context is only a projection.",
    }
    return payload, source


def _load_official_observation_input(
    value: Mapping[str, Any] | str | Path,
    *,
    index: int,
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger_path: Path | None = None
    if isinstance(value, Mapping):
        ledger = deepcopy(dict(value))
        ledger_ref = _text(ledger.get("source_object_ref")) or f"INLINE:OFFICIAL_INDUSTRY_OBSERVATION:{index}"
    else:
        ledger_path = Path(value).expanduser()
        if not ledger_path.is_absolute():
            ledger_path = PROJECT_ROOT / ledger_path
        ledger = _read_json(ledger_path)
        ledger_ref = _relative_ref(ledger_path)
    source = {
        "kind": "OFFICIAL_INDUSTRY_OBSERVATION",
        "ref": ledger_ref,
        "schema_version": _text(ledger.get("schema_version")) or "UNSPECIFIED",
        "use_status": "UNREADABLE",
        "boundary": "Official observations supply cutoff-safe industry context only; they do not establish a target-company fact.",
    }
    if not ledger:
        warnings.append(f"official_industry_observation_unreadable:{ledger_ref}")
        return {}, source
    package_ref = _text(ledger.get("source_package_ref"))
    package_path = Path(package_ref).expanduser()
    if not package_path.is_absolute():
        project_candidate = PROJECT_ROOT / package_path
        ledger_candidate = ledger_path.parent / package_path if ledger_path is not None else project_candidate
        package_path = project_candidate if project_candidate.is_file() else ledger_candidate
    source_package = _read_json(package_path)
    validation = validate_official_context_observation_ledger(
        ledger,
        source_package,
        package_root=package_path.parent,
    )
    if validation["state"] != "REVIEWABLE_CONTEXT_ONLY":
        source["use_status"] = "EXCLUDED_INVALID"
        warnings.append(
            "official_industry_observation_invalid:"
            + ledger_ref
            + ":"
            + ",".join([
                *validation["invalid_findings"],
                *validation["incomplete_findings"],
            ])
        )
        return {}, source
    source["use_status"] = "INCLUDED"
    return ledger, source


def _block_cutoff(block: Mapping[str, Any]) -> str:
    if _text(block.get("cutoff_at")):
        return _text(block.get("cutoff_at"))
    cutoffs = _strings(block.get("cutoffs"))
    return max(cutoffs, key=lambda item: _instant(item) or datetime.min.replace(tzinfo=timezone.utc)) if cutoffs else ""


def _is_future(value: Any, cutoff: datetime | None) -> bool:
    observed = _instant(value)
    return cutoff is not None and observed is not None and observed > cutoff


def _evidence_ref(
    catalog: dict[str, dict[str, Any]],
    evidence_ref: Any,
    *,
    source_object_ref: str,
    supports: str,
    knowledge_status: str = "SOURCE_POINTER",
) -> str:
    ref = _text(evidence_ref)
    if not ref:
        return ""
    current = catalog.setdefault(ref, {
        "evidence_ref": ref,
        "source_object_refs": [],
        "supports": [],
        "knowledge_status": knowledge_status,
    })
    current["source_object_refs"] = _unique([*current["source_object_refs"], source_object_ref])
    current["supports"] = _unique([*current["supports"], supports])
    if knowledge_status != "SOURCE_POINTER":
        current["knowledge_status"] = knowledge_status
    return ref


def _driver_categories(value: Mapping[str, Any] | str) -> list[str]:
    if isinstance(value, Mapping):
        explicit = _text(value.get("driver_type") or value.get("category")).lower()
        if explicit in _DRIVER_KEYS:
            return [explicit]
        text = " ".join(_text(item) for item in value.values() if isinstance(item, (str, int, float)))
    else:
        text = _text(value)
    lowered = text.lower()
    return [key for key, terms in _DRIVER_TERMS.items() if any(term in lowered for term in terms)]


def _add_driver(
    drivers: dict[str, list[dict[str, Any]]],
    *,
    statement: str,
    source_object_ref: str,
    evidence_refs: Iterable[str],
    profit_pool_effect: str = "TO_BE_UNDERWRITTEN",
    explicit_category: str = "",
) -> None:
    categories = [explicit_category] if explicit_category in _DRIVER_KEYS else _driver_categories(statement)
    for category in categories:
        item = {
            "driver": statement,
            "profit_pool_effect": profit_pool_effect or "TO_BE_UNDERWRITTEN",
            "evidence_refs": _unique(evidence_refs),
            "source_object_ref": source_object_ref,
        }
        if item not in drivers[category]:
            drivers[category].append(item)


def _arena_objects(value: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    arena = _mapping(value)
    if not arena:
        return []
    if isinstance(arena.get("competitive_arena"), dict):
        nested = deepcopy(_mapping(arena["competitive_arena"]))
        if isinstance(arena.get("members"), list) and "members" not in nested:
            nested["members"] = deepcopy(arena["members"])
        return [nested]
    if isinstance(arena.get("competitive_arenas"), list):
        return [deepcopy(_mapping(item)) for item in arena["competitive_arenas"] if _mapping(item)]
    if isinstance(arena.get("arenas"), list):
        return [deepcopy(_mapping(item)) for item in arena["arenas"] if _mapping(item)]
    return [deepcopy(arena)]


def _arena_id(arena: Mapping[str, Any]) -> str:
    return _text(arena.get("competitive_arena_id") or arena.get("arena_id"))


def _arena_evidence(arena: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    refs.extend(_strings(arena.get("evidence_refs")))
    refs.extend(_strings(arena.get("source_ids")))
    for item in _items(arena.get("evidence")):
        if isinstance(item, dict):
            refs.append(_text(item.get("source_id") or item.get("evidence_ref")))
    for dimension in _items(arena.get("required_overlap_dimensions")):
        if isinstance(dimension, dict):
            refs.extend(_strings(dimension.get("target_evidence_source_ids")))
            refs.extend(_strings(dimension.get("evidence_refs")))
    return _unique(refs)


def _block_arenas(block: Mapping[str, Any]) -> list[dict[str, Any]]:
    arenas = [_mapping(item) for item in _items(block.get("mechanism_arenas")) if _mapping(item)]
    if arenas:
        return arenas
    arena_id = _text(block.get("competitive_arena_id"))
    return [{"arena_id": arena_id}] if arena_id else []


def _normalize_stage(arena: Mapping[str, Any], source_ref: str, evidence_refs: list[str]) -> dict[str, Any]:
    mechanism = _text(arena.get("mechanism"))
    product_scope = _text(arena.get("product_or_service_scope"))
    customer_task = _text(
        arena.get("customer_task")
        or arena.get("customer_choice_or_cost_driver")
        or arena.get("customer_end_market_scope")
        or arena.get("value_driver")
    )
    if not mechanism and (product_scope or customer_task):
        mechanism = " -> ".join(item for item in (product_scope, customer_task) if item)
    return {
        "arena_id": _arena_id(arena) or "UNSPECIFIED_ARENA",
        "mechanism": mechanism or _UNKNOWN,
        "economic_scope": _text(arena.get("economic_scope") or arena.get("market_scope_type") or arena.get("geographic_scope")) or _UNKNOWN,
        "customer_job_or_choice": customer_task or _UNKNOWN,
        "value_driver": _text(arena.get("value_driver") or arena.get("economic_state")) or _UNKNOWN,
        "failure_mode": _text(arena.get("failure_mode") or arena.get("competition_interface")) or _UNKNOWN,
        "profit_pool_direction": _text(arena.get("profit_pool_direction") or arena.get("profit_pool_effect")) or "UNRESOLVED",
        "evidence_refs": evidence_refs,
        "source_object_ref": source_ref,
    }


def _member_arena_ids(member: Mapping[str, Any], fallback: Iterable[str]) -> list[str]:
    ids = _strings(member.get("arena_ids"))
    single = _text(member.get("competitive_arena_id") or member.get("arena_id"))
    if single:
        ids.append(single)
    return _unique(ids or list(fallback))


def _company_match(left: Any, right: Any) -> bool:
    a, b = _text(left).upper(), _text(right).upper()
    if not a or not b:
        return False
    if a == b:
        return True
    digits_a = "".join(ch for ch in a if ch.isdigit())
    digits_b = "".join(ch for ch in b if ch.isdigit())
    return len(digits_a) >= 6 and digits_a[-6:] == digits_b[-6:]


def _v1_members(block: Mapping[str, Any]) -> list[dict[str, Any]]:
    archetypes = {
        _text(item.get("company_id")): _mapping(item)
        for item in _items(block.get("company_archetype_map")) if isinstance(item, dict)
    }
    decisions = {
        _text(item.get("company_id")): _mapping(item)
        for item in _items(block.get("decision_heterogeneity_matrix")) if isinstance(item, dict)
    }
    arena_id = _text(block.get("competitive_arena_id"))
    result: list[dict[str, Any]] = []
    for company_id, archetype in archetypes.items():
        decision = decisions.get(company_id, {})
        result.append({
            "company_id": company_id,
            "company_name": _text(archetype.get("company_name")),
            "archetype": _text(archetype.get("archetype_id")),
            "responsibility_boundary": _text(archetype.get("condition")),
            "boundary_status": _text(archetype.get("boundary_status")),
            "arena_ids": [arena_id] if arena_id else [],
            "cutoff_state": _text(archetype.get("condition")),
            "decision_heterogeneity": _text(decision.get("external_conditions") or decision.get("company_conditions")),
            "evidence_refs": _strings(archetype.get("evidence_refs")),
        })
    return result


def _block_members(block: Mapping[str, Any]) -> list[dict[str, Any]]:
    members = [_mapping(item) for item in _items(block.get("members")) if _mapping(item)]
    return members or _v1_members(block)


def _boundary_break(member: Mapping[str, Any]) -> bool:
    status = _text(member.get("boundary_status") or member.get("packet_state")).upper()
    return bool(_items(member.get("comparability_break_evidence"))) or any(
        marker in status for marker in _BOUNDARY_MARKERS
    )


def _peer_record(member: Mapping[str, Any], arena_ids: list[str], source_ref: str) -> dict[str, Any]:
    return {
        "company_id": _text(member.get("company_id") or member.get("member_id") or member.get("issuer_id")) or "UNKNOWN_COMPANY",
        "company_name": _text(member.get("company_name") or member.get("name")) or "UNSPECIFIED",
        "archetype": _text(member.get("archetype") or member.get("archetype_id")) or _UNKNOWN,
        "common_arena_ids": arena_ids,
        "comparison_role": _text(member.get("role") or member.get("causal_role")) or "MECHANISM_PEER_CANDIDATE",
        "why_representative": _text(member.get("decision_heterogeneity") or member.get("cutoff_state") or member.get("interface")) or "Shares an explicitly recorded mechanism arena.",
        "evidence_refs": _unique([*_strings(member.get("evidence_refs")), *_strings(member.get("source_ids"))]),
        "source_object_ref": source_ref,
    }


def _dedupe_company_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in records:
        key = _text(record.get("company_id")) or _text(record.get("company_name"))
        if key not in merged:
            merged[key] = deepcopy(record)
            order.append(key)
            continue
        current = merged[key]
        for field in ("common_arena_ids", "evidence_refs"):
            current[field] = _unique([*_strings(current.get(field)), *_strings(record.get(field))])
        if current.get("company_name") in {"", "UNSPECIFIED"}:
            current["company_name"] = record.get("company_name")
    return [merged[key] for key in order]


def _verification_item(field: str, why: str, refs: Iterable[str], source_ref: str, kind: str = "FIELD") -> dict[str, Any]:
    return {
        "field": field,
        "kind": kind,
        "why_it_matters": why or "Could distinguish the candidate industry-to-company transmission.",
        "evidence_refs": _unique(refs),
        "source_object_ref": source_ref,
    }


def _dedupe_verification_fields(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (_text(item.get("kind")), _text(item.get("field")))
        if key not in seen and key[1]:
            seen.add(key)
            result.append(item)
    return result


def _mechanism_context(
    company: Mapping[str, Any],
    *,
    industry_keys: Iterable[str],
    mechanism_keys: Iterable[str],
    knowledge_dir: str | Path | None,
    supplied: Mapping[str, Any] | None,
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if supplied is not None:
        return deepcopy(dict(supplied)), {
            "kind": "INDUSTRY_KNOWLEDGE_CONTEXT",
            "ref": _text(supplied.get("source_object_ref")) or "INLINE:INDUSTRY_KNOWLEDGE_CONTEXT",
            "schema_version": _text(supplied.get("schema_version")) or "UNSPECIFIED",
            "use_status": "INCLUDED",
            "boundary": "Mechanism cards remain canonical in the industry knowledge library.",
        }
    pit_mode = bool(company.get("pit_mode")) or _text(company.get("knowledge_mode")) == "PIT_EVIDENCE_ONLY"
    industries = _unique([*_strings(industry_keys), *_strings(company.get("industry_keys"))])
    mechanisms = _unique([*_strings(mechanism_keys), *_strings(company.get("mechanism_keys"))])
    if pit_mode:
        warnings.append("current_industry_knowledge_not_loaded_in_pit_mode")
        return {}, {
            "kind": "INDUSTRY_KNOWLEDGE_CONTEXT",
            "ref": "scripts/industry_knowledge.py:read_industry_knowledge_context",
            "schema_version": "industry-knowledge-context.v1",
            "use_status": "EXCLUDED_BY_PIT_BOUNDARY",
            "boundary": "Historical use requires an explicitly supplied object-level admitted context.",
        }
    if not industries and not mechanisms:
        warnings.append("industry_knowledge_keys_not_supplied")
        return {}, {
            "kind": "INDUSTRY_KNOWLEDGE_CONTEXT",
            "ref": "scripts/industry_knowledge.py:read_industry_knowledge_context",
            "schema_version": "industry-knowledge-context.v1",
            "use_status": "NO_QUERY_KEYS",
            "boundary": "No mechanism-library query was attempted without industry or mechanism keys.",
        }
    context = read_industry_knowledge_context(
        dict(company),
        industry_keys=industries,
        mechanism_keys=mechanisms,
        knowledge_dir=knowledge_dir,
    )
    return context, {
        "kind": "INDUSTRY_KNOWLEDGE_CONTEXT",
        "ref": "scripts/industry_knowledge.py:read_industry_knowledge_context",
        "schema_version": _text(context.get("schema_version")) or "industry-knowledge-context.v1",
        "use_status": "INCLUDED",
        "boundary": "Read through the existing canonical mechanism API; no mechanism facts are copied into a new store.",
    }


def _latest_target_member(targets: list[tuple[dict[str, Any], str]]) -> tuple[dict[str, Any], str]:
    return targets[-1] if targets else ({}, "")


def validate_industry_underwriting_context(payload: Any) -> dict[str, Any]:
    """Validate structural usefulness without turning sparse context into a stop gate."""
    value = _mapping(payload)
    findings: list[str] = []
    warnings: list[str] = []
    required = (
        "context_id", "company_identity", "context_status", "report_use",
        "industry_value_chain", "structural_epochs", "industry_drivers",
        "profit_pool_outlook", "company_archetype_exposure", "representative_peers",
        "near_misses", "candidate_main_paths", "strongest_counter_thesis",
        "company_verification_fields", "evidence_refs", "knowledge_time",
        "source_objects", "coverage", "warnings",
    )
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    for field in required:
        if field not in value:
            findings.append(field + "_missing")
    if value.get("context_status") not in {"READY", "BOUNDED"}:
        findings.append("context_status_invalid")
    report_use = _mapping(value.get("report_use"))
    if report_use.get("non_blocking") is not True:
        findings.append("report_use_must_be_non_blocking")
    drivers = _mapping(value.get("industry_drivers"))
    for key in _DRIVER_KEYS:
        if not isinstance(drivers.get(key), list):
            findings.append(f"industry_drivers.{key}_must_be_array")
    identity = _mapping(value.get("company_identity"))
    for field in ("company_id", "company_name", "cutoff_at"):
        if not _text(identity.get(field)):
            findings.append("company_identity." + field + "_missing")
    if _instant(identity.get("cutoff_at")) is None:
        findings.append("company_identity.cutoff_at_invalid")
    for index, path in enumerate(_items(value.get("candidate_main_paths"))):
        candidate = _mapping(path)
        for field in (
            "path_id", "industry_regime", "industry_force", "profit_pool_effect",
            "company_exposure", "adaptation_hypothesis", "economics_implication",
            "permanent_loss_implication", "reversal_observations", "evidence_refs",
        ):
            if field not in candidate or candidate.get(field) in ("", None):
                findings.append(f"candidate_main_paths[{index}].{field}_missing")
    if value.get("context_status") == "BOUNDED":
        warnings.append("bounded_context_is_report_consumable_and_not_a_failure")
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
        "warnings": warnings,
    }


def compile_industry_underwriting_context(
    *,
    company: Mapping[str, Any],
    industry_learning_blocks: Iterable[Mapping[str, Any] | str | Path] = (),
    official_industry_observations: Iterable[Mapping[str, Any] | str | Path] = (),
    competitive_arena: Mapping[str, Any] | None = None,
    industry_keys: Iterable[str] = (),
    mechanism_keys: Iterable[str] = (),
    knowledge_dir: str | Path | None = None,
    industry_knowledge_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a compact, evidence-bounded industry context for report research."""
    company_value = dict(company)
    company_id = _text(company_value.get("company_id") or company_value.get("ts_code")) or "UNKNOWN_COMPANY"
    company_name = _text(company_value.get("company_name") or company_value.get("name")) or "UNSPECIFIED"
    company_cutoff = _text(company_value.get("cutoff_at")) or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    knowledge_cutoff = _text(company_value.get("knowledge_cutoff_at")) or company_cutoff
    knowledge_cutoff_time = _instant(knowledge_cutoff)
    warnings: list[str] = []
    evidence_catalog: dict[str, dict[str, Any]] = {}
    source_objects: list[dict[str, Any]] = []
    excluded_future_refs: list[str] = []
    included_times: list[datetime] = []
    undated_source_refs: list[str] = []

    official_ledgers: list[tuple[dict[str, Any], str]] = []
    expected_industry_id = _text(company_value.get("industry_id"))
    for index, source in enumerate(official_industry_observations):
        ledger, source_object = _load_official_observation_input(
            source,
            index=index,
            warnings=warnings,
        )
        ledger_time = _text(ledger.get("cutoff_at"))
        if ledger and _is_future(ledger_time, knowledge_cutoff_time):
            source_object["use_status"] = "EXCLUDED_FUTURE"
            source_object["boundary"] = "The official observation ledger is later than the requested knowledge cutoff."
            excluded_future_refs.append(source_object["ref"])
        elif ledger and expected_industry_id and ledger.get("industry_id") != expected_industry_id:
            source_object["use_status"] = "EXCLUDED_INDUSTRY_MISMATCH"
            source_object["boundary"] = "The official observation ledger belongs to a different industry identity."
            warnings.append("official_industry_observation_industry_mismatch:" + source_object["ref"])
        elif ledger:
            official_ledgers.append((ledger, source_object["ref"]))
            parsed = _instant(ledger_time)
            if parsed:
                included_times.append(parsed)
            else:
                undated_source_refs.append(source_object["ref"])
        source_objects.append(source_object)

    blocks: list[tuple[dict[str, Any], str]] = []
    for index, source in enumerate(industry_learning_blocks):
        block, source_object = _load_input(source, kind="INDUSTRY_LEARNING_BLOCK", index=index, warnings=warnings)
        block_time = _block_cutoff(block)
        if block and _is_future(block_time, knowledge_cutoff_time):
            source_object["use_status"] = "EXCLUDED_FUTURE"
            source_object["boundary"] = "The block is later than the requested knowledge cutoff."
            excluded_future_refs.append(source_object["ref"])
        elif block:
            blocks.append((block, source_object["ref"]))
            parsed = _instant(block_time)
            if parsed:
                included_times.append(parsed)
            else:
                undated_source_refs.append(source_object["ref"])
        source_objects.append(source_object)

    arena_input = _mapping(competitive_arena)
    arena_source_ref = _text(arena_input.get("source_object_ref")) or "INLINE:COMPANY_COMPETITIVE_ARENA"
    source_objects.append({
        "kind": "COMPANY_COMPETITIVE_ARENA",
        "ref": arena_source_ref,
        "schema_version": _text(arena_input.get("schema_version")) or "UNSPECIFIED",
        "use_status": "INCLUDED" if arena_input else "NOT_SUPPLIED",
        "boundary": "Company arena supplies exposure and comparison scope; it is not an industry fact store.",
    })
    company_arenas = _arena_objects(arena_input)

    mechanism_context, mechanism_source = _mechanism_context(
        company_value,
        industry_keys=industry_keys,
        mechanism_keys=mechanism_keys,
        knowledge_dir=knowledge_dir,
        supplied=industry_knowledge_context,
        warnings=warnings,
    )
    source_objects.append(mechanism_source)
    warnings.extend(_strings(mechanism_context.get("warnings")))

    structural_epochs: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    drivers: dict[str, list[dict[str, Any]]] = {key: [] for key in _DRIVER_KEYS}
    verification_fields: list[dict[str, Any]] = []
    target_members: list[tuple[dict[str, Any], str]] = []
    all_members: list[tuple[dict[str, Any], str, list[str]]] = []
    counter_candidates: list[tuple[str, str, list[str]]] = []
    industry_ids: list[str] = []
    official_profit_pool_effects: list[str] = []
    official_profit_pool_refs: list[str] = []
    official_thesis_parts: list[str] = []
    official_statements: list[str] = []
    official_epoch_conditions: list[str] = []

    for ledger, source_ref in official_ledgers:
        industry_ids.extend(_strings([ledger.get("industry_id")]))
        epoch_statements: list[str] = []
        epoch_refs: list[str] = []
        ledger_thesis_parts: list[str] = []
        for observation in _items(ledger.get("observations")):
            item = _mapping(observation)
            observation_id = _text(item.get("observation_id"))
            evidence_ref = _evidence_ref(
                evidence_catalog,
                observation_id,
                source_object_ref=source_ref,
                supports="OFFICIAL_INDUSTRY_" + _text(item.get("driver_type")).upper(),
                knowledge_status="OFFICIAL_CONTEXT_OBSERVATION",
            )
            refs = [evidence_ref] if evidence_ref else []
            statement = _text(item.get("statement") or item.get("metric_definition"))
            interpretation = _text(item.get("economic_interpretation"))
            effect = _text(item.get("profit_pool_effect")) or "TO_BE_UNDERWRITTEN"
            if statement:
                epoch_statements.append(statement)
                official_statements.append(statement)
                _add_driver(
                    drivers,
                    statement=statement,
                    source_object_ref=source_ref,
                    evidence_refs=refs,
                    profit_pool_effect=effect,
                    explicit_category=_text(item.get("driver_type")),
                )
            if interpretation:
                ledger_thesis_parts.append(interpretation)
                official_thesis_parts.append(interpretation)
            if effect:
                official_profit_pool_effects.append(effect)
            official_profit_pool_refs.extend(refs)
            epoch_refs.extend(refs)
            rival = _text(item.get("rival_explanation"))
            if rival:
                counter_candidates.append((rival, source_ref, refs))
        if epoch_statements:
            epoch_condition = "Official cutoff context: " + "; ".join(
                _unique(ledger_thesis_parts or epoch_statements)
            )
            official_epoch_conditions.append(epoch_condition)
            structural_epochs.append({
                "epoch_id": _text(ledger.get("epoch_id")) or f"EPOCH:OFFICIAL:{len(structural_epochs) + 1}",
                "as_of": _text(ledger.get("cutoff_at")) or "UNSPECIFIED",
                "condition": epoch_condition,
                "observations": _unique(epoch_statements),
                "evidence_refs": _unique(epoch_refs),
                "source_object_ref": source_ref,
            })

    for block, source_ref in blocks:
        industry_ids.extend(_strings([block.get("industry_id")]))
        block_time = _block_cutoff(block)
        epochs = _items(block.get("industry_epoch_map"))
        if not epochs and _mapping(block.get("industry_epoch")):
            epochs = [block["industry_epoch"]]
        for epoch in epochs:
            item = _mapping(epoch)
            as_of = _text(item.get("cutoff_at")) or block_time
            if _is_future(as_of, knowledge_cutoff_time):
                excluded_future_refs.append(f"{source_ref}#{_text(item.get('epoch_id')) or 'epoch'}")
                continue
            condition = _text(item.get("statement") or item.get("condition")) or _UNKNOWN
            observations = _unique([
                _text(item.get("observed_industry_volume")),
                _text(item.get("observed_industry_revenue")),
                _text(item.get("observed_concentration")),
            ])
            refs = [
                _evidence_ref(evidence_catalog, ref, source_object_ref=source_ref, supports="STRUCTURAL_EPOCH")
                for ref in _strings(item.get("evidence_refs"))
            ]
            refs = _unique(refs)
            structural_epochs.append({
                "epoch_id": _text(item.get("epoch_id")) or f"EPOCH:{len(structural_epochs) + 1}",
                "as_of": as_of or "UNSPECIFIED",
                "condition": condition,
                "observations": observations,
                "evidence_refs": refs,
                "source_object_ref": source_ref,
            })
            _add_driver(drivers, statement=condition, source_object_ref=source_ref, evidence_refs=refs)
            for observation in observations:
                category = "competition" if "concentration" in observation.lower() or "cr" in observation.lower() else "demand"
                _add_driver(
                    drivers, statement=observation, source_object_ref=source_ref,
                    evidence_refs=refs, explicit_category=category,
                )

        block_arena_ids: list[str] = []
        for arena in _block_arenas(block):
            refs = [
                _evidence_ref(evidence_catalog, ref, source_object_ref=source_ref, supports="INDUSTRY_VALUE_CHAIN")
                for ref in _arena_evidence(arena)
            ]
            stage = _normalize_stage(arena, source_ref, _unique(refs))
            stages.append(stage)
            block_arena_ids.append(stage["arena_id"])
            _add_driver(
                drivers, statement=" ".join((stage["mechanism"], stage["value_driver"], stage["failure_mode"])),
                source_object_ref=source_ref, evidence_refs=stage["evidence_refs"],
                profit_pool_effect=stage["profit_pool_direction"],
            )

        for member in _block_members(block):
            member_arenas = _member_arena_ids(member, block_arena_ids)
            all_members.append((member, source_ref, member_arenas))
            if _company_match(member.get("company_id") or member.get("issuer_id"), company_id):
                target_members.append((member, source_ref))
            for ref in _strings(member.get("evidence_refs")):
                _evidence_ref(evidence_catalog, ref, source_object_ref=source_ref, supports="COMPANY_ARCHETYPE_OR_PEER")

        for rival in _strings(block.get("strongest_common_rivals")):
            counter_candidates.append((rival, source_ref, []))
        for unresolved in _items(block.get("unresolved_questions")):
            item = _mapping(unresolved)
            refs = _strings(item.get("evidence_refs"))
            verification_fields.append(_verification_item(
                _text(item.get("question")) or _text(unresolved),
                _text(item.get("materiality") or item.get("next_evidence")),
                refs,
                source_ref,
                kind="QUESTION",
            ))
        for synthesis in _items(block.get("conditional_mechanism_synthesis")):
            item = _mapping(synthesis)
            refs = [
                _evidence_ref(evidence_catalog, ref, source_object_ref=source_ref, supports="CONDITIONAL_MECHANISM")
                for ref in _strings(item.get("evidence_refs"))
            ]
            if _text(item.get("mechanism")):
                stages.append({
                    "arena_id": _text(block.get("competitive_arena_id")) or "UNSPECIFIED_ARENA",
                    "mechanism": _text(item.get("mechanism")),
                    "economic_scope": _text(item.get("when")) or _UNKNOWN,
                    "customer_job_or_choice": _UNKNOWN,
                    "value_driver": _text(item.get("observed_as")) or _UNKNOWN,
                    "failure_mode": _text(item.get("unless")) or _UNKNOWN,
                    "profit_pool_direction": "UNRESOLVED",
                    "evidence_refs": _unique(refs),
                    "source_object_ref": source_ref,
                })
            if _text(item.get("counterexamples")):
                counter_candidates.append((_text(item.get("counterexamples")), source_ref, _unique(refs)))

    for arena in company_arenas:
        refs = [
            _evidence_ref(evidence_catalog, ref, source_object_ref=arena_source_ref, supports="COMPANY_COMPETITIVE_ARENA")
            for ref in _arena_evidence(arena)
        ]
        stage = _normalize_stage(arena, arena_source_ref, _unique(refs))
        stages.append(stage)
        _add_driver(
            drivers, statement=" ".join((stage["mechanism"], stage["value_driver"], stage["failure_mode"])),
            source_object_ref=arena_source_ref, evidence_refs=stage["evidence_refs"],
            profit_pool_effect=stage["profit_pool_direction"],
        )
        for dimension in _items(arena.get("required_overlap_dimensions")):
            item = _mapping(dimension)
            dimension_refs = _unique([
                *_strings(item.get("target_evidence_source_ids")),
                *_strings(item.get("evidence_refs")),
            ])
            for ref in dimension_refs:
                _evidence_ref(evidence_catalog, ref, source_object_ref=arena_source_ref, supports="COMPANY_EXPOSURE")
            verification_fields.append(_verification_item(
                _text(item.get("dimension")) or "competitive_arena_overlap",
                _text(item.get("rationale_from_mechanism") or item.get("rationale")),
                dimension_refs,
                arena_source_ref,
            ))

    profile = _mapping(mechanism_context.get("profile"))
    mechanism_cards = [
        _mapping(item) for item in [
            *_items(profile.get("mechanisms")),
            *_items(profile.get("corroborated_mechanisms")),
        ] if _mapping(item)
    ]
    for card in mechanism_cards:
        mechanism_id = _text(card.get("mechanism_id"))
        ref = _evidence_ref(
            evidence_catalog,
            mechanism_id,
            source_object_ref=mechanism_source["ref"],
            supports="REUSABLE_INDUSTRY_MECHANISM",
            knowledge_status=_text(card.get("status")) or "CANONICAL_MECHANISM_CARD",
        )
        summary = _text(card.get("summary")) or _UNKNOWN
        stages.append({
            "arena_id": "MECHANISM_LIBRARY",
            "mechanism": summary,
            "economic_scope": "; ".join(_strings(card.get("applicability_conditions"))) or _UNKNOWN,
            "customer_job_or_choice": _UNKNOWN,
            "value_driver": _text(card.get("title")) or _UNKNOWN,
            "failure_mode": "; ".join(_strings(card.get("non_applicability_conditions"))) or _UNKNOWN,
            "profit_pool_direction": "UNRESOLVED",
            "evidence_refs": [ref] if ref else [],
            "source_object_ref": mechanism_source["ref"],
        })
        _add_driver(
            drivers, statement=" ".join((summary, _text(card.get("title")))),
            source_object_ref=mechanism_source["ref"], evidence_refs=[ref] if ref else [],
        )
        for alternative in _strings(card.get("alternative_explanations")):
            counter_candidates.append((alternative, mechanism_source["ref"], [ref] if ref else []))
        for field in _strings(card.get("company_verification_fields")):
            verification_fields.append(_verification_item(
                field, summary, [ref] if ref else [], mechanism_source["ref"],
            ))

    for field in _strings(profile.get("required_company_verification_fields")):
        verification_fields.append(_verification_item(
            field,
            "Required by a matched canonical industry mechanism before applying it to this company.",
            [],
            mechanism_source["ref"],
        ))
    verification_fields = _dedupe_verification_fields(verification_fields)

    target_member, target_source_ref = _latest_target_member(target_members)
    company_arena_ids = _unique([
        *[_arena_id(arena) for arena in company_arenas if _arena_id(arena)],
        *_member_arena_ids(target_member, []),
    ])
    if not company_arena_ids:
        company_arena_ids = _unique(stage["arena_id"] for stage in stages if stage["arena_id"] != "MECHANISM_LIBRARY")

    exposure_items: list[dict[str, Any]] = []
    for arena in company_arenas:
        for dimension in _items(arena.get("required_overlap_dimensions")):
            item = _mapping(dimension)
            exposure_items.append({
                "dimension": _text(item.get("dimension")) or "UNSPECIFIED",
                "relation": _text(item.get("relation")) or "UNSPECIFIED",
                "rationale": _text(item.get("rationale_from_mechanism") or item.get("rationale")) or _UNKNOWN,
                "evidence_refs": _unique([*_strings(item.get("target_evidence_source_ids")), *_strings(item.get("evidence_refs"))]),
            })
    if not exposure_items:
        exposure_items = [{
            "dimension": "ARENA_MEMBERSHIP",
            "relation": "RECORDED_CONTEXT" if company_arena_ids else "UNRESOLVED",
            "rationale": _text(target_member.get("cutoff_state") or target_member.get("condition")) or _UNKNOWN,
            "evidence_refs": _strings(target_member.get("evidence_refs")),
        }]

    peers: list[dict[str, Any]] = []
    near_misses: list[dict[str, Any]] = []
    for member, source_ref, member_arenas in all_members:
        member_id = member.get("company_id") or member.get("member_id") or member.get("issuer_id")
        if _company_match(member_id, company_id):
            continue
        overlap = sorted(set(company_arena_ids).intersection(member_arenas))
        record = _peer_record(member, overlap, source_ref)
        if overlap and not _boundary_break(member):
            peers.append(record)
        else:
            near_misses.append({
                **record,
                "near_miss_reason": (
                    "Material scope, control, or measurement boundary differs."
                    if _boundary_break(member)
                    else "No recorded overlap with the company's mechanism-defined arena."
                ),
            })

    explicit_peer_keys = ("representative_peers", "peers", "members")
    for arena in company_arenas:
        explicit_members: list[dict[str, Any]] = []
        for key in explicit_peer_keys:
            explicit_members.extend(_mapping(item) for item in _items(arena.get(key)) if _mapping(item))
        for member in explicit_members:
            member_id = member.get("company_id") or member.get("member_id") or member.get("issuer_id")
            if _company_match(member_id, company_id):
                continue
            record = _peer_record(member, _member_arena_ids(member, [_arena_id(arena)]), arena_source_ref)
            role = _text(member.get("role") or member.get("causal_role")).upper()
            if _boundary_break(member) or member.get("near_miss") is True or role in {"NOT_COMPARABLE", "NEAR_MISS", "FALSIFIER"}:
                near_misses.append({**record, "near_miss_reason": _text(member.get("near_miss_reason")) or "Explicitly recorded as a non-comparable or falsifying case."})
            else:
                peers.append(record)
    peers = _dedupe_company_records(peers)
    near_misses = _dedupe_company_records(near_misses)

    stage_map: dict[tuple[str, str], dict[str, Any]] = {}
    for stage in stages:
        key = (stage["arena_id"], stage["mechanism"])
        if key not in stage_map:
            stage_map[key] = stage
        else:
            current = stage_map[key]
            current["evidence_refs"] = _unique([*current["evidence_refs"], *stage["evidence_refs"]])
    stages = list(stage_map.values())
    structural_epochs.sort(key=lambda item: _instant(item["as_of"]) or datetime.min.replace(tzinfo=timezone.utc))
    latest_epoch = structural_epochs[-1] if structural_epochs else {}

    explicit_profit_pool = _text(company_value.get("industry_profit_pool_direction")) or next(
        (
            _text(arena.get("profit_pool_direction") or arena.get("profit_pool_effect"))
            for arena in company_arenas
            if _text(arena.get("profit_pool_direction") or arena.get("profit_pool_effect"))
        ),
        "",
    )
    if not explicit_profit_pool:
        explicit_profit_pool = next((stage["profit_pool_direction"] for stage in stages if stage["profit_pool_direction"] != "UNRESOLVED"), "")
    official_direction = " | ".join(_unique(official_profit_pool_effects))
    profit_pool_direction = explicit_profit_pool or official_direction or "UNRESOLVED"
    profit_pool_outlook = {
        "direction": profit_pool_direction,
        "horizon": _text(company_value.get("industry_horizon")) or "NOT_SPECIFIED",
        "thesis": (
            _text(company_value.get("industry_profit_pool_thesis"))
            or ("Official cutoff observations support: " + "; ".join(_unique(official_thesis_parts)) if official_thesis_parts else "")
            or ("The available context identifies the relevant mechanisms but does not yet settle a directional profit-pool call." if profit_pool_direction == "UNRESOLVED" else explicit_profit_pool)
        ),
        "confidence": "BOUNDED" if profit_pool_direction == "UNRESOLVED" else _text(company_value.get("industry_thesis_confidence")) or "QUALITATIVE",
        "evidence_refs": _unique([
            *(ref for stage in stages for ref in stage["evidence_refs"]),
            *official_profit_pool_refs,
        ]),
    }

    company_exposure_text = _text(
        target_member.get("cutoff_state")
        or target_member.get("condition")
        or company_value.get("company_exposure")
    ) or _UNKNOWN
    adaptation_text = _text(
        target_member.get("decision_heterogeneity")
        or company_value.get("adaptation_hypothesis")
    ) or "Requires company-specific evidence on resources, execution, and adaptation."
    candidate_paths: list[dict[str, Any]] = []
    if official_thesis_parts:
        candidate_paths.append({
            "path_id": f"IUP:{company_id}:OFFICIAL_CONTEXT",
            "status": "CANDIDATE_TO_VERIFY",
            "industry_regime": official_epoch_conditions[-1] if official_epoch_conditions else _UNKNOWN,
            "industry_force": "; ".join(_unique(official_statements)) or _UNKNOWN,
            "profit_pool_effect": profit_pool_direction,
            "company_exposure": company_exposure_text,
            "adaptation_hypothesis": adaptation_text,
            "economics_implication": "Verify whether the observed industry drivers transmit through the target company's customer demand, realized price or mix, unit economics, capital needs, and cash conversion.",
            "permanent_loss_implication": _text(company_value.get("industry_permanent_loss_implication")) or "If the supporting industry mechanism reverses, normalized earnings can compress and previously committed capital can become stranded.",
            "reversal_observations": [item["field"] for item in verification_fields[:8]] or ["Company-specific demand, realized-price, unit-economics, capital-absorption, and owner-cash evidence."],
            "evidence_refs": _unique(official_profit_pool_refs),
        })
    for index, stage in enumerate(stages):
        candidate_paths.append({
            "path_id": f"IUP:{company_id}:{index + 1}",
            "status": "CANDIDATE_TO_VERIFY",
            "industry_regime": _text(latest_epoch.get("condition")) or _UNKNOWN,
            "industry_force": stage["mechanism"],
            "profit_pool_effect": stage["profit_pool_direction"] if stage["profit_pool_direction"] != "UNRESOLVED" else profit_pool_direction,
            "company_exposure": company_exposure_text,
            "adaptation_hypothesis": adaptation_text,
            "economics_implication": (
                f"Verify whether {stage['value_driver']} changes normalized earnings, capital needs, and owner-cash conversion at the company's responsibility boundary."
                if stage["value_driver"] != _UNKNOWN
                else "Normalized earnings and owner-cash transmission require company-specific verification."
            ),
            "permanent_loss_implication": stage["failure_mode"],
            "reversal_observations": [item["field"] for item in verification_fields[:8]] or ["Obtain a company-specific observation that distinguishes this path from its strongest rival."],
            "evidence_refs": stage["evidence_refs"],
        })
    if not candidate_paths:
        candidate_paths.append({
            "path_id": f"IUP:{company_id}:1",
            "status": "CANDIDATE_TO_VERIFY",
            "industry_regime": _text(latest_epoch.get("condition")) or _UNKNOWN,
            "industry_force": "Industry force is not identified by the available objects.",
            "profit_pool_effect": "Direction remains unresolved until the relevant customer, supply, and competitive mechanism is identified.",
            "company_exposure": company_exposure_text,
            "adaptation_hypothesis": adaptation_text,
            "economics_implication": "Verify how the relevant industry mechanism reaches normalized earnings, capital needs, and owner-cash conversion at the company's responsibility boundary.",
            "permanent_loss_implication": "Do not pay for an unverified industry advantage; test whether structural pressure can impair the company's earning power or capital recovery.",
            "reversal_observations": [item["field"] for item in verification_fields[:8]] or ["Company-specific customer, operating, and cash evidence."],
            "evidence_refs": [],
        })

    strongest_counter = counter_candidates[0] if counter_candidates else (
        next((stage["failure_mode"] for stage in stages if stage["failure_mode"] != _UNKNOWN), _UNKNOWN),
        next((stage["source_object_ref"] for stage in stages), "UNSPECIFIED"),
        [],
    )
    strongest_counter_thesis = {
        "statement": strongest_counter[0],
        "why_plausible": "This competing explanation is explicitly preserved by an input block, mechanism card, or arena failure mode; it is not dismissed by peer count.",
        "discriminating_observations": [item["field"] for item in verification_fields[:8]] or ["Company-specific customer, unit-economics, and cash evidence."],
        "evidence_refs": strongest_counter[2],
        "source_object_ref": strongest_counter[1],
    }

    customer_jobs = _unique(
        stage["customer_job_or_choice"] for stage in stages if stage["customer_job_or_choice"] != _UNKNOWN
    )
    available: list[str] = []
    bounded: list[str] = []
    coverage_checks = {
        "industry_value_chain": bool(stages),
        "customer_jobs": bool(customer_jobs),
        "structural_epochs": bool(structural_epochs),
        "demand_drivers": bool(drivers["demand"]),
        "supply_drivers": bool(drivers["supply"]),
        "competition_drivers": bool(drivers["competition"]),
        "regulation_drivers": bool(drivers["regulation"]),
        "profit_pool_direction": profit_pool_direction != "UNRESOLVED",
        "company_archetype_exposure": bool(target_member or company_arenas or company_value.get("archetype") or company_value.get("archetype_id")),
        "representative_peers": bool(peers),
        "candidate_main_paths": bool(stages),
        "strongest_counter_thesis": strongest_counter[0] != _UNKNOWN,
        "company_verification_fields": bool(verification_fields),
        "evidence_references": bool(evidence_catalog),
    }
    for field, is_available in coverage_checks.items():
        (available if is_available else bounded).append(field)
    if bounded:
        warnings.append("bounded_fields:" + ",".join(bounded))

    archetype = _text(
        target_member.get("archetype")
        or target_member.get("archetype_id")
        or company_value.get("archetype")
        or company_value.get("archetype_id")
    ) or _UNKNOWN
    context_status = "READY" if not bounded else "BOUNDED"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "context_id": _text(company_value.get("context_id")) or f"IUC:{company_id}:{knowledge_cutoff}",
        "company_identity": {
            "company_id": company_id,
            "company_name": company_name,
            "cutoff_at": company_cutoff,
            "industry_ids": _unique([*industry_ids, *_strings(industry_keys), *_strings(company_value.get("industry_keys"))]),
        },
        "context_status": context_status,
        "report_use": {
            "mode": "REPORT_PREPARATION_READ_MODEL",
            "non_blocking": True,
            "can_support": ["INDUSTRY_RESEARCH_AGENDA", "CANDIDATE_INDUSTRY_FUTURE_THESIS", "PEER_AND_NEAR_MISS_SELECTION"],
            "cannot_establish": ["COMPANY_FACT_WITHOUT_COMPANY_EVIDENCE", "VALUATION_PARAMETER", "INVESTMENT_ACTION"],
            "boundary": "A BOUNDED context remains usable. The report must make and source its own best-current industry and company judgment.",
        },
        "industry_value_chain": {
            "stages": stages,
            "customer_jobs": customer_jobs,
        },
        "structural_epochs": structural_epochs,
        "industry_drivers": drivers,
        "profit_pool_outlook": profit_pool_outlook,
        "company_archetype_exposure": {
            "archetype": archetype,
            "responsibility_boundary": _text(target_member.get("responsibility_boundary") or company_value.get("responsibility_boundary")) or _UNKNOWN,
            "arena_ids": company_arena_ids,
            "exposures": exposure_items,
            "current_state": company_exposure_text,
            "adaptation_hypothesis": adaptation_text,
            "evidence_refs": _strings(target_member.get("evidence_refs")),
            "source_object_ref": target_source_ref or arena_source_ref,
        },
        "representative_peers": peers,
        "near_misses": near_misses,
        "candidate_main_paths": candidate_paths,
        "strongest_counter_thesis": strongest_counter_thesis,
        "company_verification_fields": verification_fields,
        "evidence_refs": list(evidence_catalog.values()),
        "knowledge_time": {
            "cutoff_at": knowledge_cutoff,
            "latest_included_at": max(included_times).isoformat() if included_times else "UNSPECIFIED",
            "excluded_future_source_refs": _unique(excluded_future_refs),
            "undated_source_refs": _unique(undated_source_refs),
        },
        "source_objects": source_objects,
        "coverage": {"available": available, "bounded": bounded},
        "warnings": _unique(warnings),
    }
    validation = validate_industry_underwriting_context(payload)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("compiled_industry_underwriting_context_invalid:" + ",".join(validation["findings"]))
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a report-preparation IndustryUnderwritingContext")
    parser.add_argument("--company", help="Optional JSON file containing company identity and knowledge-time fields")
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--cutoff-at", default="")
    parser.add_argument("--knowledge-cutoff-at", default="")
    parser.add_argument("--industry-block", action="append", default=[])
    parser.add_argument("--official-industry-observation", action="append", default=[])
    parser.add_argument("--competitive-arena", default="")
    parser.add_argument("--industry-knowledge-context", default="")
    parser.add_argument("--industry-key", action="append", default=[])
    parser.add_argument("--mechanism-key", action="append", default=[])
    parser.add_argument("--knowledge-dir", default="")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_NAME)
    args = parser.parse_args()

    company = _read_json(Path(args.company).expanduser()) if args.company else {}
    if args.company_id:
        company["company_id"] = args.company_id
    if args.company_name:
        company["company_name"] = args.company_name
    if args.cutoff_at:
        company["cutoff_at"] = args.cutoff_at
    if args.knowledge_cutoff_at:
        company["knowledge_cutoff_at"] = args.knowledge_cutoff_at
    arena = _read_json(Path(args.competitive_arena).expanduser()) if args.competitive_arena else None
    knowledge = _read_json(Path(args.industry_knowledge_context).expanduser()) if args.industry_knowledge_context else None
    payload = compile_industry_underwriting_context(
        company=company,
        industry_learning_blocks=args.industry_block,
        official_industry_observations=args.official_industry_observation,
        competitive_arena=arena,
        industry_keys=args.industry_key,
        mechanism_keys=args.mechanism_key,
        knowledge_dir=args.knowledge_dir or None,
        industry_knowledge_context=knowledge,
    )
    _write_json(Path(args.output).expanduser(), payload)
    print(json.dumps({
        "output": str(Path(args.output).expanduser()),
        "context_id": payload["context_id"],
        "context_status": payload["context_status"],
        "peer_count": len(payload["representative_peers"]),
        "near_miss_count": len(payload["near_misses"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
