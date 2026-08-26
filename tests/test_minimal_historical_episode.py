from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import minimal_historical_episode as episode
from scripts import minimal_historical_episode_control_plane as control


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    control.initialize(conn)
    return conn


def _contract() -> dict:
    return {
        "schema_version": episode.MEASUREMENT_CONTRACT_SCHEMA_VERSION,
        "measurement_contract_id": "MHE:CONTRACT:SYNTHETIC:V1",
        "measurement_contract_version": 1,
        "company_id": "SYNTHETIC:COMPANY:ONE",
        "issuer_id": "SYNTHETIC:ISSUER:ONE",
        "cutoff_at": "2020-12-31T23:59:59+00:00",
        "metric_id": "OPERATING_MARGIN",
        "window_id": "ONE_YEAR",
        "outcome_period_end": "2021-12-31",
        "responsibility_boundary": "LISTED_ISSUER_CONSOLIDATED",
        "unit": "PERCENT",
        "settlement_tolerance": 0.5,
        "roles": {
            "forecaster_id": "SYNTHETIC:FORECASTER",
            "custodian_id": "SYNTHETIC:CUSTODIAN",
        },
        "object_class": "MINIMAL_HISTORICAL_MEASUREMENT_CONTRACT",
        "claim_class": "ONE_METRIC_PRE_OUTCOME_SCOPE",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _contract_ref(contract: dict) -> dict:
    return {
        "measurement_contract_id": contract["measurement_contract_id"],
        "measurement_contract_version": contract["measurement_contract_version"],
    }


def _static_evidence(contract: dict) -> dict:
    return {
        "schema_version": episode.STATIC_EVIDENCE_SCHEMA_VERSION,
        "evidence_receipt_id": "MHE:EVIDENCE:SYNTHETIC:V1",
        "evidence_receipt_version": 1,
        "measurement_contract_ref": _contract_ref(contract),
        "company_id": contract["company_id"],
        "issuer_id": contract["issuer_id"],
        "cutoff_at": contract["cutoff_at"],
        "metric_id": contract["metric_id"],
        "window_id": contract["window_id"],
        "curator_id": "SYNTHETIC:CURATOR",
        "source": {
            "source_id": "SYNTHETIC:STATIC:2020",
            "source_url": "https://official.example.invalid/synthetic/pre-cutoff.pdf",
            "source_type": episode.OFFICIAL_STATIC_FILING,
            "published_at": "2020-03-31",
            "issuer_id": contract["issuer_id"],
            "metric_id": contract["metric_id"],
            "responsibility_boundary": contract["responsibility_boundary"],
            "unit": contract["unit"],
            "field_ref": "Synthetic official filing p12.",
            "numeric_value": 10.0,
        },
        "object_class": "MINIMAL_HISTORICAL_STATIC_EVIDENCE",
        "claim_class": "CUTOFF_VISIBLE_OFFICIAL_FIELD",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _prediction(contract: dict, evidence: dict) -> dict:
    return {
        "schema_version": episode.PREDICTION_SCHEMA_VERSION,
        "prediction_id": "MHE:PREDICTION:SYNTHETIC:V1",
        "measurement_contract_ref": _contract_ref(contract),
        "evidence_receipt_ref": {
            "evidence_receipt_id": evidence["evidence_receipt_id"],
            "evidence_receipt_version": evidence["evidence_receipt_version"],
        },
        "company_id": contract["company_id"],
        "issuer_id": contract["issuer_id"],
        "cutoff_at": contract["cutoff_at"],
        "metric_id": contract["metric_id"],
        "window_id": contract["window_id"],
        "forecaster_id": contract["roles"]["forecaster_id"],
        "predicted_direction": "INCREASE",
        "object_class": "MINIMAL_HISTORICAL_PREDICTION",
        "claim_class": "ONE_METRIC_DIRECTIONAL_PREDICTION",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _access(contract: dict) -> dict:
    return {
        "schema_version": episode.OUTCOME_ACCESS_SCHEMA_VERSION,
        "authorization_id": "MHE:ACCESS:SYNTHETIC:V1",
        "measurement_contract_ref": _contract_ref(contract),
        "custodian_id": contract["roles"]["custodian_id"],
        "authorized_at": "2022-03-31T00:00:00+00:00",
        "object_class": "MINIMAL_HISTORICAL_OUTCOME_ACCESS",
        "claim_class": "CUSTODIAN_CONTRACT_ONLY_ACCESS",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _observation(contract: dict) -> dict:
    return {
        "schema_version": episode.OBSERVATION_SCHEMA_VERSION,
        "observation_id": "MHE:OBSERVATION:SYNTHETIC:V1",
        "measurement_contract_ref": _contract_ref(contract),
        "company_id": contract["company_id"],
        "issuer_id": contract["issuer_id"],
        "cutoff_at": contract["cutoff_at"],
        "metric_id": contract["metric_id"],
        "window_id": contract["window_id"],
        "custodian_id": contract["roles"]["custodian_id"],
        "observed_at": "2022-04-01T00:00:00+00:00",
        "source": {
            "source_id": "SYNTHETIC:OUTCOME:2021",
            "source_url": "https://official.example.invalid/synthetic/outcome.pdf",
            "source_type": episode.OFFICIAL_STATIC_FILING,
            "source_available_at": "2022-03-30T00:00:00+00:00",
            "issuer_id": contract["issuer_id"],
            "metric_id": contract["metric_id"],
            "responsibility_boundary": contract["responsibility_boundary"],
            "unit": contract["unit"],
            "field_ref": "Synthetic official filing p38.",
            "numeric_value": 11.0,
        },
        "object_class": "MINIMAL_HISTORICAL_OUTCOME_OBSERVATION",
        "claim_class": "CUSTODIAN_OBSERVED_OFFICIAL_FIELD",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _settlement_request(contract: dict) -> dict:
    return {
        "schema_version": episode.SETTLEMENT_REQUEST_SCHEMA_VERSION,
        "settlement_id": "MHE:SETTLEMENT:SYNTHETIC:V1",
        "measurement_contract_ref": _contract_ref(contract),
        "custodian_id": contract["roles"]["custodian_id"],
        "settled_at": "2022-04-02T00:00:00+00:00",
        "object_class": "MINIMAL_HISTORICAL_SETTLEMENT_REQUEST",
        "claim_class": "CUSTODIAN_MECHANICAL_SETTLEMENT_REQUEST",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _frozen_chain() -> tuple[sqlite3.Connection, dict, dict, dict]:
    conn = _conn()
    contract = _contract()
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    assert control.register_measurement_contract(conn, contract, frozen_at="2021-01-02T00:00:00+00:00")["frozen"]
    assert control.register_static_evidence(conn, evidence, frozen_at="2021-01-03T00:00:00+00:00")["frozen"]
    assert control.register_prediction(conn, prediction, frozen_at="2021-01-04T00:00:00+00:00")["frozen"]
    return conn, contract, evidence, prediction


def test_one_metric_fixture_chain_is_contract_only_for_custodian_and_mechanically_settles() -> None:
    conn, contract, _, _ = _frozen_chain()
    try:
        access = _access(contract)
        assert set(access) == {
            "schema_version", "authorization_id", "measurement_contract_ref", "custodian_id", "authorized_at",
            "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
        }
        assert control.authorize_outcome_access(conn, access) == {
            "authorized": True,
            "authorization_id": access["authorization_id"],
            "idempotent": False,
        }
        stored_access = json.loads(conn.execute(
            f"SELECT payload_json FROM {control.ACCESS_TABLE} WHERE authorization_id = ?", (access["authorization_id"],),
        ).fetchone()[0])
        assert stored_access == access
        assert "prediction_id" not in stored_access and "predicted_direction" not in stored_access
        observation = _observation(contract)
        assert control.register_observation(conn, observation)["recorded"]
        result = control.settle(conn, _settlement_request(contract))
        assert result["settled"] and result["settlement"]["status"] == "MATCH"
        assert result["settlement"] == {
            "schema_version": episode.SETTLEMENT_SCHEMA_VERSION,
            "settlement_id": "MHE:SETTLEMENT:SYNTHETIC:V1",
            "measurement_contract_ref": _contract_ref(contract),
            "prediction_id": "MHE:PREDICTION:SYNTHETIC:V1",
            "observation_id": "MHE:OBSERVATION:SYNTHETIC:V1",
            "custodian_id": "SYNTHETIC:CUSTODIAN",
            "settled_at": "2022-04-02T00:00:00+00:00",
            "status": "MATCH",
            "object_class": "MINIMAL_HISTORICAL_MECHANICAL_SETTLEMENT",
            "claim_class": "ONE_METRIC_MECHANICAL_RESULT",
            "allowed_outputs": ["MECHANICAL_SETTLEMENT_ONLY"],
            "method_transfer_rights": "NO_METHOD_TRANSFER_RIGHTS",
        }
        assert conn.execute(f"SELECT COUNT(*) FROM {control.PREDICTION_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 1
    finally:
        conn.close()


def test_static_evidence_rejects_nonstatic_late_or_identity_drift() -> None:
    contract = _contract()
    evidence = _static_evidence(contract)
    for mutate, expected in (
        (lambda value: value["source"].update({"source_type": "NEWS"}), "static_evidence.source.source_type_must_be_official_static_filing"),
        (lambda value: value["source"].update({"published_at": "2020-12-31"}), "static_evidence.source.published_at_must_precede_cutoff"),
        (lambda value: value.update({"issuer_id": "SYNTHETIC:ISSUER:OTHER"}), "static_evidence.issuer_id_must_match_measurement_contract"),
        (lambda value: value["source"].update({"metric_id": "OTHER_OPERATING_METRIC"}), "static_evidence.source.metric_id_must_match_measurement_contract"),
    ):
        invalid = deepcopy(evidence)
        mutate(invalid)
        result = episode.validate_static_evidence(invalid, measurement_contract=contract)
        assert not result["valid"]
        assert expected in result["findings"]


def test_roles_and_fixed_permissions_are_closed_before_persistence() -> None:
    contract = _contract()
    role_collision = deepcopy(contract)
    role_collision["roles"]["custodian_id"] = role_collision["roles"]["forecaster_id"]
    result = episode.validate_measurement_contract(role_collision)
    assert not result["valid"]
    assert "measurement_contract.roles_must_be_independent" in result["findings"]

    curator_collision = _static_evidence(contract)
    curator_collision["curator_id"] = contract["roles"]["forecaster_id"]
    result = episode.validate_static_evidence(curator_collision, measurement_contract=contract)
    assert not result["valid"]
    assert "static_evidence.curator_must_be_independent_from_forecaster_and_custodian" in result["findings"]

    payload = _access(contract)
    payload["predicted_direction"] = "INCREASE"
    result = episode.validate_outcome_access(payload, measurement_contract=contract)
    assert not result["valid"]
    assert "outcome_access_contains_unapproved_field:predicted_direction" in result["findings"]
    assert "outcome_access" not in payload

    permission_drift = _prediction(contract, _static_evidence(contract))
    permission_drift["method_transfer_rights"] = "TRANSFER_ALLOWED"
    result = episode.validate_prediction(
        permission_drift, measurement_contract=contract, static_evidence=_static_evidence(contract),
    )
    assert not result["valid"]
    assert "prediction.method_transfer_rights_must_be_no_method_transfer_rights" in result["findings"]


def test_control_plane_rejects_wrong_chain_time_and_observation_measurement_mismatch() -> None:
    conn, contract, _, prediction = _frozen_chain()
    try:
        second_prediction = deepcopy(prediction)
        second_prediction["prediction_id"] = "MHE:PREDICTION:SYNTHETIC:SECOND"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_prediction(conn, second_prediction, frozen_at="2021-01-05T00:00:00+00:00")
        assert exc_info.value.code == "measurement_contract_prediction_already_frozen"

        too_early = _access(contract)
        too_early["authorized_at"] = "2021-01-04T00:00:00+00:00"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.authorize_outcome_access(conn, too_early)
        assert exc_info.value.code == "outcome_access_must_follow_prediction"

        assert control.authorize_outcome_access(conn, _access(contract))["authorized"]
        mismatch = _observation(contract)
        mismatch["source"]["unit"] = "RMB"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_observation(conn, mismatch)
        assert exc_info.value.code == "observation_invalid"
        assert "observation.source.unit_must_match_measurement_contract" in exc_info.value.detail

        early_observation = _observation(contract)
        early_observation["observed_at"] = "2022-03-30T00:00:00+00:00"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_observation(conn, early_observation)
        assert exc_info.value.code == "observation_must_follow_outcome_access"
    finally:
        conn.close()


@pytest.mark.parametrize("stage", ["baseline", "outcome"])
def test_source_metric_mismatch_is_rejected_before_persistence_or_settlement(stage: str) -> None:
    if stage == "baseline":
        conn = _conn()
        contract = _contract()
        try:
            assert control.register_measurement_contract(
                conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
            )["frozen"]
            evidence = _static_evidence(contract)
            evidence["source"]["metric_id"] = "OTHER_OPERATING_METRIC"
            with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
                control.register_static_evidence(conn, evidence, frozen_at="2021-01-03T00:00:00+00:00")
            assert exc_info.value.code == "static_evidence_invalid"
            assert "static_evidence.source.metric_id_must_match_measurement_contract" in exc_info.value.detail
            assert conn.execute(f"SELECT COUNT(*) FROM {control.EVIDENCE_TABLE}").fetchone()[0] == 0
            assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
        finally:
            conn.close()
        return

    conn, contract, _, _ = _frozen_chain()
    try:
        assert control.authorize_outcome_access(conn, _access(contract))["authorized"]
        observation = _observation(contract)
        observation["source"]["metric_id"] = "OTHER_OPERATING_METRIC"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_observation(conn, observation)
        assert exc_info.value.code == "observation_invalid"
        assert "observation.source.metric_id_must_match_measurement_contract" in exc_info.value.detail
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OBSERVATION_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("stage", "numeric_value"),
    [
        pytest.param("baseline", float("nan"), id="baseline-nan"),
        pytest.param("outcome", float("inf"), id="outcome-positive-infinity"),
        pytest.param("outcome", float("-inf"), id="outcome-negative-infinity"),
    ],
)
def test_nonfinite_numeric_values_are_rejected_before_persistence_or_settlement(
    stage: str, numeric_value: float,
) -> None:
    if stage == "baseline":
        conn = _conn()
        contract = _contract()
        try:
            assert control.register_measurement_contract(
                conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
            )["frozen"]
            evidence = _static_evidence(contract)
            evidence["source"]["numeric_value"] = numeric_value
            with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
                control.register_static_evidence(conn, evidence, frozen_at="2021-01-03T00:00:00+00:00")
            assert exc_info.value.code == "static_evidence_invalid"
            assert "static_evidence.source.numeric_value_must_be_finite_numeric" in exc_info.value.detail
            assert conn.execute(f"SELECT COUNT(*) FROM {control.EVIDENCE_TABLE}").fetchone()[0] == 0
            assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
        finally:
            conn.close()
        return

    conn, contract, _, _ = _frozen_chain()
    try:
        assert control.authorize_outcome_access(conn, _access(contract))["authorized"]
        observation = _observation(contract)
        observation["source"]["numeric_value"] = numeric_value
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_observation(conn, observation)
        assert exc_info.value.code == "observation_invalid"
        assert "observation.source.numeric_value_must_be_finite_numeric" in exc_info.value.detail
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OBSERVATION_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_public_schema_keeps_the_contract_only_access_and_no_transfer_rights() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas" / "minimal_historical_episode.schema.json").read_text(encoding="utf-8"))
    access = schema["$defs"]["outcome_access"]
    assert set(access["properties"]) == {
        "schema_version", "authorization_id", "measurement_contract_ref", "custodian_id", "authorized_at",
        "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
    }
    for name in ("measurement_contract", "static_evidence", "prediction", "outcome_access", "observation", "settlement_request", "settlement"):
        properties = schema["$defs"][name]["properties"]
        assert properties["allowed_outputs"]["const"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert properties["method_transfer_rights"]["const"] == "NO_METHOD_TRANSFER_RIGHTS"
    serialized = json.dumps(schema)
    assert "turtle-pit-company-state-forecast" not in serialized
    assert "turtle-pit-forecast-pairing" not in serialized
