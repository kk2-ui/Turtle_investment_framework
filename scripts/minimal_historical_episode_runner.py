#!/usr/bin/env python3
"""Persist and inspect one Minimal Historical Episode without widening its rights.

The commands deliberately keep the pre-outcome and custodian phases separate.
The custodian commands accept a contract-only authorization, an official
observation, and a blank settlement request; they never accept a prediction.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from typing import Any, Sequence

try:
    from scripts import minimal_historical_episode as episode
    from scripts import minimal_historical_episode_control_plane as control
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import minimal_historical_episode as episode
    import minimal_historical_episode_control_plane as control


RUNTIME_RECEIPT_SCHEMA_VERSION = "turtle-minimal-historical-episode-runtime-receipt.v1"


def _read_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _connect(path: str | Path) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    control.initialize(conn)
    return conn


def freeze_preoutcome(
    database: str | Path,
    *,
    contract_path: str | Path,
    evidence_path: str | Path,
    prediction_path: str | Path,
    contract_frozen_at: str,
    evidence_frozen_at: str,
    prediction_frozen_at: str,
) -> dict[str, Any]:
    """Freeze the only phase allowed to read a prediction payload."""
    contract = _read_object(contract_path)
    evidence = _read_object(evidence_path)
    prediction = _read_object(prediction_path)
    with _connect(database) as conn:
        contract_result = control.register_measurement_contract(
            conn, contract, frozen_at=contract_frozen_at,
        )
        evidence_result = control.register_static_evidence(
            conn, evidence, frozen_at=evidence_frozen_at,
        )
        prediction_result = control.register_prediction(
            conn, prediction, frozen_at=prediction_frozen_at,
        )
    return {
        "stage": "PRE_OUTCOME_FROZEN",
        "measurement_contract_id": contract_result["measurement_contract_id"],
        "evidence_receipt_id": evidence_result["evidence_receipt_id"],
        "prediction_id": prediction_result["prediction_id"],
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def authorize_custodian(database: str | Path, *, access_path: str | Path) -> dict[str, Any]:
    """Open outcome access from a payload that contains no prediction content."""
    access = _read_object(access_path)
    forbidden = {"prediction_id", "predicted_direction", "realised_direction"}.intersection(access)
    if forbidden:
        raise ValueError(f"custodian access contains forbidden fields: {sorted(forbidden)}")
    with _connect(database) as conn:
        return control.authorize_outcome_access(conn, access)


def settle_custodian(
    database: str | Path,
    *,
    observation_path: str | Path,
    settlement_request_path: str | Path,
) -> dict[str, Any]:
    """Record one official outcome and mechanically settle stored state."""
    observation = _read_object(observation_path)
    request = _read_object(settlement_request_path)
    for name, payload in (("observation", observation), ("settlement_request", request)):
        forbidden = {"prediction_id", "predicted_direction", "realised_direction", "status"}.intersection(payload)
        if forbidden:
            raise ValueError(f"{name} contains forbidden caller-authored fields: {sorted(forbidden)}")
    with _connect(database) as conn:
        observation_result = control.register_observation(conn, observation)
        settlement_result = control.settle(conn, request)
    return {
        "stage": "MECHANICALLY_SETTLED",
        "observation_id": observation_result["observation_id"],
        "settlement": settlement_result["settlement"],
    }


def _identity(row: sqlite3.Row | None, *, id_field: str, at_field: str) -> dict[str, Any] | None:
    if row is None:
        return None
    return {id_field: row[id_field], at_field: row[at_field]}


def public_receipt(
    database: str | Path, *, measurement_contract_id: str, measurement_contract_version: int,
) -> dict[str, Any]:
    """Return chronology and rights without disclosing the prediction direction."""
    with _connect(database) as conn:
        contract_row = conn.execute(
            f"""SELECT * FROM {control.CONTRACT_TABLE}
                WHERE measurement_contract_id = ? AND measurement_contract_version = ?""",
            (measurement_contract_id, measurement_contract_version),
        ).fetchone()
        if contract_row is None:
            raise ValueError("measurement contract is not present in the persistent database")
        key = (measurement_contract_id, measurement_contract_version)
        evidence_row = conn.execute(
            f"SELECT * FROM {control.EVIDENCE_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        prediction_row = conn.execute(
            f"SELECT * FROM {control.PREDICTION_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        access_row = conn.execute(
            f"SELECT * FROM {control.ACCESS_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        observation_row = conn.execute(
            f"SELECT * FROM {control.OBSERVATION_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        settlement_row = conn.execute(
            f"SELECT * FROM {control.SETTLEMENT_TABLE} WHERE measurement_contract_id = ? AND measurement_contract_version = ?",
            key,
        ).fetchone()
        contract = json.loads(contract_row["payload_json"])
        settlement = json.loads(settlement_row["payload_json"]) if settlement_row is not None else None
        receipt = {
            "schema_version": RUNTIME_RECEIPT_SCHEMA_VERSION,
            "measurement_contract_ref": {
                "measurement_contract_id": measurement_contract_id,
                "measurement_contract_version": measurement_contract_version,
            },
            "company_id": contract["company_id"],
            "metric_id": contract["metric_id"],
            "window_id": contract["window_id"],
            "roles": deepcopy(contract["roles"]),
            "chronology": {
                "measurement_contract": _identity(
                    contract_row, id_field="measurement_contract_id", at_field="frozen_at",
                ),
                "static_evidence": _identity(
                    evidence_row, id_field="evidence_receipt_id", at_field="frozen_at",
                ),
                "prediction": _identity(
                    prediction_row, id_field="prediction_id", at_field="frozen_at",
                ),
                "outcome_access": _identity(
                    access_row, id_field="authorization_id", at_field="authorized_at",
                ),
                "observation": _identity(
                    observation_row, id_field="observation_id", at_field="observed_at",
                ),
                "settlement": _identity(
                    settlement_row, id_field="settlement_id", at_field="settled_at",
                ),
            },
            "settlement": settlement,
            "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
            "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
        }
    serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    if "predicted_direction" in serialized or "realised_direction" in serialized:
        raise AssertionError("public runtime receipt disclosed a sealed direction")
    return receipt


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    freeze = commands.add_parser("freeze-preoutcome")
    freeze.add_argument("--database", required=True)
    freeze.add_argument("--contract", required=True)
    freeze.add_argument("--evidence", required=True)
    freeze.add_argument("--prediction", required=True)
    freeze.add_argument("--contract-frozen-at", required=True)
    freeze.add_argument("--evidence-frozen-at", required=True)
    freeze.add_argument("--prediction-frozen-at", required=True)

    authorize = commands.add_parser("authorize-custodian")
    authorize.add_argument("--database", required=True)
    authorize.add_argument("--access", required=True)

    settle = commands.add_parser("settle-custodian")
    settle.add_argument("--database", required=True)
    settle.add_argument("--observation", required=True)
    settle.add_argument("--settlement-request", required=True)

    receipt = commands.add_parser("export-public-receipt")
    receipt.add_argument("--database", required=True)
    receipt.add_argument("--measurement-contract-id", required=True)
    receipt.add_argument("--measurement-contract-version", type=int, default=1)
    receipt.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "freeze-preoutcome":
        result = freeze_preoutcome(
            args.database,
            contract_path=args.contract,
            evidence_path=args.evidence,
            prediction_path=args.prediction,
            contract_frozen_at=args.contract_frozen_at,
            evidence_frozen_at=args.evidence_frozen_at,
            prediction_frozen_at=args.prediction_frozen_at,
        )
    elif args.command == "authorize-custodian":
        result = authorize_custodian(args.database, access_path=args.access)
    elif args.command == "settle-custodian":
        result = settle_custodian(
            args.database,
            observation_path=args.observation,
            settlement_request_path=args.settlement_request,
        )
    else:
        result = public_receipt(
            args.database,
            measurement_contract_id=args.measurement_contract_id,
            measurement_contract_version=args.measurement_contract_version,
        )
        _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
