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
    target_manifest = _manifest(tmp_path, selection=True)
    target_manifest["episode_id"] = "R-TEST-02"
    target_manifest["company_id"] = "CN:OTHER"
    jfc.register_manifest(conn, target_manifest)
    target = "FBI:R-TEST-02:FJ:DEMAND:S1_DECISION"
    for event_type, key in (("ACQUISITION_STARTED", "other-a"), ("OUTCOME_PACKAGE_READY", "other-p"), ("READ_ATTESTED", "other-r"), ("OUTCOME_EXTRACTED", "other-x")):
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
    acquired = jfc.run_outcome_acquisition(
        conn, feedback_item_id=item, outcome_manifest_ref=source_manifest_path, package_root=package_root,
        event_root=event_root, settlement_as_of=at,
        downloader=lambda _: b"<html><body>Q1 Fiscal Year 2027 North America Change in Transactions 1</body></html>",
    )
    assert acquired["status"] == "PACKAGE_READY"
    read = jfc.record_reader_attestation(
        conn, feedback_item_id=item, package_manifest_ref=acquired["package_manifest_ref"], package_root=package_root,
        event_root=event_root, settlement_as_of=at,
    )
    assert read["status"] == "READ_ATTESTED"
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
    extracted = jfc.record_outcome_extraction(
        conn, feedback_item_id=item, package_manifest_ref=acquired["package_manifest_ref"], package_root=package_root,
        read_attestation_ref=read["read_attestation_ref"], extraction_ref=extraction_path, settlement_as_of=at,
    )
    assert extracted["status"] == "EXTRACTED"
    exposure = {
        "schema_version": "turtle-live-forward-exposure-attestation.v1", "case_id": frozen["case_id"],
        "freeze_id": frozen["report_freeze"]["freeze_id"], "settlement_as_of": at,
        "status": "NO_NONCLAIM_RESULT_EXPOSURE", "pipeline_read_source_ids": [source_id], "nonclaim_exposure_descriptions": [],
    }
    exposure_path = tmp_path / "exposure.json"
    exposure_path.write_text(json.dumps(exposure), encoding="utf-8")
    settled = jfc.run_signal_settlement(
        conn, feedback_item_id=item, package_manifest_ref=acquired["package_manifest_ref"], package_root=package_root,
        read_attestation_ref=read["read_attestation_ref"], exposure_attestation_ref=exposure_path,
        extraction_ref=extraction_path, settlement_id="R05-S1-TEST", settlement_as_of=at, event_root=event_root,
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


def test_generic_cli_cannot_forge_an_outcome_pipeline_event(tmp_path: Path) -> None:
    conn, item, _ = _registered(tmp_path)
    conn.close()
    event_path = tmp_path / "forged_outcome_event.json"
    event_path.write_text(json.dumps(_event(item, "ACQUISITION_STARTED", "2026-04-01T00:00:00+08:00", key="forged")), encoding="utf-8")
    with pytest.raises(jfc.ControlPlaneError, match="lower-module adapter"):
        jfc._command_append(argparse.Namespace(db=str(tmp_path / "stock_analysis.db"), input=str(event_path), recorded_at=None))


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
