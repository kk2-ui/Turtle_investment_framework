#!/usr/bin/env python3
"""Read-only contract for a multi-dimensional Enterprise Judgment Episode.

An episode is a composition of existing judgment artifacts, not a new
canonical store.  This module deliberately accepts references and bounded
claim/cell metadata only.  It cannot carry an outcome value, price, valuation,
or investment instruction.  The derived claim/output matrix makes the
cell-level permission boundary explicit: a coverage or measurement failure
blocks only the claims that depend on that cell.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "enterprise-judgment-episode-manifest.v2"
LEGACY_SCHEMA_VERSION = "enterprise-judgment-episode-manifest.v1"
ALLOWED_OUTPUTS = ["EPISODE_READ_MODEL", "RESEARCH_AGENDA"]

ADMISSION_LEVELS = (
    "E0_CONTEXT",
    "E1_RECONSTRUCTION",
    "E2_MECHANISM_PROBE",
    "E3_COMPARATIVE_LAB",
    "E4_TRANSFER_AND_UTILITY",
)
_ADMISSION_RANK = {level: index for index, level in enumerate(ADMISSION_LEVELS)}

CLAIM_STATES = {
    "OBSERVED",
    "INFERRED",
    "UNKNOWN",
    "EVIDENCE_INELIGIBLE",
    "NOT_APPLICABLE",
}
OUTCOME_CELL_STATES = CLAIM_STATES | {"MEASUREMENT_MISMATCH"}
BLOCKING_CELL_STATES = {
    "UNKNOWN",
    "EVIDENCE_INELIGIBLE",
    "MEASUREMENT_MISMATCH",
    "NOT_APPLICABLE",
}
CLAIM_DOMAINS = {
    "CUSTOMER",
    "COMPETITION",
    "OPERATIONS",
    "ORGANIZATION",
    "CAPITAL_ALLOCATION",
    "CASH",
    "PERMANENT_LOSS",
    "LIFECYCLE",
}
JUDGMENT_DIMENSIONS = {
    "INITIAL_CONDITIONS",
    "IMPLEMENTED_MANAGEMENT_ACTION",
    "EXECUTION",
    "CUSTOMER_COMPETITION_RESPONSE",
    "UNIT_ECONOMICS",
    "WORKING_CAPITAL_CASH_CAPITAL",
    "ADAPTATION_PERMANENT_LOSS",
    "STRONGEST_ALTERNATIVE_EXPLANATION",
}
OUTCOME_DIMENSIONS = {
    "CUSTOMER",
    "OPERATIONS",
    "COMPETITION",
    "CASH",
    "CAPITAL_RETURN",
    "LEVERAGE",
    "PERMANENT_LOSS",
}
COMPONENT_TYPES = {
    "ENTERPRISE_CONTEXT_SNAPSHOT",
    "ENTERPRISE_SYSTEM_MODEL",
    "MANAGEMENT_DECISION_LEDGER",
    "MANAGEMENT_DECISION_OBSERVATION",
    "FORECAST_BUNDLE",
    "COMPARATIVE_EPISODE",
    "OUTCOME_MEASUREMENT_CONTRACT",
}
THREAD_ROLES = {"PRIMARY", "SUPPORTING"}
QUESTION_ROLES = {"PRIMARY", "SUPPORTING"}

_ROOT_KEYS = {
    "schema_version",
    "episode_id",
    "company_id",
    "issuer_id",
    "cutoff_at",
    "decision_contract_ref",
    "component_refs",
    "question_set",
    "claims",
    "mechanism_threads",
    "outcome_cells",
    "roles",
    "object_class",
    "claim_class",
    "allowed_outputs",
}
_CONTRACT_REF_KEYS = {"contract_id", "contract_version"}
_COMPONENT_KEYS = {"component_type", "component_id", "component_version", "admission_level", "read_only"}
_QUESTION_KEYS = {"question_id", "role", "question", "claim_ids"}
_CLAIM_KEYS = {
    "claim_id",
    "question_id",
    "method_id",
    "judgment_dimension",
    "claim_scope",
    "domain",
    "statement",
    "cell_status",
    "admission_level",
    "evidence_refs",
    "evidence_locator_refs",
    "dependent_outcome_cell_ids",
    "decision_observation_ref",
    "decision_observation_treatment",
}
_CLAIM_SCOPE_KEYS = {
    "issuer_ids",
    "product_or_service_ids",
    "plant_ids",
    "channel_ids",
    "region_ids",
    "arena_ids",
}
_THREAD_KEYS = {
    "thread_id",
    "role",
    "claim_ids",
    "hypotheses",
    "observation_clock_ref",
    "outcome_cell_ids",
}
_HYPOTHESIS_KEYS = {"hypothesis_id", "role", "statement"}
_OUTCOME_CELL_KEYS = {
    "outcome_cell_id",
    "dimension",
    "status",
    "measurement_contract_ref",
    "custodian_receipt_ref",
}
_ROLE_KEYS = {"judgment_owner_id", "independent_challenger_id", "outcome_custodian_id"}

_FORBIDDEN_KEYS = {
    "price",
    "market_price",
    "share_price",
    "stock_price",
    "entry_price",
    "valuation",
    "valuation_result",
    "expectation_gap",
    "buyband",
    "buy_band",
    "investment_instruction",
    "portfolio_action",
    "position",
    "actual_value",
    "outcome_value",
    "outcome_result",
    "settlement_value",
    "training_score",
}

_OUTPUTS_BY_ADMISSION = {
    "E0_CONTEXT": ["STATE_VIEW", "RESEARCH_AGENDA"],
    "E1_RECONSTRUCTION": ["STATE_VIEW", "DECISION_VIEW", "CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"],
    "E2_MECHANISM_PROBE": ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
    "E3_COMPARATIVE_LAB": ["COMPARATIVE_VIEW", "COMPARATIVE_CANDIDATE", "RESEARCH_AGENDA"],
    "E4_TRANSFER_AND_UTILITY": ["TRANSFER_CANDIDATE", "DECISION_UTILITY_EVALUATION", "RESEARCH_AGENDA"],
}


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


def _unique_ids(items: list[dict[str, Any]], field: str, path: str, findings: list[str]) -> set[str]:
    values: set[str] = set()
    for index, item in enumerate(items):
        value = _require_text(item, field, f"{path}[{index}]", findings)
        if value and value in values:
            _add(findings, f"{path}[{index}].{field}_duplicate")
        values.add(value)
    return values


def _unique_text_list(value: Any, path: str, findings: list[str], *, required: bool = False) -> list[str]:
    if not isinstance(value, list):
        _add(findings, path + "_must_be_list")
        return []
    values: list[str] = []
    for index, raw in enumerate(value):
        if not _text(raw):
            _add(findings, f"{path}[{index}]_must_be_nonempty_text")
            continue
        text = str(raw)
        if text in values:
            _add(findings, f"{path}[{index}]_duplicate")
        else:
            values.append(text)
    if required and not values:
        _add(findings, path + "_required")
    return values


def _validate_claim_scope(
    value: Any, *, issuer_id: str, path: str, findings: list[str],
) -> dict[str, Any]:
    scope = _closed(value, _CLAIM_SCOPE_KEYS, path, findings)
    values = {
        field: _unique_text_list(
            scope.get(field), f"{path}.{field}", findings, required=field == "issuer_ids",
        )
        for field in _CLAIM_SCOPE_KEYS
    }
    if issuer_id and issuer_id not in values["issuer_ids"]:
        _add(findings, path + ".issuer_ids_must_include_episode_issuer")
    return scope


def _forbidden_paths(value: Any, path: str = "episode") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if (
                key_text in _FORBIDDEN_KEYS
                or key_text.startswith("actual_")
                or key_text.startswith("settlement_")
                or key_text.endswith("_market_price")
                or key_text.endswith("_share_price")
                or key_text.endswith("_stock_price")
            ):
                findings.append(child_path)
            else:
                findings.extend(_forbidden_paths(nested, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return findings


def _rank(level: Any) -> int:
    return _ADMISSION_RANK.get(str(level), -1)


def _validate_contract_ref(value: Any, findings: list[str]) -> dict[str, Any]:
    item = _closed(value, _CONTRACT_REF_KEYS, "episode.decision_contract_ref", findings)
    _require_text(item, "contract_id", "episode.decision_contract_ref", findings)
    version = item.get("contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        _add(findings, "episode.decision_contract_ref.contract_version_must_be_positive_integer")
    return item


def _validate_component_refs(value: Any, findings: list[str]) -> dict[str, dict[str, Any]]:
    raw_items = _items(value)
    if not raw_items:
        _add(findings, "episode.component_refs_required")
    refs = [_closed(raw, _COMPONENT_KEYS, f"episode.component_refs[{index}]", findings) for index, raw in enumerate(raw_items)]
    seen: set[str] = set()
    by_type: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(refs):
        component_type = _require_text(ref, "component_type", f"episode.component_refs[{index}]", findings)
        component_id = _require_text(ref, "component_id", f"episode.component_refs[{index}]", findings)
        _require_text(ref, "component_version", f"episode.component_refs[{index}]", findings)
        level = ref.get("admission_level")
        if level not in ADMISSION_LEVELS:
            _add(findings, f"episode.component_refs[{index}].admission_level_invalid")
        if component_type not in COMPONENT_TYPES:
            _add(findings, f"episode.component_refs[{index}].component_type_invalid")
        if ref.get("read_only") is not True:
            _add(findings, f"episode.component_refs[{index}].must_be_read_only")
        if component_type in seen:
            _add(findings, f"episode.component_refs[{index}].component_type_duplicate")
        seen.add(component_type)
        if component_type:
            by_type[component_type] = ref
        if not component_id:
            continue
    if "ENTERPRISE_CONTEXT_SNAPSHOT" not in by_type:
        _add(findings, "episode.enterprise_context_snapshot_required")
    return by_type


def _validate_questions(value: Any, findings: list[str]) -> tuple[list[dict[str, Any]], set[str]]:
    raw_items = _items(value)
    if not 3 <= len(raw_items) <= 5:
        _add(findings, "episode.question_set_must_contain_three_to_five_questions")
    questions = [_closed(raw, _QUESTION_KEYS, f"episode.question_set[{index}]", findings) for index, raw in enumerate(raw_items)]
    ids = _unique_ids(questions, "question_id", "episode.question_set", findings)
    primary_count = 0
    for index, question in enumerate(questions):
        role = question.get("role")
        if role not in QUESTION_ROLES:
            _add(findings, f"episode.question_set[{index}].role_invalid")
        primary_count += role == "PRIMARY"
        _require_text(question, "question", f"episode.question_set[{index}]", findings)
        claim_ids = question.get("claim_ids")
        if not isinstance(claim_ids, list) or not claim_ids or any(not _text(item) for item in claim_ids):
            _add(findings, f"episode.question_set[{index}].claim_ids_required")
    if primary_count != 1:
        _add(findings, "episode.question_set_must_have_exactly_one_primary_question")
    return questions, ids


def _validate_claims(
    value: Any,
    question_ids: set[str],
    issuer_id: str,
    evidence_locator_ids: set[str] | None,
    require_typed_contract: bool,
    findings: list[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    raw_items = _items(value)
    if not raw_items:
        _add(findings, "episode.claims_required")
    claims = [
        _closed(
            raw, _CLAIM_KEYS, f"episode.claims[{index}]", findings,
            required=(
                _CLAIM_KEYS - {"decision_observation_ref", "decision_observation_treatment"}
                if require_typed_contract
                else _CLAIM_KEYS - {
                    "method_id", "judgment_dimension", "claim_scope", "evidence_locator_refs",
                    "decision_observation_ref", "decision_observation_treatment",
                }
            ),
        )
        for index, raw in enumerate(raw_items)
    ]
    ids = _unique_ids(claims, "claim_id", "episode.claims", findings)
    for index, claim in enumerate(claims):
        question_id = _require_text(claim, "question_id", f"episode.claims[{index}]", findings)
        if question_id and question_id not in question_ids:
            _add(findings, f"episode.claims[{index}].question_id_unknown")
        if require_typed_contract or "method_id" in claim:
            _require_text(claim, "method_id", f"episode.claims[{index}]", findings)
        if require_typed_contract or "judgment_dimension" in claim:
            if claim.get("judgment_dimension") not in JUDGMENT_DIMENSIONS:
                _add(findings, f"episode.claims[{index}].judgment_dimension_invalid")
        if require_typed_contract or "claim_scope" in claim:
            _validate_claim_scope(
                claim.get("claim_scope"),
                issuer_id=issuer_id,
                path=f"episode.claims[{index}].claim_scope",
                findings=findings,
            )
        if claim.get("domain") not in CLAIM_DOMAINS:
            _add(findings, f"episode.claims[{index}].domain_invalid")
        _require_text(claim, "statement", f"episode.claims[{index}]", findings)
        if claim.get("cell_status") not in CLAIM_STATES:
            _add(findings, f"episode.claims[{index}].cell_status_invalid")
        if claim.get("admission_level") not in ADMISSION_LEVELS:
            _add(findings, f"episode.claims[{index}].admission_level_invalid")
        evidence_refs = claim.get("evidence_refs")
        if not isinstance(evidence_refs, list) or any(not _text(item) for item in evidence_refs):
            _add(findings, f"episode.claims[{index}].evidence_refs_invalid")
        elif claim.get("cell_status") in {"OBSERVED", "INFERRED", "EVIDENCE_INELIGIBLE"} and not evidence_refs:
            _add(findings, f"episode.claims[{index}].evidence_refs_required_for_status")
        locator_refs = (
            _unique_text_list(
                claim.get("evidence_locator_refs"),
                f"episode.claims[{index}].evidence_locator_refs",
                findings,
            )
            if require_typed_contract or "evidence_locator_refs" in claim
            else []
        )
        if require_typed_contract and claim.get("cell_status") in {"OBSERVED", "INFERRED", "EVIDENCE_INELIGIBLE"} and not locator_refs:
            _add(findings, f"episode.claims[{index}].evidence_locator_refs_required_for_status")
        if evidence_locator_ids is not None:
            for locator_ref in locator_refs:
                if locator_ref not in evidence_locator_ids:
                    _add(findings, f"episode.claims[{index}].evidence_locator_ref_unknown:{locator_ref}")
        dependencies = claim.get("dependent_outcome_cell_ids")
        if not isinstance(dependencies, list) or any(not _text(item) for item in dependencies):
            _add(findings, f"episode.claims[{index}].dependent_outcome_cell_ids_invalid")
        observation_ref = claim.get("decision_observation_ref", "")
        treatment = claim.get("decision_observation_treatment", "")
        if observation_ref not in {"", None} and not _text(observation_ref):
            _add(findings, f"episode.claims[{index}].decision_observation_ref_invalid")
        if observation_ref and treatment not in {"ACTION_DEPENDENT", "OBSERVATION_BOUNDARY"}:
            _add(findings, f"episode.claims[{index}].decision_observation_treatment_invalid")
        if not observation_ref and treatment not in {"", None}:
            _add(findings, f"episode.claims[{index}].decision_observation_treatment_requires_ref")
    return claims, ids


def _validate_threads(value: Any, claim_ids: set[str], outcome_cell_ids: set[str], findings: list[str]) -> list[dict[str, Any]]:
    raw_items = _items(value)
    threads = [_closed(raw, _THREAD_KEYS, f"episode.mechanism_threads[{index}]", findings) for index, raw in enumerate(raw_items)]
    _unique_ids(threads, "thread_id", "episode.mechanism_threads", findings)
    primary_count = 0
    for index, thread in enumerate(threads):
        role = thread.get("role")
        if role not in THREAD_ROLES:
            _add(findings, f"episode.mechanism_threads[{index}].role_invalid")
        primary_count += role == "PRIMARY"
        linked_claims = thread.get("claim_ids")
        if (
            not isinstance(linked_claims, list)
            or not linked_claims
            or any(not _text(item) or item not in claim_ids for item in linked_claims)
        ):
            _add(findings, f"episode.mechanism_threads[{index}].claim_ids_must_reference_claims")
        hypotheses = _items(thread.get("hypotheses"))
        if len(hypotheses) != 2:
            _add(findings, f"episode.mechanism_threads[{index}].hypotheses_must_contain_h_a_and_h_b")
        roles: set[str] = set()
        for hypothesis_index, raw_hypothesis in enumerate(hypotheses):
            hypothesis = _closed(
                raw_hypothesis,
                _HYPOTHESIS_KEYS,
                f"episode.mechanism_threads[{index}].hypotheses[{hypothesis_index}]",
                findings,
            )
            _require_text(hypothesis, "hypothesis_id", f"episode.mechanism_threads[{index}].hypotheses[{hypothesis_index}]", findings)
            role_value = hypothesis.get("role")
            if role_value not in {"H_A", "H_B"}:
                _add(findings, f"episode.mechanism_threads[{index}].hypotheses[{hypothesis_index}].role_invalid")
            roles.add(str(role_value))
            _require_text(hypothesis, "statement", f"episode.mechanism_threads[{index}].hypotheses[{hypothesis_index}]", findings)
        if roles != {"H_A", "H_B"}:
            _add(findings, f"episode.mechanism_threads[{index}].hypotheses_must_distinguish_h_a_h_b")
        _require_text(thread, "observation_clock_ref", f"episode.mechanism_threads[{index}]", findings)
        linked_cells = thread.get("outcome_cell_ids")
        if (
            not isinstance(linked_cells, list)
            or not linked_cells
            or any(not _text(item) or item not in outcome_cell_ids for item in linked_cells)
        ):
            _add(findings, f"episode.mechanism_threads[{index}].outcome_cell_ids_must_reference_cells")
    if threads and primary_count != 1:
        _add(findings, "episode.mechanism_threads_must_have_exactly_one_primary_thread")
    if threads and not 3 <= len(threads) <= 5:
        _add(findings, "episode.mechanism_threads_must_contain_primary_plus_two_to_four_supporting_threads")
    return threads


def _validate_outcome_cells(value: Any, findings: list[str]) -> tuple[list[dict[str, Any]], set[str]]:
    raw_items = _items(value)
    if not raw_items:
        _add(findings, "episode.outcome_cells_required")
    cells = [_closed(raw, _OUTCOME_CELL_KEYS, f"episode.outcome_cells[{index}]", findings) for index, raw in enumerate(raw_items)]
    ids = _unique_ids(cells, "outcome_cell_id", "episode.outcome_cells", findings)
    for index, cell in enumerate(cells):
        if cell.get("dimension") not in OUTCOME_DIMENSIONS:
            _add(findings, f"episode.outcome_cells[{index}].dimension_invalid")
        status = cell.get("status")
        if status not in OUTCOME_CELL_STATES:
            _add(findings, f"episode.outcome_cells[{index}].status_invalid")
        if status == "OBSERVED":
            _require_text(cell, "custodian_receipt_ref", f"episode.outcome_cells[{index}]", findings)
        if status == "MEASUREMENT_MISMATCH":
            _require_text(cell, "measurement_contract_ref", f"episode.outcome_cells[{index}]", findings)
    return cells, ids


def _validate_bindings(
    item: dict[str, Any],
    *,
    decision_contract: Any | None,
    enterprise_bundle: Any | None,
    reconstruction_binding: Any | None,
    findings: list[str],
) -> None:
    """Optionally prove manifest references against existing canonical objects."""
    if decision_contract is not None:
        try:
            from scripts import judgment_training_decision_contract as contract_module
        except ModuleNotFoundError:  # pragma: no cover - direct script import
            import judgment_training_decision_contract as contract_module
        validation = contract_module.validate_training_decision_contract(decision_contract)
        for finding in validation["findings"]:
            _add(findings, "decision_contract:" + finding)
        contract = _mapping(decision_contract)
        ref = _mapping(item.get("decision_contract_ref"))
        if (
            ref.get("contract_id") != contract.get("contract_id")
            or ref.get("contract_version") != contract.get("contract_version")
        ):
            _add(findings, "episode.decision_contract_ref_must_match_bound_contract")
        for field in ("company_id", "issuer_id", "cutoff_at"):
            if item.get(field) != contract.get(field):
                _add(findings, f"episode.{field}_must_match_bound_decision_contract")

    if enterprise_bundle is not None:
        try:
            from scripts import enterprise_judgment_v3 as v3
        except ModuleNotFoundError:  # pragma: no cover - direct script import
            import enterprise_judgment_v3 as v3
        validation = v3.validate_enterprise_judgment_bundle(enterprise_bundle)
        for finding in validation["findings"]:
            _add(findings, "enterprise_bundle:" + finding)
        bundle = _mapping(enterprise_bundle)
        model = _mapping(bundle.get("enterprise_system_model"))
        ledger = _mapping(bundle.get("management_decision_ledger"))
        component_by_type = {
            _mapping(raw).get("component_type"): _mapping(raw)
            for raw in _items(item.get("component_refs"))
        }
        model_ref = component_by_type.get("ENTERPRISE_SYSTEM_MODEL", {})
        ledger_ref = component_by_type.get("MANAGEMENT_DECISION_LEDGER", {})
        if model_ref and (
            model_ref.get("component_id") != model.get("model_id")
            or model_ref.get("component_version") != model.get("version")
        ):
            _add(findings, "episode.enterprise_system_model_ref_must_match_bound_bundle")
        if ledger_ref and ledger_ref.get("component_id") != ledger.get("ledger_id"):
            _add(findings, "episode.management_decision_ledger_ref_must_match_bound_bundle")
        if model_ref and item.get("issuer_id") != model.get("company_id"):
            _add(findings, "episode.issuer_id_must_match_bound_enterprise_model")
        if model_ref and item.get("cutoff_at") != model.get("as_of"):
            _add(findings, "episode.cutoff_at_must_match_bound_enterprise_model")
        model_arena_ids = set(_items(model.get("competitive_arena_ids")))
        for index, raw_claim in enumerate(_items(item.get("claims"))):
            scope = _mapping(_mapping(raw_claim).get("claim_scope"))
            arena_ids = set(_items(scope.get("arena_ids")))
            if arena_ids and not arena_ids <= model_arena_ids:
                _add(findings, f"episode.claims[{index}].claim_scope.arena_ids_must_exist_in_bound_enterprise_model")

    if reconstruction_binding is not None:
        if enterprise_bundle is not None:
            _add(findings, "episode.enterprise_bundle_and_reconstruction_binding_are_mutually_exclusive")
        try:
            from scripts import enterprise_judgment_reconstruction as reconstruction_module
        except ModuleNotFoundError:  # pragma: no cover - direct script import
            import enterprise_judgment_reconstruction as reconstruction_module
        binding = _closed(
            reconstruction_binding,
            {
                "reconstruction", "spec", "source_packet_receipt", "source_package",
                "enterprise_model", "decision_ledger",
            },
            "episode.reconstruction_binding",
            findings,
        )
        if decision_contract is None:
            _add(findings, "episode.reconstruction_binding_requires_bound_decision_contract")
            return
        validation = reconstruction_module.validate_compiled_reconstruction(
            binding.get("reconstruction"),
            spec=binding.get("spec"),
            source_packet_receipt=binding.get("source_packet_receipt"),
            source_package=binding.get("source_package"),
            enterprise_model=binding.get("enterprise_model"),
            decision_ledger=binding.get("decision_ledger"),
            decision_contract=decision_contract,
        )
        for finding in validation["findings"]:
            _add(findings, "reconstruction_binding:" + finding)
        reconstruction = _mapping(binding.get("reconstruction"))
        component_by_type = {
            _mapping(raw).get("component_type"): _mapping(raw)
            for raw in _items(item.get("component_refs"))
        }
        for reference in _items(reconstruction.get("episode_component_refs")):
            expected = _mapping(reference)
            actual = component_by_type.get(expected.get("component_type"))
            if actual != expected:
                _add(findings, "episode.component_refs_must_match_bound_reconstruction")
        for field in ("company_id", "issuer_id", "cutoff_at"):
            if item.get(field) != reconstruction.get(field):
                _add(findings, f"episode.{field}_must_match_bound_reconstruction")
        if _mapping(item.get("roles")) != _mapping(reconstruction.get("roles")):
            _add(findings, "episode.roles_must_match_bound_reconstruction")

        source_status_by_ref = {
            entry.get("source_ref"): entry.get("status")
            for entry in map(_mapping, _items(_mapping(reconstruction.get("evidence_coverage")).get("sources")))
        }
        observation = _mapping(_mapping(reconstruction.get("management_decision_ledger_slice")).get("decision_observation"))
        observation_id = observation.get("observation_id")
        observation_status = observation.get("status")
        for index, claim in enumerate(_items(item.get("claims"))):
            claim_value = _mapping(claim)
            if claim_value.get("admission_level") != "E1_RECONSTRUCTION":
                continue
            claim_refs = _items(claim_value.get("evidence_refs"))
            if any(ref not in source_status_by_ref for ref in claim_refs):
                _add(findings, f"episode.claims[{index}].evidence_refs_must_be_in_bound_reconstruction")
            known_ref_states = [source_status_by_ref.get(ref) for ref in claim_refs if ref in source_status_by_ref]
            if known_ref_states and all(state == "EVIDENCE_INELIGIBLE" for state in known_ref_states):
                if claim_value.get("cell_status") not in {"EVIDENCE_INELIGIBLE", "UNKNOWN"}:
                    _add(findings, f"episode.claims[{index}].ineligible_evidence_cannot_support_active_claim")
            observation_ref = claim_value.get("decision_observation_ref", "")
            treatment = claim_value.get("decision_observation_treatment", "")
            if observation_ref:
                if observation_ref != observation_id:
                    _add(findings, f"episode.claims[{index}].decision_observation_ref_must_match_bound_reconstruction")
                elif treatment == "ACTION_DEPENDENT":
                    required_status = {
                        "NO_MATERIAL_DECISION_OBSERVED": "NOT_APPLICABLE",
                        "INSUFFICIENT_EVIDENCE": "UNKNOWN",
                    }.get(observation_status)
                    if required_status and claim_value.get("cell_status") != required_status:
                        _add(findings, f"episode.claims[{index}].action_claim_must_localize_bound_decision_observation")
                elif treatment == "OBSERVATION_BOUNDARY" and observation_status == "INSUFFICIENT_EVIDENCE":
                    if claim_value.get("cell_status") not in {"UNKNOWN", "EVIDENCE_INELIGIBLE"}:
                        _add(findings, f"episode.claims[{index}].insufficient_decision_observation_must_remain_unknown")


def validate_episode_manifest(
    manifest: Any,
    *,
    decision_contract: Any | None = None,
    enterprise_bundle: Any | None = None,
    reconstruction_binding: Any | None = None,
    evidence_locator_ids: Any | None = None,
) -> dict[str, Any]:
    """Validate a closed, read-only episode composition contract.

    Passing existing artifacts is optional for a standalone structural review.
    When supplied, their identities must bind exactly, but they are never
    mutated or promoted by this function.
    """
    findings: list[str] = []
    item = _closed(manifest, _ROOT_KEYS, "episode", findings)
    schema_version = item.get("schema_version")
    if schema_version not in {SCHEMA_VERSION, LEGACY_SCHEMA_VERSION}:
        _add(findings, "episode.schema_version_invalid")
    _require_text(item, "episode_id", "episode", findings)
    _require_text(item, "company_id", "episode", findings)
    _require_text(item, "issuer_id", "episode", findings)
    _instant(item.get("cutoff_at"), "episode.cutoff_at", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_EPISODE_MANIFEST":
        _add(findings, "episode.object_class_invalid")
    if item.get("claim_class") != "COMPOSITE_ENTERPRISE_JUDGMENT":
        _add(findings, "episode.claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        _add(findings, "episode.allowed_outputs_must_remain_read_model_and_research_agenda")

    _validate_contract_ref(item.get("decision_contract_ref"), findings)
    component_by_type = _validate_component_refs(item.get("component_refs"), findings)
    questions, question_ids = _validate_questions(item.get("question_set"), findings)
    known_locator_ids: set[str] | None = None
    if evidence_locator_ids is not None:
        locator_values = _unique_text_list(
            evidence_locator_ids, "episode.evidence_locator_ids", findings,
        )
        known_locator_ids = set(locator_values)
    claims, claim_ids = _validate_claims(
        item.get("claims"), question_ids, str(item.get("issuer_id") or ""), known_locator_ids,
        schema_version == SCHEMA_VERSION, findings,
    )
    cells, cell_ids = _validate_outcome_cells(item.get("outcome_cells"), findings)
    threads = _validate_threads(item.get("mechanism_threads"), claim_ids, cell_ids, findings)

    question_claims = {
        question.get("question_id"): {
            claim_id for claim_id in _items(question.get("claim_ids")) if _text(claim_id)
        }
        for question in questions
    }
    for claim in claims:
        question_id = claim.get("question_id")
        if question_id and claim.get("claim_id") not in question_claims.get(question_id, set()):
            _add(findings, "episode.question_set_must_reference_each_claim")
    for question_id, referenced_claim_ids in question_claims.items():
        if any(claim_id not in claim_ids for claim_id in referenced_claim_ids):
            _add(findings, f"episode.question_set.{question_id}_references_unknown_claim")

    for index, claim in enumerate(claims):
        dependencies = _items(claim.get("dependent_outcome_cell_ids"))
        if any(not _text(cell_id) or cell_id not in cell_ids for cell_id in dependencies):
            _add(findings, f"episode.claims[{index}].dependent_outcome_cell_ids_unknown")

    claim_levels = {claim.get("admission_level") for claim in claims}
    highest_claim_level = max((_rank(level) for level in claim_levels), default=-1)
    if highest_claim_level >= _rank("E1_RECONSTRUCTION"):
        for component_type in ("ENTERPRISE_SYSTEM_MODEL", "MANAGEMENT_DECISION_LEDGER"):
            if component_type not in component_by_type:
                _add(findings, f"episode.{component_type.lower()}_required_for_e1")
    if {"E2_MECHANISM_PROBE", "E3_COMPARATIVE_LAB"}.intersection(claim_levels) and not threads:
        _add(findings, "episode.mechanism_threads_required_for_e2_or_higher_claim")
    if "E3_COMPARATIVE_LAB" in claim_levels and "COMPARATIVE_EPISODE" not in component_by_type:
        _add(findings, "episode.comparative_episode_ref_required_for_e3_or_higher_claim")
    if "E4_TRANSFER_AND_UTILITY" in claim_levels and "FORECAST_BUNDLE" not in component_by_type:
        _add(findings, "episode.forecast_bundle_ref_required_for_e4_claim")
    thread_claim_ids = {
        claim_id
        for thread in threads
        for claim_id in _items(thread.get("claim_ids"))
        if _text(claim_id)
    }
    for claim in claims:
        if claim.get("admission_level") in {"E2_MECHANISM_PROBE", "E3_COMPARATIVE_LAB"} and claim.get("claim_id") not in thread_claim_ids:
            _add(findings, "episode.e2_or_e3_claim_must_belong_to_a_mechanism_thread")

    roles = _closed(item.get("roles"), _ROLE_KEYS, "episode.roles", findings)
    role_values = [_require_text(roles, field, "episode.roles", findings) for field in _ROLE_KEYS]
    if len(set(value for value in role_values if value)) != len(_ROLE_KEYS):
        _add(findings, "episode.roles_must_be_independent")

    for path in _forbidden_paths(item):
        _add(findings, "episode.forbidden_outcome_price_valuation_or_investment_field:" + path)

    _validate_bindings(
        item,
        decision_contract=decision_contract,
        enterprise_bundle=enterprise_bundle,
        reconstruction_binding=reconstruction_binding,
        findings=findings,
    )
    return {"valid": not findings, "findings": findings, "episode_manifest": deepcopy(item) if not findings else None}


def _source_locator_from_receipt(
    receipt: dict[str, Any], *, path: str, findings: list[str],
) -> dict[str, Any] | None:
    source = receipt.get("source")
    if source is None:
        if receipt.get("status") == "OBSERVED":
            _add(findings, path + ".observed_receipt_requires_source_locator")
        return None
    source_item = _mapping(source)
    if not isinstance(source, dict):
        _add(findings, path + ".source_must_be_object")
        return None
    for field in ("source_id", "source_url", "field_ref", "field_identity"):
        _require_text(source_item, field, path + ".source", findings)
    if not str(source_item.get("source_url", "")).startswith("https://"):
        _add(findings, path + ".source.source_url_must_be_https")
    page = source_item.get("pdf_page")
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        _add(findings, path + ".source.pdf_page_must_be_positive_integer")
    elif source_item.get("field_ref") != f"PDF p.{page}":
        _add(findings, path + ".source.field_ref_must_match_pdf_page")
    if source_item.get("field_identity") != receipt.get("field_id"):
        _add(findings, path + ".source.field_identity_must_match_receipt_field")
    for field in ("measurement_clock", "responsibility_boundary", "unit"):
        if source_item.get(field) != receipt.get(field):
            _add(findings, f"{path}.source.{field}_must_match_receipt")
    locator = _mapping(source_item.get("custodian_locator"))
    locator_keys = {"table_or_note", "line_item", "period_column"}
    if set(locator) != locator_keys or any(not _text(locator.get(field)) for field in locator_keys):
        _add(findings, path + ".source.custodian_locator_invalid")
    return {
        key: deepcopy(source_item[key])
        for key in (
            "source_id", "source_url", "pdf_page", "field_ref", "field_identity",
            "custodian_locator", "measurement_clock", "responsibility_boundary", "unit",
        )
        if key in source_item
    }


def _derive_claim_evidence_trace(
    manifest: dict[str, Any], canonical_settlement: Any, findings: list[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    settlement = _mapping(canonical_settlement)
    if not isinstance(canonical_settlement, dict):
        _add(findings, "episode_trace.canonical_settlement_must_be_object")
        return [], {}
    if settlement.get("schema_version") != "enterprise-outcome-measurement-settlement.v1":
        _add(findings, "episode_trace.canonical_settlement_schema_invalid")
    if settlement.get("settled") is not True:
        _add(findings, "episode_trace.canonical_settlement_must_be_settled")
    for field in ("settlement_id", "company_id", "cutoff_at"):
        _require_text(settlement, field, "episode_trace.canonical_settlement", findings)
    if settlement.get("company_id") != manifest.get("company_id"):
        _add(findings, "episode_trace.settlement_company_must_match_episode")
    if settlement.get("cutoff_at") != manifest.get("cutoff_at"):
        _add(findings, "episode_trace.settlement_cutoff_must_match_episode")

    contract_ref = _mapping(settlement.get("measurement_contract_ref"))
    contract_id = contract_ref.get("measurement_contract_id")
    contract_version = contract_ref.get("measurement_contract_version")
    if not _text(contract_id) or not isinstance(contract_version, int) or isinstance(contract_version, bool) or contract_version < 1:
        _add(findings, "episode_trace.settlement_measurement_contract_ref_invalid")

    result_rows = [_mapping(raw) for raw in _items(settlement.get("cell_results"))]
    result_ids = _unique_ids(result_rows, "cell_id", "episode_trace.canonical_settlement.cell_results", findings)
    result_statuses: dict[str, str] = {}
    for index, result in enumerate(result_rows):
        status = result.get("status")
        if status not in {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH"}:
            _add(findings, f"episode_trace.canonical_settlement.cell_results[{index}].status_invalid")
        elif _text(result.get("cell_id")):
            result_statuses[str(result["cell_id"])] = str(status)

    manifest_cells = {
        str(_mapping(raw).get("outcome_cell_id")): _mapping(raw)
        for raw in _items(manifest.get("outcome_cells"))
    }
    for cell_id, cell in manifest_cells.items():
        if cell_id not in result_ids:
            _add(findings, f"episode_trace.outcome_cell_missing_from_settlement:{cell_id}")
        measurement_ref = cell.get("measurement_contract_ref")
        if _text(measurement_ref) and measurement_ref != contract_id:
            _add(findings, f"episode_trace.outcome_cell_measurement_contract_mismatch:{cell_id}")

    raw_receipts_value = settlement.get("raw_observation_receipts")
    raw_receipts = [_mapping(raw) for raw in _items(raw_receipts_value)]
    if not isinstance(raw_receipts_value, list):
        _add(findings, "episode_trace.raw_observation_receipts_must_be_list")
    receipt_ids = _unique_ids(
        raw_receipts, "receipt_id", "episode_trace.canonical_settlement.raw_observation_receipts", findings,
    )
    ordered_receipt_ids = [raw.get("receipt_id") for raw in raw_receipts]
    if settlement.get("observation_receipt_ids") != ordered_receipt_ids:
        _add(findings, "episode_trace.observation_receipt_ids_must_match_raw_receipts_in_order")
    if len(receipt_ids) != len(raw_receipts):
        _add(findings, "episode_trace.raw_observation_receipt_ids_must_be_unique")

    traces_by_cell: dict[str, list[dict[str, Any]]] = {}
    seen_fields: set[tuple[str, str]] = set()
    for index, receipt in enumerate(raw_receipts):
        path = f"episode_trace.canonical_settlement.raw_observation_receipts[{index}]"
        cell_id = _require_text(receipt, "cell_id", path, findings)
        field_id = _require_text(receipt, "field_id", path, findings)
        if receipt.get("settlement_id") != settlement.get("settlement_id"):
            _add(findings, path + ".settlement_id_must_match_canonical_settlement")
        if receipt.get("company_id") != manifest.get("company_id"):
            _add(findings, path + ".company_id_must_match_episode")
        if receipt.get("cutoff_at") != manifest.get("cutoff_at"):
            _add(findings, path + ".cutoff_at_must_match_episode")
        if receipt.get("measurement_contract_ref") != settlement.get("measurement_contract_ref"):
            _add(findings, path + ".measurement_contract_ref_must_match_canonical_settlement")
        status = receipt.get("status")
        if status not in {"OBSERVED", "UNKNOWN", "MEASUREMENT_MISMATCH"}:
            _add(findings, path + ".status_invalid")
        if cell_id not in result_ids:
            _add(findings, path + ".cell_id_not_in_settlement_results")
        pair = (cell_id, field_id)
        if pair in seen_fields:
            _add(findings, path + ".cell_field_pair_duplicate")
        seen_fields.add(pair)
        locator = _source_locator_from_receipt(receipt, path=path, findings=findings)
        traces_by_cell.setdefault(cell_id, []).append({
            "raw_observation_receipt_id": receipt.get("receipt_id"),
            "field_id": field_id,
            "status": status,
            "source_locator": locator,
        })

    claim_traces: list[dict[str, Any]] = []
    for claim in map(_mapping, _items(manifest.get("claims"))):
        cell_traces: list[dict[str, Any]] = []
        for cell_id in _items(claim.get("dependent_outcome_cell_ids")):
            raw_traces = traces_by_cell.get(str(cell_id), [])
            if not raw_traces:
                _add(findings, f"episode_trace.dependent_cell_has_no_raw_observation_receipt:{cell_id}")
            cell_traces.append({
                "cell_id": cell_id,
                "status": result_statuses.get(str(cell_id)),
                "raw_observations": deepcopy(raw_traces),
            })
        claim_traces.append({
            "claim_id": claim.get("claim_id"),
            "method_id": claim.get("method_id"),
            "judgment_dimension": claim.get("judgment_dimension"),
            "claim_scope": deepcopy(claim.get("claim_scope")),
            "cells": cell_traces,
        })
    return claim_traces, result_statuses


def compile_claim_evidence_trace(
    manifest: Any,
    *,
    canonical_settlement: Any,
    decision_contract: Any | None = None,
    enterprise_bundle: Any | None = None,
    reconstruction_binding: Any | None = None,
    evidence_locator_ids: Any | None = None,
) -> dict[str, Any]:
    """Project claims to canonical settlement receipts without mutating either input."""
    validation = validate_episode_manifest(
        manifest,
        decision_contract=decision_contract,
        enterprise_bundle=enterprise_bundle,
        reconstruction_binding=reconstruction_binding,
        evidence_locator_ids=evidence_locator_ids,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "claim_evidence_trace": None}
    findings: list[str] = []
    traces, _ = _derive_claim_evidence_trace(_mapping(manifest), canonical_settlement, findings)
    return {
        "valid": not findings,
        "findings": findings,
        "claim_evidence_trace": deepcopy(traces) if not findings else None,
    }


def _claim_matrix_row(claim: dict[str, Any], cells_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    blocked_by: list[dict[str, str]] = []
    claim_state = str(claim.get("cell_status"))
    if claim_state in BLOCKING_CELL_STATES:
        blocked_by.append({"kind": "CLAIM_STATUS", "ref": claim_state})
    for cell_id in _items(claim.get("dependent_outcome_cell_ids")):
        cell = cells_by_id[str(cell_id)]
        status = str(cell.get("status"))
        if status in BLOCKING_CELL_STATES:
            blocked_by.append({"kind": "OUTCOME_CELL", "ref": str(cell_id)})
    allowed_outputs = ["RESEARCH_AGENDA"] if blocked_by else list(_OUTPUTS_BY_ADMISSION[claim["admission_level"]])
    return {
        "claim_id": claim["claim_id"],
        "question_id": claim["question_id"],
        "method_id": claim.get("method_id"),
        "judgment_dimension": claim.get("judgment_dimension"),
        "claim_scope": deepcopy(claim.get("claim_scope")),
        "evidence_locator_refs": list(_items(claim.get("evidence_locator_refs"))),
        "admission_level": claim["admission_level"],
        "cell_status": claim["cell_status"],
        "allowed_outputs": allowed_outputs,
        "blocked_by": blocked_by,
    }


def compile_episode_read_model(
    manifest: Any,
    *,
    decision_contract: Any | None = None,
    enterprise_bundle: Any | None = None,
    reconstruction_binding: Any | None = None,
    evidence_locator_ids: Any | None = None,
    canonical_settlement: Any | None = None,
) -> dict[str, Any]:
    """Derive permissions and optional receipt traces without writing an artifact."""
    validation = validate_episode_manifest(
        manifest,
        decision_contract=decision_contract,
        enterprise_bundle=enterprise_bundle,
        reconstruction_binding=reconstruction_binding,
        evidence_locator_ids=evidence_locator_ids,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "episode_read_model": None}
    item = _mapping(manifest)
    cells_by_id = {
        str(_mapping(raw)["outcome_cell_id"]): deepcopy(_mapping(raw)) for raw in _items(item.get("outcome_cells"))
    }
    claim_evidence_trace: list[dict[str, Any]] = []
    canonical_settlement_ref: str | None = None
    if canonical_settlement is not None:
        trace_findings: list[str] = []
        claim_evidence_trace, result_statuses = _derive_claim_evidence_trace(
            item, canonical_settlement, trace_findings,
        )
        if trace_findings:
            return {"valid": False, "findings": trace_findings, "episode_read_model": None}
        for cell_id, status in result_statuses.items():
            if cell_id in cells_by_id:
                cells_by_id[cell_id]["status"] = status
        canonical_settlement_ref = str(_mapping(canonical_settlement).get("settlement_id"))
    claim_output_matrix = [_claim_matrix_row(_mapping(raw), cells_by_id) for raw in _items(item.get("claims"))]
    row_by_claim = {row["claim_id"]: row for row in claim_output_matrix}
    thread_views: list[dict[str, Any]] = []
    for raw in _items(item.get("mechanism_threads")):
        thread = _mapping(raw)
        active_claim_ids = [
            claim_id for claim_id in thread["claim_ids"]
            if len(row_by_claim[claim_id]["allowed_outputs"]) > 1
        ]
        thread_views.append({
            "thread_id": thread["thread_id"],
            "role": thread["role"],
            "status": "ACTIVE" if active_claim_ids else "BOUNDARY_ONLY",
            "active_claim_ids": active_claim_ids,
            "blocked_claim_ids": [claim_id for claim_id in thread["claim_ids"] if claim_id not in active_claim_ids],
        })
    eligible_levels = {
        "E0_CONTEXT": True,
        "E1_RECONSTRUCTION": any(
            row["admission_level"] == "E1_RECONSTRUCTION" and len(row["allowed_outputs"]) > 1
            for row in claim_output_matrix
        ),
        "E2_MECHANISM_PROBE": any(view["status"] == "ACTIVE" for view in thread_views),
        "E3_COMPARATIVE_LAB": any(
            row["admission_level"] == "E3_COMPARATIVE_LAB" and len(row["allowed_outputs"]) > 1
            for row in claim_output_matrix
        ),
        "E4_TRANSFER_AND_UTILITY": any(
            row["admission_level"] == "E4_TRANSFER_AND_UTILITY" and len(row["allowed_outputs"]) > 1
            for row in claim_output_matrix
        ),
    }
    return {
        "valid": True,
        "findings": [],
        "episode_read_model": {
            "schema_version": item["schema_version"],
            "episode_id": item["episode_id"],
            "company_id": item["company_id"],
            "issuer_id": item["issuer_id"],
            "cutoff_at": item["cutoff_at"],
            "claim_output_matrix": claim_output_matrix,
            "claim_evidence_trace": claim_evidence_trace,
            "canonical_settlement_ref": canonical_settlement_ref,
            "mechanism_thread_views": thread_views,
            "eligible_admission_levels": eligible_levels,
            "allowed_outputs": list(ALLOWED_OUTPUTS),
            "investment_authorization": "NOT_AUTHORIZED",
        },
    }
