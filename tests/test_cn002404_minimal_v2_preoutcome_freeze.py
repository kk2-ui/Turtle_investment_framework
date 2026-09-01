"""Freeze CN002404's V2 Minimal Historical Episode before outcome access."""

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


_COHORTS = Path("docs/development/research/cohorts")
_CURATOR_PATH = _COHORTS / "CN002404_FY2018_OPERATING_REVENUE_RMB_PREOUTCOME_CURATOR_SUBMISSION.json"
_DECISION_PATH = _COHORTS / "CN002404_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_DECISION_CONTRACT.json"
_CONTRACT_PATH = _COHORTS / "CN002404_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_MEASUREMENT_CONTRACT.json"
_EVIDENCE_PATH = _COHORTS / "CN002404_FY2018_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_STATIC_EVIDENCE.json"
_PREDICTION_PATH = _COHORTS / "CN002404_FY2020_OPERATING_REVENUE_RMB_MINIMAL_HISTORICAL_EPISODE_V2_PREDICTION.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _source_verification(evidence: dict, curator: dict) -> dict:
    return {
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
        "allowed_outputs": list(episode.ALLOWED_OUTPUTS),
        "method_transfer_rights": episode.NO_METHOD_TRANSFER_RIGHTS,
    }


def test_cn002404_v2_freezes_controller_resolved_route_and_four_preoutcome_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source remains pre-cutoff; no outcome-stage row can appear here."""
    curator = _load(_CURATOR_PATH)
    decision = _load(_DECISION_PATH)
    contract = _load(_CONTRACT_PATH)
    evidence = _load(_EVIDENCE_PATH)
    prediction = _load(_PREDICTION_PATH)

    # The independent curator supplied only the cutoff-before field.  The
    # technical identity is resolved by the controller, not supplied in the
    # curator handoff.
    assert "organization_id" not in curator["source"]
    assert curator["controller_handoff"]["curator_scope"] == "STATIC_BASELINE_ONLY_NO_TECHNICAL_ROUTE_OR_OUTCOME_METADATA"
    assert evidence["curator_id"] == curator["curator_identity"]["curator_id"]
    assert evidence["source"]["source_id"] == curator["source"]["source_id"]
    assert evidence["source"]["source_url"] == curator["source"]["source_url"]
    assert evidence["source"]["field_ref"] == curator["source"]["field_ref"]
    assert evidence["source"]["numeric_value"] == curator["source"]["numeric_value"]
    assert len({
        evidence["curator_id"], decision["roles"]["forecaster_id"], decision["roles"]["custodian_id"],
    }) == 3
    assert contract["schema_version"] == episode.MEASUREMENT_CONTRACT_SCHEMA_VERSION
    assert contract["outcome_acquisition_route"]["security_code"] == "002404"
    assert contract["outcome_acquisition_route"]["organization_id"] == "9900012350"
    for payload in (decision, contract, evidence, prediction):
        assert payload["allowed_outputs"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert payload["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"

    assert episode.validate_decision_contract(decision)["valid"]
    assert episode.validate_measurement_contract(contract, decision_contract=decision)["valid"]
    assert episode.validate_static_evidence(evidence, measurement_contract=contract)["valid"]
    assert episode.validate_prediction(prediction, measurement_contract=contract, static_evidence=evidence)["valid"]

    class MockPdfResponse:
        def __enter__(self) -> "MockPdfResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def geturl(self) -> str:
            return evidence["source"]["source_url"]

        def read(self) -> bytes:
            return b"%PDF-1.7 mocked CNINFO cutoff-before source"

    def mocked_urlopen(request: object, *, timeout: int) -> MockPdfResponse:
        assert getattr(request, "full_url") == evidence["source"]["source_url"]
        assert timeout == 60
        return MockPdfResponse()

    def mocked_pdftotext(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert command[:6] == ["pdftotext", "-f", "86", "-l", "86", "-layout"]
        assert command[-1] == "-"
        assert kwargs == {"check": True, "capture_output": True, "text": True}
        return SimpleNamespace(stdout=f"page 86\n{curator['source']['exact_quote']}\n")

    monkeypatch.setattr(runner, "urlopen", mocked_urlopen)
    monkeypatch.setattr(runner.subprocess, "run", mocked_pdftotext)
    resolver_calls: list[str] = []

    def mocked_route_resolver(security_code: str) -> dict[str, str]:
        resolver_calls.append(security_code)
        return {"security_code": "002404", "organization_id": "9900012350"}

    database = tmp_path / "cn002404-v2-preoutcome.sqlite"
    source_receipt_path = tmp_path / "cn002404-v2-static-source-receipt.json"
    frozen = runner.freeze_preoutcome(
        database,
        decision_contract_path=_DECISION_PATH,
        contract_path=_CONTRACT_PATH,
        evidence_path=_EVIDENCE_PATH,
        prediction_path=_PREDICTION_PATH,
        source_verification_path=_write_json(
            tmp_path / "cn002404-v2-source-verification.json", _source_verification(evidence, curator),
        ),
        technical_route_resolver=mocked_route_resolver,
        source_receipt_output_path=source_receipt_path,
    )

    assert resolver_calls == ["002404"]
    assert frozen["stage"] == "PRE_OUTCOME_FROZEN"
    assert frozen["technical_route_identity_id"] == "MHE:ROUTE:CN002404:FY2018:V1"
    chronology = frozen["recorded_chronology"]
    assert (
        chronology["decision_contract_frozen_at"]
        < chronology["technical_route_identity_frozen_at"]
        < chronology["contract_frozen_at"]
        < chronology["evidence_frozen_at"]
        < chronology["prediction_frozen_at"]
    )
    source_receipt = _load(source_receipt_path)
    assert source_receipt["source_id"] == curator["source"]["source_id"]
    assert source_receipt["field_ref"] == curator["source"]["field_ref"]
    assert source_receipt["verification_state"] == "OPENED_OFFICIAL_PDF_FIELD_MATCHED"

    conn = sqlite3.connect(database)
    try:
        assert conn.execute(f"SELECT COUNT(*) FROM {control.DECISION_CONTRACT_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.TECHNICAL_ROUTE_IDENTITY_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.CONTRACT_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.EVIDENCE_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.PREDICTION_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {control.ACCESS_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OUTCOME_SOURCE_INVENTORY_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.OBSERVATION_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {control.SETTLEMENT_TABLE}").fetchone()[0] == 0
        route_payload = json.loads(
            conn.execute(f"SELECT payload_json FROM {control.TECHNICAL_ROUTE_IDENTITY_TABLE}").fetchone()[0]
        )
    finally:
        conn.close()
    assert route_payload["security_code"] == "002404"
    assert route_payload["organization_id"] == "9900012350"
    assert route_payload["resolver_endpoint"] == episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_ENDPOINT
    assert route_payload["resolver_version"] == episode.CNINFO_TECHNICAL_ROUTE_RESOLVER_VERSION


@pytest.mark.parametrize(
    ("path", "field", "replacement", "expected"),
    [
        (_EVIDENCE_PATH, "metric_id", "OTHER_REVENUE_METRIC", "metric_id_must_match_measurement_contract"),
        (_EVIDENCE_PATH, "responsibility_boundary", "PARENT_COMPANY_ONLY", "responsibility_boundary_must_match_measurement_contract"),
        (_EVIDENCE_PATH, "unit", "CNY_MILLIONS", "unit_must_match_measurement_contract"),
        (_EVIDENCE_PATH, "cutoff_at", "2020-12-31T23:59:59+08:00", "cutoff_at_must_match_measurement_contract"),
    ],
)
def test_cn002404_v2_rejects_static_measurement_drift(
    path: Path, field: str, replacement: str, expected: str,
) -> None:
    decision = _load(_DECISION_PATH)
    contract = _load(_CONTRACT_PATH)
    evidence = deepcopy(_load(path))
    if field in {"metric_id", "responsibility_boundary", "unit"}:
        evidence["source"][field] = replacement
    else:
        evidence[field] = replacement

    validation = episode.validate_static_evidence(evidence, measurement_contract=contract)

    assert episode.validate_measurement_contract(contract, decision_contract=decision)["valid"]
    assert not validation["valid"]
    assert f"static_evidence.{('source.' if field != 'cutoff_at' else '')}{expected}" in validation["findings"]


def test_cn002404_v2_freeze_has_no_caller_supplied_technical_route_override() -> None:
    parameters = set(inspect.signature(runner.freeze_preoutcome).parameters)

    assert "technical_route_identity_path" not in parameters
    assert "organization_id" not in parameters
    assert "outcome_acquisition_route" not in parameters
