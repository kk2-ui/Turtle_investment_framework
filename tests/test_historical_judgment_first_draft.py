from copy import deepcopy

from scripts.historical_judgment_first_draft import (
    DRAFT_SCHEMA_VERSION,
    FEEDBACK_SCHEMA_VERSION,
    compile_feedback_verdict,
    forecaster_contract,
    validate_postoutcome_feedback,
    validate_preoutcome_draft,
)


def _action(scope: str = "CORE") -> dict:
    return {
        "action_family": "CUSTOMER_ABSORPTION",
        "target_scope": scope,
        "fact_or_metric": "同口径终端销量、价格和渠道库存",
        "decision_axis": "核心需求是否真实吸收",
        "positive_effect": "维持正常盈利处理",
        "negative_effect": "有观察到的经济恶化时下调正常盈利",
    }


def _snapshot() -> dict:
    return {
        "management_execution": {
            "treatment_code": "CONDITIONAL_CREDIT",
            "rationale": "执行证据正面，但客户吸收仍待观察。",
        },
        "normal_earnings": {
            "treatment_code": "UNCHANGED",
            "rationale": "收入、持续费用和经常经营利润尚未共同改善。",
        },
        "owner_cash": {
            "treatment_code": "DO_NOT_COUNT",
            "rationale": "集团现金代理尚未闭合NCI与母公司上划。",
        },
        "permanent_loss": {
            "treatment_code": "MAINTAIN_CONSTRAINT",
            "rationale": "当前风险载体没有解除。",
        },
        "valuation_direction": {
            "treatment_code": "UNCHANGED",
            "rationale": "内在价值方向维持，不依赖市场价格。",
        },
        "next_research_action": _action(),
    }


def _draft() -> dict:
    judgments = []
    for rank, topic in enumerate(("核心需求", "现金转换", "资本配置"), start=1):
        judgments.append(
            {
                "rank": rank,
                "current_judgment": f"{topic}当前为有条件成立，而不是未知。",
                "causal_mechanism": f"{topic}通过客户、单位经济和现金链传导。",
                "strongest_counterargument": f"{topic}也可能由周期或口径变化解释。",
                "investment_implication": f"{topic}只改变对应处理轴。",
                "flip_facts": [f"同责任边界的{topic}指标出现材料反转"],
            }
        )
    return {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "episode_id": "HIST:CN000001:20240501:FY2024",
        "company_id": "CN:000001",
        "cutoff_at": "2024-05-01T00:00:00+08:00",
        "outcome_state": "SEALED_NOT_IN_PACKET",
        "enterprise_view": "公司有真实核心需求，但现金尚未闭合，因此只承保经营而不承保股东现金。",
        "most_important_enterprise_judgments": judgments,
        "scenario_analysis": {
            "optimistic": {
                "operating_path": "终端量价同升，现金转换闭合。",
                "investment_effect": "上调正常盈利，但只在现金轴闭合后计入owner cash。",
                "discriminating_facts": ["量价同升且渠道库存稳定"],
            },
            "base": {
                "operating_path": "核心守成，新业务仍为条件性期权。",
                "investment_effect": "维持当前处理和较高安全边际。",
                "discriminating_facts": ["核心收入与毛利稳定"],
            },
            "pessimistic": {
                "operating_path": "终端走弱且库存累积，现金转换恶化。",
                "investment_effect": "下调正常盈利并收紧永久损失约束。",
                "discriminating_facts": ["销量、毛利和现金同步恶化"],
            },
        },
        "material_treatment_snapshot": _snapshot(),
        "outcome_cells": [
            {
                "cell_id": "CORE_ABSORPTION",
                "direct_axes": [
                    "management_execution",
                    "normal_earnings",
                    "valuation_direction",
                    "next_research_action",
                ],
                "preserved_axes": ["owner_cash", "permanent_loss"],
                "direct_axis_links": {
                    "management_execution": "客户吸收直接检验管理层商业执行。",
                    "normal_earnings": "销量、单位经济与持续费用共同传导至经常经营利润。",
                    "valuation_direction": "经常经营利润改变内在价值方向。",
                    "next_research_action": "结果决定下一单位研究预算投向。",
                },
                "preserved_axis_reasons": {
                    "owner_cash": "该cell没有结算现金转换、NCI与母公司上划。",
                    "permanent_loss": "单期吸收没有直接结算不可逆损失载体。",
                },
                "normal_earnings_bridge": {
                    "revenue_or_volume_metric": "同口径销量与收入",
                    "recurring_profit_metric": "同责任边界经常经营利润率",
                    "persistent_cost_burden_metrics": ["销售及研发费用率"],
                    "nonrecurring_exclusions": ["处置收益和政府补助"],
                },
                "local_input_treatments": {
                    "LOCAL_UNKNOWN": {
                        "axis_updates": {},
                        "next_discriminating_evidence": "取得同口径销量和价格。",
                    },
                    "MEASUREMENT_MISMATCH": {
                        "axis_updates": {},
                        "next_discriminating_evidence": "完成责任边界和期间桥。",
                    },
                },
                "valid_input_first_match": [
                    {
                        "class_id": "ABSORPTION",
                        "economic_direction": "FAVORABLE",
                        "condition": "销量上升且单位经济不恶化",
                        "is_residual": False,
                        "observed_adverse_carriers": [],
                        "axis_updates": {
                            "management_execution": "POSITIVE_CREDIT",
                            "normal_earnings": "RAISE",
                            "valuation_direction": "UP",
                        },
                    },
                    {
                        "class_id": "OBSERVED_EROSION",
                        "economic_direction": "ADVERSE",
                        "condition": "同口径销量下降且毛利率材料恶化",
                        "is_residual": False,
                        "observed_adverse_carriers": ["销量下降", "毛利率材料恶化"],
                        "axis_updates": {
                            "management_execution": "NEGATIVE_CREDIT",
                            "normal_earnings": "LOWER",
                            "valuation_direction": "DOWN",
                        },
                    },
                    {
                        "class_id": "NONDECISIVE_MIXED",
                        "economic_direction": "MIXED",
                        "condition": "ELSE，仅限完整且可比的已观察输入",
                        "is_residual": True,
                        "observed_adverse_carriers": [],
                        "axis_updates": {},
                    },
                ],
            }
        ],
    }


def test_forecaster_contract_declares_machine_readable_root_and_list_fields() -> None:
    exact_shape = forecaster_contract()["exact_output_shape"]

    assert exact_shape["root_required_fields"]["schema_version"] == DRAFT_SCHEMA_VERSION
    assert isinstance(exact_shape["judgment_field_types"]["flip_facts"], list)
    assert isinstance(
        exact_shape["scenario_field_types"]["discriminating_facts"],
        list,
    )


def _feedback() -> dict:
    before = _snapshot()
    after = deepcopy(before)
    after["owner_cash"] = {
        "treatment_code": "COUNT_CONDITIONALLY",
        "rationale": "集团代理转正，但NCI与母公司上划仍未闭合。",
    }
    after["next_research_action"] = _action("CORE_SELL_THROUGH")
    receipt = {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "episode_id": "HIST:CN000001:20240501:FY2024",
        "company_id": "CN:000001",
        "evaluation_design": "SINGLE_ARM_DISCOVERY",
        "treatment_before": before,
        "treatment_after": after,
        "settlement_summary": {
            "diagnostic_cell_ids": ["CORE_ABSORPTION"],
            "local_unknown_cell_ids": [],
            "mismatch_cell_ids": [],
        },
    }
    receipt["verdict"] = compile_feedback_verdict(receipt)
    return receipt


def test_valid_first_draft_prioritizes_judgment_and_localizes_unknown() -> None:
    assert validate_preoutcome_draft(_draft()) == []


def test_three_operating_scenarios_are_required_in_the_first_draft() -> None:
    draft = _draft()
    del draft["scenario_analysis"]["pessimistic"]
    assert "judgment_first.scenario_analysis.pessimistic_missing" in validate_preoutcome_draft(
        draft
    )


def test_adverse_residual_else_is_rejected() -> None:
    draft = _draft()
    residual = draft["outcome_cells"][0]["valid_input_first_match"][-1]
    residual["economic_direction"] = "ADVERSE"
    residual["observed_adverse_carriers"] = ["未达到正类"]
    findings = validate_preoutcome_draft(draft)
    assert any("residual_cannot_be_directional" in item for item in findings)
    assert any("adverse_cannot_be_else" in item for item in findings)


def test_adverse_class_requires_observed_economic_carrier() -> None:
    draft = _draft()
    draft["outcome_cells"][0]["valid_input_first_match"][1][
        "observed_adverse_carriers"
    ] = []
    assert any(
        "adverse_requires_observed_carrier" in item for item in validate_preoutcome_draft(draft)
    )


def test_unknown_and_mismatch_cannot_downgrade_treatment() -> None:
    draft = _draft()
    draft["outcome_cells"][0]["local_input_treatments"]["LOCAL_UNKNOWN"][
        "axis_updates"
    ] = {"normal_earnings": "LOWER"}
    findings = validate_preoutcome_draft(draft)
    assert "judgment_first.outcome_cells[0].local_unknown_must_not_change_treatment" in findings


def test_cell_cannot_update_an_undeclared_axis() -> None:
    draft = _draft()
    draft["outcome_cells"][0]["valid_input_first_match"][0]["axis_updates"][
        "permanent_loss"
    ] = "RELAX_CONSTRAINT"
    assert any("cross_axis_update_forbidden" in item for item in validate_preoutcome_draft(draft))


def test_preserved_axes_are_the_exact_non_propagation_boundary() -> None:
    draft = _draft()
    draft["outcome_cells"][0]["preserved_axes"] = ["owner_cash"]
    assert any(
        "preserved_axes_must_be_exact_complement" in item
        for item in validate_preoutcome_draft(draft)
    )


def test_each_direct_and_preserved_axis_requires_an_economic_reason() -> None:
    draft = _draft()
    del draft["outcome_cells"][0]["direct_axis_links"]["normal_earnings"]
    del draft["outcome_cells"][0]["preserved_axis_reasons"]["owner_cash"]
    findings = validate_preoutcome_draft(draft)
    assert any("direct_axis_links_must_match_direct_axes" in item for item in findings)
    assert any("preserved_axis_reasons_must_match_preserved_axes" in item for item in findings)


def test_normal_earnings_requires_recurring_profit_and_cost_bridge() -> None:
    draft = _draft()
    del draft["outcome_cells"][0]["normal_earnings_bridge"]
    assert any("normal_earnings_bridge_missing" in item for item in validate_preoutcome_draft(draft))


def _adjusted_profit_schedule() -> dict:
    return {
        "scope_id": "SEGMENT:CORE",
        "baseline_period": "FY2023",
        "schedule_status": "FROZEN_PREOUTCOME",
        "reported_segment_profit": 120.0,
        "baseline_revenue": 1000.0,
        "adjusted_recurring_profit": 110.0,
        "adjusted_recurring_margin": 0.11,
        "capital_expenditure": 25.0,
        "depreciation_amortization": 10.0,
        "asset_impairment": 2.0,
        "capital_burden_denominator": 110.0,
        "source_refs": ["FY2023.pdf p100"],
        "adjustment_schedule": [
            {
                "item": "one-off disposal gain",
                "amount_removed_from_reported_profit": 10.0,
                "treatment": "REMOVE_FROM_RECURRING",
                "source_ref": "FY2023.pdf p101",
                "rationale": "处置不属于持续经营利润。",
            }
        ],
    }


def test_relative_adjusted_profit_threshold_requires_frozen_reconciled_baseline() -> None:
    draft = _draft()
    bridge = draft["outcome_cells"][0]["normal_earnings_bridge"]
    bridge["uses_adjusted_relative_thresholds"] = True
    bridge["required_adjusted_profit_scope_ids"] = ["SEGMENT:CORE"]
    findings = validate_preoutcome_draft(draft)
    assert any("baseline_adjusted_profit_schedules_missing" in item for item in findings)

    bridge["baseline_adjusted_profit_schedules"] = [_adjusted_profit_schedule()]
    assert validate_preoutcome_draft(draft) == []


def test_adjusted_profit_baseline_mutation_is_rejected_before_outcome_access() -> None:
    draft = _draft()
    bridge = draft["outcome_cells"][0]["normal_earnings_bridge"]
    bridge["uses_adjusted_relative_thresholds"] = True
    bridge["required_adjusted_profit_scope_ids"] = ["SEGMENT:CORE"]
    bridge["baseline_adjusted_profit_schedules"] = [_adjusted_profit_schedule()]

    del bridge["baseline_adjusted_profit_schedules"][0]["source_refs"]
    assert any("source_refs_missing" in item for item in validate_preoutcome_draft(draft))

    bridge["baseline_adjusted_profit_schedules"][0]["source_refs"] = ["FY2023.pdf p100"]
    bridge["baseline_adjusted_profit_schedules"][0]["adjusted_recurring_profit"] = 112.0
    findings = validate_preoutcome_draft(draft)
    assert any("adjusted_profit_not_reconciled" in item for item in findings)


def test_all_declared_adjusted_profit_scopes_are_required() -> None:
    draft = _draft()
    bridge = draft["outcome_cells"][0]["normal_earnings_bridge"]
    bridge["uses_adjusted_relative_thresholds"] = True
    bridge["required_adjusted_profit_scope_ids"] = ["SEGMENT:CORE", "SEGMENT:SECOND"]
    bridge["baseline_adjusted_profit_schedules"] = [_adjusted_profit_schedule()]
    assert any(
        "baseline_adjusted_profit_scopes_incomplete" in item
        for item in validate_preoutcome_draft(draft)
    )


def test_group_cash_proxy_needs_future_nci_and_parent_access_closure() -> None:
    draft = _draft()
    cell = draft["outcome_cells"][0]
    cell["direct_axes"].append("owner_cash")
    cell["preserved_axes"].remove("owner_cash")
    cell["direct_axis_links"]["owner_cash"] = "经营现金扣资本开支形成集团现金代理。"
    del cell["preserved_axis_reasons"]["owner_cash"]
    cell["owner_cash_bridge"] = {
        "cash_proxy_scope": "GROUP",
        "nci_scope": "OPEN",
        "parent_access": "UNKNOWN",
        "capex_treatment": "扣除全部长期资产购置现金",
    }
    cell["valid_input_first_match"][0]["axis_updates"][
        "owner_cash"
    ] = "COUNT_IN_PARENT_OWNER_CASH"
    findings = validate_preoutcome_draft(draft)
    assert any("parent_owner_cash_scope_requirements_missing" in item for item in findings)

    cell["valid_input_first_match"][0]["scope_requirements"] = {
        "required_nci_scope_at_settlement": ["CLOSED", "IMMATERIAL_WITH_EVIDENCE"],
        "required_parent_access_at_settlement": "EVIDENCED",
    }
    assert not any(
        "parent_owner_cash" in item for item in validate_preoutcome_draft(draft)
    )


def test_permanent_loss_direct_axis_requires_materiality_and_reversibility_bridge() -> None:
    draft = _draft()
    cell = draft["outcome_cells"][0]
    cell["direct_axes"].append("permanent_loss")
    cell["preserved_axes"].remove("permanent_loss")
    cell["direct_axis_links"]["permanent_loss"] = "持续现金吞噬可成为永久损失载体。"
    del cell["preserved_axis_reasons"]["permanent_loss"]
    assert any("permanent_loss_bridge_missing" in item for item in validate_preoutcome_draft(draft))

    cell["permanent_loss_bridge"] = {
        "risk_carrier": "必要维持性资本持续吞噬现金或主要现金长期无法上划",
        "materiality_or_persistence_test": "连续期间且覆盖材料现金规模",
        "reversibility_test": "单年可逆营运资金波动不触发",
    }
    assert not any("permanent_loss_bridge" in item for item in validate_preoutcome_draft(draft))


def test_unknown_is_not_an_allowed_investment_treatment() -> None:
    draft = _draft()
    draft["material_treatment_snapshot"]["owner_cash"]["treatment_code"] = "UNKNOWN"
    assert "judgment_first.material_treatment_snapshot.owner_cash_invalid" in validate_preoutcome_draft(
        draft
    )


def test_material_owner_cash_and_rank_one_action_change_cannot_be_erased() -> None:
    receipt = _feedback()
    receipt["verdict"]["enterprise_investment_treatment"] = "NO_MATERIAL_UPDATE"
    findings = validate_postoutcome_feedback(receipt)
    assert "judgment_feedback.enterprise_investment_treatment_inconsistent" in findings


def test_single_arm_material_update_does_not_create_method_utility() -> None:
    receipt = _feedback()
    assert receipt["verdict"] == {
        "real_feedback_turn": "COMPLETED",
        "enterprise_investment_treatment": "MATERIAL_UPDATE_BOUNDED",
        "materially_changed_axes": ["owner_cash", "next_research_action"],
        "method_learning_utility": "NOT_APPLICABLE",
    }
    assert validate_postoutcome_feedback(receipt) == []


def test_wording_or_metric_precision_alone_is_not_material_treatment_change() -> None:
    receipt = _feedback()
    receipt["treatment_after"] = deepcopy(receipt["treatment_before"])
    receipt["treatment_after"]["next_research_action"][
        "fact_or_metric"
    ] = "更精确的同口径终端销量、价格、库存和复购"
    receipt["verdict"] = compile_feedback_verdict(receipt)
    assert receipt["verdict"]["enterprise_investment_treatment"] == "NO_MATERIAL_UPDATE"
    assert receipt["verdict"]["materially_changed_axes"] == []
    assert validate_postoutcome_feedback(receipt) == []


def test_reviewer_cannot_invent_material_update_when_treatments_are_equal() -> None:
    receipt = _feedback()
    receipt["treatment_after"] = deepcopy(receipt["treatment_before"])
    receipt["verdict"] = {
        "real_feedback_turn": "COMPLETED",
        "enterprise_investment_treatment": "MATERIAL_UPDATE_BOUNDED",
        "materially_changed_axes": ["normal_earnings"],
        "method_learning_utility": "NOT_APPLICABLE",
    }
    findings = validate_postoutcome_feedback(receipt)
    assert "judgment_feedback.enterprise_investment_treatment_inconsistent" in findings
    assert "judgment_feedback.materially_changed_axes_inconsistent" in findings


def test_local_unknown_does_not_cancel_a_completed_feedback_turn() -> None:
    receipt = _feedback()
    receipt["settlement_summary"]["local_unknown_cell_ids"] = ["OWNER_CASH_DETAIL"]
    receipt["verdict"] = compile_feedback_verdict(receipt)
    assert receipt["verdict"]["real_feedback_turn"] == "COMPLETED"
    assert validate_postoutcome_feedback(receipt) == []
