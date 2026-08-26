#!/usr/bin/env python3
"""Pure reconstruction of a sealed Turtle V5 selection outcome.

This module consumes the one canonical V5 candidate bundle.  It does not adapt
V4, accept an alternate wrapper, read a database/file/network, or accept a
caller-supplied score/verdict.  Candidate admission and seal/access ordering
belong to their own slices; this function only recomputes D3/D4 from the
frozen target + EXTERNAL_SHOCK_COMPARATOR raw-field matrix.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import math
from statistics import median
from typing import Any


SELECTION_SCHEMA_VERSION = "judgment-selection-admission-v5.v1"
SELECTION_METHOD_EPOCH_ID = "JUDGMENT_SELECTION_ADMISSION_V5_2_COMPARATOR_PANEL"
OUTCOME_RECEIPTS_SCHEMA_VERSION = "judgment-v5-outcome-receipts.v1"
OUTCOME_RESOLUTION_SCHEMA_VERSION = "judgment-v5-outcome-resolution.v1"

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
RESTRUCTURING_CASH_FIELD = "restructuring_cash_paid"
RESTRUCTURING_TREATMENTS = {
    "IN_OCF_NO_ADDITIONAL_DEDUCTION",
    "SEPARATE_OPERATING_CASH_DEDUCTION",
    "OUT_OF_PERIMETER_CANNOT_SETTLE",
}
BOUNDARY_KINDS = {"MEASUREMENT", "SCOPE", "PANEL", "MECHANISM"}
RESTATEMENT_POLICIES = {"INITIAL_ONLY", "RESTATED_ONLY", "SAME_SERIES_ONLY"}
FORBIDDEN_OUTCOME_KEYS = {
    "verdict", "score", "prediction", "probability", "win_rate", "hit", "miss",
    "target_delta", "relative_delta", "peer_delta", "peer_median", "metric_value",
    "derived_value", "joint_verdict", "selection_verdict", "outcome_verdict",
}


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _instant(value: Any) -> datetime | None:
    text = _text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _source_time(source: dict[str, Any]) -> datetime | date | None:
    precision = _text(source.get("availability_precision"))
    value = _text(source.get("source_available_at"))
    if precision == "DATE_ONLY":
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    if precision == "INTRADAY":
        return _instant(value)
    return None


def _source_at_or_before_cutoff(source: dict[str, Any], cutoff: datetime) -> bool | None:
    available = _source_time(source)
    if available is None:
        return None
    if isinstance(available, datetime):
        return available <= cutoff
    # A date-only source carries no publication clock; the whole cutoff date is
    # contaminated rather than assigning it a convenient intra-day time.
    return available <= cutoff.date()


def _frozen_cell_key(cell: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _text(cell.get("issuer_id")),
        _text(cell.get("metric_id")),
        _text(cell.get("period_id")),
        _text(cell.get("field_id")),
    )


def _receipt_cell_key(cell: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _text(cell.get("issuer_id")),
        _text(cell.get("metric_id")),
        _text(cell.get("period_id")),
        _text(cell.get("field_id")),
    )


def _invalid(findings: list[str]) -> dict[str, Any]:
    return {"valid": False, "resolution": None, "findings": findings}


def _resolution(status: str, selection_freeze_id: str, **details: Any) -> dict[str, Any]:
    return {
        "schema_version": OUTCOME_RESOLUTION_SCHEMA_VERSION,
        "selection_freeze_id": selection_freeze_id,
        "status": status,
        **details,
    }


def _forbidden_outcome_paths(value: Any, *, path: str = "outcome_receipts") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if _text(key).lower() in FORBIDDEN_OUTCOME_KEYS:
                findings.append(f"{path}.{key}:caller_supplied_derived_outcome")
            findings.extend(_forbidden_outcome_paths(nested, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_forbidden_outcome_paths(nested, path=f"{path}[{index}]"))
    return findings


def _canonical_matrix_has_outcome_metadata(contract: dict[str, Any]) -> bool:
    """The sealed candidate declares identities, never outcome source metadata."""
    allowed_contract = {"frozen_raw_matrix", "fiscal_calendar_bridge"}
    allowed_cell = {
        "issuer_id", "metric_id", "period_id", "observation_role", "field_id",
        "economic_period", "perimeter_id", "currency_and_unit", "field_locator",
    }
    allowed_period = {"start", "end"}
    allowed_bridge = {"status", "bridge_id", "comparison_window_id"}
    if set(contract) - allowed_contract:
        return True
    bridge = _obj(contract.get("fiscal_calendar_bridge"))
    if set(bridge) - allowed_bridge:
        return True
    for cell in _items(contract.get("frozen_raw_matrix")):
        if not isinstance(cell, dict) or set(cell) - allowed_cell:
            return True
        if set(_obj(cell.get("economic_period"))) - allowed_period:
            return True
    return False


def _metric_by_clock(bundle: dict[str, Any], findings: list[str]) -> dict[str, dict[str, Any]]:
    metrics = _items(bundle.get("measurement_contracts"))
    by_clock: dict[str, dict[str, Any]] = {}
    if len(metrics) != 2:
        findings.append("measurement_contracts_must_contain_exactly_d3_and_d4")
    for index, value in enumerate(metrics):
        metric = _obj(value)
        clock = _text(metric.get("clock"))
        metric_id = _text(metric.get("metric_id"))
        if clock not in {"D3", "D4"} or not metric_id or clock in by_clock:
            findings.append(f"measurement_contracts[{index}]:clock_or_metric_id_invalid")
            continue
        by_clock[clock] = metric
    if set(by_clock) != {"D3", "D4"}:
        findings.append("measurement_contracts_must_contain_one_d3_and_one_d4")
    if len({_text(metric.get("metric_id")) for metric in by_clock.values()}) != 2:
        findings.append("measurement_contracts_metric_ids_must_be_distinct")
    return by_clock


def _d3_fields(metric: dict[str, Any], findings: list[str]) -> tuple[str, ...]:
    fields = tuple(_text(item) for item in _items(metric.get("formula_and_ordered_raw_fields")))
    formula = _obj(metric.get("outcome_formula"))
    if metric.get("economic_construct") != "OPERATING_CONTRIBUTION_AMOUNT":
        findings.append("D3.economic_construct_not_supported_in_slice0")
    if formula.get("formula_type") != "LINEAR_COMBINATION":
        findings.append("D3.outcome_formula_must_be_linear_combination")
    terms = _items(formula.get("terms"))
    if not fields or not terms or _text(formula.get("denominator_field_id")):
        findings.append("D3.outcome_formula_fields_or_denominator_invalid")
    term_ids: list[str] = []
    for index, term in enumerate(terms):
        item = _obj(term)
        field_id = _text(item.get("field_id"))
        coefficient = _number(item.get("coefficient"))
        if field_id not in fields or coefficient is None or coefficient == 0:
            findings.append(f"D3.outcome_formula.terms[{index}]:invalid")
        term_ids.append(field_id)
    if len(set(fields)) != len(fields) or len(set(term_ids)) != len(term_ids) or set(term_ids) != set(fields):
        findings.append("D3.outcome_formula_must_cover_each_frozen_raw_field_once")
    return fields


def _d4_fields(metric: dict[str, Any], findings: list[str]) -> tuple[str, ...]:
    treatment = _text(metric.get("restructuring_cash_treatment"))
    declared = tuple(_text(item) for item in _items(metric.get("formula_and_ordered_raw_fields")))
    if metric.get("formula_id") != D4_FORMULA_ID or metric.get("economic_construct") != "CONSERVATIVE_OWNER_CASH":
        findings.append("D4.formula_or_construct_invalid")
    if treatment not in RESTRUCTURING_TREATMENTS:
        findings.append("D4.restructuring_cash_treatment_invalid")
        return declared
    expected = D4_REQUIRED_RAW_FIELDS + ((RESTRUCTURING_CASH_FIELD,) if treatment == "SEPARATE_OPERATING_CASH_DEDUCTION" else ())
    if declared != expected:
        findings.append("D4.formula_and_ordered_raw_fields_not_canonical_for_treatment")
    return declared


def _thresholds(metric: dict[str, Any], clock: str, findings: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    discriminability = _obj(metric.get("discriminability"))
    primary = _obj(discriminability.get("primary_threshold"))
    rival = _obj(discriminability.get("rival_threshold"))
    for label, threshold in (("primary", primary), ("rival", rival)):
        if _text(threshold.get("operator")) not in {"GTE", "LTE"} or _number(threshold.get("value")) is None:
            findings.append(f"{clock}.discriminability.{label}_threshold_invalid")
    return primary, rival


def _validate_bundle(bundle: Any) -> tuple[
    list[str], str, datetime | None, str, list[str], dict[str, dict[str, Any]],
    dict[tuple[str, str, str, str], dict[str, Any]], set[tuple[str, str, str, str]],
]:
    findings: list[str] = []
    if not isinstance(bundle, dict):
        return ["selection_bundle:not_object"], "", None, "", [], {}, {}, set()
    if bundle.get("schema_version") != SELECTION_SCHEMA_VERSION:
        findings.append("selection_bundle.schema_version_invalid")
    if bundle.get("method_epoch_id") != SELECTION_METHOD_EPOCH_ID:
        findings.append("selection_bundle.method_epoch_invalid")
    if bundle.get("selection_goal") != "SELECTION":
        findings.append("selection_bundle.selection_goal_must_be_selection")
    freeze_id = _text(bundle.get("selection_freeze_id"))
    if not freeze_id:
        findings.append("selection_bundle.selection_freeze_id_missing")
    cutoff = _instant(_obj(bundle.get("time_contract")).get("research_cutoff_at"))
    if cutoff is None:
        findings.append("time_contract.research_cutoff_at_invalid")
    panel = _obj(bundle.get("counterfactual_panel"))
    target = _text(panel.get("target_issuer_id"))
    if not target:
        findings.append("counterfactual_panel.target_issuer_id_missing")
    comparators: list[str] = []
    seen: set[str] = set()
    for index, member_value in enumerate(_items(panel.get("members"))):
        member = _obj(member_value)
        issuer_id = _text(member.get("issuer_id"))
        role = _text(member.get("causal_role"))
        if not issuer_id or issuer_id == target or issuer_id in seen:
            findings.append(f"counterfactual_panel.members[{index}]:issuer_id_invalid")
        seen.add(issuer_id)
        if role == "EXTERNAL_SHOCK_COMPARATOR":
            comparators.append(issuer_id)
    if len(comparators) < 2:
        findings.append("counterfactual_panel.requires_at_least_two_external_shock_comparators")
    if target in comparators or any(not item for item in comparators):
        findings.append("counterfactual_panel.comparator_identity_invalid")
    metrics = _metric_by_clock(bundle, findings)
    fields_by_clock: dict[str, tuple[str, ...]] = {}
    for clock, metric in metrics.items():
        fields_by_clock[clock] = _d3_fields(metric, findings) if clock == "D3" else _d4_fields(metric, findings)
        _thresholds(metric, clock, findings)

    contract = _obj(bundle.get("outcome_contract"))
    if _canonical_matrix_has_outcome_metadata(contract):
        findings.append("outcome_contract_contains_noncanonical_or_outcome_source_metadata")
    bridge = _obj(contract.get("fiscal_calendar_bridge"))
    if _text(bridge.get("status")) not in {"NOT_REQUIRED", "FROZEN"}:
        findings.append("outcome_contract.fiscal_calendar_bridge.status_invalid")
    if bridge.get("status") == "FROZEN" and (not _text(bridge.get("bridge_id")) or not _text(bridge.get("comparison_window_id"))):
        findings.append("outcome_contract.fiscal_calendar_bridge.frozen_identity_missing")

    matrix: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    metric_by_id = {_text(metric.get("metric_id")): (clock, metric) for clock, metric in metrics.items()}
    eligible_issuers = {target, *comparators}
    for index, row_value in enumerate(_items(contract.get("frozen_raw_matrix"))):
        row = _obj(row_value)
        key = _frozen_cell_key(row)
        if not all(key):
            findings.append(f"outcome_contract.frozen_raw_matrix[{index}]:identity_missing")
            continue
        if key in matrix:
            findings.append(f"outcome_contract.frozen_raw_matrix[{index}]:duplicate_cell")
        matrix[key] = row
        issuer_id, metric_id, _period_id, field_id = key
        if issuer_id not in eligible_issuers:
            findings.append(f"outcome_contract.frozen_raw_matrix[{index}]:issuer_not_target_or_external_comparator")
        expected = metric_by_id.get(metric_id)
        if expected is None:
            findings.append(f"outcome_contract.frozen_raw_matrix[{index}]:metric_identity_invalid")
            continue
        clock = expected[0]
        if field_id not in fields_by_clock.get(clock, ()):
            findings.append(f"outcome_contract.frozen_raw_matrix[{index}]:field_not_in_metric_formula")
        if _text(row.get("observation_role")) not in {"BASELINE", "PRIMARY_OUTCOME", "EARLY_ARROW_NON_VOTER"}:
            findings.append(f"outcome_contract.frozen_raw_matrix[{index}]:observation_role_invalid")
        period = _obj(row.get("economic_period"))
        if _instant(period.get("start")) is None or _instant(period.get("end")) is None:
            findings.append(f"outcome_contract.frozen_raw_matrix[{index}]:economic_period_invalid")

    required: set[tuple[str, str, str, str]] = set()
    for clock, metric in metrics.items():
        metric_id = _text(metric.get("metric_id"))
        baseline_period = _text(metric.get("baseline_period_id"))
        primary_period = _text(metric.get("primary_outcome_period_id"))
        if not baseline_period or not primary_period or baseline_period == primary_period:
            findings.append(f"{clock}.baseline_or_primary_outcome_period_identity_invalid")
            continue
        for issuer_id in [target, *comparators]:
            for period_id, required_role in ((baseline_period, "BASELINE"), (primary_period, "PRIMARY_OUTCOME")):
                for field_id in fields_by_clock.get(clock, ()):
                    key = (issuer_id, metric_id, period_id, field_id)
                    row = matrix.get(key)
                    if row is None:
                        findings.append("outcome_contract.frozen_raw_matrix:required_cell_missing:" + ":".join(key))
                    elif row.get("observation_role") != required_role:
                        findings.append("outcome_contract.frozen_raw_matrix:baseline_or_primary_role_mismatch:" + ":".join(key))
                    required.add(key)
    return findings, freeze_id, cutoff, target, comparators, metrics, matrix, required


def _validate_receipts(
    receipts: Any,
    matrix: dict[tuple[str, str, str, str], dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    findings: list[str],
) -> tuple[dict[tuple[str, str, str, str], dict[str, Any]], list[dict[str, Any]], bool]:
    if not isinstance(receipts, dict):
        findings.append("outcome_receipts:not_object")
        return {}, [], False
    if receipts.get("schema_version") != OUTCOME_RECEIPTS_SCHEMA_VERSION:
        findings.append("outcome_receipts.schema_version_invalid")
    findings.extend(_forbidden_outcome_paths(receipts))
    attestation = _obj(receipts.get("custodian_attestation"))
    safe = attestation.get("research_side_outcome_exposure") == "NONE"
    if not _text(attestation.get("custodian_id")):
        findings.append("outcome_receipts.custodian_attestation.custodian_id_missing")
    if not safe:
        findings.append("outcome_receipts.research_side_outcome_exposure_requires_control_plane_breach")
    cells: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    if not isinstance(receipts.get("raw_cells"), list):
        findings.append("outcome_receipts.raw_cells_not_list")
    for index, cell_value in enumerate(_items(receipts.get("raw_cells"))):
        cell = _obj(cell_value)
        key = _receipt_cell_key(cell)
        if not all(key) or key not in matrix:
            findings.append(f"outcome_receipts.raw_cells[{index}]:cell_not_in_frozen_matrix")
            continue
        if key in cells:
            findings.append(f"outcome_receipts.raw_cells[{index}]:duplicate_cell")
        expected_clock = next((clock for clock, metric in metrics.items() if metric.get("metric_id") == key[1]), "")
        if cell.get("clock") != expected_clock:
            findings.append(f"outcome_receipts.raw_cells[{index}]:clock_does_not_match_frozen_metric")
        if _number(cell.get("value")) is None:
            findings.append(f"outcome_receipts.raw_cells[{index}]:value_invalid")
        source = _obj(cell.get("source"))
        if not _text(source.get("source_id")) or _source_time(source) is None:
            findings.append(f"outcome_receipts.raw_cells[{index}]:source_identity_or_availability_invalid")
        if source.get("filing_identity") not in {"INITIAL", "RESTATED"}:
            findings.append(f"outcome_receipts.raw_cells[{index}]:filing_identity_invalid")
        cells[key] = cell
    if not isinstance(receipts.get("boundary_facts", []), list):
        findings.append("outcome_receipts.boundary_facts_not_list")
    boundary_facts: list[dict[str, Any]] = []
    for index, fact_value in enumerate(_items(receipts.get("boundary_facts"))):
        fact = _obj(fact_value)
        if fact.get("boundary_kind") not in BOUNDARY_KINDS:
            findings.append(f"outcome_receipts.boundary_facts[{index}]:boundary_kind_invalid")
        source = _obj(fact.get("source"))
        if not _text(source.get("source_id")) or _source_time(source) is None:
            findings.append(f"outcome_receipts.boundary_facts[{index}]:source_identity_or_availability_invalid")
        boundary_facts.append(fact)
    return cells, boundary_facts, safe


def _early_primary_sources(
    cells: dict[tuple[str, str, str, str], dict[str, Any]],
    matrix: dict[tuple[str, str, str, str], dict[str, Any]],
    boundary_facts: list[dict[str, Any]], cutoff: datetime,
) -> list[str]:
    source_ids: list[str] = []
    for key, cell in cells.items():
        if _obj(matrix.get(key)).get("observation_role") != "PRIMARY_OUTCOME":
            continue
        if _source_at_or_before_cutoff(_obj(cell.get("source")), cutoff):
            source_ids.append(_text(_obj(cell.get("source")).get("source_id")))
    for fact in boundary_facts:
        if _source_at_or_before_cutoff(_obj(fact.get("source")), cutoff):
            source_ids.append(_text(_obj(fact.get("source")).get("source_id")))
    return sorted(set(source_ids))


def _restatement_measurement_boundary(
    metrics: dict[str, dict[str, Any]],
    cells: dict[tuple[str, str, str, str], dict[str, Any]],
    required: set[tuple[str, str, str, str]],
) -> list[str]:
    affected: list[str] = []
    for clock, metric in metrics.items():
        metric_id = _text(metric.get("metric_id"))
        sources = [_obj(cells[key].get("source")) for key in required if key[1] == metric_id and key in cells]
        identities = {_text(source.get("filing_identity")) for source in sources}
        policy = metric.get("restatement_or_reclassification_policy")
        invalid = (
            (policy == "INITIAL_ONLY" and identities != {"INITIAL"})
            or (policy == "RESTATED_ONLY" and identities != {"RESTATED"})
        )
        if policy == "SAME_SERIES_ONLY":
            series = {_text(source.get("restatement_series_id")) for source in sources}
            invalid = not series or "" in series or len(series) != 1
        if invalid:
            affected.append(clock)
    return affected


def _calendar_diagnostic(
    bundle: dict[str, Any], metrics: dict[str, dict[str, Any]], target: str, comparators: list[str],
    matrix: dict[tuple[str, str, str, str], dict[str, Any]],
) -> tuple[bool, list[str]]:
    bridge = _obj(_obj(bundle.get("outcome_contract")).get("fiscal_calendar_bridge"))
    status = bridge.get("status")
    reasons: list[str] = []
    for clock, metric in metrics.items():
        metric_id = _text(metric.get("metric_id"))
        for observation, period_id in (
            ("BASELINE", _text(metric.get("baseline_period_id"))),
            ("PRIMARY_OUTCOME", _text(metric.get("primary_outcome_period_id"))),
        ):
            rows = [
                row for key, row in matrix.items()
                if key[1] == metric_id and key[2] == period_id and key[0] in {target, *comparators}
            ]
            if any(row.get("observation_role") != observation for row in rows):
                reasons.append(f"observation_role_not_primary_or_baseline:{clock}:{period_id}")
                continue
            if status == "FROZEN":
                # The bridge identity is frozen once at contract level.  The
                # raw matrix carries no duplicated outcome source/bridge data.
                if not _text(bridge.get("bridge_id")) or not _text(bridge.get("comparison_window_id")):
                    reasons.append(f"fiscal_bridge_identity_missing:{clock}:{period_id}")
                continue
            windows = {
                (_text(_obj(row.get("economic_period")).get("start")), _text(_obj(row.get("economic_period")).get("end")))
                for row in rows
            }
            if len(windows) != 1:
                reasons.append(f"unfrozen_fiscal_calendar_difference:{clock}:{period_id}")
    return not reasons, reasons


def _values_for(
    issuer_id: str, metric_id: str, period_id: str, fields: tuple[str, ...],
    cells: dict[tuple[str, str, str, str], dict[str, Any]],
) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for field_id in fields:
        cell = cells.get((issuer_id, metric_id, period_id, field_id))
        value = _number(_obj(cell).get("value"))
        if value is None:
            return None
        values[field_id] = value
    return values


def _compute_d3(metric: dict[str, Any], values: dict[str, float]) -> float | None:
    total = 0.0
    for term in _items(_obj(metric.get("outcome_formula")).get("terms")):
        field_id = _text(_obj(term).get("field_id"))
        coefficient = _number(_obj(term).get("coefficient"))
        if coefficient is None or field_id not in values:
            return None
        total += coefficient * values[field_id]
    return total


def _compute_d4(metric: dict[str, Any], values: dict[str, float]) -> float | None:
    if any(field not in values for field in D4_REQUIRED_RAW_FIELDS):
        return None
    beginning_cwc = (
        values["beginning_accounts_receivable"] + values["beginning_prepayments"] + values["beginning_inventory"]
        - values["beginning_accounts_payable"] - values["beginning_contract_liabilities_or_customer_advances"]
    )
    ending_cwc = (
        values["ending_accounts_receivable"] + values["ending_prepayments"] + values["ending_inventory"]
        - values["ending_accounts_payable"] - values["ending_contract_liabilities_or_customer_advances"]
    )
    owner_cash = (
        values["cash_from_operating_activities"]
        - values["cash_paid_for_all_long_lived_asset_purchases"]
        - max(beginning_cwc - ending_cwc, 0.0)
    )
    if metric.get("restructuring_cash_treatment") == "SEPARATE_OPERATING_CASH_DEDUCTION":
        if RESTRUCTURING_CASH_FIELD not in values:
            return None
        owner_cash -= values[RESTRUCTURING_CASH_FIELD]
    return owner_cash


def _threshold_holds(threshold: dict[str, Any], relative_delta: float) -> bool:
    value = _number(threshold.get("value"))
    if value is None:
        return False
    return relative_delta >= value if threshold.get("operator") == "GTE" else relative_delta <= value


def _resolve_metric(
    clock: str, metric: dict[str, Any], target: str, comparators: list[str],
    cells: dict[tuple[str, str, str, str], dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    metric_id = _text(metric.get("metric_id"))
    fields = tuple(_text(item) for item in _items(metric.get("formula_and_ordered_raw_fields")))
    baseline_id = _text(metric.get("baseline_period_id"))
    outcome_id = _text(metric.get("primary_outcome_period_id"))
    compute = _compute_d3 if clock == "D3" else _compute_d4
    target_baseline = compute(metric, _values_for(target, metric_id, baseline_id, fields, cells) or {})
    target_outcome = compute(metric, _values_for(target, metric_id, outcome_id, fields, cells) or {})
    if target_baseline is None or target_outcome is None:
        return None, "UNKNOWN"
    comparator_rows: list[dict[str, Any]] = []
    comparator_deltas: list[float] = []
    for issuer_id in comparators:
        baseline = compute(metric, _values_for(issuer_id, metric_id, baseline_id, fields, cells) or {})
        outcome = compute(metric, _values_for(issuer_id, metric_id, outcome_id, fields, cells) or {})
        if baseline is None or outcome is None:
            return None, "UNKNOWN"
        delta = outcome - baseline
        comparator_deltas.append(delta)
        comparator_rows.append({"issuer_id": issuer_id, "baseline": baseline, "outcome": outcome, "delta": delta})
    target_delta = target_outcome - target_baseline
    median_delta = median(comparator_deltas)
    relative_delta = target_delta - median_delta
    discriminability = _obj(metric.get("discriminability"))
    primary = _threshold_holds(_obj(discriminability.get("primary_threshold")), relative_delta)
    rival = _threshold_holds(_obj(discriminability.get("rival_threshold")), relative_delta)
    direction = "H_A" if primary and not rival else "H_B" if rival and not primary else "NOT_DIAGNOSTIC"
    return {
        "clock": clock,
        "metric_id": metric_id,
        "formula_id": _text(metric.get("formula_id")),
        "target": {"issuer_id": target, "baseline": target_baseline, "outcome": target_outcome, "delta": target_delta},
        "comparators": comparator_rows,
        "median_comparator_delta": median_delta,
        "relative_delta": relative_delta,
        "supports_hypothesis": direction,
    }, direction


def resolve_v5_outcome(selection_bundle: dict[str, Any], outcome_receipts: dict[str, Any]) -> dict[str, Any]:
    """Recompute a V5 outcome from canonical sealed raw receipts only.

    Control-plane assumptions: the candidate has been independently admitted and
    sealed; an authorized custodian supplied these receipts.  If researcher
    exposure is confirmed, the caller must record a PIT breach in the control
    plane—this pure reconstructor refuses to repair it.
    """
    findings, freeze_id, cutoff, target, comparators, metrics, matrix, required = _validate_bundle(selection_bundle)
    cells, boundary_facts, safe_attestation = _validate_receipts(outcome_receipts, matrix, metrics, findings)
    if findings:
        return _invalid(findings)
    if not safe_attestation:
        return _invalid(["outcome_receipts.research_side_outcome_exposure_requires_control_plane_breach"])
    assert cutoff is not None

    early_sources = _early_primary_sources(cells, matrix, boundary_facts, cutoff)
    if early_sources:
        return {
            "valid": True,
            "resolution": _resolution("EXPOSURE_EXCLUDED", freeze_id, early_source_ids=early_sources),
            "findings": ["primary_outcome_source_available_at_or_before_research_cutoff"],
        }
    if metrics["D4"].get("restructuring_cash_treatment") == "OUT_OF_PERIMETER_CANNOT_SETTLE":
        return {
            "valid": True,
            "resolution": _resolution("BOUNDARY_CAPTURED", freeze_id, boundary_kinds=["SCOPE"], affected_clocks=["D4"]),
            "findings": ["d4_restructuring_cash_is_out_of_frozen_accounting_perimeter"],
        }
    boundary_kinds = sorted({fact.get("boundary_kind") for fact in boundary_facts if fact.get("boundary_kind") in BOUNDARY_KINDS})
    if boundary_kinds:
        return {
            "valid": True,
            "resolution": _resolution("BOUNDARY_CAPTURED", freeze_id, boundary_kinds=boundary_kinds),
            "findings": ["outcome_fact_invalidates_frozen_" + kind.lower() for kind in boundary_kinds],
        }
    missing = sorted(required - set(cells))
    if missing:
        return {
            "valid": True,
            "resolution": _resolution("UNKNOWN", freeze_id, missing_raw_cells=[":".join(key) for key in missing]),
            "findings": ["required_frozen_raw_cell_unavailable"],
        }
    restatement = _restatement_measurement_boundary(metrics, cells, required)
    if restatement:
        return {
            "valid": True,
            "resolution": _resolution("BOUNDARY_CAPTURED", freeze_id, boundary_kinds=["MEASUREMENT"], affected_clocks=restatement),
            "findings": ["frozen_restatement_or_reclassification_policy_violated"],
        }
    calendar_ok, calendar_findings = _calendar_diagnostic(selection_bundle, metrics, target, comparators, matrix)
    if not calendar_ok:
        return {
            "valid": True,
            "resolution": _resolution("NOT_DIAGNOSTIC", freeze_id, diagnostic_reasons=calendar_findings),
            "findings": ["fiscal_calendar_or_primary_window_not_diagnostic"],
        }
    results: dict[str, dict[str, Any]] = {}
    directions: list[str] = []
    for clock in ("D3", "D4"):
        result, direction = _resolve_metric(clock, metrics[clock], target, comparators, cells)
        if direction == "UNKNOWN" or result is None:
            return {
                "valid": True,
                "resolution": _resolution("UNKNOWN", freeze_id, missing_raw_cells=[]),
                "findings": ["required_frozen_raw_cell_unavailable_or_uncomputable"],
            }
        results[clock] = result
        directions.append(direction)
    if "NOT_DIAGNOSTIC" in directions:
        return {
            "valid": True,
            "resolution": _resolution("NOT_DIAGNOSTIC", freeze_id, metric_results=results),
            "findings": ["frozen_discriminability_rules_do_not_select_exactly_one_hypothesis"],
        }
    if len(set(directions)) != 1:
        return {
            "valid": True,
            "resolution": _resolution("MIXED", freeze_id, metric_results=results),
            "findings": ["d3_and_d4_support_opposite_frozen_hypotheses"],
        }
    status = "A_ONLY" if directions[0] == "H_A" else "B_ONLY"
    return {
        "valid": True,
        "resolution": _resolution(status, freeze_id, metric_results=results),
        "findings": ["d3_and_d4_independently_support_same_frozen_hypothesis"],
    }
