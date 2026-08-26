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
                "domain": "OPERATIONS",
                "statement": "The issuer's cutoff-visible operating system is directly reconstructed.",
                "cell_status": "OBSERVED",
                "admission_level": "E1_RECONSTRUCTION",
                "evidence_refs": ["H1:SYNTHETIC:OPERATING"],
                "dependent_outcome_cell_ids": [],
            },
            {
                "claim_id": "CLAIM:CASH",
                "question_id": "Q:CASH",
                "domain": "CASH",
                "statement": "Cash conversion cannot settle beyond its measurement boundary.",
                "cell_status": "INFERRED",
                "admission_level": "E1_RECONSTRUCTION",
                "evidence_refs": ["H1:SYNTHETIC:CASH"],
                "dependent_outcome_cell_ids": ["CELL:CASH"],
            },
            {
                "claim_id": "CLAIM:LOSS",
                "question_id": "Q:LOSS",
                "domain": "PERMANENT_LOSS",
                "statement": "Permanent-loss exposure remains an unresolved research question.",
                "cell_status": "UNKNOWN",
                "admission_level": "E1_RECONSTRUCTION",
                "evidence_refs": [],
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

    contract, forecast, bundle = _bound_inputs()
    manifest = _manifest(contract, forecast, bundle)
    contaminated = deepcopy(manifest)
    contaminated["claims"][0]["outcome_value"] = 99
    result = episode.validate_episode_manifest(contaminated, decision_contract=contract, enterprise_bundle=bundle)
    assert not result["valid"]
    assert "episode.claims[0]_contains_unapproved_field:outcome_value" in result["findings"]
    assert "episode.forbidden_outcome_price_valuation_or_investment_field:episode.claims[0].outcome_value" in result["findings"]
