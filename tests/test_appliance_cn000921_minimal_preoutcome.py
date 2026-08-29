"""CN000921 result-unseen Minimal Historical Episode pre-freeze acceptance."""

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


ROOT = Path(__file__).resolve().parents[1]
COHORTS = ROOT / "docs/development/research/cohorts"


def _read(name: str) -> dict:
    return json.loads((COHORTS / name).read_text(encoding="utf-8"))


def _objects() -> tuple[dict, dict, dict, dict, dict]:
    return (
        _read("CN000921_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_DECISION_CONTRACT.json"),
        _read("CN000921_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_MEASUREMENT_CONTRACT.json"),
        _read("CN000921_FY2016_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_STATIC_EVIDENCE.json"),
        _read("CN000921_FY2017_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_PREDICTION.json"),
        _read("CN000921_FY2016_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_SOURCE_VERIFICATION_INPUT.json"),
    )


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cn000921_v2_chain_is_closed_and_result_unseen() -> None:
    decision, contract, evidence, prediction, verification = _objects()
    assert episode.validate_decision_contract(decision)["valid"]
    assert episode.validate_measurement_contract(contract, decision_contract=decision)["valid"]
    assert episode.validate_static_evidence(evidence, measurement_contract=contract)["valid"]
    assert episode.validate_prediction(prediction, measurement_contract=contract, static_evidence=evidence)["valid"]
    assert verification["subject_ref"] == {
        "object_type": "STATIC_EVIDENCE",
        "object_id": evidence["evidence_receipt_id"],
        "object_version": evidence["evidence_receipt_version"],
    }
    assert len({decision["roles"]["forecaster_id"], decision["roles"]["custodian_id"], evidence["curator_id"]}) == 3
    assert contract["outcome_acquisition_route"]["organization_id"] == "gssz0000921"


def test_cn000921_runner_freezes_only_preoutcome_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision, contract, evidence, prediction, verification = _objects()
    database = tmp_path / "cn000921-minimal.db"
    source_receipt_path = tmp_path / "source-receipt.json"

    class FakePdfResponse:
        def __enter__(self) -> "FakePdfResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def geturl(self) -> str:
            return evidence["source"]["source_url"]

        def read(self) -> bytes:
            return b"%PDF-synthetic-cn000921-page-72"

    selected_pages: list[tuple[str, str]] = []

    def fake_pdftotext(args: list[str], **_: object) -> SimpleNamespace:
        start = args[args.index("-f") + 1]
        end = args[args.index("-l") + 1]
        selected_pages.append((start, end))
        return SimpleNamespace(stdout=verification["exact_quote"])

    monkeypatch.setattr(runner, "urlopen", lambda *_args, **_kwargs: FakePdfResponse())
    monkeypatch.setattr(runner.subprocess, "run", fake_pdftotext)
    frozen = runner.freeze_preoutcome(
        database,
        decision_contract_path=_write(tmp_path, "decision.json", decision),
        contract_path=_write(tmp_path, "contract.json", contract),
        evidence_path=_write(tmp_path, "evidence.json", evidence),
        prediction_path=_write(tmp_path, "prediction.json", prediction),
        source_verification_path=_write(tmp_path, "verification.json", verification),
        source_receipt_output_path=source_receipt_path,
        technical_route_resolver=lambda code: {"security_code": code, "organization_id": "gssz0000921"},
    )
    assert frozen["stage"] == "PRE_OUTCOME_FROZEN"
    assert selected_pages == [("72", "72")]
    assert json.loads(source_receipt_path.read_text(encoding="utf-8"))["numeric_value"] == 26730219497.07

    conn = sqlite3.connect(database)
    try:
        assert sum(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
            control.DECISION_CONTRACT_TABLE, control.TECHNICAL_ROUTE_IDENTITY_TABLE,
            control.CONTRACT_TABLE, control.EVIDENCE_TABLE, control.PREDICTION_TABLE,
        )) == 5
        assert sum(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
            control.ACCESS_TABLE, control.OUTCOME_SOURCE_INVENTORY_TABLE,
            control.OBSERVATION_TABLE, control.SETTLEMENT_TABLE,
        )) == 0
    finally:
        conn.close()


def test_cn000921_static_evidence_rejects_metric_or_boundary_drift() -> None:
    _, contract, evidence, _, _ = _objects()
    for field, invalid in (("metric_id", "OTHER_FIELD"), ("responsibility_boundary", "PARENT"), ("unit", "CNY")):
        drifted = deepcopy(evidence)
        drifted["source"][field] = invalid
        assert episode.validate_static_evidence(drifted, measurement_contract=contract)["valid"] is False
