from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts import judgment_feedback_control as jfc
from scripts import judgment_training_program as jtp


CASE_ID = "R-HOLDOUT-01"
PROGRAM_ID = "JTP:holdout-evaluation-test"
METHOD_VERSION = "boundary-method-test-v1"
METHOD_FROZEN_AT = "2026-02-01T00:00:00+00:00"
SETTLED_AT = "2026-03-01T00:00:00+00:00"
TEST_NOW = "2026-08-23T14:30:00+00:00"
STAGES = {
    "D1": "D1_IMPLEMENTATION",
    "D2": "D2_CUSTOMER_COMPETITOR",
    "D3": "D3_UNIT_ECONOMICS",
    "D4": "D4_CASH_BRIDGE",
    "D5": "D5_CAPITAL_RECOVERY",
}


@pytest.fixture(autouse=True)
def _fixed_real_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.fromisoformat(TEST_NOW)
    monkeypatch.setattr(jfc, "_now_dt", lambda: now)
    monkeypatch.setattr(jtp, "_now_dt", lambda: now)


def _write(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _register_program(tmp_path: Path, *, method_frozen_at: str | None) -> tuple[object, Path, Path, Path]:
    universe = tmp_path / "cohort.json"
    _write(universe, {"selection_rule": "all cutoff-eligible states"})
    training_freeze = tmp_path / "training-freeze.json"
    _write(training_freeze, {"freeze_id": "FREEZE:TRAINING"})
    holdout_freeze = tmp_path / "holdout-pre-reveal-review.md"
    holdout_freeze.write_text("reviewed before outcome reveal\n", encoding="utf-8")
    pre_review = tmp_path / "pre-reveal-review.json"
    _write(pre_review, {
        "schema_version": jfc.HOLDOUT_PRE_REVEAL_REVIEW_SCHEMA_VERSION,
        "receipt_id": "PREREVIEW:R-HOLDOUT-01:v1",
        "case_id": CASE_ID,
        "reviewer_id": "pre-reviewer",
        "reviewed_at": "2026-01-01T00:00:00+00:00",
        "verdict": "PRE_REVEAL_EVALUATION_CONTRACT_ACCEPTED",
        "outcome_body_access": "NOT_OPENED_BEFORE_CONTROL_REGISTRATION",
    })
    contract = tmp_path / "training-program.json"
    program = {
        "schema_version": jtp.SCHEMA_VERSION,
        "program_state": "ACTIVE",
        "program_id": PROGRAM_ID,
        "method_version": METHOD_VERSION,
        "method_scope": "BOUNDARY_ONLY",
        "registered_at": "2026-01-01T00:00:00+00:00",
        "method_frozen_at": method_frozen_at,
        "sampling_policy": {
            "universe_ref": universe.name,
            "cohort_formed_as_of_cutoff": True,
            "outcome_used_for_selection": False,
            "terminal_status_coverage": "ALL_CUTOFF_ELIGIBLE_STATES",
            "same_company_periods_count_as_independent": False,
        },
        "episodes": [
            {
                "training_episode_id": "JTE:training-2020",
                "case_id": "R-TRAINING-01",
                "company_id": "CN:TRAIN",
                "company_cluster_id": "COMPANY:TRAIN",
                "industry_id": "MANUFACTURING",
                "decision_domain": "CAPACITY",
                "cutoff_at": "2020-12-31T23:59:59+00:00",
                "outcome_not_before": "2021-04-01T00:00:00+00:00",
                "lane": "HISTORICAL_TRAINING",
                "provenance_role": "HISTORICAL_SELF_REPLAY",
                "outcome_access": "PIT_OUTCOME_SEALED",
                "artifacts": {"freeze_ref": training_freeze.name},
            },
            {
                "training_episode_id": "JTE:holdout-2021",
                "case_id": CASE_ID,
                "company_id": "CN:HOLDOUT",
                "company_cluster_id": "COMPANY:HOLDOUT",
                "industry_id": "MANUFACTURING",
                "decision_domain": "CAPACITY",
                "cutoff_at": "2021-12-31T23:59:59+00:00",
                "outcome_not_before": "2022-04-01T00:00:00+00:00",
                "lane": "HISTORICAL_HOLDOUT",
                "provenance_role": "HISTORICAL_SELF_REPLAY",
                "outcome_access": "PIT_OUTCOME_SEALED",
                "holdout_axis": "COMPANY_AND_TIME",
                "artifacts": {"freeze_ref": holdout_freeze.name},
            },
        ],
    }
    contract.write_text(json.dumps(program), encoding="utf-8")
    conn = jtp.connect(tmp_path / "stock_analysis.db")
    jtp.initialize(conn)
    jtp.register_program(conn, contract)
    if method_frozen_at is not None:
        conn.execute(
            "UPDATE judgment_training_programs SET method_freeze_recorded_at = ? WHERE program_id = ?",
            ("2026-02-01T01:00:00+00:00", PROGRAM_ID),
        )
        conn.commit()
    return conn, contract, holdout_freeze, pre_review


def _register_holdout_claims(
    tmp_path: Path, conn: object, contract: Path, holdout_freeze: Path, pre_review: Path,
) -> dict[str, dict]:
    source = tmp_path / "outcome-contract.json"
    measurement = tmp_path / "measurement-contract.json"
    _write(source, {"required_clock_ids": sorted(STAGES)})
    _write(measurement, {"clock_ids": sorted(STAGES)})
    manifest = {
        "schema_version": jfc.REGISTRATION_SCHEMA_VERSION,
        "episode_id": CASE_ID,
        "company_id": "CN:HOLDOUT",
        "frozen_at": "2021-12-31T23:59:59+00:00",
        "episode_class": "MECHANISM_SIGNAL_PROBE",
        "selection_status": "NO_PRIMARY",
        "learning_eligibility": "EVALUATION_ONLY",
        "program_lane": "HISTORICAL_HOLDOUT",
        "outcome_access": "PIT_OUTCOME_SEALED",
        "training_program_ref": str(contract),
        "pre_reveal_review_receipt_ref": str(pre_review),
        "claims": [
            {
                "claim_id": f"{CASE_ID}:{clock}",
                "stages": [{
                    "stage_id": stage,
                    "source_kind": "OFFICIAL_COMPANY_DISCLOSURE",
                    "source_ref": f"official:{clock}",
                    "eligible_at": "2022-04-01T00:00:00+00:00",
                    "settlement_version_policy": "INITIAL_DISCLOSURE",
                    "frozen_artifact_ref": str(holdout_freeze),
                    "source_contract_ref": str(source),
                    "measurement_contract_ref": str(measurement),
                }],
            }
            for clock, stage in STAGES.items()
        ],
    }
    jfc.register_manifest(conn, manifest, registered_at="2026-01-02T00:00:00+00:00")
    rows = conn.execute(
        "SELECT * FROM judgment_feedback_claims WHERE episode_id = ? ORDER BY stage_id",
        (CASE_ID,),
    ).fetchall()
    return {row["stage_id"][:2]: dict(row) for row in rows}


def _outcome(tmp_path: Path, holdout_freeze: Path) -> Path:
    payload = {
        "schema_version": "judgment-boundary-outcome.v1",
        "case_id": CASE_ID,
        "freeze_id": "JTE:holdout-2021",
        "settlement_id": f"HSETTLE:{CASE_ID}",
        "settlement_as_of": SETTLED_AT,
        "first_outcome_accessed_at": "2026-02-02T00:00:00+00:00",
        "selection_status": "NO_PRIMARY",
        "sources": [{"source_id": "official:later", "official": True}],
        "clocks": [
            {
                "clock": clock,
                "claim_id": f"{CASE_ID}:{clock}",
                "status": "NOT_DIAGNOSTIC",
                "measurement_scope": f"{clock} responsibility-unit observation",
                "missing_facts": "responsibility-unit field remains unavailable",
                "prohibited_substitutes": "group totals cannot replace the frozen unit",
                "source_ids": ["official:later"],
            }
            for clock in STAGES
        ],
    }
    path = tmp_path / "holdout-outcome.json"
    _write(path, payload)
    return path


def _setup(
    tmp_path: Path, *, method_frozen_at: str | None = METHOD_FROZEN_AT,
) -> tuple[object, dict[str, dict], Path]:
    conn, contract, holdout_freeze, pre_review = _register_program(
        tmp_path, method_frozen_at=method_frozen_at,
    )
    claims = _register_holdout_claims(tmp_path, conn, contract, holdout_freeze, pre_review)
    return conn, claims, _outcome(tmp_path, holdout_freeze)


def _settle(conn: object, claims: dict[str, dict], outcome: Path, tmp_path: Path, clock: str) -> dict:
    return jfc.run_holdout_settlement(
        conn,
        feedback_item_id=claims[clock]["feedback_item_id"],
        outcome_ref=outcome,
        event_root=tmp_path / "events",
        settlement_as_of=SETTLED_AT,
    )


def _receipt(tmp_path: Path, conn: object, claims: dict[str, dict]) -> Path:
    claim_settlements = []
    for clock, claim in claims.items():
        settlement = jfc._settlement_events(jfc._events(conn, claim["feedback_item_id"]))[-1]
        claim_settlements.append({
            "clock": clock,
            "feedback_item_id": claim["feedback_item_id"],
            "claim_id": claim["claim_id"],
            "stage_id": claim["stage_id"],
            "settlement_event_id": settlement["event_id"],
        })
    payload = {
        "schema_version": jfc.HOLDOUT_EVALUATION_RECEIPT_SCHEMA_VERSION,
        "receipt_id": "HRECEIPT:R-HOLDOUT-01:v1",
        "program_id": PROGRAM_ID,
        "training_episode_id": "JTE:holdout-2021",
        "case_id": CASE_ID,
        "method_version": METHOD_VERSION,
        "method_frozen_at": METHOD_FROZEN_AT,
        "evaluated_at": TEST_NOW,
        "evaluation_verdict": "NOT_DIAGNOSTIC",
        "evaluation_author_id": "holdout-evaluator",
        "reviewer_id": "independent-reviewer",
        "reviewer_acceptance": "ACCEPTED",
        "claim_settlements": claim_settlements,
    }
    path = tmp_path / "holdout-evaluation-receipt.json"
    _write(path, payload)
    return path


def _program_holdout_state(conn: object) -> str:
    status = jtp.reconcile(conn, program_id=PROGRAM_ID, as_of=TEST_NOW)
    return next(item["state"] for item in status["items"] if item["lane"] == "HISTORICAL_HOLDOUT")


def test_holdout_settlement_rejects_before_method_freeze(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path, method_frozen_at=None)

    with pytest.raises(jfc.ControlPlaneError) as error:
        _settle(conn, claims, outcome, tmp_path, "D1")

    assert error.value.code == "holdout_method_not_frozen"


def test_holdout_settlement_rejects_wrong_learning_eligibility(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    conn.execute(
        "UPDATE judgment_feedback_claims SET learning_eligibility = 'BOUNDARY_METHOD_ELIGIBLE' WHERE feedback_item_id = ?",
        (claims["D1"]["feedback_item_id"],),
    )
    conn.commit()

    with pytest.raises(jfc.ControlPlaneError) as error:
        _settle(conn, claims, outcome, tmp_path, "D1")

    assert error.value.code == "holdout_evaluation_identity_invalid"


def test_d1_d5_settlement_requires_independent_receipt_and_never_grants_learning(
    tmp_path: Path,
) -> None:
    conn, claims, outcome = _setup(tmp_path)

    for clock in ("D1", "D2", "D3", "D4"):
        _settle(conn, claims, outcome, tmp_path, clock)
        assert _program_holdout_state(conn) == "HOLDOUT_EVALUATION_ACTIVE"
    _settle(conn, claims, outcome, tmp_path, "D5")
    assert _program_holdout_state(conn) == "EVALUATION_RECEIPT_PENDING"

    receipt = _receipt(tmp_path, conn, claims)
    result = jfc.accept_holdout_evaluation_receipt(
        conn,
        receipt_ref=receipt,
        accepted_at=TEST_NOW,
    )

    assert result["status"] == "EVALUATED_HOLDOUT"
    assert _program_holdout_state(conn) == "EVALUATED_HOLDOUT"
    d1 = claims["D1"]
    settlement = jfc._settlement_events(jfc._events(conn, d1["feedback_item_id"]))[-1]
    forbidden_events = {
        "DIAGNOSIS_ACCEPTED": {"settlement_event_id": settlement["event_id"]},
        "LEARNING_NOTE_READY": {},
        "LEARNING_APPLIED": {},
    }
    for event_type, payload in forbidden_events.items():
        with pytest.raises(jfc.ControlPlaneError) as error:
            jfc.append_event(conn, {
                "feedback_item_id": d1["feedback_item_id"],
                "event_type": event_type,
                "effective_at": "2026-03-04T00:00:00+00:00",
                "actor_role": "RESEARCHER",
                "actor_id": "attempted-learner",
                "idempotency_key": f"FORBIDDEN:{event_type}",
                "artifact_refs": [str(outcome)],
                "payload": payload,
            })
        assert error.value.code in {
            "diagnosis_not_permitted_for_evaluation_only",
            "learning_not_permitted_for_episode",
        }
    assert jfc.show(
        conn, d1["feedback_item_id"], as_of=TEST_NOW,
    )["states"]["learning_state"] == "NONE"


def test_real_clock_rejects_future_registration_and_inverted_event_times(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    with pytest.raises(jfc.ControlPlaneError) as registration_error:
        jfc.register_manifest(
            conn,
            {"schema_version": jfc.REGISTRATION_SCHEMA_VERSION},
            registered_at="2026-08-23T14:31:00+00:00",
        )
    assert registration_error.value.code == "registration_in_future"

    event = {
        "feedback_item_id": claims["D1"]["feedback_item_id"],
        "event_type": "CLOSED",
        "effective_at": "2026-03-02T00:00:00+00:00",
        "actor_role": "RESEARCHER",
        "actor_id": "temporal-test",
        "idempotency_key": "TEMPORAL:INVERTED",
        "artifact_refs": [str(outcome)],
        "payload": {"closure_reason": "test"},
    }
    with pytest.raises(jfc.ControlPlaneError) as inverted_error:
        jfc.append_event(
            conn, event, recorded_at="2026-03-01T00:00:00+00:00",
        )
    assert inverted_error.value.code == "event_effective_after_recorded"
    with pytest.raises(jfc.ControlPlaneError) as future_error:
        jfc.append_event(
            conn,
            {**event, "idempotency_key": "TEMPORAL:FUTURE"},
            recorded_at="2026-08-23T14:31:00+00:00",
        )
    assert future_error.value.code == "event_recorded_in_future"


def test_legacy_freeze_without_recorded_receipt_cannot_be_repaired(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    conn.execute(
        "UPDATE judgment_training_programs SET method_freeze_recorded_at = NULL WHERE program_id = ?",
        (PROGRAM_ID,),
    )
    conn.commit()

    with pytest.raises(jfc.ControlPlaneError) as settlement_error:
        _settle(conn, claims, outcome, tmp_path, "D1")
    assert settlement_error.value.code == "holdout_method_freeze_receipt_missing"
    assert _program_holdout_state(conn) == "NEEDS_REPAIR"
    with pytest.raises(jtp.TrainingProgramError, match="cannot be backfilled"):
        jtp.freeze_method(
            conn,
            program_id=PROGRAM_ID,
            method_version=METHOD_VERSION,
            frozen_at=METHOD_FROZEN_AT,
        )


def test_pre_reveal_receipt_snapshot_cannot_change_after_registration(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    receipt_path = Path(claims["D1"]["pre_reveal_review_receipt_ref"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["reviewed_at"] = "2026-01-01T00:01:00+00:00"
    _write(receipt_path, receipt)

    with pytest.raises(jfc.ControlPlaneError) as error:
        _settle(conn, claims, outcome, tmp_path, "D1")
    assert error.value.code == "pre_reveal_review_receipt_changed"


def test_first_outcome_access_must_follow_all_prerequisites(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    payload = json.loads(outcome.read_text(encoding="utf-8"))
    payload["first_outcome_accessed_at"] = "2026-01-01T12:00:00+00:00"
    _write(outcome, payload)

    with pytest.raises(jfc.ControlPlaneError) as error:
        _settle(conn, claims, outcome, tmp_path, "D1")
    assert error.value.code == "holdout_outcome_access_precedes_prerequisites"


def test_acceptance_replays_legacy_event_times_before_writing(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    for clock in STAGES:
        _settle(conn, claims, outcome, tmp_path, clock)
    conn.execute(
        """UPDATE judgment_feedback_events
              SET effective_at = '2026-03-02T00:00:00+00:00',
                  recorded_at = '2026-03-01T00:00:00+00:00'
            WHERE feedback_item_id = ? AND event_type = 'ACQUISITION_STARTED'""",
        (claims["D1"]["feedback_item_id"],),
    )
    conn.commit()
    receipt = _receipt(tmp_path, conn, claims)

    with pytest.raises(jfc.ControlPlaneError) as error:
        jfc.accept_holdout_evaluation_receipt(
            conn, receipt_ref=receipt, accepted_at=TEST_NOW,
        )
    assert error.value.code == "holdout_event_time_invalid"
    accepted = conn.execute(
        "SELECT COUNT(*) AS count FROM judgment_feedback_events WHERE event_type = 'HOLDOUT_EVALUATION_ACCEPTED'",
    ).fetchone()["count"]
    assert accepted == 0


def test_breach_records_dirty_legacy_shape_and_remains_irreversible(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    conn.execute(
        "UPDATE judgment_training_programs SET method_freeze_recorded_at = NULL WHERE program_id = ?",
        (PROGRAM_ID,),
    )
    conn.execute(
        "UPDATE judgment_feedback_claims SET registered_at = '2026-08-23T14:31:00+00:00' WHERE episode_id = ?",
        (CASE_ID,),
    )
    conn.commit()
    breach = tmp_path / "breach.json"
    _write(breach, {
        "schema_version": jfc.HOLDOUT_EXPOSURE_BREACH_SCHEMA_VERSION,
        "breach_id": "HBREACH:R-HOLDOUT-01:v1",
        "case_id": CASE_ID,
        "first_outcome_accessed_at": "2026-08-23T14:00:00+00:00",
        "discovered_at": "2026-08-23T14:20:00+00:00",
        "root_cause": "MODEL",
        "disposition": "HOLDOUT_INVALIDATED",
    })

    recorded = jfc.record_holdout_exposure_breach(
        conn,
        feedback_item_id=claims["D1"]["feedback_item_id"],
        breach_ref=breach,
    )
    assert recorded["status"] == "EXPOSURE_BREACH"

    conn.execute(
        "UPDATE judgment_training_programs SET method_freeze_recorded_at = ? WHERE program_id = ?",
        ("2026-02-01T01:00:00+00:00", PROGRAM_ID),
    )
    conn.execute(
        "UPDATE judgment_feedback_claims SET registered_at = '2026-01-02T00:00:00+00:00' WHERE episode_id = ?",
        (CASE_ID,),
    )
    conn.commit()
    with pytest.raises(jfc.ControlPlaneError) as error:
        _settle(conn, claims, outcome, tmp_path, "D1")
    assert error.value.code == "holdout_outcome_blocked_by_exposure_breach"


def test_holdout_projection_hides_events_recorded_after_as_of(tmp_path: Path) -> None:
    conn, claims, outcome = _setup(tmp_path)
    for clock in STAGES:
        _settle(conn, claims, outcome, tmp_path, clock)
    receipt = _receipt(tmp_path, conn, claims)
    jfc.accept_holdout_evaluation_receipt(
        conn, receipt_ref=receipt, accepted_at=TEST_NOW,
    )

    past = jtp.reconcile(
        conn, program_id=PROGRAM_ID, as_of="2026-03-02T00:00:00+00:00",
    )
    current = jtp.reconcile(conn, program_id=PROGRAM_ID, as_of=TEST_NOW)
    past_holdout = next(item for item in past["items"] if item["lane"] == "HISTORICAL_HOLDOUT")
    current_holdout = next(item for item in current["items"] if item["lane"] == "HISTORICAL_HOLDOUT")
    assert past_holdout["state"] == "HOLDOUT_EVALUATION_ACTIVE"
    assert current_holdout["state"] == "EVALUATED_HOLDOUT"
