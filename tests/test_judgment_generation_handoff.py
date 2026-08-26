import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scripts import judgment_feedback_control as jfc
from scripts import judgment_training_program as jtp
from scripts.judgment_learning import (
    build_judgment_learning_note,
    build_method_feedback_review,
)
from judgment_generation_handoff import (
    build_judgment_generation_handoff,
    validate_judgment_generation_handoff,
)
from turtle_agent.tools.read_tools import (
    read_judgment_generation_handoff,
    read_report_contract_pack,
    read_structured_ledger_contract,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _contract(output: Path, purpose: str = "COMPANY_JUDGMENT_ONLY") -> None:
    _write(output / "analysis_contract.json", {
        "ts_code": "000651.SZ",
        "company_id": "CN:000651",
        "analysis_purpose": purpose,
        "data_as_of": "2026-06-30T23:59:59+08:00",
    })


def _question_plan(matches: list[dict] | None = None) -> dict:
    return {
        "report_id": "000651.SZ",
        "selected_questions": [{
            "question_id": "DQ:competition:test",
            "topic_family": "operating_transition",
            "mechanism_key": "channel_transition",
            "question": "渠道调整还是全渠道竞争位置发生了持续恶化？",
            "candidate_origins": ["official_evidence"],
            "base_rate_refs": [],
            "base_rate_sample_size": 0,
            "competing_explanations": [
                {"explanation_id": "H-A", "mechanism": "渠道重配"},
                {"explanation_id": "H-B", "mechanism": "竞争恶化"},
            ],
            "discriminating_signals": [{"signal_id": "SIG:channel", "observable": "同口径全渠道量价"}],
            "decision_link": {"action": "buy"},
            "research_tasks": [{"task_id": "DQ-T1", "research_question": "取得同口径量价"}],
            "stopping_rule": {"stop_when": "两方能分叉或资料不可得"},
            "confidence": {"state": "UNKNOWN"},
        }],
        "industry_knowledge_context": {
            "source": "industry_knowledge",
            "matched_mechanisms": list(matches or []),
            "validation_status": "AVAILABLE",
        },
        "validation": {"state": "REVIEWABLE", "invalid_findings": [], "incomplete_findings": []},
    }


def _research_inputs(output: Path, matches: list[dict] | None = None) -> None:
    _contract(output)
    _write(output / "report_context.json", {
        "meta": {"report_id": "000651.SZ"},
        "coverage": {"citable_observation_ids": ["OBS:revenue", "OBS:inventory"]},
        "unresolved_gaps": ["全渠道量价"],
        "conflicts": [],
        "validation": {"state": "REVIEWABLE"},
    })
    _write(output / "official_evidence_validation.json", {"state": "REVIEWABLE"})
    _write(output / "decisive_question_plan.json", _question_plan(matches))
    _write(output / "decisive_question_validation.json", {"state": "REVIEWABLE"})


def _ready_match(status: str = "MECHANISM_READY", assessment: str = "NOT_EVIDENCED") -> dict:
    return {
        "mechanism_id": "IKM:channel-transition",
        "mechanism_key": "channel_transition",
        "title": "渠道迁移与竞争恶化必须分开",
        "status": status,
        "match_reason": "同一行业机制",
        "company_verification_fields": ["全渠道份额", "品牌量价"],
        "alternative_explanations": ["产品周期"],
        "company_assessment": assessment,
        "question_injected": True,
        "forbidden_model_role": "not_a_claim_evidence_or_valuation_input",
    }


def _contains_forbidden_key(value) -> bool:
    forbidden = {
        "settlement", "settlement_id", "settlement_status", "settlement_as_of", "settled_at",
        "actual", "actual_value", "actual_observation", "actual_outcomes", "price", "market_price",
        "share_price", "stock_price", "action", "action_after_flip", "position", "position_after_flip",
        "investment_return",
    }
    if isinstance(value, dict):
        return any(str(key).lower() in forbidden or _contains_forbidden_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _formal_learning_admission(
    output: Path, *, event_effective_at: str = "2026-05-03T00:00:00+08:00",
    event_recorded_at: str = "2026-05-03T00:00:01+08:00",
) -> dict:
    thesis_ref = output / "learning_source_thesis.json"
    source_ref = output / "learning_outcome_contract.json"
    measurement_ref = output / "learning_measurement_contract.json"
    for path in (thesis_ref, source_ref, measurement_ref):
        _write(path, {"fixture": path.stem})
    program_ref = (output / "learning_training_program.json").resolve()
    _write(program_ref, {"fixture": "active-handoff-training-program"})
    db_path = output / "judgment_feedback_control.db"
    conn = jfc.connect(db_path)
    jtp.initialize(conn)
    program_id = "JTP:handoff:v1"
    method_version = "handoff-learning-method-v1"
    method_scope = "SELECTION_AND_BOUNDARY"
    conn.execute(
        """INSERT INTO judgment_training_programs
             (program_id, program_state, method_version, method_scope, registered_at,
              method_frozen_at, method_freeze_recorded_at, sampling_policy_json, contract_ref)
             VALUES (?, 'ACTIVE', ?, ?, ?, ?, ?, '{}', ?)""",
        (
            program_id,
            method_version,
            method_scope,
            "2026-01-01T00:00:00+08:00",
            "2026-05-10T00:00:00+08:00",
            "2026-05-10T00:00:01+08:00",
            str(program_ref),
        ),
    )
    conn.commit()
    manifest = {
        "schema_version": "judgment-feedback-control-registration.v1",
        "episode_id": "R-HANDOFF-01",
        "company_id": "COMPANY:SOURCE",
        "frozen_at": "2026-01-01T00:00:00+08:00",
        "episode_class": "JUDGMENT_SELECTION_EPISODE",
        "selection_status": "SELECTION_ADMITTED",
        "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
        "program_lane": "UNASSIGNED",
        "outcome_access": "UNSPECIFIED",
        "training_program_ref": str(program_ref),
        "claims": [{
            "claim_id": "FJ:CHANNEL",
            "stages": [{
                "stage_id": "S1",
                "source_kind": "OFFICIAL_COMPANY_DISCLOSURE",
                "source_ref": "official:2026Q1",
                "eligible_at": "2026-03-31T23:59:59+08:00",
                "settlement_version_policy": "LATEST_OFFICIAL_AS_OF_EVALUATION",
                "frozen_artifact_ref": str(thesis_ref),
                "source_contract_ref": str(source_ref),
                "measurement_contract_ref": str(measurement_ref),
            }],
        }],
    }
    jfc.register_manifest(
        conn, manifest, registered_at="2026-01-01T01:00:00+08:00",
    )
    feedback_item_id = "FBI:R-HANDOFF-01:FJ:CHANNEL:S1"
    feedback_path = (output / "formal_feedback.json").resolve()
    feedback = {
        "schema_version": "judgment-feedback-card.v2",
        "case_id": "R-HANDOFF-01",
        "freeze_id": "FREEZE:R-HANDOFF-01",
        "settlement_id": "SETTLEMENT:R-HANDOFF-01:FJ:CHANNEL",
        "settlement_as_of": "2026-05-01T00:00:00+08:00",
        "cards": [{
            "claim_id": "FJ:CHANNEL",
            "forward_judgment_id": "FJ:CHANNEL",
            "settlement_status": "CALCULATED",
            "judgment_outcome": {"status": "MISSED"},
            "increment_vs_baseline": "BASELINE_BETTER",
            "rival_hypothesis_feedback": None,
        }],
    }
    _write(feedback_path, feedback)
    note = build_judgment_learning_note(
        feedback,
        note_id="LNOTE:channel-formal",
        claim_id="FJ:CHANNEL",
        disposition="RETIRE",
        state_scope="渠道变化与竞争位置需要分离的公司。",
        measurement_scope="全渠道同口径量价与份额。",
        learning_basis="冻结判断未优于简单基线，且缺少全渠道同口径证据。",
        next_research_change="先取得全渠道同口径数据，再选择渠道重配或竞争恶化机制。",
        feedback_ref=str(feedback_path),
        experiment_id="R-HANDOFF",
        company_cluster_id="COMPANY:SOURCE",
        root_cause_classes=["DATA_COVERAGE", "REASONING"],
        failure_loci=["EVIDENCE_ACQUISITION", "MECHANISM"],
        economic_failure_loci=["MEASUREMENT", "MECHANISM"],
        recorded_at="2026-05-02T00:00:00+08:00",
    )
    note_path = (output / "formal_learning_note.json").resolve()
    _write(note_path, note)

    def append(event_type: str, event_id: str, payload: dict | None = None) -> dict:
        event_payload = dict(payload or {})
        if event_type in jfc.OUTCOME_PIPELINE_EVENTS | jfc.OUTCOME_EVENTS:
            event_payload.setdefault("settlement_version", 1)
        return jfc._append_event(conn, {
            "event_id": event_id,
            "feedback_item_id": feedback_item_id,
            "event_type": event_type,
            "effective_at": "2026-05-01T00:00:00+08:00",
            "actor_role": "AUTOMATION",
            "actor_id": "handoff-fixture",
            "idempotency_key": event_id,
            "artifact_refs": [str(thesis_ref)],
            "payload": event_payload,
        }, allow_adapter_events=True)

    append("ACQUISITION_STARTED", "JFE:handoff:a")
    append("OUTCOME_PACKAGE_READY", "JFE:handoff:p")
    append("READ_ATTESTED", "JFE:handoff:r")
    append("OUTCOME_EXTRACTED", "JFE:handoff:x")
    settlement = append(
        "CLAIM_SETTLED", "JFE:handoff:settle",
        {"settlement_verdict": "B_ONLY", "feedback_ref": str(feedback_path)},
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
            "economic_impact": "渠道重配会被误写成竞争优势。",
            "missing_facts": "全渠道同口径量价与份额。",
            "prohibited_assumptions": "不得用单一渠道外推全渠道。",
            "executable_remediation": "下一次冻结前取得全渠道同口径证据。",
            "acceptance_criteria": "研究计划包含全渠道口径与竞争机制分叉。",
        },
        effective_at=event_effective_at,
        actor_id="handoff-fixture",
    )
    event_id = ready["event"]["event_id"]
    conn.execute(
        "UPDATE judgment_feedback_events SET recorded_at = ? WHERE feedback_item_id = ?",
        (event_recorded_at, feedback_item_id),
    )
    conn.commit()

    peer_note = deepcopy(note)
    peer_note.update({
        "note_id": "LNOTE:channel-peer",
        "case_id": "R-HANDOFF-PEER",
        "freeze_id": "FREEZE:R-HANDOFF-PEER",
        "settlement_id": "SETTLEMENT:R-HANDOFF-PEER:FJ:CHANNEL",
        "experiment_id": "R-HANDOFF-PEER",
        "company_cluster_id": "COMPANY:PEER",
    })
    peer_note_path = (output / "peer_learning_note.json").resolve()
    _write(peer_note_path, peer_note)
    method_review_path = (output / "learning_method_review.json").resolve()
    _write(method_review_path, build_method_feedback_review([note, peer_note]))
    target_freeze_path = (output / "learning_target_freeze.json").resolve()
    _write(target_freeze_path, {
        "freeze_id": "FREEZE:R-HANDOFF-TARGET",
        "research_contract": {"full_channel_evidence_required": True},
    })
    application_receipt_path = (output / "learning_application_receipt.json").resolve()
    application_receipt = {
        "schema_version": "judgment-learning-application-receipt.v1",
        "receipt_id": "LAPP:handoff:channel-method",
        "application_basis": "MULTI_COMPANY_METHOD_TRANSFER",
        "source_note_ids": [note["note_id"], peer_note["note_id"]],
        "method_review_decision": {
            "decision_id": "MDEC:handoff:channel-method",
            "disposition": "APPLIED",
            "rationale": "两家公司都暴露了单一渠道证据无法识别竞争位置的问题。",
        },
        "target": {
            "experiment_id": "R-HANDOFF-TARGET",
            "company_cluster_id": "CN:000651",
            "freeze_id": "FREEZE:R-HANDOFF-TARGET",
        },
        "applications": [
            {
                "note_id": note["note_id"],
                "disposition": "APPLIED",
                "scope_rationale": "目标公司同样需要在机制选择前取得全渠道同口径证据。",
                "counterexample_or_boundary": "若已有可核验的全渠道量价，则无需保持该退路。",
                "frozen_field_changes": [{
                    "json_pointer": "/research_contract/full_channel_evidence_required",
                    "prior_rule": "全渠道证据不是机制选择前的硬门。",
                    "new_frozen_value": True,
                }],
            },
            {
                "note_id": peer_note["note_id"],
                "disposition": "NARROWED",
                "scope_rationale": "只迁移证据顺序，不迁移来源公司的方向结论。",
                "counterexample_or_boundary": "商业模式不同，不能迁移公司判断。",
            },
        ],
        "prepared_by": "handoff-target-author",
        "independent_reviewer": {
            "reviewer_id": "handoff-independent-reviewer",
            "verdict": "CONFIRMED_FIELD_CHANGE",
            "review_note": "目标冻结字段存在，且变更发生在目标结果窗口之前。",
        },
    }
    _write(application_receipt_path, application_receipt)

    latest_lineage_time = max(
        datetime.fromisoformat(event_effective_at),
        datetime.fromisoformat(event_recorded_at),
    )
    target_frozen_at = (latest_lineage_time + timedelta(hours=1)).isoformat()
    application_at = (latest_lineage_time + timedelta(hours=2)).isoformat()
    applied = jfc.record_learning_application(
        conn,
        feedback_item_id=feedback_item_id,
        application_receipt_ref=application_receipt_path,
        note_refs=[note_path, peer_note_path],
        method_review_ref=method_review_path,
        target_freeze_ref=target_freeze_path,
        target_frozen_at=target_frozen_at,
        effective_at=application_at,
        actor_id="handoff-fixture",
    )
    application_event_id = applied["event"]["event_id"]
    conn.execute(
        "UPDATE judgment_feedback_events SET recorded_at = ? WHERE event_id = ?",
        (application_at, application_event_id),
    )

    release_id = "JMREL:handoff:v1"
    released_at = (latest_lineage_time + timedelta(hours=4)).isoformat()
    method_frozen_at = (latest_lineage_time + timedelta(hours=3)).isoformat()
    release_receipt = {
        "schema_version": "judgment-method-report-release.v1",
        "release_id": release_id,
        "program_id": program_id,
        "method_version": method_version,
        "method_scope": method_scope,
        "method_frozen_at": method_frozen_at,
        "released_at": released_at,
        "released_by": "handoff-release-owner",
        "release_decision": "METHOD_RELEASED_FOR_REPORT_USE",
        "accepted_holdout_receipt_ids": ["HRECEIPT:handoff:supported"],
    }
    release_receipt_path = (output / "learning_method_release.json").resolve()
    _write(release_receipt_path, release_receipt)
    conn.execute(
        """UPDATE judgment_training_programs
              SET method_frozen_at = ?, method_freeze_recorded_at = ?
            WHERE program_id = ?""",
        (method_frozen_at, method_frozen_at, program_id),
    )
    conn.execute(
        """INSERT INTO judgment_training_method_releases
             (program_id, release_id, method_version, method_scope, method_frozen_at,
              released_at, recorded_at, released_by, release_decision, receipt_ref, receipt_json)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'METHOD_RELEASED_FOR_REPORT_USE', ?, ?)""",
        (
            program_id,
            release_id,
            method_version,
            method_scope,
            method_frozen_at,
            released_at,
            released_at,
            "handoff-release-owner",
            str(release_receipt_path),
            json.dumps(release_receipt, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()
    conn.close()
    return {
        "schema_version": "judgment-learning-admission.v1",
        "learning_note_ref": str(note_path),
        "feedback_ref": str(feedback_path),
        "control_plane_db": str(db_path.resolve()),
        "feedback_item_id": feedback_item_id,
        "learning_note_event_id": event_id,
        "learning_note_effective_at": event_effective_at,
        "application_event_id": application_event_id,
        "program_id": program_id,
        "method_version": method_version,
        "method_scope": method_scope,
        "method_release_id": release_id,
        "method_released_at": released_at,
    }


def _append_superseding_settlement(output: Path, admission: dict, *, at: str) -> None:
    conn = jfc.connect(admission["control_plane_db"])
    artifact = str((output / "learning_source_thesis.json").resolve())
    feedback_item_id = admission["feedback_item_id"]
    prior = [
        event for event in jfc._events(conn, feedback_item_id)
        if event["event_type"] in jfc.OUTCOME_EVENTS
    ][-1]

    def append(event_type: str, suffix: str, payload: dict | None = None) -> dict:
        return jfc._append_event(
            conn,
            {
                "event_id": "JFE:handoff:v2:" + suffix,
                "feedback_item_id": feedback_item_id,
                "event_type": event_type,
                "effective_at": at,
                "actor_role": "AUTOMATION",
                "actor_id": "handoff-v2-fixture",
                "idempotency_key": "handoff-v2:" + suffix,
                "artifact_refs": [artifact],
                "payload": {"settlement_version": 2, **(payload or {})},
            },
            recorded_at=at,
            allow_adapter_events=True,
        )

    append("ACQUISITION_STARTED", "a")
    append("OUTCOME_PACKAGE_READY", "p")
    append("READ_ATTESTED", "r")
    append("OUTCOME_EXTRACTED", "x")
    append(
        "CLAIM_SETTLED",
        "settle",
        {
            "settlement_verdict": "A_ONLY",
            "supersedes_event_id": prior["event_id"],
            "feedback_ref": str((output / "formal_feedback.json").resolve()),
        },
    )
    conn.close()


def test_research_agenda_has_explicit_legal_empty_states(tmp_path):
    _research_inputs(tmp_path)

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "READY"
    assert handoff["readiness"]["empty_states"] == {
        "decisive_questions": "AVAILABLE",
        "industry_priors": "NO_MATCHING_MECHANISM_READY",
        "learning_prompts": "NO_EXPLICIT_LEARNING_REFS",
    }
    assert handoff["projection"]["official_evidence"]["citable_observation_ids"] == [
        "OBS:revenue", "OBS:inventory",
    ]
    assert handoff["projection"]["decisive_questions"][0]["question_id"] == "DQ:competition:test"
    assert "decision_link" not in handoff["projection"]["decisive_questions"][0]
    assert validate_judgment_generation_handoff(handoff, output_dir=tmp_path)["state"] == "READY"


def test_cjo_research_agenda_without_decisive_plan_is_ready_with_no_prior(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv(
        "TURTLE_INDUSTRY_KNOWLEDGE_DIR", str(tmp_path / "empty-industry-library"),
    )
    _contract(tmp_path)
    _write(tmp_path / "report_context.json", {
        "meta": {"report_id": "000651.SZ"},
        "coverage": {"citable_observation_ids": ["OBS:revenue"]},
        "unresolved_gaps": [],
        "conflicts": [],
        "validation": {"state": "REVIEWABLE"},
    })
    _write(tmp_path / "official_evidence_validation.json", {"state": "REVIEWABLE"})

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "READY_WITH_NO_PRIOR"
    assert handoff["projection"]["agenda_mode"] == "EVIDENCE_ONLY"
    assert handoff["projection"]["decisive_questions"] == []
    assert handoff["projection"]["industry_priors"] == []
    assert handoff["readiness"]["empty_states"]["decisive_questions"] == (
        "NO_DECISIVE_PLAN_EVIDENCE_ONLY"
    )
    assert validate_judgment_generation_handoff(
        handoff, output_dir=tmp_path,
    )["state"] == "READY_WITH_NO_PRIOR"


def test_cjo_contract_pack_uses_research_agenda_as_the_report_level_entry(tmp_path):
    _research_inputs(tmp_path, [_ready_match()])

    pack = read_report_contract_pack(output_dir=str(tmp_path), chapter_indexes=[0, 10])

    assert pack["ok"] is True
    assert pack["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    agenda = pack["judgment_generation_handoff"]["research_agenda"]
    assert agenda["readiness"]["state"] == "READY"
    assert agenda["projection"]["decisive_questions"][0]["question_id"] == (
        "DQ:competition:test"
    )
    assert agenda["projection"]["industry_priors"][0]["mechanism_id"] == (
        "IKM:channel-transition"
    )
    assert "不表示中心路径、选择判断或公司冻结已经完成" in (
        pack["judgment_generation_handoff"]["instruction"]
    )


def test_industry_prior_requires_ready_and_not_evidenced(tmp_path):
    ready = _ready_match()
    corroborated = {**_ready_match(status="CORROBORATED"), "mechanism_id": "IKM:corroborated"}
    supported = {**_ready_match(assessment="SUPPORTED"), "mechanism_id": "IKM:supported"}
    _research_inputs(tmp_path, [ready, corroborated, supported])

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert [item["mechanism_id"] for item in handoff["projection"]["industry_priors"]] == [
        "IKM:channel-transition",
    ]
    assert handoff["projection"]["industry_priors"][0]["company_assessment"] == "NOT_EVIDENCED"
    assert handoff["readiness"]["empty_states"]["industry_priors"] == "AVAILABLE"
    assert "industry_matches_excluded_by_ready_not_evidenced_gate:2" in handoff["readiness"]["warnings"]


def test_learning_projection_requires_formal_admission_and_hides_feedback(tmp_path):
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(tmp_path)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["projection"]["learning_prompts"] == [{
        "note_id": "LNOTE:channel-formal",
        "applicability": {
            "state_scope": "渠道变化与竞争位置需要分离的公司。",
            "measurement_scope": "全渠道同口径量价与份额。",
        },
        "next_research_change": "先取得全渠道同口径数据，再选择渠道重配或竞争恶化机制。",
        "role": "CANDIDATE_METHOD_PROMPT",
    }]
    assert not _contains_forbidden_key(handoff["projection"])


def test_read_tool_projects_only_a_formally_admitted_learning_note(tmp_path):
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(tmp_path)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = read_judgment_generation_handoff(str(tmp_path), "RESEARCH_AGENDA")

    assert handoff["projection"]["learning_prompts"] == [{
        "note_id": "LNOTE:channel-formal",
        "applicability": {
            "state_scope": "渠道变化与竞争位置需要分离的公司。",
            "measurement_scope": "全渠道同口径量价与份额。",
        },
        "next_research_change": "先取得全渠道同口径数据，再选择渠道重配或竞争恶化机制。",
        "role": "CANDIDATE_METHOD_PROMPT",
    }]
    assert not _contains_forbidden_key(handoff["projection"])


@pytest.mark.parametrize(
    ("superseding_at", "expected_state"),
    [
        ("2026-06-01T00:00:00+08:00", "BLOCKED"),
        ("2026-07-01T00:00:00+08:00", "READY"),
    ],
)
def test_learning_admission_replays_latest_settlement_at_information_cutoff(
    tmp_path: Path, superseding_at: str, expected_state: str,
) -> None:
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(tmp_path)
    _append_superseding_settlement(tmp_path, admission, at=superseding_at)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == expected_state
    if expected_state == "BLOCKED":
        assert any(
            item.endswith("learning_note_stale_for_latest_settlement_at_information_cutoff")
            for item in handoff["readiness"]["invalid_findings"]
        )
        assert handoff["projection"]["learning_prompts"] == []
    else:
        assert handoff["projection"]["learning_prompts"]


def test_learning_admission_blocks_note_rewritten_after_ready_event(tmp_path: Path) -> None:
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(tmp_path)
    note_path = Path(admission["learning_note_ref"])
    note = json.loads(note_path.read_text(encoding="utf-8"))
    note["next_research_change"] = "This rewrite happened after the ready event."
    _write(note_path, note)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert any(
        item.endswith("learning_note_changed_after_ready_event")
        for item in handoff["readiness"]["invalid_findings"]
    )
    assert handoff["projection"]["learning_prompts"] == []


def test_read_tool_blocks_a_bare_learning_note_path(tmp_path):
    _research_inputs(tmp_path)
    note = tmp_path / "unadmitted-learning.json"
    _write(note, {
        "schema_version": "judgment-learning-note.v2",
        "note_id": "LNOTE:unadmitted",
        "recorded_at": "2026-05-01T00:00:00+08:00",
        "applicability": {"state_scope": "渠道", "measurement_scope": "全渠道"},
        "next_research_change": "先取得同口径全渠道数据。",
    })
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [str(note)]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = read_judgment_generation_handoff(str(tmp_path), "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert handoff["projection"]["learning_prompts"] == []
    assert "judgment_learning_admissions[0]:formal_admission_required" in (
        handoff["readiness"]["invalid_findings"]
    )


def test_read_tool_blocks_malformed_learning_admission_contract(tmp_path):
    _research_inputs(tmp_path)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = "not-a-list"
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = read_judgment_generation_handoff(str(tmp_path), "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert "analysis_contract.judgment_learning_admissions_invalid" in (
        handoff["readiness"]["invalid_findings"]
    )


def test_read_tool_blocks_structured_admission_without_control_event(tmp_path):
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(tmp_path)
    admission["learning_note_event_id"] = "JFE:missing"
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = read_judgment_generation_handoff(str(tmp_path), "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert handoff["projection"]["learning_prompts"] == []
    assert any(
        item.endswith("learning_note_ready_event_missing")
        for item in handoff["readiness"]["invalid_findings"]
    )


def test_read_tool_blocks_learning_event_effective_after_information_cutoff(tmp_path):
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(
        tmp_path,
        event_effective_at="2026-07-01T00:00:00+08:00",
        event_recorded_at="2026-05-03T00:00:01+08:00",
    )
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = read_judgment_generation_handoff(str(tmp_path), "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert any(
        item.endswith("learning_note_event_effective_after_information_cutoff")
        for item in handoff["readiness"]["invalid_findings"]
    )


def test_read_tool_blocks_backdated_event_recorded_after_information_cutoff(tmp_path):
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(
        tmp_path,
        event_effective_at="2026-05-03T00:00:00+08:00",
        event_recorded_at="2026-07-01T00:00:00+08:00",
    )
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = read_judgment_generation_handoff(str(tmp_path), "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert any(
        item.endswith("learning_note_event_recorded_after_information_cutoff")
        for item in handoff["readiness"]["invalid_findings"]
    )


def test_handoff_rejects_timezone_less_datetime_cutoff(tmp_path: Path) -> None:
    _research_inputs(tmp_path)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["data_as_of"] = "2026-06-30T23:59:59"
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = read_judgment_generation_handoff(str(tmp_path), "RESEARCH_AGENDA")
    validation = validate_judgment_generation_handoff(handoff, output_dir=tmp_path)

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert "information_cutoff_invalid" in handoff["readiness"]["invalid_findings"]
    assert validation["state"] == "INVALID"
    assert "information_cutoff_invalid" in validation["invalid_findings"]


def test_future_learning_note_is_blocked_by_information_cutoff(tmp_path):
    _research_inputs(tmp_path)
    admission = _formal_learning_admission(
        tmp_path,
        event_effective_at="2026-07-01T00:00:00+08:00",
        event_recorded_at="2026-07-01T00:00:01+08:00",
    )
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["judgment_learning_admissions"] = [admission]
    _write(tmp_path / "analysis_contract.json", contract)

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert any(
        item.endswith("learning_note_event_not_available_at_information_cutoff")
        for item in handoff["readiness"]["invalid_findings"]
    )
    assert handoff["projection"]["learning_prompts"] == []


def test_research_agenda_blocks_invalid_official_evidence_validation(tmp_path):
    _research_inputs(tmp_path)
    _write(tmp_path / "official_evidence_validation.json", {"state": "INVALID"})

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert "official_evidence_invalid" in handoff["readiness"]["invalid_findings"]


def _ledger(output: Path, name: str, validation_name: str, payload: dict, state: str = "REVIEWABLE") -> None:
    _write(output / name, payload)
    _write(output / validation_name, {
        "state": state,
        "invalid_findings": [],
        "incomplete_findings": [],
    })


def test_judgment_synthesis_projects_kernel_without_outcomes_prices_or_actions(tmp_path):
    _contract(tmp_path)
    _ledger(tmp_path, "claim_evidence.json", "claim_evidence_validation.json", {
        "report_id": "000651.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "claims": [{
            "claim_id": "C1", "claim": "渠道解释仍待全渠道数据验证。",
            "reasoning_steps": ["线上数据不足以外推全渠道"],
            "alternative_explanations": ["渠道重配"], "applicability_conditions": ["口径连续"],
            "confidence": {"kind": "analyst_subjective", "value": 0.5, "basis": "limited"},
            "judgment_impact": {"mechanism": "channel", "forward_judgment_ids": ["FJ:1"]},
            "raw_facts": [{"evidence_id": "E1", "observation_id": "OBS:1", "actual_value": 8}],
            "action": "buy",
        }],
    })
    _ledger(tmp_path, "financial_driver_bridge.json", "financial_driver_bridge_validation.json", {
        "report_id": "000651.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "drivers": [{"driver_id": "FDB:1", "layer": "COMPETITION_DEMAND", "statement": "待验证", "market_price": 10}],
        "allocation_events": [],
    })
    _ledger(tmp_path, "thesis_test.json", "thesis_test_validation.json", {
        "report_id": "000651.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "lifecycle": "reviewable",
        "central_path": {"path_id": "CP:1", "statement": "渠道重配更可能", "action_after_flip": "exit"},
        "forward_judgments": [{"judgment_id": "FJ:1", "settlement_contract": {"allowed_source_types": ["OFFICIAL"]}, "actual_observation": {"value": 1}}],
        "mechanism_chains": [], "rival_hypothesis_pairs": [], "analogy_transfer_cards": [],
    })
    _ledger(tmp_path, "insight_ledger.json", "insight_validation.json", {
        "report_id": "000651.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "insights": [{"insight_id": "I1", "title": "关键缺口", "action": "buy"}],
        "adversarial_review": {"strongest_alternative": "竞争恶化", "settlement_status": "CALCULATED"},
    })

    handoff = build_judgment_generation_handoff(tmp_path, "JUDGMENT_SYNTHESIS")

    assert handoff["readiness"]["state"] == "READY"
    assert handoff["projection"]["claims"][0]["evidence_ids"] == ["E1"]
    assert handoff["projection"]["thesis"]["forward_judgments"][0]["settlement_contract"]
    assert not _contains_forbidden_key(handoff["projection"])
    assert validate_judgment_generation_handoff(handoff, output_dir=tmp_path)["state"] == "READY"


def test_investment_enrichment_inherits_same_cutoff_cjo_without_price_or_action(tmp_path):
    _contract(tmp_path, purpose="INVESTMENT_DECISION")
    _write(tmp_path / "company_judgment_predecessor.json", {
        "schema_version": "company-judgment-predecessor.v2",
        "identity": {"status": "G1J_COMPLETE", "missing_components": []},
        "source": {
            "report_id": "000651.SZ", "data_as_of": "2026-06-30",
            "snapshot_path": "cjo/publication_snapshot.json", "thesis_path": "cjo/thesis_test.json",
            "thesis_validation_state": "DECISION_READY",
            "financial_driver_bridge_path": "cjo/financial_driver_bridge.json",
            "financial_driver_bridge_validation_state": "DECISION_READY",
        },
        "central_path": {"path_id": "CP:1", "statement": "经营判断", "market_price": 10},
        "forward_judgments": [{"judgment_id": "FJ:1", "statement": "经营结果"}],
        "mechanism_chains": [{"chain_id": "MC:1", "mechanism": "竞争到现金"}],
        "rival_hypothesis_pairs": [{"pair_id": "RHP:1", "primary": "渠道重配", "rival": "竞争恶化"}],
        "analogy_transfer_cards": [{"card_id": "ATC:1", "boundary": "仅同渠道结构"}],
        "selection_admission": {"status": "SELECTION_ADMITTED", "basis": "方向性机制已独立接纳"},
        "financial_driver_bridge": {
            "report_id": "000651.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
            "drivers": [{"driver_id": "FDB:1", "statement": "竞争传导到现金"}],
            "allocation_events": [],
        },
    })
    _write(tmp_path / "valuation_route.json", {
        "report_id": "000651.SZ", "route_id": "VR:mature", "archetype_id": "mature_cash_return",
        "models": [{"route_model_id": "VRM:ddm", "model_type": "DDM", "role": "primary"}],
        "rejected_models": [], "required_research": ["现金可达性"],
        "validation": {"state": "REVIEWABLE"},
        "action": "buy", "market_price": 10,
    })

    handoff = build_judgment_generation_handoff(tmp_path, "INVESTMENT_ENRICHMENT")

    assert handoff["readiness"]["state"] == "READY"
    assert handoff["projection"]["company_judgment_predecessor"]["central_path"]["path_id"] == "CP:1"
    assert handoff["projection"]["company_judgment_predecessor"]["rival_hypothesis_pairs"][0]["pair_id"] == "RHP:1"
    assert handoff["projection"]["company_judgment_predecessor"]["analogy_transfer_cards"][0]["card_id"] == "ATC:1"
    assert handoff["projection"]["company_judgment_predecessor"]["selection_admission"]["status"] == "SELECTION_ADMITTED"
    assert handoff["projection"]["company_judgment_predecessor"]["financial_driver_bridge"]["drivers"][0]["driver_id"] == "FDB:1"
    assert handoff["projection"]["valuation_route"]["route_id"] == "VR:mature"
    assert not _contains_forbidden_key(handoff["projection"])

    pack = read_report_contract_pack(output_dir=str(tmp_path), chapter_indexes=[0])
    enrichment = pack["judgment_generation_handoff"]["investment_enrichment"]
    assert enrichment["readiness"]["state"] == "READY"
    predecessor = pack["company_judgment_predecessor"]
    assert predecessor["identity"]["status"] == "G1J_COMPLETE"
    assert predecessor["rival_hypothesis_pairs"][0]["pair_id"] == "RHP:1"
    assert predecessor["analogy_transfer_cards"][0]["card_id"] == "ATC:1"
    assert predecessor["selection_admission"]["status"] == "SELECTION_ADMITTED"
    assert predecessor["financial_driver_bridge"]["drivers"][0]["driver_id"] == "FDB:1"

    ledger_contract = read_structured_ledger_contract(str(tmp_path), "thesis")
    ledger_predecessor = ledger_contract["company_judgment_predecessor"]
    assert ledger_predecessor["identity"]["status"] == "G1J_COMPLETE"
    assert ledger_predecessor["rival_hypothesis_pairs"][0]["pair_id"] == "RHP:1"
    assert ledger_predecessor["financial_driver_bridge"]["drivers"][0]["driver_id"] == (
        "FDB:1"
    )

    predecessor_payload = json.loads(
        (tmp_path / "company_judgment_predecessor.json").read_text(encoding="utf-8")
    )
    predecessor_payload["selection_admission"] = {
        "status": "NO_PRIMARY", "basis": "尚无方向性优势",
    }
    _write(tmp_path / "company_judgment_predecessor.json", predecessor_payload)
    no_primary = build_judgment_generation_handoff(tmp_path, "INVESTMENT_ENRICHMENT")
    assert no_primary["readiness"]["state"] == "INCOMPLETE"
    assert "investment_enrichment_requires_selection_admitted_company_judgment" in (
        no_primary["readiness"]["incomplete_findings"]
    )


def test_investment_enrichment_rejects_legacy_partial_predecessor(tmp_path):
    _contract(tmp_path, purpose="INVESTMENT_DECISION")
    _write(tmp_path / "company_judgment_predecessor.json", {
        "schema_version": "company-judgment-predecessor.v2",
        "identity": {"status": "LEGACY_PARTIAL", "missing_components": ["rival_hypothesis_pairs"]},
        "source": {"report_id": "000651.SZ", "data_as_of": "2026-06-30"},
        "central_path": {"path_id": "CP:legacy"},
        "forward_judgments": [{"judgment_id": "FJ:legacy"}],
        "mechanism_chains": [{"chain_id": "MC:legacy"}],
    })
    _write(tmp_path / "valuation_route.json", {
        "report_id": "000651.SZ", "route_id": "VR:mature",
        "validation": {"state": "REVIEWABLE"},
    })

    handoff = build_judgment_generation_handoff(tmp_path, "INVESTMENT_ENRICHMENT")

    assert handoff["readiness"]["state"] == "BLOCKED"
    assert "company_judgment_predecessor_not_g1j_complete" in handoff["readiness"]["invalid_findings"]


def test_validator_rejects_manually_injected_pre_cutoff_outcome_or_action(tmp_path):
    _research_inputs(tmp_path)
    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")
    handoff["projection"]["actual_outcomes"] = {"value": 1}
    handoff["projection"]["action"] = "buy"

    validation = validate_judgment_generation_handoff(handoff)

    assert validation["state"] == "INVALID"
    assert any("actual_outcomes" in item for item in validation["invalid_findings"])
    assert any(".action" in item for item in validation["invalid_findings"])
