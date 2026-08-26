from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from scripts import minimal_historical_episode as episode
from scripts import minimal_historical_episode_control_plane as control
from scripts import minimal_historical_episode_runner as runner


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    control.initialize(conn)
    return conn


def _decision_contract() -> dict:
    return {
        "schema_version": episode.DECISION_CONTRACT_SCHEMA_VERSION,
        "decision_contract_id": "MHE:DECISION:SYNTHETIC:V1",
        "decision_contract_version": 1,
        "company_id": "SYNTHETIC:COMPANY:ONE",
        "issuer_id": "SYNTHETIC:ISSUER:ONE",
        "cutoff_at": "2020-12-31T23:59:59+00:00",
        "metric_id": "OPERATING_MARGIN",
        "window_id": "ONE_YEAR",
        "decision_purpose": episode.DECISION_PURPOSE,
        "roles": {
            "forecaster_id": "SYNTHETIC:FORECASTER",
            "custodian_id": "SYNTHETIC:CUSTODIAN",
        },
        "object_class": "MINIMAL_HISTORICAL_DECISION_CONTRACT",
        "claim_class": "ONE_METRIC_DIRECTIONAL_DECISION_SCOPE",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _decision_contract_ref(decision_contract: dict) -> dict:
    return {
        "decision_contract_id": decision_contract["decision_contract_id"],
        "decision_contract_version": decision_contract["decision_contract_version"],
    }


def _contract(decision_contract: dict | None = None) -> dict:
    decision_contract = decision_contract or _decision_contract()
    return {
        "schema_version": episode.MEASUREMENT_CONTRACT_SCHEMA_VERSION,
        "measurement_contract_id": "MHE:CONTRACT:SYNTHETIC:V1",
        "measurement_contract_version": 1,
        "company_id": "SYNTHETIC:COMPANY:ONE",
        "issuer_id": "SYNTHETIC:ISSUER:ONE",
        "cutoff_at": "2020-12-31T23:59:59+00:00",
        "metric_id": "OPERATING_MARGIN",
        "window_id": "ONE_YEAR",
        "decision_contract_ref": _decision_contract_ref(decision_contract),
        "outcome_period_end": "2021-12-31",
        "responsibility_boundary": "LISTED_ISSUER_CONSOLIDATED",
        "unit": "PERCENT",
        "settlement_tolerance": 0.5,
        "roles": deepcopy(decision_contract["roles"]),
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
            "measurement_period_end": contract["outcome_period_end"],
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
    decision_contract = _decision_contract()
    contract = _contract(decision_contract)
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    assert control.register_decision_contract(
        conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
    )["frozen"]
    assert control.register_measurement_contract(conn, contract, frozen_at="2021-01-02T00:00:00+00:00")["frozen"]
    assert control.register_static_evidence(conn, evidence, frozen_at="2021-01-03T00:00:00+00:00")["frozen"]
    assert control.register_prediction(conn, prediction, frozen_at="2021-01-04T00:00:00+00:00")["frozen"]
    return conn, contract, evidence, prediction


def test_initialize_supports_a_vanilla_sqlite_connection_for_the_pre_outcome_chain() -> None:
    """Callers need not know that controller lookups use named sqlite rows."""
    conn = sqlite3.connect(":memory:")
    assert conn.row_factory is None
    control.initialize(conn)
    assert conn.row_factory is sqlite3.Row
    decision_contract = _decision_contract()
    contract = _contract(decision_contract)
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    try:
        assert control.register_decision_contract(
            conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        assert control.register_measurement_contract(
            conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
        )["frozen"]
        assert control.register_static_evidence(
            conn, evidence, frozen_at="2021-01-03T00:00:00+00:00",
        )["frozen"]
        assert control.register_prediction(
            conn, prediction, frozen_at="2021-01-04T00:00:00+00:00",
        )["frozen"]
        assert conn.execute(f"SELECT COUNT(*) FROM {control.PREDICTION_TABLE}").fetchone()[0] == 1
    finally:
        conn.close()


def test_measurement_contract_requires_a_prior_frozen_matching_decision_contract() -> None:
    conn = _conn()
    decision_contract = _decision_contract()
    contract = _contract(decision_contract)
    try:
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_measurement_contract(conn, contract, frozen_at="2021-01-02T00:00:00+00:00")
        assert exc_info.value.code == "decision_contract_not_found"
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 0

        assert control.register_decision_contract(
            conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        assert control.register_measurement_contract(
            conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
        )["frozen"]
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("field", "drifted_value", "expected"),
    [
        ("company_id", "SYNTHETIC:COMPANY:OTHER", "measurement_contract.company_id_must_match_decision_contract"),
        ("issuer_id", "SYNTHETIC:ISSUER:OTHER", "measurement_contract.issuer_id_must_match_decision_contract"),
        ("cutoff_at", "2020-12-30T23:59:59+00:00", "measurement_contract.cutoff_at_must_match_decision_contract"),
        ("metric_id", "OTHER_OPERATING_METRIC", "measurement_contract.metric_id_must_match_decision_contract"),
        ("window_id", "THREE_YEAR", "measurement_contract.window_id_must_match_decision_contract"),
    ],
)
def test_measurement_contract_rejects_decision_identity_drift(field: str, drifted_value: str, expected: str) -> None:
    conn = _conn()
    decision_contract = _decision_contract()
    contract = _contract(decision_contract)
    contract[field] = drifted_value
    try:
        assert control.register_decision_contract(
            conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_measurement_contract(conn, contract, frozen_at="2021-01-02T00:00:00+00:00")
        assert exc_info.value.code == "measurement_contract_invalid"
        assert expected in exc_info.value.detail
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_measurement_contract_rejects_decision_role_drift() -> None:
    conn = _conn()
    decision_contract = _decision_contract()
    contract = _contract(decision_contract)
    contract["roles"]["custodian_id"] = "SYNTHETIC:CUSTODIAN:OTHER"
    try:
        assert control.register_decision_contract(
            conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_measurement_contract(conn, contract, frozen_at="2021-01-02T00:00:00+00:00")
        assert exc_info.value.code == "measurement_contract_invalid"
        assert "measurement_contract.roles_must_match_decision_contract" in exc_info.value.detail
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_decision_contract_is_append_only_and_exact_replay_is_idempotent() -> None:
    conn = _conn()
    decision_contract = _decision_contract()
    try:
        assert control.register_decision_contract(
            conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
        ) == {
            "frozen": True,
            "decision_contract_id": decision_contract["decision_contract_id"],
            "idempotent": False,
        }
        assert control.register_decision_contract(
            conn, deepcopy(decision_contract), frozen_at="2021-01-01T00:00:00+00:00",
        )["idempotent"]

        modified = deepcopy(decision_contract)
        modified["roles"]["custodian_id"] = "SYNTHETIC:CUSTODIAN:OTHER"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_decision_contract(conn, modified, frozen_at="2021-01-01T00:00:00+00:00")
        assert exc_info.value.code == "decision_contract_immutable_conflict"

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                f"UPDATE {control.DECISION_CONTRACT_TABLE} SET payload_json = ?",
                ("{}",),
            )
    finally:
        conn.close()


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
        decision_contract = _decision_contract()
        contract = _contract(decision_contract)
        try:
            assert control.register_decision_contract(
                conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
            )["frozen"]
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


def test_outcome_source_period_mismatch_is_rejected_before_persistence_or_settlement() -> None:
    conn, contract, _, _ = _frozen_chain()
    try:
        assert control.authorize_outcome_access(conn, _access(contract))["authorized"]
        observation = _observation(contract)
        observation["source"]["measurement_period_end"] = "2020-12-31"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_observation(conn, observation)
        assert exc_info.value.code == "observation_invalid"
        assert (
            "observation.source.measurement_period_end_must_match_measurement_contract_outcome_period_end"
            in exc_info.value.detail
        )
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
        decision_contract = _decision_contract()
        contract = _contract(decision_contract)
        try:
            assert control.register_decision_contract(
                conn, decision_contract, frozen_at="2021-01-01T00:00:00+00:00",
            )["frozen"]
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
    decision = schema["$defs"]["decision_contract"]
    assert set(decision["properties"]) == {
        "schema_version", "decision_contract_id", "decision_contract_version", "company_id", "issuer_id",
        "cutoff_at", "metric_id", "window_id", "decision_purpose", "roles", "object_class", "claim_class",
        "allowed_outputs", "method_transfer_rights",
    }
    measurement = schema["$defs"]["measurement_contract"]
    assert measurement["properties"]["decision_contract_ref"] == {"$ref": "#/$defs/decision_contract_ref"}
    access = schema["$defs"]["outcome_access"]
    assert set(access["properties"]) == {
        "schema_version", "authorization_id", "measurement_contract_ref", "custodian_id", "authorized_at",
        "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
    }
    for name in ("decision_contract", "measurement_contract", "static_evidence", "prediction", "outcome_access", "observation", "settlement_request", "settlement"):
        properties = schema["$defs"][name]["properties"]
        assert properties["allowed_outputs"]["const"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert properties["method_transfer_rights"]["const"] == "NO_METHOD_TRANSFER_RIGHTS"
    serialized = json.dumps(schema)
    assert "turtle-pit-company-state-forecast" not in serialized
    assert "turtle-pit-forecast-pairing" not in serialized


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _source_verification(source: dict, *, subject_ref: dict) -> dict:
    return {
        "schema_version": runner.SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION,
        "subject_ref": subject_ref,
        "source_id": source["source_id"],
        "source_url": source["source_url"],
        "exact_quote": "本集团水泥和熟料合计净销量为2.95亿吨",
        "numeric_value": source["numeric_value"],
        "unit": source["unit"],
        "allowed_outputs": ["MECHANICAL_SETTLEMENT_ONLY"],
        "method_transfer_rights": "NO_METHOD_TRANSFER_RIGHTS",
    }


def _synthetic_source_verifier(source: dict, verification: dict) -> dict:
    return {
        "schema_version": runner.SOURCE_RECEIPT_SCHEMA_VERSION,
        "verification_state": "SYNTHETIC_TEST_DOUBLE",
        "subject_ref": verification["subject_ref"],
        "source_id": source["source_id"],
        "allowed_outputs": ["MECHANICAL_SETTLEMENT_ONLY"],
        "method_transfer_rights": "NO_METHOD_TRANSFER_RIGHTS",
    }


def test_persistent_runner_separates_preoutcome_and_custodian_phases(tmp_path: Path) -> None:
    contract = _contract()
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    database = tmp_path / "minimal-episode.db"
    evidence_verification = _source_verification(
        evidence["source"],
        subject_ref={
            "object_type": "STATIC_EVIDENCE",
            "object_id": evidence["evidence_receipt_id"],
            "object_version": evidence["evidence_receipt_version"],
        },
    )

    frozen = runner.freeze_preoutcome(
        database,
        contract_path=_write_json(tmp_path / "contract.json", contract),
        evidence_path=_write_json(tmp_path / "evidence.json", evidence),
        prediction_path=_write_json(tmp_path / "prediction.json", prediction),
        source_verification_path=_write_json(tmp_path / "evidence-verification.json", evidence_verification),
        source_verifier=_synthetic_source_verifier,
    )
    assert frozen["stage"] == "PRE_OUTCOME_FROZEN"
    assert database.is_file()
    chronology = frozen["recorded_chronology"]
    assert chronology["contract_frozen_at"] < chronology["evidence_frozen_at"] < chronology["prediction_frozen_at"]

    access = _access(contract)
    authorized = runner.controller_authorize_outcome(
        database, access_path=_write_json(tmp_path / "access.json", access),
    )
    assert authorized["authorized"]
    assert authorized["outcome_access"]["authorized_at"] != access["authorized_at"]
    settled = runner.controller_record_and_settle(
        database,
        outcome_access_authorization_id=access["authorization_id"],
        observation_path=_write_json(tmp_path / "observation.json", _observation(contract)),
        source_verification_path=_write_json(
            tmp_path / "observation-verification.json",
            _source_verification(
                _observation(contract)["source"],
                subject_ref={
                    "object_type": "OUTCOME_OBSERVATION",
                    "object_id": _observation(contract)["observation_id"],
                },
            ),
        ),
        settlement_id="MHE:SETTLEMENT:SYNTHETIC:V1",
        source_verifier=_synthetic_source_verifier,
    )
    assert settled["settlement"]["status"] == "MATCH"

    receipt = runner.public_receipt(
        database,
        measurement_contract_id=contract["measurement_contract_id"],
        measurement_contract_version=contract["measurement_contract_version"],
    )
    assert receipt["chronology"]["prediction"]["prediction_id"] == prediction["prediction_id"]
    assert receipt["chronology"]["outcome_access"]["authorization_id"] == access["authorization_id"]
    assert receipt["settlement"]["status"] == "MATCH"
    serialized = json.dumps(receipt)
    assert "predicted_direction" not in serialized
    assert "realised_direction" not in serialized
    assert receipt["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"


def test_runner_requires_stored_access_before_opening_observation_or_source_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing authorization cannot turn the runner into an outcome reader."""
    contract = _contract()
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    database = tmp_path / "minimal-episode.db"
    runner.freeze_preoutcome(
        database,
        contract_path=_write_json(tmp_path / "contract.json", contract),
        evidence_path=_write_json(tmp_path / "evidence.json", evidence),
        prediction_path=_write_json(tmp_path / "prediction.json", prediction),
        source_verification_path=_write_json(
            tmp_path / "evidence-verification.json",
            _source_verification(
                evidence["source"],
                subject_ref={
                    "object_type": "STATIC_EVIDENCE",
                    "object_id": evidence["evidence_receipt_id"],
                    "object_version": evidence["evidence_receipt_version"],
                },
            ),
        ),
        source_verifier=_synthetic_source_verifier,
    )
    reads: list[Path] = []
    verifications: list[dict] = []

    def forbidden_read(path: str | Path) -> dict:
        reads.append(Path(path))
        raise AssertionError("outcome payload was opened before stored authorization")

    def forbidden_verifier(source: dict, verification: dict) -> dict:
        verifications.append(verification)
        raise AssertionError("outcome source was verified before stored authorization")

    monkeypatch.setattr(runner, "_read_object", forbidden_read)
    with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
        runner.controller_record_and_settle(
            database,
            outcome_access_authorization_id="MHE:ACCESS:DOES-NOT-EXIST",
            observation_path=tmp_path / "outcome.json",
            source_verification_path=tmp_path / "source-verification.json",
            settlement_id="MHE:SETTLEMENT:SYNTHETIC:V1",
            source_verifier=forbidden_verifier,
        )
    assert exc_info.value.code == "outcome_access_not_authorized"
    assert reads == []
    assert verifications == []


def test_real_source_verifier_reads_only_declared_pdf_page_and_rejects_other_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quote = "本集团水泥和熟料合计净销量为2.95亿吨"
    source = {
        "source_id": "CNINFO:SYNTHETIC:PAGE2",
        "source_url": "https://static.cninfo.com.cn/finalpage/2020-01-01/SYNTHETIC.PDF",
        "field_ref": "Synthetic annual report, PDF p. 2: net sales volume",
        "numeric_value": 295000000,
        "unit": "tonnes",
    }
    verification = {
        "exact_quote": quote,
        "numeric_value": 295000000,
        "unit": "tonnes",
        "subject_ref": {"object_type": "OUTCOME_OBSERVATION", "object_id": "SYNTHETIC:OBSERVATION"},
    }

    class FakePdfResponse:
        def __enter__(self) -> "FakePdfResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def geturl(self) -> str:
            return source["source_url"]

        def read(self) -> bytes:
            return b"%PDF-synthetic-multi-page"

    selected_pages: list[tuple[str, str]] = []

    def fake_pdftotext(args: list[str], **_: object) -> SimpleNamespace:
        start = args[args.index("-f") + 1]
        end = args[args.index("-l") + 1]
        selected_pages.append((start, end))
        return SimpleNamespace(stdout=quote if start == end == "2" else "page one without field")

    monkeypatch.setattr(runner, "urlopen", lambda *_args, **_kwargs: FakePdfResponse())
    monkeypatch.setattr(runner.subprocess, "run", fake_pdftotext)

    receipt = runner.verify_official_pdf_source(source, verification)
    assert receipt["verification_state"] == "OPENED_OFFICIAL_PDF_FIELD_MATCHED"
    assert selected_pages == [("2", "2")]

    wrong_page = deepcopy(source)
    wrong_page["field_ref"] = "Synthetic annual report, PDF p. 1: net sales volume"
    with pytest.raises(ValueError, match="does not contain the exact cited field quote"):
        runner.verify_official_pdf_source(wrong_page, verification)
    assert selected_pages == [("2", "2"), ("1", "1")]


@pytest.mark.parametrize("field_ref", [None, "Synthetic annual report, page twenty-one", "PDF p. 1 and p. 2"])
def test_real_source_verifier_requires_one_parseable_declared_page(
    field_ref: object, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = {
        "source_id": "CNINFO:SYNTHETIC:BAD-PAGE",
        "source_url": "https://static.cninfo.com.cn/finalpage/2020-01-01/SYNTHETIC.PDF",
        "field_ref": field_ref,
        "numeric_value": 295000000,
        "unit": "tonnes",
    }
    verification = {
        "exact_quote": "本集团水泥和熟料合计净销量为2.95亿吨",
        "numeric_value": 295000000,
        "unit": "tonnes",
    }
    opened: list[bool] = []
    monkeypatch.setattr(runner, "urlopen", lambda *_args, **_kwargs: opened.append(True))

    with pytest.raises(ValueError, match="field_ref must declare one"):
        runner.verify_official_pdf_source(source, verification)
    assert opened == []


@pytest.mark.parametrize("stage", ["access", "observation"])
def test_persistent_runner_rejects_caller_authored_prediction_or_result_fields(
    tmp_path: Path, stage: str,
) -> None:
    contract = _contract()
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    database = tmp_path / "minimal-episode.db"
    runner.freeze_preoutcome(
        database,
        contract_path=_write_json(tmp_path / "contract.json", contract),
        evidence_path=_write_json(tmp_path / "evidence.json", evidence),
        prediction_path=_write_json(tmp_path / "prediction.json", prediction),
        source_verification_path=_write_json(
            tmp_path / "evidence-verification.json",
            _source_verification(
                evidence["source"],
                subject_ref={
                    "object_type": "STATIC_EVIDENCE",
                    "object_id": evidence["evidence_receipt_id"],
                    "object_version": evidence["evidence_receipt_version"],
                },
            ),
        ),
        source_verifier=_synthetic_source_verifier,
    )
    access = _access(contract)
    if stage == "access":
        access["predicted_direction"] = "INCREASE"
        with pytest.raises(ValueError, match="forbidden fields"):
            runner.controller_authorize_outcome(
                database, access_path=_write_json(tmp_path / "access.json", access),
            )
        return

    runner.controller_authorize_outcome(
        database, access_path=_write_json(tmp_path / "access.json", access),
    )
    observation = _observation(contract)
    observation["status"] = "MATCH"
    with pytest.raises(ValueError, match="caller-authored fields"):
        runner.controller_record_and_settle(
            database,
            outcome_access_authorization_id=access["authorization_id"],
            observation_path=_write_json(tmp_path / "observation.json", observation),
            source_verification_path=_write_json(
                tmp_path / "observation-verification.json",
                _source_verification(
                    observation["source"],
                    subject_ref={
                        "object_type": "OUTCOME_OBSERVATION",
                        "object_id": observation["observation_id"],
                    },
                ),
            ),
            settlement_id="MHE:SETTLEMENT:SYNTHETIC:V1",
            source_verifier=_synthetic_source_verifier,
        )


def test_real_runner_rejects_fixture_only_source_before_creating_database(tmp_path: Path) -> None:
    contract = _contract()
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    database = tmp_path / "minimal-episode.db"
    with pytest.raises(ValueError, match="official static.cninfo.com.cn"):
        runner.freeze_preoutcome(
            database,
            contract_path=_write_json(tmp_path / "contract.json", contract),
            evidence_path=_write_json(tmp_path / "evidence.json", evidence),
            prediction_path=_write_json(tmp_path / "prediction.json", prediction),
            source_verification_path=_write_json(
                tmp_path / "evidence-verification.json",
                _source_verification(
                    evidence["source"],
                    subject_ref={
                        "object_type": "STATIC_EVIDENCE",
                        "object_id": evidence["evidence_receipt_id"],
                        "object_version": evidence["evidence_receipt_version"],
                    },
                ),
            ),
        )
    assert not database.exists()


def test_official_source_quote_must_reconcile_to_declared_tonnes() -> None:
    verification = {
        "unit": "tonnes",
        "numeric_value": 295000000,
        "exact_quote": "本集团水泥和熟料合计净销量为2.95亿吨",
    }
    runner._verify_quote_value(verification)
    verification["numeric_value"] = 296000000
    with pytest.raises(ValueError, match="do not match"):
        runner._verify_quote_value(verification)


def test_source_verification_subject_must_match_frozen_object(tmp_path: Path) -> None:
    contract = _contract()
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    verification = _source_verification(
        evidence["source"],
        subject_ref={"object_type": "STATIC_EVIDENCE", "object_id": "WRONG", "object_version": 1},
    )
    with pytest.raises(ValueError, match="subject_ref must match"):
        runner.freeze_preoutcome(
            tmp_path / "minimal-episode.db",
            contract_path=_write_json(tmp_path / "contract.json", contract),
            evidence_path=_write_json(tmp_path / "evidence.json", evidence),
            prediction_path=_write_json(tmp_path / "prediction.json", prediction),
            source_verification_path=_write_json(tmp_path / "verification.json", verification),
            source_verifier=_synthetic_source_verifier,
        )
