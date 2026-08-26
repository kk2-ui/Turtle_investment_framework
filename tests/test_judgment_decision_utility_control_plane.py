from __future__ import annotations

from copy import deepcopy
import sqlite3

import pytest

from scripts import judgment_decision_utility as utility
from scripts import judgment_pit_forecast as pit
from scripts import judgment_pit_forecast_control_plane as control
from scripts import judgment_training_program as training_program
from scripts import judgment_v5_control_plane as v5_control
from tests.test_judgment_pit_forecast import (
    _forecast, _forecast_acquisition_scope, _outcome_measurement_contract, _paired_evaluation,
    _pairing, _preforecast_evidence_receipt, _universe_and_h1, _v3_observation_receipts,
    _v3_observed_settlement, _v6_forecast,
)
from tests.test_judgment_training_decision_contract import _contract


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    control.initialize(conn)
    training_program.initialize(conn)
    v5_control.initialize(conn)
    return conn


def _register_h1(conn: sqlite3.Connection, h1: dict) -> None:
    assert v5_control.register_h1_static_cohort_receipt(conn, {
        "receipt_id": "H1:SYNTHETIC:FORECAST:V1",
        "receipt_version": 1,
        "recorded_at": "2021-01-01T00:00:00+00:00",
        "stage0_static_package": h1,
    })["registered"]


def _utility_pairing(forecast: dict, forecast_pairing: dict, contract: dict) -> dict:
    budget = contract["evidence_budget"]

    def decision(method_id: str, status: str, unknowns: list[str], cost: float) -> dict:
        return {
            "method_id": method_id,
            "decision_status": status,
            "material_unknown_ids": unknowns,
            "evidence_budget_id": budget["evidence_budget_id"],
            "source_packet_refs": deepcopy(budget["source_packet_refs"]),
            "research_cost_hours": cost,
        }

    return {
        "schema_version": utility.CONTROL_PAIRING_SCHEMA_VERSION,
        "pairing_id": f"UTILITY:{forecast['forecast_id']}",
        "forecast_id": forecast["forecast_id"],
        "forecast_pairing_id": forecast_pairing["pairing_id"],
        "decision_contract_ref": deepcopy(forecast["decision_contract_ref"]),
        "baseline": decision(forecast_pairing["baseline_method_id"], "WATCH", ["UNKNOWN:CASH"], 2.0),
        "enhanced": decision(
            forecast_pairing["enhanced_method_id"], "RESEARCH", ["UNKNOWN:CASH", "UNKNOWN:PERMANENT_LOSS"], 3.0,
        ),
        "frozen_at": "2021-01-06T12:00:00+00:00",
        "object_class": "DECISION_UTILITY_PAIRING",
        "claim_class": "SAME_CONTRACT_METHOD_ABLATION",
        "allowed_outputs": list(utility.ALLOWED_OUTPUTS),
    }


def _utility_evaluation(pairing: dict, paired_evaluation: dict) -> dict:
    return {
        "schema_version": utility.CONTROL_EVALUATION_SCHEMA_VERSION,
        "evaluation_id": f"UTILITY:EVALUATION:{pairing['pairing_id']}",
        "pairing_id": pairing["pairing_id"],
        "forecast_paired_evaluation_id": paired_evaluation["evaluation_id"],
        "evaluated_at": "2022-04-03T00:00:00+00:00",
        "reviewer_id": "SYNTHETIC:INDEPENDENT:DECISION-UTILITY:REVIEWER",
        "dimension_findings": [
            {
                "dimension_id": dimension,
                "baseline_assessment": "NO_DIFFERENCE",
                "enhanced_assessment": "MATERIAL_IMPROVEMENT" if dimension != "RESEARCH_COST" else "NO_DIFFERENCE",
                "rationale": "Review preserves qualitative decision support and never releases a method or investment output.",
            }
            for dimension in utility.DIMENSIONS
        ],
        "object_class": "DECISION_UTILITY_EVALUATION",
        "claim_class": "MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": list(utility.ALLOWED_OUTPUTS),
    }


def _v6_chain() -> tuple[sqlite3.Connection, dict, dict, dict, dict]:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:DECISION-UTILITY:BASE",
        decision_contract_ref={"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
    )
    measurement = _outcome_measurement_contract(v2, contract)
    control.register_forecast_outcome_measurement_contract(conn, measurement, frozen_at="2021-01-02T00:00:00+00:00")
    evidence = _preforecast_evidence_receipt(v2, h1)
    control.register_preforecast_evidence_receipt(conn, evidence, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00")
    scope = _forecast_acquisition_scope(v2, measurement)
    control.register_forecast_acquisition_scope(conn, scope, frozen_at="2021-01-04T00:00:00+00:00")
    method_ref = {
        "program_id": "JTP:SYNTHETIC:DECISION-UTILITY",
        "method_version": "METHOD:TRAINING_ENHANCED:V1",
        "method_frozen_at": "2021-01-04T00:00:00+00:00",
        "method_freeze_recorded_at": "2021-01-04T01:00:00+00:00",
    }
    conn.execute(
        """INSERT INTO judgment_training_programs
           (program_id, program_state, method_version, method_scope, registered_at, method_frozen_at,
            method_freeze_recorded_at, sampling_policy_json, contract_ref)
           VALUES (?, 'ACTIVE', ?, 'BOUNDARY_ONLY', ?, ?, ?, '{}', 'synthetic:decision-utility')""",
        (
            method_ref["program_id"], method_ref["method_version"], "2021-01-01T00:00:00+00:00",
            method_ref["method_frozen_at"], method_ref["method_freeze_recorded_at"],
        ),
    )
    forecast = _v6_forecast(v2, measurement, evidence, scope, method_ref=method_ref)
    control.register_company_state_forecast(
        conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-05T00:00:00+00:00",
    )
    conn.execute(
        """INSERT INTO judgment_training_episodes
           (training_episode_id, program_id, case_id, company_id, company_cluster_id, industry_id,
            decision_domain, cutoff_at, outcome_not_before, lane, provenance_role, outcome_access,
            holdout_axis, artifacts_json)
           VALUES (?, ?, 'HOLDOUT:SYNTHETIC:DECISION-UTILITY', ?, 'COMPANY:SYNTHETIC:DECISION-UTILITY',
                   'SYNTHETIC', 'FORECAST', ?, '2022-01-01T00:00:00+00:00', 'HISTORICAL_HOLDOUT',
                   'HISTORICAL_SELF_REPLAY', 'PIT_OUTCOME_SEALED', 'COMPANY_AND_TIME', '{}')""",
        (
            "JTE:SYNTHETIC:DECISION-UTILITY", method_ref["program_id"], forecast["company_id"], forecast["cutoff_at"],
        ),
    )
    conn.commit()
    forecast_pairing = _pairing(forecast)
    forecast_pairing["schema_version"] = pit.PAIRING_SCHEMA_VERSION_V2
    forecast_pairing["holdout_binding"] = {
        "program_id": method_ref["program_id"],
        "holdout_training_episode_id": "JTE:SYNTHETIC:DECISION-UTILITY",
        "evaluated_cell_refs": [{"dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR"}],
    }
    control.register_forecast_method_pairing(conn, forecast_pairing, frozen_at="2021-01-06T00:00:00+00:00")
    return conn, forecast, contract, measurement, forecast_pairing


def _authorize_and_evaluate(conn: sqlite3.Connection, forecast: dict, contract: dict, measurement: dict, forecast_pairing: dict) -> dict:
    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION_V3,
        "authorization_id": f"OUTCOME-ACCESS:{forecast['forecast_id']}",
        "forecast_id": forecast["forecast_id"],
        "company_id": forecast["company_id"],
        "cutoff_at": forecast["cutoff_at"],
        "custodian_id": contract["roles"]["outcome_custodian_id"],
        "authorized_at": "2022-04-01T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "outcome_measurement_contract_ref": deepcopy(forecast["outcome_measurement_contract_ref"]),
        "forecast_acquisition_scope_ref": deepcopy(forecast["forecast_acquisition_scope_ref"]),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION",
        "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    control.authorize_forecast_outcome_access(conn, access)
    for receipt in _v3_observation_receipts(forecast, measurement).values():
        control.register_forecast_outcome_observation_receipt(conn, receipt)
    settlement = _v3_observed_settlement(forecast, measurement)
    control.register_forecast_settlement(conn, settlement)
    paired = _paired_evaluation(forecast, settlement, forecast_pairing)
    control.register_forecast_paired_evaluation(conn, paired)
    return paired


def test_control_pairing_uses_only_frozen_v6_forecast_pairing_before_outcome_access() -> None:
    conn, forecast, contract, measurement, forecast_pairing = _v6_chain()
    pairing = _utility_pairing(forecast, forecast_pairing, contract)
    first = control.register_decision_utility_pairing(conn, pairing, frozen_at=pairing["frozen_at"])
    replay = control.register_decision_utility_pairing(conn, deepcopy(pairing), frozen_at=pairing["frozen_at"])
    assert first == {"frozen": True, "pairing_id": pairing["pairing_id"], "idempotent": False, "learning_authorization": "CANDIDATE_ONLY"}
    assert replay["idempotent"] is True

    wrong_method = deepcopy(pairing)
    wrong_method["pairing_id"] += ":WRONG"
    wrong_method["enhanced"]["method_id"] = "METHOD:UNBOUND"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_pairing(conn, wrong_method, frozen_at=wrong_method["frozen_at"])
    assert exc_info.value.code == "decision_utility_pairing_invalid"

    after_outcome_window = deepcopy(pairing)
    after_outcome_window["pairing_id"] += ":OUTCOME-WINDOW"
    after_outcome_window["frozen_at"] = "2022-01-01T00:00:00+00:00"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_pairing(
            conn, after_outcome_window, frozen_at=after_outcome_window["frozen_at"],
        )
    assert exc_info.value.code == "decision_utility_pairing_must_precede_holdout_outcome_window"

    payload_time_drift = deepcopy(pairing)
    payload_time_drift["pairing_id"] += ":TIME-DRIFT"
    payload_time_drift["frozen_at"] = "2021-01-06T13:00:00+00:00"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_pairing(conn, payload_time_drift, frozen_at=pairing["frozen_at"])
    assert exc_info.value.code == "decision_utility_pairing_frozen_at_must_match_control_timestamp"

    forbidden_output = deepcopy(pairing)
    forbidden_output["pairing_id"] += ":OUTPUT"
    forbidden_output["allowed_outputs"] = ["DECISION_UTILITY_EVALUATION_ONLY", "INVESTMENT_INPUT"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_pairing(conn, forbidden_output, frozen_at=forbidden_output["frozen_at"])
    assert exc_info.value.code == "decision_utility_pairing_invalid"

    _authorize_and_evaluate(conn, forecast, contract, measurement, forecast_pairing)
    late = deepcopy(pairing)
    late["pairing_id"] += ":LATE"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_pairing(conn, late, frozen_at=late["frozen_at"])
    assert exc_info.value.code == "decision_utility_pairing_must_precede_outcome_access_authorization"
    conn.close()


def test_control_evaluation_resolves_registered_paired_outcome_and_stays_candidate_only() -> None:
    conn, forecast, contract, measurement, forecast_pairing = _v6_chain()
    pairing = _utility_pairing(forecast, forecast_pairing, contract)
    control.register_decision_utility_pairing(conn, pairing, frozen_at=pairing["frozen_at"])
    paired = _authorize_and_evaluate(conn, forecast, contract, measurement, forecast_pairing)
    evaluation = _utility_evaluation(pairing, paired)
    first = control.register_decision_utility_evaluation(conn, evaluation)
    replay = control.register_decision_utility_evaluation(conn, deepcopy(evaluation))
    assert first == {"evaluated": True, "evaluation_id": evaluation["evaluation_id"], "idempotent": False, "learning_authorization": "CANDIDATE_ONLY"}
    assert replay["idempotent"] is True

    contaminated = deepcopy(evaluation)
    contaminated["evaluation_id"] += ":OUTCOME-REF"
    contaminated["outcome_settlement_ref"] = "SETTLEMENT:CALLER:AUTHORED"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_evaluation(conn, contaminated)
    assert exc_info.value.code == "decision_utility_evaluation_invalid"

    role_drift = deepcopy(evaluation)
    role_drift["evaluation_id"] += ":ROLE"
    role_drift["reviewer_id"] = forecast["model_memory_mitigation"]["isolated_forecaster_id"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_evaluation(conn, role_drift)
    assert exc_info.value.code == "decision_utility_reviewer_not_independent"
    conn.close()
