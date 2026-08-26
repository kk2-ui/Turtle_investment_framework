#!/usr/bin/env python3
"""Closed synthetic CJO valuation/return snapshots and separated settlement.

The existing V3 calculation proves directional CJO-to-BuyBand propagation.  This
module adds the missing evaluation boundary: operating realisation, the
owner-cash valuation identity, and market return are recorded separately.  It
is deliberately pure and synthetic-fixture-ready; it neither reads prices nor
outcomes, persists a canonical CJO, or authorises a report/portfolio action.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any

try:
    from scripts import enterprise_judgment_v3 as v3
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_v3 as v3


SNAPSHOT_SCHEMA_VERSION = "turtle-cjo-valuation-return-snapshot.v1"
SETTLEMENT_SCHEMA_VERSION = "turtle-cjo-valuation-return-settlement.v1"
VALUATION_ALLOWED_OUTPUTS = ["VALUATION_EVALUATION_ONLY", "RESEARCH_AGENDA"]
OUTCOME_DIMENSIONS = ["NORMALIZED_EARNINGS", "OWNER_CASH", "PERMANENT_LOSS", "MARKET_RETURN"]

_SNAPSHOT_KEYS = {
    "schema_version", "snapshot_id", "cjo_ref", "financial_contract", "outcome_contract", "roles", "frozen_at",
    "object_class", "claim_class", "allowed_outputs",
}
_CJO_REF_KEYS = {"cjo_id", "model_id", "frozen_at"}
_FINANCIAL_KEYS = {
    "base_normalized_earnings", "base_owner_cash", "share_count", "required_return", "market_price",
    "holding_years", "annual_distribution",
}
_OUTCOME_CONTRACT_KEYS = {"operating_window_ends_at", "market_window_ends_at", "settlement_policy", "expected_dimensions"}
_ROLE_KEYS = {"valuation_owner_id", "independent_challenger_id", "outcome_custodian_id"}
_SETTLEMENT_KEYS = {
    "schema_version", "settlement_id", "snapshot_id", "settled_at", "outcome_custodian_id", "operating_result",
    "permanent_loss_result", "market_result", "object_class", "claim_class", "allowed_outputs",
}
_OPERATING_RESULT_KEYS = {"status", "normalized_earnings", "owner_cash"}
_PERMANENT_LOSS_KEYS = {"status", "source"}
_MARKET_RESULT_KEYS = {"status", "terminal_price", "terminal_price_source", "annual_cash_flows"}
_OBSERVATION_KEYS = {"value", "source"}
_SOURCE_KEYS = {"source_id", "source_available_at", "field_ref"}
_CASH_FLOW_KEYS = {"year_index", "amount", "source"}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
        return item
    for field in sorted(set(item).difference(allowed)):
        findings.append(f"{path}_contains_unapproved_field:{field}")
    for field in sorted(allowed.difference(item)):
        findings.append(f"{path}_missing_required_field:{field}")
    return item


def _require_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    raw = item.get(field)
    if not _text(raw):
        findings.append(f"{path}.{field}_required")
        return ""
    return str(raw).strip()


def _validate_source(value: Any, *, path: str, after: datetime, through: datetime, findings: list[str]) -> dict[str, Any]:
    source = _closed(value, _SOURCE_KEYS, path, findings)
    _require_text(source, "source_id", path, findings)
    _require_text(source, "field_ref", path, findings)
    available_at = _instant(source.get("source_available_at"), f"{path}.source_available_at", findings)
    if available_at is not None and available_at <= after:
        findings.append(f"{path}.source_must_follow_snapshot_freeze")
    if available_at is not None and available_at > through:
        findings.append(f"{path}.source_cannot_arrive_after_settlement")
    return source


def _validate_cjo_reference(snapshot: dict[str, Any], cjo: dict[str, Any], findings: list[str]) -> tuple[datetime | None, datetime | None]:
    reference = _closed(snapshot.get("cjo_ref"), _CJO_REF_KEYS, "valuation_snapshot.cjo_ref", findings)
    for field in ("cjo_id", "model_id"):
        _require_text(reference, field, "valuation_snapshot.cjo_ref", findings)
        if reference.get(field) != cjo.get(field):
            findings.append(f"valuation_snapshot.cjo_ref.{field}_must_match_frozen_cjo")
    ref_frozen = _instant(reference.get("frozen_at"), "valuation_snapshot.cjo_ref.frozen_at", findings)
    cjo_state = _mapping(cjo.get("state"))
    cjo_frozen = _instant(cjo_state.get("frozen_at"), "cjo.state.frozen_at", findings)
    if ref_frozen is not None and cjo_frozen is not None and ref_frozen != cjo_frozen:
        findings.append("valuation_snapshot.cjo_ref.frozen_at_must_match_frozen_cjo")
    return ref_frozen, cjo_frozen


def validate_valuation_return_snapshot(snapshot: Any, *, cjo: Any) -> dict[str, Any]:
    """Validate a frozen valuation identity only from an investment-ready CJO."""
    findings: list[str] = []
    item = _closed(snapshot, _SNAPSHOT_KEYS, "valuation_snapshot", findings)
    if item.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        findings.append("valuation_snapshot.schema_version_invalid")
    _require_text(item, "snapshot_id", "valuation_snapshot", findings)
    if item.get("object_class") != "CJO_VALUATION_RETURN_SNAPSHOT":
        findings.append("valuation_snapshot.object_class_invalid")
    if item.get("claim_class") != "CJO_DERIVED_VALUATION_IDENTITY":
        findings.append("valuation_snapshot.claim_class_invalid")
    if item.get("allowed_outputs") != VALUATION_ALLOWED_OUTPUTS:
        findings.append("valuation_snapshot.allowed_outputs_must_remain_evaluation_only")

    value = _mapping(cjo)
    state = v3.validate_state_vector(value.get("state"))
    if state["state"] != "VALID" or _mapping(value.get("state")).get("permission") != "INVESTMENT_INPUT":
        findings.append("valuation_snapshot.requires_frozen_investment_input_cjo")
    _, cjo_frozen_at = _validate_cjo_reference(item, value, findings)
    snapshot_frozen_at = _instant(item.get("frozen_at"), "valuation_snapshot.frozen_at", findings)
    if snapshot_frozen_at is not None and cjo_frozen_at is not None and snapshot_frozen_at < cjo_frozen_at:
        findings.append("valuation_snapshot.must_not_precede_cjo_freeze")

    financial = _closed(item.get("financial_contract"), _FINANCIAL_KEYS, "valuation_snapshot.financial_contract", findings)
    for field in _FINANCIAL_KEYS:
        if not _finite(financial.get(field)):
            findings.append(f"valuation_snapshot.financial_contract.{field}_must_be_finite")
    if _finite(financial.get("share_count")) and float(financial["share_count"]) <= 0:
        findings.append("valuation_snapshot.financial_contract.share_count_must_be_positive")
    if _finite(financial.get("required_return")) and float(financial["required_return"]) <= 0:
        findings.append("valuation_snapshot.financial_contract.required_return_must_be_positive")
    if _finite(financial.get("holding_years")) and (
        float(financial["holding_years"]) <= 0 or not float(financial["holding_years"]).is_integer()
    ):
        findings.append("valuation_snapshot.financial_contract.holding_years_must_be_positive_integer")
    try:
        propagation = v3.compile_production_buy_band(value, financial)
    except v3.EnterpriseJudgmentError as exc:
        findings.append("valuation_snapshot.cjo_propagation_invalid:" + str(exc))
        propagation = None

    outcome_contract = _closed(item.get("outcome_contract"), _OUTCOME_CONTRACT_KEYS, "valuation_snapshot.outcome_contract", findings)
    operating_end = _instant(outcome_contract.get("operating_window_ends_at"), "valuation_snapshot.outcome_contract.operating_window_ends_at", findings)
    market_end = _instant(outcome_contract.get("market_window_ends_at"), "valuation_snapshot.outcome_contract.market_window_ends_at", findings)
    if snapshot_frozen_at is not None:
        if operating_end is not None and operating_end <= snapshot_frozen_at:
            findings.append("valuation_snapshot.operating_window_must_follow_snapshot")
        if market_end is not None and market_end <= snapshot_frozen_at:
            findings.append("valuation_snapshot.market_window_must_follow_snapshot")
    if outcome_contract.get("settlement_policy") != "SEPARATE_OPERATING_VALUE_AND_MARKET":
        findings.append("valuation_snapshot.outcome_contract_must_separate_operating_value_and_market")
    if outcome_contract.get("expected_dimensions") != OUTCOME_DIMENSIONS:
        findings.append("valuation_snapshot.outcome_contract_dimensions_invalid")

    roles = _closed(item.get("roles"), _ROLE_KEYS, "valuation_snapshot.roles", findings)
    role_values = [_require_text(roles, field, "valuation_snapshot.roles", findings) for field in _ROLE_KEYS]
    if len({role for role in role_values if role}) != len(_ROLE_KEYS):
        findings.append("valuation_snapshot.roles_must_be_independent")
    return {
        "valid": not findings,
        "findings": findings,
        "snapshot": deepcopy(item) if not findings else None,
        "propagation": deepcopy(propagation) if not findings else None,
    }


def compile_valuation_return_snapshot(snapshot: Any, *, cjo: Any) -> dict[str, Any]:
    """Compile the immutable economic identity; this grants no production action."""
    result = validate_valuation_return_snapshot(snapshot, cjo=cjo)
    if not result["valid"]:
        raise ValueError("valuation_snapshot_invalid:" + ";".join(result["findings"]))
    return {"snapshot": result["snapshot"], "propagation": result["propagation"]}


def _irr(entry_price: float, annual_cash_flows: list[float], terminal_price: float) -> float | None:
    """Solve the annual cash-flow IRR on a bounded monotonic interval."""
    periods = len(annual_cash_flows)
    def npv(rate: float) -> float:
        return -entry_price + sum(
            cash / (1.0 + rate) ** year for year, cash in enumerate(annual_cash_flows, start=1)
        ) + terminal_price / (1.0 + rate) ** periods
    lower, upper = -0.99, 100.0
    if npv(lower) * npv(upper) > 0:
        return None
    for _ in range(160):
        midpoint = (lower + upper) / 2.0
        value = npv(midpoint)
        if abs(value) < 1e-11:
            return midpoint
        if npv(lower) * value <= 0:
            upper = midpoint
        else:
            lower = midpoint
    return (lower + upper) / 2.0


def validate_valuation_return_settlement(settlement: Any, *, snapshot: Any, cjo: Any) -> dict[str, Any]:
    """Settle operating, valuation identity, and market return without rewriting CJO."""
    frozen = validate_valuation_return_snapshot(snapshot, cjo=cjo)
    findings = ["valuation_snapshot:" + finding for finding in frozen["findings"]]
    item = _closed(settlement, _SETTLEMENT_KEYS, "valuation_settlement", findings)
    if item.get("schema_version") != SETTLEMENT_SCHEMA_VERSION:
        findings.append("valuation_settlement.schema_version_invalid")
    _require_text(item, "settlement_id", "valuation_settlement", findings)
    snapshot_item = _mapping(snapshot)
    if item.get("snapshot_id") != snapshot_item.get("snapshot_id"):
        findings.append("valuation_settlement.snapshot_id_must_match_snapshot")
    if item.get("object_class") != "CJO_VALUATION_RETURN_SETTLEMENT":
        findings.append("valuation_settlement.object_class_invalid")
    if item.get("claim_class") != "SEPARATE_OPERATING_VALUE_MARKET_RECONCILIATION":
        findings.append("valuation_settlement.claim_class_invalid")
    if item.get("allowed_outputs") != VALUATION_ALLOWED_OUTPUTS:
        findings.append("valuation_settlement.allowed_outputs_must_remain_evaluation_only")
    settled_at = _instant(item.get("settled_at"), "valuation_settlement.settled_at", findings)
    roles = _mapping(snapshot_item.get("roles"))
    if item.get("outcome_custodian_id") != roles.get("outcome_custodian_id"):
        findings.append("valuation_settlement.custodian_must_match_snapshot")
    if item.get("outcome_custodian_id") in {roles.get("valuation_owner_id"), roles.get("independent_challenger_id")}:
        findings.append("valuation_settlement.custodian_must_remain_independent")
    frozen_at = _instant(snapshot_item.get("frozen_at"), "valuation_snapshot.frozen_at", findings)
    outcome_contract = _mapping(snapshot_item.get("outcome_contract"))
    operating_end = _instant(outcome_contract.get("operating_window_ends_at"), "valuation_snapshot.outcome_contract.operating_window_ends_at", findings)
    market_end = _instant(outcome_contract.get("market_window_ends_at"), "valuation_snapshot.outcome_contract.market_window_ends_at", findings)
    if settled_at is not None and operating_end is not None and settled_at < operating_end:
        findings.append("valuation_settlement.must_follow_operating_window")
    if settled_at is not None and market_end is not None and settled_at < market_end:
        findings.append("valuation_settlement.must_follow_market_window")
    source_after = frozen_at or datetime.min.replace(tzinfo=timezone.utc)
    source_through = settled_at or datetime.max.replace(tzinfo=timezone.utc)

    operating = _closed(item.get("operating_result"), _OPERATING_RESULT_KEYS, "valuation_settlement.operating_result", findings)
    operating_status = operating.get("status")
    observations: dict[str, float] = {}
    if operating_status not in {"OBSERVED", "CENSORED", "UNKNOWN"}:
        findings.append("valuation_settlement.operating_result.status_invalid")
    for field in ("normalized_earnings", "owner_cash"):
        raw = operating.get(field)
        if operating_status == "OBSERVED":
            observation = _closed(raw, _OBSERVATION_KEYS, f"valuation_settlement.operating_result.{field}", findings)
            if not _finite(observation.get("value")):
                findings.append(f"valuation_settlement.operating_result.{field}.value_must_be_finite")
            else:
                observations[field] = float(observation["value"])
            _validate_source(observation.get("source"), path=f"valuation_settlement.operating_result.{field}.source", after=source_after, through=source_through, findings=findings)
        elif raw is not None:
            findings.append(f"valuation_settlement.operating_result.{field}_must_be_absent_when_not_observed")

    permanent_loss = _closed(item.get("permanent_loss_result"), _PERMANENT_LOSS_KEYS, "valuation_settlement.permanent_loss_result", findings)
    if permanent_loss.get("status") not in {"OBSERVED_NO", "OBSERVED_YES", "UNKNOWN", "CENSORED"}:
        findings.append("valuation_settlement.permanent_loss_result.status_invalid")
    if permanent_loss.get("status") in {"OBSERVED_NO", "OBSERVED_YES"}:
        _validate_source(permanent_loss.get("source"), path="valuation_settlement.permanent_loss_result.source", after=source_after, through=source_through, findings=findings)
    elif permanent_loss.get("source") is not None:
        findings.append("valuation_settlement.permanent_loss_result.source_must_be_absent_when_unresolved")

    market = _closed(item.get("market_result"), _MARKET_RESULT_KEYS, "valuation_settlement.market_result", findings)
    market_status = market.get("status")
    cash_flows: list[float] = []
    terminal_price: float | None = None
    financial = _mapping(snapshot_item.get("financial_contract"))
    years = int(financial.get("holding_years") or 0) if _finite(financial.get("holding_years")) else 0
    if market_status not in {"OBSERVED", "CENSORED", "UNKNOWN"}:
        findings.append("valuation_settlement.market_result.status_invalid")
    if market_status == "OBSERVED":
        if not _finite(market.get("terminal_price")) or float(market.get("terminal_price")) < 0:
            findings.append("valuation_settlement.market_result.terminal_price_must_be_nonnegative_finite")
        else:
            terminal_price = float(market["terminal_price"])
        _validate_source(market.get("terminal_price_source"), path="valuation_settlement.market_result.terminal_price_source", after=source_after, through=source_through, findings=findings)
        flows = _items(market.get("annual_cash_flows"))
        if len(flows) != years:
            findings.append("valuation_settlement.market_result.cash_flows_must_cover_each_holding_year")
        for index, raw in enumerate(flows):
            flow = _closed(raw, _CASH_FLOW_KEYS, f"valuation_settlement.market_result.annual_cash_flows[{index}]", findings)
            if flow.get("year_index") != index + 1:
                findings.append(f"valuation_settlement.market_result.annual_cash_flows[{index}].year_index_invalid")
            if not _finite(flow.get("amount")) or float(flow.get("amount")) < 0:
                findings.append(f"valuation_settlement.market_result.annual_cash_flows[{index}].amount_must_be_nonnegative_finite")
            else:
                cash_flows.append(float(flow["amount"]))
            _validate_source(flow.get("source"), path=f"valuation_settlement.market_result.annual_cash_flows[{index}].source", after=source_after, through=source_through, findings=findings)
    elif any(market.get(field) is not None for field in ("terminal_price", "terminal_price_source", "annual_cash_flows")):
        findings.append("valuation_settlement.market_result_values_must_be_absent_when_unresolved")

    if findings or frozen["propagation"] is None:
        return {"valid": False, "findings": findings, "operating_reconciliation": None, "valuation_reconciliation": None, "market_reconciliation": None, "learning_authorization": "NONE"}

    propagation = _mapping(frozen["propagation"])
    operating_reconciliation: dict[str, Any]
    valuation_reconciliation: dict[str, Any]
    if operating_status == "OBSERVED":
        actual_normalized = observations["normalized_earnings"]
        actual_owner_cash = observations["owner_cash"]
        operating_reconciliation = {
            "status": "OBSERVED",
            "expected_normalized_earnings": propagation["normalized_earnings"],
            "actual_normalized_earnings": actual_normalized,
            "normalized_earnings_delta": actual_normalized - propagation["normalized_earnings"],
            "expected_owner_cash": propagation["owner_cash"],
            "actual_owner_cash": actual_owner_cash,
            "owner_cash_delta": actual_owner_cash - propagation["owner_cash"],
        }
        actual_terminal_value = actual_owner_cash / float(financial["share_count"]) / float(financial["required_return"])
        expected_terminal_value = propagation["per_share_owner_cash"] / float(financial["required_return"])
        valuation_reconciliation = {
            "status": "OBSERVED_OWNER_CASH_IDENTITY",
            "expected_terminal_value": expected_terminal_value,
            "actual_owner_cash_terminal_value": actual_terminal_value,
            "owner_cash_value_delta": actual_terminal_value - expected_terminal_value,
            "entry_price_implied_owner_cash": propagation["price_implied_owner_cash"],
            "entry_expectation_gap": propagation["expectation_gap"],
        }
    else:
        operating_reconciliation = {"status": operating_status}
        valuation_reconciliation = {"status": "UNKNOWN_OWNER_CASH_IDENTITY" if operating_status == "UNKNOWN" else "CENSORED_OWNER_CASH_IDENTITY"}

    if market_status == "OBSERVED" and terminal_price is not None:
        irr = _irr(float(financial["market_price"]), cash_flows, terminal_price)
        market_reconciliation = {
            "status": "OBSERVED",
            "entry_price": float(financial["market_price"]),
            "terminal_price": terminal_price,
            "cash_distributions": sum(cash_flows),
            "annualized_realized_return": irr,
            "required_return": float(financial["required_return"]),
            "return_spread_to_required": None if irr is None else irr - float(financial["required_return"]),
        }
    else:
        market_reconciliation = {"status": market_status}
    return {
        "valid": True,
        "findings": [],
        "operating_reconciliation": operating_reconciliation,
        "valuation_reconciliation": valuation_reconciliation,
        "market_reconciliation": market_reconciliation,
        "learning_authorization": "CANDIDATE_ONLY",
    }
