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
    events = [_mapping(item) for item in _items(value.get("events"))]
    if not events:
        _add(findings, "management_decision_ledger.events_missing")
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
    transmissions: list[dict[str, Any]],
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
    normal = _aggregate_direction(transmissions, "NORMAL_EARNINGS")
    cash = _aggregate_direction(transmissions, "OWNER_CASH")
    if requested == "MIXED" or normal == "MIXED" or cash == "MIXED":
        return "MIXED"
    if normal in {"IMPROVES", "DETERIORATES"} and cash != normal:
        return "MIXED"
    return "PRIMARY"


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


def compile_cjo_candidate(
    *,
    model: Any,
    ledger: Any,
    source_package: Any,
    judgment_input: Any,
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
        source_eligibility, central_transmissions,
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
    used_transmission_ids = {
        ref for item in used_traces for ref in item["financial_transmission_ids"]
    }
    used_source_refs = {item["source_ref"] for item in used_traces}
    used_unit_ids = {item["responsibility_unit_id"] for item in used_traces}
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
            "direction": _aggregate_direction(central_transmissions, "NORMAL_EARNINGS"),
            "transmission_ids": [
                item["transmission_id"] for item in central_transmissions
                if item["layer"] == "NORMAL_EARNINGS"
            ],
        },
        "owner_cash_transmission": {
            "direction": _aggregate_direction(central_transmissions, "OWNER_CASH"),
            "transmission_ids": [
                item["transmission_id"] for item in central_transmissions
                if item["layer"] == "OWNER_CASH"
            ],
        },
        "permanent_loss_paths": [
            deepcopy(item) for item in central_transmissions if item["layer"] == "PERMANENT_LOSS"
        ],
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
            "mechanisms": [
                deepcopy(item) for item in model_value["mechanisms"]
                if item["mechanism_id"] in used_mechanism_ids
            ],
            "financial_transmissions": [
                deepcopy(item) for item in model_value["financial_transmissions"]
                if item["transmission_id"] in used_transmission_ids
            ],
        },
        "management_decision_ledger_ref": {
            "ledger_id": ledger_value["ledger_id"],
            "event_count_at_cutoff": sum(
                1 for event in ledger_value["events"]
                if _instant(event["recorded_at"]) <= cutoff and _instant(event["effective_at"]) <= cutoff
            ),
            "decisions": [deepcopy(decision_snapshots[item]) for item in sorted(used_decision_ids)],
        },
        "authority": {
            "canonical": False,
            "freeze_allowed": False,
            "report_read_allowed": False,
            "quantitative_read_allowed": False,
            "investment_authorization": False,
        },
    }
    candidate_validation = validate_cjo_candidate(candidate)
    if candidate_validation["state"] != "VALID":
        raise EnterpriseJudgmentCoreError("compiled_cjo_candidate_invalid:" + ",".join(candidate_validation["findings"]))
    return candidate


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
            "source_package", "enterprise_system_ref", "management_decision_ledger_ref", "authority",
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
    traces = [_mapping(item) for item in _items(value.get("traceability"))]
    trace_ids = _unique_ids(traces, "trace_id", "cjo_candidate.traceability", findings)
    _validate_forward_judgments(
        [_mapping(item) for item in _items(value.get("forward_judgments"))],
        trace_ids, findings, prefix="cjo_candidate",
    )
    source_validation = validate_source_package(value.get("source_package"))
    findings.extend("cjo_candidate.source_package:" + item for item in source_validation["findings"])
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
            "independent_review_receipt", "authority",
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
    traces = [_mapping(item) for item in _items(value.get("traceability"))]
    trace_ids = _unique_ids(traces, "trace_id", "frozen_cjo.traceability", findings)
    _validate_forward_judgments(
        [_mapping(item) for item in _items(value.get("forward_judgments"))],
        trace_ids, findings, prefix="frozen_cjo",
    )
    source_validation = validate_source_package(value.get("source_package"))
    findings.extend("frozen_cjo.source_package:" + item for item in source_validation["findings"])
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
    return {
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
