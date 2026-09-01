from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_episode as episode
from tests.test_judgment_pit_forecast import _forecast, _universe_and_h1
from tests.test_judgment_training_cjo_mirror import _enterprise_bundle
from tests.test_judgment_training_decision_contract import _contract


def _bound_inputs() -> tuple[dict, dict, dict]:
    universe, h1 = _universe_and_h1()
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    contract = _contract(bootstrap)
    forecast = _forecast(
        universe,
        h1,
        bootstrap["company_id"],
        forecast_id="FORECAST:SYNTHETIC:EPISODE:J0",
        decision_contract_ref={"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
    )
    return contract, forecast, _enterprise_bundle(forecast)


def _scope(issuer_id: str, **overrides: list[str]) -> dict:
    scope = {
        "issuer_ids": [issuer_id],
        "product_or_service_ids": [],
        "plant_ids": [],
        "channel_ids": [],
        "region_ids": [],
        "arena_ids": ["ARENA:SYNTHETIC:OPERATING"],
    }
    scope.update(overrides)
    return scope


def _locator_ids() -> list[str]:
    return ["LOCATOR:SYNTHETIC:OPERATING", "LOCATOR:SYNTHETIC:CASH"]


def _manifest(contract: dict, forecast: dict, bundle: dict) -> dict:
    model = bundle["enterprise_system_model"]
    ledger = bundle["management_decision_ledger"]
    return {
        "schema_version": episode.SCHEMA_VERSION,
        "episode_id": "EJE:SYNTHETIC:J0:V1",
        "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"],
        "cutoff_at": forecast["cutoff_at"],
        "decision_contract_ref": {
            "contract_id": contract["contract_id"], "contract_version": contract["contract_version"],
        },
        "component_refs": [
            {
                "component_type": "ENTERPRISE_CONTEXT_SNAPSHOT",
                "component_id": "CONTEXT:SYNTHETIC:J0",
                "component_version": "1",
                "admission_level": "E0_CONTEXT",
                "read_only": True,
            },
            {
                "component_type": "ENTERPRISE_SYSTEM_MODEL",
                "component_id": model["model_id"],
                "component_version": model["version"],
                "admission_level": "E1_RECONSTRUCTION",
                "read_only": True,
            },
            {
                "component_type": "MANAGEMENT_DECISION_LEDGER",
                "component_id": ledger["ledger_id"],
                "component_version": "1",
                "admission_level": "E1_RECONSTRUCTION",
                "read_only": True,
            },
        ],
        "question_set": [
            {
                "question_id": "Q:OPERATING",
                "role": "PRIMARY",
                "question": "What cutoff-visible operating system can be reconstructed?",
                "claim_ids": ["CLAIM:OPERATING"],
            },
            {
                "question_id": "Q:CASH",
                "role": "SUPPORTING",
                "question": "Which cash conclusion remains limited by its own measurement boundary?",
                "claim_ids": ["CLAIM:CASH"],
            },
            {
                "question_id": "Q:LOSS",
                "role": "SUPPORTING",
                "question": "Which permanent-loss question remains explicitly unknown?",
                "claim_ids": ["CLAIM:LOSS"],
            },
        ],
        "claims": [
            {
                "claim_id": "CLAIM:OPERATING",
                "question_id": "Q:OPERATING",
                "method_id": "METHOD:SYNTHETIC:ENTERPRISE_JUDGMENT:V1",
                "judgment_dimension": "INITIAL_CONDITIONS",
                "claim_scope": _scope(forecast["issuer_id"]),
                "domain": "OPERATIONS",
                "statement": "The issuer's cutoff-visible operating system is directly reconstructed.",
                "cell_status": "OBSERVED",
                "admission_level": "E1_RECONSTRUCTION",
                "evidence_refs": ["H1:SYNTHETIC:OPERATING"],
                "evidence_locator_refs": ["LOCATOR:SYNTHETIC:OPERATING"],
                "dependent_outcome_cell_ids": [],
            },
            {
                "claim_id": "CLAIM:CASH",
                "question_id": "Q:CASH",
                "method_id": "METHOD:SYNTHETIC:ENTERPRISE_JUDGMENT:V1",
                "judgment_dimension": "WORKING_CAPITAL_CASH_CAPITAL",
                "claim_scope": _scope(forecast["issuer_id"]),
                "domain": "CASH",
                "statement": "Cash conversion cannot settle beyond its measurement boundary.",
                "cell_status": "INFERRED",
                "admission_level": "E1_RECONSTRUCTION",
                "evidence_refs": ["H1:SYNTHETIC:CASH"],
                "evidence_locator_refs": ["LOCATOR:SYNTHETIC:CASH"],
                "dependent_outcome_cell_ids": ["CELL:CASH"],
            },
            {
                "claim_id": "CLAIM:LOSS",
                "question_id": "Q:LOSS",
                "method_id": "METHOD:SYNTHETIC:ENTERPRISE_JUDGMENT:V1",
                "judgment_dimension": "ADAPTATION_PERMANENT_LOSS",
                "claim_scope": _scope(forecast["issuer_id"]),
                "domain": "PERMANENT_LOSS",
                "statement": "Permanent-loss exposure remains an unresolved research question.",
                "cell_status": "UNKNOWN",
                "admission_level": "E1_RECONSTRUCTION",
                "evidence_refs": [],
                "evidence_locator_refs": [],
                "dependent_outcome_cell_ids": [],
            },
        ],
        "mechanism_threads": [],
        "outcome_cells": [{
            "outcome_cell_id": "CELL:CASH",
            "dimension": "CASH",
            "status": "MEASUREMENT_MISMATCH",
            "measurement_contract_ref": "MC:SYNTHETIC:CASH",
            "custodian_receipt_ref": "",
        }],
        "roles": {
            "judgment_owner_id": contract["roles"]["judgment_owner_id"],
            "independent_challenger_id": contract["roles"]["independent_challenger_id"],
            "outcome_custodian_id": contract["roles"]["outcome_custodian_id"],
        },
        "object_class": "ENTERPRISE_JUDGMENT_EPISODE_MANIFEST",
        "claim_class": "COMPOSITE_ENTERPRISE_JUDGMENT",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
    }


def _thread(claim_id: str, cell_id: str, role: str) -> dict:
    return {
        "thread_id": "THREAD:" + claim_id,
        "role": role,
        "claim_ids": [claim_id],
        "hypotheses": [
            {"hypothesis_id": "H-A:" + claim_id, "role": "H_A", "statement": "The prewritten mechanism transmits."},
            {"hypothesis_id": "H-B:" + claim_id, "role": "H_B", "statement": "A competing explanation better accounts for the observation."},
        ],
        "observation_clock_ref": "CLOCK:" + claim_id,
        "outcome_cell_ids": [cell_id],
    }


def _canonical_settlement(manifest: dict) -> dict:
    boundary = {
        "responsibility_unit_id": "RU:SYNTHETIC:OPERATING",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "arena_id": "ARENA:SYNTHETIC:OPERATING",
        "scope_requirement": "issuer cash only",
    }
    clock = {
        "clock_kind": "FLOW_PERIOD",
        "flow_period": {
            "period_start": "2021-01-01",
            "period_end": "2021-12-31",
            "fiscal_period": "FY2021",
        },
    }
    receipt = {
        "schema_version": "enterprise-observation-receipt.v1",
        "receipt_id": "OBS:ENTERPRISE:SYNTHETIC:CASH",
        "settlement_id": "SETTLEMENT:ENTERPRISE:SYNTHETIC:CASH",
        "measurement_contract_ref": {
            "measurement_contract_id": "MC:SYNTHETIC:CASH",
            "measurement_contract_version": 3,
        },
        "company_id": manifest["company_id"],
        "cutoff_at": manifest["cutoff_at"],
        "custodian_id": manifest["roles"]["outcome_custodian_id"],
        "authorization_receipt_id": "AUTH:SYNTHETIC:CASH",
        "cell_id": "CELL:CASH",
        "field_id": "FIELD:SYNTHETIC:FY2021:OPERATING_CASH",
        "status": "OBSERVED",
        "raw_value": 120.0,
        "measurement_clock": clock,
        "responsibility_boundary": boundary,
        "unit": "RMB",
        "source": {
            "source_id": "OFFICIAL:SYNTHETIC:FY2021",
            "source_url": "https://example.com/synthetic-fy2021.pdf",
            "pdf_page": 42,
            "field_ref": "PDF p.42",
            "field_identity": "FIELD:SYNTHETIC:FY2021:OPERATING_CASH",
            "custodian_locator": {
                "table_or_note": "consolidated cash-flow statement",
                "line_item": "net cash from operating activities",
                "period_column": "FY2021",
            },
            "measurement_clock": clock,
            "responsibility_boundary": boundary,
            "unit": "RMB",
        },
    }
    return {
        "schema_version": "enterprise-outcome-measurement-settlement.v1",
        "settled": True,
        "settlement_id": receipt["settlement_id"],
        "company_id": manifest["company_id"],
        "cutoff_at": manifest["cutoff_at"],
        "measurement_contract_ref": receipt["measurement_contract_ref"],
        "cell_results": [{
            "cell_id": "CELL:CASH",
            "status": "OBSERVED",
            "label": "OBSERVED_INCREASE",
            "computed_value": 0.2,
            "mismatch_propagation": "LOCAL_ONLY",
        }],
        "raw_observation_receipts": [receipt],
        "observation_receipt_ids": [receipt["receipt_id"]],
    }


def test_j0_manifest_is_read_only_and_localizes_measurement_mismatch() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    before_contract, before_bundle = deepcopy(contract), deepcopy(bundle)

    result = episode.compile_episode_read_model(
        manifest,
        decision_contract=contract,
        enterprise_bundle=bundle,
    )

    assert result["valid"], result["findings"]
    read_model = result["episode_read_model"]
    rows = {row["claim_id"]: row for row in read_model["claim_output_matrix"]}
    assert rows["CLAIM:OPERATING"]["allowed_outputs"] == [
        "STATE_VIEW", "DECISION_VIEW", "CJO_TRAINING_MIRROR", "RESEARCH_AGENDA",
    ]
    assert rows["CLAIM:CASH"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert rows["CLAIM:CASH"]["blocked_by"] == [{"kind": "OUTCOME_CELL", "ref": "CELL:CASH"}]
    assert rows["CLAIM:LOSS"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert read_model["eligible_admission_levels"]["E1_RECONSTRUCTION"] is True
    assert read_model["investment_authorization"] == "NOT_AUTHORIZED"
    assert all("INVESTMENT_VIEW" not in row["allowed_outputs"] for row in rows.values())
    assert contract == before_contract
    assert bundle == before_bundle


def test_j0_requires_hypothesis_pair_only_when_mechanism_probe_is_claimed() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    for claim, question in zip(manifest["claims"], manifest["question_set"], strict=True):
        claim["admission_level"] = "E2_MECHANISM_PROBE"
        claim["cell_status"] = "OBSERVED"
        claim["evidence_refs"] = ["H1:" + claim["claim_id"]]
        claim["evidence_locator_refs"] = ["LOCATOR:" + claim["claim_id"]]
        claim["dependent_outcome_cell_ids"] = ["CELL:CASH"]
        question["claim_ids"] = [claim["claim_id"]]
    manifest["outcome_cells"][0]["status"] = "OBSERVED"
    manifest["outcome_cells"][0]["custodian_receipt_ref"] = "CUSTODY:SYNTHETIC:CASH"
    manifest["mechanism_threads"] = [
        _thread("CLAIM:OPERATING", "CELL:CASH", "PRIMARY"),
        _thread("CLAIM:CASH", "CELL:CASH", "SUPPORTING"),
        _thread("CLAIM:LOSS", "CELL:CASH", "SUPPORTING"),
    ]

    result = episode.compile_episode_read_model(manifest, decision_contract=contract, enterprise_bundle=bundle)
    assert result["valid"], result["findings"]
    assert result["episode_read_model"]["eligible_admission_levels"]["E2_MECHANISM_PROBE"] is True

    malformed = deepcopy(manifest)
    malformed["mechanism_threads"][1]["hypotheses"][1]["role"] = "H_A"
    result = episode.validate_episode_manifest(malformed, decision_contract=contract, enterprise_bundle=bundle)
    assert not result["valid"]
    assert "episode.mechanism_threads[1].hypotheses_must_distinguish_h_a_h_b" in result["findings"]


def test_j0_comparative_claim_requires_its_own_reference_without_global_upgrade() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    manifest["claims"][0]["admission_level"] = "E3_COMPARATIVE_LAB"
    manifest["claims"][0]["dependent_outcome_cell_ids"] = ["CELL:CASH"]
    manifest["outcome_cells"][0].update({"status": "OBSERVED", "custodian_receipt_ref": "CUSTODY:SYNTHETIC:CASH"})
    manifest["mechanism_threads"] = [
        _thread("CLAIM:OPERATING", "CELL:CASH", "PRIMARY"),
        _thread("CLAIM:CASH", "CELL:CASH", "SUPPORTING"),
        _thread("CLAIM:LOSS", "CELL:CASH", "SUPPORTING"),
    ]

    result = episode.validate_episode_manifest(manifest, decision_contract=contract, enterprise_bundle=bundle)
    assert not result["valid"]
    assert "episode.comparative_episode_ref_required_for_e3_or_higher_claim" in result["findings"]

    manifest["component_refs"].append({
        "component_type": "COMPARATIVE_EPISODE",
        "component_id": "V5:SYNTHETIC:REFERENCE",
        "component_version": "1",
        "admission_level": "E3_COMPARATIVE_LAB",
        "read_only": True,
    })
    result = episode.compile_episode_read_model(manifest, decision_contract=contract, enterprise_bundle=bundle)
    assert result["valid"], result["findings"]
    row = next(row for row in result["episode_read_model"]["claim_output_matrix"] if row["claim_id"] == "CLAIM:OPERATING")
    assert row["allowed_outputs"] == ["COMPARATIVE_VIEW", "COMPARATIVE_CANDIDATE", "RESEARCH_AGENDA"]
    assert result["episode_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"


def test_j0_transfer_claim_can_use_forecast_path_without_forcing_comparative_lab() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    manifest["claims"][0]["admission_level"] = "E4_TRANSFER_AND_UTILITY"
    manifest["component_refs"].append({
        "component_type": "FORECAST_BUNDLE",
        "component_id": forecast["forecast_id"],
        "component_version": "2",
        "admission_level": "E4_TRANSFER_AND_UTILITY",
        "read_only": True,
    })

    result = episode.compile_episode_read_model(manifest, decision_contract=contract, enterprise_bundle=bundle)
    assert result["valid"], result["findings"]
    row = next(row for row in result["episode_read_model"]["claim_output_matrix"] if row["claim_id"] == "CLAIM:OPERATING")
    assert row["allowed_outputs"] == ["TRANSFER_CANDIDATE", "DECISION_UTILITY_EVALUATION", "RESEARCH_AGENDA"]
    assert result["episode_read_model"]["eligible_admission_levels"]["E3_COMPARATIVE_LAB"] is False
    assert result["episode_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"


def test_j0_schema_is_closed_and_manifest_rejects_outcome_or_price_payloads() -> None:
    schema = json.loads(Path("schemas/enterprise_judgment_episode_manifest.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["allowed_outputs"]["const"] == episode.ALLOWED_OUTPUTS
    assert {
        "method_id", "judgment_dimension", "claim_scope", "evidence_locator_refs",
    } <= set(schema["$defs"]["claim"]["required"])
    assert schema["$defs"]["claim_scope"]["additionalProperties"] is False

    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    contaminated = deepcopy(manifest)
    contaminated["claims"][0]["outcome_value"] = 99
    result = episode.validate_episode_manifest(contaminated, decision_contract=contract, enterprise_bundle=bundle)
    assert not result["valid"]
    assert "episode.claims[0]_contains_unapproved_field:outcome_value" in result["findings"]
    assert "episode.forbidden_outcome_price_valuation_or_investment_field:episode.claims[0].outcome_value" in result["findings"]


def test_non_cement_claim_scope_supports_product_plant_channel_region_and_arena() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    manifest["claims"][0]["claim_scope"] = _scope(
        forecast["issuer_id"],
        product_or_service_ids=["PRODUCT:HOME_APPLIANCE:COMPRESSOR"],
        plant_ids=["PLANT:CN:HEFEI:01"],
        channel_ids=["CHANNEL:OEM:DIRECT"],
        region_ids=["REGION:CN:EAST"],
    )

    result = episode.compile_episode_read_model(
        manifest,
        decision_contract=contract,
        enterprise_bundle=bundle,
        evidence_locator_ids=_locator_ids(),
    )

    assert result["valid"], result["findings"]
    row = result["episode_read_model"]["claim_output_matrix"][0]
    assert row["claim_scope"]["product_or_service_ids"] == ["PRODUCT:HOME_APPLIANCE:COMPRESSOR"]
    assert row["claim_scope"]["plant_ids"] == ["PLANT:CN:HEFEI:01"]
    assert row["claim_scope"]["channel_ids"] == ["CHANNEL:OEM:DIRECT"]
    assert row["claim_scope"]["region_ids"] == ["REGION:CN:EAST"]
    assert row["claim_scope"]["arena_ids"] == ["ARENA:SYNTHETIC:OPERATING"]
    assert "CEMENT" not in json.dumps(row)


def test_claim_rejects_unknown_evidence_locator() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    manifest["claims"][0]["evidence_locator_refs"] = ["LOCATOR:NOT:REGISTERED"]

    result = episode.validate_episode_manifest(
        manifest,
        decision_contract=contract,
        enterprise_bundle=bundle,
        evidence_locator_ids=_locator_ids(),
    )

    assert not result["valid"]
    assert "episode.claims[0].evidence_locator_ref_unknown:LOCATOR:NOT:REGISTERED" in result["findings"]


def test_claim_and_canonical_settlement_cells_must_close() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    malformed_manifest = deepcopy(manifest)
    malformed_manifest["claims"][1]["dependent_outcome_cell_ids"] = ["CELL:NOT:DECLARED"]

    result = episode.validate_episode_manifest(
        malformed_manifest,
        decision_contract=contract,
        enterprise_bundle=bundle,
        evidence_locator_ids=_locator_ids(),
    )
    assert not result["valid"]
    assert "episode.claims[1].dependent_outcome_cell_ids_unknown" in result["findings"]

    settlement = _canonical_settlement(manifest)
    settlement["raw_observation_receipts"] = []
    settlement["observation_receipt_ids"] = []
    result = episode.compile_claim_evidence_trace(
        manifest,
        canonical_settlement=settlement,
        decision_contract=contract,
        enterprise_bundle=bundle,
        evidence_locator_ids=_locator_ids(),
    )
    assert not result["valid"]
    assert "episode_trace.dependent_cell_has_no_raw_observation_receipt:CELL:CASH" in result["findings"]

    settlement = _canonical_settlement(manifest)
    settlement["raw_observation_receipts"][0]["settlement_id"] = "SETTLEMENT:OTHER"
    result = episode.compile_claim_evidence_trace(
        manifest,
        canonical_settlement=settlement,
        decision_contract=contract,
        enterprise_bundle=bundle,
        evidence_locator_ids=_locator_ids(),
    )
    assert not result["valid"]
    assert (
        "episode_trace.canonical_settlement.raw_observation_receipts[0].settlement_id_must_match_canonical_settlement"
        in result["findings"]
    )


def test_read_only_trace_projects_claim_to_canonical_receipt_and_source_locator() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    settlement = _canonical_settlement(manifest)
    before_manifest, before_settlement = deepcopy(manifest), deepcopy(settlement)

    result = episode.compile_episode_read_model(
        manifest,
        decision_contract=contract,
        enterprise_bundle=bundle,
        evidence_locator_ids=_locator_ids(),
        canonical_settlement=settlement,
    )

    assert result["valid"], result["findings"]
    read_model = result["episode_read_model"]
    rows = {row["claim_id"]: row for row in read_model["claim_output_matrix"]}
    assert rows["CLAIM:CASH"]["allowed_outputs"] == [
        "STATE_VIEW", "DECISION_VIEW", "CJO_TRAINING_MIRROR", "RESEARCH_AGENDA",
    ]
    traces = {row["claim_id"]: row for row in read_model["claim_evidence_trace"]}
    cash_cell = traces["CLAIM:CASH"]["cells"][0]
    assert cash_cell["status"] == "OBSERVED"
    raw = cash_cell["raw_observations"][0]
    assert raw["raw_observation_receipt_id"] == "OBS:ENTERPRISE:SYNTHETIC:CASH"
    assert raw["source_locator"]["field_ref"] == "PDF p.42"
    assert raw["source_locator"]["custodian_locator"]["line_item"] == "net cash from operating activities"
    assert "raw_value" not in raw
    assert read_model["canonical_settlement_ref"] == "SETTLEMENT:ENTERPRISE:SYNTHETIC:CASH"
    assert manifest == before_manifest
    assert settlement == before_settlement


def test_legacy_v1_manifest_remains_read_only_without_typed_claim_upgrade() -> None:
    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    manifest["schema_version"] = episode.LEGACY_SCHEMA_VERSION
    for claim in manifest["claims"]:
        for field in ("method_id", "judgment_dimension", "claim_scope", "evidence_locator_refs"):
            claim.pop(field)

    result = episode.compile_episode_read_model(
        manifest,
        decision_contract=contract,
        enterprise_bundle=bundle,
    )

    assert result["valid"], result["findings"]
    rows = {row["claim_id"]: row for row in result["episode_read_model"]["claim_output_matrix"]}
    assert rows["CLAIM:CASH"]["blocked_by"] == [{"kind": "OUTCOME_CELL", "ref": "CELL:CASH"}]
    assert rows["CLAIM:CASH"]["method_id"] is None
    assert result["episode_read_model"]["schema_version"] == episode.LEGACY_SCHEMA_VERSION
