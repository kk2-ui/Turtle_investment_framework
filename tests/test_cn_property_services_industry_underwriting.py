from __future__ import annotations

import json
from pathlib import Path

from scripts.industry_underwriting_context import (
    compile_industry_underwriting_context,
    validate_industry_underwriting_context,
)
from scripts.industry_underwriting_utility_review import (
    validate_industry_underwriting_utility_review,
)


ROOT = Path(__file__).resolve().parents[1]
BLOCK_PATH = (
    ROOT
    / "docs/development/research/industry_learning_blocks"
    / "CN_PROPERTY_SERVICES_2025/01_industry_learning_block.json"
)
UTILITY_REVIEW_PATH = BLOCK_PATH.with_name("07_utility_review.json")


def _read_block() -> dict:
    return json.loads(BLOCK_PATH.read_text(encoding="utf-8"))


def _compile() -> dict:
    return compile_industry_underwriting_context(
        company={
            "company_id": "HK:02669",
            "company_name": "China Overseas Property Holdings",
            "cutoff_at": "2026-08-13T23:59:59+08:00",
            "knowledge_cutoff_at": "2026-08-13T23:59:59+08:00",
            "industry_horizon": "FIVE_YEARS",
            "industry_profit_pool_thesis": (
                "Property-service profit pools are migrating from incremental new-development "
                "feeders toward mature stock operations and conditional public-service and "
                "smart-engineering adjacencies."
            ),
        },
        industry_learning_blocks=[BLOCK_PATH],
        industry_knowledge_context={
            "schema_version": "industry-knowledge-context.v1",
            "source_object_ref": "INLINE:NO_ADDITIONAL_MECHANISM_CARDS",
            "profile": {},
            "warnings": [],
        },
    )


def test_real_property_services_block_compiles_into_a_usable_zhonghai_context() -> None:
    payload = _compile()

    assert validate_industry_underwriting_context(payload)["state"] == "REVIEWABLE"
    assert payload["context_status"] == "READY"
    assert payload["report_use"]["non_blocking"] is True
    assert payload["company_identity"]["company_id"] == "HK:02669"
    assert payload["knowledge_time"]["excluded_future_source_refs"] == []


def test_context_separates_residential_public_service_and_smart_engineering_economics() -> None:
    payload = _compile()
    stages = {item["arena_id"]: item for item in payload["industry_value_chain"]["stages"]}

    residential = stages["ARENA:CN:PROPERTY_SERVICES:MATURE_RESIDENTIAL"]
    public = stages["ARENA:CN:PROPERTY_SERVICES:PUBLIC_INSTITUTIONAL"]
    smart = stages["ARENA:CN:PROPERTY_SERVICES:SMART_ENGINEERING"]

    assert "recurring service earnings" in residential["mechanism"]
    assert "collection rate" in residential["value_driver"]
    assert public["profit_pool_direction"] == "CONDITIONAL_GROWTH_WITH_WORKING_CAPITAL_AND_RENEWAL_RISK"
    assert "delayed public payment" in public["failure_mode"]
    assert smart["profit_pool_direction"] == "OPTIONALITY_SUBJECT_TO_ACCEPTANCE_AND_CASH_CONVERSION"
    assert "contract assets" in smart["failure_mode"]
    assert payload["profit_pool_outlook"]["direction"] == (
        "MIGRATING_FROM_NEW_BUILD_FEEDER_TO_STOCK_OPERATIONS_AND_CONDITIONAL_ADJACENCIES"
    )


def test_mechanism_peers_and_near_miss_are_not_a_fixed_revenue_peer_panel() -> None:
    block = _read_block()
    payload = _compile()

    expected_peers = {
        member["company_id"]
        for member in block["members"]
        if member["company_id"] != "HK:02669" and "MISMATCH" not in member.get("boundary_status", "")
    }
    assert {item["company_id"] for item in payload["representative_peers"]} == expected_peers
    assert all(item["comparison_role"].startswith("MECHANISM_PEER_") for item in payload["representative_peers"])
    assert any(item["company_id"] == "HK:01209" for item in payload["near_misses"])
    assert "NO_FIXED_COUNT" in block["peer_selection_policy"]["peer_count_rule"]
    assert "REVENUE_SIMILARITY_ONLY" in block["peer_selection_policy"]["prohibited_selection_basis"]


def test_target_unknown_economics_are_localized_to_verification_fields() -> None:
    block = _read_block()
    payload = _compile()
    target = next(member for member in block["members"] if member["company_id"] == "HK:02669")
    fields = {item["field"] for item in payload["company_verification_fields"]}

    assert "does not establish" in target["cutoff_state"]
    assert any("public and institutional projects" in field for field in fields)
    assert any("smart-engineering contract assets" in field for field in fields)
    assert "TARGET_PROJECT_ROIC_AS_FACT" in block["prohibited_outputs"]
    assert payload["candidate_main_paths"]
    assert payload["strongest_counter_thesis"]["statement"].startswith(
        "Zhonghai's public-service and smart-engineering revenue growth"
    )


def test_every_compiled_block_evidence_reference_resolves_to_an_official_source() -> None:
    block = _read_block()
    registered = {item["evidence_ref"]: item["url"] for item in block["source_register"]}
    compiled = _compile()

    assert registered
    assert all(url.startswith("https://") for url in registered.values())
    assert set(item["evidence_ref"] for item in compiled["evidence_refs"]) <= set(registered)


def test_worked_ab_changes_investment_treatment_instead_of_only_adding_prose() -> None:
    review = json.loads(UTILITY_REVIEW_PATH.read_text(encoding="utf-8"))

    assert validate_industry_underwriting_utility_review(review)["valid"]
    assert review["utility_verdict"] == "MATERIAL_UTILITY"
    assert set(review["material_treatment_change_dimensions"]) >= {
        "INDUSTRY_FUTURE_PATH",
        "TARGET_EXPOSURE",
        "PERMANENT_LOSS_PATH",
        "VALUATION_ROUTE_AND_REQUIRED_EVIDENCE",
    }
    assert review["narrowed_range_dimensions"] == ["OWNER_CASH_TREATMENT"]
    assert review["explanation_only_dimensions"] == []
