from __future__ import annotations

import sqlite3

import pytest

from scripts import judgment_cjo_valuation as valuation
from scripts import judgment_decision_utility as utility
from scripts import judgment_pit_forecast as pit
from scripts import judgment_pit_forecast_control_plane as forecast_control
from scripts import judgment_v5_control_plane as v5_control
from scripts import judgment_training_cjo_mirror as mirror
from tests.test_judgment_cjo_valuation import _cjo, _settlement, _snapshot
from tests.test_judgment_decision_utility import _episodes, _evaluation, _pairing
from tests.test_judgment_pit_forecast import _forecast, _universe_and_h1
from tests.test_judgment_training_cjo_mirror import _enterprise_bundle, _mirror
from tests.test_judgment_training_decision_contract import _contract


def test_top_level_synthetic_path_preserves_one_way_permissions() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    forecast_control.initialize(conn)
    universe, h1 = _universe_and_h1()
    v5_control.initialize(conn)
    assert v5_control.register_h1_static_cohort_receipt(conn, {
        "receipt_id": "H1:SYNTHETIC:FORECAST:V1",
        "receipt_version": 1,
        "recorded_at": "2021-01-01T00:00:00+00:00",
        "stage0_static_package": h1,
    })["registered"]
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    contract = _contract(bootstrap)
    forecast_control.register_training_decision_contract(conn, contract, frozen_at="2021-01-01T00:00:00+00:00")
    forecast = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:TOP-LEVEL:V2",
        decision_contract_ref={"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
    )
    forecast_control.register_company_state_forecast(
        conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-02T00:00:00+00:00",
    )
    shadow = {
        "schema_version": pit.SHADOW_SCHEMA_VERSION_V2, "shadow_episode_id": "SHADOW:TOP-LEVEL:V2",
        "forecast_epoch_id": pit.FORECAST_EPOCH_ID_V2, "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"], "cutoff_at": forecast["cutoff_at"], "forecast_id": forecast["forecast_id"],
        "outcome_windows": list(pit.FORECAST_WINDOWS), "custodian_id": "SYNTHETIC:CUSTODIAN",
        "status": "WAITING_EXTERNAL_OUTCOME", "object_class": "PROSPECTIVE_SHADOW_EPISODE",
        "claim_class": "PREQUENTIAL_EVALUATION", "allowed_outputs": ["FORECAST_EVALUATION_ONLY"],
        "decision_contract_ref": {"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
    }
    assert forecast_control.register_prospective_shadow_episode(
        conn, shadow, registered_at="2026-08-25T00:00:00+08:00",
    )["registered"]
    assert conn.execute(f"SELECT COUNT(*) FROM {forecast_control.SETTLEMENT_TABLE}").fetchone()[0] == 0

    teaching_bundle = _enterprise_bundle(forecast)
    teaching_mirror = _mirror(contract, forecast, teaching_bundle)
    teaching = mirror.validate_training_cjo_mirror(
        teaching_mirror, contract=contract, forecast=forecast, enterprise_bundle=teaching_bundle,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert teaching["valid"], teaching["findings"]
    assert teaching["cjo_mirror"]["overlay_boundary"]["status"] == "NOT_AUTHORIZED"
    with pytest.raises(ValueError, match="valuation_snapshot_invalid"):
        valuation.compile_valuation_return_snapshot(_snapshot(_cjo()), cjo=teaching_bundle["cjo"])

    investment_cjo = _cjo()
    valuation_snapshot = _snapshot(investment_cjo)
    valuation_result = valuation.validate_valuation_return_settlement(
        _settlement(valuation_snapshot), snapshot=valuation_snapshot, cjo=investment_cjo,
    )
    assert valuation_result["valid"], valuation_result["findings"]
    assert valuation_result["learning_authorization"] == "CANDIDATE_ONLY"

    baseline_episode, enhanced_episode = _episodes(contract)
    utility_pairing = _pairing(contract, baseline_episode, enhanced_episode)
    utility_result = utility.validate_decision_utility_evaluation(
        _evaluation(utility_pairing, contract), pairing=utility_pairing, contract=contract,
        baseline_episode=baseline_episode, enhanced_episode=enhanced_episode,
    )
    assert utility_result["valid"], utility_result["findings"]
    assert utility_result["learning_authorization"] == "CANDIDATE_ONLY"
    conn.close()
