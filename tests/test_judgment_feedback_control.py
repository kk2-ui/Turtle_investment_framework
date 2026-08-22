from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "judgment_feedback_control.py"
REPO_ROOT = MODULE_PATH.parents[1]
SPEC = importlib.util.spec_from_file_location("judgment_feedback_control", MODULE_PATH)
assert SPEC and SPEC.loader
jfc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jfc)


def _artifact(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text("{}\n", encoding="utf-8")
    return str(path)


def _manifest(tmp_path: Path, *, policy: str = "INITIAL_DISCLOSURE") -> dict:
    frozen = _artifact(tmp_path, "thesis_test.json")
    source = _artifact(tmp_path, "outcome_contract.json")
    measurement = _artifact(tmp_path, "measurement_contract.json")
    return {
        "schema_version": "judgment-feedback-control-registration.v1",
        "episode_id": "R-TEST-01",
        "company_id": "CN:TEST",
        "frozen_at": "2026-01-01T09:00:00+08:00",
        "claims": [
            {
                "claim_id": "FJ:DEMAND",
                "stages": [
                    {
                        "stage_id": "S1_DECISION",
                        "source_kind": "OFFICIAL_COMPANY_DISCLOSURE",
                        "source_ref": "official:Q1",
                        "eligible_at": "2026-03-31T23:59:59+08:00",
                        "settlement_version_policy": policy,
                        "frozen_artifact_ref": frozen,
                        "source_contract_ref": source,
                        "measurement_contract_ref": measurement,
                    },
                    {
                        "stage_id": "S2_UNIT_ECONOMICS",
                        "source_kind": "OFFICIAL_COMPANY_DISCLOSURE",
                        "source_ref": "official:H1",
                        "eligible_at": "2026-08-31T23:59:59+08:00",
                        "overdue_at": "2026-10-01T23:59:59+08:00",
                        "settlement_version_policy": policy,
                        "frozen_artifact_ref": frozen,
                        "source_contract_ref": source,
                        "measurement_contract_ref": measurement,
                    },
                ],
            }
        ],
    }


def _conn(tmp_path: Path):
    conn = jfc.connect(tmp_path / "stock_analysis.db")
    jfc.initialize(conn)
    return conn


def _event(item: str, event_type: str, effective_at: str, *, key: str, payload: dict | None = None) -> dict:
    return {
        "event_id": f"EVT:{key}",
        "feedback_item_id": item,
        "event_type": event_type,
        "effective_at": effective_at,
        "actor_role": "SYSTEM" if event_type.startswith("ACQUISITION") else "RESEARCHER",
        "actor_id": "agent-a",
        "idempotency_key": key,
        "artifact_refs": ["artifact:fixture"],
        "payload": payload or {},
    }


def _registered(tmp_path: Path):
    conn = _conn(tmp_path)
    jfc.register_manifest(conn, _manifest(tmp_path), registered_at="2026-01-01T10:00:00+08:00")
    return conn, "FBI:R-TEST-01:FJ:DEMAND:S1_DECISION", "FBI:R-TEST-01:FJ:DEMAND:S2_UNIT_ECONOMICS"


def test_registers_each_stage_and_derives_waiting_then_single_due_item(tmp_path: Path) -> None:
    conn, s1, s2 = _registered(tmp_path)
    assert jfc.show(conn, s1, as_of="2026-01-02T00:00:00+08:00")["events"][0]["event_type"] == "CLAIM_REGISTERED"
    before = jfc.reconcile(conn, as_of="2026-03-30T23:59:59+08:00")
    assert [item["feedback_item_id"] for item in before["items"]] == [s1, s2]
    assert {item["time_state"] for item in before["items"]} == {"WAITING"}

    due = jfc.reconcile(conn, as_of="2026-04-01T00:00:00+08:00")
    by_id = {item["feedback_item_id"]: item for item in due["items"]}
    assert by_id[s1]["time_state"] == "DUE"
    assert by_id[s1]["priority"] == "P1"
    assert by_id[s2]["time_state"] == "WAITING"


def test_pre_due_outcome_acquisition_is_rejected(tmp_path: Path) -> None:
    conn, s1, _ = _registered(tmp_path)
    with pytest.raises(jfc.ControlPlaneError, match="before eligible_at"):
        jfc.append_event(conn, _event(s1, "ACQUISITION_STARTED", "2026-03-01T00:00:00+08:00", key="early"))


def test_event_sequence_and_idempotency_are_append_only(tmp_path: Path) -> None:
    conn, s1, _ = _registered(tmp_path)
    at = "2026-04-01T00:00:00+08:00"
    first = jfc.append_event(conn, _event(s1, "ACQUISITION_STARTED", at, key="acquire"))
    repeat = jfc.append_event(conn, _event(s1, "ACQUISITION_STARTED", at, key="acquire"))
    assert first["idempotent"] is False
    assert repeat == {"schema_version": jfc.SCHEMA_VERSION, "event_id": "EVT:acquire", "idempotent": True}
    with pytest.raises(jfc.ControlPlaneError, match="different content"):
        jfc.append_event(conn, _event(s1, "ACQUISITION_BLOCKED", at, key="acquire"))
    with pytest.raises(jfc.ControlPlaneError, match="requires OUTCOME_PACKAGE_READY"):
        jfc.append_event(conn, _event(s1, "READ_ATTESTED", at, key="read-too-early"))

    jfc.append_event(conn, _event(s1, "OUTCOME_PACKAGE_READY", at, key="package"))
    jfc.append_event(conn, _event(s1, "READ_ATTESTED", at, key="read"))
    jfc.append_event(conn, _event(s1, "OUTCOME_EXTRACTED", at, key="extract"))
    jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="settle", payload={"settlement_verdict": "A_ONLY"}))
    item = jfc.show(conn, s1, as_of=at)
    assert item["states"]["evidence_state"] == "EXTRACTED"
    assert item["states"]["settlement_state"] == "A_ONLY"
    assert item["states"]["learning_state"] == "DIAGNOSIS_PENDING"
    with pytest.raises(jfc.ControlPlaneError, match="accepts only one settlement"):
        jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="settle-2", payload={"settlement_verdict": "B_ONLY"}))


def test_a_later_acquisition_cannot_retroactively_authorize_an_earlier_package(tmp_path: Path) -> None:
    conn, s1, _ = _registered(tmp_path)
    jfc.append_event(conn, _event(s1, "ACQUISITION_STARTED", "2026-04-02T00:00:00+08:00", key="late-acquire"))
    with pytest.raises(jfc.ControlPlaneError, match="requires ACQUISITION_STARTED"):
        jfc.append_event(conn, _event(s1, "OUTCOME_PACKAGE_READY", "2026-04-01T00:00:00+08:00", key="backdated-package"))


def test_latest_official_policy_requires_an_ordered_version_chain(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    manifest = _manifest(tmp_path, policy="LATEST_OFFICIAL_AS_OF_EVALUATION")
    jfc.register_manifest(conn, manifest)
    s1 = "FBI:R-TEST-01:FJ:DEMAND:S1_DECISION"
    at = "2026-04-01T00:00:00+08:00"
    for event_type, key in (("ACQUISITION_STARTED", "a"), ("OUTCOME_PACKAGE_READY", "p"), ("READ_ATTESTED", "r"), ("OUTCOME_EXTRACTED", "x")):
        jfc.append_event(conn, _event(s1, event_type, at, key=key))
    with pytest.raises(jfc.ControlPlaneError, match="increase by one"):
        jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="bad-version", payload={"settlement_verdict": "A_ONLY", "settlement_version": 2}))
    jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="v1", payload={"settlement_verdict": "A_ONLY", "settlement_version": 1}))
    with pytest.raises(jfc.ControlPlaneError, match="reference prior"):
        jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="v2-bad", payload={"settlement_verdict": "B_ONLY", "settlement_version": 2}))
    jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="v2", payload={"settlement_verdict": "B_ONLY", "settlement_version": 2, "supersedes_event_id": "EVT:v1"}))
    assert jfc.show(conn, s1, as_of=at)["states"]["settlement_state"] == "B_ONLY"


def _diagnosis(settlement_event_id: str) -> dict:
    return {
        "settlement_event_id": settlement_event_id,
        "epistemic_failure_locus": "MECHANISM",
        "delivery_root_cause": "REASONING",
        "economic_impact": "unit economics would be misread",
        "missing_facts": "customer-level evidence remains unavailable",
        "prohibited_assumptions": "do not infer customer retention from revenue alone",
        "executable_remediation": "bind customer response to the next freeze",
        "acceptance_criteria": "next company card contains the response contract",
    }


def test_learning_application_requires_real_cross_company_change_and_reviewer(tmp_path: Path) -> None:
    conn, s1, _ = _registered(tmp_path)
    at = "2026-04-01T00:00:00+08:00"
    for event_type, key in (("ACQUISITION_STARTED", "a"), ("OUTCOME_PACKAGE_READY", "p"), ("READ_ATTESTED", "r"), ("OUTCOME_EXTRACTED", "x")):
        jfc.append_event(conn, _event(s1, event_type, at, key=key))
    jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="settle", payload={"settlement_verdict": "B_ONLY"}))
    jfc.append_event(conn, _event(s1, "DIAGNOSIS_ACCEPTED", at, key="diagnosis", payload=_diagnosis("EVT:settle")))
    jfc.append_event(conn, _event(s1, "LEARNING_NOTE_READY", at, key="note", payload={
        "diagnosis_event_id": "EVT:diagnosis",
        "learning_note_ref": _artifact(tmp_path, "learning_note.json"),
    }))
    same_company = {
        "learning_note_event_id": "EVT:note",
        "application_scope": "METHOD_TRANSFER",
        "target_episode_id": "R-TEST-02",
        "target_company_id": "CN:TEST",
        "target_frozen_artifact_ref": _artifact(tmp_path, "next_thesis.json"),
        "target_frozen_at": "2026-03-31T00:00:00+08:00",
        "changed_field_ref": "forward_judgments[0].customer_response_contract",
        "before_method_meaning": "no customer clock",
        "after_method_meaning": "customer clock frozen",
        "change_reason": "source episode learning",
        "reviewer_id": "reviewer-b",
        "target_author_id": "author-a",
        "reviewer_acceptance": "ACCEPTED",
    }
    with pytest.raises(jfc.ControlPlaneError, match="different company"):
        jfc.append_event(conn, _event(s1, "LEARNING_APPLIED", at, key="same-company", payload=same_company))
    same_company["target_company_id"] = "CN:OTHER"
    same_company["reviewer_id"] = "author-a"
    with pytest.raises(jfc.ControlPlaneError, match="must differ"):
        jfc.append_event(conn, _event(s1, "LEARNING_APPLIED", at, key="not-independent", payload=same_company))
    same_company["reviewer_id"] = "reviewer-b"
    jfc.append_event(conn, _event(s1, "LEARNING_APPLIED", at, key="applied", payload=same_company))
    assert jfc.show(conn, s1, as_of=at)["states"]["learning_state"] == "REPLICATION_PENDING"


def test_measurement_mismatch_cannot_create_learning_note(tmp_path: Path) -> None:
    conn, s1, _ = _registered(tmp_path)
    at = "2026-04-01T00:00:00+08:00"
    for event_type, key in (("ACQUISITION_STARTED", "a"), ("OUTCOME_PACKAGE_READY", "p"), ("READ_ATTESTED", "r"), ("OUTCOME_EXTRACTED", "x")):
        jfc.append_event(conn, _event(s1, event_type, at, key=key))
    jfc.append_event(conn, _event(s1, "MEASUREMENT_MISMATCH", at, key="mismatch"))
    jfc.append_event(conn, _event(s1, "DIAGNOSIS_ACCEPTED", at, key="diagnosis", payload=_diagnosis("EVT:mismatch")))
    with pytest.raises(jfc.ControlPlaneError, match="cannot create method learning"):
        jfc.append_event(conn, _event(s1, "LEARNING_NOTE_READY", at, key="note", payload={
            "diagnosis_event_id": "EVT:diagnosis",
            "learning_note_ref": _artifact(tmp_path, "learning_note.json"),
        }))


def test_restart_derives_the_same_inbox(tmp_path: Path) -> None:
    db = tmp_path / "stock_analysis.db"
    conn, _, _ = _registered(tmp_path)
    first = jfc.reconcile(conn, as_of="2026-04-01T00:00:00+08:00")
    conn.close()
    second_conn = jfc.connect(db)
    jfc.initialize(second_conn)
    second = jfc.reconcile(second_conn, as_of="2026-04-01T00:00:00+08:00")
    assert first == second


def test_register_experiment_requires_explicit_contract_and_resolves_local_artifacts(tmp_path: Path) -> None:
    experiment = tmp_path / "R-TEST-01"
    experiment.mkdir()
    for name in ("thesis_test.json", "outcome_contract.json", "measurement_contract.json"):
        _artifact(experiment, name)
    manifest = _manifest(experiment)
    for stage in manifest["claims"][0]["stages"]:
        stage["frozen_artifact_ref"] = "thesis_test.json"
        stage["source_contract_ref"] = "outcome_contract.json"
        stage["measurement_contract_ref"] = "measurement_contract.json"
    (experiment / "judgment_feedback_control.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = jfc._command_register(argparse.Namespace(
        db=str(tmp_path / "stock_analysis.db"), experiment_dir=str(experiment), registered_at="2026-01-01T10:00:00+08:00",
    ))
    assert len(result["registered"]) == 2
    conn = jfc.connect(tmp_path / "stock_analysis.db")
    claim = jfc.show(conn, "FBI:R-TEST-01:FJ:DEMAND:S1_DECISION")["claim"]
    assert claim["frozen_artifact_ref"] == str((experiment / "thesis_test.json").resolve())


def test_projects_a_real_forward_contract_into_separate_due_clocks(tmp_path: Path) -> None:
    experiment = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-05_prospective_operating_feedback"
    contract = experiment / "08_outcome_acquisition_contract.json"
    conn = _conn(tmp_path)
    result = jfc.register_live_forward_contract(
        conn,
        contract_path=contract,
        registered_at="2026-08-22T12:00:00+08:00",
    )
    assert len(result["registered"]) == 2
    first = "FBI:R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821:R05-S1:EARLY_MECHANISM"
    second = "FBI:R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821:R05-S2:CONTINUATION_SIGNAL"
    waiting = jfc.reconcile(conn, as_of="2027-01-01T00:00:00-08:00")
    states = {item["feedback_item_id"]: item["time_state"] for item in waiting["items"]}
    assert states[first] == "WAITING"
    assert states[second] == "WAITING"
    due = jfc.reconcile(conn, as_of="2027-01-01T00:00:01-08:00")
    states = {item["feedback_item_id"]: item["time_state"] for item in due["items"]}
    assert states[first] == "DUE"
    assert states[second] == "WAITING"
    assert jfc.show(conn, first)["claim"]["measurement_contract_ref"].endswith("/metric_reconstruction_contract")


def test_sync_keeps_a_bad_forward_contract_visible(tmp_path: Path) -> None:
    root = tmp_path / "experiments"
    bad = root / "R-BAD"
    bad.mkdir(parents=True)
    (bad / "08_outcome_acquisition_contract.json").write_text("{}\n", encoding="utf-8")
    conn = _conn(tmp_path)
    synced = jfc.sync_live_forward_contracts(conn, contract_root=root)
    assert synced["registered"] == []
    assert synced["issues"][0]["code"] == "live_forward_contract_not_reviewable"


def test_cjo_entry_surfaces_the_persistent_control_plane_inbox(tmp_path: Path) -> None:
    source = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-05_prospective_operating_feedback"
    target = tmp_path / "docs" / "development" / "research" / "experiments" / source.name
    target.mkdir(parents=True)
    for name in ("06_forward_freeze.md", "08_outcome_acquisition_contract.json"):
        shutil.copy2(source / name, target / name)
    run_path = REPO_ROOT / "scripts" / "turtle_agent" / "run.py"
    run_spec = importlib.util.spec_from_file_location("turtle_agent_run_control_test", run_path)
    assert run_spec and run_spec.loader
    run = importlib.util.module_from_spec(run_spec)
    run_spec.loader.exec_module(run)
    previous_root = run._FRAMEWORK_DIR
    run._FRAMEWORK_DIR = str(tmp_path)
    try:
        surfaced = run._surface_live_forward_due_inbox()
    finally:
        run._FRAMEWORK_DIR = previous_root
    assert not surfaced["sync"]["issues"]
    assert len(surfaced["inbox"]["items"]) == 2
    assert (tmp_path / "stock_analysis.db").is_file()
