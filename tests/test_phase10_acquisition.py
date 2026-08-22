from __future__ import annotations

import gzip
import json
import sys
from copy import deepcopy
from unittest.mock import patch

import pytest

from scripts.phase10_acquisition import (
    CNInfoAnnouncementExportError,
    CNInfoAnnouncementQueryError,
    DEFAULT_CUTOFF_AT,
    SSEAnnouncementQueryError,
    _download_cninfo_pdf,
    _download_sse_pdf,
    acquire_source_package,
    admit_source_manifest,
    build_post_cutoff_reading_queue,
    build_source_package_selection,
    build_600340_source_manifest,
    compose_company_manifest_with_independent_industry_sources,
    enumerate_independent_industry_sources,
    fetch_600340_sse_manifest,
    fetch_sse_announcement_records,
    enumerate_sse_announcements,
    enumerate_cninfo_announcements,
    fetch_cninfo_announcement_records,
    fetch_cninfo_manifest,
    materialize_pdf_page_markdown,
    normalize_cninfo_announcement_record,
    enumerate_official_web_releases,
    validate_stock_flow_reconciliation,
    validate_source_manifest,
)
from scripts.phase10_pit_runner import PITSourcePackage
from scripts import phase10_acquisition


def _sse_payload(
    page_no: int,
    rows: list[dict[str, object]],
    *,
    total: int,
    page_size: int = 100,
) -> dict[str, object]:
    return {
        "productId": "600340",
        "beginDate": "2018-01-01",
        "endDate": "2020-04-27",
        "pageHelp": {
            "pageNo": page_no,
            "beginPage": page_no,
            "pageSize": page_size,
            "cacheSize": 1,
            "pageCount": (total + page_size - 1) // page_size,
            "total": total,
            "data": rows,
        },
    }


def _cninfo_payload(rows: list[dict[str, object]], *, total: int) -> dict[str, object]:
    return {"totalAnnouncement": total, "announcements": rows}


def _source(source_id: str = "SSE:600340:TEST:1", **updates: object) -> dict:
    record = {
        "source_id": source_id,
        "source_version": "test-v1",
        "source_type": "EXCHANGE_ANNOUNCEMENT",
        "title": "测试公告",
        "published_at": "2020-04-27T18:00:00+08:00",
        "data_as_of": "2020-04-27",
        "revision_policy": "ORIGINAL_VINTAGE",
    }
    record.update(updates)
    return record


def _source_role_provenance(*, role: str, source_id: str) -> dict:
    return {
        "schema_version": "phase10-source-role-provenance.v1",
        "publisher_entity": {
            "entity_id": "REGULATOR:CN:MARKET" if role == "REGULATORY_DISCLOSURE" else "ENTITY:EXTERNAL",
            "legal_name": "External legal entity",
            "entity_kind": "REGULATOR" if role == "REGULATORY_DISCLOSURE" else "OPERATING_ENTITY",
        },
        "subject_entity": {
            "entity_id": "ENTITY:TARGET", "legal_name": "Target legal entity", "entity_kind": "OPERATING_ENTITY",
        },
        "relative_role": role,
        "scope": {
            "scope_id": "SCOPE:CN:AC:2026", "product_or_service": "room air conditioner",
            "geography": "China mainland", "period_start": "2026-01-01", "period_end": "2026-12-31",
        },
        "role_basis": {
            "source_id": source_id, "locator": "p. 12",
            "basis_kind": "REGULATORY_PRIMARY_INSTRUMENT" if role == "REGULATORY_DISCLOSURE" else "PUBLISHER_PRIMARY_DISCLOSURE",
        },
    }


def test_source_role_provenance_requires_entity_scope_and_readable_admitted_basis() -> None:
    source_id = "SSE:600340:ROLE:1"
    valid = _source(source_id, source_role_provenance=_source_role_provenance(
        role="COMPETITOR_DISCLOSURE", source_id=source_id,
    ))
    admitted = admit_source_manifest([valid], cutoff_at="2020-04-28T18:00:00+08:00")
    assert admitted["sources"][0]["admissible"] is True

    missing_entity = deepcopy(valid)
    missing_entity["source_role_provenance"].pop("publisher_entity")
    invalid = admit_source_manifest([missing_entity], cutoff_at="2020-04-28T18:00:00+08:00")
    assert invalid["sources"][0]["admission_status"] == "REJECTED_SOURCE_ROLE_PROVENANCE_INCOMPLETE"

    missing_basis = deepcopy(valid)
    missing_basis["source_role_provenance"]["role_basis"]["source_id"] = "SSE:600340:ABSENT"
    incomplete = admit_source_manifest([missing_basis], cutoff_at="2020-04-28T18:00:00+08:00")
    assert incomplete["sources"][0]["admission_status"] == "REJECTED_SOURCE_ROLE_PROVENANCE_INCOMPLETE"

    invalid_scope = deepcopy(valid)
    invalid_scope["source_role_provenance"]["scope"]["period_start"] = "2026-12-31"
    invalid_scope["source_role_provenance"]["scope"]["period_end"] = "2026-01-01"
    invalid = admit_source_manifest([invalid_scope], cutoff_at="2020-04-28T18:00:00+08:00")
    assert invalid["sources"][0]["admission_status"] == "REJECTED_SOURCE_ROLE_PROVENANCE_INVALID"


def _official_web_release(**updates: object) -> dict:
    record = {
        "release_id": "FY2026Q3_RESULTS",
        "title": "Issuer reports FY2026 Q3 results",
        "url": "https://investor.example.com/news/fy2026-q3-results.html",
        "published_at": "2026-07-29T16:00:00-07:00",
        "data_as_of": "2026-06-28",
        "publisher_name": "Example Corporation",
        "official_publisher_domain": "investor.example.com",
        "language": "en",
    }
    record.update(updates)
    return record


def _industry_source(
    source_id: str = "AVC:000651:AC:2025Q4:ORIGINAL",
    *,
    provider_id: str = "AVC",
    semantic: str = "RETAIL_SELL_OUT",
    shipment_sell_in_status: str = "NOT_APPLICABLE",
    **updates: object,
) -> dict:
    source_version = "avc-room-ac-retail-2025q4-original"
    metric: dict[str, object] = {
        "metric_id": "domestic_room_ac_retail_value_share",
        "unit": "%",
        "semantic": semantic,
        "provider_definition": {
            "statement": "品牌在中国家用空调零售额中的占比，按零售 sell-out 口径。",
            "locator": "README.md#metric-definition",
        },
        "shipment_sell_in_status": shipment_sell_in_status,
    }
    if shipment_sell_in_status == "PROVIDER_DEFINED_SELL_IN":
        metric["provider_sell_in_definition"] = {
            "statement": "供应商向渠道的内销出货，产业在线将其定义为 sell-in。",
            "locator": "README.md#sell-in-definition",
        }
    record: dict[str, object] = {
        "source_id": source_id,
        "source_version": source_version,
        "source_type": "LICENSED_INDUSTRY_DATA",
        "official": False,
        "title": "中国家用空调零售跟踪历史版本",
        "published_at": "2026-01-20T10:00:00+08:00",
        "data_as_of": "2025-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
        "package_path": "industry/avc-room-ac-2025q4.csv",
        "content_representation": "LICENSED_DATA_EXPORT",
        "industry_data_contract": {
            "schema_version": "phase10-independent-industry-data.v2",
            "provider_id": provider_id,
            "dataset_id": "room-air-conditioner-retail-tracker",
            "release": {
                "release_id": "AVC-AC-2025Q4-ORIGINAL",
                "version_id": source_version,
                "published_at": "2026-01-20T10:00:00+08:00",
                "data_as_of": "2025-12-31",
                "revision_status": "ORIGINAL_HISTORICAL",
                "revision_id": "ORIGINAL",
                "revision_published_at": None,
            },
            "query_identity": {
                "query_id": "AVC-QUERY-ROOM-AC-CN-2025Q4-SELL-OUT",
                "parameters": {
                    "geography": "CN domestic",
                    "product": "room air conditioner",
                    "channel": "offline + online retail",
                    "period": "2025Q4",
                },
            },
            "measurement_profile": {
                "methodology_disclosure": "PROVIDER_METHOD_DOCUMENTED",
                "methodology_locator": {"statement": "供应商对覆盖和口径的说明。", "locator": "README.md#methodology"},
                "error_status": "UNQUANTIFIED",
                "permitted_inference": "WITHIN_PROVIDER_RELATIVE_CHANGE",
                "known_limitations": [{
                    "statement": "供应商零售面板不等同于公司会计收入，覆盖和品牌映射可能变化。",
                    "conservative_treatment": "仅比较同一供应商、同一冻结范围内的变化；与其他来源不平均。",
                }],
                "disagreement_treatment": "DO_NOT_AVERAGE_REOPEN_MECHANISM",
            },
            "metric": metric,
            "scope": {
                "geography": "中国大陆国内零售市场",
                "product_mapping": {
                    "mapping_id": "AVC-ROOM-AC-v1",
                    "definition": "仅家用房间空调，不含中央空调工程项目。",
                },
                "channel_mapping": {
                    "mapping_id": "AVC-RETAIL-OMNI-v1",
                    "definition": "线上与线下零售渠道；不与厂商出货混用。",
                },
                "brand_mapping": {
                    "mapping_id": "AVC-GREE-BRAND-v1",
                    "definition": "按供应商品牌表映射格力及可比较品牌。",
                },
                "denominator": {
                    "mapping_id": "AVC-CN-ROOM-AC-ALL-BRANDS-v1",
                    "definition": "同产品、同地域、同渠道覆盖内全部品牌的零售额。",
                },
            },
        },
    }
    record.update(updates)
    return record


def _stock_flow_sources() -> list[dict]:
    boundary = {
        "boundary_id": "AVC-CN-ROOM-AC-RETAIL-2025Q4-v1",
        "geography": "中国大陆国内零售市场",
        "product_mapping_id": "AVC-ROOM-AC-v1",
        "channel_mapping_id": "AVC-RETAIL-OMNI-v1",
        "brand_mapping_id": "AVC-GREE-BRAND-v1",
        "denominator_mapping_id": "AVC-CN-ROOM-AC-ALL-BRANDS-v1",
        "period": "2025Q4",
        "inventory_ownership": "供应方定义的覆盖渠道库存，不含厂内库存。",
        "definition_locator": "README.md#stock-flow-boundary",
    }
    sources: list[dict] = []
    for semantic, source_id, metric_id, sell_in_status in (
        ("RETAIL_SELL_OUT", "AVC:000651:AC:2025Q4:RETAIL", "room_ac_retail_units", "NOT_APPLICABLE"),
        ("SHIPMENT", "AVC:000651:AC:2025Q4:SHIPMENT", "room_ac_channel_shipments", "PROVIDER_DEFINED_SELL_IN"),
        ("INVENTORY_STOCK", "AVC:000651:AC:2025Q4:INVENTORY", "room_ac_channel_inventory", "NOT_APPLICABLE"),
    ):
        source = _industry_source(
            source_id=source_id, semantic=semantic,
            shipment_sell_in_status=sell_in_status,
        )
        source["industry_data_contract"]["metric"]["metric_id"] = metric_id
        source["industry_data_contract"]["stock_flow_boundary"] = dict(boundary)
        sources.append(source)
    return sources


def test_cutoff_is_timestamp_precise_and_future_records_are_retained_as_rejections() -> None:
    result = admit_source_manifest([
        _source(),
        _source("SSE:600340:TEST:FUTURE", published_at="2020-04-27T18:00:01+08:00"),
        _source("SSE:600340:TEST:FUTURE_DATA", data_as_of="2020-04-28"),
        _source("SSE:600340:TEST:FUTURE_DATA_TIMESTAMP", data_as_of="2020-04-27T18:00:01+08:00"),
    ])
    assert result["admitted_source_ids"] == ["SSE:600340:TEST:1"]
    statuses = {item["source_id"]: item["admission_status"] for item in result["sources"]}
    assert statuses["SSE:600340:TEST:FUTURE"] == "REJECTED_FUTURE_PUBLISHED_AT"
    assert statuses["SSE:600340:TEST:FUTURE_DATA"] == "REJECTED_FUTURE_DATA_AS_OF"
    assert statuses["SSE:600340:TEST:FUTURE_DATA_TIMESTAMP"] == "REJECTED_FUTURE_DATA_AS_OF"


def test_date_only_disclosure_cannot_be_treated_as_known_inside_the_same_cutoff_day() -> None:
    result = admit_source_manifest([
        _source("SSE:600340:TEST:PREVIOUS_DAY", published_at="2020-04-26"),
        _source("SSE:600340:TEST:DATE_ONLY_CUTOFF_DAY", published_at="2020-04-27"),
        _source("SSE:600340:TEST:EXACT_CUTOFF", published_at="2020-04-27T18:00:00+08:00"),
        _source(
            "SSE:600340:TEST:DATE_ONLY_REVISION", published_at="2020-04-20",
            revision_published_at="2020-04-27",
            revision_policy="HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF",
        ),
    ])
    statuses = {item["source_id"]: item["admission_status"] for item in result["sources"]}
    assert statuses["SSE:600340:TEST:PREVIOUS_DAY"] == "ADMITTED"
    assert statuses["SSE:600340:TEST:DATE_ONLY_CUTOFF_DAY"] == "REJECTED_PUBLISHED_AT_TIME_UNKNOWN_AT_CUTOFF"
    assert statuses["SSE:600340:TEST:EXACT_CUTOFF"] == "ADMITTED"
    assert statuses["SSE:600340:TEST:DATE_ONLY_REVISION"] == "REJECTED_REVISION_TIME_UNKNOWN_AT_CUTOFF"


def test_pre_cutoff_revision_replaces_original_vintage() -> None:
    result = admit_source_manifest([
        _source("SSE:600340:AR2017:ORIGINAL", published_at="2018-03-30", data_as_of="2017-12-31", version_group="AR2017"),
        _source("SSE:600340:AR2017:REVISED", published_at="2018-04-21", data_as_of="2017-12-31", version_group="AR2017", supersedes=["SSE:600340:AR2017:ORIGINAL"], revision_policy="HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF"),
    ])
    decisions = {item["source_id"]: item for item in result["sources"]}
    assert decisions["SSE:600340:AR2017:ORIGINAL"]["admission_status"] == "REJECTED_SUPERSEDED_BEFORE_CUTOFF"
    assert decisions["SSE:600340:AR2017:REVISED"]["admissible"] is True
    assert result["admitted_source_ids"] == ["SSE:600340:AR2017:REVISED"]


def test_supersedes_requires_an_explicit_shared_version_family() -> None:
    result = admit_source_manifest([
        _source("SSE:600340:AR2017:ORIGINAL", published_at="2018-03-30", data_as_of="2017-12-31"),
        _source("SSE:600340:AR2017:REVISED", published_at="2018-04-21", data_as_of="2017-12-31", version_group="AR2017", supersedes=["SSE:600340:AR2017:ORIGINAL"], revision_policy="HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF"),
    ])
    decisions = {item["source_id"]: item for item in result["sources"]}
    assert decisions["SSE:600340:AR2017:ORIGINAL"]["admissible"] is True
    assert decisions["SSE:600340:AR2017:REVISED"]["admission_status"] == "REJECTED_INVALID_SUPERSEDES_REFERENCE"


def test_current_restated_data_and_future_revision_are_not_admissible() -> None:
    result = admit_source_manifest([
        _source("SSE:600340:TEST:RESTATED", revision_policy="CURRENT_RESTATED_ONLY"),
        _source("SSE:600340:TEST:REVISION", revision_published_at="2020-04-28"),
    ])
    statuses = {item["source_id"]: item["admission_status"] for item in result["sources"]}
    assert statuses["SSE:600340:TEST:RESTATED"] == "REJECTED_CURRENT_RESTATED_ONLY"
    assert statuses["SSE:600340:TEST:REVISION"] == "REJECTED_FUTURE_REVISION"


def test_licensed_industry_query_admits_a_versioned_avc_sell_out_release_without_calling_it_official() -> None:
    manifest = enumerate_independent_industry_sources(
        [_industry_source()],
        company_code="000651.SZ",
        cutoff_at="2026-02-01T18:00:00+08:00",
    )

    assert manifest["inventory_kind"] == "LICENSED_INDUSTRY_DATA_DECLARED_QUERY"
    assert manifest["acquisition_status"] == "LICENSED_INDUSTRY_QUERY_METADATA_FROZEN"
    assert manifest["admitted_source_ids"] == ["AVC:000651:AC:2025Q4:ORIGINAL"]
    assert manifest["sources"][0]["official"] is False
    assert manifest["sources"][0]["industry_data_contract"]["metric"]["semantic"] == "RETAIL_SELL_OUT"
    assert validate_source_manifest(manifest)["state"] == "REVIEWABLE"


def test_industry_measurement_profile_requires_a_locatable_declared_error_bound_for_level_use() -> None:
    source = _industry_source()
    profile = source["industry_data_contract"]["measurement_profile"]
    profile["error_status"] = "PROVIDER_DECLARED_BOUND"
    profile["permitted_inference"] = "LEVEL_WITH_STATED_LIMITS"

    incomplete = phase10_acquisition.validate_independent_industry_data_source(source)
    assert incomplete["state"] == "INCOMPLETE"
    assert "measurement_profile:error_bound_locator:missing_or_invalid" in incomplete["incomplete_findings"]

    profile["error_bound_locator"] = {
        "statement": "供应商声明该覆盖范围内的抽样误差界。",
        "locator": "README.md#error-bound",
    }
    reviewable = phase10_acquisition.validate_independent_industry_data_source(source)
    assert reviewable["state"] == "REVIEWABLE"


def test_licensed_industry_source_can_be_read_from_a_frozen_package_without_vendor_download(tmp_path) -> None:
    manifest = enumerate_independent_industry_sources(
        [_industry_source()],
        company_code="000651.SZ",
        cutoff_at="2026-02-01T18:00:00+08:00",
    )
    package = tmp_path / "package"
    export = package / "industry" / "avc-room-ac-2025q4.csv"
    export.parent.mkdir(parents=True)
    export.write_text("brand,retail_value_share\nGREE,24.3\n", encoding="utf-8")

    runner = PITSourcePackage(manifest, package)

    assert runner.state == "REVIEWABLE"
    assert runner.read_source("AVC:000651:AC:2025Q4:ORIGINAL").startswith(b"brand,")
    assert runner.attestation()["source_allowlist"][0]["source_id"] == "AVC:000651:AC:2025Q4:ORIGINAL"


def test_company_manifest_can_compose_a_selected_licensed_industry_release_without_changing_inventory_logic() -> None:
    company = enumerate_sse_announcements([{
        "source_id": "SSE:000651:AR2025", "source_version": "annual-2025-original",
        "source_type": "ANNUAL_REPORT", "title": "2025 年年度报告",
        "published_at": "2026-01-15T10:00:00+08:00", "data_as_of": "2025-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
    }], cutoff_at="2026-02-01T18:00:00+08:00", period_start="2025-01-01")
    company["company_code"] = "000651.SZ"
    company["source_package_selection"] = build_source_package_selection(
        company,
        selection_policy_id="company-v1", selection_reason="先冻结公司财务与现金事实。",
        source_ids=["SSE:000651:AR2025"],
        source_research_rationales=[{
            "source_id": "SSE:000651:AR2025", "selection_reason": "四层公司 driver 的官方起点。",
            "research_question_ids": ["DQ:GREE:CASH"],
        }],
    )

    composed = compose_company_manifest_with_independent_industry_sources(
        company, [_industry_source()],
        selection_policy_id="company-plus-industry-v1",
        selection_reason="在不替换公司完整公告 inventory 的前提下加入竞争 FJ 的零售端 release。",
        industry_source_research_rationales=[{
            "source_id": "AVC:000651:AC:2025Q4:ORIGINAL",
            "selection_reason": "检验品牌×渠道零售端竞争位置。",
            "research_question_ids": ["DQ:GREE:COMPETITION"],
        }],
    )

    assert validate_source_manifest(composed)["state"] == "REVIEWABLE"
    assert composed["inventory_kind"] == "COMPOSITE_COMPANY_AND_INDEPENDENT_INDUSTRY_SOURCE_PACKAGE"
    assert composed["independent_industry_source_ids"] == ["AVC:000651:AC:2025Q4:ORIGINAL"]
    assert composed["source_package_selection"]["selected_source_ids"] == [
        "SSE:000651:AR2025", "AVC:000651:AC:2025Q4:ORIGINAL",
    ]
    assert len(company["inventory"]) == 1


def test_cli_enumerates_then_composes_a_qualified_industry_release(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    company = enumerate_sse_announcements([{
        "source_id": "SSE:000651:AR2025", "source_version": "annual-2025-original",
        "source_type": "ANNUAL_REPORT", "title": "2025 年年度报告",
        "published_at": "2026-01-15T10:00:00+08:00", "data_as_of": "2025-12-31",
        "revision_policy": "ORIGINAL_VINTAGE",
    }], cutoff_at="2026-02-01T18:00:00+08:00", period_start="2025-01-01")
    company["company_code"] = "000651.SZ"
    company["source_package_selection"] = build_source_package_selection(
        company,
        selection_policy_id="company-v1", selection_reason="冻结公司事实。",
        source_ids=["SSE:000651:AR2025"],
        source_research_rationales=[{
            "source_id": "SSE:000651:AR2025", "selection_reason": "公司事实。",
            "research_question_ids": ["DQ:GREE:CASH"],
        }],
    )
    company_path = tmp_path / "company.json"
    raw_industry_path = tmp_path / "licensed_release.json"
    industry_path = tmp_path / "industry_manifest.json"
    selection_path = tmp_path / "composition_selection.json"
    output_path = tmp_path / "composite.json"
    company_path.write_text(json.dumps(company), encoding="utf-8")
    raw_industry_path.write_text(json.dumps({"records": [_industry_source()]}), encoding="utf-8")
    selection_path.write_text(json.dumps({
        "selection_policy_id": "company-plus-industry-v1",
        "selection_reason": "加入竞争 FJ 的零售端 release。",
        "source_research_rationales": [{
            "source_id": "AVC:000651:AC:2025Q4:ORIGINAL",
            "selection_reason": "检验品牌×渠道零售端竞争位置。",
            "research_question_ids": ["DQ:GREE:COMPETITION"],
        }],
    }), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["phase10_acquisition.py", "enumerate-industry",
        "--input", str(raw_industry_path), "--output", str(industry_path),
        "--company-code", "000651.SZ", "--cutoff-at", "2026-02-01T18:00:00+08:00"])
    assert phase10_acquisition.main() == 0
    monkeypatch.setattr(sys, "argv", ["phase10_acquisition.py", "compose-industry",
        "--input", str(company_path), "--industry-input", str(industry_path),
        "--selection-input", str(selection_path), "--output", str(output_path)])
    assert phase10_acquisition.main() == 0

    composite = json.loads(output_path.read_text(encoding="utf-8"))
    assert validate_source_manifest(composite)["state"] == "REVIEWABLE"
    assert composite["source_package_selection"]["selected_source_ids"] == [
        "SSE:000651:AR2025", "AVC:000651:AC:2025Q4:ORIGINAL",
    ]


def test_acquire_source_package_registers_a_local_licensed_export_without_downloading_it(tmp_path) -> None:
    manifest = enumerate_independent_industry_sources(
        [_industry_source()], company_code="000651.SZ", cutoff_at="2026-02-01T18:00:00+08:00",
    )
    export = tmp_path / "industry" / "avc-room-ac-2025q4.csv"
    export.parent.mkdir(parents=True)
    export.write_text("brand,retail_value_share\nGREE,24.3\n", encoding="utf-8")

    result = acquire_source_package(
        manifest, tmp_path,
        downloader=lambda _url: (_ for _ in ()).throw(AssertionError("licensed export must not download")),
    )

    assert result["source_package"]["status"] == "COMPLETE"
    assert result["sources"][0]["package_acquisition_status"] == "LICENSED_EXPORT_PRESENT"


def test_official_web_release_is_frozen_as_html_with_a_registered_reader_copy(tmp_path) -> None:
    manifest = enumerate_official_web_releases(
        [_official_web_release()], company_code="EXAMPLE.US", cutoff_at="2026-08-21T18:00:00+08:00",
    )
    assert validate_source_manifest(manifest)["state"] == "REVIEWABLE"
    source_id = "IR:EXAMPLE.US:FY2026Q3_RESULTS"

    result = acquire_source_package(
        manifest,
        tmp_path,
        downloader=lambda _url: b"<html><body><h1>Q3</h1><p>Comparable transactions increased 4.5%.</p></body></html>",
    )

    source = result["sources"][0]
    assert result["source_package"]["status"] == "COMPLETE"
    assert source["source_id"] == source_id
    assert source["source_type"] == "OTHER_OFFICIAL"
    assert source["official"] is True
    assert source["content_representation"] == "WEB_PAGE_MARKDOWN"
    assert (tmp_path / source["package_path"]).read_text(encoding="utf-8").startswith("<html>")
    reader = (tmp_path / source["reader_text_path"]).read_text(encoding="utf-8")
    assert "content_representation: WEB_PAGE_MARKDOWN" in reader
    assert "## 第 1 页" in reader
    assert "Comparable transactions increased 4.5%." in reader

    runner = PITSourcePackage(result, tmp_path)
    assert runner.state == "REVIEWABLE"
    assert b"Comparable transactions increased 4.5%." in runner.read_source(source_id)


def test_official_issuer_pdf_release_is_frozen_with_page_marked_reader_copy(tmp_path) -> None:
    manifest = enumerate_official_web_releases(
        [_official_web_release(
            release_id="FY2026Q3_RESULTS_PDF",
            url="https://investor.example.com/results/fy2026-q3.pdf",
            content_format="PDF",
        )],
        company_code="EXAMPLE.US",
        cutoff_at="2026-08-21T18:00:00+08:00",
    )
    assert validate_source_manifest(manifest)["state"] == "REVIEWABLE"
    source_id = "IR:EXAMPLE.US:FY2026Q3_RESULTS_PDF"

    with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[
        (1, "Comparable transactions increased 4.5%."),
    ]):
        result = acquire_source_package(
            manifest,
            tmp_path,
            downloader=lambda _url: b"%PDF-example-official-release",
        )

    source = result["sources"][0]
    assert result["source_package"]["status"] == "COMPLETE"
    assert source["source_type"] == "OTHER_OFFICIAL"
    assert source["official"] is True
    assert source["content_representation"] == "PDF_PAGE_MARKDOWN"
    assert (tmp_path / source["package_path"]).suffix == ".pdf"
    assert (tmp_path / source["package_path"]).read_bytes().startswith(b"%PDF")
    reader = (tmp_path / source["reader_text_path"]).read_text(encoding="utf-8")
    assert "content_representation: PDF_PAGE_MARKDOWN" in reader
    assert "## 第 1 页" in reader

    runner = PITSourcePackage(result, tmp_path)
    assert runner.state == "REVIEWABLE"
    assert b"Comparable transactions increased 4.5%." in runner.read_source(source_id)


def test_shipment_is_never_labeled_sell_in_without_the_provider_definition() -> None:
    unresolved = _industry_source(
        source_id="CHINAIOL:000651:AC:2025Q4:SHIPMENT",
        provider_id="CHINAIOL",
        semantic="SHIPMENT",
        shipment_sell_in_status="SHIPMENT_SEMANTICS_UNRESOLVED",
    )
    unresolved["source_version"] = "chinaiol-room-ac-shipment-2025q4-original"
    unresolved["industry_data_contract"]["release"]["version_id"] = unresolved["source_version"]
    unresolved["industry_data_contract"]["release"]["release_id"] = "CHINAIOL-AC-2025Q4-ORIGINAL"
    unresolved["industry_data_contract"]["query_identity"]["query_id"] = "CHINAIOL-QUERY-ROOM-AC-CN-2025Q4-SHIPMENT"
    manifest = enumerate_independent_industry_sources(
        [unresolved], company_code="000651.SZ", cutoff_at="2026-02-01T18:00:00+08:00",
    )
    assert manifest["sources"][0]["industry_data_contract"]["metric"]["shipment_sell_in_status"] == "SHIPMENT_SEMANTICS_UNRESOLVED"

    provider_defined = _industry_source(
        source_id="CHINAIOL:000651:AC:2025Q4:SELL-IN",
        provider_id="CHINAIOL",
        semantic="SHIPMENT",
        shipment_sell_in_status="PROVIDER_DEFINED_SELL_IN",
    )
    provider_defined["source_version"] = "chinaiol-room-ac-shipment-2025q4-original"
    provider_defined["industry_data_contract"]["release"]["version_id"] = provider_defined["source_version"]
    provider_defined["industry_data_contract"]["release"]["release_id"] = "CHINAIOL-AC-2025Q4-ORIGINAL"
    provider_defined["industry_data_contract"]["query_identity"]["query_id"] = "CHINAIOL-QUERY-ROOM-AC-CN-2025Q4-SELL-IN"
    defined_manifest = enumerate_independent_industry_sources(
        [provider_defined], company_code="000651.SZ", cutoff_at="2026-02-01T18:00:00+08:00",
    )
    assert defined_manifest["admitted_source_ids"] == ["CHINAIOL:000651:AC:2025Q4:SELL-IN"]

    mislabeled = deepcopy(unresolved)
    mislabeled["source_id"] = "CHINAIOL:000651:AC:2025Q4:MISLABELED"
    mislabeled["industry_data_contract"]["metric"]["shipment_sell_in_status"] = "PROVIDER_DEFINED_SELL_IN"
    rejected = enumerate_independent_industry_sources(
        [mislabeled], company_code="000651.SZ", cutoff_at="2026-02-01T18:00:00+08:00",
    )
    assert rejected["admitted_source_ids"] == []
    assert rejected["inventory"][0]["admission_status"] == "REJECTED_INDEPENDENT_INDUSTRY_CONTRACT_INCOMPLETE"


def test_stock_flow_reconciliation_requires_one_release_and_one_shared_boundary() -> None:
    sources = _stock_flow_sources()
    result = validate_stock_flow_reconciliation(sources)
    assert result["state"] == "RECONCILABLE"

    sources[1]["industry_data_contract"]["metric"]["shipment_sell_in_status"] = "SHIPMENT_SEMANTICS_UNRESOLVED"
    sources[1]["industry_data_contract"]["metric"].pop("provider_sell_in_definition")
    unresolved = validate_stock_flow_reconciliation(sources)
    assert unresolved["state"] == "NOT_RECONCILABLE"
    assert "shipment:provider_defined_sell_in_required" in unresolved["non_reconcilable_findings"]

    sources = _stock_flow_sources()
    sources[2]["industry_data_contract"]["stock_flow_boundary"]["period"] = "2025Q3"
    mismatched = validate_stock_flow_reconciliation(sources)
    assert mismatched["state"] == "NOT_RECONCILABLE"
    assert "stock_flow_boundaries_not_identical" in mismatched["non_reconcilable_findings"]


def test_sse_enumeration_sorts_by_date_and_title_without_dropping_future_rows() -> None:
    result = enumerate_sse_announcements([
        {"source_id": "SSE:600340:ANN:2", "title": "乙公告", "published_at": "2020-04-27", "data_as_of": "2020-04-27"},
        {"source_id": "SSE:600340:ANN:1", "title": "甲公告", "published_at": "2020-04-26", "data_as_of": "2020-04-26"},
        {"source_id": "SSE:600340:ANN:3", "title": "未来公告", "published_at": "2020-04-28", "data_as_of": "2020-04-28"},
    ])
    assert result["enumeration_complete"] is True
    assert [item["source_id"] for item in result["inventory"]] == [
        "SSE:600340:ANN:1", "SSE:600340:ANN:2", "SSE:600340:ANN:3",
    ]
    assert result["admitted_source_ids"] == ["SSE:600340:ANN:1"]
    assert result["inventory"][1]["admission_status"] == "REJECTED_PUBLISHED_AT_TIME_UNKNOWN_AT_CUTOFF"
    assert result["inventory"][2]["admission_status"] == "REJECTED_FUTURE_PUBLISHED_AT"


def test_generic_sse_cli_preserves_the_official_query_company_identity(tmp_path) -> None:
    source = tmp_path / "records.json"
    output = tmp_path / "manifest.json"
    source.write_text(json.dumps({
        "company_code": "688432",
        "records": [{
            "source_id": "SSE:688432:ANN:20260327:annual",
            "title": "2025 年年度报告",
            "published_at": "2026-03-27",
            "data_as_of": "2025-12-31",
        }],
    }), encoding="utf-8")
    with patch.object(sys, "argv", [
        "phase10_acquisition.py", "enumerate", "--input", str(source),
        "--cutoff-at", "2026-08-21T23:59:59+08:00", "--output", str(output),
    ]):
        assert phase10_acquisition.main() == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["company_code"] == "688432.SH"


def test_cninfo_export_normalizes_shenzhen_filing_and_preserves_future_rejection() -> None:
    records = [
        {
            "secCode": "000651", "announcementId": "1225250394",
            "announcementTitle": "格力电器：2025 年年度报告全文",
            "announcementTime": "2026-04-29", "adjunctUrl": "finalpage/2026-04-29/1225250394.PDF",
        },
        {
            "secCode": "000651", "announcementId": "future", "announcementTitle": "格力电器：后续公告",
            "announcementTime": "2026-05-02", "adjunctUrl": "finalpage/2026-05-02/future.PDF",
        },
    ]
    normalized = normalize_cninfo_announcement_record(records[0], company_code="000651")
    assert normalized["source_type"] == "ANNUAL_REPORT"
    assert normalized["data_as_of"] == "2025-12-31"
    assert normalized["url"] == "https://static.cninfo.com.cn/finalpage/2026-04-29/1225250394.PDF"
    assert normalized["official"] is True
    assert normalized["official_publisher_domain"] == "static.cninfo.com.cn"

    manifest = enumerate_cninfo_announcements(
        records, company_code="000651", period_start="2025-01-01", cutoff_at="2026-04-30T18:00:00+08:00",
    )
    assert manifest["inventory_kind"] == "CNINFO_ANNOUNCEMENT_FULL_EXPORT"
    assert manifest["enumeration_complete"] is True
    assert manifest["admitted_source_ids"] == ["CNINFO:000651:ANN:20260429:1225250394"]
    assert manifest["inventory"][1]["admission_status"] == "REJECTED_FUTURE_PUBLISHED_AT"
    assert validate_source_manifest(manifest)["state"] == "REVIEWABLE"


def test_cninfo_export_rejects_a_row_without_statutory_url() -> None:
    with pytest.raises(CNInfoAnnouncementExportError, match="URL"):
        normalize_cninfo_announcement_record({
            "secCode": "000651", "announcementId": "1225250394",
            "announcementTitle": "格力电器：2025 年年度报告全文", "announcementTime": "2026-04-29",
        }, company_code="000651")


def test_cninfo_fetch_paginates_complete_official_metadata_and_builds_manifest() -> None:
    rows = [
        {
            "secCode": "000651", "orgId": "gssz0000651", "announcementId": "A1",
            "announcementTitle": "格力电器：2025年年度报告", "announcementTime": "2026-04-29",
            "adjunctUrl": "finalpage/2026-04-29/A1.PDF",
        },
        {
            "secCode": "000651", "orgId": "gssz0000651", "announcementId": "A2",
            "announcementTitle": "格力电器：关于回购股份的公告", "announcementTime": "2026-05-08",
            "adjunctUrl": "finalpage/2026-05-08/A2.PDF",
        },
    ]
    requested: list[dict[str, str]] = []

    def request(params: dict[str, str]) -> dict[str, object]:
        requested.append(params)
        index = int(params["pageNum"]) - 1
        return _cninfo_payload([rows[index]], total=2)

    result = fetch_cninfo_announcement_records(
        company_code="000651", org_id="gssz0000651", begin_date="2025-01-01", end_date="2026-08-02",
        page_size=1, request=request,
    )
    assert result["record_count"] == 2
    assert result["page_count"] == 2
    assert [item["announcementId"] for item in result["records"]] == ["A1", "A2"]
    assert all(item["stock"] == "000651,gssz0000651" for item in requested)
    assert all(item["seDate"] == "2025-01-01~2026-08-02" for item in requested)
    assert all(item["sortName"] == "announcementTime" for item in requested)
    assert all(item["sortType"] == "desc" for item in requested)

    manifest = fetch_cninfo_manifest(
        company_code="000651", org_id="gssz0000651", begin_date="2025-01-01",
        cutoff_at="2026-08-02T18:00:00+08:00", page_size=1, request=request,
    )
    assert manifest["acquisition_status"] == "CNINFO_FULL_ENUMERATION_DATE_FILTER_VERIFIED"
    assert manifest["cninfo_query"]["record_count"] == 2
    assert validate_source_manifest(manifest)["state"] == "REVIEWABLE"


def test_cninfo_fetch_accepts_provider_empty_enumeration() -> None:
    """CNINFO represents a valid zero-result date query as announcements=null."""
    result = fetch_cninfo_announcement_records(
        company_code="000333", org_id="9900005965", begin_date="2026-08-23", end_date="2026-08-23",
        request=lambda _params: {"totalAnnouncement": 0, "announcements": None},
    )

    assert result["record_count"] == 0
    assert result["page_count"] == 1
    assert result["records"] == []

    manifest = fetch_cninfo_manifest(
        company_code="000333", org_id="9900005965", begin_date="2026-08-23",
        cutoff_at="2026-08-23T00:05:00+08:00",
        request=lambda _params: {"totalAnnouncement": 0, "announcements": None},
    )
    assert manifest["inventory_count"] == 0
    assert manifest["acquisition_status"] == "CNINFO_FULL_ENUMERATION_DATE_FILTER_VERIFIED"


def test_cninfo_fetch_fails_when_page_repeats_an_announcement() -> None:
    row = {
        "secCode": "000651", "orgId": "gssz0000651", "announcementId": "A1",
        "announcementTitle": "格力电器：公告", "announcementTime": "2026-04-29",
        "adjunctUrl": "finalpage/2026-04-29/A1.PDF",
    }

    with pytest.raises(CNInfoAnnouncementQueryError, match="repeated"):
        fetch_cninfo_announcement_records(
            company_code="000651", org_id="gssz0000651", begin_date="2025-01-01", end_date="2026-08-02",
            page_size=1, request=lambda _params: _cninfo_payload([row], total=2),
        )


def test_cninfo_fetch_rejects_page_size_above_provider_limit() -> None:
    with pytest.raises(ValueError, match="at most 30"):
        fetch_cninfo_announcement_records(
            company_code="000651", org_id="gssz0000651", begin_date="2025-01-01", end_date="2026-08-02",
            page_size=31,
        )


def test_post_cutoff_queue_uses_titles_only_without_acquiring_document_bodies() -> None:
    inventory = {
        "provider": "SSE",
        "endpoint": "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
        "company_code": "600340",
        "begin_date": "2020-04-28",
        "end_date": "2021-04-27",
        "record_count": 3,
        "records": [
            _source("SSE:600340:ANN:1", title="关于公司债券兑付安排的公告", published_at="2020-05-10"),
            _source("SSE:600340:ANN:2", title="2020 年半年度报告", published_at="2020-08-30"),
            _source("SSE:600340:ANN:3", title="关于办公地址变更的公告", published_at="2020-06-01"),
        ],
    }

    queue = build_post_cutoff_reading_queue(inventory)

    assert queue["metadata_only"] is True
    assert queue["pdf_downloaded"] is False
    assert queue["body_read"] is False
    assert queue["title_match_is_evidence"] is False
    assert queue["candidate_record_count"] == 2
    debt_notice = next(item for item in queue["records"] if item["source_id"] == "SSE:600340:ANN:1")
    assert set(debt_notice["candidate_claim_ids"]) == {
        "HBTCLM:600340:P10B:ORDINARY_CASH",
        "HBTCLM:600340:P10B:DEBT_REFINANCING",
    }
    interim = next(item for item in queue["records"] if item["source_id"] == "SSE:600340:ANN:2")
    assert set(interim["candidate_claim_ids"]) == {
        "HBTCLM:600340:P10B:ORDINARY_CASH",
        "HBTCLM:600340:P10B:GOV_RECEIVABLES",
        "HBTCLM:600340:P10B:DEBT_REFINANCING",
        "HBTCLM:600340:P10B:GUARANTEE_RECOVERY",
    }


def test_post_cutoff_queue_preserves_an_empty_official_inventory() -> None:
    queue = build_post_cutoff_reading_queue({
        "provider": "SSE",
        "endpoint": "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
        "company_code": "600340",
        "begin_date": "2020-04-28",
        "end_date": "2020-04-28",
        "record_count": 0,
        "records": [],
    })

    assert queue["record_count"] == 0
    assert queue["candidate_record_count"] == 0
    assert queue["records"] == []


def test_sse_malformed_rows_keep_explicit_rejection_reason() -> None:
    result = enumerate_sse_announcements([
        {"source_id": "SSE:600340:ANN:NO_TITLE", "published_at": "2020-04-20", "data_as_of": "2020-04-20"},
        {"source_id": "SSE:600340:ANN:NO_DATE", "title": "缺日期公告"},
    ])
    statuses = {item["source_id"]: item["admission_status"] for item in result["inventory"]}
    assert statuses["SSE:600340:ANN:NO_TITLE"] == "REJECTED_MISSING_ANNOUNCEMENT_TITLE"
    assert statuses["SSE:600340:ANN:NO_DATE"] == "REJECTED_MISSING_ANNOUNCEMENT_DATE"


def test_sse_fetch_paginates_and_normalizes_only_bounded_rows() -> None:
    rows = [
        {
            "SECURITY_CODE": "600340",
            "SSEDATE": "2020-04-25",
            "TITLE": "2019 年年度报告",
            "URL": "/disclosure/listedinfo/announcement/c/2020-04-25/600340_20200425_22.pdf",
        },
        {
            "SECURITY_CODE": "600340",
            "SSEDATE": "2020-04-24",
            "TITLE": "临时公告",
            "URL": "/disclosure/listedinfo/announcement/c/2020-04-24/600340_20200424_1.pdf",
        },
    ]
    requested: list[dict[str, str]] = []

    def request(params: dict[str, str]) -> dict[str, object]:
        requested.append(params)
        page_no = int(params["pageHelp.pageNo"])
        return _sse_payload(page_no, [rows[page_no - 1]], total=2, page_size=1)

    result = fetch_sse_announcement_records(page_size=1, request=request)
    assert result["record_count"] == 2
    assert result["page_count"] == 2
    assert [item["published_at"] for item in result["records"]] == ["2020-04-25", "2020-04-24"]
    assert all(params["beginDate"] == "2018-01-01" and params["endDate"] == "2020-04-27" for params in requested)
    assert all(item["source_id"].startswith("SSE:600340:ANN:") for item in result["records"])


def test_sse_fetch_fails_closed_when_response_date_echo_or_row_bounds_are_wrong() -> None:
    def wrong_echo(params: dict[str, str]) -> dict[str, object]:
        payload = _sse_payload(1, [], total=0)
        payload["endDate"] = "2020-04-28"
        return payload

    with pytest.raises(SSEAnnouncementQueryError, match="endDate"):
        fetch_sse_announcement_records(request=wrong_echo)

    def future_row(params: dict[str, str]) -> dict[str, object]:
        return _sse_payload(1, [{
            "SECURITY_CODE": "600340",
            "SSEDATE": "2020-04-28",
            "TITLE": "未来公告",
            "URL": "/future.pdf",
        }], total=1)

    with pytest.raises(SSEAnnouncementQueryError, match="outside the requested dates"):
        fetch_sse_announcement_records(request=future_row)


def test_fetch_600340_manifest_requires_all_seed_documents_and_applies_revision_rules() -> None:
    catalog = build_600340_source_manifest()
    rows = [{
        "SECURITY_CODE": "600340",
        "SSEDATE": item["published_at"],
        "TITLE": item["title"],
        "URL": item["url"],
    } for item in catalog["inventory"]]

    result = fetch_600340_sse_manifest(
        page_size=100,
        request=lambda params: _sse_payload(1, rows, total=len(rows)),
    )
    assert result["enumeration_complete"] is True
    assert result["acquisition_status"] == "SSE_FULL_ENUMERATION_DATE_FILTER_VERIFIED"
    assert result["sse_query"]["record_count"] == len(rows)
    assert "SSE:600340:AR2017:REVISED" in result["admitted_source_ids"]
    assert "SSE:600340:AR2017:ORIGINAL" in result["rejected_source_ids"]


def test_acquire_source_package_preserves_raw_pdf_and_materializes_reader_text(tmp_path) -> None:
    manifest = enumerate_sse_announcements([_source(
        source_id="SSE:600340:TEST:PDF",
        source_type="ANNUAL_REPORT",
        published_at="2020-04-20",
        data_as_of="2019-12-31",
    )])
    package = tmp_path / "package"
    with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[(1, "截止日前正文")]):
        result = acquire_source_package(
            manifest,
            package,
            downloader=lambda url: b"%PDF-test-source",
        )
    assert result["source_package"]["status"] == "COMPLETE"
    assert result["source_package"]["successful_count"] == 1
    source = result["sources"][0]
    assert source["package_acquisition_status"] == "ADMITTED_PACKAGE"
    assert (package / source["package_path"]).read_bytes() == b"%PDF-test-source"
    assert "## 第 1 页" in (package / source["reader_text_path"]).read_text(encoding="utf-8")
    assert validate_source_manifest(result)["state"] == "REVIEWABLE"


def test_acquire_source_package_reuses_completed_files_on_resume(tmp_path) -> None:
    manifest = enumerate_sse_announcements([_source(
        source_id="SSE:600340:TEST:PDF",
        source_type="ANNUAL_REPORT",
        published_at="2020-04-20",
        data_as_of="2019-12-31",
    )])
    package = tmp_path / "package"
    with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[(1, "截止日前正文")]):
        first = acquire_source_package(manifest, package, downloader=lambda url: b"%PDF-test-source")

    def unexpected_download(url: str) -> bytes:
        raise AssertionError("completed source should be reused")

    resumed = acquire_source_package(first, package, downloader=unexpected_download)
    assert resumed["source_package"]["status"] == "COMPLETE"
    assert resumed["source_package"]["successful_count"] == 1


def test_source_package_selection_downloads_only_frozen_admitted_subset(tmp_path) -> None:
    manifest = enumerate_sse_announcements([
        _source("SSE:600340:TEST:ONE", url="https://static.sse.com.cn/one.pdf"),
        _source("SSE:600340:TEST:TWO", url="https://static.sse.com.cn/two.pdf"),
    ])
    manifest["source_package_selection"] = build_source_package_selection(
        manifest,
        selection_policy_id="gree-v1-cash-and-allocation.v1",
        selection_reason="先物化年报与资本配置事件，不以公告标题作为事实。",
        source_ids=["SSE:600340:TEST:TWO"],
        source_research_rationales=[{
            "source_id": "SSE:600340:TEST:TWO",
            "selection_reason": "验证资本配置事件是否改变普通股现金可得性。",
            "research_question_ids": ["DQ-CAPITAL-ALLOCATION"],
        }],
    )
    downloaded: list[str] = []

    def downloader(url: str) -> bytes:
        downloaded.append(url)
        return b"%PDF-selected-source"

    with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[(1, "已选择正文")]):
        result = acquire_source_package(manifest, tmp_path / "package", downloader=downloader)
    assert downloaded == ["https://static.sse.com.cn/two.pdf"]
    assert len(result["sources"]) == 2
    assert result["source_package"]["selected_count"] == 1
    assert result["source_package"]["selection_policy_id"] == "gree-v1-cash-and-allocation.v1"
    assert validate_source_manifest(result)["state"] == "REVIEWABLE"


def test_acquire_source_package_materializes_existing_failed_pdf_on_resume(tmp_path) -> None:
    manifest = enumerate_sse_announcements([_source(
        source_id="SSE:600340:TEST:PDF",
        source_type="ANNUAL_REPORT",
        published_at="2020-04-20",
        data_as_of="2019-12-31",
    )])
    package = tmp_path / "package"
    (package / "pdf").mkdir(parents=True)
    pdf_path = package / "pdf/0001_SSE_600340_TEST_PDF.pdf"
    pdf_path.write_bytes(b"%PDF-existing")
    failed = deepcopy(manifest)
    failed["inventory"][0].update(
        package_path="pdf/0001_SSE_600340_TEST_PDF.pdf",
        package_acquisition_status="FAILED",
        package_acquisition_error="ValueError: source PDF has no extractable text pages",
    )
    failed["sources"][0] = failed["inventory"][0]
    with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[(1, "恢复正文")]):
        resumed = acquire_source_package(
            failed,
            package,
            downloader=lambda url: (_ for _ in ()).throw(AssertionError("raw PDF should be reused")),
        )
    assert resumed["source_package"]["status"] == "COMPLETE"


def test_download_sse_pdf_decompresses_gzip_before_pdf_signature_check() -> None:
    class FakeResponse:
        headers = {"Content-Encoding": "gzip"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return gzip.compress(b"%PDF-gzip-source")

    with patch("scripts.phase10_acquisition.urlopen", return_value=FakeResponse()):
        assert _download_sse_pdf(
            "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/test.pdf"
        ) == b"%PDF-gzip-source"


def test_download_cninfo_pdf_accepts_official_attachment_and_sets_portal_referer() -> None:
    class FakeResponse:
        headers: dict[str, str] = {}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"%PDF-cninfo-source"

    with patch("scripts.phase10_acquisition.urlopen", return_value=FakeResponse()) as mocked_urlopen:
        assert _download_cninfo_pdf(
            "https://static.cninfo.com.cn/finalpage/2026-04-29/1225250396.PDF"
        ) == b"%PDF-cninfo-source"
    request = mocked_urlopen.call_args.args[0]
    assert request.get_header("Referer") == "https://www.cninfo.com.cn/"


def test_acquire_cninfo_source_package_uses_default_official_downloader(tmp_path) -> None:
    manifest = enumerate_cninfo_announcements([{
        "secCode": "000651", "announcementId": "1225250396",
        "announcementTitle": "格力电器：2025 年年度报告",
        "announcementTime": "2026-04-29", "adjunctUrl": "finalpage/2026-04-29/1225250396.PDF",
    }], company_code="000651", period_start="2025-01-01", cutoff_at="2026-08-03T18:00:00+08:00")
    with patch("scripts.phase10_acquisition._download_cninfo_pdf", return_value=b"%PDF-cninfo-source") as download:
        with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[(1, "格力年报正文")]):
            result = acquire_source_package(manifest, tmp_path / "package")
    assert result["source_package"]["status"] == "COMPLETE"
    assert download.call_args.args[0].endswith("1225250396.PDF")
    assert result["sources"][0]["package_acquisition_status"] == "ADMITTED_PACKAGE"


def test_download_sse_pdf_rejects_gzip_encoded_bot_html() -> None:
    class FakeResponse:
        headers = {"Content-Encoding": "gzip", "Content-Type": "text/html; charset=utf-8"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return gzip.compress(b"<html>denied by bot</html>")

    with patch("scripts.phase10_acquisition.urlopen", return_value=FakeResponse()):
        with pytest.raises(SSEAnnouncementQueryError, match="does not start with the PDF signature"):
            _download_sse_pdf(
                "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/test.pdf"
            )


def test_download_sse_pdf_solves_gzip_bot_challenge_and_retries() -> None:
    challenge = """
    <html><script>
      var arg1='0123456789ABCDEF0123456789ABCDEF01234567';
      var _0x3e9e=['MzAwMDE3NjAwMDg1NjAwNjA2MTUwMTUzMzAwMzY5MDAyNzgwMDM3NQ==','c3BsaXQ='];
      var posList=[0xf,0x23,0x1d,0x18,0x21,0x10,0x1,0x26,0xa,0x9,0x13,0x1f,0x28,0x1b,0x16,0x17,0x19,0xd,0x6,0xb,0x27,0x12,0x14,0x8,0xe,0x15,0x20,0x1a,0x2,0x1e,0x7,0x4,0x11,0x5,0x3,0x1c,0x22,0x25,0xc,0x24];
      document.location.reload()
    </script></html>
    """

    class FakeResponse:
        def __init__(self, body: bytes, headers: dict[str, str]) -> None:
            self.body = body
            self.headers = headers

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self.body

    responses = [
        FakeResponse(gzip.compress(challenge.encode("utf-8")), {"Content-Encoding": "gzip"}),
        FakeResponse(b"%PDF-real-source", {}),
    ]
    with patch("scripts.phase10_acquisition.urlopen", side_effect=responses) as mocked_urlopen:
        assert _download_sse_pdf(
            "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/test.pdf"
        ) == b"%PDF-real-source"
    assert mocked_urlopen.call_count == 2
    retry_request = mocked_urlopen.call_args_list[1].args[0]
    assert retry_request.get_header("Cookie") == "acw_sc__v2=d2c7186598ab1a508a4f6064e4fa746323ab17c6"


def test_acquire_source_package_keeps_download_failure_incomplete(tmp_path) -> None:
    manifest = enumerate_sse_announcements([_source(
        source_id="SSE:600340:TEST:PDF",
        source_type="ANNUAL_REPORT",
        published_at="2020-04-20",
        data_as_of="2019-12-31",
    )])

    def fail_download(url: str) -> bytes:
        raise SSEAnnouncementQueryError("test transport failure")

    result = acquire_source_package(manifest, tmp_path / "package", downloader=fail_download)
    assert result["source_package"]["status"] == "INCOMPLETE"
    assert result["source_package"]["failed_source_ids"] == ["SSE:600340:TEST:PDF"]
    assert result["sources"][0]["package_acquisition_status"] == "FAILED"
    assert validate_source_manifest(result)["state"] == "REVIEWABLE"


def test_default_600340_catalog_requires_announcement_export_and_rejects_2017_original() -> None:
    manifest = build_600340_source_manifest()
    assert manifest["company_code"] == "600340.SH"
    assert manifest["cutoff_at"] == DEFAULT_CUTOFF_AT
    assert manifest["enumeration_complete"] is False
    decisions = {item["source_id"]: item for item in manifest["inventory"]}
    assert decisions["SSE:600340:AR2017:ORIGINAL"]["admission_status"] == "REJECTED_SUPERSEDED_BEFORE_CUTOFF"
    assert decisions["SSE:600340:AR2017:REVISED"]["admissible"] is True
    assert decisions["SSE:600340:AR2017:INQUIRY_LETTER"]["admissible"] is True
    assert validate_source_manifest(manifest)["state"] == "INCOMPLETE"


def test_manifest_validator_catches_tampered_admitted_source_list() -> None:
    manifest = enumerate_sse_announcements([_source()])
    tampered = deepcopy(manifest)
    tampered["admitted_source_ids"] = []
    result = validate_source_manifest(tampered)
    assert result["state"] == "INVALID"
    assert "admitted_source_ids_mismatch" in result["invalid_findings"]


def test_manifest_validator_recomputes_current_restated_inventory_admission() -> None:
    manifest = enumerate_sse_announcements([_source()])
    tampered = deepcopy(manifest)
    tampered["inventory"][0]["revision_policy"] = "CURRENT_RESTATED_ONLY"
    result = validate_source_manifest(tampered)
    assert result["state"] == "INVALID"
    assert "inventory[0]:admission_decision_mismatch" in result["invalid_findings"]


def test_manifest_validator_rejects_an_externally_injected_selected_source() -> None:
    manifest = enumerate_sse_announcements([_source()])
    tampered = deepcopy(manifest)
    tampered["sources"].append(_source("SSE:600340:TEST:INJECTED", published_at="2020-04-28"))
    result = validate_source_manifest(tampered)
    assert result["state"] == "INVALID"
    assert "selected_source_not_admitted:SSE:600340:TEST:INJECTED" in result["invalid_findings"]


def test_materialize_pdf_page_markdown_keeps_raw_source_and_page_locators(tmp_path) -> None:
    package = tmp_path / "package"
    (package / "raw").mkdir(parents=True)
    (package / "raw/test.pdf").write_bytes(b"%PDF-test")
    source = _source(
        source_id="SSE:600340:TEST:PDF",
        source_type="ANNUAL_REPORT",
        package_path="raw/test.pdf",
    )

    with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[
        (1, "第一页经营事实"),
        (2, "第二页债务与担保"),
    ]):
        materialized = materialize_pdf_page_markdown(
            source,
            package,
            reader_text_path="reader/test.pages.md",
        )

    assert (package / "raw/test.pdf").read_bytes() == b"%PDF-test"
    text = (package / "reader/test.pages.md").read_text(encoding="utf-8")
    assert "## 第 1 页" in text
    assert "## 第 2 页" in text
    assert materialized["content_representation"] == "PDF_PAGE_MARKDOWN"
    assert materialized["reader_text_path"] == "reader/test.pages.md"
    assert materialized["reader_text_page_count"] == 2


def test_materialize_pdf_page_markdown_uses_explicit_ocr_fallback(tmp_path) -> None:
    package = tmp_path / "package"
    (package / "raw").mkdir(parents=True)
    (package / "raw/test.pdf").write_bytes(b"%PDF-scanned")
    source = _source(
        source_id="SSE:600340:TEST:SCANNED",
        source_type="EXCHANGE_ANNOUNCEMENT",
        package_path="raw/test.pdf",
    )

    with patch("scripts.pdf_preprocessor.extract_all_pages", return_value=[]), patch(
        "scripts.phase10_acquisition._extract_pdf_pages_with_ocr",
        return_value=[(1, "OCR 页正文")],
    ):
        materialized = materialize_pdf_page_markdown(
            source,
            package,
            reader_text_path="reader/test.pages.md",
            allow_ocr=True,
        )

    assert materialized["reader_text_extractor"] == "pdftoppm+tesseract"
    assert materialized["reader_text_page_count"] == 1
    assert "OCR 页正文" in (package / "reader/test.pages.md").read_text(encoding="utf-8")


def test_materialize_pdf_page_markdown_never_overwrites_raw_or_existing_reader(tmp_path) -> None:
    package = tmp_path / "package"
    (package / "raw").mkdir(parents=True)
    raw_path = package / "raw/test.pdf"
    raw_path.write_bytes(b"%PDF-original")
    source = _source(
        source_id="SSE:600340:TEST:PDF",
        source_type="ANNUAL_REPORT",
        package_path="raw/test.pdf",
    )

    with pytest.raises(ValueError, match="must differ"):
        materialize_pdf_page_markdown(source, package, reader_text_path="raw/test.pdf")
    assert raw_path.read_bytes() == b"%PDF-original"

    (package / "reader").mkdir()
    existing_reader = package / "reader/test.pages.md"
    existing_reader.write_text("existing reader text", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_pdf_page_markdown(source, package, reader_text_path="reader/test.pages.md")
    assert existing_reader.read_text(encoding="utf-8") == "existing reader text"
