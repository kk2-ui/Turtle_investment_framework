#!/usr/bin/env python3
"""Compile Golden-report price and downside judgments into an action.

The baseline required-return price is the only price gate.  Cash accessibility
belongs upstream in the ordinary-equity value bridge.  A downside case sizes
the position and describes permanent loss; a low downside XIRR is not a second
required-return test.
"""

from __future__ import annotations

import math
from typing import Any


POLICY_VERSION = "golden-action-policy.v1"
PERMANENT_LOSS_STATES = {
    "BOUNDED",
    "MATERIAL_BUT_FINANCEABLE",
    "CLAIM_OR_SOLVENCY_BREAK",
    "UNRESOLVED_MATERIAL",
}


def _positive_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}_invalid") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name}_invalid")
    return number


def compile_golden_action(
    *,
    current_price: float,
    baseline_max_research_price: float | None,
    baseline_route_established: bool,
    permanent_loss_state: str,
    stress_return_pct: float | None = None,
) -> dict[str, Any]:
    """Return the action identity without treating stress as a second price gate.

    ``stress_return_pct`` is retained for reader display and position context.
    It never participates in the baseline price comparison.
    """
    price = _positive_number(current_price, "current_price")
    state = str(permanent_loss_state)
    if state not in PERMANENT_LOSS_STATES:
        raise ValueError("permanent_loss_state_invalid")
    stress_return = None
    if stress_return_pct is not None:
        stress_return = float(stress_return_pct)
        if not math.isfinite(stress_return):
            raise ValueError("stress_return_pct_invalid")

    result: dict[str, Any] = {
        "schema_version": POLICY_VERSION,
        "primary_price_gate": "BASELINE_REQUIRED_RETURN_PRICE",
        "cash_accessibility_role": "ORDINARY_EQUITY_VALUE_INPUT",
        "stress_role": "POSITION_AND_PERMANENT_LOSS",
        "stress_is_required_return_gate": False,
        "current_price": price,
        "baseline_max_research_price": None,
        "stress_return_pct": stress_return,
        "permanent_loss_state": state,
    }

    if not baseline_route_established or baseline_max_research_price is None:
        result.update({
            "price_gate_passed": None,
            "action": "UNDERWRITING_INCOMPLETE",
            "position_tier": "NONE",
            "reason": "The baseline value route is not established; this is not an overvaluation conclusion.",
        })
        return result

    research_price = _positive_number(
        baseline_max_research_price, "baseline_max_research_price"
    )
    result["baseline_max_research_price"] = research_price
    price_gate_passed = price <= research_price
    result["price_gate_passed"] = price_gate_passed
    if not price_gate_passed:
        result.update({
            "action": "WAIT_FOR_PRICE_OR_VALUE",
            "position_tier": "NONE",
            "reason": "The current price is above the baseline required-return price.",
        })
        return result

    if state == "CLAIM_OR_SOLVENCY_BREAK":
        result.update({
            "action": "AVOID_PERMANENT_LOSS",
            "position_tier": "NONE",
            "reason": "A reachable downside breaks survival or the ordinary-share claim, not merely the stress return hurdle.",
        })
    elif state == "UNRESOLVED_MATERIAL":
        result.update({
            "action": "UNDERWRITING_INCOMPLETE",
            "position_tier": "NONE",
            "reason": "A material permanent-loss carrier is not yet bounded; the price comparison remains visible but is not actionable.",
        })
    elif state == "MATERIAL_BUT_FINANCEABLE":
        result.update({
            "action": "BUILD_LIMITED_POSITION",
            "position_tier": "LIMITED",
            "reason": "The baseline price passes; a financeable but material downside limits initial position size.",
        })
    else:
        result.update({
            "action": "BUILD_POSITION",
            "position_tier": "STANDARD",
            "reason": "The baseline price passes and the permanent-loss path is bounded.",
        })
    return result
