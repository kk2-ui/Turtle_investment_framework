from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.decision_reliability import (
    evaluate_output_decision_reliability,
    initialize_decision_reliability_policy,
    validate_decision_reliability,
)
from scripts.decision_ledger import ledger_fingerprint
from scripts.report_completion import (
    evaluate_pending_valuation_decision_revision,
    has_valid_internal_valuation_hypothesis,
)
from scripts.valuation_model_gate import valuation_fingerprint
from scripts.turtle_agent.tools.read_tools import read_structured_ledger_contract
from scripts.turtle_agent.tools.write_tools import audit_chapter


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _fixture(output: Path) -> tuple[dict, str]:
    _write(output / "fact_observations.json", {
        "observations": [{"observation_id": "annual_report", "status": "VERIFIED"}],
    })
    _write(output / "decisive_question_plan.json", {
        "selected_questions": [{"topic_family": "cash_value_realization"}],
    })
    _write(output / "compute_bundle.json", {
        "factor3": {
            "aa_avg": {"3y": 100.0},
            "gg_normalized": {
                "aa_norm_3y": 70.0,
                "maintenance_capex": 40.0,
                "full_capex_3y": 10.0,
            },
        },
    })
    valuation = {
        "models": [
            {
                "model_id": "M1", "model_type": "EPV", "role": "primary", "status": "active",
                "basis": {"cash_flow_scope": "normalized_owner_earnings"},
                "assumptions": {
                    "discount_rate": {"value_pct": 10},
                    "retained_value_realization": 0.0,
                },
                "result": {"value_per_share": 1.6},
            },
            {
                "model_id": "M2", "model_type": "DDM", "role": "corroborative", "status": "active",
                "basis": {"cash_flow_scope": "dividend"},
                "assumptions": {
                    "discount_rate": {"value_pct": 10},
                    "terminal_growth": {"value_pct": 2},
                    "dps_hkd": 0.16,
                },
                "result": {"value_per_share": 2.04},
            },
            {
                "model_id": "M3", "model_type": "RETURN_DECOMPOSITION", "role": "primary", "status": "active",
                "basis": {"cash_flow_scope": "owner_return"},
                "assumptions": {
                    "discount_rate": {"value_pct": 10},
                    "dividend_yield_pct": 8.0,
                    "growth_value_return_pct": 1.0,
                    "required_return_pct": 10.0,
                },
                "result": {
                    "value_per_share": 1.6,
                    "gross_return_pct": 9.0,
                    "return_safety_margin_pct": -1.0,
                },
            },
        ],
        "cash_access_bridge": {
            "as_of": "2025-12-31", "unit": "RMB_m", "gross_cash_amount": 100.0,
            "components": [{
                "component_id": "cash", "amount": 100.0,
                "legal_owner_scope": "consolidated_group",
                "access_status": "UNVERIFIED", "legal_distributability": "NOT_VERIFIED",
                "haircut_pct": 100.0, "source_ids": ["annual_report"],
            }],
            "conservative_accessible_cash_amount": 0.0,
            "parent_distributable_reserves": {
                "status": "NOT_DISCLOSED", "source_ids": ["annual_report"],
            },
            "ordinary_distribution_capacity": {
                "amount": 20.0, "basis_kind": "not_verified", "source_ids": ["annual_report"],
            },
            "unresolved": ["Parent-only distributable reserves are not disclosed"],
            "conclusion": "No existing cash is admitted to primary value without a parent-company reserve test.",
        },
        "parameter_calibrations": [{
            "model_id": "M1", "parameter": "retained_value_realization", "value": 0.0,
            "method": "conservative_bound", "range_low": 0.0, "range_high": 0.6,
            "basis": "Unverified access receives a full primary-value haircut.",
            "source_ids": ["annual_report"], "market_price_inputs": [], "decision_use": "primary",
            "sensitivity": {"action_at_low": "avoid", "action_at_high": "hold"},
        }],
        "model_comparisons": [
            {
                "model_id": "M2", "against_model_id": "M1", "comparable": False,
                "discount_rate_difference_pp": 0.0, "allowed_use": "distribution_floor",
                "basis_differences": "Dividend-only scope excludes retained earnings.",
            },
            {
                "model_id": "M2", "against_model_id": "M3", "comparable": False,
                "discount_rate_difference_pp": 0.0, "allowed_use": "diagnostic",
                "basis_differences": "Dividend value versus owner-return test.",
            },
        ],
        "joint_stress_tests": [{
            "case_id": "cash_earnings_payout_joint_downside",
            "simultaneous_inputs": {
                "normalized_earnings": 80.0, "payout_ratio": 0.4,
                "retained_value_realization": 0.0,
            },
            "output": {"value_per_share": 1.0, "action": "avoid"},
            "decision_implication": "The position remains zero under the joint downside.",
        }],
        "action_policy": {
            "current_holders_action": "avoid", "nonholders_action": "avoid",
            "precedence_order": ["exit", "reduce", "hold", "buy"],
            "upgrade_requires": "Verified cash access and distribution plus an adequate price margin",
            "joint_stress_action": "avoid",
        },
    }
    _write(output / "valuation_model.json", valuation)
    return valuation, "## Ch12\nDDM is a distribution floor, not a like-for-like corroboration."


def test_complete_reliability_contract_is_decision_ready(tmp_path: Path) -> None:
    _fixture(tmp_path)
    result = validate_decision_reliability(tmp_path, report_text="clean", enforced=True)
    assert result["state"] == "DECISION_READY"
    assert result["invalid_findings"] == []
    assert result["incomplete_findings"] == []


def test_unverified_cash_cannot_enter_primary_value(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["cash_access_bridge"]["components"][0]["haircut_pct"] = 40.0
    valuation["cash_access_bridge"]["conservative_accessible_cash_amount"] = 60.0
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert any("unverified_cash_requires_full_primary_haircut" in item for item in result["invalid_findings"])
    assert "cash_access_bridge:positive_cash_value_without_parent_reserve_test" in result["invalid_findings"]


def test_company_only_cash_location_must_be_explicitly_bridged(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    facts = json.loads((tmp_path / "fact_observations.json").read_text())
    facts["observations"].append({
        "observation_id": "OBS:company_cash", "status": "VERIFIED",
        "fact_name": "company_only_cash_and_cash_equivalents_rmb_m",
    })
    _write(tmp_path / "fact_observations.json", facts)

    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "cash_access_bridge:company_only_cash_location_omitted" in result["invalid_findings"]

    valuation["cash_access_bridge"]["components"][0]["source_ids"].append("OBS:company_cash")
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "cash_access_bridge:company_only_cash_location_omitted" not in result["invalid_findings"]


def test_distributable_reserve_cannot_masquerade_as_parent_cash(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["cash_access_bridge"]["components"][0].update({
        "access_status": "VERIFIED_ACCESSIBLE",
        "legal_distributability": "VERIFIED", "haircut_pct": 0.0,
    })
    valuation["cash_access_bridge"]["conservative_accessible_cash_amount"] = 100.0
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert any("parent_cash_location_not_verified" in item for item in result["invalid_findings"])


def test_actual_distribution_flow_can_support_positive_realization_without_parent_cash(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    facts = json.loads((tmp_path / "fact_observations.json").read_text())
    facts["observations"].append({
        "observation_id": "OBS:dividend", "status": "VERIFIED",
        "fact_name": "dividends_total",
    })
    _write(tmp_path / "fact_observations.json", facts)
    valuation["models"][0]["assumptions"]["retained_value_realization"] = 0.5
    valuation["parameter_calibrations"][0].update({
        "value": 0.5, "range_low": 0.5, "source_ids": ["OBS:dividend"],
    })
    valuation["cash_access_bridge"]["ordinary_distribution_capacity"] = {
        "amount": 20.0, "basis_kind": "actual_distribution_flow",
        "source_ids": ["OBS:dividend"],
    }
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert not any("positive_retained_value_with_zero_verified_access" in item for item in result["invalid_findings"])


def test_market_price_cannot_calibrate_intrinsic_lambda(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["parameter_calibrations"][0]["market_price_inputs"] = ["current_PE"]
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert any("circular_market_input_for_intrinsic_value" in item for item in result["invalid_findings"])


def test_non_like_for_like_model_cannot_be_called_corroboration(tmp_path: Path) -> None:
    valuation, _ = _fixture(tmp_path)
    valuation["synthesis"] = {
        "action": "hold", "position_pct": 0.0,
        "chosen_value_per_share": 1.6,
    }
    valuation["models"][1]["assumptions"]["discount_rate"]["value_pct"] = 5.5
    valuation["models"][1]["result"]["value_per_share"] = 4.52
    valuation["model_comparisons"][0].update({
        "comparable": True, "allowed_use": "corroboration", "discount_rate_difference_pp": 4.5,
    })
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text="M2 DDM交叉验证")
    assert any("non_like_for_like_cannot_corroborate" in item for item in result["invalid_findings"])
    valuation["model_comparisons"][0].update({
        "comparable": False, "allowed_use": "upper_bound",
    })
    _write(tmp_path / "valuation_model.json", valuation)
    report_result = validate_decision_reliability(tmp_path, report_text="M2 DDM交叉验证")
    assert any("report_overstates_noncomparable_model" in item for item in report_result["invalid_findings"])


def test_noncomparable_model_does_not_capture_cross_validation_on_later_line(tmp_path: Path) -> None:
    valuation, _ = _fixture(tmp_path)
    valuation["model_comparisons"][0].update({
        "comparable": False, "allowed_use": "upper_bound",
    })
    _write(tmp_path / "valuation_model.json", valuation)
    report = "M2 DDM仅作分红上限。P_base由同口径经营回报交叉验证。"
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert not any("report_overstates_noncomparable_model" in item for item in result["invalid_findings"])


def test_noncomparable_model_may_explicitly_deny_cross_validation(tmp_path: Path) -> None:
    valuation, _ = _fixture(tmp_path)
    valuation["model_comparisons"][0].update({
        "comparable": False, "allowed_use": "diagnostic",
        "basis_differences": "M2 DDM仅作诊断，不构成交叉验证。",
    })
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text="")
    assert not any("report_overstates_noncomparable_model" in item for item in result["invalid_findings"])


def test_not_applicable_discount_rate_requires_null_comparison_gap(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["models"][1]["model_type"] = "NAV"
    valuation["models"][1]["assumptions"]["discount_rate"] = {
        "value_pct": 0, "kind": "not_applicable",
    }
    valuation["model_comparisons"][0].update({
        "comparable": False, "allowed_use": "stress",
        "discount_rate_difference_pp": None,
    })
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert not any("discount_rate_difference" in item for item in result["invalid_findings"])


def test_return_and_normalized_aa_formula_mismatches_block(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["models"][2]["result"]["gross_return_pct"] = 18.4
    _write(tmp_path / "valuation_model.json", valuation)
    bundle = json.loads((tmp_path / "compute_bundle.json").read_text())
    bundle["factor3"]["gg_normalized"]["aa_norm_3y"] = 100.0
    _write(tmp_path / "compute_bundle.json", bundle)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "M3:gross_return_formula_mismatch" in result["invalid_findings"]
    assert any("normalized_aa_formula_mismatch" in item for item in result["invalid_findings"])


def test_maximum_balance_cannot_support_annualized_yield(tmp_path: Path) -> None:
    _fixture(tmp_path)
    report = "年度利息4.43M/最高日存款余额373.77M，因此年化利率1.19%。"
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "maximum_balance_cannot_be_used_as_average_yield_denominator" in result["invalid_findings"]


def test_cash_component_cannot_invent_interest_rate_from_amount_observations(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["cash_access_bridge"]["components"][0]["notes"] = (
        "存款100M，利率约1.19%，低于市场。"
    )
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert any("unverified_interest_rate_derivation" in item for item in result["invalid_findings"])


def test_joint_stress_and_holder_symmetry_are_required(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["joint_stress_tests"][0]["simultaneous_inputs"] = {"normalized_earnings": 80}
    valuation["action_policy"].update({
        "current_holders_action": "hold", "nonholders_action": "avoid",
    })
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert any("at_least_three_inputs_required" in item for item in result["incomplete_findings"])
    assert "action_policy:endowment_difference_without_quantified_friction" in result["invalid_findings"]


def test_joint_stress_policy_uses_worst_action_not_last_row(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["joint_stress_tests"].append({
        "case_id": "recovery", "simultaneous_inputs": {
            "normalized_earnings": 120.0, "payout_ratio": 0.5,
            "retained_value_realization": 0.5,
        },
        "output": {"value_per_share": 2.0, "action": "buy"},
        "decision_implication": "Recovery permits buying.",
    })
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "action_policy:joint_stress_action_mismatch" not in result["invalid_findings"]


def test_negative_primary_return_margin_cannot_authorize_new_buy(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["synthesis"] = {"action": "buy"}
    valuation["action_policy"]["nonholders_action"] = "buy"
    valuation["action_policy"]["current_holders_action"] = "buy"
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "action_policy:buy_with_negative_primary_return_margin" in result["invalid_findings"]
    assert "action_policy:nonholder_buy_with_negative_primary_return_margin" in result["invalid_findings"]


def test_synthesis_lambda_must_equal_primary_retained_value_realization(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["synthesis"] = {
        "action": "avoid", "decision_rule": "EPV uses λ=0.70 as the realization rate."
    }
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "synthesis_lambda_retained_value_realization_mismatch" in result["invalid_findings"]


def test_return_growth_is_scaled_by_retained_value_realization(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    model = valuation["models"][2]
    model["assumptions"]["retained_value_realization"] = 0.0
    model["result"]["gross_return_pct"] = 8.0
    model["result"]["return_safety_margin_pct"] = -2.0
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert not any("gross_return_formula_mismatch" in item for item in result["invalid_findings"])
    assert not any("return_safety_margin_formula_mismatch" in item for item in result["invalid_findings"])


def test_scenario_only_decay_is_not_double_counted_in_return_margin(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    model = valuation["models"][2]
    model["assumptions"]["moat_decay_pct"] = 4.8
    model["decay_treatment"] = {
        "mode": "scenario_only",
        "base_margin_excludes_decay": True,
        "double_count_check": "decay lowers cash flow only",
    }
    model["result"]["gross_return_pct"] = 9.0
    model["result"]["return_safety_margin_pct"] = -1.0
    _write(tmp_path / "valuation_model.json", valuation)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert not any(
        "return_safety_margin_formula_mismatch" in item
        for item in result["invalid_findings"]
    )


def test_value_realization_payout_ratio_requires_matching_verified_fact(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    valuation["models"][0]["value_realization_bridge"] = {
        "payout_ratio": 0.5, "payout_source_ids": ["OBS:payout"],
    }
    _write(tmp_path / "valuation_model.json", valuation)
    facts = json.loads((tmp_path / "fact_observations.json").read_text())
    facts["observations"].append({
        "observation_id": "OBS:payout", "status": "VERIFIED",
        "fact_name": "dividend_payout_ratio_pct", "normalized_value": 60.0,
    })
    _write(tmp_path / "fact_observations.json", facts)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert "M1:value_realization_payout_ratio_evidence_mismatch" in result["invalid_findings"]

    facts["observations"][-1]["normalized_value"] = 50.0
    _write(tmp_path / "fact_observations.json", facts)
    result = validate_decision_reliability(tmp_path, report_text=report)
    assert not any("value_realization_payout" in item for item in result["invalid_findings"])


def test_policy_controls_completion_style_evaluation(tmp_path: Path) -> None:
    _fixture(tmp_path)
    assert evaluate_output_decision_reliability(tmp_path, persist=False)["state"] == "SKIP"
    initialize_decision_reliability_policy(tmp_path, run_id="run", enforced=True)
    assert evaluate_output_decision_reliability(tmp_path, report_text="clean")["state"] == "DECISION_READY"
    assert (tmp_path / "decision_reliability_validation.json").is_file()


def test_reliability_validation_accepts_noncanonical_candidate_override(tmp_path: Path) -> None:
    valuation, report = _fixture(tmp_path)
    candidate = json.loads(json.dumps(valuation))
    candidate["cash_access_bridge"]["components"][0]["haircut_pct"] = 40.0
    candidate["cash_access_bridge"]["conservative_accessible_cash_amount"] = 60.0
    result = validate_decision_reliability(
        tmp_path, report_text=report, valuation_override=candidate,
    )
    assert any("unverified_cash_requires_full_primary_haircut" in item for item in result["invalid_findings"])
    canonical = json.loads((tmp_path / "valuation_model.json").read_text())
    assert canonical["cash_access_bridge"]["components"][0]["haircut_pct"] == 100.0


def test_pending_decision_revision_is_fingerprint_bound_and_incomplete(
    tmp_path: Path, monkeypatch,
) -> None:
    valuation, _ = _fixture(tmp_path)
    ledger = {"entries": [{"entry_id": "D006", "value": 3.22}]}
    _write(tmp_path / "decision_ledger.json", ledger)
    _write(tmp_path / "valuation_decision_revision_proposal.json", {
        "state": "READY_FOR_DECISION_REVISION", "approval_status": "PENDING",
        "candidate": valuation,
        "candidate_fingerprint": valuation_fingerprint(valuation),
        "current_decision_ledger_fingerprint": ledger_fingerprint(ledger),
        "proposed_synthesis": {"action": "hold"},
        "required_revisions": ["synthesis_manifest_action_mismatch"],
        "structural_validation": {
            "state": "INVALID",
            "invalid_findings": ["synthesis_manifest_action_mismatch"],
            "incomplete_findings": [],
        },
        "decision_reliability_validation": {"state": "DECISION_READY"},
    })
    monkeypatch.setattr(
        "scripts.valuation_model_gate.validate_valuation_model_ledger",
        lambda *args, **kwargs: {
            "state": "INVALID",
            "invalid_findings": ["synthesis_manifest_action_mismatch"],
            "incomplete_findings": [],
        },
    )
    monkeypatch.setattr(
        "scripts.decision_reliability.validate_decision_reliability",
        lambda *args, **kwargs: {
            "state": "DECISION_READY", "invalid_findings": [],
            "incomplete_findings": [],
        },
    )

    result = evaluate_pending_valuation_decision_revision(str(tmp_path))
    assert result["state"] == "INCOMPLETE"
    assert result["status"] == "FULL_REPORT_SYNTHESIS_REQUIRED"
    assert result["findings"] == ["valuation_hypothesis_requires_full_report_synthesis"]
    assert has_valid_internal_valuation_hypothesis(str(tmp_path)) is True

    ledger["entries"][0]["value"] = 2.30
    _write(tmp_path / "decision_ledger.json", ledger)
    stale = evaluate_pending_valuation_decision_revision(str(tmp_path))
    assert stale["state"] == "INVALID"
    assert "current_decision_ledger_changed" in stale["findings"]


def test_pending_decision_revision_resolves_after_full_report_propagation(
    tmp_path: Path,
) -> None:
    valuation, _ = _fixture(tmp_path)
    valuation["synthesis"] = {
        "action": "hold", "position_pct": 0.0,
        "chosen_value_per_share": 3.22,
        "decision_entry_id": "D006",
    }
    ledger = {"entries": [{"entry_id": "D006", "value": 3.22}]}
    _write(tmp_path / "valuation_model.json", valuation)
    _write(tmp_path / "decision_ledger.json", ledger)
    _write(tmp_path / "decision_manifest.json", {
        "quantitative_decision": "hold", "unified_decision": "hold",
        "position_pct": 0.0,
    })
    _write(tmp_path / "valuation_decision_revision_proposal.json", {
        "state": "INTERNAL_SYNTHESIS_REQUIRED",
        "approval_status": "NOT_REQUESTED_AT_VALUATION_STAGE",
        "candidate": valuation,
        "candidate_fingerprint": valuation_fingerprint(valuation),
        "current_decision_ledger_fingerprint": "superseded-by-propagation",
        "proposed_synthesis": valuation["synthesis"],
    })

    result = evaluate_pending_valuation_decision_revision(str(tmp_path))

    assert result["state"] == "RESOLVED"
    assert result["status"] == "PASS"
    assert result["resolution"] == "propagated_after_full_report_synthesis"
    assert has_valid_internal_valuation_hypothesis(str(tmp_path)) is False


def test_read_contract_exposes_rejected_reliability_resume_without_authority(tmp_path: Path) -> None:
    valuation, _ = _fixture(tmp_path)
    candidate = deepcopy(valuation)
    candidate["cash_access_bridge"]["components"][0]["haircut_pct"] = 40.0
    candidate["cash_access_bridge"]["conservative_accessible_cash_amount"] = 60.0
    _write(tmp_path / "valuation_model_last_rejected.json", candidate)
    _write(tmp_path / "valuation_model_last_rejected_validation.json", {
        "state": "INVALID", "invalid_findings": ["synthesis_v_final_mismatch"],
    })

    contract = read_structured_ledger_contract(str(tmp_path), "valuation")
    resume = contract["rejected_reliability_resume"]
    assert resume["candidate_cash_access_bridge"]["conservative_accessible_cash_amount"] == 60.0
    assert any(
        "unverified_cash_requires_full_primary_haircut" in item
        for item in resume["reliability_validation"]["invalid_findings"]
    )
    assert "non-canonical" in resume["instruction"]


def test_downstream_contract_exposes_internal_valuation_without_calling_it_final(
    tmp_path: Path,
) -> None:
    valuation, _ = _fixture(tmp_path)
    valuation["synthesis"] = {
        "action": "hold", "position_pct": 0.0,
        "chosen_value_per_share": 1.6,
    }
    _write(tmp_path / "valuation_decision_revision_proposal.json", {
        "state": "INTERNAL_SYNTHESIS_REQUIRED",
        "approval_status": "NOT_REQUESTED_AT_VALUATION_STAGE",
        "candidate": valuation,
        "candidate_fingerprint": valuation_fingerprint(valuation),
        "current_manifest": {"quantitative_decision": "buy"},
    })

    contract = read_structured_ledger_contract(str(tmp_path), "thesis")
    staged = contract["internal_full_report_synthesis"]
    assert staged["status"] == "INTERNAL_HYPOTHESIS_NOT_FINAL_ACTION"
    assert staged["valuation"]["synthesis"]["action"] == "hold"
    assert any("approved" in rule for rule in staged["rules"])
    assert has_valid_internal_valuation_hypothesis(str(tmp_path)) is False


def test_chapter_audit_rejects_noncomparable_corroboration_language(tmp_path: Path) -> None:
    _fixture(tmp_path)
    chapters = tmp_path / "chapters"; chapters.mkdir()
    (chapters / "_ch12.md").write_text(
        "## Ch12 估值\n\nM2 DDM交叉验证EPV结论。", encoding="utf-8"
    )
    result = audit_chapter(str(tmp_path), 12)
    assert any(
        item.get("rule") == "DECISION_RELIABILITY_LANGUAGE"
        for item in result["violations"]
    )


def test_chapter_audit_rejects_unverified_parent_reserve_as_fact(tmp_path: Path) -> None:
    _fixture(tmp_path)
    chapters = tmp_path / "chapters"; chapters.mkdir()
    (chapters / "_ch12.md").write_text(
        "## Ch12 估值\n\n母公司可供分配储备299.19M构成现金分配法律上限。",
        encoding="utf-8",
    )
    result = audit_chapter(str(tmp_path), 12)
    assert any(
        item.get("rule") == "DECISION_RELIABILITY_LANGUAGE"
        and "未核验" in item.get("desc", "")
        for item in result["violations"]
    )
