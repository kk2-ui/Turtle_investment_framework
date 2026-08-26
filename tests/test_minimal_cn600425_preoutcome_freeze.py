"""Reproduce the CN600425 pre-outcome freeze without opening outcome access."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess

import pytest

from scripts import minimal_historical_episode as episode
from scripts import minimal_historical_episode_control_plane as control
from scripts import minimal_historical_episode_runner as runner


COHORTS = Path("docs/development/research/cohorts")


def _load(name: str) -> dict:
    return json.loads((COHORTS / name).read_text(encoding="utf-8"))


def test_cn600425_v1_artifacts_remain_readable_but_cannot_start_a_new_episode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy records remain inspectable, but a new v1 freeze is prohibited."""
    decision = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_DECISION_CONTRACT.json")
    contract = _load("CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_MEASUREMENT_CONTRACT.json")
    evidence = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_STATIC_EVIDENCE.json")
    prediction = _load("CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_PREDICTION.json")
    curator_submission = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_PREOUTCOME_CURATOR_SUBMISSION.json")
    curator_source = curator_submission["source"]

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
    assert evidence["source"]["source_id"] == curator_source["source_id"]
    assert evidence["source"]["source_url"] == curator_source["source_url"]
    assert evidence["source"]["field_ref"] == curator_source["field_ref"]
    assert evidence["source"]["numeric_value"] == curator_source["numeric_value"]
    assert curator_source["exact_quote"] == "其中：营业收入                         2,101,120,335.32 1,802,357,428.23"
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
        "source_id": curator_source["source_id"],
        "source_url": curator_source["source_url"],
        "exact_quote": curator_source["exact_quote"],
        "numeric_value": curator_source["numeric_value"],
        "unit": curator_source["unit"],
        "allowed_outputs": ["MECHANICAL_SETTLEMENT_ONLY"],
        "method_transfer_rights": "NO_METHOD_TRANSFER_RIGHTS",
    }
    verification_path = tmp_path / "cn600425-static-source-verification.json"
    receipt_path = tmp_path / "cn600425-static-source-receipt.json"
    database = tmp_path / "cn600425-preoutcome.sqlite"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

    class MockPdfResponse:
        def __enter__(self) -> "MockPdfResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def geturl(self) -> str:
            return curator_source["source_url"]

        def read(self) -> bytes:
            return b"%PDF-1.7 mocked official source"

    def mocked_urlopen(request: object, *, timeout: int) -> MockPdfResponse:
        assert getattr(request, "full_url") == curator_source["source_url"]
        assert timeout == 60
        return MockPdfResponse()

    def mocked_pdftotext(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command[:6] == ["pdftotext", "-f", "61", "-l", "61", "-layout"]
        assert command[-1] == "-"
        assert kwargs == {"check": True, "capture_output": True, "text": True}
        return subprocess.CompletedProcess(command, 0, stdout=f"page 61\n{curator_source['exact_quote']}\n", stderr="")

    monkeypatch.setattr(runner, "urlopen", mocked_urlopen)
    monkeypatch.setattr(runner.subprocess, "run", mocked_pdftotext)

    assert episode.validate_measurement_contract(contract, decision_contract=decision)["valid"]
    with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
        runner.freeze_preoutcome(
            database,
            decision_contract_path=COHORTS / "CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_DECISION_CONTRACT.json",
            contract_path=COHORTS / "CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_MEASUREMENT_CONTRACT.json",
            evidence_path=COHORTS / "CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_STATIC_EVIDENCE.json",
            prediction_path=COHORTS / "CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_PREDICTION.json",
            source_verification_path=verification_path,
            source_receipt_output_path=receipt_path,
        )
    assert exc_info.value.code == "measurement_contract_v2_required"
    assert not receipt_path.exists()
    assert not database.exists()


@pytest.mark.parametrize(
    ("source_field", "drifted_value"),
    [
        ("metric_id", "OTHER_REVENUE_METRIC"),
        ("responsibility_boundary", "PARENT_COMPANY_ONLY"),
        ("unit", "CNY_MILLIONS"),
    ],
)
def test_cn600425_static_evidence_rejects_measurement_field_drift(
    source_field: str, drifted_value: str,
) -> None:
    """A seemingly similar field cannot replace the contract-bound revenue measurement."""
    contract = _load("CN600425_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_MEASUREMENT_CONTRACT.json")
    evidence = _load("CN600425_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_STATIC_EVIDENCE.json")
    evidence = deepcopy(evidence)
    evidence["source"][source_field] = drifted_value

    validation = episode.validate_static_evidence(evidence, measurement_contract=contract)

    assert not validation["valid"]
    assert f"static_evidence.source.{source_field}_must_match_measurement_contract" in validation["findings"]
