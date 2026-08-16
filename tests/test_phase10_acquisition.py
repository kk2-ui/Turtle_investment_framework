from __future__ import annotations

from copy import deepcopy

from scripts.phase10_acquisition import (
    DEFAULT_CUTOFF_AT,
    admit_source_manifest,
    build_600340_source_manifest,
    enumerate_sse_announcements,
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
        _source("SSE:600340:AR2017:REVISED", published_at="2018-04-21", data_as_of="2017-12-31", version_group="AR2017", revision_policy="HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF"),
    ])
    decisions = {item["source_id"]: item for item in result["sources"]}
    assert decisions["SSE:600340:AR2017:ORIGINAL"]["admission_status"] == "REJECTED_SUPERSEDED_BEFORE_CUTOFF"
    assert decisions["SSE:600340:AR2017:REVISED"]["admissible"] is True


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
