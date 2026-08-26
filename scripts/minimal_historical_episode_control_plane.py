#!/usr/bin/env python3
"""Append-only in-memory-compatible control plane for minimal historical episodes.

The controller freezes Decision Contract -> Measurement Contract -> static
evidence -> prediction -> custodian -> settlement. It deliberately stores no
peers, action facts, prices, reports, method pairings, holdouts, or transfer
rights. Custodian APIs resolve their own stored inputs and never accept a
prediction or outcome value in an access or settlement request.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

try:
    from scripts import minimal_historical_episode as episode
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import minimal_historical_episode as episode


DECISION_CONTRACT_TABLE = "minimal_historical_decision_contracts"
CONTRACT_TABLE = "minimal_historical_measurement_contracts"
EVIDENCE_TABLE = "minimal_historical_static_evidence"
PREDICTION_TABLE = "minimal_historical_predictions"
ACCESS_TABLE = "minimal_historical_outcome_access"
OBSERVATION_TABLE = "minimal_historical_observations"
SETTLEMENT_TABLE = "minimal_historical_settlements"


class MinimalHistoricalEpisodeError(ValueError):
    """Stable control-plane error raised before persistent state changes."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    if not isinstance(loaded, dict):  # pragma: no cover - stored invariant
        raise MinimalHistoricalEpisodeError("stored_payload_invalid", "stored payload must be an object")
    return loaded


def _instant(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MinimalHistoricalEpisodeError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MinimalHistoricalEpisodeError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MinimalHistoricalEpisodeError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _not_future(value: str, field: str) -> None:
    if datetime.fromisoformat(value) > datetime.now(timezone.utc).replace(microsecond=0):
        raise MinimalHistoricalEpisodeError(f"{field}_cannot_be_in_future", f"{field} cannot be in the future")


def _before(left: str, right: str) -> bool:
    return datetime.fromisoformat(left) < datetime.fromisoformat(right)


def _invalid(code: str, result: dict[str, Any]) -> None:
    if not result["valid"]:
        raise MinimalHistoricalEpisodeError(code, "; ".join(result["findings"]))


def initialize(conn: sqlite3.Connection) -> None:
    """Create only the minimal-episode namespace tables."""
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {DECISION_CONTRACT_TABLE} (
                decision_contract_id TEXT NOT NULL,
                decision_contract_version INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                issuer_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                metric_id TEXT NOT NULL,
                window_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (decision_contract_id, decision_contract_version),
                UNIQUE (company_id, issuer_id, cutoff_at, metric_id, window_id)
            )"""
        )
        for operation in ("UPDATE", "DELETE"):
            conn.execute(
                f"""CREATE TRIGGER IF NOT EXISTS {DECISION_CONTRACT_TABLE}_{operation.lower()}_blocked
                    BEFORE {operation} ON {DECISION_CONTRACT_TABLE}
                    BEGIN
                        SELECT RAISE(ABORT, 'minimal historical decision contracts are append-only');
                    END"""
            )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {CONTRACT_TABLE} (
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                decision_contract_id TEXT NOT NULL,
                decision_contract_version INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                issuer_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                metric_id TEXT NOT NULL,
                window_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (measurement_contract_id, measurement_contract_version),
                UNIQUE (company_id, issuer_id, cutoff_at, metric_id, window_id),
                FOREIGN KEY (decision_contract_id, decision_contract_version)
                    REFERENCES {DECISION_CONTRACT_TABLE}(decision_contract_id, decision_contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {EVIDENCE_TABLE} (
                evidence_receipt_id TEXT NOT NULL,
                evidence_receipt_version INTEGER NOT NULL,
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (evidence_receipt_id, evidence_receipt_version),
                UNIQUE (measurement_contract_id, measurement_contract_version),
                FOREIGN KEY (measurement_contract_id, measurement_contract_version)
                    REFERENCES {CONTRACT_TABLE}(measurement_contract_id, measurement_contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {PREDICTION_TABLE} (
                prediction_id TEXT PRIMARY KEY,
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                UNIQUE (measurement_contract_id, measurement_contract_version),
                FOREIGN KEY (measurement_contract_id, measurement_contract_version)
                    REFERENCES {CONTRACT_TABLE}(measurement_contract_id, measurement_contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {ACCESS_TABLE} (
                authorization_id TEXT PRIMARY KEY,
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                authorized_at TEXT NOT NULL,
                UNIQUE (measurement_contract_id, measurement_contract_version),
                FOREIGN KEY (measurement_contract_id, measurement_contract_version)
                    REFERENCES {CONTRACT_TABLE}(measurement_contract_id, measurement_contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {OBSERVATION_TABLE} (
                observation_id TEXT PRIMARY KEY,
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                UNIQUE (measurement_contract_id, measurement_contract_version),
                FOREIGN KEY (measurement_contract_id, measurement_contract_version)
                    REFERENCES {CONTRACT_TABLE}(measurement_contract_id, measurement_contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {SETTLEMENT_TABLE} (
                settlement_id TEXT PRIMARY KEY,
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                settled_at TEXT NOT NULL,
                UNIQUE (measurement_contract_id, measurement_contract_version),
                FOREIGN KEY (measurement_contract_id, measurement_contract_version)
                    REFERENCES {CONTRACT_TABLE}(measurement_contract_id, measurement_contract_version)
            )"""
        )


def _reference(value: Any, *, field: str) -> tuple[str, int]:
    if not isinstance(value, dict):
        raise MinimalHistoricalEpisodeError(f"{field}_invalid", f"{field} must be a contract reference")
    contract_id, version = value.get("measurement_contract_id"), value.get("measurement_contract_version")
    if not isinstance(contract_id, str) or not contract_id.strip() or not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise MinimalHistoricalEpisodeError(f"{field}_invalid", f"{field} must name a positive contract identity")
    return contract_id, version


def _decision_reference(value: Any, *, field: str) -> tuple[str, int]:
    if not isinstance(value, dict):
        raise MinimalHistoricalEpisodeError(f"{field}_invalid", f"{field} must be a decision contract reference")
    contract_id, version = value.get("decision_contract_id"), value.get("decision_contract_version")
    if not isinstance(contract_id, str) or not contract_id.strip() or not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise MinimalHistoricalEpisodeError(f"{field}_invalid", f"{field} must name a positive decision contract identity")
    return contract_id, version


def _decision_contract_row(conn: sqlite3.Connection, reference: Any) -> sqlite3.Row:
    contract_id, version = _decision_reference(reference, field="decision_contract_ref")
    row = conn.execute(
        f"""SELECT * FROM {DECISION_CONTRACT_TABLE}
            WHERE decision_contract_id = ? AND decision_contract_version = ?""",
        (contract_id, version),
    ).fetchone()
    if row is None:
        raise MinimalHistoricalEpisodeError("decision_contract_not_found", "decision contract is not frozen")
    return row


def _contract_row(conn: sqlite3.Connection, reference: Any) -> sqlite3.Row:
    contract_id, version = _reference(reference, field="measurement_contract_ref")
    row = conn.execute(
        f"""SELECT * FROM {CONTRACT_TABLE}
            WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
        (contract_id, version),
    ).fetchone()
    if row is None:
        raise MinimalHistoricalEpisodeError("measurement_contract_not_found", "measurement contract is not frozen")
    return row


def _row_for_contract(conn: sqlite3.Connection, table: str, contract: dict[str, Any], *, code: str) -> sqlite3.Row:
    row = _row_for_contract_or_none(conn, table, contract)
    if row is None:
        raise MinimalHistoricalEpisodeError(code, f"{table} is required for the minimal episode chain")
    return row


def _row_for_contract_or_none(
    conn: sqlite3.Connection, table: str, contract: dict[str, Any],
) -> sqlite3.Row | None:
    return conn.execute(
        f"""SELECT * FROM {table}
            WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
        (contract["measurement_contract_id"], contract["measurement_contract_version"]),
    ).fetchone()


def register_decision_contract(
    conn: sqlite3.Connection, decision_contract: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    """Freeze one closed decision intent before the measurement contract exists."""
    timestamp = _instant(frozen_at, "decision_contract.frozen_at")
    _not_future(timestamp, "decision_contract.frozen_at")
    result = episode.validate_decision_contract(decision_contract)
    _invalid("decision_contract_invalid", result)
    payload = result["decision_contract"]
    if not _before(_instant(payload["cutoff_at"], "decision_contract.cutoff_at"), timestamp):
        raise MinimalHistoricalEpisodeError(
            "decision_contract_cutoff_not_before_freeze", "decision contract cutoff must precede freeze",
        )
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"""SELECT * FROM {DECISION_CONTRACT_TABLE}
                WHERE decision_contract_id = ? AND decision_contract_version = ?""",
            (payload["decision_contract_id"], payload["decision_contract_version"]),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise MinimalHistoricalEpisodeError(
                    "decision_contract_immutable_conflict", "decision contract identity already has different content",
                )
            return {"frozen": True, "decision_contract_id": payload["decision_contract_id"], "idempotent": True}
        conn.execute(
            f"""INSERT INTO {DECISION_CONTRACT_TABLE} (
                decision_contract_id, decision_contract_version, company_id, issuer_id, cutoff_at, metric_id,
                window_id, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["decision_contract_id"], payload["decision_contract_version"], payload["company_id"],
                payload["issuer_id"], payload["cutoff_at"], payload["metric_id"], payload["window_id"], encoded, timestamp,
            ),
        )
    return {"frozen": True, "decision_contract_id": payload["decision_contract_id"], "idempotent": False}


def register_measurement_contract(
    conn: sqlite3.Connection, contract: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    timestamp = _instant(frozen_at, "measurement_contract.frozen_at")
    _not_future(timestamp, "measurement_contract.frozen_at")
    decision_row = _decision_contract_row(conn, contract.get("decision_contract_ref") if isinstance(contract, dict) else None)
    decision_contract = _load(decision_row["payload_json"])
    result = episode.validate_measurement_contract(contract, decision_contract=decision_contract)
    _invalid("measurement_contract_invalid", result)
    payload = result["measurement_contract"]
    if not _before(decision_row["frozen_at"], timestamp):
        raise MinimalHistoricalEpisodeError(
            "decision_contract_must_precede_measurement_contract", "decision contract must precede measurement contract",
        )
    if not _before(_instant(payload["cutoff_at"], "measurement_contract.cutoff_at"), timestamp):
        raise MinimalHistoricalEpisodeError("measurement_contract_cutoff_not_before_freeze", "contract cutoff must precede freeze")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"""SELECT * FROM {CONTRACT_TABLE}
                WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
            (payload["measurement_contract_id"], payload["measurement_contract_version"]),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise MinimalHistoricalEpisodeError("measurement_contract_immutable_conflict", "contract identity already has different content")
            return {"frozen": True, "measurement_contract_id": payload["measurement_contract_id"], "idempotent": True}
        conn.execute(
            f"""INSERT INTO {CONTRACT_TABLE} (
                measurement_contract_id, measurement_contract_version, decision_contract_id, decision_contract_version,
                company_id, issuer_id, cutoff_at, metric_id, window_id, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["measurement_contract_id"], payload["measurement_contract_version"],
                payload["decision_contract_ref"]["decision_contract_id"],
                payload["decision_contract_ref"]["decision_contract_version"],
                payload["company_id"], payload["issuer_id"], payload["cutoff_at"], payload["metric_id"],
                payload["window_id"], encoded, timestamp,
            ),
        )
    return {"frozen": True, "measurement_contract_id": payload["measurement_contract_id"], "idempotent": False}


def register_static_evidence(
    conn: sqlite3.Connection, evidence: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    timestamp = _instant(frozen_at, "static_evidence.frozen_at")
    _not_future(timestamp, "static_evidence.frozen_at")
    row = _contract_row(conn, evidence.get("measurement_contract_ref") if isinstance(evidence, dict) else None)
    contract = _load(row["payload_json"])
    result = episode.validate_static_evidence(evidence, measurement_contract=contract)
    _invalid("static_evidence_invalid", result)
    payload = result["static_evidence"]
    if not _before(row["frozen_at"], timestamp):
        raise MinimalHistoricalEpisodeError("measurement_contract_must_precede_static_evidence", "contract must precede static evidence")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"""SELECT * FROM {EVIDENCE_TABLE}
                WHERE evidence_receipt_id = ? AND evidence_receipt_version = ?""",
            (payload["evidence_receipt_id"], payload["evidence_receipt_version"]),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise MinimalHistoricalEpisodeError("static_evidence_immutable_conflict", "evidence identity already has different content")
            return {"frozen": True, "evidence_receipt_id": payload["evidence_receipt_id"], "idempotent": True}
        if _row_for_contract_or_none(conn, EVIDENCE_TABLE, contract) is not None:
            raise MinimalHistoricalEpisodeError("measurement_contract_static_evidence_already_frozen", "contract already has one static evidence receipt")
        conn.execute(
            f"""INSERT INTO {EVIDENCE_TABLE} (
                evidence_receipt_id, evidence_receipt_version, measurement_contract_id, measurement_contract_version,
                payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                payload["evidence_receipt_id"], payload["evidence_receipt_version"],
                contract["measurement_contract_id"], contract["measurement_contract_version"], encoded, timestamp,
            ),
        )
    return {"frozen": True, "evidence_receipt_id": payload["evidence_receipt_id"], "idempotent": False}


def register_prediction(conn: sqlite3.Connection, prediction: dict[str, Any], *, frozen_at: str) -> dict[str, Any]:
    timestamp = _instant(frozen_at, "prediction.frozen_at")
    _not_future(timestamp, "prediction.frozen_at")
    row = _contract_row(conn, prediction.get("measurement_contract_ref") if isinstance(prediction, dict) else None)
    contract = _load(row["payload_json"])
    evidence_row = _row_for_contract(conn, EVIDENCE_TABLE, contract, code="static_evidence_not_found")
    evidence = _load(evidence_row["payload_json"])
    result = episode.validate_prediction(prediction, measurement_contract=contract, static_evidence=evidence)
    _invalid("prediction_invalid", result)
    payload = result["prediction"]
    if not _before(evidence_row["frozen_at"], timestamp):
        raise MinimalHistoricalEpisodeError("static_evidence_must_precede_prediction", "static evidence must precede prediction")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(f"SELECT * FROM {PREDICTION_TABLE} WHERE prediction_id = ?", (payload["prediction_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise MinimalHistoricalEpisodeError("prediction_immutable_conflict", "prediction identity already has different content")
            return {"frozen": True, "prediction_id": payload["prediction_id"], "idempotent": True}
        if _row_for_contract_or_none(conn, PREDICTION_TABLE, contract) is not None:
            raise MinimalHistoricalEpisodeError("measurement_contract_prediction_already_frozen", "contract already has one prediction")
        conn.execute(
            f"""INSERT INTO {PREDICTION_TABLE} (
                prediction_id, measurement_contract_id, measurement_contract_version, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?)""",
            (payload["prediction_id"], contract["measurement_contract_id"], contract["measurement_contract_version"], encoded, timestamp),
        )
    return {"frozen": True, "prediction_id": payload["prediction_id"], "idempotent": False}


def authorize_outcome_access(conn: sqlite3.Connection, authorization: dict[str, Any]) -> dict[str, Any]:
    """Open the custodian's contract-only observation lane after one prediction."""
    row = _contract_row(conn, authorization.get("measurement_contract_ref") if isinstance(authorization, dict) else None)
    contract = _load(row["payload_json"])
    result = episode.validate_outcome_access(authorization, measurement_contract=contract)
    _invalid("outcome_access_invalid", result)
    payload = result["outcome_access"]
    prediction_row = _row_for_contract(conn, PREDICTION_TABLE, contract, code="prediction_not_found")
    timestamp = _instant(payload["authorized_at"], "outcome_access.authorized_at")
    _not_future(timestamp, "outcome_access.authorized_at")
    if not _before(prediction_row["frozen_at"], timestamp):
        raise MinimalHistoricalEpisodeError("outcome_access_must_follow_prediction", "custodian access must follow the stored prediction")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(f"SELECT * FROM {ACCESS_TABLE} WHERE authorization_id = ?", (payload["authorization_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["authorized_at"] != timestamp:
                raise MinimalHistoricalEpisodeError("outcome_access_immutable_conflict", "authorization identity already has different content")
            return {"authorized": True, "authorization_id": payload["authorization_id"], "idempotent": True}
        if _row_for_contract_or_none(conn, ACCESS_TABLE, contract) is not None:
            raise MinimalHistoricalEpisodeError("measurement_contract_outcome_access_already_authorized", "contract already has outcome access")
        conn.execute(
            f"""INSERT INTO {ACCESS_TABLE} (
                authorization_id, measurement_contract_id, measurement_contract_version, custodian_id, payload_json, authorized_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                payload["authorization_id"], contract["measurement_contract_id"], contract["measurement_contract_version"],
                payload["custodian_id"], encoded, timestamp,
            ),
        )
    return {"authorized": True, "authorization_id": payload["authorization_id"], "idempotent": False}


def register_observation(conn: sqlite3.Connection, observation: dict[str, Any]) -> dict[str, Any]:
    row = _contract_row(conn, observation.get("measurement_contract_ref") if isinstance(observation, dict) else None)
    contract = _load(row["payload_json"])
    result = episode.validate_observation(observation, measurement_contract=contract)
    _invalid("observation_invalid", result)
    payload = result["observation"]
    access_row = _row_for_contract(conn, ACCESS_TABLE, contract, code="outcome_access_not_authorized")
    timestamp = _instant(payload["observed_at"], "observation.observed_at")
    _not_future(timestamp, "observation.observed_at")
    if payload["custodian_id"] != access_row["custodian_id"]:
        raise MinimalHistoricalEpisodeError("observation_custodian_does_not_match_access", "observation custodian must match access authorization")
    if not _before(access_row["authorized_at"], timestamp):
        raise MinimalHistoricalEpisodeError("observation_must_follow_outcome_access", "observation must follow custodian access")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(f"SELECT * FROM {OBSERVATION_TABLE} WHERE observation_id = ?", (payload["observation_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["observed_at"] != timestamp:
                raise MinimalHistoricalEpisodeError("observation_immutable_conflict", "observation identity already has different content")
            return {"recorded": True, "observation_id": payload["observation_id"], "idempotent": True}
        if _row_for_contract_or_none(conn, OBSERVATION_TABLE, contract) is not None:
            raise MinimalHistoricalEpisodeError("measurement_contract_observation_already_recorded", "contract already has one outcome observation")
        conn.execute(
            f"""INSERT INTO {OBSERVATION_TABLE} (
                observation_id, measurement_contract_id, measurement_contract_version, custodian_id, payload_json, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                payload["observation_id"], contract["measurement_contract_id"], contract["measurement_contract_version"],
                payload["custodian_id"], encoded, timestamp,
            ),
        )
    return {"recorded": True, "observation_id": payload["observation_id"], "idempotent": False}


def settle(conn: sqlite3.Connection, request: dict[str, Any]) -> dict[str, Any]:
    """Mechanically settle stored evidence/prediction/observation from a blank request."""
    row = _contract_row(conn, request.get("measurement_contract_ref") if isinstance(request, dict) else None)
    contract = _load(row["payload_json"])
    request_result = episode.validate_settlement_request(request, measurement_contract=contract)
    _invalid("settlement_request_invalid", request_result)
    evidence = _load(_row_for_contract(conn, EVIDENCE_TABLE, contract, code="static_evidence_not_found")["payload_json"])
    prediction = _load(_row_for_contract(conn, PREDICTION_TABLE, contract, code="prediction_not_found")["payload_json"])
    access_row = _row_for_contract(conn, ACCESS_TABLE, contract, code="outcome_access_not_authorized")
    observation_row = _row_for_contract(conn, OBSERVATION_TABLE, contract, code="observation_not_found")
    observation = _load(observation_row["payload_json"])
    payload = request_result["settlement_request"]
    timestamp = _instant(payload["settled_at"], "settlement_request.settled_at")
    _not_future(timestamp, "settlement_request.settled_at")
    if payload["custodian_id"] != access_row["custodian_id"] or payload["custodian_id"] != observation_row["custodian_id"]:
        raise MinimalHistoricalEpisodeError("settlement_custodian_mismatch", "settlement must use the authorized observation custodian")
    if not _before(observation_row["observed_at"], timestamp):
        raise MinimalHistoricalEpisodeError("settlement_must_follow_observation", "settlement must follow the recorded observation")
    derived = episode.mechanical_settlement(
        payload, measurement_contract=contract, static_evidence=evidence, prediction=prediction, observation=observation,
    )
    _invalid("mechanical_settlement_invalid", derived)
    settlement = derived["settlement"]
    encoded = _json(settlement)
    with conn:
        existing = conn.execute(f"SELECT * FROM {SETTLEMENT_TABLE} WHERE settlement_id = ?", (settlement["settlement_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["settled_at"] != timestamp:
                raise MinimalHistoricalEpisodeError("settlement_immutable_conflict", "settlement identity already has different content")
            return {"settled": True, "settlement": deepcopy(settlement), "idempotent": True}
        if _row_for_contract_or_none(conn, SETTLEMENT_TABLE, contract) is not None:
            raise MinimalHistoricalEpisodeError("measurement_contract_already_settled", "contract already has one settlement")
        conn.execute(
            f"""INSERT INTO {SETTLEMENT_TABLE} (
                settlement_id, measurement_contract_id, measurement_contract_version, payload_json, settled_at
            ) VALUES (?, ?, ?, ?, ?)""",
            (
                settlement["settlement_id"], contract["measurement_contract_id"], contract["measurement_contract_version"],
                encoded, timestamp,
            ),
        )
    return {"settled": True, "settlement": deepcopy(settlement), "idempotent": False}
