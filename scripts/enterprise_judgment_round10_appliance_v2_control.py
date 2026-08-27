#!/usr/bin/env python3
"""Thin persistence adapter for the frozen Round 10 appliance batch.

This module deliberately owns no prediction, source-acquisition, or settlement
logic.  It only projects the nine already-frozen field contracts into the
existing Minimal Historical Episode control plane, then creates the
contract-only access requests an independent custodian may later use.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any

try:
    from scripts import enterprise_judgment_round10_appliance_v2 as round10
    from scripts import minimal_historical_episode as minimal
    from scripts import minimal_historical_episode_control_plane as control
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_round10_appliance_v2 as round10
    import minimal_historical_episode as minimal
    import minimal_historical_episode_control_plane as control


class Round10ControlError(ValueError):
    """The frozen batch cannot be projected into the established control plane."""


def _controller_clock(index: int) -> str:
    """Produce a strictly ordered, controller-owned runtime chronology.

    ``round10.FROZEN_AT`` is the historical simulation's semantic freeze
    point, not permission to backdate a real append-only database write.  The
    timestamp here records when this controller actually replays the already
    committed blind package into its isolated control database.
    """
    base = datetime.now(timezone.utc) - timedelta(seconds=1)
    return (base + timedelta(milliseconds=index)).isoformat()


def _chains(batch: dict[str, Any]) -> list[dict[str, Any]]:
    result = round10.validate_batch_freeze(batch)
    if not result["valid"]:
        raise Round10ControlError("round10_batch_invalid:" + ";".join(result["findings"]))
    chains: list[dict[str, Any]] = []
    for package in batch["company_packages"]:
        chains.extend(package["minimal_field_chains"])
    if len(chains) != 9:
        raise Round10ControlError("round10_batch_requires_exactly_nine_field_chains")
    return chains


def initialize(conn: sqlite3.Connection) -> None:
    """Initialise only the pre-existing Minimal episode tables."""
    control.initialize(conn)


def freeze_preoutcome_batch(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """Persist the frozen nine-field roster without opening outcome access.

    The caller cannot supply an alternate roster, source identity, direction,
    technical route, or timestamps.  Each field is
    registered through the established Decision → route → Contract → Evidence
    → Prediction sequence.  The source package was independently curated and
    frozen in the Round 10 pre-outcome commit; this adapter does not reopen
    sources, enumerate outcome metadata, or read a prediction after storage.
    """
    chains = _chains(round10.build_real_preoutcome_batch())
    initialize(conn)
    receipts: list[dict[str, str]] = []
    for chain_index, chain in enumerate(chains):
        # Five strictly ordered controller writes per field. These record the
        # actual registration moment, never the historical cutoff simulation.
        clock = chain_index * 5
        decision = control.register_decision_contract(
            conn, chain["decision_contract"], frozen_at=_controller_clock(clock + 1),
        )
        route = control.register_technical_route_identity(
            conn, chain["technical_route_identity"], frozen_at=_controller_clock(clock + 2),
        )
        contract = control.register_measurement_contract(
            conn, chain["measurement_contract"], frozen_at=_controller_clock(clock + 3),
        )
        evidence = control.register_static_evidence(
            conn, chain["static_evidence"], frozen_at=_controller_clock(clock + 4),
        )
        prediction = control.register_prediction(
            conn, chain["prediction"], frozen_at=_controller_clock(clock + 5),
        )
        receipts.append({
            "company_id": chain["decision_contract"]["company_id"],
            "metric_id": chain["measurement_contract"]["metric_id"],
            "decision_contract_id": decision["decision_contract_id"],
            "technical_route_identity_id": route["technical_route_identity_id"],
            "measurement_contract_id": contract["measurement_contract_id"],
            "evidence_receipt_id": evidence["evidence_receipt_id"],
            "prediction_id": prediction["prediction_id"],
        })
    return {
        "stage": "ROUND10_PREOUTCOME_BATCH_REGISTERED",
        "field_count": len(receipts),
        "field_receipts": receipts,
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "INDEPENDENT_REVIEW_CANDIDATE", "RESEARCH_AGENDA"],
        "rights": dict(round10.RIGHTS),
    }


def build_contract_only_outcome_access_requests(
) -> list[dict[str, Any]]:
    """Create the nine sealed-contract access requests for distinct custodians.

    ``authorized_at`` is intentionally a placeholder: the existing runner,
    not the caller or this adapter, replaces it with its execution clock when
    access is actually opened.  The returned request has no prediction,
    baseline/enhanced judgment, price, or outcome field.
    """
    requests: list[dict[str, Any]] = []
    for chain in _chains(round10.build_real_preoutcome_batch()):
        contract = chain["measurement_contract"]
        requests.append({
            "schema_version": minimal.OUTCOME_ACCESS_SCHEMA_VERSION,
            "authorization_id": f"MHE:ACCESS:{contract['measurement_contract_id'].removeprefix('MHE:CONTRACT:')}",
            "measurement_contract_ref": {
                "measurement_contract_id": contract["measurement_contract_id"],
                "measurement_contract_version": contract["measurement_contract_version"],
            },
            "custodian_id": contract["roles"]["custodian_id"],
            "authorized_at": round10.FROZEN_AT,
            "object_class": "MINIMAL_HISTORICAL_OUTCOME_ACCESS",
            "claim_class": "CUSTODIAN_CONTRACT_ONLY_ACCESS",
            "allowed_outputs": list(minimal.ALLOWED_OUTPUTS),
            "method_transfer_rights": minimal.NO_METHOD_TRANSFER_RIGHTS,
        })
    return requests


def database_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return only lifecycle counts, never any prediction or observed value."""
    initialize(conn)
    tables = {
        "decision": control.DECISION_CONTRACT_TABLE,
        "route": control.TECHNICAL_ROUTE_IDENTITY_TABLE,
        "measurement": control.CONTRACT_TABLE,
        "evidence": control.EVIDENCE_TABLE,
        "prediction": control.PREDICTION_TABLE,
        "access": control.ACCESS_TABLE,
        "inventory": control.OUTCOME_SOURCE_INVENTORY_TABLE,
        "observation": control.OBSERVATION_TABLE,
        "settlement": control.SETTLEMENT_TABLE,
    }
    return {name: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for name, table in tables.items()}


def open_database(path: str | Path) -> sqlite3.Connection:
    """Open an isolated runtime database with the expected row shape."""
    connection = sqlite3.connect(path)
    initialize(connection)
    return connection
