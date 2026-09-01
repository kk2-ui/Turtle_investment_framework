#!/usr/bin/env python3
"""Synthetic, read-only quantitative adapter for a canonical Frozen CJO.

The adapter deliberately keeps price and valuation assumptions outside the CJO.
Its result is a development projection, never a real BuyBand, report release, or
investment authorization.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
from typing import Any

try:
    from scripts import enterprise_judgment_core as core
    from scripts import cjo_quantitative_investment_overlay as investment_overlay
except ImportError:  # pragma: no cover - direct script import fallback
    import enterprise_judgment_core as core
    import cjo_quantitative_investment_overlay as investment_overlay


SCHEMA_VERSION = "enterprise-judgment-synthetic-quantitative-adapter.v1"


class EnterpriseJudgmentQuantitativeError(ValueError):
    """Raised when a quantitative consumer attempts to exceed read authority."""


def compile_cjo_to_quantitative_investment_overlay(*, frozen_cjo: Any, overlay_request: Any) -> dict[str, Any]:
    """Compatibility entry point for the dedicated v1 candidate-only overlay.

    The original adapter remains a small synthetic directionality probe.  The
    concrete valuation identities, price-implied requirement, ExpectationGap,
    conditional BuyBand, and report read projection now live in the dedicated
    module so the probe never gains write authority over the Frozen CJO.
    """
    return investment_overlay.compile_investment_overlay(
        frozen_cjo=frozen_cjo,
        overlay_request=overlay_request,
    )


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
    return parsed if parsed.tzinfo is not None else None


def _direction_allows(direction: str, delta: float) -> bool:
    if direction == "IMPROVES":
        return delta >= 0
    if direction == "DETERIORATES":
        return delta <= 0
    if direction == "NONE":
        return delta == 0
    return True


def compile_synthetic_quantitative_overlay(*, frozen_cjo: Any, overlay_input: Any) -> dict[str, Any]:
    """Read one Frozen CJO and compile a non-authoritative synthetic overlay."""
    cjo = _mapping(frozen_cjo)
    before = deepcopy(cjo)
    validation = core.validate_frozen_cjo(cjo)
    if validation["state"] != "VALID":
        raise EnterpriseJudgmentQuantitativeError(
            "synthetic_quantitative_adapter_requires_frozen_cjo:" + ",".join(validation["findings"])
        )
    if not cjo["authority"].get("quantitative_read_allowed"):
        raise EnterpriseJudgmentQuantitativeError("frozen_cjo_quantitative_read_not_allowed")
    data = _mapping(overlay_input)
    if data.get("mode") != "SYNTHETIC":
        raise EnterpriseJudgmentQuantitativeError("quantitative_adapter_mode_must_be_synthetic")
    required = (
        "base_normalized_earnings", "base_owner_cash", "share_count", "required_return",
        "market_price", "horizon_years", "annual_distribution",
    )
    if any(not _finite(data.get(field)) for field in required):
        raise EnterpriseJudgmentQuantitativeError("quantitative_overlay_requires_finite_numeric_inputs")
    if data["share_count"] <= 0 or data["required_return"] <= 0 or data["horizon_years"] <= 0 or data["market_price"] < 0:
        raise EnterpriseJudgmentQuantitativeError("quantitative_overlay_economic_input_invalid")
    if _instant(data.get("price_as_of")) is None:
        raise EnterpriseJudgmentQuantitativeError("quantitative_overlay_price_as_of_invalid")
    driver_ids = {item["variable_id"] for item in cjo["key_operating_drivers"]}
    adjustments = [_mapping(item) for item in _items(data.get("driver_adjustments"))]
    seen: set[str] = set()
    normal_delta = 0.0
    owner_cash_delta = 0.0
    for index, adjustment in enumerate(adjustments):
        driver_id = adjustment.get("driver_id")
        if driver_id not in driver_ids or driver_id in seen:
            raise EnterpriseJudgmentQuantitativeError(
                f"quantitative_overlay.driver_adjustments[{index}].driver_id_unknown_or_duplicate"
            )
        seen.add(driver_id)
        if not _finite(adjustment.get("normalized_earnings_delta")) or not _finite(adjustment.get("owner_cash_delta")):
            raise EnterpriseJudgmentQuantitativeError(
                f"quantitative_overlay.driver_adjustments[{index}].delta_invalid"
            )
        normal_delta += float(adjustment["normalized_earnings_delta"])
        owner_cash_delta += float(adjustment["owner_cash_delta"])
    normal_direction = cjo["normal_earnings_transmission"]["direction"]
    cash_direction = cjo["owner_cash_transmission"]["direction"]
    if cjo["resolution"] == "PRIMARY":
        if not _direction_allows(normal_direction, normal_delta) or not _direction_allows(cash_direction, owner_cash_delta):
            raise EnterpriseJudgmentQuantitativeError("quantitative_overlay_driver_delta_conflicts_with_cjo_direction")

    normalized_earnings = float(data["base_normalized_earnings"]) + normal_delta
    owner_cash = float(data["base_owner_cash"]) + owner_cash_delta
    owner_cash_per_share = owner_cash / float(data["share_count"])
    required_return = float(data["required_return"])
    horizon = int(data["horizon_years"])
    annual_distribution = float(data["annual_distribution"])
    distribution_pv = sum(
        annual_distribution / (1.0 + required_return) ** year
        for year in range(1, horizon + 1)
    )
    synthetic_value_reference = distribution_pv + (
        owner_cash_per_share / required_return
    ) / (1.0 + required_return) ** horizon
    price_implied_terminal = (
        float(data["market_price"]) - distribution_pv
    ) * (1.0 + required_return) ** horizon
    price_implied_owner_cash = price_implied_terminal * required_return

    resolution = cjo["resolution"]
    if resolution == "NO_PRIMARY":
        overlay_status = "NO_PRIMARY_NO_DIRECTIONAL_CONCLUSION"
        expectation_gap: float | None = None
    elif resolution == "UNKNOWN":
        overlay_status = "UNKNOWN_NO_DIRECTIONAL_CONCLUSION"
        expectation_gap = None
    elif resolution == "MIXED":
        overlay_status = "MIXED_NO_DIRECTIONAL_CONCLUSION"
        expectation_gap = owner_cash_per_share - price_implied_owner_cash
    else:
        overlay_status = "SYNTHETIC_REFERENCE_ONLY"
        expectation_gap = owner_cash_per_share - price_implied_owner_cash

    result = {
        "schema_version": SCHEMA_VERSION,
        "object_class": "FROZEN_CJO_SYNTHETIC_QUANTITATIVE_OVERLAY",
        "cjo_ref": {
            "cjo_id": cjo["cjo_id"],
            "company_id": cjo["company_id"],
            "cutoff_at": cjo["cutoff_at"],
            "method_version": cjo["method_version"],
            "resolution": resolution,
        },
        "enterprise_case": {
            "normalized_earnings": normalized_earnings,
            "owner_cash": owner_cash,
            "owner_cash_per_share": owner_cash_per_share,
            "normal_earnings_direction": normal_direction,
            "owner_cash_direction": cash_direction,
        },
        "price_overlay": {
            "market_price": float(data["market_price"]),
            "price_as_of": data["price_as_of"],
            "price_implied_owner_cash": price_implied_owner_cash,
            "expectation_gap": expectation_gap,
            "synthetic_value_reference": synthetic_value_reference,
            "status": overlay_status,
            "directional_investment_conclusion": None,
        },
        "authority": {
            "synthetic_only": True,
            "may_modify_cjo": False,
            "real_buy_band_authorized": False,
            "report_release_authorized": False,
            "investment_action_authorized": False,
        },
    }
    if cjo != before:
        raise EnterpriseJudgmentQuantitativeError("quantitative_adapter_mutated_frozen_cjo")
    return result
