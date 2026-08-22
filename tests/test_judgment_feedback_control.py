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

# Most tests below exercise ordering and state derivation in isolation.  They
# intentionally bypass the public API's lower-module boundary, which is
# covered separately by the adapter integration tests and the direct-forgery
# regression below.  Keeping this escape private to the test module prevents
# the production API from regressing into a hand-entered settlement channel.
_PUBLIC_APPEND_EVENT = jfc.append_event


def _append_transition(conn, event: dict):
    return jfc._append_event(conn, event, allow_adapter_events=True)


jfc.append_event = _append_transition


def _artifact(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text("{}\n", encoding="utf-8")
    return str(path)


def _manifest(tmp_path: Path, *, policy: str = "INITIAL_DISCLOSURE", selection: bool = False) -> dict:
    frozen = _artifact(tmp_path, "thesis_test.json")
    source = _artifact(tmp_path, "outcome_contract.json")
    measurement = _artifact(tmp_path, "measurement_contract.json")
    manifest = {
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
    if selection:
        manifest.update({
            "episode_class": "JUDGMENT_SELECTION_EPISODE",
            "selection_status": "SELECTION_ADMITTED",
            "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
        })
    return manifest


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
        "artifact_refs": [str(MODULE_PATH)],
        "payload": payload or {},
    }


def _registered(tmp_path: Path, *, selection: bool = False):
    conn = _conn(tmp_path)
    jfc.register_manifest(conn, _manifest(tmp_path, selection=selection), registered_at="2026-01-01T10:00:00+08:00")
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
    conn, s1, _ = _registered(tmp_path, selection=True)
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
        jfc.append_event(conn, _event(s1, event_type, at, key=key, payload={"settlement_version": 1}))
    with pytest.raises(jfc.ControlPlaneError, match="next unsettled version"):
        jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="bad-version", payload={"settlement_verdict": "A_ONLY", "settlement_version": 2}))
    jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="v1", payload={"settlement_verdict": "A_ONLY", "settlement_version": 1}))
    with pytest.raises(jfc.ControlPlaneError, match="OUTCOME_EXTRACTED for the same settlement version"):
        jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="v2-no-chain", payload={"settlement_verdict": "B_ONLY", "settlement_version": 2, "supersedes_event_id": "EVT:v1"}))
    for event_type, key in (("ACQUISITION_STARTED", "a2"), ("OUTCOME_PACKAGE_READY", "p2"), ("READ_ATTESTED", "r2"), ("OUTCOME_EXTRACTED", "x2")):
        jfc.append_event(conn, _event(s1, event_type, "2026-04-02T00:00:00+08:00", key=key, payload={"settlement_version": 2}))
    with pytest.raises(jfc.ControlPlaneError, match="reference prior"):
        jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", "2026-04-02T00:00:00+08:00", key="v2-bad", payload={"settlement_verdict": "B_ONLY", "settlement_version": 2}))
    jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", "2026-04-02T00:00:00+08:00", key="v2", payload={"settlement_verdict": "B_ONLY", "settlement_version": 2, "supersedes_event_id": "EVT:v1"}))
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
    conn, s1, _ = _registered(tmp_path, selection=True)
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
    with pytest.raises(jfc.ControlPlaneError, match="real settled target claim"):
        jfc.append_event(conn, _event(s1, "REPLICATION_ACCEPTED", "2026-04-02T00:00:00+08:00", key="fake-replication", payload={
            "learning_application_event_id": "EVT:applied",
            "replication_settlement_event_id": "EVT:NONEXISTENT",
            "reviewer_id": "reviewer-c", "reviewer_receipt_ref": _artifact(tmp_path, "reviewer_receipt.json"),
            "reviewer_acceptance": "ACCEPTED",
        }))

    unrelated_manifest = _manifest(tmp_path, selection=True)
    unrelated_manifest["episode_id"] = "R-UNRELATED"
    unrelated_manifest["company_id"] = "CN:UNRELATED"
    jfc.register_manifest(conn, unrelated_manifest)
    unrelated = "FBI:R-UNRELATED:FJ:DEMAND:S1_DECISION"
    for event_type, key in (("ACQUISITION_STARTED", "unrelated-a"), ("OUTCOME_PACKAGE_READY", "unrelated-p"), ("READ_ATTESTED", "unrelated-r"), ("OUTCOME_EXTRACTED", "unrelated-x")):
        jfc.append_event(conn, _event(unrelated, event_type, "2026-04-02T00:00:00+08:00", key=key))
    jfc.append_event(conn, _event(unrelated, "CLAIM_SETTLED", "2026-04-02T00:00:00+08:00", key="unrelated-settle", payload={"settlement_verdict": "A_ONLY"}))
    with pytest.raises(jfc.ControlPlaneError, match="intended target"):
        jfc.append_event(conn, _event(s1, "REPLICATION_ACCEPTED", "2026-04-03T00:00:00+08:00", key="unrelated-replication", payload={
            "learning_application_event_id": "EVT:applied", "replication_settlement_event_id": "EVT:unrelated-settle",
            "reviewer_id": "reviewer-c", "reviewer_receipt_ref": _artifact(tmp_path, "unrelated_reviewer_receipt.json"),
            "reviewer_acceptance": "ACCEPTED",
        }))

    target_manifest = _manifest(tmp_path, selection=True)
    target_manifest["episode_id"] = "R-TEST-02"
    target_manifest["company_id"] = "CN:OTHER"
    target_manifest["claims"][0]["stages"][1]["eligible_at"] = "2026-04-01T00:00:00+08:00"
    jfc.register_manifest(conn, target_manifest)
    target = "FBI:R-TEST-02:FJ:DEMAND:S1_DECISION"
    for event_type, key in (("ACQUISITION_STARTED", "other-a"), ("OUTCOME_PACKAGE_READY", "other-p"), ("READ_ATTESTED", "other-r"), ("OUTCOME_EXTRACTED", "other-x")):
        jfc.append_event(conn, _event(target, event_type, "2026-04-02T00:00:00+08:00", key=key))
    jfc.append_event(conn, _event(target, "MEASUREMENT_MISMATCH", "2026-04-02T00:00:00+08:00", key="other-mismatch"))
    with pytest.raises(jfc.ControlPlaneError, match="real settled target claim"):
        jfc.append_event(conn, _event(s1, "REPLICATION_ACCEPTED", "2026-04-03T00:00:00+08:00", key="mismatch-replication", payload={
            "learning_application_event_id": "EVT:applied", "replication_settlement_event_id": "EVT:other-mismatch",
            "reviewer_id": "reviewer-c", "reviewer_receipt_ref": _artifact(tmp_path, "mismatch_reviewer_receipt.json"),
            "reviewer_acceptance": "ACCEPTED",
        }))
    target = "FBI:R-TEST-02:FJ:DEMAND:S2_UNIT_ECONOMICS"
    for event_type, key in (("ACQUISITION_STARTED", "other2-a"), ("OUTCOME_PACKAGE_READY", "other2-p"), ("READ_ATTESTED", "other2-r"), ("OUTCOME_EXTRACTED", "other2-x")):
        jfc.append_event(conn, _event(target, event_type, "2026-04-02T00:00:00+08:00", key=key))
    jfc.append_event(conn, _event(target, "CLAIM_SETTLED", "2026-04-02T00:00:00+08:00", key="other-settle", payload={"settlement_verdict": "A_ONLY"}))
    jfc.append_event(conn, _event(s1, "REPLICATION_ACCEPTED", "2026-04-03T00:00:00+08:00", key="real-replication", payload={
        "learning_application_event_id": "EVT:applied", "replication_settlement_event_id": "EVT:other-settle",
        "reviewer_id": "reviewer-c", "reviewer_receipt_ref": _artifact(tmp_path, "real_reviewer_receipt.json"),
        "reviewer_acceptance": "ACCEPTED",
    }))
    assert jfc.show(conn, s1, as_of="2026-04-03T00:00:00+08:00")["states"]["learning_state"] == "CLOSED"


def test_measurement_mismatch_cannot_create_learning_note(tmp_path: Path) -> None:
    conn, s1, _ = _registered(tmp_path, selection=True)
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


def test_no_primary_episode_can_settle_a_mechanism_but_cannot_create_method_learning(tmp_path: Path) -> None:
    conn, s1, _ = _registered(tmp_path)
    at = "2026-04-01T00:00:00+08:00"
    for event_type, key in (("ACQUISITION_STARTED", "a"), ("OUTCOME_PACKAGE_READY", "p"), ("READ_ATTESTED", "r"), ("OUTCOME_EXTRACTED", "x")):
        jfc.append_event(conn, _event(s1, event_type, at, key=key))
    jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", at, key="settle", payload={"settlement_verdict": "A_ONLY"}))
    jfc.append_event(conn, _event(s1, "DIAGNOSIS_ACCEPTED", at, key="diagnosis", payload=_diagnosis("EVT:settle")))
    with pytest.raises(jfc.ControlPlaneError, match="mechanism-only"):
        jfc.append_event(conn, _event(s1, "LEARNING_NOTE_READY", at, key="note", payload={
            "diagnosis_event_id": "EVT:diagnosis", "learning_note_ref": _artifact(tmp_path, "learning_note.json"),
        }))
    item = jfc.show(conn, s1, as_of=at)
    assert item["claim"]["selection_status"] == "NO_PRIMARY"
    assert item["states"]["settlement_state"] == "A_ONLY"
    assert item["states"]["learning_state"] == "NONE"


def test_latest_official_settlement_reopens_diagnosis_for_the_new_evidence_chain(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    jfc.register_manifest(conn, _manifest(tmp_path, policy="LATEST_OFFICIAL_AS_OF_EVALUATION", selection=True))
    s1 = "FBI:R-TEST-01:FJ:DEMAND:S1_DECISION"
    for version, when, verdict, supersedes in (
        (1, "2026-04-01T00:00:00+08:00", "A_ONLY", None),
        (2, "2026-04-02T00:00:00+08:00", "B_ONLY", "EVT:v1"),
    ):
        for event_type, suffix in (("ACQUISITION_STARTED", "a"), ("OUTCOME_PACKAGE_READY", "p"), ("READ_ATTESTED", "r"), ("OUTCOME_EXTRACTED", "x")):
            jfc.append_event(conn, _event(s1, event_type, when, key=f"{suffix}{version}", payload={"settlement_version": version}))
        payload = {"settlement_verdict": verdict, "settlement_version": version}
        if supersedes:
            payload["supersedes_event_id"] = supersedes
        jfc.append_event(conn, _event(s1, "CLAIM_SETTLED", when, key=f"v{version}", payload=payload))
        if version == 1:
            jfc.append_event(conn, _event(s1, "DIAGNOSIS_ACCEPTED", when, key="diagnosis-v1", payload=_diagnosis("EVT:v1")))
            assert jfc.show(conn, s1, as_of=when)["states"]["learning_state"] == "NOTE_READY"
    state = jfc.show(conn, s1, as_of="2026-04-02T01:00:00+08:00")
    assert state["states"]["settlement_state"] == "B_ONLY"
    assert state["states"]["learning_state"] == "DIAGNOSIS_PENDING"


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


def test_r54_is_registered_as_a_no_primary_mechanism_probe(tmp_path: Path) -> None:
    contract = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-54_midea_core_growth_20260430" / "08_outcome_acquisition_contract.json"
    conn = _conn(tmp_path)
    result = jfc.register_live_forward_contract(conn, contract_path=contract, registered_at="2026-08-22T12:00:00+08:00")
    assert result["registered"]
    item = result["registered"][0]["feedback_item_id"]
    claim = jfc.show(conn, item)["claim"]
    assert claim["episode_class"] == "MECHANISM_SIGNAL_PROBE"
    assert claim["selection_status"] == "NO_PRIMARY"
    assert claim["learning_eligibility"] == "MECHANISM_SETTLEMENT_ONLY"


def test_sync_keeps_a_bad_forward_contract_visible(tmp_path: Path) -> None:
    root = tmp_path / "experiments"
    bad = root / "R-BAD"
    bad.mkdir(parents=True)
    (bad / "08_outcome_acquisition_contract.json").write_text("{}\n", encoding="utf-8")
    conn = _conn(tmp_path)
    synced = jfc.sync_live_forward_contracts(conn, contract_root=root)
    assert synced["registered"] == []
    assert synced["issues"][0]["code"] == "live_forward_contract_not_reviewable"


def test_real_lower_adapters_move_a_due_mechanism_probe_from_p1_to_settlement(tmp_path: Path) -> None:
    """A due item must use raw/reader/extraction artifacts, not event labels."""
    contract = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-05_prospective_operating_feedback" / "08_outcome_acquisition_contract.json"
    conn = _conn(tmp_path)
    jfc.register_live_forward_contract(conn, contract_path=contract, registered_at="2026-08-22T12:00:00+08:00")
    item = "FBI:R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821:R05-S1:EARLY_MECHANISM"
    frozen = json.loads(contract.read_text(encoding="utf-8"))
    package_root = tmp_path / "outcome_package"
    event_root = tmp_path / "experiment"
    source_id = "IR:SBUX:FY2027Q1"
    source_manifest = {
        "schema_version": "turtle-post-cutoff-outcome-package.v1",
        "outcome_package_id": "OUTPKG:R05:S1:TEST",
        "case_id": frozen["case_id"], "freeze_id": frozen["report_freeze"]["freeze_id"],
        "frozen_cutoff": frozen["simulation_cutoff"],
        "enumeration": {"status": "COMPLETE", "query_identity": "issuer FY2027 Q1 result archive", "source_ids": [source_id]},
        "inventory": [{
            "source_id": source_id, "source_type": "OTHER_OFFICIAL", "official": True,
            "published_at": "2027-01-10T09:00:00-08:00", "source_version": "original-release-v1",
            "data_as_of": "2027-01-01", "revision_policy": "ORIGINAL_VINTAGE",
            "acquisition_kind": "OFFICIAL_WEB_RELEASE", "content_format": "HTML",
            "url": "https://investor.starbucks.com/fy2027q1", "release_id": "FY2027Q1",
            "publisher_name": "Starbucks Investor Relations", "official_publisher_domain": "investor.starbucks.com",
            "candidate_claim_ids": ["R05-S1"],
        }],
        "selected_source_ids": [source_id], "source_package_status": "INCOMPLETE",
    }
    source_manifest_path = tmp_path / "bounded_inventory.json"
    source_manifest_path.write_text(json.dumps(source_manifest), encoding="utf-8")
    at = "2027-01-15T12:00:00-08:00"
    outcome = frozen["calibration_ledger"]["claims"][0]["observable_outcome"]
    extraction = {
        "schema_version": "turtle-post-cutoff-outcome-extraction.v1", "outcome_package_id": source_manifest["outcome_package_id"],
        "case_id": frozen["case_id"], "freeze_id": frozen["report_freeze"]["freeze_id"], "settlement_as_of": at,
        "observations": [{
            "observation_id": "OBS:R05:S1:TEST", "claim_id": "R05-S1", "metric": outcome["metric"], "value": 1,
            "unit": outcome["unit"], "measurement_basis": outcome["measurement_basis"],
            "measurement_period": outcome["measurement_period"], "source_ids": [source_id], "comparability_status": "COMPARABLE",
            "reported_file_scope": "FY2027 Q1 results release", "reported_label": "North America Change in Transactions",
            "reported_locator": "North America comparable-sales results table",
            "reported_period_text": "Q1 Fiscal Year 2027",
            "reported_text": "Q1 Fiscal Year 2027 North America Change in Transactions 1",
            "reported_value_text": "1",
        }],
    }
    extraction_path = tmp_path / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")
    exposure = {
        "schema_version": "turtle-live-forward-exposure-attestation.v1", "case_id": frozen["case_id"],
        "freeze_id": frozen["report_freeze"]["freeze_id"], "settlement_as_of": at,
        "status": "NO_NONCLAIM_RESULT_EXPOSURE", "pipeline_read_source_ids": [source_id], "nonclaim_exposure_descriptions": [],
    }
    exposure_path = tmp_path / "exposure.json"
    exposure_path.write_text(json.dumps(exposure), encoding="utf-8")
    request_path = tmp_path / "09_outcome_execution.json"
    request = {
        "schema_version": jfc.DUE_EXECUTION_SCHEMA_VERSION, "feedback_item_id": item,
        "settlement_as_of": at, "outcome_manifest_ref": str(source_manifest_path),
        "package_root": str(package_root), "event_root": str(event_root),
        "extraction_ref": str(extraction_path), "exposure_attestation_ref": str(exposure_path),
        "settlement_id": "R05-S1-TEST",
    }
    pending_request = dict(request)
    pending_request.pop("extraction_ref")
    pending_request.pop("exposure_attestation_ref")
    request_path.write_text(json.dumps(pending_request), encoding="utf-8")
    pending = jfc.execute_due_claim(
        conn, execution_request_ref=request_path,
        downloader=lambda _: b"<html><body>Q1 Fiscal Year 2027 North America Change in Transactions 1</body></html>",
    )
    assert pending["status"] == "EXTRACTION_INPUT_REQUIRED"
    assert jfc.show(conn, item, as_of=at)["states"]["evidence_state"] == "READ_ATTESTED"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    settled = jfc.execute_due_claim(
        conn, execution_request_ref=request_path,
        downloader=lambda _: b"<html><body>Q1 Fiscal Year 2027 North America Change in Transactions 1</body></html>",
    )
    assert settled["status"] == "SETTLED"
    state = jfc.show(conn, item, as_of=at)
    assert state["states"]["settlement_state"] == "A_ONLY"
    assert state["states"]["learning_state"] == "NONE"
    priorities = {row["feedback_item_id"]: row["priority"] for row in jfc.reconcile(conn, as_of=at)["items"]}
    assert priorities[item] == "DONE"


def test_missing_lower_artifact_cannot_advance_a_due_claim(tmp_path: Path) -> None:
    conn, item, _ = _registered(tmp_path)
    with pytest.raises(jfc.ControlPlaneError, match="does not resolve to a file"):
        jfc.append_event(conn, {
            **_event(item, "ACQUISITION_STARTED", "2026-04-01T00:00:00+08:00", key="missing-artifact"),
            "artifact_refs": [str(tmp_path / "missing.json")],
        })


def test_public_api_cannot_forge_an_outcome_pipeline_event(tmp_path: Path) -> None:
    conn, item, _ = _registered(tmp_path)
    forged = _event(item, "ACQUISITION_STARTED", "2026-04-01T00:00:00+08:00", key="forged")
    with pytest.raises(jfc.ControlPlaneError, match="lower-module adapter"):
        _PUBLIC_APPEND_EVENT(conn, forged)


def test_real_lower_acquisition_failure_stays_blocked_at_p1(tmp_path: Path) -> None:
    contract = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-05_prospective_operating_feedback" / "08_outcome_acquisition_contract.json"
    conn = _conn(tmp_path)
    jfc.register_live_forward_contract(conn, contract_path=contract, registered_at="2026-08-22T12:00:00+08:00")
    item = "FBI:R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821:R05-S1:EARLY_MECHANISM"
    malformed_manifest = tmp_path / "malformed_inventory.json"
    malformed_manifest.write_text("{}\n", encoding="utf-8")
    result = jfc.run_outcome_acquisition(
        conn, feedback_item_id=item, outcome_manifest_ref=malformed_manifest, package_root=tmp_path / "package",
        event_root=tmp_path / "events", settlement_as_of="2027-01-15T12:00:00-08:00",
    )
    assert result["status"] == "BLOCKED"
    states = jfc.show(conn, item, as_of="2027-01-15T12:00:00-08:00")["states"]
    assert states["evidence_state"] == "BLOCKED"
    priorities = {row["feedback_item_id"]: row["priority"] for row in jfc.reconcile(conn, as_of="2027-01-15T12:00:00-08:00")["items"]}
    assert priorities[item] == "P1"


def test_legacy_live_forward_rows_are_backfilled_from_their_frozen_contracts(tmp_path: Path) -> None:
    """An upgraded control-plane DB must not re-register old rows as a new identity."""
    db_path = tmp_path / "legacy-control-plane.db"
    conn = jfc.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE judgment_feedback_claims (
          feedback_item_id TEXT PRIMARY KEY,
          episode_id TEXT NOT NULL,
          claim_id TEXT NOT NULL,
          stage_id TEXT NOT NULL,
          company_id TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          frozen_at TEXT NOT NULL,
          eligible_at TEXT NOT NULL,
          overdue_at TEXT,
          settlement_version_policy TEXT NOT NULL,
          frozen_artifact_ref TEXT NOT NULL,
          source_contract_ref TEXT NOT NULL,
          measurement_contract_ref TEXT NOT NULL,
          registered_at TEXT NOT NULL,
          UNIQUE (episode_id, claim_id, stage_id)
        );
        """
    )
    contract_paths = [
        REPO_ROOT / "docs" / "development" / "research" / "experiments" / name / "08_outcome_acquisition_contract.json"
        for name in (
            "R-05_prospective_operating_feedback",
            "R-06_prospective_retail_feedback",
            "R-54_midea_core_growth_20260430",
        )
    ]
    manifests = [
        jfc.live_forward_registration_manifest(json.loads(path.read_text(encoding="utf-8")), contract_path=path)
        for path in contract_paths
    ]
    legacy_columns = (
        "feedback_item_id", "episode_id", "claim_id", "stage_id", "company_id", "source_kind", "source_ref",
        "frozen_at", "eligible_at", "overdue_at", "settlement_version_policy", "frozen_artifact_ref",
        "source_contract_ref", "measurement_contract_ref", "registered_at",
    )
    for manifest in manifests:
        for item in jfc._expand_manifest(manifest):
            row = jfc._claim_fields(item, manifest=manifest, registered_at="2026-08-22T12:00:00+08:00")
            placeholders = ", ".join("?" for _ in legacy_columns)
            conn.execute(
                f"INSERT INTO judgment_feedback_claims ({', '.join(legacy_columns)}) VALUES ({placeholders})",
                tuple(row[column] for column in legacy_columns),
            )
    conn.commit()

    jfc.initialize(conn)
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 9
    r54 = conn.execute(
        """SELECT episode_class, selection_status, learning_eligibility
           FROM judgment_feedback_claims WHERE feedback_item_id = ?""",
        ("FBI:R-54:MIDEA:CORE_GROWTH_COMPLEXITY:20260430:R54-S3:WORKING_CAPITAL_CASH",),
    ).fetchone()
    assert tuple(r54) == ("MECHANISM_SIGNAL_PROBE", "NO_PRIMARY", "MECHANISM_SETTLEMENT_ONLY")

    synced = [jfc.register_live_forward_contract(conn, contract_path=path) for path in contract_paths]
    assert all(all(row["idempotent"] for row in result["registered"]) for result in synced)
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 9


def test_acquisition_retry_keeps_a_new_successful_receipt(tmp_path: Path) -> None:
    """A transient package failure must not make attempt two reuse BLOCKED JSON."""
    contract_path = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-05_prospective_operating_feedback" / "08_outcome_acquisition_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    conn = _conn(tmp_path)
    jfc.register_live_forward_contract(conn, contract_path=contract_path, registered_at="2026-08-22T12:00:00+08:00")
    item = "FBI:R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821:R05-S1:EARLY_MECHANISM"
    source_id = "IR:SBUX:FY2027Q1"
    inventory = {
        "schema_version": "turtle-post-cutoff-outcome-package.v1",
        "outcome_package_id": "OUTPKG:R05:S1:RETRY",
        "case_id": contract["case_id"], "freeze_id": contract["report_freeze"]["freeze_id"],
        "frozen_cutoff": contract["simulation_cutoff"],
        "enumeration": {"status": "COMPLETE", "query_identity": "issuer FY2027 Q1 result archive", "source_ids": [source_id]},
        "inventory": [{
            "source_id": source_id, "source_type": "OTHER_OFFICIAL", "official": True,
            "published_at": "2027-01-10T09:00:00-08:00", "source_version": "original-release-v1",
            "data_as_of": "2027-01-01", "revision_policy": "ORIGINAL_VINTAGE",
            "acquisition_kind": "OFFICIAL_WEB_RELEASE", "content_format": "HTML",
            "url": "https://investor.starbucks.com/fy2027q1", "release_id": "FY2027Q1",
            "publisher_name": "Starbucks Investor Relations", "official_publisher_domain": "investor.starbucks.com",
            "candidate_claim_ids": ["R05-S1"],
        }],
        "selected_source_ids": [source_id], "source_package_status": "INCOMPLETE",
    }
    inventory_path = tmp_path / "bounded_inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    package_root, event_root = tmp_path / "outcome_package", tmp_path / "events"
    as_of = "2027-01-15T12:00:00-08:00"

    malformed_path = tmp_path / "not-yet-published.json"
    malformed_path.write_text("{}\n", encoding="utf-8")
    first = jfc.run_outcome_acquisition(
        conn, feedback_item_id=item, outcome_manifest_ref=malformed_path, package_root=package_root,
        event_root=event_root, settlement_as_of=as_of,
    )
    assert first["status"] == "BLOCKED"

    second = jfc.run_outcome_acquisition(
        conn, feedback_item_id=item, outcome_manifest_ref=inventory_path, package_root=package_root,
        event_root=event_root, settlement_as_of=as_of,
        downloader=lambda _: b"<html>Q1 Fiscal Year 2027 North America Change in Transactions 1</html>",
    )
    assert second["status"] == "PACKAGE_READY"
    assert second["package_manifest_ref"] != first["receipt_ref"]
    assert "/attempt-02/" in second["package_manifest_ref"].replace("\\", "/")
    assert json.loads(Path(second["package_manifest_ref"]).read_text(encoding="utf-8"))["source_package_status"] == "COMPLETE"
    attestation = jfc.record_reader_attestation(
        conn, feedback_item_id=item, package_manifest_ref=second["package_manifest_ref"], package_root=package_root,
        event_root=event_root, settlement_as_of=as_of,
    )
    assert attestation["status"] == "READ_ATTESTED"


def test_r54_cash_clock_records_an_operating_outcome_without_selection_learning(tmp_path: Path) -> None:
    """Cash is a real feedback clock even when it is not an A/B signal."""
    contract_path = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-54_midea_core_growth_20260430" / "08_outcome_acquisition_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    conn = _conn(tmp_path)
    jfc.register_live_forward_contract(conn, contract_path=contract_path, registered_at="2026-08-22T12:00:00+08:00")
    item = "FBI:R-54:MIDEA:CORE_GROWTH_COMPLEXITY:20260430:R54-S3:WORKING_CAPITAL_CASH"
    source_id = "CNINFO:R54:2026H1"
    source_manifest = {
        "schema_version": "turtle-post-cutoff-outcome-package.v1",
        "outcome_package_id": "OUTPKG:R54:S3:TEST",
        "case_id": contract["case_id"], "freeze_id": contract["report_freeze"]["freeze_id"],
        "frozen_cutoff": contract["simulation_cutoff"],
        "enumeration": {"status": "COMPLETE", "query_identity": "美的 2026H1 官方报告", "source_ids": [source_id]},
        "inventory": [{
            "source_id": source_id, "source_type": "INTERIM_REPORT", "official": True,
            "published_at": "2026-08-23T10:00:00+08:00", "source_version": "original-release-v1",
            "data_as_of": "2026-06-30", "revision_policy": "ORIGINAL_VINTAGE",
            "acquisition_kind": "OFFICIAL_WEB_RELEASE", "content_format": "HTML",
            "url": "https://static.cninfo.com.cn/midea-2026h1", "release_id": "MIDEA-2026H1",
            "publisher_name": "美的集团", "official_publisher_domain": "static.cninfo.com.cn",
            "candidate_claim_ids": ["R54-S3"],
        }],
        "selected_source_ids": [source_id], "source_package_status": "INCOMPLETE",
    }
    inventory_path = tmp_path / "midea_inventory.json"
    inventory_path.write_text(json.dumps(source_manifest), encoding="utf-8")
    package_root, event_root = tmp_path / "midea_package", tmp_path / "midea_events"
    as_of = "2026-08-24T12:00:00+08:00"
    acquired = jfc.run_outcome_acquisition(
        conn, feedback_item_id=item, outcome_manifest_ref=inventory_path, package_root=package_root,
        event_root=event_root, settlement_as_of=as_of,
        downloader=lambda _: "<html>2026 年 1—6 月 经营活动产生的现金流量净额 123</html>".encode("utf-8"),
    )
    read = jfc.record_reader_attestation(
        conn, feedback_item_id=item, package_manifest_ref=acquired["package_manifest_ref"], package_root=package_root,
        event_root=event_root, settlement_as_of=as_of,
    )
    outcome = contract["calibration_ledger"]["claims"][3]["observable_outcome"]
    extraction = {
        "schema_version": "turtle-post-cutoff-outcome-extraction.v1", "outcome_package_id": source_manifest["outcome_package_id"],
        "case_id": contract["case_id"], "freeze_id": contract["report_freeze"]["freeze_id"], "settlement_as_of": as_of,
        "observations": [{
            "observation_id": "OBS:R54:S3:TEST", "claim_id": "R54-S3", "metric": outcome["metric"], "value": 123,
            "unit": outcome["unit"], "measurement_basis": outcome["measurement_basis"],
            "measurement_period": outcome["measurement_period"], "source_ids": [source_id], "comparability_status": "COMPARABLE",
            "reported_file_scope": "美的集团 2026 年半年度报告全文", "reported_label": "经营活动产生的现金流量净额",
            "reported_locator": "主要会计数据和财务指标 / 合并现金流量表", "reported_period_text": "2026 年 1—6 月",
            "reported_text": "2026 年 1—6 月 经营活动产生的现金流量净额 123", "reported_value_text": "123",
        }],
    }
    extraction_path = tmp_path / "midea_extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")
    jfc.record_outcome_extraction(
        conn, feedback_item_id=item, package_manifest_ref=acquired["package_manifest_ref"], package_root=package_root,
        read_attestation_ref=read["read_attestation_ref"], extraction_ref=extraction_path, settlement_as_of=as_of,
    )
    exposure = _artifact(tmp_path, "unused-exposure.json")
    result = jfc.run_signal_settlement(
        conn, feedback_item_id=item, package_manifest_ref=acquired["package_manifest_ref"], package_root=package_root,
        read_attestation_ref=read["read_attestation_ref"], exposure_attestation_ref=exposure,
        extraction_ref=extraction_path, settlement_id="R54-S3-TEST", settlement_as_of=as_of, event_root=event_root,
    )
    assert result["status"] == "OPERATING_OUTCOME_RECORDED"
    state = jfc.show(conn, item, as_of=as_of)["states"]
    assert state["settlement_state"] == "NOT_DIAGNOSTIC"
    assert state["learning_state"] == "NONE"
    priorities = {row["feedback_item_id"]: row["priority"] for row in jfc.reconcile(conn, as_of=as_of)["items"]}
    assert priorities[item] == "DONE"


def test_cjo_entry_surfaces_the_configured_persistent_control_plane_inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    configured_db = tmp_path / "configured-production.db"
    bootstrap = jfc.connect(configured_db)
    jfc.initialize(bootstrap)
    bootstrap.close()
    monkeypatch.setenv("TURTLE_DB_PATH", str(configured_db))
    run._FRAMEWORK_DIR = str(tmp_path)
    try:
        surfaced = run._surface_live_forward_due_inbox()
    finally:
        run._FRAMEWORK_DIR = previous_root
    assert not surfaced["sync"]["issues"]
    assert len(surfaced["inbox"]["items"]) == 2
    assert configured_db.is_file()
    assert not (tmp_path / "stock_analysis.db").exists()


def test_cjo_entry_dispatches_only_an_explicit_due_execution_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CJO entry point executes real adapters only when an input receipt is declared."""
    import scripts.judgment_feedback_control as control_module

    source = REPO_ROOT / "docs" / "development" / "research" / "experiments" / "R-05_prospective_operating_feedback"
    target = tmp_path / "docs" / "development" / "research" / "experiments" / source.name
    target.mkdir(parents=True)
    for name in ("06_forward_freeze.md", "08_outcome_acquisition_contract.json"):
        shutil.copy2(source / name, target / name)
    item = "FBI:R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821:R05-S1:EARLY_MECHANISM"
    request = target / "09_outcome_execution.json"
    request.write_text(json.dumps({"schema_version": jfc.DUE_EXECUTION_SCHEMA_VERSION, "feedback_item_id": item}), encoding="utf-8")
    configured_db = tmp_path / "configured-production.db"
    bootstrap = jfc.connect(configured_db)
    jfc.initialize(bootstrap)
    bootstrap.close()
    calls: list[Path] = []

    def _fake_execute(conn, *, execution_request_ref, actor_id, downloader=None):
        calls.append(Path(execution_request_ref))
        return {"status": "BLOCKED", "reason": "fixture has no real lower inputs"}

    run_path = REPO_ROOT / "scripts" / "turtle_agent" / "run.py"
    run_spec = importlib.util.spec_from_file_location("turtle_agent_run_execution_test", run_path)
    assert run_spec and run_spec.loader
    run = importlib.util.module_from_spec(run_spec)
    run_spec.loader.exec_module(run)
    previous_root = run._FRAMEWORK_DIR
    original_datetime = run.datetime

    class _FutureClock:
        @classmethod
        def now(cls):
            return original_datetime.fromisoformat("2027-01-15T12:00:00-08:00")

    monkeypatch.setenv("TURTLE_DB_PATH", str(configured_db))
    monkeypatch.setattr(control_module, "execute_due_claim", _fake_execute)
    run._FRAMEWORK_DIR = str(tmp_path)
    run.datetime = _FutureClock
    try:
        surfaced = run._surface_live_forward_due_inbox()
    finally:
        run._FRAMEWORK_DIR = previous_root
        run.datetime = original_datetime
    assert calls == [request]
    assert surfaced["executions"][0]["result"]["status"] == "BLOCKED"
