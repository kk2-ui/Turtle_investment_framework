from copy import deepcopy

from scripts.enterprise_underwriting_training import build_training_contract
from scripts.staged_judgment_training import (
    J0_SCHEMA,
    J1_SCHEMA,
    J2_SCHEMA,
    compile_stages,
    render_stage_task,
    validate_stage,
)


def _contract():
    return build_training_contract(
        contract_id="STAGED:TEST:BLIND",
        training_track="BLIND_REPLAY",
        company_id="CN:TEST",
        company_name="测试公司",
        cutoff_at="2018-12-31T23:59:59+08:00",
        allowed_sources=[{
            "source_id": "S1",
            "source_ref": "SRC:TEST",
            "available_at": "2018-12-01T00:00:00+08:00",
            "time_role": "PRE_CUTOFF",
        }],
        feedback_clocks=[
            {
                "clock_id": "EARLY",
                "horizon": "EARLY_SIGNAL",
                "opens_at": "2019-12-31T23:59:59+08:00",
                "episode_claims": ["INDUSTRY_AND_SITUATION"],
                "discriminating_observation": "早期经营信号",
            },
            {
                "clock_id": "CASH",
                "horizon": "NORMALIZATION_AND_CASH",
                "opens_at": "2020-12-31T23:59:59+08:00",
                "episode_claims": ["NORMAL_EARNINGS", "OWNER_CASH"],
                "discriminating_observation": "正常盈利和现金转换",
            },
        ],
    )


def _claim(surface, direction="MIXED"):
    return {
        "claim_id": "CLAIM:" + surface,
        "surface": surface,
        "statement": "该经济面按责任匹配证据处理。",
        "direction": direction,
        "mechanism": "经营变化经同一责任边界传导。",
        "treatment": "CONDITIONALLY_UNDERWRITE",
        "evidence_ids": ["E1"],
        "strongest_rival": "恢复路径可能强于当前判断。",
        "reversal_observations": ["后续披露显示量价和现金转换改善。"],
        "unknown": None,
    }


def _stages():
    base = {
        "ledger_id": "CN:TEST:20181231:STAGED",
        "company_id": "CN:TEST",
        "company_name": "测试公司",
        "cutoff_at": "2018-12-31T23:59:59+08:00",
        "sample_identity": "BLIND_REPLAY",
    }
    j0 = {
        "schema_version": J0_SCHEMA,
        "stage": "J0",
        "stage_id": "J0:TEST",
        **base,
        "decision_frame": "判断企业经营与现金能否持续。",
        "underwriting_route": "MATURE_CORE",
        "industry_company_questions": ["需求、竞争和资本责任如何传导到普通股现金？"],
        "components": [{
            "component_id": "CORE",
            "economic_scope": "MATURE_CORE_NORMAL_EARNINGS",
            "question": "核心业务能否保持正常盈利？",
            "evidence_ids": ["E1"],
        }],
        "evidence_refs": [{
            "evidence_id": "E1",
            "source_ref": "SRC:TEST",
            "locator": "年报第 10 页",
            "scope": "CN:TEST 合并经营",
            "used_for": "经营与现金事实",
        }],
    }
    component = {
        "component_id": "CORE",
        "economic_scope": "MATURE_CORE_NORMAL_EARNINGS",
        "treatment": "CONDITIONALLY_UNDERWRITE",
        "normal_earnings_use": "CONDITIONAL_RANGE",
        "owner_cash_use": "UNRESOLVED",
        "financing_pressure_effect": "NEUTRAL",
        "permanent_loss_use": "CONDITIONAL_PATH",
        "valuation_use": "CONDITIONAL_PRIMARY_INPUT",
        "valuation_route_bindings": [
            {"route_id": "EPV", "use": "CONDITIONAL_PRIMARY_INPUT"},
            {"route_id": "NO_BASE", "use": "EXCLUDED"},
        ],
        "reason": "核心业务可条件承保。",
        "promotion_test": "量价和单位利润改善。",
        "invalidation_test": "毛利和现金转换持续恶化。",
        "evidence_ids": ["E1"],
    }
    j1 = {
        "schema_version": J1_SCHEMA,
        "stage": "J1",
        "stage_id": "J1:TEST",
        **base,
        "components": [component],
        "claims": [_claim(surface) for surface in ("SURVIVAL", "BUSINESS_POSITION", "ADAPTATION", "NORMALIZATION", "PERMANENT_LOSS", "VALUE_ROUTE")],
    }
    industry = {
        "horizon": "未来三年",
        "most_likely_regime": "需求温和变化，利润池向效率更高者集中。",
        "profit_pool_transmission": "价格和利用率先影响利润，再影响回款与资本责任。",
        "company_exposure": "公司暴露于核心产品价格和渠道回款。",
        "adaptation": "公司通过产品和渠道调整应对。",
        "normal_economics": "正常盈利按中周期范围处理。",
        "permanent_loss": "低回报资本投入可能造成慢性损失。",
        "valuation_treatment": "以核心 EPV 为主，未证实选项保留条件处理。",
        "strongest_rival": "需求恢复和竞争缓和可能使盈利高于当前判断。",
    }
    j2 = {
        "schema_version": J2_SCHEMA,
        "stage": "J2",
        "stage_id": "J2:TEST",
        **base,
        "industry_future": industry,
        "claims": [_claim("INDUSTRY_FUTURE"), _claim("INVESTMENT_TREATMENT", "NONE")],
        "reversal_observations": ["后续披露显示量价和现金转换改善。"],
        "monitoring": "跟踪量价、毛利、应收周转和经营现金。",
    }
    return j0, j1, j2


def test_three_stage_compile_projects_only_after_each_stage_is_valid():
    contract = _contract()
    j0, j1, j2 = _stages()
    assert validate_stage("J0", j0, contract)["state"] == "REVIEWABLE"
    assert validate_stage("J1", j1, contract)["state"] == "REVIEWABLE"
    assert validate_stage("J2", j2, contract)["state"] == "REVIEWABLE"
    result = compile_stages(contract, j0, j1, j2)
    assert result["state"] == "COMPILED"
    assert result["episode"]["schema_version"] == "enterprise-underwriting-episode.v2"
    assert result["episode"]["component_decisions"][0]["component_id"] == "CORE"


def test_stage_price_or_bad_source_is_rejected_without_compilation():
    contract = _contract()
    j0, j1, j2 = _stages()
    bad = deepcopy(j0)
    bad["price"] = 10
    assert validate_stage("J0", bad, contract)["state"] == "INVALID"
    bad = deepcopy(j0)
    bad["evidence_refs"][0]["source_ref"] = "SRC:OTHER"
    assert validate_stage("J0", bad, contract)["state"] == "INVALID"
    assert compile_stages(contract, bad, j1, j2)["episode"] is None


def test_compile_rejects_j1_scope_change_and_stage_cardinality_or_enum_errors():
    contract = _contract(); j0, j1, j2 = _stages()
    changed = deepcopy(j1)
    changed["components"][0]["economic_scope"] = "SURVIVAL_FINANCING"
    assert compile_stages(contract, j0, changed, j2)["state"] == "DIAGNOSTIC_ONLY"
    bad_j1 = deepcopy(j1)
    bad_j1["claims"].append(deepcopy(bad_j1["claims"][0]))
    assert validate_stage("J1", bad_j1, contract)["state"] == "INVALID"
    bad_j2 = deepcopy(j2)
    bad_j2["claims"][0]["direction"] = "INVALID"
    assert validate_stage("J2", bad_j2, contract)["state"] == "INVALID"
    bad_j2 = deepcopy(j2)
    bad_j2["industry_future"]["action"] = "BUY"
    assert validate_stage("J2", bad_j2, contract)["state"] == "INVALID"


def test_later_stage_requires_accepted_prior_stage():
    contract = _contract()
    j0, j1, _ = _stages()
    bad_j0 = deepcopy(j0)
    bad_j0["cutoff_at"] = "2019-01-01T00:00:00+08:00"
    try:
        render_stage_task(contract, "J1", j0=bad_j0)
    except ValueError as exc:
        assert "prior_stage_not_accepted:J0" in str(exc)
    else:
        raise AssertionError("J1 task rendered from an unaccepted J0")
    # The synthetic contract intentionally has no local source artifact; the
    # prior-stage guard fires before source loading, which is the behavior under test.
    try:
        render_stage_task(contract, "J2", j0=j0, j1={})
    except ValueError as exc:
        assert "prior_stage_not_accepted:J1" in str(exc)
    else:
        raise AssertionError("J2 task rendered from an unaccepted J1")
