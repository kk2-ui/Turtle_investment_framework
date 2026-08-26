from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from scripts import enterprise_judgment_episode as episode
from scripts import enterprise_judgment_reconstruction as reconstruction
from scripts import enterprise_judgment_reconstruction_registry as reconstruction_registry
from scripts import enterprise_judgment_source_packet as source_packet
from scripts import judgment_training_decision_contract as contract_module
from tests.test_enterprise_judgment_core import _ledger, _model, _source_package


def _source_inputs(*, cash_eligibility: str = "ELIGIBLE") -> tuple[dict, dict]:
    core_source = _source_package(cash_eligibility=cash_eligibility)
    receipt = {
        "schema_version": source_packet.SCHEMA_VERSION,
        "packet_id": core_source["source_package_id"],
        "packet_version": 1,
        "company_id": core_source["company_id"],
        "issuer_id": core_source["company_id"],
        "cutoff_at": core_source["cutoff_at"],
        "sources": [{
            "source_id": source["source_ref"],
            "source_type": source["source_type"],
            "official_url": "https://official.example/" + source["source_ref"] + ".pdf",
            "published_on": source["available_at"][:10],
            "available_on": source["available_at"][:10],
            "availability_timezone": "UTC",
            "eligibility": source["eligibility"],
            "responsibility_boundary_ids": list(source["responsibility_boundary_ids"]),
            "responsibility_perimeter_id": "PERIMETER:SYNTHETIC",
            "unit": "RMB",
            "access_mode": "REMOTE_OFFICIAL_LOCATOR",
            "locators": [{"research_question_id": "Q:SYNTHETIC", "locator": source["locator"]}],
            **({"boundary_note": source["boundary_note"]} if "boundary_note" in source else {}),
        } for source in core_source["sources"]],
        "object_class": "SOURCE_PACKET_RECEIPT",
        "claim_class": "CUTOFF_ELIGIBLE_SOURCE_RECEIPT",
        "allowed_outputs": list(source_packet.ALLOWED_OUTPUTS),
    }
    projected = source_packet.compile_core_source_package(receipt)
    assert projected["valid"], projected["findings"]
    return receipt, projected["source_package"]


def _contract(source_package: dict) -> dict:
    return {
        "schema_version": contract_module.SCHEMA_VERSION,
        "contract_id": "DC:SYNTHETIC:J1",
        "contract_version": 1,
        "company_id": source_package["company_id"],
        "issuer_id": source_package["company_id"],
        "cutoff_at": source_package["cutoff_at"],
        "decision_purpose": "HISTORICAL_TRAINING",
        "holding_horizon": {"minimum_years": 1, "maximum_years": 5},
        "permanent_loss_constraints": [{
            "constraint_id": "PLC:J1", "condition": "Operating continuity or access to cash is impaired.",
            "required_treatment": "Keep permanent loss as a conservative research question.",
        }],
        "decision_flip_questions": [{
            "question_id": "DQ:J1", "statement": "Is the cutoff-visible enterprise state viable?",
            "decision_effect": "A negative answer preserves the loss guardrail.",
        }],
        "evidence_budget": {
            "evidence_budget_id": "BUDGET:SYNTHETIC:J1",
            "source_packet_refs": [{"receipt_id": source_package["source_package_id"], "receipt_version": 1}],
        },
        "price_and_opportunity_cost_policy": "PROHIBITED_FOR_HISTORICAL_TRAINING",
        "outcome_access": "NONE",
        "roles": {
            "judgment_owner_id": "OWNER:SYNTHETIC",
            "independent_challenger_id": "CHALLENGER:SYNTHETIC",
            "outcome_custodian_id": "CUSTODIAN:SYNTHETIC",
        },
        "object_class": "DECISION_CONTRACT",
        "claim_class": "EX_ANTE_DECISION_SCOPE",
        "allowed_outputs": list(contract_module.HISTORICAL_ALLOWED_OUTPUTS),
    }


def _spec(source_package: dict, contract: dict | None = None) -> dict:
    decision_contract = contract or _contract(source_package)
    return {
        "schema_version": reconstruction.SPEC_SCHEMA_VERSION,
        "reconstruction_id": "RECON:SYNTHETIC:J1",
        "company_id": source_package["company_id"],
        "issuer_id": source_package["company_id"],
        "cutoff_at": source_package["cutoff_at"],
        "decision_contract_ref": {
            "contract_id": decision_contract["contract_id"], "contract_version": decision_contract["contract_version"],
        },
        "source_packet_ref": {"receipt_id": source_package["source_package_id"], "receipt_version": 1},
        "context_snapshot_id": "CONTEXT:SYNTHETIC:J1",
        "operating_system_model_id": "OSM:SYNTHETIC:J1",
        "decision_ledger_slice_id": "SLICE:SYNTHETIC:J1",
        "feedback_loops": [
            {
                "loop_id": "LOOP:CUSTOMER-ECONOMICS",
                "domains": ["CUSTOMER", "OPERATIONS"],
                "variable_ids": ["VAR:CUSTOMER_RETENTION", "VAR:UNIT_ECONOMICS"],
                "mechanism_ids": ["MECH:CUSTOMER_TO_EARNINGS"],
                "financial_transmission_ids": ["TX:NORMAL_EARNINGS"],
                "decision_ids": ["DEC:RESET"],
                "selection_rationale": "Customer retention is the cutoff-visible first driver of the operating reset.",
                "evidence_refs": ["SRC:OPERATING"],
            },
            {
                "loop_id": "LOOP:ECONOMICS-CASH-LOSS",
                "domains": ["OPERATIONS", "CASH", "PERMANENT_LOSS"],
                "variable_ids": ["VAR:UNIT_ECONOMICS", "VAR:OWNER_CASH", "VAR:LOSS_RISK"],
                "mechanism_ids": ["MECH:EARNINGS_TO_CASH", "MECH:CASH_TO_LOSS"],
                "financial_transmission_ids": ["TX:OWNER_CASH", "TX:PERMANENT_LOSS"],
                "decision_ids": ["DEC:RESET"],
                "selection_rationale": "Cash conversion is the explicit boundary between operational progress and permanent-loss exposure.",
                "evidence_refs": ["SRC:CASH"],
            },
        ],
        "decision_observation": {
            "observation_id": "MDO:SYNTHETIC:J1",
            "status": "MATERIAL_DECISION_OBSERVED",
            "responsibility_unit_ids": ["UNIT:BUSINESS"],
            "arena_ids": ["ARENA:CORE"],
            "reviewed_source_refs": ["SRC:OPERATING"],
            "materiality_scope": "Cutoff-visible operating-system actions in the selected business unit and arena.",
            "rationale": "A ledger-backed operating reset is observable before the cutoff.",
            "next_discriminating_evidence": "Same-boundary management disclosure of execution progress.",
        },
        "decision_ids": ["DEC:RESET"],
        "roles": deepcopy(decision_contract["roles"]),
        "object_class": "ENTERPRISE_JUDGMENT_RECONSTRUCTION_SPEC",
        "claim_class": "CUTOFF_ENTERPRISE_RECONSTRUCTION",
        "allowed_outputs": list(reconstruction.ALLOWED_OUTPUTS),
    }


def _episode_manifest(source_package: dict, contract: dict, component_refs: list[dict]) -> dict:
    return {
        "schema_version": episode.SCHEMA_VERSION,
        "episode_id": "EJE:SYNTHETIC:J1",
        "company_id": source_package["company_id"],
        "issuer_id": source_package["company_id"],
        "cutoff_at": source_package["cutoff_at"],
        "decision_contract_ref": {"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
        "component_refs": component_refs,
        "question_set": [
            {"question_id": "Q:OPERATIONS", "role": "PRIMARY", "question": "What is the operating system?", "claim_ids": ["CLAIM:OPERATIONS"]},
            {"question_id": "Q:CASH", "role": "SUPPORTING", "question": "What constrains cash?", "claim_ids": ["CLAIM:CASH"]},
            {"question_id": "Q:LIFECYCLE", "role": "SUPPORTING", "question": "What lifecycle facts are unknown?", "claim_ids": ["CLAIM:LIFECYCLE"]},
        ],
        "claims": [
            {"claim_id": "CLAIM:OPERATIONS", "question_id": "Q:OPERATIONS", "domain": "OPERATIONS", "statement": "Operating system is reconstructed from cutoff-safe source IDs.", "cell_status": "OBSERVED", "admission_level": "E1_RECONSTRUCTION", "evidence_refs": ["SRC:OPERATING"], "dependent_outcome_cell_ids": []},
            {"claim_id": "CLAIM:CASH", "question_id": "Q:CASH", "domain": "CASH", "statement": "Cash bridge is an explicit reconstruction boundary.", "cell_status": "INFERRED", "admission_level": "E1_RECONSTRUCTION", "evidence_refs": ["SRC:CASH"], "dependent_outcome_cell_ids": []},
            {"claim_id": "CLAIM:LIFECYCLE", "question_id": "Q:LIFECYCLE", "domain": "LIFECYCLE", "statement": "Lifecycle remains a scoped unknown pending its own receipt.", "cell_status": "UNKNOWN", "admission_level": "E1_RECONSTRUCTION", "evidence_refs": [], "dependent_outcome_cell_ids": []},
        ],
        "mechanism_threads": [],
        "outcome_cells": [{"outcome_cell_id": "CELL:CASH", "dimension": "CASH", "status": "UNKNOWN", "measurement_contract_ref": "", "custodian_receipt_ref": ""}],
        "roles": deepcopy(contract["roles"]),
        "object_class": "ENTERPRISE_JUDGMENT_EPISODE_MANIFEST",
        "claim_class": "COMPOSITE_ENTERPRISE_JUDGMENT",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
    }


def test_j1_projects_cutoff_safe_context_operating_loops_and_decision_slice() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    ledger = _ledger()
    after_cutoff = {
        "event_id": "MDE:4", "sequence": 4, "decision_id": "DEC:RESET", "event_type": "STATUS_CHANGED",
        "recorded_at": "2026-01-10T00:00:00+00:00", "effective_at": "2026-01-10T00:00:00+00:00",
        "from_status": "IMPLEMENTED", "to_status": "EXPOSED", "rationale": "must be excluded from the cutoff view", "evidence_refs": ["SRC:CASH"],
    }
    ledger["events"].append(after_cutoff)
    before_model, before_ledger = deepcopy(model), deepcopy(ledger)

    spec = _spec(source_package, decision_contract)
    result = reconstruction.compile_enterprise_reconstruction(
        spec, source_packet_receipt=source_receipt,
        source_package=source_package, enterprise_model=model,
        decision_ledger=ledger, decision_contract=decision_contract,
    )

    assert result["valid"], result["findings"]
    compiled = result["reconstruction"]
    context = compiled["enterprise_context_snapshot"]
    assert context["dimension_coverage"]["LIFECYCLE"] == "UNKNOWN"
    assert context["dimension_coverage"]["CAPITAL_STRUCTURE"] == "UNKNOWN"
    assert len(compiled["operating_system_model"]["feedback_loops"]) == 2
    decision = compiled["management_decision_ledger_slice"]["decisions"][0]
    assert decision["status"] == "IMPLEMENTED"
    assert decision["field_statuses"]["ALTERNATIVES"] == "UNKNOWN"
    assert decision["field_statuses"]["NON_ACTION_OPTION"] == "UNKNOWN"
    assert decision["field_statuses"]["EXECUTION"] == "OBSERVED"
    assert compiled["source_packet_ref"] == spec["source_packet_ref"]
    assert compiled["investment_authorization"] == "NOT_AUTHORIZED"
    assert model == before_model
    assert ledger == before_ledger


def test_j1_components_are_a_valid_e1_input_to_j0_without_retroactive_promotion() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    ledger = _ledger()
    spec = _spec(source_package, decision_contract)
    compiled = reconstruction.compile_enterprise_reconstruction(
        spec, source_packet_receipt=source_receipt, source_package=source_package,
        enterprise_model=model, decision_ledger=ledger,
        decision_contract=decision_contract,
    )
    assert compiled["valid"], compiled["findings"]

    result = episode.compile_episode_read_model(
        _episode_manifest(source_package, decision_contract, compiled["reconstruction"]["episode_component_refs"]),
        decision_contract=decision_contract,
        reconstruction_binding={
            "reconstruction": compiled["reconstruction"], "spec": spec,
            "source_packet_receipt": source_receipt, "source_package": source_package,
            "enterprise_model": model, "decision_ledger": ledger,
        },
    )
    assert result["valid"], result["findings"]
    assert result["episode_read_model"]["eligible_admission_levels"]["E1_RECONSTRUCTION"] is True
    assert result["episode_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"


def test_j1_rejects_uncovered_loop_variables_and_outcome_or_price_payloads() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    spec = _spec(source_package, decision_contract)
    spec["feedback_loops"][0]["variable_ids"].append("VAR:OWNER_CASH")
    result = reconstruction.validate_reconstruction_spec(
        spec, source_packet_receipt=source_receipt, source_package=source_package,
        enterprise_model=_model(source_package=source_package), decision_ledger=_ledger(),
        decision_contract=decision_contract,
    )
    assert not result["valid"]
    assert "reconstruction_spec.feedback_loops[0].variables_must_be_covered_by_selected_mechanisms" in result["findings"]

    contaminated = _spec(source_package, decision_contract)
    contaminated["feedback_loops"][0]["outcome_value"] = 42
    result = reconstruction.validate_reconstruction_spec(
        contaminated, source_packet_receipt=source_receipt, source_package=source_package,
        enterprise_model=_model(source_package=source_package), decision_ledger=_ledger(),
        decision_contract=decision_contract,
    )
    assert not result["valid"]
    assert "reconstruction_spec.feedback_loops[0]_contains_unapproved_field:outcome_value" in result["findings"]
    assert "reconstruction_spec.forbidden_outcome_price_valuation_or_investment_field:reconstruction_spec.feedback_loops[0].outcome_value" in result["findings"]


def test_j1_rejects_cross_boundary_loops_and_localizes_ineligible_evidence() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    cross_boundary = _spec(source_package, decision_contract)
    model["operating_variables"][0]["responsibility_unit_id"] = "UNIT:GROUP"
    result = reconstruction.validate_reconstruction_spec(
        cross_boundary, source_packet_receipt=source_receipt, source_package=source_package,
        enterprise_model=model, decision_ledger=_ledger(),
        decision_contract=decision_contract,
    )
    assert not result["valid"]
    assert "reconstruction_spec.feedback_loops[0].must_remain_within_one_responsibility_boundary_and_arena" in result["findings"]

    ineligible_receipt, ineligible_package = _source_inputs(cash_eligibility="EVIDENCE_INELIGIBLE")
    ineligible_contract = _contract(ineligible_package)
    compiled = reconstruction.compile_enterprise_reconstruction(
        _spec(ineligible_package, ineligible_contract), source_packet_receipt=ineligible_receipt,
        source_package=ineligible_package,
        enterprise_model=_model(source_package=ineligible_package), decision_ledger=_ledger(),
        decision_contract=ineligible_contract,
    )
    assert compiled["valid"], compiled["findings"]
    coverage = compiled["reconstruction"]["evidence_coverage"]
    cash_source = next(entry for entry in coverage["sources"] if entry["source_ref"] == "SRC:CASH")
    assert cash_source["status"] == "EVIDENCE_INELIGIBLE"
    cash_loop = next(entry for entry in coverage["feedback_loops"] if entry["loop_id"] == "LOOP:ECONOMICS-CASH-LOSS")
    assert "TX:OWNER_CASH" in cash_loop["blocked_component_ids"]

    manifest = _episode_manifest(
        ineligible_package, ineligible_contract, compiled["reconstruction"]["episode_component_refs"],
    )
    result = episode.compile_episode_read_model(
        manifest,
        decision_contract=ineligible_contract,
        reconstruction_binding={
            "reconstruction": compiled["reconstruction"], "spec": _spec(ineligible_package, ineligible_contract),
            "source_packet_receipt": ineligible_receipt, "source_package": ineligible_package,
            "enterprise_model": _model(source_package=ineligible_package),
            "decision_ledger": _ledger(),
        },
    )
    assert not result["valid"]
    assert "episode.claims[1].ineligible_evidence_cannot_support_active_claim" in result["findings"]


def test_j1_allows_scoped_no_material_decision_without_promoting_it_to_an_action() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    for mechanism in model["mechanisms"]:
        mechanism["management_decision_ids"] = []
    model["state_changes"][0]["management_decision_ids"] = []
    ledger = _ledger()
    ledger["events"] = []
    spec = _spec(source_package, decision_contract)
    for loop in spec["feedback_loops"]:
        loop["decision_ids"] = []
    spec["decision_ids"] = []
    spec["decision_observation"].update({
        "status": "NO_MATERIAL_DECISION_OBSERVED",
        "rationale": "The reviewed annual-report packet identifies enterprise state but no material selected-unit action.",
    })

    compiled = reconstruction.compile_enterprise_reconstruction(
        spec, source_packet_receipt=source_receipt, source_package=source_package,
        enterprise_model=model, decision_ledger=ledger,
        decision_contract=decision_contract,
    )
    assert compiled["valid"], compiled["findings"]
    decision_slice = compiled["reconstruction"]["management_decision_ledger_slice"]
    assert decision_slice["decisions"] == []
    assert decision_slice["decision_observation"]["status"] == "NO_MATERIAL_DECISION_OBSERVED"

    manifest = _episode_manifest(source_package, decision_contract, compiled["reconstruction"]["episode_component_refs"])
    manifest["claims"][1].update({
        "decision_observation_ref": "MDO:SYNTHETIC:J1",
        "decision_observation_treatment": "ACTION_DEPENDENT",
        "cell_status": "NOT_APPLICABLE",
        "evidence_refs": [],
    })
    result = episode.compile_episode_read_model(
        manifest,
        decision_contract=decision_contract,
        reconstruction_binding={
            "reconstruction": compiled["reconstruction"], "spec": spec,
            "source_packet_receipt": source_receipt, "source_package": source_package,
            "enterprise_model": model, "decision_ledger": ledger,
        },
    )
    assert result["valid"], result["findings"]
    rows = {row["claim_id"]: row for row in result["episode_read_model"]["claim_output_matrix"]}
    assert len(rows["CLAIM:OPERATIONS"]["allowed_outputs"]) > 1
    assert rows["CLAIM:CASH"]["allowed_outputs"] == ["RESEARCH_AGENDA"]


def test_j1_requires_exact_receipt_projection_and_eligible_no_action_observation() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    ledger = _ledger()
    spec = _spec(source_package, decision_contract)
    substituted_package = deepcopy(source_package)
    substituted_package["sources"][0]["locator"] = "a hand-written source package is not receipt provenance"
    result = reconstruction.validate_reconstruction_spec(
        spec, source_packet_receipt=source_receipt, source_package=substituted_package,
        enterprise_model=model, decision_ledger=ledger, decision_contract=decision_contract,
    )
    assert not result["valid"]
    assert "source_package_must_equal_bound_source_packet_receipt_projection" in result["findings"]

    wrong_version = deepcopy(source_receipt)
    wrong_version["packet_version"] = 2
    result = reconstruction.validate_reconstruction_spec(
        spec, source_packet_receipt=wrong_version, source_package=source_package,
        enterprise_model=model, decision_ledger=ledger, decision_contract=decision_contract,
    )
    assert not result["valid"]
    assert "reconstruction_spec.source_packet_ref_must_match_bound_source_packet_receipt" in result["findings"]

    wrong_company = deepcopy(source_receipt)
    wrong_company["company_id"] = "CN:OTHER"
    result = reconstruction.validate_reconstruction_spec(
        spec, source_packet_receipt=wrong_company, source_package=source_package,
        enterprise_model=model, decision_ledger=ledger, decision_contract=decision_contract,
    )
    assert not result["valid"]
    assert "reconstruction_spec.company_id_must_match_bound_source_packet_receipt" in result["findings"]

    ineligible_receipt, ineligible_package = _source_inputs(cash_eligibility="EVIDENCE_INELIGIBLE")
    ineligible_contract = _contract(ineligible_package)
    no_action_model = _model(source_package=ineligible_package)
    for mechanism in no_action_model["mechanisms"]:
        mechanism["management_decision_ids"] = []
    no_action_model["state_changes"][0]["management_decision_ids"] = []
    no_action_ledger = _ledger()
    no_action_ledger["events"] = []
    no_action_spec = _spec(ineligible_package, ineligible_contract)
    for loop in no_action_spec["feedback_loops"]:
        loop["decision_ids"] = []
    no_action_spec["decision_ids"] = []
    no_action_spec["decision_observation"].update({
        "status": "NO_MATERIAL_DECISION_OBSERVED",
        "reviewed_source_refs": ["SRC:CASH"],
        "rationale": "This must not turn ineligible source silence into a no-action conclusion.",
    })
    result = reconstruction.validate_reconstruction_spec(
        no_action_spec, source_packet_receipt=ineligible_receipt, source_package=ineligible_package,
        enterprise_model=no_action_model, decision_ledger=no_action_ledger,
        decision_contract=ineligible_contract,
    )
    assert not result["valid"]
    assert "reconstruction_spec.no_material_decision_observation_requires_eligible_reviewed_sources" in result["findings"]


def test_j1_bound_reconstruction_rejects_custody_or_observation_substitution() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    ledger = _ledger()
    spec = _spec(source_package, decision_contract)
    compiled = reconstruction.compile_enterprise_reconstruction(
        spec, source_packet_receipt=source_receipt, source_package=source_package,
        enterprise_model=model, decision_ledger=ledger,
        decision_contract=decision_contract,
    )
    assert compiled["valid"], compiled["findings"]
    manifest = _episode_manifest(source_package, decision_contract, compiled["reconstruction"]["episode_component_refs"])
    manifest["roles"]["outcome_custodian_id"] = "CUSTODIAN:SUBSTITUTED"
    result = episode.validate_episode_manifest(
        manifest,
        decision_contract=decision_contract,
        reconstruction_binding={
            "reconstruction": compiled["reconstruction"], "spec": spec,
            "source_packet_receipt": source_receipt, "source_package": source_package,
            "enterprise_model": model, "decision_ledger": ledger,
        },
    )
    assert not result["valid"]
    assert "episode.roles_must_match_bound_reconstruction" in result["findings"]

    manifest = _episode_manifest(source_package, decision_contract, compiled["reconstruction"]["episode_component_refs"])
    tampered = deepcopy(compiled["reconstruction"])
    tampered["management_decision_ledger_slice"]["decision_observation"]["status"] = "INSUFFICIENT_EVIDENCE"
    result = episode.validate_episode_manifest(
        manifest,
        decision_contract=decision_contract,
        reconstruction_binding={
            "reconstruction": tampered, "spec": spec,
            "source_packet_receipt": source_receipt, "source_package": source_package,
            "enterprise_model": model, "decision_ledger": ledger,
        },
    )
    assert not result["valid"]
    assert "reconstruction_binding:reconstruction_must_equal_bound_cutoff_safe_compilation" in result["findings"]


def test_j1_schema_is_closed_and_limits_the_operating_system_to_two_or_three_loops() -> None:
    schema = json.loads(Path("schemas/enterprise_judgment_reconstruction.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["feedback_loops"]["maxItems"] == 3
    assert schema["properties"]["allowed_outputs"]["const"] == reconstruction.ALLOWED_OUTPUTS


def test_j1_registry_rejects_a_synchronized_replacement_of_the_frozen_bundle() -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    ledger = _ledger()
    spec = _spec(source_package, decision_contract)
    compiled = reconstruction.compile_enterprise_reconstruction(
        spec,
        source_packet_receipt=source_receipt,
        source_package=source_package,
        enterprise_model=model,
        decision_ledger=ledger,
        decision_contract=decision_contract,
    )
    assert compiled["valid"], compiled["findings"]
    inputs = {
        "spec": spec,
        "source_packet_receipt": source_receipt,
        "source_package": source_package,
        "enterprise_model": model,
        "decision_ledger": ledger,
        "decision_contract": decision_contract,
    }
    registry = sqlite3.connect(":memory:")
    reconstruction.register_frozen_reconstruction(
        registry,
        compiled["reconstruction"],
        inputs,
        frozen_at="2026-08-26T00:00:00+00:00",
    )

    assert reconstruction.validate_frozen_reconstruction_binding(
        registry, compiled["reconstruction"], inputs,
    )["valid"]
    substituted_inputs = deepcopy(inputs)
    substituted_inputs["source_packet_receipt"]["sources"][0]["source_id"] = "SRC:INVENTED"
    result = reconstruction.validate_frozen_reconstruction_binding(
        registry, compiled["reconstruction"], substituted_inputs,
    )

    assert not result["valid"]
    assert result["findings"] == ["reconstruction_inputs_must_match_frozen_registry_object"]


def test_j1_registry_cli_adapter_compiles_and_registers_approved_artifacts(tmp_path: Path) -> None:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    ledger = _ledger()
    spec = _spec(source_package, decision_contract)
    conn = sqlite3.connect(tmp_path / "canonical.db")

    result = reconstruction_registry.register_from_artifacts(
        conn,
        source_packet_receipt=source_receipt,
        decision_contract=decision_contract,
        enterprise_model=model,
        decision_ledger=ledger,
        spec=spec,
        frozen_at="2026-08-26T00:00:00+00:00",
    )
    loaded = reconstruction.load_frozen_reconstruction(
        conn,
        {
            "reconstruction_id": spec["reconstruction_id"],
            "schema_version": reconstruction.SCHEMA_VERSION,
        },
    )
    conn.close()

    assert result["frozen"] is True
    assert loaded["reconstruction"]["source_packet_ref"] == spec["source_packet_ref"]
    assert loaded["reconstruction_inputs"]["decision_contract"] == decision_contract
