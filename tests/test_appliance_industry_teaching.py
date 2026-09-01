"""Executable boundary tests for the appliance teaching-only curriculum."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.appliance_industry_teaching import (
    ApplianceTeachingError,
    compile_appliance_teaching_pack,
    validate_appliance_teaching_pack,
)


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs/development/research"


def _json(name: str) -> dict:
    return json.loads((RESEARCH / name).read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict]:
    return (
        _json("CN_APPLIANCE_TEACHING_PACK_V1.json"),
        _json("CN_APPLIANCE_INDUSTRY_J234_V1.json"),
        _json("CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json"),
    )


def test_five_appliance_mechanism_drills_compile_only_to_teaching() -> None:
    pack, block, source_register = _inputs()
    result = validate_appliance_teaching_pack(pack, block=block, source_register=source_register)
    assert result == {
        "valid": True,
        "findings": [],
        "drill_ids": [
            "APPLIANCE:DRILL:CHANGHONG:C2:WHITEGOODS_PORTFOLIO",
            "APPLIANCE:DRILL:GREE:C1:CHANNEL_COMPONENT",
            "APPLIANCE:DRILL:HAIER:C2:SERVICE_LOGISTICS",
            "APPLIANCE:DRILL:HISENSE:C1:PRODUCT_COST_INVENTORY",
            "APPLIANCE:DRILL:MIDEA:C2:CHANNEL_SUPPLY_CHAIN",
        ],
    }
    compiled = compile_appliance_teaching_pack(pack, block=block, source_register=source_register)
    assert compiled["training_state"] == "READY_FOR_TEACHING_ONLY"
    assert compiled["learning_authorization"] == "TEACHING_ONLY"
    assert compiled["result_access"] == "NOT_OPENED"
    assert compiled["evaluation_eligibility"] == "NOT_ELIGIBLE_MODEL_MEMORY_MITIGATED"
    assert {drill["company_id"] for drill in compiled["drills"]} == {
        "CN:000651", "CN:000333", "CN:600690", "CN:000921", "CN:600839",
    }
    assert all(drill["admission"]["allowed_outputs"] == ["TEACHING_ONLY", "RESEARCH_AGENDA"] for drill in compiled["drills"])


def test_teaching_cannot_drop_unknowns_or_promote_a_score() -> None:
    pack, block, source_register = _inputs()
    changed = deepcopy(pack)
    changed["drills"][0]["unknown_cell_ids"] = []
    changed["drills"][0]["outcome_label"] = "UP"
    changed["allowed_outputs"].append("METHOD_SCORE")

    result = validate_appliance_teaching_pack(changed, block=block, source_register=source_register)

    assert result["valid"] is False
    assert "appliance_teaching.allowed_outputs_must_remain_teaching_only" in result["findings"]
    assert "appliance_teaching.drills[0].unknown_cell_ids_must_preserve_episode_unknowns" in result["findings"]
    assert any("forbidden_field" in finding for finding in result["findings"])
    try:
        compile_appliance_teaching_pack(changed, block=block, source_register=source_register)
    except ApplianceTeachingError:
        pass
    else:  # pragma: no cover - makes the non-promotion boundary executable
        raise AssertionError("teaching content cannot compile into an evaluated method artifact")


def test_teaching_must_use_the_original_thread_and_page_bound_facts() -> None:
    pack, block, source_register = _inputs()
    changed = deepcopy(pack)
    changed["drills"][1]["thread_id"] = "T:MIDEA:PERIMETER_CASH"

    result = validate_appliance_teaching_pack(changed, block=block, source_register=source_register)

    assert result["valid"] is False
    assert "appliance_teaching.drills[1].thread_must_be_mechanism_candidate" in result["findings"]
    assert "appliance_teaching.drills[1].fact_cell_ids_must_exactly_match_thread" in result["findings"]
    assert "appliance_teaching.drills[1].source_refs_must_exactly_match_thread" in result["findings"]
