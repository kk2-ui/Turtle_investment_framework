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


def test_reserved_holdout_waits_but_untrained_method_cannot_freeze(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)

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


def test_company_holdout_cannot_reuse_a_training_company_cluster(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["episodes"][1]["company_cluster_id"] = "COMPANY:midea"

    result = jtp.validate_program(payload, contract_path=contract, validate_artifacts=False)

    assert result["state"] == "INVALID"
    assert any(item.endswith("company_holdout_cluster_seen_in_training") for item in result["findings"])


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


def test_method_freeze_requires_a_holdout_reservation(tmp_path: Path) -> None:
    payload, contract = _program(tmp_path)
    payload["method_frozen_at"] = None
    payload["program_state"] = "DRAFT"
    payload["episodes"] = [item for item in payload["episodes"] if item["lane"] != "HISTORICAL_HOLDOUT"]
    contract.write_text(json.dumps(payload), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)

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
