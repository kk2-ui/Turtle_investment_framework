from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.judgment_learning import (
    JudgmentLearningError,
    build_method_feedback_review,
    build_judgment_learning_note,
    persist_learning_application_receipt,
    persist_judgment_learning_note,
    validate_learning_application_receipt,
    validate_judgment_learning_admission,
    validate_judgment_learning_note,
)


def _feedback(*, settlement_status: str = "CALCULATED", rival_signal_verdict: str | None = None) -> dict:
    rival_feedback = (
        {"state": "DERIVED_FROM_FROZEN_RIVAL_SIGNAL", "pair_id": "RHP:gree:integration",
         "signal_id": "RHPSIG:gree:integration-early", "signal_stage": "EARLY_MECHANISM",
         "signal_verdict": rival_signal_verdict, "pair_verdict": "NOT_YET_DUE"}
        if rival_signal_verdict is not None else None
    )
    return {
        "schema_version": "judgment-feedback-card.v2",
        "case_id": "HBTCASE:gree:20211031",
        "freeze_id": "FREEZE:gree:20211031",
        "settlement_id": "HBTSETTLE:gree:20220731",
        "settlement_as_of": "2026-08-20T00:00:00+00:00",
        "cards": [{
            "claim_id": "HBTCLM:gree:integration",
            "forward_judgment_id": "FJ:gree:integration",
            "settlement_status": settlement_status,
            "judgment_outcome": {"status": "MISSED"},
            "increment_vs_baseline": "BASELINE_BETTER",
            "rival_hypothesis_feedback": rival_feedback,
        }],
    }


def _note(feedback: dict, **overrides: object) -> dict:
    arguments = {
        "note_id": "LNOTE:gree:integration:20220731",
        "claim_id": "HBTCLM:gree:integration",
        "feedback_ref": "/tmp/turtle-feedback.json",
        "disposition": "RETIRE",
        "state_scope": "Acquisitions with unquantified synergy claims.",
        "measurement_scope": "Post-control operating cash flow on a comparable reporting basis.",
        "learning_basis": "The frozen claim missed while its carry-forward baseline remained adequate.",
        "next_research_change": "Require a pre-cutoff metric, comparator and 6-12 month discriminator before using synergy as a forward judgment.",
        "experiment_id": "R-02",
        "company_cluster_id": "COMPANY:gree",
        "root_cause_classes": ["REASONING", "DATA_COVERAGE"],
        "failure_loci": ["MECHANISM", "EVIDENCE_ACQUISITION"],
        "economic_failure_loci": ["DECISION", "TRANSMISSION"],
        "recorded_at": "2026-08-21T08:00:00+00:00",
    }
    arguments.update(overrides)
    return build_judgment_learning_note(feedback, **arguments)


def _admission_fixture() -> tuple[dict, dict, dict, dict]:
    feedback = _feedback()
    note = _note(feedback)
    admission = {
        "schema_version": "judgment-learning-admission.v1",
        "learning_note_ref": "/tmp/turtle-learning.json",
        "feedback_ref": "/tmp/turtle-feedback.json",
        "control_plane_db": "/tmp/turtle-control.db",
        "feedback_item_id": "FBI:gree:integration",
        "learning_note_event_id": "JFE:learning-ready",
        "learning_note_effective_at": "2026-08-21T09:00:00+00:00",
    }
    event = {
        "event_id": "JFE:learning-ready",
        "feedback_item_id": "FBI:gree:integration",
        "event_type": "LEARNING_NOTE_READY",
        "effective_at": "2026-08-21T09:00:00+00:00",
        "recorded_at": "2026-08-21T09:00:01+00:00",
        "artifact_refs": [
            "/tmp/turtle-feedback.json", "/tmp/turtle-learning.json",
        ],
        "payload": {
            "learning_note_ref": "/tmp/turtle-learning.json",
            "learning_note_id": note["note_id"],
            "feedback_ref": "/tmp/turtle-feedback.json",
            "case_id": note["case_id"],
            "claim_id": note["claim_id"],
            "settlement_id": note["settlement_id"],
            "learning_note_snapshot": deepcopy(note),
            "feedback_snapshot": deepcopy(feedback),
        },
        "control_claim": {
            "episode_id": note["case_id"],
            "claim_id": note["claim_id"],
        },
        "admission_state": "REVIEWABLE",
        "admission_findings": [],
    }
    return admission, note, feedback, event


def test_learning_note_is_linked_to_feedback_and_contains_only_a_next_cycle_action() -> None:
    note = _note(_feedback())

    assert note["feedback_context"] == {
        "forward_judgment_id": "FJ:gree:integration",
        "settlement_status": "CALCULATED",
        "judgment_outcome_status": "MISSED",
        "increment_vs_baseline": "BASELINE_BETTER",
        "rival_hypothesis_feedback": None,
    }
    assert "prediction" not in note
    assert "valuation" not in note
    assert note["disposition"] == "RETIRE"
    assert note["failure_loci"] == ["MECHANISM", "EVIDENCE_ACQUISITION"]
    assert note["economic_failure_loci"] == ["DECISION", "TRANSMISSION"]


def test_formal_learning_admission_binds_note_feedback_control_event_and_cutoff() -> None:
    admission, note, feedback, event = _admission_fixture()

    validation = validate_judgment_learning_admission(
        admission, note=note, feedback=feedback, control_event=event,
        information_cutoff="2026-08-22T00:00:00+00:00",
    )

    assert validation == {
        "schema_version": "judgment-learning-admission-validation.v1",
        "state": "REVIEWABLE",
        "findings": [],
    }


def test_formal_learning_admission_rejects_backdated_post_cutoff_event() -> None:
    admission, note, feedback, event = _admission_fixture()
    event["recorded_at"] = "2026-08-23T00:00:00+00:00"

    validation = validate_judgment_learning_admission(
        admission, note=note, feedback=feedback, control_event=event,
        information_cutoff="2026-08-22T00:00:00+00:00",
    )

    assert validation["state"] == "INVALID"
    assert "learning_note_event_recorded_after_information_cutoff" in validation["findings"]


def test_formal_learning_admission_rejects_changed_event_snapshots() -> None:
    admission, note, feedback, event = _admission_fixture()
    note["next_research_change"] = "A post-event rewrite must not be admitted."
    feedback["cards"][0]["judgment_outcome"]["status"] = "HIT"

    validation = validate_judgment_learning_admission(
        admission, note=note, feedback=feedback, control_event=event,
        information_cutoff="2026-08-22T00:00:00+00:00",
    )

    assert validation["state"] == "INVALID"
    assert "learning_note_changed_after_ready_event" in validation["findings"]
    assert "learning_feedback_changed_after_ready_event" in validation["findings"]


def test_formal_learning_admission_requires_timezone_except_date_only_cutoff() -> None:
    admission, note, feedback, event = _admission_fixture()
    note["recorded_at"] = "2026-08-21T08:00:00"

    validation = validate_judgment_learning_admission(
        admission, note=note, feedback=feedback, control_event=event,
        information_cutoff="2026-08-22",
    )

    assert validation["state"] == "INVALID"
    assert "learning_note_recorded_at_timezone_missing" in validation["findings"]


def test_formal_learning_admission_rejects_missing_event_and_extra_self_receipt() -> None:
    admission, note, feedback, _ = _admission_fixture()
    admission["self_reported_receipt"] = {"status": "accepted"}

    validation = validate_judgment_learning_admission(
        admission, note=note, feedback=feedback, control_event={},
        information_cutoff="2026-08-22T00:00:00+00:00",
    )

    assert validation["state"] == "INVALID"
    assert "learning_note_ready_event_missing" in validation["findings"]
    assert "admission_unexpected_fields:self_reported_receipt" in validation["findings"]


def test_learning_note_cannot_retire_an_unsettled_signal() -> None:
    with pytest.raises(JudgmentLearningError, match="requires_calculated"):
        _note(_feedback(settlement_status="PARTIAL"))


def test_learning_note_requires_a_concrete_failure_locus_and_root_cause_class() -> None:
    with pytest.raises(JudgmentLearningError, match="failure_loci_missing"):
        _note(_feedback(), failure_loci=[])
    with pytest.raises(JudgmentLearningError, match="root_cause_classes_missing"):
        _note(_feedback(), root_cause_classes=[])
    with pytest.raises(JudgmentLearningError, match="failure_loci_invalid"):
        _note(_feedback(), failure_loci=["OUTCOME_WAS_BAD"])
    with pytest.raises(JudgmentLearningError, match="economic_failure_loci_missing"):
        _note(_feedback(), economic_failure_loci=[])
    with pytest.raises(JudgmentLearningError, match="economic_failure_loci_invalid"):
        _note(_feedback(), economic_failure_loci=["EVIDENCE_ACQUISITION"])
    with pytest.raises(JudgmentLearningError, match="company_cluster_id_missing"):
        _note(_feedback(), company_cluster_id="")
    with pytest.raises(JudgmentLearningError, match="experiment_id_missing"):
        _note(_feedback(), experiment_id="")


def test_learning_note_requires_a_review_even_when_the_signal_is_correct() -> None:
    feedback = _feedback()
    feedback["cards"][0].update({
        "judgment_outcome": {"status": "MET"},
        "increment_vs_baseline": "JUDGMENT_BETTER",
    })

    note = _note(
        feedback,
        disposition="RETAIN",
        learning_basis="The signal beat its frozen baseline and separated the competing mechanisms on the declared measurement boundary.",
    )

    assert note["disposition"] == "RETAIN"
    assert note["feedback_context"]["increment_vs_baseline"] == "JUDGMENT_BETTER"


def test_learning_note_cannot_retain_or_retire_a_mixed_rival_signal() -> None:
    with pytest.raises(JudgmentLearningError, match="requires_diagnostic_rival_signal"):
        _note(_feedback(rival_signal_verdict="MIXED"))


def test_learning_note_cannot_bypass_a_present_pair_without_a_derived_signal() -> None:
    feedback = _feedback()
    feedback["cards"][0]["rival_hypothesis_feedback"] = {
        "state": "PAIR_PRESENT_BUT_CLAIM_NOT_LINKED",
    }

    with pytest.raises(JudgmentLearningError, match="requires_derived_rival_signal"):
        _note(feedback)


def test_learning_note_can_act_on_a_derived_diagnostic_early_signal() -> None:
    note = _note(
        _feedback(rival_signal_verdict="SUPPORTS_PRIMARY"),
        disposition="RETAIN",
        learning_basis="The early signal beat its baseline and uniquely separated the frozen mechanisms.",
    )

    assert note["feedback_context"]["rival_hypothesis_feedback"]["signal_verdict"] == "SUPPORTS_PRIMARY"


def test_learning_note_rejects_attempts_to_rewrite_frozen_prediction() -> None:
    note = _note(_feedback())
    note["prediction"] = {"operator": "AT_LEAST", "value": 1}

    validation = validate_judgment_learning_note(note, _feedback())

    assert validation["state"] == "INVALID"
    assert "frozen_or_investment_fields_forbidden:prediction" in validation["findings"]


def test_learning_note_rejects_investment_fields_even_when_feedback_is_real() -> None:
    note = _note(_feedback())
    note["investment_return"] = "positive"

    validation = validate_judgment_learning_note(note, _feedback())

    assert validation["state"] == "INVALID"
    assert "frozen_or_investment_fields_forbidden:investment_return" in validation["findings"]


def test_learning_note_is_append_only(tmp_path) -> None:
    feedback = _feedback()
    note = _note(feedback)

    first = persist_judgment_learning_note(tmp_path, note, feedback)
    second = persist_judgment_learning_note(tmp_path, deepcopy(note), feedback)

    assert first["written"] is True
    assert second["written"] is False
    assert second["error"] == "learning_note_already_exists"


def test_learning_note_consumes_the_actual_feedback_builder_output() -> None:
    from scripts.judgment_feedback import build_judgment_feedback_cards
    from tests.test_judgment_feedback import _forward_case
    from tests.test_stage36_historical_backtest_v2 import _v2_settlement

    feedback = build_judgment_feedback_cards(_forward_case(), _v2_settlement())
    note = build_judgment_learning_note(
        feedback,
        note_id="LNOTE:fixture:owner-cash:20220331",
        claim_id="HBTCLM:owner-cash",
        feedback_ref="/tmp/turtle-feedback.json",
        disposition="RETIRE",
        state_scope="Cash conversion claims with a frozen simple baseline.",
        measurement_scope="Ordinary-share owner cash under the disclosed accounting definition.",
        learning_basis="The frozen forward judgment missed while the carry-forward baseline was met.",
        next_research_change="Require a driver-level explanation for any cash forecast that claims to improve on carry-forward.",
        experiment_id="R-02",
        company_cluster_id="COMPANY:fixture",
        root_cause_classes=["REASONING"],
        failure_loci=["FINANCIAL_TRANSMISSION"],
        economic_failure_loci=["TRANSMISSION"],
        recorded_at="2026-08-21T08:00:00+00:00",
    )

    assert note["feedback_context"]["settlement_status"] == "CALCULATED"


def test_method_feedback_review_keeps_one_company_as_a_local_action_not_method_proof() -> None:
    review = build_method_feedback_review([_note(_feedback())])

    assert review["state"] == "SINGLE_COMPANY_ACTION_ONLY"
    assert review["company_cluster_ids"] == ["COMPANY:gree"]
    assert review["analysis_failure_loci"][0]["analysis_failure_locus"] == "EVIDENCE_ACQUISITION"
    assert review["economic_failure_loci"][0]["economic_failure_locus"] == "DECISION"
    assert "accuracy" in review["limitations"][0]


def test_method_feedback_review_opens_cross_company_review_without_scoring() -> None:
    first = _note(_feedback())
    second = deepcopy(first)
    second.update({
        "note_id": "LNOTE:walmart:transactions:20260821",
        "case_id": "HBTCASE:walmart:20260821",
        "claim_id": "HBTCLM:walmart:transactions",
        "experiment_id": "R-06",
        "company_cluster_id": "COMPANY:walmart",
        "next_research_change": "Keep the comparable transaction definition and test the same signal in another retail format.",
    })

    review = build_method_feedback_review([first, second])

    assert review["state"] == "MULTI_COMPANY_METHOD_REVIEW_REQUIRED"
    assert review["company_cluster_ids"] == ["COMPANY:gree", "COMPANY:walmart"]
    mechanism = next(item for item in review["analysis_failure_loci"] if item["analysis_failure_locus"] == "MECHANISM")
    assert mechanism["experiment_ids"] == ["R-02", "R-06"]
    assert "score" in review["limitations"][0]


def test_learning_application_receipt_proves_a_cross_company_pre_freeze_change(tmp_path) -> None:
    first = _note(_feedback())
    second = deepcopy(first)
    second.update({
        "note_id": "LNOTE:walmart:transactions:20260821",
        "case_id": "HBTCASE:walmart:20260821",
        "claim_id": "HBTCLM:walmart:transactions",
        "experiment_id": "R-06",
        "company_cluster_id": "COMPANY:walmart",
        "next_research_change": "Require a second customer response metric before selecting a continuation mechanism.",
    })
    notes = [first, second]
    review = build_method_feedback_review(notes)
    target_freeze = {
        "freeze_id": "FREEZE:target:20260822",
        "rival_hypothesis_pairs": [{"signals": [{"metric_reconstruction_contract": {"requires_customer_response_before_unit_economics": True}}]}],
    }
    receipt = {
        "schema_version": "judgment-learning-application-receipt.v1",
        "receipt_id": "LAPP:target:20260822",
        "source_note_ids": [first["note_id"], second["note_id"]],
        "method_review_decision": {
            "decision_id": "MDEC:customer-response:001",
            "disposition": "APPLIED",
            "rationale": "Both notes identify a missing customer-response check before financial transmission.",
        },
        "target": {"experiment_id": "R-53", "company_cluster_id": "COMPANY:target", "freeze_id": "FREEZE:target:20260822"},
        "applications": [
            {
                "note_id": first["note_id"], "disposition": "APPLIED",
                "scope_rationale": "The target also depends on customer adoption before cash conversion.",
                "counterexample_or_boundary": "If customer response remains unavailable, the target must stay NO_PRIMARY.",
                "frozen_field_changes": [{
                    "json_pointer": "/rival_hypothesis_pairs/0/signals/0/metric_reconstruction_contract/requires_customer_response_before_unit_economics",
                    "prior_rule": "Unit economics could be frozen without a customer-response observation.",
                    "new_frozen_value": True,
                }],
            },
            {
                "note_id": second["note_id"], "disposition": "NARROWED",
                "scope_rationale": "The target has no comparable transaction definition.",
                "counterexample_or_boundary": "A same-definition transaction metric would reopen this application.",
            },
        ],
        "prepared_by": "researcher-a",
        "independent_reviewer": {
            "reviewer_id": "reviewer-b", "verdict": "CONFIRMED_FIELD_CHANGE",
            "review_note": "The cited frozen field exists and is earlier than any target outcome window.",
        },
    }
    assert validate_learning_application_receipt(
        receipt, notes=notes, method_review=review, target_freeze=target_freeze,
    )["state"] == "REVIEWABLE"
    assert persist_learning_application_receipt(
        tmp_path, receipt, notes=notes, method_review=review, target_freeze=target_freeze,
    )["written"] is True

    receipt["applications"][0]["frozen_field_changes"][0]["new_frozen_value"] = False
    invalid = validate_learning_application_receipt(
        receipt, notes=notes, method_review=review, target_freeze=target_freeze,
    )
    assert invalid["state"] == "INVALID"
    assert "applications[0]:frozen_field_changes[0]:new_value_not_in_target_freeze" in invalid["findings"]
