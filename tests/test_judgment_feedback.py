from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.judgment_feedback import JudgmentFeedbackError, build_judgment_feedback_cards
from tests.test_stage36_historical_backtest_v2 import (
    _company_judgment_case,
    _company_judgment_early_settlement,
    _licensed_industry_actual_source,
    _licensed_industry_series_contract,
    _pre_cutoff_licensed_industry_source,
    _rival_pair_settlement,
    _v2_case,
    _v2_settlement,
)


def _forward_case() -> dict:
    case = _v2_case()
    claim = case["calibration_ledger"]["claims"][0]
    claim["prediction"]["resolution_due"] = "2022-03-31"
    claim.update({
        "forward_judgment_id": "fj.owner_cash",
        "central_path_id": "CP:owner-cash",
        "mechanism_chain_ids": ["mechanism.cash-conversion"],
        "transmission": {
            "normalized_earnings": {"direction": "not_material", "basis": "cash-only test", "conservative_treatment": "do not infer earnings improvement"},
            "owner_cash": {"direction": "negative", "basis": "owner cash below frozen floor"},
            "valuation": {"direction": "negative", "basis": "lower owner cash reduces value"},
            "expected_return": {"direction": "negative", "basis": "lower value reduces conditional return"},
        },
        "baseline": {
            "baseline_id": "baseline.owner-cash-carry",
            "method": "CARRY_FORWARD",
            "statement": "Keep the lower prior owner-cash floor.",
            "scope_conditions": "Same frozen official accounting definition.",
            "input_evidence_ids": ["EVD:owner-cash-prior"],
            "prediction": {
                "metric": "ordinary_share_owner_cash_per_share",
                "operator": "AT_LEAST",
                "value": 0.15,
                "unit": "HKD/share",
                "horizon": "FY2021 results",
                "resolution_due": "2022-03-31",
            },
        },
    })
    return case


def _forward_rival_pair_case(*, early_value: float, rival_value: float) -> dict:
    """Freeze distinct early and terminal CJO claims for feedback routing."""
    case = _forward_case()
    early = case["calibration_ledger"]["claims"][0]
    early["prediction"]["value"] = early_value
    terminal = deepcopy(early)
    terminal["claim_id"] = case["calibration_ledger"]["claims"][1]["claim_id"]
    terminal["forward_judgment_id"] = "fj.owner_cash_terminal"
    terminal["prediction"].update({"horizon": "FY2022 results", "resolution_due": "2023-03-31"})
    terminal["baseline"]["prediction"].update({"horizon": "FY2022 results", "resolution_due": "2023-03-31"})
    terminal["observable_outcome"].update({
        "measurement_period": {"kind": "REPORTING_PERIOD", "start": "2022-01-01", "end": "2022-12-31"},
        "observation_window": {
            "opens_after": "2022-08-31T18:00:00+08:00",
            "closes_at": "2023-03-31T18:00:00+08:00",
        },
    })
    case["calibration_ledger"]["claims"][1] = terminal
    case["report_freeze"]["independent_review"]["claim_reviews"][1].update({
        "disposition": "SUPPORTED",
        "notes": ["终局经营预测及其可结算口径已冻结。"],
    })
    early_rival = deepcopy(early["prediction"])
    early_rival.update({"operator": "AT_MOST", "value": rival_value})
    terminal_rival = deepcopy(terminal["prediction"])
    terminal_rival.update({"operator": "AT_MOST", "value": rival_value})
    case["calibration_ledger"]["rival_hypothesis_pairs"] = [{
        "pair_id": "RHP:cash-quality",
        "competitive_test_id": "test.cash-quality",
        "primary_mechanism_chain_id": "mechanism.cash-primary",
        "rival_mechanism_chain_id": "mechanism.cash-rival",
        "discriminators": [{
            "signal_id": "RHPSIG:cash-early", "sequence": 1, "stage": "EARLY_MECHANISM",
            "forward_judgment_id": early["forward_judgment_id"], "claim_id": early["claim_id"],
            "primary_prediction": deepcopy(early["prediction"]), "rival_prediction": early_rival,
        }, {
            "signal_id": "RHPSIG:cash-terminal", "sequence": 2, "stage": "TERMINAL_OPERATING",
            "forward_judgment_id": terminal["forward_judgment_id"], "claim_id": terminal["claim_id"],
            "primary_prediction": deepcopy(terminal["prediction"]), "rival_prediction": terminal_rival,
        }],
    }]
    case["calibration_ledger"]["analogy_transfer_cards"] = [{
        "card_id": "ATC:cash-quality", "target_pair_id": "RHP:cash-quality",
    }]
    return case


def test_feedback_card_keeps_baseline_mechanism_and_return_separate() -> None:
    cards = build_judgment_feedback_cards(_forward_case(), _v2_settlement())

    assert cards["investment_return"] == "SEPARATE_NOT_INCLUDED"
    card = cards["cards"][0]
    assert card["judgment_outcome"]["status"] == "MISSED"
    assert card["baseline"]["outcome"]["status"] == "MET"
    assert card["increment_vs_baseline"] == "BASELINE_BETTER"
    assert card["mechanism_chain_ids"] == ["mechanism.cash-conversion"]
    assert card["transmission"]["owner_cash"]["direction"] == "negative"
    assert card["financial_driver_context"]["state"] == "NOT_PRESENT_IN_LEGACY_FROZEN_CASE"
    assert card["root_cause_review"]["state"] == "PENDING_HUMAN_REVIEW"


def test_feedback_refuses_to_reconstruct_a_missing_frozen_baseline() -> None:
    case = _forward_case()
    case["calibration_ledger"]["claims"][0].pop("baseline")

    with pytest.raises(JudgmentFeedbackError, match="lacks its baseline"):
        build_judgment_feedback_cards(case, _v2_settlement())


def test_feedback_uses_strict_validation_for_a_non_fixture_case(monkeypatch) -> None:
    """P-34 cannot be bypassed by entering through feedback instead of HBT."""
    import scripts.judgment_feedback as feedback_module

    case = _forward_case()
    settlement = _v2_settlement()
    case["case_id"] = "HBTCASE:PRODUCTION-FIXTURE"
    case["report_freeze"]["mode"] = "PRODUCTION_PIPELINE"
    settlement["case_id"] = case["case_id"]
    seen: list[bool] = []

    def reviewed_case(_: dict, *, allow_test_fixtures: bool, **__: object) -> dict:
        seen.append(allow_test_fixtures)
        return {"state": "REVIEWABLE"}

    def reviewed_settlement(_: dict, *, allow_test_fixtures: bool, **__: object) -> dict:
        seen.append(allow_test_fixtures)
        return {"state": "REVIEWABLE"}

    monkeypatch.setattr(feedback_module, "validate_case", reviewed_case)
    monkeypatch.setattr(feedback_module, "validate_settlement", reviewed_settlement)
    feedback_module.build_judgment_feedback_cards(case, settlement)

    assert seen == [False, False]


def test_feedback_rejects_a_request_to_treat_production_case_as_fixture() -> None:
    case = _forward_case()
    case["case_id"] = "HBTCASE:PRODUCTION-FIXTURE"
    case["report_freeze"]["mode"] = "PRODUCTION_PIPELINE"

    with pytest.raises(JudgmentFeedbackError, match="cannot enable test-fixture"):
        build_judgment_feedback_cards(case, _v2_settlement(), allow_test_fixtures=True)


def test_feedback_marks_an_identical_baseline_nondiscriminating_not_selection_success() -> None:
    case = _forward_case()
    claim = case["calibration_ledger"]["claims"][0]
    claim["baseline"]["prediction"] = deepcopy(claim["prediction"])
    case["calibration_ledger"]["selection_admission"] = {
        "status": "SELECTION_ADMITTED",
        "selection_forward_judgment_ids": ["fj.owner_cash"],
    }
    claim["observable_outcome"]["metric_reconstruction_contract"] = {
        "source_targets": [{
            "source_type": "ANNUAL_REPORT",
            "file_scope": "FY2021 annual report",
            "reported_label": "ordinary-share owner cash per share",
            "reported_locator": "cash conversion note / ordinary-share bridge",
        }],
        "prohibited_substitutes": ["reported revenue", "management commentary"],
        "definition_change_action": "MEASUREMENT_MISMATCH",
    }

    settlement = _v2_settlement()
    settlement["actual_outcomes"]["operating_observations"][0].update({
        "reported_file_scope": "FY2021 annual report",
        "reported_label": "ordinary-share owner cash per share",
        "reported_locator": "cash conversion note / ordinary-share bridge",
    })
    card = build_judgment_feedback_cards(case, settlement)["cards"][0]

    assert card["increment_vs_baseline"] == "BASELINE_NONDISCRIMINATING"
    assert card["selection_learning"]["outcome"] == "BASELINE_NONDISCRIMINATING"


def test_feedback_marks_a_selected_metric_definition_change_not_diagnostic() -> None:
    case = _forward_case()
    claim = case["calibration_ledger"]["claims"][0]
    claim["observable_outcome"]["metric_reconstruction_contract"] = {
        "source_targets": [{
            "source_type": "ANNUAL_REPORT",
            "file_scope": "FY2021 annual report",
            "reported_label": "ordinary-share owner cash per share",
            "reported_locator": "Cash conversion note / ordinary-share bridge",
        }],
        "prohibited_substitutes": ["reported revenue", "reported net income", "management commentary"],
        "definition_change_action": "MEASUREMENT_MISMATCH",
    }
    case["calibration_ledger"]["selection_admission"] = {
        "status": "SELECTION_ADMITTED",
        "selection_forward_judgment_ids": ["fj.owner_cash"],
    }
    settlement = _v2_settlement()
    settlement["model_forecast_error"]["status"] = "NOT_CALCULABLE"
    settlement["model_forecast_error"]["claim_settlements"][0].update({
        "status": "NOT_CALCULABLE", "observation_ids": [],
    })
    settlement["model_forecast_error"]["metrics"] = []
    settlement["actual_outcomes"]["operating_observations"][0]["comparability_status"] = "SCOPE_OR_ACCOUNTING_DRIFT"

    card = build_judgment_feedback_cards(case, settlement)["cards"][0]

    assert card["selection_learning"]["outcome"] == "NOT_DIAGNOSTIC"
    assert card["selection_learning"]["reason_code"] == "MEASUREMENT_MISMATCH"


def test_feedback_marks_a_selected_licensed_series_mismatch_not_diagnostic() -> None:
    case = _company_judgment_case()
    claim = case["calibration_ledger"]["claims"][0]
    pre_cutoff_source = _pre_cutoff_licensed_industry_source()
    case["sources"].append(pre_cutoff_source)
    case["report_freeze"]["independent_review"]["claim_reviews"][0]["source_ids"] = [pre_cutoff_source["source_id"]]
    claim.update({
        "forward_judgment_id": "fj.retail-share",
        "prediction": {
            "metric": "domestic_room_ac_retail_value_share", "operator": "AT_LEAST",
            "value": 25.0, "unit": "%", "horizon": "FY2021 retail results",
        },
        "threshold": {
            "metric": "domestic_room_ac_retail_value_share", "operator": "AT_MOST",
            "value": 23.0, "unit": "%", "consequence": "重开竞争机制。",
        },
        "source_ids": [pre_cutoff_source["source_id"]],
        "baseline": {
            "baseline_id": "baseline.retail-share", "method": "CARRY_FORWARD",
            "statement": "保持冻结前同一面板份额。", "scope_conditions": "同一供应商和映射。",
            "input_evidence_ids": ["EVD:retail-share-prior"],
            "prediction": {
                "metric": "domestic_room_ac_retail_value_share", "operator": "AT_LEAST",
                "value": 25.0, "unit": "%", "horizon": "FY2021 retail results",
                "resolution_due": "2022-03-31",
            },
        },
    })
    outcome = claim["observable_outcome"]
    outcome.update({
        "metric": "domestic_room_ac_retail_value_share", "unit": "%",
        "measurement_basis": "same-product, same-channel domestic retail value share; retail sell-out only",
        "measurement_rule": "仅使用同一冻结 AVC panel 的后续 release。",
        "allowed_source_types": ["LICENSED_INDUSTRY_DATA"],
        "industry_measurement_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE",
        "licensed_industry_series_contract": _licensed_industry_series_contract(pre_cutoff_source),
        "metric_reconstruction_contract": {
            "source_targets": [{
                "source_type": "LICENSED_INDUSTRY_DATA", "file_scope": "AVC retail tracker next release",
                "reported_label": "domestic room AC retail value share", "reported_locator": "retail panel / Gree share",
            }],
            "prohibited_substitutes": ["other vendor panel", "shipment share"],
            "definition_change_action": "MEASUREMENT_MISMATCH",
        },
    })
    case["calibration_ledger"]["selection_admission"] = {
        "status": "SELECTION_ADMITTED", "selection_forward_judgment_ids": ["fj.retail-share"],
    }
    settlement = _company_judgment_early_settlement()
    settlement["report_coverage"]["claim_reviews"][0]["source_ids"] = [pre_cutoff_source["source_id"]]
    mismatch_source = _licensed_industry_actual_source()
    mismatch_source["industry_data_contract"]["scope"]["brand_mapping"]["mapping_id"] = "AVC-GREE-NEW-v2"
    settlement["actual_sources"].append(mismatch_source)
    settlement["operating_source_timeline"]["source_ids"].append(mismatch_source["source_id"])
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation.update({
        "observation_id": "HBTOBS:retail-share:FY2021",
        "metric": "domestic_room_ac_retail_value_share", "value": 24.5, "unit": "%",
        "measurement_basis": outcome["measurement_basis"],
        "source_ids": [mismatch_source["source_id"]],
        "comparability_status": "SCOPE_OR_ACCOUNTING_DRIFT",
    })
    settlement["model_forecast_error"].update({"status": "NOT_CALCULABLE", "metrics": []})
    settlement["model_forecast_error"]["claim_settlements"][0].update({
        "status": "NOT_CALCULABLE", "observation_ids": [],
    })

    card = build_judgment_feedback_cards(case, settlement)["cards"][0]

    assert card["selection_learning"]["outcome"] == "NOT_DIAGNOSTIC"
    assert card["selection_learning"]["reason_code"] == "MEASUREMENT_MISMATCH"


def test_feedback_keeps_the_reviewed_four_layer_driver_context() -> None:
    case = _forward_case()
    case["calibration_ledger"]["claims"][0]["financial_driver_ids"] = ["FDBDRV:cash"]
    bridge = {
        "schema_version": "frozen-financial-driver-bridge.v1",
        "ledger_sha256": "frozen-bridge-hash",
        "validation_state": "REVIEWABLE",
        "drivers": [
            {"driver_id": "FDBDRV:demand", "layer": "COMPETITION_DEMAND", "status": "OBSERVED", "observation_ids": ["OBS:demand"]},
            {"driver_id": "FDBDRV:margin", "layer": "UNIT_ECONOMICS", "status": "OBSERVED", "observation_ids": ["OBS:margin"]},
            {"driver_id": "FDBDRV:cash", "layer": "CASH_CONVERSION", "status": "OBSERVED", "observation_ids": ["OBS:cash"]},
            {"driver_id": "FDBDRV:allocation", "layer": "CAPITAL_ALLOCATION", "status": "UNKNOWN", "conservative_treatment": "exclude unresolved allocation outcome"},
        ],
        "allocation_events": [{"event_id": "FDBEV:cash", "classification": "UNRESOLVED"}],
    }
    case["financial_driver_bridge"] = bridge
    case["report_freeze"]["independent_review"]["frozen_case_contract"] = {"financial_driver_bridge": deepcopy(bridge)}

    card = build_judgment_feedback_cards(case, _v2_settlement())["cards"][0]

    context = card["financial_driver_context"]
    assert context["state"] == "FROZEN_REVIEWABLE"
    assert context["linked_driver_ids"] == ["FDBDRV:cash"]
    assert {item["layer"] for item in context["layers"]} == {
        "COMPETITION_DEMAND", "UNIT_ECONOMICS", "CASH_CONVERSION", "CAPITAL_ALLOCATION",
    }
    cash_layer = next(item for item in context["layers"] if item["layer"] == "CASH_CONVERSION")
    assert cash_layer["linked_driver_ids"] == ["FDBDRV:cash"]


def test_feedback_binds_a_claim_to_its_derived_rival_signal_not_the_pair_story() -> None:
    case = _forward_rival_pair_case(early_value=0.10, rival_value=0.05)
    claim = case["calibration_ledger"]["claims"][0]
    claim["rival_hypothesis_pair_id"] = "RHP:cash-quality"
    claim["rival_signal_id"] = "RHPSIG:cash-early"
    settlement = _rival_pair_settlement()
    settlement["model_forecast_error"]["metrics"][0]["forecast_value"] = 0.10
    settlement["model_forecast_error"]["metrics"][1]["forecast_value"] = 0.10
    feedback = build_judgment_feedback_cards(case, settlement)
    rival_feedback = feedback["cards"][0]["rival_hypothesis_feedback"]

    assert rival_feedback["state"] == "DERIVED_FROM_FROZEN_RIVAL_SIGNAL"
    assert rival_feedback["signal_id"] == "RHPSIG:cash-early"
    assert rival_feedback["signal_verdict"] == "SUPPORTS_PRIMARY"
    assert rival_feedback["comparison_state"] == "PRIMARY_ONLY"
    assert rival_feedback["research_implication"] == "DIAGNOSTIC_SUPPORT_FOR_PRIMARY"


def test_feedback_routes_a_shared_failure_to_mechanism_or_measurement_research() -> None:
    case = _forward_rival_pair_case(early_value=0.18, rival_value=0.17)
    claim = case["calibration_ledger"]["claims"][0]
    claim.update({
        "rival_hypothesis_pair_id": "RHP:cash-quality",
        "rival_signal_id": "RHPSIG:cash-early",
    })
    settlement = _rival_pair_settlement()
    settlement["model_forecast_error"]["metrics"][0].update({"forecast_value": 0.18, "actual_value": 0.175})
    settlement["actual_outcomes"]["operating_observations"][0]["value"] = 0.175

    rival_feedback = build_judgment_feedback_cards(case, settlement)["cards"][0]["rival_hypothesis_feedback"]

    assert rival_feedback["signal_verdict"] == "MIXED"
    assert rival_feedback["comparison_state"] == "NEITHER_MET"
    assert rival_feedback["research_implication"] == "MECHANISM_OR_MEASUREMENT_RESEARCH_REDIRECT"
