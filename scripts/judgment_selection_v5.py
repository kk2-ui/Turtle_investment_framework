#!/usr/bin/env python3
"""Pure pre-outcome admission checks for Turtle's V5 selection bundles.

This module intentionally has no database, file, network, V4, outcome, or control-plane
dependency.  It validates only whether a frozen *pre-outcome* economic contract has the
minimum shape to be admitted to a later seal.  It never computes an outcome verdict.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import math
from typing import Any, Iterable


SCHEMA_VERSION = "judgment-selection-admission-v5.v1"
METHOD_EPOCH_ID = "JUDGMENT_SELECTION_ADMISSION_V5_2_COMPARATOR_PANEL"

SELECTION_ADMITTED = "SELECTION_ADMITTED"
STAGE0_REJECTED = "STAGE0_REJECTED"
NO_PRIMARY = "NO_PRIMARY"
NOT_ADMITTED = "NOT_ADMITTED"
TEACHING_ONLY = "TEACHING_ONLY"
ADMISSION_STATUSES = {
    SELECTION_ADMITTED,
    STAGE0_REJECTED,
    NO_PRIMARY,
    NOT_ADMITTED,
    TEACHING_ONLY,
}

SUPPORTED_TOPOLOGIES = {"CUSTOMER_RESPONSE", "COST_RESTRUCTURING"}
UNSUPPORTED_TOPOLOGIES = {
    "PRODUCT_OR_INNOVATION",
    "CAPITAL_ALLOCATION_OR_INTEGRATION",
}
BRIDGE_TYPES = {"IDENTITY", "SEGMENT_MATCH", "QUANTIFIED_ISSUER_AGGREGATION"}
ARENA_SCOPE_TYPES = {"NATIONAL", "REGIONAL", "EXPORT", "SEGMENT", "MULTI_REGION_PORTFOLIO"}
OVERLAP_RELATIONS = {
    "REQUIRED_EQUAL",
    "REQUIRED_OVERLAP",
    "REQUIRED_EXPOSURE",
    "NOT_REQUIRED",
}
PANEL_ROLES = {
    "EXTERNAL_SHOCK_COMPARATOR",
    "EQUILIBRIUM_RESPONSE_WITNESS",
    "FALSIFIER",
}
SOURCE_LANES = {"STAGE0_STATIC", "ACTION_STATIC", "PUBLIC_ARENA_CONTEXT", "OUTCOME_SEALED"}
ALLOWED_D3_CONSTRUCTS = {
    "OPERATING_CONTRIBUTION_AMOUNT",
    "OPERATING_CONTRIBUTION_MARGIN",
    "UNIT_ECONOMICS_FROM_SAME_PERIMETER_FIELDS",
}
D4_FORMULA_ID = "D4_CONSERVATIVE_OWNER_CASH_V1"
D4_REQUIRED_RAW_FIELDS = (
    "cash_from_operating_activities",
    "cash_paid_for_all_long_lived_asset_purchases",
    "beginning_accounts_receivable",
    "beginning_prepayments",
    "beginning_inventory",
    "beginning_accounts_payable",
    "beginning_contract_liabilities_or_customer_advances",
    "ending_accounts_receivable",
    "ending_prepayments",
    "ending_inventory",
    "ending_accounts_payable",
    "ending_contract_liabilities_or_customer_advances",
)
D4_RESTRUCTURING_CASH_FIELD = "restructuring_cash_paid"
D4_CASH_WORKING_CAPITAL_COMPONENTS = {
    "accounts_receivable",
    "prepayments",
    "inventory",
    "accounts_payable",
    "contract_liabilities_or_customer_advances",
}
D4_RESTRUCTURING_TREATMENTS = {
    "IN_OCF_NO_ADDITIONAL_DEDUCTION",
    "SEPARATE_OPERATING_CASH_DEDUCTION",
    "OUT_OF_PERIMETER_CANNOT_SETTLE",
}
_LEGACY_IDENTITIES = ("r-104", "r104", "r-103", "r103")
_STAGE0_FORBIDDEN_KEYS = {
    "action",
    "action_id",
    "action_title",
    "action_effective_window",
    "focal_target",
    "focal_issuer",
    "focal_issuer_id",
    "target_issuer",
    "target_issuer_id",
    "final_peer",
    "final_peer_role",
    "causal_role",
    "common_driver",
    "outcome",
    "outcome_value",
    "outcome_source",
    "winner",
}
_STAGE0_ALLOWED_KEYS = {
    "cohort_snapshot_id",
    "cohort_eligibility_as_of",
    "arena_family",
    "members",
}
_STAGE0_MEMBER_ALLOWED_KEYS = {
    "company_id",
    "issuer_id",
    "responsibility_unit_id",
    "control_group_id",
    "boundary",
    "carrier_identity_source_ids",
    "d2_or_cost_field_history",
    "d3_d4_field_history",
}
_STAGE0_FIELD_ALLOWED_KEYS = {"period_end", "field_id", "source_id"}
_STAGE0_MEMBER_BOUNDARY_KEYS = {"responsibility_unit_id", "perimeter_id", "unit"}
_OUTCOME_CONTRACT_FORBIDDEN_KEYS = {
    "source",
    "source_id",
    "source_available_at",
    "published_at",
    "published_at_or_date",
    "publisher",
    "official_artifact_id",
    "title",
    "url",
    "actual_outcome_inventory",
    "value",
}
_SOURCE_PROVENANCE_KEYS = {"h1", "h2"}
_H1_PROVENANCE_KEYS = {
    "receipt_id", "receipt_version", "cohort_id", "selection_as_of", "curator_id",
}
_H2_PROVENANCE_KEYS = {
    "receipt_id", "receipt_version", "parent_receipt_id", "parent_receipt_version",
    "screen_id", "cutoff_at",
}
_STATIC_SOURCE_IDENTITY_TEXT_FIELDS = (
    "official_artifact_id",
    "source_url",
    "publisher",
    "source_type",
    "issuer_id",
    "responsibility_unit_id",
    "perimeter_id",
    "unit",
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _date_only(value: Any) -> date | None:
    if not _text(value):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _source_is_before(source: dict[str, Any], boundary: datetime) -> bool:
    precision = source.get("availability_precision")
    available = source.get("published_at_or_date")
    if precision == "DATE_ONLY":
        published = _date_only(available)
        return published is not None and published < boundary.date()
    if precision == "INTRADAY":
        published_at = _instant(available)
        return published_at is not None and published_at <= boundary
    return False


def _valid_source_provenance(value: Any, findings: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the receipt references and immutable snapshots without any DB read."""
    provenance = _mapping(value)
    if set(provenance) != _SOURCE_PROVENANCE_KEYS:
        _add(findings, "source_provenance_shape_invalid")
    h1 = _mapping(provenance.get("h1"))
    h2 = _mapping(provenance.get("h2"))
    if set(h1) != _H1_PROVENANCE_KEYS:
        _add(findings, "source_provenance_h1_shape_invalid")
    if set(h2) != _H2_PROVENANCE_KEYS:
        _add(findings, "source_provenance_h2_shape_invalid")
    for field in ("receipt_id", "cohort_id", "curator_id"):
        if not _text(h1.get(field)):
            _add(findings, "source_provenance_h1_identity_invalid")
    if not _positive_integer(h1.get("receipt_version")):
        _add(findings, "source_provenance_h1_version_invalid")
    if _instant(h1.get("selection_as_of")) is None:
        _add(findings, "source_provenance_h1_selection_as_of_invalid")
    for field in ("receipt_id", "parent_receipt_id", "screen_id"):
        if not _text(h2.get(field)):
            _add(findings, "source_provenance_h2_identity_invalid")
    if not _positive_integer(h2.get("receipt_version")) or not _positive_integer(h2.get("parent_receipt_version")):
        _add(findings, "source_provenance_h2_version_invalid")
    if _instant(h2.get("cutoff_at")) is None:
        _add(findings, "source_provenance_h2_cutoff_invalid")
    if (
        _text(h1.get("receipt_id"))
        and _positive_integer(h1.get("receipt_version"))
        and (h2.get("parent_receipt_id"), h2.get("parent_receipt_version"))
        != (h1.get("receipt_id"), h1.get("receipt_version"))
    ):
        _add(findings, "source_provenance_h2_parent_not_h1")
    return h1, h2


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_strings(nested)


def _contains_legacy_identity(bundle: dict[str, Any]) -> bool:
    return any(token in text.lower() for text in _walk_strings(bundle) for token in _LEGACY_IDENTITIES)


def _stage0_has_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in _STAGE0_FORBIDDEN_KEYS:
                return True
            if _stage0_has_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(_stage0_has_forbidden_key(item) for item in value)
    return False


def _stage0_has_unapproved_shape(cohort: dict[str, Any]) -> bool:
    """Stage 0 is deliberately a closed information set, not a loose memo."""
    if set(cohort) - _STAGE0_ALLOWED_KEYS:
        return True
    for member in _items(cohort.get("members")):
        member_map = _mapping(member)
        if set(member_map) - _STAGE0_MEMBER_ALLOWED_KEYS:
            return True
        boundary = _mapping(member_map.get("boundary"))
        if set(boundary) - _STAGE0_MEMBER_BOUNDARY_KEYS:
            return True
        for history_name in ("d2_or_cost_field_history", "d3_d4_field_history"):
            for record in _items(member_map.get(history_name)):
                if set(_mapping(record)) - _STAGE0_FIELD_ALLOWED_KEYS:
                    return True
    return False


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _source_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [item for item in _items(value) if _text(item)]


def _all_references_known(value: Any, source_by_id: dict[str, dict[str, Any]], findings: list[str], prefix: str) -> None:
    for source_id in _source_ids(value):
        if source_id not in source_by_id:
            _add(findings, f"{prefix}_source_not_in_manifest")


def _source_has_lane(
    source_ids: Any,
    source_by_id: dict[str, dict[str, Any]],
    lane: str,
    findings: list[str],
    prefix: str,
) -> None:
    values = _source_ids(source_ids)
    if not values or any(source_by_id.get(source_id, {}).get("source_lane") != lane for source_id in values):
        _add(findings, f"{prefix}_source_lane_invalid")


def _membership_is_proven(value: Any, source_by_id: dict[str, dict[str, Any]]) -> bool:
    membership = _mapping(value)
    source_ids = _source_ids(membership.get("source_ids"))
    return membership.get("status") == "PROVEN" and bool(source_ids) and all(source_id in source_by_id for source_id in source_ids)


def _valid_dimension_list(
    value: Any,
    source_by_id: dict[str, dict[str, Any]],
    findings: list[str],
    prefix: str,
    *,
    require_peer_evidence: bool,
) -> list[dict[str, Any]]:
    dimensions = [_mapping(item) for item in _items(value)]
    if not dimensions:
        _add(findings, f"{prefix}_dimensions_missing")
        return []
    for dimension in dimensions:
        if dimension.get("relation") not in OVERLAP_RELATIONS:
            _add(findings, f"{prefix}_relation_invalid")
        if not _text(dimension.get("dimension")) or not _text(dimension.get("rationale_from_mechanism")):
            _add(findings, f"{prefix}_dimension_identity_missing")
        target_sources = dimension.get("target_evidence_source_ids")
        peer_sources = dimension.get("peer_evidence_source_ids")
        if not _source_ids(target_sources):
            _add(findings, f"{prefix}_target_evidence_missing")
        _all_references_known(target_sources, source_by_id, findings, f"{prefix}_target_evidence")
        if require_peer_evidence and not _source_ids(peer_sources):
            _add(findings, f"{prefix}_peer_evidence_missing")
        _all_references_known(peer_sources, source_by_id, findings, f"{prefix}_peer_evidence")
    return dimensions


def _metric_raw_locator_ids(metric: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for locator in _items(metric.get("raw_field_source_locators")):
        field_id = _mapping(locator).get("field_id")
        if _text(field_id):
            ids.add(field_id)
    return ids


def _outcome_contract_has_actual_metadata(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in _OUTCOME_CONTRACT_FORBIDDEN_KEYS:
                return True
            if _outcome_contract_has_actual_metadata(nested):
                return True
    elif isinstance(value, list):
        return any(_outcome_contract_has_actual_metadata(item) for item in value)
    return False


def _valid_d3_outcome_formula(metric: dict[str, Any]) -> bool:
    formula = _mapping(metric.get("outcome_formula"))
    raw_fields = _source_ids(metric.get("formula_and_ordered_raw_fields"))
    terms = [_mapping(term) for term in _items(formula.get("terms"))]
    term_ids = [term.get("field_id") for term in terms if _text(term.get("field_id"))]
    denominator = formula.get("denominator_field_id")
    if formula.get("formula_type") != "LINEAR_COMBINATION" or not terms:
        return False
    if len(term_ids) != len(terms) or len(set(term_ids)) != len(term_ids):
        return False
    if any(not _finite(term.get("coefficient")) or term.get("coefficient") == 0 for term in terms):
        return False
    if any(field_id not in raw_fields for field_id in term_ids):
        return False
    construct = metric.get("economic_construct")
    if construct == "OPERATING_CONTRIBUTION_AMOUNT":
        return denominator is None and set(term_ids) == set(raw_fields)
    return _text(denominator) and denominator in raw_fields and set(term_ids) | {denominator} == set(raw_fields)


def _validate_outcome_contract(
    value: Any,
    *,
    target_issuer_id: Any,
    panel_members: list[dict[str, Any]],
    metrics_by_clock: dict[str, dict[str, Any]],
    metric_periods: dict[str, Any],
    findings: list[str],
) -> None:
    """Check frozen matrix identity only; receipt sources and values are post-seal data."""
    contract = _mapping(value)
    if _outcome_contract_has_actual_metadata(contract):
        _add(findings, "isolation_outcome_contract_actual_source_metadata_forbidden")
    matrix = _items(contract.get("frozen_raw_matrix"))
    bridge = _mapping(contract.get("fiscal_calendar_bridge"))
    if not matrix:
        _add(findings, "outcome_contract_frozen_raw_matrix_missing")
    bridge_status = bridge.get("status")
    if bridge_status not in {"NOT_REQUIRED", "FROZEN"}:
        _add(findings, "outcome_contract_fiscal_calendar_bridge_invalid")
    elif bridge_status == "FROZEN":
        if not _text(bridge.get("bridge_id")) or not _text(bridge.get("comparison_window_id")):
            _add(findings, "outcome_contract_fiscal_calendar_bridge_identity_missing")
    elif bridge.get("bridge_id") is not None or bridge.get("comparison_window_id") is not None:
        _add(findings, "outcome_contract_not_required_bridge_must_not_carry_identity")

    comparators = [
        member.get("issuer_id")
        for member in panel_members
        if member.get("causal_role") == "EXTERNAL_SHOCK_COMPARATOR"
    ]
    issuer_ids = {target_issuer_id, *comparators}
    metric_by_id = {
        metric.get("metric_id"): metric
        for metric in metrics_by_clock.values()
        if _text(metric.get("metric_id"))
    }
    frozen: set[tuple[str, str, str, str]] = set()
    for row in matrix:
        cell = _mapping(row)
        key = (
            cell.get("issuer_id"),
            cell.get("metric_id"),
            cell.get("period_id"),
            cell.get("field_id"),
        )
        if not all(_text(item) for item in key):
            _add(findings, "outcome_contract_frozen_raw_matrix_identity_missing")
            continue
        if key in frozen:
            _add(findings, "outcome_contract_frozen_raw_matrix_duplicate_cell")
            continue
        frozen.add(key)
        metric = metric_by_id.get(cell.get("metric_id"))
        if cell.get("issuer_id") not in issuer_ids:
            _add(findings, "outcome_contract_member_must_be_target_or_external_comparator")
            continue
        if metric is None:
            _add(findings, "outcome_contract_metric_not_frozen")
            continue
        expected_role = {
            metric.get("baseline_period_id"): "BASELINE",
            metric.get("primary_outcome_period_id"): "PRIMARY_OUTCOME",
        }.get(cell.get("period_id"))
        if expected_role is None or cell.get("observation_role") != expected_role:
            _add(findings, "outcome_contract_period_or_observation_role_invalid")
        if cell.get("field_id") not in _source_ids(metric.get("formula_and_ordered_raw_fields")):
            _add(findings, "outcome_contract_field_not_in_metric_identity")
        economic_period = _mapping(cell.get("economic_period"))
        if not _text(economic_period.get("start")) or not _text(economic_period.get("end")):
            _add(findings, "outcome_contract_economic_period_not_metric_bound")
        elif cell.get("observation_role") == "PRIMARY_OUTCOME" and economic_period != _mapping(metric_periods.get(metric.get("clock"))):
            _add(findings, "outcome_contract_economic_period_not_metric_bound")
        if cell.get("perimeter_id") != metric.get("accounting_perimeter_id") or cell.get("currency_and_unit") != metric.get("currency_and_unit"):
            _add(findings, "outcome_contract_measurement_identity_not_metric_bound")
        if not _text(cell.get("field_locator")):
            _add(findings, "outcome_contract_field_locator_missing")

    for metric in metrics_by_clock.values():
        for issuer_id in issuer_ids:
            for period_id in (metric.get("baseline_period_id"), metric.get("primary_outcome_period_id")):
                for field_id in _source_ids(metric.get("formula_and_ordered_raw_fields")):
                    if (issuer_id, metric.get("metric_id"), period_id, field_id) not in frozen:
                        _add(findings, "outcome_contract_required_frozen_raw_cell_missing")


def _valid_threshold(value: Any, *, operator: str, unit: Any) -> bool:
    threshold = _mapping(value)
    return (
        threshold.get("operator") == operator
        and _finite(threshold.get("value"))
        and _text(threshold.get("unit"))
        and threshold.get("unit") == unit
    )


def _status(findings: list[str], selection_goal: Any) -> str:
    review_prefixes = ("review_", "reviewer_")
    core_findings = [finding for finding in findings if not finding.startswith(review_prefixes)]
    if any(finding.startswith((
        "isolation_", "firewall_", "bundle_", "source_provenance_", "source_static_identity_",
    )) for finding in core_findings):
        return NOT_ADMITTED
    if any(finding.startswith("stage0_") for finding in core_findings):
        return STAGE0_REJECTED
    if core_findings:
        return NO_PRIMARY
    if findings:
        return NOT_ADMITTED
    if selection_goal == "TEACHING_ONLY":
        return TEACHING_ONLY
    return SELECTION_ADMITTED


def validate_v5_candidate(bundle: Any) -> dict[str, Any]:
    """Validate a V5 pre-outcome bundle without external reads or side effects.

    The returned status says only whether this *pre-outcome* candidate is eligible for a
    later seal.  It must not be used as a result, probability, investment, or report-use
    decision.
    """
    findings: list[str] = []
    if not isinstance(bundle, dict):
        return {"valid": False, "admission_status": NOT_ADMITTED, "findings": ["bundle_not_object"]}

    if bundle.get("schema_version") != SCHEMA_VERSION:
        _add(findings, "bundle_schema_version_invalid")
    if bundle.get("method_epoch_id") != METHOD_EPOCH_ID:
        _add(findings, "bundle_method_epoch_invalid")
    selection_goal = bundle.get("selection_goal")
    if selection_goal not in {"SELECTION", "TEACHING_ONLY"}:
        _add(findings, "bundle_selection_goal_invalid")
    if not _text(bundle.get("candidate_id")):
        _add(findings, "bundle_candidate_id_missing")
    if not _text(bundle.get("selection_freeze_id")):
        _add(findings, "bundle_selection_freeze_id_missing")
    if not _text(bundle.get("episode_collision_key")):
        _add(findings, "bundle_episode_collision_key_missing")
    sealed_at = _instant(bundle.get("sealed_at"))
    recorded_at = _instant(bundle.get("recorded_at"))
    if sealed_at is None:
        _add(findings, "bundle_sealed_at_invalid")
    if recorded_at is None:
        _add(findings, "bundle_recorded_at_invalid")
    elif sealed_at is not None and sealed_at > recorded_at:
        _add(findings, "bundle_sealed_after_recorded")
    if "research_cutoff_at" in bundle:
        _add(findings, "bundle_research_cutoff_must_only_exist_in_time_contract")
    if _contains_legacy_identity(bundle):
        _add(findings, "isolation_legacy_or_holdout_identity_forbidden")
    h1_provenance, h2_provenance = _valid_source_provenance(bundle.get("source_provenance"), findings)

    if selection_goal == "SELECTION":
        firewall = _mapping(bundle.get("source_firewall_receipt"))
        if (
            not _text(firewall.get("receipt_id"))
            or not _text(firewall.get("researcher_id"))
            or _instant(firewall.get("attested_at")) is None
            or firewall.get("researcher_outcome_body_access") != "NONE"
            or firewall.get("researcher_outcome_metadata_access") != "NONE"
            or firewall.get("outcome_access_authorized") is not False
        ):
            _add(findings, "firewall_preoutcome_outcome_access_not_sealed")

        review = _mapping(bundle.get("independent_pre_outcome_review"))
        reviewer_id = review.get("reviewer_id")
        designer_id = review.get("pre_outcome_designer_id")
        reviewed_at = _instant(review.get("reviewed_at"))
        if (
            not _text(review.get("review_id"))
            or not _text(designer_id)
            or not _text(reviewer_id)
            or reviewed_at is None
        ):
            _add(findings, "review_identity_or_time_invalid")
        if review.get("verdict") != "ACCEPTED":
            _add(findings, "review_not_accepted")
        if (
            review.get("reviewer_outcome_body_access") != "NONE"
            or review.get("reviewer_outcome_metadata_access") != "NONE"
        ):
            _add(findings, "reviewer_preoutcome_outcome_access_not_sealed")
        if _text(designer_id) and designer_id != firewall.get("researcher_id"):
            _add(findings, "review_designer_firewall_identity_mismatch")
        if _text(reviewer_id) and reviewer_id == designer_id:
            _add(findings, "reviewer_not_independent_from_researcher")
        if reviewed_at is not None and sealed_at is not None and reviewed_at > sealed_at:
            _add(findings, "review_after_selection_freeze")
        firewall_attested_at = _instant(firewall.get("attested_at"))
        if firewall_attested_at is not None and reviewed_at is not None and firewall_attested_at > reviewed_at:
            _add(findings, "firewall_attested_after_review")

        reviewed_selection_contract = review.get("reviewed_selection_contract")
        expected_reviewed_selection_contract = {
            field: bundle.get(field)
            for field in (
                "schema_version", "candidate_id", "method_epoch_id", "selection_goal", "selection_freeze_id",
                "episode_collision_key", "sealed_at", "recorded_at", "cohort_snapshot", "action_scope",
                "scope_bridges", "competitive_arena", "external_driver_reference", "counterfactual_panel",
                "measurement_contracts", "time_contract", "outcome_contract", "materiality_and_resolution_contract",
                "source_manifest", "source_provenance", "source_firewall_receipt",
            )
        }
        if reviewed_selection_contract != expected_reviewed_selection_contract:
            _add(findings, "review_binding_does_not_match_selection_freeze")

    time_contract = _mapping(bundle.get("time_contract"))
    cutoff = _instant(time_contract.get("research_cutoff_at"))
    cohort_time = _instant(time_contract.get("cohort_eligibility_as_of"))
    if cutoff is None:
        _add(findings, "time_research_cutoff_invalid")
    if cohort_time is None:
        _add(findings, "time_cohort_eligibility_invalid")

    h1_selection_as_of = _instant(h1_provenance.get("selection_as_of"))
    if cohort_time is not None and h1_selection_as_of is not None and h1_selection_as_of != cohort_time:
        _add(findings, "source_provenance_h1_cohort_time_mismatch")
    if cutoff is not None and _instant(h2_provenance.get("cutoff_at")) is not None \
            and _instant(h2_provenance.get("cutoff_at")) != cutoff:
        _add(findings, "source_provenance_h2_cutoff_mismatch")

    sources = [_mapping(source) for source in _items(bundle.get("source_manifest"))]
    source_by_id: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_id = source.get("source_id")
        if not _text(source_id) or source_id in source_by_id:
            _add(findings, "source_identity_missing_or_duplicate")
            continue
        source_by_id[source_id] = source
        if any(not _text(source.get(field)) for field in _STATIC_SOURCE_IDENTITY_TEXT_FIELDS):
            _add(findings, "source_static_identity_missing")
        if source.get("source_lane") not in SOURCE_LANES:
            _add(findings, "source_lane_invalid")
        if source.get("source_lane") == "OUTCOME_SEALED" or source.get("outcome_visibility") == "SEALED":
            _add(findings, "isolation_outcome_source_identity_leak")
        if cutoff is not None and not _source_is_before(source, cutoff):
            _add(findings, "source_not_cutoff_before")
    if not source_by_id:
        _add(findings, "source_manifest_missing")

    cohort = _mapping(bundle.get("cohort_snapshot"))
    if _stage0_has_forbidden_key(cohort):
        _add(findings, "stage0_action_or_outcome_contaminated")
    if _stage0_has_unapproved_shape(cohort):
        _add(findings, "stage0_information_set_not_closed")
    members = [_mapping(member) for member in _items(cohort.get("members"))]
    issuer_ids = [member.get("issuer_id") for member in members if _text(member.get("issuer_id"))]
    control_group_ids = [member.get("control_group_id") for member in members if _text(member.get("control_group_id"))]
    if len(members) < 3 or len(set(issuer_ids)) < 3 or len(set(control_group_ids)) < 3:
        _add(findings, "stage0_independent_three_issuer_capacity_not_met")
    cohort_declared_time = _instant(cohort.get("cohort_eligibility_as_of"))
    if cohort_time is None or cohort_declared_time is None or cohort_declared_time != cohort_time:
        _add(findings, "stage0_cohort_time_identity_invalid")
    if _text(h1_provenance.get("cohort_id")) and h1_provenance.get("cohort_id") != cohort.get("cohort_snapshot_id"):
        _add(findings, "source_provenance_h1_cohort_snapshot_mismatch")
    for member in members:
        if any(not _text(member.get(field)) for field in (
            "company_id", "issuer_id", "responsibility_unit_id", "control_group_id",
        )):
            _add(findings, "stage0_member_identity_missing")
        boundary = _mapping(member.get("boundary"))
        if (
            set(boundary) != _STAGE0_MEMBER_BOUNDARY_KEYS
            or any(not _text(boundary.get(field)) for field in _STAGE0_MEMBER_BOUNDARY_KEYS)
            or boundary.get("responsibility_unit_id") != member.get("responsibility_unit_id")
        ):
            _add(findings, "stage0_member_boundary_invalid")
        carrier_sources = member.get("carrier_identity_source_ids")
        _all_references_known(carrier_sources, source_by_id, findings, "stage0_carrier")
        _source_has_lane(carrier_sources, source_by_id, "STAGE0_STATIC", findings, "stage0_carrier")
        d2_history = _items(member.get("d2_or_cost_field_history"))
        d3_d4_history = _items(member.get("d3_d4_field_history"))
        if len(d2_history) < 3:
            _add(findings, "stage0_three_d2_or_cost_field_identities_missing")
        if len(d3_d4_history) < 5:
            _add(findings, "stage0_five_d3_d4_field_identities_missing")
        for record in d2_history + d3_d4_history:
            source_id = _mapping(record).get("source_id")
            if source_id not in source_by_id:
                _add(findings, "stage0_field_source_not_in_manifest")
            elif source_by_id[source_id].get("source_lane") != "STAGE0_STATIC":
                _add(findings, "stage0_field_source_lane_invalid")
            elif cohort_time is not None and not _source_is_before(source_by_id[source_id], cohort_time):
                _add(findings, "stage0_field_source_not_cohort_before")

    action = _mapping(bundle.get("action_scope"))
    topology = action.get("mechanism_topology")
    if topology not in SUPPORTED_TOPOLOGIES:
        _add(findings, "action_topology_not_supported")
    if action.get("implementation_status") != "IMPLEMENTED":
        _add(findings, "action_not_implemented")
    if action.get("decision_authority") not in {
        "ISSUER_MANAGEMENT", "ISSUER_BOARD", "REPORTABLE_SEGMENT_MANAGEMENT",
    }:
        _add(findings, "action_decision_authority_invalid")
    if not _text(action.get("action_id")) or not _text(action.get("focal_issuer_id")):
        _add(findings, "action_identity_missing")
    if action.get("focal_issuer_id") not in issuer_ids:
        _add(findings, "action_focal_issuer_not_in_stage0")
    _all_references_known(action.get("source_ids"), source_by_id, findings, "action")
    _source_has_lane(action.get("source_ids"), source_by_id, "ACTION_STATIC", findings, "action")
    carriers = [_mapping(carrier) for carrier in _items(action.get("economic_carriers"))]
    carrier_ids = {carrier.get("carrier_id") for carrier in carriers if _text(carrier.get("carrier_id"))}
    if not carrier_ids:
        _add(findings, "action_economic_carrier_missing")
    for carrier in carriers:
        if not _text(carrier.get("functional_type")) or not _text(carrier.get("legal_or_operating_owner")):
            _add(findings, "action_carrier_identity_invalid")
        _all_references_known(carrier.get("implementation_source_ids"), source_by_id, findings, "action_carrier")
        _source_has_lane(carrier.get("implementation_source_ids"), source_by_id, "ACTION_STATIC", findings, "action_carrier")

    d2_role = action.get("d2_role")
    if topology == "CUSTOMER_RESPONSE":
        if d2_role != "CENTRAL_VOTER" or len(_items(action.get("d2_observations"))) < 3:
            _add(findings, "action_customer_d2_central_observability_missing")
    elif topology == "COST_RESTRUCTURING":
        if d2_role not in {"CENTRAL_VOTER", "DIAGNOSTIC_NON_VOTER"}:
            _add(findings, "action_cost_d2_role_invalid")
        elif d2_role == "CENTRAL_VOTER" and len(_items(action.get("d2_observations"))) < 3:
            _add(findings, "action_customer_d2_central_observability_missing")
        elif d2_role == "DIAGNOSTIC_NON_VOTER" and len(_items(action.get("cost_driver_observations"))) < 3:
            _add(findings, "action_cost_driver_observability_missing")

    h_a = _mapping(action.get("h_a"))
    h_b = _mapping(action.get("h_b"))
    a_predictions = _mapping(h_a.get("central_endpoint_predictions"))
    b_predictions = _mapping(h_b.get("central_endpoint_predictions"))
    if not _text(h_a.get("hypothesis_id")) or not _text(h_b.get("hypothesis_id")) or h_a.get("hypothesis_id") == h_b.get("hypothesis_id"):
        _add(findings, "action_hypothesis_identity_invalid")
    if not _text(a_predictions.get("D3")) or not _text(a_predictions.get("D4")) or not _text(b_predictions.get("D3")) or not _text(b_predictions.get("D4")):
        _add(findings, "action_hypothesis_central_endpoint_missing")
    elif a_predictions.get("D3") == b_predictions.get("D3") and a_predictions.get("D4") == b_predictions.get("D4"):
        _add(findings, "action_hypotheses_do_not_diverge")

    action_window = _mapping(action.get("action_effective_window"))
    action_start = _instant(action_window.get("start"))
    decision_at = _instant(action.get("decision_observable_at"))
    if action_start is None or not _text(action_window.get("end_or_ongoing_status")):
        _add(findings, "time_action_effective_window_invalid")
    if decision_at is None:
        _add(findings, "time_decision_observable_invalid")

    bridges = [_mapping(bridge) for bridge in _items(bundle.get("scope_bridges"))]
    bridge_by_id = {
        bridge.get("scope_bridge_id"): bridge
        for bridge in bridges
        if _text(bridge.get("scope_bridge_id"))
    }
    if len(bridge_by_id) != len(bridges):
        _add(findings, "bridge_identity_missing_or_duplicate")
    for bridge in bridges:
        bridge_type = bridge.get("bridge_type")
        if bridge_type not in BRIDGE_TYPES:
            _add(findings, "bridge_type_invalid")
            continue
        _all_references_known(bridge.get("decision_to_carrier_source_ids"), source_by_id, findings, "bridge")
        _all_references_known(bridge.get("carrier_to_perimeter_source_ids"), source_by_id, findings, "bridge")
        if not _source_ids(bridge.get("decision_to_carrier_source_ids")) or not _source_ids(bridge.get("carrier_to_perimeter_source_ids")):
            _add(findings, "bridge_evidence_source_missing")
        rights = bridge.get("economic_rights_type")
        if rights in {"EQUITY_METHOD", "UNCONSOLIDATED"}:
            _add(findings, "bridge_economic_rights_not_eligible")
        if rights == "CONSOLIDATED_WITH_NCI" and not _text(bridge.get("nci_treatment")):
            _add(findings, "bridge_nci_treatment_missing")
        carrier_perimeters = _source_ids(bridge.get("carrier_perimeter_ids"))
        metric_perimeters = _source_ids(bridge.get("metric_perimeter_ids"))
        if bridge_type == "IDENTITY":
            if (
                carrier_perimeters != metric_perimeters
                or bridge.get("coverage_basis") != "NOT_APPLICABLE_FULL_PERIMETER"
                or bridge.get("implementation_scope") != "FULL_METRIC_PERIMETER"
                or not _text(bridge.get("carrier_reporting_basis"))
                or bridge.get("carrier_reporting_basis") != bridge.get("metric_reporting_basis")
            ):
                _add(findings, "bridge_identity_perimeter_or_coverage_invalid")
            if any(bridge.get(field) is not None for field in ("coverage_numerator", "coverage_denominator")):
                _add(findings, "bridge_identity_must_not_fake_coverage")
        elif bridge_type == "SEGMENT_MATCH":
            if (
                carrier_perimeters != metric_perimeters
                or not _text(bridge.get("formal_segment_id"))
                or not _text(bridge.get("segment_continuity_policy"))
            ):
                _add(findings, "bridge_segment_match_identity_or_continuity_invalid")
        else:
            if (
                not _text(bridge.get("coverage_basis"))
                or bridge.get("coverage_basis") == "NOT_APPLICABLE_FULL_PERIMETER"
                or not _text(bridge.get("mechanism_channel"))
                or bridge.get("mechanism_channel") != bridge.get("coverage_channel")
            ):
                _add(findings, "bridge_aggregation_coverage_basis_missing")
            numerator = _mapping(bridge.get("coverage_numerator"))
            denominator = _mapping(bridge.get("coverage_denominator"))
            if (
                not _finite(numerator.get("value"))
                or not _finite(denominator.get("value"))
                or denominator.get("value", 0) <= 0
                or numerator.get("unit") != denominator.get("unit")
                or numerator.get("period_end") != denominator.get("period_end")
                or not _text(bridge.get("coverage_as_of"))
                or numerator.get("source_id") not in source_by_id
                or denominator.get("source_id") not in source_by_id
                or not isinstance(bridge.get("known_omitted_material_items"), list)
                or not isinstance(bridge.get("known_other_material_changes"), list)
            ):
                _add(findings, "bridge_aggregation_quantification_invalid")
        if not _text(bridge.get("action_cash_boundary")) or not _text(bridge.get("permitted_conclusion_scope")):
            _add(findings, "bridge_conclusion_or_cash_boundary_missing")

    arena = _mapping(bundle.get("competitive_arena"))
    arena_type = arena.get("market_scope_type")
    if arena_type not in ARENA_SCOPE_TYPES:
        _add(findings, "arena_market_scope_type_invalid")
    arena_dimensions = _valid_dimension_list(
        arena.get("required_overlap_dimensions"),
        source_by_id,
        findings,
        "arena",
        require_peer_evidence=selection_goal == "SELECTION",
    )
    if arena_type == "REGIONAL" and not any(
        dimension.get("dimension") == "GEOGRAPHIC_MARKET" and dimension.get("relation") == "REQUIRED_OVERLAP"
        for dimension in arena_dimensions
    ):
        _add(findings, "arena_regional_geographic_overlap_missing")
    if arena_type == "MULTI_REGION_PORTFOLIO" and not (
        _text(arena.get("dominant_subarena_id")) or _items(arena.get("material_subarena_ids"))
    ):
        _add(findings, "arena_multi_region_subarena_binding_missing")
    if selection_goal == "SELECTION":
        external_driver = _mapping(bundle.get("external_driver_reference"))
        if not _text(external_driver.get("external_driver_reference_id")) or not _text(external_driver.get("driver_description")):
            _add(findings, "arena_external_driver_identity_missing")
        _valid_dimension_list(
            external_driver.get("required_exposure_dimensions"),
            source_by_id,
            findings,
            "driver",
            require_peer_evidence=True,
        )
        _all_references_known(external_driver.get("target_driver_exposure_source_ids"), source_by_id, findings, "driver")

        panel = _mapping(bundle.get("counterfactual_panel"))
        if panel.get("target_issuer_id") != action.get("focal_issuer_id"):
            _add(findings, "panel_target_identity_invalid")
        if not _text(panel.get("non_replacement_rule")):
            _add(findings, "panel_non_replacement_rule_missing")
        panel_members = [_mapping(member) for member in _items(panel.get("members"))]
        comparator_count = 0
        panel_issuer_ids: set[str] = set()
        panel_groups: set[str] = set()
        cohort_by_issuer = {member.get("issuer_id"): member for member in members}
        target_group = _mapping(cohort_by_issuer.get(action.get("focal_issuer_id"))).get("control_group_id")
        for member in panel_members:
            issuer = member.get("issuer_id")
            group = member.get("control_group_id")
            role = member.get("causal_role")
            if role not in PANEL_ROLES or not _text(issuer) or not _text(group):
                _add(findings, "panel_member_identity_or_role_invalid")
                continue
            if issuer == action.get("focal_issuer_id") or issuer not in cohort_by_issuer or issuer in panel_issuer_ids or group in panel_groups or group == target_group:
                _add(findings, "panel_member_not_independent_stage0_peer")
            panel_issuer_ids.add(issuer)
            panel_groups.add(group)
            _all_references_known(member.get("source_ids"), source_by_id, findings, "panel")
            if role == "EXTERNAL_SHOCK_COMPARATOR":
                comparator_count += 1
                if (
                    member.get("eligible_for_relative_baseline") is not True
                    or member.get("shared_driver_exposure") != "PROVEN"
                    or member.get("parallel_action") != "BOUNDED_ABSENT"
                    or member.get("target_action_spillover") != "BOUNDED_NONINTERFERENCE"
                    or not _membership_is_proven(member.get("external_driver_reference_membership"), source_by_id)
                ):
                    _add(findings, "panel_comparator_external_driver_or_noninterference_invalid")
            elif role == "EQUILIBRIUM_RESPONSE_WITNESS":
                if member.get("eligible_for_relative_baseline") is not False or not _membership_is_proven(member.get("mechanism_arena_membership"), source_by_id):
                    _add(findings, "panel_witness_membership_or_baseline_invalid")
            elif role == "FALSIFIER" and member.get("eligible_for_relative_baseline") is not False:
                _add(findings, "panel_falsifier_must_not_enter_baseline")
        if comparator_count < 2 or comparator_count > 7:
            _add(findings, "panel_two_to_seven_external_comparators_required")

    metrics = [_mapping(metric) for metric in _items(bundle.get("measurement_contracts"))]
    metrics_by_clock = {metric.get("clock"): metric for metric in metrics if metric.get("clock") in {"D3", "D4"}}
    if selection_goal == "SELECTION":
        if len(metrics) != 2 or set(metrics_by_clock) != {"D3", "D4"}:
            _add(findings, "metric_exactly_one_d3_and_one_d4_required")
    elif selection_goal == "TEACHING_ONLY":
        if len(metrics) != 1 or set(metrics_by_clock) != {"D3"}:
            _add(findings, "metric_teaching_only_requires_d3_without_d4")

    for clock, metric in metrics_by_clock.items():
        bridge = bridge_by_id.get(metric.get("scope_bridge_id"))
        if bridge is None:
            _add(findings, "metric_scope_bridge_missing")
            continue
        if metric.get("accounting_perimeter_id") not in _source_ids(bridge.get("metric_perimeter_ids")):
            _add(findings, "metric_accounting_perimeter_not_in_bridge")
        if metric.get("carrier_or_segment_id") not in carrier_ids:
            _add(findings, "metric_carrier_not_in_action_scope")
        if metric.get("allowed_conclusion_scope") != bridge.get("permitted_conclusion_scope"):
            _add(findings, "metric_conclusion_scope_not_bridge_bound")
        if not _text(metric.get("currency_and_unit")) or metric.get("period_basis") not in {"FISCAL_YEAR", "QUARTER", "TRAILING_PERIOD"}:
            _add(findings, "metric_unit_or_period_basis_invalid")
        if not _text(metric.get("gross_or_net_definition")) or not _text(metric.get("restatement_or_reclassification_policy")):
            _add(findings, "metric_identity_policy_missing")
        if not isinstance(metric.get("baseline_observation_matrix"), dict) or not isinstance(metric.get("primary_outcome_matrix"), dict):
            _add(findings, "metric_observation_matrix_missing")
        if not _text(metric.get("source_available_at_policy")):
            _add(findings, "metric_source_availability_policy_missing")
        if (
            not _text(metric.get("baseline_period_id"))
            or not _text(metric.get("primary_outcome_period_id"))
            or metric.get("baseline_period_id") == metric.get("primary_outcome_period_id")
        ):
            _add(findings, f"metric_{clock.lower()}_baseline_or_primary_period_invalid")
        discriminability = _mapping(metric.get("discriminability"))
        if selection_goal == "SELECTION" and (
            discriminability.get("status") != "SUPPORTED"
            or not _valid_threshold(
                discriminability.get("primary_threshold"), operator="GTE", unit=metric.get("currency_and_unit"),
            )
            or not _valid_threshold(
                discriminability.get("rival_threshold"), operator="LTE", unit=metric.get("currency_and_unit"),
            )
        ):
            _add(findings, f"metric_{clock.lower()}_discriminability_invalid")
        if clock == "D3":
            if (
                metric.get("economic_construct") not in ALLOWED_D3_CONSTRUCTS
                or not _items(metric.get("formula_and_ordered_raw_fields"))
                or not _valid_d3_outcome_formula(metric)
            ):
                _add(findings, "metric_d3_identity_invalid")
        else:
            raw_fields = tuple(metric.get("formula_and_ordered_raw_fields", []))
            if metric.get("economic_construct") != "CONSERVATIVE_OWNER_CASH" or metric.get("formula_id") != D4_FORMULA_ID:
                _add(findings, "metric_d4_formula_invalid")
            treatment = metric.get("restructuring_cash_treatment")
            expected_raw_fields = D4_REQUIRED_RAW_FIELDS
            if treatment == "SEPARATE_OPERATING_CASH_DEDUCTION":
                expected_raw_fields = D4_REQUIRED_RAW_FIELDS + (D4_RESTRUCTURING_CASH_FIELD,)
            if raw_fields != expected_raw_fields or _metric_raw_locator_ids(metric) != set(expected_raw_fields):
                _add(findings, "metric_d4_raw_field_identity_invalid")
            if set(_items(metric.get("cash_working_capital_components"))) != D4_CASH_WORKING_CAPITAL_COMPONENTS:
                _add(findings, "metric_d4_cash_working_capital_boundary_invalid")
            if treatment not in D4_RESTRUCTURING_TREATMENTS:
                _add(findings, "metric_d4_restructuring_cash_treatment_invalid")
            elif treatment == "OUT_OF_PERIMETER_CANNOT_SETTLE" and selection_goal == "SELECTION":
                _add(findings, "metric_d4_out_of_perimeter_restructuring_not_settleable")
            if bridge.get("economic_rights_type") == "CONSOLIDATED_WITH_NCI" and not _text(metric.get("nci_treatment")):
                _add(findings, "metric_d4_nci_treatment_missing")

    declared_action_window = _mapping(time_contract.get("action_effective_window"))
    declared_action_start = _instant(declared_action_window.get("start"))
    declared_decision = _instant(time_contract.get("decision_observable_at"))
    if declared_action_start != action_start or declared_decision != decision_at:
        _add(findings, "time_action_scope_identity_mismatch")
    if cutoff is not None and action_start is not None and decision_at is not None:
        if cohort_time is None or not (cohort_time < action_start and cohort_time < decision_at):
            _add(findings, "time_cohort_not_before_action_and_decision")
        if action_start > cutoff or decision_at > cutoff:
            _add(findings, "time_action_or_decision_not_cutoff_before")
    metric_periods = _mapping(time_contract.get("metric_economic_periods"))
    for clock in ("D3", "D4"):
        if clock not in metrics_by_clock:
            continue
        period = _mapping(metric_periods.get(clock))
        period_start = _instant(period.get("start"))
        period_end = _instant(period.get("end"))
        if period_start is None or period_end is None or period_start >= period_end or action_start is None or period_start <= action_start:
            _add(findings, f"time_{clock.lower()}_economic_period_invalid")
    if not _text(time_contract.get("outcome_window_id")):
        _add(findings, "time_outcome_window_id_missing")
    if selection_goal == "SELECTION":
        panel_for_outcome = _mapping(bundle.get("counterfactual_panel"))
        _validate_outcome_contract(
            bundle.get("outcome_contract"),
            target_issuer_id=panel_for_outcome.get("target_issuer_id"),
            panel_members=[_mapping(member) for member in _items(panel_for_outcome.get("members"))],
            metrics_by_clock=metrics_by_clock,
            metric_periods=metric_periods,
            findings=findings,
        )

    materiality = _mapping(bundle.get("materiality_and_resolution_contract"))
    decision_materiality = _mapping(materiality.get("decision_materiality"))
    if decision_materiality.get("status") != "SUPPORTED" or not _source_ids(decision_materiality.get("evidence_source_ids")):
        _add(findings, "materiality_decision_not_supported")
    _all_references_known(decision_materiality.get("evidence_source_ids"), source_by_id, findings, "materiality_decision")
    materiality_keys = ["d3_outcome_discriminability"]
    if selection_goal == "SELECTION":
        materiality_keys.append("d4_outcome_discriminability")
    for clock_key in materiality_keys:
        contract = _mapping(materiality.get(clock_key))
        clock = "D3" if clock_key.startswith("d3_") else "D4"
        metric = metrics_by_clock.get(clock, {})
        if (
            contract.get("status") != "SUPPORTED"
            or not _valid_threshold(
                contract.get("primary_threshold"), operator="GTE", unit=metric.get("currency_and_unit"),
            )
            or not _valid_threshold(
                contract.get("rival_threshold"), operator="LTE", unit=metric.get("currency_and_unit"),
            )
        ):
            _add(findings, f"materiality_{clock_key}_invalid")
    if _mapping(materiality.get("investor_materiality")).get("status") not in {"SUPPORTED", "UNKNOWN", "REFUTED"}:
        _add(findings, "materiality_investor_status_invalid")

    admission_status = _status(findings, selection_goal)
    return {
        "valid": admission_status == SELECTION_ADMITTED,
        "admission_status": admission_status,
        "findings": findings,
    }
