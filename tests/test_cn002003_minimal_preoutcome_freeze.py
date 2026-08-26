from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from scripts import minimal_historical_episode as episode
from scripts import minimal_historical_episode_control_plane as control
from scripts import minimal_historical_episode_runner as runner


_COHORTS = Path("docs/development/research/cohorts")
_CURATOR_PATH = _COHORTS / "CN002003_FY2018_OPERATING_REVENUE_RMB_PREOUTCOME_CURATOR_SUBMISSION.json"
_DECISION_PATH = _COHORTS / "CN002003_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_DECISION_CONTRACT.json"
_CONTRACT_PATH = _COHORTS / "CN002003_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_MEASUREMENT_CONTRACT.json"
_EVIDENCE_PATH = _COHORTS / "CN002003_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_STATIC_EVIDENCE.json"
_PREDICTION_PATH = _COHORTS / "CN002003_FY2020_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_PREDICTION.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cn002003_v1_artifacts_remain_readable_but_cannot_start_a_new_episode(
    tmp_path: Path, monkeypatch,
) -> None:
    """The v1 record is readable history, never a route-less new custody flow."""
    curator = _load(_CURATOR_PATH)
    decision = _load(_DECISION_PATH)
    contract = _load(_CONTRACT_PATH)
    evidence = _load(_EVIDENCE_PATH)
    prediction = _load(_PREDICTION_PATH)

    assert curator["information_boundary"]["read_inputs"] == [
        "H1:COHORT:CN:TEXTILE_APPAREL_EXPORT_MANUFACTURING:20191231:STATIC:V1@1",
        curator["source"]["source_id"],
    ]
    assert evidence["curator_id"] == curator["curator_identity"]["curator_id"]
    assert evidence["source"]["source_id"] == curator["source"]["source_id"]
    assert evidence["source"]["source_url"] == curator["source"]["source_url"]
    assert evidence["source"]["field_ref"] == curator["source"]["field_ref"]
    assert evidence["source"]["numeric_value"] == curator["source"]["numeric_value"]
    assert len({
        evidence["curator_id"], decision["roles"]["forecaster_id"], decision["roles"]["custodian_id"],
    }) == 3
    for payload in (decision, contract, evidence, prediction):
        assert payload["allowed_outputs"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert payload["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"

    verification = {
        "schema_version": runner.SOURCE_VERIFICATION_INPUT_SCHEMA_VERSION,
        "subject_ref": {
            "object_type": "STATIC_EVIDENCE",
            "object_id": evidence["evidence_receipt_id"],
            "object_version": evidence["evidence_receipt_version"],
        },
        "source_id": evidence["source"]["source_id"],
        "source_url": evidence["source"]["source_url"],
        "exact_quote": curator["source"]["exact_quote"],
        "numeric_value": evidence["source"]["numeric_value"],
        "unit": evidence["source"]["unit"],
        "allowed_outputs": ["MECHANICAL_SETTLEMENT_ONLY"],
        "method_transfer_rights": "NO_METHOD_TRANSFER_RIGHTS",
    }

    class FakePdfResponse:
        def __enter__(self) -> "FakePdfResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def geturl(self) -> str:
            return evidence["source"]["source_url"]

        def read(self) -> bytes:
            return b"%PDF-synthetic-cn002003-page-71"

    selected_pages: list[tuple[str, str]] = []

    def fake_pdftotext(args: list[str], **_: object) -> SimpleNamespace:
        start = args[args.index("-f") + 1]
        end = args[args.index("-l") + 1]
        selected_pages.append((start, end))
        return SimpleNamespace(stdout=curator["source"]["exact_quote"])

    monkeypatch.setattr(runner, "urlopen", lambda *_args, **_kwargs: FakePdfResponse())
    monkeypatch.setattr(runner.subprocess, "run", fake_pdftotext)

    database = tmp_path / "cn002003-minimal-episode.db"
    source_receipt_path = tmp_path / "cn002003-preoutcome-source-receipt.json"
    assert episode.validate_decision_contract(decision)["valid"]
    assert episode.validate_measurement_contract(contract, decision_contract=decision)["valid"]
    assert episode.validate_static_evidence(evidence, measurement_contract=contract)["valid"]
    assert episode.validate_prediction(prediction, measurement_contract=contract, static_evidence=evidence)["valid"]
    with pytest.raises(control.MinimalHistoricalEpisodeError) as exc_info:
        runner.freeze_preoutcome(
            database,
            decision_contract_path=_DECISION_PATH,
            contract_path=_CONTRACT_PATH,
            evidence_path=_EVIDENCE_PATH,
            prediction_path=_PREDICTION_PATH,
            source_verification_path=_write_json(tmp_path / "source-verification.json", verification),
            source_receipt_output_path=source_receipt_path,
        )
    assert exc_info.value.code == "measurement_contract_v2_required"
    assert selected_pages == []
    assert not source_receipt_path.exists()
    assert not database.exists()


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
