#!/usr/bin/env python3
"""Canonical Enterprise Judgment Core v1.

The core has one write direction::

    EnterpriseSystemModel
      -> append-only ManagementDecisionLedger
      -> review-ready CJO candidate
      -> independently reviewed Frozen CJO

Forecasts, training notes, prices, valuation results, and report prose are not
writers of these objects.  They may only create candidate amendments or consume
read-only projections.  All timestamps that become part of a canonical object
are supplied by the caller; the compiler never reads the current clock.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any


ENTERPRISE_SYSTEM_MODEL_VERSION = "enterprise-system-model.v1"
MANAGEMENT_DECISION_LEDGER_VERSION = "management-decision-ledger.v1"
CJO_CANDIDATE_VERSION = "company-judgment-object-candidate.v1"
FROZEN_CJO_VERSION = "frozen-company-judgment-object.v1"
CJO_REVIEW_VERSION = "company-judgment-independent-review.v1"
CANDIDATE_AMENDMENT_VERSION = "company-judgment-candidate-amendment.v1"
REPORT_HANDOFF_VERSION = "enterprise-judgment-report-handoff.v1"

SOURCE_ELIGIBILITY = {"ELIGIBLE", "EVIDENCE_INELIGIBLE"}
REASONING_KINDS = {"OBSERVATION", "INFERENCE"}
EVIDENCE_STATES = {"SUPPORTED", "CONTRADICTED", "MODEL_UNCERTAIN", "EVIDENCE_INELIGIBLE", "UNKNOWN"}
RESOLUTIONS = {"PRIMARY", "NO_PRIMARY", "MIXED", "UNKNOWN"}
DECISION_STATUSES = {
    "PLANNED", "COMMITTED", "IMPLEMENTED", "EXPOSED", "REALIZED",
    "CANCELLED", "INSUFFICIENT_EVIDENCE",
}
DECISION_EVENT_TYPES = {"DECISION_RECORDED", "STATUS_CHANGED", "EVIDENCE_ATTACHED"}
UNIT_TYPES = {"COMPANY", "GROUP", "PARENT", "SUBSIDIARY", "BUSINESS_UNIT"}
DECISION_STATUS_TRANSITIONS = {
    "PLANNED": {"COMMITTED", "IMPLEMENTED", "CANCELLED", "INSUFFICIENT_EVIDENCE"},
    "COMMITTED": {"IMPLEMENTED", "CANCELLED", "INSUFFICIENT_EVIDENCE"},
    "IMPLEMENTED": {"EXPOSED", "REALIZED", "CANCELLED", "INSUFFICIENT_EVIDENCE"},
    "EXPOSED": {"REALIZED", "CANCELLED", "INSUFFICIENT_EVIDENCE"},
    "REALIZED": {"INSUFFICIENT_EVIDENCE"},
    "CANCELLED": {"INSUFFICIENT_EVIDENCE"},
    "INSUFFICIENT_EVIDENCE": DECISION_STATUSES - {"INSUFFICIENT_EVIDENCE"},
}
TRANSMISSION_LAYERS = {"NORMAL_EARNINGS", "OWNER_CASH", "PERMANENT_LOSS"}
DIRECTIONS = {"IMPROVES", "DETERIORATES", "MIXED", "UNKNOWN", "NONE"}
AMENDMENT_ORIGINS = {"FORECAST", "TRAINING", "LEARNING_NOTE"}

_FORBIDDEN_ENTERPRISE_KEYS = {
    "price", "market_price", "share_price", "stock_price", "entry_price",
    "valuation", "valuation_result", "expectation_gap", "buy_band", "buyband",
    "expected_return", "investment_return", "portfolio_action", "position",
    "outcome_result", "future_settlement", "training_score",
}


class EnterpriseJudgmentCoreError(ValueError):
    """Raised when an object crosses a canonical authority boundary."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _validation(findings: list[str], **extra: Any) -> dict[str, Any]:
    return {"state": "VALID" if not findings else "INVALID", "findings": findings, **extra}


def _forbidden_paths(value: Any, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            path = f"{prefix}.{key}"
            if (
                lowered in _FORBIDDEN_ENTERPRISE_KEYS
                or lowered.startswith("actual_")
                or lowered.startswith("outcome_")
                or lowered.startswith("settlement_")
                or lowered.startswith("forecast_")
                or (
                    lowered.startswith("training_")
                    and lowered != "training_write_allowed"
                )
                or lowered.startswith("learning_")
                or lowered.endswith("_market_price")
                or lowered.endswith("_share_price")
                or lowered.endswith("_stock_price")
            ):
                findings.append(path)
            else:
                findings.extend(_forbidden_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_paths(item, f"{prefix}[{index}]"))
    return findings


def _reject_extra_fields(value: dict[str, Any], allowed: set[str], path: str, findings: list[str]) -> None:
    for field in sorted(set(value) - allowed):
        _add(findings, f"{path}.{field}_unsupported")


def _unique_ids(items: list[Any], field: str, prefix: str, findings: list[str]) -> set[str]:
    result: set[str] = set()
    for index, raw in enumerate(items):
        value = _mapping(raw).get(field)
        if not _text(value) or value in result:
            _add(findings, f"{prefix}[{index}].{field}_missing_or_duplicate")
        else:
            result.add(value)
    return result


def validate_source_package(source_package: Any) -> dict[str, Any]:
    """Validate the bounded PIT source package used by one historical CJO."""
    value = _mapping(source_package)
    findings: list[str] = []
    _reject_extra_fields(
        value,
        {"source_package_id", "company_id", "cutoff_at", "method_version", "sources"},
        "source_package",
        findings,
    )
    for field in ("source_package_id", "company_id", "cutoff_at", "method_version"):
        if not _text(value.get(field)):
            _add(findings, f"source_package.{field}_missing")
    cutoff = _instant(value.get("cutoff_at"))
    if cutoff is None:
        _add(findings, "source_package.cutoff_at_invalid")
        cutoff = datetime.min.replace(tzinfo=timezone.utc)
    sources = [_mapping(item) for item in _items(value.get("sources"))]
    if not sources:
        _add(findings, "source_package.sources_missing")
    source_refs = _unique_ids(sources, "source_ref", "source_package.sources", findings)
    eligibility: dict[str, str] = {}
    available_at: dict[str, datetime] = {}
    for index, source in enumerate(sources):
        _reject_extra_fields(
            source,
            {
                "source_ref", "source_type", "locator", "available_at", "eligibility",
                "responsibility_boundary_ids", "boundary_note",
            },
            f"source_package.sources[{index}]",
            findings,
        )
        for field in ("source_type", "locator"):
            if not _text(source.get(field)):
                _add(findings, f"source_package.sources[{index}].{field}_missing")
        if source.get("eligibility") not in SOURCE_ELIGIBILITY:
            _add(findings, f"source_package.sources[{index}].eligibility_invalid")
        elif _text(source.get("source_ref")):
            eligibility[source["source_ref"]] = source["eligibility"]
        instant = _instant(source.get("available_at"))
        if instant is None:
            _add(findings, f"source_package.sources[{index}].available_at_invalid")
        elif instant > cutoff:
            _add(findings, f"source_package.sources[{index}].after_cutoff")
        elif _text(source.get("source_ref")):
            available_at[source["source_ref"]] = instant
        boundaries = source.get("responsibility_boundary_ids")
        if not isinstance(boundaries, list) or not boundaries or any(not _text(item) for item in boundaries):
            _add(findings, f"source_package.sources[{index}].responsibility_boundary_ids_invalid")
        if source.get("eligibility") == "EVIDENCE_INELIGIBLE" and not _text(source.get("boundary_note")):
            _add(findings, f"source_package.sources[{index}].boundary_note_required")
    for path in _forbidden_paths(value):
        _add(findings, "source_package.forbidden_investment_or_outcome_field:" + path)
    return _validation(
        findings,
        cutoff=cutoff,
        source_refs=source_refs,
        source_eligibility=eligibility,
        source_available_at=available_at,
    )


def _validate_evidence_refs(
    refs: Any,
    *,
    path: str,
    source_refs: set[str],
    findings: list[str],
    required: bool = True,
) -> list[str]:
    values = _items(refs)
    if required and not values:
        _add(findings, path + ".evidence_refs_missing")
    result: list[str] = []
    for index, ref in enumerate(values):
        if not _text(ref) or ref not in source_refs:
            _add(findings, f"{path}.evidence_refs[{index}]_unknown")
        else:
            result.append(ref)
    return result


def validate_enterprise_system_model(model: Any, *, source_package: Any) -> dict[str, Any]:
    """Validate company -> unit -> mechanism -> financial-transmission topology."""
    value = _mapping(model)
    package_validation = validate_source_package(source_package)
    findings = ["source_package:" + item for item in package_validation["findings"]]
    _reject_extra_fields(
        value,
        {
            "schema_version", "model_id", "company_id", "version", "cutoff_at", "method_version",
            "source_package_id", "responsibility_units", "arenas", "operating_variables",
            "mechanisms", "financial_transmissions", "operating_states", "state_changes",
        },
        "enterprise_system_model",
        findings,
    )
    for field in (
        "model_id", "company_id", "version", "cutoff_at", "method_version",
        "source_package_id",
    ):
        if not _text(value.get(field)):
            _add(findings, f"enterprise_system_model.{field}_missing")
    if value.get("schema_version") != ENTERPRISE_SYSTEM_MODEL_VERSION:
        _add(findings, "enterprise_system_model.schema_version_invalid")
    if value.get("company_id") != _mapping(source_package).get("company_id"):
        _add(findings, "enterprise_system_model.company_id_source_package_mismatch")
    if value.get("source_package_id") != _mapping(source_package).get("source_package_id"):
        _add(findings, "enterprise_system_model.source_package_id_mismatch")
    if value.get("method_version") != _mapping(source_package).get("method_version"):
        _add(findings, "enterprise_system_model.method_version_mismatch")
    cutoff = _instant(value.get("cutoff_at"))
    if cutoff is None:
        _add(findings, "enterprise_system_model.cutoff_at_invalid")
        cutoff = datetime.min.replace(tzinfo=timezone.utc)
    if cutoff != package_validation["cutoff"]:
        _add(findings, "enterprise_system_model.cutoff_source_package_mismatch")

    source_refs = package_validation["source_refs"]
    units = [_mapping(item) for item in _items(value.get("responsibility_units"))]
    arenas = [_mapping(item) for item in _items(value.get("arenas"))]
    variables = [_mapping(item) for item in _items(value.get("operating_variables"))]
    mechanisms = [_mapping(item) for item in _items(value.get("mechanisms"))]
    transmissions = [_mapping(item) for item in _items(value.get("financial_transmissions"))]
    states = [_mapping(item) for item in _items(value.get("operating_states"))]
    changes = [_mapping(item) for item in _items(value.get("state_changes"))]
    for name, items in (
        ("responsibility_units", units), ("arenas", arenas),
        ("operating_variables", variables), ("mechanisms", mechanisms),
        ("financial_transmissions", transmissions), ("operating_states", states),
    ):
        if not items:
            _add(findings, f"enterprise_system_model.{name}_missing")

    unit_ids = _unique_ids(units, "unit_id", "enterprise_system_model.responsibility_units", findings)
    for index, unit in enumerate(units):
        _reject_extra_fields(
            unit,
            {
                "unit_id", "unit_type", "parent_unit_id", "accounting_perimeter", "decision_scope",
                "economic_carrier", "measurement_surface", "legal_entity_ids",
            },
            f"enterprise_system_model.responsibility_units[{index}]",
            findings,
        )
        for field in (
            "unit_type", "accounting_perimeter", "decision_scope", "economic_carrier",
            "measurement_surface",
        ):
            if not _text(unit.get(field)):
                _add(findings, f"enterprise_system_model.responsibility_units[{index}].{field}_missing")
        if unit.get("unit_type") not in UNIT_TYPES:
            _add(findings, f"enterprise_system_model.responsibility_units[{index}].unit_type_invalid")
        parent = unit.get("parent_unit_id")
        if parent is not None and (parent not in unit_ids or parent == unit.get("unit_id")):
            _add(findings, f"enterprise_system_model.responsibility_units[{index}].parent_invalid")
        legal_entities = unit.get("legal_entity_ids")
        if not isinstance(legal_entities, list) or not legal_entities or any(not _text(item) for item in legal_entities):
            _add(findings, f"enterprise_system_model.responsibility_units[{index}].legal_entity_ids_invalid")
    parent_by_unit = {unit.get("unit_id"): unit.get("parent_unit_id") for unit in units if _text(unit.get("unit_id"))}
    for unit_id in parent_by_unit:
        visited: set[str] = set()
        cursor: str | None = unit_id
        while cursor is not None and cursor in parent_by_unit:
            if cursor in visited:
                _add(findings, "enterprise_system_model.responsibility_unit_parent_cycle:" + unit_id)
                break
            visited.add(cursor)
            cursor = parent_by_unit[cursor]

    arena_ids = _unique_ids(arenas, "arena_id", "enterprise_system_model.arenas", findings)
    for index, arena in enumerate(arenas):
        _reject_extra_fields(
            arena,
            {
                "arena_id", "responsibility_unit_id", "product_or_service_scope", "customer_task",
                "competition_mechanism", "window", "competitor_or_alternative_refs", "evidence_refs",
            },
            f"enterprise_system_model.arenas[{index}]",
            findings,
        )
        if arena.get("responsibility_unit_id") not in unit_ids:
            _add(findings, f"enterprise_system_model.arenas[{index}].responsibility_unit_unknown")
        for field in ("product_or_service_scope", "customer_task", "competition_mechanism", "window"):
            if not _text(arena.get(field)):
                _add(findings, f"enterprise_system_model.arenas[{index}].{field}_missing")
        if not isinstance(arena.get("competitor_or_alternative_refs"), list):
            _add(findings, f"enterprise_system_model.arenas[{index}].competitor_or_alternative_refs_invalid")
        _validate_evidence_refs(
            arena.get("evidence_refs"), path=f"enterprise_system_model.arenas[{index}]",
            source_refs=source_refs, findings=findings,
        )

    variable_ids = _unique_ids(variables, "variable_id", "enterprise_system_model.operating_variables", findings)
    for index, variable in enumerate(variables):
        _reject_extra_fields(
            variable,
            {"variable_id", "responsibility_unit_id", "arena_id", "name", "observation_state", "evidence_refs"},
            f"enterprise_system_model.operating_variables[{index}]",
            findings,
        )
        if variable.get("responsibility_unit_id") not in unit_ids or variable.get("arena_id") not in arena_ids:
            _add(findings, f"enterprise_system_model.operating_variables[{index}].scope_unknown")
        if not _text(variable.get("name")) or variable.get("observation_state") not in {
            "OBSERVED", "INFERRED", "UNKNOWN", "CONTRADICTED",
        }:
            _add(findings, f"enterprise_system_model.operating_variables[{index}].identity_or_state_invalid")
        _validate_evidence_refs(
            variable.get("evidence_refs"), path=f"enterprise_system_model.operating_variables[{index}]",
            source_refs=source_refs, findings=findings,
            required=variable.get("observation_state") != "UNKNOWN",
        )

    mechanism_ids = _unique_ids(mechanisms, "mechanism_id", "enterprise_system_model.mechanisms", findings)
    for index, mechanism in enumerate(mechanisms):
        _reject_extra_fields(
            mechanism,
            {
                "mechanism_id", "responsibility_unit_id", "arena_id", "description", "reasoning_kind",
                "from_variable_ids", "to_variable_ids", "management_decision_ids", "evidence_refs",
            },
            f"enterprise_system_model.mechanisms[{index}]",
            findings,
        )
        if mechanism.get("responsibility_unit_id") not in unit_ids or mechanism.get("arena_id") not in arena_ids:
            _add(findings, f"enterprise_system_model.mechanisms[{index}].scope_unknown")
        if not _text(mechanism.get("description")) or mechanism.get("reasoning_kind") not in REASONING_KINDS:
            _add(findings, f"enterprise_system_model.mechanisms[{index}].description_or_reasoning_kind_invalid")
        for field in ("from_variable_ids", "to_variable_ids"):
            refs = mechanism.get(field)
            if not isinstance(refs, list) or not refs or any(ref not in variable_ids for ref in refs):
                _add(findings, f"enterprise_system_model.mechanisms[{index}].{field}_invalid")
        if not isinstance(mechanism.get("management_decision_ids"), list):
            _add(findings, f"enterprise_system_model.mechanisms[{index}].management_decision_ids_invalid")
        _validate_evidence_refs(
            mechanism.get("evidence_refs"), path=f"enterprise_system_model.mechanisms[{index}]",
            source_refs=source_refs, findings=findings,
            required=mechanism.get("reasoning_kind") == "OBSERVATION",
        )

    transmission_ids = _unique_ids(
        transmissions, "transmission_id", "enterprise_system_model.financial_transmissions", findings,
    )
    for index, transmission in enumerate(transmissions):
        _reject_extra_fields(
            transmission,
            {"transmission_id", "mechanism_id", "layer", "direction", "description", "evidence_refs"},
            f"enterprise_system_model.financial_transmissions[{index}]",
            findings,
        )
        if transmission.get("mechanism_id") not in mechanism_ids:
            _add(findings, f"enterprise_system_model.financial_transmissions[{index}].mechanism_unknown")
        if transmission.get("layer") not in TRANSMISSION_LAYERS or transmission.get("direction") not in DIRECTIONS:
            _add(findings, f"enterprise_system_model.financial_transmissions[{index}].layer_or_direction_invalid")
        if not _text(transmission.get("description")):
            _add(findings, f"enterprise_system_model.financial_transmissions[{index}].description_missing")
        _validate_evidence_refs(
            transmission.get("evidence_refs"), path=f"enterprise_system_model.financial_transmissions[{index}]",
            source_refs=source_refs, findings=findings,
            required=transmission.get("direction") not in {"UNKNOWN", "NONE"},
        )

    state_ids = _unique_ids(states, "state_id", "enterprise_system_model.operating_states", findings)
    for index, state in enumerate(states):
        _reject_extra_fields(
            state,
            {"state_id", "responsibility_unit_id", "observed_at", "variable_states", "evidence_refs"},
            f"enterprise_system_model.operating_states[{index}]",
            findings,
        )
        if state.get("responsibility_unit_id") not in unit_ids:
            _add(findings, f"enterprise_system_model.operating_states[{index}].responsibility_unit_unknown")
        observed_at = _instant(state.get("observed_at"))
        if observed_at is None or observed_at > cutoff:
            _add(findings, f"enterprise_system_model.operating_states[{index}].observed_at_invalid_or_after_cutoff")
        if not isinstance(state.get("variable_states"), dict):
            _add(findings, f"enterprise_system_model.operating_states[{index}].variable_states_invalid")
        elif any(ref not in variable_ids for ref in state["variable_states"]):
            _add(findings, f"enterprise_system_model.operating_states[{index}].variable_unknown")
        _validate_evidence_refs(
            state.get("evidence_refs"), path=f"enterprise_system_model.operating_states[{index}]",
            source_refs=source_refs, findings=findings,
        )

    change_ids = _unique_ids(changes, "change_id", "enterprise_system_model.state_changes", findings)
    for index, change in enumerate(changes):
        _reject_extra_fields(
            change,
            {"change_id", "from_state_id", "to_state_id", "mechanism_ids", "management_decision_ids", "evidence_refs"},
            f"enterprise_system_model.state_changes[{index}]",
            findings,
        )
        if change.get("from_state_id") not in state_ids or change.get("to_state_id") not in state_ids:
            _add(findings, f"enterprise_system_model.state_changes[{index}].state_ref_invalid")
        if change.get("from_state_id") == change.get("to_state_id"):
            _add(findings, f"enterprise_system_model.state_changes[{index}].state_change_must_change_state")
        mechanism_refs = change.get("mechanism_ids")
        if not isinstance(mechanism_refs, list) or not mechanism_refs or any(ref not in mechanism_ids for ref in mechanism_refs):
            _add(findings, f"enterprise_system_model.state_changes[{index}].mechanism_ids_invalid")
        if not isinstance(change.get("management_decision_ids"), list):
            _add(findings, f"enterprise_system_model.state_changes[{index}].management_decision_ids_invalid")
        _validate_evidence_refs(
            change.get("evidence_refs"), path=f"enterprise_system_model.state_changes[{index}]",
            source_refs=source_refs, findings=findings,
        )

    for path in _forbidden_paths(value):
        _add(findings, "enterprise_system_model.forbidden_price_valuation_training_or_outcome_field:" + path)
    return _validation(
        findings,
        unit_ids=unit_ids,
        arena_ids=arena_ids,
        variable_ids=variable_ids,
        mechanism_ids=mechanism_ids,
        transmission_ids=transmission_ids,
        state_ids=state_ids,
        change_ids=change_ids,
    )


def _decision_snapshots(ledger: dict[str, Any], *, through: datetime | None = None) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for event in ledger.get("events", []):
        recorded_at = _instant(event.get("recorded_at"))
        effective_at = _instant(event.get("effective_at"))
        if through is not None and (
            recorded_at is None or effective_at is None or recorded_at > through or effective_at > through
        ):
            continue
        decision_id = event["decision_id"]
        if event["event_type"] == "DECISION_RECORDED":
            snapshots[decision_id] = {
                key: deepcopy(event.get(key)) for key in (
                    "decision_id", "status", "responsibility_unit_id", "arena_id", "responsible_party",
                    "problem_statement", "expected_mechanism_ids", "strongest_counterargument",
                    "observable_signal_ids", "financial_transmission_ids", "unknowns", "evidence_refs",
                )
            }
            snapshots[decision_id]["last_event_id"] = event["event_id"]
            snapshots[decision_id]["effective_at"] = event["effective_at"]
        elif decision_id in snapshots and event["event_type"] == "STATUS_CHANGED":
            snapshots[decision_id]["status"] = event["to_status"]
            snapshots[decision_id]["last_event_id"] = event["event_id"]
            snapshots[decision_id]["effective_at"] = event["effective_at"]
            if event.get("evidence_refs"):
                snapshots[decision_id]["evidence_refs"] = list(dict.fromkeys(
                    snapshots[decision_id].get("evidence_refs", []) + event["evidence_refs"]
                ))
        elif decision_id in snapshots and event["event_type"] == "EVIDENCE_ATTACHED":
            snapshots[decision_id]["last_event_id"] = event["event_id"]
            snapshots[decision_id]["evidence_refs"] = list(dict.fromkeys(
                snapshots[decision_id].get("evidence_refs", []) + event.get("evidence_refs", [])
            ))
    return snapshots


def validate_management_decision_ledger(ledger: Any, *, source_package: Any) -> dict[str, Any]:
    """Validate an event ledger whose only legal update is a suffix append."""
    value = _mapping(ledger)
    package_validation = validate_source_package(source_package)
    findings = ["source_package:" + item for item in package_validation["findings"]]
    _reject_extra_fields(
        value,
        {"schema_version", "ledger_id", "company_id", "created_at", "append_policy", "events"},
        "management_decision_ledger",
        findings,
    )
    if value.get("schema_version") != MANAGEMENT_DECISION_LEDGER_VERSION:
        _add(findings, "management_decision_ledger.schema_version_invalid")
    for field in ("ledger_id", "company_id", "created_at"):
        if not _text(value.get(field)):
            _add(findings, f"management_decision_ledger.{field}_missing")
    if value.get("company_id") != _mapping(source_package).get("company_id"):
        _add(findings, "management_decision_ledger.company_id_source_package_mismatch")
    if value.get("append_policy") != "EVENT_SUFFIX_ONLY":
        _add(findings, "management_decision_ledger.append_policy_invalid")
    if _instant(value.get("created_at")) is None:
        _add(findings, "management_decision_ledger.created_at_invalid")
    # An empty append-only ledger is valid for J1.  Its meaning is established
    # only by J1's separately evidence-bound decision observation; it is not
    # permission to invent a decision merely to enter reconstruction.
    events = [_mapping(item) for item in _items(value.get("events"))]
    event_ids = _unique_ids(events, "event_id", "management_decision_ledger.events", findings)
    source_refs = package_validation["source_refs"]
    source_available_at = package_validation["source_available_at"]
    snapshots: dict[str, dict[str, Any]] = {}
    prior_recorded: datetime | None = None
    for index, event in enumerate(events):
        path = f"management_decision_ledger.events[{index}]"
        _reject_extra_fields(
            event,
            {
                "event_id", "sequence", "decision_id", "event_type", "recorded_at", "effective_at",
                "status", "from_status", "to_status", "responsibility_unit_id", "arena_id",
                "responsible_party", "problem_statement", "expected_mechanism_ids",
                "strongest_counterargument", "observable_signal_ids", "financial_transmission_ids",
                "unknowns", "evidence_refs", "rationale",
            },
            path,
            findings,
        )
        if event.get("sequence") != index + 1:
            _add(findings, path + ".sequence_not_contiguous")
        if event.get("event_type") not in DECISION_EVENT_TYPES:
            _add(findings, path + ".event_type_invalid")
        if not _text(event.get("decision_id")):
            _add(findings, path + ".decision_id_missing")
        recorded_at = _instant(event.get("recorded_at"))
        effective_at = _instant(event.get("effective_at"))
        if recorded_at is None or effective_at is None:
            _add(findings, path + ".timestamp_invalid")
        elif effective_at > recorded_at:
            _add(findings, path + ".effective_after_recorded")
        if prior_recorded is not None and recorded_at is not None and recorded_at < prior_recorded:
            _add(findings, path + ".recorded_at_not_monotonic")
        if recorded_at is not None:
            prior_recorded = recorded_at
        refs = _validate_evidence_refs(
            event.get("evidence_refs"), path=path, source_refs=source_refs,
            findings=findings, required=event.get("event_type") != "DECISION_RECORDED" or event.get("status") != "PLANNED",
        )
        if recorded_at is not None:
            for ref in refs:
                if source_available_at.get(ref, recorded_at) > recorded_at:
                    _add(findings, path + ".evidence_not_available_when_recorded")
        decision_id = event.get("decision_id")
        if event.get("event_type") == "DECISION_RECORDED":
            if decision_id in snapshots:
                _add(findings, path + ".decision_already_recorded")
                continue
            if event.get("status") not in DECISION_STATUSES:
                _add(findings, path + ".status_invalid")
            for field in (
                "responsibility_unit_id", "arena_id", "responsible_party", "problem_statement",
                "strongest_counterargument",
            ):
                if not _text(event.get(field)):
                    _add(findings, path + f".{field}_missing")
            for field in ("expected_mechanism_ids", "observable_signal_ids", "financial_transmission_ids", "unknowns"):
                values = event.get(field)
                if not isinstance(values, list) or not values:
                    _add(findings, path + f".{field}_missing")
            snapshots[decision_id] = {"status": event.get("status")}
        elif decision_id not in snapshots:
            _add(findings, path + ".decision_not_recorded")
        elif event.get("event_type") == "STATUS_CHANGED":
            if event.get("from_status") != snapshots[decision_id]["status"]:
                _add(findings, path + ".from_status_not_current")
            if event.get("to_status") not in DECISION_STATUSES or event.get("to_status") == event.get("from_status"):
                _add(findings, path + ".to_status_invalid")
            elif event.get("to_status") not in DECISION_STATUS_TRANSITIONS.get(event.get("from_status"), set()):
                _add(findings, path + ".status_transition_invalid")
            if not _text(event.get("rationale")):
                _add(findings, path + ".rationale_missing")
            snapshots[decision_id]["status"] = event.get("to_status")
        elif event.get("event_type") == "EVIDENCE_ATTACHED" and not refs:
            _add(findings, path + ".evidence_attachment_empty")
    for path in _forbidden_paths(value):
        _add(findings, "management_decision_ledger.forbidden_price_valuation_training_or_outcome_field:" + path)
    return _validation(findings, event_ids=event_ids, decision_snapshots=_decision_snapshots(value))


def validate_ledger_extension(previous: Any, current: Any, *, source_package: Any) -> dict[str, Any]:
    """Prove append-only history by direct prefix comparison, without fingerprints."""
    before = _mapping(previous)
    after = _mapping(current)
    findings: list[str] = []
    for field in ("schema_version", "ledger_id", "company_id", "created_at", "append_policy"):
        if before.get(field) != after.get(field):
            _add(findings, "management_decision_ledger.identity_mutated:" + field)
    previous_events = _items(before.get("events"))
    current_events = _items(after.get("events"))
    if len(current_events) <= len(previous_events):
        _add(findings, "management_decision_ledger.extension_requires_new_suffix")
    elif current_events[:len(previous_events)] != previous_events:
        _add(findings, "management_decision_ledger.history_mutated")
    validation = validate_management_decision_ledger(after, source_package=source_package)
    findings.extend(validation["findings"])
    return _validation(list(dict.fromkeys(findings)))


def append_management_decision_event(ledger: Any, event: Any, *, source_package: Any) -> dict[str, Any]:
    """Return a new ledger with exactly one validated event appended."""
    before = deepcopy(_mapping(ledger))
    validation = validate_management_decision_ledger(before, source_package=source_package)
    if validation["state"] != "VALID":
        raise EnterpriseJudgmentCoreError("management_decision_ledger_invalid:" + ",".join(validation["findings"]))
    updated = deepcopy(before)
    updated.setdefault("events", []).append(deepcopy(_mapping(event)))
    extension = validate_ledger_extension(before, updated, source_package=source_package)
    if extension["state"] != "VALID":
        raise EnterpriseJudgmentCoreError("management_decision_ledger_append_rejected:" + ",".join(extension["findings"]))
    return updated


def _aggregate_direction(transmissions: list[dict[str, Any]], layer: str) -> str:
    directions = {
        item.get("direction") for item in transmissions
        if item.get("layer") == layer and item.get("direction") != "NONE"
    }
    if not directions:
        return "UNKNOWN"
    if "MIXED" in directions or len(directions) > 1:
        return "MIXED"
    return next(iter(directions))


def _resolution(
    requested: str,
    central_path: dict[str, Any],
    central_traces: list[dict[str, Any]],
    source_eligibility: dict[str, str],
) -> str:
    if requested not in RESOLUTIONS:
        raise EnterpriseJudgmentCoreError("judgment_input.resolution_invalid")
    if not central_path:
        if requested not in {"NO_PRIMARY", "UNKNOWN"}:
            raise EnterpriseJudgmentCoreError("directional_resolution_requires_central_path")
        return requested
    if requested in {"NO_PRIMARY", "UNKNOWN"}:
        raise EnterpriseJudgmentCoreError("abstention_resolution_cannot_define_central_path")
    if not central_traces or any(source_eligibility.get(item.get("source_ref")) != "ELIGIBLE" for item in central_traces):
        return "NO_PRIMARY"
    # ``resolution`` answers whether the evidenced central operating mechanism
    # is the current primary explanation.  Earnings, owner cash and permanent
    # loss remain separate transmission axes below; an unresolved or opposing
    # downstream axis must constrain only the claim or action that consumes it.
    return requested


def _validate_forward_judgments(
    judgments: list[dict[str, Any]], trace_ids: set[str], findings: list[str], *, prefix: str,
) -> None:
    if not 3 <= len(judgments) <= 5:
        _add(findings, prefix + ".forward_judgments_must_have_3_to_5_items")
    ids = _unique_ids(judgments, "judgment_id", prefix + ".forward_judgments", findings)
    del ids
    for index, judgment in enumerate(judgments):
        path = f"{prefix}.forward_judgments[{index}]"
        for field in ("claim", "horizon", "observable_condition"):
            if not _text(judgment.get(field)):
                _add(findings, path + f".{field}_missing")
        if judgment.get("evidence_state") not in EVIDENCE_STATES:
            _add(findings, path + ".evidence_state_invalid")
        refs = judgment.get("trace_ids")
        if not isinstance(refs, list) or not refs or any(ref not in trace_ids for ref in refs):
            _add(findings, path + ".trace_ids_invalid")
        if judgment.get("evidence_state") in {"MODEL_UNCERTAIN", "EVIDENCE_INELIGIBLE", "UNKNOWN"}:
            if judgment.get("direction") != "UNKNOWN" or judgment.get("status") != "UNKNOWN":
                _add(findings, path + ".uncertain_or_ineligible_must_remain_unknown")
        elif judgment.get("direction") not in DIRECTIONS or judgment.get("status") not in {"OPEN", "SUPPORTED", "CONTRADICTED"}:
            _add(findings, path + ".direction_or_status_invalid")


def _validate_underwriting_thesis_projection(
    projection: Any,
    *,
    cjo: dict[str, Any],
    prefix: str,
    findings: list[str],
) -> None:
    """Keep an optional complete underwriting thesis bound to the CJO.

    The Episode remains the composition/read model.  This validator only
    checks that its price-free projection has not changed company, cutoff, or
    the two narrative claims also represented by the narrower CJO schema.
    Legacy CJO objects omit the projection and remain valid.
    """
    if projection is None:
        return
    value = _mapping(projection)
    if not value:
        _add(findings, prefix + ".underwriting_thesis_projection_invalid")
        return
    try:
        from scripts.enterprise_underwriting_episode import (
            validate_price_free_underwriting_thesis_projection,
        )
    except ModuleNotFoundError:  # pragma: no cover - direct script fallback
        from enterprise_underwriting_episode import (
            validate_price_free_underwriting_thesis_projection,
        )
    projection_validation = validate_price_free_underwriting_thesis_projection(value)
    for finding in projection_validation.get("findings") or []:
        _add(
            findings,
            prefix + ".underwriting_thesis_projection." + str(finding),
        )
    if value.get("schema_version") != "enterprise-underwriting-thesis-projection.v1":
        _add(findings, prefix + ".underwriting_thesis_projection.schema_version_invalid")
    mapping_fields = {
        "situation_model", "value_route", "underwriting_thesis",
    }
    list_fields = {
        "reversal_observations", "component_treatments", "evidence_trace",
    }
    for field in (
        "episode_id", "company_id", "cutoff_at", "sample_identity",
        "underwriting_thesis_id", "decision_frame", "underwriting_route",
        "situation_model", "business_position",
        "survival_case", "adaptation_case", "normalization_case",
        "permanent_loss_map", "value_route", "strongest_rival",
        "reversal_observations", "component_treatments", "evidence_trace",
        "underwriting_thesis",
    ):
        item = value.get(field)
        if field in mapping_fields:
            if not _mapping(item):
                _add(findings, prefix + ".underwriting_thesis_projection." + field + "_missing")
        elif field in list_fields:
            if not _items(item):
                _add(findings, prefix + ".underwriting_thesis_projection." + field + "_missing")
        elif not _text(item):
            _add(findings, prefix + ".underwriting_thesis_projection." + field + "_missing")
    if value.get("company_id") != cjo.get("company_id"):
        _add(findings, prefix + ".underwriting_thesis_projection_company_id_mismatch")
    if value.get("cutoff_at") != cjo.get("cutoff_at"):
        _add(findings, prefix + ".underwriting_thesis_projection_cutoff_mismatch")

    thesis = _mapping(value.get("underwriting_thesis"))
    if thesis.get("thesis_id") != value.get("underwriting_thesis_id"):
        _add(findings, prefix + ".underwriting_thesis_projection_thesis_id_mismatch")
    central_claim = _mapping(cjo.get("central_path")).get("claim")
    if thesis.get("central_path") != central_claim:
        _add(findings, prefix + ".underwriting_thesis_projection_central_path_mismatch")
    rival_claim = _mapping(cjo.get("strongest_counterargument")).get("claim")
    if thesis.get("strongest_rival") != rival_claim:
        _add(findings, prefix + ".underwriting_thesis_projection_strongest_rival_mismatch")
    if value.get("strongest_rival") != thesis.get("strongest_rival"):
        _add(findings, prefix + ".underwriting_thesis_projection_rival_internal_mismatch")
    directions = _mapping(thesis.get("economic_directions"))
    expected_directions = {
        "normal_earnings": _mapping(cjo.get("normal_earnings_transmission")).get("direction"),
        "owner_cash": _mapping(cjo.get("owner_cash_transmission")).get("direction"),
    }
    for axis, observed in expected_directions.items():
        if directions.get(axis) != observed:
            _add(
                findings,
                prefix + ".underwriting_thesis_projection_" + axis + "_direction_mismatch",
            )
    loss_directions = {
        str(item.get("direction") or "")
        for item in _items(cjo.get("permanent_loss_paths"))
        if isinstance(item, dict)
    }
    expected_loss = directions.get("permanent_loss")
    if loss_directions != ({expected_loss} if expected_loss != "NONE" else set()):
        _add(
            findings,
            prefix + ".underwriting_thesis_projection_permanent_loss_direction_mismatch",
        )
    enterprise_transmissions = {
        str(item.get("transmission_id") or ""): item
        for item in _items(_mapping(cjo.get("enterprise_system_ref")).get("financial_transmissions"))
        if isinstance(item, dict) and item.get("transmission_id")
    }
    for field, axis in (
        ("normal_earnings_transmission", "normal_earnings"),
        ("owner_cash_transmission", "owner_cash"),
    ):
        summary = _mapping(cjo.get(field))
        for transmission_id in _items(summary.get("transmission_ids")):
            if _mapping(enterprise_transmissions.get(str(transmission_id))).get("direction") != directions.get(axis):
                _add(
                    findings,
                    prefix + ".underwriting_thesis_projection_" + axis
                    + "_enterprise_transmission_direction_mismatch:" + str(transmission_id),
                )
    for path in _items(cjo.get("permanent_loss_paths")):
        item = _mapping(path)
        transmission_id = str(item.get("transmission_id") or "")
        if _mapping(enterprise_transmissions.get(transmission_id)).get("direction") != item.get("direction"):
            _add(
                findings,
                prefix
                + ".underwriting_thesis_projection_permanent_loss_enterprise_transmission_direction_mismatch:"
                + transmission_id,
            )
    for path in _forbidden_paths(value):
        _add(
            findings,
            prefix + ".underwriting_thesis_projection_forbidden_price_valuation_or_outcome_field:"
            + path,
        )


def compile_cjo_candidate(
    *,
    model: Any,
    ledger: Any,
    source_package: Any,
    judgment_input: Any,
    underwriting_episode: Any | None = None,
) -> dict[str, Any]:
    """Compile a review-ready candidate.  This function cannot freeze or authorize it."""
    model_value = _mapping(model)
    ledger_value = _mapping(ledger)
    package_value = _mapping(source_package)
    judgment = _mapping(judgment_input)
    model_validation = validate_enterprise_system_model(model_value, source_package=package_value)
    ledger_validation = validate_management_decision_ledger(ledger_value, source_package=package_value)
    findings = ["model:" + item for item in model_validation["findings"]]
    findings.extend("ledger:" + item for item in ledger_validation["findings"])
    if findings:
        raise EnterpriseJudgmentCoreError("cjo_candidate_inputs_invalid:" + ",".join(findings))
    for field in ("candidate_id", "judgment_owner_id", "compiled_at", "resolution"):
        if not _text(judgment.get(field)):
            raise EnterpriseJudgmentCoreError("judgment_input." + field + "_missing")
    if _instant(judgment.get("compiled_at")) is None:
        raise EnterpriseJudgmentCoreError("judgment_input.compiled_at_invalid")
    cutoff = model_validation.get("cutoff") or _instant(model_value.get("cutoff_at"))
    decision_snapshots = _decision_snapshots(ledger_value, through=cutoff)

    unit_by_id = {item["unit_id"]: item for item in model_value["responsibility_units"]}
    variable_by_id = {item["variable_id"]: item for item in model_value["operating_variables"]}
    mechanism_by_id = {item["mechanism_id"]: item for item in model_value["mechanisms"]}
    transmission_by_id = {
        item["transmission_id"]: item for item in model_value["financial_transmissions"]
    }
    model_decision_ids = {
        decision_id
        for mechanism in model_value["mechanisms"]
        for decision_id in mechanism.get("management_decision_ids", [])
    } | {
        decision_id
        for change in model_value.get("state_changes", [])
        for decision_id in change.get("management_decision_ids", [])
    }
    missing_model_decisions = model_decision_ids - set(decision_snapshots)
    if missing_model_decisions:
        raise EnterpriseJudgmentCoreError(
            "enterprise_model_decision_not_available_at_cutoff:" + ",".join(sorted(missing_model_decisions))
        )
    for decision_id in model_decision_ids:
        decision = decision_snapshots[decision_id]
        if decision.get("responsibility_unit_id") not in unit_by_id:
            raise EnterpriseJudgmentCoreError("management_decision_responsibility_unit_not_in_model:" + decision_id)
        if decision.get("arena_id") not in {item["arena_id"] for item in model_value["arenas"]}:
            raise EnterpriseJudgmentCoreError("management_decision_arena_not_in_model:" + decision_id)
        if any(item not in mechanism_by_id for item in decision.get("expected_mechanism_ids", [])):
            raise EnterpriseJudgmentCoreError("management_decision_mechanism_not_in_model:" + decision_id)
        if any(item not in transmission_by_id for item in decision.get("financial_transmission_ids", [])):
            raise EnterpriseJudgmentCoreError("management_decision_financial_transmission_not_in_model:" + decision_id)
    source_eligibility = validate_source_package(package_value)["source_eligibility"]
    source_by_ref = {item["source_ref"]: item for item in package_value["sources"]}

    traces = [_mapping(item) for item in _items(judgment.get("traceability"))]
    trace_findings: list[str] = []
    trace_ids = _unique_ids(traces, "trace_id", "judgment_input.traceability", trace_findings)
    for index, trace in enumerate(traces):
        path = f"judgment_input.traceability[{index}]"
        if trace.get("source_ref") not in source_by_ref:
            _add(trace_findings, path + ".source_ref_unknown")
        if trace.get("responsibility_unit_id") not in unit_by_id:
            _add(trace_findings, path + ".responsibility_unit_unknown")
        if trace.get("mechanism_id") not in mechanism_by_id:
            _add(trace_findings, path + ".mechanism_unknown")
        if trace.get("reasoning_kind") not in REASONING_KINDS:
            _add(trace_findings, path + ".reasoning_kind_invalid")
        transmission_ids = trace.get("financial_transmission_ids")
        if not isinstance(transmission_ids, list) or not transmission_ids or any(
            item not in transmission_by_id for item in transmission_ids
        ):
            _add(trace_findings, path + ".financial_transmission_ids_invalid")
        elif trace.get("mechanism_id") in mechanism_by_id and any(
            transmission_by_id[item]["mechanism_id"] != trace.get("mechanism_id")
            for item in transmission_ids
        ):
            _add(trace_findings, path + ".financial_transmission_mechanism_mismatch")
    if trace_findings:
        raise EnterpriseJudgmentCoreError("judgment_input_traceability_invalid:" + ",".join(trace_findings))

    central_path = deepcopy(_mapping(judgment.get("central_path")))
    if central_path and not _text(central_path.get("claim")):
        raise EnterpriseJudgmentCoreError("judgment_input.central_path.claim_missing")
    central_trace_ids = _items(central_path.get("trace_ids"))
    if central_path and (
        not central_trace_ids or any(item not in trace_ids for item in central_trace_ids)
    ):
        raise EnterpriseJudgmentCoreError("judgment_input.central_path.trace_ids_invalid")
    trace_by_id = {item["trace_id"]: item for item in traces}
    central_traces = [trace_by_id[item] for item in central_trace_ids]
    central_transmission_ids = list(dict.fromkeys(
        transmission_id
        for trace in central_traces
        for transmission_id in trace.get("financial_transmission_ids", [])
    ))
    central_transmissions = [transmission_by_id[item] for item in central_transmission_ids]
    resolution = _resolution(
        judgment["resolution"], central_path, central_traces,
        source_eligibility,
    )
    if resolution == "NO_PRIMARY":
        central_path = {}
        central_trace_ids = []
        central_transmission_ids = []
        central_transmissions = []

    forward_judgments = deepcopy([_mapping(item) for item in _items(judgment.get("forward_judgments"))])
    forward_findings: list[str] = []
    _validate_forward_judgments(forward_judgments, trace_ids, forward_findings, prefix="judgment_input")
    for index, item in enumerate(forward_judgments):
        item_traces = [trace_by_id[trace_id] for trace_id in item.get("trace_ids", [])]
        if any(source_eligibility.get(trace.get("source_ref")) == "EVIDENCE_INELIGIBLE" for trace in item_traces):
            if item.get("evidence_state") != "EVIDENCE_INELIGIBLE":
                _add(
                    forward_findings,
                    f"judgment_input.forward_judgments[{index}].ineligible_source_must_remain_evidence_ineligible",
                )
    if forward_findings:
        raise EnterpriseJudgmentCoreError("judgment_input_forward_judgments_invalid:" + ",".join(forward_findings))
    strongest_counterargument = deepcopy(_mapping(judgment.get("strongest_counterargument")))
    if not _text(strongest_counterargument.get("claim")):
        raise EnterpriseJudgmentCoreError("judgment_input.strongest_counterargument.claim_missing")
    counter_trace_ids = strongest_counterargument.get("trace_ids")
    if not isinstance(counter_trace_ids, list) or not counter_trace_ids or any(item not in trace_ids for item in counter_trace_ids):
        raise EnterpriseJudgmentCoreError("judgment_input.strongest_counterargument.trace_ids_invalid")

    key_driver_ids = judgment.get("key_driver_ids")
    if not isinstance(key_driver_ids, list) or not key_driver_ids or any(item not in variable_by_id for item in key_driver_ids):
        raise EnterpriseJudgmentCoreError("judgment_input.key_driver_ids_invalid")
    unknowns = deepcopy([_mapping(item) for item in _items(judgment.get("unknowns"))])
    for index, unknown in enumerate(unknowns):
        for field in ("unknown_id", "description", "conservative_treatment", "closing_evidence"):
            if not _text(unknown.get(field)):
                raise EnterpriseJudgmentCoreError(f"judgment_input.unknowns[{index}].{field}_missing")
    monitoring = deepcopy(_mapping(judgment.get("monitoring_contract")))
    if not _text(monitoring.get("contract_id")) or not isinstance(monitoring.get("signals"), list) or not monitoring["signals"]:
        raise EnterpriseJudgmentCoreError("judgment_input.monitoring_contract_invalid")

    used_trace_ids = set(central_trace_ids) | set(counter_trace_ids)
    for item in forward_judgments:
        used_trace_ids.update(item["trace_ids"])
    used_traces = [deepcopy(item) for item in traces if item["trace_id"] in used_trace_ids]
    used_mechanism_ids = {item["mechanism_id"] for item in used_traces}
    used_mechanisms = [
        mechanism_by_id[item] for item in sorted(used_mechanism_ids)
    ]
    used_variable_ids = {
        variable_id
        for mechanism in used_mechanisms
        for field in ("from_variable_ids", "to_variable_ids")
        for variable_id in mechanism.get(field, [])
    }
    used_variable_ids.update(key_driver_ids)
    used_arena_ids = {
        str(mechanism.get("arena_id")) for mechanism in used_mechanisms
        if _text(mechanism.get("arena_id"))
    }
    used_transmission_ids = {
        ref for item in used_traces for ref in item["financial_transmission_ids"]
    }
    used_unit_ids = {item["responsibility_unit_id"] for item in used_traces}
    used_source_refs = {item["source_ref"] for item in used_traces}
    selected_model_items = (
        [item for item in model_value["arenas"] if item["arena_id"] in used_arena_ids]
        + [item for item in model_value["operating_variables"] if item["variable_id"] in used_variable_ids]
        + [item for item in model_value["mechanisms"] if item["mechanism_id"] in used_mechanism_ids]
        + [item for item in model_value["financial_transmissions"] if item["transmission_id"] in used_transmission_ids]
        + [
            item for item in model_value["operating_states"]
            if item["responsibility_unit_id"] in used_unit_ids
            and any(variable_id in used_variable_ids for variable_id in item.get("variable_states", {}))
        ]
        + [
            item for item in model_value["state_changes"]
            if any(
                mechanism_id in used_mechanism_ids
                for mechanism_id in item.get("mechanism_ids", [])
            )
        ]
    )
    for item in selected_model_items:
        used_source_refs.update(item.get("evidence_refs", []))
    used_decision_ids = {
        decision_id
        for mechanism_id in used_mechanism_ids
        for decision_id in mechanism_by_id[mechanism_id].get("management_decision_ids", [])
    }
    missing_decisions = used_decision_ids - set(decision_snapshots)
    if missing_decisions:
        raise EnterpriseJudgmentCoreError(
            "enterprise_mechanism_decision_not_available_at_cutoff:" + ",".join(sorted(missing_decisions))
        )
    for decision_id in used_decision_ids:
        used_source_refs.update(decision_snapshots[decision_id].get("evidence_refs", []))

    underwriting_projection: dict[str, Any] | None = None
    if underwriting_episode is not None:
        try:
            from scripts.enterprise_underwriting_episode import (
                project_price_free_underwriting_thesis,
                validate_enterprise_underwriting_episode,
            )
        except ModuleNotFoundError:  # pragma: no cover - direct script fallback
            from enterprise_underwriting_episode import (
                project_price_free_underwriting_thesis,
                validate_enterprise_underwriting_episode,
            )
        episode_validation = validate_enterprise_underwriting_episode(
            underwriting_episode
        )
        if episode_validation.get("state") != "REVIEWABLE":
            raise EnterpriseJudgmentCoreError(
                "underwriting_episode_invalid:"
                + ",".join(str(item) for item in episode_validation.get("findings") or [])
            )
        underwriting_projection = project_price_free_underwriting_thesis(
            underwriting_episode
        )
        if underwriting_projection.get("sample_identity") != "WORKED_CASE":
            package_source_refs = {
                str(item.get("source_ref") or "")
                for item in _items(package_value.get("sources"))
                if isinstance(item, dict)
            }
            episode_source_refs = {
                str(item.get("source_ref") or "")
                for item in _items(underwriting_projection.get("evidence_trace"))
                if isinstance(item, dict)
            }
            missing_episode_sources = episode_source_refs - package_source_refs
            if missing_episode_sources:
                raise EnterpriseJudgmentCoreError(
                    "underwriting_episode_evidence_not_in_source_package:"
                    + ",".join(sorted(missing_episode_sources))
                )

    economic_directions = _mapping(
        _mapping(underwriting_projection.get("underwriting_thesis")).get(
            "economic_directions"
        )
    ) if underwriting_projection is not None else {}
    normal_earnings_direction = (
        economic_directions.get("normal_earnings")
        if economic_directions else _aggregate_direction(central_transmissions, "NORMAL_EARNINGS")
    )
    owner_cash_direction = (
        economic_directions.get("owner_cash")
        if economic_directions else _aggregate_direction(central_transmissions, "OWNER_CASH")
    )
    permanent_loss_paths = [
        deepcopy(item) for item in central_transmissions if item["layer"] == "PERMANENT_LOSS"
    ]
    if economic_directions:
        expected_loss_direction = economic_directions.get("permanent_loss")
        if expected_loss_direction == "NONE":
            permanent_loss_paths = []
        else:
            for item in permanent_loss_paths:
                item["direction"] = expected_loss_direction
    selected_financial_transmissions = [
        deepcopy(item)
        for item in model_value["financial_transmissions"]
        if item["transmission_id"] in used_transmission_ids
    ]
    if economic_directions:
        direction_by_layer = {
            "NORMAL_EARNINGS": economic_directions.get("normal_earnings"),
            "OWNER_CASH": economic_directions.get("owner_cash"),
            "PERMANENT_LOSS": economic_directions.get("permanent_loss"),
        }
        for item in selected_financial_transmissions:
            if item.get("layer") in direction_by_layer:
                item["direction"] = direction_by_layer[item["layer"]]

    candidate = {
        "schema_version": CJO_CANDIDATE_VERSION,
        "object_class": "COMPANY_JUDGMENT_OBJECT_CANDIDATE",
        "candidate_id": judgment["candidate_id"],
        "company_id": model_value["company_id"],
        "cutoff_at": model_value["cutoff_at"],
        "method_version": model_value["method_version"],
        "compiled_at": judgment["compiled_at"],
        "judgment_owner_id": judgment["judgment_owner_id"],
        "state": "REVIEW_READY",
        "resolution": resolution,
        "central_path": central_path,
        "forward_judgments": forward_judgments,
        "key_operating_drivers": [deepcopy(variable_by_id[item]) for item in key_driver_ids],
        "normal_earnings_transmission": {
            "direction": normal_earnings_direction,
            "transmission_ids": [
                item["transmission_id"] for item in central_transmissions
                if item["layer"] == "NORMAL_EARNINGS" and normal_earnings_direction != "NONE"
            ],
        },
        "owner_cash_transmission": {
            "direction": owner_cash_direction,
            "transmission_ids": [
                item["transmission_id"] for item in central_transmissions
                if item["layer"] == "OWNER_CASH" and owner_cash_direction != "NONE"
            ],
        },
        "permanent_loss_paths": permanent_loss_paths,
        "strongest_counterargument": strongest_counterargument,
        "unknowns": unknowns,
        "monitoring_contract": monitoring,
        "traceability": used_traces,
        "source_package": {
            "source_package_id": package_value["source_package_id"],
            "company_id": package_value["company_id"],
            "cutoff_at": package_value["cutoff_at"],
            "method_version": package_value["method_version"],
            "sources": [
                deepcopy(item) for item in package_value["sources"]
                if item["source_ref"] in used_source_refs
            ],
        },
        "enterprise_system_ref": {
            "model_id": model_value["model_id"],
            "version": model_value["version"],
            "responsibility_units": [
                deepcopy(item) for item in model_value["responsibility_units"]
                if item["unit_id"] in used_unit_ids
            ],
            "arenas": [
                deepcopy(item) for item in model_value["arenas"]
                if item["arena_id"] in used_arena_ids
            ],
            "operating_variables": [
                deepcopy(item) for item in model_value["operating_variables"]
                if item["variable_id"] in used_variable_ids
            ],
            "mechanisms": [
                deepcopy(item) for item in model_value["mechanisms"]
                if item["mechanism_id"] in used_mechanism_ids
            ],
            "financial_transmissions": [
                deepcopy(item) for item in selected_financial_transmissions
            ],
            "operating_states": [
                deepcopy(item) for item in model_value["operating_states"]
                if item["responsibility_unit_id"] in used_unit_ids
                and any(
                    variable_id in used_variable_ids
                    for variable_id in item.get("variable_states", {})
                )
            ],
            "state_changes": [
                deepcopy(item) for item in model_value["state_changes"]
                if any(
                    mechanism_id in used_mechanism_ids
                    for mechanism_id in item.get("mechanism_ids", [])
                )
            ],
        },
        "management_decision_ledger_ref": {
            "ledger_id": ledger_value["ledger_id"],
            "event_count_at_cutoff": sum(
                1 for event in ledger_value["events"]
                if _instant(event["recorded_at"]) <= cutoff and _instant(event["effective_at"]) <= cutoff
            ),
            "decisions": [deepcopy(decision_snapshots[item]) for item in sorted(used_decision_ids)],
            "events": [
                deepcopy(event) for event in ledger_value["events"]
                if event.get("decision_id") in used_decision_ids
                and _instant(event.get("recorded_at")) <= cutoff
                and _instant(event.get("effective_at")) <= cutoff
            ],
        },
        "authority": {
            "canonical": False,
            "freeze_allowed": False,
            "report_read_allowed": False,
            "quantitative_read_allowed": False,
            "investment_authorization": False,
        },
    }
    if underwriting_projection is not None:
        candidate["underwriting_thesis_projection"] = deepcopy(
            underwriting_projection
        )
    candidate_validation = validate_cjo_candidate(candidate)
    if candidate_validation["state"] != "VALID":
        raise EnterpriseJudgmentCoreError("compiled_cjo_candidate_invalid:" + ",".join(candidate_validation["findings"]))
    return candidate


def _validate_cjo_reader_projection(
    value: dict[str, Any],
    *,
    prefix: str,
    source_validation: dict[str, Any],
    findings: list[str],
) -> None:
    """Deep-check the reader projection without invalidating older v1 omissions."""
    enterprise = _mapping(value.get("enterprise_system_ref"))
    cutoff = _instant(value.get("cutoff_at"))
    source_refs = set(source_validation.get("source_refs") or set())
    source_available = source_validation.get("source_available_at") or {}

    def evidence_refs(item: dict[str, Any], path: str, *, required: bool = True) -> list[str]:
        refs = _validate_evidence_refs(
            item.get("evidence_refs"), path=path, source_refs=source_refs,
            findings=findings, required=required,
        )
        if cutoff is not None:
            for ref in refs:
                available = source_available.get(ref)
                if available is None or available > cutoff:
                    _add(findings, path + ".source_not_available_at_cutoff:" + ref)
        return refs

    units = [_mapping(item) for item in _items(enterprise.get("responsibility_units"))]
    unit_ids = _unique_ids(units, "unit_id", prefix + ".enterprise_system_ref.responsibility_units", findings)
    for index, unit in enumerate(units):
        path = f"{prefix}.enterprise_system_ref.responsibility_units[{index}]"
        for field in (
            "accounting_perimeter", "decision_scope", "economic_carrier",
            "measurement_surface",
        ):
            if not _text(unit.get(field)):
                _add(findings, path + "." + field + "_missing")

    arenas_present = "arenas" in enterprise
    arenas_value = enterprise.get("arenas")
    if arenas_present and not isinstance(arenas_value, list):
        _add(findings, prefix + ".enterprise_system_ref.arenas_invalid")
    arenas = [_mapping(item) for item in _items(arenas_value)]
    arena_ids = _unique_ids(arenas, "arena_id", prefix + ".enterprise_system_ref.arenas", findings)
    arena_by_id = {item.get("arena_id"): item for item in arenas if _text(item.get("arena_id"))}
    for index, arena in enumerate(arenas):
        path = f"{prefix}.enterprise_system_ref.arenas[{index}]"
        if arena.get("responsibility_unit_id") not in unit_ids:
            _add(findings, path + ".responsibility_unit_unknown")
        for field in (
            "product_or_service_scope", "customer_task", "competition_mechanism", "window",
        ):
            if not _text(arena.get(field)):
                _add(findings, path + "." + field + "_missing")
        evidence_refs(arena, path)

    variables_present = "operating_variables" in enterprise
    variables_value = enterprise.get("operating_variables")
    if variables_present and not isinstance(variables_value, list):
        _add(findings, prefix + ".enterprise_system_ref.operating_variables_invalid")
    variables = [_mapping(item) for item in _items(variables_value)]
    variable_ids = _unique_ids(
        variables, "variable_id", prefix + ".enterprise_system_ref.operating_variables", findings,
    )
    variable_by_id = {
        item.get("variable_id"): item for item in variables if _text(item.get("variable_id"))
    }
    for index, variable in enumerate(variables):
        path = f"{prefix}.enterprise_system_ref.operating_variables[{index}]"
        if variable.get("responsibility_unit_id") not in unit_ids:
            _add(findings, path + ".responsibility_unit_unknown")
        if arenas_present and variable.get("arena_id") not in arena_ids:
            _add(findings, path + ".arena_unknown")
        if not _text(variable.get("name")) or variable.get("observation_state") not in {
            "OBSERVED", "INFERRED", "UNKNOWN", "CONTRADICTED",
        }:
            _add(findings, path + ".name_or_observation_state_invalid")
        evidence_refs(
            variable, path,
            required=variable.get("observation_state") not in {"UNKNOWN"},
        )

    mechanisms = [_mapping(item) for item in _items(enterprise.get("mechanisms"))]
    mechanism_ids = _unique_ids(
        mechanisms, "mechanism_id", prefix + ".enterprise_system_ref.mechanisms", findings,
    )
    mechanism_by_id = {
        item.get("mechanism_id"): item for item in mechanisms if _text(item.get("mechanism_id"))
    }
    for index, mechanism in enumerate(mechanisms):
        path = f"{prefix}.enterprise_system_ref.mechanisms[{index}]"
        unit_id = mechanism.get("responsibility_unit_id")
        arena_id = mechanism.get("arena_id")
        if unit_id not in unit_ids:
            _add(findings, path + ".responsibility_unit_unknown")
        if arenas_present and arena_id not in arena_ids:
            _add(findings, path + ".arena_unknown")
        if arenas_present and arena_id in arena_by_id and arena_by_id[arena_id].get("responsibility_unit_id") != unit_id:
            _add(findings, path + ".arena_unit_mismatch")
        if not _text(mechanism.get("description")) or mechanism.get("reasoning_kind") not in REASONING_KINDS:
            _add(findings, path + ".description_or_reasoning_kind_invalid")
        for field in ("from_variable_ids", "to_variable_ids"):
            ids = mechanism.get(field)
            if not isinstance(ids, list) or not ids:
                _add(findings, path + "." + field + "_missing")
                continue
            if variables_present and any(item not in variable_ids for item in ids):
                _add(findings, path + "." + field + "_unknown")
            if variables_present and any(
                variable_by_id.get(item, {}).get("responsibility_unit_id") != unit_id
                or variable_by_id.get(item, {}).get("arena_id") != arena_id
                for item in ids if item in variable_by_id
            ):
                _add(findings, path + ".variable_scope_mismatch")
        evidence_refs(
            mechanism, path,
            required=mechanism.get("reasoning_kind") == "OBSERVATION",
        )

    transmissions = [
        _mapping(item) for item in _items(enterprise.get("financial_transmissions"))
    ]
    transmission_ids = _unique_ids(
        transmissions, "transmission_id",
        prefix + ".enterprise_system_ref.financial_transmissions", findings,
    )
    for index, transmission in enumerate(transmissions):
        path = f"{prefix}.enterprise_system_ref.financial_transmissions[{index}]"
        if transmission.get("mechanism_id") not in mechanism_ids:
            _add(findings, path + ".mechanism_unknown")
        if transmission.get("layer") not in {"NORMAL_EARNINGS", "OWNER_CASH", "PERMANENT_LOSS"}:
            _add(findings, path + ".layer_invalid")
        if transmission.get("direction") not in DIRECTIONS or not _text(transmission.get("description")):
            _add(findings, path + ".direction_or_description_invalid")
        evidence_refs(
            transmission, path,
            required=transmission.get("direction") not in {"UNKNOWN", "NONE"},
        )

    states_present = "operating_states" in enterprise
    states_value = enterprise.get("operating_states")
    if states_present and not isinstance(states_value, list):
        _add(findings, prefix + ".enterprise_system_ref.operating_states_invalid")
    states = [_mapping(item) for item in _items(states_value)]
    state_ids = _unique_ids(states, "state_id", prefix + ".enterprise_system_ref.operating_states", findings)
    state_by_id = {item.get("state_id"): item for item in states if _text(item.get("state_id"))}
    for index, state in enumerate(states):
        path = f"{prefix}.enterprise_system_ref.operating_states[{index}]"
        unit_id = state.get("responsibility_unit_id")
        if unit_id not in unit_ids:
            _add(findings, path + ".responsibility_unit_unknown")
        observed_at = _instant(state.get("observed_at"))
        if observed_at is None or cutoff is None or observed_at > cutoff:
            _add(findings, path + ".observed_at_after_cutoff_or_invalid")
        variable_states = state.get("variable_states")
        if not isinstance(variable_states, dict) or not variable_states:
            _add(findings, path + ".variable_states_invalid")
        else:
            for variable_id, state_value in variable_states.items():
                if variables_present and variable_id not in variable_ids:
                    _add(findings, path + ".variable_unknown:" + str(variable_id))
                elif variables_present and variable_by_id.get(variable_id, {}).get("responsibility_unit_id") != unit_id:
                    _add(findings, path + ".variable_unit_mismatch:" + str(variable_id))
                if not _text(state_value):
                    _add(findings, path + ".state_value_missing:" + str(variable_id))
        evidence_refs(state, path)

    decision_ref = _mapping(value.get("management_decision_ledger_ref"))
    decisions_value = decision_ref.get("decisions")
    if not isinstance(decisions_value, list):
        _add(findings, prefix + ".management_decision_ledger_ref.decisions_invalid")
    decisions = [_mapping(item) for item in _items(decisions_value)]
    decision_ids = _unique_ids(
        decisions, "decision_id", prefix + ".management_decision_ledger_ref.decisions", findings,
    )
    for index, mechanism in enumerate(mechanisms):
        decision_links = mechanism.get("management_decision_ids")
        if not isinstance(decision_links, list) or any(
            item not in decision_ids for item in decision_links
        ):
            _add(
                findings,
                f"{prefix}.enterprise_system_ref.mechanisms[{index}].management_decision_ids_invalid",
            )
    for index, decision in enumerate(decisions):
        path = f"{prefix}.management_decision_ledger_ref.decisions[{index}]"
        if decision.get("responsibility_unit_id") not in unit_ids:
            _add(findings, path + ".responsibility_unit_unknown")
        if arenas_present and decision.get("arena_id") not in arena_ids:
            _add(findings, path + ".arena_unknown")
        for field in ("responsible_party", "problem_statement", "strongest_counterargument"):
            if not _text(decision.get(field)):
                _add(findings, path + "." + field + "_missing")
        if decision.get("status") not in DECISION_STATUSES:
            _add(findings, path + ".status_invalid")
        effective_at = _instant(decision.get("effective_at"))
        if effective_at is None or cutoff is None or effective_at > cutoff:
            _add(findings, path + ".effective_at_after_cutoff_or_invalid")
        for field, known in (
            ("expected_mechanism_ids", mechanism_ids),
            ("financial_transmission_ids", transmission_ids),
        ):
            ids = decision.get(field)
            if not isinstance(ids, list) or not ids or any(item not in known for item in ids):
                _add(findings, path + "." + field + "_invalid")
        for field in ("observable_signal_ids", "unknowns"):
            items = decision.get(field)
            if not isinstance(items, list) or not items or any(not _text(item) for item in items):
                _add(findings, path + "." + field + "_invalid")
        evidence_refs(decision, path, required=decision.get("status") != "PLANNED")

    events_present = "events" in decision_ref
    events_value = decision_ref.get("events")
    if events_present and not isinstance(events_value, list):
        _add(findings, prefix + ".management_decision_ledger_ref.events_invalid")
    events = [_mapping(item) for item in _items(events_value)]
    _unique_ids(events, "event_id", prefix + ".management_decision_ledger_ref.events", findings)
    event_count_at_cutoff = decision_ref.get("event_count_at_cutoff")
    if (
        not isinstance(event_count_at_cutoff, int)
        or event_count_at_cutoff < len(events)
    ):
        _add(findings, prefix + ".management_decision_ledger_ref.event_count_at_cutoff_invalid")
    event_status: dict[str, str] = {}
    prior_recorded: datetime | None = None
    prior_sequence = 0
    for index, event in enumerate(events):
        path = f"{prefix}.management_decision_ledger_ref.events[{index}]"
        decision_id = event.get("decision_id")
        if decision_id not in decision_ids:
            _add(findings, path + ".decision_unknown")
        event_type = event.get("event_type")
        if event_type not in DECISION_EVENT_TYPES:
            _add(findings, path + ".event_type_invalid")
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or sequence <= prior_sequence:
            _add(findings, path + ".sequence_invalid_or_not_monotonic")
        elif sequence > 0:
            prior_sequence = sequence
        recorded_at = _instant(event.get("recorded_at"))
        effective_at = _instant(event.get("effective_at"))
        if (
            recorded_at is None or effective_at is None or cutoff is None
            or effective_at > recorded_at or recorded_at > cutoff or effective_at > cutoff
        ):
            _add(findings, path + ".timestamp_or_cutoff_invalid")
        if prior_recorded is not None and recorded_at is not None and recorded_at < prior_recorded:
            _add(findings, path + ".recorded_at_not_monotonic")
        if recorded_at is not None:
            prior_recorded = recorded_at
        refs = evidence_refs(
            event, path,
            required=event_type != "DECISION_RECORDED" or event.get("status") != "PLANNED",
        )
        if recorded_at is not None:
            for ref in refs:
                available = source_available.get(ref)
                if available is None or available > recorded_at:
                    _add(findings, path + ".evidence_not_available_when_recorded:" + ref)
        if event_type == "DECISION_RECORDED":
            if decision_id in event_status:
                _add(findings, path + ".decision_already_recorded")
            if event.get("status") not in DECISION_STATUSES:
                _add(findings, path + ".status_invalid")
            event_status[str(decision_id)] = str(event.get("status") or "")
        elif decision_id not in event_status:
            _add(findings, path + ".decision_not_recorded")
        elif event_type == "STATUS_CHANGED":
            if event.get("from_status") != event_status.get(str(decision_id)):
                _add(findings, path + ".from_status_not_current")
            if event.get("to_status") not in DECISION_STATUS_TRANSITIONS.get(
                event.get("from_status"), set()
            ):
                _add(findings, path + ".status_transition_invalid")
            if not _text(event.get("rationale")):
                _add(findings, path + ".rationale_missing")
            event_status[str(decision_id)] = str(event.get("to_status") or "")
    if events_present:
        try:
            rebuilt = _decision_snapshots({"events": events}, through=cutoff)
        except (KeyError, TypeError):
            rebuilt = {}
            _add(findings, prefix + ".management_decision_ledger_ref.events_unreadable")
        actual = {item.get("decision_id"): item for item in decisions}
        if rebuilt != actual:
            _add(findings, prefix + ".management_decision_ledger_ref.snapshot_event_mismatch")

    changes_present = "state_changes" in enterprise
    changes_value = enterprise.get("state_changes")
    if changes_present and not isinstance(changes_value, list):
        _add(findings, prefix + ".enterprise_system_ref.state_changes_invalid")
    changes = [_mapping(item) for item in _items(changes_value)]
    _unique_ids(changes, "change_id", prefix + ".enterprise_system_ref.state_changes", findings)
    for index, change in enumerate(changes):
        path = f"{prefix}.enterprise_system_ref.state_changes[{index}]"
        if states_present and (
            change.get("from_state_id") not in state_ids
            or change.get("to_state_id") not in state_ids
        ):
            _add(findings, path + ".state_unknown")
        if states_present and all(
            item in state_by_id for item in (change.get("from_state_id"), change.get("to_state_id"))
        ) and state_by_id[change["from_state_id"]].get("responsibility_unit_id") != state_by_id[change["to_state_id"]].get("responsibility_unit_id"):
            _add(findings, path + ".state_unit_mismatch")
        if states_present and all(
            item in state_by_id for item in (change.get("from_state_id"), change.get("to_state_id"))
        ):
            from_at = _instant(state_by_id[change["from_state_id"]].get("observed_at"))
            to_at = _instant(state_by_id[change["to_state_id"]].get("observed_at"))
            if from_at is None or to_at is None or from_at >= to_at:
                _add(findings, path + ".state_time_order_invalid")
        mechanism_refs = change.get("mechanism_ids")
        if not isinstance(mechanism_refs, list) or not mechanism_refs or any(
            item not in mechanism_by_id for item in mechanism_refs
        ):
            _add(findings, path + ".mechanism_ids_invalid")
        decision_refs = change.get("management_decision_ids")
        if not isinstance(decision_refs, list) or any(item not in decision_ids for item in decision_refs):
            _add(findings, path + ".management_decision_ids_invalid")
        evidence_refs(change, path)


def validate_cjo_candidate(candidate: Any) -> dict[str, Any]:
    value = _mapping(candidate)
    findings: list[str] = []
    _reject_extra_fields(
        value,
        {
            "schema_version", "object_class", "candidate_id", "company_id", "cutoff_at",
            "method_version", "compiled_at", "judgment_owner_id", "state", "resolution",
            "central_path", "forward_judgments", "key_operating_drivers",
            "normal_earnings_transmission", "owner_cash_transmission", "permanent_loss_paths",
            "strongest_counterargument", "unknowns", "monitoring_contract", "traceability",
            "source_package", "enterprise_system_ref", "management_decision_ledger_ref",
            "underwriting_thesis_projection", "authority",
        },
        "cjo_candidate",
        findings,
    )
    if value.get("schema_version") != CJO_CANDIDATE_VERSION or value.get("object_class") != "COMPANY_JUDGMENT_OBJECT_CANDIDATE":
        _add(findings, "cjo_candidate.identity_invalid")
    for field in (
        "candidate_id", "company_id", "cutoff_at", "method_version", "compiled_at", "judgment_owner_id",
    ):
        if not _text(value.get(field)):
            _add(findings, f"cjo_candidate.{field}_missing")
    if _instant(value.get("cutoff_at")) is None or _instant(value.get("compiled_at")) is None:
        _add(findings, "cjo_candidate.timestamp_invalid")
    if value.get("state") != "REVIEW_READY" or value.get("resolution") not in RESOLUTIONS:
        _add(findings, "cjo_candidate.state_or_resolution_invalid")
    if value.get("resolution") in {"NO_PRIMARY", "UNKNOWN"} and value.get("central_path"):
        _add(findings, "cjo_candidate.abstention_cannot_have_central_path")
    if value.get("resolution") in {"PRIMARY", "MIXED"} and not _mapping(value.get("central_path")):
        _add(findings, "cjo_candidate.directional_or_mixed_requires_central_path")
    _validate_underwriting_thesis_projection(
        value.get("underwriting_thesis_projection"),
        cjo=value,
        prefix="cjo_candidate",
        findings=findings,
    )
    traces = [_mapping(item) for item in _items(value.get("traceability"))]
    trace_ids = _unique_ids(traces, "trace_id", "cjo_candidate.traceability", findings)
    _validate_forward_judgments(
        [_mapping(item) for item in _items(value.get("forward_judgments"))],
        trace_ids, findings, prefix="cjo_candidate",
    )
    source_validation = validate_source_package(value.get("source_package"))
    findings.extend("cjo_candidate.source_package:" + item for item in source_validation["findings"])
    _validate_cjo_reader_projection(
        value, prefix="cjo_candidate", source_validation=source_validation,
        findings=findings,
    )
    if _mapping(value.get("source_package")).get("company_id") != value.get("company_id"):
        _add(findings, "cjo_candidate.source_package_company_id_mismatch")
    if _mapping(value.get("source_package")).get("cutoff_at") != value.get("cutoff_at"):
        _add(findings, "cjo_candidate.source_package_cutoff_mismatch")
    if _mapping(value.get("source_package")).get("method_version") != value.get("method_version"):
        _add(findings, "cjo_candidate.source_package_method_version_mismatch")
    enterprise_ref = _mapping(value.get("enterprise_system_ref"))
    unit_ids = {
        item.get("unit_id") for item in map(_mapping, _items(enterprise_ref.get("responsibility_units")))
        if _text(item.get("unit_id"))
    }
    mechanism_ids = {
        item.get("mechanism_id") for item in map(_mapping, _items(enterprise_ref.get("mechanisms")))
        if _text(item.get("mechanism_id"))
    }
    transmission_by_id = {
        item.get("transmission_id"): item
        for item in map(_mapping, _items(enterprise_ref.get("financial_transmissions")))
        if _text(item.get("transmission_id"))
    }
    trace_by_id = {item.get("trace_id"): item for item in traces if _text(item.get("trace_id"))}
    for index, trace in enumerate(traces):
        if trace.get("source_ref") not in source_validation["source_refs"]:
            _add(findings, f"cjo_candidate.traceability[{index}].source_ref_unknown")
        if trace.get("responsibility_unit_id") not in unit_ids:
            _add(findings, f"cjo_candidate.traceability[{index}].responsibility_unit_unknown")
        if trace.get("mechanism_id") not in mechanism_ids or trace.get("reasoning_kind") not in REASONING_KINDS:
            _add(findings, f"cjo_candidate.traceability[{index}].mechanism_or_reasoning_kind_invalid")
        transmission_ids = trace.get("financial_transmission_ids")
        if not isinstance(transmission_ids, list) or not transmission_ids or any(
            item not in transmission_by_id for item in transmission_ids
        ):
            _add(findings, f"cjo_candidate.traceability[{index}].financial_transmission_ids_invalid")
        elif any(
            transmission_by_id[item].get("mechanism_id") != trace.get("mechanism_id")
            for item in transmission_ids
        ):
            _add(findings, f"cjo_candidate.traceability[{index}].financial_transmission_mechanism_mismatch")
    central_trace_ids = _items(_mapping(value.get("central_path")).get("trace_ids"))
    if value.get("resolution") in {"PRIMARY", "MIXED"} and (
        not central_trace_ids or any(item not in trace_ids for item in central_trace_ids)
    ):
        _add(findings, "cjo_candidate.central_path_trace_ids_invalid")
    if any(
        source_validation["source_eligibility"].get(trace_by_id[item].get("source_ref")) != "ELIGIBLE"
        for item in central_trace_ids if item in trace_by_id
    ):
        _add(findings, "cjo_candidate.central_path_uses_ineligible_evidence")
    counter_trace_ids = _items(_mapping(value.get("strongest_counterargument")).get("trace_ids"))
    if not counter_trace_ids or any(item not in trace_ids for item in counter_trace_ids):
        _add(findings, "cjo_candidate.strongest_counterargument_trace_ids_invalid")
    for index, judgment in enumerate(map(_mapping, _items(value.get("forward_judgments")))):
        judgment_traces = [trace_by_id[item] for item in judgment.get("trace_ids", []) if item in trace_by_id]
        if any(
            source_validation["source_eligibility"].get(trace.get("source_ref")) == "EVIDENCE_INELIGIBLE"
            for trace in judgment_traces
        ) and judgment.get("evidence_state") != "EVIDENCE_INELIGIBLE":
            _add(findings, f"cjo_candidate.forward_judgments[{index}].ineligible_source_not_preserved")
    for field, layer in (
        ("normal_earnings_transmission", "NORMAL_EARNINGS"),
        ("owner_cash_transmission", "OWNER_CASH"),
    ):
        summary = _mapping(value.get(field))
        ids = summary.get("transmission_ids")
        if summary.get("direction") not in DIRECTIONS or not isinstance(ids, list) or any(
            item not in transmission_by_id or transmission_by_id[item].get("layer") != layer for item in ids
        ):
            _add(findings, "cjo_candidate." + field + "_invalid")
    authority = _mapping(value.get("authority"))
    expected_authority = {
        "canonical": False,
        "freeze_allowed": False,
        "report_read_allowed": False,
        "quantitative_read_allowed": False,
        "investment_authorization": False,
    }
    if authority != expected_authority:
        _add(findings, "cjo_candidate.authority_must_be_candidate_only")
    for required in (
        "key_operating_drivers", "normal_earnings_transmission", "owner_cash_transmission",
        "strongest_counterargument", "unknowns", "monitoring_contract", "enterprise_system_ref",
        "management_decision_ledger_ref",
    ):
        if required not in value:
            _add(findings, "cjo_candidate." + required + "_missing")
    for path in _forbidden_paths(value):
        _add(findings, "cjo_candidate.forbidden_price_valuation_training_or_outcome_field:" + path)
    return _validation(findings)


def validate_independent_review(review: Any, *, candidate: Any) -> dict[str, Any]:
    value = _mapping(review)
    candidate_value = _mapping(candidate)
    findings: list[str] = []
    _reject_extra_fields(
        value,
        {
            "schema_version", "review_id", "candidate_id", "company_id", "cutoff_at",
            "method_version", "reviewer_id", "reviewed_at", "decision", "material_findings",
            "accepted_criteria",
        },
        "cjo_review",
        findings,
    )
    if value.get("schema_version") != CJO_REVIEW_VERSION:
        _add(findings, "cjo_review.schema_version_invalid")
    for field in ("review_id", "candidate_id", "reviewer_id", "reviewed_at"):
        if not _text(value.get(field)):
            _add(findings, "cjo_review." + field + "_missing")
    if value.get("candidate_id") != candidate_value.get("candidate_id"):
        _add(findings, "cjo_review.candidate_id_mismatch")
    if value.get("reviewer_id") == candidate_value.get("judgment_owner_id"):
        _add(findings, "cjo_review.author_cannot_self_sign")
    if _instant(value.get("reviewed_at")) is None:
        _add(findings, "cjo_review.reviewed_at_invalid")
    if value.get("decision") != "ACCEPTED":
        _add(findings, "cjo_review.decision_not_accepted")
    if value.get("material_findings") not in ([], None):
        _add(findings, "cjo_review.material_findings_open")
    criteria = value.get("accepted_criteria")
    required_criteria = {
        "TRACEABILITY", "UNKNOWN_PRESERVATION", "COUNTERARGUMENT",
        "FINANCIAL_TRANSMISSION", "PIT_CUTOFF", "AUTHORITY_BOUNDARY",
    }
    if not isinstance(criteria, list) or not required_criteria <= set(criteria):
        _add(findings, "cjo_review.accepted_criteria_incomplete")
    for field in ("company_id", "cutoff_at", "method_version"):
        if value.get(field) != candidate_value.get(field):
            _add(findings, "cjo_review.identity_mismatch:" + field)
    for path in _forbidden_paths(value):
        _add(findings, "cjo_review.forbidden_price_valuation_training_or_outcome_field:" + path)
    return _validation(findings)


def freeze_cjo(*, candidate: Any, independent_review: Any) -> dict[str, Any]:
    """Freeze one candidate after an independent accepted review."""
    candidate_value = deepcopy(_mapping(candidate))
    candidate_validation = validate_cjo_candidate(candidate_value)
    review_validation = validate_independent_review(independent_review, candidate=candidate_value)
    findings = ["candidate:" + item for item in candidate_validation["findings"]]
    findings.extend("review:" + item for item in review_validation["findings"])
    if findings:
        raise EnterpriseJudgmentCoreError("cjo_freeze_rejected:" + ",".join(findings))
    review = deepcopy(_mapping(independent_review))
    frozen = deepcopy(candidate_value)
    frozen["schema_version"] = FROZEN_CJO_VERSION
    frozen["object_class"] = "FROZEN_COMPANY_JUDGMENT_OBJECT"
    frozen["cjo_id"] = "CJO:FROZEN:" + candidate_value["candidate_id"]
    frozen.pop("candidate_id", None)
    frozen["state"] = "FROZEN"
    frozen["frozen_at"] = review["reviewed_at"]
    frozen["independent_review_receipt"] = {
        key: deepcopy(review[key]) for key in (
            "review_id", "candidate_id", "company_id", "cutoff_at", "method_version",
            "reviewer_id", "reviewed_at", "decision", "accepted_criteria",
        )
    }
    # Direct reviewed values, not a digest: later validation can prove that a
    # reader-facing field was not rewritten after the independent acceptance.
    frozen["independent_review_receipt"]["reviewed_reader_projection"] = {
        "enterprise_system_ref": deepcopy(frozen["enterprise_system_ref"]),
        "management_decision_ledger_ref": deepcopy(
            frozen["management_decision_ledger_ref"]
        ),
    }
    if "underwriting_thesis_projection" in frozen:
        frozen["independent_review_receipt"]["reviewed_reader_projection"][
            "underwriting_thesis_projection"
        ] = deepcopy(frozen["underwriting_thesis_projection"])
    frozen["authority"] = {
        "canonical": True,
        "append_only_predecessors": True,
        "report_read_allowed": True,
        "quantitative_read_allowed": True,
        "training_write_allowed": False,
        "price_write_allowed": False,
        "valuation_write_allowed": False,
        "investment_authorization": False,
    }
    validation = validate_frozen_cjo(frozen)
    if validation["state"] != "VALID":
        raise EnterpriseJudgmentCoreError("frozen_cjo_invalid:" + ",".join(validation["findings"]))
    return frozen


def validate_frozen_cjo(cjo: Any) -> dict[str, Any]:
    value = _mapping(cjo)
    findings: list[str] = []
    _reject_extra_fields(
        value,
        {
            "schema_version", "object_class", "cjo_id", "company_id", "cutoff_at",
            "method_version", "compiled_at", "judgment_owner_id", "state", "frozen_at",
            "resolution", "central_path", "forward_judgments", "key_operating_drivers",
            "normal_earnings_transmission", "owner_cash_transmission", "permanent_loss_paths",
            "strongest_counterargument", "unknowns", "monitoring_contract", "traceability",
            "source_package", "enterprise_system_ref", "management_decision_ledger_ref",
            "underwriting_thesis_projection", "independent_review_receipt", "authority",
        },
        "frozen_cjo",
        findings,
    )
    if value.get("schema_version") != FROZEN_CJO_VERSION or value.get("object_class") != "FROZEN_COMPANY_JUDGMENT_OBJECT":
        _add(findings, "frozen_cjo.identity_invalid")
    for field in (
        "cjo_id", "company_id", "cutoff_at", "method_version", "compiled_at", "judgment_owner_id", "frozen_at",
    ):
        if not _text(value.get(field)):
            _add(findings, "frozen_cjo." + field + "_missing")
    if _instant(value.get("cutoff_at")) is None or _instant(value.get("compiled_at")) is None or _instant(value.get("frozen_at")) is None:
        _add(findings, "frozen_cjo.timestamp_invalid")
    if value.get("state") != "FROZEN" or value.get("resolution") not in RESOLUTIONS:
        _add(findings, "frozen_cjo.state_or_resolution_invalid")
    if value.get("resolution") in {"NO_PRIMARY", "UNKNOWN"} and value.get("central_path"):
        _add(findings, "frozen_cjo.abstention_cannot_have_central_path")
    if value.get("resolution") in {"PRIMARY", "MIXED"} and not _mapping(value.get("central_path")):
        _add(findings, "frozen_cjo.directional_or_mixed_requires_central_path")
    _validate_underwriting_thesis_projection(
        value.get("underwriting_thesis_projection"),
        cjo=value,
        prefix="frozen_cjo",
        findings=findings,
    )
    traces = [_mapping(item) for item in _items(value.get("traceability"))]
    trace_ids = _unique_ids(traces, "trace_id", "frozen_cjo.traceability", findings)
    _validate_forward_judgments(
        [_mapping(item) for item in _items(value.get("forward_judgments"))],
        trace_ids, findings, prefix="frozen_cjo",
    )
    source_validation = validate_source_package(value.get("source_package"))
    findings.extend("frozen_cjo.source_package:" + item for item in source_validation["findings"])
    _validate_cjo_reader_projection(
        value, prefix="frozen_cjo", source_validation=source_validation,
        findings=findings,
    )
    if _mapping(value.get("source_package")).get("company_id") != value.get("company_id"):
        _add(findings, "frozen_cjo.source_package_company_id_mismatch")
    if _mapping(value.get("source_package")).get("cutoff_at") != value.get("cutoff_at"):
        _add(findings, "frozen_cjo.source_package_cutoff_mismatch")
    if _mapping(value.get("source_package")).get("method_version") != value.get("method_version"):
        _add(findings, "frozen_cjo.source_package_method_version_mismatch")
    enterprise_ref = _mapping(value.get("enterprise_system_ref"))
    unit_ids = {
        item.get("unit_id") for item in map(_mapping, _items(enterprise_ref.get("responsibility_units")))
        if _text(item.get("unit_id"))
    }
    mechanism_ids = {
        item.get("mechanism_id") for item in map(_mapping, _items(enterprise_ref.get("mechanisms")))
        if _text(item.get("mechanism_id"))
    }
    transmission_by_id = {
        item.get("transmission_id"): item
        for item in map(_mapping, _items(enterprise_ref.get("financial_transmissions")))
        if _text(item.get("transmission_id"))
    }
    trace_by_id = {item.get("trace_id"): item for item in traces if _text(item.get("trace_id"))}
    for index, trace in enumerate(traces):
        if trace.get("source_ref") not in source_validation["source_refs"]:
            _add(findings, f"frozen_cjo.traceability[{index}].source_ref_unknown")
        if trace.get("responsibility_unit_id") not in unit_ids:
            _add(findings, f"frozen_cjo.traceability[{index}].responsibility_unit_unknown")
        if trace.get("mechanism_id") not in mechanism_ids or trace.get("reasoning_kind") not in REASONING_KINDS:
            _add(findings, f"frozen_cjo.traceability[{index}].mechanism_or_reasoning_kind_invalid")
        transmission_ids = trace.get("financial_transmission_ids")
        if not isinstance(transmission_ids, list) or not transmission_ids or any(
            item not in transmission_by_id for item in transmission_ids
        ):
            _add(findings, f"frozen_cjo.traceability[{index}].financial_transmission_ids_invalid")
        elif any(
            transmission_by_id[item].get("mechanism_id") != trace.get("mechanism_id")
            for item in transmission_ids
        ):
            _add(findings, f"frozen_cjo.traceability[{index}].financial_transmission_mechanism_mismatch")
    central_trace_ids = _items(_mapping(value.get("central_path")).get("trace_ids"))
    if value.get("resolution") in {"PRIMARY", "MIXED"} and (
        not central_trace_ids or any(item not in trace_ids for item in central_trace_ids)
    ):
        _add(findings, "frozen_cjo.central_path_trace_ids_invalid")
    if any(
        source_validation["source_eligibility"].get(trace_by_id[item].get("source_ref")) != "ELIGIBLE"
        for item in central_trace_ids if item in trace_by_id
    ):
        _add(findings, "frozen_cjo.central_path_uses_ineligible_evidence")
    counter_trace_ids = _items(_mapping(value.get("strongest_counterargument")).get("trace_ids"))
    if not counter_trace_ids or any(item not in trace_ids for item in counter_trace_ids):
        _add(findings, "frozen_cjo.strongest_counterargument_trace_ids_invalid")
    for index, judgment in enumerate(map(_mapping, _items(value.get("forward_judgments")))):
        judgment_traces = [trace_by_id[item] for item in judgment.get("trace_ids", []) if item in trace_by_id]
        if any(
            source_validation["source_eligibility"].get(trace.get("source_ref")) == "EVIDENCE_INELIGIBLE"
            for trace in judgment_traces
        ) and judgment.get("evidence_state") != "EVIDENCE_INELIGIBLE":
            _add(findings, f"frozen_cjo.forward_judgments[{index}].ineligible_source_not_preserved")
    for field, layer in (
        ("normal_earnings_transmission", "NORMAL_EARNINGS"),
        ("owner_cash_transmission", "OWNER_CASH"),
    ):
        summary = _mapping(value.get(field))
        ids = summary.get("transmission_ids")
        if summary.get("direction") not in DIRECTIONS or not isinstance(ids, list) or any(
            item not in transmission_by_id or transmission_by_id[item].get("layer") != layer for item in ids
        ):
            _add(findings, "frozen_cjo." + field + "_invalid")
    receipt = _mapping(value.get("independent_review_receipt"))
    if receipt.get("decision") != "ACCEPTED" or receipt.get("reviewer_id") == value.get("judgment_owner_id"):
        _add(findings, "frozen_cjo.independent_review_receipt_invalid")
    for field in ("review_id", "candidate_id", "reviewer_id", "reviewed_at"):
        if not _text(receipt.get(field)):
            _add(findings, "frozen_cjo.independent_review_receipt_missing:" + field)
    for field in ("company_id", "cutoff_at", "method_version"):
        if receipt.get(field) != value.get(field):
            _add(findings, "frozen_cjo.independent_review_receipt_identity_mismatch:" + field)
    if receipt.get("reviewed_at") != value.get("frozen_at"):
        _add(findings, "frozen_cjo.reviewed_at_frozen_at_mismatch")
    reviewed_projection = receipt.get("reviewed_reader_projection")
    enterprise_projection = _mapping(value.get("enterprise_system_ref"))
    decision_projection = _mapping(value.get("management_decision_ledger_ref"))
    has_new_reader_projection = any(
        field in enterprise_projection
        for field in ("arenas", "operating_variables", "operating_states", "state_changes")
    ) or "events" in decision_projection or "underwriting_thesis_projection" in value
    if has_new_reader_projection and reviewed_projection is None:
        _add(findings, "frozen_cjo.reviewed_reader_projection_missing_for_new_shape")
    elif reviewed_projection is not None:
        reviewed_projection = _mapping(reviewed_projection)
        expected_projection = {
            "enterprise_system_ref": value.get("enterprise_system_ref"),
            "management_decision_ledger_ref": value.get("management_decision_ledger_ref"),
        }
        if "underwriting_thesis_projection" in value:
            expected_projection["underwriting_thesis_projection"] = value.get(
                "underwriting_thesis_projection"
            )
        if reviewed_projection != expected_projection:
            _add(findings, "frozen_cjo.reviewed_reader_projection_mutated")
    required_criteria = {
        "TRACEABILITY", "UNKNOWN_PRESERVATION", "COUNTERARGUMENT",
        "FINANCIAL_TRANSMISSION", "PIT_CUTOFF", "AUTHORITY_BOUNDARY",
    }
    if not isinstance(receipt.get("accepted_criteria"), list) or not required_criteria <= set(receipt["accepted_criteria"]):
        _add(findings, "frozen_cjo.independent_review_criteria_incomplete")
    authority = _mapping(value.get("authority"))
    required_authority = {
        "canonical": True,
        "append_only_predecessors": True,
        "report_read_allowed": True,
        "quantitative_read_allowed": True,
        "training_write_allowed": False,
        "price_write_allowed": False,
        "valuation_write_allowed": False,
        "investment_authorization": False,
    }
    if authority != required_authority:
        _add(findings, "frozen_cjo.authority_invalid")
    for path in _forbidden_paths(value):
        _add(findings, "frozen_cjo.forbidden_price_valuation_training_or_outcome_field:" + path)
    return _validation(findings)


def compile_candidate_amendment(
    *,
    frozen_cjo: Any,
    amendment_id: str,
    origin: str,
    proposed_at: str,
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a candidate-only training/forecast note without mutating the CJO."""
    cjo = _mapping(frozen_cjo)
    validation = validate_frozen_cjo(cjo)
    if validation["state"] != "VALID":
        raise EnterpriseJudgmentCoreError("candidate_amendment_requires_frozen_cjo")
    if not _text(amendment_id) or origin not in AMENDMENT_ORIGINS or _instant(proposed_at) is None:
        raise EnterpriseJudgmentCoreError("candidate_amendment_identity_invalid")
    if not isinstance(proposals, list) or not proposals:
        raise EnterpriseJudgmentCoreError("candidate_amendment_proposals_missing")
    for index, proposal in enumerate(proposals):
        if not _text(_mapping(proposal).get("target")) or not _text(_mapping(proposal).get("rationale")):
            raise EnterpriseJudgmentCoreError(f"candidate_amendment.proposals[{index}]_invalid")
    for path in _forbidden_paths(proposals):
        raise EnterpriseJudgmentCoreError("candidate_amendment_forbidden_price_or_valuation_field:" + path)
    return {
        "schema_version": CANDIDATE_AMENDMENT_VERSION,
        "object_class": "CJO_CANDIDATE_AMENDMENT",
        "amendment_id": amendment_id,
        "origin": origin,
        "proposed_at": proposed_at,
        "base_cjo_ref": {
            "cjo_id": cjo["cjo_id"],
            "company_id": cjo["company_id"],
            "cutoff_at": cjo["cutoff_at"],
            "method_version": cjo["method_version"],
        },
        "proposals": deepcopy(proposals),
        "status": "CANDIDATE_ONLY",
        "authority": {
            "may_modify_frozen_cjo": False,
            "requires_new_enterprise_model_or_ledger_event": True,
            "requires_new_independent_review": True,
            "investment_authorization": False,
        },
    }


def project_frozen_cjo_to_judgment_synthesis(cjo: Any) -> dict[str, Any]:
    """Project a Frozen CJO into the existing read-only JUDGMENT_SYNTHESIS shape."""
    value = _mapping(cjo)
    validation = validate_frozen_cjo(value)
    if validation["state"] != "VALID":
        raise EnterpriseJudgmentCoreError("judgment_synthesis_requires_frozen_cjo:" + ",".join(validation["findings"]))
    claims: list[dict[str, Any]] = []
    if value.get("central_path"):
        claims.append({
            "claim_id": "CENTRAL_PATH",
            "claim": value["central_path"].get("claim"),
            "trace_ids": deepcopy(value["central_path"].get("trace_ids", [])),
            "resolution": value["resolution"],
        })
    claims.extend({
        "claim_id": item["judgment_id"],
        "claim": item["claim"],
        "trace_ids": deepcopy(item["trace_ids"]),
        "status": item["status"],
        "evidence_state": item["evidence_state"],
    } for item in value["forward_judgments"])
    allocation_events = [
        deepcopy(item) for item in value["management_decision_ledger_ref"]["decisions"]
        if any("capital" in str(signal).lower() for signal in item.get("observable_signal_ids", []))
    ]
    projection = {
        "ledger_states": {
            "frozen_cjo": "FROZEN",
            "enterprise_system_model": "SNAPSHOT_READ_ONLY",
            "management_decision_ledger": "APPEND_ONLY_AS_OF_SNAPSHOT",
        },
        "claims": claims,
        "financial_drivers": deepcopy(value["key_operating_drivers"]),
        "allocation_events": allocation_events,
        "thesis": {
            "resolution": value["resolution"],
            "central_path": deepcopy(value["central_path"]),
            "forward_judgments": deepcopy(value["forward_judgments"]),
            "normal_earnings_transmission": deepcopy(value["normal_earnings_transmission"]),
            "owner_cash_transmission": deepcopy(value["owner_cash_transmission"]),
            "permanent_loss_paths": deepcopy(value["permanent_loss_paths"]),
            "strongest_counterargument": deepcopy(value["strongest_counterargument"]),
            "unknowns": deepcopy(value["unknowns"]),
            "monitoring_contract": deepcopy(value["monitoring_contract"]),
        },
        "insights": [],
        "adversarial_review": {
            "strongest_counterargument": deepcopy(value["strongest_counterargument"]),
            "independent_review_receipt": deepcopy(value["independent_review_receipt"]),
        },
        "frozen_cjo": deepcopy(value),
    }
    if "underwriting_thesis_projection" in value:
        projection["underwriting_thesis_projection"] = deepcopy(
            value["underwriting_thesis_projection"]
        )
    return projection


def build_report_handoff(cjo: Any) -> dict[str, Any]:
    """Return a report-readable snapshot with no publication or investment authority."""
    value = _mapping(cjo)
    projection = project_frozen_cjo_to_judgment_synthesis(value)
    return {
        "schema_version": REPORT_HANDOFF_VERSION,
        "object_class": "FROZEN_CJO_REPORT_HANDOFF",
        "cjo_ref": {
            "cjo_id": value["cjo_id"],
            "company_id": value["company_id"],
            "cutoff_at": value["cutoff_at"],
            "method_version": value["method_version"],
        },
        "projection": projection,
        "authority": {
            "read_only": True,
            "report_use": "REPORT_USE_NOT_RELEASED",
            "may_create_second_judgment_source": False,
            "publication_authorization": False,
            "investment_authorization": False,
        },
    }
