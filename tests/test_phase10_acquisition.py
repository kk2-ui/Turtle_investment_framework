from __future__ import annotations

import gzip
from copy import deepcopy
from unittest.mock import patch

import pytest

from scripts.phase10_acquisition import (
    DEFAULT_CUTOFF_AT,
    SSEAnnouncementQueryError,
    _download_sse_pdf,
    acquire_source_package,
    admit_source_manifest,
    build_post_cutoff_reading_queue,
    build_600340_source_manifest,
    fetch_600340_sse_manifest,
    fetch_sse_announcement_records,
    enumerate_sse_announcements,
    materialize_pdf_page_markdown,
    validate_source_manifest,
)


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
