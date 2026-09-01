from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import judgment_feedback_control as jfc
from scripts import judgment_training_program as jtp


def _write(path: Path, payload: dict | None = None) -> str:
    path.write_text(json.dumps(payload or {}), encoding="utf-8")
    return str(path)


def _program(tmp_path: Path) -> tuple[dict, Path]:
    universe = tmp_path / "cohort-register.json"
    _write(universe, {"selection_rule": "all cutoff-eligible peers, regardless of later status"})
    holdout_freeze = tmp_path / "holdout-freeze.md"
    holdout_freeze.write_text("frozen holdout", encoding="utf-8")
    live_freeze = tmp_path / "live-freeze.json"
    _write(live_freeze, {"state": "FROZEN"})
    contract = tmp_path / "training-program.json"
    payload = {
        "schema_version": jtp.SCHEMA_VERSION,
        "program_state": "ACTIVE",
        "program_id": "JTP:appliance-v1",
        "method_version": "enterprise-judgment-v1",
        "registered_at": "2026-01-01T00:00:00+08:00",
        "method_frozen_at": "2026-02-01T00:00:00+08:00",
        "sampling_policy": {
            "universe_ref": universe.name,
            "cohort_formed_as_of_cutoff": True,
            "outcome_used_for_selection": False,
            "terminal_status_coverage": "ALL_CUTOFF_ELIGIBLE_STATES",
            "same_company_periods_count_as_independent": False,
        },
        "episodes": [
            {
                "training_episode_id": "JTE:midea-2008",
                "case_id": "HBTCASE:midea-2008",
                "company_id": "CN:000333",
                "company_cluster_id": "COMPANY:midea",
                "industry_id": "CN_HOME_APPLIANCE",
                "decision_domain": "CONTROL_INTEGRATION",
                "cutoff_at": "2008-12-31T23:59:59+08:00",
                "outcome_not_before": "2009-04-01T00:00:00+08:00",
                "lane": "HISTORICAL_TRAINING",
                "provenance_role": "HISTORICAL_SELF_REPLAY",
                "outcome_access": "PIT_OUTCOME_SEALED",
            },
            {
                "training_episode_id": "JTE:jinko-2010",
                "case_id": "HBTCASE:jinko-2010",
                "company_id": "US:JKS",
                "company_cluster_id": "COMPANY:jinko",
                "industry_id": "SOLAR_MANUFACTURING",
                "decision_domain": "CAPACITY_INTEGRATION",
                "cutoff_at": "2010-06-30T23:59:59+08:00",
                "outcome_not_before": "2011-04-01T00:00:00+08:00",
                "lane": "HISTORICAL_HOLDOUT",
                "provenance_role": "HISTORICAL_SELF_REPLAY",
                "outcome_access": "PIT_OUTCOME_SEALED",
                "holdout_axis": "COMPANY_AND_TIME",
                "artifacts": {"freeze_ref": holdout_freeze.name},
            },
            {
                "training_episode_id": "JTE:midea-2026-live",
                "case_id": "R-54",
                "company_id": "CN:000333",
                "company_cluster_id": "COMPANY:midea",
                "industry_id": "DIVERSIFIED_MANUFACTURING",
                "decision_domain": "PORTFOLIO_GROWTH",
                "cutoff_at": "2026-04-30T23:59:59+08:00",
                "outcome_not_before": "2026-09-30T23:59:59+08:00",
                "lane": "LIVE_SENTINEL",
                "provenance_role": "REAL_FORWARD",
                "outcome_access": "NOT_YET_RELEASED",
                "artifacts": {"freeze_ref": live_freeze.name},
            },
        ],
    }
    contract.write_text(json.dumps(payload), encoding="utf-8")
    return payload, contract


def test_historical_work_remains_active_while_live_sentinel_waits(tmp_path: Path) -> None:
    _, contract = _program(tmp_path)
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    assert jtp.register_program(conn, contract)["registered"] is True
    conn.execute(
        "UPDATE judgment_training_programs SET method_freeze_recorded_at = ? WHERE program_id = ?",
        ("2026-02-01T01:00:00+08:00", "JTP:appliance-v1"),
    )
    conn.commit()

    status = jtp.reconcile(
        conn, program_id="JTP:appliance-v1", as_of="2026-08-23T12:00:00+08:00",
    )

    assert status["system_state"] == "ACTIVE"
    by_id = {item["training_episode_id"]: item for item in status["items"]}
    assert by_id["JTE:midea-2008"]["state"] == "READY_TO_FREEZE"
    assert by_id["JTE:jinko-2010"]["state"] == "READY_FOR_CONTROL_REGISTRATION"
    assert by_id["JTE:midea-2026-live"]["state"] == "WAITING_EXTERNAL"
    assert status["lane_summary"]["LIVE_SENTINEL"]["actionable"] == 0


def test_program_registration_is_immutable_and_idempotent(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    assert jtp.register_program(conn, contract)["idempotent"] is True

    payload["method_version"] = "changed-after-registration"
    contract.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(jtp.TrainingProgramError, match="immutable training program differs"):
        jtp.register_program(conn, contract)


def test_reserved_holdout_waits_but_untrained_method_cannot_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-25T00:00:00+08:00", "test"),
    )

    before = jtp.reconcile(
        conn, program_id=payload["program_id"], as_of="2026-08-23T12:00:00+08:00",
    )
    holdout_before = next(item for item in before["items"] if item["lane"] == "HISTORICAL_HOLDOUT")
    assert holdout_before["state"] == "WAITING_FOR_METHOD_FREEZE"

    with pytest.raises(jtp.TrainingProgramError, match="accepted cross-company learning application"):
        jtp.freeze_method(
            conn, program_id=payload["program_id"], method_version=payload["method_version"],
            frozen_at="2026-08-24T00:00:00+08:00",
        )


def test_survivor_selected_program_is_rejected(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["sampling_policy"]["outcome_used_for_selection"] = True
    payload["sampling_policy"]["terminal_status_coverage"] = "SURVIVORS_ONLY"

    result = jtp.validate_program(payload, contract_path=contract, validate_artifacts=False)

    assert result["state"] == "INVALID"
    assert "sampling_policy.outcome_selection_forbidden" in result["findings"]
    assert "sampling_policy.survivor_only_sampling_forbidden" in result["findings"]


def test_program_rejects_an_unknown_selection_admission_version(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["required_selection_admission_version"] = "JUDGMENT_SELECTION_ADMISSION_V99"

    result = jtp.validate_program(payload, contract_path=contract, validate_artifacts=False)

    assert result["state"] == "INVALID"
    assert "required_selection_admission_version_invalid" in result["findings"]


def test_draft_program_may_wait_for_a_valid_training_admission(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["program_state"] = "DRAFT"
    payload["episodes"] = [
        item for item in payload["episodes"]
        if item["lane"] != "HISTORICAL_TRAINING"
    ]
    contract.write_text(json.dumps(payload), encoding="utf-8")

    result = jtp.validate_program(payload, contract_path=contract, validate_artifacts=False)

    assert result["state"] == "REVIEWABLE"
    assert result["lane_counts"]["HISTORICAL_TRAINING"] == 0


def test_registered_draft_program_is_not_projected_as_active(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["program_state"] = "DRAFT"
    payload["episodes"] = [
        item for item in payload["episodes"]
        if item["lane"] != "HISTORICAL_TRAINING"
    ]
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)

    status = jtp.reconcile(
        conn, program_id=payload["program_id"], as_of="2026-08-23T12:00:00+08:00",
    )

    assert status["system_state"] == "DRAFT"
    assert status["historical_method_state"] == "PROGRAM_DRAFT"


def test_active_program_still_requires_a_training_lane(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["episodes"] = [
        item for item in payload["episodes"]
        if item["lane"] != "HISTORICAL_TRAINING"
    ]
    contract.write_text(json.dumps(payload), encoding="utf-8")

    result = jtp.validate_program(payload, contract_path=contract, validate_artifacts=False)

    assert result["state"] == "INVALID"
    assert "historical_training_lane_missing" in result["findings"]


def test_draft_activation_cannot_expand_method_scope(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["program_state"] = "DRAFT"
    payload["method_scope"] = "BOUNDARY_ONLY"
    payload["method_frozen_at"] = None
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)

    payload["program_state"] = "ACTIVE"
    payload["method_scope"] = "SELECTION_AND_BOUNDARY"
    contract.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(jtp.TrainingProgramError, match="immutable training program differs"):
        jtp.register_program(conn, contract)

    row = conn.execute(
        "SELECT program_state, method_scope FROM judgment_training_programs WHERE program_id = ?",
        (payload["program_id"],),
    ).fetchone()
    assert tuple(row) == ("DRAFT", "BOUNDARY_ONLY")


def test_company_holdout_cannot_reuse_a_training_company_cluster(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["episodes"][1]["company_cluster_id"] = "COMPANY:midea"

    result = jtp.validate_program(payload, contract_path=contract, validate_artifacts=False)

    assert result["state"] == "INVALID"
    assert any(item.endswith("company_holdout_cluster_seen_in_training") for item in result["findings"])


def _linked_successor_program(tmp_path: Path) -> tuple[object, dict, Path, dict, Path]:
    source, source_contract = _program(tmp_path)
    source["program_id"] = "JTP:selection-development-v1"
    source["method_version"] = "selection-method-v1"
    source["method_frozen_at"] = None
    source["episodes"] = source["episodes"][:2]
    source_contract.write_text(json.dumps(source), encoding="utf-8")

    successor_contract = tmp_path / "training-program-v2.json"
    successor = deepcopy(source)
    successor.update({
        "program_id": "JTP:selection-development-v2",
        "method_version": "selection-method-v2",
        "registered_at": "2026-01-03T00:00:00+08:00",
        "episodes": [deepcopy(source["episodes"][0])],
    })
    successor["episodes"][0].update({
        "training_episode_id": "JTE:successor-training",
        "case_id": "SELECTIONCASE:successor-training",
        "company_id": "CN:600132",
        "company_cluster_id": "COMPANY:successor",
    })
    holdout = source["episodes"][1]
    successor["holdout_links"] = [{
        "source_program_id": source["program_id"],
        "source_training_episode_id": holdout["training_episode_id"],
        "source_case_id": holdout["case_id"],
        "source_freeze_ref": str((tmp_path / holdout["artifacts"]["freeze_ref"]).resolve()),
        "link_role": "HISTORICAL_HOLDOUT",
    }]
    successor_contract.write_text(json.dumps(successor), encoding="utf-8")
    conn = jtp.connect(tmp_path / "linked-program.sqlite")
    jtp.initialize(conn)
    jtp.register_program(conn, source_contract)
    return conn, source, source_contract, successor, successor_contract


def test_successor_links_predecessor_holdout_without_rehoming_episode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, source, _, successor, successor_contract = _linked_successor_program(tmp_path)

    registered = jtp.register_program(conn, successor_contract)
    monkeypatch.setattr(jtp, "_program_control_items", lambda *args, **kwargs: {})
    status = jtp.reconcile(
        conn, program_id=successor["program_id"], as_of="2026-08-23T12:00:00+08:00",
    )

    source_holdout = source["episodes"][1]
    episode = conn.execute(
        "SELECT program_id FROM judgment_training_episodes WHERE training_episode_id = ?",
        (source_holdout["training_episode_id"],),
    ).fetchone()
    linked = next(item for item in status["items"] if item["lane"] == "HISTORICAL_HOLDOUT")
    assert registered["registered"] is True
    assert episode["program_id"] == source["program_id"]
    assert conn.execute(
        "SELECT COUNT(*) FROM judgment_training_episodes WHERE training_episode_id = ?",
        (source_holdout["training_episode_id"],),
    ).fetchone()[0] == 1
    assert linked["training_episode_id"] == source_holdout["training_episode_id"]
    assert linked["holdout_relation"] == "LINKED"
    assert linked["source_program_id"] == source["program_id"]
    assert linked["state"] == "WAITING_FOR_METHOD_FREEZE"
    assert status["lane_summary"]["HISTORICAL_HOLDOUT"]["count"] == 1


def test_linked_holdout_counts_for_successor_method_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, _, _, successor, successor_contract = _linked_successor_program(tmp_path)
    jtp.register_program(conn, successor_contract)
    monkeypatch.setattr(jtp, "_holdout_exposure_events", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        jtp, "_accepted_application_times",
        lambda *args, **kwargs: [jtp._parse_time("2026-08-23T10:00:00+08:00", "test")],
    )
    monkeypatch.setattr(jtp, "_program_control_items", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-25T00:00:00+08:00", "test"),
    )

    def terminal_status(row: dict, **_: object) -> dict:
        state = "TRANSFER_APPLIED" if row["lane"] == "HISTORICAL_TRAINING" else "WAITING_FOR_METHOD_FREEZE"
        return {"state": state, "actionable": False, "findings": []}

    monkeypatch.setattr(jtp, "_episode_status", terminal_status)
    frozen = jtp.freeze_method(
        conn, program_id=successor["program_id"], method_version=successor["method_version"],
        frozen_at="2026-08-24T00:00:00+08:00",
    )

    assert frozen["program_id"] == successor["program_id"]
    assert frozen["idempotent"] is False


def test_linked_holdout_identity_and_company_axis_are_revalidated_at_registration(
    tmp_path: Path,
) -> None:
    conn, source, _, successor, successor_contract = _linked_successor_program(tmp_path)
    successor["holdout_links"][0]["source_case_id"] = "HOLDOUT:rewritten"
    successor_contract.write_text(json.dumps(successor), encoding="utf-8")

    with pytest.raises(jtp.TrainingProgramError, match="source identity differs"):
        jtp.register_program(conn, successor_contract)

    successor["holdout_links"][0]["source_case_id"] = source["episodes"][1]["case_id"]
    successor["episodes"][0]["company_cluster_id"] = source["episodes"][1]["company_cluster_id"]
    successor_contract.write_text(json.dumps(successor), encoding="utf-8")
    with pytest.raises(jtp.TrainingProgramError, match="cannot reuse"):
        jtp.register_program(conn, successor_contract)


def test_feedback_control_resolves_source_claim_to_frozen_successor_program(
    tmp_path: Path,
) -> None:
    conn, source, source_contract, successor, successor_contract = _linked_successor_program(tmp_path)
    jtp.register_program(conn, successor_contract)
    conn.execute(
        """UPDATE judgment_training_programs
              SET method_frozen_at = ?, method_freeze_recorded_at = ?
            WHERE program_id = ?""",
        (
            "2026-08-24T00:00:00+08:00", "2026-08-24T00:01:00+08:00",
            successor["program_id"],
        ),
    )
    conn.commit()
    source_holdout = source["episodes"][1]
    claim = {
        "program_lane": "HISTORICAL_HOLDOUT",
        "learning_eligibility": "EVALUATION_ONLY",
        "training_program_ref": str(source_contract.resolve()),
        "episode_id": source_holdout["case_id"],
    }

    context = jfc._require_frozen_holdout_program(
        conn, claim,
        effective_at=jfc._parse_time("2026-08-24T00:02:00+08:00", field="test"),
    )

    assert context["program_id"] == successor["program_id"]
    assert context["method_version"] == successor["method_version"]
    assert context["training_episode_id"] == source_holdout["training_episode_id"]
    assert context["source_program_id"] == source["program_id"]
    assert context["holdout_relation"] == "LINKED"


def test_program_artifact_slots_cannot_duplicate_feedback_control_semantics(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["episodes"][1]["artifacts"] = {
        "case_ref": "case.json",
        "settlement_ref": "settlement.json",
        "feedback_ref": "feedback.json",
        "learning_note_ref": "note.json",
    }

    result = jtp.validate_program(payload, contract_path=contract, validate_artifacts=False)

    assert result["state"] == "INVALID"
    assert any("artifacts_unexpected_fields" in item for item in result["findings"])


def _feedback_manifest(tmp_path: Path, *, identity: dict[str, str]) -> dict:
    frozen = _write(tmp_path / "frozen.json")
    source = _write(tmp_path / "source.json")
    measurement = _write(tmp_path / "measurement.json")
    return {
        "schema_version": jfc.REGISTRATION_SCHEMA_VERSION,
        "episode_id": "HBTCASE:midea-2008",
        "company_id": "CN:000333",
        "frozen_at": "2008-12-31T23:59:59+08:00",
        "episode_class": "JUDGMENT_SELECTION_EPISODE",
        "selection_status": "SELECTION_ADMITTED",
        **identity,
        "feedback_items": [{
            "claim_id": "HBTCLM:midea:integration",
            "stage_id": "CUSTOMER_COMPETITOR_RESPONSE",
            "source_kind": "OFFICIAL_COMPANY_DISCLOSURE",
            "source_ref": "official:FY2009",
            "eligible_at": "2009-04-01T00:00:00+08:00",
            "settlement_version_policy": "INITIAL_DISCLOSURE",
            "frozen_artifact_ref": frozen,
            "source_contract_ref": source,
            "measurement_contract_ref": measurement,
        }],
    }


def test_feedback_control_accepts_sealed_historical_training_identity(tmp_path: Path) -> None:
    _, contract = _program(tmp_path)
    identity = jtp.feedback_control_identity(
        {"lane": "HISTORICAL_TRAINING", "outcome_access": "PIT_OUTCOME_SEALED"},
        selection_status="SELECTION_ADMITTED", program_ref=str(contract),
    )
    conn = jfc.connect(tmp_path / "feedback.db")
    jfc.initialize(conn)

    result = jfc.register_manifest(conn, _feedback_manifest(tmp_path, identity=identity))
    claim = jfc.reconcile(conn, as_of="2009-04-02T00:00:00+08:00")["items"][0]

    assert result["registered"][0]["registered"] is True
    assert claim["program_lane"] == "HISTORICAL_TRAINING"
    assert claim["learning_eligibility"] == "SELECTION_METHOD_ELIGIBLE"


def test_feedback_control_rejects_learning_enabled_holdout(tmp_path: Path) -> None:
    _, contract = _program(tmp_path)
    identity = {
        "program_lane": "HISTORICAL_HOLDOUT",
        "outcome_access": "PIT_OUTCOME_SEALED",
        "training_program_ref": str(contract),
        "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
    }
    conn = jfc.connect(tmp_path / "feedback.db")
    jfc.initialize(conn)

    with pytest.raises(jfc.ControlPlaneError, match="EVALUATION_ONLY"):
        jfc.register_manifest(conn, _feedback_manifest(tmp_path, identity=identity))


def test_feedback_identity_marks_teaching_as_non_learning(tmp_path: Path) -> None:
    _, contract = _program(tmp_path)
    identity = jtp.feedback_control_identity(
        {"lane": "HISTORICAL_TEACHING", "outcome_access": "OUTCOME_EXPOSED"},
        selection_status="NO_PRIMARY", program_ref=str(contract),
    )

    assert identity["learning_eligibility"] == "TEACHING_ONLY"


def test_historical_no_primary_projects_to_boundary_learning_only(tmp_path: Path) -> None:
    _, contract = _program(tmp_path)
    identity = jtp.feedback_control_identity(
        {"lane": "HISTORICAL_TRAINING", "outcome_access": "PIT_OUTCOME_SEALED"},
        selection_status="NO_PRIMARY", program_ref=str(contract),
    )

    assert identity["learning_eligibility"] == "BOUNDARY_METHOD_ELIGIBLE"


def test_freeze_artifact_can_be_appended_once_after_program_registration(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    freeze = tmp_path / "training-freeze.md"
    freeze.write_text("first frozen version", encoding="utf-8")

    recorded = jtp.record_artifact(
        conn, training_episode_id="JTE:midea-2008", kind="freeze_ref",
        artifact_path=freeze, recorded_at="2026-01-02T00:00:00+08:00",
    )
    status = jtp.reconcile(
        conn, program_id=payload["program_id"], as_of="2026-08-23T12:00:00+08:00",
    )
    training = next(item for item in status["items"] if item["training_episode_id"] == "JTE:midea-2008")

    assert recorded["recorded"] is True
    assert training["state"] == "READY_FOR_CONTROL_REGISTRATION"
    assert jtp.record_artifact(
        conn, training_episode_id="JTE:midea-2008", kind="freeze_ref",
        artifact_path=freeze, recorded_at="2026-01-02T00:00:00+08:00",
    )["idempotent"] is True

    freeze.write_text("rewritten after registration", encoding="utf-8")
    with pytest.raises(jtp.TrainingProgramError, match="immutable once recorded"):
        jtp.record_artifact(
            conn, training_episode_id="JTE:midea-2008", kind="freeze_ref",
            artifact_path=freeze, recorded_at="2026-01-03T00:00:00+08:00",
        )


def test_method_freeze_requires_a_holdout_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    payload["program_state"] = "DRAFT"
    payload["episodes"] = [item for item in payload["episodes"] if item["lane"] != "HISTORICAL_HOLDOUT"]
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-25T00:00:00+08:00", "test"),
    )

    with pytest.raises(jtp.TrainingProgramError, match="clean historical holdout reservation"):
        jtp.freeze_method(
            conn, program_id=payload["program_id"], method_version=payload["method_version"],
            frozen_at="2026-08-24T00:00:00+08:00",
        )


def test_clean_holdout_can_be_reserved_only_before_training_outcome_exposure(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    payload["program_state"] = "DRAFT"
    holdout = payload["episodes"].pop(1)
    contract.write_text(json.dumps(payload), encoding="utf-8")
    holdout_path = tmp_path / "holdout.json"
    holdout_path.write_text(json.dumps(holdout), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)

    reserved = jtp.reserve_holdout(
        conn, program_id=payload["program_id"], episode=holdout,
        contract_path=holdout_path, reserved_at="2026-01-02T00:00:00+08:00",
    )
    status = jtp.reconcile(
        conn, program_id=payload["program_id"], as_of="2026-08-23T12:00:00+08:00",
    )
    holdout_status = next(item for item in status["items"] if item["lane"] == "HISTORICAL_HOLDOUT")

    assert reserved["reserved"] is True
    assert holdout_status["state"] == "WAITING_FOR_METHOD_FREEZE"
    assert jtp.register_program(conn, contract)["idempotent"] is True


def test_future_program_registration_writes_no_training_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    payload["registered_at"] = "2026-08-26T00:00:00+08:00"
    payload["method_frozen_at"] = None
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-25T00:00:00+08:00", "test"),
    )

    with pytest.raises(jtp.TrainingProgramError, match="real current time"):
        jtp.register_program(conn, contract)

    assert conn.execute("SELECT COUNT(*) FROM judgment_training_programs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM judgment_training_episodes").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM judgment_training_artifact_events").fetchone()[0] == 0


def test_future_holdout_reservation_writes_no_episode_or_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    payload["program_state"] = "DRAFT"
    holdout = payload["episodes"].pop(1)
    contract.write_text(json.dumps(payload), encoding="utf-8")
    holdout_path = tmp_path / "holdout.json"
    holdout_path.write_text(json.dumps(holdout), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-25T00:00:00+08:00", "test"),
    )
    jtp.register_program(conn, contract)
    episode_count = conn.execute("SELECT COUNT(*) FROM judgment_training_episodes").fetchone()[0]
    artifact_count = conn.execute("SELECT COUNT(*) FROM judgment_training_artifact_events").fetchone()[0]

    with pytest.raises(jtp.TrainingProgramError, match="real current time"):
        jtp.reserve_holdout(
            conn,
            program_id=payload["program_id"],
            episode=holdout,
            contract_path=holdout_path,
            reserved_at="2026-08-26T00:00:00+08:00",
        )

    assert conn.execute("SELECT COUNT(*) FROM judgment_training_episodes").fetchone()[0] == episode_count
    assert conn.execute("SELECT COUNT(*) FROM judgment_training_artifact_events").fetchone()[0] == artifact_count
    assert conn.execute(
        "SELECT 1 FROM judgment_training_episodes WHERE training_episode_id = ?",
        (holdout["training_episode_id"],),
    ).fetchone() is None


def test_method_freeze_accepts_only_terminal_training_and_unexposed_holdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    monkeypatch.setattr(jtp, "_holdout_exposure_events", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-25T00:00:00+08:00", "test"),
    )
    monkeypatch.setattr(
        jtp, "_accepted_application_times",
        lambda *args, **kwargs: [jtp._parse_time("2026-08-23T10:00:00+08:00", "test")],
    )
    monkeypatch.setattr(jtp, "_program_control_items", lambda *args, **kwargs: {})

    def terminal_status(row: dict, **_: object) -> dict:
        state = "TRANSFER_APPLIED" if row["lane"] == "HISTORICAL_TRAINING" else "WAITING_FOR_METHOD_FREEZE"
        return {"state": state, "actionable": False, "findings": []}

    monkeypatch.setattr(jtp, "_episode_status", terminal_status)
    frozen = jtp.freeze_method(
        conn, program_id=payload["program_id"], method_version=payload["method_version"],
        frozen_at="2026-08-24T00:00:00+08:00",
    )

    assert frozen["idempotent"] is False


def test_live_wait_is_separate_from_completed_historical_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    monkeypatch.setattr(jtp, "_program_control_items", lambda *args, **kwargs: {})

    def projected_status(row: dict, **_: object) -> dict:
        state = {
            "HISTORICAL_TRAINING": "TRANSFER_APPLIED",
            "HISTORICAL_HOLDOUT": "EVALUATED_HOLDOUT",
            "LIVE_SENTINEL": "WAITING_EXTERNAL",
        }[row["lane"]]
        return {"state": state, "actionable": False, "findings": []}

    monkeypatch.setattr(jtp, "_episode_status", projected_status)
    status = jtp.reconcile(
        conn, program_id=payload["program_id"], as_of="2026-08-23T12:00:00+08:00",
    )

    assert status["system_state"] == "HISTORICAL_EVALUATION_COMPLETE"
    assert status["historical_method_state"] == "HISTORICAL_EVALUATION_COMPLETE"
    assert status["deployment_calibration_state"] == "WAITING_EXTERNAL"


def _selection_development_assets() -> tuple[Path, Path, Path, Path]:
    root = Path(__file__).parents[1]
    experiment = (
        root / "docs" / "development" / "research" / "experiments"
        / "R-104_chongqing_beer_network_pruning_unit_economics_20160430"
    )
    return (
        root / "config" / "judgment_selection_program_candidate_v2.json",
        experiment,
        experiment / "02_independent_pre_outcome_review.json",
        experiment / "judgment_feedback_control.json",
    )


def _selection_program_without_review(tmp_path: Path) -> tuple[dict, Path]:
    contract, _, _, _ = _selection_development_assets()
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["program_state"] = "DRAFT"
    payload["registered_at"] = "2026-08-24T01:25:00+08:00"
    universe_ref = payload["sampling_policy"]["universe_ref"]
    payload["sampling_policy"]["universe_ref"] = str((contract.parent / universe_ref).resolve())
    for episode in payload["episodes"]:
        for field, reference in list((episode.get("artifacts") or {}).items()):
            episode["artifacts"][field] = str((contract.parent / reference).resolve())
    training = next(item for item in payload["episodes"] if item["lane"] == "HISTORICAL_TRAINING")
    training["artifacts"].pop("selection_review_ref", None)
    temporary = tmp_path / "selection-program-without-review.json"
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    return payload, temporary


def test_selection_candidate_waits_for_review_before_feedback_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, experiment, review_ref, manifest_ref = _selection_development_assets()
    payload, contract = _selection_program_without_review(tmp_path)
    now = jtp._parse_time("2026-08-24T02:00:00+08:00", "test")
    monkeypatch.setattr(jtp, "_now_dt", lambda: now)
    monkeypatch.setattr(jfc, "_now_dt", lambda: now)
    conn = jtp.connect(tmp_path / "selection-candidate.sqlite")
    jtp.initialize(conn)

    registered = jtp.register_program(conn, contract)
    status = jtp.reconcile(
        conn,
        program_id=payload["program_id"],
        as_of="2026-08-24T01:30:00+08:00",
    )
    candidate = next(item for item in status["items"] if item["case_id"].startswith("SELECTIONCASE:R-104:"))
    manifest = jfc._resolve_manifest_artifact_refs(
        json.loads(manifest_ref.read_text(encoding="utf-8")), experiment,
    )
    manifest["training_program_ref"] = str(contract.resolve())

    assert registered["registered"] is True
    assert candidate["state"] == "AWAITING_SELECTION_REVIEW"
    assert candidate["findings"] == ["selection_review_required"]
    with pytest.raises(jfc.ControlPlaneError) as blocked:
        jfc.register_manifest(
            conn, manifest, registered_at="2026-08-24T01:35:00+08:00",
        )
    assert blocked.value.code == "selection_review_required"
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 0
    alternate_freeze = tmp_path / "alternate-freeze.json"
    alternate_freeze.write_text("{}", encoding="utf-8")
    swapped_manifest = deepcopy(manifest)
    for item in swapped_manifest["feedback_items"]:
        item["frozen_artifact_ref"] = str(alternate_freeze)
    with pytest.raises(jfc.ControlPlaneError) as swapped:
        jfc.register_manifest(
            conn, swapped_manifest, registered_at="2026-08-24T01:35:00+08:00",
        )
    assert swapped.value.code == "selection_candidate_snapshot_mismatch"
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 0

    appended = jtp.record_artifact(
        conn,
        training_episode_id="JTE:R-104:chongqing-beer-selection-development-2016",
        kind="selection_review_ref",
        artifact_path=review_ref,
        recorded_at="2026-08-24T01:27:00+08:00",
    )
    after_review = jtp.reconcile(
        conn,
        program_id=payload["program_id"],
        as_of="2026-08-24T01:30:00+08:00",
    )
    candidate_after_review = next(
        item for item in after_review["items"] if item["case_id"].startswith("SELECTIONCASE:R-104:")
    )
    with pytest.raises(jfc.ControlPlaneError) as draft_blocked:
        jfc.register_manifest(
            conn, manifest, registered_at="2026-08-24T01:35:00+08:00",
        )

    assert appended["recorded"] is True
    assert candidate_after_review["state"] == "READY_FOR_CONTROL_REGISTRATION"
    assert draft_blocked.value.code == "selection_training_program_not_active"
    assert conn.execute("SELECT COUNT(*) FROM judgment_feedback_claims").fetchone()[0] == 0

    activated_payload = deepcopy(payload)
    activated_payload["program_state"] = "ACTIVE"
    contract.write_text(json.dumps(activated_payload), encoding="utf-8")
    with pytest.raises(jtp.TrainingProgramError, match="activation training artifact set differs"):
        jtp.register_program(conn, contract)

    training = next(
        item for item in activated_payload["episodes"] if item["lane"] == "HISTORICAL_TRAINING"
    )
    training["artifacts"]["selection_review_ref"] = str(review_ref.resolve())
    contract.write_text(json.dumps(activated_payload), encoding="utf-8")
    activated = jtp.register_program(conn, contract)

    assert activated["activated"] is True
    assert conn.execute(
        "SELECT program_state FROM judgment_training_programs WHERE program_id = ?",
        (payload["program_id"],),
    ).fetchone()[0] == "ACTIVE"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"case_id": "SELECTIONCASE:R-OTHER"}, "review_case_id_mismatch"),
        ({"reviewed_at": "2026-08-23T22:00:00+08:00"}, "reviewed_before_candidate_freeze"),
    ],
)
def test_selection_review_identity_and_time_mismatch_are_not_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    mutation: dict[str, str], expected: str,
) -> None:
    _, _, review_ref, _ = _selection_development_assets()
    _, contract = _selection_program_without_review(tmp_path)
    now = jtp._parse_time("2026-08-24T02:00:00+08:00", "test")
    monkeypatch.setattr(jtp, "_now_dt", lambda: now)
    conn = jtp.connect(tmp_path / "invalid-selection-review.sqlite")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    review = json.loads(review_ref.read_text(encoding="utf-8"))
    review.update(mutation)
    invalid_ref = tmp_path / "invalid-selection-review.json"
    invalid_ref.write_text(json.dumps(review), encoding="utf-8")

    with pytest.raises(jtp.TrainingProgramError, match=expected):
        jtp.record_artifact(
            conn,
            training_episode_id="JTE:R-104:chongqing-beer-selection-development-2016",
            kind="selection_review_ref",
            artifact_path=invalid_ref,
            recorded_at="2026-08-24T01:27:00+08:00",
        )

    assert conn.execute(
        """SELECT 1 FROM judgment_training_artifact_events
            WHERE training_episode_id = ? AND artifact_kind = 'selection_review_ref'""",
        ("JTE:R-104:chongqing-beer-selection-development-2016",),
    ).fetchone() is None


def test_case_validator_dispatch_preserves_boundary_and_legacy_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "case_id": "CASE:dispatch",
        "company_id": "CN:TEST",
        "company_cluster_id": "COMPANY:test",
        "industry_id": "TEST",
        "cutoff_at": "2020-12-31T23:59:59+08:00",
    }
    calls: list[str] = []
    monkeypatch.setattr(
        jtp,
        "validate_boundary_case",
        lambda _: calls.append("boundary") or {"state": "REVIEWABLE", "findings": []},
    )
    monkeypatch.setattr(
        jtp,
        "validate_case",
        lambda _, **__: calls.append("legacy") or {"state": "REVIEWABLE", "findings": []},
    )
    monkeypatch.setattr(
        jtp,
        "validate_selection_candidate",
        lambda _: (_ for _ in ()).throw(AssertionError("candidate validator must not receive old cases")),
    )

    jtp._validate_case_payload(row, {"schema_version": "judgment-boundary-case.v1", "case_id": "CASE:dispatch"})
    jtp._validate_case_payload(row, {"schema_version": "historical-backtest-case.v4", "case_id": "CASE:dispatch"})

    assert calls == ["boundary", "legacy"]


def test_non_diagnostic_selection_boundary_is_terminal_but_cannot_grant_transfer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_ref, experiment, review_ref, _ = _selection_development_assets()
    program = json.loads(contract_ref.read_text(encoding="utf-8"))
    row = next(item for item in program["episodes"] if item["lane"] == "HISTORICAL_TRAINING")
    case_ref = experiment / "01_case_freeze.json"
    now = jtp._parse_time("2026-08-25T00:00:00+08:00", "test")
    monkeypatch.setattr(jtp, "_now_dt", lambda: now)
    monkeypatch.setattr(jfc, "_now_dt", lambda: now)
    artifacts = {
        "case_ref": {
            "artifact_ref": str(case_ref),
            "recorded_at": "2026-08-24T01:23:00+08:00",
            "content_json": case_ref.read_text(encoding="utf-8"),
        },
        "selection_review_ref": {
            "artifact_ref": str(review_ref),
            "recorded_at": "2026-08-24T01:27:00+08:00",
            "content_json": review_ref.read_text(encoding="utf-8"),
        },
    }
    stages = [
        "D1_IMPLEMENTATION", "D2_CUSTOMER_ABSORPTION", "D3_PRODUCT_VOLUME",
        "D3_UNIT_ECONOMICS", "D4_WORKING_CAPITAL_AND_CASH", "D5_CAPITAL_RETURN",
    ]
    control_items = []
    for index, stage_id in enumerate(stages):
        settlement = {
            "event_id": f"SETTLEMENT:{index}",
            "event_type": "MEASUREMENT_MISMATCH",
            "effective_at": "2026-08-24T01:30:00+08:00",
            "recorded_at": "2026-08-24T01:31:00+08:00",
            "payload": {},
        }
        events = [settlement]
        event_types = ["MEASUREMENT_MISMATCH"]
        if stage_id == "D3_UNIT_ECONOMICS":
            events.extend([
                {
                    "event_id": "DIAGNOSIS:R104-FIXTURE",
                    "event_type": "DIAGNOSIS_ACCEPTED",
                        "effective_at": "2026-08-24T01:38:00+08:00",
                        "recorded_at": "2026-08-24T01:39:00+08:00",
                    "payload": {"settlement_event_id": settlement["event_id"]},
                },
                {
                    "event_id": "BOUNDARY-NOTE:R104-FIXTURE",
                    "event_type": "LEARNING_NOTE_READY",
                        "effective_at": "2026-08-24T01:47:00+08:00",
                        "recorded_at": "2026-08-24T01:48:00+08:00",
                    "payload": {
                        "diagnosis_event_id": "DIAGNOSIS:R104-FIXTURE",
                        "learning_scope": "MEASUREMENT_BOUNDARY",
                    },
                },
            ])
            event_types.extend(["DIAGNOSIS_ACCEPTED", "LEARNING_NOTE_READY"])
        control_items.append({
            "program_lane": "HISTORICAL_TRAINING",
            "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
            "selection_status": "SELECTION_ADMITTED",
            "stage_id": stage_id,
            "event_types": event_types,
            "event_records": events,
            "learning_state": (
                "MEASUREMENT_BOUNDARY_READY" if stage_id == "D3_UNIT_ECONOMICS" else "NOTE_READY"
            ),
        })

    status = jtp._episode_status(
        row, as_of=now, method_frozen_at=None, method_freeze_recorded_at=None,
        artifacts=artifacts, control_items=control_items,
    )

    assert status == {
        "state": "MEASUREMENT_BOUNDARY_CAPTURED",
        "actionable": False,
        "findings": [
            "non_directional_measurement_learning_only",
            "new_selection_training_episode_required",
        ],
    }


def test_mixed_selection_bundle_is_a_terminal_mechanism_boundary_not_a_diagnosis_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_ref, experiment, review_ref, _ = _selection_development_assets()
    program = json.loads(contract_ref.read_text(encoding="utf-8"))
    row = next(item for item in program["episodes"] if item["lane"] == "HISTORICAL_TRAINING")
    case_ref = experiment / "01_case_freeze.json"
    # R-104's real topology omits optional D3 product volume.  It must remain
    # valid even though control-plane reconciliation orders claims by current
    # priority instead of the frozen registration order.
    feedback_items = [
        {"claim_id": f"R104:{stage_id}", "stage_id": stage_id}
        for stage_id in (
            "D1_IMPLEMENTATION",
            "D2_CUSTOMER_ABSORPTION",
            "D3_UNIT_ECONOMICS",
            "D4_WORKING_CAPITAL_AND_CASH",
            "D5_CAPITAL_RETURN",
        )
    ]
    feedback_path = tmp_path / "mixed-selection-feedback.json"
    feedback_path.write_text(json.dumps({
        "schema_version": "judgment-selection-feedback-card.v1",
        "case_id": row["case_id"],
        "cards": [
            {"claim_id": item["claim_id"], "stage_id": item["stage_id"]}
            for item in feedback_items
        ],
        "joint_comparison": {"overall_verdict": "MIXED"},
    }), encoding="utf-8")
    now = jtp._parse_time("2026-08-25T00:00:00+08:00", "test")
    monkeypatch.setattr(jtp, "_now_dt", lambda: now)
    monkeypatch.setattr(jfc, "_now_dt", lambda: now)
    artifacts = {
        "case_ref": {
            "artifact_ref": str(case_ref),
            "recorded_at": "2026-08-24T01:23:00+08:00",
            "content_json": case_ref.read_text(encoding="utf-8"),
        },
        "selection_review_ref": {
            "artifact_ref": str(review_ref),
            "recorded_at": "2026-08-24T01:27:00+08:00",
            "content_json": review_ref.read_text(encoding="utf-8"),
        },
    }
    control_items = [
        {
            "episode_id": row["case_id"],
            "claim_id": item["claim_id"],
            "stage_id": item["stage_id"],
            "program_lane": "HISTORICAL_TRAINING",
            "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
            "selection_status": "SELECTION_ADMITTED",
            "event_types": ["CLAIM_SETTLED"],
            "event_records": [{
                "event_id": f"SETTLEMENT:{item['claim_id']}",
                "event_type": "CLAIM_SETTLED",
                "effective_at": "2026-08-24T01:30:00+08:00",
                "recorded_at": "2026-08-24T01:31:00+08:00",
                "payload": {"feedback_ref": str(feedback_path)},
            }],
            # D3 and D4 may each retain their diagnostic readings.  The
            # bundle result, not their local state, decides method rights.
            "learning_state": "DIAGNOSIS_PENDING",
        }
        for item in feedback_items
    ]

    status = jtp._episode_status(
        row, as_of=now, method_frozen_at=None, method_freeze_recorded_at=None,
        artifacts=artifacts, control_items=control_items,
    )

    assert status == {
        "state": "MIXED_MECHANISM_BOUNDARY_CAPTURED",
        "actionable": False,
        "findings": [
            "non_directional_mixed_mechanism_boundary",
            "directional_selection_learning_prohibited",
            "new_selection_training_episode_required",
        ],
    }


def test_method_freeze_and_artifact_receipts_reject_future_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-23T12:00:00+08:00", "test"),
    )

    with pytest.raises(jtp.TrainingProgramError, match="future"):
        jtp.freeze_method(
            conn,
            program_id=payload["program_id"],
            method_version=payload["method_version"],
            frozen_at="2026-08-24T00:00:00+08:00",
        )
    late_artifact = tmp_path / "late-freeze.md"
    late_artifact.write_text("late", encoding="utf-8")
    with pytest.raises(jtp.TrainingProgramError, match="real current time"):
        jtp.record_artifact(
            conn,
            training_episode_id="JTE:midea-2008",
            kind="freeze_ref",
            artifact_path=late_artifact,
            recorded_at="2026-08-24T00:00:00+08:00",
        )


def test_holdout_freeze_cannot_be_attached_after_method_freeze(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    holdout = next(item for item in payload["episodes"] if item["lane"] == "HISTORICAL_HOLDOUT")
    holdout["artifacts"] = {}
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    late_freeze = tmp_path / "late-holdout-freeze.md"
    late_freeze.write_text("created after method freeze", encoding="utf-8")

    with pytest.raises(jtp.TrainingProgramError, match="after method freeze"):
        jtp.record_artifact(
            conn,
            training_episode_id=holdout["training_episode_id"],
            kind="freeze_ref",
            artifact_path=late_freeze,
            recorded_at="2026-02-02T00:00:00+08:00",
        )


def test_legacy_invalid_learning_chain_cannot_grant_transfer_or_method_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    payload["method_scope"] = "BOUNDARY_ONLY"
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    now = jtp._parse_time("2026-08-25T00:00:00+08:00", "test")
    monkeypatch.setattr(jtp, "_now_dt", lambda: now)
    monkeypatch.setattr(jfc, "_now_dt", lambda: now)

    training_freeze = tmp_path / "training-freeze.md"
    training_freeze.write_text("frozen before replay", encoding="utf-8")
    jtp.record_artifact(
        conn,
        training_episode_id="JTE:midea-2008",
        kind="freeze_ref",
        artifact_path=training_freeze,
        recorded_at="2026-01-02T00:00:00+08:00",
    )
    identity = jtp.feedback_control_identity(
        payload["episodes"][0],
        selection_status="NO_PRIMARY",
        program_ref=str(contract),
    )
    manifest = _feedback_manifest(tmp_path, identity=identity)
    manifest.update({
        "episode_class": "MECHANISM_SIGNAL_PROBE",
        "selection_status": "NO_PRIMARY",
    })
    jfc.register_manifest(
        conn, manifest, registered_at="2026-01-03T00:00:00+08:00",
    )
    feedback_item_id = "FBI:HBTCASE:midea-2008:HBTCLM:midea:integration:CUSTOMER_COMPETITOR_RESPONSE"
    events = [
        ("EVT:legacy-settlement", "CLAIM_SETTLED", "2026-08-23T13:20:00+00:00", {"settlement_verdict": "B_ONLY"}),
        ("EVT:legacy-diagnosis", "DIAGNOSIS_ACCEPTED", "2026-08-23T13:30:00+00:00", {"settlement_event_id": "EVT:legacy-settlement"}),
        ("EVT:legacy-note", "LEARNING_NOTE_READY", "2026-08-23T13:30:00+00:00", {"diagnosis_event_id": "EVT:legacy-diagnosis"}),
        ("EVT:legacy-application", "LEARNING_APPLIED", "2026-08-23T13:45:00+00:00", {"learning_note_event_id": "EVT:legacy-note"}),
    ]
    for event_id, event_type, effective_at, event_payload in events:
        conn.execute(
            """INSERT INTO judgment_feedback_events
                 (event_id, feedback_item_id, event_type, effective_at, recorded_at,
                  actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
                 VALUES (?, ?, ?, ?, '2026-08-23T12:00:00+00:00',
                         'RESEARCHER', 'legacy-import', ?, '[]', ?)""",
            (event_id, feedback_item_id, event_type, effective_at, event_id, json.dumps(event_payload)),
        )
    conn.commit()

    status = jtp.reconcile(
        conn, program_id=payload["program_id"], as_of="2026-08-24T00:00:00+08:00",
    )
    training = next(item for item in status["items"] if item["training_episode_id"] == "JTE:midea-2008")

    assert training["state"] == "INVALID_LEARNING_CHAIN", training["findings"]
    assert "invalid_learning_chain" in training["findings"]
    assert status["historical_method_state"] == "NEEDS_REPAIR"
    assert status["system_state"] == "NEEDS_REPAIR"
    assert jtp._accepted_application_times(
        conn,
        program_id=payload["program_id"],
        contract_ref=str(contract.resolve()),
        method_scope=payload.get("method_scope", "SELECTION_AND_BOUNDARY"),
    ) == []
    with pytest.raises(jtp.TrainingProgramError, match="accepted cross-company learning application"):
        jtp.freeze_method(
            conn,
            program_id=payload["program_id"],
            method_version=payload["method_version"],
            frozen_at="2026-08-24T00:00:00+08:00",
        )


def _method_release_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, verdict: str,
) -> tuple[object, Path]:
    conn = jtp.connect(tmp_path / "method-release.sqlite")
    jtp.initialize(conn)
    program_ref = Path(_write(tmp_path / "program.json", {"fixture": True})).resolve()
    artifact_ref = Path(_write(tmp_path / "artifact.json", {"fixture": True})).resolve()
    conn.execute(
        """INSERT INTO judgment_training_programs
             (program_id, program_state, method_version, method_scope, registered_at,
              method_frozen_at, method_freeze_recorded_at, sampling_policy_json, contract_ref)
             VALUES ('JTP:release-fixture', 'ACTIVE', 'selection-v1',
                     'SELECTION_AND_BOUNDARY', ?, ?, ?, '{}', ?)""",
        (
            "2026-08-20T00:00:00+08:00", "2026-08-22T10:00:00+08:00",
            "2026-08-22T10:01:00+08:00", str(program_ref),
        ),
    )
    conn.execute(
        """INSERT INTO judgment_training_episodes
             (training_episode_id, program_id, case_id, company_id, company_cluster_id,
              industry_id, decision_domain, cutoff_at, outcome_not_before, lane,
              provenance_role, outcome_access, holdout_axis, artifacts_json)
             VALUES ('JTE:holdout-fixture', 'JTP:release-fixture', 'HOLDOUT:fixture',
                     'CN:TEST', 'COMPANY:holdout', 'TEST', 'TEST_SELECTION', ?, ?,
                     'HISTORICAL_HOLDOUT', 'HISTORICAL_SELF_REPLAY',
                     'PIT_OUTCOME_SEALED', 'COMPANY', '{}')""",
        ("2020-12-31T23:59:59+08:00", "2022-05-01T00:00:00+08:00"),
    )
    conn.execute(
        """INSERT INTO judgment_feedback_claims
             (feedback_item_id, episode_id, claim_id, stage_id, company_id, source_kind,
              source_ref, frozen_at, eligible_at, overdue_at, settlement_version_policy,
              frozen_artifact_ref, source_contract_ref, measurement_contract_ref,
              episode_class, selection_status, learning_eligibility, program_lane,
              outcome_access, training_program_ref, pre_reveal_review_receipt_ref,
              pre_reveal_review_receipt_json, registered_at)
             VALUES ('FBI:holdout-fixture', 'HOLDOUT:fixture', 'D5', 'D5_CAPITAL_RETURN',
                     'CN:TEST', 'OFFICIAL_COMPANY_DISCLOSURE', 'official:fixture', ?, ?, NULL,
                     'INITIAL_DISCLOSURE', ?, ?, ?, 'JUDGMENT_SELECTION_EPISODE',
                     'SELECTION_ADMITTED', 'EVALUATION_ONLY', 'HISTORICAL_HOLDOUT',
                     'PIT_OUTCOME_SEALED', ?, ?, '{}', ?)""",
        (
            "2020-12-31T23:59:59+08:00", "2022-05-01T00:00:00+08:00",
            str(artifact_ref), str(artifact_ref), str(artifact_ref), str(program_ref),
            str(artifact_ref), "2026-08-22T11:00:00+08:00",
        ),
    )
    conn.execute(
        """INSERT INTO judgment_feedback_events
             (event_id, feedback_item_id, event_type, effective_at, recorded_at,
              actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
             VALUES ('JFE:holdout-evaluation', 'FBI:holdout-fixture',
                     'HOLDOUT_EVALUATION_ACCEPTED', ?, ?, 'REVIEWER',
                     'holdout-reviewer', 'holdout-evaluation', '[]', ?)""",
        (
            "2026-08-22T12:00:00+08:00", "2026-08-22T12:01:00+08:00",
            json.dumps({"receipt_id": "HRECEIPT:fixture", "evaluation_verdict": verdict}),
        ),
    )
    conn.commit()
    monkeypatch.setattr(
        jtp, "reconcile", lambda *_, **__: {"historical_method_state": "HISTORICAL_EVALUATION_COMPLETE"},
    )
    monkeypatch.setattr(
        jtp, "_now_dt", lambda: jtp._parse_time("2026-08-23T12:00:00+08:00", "test"),
    )
    receipt = {
        "schema_version": jtp.METHOD_REPORT_RELEASE_SCHEMA_VERSION,
        "release_id": "JMREL:release-fixture:v1",
        "program_id": "JTP:release-fixture",
        "method_version": "selection-v1",
        "method_scope": "SELECTION_AND_BOUNDARY",
        "method_frozen_at": "2026-08-22T10:00:00+08:00",
        "released_at": "2026-08-23T10:00:00+08:00",
        "released_by": "release-owner",
        "release_decision": "METHOD_RELEASED_FOR_REPORT_USE",
        "accepted_holdout_receipt_ids": ["HRECEIPT:fixture"],
    }
    receipt_path = Path(_write(tmp_path / "method-release.json", receipt))
    return conn, receipt_path


def test_supported_holdout_can_be_explicitly_released_for_report_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, receipt = _method_release_fixture(tmp_path, monkeypatch, verdict="SUPPORTED")

    first = jtp.release_method_for_report_use(
        conn, receipt_ref=receipt, recorded_at="2026-08-23T10:01:00+08:00",
    )
    second = jtp.release_method_for_report_use(
        conn, receipt_ref=receipt, recorded_at="2026-08-23T10:01:00+08:00",
    )

    assert first["release_decision"] == "METHOD_RELEASED_FOR_REPORT_USE"
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert conn.execute("SELECT COUNT(*) FROM judgment_training_method_releases").fetchone()[0] == 1


@pytest.mark.parametrize("verdict", ["MIXED", "FAILED", "NOT_DIAGNOSTIC"])
def test_non_supporting_holdout_cannot_release_method_for_report_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verdict: str,
) -> None:
    conn, receipt = _method_release_fixture(tmp_path, monkeypatch, verdict=verdict)

    with pytest.raises(jtp.TrainingProgramError, match="did not support"):
        jtp.release_method_for_report_use(
            conn, receipt_ref=receipt, recorded_at="2026-08-23T10:01:00+08:00",
        )

    assert conn.execute("SELECT COUNT(*) FROM judgment_training_method_releases").fetchone()[0] == 0
