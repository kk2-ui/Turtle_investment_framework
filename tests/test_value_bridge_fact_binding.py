from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.valuation_model_gate import _validate_value_bridge_fact_bindings
from scripts.valuation_value_bridges import compile_valuation_value_bridges


def _ordinary_input() -> dict:
    facts = [
        ("OBS:DIST:EARNINGS", 100.0, "RMB_m"),
        ("OBS:DIST:RATE", 0.4, "ratio"),
        ("OBS:DIST:FRICTION", 0.1, "ratio"),
        ("OBS:DIST:FIXED", 2.0, "RMB_m"),
    ]
    return {
        "schema_version": "valuation-value-bridges-input.v1",
        "canonical_fact_bindings": [
            {"path": "ordinary_distribution.model_input.normalized_ordinary_share_operating_earnings", "evidence_id": facts[0][0]},
            {"path": "ordinary_distribution.model_input.ordinary_distribution_rate", "evidence_id": facts[1][0]},
            {"path": "ordinary_distribution.model_input.distribution_tax_and_collection_friction_rate", "evidence_id": facts[2][0]},
            {"path": "ordinary_distribution.model_input.fixed_collection_cost", "evidence_id": facts[3][0]},
        ],
        "ordinary_distribution": {
            "model_input": {
                "schema_version": "ordinary-distribution-input.v1",
                "model_id": "DIST:FACT-BINDING",
                "company_id": "TEST.HK",
                "cutoff_at": "2026-08-11",
                "position_as_of": "2025-12-31",
                "currency": "RMB",
                "unit": "RMB_m",
                "verified_facts": [
                    {"fact_id": fact_id, "status": "VERIFIED"}
                    for fact_id, _, _ in facts
                ],
                "input_fact_ids": [fact_id for fact_id, _, _ in facts],
                "normalized_ordinary_share_operating_earnings": 100.0,
                "ordinary_distribution_rate": 0.4,
                "distribution_tax_and_collection_friction_rate": 0.1,
                "fixed_collection_cost": 2.0,
            }
        },
    }


def _write_verified_observations(output: Path) -> None:
    rows = [
        ("OBS:DIST:EARNINGS", 100.0, "RMB_m"),
        ("OBS:DIST:RATE", 0.4, "ratio"),
        ("OBS:DIST:FRICTION", 0.1, "ratio"),
        ("OBS:DIST:FIXED", 2.0, "RMB_m"),
    ]
    (output / "fact_observations.json").write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "observation_id": fact_id,
                        "normalized_value": value,
                        "unit": unit,
                        "currency": "RMB" if unit == "RMB_m" else None,
                        "as_of": "2025-12-31",
                        "measurement_context": {},
                        "status": "VERIFIED",
                    }
                    for fact_id, value, unit in rows
                ]
            }
        ),
        encoding="utf-8",
    )


def _validate(output: Path, bridge_input: dict) -> tuple[list[str], list[str]]:
    payload = {"value_bridge_models": compile_valuation_value_bridges(bridge_input)}
    invalid: list[str] = []
    incomplete: list[str] = []
    _validate_value_bridge_fact_bindings(
        payload, output, required=True, invalid=invalid, incomplete=incomplete
    )
    return invalid, incomplete


def test_every_distribution_operand_is_resolved_to_current_verified_observation(
    tmp_path: Path,
) -> None:
    _write_verified_observations(tmp_path)

    invalid, incomplete = _validate(tmp_path, _ordinary_input())

    assert invalid == []
    assert incomplete == []


def test_self_declared_verified_fact_cannot_replace_current_registry_evidence(
    tmp_path: Path,
) -> None:
    _write_verified_observations(tmp_path)
    payload = _ordinary_input()
    fake = "OBS:FAKE:RATE"
    payload["ordinary_distribution"]["model_input"]["verified_facts"][1]["fact_id"] = fake
    payload["ordinary_distribution"]["model_input"]["input_fact_ids"][1] = fake
    payload["canonical_fact_bindings"][1]["evidence_id"] = fake

    invalid, incomplete = _validate(tmp_path, payload)

    assert incomplete == []
    assert any("unknown_or_unverified_evidence:" + fake in item for item in invalid)


def test_altered_operand_cannot_keep_a_real_observation_id(tmp_path: Path) -> None:
    _write_verified_observations(tmp_path)
    payload = _ordinary_input()
    payload["ordinary_distribution"]["model_input"]["fixed_collection_cost"] = 3.0

    invalid, _ = _validate(tmp_path, payload)

    assert any("numeric_value_mismatch:ordinary_distribution.model_input.fixed_collection_cost" in item for item in invalid)


def test_missing_binding_leaves_the_numeric_operand_invalid(tmp_path: Path) -> None:
    _write_verified_observations(tmp_path)
    payload = _ordinary_input()
    payload["canonical_fact_bindings"] = payload["canonical_fact_bindings"][:-1]

    invalid, _ = _validate(tmp_path, payload)

    assert "value_bridge_fact_bindings_operand_unbound:ordinary_distribution.model_input.fixed_collection_cost" in invalid
