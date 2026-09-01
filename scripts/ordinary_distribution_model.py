#!/usr/bin/env python3
"""Deterministic ordinary-share distribution model.

The model owns the calculation from normalized ordinary-share operating
earnings to the cash distribution left after variable tax/collection
friction and fixed collection cost.  Callers provide economic inputs and
their accepted fact references; they cannot provide the calculated result.
Reader rounding and unit conversion belong to the downstream value-bridge
compiler, not to this model or to a report writer.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import math
from typing import Any


INPUT_SCHEMA = "ordinary-distribution-input.v1"
MODEL_SCHEMA = "ordinary-distribution-model.v1"
INPUT_VALIDATION_SCHEMA = "ordinary-distribution-input-validation.v1"
MODEL_VALIDATION_SCHEMA = "ordinary-distribution-model-validation.v1"

_INPUT_FIELDS = {
    "schema_version",
    "model_id",
    "company_id",
    "cutoff_at",
    "position_as_of",
    "currency",
    "unit",
    "verified_facts",
    "input_fact_ids",
    "normalized_ordinary_share_operating_earnings",
    "ordinary_distribution_rate",
    "distribution_tax_and_collection_friction_rate",
    "fixed_collection_cost",
}
_OUTPUT_FIELDS = {
    "schema_version",
    "model_id",
    "company_id",
    "cutoff_at",
    "position_as_of",
    "as_of",
    "currency",
    "unit",
    "input_fact_ids",
    "normalized_ordinary_share_operating_earnings",
    "ordinary_distribution_rate",
    "gross_common_distribution",
    "distribution_tax_and_collection_friction_rate",
    "variable_tax_and_collection_friction",
    "fixed_collection_cost",
    "after_tax_common_distribution",
    "economic_identity",
    "valuation_destination",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _validation(schema: str, findings: list[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(findings))
    return {
        "schema_version": schema,
        "state": "VALID" if not unique else "INVALID",
        "findings": unique,
    }


def validate_ordinary_distribution_input(payload: Any) -> dict[str, Any]:
    value = _mapping(payload)
    findings: list[str] = []
    if not isinstance(payload, dict):
        findings.append("input_not_object")
    findings.extend(
        "$:unknown_field:" + field for field in sorted(set(value) - _INPUT_FIELDS)
    )
    if value.get("schema_version") != INPUT_SCHEMA:
        findings.append("schema_version_invalid")
    for field in (
        "model_id", "company_id", "cutoff_at", "position_as_of", "currency", "unit",
    ):
        if not _text(value.get(field)):
            findings.append(field + "_missing")
    try:
        cutoff_at = date.fromisoformat(str(value.get("cutoff_at") or ""))
        position_as_of = date.fromisoformat(str(value.get("position_as_of") or ""))
        if position_as_of > cutoff_at:
            findings.append("position_as_of_after_evidence_cutoff")
    except ValueError:
        findings.append("position_as_of_or_cutoff_at_invalid")

    verified_ids: set[str] = set()
    facts = value.get("verified_facts")
    if not isinstance(facts, list) or not facts:
        findings.append("verified_facts_missing")
    else:
        for index, raw in enumerate(facts):
            fact = _mapping(raw)
            if set(fact) != {"fact_id", "status"}:
                findings.append(f"verified_facts[{index}].fields_invalid")
            fact_id = fact.get("fact_id")
            if not _text(fact_id) or fact_id in verified_ids:
                findings.append(f"verified_facts[{index}].fact_id_missing_or_duplicate")
            else:
                verified_ids.add(str(fact_id))
            if fact.get("status") != "VERIFIED":
                findings.append(f"verified_facts[{index}].status_not_verified")
    refs = value.get("input_fact_ids")
    if not isinstance(refs, list) or not refs or any(not _text(item) for item in refs):
        findings.append("input_fact_ids_invalid")
    else:
        if len(set(refs)) != len(refs):
            findings.append("input_fact_ids_duplicate")
        findings.extend(
            "input_fact_ids_not_verified:" + str(ref)
            for ref in refs if ref not in verified_ids
        )

    earnings = _number(value.get("normalized_ordinary_share_operating_earnings"))
    distribution_rate = _number(value.get("ordinary_distribution_rate"))
    friction_rate = _number(
        value.get("distribution_tax_and_collection_friction_rate")
    )
    fixed_cost = _number(value.get("fixed_collection_cost"))
    if earnings is None or earnings < 0:
        findings.append("normalized_ordinary_share_operating_earnings_invalid")
    if distribution_rate is None or not 0 <= distribution_rate <= 1:
        findings.append("ordinary_distribution_rate_invalid")
    if friction_rate is None or not 0 <= friction_rate <= 1:
        findings.append("distribution_tax_and_collection_friction_rate_invalid")
    if fixed_cost is None or fixed_cost < 0:
        findings.append("fixed_collection_cost_invalid")
    if all(item is not None for item in (earnings, distribution_rate, friction_rate, fixed_cost)):
        available_after_variable_friction = (
            float(earnings) * float(distribution_rate) * (1 - float(friction_rate))
        )
        if float(fixed_cost) > available_after_variable_friction:
            findings.append("fixed_collection_cost_exceeds_distribution_after_variable_friction")
    return _validation(INPUT_VALIDATION_SCHEMA, findings)


def _compute_unchecked(value: dict[str, Any]) -> dict[str, Any]:
    earnings = float(value["normalized_ordinary_share_operating_earnings"])
    distribution_rate = float(value["ordinary_distribution_rate"])
    friction_rate = float(value["distribution_tax_and_collection_friction_rate"])
    fixed_cost = float(value["fixed_collection_cost"])
    gross = earnings * distribution_rate
    variable_friction = gross * friction_rate
    after_tax = gross * (1 - friction_rate) - fixed_cost
    return {
        "schema_version": MODEL_SCHEMA,
        "model_id": value["model_id"],
        "company_id": value["company_id"],
        "cutoff_at": value["cutoff_at"],
        "position_as_of": value["position_as_of"],
        "as_of": value["position_as_of"],
        "currency": value["currency"],
        "unit": value["unit"],
        "input_fact_ids": deepcopy(value["input_fact_ids"]),
        "normalized_ordinary_share_operating_earnings": earnings,
        "ordinary_distribution_rate": distribution_rate,
        "gross_common_distribution": gross,
        "distribution_tax_and_collection_friction_rate": friction_rate,
        "variable_tax_and_collection_friction": variable_friction,
        "fixed_collection_cost": fixed_cost,
        "after_tax_common_distribution": after_tax,
        "economic_identity": (
            "normalized_earnings_times_distribution_rate_less_tax_and_collection_friction"
        ),
        "valuation_destination": "ordinary_share_distribution_return",
    }


def compute_ordinary_distribution_model(payload: Any) -> dict[str, Any]:
    validation = validate_ordinary_distribution_input(payload)
    if validation["state"] != "VALID":
        raise ValueError(
            "ordinary_distribution_input_invalid:"
            + ",".join(validation["findings"])
        )
    return _compute_unchecked(_mapping(payload))


def validate_ordinary_distribution_model(value: Any) -> dict[str, Any]:
    observed = _mapping(value)
    findings: list[str] = []
    if not isinstance(value, dict):
        findings.append("output_not_object")
    findings.extend(
        "$:unknown_field:" + field for field in sorted(set(observed) - _OUTPUT_FIELDS)
    )
    if observed.get("schema_version") != MODEL_SCHEMA:
        findings.append("schema_version_invalid")
    required = _OUTPUT_FIELDS - {"schema_version"}
    findings.extend(field + "_missing" for field in sorted(required - set(observed)))
    if not findings:
        reconstructed_input = {
            "schema_version": INPUT_SCHEMA,
            "model_id": observed["model_id"],
            "company_id": observed["company_id"],
            "cutoff_at": observed["cutoff_at"],
            "position_as_of": observed["position_as_of"],
            "currency": observed["currency"],
            "unit": observed["unit"],
            "verified_facts": [
                {"fact_id": fact_id, "status": "VERIFIED"}
                for fact_id in observed["input_fact_ids"]
            ],
            "input_fact_ids": deepcopy(observed["input_fact_ids"]),
            "normalized_ordinary_share_operating_earnings": observed[
                "normalized_ordinary_share_operating_earnings"
            ],
            "ordinary_distribution_rate": observed["ordinary_distribution_rate"],
            "distribution_tax_and_collection_friction_rate": observed[
                "distribution_tax_and_collection_friction_rate"
            ],
            "fixed_collection_cost": observed["fixed_collection_cost"],
        }
        input_validation = validate_ordinary_distribution_input(reconstructed_input)
        if input_validation["state"] != "VALID":
            findings.extend(
                "reconstructed_input:" + item
                for item in input_validation["findings"]
            )
        else:
            expected = _compute_unchecked(reconstructed_input)
            if observed != expected:
                findings.append("output_not_deterministic")
    return _validation(MODEL_VALIDATION_SCHEMA, findings)


__all__ = [
    "compute_ordinary_distribution_model",
    "validate_ordinary_distribution_input",
    "validate_ordinary_distribution_model",
]
