from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.judgment_experience_memory import (
    EXPERIENCE_REGISTRY_SCHEMA,
    JudgmentExperienceError,
    append_experience_feedback,
    build_experience_feedback_event,
    build_experience_invocation_receipt,
    build_experience_retrieval_pack,
    compile_feedback_experience_record,
    compile_existing_source_experience_record,
    compile_teaching_experience_record,
    project_existing_analogy_transfer_card,
    validate_experience_feedback_event,
    validate_experience_invocation_receipt,
    validate_experience_registry,
    validate_judgment_experience_record,
    version_record_after_feedback,
)


TIME = "2026-08-29T10:00:00+08:00"


def _teaching_case(case_id: str = "TEACH:CN002080:20190501:FY2019", company_id: str = "CN:002080") -> dict:
    return {
        "case_id": case_id,
        "company_id": company_id,
        "company_cluster_id": "COMPANY:" + company_id.removeprefix("CN:"),
        "track": "TEACHING",
        "status": "CURATED",
        "source_refs": ["docs/teaching/preoutcome.md", "docs/teaching/settlement.json"],
        "artifact_refs": {"postoutcome_review_ref": "docs/teaching/independent_review.md"},
        "lesson": {
            "state_and_constraint": "A capital-intensive new line had reached construction completion before unit economics matured.",
            "management_choice_or_no_action": "Management added a second line before the first line had a mature capital return.",
            "customer_or_operating_response": "Customer certification and revenue improved while line profit remained unresolved.",
            "cash_or_capital_result": "Parent funding did not establish project cash recovery.",
            "mechanism_lesson": "Construction, customer absorption, and capital return are separate stages.",
            "strongest_rival": "Early losses can be normal ramp-up rather than permanent failure.",
            "investor_treatment": "Keep the option outside base owner cash until customer and unit-economic evidence converge.",
            "transfer_question": "Do customer absorption, line economics, and cash recovery improve together?",
        },
    }


def _structural_key(*, boundary: str = "BUSINESS_LINE", arena: str = "CAPITAL_INTENSIVE_B2B_MANUFACTURING") -> dict:
    return {
        "mechanism_kinds": ["CAPACITY_ABSORPTION_CAPITAL_RETURN"],
        "lifecycle": "EXPANSION",
        "industry_epoch": "CAPACITY_BUILDOUT",
        "competitive_arena": arena,
        "responsibility_boundary": boundary,
        "company_constraints": ["CAPITAL_INTENSIVE_EXPANSION", "CUSTOMER_CONCENTRATION"],
    }


def _record(*, record_id: str = "JER:TEACH:CAPACITY:V1", boundary: str = "BUSINESS_LINE", roles: list[str] | None = None) -> dict:
    return compile_teaching_experience_record(
        _teaching_case(), record_id=record_id, recorded_at=TIME,
        structural_key=_structural_key(boundary=boundary),
        retrieval_roles=roles or ["PRIMARY_ANALOG"],
        economic_failure_loci=["MECHANISM", "TRANSMISSION"],
        apply_when=["The target has a separately identifiable expansion line and cutoff-visible customer absorption evidence."],
        do_not_apply_when=["Group cash or construction completion is the only available carrier."],
    )


def _target(*, company_id: str = "CN:002475", boundary: str = "BUSINESS_LINE") -> dict:
    code = company_id.removeprefix("CN:")
    return {
        "case_id": "EXPERIENCE_TARGET:CN" + code + ":20240501",
        "company_id": company_id,
        "company_cluster_id": "COMPANY:CN" + code,
        "cutoff_at": "2024-05-01T00:00:00+08:00",
        "outcome_access_state": "SEALED",
        "structural_key": _structural_key(boundary=boundary),
        "primary_question": "Can incremental manufacturing capacity earn customer absorption, unit economics, and cash recovery before it enters base owner cash?",
        "strongest_rival": "A temporary ramp can look weak before customer programs mature.",
        "permitted_evidence_ceiling": "TEACHING",
        "preoutcome_control_ref": "tests/fixtures/judgment_experience_memory/target_control_" + code + ".json",
    }


def _applied_receipt(record: dict, pack: dict) -> dict:
    return build_experience_invocation_receipt(
        invocation_id="EIR:CN002475:CAPACITY:V1", retrieval_pack=pack, record=record,
        state="APPLIED_PREOUTCOME", structural_match="The target shares an expansion-stage B2B manufacturing line and a customer-concentration constraint.",
        mismatch_dimensions=["The target sells precision components rather than specialty materials."],
        accepted_transfer=["Test capacity completion, customer absorption, line economics, and cash recovery separately."],
        rejected_transfer=["Do not import the source company outcome or any project threshold."],
        changed_question_refs=["Q:TARGET:INCREMENTAL_CAPACITY"],
        changed_evidence_priority=["EVIDENCE:TARGET:CUSTOMER_PROGRAMS", "EVIDENCE:TARGET:SEGMENT_CASH"],
        changed_rival_or_discriminator_refs=["RIVAL:TARGET:RAMP_VS_DURABLE_RETURN"],
        changed_investor_treatment="Exclude the incremental line from base owner-cash treatment until the target's customer, unit-economic, and cash carriers converge.",
        frozen_at=TIME,
    )


def _target_card() -> dict:
    return {
        "card_id": "ATC:CN002475:CAPACITY:V1",
        "target_pair_id": "RHP:CN002475:CAPACITY",
        "target_state_vector": ["capacity expansion", "customer concentration", "business-line cash boundary"],
        "structural_mapping": [{
            "source_driver": "construction completion", "target_driver": "incremental capacity deployment",
            "intermediate_variable": "customer absorption and line economics", "operating_outcome": "cash recovery",
        }],
        "mismatch_dimensions": ["different product category and customer program timing"],
        "application_rule": {
            "when_to_apply": "only when the target line has its own customer and cash evidence",
            "when_not_to_apply": "when group cash is substituted for the line economics",
        },
        "invalidation_conditions": [{
            "signal_id": "RHPSIG:CN002475:CAPACITY", "condition": "line customer absorption does not progress",
            "effect": "keep incremental value outside the base treatment",
        }],
        "strongest_near_miss": {
            "status": "UNKNOWN_NO_QUALIFIED_EPISODE", "unknown_reason": "The generic target fixture has no registered near-miss episode.",
            "conservative_treatment": "Use the card as a question prompt rather than primary support.",
        },
        "linked_discriminator_ids": ["RHPSIG:CN002475:CAPACITY"],
        "support_role": "QUESTION_ONLY",
    }


def test_m0_compiler_reuses_teaching_lesson_without_creating_a_second_card_or_learning_note() -> None:
    record = _record()

    assert validate_judgment_experience_record(record)["state"] == "REVIEWABLE"
    assert record["source_kind"] == "TEACHING"
    assert "analogy_transfer_card" not in record
    assert "learning_note" not in record
    assert record["source_refs"] == _teaching_case()["source_refs"]


def test_m1_compiles_a_reviewed_blind_feedback_without_copying_outcome_values() -> None:
    record = compile_feedback_experience_record(
        {
            "status": "COMPLETED", "candidate": {"security_id": "CN:601012"},
            "independent_post_outcome_review": {"verdict": "ACCEPT"},
        },
        record_id="JER:CN601012:PRICE_CASH:V1", source_case_id="BLIND:CN601012:20240501:FY2024",
        source_refs=["docs/preoutcome.json", "docs/settlement.json", "docs/feedback.json"],
        review_refs=["docs/postoutcome_review.md"], recorded_at=TIME,
        proposition="Scale requires same-boundary price, cost, and cash-capex evidence before durable economics are credited.",
        structural_key=_structural_key(), decision_or_no_action="Continue capacity deployment under price pressure.",
        mechanism_chain="capacity -> price and cost -> cash-capex absorption",
        observable_signals=["same-boundary revenue, margin, and cash-capex coverage"],
        strongest_rival="A cycle recovery can repair economics before capacity is reduced.",
        apply_when=["capital-intensive manufacturing has capacity and price pressure"],
        do_not_apply_when=["the target has no comparable responsibility boundary"],
        investor_relevance="Do not credit scale as durable owner cash before current-company economics are observed.",
        retrieval_roles=["PRIMARY_ANALOG"], economic_failure_loci=["MECHANISM", "TRANSMISSION"],
    )

    assert validate_judgment_experience_record(record)["state"] == "REVIEWABLE"
    assert record["source_kind"] == "BLIND_FEEDBACK"
    assert "actual" not in record
    assert "outcome" not in record


@pytest.mark.parametrize("source_kind", ["LEARNING_NOTE", "CONDITIONAL_MECHANISM"])
def test_m1_generic_compiler_keeps_existing_learning_and_mechanism_objects_as_references(source_kind: str) -> None:
    source_ref = "tests/fixtures/judgment_experience_memory/" + (
        "learning_note.json" if source_kind == "LEARNING_NOTE" else "conditional_mechanism.json"
    )
    record = compile_existing_source_experience_record(
        {
            "source_kind": source_kind, "source_case_id": "CASE:SOURCE", "source_company_id": "CN:600000",
            "source_company_cluster_id": "COMPANY:CN600000", "source_refs": ["docs/source.json"],
            "review_refs": ["tests/fixtures/judgment_experience_memory/canonical_review.md"],
            "evidence_ceiling": "MECHANISM" if source_kind == "LEARNING_NOTE" else "MECHANISM_CANDIDATE",
            "feedback_event_refs": ["EFE:SOURCE"], "canonical_source_ref": source_ref,
            "canonical_review_ref": "tests/fixtures/judgment_experience_memory/canonical_review.md",
            **({"canonical_synthesis_id": "CMS:SOURCE:1"} if source_kind == "CONDITIONAL_MECHANISM" else {}),
        },
        record_id="JER:SOURCE:" + source_kind + ":V1", recorded_at=TIME,
        proposition="A conditional mechanism is reusable only under its stated conditions.",
        structural_key=_structural_key(), decision_or_no_action="Preserve the source decision as an input, not a target conclusion.",
        mechanism_chain="source state -> current-company question", observable_signals=["current-company discriminator"],
        strongest_rival="The target's responsibility boundary differs.", apply_when=["conditions match"],
        do_not_apply_when=["conditions differ"], investor_relevance="Change evidence order only.",
        retrieval_roles=["PRIMARY_ANALOG"], economic_failure_loci=["MECHANISM"],
    )

    assert validate_judgment_experience_record(record)["state"] == "REVIEWABLE"
    assert record["source_refs"] == ["docs/source.json"]


def test_structural_retrieval_returns_primary_and_boundary_without_forcing_a_match() -> None:
    primary = _record()
    boundary = _record(
        record_id="JER:TEACH:CAPACITY:BOUNDARY:V1", boundary="GROUP", roles=["BOUNDARY_RECORD"],
    )

    pack = build_experience_retrieval_pack(
        pack_id="ERP:CN002475:CAPACITY:V1", target=_target(), records=[primary, boundary], retrieved_at=TIME,
    )

    assert pack["status"] == "RETRIEVAL_READY"
    assert [item["role"] for item in pack["candidates"]] == ["PRIMARY_ANALOG", "BOUNDARY_RECORD"]
    assert pack["candidates"][1]["fit"] == "BOUNDARY_ONLY"


def test_same_industry_but_responsibility_mismatch_is_not_promoted_to_primary() -> None:
    mismatched = _record(boundary="GROUP")
    pack = build_experience_retrieval_pack(
        pack_id="ERP:CN002475:MISMATCH:V1", target=_target(), records=[mismatched], retrieved_at=TIME,
    )

    assert pack["status"] == "NO_APPLICABLE_EXPERIENCE"
    assert pack["candidates"] == []


def test_result_leakage_and_source_target_identity_are_rejected_locally() -> None:
    leaked = _target()
    leaked["outcome"] = "later annual report result"
    with pytest.raises(JudgmentExperienceError, match="target context invalid"):
        build_experience_retrieval_pack(pack_id="ERP:LEAK", target=leaked, records=[_record()], retrieved_at=TIME)

    same_company = _target(company_id="CN:002080")
    pack = build_experience_retrieval_pack(pack_id="ERP:SAME", target=same_company, records=[_record()], retrieved_at=TIME)
    assert pack["status"] == "NO_APPLICABLE_EXPERIENCE"


def test_retrieved_not_applied_has_no_transfer_credit_or_target_card() -> None:
    record = _record()
    pack = build_experience_retrieval_pack(pack_id="ERP:CN002475:V1", target=_target(), records=[record], retrieved_at=TIME)
    receipt = build_experience_invocation_receipt(
        invocation_id="EIR:CN002475:NOT_APPLIED:V1", retrieval_pack=pack, record=record,
        state="RETRIEVED_NOT_APPLIED", structural_match="The mechanism is structurally similar but not decision-changing for this target.",
        mismatch_dimensions=["Target evidence already resolves the question."], accepted_transfer=[],
        rejected_transfer=["No research treatment changes before outcome."], changed_question_refs=[],
        changed_evidence_priority=[], changed_rival_or_discriminator_refs=[], changed_investor_treatment="", frozen_at=TIME,
    )

    assert validate_experience_invocation_receipt(receipt)["state"] == "REVIEWABLE"
    assert receipt["projected_analogy_transfer_card_id"] is None
    with pytest.raises(JudgmentExperienceError, match="only applied"):
        project_existing_analogy_transfer_card(receipt, record, _target_card())


def test_applied_invocation_projects_one_existing_target_card_and_not_a_value() -> None:
    record = _record()
    pack = build_experience_retrieval_pack(pack_id="ERP:CN002475:V1", target=_target(), records=[record], retrieved_at=TIME)
    receipt, card = project_existing_analogy_transfer_card(_applied_receipt(record, pack), record, _target_card())

    assert receipt["projected_analogy_transfer_card_id"] == card["card_id"]
    assert card["source_case_id"] == record["source_case_id"]
    assert card["settlement_rule"] == "DERIVE_FROM_PAIR_SIGNALS_ONLY"

    forged = deepcopy(receipt)
    forged["cjo_value"] = "a historical memory cannot set this"
    assert "experience_cannot_write_cjo_or_investment_value" in validate_experience_invocation_receipt(forged)["findings"]
    with pytest.raises(JudgmentExperienceError, match="forbidden"):
        project_existing_analogy_transfer_card(receipt, record, {**_target_card(), "valuation": "forged"})


def test_measurement_block_stays_local_and_feedback_versions_preserve_the_original_invocation() -> None:
    record = _record()
    pack = build_experience_retrieval_pack(pack_id="ERP:CN002475:V1", target=_target(), records=[record], retrieved_at=TIME)
    receipt = _applied_receipt(record, pack)
    event = build_experience_feedback_event(
        event_id="EFE:CN002475:MEASUREMENT:V1", receipt=receipt, status="MEASUREMENT_BLOCKED",
        feedback_ref="tests/fixtures/judgment_experience_memory/outcome_settlement.json",
        review_ref="tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md",
        recorded_at="2026-08-30T10:00:00+08:00",
        explanation="The target outcome used an incompatible business-line perimeter, so the invocation cannot be diagnosed.",
        economic_failure_loci=["MEASUREMENT"],
    )
    assert validate_experience_feedback_event(event)["state"] == "REVIEWABLE"
    assert event["status"] == "MEASUREMENT_BLOCKED"

    with pytest.raises(JudgmentExperienceError, match="measurement_blocked_requires"):
        build_experience_feedback_event(
            event_id="EFE:BAD", receipt=receipt, status="MEASUREMENT_BLOCKED",
            feedback_ref="tests/fixtures/judgment_experience_memory/outcome_settlement.json",
            review_ref="tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md",
            recorded_at="2026-08-30T10:00:00+08:00", explanation="wrong", economic_failure_loci=["MECHANISM"],
        )

    updated = version_record_after_feedback(record, event, receipt=receipt, recorded_at="2026-08-30T10:00:00+08:00")
    assert updated["version"] == 2
    assert updated["status"] == "RETRIEVAL_READY"
    registry = {"schema_version": EXPERIENCE_REGISTRY_SCHEMA, "records": [record], "feedback_events": []}
    appended = append_experience_feedback(registry, record=record, event=event, receipt=receipt, updated_record=updated)
    assert registry["records"] == [record]
    assert len(appended["records"]) == 2
    assert appended["feedback_events"] == [event]
    assert validate_experience_registry(appended)["state"] == "REVIEWABLE"
