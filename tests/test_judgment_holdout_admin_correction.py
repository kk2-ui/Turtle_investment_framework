from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import judgment_feedback_control as jfc
from scripts import judgment_training_program as jtp


R103 = jfc.R103_HOLDOUT_CASE_ID
SOURCE_PROGRAM = "JTP:selection-development-v1"
TARGET_PROGRAM = "JTP:selection-development-v2"
SOURCE_EPISODE = "JTE:R-103:yinlun-pre-training-holdout-reservation-2020"
TARGET_EPISODE = "JTE:R-104:selection-development"
METHOD_VERSION = "selection-method-v2"
FROZEN_AT = "2026-01-04T00:00:00+00:00"
FREEZE_RECORDED_AT = "2026-01-04T01:00:00+00:00"
AS_OF = "2026-01-10T00:00:00+00:00"


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _state(conn: object) -> str:
    status = jtp.reconcile(conn, program_id=TARGET_PROGRAM, as_of=AS_OF)
    return next(item["state"] for item in status["items"] if item["case_id"] == R103)


def _setup(tmp_path: Path) -> tuple[object, Path, Path, Path]:
    conn = jtp.connect(tmp_path / "judgment.sqlite")
    jtp.initialize(conn)
    source_contract = _write(tmp_path / "source-program.json", {"program": "source"})
    target_contract = _write(tmp_path / "target-program.json", {"program": "target"})
    holdout_root = tmp_path / "R-103"
    holdout_root.mkdir()
    freeze = _write(holdout_root / "01_holdout_freeze.json", {"freeze": "sealed"})
    source_row = (
        SOURCE_PROGRAM, "ACTIVE", "selection-method-v1", "SELECTION_AND_BOUNDARY",
        "2026-01-01T00:00:00+00:00", None, None, "{}", str(source_contract),
    )
    target_row = (
        TARGET_PROGRAM, "ACTIVE", METHOD_VERSION, "SELECTION_AND_BOUNDARY",
        "2026-01-02T00:00:00+00:00", FROZEN_AT, FREEZE_RECORDED_AT, "{}", str(target_contract),
    )
    conn.execute(
        """INSERT INTO judgment_training_programs
           (program_id, program_state, method_version, method_scope, registered_at,
            method_frozen_at, method_freeze_recorded_at, sampling_policy_json, contract_ref)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        source_row,
    )
    conn.execute(
        """INSERT INTO judgment_training_programs
           (program_id, program_state, method_version, method_scope, registered_at,
            method_frozen_at, method_freeze_recorded_at, sampling_policy_json, contract_ref)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        target_row,
    )
    episode_columns = (
        "training_episode_id", "program_id", "case_id", "company_id", "company_cluster_id",
        "industry_id", "decision_domain", "cutoff_at", "outcome_not_before", "lane",
        "provenance_role", "outcome_access", "holdout_axis", "artifacts_json",
    )
    source_episode = (
        SOURCE_EPISODE, SOURCE_PROGRAM, R103, "CN:002126", "COMPANY:yinlun",
        "CN_AUTOMOTIVE_THERMAL_MANAGEMENT", "NEV", "2020-12-31T23:59:59+00:00",
        "2023-05-01T00:00:00+00:00", "HISTORICAL_HOLDOUT", "HISTORICAL_SELF_REPLAY",
        "PIT_OUTCOME_SEALED", "COMPANY", json.dumps({"freeze_ref": str(freeze)}),
    )
    target_episode = (
        TARGET_EPISODE, TARGET_PROGRAM, "SELECTIONCASE:R-104", "CN:600132", "COMPANY:chongqing-beer",
        "CN_BEER", "NETWORK_PRUNING", "2016-04-30T23:59:59+00:00",
        "2017-04-01T00:00:00+00:00", "HISTORICAL_TRAINING", "HISTORICAL_SELF_REPLAY",
        "PIT_OUTCOME_SEALED", None, "{}",
    )
    conn.execute(
        f"INSERT INTO judgment_training_episodes ({','.join(episode_columns)}) VALUES ({','.join('?' for _ in episode_columns)})",
        source_episode,
    )
    conn.execute(
        f"INSERT INTO judgment_training_episodes ({','.join(episode_columns)}) VALUES ({','.join('?' for _ in episode_columns)})",
        target_episode,
    )
    conn.execute(
        """INSERT INTO judgment_training_holdout_links
           (program_id, source_program_id, source_training_episode_id, source_case_id,
            source_freeze_ref, link_role)
           VALUES (?, ?, ?, ?, ?, 'HISTORICAL_HOLDOUT')""",
        (TARGET_PROGRAM, SOURCE_PROGRAM, SOURCE_EPISODE, R103, str(freeze)),
    )
    conn.execute(
        """INSERT INTO judgment_training_artifact_events
           (training_episode_id, artifact_kind, artifact_ref, recorded_at, content_json, content_text)
           VALUES (?, 'freeze_ref', ?, '2026-01-03T00:00:00+00:00', NULL, ?)""",
        (SOURCE_EPISODE, str(freeze), freeze.read_text(encoding="utf-8")),
    )
    source = _write(tmp_path / "source.json", {})
    measurement = _write(tmp_path / "measurement.json", {})
    feedback_item_id = "FBI:SELECTIONCASE:R-104:R-104:D5:D5_CAPITAL_RETURN"
    conn.execute(
        """INSERT INTO judgment_feedback_claims
           (feedback_item_id, episode_id, claim_id, stage_id, company_id, source_kind,
            source_ref, frozen_at, eligible_at, overdue_at, settlement_version_policy,
            frozen_artifact_ref, source_contract_ref, measurement_contract_ref,
            episode_class, selection_status, learning_eligibility, program_lane,
            outcome_access, training_program_ref, registered_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            feedback_item_id, "SELECTIONCASE:R-104", "R-104:D5", "D5_CAPITAL_RETURN", "CN:600132",
            "OFFICIAL", "official:R-104", "2026-01-02T00:00:00+00:00", "2026-01-02T00:00:00+00:00",
            "INITIAL_DISCLOSURE", str(freeze), str(source), str(measurement),
            "JUDGMENT_SELECTION_EPISODE", "SELECTION_ADMITTED", "SELECTION_METHOD_ELIGIBLE",
            "HISTORICAL_TRAINING", "PIT_OUTCOME_SEALED", str(target_contract), "2026-01-02T00:00:00+00:00",
        ),
    )
    conn.execute(
        """INSERT INTO judgment_feedback_events
           (event_id, feedback_item_id, event_type, effective_at, recorded_at,
            actor_role, actor_id, idempotency_key, artifact_refs_json, payload_json)
           VALUES ('JFE:R-104:LEARNING_APPLIED', ?, 'LEARNING_APPLIED',
                   '2026-01-03T00:00:00+00:00', '2026-01-03T00:00:00+00:00',
                   'REVIEWER', 'r104-learner', 'R104:LEARNING_APPLIED', '[]', '{}')""",
        (feedback_item_id,),
    )
    conn.commit()
    return conn, target_contract, freeze, holdout_root


def _correction(tmp_path: Path, *, target_contract: Path) -> Path:
    method_review = _write(tmp_path / "method-review.json", {
        "schema_version": "judgment-selection-method-freeze-review.v1",
        "review_id": "METHODREVIEW:R-104:v1",
        "method_version": METHOD_VERSION,
        "reviewer_id": "method-reviewer",
        "reviewed_at": "2026-01-03T12:00:00+00:00",
        "verdict": "FROZEN_SELECTION_METHOD_ACCEPTED",
    })
    return _write(tmp_path / "04a_post_freeze_administrative_prerequisite_correction.json", {
        "schema_version": jfc.HOLDOUT_ADMIN_CORRECTION_SCHEMA_VERSION,
        "correction_id": "HADMINCORR:R-103:v1",
        "program_id": TARGET_PROGRAM,
        "source_program_id": SOURCE_PROGRAM,
        "training_episode_id": SOURCE_EPISODE,
        "case_id": R103,
        "method_version": METHOD_VERSION,
        "method_scope": "SELECTION_AND_BOUNDARY",
        "method_frozen_at": FROZEN_AT,
        "method_freeze_recorded_at": FREEZE_RECORDED_AT,
        "method_application_event_id": "JFE:R-104:LEARNING_APPLIED",
        "independent_method_review_ref": str(method_review),
        "correction_author_id": "admin-author",
        "method_designer_id": "method-designer",
        "r102_learner_id": "r102-learner",
        "future_evaluator_id": "r103-isolated-evaluator",
        "outcome_custodian_id": "r103-outcome-custodian",
        "corrected_at": "2026-01-05T00:00:00+00:00",
        "superseded_prerequisite": "R-102 development-specific textual prerequisite",
        "replacement_prerequisite": "the frozen linked selection method and its independent review govern R-103",
        "sealed_core_mutation": "NONE",
        "outcome_body_access": "NOT_OPENED",
        "authorization_effect": "NO_APPLICATION_CONTROL_OR_OUTCOME_REVEAL",
    })


def _review(tmp_path: Path, correction: Path, *, reviewer_id: str = "admin-independent-reviewer") -> Path:
    snapshot = json.loads(correction.read_text(encoding="utf-8"))
    return _write(tmp_path / "04b_independent_administrative_prerequisite_review.json", {
        "schema_version": jfc.HOLDOUT_ADMIN_CORRECTION_REVIEW_SCHEMA_VERSION,
        "review_id": "HADMINREVIEW:R-103:v1",
        "correction_id": snapshot["correction_id"],
        "program_id": snapshot["program_id"],
        "training_episode_id": snapshot["training_episode_id"],
        "case_id": snapshot["case_id"],
        "correction_ref": str(correction),
        "reviewed_correction": snapshot,
        "reviewer_id": reviewer_id,
        "reviewer_acceptance": "ACCEPTED",
        "reviewed_at": "2026-01-06T00:00:00+00:00",
        "verdict": "ADMINISTRATIVE_PREREQUISITE_CORRECTION_ACCEPTED",
        "sealed_core_mutation": "NONE",
        "outcome_body_access": "NOT_OPENED",
        "authorization_effect": "NO_APPLICATION_CONTROL_OR_OUTCOME_REVEAL",
    })


def test_r103_overlay_is_append_only_and_gates_control_in_order(tmp_path: Path) -> None:
    conn, target_contract, freeze, root = _setup(tmp_path)
    claim = {
        "program_lane": "HISTORICAL_HOLDOUT",
        "learning_eligibility": "EVALUATION_ONLY",
        "training_program_ref": str(tmp_path / "source-program.json"),
        "episode_id": R103,
    }
    assert _state(conn) == "ADMINISTRATIVE_CORRECTION_REQUIRED"
    with pytest.raises(jfc.ControlPlaneError) as blocked:
        jfc._require_frozen_holdout_program(
            conn, claim, effective_at=jfc._parse_time(AS_OF, field="test"),
        )
    assert blocked.value.code == "administrative_correction_required"

    correction = _correction(tmp_path, target_contract=target_contract)
    first = jfc.append_holdout_admin_correction(
        conn, correction_ref=correction, recorded_at="2026-01-05T01:00:00+00:00",
    )
    assert first["idempotent"] is False
    assert jfc.append_holdout_admin_correction(
        conn, correction_ref=correction, recorded_at="2026-01-05T02:00:00+00:00",
    )["idempotent"] is True
    assert _state(conn) == "ADMINISTRATIVE_CORRECTION_REVIEW_REQUIRED"

    rejected_review = _review(tmp_path, correction, reviewer_id="r102-learner")
    with pytest.raises(jfc.ControlPlaneError) as independence:
        jfc.review_holdout_admin_correction(
            conn, review_ref=rejected_review, recorded_at="2026-01-06T01:00:00+00:00",
        )
    assert independence.value.code == "holdout_admin_reviewer_not_independent"
    accepted_review = _review(tmp_path, correction)
    jfc.review_holdout_admin_correction(
        conn, review_ref=accepted_review, recorded_at="2026-01-06T01:00:00+00:00",
    )
    assert _state(conn) == "FROZEN_METHOD_APPLICATION_REQUIRED"

    application = _write(root / "05_frozen_method_application_prediction.json", {
        "schema_version": jfc.HOLDOUT_METHOD_APPLICATION_SCHEMA_VERSION,
        "application_id": "HAPP:R-103:v1",
        "program_id": TARGET_PROGRAM,
        "source_program_id": SOURCE_PROGRAM,
        "training_episode_id": SOURCE_EPISODE,
        "case_id": R103,
        "method_version": METHOD_VERSION,
        "method_scope": "SELECTION_AND_BOUNDARY",
        "method_frozen_at": FROZEN_AT,
        "method_freeze_recorded_at": FREEZE_RECORDED_AT,
        "application_author_id": "r103-isolated-evaluator",
        "applied_at": "2026-01-07T00:00:00+00:00",
        "outcome_body_access": "NOT_OPENED_BEFORE_CONTROL_REGISTRATION",
        "selection_status": "NO_PRIMARY",
        "claims": [{"stage_id": stage} for stage in jfc.REQUIRED_SELECTION_STAGE_IDS],
    })
    assert application.is_file()
    assert _state(conn) == "PRE_REVEAL_REVIEW_REQUIRED"

    _write(root / "06_independent_pre_reveal_receipt.json", {
        "schema_version": jfc.HOLDOUT_PRE_REVEAL_REVIEW_SCHEMA_VERSION,
        "receipt_id": "PREREVIEW:R-103:v1",
        "case_id": R103,
        "application_id": "HAPP:R-103:v1",
        "reviewer_id": "r103-pre-reveal-reviewer",
        "reviewed_at": "2026-01-08T00:00:00+00:00",
        "verdict": "PRE_REVEAL_EVALUATION_CONTRACT_ACCEPTED",
        "outcome_body_access": "NOT_OPENED_BEFORE_CONTROL_REGISTRATION",
    })
    assert _state(conn) == "READY_FOR_CONTROL_REGISTRATION"
    assert jfc._require_frozen_holdout_program(
        conn, claim, effective_at=jfc._parse_time(AS_OF, field="test"),
    )["program_id"] == TARGET_PROGRAM


def test_r103_linked_holdout_rejects_boundary_scope_before_correction(tmp_path: Path) -> None:
    conn, _, _, _ = _setup(tmp_path)
    conn.execute(
        "UPDATE judgment_training_programs SET method_scope = 'BOUNDARY_ONLY' WHERE program_id = ?",
        (TARGET_PROGRAM,),
    )
    conn.commit()

    assert _state(conn) == "R103_SELECTION_METHOD_SCOPE_MISMATCH"
