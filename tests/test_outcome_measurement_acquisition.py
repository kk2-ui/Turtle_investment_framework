from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import outcome_measurement_acquisition as acquisition


_DIMENSIONS = (
    "NORMAL_EARNINGS",
    "ROIC_OR_OPERATING_MARGIN",
    "CASH_CONVERSION_AND_CAPEX_BURDEN",
    "LEVERAGE_AND_FINANCIAL_RESILIENCE",
    "COMPETITIVE_POSITION",
    "PERMANENT_LOSS_RISK",
)
_WINDOWS = ("ONE_YEAR", "THREE_YEAR", "FIVE_YEAR")
_PERIODS = {"ONE_YEAR": "2015-12-31", "THREE_YEAR": "2016-12-31", "FIVE_YEAR": "2017-12-31"}


def _contract(*, company_id: str = "CN:600660", issuer_id: str = "ISSUER:CN:600660") -> dict:
    cells = []
    for dimension in _DIMENSIONS:
        for window in _WINDOWS:
            cells.append({
                "dimension_id": dimension,
                "window_id": window,
                "measurement_id": f"M:{dimension}:{window}",
                "measurement_kind": "BINARY_EVENT",
                "outcome_period_end": _PERIODS[window],
                "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:600660",
                "unit": "RMB",
                "official_source_type": "OFFICIAL_ANNUAL_REPORT",
                "source_field_id": "UNSUPPORTED_FIELD",
                "metric_definition": "contract-defined annual measurement",
                "mismatch_rules": ["NO_SCOPE_SUBSTITUTION"],
                "event_definition": "the frozen annual field is available",
            })
    return {
        "schema_version": "turtle-pit-forecast-outcome-measurement-contract.v1",
        "measurement_contract_id": "OMC:CN600660:V1",
        "measurement_contract_version": 1,
        "decision_contract_ref": {"contract_id": "DC:CN600660:V1", "contract_version": 1},
        "company_id": company_id,
        "issuer_id": issuer_id,
        "cutoff_at": "2014-01-01T00:00:00+08:00",
        "custodian_id": "CUSTODIAN:OUTCOME:CN600660:V1",
        "applied_policy_change_ids": [],
        "cells": cells,
        "object_class": "FORECAST_OUTCOME_MEASUREMENT_CONTRACT",
        "claim_class": "PRE_OUTCOME_SETTLEMENT_DEFINITION",
        "allowed_outputs": ["FORECAST_OUTCOME_ACQUISITION_ONLY"],
    }


def _cell(contract: dict, dimension: str, window: str, *, source_field_id: str, measurement_id: str | None = None) -> None:
    for entry in contract["cells"]:
        if entry["dimension_id"] == dimension and entry["window_id"] == window:
            entry["source_field_id"] = source_field_id
            entry["metric_definition"] = source_field_id
            if measurement_id is not None:
                entry["measurement_id"] = measurement_id
            return
    raise AssertionError("fixture cell missing")


def _inventory(
    contract: dict,
    pdf_path: Path,
    *,
    period_end: str = "2015-12-31",
    source_id: str = "SSE:600660:ANN:20160321:600660_2015_n",
    source_url: str = "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2016-03-21/600660_2015_n.pdf",
    source_available_date: str = "2016-03-21",
) -> dict:
    return {
        "schema_version": acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "INV:CN600660:V1",
        "measurement_contract_ref": {
            "measurement_contract_id": contract["measurement_contract_id"],
            "measurement_contract_version": contract["measurement_contract_version"],
        },
        "custodian_id": contract["custodian_id"],
        "registered_at": "2026-08-26T00:00:00+08:00",
        "documents": [{
            "source_id": source_id,
            "source_url": source_url,
            "local_pdf_path": str(pdf_path),
            "issuer_id": contract["issuer_id"],
            "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:600660",
            "report_period_end": period_end,
            "official_source_type": "OFFICIAL_ANNUAL_REPORT",
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": "registered original annual report; no restatement note on the located statement page",
            "availability_precision": "DATE_ONLY",
            "source_available_date": source_available_date,
            "source_available_at": None,
        }],
        "object_class": acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["FORECAST_OUTCOME_ACQUISITION_ONLY"],
    }


def _synthetic_pages(_: Path) -> list[str]:
    return [
        "合并利润表\n单位：元\n其中：营业收入 1,000 900",
        "合并资产负债表\n单位：元\n资产总计 2,000 1,800",
        "合并现金流量表\n单位：元\n经营活动产生的现金流量净额 500 450",
        "母公司利润表\n单位：元\n一、营业收入 400 390",
        "分部报告\n单位：元\n汽车玻璃 600 550",
    ]


def test_acquisition_keeps_observed_mismatch_and_unknown_fields_independent(tmp_path: Path) -> None:
    """One accounting mismatch cannot erase the report's usable statements."""
    pdf = tmp_path / "registered-official.pdf"
    pdf.write_bytes(b"%PDF-1.7 synthetic static official annual report")
    contract = _contract()
    _cell(contract, "NORMAL_EARNINGS", "ONE_YEAR", source_field_id="CONSOLIDATED_REVENUE_RMB", measurement_id="M:REVENUE")
    _cell(contract, "ROIC_OR_OPERATING_MARGIN", "ONE_YEAR", source_field_id="CONSOLIDATED_TOTAL_ASSETS_RMB", measurement_id="M:ASSETS")
    _cell(contract, "CASH_CONVERSION_AND_CAPEX_BURDEN", "ONE_YEAR", source_field_id="CONSOLIDATED_OPERATING_CASH_FLOW_RMB", measurement_id="M:CASH")
    _cell(contract, "COMPETITIVE_POSITION", "ONE_YEAR", source_field_id="SEGMENT_REVENUE_RMB:汽车玻璃", measurement_id="M:SEGMENT")
    _cell(contract, "LEVERAGE_AND_FINANCIAL_RESILIENCE", "ONE_YEAR", source_field_id="PARENT_REVENUE_RMB", measurement_id="M:PARENT")
    _cell(contract, "PERMANENT_LOSS_RISK", "ONE_YEAR", source_field_id="CONSOLIDATED_NOT_DISCLOSED_RMB", measurement_id="M:UNKNOWN")
    inventory = _inventory(contract, pdf)

    result = acquisition.acquire_outcome_measurements(
        contract, inventory,
        measurement_ids=["M:REVENUE", "M:ASSETS", "M:CASH", "M:SEGMENT", "M:PARENT", "M:UNKNOWN"],
        page_reader=_synthetic_pages,
    )

    assert acquisition.validate_acquisition_result(result)["valid"]
    by_id = {item["measurement_id"]: item for item in result["observations"]}
    assert {key: item["status"] for key, item in by_id.items()} == {
        "M:REVENUE": "OBSERVED", "M:ASSETS": "OBSERVED", "M:CASH": "OBSERVED",
        "M:SEGMENT": "OBSERVED", "M:PARENT": "MEASUREMENT_MISMATCH", "M:UNKNOWN": "UNKNOWN",
    }
    assert by_id["M:REVENUE"]["current_value"] == 1000.0
    assert by_id["M:REVENUE"]["comparative_value"] == 900.0
    assert by_id["M:ASSETS"]["statement_kind"] == "CONSOLIDATED_BALANCE_SHEET"
    assert by_id["M:CASH"]["statement_kind"] == "CONSOLIDATED_CASH_FLOW_STATEMENT"
    assert by_id["M:SEGMENT"]["statement_kind"] == "SEGMENT_OR_PRODUCT_OPERATIONAL_DATA"
    assert by_id["M:PARENT"]["reason"] == "ACCOUNTING_SCOPE_MISMATCH_PARENT_FIELD_CANNOT_SETTLE_CONSOLIDATED_CONTRACT"
    assert by_id["M:UNKNOWN"]["reason"] == "SOURCE_FIELD_ID_NOT_SUPPORTED_BY_LOCAL_ANNUAL_REPORT_CATALOGUE"
    assert by_id["M:REVENUE"]["source"]["pdf_page"] == 1
    assert result["allowed_outputs"] == ["FORECAST_OUTCOME_ACQUISITION_ONLY"]
    assert "prediction" not in json.dumps(result, ensure_ascii=False).casefold()


def test_inventory_must_be_local_static_contract_bound_and_is_checked_before_pdf_read(tmp_path: Path) -> None:
    pdf = tmp_path / "registered-official.pdf"
    pdf.write_bytes(b"%PDF-1.7 synthetic static official annual report")
    contract = _contract()
    _cell(contract, "NORMAL_EARNINGS", "ONE_YEAR", source_field_id="CONSOLIDATED_REVENUE_RMB", measurement_id="M:REVENUE")
    inventory = _inventory(contract, pdf)
    invalid = deepcopy(inventory)
    invalid["documents"][0]["source_url"] = "https://example.com/report.pdf"
    calls: list[Path] = []

    def reader(path: Path) -> list[str]:
        calls.append(path)
        return _synthetic_pages(path)

    with pytest.raises(acquisition.OutcomeMeasurementAcquisitionError, match="static_official_pdf"):
        acquisition.acquire_outcome_measurements(contract, invalid, measurement_ids=["M:REVENUE"], page_reader=reader)
    assert calls == []


def _workspace_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "analy":
            return parent
    return None


def _real_r60_paths() -> tuple[Path, Path] | None:
    root = _workspace_root()
    if root is None:
        return None
    fixture_root = root / "worktrees" / "Turtle_investment_framework" / "docs-r60-fuyao-us-plant-teaching" / "output" / "research" / "r60_fuyao_us_plant_teaching" / "source_package" / "pdf"
    reports = (
        fixture_root / "0003_SSE_600660_ANN_20150217_600660_2014_n.pdf",
        fixture_root / "0004_SSE_600660_ANN_20160321_600660_2015_n.pdf",
    )
    return reports if all(path.is_file() for path in reports) else None


def test_real_registered_static_annual_reports_are_field_level_observable() -> None:
    """Acceptance: two pre-existing SSE annual PDFs remain page-reproducible.

    The files are local, already selected in R60's static source package, and
    are intentionally read without network access.  A missing external fixture
    skips this environment-specific acceptance test rather than replacing it
    with an unregistered web source.
    """
    reports = _real_r60_paths()
    if reports is None:
        pytest.skip("R60 registered local official annual-report PDFs are unavailable in this checkout")
    report_2014, report_2015 = reports
    contract = _contract()
    _cell(contract, "NORMAL_EARNINGS", "ONE_YEAR", source_field_id="CONSOLIDATED_REVENUE_RMB", measurement_id="M:REVENUE:2015")
    _cell(contract, "NORMAL_EARNINGS", "THREE_YEAR", source_field_id="CONSOLIDATED_REVENUE_RMB", measurement_id="M:REVENUE:2016")
    _cell(contract, "LEVERAGE_AND_FINANCIAL_RESILIENCE", "ONE_YEAR", source_field_id="PARENT_REVENUE_RMB", measurement_id="M:PARENT:2015")
    _cell(contract, "PERMANENT_LOSS_RISK", "ONE_YEAR", source_field_id="CONSOLIDATED_NOT_DISCLOSED_RMB", measurement_id="M:UNKNOWN:2015")
    # The two requested outcome periods deliberately match the two independently
    # registered annual reports.  Contract windows remain strictly increasing.
    for cell in contract["cells"]:
        if cell["window_id"] == "ONE_YEAR":
            cell["outcome_period_end"] = "2014-12-31"
        elif cell["window_id"] == "THREE_YEAR":
            cell["outcome_period_end"] = "2015-12-31"
        else:
            cell["outcome_period_end"] = "2016-12-31"
    inventory = _inventory(
        contract,
        report_2014,
        period_end="2014-12-31",
        source_id="SSE:600660:ANN:20150217:600660_2014_n",
        source_url="https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2015-02-16/600660_2014_n.pdf",
        source_available_date="2015-02-17",
    )
    inventory["documents"].append({
        "source_id": "SSE:600660:ANN:20160321:600660_2015_n",
        "source_url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2016-03-21/600660_2015_n.pdf",
        "local_pdf_path": str(report_2015),
        "issuer_id": "ISSUER:CN:600660",
        "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:600660",
        "report_period_end": "2015-12-31",
        "official_source_type": "OFFICIAL_ANNUAL_REPORT",
        "report_scope": "ISSUER_FILING",
        "currency": "RMB",
        "revision_policy": "ORIGINAL_VINTAGE",
        "consolidation_or_restatement_note": "registered original SSE annual report; no restatement note on the located statement page",
        "availability_precision": "DATE_ONLY",
        "source_available_date": "2016-03-21",
        "source_available_at": None,
    })

    result = acquisition.acquire_outcome_measurements(
        contract, inventory,
        measurement_ids=["M:REVENUE:2015", "M:REVENUE:2016", "M:PARENT:2015", "M:UNKNOWN:2015"],
    )

    assert acquisition.validate_acquisition_result(result)["valid"]
    by_id = {item["measurement_id"]: item for item in result["observations"]}
    assert by_id["M:REVENUE:2015"]["status"] == "OBSERVED"
    assert by_id["M:REVENUE:2016"]["status"] == "OBSERVED"
    assert by_id["M:REVENUE:2015"]["source"]["source_id"] == "SSE:600660:ANN:20150217:600660_2014_n"
    assert by_id["M:REVENUE:2016"]["source"]["source_id"] == "SSE:600660:ANN:20160321:600660_2015_n"
    assert by_id["M:REVENUE:2015"]["source"]["pdf_page"] == 54
    assert by_id["M:REVENUE:2016"]["source"]["pdf_page"] == 73
    assert by_id["M:PARENT:2015"]["status"] == "MEASUREMENT_MISMATCH"
    assert by_id["M:UNKNOWN:2015"]["status"] == "UNKNOWN"
