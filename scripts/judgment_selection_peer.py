#!/usr/bin/env python3
"""Pure V4 peer-relative selection bindings and outcome derivation.

V4 keeps the historical selection episode as one target-company episode.  A
frozen peer panel is an observation control, not a second set of claims, a
score, or a source of investment returns.  This module consequently has no
database or file-system dependency: callers supply the already frozen
candidate/source/measurement artifacts and the custodian outcome.

The raw outcome shape intentionally contains *only* source-backed input
fields.  For every frozen panel member it records ``reference_raw`` and
``outcome_raw`` dictionaries.  Each carries the frozen D3/D4 formula IDs and
a ``fields`` dictionary with the five D3 fields and the twelve D4
cash/working-capital fields.  Each field is a source-bearing object::

  {"value": 1.0, "unit": "RMB", "source_id": "...",
   "source_type": "CNINFO_OFFICIAL_AUDITED_ANNUAL_REPORT",
   "issuer_id": "CN:...", "period_end": "YYYY-MM-DD",
   "perimeter_id": "LISTED_CONSOLIDATED_ISSUER", "field_ref": "..."}

The frozen source contract states the member identity, expected issuer,
perimeter, reference/outcome periods, permitted source types and exact field
references.  That lets a validator reject a peer replacement, source/issuer/
period/perimeter/field drift without treating a convenient derived metric as
evidence.  Scalars, margins, deltas and the peer median are recomputed here.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import median
from typing import Any


V4_ADMISSION_VERSION = "JUDGMENT_SELECTION_ADMISSION_V4"
PEER_RELATIVE_METHOD = "DELTA_VS_PEER_MEDIAN"
PEER_RELATIVE_UNIT = "ratio"
PEER_RELATIVE_CONJUNCTION = "D3_AND_D4"
PEER_RELATIVE_STEP_FORMULA = (
    "MAX_TARGET_ABSOLUTE_STEP_PER_REFERENCE_REVENUE_AND_"
    "PREACTION_PEER_RELATIVE_SCALED_MAD"
)
PEER_REQUIRED_STAGE_IDS = {
    "D3_UNIT_ECONOMICS",
    "D4_WORKING_CAPITAL_AND_CASH",
}
D3_FIELDS = (
    "operating_revenue_rmb",
    "operating_cost_rmb",
    "taxes_and_surcharges_rmb",
    "selling_expense_rmb",
    "administrative_expense_rmb",
)
D4_FIELDS = (
    "operating_cash_flow_rmb",
    "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb",
    "opening_accounts_receivable_rmb",
    "opening_prepayments_rmb",
    "opening_inventory_rmb",
    "opening_accounts_payable_rmb",
    "opening_customer_advances_rmb",
    "ending_accounts_receivable_rmb",
    "ending_prepayments_rmb",
    "ending_inventory_rmb",
    "ending_accounts_payable_rmb",
    "ending_customer_advances_rmb",
)
ALL_RAW_FIELDS = D3_FIELDS + D4_FIELDS
_OUTCOME_CALLER_DERIVATION_KEYS = {
    "peer_verdict",
    "peer_score",
    "peer_relative_verdict",
    "peer_relative_score",
    "relative_verdict",
    "relative_score",
    "target_delta",
    "median_peer_delta",
    "peer_median_delta",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _date_or_time(value: Any) -> datetime | None:
    """Parse a contract date or an ISO-8601 instant into UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if len(candidate) == 10:
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _is_v4(candidate: dict[str, Any]) -> bool:
    return _dict(candidate.get("peer_panel_observability")).get("gate_version") == V4_ADMISSION_VERSION


def _candidate_panel(candidate: dict[str, Any]) -> dict[str, Any]:
    return _dict(candidate.get("peer_panel_observability"))


def _candidate_order(candidate: dict[str, Any]) -> list[str]:
    order = _dict(_candidate_panel(candidate).get("frozen_panel")).get("frozen_order")
    return [_text(item) for item in order] if isinstance(order, list) else []


def _relative_method(value: Any) -> dict[str, Any]:
    return _dict(value).get("relative_method") if isinstance(_dict(value).get("relative_method"), dict) else {}


def _method_identity(value: Any) -> tuple[str, str, str, str]:
    method = _relative_method(value)
    return (
        _text(method.get("method")),
        _text(method.get("reference_period_end")),
        _text(method.get("unit")),
        _text(method.get("conjunction")),
    )


def _member_rows(value: Any) -> list[dict[str, Any]]:
    rows = _dict(value).get("members")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _member_order(value: Any) -> list[str]:
    bundle = _dict(value)
    frozen_order = bundle.get("frozen_order")
    if isinstance(frozen_order, list):
        return [_text(item) for item in frozen_order]
    return [_text(row.get("company_id")) for row in _member_rows(value)]


def _member_by_company(value: Any) -> dict[str, dict[str, Any]]:
    return {_text(row.get("company_id")): row for row in _member_rows(value) if _text(row.get("company_id"))}


def _expected_member_identities(candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    panel = _candidate_panel(candidate)
    members = [_dict(panel.get("target"))] + [row for row in panel.get("peers") or [] if isinstance(row, dict)]
    return {_text(row.get("company_id")): row for row in members if _text(row.get("company_id"))}


def _candidate_formula_ids(candidate: dict[str, Any]) -> tuple[str, str]:
    cash = _dict(candidate.get("cash_transmission_observability"))
    d3_formula_id = ""
    for leg in cash.get("transmission_legs") or []:
        if isinstance(leg, dict) and leg.get("leg_id") == "OPERATING_CONTRIBUTION":
            d3_formula_id = _text(_dict(leg.get("official_field_identity")).get("field_id"))
            break
    d4_formula_id = _text(_dict(cash.get("d4_formula")).get("formula_id"))
    return d3_formula_id, d4_formula_id


def _candidate_action_at(candidate: dict[str, Any]) -> datetime | None:
    cash = _dict(candidate.get("cash_transmission_observability"))
    anchors = _dict(cash.get("materiality_anchors"))
    action = _dict(anchors.get("action_exposure"))
    return _date_or_time(action.get("implemented_or_incurred_at"))


def _candidate_reference(member: dict[str, Any], reference_period_end: str) -> dict[str, Any]:
    for row in member.get("annual_d3_d4_raw_observations") or []:
        if isinstance(row, dict) and row.get("period_end") == reference_period_end:
            return row
    return {}


def _candidate_reference_contract(
    member: dict[str, Any], reference_period_end: str,
) -> dict[str, Any]:
    reference = _candidate_reference(member, reference_period_end)
    d3_fields = _dict(reference.get("d3_raw_fields"))
    return {
        "period_end": reference_period_end,
        "d3_formula_id": reference.get("d3_formula_id"),
        "d4_formula_id": reference.get("d4_formula_id"),
        "reference_revenue": _dict(d3_fields.get("operating_revenue_rmb")).get("value"),
        "fields": {**d3_fields, **_dict(reference.get("d4_raw_fields"))},
    }


def _stage_value_from_fields(fields: dict[str, Any], stage_id: str) -> float | None:
    values = {name: _number(_dict(fields.get(name)).get("value")) for name in ALL_RAW_FIELDS}
    if any(value is None for value in values.values()):
        return None
    if stage_id == "D3_UNIT_ECONOMICS":
        return (
            values["operating_revenue_rmb"]
            - values["operating_cost_rmb"]
            - values["taxes_and_surcharges_rmb"]
            - values["selling_expense_rmb"]
            - values["administrative_expense_rmb"]
        )
    opening = (
        values["opening_accounts_receivable_rmb"]
        + values["opening_prepayments_rmb"]
        + values["opening_inventory_rmb"]
        - values["opening_accounts_payable_rmb"]
        - values["opening_customer_advances_rmb"]
    )
    ending = (
        values["ending_accounts_receivable_rmb"]
        + values["ending_prepayments_rmb"]
        + values["ending_inventory_rmb"]
        - values["ending_accounts_payable_rmb"]
        - values["ending_customer_advances_rmb"]
    )
    return (
        values["operating_cash_flow_rmb"]
        - values["cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb"]
        - max(opening - ending, 0.0)
    )


def _candidate_stage_thresholds(
    candidate: dict[str, Any], stage_id: str,
) -> dict[str, Any] | None:
    """Recompute the V4 stage step and its target reference denominator."""
    panel = _candidate_panel(candidate)
    target = _dict(panel.get("target"))
    reference_period_end = _text(_relative_method(panel).get("reference_period_end"))
    values: list[float] = []
    for row in target.get("annual_d3_d4_raw_observations") or []:
        if not isinstance(row, dict):
            return None
        fields = {**_dict(row.get("d3_raw_fields")), **_dict(row.get("d4_raw_fields"))}
        value = _stage_value_from_fields(fields, stage_id)
        if value is None:
            return None
        values.append(value)
    reference = _candidate_reference_contract(target, reference_period_end)
    revenue = _number(reference.get("reference_revenue"))
    baseline = _stage_value_from_fields(_dict(reference.get("fields")), stage_id)
    if len(values) < 5 or revenue is None or revenue <= 0 or baseline is None:
        return None
    center = float(median(values))
    raw_mad = float(median([abs(value - center) for value in values]))
    step = 1.4826 * raw_mad
    if step <= 0:
        return None
    peer_histories: list[dict[str, tuple[float, float]]] = []
    for peer in _candidate_panel(candidate).get("peers") or []:
        if not isinstance(peer, dict):
            return None
        history: dict[str, tuple[float, float]] = {}
        for row in peer.get("annual_d3_d4_raw_observations") or []:
            if not isinstance(row, dict):
                return None
            fields = {**_dict(row.get("d3_raw_fields")), **_dict(row.get("d4_raw_fields"))}
            value = _stage_value_from_fields(fields, stage_id)
            revenue_value = _number(_dict(fields.get("operating_revenue_rmb")).get("value"))
            period = _text(row.get("period_end"))
            if value is None or revenue_value is None or revenue_value <= 0 or not period:
                return None
            history[period] = (value, revenue_value)
        peer_histories.append(history)
    target_history: dict[str, tuple[float, float]] = {}
    for row in target.get("annual_d3_d4_raw_observations") or []:
        if not isinstance(row, dict):
            return None
        fields = {**_dict(row.get("d3_raw_fields")), **_dict(row.get("d4_raw_fields"))}
        value = _stage_value_from_fields(fields, stage_id)
        revenue_value = _number(_dict(fields.get("operating_revenue_rmb")).get("value"))
        period = _text(row.get("period_end"))
        if value is None or revenue_value is None or revenue_value <= 0 or not period:
            return None
        target_history[period] = (value, revenue_value)
    common_periods = set(target_history)
    for history in peer_histories:
        common_periods.intersection_update(history)
    if reference_period_end not in common_periods or len(common_periods) < 3:
        return None
    target_reference_margin = target_history[reference_period_end][0] / target_history[reference_period_end][1]
    peer_reference_margins = [
        history[reference_period_end][0] / history[reference_period_end][1]
        for history in peer_histories
    ]
    relative_preaction_deltas = []
    for period in sorted(common_periods):
        target_delta = target_history[period][0] / target_history[period][1] - target_reference_margin
        peer_deltas = [
            history[period][0] / history[period][1] - reference_margin
            for history, reference_margin in zip(peer_histories, peer_reference_margins)
        ]
        relative_preaction_deltas.append(target_delta - float(median(peer_deltas)))
    peer_delta_center = float(median(relative_preaction_deltas))
    peer_delta_mad = float(median([abs(value - peer_delta_center) for value in relative_preaction_deltas]))
    peer_noise_step = 1.4826 * peer_delta_mad
    target_ratio_step = step / revenue
    return {
        "baseline": baseline,
        "absolute_step": step,
        "reference_revenue": revenue,
        "target_ratio_step": target_ratio_step,
        "common_preaction_period_ends": sorted(common_periods),
        "relative_delta_median": peer_delta_center,
        "relative_delta_median_absolute_deviation": peer_delta_mad,
        "peer_preaction_relative_scaled_mad": peer_noise_step,
        "relative_ratio_step": max(target_ratio_step, peer_noise_step),
    }


def _contains_forbidden_outcome_derivation(value: Any, *, path: str = "outcome.peer_relative_measurement") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in _OUTCOME_CALLER_DERIVATION_KEYS:
                findings.append(child_path + ":caller_supplied_peer_verdict_or_score")
            findings.extend(_contains_forbidden_outcome_derivation(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_contains_forbidden_outcome_derivation(child, path=f"{path}[{index}]"))
    return findings


def _rule_by_stage(measurement_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for rule in measurement_contract.get("measurement_rules") or []:
        if not isinstance(rule, dict):
            continue
        clock = _text(rule.get("clock"))
        # Stage identity comes from the frozen prediction/registration.  D3
        # and D4 are unambiguous in the V4 peer contract because only D3 unit
        # economics and D4 cash may carry a peer test.
        if clock == "D3" and isinstance(rule.get("peer_relative_test"), dict):
            rules["D3_UNIT_ECONOMICS"] = rule
        elif clock == "D4" and isinstance(rule.get("peer_relative_test"), dict):
            rules["D4_WORKING_CAPITAL_AND_CASH"] = rule
    return rules


def _same_number(left: Any, right: Any) -> bool:
    left_number = _number(left)
    right_number = _number(right)
    return left_number is not None and right_number is not None and math.isclose(
        left_number, right_number, rel_tol=0.0, abs_tol=1e-9,
    )


def _exact_threshold(value: Any, *, operator: str, target: float, unit: str) -> bool:
    return isinstance(value, dict) and value.get("operator") == operator \
        and value.get("unit") == unit and _same_number(value.get("value"), target)


def _valid_relative_test(
    test: Any, *, formula_id: str, ratio_step: float,
) -> bool:
    test = _dict(test)
    return (
        test.get("method") == PEER_RELATIVE_METHOD
        and test.get("unit") == PEER_RELATIVE_UNIT
        and test.get("conjunction") == PEER_RELATIVE_CONJUNCTION
        and test.get("formula_id") == formula_id
        and _exact_threshold(
            test.get("primary_test"), operator="GREATER_THAN_OR_EQUAL",
            target=ratio_step, unit=PEER_RELATIVE_UNIT,
        )
        and _exact_threshold(
            test.get("rival_test"), operator="LESS_THAN_OR_EQUAL",
            target=-ratio_step, unit=PEER_RELATIVE_UNIT,
        )
    )


def _outcome_period_is_valid_for_action(
    period_end: Any, *, action_at: datetime | None,
) -> bool:
    """A result period cannot predate the selected operating action.

    Period ends are date-level accounting labels, while an implemented action
    may carry a precise instant.  The resulting economic ordering is therefore
    checked at the calendar-date level: an action and a period end on the same
    day are not silently treated as a backwards result period.
    """
    period = _date_or_time(period_end)
    return period is not None and action_at is not None and period.date() >= action_at.date()


def _validate_outcome_raw_field_contract(
    value: Any, *, issuer_id: str, perimeter_id: str, prefix: str,
) -> list[str]:
    field = _dict(value)
    findings: list[str] = []
    allowed_types = field.get("allowed_source_types")
    if not isinstance(allowed_types, list) or not allowed_types or not all(_text(item) for item in allowed_types):
        findings.append(prefix + ":allowed_source_types_invalid")
    if field.get("issuer_id") != issuer_id:
        findings.append(prefix + ":issuer_id_mismatch")
    if field.get("perimeter_id") != perimeter_id:
        findings.append(prefix + ":perimeter_id_mismatch")
    if not _text(field.get("field_ref")):
        findings.append(prefix + ":field_ref_missing")
    return findings


def _validate_member_outcome_contract(
    member: dict[str, Any], *, expected_period_end: str, d3_formula_id: str,
    d4_formula_id: str, prefix: str,
) -> list[str]:
    """Validate the frozen seventeen-field result-period input contract.

    Registration cannot know later values or source IDs, but it must freeze
    one common period and a complete target/peer field topology.  Settlement
    then binds actual source-bearing fields to this exact contract.
    """
    findings: list[str] = []
    outcome = _dict(member.get("outcome"))
    company_id = _text(member.get("company_id"))
    if outcome.get("period_end") != expected_period_end:
        findings.append(prefix + "_outcome_period_mismatch:" + company_id)
    if outcome.get("d3_formula_id") != d3_formula_id \
            or outcome.get("d4_formula_id") != d4_formula_id:
        findings.append(prefix + "_outcome_formula_identity_mismatch:" + company_id)
    fields = _dict(outcome.get("fields"))
    if set(fields) != set(ALL_RAW_FIELDS):
        findings.append(prefix + "_outcome_raw_field_set_invalid:" + company_id)
        return findings
    for field_name in ALL_RAW_FIELDS:
        findings.extend(_validate_outcome_raw_field_contract(
            fields.get(field_name), issuer_id=_text(member.get("issuer_id")),
            perimeter_id=_text(member.get("perimeter_id")),
            prefix=f"{prefix}_outcome_raw_field:{company_id}:{field_name}",
        ))
    return findings


def validate_peer_contract_binding(
    candidate: dict[str, Any], source_contract: dict[str, Any], measurement_contract: dict[str, Any],
) -> list[str]:
    """Bind the V4 frozen panel across candidate, acquisition and measurement.

    The return is a deterministic list rather than an exception so both
    registration and outcome validation can make the exact same decision.
    Legacy packets intentionally have no V4 panel and return an empty list.
    """
    if not isinstance(candidate, dict):
        return ["peer_binding.candidate_not_object"]
    if not _is_v4(candidate):
        return []
    findings: list[str] = []
    panel = _candidate_panel(candidate)
    panel_id = _text(panel.get("panel_contract_id"))
    order = _candidate_order(candidate)
    candidate_method = _method_identity(panel)
    if not panel_id:
        findings.append("peer_binding.candidate_panel_contract_id_missing")
    if len(order) < 4 or len(order) > 8 or not all(order) or len(set(order)) != len(order):
        findings.append("peer_binding.candidate_frozen_order_invalid")
    elif order[0] != _text(candidate.get("company_id")):
        findings.append("peer_binding.candidate_target_must_be_first_frozen_member")
    if candidate_method != (
        PEER_RELATIVE_METHOD, candidate_method[1], PEER_RELATIVE_UNIT, PEER_RELATIVE_CONJUNCTION,
    ) or not candidate_method[1]:
        findings.append("peer_binding.candidate_relative_method_invalid")

    expected_members = _expected_member_identities(candidate)
    if list(expected_members) != order:
        findings.append("peer_binding.candidate_member_identity_does_not_match_frozen_order")
    d3_formula_id, d4_formula_id = _candidate_formula_ids(candidate)
    if not d3_formula_id or not d4_formula_id:
        findings.append("peer_binding.candidate_formula_identity_missing")

    source_bundle = _dict(_dict(source_contract).get("peer_relative_acquisition"))
    measurement_bundle = _dict(_dict(measurement_contract).get("peer_relative_measurement"))
    source_outcome_period = _text(source_bundle.get("outcome_period_end"))
    measurement_outcome_period = _text(measurement_bundle.get("outcome_period_end"))
    action_at = _candidate_action_at(candidate)
    if not source_outcome_period or _date_or_time(source_outcome_period) is None:
        findings.append("peer_binding.source_contract_outcome_period_missing_or_invalid")
    elif not _outcome_period_is_valid_for_action(source_outcome_period, action_at=action_at):
        findings.append("peer_binding.source_contract_outcome_period_before_action")
    if not measurement_outcome_period or _date_or_time(measurement_outcome_period) is None:
        findings.append("peer_binding.measurement_contract_outcome_period_missing_or_invalid")
    elif not _outcome_period_is_valid_for_action(measurement_outcome_period, action_at=action_at):
        findings.append("peer_binding.measurement_contract_outcome_period_before_action")
    if source_outcome_period and measurement_outcome_period \
            and source_outcome_period != measurement_outcome_period:
        findings.append("peer_binding.source_measurement_outcome_period_mismatch")
    source_members = _member_by_company(source_bundle)

    for artifact_name, artifact, bundle_key in (
        ("source_contract", source_contract, "peer_relative_acquisition"),
        ("measurement_contract", measurement_contract, "peer_relative_measurement"),
    ):
        if not isinstance(artifact, dict):
            findings.append(f"peer_binding.{artifact_name}_not_object")
            continue
        bundle = artifact.get(bundle_key)
        if not isinstance(bundle, dict):
            findings.append(f"peer_binding.{artifact_name}_{bundle_key}_missing")
            continue
        if bundle.get("panel_contract_id") != panel_id:
            findings.append(f"peer_binding.{artifact_name}_panel_contract_id_mismatch")
        if _member_order(bundle) != order:
            findings.append(f"peer_binding.{artifact_name}_frozen_order_mismatch")
        if _method_identity(bundle) != candidate_method:
            findings.append(f"peer_binding.{artifact_name}_relative_method_mismatch")
        members = _member_by_company(bundle)
        if [_text(row.get("company_id")) for row in _member_rows(bundle)] != order:
            findings.append(f"peer_binding.{artifact_name}_member_order_mismatch")
        if set(members) != set(order):
            findings.append(f"peer_binding.{artifact_name}_member_set_mismatch")
            continue
        expected_outcome_period = (
            source_outcome_period if artifact_name == "source_contract" else measurement_outcome_period
        )
        for company_id in order:
            candidate_member = expected_members.get(company_id, {})
            artifact_member = members[company_id]
            for field in (
                "company_id", "issuer_id", "control_group_id", "responsibility_unit_id",
            ):
                if artifact_member.get(field) != candidate_member.get(field):
                    findings.append(f"peer_binding.{artifact_name}_member_identity_mismatch:{company_id}")
                    break
            candidate_boundary = _dict(candidate_member.get("boundary"))
            expected_perimeter = _text(candidate_boundary.get("perimeter_id"))
            if artifact_member.get("perimeter_id") != expected_perimeter:
                findings.append(f"peer_binding.{artifact_name}_member_perimeter_mismatch:{company_id}")
            if artifact_member.get("control_group_evidence") != candidate_member.get("control_group_evidence"):
                findings.append(f"peer_binding.{artifact_name}_control_group_evidence_mismatch:{company_id}")
            history = candidate_member.get("annual_d3_d4_raw_observations")
            if artifact_member.get("pre_action_history") != history:
                findings.append(f"peer_binding.{artifact_name}_pre_action_history_mismatch:{company_id}")
            if expected_outcome_period:
                findings.extend(_validate_member_outcome_contract(
                    artifact_member, expected_period_end=expected_outcome_period,
                    d3_formula_id=d3_formula_id, d4_formula_id=d4_formula_id,
                    prefix=f"peer_binding.{artifact_name}",
                ))
            if artifact_name == "measurement_contract":
                source_member = source_members.get(company_id)
                if source_member is None:
                    findings.append(
                        "peer_binding.source_contract_outcome_member_missing:" + company_id
                    )
                elif artifact_member.get("outcome") != source_member.get("outcome"):
                    findings.append(
                        "peer_binding.source_measurement_outcome_contract_mismatch:" + company_id
                    )
            expected_reference = _candidate_reference_contract(
                candidate_member, candidate_method[1],
            )
            reference = _dict(artifact_member.get("reference"))
            for field in ("period_end", "d3_formula_id", "d4_formula_id", "reference_revenue"):
                if reference.get(field) != expected_reference.get(field):
                    findings.append(f"peer_binding.{artifact_name}_reference_identity_mismatch:{company_id}")
                    break
            if artifact_name == "source_contract":
                if reference.get("fields") != expected_reference.get("fields"):
                    findings.append(f"peer_binding.source_contract_reference_fields_mismatch:{company_id}")
                outcome_formula = _dict(artifact_member.get("outcome"))
                if outcome_formula.get("d3_formula_id") != d3_formula_id \
                        or outcome_formula.get("d4_formula_id") != d4_formula_id:
                    findings.append(f"peer_binding.source_contract_outcome_formula_mismatch:{company_id}")

    if isinstance(measurement_contract, dict):
        rules = _rule_by_stage(measurement_contract)
        if set(rules) != PEER_REQUIRED_STAGE_IDS:
            findings.append("peer_binding.measurement_contract_d3_d4_peer_rules_required")
        for stage_id in PEER_REQUIRED_STAGE_IDS:
            rule = rules.get(stage_id, {})
            anchor = _dict(_dict(candidate.get("cash_transmission_observability")).get("materiality_anchors")).get(stage_id)
            thresholds = _candidate_stage_thresholds(candidate, stage_id)
            formula_id = d3_formula_id if stage_id == "D3_UNIT_ECONOMICS" else d4_formula_id
            if not isinstance(anchor, dict) or thresholds is None:
                findings.append(f"peer_binding.candidate_stage_anchor_invalid:{stage_id}")
                continue
            relative_anchor = _dict(anchor.get("relative_peer_threshold"))
            if (
                relative_anchor.get("formula") != PEER_RELATIVE_STEP_FORMULA
                or relative_anchor.get("common_preaction_period_ends") != thresholds["common_preaction_period_ends"]
                or not _same_number(relative_anchor.get("target_absolute_ratio_step"), thresholds["target_ratio_step"])
                or not _same_number(
                    relative_anchor.get("relative_delta_median"), thresholds["relative_delta_median"],
                )
                or not _same_number(
                    relative_anchor.get("relative_delta_median_absolute_deviation"),
                    thresholds["relative_delta_median_absolute_deviation"],
                )
                or not _same_number(
                    relative_anchor.get("peer_preaction_relative_scaled_mad"),
                    thresholds["peer_preaction_relative_scaled_mad"],
                )
                or not _same_number(relative_anchor.get("relative_ratio_step"), thresholds["relative_ratio_step"])
            ):
                findings.append(f"peer_binding.candidate_relative_noise_threshold_invalid:{stage_id}")
            if rule.get("formula_id") != formula_id \
                    or not _exact_threshold(
                        rule.get("primary_test"), operator="GREATER_THAN_OR_EQUAL",
                        target=thresholds["baseline"] + thresholds["absolute_step"], unit="RMB",
                    ) \
                    or not _exact_threshold(
                        rule.get("rival_test"), operator="LESS_THAN_OR_EQUAL",
                        target=thresholds["baseline"] - thresholds["absolute_step"], unit="RMB",
                    ):
                findings.append(f"peer_binding.measurement_contract_absolute_rule_not_candidate_anchor:{stage_id}")
            if not _valid_relative_test(
                rule.get("peer_relative_test"), formula_id=formula_id,
                ratio_step=thresholds["relative_ratio_step"],
            ):
                findings.append(f"peer_binding.measurement_contract_peer_relative_test_invalid:{stage_id}")
    return findings


def _field_identity(
    field: Any, *, expected: dict[str, Any], period_end: str, prefix: str,
    candidate_cutoff: datetime | None, require_post_cutoff_publication: bool,
) -> tuple[float | None, str | None, list[str]]:
    """Validate one source-backed raw field against its frozen source row."""
    findings: list[str] = []
    field = _dict(field)
    value = _number(field.get("value"))
    if value is None:
        findings.append(prefix + ":value_invalid")
    if field.get("unit") != "RMB":
        findings.append(prefix + ":unit_must_be_rmb")
    if not _text(field.get("source_id")):
        findings.append(prefix + ":source_id_missing")
    allowed_types = expected.get("allowed_source_types")
    if isinstance(allowed_types, list):
        if field.get("source_type") not in set(allowed_types):
            findings.append(prefix + ":source_type_not_frozen")
    elif field.get("source_type") != expected.get("source_type"):
        findings.append(prefix + ":source_type_not_frozen")
    for field_name in ("issuer_id", "perimeter_id", "field_ref", "source_id", "published_at"):
        if expected.get(field_name) not in (None, "") and field.get(field_name) != expected.get(field_name):
            findings.append(prefix + ":" + field_name + "_mismatch")
    if expected.get("value") is not None and not _same_number(field.get("value"), expected.get("value")):
        findings.append(prefix + ":value_mismatch")
    if field.get("period_end") != period_end:
        findings.append(prefix + ":period_end_mismatch")
    if require_post_cutoff_publication:
        published_at = _date_or_time(field.get("published_at"))
        if published_at is None:
            findings.append(prefix + ":published_at_invalid")
        elif candidate_cutoff is None or published_at <= candidate_cutoff:
            findings.append(prefix + ":published_at_not_strictly_after_candidate_cutoff")
    return value, _text(field.get("source_id")) or None, findings


def _raw_snapshot(
    value: Any, *, expected_member: dict[str, Any], period_end: str, prefix: str,
    candidate_cutoff: datetime | None, require_post_cutoff_publication: bool,
) -> tuple[dict[str, float], dict[str, str], list[str]]:
    raw = _dict(value)
    fields: dict[str, float] = {}
    source_ids: dict[str, str] = {}
    findings: list[str] = []
    expected_fields = _dict(expected_member.get("fields"))
    if raw.get("d3_formula_id") != expected_member.get("d3_formula_id") \
            or raw.get("d4_formula_id") != expected_member.get("d4_formula_id"):
        findings.append(prefix + ":formula_identity_mismatch")
    raw_fields = _dict(raw.get("fields"))
    if set(raw_fields) != set(ALL_RAW_FIELDS):
        findings.append(prefix + ":raw_field_set_invalid")
    if set(expected_fields) != set(ALL_RAW_FIELDS):
        findings.append(prefix + ":frozen_field_set_invalid")
    for name in ALL_RAW_FIELDS:
        field_value, source_id, field_findings = _field_identity(
            raw_fields.get(name), expected=_dict(expected_fields.get(name)), period_end=period_end,
            prefix=f"{prefix}.{name}", candidate_cutoff=candidate_cutoff,
            require_post_cutoff_publication=require_post_cutoff_publication,
        )
        findings.extend(field_findings)
        if field_value is not None:
            fields[name] = field_value
        if source_id:
            source_ids[name] = source_id
    return fields, source_ids, findings


def _scalars_and_margins(fields: dict[str, float]) -> tuple[dict[str, float] | None, list[str]]:
    if set(fields) != set(ALL_RAW_FIELDS):
        return None, ["raw_fields_incomplete"]
    revenue = fields["operating_revenue_rmb"]
    if revenue == 0:
        return None, ["operating_revenue_zero_margin_undefined"]
    d3 = (
        revenue
        - fields["operating_cost_rmb"]
        - fields["taxes_and_surcharges_rmb"]
        - fields["selling_expense_rmb"]
        - fields["administrative_expense_rmb"]
    )
    opening_wc = (
        fields["opening_accounts_receivable_rmb"]
        + fields["opening_prepayments_rmb"]
        + fields["opening_inventory_rmb"]
        - fields["opening_accounts_payable_rmb"]
        - fields["opening_customer_advances_rmb"]
    )
    ending_wc = (
        fields["ending_accounts_receivable_rmb"]
        + fields["ending_prepayments_rmb"]
        + fields["ending_inventory_rmb"]
        - fields["ending_accounts_payable_rmb"]
        - fields["ending_customer_advances_rmb"]
    )
    owner_cash = (
        fields["operating_cash_flow_rmb"]
        - fields["cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb"]
        - max(opening_wc - ending_wc, 0.0)
    )
    return {
        "D3_UNIT_ECONOMICS": d3,
        "D4_WORKING_CAPITAL_AND_CASH": owner_cash,
        "D3_margin": d3 / revenue,
        "D4_margin": owner_cash / revenue,
    }, []


def _outcome_peer_bundle(outcome: dict[str, Any]) -> dict[str, Any]:
    return _dict(outcome.get("peer_relative_measurement"))


def derive_peer_relative_observations(
    outcome: dict[str, Any], *, candidate: dict[str, Any], source_contract: dict[str, Any],
    measurement_contract: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Recompute V4 D3/D4 peer observations from raw source-backed fields.

    Returned observations are keyed by selection stage and include absolute
    target scalar, margin deltas and peer median.  Nothing caller-supplied is
    used as a verdict or score.
    """
    if not _is_v4(candidate):
        return {}, []
    findings = validate_peer_contract_binding(candidate, source_contract, measurement_contract)
    if not isinstance(outcome, dict):
        return {}, findings + ["peer_outcome.outcome_not_object"]
    bundle = _outcome_peer_bundle(outcome)
    findings.extend(_contains_forbidden_outcome_derivation(bundle))
    panel_id = _text(_candidate_panel(candidate).get("panel_contract_id"))
    order = _candidate_order(candidate)
    method = _method_identity(_candidate_panel(candidate))
    if bundle.get("panel_contract_id") != panel_id:
        findings.append("peer_outcome.panel_contract_id_mismatch")
    if _member_order(bundle) != order:
        findings.append("peer_outcome.frozen_order_mismatch")
    if _method_identity(bundle) != method:
        findings.append("peer_outcome.relative_method_mismatch")

    source_bundle = _dict(source_contract.get("peer_relative_acquisition"))
    expected_members = _member_by_company(source_bundle)
    frozen_outcome_period = _text(source_bundle.get("outcome_period_end"))
    supplied_outcome_period = _text(bundle.get("outcome_period_end"))
    action_at = _candidate_action_at(candidate)
    if not supplied_outcome_period or _date_or_time(supplied_outcome_period) is None:
        findings.append("peer_outcome.outcome_period_missing_or_invalid")
    else:
        if supplied_outcome_period != frozen_outcome_period:
            findings.append("peer_outcome.outcome_period_does_not_match_frozen_contract")
        if not _outcome_period_is_valid_for_action(supplied_outcome_period, action_at=action_at):
            findings.append("peer_outcome.outcome_period_before_action")
    rows = _member_by_company(bundle)
    actual_member_row_order = [_text(row.get("company_id")) for row in _member_rows(bundle)]
    if actual_member_row_order != order:
        findings.append("peer_outcome.member_order_mismatch")
    if set(rows) != set(order):
        findings.append("peer_outcome.member_set_mismatch")
        return {}, findings
    if len(_member_rows(bundle)) != len(order):
        findings.append("peer_outcome.member_rows_duplicate_or_invalid")
        return {}, findings

    member_values: dict[str, dict[str, dict[str, float]]] = {}
    member_sources: dict[str, dict[str, dict[str, str]]] = {}
    candidate_cutoff = _date_or_time(candidate.get("cutoff_at"))
    for company_id in order:
        row = rows.get(company_id, {})
        expected = expected_members.get(company_id, {})
        if not expected:
            findings.append("peer_outcome.member_not_in_frozen_acquisition:" + company_id)
            continue
        for field in (
            "company_id", "issuer_id", "control_group_id", "responsibility_unit_id", "perimeter_id",
        ):
            if row.get(field) != expected.get(field):
                findings.append(f"peer_outcome.member_{field}_mismatch:{company_id}")
        if row.get("control_group_evidence") != expected.get("control_group_evidence"):
            findings.append(f"peer_outcome.member_control_group_evidence_mismatch:{company_id}")
        snapshots: dict[str, dict[str, float]] = {}
        sources: dict[str, dict[str, str]] = {}
        for snapshot in ("reference", "outcome"):
            expected_snapshot = _dict(expected.get(snapshot))
            period_end = _text(expected_snapshot.get("period_end"))
            raw_fields, source_ids, raw_findings = _raw_snapshot(
                row.get(snapshot + "_raw"), expected_member=expected_snapshot,
                period_end=period_end, prefix=f"peer_outcome.members[{company_id}].{snapshot}",
                candidate_cutoff=candidate_cutoff,
                require_post_cutoff_publication=snapshot == "outcome",
            )
            findings.extend(raw_findings)
            result, math_findings = _scalars_and_margins(raw_fields)
            if math_findings:
                findings.extend(
                    f"peer_outcome.members[{company_id}].{snapshot}:{finding}"
                    for finding in math_findings
                )
            elif result is not None:
                snapshots[snapshot] = result
                sources[snapshot] = source_ids
        if set(snapshots) == {"reference", "outcome"}:
            member_values[company_id] = snapshots
            member_sources[company_id] = sources

    if set(member_values) != set(order):
        return {}, findings
    target_id = order[0]
    derived: dict[str, dict[str, Any]] = {}
    for stage_id, margin_key in (
        ("D3_UNIT_ECONOMICS", "D3_margin"),
        ("D4_WORKING_CAPITAL_AND_CASH", "D4_margin"),
    ):
        target = member_values[target_id]
        target_delta = target["outcome"][margin_key] - target["reference"][margin_key]
        peer_deltas = [
            member_values[company_id]["outcome"][margin_key]
            - member_values[company_id]["reference"][margin_key]
            for company_id in order[1:]
        ]
        peer_median = float(median(peer_deltas))
        source_fields = D3_FIELDS if stage_id == "D3_UNIT_ECONOMICS" else D4_FIELDS
        derived[stage_id] = {
            "target_scalar": target["outcome"][stage_id],
            "target_margin_reference": target["reference"][margin_key],
            "target_margin_outcome": target["outcome"][margin_key],
            "target_delta": target_delta,
            "peer_deltas": peer_deltas,
            "median_peer_delta": peer_median,
            "relative_delta_vs_peer_median": target_delta - peer_median,
            "target_source_ids": sorted({
                member_sources[target_id]["outcome"][field_name]
                for field_name in source_fields
                if field_name in member_sources[target_id]["outcome"]
            }),
        }
    return derived, findings


def validate_peer_relative_outcome(
    outcome: dict[str, Any], *, candidate: dict[str, Any], source_contract: dict[str, Any],
    measurement_contract: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Validate and return recomputed V4 observations for the feedback layer."""
    derived, findings = derive_peer_relative_observations(
        outcome, candidate=candidate, source_contract=source_contract,
        measurement_contract=measurement_contract,
    )
    if not _is_v4(candidate):
        return derived, findings
    claims = {
        _text(item.get("stage_id")): item
        for item in outcome.get("claims") or [] if isinstance(item, dict)
    }
    for stage_id, observation in derived.items():
        claim = claims.get(stage_id)
        if not isinstance(claim, dict):
            findings.append("peer_outcome.target_claim_missing:" + stage_id)
            continue
        if claim.get("status") != "OBSERVED":
            # The peer panel may still be fully acquired while the target
            # scalar is unusable under its stricter absolute measurement
            # contract.  Preserve that UNKNOWN/MISMATCH at the card layer;
            # it must resolve to NOT_DIAGNOSTIC rather than become a fake
            # panel-validation failure or a directional verdict.
            continue
        observed = _number(claim.get("observed_value"))
        if observed is None or not math.isclose(
            observed, observation["target_scalar"], rel_tol=0.0, abs_tol=1e-6,
        ):
            findings.append("peer_outcome.target_scalar_mismatch:" + stage_id)
        if claim.get("observed_unit") != "RMB":
            findings.append("peer_outcome.target_scalar_unit_mismatch:" + stage_id)
        claim_sources = claim.get("source_ids")
        if not isinstance(claim_sources, list) or set(claim_sources) != set(observation["target_source_ids"]):
            findings.append("peer_outcome.target_source_ids_mismatch:" + stage_id)
    return derived, findings


def peer_relative_card_observation(
    rule: dict[str, Any], *, derived: dict[str, Any], evaluate_rule: Any,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Score the recomputed relative delta only through frozen peer tests.

    ``evaluate_rule`` is injected from ``judgment_selection_feedback`` to
    preserve its exact comparison semantics without introducing a second rule
    engine.
    """
    test = _dict(rule.get("peer_relative_test"))
    primary = evaluate_rule(
        test.get("primary_test"), value=derived["relative_delta_vs_peer_median"], unit=PEER_RELATIVE_UNIT,
    )
    rival = evaluate_rule(
        test.get("rival_test"), value=derived["relative_delta_vs_peer_median"], unit=PEER_RELATIVE_UNIT,
    )
    if primary.get("status") == "MET" and rival.get("status") != "MET":
        verdict = "A_ONLY"
    elif rival.get("status") == "MET" and primary.get("status") != "MET":
        verdict = "B_ONLY"
    elif primary.get("status") == "NO_FROZEN_RULE" or rival.get("status") == "NO_FROZEN_RULE":
        verdict = "NOT_DIAGNOSTIC"
    else:
        verdict = "MIXED"
    return primary, rival, verdict


def conjunct_absolute_and_peer_verdict(absolute: str, peer_relative: str) -> str:
    """Require agreement; a missing path cannot be converted into a winner."""
    if absolute == "NOT_DIAGNOSTIC" or peer_relative == "NOT_DIAGNOSTIC":
        return "NOT_DIAGNOSTIC"
    if absolute == peer_relative and absolute in {"A_ONLY", "B_ONLY"}:
        return absolute
    return "MIXED"
