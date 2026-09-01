#!/usr/bin/env python3
"""Decompose licensed retail sell-out changes without claiming causal effects.

This is deliberately a diagnostic bridge for competition research.  It splits
Gree's observed retail units/value change into category-market scale, category
mix, and within-category Gree-share contributions.  The contributions are a
Shapley accounting decomposition: their order does not depend on whether a
researcher moves market scale, mix, or Gree share first.  They do *not* show
why any contribution occurred and cannot be used as company revenue, cash,
valuation, return, or investment-decision inputs.
"""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from itertools import permutations
from pathlib import Path
from typing import Any

from scripts.phase10_acquisition import (
    independent_industry_inference_mode,
    validate_independent_industry_data_source,
)


SCHEMA_VERSION = "industry-retail-state-decomposition.v1"
PURPOSE = "COMPETITION_DIAGNOSTIC_ONLY"
ALLOWED_DIMENSIONS = {"channel", "product_type", "capacity_band", "price_band", "region"}
METRICS = {
    "units": ("market_units", "gree_units", "gree_within_cell_unit_share"),
    "value": ("market_value_rmb", "gree_value_rmb", "gree_within_cell_value_share"),
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _cell_key(dimensions: list[str], cell: dict[str, Any]) -> tuple[str, ...]:
    values = cell.get("dimensions")
    if not isinstance(values, dict):
        return ()
    return tuple(str(values.get(field) or "") for field in dimensions)


def validate_industry_retail_state_decomposition(payload: Any) -> dict[str, Any]:
    """Validate a two-period, complete licensed retail sell-out panel."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(payload, dict):
        return {
            "schema_version": "industry-retail-state-decomposition-validation.v1",
            "state": "INVALID", "status": "FAIL",
            "invalid_findings": ["payload_not_object"], "incomplete_findings": [],
        }
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(payload.get("analysis_id") or "").startswith("IRSD:"):
        invalid.append("analysis_id_invalid")
    if payload.get("purpose") != PURPOSE:
        invalid.append("purpose_must_be_competition_diagnostic_only")

    source = payload.get("source")
    if not isinstance(source, dict):
        incomplete.append("source_missing")
    else:
        source_validation = validate_independent_industry_data_source(source)
        invalid.extend("source:" + finding for finding in source_validation["invalid_findings"])
        incomplete.extend("source:" + finding for finding in source_validation["incomplete_findings"])
        if source.get("admissible") is not True:
            invalid.append("source_not_admissible")
        metric = ((source.get("industry_data_contract") or {}).get("metric") or {})
        if metric.get("semantic") != "RETAIL_SELL_OUT":
            invalid.append("source_must_be_retail_sell_out")
        if independent_industry_inference_mode(source) not in {
            "WITHIN_PROVIDER_RELATIVE_CHANGE", "LEVEL_WITH_STATED_LIMITS",
        }:
            invalid.append("source_measurement_profile_not_sufficient_for_relative_change")

    base_period = str(payload.get("base_period") or "").strip()
    comparison_period = str(payload.get("comparison_period") or "").strip()
    if not base_period or not comparison_period:
        incomplete.append("two_periods_required")
    elif base_period == comparison_period:
        invalid.append("comparison_period_must_differ_from_base_period")

    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        incomplete.append("dimensions_missing")
        dimensions = []
    elif any(item not in ALLOWED_DIMENSIONS for item in dimensions):
        invalid.append("dimension_invalid")
    elif len(set(dimensions)) != len(dimensions):
        invalid.append("dimension_duplicate")

    cells = payload.get("cells")
    if not isinstance(cells, list) or not cells:
        incomplete.append("cells_missing")
        cells = []
    keys_by_period: dict[str, set[tuple[str, ...]]] = {base_period: set(), comparison_period: set()}
    for index, cell in enumerate(cells):
        prefix = f"cells[{index}]"
        if not isinstance(cell, dict):
            invalid.append(prefix + ":not_object")
            continue
        period = str(cell.get("period") or "")
        if period not in keys_by_period:
            invalid.append(prefix + ":period_not_in_comparison")
        dimension_values = cell.get("dimensions")
        if not isinstance(dimension_values, dict) or set(dimension_values) != set(dimensions):
            invalid.append(prefix + ":dimensions_do_not_match_panel")
        elif any(not str(dimension_values.get(field) or "").strip() for field in dimensions):
            incomplete.append(prefix + ":dimension_value_missing")
        key = _cell_key(dimensions, cell)
        if period in keys_by_period:
            if key in keys_by_period[period]:
                invalid.append(prefix + ":duplicate_category_cell")
            keys_by_period[period].add(key)
        for market_key, gree_key, _ in METRICS.values():
            market_value = cell.get(market_key)
            gree_value = cell.get(gree_key)
            if not _is_number(market_value) or float(market_value) <= 0:
                invalid.append(prefix + f":{market_key}_must_be_positive_number")
            if not _is_number(gree_value) or float(gree_value) < 0:
                invalid.append(prefix + f":{gree_key}_must_be_nonnegative_number")
            elif _is_number(market_value) and float(gree_value) > float(market_value):
                invalid.append(prefix + f":{gree_key}_cannot_exceed_{market_key}")
    if base_period and comparison_period and keys_by_period.get(base_period) != keys_by_period.get(comparison_period):
        invalid.append("category_cells_must_be_complete_and_stable_across_periods")

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": "industry-retail-state-decomposition-validation.v1",
        "state": state, "status": "PASS" if state == "REVIEWABLE" else "FAIL",
        "invalid_findings": invalid, "incomplete_findings": incomplete,
    }


def _aggregate_period(
    cells: list[dict[str, Any]], *, period: str, dimensions: list[str], market_key: str, gree_key: str,
) -> tuple[float, dict[tuple[str, ...], float], dict[tuple[str, ...], float], dict[tuple[str, ...], dict[str, float]]]:
    selected = [item for item in cells if item.get("period") == period]
    market_total = sum(float(item[market_key]) for item in selected)
    mix = {_cell_key(dimensions, item): float(item[market_key]) / market_total for item in selected}
    share = {_cell_key(dimensions, item): float(item[gree_key]) / float(item[market_key]) for item in selected}
    detail = {
        _cell_key(dimensions, item): {"market": float(item[market_key]), "gree": float(item[gree_key])}
        for item in selected
    }
    return market_total, mix, share, detail


def _value(market_total: float, mix: dict[tuple[str, ...], float], share: dict[tuple[str, ...], float]) -> float:
    return market_total * sum(mix[key] * share[key] for key in mix)


def _shapley_contributions(
    base: tuple[float, dict[tuple[str, ...], float], dict[tuple[str, ...], float]],
    comparison: tuple[float, dict[tuple[str, ...], float], dict[tuple[str, ...], float]],
) -> dict[str, float]:
    """Average all six factor orders so no chosen base ordering drives results."""
    labels = ("market_scale", "category_mix", "within_cell_gree_share")
    values = {label: 0.0 for label in labels}
    for order in permutations(labels):
        state = {label: base[index] for index, label in enumerate(labels)}
        previous = _value(state["market_scale"], state["category_mix"], state["within_cell_gree_share"])
        for label in order:
            state[label] = comparison[labels.index(label)]
            current = _value(state["market_scale"], state["category_mix"], state["within_cell_gree_share"])
            values[label] += current - previous
            previous = current
    return {label: value / math.factorial(len(labels)) for label, value in values.items()}


def _metric_decomposition(payload: dict[str, Any], metric_name: str) -> dict[str, Any]:
    market_key, gree_key, share_label = METRICS[metric_name]
    dimensions = payload["dimensions"]
    base = _aggregate_period(payload["cells"], period=payload["base_period"], dimensions=dimensions, market_key=market_key, gree_key=gree_key)
    comparison = _aggregate_period(payload["cells"], period=payload["comparison_period"], dimensions=dimensions, market_key=market_key, gree_key=gree_key)
    base_core, comparison_core = base[:3], comparison[:3]
    contributions = _shapley_contributions(base_core, comparison_core)
    base_gree = _value(*base_core)
    comparison_gree = _value(*comparison_core)
    change = comparison_gree - base_gree
    transitions = []
    for key in sorted(base[3]):
        base_detail = base[3][key]
        comparison_detail = comparison[3][key]
        transitions.append({
            "dimensions": dict(zip(dimensions, key)),
            "base_market": base_detail["market"], "comparison_market": comparison_detail["market"],
            "base_gree": base_detail["gree"], "comparison_gree": comparison_detail["gree"],
            "base_" + share_label: base_detail["gree"] / base_detail["market"],
            "comparison_" + share_label: comparison_detail["gree"] / comparison_detail["market"],
        })
    return {
        "base_gree_total": base_gree,
        "comparison_gree_total": comparison_gree,
        "change": change,
        "contributions": contributions,
        "contribution_sum": sum(contributions.values()),
        "reconciliation_error": sum(contributions.values()) - change,
        "cell_transitions": transitions,
    }


def decompose_industry_retail_state(payload: Any) -> dict[str, Any]:
    """Return a source-bound descriptive decomposition or its validation error."""
    validation = validate_industry_retail_state_decomposition(payload)
    if validation["state"] != "REVIEWABLE":
        return {"computed": False, "validation": validation}
    body = deepcopy(payload)
    source = body["source"]
    source_contract = source["industry_data_contract"]
    return {
        "schema_version": SCHEMA_VERSION,
        "computed": True,
        "analysis_id": body["analysis_id"],
        "purpose": PURPOSE,
        "source_reference": {
            "source_id": source["source_id"], "source_version": source["source_version"],
            "provider_id": source_contract["provider_id"],
            "release_id": source_contract["release"]["release_id"],
            "query_id": source_contract["query_identity"]["query_id"],
            "semantic": source_contract["metric"]["semantic"],
        },
        "base_period": body["base_period"], "comparison_period": body["comparison_period"],
        "dimensions": body["dimensions"],
        "units": _metric_decomposition(body, "units"),
        "value": _metric_decomposition(body, "value"),
        "interpretation_boundary": {
            "allowed": "Describe observed retail market scale, category mix, and within-cell Gree share changes for an H-A/H-B discriminator.",
            "prohibited": [
                "causal attribution", "company revenue recognition", "owner cash", "capital allocation",
                "valuation", "share price", "investment decision", "empirical base rate",
            ],
        },
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"input_invalid:{exc.__class__.__name__}")
    result = decompose_industry_retail_state(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(args.output), "computed": result["computed"]}, ensure_ascii=False))
    return 0 if result["computed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
