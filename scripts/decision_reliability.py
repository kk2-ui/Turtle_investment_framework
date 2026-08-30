#!/usr/bin/env python3
"""Non-compensating decision-reliability gate for valuation reports.

This gate closes the gap between a structurally valid valuation ledger and a
decision-reliable one.  It checks the five failure families repeatedly found
by independent Phase-08 reviews: cash accessibility, parameter calibration,
model comparability, calculation integrity, and joint-stress/action coherence.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POLICY_VERSION = "decision-reliability-policy.v1"
VALIDATION_VERSION = "decision-reliability-validation.v1"
ACCESS_STATES = {"VERIFIED_ACCESSIBLE", "CONDITIONAL", "RESTRICTED", "RELATED_PARTY", "UNVERIFIED"}
DISTRIBUTABILITY_STATES = {"VERIFIED", "CONDITIONAL", "NOT_VERIFIED"}
CALIBRATION_METHODS = {"empirical", "historical_base_rate", "conservative_bound", "working_assumption"}
ALLOWED_MODEL_USES = {
    "corroboration", "cross_check_only", "distribution_floor", "upper_bound",
    "stress", "diagnostic",
}
ACTIONS = {"buy", "hold", "avoid"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _same(left: Any, right: Any, *, tolerance: float = 1e-3) -> bool:
    lval, rval = _num(left), _num(right)
    return lval is not None and rval is not None and math.isclose(
        lval, rval, rel_tol=tolerance, abs_tol=tolerance
    )


def initialize_decision_reliability_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool = True
) -> dict[str, Any]:
    payload = {
        "schema_version": POLICY_VERSION,
        "run_id": str(run_id),
        "enforced": bool(enforced),
        "created_at": _now(),
    }
    path = Path(output_dir) / "decision_reliability_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _cash_question_selected(output: Path, valuation: dict[str, Any]) -> bool:
    plan = _load(output / "decisive_question_plan.json")
    if any(
        isinstance(row, dict) and row.get("topic_family") == "cash_value_realization"
        for row in plan.get("selected_questions") or []
    ):
        return True
    return any(
        isinstance(model, dict)
        and (
            model.get("model_type") == "RETURN_DECOMPOSITION"
            or "retained_value_realization" in _mapping(model.get("assumptions"))
        )
        for model in valuation.get("models") or []
    )


def _verified_source_ids(output: Path) -> set[str]:
    """Return auditable evidence identities, never free-form source labels."""
    result: set[str] = set()
    for filename, collection, identity in (
        ("fact_observations.json", "observations", "observation_id"),
        ("calculation_observations.json", "calculations", "calculation_id"),
    ):
        for row in _load(output / filename).get(collection) or []:
            if (
                isinstance(row, dict)
                and str(row.get("status") or "").upper() == "VERIFIED"
                and row.get(identity)
            ):
                result.add(str(row[identity]))
    for claim in _load(output / "claim_evidence.json").get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for fact in claim.get("raw_facts") or []:
            if isinstance(fact, dict) and fact.get("evidence_id"):
                result.add(str(fact["evidence_id"]))
    return result


def _verified_fact_names(output: Path) -> dict[str, str]:
    """Map verified observation identities to their normalized fact names."""
    return {
        str(row.get("observation_id")): str(row.get("fact_name") or "").lower()
        for row in _load(output / "fact_observations.json").get("observations") or []
        if isinstance(row, dict)
        and str(row.get("status") or "").upper() == "VERIFIED"
        and row.get("observation_id")
    }


def _check_source_ids(
    value: Any, *, prefix: str, verified_ids: set[str],
    invalid: list[str], incomplete: list[str],
) -> None:
    if not isinstance(value, list) or not value:
        incomplete.append(prefix + ":source_ids_missing")
        return
    unknown = [str(item) for item in value if str(item) not in verified_ids]
    if unknown:
        invalid.append(prefix + ":source_ids_unverified:" + "|".join(unknown))


def _validate_cash_bridge(
    valuation: dict[str, Any], *, required: bool,
    verified_ids: set[str], verified_fact_names: dict[str, str],
    invalid: list[str], incomplete: list[str], warnings: list[str],
) -> None:
    canonical = _mapping(
        _mapping(_mapping(valuation.get("value_bridge_models")).get("result")).get(
            "cash_accessibility"
        )
    )
    if canonical:
        fact_ids = canonical.get("input_fact_ids") or []
        unknown = [str(item) for item in fact_ids if str(item) not in verified_ids]
        if unknown:
            invalid.append(
                "cash_accessibility_model:source_ids_unverified:" + "|".join(unknown)
            )
        future = _mapping(canonical.get("future_retained_cash_realization"))
        adopted_rate = _num(future.get("adopted_realization_rate"))
        for model in valuation.get("models") or []:
            if not isinstance(model, dict) or model.get("status", "active") != "active":
                continue
            assumptions = _mapping(model.get("assumptions"))
            if (
                model.get("model_type") != "RETURN_DECOMPOSITION"
                and "retained_value_realization" not in assumptions
            ):
                continue
            submitted = _num(assumptions.get("retained_value_realization"))
            if submitted is None:
                incomplete.append(
                    f"cash_accessibility_model:{model.get('model_id')}:retained_value_realization_missing"
                )
            elif adopted_rate is None or not _same(submitted, adopted_rate):
                invalid.append(
                    f"cash_accessibility_model:{model.get('model_id')}:retained_value_realization_mismatch"
                )
        if _num(
            _mapping(canonical.get("existing_excess_cash_realization")).get(
                "adopted_value"
            )
        ) == 0:
            warnings.append(
                "cash_accessibility_model:no_existing_cash_admitted_to_primary_value"
            )
        return
    bridge = valuation.get("cash_access_bridge")
    if not isinstance(bridge, dict):
        if required:
            incomplete.append("cash_access_bridge_missing")
        return
    gross = _num(bridge.get("gross_cash_amount"))
    if gross is None or gross < 0:
        invalid.append("cash_access_bridge:gross_cash_invalid")
    if not str(bridge.get("as_of") or ""):
        incomplete.append("cash_access_bridge:as_of_missing")
    if not str(bridge.get("unit") or ""):
        incomplete.append("cash_access_bridge:unit_missing")
    components = bridge.get("components")
    if not isinstance(components, list) or not components:
        incomplete.append("cash_access_bridge:components_missing")
        components = []
    seen: set[str] = set()
    component_sum = 0.0
    accessible_sum = 0.0
    unresolved_access = False
    for index, row in enumerate(components):
        prefix = f"cash_access_bridge:components[{index}]"
        if not isinstance(row, dict):
            invalid.append(prefix + ":not_object")
            continue
        identity = str(row.get("component_id") or "")
        if not identity:
            invalid.append(prefix + ":component_id_missing")
        elif identity in seen:
            invalid.append("cash_access_bridge:duplicate_component:" + identity)
        seen.add(identity)
        amount = _num(row.get("amount"))
        haircut = _num(row.get("haircut_pct"))
        if amount is None or amount < 0:
            invalid.append(prefix + ":amount_invalid")
            continue
        component_sum += amount
        if haircut is None or not 0 <= haircut <= 100:
            invalid.append(prefix + ":haircut_invalid")
            haircut = 100.0
        access = str(row.get("access_status") or "")
        distribution = str(row.get("legal_distributability") or "")
        if access not in ACCESS_STATES:
            invalid.append(prefix + ":access_status_invalid")
        if distribution not in DISTRIBUTABILITY_STATES:
            invalid.append(prefix + ":legal_distributability_invalid")
        if not str(row.get("legal_owner_scope") or ""):
            incomplete.append(prefix + ":legal_owner_scope_missing")
        _check_source_ids(
            row.get("source_ids"), prefix=prefix, verified_ids=verified_ids,
            invalid=invalid, incomplete=incomplete,
        )
        notes = str(row.get("notes") or "")
        states_interest_rate = bool(re.search(
            r"(?:利率|收益率|interest\s+rate|yield)[^。；;\n]{0,24}\d+(?:\.\d+)?%"
            r"|\d+(?:\.\d+)?%[^。；;\n]{0,24}(?:利率|收益率|interest\s+rate|yield)",
            notes, re.I,
        ))
        rate_directly_supported = any(
            re.search(r"interest_rate|deposit_rate|yield", verified_fact_names.get(str(source_id), ""))
            for source_id in row.get("source_ids") or []
        ) or any(str(source_id).startswith("CALC:") for source_id in row.get("source_ids") or [])
        if states_interest_rate and not rate_directly_supported:
            invalid.append(prefix + ":unverified_interest_rate_derivation")
        if access != "VERIFIED_ACCESSIBLE" or distribution != "VERIFIED":
            unresolved_access = True
            if haircut < 100:
                invalid.append(prefix + ":unverified_cash_requires_full_primary_haircut")
        elif haircut < 100 and not any(
            re.search(r"(?:parent|holding_company|company_only).*(?:cash|bank)", verified_fact_names.get(str(source_id), ""))
            for source_id in row.get("source_ids") or []
        ):
            # A distributable-reserve observation proves a legal ceiling, not
            # the location of cash at the parent entity.  The two identities
            # must never be collapsed merely because their amounts match.
            invalid.append(prefix + ":parent_cash_location_not_verified")
        accessible_sum += amount * (1 - haircut / 100)
    if gross is not None and components and not _same(component_sum, gross, tolerance=0.01):
        invalid.append(
            f"cash_access_bridge:component_sum_mismatch:{component_sum:.4f}!={gross:.4f}"
        )
    # A company-only balance-sheet cash observation proves a legal-entity
    # location that is more specific than a consolidated cash total.  It does
    # not prove immediate distributability, but omitting it from the bridge
    # would wrongly turn a known location into "no parent cash observed".
    company_cash_ids = {
        source_id for source_id, fact_name in verified_fact_names.items()
        if fact_name == "company_only_cash_and_cash_equivalents_rmb_m"
    }
    bridged_source_ids = {
        str(source_id)
        for row in components if isinstance(row, dict)
        for source_id in row.get("source_ids") or []
    }
    if company_cash_ids and not company_cash_ids.intersection(bridged_source_ids):
        invalid.append("cash_access_bridge:company_only_cash_location_omitted")
    conservative = _num(bridge.get("conservative_accessible_cash_amount"))
    if conservative is None or conservative < 0:
        invalid.append("cash_access_bridge:conservative_accessible_cash_invalid")
    elif not _same(conservative, accessible_sum, tolerance=0.01):
        invalid.append(
            f"cash_access_bridge:accessible_cash_reconciliation_mismatch:{conservative:.4f}!={accessible_sum:.4f}"
        )
    capacity = bridge.get("ordinary_distribution_capacity")
    capacity_kind = str((capacity or {}).get("basis_kind") or "")
    capacity_sources = (capacity or {}).get("source_ids") or []
    verified_distribution_flow = (
        capacity_kind == "actual_distribution_flow"
        and any(
            verified_fact_names.get(str(source_id), "")
            in {"dividends_total", "dividend_payout_ratio_pct", "dividend_per_share"}
            for source_id in capacity_sources
        )
    )
    if conservative == 0 and not verified_distribution_flow:
        for model in valuation.get("models") or []:
            if not isinstance(model, dict) or model.get("status", "active") != "active":
                continue
            realization = _num(
                (model.get("assumptions") or {}).get("retained_value_realization")
            )
            if realization is not None and realization > 0:
                invalid.append(
                    f"cash_access_bridge:{model.get('model_id')}:positive_retained_value_with_zero_verified_access"
                )
    reserves = bridge.get("parent_distributable_reserves")
    if not isinstance(reserves, dict):
        incomplete.append("cash_access_bridge:parent_distributable_reserves_missing")
    else:
        reserve_status = str(reserves.get("status") or "")
        if reserve_status not in {"VERIFIED", "NOT_DISCLOSED", "NOT_APPLICABLE"}:
            invalid.append("cash_access_bridge:parent_reserve_status_invalid")
        if reserve_status != "VERIFIED" and conservative and conservative > 0:
            invalid.append("cash_access_bridge:positive_cash_value_without_parent_reserve_test")
        _check_source_ids(
            reserves.get("source_ids"), prefix="cash_access_bridge:parent_reserve",
            verified_ids=verified_ids, invalid=invalid, incomplete=incomplete,
        )
    if not isinstance(capacity, dict) or _num(capacity.get("amount")) is None:
        incomplete.append("cash_access_bridge:ordinary_distribution_capacity_missing")
    else:
        if capacity_kind not in {"actual_distribution_flow", "legal_reserve_ceiling", "not_verified"}:
            incomplete.append("cash_access_bridge:ordinary_distribution_capacity_basis_kind_missing")
        if capacity_kind == "actual_distribution_flow" and not verified_distribution_flow:
            invalid.append("cash_access_bridge:ordinary_distribution_flow_not_verified")
        _check_source_ids(
            capacity.get("source_ids"), prefix="cash_access_bridge:ordinary_distribution",
            verified_ids=verified_ids, invalid=invalid, incomplete=incomplete,
        )
    unresolved = bridge.get("unresolved")
    if unresolved_access and (not isinstance(unresolved, list) or not unresolved):
        incomplete.append("cash_access_bridge:unresolved_access_not_disclosed")
    if not str(bridge.get("conclusion") or "").strip():
        incomplete.append("cash_access_bridge:conclusion_missing")
    if conservative == 0:
        warnings.append("cash_access_bridge:no_existing_cash_admitted_to_primary_value")


def _validate_calibrations(
    valuation: dict[str, Any], verified_ids: set[str],
    invalid: list[str], incomplete: list[str]
) -> None:
    required: dict[tuple[str, str], tuple[float, str]] = {}
    for model in valuation.get("models") or []:
        if not isinstance(model, dict) or model.get("status", "active") != "active":
            continue
        mid = str(model.get("model_id") or "")
        assumptions = model.get("assumptions") or {}
        for key, direction in (
            ("retained_value_realization", "benefit"),
            ("moat_decay_pct", "penalty"),
        ):
            value = _num(assumptions.get(key))
            if value is not None:
                required[(mid, key)] = (value, direction)
    rows = valuation.get("parameter_calibrations")
    if required and (not isinstance(rows, list) or not rows):
        incomplete.append("parameter_calibrations_missing")
        return
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            invalid.append(f"parameter_calibrations[{index}]:not_object")
            continue
        key = (str(row.get("model_id") or ""), str(row.get("parameter") or ""))
        if key in by_key:
            invalid.append(f"parameter_calibration_duplicate:{key[0]}:{key[1]}")
        by_key[key] = row
    for (mid, parameter), (value, direction) in required.items():
        prefix = f"parameter_calibration:{mid}:{parameter}"
        row = by_key.get((mid, parameter))
        if not row:
            incomplete.append(prefix + ":missing")
            continue
        if not _same(row.get("value"), value):
            invalid.append(prefix + ":value_mismatch")
        method = str(row.get("method") or "")
        if method not in CALIBRATION_METHODS:
            invalid.append(prefix + ":method_invalid")
        low, high = _num(row.get("range_low")), _num(row.get("range_high"))
        if low is None or high is None or low > value or high < value or low > high:
            invalid.append(prefix + ":range_invalid")
        if not str(row.get("basis") or "").strip():
            incomplete.append(prefix + ":basis_missing")
        _check_source_ids(
            row.get("source_ids"), prefix=prefix, verified_ids=verified_ids,
            invalid=invalid, incomplete=incomplete,
        )
        market_inputs = row.get("market_price_inputs")
        if market_inputs:
            invalid.append(prefix + ":circular_market_input_for_intrinsic_value")
        if method == "conservative_bound" and low is not None and high is not None:
            expected = low if direction == "benefit" else high
            if not _same(value, expected):
                invalid.append(prefix + ":not_set_to_conservative_bound")
        if method == "working_assumption" and row.get("decision_use") == "primary":
            invalid.append(prefix + ":uncalibrated_working_assumption_cannot_drive_primary")
        if parameter == "retained_value_realization":
            canonical_cash = _mapping(
                _mapping(_mapping(valuation.get("value_bridge_models")).get("result")).get(
                    "cash_accessibility"
                )
            )
            canonical_future = _mapping(
                canonical_cash.get("future_retained_cash_realization")
            )
            canonical_range = _mapping(canonical_future.get("realization_rate_range"))
            canonical_low = _num(canonical_range.get("low"))
            canonical_high = _num(canonical_range.get("high"))
            canonical_value = _num(canonical_future.get("adopted_realization_rate"))
            if canonical_cash and (
                canonical_value is None
                or canonical_low is None
                or canonical_high is None
                or not _same(value, canonical_value)
                or not _same(low, canonical_low)
                or not _same(high, canonical_high)
            ):
                invalid.append(prefix + ":not_cash_accessibility_model_derived")
            if canonical_cash and method == "working_assumption":
                invalid.append(prefix + ":cash_model_cannot_be_working_assumption")
        sensitivity = row.get("sensitivity")
        if not isinstance(sensitivity, dict) or not sensitivity.get("action_at_low") or not sensitivity.get("action_at_high"):
            incomplete.append(prefix + ":two_sided_action_sensitivity_missing")


def _validate_model_comparability(
    valuation: dict[str, Any], report_text: str,
    invalid: list[str], incomplete: list[str],
) -> None:
    models = {
        str(row.get("model_id")): row for row in valuation.get("models") or []
        if isinstance(row, dict) and row.get("status", "active") == "active"
    }
    primary_ids = [mid for mid, row in models.items() if row.get("role") == "primary"]
    rows = valuation.get("model_comparisons")
    if len(models) >= 2 and (not isinstance(rows, list) or not rows):
        incomplete.append("model_comparisons_missing")
        return
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            invalid.append(f"model_comparisons[{index}]:not_object")
            continue
        pair = (str(row.get("model_id") or ""), str(row.get("against_model_id") or ""))
        pairs[pair] = row
    for mid, model in models.items():
        if mid in primary_ids:
            continue
        if str(model.get("route_model_id") or "") == "REPLACEMENT_VALUE":
            epv_primary_ids = [
                pid for pid in primary_ids
                if str((models.get(pid) or {}).get("model_type") or "") == "EPV"
            ]
            against = next((pid for pid in epv_primary_ids if (mid, pid) in pairs), "")
        else:
            against = next((pid for pid in primary_ids if (mid, pid) in pairs), "")
        prefix = f"model_comparison:{mid}"
        if not against:
            incomplete.append(prefix + ":primary_comparison_missing")
            continue
        row = pairs[(mid, against)]
        use = str(row.get("allowed_use") or "")
        if use not in ALLOWED_MODEL_USES:
            invalid.append(prefix + ":allowed_use_invalid")
        if not str(row.get("basis_differences") or "").strip():
            incomplete.append(prefix + ":basis_differences_missing")
        primary = models[against]
        replacement_epv_pair = (
            str(model.get("route_model_id") or "") == "REPLACEMENT_VALUE"
            and str(primary.get("model_type") or "") == "EPV"
        )
        if replacement_epv_pair and use != "cross_check_only":
            invalid.append(prefix + ":replacement_epv_must_be_cross_check_only")
        if use == "cross_check_only" and not replacement_epv_pair:
            invalid.append(prefix + ":cross_check_only_reserved_for_replacement_epv")
        if replacement_epv_pair:
            replacement_result = _mapping(
                _mapping(_mapping(valuation.get("value_bridge_models")).get("result")).get(
                    "replacement_value"
                )
            )
            comparable = (
                _mapping(replacement_result.get("epv_cross_check")).get("status")
                == "COMPARABLE"
            )
            if bool(row.get("comparable")) != comparable:
                invalid.append(prefix + ":replacement_epv_comparability_mismatch")
        rate_contract = (model.get("assumptions") or {}).get("discount_rate") or {}
        primary_rate_contract = (primary.get("assumptions") or {}).get("discount_rate") or {}
        rate = _num(rate_contract.get("value_pct"))
        primary_rate = _num(primary_rate_contract.get("value_pct"))
        # A serialized zero with ``kind=not_applicable`` is not a 0% rate.
        # Treating it as one invents a ten-point NAV/EPV gap.
        rate_applicable = str(rate_contract.get("kind") or "") != "not_applicable"
        primary_rate_applicable = str(primary_rate_contract.get("kind") or "") != "not_applicable"
        rate_gap = (
            abs(rate - primary_rate)
            if rate_applicable and primary_rate_applicable
            and rate is not None and primary_rate is not None
            else None
        )
        scopes_differ = (model.get("basis") or {}).get("cash_flow_scope") != (primary.get("basis") or {}).get("cash_flow_scope")
        comparable = row.get("comparable") is True
        submitted_gap = row.get("discount_rate_difference_pp")
        if rate_gap is not None and not _same(submitted_gap, rate_gap):
            invalid.append(prefix + ":discount_rate_difference_mismatch")
        if rate_gap is None and submitted_gap is not None:
            invalid.append(prefix + ":discount_rate_difference_not_applicable")
        if (rate_gap is not None and rate_gap > 1.0) or scopes_differ:
            if comparable and use == "corroboration":
                invalid.append(prefix + ":non_like_for_like_cannot_corroborate")
            if use == "corroboration":
                invalid.append(prefix + ":basis_mismatch_mislabeled_corroboration")
        model_type = str(model.get("model_type") or "")
        type_count = sum(
            str(item.get("model_type") or "") == model_type
            for item in models.values()
        )
        aliases = [re.escape(mid)]
        if model_type and type_count == 1:
            aliases.append(re.escape(model_type))
        model_anchor = "(?:" + "|".join(aliases) + ")"
        auditable_fragments = [("report", report_text)]
        synthesis = valuation.get("synthesis") or {}
        auditable_fragments.extend(
            (f"synthesis.{key}", str(synthesis.get(key) or "")) for key in (
                "decision_rule", "divergence_explanation",
            )
        )
        auditable_fragments.extend(
            (f"model_comparison.{item.get('model_id')}", str(item.get("basis_differences") or ""))
            for item in valuation.get("model_comparisons") or []
            if isinstance(item, dict)
        )
        semantic_aliases = {
            "M:DCF_FCFE:v1": r"(?:DCF[_ -]?FCFE|P[_ -]?FCFE|FCFE)",
            "M:DDM:v1": r"DDM",
            "M:NAV:v1": r"NAV",
        }
        alias_pattern = semantic_aliases.get(mid)
        if alias_pattern:
            model_anchor = "(?:" + model_anchor[3:-1] + "|" + alias_pattern + ")"
        overstatement_scope = ""
        for scope, fragment in auditable_fragments:
            for sentence in re.split(r"[。！？!?;；\n]+", fragment):
                if not re.search(model_anchor, sentence, re.I):
                    continue
                claim = re.search(r"交叉验证|相互印证|corroborat", sentence, re.I)
                if not claim:
                    continue
                prefix = sentence[max(0, claim.start() - 18):claim.start()]
                if re.search(r"不(?:可|能|构成|是)?|禁止|并非|不得|never|not|cannot", prefix, re.I):
                    continue
                overstatement_scope = scope
                break
            if overstatement_scope:
                break
        if use != "corroboration" and overstatement_scope:
            invalid.append(
                f"model_comparison:{mid}:report_overstates_noncomparable_model:"
                f"{overstatement_scope}"
            )


def _validate_calculation_integrity(
    valuation: dict[str, Any], bundle: dict[str, Any], report_text: str,
    invalid: list[str], warnings: list[str],
) -> None:
    for model in valuation.get("models") or []:
        if not isinstance(model, dict) or model.get("status", "active") != "active":
            continue
        mid = str(model.get("model_id") or "")
        assumptions = model.get("assumptions") or {}
        result = model.get("result") or {}
        if model.get("model_type") == "DDM":
            r = _num((assumptions.get("discount_rate") or {}).get("value_pct"))
            g = _num((assumptions.get("terminal_growth") or {}).get("value_pct"))
            dps = _num(assumptions.get("dps_hkd"))
            value = _num(result.get("value_per_share"))
            if None not in {r, g, dps, value} and r > g:
                expected = dps * (1 + g / 100) / ((r - g) / 100)
                if not _same(value, expected, tolerance=0.01):
                    invalid.append(f"{mid}:ddm_formula_mismatch:{value}!={expected:.4f}")
        if model.get("model_type") == "RETURN_DECOMPOSITION":
            dividend = _num(assumptions.get("dividend_yield_pct")) or 0.0
            growth = _num(assumptions.get("growth_value_return_pct")) or 0.0
            decay = _num(assumptions.get("moat_decay_pct")) or 0.0
            required = _num(assumptions.get("required_return_pct"))
            gross = _num(result.get("gross_return_pct"))
            margin = _num(result.get("return_safety_margin_pct"))
            realization = _num(assumptions.get("retained_value_realization"))
            expected_gross = dividend + growth * (
                realization if realization is not None else 1.0
            )
            if gross is None or not _same(gross, expected_gross, tolerance=0.01):
                invalid.append(f"{mid}:gross_return_formula_mismatch")
            decay_mode = str((model.get("decay_treatment") or {}).get("mode") or "incremental_hurdle")
            expected_margin = (
                expected_gross - required
                if decay_mode in {"scenario_only", "cash_flow_adjustment"}
                else expected_gross - required - decay
            ) if required is not None else None
            if required is not None and (margin is None or not _same(margin, expected_margin, tolerance=0.01)):
                invalid.append(f"{mid}:return_safety_margin_formula_mismatch")
    normalized = ((bundle.get("factor3") or {}).get("gg_normalized") or {})
    aa = _num(normalized.get("aa_norm_3y"))
    maintenance = _num(normalized.get("maintenance_capex"))
    full = _num(normalized.get("full_capex_3y"))
    conservative_aa = _num((((bundle.get("factor3") or {}).get("aa_avg") or {}).get("3y")))
    if None not in {aa, maintenance, full, conservative_aa}:
        expected = max(0.0, conservative_aa + full - maintenance)
        if not _same(aa, expected, tolerance=0.01):
            invalid.append(f"normalized_aa_formula_mismatch:{aa}!={expected:.4f}")
    fcfe = ((bundle.get("factor3") or {}).get("gg_fcfe") or {})
    if fcfe:
        if fcfe.get("base_semantics") != "distributed_fcfe_owner_return_pct":
            invalid.append("gg_fcfe:base_semantics_missing_or_invalid")
        if _num(fcfe.get("fcfe_yield_pct")) is None:
            invalid.append("gg_fcfe:raw_fcfe_yield_missing")
        if not _same(fcfe.get("base"), fcfe.get("distributed_fcfe_yield_pct")):
            invalid.append("gg_fcfe:distributed_yield_identity_mismatch")
    if re.search(r"AA\s*=\s*(?:NP|净利润|歸母|归母).{0,120}-\s*W", report_text, re.I | re.S):
        invalid.append("report_uses_double_counting_np_minus_w_aa_formula")
    for match in re.finditer(r"λ\s*/\s*([0-9.]+)\s*[≈=].{0,40}?×\s*([0-9.]+)", report_text):
        denominator, displayed = _num(match.group(1)), _num(match.group(2))
        lambda_values = [
            _num((row.get("assumptions") or {}).get("retained_value_realization"))
            for row in valuation.get("models") or [] if isinstance(row, dict)
        ]
        lambda_values = [value for value in lambda_values if value is not None]
        if denominator and displayed is not None and lambda_values:
            expected = lambda_values[0] / denominator
            if not _same(displayed, expected, tolerance=0.01):
                invalid.append("report_lambda_ratio_arithmetic_mismatch")
    dps_by_year: dict[str, set[float]] = {}
    for line in report_text.splitlines():
        if "DPS" not in line.upper():
            continue
        # Bind only an explicit year↔DPS pair.  A DPS sentence commonly also
        # contains EPS, payout ratio, GG parameters and scenario values; taking
        # every decimal from that line creates false cross-year conflicts.
        patterns = (
            r"(?:FY)?(20\d{2})[^\n]{0,48}?\bDPS\s*(?:=|:)?\s*(0\.\d{2,4})",
            r"\bDPS[^\n]{0,24}?(?:FY)?(20\d{2})\s*(?:=|:)?\s*(0\.\d{2,4})",
        )
        for pattern in patterns:
            for year, value in re.findall(pattern, line, re.I):
                dps_by_year.setdefault(year, set()).add(float(value))
    for year, values in dps_by_year.items():
        if len(values) > 1:
            invalid.append(f"report_dps_identity_conflict:{year}:{'|'.join(map(str, sorted(values)))}")
    auditable_text = report_text + "\n" + json.dumps(valuation, ensure_ascii=False)
    if "最高" in auditable_text and re.search(r"利息.{0,80}(?:最高|最大).{0,40}(?:利率|收益率)", auditable_text, re.S):
        invalid.append("maximum_balance_cannot_be_used_as_average_yield_denominator")


def _validate_joint_stress_and_action(
    valuation: dict[str, Any], *, cash_required: bool,
    invalid: list[str], incomplete: list[str],
) -> None:
    rows = valuation.get("joint_stress_tests")
    if not isinstance(rows, list) or not rows:
        incomplete.append("joint_stress_tests_missing")
        rows = []
    has_complete = False
    stress_actions: list[str] = []
    for index, row in enumerate(rows):
        prefix = f"joint_stress_tests[{index}]"
        if not isinstance(row, dict):
            invalid.append(prefix + ":not_object")
            continue
        inputs = row.get("simultaneous_inputs")
        if not isinstance(inputs, dict) or len(inputs) < 3:
            incomplete.append(prefix + ":at_least_three_inputs_required")
            continue
        keys = set(inputs)
        if cash_required and not keys.intersection({"cash_access_pct", "retained_value_realization", "accessible_cash_amount"}):
            incomplete.append(prefix + ":cash_access_input_missing")
        if not keys.intersection({"normalized_earnings", "normalized_profit", "owner_earnings"}):
            incomplete.append(prefix + ":earnings_input_missing")
        if "payout_ratio" not in keys:
            incomplete.append(prefix + ":payout_input_missing")
        output = row.get("output")
        if not isinstance(output, dict) or _num(output.get("value_per_share")) is None:
            incomplete.append(prefix + ":value_output_missing")
        action = str((output or {}).get("action") or "")
        if action not in ACTIONS:
            invalid.append(prefix + ":action_invalid")
        else:
            stress_actions.append(action)
        if not str(row.get("decision_implication") or "").strip():
            incomplete.append(prefix + ":decision_implication_missing")
        if len(inputs) >= 3 and action in ACTIONS:
            has_complete = True
    policy = valuation.get("action_policy")
    if not isinstance(policy, dict):
        incomplete.append("action_policy_missing")
        return
    holder_action = str(policy.get("current_holders_action") or "")
    nonholder_action = str(policy.get("nonholders_action") or "")
    if holder_action not in ACTIONS or nonholder_action not in ACTIONS:
        invalid.append("action_policy:action_invalid")
    if holder_action != nonholder_action:
        friction = policy.get("holder_specific_friction")
        if not isinstance(friction, dict) or _num(friction.get("quantified_cost_pct")) is None or not friction.get("source_ids"):
            invalid.append("action_policy:endowment_difference_without_quantified_friction")
    precedence = policy.get("precedence_order")
    if not isinstance(precedence, list) or len(precedence) < 4:
        incomplete.append("action_policy:precedence_order_missing")
    upgrade = str(policy.get("upgrade_requires") or "")
    if cash_required and not re.search(r"cash|现金|分配|可达|兑现", upgrade, re.I):
        invalid.append("action_policy:upgrade_ignores_decisive_cash_question")
    action_rank = {"buy": 0, "hold": 1, "avoid": 2}
    stress_action = max(stress_actions, key=action_rank.get) if stress_actions else ""
    if has_complete and stress_action and policy.get("joint_stress_action") != stress_action:
        invalid.append("action_policy:joint_stress_action_mismatch")
    primary_return_margins = [
        _num((row.get("result") or {}).get("return_safety_margin_pct"))
        for row in valuation.get("models") or []
        if isinstance(row, dict) and row.get("status", "active") == "active"
        and row.get("role") == "primary"
        and row.get("model_type") == "RETURN_DECOMPOSITION"
    ]
    if any(value is not None and value < 0 for value in primary_return_margins):
        synthesis_action = str((valuation.get("synthesis") or {}).get("action") or "")
        if synthesis_action == "buy":
            invalid.append("action_policy:buy_with_negative_primary_return_margin")
        if nonholder_action == "buy":
            invalid.append("action_policy:nonholder_buy_with_negative_primary_return_margin")


def _validate_synthesis_parameter_identity(
    valuation: dict[str, Any], invalid: list[str]
) -> None:
    """Prevent prose λ from drifting away from the modeled realization rate."""
    synthesis = valuation.get("synthesis") or {}
    decision_rule = str(synthesis.get("decision_rule") or "")
    match = re.search(r"(?:λ|lambda)\s*[=:：]\s*(0(?:\.\d+)?|1(?:\.0+)?)", decision_rule, re.I)
    if not match:
        return
    displayed = _num(match.group(1))
    modeled = {
        round(value, 8)
        for model in valuation.get("models") or []
        if isinstance(model, dict)
        and model.get("status", "active") == "active"
        and model.get("role") == "primary"
        and (value := _num(
            (model.get("assumptions") or {}).get("retained_value_realization")
        )) is not None
    }
    if displayed is not None and modeled and any(
        not math.isclose(displayed, value, rel_tol=1e-6, abs_tol=1e-6)
        for value in modeled
    ):
        invalid.append("synthesis_lambda_retained_value_realization_mismatch")


def _validate_value_realization_evidence(
    output: Path, valuation: dict[str, Any], verified_ids: set[str],
    invalid: list[str], incomplete: list[str],
) -> None:
    observations = {
        str(row.get("observation_id")): row
        for row in _load(output / "fact_observations.json").get("observations") or []
        if isinstance(row, dict)
    }
    realization_owners = [
        model for model in valuation.get("models") or []
        if isinstance(model, dict) and model.get("status", "active") == "active"
        and isinstance(model.get("value_realization_bridge"), dict)
    ]
    synthesis = valuation.get("synthesis") or {}
    if isinstance(synthesis.get("value_realization_bridge"), dict):
        realization_owners.append({
            "model_id": "synthesis", "status": "active",
            "value_realization_bridge": synthesis["value_realization_bridge"],
        })
    for model in realization_owners:
        bridge = model.get("value_realization_bridge")
        if not isinstance(bridge, dict):
            continue
        mid = str(model.get("model_id") or "unknown")
        payout = _num(bridge.get("payout_ratio"))
        source_ids = bridge.get("payout_source_ids") or []
        if not isinstance(source_ids, list) or not source_ids:
            incomplete.append(f"{mid}:value_realization_payout_source_missing")
            continue
        matched = False
        for source_id in source_ids:
            row = observations.get(str(source_id)) or {}
            if str(source_id) not in verified_ids:
                invalid.append(f"{mid}:value_realization_payout_source_unverified:{source_id}")
                continue
            if row.get("fact_name") != "dividend_payout_ratio_pct":
                invalid.append(f"{mid}:value_realization_payout_source_wrong_fact:{source_id}")
                continue
            observed = _num(row.get("normalized_value"))
            if payout is not None and observed is not None and _same(payout, observed / 100):
                matched = True
        if not matched:
            invalid.append(f"{mid}:value_realization_payout_ratio_evidence_mismatch")


def validate_decision_reliability(
    output_dir: str | Path, *, report_text: str = "", enforced: bool = True,
    valuation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    valuation = valuation_override if isinstance(valuation_override, dict) else _load(output / "valuation_model.json")
    bundle = _load(output / "compute_bundle.json")
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if not valuation:
        incomplete.append("valuation_model_missing")
    elif str((valuation.get("synthesis") or {}).get("action") or "") == "unresolved":
        # Reliability here means the product faithfully withholds a price
        # action.  Do not require a fabricated primary model, stress grid, or
        # value range merely to make an unavailable valuation look complete.
        if not str((valuation.get("synthesis") or {}).get("decision_rule") or "").strip():
            incomplete.append("unresolved_synthesis_decision_rule_missing")
        warnings.append("valuation_unresolved_current_price_action_withheld")
    else:
        verified_ids = _verified_source_ids(output)
        verified_fact_names = _verified_fact_names(output)
        cash_required = _cash_question_selected(output, valuation)
        bridge_policy = _load(output / "valuation_model_policy.json")
        canonical_cash = _mapping(
            _mapping(_mapping(valuation.get("value_bridge_models")).get("result")).get(
                "cash_accessibility"
            )
        )
        if (
            cash_required
            and bridge_policy.get("require_value_bridge_models") is True
            and not canonical_cash
        ):
            incomplete.append("cash_accessibility_model_missing")
        _validate_cash_bridge(
            valuation, required=cash_required,
            verified_ids=verified_ids, verified_fact_names=verified_fact_names,
            invalid=invalid, incomplete=incomplete, warnings=warnings,
        )
        _validate_calibrations(valuation, verified_ids, invalid, incomplete)
        _validate_model_comparability(valuation, report_text, invalid, incomplete)
        _validate_calculation_integrity(valuation, bundle, report_text, invalid, warnings)
        _validate_joint_stress_and_action(
            valuation, cash_required=cash_required,
            invalid=invalid, incomplete=incomplete,
        )
        _validate_synthesis_parameter_identity(valuation, invalid)
        _validate_value_realization_evidence(
            output, valuation, verified_ids, invalid, incomplete
        )
    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "DECISION_READY"
    if not enforced:
        state = "REVIEWABLE" if state == "DECISION_READY" else state
    return {
        "schema_version": VALIDATION_VERSION,
        "state": state,
        "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "warnings": warnings,
        "enforced": bool(enforced),
    }


def evaluate_output_decision_reliability(
    output_dir: str | Path, *, report_text: str = "", persist: bool = True
) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _load(output / "decision_reliability_policy.json")
    if not policy:
        return {
            "schema_version": VALIDATION_VERSION,
            "state": "SKIP", "status": "SKIP", "invalid_findings": [],
            "incomplete_findings": [], "warnings": [], "enforced": False,
        }
    result = validate_decision_reliability(
        output, report_text=report_text, enforced=bool(policy.get("enforced"))
    )
    if persist:
        (output / "decision_reliability_validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report")
    parser.add_argument("--initialize-policy", action="store_true")
    parser.add_argument("--run-id", default="manual")
    args = parser.parse_args()
    if args.initialize_policy:
        initialize_decision_reliability_policy(args.output_dir, run_id=args.run_id, enforced=True)
    report_text = ""
    if args.report:
        report_text = Path(args.report).read_text(encoding="utf-8")
    result = evaluate_output_decision_reliability(
        args.output_dir, report_text=report_text, persist=True
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "SKIP"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
