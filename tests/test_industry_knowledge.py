import json

from industry_knowledge import (
    build_company_industry_profile,
    initialize_industry_knowledge,
    read_industry_knowledge_context,
    review_industry_mechanism,
    search_industry_knowledge,
    validate_industry_knowledge,
    write_industry_insight_candidate,
)


MECHANISM_KEY = "margin_channel_cost_offset"
INDUSTRY_KEY = "consumer_bottling"


def _candidate(candidate_id: str, group: str, period: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "status": "CANDIDATE",
        "title": "毛利变化必须与渠道费用一起观察",
        "mechanism_key": MECHANISM_KEY,
        "industry_keys": [INDUSTRY_KEY],
        "company_id": candidate_id.replace("IKC:", "COMPANY:"),
        "corporate_group_id": group,
        "reporting_period": period,
        "insight": "毛利率变化可能被销售配送费用率抵消，不能单独外推利润。",
        "applicability_conditions": ["产品组合和渠道费用均对经营利润有材料影响"],
        "non_applicability_conditions": ["销售费用与渠道履约无关且已被单列重分类"],
        "alternative_explanations": ["一次性税项或会计分类变化造成利润变化"],
        "company_verification_fields": ["毛利率", "销售配送费用率", "产品组合", "关键包材成本"],
        "evidence": [{
            "evidence_type": "OBS", "reference_id": "OBS:" + candidate_id,
            "source_id": "annual-report-" + candidate_id, "source_group_id": "filing-" + candidate_id,
            "authority": "audited_filing", "published_at": "2026-03-20", "data_as_of": period,
            "statement": "毛利率和销售费用率均由经审计年报直接披露。", "direct_support": True,
        }],
    }


def _mechanism(status: str, candidate_ids: list[str]) -> dict:
    payload = {
        "mechanism_id": "IKM:margin-channel-cost-offset",
        "author_id": "mechanism-author",
        "status": status,
        "mechanism_key": MECHANISM_KEY,
        "title": "毛利与渠道费用对冲",
        "summary": "产品或投入成本引起的毛利变化，可能被销售、配送或促销效率抵消或放大。",
        "industry_keys": [INDUSTRY_KEY],
        "candidate_ids": candidate_ids,
        "applicability_conditions": ["渠道履约费用对利润有材料影响"],
        "non_applicability_conditions": ["仅由无关的一次性会计重分类驱动"],
        "alternative_explanations": ["税率变化或一次性补贴导致利润变化"],
        "company_verification_fields": ["毛利率", "销售配送费用率", "产品组合", "关键包材成本"],
        "prohibited_uses": ["company_fact", "valuation_parameter", "probability", "automatic_investment_conclusion"],
    }
    if status == "MECHANISM_READY":
        payload["author_id"] = "mechanism-author"
        payload["independent_review"] = {
            "reviewer_id": "independent-reviewer",
            "reviewed_at": "2026-08-16",
            "scope": "验证机制表述、适用边界、反例、替代解释和公司取证字段",
            "outcome": "ACCEPTED",
            "independent": True,
        }
        payload["settled_episode_evidence"] = [
            {
                "episode_id": "MEP:group-a-margin",
                "company_id": "COMPANY:group-a",
                "corporate_group_id": "group-a",
                "information_cutoff": "2023-08-31",
                "claim_id": "HBTCLM:group-a-margin",
                "settlement_id": "HBTSETTLE:group-a-margin",
                "settled_at": "2024-03-31",
                "outcome_artifact_ref": "research/group-a/settlement.json",
                "review_artifact_ref": "research/group-a/settlement-review.md",
                "reviewer_id": "episode-reviewer-a",
                "independent_reviewed": True,
                "relationship_to_mechanism": "SUPPORTS",
            },
            {
                "episode_id": "MEP:group-b-margin",
                "company_id": "COMPANY:group-b",
                "corporate_group_id": "group-b",
                "information_cutoff": "2024-08-31",
                "claim_id": "HBTCLM:group-b-margin",
                "settlement_id": "HBTSETTLE:group-b-margin",
                "settled_at": "2025-03-31",
                "outcome_artifact_ref": "research/group-b/settlement.json",
                "review_artifact_ref": "research/group-b/settlement-review.md",
                "reviewer_id": "episode-reviewer-b",
                "independent_reviewed": True,
                "relationship_to_mechanism": "SUPPORTS",
            },
            {
                "episode_id": "MEP:group-c-boundary",
                "company_id": "COMPANY:group-c",
                "corporate_group_id": "group-c",
                "information_cutoff": "2025-08-31",
                "claim_id": "HBTCLM:group-c-boundary",
                "settlement_id": "HBTSETTLE:group-c-boundary",
                "settled_at": "2026-03-31",
                "outcome_artifact_ref": "research/group-c/settlement.json",
                "review_artifact_ref": "research/group-c/settlement-review.md",
                "reviewer_id": "episode-reviewer-c",
                "independent_reviewed": True,
                "relationship_to_mechanism": "BOUNDARY",
            },
        ]
    return payload


def test_default_policy_and_taxonomy_are_canonical_not_chat_memory(tmp_path):
    result = initialize_industry_knowledge(tmp_path / "industry")
    policy = result["policy"]
    assert policy["library_role"] == "research_prompt_prior_only"
    assert {"company_fact", "valuation_parameter", "probability"}.issubset(policy["prohibited_uses"])
    assert result["taxonomy"]["mechanism_families"]
    assert (tmp_path / "industry" / "candidates").is_dir()
    assert (tmp_path / "industry" / "mechanisms").is_dir()


def test_candidate_requires_direct_obs_or_doc_evidence(tmp_path):
    candidate = _candidate("IKC:weak", "group-a", "FY2024")
    candidate["evidence"][0]["evidence_type"] = "REPORT"
    result = write_industry_insight_candidate(candidate, knowledge_dir=tmp_path / "industry")
    assert result["written"] is False
    assert "evidence[0]:not_direct_obs_or_doc" in result["validation"]["invalid_findings"]


def test_same_group_cannot_fake_corroboration_but_independent_groups_can_share_a_reporting_period(tmp_path):
    library = tmp_path / "industry"
    first = _candidate("IKC:first", "group-a", "FY2024")
    same_group_same_period = _candidate("IKC:same-group-period", "group-a", "FY2024")
    same_group_new_period = _candidate("IKC:same-group-new-period", "group-a", "FY2025")
    for candidate in (first, same_group_same_period, same_group_new_period):
        assert write_industry_insight_candidate(candidate, knowledge_dir=library)["written"] is True
    result = review_industry_mechanism(
        _mechanism("CORROBORATED", ["IKC:first", "IKC:same-group-period", "IKC:same-group-new-period"]), knowledge_dir=library,
    )
    assert result["written"] is False
    validation = result["validation"]
    assert validation["independent_corporate_group_count"] == 1
    assert validation["distinct_reporting_period_count"] == 2
    assert (
        "cross_group_or_concentrated_industry_corroboration_insufficient:groups=1;periods=2"
        in validation["invalid_findings"]
    )

    independent_group_library = tmp_path / "independent-group"
    for candidate in (
        _candidate("IKC:group-a-2024", "group-a", "FY2024"),
        _candidate("IKC:group-b-2024", "group-b", "FY2024"),
    ):
        assert write_industry_insight_candidate(candidate, knowledge_dir=independent_group_library)["written"] is True
    independent_group_result = review_industry_mechanism(
        _mechanism("CORROBORATED", ["IKC:group-a-2024", "IKC:group-b-2024"]), knowledge_dir=independent_group_library,
    )
    assert independent_group_result["written"] is True
    assert independent_group_result["validation"]["corroboration_basis"] == "independent_corporate_groups"


def test_mechanism_ready_requires_independent_review_and_only_yields_questions(tmp_path):
    library = tmp_path / "industry"
    ids = ["IKC:a", "IKC:b", "IKC:c"]
    for candidate in (
        _candidate(ids[0], "group-a", "FY2023"),
        _candidate(ids[1], "group-b", "FY2024"),
        _candidate(ids[2], "group-c", "FY2025"),
    ):
        assert write_industry_insight_candidate(candidate, knowledge_dir=library)["written"] is True
    mechanism = _mechanism("MECHANISM_READY", ids)
    mechanism.pop("independent_review")
    missing_review = review_industry_mechanism(mechanism, knowledge_dir=library)
    assert missing_review["written"] is False
    assert missing_review["validation"]["state"] == "INCOMPLETE"
    assert "mechanism_ready_independent_review_missing_or_not_accepted" in missing_review["validation"]["incomplete_findings"]

    mechanism = _mechanism("MECHANISM_READY", ids)
    result = review_industry_mechanism(mechanism, knowledge_dir=library)
    assert result["written"] is True
    assert result["validation"]["independent_corporate_group_count"] == 3
    profile = build_company_industry_profile(
        {"company_id": "00506.HK", "industry_keys": [INDUSTRY_KEY]}, knowledge_dir=library,
    )
    assert profile["mechanisms"][0]["mechanism_id"] == "IKM:margin-channel-cost-offset"
    assert "valuation_parameter" in profile["prohibited_uses"]
    context = read_industry_knowledge_context("00506.HK", industry_keys=[INDUSTRY_KEY], knowledge_dir=library)
    assert context["research_questions"]
    assert context["usage_contract"]["cannot_establish_company_fact"] is True
    assert context["usage_contract"]["cannot_supply_valuation_parameter"] is True
    assert context["usage_contract"]["cannot_supply_probability"] is True

    same_author = _mechanism("MECHANISM_READY", ids)
    same_author["independent_review"]["reviewer_id"] = same_author["author_id"]
    rejected = review_industry_mechanism(same_author, knowledge_dir=tmp_path / "same-author")
    assert rejected["written"] is False
    assert "mechanism_ready_reviewer_same_as_author" in rejected["validation"]["invalid_findings"]


def test_mechanism_ready_requires_settled_cross_company_support_and_a_boundary(tmp_path):
    library = tmp_path / "industry"
    ids = ["IKC:a", "IKC:b", "IKC:c"]
    for candidate, group, period in zip(ids, ("group-a", "group-b", "group-c"), ("FY2023", "FY2024", "FY2025"), strict=True):
        assert write_industry_insight_candidate(
            _candidate(candidate, group, period), knowledge_dir=library,
        )["written"] is True

    missing = _mechanism("MECHANISM_READY", ids)
    missing.pop("settled_episode_evidence")
    result = review_industry_mechanism(missing, knowledge_dir=library)
    assert result["written"] is False
    assert "mechanism_ready_settled_episode_evidence_missing" in result["validation"]["incomplete_findings"]

    same_group = _mechanism("MECHANISM_READY", ids)
    for item in same_group["settled_episode_evidence"]:
        if item["relationship_to_mechanism"] == "SUPPORTS":
            item["corporate_group_id"] = "group-a"
    result = review_industry_mechanism(same_group, knowledge_dir=library)
    assert result["written"] is False
    assert (
        "mechanism_ready_independent_settled_support_insufficient:groups=1;required=2"
        in result["validation"]["incomplete_findings"]
    )

    no_boundary = _mechanism("MECHANISM_READY", ids)
    no_boundary["settled_episode_evidence"][-1]["relationship_to_mechanism"] = "NOT_DIAGNOSTIC"
    result = review_industry_mechanism(no_boundary, knowledge_dir=library)
    assert result["written"] is False
    assert "mechanism_ready_boundary_or_counterexample_missing" in result["validation"]["incomplete_findings"]

    post_outcome = _mechanism("MECHANISM_READY", ids)
    post_outcome["settled_episode_evidence"][0]["information_cutoff"] = "2024-04-01"
    result = review_industry_mechanism(post_outcome, knowledge_dir=library)
    assert result["written"] is False
    assert (
        "settled_episode_evidence[0]:settlement_not_after_information_cutoff"
        in result["validation"]["invalid_findings"]
    )


def test_concentrated_industry_exception_is_explicit_and_limited(tmp_path):
    library = tmp_path / "industry"
    ids = ["IKC:single-group-2023", "IKC:single-group-2024", "IKC:single-group-2025"]
    for candidate, period in zip(ids, ("FY2023", "FY2024", "FY2025"), strict=True):
        assert write_industry_insight_candidate(
            _candidate(candidate, "group-only", period), knowledge_dir=library,
        )["written"] is True

    no_exception = review_industry_mechanism(
        _mechanism("CORROBORATED", ids), knowledge_dir=library,
    )
    assert no_exception["written"] is False
    assert no_exception["validation"]["corroboration_basis"] == "insufficient"

    exception = _mechanism("CORROBORATED", ids)
    exception["concentrated_industry_exception"] = {
        "enabled": True,
        "rationale": "该监管辖区仅有一个具有可得、完整长期披露的合格经营主体。",
        "external_validity_limitation": "该机制仅能作为该辖区的有限先验，不能外推为跨公司行业规律。",
    }
    result = review_industry_mechanism(exception, knowledge_dir=library)
    assert result["written"] is True
    assert result["validation"]["corroboration_basis"] == "concentrated_industry_multi_period_limited"
    assert result["validation"]["external_validity_limited"] is True


def test_corroborated_card_is_reviewer_material_not_an_auto_injected_company_question(tmp_path):
    library = tmp_path / "industry"
    ids = ["IKC:group-a", "IKC:group-b"]
    for candidate, group in zip(ids, ("group-a", "group-b"), strict=True):
        assert write_industry_insight_candidate(
            _candidate(candidate, group, "FY2025"), knowledge_dir=library,
        )["written"] is True
    assert review_industry_mechanism(
        _mechanism("CORROBORATED", ids), knowledge_dir=library,
    )["written"] is True

    default_search = search_industry_knowledge(
        industry_keys=[INDUSTRY_KEY], knowledge_dir=library,
    )
    assert default_search["results"] == []
    reviewer_search = search_industry_knowledge(
        industry_keys=[INDUSTRY_KEY], statuses=["CORROBORATED"], knowledge_dir=library,
    )
    assert reviewer_search["results"][0]["status"] == "CORROBORATED"
    assert "candidate_ids" not in reviewer_search["results"][0]
    assert "evidence" not in reviewer_search["results"][0]

    profile = build_company_industry_profile(
        {"company_id": "00506.HK", "industry_keys": [INDUSTRY_KEY]}, knowledge_dir=library,
    )
    assert profile["mechanisms"] == []
    context = read_industry_knowledge_context(
        "00506.HK", industry_keys=[INDUSTRY_KEY], knowledge_dir=library,
    )
    assert context["research_questions"] == []


def test_retired_mechanism_is_not_a_default_prior(tmp_path):
    library = tmp_path / "industry"
    candidate = _candidate("IKC:retired", "group-a", "FY2024")
    assert write_industry_insight_candidate(candidate, knowledge_dir=library)["written"] is True
    retired = _mechanism("RETIRED", ["IKC:retired"])
    retired["lifecycle_reason"] = "后续官方披露显示原机制只适用于已取消的监管安排。"
    assert review_industry_mechanism(retired, knowledge_dir=library)["written"] is True

    default_search = search_industry_knowledge(
        industry_keys=[INDUSTRY_KEY], knowledge_dir=library,
    )
    assert default_search["results"] == []
    historical_search = search_industry_knowledge(
        industry_keys=[INDUSTRY_KEY], statuses=["RETIRED"], knowledge_dir=library,
    )
    assert historical_search["results"][0]["status"] == "RETIRED"


def test_ready_card_is_not_returned_without_a_company_industry_or_mechanism_match(tmp_path):
    library = tmp_path / "industry"
    ids = ["IKC:a", "IKC:b", "IKC:c"]
    for candidate in (
        _candidate(ids[0], "group-a", "FY2023"),
        _candidate(ids[1], "group-b", "FY2024"),
        _candidate(ids[2], "group-c", "FY2025"),
    ):
        write_industry_insight_candidate(candidate, knowledge_dir=library)
    review_industry_mechanism(_mechanism("MECHANISM_READY", ids), knowledge_dir=library)
    profile = build_company_industry_profile("UNKNOWN", knowledge_dir=library)
    assert profile["mechanisms"] == []
    assert "company_industry_or_mechanism_keys_missing" in profile["warnings"]


def test_output_directory_metadata_can_build_an_end_to_end_profile(tmp_path):
    library = tmp_path / "industry"
    ids = ["IKC:a", "IKC:b"]
    for candidate, group in zip(ids, ("group-a", "group-b"), strict=True):
        assert write_industry_insight_candidate(
            _candidate(candidate, group, "FY2025"), knowledge_dir=library,
        )["written"] is True
    assert review_industry_mechanism(_mechanism("MECHANISM_READY", ids), knowledge_dir=library)["written"] is True

    output = tmp_path / "output"; output.mkdir()
    (output / "analysis_contract.json").write_text(json.dumps({
        "ts_code": "00506.HK", "industry_classification": {"l2": "食品饮料"},
    }, ensure_ascii=False), encoding="utf-8")
    (output / "industry_context.json").write_text(json.dumps({
        "meta": {"industry_group": "饮料装瓶"},
    }, ensure_ascii=False), encoding="utf-8")
    (output / "company_archetype.json").write_text(json.dumps({
        "primary_archetype": {"archetype_id": "mature_cash_return"}, "secondary_archetypes": [],
    }, ensure_ascii=False), encoding="utf-8")
    (output / "decisive_question_plan.json").write_text(json.dumps({
        "report_id": "00506.HK", "selected_questions": [{"mechanism_key": MECHANISM_KEY}],
    }, ensure_ascii=False), encoding="utf-8")
    profile = build_company_industry_profile(output, knowledge_dir=library)
    assert profile["company_id"] == "00506.HK"
    assert profile["industry_keys"] == [INDUSTRY_KEY]
    assert profile["mechanism_keys"] == [MECHANISM_KEY]
    assert profile["source_metadata"]["source_metadata_files"] == [
        "analysis_contract.json", "industry_context.json", "company_archetype.json", "decisive_question_plan.json",
    ]
    assert profile["mechanisms"][0]["mechanism_key"] == MECHANISM_KEY


def test_library_validation_and_schema_are_parseable_without_hash_contracts(tmp_path):
    library = tmp_path / "industry"
    result = validate_industry_knowledge(library)
    assert result["state"] == "REVIEWABLE"
    assert result["summary"] == {"candidate_count": 0, "mechanism_count": 0, "mechanism_ready_count": 0}
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas" / "industry_knowledge.schema.json").read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$defs"]["mechanism"]["properties"]["status"]["enum"] == ["CANDIDATE", "CORROBORATED", "MECHANISM_READY", "RETIRED", "REJECTED"]


def test_environment_override_is_respected(monkeypatch, tmp_path):
    custom = tmp_path / "custom-library"
    monkeypatch.setenv("TURTLE_INDUSTRY_KNOWLEDGE_DIR", str(custom))
    result = initialize_industry_knowledge()
    assert result["knowledge_dir"] == str(custom)
    assert (custom / "policy.json").is_file()
