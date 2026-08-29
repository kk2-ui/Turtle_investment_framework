from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from scripts import minimal_historical_episode as episode
from scripts import minimal_historical_episode_control_plane as control
from scripts import minimal_historical_episode_runner as runner
from scripts import minimal_historical_outcome_acquisition as outcome_acquisition
from scripts import minimal_historical_technical_route_identity as route_identity_adapter


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
        "company_id": "CN:600585",
        "issuer_id": "ISSUER:CN:600585",
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


def _technical_route_identity(decision_contract: dict) -> dict:
    code = decision_contract["company_id"].split(":", 1)[1]
    return {
        "schema_version": episode.TECHNICAL_ROUTE_IDENTITY_SCHEMA_VERSION,
        "technical_route_identity_id": f"MHE:ROUTE:{code}:SYNTHETIC:V1",
        "technical_route_identity_version": 1,
        "decision_contract_ref": _decision_contract_ref(decision_contract),
        "company_id": decision_contract["company_id"],
        "issuer_id": decision_contract["issuer_id"],
        "security_code": code,
        "organization_id": "SYNTHETIC-ORG",
        "resolver_endpoint": episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT,
        "resolver_version": episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION,
        "observed_at": "2021-01-01T12:00:00+00:00",
        "object_class": "MINIMAL_HISTORICAL_TECHNICAL_ROUTE_IDENTITY",
        "claim_class": "TECHNICAL_ROUTE_IDENTITY",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _synthetic_technical_route_resolver(security_code: str) -> dict:
    """Fixture resolver; production runner alone uses CNINFO's stock map."""
    return {"security_code": security_code, "organization_id": "SYNTHETIC-ORG"}


def _register_technical_route_identity(conn: sqlite3.Connection, decision_contract: dict) -> dict:
    route_identity = _technical_route_identity(decision_contract)
    assert control.register_technical_route_identity(
        conn, route_identity, frozen_at="2021-01-01T12:00:00+00:00",
    )["frozen"]
    return route_identity


def _contract(decision_contract: dict | None = None) -> dict:
    decision_contract = decision_contract or _decision_contract()
    route_identity = _technical_route_identity(decision_contract)
    return {
        "schema_version": episode.MEASUREMENT_CONTRACT_SCHEMA_VERSION,
        "measurement_contract_id": "MHE:CONTRACT:SYNTHETIC:V2",
        "measurement_contract_version": 2,
        "company_id": decision_contract["company_id"],
        "issuer_id": decision_contract["issuer_id"],
        "cutoff_at": "2020-12-31T23:59:59+00:00",
        "metric_id": "OPERATING_MARGIN",
        "window_id": "ONE_YEAR",
        "decision_contract_ref": _decision_contract_ref(decision_contract),
        "outcome_period_end": "2021-12-31",
        "responsibility_boundary": "LISTED_ISSUER_CONSOLIDATED",
        "unit": "PERCENT",
        "settlement_tolerance": 0.5,
        "technical_route_identity_ref": {
            "technical_route_identity_id": route_identity["technical_route_identity_id"],
            "technical_route_identity_version": route_identity["technical_route_identity_version"],
        },
        "outcome_acquisition_route": {
            "provider": episode.CNINFO_OUTCOME_ROUTE_PROVIDER,
            "provider_version": episode.CNINFO_OUTCOME_ROUTE_PROVIDER_VERSION,
            "security_code": decision_contract["company_id"].split(":", 1)[1],
            "organization_id": "SYNTHETIC-ORG",
            "tab_name": episode.CNINFO_OUTCOME_ROUTE_TAB,
            "announcement_category": episode.CNINFO_OUTCOME_ROUTE_CATEGORY,
            "begin_date": "2022-01-01",
            "end_date": "2022-12-31",
            "page_size": 30,
            "static_pdf_url_policy": episode.CNINFO_OUTCOME_ROUTE_URL_POLICY,
            "annual_report_version_policy": episode.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ORIGINAL_ONLY,
        },
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


def test_technical_route_identity_projects_only_code_org_and_resolver_provenance() -> None:
    decision = _decision_contract()
    result = route_identity_adapter.resolve_technical_route_identity(
        technical_route_identity_id="MHE:ROUTE:SYNTHETIC:V1",
        technical_route_identity_version=1,
        decision_contract=decision,
        observed_at="2021-01-01T12:00:00+00:00",
        resolver=lambda code: {"security_code": code, "organization_id": "SYNTHETIC-ORG"},
    )
    assert result["status"] == "TECHNICAL_ROUTE_IDENTITY_READY"
    receipt = result["technical_route_identity"]
    assert episode.validate_technical_route_identity(receipt, decision_contract=decision)["valid"]
    assert receipt["security_code"] == "600585"
    assert receipt["organization_id"] == "SYNTHETIC-ORG"
    assert receipt["resolver_endpoint"] == episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT
    assert receipt["resolver_version"] == episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION
    serialized = json.dumps(receipt)
    for forbidden in ("company_name", "name", "title", "announcement", "pdf", "body", "outcome", "price"):
        assert forbidden not in serialized.casefold()


@pytest.mark.parametrize(
    ("resolver", "rule"),
    [
        (lambda code: {"security_code": code, "organization_id": "SYNTHETIC-ORG", "company_name": "forbidden"}, "CNINFO_TECHNICAL_ROUTE_RESOLVER_RESPONSE_INVALID"),
        (lambda _code: {"security_code": "600000", "organization_id": "SYNTHETIC-ORG"}, "CNINFO_TECHNICAL_ROUTE_IDENTITY_MISMATCH"),
        (lambda _code: (_ for _ in ()).throw(RuntimeError("unavailable")), "CNINFO_TECHNICAL_ROUTE_RESOLVER_UNAVAILABLE"),
    ],
)
def test_technical_route_identity_resolver_failure_or_identity_drift_is_value_free_mismatch(
    resolver, rule: str,
) -> None:
    result = route_identity_adapter.resolve_technical_route_identity(
        technical_route_identity_id="MHE:ROUTE:SYNTHETIC:V1",
        technical_route_identity_version=1,
        decision_contract=_decision_contract(),
        observed_at="2021-01-01T12:00:00+00:00",
        resolver=resolver,
    )
    assert result["status"] == "MEASUREMENT_MISMATCH"
    assert result["mismatch_rule"] == rule
    assert "technical_route_identity" not in result
    assert set(result) == {
        "schema_version", "status", "mismatch_rule", "mismatch_detail", "object_class", "claim_class",
        "allowed_outputs", "method_transfer_rights",
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
            "source_id": "CNINFO:600585:ANN:20220330:SYNTHETIC-2021-ANNUAL",
            "source_url": "https://static.cninfo.com.cn/finalpage/2022-03-30/SYNTHETIC.PDF",
            "source_type": episode.OFFICIAL_STATIC_FILING,
            "source_available_at": "2022-03-30",
            "source_available_precision": "DATE_ONLY",
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


def _field_ready_inventory(contract: dict, observation: dict | None = None) -> dict:
    observation = observation or _observation(contract)
    source = {
        key: value for key, value in observation["source"].items()
        if key != "numeric_value"
    }
    return {
        "schema_version": episode.OUTCOME_SOURCE_INVENTORY_SCHEMA_VERSION,
        "inventory_receipt_id": "MHE:INVENTORY:SYNTHETIC:V1",
        "measurement_contract_ref": _contract_ref(contract),
        "custodian_id": contract["roles"]["custodian_id"],
        "inventoried_at": "2022-03-31T00:00:01+00:00",
        "status": "FIELD_READY",
        "source": source,
        "object_class": "MINIMAL_HISTORICAL_OUTCOME_SOURCE_INVENTORY_RECEIPT",
        "claim_class": "CUSTODIAN_VALUE_FREE_SOURCE_READINESS",
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def _register_field_ready_inventory(conn: sqlite3.Connection, contract: dict) -> dict:
    inventory = _field_ready_inventory(contract)
    assert control.register_outcome_source_inventory(
        conn, inventory, inventoried_at=inventory["inventoried_at"],
    )["recorded"]
    return inventory


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
    _register_technical_route_identity(conn, decision_contract)
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
        _register_technical_route_identity(conn, decision_contract)
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
        _register_technical_route_identity(conn, decision_contract)
        assert control.register_measurement_contract(
            conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
        )["frozen"]
    finally:
        conn.close()


def test_v2_measurement_contract_requires_matching_frozen_technical_route_identity() -> None:
    conn = _conn()
    decision = _decision_contract()
    contract = _contract(decision)
    try:
        assert control.register_decision_contract(
            conn, decision, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_measurement_contract(
                conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
            )
        assert exc_info.value.code == "technical_route_identity_not_found"
        route_identity = _register_technical_route_identity(conn, decision)
        drifted = deepcopy(contract)
        drifted["outcome_acquisition_route"]["organization_id"] = "CALLER-OVERRIDE"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_measurement_contract(
                conn, drifted, frozen_at="2021-01-02T00:00:00+00:00",
            )
        assert exc_info.value.code == "measurement_contract_invalid"
        assert "measurement_contract.outcome_acquisition_route.organization_id_must_match_route_identity" in exc_info.value.detail
        assert control.register_measurement_contract(
            conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
        )["frozen"]
        assert route_identity["organization_id"] == contract["outcome_acquisition_route"]["organization_id"]
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
        inventory = _register_field_ready_inventory(conn, contract)
        assert inventory["status"] == "FIELD_READY"
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
        _register_field_ready_inventory(conn, contract)
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
            _register_technical_route_identity(conn, decision_contract)
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
        _register_field_ready_inventory(conn, contract)
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
        _register_field_ready_inventory(conn, contract)
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
            _register_technical_route_identity(conn, decision_contract)
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
        _register_field_ready_inventory(conn, contract)
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


def test_outcome_source_inventory_is_value_free_append_only_and_exact_replay_is_idempotent() -> None:
    conn, contract, _, _ = _frozen_chain()
    try:
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_outcome_source_inventory(
                conn, _field_ready_inventory(contract), inventoried_at="2022-03-31T00:00:01+00:00",
            )
        assert exc_info.value.code == "outcome_access_not_authorized"

        assert control.authorize_outcome_access(conn, _access(contract))["authorized"]
        inventory = _field_ready_inventory(contract)
        wrong_custodian = deepcopy(inventory)
        wrong_custodian["custodian_id"] = "SYNTHETIC:CUSTODIAN:OTHER"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_outcome_source_inventory(
                conn, wrong_custodian, inventoried_at=wrong_custodian["inventoried_at"],
            )
        assert exc_info.value.code == "outcome_source_inventory_invalid"
        assert "outcome_source_inventory.custodian_id_must_match_measurement_contract" in exc_info.value.detail
        inventory["source"]["numeric_value"] = 11.0
        invalid = episode.validate_outcome_source_inventory(inventory, measurement_contract=contract)
        assert not invalid["valid"]
        assert "outcome_source_inventory.source_contains_unapproved_field:numeric_value" in invalid["findings"]
        inventory["source"].pop("numeric_value")

        assert control.register_outcome_source_inventory(
            conn, inventory, inventoried_at=inventory["inventoried_at"],
        ) == {
            "recorded": True,
            "inventory_receipt_id": inventory["inventory_receipt_id"],
            "status": "FIELD_READY",
            "idempotent": False,
        }
        assert control.register_outcome_source_inventory(
            conn, deepcopy(inventory), inventoried_at=inventory["inventoried_at"],
        )["idempotent"]
        changed = deepcopy(inventory)
        changed["source"]["field_ref"] = "Synthetic official filing PDF p. 39."
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_outcome_source_inventory(
                conn, changed, inventoried_at=inventory["inventoried_at"],
            )
        assert exc_info.value.code == "outcome_source_inventory_immutable_conflict"
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(f"DELETE FROM {control.OUTCOME_SOURCE_INVENTORY_TABLE}")
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("source", "source_available_at"), "2020-12-31", "source_available_at_must_follow_cutoff"),
        (("source", "measurement_period_end"), "2020-12-31", "measurement_period_end_must_match_measurement_contract_outcome_period_end"),
        (("source", "source_url"), "https://static.cninfo.com.cn/not-finalpage/SYNTHETIC.PDF", "source_url_must_be_exact_static_cninfo_finalpage_pdf"),
        (("source", "field_ref"), "PDF p. 1 and p. 2", "field_ref_must_include_one_parseable_pdf_page"),
    ],
)
def test_field_ready_inventory_rejects_early_or_nonunique_source_identity(
    path: tuple[str, str], value: str, expected: str,
) -> None:
    contract = _contract()
    inventory = _field_ready_inventory(contract)
    inventory[path[0]][path[1]] = value
    result = episode.validate_outcome_source_inventory(inventory, measurement_contract=contract)
    assert not result["valid"]
    assert f"outcome_source_inventory.{path[0]}.{expected}" in result["findings"]


def test_measurement_mismatch_inventory_is_retained_but_blocks_observation_and_settlement() -> None:
    conn, contract, _, _ = _frozen_chain()
    try:
        assert control.authorize_outcome_access(conn, _access(contract))["authorized"]
        mismatch = {
            "schema_version": episode.OUTCOME_SOURCE_INVENTORY_SCHEMA_VERSION,
            "inventory_receipt_id": "MHE:INVENTORY:SYNTHETIC:MISMATCH",
            "measurement_contract_ref": _contract_ref(contract),
            "custodian_id": contract["roles"]["custodian_id"],
            "inventoried_at": "2022-03-31T00:00:01+00:00",
            "status": "MEASUREMENT_MISMATCH",
            "mismatch_rule": "DIRECT_FIELD_UNAVAILABLE",
            "mismatch_detail": "the official annual report does not expose one direct field under the frozen definition",
            "object_class": "MINIMAL_HISTORICAL_OUTCOME_SOURCE_INVENTORY_RECEIPT",
            "claim_class": "CUSTODIAN_VALUE_FREE_SOURCE_READINESS",
            "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
            "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
        }
        assert control.register_outcome_source_inventory(
            conn, mismatch, inventoried_at=mismatch["inventoried_at"],
        )["status"] == "MEASUREMENT_MISMATCH"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_observation(conn, _observation(contract))
        assert exc_info.value.code == "outcome_source_inventory_measurement_mismatch"
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.settle(conn, _settlement_request(contract))
        assert exc_info.value.code == "outcome_source_inventory_measurement_mismatch"
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OBSERVATION_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("source_id", "SYNTHETIC:OUTCOME:OTHER", "observation.source.source_id_must_match_field_ready_inventory"),
        ("field_ref", "Synthetic official filing PDF p. 39.", "observation.source.field_ref_must_match_field_ready_inventory"),
    ],
)
def test_observation_must_match_the_field_ready_inventory_exactly(
    field: str, value: str, expected: str,
) -> None:
    conn, contract, _, _ = _frozen_chain()
    try:
        assert control.authorize_outcome_access(conn, _access(contract))["authorized"]
        _register_field_ready_inventory(conn, contract)
        observation = _observation(contract)
        observation["source"][field] = value
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_observation(conn, observation)
        assert exc_info.value.code == "observation_invalid"
        assert expected in exc_info.value.detail
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
    assert measurement["properties"]["schema_version"] == {
        "const": "turtle-minimal-historical-episode-measurement-contract.v2",
    }
    assert measurement["properties"]["outcome_acquisition_route"] == {
        "$ref": "#/$defs/outcome_acquisition_route",
    }
    assert schema["$defs"]["measurement_contract_v1"]["properties"]["schema_version"] == {
        "const": "turtle-minimal-historical-episode-measurement-contract.v1",
    }
    assert schema["$defs"]["outcome_acquisition_route"]["properties"]["provider"] == {
        "const": "CNINFO_ANNOUNCEMENT_METADATA",
    }
    assert schema["$defs"]["outcome_acquisition_route"]["properties"]["annual_report_version_policy"] == {
        "enum": ["ORIGINAL_ONLY", "ONE_OFFICIAL_REVISED_VERSION_AFTER_ORIGINAL"],
    }
    access = schema["$defs"]["outcome_access"]
    assert set(access["properties"]) == {
        "schema_version", "authorization_id", "measurement_contract_ref", "custodian_id", "authorized_at",
        "object_class", "claim_class", "allowed_outputs", "method_transfer_rights",
    }
    inventory = schema["$defs"]["outcome_source_inventory"]
    assert "numeric_value" not in json.dumps(inventory)
    assert schema["$defs"]["source_verification_input"]["properties"]["unit"] == {
        "$ref": "#/$defs/nonempty",
    }
    assert schema["$defs"]["official_source_receipt"]["properties"]["unit"] == {
        "$ref": "#/$defs/nonempty",
    }
    for name in ("decision_contract", "measurement_contract", "static_evidence", "prediction", "outcome_access", "observation", "settlement_request", "settlement"):
        properties = schema["$defs"][name]["properties"]
        assert properties["allowed_outputs"]["const"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert properties["method_transfer_rights"]["const"] == "NO_METHOD_TRANSFER_RIGHTS"
    serialized = json.dumps(schema)
    assert "turtle-pit-company-state-forecast" not in serialized
    assert "turtle-pit-forecast-pairing" not in serialized


def test_fixture_only_v2_preoutcome_template_is_closed_and_route_bound() -> None:
    root = Path(__file__).resolve().parents[1]
    template = json.loads((
        root / "docs/development/research/cohorts/MINIMAL_HISTORICAL_EPISODE_V2_ROUTE_FIXTURE_TEMPLATE.json"
    ).read_text(encoding="utf-8"))
    assert template["template_kind"] == "MINIMAL_HISTORICAL_EPISODE_V2_PREOUTCOME_FIXTURE_ONLY"
    assert template["not_real_company_or_source"] is True
    decision = template["decision_contract"]
    contract = template["measurement_contract"]
    assert episode.validate_decision_contract(decision)["valid"]
    assert episode.validate_technical_route_identity(template["technical_route_identity"], decision_contract=decision)["valid"]
    assert episode.validate_measurement_contract(
        contract, decision_contract=decision, technical_route_identity=template["technical_route_identity"],
    )["valid"]
    assert episode.validate_static_evidence(template["static_evidence"], measurement_contract=contract)["valid"]
    assert episode.validate_prediction(
        template["prediction"], measurement_contract=contract, static_evidence=template["static_evidence"],
    )["valid"]


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
        technical_route_resolver=_synthetic_technical_route_resolver,
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
    inventory = _field_ready_inventory(contract)
    registered_inventory = runner.controller_acquire_and_register_outcome_source_inventory(
        database,
        outcome_access_authorization_id=access["authorization_id"],
        inventory_receipt_id=inventory["inventory_receipt_id"],
        field_locator=lambda *_: inventory["source"]["field_ref"],
        request=_cninfo_request([_cninfo_row()]),
    )
    assert registered_inventory["status"] == "FIELD_READY"
    assert runner.controller_acquire_and_register_outcome_source_inventory(
        database,
        outcome_access_authorization_id=access["authorization_id"],
        inventory_receipt_id=inventory["inventory_receipt_id"],
        field_locator=lambda *_: inventory["source"]["field_ref"],
        request=_cninfo_request([_cninfo_row()]),
    )["idempotent"]
    settled = runner.controller_record_and_settle(
        database,
        outcome_access_authorization_id=access["authorization_id"],
        outcome_source_inventory_receipt_id=inventory["inventory_receipt_id"],
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
    assert receipt["chronology"]["outcome_source_inventory"]["inventory_receipt_id"] == inventory["inventory_receipt_id"]
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
        technical_route_resolver=_synthetic_technical_route_resolver,
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
            outcome_source_inventory_receipt_id="MHE:INVENTORY:DOES-NOT-EXIST",
            observation_path=tmp_path / "outcome.json",
            source_verification_path=tmp_path / "source-verification.json",
            settlement_id="MHE:SETTLEMENT:SYNTHETIC:V1",
            source_verifier=forbidden_verifier,
        )
    assert exc_info.value.code == "outcome_access_not_authorized"
    assert reads == []
    assert verifications == []


def _cninfo_bound_contract_chain() -> tuple[dict, dict, dict]:
    decision = _decision_contract()
    decision["company_id"] = "CN:600585"
    decision["issuer_id"] = "ISSUER:CN:600585"
    contract = _contract(decision)
    contract["company_id"] = decision["company_id"]
    contract["issuer_id"] = decision["issuer_id"]
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    return contract, evidence, prediction


_CN600425_FY2017_OPERATING_REVENUE_QUOTE = (
    "其中：营业收入                         2,101,120,335.32 1,802,357,428.23"
)


def _cn600425_revenue_preoutcome_chain() -> tuple[dict, dict, dict, dict]:
    """The independent curator's result-free FY2017 static field, as test data."""
    decision = _decision_contract()
    decision.update({
        "decision_contract_id": "MHE:DECISION:CN600425:FY2017:V1",
        "company_id": "CN:600425",
        "issuer_id": "ISSUER:CN:600425",
        "cutoff_at": "2018-04-30T23:59:59+08:00",
        "metric_id": "ISSUER_CONSOLIDATED_OPERATING_REVENUE_RMB",
        "roles": {
            "forecaster_id": "FORECASTER:CN600425:PREOUTCOME:TEST",
            "custodian_id": "CUSTODIAN:CN600425:FUTURE:TEST",
        },
    })
    contract = _contract(decision)
    contract.update({
        "measurement_contract_id": "MHE:CONTRACT:CN600425:FY2018:V2",
        "measurement_contract_version": 2,
        "company_id": decision["company_id"],
        "issuer_id": decision["issuer_id"],
        "cutoff_at": decision["cutoff_at"],
        "metric_id": decision["metric_id"],
        "outcome_period_end": "2018-12-31",
        "responsibility_boundary": "LISTED_CONSOLIDATED_ISSUER",
        "unit": "RMB",
        "settlement_tolerance": 0.01,
        "roles": deepcopy(decision["roles"]),
        "outcome_acquisition_route": {
            "provider": episode.CNINFO_OUTCOME_ROUTE_PROVIDER,
            "provider_version": episode.CNINFO_OUTCOME_ROUTE_PROVIDER_VERSION,
            "security_code": "600425",
            "organization_id": "SYNTHETIC-ORG",
            "tab_name": episode.CNINFO_OUTCOME_ROUTE_TAB,
            "announcement_category": episode.CNINFO_OUTCOME_ROUTE_CATEGORY,
            "begin_date": "2019-01-01",
            "end_date": "2019-12-31",
            "page_size": 30,
            "static_pdf_url_policy": episode.CNINFO_OUTCOME_ROUTE_URL_POLICY,
            "annual_report_version_policy": episode.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ORIGINAL_ONLY,
        },
    })
    evidence = _static_evidence(contract)
    evidence.update({
        "evidence_receipt_id": "MHE:EVIDENCE:CN600425:FY2017:V1",
        "company_id": contract["company_id"],
        "issuer_id": contract["issuer_id"],
        "cutoff_at": contract["cutoff_at"],
        "metric_id": contract["metric_id"],
        "curator_id": "CURATOR:CN600425:REVENUE:TEST",
        "source": {
            "source_id": "CNINFO:600425:ANN:20180421:1204677754",
            "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-21/1204677754.PDF",
            "source_type": episode.OFFICIAL_STATIC_FILING,
            "published_at": "2018-04-21",
            "issuer_id": contract["issuer_id"],
            "metric_id": contract["metric_id"],
            "responsibility_boundary": contract["responsibility_boundary"],
            "unit": contract["unit"],
            "field_ref": (
                "FY2017 Xinjiang Tianshan Cement annual report, consolidated income statement, "
                "PDF p. 61, 营业收入."
            ),
            "numeric_value": 2101120335.32,
        },
    })
    prediction = _prediction(contract, evidence)
    prediction["prediction_id"] = "MHE:PREDICTION:CN600425:FY2018:V1"
    return decision, contract, evidence, prediction


def _rmb_source_verification(source: dict, *, subject_ref: dict) -> dict:
    return {
        "schema_version": runner.SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION,
        "subject_ref": subject_ref,
        "source_id": source["source_id"],
        "source_url": source["source_url"],
        "exact_quote": _CN600425_FY2017_OPERATING_REVENUE_QUOTE,
        "numeric_value": source["numeric_value"],
        "unit": source["unit"],
        "allowed_outputs": ["MECHANICAL_SETTLEMENT_ONLY"],
        "method_transfer_rights": "NO_METHOD_TRANSFER_RIGHTS",
    }


def test_real_runner_freezes_cn600425_rmb_revenue_preoutcome_chain_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock only the PDF transport: no outcome object is opened or written."""
    decision, contract, evidence, prediction = _cn600425_revenue_preoutcome_chain()
    database = tmp_path / "cn600425-minimal-episode.db"
    source_receipt_path = tmp_path / "cn600425-preoutcome-source-receipt.json"

    class FakePdfResponse:
        def __enter__(self) -> "FakePdfResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def geturl(self) -> str:
            return evidence["source"]["source_url"]

        def read(self) -> bytes:
            return b"%PDF-synthetic-cn600425-page-61"

    selected_pages: list[tuple[str, str]] = []

    def fake_pdftotext(args: list[str], **_: object) -> SimpleNamespace:
        start = args[args.index("-f") + 1]
        end = args[args.index("-l") + 1]
        selected_pages.append((start, end))
        return SimpleNamespace(stdout=_CN600425_FY2017_OPERATING_REVENUE_QUOTE)

    monkeypatch.setattr(runner, "urlopen", lambda *_args, **_kwargs: FakePdfResponse())
    monkeypatch.setattr(runner.subprocess, "run", fake_pdftotext)
    frozen = runner.freeze_preoutcome(
        database,
        decision_contract_path=_write_json(tmp_path / "decision.json", decision),
        technical_route_resolver=_synthetic_technical_route_resolver,
        contract_path=_write_json(tmp_path / "contract.json", contract),
        evidence_path=_write_json(tmp_path / "evidence.json", evidence),
        prediction_path=_write_json(tmp_path / "prediction.json", prediction),
        source_verification_path=_write_json(
            tmp_path / "evidence-verification.json",
            _rmb_source_verification(
                evidence["source"],
                subject_ref={
                    "object_type": "STATIC_EVIDENCE",
                    "object_id": evidence["evidence_receipt_id"],
                    "object_version": evidence["evidence_receipt_version"],
                },
            ),
        ),
        source_receipt_output_path=source_receipt_path,
    )
    assert frozen["stage"] == "PRE_OUTCOME_FROZEN"
    assert frozen["source_acquisition"]["unit"] == "RMB"
    assert selected_pages == [("61", "61")]
    assert json.loads(source_receipt_path.read_text(encoding="utf-8"))["numeric_value"] == 2101120335.32

    conn = sqlite3.connect(database)
    try:
        preoutcome_count = sum(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                control.DECISION_CONTRACT_TABLE,
                control.CONTRACT_TABLE,
                control.EVIDENCE_TABLE,
                control.PREDICTION_TABLE,
            )
        )
        outcome_count = sum(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                control.ACCESS_TABLE,
                control.OUTCOME_SOURCE_INVENTORY_TABLE,
                control.OBSERVATION_TABLE,
                control.SETTLEMENT_TABLE,
            )
        )
    finally:
        conn.close()
    assert preoutcome_count == 4
    assert outcome_count == 0


def test_runner_rejects_missing_v2_route_before_opening_the_static_source(tmp_path: Path) -> None:
    decision = _decision_contract()
    contract = _contract(decision)
    contract.pop("outcome_acquisition_route")
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    opened: list[bool] = []

    def forbidden_source_verifier(*_: object) -> dict:
        opened.append(True)
        raise AssertionError("route-less contract must fail before source verification")

    with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
        runner.freeze_preoutcome(
            tmp_path / "route-less.db",
            decision_contract_path=_write_json(tmp_path / "decision.json", decision),
            contract_path=_write_json(tmp_path / "contract.json", contract),
            evidence_path=_write_json(tmp_path / "evidence.json", evidence),
            prediction_path=_write_json(tmp_path / "prediction.json", prediction),
            source_verification_path=_write_json(
                tmp_path / "verification.json",
                _source_verification(
                    evidence["source"],
                    subject_ref={
                        "object_type": "STATIC_EVIDENCE",
                        "object_id": evidence["evidence_receipt_id"],
                        "object_version": evidence["evidence_receipt_version"],
                    },
                ),
            ),
            source_verifier=forbidden_source_verifier,
        )
    assert exc_info.value.code == "measurement_contract_invalid"
    assert "measurement_contract_missing_required_field:outcome_acquisition_route" in exc_info.value.detail
    assert opened == []


def _authorized_cninfo_database(
    tmp_path: Path, *, annual_report_version_policy: str | None = episode.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ORIGINAL_ONLY,
) -> tuple[Path, dict]:
    contract, evidence, prediction = _cninfo_bound_contract_chain()
    if annual_report_version_policy is None:
        contract["outcome_acquisition_route"].pop("annual_report_version_policy")
    else:
        contract["outcome_acquisition_route"]["annual_report_version_policy"] = annual_report_version_policy
    database = tmp_path / "cninfo-minimal-episode.db"
    runner.freeze_preoutcome(
        database,
        contract_path=_write_json(tmp_path / "contract.json", contract),
        technical_route_resolver=_synthetic_technical_route_resolver,
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
    runner.controller_authorize_outcome(
        database, access_path=_write_json(tmp_path / "access.json", access),
    )
    return database, contract


def _cninfo_row(
    *,
    title: str = "2021年年度报告",
    url: str = "finalpage/2022-03-30/SYNTHETIC.PDF",
    announcement_date: str = "2022-03-30",
    announcement_id: str = "SYNTHETIC-2021-ANNUAL",
) -> dict:
    return {
        "secCode": "600585",
        "orgId": "SYNTHETIC-ORG",
        "announcementTime": announcement_date,
        "announcementId": announcement_id,
        "announcementTitle": title,
        "adjunctUrl": url,
    }


def _cninfo_request(records: list[dict]) -> Callable[[dict[str, str]], dict]:
    def request(_: dict[str, str]) -> dict:
        return {"totalAnnouncement": len(records), "announcements": deepcopy(records)}
    return request


def test_custodian_acquisition_enumerates_one_contract_bound_static_annual_report(tmp_path: Path) -> None:
    database, contract = _authorized_cninfo_database(tmp_path)
    captured_params: list[dict[str, str]] = []

    def request(params: dict[str, str]) -> dict:
        captured_params.append(deepcopy(params))
        return _cninfo_request([_cninfo_row()])(params)

    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:V1",
        field_locator=lambda source, _: "FY2021 annual report, PDF p. 38",
        request=request,
    )
    assert candidate["status"] == "FIELD_READY"
    assert candidate["source"] == {
        "source_id": "CNINFO:600585:ANN:20220330:SYNTHETIC-2021-ANNUAL",
        "source_url": "https://static.cninfo.com.cn/finalpage/2022-03-30/SYNTHETIC.PDF",
        "source_type": "OFFICIAL_STATIC_FILING",
        "source_available_at": "2022-03-30",
        "source_available_precision": "DATE_ONLY",
        "issuer_id": contract["issuer_id"],
        "metric_id": contract["metric_id"],
        "measurement_period_end": contract["outcome_period_end"],
        "responsibility_boundary": contract["responsibility_boundary"],
        "unit": contract["unit"],
        "field_ref": "FY2021 annual report, PDF p. 38",
    }
    serialized = json.dumps(candidate)
    for forbidden in ("numeric_value", "exact_quote", "predicted_direction", "price", "cjo", "learning"):
        assert forbidden not in serialized
    assert captured_params == [{
        "stock": "600585,SYNTHETIC-ORG",
        "tabName": "fulltext",
        "pageSize": "30",
        "pageNum": "1",
        "column": "sse",
        "category": "",
        "plate": "sh",
        "seDate": "2022-01-01~2022-12-31",
        "searchkey": "",
        "secid": "",
        "sortName": "announcementTime",
        "sortType": "desc",
        "isHLtitle": "true",
    }]


@pytest.mark.parametrize(
    ("records", "locator", "rule"),
    [
        ([], None, "NO_UNIQUE_DIRECT_ANNUAL_REPORT"),
        ([_cninfo_row(), {**_cninfo_row(), "announcementId": "SYNTHETIC-SECOND"}], None, "NO_UNIQUE_DIRECT_ANNUAL_REPORT"),
        ([_cninfo_row(title="2021年年度报告摘要")], None, "NO_UNIQUE_DIRECT_ANNUAL_REPORT"),
        ([_cninfo_row(title="2021年年度报告（修订版）")], None, "ANNUAL_REPORT_VERSION_FAMILY_UNRESOLVED"),
        ([_cninfo_row(), {**_cninfo_row(title="2021年年度报告更正后"), "announcementId": "SYNTHETIC-REVISED"}], None, "ANNUAL_REPORT_VERSION_FAMILY_UNRESOLVED"),
        ([_cninfo_row(), {**_cninfo_row(title="关于撤销2021年年度报告的公告"), "announcementId": "SYNTHETIC-WITHDRAWN"}], None, "ANNUAL_REPORT_CANCELLATION_OR_WITHDRAWAL_UNRESOLVED"),
        ([_cninfo_row(), {**_cninfo_row(title="2021年年度报告已取消"), "announcementId": "SYNTHETIC-CANCELLED"}], None, "ANNUAL_REPORT_CANCELLATION_OR_WITHDRAWAL_UNRESOLVED"),
        ([_cninfo_row(), {**_cninfo_row(title="关于2021年年度报告作废的公告"), "announcementId": "SYNTHETIC-VOIDED"}], None, "ANNUAL_REPORT_CANCELLATION_OR_WITHDRAWAL_UNRESOLVED"),
        ([_cninfo_row(url="announcement/SYNTHETIC.PDF")], None, "ANNUAL_REPORT_NOT_STATIC_FINALPAGE"),
        ([_cninfo_row(title="2020年年度报告")], None, "NO_UNIQUE_DIRECT_ANNUAL_REPORT"),
        ([_cninfo_row()], None, "DIRECT_FIELD_PAGE_LOCATOR_UNAVAILABLE"),
    ],
)
def test_custodian_acquisition_returns_value_free_mismatch_for_nonunique_or_unusable_candidates(
    tmp_path: Path, records: list[dict], locator: object, rule: str,
) -> None:
    database, _ = _authorized_cninfo_database(tmp_path)
    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:MISMATCH",
        field_locator=locator if callable(locator) else None,
        request=_cninfo_request(records),
    )
    assert candidate["status"] == "MEASUREMENT_MISMATCH"
    assert candidate["mismatch_rule"] == rule
    assert "source" not in candidate and "numeric_value" not in json.dumps(candidate)


def test_custodian_acquisition_ignores_annual_report_summary_when_one_full_original_report_exists(
    tmp_path: Path,
) -> None:
    database, contract = _authorized_cninfo_database(tmp_path)
    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:FULL-ONLY",
        field_locator=lambda source, _: "FY2021 annual report, PDF p. 38",
        request=_cninfo_request([
            _cninfo_row(),
            {**_cninfo_row(title="2021年年度报告摘要"), "announcementId": "SYNTHETIC-SUMMARY"},
        ]),
    )
    assert candidate["status"] == "FIELD_READY"
    assert candidate["source"]["source_id"] == "CNINFO:600585:ANN:20220330:SYNTHETIC-2021-ANNUAL"
    assert candidate["source"]["issuer_id"] == contract["issuer_id"]


def test_custodian_acquisition_ignores_performance_meeting_notice_when_original_report_is_unique(
    tmp_path: Path,
) -> None:
    database, contract = _authorized_cninfo_database(tmp_path)
    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:REPORT-PLUS-MEETING",
        field_locator=lambda source, _: "FY2021 annual report, PDF p. 38",
        request=_cninfo_request([
            _cninfo_row(),
            {
                **_cninfo_row(
                    title="关于举行2021年年度报告网上业绩说明会的公告",
                    announcement_date="2022-04-08",
                    announcement_id="SYNTHETIC-PERFORMANCE-MEETING",
                    url="finalpage/2022-04-08/SYNTHETIC-PERFORMANCE-MEETING.PDF",
                ),
            },
        ]),
    )
    assert candidate["status"] == "FIELD_READY"
    assert candidate["source"]["source_id"] == "CNINFO:600585:ANN:20220330:SYNTHETIC-2021-ANNUAL"
    assert candidate["source"]["issuer_id"] == contract["issuer_id"]


def test_custodian_acquisition_keeps_legacy_default_closed_for_original_and_revised_family(
    tmp_path: Path,
) -> None:
    database, contract = _authorized_cninfo_database(tmp_path, annual_report_version_policy=None)
    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:LEGACY-DEFAULT",
        field_locator=lambda source, _: "FY2021 annual report, PDF p. 38",
        request=_cninfo_request([
            _cninfo_row(),
            _cninfo_row(
                title="2021年年度报告（修订版）",
                announcement_date="2022-04-20",
                announcement_id="SYNTHETIC-REVISED",
                url="finalpage/2022-04-20/SYNTHETIC-REVISED.PDF",
            ),
        ]),
    )
    assert "annual_report_version_policy" not in contract["outcome_acquisition_route"]
    assert candidate["status"] == "MEASUREMENT_MISMATCH"
    assert candidate["mismatch_rule"] == "ANNUAL_REPORT_VERSION_POLICY_MISMATCH"


def test_custodian_acquisition_selects_one_explicit_official_revised_version_and_retains_date_page_identity(
    tmp_path: Path,
) -> None:
    database, contract = _authorized_cninfo_database(
        tmp_path,
        annual_report_version_policy=episode.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ONE_REVISED_AFTER_ORIGINAL,
    )
    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:REVISED",
        field_locator=lambda source, _: "FY2021 annual report, PDF p. 38",
        request=_cninfo_request([
            _cninfo_row(),
            _cninfo_row(
                title="2021年年度报告（修订版）",
                announcement_date="2022-04-20",
                announcement_id="SYNTHETIC-REVISED",
                url="finalpage/2022-04-20/SYNTHETIC-REVISED.PDF",
            ),
            _cninfo_row(title="2021年年度报告摘要", announcement_id="SYNTHETIC-SUMMARY"),
        ]),
    )
    assert candidate["status"] == "FIELD_READY"
    assert candidate["source"] == {
        "source_id": "CNINFO:600585:ANN:20220420:SYNTHETIC-REVISED",
        "source_url": "https://static.cninfo.com.cn/finalpage/2022-04-20/SYNTHETIC-REVISED.PDF",
        "source_type": episode.OFFICIAL_STATIC_FILING,
        "source_available_at": "2022-04-20",
        "source_available_precision": "DATE_ONLY",
        "issuer_id": contract["issuer_id"],
        "metric_id": contract["metric_id"],
        "measurement_period_end": contract["outcome_period_end"],
        "responsibility_boundary": contract["responsibility_boundary"],
        "unit": contract["unit"],
        "field_ref": "FY2021 annual report, PDF p. 38",
    }


def test_custodian_acquisition_rejects_policy_mismatch_and_ambiguous_revised_family(
    tmp_path: Path,
) -> None:
    database, _ = _authorized_cninfo_database(
        tmp_path,
        annual_report_version_policy=episode.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ONE_REVISED_AFTER_ORIGINAL,
    )
    common = {
        "outcome_access_authorization_id": "MHE:ACCESS:SYNTHETIC:V1",
        "inventory_receipt_id": "MHE:INVENTORY:CNINFO:VERSION-MISMATCH",
        "field_locator": lambda source, _: "FY2021 annual report, PDF p. 38",
    }
    policy_mismatch = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database), request=_cninfo_request([_cninfo_row()]), **common,
    )
    assert policy_mismatch["status"] == "MEASUREMENT_MISMATCH"
    assert policy_mismatch["mismatch_rule"] == "ANNUAL_REPORT_VERSION_POLICY_MISMATCH"

    ambiguous = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        request=_cninfo_request([
            _cninfo_row(),
            _cninfo_row(
                title="2021年年度报告（修订版）",
                announcement_date="2022-04-20",
                announcement_id="SYNTHETIC-REVISED-ONE",
                url="finalpage/2022-04-20/SYNTHETIC-REVISED-ONE.PDF",
            ),
            _cninfo_row(
                title="2021年年度报告（修订版）",
                announcement_date="2022-04-21",
                announcement_id="SYNTHETIC-REVISED-TWO",
                url="finalpage/2022-04-21/SYNTHETIC-REVISED-TWO.PDF",
            ),
        ]),
        **{**common, "inventory_receipt_id": "MHE:INVENTORY:CNINFO:AMBIGUOUS"},
    )
    assert ambiguous["status"] == "MEASUREMENT_MISMATCH"
    assert ambiguous["mismatch_rule"] == "ANNUAL_REPORT_VERSION_FAMILY_UNRESOLVED"


@pytest.mark.parametrize(
    ("unresolved_title", "expected_rule"),
    [
        ("关于2021年年度报告作废的公告", "ANNUAL_REPORT_CANCELLATION_OR_WITHDRAWAL_UNRESOLVED"),
        ("2021年年度报告补充公告", "ANNUAL_REPORT_VERSION_FAMILY_UNRESOLVED"),
    ],
)
def test_custodian_acquisition_never_opens_a_revised_family_with_voided_or_unwhitelisted_member(
    tmp_path: Path, unresolved_title: str, expected_rule: str,
) -> None:
    database, _ = _authorized_cninfo_database(
        tmp_path,
        annual_report_version_policy=episode.CNINFO_ANNUAL_REPORT_VERSION_POLICY_ONE_REVISED_AFTER_ORIGINAL,
    )
    locator_calls: list[dict] = []
    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:UNRESOLVED-MEMBER",
        field_locator=lambda source, _: locator_calls.append(source) or "FY2021 annual report, PDF p. 38",
        request=_cninfo_request([
            _cninfo_row(),
            _cninfo_row(
                title="2021年年度报告（修订版）",
                announcement_date="2022-04-20",
                announcement_id="SYNTHETIC-REVISED",
                url="finalpage/2022-04-20/SYNTHETIC-REVISED.PDF",
            ),
            _cninfo_row(title=unresolved_title, announcement_id="SYNTHETIC-UNRESOLVED"),
        ]),
    )
    assert candidate["status"] == "MEASUREMENT_MISMATCH"
    assert candidate["mismatch_rule"] == expected_rule
    assert locator_calls == []
    assert "source" not in candidate


def test_custodian_acquisition_does_not_enumerate_before_stored_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    enumerated: list[bool] = []

    def forbidden_fetch(**_: object) -> dict:
        enumerated.append(True)
        raise AssertionError("CNINFO metadata was touched without access")

    monkeypatch.setattr(outcome_acquisition.phase10, "fetch_cninfo_announcement_records", forbidden_fetch)
    with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
        outcome_acquisition.acquire_cninfo_outcome_source_candidate(
            str(tmp_path / "missing.db"),
            outcome_access_authorization_id="MHE:ACCESS:MISSING",
            inventory_receipt_id="MHE:INVENTORY:MISSING",
        )
    assert exc_info.value.code == "outcome_access_not_authorized"
    assert enumerated == []


def test_inventory_and_acquisition_interfaces_never_accept_prediction_payloads() -> None:
    for function in (
        runner.controller_acquire_and_register_outcome_source_inventory,
        outcome_acquisition.acquire_cninfo_outcome_source_candidate,
    ):
        parameter_names = set(inspect.signature(function).parameters)
        assert "prediction" not in parameter_names
        assert "prediction_path" not in parameter_names
        assert "predicted_direction" not in parameter_names


def test_outcome_acquisition_interface_never_accepts_caller_route_drift() -> None:
    for function in (
        outcome_acquisition.acquire_cninfo_outcome_source_candidate,
        runner.controller_acquire_and_register_outcome_source_inventory,
    ):
        parameter_names = set(inspect.signature(function).parameters)
        assert {"cninfo_security_code", "cninfo_org_id", "begin_date", "end_date", "route", "inventory_path"}.isdisjoint(parameter_names)
    assert not hasattr(runner, "controller_register_outcome_source_inventory")
    with pytest.raises(SystemExit):
        runner._parser().parse_args([
            "controller-register-outcome-source-inventory",
            "--database", "synthetic.db",
        ])


def test_preoutcome_runner_derives_technical_route_identity_and_rejects_manual_override(
    tmp_path: Path,
) -> None:
    """No supported freeze input can inject a hand-authored orgId receipt."""
    contract = _contract()
    evidence = _static_evidence(contract)
    prediction = _prediction(contract, evidence)
    parameters = set(inspect.signature(runner.freeze_preoutcome).parameters)
    assert "technical_route_identity_path" not in parameters
    assert "organization_id" not in parameters
    with pytest.raises(SystemExit):
        runner._parser().parse_args([
            "freeze-preoutcome",
            "--database", "synthetic.db",
            "--technical-route-identity", "caller-authored.json",
        ])

    database = tmp_path / "route-override.db"
    with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
        runner.freeze_preoutcome(
            database,
            contract_path=_write_json(tmp_path / "contract.json", contract),
            evidence_path=_write_json(tmp_path / "evidence.json", evidence),
            prediction_path=_write_json(tmp_path / "prediction.json", prediction),
            source_verification_path=_write_json(
                tmp_path / "verification.json",
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
            technical_route_resolver=lambda code: {
                "security_code": code, "organization_id": "CALLER-OVERRIDE",
            },
        )
    assert exc_info.value.code == "measurement_contract_invalid"
    assert "organization_id_must_match_route_identity" in exc_info.value.detail
    conn = sqlite3.connect(database)
    try:
        control.initialize(conn)
        assert conn.execute(f"SELECT COUNT(*) FROM {control.TECHNICAL_ROUTE_IDENTITY_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.PREDICTION_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_runner_converts_outside_route_metadata_to_value_free_mismatch_before_observation(
    tmp_path: Path,
) -> None:
    database, contract = _authorized_cninfo_database(tmp_path)
    outside_route = _cninfo_row()
    outside_route["announcementTime"] = "2023-03-30"
    candidate = runner.controller_acquire_and_register_outcome_source_inventory(
        database,
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:OUTSIDE-ROUTE",
        field_locator=lambda *_: "PDF p. 38",
        request=_cninfo_request([outside_route]),
    )
    assert candidate["status"] == "MEASUREMENT_MISMATCH"
    assert candidate["outcome_source_inventory"]["mismatch_rule"] == "CNINFO_METADATA_ENUMERATION_INVALID"
    assert "source" not in candidate["outcome_source_inventory"]
    conn = sqlite3.connect(database)
    try:
        row = conn.execute(
            f"SELECT payload_json FROM {control.OUTCOME_SOURCE_INVENTORY_TABLE}"
        ).fetchone()
        assert row is not None
        assert "2023" not in row[0]
        assert "source" not in json.loads(row[0])
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OBSERVATION_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()
    with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
        runner.controller_record_and_settle(
            database,
            outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
            outcome_source_inventory_receipt_id="MHE:INVENTORY:CNINFO:OUTSIDE-ROUTE",
            observation_path=tmp_path / "not-read.json",
            source_verification_path=tmp_path / "not-read-verification.json",
            settlement_id="MHE:SETTLEMENT:OUTSIDE-ROUTE",
        )
    assert exc_info.value.code == "outcome_source_inventory_measurement_mismatch"
    assert candidate["outcome_source_inventory"]["measurement_contract_ref"] == _contract_ref(contract)


@pytest.mark.parametrize(
    ("route_field", "value", "expected"),
    [
        ("organization_id", "", "measurement_contract.outcome_acquisition_route.organization_id_required"),
        ("security_code", "600000", "measurement_contract.outcome_acquisition_route.security_code_must_match_company_id"),
        ("begin_date", "2021-12-31", "measurement_contract.outcome_acquisition_route.begin_date_must_follow_outcome_period_end"),
        ("annual_report_version_policy", "CALLER_SOURCE_SELECTION", "measurement_contract.outcome_acquisition_route.annual_report_version_policy_invalid"),
    ],
)
def test_v2_route_missing_or_mismatched_is_rejected_before_access(
    route_field: str, value: str, expected: str,
) -> None:
    conn = _conn()
    try:
        decision = _decision_contract()
        contract = _contract(decision)
        contract["outcome_acquisition_route"][route_field] = value
        assert control.register_decision_contract(
            conn, decision, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_measurement_contract(
                conn, contract, frozen_at="2021-01-02T00:00:00+00:00",
            )
        assert exc_info.value.code == "measurement_contract_invalid"
        assert expected in exc_info.value.detail
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.ACCESS_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_legacy_v1_measurement_contract_is_readable_history_but_cannot_open_new_custody() -> None:
    decision = _decision_contract()
    legacy = _contract(decision)
    legacy.update({
        "schema_version": episode.MEASUREMENT_CONTRACT_V1_SCHEMA_VERSION,
        "measurement_contract_id": "MHE:CONTRACT:SYNTHETIC:V1",
        "measurement_contract_version": 1,
    })
    legacy.pop("outcome_acquisition_route")
    legacy.pop("technical_route_identity_ref")
    assert episode.validate_measurement_contract(legacy, decision_contract=decision)["valid"]
    conn = _conn()
    try:
        assert control.register_decision_contract(
            conn, decision, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.register_measurement_contract(
                conn, legacy, frozen_at="2021-01-02T00:00:00+00:00",
            )
        assert exc_info.value.code == "measurement_contract_v2_required"
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_existing_v1_exact_replay_is_readable_but_cannot_authorize_new_access() -> None:
    decision = _decision_contract()
    legacy = _contract(decision)
    legacy.update({
        "schema_version": episode.MEASUREMENT_CONTRACT_V1_SCHEMA_VERSION,
        "measurement_contract_id": "MHE:CONTRACT:SYNTHETIC:LEGACY:V1",
        "measurement_contract_version": 1,
    })
    legacy.pop("outcome_acquisition_route")
    legacy.pop("technical_route_identity_ref")
    frozen_at = "2021-01-02T00:00:00+00:00"
    conn = _conn()
    try:
        assert control.register_decision_contract(
            conn, decision, frozen_at="2021-01-01T00:00:00+00:00",
        )["frozen"]
        conn.execute(
            f"""INSERT INTO {control.CONTRACT_TABLE} (
                measurement_contract_id, measurement_contract_version, decision_contract_id, decision_contract_version,
                company_id, issuer_id, cutoff_at, metric_id, window_id, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                legacy["measurement_contract_id"], legacy["measurement_contract_version"],
                decision["decision_contract_id"], decision["decision_contract_version"],
                legacy["company_id"], legacy["issuer_id"], legacy["cutoff_at"], legacy["metric_id"],
                legacy["window_id"], json.dumps(legacy, ensure_ascii=False, sort_keys=True, separators=(",", ":")), frozen_at,
            ),
        )
        assert control.register_measurement_contract(conn, legacy, frozen_at=frozen_at) == {
            "frozen": True,
            "measurement_contract_id": legacy["measurement_contract_id"],
            "idempotent": True,
        }
        with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
            control.authorize_outcome_access(conn, _access(legacy))
        assert exc_info.value.code == "outcome_acquisition_route_v2_required_before_access"
    finally:
        conn.close()


def test_custodian_acquisition_converts_cninfo_metadata_identity_drift_to_mismatch(tmp_path: Path) -> None:
    database, _ = _authorized_cninfo_database(tmp_path)
    wrong_identity = _cninfo_row()
    wrong_identity["secCode"] = "600000"
    candidate = outcome_acquisition.acquire_cninfo_outcome_source_candidate(
        str(database),
        outcome_access_authorization_id="MHE:ACCESS:SYNTHETIC:V1",
        inventory_receipt_id="MHE:INVENTORY:CNINFO:IDENTITY",
        field_locator=lambda *_: "PDF p. 38",
        request=_cninfo_request([wrong_identity]),
    )
    assert candidate["status"] == "MEASUREMENT_MISMATCH"
    assert candidate["mismatch_rule"] == "CNINFO_METADATA_ENUMERATION_INVALID"


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
        technical_route_resolver=_synthetic_technical_route_resolver,
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
    inventory = _field_ready_inventory(contract)
    runner.controller_acquire_and_register_outcome_source_inventory(
        database,
        outcome_access_authorization_id=access["authorization_id"],
        inventory_receipt_id=inventory["inventory_receipt_id"],
        field_locator=lambda *_: inventory["source"]["field_ref"],
        request=_cninfo_request([_cninfo_row()]),
    )
    observation = _observation(contract)
    observation["status"] = "MATCH"
    with pytest.raises(ValueError, match="caller-authored fields"):
        runner.controller_record_and_settle(
            database,
            outcome_access_authorization_id=access["authorization_id"],
            outcome_source_inventory_receipt_id=inventory["inventory_receipt_id"],
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
            technical_route_resolver=_synthetic_technical_route_resolver,
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


def test_official_rmb_revenue_quote_uses_only_the_selected_consolidated_current_period_column() -> None:
    _, _, evidence, _ = _cn600425_revenue_preoutcome_chain()
    verification = _rmb_source_verification(
        evidence["source"],
        subject_ref={"object_type": "STATIC_EVIDENCE", "object_id": evidence["evidence_receipt_id"], "object_version": 1},
    )
    runner._verify_quote_value(verification, source=evidence["source"])

    # The second disclosed amount is the comparative-period column.  It cannot
    # be substituted merely because it occurs in the same exact quote.
    verification["numeric_value"] = 1802357428.23
    with pytest.raises(ValueError, match="do not match"):
        runner._verify_quote_value(verification, source=evidence["source"])


@pytest.mark.parametrize(
    ("metric_id", "boundary", "field_ref", "quote", "numeric_value"),
    [
        (
            "CONSOLIDATED_REVENUE_RMB",
            "LISTED_ISSUER_CONSOLIDATED:CN002032",
            "FY2018 annual report, consolidated income statement, PDF p.69, 营业收入.",
            "其中：营业收入 17,851,264,801.72 14,542,193,769.70",
            17851264801.72,
        ),
        (
            "CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
            "LISTED_ISSUER_CONSOLIDATED:CN002032",
            "FY2018 annual report, consolidated cash-flow statement, PDF p.73, 经营活动产生的现金流量净额.",
            "经营活动产生的现金流量净额 2,013,658,744.84 1,101,068,593.63",
            2013658744.84,
        ),
        (
            "PRODUCT_REVENUE_RMB:电锅类",
            "LISTED_ISSUER_CONSOLIDATED:CN002032:DISCLOSED_PRODUCT_CATEGORY:电锅类",
            "FY2018 annual report, segment or product operational data, PDF p.12, 电锅类.",
            "电锅类 4,241,166,335.58 23.76% 3,809,138,321.20 26.19% 11.34%",
            4241166335.58,
        ),
    ],
)
def test_runner_verifies_frozen_appliance_metric_identities_without_aliasing_boundaries(
    metric_id: str, boundary: str, field_ref: str, quote: str, numeric_value: float,
) -> None:
    source = {
        "metric_id": metric_id,
        "issuer_id": "ISSUER:CN:002032",
        "responsibility_boundary": boundary,
        "field_ref": field_ref,
    }
    runner._verify_quote_value(
        {"unit": "RMB", "numeric_value": numeric_value, "exact_quote": quote},
        source=source,
    )

    drift = deepcopy(source)
    drift["responsibility_boundary"] = "LISTED_ISSUER_CONSOLIDATED:CN:OTHER"
    with pytest.raises(ValueError, match="supported consolidated financial-statement field"):
        runner._verify_quote_value(
            {"unit": "RMB", "numeric_value": numeric_value, "exact_quote": quote},
            source=drift,
        )


def test_source_verification_rejects_nonfinite_contract_bound_numbers_before_pdf_access(tmp_path: Path) -> None:
    decision, contract, evidence, prediction = _cn600425_revenue_preoutcome_chain()
    evidence["source"]["numeric_value"] = float("nan")
    verification = _rmb_source_verification(
        evidence["source"],
        subject_ref={
            "object_type": "STATIC_EVIDENCE",
            "object_id": evidence["evidence_receipt_id"],
            "object_version": evidence["evidence_receipt_version"],
        },
    )
    opened: list[bool] = []

    with pytest.raises(ValueError, match="finite numeric"):
        runner.freeze_preoutcome(
            tmp_path / "nonfinite.db",
            decision_contract_path=_write_json(tmp_path / "decision.json", decision),
            technical_route_resolver=_synthetic_technical_route_resolver,
            contract_path=_write_json(tmp_path / "contract.json", contract),
            evidence_path=_write_json(tmp_path / "evidence.json", evidence),
            prediction_path=_write_json(tmp_path / "prediction.json", prediction),
            source_verification_path=_write_json(tmp_path / "verification.json", verification),
            source_verifier=lambda *_: opened.append(True),
        )
    assert opened == []


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
            technical_route_resolver=_synthetic_technical_route_resolver,
            evidence_path=_write_json(tmp_path / "evidence.json", evidence),
            prediction_path=_write_json(tmp_path / "prediction.json", prediction),
            source_verification_path=_write_json(tmp_path / "verification.json", verification),
            source_verifier=_synthetic_source_verifier,
        )
