#!/usr/bin/env python3
"""Triage cutoff-only source manifests before expensive V4 acquisition.

This is deliberately *not* a selection candidate validator, episode
register, outcome reader, or feedback engine.  A curator supplies only the
cutoff-before sources that establish four early questions:

1. Is there an already implemented, commercially meaningful action on the
   candidate's common issuer boundary?
2. Is independent, non-mechanical D2 observable three times before cutoff?
3. Is there a selected H-A and a still-live, distinct H-B?
4. Has result access remained sealed and has every supplied source stayed
   cutoff-before?

The legacy ``DISCOVERY_READY`` predicate is retained only for historical
fixtures and isolated compatibility tests.  It is not a real candidate-entry
API: current admission derives its internal predicate only from a valid H1
static cohort receipt plus one closed H2 action-screen extension.

Manifest interface (JSON object):

* ``schema_version``: ``judgment-selection-discovery-manifest.v1``
* ``manifest_id``, ``cutoff_at`` and ``candidate_identity`` with
  ``company_id``, ``issuer_id``, ``responsibility_unit_id``, ``industry_id``
  and a V4-shaped ``common_boundary``.
* ``cohort_feasibility_record``: a cutoff-before industry universe of at
  least five control-independent issuers with source-bearing D2 and D3/D4
  availability identities.  It must exist before the selected action.
* ``action``: common-boundary ``IMPLEMENTED_OR_IRREVOCABLY_INCURRED`` action,
  official implementation/exposure evidence, and one permitted exposure kind.
* ``d2_observability``: a common-boundary, official, non-mechanical D2 field
  with three distinct cutoff-before repetitions.
* ``cutoff_before_facts`` and ``hypothesis_pair``: official, source-bearing
  facts are explicitly assigned to a selected primary and a live strongest
  rival; the pair also carries an explicit pre-outcome selection basis.
* ``source_firewall``: outcome body and metadata remain unread/prohibited,
  and the curator records the one currently verified PIT-safe discovery entry
  route.  CNINFO fulltext lookups, including non-issuer industry keywords,
  are not safe: the page can render a current price or latest-announcement
  card before its date filter applies.

The evidence object deliberately reuses the V4 candidate helper's official,
issuer, perimeter, responsibility-unit, unit, and cutoff checks.  Do not add
five-year D3/D4, peer, materiality, or outcome fields here; those belong to
the existing V4 candidate and outcome contracts after this triage passes.

The public CLI accepts only the H1 static-PDF cohort intake package and never
falls back to the legacy V4 standalone cohort result.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

try:  # Works both as ``python scripts/...`` and as ``from scripts import ...``.
    from scripts import judgment_selection_candidate as candidate_contract
except ModuleNotFoundError:  # pragma: no cover - direct-script import path
    import judgment_selection_candidate as candidate_contract


MANIFEST_SCHEMA_VERSION = "judgment-selection-discovery-manifest.v1"
RESULT_SCHEMA_VERSION = "judgment-selection-discovery-triage-result.v1"
DISCOVERY_READY = "DISCOVERY_READY"
NO_PRIMARY = "NO_PRIMARY"
FEASIBLE_FOR_V4_FINAL_PANEL = "FEASIBLE_FOR_V4_FINAL_PANEL"

ACTION_SCOPE = "CANDIDATE_COMMON_BOUNDARY"
COMMERCIAL_ACTION = "COMMERCIAL_COMPETITIVE_DECISION"
FACT_SCOPE_CANDIDATE = "CANDIDATE_COMMON_BOUNDARY"
FACT_SCOPE_D2 = "D2_COMMON_RESPONSIBILITY_PERIMETER"
FACT_SCOPE_COST = "COST_COMMON_RESPONSIBILITY_PERIMETER"
ACTION_KINDS = set(candidate_contract.V4_ACTION_EXPOSURE_KINDS)
ACTUAL_BASES = {"ACTUAL_CASH_PAID", "RECOGNIZED_ASSET"}
D2_KINDS = set(candidate_contract.V4_DIRECT_CUSTOMER_OBSERVATION_KINDS)

# This is deliberately an *entry* contract rather than a generic web-policy.
# Other research tasks may legitimately navigate issuer pages.  Historical PIT
# selection discovery cannot, because CNINFO's issuer/fulltext surfaces — now
# including nominally non-issuer industry keywords — can disclose current
# metadata before filtering the requested historic window.
KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF = "KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF"
PIT_SAFE_DISCOVERY_ENTRY_KINDS = {
    KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF,
}
POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY = "PREDECLARED_CUTOFF_BEFORE_STATIC_CNINFO_PDF_PACKAGE_ONLY"

# H1 has a narrower input than the legacy V4 observability record.  It is an
# offline curator hand-off, not a second V5 selection bundle: no action,
# target, final panel, outcome, or database state is permitted here.
STAGE0_STATIC_PACKAGE_SCHEMA_VERSION = "judgment-selection-stage0-static-package.v1"
STAGE0_STATIC_RESULT_SCHEMA_VERSION = "judgment-selection-stage0-static-result.v1"
CURATOR_SUPPLIED_STATIC_PDF_PACKAGE = "CURATOR_SUPPLIED_CUTOFF_BEFORE_STATIC_CNINFO_PDF_PACKAGE"
FEASIBLE_FOR_V5_FINAL_PANEL = "FEASIBLE_FOR_V5_FINAL_PANEL"
FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE = "FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE"
STAGE0_FEASIBILITY_REVIEWABLE = "STAGE0_FEASIBILITY_REVIEWABLE"
INSUFFICIENT_STATIC_SOURCE_PACKAGE = "INSUFFICIENT_STATIC_SOURCE_PACKAGE"
STAGE0_REJECTED = "STAGE0_REJECTED"
STAGE0_ARENA_SCOPE_TYPES = {"NATIONAL", "REGIONAL", "EXPORT", "SEGMENT", "MULTI_REGION_PORTFOLIO"}
STAGE0_MECHANISM_TOPOLOGIES = {"CUSTOMER_RESPONSE", "COST_RESTRUCTURING"}
STAGE0_COST_DRIVER_KINDS = {
    "ENERGY_INPUT_COST", "LABOR_COST", "LOGISTICS_COST", "FIXED_COST", "UNIT_OPERATING_COST", "UTILIZATION",
}
_STAGE0_FORBIDDEN_KEYS = {
    "action", "action_id", "action_title", "focal_target", "focal_issuer", "focal_issuer_id",
    "target", "target_issuer", "target_issuer_id", "final_peer", "final_peer_panel",
    "final_peer_role", "common_driver", "outcome", "outcome_value", "outcome_source", "winner",
}
_PAGE_REFERENCE = re.compile(r"(?:\bp(?:age)?\.?\s*\d+|第\s*\d+\s*页)", re.IGNORECASE)
_STAGE0_PACKAGE_KEYS = {
    "schema_version", "entry_kind", "cohort_id", "industry_id", "selection_as_of", "mechanism_topology",
    "cohort_eligibility_as_of", "arena_family", "current_admission_assessment",
    "curator_attestation", "universe", "competitive_arena", "static_pdf_sources", "members",
}
_STAGE0_ASSESSMENT_KEYS = {"status", "reason"}
_STAGE0_ATTESTATION_KEYS = {
    "curator_id", "issuer_code_or_name_submitted_to_cninfo_fulltext", "cninfo_issuer_stock_or_detail_page_opened",
    "post_identification_access", "post_cutoff_metadata_or_body_read",
}
_STAGE0_UNIVERSE_KEYS = {
    "universe_id", "membership_rule", "cohort_scope", "not_final_peer_universe", "listed_company_ids",
}
_STAGE0_MEMBER_KEYS = {
    "company_id", "issuer_id", "responsibility_unit_id", "control_group_id", "industry_id", "boundary",
    "industry_business_evidence", "control_group_evidence", "final_peer_panel_disposition",
    "final_peer_panel_rationale", "comparability_break_evidence", "d2_field_availability", "annual_d3_d4_availability",
    "cost_field_availability", "competitive_arena_id", "carrier_identity_source_ids",
}
_STAGE0_BOUNDARY_KEYS = {"responsibility_unit_id", "perimeter_id", "unit"}
_STAGE0_EVIDENCE_KEYS = {
    "source_id", "source_type", "issuer_id", "perimeter_id", "responsibility_unit_id", "unit",
    "published_at", "field_ref", "observed_control_group_id",
}
_STAGE0_D2_KEYS = {"field_id", "definition", "repetitions"}
_STAGE0_COST_KEYS = {"field_id", "cost_driver_kind", "definition", "repetitions"}
_STAGE0_REPETITION_KEYS = {"period_end", "evidence"}
_STAGE0_ANNUAL_KEYS = {"period_end", "evidence"}
_STAGE0_ARENA_KEYS = {
    "competitive_arena_id", "market_scope_type", "product_or_service_scope", "geographic_scope",
    "customer_end_market_scope", "evidence",
}
_STAGE0_STATIC_SOURCE_KEYS = {
    "source_id", "url", "published_at", "source_type", "period_end", "field_refs", "issuer_id",
    "responsibility_unit_id", "perimeter_id", "unit",
}

# H2 is deliberately a closed action-screen hand-off.  H1 names a feasible
# arena without an action.  H2 may add only the curator's predeclared static
# PDFs needed to decide one member's action screen; it cannot append another
# member, route through a live page, or carry outcome material.
ACTION_SCREEN_STATIC_EXTENSION_SCHEMA_VERSION = "judgment-selection-action-screen-static-extension.v1"
ACTION_SCREEN_STATIC_RESULT_SCHEMA_VERSION = "judgment-selection-action-screen-static-result.v1"
ACTION_SCREEN_REVIEWABLE = "ACTION_SCREEN_REVIEWABLE"
ACTION_SCREEN_REJECTED = "ACTION_SCREEN_REJECTED"
_H2_EXTENSION_KEYS = {
    "schema_version", "screen_id", "stage0_cohort_id", "stage0_selection_as_of", "curator_id",
    "cutoff_at", "mechanism_topology", "candidate_identity", "static_pdf_sources",
    "source_firewall_attestation", "action", "cutoff_before_facts", "hypothesis_pair",
    "d2_observability", "cost_driver_observability",
}
_H2_CANDIDATE_IDENTITY_KEYS = {
    "company_id", "issuer_id", "responsibility_unit_id", "industry_id", "common_boundary",
}
_H2_SOURCE_FIREWALL_KEYS = {
    "outcome_body_access", "outcome_metadata_access", "post_cutoff_sources_prohibited",
}
_H2_STATIC_SOURCE_KEYS = {
    "source_id", "url", "published_at", "source_type", "field_refs", "issuer_id",
    "responsibility_unit_id", "perimeter_id", "unit",
}
_H2_ACTION_KEYS = {
    "action_id", "action_statement", "action_scope", "economic_character", "economic_action_type",
    "action_state", "implemented_or_incurred_at", "boundary", "issuer_scope_bridge",
    "decision_specificity", "explicitly_immaterial", "implementation_evidence", "exposure",
}
_H2_ACTION_SCOPE_BRIDGE_KEYS = {
    "outcome_scope", "action_scope_relation", "issuer_level_mechanism_only", "evidence",
}
_H2_DECISION_SPECIFICITY_KEYS = {
    "decision_class", "incremental_to_maintenance_or_mandated_baseline", "evidence",
}
_H2_ACTION_EXPOSURE_KEYS = {
    "kind", "actual_basis", "evidence", "implemented_net_price_delta_field_ref",
    "preaction_actual_units_field_ref",
}
_H2_FACT_KEYS = {"fact_id", "statement", "evidence_scope", "evidence"}
_H2_HYPOTHESIS_PAIR_KEYS = {"decisive_question", "primary", "strongest_rival", "selection_basis"}
_H2_HYPOTHESIS_KEYS = {"hypothesis_id", "mechanism", "pre_outcome_rationale", "supporting_fact_ids", "live_before_cutoff"}
_H2_SELECTION_BASIS_KEYS = {"directional_preference", "why_not_common", "why_rival_remains_live"}
_H2_D2_KEYS = {
    "primary_hypothesis_id", "observation_kind", "not_mechanically_changed_by_action", "boundary",
    "field_id", "repetitions",
}
_H2_COST_KEYS = {"primary_hypothesis_id", "observation_kind", "boundary", "field_id", "repetitions"}
_H2_REPETITION_KEYS = {"period_end", "field_ref", "evidence"}
_H2_EVIDENCE_KEYS = {
    "source_id", "source_type", "issuer_id", "perimeter_id", "responsibility_unit_id", "unit",
    "published_at", "field_ref",
}

NEXT_V4_ACQUISITION_PACKAGE = (
    "target_five_pre_action_annual_raw_d3_d4",
    "target_d3_and_d4_independent_scaled_mad_anchors",
    "fixed_three_to_seven_non_common-control-peer_panel_with_three_annual_raw_d3_d4_each",
    "peer_universe_exclusions_order_and_no_replacement_contract",
    "target_and_peer_control_group_official_source_package",
    "target_and_peer_structural_comparability_registers",
    "complete_d4_cash_bridge_coverage",
    "pre_outcome_candidate_source_measurement_and_outcome_firewall_contracts",
)

DOES_NOT_GRANT = (
    "selection_episode",
    "outcome_access",
    "directional_learning",
    "method_freeze",
    "holdout_release",
    "report_use",
)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _missing(findings: list[str], path: str) -> None:
    findings.append(f"missing:{path}")


def _invalid(findings: list[str], path: str, reason: str) -> None:
    findings.append(f"invalid:{path}:{reason}")


def _require_text(value: Any, path: str, findings: list[str]) -> str:
    if not _text(value):
        _missing(findings, path)
        return ""
    return str(value)


def _validate_identity(manifest: dict[str, Any], findings: list[str]) -> tuple[dict[str, Any], Any]:
    identity = manifest.get("candidate_identity")
    if not isinstance(identity, dict):
        _missing(findings, "candidate_identity")
        return {}, None
    for field in ("company_id", "issuer_id", "responsibility_unit_id", "industry_id"):
        _require_text(identity.get(field), f"candidate_identity.{field}", findings)
    boundary = identity.get("common_boundary")
    if not isinstance(boundary, dict):
        _missing(findings, "candidate_identity.common_boundary")
    else:
        for field in ("responsibility_unit_id", "perimeter_id", "unit"):
            _require_text(boundary.get(field), f"candidate_identity.common_boundary.{field}", findings)
        if boundary.get("responsibility_unit_id") != identity.get("responsibility_unit_id"):
            _invalid(findings, "candidate_identity.common_boundary.responsibility_unit_id", "must_match_candidate_identity")
        if boundary.get("perimeter_id") != candidate_contract.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER:
            _invalid(findings, "candidate_identity.common_boundary.perimeter_id", "must_be_listed_consolidated_issuer")
    return identity, boundary


def _validate_current_cohort_admission_assessment(manifest: dict[str, Any], findings: list[str]) -> None:
    """Honor an explicit Stage-0 conclusion without retroactively changing legacy cohorts.

    A disclosure-availability cohort can remain a useful field catalogue after
    it is found too small, structurally broken, or geographically incoherent
    for a V4 final peer panel.  When that conclusion is explicitly recorded,
    discovery must not turn the same record back into a V4 case.  Older
    synthetic/V3 objects that predate this field keep their existing contract.
    """
    cohort = _dict(manifest.get("cohort_feasibility_record"))
    assessment = _dict(cohort.get("current_admission_assessment"))
    if "status" in assessment and assessment.get("status") != FEASIBLE_FOR_V4_FINAL_PANEL:
        _invalid(
            findings,
            "cohort_feasibility_record.current_admission_assessment.status",
            "must_equal_feasible_for_v4_final_panel",
        )


def _validate_source_list(
    evidence: Any,
    *,
    cutoff: Any,
    identity: dict[str, Any],
    boundary: Any,
    path: str,
    findings: list[str],
) -> None:
    """Delegate official source/boundary/cutoff checks to the V4 helper."""
    source_findings, valid = candidate_contract._valid_v4_evidence_list(
        evidence,
        cutoff,
        issuer_id=str(identity.get("issuer_id") or ""),
        perimeter_id=str(_dict(boundary).get("perimeter_id") or ""),
        boundary=_dict(boundary),
        prefix=path,
    )
    if not valid:
        findings.extend(f"invalid:{item}" for item in source_findings)


def _validate_action(
    manifest: dict[str, Any], *, cutoff: Any, identity: dict[str, Any], boundary: Any, findings: list[str],
) -> None:
    action = manifest.get("action")
    if not isinstance(action, dict):
        _missing(findings, "action")
        return
    _require_text(action.get("action_id"), "action.action_id", findings)
    _require_text(action.get("action_statement"), "action.action_statement", findings)
    if action.get("action_scope") != ACTION_SCOPE:
        _invalid(findings, "action.action_scope", "must_be_candidate_common_boundary")
    if action.get("economic_character") != COMMERCIAL_ACTION:
        _invalid(findings, "action.economic_character", "must_be_commercial_competitive_decision")
    if action.get("economic_action_type") not in candidate_contract.V4_ALLOWED_OPERATIONAL_ACTION_TYPES:
        _invalid(findings, "action.economic_action_type", "must_be_supported_operating_topology")
    if action.get("action_state") != candidate_contract.V4_ACTION_IMPLEMENTED:
        _invalid(findings, "action.action_state", "must_be_implemented_or_irrevocably_incurred")
    action_at = candidate_contract._date_or_time(action.get("implemented_or_incurred_at"))
    if action_at is None:
        _missing(findings, "action.implemented_or_incurred_at")
    elif cutoff is None or action_at > cutoff:
        _invalid(findings, "action.implemented_or_incurred_at", "must_be_cutoff_before")
    if not candidate_contract._same_boundary(action.get("boundary"), boundary):
        _invalid(findings, "action.boundary", "must_match_candidate_common_boundary")
    scope_bridge = action.get("issuer_scope_bridge")
    if not isinstance(scope_bridge, dict) \
            or scope_bridge.get("outcome_scope") != candidate_contract.V4_LISTED_CONSOLIDATED_ISSUER_PERIMETER \
            or scope_bridge.get("action_scope_relation") != "ISSUER_WIDE_OPERATING_DECISION" \
            or scope_bridge.get("issuer_level_mechanism_only") is not True:
        _invalid(findings, "action.issuer_scope_bridge", "must_prove_issuer_wide_mechanism_not_project_roi")
    else:
        _validate_source_list(
            scope_bridge.get("evidence"), cutoff=cutoff, identity=identity, boundary=boundary,
            path="action.issuer_scope_bridge.evidence", findings=findings,
        )
    specificity = action.get("decision_specificity")
    if not isinstance(specificity, dict) \
            or specificity.get("decision_class") != "DISCRETIONARY_OPERATING_DECISION" \
            or specificity.get("incremental_to_maintenance_or_mandated_baseline") is not True:
        _invalid(findings, "action.decision_specificity", "must_be_incremental_discretionary_operating_decision")
    else:
        _validate_source_list(
            specificity.get("evidence"), cutoff=cutoff, identity=identity, boundary=boundary,
            path="action.decision_specificity.evidence", findings=findings,
        )
    if action.get("explicitly_immaterial") is not False:
        _invalid(findings, "action.explicitly_immaterial", "must_be_false")
    _validate_source_list(
        action.get("implementation_evidence"), cutoff=cutoff, identity=identity, boundary=boundary,
        path="action.implementation_evidence", findings=findings,
    )
    exposure = action.get("exposure")
    if not isinstance(exposure, dict):
        _missing(findings, "action.exposure")
        return
    kind = exposure.get("kind")
    if kind not in ACTION_KINDS:
        _invalid(findings, "action.exposure.kind", "must_be_actual_cash_recognized_asset_or_implemented_net_price_delta_times_actual_units")
    _validate_source_list(
        exposure.get("evidence"), cutoff=cutoff, identity=identity, boundary=boundary,
        path="action.exposure.evidence", findings=findings,
    )
    if kind == "ACTUAL_CASH_OR_RECOGNIZED_ASSET":
        if exposure.get("actual_basis") not in ACTUAL_BASES:
            _invalid(findings, "action.exposure.actual_basis", "must_be_actual_cash_paid_or_recognized_asset")
    elif kind == "IMPLEMENTED_NET_PRICE_DELTA_X_PREACTION_ACTUAL_UNITS":
        for field in ("implemented_net_price_delta_field_ref", "preaction_actual_units_field_ref"):
            _require_text(exposure.get(field), f"action.exposure.{field}", findings)


def _validate_d2(
    manifest: dict[str, Any], *, cutoff: Any, identity: dict[str, Any], boundary: Any, primary_id: str, findings: list[str],
) -> None:
    d2 = manifest.get("d2_observability")
    if not isinstance(d2, dict):
        _missing(findings, "d2_observability")
        return
    if d2.get("primary_hypothesis_id") != primary_id or not primary_id:
        _invalid(findings, "d2_observability.primary_hypothesis_id", "must_match_primary_hypothesis")
    if d2.get("observation_kind") not in D2_KINDS:
        _invalid(findings, "d2_observability.observation_kind", "must_be_independent_customer_absorption_measure")
    if d2.get("not_mechanically_changed_by_action") is not True:
        _invalid(findings, "d2_observability.not_mechanically_changed_by_action", "must_be_true")
    d2_boundary = d2.get("boundary")
    if not isinstance(d2_boundary, dict) or not isinstance(boundary, dict) or any(
        d2_boundary.get(field) != boundary.get(field)
        for field in ("responsibility_unit_id", "perimeter_id")
    ):
        _invalid(findings, "d2_observability.boundary", "must_match_candidate_common_responsibility_and_perimeter")
    _require_text(d2.get("field_id"), "d2_observability.field_id", findings)
    repetitions = d2.get("repetitions")
    if not isinstance(repetitions, list) or len(repetitions) < 3:
        _invalid(findings, "d2_observability.repetitions", "requires_at_least_three_cutoff_before_periods")
        return
    periods: set[str] = set()
    for index, repetition in enumerate(repetitions):
        path = f"d2_observability.repetitions[{index}]"
        if not isinstance(repetition, dict):
            _invalid(findings, path, "must_be_object")
            continue
        period_end = candidate_contract._date_or_time(repetition.get("period_end"))
        if period_end is None:
            _missing(findings, f"{path}.period_end")
        elif cutoff is None or period_end > cutoff:
            _invalid(findings, f"{path}.period_end", "must_be_cutoff_before")
        else:
            periods.add(str(repetition.get("period_end")))
        _require_text(repetition.get("field_ref"), f"{path}.field_ref", findings)
        _validate_source_list(
            repetition.get("evidence"), cutoff=cutoff, identity=identity, boundary=d2_boundary,
            path=f"{path}.evidence", findings=findings,
        )
    if len(periods) < 3:
        _invalid(findings, "d2_observability.repetitions", "must_contain_three_distinct_periods")


def _validate_cost_driver(
    manifest: dict[str, Any], *, cutoff: Any, identity: dict[str, Any],
    boundary: Any, primary_id: str, findings: list[str],
) -> None:
    driver = manifest.get("cost_driver_observability")
    if not isinstance(driver, dict):
        _missing(findings, "cost_driver_observability")
        return
    if driver.get("primary_hypothesis_id") != primary_id or not primary_id:
        _invalid(findings, "cost_driver_observability.primary_hypothesis_id", "must_match_primary_hypothesis")
    if driver.get("observation_kind") not in candidate_contract.V4_COST_DRIVER_KINDS:
        _invalid(findings, "cost_driver_observability.observation_kind", "must_be_supported_cost_driver")
    if not candidate_contract._same_boundary(driver.get("boundary"), boundary):
        _invalid(findings, "cost_driver_observability.boundary", "must_match_candidate_common_boundary")
    _require_text(driver.get("field_id"), "cost_driver_observability.field_id", findings)
    repetitions = driver.get("repetitions")
    if not isinstance(repetitions, list) or len(repetitions) < 3:
        _invalid(findings, "cost_driver_observability.repetitions", "requires_at_least_three_cutoff_before_periods")
        return
    periods: set[str] = set()
    for index, repetition in enumerate(repetitions):
        path = f"cost_driver_observability.repetitions[{index}]"
        if not isinstance(repetition, dict):
            _invalid(findings, path, "must_be_object")
            continue
        period_end = candidate_contract._date_or_time(repetition.get("period_end"))
        if period_end is None:
            _missing(findings, f"{path}.period_end")
        elif cutoff is None or period_end > cutoff:
            _invalid(findings, f"{path}.period_end", "must_be_cutoff_before")
        else:
            periods.add(str(repetition.get("period_end")))
        _require_text(repetition.get("field_ref"), f"{path}.field_ref", findings)
        _validate_source_list(
            repetition.get("evidence"), cutoff=cutoff, identity=identity, boundary=boundary,
            path=f"{path}.evidence", findings=findings,
        )
    if len(periods) < 3:
        _invalid(findings, "cost_driver_observability.repetitions", "must_contain_three_distinct_periods")


def _validate_cutoff_before_facts(
    manifest: dict[str, Any], *, cutoff: Any, identity: dict[str, Any], boundary: Any, findings: list[str],
) -> set[str]:
    """Bind each H-A/H-B rationale to an official cutoff-before fact."""
    facts = manifest.get("cutoff_before_facts")
    if not isinstance(facts, list) or not facts:
        _missing(findings, "cutoff_before_facts")
        return set()
    fact_ids: set[str] = set()
    for index, fact in enumerate(facts):
        path = f"cutoff_before_facts[{index}]"
        if not isinstance(fact, dict):
            _invalid(findings, path, "must_be_object")
            continue
        fact_id = _require_text(fact.get("fact_id"), f"{path}.fact_id", findings)
        _require_text(fact.get("statement"), f"{path}.statement", findings)
        scope = fact.get("evidence_scope", FACT_SCOPE_CANDIDATE)
        fact_boundary = boundary
        if scope == FACT_SCOPE_D2:
            d2 = _dict(manifest.get("d2_observability"))
            fact_boundary = d2.get("boundary")
        elif scope == FACT_SCOPE_COST:
            driver = _dict(manifest.get("cost_driver_observability"))
            fact_boundary = driver.get("boundary")
        elif scope != FACT_SCOPE_CANDIDATE:
            _invalid(findings, f"{path}.evidence_scope", "must_be_candidate_d2_or_cost_common_boundary")
        _validate_source_list(
            fact.get("evidence"), cutoff=cutoff, identity=identity, boundary=fact_boundary,
            path=f"{path}.evidence", findings=findings,
        )
        if fact_id in fact_ids:
            _invalid(findings, f"{path}.fact_id", "must_be_unique")
        elif fact_id:
            fact_ids.add(fact_id)
    return fact_ids


def _validate_hypothesis_pair(manifest: dict[str, Any], known_fact_ids: set[str], findings: list[str]) -> str:
    pair = manifest.get("hypothesis_pair")
    if not isinstance(pair, dict):
        _missing(findings, "hypothesis_pair")
        return ""
    _require_text(pair.get("decisive_question"), "hypothesis_pair.decisive_question", findings)
    primary = pair.get("primary")
    rival = pair.get("strongest_rival")
    if not isinstance(primary, dict):
        _missing(findings, "hypothesis_pair.primary")
        primary = {}
    if not isinstance(rival, dict):
        _missing(findings, "hypothesis_pair.strongest_rival")
        rival = {}
    primary_id = _require_text(primary.get("hypothesis_id"), "hypothesis_pair.primary.hypothesis_id", findings)
    rival_id = _require_text(rival.get("hypothesis_id"), "hypothesis_pair.strongest_rival.hypothesis_id", findings)
    for label, hypothesis in (("primary", primary), ("strongest_rival", rival)):
        _require_text(hypothesis.get("mechanism"), f"hypothesis_pair.{label}.mechanism", findings)
        _require_text(hypothesis.get("pre_outcome_rationale"), f"hypothesis_pair.{label}.pre_outcome_rationale", findings)
        fact_ids = hypothesis.get("supporting_fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids or not all(_text(item) for item in fact_ids):
            _invalid(findings, f"hypothesis_pair.{label}.supporting_fact_ids", "requires_cutoff_before_fact_ids")
        elif not set(fact_ids).issubset(known_fact_ids):
            _invalid(findings, f"hypothesis_pair.{label}.supporting_fact_ids", "must_reference_supplied_cutoff_before_facts")
    if primary_id and primary_id == rival_id:
        _invalid(findings, "hypothesis_pair", "primary_and_strongest_rival_must_differ")
    if primary.get("mechanism") == rival.get("mechanism") and _text(primary.get("mechanism")):
        _invalid(findings, "hypothesis_pair", "primary_and_strongest_rival_mechanisms_must_differ")
    if rival.get("live_before_cutoff") is not True:
        _invalid(findings, "hypothesis_pair.strongest_rival.live_before_cutoff", "must_be_true")
    basis = pair.get("selection_basis")
    if not isinstance(basis, dict):
        _missing(findings, "hypothesis_pair.selection_basis")
    else:
        if basis.get("directional_preference") != primary_id:
            _invalid(findings, "hypothesis_pair.selection_basis.directional_preference", "must_match_primary_hypothesis")
        _require_text(basis.get("why_not_common"), "hypothesis_pair.selection_basis.why_not_common", findings)
        _require_text(basis.get("why_rival_remains_live"), "hypothesis_pair.selection_basis.why_rival_remains_live", findings)
    return primary_id


def _validate_firewall(manifest: dict[str, Any], findings: list[str]) -> None:
    firewall = manifest.get("source_firewall")
    if not isinstance(firewall, dict):
        _missing(findings, "source_firewall")
        return
    if firewall.get("outcome_body_access") != "UNREAD_AND_PROHIBITED":
        _invalid(findings, "source_firewall.outcome_body_access", "must_be_unread_and_prohibited")
    if firewall.get("outcome_metadata_access") != "NONE":
        _invalid(findings, "source_firewall.outcome_metadata_access", "must_be_none")
    if firewall.get("post_cutoff_sources_prohibited") is not True:
        _invalid(findings, "source_firewall.post_cutoff_sources_prohibited", "must_be_true")
    _require_text(firewall.get("curator_attestation"), "source_firewall.curator_attestation", findings)
    _validate_discovery_entry(firewall, manifest=manifest, findings=findings)
    receipt = firewall.get("access_receipt")
    if not isinstance(receipt, dict):
        _missing(findings, "source_firewall.access_receipt")
        return
    if receipt.get("schema_version") != "phase10-pit-runner-attestation.v1" \
            or receipt.get("runner") != "phase10_pit_runner" \
            or receipt.get("assurance_level") != "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS" \
            or receipt.get("state") != "REVIEWABLE" \
            or receipt.get("cutoff_at") != manifest.get("cutoff_at"):
        _invalid(findings, "source_firewall.access_receipt", "must_be_reviewable_matching_phase10_receipt")
        return
    allowed = receipt.get("allowed_source_ids")
    allowlist = receipt.get("source_allowlist")
    if not isinstance(allowed, list) or not allowed or not all(_text(item) for item in allowed) \
            or not isinstance(allowlist, list):
        _invalid(findings, "source_firewall.access_receipt", "source_allowlist_missing")
        return
    cutoff = candidate_contract._time(manifest.get("cutoff_at"))
    listed: set[str] = set()
    for index, source in enumerate(allowlist):
        if not isinstance(source, dict) or not _text(source.get("source_id")):
            _invalid(findings, f"source_firewall.access_receipt.source_allowlist[{index}]", "identity_invalid")
            continue
        listed.add(str(source["source_id"]))
        published_at = candidate_contract._date_or_time(source.get("published_at"))
        if published_at is None or cutoff is None or published_at > cutoff:
            _invalid(findings, f"source_firewall.access_receipt.source_allowlist[{index}]", "not_cutoff_before")
    if set(allowed) != listed:
        _invalid(findings, "source_firewall.access_receipt", "allowed_source_ids_not_exact_allowlist")
    supplied = _manifest_source_ids({key: value for key, value in manifest.items() if key != "source_firewall"})
    if not supplied.issubset(set(allowed)):
        _invalid(findings, "source_firewall.access_receipt", "supplied_source_not_in_phase10_allowlist")


def _validate_discovery_entry(
    firewall: dict[str, Any], *, manifest: dict[str, Any], findings: list[str],
) -> None:
    """Require an auditable PIT-safe source-discovery route.

    This does not claim to sandbox a collaborator's browser.  It makes the
    actual route reviewable and rejects a manifest that records the known
    unsafe CNINFO issuer-search path.  The source receipt remains the
    authoritative record for the later PDF's cutoff and admission identity.
    """
    entry = firewall.get("discovery_entry")
    if not isinstance(entry, dict):
        _missing(findings, "source_firewall.discovery_entry")
        return
    if entry.get("kind") not in PIT_SAFE_DISCOVERY_ENTRY_KINDS:
        _invalid(
            findings,
            "source_firewall.discovery_entry.kind",
            "must_be_predeclared_cutoff_before_static_cninfo_pdf_package",
        )
    if entry.get("issuer_code_or_name_submitted_to_cninfo_fulltext") is not False:
        _invalid(
            findings,
            "source_firewall.discovery_entry.issuer_code_or_name_submitted_to_cninfo_fulltext",
            "must_be_false",
        )
    if entry.get("cninfo_issuer_stock_or_detail_page_opened") is not False:
        _invalid(
            findings,
            "source_firewall.discovery_entry.cninfo_issuer_stock_or_detail_page_opened",
            "must_be_false",
        )
    if entry.get("post_identification_access") != POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY:
        _invalid(
            findings,
            "source_firewall.discovery_entry.post_identification_access",
            "must_be_predeclared_cutoff_before_static_cninfo_pdf_package_only",
        )
    sources = entry.get("static_pdf_sources")
    if not isinstance(sources, list) or not sources:
        _invalid(findings, "source_firewall.discovery_entry.static_pdf_sources", "must_be_nonempty_list")
        return
    supplied = _manifest_source_ids({key: value for key, value in manifest.items() if key != "source_firewall"})
    for index, source in enumerate(sources):
        path = f"source_firewall.discovery_entry.static_pdf_sources[{index}]"
        if not isinstance(source, dict):
            _invalid(findings, path, "must_be_object")
            continue
        pdf_url = source.get("url")
        if not isinstance(pdf_url, str) or not pdf_url.startswith("https://static.cninfo.com.cn/") \
                or ".pdf" not in pdf_url.lower():
            _invalid(findings, f"{path}.url", "must_be_static_cninfo_pdf_url")
        source_id = source.get("source_id")
        if not _text(source_id):
            _missing(findings, f"{path}.source_id")
        elif source_id not in supplied:
            _invalid(findings, f"{path}.source_id", "must_be_a_supplied_cutoff_before_source")


def _manifest_source_ids(value: Any) -> set[str]:
    if isinstance(value, dict):
        result = {str(value["source_id"])} if _text(value.get("source_id")) else set()
        for item in value.values():
            result.update(_manifest_source_ids(item))
        return result
    if isinstance(value, list):
        return set().union(*(_manifest_source_ids(item) for item in value)) if value else set()
    return set()


def _stage0_contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in _STAGE0_FORBIDDEN_KEYS or _stage0_contains_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(_stage0_contains_forbidden_key(item) for item in value)
    return False


def _stage0_closed_mapping(value: Any, *, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _invalid(findings, path, "must_be_object")
        return {}
    if set(value) - allowed:
        _invalid(findings, path, "contains_unapproved_information")
    return value


def _validate_stage0_closed_shape(package: dict[str, Any], findings: list[str]) -> None:
    """Keep the H1 receipt closed so it cannot become action-first research."""
    _stage0_closed_mapping(package, allowed=_STAGE0_PACKAGE_KEYS, path="package", findings=findings)
    _stage0_closed_mapping(
        package.get("current_admission_assessment"), allowed=_STAGE0_ASSESSMENT_KEYS,
        path="current_admission_assessment", findings=findings,
    )
    _stage0_closed_mapping(
        package.get("curator_attestation"), allowed=_STAGE0_ATTESTATION_KEYS,
        path="curator_attestation", findings=findings,
    )
    _stage0_closed_mapping(package.get("universe"), allowed=_STAGE0_UNIVERSE_KEYS, path="universe", findings=findings)
    arena = _stage0_closed_mapping(
        package.get("competitive_arena"), allowed=_STAGE0_ARENA_KEYS,
        path="competitive_arena", findings=findings,
    )
    for index, evidence in enumerate(arena.get("evidence") if isinstance(arena.get("evidence"), list) else []):
        _stage0_closed_mapping(
            evidence, allowed=_STAGE0_EVIDENCE_KEYS,
            path=f"competitive_arena.evidence[{index}]", findings=findings,
        )
    for index, source in enumerate(package.get("static_pdf_sources") if isinstance(package.get("static_pdf_sources"), list) else []):
        _stage0_closed_mapping(
            source, allowed=_STAGE0_STATIC_SOURCE_KEYS,
            path=f"static_pdf_sources[{index}]", findings=findings,
        )
    for member_index, member_value in enumerate(package.get("members") if isinstance(package.get("members"), list) else []):
        member = _stage0_closed_mapping(
            member_value, allowed=_STAGE0_MEMBER_KEYS, path=f"members[{member_index}]", findings=findings,
        )
        _stage0_closed_mapping(
            member.get("boundary"), allowed=_STAGE0_BOUNDARY_KEYS,
            path=f"members[{member_index}].boundary", findings=findings,
        )
        for evidence_name in ("industry_business_evidence", "control_group_evidence", "comparability_break_evidence"):
            for evidence_index, evidence in enumerate(member.get(evidence_name) if isinstance(member.get(evidence_name), list) else []):
                _stage0_closed_mapping(
                    evidence, allowed=_STAGE0_EVIDENCE_KEYS,
                    path=f"members[{member_index}].{evidence_name}[{evidence_index}]", findings=findings,
                )
        d2 = (
            _stage0_closed_mapping(
                member.get("d2_field_availability"), allowed=_STAGE0_D2_KEYS,
                path=f"members[{member_index}].d2_field_availability", findings=findings,
            )
            if "d2_field_availability" in member else {}
        )
        for repetition_index, repetition in enumerate(d2.get("repetitions") if isinstance(d2.get("repetitions"), list) else []):
            repetition_map = _stage0_closed_mapping(
                repetition, allowed=_STAGE0_REPETITION_KEYS,
                path=f"members[{member_index}].d2_field_availability.repetitions[{repetition_index}]", findings=findings,
            )
            for evidence_index, evidence in enumerate(repetition_map.get("evidence") if isinstance(repetition_map.get("evidence"), list) else []):
                _stage0_closed_mapping(
                    evidence, allowed=_STAGE0_EVIDENCE_KEYS,
                    path=f"members[{member_index}].d2_field_availability.repetitions[{repetition_index}].evidence[{evidence_index}]",
                    findings=findings,
                )
        cost = (
            _stage0_closed_mapping(
                member.get("cost_field_availability"), allowed=_STAGE0_COST_KEYS,
                path=f"members[{member_index}].cost_field_availability", findings=findings,
            )
            if "cost_field_availability" in member else {}
        )
        for repetition_index, repetition in enumerate(cost.get("repetitions") if isinstance(cost.get("repetitions"), list) else []):
            repetition_map = _stage0_closed_mapping(
                repetition, allowed=_STAGE0_REPETITION_KEYS,
                path=f"members[{member_index}].cost_field_availability.repetitions[{repetition_index}]", findings=findings,
            )
            for evidence_index, evidence in enumerate(repetition_map.get("evidence") if isinstance(repetition_map.get("evidence"), list) else []):
                _stage0_closed_mapping(
                    evidence, allowed=_STAGE0_EVIDENCE_KEYS,
                    path=f"members[{member_index}].cost_field_availability.repetitions[{repetition_index}].evidence[{evidence_index}]",
                    findings=findings,
                )
        for annual_index, annual in enumerate(member.get("annual_d3_d4_availability") if isinstance(member.get("annual_d3_d4_availability"), list) else []):
            annual_map = _stage0_closed_mapping(
                annual, allowed=_STAGE0_ANNUAL_KEYS,
                path=f"members[{member_index}].annual_d3_d4_availability[{annual_index}]", findings=findings,
            )
            for evidence_index, evidence in enumerate(annual_map.get("evidence") if isinstance(annual_map.get("evidence"), list) else []):
                _stage0_closed_mapping(
                    evidence, allowed=_STAGE0_EVIDENCE_KEYS,
                    path=f"members[{member_index}].annual_d3_d4_availability[{annual_index}].evidence[{evidence_index}]",
                    findings=findings,
                )


def _stage0_source_is_strictly_before(source: dict[str, Any], selection_as_of: Any) -> bool:
    """Date-only static disclosures are never same-day Stage-0 evidence."""
    selection = candidate_contract._time(selection_as_of)
    published_raw = source.get("published_at")
    published = candidate_contract._date_or_time(published_raw)
    if selection is None or published is None:
        return False
    if isinstance(published_raw, str) and len(published_raw.strip()) == 10:
        return published.date() < selection.date()
    return published < selection


def _stage0_evidence_records(value: Any) -> list[dict[str, Any]]:
    """Find source-bearing field references in one member's declared record."""
    if isinstance(value, dict):
        own = [value] if _text(value.get("source_id")) and _text(value.get("field_ref")) else []
        return own + [record for nested in value.values() for record in _stage0_evidence_records(nested)]
    if isinstance(value, list):
        return [record for nested in value for record in _stage0_evidence_records(nested)]
    return []


def _validate_stage0_static_sources(
    package: dict[str, Any], *, selection_as_of: Any, findings: list[str],
) -> dict[str, dict[str, Any]]:
    declared = package.get("static_pdf_sources")
    if not isinstance(declared, list) or not declared:
        _invalid(findings, "static_pdf_sources", "must_be_nonempty_list")
        return {}
    source_index: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(declared):
        path = f"static_pdf_sources[{index}]"
        if not isinstance(source, dict):
            _invalid(findings, path, "must_be_object")
            continue
        source_id = source.get("source_id")
        if not _text(source_id) or source_id in source_index:
            _invalid(findings, f"{path}.source_id", "must_be_unique_nonempty")
            continue
        source_index[str(source_id)] = {"field_refs": set()}
        url = source.get("url")
        if not isinstance(url, str) or not re.fullmatch(
            r"https://static\.cninfo\.com\.cn/finalpage/.+\.pdf", url, re.IGNORECASE,
        ):
            _invalid(findings, f"{path}.url", "must_be_static_cninfo_finalpage_pdf")
        if source.get("source_type") != "OFFICIAL_AUDITED_ANNUAL_REPORT":
            _invalid(findings, f"{path}.source_type", "must_be_official_audited_annual_report")
        for field in ("issuer_id", "responsibility_unit_id", "perimeter_id", "unit"):
            if not _text(source.get(field)):
                _missing(findings, f"{path}.{field}")
            else:
                source_index[str(source_id)][field] = str(source[field])
        if candidate_contract._date_or_time(source.get("period_end")) is None:
            _invalid(findings, f"{path}.period_end", "must_be_date")
        else:
            source_index[str(source_id)]["period_end"] = str(source["period_end"])
        if not _stage0_source_is_strictly_before(source, selection_as_of):
            _invalid(findings, f"{path}.published_at", "must_be_strictly_before_selection_as_of")
        field_refs = source.get("field_refs")
        if not isinstance(field_refs, list) or not field_refs or not all(
            _text(field_ref) and _PAGE_REFERENCE.search(str(field_ref)) for field_ref in field_refs
        ):
            _invalid(findings, f"{path}.field_refs", "must_contain_paged_field_references")
        else:
            source_index[str(source_id)]["field_refs"] = {str(field_ref) for field_ref in field_refs}
    return source_index


def _validate_stage0_arena(
    package: dict[str, Any], *, source_fields: dict[str, dict[str, Any]], findings: list[str],
) -> str:
    arena = package.get("competitive_arena")
    if not isinstance(arena, dict):
        _missing(findings, "competitive_arena")
        return ""
    for field in (
        "competitive_arena_id", "product_or_service_scope", "geographic_scope", "customer_end_market_scope",
    ):
        _require_text(arena.get(field), f"competitive_arena.{field}", findings)
    if arena.get("market_scope_type") not in STAGE0_ARENA_SCOPE_TYPES:
        _invalid(findings, "competitive_arena.market_scope_type", "must_be_supported_mechanism_arena_scope")
    if source_fields:
        for index, evidence in enumerate(_stage0_evidence_records(arena.get("evidence"))):
            source_id = str(evidence["source_id"])
            field_ref = str(evidence["field_ref"])
            path = f"competitive_arena.evidence[{index}]"
            if source_id not in source_fields:
                _invalid(findings, f"{path}.source_id", "must_be_declared_static_pdf")
            elif field_ref not in source_fields[source_id]["field_refs"]:
                _invalid(findings, f"{path}.field_ref", "must_match_declared_static_pdf_page")
    if not _stage0_evidence_records(arena.get("evidence")):
        _invalid(findings, "competitive_arena.evidence", "must_be_source_bearing")
    return str(arena.get("competitive_arena_id") or "")


def _validate_stage0_period_bound_field_history(
    history: Any,
    *,
    source_fields: dict[str, dict[str, Any]],
    path: str,
    findings: list[str],
) -> None:
    """Each recurring field identity must cite the annual PDF for that period."""
    for record_index, record_value in enumerate(history if isinstance(history, list) else []):
        record = _dict(record_value)
        period_end = record.get("period_end")
        for evidence_index, evidence in enumerate(record.get("evidence") if isinstance(record.get("evidence"), list) else []):
            source = source_fields.get(evidence.get("source_id"))
            if source is not None and source.get("period_end") != period_end:
                _invalid(
                    findings,
                    f"{path}[{record_index}].evidence[{evidence_index}].period_end",
                    "must_match_declared_static_pdf_period_end",
                )


def _validate_stage0_optional_cost_histories(package: dict[str, Any], findings: list[str]) -> None:
    """Apply the legacy three-period identity test to any additionally declared cost field.

    The base legacy projection already checks a cost history when it is the
    sole Stage-0 history.  When central customer D2 is also present, the
    projection necessarily keeps D2; validate a second, cost-projected copy
    so an optional diagnostic field cannot arrive without its own identity
    and recurrent source-bearing observations.
    """
    members = package.get("members")
    if not isinstance(members, list) or not any(
        isinstance(member, dict)
        and isinstance(member.get("d2_field_availability"), dict)
        and "cost_field_availability" in member
        for member in members
    ):
        return
    cost_record = deepcopy(package)
    cost_record["schema_version"] = candidate_contract.V4_COHORT_FEASIBILITY_SCHEMA_VERSION
    for member in cost_record.get("members") if isinstance(cost_record.get("members"), list) else []:
        if isinstance(member, dict) and "cost_field_availability" in member:
            member["d2_field_availability"] = member["cost_field_availability"]
    checked = candidate_contract.validate_v4_cohort_feasibility_record(cost_record, action_at=None)
    for finding in checked["findings"]:
        if "_d2_availability" in finding:
            findings.append("invalid:" + finding.replace("_d2_availability", "_cost_field_availability"))


def validate_stage0_static_source_package(package: Any) -> dict[str, Any]:
    """Validate the H1 offline curator package without selecting an action.

    The package is deliberately not accepted by ``validate_v5_candidate`` and
    cannot be sealed.  It only establishes a static, pre-action cohort that
    may later enter the candidate-decision screen with the same declared PDFs.
    """
    findings: list[str] = []
    if not isinstance(package, dict):
        return {
            "schema_version": STAGE0_STATIC_RESULT_SCHEMA_VERSION,
            "state": INSUFFICIENT_STATIC_SOURCE_PACKAGE,
            "findings": ["invalid:package:must_be_object"],
            "does_not_grant": list(DOES_NOT_GRANT),
        }
    if package.get("schema_version") != STAGE0_STATIC_PACKAGE_SCHEMA_VERSION:
        _invalid(findings, "schema_version", "must_equal_stage0_static_package_v1")
    _validate_stage0_closed_shape(package, findings)
    if package.get("entry_kind") != CURATOR_SUPPLIED_STATIC_PDF_PACKAGE:
        _invalid(findings, "entry_kind", "must_be_curator_supplied_static_cninfo_pdf_package")
    selection_as_of = package.get("selection_as_of")
    if candidate_contract._time(selection_as_of) is None:
        _invalid(findings, "selection_as_of", "must_be_timezone_aware_iso8601")
    cohort_eligibility_as_of = package.get("cohort_eligibility_as_of")
    if candidate_contract._time(cohort_eligibility_as_of) is None \
            or candidate_contract._time(cohort_eligibility_as_of) != candidate_contract._time(selection_as_of):
        _invalid(findings, "cohort_eligibility_as_of", "must_match_selection_as_of_timezone_aware")
    _require_text(package.get("arena_family"), "arena_family", findings)
    topology = package.get("mechanism_topology")
    if topology not in STAGE0_MECHANISM_TOPOLOGIES:
        _invalid(findings, "mechanism_topology", "must_be_customer_response_or_cost_restructuring")
    assessment = _dict(package.get("current_admission_assessment"))
    if assessment.get("status") != FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE:
        _invalid(findings, "current_admission_assessment.status", "must_equal_feasible_for_h1_static_source_package")
    attestation = package.get("curator_attestation")
    if not isinstance(attestation, dict):
        _missing(findings, "curator_attestation")
    else:
        _require_text(attestation.get("curator_id"), "curator_attestation.curator_id", findings)
        for field in (
            "issuer_code_or_name_submitted_to_cninfo_fulltext",
            "cninfo_issuer_stock_or_detail_page_opened",
            "post_cutoff_metadata_or_body_read",
        ):
            if attestation.get(field) is not False:
                _invalid(findings, f"curator_attestation.{field}", "must_be_false")
        if attestation.get("post_identification_access") != POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY:
            _invalid(
                findings,
                "curator_attestation.post_identification_access",
                "must_be_predeclared_cutoff_before_static_cninfo_pdf_package_only",
            )
    if _stage0_contains_forbidden_key({
        key: value for key, value in package.items()
        if key not in {"current_admission_assessment", "curator_attestation"}
    }):
        _invalid(findings, "package", "must_not_contain_action_target_or_outcome_information")

    source_fields = _validate_stage0_static_sources(
        package, selection_as_of=selection_as_of, findings=findings,
    )
    arena_id = _validate_stage0_arena(package, source_fields=source_fields, findings=findings)

    # Reuse the proven legacy field/control/boundary checks while keeping this
    # strict H1 receipt separate from both V4 discovery and the V5 root bundle.
    legacy_record = deepcopy(package)
    legacy_record["schema_version"] = candidate_contract.V4_COHORT_FEASIBILITY_SCHEMA_VERSION
    if topology == "COST_RESTRUCTURING":
        for member in legacy_record.get("members") if isinstance(legacy_record.get("members"), list) else []:
            if isinstance(member, dict) and "cost_field_availability" in member and "d2_field_availability" not in member:
                member["d2_field_availability"] = member["cost_field_availability"]
    legacy = candidate_contract.validate_v4_cohort_feasibility_record(legacy_record, action_at=None)
    findings.extend("invalid:" + item for item in legacy["findings"])
    if topology == "COST_RESTRUCTURING":
        _validate_stage0_optional_cost_histories(package, findings)
    members = [_dict(member) for member in package.get("members") if isinstance(member, dict)]
    allowed_dispositions = {"PENDING_ACTION_WINDOW_REVIEW", "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"}
    if len(members) < 5 or any(
        member.get("final_peer_panel_disposition") not in allowed_dispositions
        for member in members
    ):
        _invalid(findings, "members", "must_have_five_disclosure_members")
    for member_index, member in enumerate(members):
        if member.get("competitive_arena_id") != arena_id:
            _invalid(findings, f"members[{member_index}].competitive_arena_id", "must_match_package_arena")
        if source_fields:
            for evidence_index, evidence in enumerate(_stage0_evidence_records(member)):
                source_id = str(evidence["source_id"])
                field_ref = str(evidence["field_ref"])
                path = f"members[{member_index}].evidence[{evidence_index}]"
                if source_id not in source_fields:
                    _invalid(findings, f"{path}.source_id", "must_be_declared_static_pdf")
                    continue
                source = source_fields[source_id]
                if field_ref not in source["field_refs"]:
                    _invalid(findings, f"{path}.field_ref", "must_match_declared_static_pdf_page")
                for field in ("issuer_id", "responsibility_unit_id", "perimeter_id", "unit"):
                    if source.get(field) != evidence.get(field):
                        _invalid(findings, f"{path}.{field}", "must_match_declared_static_pdf_identity")
        break_evidence = member.get("comparability_break_evidence")
        if member.get("final_peer_panel_disposition") == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK":
            member_boundary = _dict(member.get("boundary"))
            _validate_source_list(
                break_evidence, cutoff=candidate_contract._time(selection_as_of),
                identity={"issuer_id": member.get("issuer_id")},
                boundary=member_boundary,
                path=f"cohort_member[{member_index}].comparability_break_evidence", findings=findings,
            )
        elif break_evidence is not None:
            _invalid(
                findings,
                f"cohort_member[{member_index}].comparability_break_evidence",
                "must_be_reserved_for_known_scope_or_control_break",
            )
        carrier_sources = member.get("carrier_identity_source_ids")
        if not isinstance(carrier_sources, list) or not carrier_sources or not all(_text(item) for item in carrier_sources):
            _invalid(findings, f"members[{member_index}].carrier_identity_source_ids", "must_be_nonempty_static_source_list")
        elif source_fields:
            for source_id in carrier_sources:
                source = source_fields.get(source_id)
                if source is None:
                    _invalid(findings, f"members[{member_index}].carrier_identity_source_ids", "must_be_declared_static_pdf")
                elif any(source.get(field) != member.get(field) for field in ("issuer_id", "responsibility_unit_id")) \
                        or source.get("perimeter_id") != _dict(member.get("boundary")).get("perimeter_id") \
                        or source.get("unit") != _dict(member.get("boundary")).get("unit"):
                    _invalid(findings, f"members[{member_index}].carrier_identity_source_ids", "must_match_member_static_pdf_identity")
        d2_history = member.get("d2_field_availability")
        cost_history = member.get("cost_field_availability")
        if topology == "CUSTOMER_RESPONSE":
            if not isinstance(d2_history, dict) or isinstance(cost_history, dict):
                _invalid(findings, f"members[{member_index}]", "must_have_d2_not_cost_field_history_for_customer_response")
            _validate_stage0_period_bound_field_history(
                _dict(d2_history).get("repetitions"), source_fields=source_fields,
                path=f"members[{member_index}].d2_field_availability.repetitions", findings=findings,
            )
        elif topology == "COST_RESTRUCTURING":
            cost = _dict(cost_history)
            if not cost and not isinstance(d2_history, dict):
                _invalid(findings, f"members[{member_index}]", "must_have_d2_or_cost_field_history_for_cost_restructuring")
            if cost and cost.get("cost_driver_kind") not in STAGE0_COST_DRIVER_KINDS:
                _invalid(findings, f"members[{member_index}].cost_field_availability.cost_driver_kind", "must_be_supported")
            if cost:
                _validate_stage0_period_bound_field_history(
                    cost.get("repetitions"), source_fields=source_fields,
                    path=f"members[{member_index}].cost_field_availability.repetitions", findings=findings,
                )
            if isinstance(d2_history, dict):
                _validate_stage0_period_bound_field_history(
                    d2_history.get("repetitions"), source_fields=source_fields,
                    path=f"members[{member_index}].d2_field_availability.repetitions", findings=findings,
                )
        _validate_stage0_period_bound_field_history(
            member.get("annual_d3_d4_availability"), source_fields=source_fields,
            path=f"members[{member_index}].annual_d3_d4_availability", findings=findings,
        )

    source_problem = any(
        token in finding for finding in findings
        for token in (
            "static_pdf_sources", "entry_kind", "curator_attestation", "declared_static_pdf",
            "static_cninfo_finalpage_pdf", "static_pdf_page", "selection_as_of",
        )
    )
    structural_problem = (bool(findings) and not source_problem) or any(
        token in finding for finding in findings
        for token in (
            "current_admission_assessment",
            "cohort_",
            "members:must_have_five_disclosure_members",
            "competitive_arena_id:must_match_package_arena",
            "package:must_not_contain_action_target_or_outcome_information",
            "competitive_arena.market_scope_type",
            "competitive_arena.product_or_service_scope",
            "competitive_arena.geographic_scope",
            "competitive_arena.customer_end_market_scope",
        )
    )
    state = (
        STAGE0_FEASIBILITY_REVIEWABLE if not findings
        else STAGE0_REJECTED if structural_problem
        else INSUFFICIENT_STATIC_SOURCE_PACKAGE
    )
    result = {
        "schema_version": STAGE0_STATIC_RESULT_SCHEMA_VERSION,
        "state": state,
        "findings": findings,
        "does_not_grant": list(DOES_NOT_GRANT),
    }
    if state == STAGE0_FEASIBILITY_REVIEWABLE:
        result["next_permitted_step"] = "CURATOR_ACTION_SCREEN_STATIC_EXTENSION"
    return result


def _h2_contains_forbidden_key(value: Any) -> bool:
    """Reject result/final-peer material while permitting action scope language."""
    forbidden = {
        "outcome", "outcome_value", "outcome_source", "winner", "final_peer", "final_peer_panel",
        "final_peer_role", "focal_target", "focal_issuer", "focal_issuer_id", "target_issuer",
        "target_issuer_id", "members", "cohort_feasibility_record",
    }
    if isinstance(value, dict):
        return any(
            str(key).lower() in forbidden or _h2_contains_forbidden_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(_h2_contains_forbidden_key(item) for item in value)
    return False


def _h2_closed_mapping(value: Any, *, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _invalid(findings, path, "must_be_object")
        return {}
    if set(value) - allowed:
        _invalid(findings, path, "contains_unapproved_information")
    return value


def _validate_h2_evidence_shape(value: Any, *, path: str, findings: list[str]) -> None:
    if not isinstance(value, list):
        return
    for index, evidence in enumerate(value):
        _h2_closed_mapping(
            evidence, allowed=_H2_EVIDENCE_KEYS, path=f"{path}[{index}]", findings=findings,
        )


def _validate_h2_closed_shape(extension: dict[str, Any], findings: list[str]) -> None:
    _h2_closed_mapping(extension, allowed=_H2_EXTENSION_KEYS, path="action_screen_extension", findings=findings)
    identity = _h2_closed_mapping(
        extension.get("candidate_identity"), allowed=_H2_CANDIDATE_IDENTITY_KEYS,
        path="action_screen_extension.candidate_identity", findings=findings,
    )
    _h2_closed_mapping(
        identity.get("common_boundary"), allowed=_STAGE0_BOUNDARY_KEYS,
        path="action_screen_extension.candidate_identity.common_boundary", findings=findings,
    )
    _h2_closed_mapping(
        extension.get("source_firewall_attestation"), allowed=_H2_SOURCE_FIREWALL_KEYS,
        path="action_screen_extension.source_firewall_attestation", findings=findings,
    )
    for index, source in enumerate(extension.get("static_pdf_sources") if isinstance(extension.get("static_pdf_sources"), list) else []):
        _h2_closed_mapping(
            source, allowed=_H2_STATIC_SOURCE_KEYS,
            path=f"action_screen_extension.static_pdf_sources[{index}]", findings=findings,
        )
    action = _h2_closed_mapping(
        extension.get("action"), allowed=_H2_ACTION_KEYS,
        path="action_screen_extension.action", findings=findings,
    )
    _h2_closed_mapping(action.get("boundary"), allowed=_STAGE0_BOUNDARY_KEYS,
                       path="action_screen_extension.action.boundary", findings=findings)
    bridge = _h2_closed_mapping(
        action.get("issuer_scope_bridge"), allowed=_H2_ACTION_SCOPE_BRIDGE_KEYS,
        path="action_screen_extension.action.issuer_scope_bridge", findings=findings,
    )
    _validate_h2_evidence_shape(
        bridge.get("evidence"), path="action_screen_extension.action.issuer_scope_bridge.evidence", findings=findings,
    )
    specificity = _h2_closed_mapping(
        action.get("decision_specificity"), allowed=_H2_DECISION_SPECIFICITY_KEYS,
        path="action_screen_extension.action.decision_specificity", findings=findings,
    )
    _validate_h2_evidence_shape(
        specificity.get("evidence"), path="action_screen_extension.action.decision_specificity.evidence", findings=findings,
    )
    _validate_h2_evidence_shape(
        action.get("implementation_evidence"), path="action_screen_extension.action.implementation_evidence", findings=findings,
    )
    exposure = _h2_closed_mapping(
        action.get("exposure"), allowed=_H2_ACTION_EXPOSURE_KEYS,
        path="action_screen_extension.action.exposure", findings=findings,
    )
    _validate_h2_evidence_shape(
        exposure.get("evidence"), path="action_screen_extension.action.exposure.evidence", findings=findings,
    )
    for index, fact in enumerate(extension.get("cutoff_before_facts") if isinstance(extension.get("cutoff_before_facts"), list) else []):
        fact_map = _h2_closed_mapping(
            fact, allowed=_H2_FACT_KEYS,
            path=f"action_screen_extension.cutoff_before_facts[{index}]", findings=findings,
        )
        _validate_h2_evidence_shape(
            fact_map.get("evidence"), path=f"action_screen_extension.cutoff_before_facts[{index}].evidence", findings=findings,
        )
    pair = _h2_closed_mapping(
        extension.get("hypothesis_pair"), allowed=_H2_HYPOTHESIS_PAIR_KEYS,
        path="action_screen_extension.hypothesis_pair", findings=findings,
    )
    for name in ("primary", "strongest_rival"):
        _h2_closed_mapping(
            pair.get(name), allowed=_H2_HYPOTHESIS_KEYS,
            path=f"action_screen_extension.hypothesis_pair.{name}", findings=findings,
        )
    _h2_closed_mapping(
        pair.get("selection_basis"), allowed=_H2_SELECTION_BASIS_KEYS,
        path="action_screen_extension.hypothesis_pair.selection_basis", findings=findings,
    )
    for name, allowed in (("d2_observability", _H2_D2_KEYS), ("cost_driver_observability", _H2_COST_KEYS)):
        if name not in extension:
            continue
        observation = _h2_closed_mapping(
            extension.get(name), allowed=allowed, path=f"action_screen_extension.{name}", findings=findings,
        )
        _h2_closed_mapping(
            observation.get("boundary"), allowed=_STAGE0_BOUNDARY_KEYS,
            path=f"action_screen_extension.{name}.boundary", findings=findings,
        )
        for index, repetition in enumerate(observation.get("repetitions") if isinstance(observation.get("repetitions"), list) else []):
            repetition_map = _h2_closed_mapping(
                repetition, allowed=_H2_REPETITION_KEYS,
                path=f"action_screen_extension.{name}.repetitions[{index}]", findings=findings,
            )
            _validate_h2_evidence_shape(
                repetition_map.get("evidence"), path=f"action_screen_extension.{name}.repetitions[{index}].evidence", findings=findings,
            )


def _validate_h2_static_sources(
    extension: dict[str, Any], *, cutoff_at: Any, stage0_source_ids: set[str], findings: list[str],
) -> dict[str, dict[str, Any]]:
    sources = extension.get("static_pdf_sources")
    if not isinstance(sources, list) or not sources:
        _invalid(findings, "action_screen_extension.static_pdf_sources", "must_be_nonempty_list")
        return {}
    source_index: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(sources):
        path = f"action_screen_extension.static_pdf_sources[{index}]"
        if not isinstance(source, dict):
            _invalid(findings, path, "must_be_object")
            continue
        source_id = source.get("source_id")
        if not _text(source_id) or str(source_id) in source_index:
            _invalid(findings, f"{path}.source_id", "must_be_unique_nonempty")
            continue
        source_id = str(source_id)
        if source_id in stage0_source_ids:
            _invalid(findings, f"{path}.source_id", "must_not_redeclare_stage0_static_pdf")
            continue
        source_index[source_id] = source
        url = source.get("url")
        if not isinstance(url, str) or not re.fullmatch(
            r"https://static\.cninfo\.com\.cn/finalpage/.+\.pdf", url, re.IGNORECASE,
        ):
            _invalid(findings, f"{path}.url", "must_be_static_cninfo_finalpage_pdf")
        if source.get("source_type") not in candidate_contract.V4_OFFICIAL_EVIDENCE_SOURCE_TYPES:
            _invalid(findings, f"{path}.source_type", "must_be_official_static_disclosure")
        for field in ("issuer_id", "responsibility_unit_id", "perimeter_id", "unit"):
            if not _text(source.get(field)):
                _missing(findings, f"{path}.{field}")
        if not _stage0_source_is_strictly_before(source, cutoff_at):
            _invalid(findings, f"{path}.published_at", "must_be_strictly_before_screen_cutoff")
        field_refs = source.get("field_refs")
        if not isinstance(field_refs, list) or not field_refs or not all(
            _text(field_ref) and _PAGE_REFERENCE.search(str(field_ref)) for field_ref in field_refs
        ):
            _invalid(findings, f"{path}.field_refs", "must_contain_paged_field_references")
    return source_index


def _h2_screen_evidence_records(extension: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only action-screen citations, never source declarations themselves."""
    payload = {
        key: extension.get(key)
        for key in ("action", "cutoff_before_facts", "hypothesis_pair", "d2_observability", "cost_driver_observability")
        if key in extension
    }
    return _stage0_evidence_records(payload)


def _validate_h2_screen_sources(
    extension: dict[str, Any], *, h1_sources: dict[str, dict[str, Any]],
    h2_sources: dict[str, dict[str, Any]], findings: list[str],
) -> None:
    evidence_records = _h2_screen_evidence_records(extension)
    used: set[str] = set()
    sources = {**h1_sources, **h2_sources}
    for index, evidence in enumerate(evidence_records):
        path = f"action_screen_extension.evidence[{index}]"
        source_id = str(evidence.get("source_id") or "")
        source = sources.get(source_id)
        if source is None:
            _invalid(findings, f"{path}.source_id", "must_be_declared_action_screen_static_pdf")
            continue
        used.add(source_id)
        field_ref = evidence.get("field_ref")
        if field_ref not in source.get("field_refs", []):
            _invalid(findings, f"{path}.field_ref", "must_match_declared_action_screen_static_pdf_page")
        for field in (
            "source_type", "issuer_id", "responsibility_unit_id", "perimeter_id", "unit", "published_at",
        ):
            if evidence.get(field) != source.get(field):
                _invalid(findings, f"{path}.{field}", "must_match_declared_action_screen_static_pdf_identity")
    # H1 sources are a receipt-wide feasibility pool and need not all become
    # action-screen citations.  Every *new* H2 PDF, however, must be used now;
    # otherwise it would be an impermissible appendable reserve.
    for source_id in sorted(set(h2_sources) - used):
        _invalid(
            findings, "action_screen_extension.static_pdf_sources",
            "must_not_declare_unused_or_post_screen_source:" + source_id,
        )


def _project_stage0_legacy_cohort(package: dict[str, Any]) -> dict[str, Any]:
    """Adapt the stricter H1 feasibility record only inside the legacy validator."""
    cohort = {
        "schema_version": candidate_contract.V4_COHORT_FEASIBILITY_SCHEMA_VERSION,
        "cohort_id": package.get("cohort_id"),
        "industry_id": package.get("industry_id"),
        "selection_as_of": package.get("selection_as_of"),
        "universe": deepcopy(package.get("universe")),
        "members": deepcopy(package.get("members")),
    }
    if package.get("mechanism_topology") == "COST_RESTRUCTURING":
        for member in cohort["members"] if isinstance(cohort["members"], list) else []:
            if isinstance(member, dict) and "d2_field_availability" not in member and "cost_field_availability" in member:
                member["d2_field_availability"] = deepcopy(member["cost_field_availability"])
    return cohort


def _project_h2_legacy_manifest(stage0_package: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    """Make the old triage an internal predicate, not an alternate admission input."""
    h1_sources = stage0_package.get("static_pdf_sources") if isinstance(stage0_package.get("static_pdf_sources"), list) else []
    h2_sources = extension.get("static_pdf_sources") if isinstance(extension.get("static_pdf_sources"), list) else []
    static_sources = [*h1_sources, *h2_sources]
    source_allowlist = [
        {"source_id": source.get("source_id"), "published_at": source.get("published_at")}
        for source in static_sources if isinstance(source, dict)
    ]
    source_ids = [item["source_id"] for item in source_allowlist if _text(item.get("source_id"))]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": extension.get("screen_id"),
        "mechanism_topology": extension.get("mechanism_topology"),
        "cutoff_at": extension.get("cutoff_at"),
        "candidate_identity": deepcopy(extension.get("candidate_identity")),
        "cohort_feasibility_record": _project_stage0_legacy_cohort(stage0_package),
        "action": deepcopy(extension.get("action")),
        "cutoff_before_facts": deepcopy(extension.get("cutoff_before_facts")),
        "hypothesis_pair": deepcopy(extension.get("hypothesis_pair")),
        **({"d2_observability": deepcopy(extension.get("d2_observability"))} if "d2_observability" in extension else {}),
        **({"cost_driver_observability": deepcopy(extension.get("cost_driver_observability"))} if "cost_driver_observability" in extension else {}),
        "source_firewall": {
            "outcome_body_access": extension.get("source_firewall_attestation", {}).get("outcome_body_access"),
            "outcome_metadata_access": extension.get("source_firewall_attestation", {}).get("outcome_metadata_access"),
            "post_cutoff_sources_prohibited": extension.get("source_firewall_attestation", {}).get("post_cutoff_sources_prohibited"),
            "curator_attestation": "H2 action screen supplied by " + str(extension.get("curator_id") or ""),
            "discovery_entry": {
                "kind": KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF,
                "issuer_code_or_name_submitted_to_cninfo_fulltext": False,
                "cninfo_issuer_stock_or_detail_page_opened": False,
                "post_identification_access": POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY,
                "static_pdf_sources": [
                    {"url": source.get("url"), "source_id": source.get("source_id")}
                    for source in static_sources if isinstance(source, dict)
                ],
            },
            "access_receipt": {
                "schema_version": "phase10-pit-runner-attestation.v1",
                "runner": "phase10_pit_runner",
                "assurance_level": "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS",
                "state": "REVIEWABLE",
                "cutoff_at": extension.get("cutoff_at"),
                "allowed_source_ids": source_ids,
                "source_allowlist": source_allowlist,
            },
        },
    }


def validate_action_screen_static_extension(stage0_package: Any, extension: Any) -> dict[str, Any]:
    """Validate H2 against one accepted H1 cohort and project the legacy triage input.

    The returned legacy manifest is internal validation material.  Candidate
    admission must supply the H1 package plus this closed H2 extension, never
    a free-standing manifest that can append a company or source after screen
    formation.
    """
    findings: list[str] = []
    h1 = validate_stage0_static_source_package(stage0_package)
    if h1.get("state") != STAGE0_FEASIBILITY_REVIEWABLE:
        findings.append("invalid:stage0_static_package:must_be_h1_feasibility_reviewable")
        findings.extend("invalid:stage0_static_package." + str(item) for item in h1.get("findings", []))
    if not isinstance(stage0_package, dict):
        return {
            "schema_version": ACTION_SCREEN_STATIC_RESULT_SCHEMA_VERSION,
            "state": ACTION_SCREEN_REJECTED,
            "findings": findings,
            "does_not_grant": list(DOES_NOT_GRANT),
        }
    if not isinstance(extension, dict):
        findings.append("invalid:action_screen_extension:must_be_object")
        return {
            "schema_version": ACTION_SCREEN_STATIC_RESULT_SCHEMA_VERSION,
            "state": ACTION_SCREEN_REJECTED,
            "findings": findings,
            "does_not_grant": list(DOES_NOT_GRANT),
        }
    if extension.get("schema_version") != ACTION_SCREEN_STATIC_EXTENSION_SCHEMA_VERSION:
        _invalid(findings, "action_screen_extension.schema_version", "must_equal_action_screen_static_extension_v1")
    _validate_h2_closed_shape(extension, findings)
    if _h2_contains_forbidden_key(extension):
        _invalid(findings, "action_screen_extension", "must_not_contain_outcome_final_peer_or_new_cohort_material")
    for field in ("screen_id", "stage0_cohort_id", "stage0_selection_as_of", "curator_id"):
        _require_text(extension.get(field), f"action_screen_extension.{field}", findings)
    if extension.get("stage0_cohort_id") != stage0_package.get("cohort_id"):
        _invalid(findings, "action_screen_extension.stage0_cohort_id", "must_match_h1_cohort")
    if candidate_contract._time(extension.get("stage0_selection_as_of")) is None \
            or candidate_contract._time(extension.get("stage0_selection_as_of")) != candidate_contract._time(stage0_package.get("selection_as_of")):
        _invalid(findings, "action_screen_extension.stage0_selection_as_of", "must_match_h1_selection_as_of")
    h1_curator = _dict(stage0_package.get("curator_attestation")).get("curator_id")
    if extension.get("curator_id") != h1_curator:
        _invalid(findings, "action_screen_extension.curator_id", "must_match_h1_curator")
    cutoff = extension.get("cutoff_at")
    if candidate_contract._time(cutoff) is None:
        _invalid(findings, "action_screen_extension.cutoff_at", "must_be_timezone_aware_iso8601")
    expected_h2_topology = {
        "CUSTOMER_RESPONSE": candidate_contract.V4_CUSTOMER_RESPONSE_CHAIN,
        "COST_RESTRUCTURING": candidate_contract.V4_COST_RESTRUCTURING_CHAIN,
    }.get(stage0_package.get("mechanism_topology"))
    if extension.get("mechanism_topology") != expected_h2_topology:
        _invalid(findings, "action_screen_extension.mechanism_topology", "must_match_h1_mechanism_topology")
    identity = _dict(extension.get("candidate_identity"))
    candidate_company_id = identity.get("company_id")
    member = next(
        (item for item in stage0_package.get("members", [])
         if isinstance(item, dict) and item.get("company_id") == candidate_company_id),
        None,
    )
    if not isinstance(member, dict):
        _invalid(findings, "action_screen_extension.candidate_identity.company_id", "must_be_h1_cohort_member")
    elif any(identity.get(field) != member.get(field) for field in (
        "issuer_id", "responsibility_unit_id", "industry_id",
    )) or not candidate_contract._same_boundary(identity.get("common_boundary"), member.get("boundary")):
        _invalid(findings, "action_screen_extension.candidate_identity", "must_match_h1_member_identity")
    firewall = _dict(extension.get("source_firewall_attestation"))
    if firewall.get("outcome_body_access") != "UNREAD_AND_PROHIBITED" \
            or firewall.get("outcome_metadata_access") != "NONE" \
            or firewall.get("post_cutoff_sources_prohibited") is not True:
        _invalid(findings, "action_screen_extension.source_firewall_attestation", "must_seal_outcome_and_post_cutoff_access")
    h1_source_index = {
        str(source["source_id"]): source for source in stage0_package.get("static_pdf_sources", [])
        if isinstance(source, dict) and _text(source.get("source_id"))
    }
    h1_source_ids = set(h1_source_index)
    h2_sources = _validate_h2_static_sources(
        extension, cutoff_at=cutoff, stage0_source_ids=h1_source_ids, findings=findings,
    )
    _validate_h2_screen_sources(
        extension, h1_sources=h1_source_index, h2_sources=h2_sources, findings=findings,
    )
    projected = _project_h2_legacy_manifest(stage0_package, extension)
    triage = triage_selection_discovery_manifest(projected)
    if triage.get("state") != DISCOVERY_READY:
        findings.append("invalid:action_screen_extension:legacy_triage_not_ready")
        findings.extend("invalid:action_screen_extension." + str(item) for item in triage.get("findings", []))
    result = {
        "schema_version": ACTION_SCREEN_STATIC_RESULT_SCHEMA_VERSION,
        "state": ACTION_SCREEN_REVIEWABLE if not findings else ACTION_SCREEN_REJECTED,
        "findings": findings,
        "does_not_grant": list(DOES_NOT_GRANT),
    }
    if not findings:
        result["projected_legacy_manifest"] = projected
    return result


def triage_selection_discovery_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return only ``DISCOVERY_READY`` or precise pre-candidate ``NO_PRIMARY``.

    The result is intentionally stateless.  It does not write a candidate,
    construct a case directory, read a result package, or authorize any later
    training/feedback transition.
    """
    findings: list[str] = []
    if not isinstance(manifest, dict):
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "state": NO_PRIMARY,
            "findings": ["invalid:manifest:must_be_object"],
            "next_acquisition_package": [],
            "does_not_grant": list(DOES_NOT_GRANT),
        }
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        _invalid(findings, "schema_version", "must_equal_judgment_selection_discovery_manifest_v1")
    _require_text(manifest.get("manifest_id"), "manifest_id", findings)
    topology = manifest.get("mechanism_topology")
    if topology not in candidate_contract.V4_MECHANISM_TOPOLOGIES:
        _invalid(findings, "mechanism_topology", "must_be_customer_response_or_cost_restructuring_chain")
    cutoff = candidate_contract._time(manifest.get("cutoff_at"))
    if cutoff is None:
        _invalid(findings, "cutoff_at", "must_be_timezone_aware_iso8601")
    identity, boundary = _validate_identity(manifest, findings)
    known_fact_ids = _validate_cutoff_before_facts(
        manifest, cutoff=cutoff, identity=identity, boundary=boundary, findings=findings,
    )
    primary_id = _validate_hypothesis_pair(manifest, known_fact_ids, findings)
    _validate_action(manifest, cutoff=cutoff, identity=identity, boundary=boundary, findings=findings)
    cohort_result = candidate_contract.validate_v4_cohort_feasibility_record(
        manifest.get("cohort_feasibility_record"),
        action_at=candidate_contract._date_or_time(_dict(manifest.get("action")).get("implemented_or_incurred_at")),
        target_company_id=identity.get("company_id") if isinstance(identity, dict) else None,
        target_industry_id=identity.get("industry_id") if isinstance(identity, dict) else None,
    )
    findings.extend("invalid:" + item for item in cohort_result["findings"])
    _validate_current_cohort_admission_assessment(manifest, findings)
    if topology == candidate_contract.V4_CUSTOMER_RESPONSE_CHAIN:
        _validate_d2(
            manifest, cutoff=cutoff, identity=identity, boundary=boundary,
            primary_id=primary_id, findings=findings,
        )
    elif topology == candidate_contract.V4_COST_RESTRUCTURING_CHAIN:
        _validate_cost_driver(
            manifest, cutoff=cutoff, identity=identity, boundary=boundary,
            primary_id=primary_id, findings=findings,
        )
    _validate_firewall(manifest, findings)
    state = DISCOVERY_READY if not findings else NO_PRIMARY
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "state": state,
        "findings": findings,
        "next_acquisition_package": list(NEXT_V4_ACQUISITION_PACKAGE) if state == DISCOVERY_READY else [],
        "does_not_grant": list(DOES_NOT_GRANT),
    }


def _read_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest JSON must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cohort-only",
        action="store_true",
        required=True,
        help="validate a strict curator-supplied static-PDF Stage-0 package; does not select an action",
    )
    parser.add_argument("manifest", help="strict curator-supplied static Stage-0 package JSON")
    args = parser.parse_args(argv)
    try:
        packet = _read_manifest(args.manifest)
        result = validate_stage0_static_source_package(packet)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "schema_version": STAGE0_STATIC_RESULT_SCHEMA_VERSION,
            "state": INSUFFICIENT_STATIC_SOURCE_PACKAGE,
            "findings": [f"invalid:cohort_file:{exc}"],
            "does_not_grant": list(DOES_NOT_GRANT),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == STAGE0_FEASIBILITY_REVIEWABLE else 2


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
