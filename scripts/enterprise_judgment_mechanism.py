#!/usr/bin/env python3
"""J2 pre-outcome mechanism-thread validation and projection.

J2 enriches the thread skeletons already frozen in a J0 episode and resolves
their evidence and responsibility bindings against a J1 reconstruction.  It
does not copy canonical facts, observe outcomes, forecast, or run a
comparative.  Structural and leakage failures reject the contract; reference
failures remain local so they can restrict only claims that depend on the
affected thread.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any

try:
    from scripts import enterprise_judgment_core as core
    from scripts import enterprise_judgment_episode as episode
    from scripts import enterprise_judgment_reconstruction as reconstruction
    from scripts import judgment_historical_training as historical
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_core as core
    import enterprise_judgment_episode as episode
    import enterprise_judgment_reconstruction as reconstruction
    import judgment_historical_training as historical


SCHEMA_VERSION = "enterprise-judgment-mechanism-thread-set.v1"
ALLOWED_OUTPUTS = ["MECHANISM_THREAD_READ_MODEL", "RESEARCH_AGENDA"]

CLAIM_TYPES = {
    "DESCRIPTIVE_STRUCTURE",
    "WITHIN_CASE_MECHANISM",
    "LIFECYCLE_TRANSITION",
    "RELATIVE_CAUSAL",
}.intersection(historical.CLAIM_CLASSES)
LOCAL_STATUSES = set(episode.CLAIM_STATES)
SOURCE_ELIGIBILITY = set(core.SOURCE_ELIGIBILITY)
INFORMATION_ROLES = set(historical.INFORMATION_ROLES)
EVIDENCE_CEILINGS = {"CONTEXT", "TEACHING", "MECHANISM"}
THREAD_ROLES = set(episode.THREAD_ROLES)
HYPOTHESIS_ROLES = {"H_A", "H_B"}

_BLOCKING_LOCAL_STATUSES = {"UNKNOWN", "EVIDENCE_INELIGIBLE", "NOT_APPLICABLE"}
_FORECASTABLE_CLAIM_TYPES = CLAIM_TYPES - {"RELATIVE_CAUSAL"}
_THREAD_OUTPUTS_BY_CEILING = {
    "CONTEXT": ["RESEARCH_AGENDA"],
    "TEACHING": ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
    "MECHANISM": ["MECHANISM_VIEW", "TEACHING_ONLY", "MECHANISM_CANDIDATE", "RESEARCH_AGENDA"],
}

_ROOT_KEYS = {
    "schema_version",
    "thread_set_id",
    "episode_ref",
    "reconstruction_ref",
    "threads",
    "outcome_access",
    "object_class",
    "claim_class",
    "allowed_outputs",
}
_EPISODE_REF_KEYS = {"episode_id", "schema_version"}
_RECONSTRUCTION_REF_KEYS = {"reconstruction_id", "schema_version"}
_RECONSTRUCTION_INPUT_KEYS = {
    "spec",
    "source_packet_receipt",
    "source_package",
    "enterprise_model",
    "decision_ledger",
    "decision_contract",
}
_THREAD_KEYS = {
    "thread_id",
    "role",
    "claim_ids",
    "claim_type",
    "hypotheses",
    "responsibility_boundary",
    "reconstruction_loop_ids",
    "evidence_discriminator",
    "observation_clock",
    "outcome_cell_refs",
    "source_refs",
    "local_status",
    "evidence_ceiling",
    "permitted_outputs",
    "e3_comparative_requested",
    "comparative_projection_contract",
}
_HYPOTHESIS_KEYS = {"hypothesis_id", "role", "statement"}
_BOUNDARY_KEYS = {"responsibility_unit_id", "arena_id"}
_DISCRIMINATOR_KEYS = {"discriminator_id", "observable", "expected_if_h_a", "expected_if_h_b"}
_CLOCK_KEYS = {"clock_id", "opens_at", "due_at"}
_SOURCE_REF_KEYS = {"source_ref", "available_at", "information_role"}
_COMPARATIVE_CONTRACT_KEYS = {"hypothesis_bindings", "outcome_bindings", "source_lineage"}
_COMPARATIVE_HYPOTHESIS_BINDING_KEYS = {
    "role", "j2_hypothesis_id", "j2_statement", "v5_hypothesis_id", "v5_mechanism",
}
_COMPARATIVE_OUTCOME_BINDING_KEYS = {
    "outcome_cell_id", "measurement_contract_ref", "v5_measurement_contracts",
}
_COMPARATIVE_SOURCE_LINEAGE_KEYS = {
    "j1_source_packet_refs", "j2_source_refs", "v5_source_provenance", "v5_sources",
}

_FORBIDDEN_KEYS = {
    "price",
    "market_price",
    "share_price",
    "stock_price",
    "entry_price",
    "return",
    "returns",
    "stock_return",
    "shareholder_return",
    "total_shareholder_return",
    "actual_value",
    "outcome_value",
    "outcome_result",
    "settlement_value",
    "company_score",
    "company_quality",
    "overall_company_quality",
    "universal_upgrade",
    "valuation",
    "buyband",
    "buy_band",
    "investment_instruction",
}
_LEAKAGE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:stock|share|market|entry)\s+price\b",
        r"\b(?:stock|shareholder|market|portfolio|security)\s+returns?\b",
        r"\btotal\s+shareholder\s+return\b",
        r"\bpost[- ]cutoff\b",
        r"\b(?:actual|realized|settled)\s+outcome\b",
        r"\blater\s+survival\b",
    )
)
_UNIVERSAL_QUALITY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\buniversal(?:ly)?\s+(?:high[- ]quality|excellent|superior)\s+compan(?:y|ies)\b",
        r"\b(?:proves?|establishes?|upgrades?)\b.{0,80}\b(?:company|issuer)\b.{0,50}\b(?:overall|universally|high[- ]quality|excellent|superior)\b",
        r"\b(?:company|issuer)\b.{0,50}\b(?:always|inherently)\b.{0,30}\b(?:high[- ]quality|excellent|superior)\b",
    )
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(
    value: Any,
    allowed: set[str],
    path: str,
    findings: list[str],
    *,
    required: set[str] | None = None,
) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, f"{path}_must_be_object")
        return item
    for field in sorted(set(item).difference(allowed)):
        _add(findings, f"{path}_contains_unapproved_field:{field}")
    for field in sorted((allowed if required is None else required).difference(item)):
        _add(findings, f"{path}_missing_required_field:{field}")
    return item


def _require_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        _add(findings, f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        _add(findings, f"{path}_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        _add(findings, f"{path}_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _add(findings, f"{path}_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _ids(value: Any, path: str, findings: list[str]) -> list[str]:
    values = _items(value)
    if not values:
        _add(findings, path + "_required")
    result: list[str] = []
    for index, raw in enumerate(values):
        if not _text(raw):
            _add(findings, f"{path}[{index}]_must_be_nonempty_text")
            continue
        item = str(raw)
        if item in result:
            _add(findings, f"{path}[{index}]_duplicate")
        else:
            result.append(item)
    return result


def _forbidden_paths(value: Any, path: str = "mechanism_thread_set") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if key_text == "comparative_projection_contract":
                continue
            if (
                key_text in _FORBIDDEN_KEYS
                or key_text.startswith("actual_")
                or key_text.startswith("settlement_")
                or key_text.endswith("_market_price")
                or key_text.endswith("_stock_return")
            ):
                paths.append(child_path)
            else:
                paths.extend(_forbidden_paths(nested, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _narrative_values(thread: dict[str, Any]) -> list[str]:
    values = [
        str(_mapping(thread.get("evidence_discriminator")).get(field, ""))
        for field in ("observable", "expected_if_h_a", "expected_if_h_b")
    ]
    values.extend(str(_mapping(raw).get("statement", "")) for raw in _items(thread.get("hypotheses")))
    return values


def _expected_outputs(local_status: Any, evidence_ceiling: Any) -> list[str]:
    if local_status in _BLOCKING_LOCAL_STATUSES:
        return ["RESEARCH_AGENDA"]
    return list(_THREAD_OUTPUTS_BY_CEILING.get(str(evidence_ceiling), []))


def _validate_hypotheses(value: Any, path: str, findings: list[str]) -> list[dict[str, Any]]:
    raw_items = _items(value)
    if len(raw_items) != 2:
        _add(findings, path + "_must_contain_h_a_and_h_b")
    hypotheses = [_closed(raw, _HYPOTHESIS_KEYS, f"{path}[{index}]", findings) for index, raw in enumerate(raw_items)]
    roles: set[str] = set()
    ids: set[str] = set()
    for index, hypothesis in enumerate(hypotheses):
        hypothesis_id = _require_text(hypothesis, "hypothesis_id", f"{path}[{index}]", findings)
        if hypothesis_id in ids:
            _add(findings, f"{path}[{index}].hypothesis_id_duplicate")
        ids.add(hypothesis_id)
        role = hypothesis.get("role")
        if role not in HYPOTHESIS_ROLES:
            _add(findings, f"{path}[{index}].role_invalid")
        roles.add(str(role))
        _require_text(hypothesis, "statement", f"{path}[{index}]", findings)
    if roles != HYPOTHESIS_ROLES:
        _add(findings, path + "_must_distinguish_h_a_h_b")
    return hypotheses


def _validate_thread_shape(
    value: Any,
    *,
    index: int,
    cutoff: datetime | None,
    findings: list[str],
) -> dict[str, Any]:
    path = f"mechanism_thread_set.threads[{index}]"
    thread = _closed(
        value,
        _THREAD_KEYS,
        path,
        findings,
        required=_THREAD_KEYS - {"comparative_projection_contract"},
    )
    _require_text(thread, "thread_id", path, findings)
    if thread.get("role") not in THREAD_ROLES:
        _add(findings, path + ".role_invalid")
    _ids(thread.get("claim_ids"), path + ".claim_ids", findings)
    claim_type = thread.get("claim_type")
    if claim_type not in CLAIM_TYPES:
        _add(findings, path + ".claim_type_invalid")
    _validate_hypotheses(thread.get("hypotheses"), path + ".hypotheses", findings)

    boundary = _closed(thread.get("responsibility_boundary"), _BOUNDARY_KEYS, path + ".responsibility_boundary", findings)
    _require_text(boundary, "responsibility_unit_id", path + ".responsibility_boundary", findings)
    _require_text(boundary, "arena_id", path + ".responsibility_boundary", findings)
    _ids(thread.get("reconstruction_loop_ids"), path + ".reconstruction_loop_ids", findings)

    discriminator = _closed(thread.get("evidence_discriminator"), _DISCRIMINATOR_KEYS, path + ".evidence_discriminator", findings)
    for field in _DISCRIMINATOR_KEYS:
        _require_text(discriminator, field, path + ".evidence_discriminator", findings)
    if (
        _text(discriminator.get("expected_if_h_a"))
        and discriminator.get("expected_if_h_a") == discriminator.get("expected_if_h_b")
    ):
        _add(findings, path + ".evidence_discriminator_must_distinguish_h_a_h_b")

    clock = _closed(thread.get("observation_clock"), _CLOCK_KEYS, path + ".observation_clock", findings)
    _require_text(clock, "clock_id", path + ".observation_clock", findings)
    opens_at = _instant(clock.get("opens_at"), path + ".observation_clock.opens_at", findings)
    due_at = _instant(clock.get("due_at"), path + ".observation_clock.due_at", findings)
    if cutoff is not None and opens_at is not None and opens_at < cutoff:
        _add(findings, path + ".observation_clock_must_open_at_or_after_cutoff")
    if opens_at is not None and due_at is not None and due_at <= opens_at:
        _add(findings, path + ".observation_clock.due_at_must_follow_opens_at")

    _ids(thread.get("outcome_cell_refs"), path + ".outcome_cell_refs", findings)
    raw_sources = _items(thread.get("source_refs"))
    if not raw_sources:
        _add(findings, path + ".source_refs_required")
    seen_sources: set[str] = set()
    for source_index, raw_source in enumerate(raw_sources):
        source_path = f"{path}.source_refs[{source_index}]"
        source = _closed(raw_source, _SOURCE_REF_KEYS, source_path, findings)
        source_ref = _require_text(source, "source_ref", source_path, findings)
        if source_ref in seen_sources:
            _add(findings, source_path + ".source_ref_duplicate")
        seen_sources.add(source_ref)
        available_at = _instant(source.get("available_at"), source_path + ".available_at", findings)
        if cutoff is not None and available_at is not None and available_at > cutoff:
            _add(findings, source_path + ".source_must_be_available_at_or_before_cutoff")
        information_role = source.get("information_role")
        if information_role not in INFORMATION_ROLES:
            _add(findings, source_path + ".information_role_invalid")
        elif information_role != "CUTOFF_VISIBLE":
            _add(findings, source_path + ".must_be_cutoff_visible")

    local_status = thread.get("local_status")
    if local_status not in LOCAL_STATUSES:
        _add(findings, path + ".local_status_invalid")
    evidence_ceiling = thread.get("evidence_ceiling")
    if evidence_ceiling not in EVIDENCE_CEILINGS:
        _add(findings, path + ".evidence_ceiling_invalid_or_above_j2")
    expected_outputs = _expected_outputs(local_status, evidence_ceiling)
    if thread.get("permitted_outputs") != expected_outputs:
        _add(findings, path + ".permitted_outputs_must_match_local_status_and_evidence_ceiling")
    requested = thread.get("e3_comparative_requested")
    if not isinstance(requested, bool):
        _add(findings, path + ".e3_comparative_requested_must_be_boolean")
    elif requested != (claim_type == "RELATIVE_CAUSAL"):
        _add(findings, path + ".relative_causal_claim_and_e3_request_must_match")

    for text in _narrative_values(thread):
        if any(pattern.search(text) for pattern in _LEAKAGE_PATTERNS):
            _add(findings, path + ".pre_outcome_narrative_contains_price_return_or_post_cutoff_leakage")
        if any(pattern.search(text) for pattern in _UNIVERSAL_QUALITY_PATTERNS):
            _add(findings, path + ".universal_company_quality_upgrade_prohibited")
    return thread


def _validate_reconstruction_shape(value: Any, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, "reconstruction_must_be_object")
        return item
    if item.get("schema_version") != reconstruction.SCHEMA_VERSION:
        _add(findings, "reconstruction.schema_version_invalid")
    for field in ("reconstruction_id", "company_id", "issuer_id", "cutoff_at"):
        _require_text(item, field, "reconstruction", findings)
    source_packet_ref = _mapping(item.get("source_packet_ref"))
    if not _text(source_packet_ref.get("receipt_id")):
        _add(findings, "reconstruction.source_packet_ref.receipt_id_required")
    receipt_version = source_packet_ref.get("receipt_version")
    if not isinstance(receipt_version, int) or isinstance(receipt_version, bool) or receipt_version < 1:
        _add(findings, "reconstruction.source_packet_ref.receipt_version_must_be_positive_integer")
    _instant(item.get("cutoff_at"), "reconstruction.cutoff_at", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_RECONSTRUCTION":
        _add(findings, "reconstruction.object_class_invalid")
    if item.get("claim_class") != "CUTOFF_ENTERPRISE_RECONSTRUCTION":
        _add(findings, "reconstruction.claim_class_invalid")
    if item.get("allowed_outputs") != reconstruction.ALLOWED_OUTPUTS:
        _add(findings, "reconstruction.allowed_outputs_invalid")
    if item.get("investment_authorization") != "NOT_AUTHORIZED":
        _add(findings, "reconstruction.investment_authorization_must_remain_not_authorized")
    if not isinstance(item.get("roles"), dict):
        _add(findings, "reconstruction.roles_required")
    if not isinstance(item.get("operating_system_model"), dict):
        _add(findings, "reconstruction.operating_system_model_required")
    if not isinstance(item.get("enterprise_context_snapshot"), dict):
        _add(findings, "reconstruction.enterprise_context_snapshot_required")
    if not isinstance(item.get("management_decision_ledger_slice"), dict):
        _add(findings, "reconstruction.management_decision_ledger_slice_required")
    if not isinstance(item.get("evidence_coverage"), dict):
        _add(findings, "reconstruction.evidence_coverage_required")
    else:
        coverage = _mapping(item.get("evidence_coverage"))
        if not isinstance(coverage.get("feedback_loops"), list):
            _add(findings, "reconstruction.evidence_coverage.feedback_loops_required")
        if not isinstance(coverage.get("sources"), list):
            _add(findings, "reconstruction.evidence_coverage.sources_required")
    if not isinstance(item.get("episode_component_refs"), list):
        _add(findings, "reconstruction.episode_component_refs_required")
    return item


def validate_mechanism_thread_set(
    thread_set: Any,
    *,
    episode_manifest: Any,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
    reconstruction_registry: Any | None = None,
) -> dict[str, Any]:
    """Validate the closed J2 contract and its J0/J1 object identities.

    Thread-level reference resolution is intentionally deferred to the
    projection so one bad binding does not invalidate unrelated claims.
    """
    findings: list[str] = []
    item = _closed(thread_set, _ROOT_KEYS, "mechanism_thread_set", findings)
    if item.get("schema_version") != SCHEMA_VERSION:
        _add(findings, "mechanism_thread_set.schema_version_invalid")
    _require_text(item, "thread_set_id", "mechanism_thread_set", findings)
    if item.get("outcome_access") != "NONE":
        _add(findings, "mechanism_thread_set.outcome_access_must_remain_none")
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_MECHANISM_THREAD_SET":
        _add(findings, "mechanism_thread_set.object_class_invalid")
    if item.get("claim_class") != "LOCAL_MECHANISM_THREADS":
        _add(findings, "mechanism_thread_set.claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        _add(findings, "mechanism_thread_set.allowed_outputs_must_exclude_forecast_comparative_and_investment")

    episode_ref = _closed(item.get("episode_ref"), _EPISODE_REF_KEYS, "mechanism_thread_set.episode_ref", findings)
    _require_text(episode_ref, "episode_id", "mechanism_thread_set.episode_ref", findings)
    _require_text(episode_ref, "schema_version", "mechanism_thread_set.episode_ref", findings)
    reconstruction_ref = _closed(
        item.get("reconstruction_ref"),
        _RECONSTRUCTION_REF_KEYS,
        "mechanism_thread_set.reconstruction_ref",
        findings,
    )
    _require_text(reconstruction_ref, "reconstruction_id", "mechanism_thread_set.reconstruction_ref", findings)
    _require_text(reconstruction_ref, "schema_version", "mechanism_thread_set.reconstruction_ref", findings)

    episode_validation = episode.validate_episode_manifest(episode_manifest)
    for finding in episode_validation["findings"]:
        _add(findings, "episode:" + finding)
    episode_item = _mapping(episode_manifest)
    reconstruction_item = _validate_reconstruction_shape(reconstruction_read_model, findings)
    inputs = _closed(
        reconstruction_inputs,
        _RECONSTRUCTION_INPUT_KEYS,
        "reconstruction_inputs",
        findings,
    )
    if set(inputs) == _RECONSTRUCTION_INPUT_KEYS:
        proof = reconstruction.validate_compiled_reconstruction(
            reconstruction_read_model,
            spec=inputs["spec"],
            source_packet_receipt=inputs["source_packet_receipt"],
            source_package=inputs["source_package"],
            enterprise_model=inputs["enterprise_model"],
            decision_ledger=inputs["decision_ledger"],
            decision_contract=inputs["decision_contract"],
        )
        for finding in proof["findings"]:
            _add(findings, "reconstruction_proof:" + str(finding))
        if reconstruction_registry is not None:
            frozen_binding = reconstruction.validate_frozen_reconstruction_binding(
                reconstruction_registry,
                reconstruction_read_model,
                inputs,
            )
            for finding in frozen_binding["findings"]:
                _add(findings, "reconstruction_registry:" + str(finding))
    if (
        episode_ref.get("episode_id") != episode_item.get("episode_id")
        or episode_ref.get("schema_version") != episode_item.get("schema_version")
    ):
        _add(findings, "mechanism_thread_set.episode_ref_must_match_bound_episode")
    if (
        reconstruction_ref.get("reconstruction_id") != reconstruction_item.get("reconstruction_id")
        or reconstruction_ref.get("schema_version") != reconstruction_item.get("schema_version")
    ):
        _add(findings, "mechanism_thread_set.reconstruction_ref_must_match_bound_reconstruction")
    for field in ("company_id", "issuer_id", "cutoff_at"):
        if episode_item.get(field) != reconstruction_item.get(field):
            _add(findings, f"mechanism_thread_set.{field}_must_match_j0_and_j1")
    if _mapping(episode_item.get("roles")) != _mapping(reconstruction_item.get("roles")):
        _add(findings, "mechanism_thread_set.roles_must_match_j0_and_j1")
    episode_components = {_mapping(raw).get("component_type"): _mapping(raw) for raw in _items(episode_item.get("component_refs"))}
    for raw in _items(reconstruction_item.get("episode_component_refs")):
        reference = _mapping(raw)
        if episode_components.get(reference.get("component_type")) != reference:
            _add(findings, "mechanism_thread_set.episode_components_must_match_bound_reconstruction")

    cutoff = _instant(episode_item.get("cutoff_at"), "episode.cutoff_at", findings)
    raw_threads = _items(item.get("threads"))
    if not 3 <= len(raw_threads) <= 5:
        _add(findings, "mechanism_thread_set.threads_must_contain_primary_plus_two_to_four_supporting_threads")
    threads = [
        _validate_thread_shape(raw, index=index, cutoff=cutoff, findings=findings)
        for index, raw in enumerate(raw_threads)
    ]
    seen_ids: set[str] = set()
    primary_count = 0
    for index, thread in enumerate(threads):
        thread_id = str(thread.get("thread_id", ""))
        if thread_id in seen_ids:
            _add(findings, f"mechanism_thread_set.threads[{index}].thread_id_duplicate")
        seen_ids.add(thread_id)
        primary_count += thread.get("role") == "PRIMARY"
    if primary_count != 1:
        _add(findings, "mechanism_thread_set.threads_must_have_exactly_one_primary_thread")

    for path in _forbidden_paths(item):
        _add(findings, "mechanism_thread_set.forbidden_pre_outcome_field:" + path)
    return {
        "valid": not findings,
        "findings": findings,
        "mechanism_thread_set": deepcopy(item) if not findings else None,
    }


def _hypothesis_signature(value: Any) -> list[tuple[Any, Any, Any]]:
    return sorted([
        (item.get("hypothesis_id"), item.get("role"), item.get("statement"))
        for item in map(_mapping, _items(value))
    ], key=lambda item: tuple(str(value) for value in item))


def _comparative_contract_reasons(
    thread: dict[str, Any],
    *,
    outcome_cells: dict[str, dict[str, Any]],
    j1_source_packet_refs: list[dict[str, Any]],
) -> list[str]:
    """Validate the pre-J4 semantic bridge without downgrading J2 itself."""
    reasons: list[str] = []
    contract_value = thread.get("comparative_projection_contract")
    relative_e3 = bool(
        thread.get("claim_type") == "RELATIVE_CAUSAL"
        and thread.get("e3_comparative_requested") is True
    )
    if not relative_e3:
        if contract_value is not None:
            _add(reasons, "COMPARATIVE_PROJECTION_CONTRACT_ONLY_ALLOWED_FOR_RELATIVE_CAUSAL_E3")
        return reasons
    if not isinstance(contract_value, dict):
        _add(reasons, "COMPARATIVE_PROJECTION_CONTRACT_REQUIRED")
        return reasons

    contract = _closed(
        contract_value,
        _COMPARATIVE_CONTRACT_KEYS,
        "comparative_projection_contract",
        reasons,
    )
    for path in _forbidden_paths(contract, "comparative_projection_contract"):
        _add(reasons, "COMPARATIVE_PROJECTION_CONTRACT_FORBIDDEN_PRE_OUTCOME_FIELD:" + path)

    hypotheses_by_role = {
        _mapping(raw).get("role"): _mapping(raw)
        for raw in _items(thread.get("hypotheses"))
    }
    raw_hypothesis_bindings = contract.get("hypothesis_bindings")
    actual_by_role: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_hypothesis_bindings, list) or len(raw_hypothesis_bindings) != 2:
        _add(reasons, "COMPARATIVE_HYPOTHESIS_BINDINGS_MUST_COVER_H_A_AND_H_B")
    else:
        for index, raw in enumerate(raw_hypothesis_bindings):
            binding = _closed(
                raw,
                _COMPARATIVE_HYPOTHESIS_BINDING_KEYS,
                f"comparative_projection_contract.hypothesis_bindings[{index}]",
                reasons,
            )
            role = binding.get("role")
            if role not in HYPOTHESIS_ROLES or role in actual_by_role:
                _add(reasons, "COMPARATIVE_HYPOTHESIS_BINDINGS_MUST_COVER_H_A_AND_H_B")
            else:
                actual_by_role[str(role)] = binding
        expected_by_role = {
            role: {
                "role": role,
                "j2_hypothesis_id": hypotheses_by_role.get(role, {}).get("hypothesis_id"),
                "j2_statement": hypotheses_by_role.get(role, {}).get("statement"),
                "v5_hypothesis_id": hypotheses_by_role.get(role, {}).get("hypothesis_id"),
                "v5_mechanism": hypotheses_by_role.get(role, {}).get("statement"),
            }
            for role in sorted(HYPOTHESIS_ROLES)
        }
        if actual_by_role != expected_by_role:
            _add(reasons, "COMPARATIVE_HYPOTHESES_MUST_PRESERVE_J2_SEMANTICS")

    expected_cell_ids = [str(value) for value in _items(thread.get("outcome_cell_refs"))]
    bound_cells: list[str] = []
    bound_metrics: list[str] = []
    raw_outcome_bindings = contract.get("outcome_bindings")
    if not isinstance(raw_outcome_bindings, list) or not raw_outcome_bindings:
        _add(reasons, "COMPARATIVE_OUTCOME_BINDINGS_REQUIRED")
    else:
        for index, raw in enumerate(raw_outcome_bindings):
            binding = _closed(
                raw,
                _COMPARATIVE_OUTCOME_BINDING_KEYS,
                f"comparative_projection_contract.outcome_bindings[{index}]",
                reasons,
            )
            cell_id = binding.get("outcome_cell_id")
            measurement_ref = binding.get("measurement_contract_ref")
            if cell_id not in expected_cell_ids or cell_id in bound_cells:
                _add(reasons, "COMPARATIVE_OUTCOME_CELLS_MUST_EXACTLY_COVER_J2_THREAD")
            else:
                bound_cells.append(str(cell_id))
            expected_measurement_ref = outcome_cells.get(str(cell_id), {}).get("measurement_contract_ref")
            if not _text(measurement_ref) or measurement_ref != expected_measurement_ref:
                _add(reasons, "COMPARATIVE_MEASUREMENT_REF_MUST_MATCH_J0_OUTCOME_CELL")
            v5_contracts = _items(binding.get("v5_measurement_contracts"))
            if len(v5_contracts) != 1 or not isinstance(v5_contracts[0], dict):
                _add(reasons, "COMPARATIVE_OUTCOME_CELL_MUST_BIND_EXACTLY_ONE_V5_MEASUREMENT_CONTRACT")
                continue
            metric_id = _mapping(v5_contracts[0]).get("metric_id")
            if not _text(metric_id) or metric_id != measurement_ref:
                _add(reasons, "COMPARATIVE_V5_METRIC_ID_MUST_MATCH_FROZEN_MEASUREMENT_REF")
            elif str(metric_id) in bound_metrics:
                _add(reasons, "COMPARATIVE_V5_METRICS_MUST_BE_UNIQUE")
            else:
                bound_metrics.append(str(metric_id))
        if set(bound_cells) != set(expected_cell_ids) or len(bound_cells) != len(expected_cell_ids):
            _add(reasons, "COMPARATIVE_OUTCOME_CELLS_MUST_EXACTLY_COVER_J2_THREAD")

    lineage = _closed(
        contract.get("source_lineage"),
        _COMPARATIVE_SOURCE_LINEAGE_KEYS,
        "comparative_projection_contract.source_lineage",
        reasons,
    )
    if _items(lineage.get("j1_source_packet_refs")) != j1_source_packet_refs:
        _add(reasons, "COMPARATIVE_J1_SOURCE_PACKET_LINEAGE_MUST_MATCH")
    if _items(lineage.get("j2_source_refs")) != _items(thread.get("source_refs")):
        _add(reasons, "COMPARATIVE_J2_SOURCE_LINEAGE_MUST_MATCH")
    if not isinstance(lineage.get("v5_source_provenance"), dict) or not lineage.get("v5_source_provenance"):
        _add(reasons, "COMPARATIVE_V5_SOURCE_PROVENANCE_REQUIRED")
    v5_sources = lineage.get("v5_sources")
    if (
        not isinstance(v5_sources, list)
        or not v5_sources
        or any(not isinstance(source, dict) for source in v5_sources)
    ):
        _add(reasons, "COMPARATIVE_V5_SOURCES_REQUIRED")
    return reasons


def _local_binding_reasons(
    thread: dict[str, Any],
    *,
    episode_thread: dict[str, Any] | None,
    claim_ids: set[str],
    outcome_cell_ids: set[str],
    loop_by_id: dict[str, dict[str, Any]],
    source_by_ref: dict[str, dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    if episode_thread is None:
        reasons.append("THREAD_NOT_IN_BOUND_EPISODE")
    else:
        comparisons = (
            (thread.get("role"), episode_thread.get("role"), "ROLE_MISMATCH"),
            (set(_items(thread.get("claim_ids"))), set(_items(episode_thread.get("claim_ids"))), "CLAIM_REFS_MISMATCH"),
            (_hypothesis_signature(thread.get("hypotheses")), _hypothesis_signature(episode_thread.get("hypotheses")), "HYPOTHESES_MISMATCH"),
            (_mapping(thread.get("observation_clock")).get("clock_id"), episode_thread.get("observation_clock_ref"), "OBSERVATION_CLOCK_MISMATCH"),
            (set(_items(thread.get("outcome_cell_refs"))), set(_items(episode_thread.get("outcome_cell_ids"))), "OUTCOME_CELL_REFS_MISMATCH"),
        )
        reasons.extend(reason for actual, expected, reason in comparisons if actual != expected)

    if any(claim_id not in claim_ids for claim_id in _items(thread.get("claim_ids"))):
        reasons.append("CLAIM_REF_NOT_IN_BOUND_EPISODE")
    if any(cell_id not in outcome_cell_ids for cell_id in _items(thread.get("outcome_cell_refs"))):
        reasons.append("OUTCOME_CELL_REF_NOT_IN_BOUND_EPISODE")

    boundary = _mapping(thread.get("responsibility_boundary"))
    expected_scope = (boundary.get("responsibility_unit_id"), boundary.get("arena_id"))
    selected_loop_source_refs: set[str] = set()
    for loop_id in _items(thread.get("reconstruction_loop_ids")):
        loop = loop_by_id.get(str(loop_id))
        if loop is None:
            reasons.append("RECONSTRUCTION_LOOP_REF_UNKNOWN:" + str(loop_id))
        else:
            selected_loop_source_refs.update(str(ref) for ref in _items(loop.get("evidence_refs")))
            if (loop.get("responsibility_unit_id"), loop.get("arena_id")) != expected_scope:
                reasons.append("RECONSTRUCTION_LOOP_RESPONSIBILITY_BOUNDARY_MISMATCH:" + str(loop_id))

    for raw_source in _items(thread.get("source_refs")):
        source_ref = str(_mapping(raw_source).get("source_ref"))
        source = source_by_ref.get(source_ref)
        if source is None:
            reasons.append("SOURCE_REF_UNKNOWN:" + source_ref)
            continue
        if source_ref not in selected_loop_source_refs:
            reasons.append("SOURCE_NOT_IN_REFERENCED_LOOPS:" + source_ref)
        status = source.get("status")
        if status not in SOURCE_ELIGIBILITY:
            reasons.append("SOURCE_STATUS_INVALID:" + source_ref)
        elif status == "EVIDENCE_INELIGIBLE":
            reasons.append("SOURCE_EVIDENCE_INELIGIBLE:" + source_ref)
        if expected_scope[0] not in _items(source.get("responsibility_boundary_ids")):
            reasons.append("SOURCE_RESPONSIBILITY_BOUNDARY_MISMATCH:" + source_ref)
    return list(dict.fromkeys(reasons))


def compile_mechanism_thread_projection(
    thread_set: Any,
    *,
    episode_manifest: Any,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
    reconstruction_registry: Any | None = None,
) -> dict[str, Any]:
    """Resolve J2 locally and derive thread/claim permissions without promotion."""
    validation = validate_mechanism_thread_set(
        thread_set,
        episode_manifest=episode_manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=reconstruction_registry,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "mechanism_thread_read_model": None}

    item = _mapping(thread_set)
    episode_item = _mapping(episode_manifest)
    reconstruction_item = _mapping(reconstruction_read_model)
    episode_projection = episode.compile_episode_read_model(episode_manifest)
    episode_rows = {
        row["claim_id"]: row for row in episode_projection["episode_read_model"]["claim_output_matrix"]
    }
    claims = {_mapping(raw).get("claim_id"): _mapping(raw) for raw in _items(episode_item.get("claims"))}
    outcome_cells = {
        _mapping(raw).get("outcome_cell_id"): _mapping(raw) for raw in _items(episode_item.get("outcome_cells"))
    }
    expected_threads = {
        _mapping(raw).get("thread_id"): _mapping(raw) for raw in _items(episode_item.get("mechanism_threads"))
    }
    loops = _items(_mapping(reconstruction_item.get("evidence_coverage")).get("feedback_loops"))
    loop_by_id = {_mapping(raw).get("loop_id"): _mapping(raw) for raw in loops}
    sources = _items(_mapping(reconstruction_item.get("evidence_coverage")).get("sources"))
    source_by_ref = {_mapping(raw).get("source_ref"): _mapping(raw) for raw in sources}

    thread_views: list[dict[str, Any]] = []
    supplied_ids: set[str] = set()
    claim_thread_blockers: dict[str, list[dict[str, str]]] = {str(claim_id): [] for claim_id in claims}
    claim_thread_outputs: dict[str, list[list[str]]] = {str(claim_id): [] for claim_id in claims}
    claim_thread_ids: dict[str, list[str]] = {str(claim_id): [] for claim_id in claims}

    for raw in _items(item.get("threads")):
        thread = _mapping(raw)
        thread_id = str(thread["thread_id"])
        supplied_ids.add(thread_id)
        reasons = _local_binding_reasons(
            thread,
            episode_thread=expected_threads.get(thread_id),
            claim_ids={str(value) for value in claims},
            outcome_cell_ids={str(value) for value in outcome_cells},
            loop_by_id=loop_by_id,
            source_by_ref=source_by_ref,
        )
        comparative_contract_findings = _comparative_contract_reasons(
            thread,
            outcome_cells={str(key): value for key, value in outcome_cells.items()},
            j1_source_packet_refs=[deepcopy(reconstruction_item["source_packet_ref"])],
        )
        if thread.get("local_status") in _BLOCKING_LOCAL_STATUSES:
            reasons.append("LOCAL_STATUS:" + str(thread.get("local_status")))
        resolved = not reasons
        permitted_outputs = list(thread["permitted_outputs"]) if resolved else ["RESEARCH_AGENDA"]
        dependent_claim_ids = [claim_id for claim_id in _items(thread.get("claim_ids")) if claim_id in claims]
        j3_eligible = bool(
            resolved
            and thread.get("claim_type") in _FORECASTABLE_CLAIM_TYPES
            and thread.get("local_status") in {"OBSERVED", "INFERRED"}
            and thread.get("evidence_ceiling") in {"TEACHING", "MECHANISM"}
            and all(len(episode_rows[claim_id]["allowed_outputs"]) > 1 for claim_id in dependent_claim_ids)
        )
        j4_eligible = bool(
            resolved
            and not comparative_contract_findings
            and thread.get("claim_type") == "RELATIVE_CAUSAL"
            and thread.get("e3_comparative_requested") is True
            and thread.get("local_status") in {"OBSERVED", "INFERRED"}
            and thread.get("evidence_ceiling") == "MECHANISM"
        )
        thread_views.append({
            "thread_id": thread_id,
            "role": thread["role"],
            "claim_type": thread["claim_type"],
            "resolution_status": "RESOLVED" if resolved else "BOUNDARY_ONLY",
            "binding_findings": reasons,
            "claim_ids": list(thread["claim_ids"]),
            "hypotheses": deepcopy(thread["hypotheses"]),
            "responsibility_boundary": deepcopy(thread["responsibility_boundary"]),
            "outcome_cell_refs": list(thread["outcome_cell_refs"]),
            "source_refs": deepcopy(thread["source_refs"]),
            "local_status": thread["local_status"],
            "evidence_ceiling": thread["evidence_ceiling"],
            "permitted_outputs": permitted_outputs,
            "j3_forecast_eligible": j3_eligible,
            "e3_comparative_requested": thread["e3_comparative_requested"],
            "j4_comparative_eligible": j4_eligible,
            "comparative_projection_contract": deepcopy(
                thread.get("comparative_projection_contract")
            ),
            "comparative_contract_findings": comparative_contract_findings,
            "forecast_performed": False,
            "comparative_performed": False,
        })
        for claim_id in dependent_claim_ids:
            if thread_id not in claim_thread_ids[claim_id]:
                claim_thread_ids[claim_id].append(thread_id)
            if reasons:
                claim_thread_blockers[claim_id].extend(
                    {"thread_id": thread_id, "reason": reason} for reason in reasons
                )
            else:
                claim_thread_outputs[claim_id].append(permitted_outputs)

    for thread_id, expected in expected_threads.items():
        if thread_id in supplied_ids:
            continue
        reason = "THREAD_DETAIL_MISSING"
        thread_views.append({
            "thread_id": thread_id,
            "role": expected.get("role"),
            "claim_type": None,
            "resolution_status": "BOUNDARY_ONLY",
            "binding_findings": [reason],
            "claim_ids": list(_items(expected.get("claim_ids"))),
            "hypotheses": deepcopy(_items(expected.get("hypotheses"))),
            "responsibility_boundary": None,
            "outcome_cell_refs": list(_items(expected.get("outcome_cell_ids"))),
            "source_refs": [],
            "local_status": "UNKNOWN",
            "evidence_ceiling": None,
            "permitted_outputs": ["RESEARCH_AGENDA"],
            "j3_forecast_eligible": False,
            "e3_comparative_requested": False,
            "j4_comparative_eligible": False,
            "comparative_projection_contract": None,
            "comparative_contract_findings": ["COMPARATIVE_PROJECTION_CONTRACT_NOT_APPLICABLE"],
            "forecast_performed": False,
            "comparative_performed": False,
        })
        for claim_id in _items(expected.get("claim_ids")):
            if claim_id not in claims:
                continue
            if thread_id not in claim_thread_ids[claim_id]:
                claim_thread_ids[claim_id].append(str(thread_id))
            claim_thread_blockers[claim_id].append({"thread_id": str(thread_id), "reason": reason})

    claim_permissions: list[dict[str, Any]] = []
    for claim_id, row in episode_rows.items():
        blockers = list(row["blocked_by"])
        blockers.extend(claim_thread_blockers[claim_id])
        dependent_threads = claim_thread_ids[claim_id]
        if blockers:
            allowed_outputs = ["RESEARCH_AGENDA"]
        elif dependent_threads:
            thread_output_sets = claim_thread_outputs[claim_id]
            allowed_outputs = [
                output
                for output in thread_output_sets[0]
                if all(output in outputs for outputs in thread_output_sets[1:])
            ]
        else:
            allowed_outputs = list(row["allowed_outputs"])
        claim_permissions.append({
            "claim_id": claim_id,
            "dependent_thread_ids": dependent_threads,
            "allowed_outputs": allowed_outputs,
            "blocked_by": blockers,
        })

    return {
        "valid": True,
        "findings": [],
        "mechanism_thread_read_model": {
            "schema_version": SCHEMA_VERSION,
            "thread_set_id": item["thread_set_id"],
            "episode_ref": deepcopy(item["episode_ref"]),
            "reconstruction_ref": deepcopy(item["reconstruction_ref"]),
            "company_id": episode_item["company_id"],
            "issuer_id": episode_item["issuer_id"],
            "cutoff_at": episode_item["cutoff_at"],
            "source_packet_refs": [deepcopy(reconstruction_item["source_packet_ref"])],
            "thread_views": thread_views,
            "claim_permissions": claim_permissions,
            "allowed_outputs": list(ALLOWED_OUTPUTS),
            "forecast_authorization": "NOT_AUTHORIZED",
            "comparative_authorization": "NOT_AUTHORIZED",
            "investment_authorization": "NOT_AUTHORIZED",
        },
    }
