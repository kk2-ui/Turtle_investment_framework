from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from scripts import enterprise_judgment_core as core
from scripts import enterprise_judgment_episode as episode
from scripts import enterprise_judgment_forecast_projection as forecast_projection
from scripts import enterprise_judgment_mechanism as mechanism
from scripts import enterprise_judgment_reconstruction as reconstruction
from scripts import enterprise_judgment_source_packet as source_packet
from scripts import judgment_training_decision_contract as decision_contract


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
PACKAGE_PATH = BLOCK_DIR / "23_round4_preoutcome_mechanism_package.json"
ROSTER_PATH = BLOCK_DIR / "04_pre_outcome_roster_freeze.json"
BLOCK_PATH = BLOCK_DIR / "04_industry_learning_block.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compile_chain() -> tuple[dict, dict, dict, dict, dict]:
    package = _load(PACKAGE_PATH)
    receipt = package["source_packet_receipt"]
    projected_source = source_packet.compile_core_source_package(receipt)
    assert projected_source["valid"], projected_source["findings"]
    core_source_package = projected_source["source_package"]

    contract = package["decision_contract"]
    contract_result = decision_contract.validate_training_decision_contract(contract)
    assert contract_result["valid"], contract_result["findings"]

    model = package["enterprise_system_model"]
    model_result = core.validate_enterprise_system_model(model, source_package=core_source_package)
    assert model_result["state"] == "VALID", model_result["findings"]
    ledger = package["management_decision_ledger"]
    ledger_result = core.validate_management_decision_ledger(ledger, source_package=core_source_package)
    assert ledger_result["state"] == "VALID", ledger_result["findings"]

    spec = package["reconstruction_spec"]
    compiled_reconstruction = reconstruction.compile_enterprise_reconstruction(
        spec,
        source_packet_receipt=receipt,
        source_package=core_source_package,
        enterprise_model=model,
        decision_ledger=ledger,
        decision_contract=contract,
    )
    assert compiled_reconstruction["valid"], compiled_reconstruction["findings"]
    reconstruction_read_model = compiled_reconstruction["reconstruction"]
    reconstruction_inputs = {
        "spec": spec,
        "source_packet_receipt": receipt,
        "source_package": core_source_package,
        "enterprise_model": model,
        "decision_ledger": ledger,
        "decision_contract": contract,
    }

    manifest = package["episode_manifest"]
    compiled_episode = episode.compile_episode_read_model(
        manifest,
        decision_contract=contract,
        reconstruction_binding={
            "reconstruction": reconstruction_read_model,
            "spec": spec,
            "source_packet_receipt": receipt,
            "source_package": core_source_package,
            "enterprise_model": model,
            "decision_ledger": ledger,
        },
    )
    assert compiled_episode["valid"], compiled_episode["findings"]

    registry = sqlite3.connect(":memory:")
    reconstruction.register_frozen_reconstruction(
        registry,
        reconstruction_read_model,
        reconstruction_inputs,
        frozen_at=datetime(2014, 4, 16, tzinfo=timezone.utc).isoformat(),
    )
    compiled_mechanism = mechanism._compile_mechanism_thread_projection_with_registry(
        package["mechanism_thread_set"],
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )
    assert compiled_mechanism["valid"], compiled_mechanism["findings"]

    compiled_forecast = forecast_projection._compile_forecast_projection_with_registry(
        manifest,
        package["forecast_projection_source"],
        mechanism_thread_set=package["mechanism_thread_set"],
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )
    assert compiled_forecast["valid"], compiled_forecast["findings"]
    return (
        package,
        reconstruction_read_model,
        compiled_episode["episode_read_model"],
        compiled_mechanism["mechanism_thread_read_model"],
        compiled_forecast["forecast_projection"],
    )


def test_round4_selection_is_mechanical_and_outcome_blind() -> None:
    package = _load(PACKAGE_PATH)
    roster_freeze = _load(ROSTER_PATH)
    block = _load(BLOCK_PATH)
    selection = package["selection"]
    completed = set(selection["completed_company_ids"])
    first_unseen = next(
        row for row in block["company_cutoff_transition_roster"]
        if row["company_id"] not in completed
    )

    assert selection["selected_rank"] == 17
    assert selection["transition_id"] == "CCR:600802:20140416:20150415"
    assert first_unseen["rank"] == selection["selected_rank"]
    assert first_unseen["transition_id"] == selection["transition_id"]
    assert roster_freeze["company_cutoff_transition_ids"][selection["selected_rank"] - 1] == selection["transition_id"]
    assert selection["selection_used_outcome"] is False
    assert selection["selection_used_lifecycle_label"] is False
    assert selection["selection_used_source_convenience"] is False
    assert package["sealed_outcome_source"] == {
        "source_id": "CNINFO:600802:ANN:20150324:1200733162",
        "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
        "outcome_content_read": False,
    }


def test_round4_real_preoutcome_package_compiles_through_j0_j1_j2_and_j3() -> None:
    package, reconstruction_read_model, episode_read_model, mechanism_read_model, forecast = _compile_chain()

    decision = reconstruction_read_model["management_decision_ledger_slice"]["decisions"][0]
    assert decision["status"] == "PLANNED"
    assert decision["field_statuses"]["RESOURCE_COMMITMENT"] == "UNKNOWN"
    assert decision["field_statuses"]["EXECUTION"] == "UNKNOWN"
    assert episode_read_model["eligible_admission_levels"]["E2_MECHANISM_PROBE"] is True

    views = {view["thread_id"]: view for view in mechanism_read_model["thread_views"]}
    assert set(views) == {
        "THREAD:600802:CHANNEL_VOLUME",
        "THREAD:600802:UNIT_ECONOMICS",
        "THREAD:600802:CASH_CAPITAL_LOSS",
    }
    assert all(view["resolution_status"] == "RESOLVED" for view in views.values())
    assert all(view["j3_forecast_eligible"] for view in views.values())
    assert all(not view["e3_comparative_requested"] for view in views.values())
    assert all(not view["j4_comparative_eligible"] for view in views.values())

    requests = {request["request_id"]: request for request in forecast["forecast_requests"]}
    assert set(requests) == {
        "REQ:600802:SALES_VOLUME:ONE_YEAR",
        "REQ:600802:UNIT_ECONOMICS:ONE_YEAR",
        "REQ:600802:CASH:ONE_YEAR",
        "REQ:600802:PERMANENT_LOSS:ABSTAIN",
    }
    assert requests["REQ:600802:CASH:ONE_YEAR"]["response_contract"]["engine_adapter_state"] == "REQUEST_ONLY"
    assert requests["REQ:600802:PERMANENT_LOSS:ABSTAIN"]["response_contract"]["request_kind"] == "ABSTAIN"
    assert forecast["cell_rejections"] == []
    assert set(forecast["rights"].values()) == {"NOT_AUTHORIZED"}
    assert package["rights"]["enterprise_learning"] == "NOT_YET_CANDIDATE"


def test_round4_contracts_keep_feedback_layers_local_and_prohibit_attribution_shortcuts() -> None:
    package = _load(PACKAGE_PATH)
    contracts = package["cell_measurement_contracts"]
    layers = {contract["layer"] for contract in contracts}
    assert layers == {
        "PLAN",
        "IMPLEMENTED",
        "EXECUTED",
        "CUSTOMER_RESPONSE",
        "UNIT_ECONOMICS",
        "CASH",
        "CAPITAL_RETURN",
        "PERMANENT_LOSS",
    }
    assert len({contract["cell_id"] for contract in contracts}) == len(contracts)
    assert len({contract["measurement_contract_id"] for contract in contracts}) == len(contracts)
    assert all(contract["prohibited_inference"] for contract in contracts)
    assert package["rights"] == {
        "comparative": "NOT_AUTHORIZED",
        "cjo": "NOT_AUTHORIZED",
        "valuation": "NOT_AUTHORIZED",
        "report": "NOT_AUTHORIZED",
        "investment": "NOT_AUTHORIZED",
        "enterprise_learning": "NOT_YET_CANDIDATE",
    }
