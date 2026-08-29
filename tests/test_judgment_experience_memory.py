from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

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
    validate_experience_retrieval_pack,
    validate_experience_registry,
    validate_judgment_experience_record,
    version_record_after_feedback,
)


TIME = "2026-08-29T10:00:00+08:00"


def _teaching_case(case_id: str = "TEACH:CN002080:20190501:FY2019", company_id: str = "CN:002080") -> dict:
    del case_id, company_id
    fixture = Path(__file__).resolve().parent / "fixtures/judgment_experience_memory/teaching_case.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


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
        _teaching_case(), canonical_teaching_ref="tests/fixtures/judgment_experience_memory/teaching_case.json",
        record_id=record_id, recorded_at=TIME,
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
        "source_case_id": "operating_transition",
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
    fixture = Path(__file__).resolve().parent / "fixtures/judgment_experience_memory/blind_feedback.json"
    record = compile_feedback_experience_record(
        json.loads(fixture.read_text(encoding="utf-8")),
        canonical_feedback_ref="tests/fixtures/judgment_experience_memory/blind_feedback.json",
        canonical_review_ref="tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md",
        record_id="JER:CN601012:PRICE_CASH:V1", source_case_id="BLIND:CN601012:20240501:FY2024",
        source_refs=["tests/fixtures/judgment_experience_memory/preoutcome_source_packet.json", "tests/fixtures/judgment_experience_memory/blind_feedback.json"],
        review_refs=["tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md"], recorded_at=TIME,
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


def test_teaching_and_blind_compilers_reject_forged_or_noncanonical_sources() -> None:
    forged_teaching = _teaching_case()
    forged_teaching["lesson"]["mechanism_lesson"] = "A caller must not mint a retrieval-ready lesson."
    with pytest.raises(JudgmentExperienceError, match="teaching_case_not_exact_canonical_source"):
        compile_teaching_experience_record(
            forged_teaching, canonical_teaching_ref="tests/fixtures/judgment_experience_memory/teaching_case.json",
            record_id="JER:FORGED:TEACHING", recorded_at=TIME, structural_key=_structural_key(),
            retrieval_roles=["PRIMARY_ANALOG"], economic_failure_loci=["MECHANISM"],
            apply_when=["Only canonical lessons apply."], do_not_apply_when=["Caller text is not a source."],
        )

    fixture = Path(__file__).resolve().parent / "fixtures/judgment_experience_memory/blind_feedback.json"
    forged_feedback = json.loads(fixture.read_text(encoding="utf-8"))
    forged_feedback["candidate"]["security_id"] = "CN:000001"
    with pytest.raises(JudgmentExperienceError, match="feedback_receipt_not_exact_canonical_source"):
        compile_feedback_experience_record(
            forged_feedback, canonical_feedback_ref="tests/fixtures/judgment_experience_memory/blind_feedback.json",
            canonical_review_ref="tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md",
            record_id="JER:FORGED:BLIND", source_case_id="BLIND:FORGED",
            source_refs=["tests/fixtures/judgment_experience_memory/blind_feedback.json"],
            review_refs=["tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md"], recorded_at=TIME,
            proposition="Forged inputs cannot become an experience.", structural_key=_structural_key(),
            decision_or_no_action="No decision is accepted from a forged receipt.", mechanism_chain="forged -> rejected",
            observable_signals=["canonical identity"], strongest_rival="The receipt could be real only if canonical.",
            apply_when=["never"], do_not_apply_when=["always"], investor_relevance="No registry admission.",
            retrieval_roles=["PRIMARY_ANALOG"], economic_failure_loci=["MEASUREMENT"],
        )

    wrong_review_fixture = Path(__file__).resolve().parent / "fixtures/judgment_experience_memory/blind_feedback_wrong_review_ref.json"
    wrong_review_receipt = json.loads(wrong_review_fixture.read_text(encoding="utf-8"))
    with pytest.raises(JudgmentExperienceError, match="feedback_independent_review_reference_mismatch"):
        compile_feedback_experience_record(
            wrong_review_receipt,
            canonical_feedback_ref="tests/fixtures/judgment_experience_memory/blind_feedback_wrong_review_ref.json",
            canonical_review_ref="tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md",
            record_id="JER:WRONG:REVIEW", source_case_id="BLIND:WRONG:REVIEW",
            source_refs=["tests/fixtures/judgment_experience_memory/blind_feedback_wrong_review_ref.json"],
            review_refs=["tests/fixtures/judgment_experience_memory/independent_postoutcome_review.md"], recorded_at=TIME,
            proposition="Same filenames must not substitute an independent review.", structural_key=_structural_key(),
            decision_or_no_action="No compilation under a mismatched review.", mechanism_chain="mismatch -> reject",
            observable_signals=["resolved review path"], strongest_rival="The artifact could be another review.",
            apply_when=["never"], do_not_apply_when=["review path differs"], investor_relevance="No registry admission.",
            retrieval_roles=["PRIMARY_ANALOG"], economic_failure_loci=["MEASUREMENT"],
        )


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

    same_cluster_record = _record()
    same_cluster_record["source_company_id"] = "HK:00000"
    same_cluster_record["source_company_cluster_id"] = _target()["company_cluster_id"]
    pack = build_experience_retrieval_pack(pack_id="ERP:SAME", target=_target(), records=[same_cluster_record], retrieved_at=TIME)
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
    assert card["source_case_id"] == "operating_transition"
    assert card["experience_record_id"] == record["record_id"]
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
        feedback_ref="tests/fixtures/judgment_experience_memory/feedback_settlement_binding.json",
        review_ref="tests/fixtures/judgment_experience_memory/independent_feedback_review.json",
        recorded_at="2026-08-30T10:00:00+08:00",
        explanation="The target outcome used an incompatible business-line perimeter, so the invocation cannot be diagnosed.",
        economic_failure_loci=["MEASUREMENT"],
    )
    assert validate_experience_feedback_event(event)["state"] == "REVIEWABLE"
    assert event["status"] == "MEASUREMENT_BLOCKED"

    with pytest.raises(JudgmentExperienceError, match="measurement_blocked_requires"):
        build_experience_feedback_event(
            event_id="EFE:BAD", receipt=receipt, status="MEASUREMENT_BLOCKED",
            feedback_ref="tests/fixtures/judgment_experience_memory/feedback_settlement_binding.json",
            review_ref="tests/fixtures/judgment_experience_memory/independent_feedback_review.json",
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


def test_latest_retired_record_cannot_resurrect_an_older_retrieval_ready_version() -> None:
    original = _record(record_id="JER:VERSIONED:V1")
    retired = deepcopy(original)
    retired.update({
        "version": 2,
        "status": "RETIRED",
        "recorded_at": "2026-08-30T10:00:00+08:00",
        "feedback_event_refs": ["EFE:TARGET:RETIRED"],
    })

    pack = build_experience_retrieval_pack(
        pack_id="ERP:VERSIONED:RETIRED", target=_target(), records=[original, retired], retrieved_at=TIME,
    )

    assert pack["status"] == "NO_APPLICABLE_EXPERIENCE"


def test_latest_bounded_record_replaces_old_scope_and_evidence_ceiling_filters_before_ranking() -> None:
    original = _record(record_id="JER:VERSIONED:V1")
    bounded = deepcopy(original)
    bounded.update({
        "version": 2,
        "status": "BOUNDED",
        "recorded_at": "2026-08-30T10:00:00+08:00",
        "feedback_event_refs": ["EFE:TARGET:BOUNDARY"],
        "do_not_apply_when": ["A different responsibility boundary is present."],
    })

    pack = build_experience_retrieval_pack(
        pack_id="ERP:VERSIONED:BOUNDED", target=_target(), records=[original, bounded], retrieved_at=TIME,
    )
    assert pack["candidates"][0]["record_version"] == 2
    assert pack["candidates"][0]["guidance"]["do_not_apply_when"] == ["A different responsibility boundary is present."]

    mechanism_only = _record(record_id="JER:CEILING:V1")
    mechanism_only["evidence_ceiling"] = "MECHANISM"
    no_permission_pack = build_experience_retrieval_pack(
        pack_id="ERP:CEILING", target=_target(), records=[mechanism_only], retrieved_at=TIME,
    )
    assert no_permission_pack["status"] == "NO_APPLICABLE_EXPERIENCE"


def test_unapplied_or_rogue_feedback_cannot_receive_transfer_credit_or_skip_versions() -> None:
    record = _record()
    pack = build_experience_retrieval_pack(pack_id="ERP:CN002475:V1", target=_target(), records=[record], retrieved_at=TIME)
    unapplied = build_experience_invocation_receipt(
        invocation_id="EIR:CN002475:UNAPPLIED:V1", retrieval_pack=pack, record=record,
        state="RETRIEVED_NOT_APPLIED", structural_match="Question only.", mismatch_dimensions=["No target change."],
        accepted_transfer=[], rejected_transfer=["No change."], changed_question_refs=[], changed_evidence_priority=[],
        changed_rival_or_discriminator_refs=[], changed_investor_treatment="", frozen_at=TIME,
    )
    with pytest.raises(JudgmentExperienceError, match="only_applied_preoutcome"):
        build_experience_feedback_event(
            event_id="EFE:UNAPPLIED", receipt=unapplied, status="SUPPORTED",
            feedback_ref="tests/fixtures/judgment_experience_memory/feedback_settlement_binding.json",
            review_ref="tests/fixtures/judgment_experience_memory/independent_feedback_review.json",
            recorded_at="2026-08-30T10:00:00+08:00", explanation="Must not credit a retrieval-only event.",
            economic_failure_loci=["MECHANISM"],
        )

    receipt = _applied_receipt(record, pack)
    event = build_experience_feedback_event(
        event_id="EFE:APPLIED", receipt=receipt, status="SUPPORTED",
        feedback_ref="tests/fixtures/judgment_experience_memory/feedback_settlement_binding.json",
        review_ref="tests/fixtures/judgment_experience_memory/independent_feedback_review.json",
        recorded_at="2026-08-30T10:00:00+08:00", explanation="A valid post-freeze application feedback event.",
        economic_failure_loci=["MECHANISM"],
    )
    updated = version_record_after_feedback(record, event, receipt=receipt, recorded_at="2026-08-30T10:00:00+08:00")
    rogue = deepcopy(updated)
    rogue["version"] = 99
    registry = {"schema_version": EXPERIENCE_REGISTRY_SCHEMA, "records": [record], "feedback_events": []}
    with pytest.raises(JudgmentExperienceError, match="updated_record_not_exact_feedback_derived_version"):
        append_experience_feedback(registry, record=record, event=event, receipt=receipt, updated_record=rogue)


@pytest.mark.parametrize(
    ("binding_ref", "review_ref", "expected"),
    [
        ("tests/fixtures/judgment_experience_memory/feedback_settlement_binding_wrong_case.json", "tests/fixtures/judgment_experience_memory/independent_feedback_review.json", "settlement_binding_target_case_id_mismatch"),
        ("tests/fixtures/judgment_experience_memory/feedback_settlement_binding_unauthorized.json", "tests/fixtures/judgment_experience_memory/independent_feedback_review_unauthorized.json", "outcome_access_not_authorized"),
        ("tests/fixtures/judgment_experience_memory/feedback_settlement_binding_wrong_authorization_case.json", "tests/fixtures/judgment_experience_memory/independent_feedback_review_wrong_authorization_case.json", "outcome_access_case_id_mismatch"),
        ("tests/fixtures/judgment_experience_memory/feedback_settlement_binding.json", "tests/fixtures/judgment_experience_memory/independent_feedback_review_rejected.json", "independent_review_not_accepted"),
    ],
)
def test_feedback_requires_matched_settlement_authorization_and_independent_acceptance(
    binding_ref: str, review_ref: str, expected: str,
) -> None:
    record = _record()
    pack = build_experience_retrieval_pack(pack_id="ERP:CN002475:V1", target=_target(), records=[record], retrieved_at=TIME)
    receipt = _applied_receipt(record, pack)
    with pytest.raises(JudgmentExperienceError, match=expected):
        build_experience_feedback_event(
            event_id="EFE:BAD:BINDING", receipt=receipt, status="SUPPORTED", feedback_ref=binding_ref,
            review_ref=review_ref, recorded_at="2026-08-30T10:00:00+08:00",
            explanation="No unrelated settlement or review may change an experience.", economic_failure_loci=["MECHANISM"],
        )


def test_real_registry_is_reviewable_and_keeps_only_references_and_questions() -> None:
    root = Path(__file__).resolve().parents[1]
    registry_path = root / "docs/development/research/training_campaigns/JUDGMENT_UTILITY_HISTORICAL_20260828/171_JUDGMENT_EXPERIENCE_REGISTRY_V1.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    assert validate_experience_registry(registry)["state"] == "REVIEWABLE"
    for record in registry["records"]:
        for ref in [*record["source_refs"], *record["review_refs"]]:
            assert (root / ref).is_file()
        assert not {"price", "valuation", "buyband", "probability", "investment_action"} & set(record)


def test_hundsunn_teaching_record_uses_its_core_option_structure_not_a_manufacturing_proxy() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root / "docs/development/research/training_campaigns/JUDGMENT_UTILITY_HISTORICAL_20260828/171_JUDGMENT_EXPERIENCE_REGISTRY_V1.json").read_text(encoding="utf-8"))
    record = next(item for item in registry["records"] if item["record_id"] == "JER:TEACH:CN600570:RESPONSIBILITY_CASH_BOUNDARY:V1")

    assert record["structural_key"] == {
        "mechanism_kinds": [
            "CORE_OPTION_RESPONSIBILITY_BOUNDARY",
            "REPEATABLE_CUSTOMER_ECONOMICS",
            "STRATEGIC_CAPITAL_ALLOCATION",
        ],
        "lifecycle": "MATURE_CORE_WITH_EMERGING_OPTION",
        "industry_epoch": "TECHNOLOGY_DEPLOYMENT_AND_REGULATORY_CYCLE",
        "competitive_arena": "MATURE_CORE_AND_EMERGING_OPTION",
        "responsibility_boundary": "CORE_BUSINESS_VS_EMERGING_OPTION_AND_STRATEGIC_CAPITAL",
        "company_constraints": [
            "R_AND_D_INTENSITY",
            "EARLY_OPTION_COMMERCIALIZATION",
            "STRATEGIC_CAPITAL_ALLOCATION",
        ],
    }


def test_real_different_company_sealed_application_freezes_a_question_not_a_target_conclusion() -> None:
    root = Path(__file__).resolve().parents[1]
    app_dir = root / "docs/development/research/experience_applications/CN601865_20240401"
    registry = json.loads((root / "docs/development/research/training_campaigns/JUDGMENT_UTILITY_HISTORICAL_20260828/171_JUDGMENT_EXPERIENCE_REGISTRY_V1.json").read_text(encoding="utf-8"))
    record = registry["records"][0]
    pack = json.loads((app_dir / "05_EXPERIENCE_RETRIEVAL_PACK.json").read_text(encoding="utf-8"))
    receipt = json.loads((app_dir / "06_EXPERIENCE_INVOCATION_RECEIPT.json").read_text(encoding="utf-8"))
    card = json.loads((app_dir / "07_ANALOGY_TRANSFER_CARD.json").read_text(encoding="utf-8"))

    assert record["source_company_cluster_id"] != receipt["target_company_cluster_id"]
    assert validate_experience_retrieval_pack(pack)["state"] == "REVIEWABLE"
    assert validate_experience_invocation_receipt(receipt)["state"] == "REVIEWABLE"
    projected_receipt, projected_card = project_existing_analogy_transfer_card(receipt, record, card)
    assert projected_receipt == receipt
    assert projected_card == card
    assert receipt["state"] == "APPLIED_PREOUTCOME"
    assert receipt["changed_question_refs"]
    assert receipt["changed_evidence_priority"]
    assert receipt["changed_rival_or_discriminator_refs"]
    assert "base normal owner-cash" in receipt["changed_investor_treatment"]
    serialized = json.dumps({"pack": pack, "receipt": receipt, "card": card}, ensure_ascii=False).lower()
    for forbidden in ("buyband", "investment_action", "target outcome"):
        assert forbidden not in serialized


def test_real_flatglass_feedback_updates_one_cash_leg_without_granting_transfer_credit() -> None:
    root = Path(__file__).resolve().parents[1]
    app_dir = root / "docs/development/research/experience_applications/CN601865_20240401"
    registry_path = root / "docs/development/research/training_campaigns/JUDGMENT_UTILITY_HISTORICAL_20260828/171_JUDGMENT_EXPERIENCE_REGISTRY_V1.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    settlement = json.loads((app_dir / "11_FY2024_CUSTODIAN_OUTCOME_SETTLEMENT.json").read_text(encoding="utf-8"))
    event = json.loads((app_dir / "14_EXPERIENCE_FEEDBACK_EVENT.json").read_text(encoding="utf-8"))
    review = json.loads((app_dir / "13_INDEPENDENT_EXPERIENCE_FEEDBACK_REVIEW.json").read_text(encoding="utf-8"))

    assert settlement["settled"] is True
    cell = settlement["frozen_cell_settlements"][0]
    assert cell["resolution_state"] == "RESOLVED__CASH_CAPEX_COVERED"
    assert cell["frozen_calculation"]["cash_capex_coverage_RMB"] == 1027226543.62
    assert event["status"] == "NOT_DIAGNOSTIC"
    assert review["verdict"] == "ACCEPT"
    assert review["permissions"]["transfer_validated"] is False
    assert validate_experience_feedback_event(event)["state"] == "REVIEWABLE"
    assert validate_experience_registry(registry)["state"] == "REVIEWABLE"

    versions = sorted(
        item["version"] for item in registry["records"]
        if item["record_id"] == event["record_id"]
    )
    assert versions == [1, 2]
    latest = next(
        item for item in registry["records"]
        if item["record_id"] == event["record_id"] and item["version"] == 2
    )
    assert latest["status"] == "RETRIEVAL_READY"
    assert event["event_id"] in latest["feedback_event_refs"]
