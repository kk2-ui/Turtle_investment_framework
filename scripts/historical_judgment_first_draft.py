#!/usr/bin/env python3
"""Local first-draft contract for historical enterprise-judgment training.

This module does not decide whether a company is admissible and does not add a
global research gate.  It records what the forecaster actually thinks before
the outcome is opened, prevents a local missing field from becoming an
economic deterioration, and keeps post-outcome feedback separate from method
utility.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DRAFT_SCHEMA_VERSION = "historical-judgment-first-draft.v1"
FEEDBACK_SCHEMA_VERSION = "historical-judgment-feedback.v1"

TREATMENT_CODES: dict[str, set[str]] = {
    "management_execution": {
        "POSITIVE_CREDIT",
        "CONDITIONAL_CREDIT",
        "NEGATIVE_CREDIT",
        "NO_CREDIT_ASSIGNED",
    },
    "normal_earnings": {"RAISE", "UNCHANGED", "LOWER", "EXCLUDE_COMPONENT"},
    "owner_cash": {
        "COUNT_IN_PARENT_OWNER_CASH",
        "COUNT_CONDITIONALLY",
        "DO_NOT_COUNT",
    },
    "permanent_loss": {
        "RELAX_CONSTRAINT",
        "MAINTAIN_CONSTRAINT",
        "TIGHTEN_CONSTRAINT",
        "THESIS_BLOCKING",
    },
    "valuation_direction": {"UP", "UNCHANGED", "DOWN", "WITHHELD"},
}
TREATMENT_AXES = tuple(TREATMENT_CODES)
ALL_AXES = TREATMENT_AXES + ("next_research_action",)
ACTION_FIELDS = (
    "action_family",
    "target_scope",
    "fact_or_metric",
    "decision_axis",
    "positive_effect",
    "negative_effect",
)
MATERIAL_ACTION_FIELDS = ("action_family", "target_scope", "decision_axis")
ECONOMIC_DIRECTIONS = {"FAVORABLE", "NEUTRAL", "MIXED", "ADVERSE"}
LOCAL_INPUT_STATES = {"LOCAL_UNKNOWN", "MEASUREMENT_MISMATCH"}


def forecaster_contract() -> dict[str, Any]:
    """Return the contract embedded in each fresh forecaster packet."""

    return {
        "contract_version": DRAFT_SCHEMA_VERSION,
        "objective": (
            "在证据不完美但结果仍封存时，先形成当前最合理、可反驳、对投资有用的企业判断；"
            "outcome cells 只负责未来检验这些判断。"
        ),
        "required_product": {
            "enterprise_view": "一段当前整体判断，不得以资料不足或待披露代替",
            "most_important_enterprise_judgments": {
                "count": 3,
                "required_fields": [
                    "current_judgment",
                    "causal_mechanism",
                    "strongest_counterargument",
                    "investment_implication",
                    "flip_facts",
                ],
            },
            "scenario_analysis": {
                "required_scenarios": ["optimistic", "base", "pessimistic"],
                "required_fields": [
                    "operating_path",
                    "investment_effect",
                    "discriminating_facts",
                ],
                "rule": "情景是经营路径，不是把同一结论换成高/中/低三个形容词。",
            },
            "material_treatment_snapshot": {
                "axes": list(ALL_AXES),
                "allowed_treatment_codes": {
                    axis: sorted(codes) for axis, codes in TREATMENT_CODES.items()
                },
                "rule": (
                    "UNKNOWN不是投资处理。证据不足时仍须写明当前是排除、条件计入、维持约束或暂缓估值方向。"
                ),
                "valuation_direction_rule": (
                    "这里判断的是内在价值相对共同参考状态的方向，不是市场价格、正式估值或BuyBand；"
                    "缺少价格本身不能成为WITHHELD的理由。"
                ),
            },
        },
        "economic_bridge_rules": [
            "合并OCF减资本开支只能称GROUP_CASH_PROXY；NCI归属与母公司上划能力未闭合时，最多COUNT_CONDITIONALLY。",
            "收入和毛利率不能单独RAISE或LOWER normal earnings；必须消费同责任边界的持续费用负担与经常经营利润或利润率。",
            "direct_axes不是越少越好。列入机制真实能改变的轴，并逐轴写direct_axis_links；未列入轴逐轴说明preserved_axis_reasons。",
            "单年可逆现金波动只更新owner cash；材料且持续的维持性现金吞噬或结构性上划阻断同时是permanent-loss载体，必须预设severe分支。",
        ],
        "outcome_cell_rules": [
            "先声明direct_axes；cell只能改这些轴，其他轴列入preserved_axes。",
            "LOCAL_UNKNOWN与MEASUREMENT_MISMATCH必须在数值分类之前局部结算，且axis_updates必须为空。",
            "ADVERSE只可由明确、已观察的负面经济载体触发；不得把ELSE、未披露或不可比写成恶化。",
            "完整可比输入的剩余补集只能是NEUTRAL或MIXED，不得是ADVERSE。",
            "单轴改善或恶化不得自动传播到owner cash、永久损失或估值方向。",
        ],
        "postoutcome_rules": [
            "分别结算REAL_FEEDBACK_TURN、ENTERPRISE_INVESTMENT_TREATMENT、METHOD_LEARNING_UTILITY。",
            "owner-cash等处理代码改变，或rank-1研究行动的family/scope/decision-axis改变，属于材料处理变化。",
            "单臂真实反馈可以改变企业处理，但不能据此声称方法效用。",
            "字段更多、文字更完整、概率更准或reviewer更积极均不构成方法效用。",
        ],
        "exact_output_shape": {
            "root_required_fields": {
                "schema_version": DRAFT_SCHEMA_VERSION,
                "episode_id": "...",
                "company_id": "...",
                "cutoff_at": "...",
                "outcome_state": "SEALED_NOT_IN_PACKET",
                "enterprise_view": "...",
            },
            "judgment_field_types": {
                "flip_facts": ["至少一项可观察、可反驳的翻转事实"],
            },
            "scenario_field_types": {
                "discriminating_facts": ["至少一项可区分经营路径的事实"],
            },
            "material_treatment_snapshot": {
                axis: {"treatment_code": f"ONE_OF_ALLOWED_{axis.upper()}", "rationale": "..."}
                for axis in TREATMENT_AXES
            }
            | {
                "next_research_action": {
                    "action_family": "...",
                    "target_scope": "...",
                    "fact_or_metric": "...",
                    "decision_axis": "...",
                    "positive_effect": "...",
                    "negative_effect": "...",
                }
            },
            "outcome_cell_required_fields": [
                "cell_id",
                "direct_axes",
                "preserved_axes",
                "direct_axis_links",
                "preserved_axis_reasons",
                "local_input_treatments",
                "valid_input_first_match",
            ],
            "conditional_cell_bridges": {
                "when_normal_earnings_is_direct": {
                    "normal_earnings_bridge": {
                        "revenue_or_volume_metric": "...",
                        "recurring_profit_metric": "...",
                        "persistent_cost_burden_metrics": ["..."],
                        "nonrecurring_exclusions": ["..."],
                    }
                },
                "when_owner_cash_is_direct": {
                    "owner_cash_bridge": {
                        "cash_proxy_scope": "GROUP_OR_PARENT",
                        "nci_scope": "CLOSED_OR_OPEN_OR_IMMATERIAL_WITH_EVIDENCE",
                        "parent_access": "EVIDENCED_OR_UNKNOWN_OR_BLOCKED",
                        "capex_treatment": "...",
                    }
                },
                "when_permanent_loss_is_direct": {
                    "permanent_loss_bridge": {
                        "risk_carrier": "...",
                        "materiality_or_persistence_test": "...",
                        "reversibility_test": "...",
                    }
                },
            },
            "valid_input_first_match_item": {
                "class_id": "...",
                "economic_direction": "FAVORABLE_OR_NEUTRAL_OR_MIXED_OR_ADVERSE",
                "condition": "...",
                "is_residual": False,
                "observed_adverse_carriers": [],
                "axis_updates": {},
                "scope_requirements": {
                    "required_nci_scope_at_settlement": [
                        "CLOSED",
                        "IMMATERIAL_WITH_EVIDENCE",
                    ],
                    "required_parent_access_at_settlement": "EVIDENCED",
                },
            },
            "local_input_treatments": {
                "LOCAL_UNKNOWN": {
                    "axis_updates": {},
                    "next_discriminating_evidence": "...",
                },
                "MEASUREMENT_MISMATCH": {
                    "axis_updates": {},
                    "next_discriminating_evidence": "...",
                },
            },
        },
    }


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_adjusted_profit_baselines(
    bridge: dict[str, Any], prefix: str, findings: list[str]
) -> None:
    """Bind relative adjusted-profit thresholds to a pre-outcome denominator.

    This is opt-in: existing cases that do not use adjusted relative thresholds
    are unchanged.  Once a case declares that treatment, the result custodian
    must not be left to invent the baseline or its exclusions after reveal.
    """

    if bridge.get("uses_adjusted_relative_thresholds") is not True:
        return
    schedules = bridge.get("baseline_adjusted_profit_schedules")
    if not isinstance(schedules, list) or not schedules:
        findings.append(f"{prefix}.baseline_adjusted_profit_schedules_missing")
        return
    required_scope_ids = bridge.get("required_adjusted_profit_scope_ids")
    if (
        not isinstance(required_scope_ids, list)
        or not required_scope_ids
        or len(required_scope_ids) != len(set(required_scope_ids))
        or not all(_nonempty_text(scope_id) for scope_id in required_scope_ids)
    ):
        findings.append(f"{prefix}.required_adjusted_profit_scope_ids_invalid")
        required_scope_set: set[str] = set()
    else:
        required_scope_set = set(required_scope_ids)
    seen_scopes: set[str] = set()
    numeric_fields = (
        "reported_segment_profit",
        "baseline_revenue",
        "adjusted_recurring_profit",
        "adjusted_recurring_margin",
        "capital_expenditure",
        "depreciation_amortization",
        "asset_impairment",
        "capital_burden_denominator",
    )
    for index, schedule in enumerate(schedules):
        item_prefix = f"{prefix}.baseline_adjusted_profit_schedules[{index}]"
        if not isinstance(schedule, dict):
            findings.append(f"{item_prefix}.must_be_object")
            continue
        scope_id = schedule.get("scope_id")
        if not _nonempty_text(scope_id) or scope_id in seen_scopes:
            findings.append(f"{item_prefix}.scope_id_missing_or_duplicate")
        else:
            seen_scopes.add(scope_id)
        if schedule.get("baseline_period") != "FY2023":
            findings.append(f"{item_prefix}.baseline_period_must_be_fy2023")
        if schedule.get("schedule_status") != "FROZEN_PREOUTCOME":
            findings.append(f"{item_prefix}.schedule_not_frozen_preoutcome")
        for field in numeric_fields:
            if not _finite_number(schedule.get(field)):
                findings.append(f"{item_prefix}.{field}_missing")
        refs = schedule.get("source_refs")
        if not isinstance(refs, list) or not any(_nonempty_text(ref) for ref in refs):
            findings.append(f"{item_prefix}.source_refs_missing")
        adjustments = schedule.get("adjustment_schedule")
        if not isinstance(adjustments, list) or not adjustments:
            findings.append(f"{item_prefix}.adjustment_schedule_missing")
            continue
        removed_total = 0.0
        adjustments_valid = True
        for adjustment_index, adjustment in enumerate(adjustments):
            adjustment_prefix = f"{item_prefix}.adjustment_schedule[{adjustment_index}]"
            if not isinstance(adjustment, dict):
                findings.append(f"{adjustment_prefix}.must_be_object")
                adjustments_valid = False
                continue
            for field in ("item", "treatment", "source_ref", "rationale"):
                if not _nonempty_text(adjustment.get(field)):
                    findings.append(f"{adjustment_prefix}.{field}_missing")
                    adjustments_valid = False
            amount = adjustment.get("amount_removed_from_reported_profit")
            if not _finite_number(amount):
                findings.append(f"{adjustment_prefix}.amount_missing")
                adjustments_valid = False
            else:
                removed_total += float(amount)
        if all(_finite_number(schedule.get(field)) for field in numeric_fields) and adjustments_valid:
            reported = float(schedule["reported_segment_profit"])
            adjusted = float(schedule["adjusted_recurring_profit"])
            revenue = float(schedule["baseline_revenue"])
            expected_adjusted = reported - removed_total
            if abs(adjusted - expected_adjusted) > max(1.0, abs(expected_adjusted) * 1e-9):
                findings.append(f"{item_prefix}.adjusted_profit_not_reconciled")
            expected_margin = adjusted / revenue if revenue else None
            if expected_margin is None or abs(
                float(schedule["adjusted_recurring_margin"]) - expected_margin
            ) > 1e-9:
                findings.append(f"{item_prefix}.adjusted_margin_not_reconciled")
            if abs(float(schedule["capital_burden_denominator"]) - adjusted) > max(
                1.0, abs(adjusted) * 1e-9
            ):
                findings.append(f"{item_prefix}.capital_burden_denominator_not_adjusted_profit")
    if required_scope_set and seen_scopes != required_scope_set:
        findings.append(f"{prefix}.baseline_adjusted_profit_scopes_incomplete")


def _validate_action(action: Any, prefix: str, findings: list[str]) -> None:
    if not isinstance(action, dict):
        findings.append(f"{prefix}.must_be_object")
        return
    for field in ACTION_FIELDS:
        if not _nonempty_text(action.get(field)):
            findings.append(f"{prefix}.{field}_missing")


def _validate_snapshot(snapshot: Any, prefix: str, findings: list[str]) -> None:
    if not isinstance(snapshot, dict):
        findings.append(f"{prefix}.must_be_object")
        return
    for axis, allowed in TREATMENT_CODES.items():
        treatment = snapshot.get(axis)
        if not isinstance(treatment, dict):
            findings.append(f"{prefix}.{axis}_must_include_code_and_rationale")
            continue
        if treatment.get("treatment_code") not in allowed:
            findings.append(f"{prefix}.{axis}_invalid")
        if not _nonempty_text(treatment.get("rationale")):
            findings.append(f"{prefix}.{axis}_rationale_missing")
    _validate_action(snapshot.get("next_research_action"), f"{prefix}.next_research_action", findings)


def validate_preoutcome_draft(draft: dict[str, Any]) -> list[str]:
    """Validate the local judgment product without re-validating its evidence stack."""

    findings: list[str] = []
    if draft.get("schema_version") != DRAFT_SCHEMA_VERSION:
        findings.append("judgment_first.schema_version_invalid")
    for field in ("episode_id", "company_id", "cutoff_at", "enterprise_view"):
        if not _nonempty_text(draft.get(field)):
            findings.append(f"judgment_first.{field}_missing")
    if draft.get("outcome_state") != "SEALED_NOT_IN_PACKET":
        findings.append("judgment_first.outcome_not_sealed")

    judgments = draft.get("most_important_enterprise_judgments")
    if not isinstance(judgments, list) or len(judgments) != 3:
        findings.append("judgment_first.three_prioritized_judgments_required")
    else:
        for index, judgment in enumerate(judgments):
            prefix = f"judgment_first.judgments[{index}]"
            if not isinstance(judgment, dict):
                findings.append(f"{prefix}.must_be_object")
                continue
            for field in (
                "current_judgment",
                "causal_mechanism",
                "strongest_counterargument",
                "investment_implication",
            ):
                if not _nonempty_text(judgment.get(field)):
                    findings.append(f"{prefix}.{field}_missing")
            flip_facts = judgment.get("flip_facts")
            if not isinstance(flip_facts, list) or not any(_nonempty_text(item) for item in flip_facts):
                findings.append(f"{prefix}.flip_facts_missing")

    _validate_snapshot(
        draft.get("material_treatment_snapshot"),
        "judgment_first.material_treatment_snapshot",
        findings,
    )

    scenarios = draft.get("scenario_analysis")
    if not isinstance(scenarios, dict):
        findings.append("judgment_first.scenario_analysis_missing")
    else:
        for name in ("optimistic", "base", "pessimistic"):
            scenario = scenarios.get(name)
            prefix = f"judgment_first.scenario_analysis.{name}"
            if not isinstance(scenario, dict):
                findings.append(f"{prefix}_missing")
                continue
            for field in ("operating_path", "investment_effect"):
                if not _nonempty_text(scenario.get(field)):
                    findings.append(f"{prefix}.{field}_missing")
            facts = scenario.get("discriminating_facts")
            if not isinstance(facts, list) or not any(_nonempty_text(item) for item in facts):
                findings.append(f"{prefix}.discriminating_facts_missing")

    cells = draft.get("outcome_cells")
    if not isinstance(cells, list) or not cells:
        findings.append("judgment_first.outcome_cells_missing")
        return findings

    seen_cells: set[str] = set()
    all_axes = set(ALL_AXES)
    for index, cell in enumerate(cells):
        prefix = f"judgment_first.outcome_cells[{index}]"
        if not isinstance(cell, dict):
            findings.append(f"{prefix}.must_be_object")
            continue
        cell_id = cell.get("cell_id")
        if not _nonempty_text(cell_id) or cell_id in seen_cells:
            findings.append(f"{prefix}.cell_id_missing_or_duplicate")
        else:
            seen_cells.add(cell_id)

        direct_axes = cell.get("direct_axes")
        preserved_axes = cell.get("preserved_axes")
        if not isinstance(direct_axes, list) or not direct_axes or not set(direct_axes) <= all_axes:
            findings.append(f"{prefix}.direct_axes_invalid")
            direct_set: set[str] = set()
        else:
            direct_set = set(direct_axes)
            if len(direct_set) != len(direct_axes):
                findings.append(f"{prefix}.direct_axes_duplicate")
        if not isinstance(preserved_axes, list) or set(preserved_axes) != all_axes - direct_set:
            findings.append(f"{prefix}.preserved_axes_must_be_exact_complement")

        direct_links = cell.get("direct_axis_links")
        if not isinstance(direct_links, dict) or set(direct_links) != direct_set:
            findings.append(f"{prefix}.direct_axis_links_must_match_direct_axes")
        elif any(not _nonempty_text(link) for link in direct_links.values()):
            findings.append(f"{prefix}.direct_axis_link_missing")
        preserved_reasons = cell.get("preserved_axis_reasons")
        if not isinstance(preserved_reasons, dict) or set(preserved_reasons) != all_axes - direct_set:
            findings.append(f"{prefix}.preserved_axis_reasons_must_match_preserved_axes")
        elif any(not _nonempty_text(reason) for reason in preserved_reasons.values()):
            findings.append(f"{prefix}.preserved_axis_reason_missing")

        if "normal_earnings" in direct_set:
            bridge = cell.get("normal_earnings_bridge")
            if not isinstance(bridge, dict):
                findings.append(f"{prefix}.normal_earnings_bridge_missing")
            else:
                for field in ("revenue_or_volume_metric", "recurring_profit_metric"):
                    if not _nonempty_text(bridge.get(field)):
                        findings.append(f"{prefix}.normal_earnings_bridge.{field}_missing")
                for field in ("persistent_cost_burden_metrics", "nonrecurring_exclusions"):
                    values = bridge.get(field)
                    if not isinstance(values, list) or not any(_nonempty_text(value) for value in values):
                        findings.append(f"{prefix}.normal_earnings_bridge.{field}_missing")
                _validate_adjusted_profit_baselines(
                    bridge,
                    f"{prefix}.normal_earnings_bridge",
                    findings,
                )

        owner_cash_bridge = cell.get("owner_cash_bridge") if "owner_cash" in direct_set else None
        if "owner_cash" in direct_set:
            if not isinstance(owner_cash_bridge, dict):
                findings.append(f"{prefix}.owner_cash_bridge_missing")
            else:
                if owner_cash_bridge.get("cash_proxy_scope") not in {"GROUP", "PARENT"}:
                    findings.append(f"{prefix}.owner_cash_bridge.cash_proxy_scope_invalid")
                if owner_cash_bridge.get("nci_scope") not in {
                    "CLOSED",
                    "OPEN",
                    "IMMATERIAL_WITH_EVIDENCE",
                }:
                    findings.append(f"{prefix}.owner_cash_bridge.nci_scope_invalid")
                if owner_cash_bridge.get("parent_access") not in {
                    "EVIDENCED",
                    "UNKNOWN",
                    "BLOCKED",
                }:
                    findings.append(f"{prefix}.owner_cash_bridge.parent_access_invalid")
                if not _nonempty_text(owner_cash_bridge.get("capex_treatment")):
                    findings.append(f"{prefix}.owner_cash_bridge.capex_treatment_missing")

        if "permanent_loss" in direct_set:
            bridge = cell.get("permanent_loss_bridge")
            if not isinstance(bridge, dict):
                findings.append(f"{prefix}.permanent_loss_bridge_missing")
            else:
                for field in (
                    "risk_carrier",
                    "materiality_or_persistence_test",
                    "reversibility_test",
                ):
                    if not _nonempty_text(bridge.get(field)):
                        findings.append(f"{prefix}.permanent_loss_bridge.{field}_missing")

        local = cell.get("local_input_treatments")
        if not isinstance(local, dict) or set(local) != LOCAL_INPUT_STATES:
            findings.append(f"{prefix}.local_input_treatments_invalid")
        else:
            for state in sorted(LOCAL_INPUT_STATES):
                treatment = local[state]
                if not isinstance(treatment, dict):
                    findings.append(f"{prefix}.local_input_treatments.{state}_invalid")
                    continue
                if treatment.get("axis_updates") != {}:
                    findings.append(f"{prefix}.{state.lower()}_must_not_change_treatment")
                if not _nonempty_text(treatment.get("next_discriminating_evidence")):
                    findings.append(f"{prefix}.{state.lower()}_next_evidence_missing")

        classes = cell.get("valid_input_first_match")
        if not isinstance(classes, list) or not classes:
            findings.append(f"{prefix}.valid_input_first_match_missing")
            continue
        residual_indexes = [
            i
            for i, item in enumerate(classes)
            if isinstance(item, dict) and item.get("is_residual") is True
        ]
        if residual_indexes != [len(classes) - 1]:
            findings.append(f"{prefix}.exactly_one_final_residual_required")
        for class_index, classification in enumerate(classes):
            class_prefix = f"{prefix}.valid_input_first_match[{class_index}]"
            if not isinstance(classification, dict):
                findings.append(f"{class_prefix}.must_be_object")
                continue
            if not _nonempty_text(classification.get("class_id")):
                findings.append(f"{class_prefix}.class_id_missing")
            direction = classification.get("economic_direction")
            if direction not in ECONOMIC_DIRECTIONS:
                findings.append(f"{class_prefix}.economic_direction_invalid")
            if not _nonempty_text(classification.get("condition")):
                findings.append(f"{class_prefix}.condition_missing")
            is_residual = classification.get("is_residual") is True
            if is_residual and direction not in {"NEUTRAL", "MIXED"}:
                findings.append(f"{class_prefix}.residual_cannot_be_directional")
            adverse = classification.get("observed_adverse_carriers")
            if direction == "ADVERSE" and (
                not isinstance(adverse, list) or not any(_nonempty_text(item) for item in adverse)
            ):
                findings.append(f"{class_prefix}.adverse_requires_observed_carrier")
            if direction == "ADVERSE" and is_residual:
                findings.append(f"{class_prefix}.adverse_cannot_be_else")

            updates = classification.get("axis_updates")
            if not isinstance(updates, dict):
                findings.append(f"{class_prefix}.axis_updates_must_be_object")
                continue
            if not set(updates) <= direct_set:
                findings.append(f"{class_prefix}.cross_axis_update_forbidden")
            for axis, value in updates.items():
                if axis in TREATMENT_CODES and value not in TREATMENT_CODES[axis]:
                    findings.append(f"{class_prefix}.{axis}_treatment_invalid")
                if axis == "next_research_action":
                    _validate_action(value, f"{class_prefix}.next_research_action", findings)
            if "owner_cash" in updates and updates.get("owner_cash") == "COUNT_IN_PARENT_OWNER_CASH":
                scope_requirements = classification.get("scope_requirements")
                if not isinstance(scope_requirements, dict):
                    findings.append(f"{class_prefix}.parent_owner_cash_scope_requirements_missing")
                else:
                    settlement_requirements = scope_requirements.get("settlement")
                    if isinstance(settlement_requirements, dict):
                        allowed_nci = settlement_requirements.get("nci_scope")
                        required_parent_access = settlement_requirements.get("parent_access")
                    else:
                        allowed_nci = scope_requirements.get("required_nci_scope_at_settlement")
                        required_parent_access = scope_requirements.get(
                            "required_parent_access_at_settlement"
                        )
                    if not isinstance(allowed_nci, list) or not allowed_nci or not set(allowed_nci) <= {
                        "CLOSED",
                        "IMMATERIAL_WITH_EVIDENCE",
                    }:
                        findings.append(f"{class_prefix}.parent_owner_cash_nci_requirement_invalid")
                    if required_parent_access != "EVIDENCED":
                        findings.append(f"{class_prefix}.parent_owner_cash_access_requirement_invalid")
    return findings


def _material_action_tuple(action: dict[str, Any]) -> tuple[Any, ...]:
    if not isinstance(action, dict):
        return tuple(None for _ in MATERIAL_ACTION_FIELDS)
    return tuple(action.get(field) for field in MATERIAL_ACTION_FIELDS)


def _snapshot_code(snapshot: dict[str, Any], axis: str) -> Any:
    treatment = snapshot.get(axis)
    return treatment.get("treatment_code") if isinstance(treatment, dict) else treatment


def derive_material_treatment_changes(
    before: dict[str, Any], after: dict[str, Any]
) -> list[str]:
    if not isinstance(before, dict):
        before = {}
    if not isinstance(after, dict):
        after = {}
    changes = [
        axis for axis in TREATMENT_AXES if _snapshot_code(before, axis) != _snapshot_code(after, axis)
    ]
    before_action = before.get("next_research_action", {})
    after_action = after.get("next_research_action", {})
    if _material_action_tuple(before_action) != _material_action_tuple(after_action):
        changes.append("next_research_action")
    return changes


def compile_feedback_verdict(receipt: dict[str, Any]) -> dict[str, Any]:
    diagnostic_cells = receipt.get("settlement_summary", {}).get("diagnostic_cell_ids", [])
    changes = derive_material_treatment_changes(
        receipt.get("treatment_before", {}), receipt.get("treatment_after", {})
    )
    evaluation_design = receipt.get("evaluation_design")
    return {
        "real_feedback_turn": (
            "COMPLETED"
            if isinstance(diagnostic_cells, list) and bool(diagnostic_cells)
            else "NOT_DIAGNOSTIC"
        ),
        "enterprise_investment_treatment": (
            "MATERIAL_UPDATE_BOUNDED" if changes else "NO_MATERIAL_UPDATE"
        ),
        "materially_changed_axes": changes,
        "method_learning_utility": (
            "NOT_APPLICABLE"
            if evaluation_design == "SINGLE_ARM_DISCOVERY"
            else "DEFER_TO_PAIRED_UTILITY"
        ),
    }


def validate_postoutcome_feedback(receipt: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if receipt.get("schema_version") != FEEDBACK_SCHEMA_VERSION:
        findings.append("judgment_feedback.schema_version_invalid")
    for field in ("episode_id", "company_id"):
        if not _nonempty_text(receipt.get(field)):
            findings.append(f"judgment_feedback.{field}_missing")
    if receipt.get("evaluation_design") not in {"SINGLE_ARM_DISCOVERY", "PAIRED_TREATMENT"}:
        findings.append("judgment_feedback.evaluation_design_invalid")
    _validate_snapshot(receipt.get("treatment_before"), "judgment_feedback.treatment_before", findings)
    _validate_snapshot(receipt.get("treatment_after"), "judgment_feedback.treatment_after", findings)

    summary = receipt.get("settlement_summary")
    if not isinstance(summary, dict):
        findings.append("judgment_feedback.settlement_summary_missing")
    else:
        for field in ("diagnostic_cell_ids", "local_unknown_cell_ids", "mismatch_cell_ids"):
            if not isinstance(summary.get(field), list):
                findings.append(f"judgment_feedback.settlement_summary.{field}_must_be_list")

    expected = compile_feedback_verdict(receipt)
    declared = receipt.get("verdict")
    if not isinstance(declared, dict):
        findings.append("judgment_feedback.verdict_missing")
    else:
        for field in (
            "real_feedback_turn",
            "enterprise_investment_treatment",
            "method_learning_utility",
        ):
            if declared.get(field) != expected[field]:
                findings.append(f"judgment_feedback.{field}_inconsistent")
        if declared.get("materially_changed_axes") != expected["materially_changed_axes"]:
            findings.append("judgment_feedback.materially_changed_axes_inconsistent")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("preoutcome", "feedback"))
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    findings = (
        validate_preoutcome_draft(artifact)
        if args.kind == "preoutcome"
        else validate_postoutcome_feedback(artifact)
    )
    print(json.dumps({"valid": not findings, "findings": findings}, ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
