from copy import deepcopy
import json
from pathlib import Path

from scripts import judgment_training_curriculum as curriculum


def _lesson() -> dict:
    return {
        "state_and_constraint": "行业需求疲弱且公司有新产能等待吸收。",
        "management_choice_or_no_action": "管理层按计划投产并扩展渠道。",
        "customer_or_operating_response": "认证和开工发生，但客户订单与利用率改善较慢。",
        "cash_or_capital_result": "责任单元仍亏损，集团现金不能替代项目回报。",
        "mechanism_lesson": "建设完成只结算部署，客户吸收和资本回报必须另看。",
        "strongest_rival": "需求恢复可能滞后，不能仅据首年亏损判定项目失败。",
        "near_miss": "同样完成建设但没有责任匹配销量和利润的案例不能算商业成功。",
        "investor_treatment": "不给基准增长溢价，保留有条件的恢复选择权。",
        "transfer_question": "下一家公司应先检查利用率和费用后单位经济是否跟随投产。",
    }


def _teaching_case(case_id: str = "TEACH:CN002080:FY2019", *, cluster: str = "COMPANY:CN002080") -> dict:
    return {
        "case_id": case_id,
        "company_id": "CN:002080",
        "company_cluster_id": cluster,
        "company_name": "中材科技",
        "industry_id": "SPECIALTY_MATERIALS",
        "track": "TEACHING",
        "status": "CURATED",
        "cutoff_at": "2019-05-01T00:00:00+08:00",
        "outcome_window": None,
        "outcome_access": "RESULT_KNOWN",
        "selection_exposure": "RESULT_KNOWN_OR_DERIVED_VISIBLE",
        "role_isolation_state": "NOT_REQUIRED_FOR_TEACHING",
        "primary_capability_units": [
            "CUSTOMER_ABSORPTION",
            "CAPITAL_ALLOCATION",
        ],
        "mechanism_focus": "建设投产如何经过客户吸收和责任单元经济转成资本回报",
        "claim_scope": "WITHIN_CASE_MECHANISM",
        "comparative_mode": "NOT_REQUIRED",
        "source_refs": ["docs/example/settlement.json"],
        "artifact_refs": {"lesson_ref": "docs/example/investor-readout.md"},
        "lesson": _lesson(),
        "holdout_axis": None,
    }


def _blind_case(case_id: str = "BLIND:CN603195:FY2024", *, status: str = "SETTLED") -> dict:
    return {
        "case_id": case_id,
        "company_id": "CN:603195",
        "company_cluster_id": "COMPANY:CN603195",
        "company_name": "公牛集团",
        "industry_id": "CONSUMER_ELECTRICAL",
        "track": "BLIND_JUDGMENT",
        "status": status,
        "cutoff_at": "2024-05-01T00:00:00+08:00",
        "outcome_window": {
            "starts_at": "2025-04-01T00:00:00+08:00",
            "ends_at": "2025-05-01T00:00:00+08:00",
        },
        "outcome_access": "REVEALED_AFTER_FREEZE" if status == "SETTLED" else "SEALED",
        "selection_exposure": "PREOUTCOME_ONLY",
        "role_isolation_state": "ROLE_ISOLATION_PROVED" if status != "REGISTERED" else "BLIND_PACKET_READY",
        "primary_capability_units": [
            "BUSINESS_MODEL_ECONOMICS",
            "OWNER_CASH_CONVERSION",
        ],
        "mechanism_focus": "品牌渠道与费用后利润、集团现金和母公司现金的分离",
        "claim_scope": "ENTERPRISE_JUDGMENT",
        "comparative_mode": "NOT_REQUIRED",
        "source_refs": ["docs/example/preoutcome.json"],
        "artifact_refs": {
            "preoutcome_judgment_ref": "docs/example/preoutcome.json",
            **(
                {
                    "settlement_ref": "docs/example/settlement.json",
                    "postoutcome_review_ref": "docs/example/review.md",
                }
                if status == "SETTLED"
                else {}
            ),
        },
        "lesson": None,
        "holdout_axis": None,
    }


def _holdout_case() -> dict:
    return {
        "case_id": "HOLDOUT:CN000333:FY2018",
        "company_id": "CN:000333",
        "company_cluster_id": "COMPANY:CN000333",
        "company_name": "美的集团",
        "industry_id": "HOME_APPLIANCE",
        "track": "HISTORICAL_HOLDOUT",
        "status": "RESERVED",
        "cutoff_at": "2018-05-01T00:00:00+08:00",
        "outcome_window": {
            "starts_at": "2019-04-01T00:00:00+08:00",
            "ends_at": "2019-05-01T00:00:00+08:00",
        },
        "outcome_access": "SEALED",
        "selection_exposure": "METADATA_ONLY",
        "role_isolation_state": "BLIND_PACKET_READY",
        "primary_capability_units": ["MANAGEMENT_DECISION_EXECUTION"],
        "mechanism_focus": "并购整合后的产品、渠道、费用和现金吸收",
        "claim_scope": "ENTERPRISE_JUDGMENT",
        "comparative_mode": "NOT_REQUIRED",
        "source_refs": [],
        "artifact_refs": {"freeze_ref": "docs/example/holdout-freeze.json"},
        "lesson": None,
        "holdout_axis": "COMPANY",
    }


def _prospective_case() -> dict:
    return {
        "case_id": "FORWARD:CN601899:FY2026",
        "company_id": "CN:601899",
        "company_cluster_id": "COMPANY:CN601899",
        "company_name": "紫金矿业",
        "industry_id": "GLOBAL_MINING",
        "track": "PROSPECTIVE",
        "status": "FROZEN",
        "cutoff_at": "2026-05-01T00:00:00+08:00",
        "outcome_window": {
            "starts_at": "2027-03-01T00:00:00+08:00",
            "ends_at": "2027-05-01T00:00:00+08:00",
        },
        "outcome_access": "NOT_YET_RELEASED",
        "selection_exposure": "PREOUTCOME_ONLY",
        "role_isolation_state": "NOT_REQUIRED_RESULT_DOES_NOT_EXIST",
        "primary_capability_units": [
            "CAPITAL_ALLOCATION",
            "PERMANENT_LOSS_AND_LIFECYCLE",
        ],
        "mechanism_focus": "扩产和并购如何在单位经济、现金和跨境风险后创造价值",
        "claim_scope": "ENTERPRISE_JUDGMENT",
        "comparative_mode": "NOT_REQUIRED",
        "source_refs": ["docs/example/fy2025.pdf"],
        "artifact_refs": {
            "preoutcome_judgment_ref": "docs/example/judgment.md",
            "freeze_ref": "docs/example/freeze.json",
        },
        "lesson": None,
        "holdout_axis": None,
    }


def _curriculum() -> dict:
    return {
        "schema_version": curriculum.SCHEMA_VERSION,
        "curriculum_id": "JCC:ENTERPRISE-JUDGMENT:V1",
        "curriculum_version": "enterprise-judgment-curriculum.v1",
        "state": "BUILDING",
        "objective": "用高频教学建立机制认知，用历史盲判断练习，用独立留出考试，用前瞻案例校准现实稳定性。",
        "capacity_targets": {
            "TEACHING": {"lower": 20, "target": 24, "upper": 30},
            "BLIND_JUDGMENT": {"lower": 8, "target": 10, "upper": 12},
            "HISTORICAL_HOLDOUT": {"lower": 4, "target": 5, "upper": 6},
            "PROSPECTIVE": {"lower": 1, "target": 2, "upper": 3},
        },
        "execution_policy": {
            "same_company_cutoffs_count_as_independent": False,
            "teaching_can_use_known_results": True,
            "blind_requires_role_scoped_result_isolation": True,
            "holdout_can_influence_training": False,
            "prospective_wait_blocks_historical_training": False,
            "comparative_default": "NOT_REQUIRED",
            "teaching_cases_per_blind_cycle": 3,
        },
        "cases": [_teaching_case(), _blind_case(), _holdout_case(), _prospective_case()],
        "teaching_candidate_pool": [],
    }


def test_four_track_curriculum_is_reviewable_below_planning_capacity() -> None:
    result = curriculum.validate_curriculum(_curriculum())
    assert result["valid"], result["findings"]
    assert result["progress"]["capability_claim"] == "NOT_DEMONSTRATED_BY_CURRICULUM_COUNTS"
    assert not result["progress"]["historical_training_blocked_by_holdout_or_prospective"]


def test_known_result_local_pool_routes_to_teaching_instead_of_global_blacklist() -> None:
    result = curriculum.route_candidate(
        selection_exposure="RESULT_KNOWN_OR_DERIVED_VISIBLE",
        outcome_exists=True,
        outcome_released=True,
    )
    assert result["allowed_tracks"] == ["TEACHING"]


def test_preoutcome_candidate_can_enter_blind_or_holdout_without_comparative() -> None:
    result = curriculum.route_candidate(
        selection_exposure="PREOUTCOME_ONLY",
        outcome_exists=True,
        outcome_released=True,
    )
    assert result["allowed_tracks"] == ["TEACHING", "BLIND_JUDGMENT", "HISTORICAL_HOLDOUT"]
    assert _blind_case()["comparative_mode"] == "NOT_REQUIRED"


def test_teaching_only_curriculum_does_not_require_holdout_or_blind_lane() -> None:
    payload = _curriculum()
    payload["cases"] = [_teaching_case()]
    result = curriculum.validate_curriculum(payload)
    assert result["valid"], result["findings"]
    assert result["progress"]["next_action"] == "EXPAND_TEACHING_CANDIDATE_POOL"


def test_result_known_local_candidate_pool_adds_teaching_capacity_not_ability_evidence() -> None:
    payload = _curriculum()
    payload["cases"] = []
    payload["teaching_candidate_pool"] = [{
        "candidate_id": "TCAND:HAIER",
        "company_ids": ["CN:600690", "DE:690D"],
        "company_cluster_id": "COMPANY:HAIER",
        "company_name": "海尔智家",
        "industry_id": "HOME_APPLIANCE",
        "primary_capability_units": ["BUSINESS_MODEL_ECONOMICS", "CUSTOMER_ABSORPTION"],
        "mechanism_focus": "全球品牌、渠道和供应链如何转成同口径单位经济",
        "selection_exposure": "RESULT_KNOWN_OR_DERIVED_VISIBLE",
        "source_locator": "LOCAL_OUTPUT:600690_海尔智家",
    }]
    result = curriculum.validate_curriculum(payload)
    assert result["valid"], result["findings"]
    pool = result["progress"]["teaching_candidate_pool"]
    assert pool["independent_company_cluster_count"] == 1
    assert pool["teaching_library_pipeline_independent_company_cluster_count"] == 1
    assert pool["ability_evidence_count"] == 0
    assert result["progress"]["next_action"] == "CURATE_NEXT_TEACHING_CANDIDATE"


def test_result_known_case_cannot_masquerade_as_blind_or_holdout() -> None:
    payload = _curriculum()
    payload["cases"][1]["selection_exposure"] = "RESULT_KNOWN_OR_DERIVED_VISIBLE"
    result = curriculum.validate_curriculum(payload)
    assert not result["valid"]
    assert "cases[1].blind_role_cannot_have_result_exposure" in result["findings"]


def test_teaching_completion_requires_full_mechanism_lesson_not_a_field_receipt() -> None:
    payload = _curriculum()
    del payload["cases"][0]["lesson"]["cash_or_capital_result"]
    result = curriculum.validate_curriculum(payload)
    assert not result["valid"]
    assert "cases[0].lesson.cash_or_capital_result_missing" in result["findings"]


def test_repeated_cutoffs_of_one_company_do_not_increase_independent_sample_count() -> None:
    payload = _curriculum()
    repeat = deepcopy(_teaching_case("TEACH:CN002080:FY2020"))
    repeat["cutoff_at"] = "2020-05-01T00:00:00+08:00"
    payload["cases"].append(repeat)
    result = curriculum.validate_curriculum(payload)
    assert result["valid"], result["findings"]
    progress = result["progress"]["track_progress"]["TEACHING"]
    assert progress["episode_count"] == 2
    assert progress["independent_company_cluster_count"] == 1


def test_repeated_cutoffs_do_not_accelerate_teaching_to_blind_schedule() -> None:
    payload = _curriculum()
    payload["cases"] = [_teaching_case()]
    for year in (2020, 2021):
        repeat = deepcopy(_teaching_case(f"TEACH:CN002080:FY{year}"))
        repeat["cutoff_at"] = f"{year}-05-01T00:00:00+08:00"
        payload["cases"].append(repeat)
    status = curriculum.curriculum_status(payload)
    assert status["track_progress"]["TEACHING"]["completed_episode_count"] == 3
    assert status["track_progress"]["TEACHING"]["completed_independent_company_cluster_count"] == 1
    assert status["next_action"] == "EXPAND_TEACHING_CANDIDATE_POOL"


def test_two_listed_securities_may_share_one_economic_company_cluster() -> None:
    payload = _curriculum()
    first = _teaching_case("TEACH:HAIER-A:FY2020", cluster="COMPANY:HAIER")
    first["company_id"] = "CN:600690"
    first["company_name"] = "海尔智家A"
    second = deepcopy(first)
    second["case_id"] = "TEACH:HAIER-D:FY2020"
    second["company_id"] = "DE:690D"
    second["company_name"] = "海尔智家D"
    payload["cases"] = [first, second]
    result = curriculum.validate_curriculum(payload)
    assert result["valid"], result["findings"]
    progress = result["progress"]["track_progress"]["TEACHING"]
    assert progress["episode_count"] == 2
    assert progress["independent_company_cluster_count"] == 1


def test_same_security_cannot_silently_map_to_two_company_clusters() -> None:
    payload = _curriculum()
    repeat = deepcopy(_teaching_case("TEACH:CN002080:FY2020", cluster="COMPANY:OTHER"))
    payload["cases"].append(repeat)
    findings = curriculum.validate_curriculum(payload)["findings"]
    assert "curriculum.company_id_maps_to_multiple_clusters:CN:002080" in findings


def test_company_holdout_cannot_overlap_teaching_or_blind_cluster() -> None:
    payload = _curriculum()
    payload["cases"][2]["company_cluster_id"] = "COMPANY:CN002080"
    result = curriculum.validate_curriculum(payload)
    assert not result["valid"]
    assert "cases[2].company_holdout_cluster_seen_in_training" in result["findings"]


def test_holdout_reservation_does_not_claim_execution_isolation_before_execution() -> None:
    payload = _curriculum()
    assert curriculum.validate_curriculum(payload)["valid"]
    payload["cases"][2]["status"] = "FROZEN"
    result = curriculum.validate_curriculum(payload)
    assert "cases[2].executed_holdout_requires_proved_role_isolation" in result["findings"]


def test_relative_causal_claim_alone_requires_comparative() -> None:
    payload = _curriculum()
    payload["cases"][0]["claim_scope"] = "RELATIVE_CAUSAL_EFFECT"
    result = curriculum.validate_curriculum(payload)
    assert "cases[0].relative_causal_claim_requires_comparative" in result["findings"]
    payload["cases"][0]["comparative_mode"] = "REQUIRED_FOR_RELATIVE_CAUSAL_CLAIM"
    assert curriculum.validate_curriculum(payload)["valid"]


def test_comparative_cannot_become_a_default_requirement_for_enterprise_judgment() -> None:
    payload = _curriculum()
    payload["cases"][0]["comparative_mode"] = "REQUIRED_FOR_RELATIVE_CAUSAL_CLAIM"
    result = curriculum.validate_curriculum(payload)
    assert "cases[0].comparative_requirement_exceeds_claim_scope" in result["findings"]


def test_frozen_blind_case_requires_real_role_isolation_and_artifact_chain() -> None:
    payload = _curriculum()
    payload["cases"][1]["status"] = "FROZEN"
    payload["cases"][1]["outcome_access"] = "SEALED"
    payload["cases"][1]["role_isolation_state"] = "BLIND_PACKET_READY"
    result = curriculum.validate_curriculum(payload)
    assert "cases[1].blind_execution_requires_proved_role_isolation" in result["findings"]


def test_waiting_prospective_case_never_blocks_historical_training() -> None:
    status = curriculum.curriculum_status(_curriculum())
    assert status["state"] == "ACTIONABLE"
    assert status["historical_training_blocked_by_holdout_or_prospective"] is False


def test_sample_counts_never_auto_grant_capability_or_method_utility() -> None:
    payload = _curriculum()
    payload["capacity_targets"] = {
        track: {"lower": 0, "target": 0, "upper": 0} for track in curriculum.TRACKS
    }
    status = curriculum.curriculum_status(payload)
    assert status["capability_claim"] == "NOT_DEMONSTRATED_BY_CURRICULUM_COUNTS"
    assert status["method_utility_claim"] == "REQUIRES_BLIND_TREATMENT_FEEDBACK_AND_INDEPENDENT_HOLDOUT"


def test_checked_in_curriculum_registers_real_assets_without_overclaiming_capacity() -> None:
    repo = Path(__file__).resolve().parents[1]
    path = repo / "docs/development/research/training_curricula/ENTERPRISE_JUDGMENT_CAPABILITY_CURRICULUM_V1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = curriculum.validate_curriculum(payload)
    assert result["valid"], result["findings"]

    progress = result["progress"]
    assert progress["track_progress"]["TEACHING"]["completed_independent_company_cluster_count"] == 12
    assert progress["track_progress"]["BLIND_JUDGMENT"]["independent_company_cluster_count"] == 2
    assert progress["track_progress"]["BLIND_JUDGMENT"]["completed_independent_company_cluster_count"] == 1
    assert progress["track_progress"]["HISTORICAL_HOLDOUT"]["independent_company_cluster_count"] == 0
    assert progress["track_progress"]["PROSPECTIVE"]["independent_company_cluster_count"] == 2
    assert progress["teaching_candidate_pool"]["independent_company_cluster_count"] == 12
    assert progress["teaching_candidate_pool"]["teaching_library_pipeline_independent_company_cluster_count"] == 24
    assert progress["teaching_candidate_pool"]["ability_evidence_count"] == 0
    assert progress["next_action"] == "FREEZE_NEXT_REGISTERED_BLIND_CASE"
    assert progress["capability_claim"] == "NOT_DEMONSTRATED_BY_CURRICULUM_COUNTS"
    assert progress["comparative_is_default_entry"] is False
    assert progress["capability_coverage_by_distinct_company_clusters"]["CAPITAL_ALLOCATION"] == 7
    assert progress["capability_coverage_by_distinct_company_clusters"]["COMPETITION_AND_PRICING"] == 3
    assert progress["capability_coverage_by_distinct_company_clusters"]["VALUATION_AND_ENTRY_TREATMENT"] == 2
    assert progress["teaching_pipeline_coverage_by_distinct_company_clusters"]["VALUATION_AND_ENTRY_TREATMENT"] == 2

    for case in payload["cases"]:
        for ref in case["source_refs"]:
            assert (repo / ref).exists(), ref
        for ref in case["artifact_refs"].values():
            assert (repo / ref).exists(), ref
