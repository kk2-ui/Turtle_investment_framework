from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.base_rate_case_library import (
    append_case,
    append_event,
    build_base_rate_context,
    build_candidate_cases_from_output,
    case_monitoring_tasks,
    evaluate_library,
    evaluate_output_base_rate,
    initialize_base_rate_policy,
    prepare_case,
    query_cases,
    validate_case,
    validate_verified_episode_reference,
)
from scripts.research_calibration import create_publication_snapshot


def _case(case_id: str = "CASE:test:001", *, mechanism: str = "cash_control_access_and_distribution") -> dict:
    return {
        "schema_version": "base-rate-case.v1", "case_id": case_id,
        "case_status_at_capture": "REVIEWABLE", "report_id": "01502.HK",
        "as_of": "2025-12-31", "information_cutoff": "2026-04-30",
        "archetype_ids": ["property_service"], "mechanism_keys": [mechanism],
        "variable_keys": ["valuation.v_final", "decision.position.recommended"],
        "decisive_question": {"question_id": "DQ:cash", "topic_family": "cash", "question": "受限现金最终能否由少数股东获得？"},
        "source_capture": {"kind": "publication_snapshot", "artifact_id": "publication_snapshot.json", "artifact_sha256": "a" * 64},
        "visible_evidence": [
            {"source_id": "annual-2025.pdf", "source_group_id": "annual-2025", "sha256": "b" * 64, "disclosed_at": "2026-03-28", "data_as_of": "2025-12-31"},
            {"source_id": "exchange-notice.pdf", "source_group_id": "exchange-2026", "sha256": "c" * 64, "disclosed_at": "2026-04-15", "data_as_of": "2026-04-15"},
        ],
        "prediction": {
            "status": "RECORDED", "outcome_space": [
                {"scenario_id": "distributed", "label": "现金兑现", "mechanism": "分红或回购"},
                {"scenario_id": "trapped", "label": "现金受限", "mechanism": "关联存款或低效并购"},
            ], "resolution_due": "2027-04-30", "probability_kind": "analyst_subjective",
            "probabilities": [
                {"scenario_id": "distributed", "value": 0.4, "interval": [0.25, 0.55]},
                {"scenario_id": "trapped", "value": 0.6, "interval": [0.45, 0.75]},
            ], "basis": "截至cutoff的治理与分红证据", "as_of": "2026-04-30",
        },
        "comparability": {
            "population_definition": "国企物业服务公司存在大额净现金但少数股东获取受限",
            "inclusion_rule": "同一现金控制机制且有年度披露",
            "exclusion_rule": "民营控股、无净现金或信息泄漏案例",
        },
    }


def _source(disclosed: str = "2027-05-02") -> list[dict]:
    return [{"source_id": "annual-2026.pdf", "sha256": "d" * 64, "disclosed_at": disclosed}]


def _episode(
    *, company_id: str = "01502.HK", episode_id: str = "MEP:test:001",
    common_question_set_id: str = "CQS:mature-cash-manufacturing.v1",
) -> dict:
    return {
        "episode_id": episode_id, "industry_regime": "consumer-demand-pressure",
        "common_question_set_id": common_question_set_id,
        "terminal_outcome_scope": "TERMINAL_OPERATING_OUTCOME",
        "mechanism_chain_ids": ["mechanism.cash-control"],
        "strongest_alternative_id": "alternative.trapped-cash",
        "financial_driver_bridge": {"state": "BOUND", "reference": "financial_driver_bridge.json#v1"},
        "forward_judgment_ids": ["fj.cash-access"], "baseline_ids": ["baseline.cash-access"],
        "cluster": {"company_id": company_id, "period_cluster_id": "2025", "mechanism_cluster_id": "cash-control"},
        "settlement_status": "OPEN",
    }


def _resolve_and_approve(root: Path, case_id: str, scenario: str) -> None:
    assert append_event({
        "event_id": "CASEEV:" + case_id.split(":")[-1] + ":outcome", "case_id": case_id,
        "event_type": "outcome", "observed_at": "2027-05-02", "source_evidence": _source(),
        "resolved_scenario_id": scenario,
    }, library_dir=root)["written"]
    assert append_event({
        "event_id": "CASEEV:" + case_id.split(":")[-1] + ":review", "case_id": case_id,
        "event_type": "eligibility_review", "observed_at": "2027-05-03", "source_evidence": _source(),
        "approved": True, "reviewer": "independent-reviewer", "rationale": "时间边界、口径和结果来源均已复核",
    }, library_dir=root)["written"]


def test_valid_case_schema_and_append_only_idempotence(tmp_path: Path) -> None:
    record = _case()
    first = append_case(record, library_dir=tmp_path)
    second = append_case(record, library_dir=tmp_path)
    assert first["validation"]["state"] == "REVIEWABLE"
    assert second["idempotent"] is True
    changed = deepcopy(record)
    changed["prediction"]["probabilities"][0].update({"value": 0.5, "interval": [0.4, 0.6]})
    changed["prediction"]["probabilities"][1].update({"value": 0.5, "interval": [0.4, 0.6]})
    assert append_case(changed, library_dir=tmp_path)["error"] == "append_only_case_conflict"
    assert len((tmp_path / "cases.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_verified_episode_reference_requires_matching_settled_case(tmp_path: Path) -> None:
    record = _case("CASE:near-miss:001")
    record["episode"] = _episode(episode_id="MEP:near-miss:001")
    assert append_case(record, library_dir=tmp_path)["written"]
    _resolve_and_approve(tmp_path, "CASE:near-miss:001", "trapped")
    outcome_id = "CASEEV:001:outcome"
    verified = validate_verified_episode_reference(
        case_id="CASE:near-miss:001", episode_id="MEP:near-miss:001",
        outcome_event_id=outcome_id, library_dir=tmp_path,
    )
    assert verified["state"] == "REVIEWABLE"
    mismatched = validate_verified_episode_reference(
        case_id="CASE:near-miss:001", episode_id="MEP:not-this-case",
        outcome_event_id=outcome_id, library_dir=tmp_path,
    )
    assert "episode_not_registered_for_case" in mismatched["invalid_findings"]


def test_future_information_and_hindsight_fields_are_invalid(tmp_path: Path) -> None:
    leaked = _case(); leaked["visible_evidence"][0]["disclosed_at"] = "2026-05-01"
    result = validate_case(prepare_case(leaked))
    assert "visible_evidence[0]:future_information_leakage" in result["invalid_findings"]
    leaked["prediction"]["outcome"] = "trapped"
    result = append_case(leaked, library_dir=tmp_path)
    assert result["written"] is False
    assert any("hindsight" in item for item in result["validation"]["invalid_findings"])


def test_same_source_group_warns_and_does_not_fake_cross_validation() -> None:
    record = _case()
    record["visible_evidence"][1]["source_group_id"] = "annual-2025"
    result = validate_case(prepare_case(record))
    assert result["state"] == "REVIEWABLE"
    assert "duplicate_source_groups_do_not_count_as_cross_validation" in result["warnings"]


def test_episode_identity_extends_the_existing_case_without_creating_a_second_library() -> None:
    record = _case(); record["episode"] = _episode()
    assert validate_case(prepare_case(record), require_episode_identity=True)["state"] == "REVIEWABLE"
    missing = validate_case(prepare_case(_case()), require_episode_identity=True)
    assert missing["state"] == "INCOMPLETE"
    assert "mechanism_episode_missing" in missing["incomplete_findings"]
    invalid = _case(); invalid["episode"] = _episode(); invalid["episode"]["cluster"].pop("mechanism_cluster_id")
    result = validate_case(prepare_case(invalid), require_episode_identity=True)
    assert result["state"] == "INCOMPLETE"
    assert "mechanism_episode:cluster_mechanism_cluster_id_missing" in result["incomplete_findings"]


def test_new_policy_requires_episode_only_for_cases_entering_reference_context(tmp_path: Path) -> None:
    library = tmp_path / "library"
    append_case(_case(), library_dir=library)
    _resolve_and_approve(library, "CASE:test:001", "trapped")
    context = build_base_rate_context(
        tmp_path, archetype_ids=["property_service"],
        questions=[{"mechanism_key": "cash_control_access_and_distribution", "decision_link": {}}],
        library_dir=library,
    )
    initialize_base_rate_policy(tmp_path, run_id="episode-required", enforced=True, context=context, require_episode_identity=True)
    result = evaluate_output_base_rate(tmp_path, library_dir=library, persist=False)
    assert result["state"] == "INCOMPLETE"
    assert "CASE:test:001:mechanism_episode_missing" in result["incomplete_findings"]


def test_selection_required_policy_excludes_unregistered_cases_from_calibration_cohort(tmp_path: Path) -> None:
    library = tmp_path / "library"
    append_case(_case(), library_dir=library)
    _resolve_and_approve(library, "CASE:test:001", "trapped")
    context = build_base_rate_context(
        tmp_path, archetype_ids=["property_service"],
        questions=[{"mechanism_key": "cash_control_access_and_distribution", "decision_link": {}}],
        library_dir=library,
    )
    initialize_base_rate_policy(
        tmp_path, run_id="selection-required", enforced=True, context=context,
        require_case_selection_identity=True,
    )
    result = evaluate_output_base_rate(tmp_path, library_dir=library, persist=False)
    assert result["state"] == "INCOMPLETE"
    assert "CASE:test:001:case_selection_missing" in result["incomplete_findings"]


def test_valuation_reference_index_cannot_become_historical_case() -> None:
    record = _case()
    record["source_capture"] = {
        "kind": "valuation_reference_index",
        "artifact_id": "130家估值模型/company_index.json",
        "artifact_sha256": "a" * 64,
    }
    result = validate_case(prepare_case(record))
    assert result["state"] == "INVALID"
    assert "mechanism_reference_not_case_evidence" in result["invalid_findings"]


def test_outcomes_are_post_cutoff_append_only_events(tmp_path: Path) -> None:
    append_case(_case(), library_dir=tmp_path)
    early = append_event({
        "event_id": "CASEEV:early", "case_id": "CASE:test:001", "event_type": "outcome",
        "observed_at": "2026-04-01", "source_evidence": _source("2026-04-01"),
        "resolved_scenario_id": "trapped",
    }, library_dir=tmp_path)
    assert early["written"] is False
    _resolve_and_approve(tmp_path, "CASE:test:001", "trapped")
    conflict = append_event({
        "event_id": "CASEEV:second-outcome", "case_id": "CASE:test:001", "event_type": "outcome",
        "observed_at": "2027-05-04", "source_evidence": _source(), "resolved_scenario_id": "distributed",
    }, library_dir=tmp_path)
    assert conflict["error"] == "case_outcome_already_recorded"


def test_only_resolved_and_approved_cases_enter_empirical_rate(tmp_path: Path) -> None:
    for index in range(5):
        case_id = f"CASE:sample:{index}"
        record = _case(case_id)
        record["episode"] = _episode(company_id=f"COMPANY:{index}", episode_id=f"MEP:sample:{index}")
        append_case(record, library_dir=tmp_path)
        _resolve_and_approve(tmp_path, case_id, "trapped" if index < 3 else "distributed")
    append_case(_case("CASE:unresolved"), library_dir=tmp_path)
    result = query_cases(
        mechanism_key="cash_control_access_and_distribution",
        archetype_ids=["property_service"], library_dir=tmp_path,
    )
    assert result["eligible_sample_size"] == 5
    assert result["independent_company_sample_size"] == 5
    assert result["empirical_base_rate"] == {"distributed": 0.4, "trapped": 0.6}
    assert all(item["case_fingerprint"] and item["outcome_event_id"] for item in result["eligible_cases"])


def test_case_monitoring_tasks_make_promotion_explicit(tmp_path: Path) -> None:
    append_case(_case(), library_dir=tmp_path)
    tasks = case_monitoring_tasks("01502.HK", library_dir=tmp_path)
    assert tasks[0]["state"] == "REVIEWABLE"
    assert tasks[0]["next_required_event"] == "record_outcome"
    assert tasks[0]["automatic_promotion_forbidden"] is True
    _resolve_and_approve(tmp_path, "CASE:test:001", "trapped")
    eligible = case_monitoring_tasks("01502.HK", library_dir=tmp_path)
    assert eligible[0]["state"] == "ELIGIBLE"
    assert eligible[0]["next_required_event"] is None


def test_small_sample_never_emits_pseudo_precise_base_rate(tmp_path: Path) -> None:
    append_case(_case(), library_dir=tmp_path); _resolve_and_approve(tmp_path, "CASE:test:001", "trapped")
    result = query_cases(mechanism_key="cash_control_access_and_distribution", archetype_ids=["property_service"], library_dir=tmp_path)
    assert result["eligible_sample_size"] == 1
    assert result["empirical_base_rate"] is None
    assert result["warnings"] == ["sample_too_small:1<5"]


def test_many_reports_from_one_company_do_not_create_an_empirical_base_rate(tmp_path: Path) -> None:
    for index in range(6):
        case_id = f"CASE:gree:{index}"
        record = _case(case_id)
        record["episode"] = _episode(company_id="000651.SZ", episode_id=f"MEP:gree:{index}")
        append_case(record, library_dir=tmp_path)
        _resolve_and_approve(tmp_path, case_id, "trapped" if index < 3 else "distributed")

    result = query_cases(
        mechanism_key="cash_control_access_and_distribution",
        archetype_ids=["property_service"], library_dir=tmp_path,
    )

    assert result["eligible_sample_size"] == 6
    assert result["independent_company_sample_size"] == 1
    assert result["independence_qualified"] is False
    assert result["empirical_base_rate"] is None
    assert any(item.startswith("correlated_company_episodes_prevent_base_rate:000651.SZ") for item in result["warnings"])


def test_mixed_question_sets_do_not_become_a_reference_class(tmp_path: Path) -> None:
    for index in range(5):
        case_id = f"CASE:mixed:{index}"
        record = _case(case_id)
        record["episode"] = _episode(
            company_id=f"COMPANY:{index}", episode_id=f"MEP:mixed:{index}",
            common_question_set_id="CQS:cash.v1" if index < 3 else "CQS:competition.v1",
        )
        append_case(record, library_dir=tmp_path)
        _resolve_and_approve(tmp_path, case_id, "trapped" if index < 3 else "distributed")

    result = query_cases(
        mechanism_key="cash_control_access_and_distribution",
        archetype_ids=["property_service"], library_dir=tmp_path,
    )

    assert result["independent_company_sample_size"] == 5
    assert result["independence_qualified"] is False
    assert result["empirical_base_rate"] is None
    assert any(item.startswith("mixed_common_question_sets_prevent_base_rate:") for item in result["warnings"])


def test_context_is_mechanism_first_and_freezes_case_fingerprints(tmp_path: Path) -> None:
    library = tmp_path / "library"
    append_case(_case(), library_dir=library); _resolve_and_approve(library, "CASE:test:001", "trapped")
    output = tmp_path / "output"; output.mkdir()
    question = {"mechanism_key": "cash_control_access_and_distribution", "decision_link": {"affected_metric_ids": ["valuation.v_final"]}}
    context = build_base_rate_context(output, archetype_ids=["property_service"], questions=[question], library_dir=library)
    query = context["queries"]["cash_control_access_and_distribution"]
    assert query["eligible_cases"][0]["case_fingerprint"]
    assert "company_name" not in query
    assert context["policy"]["company_name_matching_forbidden"] is True
    assert json.loads((output / "base_rate_context.json").read_text(encoding="utf-8"))["context_fingerprint"] == context["context_fingerprint"]


def test_candidate_extraction_never_promotes_unverified_old_report(tmp_path: Path) -> None:
    output, library = tmp_path / "output", tmp_path / "library"; output.mkdir()
    (output / "decisive_question_plan.json").write_text(json.dumps({
        "report_id": "000651.SZ", "generated_at": "2026-08-02T00:00:00+00:00",
        "input_sources": {"annual.pdf": "a" * 64}, "selected_questions": [{
            "question_id": "DQ:cycle", "topic_family": "cycle", "mechanism_key": "cycle_structure_or_accounting_disturbance",
            "question": "内销下滑是周期性还是结构性？", "competing_explanations": [
                {"explanation_id": "cycle", "label": "周期", "mechanism": "需求周期"},
                {"explanation_id": "structural", "label": "结构", "mechanism": "品类饱和"}],
            "decision_link": {"affected_metric_ids": ["valuation.v_final"]},
        }]
    }, ensure_ascii=False), encoding="utf-8")
    (output / "company_archetype.json").write_text(json.dumps({"primary_archetype": {"archetype_id": "mature_consumer_manufacturing"}, "secondary_archetypes": []}), encoding="utf-8")
    (output / "analysis_contract.json").write_text(json.dumps({"data_as_of": "2025-12-31"}), encoding="utf-8")
    result = build_candidate_cases_from_output(output, library_dir=library)
    assert result["written"] is True
    quality = evaluate_library(library)
    assert quality["summary"]["states"] == {"CANDIDATE": 1}
    assert quality["summary"]["eligible_case_count"] == 0
    case = json.loads((library / "cases.jsonl").read_text(encoding="utf-8"))
    assert case["prediction"]["status"] == "NOT_ASSIGNED"


def test_legacy_output_without_policy_skips_base_rate_gate(tmp_path: Path) -> None:
    assert evaluate_output_base_rate(tmp_path, library_dir=tmp_path / "library", persist=False)["state"] == "SKIP"


def test_enforced_policy_requires_frozen_context(tmp_path: Path) -> None:
    initialize_base_rate_policy(tmp_path, run_id="run-1", enforced=True, context={})
    result = evaluate_output_base_rate(tmp_path, library_dir=tmp_path / "library", persist=False)
    assert result["state"] == "INCOMPLETE"
    assert result["incomplete_findings"] == ["base_rate_context_missing"]


def test_small_sample_context_is_reviewable_but_fake_base_rate_is_invalid(tmp_path: Path) -> None:
    output, library = tmp_path / "output", tmp_path / "library"
    output.mkdir()
    append_case(_case(), library_dir=library)
    _resolve_and_approve(library, "CASE:test:001", "trapped")
    mechanism = "cash_control_access_and_distribution"
    context = build_base_rate_context(
        output,
        archetype_ids=["property_service"],
        questions=[{"mechanism_key": mechanism, "decision_link": {"affected_metric_ids": ["valuation.v_final"]}}],
        library_dir=library,
    )
    (output / "decisive_question_plan.json").write_text(json.dumps({
        "selected_questions": [{"mechanism_key": mechanism}]
    }), encoding="utf-8")
    initialize_base_rate_policy(output, run_id="run-1", enforced=True, context=context)
    clean = evaluate_output_base_rate(output, library_dir=library, persist=False)
    assert clean["state"] == "REVIEWABLE"
    assert "sample_too_small:1<5" in clean["warnings"]
    (output / "thesis_test.json").write_text(json.dumps({
        "probability_sets": [{"set_id": "prob.core", "estimates": [{
            "kind": "base_rate", "source_ids": ["CASE:test:001"]
        }]}]
    }), encoding="utf-8")
    invalid = evaluate_output_base_rate(output, library_dir=library, persist=False)
    assert invalid["state"] == "INVALID"
    assert "prob.core:base_rate_sample_too_small:1" in invalid["invalid_findings"]


def test_publication_snapshot_freezes_base_rate_context_hash(tmp_path: Path) -> None:
    context = build_base_rate_context(
        tmp_path,
        archetype_ids=["property_service"],
        questions=[{"mechanism_key": "cash_control_access_and_distribution", "decision_link": {}}],
        library_dir=tmp_path / "library",
    )
    result = create_publication_snapshot(tmp_path, "report", dry_run=True)
    assert result["written"] is True
    assert result["snapshot"]["ledger_sha256"]["base_rate_context"]
    assert result["snapshot"]["ledger_sha256"]["base_rate_context"] != context["context_fingerprint"]


def test_schema_files_parse() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas"
    for name in ("base_rate_case.schema.json", "base_rate_case_event.schema.json", "base_rate_context.schema.json", "base_rate_policy.schema.json", "case_selection_register.schema.json"):
        schema = json.loads((root / name).read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["required"]
