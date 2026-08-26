from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import judgment_pit_forecast as pit
from scripts import judgment_pit_forecast_control_plane as control
from scripts import judgment_training_program as training_program
from scripts import judgment_v5_control_plane as v5_control
from tests.test_judgment_pit_forecast import (
    _attribution, _forecast, _observed_settlement, _outcome_measurement_contract, _paired_evaluation, _pairing,
    _curator_field_extraction, _forecast_acquisition_scope, _preforecast_evidence_receipt, _universe_and_h1,
    _v3_forecast, _v3_observation_receipts, _v3_observed_settlement, _v4_forecast, _v5_forecast, _v6_forecast,
)
from tests.test_judgment_training_decision_contract import _contract


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    control.initialize(conn)
    return conn


def _register_h1_receipt(conn: sqlite3.Connection, h1: dict) -> None:
    v5_control.initialize(conn)
    result = v5_control.register_h1_static_cohort_receipt(conn, {
        "receipt_id": "H1:SYNTHETIC:FORECAST:V1",
        "receipt_version": 1,
        "recorded_at": "2021-01-01T00:00:00+00:00",
        "stage0_static_package": h1,
    })
    assert result["registered"]


def _freeze(conn: sqlite3.Connection, universe: dict, h1: dict, company_id: str, *, forecast_id: str | None = None) -> dict:
    forecast = _forecast(universe, h1, company_id, forecast_id=forecast_id)
    result = control.register_company_state_forecast(
        conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-02T00:00:00+00:00",
    )
    assert result["frozen"]
    return forecast


def test_forecast_freeze_is_immutable_and_cannot_be_backdated() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    forecast = _forecast(universe, h1, universe["members"][0]["company_id"])
    first = control.register_company_state_forecast(
        conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-02T00:00:00+00:00",
    )
    replay = control.register_company_state_forecast(
        conn, deepcopy(forecast), universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-02T00:00:00+00:00",
    )
    assert first["idempotent"] is False
    assert replay["idempotent"] is True
    changed = deepcopy(forecast)
    changed["dimensions"][0]["forecast_by_window"][0]["probabilities"][0]["probability"] = 0.2
    changed["dimensions"][0]["forecast_by_window"][0]["probabilities"][1]["probability"] = 0.5
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, changed, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-02T00:00:00+00:00",
        )
    assert exc_info.value.code == "forecast_immutable_conflict"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2999-01-01T00:00:00+00:00",
        )
    assert exc_info.value.code == "frozen_at_cannot_be_in_future"
    conn.close()


def test_v2_forecast_requires_a_previously_frozen_matching_decision_contract() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    first = control.register_training_decision_contract(
        conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
    )
    assert first["frozen"] and not first["idempotent"]
    v2_forecast = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:V2",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    registered = control.register_company_state_forecast(
        conn, v2_forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-02T00:00:00+00:00",
    )
    assert registered["frozen"]
    settlement = _observed_settlement(v2_forecast)
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_settlement(conn, settlement)
    assert exc_info.value.code == "settlement_invalid"
    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION,
        "authorization_id": "OUTCOME-ACCESS:SYNTHETIC:V2",
        "forecast_id": v2_forecast["forecast_id"],
        "company_id": v2_forecast["company_id"],
        "cutoff_at": v2_forecast["cutoff_at"],
        "custodian_id": decision_contract["roles"]["outcome_custodian_id"],
        "authorized_at": "2021-01-03T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION",
        "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    wrong_access = deepcopy(access)
    wrong_access["authorization_id"] = "OUTCOME-ACCESS:SYNTHETIC:V2:WRONG"
    wrong_access["custodian_id"] = "SYNTHETIC:OTHER:CUSTODIAN"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.authorize_forecast_outcome_access(conn, wrong_access)
    assert exc_info.value.code == "outcome_access_custodian_must_match_decision_contract"
    assert control.authorize_forecast_outcome_access(conn, access)["authorized"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_settlement(conn, settlement)
    assert exc_info.value.code == "settlement_invalid"

    unknown_ref = deepcopy(v2_forecast)
    unknown_ref["forecast_id"] = "FORECAST:SYNTHETIC:V2:UNKNOWN"
    unknown_ref["decision_contract_ref"]["contract_id"] = "DC:UNKNOWN"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, unknown_ref, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
        )
    assert exc_info.value.code == "decision_contract_not_found"

    legacy_retrofit = _forecast(universe, h1, bootstrap["company_id"])
    legacy_retrofit["decision_contract_ref"] = {"contract_id": decision_contract["contract_id"], "contract_version": 1}
    rejected = pit.validate_company_state_forecast(legacy_retrofit, universe_snapshot=universe, stage0_package=h1)
    assert not rejected["valid"]
    assert "forecast.v1_cannot_retrofit_decision_contract" in rejected["findings"]
    conn.close()


def test_v3_forecast_requires_a_prior_measurement_contract_and_deterministic_observed_mapping() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:V3:BASE",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, _v3_forecast(v2, measurement_contract), universe_snapshot=universe, stage0_package=h1,
            frozen_at="2021-01-03T00:00:00+00:00",
        )
    assert exc_info.value.code == "outcome_measurement_contract_not_found"
    unapproved_policy = deepcopy(measurement_contract)
    unapproved_policy["measurement_contract_id"] = "OMC:SYNTHETIC:UNAPPROVED-POLICY"
    unapproved_policy["applied_policy_change_ids"] = ["POLICY:UNFROZEN"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_outcome_measurement_contract(
            conn, unapproved_policy, frozen_at="2021-01-02T00:00:00+00:00",
        )
    assert exc_info.value.code == "measurement_contract_policy_application_mismatch"
    registered = control.register_forecast_outcome_measurement_contract(
        conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00",
    )
    assert registered["frozen"]
    v3 = _v3_forecast(v2, measurement_contract)
    assert control.register_company_state_forecast(
        conn, v3, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
    )["frozen"]
    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION_V2,
        "authorization_id": "OUTCOME-ACCESS:SYNTHETIC:V3",
        "forecast_id": v3["forecast_id"],
        "company_id": v3["company_id"],
        "cutoff_at": v3["cutoff_at"],
        "custodian_id": decision_contract["roles"]["outcome_custodian_id"],
        "authorized_at": "2021-01-04T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "outcome_measurement_contract_ref": deepcopy(v3["outcome_measurement_contract_ref"]),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION",
        "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    assert control.authorize_forecast_outcome_access(conn, access)["authorized"]
    observations = _v3_observation_receipts(v3, measurement_contract)
    first_observation_id = next(iter(observations))
    mismatch_receipt = observations.pop(first_observation_id)
    mismatch_receipt["observation_status"] = "MEASUREMENT_MISMATCH"
    mismatch_receipt.pop("realized_measurement")
    mismatch_receipt["mismatch_rule"] = measurement_contract["cells"][0]["mismatch_rules"][0]
    mismatch_receipt["mismatch_detail"] = "The disclosed result uses a different frozen responsibility boundary."
    mismatch_receipt["outcome_source"]["source_field_id"] = "FIELD:DISCLOSED:DIFFERENT:BOUNDARY"
    assert control.register_forecast_outcome_observation_receipt(conn, mismatch_receipt)["recorded"]
    for receipt in observations.values():
        assert control.register_forecast_outcome_observation_receipt(conn, receipt)["recorded"]
    settlement = _v3_observed_settlement(v3, measurement_contract)
    first_entry = next(
        entry for entry in settlement["dimension_settlements"]
        if entry["outcome_observation_ref"]["observation_id"] == first_observation_id
    )
    first_entry["status"] = "MEASUREMENT_MISMATCH"
    first_entry["realized_label"] = None
    assert control.register_forecast_settlement(conn, settlement)["coverage"]["observed_scored_cells"] == 17

    drifted_settlement = _v3_observed_settlement(v3, measurement_contract)
    drifted_settlement["dimension_settlements"][0]["outcome_observation_ref"]["observation_id"] = "OBS:UNREGISTERED"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_settlement(conn, drifted_settlement)
    assert exc_info.value.code == "settlement_invalid"
    conn.close()


def test_v4_forecast_requires_an_immutable_h1_bound_field_extraction_before_freeze() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:V4:BASE",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    control.register_forecast_outcome_measurement_contract(
        conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00",
    )
    evidence_receipt = _preforecast_evidence_receipt(v2, h1)
    v4 = _v4_forecast(v2, measurement_contract, evidence_receipt)

    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, v4, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-04T00:00:00+00:00",
        )
    assert exc_info.value.code == "preforecast_evidence_receipt_not_found"

    invalid_page = deepcopy(evidence_receipt)
    invalid_page["fields"][0]["field_ref"] = "Synthetic annual report field without an extractable page."
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_preforecast_evidence_receipt(
            conn, invalid_page, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
        )
    assert exc_info.value.code == "preforecast_evidence_receipt_invalid"

    receipt = control.register_curator_preforecast_field_extraction(
        conn, _curator_field_extraction(evidence_receipt),
        evidence_receipt_id=evidence_receipt["evidence_receipt_id"], evidence_receipt_version=1,
        h1_source_packet_ref=evidence_receipt["h1_source_packet_ref"], company_id=v2["company_id"],
        issuer_id=v2["issuer_id"], cutoff_at=v2["cutoff_at"], curator_id=evidence_receipt["curator_id"],
        stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
    )
    assert receipt == {
        "frozen": True,
        "evidence_receipt_id": evidence_receipt["evidence_receipt_id"],
        "idempotent": False,
    }
    role_drift = deepcopy(v4)
    role_drift["model_memory_mitigation"]["isolated_forecaster_id"] = evidence_receipt["curator_id"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, role_drift, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-04T00:00:00+00:00",
        )
    assert exc_info.value.code == "forecast_invalid"
    frozen = control.register_company_state_forecast(
        conn, v4, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-04T00:00:00+00:00",
    )
    assert frozen["frozen"] and not frozen["idempotent"]
    assert control.register_company_state_forecast(
        conn, deepcopy(v4), universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-04T00:00:00+00:00",
    )["idempotent"]
    late_scope = _forecast_acquisition_scope(v2, measurement_contract)
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_acquisition_scope(conn, late_scope, frozen_at="2021-01-05T00:00:00+00:00")
    assert exc_info.value.code == "acquisition_scope_must_precede_forecast"
    assert conn.execute(f"SELECT COUNT(*) FROM {control.OUTCOME_ACCESS_TABLE} WHERE forecast_id = ?", (v4["forecast_id"],)).fetchone()[0] == 0
    conn.close()


def test_v5_requires_a_frozen_acquisition_scope_and_blocks_out_of_scope_observations() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:V5:BASE",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    control.register_forecast_outcome_measurement_contract(
        conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00",
    )
    evidence_receipt = _preforecast_evidence_receipt(v2, h1)
    control.register_preforecast_evidence_receipt(
        conn, evidence_receipt, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
    )
    included_dimensions = set(pit.FORECAST_DIMENSIONS[:-2])
    scope = _forecast_acquisition_scope(v2, measurement_contract, included_dimensions=included_dimensions)
    v5 = _v5_forecast(v2, measurement_contract, evidence_receipt, scope)
    for dimension in v5["dimensions"]:
        if dimension["dimension_id"] not in included_dimensions:
            dimension["evidence_status"] = "EVIDENCE_INELIGIBLE"
            dimension["forecast_by_window"] = []

    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, v5, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-05T00:00:00+00:00",
        )
    assert exc_info.value.code == "forecast_acquisition_scope_not_found"
    frozen_scope = control.register_forecast_acquisition_scope(
        conn, scope, frozen_at="2021-01-04T00:00:00+00:00",
    )
    assert frozen_scope["frozen"] and not frozen_scope["idempotent"]
    assert control.register_company_state_forecast(
        conn, v5, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-05T00:00:00+00:00",
    )["frozen"]

    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION_V3,
        "authorization_id": "OUTCOME-ACCESS:SYNTHETIC:V5",
        "forecast_id": v5["forecast_id"],
        "company_id": v5["company_id"],
        "cutoff_at": v5["cutoff_at"],
        "custodian_id": decision_contract["roles"]["outcome_custodian_id"],
        "authorized_at": "2021-01-06T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "outcome_measurement_contract_ref": deepcopy(v5["outcome_measurement_contract_ref"]),
        "forecast_acquisition_scope_ref": deepcopy(v5["forecast_acquisition_scope_ref"]),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION",
        "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    missing_scope_access = deepcopy(access)
    missing_scope_access.pop("forecast_acquisition_scope_ref")
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.authorize_forecast_outcome_access(conn, missing_scope_access)
    assert exc_info.value.code == "outcome_access_invalid"
    assert control.authorize_forecast_outcome_access(conn, access)["authorized"]
    observations = _v3_observation_receipts(v5, measurement_contract)
    in_scope = observations[f"OBS:{v5['forecast_id']}:NORMAL_EARNINGS:ONE_YEAR"]
    assert control.register_forecast_outcome_observation_receipt(conn, in_scope)["recorded"]
    excluded = observations[f"OBS:{v5['forecast_id']}:PERMANENT_LOSS_RISK:ONE_YEAR"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_outcome_observation_receipt(conn, excluded)
    assert exc_info.value.code == "outcome_observation_invalid"
    assert conn.execute(
        f"SELECT COUNT(*) FROM {control.OUTCOME_OBSERVATION_TABLE} WHERE forecast_id = ?", (v5["forecast_id"],),
    ).fetchone()[0] == 1
    for observation in observations.values():
        if observation["dimension_id"] in included_dimensions and observation["observation_id"] != in_scope["observation_id"]:
            assert control.register_forecast_outcome_observation_receipt(conn, observation)["recorded"]
    base_for_settlement = deepcopy(v5)
    for original, dimension in zip(v2["dimensions"], base_for_settlement["dimensions"]):
        if dimension["dimension_id"] not in included_dimensions:
            dimension["evidence_status"] = "MODEL_UNCERTAIN"
            dimension["forecast_by_window"] = deepcopy(original["forecast_by_window"])
    settlement = _v3_observed_settlement(base_for_settlement, measurement_contract)
    for entry in settlement["dimension_settlements"]:
        if entry["dimension_id"] not in included_dimensions:
            entry["status"] = "EVIDENCE_INELIGIBLE"
            entry["realized_label"] = None
            entry.pop("outcome_observation_ref")
    assert control.register_forecast_settlement(conn, settlement)["settled"]
    conn.close()


def test_v6_forecast_binds_the_preexisting_immutable_method_identity() -> None:
    conn = _conn()
    training_program.initialize(conn)
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:METHOD:V6:BASE",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    control.register_forecast_outcome_measurement_contract(conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00")
    evidence_receipt = _preforecast_evidence_receipt(v2, h1)
    control.register_preforecast_evidence_receipt(conn, evidence_receipt, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00")
    scope = _forecast_acquisition_scope(v2, measurement_contract)
    control.register_forecast_acquisition_scope(conn, scope, frozen_at="2021-01-04T00:00:00+00:00")
    conn.execute(
        """INSERT INTO judgment_training_programs
               (program_id, program_state, method_version, method_scope, registered_at, method_frozen_at,
                method_freeze_recorded_at, sampling_policy_json, contract_ref)
               VALUES (?, 'ACTIVE', ?, 'BOUNDARY_ONLY', ?, ?, ?, '{}', 'synthetic:method-program')""",
        (
            "JTP:synthetic-forecast-method", "METHOD:TRAINING_ENHANCED:V1",
            "2021-01-01T00:00:00+00:00", "2021-01-04T00:00:00+00:00", "2021-01-04T01:00:00+00:00",
        ),
    )
    conn.commit()
    method_ref = {
        "program_id": "JTP:synthetic-forecast-method",
        "method_version": "METHOD:TRAINING_ENHANCED:V1",
        "method_frozen_at": "2021-01-04T00:00:00+00:00",
        "method_freeze_recorded_at": "2021-01-04T01:00:00+00:00",
    }
    v6 = _v6_forecast(v2, measurement_contract, evidence_receipt, scope, method_ref=method_ref)
    assert control.register_company_state_forecast(
        conn, v6, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-05T00:00:00+00:00",
    )["frozen"]
    mismatch = deepcopy(v6)
    mismatch["forecast_id"] = "FORECAST:SYNTHETIC:METHOD:V6:MISMATCH"
    mismatch["forecast_method_ref"]["method_version"] = "METHOD:REWRITTEN"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_company_state_forecast(
            conn, mismatch, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-05T00:00:00+00:00",
        )
    assert exc_info.value.code == "forecast_method_identity_invalid"

    for program_id, method_frozen_at, method_recorded_at in (
        ("JTP:synthetic-forecast-method", "2021-01-04T00:00:00+00:00", "2021-01-04T01:00:00+00:00"),
        ("JTP:synthetic-forecast-method-same-name", "2021-01-04T02:00:00+00:00", "2021-01-04T03:00:00+00:00"),
    ):
        if program_id != "JTP:synthetic-forecast-method":
            conn.execute(
                """INSERT INTO judgment_training_programs
                       (program_id, program_state, method_version, method_scope, registered_at, method_frozen_at,
                        method_freeze_recorded_at, sampling_policy_json, contract_ref)
                       VALUES (?, 'ACTIVE', ?, 'BOUNDARY_ONLY', ?, ?, ?, '{}', 'synthetic:method-program')""",
                (
                    program_id, "METHOD:TRAINING_ENHANCED:V1",
                    "2021-01-01T00:00:00+00:00", method_frozen_at, method_recorded_at,
                ),
            )
        conn.execute(
            """INSERT INTO judgment_training_episodes
                   (training_episode_id, program_id, case_id, company_id, company_cluster_id, industry_id,
                    decision_domain, cutoff_at, outcome_not_before, lane, provenance_role, outcome_access,
                    holdout_axis, artifacts_json)
                   VALUES (?, ?, ?, ?, 'COMPANY:SYNTHETIC:METHOD', 'SYNTHETIC', 'FORECAST', ?,
                           '2022-01-01T00:00:00+00:00', 'HISTORICAL_HOLDOUT', 'HISTORICAL_SELF_REPLAY',
                           'PIT_OUTCOME_SEALED', 'COMPANY_AND_TIME', '{}')""",
            (
                f"JTE:synthetic-forecast-method:{program_id.rsplit('-', 1)[-1]}", program_id,
                f"HOLDOUT:SYNTHETIC:METHOD:{program_id.rsplit('-', 1)[-1]}", v6["company_id"], v6["cutoff_at"],
            ),
        )
    conn.commit()
    pairing = _pairing(v6)
    pairing["schema_version"] = pit.PAIRING_SCHEMA_VERSION_V2
    pairing["holdout_binding"] = {
        "program_id": "JTP:synthetic-forecast-method-same-name",
        "holdout_training_episode_id": "JTE:synthetic-forecast-method:name",
        "evaluated_cell_refs": [{"dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR"}],
    }
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_method_pairing(conn, pairing, frozen_at="2021-01-06T00:00:00+00:00")
    assert exc_info.value.code == "pairing_invalid"
    assert "program_id_must_match_forecast_method_identity" in str(exc_info.value)
    pairing["holdout_binding"] = {
        "program_id": "JTP:synthetic-forecast-method",
        "holdout_training_episode_id": "JTE:synthetic-forecast-method:method",
        "evaluated_cell_refs": [{"dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR"}],
    }
    assert control.register_forecast_method_pairing(
        conn, pairing, frozen_at="2021-01-06T00:00:00+00:00",
    )["frozen"]
    conn.close()


def test_v2_shadow_requires_the_same_previously_frozen_decision_contract_and_no_outcome() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    forecast = _forecast(universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:SHADOW:V2", decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1})
    control.register_company_state_forecast(conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-02T00:00:00+00:00")
    shadow = {"schema_version": pit.SHADOW_SCHEMA_VERSION_V2, "shadow_episode_id": "SHADOW:SYNTHETIC:V2", "forecast_epoch_id": pit.FORECAST_EPOCH_ID_V2, "company_id": forecast["company_id"], "issuer_id": forecast["issuer_id"], "cutoff_at": forecast["cutoff_at"], "forecast_id": forecast["forecast_id"], "outcome_windows": list(pit.FORECAST_WINDOWS), "custodian_id": "SYNTHETIC:CUSTODIAN", "status": "WAITING_EXTERNAL_OUTCOME", "object_class": "PROSPECTIVE_SHADOW_EPISODE", "claim_class": "PREQUENTIAL_EVALUATION", "allowed_outputs": ["FORECAST_EVALUATION_ONLY"], "decision_contract_ref": {"contract_id": decision_contract["contract_id"], "contract_version": 1}}
    assert control.register_prospective_shadow_episode(conn, shadow, registered_at="2026-08-25T00:00:00+08:00")["registered"]
    wrong_custodian = deepcopy(shadow)
    wrong_custodian["shadow_episode_id"] = "SHADOW:SYNTHETIC:V2:WRONG-CUSTODIAN"
    wrong_custodian["custodian_id"] = "SYNTHETIC:OTHER:CUSTODIAN"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_prospective_shadow_episode(conn, wrong_custodian, registered_at="2026-08-25T00:00:00+08:00")
    assert exc_info.value.code == "shadow_custodian_must_match_decision_contract"
    contaminated = deepcopy(shadow); contaminated["shadow_episode_id"] = "SHADOW:SYNTHETIC:V2:OUTCOME"; contaminated["outcome"] = "known"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_prospective_shadow_episode(conn, contaminated, registered_at="2026-08-25T00:00:00+08:00")
    assert exc_info.value.code == "shadow_invalid"
    conn.close()


def test_v3_prospective_company_shadow_binds_measurement_and_closes_access_until_resolution() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:SHADOW:V3:BASE",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    future_periods = {"ONE_YEAR": "2026-08-18", "THREE_YEAR": "2026-08-19", "FIVE_YEAR": "2026-08-20"}
    for cell in measurement_contract["cells"]:
        cell["outcome_period_end"] = future_periods[cell["window_id"]]
    control.register_forecast_outcome_measurement_contract(
        conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00",
    )
    forecast = _v3_forecast(v2, measurement_contract)
    control.register_company_state_forecast(
        conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
    )
    shadow = {
        "schema_version": pit.SHADOW_SCHEMA_VERSION_V3,
        "shadow_episode_id": "SHADOW:SYNTHETIC:V3",
        "forecast_epoch_id": pit.FORECAST_EPOCH_ID_V3,
        "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"],
        "cutoff_at": forecast["cutoff_at"],
        "forecast_id": forecast["forecast_id"],
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "custodian_id": decision_contract["roles"]["outcome_custodian_id"],
        "status": "WAITING_EXTERNAL_OUTCOME",
        "object_class": "PROSPECTIVE_SHADOW_EPISODE",
        "claim_class": "PREQUENTIAL_EVALUATION",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY"],
        "decision_contract_ref": deepcopy(forecast["decision_contract_ref"]),
        "outcome_measurement_contract_ref": deepcopy(forecast["outcome_measurement_contract_ref"]),
        "resolution_calendar": [
            {"window_id": window_id, "resolution_due_at": "2026-08-24T00:00:00+00:00"}
            for window_id in pit.FORECAST_WINDOWS
        ],
    }
    assert control.register_prospective_shadow_episode(
        conn, shadow, registered_at="2021-01-04T00:00:00+00:00",
    )["registered"]
    before_forecast = deepcopy(shadow)
    before_forecast["shadow_episode_id"] = "SHADOW:SYNTHETIC:V3:BEFORE-FORECAST"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_prospective_shadow_episode(conn, before_forecast, registered_at="2021-01-02T00:00:00+00:00")
    assert exc_info.value.code == "forecast_must_precede_shadow_registration"
    historical_relabel = deepcopy(shadow)
    historical_relabel["shadow_episode_id"] = "SHADOW:SYNTHETIC:V3:HISTORICAL"
    historical_relabel["resolution_calendar"] = [
        {"window_id": window_id, "resolution_due_at": "2027-01-01T00:00:00+00:00"}
        for window_id in pit.FORECAST_WINDOWS
    ]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_prospective_shadow_episode(conn, historical_relabel, registered_at="2026-08-25T00:00:00+00:00")
    assert exc_info.value.code == "shadow_outcome_period_already_started"
    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION_V2,
        "authorization_id": "OUTCOME-ACCESS:SYNTHETIC:SHADOW:V3",
        "forecast_id": forecast["forecast_id"],
        "company_id": forecast["company_id"],
        "cutoff_at": forecast["cutoff_at"],
        "custodian_id": decision_contract["roles"]["outcome_custodian_id"],
        "authorized_at": "2021-01-05T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "outcome_measurement_contract_ref": deepcopy(forecast["outcome_measurement_contract_ref"]),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION",
        "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.authorize_forecast_outcome_access(conn, access)
    assert exc_info.value.code == "outcome_access_precedes_prospective_shadow_resolution_due"
    assert conn.execute(f"SELECT COUNT(*) FROM {control.OUTCOME_ACCESS_TABLE}").fetchone()[0] == 0
    access["authorized_at"] = "2026-08-25T00:00:00+00:00"
    assert control.authorize_forecast_outcome_access(conn, access)["authorized"]
    late_shadow = deepcopy(shadow)
    late_shadow["shadow_episode_id"] = "SHADOW:SYNTHETIC:V3:LATE"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_prospective_shadow_episode(conn, late_shadow, registered_at="2026-08-23T00:00:00+00:00")
    assert exc_info.value.code == "shadow_outcome_period_already_started"
    conn.close()


def test_tournament_resolves_only_frozen_forecasts_and_shadow_does_not_expose_outcome() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    pending_company_ids = [member["company_id"] for member in h1["members"]
                           if member["final_peer_panel_disposition"] == "PENDING_ACTION_WINDOW_REVIEW"]
    forecasts = [_freeze(conn, universe, h1, company_id) for company_id in pending_company_ids]
    company_ids = [forecast["company_id"] for forecast in forecasts]
    tournament = {
        "schema_version": pit.TOURNAMENT_SCHEMA_VERSION,
        "tournament_id": "TOURNAMENT:SYNTHETIC:CONTROL:V1",
        "forecast_epoch_id": pit.FORECAST_EPOCH_ID,
        "cutoff_at": universe["cutoff_at"],
        "universe_id": universe["universe_id"],
        "source_packet_refs": [{"receipt_id": "H1:SYNTHETIC:FORECAST:V1", "receipt_version": 1}],
        "ranked_company_ids": company_ids,
        "forecast_ids": [forecast["forecast_id"] for forecast in forecasts],
        "dimension_rankings": [{
            "dimension_id": dimension_id,
            "ordered_company_ids": company_ids,
            "unranked_company_ids": [],
            "rationale": "Reference ranking, not a causal panel.",
        } for dimension_id in pit.FORECAST_DIMENSIONS],
        "object_class": "RELATIVE_TRAJECTORY_TOURNAMENT",
        "claim_class": "RELATIVE_TRAJECTORY_REFERENCE",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }
    assert control.register_relative_trajectory_tournament(
        conn, tournament, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
    )["frozen"]
    shadow = {
        "schema_version": pit.SHADOW_SCHEMA_VERSION,
        "shadow_episode_id": "SHADOW:SYNTHETIC:CONTROL:V1",
        "forecast_epoch_id": pit.FORECAST_EPOCH_ID,
        "company_id": forecasts[0]["company_id"],
        "issuer_id": forecasts[0]["issuer_id"],
        "cutoff_at": forecasts[0]["cutoff_at"],
        "forecast_id": forecasts[0]["forecast_id"],
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "custodian_id": "SYNTHETIC:INDEPENDENT:CUSTODIAN",
        "status": "WAITING_EXTERNAL_OUTCOME",
        "object_class": "PROSPECTIVE_SHADOW_EPISODE",
        "claim_class": "PREQUENTIAL_EVALUATION",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY"],
    }
    assert control.register_prospective_shadow_episode(
        conn, shadow, registered_at="2026-08-25T00:00:00+08:00",
    )["registered"]
    assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
    conn.close()


def test_only_an_independent_custodian_can_settle_frozen_forecast() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:ROLE:V2",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    control.register_forecast_outcome_measurement_contract(conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00")
    forecast = _v3_forecast(v2, measurement_contract)
    control.register_company_state_forecast(conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00")
    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION_V2,
        "authorization_id": "OUTCOME-ACCESS:SYNTHETIC:ROLE:V3",
        "forecast_id": forecast["forecast_id"], "company_id": forecast["company_id"], "cutoff_at": forecast["cutoff_at"],
        "custodian_id": "SYNTHETIC:CUSTODIAN", "authorized_at": "2021-01-04T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "outcome_measurement_contract_ref": deepcopy(forecast["outcome_measurement_contract_ref"]),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION", "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    control.authorize_forecast_outcome_access(conn, access)
    for receipt in _v3_observation_receipts(forecast, measurement_contract).values():
        control.register_forecast_outcome_observation_receipt(conn, receipt)
    settlement = _v3_observed_settlement(forecast, measurement_contract)
    settlement["custodian_id"] = forecast["model_memory_mitigation"]["isolated_forecaster_id"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_settlement(conn, settlement)
    assert exc_info.value.code == "settlement_custodian_not_independent"
    settlement["custodian_id"] = "SYNTHETIC:CUSTODIAN"
    result = control.register_forecast_settlement(conn, settlement)
    assert result["settled"] and result["coverage"]["selective_coverage"] == 1.0
    assert control.register_forecast_settlement(conn, deepcopy(settlement))["idempotent"] is True
    conn.close()


def test_pairing_precedes_outcome_and_only_direct_forecast_policy_becomes_active() -> None:
    conn = _conn()
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(
        conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
    )
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:POLICY:V2",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    control.register_forecast_outcome_measurement_contract(
        conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00",
    )
    forecast = _v3_forecast(v2, measurement_contract)
    control.register_company_state_forecast(
        conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00",
    )
    pairing = _pairing(forecast)
    first = control.register_forecast_method_pairing(conn, pairing, frozen_at="2021-01-03T12:00:00+00:00")
    assert first["frozen"] and not first["idempotent"]
    assert control.register_forecast_method_pairing(
        conn, deepcopy(pairing), frozen_at="2021-01-03T12:00:00+00:00",
    )["idempotent"]

    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION_V2,
        "authorization_id": "OUTCOME-ACCESS:SYNTHETIC:POLICY:V3",
        "forecast_id": forecast["forecast_id"],
        "company_id": forecast["company_id"],
        "cutoff_at": forecast["cutoff_at"],
        "custodian_id": decision_contract["roles"]["outcome_custodian_id"],
        "authorized_at": "2021-01-04T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "outcome_measurement_contract_ref": deepcopy(forecast["outcome_measurement_contract_ref"]),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION",
        "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    control.authorize_forecast_outcome_access(conn, access)
    post_access_pairing = deepcopy(pairing)
    post_access_pairing["pairing_id"] = "PAIRING:POST_ACCESS:REJECTED"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_method_pairing(
            conn, post_access_pairing, frozen_at="2021-01-04T00:00:01+00:00",
        )
    assert exc_info.value.code == "pairing_must_precede_outcome_access_authorization"
    for receipt in _v3_observation_receipts(forecast, measurement_contract).values():
        control.register_forecast_outcome_observation_receipt(conn, receipt)
    settlement = _v3_observed_settlement(forecast, measurement_contract)
    assert control.register_forecast_settlement(conn, settlement)["settled"]
    late_pairing = deepcopy(pairing)
    late_pairing["pairing_id"] = "PAIRING:TOO_LATE"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_method_pairing(conn, late_pairing, frozen_at="2022-04-02T00:00:00+00:00")
    assert exc_info.value.code == "pairing_must_be_frozen_before_settlement"

    evaluation = _paired_evaluation(forecast, settlement, pairing)
    compared = control.register_forecast_paired_evaluation(conn, evaluation)
    assert compared["evaluated"] and len(compared["cell_comparisons"]) == 18
    direct = _attribution(forecast, settlement)
    self_review = deepcopy(direct)
    self_review["attribution_id"] = "ATTRIBUTION:SELF_REVIEW:REJECTED"
    self_review["reviewer_id"] = forecast["model_memory_mitigation"]["isolated_forecaster_id"]
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_error_attribution(conn, self_review)
    assert exc_info.value.code == "attribution_reviewer_not_independent"
    recorded = control.register_forecast_error_attribution(conn, direct)
    assert recorded["learning_authorization"] == "FORECAST_POLICY_DIRECT"
    assert control.read_active_forecast_learning_policies(conn, as_of="2022-12-31T00:00:00+00:00") == []
    active = control.read_active_forecast_learning_policies(conn, as_of="2023-01-01T00:00:00+00:00")
    assert [item["learning_scope"] for item in active] == ["CALIBRATION"]

    candidate = _attribution(forecast, settlement, scope="EVIDENCE_PRIORITY", evaluation=evaluation)
    candidate["attribution_id"] = "ATTRIBUTION:CANDIDATE:CONTROL"
    candidate["policy_change"]["change_id"] = "POLICY:CANDIDATE:V1"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_error_attribution(conn, candidate)
    assert exc_info.value.code == "attribution_invalid"
    assert [item["learning_scope"] for item in control.read_active_forecast_learning_policies(
        conn, as_of="2024-01-01T00:00:00+00:00",
    )] == ["CALIBRATION"]
    conn.close()


def test_v2_pairing_derives_company_time_holdout_from_frozen_training_program() -> None:
    conn = _conn()
    training_program.initialize(conn)
    universe, h1 = _universe_and_h1()
    _register_h1_receipt(conn, h1)
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    decision_contract = _contract(bootstrap)
    control.register_training_decision_contract(conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00")
    v2 = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:HOLDOUT:V3:BASE",
        decision_contract_ref={"contract_id": decision_contract["contract_id"], "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    control.register_forecast_outcome_measurement_contract(conn, measurement_contract, frozen_at="2021-01-02T00:00:00+00:00")
    forecast = _v3_forecast(v2, measurement_contract)
    control.register_company_state_forecast(conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2021-01-03T00:00:00+00:00")
    conn.execute(
        """INSERT INTO judgment_training_programs
               (program_id, program_state, method_version, method_scope, registered_at, method_frozen_at,
                method_freeze_recorded_at, sampling_policy_json, contract_ref)
               VALUES (?, 'ACTIVE', ?, 'BOUNDARY_ONLY', ?, ?, ?, '{}', 'synthetic:holdout-program')""",
        (
            "JTP:synthetic-forecast-holdout", "METHOD:TRAINING_ENHANCED:V1",
            "2021-01-01T00:00:00+00:00", "2021-01-03T00:00:00+00:00", "2021-01-03T01:00:00+00:00",
        ),
    )
    conn.execute(
        """INSERT INTO judgment_training_episodes
               (training_episode_id, program_id, case_id, company_id, company_cluster_id, industry_id,
                decision_domain, cutoff_at, outcome_not_before, lane, provenance_role, outcome_access,
                holdout_axis, artifacts_json)
               VALUES (?, ?, 'HOLDOUT:SYNTHETIC:FORECAST', ?, 'COMPANY:SYNTHETIC:HOLDOUT', 'SYNTHETIC',
                       'FORECAST', ?, '2022-01-01T00:00:00+00:00', 'HISTORICAL_HOLDOUT',
                       'HISTORICAL_SELF_REPLAY', 'PIT_OUTCOME_SEALED', 'COMPANY_AND_TIME', '{}')""",
        ("JTE:synthetic-forecast-holdout", "JTP:synthetic-forecast-holdout", forecast["company_id"], forecast["cutoff_at"]),
    )
    conn.commit()
    pairing = _pairing(forecast)
    pairing["schema_version"] = pit.PAIRING_SCHEMA_VERSION_V2
    pairing["holdout_binding"] = {
        "program_id": "JTP:synthetic-forecast-holdout",
        "holdout_training_episode_id": "JTE:synthetic-forecast-holdout",
        "evaluated_cell_refs": [{"dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR"}],
    }
    assert control.register_forecast_method_pairing(conn, pairing, frozen_at="2021-01-03T12:00:00+00:00")["frozen"]
    stored = json.loads(conn.execute(
        f"SELECT payload_json FROM {control.PAIRING_TABLE} WHERE pairing_id = ?", (pairing["pairing_id"],),
    ).fetchone()[0])
    assert stored["holdout_binding"]["company_cluster_id"] == "COMPANY:SYNTHETIC:HOLDOUT"
    assert stored["holdout_binding"]["evaluated_cells"] == [{
        "dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR", "outcome_period_end": "2021-12-31",
    }]
    wrong_method = deepcopy(pairing)
    wrong_method["pairing_id"] = "PAIRING:SYNTHETIC:HOLDOUT:WRONG-METHOD"
    wrong_method["enhanced_method_id"] = "METHOD:OTHER"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_method_pairing(conn, wrong_method, frozen_at="2021-01-03T12:00:00+00:00")
    assert exc_info.value.code == "pairing_holdout_method_version_mismatch"
    late_pairing = deepcopy(pairing)
    late_pairing["pairing_id"] = "PAIRING:SYNTHETIC:HOLDOUT:LATE"
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_forecast_method_pairing(conn, late_pairing, frozen_at="2022-01-01T00:00:00+00:00")
    assert exc_info.value.code == "pairing_must_precede_holdout_outcome_window"
    conn.close()


def test_current_mechanism_signal_shadow_is_persisted_without_forecast_or_outcome() -> None:
    conn = _conn()
    root = Path(__file__).resolve().parents[1]
    with (root / "docs/development/research/cohorts/SHADOW_R05_SBUX_NA_TRANSACTION_DURABILITY_20260821.json").open(encoding="utf-8") as handle:
        shadow = json.load(handle)
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_prospective_signal_shadow_episode(
            conn, shadow, registered_at="2026-08-25T00:00:00+08:00",
        )
    assert exc_info.value.code == "signal_source_freeze_not_registered"
    assert control.register_prospective_signal_source_freeze(
        conn, shadow["source_freeze_ref"], registered_at="2026-08-25T00:00:00+08:00",
    )["registered"]
    source_drift = deepcopy(shadow)
    source_drift["shadow_episode_id"] = "SHADOW:R05:SYNTHETIC:SOURCE-DRIFT"
    source_drift["source_freeze_ref"]["allowed_source_ids"].append("STATIC:UNDECLARED")
    with pytest.raises(control.ForecastControlError) as exc_info:
        control.register_prospective_signal_shadow_episode(
            conn, source_drift, registered_at="2026-08-25T00:00:00+08:00",
        )
    assert exc_info.value.code == "signal_source_freeze_mismatch"
    first = control.register_prospective_signal_shadow_episode(
        conn, shadow, registered_at="2026-08-25T00:00:00+08:00",
    )
    replay = control.register_prospective_signal_shadow_episode(
        conn, deepcopy(shadow), registered_at="2026-08-25T00:00:00+08:00",
    )
    assert first["registered"] and not first["idempotent"]
    assert replay["registered"] and replay["idempotent"]
    assert conn.execute(f"SELECT COUNT(*) FROM {control.FORECAST_TABLE}").fetchone()[0] == 0
    assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
    conn.close()
