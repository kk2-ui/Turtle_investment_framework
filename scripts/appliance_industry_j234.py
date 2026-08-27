#!/usr/bin/env python3
"""Read-only J2/J3/J4 contracts for the China appliance learning block.

This adapter consumes the already frozen statutory-PDF source register.  It
does not fetch sources, open outcome windows, create forecasts, or assemble a
comparative panel.  Its purpose is to keep each company/cutoff question and
its evidentiary ceiling explicit, so an unavailable product or cash field
stops only the claim that needs it.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


SOURCE_REGISTER_SCHEMA = "turtle-cn-appliance-industry-learning-block-sources.v1"
J234_SCHEMA = "turtle-cn-appliance-industry-j234.v1"
CN_TZ = ZoneInfo("Asia/Shanghai")

CELL_STATES = {"OBSERVED", "INFERRED", "UNKNOWN", "EVIDENCE_INELIGIBLE", "NOT_APPLICABLE"}
DOMAINS = {"CUSTOMER", "OPERATING", "COMPETITION", "CASH", "CAPITAL_RETURN", "LEVERAGE", "PERMANENT_LOSS"}
CEILINGS = {"CONTEXT_ONLY", "TEACHING_ONLY", "MECHANISM_CANDIDATE"}
J2_OUTPUTS = {"INDUSTRY_CONTEXT", "TEACHING_ONLY", "MECHANISM_CANDIDATE", "RESEARCH_AGENDA"}
J3_REQUIRED_CONTRACTS = {"DECISION_CONTRACT", "OUTCOME_MEASUREMENT_CONTRACT", "PREFREEZE_EVIDENCE_RECEIPT"}
J4_STATE = "NOT_ADMITTED_MISSING_HOMOGENEOUS_PRODUCT_BOUNDARY"
UNIVERSE_ROLES = {"CORE_SYSTEM_RECONSTRUCTION", "CONTEXTUAL_RISK_SET"}
UNIVERSE_EVIDENCE_STATES = {"OBSERVED_SYSTEM_CONTEXT", "SOURCE_REGISTERED_CONTEXT_ONLY"}

_SOURCE_KEYS = {
    "source_id", "company_id", "company_name", "reporting_period_end", "report_type", "announced_on",
    "availability_precision", "provenance", "static_pdf_url", "physical_pages_used", "eligible_for_cutoff_ids",
}
_EPISODE_KEYS = {
    "episode_id", "company_id", "issuer_id", "company_cluster_id", "cutoff_id", "responsibility_boundary",
    "primary_question", "supporting_questions", "cells", "mechanism_threads", "allowed_outputs",
}
_UNIVERSE_MEMBER_KEYS = {
    "company_id", "issuer_id", "company_cluster_id", "cutoff_id", "responsibility_boundary", "universe_role",
    "evidence_state", "source_refs", "reason",
}
_QUESTION_KEYS = {"question_id", "role", "question", "required_cell_ids", "observation_state", "source_refs"}
_CELL_KEYS = {"cell_id", "domain", "observation_state", "source_refs", "reason"}
_THREAD_KEYS = {
    "thread_id", "question_id", "h_a", "h_b", "evidence_cell_ids", "source_refs", "evidence_ceiling",
    "observation_clock", "permitted_conclusion", "allowed_outputs",
}
_HANDOFF_KEYS = {
    "handoff_id", "episode_id", "state", "eligible_cell_ids", "unresolved_cell_ids", "required_contracts",
    "allowed_outputs", "prohibited_outputs",
}
_GATE_KEYS = {"gate_id", "state", "candidate_episode_ids", "arena_labels", "missing_facts", "allowed_outputs", "prohibited_outputs"}
_FORBIDDEN_KEYS = {
    "price", "market_price", "stock_price", "return", "outcome", "outcome_label", "settlement", "valuation",
    "buyband", "buy_band", "investment", "cjo", "forecast_probability", "forecast_direction", "panel",
    "peer_panel", "method_transfer",
}


class ApplianceJ234Error(ValueError):
    """Raised when a caller tries to compile an invalid J2/J3/J4 block."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(raw: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(raw)
    if not isinstance(raw, dict):
        _add(findings, f"{path}_must_be_object")
        return item
    for field in sorted(set(item) - allowed):
        _add(findings, f"{path}.contains_unsupported_field:{field}")
    return item


def _require(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        _add(findings, f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        _add(findings, f"{path}_must_be_timezone_aware")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        _add(findings, f"{path}_must_be_timezone_aware")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _add(findings, f"{path}_must_be_timezone_aware")
        return None
    return parsed.astimezone(CN_TZ)


def _forbidden_paths(value: Any, path: str) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            child = f"{path}.{key}"
            if lowered in _FORBIDDEN_KEYS or lowered.startswith("actual_") or lowered.startswith("settlement_"):
                paths.append(child)
            else:
                paths.extend(_forbidden_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def validate_appliance_source_register(source_register: Any) -> dict[str, Any]:
    """Validate only source identity, page locators and cutoff availability."""
    findings: list[str] = []
    item = _mapping(source_register)
    if item.get("schema_version") != SOURCE_REGISTER_SCHEMA:
        _add(findings, "source_register.schema_version_invalid")
    block_id = _require(item, "block_id", "source_register", findings)
    cutoffs: dict[str, datetime] = {}
    for index, raw in enumerate(_items(item.get("cutoffs"))):
        path = f"source_register.cutoffs[{index}]"
        cutoff = _closed(raw, {"cutoff_id", "cutoff_at", "purpose"}, path, findings)
        cutoff_id = _require(cutoff, "cutoff_id", path, findings)
        instant = _instant(cutoff.get("cutoff_at"), f"{path}.cutoff_at", findings)
        _require(cutoff, "purpose", path, findings)
        if cutoff_id in cutoffs:
            _add(findings, f"{path}.cutoff_id_duplicate")
        elif instant is not None:
            cutoffs[cutoff_id] = instant
    if len(cutoffs) < 2:
        _add(findings, "source_register.requires_at_least_two_cutoffs")

    sources: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_items(item.get("sources"))):
        path = f"source_register.sources[{index}]"
        source = _closed(raw, _SOURCE_KEYS, path, findings)
        source_id = _require(source, "source_id", path, findings)
        if source_id in sources:
            _add(findings, f"{path}.source_id_duplicate")
        else:
            sources[source_id] = source
        for field in ("company_id", "reporting_period_end", "report_type", "announced_on", "availability_precision", "provenance", "static_pdf_url"):
            _require(source, field, path, findings)
        if source.get("availability_precision") != "DATE_ONLY":
            _add(findings, f"{path}.availability_precision_must_remain_date_only")
        if source.get("provenance") != "OFFICIAL_STATUTORY_STATIC_PDF":
            _add(findings, f"{path}.provenance_invalid")
        if not str(source.get("static_pdf_url", "")).startswith("https://static.cninfo.com.cn/finalpage/"):
            _add(findings, f"{path}.static_pdf_url_invalid")
        pages = _items(source.get("physical_pages_used"))
        if not pages or any(not isinstance(page, int) or isinstance(page, bool) or page <= 0 for page in pages):
            _add(findings, f"{path}.physical_pages_used_invalid")
        try:
            announced = date.fromisoformat(str(source.get("announced_on")))
        except (TypeError, ValueError):
            announced = None
            _add(findings, f"{path}.announced_on_invalid")
        eligible = _items(source.get("eligible_for_cutoff_ids"))
        if not eligible or any(not _text(value) for value in eligible):
            _add(findings, f"{path}.eligible_for_cutoff_ids_invalid")
        for cutoff_id in eligible:
            cutoff = cutoffs.get(cutoff_id)
            if cutoff is None:
                _add(findings, f"{path}.unknown_cutoff_id:{cutoff_id}")
            elif announced is not None and announced >= cutoff.date():
                _add(findings, f"{path}.announcement_not_strictly_before_cutoff:{cutoff_id}")
    return {"valid": not findings, "findings": findings, "block_id": block_id, "cutoffs": cutoffs, "sources": sources}


def _validate_source_refs(
    raw_refs: Any, *, sources: dict[str, dict[str, Any]], company_id: str, cutoff_id: str, path: str, findings: list[str], required: bool,
) -> list[str]:
    refs = _items(raw_refs)
    if required and not refs:
        _add(findings, f"{path}_required")
    ids: list[str] = []
    for index, raw in enumerate(refs):
        ref_path = f"{path}[{index}]"
        ref = _closed(raw, {"source_id", "physical_page"}, ref_path, findings)
        source_id = _require(ref, "source_id", ref_path, findings)
        page = ref.get("physical_page")
        source = sources.get(source_id)
        if source is None:
            _add(findings, f"{ref_path}.source_not_in_source_register")
            continue
        ids.append(source_id)
        if source.get("company_id") != company_id:
            _add(findings, f"{ref_path}.company_must_match_episode")
        if cutoff_id not in _items(source.get("eligible_for_cutoff_ids")):
            _add(findings, f"{ref_path}.source_not_eligible_for_episode_cutoff")
        if page not in _items(source.get("physical_pages_used")):
            _add(findings, f"{ref_path}.physical_page_not_declared_by_source")
    return ids


def _validate_industry_universe(
    raw_members: Any, *, sources: dict[str, dict[str, Any]], cutoffs: dict[str, datetime], findings: list[str],
) -> tuple[dict[tuple[str, str], dict[str, Any]], set[str], set[str]]:
    """Validate a five-plus issuer risk set without calling it a peer panel.

    A contextual member has a statutory PDF at the same cutoff, but the
    present packet has not earned a product-level or causal comparison.  This
    allows the industry universe to be wider than the initial deep
    reconstruction, while making that limit machine-readable.
    """
    members = _items(raw_members)
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    companies: set[str] = set()
    seen_cutoffs: set[str] = set()
    core_companies: set[str] = set()
    for index, raw in enumerate(members):
        path = f"appliance_j234.industry_universe[{index}]"
        member = _closed(raw, _UNIVERSE_MEMBER_KEYS, path, findings)
        company_id = _require(member, "company_id", path, findings)
        _require(member, "issuer_id", path, findings)
        _require(member, "company_cluster_id", path, findings)
        cutoff_id = _require(member, "cutoff_id", path, findings)
        key = (company_id, cutoff_id)
        if key in by_key:
            _add(findings, f"{path}.company_cutoff_duplicate")
        else:
            by_key[key] = member
        companies.add(company_id)
        seen_cutoffs.add(cutoff_id)
        if cutoff_id not in cutoffs:
            _add(findings, f"{path}.cutoff_id_unknown")
        boundary = _closed(
            member.get("responsibility_boundary"),
            {"responsibility_unit_id", "perimeter_id", "arena_labels"},
            f"{path}.responsibility_boundary",
            findings,
        )
        for field in ("responsibility_unit_id", "perimeter_id"):
            _require(boundary, field, f"{path}.responsibility_boundary", findings)
        if boundary.get("perimeter_id") != "LISTED_CONSOLIDATED_ISSUER":
            _add(findings, f"{path}.responsibility_boundary_must_remain_listed_consolidated")
        if not _items(boundary.get("arena_labels")):
            _add(findings, f"{path}.responsibility_boundary.arena_labels_required")
        role = member.get("universe_role")
        if role not in UNIVERSE_ROLES:
            _add(findings, f"{path}.universe_role_invalid")
        elif role == "CORE_SYSTEM_RECONSTRUCTION":
            core_companies.add(company_id)
        state = member.get("evidence_state")
        if state not in UNIVERSE_EVIDENCE_STATES:
            _add(findings, f"{path}.evidence_state_invalid")
        if role == "CONTEXTUAL_RISK_SET" and state != "SOURCE_REGISTERED_CONTEXT_ONLY":
            _add(findings, f"{path}.contextual_member_must_remain_source_registered_only")
        _validate_source_refs(
            member.get("source_refs"),
            sources=sources,
            company_id=company_id,
            cutoff_id=cutoff_id,
            path=f"{path}.source_refs",
            findings=findings,
            required=True,
        )
        if state == "SOURCE_REGISTERED_CONTEXT_ONLY" and not _text(member.get("reason")):
            _add(findings, f"{path}.source_registered_context_requires_reason")
    if len(companies) < 5:
        _add(findings, "appliance_j234.industry_universe_requires_at_least_five_companies")
    if len(seen_cutoffs) < 2:
        _add(findings, "appliance_j234.industry_universe_requires_multiple_cutoffs")
    if len(core_companies) < 3:
        _add(findings, "appliance_j234.industry_universe_requires_three_core_companies")
    for company_id in companies:
        if not all((company_id, cutoff_id) in by_key for cutoff_id in cutoffs):
            _add(findings, f"appliance_j234.industry_universe_missing_company_cutoff:{company_id}")
    return by_key, core_companies, set()


def validate_appliance_j234(block: Any, *, source_register: Any) -> dict[str, Any]:
    """Validate J2 threads, J3 contract handoffs and J4 non-admission locally."""
    findings: list[str] = []
    register = validate_appliance_source_register(source_register)
    findings.extend(f"source_register:{finding}" for finding in register["findings"])
    value = _closed(block, {
        "schema_version", "block_id", "source_register_ref", "industry_universe", "episodes", "forecast_handoffs", "comparative_gates",
        "allowed_outputs", "prohibited_outputs",
    }, "appliance_j234", findings)
    if value.get("schema_version") != J234_SCHEMA:
        _add(findings, "appliance_j234.schema_version_invalid")
    if value.get("block_id") != register.get("block_id"):
        _add(findings, "appliance_j234.block_id_must_match_source_register")
    source_ref = _closed(value.get("source_register_ref"), {"block_id", "schema_version"}, "appliance_j234.source_register_ref", findings)
    if source_ref.get("block_id") != register.get("block_id") or source_ref.get("schema_version") != SOURCE_REGISTER_SCHEMA:
        _add(findings, "appliance_j234.source_register_ref_mismatch")
    for path in _forbidden_paths(value, "appliance_j234"):
        _add(findings, "appliance_j234.forbidden_field:" + path)

    universe_by_key, core_companies, _ = _validate_industry_universe(
        value.get("industry_universe"),
        sources=register["sources"],
        cutoffs=register["cutoffs"],
        findings=findings,
    )

    episodes = _items(value.get("episodes"))
    if len(episodes) < 3:
        _add(findings, "appliance_j234.requires_three_company_episodes")
    episode_by_id: dict[str, dict[str, Any]] = {}
    companies: set[str] = set()
    cutoff_ids: set[str] = set()
    for index, raw in enumerate(episodes):
        path = f"appliance_j234.episodes[{index}]"
        episode = _closed(raw, _EPISODE_KEYS, path, findings)
        episode_id = _require(episode, "episode_id", path, findings)
        company_id = _require(episode, "company_id", path, findings)
        _require(episode, "issuer_id", path, findings)
        _require(episode, "company_cluster_id", path, findings)
        cutoff_id = _require(episode, "cutoff_id", path, findings)
        if (company_id, cutoff_id) not in universe_by_key:
            _add(findings, f"{path}.company_cutoff_must_be_in_industry_universe")
        elif universe_by_key[(company_id, cutoff_id)].get("universe_role") != "CORE_SYSTEM_RECONSTRUCTION":
            _add(findings, f"{path}.deep_episode_requires_core_system_member")
        if episode_id in episode_by_id:
            _add(findings, f"{path}.episode_id_duplicate")
        else:
            episode_by_id[episode_id] = episode
        companies.add(company_id)
        cutoff_ids.add(cutoff_id)
        boundary = _closed(episode.get("responsibility_boundary"), {"responsibility_unit_id", "perimeter_id", "arena_labels"}, f"{path}.responsibility_boundary", findings)
        for field in ("responsibility_unit_id", "perimeter_id"):
            _require(boundary, field, f"{path}.responsibility_boundary", findings)
        if boundary.get("perimeter_id") != "LISTED_CONSOLIDATED_ISSUER":
            _add(findings, f"{path}.responsibility_boundary_must_remain_listed_consolidated")
        if not _items(boundary.get("arena_labels")):
            _add(findings, f"{path}.responsibility_boundary.arena_labels_required")

        cells: dict[str, dict[str, Any]] = {}
        domains: set[str] = set()
        for cell_index, raw_cell in enumerate(_items(episode.get("cells"))):
            cell_path = f"{path}.cells[{cell_index}]"
            cell = _closed(raw_cell, _CELL_KEYS, cell_path, findings)
            cell_id = _require(cell, "cell_id", cell_path, findings)
            if cell_id in cells:
                _add(findings, f"{cell_path}.cell_id_duplicate")
            else:
                cells[cell_id] = cell
            domain = cell.get("domain")
            if domain not in DOMAINS:
                _add(findings, f"{cell_path}.domain_invalid")
            else:
                domains.add(domain)
            state = cell.get("observation_state")
            if state not in CELL_STATES:
                _add(findings, f"{cell_path}.observation_state_invalid")
            if state in {"OBSERVED", "INFERRED"}:
                _validate_source_refs(cell.get("source_refs"), sources=register["sources"], company_id=company_id, cutoff_id=cutoff_id, path=f"{cell_path}.source_refs", findings=findings, required=True)
            elif _items(cell.get("source_refs")):
                _add(findings, f"{cell_path}.unresolved_cell_cannot_claim_sources")
            elif not _text(cell.get("reason")):
                _add(findings, f"{cell_path}.unresolved_cell_requires_reason")
        if domains != DOMAINS:
            _add(findings, f"{path}.cells_must_cover_each_required_domain")

        questions = [episode.get("primary_question"), *_items(episode.get("supporting_questions"))]
        if not 3 <= len(questions) <= 5:
            _add(findings, f"{path}.requires_one_primary_and_two_to_four_supporting_questions")
        question_ids: set[str] = set()
        for question_index, raw_question in enumerate(questions):
            question_path = f"{path}.questions[{question_index}]"
            question = _closed(raw_question, _QUESTION_KEYS, question_path, findings)
            question_id = _require(question, "question_id", question_path, findings)
            if question_id in question_ids:
                _add(findings, f"{question_path}.question_id_duplicate")
            question_ids.add(question_id)
            if question_index == 0 and question.get("role") != "PRIMARY":
                _add(findings, f"{question_path}.first_question_must_be_primary")
            if question_index and question.get("role") != "SUPPORTING":
                _add(findings, f"{question_path}.supporting_question_role_invalid")
            _require(question, "question", question_path, findings)
            required_cells = _items(question.get("required_cell_ids"))
            if not required_cells or not set(required_cells) <= set(cells):
                _add(findings, f"{question_path}.required_cell_ids_invalid")
            state = question.get("observation_state")
            if state not in CELL_STATES:
                _add(findings, f"{question_path}.observation_state_invalid")
            if state in {"OBSERVED", "INFERRED"}:
                _validate_source_refs(question.get("source_refs"), sources=register["sources"], company_id=company_id, cutoff_id=cutoff_id, path=f"{question_path}.source_refs", findings=findings, required=True)
            elif _items(question.get("source_refs")):
                _add(findings, f"{question_path}.unresolved_question_cannot_claim_sources")

        threads = _items(episode.get("mechanism_threads"))
        if not 2 <= len(threads) <= 3:
            _add(findings, f"{path}.requires_two_to_three_mechanism_threads")
        for thread_index, raw_thread in enumerate(threads):
            thread_path = f"{path}.mechanism_threads[{thread_index}]"
            thread = _closed(raw_thread, _THREAD_KEYS, thread_path, findings)
            _require(thread, "thread_id", thread_path, findings)
            if thread.get("question_id") not in question_ids:
                _add(findings, f"{thread_path}.question_id_unknown")
            for field in ("h_a", "h_b", "permitted_conclusion", "observation_clock"):
                _require(thread, field, thread_path, findings)
            evidence_cells = _items(thread.get("evidence_cell_ids"))
            if not evidence_cells or not set(evidence_cells) <= set(cells):
                _add(findings, f"{thread_path}.evidence_cell_ids_invalid")
            ceiling = thread.get("evidence_ceiling")
            if ceiling not in CEILINGS:
                _add(findings, f"{thread_path}.evidence_ceiling_invalid")
            if ceiling == "MECHANISM_CANDIDATE" and any(cells[cell_id].get("observation_state") not in {"OBSERVED", "INFERRED"} for cell_id in evidence_cells if cell_id in cells):
                _add(findings, f"{thread_path}.mechanism_candidate_cannot_depend_on_unresolved_cell")
            _validate_source_refs(thread.get("source_refs"), sources=register["sources"], company_id=company_id, cutoff_id=cutoff_id, path=f"{thread_path}.source_refs", findings=findings, required=True)
            outputs = _items(thread.get("allowed_outputs"))
            if not outputs or any(output not in J2_OUTPUTS for output in outputs):
                _add(findings, f"{thread_path}.allowed_outputs_invalid")
        outputs = _items(episode.get("allowed_outputs"))
        if not outputs or any(output not in J2_OUTPUTS for output in outputs):
            _add(findings, f"{path}.allowed_outputs_invalid")
    if len(companies) < 3:
        _add(findings, "appliance_j234.requires_cross_company_variation")
    if not companies <= core_companies:
        _add(findings, "appliance_j234.deep_episodes_must_remain_within_core_universe_members")
    if len(cutoff_ids) < 2:
        _add(findings, "appliance_j234.requires_longitudinal_variation")

    handoffs = _items(value.get("forecast_handoffs"))
    if len(handoffs) != len(episode_by_id):
        _add(findings, "appliance_j234.forecast_handoffs_must_cover_each_episode_once")
    handoff_ids: set[str] = set()
    handoff_episodes: set[str] = set()
    for index, raw in enumerate(handoffs):
        path = f"appliance_j234.forecast_handoffs[{index}]"
        handoff = _closed(raw, _HANDOFF_KEYS, path, findings)
        handoff_id = _require(handoff, "handoff_id", path, findings)
        if handoff_id in handoff_ids:
            _add(findings, f"{path}.handoff_id_duplicate")
        handoff_ids.add(handoff_id)
        episode = episode_by_id.get(handoff.get("episode_id"))
        if episode is None:
            _add(findings, f"{path}.episode_id_unknown")
            continue
        handoff_episodes.add(str(handoff.get("episode_id")))
        if handoff.get("state") != "FORECAST_CONTRACT_REQUIRED":
            _add(findings, f"{path}.state_must_require_separate_forecast_contract")
        cells_by_id = {cell.get("cell_id"): cell for cell in map(_mapping, _items(episode.get("cells")))}
        eligible = _items(handoff.get("eligible_cell_ids"))
        unresolved = _items(handoff.get("unresolved_cell_ids"))
        expected_eligible = {cell_id for cell_id, cell in cells_by_id.items() if cell.get("observation_state") in {"OBSERVED", "INFERRED"}}
        expected_unresolved = set(cells_by_id) - expected_eligible
        if set(eligible) != expected_eligible or set(unresolved) != expected_unresolved:
            _add(findings, f"{path}.cell_projection_must_match_episode")
        if set(_items(handoff.get("required_contracts"))) != J3_REQUIRED_CONTRACTS:
            _add(findings, f"{path}.required_contracts_invalid")
        if _items(handoff.get("allowed_outputs")) != ["RESEARCH_AGENDA"]:
            _add(findings, f"{path}.allowed_outputs_must_remain_research_agenda")
        forbidden = set(_items(handoff.get("prohibited_outputs")))
        if not {"FORECAST", "PROBABILITY", "OUTCOME_SETTLEMENT", "CJO", "VALUATION", "REPORT", "INVESTMENT"} <= forbidden:
            _add(findings, f"{path}.prohibited_outputs_incomplete")
    if handoff_episodes != set(episode_by_id):
        _add(findings, "appliance_j234.forecast_handoffs_missing_episode")

    gates = _items(value.get("comparative_gates"))
    if not gates:
        _add(findings, "appliance_j234.comparative_gate_required")
    for index, raw in enumerate(gates):
        path = f"appliance_j234.comparative_gates[{index}]"
        gate = _closed(raw, _GATE_KEYS, path, findings)
        _require(gate, "gate_id", path, findings)
        if gate.get("state") != J4_STATE:
            _add(findings, f"{path}.state_must_preserve_non_admission")
        candidates = _items(gate.get("candidate_episode_ids"))
        if not candidates or any(candidate not in episode_by_id for candidate in candidates):
            _add(findings, f"{path}.candidate_episode_ids_invalid")
        if len(_items(gate.get("arena_labels"))) < 2 or len(_items(gate.get("missing_facts"))) < 3:
            _add(findings, f"{path}.requires_arena_boundary_and_missing_fact_set")
        if _items(gate.get("allowed_outputs")) != ["RESEARCH_AGENDA"]:
            _add(findings, f"{path}.allowed_outputs_must_remain_research_agenda")
        forbidden = set(_items(gate.get("prohibited_outputs")))
        if not {"PANEL", "CAUSAL_VERDICT", "METHOD_TRANSFER", "CJO", "VALUATION", "REPORT", "INVESTMENT"} <= forbidden:
            _add(findings, f"{path}.prohibited_outputs_incomplete")

    if _items(value.get("allowed_outputs")) != ["INDUSTRY_CONTEXT", "TEACHING_ONLY", "MECHANISM_CANDIDATE", "RESEARCH_AGENDA"]:
        _add(findings, "appliance_j234.allowed_outputs_invalid")
    prohibited = set(_items(value.get("prohibited_outputs")))
    if not {"FORECAST", "OUTCOME_SETTLEMENT", "METHOD_TRANSFER", "CJO", "VALUATION", "REPORT", "INVESTMENT"} <= prohibited:
        _add(findings, "appliance_j234.prohibited_outputs_incomplete")
    return {"valid": not findings, "findings": findings, "episode_ids": sorted(episode_by_id)}


def compile_appliance_j234_read_model(block: Any, *, source_register: Any) -> dict[str, Any]:
    """Return read-only J2/J3/J4 views with no forecast or panel creation."""
    validation = validate_appliance_j234(block, source_register=source_register)
    if not validation["valid"]:
        raise ApplianceJ234Error("appliance_j234_invalid:" + ",".join(validation["findings"]))
    item = _mapping(block)
    return {
        "block_id": item["block_id"],
        "industry_universe": deepcopy(item["industry_universe"]),
        "j2_episode_ids": validation["episode_ids"],
        "j3_handoffs": deepcopy(item["forecast_handoffs"]),
        "j4_gates": deepcopy(item["comparative_gates"]),
        "investment_authorization": "NOT_AUTHORIZED",
    }
