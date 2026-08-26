#!/usr/bin/env python3
"""Project one explicitly requested mechanism thread to the existing V5 contract.

J4 is a read-only adapter.  It neither constructs a Comparative candidate nor
repairs one: the caller supplies an unchanged V5 pre-outcome bundle, and the
existing V5 validator remains the economic admission authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any

try:
    from scripts import enterprise_judgment_mechanism as mechanism
    from scripts import judgment_selection_v5 as v5
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_mechanism as mechanism
    import judgment_selection_v5 as v5


REQUEST_SCHEMA_VERSION = "enterprise-judgment-comparative-projection-request.v1"
SCHEMA_VERSION = "enterprise-judgment-comparative-projection.v1"
J2_SCHEMA_VERSION = "enterprise-judgment-mechanism-thread-set.v1"

NOT_REQUESTED = "NOT_REQUESTED"
NOT_ADMITTED = "NOT_ADMITTED"
ADMISSION_CANDIDATE = "ADMISSION_CANDIDATE"

RELATIVE_CAUSAL = "RELATIVE_CAUSAL"
E3_COMPARATIVE_LAB = "E3_COMPARATIVE_LAB"
ESTIMAND_CONTRAST = "TARGET_CHANGE_RELATIVE_TO_FROZEN_EXTERNAL_SHOCK_COMPARATOR_BASELINE"
CENSORING_RULE = "PRESERVE_MISSING_OR_BOUNDARY_WITHOUT_MEMBER_REPLACEMENT"

_ROOT_KEYS = {
    "schema_version", "episode_ref", "thread_ref", "target_trial_bindings", "v5_candidate",
}
_EPISODE_REF_KEYS = {"episode_id", "company_id", "issuer_id", "cutoff_at"}
_THREAD_REF_KEYS = {
    "thread_id", "claim_class", "requested_admission_level", "claim_ids",
    "hypothesis_ids", "responsibility_boundary", "outcome_cell_ids",
}
_HYPOTHESIS_ID_KEYS = {"h_a", "h_b"}
_RESPONSIBILITY_BOUNDARY_KEYS = {"responsibility_unit_id", "arena_id"}
_TARGET_TRIAL_KEYS = {
    "action_exposure", "eligibility_time_zero", "comparator_roles",
    "outcome_follow_up", "censoring_interference", "estimand",
}
_ACTION_EXPOSURE_KEYS = {
    "action_id", "focal_issuer_id", "exposure_start", "economic_carrier_ids", "scope_bridge_ids",
}
_ELIGIBILITY_TIME_ZERO_KEYS = {
    "cohort_snapshot_id", "eligibility_as_of", "time_zero", "decision_observable_at",
}
_COMPARATOR_ROLE_KEYS = {
    "counterfactual_panel_id", "external_shock_comparator_ids", "witness_ids", "falsifier_ids",
}
_OUTCOME_FOLLOW_UP_KEYS = {
    "metric_ids_by_clock", "economic_periods", "outcome_window_id",
    "minimum_decision_exposure_rule",
}
_CENSORING_INTERFERENCE_KEYS = {
    "censoring_rule", "non_replacement_rule", "member_assumptions",
}
_MEMBER_ASSUMPTION_KEYS = {"issuer_id", "parallel_action", "target_action_spillover"}
_ESTIMAND_KEYS = {
    "estimand_id", "target_issuer_id", "action_id", "comparator_role",
    "metric_ids_by_clock", "contrast", "outcome_window_id",
}
_J2_V5_BRIDGE_KEYS = {"hypothesis_bindings", "outcome_bindings", "source_lineage"}
_HYPOTHESIS_BINDING_KEYS = {
    "role", "j2_hypothesis_id", "j2_statement", "v5_hypothesis_id", "v5_mechanism",
}
_OUTCOME_BINDING_KEYS = {
    "outcome_cell_id", "measurement_contract_ref", "v5_measurement_contracts",
}
_SOURCE_LINEAGE_KEYS = {
    "j1_source_packet_refs", "j2_source_refs", "v5_source_provenance", "v5_sources",
}

_PRE_OUTCOME_FORBIDDEN_KEYS = {
    "price", "market_price", "share_price", "stock_price", "entry_price",
    "return", "returns", "security_return", "investment_return", "total_return",
    "benchmark_return", "actual_value", "observed_value", "outcome_value",
    "outcome_result", "settlement_value", "realized_value", "realized_return",
    "actual_source_id", "outcome_source_id", "post_cutoff_source_id",
}
_POST_CUTOFF_TIME_KEYS = {
    "available_at", "observed_at", "outcome_observed_at", "source_available_at", "filed_at",
    "reported_at",
}
_PRE_OUTCOME_LEAKAGE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:stock|share|market|entry)\s+price\b",
        r"\b(?:stock|shareholder|market|portfolio|security)\s+returns?\b",
        r"\btotal\s+shareholder\s+return\b",
        r"\bpost[- ]cutoff\b",
        r"\b(?:actual|realized|settled)\s+outcome\b",
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


def _ids(value: Any, path: str, findings: list[str]) -> list[str]:
    values = _items(value)
    if not values:
        _add(findings, path + "_required")
    result: list[str] = []
    for index, raw in enumerate(values):
        if not _text(raw):
            _add(findings, f"{path}[{index}]_must_be_nonempty_text")
        elif raw in result:
            _add(findings, f"{path}[{index}]_duplicate")
        else:
            result.append(raw)
    return result


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _same_instant(left: Any, right: Any) -> bool:
    left_time = _instant(left)
    right_time = _instant(right)
    return left_time is not None and right_time is not None and left_time == right_time


def _pre_outcome_forbidden_paths(value: Any, path: str = "projection_request") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).lower()
            child_path = f"{path}.{raw_key}"
            if key in _PRE_OUTCOME_FORBIDDEN_KEYS or key.startswith("post_cutoff"):
                paths.append(child_path)
            else:
                paths.extend(_pre_outcome_forbidden_paths(nested, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_pre_outcome_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _post_cutoff_data_paths(value: Any, cutoff: datetime | None, path: str = "projection_request") -> list[str]:
    if cutoff is None:
        return []
    paths: list[str] = []
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).lower()
            child_path = f"{path}.{raw_key}"
            if key in _POST_CUTOFF_TIME_KEYS:
                observed_at = _instant(nested)
                if observed_at is not None and observed_at > cutoff:
                    paths.append(child_path)
            else:
                paths.extend(_post_cutoff_data_paths(nested, cutoff, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_post_cutoff_data_paths(nested, cutoff, f"{path}[{index}]"))
    return paths


def _noncausal_reference_paths(value: Any, path: str = "projection_request") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).lower()
            child_path = f"{path}.{raw_key}"
            if "relative_reference" in key or "archetype" in key:
                paths.append(child_path)
            elif key == "causal_role" and str(nested).upper() in {"RELATIVE_REFERENCE", "ARCHETYPE"}:
                paths.append(child_path)
            else:
                paths.extend(_noncausal_reference_paths(nested, child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_noncausal_reference_paths(nested, f"{path}[{index}]"))
    return paths


def _pre_outcome_leakage_text_paths(value: Any, path: str) -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _PRE_OUTCOME_LEAKAGE_PATTERNS):
            paths.append(path)
    elif isinstance(value, dict):
        for key, nested in value.items():
            paths.extend(_pre_outcome_leakage_text_paths(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_pre_outcome_leakage_text_paths(nested, f"{path}[{index}]"))
    return paths


def _typed_reference_issuer(value: Any) -> bool:
    if not _text(value):
        return False
    upper = value.strip().upper()
    return upper.startswith(("ARCHETYPE:", "RELATIVE_REFERENCE:", "RELATIVE-REFERENCE:"))


def _projection_result(
    request: dict[str, Any],
    *,
    status: str,
    findings: list[str],
    v5_validation: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    episode_ref = _mapping(request.get("episode_ref"))
    thread_ref = _mapping(request.get("thread_ref"))
    validation = v5_validation or {
        "valid": False,
        "admission_status": "NOT_EVALUATED",
        "findings": [],
    }
    candidate_identity = _mapping(candidate)
    return {
        "schema_version": SCHEMA_VERSION,
        "object_class": "ENTERPRISE_JUDGMENT_COMPARATIVE_PROJECTION",
        "episode_ref": {
            field: episode_ref.get(field) for field in ("episode_id", "company_id", "issuer_id", "cutoff_at")
        },
        "thread_ref": {
            field: thread_ref.get(field)
            for field in ("thread_id", "claim_class", "requested_admission_level")
        },
        "projection_status": status,
        "comparative_candidate": deepcopy(candidate) if status == ADMISSION_CANDIDATE else None,
        "v5_validation": {
            "schema_version": candidate_identity.get("schema_version"),
            "method_epoch_id": candidate_identity.get("method_epoch_id"),
            "candidate_id": candidate_identity.get("candidate_id"),
            "valid": bool(validation.get("valid")),
            "admission_status": validation.get("admission_status", "NOT_EVALUATED"),
            "findings": list(validation.get("findings", [])),
        },
        "findings": list(findings),
        "locality": {
            "applies_only_to_thread_id": thread_ref.get("thread_id"),
            "e0_e2_unaffected": True,
            "other_threads_unaffected": True,
            "industry_block_unaffected": True,
        },
        "authority": {
            "pre_outcome_projection_only": True,
            "database_writes_authorized": False,
            "outcome_reads_authorized": False,
            "peer_recruitment_authorized": False,
            "h2_fabrication_authorized": False,
            "selection_seal_authorized": False,
            "method_freeze_authorized": False,
            "cjo_authorized": False,
            "report_authorized": False,
            "valuation_authorized": False,
            "investment_authorized": False,
        },
    }


def _validate_protocol_identity(request: dict[str, Any], findings: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    _closed(request, _ROOT_KEYS, "projection_request", findings, required={"schema_version", "episode_ref", "thread_ref"})
    if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
        _add(findings, "projection_request.schema_version_invalid")

    episode_ref = _closed(request.get("episode_ref"), _EPISODE_REF_KEYS, "projection_request.episode_ref", findings)
    for field in _EPISODE_REF_KEYS:
        if not _text(episode_ref.get(field)):
            _add(findings, f"projection_request.episode_ref.{field}_required")
    if _text(episode_ref.get("cutoff_at")) and _instant(episode_ref.get("cutoff_at")) is None:
        _add(findings, "projection_request.episode_ref.cutoff_at_must_be_timezone_aware_iso8601")

    thread_ref = _closed(
        request.get("thread_ref"), _THREAD_REF_KEYS, "projection_request.thread_ref", findings,
        required={"thread_id", "claim_class", "requested_admission_level"},
    )
    if not _text(thread_ref.get("thread_id")):
        _add(findings, "projection_request.thread_ref.thread_id_required")
    return episode_ref, thread_ref


def _validate_active_thread(thread_ref: dict[str, Any], candidate: dict[str, Any], findings: list[str]) -> None:
    _closed(thread_ref, _THREAD_REF_KEYS, "projection_request.thread_ref", findings)
    claim_ids = _ids(thread_ref.get("claim_ids"), "projection_request.thread_ref.claim_ids", findings)
    outcome_cell_ids = _ids(
        thread_ref.get("outcome_cell_ids"), "projection_request.thread_ref.outcome_cell_ids", findings,
    )
    if set(claim_ids).intersection(outcome_cell_ids):
        _add(findings, "projection_request.thread_ref.claim_and_outcome_cell_ids_must_be_distinct")
    hypothesis_ids = _closed(
        thread_ref.get("hypothesis_ids"), _HYPOTHESIS_ID_KEYS,
        "projection_request.thread_ref.hypothesis_ids", findings,
    )
    if any(not _text(hypothesis_ids.get(field)) for field in _HYPOTHESIS_ID_KEYS):
        _add(findings, "projection_request.thread_ref.hypothesis_ids_must_bind_h_a_and_h_b")
    action = _mapping(candidate.get("action_scope"))
    expected_hypotheses = {
        "h_a": _mapping(action.get("h_a")).get("hypothesis_id"),
        "h_b": _mapping(action.get("h_b")).get("hypothesis_id"),
    }
    if hypothesis_ids != expected_hypotheses:
        _add(findings, "projection_request.thread_ref.hypothesis_ids_must_match_v5_action_scope")

    responsibility_boundary = _closed(
        thread_ref.get("responsibility_boundary"), _RESPONSIBILITY_BOUNDARY_KEYS,
        "projection_request.thread_ref.responsibility_boundary", findings,
    )
    cohort = _mapping(candidate.get("cohort_snapshot"))
    target_member = next(
        (
            _mapping(raw) for raw in _items(cohort.get("members"))
            if _mapping(raw).get("issuer_id") == action.get("focal_issuer_id")
        ),
        {},
    )
    expected_boundary = {
        "responsibility_unit_id": target_member.get("responsibility_unit_id"),
        "arena_id": _mapping(candidate.get("competitive_arena")).get("competitive_arena_id"),
    }
    if responsibility_boundary != expected_boundary:
        _add(findings, "projection_request.thread_ref.responsibility_boundary_must_match_v5_target_and_arena")


def _validate_episode_binding(
    episode_ref: dict[str, Any], candidate: dict[str, Any], findings: list[str],
) -> None:
    action = _mapping(candidate.get("action_scope"))
    cohort = _mapping(candidate.get("cohort_snapshot"))
    time_contract = _mapping(candidate.get("time_contract"))
    target_issuer_id = action.get("focal_issuer_id")
    target_member = next(
        (
            _mapping(raw) for raw in _items(cohort.get("members"))
            if _mapping(raw).get("issuer_id") == target_issuer_id
        ),
        {},
    )
    if episode_ref.get("issuer_id") != target_issuer_id:
        _add(findings, "projection_request.episode_ref.issuer_id_must_match_v5_target")
    if episode_ref.get("company_id") != target_member.get("company_id"):
        _add(findings, "projection_request.episode_ref.company_id_must_match_v5_target")
    if not _same_instant(episode_ref.get("cutoff_at"), time_contract.get("research_cutoff_at")):
        _add(findings, "projection_request.episode_ref.cutoff_at_must_match_v5_research_cutoff")


def _validate_j2_v5_bridge(
    value: Any,
    *,
    thread_view: dict[str, Any],
    episode_manifest: dict[str, Any],
    j2_read_model: dict[str, Any],
    candidate: dict[str, Any],
    findings: list[str],
) -> None:
    """Require an explicit, auditable mapping from the J2 question into V5."""
    bridge = _closed(
        value,
        _J2_V5_BRIDGE_KEYS,
        "j2_v5_bridge",
        findings,
    )
    action = _mapping(candidate.get("action_scope"))
    hypotheses_by_role = {
        _mapping(raw).get("role"): _mapping(raw)
        for raw in _items(thread_view.get("hypotheses"))
    }
    v5_hypotheses = {"H_A": _mapping(action.get("h_a")), "H_B": _mapping(action.get("h_b"))}
    raw_hypothesis_bindings = bridge.get("hypothesis_bindings")
    if not isinstance(raw_hypothesis_bindings, list) or len(raw_hypothesis_bindings) != 2:
        _add(findings, "j2_v5_bridge.hypothesis_bindings_must_cover_h_a_and_h_b")
    else:
        actual_by_role: dict[str, dict[str, Any]] = {}
        for index, raw in enumerate(raw_hypothesis_bindings):
            binding = _closed(
                raw,
                _HYPOTHESIS_BINDING_KEYS,
                f"j2_v5_bridge.hypothesis_bindings[{index}]",
                findings,
            )
            role = binding.get("role")
            if role not in {"H_A", "H_B"} or role in actual_by_role:
                _add(findings, "j2_v5_bridge.hypothesis_bindings_must_cover_h_a_and_h_b")
            else:
                actual_by_role[str(role)] = binding
        expected_by_role = {
            role: {
                "role": role,
                "j2_hypothesis_id": hypotheses_by_role.get(role, {}).get("hypothesis_id"),
                "j2_statement": hypotheses_by_role.get(role, {}).get("statement"),
                "v5_hypothesis_id": v5_hypotheses[role].get("hypothesis_id"),
                "v5_mechanism": v5_hypotheses[role].get("mechanism"),
            }
            for role in ("H_A", "H_B")
        }
        if actual_by_role != expected_by_role:
            _add(findings, "j2_v5_bridge.hypotheses_must_match_j2_and_v5_semantics")
        for role in ("H_A", "H_B"):
            j2_hypothesis = hypotheses_by_role.get(role, {})
            v5_hypothesis = v5_hypotheses[role]
            if (
                j2_hypothesis.get("hypothesis_id") != v5_hypothesis.get("hypothesis_id")
                or j2_hypothesis.get("statement") != v5_hypothesis.get("mechanism")
            ):
                _add(
                    findings,
                    "j2_v5_bridge.hypotheses_must_preserve_one_frozen_mechanism_identity",
                )

    episode_cells = {
        _mapping(raw).get("outcome_cell_id"): _mapping(raw)
        for raw in _items(episode_manifest.get("outcome_cells"))
    }
    expected_cell_ids = list(_items(thread_view.get("outcome_cell_refs")))
    v5_metric_ids = [
        _mapping(raw).get("metric_id") for raw in _items(candidate.get("measurement_contracts"))
    ]
    raw_outcome_bindings = bridge.get("outcome_bindings")
    bound_cells: list[str] = []
    bound_metrics: list[str] = []
    if not isinstance(raw_outcome_bindings, list) or not raw_outcome_bindings:
        _add(findings, "j2_v5_bridge.outcome_bindings_required")
    else:
        for index, raw in enumerate(raw_outcome_bindings):
            binding = _closed(
                raw,
                _OUTCOME_BINDING_KEYS,
                f"j2_v5_bridge.outcome_bindings[{index}]",
                findings,
            )
            cell_id = binding.get("outcome_cell_id")
            measurement_ref = binding.get("measurement_contract_ref")
            bound_contracts = [_mapping(raw) for raw in _items(binding.get("v5_measurement_contracts"))]
            metric_ids = [contract.get("metric_id") for contract in bound_contracts]
            if cell_id not in expected_cell_ids or cell_id in bound_cells:
                _add(findings, "j2_v5_bridge.outcome_cells_must_exactly_cover_j2_thread")
            else:
                bound_cells.append(str(cell_id))
            if not _text(measurement_ref) or measurement_ref != episode_cells.get(cell_id, {}).get("measurement_contract_ref"):
                _add(findings, "j2_v5_bridge.measurement_contract_ref_must_match_j0_outcome_cell")
            candidate_contracts = {
                _mapping(raw).get("metric_id"): _mapping(raw)
                for raw in _items(candidate.get("measurement_contracts"))
            }
            if (
                len(metric_ids) != 1
                or any(
                    not _text(metric_id) or candidate_contracts.get(metric_id) != contract
                    for metric_id, contract in zip(metric_ids, bound_contracts, strict=True)
                )
            ):
                _add(findings, "j2_v5_bridge.measurement_contracts_must_match_v5_semantics")
            if len(metric_ids) == 1 and metric_ids[0] != measurement_ref:
                _add(findings, "j2_v5_bridge.v5_metric_id_must_match_frozen_measurement_ref")
            bound_metrics.extend(str(metric_id) for metric_id in metric_ids if _text(metric_id))
        if set(bound_cells) != set(expected_cell_ids) or len(bound_cells) != len(expected_cell_ids):
            _add(findings, "j2_v5_bridge.outcome_cells_must_exactly_cover_j2_thread")
        if set(bound_metrics) != set(v5_metric_ids) or len(bound_metrics) != len(v5_metric_ids):
            _add(findings, "j2_v5_bridge.v5_metrics_must_be_mapped_exactly_once")

    lineage = _closed(
        bridge.get("source_lineage"),
        _SOURCE_LINEAGE_KEYS,
        "j2_v5_bridge.source_lineage",
        findings,
    )
    expected_lineage = {
        "j1_source_packet_refs": deepcopy(_items(j2_read_model.get("source_packet_refs"))),
        "j2_source_refs": deepcopy(_items(thread_view.get("source_refs"))),
        "v5_source_provenance": deepcopy(_mapping(candidate.get("source_provenance"))),
        "v5_sources": deepcopy(_items(candidate.get("source_manifest"))),
    }
    if lineage != expected_lineage:
        _add(findings, "j2_v5_bridge.source_lineage_must_match_j1_j2_and_v5")


def _validate_target_trial_bindings(request: dict[str, Any], candidate: dict[str, Any], findings: list[str]) -> None:
    bindings = _closed(
        request.get("target_trial_bindings"), _TARGET_TRIAL_KEYS,
        "projection_request.target_trial_bindings", findings,
    )
    action = _mapping(candidate.get("action_scope"))
    cohort = _mapping(candidate.get("cohort_snapshot"))
    time_contract = _mapping(candidate.get("time_contract"))
    panel = _mapping(candidate.get("counterfactual_panel"))
    panel_members = [_mapping(raw) for raw in _items(panel.get("members"))]
    metrics = [_mapping(raw) for raw in _items(candidate.get("measurement_contracts"))]
    metric_ids_by_clock = {
        str(metric.get("clock")): metric.get("metric_id")
        for metric in metrics if metric.get("clock") in {"D3", "D4"}
    }

    action_binding = _closed(
        bindings.get("action_exposure"), _ACTION_EXPOSURE_KEYS,
        "projection_request.target_trial_bindings.action_exposure", findings,
    )
    expected_action_binding = {
        "action_id": action.get("action_id"),
        "focal_issuer_id": action.get("focal_issuer_id"),
        "exposure_start": _mapping(action.get("action_effective_window")).get("start"),
        "economic_carrier_ids": [
            _mapping(raw).get("carrier_id") for raw in _items(action.get("economic_carriers"))
        ],
        "scope_bridge_ids": [
            _mapping(raw).get("scope_bridge_id") for raw in _items(candidate.get("scope_bridges"))
        ],
    }
    if action_binding != expected_action_binding:
        _add(findings, "projection_request.action_exposure_must_match_v5_candidate")

    eligibility_binding = _closed(
        bindings.get("eligibility_time_zero"), _ELIGIBILITY_TIME_ZERO_KEYS,
        "projection_request.target_trial_bindings.eligibility_time_zero", findings,
    )
    expected_eligibility_binding = {
        "cohort_snapshot_id": cohort.get("cohort_snapshot_id"),
        "eligibility_as_of": time_contract.get("cohort_eligibility_as_of"),
        "time_zero": _mapping(time_contract.get("action_effective_window")).get("start"),
        "decision_observable_at": time_contract.get("decision_observable_at"),
    }
    if eligibility_binding != expected_eligibility_binding:
        _add(findings, "projection_request.eligibility_time_zero_must_match_v5_candidate")

    comparator_binding = _closed(
        bindings.get("comparator_roles"), _COMPARATOR_ROLE_KEYS,
        "projection_request.target_trial_bindings.comparator_roles", findings,
    )
    expected_comparator_binding = {
        "counterfactual_panel_id": panel.get("counterfactual_panel_id"),
        "external_shock_comparator_ids": [
            member.get("issuer_id") for member in panel_members
            if member.get("causal_role") == "EXTERNAL_SHOCK_COMPARATOR"
        ],
        "witness_ids": [
            member.get("issuer_id") for member in panel_members
            if member.get("causal_role") == "EQUILIBRIUM_RESPONSE_WITNESS"
        ],
        "falsifier_ids": [
            member.get("issuer_id") for member in panel_members
            if member.get("causal_role") == "FALSIFIER"
        ],
    }
    if comparator_binding != expected_comparator_binding:
        _add(findings, "projection_request.comparator_roles_must_match_v5_panel")

    outcome_binding = _closed(
        bindings.get("outcome_follow_up"), _OUTCOME_FOLLOW_UP_KEYS,
        "projection_request.target_trial_bindings.outcome_follow_up", findings,
    )
    expected_outcome_binding = {
        "metric_ids_by_clock": metric_ids_by_clock,
        "economic_periods": deepcopy(_mapping(time_contract.get("metric_economic_periods"))),
        "outcome_window_id": time_contract.get("outcome_window_id"),
        "minimum_decision_exposure_rule": time_contract.get("minimum_decision_exposure_rule"),
    }
    if outcome_binding != expected_outcome_binding:
        _add(findings, "projection_request.outcome_follow_up_must_match_v5_candidate")

    censoring_binding = _closed(
        bindings.get("censoring_interference"), _CENSORING_INTERFERENCE_KEYS,
        "projection_request.target_trial_bindings.censoring_interference", findings,
    )
    member_assumptions = _items(censoring_binding.get("member_assumptions"))
    for index, raw in enumerate(member_assumptions):
        _closed(
            raw, _MEMBER_ASSUMPTION_KEYS,
            f"projection_request.target_trial_bindings.censoring_interference.member_assumptions[{index}]",
            findings,
        )
    expected_censoring_binding = {
        "censoring_rule": CENSORING_RULE,
        "non_replacement_rule": panel.get("non_replacement_rule"),
        "member_assumptions": [
            {
                "issuer_id": member.get("issuer_id"),
                "parallel_action": member.get("parallel_action"),
                "target_action_spillover": member.get("target_action_spillover"),
            }
            for member in panel_members
        ],
    }
    if censoring_binding != expected_censoring_binding:
        _add(findings, "projection_request.censoring_interference_must_match_v5_panel")

    estimand_binding = _closed(
        bindings.get("estimand"), _ESTIMAND_KEYS,
        "projection_request.target_trial_bindings.estimand", findings,
    )
    if not _text(estimand_binding.get("estimand_id")):
        _add(findings, "projection_request.estimand.estimand_id_required")
    expected_estimand_binding = {
        "target_issuer_id": action.get("focal_issuer_id"),
        "action_id": action.get("action_id"),
        "comparator_role": "EXTERNAL_SHOCK_COMPARATOR",
        "metric_ids_by_clock": metric_ids_by_clock,
        "contrast": ESTIMAND_CONTRAST,
        "outcome_window_id": time_contract.get("outcome_window_id"),
    }
    if {key: estimand_binding.get(key) for key in expected_estimand_binding} != expected_estimand_binding:
        _add(findings, "projection_request.estimand_must_match_v5_candidate")

    bound_issuer_ids = [
        *expected_comparator_binding["external_shock_comparator_ids"],
        *expected_comparator_binding["witness_ids"],
        *expected_comparator_binding["falsifier_ids"],
    ]
    if any(_typed_reference_issuer(issuer_id) for issuer_id in bound_issuer_ids):
        _add(findings, "projection_request.relative_reference_or_archetype_cannot_be_comparator")


def _compile_comparative_projection(projection_request: Any) -> dict[str, Any]:
    """Return a thread-local J4 status and, only when admitted, the unchanged V5 bundle."""
    if not isinstance(projection_request, dict):
        return _projection_result(
            {}, status=NOT_ADMITTED, findings=["projection_request_must_be_object"],
        )

    request = projection_request
    findings: list[str] = []
    episode_ref, thread_ref = _validate_protocol_identity(request, findings)
    cutoff = _instant(episode_ref.get("cutoff_at"))
    for path in _pre_outcome_forbidden_paths(request):
        _add(findings, "projection_request.pre_outcome_price_return_or_actual_data_forbidden:" + path)
    for path in _post_cutoff_data_paths(request, cutoff):
        _add(findings, "projection_request.post_cutoff_data_forbidden:" + path)
    for path in _pre_outcome_leakage_text_paths(request, "projection_request"):
        _add(findings, "projection_request.pre_outcome_narrative_leakage_forbidden:" + path)
    for path in _noncausal_reference_paths(request):
        _add(findings, "projection_request.relative_reference_or_archetype_cannot_be_comparator:" + path)

    if findings:
        return _projection_result(request, status=NOT_ADMITTED, findings=findings)

    if not (
        thread_ref.get("claim_class") == RELATIVE_CAUSAL
        and thread_ref.get("requested_admission_level") == E3_COMPARATIVE_LAB
    ):
        return _projection_result(
            request,
            status=NOT_REQUESTED,
            findings=["thread_did_not_explicitly_request_relative_causal_e3"],
        )

    candidate_value = request.get("v5_candidate")
    candidate = _mapping(candidate_value)
    if not isinstance(candidate_value, dict):
        _add(findings, "projection_request.v5_candidate_required_for_relative_causal_e3")
    before = deepcopy(candidate)

    _validate_active_thread(thread_ref, candidate, findings)
    _validate_episode_binding(episode_ref, candidate, findings)
    _validate_target_trial_bindings(request, candidate, findings)

    validation = v5.validate_v5_candidate(candidate)
    if candidate != before:
        _add(findings, "projection_adapter_or_v5_validator_mutated_candidate")
    if candidate.get("selection_goal") != "SELECTION":
        _add(findings, "projection_request.v5_candidate_must_request_selection")
    if validation.get("admission_status") != v5.SELECTION_ADMITTED:
        _add(findings, "projection_request.v5_candidate_not_selection_admitted")
    for finding in validation.get("findings", []):
        _add(findings, "v5:" + str(finding))

    status = ADMISSION_CANDIDATE if not findings else NOT_ADMITTED
    return _projection_result(
        request,
        status=status,
        findings=findings,
        v5_validation=validation,
        candidate=candidate,
    )


def compile_serialized_j2_thread_projection(
    episode_manifest: Any,
    reconstruction_read_model: Any,
    reconstruction_inputs: Any,
    mechanism_thread_set: Any,
    thread_id: str,
    target_trial_bindings: Any,
    v5_candidate: Any,
    *,
    reconstruction_registry: Any | None = None,
) -> dict[str, Any]:
    """Compile J2, then project one compiler-resolved thread into J4.

    Callers provide J0/J1/J2 source objects, never a claimed J2 read model.
    The public path accepts thread identity and permissions only from the J2
    compiler result; target-trial bindings and the V5 candidate remain caller
    supplied and are independently checked by the private J4 protocol core.
    """
    episode = _mapping(episode_manifest)
    failure_request = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "episode_ref": {
            field: episode.get(field)
            for field in ("episode_id", "company_id", "issuer_id", "cutoff_at")
        },
        "thread_ref": {
            "thread_id": thread_id,
            "claim_class": None,
            "requested_admission_level": None,
        },
    }
    if reconstruction_registry is None:
        return _projection_result(
            failure_request,
            status=NOT_ADMITTED,
            findings=["serialized_j2.frozen_reconstruction_registry_required"],
        )
    compiled = mechanism.compile_mechanism_thread_projection(
        mechanism_thread_set,
        episode_manifest=episode_manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=reconstruction_registry,
    )
    if not isinstance(compiled, dict) or compiled.get("valid") is not True:
        compiler_findings = _items(_mapping(compiled).get("findings"))
        findings = ["serialized_j2.j2_compile_failed:" + str(item) for item in compiler_findings]
        if not findings:
            findings = ["serialized_j2.j2_compile_failed"]
        return _projection_result(failure_request, status=NOT_ADMITTED, findings=findings)

    read_model = _mapping(compiled.get("mechanism_thread_read_model"))
    matching_views = [
        _mapping(raw)
        for raw in _items(read_model.get("thread_views"))
        if _mapping(raw).get("thread_id") == thread_id
    ]
    if len(matching_views) != 1:
        return _projection_result(
            failure_request,
            status=NOT_ADMITTED,
            findings=["serialized_j2.compiled_thread_view_required_exactly_once"],
        )

    view = matching_views[0]
    hypotheses_by_role: dict[str, list[Any]] = {"H_A": [], "H_B": []}
    for raw in _items(view.get("hypotheses")):
        hypothesis = _mapping(raw)
        role = hypothesis.get("role")
        if role in hypotheses_by_role:
            hypotheses_by_role[str(role)].append(hypothesis.get("hypothesis_id"))

    def only_hypothesis_id(role: str) -> Any:
        values = hypotheses_by_role[role]
        return values[0] if len(values) == 1 else None

    public_bindings = deepcopy(_mapping(target_trial_bindings))
    request = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "episode_ref": {
            "episode_id": _mapping(read_model.get("episode_ref")).get("episode_id"),
            "company_id": read_model.get("company_id"),
            "issuer_id": read_model.get("issuer_id"),
            "cutoff_at": read_model.get("cutoff_at"),
        },
        "thread_ref": {
            "thread_id": view.get("thread_id"),
            "claim_class": view.get("claim_type"),
            "requested_admission_level": (
                E3_COMPARATIVE_LAB
                if view.get("e3_comparative_requested") is True
                else "E2_MECHANISM_PROBE"
            ),
            "claim_ids": deepcopy(view.get("claim_ids")),
            "hypothesis_ids": {
                "h_a": only_hypothesis_id("H_A"),
                "h_b": only_hypothesis_id("H_B"),
            },
            "responsibility_boundary": deepcopy(view.get("responsibility_boundary")),
            "outcome_cell_ids": deepcopy(view.get("outcome_cell_refs")),
        },
        "target_trial_bindings": public_bindings,
        "v5_candidate": deepcopy(v5_candidate),
    }

    explicit_relative_e3 = bool(
        view.get("claim_type") == RELATIVE_CAUSAL
        and view.get("e3_comparative_requested") is True
    )
    compiler_boundary_findings: list[str] = []
    if read_model.get("comparative_authorization") != "NOT_AUTHORIZED":
        _add(
            compiler_boundary_findings,
            "serialized_j2.compiled_read_model.comparative_authorization_must_remain_not_authorized",
        )
    if view.get("comparative_performed") is not False:
        _add(
            compiler_boundary_findings,
            "serialized_j2.compiled_thread_view.comparative_performed_must_be_false",
        )
    if explicit_relative_e3:
        if view.get("resolution_status") != "RESOLVED":
            _add(compiler_boundary_findings, "serialized_j2.compiled_thread_view_must_be_resolved")
        for finding in _items(view.get("comparative_contract_findings")):
            _add(
                compiler_boundary_findings,
                "serialized_j2.comparative_projection_contract:" + str(finding),
            )
        if view.get("j4_comparative_eligible") is not True:
            _add(compiler_boundary_findings, "serialized_j2.compiled_thread_view_not_comparative_eligible")
        _validate_j2_v5_bridge(
            view.get("comparative_projection_contract"),
            thread_view=view,
            episode_manifest=episode,
            j2_read_model=read_model,
            candidate=_mapping(v5_candidate),
            findings=compiler_boundary_findings,
        )
    if compiler_boundary_findings:
        return _projection_result(
            request,
            status=NOT_ADMITTED,
            findings=compiler_boundary_findings,
        )
    return _compile_comparative_projection(request)


project_mechanism_thread_to_comparative = compile_serialized_j2_thread_projection
