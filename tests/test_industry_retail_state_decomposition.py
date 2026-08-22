from __future__ import annotations

from copy import deepcopy

from scripts.industry_retail_state_decomposition import (
    decompose_industry_retail_state,
    validate_industry_retail_state_decomposition,
)


def _source() -> dict:
    return {
        "source_id": "AVC:000651:ROOMAC:2025Q2:ORIGINAL",
        "source_version": "avc-room-ac-2025q2-original",
        "source_type": "LICENSED_INDUSTRY_DATA",
        "official": False,
        "admissible": True,
        "title": "中国家用空调零售历史版本",
        "published_at": "2025-07-15T10:00:00+08:00",
        "data_as_of": "2025-06-30",
        "revision_policy": "ORIGINAL_VINTAGE",
        "package_path": "industry/avc-room-ac-2025q2.csv",
        "content_representation": "LICENSED_DATA_EXPORT",
        "industry_data_contract": {
            "schema_version": "phase10-independent-industry-data.v2",
            "provider_id": "AVC", "dataset_id": "room-air-conditioner-retail-tracker",
            "release": {
                "release_id": "AVC-ROOM-AC-2025Q2-ORIGINAL",
                "version_id": "avc-room-ac-2025q2-original",
                "published_at": "2025-07-15T10:00:00+08:00", "data_as_of": "2025-06-30",
                "revision_status": "ORIGINAL_HISTORICAL", "revision_id": "ORIGINAL",
                "revision_published_at": None,
            },
            "query_identity": {"query_id": "AVC-ROOM-AC-CN-2025Q2-SELL-OUT", "parameters": {"geography": "CN", "product": "room AC", "channel": "omnichannel", "period": "2025Q2"}},
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
                "metric_id": "retail_sell_out", "unit": "units_and_rmb", "semantic": "RETAIL_SELL_OUT",
                "provider_definition": {"statement": "终端零售 sell-out", "locator": "dictionary#retail"},
                "shipment_sell_in_status": "NOT_APPLICABLE",
            },
            "scope": {
                "geography": "中国大陆", "product_mapping": {"mapping_id": "room-ac-v1", "definition": "room AC"},
                "channel_mapping": {"mapping_id": "retail-omni-v1", "definition": "online/offline retail"},
                "brand_mapping": {"mapping_id": "gree-v1", "definition": "Gree brand group"},
                "denominator": {"mapping_id": "all-brands-v1", "definition": "all covered brands"},
            },
        },
    }


def _cell(period: str, channel: str, price_band: str, market_units: float, gree_units: float, market_value: float, gree_value: float) -> dict:
    return {"period": period, "dimensions": {"channel": channel, "price_band": price_band}, "market_units": market_units, "gree_units": gree_units, "market_value_rmb": market_value, "gree_value_rmb": gree_value}


def _payload() -> dict:
    return {
        "schema_version": "industry-retail-state-decomposition.v1",
        "analysis_id": "IRSD:gree:2024q2-to-2025q2", "purpose": "COMPETITION_DIAGNOSTIC_ONLY",
        "source": _source(), "base_period": "2024Q2", "comparison_period": "2025Q2",
        "dimensions": ["channel", "price_band"],
        "cells": [
            _cell("2024Q2", "online", "low", 1000, 200, 1800000, 360000),
            _cell("2024Q2", "online", "high", 400, 120, 1600000, 520000),
            _cell("2024Q2", "offline", "low", 600, 150, 1200000, 300000),
            _cell("2024Q2", "offline", "high", 500, 200, 2000000, 840000),
            _cell("2025Q2", "online", "low", 1300, 195, 2210000, 312000),
            _cell("2025Q2", "online", "high", 350, 91, 1260000, 336000),
            _cell("2025Q2", "offline", "low", 600, 150, 1140000, 285000),
            _cell("2025Q2", "offline", "high", 650, 260, 2730000, 1170000),
        ],
    }


def test_decomposition_reconciles_and_keeps_source_as_retail_competition_only() -> None:
    result = decompose_industry_retail_state(_payload())
    assert result["computed"] is True
    assert result["source_reference"]["semantic"] == "RETAIL_SELL_OUT"
    assert abs(result["units"]["reconciliation_error"]) < 1e-9
    assert abs(result["value"]["reconciliation_error"]) < 1e-9
    assert set(result["units"]["contributions"]) == {"market_scale", "category_mix", "within_cell_gree_share"}
    assert "owner cash" in result["interpretation_boundary"]["prohibited"]


def test_decomposition_is_invariant_to_cell_order() -> None:
    original = decompose_industry_retail_state(_payload())
    reordered = _payload()
    reordered["cells"] = list(reversed(reordered["cells"]))
    result = decompose_industry_retail_state(reordered)
    assert result["units"]["contributions"] == original["units"]["contributions"]
    assert result["value"]["contributions"] == original["value"]["contributions"]


def test_decomposition_rejects_shipment_and_missing_cell_instead_of_backfilling() -> None:
    shipment = _payload()
    shipment["source"]["industry_data_contract"]["metric"]["semantic"] = "SHIPMENT"
    shipment["source"]["industry_data_contract"]["metric"]["shipment_sell_in_status"] = "SHIPMENT_SEMANTICS_UNRESOLVED"
    result = validate_industry_retail_state_decomposition(shipment)
    assert result["state"] == "INVALID"
    assert "source_must_be_retail_sell_out" in result["invalid_findings"]

    incomplete = _payload()
    incomplete["cells"] = incomplete["cells"][:-1]
    result = decompose_industry_retail_state(incomplete)
    assert result["computed"] is False
    assert "category_cells_must_be_complete_and_stable_across_periods" in result["validation"]["invalid_findings"]


def test_decomposition_rejects_company_revenue_or_value_use_by_contract() -> None:
    payload = _payload()
    payload["purpose"] = "COMPANY_REVENUE_OR_VALUATION"
    result = decompose_industry_retail_state(payload)
    assert result["computed"] is False
    assert "purpose_must_be_competition_diagnostic_only" in result["validation"]["invalid_findings"]


def test_decomposition_keeps_a_directional_vendor_sensor_outside_quantitative_attribution() -> None:
    payload = _payload()
    payload["source"]["industry_data_contract"]["measurement_profile"]["permitted_inference"] = "DIRECTIONAL_SENSOR_ONLY"

    result = validate_industry_retail_state_decomposition(payload)

    assert result["state"] == "INVALID"
    assert "source_measurement_profile_not_sufficient_for_relative_change" in result["invalid_findings"]
