#!/usr/bin/env python3
"""Read-only, synthetic CJO-to-quantitative investment-overlay compiler.

This module deliberately has no dependency on Forecast, Measurement Contract,
settlement, learning notes, a report writer, or trading infrastructure.  It
consumes a validated Frozen CJO plus an independently supplied offline price
and valuation request, then returns a non-authoritative valuation read model.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
from typing import Any

try:
    from scripts import enterprise_judgment_core as core
    from scripts import current_company_cjo_admission as current_cjo_admission
except ImportError:  # pragma: no cover - direct script import fallback
    import enterprise_judgment_core as core
    import current_company_cjo_admission as current_cjo_admission


SCHEMA_VERSION = "cjo-quantitative-investment-overlay.v1"
REQUEST_SCHEMA_VERSION = "cjo-quantitative-investment-overlay-request.v1"
REPORT_PROJECTION_VERSION = "cjo-quantitative-investment-overlay-report-projection.v1"

_RANGE_KEYS = ("low", "base", "high")
_D4_STATES = {"CLOSED", "UNRESOLVED", "UNKNOWN", "INELIGIBLE"}
_ACCESS_STATES = {"ACCESSIBLE", "PARTIAL", "INACCESSIBLE", "UNKNOWN"}
_PERMANENT_LOSS_LEVELS = {"LOW", "MODERATE", "HIGH", "UNKNOWN"}
_METHOD_IDENTITIES = {
    "ASSET_TO_COMMON_EQUITY",
    "NORMAL_EARNINGS_CAPITALIZATION",
    "OWNER_CASH_CAPITALIZATION",
}
_FORBIDDEN_INPUT_KEYS = {
    "forecast", "forecast_id", "forecast_output", "training", "training_sample",
    "measurement_contract", "settlement", "learning_note", "learning_notes",
    "outcome", "outcomes", "actual", "actuals",
}


class CJOQuantitativeInvestmentOverlayError(ValueError):
    """Raised when an overlay request exceeds its read-only authority."""


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


def _find_forbidden_paths(value: Any, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            path = f"{prefix}.{key}"
            if key_text in _FORBIDDEN_INPUT_KEYS:
                findings.append(path)
            findings.extend(_find_forbidden_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_find_forbidden_paths(item, f"{prefix}[{index}]"))
    return findings


def _range_validation(value: Any, label: str, findings: list[str], *, non_negative: bool = True) -> None:
    item = _mapping(value)
    if set(item) != set(_RANGE_KEYS) or any(not _finite(item.get(key)) for key in _RANGE_KEYS):
        findings.append(label + "_must_be_finite_low_base_high_range")
        return
    low, base, high = (float(item[key]) for key in _RANGE_KEYS)
    if low > base or base > high:
        findings.append(label + "_range_order_invalid")
    if non_negative and low < 0:
        findings.append(label + "_must_be_non_negative")


def _range(value: dict[str, Any]) -> dict[str, float]:
    return {key: float(value[key]) for key in _RANGE_KEYS}


def _range_math(left: dict[str, float], right: dict[str, float], *, operation: str) -> dict[str, float]:
    if operation == "add":
        return {key: left[key] + right[key] for key in _RANGE_KEYS}
    if operation == "subtract":
        return {key: left[key] - right[key] for key in _RANGE_KEYS}
    raise AssertionError("unsupported range operation")


def _range_scale(value: dict[str, float], factor: float) -> dict[str, float]:
    return {key: value[key] * factor for key in _RANGE_KEYS}


def _range_divide(value: dict[str, float], denominator: float) -> dict[str, float]:
    return {key: value[key] / denominator for key in _RANGE_KEYS}


def _trace_ids_valid(raw_ids: Any, cjo_trace_ids: set[str]) -> bool:
    return isinstance(raw_ids, list) and bool(raw_ids) and all(
        isinstance(item, str) and item in cjo_trace_ids for item in raw_ids
    )


def _cjo_ref(cjo: dict[str, Any]) -> dict[str, str]:
    return {
        "cjo_id": cjo["cjo_id"],
        "company_id": cjo["company_id"],
        "cutoff_at": cjo["cutoff_at"],
        "method_version": cjo["method_version"],
    }


def _expected_method_ids(methods: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("identity") or "") for item in methods}


def _transmission_layers(cjo: dict[str, Any]) -> tuple[dict[str, str], dict[str, set[str]]]:
    transmission_layers = {
        str(item.get("transmission_id") or ""): str(item.get("layer") or "")
        for item in _items(_mapping(cjo.get("enterprise_system_ref")).get("financial_transmissions"))
        if isinstance(item, dict)
    }
    trace_layers: dict[str, set[str]] = {}
    for trace in _items(cjo.get("traceability")):
        item = _mapping(trace)
        trace_id = str(item.get("trace_id") or "")
        if trace_id:
            trace_layers[trace_id] = {
                transmission_layers.get(str(transmission_id), "")
                for transmission_id in _items(item.get("financial_transmission_ids"))
                if transmission_layers.get(str(transmission_id), "")
            }
    return transmission_layers, trace_layers


def _axis_is_closed_in_cjo(cjo: dict[str, Any], layer: str) -> tuple[bool, str]:
    """Return whether the Frozen CJO itself supports downstream use of an axis."""
    _, trace_layers = _transmission_layers(cjo)
    if layer == "OWNER_CASH":
        directions = [str(_mapping(cjo.get("owner_cash_transmission")).get("direction") or "")]
    else:
        directions = [
            str(_mapping(item).get("direction") or "")
            for item in _items(cjo.get("permanent_loss_paths"))
        ]
    if not directions or any(direction not in {"IMPROVES", "STABLE"} for direction in directions):
        return False, "CJO_AXIS_DIRECTION_NOT_CLOSED"
    for judgment in _items(cjo.get("forward_judgments")):
        item = _mapping(judgment)
        if not any(layer in trace_layers.get(str(trace_id), set()) for trace_id in _items(item.get("trace_ids"))):
            continue
        if item.get("evidence_state") in {"EVIDENCE_INELIGIBLE", "MODEL_UNCERTAIN"} or item.get("status") == "UNKNOWN":
            return False, "CJO_AXIS_EVIDENCE_NOT_CLOSED"
    return True, "CJO_AXIS_CLOSED"


def _admission_consumes_layer(cjo: dict[str, Any], admission: dict[str, Any], layer: str) -> bool:
    transmission_layers, _ = _transmission_layers(cjo)
    binding = _mapping(_mapping(admission.get("candidate_binding")).get("primary_binding"))
    for raw in _items(binding.get("forward_judgment_bindings")):
        if any(
            transmission_layers.get(str(transmission_id)) == layer
            for transmission_id in _items(_mapping(raw).get("cjo_transmission_ids"))
        ):
            return True
    return False


def _effective_axis_closure(cjo: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    admission = _mapping(request.get("cjo_admission"))
    owner = _mapping(_mapping(request.get("financial_ranges")).get("owner_cash"))
    requested_loss = str(_mapping(request.get("permanent_loss_assessment")).get("level") or "UNKNOWN")
    cash_cjo_closed, cash_reason = _axis_is_closed_in_cjo(cjo, "OWNER_CASH")
    loss_cjo_closed, loss_reason = _axis_is_closed_in_cjo(cjo, "PERMANENT_LOSS")
    cash_binding = _admission_consumes_layer(cjo, admission, "OWNER_CASH")
    loss_binding = _admission_consumes_layer(cjo, admission, "PERMANENT_LOSS")
    cash_closed = owner.get("d4_status") == "CLOSED" and cash_cjo_closed and cash_binding
    loss_closed = requested_loss in {"LOW", "MODERATE"} and loss_cjo_closed and loss_binding
    effective_d4 = str(owner.get("d4_status") or "UNKNOWN")
    if not cash_closed and effective_d4 == "CLOSED":
        effective_d4 = "INELIGIBLE" if cash_reason == "CJO_AXIS_EVIDENCE_NOT_CLOSED" else "UNKNOWN"
    return {
        "cash_closed": cash_closed,
        "effective_d4_status": effective_d4,
        "cash_reason": cash_reason if not cash_cjo_closed else "ADMISSION_CASH_BINDING_MISSING" if not cash_binding else "REQUEST_D4_OPEN",
        "permanent_loss_closed": loss_closed,
        "effective_permanent_loss_level": (
            requested_loss if requested_loss in {"HIGH", "UNKNOWN"} or loss_closed else "UNKNOWN"
        ),
        "permanent_loss_reason": loss_reason if not loss_cjo_closed else "ADMISSION_LOSS_BINDING_MISSING" if not loss_binding else "REQUEST_LOSS_OPEN",
    }


def validate_overlay_request(*, frozen_cjo: Any, overlay_request: Any) -> dict[str, Any]:
    """Validate the bounded, non-canonical input surface for an overlay."""
    cjo = _mapping(frozen_cjo)
    cjo_validation = core.validate_frozen_cjo(cjo)
    findings: list[str] = []
    if cjo_validation["state"] != "VALID":
        findings.extend("frozen_cjo:" + item for item in cjo_validation["findings"])
    elif not cjo["authority"].get("quantitative_read_allowed"):
        findings.append("frozen_cjo.quantitative_read_not_allowed")

    value = _mapping(overlay_request)
    required = {
        "schema_version", "object_class", "overlay_id", "mode", "valuation_as_of", "cjo_ref",
        "financial_ranges", "asset_identity", "valuation_method_identities", "price_snapshot",
        "return_contract", "permanent_loss_assessment", "buy_band_policy", "cjo_admission",
    }
    missing = sorted(required - set(value))
    if missing:
        findings.extend("overlay_request.missing:" + item for item in missing)
    if value.get("schema_version") != REQUEST_SCHEMA_VERSION:
        findings.append("overlay_request.schema_version_invalid")
    if value.get("object_class") != "CJO_QUANTITATIVE_INVESTMENT_OVERLAY_REQUEST":
        findings.append("overlay_request.object_class_invalid")
    if not _text(value.get("overlay_id")):
        findings.append("overlay_request.overlay_id_invalid")
    if value.get("mode") != "SYNTHETIC_OFFLINE":
        findings.append("overlay_request.mode_must_be_synthetic_offline")
    valuation_as_of = _instant(value.get("valuation_as_of"))
    if valuation_as_of is None:
        findings.append("overlay_request.valuation_as_of_invalid")
    forbidden = _find_forbidden_paths(value)
    findings.extend("overlay_request.forbidden_training_or_outcome_input:" + path for path in forbidden)

    if cjo_validation["state"] == "VALID":
        if _mapping(value.get("cjo_ref")) != _cjo_ref(cjo):
            findings.append("overlay_request.cjo_ref_must_match_frozen_cjo")
        admission_validation = current_cjo_admission.validate_frozen_current_company_cjo_admission(
            frozen_cjo=cjo,
            admission_receipt=value.get("cjo_admission"),
            require_overlay=True,
        )
        findings.extend(
            "overlay_request.current_company_cjo_admission:" + item
            for item in admission_validation["findings"]
        )
    traces = {item["trace_id"] for item in cjo.get("traceability") or [] if isinstance(item, dict)}
    financial = _mapping(value.get("financial_ranges"))
    if not _finite(financial.get("share_count")) or float(financial.get("share_count") or 0) <= 0:
        findings.append("financial_ranges.share_count_must_be_positive")
    for name, direction in (
        ("normalized_earnings", _mapping(cjo.get("normal_earnings_transmission")).get("direction")),
        ("owner_cash", _mapping(cjo.get("owner_cash_transmission")).get("direction")),
    ):
        section = _mapping(financial.get(name))
        _range_validation(section.get("range"), "financial_ranges." + name + ".range", findings)
        if section.get("cjo_direction") != direction:
            findings.append("financial_ranges." + name + ".cjo_direction_must_match_frozen_cjo")
        if not _trace_ids_valid(section.get("cjo_trace_ids"), traces):
            findings.append("financial_ranges." + name + ".cjo_trace_ids_invalid")
    owner_cash = _mapping(financial.get("owner_cash"))
    if owner_cash.get("d4_status") not in _D4_STATES:
        findings.append("financial_ranges.owner_cash.d4_status_invalid")

    asset = _mapping(value.get("asset_identity"))
    for field in ("non_cash_common_equity", "book_cash", "accessible_common_cash", "capital_burden"):
        _range_validation(asset.get(field), "asset_identity." + field, findings)
    access_status = asset.get("cash_access_status")
    if access_status not in _ACCESS_STATES:
        findings.append("asset_identity.cash_access_status_invalid")
    elif access_status in {"INACCESSIBLE", "UNKNOWN"}:
        accessible = _mapping(asset.get("accessible_common_cash"))
        if any(_finite(accessible.get(key)) and float(accessible[key]) != 0 for key in _RANGE_KEYS):
            findings.append("asset_identity.inaccessible_or_unknown_cash_must_not_enter_common_equity")
    if asset.get("capital_burden_status") not in {"CLOSED", "UNKNOWN", "INELIGIBLE"}:
        findings.append("asset_identity.capital_burden_status_invalid")
    if not _trace_ids_valid(asset.get("cjo_trace_ids"), traces):
        findings.append("asset_identity.cjo_trace_ids_invalid")

    methods = [_mapping(item) for item in _items(value.get("valuation_method_identities"))]
    if len(methods) != 3 or _expected_method_ids(methods) != _METHOD_IDENTITIES:
        findings.append("valuation_method_identities_must_contain_one_asset_earnings_and_owner_cash_identity")
    method_ids: set[str] = set()
    for index, method in enumerate(methods):
        prefix = f"valuation_method_identities[{index}]"
        method_id = method.get("method_id")
        identity = method.get("identity")
        if not _text(method_id) or method_id in method_ids:
            findings.append(prefix + ".method_id_missing_or_duplicate")
        method_ids.add(str(method_id or ""))
        if identity not in _METHOD_IDENTITIES:
            findings.append(prefix + ".identity_invalid")
        if identity != "ASSET_TO_COMMON_EQUITY":
            rate = method.get("capitalization_rate")
            if not _finite(rate) or not 0 < float(rate) < 1:
                findings.append(prefix + ".capitalization_rate_invalid")
        elif "capitalization_rate" in method:
            findings.append(prefix + ".asset_identity_must_not_have_capitalization_rate")

    price = _mapping(value.get("price_snapshot"))
    if not _text(price.get("snapshot_id")) or not _text(price.get("source_ref")):
        findings.append("price_snapshot.identity_missing")
    if price.get("independence_status") != "INDEPENDENT":
        findings.append("price_snapshot.must_be_independent")
    price_as_of = _instant(price.get("as_of"))
    if price_as_of is None:
        findings.append("price_snapshot.as_of_invalid")
    elif valuation_as_of is not None and price_as_of > valuation_as_of:
        findings.append("price_snapshot.after_valuation_as_of")
    if not _finite(price.get("market_price")) or float(price.get("market_price") or 0) < 0:
        findings.append("price_snapshot.market_price_invalid")

    returns = _mapping(value.get("return_contract"))
    if not isinstance(returns.get("horizon_years"), int) or returns.get("horizon_years", 0) <= 0:
        findings.append("return_contract.horizon_years_invalid")
    if not _finite(returns.get("required_return")) or not 0 < float(returns.get("required_return") or 0) < 1:
        findings.append("return_contract.required_return_invalid")
    _range_validation(returns.get("annual_distribution"), "return_contract.annual_distribution", findings)

    permanent_loss = _mapping(value.get("permanent_loss_assessment"))
    if permanent_loss.get("level") not in _PERMANENT_LOSS_LEVELS:
        findings.append("permanent_loss_assessment.level_invalid")
    if not _text(permanent_loss.get("rationale")):
        findings.append("permanent_loss_assessment.rationale_missing")
    if not _trace_ids_valid(permanent_loss.get("cjo_trace_ids"), traces):
        findings.append("permanent_loss_assessment.cjo_trace_ids_invalid")

    policy = _mapping(value.get("buy_band_policy"))
    if not _finite(policy.get("safety_margin")) or not 0 <= float(policy.get("safety_margin") or -1) < 1:
        findings.append("buy_band_policy.safety_margin_invalid")

    findings = list(dict.fromkeys(findings))
    return {
        "schema_version": REQUEST_SCHEMA_VERSION + ".validation",
        "state": "VALID" if not findings else "INVALID",
        "findings": findings,
    }


def _identity_result(method: dict[str, Any], *, status: str, total_value: dict[str, float] | None,
                     share_count: float, note: str) -> dict[str, Any]:
    return {
        "method_id": method["method_id"],
        "identity": method["identity"],
        "status": status,
        "total_common_equity_value": total_value,
        "per_share_value": _range_divide(total_value, share_count) if total_value is not None else None,
        "note": note,
    }


def _price_maximum(value_per_share: dict[str, float], annual_distribution: dict[str, float],
                   required_return: float, horizon_years: int) -> dict[str, float]:
    distribution_pv = {
        key: sum(annual_distribution[key] / (1 + required_return) ** year for year in range(1, horizon_years + 1))
        for key in _RANGE_KEYS
    }
    return {
        key: distribution_pv[key] + value_per_share[key] / (1 + required_return) ** horizon_years
        for key in _RANGE_KEYS
    }


def _buy_band(*, cjo: dict[str, Any], cash_closed: bool, cash_access_status: str,
              capital_burden_closed: bool, permanent_loss_level: str,
              identities: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    no_direction = cjo["resolution"] in {"NO_PRIMARY", "UNKNOWN", "MIXED"}
    closure_reason: str | None = None
    if permanent_loss_level in {"HIGH", "UNKNOWN"}:
        closure_reason = "CLOSED_PERMANENT_LOSS_RISK"
    elif no_direction:
        closure_reason = "CLOSED_" + cjo["resolution"] + "_CJO"
    elif not cash_closed:
        closure_reason = "CLOSED_D4_OWNER_CASH"
    elif not capital_burden_closed:
        closure_reason = "CLOSED_CAPITAL_BURDEN"
    elif cash_access_status in {"INACCESSIBLE", "UNKNOWN"}:
        closure_reason = "CLOSED_CASH_ACCESSIBILITY"

    usable = [item for item in identities if item["status"] == "USABLE" and item["per_share_value"]]
    research_upper = max((item["per_share_value"]["high"] for item in usable), default=None)
    current_price = float(_mapping(request["price_snapshot"])["market_price"])
    cash_identity = next((item for item in identities if item["identity"] == "OWNER_CASH_CAPITALIZATION"), None)
    cash_price = None
    if cash_identity and cash_identity.get("per_share_value"):
        contract = _mapping(request["return_contract"])
        cash_price = _price_maximum(
            cash_identity["per_share_value"], _range(contract["annual_distribution"]),
            float(contract["required_return"]), int(contract["horizon_years"]),
        )
    if closure_reason:
        return {
            "state": "BUY_BAND_CLOSED" if closure_reason.startswith("CLOSED_PERMANENT") else "RESEARCH_OR_DATA_ONLY",
            "research_zone": {
                "state": "RESEARCH_ONLY" if research_upper is not None else "UNASSESSABLE",
                "maximum_price": research_upper,
                "reason": closure_reason,
            },
            "safety_margin_zone": {"state": closure_reason, "maximum_price": None},
            "conditional_buy_zone": {"state": closure_reason, "maximum_price": None, "conditions": []},
            "data_insufficient_zone": {
                "state": "ACTIVE" if closure_reason in {"CLOSED_D4_OWNER_CASH", "CLOSED_CAPITAL_BURDEN", "CLOSED_CASH_ACCESSIBILITY"} else "NOT_ACTIVE",
                "reason": closure_reason,
            },
            "current_price_position": "NOT_A_BUY_BAND",
            "permanent_loss_closure": permanent_loss_level in {"HIGH", "UNKNOWN"},
        }
    if cash_access_status == "PARTIAL":
        return {
            "state": "CONDITIONAL_ONLY_PARTIAL_CASH_ACCESS",
            "research_zone": {"state": "RESEARCH_ONLY", "maximum_price": research_upper, "reason": "PARTIAL_CASH_ACCESS"},
            "safety_margin_zone": {"state": "CLOSED_PARTIAL_CASH_ACCESS", "maximum_price": None},
            "conditional_buy_zone": {
                "state": "CONDITIONAL_ONLY", "maximum_price": None,
                "conditions": ["Resolve ordinary-share access to restricted cash before setting a buy boundary."],
            },
            "data_insufficient_zone": {"state": "ACTIVE", "reason": "PARTIAL_CASH_ACCESS"},
            "current_price_position": "NOT_A_BUY_BAND",
            "permanent_loss_closure": False,
        }
    assert cash_price is not None
    safety_margin = float(_mapping(request["buy_band_policy"])["safety_margin"])
    safety_maximum = cash_price["low"] * (1 - safety_margin)
    return {
        "state": "CONDITIONAL_BUY_BAND",
        "research_zone": {"state": "OPEN_RESEARCH", "maximum_price": research_upper, "reason": "Not an investment authorization."},
        "safety_margin_zone": {"state": "OPEN_SAFETY_MARGIN", "maximum_price": safety_maximum},
        "conditional_buy_zone": {
            "state": "CONDITIONAL_ONLY", "maximum_price": safety_maximum,
            "conditions": [
                "Frozen CJO remains PRIMARY at the referenced cutoff and method version.",
                "D4 owner-cash closure and capital-burden closure remain valid.",
                "Ordinary-share cash accessibility remains ACCESSIBLE.",
                "Permanent-loss assessment does not rise to HIGH or UNKNOWN.",
            ],
        },
        "data_insufficient_zone": {"state": "NOT_ACTIVE", "reason": None},
        "current_price_position": (
            "WITHIN_CONDITIONAL_BUY_ZONE" if current_price <= safety_maximum
            else "WITHIN_RESEARCH_ZONE" if research_upper is not None and current_price <= research_upper
            else "ABOVE_RESEARCH_ZONE"
        ),
        "permanent_loss_closure": False,
    }


def _expectation_gap(*, cjo: dict[str, Any], identities: list[dict[str, Any]], request: dict[str, Any],
                     share_count: float, cash_closed: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    price = float(_mapping(request["price_snapshot"])["market_price"])
    financial = _mapping(request["financial_ranges"])
    requirements: list[dict[str, Any]] = []
    explainers: list[dict[str, Any]] = []
    range_by_identity = {
        "NORMAL_EARNINGS_CAPITALIZATION": _range(_mapping(financial["normalized_earnings"])["range"]),
        "OWNER_CASH_CAPITALIZATION": _range(_mapping(financial["owner_cash"])["range"]),
    }
    for identity in identities:
        name = identity["identity"]
        if name == "ASSET_TO_COMMON_EQUITY" or identity["status"] != "USABLE":
            continue
        method = next(item for item in _items(request["valuation_method_identities"])
                      if _mapping(item).get("method_id") == identity["method_id"])
        rate = float(_mapping(method)["capitalization_rate"])
        implied = price * share_count * rate
        operating_range = range_by_identity[name]
        item = {
            "method_id": identity["method_id"],
            "identity": name,
            "capitalization_rate": rate,
            "price_implied_operating_requirement": implied,
            "cjo_bound_operating_range": operating_range,
            "market_price_lies_within_identity_range": identity["per_share_value"]["low"] <= price <= identity["per_share_value"]["high"],
        }
        requirements.append(item)
        if item["market_price_lies_within_identity_range"]:
            explainers.append(item)
    if cjo["resolution"] != "PRIMARY":
        return {
            "status": "EXPECTATION_GAP_UNAVAILABLE_" + cjo["resolution"],
            "direction": "UNKNOWN",
            "value": None,
            "selected_requirement": None,
            "reason": "A non-PRIMARY Frozen CJO cannot become a directional investment conclusion.",
        }, requirements
    if len(explainers) > 1:
        return {
            "status": "EXPECTATION_GAP_UNKNOWN_MULTIPLE_PLAUSIBLE_PARAMETER_SETS",
            "direction": "UNKNOWN",
            "value": None,
            "selected_requirement": None,
            "reason": "More than one CJO-consistent operating identity explains the current price.",
        }, requirements
    preferred_identity = (
        "OWNER_CASH_CAPITALIZATION" if cash_closed else "NORMAL_EARNINGS_CAPITALIZATION"
    )
    preferred = next((item for item in requirements if item["identity"] == preferred_identity), None)
    selected = explainers[0] if explainers else preferred
    if selected is None:
        return {
            "status": "EXPECTATION_GAP_UNKNOWN_NO_USABLE_OPERATING_IDENTITY",
            "direction": "UNKNOWN",
            "value": None,
            "selected_requirement": None,
            "reason": "No usable price-implied operating identity is available.",
        }, requirements
    base = selected["cjo_bound_operating_range"]["base"]
    value = base - selected["price_implied_operating_requirement"]
    direction = (
        "CJO_BASE_ABOVE_PRICE_REQUIREMENT" if value > 0
        else "CJO_BASE_BELOW_PRICE_REQUIREMENT" if value < 0
        else "CJO_BASE_EQUALS_PRICE_REQUIREMENT"
    )
    return {
        "status": "EXPECTATION_GAP_UNIQUE_REFERENCE" if explainers else "EXPECTATION_GAP_UNIQUE_REFERENCE_OUTSIDE_RANGE",
        "direction": direction,
        "value": value,
        "selected_requirement": selected,
        "reason": "A single operating identity is used as a synthetic, CJO-bound reference; it is not an investment authorization.",
    }, requirements


def compile_investment_overlay(*, frozen_cjo: Any, overlay_request: Any) -> dict[str, Any]:
    """Compile a candidate-only valuation and conditional BuyBand from a Frozen CJO."""
    cjo = _mapping(frozen_cjo)
    before = deepcopy(cjo)
    validation = validate_overlay_request(frozen_cjo=cjo, overlay_request=overlay_request)
    if validation["state"] != "VALID":
        raise CJOQuantitativeInvestmentOverlayError("overlay_request_rejected:" + ",".join(validation["findings"]))
    request = deepcopy(_mapping(overlay_request))
    axis_closure = _effective_axis_closure(cjo, request)
    financial = _mapping(request["financial_ranges"])
    share_count = float(financial["share_count"])
    normalized_range = _range(_mapping(financial["normalized_earnings"])["range"])
    owner_cash = _mapping(financial["owner_cash"])
    effective_d4_status = str(axis_closure["effective_d4_status"])
    owner_cash_range = _range(owner_cash["range"])
    asset = _mapping(request["asset_identity"])
    asset_value = _range_math(
        _range_math(_range(asset["non_cash_common_equity"]), _range(asset["accessible_common_cash"]), operation="add"),
        _range(asset["capital_burden"]), operation="subtract",
    )
    methods = {_mapping(item)["identity"]: _mapping(item) for item in _items(request["valuation_method_identities"])}
    identities = [
        _identity_result(
            methods["ASSET_TO_COMMON_EQUITY"], status="USABLE", total_value=asset_value,
            share_count=share_count,
            note="Book cash is disclosed but never enters common-equity value directly; only accessible_common_cash is included.",
        ),
        _identity_result(
            methods["NORMAL_EARNINGS_CAPITALIZATION"], status="USABLE",
            total_value=_range_scale(normalized_range, 1 / float(methods["NORMAL_EARNINGS_CAPITALIZATION"]["capitalization_rate"])),
            share_count=share_count,
            note="Normal-earnings identity; it does not substitute for owner-cash closure.",
        ),
        _identity_result(
            methods["OWNER_CASH_CAPITALIZATION"],
            status="USABLE" if axis_closure["cash_closed"] else "UNAVAILABLE_D4_OWNER_CASH",
            total_value=(
                _range_scale(owner_cash_range, 1 / float(methods["OWNER_CASH_CAPITALIZATION"]["capitalization_rate"]))
                if axis_closure["cash_closed"] else None
            ),
            share_count=share_count,
            note=(
                "D4-closed owner-cash identity."
                if axis_closure["cash_closed"]
                else "Owner cash is not closed in both the Frozen CJO and its consumed admission binding; this identity cannot set a BuyBand."
            ),
        ),
    ]
    cash_closed = bool(axis_closure["cash_closed"])
    expectation_gap, requirements = _expectation_gap(
        cjo=cjo, identities=identities, request=request, share_count=share_count, cash_closed=cash_closed,
    )
    buy_band = _buy_band(
        cjo=cjo,
        cash_closed=cash_closed,
        cash_access_status=asset["cash_access_status"],
        capital_burden_closed=asset["capital_burden_status"] == "CLOSED",
        permanent_loss_level=str(axis_closure["effective_permanent_loss_level"]),
        identities=identities,
        request=request,
    )
    signals = [item.get("signal_id") for item in _items(_mapping(cjo["monitoring_contract"]).get("signals")) if _text(item.get("signal_id"))]
    reversal_conditions = [
        {"condition_id": "CJO_MONITORING:" + signal, "condition": "Monitor Frozen CJO signal " + signal + "."}
        for signal in signals
    ]
    reversal_conditions.extend([
        {"condition_id": "D4_OWNER_CASH", "condition": "Close or preserve D4 owner-cash support at the same responsibility boundary."},
        {"condition_id": "CASH_ACCESS", "condition": "Verify ordinary-share access to cash and capital burden."},
        {"condition_id": "PERMANENT_LOSS", "condition": "Close the overlay if permanent-loss assessment becomes HIGH or UNKNOWN."},
    ])
    research_questions = [
        {"question_id": "OVERLAY:D4", "question": "What same-boundary evidence closes owner cash after maintenance and necessary reinvestment?"}
    ] if not cash_closed else []
    if expectation_gap["status"].startswith("EXPECTATION_GAP_UNKNOWN"):
        research_questions.append({
            "question_id": "OVERLAY:EXPECTATION_IDENTITY",
            "question": "Which operating identity is the market actually pricing, and what discriminating evidence would select it?",
        })
    if asset["cash_access_status"] != "ACCESSIBLE":
        research_questions.append({
            "question_id": "OVERLAY:CASH_ACCESS", "question": "What cash is legally and economically reachable by ordinary shareholders?",
        })
    result = {
        "schema_version": SCHEMA_VERSION,
        "object_class": "CJO_QUANTITATIVE_INVESTMENT_OVERLAY",
        "overlay_id": request["overlay_id"],
        "mode": "SYNTHETIC_OFFLINE",
        "valuation_as_of": request["valuation_as_of"],
        "cjo_ref": {**_cjo_ref(cjo), "resolution": cjo["resolution"]},
        "cjo_admission_ref": {
            "admission_id": request["cjo_admission"]["admission_id"],
            "status": request["cjo_admission"]["status"],
            "cjo_ref": deepcopy(request["cjo_admission"]["cjo_ref"]),
        },
        "financial_ranges": {
            "share_count": share_count,
            "normalized_earnings": {"range": normalized_range, "cjo_direction": financial["normalized_earnings"]["cjo_direction"], "cjo_trace_ids": deepcopy(financial["normalized_earnings"]["cjo_trace_ids"])},
            "owner_cash": {"range": owner_cash_range, "d4_status": effective_d4_status, "cjo_direction": owner_cash["cjo_direction"], "cjo_trace_ids": deepcopy(owner_cash["cjo_trace_ids"])},
        },
        "asset_accessibility": {
            "cash_access_status": asset["cash_access_status"],
            "book_cash_disclosed": _range(asset["book_cash"]),
            "accessible_common_cash_included": _range(asset["accessible_common_cash"]),
            "book_cash_directly_added_to_common_equity": False,
            "capital_burden_status": asset["capital_burden_status"],
        },
        "value_identities": identities,
        "price_snapshot_ref": {key: request["price_snapshot"][key] for key in ("snapshot_id", "source_ref", "as_of", "independence_status")},
        "price_overlay": {
            "market_price": float(request["price_snapshot"]["market_price"]),
            "price_implied_operating_requirements": requirements,
            "expectation_gap": expectation_gap,
        },
        "buy_band": buy_band,
        "reversal_conditions": reversal_conditions,
        "research_questions": research_questions,
        "authority": {
            "overlay_status": "CANDIDATE_ONLY",
            "production_status": "PRODUCTION_PENDING",
            "may_modify_frozen_cjo": False,
            "may_modify_training": False,
            "may_modify_report_truth": False,
            "may_authorize_trading": False,
            "report_read_allowed": True,
        },
    }
    if cjo != before:
        raise CJOQuantitativeInvestmentOverlayError("overlay_mutated_frozen_cjo")
    return result


def validate_investment_overlay(overlay: Any) -> dict[str, Any]:
    """Validate an already compiled overlay without recomputing CJO truth."""
    value = _mapping(overlay)
    findings: list[str] = []
    required = {
        "schema_version", "object_class", "overlay_id", "mode", "valuation_as_of", "cjo_ref",
        "cjo_admission_ref", "financial_ranges", "asset_accessibility", "value_identities", "price_snapshot_ref",
        "price_overlay", "buy_band", "reversal_conditions", "research_questions", "authority",
    }
    findings.extend("overlay.missing:" + item for item in sorted(required - set(value)))
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("overlay.schema_version_invalid")
    if value.get("object_class") != "CJO_QUANTITATIVE_INVESTMENT_OVERLAY":
        findings.append("overlay.object_class_invalid")
    if value.get("mode") != "SYNTHETIC_OFFLINE":
        findings.append("overlay.mode_invalid")
    if _instant(value.get("valuation_as_of")) is None:
        findings.append("overlay.valuation_as_of_invalid")
    cjo_ref = _mapping(value.get("cjo_ref"))
    if any(not _text(cjo_ref.get(field)) for field in ("cjo_id", "company_id", "cutoff_at", "method_version")):
        findings.append("overlay.cjo_ref_invalid")
    admission_ref = _mapping(value.get("cjo_admission_ref"))
    if (
        not _text(admission_ref.get("admission_id"))
        or admission_ref.get("status") != current_cjo_admission.PRIMARY_ADMITTED
        or _mapping(admission_ref.get("cjo_ref")) != cjo_ref
    ):
        findings.append("overlay.current_company_cjo_admission_ref_invalid")
    financial = _mapping(value.get("financial_ranges"))
    for field in ("normalized_earnings", "owner_cash"):
        section = _mapping(financial.get(field))
        _range_validation(section.get("range"), "overlay.financial_ranges." + field + ".range", findings)
    if _mapping(financial.get("owner_cash")).get("d4_status") not in _D4_STATES:
        findings.append("overlay.owner_cash_d4_status_invalid")
    accessibility = _mapping(value.get("asset_accessibility"))
    if accessibility.get("book_cash_directly_added_to_common_equity") is not False:
        findings.append("overlay.book_cash_must_not_be_directly_added")
    if accessibility.get("cash_access_status") not in _ACCESS_STATES:
        findings.append("overlay.cash_access_status_invalid")
    if not isinstance(value.get("value_identities"), list) or len(value.get("value_identities")) != 3:
        findings.append("overlay.value_identities_invalid")
    price = _mapping(value.get("price_overlay"))
    if not _finite(price.get("market_price")):
        findings.append("overlay.market_price_invalid")
    expectation = _mapping(price.get("expectation_gap"))
    if not _text(expectation.get("status")) or not _text(expectation.get("direction")):
        findings.append("overlay.expectation_gap_invalid")
    authority = _mapping(value.get("authority"))
    expected_authority = {
        "overlay_status": "CANDIDATE_ONLY",
        "production_status": "PRODUCTION_PENDING",
        "may_modify_frozen_cjo": False,
        "may_modify_training": False,
        "may_modify_report_truth": False,
        "may_authorize_trading": False,
        "report_read_allowed": True,
    }
    if authority != expected_authority:
        findings.append("overlay.authority_must_remain_candidate_only")
    return {
        "schema_version": SCHEMA_VERSION + ".validation",
        "state": "VALID" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def build_overlay_report_projection(overlay: Any) -> dict[str, Any]:
    """Expose a bounded, price-snapshot-free overlay view for report handoff."""
    value = _mapping(overlay)
    validation = validate_investment_overlay(value)
    if validation["state"] != "VALID":
        raise CJOQuantitativeInvestmentOverlayError("report_projection_requires_valid_overlay:" + ",".join(validation["findings"]))
    requirements = [
        {
            key: deepcopy(item[key])
            for key in (
                "method_id", "identity", "capitalization_rate",
                "price_implied_operating_requirement", "cjo_bound_operating_range",
            )
        }
        for item in value["price_overlay"]["price_implied_operating_requirements"]
    ]
    expectation_gap = deepcopy(value["price_overlay"]["expectation_gap"])
    selected = _mapping(expectation_gap.get("selected_requirement"))
    if selected:
        expectation_gap["selected_requirement"] = {
            key: deepcopy(selected[key])
            for key in (
                "method_id", "identity", "capitalization_rate",
                "price_implied_operating_requirement", "cjo_bound_operating_range",
            )
        }
    return {
        "schema_version": REPORT_PROJECTION_VERSION,
        "cjo_ref": deepcopy(value["cjo_ref"]),
        "valuation_identities": deepcopy(value["value_identities"]),
        "price_implied_operating_requirements": requirements,
        "expectation_gap": expectation_gap,
        "buy_band": deepcopy(value["buy_band"]),
        "reversal_conditions": deepcopy(value["reversal_conditions"]),
        "research_questions": deepcopy(value["research_questions"]),
        "authority": {
            "report_read_only": True,
            "may_modify_overlay": False,
            "may_modify_frozen_cjo": False,
            "may_authorize_trading": False,
        },
    }
