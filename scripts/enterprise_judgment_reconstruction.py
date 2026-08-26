#!/usr/bin/env python3
"""J1 cutoff-safe EnterpriseJudgmentEpisode reconstruction projection.

The canonical enterprise model and append-only management ledger remain the
only writers.  J1 selects a small, evidence-bound operating-system view and a
ledger slice as of one cutoff.  It intentionally represents unavailable
lifecycle, capital-structure, option, adaptation, and capital-allocation data
as field-level ``UNKNOWN`` rather than manufacturing a complete company story.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

try:
    from scripts import enterprise_judgment_core as core
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_core as core


SCHEMA_VERSION = "enterprise-judgment-reconstruction.v1"
SPEC_SCHEMA_VERSION = "enterprise-judgment-reconstruction-spec.v1"
ALLOWED_OUTPUTS = ["RECONSTRUCTION_READ_MODEL", "CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"]
REGISTRY_TABLE = "enterprise_judgment_frozen_reconstructions"


def _default_canonical_registry_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    local = repo_root / "stock_analysis.db"
    if local.exists():
        return local
    git_metadata = repo_root / ".git"
    if git_metadata.is_file():
        marker = git_metadata.read_text(encoding="utf-8").strip()
        if marker.startswith("gitdir:"):
            git_dir = Path(marker.split(":", 1)[1].strip()).resolve()
            shared = git_dir.parents[2] / "stock_analysis.db"
            if shared.exists():
                return shared
    return local


CANONICAL_REGISTRY_PATH = _default_canonical_registry_path()


class FrozenReconstructionRegistryError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

LOOP_DOMAINS = {"CUSTOMER", "COMPETITION", "OPERATIONS", "CASH", "CAPITAL_ALLOCATION", "PERMANENT_LOSS"}
FIELD_STATES = {"OBSERVED", "INFERRED", "UNKNOWN", "EVIDENCE_INELIGIBLE", "NOT_APPLICABLE"}
_ROOT_KEYS = {
    "schema_version", "reconstruction_id", "company_id", "issuer_id", "cutoff_at",
    "decision_contract_ref", "source_packet_ref", "context_snapshot_id", "operating_system_model_id",
    "decision_ledger_slice_id", "feedback_loops", "decision_observation", "decision_ids", "roles",
    "object_class", "claim_class", "allowed_outputs",
}
_LOOP_KEYS = {
    "loop_id", "domains", "variable_ids", "mechanism_ids", "financial_transmission_ids",
    "decision_ids", "selection_rationale", "evidence_refs",
}
_ROLE_KEYS = {"judgment_owner_id", "independent_challenger_id", "outcome_custodian_id"}
_CONTRACT_REF_KEYS = {"contract_id", "contract_version"}
_SOURCE_PACKET_REF_KEYS = {"receipt_id", "receipt_version"}
_DECISION_OBSERVATION_KEYS = {
    "observation_id", "status", "responsibility_unit_ids", "arena_ids", "reviewed_source_refs",
    "materiality_scope", "rationale", "next_discriminating_evidence",
}
DECISION_OBSERVATION_STATES = {
    "MATERIAL_DECISION_OBSERVED",
    "NO_MATERIAL_DECISION_OBSERVED",
    "INSUFFICIENT_EVIDENCE",
}
_FORBIDDEN_KEYS = {
    "price", "market_price", "share_price", "stock_price", "entry_price", "valuation",
    "valuation_result", "expectation_gap", "buyband", "buy_band", "portfolio_action",
    "position", "outcome_value", "outcome_result", "actual_value", "settlement_value",
    "training_score",
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


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, f"{path}_must_be_object")
        return item
    for field in sorted(set(item).difference(allowed)):
        _add(findings, f"{path}_contains_unapproved_field:{field}")
    for field in sorted(allowed.difference(item)):
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


def _ids(value: Any, path: str, findings: list[str], *, required: bool = True) -> list[str]:
    values = _items(value)
    if required and not values:
        _add(findings, path + "_required")
    result: list[str] = []
    for index, item in enumerate(values):
        if not _text(item):
            _add(findings, f"{path}[{index}]_must_be_nonempty_text")
        elif str(item) in result:
            _add(findings, f"{path}[{index}]_duplicate")
        else:
            result.append(str(item))
    return result


def _forbidden_paths(value: Any, path: str = "reconstruction_spec") -> list[str]:
    paths: list[str] = []
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
                paths.append(child_path)
            else:
                paths.extend(_forbidden_paths(nested, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _validated_inputs(source_package: Any, enterprise_model: Any, decision_ledger: Any, findings: list[str]) -> None:
    for prefix, validator, value in (
        ("source_package", core.validate_source_package, source_package),
        ("enterprise_model", lambda item: core.validate_enterprise_system_model(item, source_package=source_package), enterprise_model),
        ("decision_ledger", lambda item: core.validate_management_decision_ledger(item, source_package=source_package), decision_ledger),
    ):
        result = validator(value)
        for finding in result["findings"]:
            _add(findings, prefix + ":" + finding)


def _validate_reference(
    value: Any,
    *,
    allowed: set[str],
    path: str,
    id_field: str,
    version_field: str,
    findings: list[str],
) -> dict[str, Any]:
    item = _closed(value, allowed, path, findings)
    _require_text(item, id_field, path, findings)
    version = item.get(version_field)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        _add(findings, f"{path}.{version_field}_must_be_positive_integer")
    return item


def _contract_module() -> Any:
    try:
        from scripts import judgment_training_decision_contract as contract_module
    except ModuleNotFoundError:  # pragma: no cover - direct script import
        import judgment_training_decision_contract as contract_module
    return contract_module


def _source_packet_module() -> Any:
    try:
        from scripts import enterprise_judgment_source_packet as source_packet_module
    except ModuleNotFoundError:  # pragma: no cover - direct script import
        import enterprise_judgment_source_packet as source_packet_module
    return source_packet_module


def _validate_source_receipt_binding(
    source_packet_receipt: Any,
    source_package: Any,
    findings: list[str],
) -> dict[str, Any]:
    """Require J1's core package to be the exact receipt projection."""
    projected = _source_packet_module().compile_core_source_package(source_packet_receipt)
    for finding in projected["findings"]:
        _add(findings, "source_packet_receipt:" + finding)
    if not projected["valid"]:
        return {}
    if _mapping(source_package) != projected["source_package"]:
        _add(findings, "source_package_must_equal_bound_source_packet_receipt_projection")
    return _mapping(source_packet_receipt)


def validate_reconstruction_spec(
    spec: Any,
    *,
    source_packet_receipt: Any,
    source_package: Any,
    enterprise_model: Any,
    decision_ledger: Any,
    decision_contract: Any,
) -> dict[str, Any]:
    """Validate J1 selection while retaining canonical model/ledger authority.

    A J1 reconstruction is bound to the same ex-ante decision contract as its
    episode.  It can explicitly say that a material management decision was
    not observed; only a selected observed decision needs a ledger entry.
    """
    findings: list[str] = []
    receipt = _validate_source_receipt_binding(source_packet_receipt, source_package, findings)
    _validated_inputs(source_package, enterprise_model, decision_ledger, findings)
    item = _closed(spec, _ROOT_KEYS, "reconstruction_spec", findings)
    if item.get("schema_version") != SPEC_SCHEMA_VERSION:
        _add(findings, "reconstruction_spec.schema_version_invalid")
    for field in (
        "reconstruction_id", "company_id", "issuer_id", "context_snapshot_id",
        "operating_system_model_id", "decision_ledger_slice_id",
    ):
        _require_text(item, field, "reconstruction_spec", findings)
    cutoff = _instant(item.get("cutoff_at"), "reconstruction_spec.cutoff_at", findings)
    if item.get("object_class") != "ENTERPRISE_JUDGMENT_RECONSTRUCTION_SPEC":
        _add(findings, "reconstruction_spec.object_class_invalid")
    if item.get("claim_class") != "CUTOFF_ENTERPRISE_RECONSTRUCTION":
        _add(findings, "reconstruction_spec.claim_class_invalid")
    if item.get("allowed_outputs") != ALLOWED_OUTPUTS:
        _add(findings, "reconstruction_spec.allowed_outputs_must_exclude_outcome_valuation_and_investment")

    contract_ref = _validate_reference(
        item.get("decision_contract_ref"), allowed=_CONTRACT_REF_KEYS,
        path="reconstruction_spec.decision_contract_ref", id_field="contract_id",
        version_field="contract_version", findings=findings,
    )
    source_packet_ref = _validate_reference(
        item.get("source_packet_ref"), allowed=_SOURCE_PACKET_REF_KEYS,
        path="reconstruction_spec.source_packet_ref", id_field="receipt_id",
        version_field="receipt_version", findings=findings,
    )
    contract_validation = _contract_module().validate_training_decision_contract(decision_contract)
    for finding in contract_validation["findings"]:
        _add(findings, "decision_contract:" + finding)
    contract = _mapping(decision_contract)
    if (
        contract_ref.get("contract_id") != contract.get("contract_id")
        or contract_ref.get("contract_version") != contract.get("contract_version")
    ):
        _add(findings, "reconstruction_spec.decision_contract_ref_must_match_bound_contract")
    for field in ("company_id", "issuer_id", "cutoff_at"):
        if item.get(field) != contract.get(field):
            _add(findings, f"reconstruction_spec.{field}_must_match_bound_decision_contract")
    budget_refs = _items(_mapping(contract.get("evidence_budget")).get("source_packet_refs"))
    if budget_refs != [source_packet_ref]:
        _add(findings, "reconstruction_spec.source_packet_ref_must_match_bound_decision_contract")

    package = _mapping(source_package)
    model = _mapping(enterprise_model)
    ledger = _mapping(decision_ledger)
    if (
        source_packet_ref.get("receipt_id") != receipt.get("packet_id")
        or source_packet_ref.get("receipt_version") != receipt.get("packet_version")
    ):
        _add(findings, "reconstruction_spec.source_packet_ref_must_match_bound_source_packet_receipt")
    if source_packet_ref.get("receipt_id") != package.get("source_package_id"):
        _add(findings, "reconstruction_spec.source_packet_ref_must_match_canonical_source_package")
    for field in ("company_id", "issuer_id", "cutoff_at"):
        if item.get(field) != receipt.get(field):
            _add(findings, f"reconstruction_spec.{field}_must_match_bound_source_packet_receipt")
    for field, value in (
        ("company_id", package.get("company_id")),
        ("company_id", model.get("company_id")),
        ("company_id", ledger.get("company_id")),
    ):
        if item.get(field) != value:
            _add(findings, f"reconstruction_spec.{field}_must_match_canonical_inputs")
    if item.get("cutoff_at") != package.get("cutoff_at") or item.get("cutoff_at") != model.get("cutoff_at"):
        _add(findings, "reconstruction_spec.cutoff_at_must_match_source_package_and_model")

    variable_by_id = {entry.get("variable_id"): entry for entry in map(_mapping, _items(model.get("operating_variables")))}
    mechanism_by_id = {entry.get("mechanism_id"): entry for entry in map(_mapping, _items(model.get("mechanisms")))}
    transmission_by_id = {entry.get("transmission_id"): entry for entry in map(_mapping, _items(model.get("financial_transmissions")))}
    source_by_ref = {entry.get("source_ref"): entry for entry in map(_mapping, _items(package.get("sources")))}
    source_refs = set(source_by_ref)
    decisions_by_id = core._decision_snapshots(ledger, through=cutoff) if cutoff is not None else {}

    loops = [_closed(raw, _LOOP_KEYS, f"reconstruction_spec.feedback_loops[{index}]", findings) for index, raw in enumerate(_items(item.get("feedback_loops")))]
    if not 2 <= len(loops) <= 3:
        _add(findings, "reconstruction_spec.feedback_loops_must_contain_two_to_three_material_loops")
    loop_ids: set[str] = set()
    loop_decision_ids: set[str] = set()
    for index, loop in enumerate(loops):
        loop_id = _require_text(loop, "loop_id", f"reconstruction_spec.feedback_loops[{index}]", findings)
        if loop_id in loop_ids:
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].loop_id_duplicate")
        loop_ids.add(loop_id)
        domains = _ids(loop.get("domains"), f"reconstruction_spec.feedback_loops[{index}].domains", findings)
        if any(domain not in LOOP_DOMAINS for domain in domains):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].domains_invalid")
        variable_ids = _ids(loop.get("variable_ids"), f"reconstruction_spec.feedback_loops[{index}].variable_ids", findings)
        if len(variable_ids) < 2 or any(variable_id not in variable_by_id for variable_id in variable_ids):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].variable_ids_invalid")
        mechanism_ids = _ids(loop.get("mechanism_ids"), f"reconstruction_spec.feedback_loops[{index}].mechanism_ids", findings)
        if any(mechanism_id not in mechanism_by_id for mechanism_id in mechanism_ids):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].mechanism_ids_invalid")
        covered_variables = {
            variable_id
            for mechanism_id in mechanism_ids
            for variable_id in (
                _items(mechanism_by_id.get(mechanism_id, {}).get("from_variable_ids"))
                + _items(mechanism_by_id.get(mechanism_id, {}).get("to_variable_ids"))
            )
        }
        if any(variable_id not in covered_variables for variable_id in variable_ids):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].variables_must_be_covered_by_selected_mechanisms")
        transmission_ids = _ids(loop.get("financial_transmission_ids"), f"reconstruction_spec.feedback_loops[{index}].financial_transmission_ids", findings)
        if any(transmission_id not in transmission_by_id for transmission_id in transmission_ids):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].financial_transmission_ids_invalid")
        elif any(transmission_by_id[transmission_id].get("mechanism_id") not in mechanism_ids for transmission_id in transmission_ids):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].transmissions_must_belong_to_selected_mechanisms")
        decisions = _ids(
            loop.get("decision_ids"), f"reconstruction_spec.feedback_loops[{index}].decision_ids",
            findings, required=False,
        )
        if any(decision_id not in decisions_by_id for decision_id in decisions):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].decision_ids_invalid")
        mechanism_decision_ids = {
            decision_id
            for mechanism_id in mechanism_ids
            for decision_id in _items(mechanism_by_id.get(mechanism_id, {}).get("management_decision_ids"))
        }
        if any(decision_id not in mechanism_decision_ids for decision_id in decisions):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].decision_ids_must_bind_selected_mechanisms")
        loop_decision_ids.update(decisions)
        _require_text(loop, "selection_rationale", f"reconstruction_spec.feedback_loops[{index}]", findings)
        evidence_refs = _ids(loop.get("evidence_refs"), f"reconstruction_spec.feedback_loops[{index}].evidence_refs", findings)
        if any(reference not in source_refs for reference in evidence_refs):
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].evidence_refs_unknown")

        selected_variables = [variable_by_id[variable_id] for variable_id in variable_ids if variable_id in variable_by_id]
        selected_mechanisms = [mechanism_by_id[mechanism_id] for mechanism_id in mechanism_ids if mechanism_id in mechanism_by_id]
        scopes = {
            (entry.get("responsibility_unit_id"), entry.get("arena_id"))
            for entry in selected_variables + selected_mechanisms
        }
        if len(scopes) != 1:
            _add(findings, f"reconstruction_spec.feedback_loops[{index}].must_remain_within_one_responsibility_boundary_and_arena")
            loop_scope: tuple[Any, Any] | None = None
        else:
            loop_scope = next(iter(scopes))
        component_evidence_refs = set(evidence_refs)
        for entry in selected_variables + selected_mechanisms:
            component_evidence_refs.update(_items(entry.get("evidence_refs")))
        for transmission_id in transmission_ids:
            if transmission_id in transmission_by_id:
                component_evidence_refs.update(_items(transmission_by_id[transmission_id].get("evidence_refs")))
        for decision_id in decisions:
            snapshot = decisions_by_id.get(decision_id, {})
            component_evidence_refs.update(_items(snapshot.get("evidence_refs")))
            if loop_scope is not None and (
                snapshot.get("responsibility_unit_id"), snapshot.get("arena_id")
            ) != loop_scope:
                _add(findings, f"reconstruction_spec.feedback_loops[{index}].decision_scope_must_match_selected_mechanisms")
        if loop_scope is not None:
            responsibility_unit_id, _ = loop_scope
            for source_ref in component_evidence_refs:
                source = source_by_ref.get(source_ref, {})
                if source_ref not in source_by_ref:
                    continue
                if responsibility_unit_id not in _items(source.get("responsibility_boundary_ids")):
                    _add(findings, f"reconstruction_spec.feedback_loops[{index}].evidence_must_cover_responsibility_boundary")

    decision_observation = _closed(
        item.get("decision_observation"), _DECISION_OBSERVATION_KEYS,
        "reconstruction_spec.decision_observation", findings,
    )
    _require_text(decision_observation, "observation_id", "reconstruction_spec.decision_observation", findings)
    observation_state = decision_observation.get("status")
    if observation_state not in DECISION_OBSERVATION_STATES:
        _add(findings, "reconstruction_spec.decision_observation.status_invalid")
    observation_units = _ids(
        decision_observation.get("responsibility_unit_ids"),
        "reconstruction_spec.decision_observation.responsibility_unit_ids", findings,
    )
    observation_arenas = _ids(
        decision_observation.get("arena_ids"),
        "reconstruction_spec.decision_observation.arena_ids", findings,
    )
    observation_refs = _ids(
        decision_observation.get("reviewed_source_refs"),
        "reconstruction_spec.decision_observation.reviewed_source_refs", findings,
    )
    if any(reference not in source_refs for reference in observation_refs):
        _add(findings, "reconstruction_spec.decision_observation.reviewed_source_refs_unknown")
    for field in ("materiality_scope", "rationale", "next_discriminating_evidence"):
        _require_text(decision_observation, field, "reconstruction_spec.decision_observation", findings)
    for unit_id in observation_units:
        if any(unit_id not in _items(source_by_ref.get(source_ref, {}).get("responsibility_boundary_ids")) for source_ref in observation_refs if source_ref in source_by_ref):
            _add(findings, "reconstruction_spec.decision_observation.reviewed_sources_must_cover_responsibility_boundaries")
    selected_loop_scopes = {
        (variable_by_id[variable_id].get("responsibility_unit_id"), variable_by_id[variable_id].get("arena_id"))
        for loop in loops
        for variable_id in _ids(loop.get("variable_ids"), "reconstruction_spec.loop.variable_ids", findings)
        if variable_id in variable_by_id
    }
    if set(observation_units) != {scope[0] for scope in selected_loop_scopes}:
        _add(findings, "reconstruction_spec.decision_observation.responsibility_units_must_match_selected_loops")
    if set(observation_arenas) != {scope[1] for scope in selected_loop_scopes}:
        _add(findings, "reconstruction_spec.decision_observation.arenas_must_match_selected_loops")
    declared_decisions = _ids(
        item.get("decision_ids"), "reconstruction_spec.decision_ids", findings,
        required=observation_state == "MATERIAL_DECISION_OBSERVED",
    )
    if set(declared_decisions) != loop_decision_ids:
        _add(findings, "reconstruction_spec.decision_ids_must_equal_selected_loop_decisions")
    if observation_state == "MATERIAL_DECISION_OBSERVED" and not declared_decisions:
        _add(findings, "reconstruction_spec.observed_decisions_require_selected_ledger_entries")
    if observation_state in {"NO_MATERIAL_DECISION_OBSERVED", "INSUFFICIENT_EVIDENCE"} and declared_decisions:
        _add(findings, "reconstruction_spec.non_observed_decision_state_cannot_select_ledger_entries")
    if observation_state == "NO_MATERIAL_DECISION_OBSERVED" and any(
        source_by_ref.get(source_ref, {}).get("eligibility") != "ELIGIBLE"
        for source_ref in observation_refs
    ):
        _add(findings, "reconstruction_spec.no_material_decision_observation_requires_eligible_reviewed_sources")
    if observation_state in {"NO_MATERIAL_DECISION_OBSERVED", "INSUFFICIENT_EVIDENCE"}:
        selected_mechanisms = {
            mechanism_id
            for loop in loops
            for mechanism_id in _ids(loop.get("mechanism_ids"), "reconstruction_spec.loop.mechanism_ids", findings)
        }
        if any(
            _items(mechanism_by_id.get(mechanism_id, {}).get("management_decision_ids"))
            for mechanism_id in selected_mechanisms
        ):
            _add(findings, "reconstruction_spec.non_observed_decision_state_cannot_select_action_bound_mechanisms")

    roles = _closed(item.get("roles"), _ROLE_KEYS, "reconstruction_spec.roles", findings)
    role_values = [_require_text(roles, field, "reconstruction_spec.roles", findings) for field in _ROLE_KEYS]
    if len(set(value for value in role_values if value)) != len(_ROLE_KEYS):
        _add(findings, "reconstruction_spec.roles_must_be_independent")
    if roles != _mapping(contract.get("roles")):
        _add(findings, "reconstruction_spec.roles_must_match_bound_decision_contract")
    for path in _forbidden_paths(item):
        _add(findings, "reconstruction_spec.forbidden_outcome_price_valuation_or_investment_field:" + path)
    return {"valid": not findings, "findings": findings, "reconstruction_spec": deepcopy(item) if not findings else None}


def _decision_slice(ledger: dict[str, Any], decision_ids: set[str], cutoff: datetime) -> list[dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for event in map(_mapping, _items(ledger.get("events"))):
        recorded_at = datetime.fromisoformat(str(event["recorded_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        effective_at = datetime.fromisoformat(str(event["effective_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        decision_id = event["decision_id"]
        if decision_id not in decision_ids or recorded_at > cutoff or effective_at > cutoff:
            continue
        if event["event_type"] == "DECISION_RECORDED":
            snapshots[decision_id] = {
                "decision_id": decision_id,
                "status": event["status"],
                "last_event_id": event["event_id"],
                "responsibility_unit_id": event["responsibility_unit_id"],
                "arena_id": event["arena_id"],
                "problem_statement": event["problem_statement"],
                "expected_mechanism_ids": list(event["expected_mechanism_ids"]),
                "strongest_counterargument": event["strongest_counterargument"],
                "observable_signal_ids": list(event["observable_signal_ids"]),
                "financial_transmission_ids": list(event["financial_transmission_ids"]),
                "known_unknowns": list(event["unknowns"]),
                "evidence_refs": list(event["evidence_refs"]),
            }
        elif decision_id in snapshots and event["event_type"] == "STATUS_CHANGED":
            snapshots[decision_id]["status"] = event["to_status"]
            snapshots[decision_id]["last_event_id"] = event["event_id"]
            snapshots[decision_id]["evidence_refs"] = list(dict.fromkeys(
                snapshots[decision_id]["evidence_refs"] + _items(event.get("evidence_refs"))
            ))
        elif decision_id in snapshots and event["event_type"] == "EVIDENCE_ATTACHED":
            snapshots[decision_id]["last_event_id"] = event["event_id"]
            snapshots[decision_id]["evidence_refs"] = list(dict.fromkeys(
                snapshots[decision_id]["evidence_refs"] + _items(event.get("evidence_refs"))
            ))
    entries: list[dict[str, Any]] = []
    for decision_id in sorted(snapshots):
        entry = snapshots[decision_id]
        status = entry["status"]
        entries.append({
            **entry,
            "field_statuses": {
                "PROBLEM": "OBSERVED",
                "ALTERNATIVES": "UNKNOWN",
                "NON_ACTION_OPTION": "UNKNOWN",
                "RESOURCE_COMMITMENT": "OBSERVED" if status in {"COMMITTED", "IMPLEMENTED", "EXPOSED", "REALIZED"} else "UNKNOWN",
                "EXECUTION": "OBSERVED" if status in {"IMPLEMENTED", "EXPOSED", "REALIZED"} else "UNKNOWN",
                "ADAPTATION": "UNKNOWN",
                "CAPITAL_ALLOCATION": "UNKNOWN",
            },
        })
    return entries


def _deduplicated_texts(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if _text(value)))


def _coverage_state(
    evidence_refs: list[Any],
    *,
    source_by_ref: dict[str, dict[str, Any]],
    inferred: bool = False,
) -> str:
    refs = _deduplicated_texts(evidence_refs)
    has_eligible = any(source_by_ref.get(ref, {}).get("eligibility") == "ELIGIBLE" for ref in refs)
    has_ineligible = any(
        source_by_ref.get(ref, {}).get("eligibility") == "EVIDENCE_INELIGIBLE" for ref in refs
    )
    if has_eligible:
        return "INFERRED" if inferred else "OBSERVED"
    if has_ineligible:
        return "EVIDENCE_INELIGIBLE"
    return "UNKNOWN"


def _coverage_entry(
    *,
    component_type: str,
    component_id: str,
    evidence_refs: list[Any],
    source_by_ref: dict[str, dict[str, Any]],
    inferred: bool = False,
) -> dict[str, Any]:
    refs = _deduplicated_texts(evidence_refs)
    return {
        "component_type": component_type,
        "component_id": component_id,
        "status": _coverage_state(refs, source_by_ref=source_by_ref, inferred=inferred),
        "evidence_refs": refs,
    }


def _aggregate_coverage(entries: list[dict[str, Any]]) -> str:
    states = [entry["status"] for entry in entries]
    if "INFERRED" in states:
        return "INFERRED"
    if "OBSERVED" in states:
        return "OBSERVED"
    if "EVIDENCE_INELIGIBLE" in states:
        return "EVIDENCE_INELIGIBLE"
    return "UNKNOWN"


def _build_evidence_coverage(
    *,
    loops: list[dict[str, Any]],
    model: dict[str, Any],
    ledger: dict[str, Any],
    cutoff: datetime,
    source_by_ref: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    variable_by_id = {
        entry.get("variable_id"): entry for entry in map(_mapping, _items(model.get("operating_variables")))
    }
    mechanism_by_id = {
        entry.get("mechanism_id"): entry for entry in map(_mapping, _items(model.get("mechanisms")))
    }
    transmission_by_id = {
        entry.get("transmission_id"): entry for entry in map(_mapping, _items(model.get("financial_transmissions")))
    }
    decision_by_id = core._decision_snapshots(ledger, through=cutoff)
    loop_entries: list[dict[str, Any]] = []
    all_source_refs: list[str] = []
    for loop in loops:
        variable_entries = []
        for variable_id in loop["variable_ids"]:
            variable = variable_by_id[variable_id]
            variable_entries.append(_coverage_entry(
                component_type="OPERATING_VARIABLE", component_id=variable_id,
                evidence_refs=_items(variable.get("evidence_refs")), source_by_ref=source_by_ref,
                inferred=variable.get("observation_state") != "OBSERVED",
            ))
        mechanism_entries = []
        for mechanism_id in loop["mechanism_ids"]:
            mechanism = mechanism_by_id[mechanism_id]
            variable_refs = [
                ref
                for variable_id in _items(mechanism.get("from_variable_ids")) + _items(mechanism.get("to_variable_ids"))
                for ref in _items(variable_by_id[variable_id].get("evidence_refs"))
            ]
            mechanism_entries.append(_coverage_entry(
                component_type="MECHANISM", component_id=mechanism_id,
                evidence_refs=_items(mechanism.get("evidence_refs")) + variable_refs,
                source_by_ref=source_by_ref, inferred=mechanism.get("reasoning_kind") != "OBSERVATION",
            ))
        transmission_entries = []
        for transmission_id in loop["financial_transmission_ids"]:
            transmission = transmission_by_id[transmission_id]
            mechanism = mechanism_by_id[transmission["mechanism_id"]]
            transmission_entries.append(_coverage_entry(
                component_type="FINANCIAL_TRANSMISSION", component_id=transmission_id,
                evidence_refs=(
                    _items(transmission.get("evidence_refs"))
                    + _items(mechanism.get("evidence_refs"))
                ),
                source_by_ref=source_by_ref, inferred=True,
            ))
        decision_entries = [
            _coverage_entry(
                component_type="MANAGEMENT_DECISION", component_id=decision_id,
                evidence_refs=_items(decision_by_id[decision_id].get("evidence_refs")),
                source_by_ref=source_by_ref,
            )
            for decision_id in loop["decision_ids"]
        ]
        components = variable_entries + mechanism_entries + transmission_entries + decision_entries
        source_refs = _deduplicated_texts(
            list(loop["evidence_refs"])
            + [ref for component in components for ref in component["evidence_refs"]]
        )
        all_source_refs.extend(source_refs)
        scopes = {
            (variable_by_id[variable_id]["responsibility_unit_id"], variable_by_id[variable_id]["arena_id"])
            for variable_id in loop["variable_ids"]
        }
        scope = next(iter(scopes))
        loop_entries.append({
            "loop_id": loop["loop_id"],
            "responsibility_unit_id": scope[0],
            "arena_id": scope[1],
            "status": _aggregate_coverage(components),
            "components": components,
            "blocked_component_ids": [
                component["component_id"]
                for component in components
                if component["status"] in {"UNKNOWN", "EVIDENCE_INELIGIBLE"}
            ],
            "evidence_refs": source_refs,
        })
    source_entries = [
        {
            "source_ref": source_ref,
            "status": source_by_ref[source_ref]["eligibility"],
            "responsibility_boundary_ids": list(source_by_ref[source_ref]["responsibility_boundary_ids"]),
        }
        for source_ref in _deduplicated_texts(all_source_refs)
    ]
    return {"sources": source_entries, "feedback_loops": loop_entries}


def _context_dimension_coverage(coverage: dict[str, Any]) -> dict[str, str]:
    loops = _items(coverage.get("feedback_loops"))

    def for_domains(domains: set[str]) -> str:
        relevant = [entry for entry in loops if domains.intersection(set(_items(entry.get("domains"))))]
        return _aggregate_coverage(relevant) if relevant else "UNKNOWN"

    # Loop objects do not duplicate domains in coverage, so retain their
    # selection-only mapping at the call site rather than claiming a broader
    # enterprise fact from an unselected source.
    return {
        "BUSINESS_MODEL": _aggregate_coverage(loops) if loops else "UNKNOWN",
        "CUSTOMER": for_domains({"CUSTOMER"}),
        "COMPETITION": for_domains({"COMPETITION"}),
        "RESPONSIBILITY_BOUNDARY": _aggregate_coverage(loops) if loops else "UNKNOWN",
        "LIFECYCLE": "UNKNOWN",
        "CAPITAL_STRUCTURE": "UNKNOWN",
    }


def compile_enterprise_reconstruction(
    spec: Any,
    *,
    source_packet_receipt: Any,
    source_package: Any,
    enterprise_model: Any,
    decision_ledger: Any,
    decision_contract: Any,
) -> dict[str, Any]:
    """Compile J1's component read models with no canonical writes or promotion."""
    validation = validate_reconstruction_spec(
        spec,
        source_packet_receipt=source_packet_receipt,
        source_package=source_package,
        enterprise_model=enterprise_model,
        decision_ledger=decision_ledger,
        decision_contract=decision_contract,
    )
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "reconstruction": None}
    item = _mapping(spec)
    package = _mapping(source_package)
    model = _mapping(enterprise_model)
    ledger = _mapping(decision_ledger)
    cutoff = datetime.fromisoformat(str(item["cutoff_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
    loops = [_mapping(loop) for loop in _items(item.get("feedback_loops"))]
    source_by_ref = {entry["source_ref"]: entry for entry in map(_mapping, _items(package.get("sources")))}
    coverage = _build_evidence_coverage(
        loops=loops, model=model, ledger=ledger, cutoff=cutoff, source_by_ref=source_by_ref,
    )
    for entry, loop in zip(coverage["feedback_loops"], loops, strict=True):
        entry["domains"] = list(loop["domains"])
    context = {
        "snapshot_id": item["context_snapshot_id"],
        "company_id": item["company_id"],
        "cutoff_at": item["cutoff_at"],
        "source_package_ref": {"source_package_id": package["source_package_id"], "method_version": package["method_version"]},
        "enterprise_model_ref": {"model_id": model["model_id"], "version": model["version"]},
        "responsibility_unit_ids": [unit["unit_id"] for unit in map(_mapping, _items(model["responsibility_units"]))],
        "competitive_arena_ids": [arena["arena_id"] for arena in map(_mapping, _items(model["arenas"]))],
        "operating_state_ids": [state["state_id"] for state in map(_mapping, _items(model["operating_states"]))],
        "dimension_coverage": _context_dimension_coverage(coverage),
    }
    operating_system = {
        "operating_system_model_id": item["operating_system_model_id"],
        "source_model_ref": {"model_id": model["model_id"], "version": model["version"]},
        "feedback_loops": [{
            "loop_id": loop["loop_id"],
            "domains": list(loop["domains"]),
            "variable_ids": list(loop["variable_ids"]),
            "mechanism_ids": list(loop["mechanism_ids"]),
            "financial_transmission_ids": list(loop["financial_transmission_ids"]),
            "decision_ids": list(loop["decision_ids"]),
            "evidence_refs": list(loop["evidence_refs"]),
        } for loop in loops],
    }
    ledger_slice = {
        "slice_id": item["decision_ledger_slice_id"],
        "ledger_ref": {"ledger_id": ledger["ledger_id"], "append_policy": ledger["append_policy"]},
        "cutoff_at": item["cutoff_at"],
        "decision_observation": deepcopy(item["decision_observation"]),
        "decisions": _decision_slice(ledger, set(item["decision_ids"]), cutoff),
    }
    reconstruction = {
        "schema_version": SCHEMA_VERSION,
        "reconstruction_id": item["reconstruction_id"],
        "company_id": item["company_id"],
        "issuer_id": item["issuer_id"],
        "cutoff_at": item["cutoff_at"],
        "source_packet_ref": deepcopy(item["source_packet_ref"]),
        "enterprise_context_snapshot": context,
        "operating_system_model": operating_system,
        "management_decision_ledger_slice": ledger_slice,
        "evidence_coverage": coverage,
        "episode_component_refs": [
            {"component_type": "ENTERPRISE_CONTEXT_SNAPSHOT", "component_id": context["snapshot_id"], "component_version": "1", "admission_level": "E0_CONTEXT", "read_only": True},
            {"component_type": "ENTERPRISE_SYSTEM_MODEL", "component_id": model["model_id"], "component_version": model["version"], "admission_level": "E1_RECONSTRUCTION", "read_only": True},
            {"component_type": "MANAGEMENT_DECISION_LEDGER", "component_id": ledger["ledger_id"], "component_version": core.MANAGEMENT_DECISION_LEDGER_VERSION, "admission_level": "E1_RECONSTRUCTION", "read_only": True},
            {"component_type": "MANAGEMENT_DECISION_OBSERVATION", "component_id": item["decision_observation"]["observation_id"], "component_version": "1", "admission_level": "E1_RECONSTRUCTION", "read_only": True},
        ],
        "roles": deepcopy(item["roles"]),
        "object_class": "ENTERPRISE_JUDGMENT_RECONSTRUCTION",
        "claim_class": "CUTOFF_ENTERPRISE_RECONSTRUCTION",
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "investment_authorization": "NOT_AUTHORIZED",
    }
    return {"valid": True, "findings": [], "reconstruction": reconstruction}


def validate_compiled_reconstruction(
    reconstruction: Any,
    *,
    spec: Any,
    source_packet_receipt: Any,
    source_package: Any,
    enterprise_model: Any,
    decision_ledger: Any,
    decision_contract: Any,
) -> dict[str, Any]:
    """Prove a supplied J1 read model is exactly the bound compilation."""
    compiled = compile_enterprise_reconstruction(
        spec,
        source_packet_receipt=source_packet_receipt,
        source_package=source_package,
        enterprise_model=enterprise_model,
        decision_ledger=decision_ledger,
        decision_contract=decision_contract,
    )
    findings = list(compiled["findings"])
    if compiled["valid"] and _mapping(reconstruction) != compiled["reconstruction"]:
        _add(findings, "reconstruction_must_equal_bound_cutoff_safe_compilation")
    return {"valid": not findings, "findings": findings, "reconstruction": deepcopy(_mapping(reconstruction)) if not findings else None}


def initialize_reconstruction_registry(conn: sqlite3.Connection) -> None:
    """Create the append-only J1 trust root used by downstream projections."""
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {REGISTRY_TABLE} (
                reconstruction_id TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (reconstruction_id, schema_version)
            )"""
        )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def register_frozen_reconstruction(
    conn: sqlite3.Connection,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
    *,
    frozen_at: str,
) -> dict[str, Any]:
    """Freeze one fully replayable J1 object before J2/J3/J4 consume it."""
    inputs = _mapping(reconstruction_inputs)
    expected_input_keys = {
        "spec",
        "source_packet_receipt",
        "source_package",
        "enterprise_model",
        "decision_ledger",
        "decision_contract",
    }
    if set(inputs) != expected_input_keys:
        raise ValueError("frozen reconstruction requires the complete J1 compilation inputs")
    validation = validate_compiled_reconstruction(
        reconstruction_read_model,
        spec=inputs["spec"],
        source_packet_receipt=inputs["source_packet_receipt"],
        source_package=inputs["source_package"],
        enterprise_model=inputs["enterprise_model"],
        decision_ledger=inputs["decision_ledger"],
        decision_contract=inputs["decision_contract"],
    )
    if not validation["valid"]:
        raise ValueError("invalid reconstruction freeze: " + "; ".join(validation["findings"]))
    item = validation["reconstruction"]
    freeze_instant = _instant(frozen_at, "frozen_reconstruction.frozen_at", [])
    cutoff_instant = _instant(item.get("cutoff_at"), "frozen_reconstruction.cutoff_at", [])
    if freeze_instant is None or cutoff_instant is None or freeze_instant <= cutoff_instant:
        raise ValueError("frozen reconstruction must be registered after its cutoff")
    payload = {
        "reconstruction": deepcopy(item),
        "reconstruction_inputs": deepcopy(inputs),
    }
    encoded = _canonical_json(payload)
    initialize_reconstruction_registry(conn)
    identity = (item["reconstruction_id"], item["schema_version"])
    existing = conn.execute(
        f"SELECT payload_json, frozen_at FROM {REGISTRY_TABLE} WHERE reconstruction_id = ? AND schema_version = ?",
        identity,
    ).fetchone()
    if existing is not None:
        if existing[0] != encoded or existing[1] != freeze_instant.isoformat():
            raise ValueError("frozen reconstruction identity already has different content")
        return {
            "frozen": True,
            "reconstruction_id": identity[0],
            "schema_version": identity[1],
            "idempotent": True,
        }
    with conn:
        conn.execute(
            f"""INSERT INTO {REGISTRY_TABLE} (
                reconstruction_id, schema_version, company_id, cutoff_at, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                identity[0],
                identity[1],
                item["company_id"],
                item["cutoff_at"],
                encoded,
                freeze_instant.isoformat(),
            ),
        )
    return {
        "frozen": True,
        "reconstruction_id": identity[0],
        "schema_version": identity[1],
        "idempotent": False,
    }


def validate_frozen_reconstruction_binding(
    conn: sqlite3.Connection,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
) -> dict[str, Any]:
    """Compare caller material with the previously frozen canonical J1 bundle."""
    item = _mapping(reconstruction_read_model)
    identity = (item.get("reconstruction_id"), item.get("schema_version"))
    try:
        row = conn.execute(
            f"SELECT payload_json FROM {REGISTRY_TABLE} WHERE reconstruction_id = ? AND schema_version = ?",
            identity,
        ).fetchone()
    except sqlite3.OperationalError:
        return {"valid": False, "findings": ["frozen_reconstruction_registry_not_initialized"]}
    if row is None:
        return {"valid": False, "findings": ["frozen_reconstruction_not_registered"]}
    payload = json.loads(row[0])
    findings: list[str] = []
    if item != _mapping(payload).get("reconstruction"):
        _add(findings, "reconstruction_must_match_frozen_registry_object")
    if _mapping(reconstruction_inputs) != _mapping(payload).get("reconstruction_inputs"):
        _add(findings, "reconstruction_inputs_must_match_frozen_registry_object")
    return {"valid": not findings, "findings": findings}


def load_frozen_reconstruction(
    conn: sqlite3.Connection,
    reconstruction_ref: Any,
) -> dict[str, Any]:
    """Load one previously frozen J1 bundle by its formal object identity."""
    reference = _mapping(reconstruction_ref)
    if set(reference) != {"reconstruction_id", "schema_version"}:
        raise FrozenReconstructionRegistryError(
            "frozen_reconstruction_ref_invalid",
            "Frozen J1 reference requires reconstruction_id and schema_version only",
        )
    try:
        row = conn.execute(
            f"""SELECT payload_json, frozen_at FROM {REGISTRY_TABLE}
                WHERE reconstruction_id = ? AND schema_version = ?""",
            (reference.get("reconstruction_id"), reference.get("schema_version")),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise FrozenReconstructionRegistryError(
            "frozen_reconstruction_registry_not_initialized",
            "The canonical Frozen J1 registry is not initialized",
        ) from exc
    if row is None:
        raise FrozenReconstructionRegistryError(
            "frozen_reconstruction_not_registered",
            "The requested Frozen J1 identity is not registered",
        )
    payload = json.loads(row[0])
    return {
        "reconstruction": deepcopy(_mapping(payload).get("reconstruction")),
        "reconstruction_inputs": deepcopy(_mapping(payload).get("reconstruction_inputs")),
        "frozen_at": row[1],
    }


def resolve_canonical_frozen_reconstruction(
    reconstruction_ref: Any,
) -> tuple[sqlite3.Connection, dict[str, Any]]:
    """Resolve Frozen J1 from the control-plane-owned production registry."""
    path = CANONICAL_REGISTRY_PATH.resolve()
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError as exc:
        raise FrozenReconstructionRegistryError(
            "canonical_frozen_reconstruction_registry_unavailable",
            "The canonical Frozen J1 registry is unavailable",
        ) from exc
    try:
        return conn, load_frozen_reconstruction(conn, reconstruction_ref)
    except Exception:
        conn.close()
        raise
