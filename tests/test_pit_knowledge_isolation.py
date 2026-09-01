from __future__ import annotations

import json
from pathlib import Path

from scripts import base_rate_case_library as base_rate
from scripts import decisive_question
from judgment_generation_handoff import build_judgment_generation_handoff


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _contract(output: Path, *, pit: bool) -> None:
    payload = {
        "ts_code": "600340.SH",
        "company_id": "CN:600340",
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": "2020-04-27T18:00:00+08:00",
    }
    if pit:
        payload["pit_production"] = {
            "cutoff_at": "2020-04-27T18:00:00+08:00",
            "source_access": "PIT_ALLOWLIST_ONLY",
        }
    _write(output / "analysis_contract.json", payload)


def _empty_query(mechanism: str) -> dict:
    return {
        "mechanism_key": mechanism,
        "archetype_ids": ["industrial"],
        "variable_keys": [],
        "eligible_sample_size": 0,
        "independent_company_sample_size": 0,
        "independence_qualified": False,
        "common_question_set_ids": [],
        "terminal_outcome_scopes": [],
        "outcome_counts": {},
        "empirical_base_rate": None,
        "eligible_cases": [],
        "warnings": [],
    }


def test_pit_base_rate_does_not_open_current_library(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "pit-output"
    output.mkdir()
    _contract(output, pit=True)
    current_library = tmp_path / "current-library"
    current_library.mkdir()

    def forbidden_query(**_kwargs):
        raise AssertionError("PIT attempted to query the current base-rate library")

    def forbidden_read(_path):
        raise AssertionError("PIT attempted to read the current base-rate library")

    monkeypatch.setattr(base_rate, "query_cases", forbidden_query)
    monkeypatch.setattr(base_rate, "_read_jsonl", forbidden_read)
    context = base_rate.build_base_rate_context(
        output,
        archetype_ids=["industrial"],
        questions=[{"mechanism_key": "channel_transition", "decision_link": {}}],
        library_dir=current_library,
        persist=False,
    )

    query = context["queries"]["channel_transition"]
    assert context["availability"] == {
        "mode": "PIT_EVIDENCE_ONLY",
        "cutoff_at": "2020-04-27T18:00:00+08:00",
        "base_rate_library": "UNAVAILABLE_NO_CASE_LEVEL_ADMISSION",
    }
    assert query["eligible_sample_size"] == 0
    assert query["eligible_cases"] == []
    assert query["empirical_base_rate"] is None
    assert "pit_global_base_rate_library_forbidden_without_case_level_admission" in context["warnings"]
    assert base_rate.validate_base_rate_context(
        context, output_dir=output, library_dir=current_library,
    )["state"] == "REVIEWABLE"


def test_non_pit_base_rate_still_queries_current_library(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "current-output"
    output.mkdir()
    _contract(output, pit=False)
    library = tmp_path / "current-library"
    library.mkdir()
    called = []

    def current_query(**kwargs):
        called.append(kwargs)
        return _empty_query(str(kwargs["mechanism_key"]))

    monkeypatch.setattr(base_rate, "query_cases", current_query)
    context = base_rate.build_base_rate_context(
        output,
        archetype_ids=["industrial"],
        questions=[{"mechanism_key": "channel_transition", "decision_link": {}}],
        library_dir=library,
        persist=False,
    )

    assert len(called) == 1
    assert called[0]["library_dir"] == library.resolve()
    assert context["availability"]["mode"] == "CURRENT_LIBRARY"


def test_pit_industry_context_does_not_open_current_knowledge(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "pit-output"
    output.mkdir()
    _contract(output, pit=True)

    def forbidden_initialize(*_args, **_kwargs):
        raise AssertionError("PIT attempted to open current industry knowledge")

    monkeypatch.setattr(
        "scripts.industry_knowledge.initialize_industry_knowledge",
        forbidden_initialize,
    )
    context = decisive_question.build_industry_knowledge_context(output)

    assert context["validation_status"] == "PIT_EVIDENCE_ONLY"
    assert context["matched_mechanisms"] == []
    assert context["availability"]["industry_knowledge"] == (
        "UNAVAILABLE_NO_OBJECT_LEVEL_ADMISSION"
    )
    assert context["warnings"] == [
        "pit_global_industry_knowledge_forbidden_without_object_level_admission"
    ]


def test_non_pit_industry_context_still_projects_ready_mechanism(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "current-output"
    output.mkdir()
    _contract(output, pit=False)
    mechanism = {
        "mechanism_id": "IKM:channel",
        "mechanism_key": "channel_transition",
        "title": "Channel transition",
        "status": "MECHANISM_READY",
        "industry_keys": ["appliance"],
        "company_verification_fields": ["same-scope channel volume"],
        "alternative_explanations": ["product cycle"],
    }
    monkeypatch.setattr(
        "scripts.industry_knowledge.load_company_industry_metadata",
        lambda _output: {
            "company_id": "600340.SH", "industry_keys": ["appliance"],
            "mechanism_keys": [], "archetype_ids": [], "source_metadata_files": [],
        },
    )
    monkeypatch.setattr(
        "scripts.industry_knowledge.build_company_industry_profile",
        lambda *_args, **_kwargs: {
            "schema_version": "company-industry-profile.v1",
            "company_id": "600340.SH", "industry_keys": ["appliance"],
            "profile_role": "research_prompt_prior_only", "mechanisms": [mechanism],
            "required_company_verification_fields": ["same-scope channel volume"],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "scripts.industry_knowledge.read_industry_knowledge_context",
        lambda *_args, **_kwargs: {
            "profile": {"mechanisms": [mechanism]},
            "research_questions": [{**mechanism, "match_reason": "current taxonomy match"}],
            "availability": {"mode": "CURRENT_LIBRARY", "industry_knowledge": "AVAILABLE"},
            "validation_status": "AVAILABLE", "warnings": [],
        },
    )

    context = decisive_question.build_industry_knowledge_context(output)

    assert context["matched_mechanisms"][0]["mechanism_id"] == "IKM:channel"
    assert context["matched_mechanisms"][0]["company_assessment"] == "NOT_EVIDENCED"
    assert context["availability"]["mode"] == "CURRENT_LIBRARY"


def test_pit_decisive_plan_generation_records_both_knowledge_degradations(
    tmp_path: Path, monkeypatch,
) -> None:
    _contract(tmp_path, pit=True)
    _write(tmp_path / "report_context.json", {
        "meta": {"report_id": "600340.SH"}, "domains": {},
    })
    _write(tmp_path / "compute_bundle.json", {})
    _write(tmp_path / "company_archetype.json", {
        "primary_archetype": {"archetype_id": "industrial"},
        "secondary_archetypes": [],
    })
    monkeypatch.setattr(
        decisive_question, "generate_decisive_candidates", lambda *_args, **_kwargs: [],
    )

    plan = decisive_question.build_decisive_question_plan(tmp_path, persist=False)

    assert plan["industry_knowledge_context"]["matched_mechanisms"] == []
    assert plan["industry_knowledge_context"]["availability"]["mode"] == (
        "PIT_EVIDENCE_ONLY"
    )
    assert "pit_global_industry_knowledge_forbidden_without_object_level_admission" in (
        plan["industry_knowledge_context"]["warnings"]
    )
    assert "pit_global_base_rate_library_forbidden_without_case_level_admission" in (
        plan["base_rate_context"]["warnings"]
    )


def _handoff_evidence(output: Path) -> None:
    _write(output / "report_context.json", {
        "meta": {"report_id": "600340.SH"},
        "coverage": {"citable_observation_ids": ["OBS:pit"]},
        "unresolved_gaps": [], "conflicts": [],
        "validation": {"state": "REVIEWABLE"},
    })
    _write(output / "official_evidence_validation.json", {"state": "REVIEWABLE"})


def test_pit_handoff_strips_unproven_upstream_plan_and_prior(tmp_path: Path) -> None:
    _contract(tmp_path, pit=True)
    _handoff_evidence(tmp_path)
    _write(tmp_path / "base_rate_context.json", {
        "availability": {"mode": "CURRENT_LIBRARY"},
        "queries": {"channel_transition": {"eligible_sample_size": 8}},
    })
    _write(tmp_path / "decisive_question_plan.json", {
        "report_id": "600340.SH",
        "selected_questions": [{
            "question_id": "DQ:unsafe", "mechanism_key": "channel_transition",
            "question": "This question was influenced by current global knowledge?",
            "candidate_origins": ["industry_knowledge:IKM:future"],
            "base_rate_refs": ["CASE:future"], "base_rate_sample_size": 8,
        }],
        "industry_knowledge_context": {
            "matched_mechanisms": [{
                "mechanism_id": "IKM:future", "status": "MECHANISM_READY",
                "company_assessment": "NOT_EVIDENCED",
            }],
        },
        "validation": {"state": "REVIEWABLE"},
    })
    _write(tmp_path / "decisive_question_validation.json", {"state": "REVIEWABLE"})

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "READY_WITH_NO_PRIOR"
    assert handoff["projection"]["agenda_mode"] == "EVIDENCE_ONLY"
    assert handoff["projection"]["decisive_questions"] == []
    assert handoff["projection"]["industry_priors"] == []
    assert handoff["readiness"]["empty_states"]["industry_priors"] == "PIT_EVIDENCE_ONLY"
    assert not any(
        str(item.get("artifact_ref") or "").startswith("canonical:industry_knowledge")
        for item in handoff["source_refs"]
    )
    assert "pit_upstream_decisive_plan_rejected_unproven_knowledge_isolation" in (
        handoff["readiness"]["warnings"]
    )


def test_pit_handoff_accepts_evidence_only_plan_with_explicit_isolation(tmp_path: Path) -> None:
    _contract(tmp_path, pit=True)
    _handoff_evidence(tmp_path)
    _write(tmp_path / "base_rate_context.json", {
        "availability": {
            "mode": "PIT_EVIDENCE_ONLY",
            "base_rate_library": "UNAVAILABLE_NO_CASE_LEVEL_ADMISSION",
        },
        "queries": {"issuer_evidence": {"eligible_sample_size": 0}},
    })
    _write(tmp_path / "decisive_question_plan.json", {
        "report_id": "600340.SH",
        "selected_questions": [{
            "question_id": "DQ:pit", "mechanism_key": "issuer_evidence",
            "question": "Which cutoff-visible issuer evidence distinguishes the two operating paths?",
            "candidate_origins": ["official_evidence"],
            "base_rate_refs": [], "base_rate_sample_size": 0,
        }],
        "industry_knowledge_context": {
            "matched_mechanisms": [],
            "availability": {
                "mode": "PIT_EVIDENCE_ONLY",
                "industry_knowledge": "UNAVAILABLE_NO_OBJECT_LEVEL_ADMISSION",
            },
        },
        "validation": {"state": "REVIEWABLE"},
    })
    _write(tmp_path / "decisive_question_validation.json", {"state": "REVIEWABLE"})

    handoff = build_judgment_generation_handoff(tmp_path, "RESEARCH_AGENDA")

    assert handoff["readiness"]["state"] == "READY"
    assert handoff["projection"]["agenda_mode"] == "DECISIVE_PLAN"
    assert [item["question_id"] for item in handoff["projection"]["decisive_questions"]] == [
        "DQ:pit"
    ]
    assert handoff["projection"]["industry_priors"] == []
    assert handoff["readiness"]["empty_states"]["industry_priors"] == "PIT_EVIDENCE_ONLY"
    assert "pit_global_base_rate_library_forbidden_without_case_level_admission" in (
        handoff["readiness"]["warnings"]
    )


def test_no_primary_cjo_remains_complete_but_cannot_enter_investment_enrichment(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "analysis_contract.json", {
        "ts_code": "600340.SH", "company_id": "CN:600340",
        "analysis_purpose": "INVESTMENT_DECISION", "data_as_of": "2020-04-27",
    })
    _write(tmp_path / "company_judgment_predecessor.json", {
        "schema_version": "company-judgment-predecessor.v2",
        "identity": {"status": "G1J_COMPLETE", "missing_components": []},
        "source": {
            "report_id": "600340.SH", "data_as_of": "2020-04-27",
            "thesis_validation_state": "DECISION_READY",
            "financial_driver_bridge_validation_state": "REVIEWABLE",
        },
        "forward_judgments": [{"judgment_id": "FJ:signal-probe"}],
        "mechanism_chains": [{"chain_id": "MC:two-sided"}],
        "rival_hypothesis_pairs": [{"pair_id": "RHP:two-sided"}],
        "analogy_transfer_cards": [{"card_id": "ATC:boundary"}],
        "selection_admission": {
            "status": "NO_PRIMARY", "reason": "cutoff-visible evidence is non-directional",
        },
        "financial_driver_bridge": {
            "report_id": "600340.SH", "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
            "drivers": [{"driver_id": "FDB:signal"}], "allocation_events": [],
        },
    })
    _write(tmp_path / "valuation_route.json", {
        "report_id": "600340.SH", "route_id": "VR:test",
        "validation": {"state": "REVIEWABLE"},
    })

    handoff = build_judgment_generation_handoff(tmp_path, "INVESTMENT_ENRICHMENT")

    assert handoff["readiness"]["state"] == "INCOMPLETE"
    assert "company_judgment_predecessor.central_path_missing" in (
        handoff["readiness"]["incomplete_findings"]
    )
    assert "investment_enrichment_requires_selection_admitted_company_judgment" in (
        handoff["readiness"]["incomplete_findings"]
    )
