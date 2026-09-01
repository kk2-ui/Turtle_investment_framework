from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.report_completion import evaluate_report_completion
from scripts.turtle_agent.run import _repair_targets_from_completion
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.write_tools import write_valuation_model_ledger
from scripts.valuation_model_gate import (
    build_valuation_model_ledger,
    bind_valuation_references,
    evaluate_output_valuation_model,
    initialize_valuation_model_policy,
    persist_valuation_model_ledger,
    promote_reviewable_valuation_model,
    validate_valuation_model_ledger,
)


ENTRY_ID = "valuation.v_final@base.current"


def _prepare(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "compute_bundle.json").write_text("{}", encoding="utf-8")
    (output / "decision_manifest.json").write_text(json.dumps({
        "quantitative_decision": "hold", "position_pct": 5.0,
    }), encoding="utf-8")
    (output / "decision_ledger.json").write_text(json.dumps({"entries": [{
        "entry_id": ENTRY_ID, "metric_id": "valuation.v_final", "value": 50.0, "status": "active",
    }]}), encoding="utf-8")


def _sens(action: str = "hold") -> list[dict]:
    return [
        {"case_id": "discount_rate_up_1pp", "value_per_share": 44.0, "action": action},
        {"case_id": "growth_down_1pp", "value_per_share": 46.0, "action": action},
        {"case_id": "combined_stress", "value_per_share": 40.0, "action": action},
    ]


def _dcf() -> dict:
    return {
        "model_id": "dcf.fcff.base", "model_type": "DCF", "role": "primary", "status": "active",
        "chapters": [12],
        "independence_group_id": "cashflow", "shared_assumption_ids": ["revenue.base", "margin.base"],
        "applicability": {"business_fit": "operating company", "cash_flow_fit": "normalized", "capital_structure_fit": "stable", "payout_fit": "not_applicable", "rationale": "normalized FCFF is observable", "disqualifiers": []},
        "basis": {"value_scope": "enterprise", "cash_flow_scope": "FCFF", "currency": "RMB", "as_of": "2026-08-02", "tax_basis": "post_tax"},
        "assumptions": {"forecast_years": 5, "discount_rate": {"value_pct": 10.0, "kind": "WACC", "inflation_basis": "nominal", "tax_basis": "post_tax"}, "terminal_growth": {"value_pct": 2.0, "inflation_basis": "nominal"}},
        "result": {"value_per_share": 50.0},
        "equity_bridge": {"enterprise_value": 500.0, "non_operating_assets": 100.0, "debt": 80.0, "minority_interest": 10.0, "other_adjustments": -10.0, "equity_value": 500.0, "shares": 10.0, "per_share_value": 50.0},
        "terminal_value": {"present_value": 275.0, "total_model_value": 500.0, "share_pct": 55.0}, "sensitivity_tests": _sens(),
        "source_ids": ["compute_bundle.json"], "decision_entry_ids": [ENTRY_ID],
    }


def _ddm() -> dict:
    return {
        "model_id": "ddm.normalized", "model_type": "DDM", "role": "corroborative", "status": "active",
        "chapters": [13],
        "independence_group_id": "distribution", "shared_assumption_ids": ["payout.normalized"],
        "applicability": {"business_fit": "dividend payer", "cash_flow_fit": "stable", "capital_structure_fit": "stable", "payout_fit": "normalized", "rationale": "normalized payout corroborates FCFF", "disqualifiers": []},
        "basis": {"value_scope": "equity", "cash_flow_scope": "dividend", "currency": "RMB", "as_of": "2026-08-02", "tax_basis": "post_tax"},
        "assumptions": {"discount_rate": {"value_pct": 10.0, "kind": "cost_of_equity", "inflation_basis": "nominal", "tax_basis": "post_tax"}, "terminal_growth": {"value_pct": 2.0, "inflation_basis": "nominal"}},
        "result": {"value_per_share": 48.0}, "terminal_value": {"present_value": 300.0, "total_model_value": 500.0, "share_pct": 60.0}, "sensitivity_tests": _sens(),
        "source_ids": ["compute_bundle.json"], "decision_entry_ids": [ENTRY_ID],
    }


def _payload(output: Path, *, freeze: bool = True) -> dict:
    _prepare(output)
    return build_valuation_model_ledger(
        output,
        {"business_type": "general_operating", "asset_intensity": "mixed", "valuation_route": "R5", "route_reasoning": "stable franchise; use return/cash-flow anchors"},
        [_dcf(), _ddm()],
        {"action": "hold", "position_pct": 5.0, "range_low": 40.0, "range_high": 60.0, "chosen_value_per_share": 50.0, "decision_rule": "primary FCFF with independent payout cross-check", "divergence_explanation": "", "decision_entry_id": ENTRY_ID},
        change_reason="initial valuation validation", freeze=freeze,
    )


def _enable_contracts(
    output: Path, *, normalization: bool = False, decay: bool = False,
    owner_earnings: bool = False, holding_period: bool = False,
) -> None:
    initialize_valuation_model_policy(
        output,
        run_id="contract-test",
        enforced=False,
        require_normalization_bridge=normalization,
        require_decay_treatment=decay,
        require_owner_earnings_normalization=owner_earnings,
        require_holding_period_return_bridge=holding_period,
    )


def _as_epv(payload: dict) -> dict:
    model = payload["models"][0]
    model["model_type"] = "EPV"
    model["basis"].update({
        "value_scope": "equity",
        "cash_flow_scope": "normalized_earnings",
        "currency": "RMB",
    })
    model["assumptions"]["discount_rate"]["kind"] = "cost_of_equity"
    model["normalization_bridge"] = {
        "source_currency": "RMB",
        "model_currency": "RMB",
        "source_normalized_earnings": 50.0,
        "fx_source_per_model": 1.0,
        "normalized_earnings_model_currency": 50.0,
        "capitalization_rate_pct": 10.0,
        "capitalized_value": 500.0,
        "shares": 10.0,
        "per_share_value": 50.0,
        "non_operating_income_treatment": "excluded from normalized earnings",
        "adjustments": [{"adjustment_id": "normalize.one_off", "amount": 5.0}],
        "source_ids": ["compute_bundle.json"],
    }
    return model


def _as_return_decomposition(payload: dict, *, mode: str) -> dict:
    model = payload["models"][0]
    model["model_type"] = "RETURN_DECOMPOSITION"
    model["basis"].update({
        "value_scope": "equity",
        "cash_flow_scope": "owner_return",
    })
    model["result"].update({
        "gross_return_pct": 14.8,
        "required_return_pct": 10.0,
        "decay_pct": 4.8,
        "return_safety_margin_pct": 4.8 if mode == "scenario_only" else 0.0,
    })
    model["decay_treatment"] = {
        "mode": mode,
        "base_margin_excludes_decay": mode == "scenario_only",
        "double_count_check": "decay is applied exactly once in the declared mode",
    }
    return model


def _validate(tmp_path: Path, payload: dict, *, enforced: bool = True) -> dict:
    report = "## Ch12 估值\n[valuation: dcf.fcff.base]\n\n## Ch13 DDM\n[valuation: ddm.normalized]"
    return validate_valuation_model_ledger(payload, output_dir=tmp_path, report_text=report, enforced=enforced)


def test_valid_valuation_ledger_reaches_decision_ready(tmp_path: Path) -> None:
    assert _validate(tmp_path, _payload(tmp_path))["state"] == "DECISION_READY"


def test_new_contracts_are_backward_compatible_until_policy_enables_them(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path, freeze=False)
    _as_epv(payload).pop("normalization_bridge")
    result = _validate(tmp_path, payload, enforced=False)
    assert not any("normalization_bridge" in item for item in result["invalid_findings"])

    payload = _payload(tmp_path, freeze=False)
    _as_return_decomposition(payload, mode="scenario_only").pop("decay_treatment")
    result = _validate(tmp_path, payload, enforced=False)
    assert not any("decay_treatment" in item for item in result["invalid_findings"])


def test_primary_epv_requires_complete_normalization_bridge_when_enabled(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path, freeze=False)
    _as_epv(payload).pop("normalization_bridge")
    _enable_contracts(tmp_path, normalization=True)

    result = _validate(tmp_path, payload, enforced=False)

    assert "dcf.fcff.base:normalization_bridge_missing" in result["invalid_findings"]
    assert result["state"] == "INVALID"


def test_primary_epv_normalization_bridge_rejects_bad_arithmetic_and_empty_audit_fields(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path, freeze=False)
    bridge = _as_epv(payload)["normalization_bridge"]
    bridge.update({
        "fx_source_per_model": 2.0,
        "capitalized_value": 490.0,
        "per_share_value": 48.0,
        "non_operating_income_treatment": "",
        "adjustments": [],
        "source_ids": [],
    })
    _enable_contracts(tmp_path, normalization=True)

    findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]

    assert "dcf.fcff.base:normalization_bridge_same_currency_fx_invalid" in findings
    assert "dcf.fcff.base:normalization_bridge_fx_arithmetic_mismatch" in findings
    assert "dcf.fcff.base:normalization_bridge_capitalization_mismatch" in findings
    assert "dcf.fcff.base:normalization_bridge_per_share_mismatch" in findings
    assert "dcf.fcff.base:normalization_bridge_result_mismatch" in findings
    assert "dcf.fcff.base:normalization_bridge_non_operating_income_treatment_missing" in findings
    assert "dcf.fcff.base:normalization_bridge_adjustments_missing" in findings
    assert "dcf.fcff.base:normalization_bridge_source_ids_missing" in findings


def test_primary_epv_accepts_reconciled_normalization_bridge(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    model = _as_epv(payload)
    model["basis"]["currency"] = "HKD"
    model["normalization_bridge"].update({
        "source_currency": "RMB",
        "model_currency": "HKD",
        "source_normalized_earnings": 45.0,
        "fx_source_per_model": 0.9,
    })
    _enable_contracts(tmp_path, normalization=True)

    result = _validate(tmp_path, payload, enforced=False)

    assert not any("normalization_bridge" in item for item in result["invalid_findings"])


def test_primary_return_decomposition_requires_decay_treatment_when_enabled(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path, freeze=False)
    _as_return_decomposition(payload, mode="scenario_only").pop("decay_treatment")
    _enable_contracts(tmp_path, decay=True)

    result = _validate(tmp_path, payload, enforced=False)

    assert "dcf.fcff.base:decay_treatment_missing" in result["invalid_findings"]
    assert result["state"] == "INVALID"


def test_scenario_only_decay_must_be_excluded_from_base_margin(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    model = _as_return_decomposition(payload, mode="scenario_only")
    model["result"]["return_safety_margin_pct"] = 0.0
    model["decay_treatment"]["base_margin_excludes_decay"] = False
    _enable_contracts(tmp_path, decay=True)

    findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]

    assert "dcf.fcff.base:scenario_only_margin_mismatch" in findings
    assert "dcf.fcff.base:scenario_only_must_exclude_decay_from_base_margin" in findings


def test_incremental_hurdle_decay_must_be_included_exactly_once(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    model = _as_return_decomposition(payload, mode="incremental_hurdle")
    model["result"]["return_safety_margin_pct"] = 4.8
    model["decay_treatment"]["base_margin_excludes_decay"] = True
    _enable_contracts(tmp_path, decay=True)

    findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]

    assert "dcf.fcff.base:incremental_hurdle_margin_mismatch" in findings
    assert "dcf.fcff.base:incremental_hurdle_must_include_decay_in_base_margin" in findings


def test_valid_decay_modes_pass_and_invalid_or_undocumented_modes_fail(
    tmp_path: Path,
) -> None:
    _enable_contracts(tmp_path, decay=True)
    for mode in ("scenario_only", "incremental_hurdle", "cash_flow_adjustment"):
        payload = _payload(tmp_path, freeze=False)
        _as_return_decomposition(payload, mode=mode)
        findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]
        assert not any("decay_treatment" in item or f"{mode}_" in item for item in findings)

    payload = _payload(tmp_path, freeze=False)
    model = _as_return_decomposition(payload, mode="scenario_only")
    model["decay_treatment"].update({"mode": "additive_everywhere", "double_count_check": ""})
    findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]
    assert "dcf.fcff.base:decay_treatment_mode_invalid" in findings
    assert "dcf.fcff.base:decay_treatment_double_count_check_missing" in findings


def test_owner_earnings_bridge_requires_multiyear_capex_and_working_capital_treatment(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path, freeze=False)
    _as_epv(payload)
    _enable_contracts(tmp_path, owner_earnings=True)
    findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]
    assert "dcf.fcff.base:normalization_window_too_short" in findings
    assert "dcf.fcff.base:maintenance_capex_treatment_missing" in findings
    assert "dcf.fcff.base:working_capital_treatment_missing" in findings


def test_holding_period_bridge_reconciles_base_return_and_scenario_irr(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    model = _as_return_decomposition(payload, mode="scenario_only")
    model["result"]["gross_return_pct"] = 10.0
    model["result"]["return_safety_margin_pct"] = 0.0
    model["holding_period_return_bridge"] = {
        "years": 1, "entry_price": 10.0, "annual_dividend_per_share": 1.0,
        "source_ids": ["compute_bundle.json"],
        "scenarios": [
            {
                "role": "downside", "terminal_price": 8.0, "irr_pct": -15.0,
                "annual_dividend_per_share": 0.5,
            },
            {"role": "base", "terminal_price": 10.0, "irr_pct": 10.0},
            {"role": "upside", "terminal_price": 12.0, "irr_pct": 30.0},
        ],
    }
    _enable_contracts(tmp_path, holding_period=True)
    findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]
    assert not any("holding_period" in item for item in findings)

    model["holding_period_return_bridge"]["scenarios"][1]["irr_pct"] = 7.0
    findings = _validate(tmp_path, payload, enforced=False)["invalid_findings"]
    assert "dcf.fcff.base:holding_period_scenarios[1]:irr_arithmetic_mismatch" in findings
    assert "dcf.fcff.base:holding_period_base_return_mismatch" in findings


def test_synthesis_value_must_reconcile_to_primary_or_auditable_bridge(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    payload["synthesis"]["chosen_value_per_share"] = 49.0
    payload["synthesis"]["range_low"] = 48.0
    for entry in json.loads((tmp_path / "decision_ledger.json").read_text())["entries"]:
        entry["value"] = 49.0
    ledger = json.loads((tmp_path / "decision_ledger.json").read_text())
    ledger["entries"][0]["value"] = 49.0
    (tmp_path / "decision_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    result = _validate(tmp_path, payload)
    assert "synthesis_not_reconciled_to_primary_model" in result["invalid_findings"]

    payload["synthesis"]["value_realization_bridge"] = {
        "method": "weighted_average", "output_value_per_share": 49.0,
        "inputs": [
            {"model_id": "dcf.fcff.base", "weight": 0.5},
            {"model_id": "ddm.normalized", "weight": 0.5},
        ],
    }
    result = _validate(tmp_path, payload)
    assert "synthesis_not_reconciled_to_primary_model" not in result["invalid_findings"]
    assert not any("synthesis_weighted_bridge" in item for item in result["invalid_findings"])


def test_separate_components_bridge_keeps_operating_epv_distinct_from_growth(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    payload["models"][0]["result"]["value_per_share"] = 48.0
    payload["models"][0]["equity_bridge"].update({
        "other_adjustments": -30.0,
        "equity_value": 480.0,
        "per_share_value": 48.0,
    })
    payload["synthesis"].update({
        "chosen_value_per_share": 49.0,
        "range_low": 40.0,
        "range_high": 60.0,
        "value_realization_bridge": {
            "method": "separate_value_components",
            "operating_model_id": "dcf.fcff.base",
            "operating_value_per_share": 48.0,
            "retained_growth_per_share": 1.0,
            "retained_growth_realization": 1.0,
            "growth_source_ids": ["normalized-growth-study"],
            "accessible_cash_per_share": 0.0,
            "output_value_per_share": 49.0,
        },
    })
    ledger = json.loads((tmp_path / "decision_ledger.json").read_text())
    ledger["entries"][0]["value"] = 49.0
    (tmp_path / "decision_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")

    result = _validate(tmp_path, payload)
    assert "synthesis_separate_components_bridge_arithmetic_mismatch" not in result["invalid_findings"]


def test_separate_components_bridge_cannot_smuggle_in_unreconciled_cash(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    payload["synthesis"].update({
        "chosen_value_per_share": 51.0,
        "range_low": 40.0,
        "range_high": 60.0,
        "value_realization_bridge": {
            "method": "separate_value_components",
            "operating_model_id": "dcf.fcff.base",
            "operating_value_per_share": 50.0,
            "retained_growth_per_share": 0.0,
            "retained_growth_realization": 0.0,
            "accessible_cash_per_share": 1.0,
            "output_value_per_share": 51.0,
        },
    })
    ledger = json.loads((tmp_path / "decision_ledger.json").read_text())
    ledger["entries"][0]["value"] = 51.0
    (tmp_path / "decision_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")

    result = _validate(tmp_path, payload)
    assert "synthesis_separate_components_bridge_arithmetic_mismatch" in result["invalid_findings"]


def test_reliable_action_change_creates_pending_revision_without_overwriting_canonical(
    tmp_path: Path, monkeypatch,
) -> None:
    canonical = _payload(tmp_path, freeze=False)
    (tmp_path / "valuation_model.json").write_text(
        json.dumps(canonical, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "decision_reliability_policy.json").write_text(
        json.dumps({"enforced": True}), encoding="utf-8"
    )
    before = (tmp_path / "valuation_model.json").read_bytes()
    candidate = deepcopy(canonical)
    candidate["synthesis"]["action"] = "buy"
    candidate["models"][0]["fragility_mitigation"] = (
        "The proposed action remains capped by the explicit combined stress."
    )
    (tmp_path / "_ch12.md").write_text(
        "## Ch12\n[valuation: dcf.fcff.base]", encoding="utf-8"
    )
    (tmp_path / "_ch13.md").write_text(
        "## Ch13\n[valuation: ddm.normalized]", encoding="utf-8"
    )

    monkeypatch.setattr(
        "scripts.decision_reliability.validate_decision_reliability",
        lambda *args, **kwargs: {
            "state": "DECISION_READY", "status": "PASS",
            "invalid_findings": [], "incomplete_findings": [],
        },
    )
    result = write_valuation_model_ledger(
        str(tmp_path),
        company_profile=candidate["company_profile"],
        models=candidate["models"],
        synthesis=candidate["synthesis"],
        change_reason="reliability changes action",
        freeze=False,
    )

    assert result["written"] is False
    assert result["decision_revision_proposed"] is True
    assert result["full_report_synthesis_required"] is True
    assert (tmp_path / "valuation_model.json").read_bytes() == before
    proposal = json.loads(
        (tmp_path / "valuation_decision_revision_proposal.json").read_text()
    )
    assert proposal["state"] == "INTERNAL_SYNTHESIS_REQUIRED"
    assert proposal["approval_status"] == "NOT_REQUESTED_AT_VALUATION_STAGE"
    assert proposal["review_scope"] == "FULL_REPORT_PHILOSOPHY_ALIGNMENT"
    assert proposal["proposed_synthesis"]["action"] == "buy"


def test_unenforced_reliability_never_creates_decision_revision_proposal(
    tmp_path: Path,
) -> None:
    canonical = _payload(tmp_path, freeze=False)
    candidate = deepcopy(canonical)
    candidate["synthesis"]["action"] = "buy"

    result = write_valuation_model_ledger(
        str(tmp_path),
        company_profile=candidate["company_profile"],
        models=candidate["models"],
        synthesis=candidate["synthesis"],
        change_reason="legacy unenforced write",
        freeze=False,
    )

    assert result.get("decision_revision_proposed") is not True
    assert not (tmp_path / "valuation_decision_revision_proposal.json").exists()


def test_fcff_requires_enterprise_value_and_wacc(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["assumptions"]["discount_rate"]["kind"] = "cost_of_equity"
    result = _validate(tmp_path, payload)
    assert result["state"] == "INVALID"
    assert any("fcff_requires_enterprise_wacc" in x for x in result["invalid_findings"])


def test_malformed_nested_assumptions_return_validation_error_not_exception(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path, freeze=False)
    payload["models"][0]["assumptions"] = 10.0

    result = validate_valuation_model_ledger(
        payload, output_dir=tmp_path, enforced=True
    )

    assert any("assumptions_invalid" in x for x in result["invalid_findings"])


def test_enterprise_to_equity_bridge_must_reconcile(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["equity_bridge"]["debt"] = 60.0
    result = _validate(tmp_path, payload)
    assert any("enterprise_to_equity_bridge_mismatch" in x for x in result["invalid_findings"])


def test_equity_scope_result_mismatch_requires_auditable_realization_bridge(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    model = payload["models"][1]
    model["equity_bridge"] = {
        "enterprise_value": 600.0, "non_operating_assets": 0.0,
        "debt": 0.0, "minority_interest": 0.0, "other_adjustments": 0.0,
        "equity_value": 600.0, "shares": 10.0, "per_share_value": 60.0,
        "currency": "RMB",
    }
    result = _validate(tmp_path, payload)
    assert "ddm.normalized:result_bridge_mismatch" in result["invalid_findings"]

    model["assumptions"]["retained_value_realization"] = 0.6
    model["value_realization_bridge"] = {
        "gross_per_share": 60.0, "payout_ratio": 0.5,
        "retained_value_realization": 0.6, "realized_per_share": 48.0,
        "payout_source_ids": ["OBS:payout"],
    }
    result = _validate(tmp_path, payload)
    assert not any("result_bridge_mismatch" in item for item in result["invalid_findings"])
    assert not any("value_realization_" in item for item in result["invalid_findings"])


def test_nominal_real_mismatch_is_invalid(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["assumptions"]["terminal_growth"]["inflation_basis"] = "real"
    assert any("nominal_real_mismatch" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_tax_basis_must_be_explicit_and_consistent(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["assumptions"]["discount_rate"]["tax_basis"] = "pre_tax"
    assert any("tax_basis_mismatch" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_r_must_exceed_g_with_primary_safety_buffer(tmp_path: Path) -> None:
    equal = _payload(tmp_path, freeze=False); equal["models"][0]["assumptions"]["terminal_growth"]["value_pct"] = 10.0
    assert any("r_not_greater" in x for x in _validate(tmp_path, equal)["invalid_findings"])
    narrow = _payload(tmp_path, freeze=False); narrow["models"][0]["assumptions"]["terminal_growth"]["value_pct"] = 7.5
    assert any("r_g_buffer_too_small" in x for x in _validate(tmp_path, narrow)["invalid_findings"])


def test_bank_cannot_use_fcff_dcf_as_primary(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["company_profile"]["business_type"] = "bank"
    result = _validate(tmp_path, payload)
    assert any("model_not_applicable_to_bank" in x for x in result["invalid_findings"])


def test_unstable_payout_disqualifies_primary_ddm(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["role"] = "corroborative"; payload["models"][1]["role"] = "primary"; payload["models"][1]["applicability"]["payout_fit"] = "unstable"
    assert any("ddm_payout_unfit" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_asset_light_company_cannot_use_nav_as_primary(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["company_profile"]["asset_intensity"] = "asset_light"; payload["models"][0]["model_type"] = "NAV"
    assert any("asset_method_primary" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_rejected_route_model_accepts_explicit_rejected_role(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    payload["models"].append({
        "model_id": "nav.rejected", "model_type": "NAV", "role": "rejected",
        "status": "rejected", "rejection_reason": "品牌经营价值不由账面净资产决定",
    })
    result = _validate(tmp_path, payload)
    assert "nav.rejected:role_invalid" not in result["invalid_findings"]


def test_active_model_cannot_masquerade_as_rejected_role(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    payload["models"][0]["role"] = "rejected"
    assert "dcf.fcff.base:role_invalid" in _validate(tmp_path, payload)["invalid_findings"]


def test_cyclical_company_requires_normalized_cash_flow(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["company_profile"]["business_type"] = "cyclical"; payload["models"][0]["applicability"]["cash_flow_fit"] = "stable"
    assert any("cyclical_cash_flow_not_normalized" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_relative_method_cannot_be_only_primary_anchor(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"] = [payload["models"][0]]; payload["models"][0]["model_type"] = "RELATIVE"
    assert "relative_valuation_cannot_be_sole_primary" in _validate(tmp_path, payload)["invalid_findings"]


def test_perpetuity_models_require_three_stress_cases(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["sensitivity_tests"] = []
    result = _validate(tmp_path, payload)
    assert result["state"] == "INCOMPLETE"
    assert sum("sensitivity_case_missing" in x for x in result["incomplete_findings"]) == 3


def test_terminal_share_must_reconcile_to_components(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["terminal_value"]["share_pct"] = 65.0
    assert any("terminal_share_mismatch" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_action_flip_requires_explicit_fragility_mitigation(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["sensitivity_tests"][0]["action"] = "avoid"
    result = _validate(tmp_path, payload)
    assert any("fragility_mitigation_missing" in x for x in result["incomplete_findings"])
    payload["models"][0]["fragility_mitigation"] = "仓位按压力情景封顶，并以独立DDM复核"
    assert not any("fragility_mitigation_missing" in x for x in _validate(tmp_path, payload)["incomplete_findings"])


def test_fragile_primary_requires_independent_corroboration(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"] = [payload["models"][0]]; payload["models"][0]["terminal_value"]["share_pct"] = 85.0
    result = _validate(tmp_path, payload)
    assert "fragile_primary_without_independent_corroboration" in result["incomplete_findings"]
    assert any("fragility_mitigation_missing" in x for x in result["incomplete_findings"])


def test_shared_assumptions_cannot_fake_independence(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][1]["shared_assumption_ids"] = deepcopy(payload["models"][0]["shared_assumption_ids"])
    result = _validate(tmp_path, payload)
    assert any("false_independence_shared_assumptions" in x for x in result["invalid_findings"])


def test_large_model_divergence_requires_explanation(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][1]["result"]["value_per_share"] = 20.0
    result = _validate(tmp_path, payload)
    assert "model_divergence_unexplained" in result["incomplete_findings"]


def test_synthesis_must_match_vfinal_manifest_and_position(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["synthesis"]["chosen_value_per_share"] = 49.0
    assert "synthesis_v_final_mismatch" in _validate(tmp_path, payload)["invalid_findings"]


def test_unknown_model_source_is_invalid(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False); payload["models"][0]["source_ids"] = ["invented_model_database"]
    assert any("source_unresolved" in x for x in _validate(tmp_path, payload)["invalid_findings"])


def test_model_ids_must_be_bound_to_declared_chapters(tmp_path: Path) -> None:
    payload = _payload(tmp_path, freeze=False)
    report = "## Ch12 估值\n没有模型绑定\n\n## Ch13 DDM\n[valuation: invented.model]"
    result = validate_valuation_model_ledger(payload, output_dir=tmp_path, report_text=report, enforced=True)
    assert any("valuation_reference_missing" in x for x in result["incomplete_findings"])
    assert "unknown_valuation_reference:invented.model" in result["invalid_findings"]


def test_valid_model_is_bound_then_frozen_without_llm_chapter_rewrite(tmp_path: Path) -> None:
    initialize_valuation_model_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path, freeze=False)
    chapters = tmp_path / "chapters"; chapters.mkdir()
    (chapters / "_ch12.md").write_text("## Ch12 估值\n原有分析正文", encoding="utf-8")
    (chapters / "_ch13.md").write_text("## Ch13 DDM\n原有分析正文", encoding="utf-8")
    report = "\n".join(path.read_text(encoding="utf-8") for path in sorted(chapters.glob("_ch*.md")))
    first = persist_valuation_model_ledger(tmp_path, payload, report_text=report)
    assert first["written"] is True and first["validation"]["state"] == "INCOMPLETE"
    binding = bind_valuation_references(tmp_path, payload)
    assert binding["anchors_inserted"] == 2
    rebound = "\n".join(path.read_text(encoding="utf-8") for path in sorted(chapters.glob("_ch*.md")))
    promoted = promote_reviewable_valuation_model(tmp_path, report_text=rebound)
    assert promoted["promoted"] is True
    assert validate_valuation_model_ledger(
        json.loads((tmp_path / "valuation_model.json").read_text(encoding="utf-8")),
        output_dir=tmp_path, report_text=rebound, enforced=True,
    )["state"] == "DECISION_READY"


def test_frozen_valuation_ledger_rejects_drift(tmp_path: Path) -> None:
    initialize_valuation_model_policy(tmp_path, run_id="run", enforced=True)
    original = _payload(tmp_path)
    report = "## Ch12 估值\n[valuation: dcf.fcff.base]\n\n## Ch13 DDM\n[valuation: ddm.normalized]"
    assert persist_valuation_model_ledger(tmp_path, original, report_text=report)["written"] is True
    changed = _payload(tmp_path); changed["models"][1]["result"]["value_per_share"] = 47.0
    changed = build_valuation_model_ledger(tmp_path, changed["company_profile"], changed["models"], changed["synthesis"], change_reason="attempted drift", freeze=True)
    result = persist_valuation_model_ledger(tmp_path, changed, report_text=report)
    assert result["written"] is False and result["valuation_frozen"] is True


def test_new_policy_missing_ledger_maps_completion_to_incomplete(tmp_path: Path) -> None:
    initialize_valuation_model_policy(tmp_path, run_id="run", enforced=True)
    assert evaluate_output_valuation_model(tmp_path, persist=False)["state"] == "INCOMPLETE"
    completion = evaluate_report_completion("draft", str(tmp_path))
    assert completion.status == "INCOMPLETE"
    assert completion.validators["valuation_model"]["state"] == "INCOMPLETE"


def test_invalid_valuation_maps_completion_to_invalid(tmp_path: Path) -> None:
    initialize_valuation_model_policy(tmp_path, run_id="run", enforced=True)
    payload = _payload(tmp_path); payload["models"][0]["basis"]["value_scope"] = "equity"
    (tmp_path / "valuation_model.json").write_text(json.dumps(payload), encoding="utf-8")
    assert evaluate_report_completion("draft", str(tmp_path)).status == "INVALID"


def test_old_output_without_policy_remains_skip(tmp_path: Path) -> None:
    assert evaluate_output_valuation_model(tmp_path, persist=False)["state"] == "SKIP"


def test_valuation_tool_is_auto_discoverable() -> None:
    registry = ToolRegistry(); registry.auto_discover("turtle_agent.tools.write_tools")
    assert "write_valuation_model_ledger" in registry.list_tools()


def test_valuation_failure_routes_quantitative_and_summary_chapters() -> None:
    completion = {"blocking_findings": ["Valuation model: INCOMPLETE: valuation_model_missing"]}
    assert _repair_targets_from_completion(completion) == (14, 0)
