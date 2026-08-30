from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.ordinary_distribution_model import (
    compute_ordinary_distribution_model,
    validate_ordinary_distribution_input,
    validate_ordinary_distribution_model,
)


ROOT = Path(__file__).resolve().parents[1]


def _input() -> dict:
    fact_ids = ["OBS:EARNINGS", "OBS:DISTRIBUTION", "OBS:FRICTION"]
    return {
        "schema_version": "ordinary-distribution-input.v1",
        "model_id": "DIST:02669:2025",
        "company_id": "02669.HK",
        "cutoff_at": "2026-08-11",
        "position_as_of": "2025-12-31",
        "currency": "RMB",
        "unit": "RMB_m",
        "verified_facts": [
            {"fact_id": fact_id, "status": "VERIFIED"} for fact_id in fact_ids
        ],
        "input_fact_ids": fact_ids,
        "normalized_ordinary_share_operating_earnings": 896.9796304399521,
        "ordinary_distribution_rate": 0.35,
        "distribution_tax_and_collection_friction_rate": 0.1027,
        "fixed_collection_cost": 3.28396046,
    }


def test_computes_after_tax_common_distribution_from_inputs_only() -> None:
    result = compute_ordinary_distribution_model(_input())

    assert result["gross_common_distribution"] == pytest.approx(313.9428706539832)
    assert result["after_tax_common_distribution"] == 278.41697737781914
    assert result["valuation_destination"] == "ordinary_share_distribution_return"
    assert validate_ordinary_distribution_model(result)["state"] == "VALID"


def test_input_rejects_a_copied_result_and_unverified_inputs() -> None:
    payload = _input()
    payload["after_tax_common_distribution"] = 278.41697737781914
    payload["input_fact_ids"].append("OBS:NOT-VERIFIED")

    findings = validate_ordinary_distribution_input(payload)["findings"]

    assert "$:unknown_field:after_tax_common_distribution" in findings
    assert "input_fact_ids_not_verified:OBS:NOT-VERIFIED" in findings


def test_model_validation_recomputes_and_rejects_tampering() -> None:
    result = compute_ordinary_distribution_model(_input())
    changed = deepcopy(result)
    changed["after_tax_common_distribution"] = 375.8

    validation = validate_ordinary_distribution_model(changed)

    assert validation["state"] == "INVALID"
    assert validation["findings"] == ["output_not_deterministic"]


def test_fixed_cost_cannot_make_the_distribution_negative() -> None:
    payload = _input()
    payload["fixed_collection_cost"] = 1_000

    validation = validate_ordinary_distribution_input(payload)

    assert "fixed_collection_cost_exceeds_distribution_after_variable_friction" in (
        validation["findings"]
    )


def test_schema_is_closed() -> None:
    schema = json.loads(
        (ROOT / "schemas/ordinary_distribution_model.schema.json").read_text()
    )
    assert schema["additionalProperties"] is False
    assert "after_tax_common_distribution" in schema["required"]
