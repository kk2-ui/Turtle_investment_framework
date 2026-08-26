#!/usr/bin/env python3
"""J3 request projection from compiled J2 threads into forecast semantics.

The adapter is deliberately pure and offline.  It selects explicitly eligible
thread cells, preserves their J0/source/measurement identities, and emits
requests for the existing forecast lane to answer later.  It does not produce
probabilities, intervals, scores, settlements, causal claims, or downstream
authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any

try:
    from scripts import enterprise_judgment_episode as episode
    from scripts import enterprise_judgment_mechanism as mechanism
    from scripts import judgment_pit_forecast as pit
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_episode as episode
    import enterprise_judgment_mechanism as mechanism
    import judgment_pit_forecast as pit


SOURCE_SCHEMA_VERSION = "enterprise-judgment-forecast-projection-source.v1"
SCHEMA_VERSION = "enterprise-judgment-forecast-projection.v1"
J2_SCHEMA_VERSION = "enterprise-judgment-mechanism-thread-set.v1"
ALLOWED_OUTPUTS = ["FORECAST_REQUESTS_ONLY", "RESEARCH_AGENDA"]

PROJECTION_STATES = {"FORECAST_REQUESTS_READY", "NO_FORECAST_ELIGIBLE_CELLS"}
REQUEST_KINDS = {
    "ORDINAL_PROBABILITY",
    "BINARY_PROBABILITY",
    "NUMERIC_INTERVAL",
    "ABSTAIN",
}
_FORECASTABLE_J2_CLAIM_TYPES = {
    "DESCRIPTIVE_STRUCTURE",
    "WITHIN_CASE_MECHANISM",
    "LIFECYCLE_TRANSITION",
}
_FORECAST_DIMENSIONS_BY_OUTCOME_DOMAIN = {
    "CUSTOMER": {"NORMAL_EARNINGS", "COMPETITIVE_POSITION"},
    "OPERATIONS": {"NORMAL_EARNINGS", "ROIC_OR_OPERATING_MARGIN"},
    "COMPETITION": {"COMPETITIVE_POSITION"},
    "CASH": {"CASH_CONVERSION_AND_CAPEX_BURDEN"},
    "CAPITAL_RETURN": {"ROIC_OR_OPERATING_MARGIN"},
    "LEVERAGE": {"LEVERAGE_AND_FINANCIAL_RESILIENCE"},
    "PERMANENT_LOSS": {"PERMANENT_LOSS_RISK"},
}

_SOURCE_ROOT_KEYS = {
    "schema_version",
    "projection_id",
    "episode_ref",
    "mechanism_thread_set_ref",
    "source_packet_refs",
    "threads",
    "object_class",
    "claim_class",
    "allowed_outputs",
}
_EPISODE_REF_KEYS = {"episode_id", "company_id", "issuer_id", "cutoff_at"}
_MECHANISM_THREAD_SET_REF_KEYS = {"thread_set_id", "schema_version"}
_SOURCE_PACKET_REF_KEYS = {"receipt_id", "receipt_version"}
_THREAD_KEYS = {"thread_id", "cells"}
_CELL_KEYS = {
    "request_id",
    "outcome_cell_id",
    "forecast_eligible",
    "forecast_dimension_id",
    "window_id",
    "request_kind",
    "measurement_ref",
    "evidence_refs",
    "baseline_reference",
    "event_statement",
    "interval_coverage",
    "interval_unit",
    "abstain_reason",
}
_MEASUREMENT_REF_KEYS = {
    "measurement_contract_id",
    "measurement_contract_version",
    "measurement_id",
}
_EVIDENCE_REF_KEYS = {"source_id", "published_at", "available_at", "field_ref", "field_id"}

_FORBIDDEN_KEYS = {
    "price",
    "market_price",
    "share_price",
    "stock_price",
    "entry_price",
    "return",
    "returns",
    "total_return",
    "market_return",
    "investment_return",
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
    "post_cutoff_evidence",
}

_RIGHTS = {
    "causal": "NOT_AUTHORIZED",
    "comparative": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "method_freeze": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}

_DIRECT_SCORES = [
    "CALIBRATION",
    "STATE_DEFINITION",
    "UNCERTAINTY_POLICY",
    "BASELINE_PERFORMANCE",
]
_DIRECT_FAILURE_LOCI = [
    "CALIBRATION",
    "STATE_DEFINITION",
    "UNCERTAINTY",
    "BASELINE_PERFORMANCE",
    "OUTCOME_MEASUREMENT",
]
_CANDIDATE_SCOPES = ["EVIDENCE_PRIORITY", "RIVAL_HYPOTHESIS_METHOD"]


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed_root(
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
    for field in sorted((required or allowed).difference(item)):
        _add(findings, f"{path}_missing_required_field:{field}")
    return item


def _closed_local(
    value: Any,
    allowed: set[str],
    path: str,
    reasons: list[str],
    *,
    required: set[str] | None = None,
) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(reasons, f"{path}_must_be_object")
        return item
    for field in sorted(set(item).difference(allowed)):
        _add(reasons, f"{path}_contains_unapproved_field:{field}")
    for field in sorted((required or allowed).difference(item)):
        _add(reasons, f"{path}_missing_required_field:{field}")
    return item


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


def _source_date(value: Any, path: str, reasons: list[str]) -> date | None:
    if not _text(value):
        _add(reasons, f"{path}_must_be_iso_date")
        return None
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        _add(reasons, f"{path}_must_be_iso_date")
        return None
    if parsed.isoformat() != value:
        _add(reasons, f"{path}_must_be_iso_date")
        return None
    return parsed


def _forbidden_paths(value: Any, path: str = "projection_source") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child_path = f"{path}.{key}"
            key_text = str(key).lower()
            if (
                key_text in _FORBIDDEN_KEYS
                or key_text.startswith("actual_")
                or key_text.startswith("settlement_")
                or key_text.endswith("_market_price")
                or key_text.endswith("_share_price")
                or key_text.endswith("_stock_price")
                or key_text.endswith("_return")
            ):
                paths.append(child_path)
            else:
                paths.extend(_forbidden_paths(nested, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _validate_episode_ref(
    value: Any,
    manifest: dict[str, Any],
    findings: list[str],
) -> dict[str, Any]:
    reference = _closed_root(value, _EPISODE_REF_KEYS, "projection_source.episode_ref", findings)
    for field in _EPISODE_REF_KEYS:
        if not _text(reference.get(field)):
            _add(findings, f"projection_source.episode_ref.{field}_required")
        elif reference.get(field) != manifest.get(field):
            _add(findings, f"projection_source.episode_ref.{field}_must_match_episode")
    _instant(reference.get("cutoff_at"), "projection_source.episode_ref.cutoff_at", findings)
    return reference


def _validate_source_packet_refs(
    value: Any,
    *,
    expected: Any,
    findings: list[str],
) -> list[dict[str, Any]]:
    references = _items(value)
    if not isinstance(value, list) or not references:
        _add(findings, "projection_source.source_packet_refs_nonempty_list_required")
        return []
    normalized: list[dict[str, Any]] = []
    identities: set[tuple[str, int]] = set()
    for index, raw in enumerate(references):
        reference = _closed_root(
            raw,
            _SOURCE_PACKET_REF_KEYS,
            f"projection_source.source_packet_refs[{index}]",
            findings,
        )
        receipt_id = reference.get("receipt_id")
        receipt_version = reference.get("receipt_version")
        if not _text(receipt_id):
            _add(findings, f"projection_source.source_packet_refs[{index}].receipt_id_required")
        if not isinstance(receipt_version, int) or isinstance(receipt_version, bool) or receipt_version < 1:
            _add(findings, f"projection_source.source_packet_refs[{index}].receipt_version_must_be_positive_integer")
        identity = (str(receipt_id), receipt_version if isinstance(receipt_version, int) else -1)
        if identity in identities:
            _add(findings, "projection_source.source_packet_refs_must_be_unique")
        identities.add(identity)
        normalized.append(reference)
    if normalized != _items(expected):
        _add(findings, "projection_source.source_packet_refs_must_match_j2_lineage")
    return normalized


def _validate_mechanism_thread_read_model(
    value: Any,
    *,
    manifest: dict[str, Any],
    source_ref: Any,
    findings: list[str],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Read the stable routing fields from the internally compiled J2 model."""
    reference = _closed_root(
        source_ref,
        _MECHANISM_THREAD_SET_REF_KEYS,
        "projection_source.mechanism_thread_set_ref",
        findings,
    )
    if not _text(reference.get("thread_set_id")):
        _add(findings, "projection_source.mechanism_thread_set_ref.thread_set_id_required")
    if reference.get("schema_version") != J2_SCHEMA_VERSION:
        _add(findings, "projection_source.mechanism_thread_set_ref.schema_version_invalid")

    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, "mechanism_thread_read_model_must_be_object")
        return reference, {}
    if item.get("schema_version") != J2_SCHEMA_VERSION:
        _add(findings, "mechanism_thread_read_model.schema_version_invalid")
    if item.get("thread_set_id") != reference.get("thread_set_id"):
        _add(findings, "mechanism_thread_read_model.thread_set_id_must_match_projection_source")
    for field in ("company_id", "issuer_id", "cutoff_at"):
        if item.get(field) != manifest.get(field):
            _add(findings, f"mechanism_thread_read_model.{field}_must_match_episode")
    if item.get("forecast_authorization") != "NOT_AUTHORIZED":
        _add(findings, "mechanism_thread_read_model.forecast_authorization_must_remain_not_authorized")

    raw_views = item.get("thread_views")
    if not isinstance(raw_views, list):
        _add(findings, "mechanism_thread_read_model.thread_views_must_be_list")
        return reference, {}
    views: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_views):
        view = _mapping(raw)
        if not isinstance(raw, dict):
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}]_must_be_object")
            continue
        thread_id = view.get("thread_id")
        if not _text(thread_id):
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].thread_id_required")
            continue
        if str(thread_id) in views:
            _add(findings, "mechanism_thread_read_model.thread_ids_must_be_unique")
            continue
        if not isinstance(view.get("j3_forecast_eligible"), bool):
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].j3_forecast_eligible_must_be_boolean")
        if view.get("resolution_status") not in {"RESOLVED", "BOUNDARY_ONLY"}:
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].resolution_status_invalid")
        if view.get("j3_forecast_eligible") is True and view.get("resolution_status") != "RESOLVED":
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].eligible_thread_must_be_resolved")
        if view.get("forecast_performed") is not False:
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].forecast_performed_must_be_false")
        for field in ("claim_type", "local_status", "evidence_ceiling"):
            if not _text(view.get(field)):
                _add(findings, f"mechanism_thread_read_model.thread_views[{index}].{field}_required")
        if not isinstance(view.get("claim_ids"), list) or not view.get("claim_ids"):
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].claim_ids_required")
        if not isinstance(view.get("outcome_cell_refs"), list) or not view.get("outcome_cell_refs"):
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].outcome_cell_refs_required")
        raw_sources = view.get("source_refs")
        if not isinstance(raw_sources, list) or not raw_sources:
            _add(findings, f"mechanism_thread_read_model.thread_views[{index}].source_refs_required")
        else:
            source_ids: set[str] = set()
            for source_index, raw_source in enumerate(raw_sources):
                source = _mapping(raw_source)
                source_id = source.get("source_ref")
                source_path = f"mechanism_thread_read_model.thread_views[{index}].source_refs[{source_index}]"
                if not _text(source_id):
                    _add(findings, source_path + ".source_ref_required")
                elif str(source_id) in source_ids:
                    _add(findings, source_path + ".source_ref_duplicate")
                else:
                    source_ids.add(str(source_id))
                _instant(source.get("available_at"), source_path + ".available_at", findings)
                if source.get("information_role") != "CUTOFF_VISIBLE":
                    _add(findings, source_path + ".information_role_must_be_cutoff_visible")
        views[str(thread_id)] = view
    return reference, views


def _validate_threads(value: Any, findings: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _add(findings, "projection_source.threads_must_be_list")
        return []
    threads: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        thread = _closed_root(raw, _THREAD_KEYS, f"projection_source.threads[{index}]", findings)
        thread_id = thread.get("thread_id")
        if not _text(thread_id):
            _add(findings, f"projection_source.threads[{index}].thread_id_required")
        elif str(thread_id) in seen:
            _add(findings, "projection_source.thread_ids_must_be_unique")
        else:
            seen.add(str(thread_id))
        if not isinstance(thread.get("cells"), list):
            _add(findings, f"projection_source.threads[{index}].cells_must_be_list")
        threads.append(thread)
    return threads


def _local_rejection(
    *,
    thread_id: Any,
    request_id: Any,
    outcome_cell_id: Any,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "thread_id": str(thread_id or "UNKNOWN_THREAD"),
        "request_id": str(request_id or "UNKNOWN_REQUEST"),
        "outcome_cell_id": str(outcome_cell_id or "UNKNOWN_CELL"),
        "reasons": list(dict.fromkeys(reasons)),
    }


def _validate_evidence_refs(
    value: Any,
    *,
    path: str,
    cutoff: datetime,
    j2_source_refs: dict[str, dict[str, Any]],
    reasons: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _add(reasons, f"{path}_nonempty_list_required")
        return []
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        reference = _closed_local(
            raw,
            _EVIDENCE_REF_KEYS,
            f"{path}[{index}]",
            reasons,
            required=_EVIDENCE_REF_KEYS - {"field_id"},
        )
        for field in ("source_id", "field_ref"):
            if not _text(reference.get(field)):
                _add(reasons, f"{path}[{index}].{field}_required")
        if "field_id" in reference and not _text(reference.get("field_id")):
            _add(reasons, f"{path}[{index}].field_id_must_be_nonempty_text")
        published = _source_date(reference.get("published_at"), f"{path}[{index}].published_at", reasons)
        if published is not None and published > cutoff.date():
            _add(reasons, f"{path}[{index}].post_cutoff_evidence_rejected")
        available = _instant(reference.get("available_at"), f"{path}[{index}].available_at", reasons)
        if available is not None and available > cutoff:
            _add(reasons, f"{path}[{index}].post_cutoff_evidence_rejected")
        source = j2_source_refs.get(str(reference.get("source_id")))
        if source is None:
            _add(reasons, f"{path}[{index}].source_id_not_bound_to_j2_thread")
        else:
            j2_available = _instant(source.get("available_at"), f"{path}[{index}].j2_source_available_at", reasons)
            if available is not None and j2_available is not None and available != j2_available:
                _add(reasons, f"{path}[{index}].available_at_must_match_j2_source")
        normalized.append(reference)
    return normalized


def _validate_measurement_ref(
    value: Any,
    *,
    path: str,
    episode_cell: dict[str, Any],
    reasons: list[str],
) -> dict[str, Any]:
    reference = _closed_local(value, _MEASUREMENT_REF_KEYS, path, reasons)
    for field in ("measurement_contract_id", "measurement_id"):
        if not _text(reference.get(field)):
            _add(reasons, f"{path}.{field}_required")
    version = reference.get("measurement_contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        _add(reasons, f"{path}.measurement_contract_version_must_be_positive_integer")
    if reference.get("measurement_contract_id") != episode_cell.get("measurement_contract_ref"):
        _add(reasons, f"{path}.measurement_contract_id_must_match_episode_cell")
    return reference


def _response_contract(cell: dict[str, Any], dimension_id: str) -> dict[str, Any]:
    kind = str(cell["request_kind"])
    if kind == "ORDINAL_PROBABILITY":
        labels = pit.RISK_LABELS if dimension_id == "PERMANENT_LOSS_RISK" else pit.NON_RISK_LABELS
        return {
            "request_kind": kind,
            "evidence_status": "MODEL_UNCERTAIN",
            "labels": list(labels),
            "probabilities_must_sum_to_one": True,
        }
    if kind == "BINARY_PROBABILITY":
        return {
            "request_kind": kind,
            "evidence_status": "MODEL_UNCERTAIN",
            "event_statement": cell["event_statement"],
        }
    if kind == "NUMERIC_INTERVAL":
        return {
            "request_kind": kind,
            "evidence_status": "MODEL_UNCERTAIN",
            "interval_coverage": float(cell["interval_coverage"]),
            "unit": cell["interval_unit"],
            "engine_adapter_state": "REQUEST_ONLY",
        }
    return {
        "request_kind": "ABSTAIN",
        "evidence_status": "EVIDENCE_INELIGIBLE",
        "reason": cell["abstain_reason"],
    }


def _coverage_permission(request_kind: str) -> dict[str, Any]:
    if request_kind == "ABSTAIN":
        statuses = ["EVIDENCE_INELIGIBLE"]
    else:
        statuses = sorted(pit.SETTLEMENT_STATUSES - {"EVIDENCE_INELIGIBLE"})
    return {
        "locality": "CELL_LOCAL",
        "settlement_statuses": statuses,
    }


def _error_attribution_permission(request_kind: str) -> dict[str, Any]:
    if request_kind == "ABSTAIN":
        return {
            "direct_learning_scopes": ["COVERAGE"],
            "candidate_learning_scopes": [],
            "failure_loci": ["COVERAGE", "OUTCOME_MEASUREMENT"],
            "candidate_disposition": "NONE",
            "activation_gate": "EXISTING_FORECAST_SETTLEMENT_REQUIRED",
            "causal_attribution": "NOT_AUTHORIZED",
        }
    return {
        "direct_learning_scopes": list(_DIRECT_SCORES),
        "candidate_learning_scopes": list(_CANDIDATE_SCOPES),
        "failure_loci": list(_DIRECT_FAILURE_LOCI) + list(_CANDIDATE_SCOPES),
        "candidate_disposition": "CANDIDATE_REQUIRES_PAIRED_HOLDOUT",
        "activation_gate": "EXISTING_FORECAST_SETTLEMENT_REQUIRED",
        "causal_attribution": "NOT_AUTHORIZED",
    }


def _validate_request_kind(cell: dict[str, Any], path: str, reasons: list[str]) -> None:
    kind = cell.get("request_kind")
    if kind not in REQUEST_KINDS:
        _add(reasons, f"{path}.request_kind_invalid")
        return
    if kind != "ABSTAIN" and not _text(cell.get("baseline_reference")):
        _add(reasons, f"{path}.baseline_reference_required")
    if kind == "ORDINAL_PROBABILITY":
        incompatible = {"event_statement", "interval_coverage", "interval_unit", "abstain_reason"}
    elif kind == "BINARY_PROBABILITY":
        incompatible = {"interval_coverage", "interval_unit", "abstain_reason"}
        if not _text(cell.get("event_statement")):
            _add(reasons, f"{path}.event_statement_required")
    elif kind == "NUMERIC_INTERVAL":
        incompatible = {"event_statement", "abstain_reason"}
        coverage = cell.get("interval_coverage")
        if (
            not isinstance(coverage, (int, float))
            or isinstance(coverage, bool)
            or not 0.0 < float(coverage) < 1.0
        ):
            _add(reasons, f"{path}.interval_coverage_must_be_between_zero_and_one")
        if not _text(cell.get("interval_unit")):
            _add(reasons, f"{path}.interval_unit_required")
    else:
        incompatible = {"event_statement", "interval_coverage", "interval_unit"}
        if not _text(cell.get("abstain_reason")):
            _add(reasons, f"{path}.abstain_reason_required")
    for field in sorted(incompatible.intersection(cell)):
        _add(reasons, f"{path}.{field}_not_allowed_for_{str(kind).lower()}")


def _project_cell(
    raw: Any,
    *,
    path: str,
    thread_id: str,
    episode_thread: dict[str, Any] | None,
    mechanism_thread_view: dict[str, Any] | None,
    episode_claim_rows: dict[str, dict[str, Any]],
    episode_cells: dict[str, dict[str, Any]],
    cutoff: datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    reasons: list[str] = []
    cell = _closed_local(
        raw,
        _CELL_KEYS,
        path,
        reasons,
        required={
            "request_id",
            "outcome_cell_id",
            "forecast_eligible",
            "forecast_dimension_id",
            "window_id",
            "request_kind",
            "measurement_ref",
            "evidence_refs",
        },
    )
    if cell.get("forecast_eligible") is not True:
        if not isinstance(cell.get("forecast_eligible"), bool):
            _add(reasons, f"{path}.forecast_eligible_must_be_boolean")
        if reasons:
            return None, _local_rejection(
                thread_id=thread_id,
                request_id=cell.get("request_id"),
                outcome_cell_id=cell.get("outcome_cell_id"),
                reasons=reasons,
            )
        return None, None

    for field in ("request_id", "outcome_cell_id"):
        if not _text(cell.get(field)):
            _add(reasons, f"{path}.{field}_required")
    dimension_id = cell.get("forecast_dimension_id")
    if dimension_id not in pit.FORECAST_DIMENSIONS:
        _add(reasons, f"{path}.forecast_dimension_id_invalid")
    if cell.get("window_id") not in pit.FORECAST_WINDOWS:
        _add(reasons, f"{path}.window_id_invalid")
    _validate_request_kind(cell, path, reasons)

    outcome_cell_id = str(cell.get("outcome_cell_id") or "")
    episode_cell = episode_cells.get(outcome_cell_id)
    if episode_thread is None:
        _add(reasons, f"{path}.thread_id_not_in_episode")
    elif outcome_cell_id not in _items(episode_thread.get("outcome_cell_ids")):
        _add(reasons, f"{path}.outcome_cell_id_not_bound_to_episode_thread")
    if mechanism_thread_view is None:
        _add(reasons, f"{path}.thread_id_not_in_mechanism_thread_read_model")
    elif mechanism_thread_view.get("j3_forecast_eligible") is not True:
        _add(reasons, f"{path}.j2_thread_not_forecast_eligible")
    else:
        expected_claim_ids = list(_items(_mapping(episode_thread).get("claim_ids")))
        expected_outcome_cells = list(_items(_mapping(episode_thread).get("outcome_cell_ids")))
        derived_eligible = bool(
            mechanism_thread_view.get("resolution_status") == "RESOLVED"
            and mechanism_thread_view.get("claim_type") in _FORECASTABLE_J2_CLAIM_TYPES
            and mechanism_thread_view.get("local_status") in {"OBSERVED", "INFERRED"}
            and mechanism_thread_view.get("evidence_ceiling") in {"TEACHING", "MECHANISM"}
            and mechanism_thread_view.get("claim_ids") == expected_claim_ids
            and mechanism_thread_view.get("outcome_cell_refs") == expected_outcome_cells
            and all(
                len(_items(episode_claim_rows.get(str(claim_id), {}).get("allowed_outputs"))) > 1
                for claim_id in expected_claim_ids
            )
        )
        if not derived_eligible:
            _add(reasons, f"{path}.j2_thread_eligibility_inconsistent")
    if episode_cell is None:
        _add(reasons, f"{path}.outcome_cell_id_not_in_episode")
        episode_cell = {}
    else:
        status = episode_cell.get("status")
        if status in {"OBSERVED", "MEASUREMENT_MISMATCH", "NOT_APPLICABLE"}:
            _add(reasons, f"{path}.episode_cell_not_open_for_forecast:{status}")
        if cell.get("request_kind") != "ABSTAIN" and status == "EVIDENCE_INELIGIBLE":
            _add(reasons, f"{path}.evidence_ineligible_cell_requires_abstain")
        allowed_dimensions = _FORECAST_DIMENSIONS_BY_OUTCOME_DOMAIN.get(
            str(episode_cell.get("dimension")), set()
        )
        if dimension_id not in allowed_dimensions:
            _add(reasons, f"{path}.forecast_dimension_incompatible_with_outcome_domain")

    measurement = _validate_measurement_ref(
        cell.get("measurement_ref"),
        path=f"{path}.measurement_ref",
        episode_cell=episode_cell,
        reasons=reasons,
    )
    evidence_refs = _validate_evidence_refs(
        cell.get("evidence_refs"),
        path=f"{path}.evidence_refs",
        cutoff=cutoff,
        j2_source_refs={
            str(_mapping(source).get("source_ref")): _mapping(source)
            for source in _items(_mapping(mechanism_thread_view).get("source_refs"))
        },
        reasons=reasons,
    )
    if reasons:
        return None, _local_rejection(
            thread_id=thread_id,
            request_id=cell.get("request_id"),
            outcome_cell_id=cell.get("outcome_cell_id"),
            reasons=reasons,
        )

    request_kind = str(cell["request_kind"])
    request = {
        "request_id": cell["request_id"],
        "thread_id": thread_id,
        "outcome_cell_id": cell["outcome_cell_id"],
        "forecast_dimension_id": dimension_id,
        "window_id": cell["window_id"],
        "measurement_ref": deepcopy(measurement),
        "evidence_refs": deepcopy(evidence_refs),
        "response_contract": _response_contract(cell, str(dimension_id)),
        "coverage_permission": _coverage_permission(request_kind),
        "error_attribution_permission": _error_attribution_permission(request_kind),
    }
    if request_kind != "ABSTAIN":
        request["baseline_reference"] = cell["baseline_reference"]
    return request, None


def _prepare(
    episode_manifest: Any,
    projection_source: Any,
    mechanism_thread_set: Any,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
    reconstruction_registry: Any | None,
) -> dict[str, Any]:
    findings: list[str] = []
    manifest = _mapping(episode_manifest)
    episode_validation = episode.validate_episode_manifest(episode_manifest)
    findings.extend(f"episode:{finding}" for finding in episode_validation["findings"])

    source = _closed_root(projection_source, _SOURCE_ROOT_KEYS, "projection_source", findings)
    if source.get("schema_version") != SOURCE_SCHEMA_VERSION:
        _add(findings, "projection_source.schema_version_invalid")
    if not _text(source.get("projection_id")):
        _add(findings, "projection_source.projection_id_required")
    if source.get("object_class") != "ENTERPRISE_JUDGMENT_FORECAST_PROJECTION_SOURCE":
        _add(findings, "projection_source.object_class_invalid")
    if source.get("claim_class") != "J2_FORECAST_ELIGIBILITY_ROUTING":
        _add(findings, "projection_source.claim_class_invalid")
    if source.get("allowed_outputs") != ALLOWED_OUTPUTS:
        _add(findings, "projection_source.allowed_outputs_must_remain_request_only")
    for path in _forbidden_paths(projection_source):
        _add(findings, "projection_source.forbidden_price_return_outcome_or_valuation_field:" + path)

    if reconstruction_registry is None:
        _add(findings, "projection_source.frozen_reconstruction_registry_required")
    j2_result = mechanism.compile_mechanism_thread_projection(
        mechanism_thread_set,
        episode_manifest=episode_manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=reconstruction_registry,
    )
    if not j2_result["valid"]:
        findings.extend("j2:" + str(finding) for finding in j2_result["findings"])
    mechanism_thread_read_model = j2_result.get("mechanism_thread_read_model")

    episode_ref = _validate_episode_ref(source.get("episode_ref"), manifest, findings)
    mechanism_thread_set_ref, mechanism_thread_views = _validate_mechanism_thread_read_model(
        mechanism_thread_read_model,
        manifest=manifest,
        source_ref=source.get("mechanism_thread_set_ref"),
        findings=findings,
    )
    source_packet_refs = _validate_source_packet_refs(
        source.get("source_packet_refs"),
        expected=_mapping(mechanism_thread_read_model).get("source_packet_refs"),
        findings=findings,
    )
    threads = _validate_threads(source.get("threads"), findings)
    cutoff = _instant(manifest.get("cutoff_at"), "episode.cutoff_at", findings)
    if findings or cutoff is None:
        return {
            "valid": False,
            "findings": findings,
            "projection_source": None,
            "forecast_requests": [],
            "cell_rejections": [],
        }

    episode_threads = {
        str(_mapping(raw).get("thread_id")): _mapping(raw)
        for raw in _items(manifest.get("mechanism_threads"))
    }
    episode_cells = {
        str(_mapping(raw).get("outcome_cell_id")): _mapping(raw)
        for raw in _items(manifest.get("outcome_cells"))
    }
    episode_projection = episode.compile_episode_read_model(manifest)
    episode_claim_rows = {
        str(_mapping(raw).get("claim_id")): _mapping(raw)
        for raw in _items(_mapping(episode_projection.get("episode_read_model")).get("claim_output_matrix"))
    }
    requests: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    seen_request_ids: set[str] = set()
    seen_cell_windows: set[tuple[str, str]] = set()
    for thread_index, thread in enumerate(threads):
        thread_id = str(thread.get("thread_id") or "")
        episode_thread = episode_threads.get(thread_id)
        mechanism_thread_view = mechanism_thread_views.get(thread_id)
        for cell_index, raw_cell in enumerate(_items(thread.get("cells"))):
            request, rejection = _project_cell(
                raw_cell,
                path=f"projection_source.threads[{thread_index}].cells[{cell_index}]",
                thread_id=thread_id,
                episode_thread=episode_thread,
                mechanism_thread_view=mechanism_thread_view,
                episode_claim_rows=episode_claim_rows,
                episode_cells=episode_cells,
                cutoff=cutoff,
            )
            if rejection is not None:
                rejections.append(rejection)
                continue
            if request is None:
                continue
            duplicate_reasons: list[str] = []
            request_id = str(request["request_id"])
            cell_window = (str(request["outcome_cell_id"]), str(request["window_id"]))
            if request_id in seen_request_ids:
                duplicate_reasons.append("forecast_request_id_duplicate")
            if cell_window in seen_cell_windows:
                duplicate_reasons.append("outcome_cell_window_duplicate")
            if duplicate_reasons:
                rejections.append(_local_rejection(
                    thread_id=thread_id,
                    request_id=request_id,
                    outcome_cell_id=request["outcome_cell_id"],
                    reasons=duplicate_reasons,
                ))
                continue
            seen_request_ids.add(request_id)
            seen_cell_windows.add(cell_window)
            requests.append(request)

    return {
        "valid": True,
        "findings": [],
        "projection_source": deepcopy(source),
        "episode_ref": deepcopy(episode_ref),
        "mechanism_thread_set_ref": deepcopy(mechanism_thread_set_ref),
        "source_packet_refs": deepcopy(source_packet_refs),
        "forecast_requests": requests,
        "cell_rejections": rejections,
    }


def validate_forecast_projection_source(
    episode_manifest: Any,
    projection_source: Any,
    *,
    mechanism_thread_set: Any,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
    reconstruction_registry: Any | None = None,
) -> dict[str, Any]:
    """Validate root lineage while retaining cell-local routing failures."""
    prepared = _prepare(
        episode_manifest,
        projection_source,
        mechanism_thread_set,
        reconstruction_read_model,
        reconstruction_inputs,
        reconstruction_registry,
    )
    return {
        "valid": prepared["valid"],
        "findings": prepared["findings"],
        "projection_source": prepared["projection_source"],
        "cell_rejections": prepared["cell_rejections"],
    }


def compile_forecast_projection(
    episode_manifest: Any,
    projection_source: Any,
    *,
    mechanism_thread_set: Any,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
    reconstruction_registry: Any | None = None,
) -> dict[str, Any]:
    """Compile request-only J3 output without running or freezing a forecast."""
    prepared = _prepare(
        episode_manifest,
        projection_source,
        mechanism_thread_set,
        reconstruction_read_model,
        reconstruction_inputs,
        reconstruction_registry,
    )
    if not prepared["valid"]:
        return {
            "valid": False,
            "findings": prepared["findings"],
            "forecast_projection": None,
        }
    requests = prepared["forecast_requests"]
    projection = {
        "schema_version": SCHEMA_VERSION,
        "projection_id": prepared["projection_source"]["projection_id"],
        "projection_state": "FORECAST_REQUESTS_READY" if requests else "NO_FORECAST_ELIGIBLE_CELLS",
        "episode_ref": prepared["episode_ref"],
        "mechanism_thread_set_ref": prepared["mechanism_thread_set_ref"],
        "decision_contract_ref": deepcopy(_mapping(episode_manifest).get("decision_contract_ref")),
        "source_packet_refs": prepared["source_packet_refs"],
        "forecast_requests": requests,
        "cell_rejections": prepared["cell_rejections"],
        "preserved_admission": {
            "E0_CONTEXT": "PRESERVED",
            "E1_RECONSTRUCTION": "PRESERVED",
        },
        "rights": deepcopy(_RIGHTS),
        "object_class": "ENTERPRISE_JUDGMENT_FORECAST_PROJECTION",
        "claim_class": "FORECAST_REQUEST_ROUTING",
        "allowed_outputs": list(ALLOWED_OUTPUTS),
    }
    return {
        "valid": True,
        "findings": [],
        "forecast_projection": projection,
    }
