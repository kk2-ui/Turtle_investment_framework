from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import judgment_decision_utility as utility
from scripts import judgment_pit_forecast as pit
from scripts import judgment_pit_forecast_control_plane as control
from scripts import judgment_training_program as training_program
from scripts import judgment_v5_control_plane as v5_control
from tests.test_judgment_decision_utility import _contract, _episodes, _pairing
from tests.test_judgment_pit_forecast import (
    _forecast,
    _forecast_acquisition_scope,
    _outcome_measurement_contract,
    _paired_evaluation,
    _pairing as _forecast_pairing,
    _preforecast_evidence_receipt,
    _universe_and_h1,
    _v3_observation_receipts,
    _v3_observed_settlement,
    _v6_forecast,
)
from tests.test_judgment_training_decision_contract import _contract as _training_contract


BASELINE_METHOD_ID = "METHOD:CONTROL:RETAIL_BASELINE:V1"
ENHANCED_METHOD_ID = "METHOD:CONTROL:RETAIL_ENHANCED:V1"


def _control_inputs() -> tuple[dict, dict, dict, dict, dict, dict]:
    contract = _contract()
    baseline, enhanced = _episodes(
        contract,
        baseline_method_id=BASELINE_METHOD_ID,
        enhanced_method_id=ENHANCED_METHOD_ID,
    )
    forecast = {
        "schema_version": "turtle-pit-company-state-forecast.v6",
        "forecast_id": "FORECAST:CN601933:20190501:V6",
        "company_id": contract["company_id"],
        "issuer_id": contract["issuer_id"],
        "cutoff_at": contract["cutoff_at"],
        "decision_contract_ref": {
            "contract_id": contract["contract_id"], "contract_version": contract["contract_version"],
        },
    }
    forecast_pairing = {
        "schema_version": "turtle-pit-forecast-pairing.v3",
        "pairing_id": "FORECAST-PAIR:CN601933:20190501:V3",
        "forecast_id": forecast["forecast_id"],
        "baseline_method_id": BASELINE_METHOD_ID,
        "enhanced_method_id": ENHANCED_METHOD_ID,
        "holdout_binding": {
            "program_id": "JTP:RETAIL:V1",
            "holdout_training_episode_id": "JTE:CN601933:20190501",
        },
    }
    pairing = _pairing(
        contract, baseline, enhanced, control=True,
        baseline_method_id=BASELINE_METHOD_ID,
        enhanced_method_id=ENHANCED_METHOD_ID,
    )
    pairing.update({
        "forecast_id": forecast["forecast_id"],
        "forecast_pairing_id": forecast_pairing["pairing_id"],
    })
    return contract, baseline, enhanced, forecast, forecast_pairing, pairing


def _control_evaluation(pairing: dict, paired: dict) -> dict:
    return {
        "schema_version": utility.CONTROL_EVALUATION_SCHEMA_VERSION,
        "evaluation_id": "UTILITY:EVALUATION:CN601933:20190501:V2",
        "pairing_id": pairing["pairing_id"],
        "forecast_paired_evaluation_id": paired["evaluation_id"],
        "evaluated_at": "2020-05-03T00:00:00+08:00",
        "reviewer_id": "AGENT:RETAIL:INDEPENDENT_DECISION_UTILITY_REVIEWER",
        "dimension_findings": [{
            "dimension_id": dimension,
            "baseline_assessment": "NO_DIFFERENCE",
            "enhanced_assessment": (
                "UNKNOWN" if dimension == "IMPLEMENTED_MANAGEMENT_ACTION"
                else "NOT_DIAGNOSTIC" if dimension == "CUSTOMER_COMPETITION_RESPONSE"
                else "MATERIAL_IMPROVEMENT"
            ),
            "rationale": "Each dimension remains independently reviewable without an aggregate release score.",
        } for dimension in utility.DIMENSIONS],
        "object_class": "DECISION_UTILITY_EVALUATION",
        "claim_class": "MATERIAL_DECISION_UTILITY_REVIEW",
        "allowed_outputs": list(utility.ALLOWED_OUTPUTS),
    }


def test_control_pairing_binds_episode_methods_to_frozen_forecast_pairing() -> None:
    contract, baseline, enhanced, forecast, forecast_pairing, pairing = _control_inputs()

    result = utility.validate_decision_utility_control_pairing(
        pairing,
        forecast=forecast,
        forecast_pairing=forecast_pairing,
        contract=contract,
        baseline_episode=baseline,
        enhanced_episode=enhanced,
    )

    assert result["valid"], result["findings"]
    assert result["learning_authorization"] == "CANDIDATE_ONLY"
    assert result["pairing"]["baseline_episode_id"] == baseline["episode_id"]
    assert result["pairing"]["enhanced_episode_id"] == enhanced["episode_id"]


def test_control_pairing_rejects_method_drift_and_missing_external_episode() -> None:
    contract, baseline, enhanced, forecast, forecast_pairing, pairing = _control_inputs()
    drift = deepcopy(pairing)
    drift["enhanced_method_id"] = "METHOD:UNBOUND"
    result = utility.validate_decision_utility_control_pairing(
        drift,
        forecast=forecast,
        forecast_pairing=forecast_pairing,
        contract=contract,
        baseline_episode=baseline,
        enhanced_episode=enhanced,
    )
    assert not result["valid"]
    assert "decision_utility_control_pairing.enhanced_method_must_match_forecast_pairing" in result["findings"]
    assert "decision_utility_control_pairing.enhanced_method_id_must_match_episode" in result["findings"]

    missing = utility.validate_decision_utility_control_pairing(
        pairing,
        forecast=forecast,
        forecast_pairing=forecast_pairing,
        contract=contract,
    )
    assert not missing["valid"]
    assert "decision_utility_control_pairing.baseline_episode_manifest_required" in missing["findings"]
    assert "decision_utility_control_pairing.enhanced_episode_manifest_required" in missing["findings"]


def test_control_evaluation_is_independent_and_candidate_only_with_local_unknowns() -> None:
    contract, baseline, enhanced, forecast, forecast_pairing, pairing = _control_inputs()
    paired = {
        "evaluation_id": "FORECAST:EVALUATION:CN601933:FY2019:V1",
        "pairing_id": forecast_pairing["pairing_id"],
        "forecast_id": forecast["forecast_id"],
        "evaluated_at": "2020-05-02T00:00:00+08:00",
    }
    evaluation = _control_evaluation(pairing, paired)

    result = utility.validate_decision_utility_control_evaluation(
        evaluation,
        pairing=pairing,
        forecast=forecast,
        forecast_pairing=forecast_pairing,
        forecast_paired_evaluation=paired,
        contract=contract,
        baseline_episode=baseline,
        enhanced_episode=enhanced,
    )

    assert result["valid"], result["findings"]
    assert result["learning_authorization"] == "CANDIDATE_ONLY"
    assert result["evaluation"] == evaluation
    conflicted = deepcopy(evaluation)
    conflicted["reviewer_id"] = contract["roles"]["outcome_custodian_id"]
    result = utility.validate_decision_utility_control_evaluation(
        conflicted,
        pairing=pairing,
        forecast=forecast,
        forecast_pairing=forecast_pairing,
        forecast_paired_evaluation=paired,
        contract=contract,
        baseline_episode=baseline,
        enhanced_episode=enhanced,
    )
    assert not result["valid"]
    assert "decision_utility_control_evaluation.reviewer_must_be_independent_of_contract_roles" in result["findings"]


def test_control_schema_has_no_embedded_decision_truth_source() -> None:
    schema = json.loads(Path("schemas/judgment_decision_utility_control.schema.json").read_text(encoding="utf-8"))
    pairing = schema["$defs"]["pairing"]
    assert pairing["additionalProperties"] is False
    assert "decision" not in schema["$defs"]
    assert "baseline_episode_id" in pairing["required"]
    assert "enhanced_episode_id" in pairing["required"]


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


def _v6_chain() -> tuple[sqlite3.Connection, dict, dict, dict, dict, dict, dict, dict]:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    contract = _training_contract(bootstrap)
    control.register_training_decision_contract(conn, contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe,
        h1,
        bootstrap["company_id"],
        forecast_id="FORECAST:SYNTHETIC:DECISION-UTILITY:BASE",
        decision_contract_ref={"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
    )
    measurement = _outcome_measurement_contract(v2, contract)
    control.register_forecast_outcome_measurement_contract(
        conn, measurement, frozen_at="2021-01-02T00:00:00+00:00",
    )
    evidence = _preforecast_evidence_receipt(v2, h1)
    control.register_preforecast_evidence_receipt(
        conn, evidence, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
    )
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
        conn, forecast, universe_snapshot=universe, stage0_package=h1,
        frozen_at="2021-01-05T00:00:00+00:00",
    )
    conn.execute(
        """INSERT INTO judgment_training_episodes
           (training_episode_id, program_id, case_id, company_id, company_cluster_id, industry_id,
            decision_domain, cutoff_at, outcome_not_before, outcome_window_ends_at, lane, provenance_role,
            outcome_access, holdout_axis, artifacts_json)
           VALUES (?, ?, 'HOLDOUT:SYNTHETIC:DECISION-UTILITY', ?, 'COMPANY:SYNTHETIC:DECISION-UTILITY',
                   'SYNTHETIC', 'FORECAST', ?, '2022-01-01T00:00:00+00:00', '2023-01-01T00:00:00+00:00',
                   'HISTORICAL_HOLDOUT', 'HISTORICAL_SELF_REPLAY', 'PIT_OUTCOME_SEALED',
                   'COMPANY_AND_TIME', '{}')""",
        (
            "JTE:SYNTHETIC:DECISION-UTILITY", method_ref["program_id"],
            forecast["company_id"], forecast["cutoff_at"],
        ),
    )
    conn.execute(
        """INSERT INTO judgment_training_episodes
           (training_episode_id, program_id, case_id, company_id, company_cluster_id, industry_id,
            decision_domain, cutoff_at, outcome_not_before, outcome_window_ends_at, lane, provenance_role,
            outcome_access, holdout_axis, artifacts_json)
           VALUES ('JTE:SYNTHETIC:DECISION-UTILITY:TRAINING', ?, 'TRAINING:SYNTHETIC:DECISION-UTILITY',
                   'CN:SYNTHETIC:TRAIN', 'COMPANY:SYNTHETIC:DECISION-UTILITY:TRAIN', 'SYNTHETIC',
                   'FORECAST', '2019-12-31T23:59:59+00:00', '2020-01-01T00:00:00+00:00',
                   '2021-01-01T00:00:00+00:00', 'HISTORICAL_TRAINING', 'HISTORICAL_SELF_REPLAY',
                   'PIT_OUTCOME_SEALED', NULL, '{}')""",
        (method_ref["program_id"],),
    )
    conn.commit()
    forecast_pairing = _forecast_pairing(forecast)
    forecast_pairing["schema_version"] = pit.PAIRING_SCHEMA_VERSION_V3
    forecast_pairing["holdout_binding"] = {
        "program_id": method_ref["program_id"],
        "holdout_training_episode_id": "JTE:SYNTHETIC:DECISION-UTILITY",
        "evaluated_cell_refs": [{"dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR"}],
    }
    control.register_forecast_method_pairing(conn, forecast_pairing, frozen_at="2021-01-06T00:00:00+00:00")
    baseline, enhanced = _episodes(
        contract,
        baseline_method_id=forecast_pairing["baseline_method_id"],
        enhanced_method_id=forecast_pairing["enhanced_method_id"],
    )
    pairing = _pairing(
        contract,
        baseline,
        enhanced,
        control=True,
        baseline_method_id=forecast_pairing["baseline_method_id"],
        enhanced_method_id=forecast_pairing["enhanced_method_id"],
    )
    pairing.update({
        "pairing_id": f"UTILITY:{forecast['forecast_id']}",
        "forecast_id": forecast["forecast_id"],
        "forecast_pairing_id": forecast_pairing["pairing_id"],
        "frozen_at": "2021-01-06T12:00:00+00:00",
    })
    return conn, forecast, contract, measurement, forecast_pairing, pairing, baseline, enhanced


def _authorize_and_evaluate(
    conn: sqlite3.Connection, forecast: dict, contract: dict, measurement: dict, forecast_pairing: dict,
) -> dict:
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


def test_registered_pairing_persists_immutable_episode_snapshots_before_outcome_access() -> None:
    conn, forecast, contract, measurement, forecast_pairing, pairing, baseline, enhanced = _v6_chain()
    first = control.register_decision_utility_pairing(
        conn,
        pairing,
        baseline_episode=baseline,
        enhanced_episode=enhanced,
        frozen_at=pairing["frozen_at"],
    )
    replay = control.register_decision_utility_pairing(
        conn,
        deepcopy(pairing),
        baseline_episode=deepcopy(baseline),
        enhanced_episode=deepcopy(enhanced),
        frozen_at=pairing["frozen_at"],
    )
    assert first == {
        "frozen": True,
        "pairing_id": pairing["pairing_id"],
        "idempotent": False,
        "learning_authorization": "CANDIDATE_ONLY",
    }
    assert replay["idempotent"] is True
    rows = conn.execute(
        f"SELECT episode_role FROM {control.DECISION_UTILITY_EPISODE_TABLE} "
        "WHERE decision_utility_pairing_id = ? ORDER BY episode_role",
        (pairing["pairing_id"],),
    ).fetchall()
    assert [row["episode_role"] for row in rows] == ["BASELINE", "ENHANCED"]

    changed = deepcopy(enhanced)
    changed["claims"][0]["statement"] = "A post-freeze replacement must not be accepted."
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_pairing(
            conn,
            deepcopy(pairing),
            baseline_episode=baseline,
            enhanced_episode=changed,
            frozen_at=pairing["frozen_at"],
        )
    assert exc_info.value.code == "decision_utility_episode_immutable_conflict"

    _authorize_and_evaluate(conn, forecast, contract, measurement, forecast_pairing)
    late = deepcopy(pairing)
    late["pairing_id"] += ":LATE"
    late["baseline_episode_id"] = baseline["episode_id"]
    late["enhanced_episode_id"] = enhanced["episode_id"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_pairing(
            conn,
            late,
            baseline_episode=baseline,
            enhanced_episode=enhanced,
            frozen_at=late["frozen_at"],
        )
    assert exc_info.value.code == "decision_utility_pairing_must_precede_outcome_access_authorization"
    conn.close()


def test_registered_utility_evaluation_uses_frozen_episode_snapshots() -> None:
    conn, forecast, contract, measurement, forecast_pairing, pairing, baseline, enhanced = _v6_chain()
    control.register_decision_utility_pairing(
        conn,
        pairing,
        baseline_episode=baseline,
        enhanced_episode=enhanced,
        frozen_at=pairing["frozen_at"],
    )
    paired = _authorize_and_evaluate(conn, forecast, contract, measurement, forecast_pairing)
    evaluation = _control_evaluation(pairing, paired)
    evaluation["evaluated_at"] = "2022-04-03T00:00:00+00:00"
    first = control.register_decision_utility_evaluation(conn, evaluation)
    replay = control.register_decision_utility_evaluation(conn, deepcopy(evaluation))
    assert first == {
        "evaluated": True,
        "evaluation_id": evaluation["evaluation_id"],
        "idempotent": False,
        "learning_authorization": "CANDIDATE_ONLY",
    }
    assert replay["idempotent"] is True

    conn.execute(
        f"DELETE FROM {control.DECISION_UTILITY_EPISODE_TABLE} "
        "WHERE decision_utility_pairing_id = ? AND episode_role = 'ENHANCED'",
        (pairing["pairing_id"],),
    )
    missing = deepcopy(evaluation)
    missing["evaluation_id"] += ":MISSING"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_decision_utility_evaluation(conn, missing)
    assert exc_info.value.code == "decision_utility_episode_snapshot_not_found"
    conn.close()
