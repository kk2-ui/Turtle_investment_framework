from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from scripts.phase10_acquisition import (
    DEFAULT_CUTOFF_AT,
    admit_source_manifest,
    build_600340_source_manifest,
    enumerate_sse_announcements,
    materialize_pdf_page_markdown,
    validate_source_manifest,
)


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
    assert result["admitted_source_ids"] == ["SSE:600340:ANN:1", "SSE:600340:ANN:2"]
    assert result["inventory"][2]["admission_status"] == "REJECTED_FUTURE_PUBLISHED_AT"


def test_sse_malformed_rows_keep_explicit_rejection_reason() -> None:
    result = enumerate_sse_announcements([
        {"source_id": "SSE:600340:ANN:NO_TITLE", "published_at": "2020-04-20", "data_as_of": "2020-04-20"},
        {"source_id": "SSE:600340:ANN:NO_DATE", "title": "缺日期公告"},
    ])
    statuses = {item["source_id"]: item["admission_status"] for item in result["inventory"]}
    assert statuses["SSE:600340:ANN:NO_TITLE"] == "REJECTED_MISSING_ANNOUNCEMENT_TITLE"
    assert statuses["SSE:600340:ANN:NO_DATE"] == "REJECTED_MISSING_ANNOUNCEMENT_DATE"


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
