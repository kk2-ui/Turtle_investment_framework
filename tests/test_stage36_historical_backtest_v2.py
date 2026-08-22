from __future__ import annotations

from copy import deepcopy

from scripts.historical_backtest import (
    CASE_SCHEMA_VERSION_V2,
    SETTLEMENT_SCHEMA_VERSION_V2,
    validate_case,
    validate_settlement,
    validate_settlement_series,
)
from tests.test_stage36_historical_backtest_pilot import _case, _settlement


def _v2_case() -> dict:
    case = deepcopy(_case())
    case["schema_version"] = CASE_SCHEMA_VERSION_V2
    case["purpose"] = "INVESTMENT_DECISION"
    for claim in case["calibration_ledger"]["claims"]:
        outcome = claim["observable_outcome"]
        start = outcome.pop("period_start")
        end = outcome.pop("period_end")
        outcome["measurement_period"] = {
            "kind": "REPORTING_PERIOD",
            "start": start,
            "end": end,
        }
        outcome["observation_window"] = {
            "opens_after": "2021-08-31T18:00:00+08:00",
            "closes_at": "2022-08-31T18:00:00+08:00",
        }
    return case


def _v2_settlement() -> dict:
    settlement = deepcopy(_settlement())
    settlement["schema_version"] = SETTLEMENT_SCHEMA_VERSION_V2
    for source in settlement["actual_sources"]:
        source["content_access"] = "BODY_READ"
    for observation in settlement["actual_outcomes"]["operating_observations"]:
        start = observation.pop("period_start")
        end = observation.pop("period_end")
        observation["measurement_period"] = {
            "kind": "REPORTING_PERIOD",
            "start": start,
            "end": end,
        }
    return settlement


def _company_judgment_case() -> dict:
    """A price-free case with one due and one future operating judgment."""
    case = _v2_case()
    case["purpose"] = "COMPANY_JUDGMENT_ONLY"
    case["route"] = "DUAL"
    case["forecast"]["terminal_handling"] = "DUAL_TERMINAL_PATH"
    case["price_identity"] = {
        "primary_route": "PRIMARY_ROUTE_UNKNOWN",
        "primary_price_identity": "UNKNOWN",
        "prices": [],
    }
    case.pop("investment_decision")
    claims = case["calibration_ledger"]["claims"]
    claims[0]["forward_judgment_id"] = "fj.owner-cash-early"
    claims[0]["prediction"]["resolution_due"] = "2022-03-31"
    future = deepcopy(claims[0])
    future["claim_id"] = "HBTCLM:minority-cash-access"
    future["forward_judgment_id"] = "fj.owner-cash-terminal"
    future["prediction"].update({"horizon": "FY2025 results", "resolution_due": "2026-08-31"})
    future["observable_outcome"].update({
        "measurement_period": {"kind": "REPORTING_PERIOD", "start": "2025-01-01", "end": "2025-12-31"},
        "observation_window": {
            "opens_after": "2025-08-31T18:00:00+08:00",
            "closes_at": "2026-08-31T18:00:00+08:00",
        },
    })
    claims[1] = future
    case["report_freeze"]["frozen_report"]["claim_ids"] = [claim["claim_id"] for claim in claims]
    case["report_freeze"]["independent_review"]["claim_reviews"][1].update({
        "disposition": "SUPPORTED",
        "notes": ["远期经营预测及其结算窗口已冻结。"],
    })
    return case


def _company_judgment_early_settlement() -> dict:
    settlement = _v2_settlement()
    settlement.update({
        "settlement_series_id": "HBTSETS:TEST:COMPANY-JUDGMENT",
        "settlement_sequence": 1,
        "previous_settlement_id": None,
        "settlement_stage": "EARLY_MECHANISM",
    })
    settlement["actual_sources"] = settlement["actual_sources"][:1]
    settlement["model_forecast_error"]["status"] = "PARTIAL"
    settlement["model_forecast_error"]["claim_settlements"][1].update({
        "frozen_disposition": "PREDICTION",
        "status": "PARTIAL",
        "observation_ids": [],
    })
    settlement["report_coverage"]["claim_reviews"][1]["disposition"] = "SUPPORTED"
    settlement["report_coverage"]["supported_claim_count"] = 2
    settlement["investment_return_outcome"] = {
        "status": "NOT_APPLICABLE",
        "action": "UNKNOWN",
        "frozen_action": "UNKNOWN",
        "frozen_price_identity": "UNKNOWN",
        "total_return": None,
        "benchmark_return": None,
        "currency": "HKD",
        "notes": ["This is a company-judgment-only settlement; price and investment return are intentionally excluded."],
        "execution": {
            "execution_rule": "No investment action is part of a company-judgment-only case.",
            "fill_status": "NOT_APPLICABLE",
            "entry": {"date": None, "price": None, "quantity": None, "currency": None, "source_ids": []},
            "exit": {"status": "NOT_APPLICABLE", "date": None, "price": None, "quantity": None, "currency": None, "source_ids": []},
        },
        "cash_flow_ledger": [],
        "corporate_actions": [],
        "taxes_fees_fx": {"tax_rate": 0.1, "transaction_fee_rate": 0.001, "dividend_tax_rate": 0.1, "base_currency": "HKD", "fx_rule": "仅在报告冻结时使用历史可见汇率"},
        "benchmark_identity": {
            "benchmark_id": "NOT_APPLICABLE",
            "market": "NOT_APPLICABLE",
            "currency": "HKD",
            "return_basis": "NOT_APPLICABLE",
            "calculation_rule": "Investment return is outside this case purpose.",
            "source_ids": [],
        },
    }
    return settlement


def _licensed_industry_actual_source() -> dict:
    source_version = "avc-room-ac-retail-2021-original"
    return {
        "source_id": "AVC:000651:AC:2021:ORIGINAL",
        "source_type": "LICENSED_INDUSTRY_DATA",
        "official": False,
        "published_at": "2022-03-25T10:00:00+08:00",
        "source_version": source_version,
        "data_as_of": "2021-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
        "content_access": "BODY_READ",
        "industry_data_contract": {
            "schema_version": "phase10-independent-industry-data.v2",
            "provider_id": "AVC",
            "dataset_id": "room-air-conditioner-retail-tracker",
            "release": {
                "release_id": "AVC-AC-2021-ORIGINAL",
                "version_id": source_version,
                "published_at": "2022-03-25T10:00:00+08:00",
                "data_as_of": "2021-12-31",
                "revision_status": "ORIGINAL_HISTORICAL",
                "revision_id": "ORIGINAL",
                "revision_published_at": None,
            },
            "query_identity": {
                "query_id": "AVC-QUERY-ROOM-AC-CN-2021-SELL-OUT",
                "parameters": {"geography": "CN domestic", "product": "room air conditioner", "channel": "retail"},
            },
            "measurement_profile": {
                "methodology_disclosure": "PROVIDER_METHOD_DOCUMENTED",
                "methodology_locator": {"statement": "供应商说明了零售面板覆盖与口径。", "locator": "README.md#methodology"},
                "error_status": "UNQUANTIFIED",
                "permitted_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE",
                "known_limitations": [{
                    "statement": "零售面板不等于公司会计收入，覆盖和品牌映射可能变化。",
                    "conservative_treatment": "只用于同一供应商、同一映射下的相对变化；不与其他来源平均。",
                }],
                "disagreement_treatment": "DO_NOT_AVERAGE_REOPEN_MECHANISM",
            },
            "metric": {
                "metric_id": "domestic_room_ac_retail_value_share",
                "unit": "%",
                "semantic": "RETAIL_SELL_OUT",
                "provider_definition": {
                    "statement": "同口径中国家用空调品牌零售额份额。",
                    "locator": "README.md#metric-definition",
                },
                "shipment_sell_in_status": "NOT_APPLICABLE",
            },
            "scope": {
                "geography": "中国大陆国内零售市场",
                "product_mapping": {"mapping_id": "AVC-ROOM-AC-v1", "definition": "家用房间空调。"},
                "channel_mapping": {"mapping_id": "AVC-RETAIL-v1", "definition": "同口径零售渠道。"},
                "brand_mapping": {"mapping_id": "AVC-GREE-v1", "definition": "供应商品牌到格力品牌口径。"},
                "denominator": {"mapping_id": "AVC-ALL-BRANDS-v1", "definition": "同范围内全部品牌零售额。"},
            },
        },
    }


def _pre_cutoff_licensed_industry_source() -> dict:
    source = _licensed_industry_actual_source()
    source.update({
        "source_id": "AVC:000651:AC:2020:ORIGINAL",
        "source_version": "avc-room-ac-retail-2020-original",
        "published_at": "2021-03-25T10:00:00+08:00",
        "data_as_of": "2020-12-31",
        "admissible": True,
    })
    release = source["industry_data_contract"]["release"]
    release.update({
        "release_id": "AVC-AC-2020-ORIGINAL",
        "version_id": source["source_version"],
        "published_at": source["published_at"],
        "data_as_of": source["data_as_of"],
    })
    source["industry_data_contract"]["query_identity"]["query_id"] = "AVC-QUERY-ROOM-AC-CN-2020-SELL-OUT"
    return source


def _licensed_industry_series_contract(source: dict) -> dict:
    contract = source["industry_data_contract"]
    scope = contract["scope"]
    return {
        "pre_cutoff_source_id": source["source_id"],
        "provider_id": contract["provider_id"],
        "dataset_id": contract["dataset_id"],
        "metric_id": contract["metric"]["metric_id"],
        "semantic": contract["metric"]["semantic"],
        "geography": scope["geography"],
        "product_mapping_id": scope["product_mapping"]["mapping_id"],
        "channel_mapping_id": scope["channel_mapping"]["mapping_id"],
        "brand_mapping_id": scope["brand_mapping"]["mapping_id"],
        "denominator_mapping_id": scope["denominator"]["mapping_id"],
    }


def _rival_pair_case(*, rival_prediction: dict) -> dict:
    case = _v2_case()
    claim = case["calibration_ledger"]["claims"][0]
    claim["forward_judgment_id"] = "fj.cash-early"
    claim["prediction"].update({"value": 0.18, "resolution_due": "2022-03-31"})
    early_rival = deepcopy(rival_prediction)
    early_rival["resolution_due"] = "2022-03-31"
    terminal = deepcopy(claim)
    terminal["claim_id"] = "HBTCLM:minority-cash-access"
    terminal["statement"] = claim["statement"]
    terminal["forward_judgment_id"] = "fj.cash-terminal"
    terminal["prediction"].update({"horizon": "FY2022 results", "resolution_due": "2023-03-31"})
    terminal["observable_outcome"].update({
        "measurement_period": {"kind": "REPORTING_PERIOD", "start": "2022-01-01", "end": "2022-12-31"},
        "observation_window": {
            "opens_after": "2022-08-31T18:00:00+08:00",
            "closes_at": "2023-03-31T18:00:00+08:00",
        },
    })
    terminal_rival = deepcopy(rival_prediction)
    terminal_rival.update({"horizon": "FY2022 results", "resolution_due": "2023-03-31"})
    case["calibration_ledger"]["claims"][1] = terminal
    case["report_freeze"]["independent_review"]["claim_reviews"][1].update({
        "disposition": "SUPPORTED",
        "notes": ["终局经营预测及其可结算口径已冻结。"],
    })
    case["calibration_ledger"]["rival_hypothesis_pairs"] = [{
        "pair_id": "RHP:cash-quality",
        "competitive_test_id": "test.cash-quality",
        "primary_mechanism_chain_id": "mechanism.cash-normalizes",
        "rival_mechanism_chain_id": "mechanism.cash-erodes",
        "discriminators": [{
            "signal_id": "RHPSIG:cash-early", "sequence": 1, "stage": "EARLY_MECHANISM",
            "forward_judgment_id": "fj.cash-early", "claim_id": claim["claim_id"],
            "primary_prediction": deepcopy(claim["prediction"]), "rival_prediction": early_rival,
        }, {
            "signal_id": "RHPSIG:cash-terminal", "sequence": 2, "stage": "TERMINAL_OPERATING",
            "forward_judgment_id": "fj.cash-terminal", "claim_id": terminal["claim_id"],
            "primary_prediction": deepcopy(terminal["prediction"]), "rival_prediction": terminal_rival,
        }],
    }]
    case["calibration_ledger"]["analogy_transfer_cards"] = [{
        "card_id": "ATC:cash-quality", "target_pair_id": "RHP:cash-quality",
    }]
    return case


def _rival_pair_settlement() -> dict:
    settlement = _v2_settlement()
    settlement["model_forecast_error"]["metrics"][0]["forecast_value"] = 0.18
    settlement["settlement_as_of"] = "2023-03-31T18:00:00+08:00"
    terminal_source = deepcopy(settlement["actual_sources"][0])
    terminal_source.update({
        "source_id": "AR:00506:2022",
        "published_at": "2023-03-25T18:00:00+08:00",
        "source_version": "2022-original",
        "data_as_of": "2022-12-31",
    })
    settlement["actual_sources"].append(terminal_source)
    settlement["operating_source_timeline"]["source_ids"].append(terminal_source["source_id"])
    terminal_observation = deepcopy(settlement["actual_outcomes"]["operating_observations"][0])
    terminal_observation.update({
        "observation_id": "HBTOBS:owner-cash:FY2022",
        "claim_id": "HBTCLM:minority-cash-access",
        "measurement_period": {"kind": "REPORTING_PERIOD", "start": "2022-01-01", "end": "2022-12-31"},
        "source_ids": [terminal_source["source_id"]],
    })
    settlement["actual_outcomes"]["operating_observations"].append(terminal_observation)
    terminal_metric = deepcopy(settlement["model_forecast_error"]["metrics"][0])
    terminal_metric.update({
        "claim_id": "HBTCLM:minority-cash-access",
        "observation_id": terminal_observation["observation_id"],
        "actual_source_ids": [terminal_source["source_id"]],
    })
    settlement["model_forecast_error"]["metrics"].append(terminal_metric)
    settlement["model_forecast_error"]["claim_settlements"][1].update({
        "claim_id": "HBTCLM:minority-cash-access",
        "frozen_disposition": "PREDICTION",
        "status": "CALCULATED",
        "observation_ids": [terminal_observation["observation_id"]],
    })
    settlement["report_coverage"]["claim_reviews"][1]["disposition"] = "SUPPORTED"
    settlement["report_coverage"]["supported_claim_count"] = 2
    return settlement


def test_v2_accepts_reporting_period_separate_from_post_freeze_window() -> None:
    case = _v2_case()
    settlement = _v2_settlement()

    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"


def test_v2_rejects_metadata_only_or_window_outside_operating_observations() -> None:
    case = _v2_case()
    metadata_only = _v2_settlement()
    metadata_only["actual_sources"][0]["content_access"] = "METADATA_ONLY"
    result = validate_settlement(metadata_only, case=case)
    assert "actual_outcomes.operating_observations[0]:source_body_not_read:AR:00506:2021" in result["invalid_findings"]

    window_outside = _v2_settlement()
    case["calibration_ledger"]["claims"][0]["observable_outcome"]["observation_window"]["closes_at"] = "2022-03-24T18:00:00+08:00"
    result = validate_settlement(window_outside, case=case)
    assert "actual_outcomes.operating_observations[0]:source_published_after_observation_window:AR:00506:2021" in result["invalid_findings"]


def test_selected_fj_requires_its_frozen_reported_label_and_locator() -> None:
    case = _v2_case()
    claim = case["calibration_ledger"]["claims"][0]
    claim["forward_judgment_id"] = "fj.owner-cash"
    case["calibration_ledger"]["selection_admission"] = {
        "status": "SELECTION_ADMITTED",
        "selection_forward_judgment_ids": ["fj.owner-cash"],
    }
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
    settlement = _v2_settlement()
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation.update({
        "reported_file_scope": "FY2021 annual report",
        "reported_label": "ordinary-share owner cash per share",
        "reported_locator": "Cash conversion note / ordinary-share bridge",
    })

    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"

    proxy = deepcopy(settlement)
    proxy["actual_outcomes"]["operating_observations"][0]["reported_label"] = "reported revenue"
    result = validate_settlement(proxy, case=case)
    assert (
        "actual_outcomes.operating_observations[0]:reported_disclosure_does_not_match_metric_reconstruction_contract"
        in result["invalid_findings"]
    )


def test_v2_rejects_a_non_numeric_result_instead_of_calling_both_mechanisms_wrong() -> None:
    case = _v2_case()
    settlement = _v2_settlement()
    settlement["actual_outcomes"]["operating_observations"][0]["value"] = "not disclosed"
    settlement["model_forecast_error"]["metrics"][0]["actual_value"] = "not disclosed"

    result = validate_settlement(settlement, case=case)

    assert result["state"] == "INVALID"
    assert (
        "actual_outcomes.operating_observations[0]:value_must_be_numeric_for_quantitative_prediction"
        in result["invalid_findings"]
    )
    assert (
        "model_forecast_error.metrics[0]:actual_value_must_be_numeric_for_point_prediction"
        in result["invalid_findings"]
    )


def test_v2_event_window_requires_an_in_window_event_period_but_not_report_period_end() -> None:
    case = _v2_case()
    outcome = case["calibration_ledger"]["claims"][0]["observable_outcome"]
    outcome["measurement_period"] = {
        "kind": "EVENT_WINDOW",
        "start": "2022-03-25",
        "end": "2022-03-25",
    }
    outcome["allowed_source_types"] = ["ANNUAL_REPORT"]
    settlement = _v2_settlement()
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation["measurement_period"] = deepcopy(outcome["measurement_period"])
    observation["event_period"] = {"start": "2022-03-25", "end": "2022-03-25"}
    settlement["actual_sources"][0].update({
        "source_type": "ANNUAL_REPORT",
        "data_as_of": "2021-12-31",
    })

    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"

    outside_event_period = deepcopy(settlement)
    outside_event_period["actual_outcomes"]["operating_observations"][0]["event_period"] = {
        "start": "2022-03-24", "end": "2022-03-25",
    }
    result = validate_settlement(outside_event_period, case=case)
    assert "actual_outcomes.operating_observations[0].event_period:starts_before_frozen_measurement_period" in result["invalid_findings"]


def test_company_judgment_only_can_settle_due_operating_claims_without_price_or_return() -> None:
    case = _company_judgment_case()
    settlement = _company_judgment_early_settlement()

    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"


def test_company_judgment_forward_judgment_can_settle_from_a_body_read_first_party_web_release() -> None:
    case = _company_judgment_case()
    claim = case["calibration_ledger"]["claims"][0]
    claim["observable_outcome"]["allowed_source_types"] = ["OTHER_OFFICIAL"]
    settlement = _company_judgment_early_settlement()
    source = deepcopy(settlement["actual_sources"][0])
    source.update({
        "source_id": "IR:TEST:FY2021_RESULTS",
        "source_type": "OTHER_OFFICIAL",
        "official": True,
        "source_version": "official-ir-release:FY2021_RESULTS",
        "content_access": "BODY_READ",
    })
    settlement["actual_sources"].append(source)
    settlement["operating_source_timeline"]["source_ids"].append(source["source_id"])
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation["source_ids"] = [source["source_id"]]
    metric = settlement["model_forecast_error"]["metrics"][0]
    metric["actual_source_ids"] = [source["source_id"]]
    settlement["model_forecast_error"]["claim_settlements"][0]["observation_ids"] = [observation["observation_id"]]

    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"

    settlement["actual_sources"][1]["official"] = False
    result = validate_settlement(settlement, case=case)
    assert "actual_sources[1]:official_source_required" in result["invalid_findings"]


def test_company_judgment_forward_judgment_can_settle_with_non_official_versioned_industry_data() -> None:
    case = _company_judgment_case()
    claim = case["calibration_ledger"]["claims"][0]
    pre_cutoff_source = _pre_cutoff_licensed_industry_source()
    case["sources"].append(pre_cutoff_source)
    claim["source_ids"] = [pre_cutoff_source["source_id"]]
    case["report_freeze"]["independent_review"]["claim_reviews"][0]["source_ids"] = [pre_cutoff_source["source_id"]]
    claim["prediction"] = {
        "metric": "domestic_room_ac_retail_value_share",
        "operator": "AT_LEAST",
        "value": 25.0,
        "unit": "%",
        "horizon": "FY2021 retail results",
    }
    claim["threshold"] = {
        "metric": "domestic_room_ac_retail_value_share",
        "operator": "AT_MOST",
        "value": 23.0,
        "unit": "%",
        "consequence": "竞争地位的主机制需要改判。",
    }
    outcome = claim["observable_outcome"]
    outcome.update({
        "metric": "domestic_room_ac_retail_value_share",
        "unit": "%",
        "measurement_basis": "same-product, same-channel domestic retail value share; retail sell-out only",
        "measurement_rule": "仅使用版本、品牌、渠道、产品与分母均冻结的 AVC 零售 sell-out 发布版本。",
        "allowed_source_types": ["LICENSED_INDUSTRY_DATA"],
        "industry_measurement_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE",
        "licensed_industry_series_contract": _licensed_industry_series_contract(pre_cutoff_source),
    })

    settlement = _company_judgment_early_settlement()
    settlement["report_coverage"]["claim_reviews"][0]["source_ids"] = [pre_cutoff_source["source_id"]]
    settlement["actual_sources"].append(_licensed_industry_actual_source())
    settlement["operating_source_timeline"]["source_ids"].append("AVC:000651:AC:2021:ORIGINAL")
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation.update({
        "observation_id": "HBTOBS:retail-share:FY2021",
        "metric": "domestic_room_ac_retail_value_share",
        "value": 24.5,
        "unit": "%",
        "measurement_basis": outcome["measurement_basis"],
        "source_ids": ["AVC:000651:AC:2021:ORIGINAL"],
    })
    metric = settlement["model_forecast_error"]["metrics"][0]
    metric.update({
        "observation_id": "HBTOBS:retail-share:FY2021",
        "metric": "domestic_room_ac_retail_value_share",
        "forecast_value": 25.0,
        "actual_value": 24.5,
        "unit": "%",
        "actual_source_ids": ["AVC:000651:AC:2021:ORIGINAL"],
    })
    settlement["model_forecast_error"]["claim_settlements"][0]["observation_ids"] = ["HBTOBS:retail-share:FY2021"]

    assert validate_case(case)["state"] == "REVIEWABLE"
    assert validate_settlement(settlement, case=case)["state"] == "REVIEWABLE"

    settlement["actual_sources"][1]["official"] = True
    result = validate_settlement(settlement, case=case)
    assert "actual_sources[1]:independent_industry_source_must_be_non_official" in result["invalid_findings"]

    channel_mismatch = _company_judgment_early_settlement()
    channel_mismatch["report_coverage"]["claim_reviews"][0]["source_ids"] = [pre_cutoff_source["source_id"]]
    mismatched_source = _licensed_industry_actual_source()
    mismatched_source["industry_data_contract"]["scope"]["channel_mapping"]["mapping_id"] = "AVC-ONLINE-v1"
    channel_mismatch["actual_sources"].append(mismatched_source)
    channel_mismatch["operating_source_timeline"]["source_ids"].append(mismatched_source["source_id"])
    mismatch_observation = channel_mismatch["actual_outcomes"]["operating_observations"][0]
    mismatch_observation.update({
        "observation_id": "HBTOBS:retail-share:FY2021",
        "metric": "domestic_room_ac_retail_value_share",
        "value": 24.5,
        "unit": "%",
        "measurement_basis": outcome["measurement_basis"],
        "source_ids": [mismatched_source["source_id"]],
    })
    mismatch_metric = channel_mismatch["model_forecast_error"]["metrics"][0]
    mismatch_metric.update({
        "observation_id": "HBTOBS:retail-share:FY2021",
        "metric": "domestic_room_ac_retail_value_share",
        "forecast_value": 25.0,
        "actual_value": 24.5,
        "unit": "%",
        "actual_source_ids": [mismatched_source["source_id"]],
    })
    channel_mismatch["model_forecast_error"]["claim_settlements"][0]["observation_ids"] = ["HBTOBS:retail-share:FY2021"]
    mismatch_result = validate_settlement(channel_mismatch, case=case)
    assert (
        "actual_outcomes.operating_observations[0]:licensed_industry_series_does_not_match_frozen_contract"
        in mismatch_result["invalid_findings"]
    )


def test_company_judgment_cannot_settle_a_numeric_claim_from_a_directional_industry_sensor() -> None:
    case = _company_judgment_case()
    claim = case["calibration_ledger"]["claims"][0]
    claim["prediction"] = {
        "metric": "domestic_room_ac_retail_value_share", "operator": "AT_LEAST",
        "value": 25.0, "unit": "%", "horizon": "FY2021 retail results",
    }
    claim["threshold"] = {
        "metric": "domestic_room_ac_retail_value_share", "operator": "AT_MOST",
        "value": 23.0, "unit": "%", "consequence": "需要重新研究竞争机制。",
    }
    outcome = claim["observable_outcome"]
    outcome.update({
        "metric": "domestic_room_ac_retail_value_share", "unit": "%",
        "measurement_basis": "same-product, same-channel domestic retail value share; retail sell-out only",
        "measurement_rule": "仅使用冻结的 AVC 零售版本。",
        "allowed_source_types": ["LICENSED_INDUSTRY_DATA"],
        "industry_measurement_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE",
    })
    settlement = _company_judgment_early_settlement()
    source = _licensed_industry_actual_source()
    source["industry_data_contract"]["measurement_profile"]["permitted_inference"] = "DIRECTIONAL_SENSOR_ONLY"
    settlement["actual_sources"].append(source)
    settlement["operating_source_timeline"]["source_ids"].append(source["source_id"])
    observation = settlement["actual_outcomes"]["operating_observations"][0]
    observation.update({
        "observation_id": "HBTOBS:retail-share:FY2021", "metric": "domestic_room_ac_retail_value_share",
        "value": 24.5, "unit": "%", "measurement_basis": outcome["measurement_basis"],
        "source_ids": [source["source_id"]],
    })

    result = validate_settlement(settlement, case=case)

    assert "actual_sources[1]:industry_data_contract:measurement_profile:unquantified_error_cannot_support_level_inference" not in result["invalid_findings"]
    assert "actual_outcomes.operating_observations[0]:industry_source_not_quantitative:AVC:000651:AC:2021:ORIGINAL" in result["invalid_findings"]


def test_company_judgment_only_rejects_an_early_result_for_a_future_claim() -> None:
    case = _company_judgment_case()
    settlement = _company_judgment_early_settlement()
    settlement["model_forecast_error"]["claim_settlements"][1].update({
        "status": "CALCULATED",
        "observation_ids": ["HBTOBS:owner-cash:FY2021"],
    })

    result = validate_settlement(settlement, case=case)
    assert "calibration_ledger.claims:HBTCLM:minority-cash-access:future_claim_requires_partial_without_observation" in result["invalid_findings"]


def test_company_judgment_settlement_series_is_append_only() -> None:
    case = _company_judgment_case()
    early = _company_judgment_early_settlement()
    later = deepcopy(early)
    later.update({
        "settlement_id": "HBTSET:TEST:2022-09",
        "settlement_as_of": "2022-09-30T18:00:00+08:00",
        "settlement_sequence": 2,
        "previous_settlement_id": early["settlement_id"],
    })

    assert validate_settlement_series([early, later], case=case)["state"] == "REVIEWABLE"

    later["previous_settlement_id"] = "HBTSET:OTHER"
    result = validate_settlement_series([early, later], case=case)
    assert "settlements[1]:previous_settlement_id_does_not_match_predecessor" in result["invalid_findings"]


def test_company_judgment_settlement_series_rejects_rewriting_a_calculated_actual_or_source() -> None:
    case = _company_judgment_case()
    early = _company_judgment_early_settlement()
    later = deepcopy(early)
    later.update({
        "settlement_id": "HBTSET:TEST:2022-09",
        "settlement_as_of": "2022-09-30T18:00:00+08:00",
        "settlement_sequence": 2,
        "previous_settlement_id": early["settlement_id"],
    })

    # A later CJO settlement must append a new observation rather than
    # silently turn the already-settled early fact into a favorable result.
    later["actual_outcomes"]["operating_observations"][0]["value"] = 0.30
    later["model_forecast_error"]["metrics"][0]["actual_value"] = 0.30
    result = validate_settlement_series([early, later], case=case)

    assert (
        "settlements[1]:calculated_claim_observation_payload_rewritten:"
        "HBTCLM:owner-cash:HBTOBS:owner-cash:FY2021"
        in result["invalid_findings"]
    )

    later = deepcopy(early)
    later.update({
        "settlement_id": "HBTSET:TEST:2022-09",
        "settlement_as_of": "2022-09-30T18:00:00+08:00",
        "settlement_sequence": 2,
        "previous_settlement_id": early["settlement_id"],
    })
    later["actual_sources"][0]["source_version"] = "rewritten-source-version"
    result = validate_settlement_series([early, later], case=case)

    assert (
        "settlements[1]:calculated_claim_source_payload_rewritten:"
        "HBTCLM:owner-cash:AR:00506:2021"
        in result["invalid_findings"]
    )


def test_rival_pair_outcome_is_derived_from_the_same_official_operating_observation() -> None:
    case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_MOST", "value": 0.15,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })
    result = validate_settlement(_rival_pair_settlement(), case=case)

    assert result["state"] == "REVIEWABLE"
    pair = result["rival_hypothesis_pair_outcomes"][0]
    assert pair["pair_verdict"] == "SUPPORTS_PRIMARY"
    assert {signal["verdict"] for signal in pair["signals"]} == {"SUPPORTS_PRIMARY"}


def test_rival_pair_rejects_a_nested_predicate_before_settlement() -> None:
    case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_LEAST", "value": 0.20,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })

    result = validate_case(case)

    assert result["state"] == "INVALID"
    assert (
        "calibration_ledger.rival_hypothesis_pairs[0].discriminators[0]:predictions_do_not_allow_both_sides_to_win"
        in result["invalid_findings"]
    )


def test_rival_pair_never_accepts_a_handwritten_or_one_sided_verdict(tmp_path=None) -> None:
    case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_MOST", "value": 0.18,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })
    settlement = _rival_pair_settlement()
    settlement["model_forecast_error"]["rival_hypothesis_pair_outcomes"] = [{"pair_id": "RHP:cash-quality", "pair_verdict": "SUPPORTS_RIVAL"}]
    result = validate_settlement(settlement, case=case)

    assert "model_forecast_error:rival_hypothesis_pair_outcomes_must_be_derived_not_submitted" in result["invalid_findings"]
    assert result["rival_hypothesis_pair_outcomes"][0]["pair_verdict"] == "MIXED"


def test_rival_pair_distinguishes_shared_prediction_from_shared_failure() -> None:
    both_met_case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_MOST", "value": 0.20,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })
    both_met = validate_settlement(_rival_pair_settlement(), case=both_met_case)
    both_met_pair = both_met["rival_hypothesis_pair_outcomes"][0]

    neither_met_case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_MOST", "value": 0.17,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })
    neither_met_settlement = _rival_pair_settlement()
    for metric in neither_met_settlement["model_forecast_error"]["metrics"]:
        metric["actual_value"] = 0.175
    for observation in neither_met_settlement["actual_outcomes"]["operating_observations"]:
        observation["value"] = 0.175
    neither_met = validate_settlement(neither_met_settlement, case=neither_met_case)
    neither_met_pair = neither_met["rival_hypothesis_pair_outcomes"][0]

    assert both_met_pair["pair_verdict"] == "MIXED"
    assert {signal["comparison_state"] for signal in both_met_pair["signals"]} == {"BOTH_MET"}
    assert both_met_pair["terminal_comparison_state"] == "BOTH_MET"
    assert neither_met_pair["pair_verdict"] == "MIXED"
    assert {signal["comparison_state"] for signal in neither_met_pair["signals"]} == {"NEITHER_MET"}
    assert neither_met_pair["terminal_comparison_state"] == "NEITHER_MET"


def test_rival_pair_requires_the_rival_predicate_before_it_can_support_the_rival() -> None:
    case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_MOST", "value": 0.18,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })
    case["calibration_ledger"]["claims"][0]["prediction"]["value"] = 0.20
    case["calibration_ledger"]["claims"][1]["prediction"]["value"] = 0.20
    for signal in case["calibration_ledger"]["rival_hypothesis_pairs"][0]["discriminators"]:
        signal["primary_prediction"]["value"] = 0.20
    settlement = _rival_pair_settlement()
    for metric in settlement["model_forecast_error"]["metrics"]:
        metric["forecast_value"] = 0.20
    result = validate_settlement(settlement, case=case)

    assert result["state"] == "REVIEWABLE"
    assert result["rival_hypothesis_pair_outcomes"][0]["pair_verdict"] == "SUPPORTS_RIVAL"


def test_company_judgment_pair_keeps_a_future_signal_not_yet_due_without_return_data() -> None:
    case = _company_judgment_case()
    early = case["calibration_ledger"]["claims"][0]
    future = case["calibration_ledger"]["claims"][1]
    early_rival = deepcopy(early["prediction"])
    early_rival.update({"operator": "AT_MOST", "value": 0.15})
    terminal_rival = deepcopy(future["prediction"])
    terminal_rival.update({"operator": "AT_MOST", "value": 0.15})
    case["calibration_ledger"]["rival_hypothesis_pairs"] = [{
        "pair_id": "RHP:future-cash", "competitive_test_id": "test.future-cash",
        "primary_mechanism_chain_id": "mechanism.future-primary", "rival_mechanism_chain_id": "mechanism.future-rival",
        "discriminators": [{
            "signal_id": "RHPSIG:future-early", "sequence": 1, "stage": "EARLY_MECHANISM",
            "forward_judgment_id": early["forward_judgment_id"], "claim_id": early["claim_id"],
            "primary_prediction": deepcopy(early["prediction"]), "rival_prediction": early_rival,
        }, {
            "signal_id": "RHPSIG:future-terminal", "sequence": 2, "stage": "TERMINAL_OPERATING",
            "forward_judgment_id": future["forward_judgment_id"], "claim_id": future["claim_id"],
            "primary_prediction": deepcopy(future["prediction"]), "rival_prediction": terminal_rival,
        }],
    }]
    case["calibration_ledger"]["analogy_transfer_cards"] = [{"card_id": "ATC:future-cash", "target_pair_id": "RHP:future-cash"}]
    settlement = _company_judgment_early_settlement()
    result = validate_settlement(settlement, case=case)

    assert result["state"] == "REVIEWABLE"
    assert result["rival_hypothesis_pair_outcomes"][0]["pair_verdict"] == "NOT_YET_DUE"
    assert settlement["investment_return_outcome"]["status"] == "NOT_APPLICABLE"


def test_rival_pair_rejects_a_copied_early_signal_as_a_terminal_outcome() -> None:
    case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_MOST", "value": 0.15,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })
    early, terminal = case["calibration_ledger"]["rival_hypothesis_pairs"][0]["discriminators"]
    terminal.update({
        "forward_judgment_id": early["forward_judgment_id"],
        "claim_id": early["claim_id"],
        "primary_prediction": deepcopy(early["primary_prediction"]),
        "rival_prediction": deepcopy(early["rival_prediction"]),
    })

    result = validate_case(case)

    findings = result["invalid_findings"]
    prefix = "calibration_ledger.rival_hypothesis_pairs[0]"
    assert result["state"] == "INVALID"
    assert prefix + ".discriminators[1]:forward_judgment_reused" in findings
    assert prefix + ":early_and_terminal_claims_must_differ" in findings
    assert prefix + ":early_and_terminal_forward_judgments_must_differ" in findings
    assert prefix + ":early_and_terminal_observation_windows_must_differ" in findings


def test_rival_pair_requires_each_discriminator_to_bind_its_own_frozen_claim() -> None:
    case = _rival_pair_case(rival_prediction={
        "metric": "ordinary_share_owner_cash_per_share", "operator": "AT_MOST", "value": 0.15,
        "unit": "HKD/share", "horizon": "FY2021 results",
    })
    early, terminal = case["calibration_ledger"]["rival_hypothesis_pairs"][0]["discriminators"]
    terminal["claim_id"] = early["claim_id"]

    result = validate_case(case)

    assert result["state"] == "INVALID"
    assert (
        "calibration_ledger.rival_hypothesis_pairs[0].discriminators[1]"
        ":claim_id_does_not_match_forward_judgment"
        in result["invalid_findings"]
    )
