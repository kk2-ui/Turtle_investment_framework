"""Regression tests for the five-company appliance J2/J3/J4 read model."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.appliance_industry_j234 import (
    ApplianceJ234Error,
    compile_appliance_j234_read_model,
    validate_appliance_j234,
)


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs/development/research"


def _register() -> dict:
    return json.loads((RESEARCH / "CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json").read_text(encoding="utf-8"))


def _block() -> dict:
    return json.loads((RESEARCH / "CN_APPLIANCE_INDUSTRY_J234_V1.json").read_text(encoding="utf-8"))


def test_j234_compiles_a_five_company_risk_set_without_creating_a_panel() -> None:
    block = _block()
    result = validate_appliance_j234(block, source_register=_register())

    assert result == {
        "valid": True,
        "findings": [],
        "episode_ids": ["J2:CN:000333:C2", "J2:CN:000651:C1", "J2:CN:600690:C2"],
    }
    read_model = compile_appliance_j234_read_model(block, source_register=_register())
    assert {member["company_id"] for member in read_model["industry_universe"]} == {
        "CN:000651", "CN:000333", "CN:600690", "CN:000921", "CN:600839",
    }
    assert all(gate["state"] == "NOT_ADMITTED_MISSING_HOMOGENEOUS_PRODUCT_BOUNDARY" for gate in read_model["j4_gates"])
    assert read_model["investment_authorization"] == "NOT_AUTHORIZED"


def test_j234_rejects_a_three_company_universe_even_when_three_deep_episodes_remain() -> None:
    block = _block()
    block["industry_universe"] = [
        member for member in block["industry_universe"]
        if member["company_id"] not in {"CN:000921", "CN:600839"}
    ]

    result = validate_appliance_j234(block, source_register=_register())

    assert result["valid"] is False
    assert "appliance_j234.industry_universe_requires_at_least_five_companies" in result["findings"]
    assert "appliance_j234.industry_universe_requires_two_contextual_members" in result["findings"]


def test_j234_does_not_promote_contextual_members_or_outcome_content() -> None:
    block = _block()
    core = next(
        member for member in block["industry_universe"]
        if member["company_id"] == "CN:000651" and member["cutoff_id"] == "CN_APPLIANCE_C1_20170430"
    )
    core["universe_role"] = "CONTEXTUAL_RISK_SET"
    core["evidence_state"] = "SOURCE_REGISTERED_CONTEXT_ONLY"
    core["reason"] = "A deep episode cannot be silently demoted after its question has been registered."
    result = validate_appliance_j234(block, source_register=_register())
    assert result["valid"] is False
    assert "appliance_j234.episodes[0].deep_episode_requires_core_system_member" in result["findings"]

    contaminated = _block()
    contaminated["episodes"][0]["cells"][0]["outcome_label"] = "UP"
    result = validate_appliance_j234(contaminated, source_register=_register())
    assert result["valid"] is False
    assert any("forbidden_field" in finding for finding in result["findings"])
    try:
        compile_appliance_j234_read_model(contaminated, source_register=_register())
    except ApplianceJ234Error:
        pass
    else:  # pragma: no cover - makes the permission boundary executable
        raise AssertionError("outcome content must not compile into the J2/J3/J4 read model")
