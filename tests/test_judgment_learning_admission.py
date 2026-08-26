from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import judgment_feedback_control as jfc
from scripts import judgment_training_program as jtp
from scripts.judgment_generation_handoff import build_judgment_generation_handoff
from scripts.judgment_learning import (
    build_judgment_learning_note,
    build_method_feedback_review,
)
from scripts.judgment_learning_admission import (
    refresh_analysis_contract_learning_admissions,
    select_judgment_learning_admissions,
)


CUTOFF = "2026-08-23T23:59:59+08:00"


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path.resolve()


def _event(
    conn: sqlite3.Connection,
    feedback_item_id: str,
    event_type: str,
    event_id: str,
    effective_at: str,
    *,
    artifact_ref: Path,
    payload: dict | None = None,
) -> dict:
    body = dict(payload or {})
    if event_type in jfc.OUTCOME_PIPELINE_EVENTS | jfc.OUTCOME_EVENTS:
        body.setdefault("settlement_version", 1)
    return jfc._append_event(
        conn,
        {
            "event_id": event_id,
            "feedback_item_id": feedback_item_id,
            "event_type": event_type,
            "effective_at": effective_at,
            "actor_role": "AUTOMATION",
            "actor_id": "learning-admission-fixture",
            "idempotency_key": event_id,
            "artifact_refs": [str(artifact_ref)],
            "payload": body,
        },
        allow_adapter_events=True,
    )


def _valid_control_plane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    fixed_now = datetime(2026, 8, 23, 4, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(jfc, "_now_dt", lambda: fixed_now)

    thesis = _write(tmp_path / "source_thesis.json", {"fixture": "source"})
    source_contract = _write(tmp_path / "outcome_contract.json", {"fixture": "source-contract"})
    measurement = _write(tmp_path / "measurement_contract.json", {"fixture": "measurement"})
    program = _write(tmp_path / "training_program.json", {"fixture": "program"})
    database = tmp_path / "control-plane.db"
    conn = jfc.connect(database)
    jtp.initialize(conn)
    method_frozen_at = "2026-08-22T16:00:00+08:00"
    method_released_at = "2026-08-23T10:00:00+08:00"
    stored_method_frozen_at = "2026-08-22T08:00:00+00:00"
    stored_method_released_at = "2026-08-23T02:00:00+00:00"
    release_receipt = {
        "schema_version": "judgment-method-report-release.v1",
        "release_id": "JMREL:fixture:v1",
        "program_id": "JTP:fixture:v1",
        "method_version": "enterprise-judgment-fixture-v1",
        "method_scope": "SELECTION_AND_BOUNDARY",
        "method_frozen_at": method_frozen_at,
        "released_at": method_released_at,
        "released_by": "fixture-release-owner",
        "release_decision": "METHOD_RELEASED_FOR_REPORT_USE",
        "accepted_holdout_receipt_ids": ["HRECEIPT:fixture"],
    }
    conn.execute(
        """INSERT INTO judgment_training_programs
             (program_id, program_state, method_version, method_scope, registered_at,
              method_frozen_at, method_freeze_recorded_at, sampling_policy_json, contract_ref)
             VALUES (?, 'ACTIVE', ?, 'SELECTION_AND_BOUNDARY', ?, ?, ?, '{}', ?)""",
        (
            "JTP:fixture:v1", "enterprise-judgment-fixture-v1",
            "2026-01-01T00:00:00+08:00", stored_method_frozen_at,
            "2026-08-22T16:01:00+08:00", str(program),
        ),
    )
    conn.execute(
        """INSERT INTO judgment_training_method_releases
             (program_id, release_id, method_version, method_scope, method_frozen_at,
              released_at, recorded_at, released_by, release_decision, receipt_ref, receipt_json)
             VALUES (?, ?, ?, 'SELECTION_AND_BOUNDARY', ?, ?, ?, ?,
                     'METHOD_RELEASED_FOR_REPORT_USE', ?, ?)""",
        (
            "JTP:fixture:v1", "JMREL:fixture:v1", "enterprise-judgment-fixture-v1",
            stored_method_frozen_at, stored_method_released_at, "2026-08-23T11:00:00+08:00",
            "fixture-release-owner", str(tmp_path / "method_release.json"),
            json.dumps(release_receipt, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()
    jfc.register_manifest(
        conn,
        {
            "schema_version": "judgment-feedback-control-registration.v1",
            "episode_id": "R-SOURCE",
            "company_id": "COMPANY:source",
            "frozen_at": "2026-01-01T00:00:00+08:00",
            "episode_class": "JUDGMENT_SELECTION_EPISODE",
            "selection_status": "SELECTION_ADMITTED",
            "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
            "program_lane": "HISTORICAL_TRAINING",
            "outcome_access": "PIT_OUTCOME_SEALED",
            "training_program_ref": str(program),
            "claims": [{
                "claim_id": "FJ:SOURCE",
                "stages": [{
                    "stage_id": "S1",
                    "source_kind": "OFFICIAL_COMPANY_DISCLOSURE",
                    "source_ref": "official:source",
                    "eligible_at": "2026-06-30T23:59:59+08:00",
                    "settlement_version_policy": "LATEST_OFFICIAL_AS_OF_EVALUATION",
                    "frozen_artifact_ref": str(thesis),
                    "source_contract_ref": str(source_contract),
                    "measurement_contract_ref": str(measurement),
                }],
            }],
        },
        registered_at="2026-01-01T01:00:00+08:00",
    )
    feedback_item_id = "FBI:R-SOURCE:FJ:SOURCE:S1"
    feedback = {
        "schema_version": "judgment-feedback-card.v2",
        "case_id": "R-SOURCE",
        "freeze_id": "FREEZE:R-SOURCE",
        "settlement_id": "SETTLEMENT:R-SOURCE:FJ:SOURCE",
        "settlement_as_of": "2026-08-21T10:00:00+08:00",
        "cards": [{
            "claim_id": "FJ:SOURCE",
            "forward_judgment_id": "FJ:SOURCE",
            "settlement_status": "CALCULATED",
            "judgment_outcome": {"status": "MISSED"},
            "increment_vs_baseline": "BASELINE_BETTER",
            "rival_hypothesis_feedback": None,
        }],
    }
    feedback_path = _write(tmp_path / "feedback.json", feedback)
    note = build_judgment_learning_note(
        feedback,
        note_id="LNOTE:source:method",
        claim_id="FJ:SOURCE",
        disposition="RETIRE",
        state_scope="客户响应必须先于单位经济判断。",
        measurement_scope="同口径客户采用和订单转化。",
        learning_basis="原判断未优于简单基线，且缺少客户响应证据。",
        next_research_change="冻结中心路径前先取得客户响应信号，否则保持 NO_PRIMARY。",
        feedback_ref=str(feedback_path),
        experiment_id="R-SOURCE",
        company_cluster_id="COMPANY:source",
        root_cause_classes=["DATA_COVERAGE", "REASONING"],
        failure_loci=["EVIDENCE_ACQUISITION", "MECHANISM"],
        economic_failure_loci=["MEASUREMENT", "MECHANISM"],
        recorded_at="2026-08-22T10:00:00+08:00",
    )
    note_path = _write(tmp_path / "source_note.json", note)

    base_at = "2026-08-21T10:00:00+08:00"
    for event_type, suffix in (
        ("ACQUISITION_STARTED", "acquire"),
        ("OUTCOME_PACKAGE_READY", "package"),
        ("READ_ATTESTED", "read"),
        ("OUTCOME_EXTRACTED", "extract"),
    ):
        _event(
            conn, feedback_item_id, event_type, "JFE:source:" + suffix, base_at,
            artifact_ref=thesis,
        )
    settlement = _event(
        conn,
        feedback_item_id,
        "CLAIM_SETTLED",
        "JFE:source:settlement",
        base_at,
        artifact_ref=thesis,
        payload={"settlement_verdict": "B_ONLY", "feedback_ref": str(feedback_path)},
    )
    ready = jfc.record_learning_note(
        conn,
        feedback_item_id=feedback_item_id,
        feedback_ref=feedback_path,
        learning_note_ref=note_path,
        diagnosis_payload={
            "settlement_event_id": settlement["event_id"],
            "epistemic_failure_locus": "MECHANISM",
            "delivery_root_cause": "DATA_COVERAGE",
            "economic_impact": "可能把尚未验证的采用写成竞争优势。",
            "missing_facts": "同口径客户采用和订单转化。",
            "prohibited_assumptions": "不得用收入增长替代客户响应。",
            "executable_remediation": "下一次冻结前取得客户响应证据。",
            "acceptance_criteria": "冻结字段包含客户响应门和 NO_PRIMARY 退路。",
        },
        effective_at="2026-08-22T11:00:00+08:00",
        actor_id="learning-admission-fixture",
    )

    peer_note = deepcopy(note)
    peer_note.update({
        "note_id": "LNOTE:peer:method",
        "case_id": "R-PEER",
        "freeze_id": "FREEZE:R-PEER",
        "settlement_id": "SETTLEMENT:R-PEER:FJ:PEER",
        "claim_id": "FJ:PEER",
        "experiment_id": "R-PEER",
        "company_cluster_id": "COMPANY:peer",
    })
    peer_path = _write(tmp_path / "peer_note.json", peer_note)
    review = build_method_feedback_review([note, peer_note])
    review_path = _write(tmp_path / "method_review.json", review)
    target = {
        "freeze_id": "FREEZE:R-TARGET",
        "research_contract": {"customer_response_required": True},
    }
    target_path = _write(tmp_path / "target_freeze.json", target)
    receipt = {
        "schema_version": "judgment-learning-application-receipt.v1",
        "receipt_id": "LAPP:target:method",
        "application_basis": "MULTI_COMPANY_METHOD_TRANSFER",
        "source_note_ids": [note["note_id"], peer_note["note_id"]],
        "method_review_decision": {
            "decision_id": "MDEC:customer-response",
            "disposition": "APPLIED",
            "rationale": "两家公司都暴露了客户响应缺失导致的机制误判。",
        },
        "target": {
            "experiment_id": "R-TARGET",
            "company_cluster_id": "COMPANY:target",
            "freeze_id": "FREEZE:R-TARGET",
        },
        "applications": [
            {
                "note_id": note["note_id"],
                "disposition": "APPLIED",
                "scope_rationale": "目标公司同样需要先确认客户响应。",
                "counterexample_or_boundary": "若已存在直接客户采用数据则无需该退路。",
                "frozen_field_changes": [{
                    "json_pointer": "/research_contract/customer_response_required",
                    "prior_rule": "客户响应不是冻结前硬门。",
                    "new_frozen_value": True,
                }],
            },
            {
                "note_id": peer_note["note_id"],
                "disposition": "NARROWED",
                "scope_rationale": "只迁移客户响应顺序，不迁移原公司结论。",
                "counterexample_or_boundary": "商业模式不同，不能迁移方向结论。",
            },
        ],
        "prepared_by": "target-author",
        "independent_reviewer": {
            "reviewer_id": "independent-reviewer",
            "verdict": "CONFIRMED_FIELD_CHANGE",
            "review_note": "目标冻结字段存在，且变更发生在目标结果窗口之前。",
        },
    }
    receipt_path = _write(tmp_path / "application_receipt.json", receipt)
    applied = jfc.record_learning_application(
        conn,
        feedback_item_id=feedback_item_id,
        application_receipt_ref=receipt_path,
        note_refs=[note_path, peer_path],
        method_review_ref=review_path,
        target_freeze_ref=target_path,
        target_frozen_at="2026-08-22T14:00:00+08:00",
        effective_at="2026-08-22T15:00:00+08:00",
        actor_id="learning-admission-fixture",
    )
    conn.close()
    return {
        "database": database,
        "feedback_item_id": feedback_item_id,
        "note_id": note["note_id"],
        "note_event_id": ready["event"]["event_id"],
        "application_event_id": applied["event"]["event_id"],
    }


def _mutate_application(database: Path, event_id: str, mutate) -> None:
    conn = sqlite3.connect(database)
    raw = conn.execute(
        "SELECT payload_json FROM judgment_feedback_events WHERE event_id = ?", (event_id,),
    ).fetchone()[0]
    payload = json.loads(raw)
    mutate(payload)
    conn.execute(
        "UPDATE judgment_feedback_events SET payload_json = ? WHERE event_id = ?",
        (json.dumps(payload, ensure_ascii=False), event_id),
    )
    conn.commit()
    conn.close()


def test_real_control_plane_application_refreshes_contract_and_safe_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)
    output = tmp_path / "report"
    output.mkdir()
    _write(output / "analysis_contract.json", {
        "ts_code": "000651.SZ",
        "company_id": "COMPANY:target-report",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": CUTOFF,
    })
    _write(output / "report_context.json", {
        "coverage": {"citable_observation_ids": []},
        "unresolved_gaps": [],
        "conflicts": [],
        "validation": {"state": "REVIEWABLE"},
    })
    _write(output / "official_evidence_validation.json", {"state": "REVIEWABLE"})

    selected = refresh_analysis_contract_learning_admissions(
        output, control_plane_db=fixture["database"],
    )

    assert selected["state"] == "READY"
    assert selected["selected_count"] == 1
    handoff = build_judgment_generation_handoff(output, "RESEARCH_AGENDA")
    prompts = handoff["projection"]["learning_prompts"]
    assert prompts == [{
        "note_id": fixture["note_id"],
        "applicability": {
            "state_scope": "客户响应必须先于单位经济判断。",
            "measurement_scope": "同口径客户采用和订单转化。",
        },
        "next_research_change": "冻结中心路径前先取得客户响应信号，否则保持 NO_PRIMARY。",
        "role": "CANDIDATE_METHOD_PROMPT",
    }]
    serialized = json.dumps(prompts, ensure_ascii=False).lower()
    assert all(word not in serialized for word in ("settlement", "price", "action", "outcome"))


def test_learning_application_without_post_holdout_release_is_not_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)
    conn = sqlite3.connect(fixture["database"])
    conn.execute("DELETE FROM judgment_training_method_releases")
    conn.commit()
    conn.close()

    result = select_judgment_learning_admissions(fixture["database"], information_cutoff=CUTOFF)

    assert result["state"] == "NO_ELIGIBLE_LEARNING"
    assert result["excluded_counts"] == {"method_release_missing": 1}


def test_handoff_rechecks_release_after_contract_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)
    output = tmp_path / "report"
    output.mkdir()
    _write(output / "analysis_contract.json", {
        "ts_code": "000651.SZ",
        "company_id": "COMPANY:target-report",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": CUTOFF,
    })
    _write(output / "report_context.json", {
        "coverage": {"citable_observation_ids": []},
        "unresolved_gaps": [],
        "conflicts": [],
        "validation": {"state": "REVIEWABLE"},
    })
    _write(output / "official_evidence_validation.json", {"state": "REVIEWABLE"})
    assert refresh_analysis_contract_learning_admissions(
        output, control_plane_db=fixture["database"],
    )["selected_count"] == 1
    conn = sqlite3.connect(fixture["database"])
    conn.execute("DELETE FROM judgment_training_method_releases")
    conn.commit()
    conn.close()

    handoff = build_judgment_generation_handoff(output, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert any(
        finding.endswith("method_not_released_for_report_use")
        for finding in handoff["readiness"]["invalid_findings"]
    )
    assert handoff["projection"]["learning_prompts"] == []


def test_unapplied_learning_note_is_not_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)
    conn = sqlite3.connect(fixture["database"])
    conn.execute(
        "DELETE FROM judgment_feedback_events WHERE event_id = ?",
        (fixture["application_event_id"],),
    )
    conn.commit()
    conn.close()

    result = select_judgment_learning_admissions(fixture["database"], information_cutoff=CUTOFF)

    assert result["state"] == "NO_ELIGIBLE_LEARNING"
    assert result["selected_count"] == 0


def test_application_after_report_cutoff_is_not_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)

    result = select_judgment_learning_admissions(
        fixture["database"], information_cutoff="2026-08-22T14:30:00+08:00",
    )

    assert result["selected_count"] == 0
    assert result["excluded_counts"] == {"application_after_information_cutoff": 1}


@pytest.mark.parametrize("lane", ["HISTORICAL_TEACHING", "HISTORICAL_HOLDOUT"])
def test_teaching_and_holdout_lanes_are_not_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lane: str,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)
    conn = sqlite3.connect(fixture["database"])
    conn.execute(
        "UPDATE judgment_feedback_claims SET program_lane = ? WHERE feedback_item_id = ?",
        (lane, fixture["feedback_item_id"]),
    )
    conn.commit()
    conn.close()

    result = select_judgment_learning_admissions(fixture["database"], information_cutoff=CUTOFF)

    assert result["selected_count"] == 0
    assert result["excluded_counts"] == {"prohibited_program_lane": 1}


def test_method_ineligible_record_is_not_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)
    conn = sqlite3.connect(fixture["database"])
    conn.execute(
        "UPDATE judgment_feedback_claims SET learning_eligibility = 'TEACHING_ONLY' "
        "WHERE feedback_item_id = ?",
        (fixture["feedback_item_id"],),
    )
    conn.commit()
    conn.close()

    result = select_judgment_learning_admissions(fixture["database"], information_cutoff=CUTOFF)

    assert result["selected_count"] == 0
    assert result["excluded_counts"] == {"learning_scope_not_method_eligible": 1}


@pytest.mark.parametrize(
    ("mutate", "finding"),
    [
        (
            lambda payload: payload.update({"reviewer_id": payload["target_author_id"]}),
            "application_reviewer_not_independent",
        ),
        (
            lambda payload: payload.update({"target_company_id": "COMPANY:source"}),
            "application_not_cross_company",
        ),
        (
            lambda payload: payload.update({"target_frozen_at": "2026-08-22T16:00:00+08:00"}),
            "application_target_temporal_order_invalid",
        ),
    ],
)
def test_malformed_legacy_application_is_revalidated_and_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    finding: str,
) -> None:
    fixture = _valid_control_plane(tmp_path, monkeypatch)
    _mutate_application(fixture["database"], fixture["application_event_id"], mutate)

    result = select_judgment_learning_admissions(fixture["database"], information_cutoff=CUTOFF)

    assert result["selected_count"] == 0
    assert result["excluded_counts"] == {finding: 1}
