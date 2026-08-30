#!/usr/bin/env python3
"""Deterministically compile canonical value models into valuation projections.

The bridge never accepts prose summaries as inputs.  It stores each canonical
model input, recomputes the model result, and derives machine-readable
valuation projections, numeric claims, and plain reader conclusions.  Output
validation repeats the full compilation, so copied or edited numbers cannot
masquerade as model results.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Any

from scripts.cash_accessibility_model import (
    compute_cash_accessibility_model,
    validate_cash_accessibility_input,
)
from scripts.ordinary_distribution_model import (
    compute_ordinary_distribution_model,
    validate_ordinary_distribution_input,
)
from scripts.replacement_value_model import (
    compute_replacement_value_model,
    project_replacement_value_reader_conclusions,
    validate_replacement_value_model,
)
from scripts.reader_coverage import reader_boundary_findings


INPUT_SCHEMA_VERSION = "valuation-value-bridges-input.v1"
OUTPUT_SCHEMA_VERSION = "valuation-value-bridges.v1"
VALIDATION_SCHEMA_VERSION = "valuation-value-bridges-validation.v1"

MODEL_KEYS = {
    "cash_accessibility",
    "ordinary_distribution",
    "replacement_value",
    "working_capital",
}
_INPUT_FIELDS = {"schema_version", "canonical_fact_bindings", *MODEL_KEYS}
_OUTPUT_FIELDS = {
    "schema_version",
    "model_input",
    "result",
    "valuation_projection",
    "reader_conclusions",
    "numeric_claims",
    "reader_slots",
}
_CASH_WRAPPER_FIELDS = {"model_input", "valuation_context"}
_MODEL_WRAPPER_FIELDS = {"model_input"}
_VALUATION_CONTEXT_FIELDS = {
    "company_id",
    "operating_model_id",
    "position_as_of",
    "ordinary_share_claim_scope",
    "valuation_currency",
    "fx_source_per_valuation_currency",
    "shares",
    "source_fact_ids",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _unknown_fields(
    value: dict[str, Any], allowed: set[str], prefix: str, findings: list[str]
) -> None:
    findings.extend(prefix + ":unknown_field:" + key for key in sorted(set(value) - allowed))


def _model_findings(prefix: str, validation: dict[str, Any]) -> list[str]:
    return [prefix + ":" + str(finding) for finding in _items(validation.get("findings"))]


def _working_capital_api() -> tuple[Any, Any]:
    from scripts.working_capital_model import (  # imported only when that optional model is used
        compute_working_capital_model,
        validate_working_capital_model,
    )

    return validate_working_capital_model, compute_working_capital_model


def validate_valuation_value_bridge_input(payload: Any) -> dict[str, Any]:
    """Validate model wrappers; at least one canonical model must be present."""
    value = _mapping(payload)
    findings: list[str] = []
    if not isinstance(payload, dict):
        findings.append("input_not_object")
    _unknown_fields(value, _INPUT_FIELDS, "$", findings)
    if value.get("schema_version") != INPUT_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    present = [key for key in MODEL_KEYS if key in value]
    if not present:
        findings.append("at_least_one_model_required")

    if "cash_accessibility" in value:
        wrapper = _mapping(value.get("cash_accessibility"))
        _unknown_fields(wrapper, _CASH_WRAPPER_FIELDS, "cash_accessibility", findings)
        if not isinstance(wrapper.get("model_input"), dict):
            findings.append("cash_accessibility:model_input_missing")
        else:
            cash_validation = validate_cash_accessibility_input(wrapper["model_input"])
            if cash_validation.get("state") != "VALID":
                findings.extend(_model_findings("cash_accessibility:model_input", cash_validation))
        context = _mapping(wrapper.get("valuation_context"))
        _unknown_fields(context, _VALUATION_CONTEXT_FIELDS, "cash_accessibility:valuation_context", findings)
        for field in (
            "company_id", "operating_model_id", "position_as_of",
            "ordinary_share_claim_scope", "valuation_currency",
        ):
            if not _text(context.get(field)):
                findings.append("cash_accessibility:" + field + "_missing")
        if not _text(context.get("valuation_currency")):
            findings.append("cash_accessibility:valuation_currency_missing")
        if (
            isinstance(wrapper.get("model_input"), dict)
            and context.get("company_id") != wrapper["model_input"].get("company_id")
        ):
            findings.append("cash_accessibility:company_id_mismatch")
        if (
            isinstance(wrapper.get("model_input"), dict)
            and context.get("position_as_of")
            != wrapper["model_input"].get("position_as_of")
        ):
            findings.append("cash_accessibility:position_as_of_mismatch")
        fx = _number(context.get("fx_source_per_valuation_currency"))
        shares = _number(context.get("shares"))
        if fx is None or fx <= 0:
            findings.append("cash_accessibility:fx_source_per_valuation_currency_invalid")
        elif (
            isinstance(wrapper.get("model_input"), dict)
            and wrapper["model_input"].get("currency") == context.get("valuation_currency")
            and not math.isclose(fx, 1.0, rel_tol=1e-12, abs_tol=1e-12)
        ):
            findings.append("cash_accessibility:same_currency_fx_must_equal_one")
        if shares is None or shares <= 0:
            findings.append("cash_accessibility:shares_invalid")
        source_fact_ids = context.get("source_fact_ids")
        if source_fact_ids is not None and (
            not isinstance(source_fact_ids, list)
            or not source_fact_ids
            or not all(_text(item) for item in source_fact_ids)
        ):
            findings.append("cash_accessibility:source_fact_ids_invalid")

    if "replacement_value" in value:
        wrapper = _mapping(value.get("replacement_value"))
        _unknown_fields(wrapper, _MODEL_WRAPPER_FIELDS, "replacement_value", findings)
        model_input = wrapper.get("model_input")
        if not isinstance(model_input, dict):
            findings.append("replacement_value:model_input_missing")
        else:
            replacement_validation = validate_replacement_value_model(model_input)
            if replacement_validation.get("state") != "REVIEWABLE":
                findings.extend(_model_findings("replacement_value:model_input", replacement_validation))
            if _mapping(model_input.get("model_context")).get("purpose") != "COMPANY_ANALYSIS":
                findings.append("replacement_value:method_fixture_cannot_enter_company_valuation")

    if "ordinary_distribution" in value:
        wrapper = _mapping(value.get("ordinary_distribution"))
        _unknown_fields(
            wrapper, _MODEL_WRAPPER_FIELDS, "ordinary_distribution", findings
        )
        model_input = wrapper.get("model_input")
        if not isinstance(model_input, dict):
            findings.append("ordinary_distribution:model_input_missing")
        else:
            distribution_validation = validate_ordinary_distribution_input(model_input)
            if distribution_validation.get("state") != "VALID":
                findings.extend(
                    _model_findings(
                        "ordinary_distribution:model_input", distribution_validation
                    )
                )
            currency = str(model_input.get("currency") or "")
            unit = str(model_input.get("unit") or "")
            if unit not in {"million", currency + "_m"}:
                findings.append("ordinary_distribution:reader_unit_not_supported")

    if "working_capital" in value:
        wrapper = _mapping(value.get("working_capital"))
        _unknown_fields(wrapper, _MODEL_WRAPPER_FIELDS, "working_capital", findings)
        model_input = wrapper.get("model_input")
        if not isinstance(model_input, dict):
            findings.append("working_capital:model_input_missing")
        else:
            validate_working_capital_model, _ = _working_capital_api()
            validation = validate_working_capital_model(model_input)
            valid_state = validation.get("state") in {"VALID", "REVIEWABLE"}
            if not valid_state:
                findings.extend(_model_findings("working_capital:model_input", validation))

    # All present models belong to one company valuation episode.  A valid
    # specialist model for another company, currency or balance-sheet date
    # must not be allowed to feed a syntactically valid reader slot or value
    # bridge in this episode.
    identities: list[tuple[str, Any, Any, Any]] = []
    for key in sorted(MODEL_KEYS):
        model_input = _mapping(_mapping(value.get(key)).get("model_input"))
        if not model_input:
            continue
        basis = _mapping(model_input.get("basis"))
        identities.append((
            key,
            model_input.get("company_id"),
            model_input.get("position_as_of") or basis.get("as_of"),
            model_input.get("currency") or basis.get("currency"),
        ))
    for index, identity_name in enumerate(("company_id", "position_as_of", "currency"), start=1):
        observed = {str(row[index]) for row in identities if _text(row[index])}
        if len(observed) > 1:
            findings.append("model_identity_mismatch:" + identity_name)

    findings = _unique(findings)
    return {
        "schema_version": "valuation-value-bridges-input-validation.v1",
        "state": "VALID" if not findings else "INVALID",
        "findings": findings,
    }


def _fmt(value: Any, digits: int = 4) -> str:
    number = float(value)
    return f"{number:,.{digits}f}".rstrip("0").rstrip(".")


def _reader_million_amount(currency: str, value: Any, *, digits: int = 2) -> str:
    return f"{currency}{_fmt(value, digits)}百万元"


def _reader_amount(currency: str, unit: str, value: Any, *, digits: int = 2) -> str:
    """Render a public amount without leaking a model's internal unit token."""
    if unit.endswith("_m"):
        return _reader_million_amount(currency, value, digits=digits)
    return f"{currency}{_fmt(value, digits)} {unit}"


def _cash_per_share(amount: Any, *, fx: float, shares: float) -> float:
    return float(amount) / fx / shares


def _cash_projection(
    result: dict[str, Any], context: dict[str, Any]
) -> tuple[
    dict[str, Any],
    list[str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    fx = float(context["fx_source_per_valuation_currency"])
    shares = float(context["shares"])
    valuation_currency = str(context["valuation_currency"])
    existing = result["existing_excess_cash_realization"]
    receivable = result["related_party_receivable_realization"]
    future = result["future_retained_cash_realization"]

    def component_projection(component: dict[str, Any]) -> dict[str, Any]:
        amount_range = component["amount_range"]
        return {
            "amount_range_source_currency": deepcopy(amount_range),
            "adopted_amount_source_currency": component["adopted_value"],
            "per_share_range": {
                key: _cash_per_share(amount_range[key], fx=fx, shares=shares)
                for key in ("low", "base", "high")
            },
            "adopted_per_share": _cash_per_share(
                component["adopted_value"], fx=fx, shares=shares
            ),
            "valuation_destination": component["valuation_destination"],
        }

    existing_projection = component_projection(existing)
    receivable_projection = component_projection(receivable)
    projection = {
        "source_model_id": result["model_id"],
        "company_id": result["company_id"],
        "operating_model_id": context["operating_model_id"],
        "position_as_of": result["position_as_of"],
        "ordinary_share_claim_scope": context["ordinary_share_claim_scope"],
        "source_currency": result["currency"],
        "source_unit": result["unit"],
        "valuation_currency": valuation_currency,
        "fx_source_per_valuation_currency": fx,
        "shares": shares,
        "existing_excess_cash": existing_projection,
        "related_party_receivables": receivable_projection,
        "future_retained_cash": {
            "realization_rate_range": deepcopy(future["realization_rate_range"]),
            "adopted_realization_rate": future["adopted_realization_rate"],
            "valuation_destination": future["valuation_destination"],
        },
    }
    reader: list[str] = []
    as_of = result["as_of"]
    claims = [
        {
            "claim_id": "cash.existing_excess_cash_per_share",
            "source_model_id": result["model_id"],
            "metric": "recognized_existing_excess_cash_per_share",
            "range_low": existing_projection["per_share_range"]["low"],
            "range_high": existing_projection["per_share_range"]["high"],
            "selected_value": existing_projection["adopted_per_share"],
            "currency": valuation_currency,
            "unit": "per_share",
            "as_of": as_of,
            "scope": "ordinary_common_equity_existing_excess_cash",
        },
        {
            "claim_id": "cash.related_party_receivable_per_share",
            "source_model_id": result["model_id"],
            "metric": "recognized_related_party_receivable_per_share",
            "range_low": receivable_projection["per_share_range"]["low"],
            "range_high": receivable_projection["per_share_range"]["high"],
            "selected_value": receivable_projection["adopted_per_share"],
            "currency": valuation_currency,
            "unit": "per_share",
            "as_of": as_of,
            "scope": "ordinary_common_equity_related_party_receivable",
        },
    ]
    existing_selected = (
        f"每股{valuation_currency}{_fmt(existing_projection['adopted_per_share'])}"
    )
    existing_range = (
        f"每股{valuation_currency}{_fmt(existing_projection['per_share_range']['low'])}–"
        f"{_fmt(existing_projection['per_share_range']['high'])}"
    )
    receivable_selected = (
        f"每股{valuation_currency}{_fmt(receivable_projection['adopted_per_share'])}"
    )
    receivable_range = (
        f"每股{valuation_currency}{_fmt(receivable_projection['per_share_range']['low'])}–"
        f"{_fmt(receivable_projection['per_share_range']['high'])}"
    )
    future_rate_range = future.get("realization_rate_range")
    if isinstance(future_rate_range, dict):
        future_selected = (
            _fmt(float(future["adopted_realization_rate"]) * 100, 2) + "%"
        )
        future_range = (
            _fmt(float(future_rate_range["low"]) * 100, 2)
            + "%–"
            + _fmt(float(future_rate_range["high"]) * 100, 2)
            + "%"
        )
        future_phrase = (
            "；未来留存现金实现率为"
            + future_selected
            + "（范围"
            + future_range
            + "）"
        )
        claims.append({
            "claim_id": "cash.future_retained_cash_realization_rate",
            "source_model_id": result["model_id"],
            "metric": "future_retained_cash_realization_rate",
            "range_low": future_rate_range["low"],
            "range_high": future_rate_range["high"],
            "selected_value": future["adopted_realization_rate"],
            "currency": "NOT_APPLICABLE",
            "unit": "ratio",
            "as_of": as_of,
            "scope": "future_retained_cash_operating_value_adjustment",
        })
    else:
        future_selected = "尚无可前推依据"
        future_range = "未形成"
        future_phrase = "；未来留存现金也不预设实现率"
    if existing.get("realization_rate_range") is None:
        existing_phrase = "存量超额现金只保留法律可达上限，主估值不预先计入"
    else:
        existing_phrase = (
            "按可重复回流记录，存量超额现金计入"
            + existing_selected
            + "（范围"
            + existing_range
            + "）"
        )
    if receivable.get("recovery_status") in {"EVIDENCE_BACKED", "PARTIAL_EVIDENCE"}:
        receivable_phrase = (
            "关联方应收按已收款和同机制成熟批次计入"
            + receivable_selected
            + "（范围"
            + receivable_range
            + "）"
        )
    else:
        receivable_phrase = (
            "关联方应收只计已收回金额"
            + receivable_selected
            + "，未收部分视作回收选择权"
        )
    slot = {
        "slot_id": "cash_value_bridge_summary",
        "claim_id": "cash.existing_excess_cash_per_share",
        "claim_ids": [claim["claim_id"] for claim in claims],
        "metric": "CASH_VALUE_BRIDGE_SUMMARY",
        "target_chapter": 12,
        "display_variants": {
            "existing_selected": existing_selected,
            "existing_range": existing_range,
            "receivable_selected": receivable_selected,
            "receivable_range": receivable_range,
            "future_realization_selected": future_selected,
            "future_realization_range": future_range,
        },
        "sentence": (
            existing_phrase
            + "；"
            + receivable_phrase
            + future_phrase
            + "。三者不重复计值，也不能替经营价值证明当前价格。"
        ),
    }
    return projection, reader, claims, [slot]


def _replacement_projection(
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    basis = result["basis"]
    epv = result["epv_cross_check"]
    per_share_range = result.get("per_share_range")
    replacement_low = (
        float(per_share_range["range_low"])
        if isinstance(per_share_range, dict)
        else None
    )
    joint_ceiling: float | None = None
    joint_reason = ""
    recognized_scope = _mapping(result.get("economic_conclusion")).get(
        "recognized_scope"
    )
    if recognized_scope != "ALL_SUBMITTED_COMPONENTS_RECOGNIZED":
        joint_reason = "REPLACEMENT_SCOPE_INCOMPLETE"
    elif epv["status"] != "COMPARABLE":
        joint_reason = "EPV_NOT_COMPARABLE"
    else:
        epv_low = float(epv["epv_per_share_range"]["range_low"])
        if replacement_low is None or replacement_low <= 0 or epv_low <= 0:
            joint_reason = "NON_POSITIVE_LOWER_BOUND"
        else:
            joint_ceiling = min(replacement_low, epv_low)
    projection = {
        "source_model_id": result["model_id"],
        "basis": deepcopy(basis),
        "ordinary_common_equity_range": deepcopy(result["ordinary_common_equity_range"]),
        "per_share_range": deepcopy(result["per_share_range"]),
        "epv_cross_check": deepcopy(epv),
        "joint_protection_price_ceiling": {
            "value": joint_ceiling,
            "currency": basis["currency"],
            "scope": basis["ordinary_share_claim_scope"],
            "as_of": basis["as_of"],
            "meaning": "highest_price_covered_by_both_independent_lower_bounds",
            "reason": joint_reason,
        },
        "economic_conclusion": deepcopy(result["economic_conclusion"]),
    }
    # The public surface is deliberately one synthesized conclusion.  The
    # component-by-component diagnostic belongs to the model result/appendix,
    # not to the reader report.
    reader: list[str] = []
    claims: list[dict[str, Any]] = []
    if isinstance(per_share_range, dict):
        claims.append(
            {
                "claim_id": "replacement.ordinary_common_equity_per_share",
                "source_model_id": result["model_id"],
                "metric": "going_concern_replacement_value_per_share",
                "range_low": per_share_range["range_low"],
                "range_high": per_share_range["range_high"],
                "selected_value": None,
                "currency": basis["currency"],
                "unit": "per_share",
                "as_of": basis["as_of"],
                "scope": basis["ordinary_share_claim_scope"],
            }
        )
    if epv["status"] == "COMPARABLE":
        claims.append(
            {
                "claim_id": "replacement.epv_cross_check_per_share",
                "source_model_id": epv["model_id"],
                "metric": "epv_cross_check_per_share",
                "range_low": epv["epv_per_share_range"]["range_low"],
                "range_high": epv["epv_per_share_range"]["range_high"],
                "selected_value": None,
                "currency": basis["currency"],
                "unit": "per_share",
                "as_of": basis["as_of"],
                "scope": basis["ordinary_share_claim_scope"],
            }
        )
    if joint_ceiling is not None:
        claims.append(
            {
                "claim_id": "replacement.joint_protection_price_ceiling",
                "source_model_id": result["model_id"],
                "metric": "joint_protection_price_ceiling",
                "range_low": joint_ceiling,
                "range_high": joint_ceiling,
                "selected_value": joint_ceiling,
                "currency": basis["currency"],
                "unit": "per_share",
                "as_of": basis["as_of"],
                "scope": basis["ordinary_share_claim_scope"],
            }
        )
        replacement_display = (
            f"每股{basis['currency']}{_fmt(per_share_range['range_low'])}–"
            f"{_fmt(per_share_range['range_high'])}"
        )
        epv_display = (
            f"每股{basis['currency']}{_fmt(epv['epv_per_share_range']['range_low'])}–"
            f"{_fmt(epv['epv_per_share_range']['range_high'])}"
        )
        joint_display = f"每股{basis['currency']}{_fmt(joint_ceiling)}"
        slot = {
            "slot_id": "replacement_epv_cross_check",
            "claim_id": "replacement.ordinary_common_equity_per_share",
            "claim_ids": [claim["claim_id"] for claim in claims],
            "metric": "REPLACEMENT_EPV_CROSS_CHECK",
            "target_chapter": 12,
            "display_variants": {
                "replacement_range": replacement_display,
                "epv_range": epv_display,
                "joint_protection_ceiling": joint_display,
            },
            "sentence": (
                "持续经营重置价值为" + replacement_display + "，EPV为" + epv_display
                + "；两条独立下限共同保护的最高价格为" + joint_display
                + "，取较低者，不相加也不平均。"
            ),
        }
    else:
        reason_text = {
            "REPLACEMENT_SCOPE_INCOMPLETE": "持续经营重置价值还没有覆盖全部关键能力和启动资本",
            "EPV_NOT_COMPARABLE": "EPV与重置价值还没有形成同口径的独立下限",
            "NON_POSITIVE_LOWER_BOUND": "至少一条独立价值线没有正的下限",
        }.get(joint_reason, "两条独立价值线还没有同时成立")
        slot = {
            "slot_id": "replacement_epv_cross_check",
            "claim_ids": [claim["claim_id"] for claim in claims],
            "metric": "REPLACEMENT_EPV_CROSS_CHECK",
            "target_chapter": 12,
            "display_variants": {"reason": reason_text},
            "sentence": (
                reason_text
                + "，因此现在不能声称资产与盈利共同提供价格底；买入价必须由已经单独成立的价值线支撑，"
                + "待两条都完整后再取较低者，不能相加抬高价值。"
            ),
        }
    return projection, reader, claims, [slot]


def _working_capital_projection(
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compile the working-capital public result contract.

    The working-capital owner exposes period-local recurring charges.  UNKNOWN
    periods retain null ranges and are described, never converted to zero.
    """
    basis = _mapping(result.get("basis"))
    valuation_treatment = _mapping(result.get("valuation_treatment"))
    period_projections: list[dict[str, Any]] = []
    reader: list[str] = []
    claims: list[dict[str, Any]] = []
    for index, raw_period in enumerate(_items(result.get("period_results"))):
        period = _mapping(raw_period)
        period_id = str(period.get("period_id") or index)
        charge_range = period.get("recurring_steady_state_charge_range")
        adopted_charge = period.get("adopted_recurring_charge")
        normalized_range = period.get("normalized_owner_cash_range")
        period_projection = {
            "period_id": period_id,
            "actual_cash_capital_charge": _mapping(
                period.get("stock_flow_reconciliation")
            ).get("actual_cash_capital_charge"),
            "current_owner_cash": period.get("current_owner_cash"),
            "normalized_owner_cash_range": deepcopy(normalized_range),
            "adopted_normalized_owner_cash": period.get("adopted_normalized_owner_cash"),
            "recurring_steady_state_charge_range": deepcopy(charge_range),
            "adopted_recurring_charge": adopted_charge,
            "adopted_recurring_endpoint": period.get("adopted_recurring_endpoint"),
            "normalization_status": period.get("normalization_status"),
        }
        period_projections.append(period_projection)
        if charge_range is None or adopted_charge is None:
            continue
        low, high = _two_point_range(charge_range)
        claims.append(
            {
                "claim_id": "working_capital.recurring_charge." + period_id,
                "source_model_id": result["model_id"],
                "metric": "recurring_working_capital_owner_earnings_charge",
                "range_low": low,
                "range_high": high,
                "selected_value": adopted_charge,
                "currency": basis.get("currency", ""),
                "unit": basis.get("unit", ""),
                "as_of": basis.get("as_of", ""),
                "scope": basis.get("ordinary_share_claim_scope", ""),
            }
        )

    reference = _mapping(result.get("reference_period_result"))
    reference_range = reference.get("normalized_owner_cash_range")
    reference_adopted = reference.get("adopted_normalized_owner_cash")
    reference_disclosure_mode = str(
        reference.get("disclosure_mode") or "FULL_GROSS_FLOW"
    )
    reference_actual_charge = _number(
        _mapping(reference.get("stock_flow_reconciliation")).get(
            "actual_cash_capital_charge"
        )
    )
    owner_earnings_treatment = {
        "reference_period_id": reference.get("period_id"),
        "owner_cash_basis": reference.get("owner_cash_basis"),
        "current_owner_cash": reference.get("current_owner_cash"),
        "recurring_steady_state_charge_range": deepcopy(
            reference.get("recurring_steady_state_charge_range")
        ),
        "adopted_recurring_charge": reference.get("adopted_recurring_charge"),
        "adopted_recurring_endpoint": reference.get("adopted_recurring_endpoint"),
        "normalized_owner_cash_range": deepcopy(reference_range),
        "adopted_normalized_owner_cash": reference_adopted,
        "normalization_status": reference.get("normalization_status"),
        "epv_use": valuation_treatment.get("epv_use"),
        "epv_working_capital_treatment": valuation_treatment.get(
            "epv_working_capital_treatment"
        ),
        "terminal_route": valuation_treatment.get("terminal_route"),
        "terminal_owner_cash_source": valuation_treatment.get(
            "terminal_owner_cash_source"
        ),
        "terminal_working_capital_treatment": valuation_treatment.get(
            "terminal_working_capital_treatment"
        ),
    }
    reference_id = str(reference.get("period_id") or "")
    uses_normalized_owner_cash_for_continuing_value = (
        valuation_treatment.get("epv_use") == "NORMALIZED_OWNER_CASH"
        or valuation_treatment.get("terminal_route") == "CONTINUING"
    )
    observed_claim_id: str | None = None
    observed_display: str | None = None
    movement_direction: str | None = None
    if (
        reference_disclosure_mode == "NET_MOVEMENT_ONLY"
        and reference_actual_charge is not None
    ):
        observed_claim_id = "working_capital.observed_cash_capital_charge." + reference_id
        claims.append(
            {
                "claim_id": observed_claim_id,
                "source_model_id": result["model_id"],
                "metric": "observed_working_capital_cash_capital_charge",
                "range_low": reference_actual_charge,
                "range_high": reference_actual_charge,
                "selected_value": reference_actual_charge,
                "currency": basis.get("currency", ""),
                "unit": basis.get("unit", ""),
                "as_of": basis.get("as_of", ""),
                "scope": basis.get("ordinary_share_claim_scope", ""),
            }
        )
        observed_display = _reader_amount(
            str(basis.get("currency", "")),
            str(basis.get("unit", "")),
            abs(reference_actual_charge),
        )
        movement_direction = (
            "净占用"
            if reference_actual_charge > 0
            else "净释放" if reference_actual_charge < 0 else "无净变动"
        )
    if reference_range is None or reference_adopted is None:
        if reference_disclosure_mode == "NET_MOVEMENT_ONLY" and observed_display is not None:
            observed_phrase = (
                "本期观察到营运资本" + movement_direction + observed_display
                if movement_direction != "无净变动"
                else "本期观察到营运资本无净变动"
            )
            if uses_normalized_owner_cash_for_continuing_value:
                slot_sentence = (
                    observed_phrase
                    + "，但现有汇总披露不能区分新项目启动投入与稳态负担，不能据此把其中固定比例永久扣减。"
                    + "主估值不采用50%之类的预设；在项目批次回款和稳态周转证据补齐前，"
                    + "盈利兑现质量需要单独折价观察。"
                )
            else:
                slot_sentence = (
                    observed_phrase
                    + "，但它不能直接被当成可回收资产或永久负担；当前回收路径只计入有证据的实际回收。"
                )
        elif uses_normalized_owner_cash_for_continuing_value:
            slot_sentence = (
                "现有披露不能把新项目启动投入与稳态营运资本负担分开，主估值因此不采用固定比例永久扣减；"
                "在项目批次回款和稳态周转证据补齐前，盈利兑现质量需要单独折价观察。"
            )
        else:
            slot_sentence = (
                "现有披露不能把新项目启动投入、稳态负担和回收分开；当前回收或清算路径只计入"
                "有证据的实际回收，不把当期净变动直接资本化。"
            )
    else:
        normalized_low, normalized_high = _two_point_range(reference_range)
        if uses_normalized_owner_cash_for_continuing_value:
            normalized_display = (
                _reader_amount(str(basis.get("currency", "")), str(basis.get("unit", "")), normalized_low)
                + "–"
                + _reader_amount(str(basis.get("currency", "")), str(basis.get("unit", "")), normalized_high)
            )
            adopted_display = _reader_amount(
                str(basis.get("currency", "")), str(basis.get("unit", "")), reference_adopted
            )
            slot_sentence = (
                "用于持续经营估值的正常化所有者现金为" + normalized_display
                + "，采用" + adopted_display
                + "；这是以稳态经常性负担替换当期占用后的口径，不会把同一负担扣减两次。"
            )
            claims.append(
                {
                    "claim_id": "working_capital.normalized_owner_cash." + reference_id,
                    "source_model_id": result["model_id"],
                    "metric": "normalized_owner_cash_for_valuation",
                    "range_low": normalized_low,
                    "range_high": normalized_high,
                    "selected_value": reference_adopted,
                    "currency": basis.get("currency", ""),
                    "unit": basis.get("unit", ""),
                    "as_of": basis.get("as_of", ""),
                    "scope": basis.get("ordinary_share_claim_scope", ""),
                }
            )
        else:
            slot_sentence = (
                "正常化所有者现金"
                + _reader_amount(str(basis.get("currency", "")), str(basis.get("unit", "")), normalized_low)
                + "–"
                + _reader_amount(str(basis.get("currency", "")), str(basis.get("unit", "")), normalized_high)
                + "仅作为历史经济诊断；"
                "当前采用回收或清算路径，只识别指定营运资本存量的回收，不将该现金流"
                "资本化为持续经营价值。"
            )
    projection = {
        "source_model_id": result["model_id"],
        "basis": deepcopy(basis),
        "periods": period_projections,
        "owner_earnings_valuation_treatment": owner_earnings_treatment,
        "valuation_treatment": deepcopy(valuation_treatment),
        "double_count_flags": deepcopy(result.get("double_count_flags")),
        "economic_conclusion": deepcopy(result.get("economic_conclusion")),
    }
    reference_claim_ids = [
        claim["claim_id"] for claim in claims
        if claim["claim_id"].startswith("working_capital.normalized_owner_cash.")
    ]
    if observed_claim_id is not None:
        reference_claim_ids.append(observed_claim_id)
    display_variants = {"reference_period": reference_id}
    if observed_display is not None and movement_direction is not None:
        display_variants.update(
            {
                "observed_cash_capital_movement": observed_display,
                "movement_direction": movement_direction,
            }
        )
    slot = {
        "slot_id": "working_capital_normalization_summary",
        "claim_ids": reference_claim_ids,
        "metric": "WORKING_CAPITAL_NORMALIZATION_SUMMARY",
        "target_chapter": 12,
        "display_variants": display_variants,
        "sentence": slot_sentence,
    }
    return projection, reader, claims, [slot]


def _ordinary_distribution_projection(
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Project one owner-model result into a compiler-owned reader slot."""
    value = float(result["after_tax_common_distribution"])
    currency = str(result["currency"])
    full_precision = Decimal(str(result["after_tax_common_distribution"]))
    million_3dp = full_precision.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    hundred_million_3dp = (full_precision / Decimal("100")).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    million_display = f"{currency}{million_3dp:,.3f}百万元"
    hundred_million_display = f"约{currency}{hundred_million_3dp:,.3f}亿元"
    sentence = (
        "税费和收取摩擦后的普通股分配为"
        + million_display
        + "，即"
        + hundred_million_display
        + "。"
    )
    claim_id = "distribution.after_tax_common"
    metric = "AFTER_TAX_COMMON_DISTRIBUTION"
    projection = {
        "source_model_id": result["model_id"],
        "company_id": result["company_id"],
        "as_of": result["as_of"],
        "currency": currency,
        "unit": result["unit"],
        "normalized_ordinary_share_operating_earnings": result[
            "normalized_ordinary_share_operating_earnings"
        ],
        "ordinary_distribution_rate": result["ordinary_distribution_rate"],
        "distribution_tax_and_collection_friction_rate": result[
            "distribution_tax_and_collection_friction_rate"
        ],
        "fixed_collection_cost": result["fixed_collection_cost"],
        "after_tax_common_distribution": value,
        "valuation_destination": result["valuation_destination"],
    }
    claim = {
        "claim_id": claim_id,
        "source_model_id": result["model_id"],
        "metric": metric,
        "range_low": value,
        "range_high": value,
        "selected_value": value,
        "currency": currency,
        "unit": result["unit"],
        "as_of": result["as_of"],
        "scope": "ordinary_common_equity_distribution",
    }
    slot = {
        "slot_id": "after_tax_common_distribution",
        "claim_id": claim_id,
        "metric": metric,
        "target_chapter": 12,
        "display_variants": {
            "million_3dp": million_display,
            "hundred_million_3dp_approx": hundred_million_display,
        },
        "sentence": sentence,
    }
    return projection, [], [claim], [slot]


def _two_point_range(value: Any) -> tuple[float, float]:
    item = _mapping(value)
    if "range_low" in item or "range_high" in item:
        return float(item["range_low"]), float(item["range_high"])
    return float(item["low"]), float(item["high"])


def _compile_unchecked(payload: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    projections: dict[str, Any] = {}
    reader: list[str] = []
    claims: list[dict[str, Any]] = []
    reader_slots: list[dict[str, Any]] = []

    if "cash_accessibility" in payload:
        wrapper = payload["cash_accessibility"]
        result = compute_cash_accessibility_model(wrapper["model_input"])
        projection, conclusions, numeric_claims, slots = _cash_projection(
            result, wrapper["valuation_context"]
        )
        results["cash_accessibility"] = result
        projections["cash_accessibility"] = projection
        reader.extend(conclusions)
        claims.extend(numeric_claims)
        reader_slots.extend(slots)

    if "replacement_value" in payload:
        wrapper = payload["replacement_value"]
        result = compute_replacement_value_model(wrapper["model_input"])
        projection, conclusions, numeric_claims, slots = _replacement_projection(result)
        results["replacement_value"] = result
        projections["replacement_value"] = projection
        reader.extend(conclusions)
        claims.extend(numeric_claims)
        reader_slots.extend(slots)

    if "ordinary_distribution" in payload:
        wrapper = payload["ordinary_distribution"]
        result = compute_ordinary_distribution_model(wrapper["model_input"])
        projection, conclusions, numeric_claims, slots = (
            _ordinary_distribution_projection(result)
        )
        results["ordinary_distribution"] = result
        projections["ordinary_distribution"] = projection
        reader.extend(conclusions)
        claims.extend(numeric_claims)
        reader_slots.extend(slots)

    if "working_capital" in payload:
        wrapper = payload["working_capital"]
        _, compute_working_capital_model = _working_capital_api()
        result = compute_working_capital_model(wrapper["model_input"])
        projection, conclusions, numeric_claims, slots = _working_capital_projection(result)
        results["working_capital"] = result
        projections["working_capital"] = projection
        reader.extend(conclusions)
        claims.extend(numeric_claims)
        reader_slots.extend(slots)
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "model_input": deepcopy(payload),
        "result": results,
        "valuation_projection": projections,
        "reader_conclusions": reader,
        "numeric_claims": claims,
        "reader_slots": reader_slots,
    }


def compile_valuation_value_bridges(payload: Any) -> dict[str, Any]:
    """Compute every present model and compile valuation/reader projections."""
    validation = validate_valuation_value_bridge_input(payload)
    if validation["state"] != "VALID":
        raise ValueError("valuation_value_bridge_input_invalid:" + ",".join(validation["findings"]))
    compiled = _compile_unchecked(_mapping(payload))
    boundary = reader_boundary_findings(
        "\n".join(
            [*compiled["reader_conclusions"]]
            + [slot["sentence"] for slot in compiled["reader_slots"]]
        )
    )
    if boundary:
        raise ValueError(
            "valuation_value_bridge_reader_boundary_invalid:" + ",".join(boundary)
        )
    return compiled


def validate_valuation_value_bridges(value: Any) -> dict[str, Any]:
    """Recompute the entire output and reject any free-copied or edited field."""
    observed = _mapping(value)
    findings: list[str] = []
    if not isinstance(value, dict):
        findings.append("output_not_object")
    _unknown_fields(observed, _OUTPUT_FIELDS, "$", findings)
    if observed.get("schema_version") != OUTPUT_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    model_input = observed.get("model_input")
    input_validation = validate_valuation_value_bridge_input(model_input)
    if input_validation["state"] != "VALID":
        findings.extend(_model_findings("model_input", input_validation))
    else:
        expected = _compile_unchecked(_mapping(model_input))
        for field in (
            "result",
            "valuation_projection",
            "reader_conclusions",
            "numeric_claims",
            "reader_slots",
        ):
            if observed.get(field) != expected[field]:
                findings.append(field + "_not_deterministic_projection")
        conclusions = observed.get("reader_conclusions")
        if isinstance(conclusions, list):
            findings.extend(
                "reader_boundary:" + finding
                for finding in reader_boundary_findings("\n".join(str(item) for item in conclusions))
            )
        slots = observed.get("reader_slots")
        if isinstance(slots, list):
            findings.extend(
                "reader_boundary:" + finding
                for finding in reader_boundary_findings(
                    "\n".join(
                        str(_mapping(item).get("sentence") or "") for item in slots
                    )
                )
            )
    findings = _unique(findings)
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "VALID" if not findings else "INVALID",
        "findings": findings,
    }


__all__ = [
    "compile_valuation_value_bridges",
    "validate_valuation_value_bridge_input",
    "validate_valuation_value_bridges",
]
