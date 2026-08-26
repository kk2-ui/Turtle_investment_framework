"""Reproduce the CN600425 pre-outcome freeze without opening outcome access."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from scripts import minimal_historical_episode_control_plane as control


COHORTS = Path("docs/development/research/cohorts")


def _load(name: str) -> dict:
    return json.loads((COHORTS / name).read_text(encoding="utf-8"))


def test_cn600425_revenue_preoutcome_chain_is_closed_and_stops_before_access(tmp_path: Path) -> None:
    """The independently curated field can freeze only the four allowed objects."""
    decision = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_DECISION_CONTRACT.json")
    contract = _load("CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_MEASUREMENT_CONTRACT.json")
    evidence = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_STATIC_EVIDENCE.json")
    prediction = _load("CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_PREDICTION.json")

    assert evidence["curator_id"] not in set(decision["roles"].values())
    assert decision["roles"]["forecaster_id"] != decision["roles"]["custodian_id"]
    assert contract["decision_contract_ref"] == {
        "decision_contract_id": decision["decision_contract_id"],
        "decision_contract_version": decision["decision_contract_version"],
    }
    assert evidence["measurement_contract_ref"] == {
        "measurement_contract_id": contract["measurement_contract_id"],
        "measurement_contract_version": contract["measurement_contract_version"],
    }
    assert prediction["measurement_contract_ref"] == evidence["measurement_contract_ref"]
    assert prediction["evidence_receipt_ref"] == {
        "evidence_receipt_id": evidence["evidence_receipt_id"],
        "evidence_receipt_version": evidence["evidence_receipt_version"],
    }

    conn = sqlite3.connect(tmp_path / "cn600425-preoutcome.sqlite")
    try:
        control.initialize(conn)
        assert control.register_decision_contract(
            conn, decision, frozen_at="2026-08-26T13:00:00+08:00",
        )["frozen"]
        assert control.register_measurement_contract(
            conn, contract, frozen_at="2026-08-26T13:01:00+08:00",
        )["frozen"]
        assert control.register_static_evidence(
            conn, evidence, frozen_at="2026-08-26T13:02:00+08:00",
        )["frozen"]
        assert control.register_prediction(
            conn, prediction, frozen_at="2026-08-26T13:03:00+08:00",
        )["frozen"]

        assert conn.execute(f"SELECT COUNT(*) FROM {control.DECISION_CONTRACT_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.EVIDENCE_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.PREDICTION_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.ACCESS_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OUTCOME_SOURCE_INVENTORY_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OBSERVATION_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()
