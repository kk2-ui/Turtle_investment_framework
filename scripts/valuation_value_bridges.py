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
    _cash_factual_operands,
    compute_cash_accessibility_model,
    validate_cash_accessibility_input,
)
from scripts.ordinary_distribution_model import (
    compute_ordinary_distribution_model,
    validate_ordinary_distribution_input,
)
from scripts.epv_model import compute_epv_model, validate_epv_model_input
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
    "epv",
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
_REPLACEMENT_WRAPPER_FIELDS = {"model_input", "epv_model_id"}
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


def _cash_register_observations(cash_input: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the cash model's already-validated official fact map."""
    register = _mapping(cash_input.get("official_fact_register"))
    return {
        str(item.get("fact_id")): item
        for item in _items(register.get("observations"))
        if isinstance(item, dict) and _text(item.get("fact_id"))
    }


def _validate_cash_value_bridge_canonical_bindings(
    payload: dict[str, Any],
    *,
    wrapper: dict[str, Any],
    context: dict[str, Any],
    findings: list[str],
) -> None:
    """Make the valuation bridge consume—not merely carry—cash official facts.

    The standalone cash model validates every amount/rate/judgment against its
    cutoff official register.  This bridge additionally requires its global
    operand binding ledger to name the exact same fact for every numeric cash
    operand and for the share count that converts the recognized amount into
    ordinary-equity per-share value.
    """
    cash_input = _mapping(wrapper.get("model_input"))
    outer = payload.get("canonical_fact_bindings")
    if not isinstance(outer, list):
        findings.append("cash_accessibility:canonical_fact_bindings_missing")
        return
    outer_by_path: dict[str, str] = {}
    for index, raw in enumerate(outer):
        binding = _mapping(raw)
        path = str(binding.get("path") or "")
        fact_id = str(binding.get("evidence_id") or "")
        if not path or not fact_id:
            findings.append(
                "cash_accessibility:canonical_fact_bindings["
                + str(index) + "]:path_or_evidence_id_missing"
            )
            continue
        if path in outer_by_path:
            findings.append(
                "cash_accessibility:canonical_fact_bindings_duplicate_path:" + path
            )
            continue
        outer_by_path[path] = fact_id
    observations = _cash_register_observations(cash_input)
    local_bindings = _items(cash_input.get("canonical_fact_bindings"))
    cash_operands = _cash_factual_operands(cash_input)
    for raw in local_bindings:
        local = _mapping(raw)
        local_path = str(local.get("path") or "")
        local_fact_id = str(local.get("fact_id") or "")
        if (
            local_path not in cash_operands
            or isinstance(cash_operands[local_path], bool)
            or not isinstance(cash_operands[local_path], (int, float))
        ):
            # Boolean/text cash admission judgments are consumed by the cash
            # model itself; the value bridge's numeric ledger does not invent
            # an arithmetic operand for them.
            continue
        outer_path = "cash_accessibility.model_input." + local_path
        if outer_by_path.get(outer_path) != local_fact_id:
            findings.append(
                "cash_accessibility:canonical_fact_binding_missing_or_mismatch:"
                + outer_path
            )

    source_fact_ids = context.get("source_fact_ids")
    if not isinstance(source_fact_ids, list) or not source_fact_ids or not all(
        _text(item) for item in source_fact_ids
    ):
        findings.append("cash_accessibility:valuation_context_source_fact_ids_missing")
        return
    declared_context_facts = set(source_fact_ids)

    def validate_context_operand(path: str, value: Any, unit: str, *, required: bool) -> None:
        evidence_id = outer_by_path.get(path)
        if not evidence_id:
            if required:
                findings.append("cash_accessibility:canonical_fact_binding_missing:" + path)
            return
        if evidence_id not in declared_context_facts:
            findings.append("cash_accessibility:context_fact_not_declared:" + path)
            return
        observation = observations.get(evidence_id)
        if observation is None:
            findings.append("cash_accessibility:context_fact_not_canonical_official_observation:" + path)
            return
        if observation.get("unit") != unit:
            findings.append("cash_accessibility:context_fact_unit_mismatch:" + path)
        observed_number = _number(observation.get("value"))
        submitted_number = _number(value)
        if (
            observed_number is None
            or submitted_number is None
            or not math.isclose(
                observed_number, submitted_number, rel_tol=1e-12, abs_tol=1e-12,
            )
        ):
            findings.append("cash_accessibility:context_fact_value_mismatch:" + path)
        if path.endswith(".shares") and observation.get("responsibility_boundary") != context.get(
            "ordinary_share_claim_scope"
        ):
            findings.append("cash_accessibility:context_fact_responsibility_boundary_mismatch:" + path)

    validate_context_operand(
        "cash_accessibility.valuation_context.shares",
        context.get("shares"),
        "million_shares",
        required=True,
    )
    same_currency = cash_input.get("currency") == context.get("valuation_currency")
    if not same_currency:
        validate_context_operand(
            "cash_accessibility.valuation_context.fx_source_per_valuation_currency",
            context.get("fx_source_per_valuation_currency"),
            "ratio",
            required=True,
        )


def _working_capital_api() -> tuple[Any, Any]:
    from scripts.working_capital_model import (  # imported only when that optional model is used
        compute_working_capital_model,
        validate_working_capital_model,
    )

    return validate_working_capital_model, compute_working_capital_model


def _canonical_epv_cross_check(result: dict[str, Any]) -> dict[str, Any]:
    """Project the deterministic EPV owner into replacement's comparison shape."""
    if result.get("status") != "COMPARABLE":
        return {
            "status": "NOT_COMPARABLE",
            "reason": str(
                _mapping(result.get("economic_conclusion")).get("reason")
                or "The canonical EPV owner has unresolved material operands."
            ),
            "synthesis_rule": "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE",
        }
    basis = _mapping(result.get("basis"))
    equity = _mapping(result.get("ordinary_common_equity_range"))
    per_share = _mapping(result.get("per_share_range"))
    bridge = _mapping(result.get("equity_bridge"))
    model_id = str(result.get("model_id") or "")
    calc_prefix = "CALC:" + model_id + ":"
    return {
        "status": "COMPARABLE",
        "model_id": model_id,
        "economic_entity": basis["economic_entity"],
        "operating_perimeter": basis["operating_perimeter"],
        "ordinary_share_claim_scope": basis["ordinary_share_claim_scope"],
        "value_scope": "ordinary_common_equity",
        "currency": basis["currency"],
        "unit": basis["unit"],
        "as_of": basis["as_of"],
        "equity_value_low": equity["range_low"],
        "equity_value_high": equity["range_high"],
        "shares_outstanding": bridge["shares"],
        "per_share_low": per_share["range_low"],
        "per_share_high": per_share["range_high"],
        "synthesis_rule": "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE",
        "source_fact_ids": [
            calc_prefix + "EQUITY:LOW",
            calc_prefix + "EQUITY:HIGH",
            calc_prefix + "PER-SHARE:LOW",
            calc_prefix + "PER-SHARE:HIGH",
        ],
    }


def _effective_replacement_input(
    payload: dict[str, Any], epv_result: dict[str, Any] | None,
) -> dict[str, Any]:
    wrapper = _mapping(payload.get("replacement_value"))
    model_input = deepcopy(_mapping(wrapper.get("model_input")))
    epv_model_id = str(wrapper.get("epv_model_id") or "")
    if epv_model_id and epv_result is not None:
        model_input["epv_cross_check"] = _canonical_epv_cross_check(epv_result)
    return model_input


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
        if (
            isinstance(wrapper.get("model_input"), dict)
            and cash_validation.get("state") == "VALID"
        ):
            _validate_cash_value_bridge_canonical_bindings(
                value,
                wrapper=wrapper,
                context=context,
                findings=findings,
            )

    epv_result_for_replacement: dict[str, Any] | None = None
    if "epv" in value:
        wrapper = _mapping(value.get("epv"))
        _unknown_fields(wrapper, _MODEL_WRAPPER_FIELDS, "epv", findings)
        model_input = wrapper.get("model_input")
        if not isinstance(model_input, dict):
            findings.append("epv:model_input_missing")
        else:
            epv_validation = validate_epv_model_input(model_input)
            if epv_validation.get("state") != "VALID":
                findings.extend(_model_findings("epv:model_input", epv_validation))
            else:
                epv_result_for_replacement = compute_epv_model(model_input)

    if "replacement_value" in value:
        wrapper = _mapping(value.get("replacement_value"))
        _unknown_fields(
            wrapper, _REPLACEMENT_WRAPPER_FIELDS, "replacement_value", findings
        )
        model_input = wrapper.get("model_input")
        if not isinstance(model_input, dict):
            findings.append("replacement_value:model_input_missing")
        else:
            epv_model_id = str(wrapper.get("epv_model_id") or "")
            submitted_epv = model_input.get("epv_cross_check")
            if epv_model_id:
                if submitted_epv is not None:
                    findings.append(
                        "replacement_value:hand_filled_epv_cross_check_forbidden"
                    )
                epv_input = _mapping(_mapping(value.get("epv")).get("model_input"))
                if not epv_input:
                    findings.append("replacement_value:canonical_epv_model_missing")
                elif epv_input.get("model_id") != epv_model_id:
                    findings.append("replacement_value:canonical_epv_model_id_mismatch")
                effective = _effective_replacement_input(
                    value, epv_result_for_replacement
                )
            else:
                effective = model_input
                if _mapping(submitted_epv).get("status") == "COMPARABLE":
                    findings.append(
                        "replacement_value:comparable_epv_requires_canonical_model"
                    )
            replacement_validation = validate_replacement_value_model(effective)
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
    legal = result["legal_cash_accessibility"]
    existing = result["existing_excess_cash_realization"]
    receivable = result["related_party_receivable_realization"]
    future = result["future_retained_cash_realization"]

    def component_projection(component: dict[str, Any]) -> dict[str, Any]:
        amount_range = component["amount_range"]
        conditional_amount_range = component.get("conditional_amount_range")
        return {
            "amount_range_source_currency": deepcopy(amount_range),
            "adopted_amount_source_currency": component["adopted_value"],
            "evidenced_lower_bound_source_currency": component[
                "evidenced_lower_bound"
            ],
            "conditional_amount_range_source_currency": deepcopy(
                conditional_amount_range
            ),
            "unrecognized_remainder_source_currency": component[
                "unrecognized_remainder"
            ],
            "per_share_range": {
                key: _cash_per_share(amount_range[key], fx=fx, shares=shares)
                for key in ("low", "base", "high")
            },
            "adopted_per_share": _cash_per_share(
                component["adopted_value"], fx=fx, shares=shares
            ),
            "evidenced_lower_bound_per_share": _cash_per_share(
                component["evidenced_lower_bound"], fx=fx, shares=shares
            ),
            "conditional_per_share_range": (
                None
                if conditional_amount_range is None
                else {
                    key: _cash_per_share(
                        conditional_amount_range[key], fx=fx, shares=shares
                    )
                    for key in ("low", "base", "high")
                }
            ),
            "unrecognized_remainder_per_share": _cash_per_share(
                component["unrecognized_remainder"], fx=fx, shares=shares
            ),
            "evidence_state": deepcopy(component["evidence_state"]),
            "valuation_destination": component["valuation_destination"],
        }

    existing_projection = component_projection(existing)
    receivable_projection = component_projection(receivable)
    legal_projection = {
        "evidenced_additive_leaf_total_source_currency": legal[
            "additive_leaf_total"
        ],
        "diagnostic_unrecognized_ceiling_source_currency": legal[
            "diagnostic_total_ceiling"
        ],
        "conditional_upper_bound_source_currency": legal["amount_range"]["high"],
        "adopted_amount_source_currency": legal["adopted_value"],
        "evidenced_additive_leaf_total_per_share": _cash_per_share(
            legal["additive_leaf_total"], fx=fx, shares=shares
        ),
        "diagnostic_unrecognized_ceiling_per_share": _cash_per_share(
            legal["diagnostic_total_ceiling"], fx=fx, shares=shares
        ),
        "conditional_upper_bound_per_share": _cash_per_share(
            legal["amount_range"]["high"], fx=fx, shares=shares
        ),
        "adopted_per_share": _cash_per_share(
            legal["adopted_value"], fx=fx, shares=shares
        ),
    }
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
        "legal_cash_accessibility": legal_projection,
        "existing_excess_cash": existing_projection,
        "related_party_receivables": receivable_projection,
        "future_retained_cash": {
            "realization_rate_range": deepcopy(future["realization_rate_range"]),
            "adopted_realization_rate": future["adopted_realization_rate"],
            "evidenced_lower_bound_source_currency": future[
                "evidenced_lower_bound"
            ],
            "conditional_amount_range_source_currency": deepcopy(
                future["conditional_amount_range"]
            ),
            "unrecognized_remainder_source_currency": future[
                "unrecognized_remainder"
            ],
            "evidence_state": deepcopy(future["evidence_state"]),
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
        f"每股{valuation_currency}{_fmt(existing_projection['evidenced_lower_bound_per_share'])}"
    )
    existing_range = (
        f"每股{valuation_currency}{_fmt(existing_projection['per_share_range']['low'])}–"
        f"{_fmt(existing_projection['per_share_range']['high'])}"
    )
    receivable_selected = (
        f"每股{valuation_currency}{_fmt(receivable_projection['evidenced_lower_bound_per_share'])}"
    )
    receivable_range = (
        f"每股{valuation_currency}{_fmt(receivable_projection['per_share_range']['low'])}–"
        f"{_fmt(receivable_projection['per_share_range']['high'])}"
    )
    future_rate_range = future.get("realization_rate_range")
    if isinstance(future_rate_range, dict):
        future_conditional = future["conditional_amount_range"]
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
            "；未来留存现金已证实现率下限为"
            + future_selected
            + "（范围"
            + future_range
            + "），对应已证下限为"
            + _reader_amount(
                str(result["currency"]),
                str(result["unit"]),
                future["evidenced_lower_bound"],
            )
            + "（条件范围"
            + _reader_amount(
                str(result["currency"]),
                str(result["unit"]),
                future_conditional["low"],
            )
            + "–"
            + _reader_amount(
                str(result["currency"]),
                str(result["unit"]),
                future_conditional["high"],
            )
            + "），未认可余量为"
            + _reader_amount(
                str(result["currency"]),
                str(result["unit"]),
                future["unrecognized_remainder"],
            )
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
        future_phrase = (
            "；未来留存现金不预设实现率，已证下限为"
            + _reader_amount(
                str(result["currency"]),
                str(result["unit"]),
                future["evidenced_lower_bound"],
            )
            + "，未形成条件区间，未认可余量为"
            + _reader_amount(
                str(result["currency"]),
                str(result["unit"]),
                future["unrecognized_remainder"],
            )
        )
    if existing.get("realization_rate_range") is None:
        existing_phrase = (
            "存量超额现金已证下限为"
            + existing_selected
            + "，未形成条件区间，未认可余量为每股"
            + valuation_currency
            + _fmt(existing_projection["unrecognized_remainder_per_share"])
        )
    else:
        existing_phrase = (
            "按可重复回流记录，存量超额现金已证下限为"
            + existing_selected
            + "（条件范围"
            + existing_range
            + "），未认可余量为每股"
            + valuation_currency
            + _fmt(existing_projection["unrecognized_remainder_per_share"])
        )
    legal_phrase = ""
    if legal_projection["diagnostic_unrecognized_ceiling_per_share"] > 0:
        legal_phrase = (
            "普通股现金已证可达金额为每股"
            + valuation_currency
            + _fmt(legal_projection["adopted_per_share"])
            + "；合并诊断条件上限为每股"
            + valuation_currency
            + _fmt(
                legal_projection[
                    "diagnostic_unrecognized_ceiling_per_share"
                ]
            )
            + "，仍未认可；"
        )
    if receivable.get("recovery_status") in {"EVIDENCE_BACKED", "PARTIAL_EVIDENCE"}:
        receivable_phrase = (
            "关联方应收按已收款和同机制成熟批次形成已证下限"
            + receivable_selected
            + "（条件范围"
            + receivable_range
            + "），未认可余量为每股"
            + valuation_currency
            + _fmt(receivable_projection["unrecognized_remainder_per_share"])
        )
    else:
        receivable_phrase = (
            "关联方应收已证下限仅为已收回金额（当前为"
            + receivable_selected
            + "），未形成条件区间，未认可余量为每股"
            + valuation_currency
            + _fmt(receivable_projection["unrecognized_remainder_per_share"])
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
            "existing_unrecognized_remainder": _fmt(
                existing_projection["unrecognized_remainder_per_share"]
            ),
            "receivable_selected": receivable_selected,
            "receivable_range": receivable_range,
            "receivable_unrecognized_remainder": _fmt(
                receivable_projection["unrecognized_remainder_per_share"]
            ),
            "future_realization_selected": future_selected,
            "future_realization_range": future_range,
            "future_evidenced_lower_bound": _fmt(
                future["evidenced_lower_bound"]
            ),
            "future_unrecognized_remainder": _fmt(
                future["unrecognized_remainder"]
            ),
        },
        "sentence": (
            legal_phrase
            + existing_phrase
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


def _epv_projection(
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    basis = _mapping(result.get("basis"))
    projection = {
        "source_model_id": result["model_id"],
        "company_id": result["company_id"],
        "status": result["status"],
        "basis": deepcopy(basis),
        "sustainable_owner_earnings_range": deepcopy(
            result.get("sustainable_owner_earnings_range")
        ),
        "operating_value_range": deepcopy(result.get("operating_value_range")),
        "ordinary_common_equity_range": deepcopy(
            result.get("ordinary_common_equity_range")
        ),
        "per_share_range": deepcopy(result.get("per_share_range")),
        "critical_unknowns": deepcopy(result.get("critical_unknowns") or []),
        "economic_conclusion": deepcopy(result.get("economic_conclusion")),
    }
    claims: list[dict[str, Any]] = []
    per_share = result.get("per_share_range")
    if isinstance(per_share, dict):
        claims.append({
            "claim_id": "epv.ordinary_common_equity_per_share",
            "source_model_id": result["model_id"],
            "metric": "earnings_power_value_per_share",
            "range_low": per_share["range_low"],
            "range_high": per_share["range_high"],
            "selected_value": None,
            "currency": basis["currency"],
            "unit": "per_share",
            "as_of": basis["as_of"],
            "scope": basis["ordinary_share_claim_scope"],
        })
    return projection, [], claims, []


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
                if reference_actual_charge > 0:
                    consequence = (
                        "这意味着本期利润的可变现性低于报表利润所示；在稳态占用分离前，"
                        "EPV不能作为买入依据。"
                    )
                elif reference_actual_charge < 0:
                    consequence = (
                        "这意味着本期现金流受营运资本释放抬高，不能直接代表可持续盈利；"
                        "在稳态占用分离前，EPV不能作为买入依据。"
                    )
                else:
                    consequence = (
                        "这尚不能证明利润可以稳定转换为现金；在稳态占用分离前，"
                        "EPV不能作为买入依据。"
                    )
                slot_sentence = observed_phrase + "；" + consequence
            else:
                slot_sentence = (
                    observed_phrase
                    + "，但它不能直接被当成可回收资产或永久负担；当前回收路径只计入有证据的实际回收。"
                )
        elif uses_normalized_owner_cash_for_continuing_value:
            slot_sentence = (
                "稳态营运资本需求尚未从项目启动垫资中分离，报表利润能转换成多少可持续现金仍不清楚；"
                "在此之前，EPV不能作为买入依据。"
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

    epv_result: dict[str, Any] | None = None
    if "epv" in payload:
        epv_result = compute_epv_model(payload["epv"]["model_input"])
        projection, conclusions, numeric_claims, slots = _epv_projection(epv_result)
        results["epv"] = epv_result
        projections["epv"] = projection
        reader.extend(conclusions)
        claims.extend(numeric_claims)
        reader_slots.extend(slots)

    if "replacement_value" in payload:
        wrapper = payload["replacement_value"]
        result = compute_replacement_value_model(
            _effective_replacement_input(payload, epv_result)
        )
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
