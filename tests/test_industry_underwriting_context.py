from __future__ import annotations

import json
from pathlib import Path

import scripts.industry_underwriting_context as context
from scripts.industry_underwriting_context import (
    compile_industry_underwriting_context,
    validate_industry_underwriting_context,
)


ROOT = Path(__file__).resolve().parents[1]
CEMENT_BLOCK = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/04_industry_learning_block.json"
CEMENT_ARENA = ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"
EXPRESS_BLOCK = ROOT / "docs/development/research/industry_learning_blocks/CN_FRANCHISE_EXPRESS_2018_2019/01_industry_learning_block.json"
SCHEMA = ROOT / "schemas/industry_underwriting_context_v1.schema.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_cement_block_compiles_peers_near_misses_epochs_and_evidence() -> None:
    payload = compile_industry_underwriting_context(
        company={
            "company_id": "CN:600585",
            "company_name": "Anhui Conch Cement",
            "cutoff_at": "2018-04-30T23:59:59+08:00",
        },
        industry_learning_blocks=[CEMENT_BLOCK],
        competitive_arena=_read(CEMENT_ARENA),
    )

    assert validate_industry_underwriting_context(payload)["state"] == "REVIEWABLE"
    assert payload["report_use"]["non_blocking"] is True
    assert len(payload["structural_epochs"]) == 6
    assert payload["company_archetype_exposure"]["archetype"] == "ARCHETYPE:CONSOLIDATED_OPERATING_AND_CASH_TRACK"
    assert {item["company_id"] for item in payload["representative_peers"]} == {"CN:600425", "CN:600802"}
    assert {item["company_id"] for item in payload["near_misses"]} == {"CN:600801", "CN:000401"}
    assert all("boundary" in item["near_miss_reason"].lower() for item in payload["near_misses"])
    assert payload["candidate_main_paths"]
    assert payload["company_verification_fields"]
    assert payload["evidence_refs"]


def test_v2_express_block_yields_value_chain_drivers_and_company_exposure() -> None:
    payload = compile_industry_underwriting_context(
        company={
            "company_id": "CN:002120",
            "company_name": "Yunda Holding",
            "cutoff_at": "2019-05-01T00:00:00+08:00",
        },
        industry_learning_blocks=[EXPRESS_BLOCK],
    )

    stages = payload["industry_value_chain"]["stages"]
    assert len(stages) == 4
    assert any("franchise" in item["mechanism"].lower() for item in stages)
    assert payload["industry_value_chain"]["customer_jobs"]
    assert payload["industry_drivers"]["demand"]
    assert payload["industry_drivers"]["supply"]
    assert payload["industry_drivers"]["competition"]
    assert payload["strongest_counter_thesis"]["statement"].startswith("National parcel demand")
    assert payload["company_archetype_exposure"]["responsibility_boundary"] == "ISSUER_CONSOLIDATED_WITH_HUB_CONTROL_AND_FRANCHISE_EDGE"
    assert {item["company_id"] for item in payload["representative_peers"]} == {"CN:002468", "CN:600233"}


def test_company_arena_preserves_all_representative_peers_without_a_small_panel_cap() -> None:
    members = [{
        "member_id": "CN:TARGET",
        "company_name": "Target",
        "role": "TARGET",
        "actor_side": "ISSUER",
        "interface": "customer interface",
    }]
    members.extend({
        "member_id": f"CN:PEER:{index}",
        "company_name": f"Peer {index}",
        "role": "EQUILIBRIUM_RESPONSE_WITNESS",
        "actor_side": "ISSUER",
        "interface": "same customer task",
        "source_ids": [f"SRC:PEER:{index}"],
    } for index in range(1, 7))
    arena = {
        "schema_version": "enterprise-judgment-v3.v1",
        "competitive_arenas": [{
            "arena_id": "ARENA:SYNTHETIC:NATIONAL",
            "product_or_service_scope": "National service",
            "customer_task": "Complete the same customer job",
            "competition_interface": "Price, reliability, and distribution",
            "economic_state": "Competitive",
            "required_overlap_dimensions": [{
                "dimension": "CUSTOMER_TASK",
                "relation": "REQUIRED_OVERLAP",
                "rationale": "Customers choose among these suppliers.",
                "evidence_refs": ["SRC:TARGET:ARENA"],
            }],
            "members": members,
        }],
    }

    payload = compile_industry_underwriting_context(
        company={
            "company_id": "CN:TARGET",
            "company_name": "Target",
            "cutoff_at": "2026-08-29T00:00:00+08:00",
        },
        competitive_arena=arena,
    )

    assert len(payload["representative_peers"]) == 6
    assert [item["company_id"] for item in payload["representative_peers"]] == [f"CN:PEER:{index}" for index in range(1, 7)]


def test_compiler_reuses_existing_industry_knowledge_read_api(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_read(company, **kwargs):
        calls.append({"company": company, **kwargs})
        return {
            "schema_version": "industry-knowledge-context.v1",
            "profile": {
                "mechanisms": [{
                    "mechanism_id": "IKM:channel-cost-offset",
                    "mechanism_key": "margin_channel_cost_offset",
                    "title": "Channel cost offset",
                    "status": "MECHANISM_READY",
                    "summary": "Channel costs can offset a gross-margin improvement.",
                    "applicability_conditions": ["Channel fulfilment is material"],
                    "non_applicability_conditions": ["No channel cost exposure"],
                    "alternative_explanations": ["Accounting reclassification"],
                    "company_verification_fields": ["gross margin", "channel fulfilment cost"],
                }],
                "corroborated_mechanisms": [],
                "required_company_verification_fields": ["gross margin", "channel fulfilment cost"],
            },
            "warnings": [],
        }

    monkeypatch.setattr(context, "read_industry_knowledge_context", fake_read)
    payload = compile_industry_underwriting_context(
        company={
            "company_id": "CN:TEST",
            "company_name": "Test Company",
            "cutoff_at": "2026-08-29T00:00:00+08:00",
            "industry_keys": ["consumer_bottling"],
        },
    )

    assert len(calls) == 1
    assert calls[0]["industry_keys"] == ["consumer_bottling"]
    assert any(item["evidence_ref"] == "IKM:channel-cost-offset" for item in payload["evidence_refs"])
    assert {item["field"] for item in payload["company_verification_fields"]} >= {"gross margin", "channel fulfilment cost"}
    assert any("Channel costs" in item["mechanism"] for item in payload["industry_value_chain"]["stages"])


def test_pit_mode_does_not_open_the_current_global_mechanism_library(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("current knowledge API must not be opened for PIT without admitted context")

    monkeypatch.setattr(context, "read_industry_knowledge_context", forbidden)
    payload = compile_industry_underwriting_context(
        company={
            "company_id": "CN:PIT",
            "company_name": "Historical Company",
            "cutoff_at": "2018-04-30T00:00:00+08:00",
            "pit_mode": True,
            "industry_keys": ["consumer_bottling"],
        },
    )

    assert payload["context_status"] == "BOUNDED"
    assert "current_industry_knowledge_not_loaded_in_pit_mode" in payload["warnings"]
    assert payload["candidate_main_paths"]
    assert validate_industry_underwriting_context(payload)["state"] == "REVIEWABLE"


def test_future_block_is_excluded_and_sparse_context_still_compiles() -> None:
    future_block = {
        "schema_version": "industry-learning-block.v2",
        "source_object_ref": "INLINE:FUTURE_BLOCK",
        "block_id": "ILB:FUTURE",
        "industry_id": "INDUSTRY:FUTURE",
        "cutoff_at": "2030-01-01T00:00:00+08:00",
        "industry_epoch": {"epoch_id": "EPOCH:FUTURE", "condition": "Future result"},
        "mechanism_arenas": [{"arena_id": "ARENA:FUTURE", "mechanism": "Future mechanism"}],
    }
    payload = compile_industry_underwriting_context(
        company={
            "company_id": "CN:SPARSE",
            "company_name": "Sparse Company",
            "cutoff_at": "2026-08-29T00:00:00+08:00",
        },
        industry_learning_blocks=[future_block],
    )

    assert payload["context_status"] == "BOUNDED"
    assert payload["structural_epochs"] == []
    assert payload["industry_value_chain"]["stages"] == []
    assert payload["candidate_main_paths"][0]["status"] == "CANDIDATE_TO_VERIFY"
    assert payload["knowledge_time"]["excluded_future_source_refs"] == ["INLINE:FUTURE_BLOCK"]
    assert validate_industry_underwriting_context(payload)["state"] == "REVIEWABLE"


def test_schema_declares_the_stable_handoff_surface_and_default_filename() -> None:
    schema = _read(SCHEMA)
    required = set(schema["required"])
    assert {
        "industry_value_chain", "structural_epochs", "industry_drivers", "profit_pool_outlook",
        "company_archetype_exposure", "representative_peers", "near_misses",
        "candidate_main_paths", "strongest_counter_thesis", "company_verification_fields",
        "evidence_refs", "knowledge_time",
    } <= required
    assert schema["properties"]["context_status"]["enum"] == ["READY", "BOUNDED"]
    assert context.DEFAULT_OUTPUT_NAME == "industry_underwriting_context.json"
