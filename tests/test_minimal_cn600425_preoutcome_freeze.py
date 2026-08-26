"""Reproduce the CN600425 pre-outcome freeze without opening outcome access."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from scripts import minimal_historical_episode_control_plane as control
from scripts import minimal_historical_episode_runner as runner


COHORTS = Path("docs/development/research/cohorts")


def _load(name: str) -> dict:
    return json.loads((COHORTS / name).read_text(encoding="utf-8"))


def test_cn600425_revenue_runner_freezes_only_the_preoutcome_chain(tmp_path: Path) -> None:
    """The real runner verifies the frozen static field before it seals four records."""
    decision = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_DECISION_CONTRACT.json")
    contract = _load("CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_MEASUREMENT_CONTRACT.json")
    evidence = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_STATIC_EVIDENCE.json")
    prediction = _load("CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_PREDICTION.json")

    assert decision["company_id"] == "CN:600425"
    assert decision["issuer_id"] == "ISSUER:CN:600425"
    assert decision["cutoff_at"] == "2018-04-30T23:59:59+08:00"
    assert decision["roles"] == {
        "forecaster_id": "FORECASTER:CN600425:REVENUE:20260826",
        "custodian_id": "CUSTODIAN:CN600425:REVENUE:FUTURE",
    }
    assert contract["metric_id"] == "ISSUER_CONSOLIDATED_OPERATING_REVENUE_RMB"
    assert contract["responsibility_boundary"] == "LISTED_CONSOLIDATED_ISSUER"
    assert contract["unit"] == "RMB"
    assert evidence["curator_id"] == "CURATOR:CN600425:REVENUE:20260826"
    assert evidence["source"]["source_id"] == "CNINFO:600425:ANN:20180421:1204677754"
    assert evidence["source"]["source_url"] == "https://static.cninfo.com.cn/finalpage/2018-04-21/1204677754.PDF"
    assert evidence["source"]["field_ref"].endswith("PDF p. 61, 营业收入.")
    for value in (decision, contract, evidence, prediction):
        assert value["allowed_outputs"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert value["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"

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

    verification = {
        "schema_version": runner.SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION,
        "subject_ref": {
            "object_type": "STATIC_EVIDENCE",
            "object_id": evidence["evidence_receipt_id"],
            "object_version": evidence["evidence_receipt_version"],
        },
        "source_id": "CNINFO:600425:ANN:20180421:1204677754",
        "source_url": "https://static.cninfo.com.cn/finalpage/2018-04-21/1204677754.PDF",
        "exact_quote": "其中：营业收入 2,101,120,335.32 1,803,015,198.11",
        "numeric_value": 2101120335.32,
        "unit": "RMB",
        "allowed_outputs": ["MECHANICAL_SETTLEMENT_ONLY"],
        "method_transfer_rights": "NO_METHOD_TRANSFER_RIGHTS",
    }
    verification_path = tmp_path / "cn600425-static-source-verification.json"
    receipt_path = tmp_path / "cn600425-static-source-receipt.json"
    database = tmp_path / "cn600425-preoutcome.sqlite"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

    def mocked_official_pdf_source(source: dict, source_verification: dict) -> dict:
        """Model the official PDF retriever without opening any external source."""
        assert source == evidence["source"]
        assert source_verification == verification
        assert runner._declared_pdf_page(source["field_ref"]) == 61
        runner._verify_quote_value(source_verification, source=source)
        return {
            "schema_version": runner.SOURCE_RECEIPT_SCHEMA_VERSION,
            "verification_state": "OPENED_OFFICIAL_PDF_FIELD_MATCHED",
            "retrieved_at": "2026-08-26T13:10:00+00:00",
            "subject_ref": source_verification["subject_ref"],
            "source_id": source["source_id"],
            "source_url": source["source_url"],
            "field_ref": source["field_ref"],
            "exact_quote": source_verification["exact_quote"],
            "numeric_value": source["numeric_value"],
            "unit": source["unit"],
            "allowed_outputs": source_verification["allowed_outputs"],
            "method_transfer_rights": source_verification["method_transfer_rights"],
        }

    result = runner.freeze_preoutcome(
        database,
        decision_contract_path=COHORTS / "CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_DECISION_CONTRACT.json",
        contract_path=COHORTS / "CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_MEASUREMENT_CONTRACT.json",
        evidence_path=COHORTS / "CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_STATIC_EVIDENCE.json",
        prediction_path=COHORTS / "CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_PREDICTION.json",
        source_verification_path=verification_path,
        source_verifier=mocked_official_pdf_source,
        source_receipt_output_path=receipt_path,
    )

    assert result["stage"] == "PRE_OUTCOME_FROZEN"
    assert result["source_acquisition"]["verification_state"] == "OPENED_OFFICIAL_PDF_FIELD_MATCHED"
    assert result["source_acquisition"]["source_id"] == evidence["source"]["source_id"]
    assert result["source_acquisition"]["field_ref"] == evidence["source"]["field_ref"]
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == result["source_acquisition"]

    conn = sqlite3.connect(database)
    try:
        control.initialize(conn)
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
