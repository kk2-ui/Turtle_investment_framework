#!/usr/bin/env python3
"""Append-only persistence for the PIT company-state forecast epoch.

The control plane intentionally has a small namespace.  It freezes forecast
objects and later accepts a custodian's dimension settlement; it never reads a
source, computes a CJO, changes V5, or authorises report/portfolio use.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

try:
    from scripts import judgment_pit_forecast as pit
    from scripts import judgment_decision_utility as decision_utility
    from scripts import judgment_training_decision_contract as decision_contract
    from scripts import judgment_training_program as training_program
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_pit_forecast as pit
    import judgment_decision_utility as decision_utility
    import judgment_training_decision_contract as decision_contract
    import judgment_training_program as training_program


FORECAST_TABLE = "judgment_pit_company_state_forecasts"
TOURNAMENT_TABLE = "judgment_pit_relative_trajectory_tournaments"
SETTLEMENT_TABLE = "judgment_pit_forecast_settlements"
SHADOW_TABLE = "judgment_pit_prospective_shadow_episodes"
SIGNAL_SHADOW_TABLE = "judgment_pit_prospective_signal_shadows"
SIGNAL_SOURCE_FREEZE_TABLE = "judgment_pit_prospective_signal_source_freezes"
PAIRING_TABLE = "judgment_pit_forecast_method_pairings"
PAIRED_EVALUATION_TABLE = "judgment_pit_forecast_paired_evaluations"
ATTRIBUTION_TABLE = "judgment_pit_forecast_error_attributions"
DECISION_UTILITY_PAIRING_TABLE = "judgment_pit_decision_utility_pairings"
DECISION_UTILITY_EVALUATION_TABLE = "judgment_pit_decision_utility_evaluations"
DECISION_CONTRACT_TABLE = "judgment_pit_training_decision_contracts"
OUTCOME_ACCESS_TABLE = "judgment_pit_forecast_outcome_access_authorizations"
OUTCOME_MEASUREMENT_CONTRACT_TABLE = "judgment_pit_forecast_outcome_measurement_contracts"
FORECAST_ACQUISITION_SCOPE_TABLE = "judgment_pit_forecast_acquisition_scopes"
OUTCOME_OBSERVATION_TABLE = "judgment_pit_forecast_outcome_observation_receipts"
PREFORCAST_EVIDENCE_TABLE = "judgment_pit_preforecast_evidence_receipts"


class ForecastControlError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _instant(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ForecastControlError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForecastControlError(f"{field}_invalid", f"{field} must be a timezone-aware ISO-8601 instant")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _require_not_future(timestamp: str, field: str) -> None:
    """Reject caller-supplied ledger times that have not occurred yet."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if timestamp > now:
        raise ForecastControlError(
            f"{field}_cannot_be_in_future",
            f"{field} must not be later than the control-plane clock",
        )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    if not isinstance(loaded, dict):  # pragma: no cover - stored control invariant
        raise ForecastControlError("stored_payload_invalid", "stored payload must be an object")
    return loaded


def initialize(conn: sqlite3.Connection) -> None:
    """Create only forecast-epoch tables, independently of V5 control tables."""
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {FORECAST_TABLE} (
                forecast_id TEXT PRIMARY KEY,
                forecast_epoch_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                forecaster_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                UNIQUE (forecast_epoch_id, company_id, cutoff_at)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {SIGNAL_SOURCE_FREEZE_TABLE} (
                freeze_id TEXT PRIMARY KEY,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {SIGNAL_SHADOW_TABLE} (
                shadow_episode_id TEXT PRIMARY KEY,
                source_freeze_id TEXT NOT NULL UNIQUE,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {TOURNAMENT_TABLE} (
                tournament_id TEXT PRIMARY KEY,
                forecast_epoch_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {SETTLEMENT_TABLE} (
                settlement_id TEXT PRIMARY KEY,
                forecast_id TEXT NOT NULL UNIQUE,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                settled_at TEXT NOT NULL,
                FOREIGN KEY (forecast_id) REFERENCES {FORECAST_TABLE}(forecast_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {SHADOW_TABLE} (
                shadow_episode_id TEXT PRIMARY KEY,
                forecast_id TEXT NOT NULL UNIQUE,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                FOREIGN KEY (forecast_id) REFERENCES {FORECAST_TABLE}(forecast_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {PAIRING_TABLE} (
                pairing_id TEXT PRIMARY KEY,
                forecast_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                FOREIGN KEY (forecast_id) REFERENCES {FORECAST_TABLE}(forecast_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {PAIRED_EVALUATION_TABLE} (
                evaluation_id TEXT PRIMARY KEY,
                pairing_id TEXT NOT NULL UNIQUE,
                settlement_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                FOREIGN KEY (pairing_id) REFERENCES {PAIRING_TABLE}(pairing_id),
                FOREIGN KEY (settlement_id) REFERENCES {SETTLEMENT_TABLE}(settlement_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {ATTRIBUTION_TABLE} (
                attribution_id TEXT PRIMARY KEY,
                forecast_id TEXT NOT NULL,
                settlement_id TEXT NOT NULL,
                learning_scope TEXT NOT NULL,
                disposition TEXT NOT NULL,
                policy_change_id TEXT UNIQUE,
                payload_json TEXT NOT NULL,
                attributed_at TEXT NOT NULL,
                FOREIGN KEY (forecast_id) REFERENCES {FORECAST_TABLE}(forecast_id),
                FOREIGN KEY (settlement_id) REFERENCES {SETTLEMENT_TABLE}(settlement_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {DECISION_UTILITY_PAIRING_TABLE} (
                pairing_id TEXT PRIMARY KEY,
                forecast_id TEXT NOT NULL,
                forecast_pairing_id TEXT NOT NULL UNIQUE,
                decision_contract_id TEXT NOT NULL,
                decision_contract_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                FOREIGN KEY (forecast_id) REFERENCES {FORECAST_TABLE}(forecast_id),
                FOREIGN KEY (forecast_pairing_id) REFERENCES {PAIRING_TABLE}(pairing_id),
                FOREIGN KEY (decision_contract_id, decision_contract_version)
                    REFERENCES {DECISION_CONTRACT_TABLE}(contract_id, contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {DECISION_UTILITY_EVALUATION_TABLE} (
                evaluation_id TEXT PRIMARY KEY,
                decision_utility_pairing_id TEXT NOT NULL UNIQUE,
                forecast_paired_evaluation_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                FOREIGN KEY (decision_utility_pairing_id)
                    REFERENCES {DECISION_UTILITY_PAIRING_TABLE}(pairing_id),
                FOREIGN KEY (forecast_paired_evaluation_id)
                    REFERENCES {PAIRED_EVALUATION_TABLE}(evaluation_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {DECISION_CONTRACT_TABLE} (
                contract_id TEXT NOT NULL,
                contract_version INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (contract_id, contract_version),
                UNIQUE (company_id, cutoff_at)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {OUTCOME_ACCESS_TABLE} (
                authorization_id TEXT PRIMARY KEY,
                forecast_id TEXT NOT NULL UNIQUE,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                authorized_at TEXT NOT NULL,
                FOREIGN KEY (forecast_id) REFERENCES {FORECAST_TABLE}(forecast_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {OUTCOME_MEASUREMENT_CONTRACT_TABLE} (
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                contract_id TEXT NOT NULL,
                contract_version INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (measurement_contract_id, measurement_contract_version),
                UNIQUE (contract_id, contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {FORECAST_ACQUISITION_SCOPE_TABLE} (
                scope_id TEXT NOT NULL,
                scope_version INTEGER NOT NULL,
                measurement_contract_id TEXT NOT NULL,
                measurement_contract_version INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (scope_id, scope_version),
                UNIQUE (measurement_contract_id, measurement_contract_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {OUTCOME_OBSERVATION_TABLE} (
                observation_id TEXT PRIMARY KEY,
                forecast_id TEXT NOT NULL,
                measurement_id TEXT NOT NULL,
                custodian_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                UNIQUE (forecast_id, measurement_id),
                FOREIGN KEY (forecast_id) REFERENCES {FORECAST_TABLE}(forecast_id)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {PREFORCAST_EVIDENCE_TABLE} (
                evidence_receipt_id TEXT NOT NULL,
                evidence_receipt_version INTEGER NOT NULL,
                h1_receipt_id TEXT NOT NULL,
                h1_receipt_version INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                curator_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL,
                PRIMARY KEY (evidence_receipt_id, evidence_receipt_version),
                UNIQUE (company_id, cutoff_at)
            )"""
        )


def _forecast_row(conn: sqlite3.Connection, forecast_id: str) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {FORECAST_TABLE} WHERE forecast_id = ?", (forecast_id,)).fetchone()
    if row is None:
        raise ForecastControlError("forecast_not_found", "forecast_id is not frozen")
    return row


def _row(conn: sqlite3.Connection, table: str, identifier_field: str, identifier: str, *, code: str) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {table} WHERE {identifier_field} = ?", (identifier,)).fetchone()
    if row is None:
        raise ForecastControlError(code, f"{identifier_field} is not registered")
    return row


def _outcome_observation_receipts_for_settlement(conn: sqlite3.Connection, settlement: dict[str, Any]) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    rows = settlement.get("dimension_settlements") if isinstance(settlement.get("dimension_settlements"), list) else []
    for raw in rows:
        entry = raw if isinstance(raw, dict) else {}
        if entry.get("status") not in {"OBSERVED", "MEASUREMENT_MISMATCH"}:
            continue
        ref = entry.get("outcome_observation_ref") if isinstance(entry.get("outcome_observation_ref"), dict) else {}
        observation_id = ref.get("observation_id")
        if not isinstance(observation_id, str) or not observation_id:
            continue
        row = conn.execute(
            f"SELECT payload_json FROM {OUTCOME_OBSERVATION_TABLE} WHERE observation_id = ?", (observation_id,),
        ).fetchone()
        if row is not None:
            receipts[observation_id] = _load(row["payload_json"])
    return receipts


def _decision_contract_row(conn: sqlite3.Connection, reference: Any) -> sqlite3.Row:
    ref = reference if isinstance(reference, dict) else {}
    contract_id = ref.get("contract_id")
    contract_version = ref.get("contract_version")
    row = conn.execute(
        f"SELECT * FROM {DECISION_CONTRACT_TABLE} WHERE contract_id = ? AND contract_version = ?",
        (contract_id, contract_version),
    ).fetchone()
    if row is None:
        raise ForecastControlError("decision_contract_not_found", "forecast V2 must reference a frozen Decision Contract")
    return row


def _outcome_measurement_contract_row(conn: sqlite3.Connection, reference: Any) -> sqlite3.Row:
    ref = reference if isinstance(reference, dict) else {}
    contract_id = ref.get("measurement_contract_id")
    version = ref.get("measurement_contract_version")
    row = conn.execute(
        f"""SELECT * FROM {OUTCOME_MEASUREMENT_CONTRACT_TABLE}
            WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
        (contract_id, version),
    ).fetchone()
    if row is None:
        raise ForecastControlError(
            "outcome_measurement_contract_not_found",
            "Forecast V3 requires a previously frozen Outcome Measurement Contract",
        )
    return row


def _forecast_acquisition_scope_row(conn: sqlite3.Connection, reference: Any) -> sqlite3.Row:
    ref = reference if isinstance(reference, dict) else {}
    scope_id = ref.get("scope_id")
    scope_version = ref.get("scope_version")
    row = conn.execute(
        f"""SELECT * FROM {FORECAST_ACQUISITION_SCOPE_TABLE}
            WHERE scope_id = ? AND scope_version = ?""",
        (scope_id, scope_version),
    ).fetchone()
    if row is None:
        raise ForecastControlError(
            "forecast_acquisition_scope_not_found",
            "Forecast V5 requires a previously frozen custodian collection scope",
        )
    return row


def _preforecast_evidence_receipt_row(conn: sqlite3.Connection, reference: Any) -> sqlite3.Row:
    ref = reference if isinstance(reference, dict) else {}
    receipt_id = ref.get("evidence_receipt_id")
    version = ref.get("evidence_receipt_version")
    row = conn.execute(
        f"""SELECT * FROM {PREFORCAST_EVIDENCE_TABLE}
            WHERE evidence_receipt_id = ? AND evidence_receipt_version = ?""",
        (receipt_id, version),
    ).fetchone()
    if row is None:
        raise ForecastControlError(
            "preforecast_evidence_receipt_not_found",
            "Forecast V4 requires a previously frozen cutoff-visible field-extraction receipt",
        )
    return row


def _require_registered_h1_source_packet(
    conn: sqlite3.Connection, source_packet_refs: Any, *, stage0_package: dict[str, Any] | None = None,
) -> None:
    """Require V2 training objects to use an immutable H1 receipt already in the control DB."""
    refs = source_packet_refs if isinstance(source_packet_refs, list) else []
    if len(refs) != 1 or not isinstance(refs[0], dict):
        raise ForecastControlError("h1_receipt_reference_invalid", "V2 training objects require one H1 receipt reference")
    receipt_id, receipt_version = refs[0].get("receipt_id"), refs[0].get("receipt_version")
    try:
        row = conn.execute(
            """SELECT receipt_kind, payload_json FROM judgment_v5_preselection_receipts
               WHERE receipt_id = ? AND receipt_version = ?""",
            (receipt_id, receipt_version),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise ForecastControlError(
            "h1_receipt_registry_not_initialized",
            "V2 training requires the V5 preselection-receipt registry to be initialized",
        ) from exc
    if row is None or row["receipt_kind"] != "H1_STATIC_COHORT":
        raise ForecastControlError(
            "h1_receipt_not_registered",
            "V2 training requires a registered H1 static-cohort receipt",
        )
    if stage0_package is not None:
        stored = _load(row["payload_json"])
        if _json(stored) != _json(stage0_package):
            raise ForecastControlError(
                "h1_receipt_payload_mismatch",
                "the supplied H1 package must exactly match the registered immutable receipt",
            )


def register_training_decision_contract(
    conn: sqlite3.Connection, contract: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    """Freeze an outcome-free Decision Contract before a V2 forecast exists."""
    if not isinstance(contract, dict):
        raise ForecastControlError("decision_contract_invalid", "decision contract must be an object")
    timestamp = _instant(frozen_at, "decision_contract.frozen_at")
    _require_not_future(timestamp, "decision_contract.frozen_at")
    validation = decision_contract.validate_training_decision_contract(contract)
    if not validation["valid"]:
        raise ForecastControlError("decision_contract_invalid", "; ".join(validation["findings"]))
    payload = validation["decision_contract"]
    _require_registered_h1_source_packet(conn, payload["evidence_budget"]["source_packet_refs"])
    if _instant(payload["cutoff_at"], "decision_contract.cutoff_at") >= timestamp:
        raise ForecastControlError("decision_contract_cutoff_not_before_freeze", "Decision Contract cutoff must precede its freeze")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {DECISION_CONTRACT_TABLE} WHERE contract_id = ? AND contract_version = ?",
            (payload["contract_id"], payload["contract_version"]),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError("decision_contract_immutable_conflict", "Decision Contract identity already has different content")
            return {
                "frozen": True, "contract_id": payload["contract_id"],
                "contract_version": payload["contract_version"], "idempotent": True,
            }
        if conn.execute(
            f"SELECT contract_id FROM {DECISION_CONTRACT_TABLE} WHERE company_id = ? AND cutoff_at = ?",
            (payload["company_id"], payload["cutoff_at"]),
        ).fetchone() is not None:
            raise ForecastControlError("company_cutoff_decision_contract_already_frozen", "company/cutoff already has a Decision Contract")
        conn.execute(
            f"""INSERT INTO {DECISION_CONTRACT_TABLE} (
                contract_id, contract_version, company_id, cutoff_at, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                payload["contract_id"], payload["contract_version"], payload["company_id"],
                payload["cutoff_at"], encoded, timestamp,
            ),
        )
    return {
        "frozen": True, "contract_id": payload["contract_id"],
        "contract_version": payload["contract_version"], "idempotent": False,
    }


def register_forecast_outcome_measurement_contract(
    conn: sqlite3.Connection, measurement_contract: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    """Freeze a custodian-readable outcome map before a Forecast V3 can exist."""
    if not isinstance(measurement_contract, dict):
        raise ForecastControlError("outcome_measurement_contract_invalid", "measurement contract must be an object")
    timestamp = _instant(frozen_at, "measurement_contract.frozen_at")
    _require_not_future(timestamp, "measurement_contract.frozen_at")
    validation = pit.validate_forecast_outcome_measurement_contract(measurement_contract)
    if not validation["valid"]:
        raise ForecastControlError("outcome_measurement_contract_invalid", "; ".join(validation["findings"]))
    payload = validation["measurement_contract"]
    decision_row = _decision_contract_row(conn, payload.get("decision_contract_ref"))
    decision = _load(decision_row["payload_json"])
    ref = payload["decision_contract_ref"]
    if payload["company_id"] != decision["company_id"] or payload["cutoff_at"] != decision["cutoff_at"]:
        raise ForecastControlError("measurement_contract_decision_identity_mismatch", "company and cutoff must match the frozen Decision Contract")
    expected_custodian = decision["roles"]["outcome_custodian_id"]
    if payload["custodian_id"] != expected_custodian:
        raise ForecastControlError("measurement_contract_custodian_mismatch", "measurement contract must name the Decision Contract outcome custodian")
    if _instant(decision_row["frozen_at"], "decision_contract.frozen_at") >= timestamp:
        raise ForecastControlError("decision_contract_must_precede_measurement_contract", "Decision Contract must freeze before its measurement contract")
    active_policies = read_active_forecast_learning_policies(conn, as_of=payload["cutoff_at"])
    expected_policy_ids = [entry["policy_change"]["change_id"] for entry in active_policies]
    if payload["applied_policy_change_ids"] != expected_policy_ids:
        raise ForecastControlError(
            "measurement_contract_policy_application_mismatch",
            "measurement contract must acknowledge every direct policy active at its cutoff in order",
        )
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"""SELECT * FROM {OUTCOME_MEASUREMENT_CONTRACT_TABLE}
                WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
            (payload["measurement_contract_id"], payload["measurement_contract_version"]),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError("outcome_measurement_contract_immutable_conflict", "measurement contract identity already has different content")
            return {"frozen": True, "measurement_contract_id": payload["measurement_contract_id"], "idempotent": True}
        if conn.execute(
            f"SELECT measurement_contract_id FROM {OUTCOME_MEASUREMENT_CONTRACT_TABLE} WHERE contract_id = ? AND contract_version = ?",
            (ref["contract_id"], ref["contract_version"]),
        ).fetchone() is not None:
            raise ForecastControlError("decision_contract_measurement_contract_already_frozen", "Decision Contract has one immutable measurement contract")
        conn.execute(
            f"""INSERT INTO {OUTCOME_MEASUREMENT_CONTRACT_TABLE} (
                measurement_contract_id, measurement_contract_version, contract_id, contract_version,
                company_id, cutoff_at, custodian_id, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["measurement_contract_id"], payload["measurement_contract_version"],
                ref["contract_id"], ref["contract_version"], payload["company_id"], payload["cutoff_at"],
                payload["custodian_id"], encoded, timestamp,
            ),
        )
    return {"frozen": True, "measurement_contract_id": payload["measurement_contract_id"], "idempotent": False}


def register_forecast_acquisition_scope(
    conn: sqlite3.Connection, scope: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    """Freeze the exact post-forecast cells a custodian may collect for V5.

    The scope is created before the forecast, references a single immutable
    Measurement Contract, and contains no forecast probability or outcome
    content.  Its only job is to prevent the custodian from acquiring cells
    that the eventual forecast marked evidence-ineligible.
    """
    if not isinstance(scope, dict):
        raise ForecastControlError("forecast_acquisition_scope_invalid", "acquisition scope must be an object")
    timestamp = _instant(frozen_at, "forecast_acquisition_scope.frozen_at")
    _require_not_future(timestamp, "forecast_acquisition_scope.frozen_at")
    measurement_row = _outcome_measurement_contract_row(conn, scope.get("outcome_measurement_contract_ref"))
    measurement = _load(measurement_row["payload_json"])
    validation = pit.validate_forecast_acquisition_scope(scope, measurement_contract=measurement)
    if not validation["valid"]:
        raise ForecastControlError("forecast_acquisition_scope_invalid", "; ".join(validation["findings"]))
    payload = validation["acquisition_scope"]
    decision_row = _decision_contract_row(conn, payload.get("decision_contract_ref"))
    decision = _load(decision_row["payload_json"])
    if payload["custodian_id"] != decision["roles"]["outcome_custodian_id"]:
        raise ForecastControlError("acquisition_scope_custodian_mismatch", "scope must name the Decision Contract outcome custodian")
    if _instant(measurement_row["frozen_at"], "measurement_contract.frozen_at") >= timestamp:
        raise ForecastControlError(
            "measurement_contract_must_precede_acquisition_scope_freeze",
            "Outcome Measurement Contract must freeze before its collection scope",
        )
    encoded = _json(payload)
    ref = payload["outcome_measurement_contract_ref"]
    with conn:
        existing = conn.execute(
            f"""SELECT * FROM {FORECAST_ACQUISITION_SCOPE_TABLE}
                WHERE scope_id = ? AND scope_version = ?""",
            (payload["scope_id"], payload["scope_version"]),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError("forecast_acquisition_scope_immutable_conflict", "scope identity already has different frozen content")
            return {"frozen": True, "scope_id": payload["scope_id"], "idempotent": True}
        for row in conn.execute(f"SELECT payload_json FROM {FORECAST_TABLE}").fetchall():
            frozen_forecast = _load(row["payload_json"])
            if frozen_forecast.get("outcome_measurement_contract_ref") == ref:
                raise ForecastControlError(
                    "acquisition_scope_must_precede_forecast",
                    "a Measurement Contract already used by a frozen forecast cannot gain a later collection scope",
                )
        if conn.execute(
            f"""SELECT scope_id FROM {FORECAST_ACQUISITION_SCOPE_TABLE}
                WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
            (ref["measurement_contract_id"], ref["measurement_contract_version"]),
        ).fetchone() is not None:
            raise ForecastControlError(
                "measurement_contract_acquisition_scope_already_frozen",
                "each Measurement Contract has one immutable acquisition scope",
            )
        conn.execute(
            f"""INSERT INTO {FORECAST_ACQUISITION_SCOPE_TABLE} (
                scope_id, scope_version, measurement_contract_id, measurement_contract_version,
                company_id, cutoff_at, custodian_id, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["scope_id"], payload["scope_version"], ref["measurement_contract_id"],
                ref["measurement_contract_version"], payload["company_id"], payload["cutoff_at"],
                payload["custodian_id"], encoded, timestamp,
            ),
        )
    return {"frozen": True, "scope_id": payload["scope_id"], "idempotent": False}


def register_preforecast_evidence_receipt(
    conn: sqlite3.Connection, receipt: dict[str, Any], *, stage0_package: dict[str, Any], frozen_at: str,
) -> dict[str, Any]:
    """Freeze curator-extracted cutoff-visible fields from one registered H1 packet.

    This is an acquisition receipt only: it cannot create a forecast, outcome
    authorization, settlement, CJO, valuation, or any investment output.
    """
    if not isinstance(receipt, dict):
        raise ForecastControlError("preforecast_evidence_receipt_invalid", "preforecast evidence receipt must be an object")
    timestamp = _instant(frozen_at, "preforecast_evidence.frozen_at")
    _require_not_future(timestamp, "preforecast_evidence.frozen_at")
    reference = receipt.get("h1_source_packet_ref") if isinstance(receipt.get("h1_source_packet_ref"), dict) else {}
    _require_registered_h1_source_packet(conn, [reference], stage0_package=stage0_package)
    validation = pit.validate_preforecast_evidence_receipt(
        receipt, stage0_package=stage0_package, h1_source_packet_ref=reference,
    )
    if not validation["valid"]:
        raise ForecastControlError("preforecast_evidence_receipt_invalid", "; ".join(validation["findings"]))
    payload = validation["evidence_receipt"]
    if _instant(payload["cutoff_at"], "preforecast_evidence.cutoff_at") >= timestamp:
        raise ForecastControlError("preforecast_evidence_cutoff_not_before_freeze", "cutoff must precede field-extraction receipt freeze")
    encoded = _json(payload)
    ref = payload["h1_source_packet_ref"]
    with conn:
        existing = conn.execute(
            f"""SELECT * FROM {PREFORCAST_EVIDENCE_TABLE}
                WHERE evidence_receipt_id = ? AND evidence_receipt_version = ?""",
            (payload["evidence_receipt_id"], payload["evidence_receipt_version"]),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError("preforecast_evidence_receipt_immutable_conflict", "evidence receipt identity already has different content")
            return {"frozen": True, "evidence_receipt_id": payload["evidence_receipt_id"], "idempotent": True}
        if conn.execute(
            f"SELECT evidence_receipt_id FROM {PREFORCAST_EVIDENCE_TABLE} WHERE company_id = ? AND cutoff_at = ?",
            (payload["company_id"], payload["cutoff_at"]),
        ).fetchone() is not None:
            raise ForecastControlError("company_cutoff_preforecast_evidence_already_frozen", "company/cutoff already has one immutable field-extraction receipt")
        conn.execute(
            f"""INSERT INTO {PREFORCAST_EVIDENCE_TABLE} (
                evidence_receipt_id, evidence_receipt_version, h1_receipt_id, h1_receipt_version,
                company_id, cutoff_at, curator_id, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["evidence_receipt_id"], payload["evidence_receipt_version"], ref["receipt_id"], ref["receipt_version"],
                payload["company_id"], payload["cutoff_at"], payload["curator_id"], encoded, timestamp,
            ),
        )
    return {"frozen": True, "evidence_receipt_id": payload["evidence_receipt_id"], "idempotent": False}


def register_curator_preforecast_field_extraction(
    conn: sqlite3.Connection, extraction: dict[str, Any], *, evidence_receipt_id: str, evidence_receipt_version: int,
    h1_source_packet_ref: dict[str, Any], company_id: str, issuer_id: str, cutoff_at: str, curator_id: str,
    stage0_package: dict[str, Any], frozen_at: str,
) -> dict[str, Any]:
    """Compile and freeze a closed independent-curator field submission.

    The caller may supply no forecast content here: the input is limited to
    cutoff-visible facts from H1-admitted PDFs.  The resulting immutable
    receipt remains evidence-only until a separately authored Forecast V4
    cites exact field identities.
    """
    compiled = pit.compile_preforecast_evidence_receipt(
        extraction,
        evidence_receipt_id=evidence_receipt_id, evidence_receipt_version=evidence_receipt_version,
        h1_source_packet_ref=h1_source_packet_ref, company_id=company_id, issuer_id=issuer_id,
        cutoff_at=cutoff_at, curator_id=curator_id, stage0_package=stage0_package,
    )
    if not compiled["valid"]:
        raise ForecastControlError("curator_preforecast_extraction_invalid", "; ".join(compiled["findings"]))
    return register_preforecast_evidence_receipt(
        conn, compiled["evidence_receipt"], stage0_package=stage0_package, frozen_at=frozen_at,
    )


def register_company_state_forecast(
    conn: sqlite3.Connection, forecast: dict[str, Any], *, universe_snapshot: dict[str, Any], stage0_package: dict[str, Any], frozen_at: str,
) -> dict[str, Any]:
    """Validate and freeze one forecast; exact replay is the only retry path."""
    timestamp = _instant(frozen_at, "frozen_at")
    _require_not_future(timestamp, "frozen_at")
    preforecast_evidence: dict[str, Any] | None = None
    measurement_contract: dict[str, Any] | None = None
    acquisition_scope: dict[str, Any] | None = None
    schema_version = forecast.get("schema_version") if isinstance(forecast, dict) else None
    if schema_version in {pit.FORECAST_SCHEMA_VERSION_V4, pit.FORECAST_SCHEMA_VERSION_V5, pit.FORECAST_SCHEMA_VERSION_V6}:
        preforecast_evidence = _load(
            _preforecast_evidence_receipt_row(conn, forecast.get("preforecast_evidence_receipt_ref"))["payload_json"],
        )
    if schema_version in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        measurement_contract = _load(
            _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
        )
        acquisition_scope = _load(
            _forecast_acquisition_scope_row(conn, forecast.get("forecast_acquisition_scope_ref"))["payload_json"],
        )
    validation = pit.validate_company_state_forecast(
        forecast, universe_snapshot=universe_snapshot, stage0_package=stage0_package,
        preforecast_evidence_receipt=preforecast_evidence, forecast_acquisition_scope=acquisition_scope,
        outcome_measurement_contract=measurement_contract,
    )
    if not validation["valid"]:
        raise ForecastControlError("forecast_invalid", "; ".join(validation["findings"]))
    payload = validation["forecast"]
    if _instant(payload["cutoff_at"], "forecast.cutoff_at") >= _instant(timestamp, "frozen_at"):
        raise ForecastControlError("forecast_cutoff_not_before_freeze", "forecast cutoff must precede its freeze timestamp")
    if payload["schema_version"] in pit.CONTRACT_FIRST_FORECAST_SCHEMA_VERSIONS:
        _require_registered_h1_source_packet(
            conn, payload["source_packet_refs"], stage0_package=stage0_package,
        )
        contract_row = _decision_contract_row(conn, payload.get("decision_contract_ref"))
        contract_payload = _load(contract_row["payload_json"])
        contract_validation = decision_contract.validate_contract_for_forecast(contract_payload, payload)
        if not contract_validation["valid"]:
            raise ForecastControlError("forecast_decision_contract_invalid", "; ".join(contract_validation["findings"]))
        if _instant(contract_row["frozen_at"], "decision_contract.frozen_at") >= _instant(timestamp, "forecast.frozen_at"):
            raise ForecastControlError("decision_contract_must_precede_forecast_freeze", "Decision Contract must already be frozen")
    if payload["schema_version"] in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        measurement_row = _outcome_measurement_contract_row(conn, payload.get("outcome_measurement_contract_ref"))
        measurement = _load(measurement_row["payload_json"])
        measurement_validation = pit.validate_forecast_outcome_measurement_contract(measurement)
        if not measurement_validation["valid"]:
            raise ForecastControlError("stored_outcome_measurement_contract_invalid", "; ".join(measurement_validation["findings"]))
        if measurement["decision_contract_ref"] != payload["decision_contract_ref"]:
            raise ForecastControlError("forecast_measurement_contract_decision_mismatch", "measurement contract must bind the same Decision Contract")
        if any(measurement[field] != payload[field] for field in ("company_id", "issuer_id", "cutoff_at")):
            raise ForecastControlError("forecast_measurement_contract_identity_mismatch", "measurement contract must match the frozen forecast identity")
        if measurement["applied_policy_change_ids"] != payload["applied_policy_change_ids"]:
            raise ForecastControlError("forecast_measurement_contract_policy_mismatch", "forecast must carry exactly the policies bound in its measurement contract")
        if _instant(measurement_row["frozen_at"], "measurement_contract.frozen_at") >= _instant(timestamp, "forecast.frozen_at"):
            raise ForecastControlError("measurement_contract_must_precede_forecast_freeze", "Outcome Measurement Contract must freeze before a measurement-contract forecast")
    if payload["schema_version"] in {pit.FORECAST_SCHEMA_VERSION_V4, pit.FORECAST_SCHEMA_VERSION_V5, pit.FORECAST_SCHEMA_VERSION_V6}:
        evidence_row = _preforecast_evidence_receipt_row(conn, payload.get("preforecast_evidence_receipt_ref"))
        if _instant(evidence_row["frozen_at"], "preforecast_evidence.frozen_at") >= _instant(timestamp, "forecast.frozen_at"):
            raise ForecastControlError("preforecast_evidence_must_precede_forecast_freeze", "field-extraction receipt must freeze before Forecast V4")
    if payload["schema_version"] in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        scope_row = _forecast_acquisition_scope_row(conn, payload.get("forecast_acquisition_scope_ref"))
        if _instant(scope_row["frozen_at"], "forecast_acquisition_scope.frozen_at") >= _instant(timestamp, "forecast.frozen_at"):
            raise ForecastControlError(
                "acquisition_scope_must_precede_forecast_freeze",
                "custodian acquisition scope must freeze before Forecast V5",
            )
    if payload["schema_version"] == pit.FORECAST_SCHEMA_VERSION_V6:
        method_ref = payload["forecast_method_ref"]
        try:
            resolved_method = training_program.resolve_frozen_method(
                conn, program_id=method_ref["program_id"], method_version=method_ref["method_version"], as_of=timestamp,
            )
        except (training_program.TrainingProgramError, sqlite3.OperationalError) as exc:
            raise ForecastControlError("forecast_method_identity_invalid", str(exc)) from exc
        if resolved_method != method_ref:
            raise ForecastControlError(
                "forecast_method_identity_mismatch",
                "Forecast V6 must bind the exact immutable method identity resolved from the training program",
            )
    encoded = _json(payload)
    mitigation = payload["model_memory_mitigation"]
    with conn:
        existing = conn.execute(f"SELECT * FROM {FORECAST_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError("forecast_immutable_conflict", "forecast_id already identifies different frozen content")
            return {"frozen": True, "forecast_id": payload["forecast_id"], "idempotent": True}
        duplicate = conn.execute(
            f"SELECT forecast_id FROM {FORECAST_TABLE} WHERE forecast_epoch_id = ? AND company_id = ? AND cutoff_at = ?",
            (payload["forecast_epoch_id"], payload["company_id"], payload["cutoff_at"]),
        ).fetchone()
        if duplicate is not None:
            raise ForecastControlError("company_cutoff_forecast_already_frozen", "company/cutoff already has an immutable forecast in this epoch")
        conn.execute(
            f"""INSERT INTO {FORECAST_TABLE} (
                forecast_id, forecast_epoch_id, company_id, cutoff_at, forecaster_id, payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["forecast_id"], payload["forecast_epoch_id"], payload["company_id"], payload["cutoff_at"],
                mitigation["isolated_forecaster_id"], encoded, timestamp,
            ),
        )
    return {"frozen": True, "forecast_id": payload["forecast_id"], "idempotent": False}


def register_relative_trajectory_tournament(
    conn: sqlite3.Connection, tournament: dict[str, Any], *, universe_snapshot: dict[str, Any], stage0_package: dict[str, Any], frozen_at: str,
) -> dict[str, Any]:
    """Freeze a reference ranking only after resolving every forecast from DB."""
    timestamp = _instant(frozen_at, "frozen_at")
    _require_not_future(timestamp, "frozen_at")
    forecast_ids = tournament.get("forecast_ids") if isinstance(tournament, dict) else None
    if not isinstance(forecast_ids, list):
        raise ForecastControlError("tournament_invalid", "forecast_ids must be a list")
    forecasts = [_load(_forecast_row(conn, str(forecast_id))["payload_json"]) for forecast_id in forecast_ids]
    validation = pit.validate_relative_trajectory_tournament(
        tournament, forecasts=forecasts, universe_snapshot=universe_snapshot, stage0_package=stage0_package,
    )
    if not validation["valid"]:
        raise ForecastControlError("tournament_invalid", "; ".join(validation["findings"]))
    payload = validation["tournament"]
    encoded = _json(payload)
    with conn:
        existing = conn.execute(f"SELECT * FROM {TOURNAMENT_TABLE} WHERE tournament_id = ?", (payload["tournament_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError("tournament_immutable_conflict", "tournament_id already identifies different frozen content")
            return {"frozen": True, "tournament_id": payload["tournament_id"], "idempotent": True}
        conn.execute(
            f"INSERT INTO {TOURNAMENT_TABLE} (tournament_id, forecast_epoch_id, cutoff_at, payload_json, frozen_at) VALUES (?, ?, ?, ?, ?)",
            (payload["tournament_id"], payload["forecast_epoch_id"], payload["cutoff_at"], encoded, timestamp),
        )
    return {"frozen": True, "tournament_id": payload["tournament_id"], "idempotent": False}


def register_prospective_shadow_episode(
    conn: sqlite3.Connection, shadow: dict[str, Any], *, registered_at: str,
) -> dict[str, Any]:
    """Register a known-pending shadow episode without exposing a result."""
    timestamp = _instant(registered_at, "registered_at")
    _require_not_future(timestamp, "registered_at")
    if not isinstance(shadow, dict):
        raise ForecastControlError("shadow_invalid", "shadow must be an object")
    forecast_row = _forecast_row(conn, str(shadow.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    if _instant(forecast_row["frozen_at"], "forecast.frozen_at") >= timestamp:
        raise ForecastControlError(
            "forecast_must_precede_shadow_registration",
            "a prospective shadow cannot be registered before its frozen forecast exists",
        )
    measurement_contract = None
    preforecast_evidence_receipt = None
    acquisition_scope = None
    if shadow.get("schema_version") == pit.SHADOW_SCHEMA_VERSION_V3:
        if forecast.get("schema_version") not in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
            raise ForecastControlError("shadow_invalid", "V3 shadow requires a V3/V4/V5 Measurement-Contract forecast")
        measurement_contract = _load(
            _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
        )
        if forecast.get("schema_version") in {pit.FORECAST_SCHEMA_VERSION_V4, pit.FORECAST_SCHEMA_VERSION_V5, pit.FORECAST_SCHEMA_VERSION_V6}:
            preforecast_evidence_receipt = _load(
                _preforecast_evidence_receipt_row(conn, forecast.get("preforecast_evidence_receipt_ref"))["payload_json"],
            )
        if forecast.get("schema_version") in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
            acquisition_scope = _load(
                _forecast_acquisition_scope_row(conn, forecast.get("forecast_acquisition_scope_ref"))["payload_json"],
            )
    validation = pit.validate_prospective_shadow_episode(
        shadow, forecast=forecast, now_at=timestamp, measurement_contract=measurement_contract,
        preforecast_evidence_receipt=preforecast_evidence_receipt, acquisition_scope=acquisition_scope,
    )
    if not validation["valid"]:
        raise ForecastControlError("shadow_invalid", "; ".join(validation["findings"]))
    payload = validation["shadow"]
    if payload["schema_version"] in {pit.SHADOW_SCHEMA_VERSION_V2, pit.SHADOW_SCHEMA_VERSION_V3}:
        contract_row = _decision_contract_row(conn, payload.get("decision_contract_ref"))
        contract_payload = _load(contract_row["payload_json"])
        contract_validation = decision_contract.validate_contract_for_forecast(contract_payload, forecast)
        if not contract_validation["valid"]:
            raise ForecastControlError("shadow_decision_contract_invalid", "; ".join(contract_validation["findings"]))
        if payload["custodian_id"] != contract_payload["roles"]["outcome_custodian_id"]:
            raise ForecastControlError(
                "shadow_custodian_must_match_decision_contract",
                "shadow must name the outcome custodian frozen in its Decision Contract",
            )
        if _instant(contract_row["frozen_at"], "decision_contract.frozen_at") >= timestamp:
            raise ForecastControlError("decision_contract_must_precede_shadow_registration", "Decision Contract must precede shadow registration")
    if payload["schema_version"] == pit.SHADOW_SCHEMA_VERSION_V3:
        measurement_row = _outcome_measurement_contract_row(conn, payload.get("outcome_measurement_contract_ref"))
        for cell in measurement_contract["cells"]:
            try:
                outcome_period_end = datetime.fromisoformat(cell["outcome_period_end"]).date()
            except (KeyError, TypeError, ValueError) as exc:  # stored Measurement Contract invariant
                raise ForecastControlError("stored_measurement_contract_invalid", "outcome period end must be an ISO date") from exc
            if outcome_period_end < datetime.fromisoformat(timestamp).date():
                raise ForecastControlError(
                    "shadow_outcome_period_already_started",
                    "a prospective shadow must be registered before every Measurement Contract outcome period ends",
                )
        if _instant(measurement_row["frozen_at"], "measurement_contract.frozen_at") >= timestamp:
            raise ForecastControlError(
                "measurement_contract_must_precede_shadow_registration",
                "Measurement Contract must precede prospective-shadow registration",
            )
        if preforecast_evidence_receipt is not None:
            evidence_row = _preforecast_evidence_receipt_row(conn, payload.get("preforecast_evidence_receipt_ref"))
            if _instant(evidence_row["frozen_at"], "preforecast_evidence_receipt.frozen_at") >= timestamp:
                raise ForecastControlError(
                    "preforecast_evidence_receipt_must_precede_shadow_registration",
                    "preforecast evidence receipt must precede prospective-shadow registration",
                )
        if acquisition_scope is not None:
            scope_row = _forecast_acquisition_scope_row(conn, payload.get("forecast_acquisition_scope_ref"))
            if _instant(scope_row["frozen_at"], "forecast_acquisition_scope.frozen_at") >= timestamp:
                raise ForecastControlError(
                    "forecast_acquisition_scope_must_precede_shadow_registration",
                    "Forecast Acquisition Scope must precede prospective-shadow registration",
                )
        for table, code in (
            (OUTCOME_ACCESS_TABLE, "shadow_cannot_follow_outcome_access"),
            (OUTCOME_OBSERVATION_TABLE, "shadow_cannot_follow_outcome_observation"),
            (SETTLEMENT_TABLE, "shadow_cannot_follow_settlement"),
        ):
            if conn.execute(f"SELECT 1 FROM {table} WHERE forecast_id = ?", (payload["forecast_id"],)).fetchone() is not None:
                raise ForecastControlError(code, "a prospective shadow must be registered before any outcome-lane record")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(f"SELECT * FROM {SHADOW_TABLE} WHERE shadow_episode_id = ?", (payload["shadow_episode_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["registered_at"] != timestamp:
                raise ForecastControlError("shadow_immutable_conflict", "shadow episode already identifies different content")
            return {"registered": True, "shadow_episode_id": payload["shadow_episode_id"], "idempotent": True}
        duplicate = conn.execute(f"SELECT shadow_episode_id FROM {SHADOW_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],)).fetchone()
        if duplicate is not None:
            raise ForecastControlError("forecast_shadow_already_registered", "a forecast can have only one unresolved shadow episode")
        conn.execute(
            f"INSERT INTO {SHADOW_TABLE} (shadow_episode_id, forecast_id, custodian_id, payload_json, registered_at) VALUES (?, ?, ?, ?, ?)",
            (payload["shadow_episode_id"], payload["forecast_id"], payload["custodian_id"], encoded, timestamp),
        )
    return {"registered": True, "shadow_episode_id": payload["shadow_episode_id"], "idempotent": False}


def register_prospective_signal_source_freeze(
    conn: sqlite3.Connection, source_freeze: dict[str, Any], *, registered_at: str,
) -> dict[str, Any]:
    """Append the cutoff-visible source allowlist before a signal probe exists."""
    timestamp = _instant(registered_at, "registered_at")
    _require_not_future(timestamp, "registered_at")
    validation = pit.validate_prospective_signal_source_freeze(source_freeze, now_at=timestamp)
    if not validation["valid"]:
        raise ForecastControlError("signal_source_freeze_invalid", "; ".join(validation["findings"]))
    payload = validation["source_freeze"]
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {SIGNAL_SOURCE_FREEZE_TABLE} WHERE freeze_id = ?", (payload["freeze_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["registered_at"] != timestamp:
                raise ForecastControlError(
                    "signal_source_freeze_immutable_conflict",
                    "source-freeze id already identifies different immutable content",
                )
            return {"registered": True, "freeze_id": payload["freeze_id"], "idempotent": True}
        conn.execute(
            f"INSERT INTO {SIGNAL_SOURCE_FREEZE_TABLE} (freeze_id, cutoff_at, payload_json, registered_at) VALUES (?, ?, ?, ?)",
            (payload["freeze_id"], payload["cutoff_at"], encoded, timestamp),
        )
    return {"registered": True, "freeze_id": payload["freeze_id"], "idempotent": False}


def register_prospective_signal_shadow_episode(
    conn: sqlite3.Connection, shadow: dict[str, Any], *, registered_at: str,
) -> dict[str, Any]:
    """Persist a current prequential signal probe without a forecast/CJO bridge."""
    timestamp = _instant(registered_at, "registered_at")
    _require_not_future(timestamp, "registered_at")
    validation = pit.validate_prospective_signal_shadow_episode(shadow, now_at=timestamp)
    if not validation["valid"]:
        raise ForecastControlError("signal_shadow_invalid", "; ".join(validation["findings"]))
    payload = validation["shadow"]
    encoded = _json(payload)
    freeze_id = payload["source_freeze_ref"]["freeze_id"]
    freeze_row = conn.execute(
        f"SELECT payload_json, registered_at FROM {SIGNAL_SOURCE_FREEZE_TABLE} WHERE freeze_id = ?", (freeze_id,),
    ).fetchone()
    if freeze_row is None:
        raise ForecastControlError(
            "signal_source_freeze_not_registered",
            "a prospective signal shadow must cite a previously registered immutable source-freeze receipt",
        )
    if _load(freeze_row["payload_json"]) != payload["source_freeze_ref"]:
        raise ForecastControlError(
            "signal_source_freeze_mismatch",
            "signal shadow source-freeze content must exactly match the registered immutable receipt",
        )
    if _instant(freeze_row["registered_at"], "signal_source_freeze.registered_at") > timestamp:
        raise ForecastControlError(
            "signal_source_freeze_must_precede_shadow_registration",
            "source-freeze receipt must be registered before its signal shadow",
        )
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {SIGNAL_SHADOW_TABLE} WHERE shadow_episode_id = ?", (payload["shadow_episode_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["registered_at"] != timestamp:
                raise ForecastControlError("signal_shadow_immutable_conflict", "shadow episode already identifies different content")
            return {"registered": True, "shadow_episode_id": payload["shadow_episode_id"], "idempotent": True}
        duplicate = conn.execute(
            f"SELECT shadow_episode_id FROM {SIGNAL_SHADOW_TABLE} WHERE source_freeze_id = ?", (freeze_id,),
        ).fetchone()
        if duplicate is not None:
            raise ForecastControlError("source_freeze_shadow_already_registered", "a source freeze can have only one unresolved signal shadow")
        conn.execute(
            f"INSERT INTO {SIGNAL_SHADOW_TABLE} (shadow_episode_id, source_freeze_id, custodian_id, payload_json, registered_at) VALUES (?, ?, ?, ?, ?)",
            (payload["shadow_episode_id"], freeze_id, payload["custodian_id"], encoded, timestamp),
        )
    return {"registered": True, "shadow_episode_id": payload["shadow_episode_id"], "idempotent": False}


def authorize_forecast_outcome_access(
    conn: sqlite3.Connection, authorization: dict[str, Any],
) -> dict[str, Any]:
    """Record the sole custodian's outcome-read permission after a V2 forecast is frozen.

    The authorization contains no source IDs, measurements, or realised facts.
    Those may enter only in a later settlement by this already-designated custodian.
    """
    if not isinstance(authorization, dict):
        raise ForecastControlError("outcome_access_invalid", "outcome access authorization must be an object")
    forecast_row = _forecast_row(conn, str(authorization.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    if forecast.get("schema_version") not in pit.CONTRACT_FIRST_FORECAST_SCHEMA_VERSIONS:
        raise ForecastControlError("outcome_access_requires_contract_first_forecast", "only contract-first forecasts may open outcome access")
    measurement_contract = None
    acquisition_scope = None
    if forecast.get("schema_version") in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        measurement_contract = _load(
            _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
        )
        acquisition_scope = _load(
            _forecast_acquisition_scope_row(conn, forecast.get("forecast_acquisition_scope_ref"))["payload_json"],
        )
    validation = pit.validate_forecast_outcome_access_authorization(
        authorization, forecast=forecast, acquisition_scope=acquisition_scope,
        measurement_contract=measurement_contract,
    )
    if not validation["valid"]:
        raise ForecastControlError("outcome_access_invalid", "; ".join(validation["findings"]))
    payload = validation["authorization"]
    contract_row = _decision_contract_row(conn, forecast.get("decision_contract_ref"))
    contract = _load(contract_row["payload_json"])
    expected_custodian = contract["roles"]["outcome_custodian_id"]
    if payload["custodian_id"] != expected_custodian:
        raise ForecastControlError(
            "outcome_access_custodian_must_match_decision_contract",
            "only the outcome custodian frozen in the Decision Contract may open outcome access",
        )
    if forecast.get("schema_version") in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        measurement_row = _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))
        measurement = _load(measurement_row["payload_json"])
        if payload.get("outcome_measurement_contract_ref") != forecast.get("outcome_measurement_contract_ref"):
            raise ForecastControlError("outcome_access_measurement_contract_mismatch", "authorization must bind the frozen Measurement Contract")
        if measurement["custodian_id"] != payload["custodian_id"]:
            raise ForecastControlError("outcome_access_measurement_contract_custodian_mismatch", "authorization custodian must match Measurement Contract")
    timestamp = _instant(payload["authorized_at"], "outcome_access.authorized_at")
    _require_not_future(timestamp, "outcome_access.authorized_at")
    if timestamp <= _instant(forecast_row["frozen_at"], "forecast.frozen_at"):
        raise ForecastControlError("outcome_access_precedes_forecast_freeze", "outcome access must follow the frozen Forecast V2")
    shadow_row = conn.execute(
        f"SELECT payload_json FROM {SHADOW_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],),
    ).fetchone()
    if shadow_row is not None:
        shadow = _load(shadow_row["payload_json"])
        if shadow.get("schema_version") == pit.SHADOW_SCHEMA_VERSION_V3:
            due_at = max(
                _instant(item["resolution_due_at"], "shadow.resolution_due_at")
                for item in shadow["resolution_calendar"]
            )
            if timestamp < due_at:
                raise ForecastControlError(
                    "outcome_access_precedes_prospective_shadow_resolution_due",
                    "custodian outcome access stays closed until the prospective shadow's final resolution due time",
                )
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {OUTCOME_ACCESS_TABLE} WHERE authorization_id = ?", (payload["authorization_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["authorized_at"] != timestamp:
                raise ForecastControlError("outcome_access_immutable_conflict", "authorization_id already identifies different content")
            return {"authorized": True, "authorization_id": payload["authorization_id"], "idempotent": True}
        if conn.execute(
            f"SELECT authorization_id FROM {OUTCOME_ACCESS_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],),
        ).fetchone() is not None:
            raise ForecastControlError("forecast_outcome_access_already_authorized", "each forecast has one immutable outcome-access authorization")
        conn.execute(
            f"INSERT INTO {OUTCOME_ACCESS_TABLE} (authorization_id, forecast_id, custodian_id, payload_json, authorized_at) VALUES (?, ?, ?, ?, ?)",
            (payload["authorization_id"], payload["forecast_id"], payload["custodian_id"], encoded, timestamp),
        )
    return {"authorized": True, "authorization_id": payload["authorization_id"], "idempotent": False}


def register_forecast_outcome_observation_receipt(
    conn: sqlite3.Connection, receipt: dict[str, Any],
) -> dict[str, Any]:
    """Persist one custodian-extracted V3 outcome field before settlement.

    The receipt binds issuer, source page, field identity, period, perimeter,
    unit and raw value to a frozen Measurement Contract.  Settlement receives
    only its immutable identity, never a fresh caller-declared raw field.
    """
    if not isinstance(receipt, dict):
        raise ForecastControlError("outcome_observation_invalid", "outcome observation receipt must be an object")
    forecast_row = _forecast_row(conn, str(receipt.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    if forecast.get("schema_version") not in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        raise ForecastControlError("outcome_observation_requires_measurement_contract_forecast", "only a measurement-contract forecast has an observation lane")
    measurement = _load(
        _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
    )
    acquisition_scope = None
    if forecast.get("schema_version") in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        acquisition_scope = _load(
            _forecast_acquisition_scope_row(conn, forecast.get("forecast_acquisition_scope_ref"))["payload_json"],
        )
    validation = pit.validate_forecast_outcome_observation_receipt(
        receipt, forecast=forecast, measurement_contract=measurement, acquisition_scope=acquisition_scope,
    )
    if not validation["valid"]:
        raise ForecastControlError("outcome_observation_invalid", "; ".join(validation["findings"]))
    payload = validation["observation_receipt"]
    contract_row = _decision_contract_row(conn, forecast.get("decision_contract_ref"))
    contract = _load(contract_row["payload_json"])
    if payload["custodian_id"] != contract["roles"]["outcome_custodian_id"]:
        raise ForecastControlError("outcome_observation_custodian_mismatch", "only the Decision Contract custodian may register outcome observations")
    access = conn.execute(
        f"SELECT * FROM {OUTCOME_ACCESS_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],),
    ).fetchone()
    if access is None:
        raise ForecastControlError("outcome_observation_access_not_authorized", "custodian access authorization must precede outcome observation")
    if access["custodian_id"] != payload["custodian_id"]:
        raise ForecastControlError("outcome_observation_custodian_does_not_match_access", "receipt custodian must match outcome access")
    observed_at = _instant(payload["observed_at"], "outcome_observation.observed_at")
    _require_not_future(observed_at, "outcome_observation.observed_at")
    if observed_at < _instant(access["authorized_at"], "outcome_access.authorized_at"):
        raise ForecastControlError("outcome_observation_precedes_access", "outcome observation must follow authorization")
    if conn.execute(f"SELECT settlement_id FROM {SETTLEMENT_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],)).fetchone() is not None:
        raise ForecastControlError("outcome_observation_after_settlement", "observation receipts must be complete before settlement")
    cells = {
        (cell["dimension_id"], cell["window_id"]): cell
        for cell in measurement["cells"]
    }
    measurement_id = cells[(payload["dimension_id"], payload["window_id"])]["measurement_id"]
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {OUTCOME_OBSERVATION_TABLE} WHERE observation_id = ?", (payload["observation_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["observed_at"] != observed_at:
                raise ForecastControlError("outcome_observation_immutable_conflict", "observation_id already identifies different content")
            return {"recorded": True, "observation_id": payload["observation_id"], "idempotent": True}
        if conn.execute(
            f"SELECT observation_id FROM {OUTCOME_OBSERVATION_TABLE} WHERE forecast_id = ? AND measurement_id = ?",
            (payload["forecast_id"], measurement_id),
        ).fetchone() is not None:
            raise ForecastControlError("forecast_measurement_already_observed", "each forecast measurement cell has one immutable observation receipt")
        conn.execute(
            f"""INSERT INTO {OUTCOME_OBSERVATION_TABLE} (
                observation_id, forecast_id, measurement_id, custodian_id, payload_json, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (payload["observation_id"], payload["forecast_id"], measurement_id, payload["custodian_id"], encoded, observed_at),
        )
    return {"recorded": True, "observation_id": payload["observation_id"], "idempotent": False}


def register_forecast_settlement(conn: sqlite3.Connection, settlement: dict[str, Any]) -> dict[str, Any]:
    """Accept only a later custodian settlement and preserve per-dimension scores."""
    if not isinstance(settlement, dict):
        raise ForecastControlError("settlement_invalid", "settlement must be an object")
    forecast_row = _forecast_row(conn, str(settlement.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    measurement_contract: dict[str, Any] | None = None
    observation_receipts: dict[str, dict[str, Any]] = {}
    acquisition_scope: dict[str, Any] | None = None
    if forecast.get("schema_version") in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        measurement_contract = _load(
            _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
        )
        observation_receipts = _outcome_observation_receipts_for_settlement(conn, settlement)
    if forecast.get("schema_version") in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        acquisition_scope = _load(
            _forecast_acquisition_scope_row(conn, forecast.get("forecast_acquisition_scope_ref"))["payload_json"],
        )
    validation = pit.settle_company_state_forecast(
        forecast, settlement, measurement_contract=measurement_contract, observation_receipts=observation_receipts,
        acquisition_scope=acquisition_scope,
    )
    if not validation["valid"]:
        raise ForecastControlError("settlement_invalid", "; ".join(validation["findings"]))
    payload = validation["settlement"]
    if payload["custodian_id"] == forecast_row["forecaster_id"]:
        raise ForecastControlError("settlement_custodian_not_independent", "forecasting agent cannot be its own outcome custodian")
    if forecast.get("schema_version") in pit.CONTRACT_FIRST_FORECAST_SCHEMA_VERSIONS:
        contract_row = _decision_contract_row(conn, forecast.get("decision_contract_ref"))
        contract_payload = _load(contract_row["payload_json"])
        contract_validation = decision_contract.validate_contract_for_forecast(contract_payload, forecast)
        if not contract_validation["valid"]:
            raise ForecastControlError("settlement_decision_contract_invalid", "; ".join(contract_validation["findings"]))
        if payload["custodian_id"] != contract_payload["roles"]["outcome_custodian_id"]:
            raise ForecastControlError(
                "settlement_custodian_must_match_decision_contract",
                "V2 settlement must be performed by the outcome custodian frozen in its Decision Contract",
            )
    timestamp = _instant(payload["settled_at"], "settlement.settled_at")
    _require_not_future(timestamp, "settlement.settled_at")
    if forecast.get("schema_version") in pit.CONTRACT_FIRST_FORECAST_SCHEMA_VERSIONS:
        authorization_row = conn.execute(
            f"SELECT * FROM {OUTCOME_ACCESS_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],),
        ).fetchone()
        if authorization_row is None:
            raise ForecastControlError(
                "forecast_outcome_access_not_authorized",
                "Forecast V2 settlement requires a prior immutable custodian outcome-access authorization",
            )
        if authorization_row["custodian_id"] != payload["custodian_id"]:
            raise ForecastControlError("settlement_custodian_does_not_match_outcome_access", "settlement custodian must match outcome-access authorization")
        if timestamp < _instant(authorization_row["authorized_at"], "outcome_access.authorized_at"):
            raise ForecastControlError("settlement_precedes_outcome_access_authorization", "settlement must follow outcome-access authorization")
    if timestamp <= _instant(forecast_row["frozen_at"], "forecast.frozen_at"):
        raise ForecastControlError("settlement_precedes_freeze", "settlement must follow frozen forecast")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(f"SELECT * FROM {SETTLEMENT_TABLE} WHERE settlement_id = ?", (payload["settlement_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded:
                raise ForecastControlError("settlement_immutable_conflict", "settlement_id already identifies different content")
            return {"settled": True, "settlement_id": payload["settlement_id"], "idempotent": True, "coverage": validation["coverage"]}
        if conn.execute(f"SELECT settlement_id FROM {SETTLEMENT_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],)).fetchone() is not None:
            raise ForecastControlError("forecast_already_settled", "forecast already has an immutable settlement")
        conn.execute(
            f"INSERT INTO {SETTLEMENT_TABLE} (settlement_id, forecast_id, custodian_id, payload_json, settled_at) VALUES (?, ?, ?, ?, ?)",
            (payload["settlement_id"], payload["forecast_id"], payload["custodian_id"], encoded, timestamp),
        )
    return {"settled": True, "settlement_id": payload["settlement_id"], "idempotent": False, "coverage": validation["coverage"]}


def register_forecast_method_pairing(
    conn: sqlite3.Connection, pairing: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    """Freeze a baseline beside an already-frozen forecast before settlement.

    This records a method comparison contract, not a second company conclusion.
    Once the outcome is stored, a new pairing is rejected rather than allowing
    a baseline to be reconstructed with outcome knowledge.
    """
    if not isinstance(pairing, dict):
        raise ForecastControlError("pairing_invalid", "pairing must be an object")
    timestamp = _instant(frozen_at, "pairing.frozen_at")
    _require_not_future(timestamp, "pairing.frozen_at")
    forecast_row = _forecast_row(conn, str(pairing.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    measurement_contract = None
    if forecast.get("schema_version") in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        measurement_contract = _load(
            _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
        )
    prepared_pairing = deepcopy(pairing)
    if prepared_pairing.get("schema_version") == pit.PAIRING_SCHEMA_VERSION_V2:
        raw_binding = prepared_pairing.get("holdout_binding")
        if not isinstance(raw_binding, dict) or set(raw_binding) != {
            "program_id", "holdout_training_episode_id", "evaluated_cell_refs",
        }:
            raise ForecastControlError(
                "pairing_holdout_binding_invalid",
                "V2 pairing must request exactly a program, COMPANY_AND_TIME episode and evaluated cell refs",
            )
        if not isinstance(raw_binding.get("evaluated_cell_refs"), list):
            raise ForecastControlError("pairing_holdout_binding_invalid", "evaluated_cell_refs must be a list")
        try:
            resolved = training_program.resolve_frozen_company_time_holdout(
                conn,
                program_id=str(raw_binding.get("program_id") or ""),
                training_episode_id=str(raw_binding.get("holdout_training_episode_id") or ""),
                as_of=timestamp,
            )
        except training_program.TrainingProgramError as exc:
            raise ForecastControlError("pairing_holdout_binding_invalid", str(exc)) from exc
        if resolved["method_version"] != prepared_pairing.get("enhanced_method_id"):
            raise ForecastControlError(
                "pairing_holdout_method_version_mismatch",
                "enhanced method must exactly match the frozen COMPANY_AND_TIME holdout method version",
            )
        if timestamp >= _instant(resolved["outcome_not_before"], "holdout.outcome_not_before"):
            raise ForecastControlError(
                "pairing_must_precede_holdout_outcome_window",
                "a paired baseline must be frozen before the canonical holdout outcome window opens",
            )
        if (
            resolved["company_id"] != forecast.get("company_id")
            or _instant(resolved["cutoff_at"], "holdout.cutoff_at") != _instant(forecast["cutoff_at"], "forecast.cutoff_at")
        ):
            raise ForecastControlError(
                "pairing_holdout_forecast_identity_mismatch",
                "Forecast company and cutoff must exactly match the resolved COMPANY_AND_TIME holdout",
            )
        if measurement_contract is None:
            raise ForecastControlError(
                "pairing_holdout_requires_measurement_contract",
                "V2 pairing needs the forecast's frozen Measurement Contract",
            )
        measurement_cells = {
            (cell["dimension_id"], cell["window_id"]): cell
            for cell in measurement_contract["cells"]
        }
        forecast_cells = pit._forecast_cell_index(forecast)
        evaluated_cells: list[dict[str, str]] = []
        seen_cells: set[tuple[str, str]] = set()
        for index, raw in enumerate(raw_binding["evaluated_cell_refs"]):
            if not isinstance(raw, dict) or set(raw) != {"dimension_id", "window_id"}:
                raise ForecastControlError(
                    "pairing_holdout_binding_invalid",
                    f"evaluated_cell_refs[{index}] must name exactly one forecast dimension/window",
                )
            key = (raw.get("dimension_id"), raw.get("window_id"))
            if key not in forecast_cells or key not in measurement_cells or key in seen_cells:
                raise ForecastControlError(
                    "pairing_holdout_binding_invalid",
                    "evaluated cells must be unique MODEL_UNCERTAIN Measurement-Contract cells",
                )
            seen_cells.add(key)
            evaluated_cells.append({
                "dimension_id": key[0], "window_id": key[1],
                "outcome_period_end": measurement_cells[key]["outcome_period_end"],
            })
        if not evaluated_cells:
            raise ForecastControlError("pairing_holdout_binding_invalid", "at least one evaluated cell is required")
        prepared_pairing["holdout_binding"] = {**resolved, "evaluated_cells": evaluated_cells}
    validation = pit.validate_forecast_pairing(
        prepared_pairing, forecast=forecast, measurement_contract=measurement_contract,
    )
    if not validation["valid"]:
        raise ForecastControlError("pairing_invalid", "; ".join(validation["findings"]))
    payload = validation["pairing"]
    if timestamp <= _instant(forecast_row["frozen_at"], "forecast.frozen_at"):
        raise ForecastControlError("pairing_precedes_forecast_freeze", "method pairing must follow its frozen forecast")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {PAIRING_TABLE} WHERE pairing_id = ?", (payload["pairing_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError("pairing_immutable_conflict", "pairing_id already identifies different frozen content")
            return {"frozen": True, "pairing_id": payload["pairing_id"], "idempotent": True}
        if conn.execute(
            f"SELECT settlement_id FROM {SETTLEMENT_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],),
        ).fetchone() is not None:
            raise ForecastControlError("pairing_must_be_frozen_before_settlement", "baseline cannot be registered after a forecast settles")
        if conn.execute(
            f"SELECT authorization_id FROM {OUTCOME_ACCESS_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],),
        ).fetchone() is not None:
            raise ForecastControlError(
                "pairing_must_precede_outcome_access_authorization",
                "baseline cannot be registered after custodian outcome access opens",
            )
        if conn.execute(
            f"SELECT pairing_id FROM {PAIRING_TABLE} WHERE forecast_id = ?", (payload["forecast_id"],),
        ).fetchone() is not None:
            raise ForecastControlError("forecast_pairing_already_frozen", "forecast already has an immutable method pairing")
        conn.execute(
            f"INSERT INTO {PAIRING_TABLE} (pairing_id, forecast_id, payload_json, frozen_at) VALUES (?, ?, ?, ?)",
            (payload["pairing_id"], payload["forecast_id"], encoded, timestamp),
        )
    return {"frozen": True, "pairing_id": payload["pairing_id"], "idempotent": False}


def register_forecast_paired_evaluation(conn: sqlite3.Connection, evaluation: dict[str, Any]) -> dict[str, Any]:
    """Persist a per-cell baseline/enhanced comparison after custodian settlement."""
    if not isinstance(evaluation, dict):
        raise ForecastControlError("paired_evaluation_invalid", "paired evaluation must be an object")
    pairing_row = _row(
        conn, PAIRING_TABLE, "pairing_id", str(evaluation.get("pairing_id") or ""), code="pairing_not_found",
    )
    pairing = _load(pairing_row["payload_json"])
    forecast_row = _forecast_row(conn, str(pairing["forecast_id"]))
    forecast = _load(forecast_row["payload_json"])
    measurement_contract = None
    acquisition_scope = None
    if forecast.get("schema_version") in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        measurement_contract = _load(
            _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
        )
    if forecast.get("schema_version") in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        acquisition_scope = _load(
            _forecast_acquisition_scope_row(conn, forecast.get("forecast_acquisition_scope_ref"))["payload_json"],
        )
    settlement_row = _row(
        conn, SETTLEMENT_TABLE, "settlement_id", str(evaluation.get("settlement_id") or ""), code="settlement_not_found",
    )
    settlement = _load(settlement_row["payload_json"])
    observation_receipts = _outcome_observation_receipts_for_settlement(conn, settlement)
    validation = pit.validate_forecast_paired_evaluation(
        evaluation, forecast=forecast, settlement=settlement, pairing=pairing, measurement_contract=measurement_contract,
        observation_receipts=observation_receipts, acquisition_scope=acquisition_scope,
    )
    if not validation["valid"]:
        raise ForecastControlError("paired_evaluation_invalid", "; ".join(validation["findings"]))
    payload = validation["paired_evaluation"]
    timestamp = _instant(payload["evaluated_at"], "paired_evaluation.evaluated_at")
    _require_not_future(timestamp, "paired_evaluation.evaluated_at")
    if timestamp < _instant(settlement_row["settled_at"], "settlement.settled_at"):
        raise ForecastControlError("paired_evaluation_precedes_settlement", "paired evaluation must follow settlement")
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {PAIRED_EVALUATION_TABLE} WHERE evaluation_id = ?", (payload["evaluation_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["evaluated_at"] != timestamp:
                raise ForecastControlError("paired_evaluation_immutable_conflict", "evaluation_id already identifies different content")
            return {
                "evaluated": True, "evaluation_id": payload["evaluation_id"], "idempotent": True,
                "cell_comparisons": validation["cell_comparisons"],
            }
        if conn.execute(
            f"SELECT evaluation_id FROM {PAIRED_EVALUATION_TABLE} WHERE pairing_id = ? OR settlement_id = ?",
            (payload["pairing_id"], payload["settlement_id"]),
        ).fetchone() is not None:
            raise ForecastControlError("pairing_or_settlement_already_evaluated", "pairing and settlement have one immutable evaluation")
        conn.execute(
            f"""INSERT INTO {PAIRED_EVALUATION_TABLE} (
                evaluation_id, pairing_id, settlement_id, payload_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?)""",
            (payload["evaluation_id"], payload["pairing_id"], payload["settlement_id"], encoded, timestamp),
        )
    return {
        "evaluated": True, "evaluation_id": payload["evaluation_id"], "idempotent": False,
        "cell_comparisons": validation["cell_comparisons"],
    }


def register_decision_utility_pairing(
    conn: sqlite3.Connection, pairing: dict[str, Any], *, frozen_at: str,
) -> dict[str, Any]:
    """Freeze a qualitative method comparison before custodian access opens.

    This is an append-only companion to Forecast Pairing V2.  It never
    creates a policy, changes a CJO, or permits report or investment use.
    """
    if not isinstance(pairing, dict):
        raise ForecastControlError("decision_utility_pairing_invalid", "pairing must be an object")
    timestamp = _instant(frozen_at, "decision_utility_pairing.frozen_at")
    _require_not_future(timestamp, "decision_utility_pairing.frozen_at")
    forecast_pairing_row = _row(
        conn, PAIRING_TABLE, "pairing_id", str(pairing.get("forecast_pairing_id") or ""),
        code="forecast_pairing_not_found",
    )
    forecast_pairing = _load(forecast_pairing_row["payload_json"])
    forecast_row = _forecast_row(conn, str(forecast_pairing.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    contract_row = _decision_contract_row(conn, forecast.get("decision_contract_ref"))
    contract_payload = _load(contract_row["payload_json"])
    validation = decision_utility.validate_decision_utility_control_pairing(
        pairing, forecast=forecast, forecast_pairing=forecast_pairing, contract=contract_payload,
    )
    if not validation["valid"]:
        raise ForecastControlError("decision_utility_pairing_invalid", "; ".join(validation["findings"]))
    payload = validation["pairing"]
    if _instant(payload["frozen_at"], "decision_utility_pairing.payload.frozen_at") != timestamp:
        raise ForecastControlError(
            "decision_utility_pairing_frozen_at_must_match_control_timestamp",
            "the immutable pairing payload must carry the exact control-plane freeze instant",
        )
    if timestamp < _instant(forecast_pairing_row["frozen_at"], "forecast_pairing.frozen_at"):
        raise ForecastControlError(
            "decision_utility_pairing_precedes_forecast_pairing",
            "decision utility pairing must follow its immutable Forecast Pairing V2",
        )
    holdout = forecast_pairing.get("holdout_binding") if isinstance(forecast_pairing.get("holdout_binding"), dict) else {}
    if timestamp >= _instant(holdout.get("outcome_not_before"), "forecast_pairing.holdout.outcome_not_before"):
        raise ForecastControlError(
            "decision_utility_pairing_must_precede_holdout_outcome_window",
            "qualitative baseline/enhanced decisions must freeze before the canonical holdout outcome window opens",
        )
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {DECISION_UTILITY_PAIRING_TABLE} WHERE pairing_id = ?", (payload["pairing_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise ForecastControlError(
                    "decision_utility_pairing_immutable_conflict",
                    "pairing_id already identifies different immutable content",
                )
            return {
                "frozen": True, "pairing_id": payload["pairing_id"], "idempotent": True,
                "learning_authorization": validation["learning_authorization"],
            }
        if conn.execute(
            f"SELECT authorization_id FROM {OUTCOME_ACCESS_TABLE} WHERE forecast_id = ?", (forecast["forecast_id"],),
        ).fetchone() is not None:
            raise ForecastControlError(
                "decision_utility_pairing_must_precede_outcome_access_authorization",
                "qualitative baseline/enhanced decisions cannot be introduced after custodian access opens",
            )
        if conn.execute(
            f"SELECT pairing_id FROM {DECISION_UTILITY_PAIRING_TABLE} WHERE forecast_pairing_id = ?",
            (payload["forecast_pairing_id"],),
        ).fetchone() is not None:
            raise ForecastControlError(
                "forecast_pairing_already_has_decision_utility_pairing",
                "a Forecast Pairing V2 has one immutable decision-utility pairing",
            )
        ref = payload["decision_contract_ref"]
        conn.execute(
            f"""INSERT INTO {DECISION_UTILITY_PAIRING_TABLE} (
                pairing_id, forecast_id, forecast_pairing_id, decision_contract_id, decision_contract_version,
                payload_json, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["pairing_id"], forecast["forecast_id"], payload["forecast_pairing_id"],
                ref["contract_id"], ref["contract_version"], encoded, timestamp,
            ),
        )
    return {
        "frozen": True, "pairing_id": payload["pairing_id"], "idempotent": False,
        "learning_authorization": validation["learning_authorization"],
    }


def register_decision_utility_evaluation(
    conn: sqlite3.Connection, evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Record an independent qualitative review of an exact paired outcome.

    The settlement and company-and-time holdout are resolved from registered
    forecast artifacts; callers cannot substitute either with an ad-hoc
    reference.  The sole authorization remains ``CANDIDATE_ONLY``.
    """
    if not isinstance(evaluation, dict):
        raise ForecastControlError("decision_utility_evaluation_invalid", "evaluation must be an object")
    pairing_row = _row(
        conn, DECISION_UTILITY_PAIRING_TABLE, "pairing_id", str(evaluation.get("pairing_id") or ""),
        code="decision_utility_pairing_not_found",
    )
    pairing = _load(pairing_row["payload_json"])
    forecast_pairing_row = _row(
        conn, PAIRING_TABLE, "pairing_id", str(pairing.get("forecast_pairing_id") or ""),
        code="forecast_pairing_not_found",
    )
    forecast_pairing = _load(forecast_pairing_row["payload_json"])
    forecast_row = _forecast_row(conn, str(forecast_pairing.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    contract_row = _decision_contract_row(conn, forecast.get("decision_contract_ref"))
    contract_payload = _load(contract_row["payload_json"])
    paired_evaluation_row = _row(
        conn, PAIRED_EVALUATION_TABLE, "evaluation_id", str(evaluation.get("forecast_paired_evaluation_id") or ""),
        code="forecast_paired_evaluation_not_found",
    )
    paired_evaluation = _load(paired_evaluation_row["payload_json"])
    validation = decision_utility.validate_decision_utility_control_evaluation(
        evaluation, pairing=pairing, forecast=forecast, forecast_pairing=forecast_pairing,
        forecast_paired_evaluation=paired_evaluation, contract=contract_payload,
    )
    if not validation["valid"]:
        raise ForecastControlError("decision_utility_evaluation_invalid", "; ".join(validation["findings"]))
    payload = validation["evaluation"]
    timestamp = _instant(payload["evaluated_at"], "decision_utility_evaluation.evaluated_at")
    _require_not_future(timestamp, "decision_utility_evaluation.evaluated_at")
    if timestamp < _instant(paired_evaluation_row["evaluated_at"], "forecast_paired_evaluation.evaluated_at"):
        raise ForecastControlError(
            "decision_utility_evaluation_precedes_forecast_paired_evaluation",
            "decision utility evaluation must follow the immutable per-cell forecast comparison",
        )
    settlement_row = _row(
        conn, SETTLEMENT_TABLE, "settlement_id", str(paired_evaluation.get("settlement_id") or ""),
        code="settlement_not_found",
    )
    if payload["reviewer_id"] in {forecast_row["forecaster_id"], settlement_row["custodian_id"]}:
        raise ForecastControlError(
            "decision_utility_reviewer_not_independent",
            "reviewer must differ from both forecast owner and outcome custodian",
        )
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {DECISION_UTILITY_EVALUATION_TABLE} WHERE evaluation_id = ?", (payload["evaluation_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["evaluated_at"] != timestamp:
                raise ForecastControlError(
                    "decision_utility_evaluation_immutable_conflict",
                    "evaluation_id already identifies different immutable content",
                )
            return {
                "evaluated": True, "evaluation_id": payload["evaluation_id"], "idempotent": True,
                "learning_authorization": validation["learning_authorization"],
            }
        if conn.execute(
            f"SELECT evaluation_id FROM {DECISION_UTILITY_EVALUATION_TABLE} "
            "WHERE decision_utility_pairing_id = ? OR forecast_paired_evaluation_id = ?",
            (payload["pairing_id"], payload["forecast_paired_evaluation_id"]),
        ).fetchone() is not None:
            raise ForecastControlError(
                "decision_utility_pairing_or_forecast_evaluation_already_reviewed",
                "one immutable utility review is allowed for each pairing and forecast evaluation",
            )
        conn.execute(
            f"""INSERT INTO {DECISION_UTILITY_EVALUATION_TABLE} (
                evaluation_id, decision_utility_pairing_id, forecast_paired_evaluation_id, payload_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?)""",
            (
                payload["evaluation_id"], payload["pairing_id"],
                payload["forecast_paired_evaluation_id"], encoded, timestamp,
            ),
        )
    return {
        "evaluated": True, "evaluation_id": payload["evaluation_id"], "idempotent": False,
        "learning_authorization": validation["learning_authorization"],
    }


def register_forecast_error_attribution(conn: sqlite3.Connection, attribution: dict[str, Any]) -> dict[str, Any]:
    """Admit only limited forecast-method feedback; never a CJO or investment change."""
    if not isinstance(attribution, dict):
        raise ForecastControlError("attribution_invalid", "attribution must be an object")
    forecast_row = _forecast_row(conn, str(attribution.get("forecast_id") or ""))
    forecast = _load(forecast_row["payload_json"])
    measurement_contract = None
    acquisition_scope = None
    if forecast.get("schema_version") in pit.MEASUREMENT_CONTRACT_FORECAST_SCHEMA_VERSIONS:
        measurement_contract = _load(
            _outcome_measurement_contract_row(conn, forecast.get("outcome_measurement_contract_ref"))["payload_json"],
        )
    if forecast.get("schema_version") in pit.ACQUISITION_SCOPE_FORECAST_SCHEMA_VERSIONS:
        acquisition_scope = _load(
            _forecast_acquisition_scope_row(conn, forecast.get("forecast_acquisition_scope_ref"))["payload_json"],
        )
    settlement_row = _row(
        conn, SETTLEMENT_TABLE, "settlement_id", str(attribution.get("settlement_id") or ""), code="settlement_not_found",
    )
    settlement = _load(settlement_row["payload_json"])
    observation_receipts = _outcome_observation_receipts_for_settlement(conn, settlement)
    if settlement.get("forecast_id") != forecast.get("forecast_id"):
        raise ForecastControlError("attribution_forecast_settlement_mismatch", "settlement belongs to another forecast")

    paired_evaluation: dict[str, Any] | None = None
    pairing: dict[str, Any] | None = None
    evaluation_id = attribution.get("paired_evaluation_id")
    if isinstance(evaluation_id, str) and evaluation_id:
        evaluation_row = _row(
            conn, PAIRED_EVALUATION_TABLE, "evaluation_id", evaluation_id, code="paired_evaluation_not_found",
        )
        paired_evaluation = _load(evaluation_row["payload_json"])
        pairing_row = _row(
            conn, PAIRING_TABLE, "pairing_id", str(paired_evaluation.get("pairing_id") or ""), code="pairing_not_found",
        )
        pairing = _load(pairing_row["payload_json"])
    validation = pit.validate_forecast_error_attribution(
        attribution, forecast=forecast, settlement=settlement, pairing=pairing, paired_evaluation=paired_evaluation,
        measurement_contract=measurement_contract, observation_receipts=observation_receipts,
        acquisition_scope=acquisition_scope,
    )
    if not validation["valid"]:
        raise ForecastControlError("attribution_invalid", "; ".join(validation["findings"]))
    payload = validation["attribution"]
    if payload["reviewer_id"] in {forecast_row["forecaster_id"], settlement_row["custodian_id"]}:
        raise ForecastControlError("attribution_reviewer_not_independent", "reviewer must differ from forecaster and outcome custodian")
    timestamp = _instant(payload["attributed_at"], "attribution.attributed_at")
    _require_not_future(timestamp, "attribution.attributed_at")
    if timestamp < _instant(settlement_row["settled_at"], "settlement.settled_at"):
        raise ForecastControlError("attribution_precedes_settlement", "attribution must follow settlement")
    if paired_evaluation is not None and timestamp < _instant(paired_evaluation["evaluated_at"], "paired_evaluation.evaluated_at"):
        raise ForecastControlError("attribution_precedes_paired_evaluation", "candidate attribution must follow paired evaluation")
    policy = payload.get("policy_change") if isinstance(payload.get("policy_change"), dict) else {}
    policy_change_id = policy.get("change_id") if payload.get("disposition") == "DIRECT_FORECAST_POLICY" else None
    encoded = _json(payload)
    with conn:
        existing = conn.execute(
            f"SELECT * FROM {ATTRIBUTION_TABLE} WHERE attribution_id = ?", (payload["attribution_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["attributed_at"] != timestamp:
                raise ForecastControlError("attribution_immutable_conflict", "attribution_id already identifies different content")
            return {
                "recorded": True, "attribution_id": payload["attribution_id"], "idempotent": True,
                "learning_authorization": validation["learning_authorization"],
            }
        if policy_change_id and conn.execute(
            f"SELECT attribution_id FROM {ATTRIBUTION_TABLE} WHERE policy_change_id = ?", (policy_change_id,),
        ).fetchone() is not None:
            raise ForecastControlError("forecast_policy_change_already_recorded", "direct forecast policy change_id is immutable and unique")
        conn.execute(
            f"""INSERT INTO {ATTRIBUTION_TABLE} (
                attribution_id, forecast_id, settlement_id, learning_scope, disposition, policy_change_id, payload_json, attributed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["attribution_id"], payload["forecast_id"], payload["settlement_id"], payload["learning_scope"],
                payload["disposition"], policy_change_id, encoded, timestamp,
            ),
        )
    return {
        "recorded": True, "attribution_id": payload["attribution_id"], "idempotent": False,
        "learning_authorization": validation["learning_authorization"],
    }


def read_active_forecast_learning_policies(conn: sqlite3.Connection, *, as_of: str) -> list[dict[str, Any]]:
    """Project only direct forecast policies that were available before a new cutoff.

    Candidate evidence-priority and rival-hypothesis entries intentionally do
    not appear here: they require later paired replication before a separate
    method-release epoch can consume them.
    """
    cutoff = _instant(as_of, "as_of")
    policies: list[dict[str, Any]] = []
    rows = conn.execute(
        f"""SELECT a.payload_json FROM {ATTRIBUTION_TABLE} AS a
            JOIN {FORECAST_TABLE} AS f ON f.forecast_id = a.forecast_id
                WHERE a.disposition = 'DIRECT_FORECAST_POLICY' AND f.forecast_epoch_id IN (?, ?, ?, ?)
            ORDER BY a.attributed_at, a.attribution_id""",
        (pit.FORECAST_EPOCH_ID_V3, pit.FORECAST_EPOCH_ID_V4, pit.FORECAST_EPOCH_ID_V5, pit.FORECAST_EPOCH_ID_V6),
    ).fetchall()
    for row in rows:
        payload = _load(row["payload_json"])
        change = payload.get("policy_change") if isinstance(payload.get("policy_change"), dict) else {}
        effective = change.get("effective_from_cutoff_at")
        if isinstance(effective, str) and _instant(effective, "policy_change.effective_from_cutoff_at") <= cutoff:
            policies.append({
                "attribution_id": payload["attribution_id"], "learning_scope": payload["learning_scope"],
                "policy_change": change,
            })
    return policies
