#!/usr/bin/env python3
"""Point-in-time source acquisition primitives for the Phase 10 first case.

The module is deliberately an offline boundary layer.  A caller may feed it
the records returned by an SSE announcement export or an already downloaded
source catalog; it never uses the current web page as a proxy for a historical
vintage.  Every discovered announcement is retained, including rejected
records, so later review can distinguish an incomplete enumeration from an
empty selection.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


MANIFEST_SCHEMA_VERSION = "phase10-source-manifest.v1"
DEFAULT_COMPANY_CODE = "600340.SH"
DEFAULT_CUTOFF_AT = "2020-04-27T18:00:00+08:00"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
PDF_PAGE_MARKDOWN = "PDF_PAGE_MARKDOWN"
PDF_PAGE_MARKDOWN_EXTRACTOR = "pdf_preprocessor.extract_all_pages"
PDF_PAGE_MARKDOWN_EXTRACTOR_VERSION = "phase10-pdf-page-markdown.v1"
PDF_OCR_EXTRACTOR = "pdftoppm+tesseract"
PDF_OCR_EXTRACTOR_VERSION = "phase10-pdf-ocr-tesseract.v1"
SSE_BULLETIN_QUERY_URL = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"
SSE_STATIC_BASE_URL = "https://static.sse.com.cn"
SSE_SECURITY_TYPES = "0101,120100,020100,020200,120200"

POST_CUTOFF_CLAIM_TITLE_TERMS: dict[str, tuple[str, ...]] = {
    "HBTCLM:600340:P10B:ORDINARY_CASH": (
        "年度报告", "半年度报告", "季度报告", "现金流量", "募集资金", "资产负债", "融资", "债券", "永续债",
    ),
    "HBTCLM:600340:P10B:GOV_RECEIVABLES": (
        "年度报告", "半年度报告", "应收账款", "应收", "园区", "结算", "回款", "减值", "坏账",
    ),
    "HBTCLM:600340:P10B:DEBT_REFINANCING": (
        "年度报告", "半年度报告", "债券", "融资券", "中票", "公司债", "兑付", "回售", "展期", "借款", "永续债", "担保",
    ),
    "HBTCLM:600340:P10B:GUARANTEE_RECOVERY": (
        "年度报告", "半年度报告", "担保", "关联交易", "关联方", "委托贷款", "拆借", "展期", "抵押", "质押", "诉讼", "资产减值",
    ),
}

ADMITTED = "ADMITTED"
REJECTION_REASONS = {
    "FUTURE_PUBLISHED_AT",
    "FUTURE_DATA_AS_OF",
    "FUTURE_REVISION",
    "CURRENT_RESTATED_ONLY",
    "SUPERSEDED_BEFORE_CUTOFF",
    "MISSING_IDENTITY",
    "DUPLICATE_SOURCE_ID",
    "MISSING_ANNOUNCEMENT_TITLE",
    "MISSING_ANNOUNCEMENT_DATE",
    "MISSING_VERSION_FAMILY",
    "INVALID_SUPERSEDES_REFERENCE",
}


class SSEAnnouncementQueryError(RuntimeError):
    """Raised when the official SSE response cannot prove a bounded inventory."""


def _timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp, treating date-only values as local midnight."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text[:10]), time.min)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def _copy_record(record: dict[str, Any], **updates: Any) -> dict[str, Any]:
    result = deepcopy(record)
    result.update(updates)
    return result


def _package_relative_path(value: Any) -> str | None:
    """Normalize a source-package-relative path without accepting escapes."""
    text = str(value or "").strip().replace("\\", "/")
    if not text or text.startswith("/"):
        return None
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate.as_posix()


def _resolve_package_path(package_root: Path, relative_path: str, *, field: str) -> Path:
    resolved = (package_root / relative_path).resolve()
    if resolved != package_root and package_root not in resolved.parents:
        raise ValueError(f"{field} must stay under package_root")
    return resolved


def _extract_pdf_pages_with_ocr(pdf_path: Path) -> list[tuple[int, str]]:
    """Extract page text from a scanned PDF using installed CLI tools."""
    with tempfile.TemporaryDirectory(prefix="phase10-pdf-ocr-") as temporary:
        prefix = Path(temporary) / "page"
        try:
            subprocess.run(
                ["pdftoppm", "-png", "-r", "150", str(pdf_path), str(prefix)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise ValueError("source PDF OCR rasterizer unavailable or failed") from exc
        image_paths = sorted(
            Path(temporary).glob("page-*.png"),
            key=lambda path: int(path.stem.rsplit("-", 1)[1]),
        )
        if not image_paths:
            raise ValueError("source PDF OCR produced no page images")
        pages: list[tuple[int, str]] = []
        for image_path in image_paths:
            try:
                result = subprocess.run(
                    ["tesseract", str(image_path), "stdout", "-l", "chi_sim+eng"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                raise ValueError("source PDF OCR engine unavailable or failed") from exc
            text = result.stdout.strip()
            if text:
                page_number = int(image_path.stem.rsplit("-", 1)[1])
                pages.append((page_number, text))
        return pages


def materialize_pdf_page_markdown(
    source: dict[str, Any],
    package_root: str | Path,
    *,
    reader_text_path: str | None = None,
    allow_ocr: bool = False,
) -> dict[str, Any]:
    """Create the registered, page-marked reader representation for one PDF.

    The original official PDF remains the source artifact at ``package_path``.
    The derived Markdown stays in the same source package and is usable only
    through the runner's source-id boundary.  It is never written to a normal
    Turtle output directory.
    """
    root = Path(package_root).expanduser().resolve()
    raw_relative = _package_relative_path(source.get("package_path"))
    if raw_relative is None:
        raise ValueError("source.package_path must be a relative source-package path")
    raw_path = _resolve_package_path(root, raw_relative, field="source.package_path")
    if raw_path.suffix.lower() != ".pdf":
        raise ValueError("materialize_pdf_page_markdown requires a PDF package_path")
    if not raw_path.is_file():
        raise FileNotFoundError(f"source PDF missing: {raw_relative}")

    chosen_reader_path = reader_text_path or source.get("reader_text_path")
    if not chosen_reader_path:
        chosen_reader_path = str(Path(raw_relative).with_suffix(".pages.md"))
    reader_relative = _package_relative_path(chosen_reader_path)
    if reader_relative is None:
        raise ValueError("reader_text_path must be a relative source-package path")
    destination = _resolve_package_path(root, reader_relative, field="source.reader_text_path")
    if destination == raw_path:
        raise ValueError("reader_text_path must differ from source.package_path")
    if destination.exists():
        raise FileExistsError(f"reader_text_path already exists: {reader_relative}")

    try:
        from scripts.pdf_preprocessor import extract_all_pages
    except ModuleNotFoundError:
        from pdf_preprocessor import extract_all_pages

    pages = extract_all_pages(str(raw_path), verbose=False)
    nonempty_pages = [(number, text.strip()) for number, text in pages if text and text.strip()]
    reader_text_extractor = PDF_PAGE_MARKDOWN_EXTRACTOR
    reader_text_extractor_version = PDF_PAGE_MARKDOWN_EXTRACTOR_VERSION
    if not nonempty_pages and allow_ocr:
        nonempty_pages = [
            (number, text.strip())
            for number, text in _extract_pdf_pages_with_ocr(raw_path)
            if text and text.strip()
        ]
        reader_text_extractor = PDF_OCR_EXTRACTOR
        reader_text_extractor_version = PDF_OCR_EXTRACTOR_VERSION
    if not nonempty_pages:
        raise ValueError("source PDF has no extractable text pages")

    source_id = str(source.get("source_id") or "").strip()
    source_version = str(source.get("source_version") or "").strip()
    lines = [
        f"# {source_id or raw_relative}",
        "",
        f"- source_id: {source_id}",
        f"- source_version: {source_version}",
        f"- content_representation: {PDF_PAGE_MARKDOWN}",
        "",
    ]
    for page_number, text in nonempty_pages:
        lines.extend((f"## 第 {page_number} 页", "", text, ""))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return _copy_record(
        source,
        content_representation=PDF_PAGE_MARKDOWN,
        reader_text_path=reader_relative,
        reader_text_extractor=reader_text_extractor,
        reader_text_extractor_version=reader_text_extractor_version,
        reader_text_page_count=len(nonempty_pages),
    )


def _source_identity_ok(source: dict[str, Any]) -> bool:
    required = ("source_id", "source_version", "source_type", "revision_policy")
    return all(str(source.get(field) or "").strip() for field in required)


def _reject(source: dict[str, Any], reason: str) -> dict[str, Any]:
    return _copy_record(source, admissible=False, admission_status=f"REJECTED_{reason}")


def _admit_one(source: dict[str, Any], cutoff: datetime) -> dict[str, Any]:
    if not _source_identity_ok(source):
        return _reject(source, "MISSING_IDENTITY")
    if source.get("source_type") == "EXCHANGE_ANNOUNCEMENT" and not str(source.get("title") or "").strip():
        return _reject(source, "MISSING_ANNOUNCEMENT_TITLE")
    published = _timestamp(source.get("published_at"))
    data_as_of = _timestamp(source.get("data_as_of"))
    revision_at = _timestamp(source.get("revision_published_at")) if source.get("revision_published_at") else None
    if published is None:
        reason = "MISSING_ANNOUNCEMENT_DATE" if source.get("source_type") == "EXCHANGE_ANNOUNCEMENT" else "MISSING_IDENTITY"
        return _reject(source, reason)
    if published > cutoff:
        return _reject(source, "FUTURE_PUBLISHED_AT")
    if data_as_of is None:
        return _reject(source, "MISSING_IDENTITY")
    if data_as_of > cutoff:
        return _reject(source, "FUTURE_DATA_AS_OF")
    if revision_at and revision_at > cutoff:
        return _reject(source, "FUTURE_REVISION")
    if source.get("revision_policy") == "CURRENT_RESTATED_ONLY":
        return _reject(source, "CURRENT_RESTATED_ONLY")
    return _copy_record(source, admissible=True, admission_status=ADMITTED)


def _version_family(source: dict[str, Any]) -> str | None:
    group = source.get("version_group") or source.get("revision_group")
    normalized = str(group or "").strip()
    return normalized or None


def _supersedes_ids(source: dict[str, Any]) -> list[str] | None:
    """Return explicit replacement targets, or ``None`` for a malformed value."""
    if "supersedes" not in source:
        return []
    value = source.get("supersedes")
    if not isinstance(value, list):
        return None
    ids = [str(item or "").strip() for item in value]
    if not ids or any(not item for item in ids) or len(set(ids)) != len(ids):
        return None
    return ids


def _apply_supersession_rules(decisions: list[dict[str, Any]]) -> None:
    """Require an explicit version family before one source replaces another."""
    source_index = {
        str(source.get("source_id") or ""): source
        for source in decisions
        if str(source.get("source_id") or "")
    }
    for index, decision in enumerate(decisions):
        if decision.get("admissible") is not True:
            continue
        targets = _supersedes_ids(decision)
        if targets == []:
            continue
        family = _version_family(decision)
        if family is None:
            decisions[index] = _reject(decision, "MISSING_VERSION_FAMILY")
            continue
        if targets is None or any(
            target not in source_index or _version_family(source_index[target]) != family
            for target in targets
        ):
            decisions[index] = _reject(decision, "INVALID_SUPERSEDES_REFERENCE")

    # Once both replacement ends declare the same family, the latest eligible
    # disclosure is the sole selected version at this cutoff.
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, decision in enumerate(decisions):
        if decision.get("admissible") is True:
            family = _version_family(decision)
            if family:
                groups.setdefault(family, []).append((index, decision))
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda item: (_timestamp(item[1].get("published_at")) or datetime.min.replace(tzinfo=timezone.utc), item[0]))
        for index, _decision in members[:-1]:
            decisions[index] = _reject(decisions[index], "SUPERSEDED_BEFORE_CUTOFF")


def admit_source_manifest(
    sources: Iterable[dict[str, Any]],
    *,
    cutoff_at: str = DEFAULT_CUTOFF_AT,
    company_code: str = DEFAULT_COMPANY_CODE,
) -> dict[str, Any]:
    """Admit a source catalog at a precise cutoff, retaining every decision.

    The newest admissible version in a declared ``version_group`` wins.  An
    older version is explicitly retained as ``REJECTED_SUPERSEDED...`` rather
    than silently dropped.  This is what makes the 2017 original annual report
    fail in favor of its 2018-04-21 revision.
    """
    cutoff = _timestamp(cutoff_at)
    if cutoff is None:
        raise ValueError(f"invalid cutoff_at: {cutoff_at!r}")
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for raw in sources:
        source = deepcopy(raw)
        source_id = str(source.get("source_id") or "")
        if source_id and source_id in seen:
            duplicate_ids.add(source_id)
        if source_id:
            seen.add(source_id)
        decision = _admit_one(source, cutoff)
        if source_id in duplicate_ids:
            decision = _reject(decision, "DUPLICATE_SOURCE_ID")
        decisions.append(decision)

    _apply_supersession_rules(decisions)

    admitted = [item for item in decisions if item.get("admissible") is True]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "company_code": company_code,
        "cutoff_at": cutoff.isoformat(),
        "cutoff_timezone": "Asia/Shanghai",
        "sources": decisions,
        "admitted_source_ids": [str(item["source_id"]) for item in admitted],
        "rejected_source_ids": [str(item.get("source_id") or "") for item in decisions if item.get("admissible") is not True],
        "admitted_count": len(admitted),
        "rejected_count": len(decisions) - len(admitted),
    }


def enumerate_sse_announcements(
    records: Iterable[dict[str, Any]],
    *,
    cutoff_at: str = DEFAULT_CUTOFF_AT,
    period_start: str = "2018-01-01",
) -> dict[str, Any]:
    """Preserve a full SSE announcement inventory before source selection.

    ``records`` is expected to be the complete result of an SSE page/export for
    the requested period.  The function does not silently discard a future or
    malformed row: each row becomes a source decision and remains reviewable.
    """
    materialized = [deepcopy(item) for item in records]
    normalized: list[dict[str, Any]] = []
    for item in materialized:
        title = str(item.get("title") or item.get("announcement_title") or "").strip()
        published_value = item.get("published_at") or item.get("announcement_date")
        published = _timestamp(published_value)
        source = _copy_record(
            item,
            source_id=item.get("source_id") or f"SSE:600340:ANN:{published_value}:{title}",
            source_version=item.get("source_version") or "sse-announcement-original",
            source_type=item.get("source_type") or "EXCHANGE_ANNOUNCEMENT",
            revision_policy=item.get("revision_policy") or "ORIGINAL_VINTAGE",
            published_at=published_value,
            data_as_of=item.get("data_as_of") or (published.date().isoformat() if published else ""),
            title=title,
        )
        if not title:
            normalized.append(_reject(source, "MISSING_ANNOUNCEMENT_TITLE"))
        elif published is None:
            normalized.append(_reject(source, "MISSING_ANNOUNCEMENT_DATE"))
        else:
            normalized.append(source)
    normalized.sort(key=lambda item: (_timestamp(item.get("published_at")) or datetime.max.replace(tzinfo=timezone.utc), str(item.get("title") or "")))
    manifest = admit_source_manifest(normalized, cutoff_at=cutoff_at)
    manifest.update({
        "inventory_kind": "SSE_ANNOUNCEMENT_FULL_ENUMERATION",
        "period_start": period_start,
        "period_end": _timestamp(cutoff_at).date().isoformat() if _timestamp(cutoff_at) else cutoff_at[:10],
        "enumeration_complete": True,
        "inventory_count": len(normalized),
        "inventory": manifest.pop("sources"),
    })
    # The generic manifest still exposes selected source records via `sources`;
    # keeping `inventory` as the authoritative full list avoids losing rejects.
    manifest["sources"] = [item for item in manifest["inventory"] if item.get("admissible") is True]
    manifest["admitted_source_ids"] = [str(item["source_id"]) for item in manifest["sources"]]
    manifest["rejected_source_ids"] = [str(item.get("source_id") or "") for item in manifest["inventory"] if item.get("admissible") is not True]
    manifest["admitted_count"] = len(manifest["sources"])
    manifest["rejected_count"] = len(manifest["inventory"]) - len(manifest["sources"])
    return manifest


def _sse_date(value: Any, *, field: str) -> date:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise SSEAnnouncementQueryError(f"SSE {field} is not an ISO date: {text!r}") from exc


def _sse_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise SSEAnnouncementQueryError("SSE announcement URL missing")
    return urljoin(SSE_STATIC_BASE_URL, raw)


def normalize_sse_announcement_record(record: dict[str, Any], *, company_code: str) -> dict[str, Any]:
    """Convert one official SSE row into the stable source-inventory shape."""
    security_code = str(record.get("SECURITY_CODE") or record.get("security_code") or "").strip()
    if security_code != company_code:
        raise SSEAnnouncementQueryError(f"SSE row security code mismatch: {security_code!r}")
    published_at = _sse_date(record.get("SSEDATE") or record.get("published_at"), field="SSEDATE").isoformat()
    title = str(record.get("TITLE") or record.get("title") or "").strip()
    if not title:
        raise SSEAnnouncementQueryError("SSE announcement title missing")
    source_url = _sse_url(record.get("URL") or record.get("url"))
    filename = Path(urlparse(source_url).path).stem
    stable_filename = re.sub(r"[^A-Za-z0-9]+", "_", filename).strip("_")
    if not stable_filename:
        raise SSEAnnouncementQueryError("SSE announcement URL has no stable filename")
    normalized: dict[str, Any] = {
        "source_id": f"SSE:{company_code}:ANN:{published_at.replace('-', '')}:{stable_filename}",
        "source_version": f"sse-announcement-original:{stable_filename}",
        "source_type": "EXCHANGE_ANNOUNCEMENT",
        "title": title,
        "url": source_url,
        "published_at": published_at,
        "data_as_of": published_at,
        "revision_policy": "ORIGINAL_VINTAGE",
    }
    bulletin_type = str(record.get("BULLETIN_TYPE") or "").strip()
    if bulletin_type:
        normalized["sse_bulletin_type"] = bulletin_type
    return normalized


def _default_sse_request(params: dict[str, str]) -> dict[str, Any]:
    request = Request(
        SSE_BULLETIN_QUERY_URL + "?" + urlencode(params),
        headers={
            "Referer": "https://www.sse.com.cn/",
            "User-Agent": "Mozilla/5.0 (Phase10 PIT acquisition)",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SSEAnnouncementQueryError(f"SSE query failed: {exc.__class__.__name__}") from exc
    if not isinstance(payload, dict):
        raise SSEAnnouncementQueryError("SSE query response is not an object")
    return payload


def _validate_sse_page(
    payload: dict[str, Any],
    *,
    company_code: str,
    begin_date: date,
    end_date: date,
    expected_page_no: int,
    expected_page_size: int,
) -> tuple[int, list[dict[str, Any]]]:
    if str(payload.get("productId") or "").strip() != company_code:
        raise SSEAnnouncementQueryError("SSE response productId does not match request")
    if str(payload.get("beginDate") or "").strip() != begin_date.isoformat():
        raise SSEAnnouncementQueryError("SSE response beginDate does not match request")
    if str(payload.get("endDate") or "").strip() != end_date.isoformat():
        raise SSEAnnouncementQueryError("SSE response endDate does not match request")
    page_help = payload.get("pageHelp")
    if not isinstance(page_help, dict):
        raise SSEAnnouncementQueryError("SSE response pageHelp missing")
    if page_help.get("pageNo") != expected_page_no or page_help.get("beginPage") != expected_page_no:
        raise SSEAnnouncementQueryError("SSE response page number does not match request")
    if page_help.get("pageSize") != expected_page_size or page_help.get("cacheSize") != 1:
        raise SSEAnnouncementQueryError("SSE response did not honor single-page pagination")
    total = page_help.get("total")
    if type(total) is not int or total < 0:
        raise SSEAnnouncementQueryError("SSE response total is invalid")
    expected_page_count = (total + expected_page_size - 1) // expected_page_size
    if page_help.get("pageCount") != expected_page_count:
        raise SSEAnnouncementQueryError("SSE response page count is inconsistent with total")
    records = page_help.get("data")
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise SSEAnnouncementQueryError("SSE response page data is invalid")
    for record in records:
        security_code = str(record.get("SECURITY_CODE") or record.get("security_code") or "").strip()
        if security_code != company_code:
            raise SSEAnnouncementQueryError("SSE response includes a different security code")
        published_at = _sse_date(record.get("SSEDATE") or record.get("published_at"), field="SSEDATE")
        if not begin_date <= published_at <= end_date:
            raise SSEAnnouncementQueryError("SSE response includes a row outside the requested dates")
    return total, records


def fetch_sse_announcement_records(
    *,
    company_code: str = "600340",
    begin_date: str = "2018-01-01",
    end_date: str = "2020-04-27",
    page_size: int = 100,
    request: Callable[[dict[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fetch and validate every page in an official SSE announcement query."""
    start = _sse_date(begin_date, field="begin_date")
    end = _sse_date(end_date, field="end_date")
    if start > end:
        raise ValueError("begin_date must not be after end_date")
    if type(page_size) is not int or page_size <= 0:
        raise ValueError("page_size must be a positive integer")
    fetch_page = request or _default_sse_request
    records: list[dict[str, Any]] = []
    expected_total: int | None = None
    page_no = 1
    while expected_total is None or len(records) < expected_total:
        params = {
            "productId": company_code,
            "beginDate": start.isoformat(),
            "endDate": end.isoformat(),
            "securityType": SSE_SECURITY_TYPES,
            "reportType": "ALL",
            "pageHelp.pageSize": str(page_size),
            "pageHelp.pageNo": str(page_no),
            "pageHelp.beginPage": str(page_no),
            "pageHelp.cacheSize": "1",
        }
        payload = fetch_page(params)
        if not isinstance(payload, dict):
            raise SSEAnnouncementQueryError("SSE request adapter returned a non-object")
        total, page_records = _validate_sse_page(
            payload,
            company_code=company_code,
            begin_date=start,
            end_date=end,
            expected_page_no=page_no,
            expected_page_size=page_size,
        )
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise SSEAnnouncementQueryError("SSE response total changed during pagination")
        if not page_records and len(records) < expected_total:
            raise SSEAnnouncementQueryError("SSE response ended before the declared total")
        records.extend(deepcopy(page_records))
        if len(records) > expected_total:
            raise SSEAnnouncementQueryError("SSE response exceeded the declared total")
        page_no += 1
        if page_no > expected_total + 1:
            raise SSEAnnouncementQueryError("SSE pagination exceeded the declared total")

    normalized = [normalize_sse_announcement_record(record, company_code=company_code) for record in records]
    return {
        "provider": "SSE",
        "endpoint": SSE_BULLETIN_QUERY_URL,
        "company_code": company_code,
        "begin_date": start.isoformat(),
        "end_date": end.isoformat(),
        "security_types": SSE_SECURITY_TYPES,
        "report_type": "ALL",
        "requested_page_size": page_size,
        "page_count": page_no - 1,
        "record_count": len(normalized),
        "records": normalized,
    }


def build_post_cutoff_reading_queue(inventory: dict[str, Any]) -> dict[str, Any]:
    """Turn official announcement metadata into a bounded claim-reading queue.

    Titles only establish which documents may be read after a formal freeze.
    They are not evidence of a collection, refinancing, guarantee loss, or any
    later investment outcome. This function deliberately does not acquire a
    document body or call the source-package downloader.
    """
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else None
    if records is None or any(not isinstance(record, dict) for record in records):
        raise ValueError("inventory.records must be an array of announcement metadata")
    required_query_fields = ("provider", "endpoint", "company_code", "begin_date", "end_date")
    if any(not inventory.get(field) for field in required_query_fields):
        raise ValueError("inventory is missing official query metadata")
    if type(inventory.get("record_count")) is not int or inventory.get("record_count") < 0:
        raise ValueError("inventory record_count is invalid")
    if inventory.get("record_count") != len(records):
        raise ValueError("inventory record_count does not match records")

    queue: list[dict[str, Any]] = []
    for record in records:
        title = str(record.get("title") or "").strip()
        if not title:
            raise ValueError("announcement metadata title is missing")
        normalized_title = title.casefold()
        candidate_claim_ids: list[str] = []
        matched_terms: dict[str, list[str]] = {}
        for claim_id, terms in POST_CUTOFF_CLAIM_TITLE_TERMS.items():
            matches = [term for term in terms if term.casefold() in normalized_title]
            if matches:
                candidate_claim_ids.append(claim_id)
                matched_terms[claim_id] = matches
        queued = deepcopy(record)
        queued["candidate_claim_ids"] = candidate_claim_ids
        queued["matched_terms"] = matched_terms
        queue.append(queued)

    queue.sort(key=lambda item: (
        str(item.get("published_at") or ""),
        str(item.get("title") or ""),
        str(item.get("source_id") or ""),
    ))
    return {
        "schema_version": "phase10-post-cutoff-inventory.v1",
        "purpose": "OFFICIAL_METADATA_ONLY_READING_QUEUE",
        "metadata_only": True,
        "pdf_downloaded": False,
        "body_read": False,
        "title_match_is_evidence": False,
        "query": {
            **{field: inventory.get(field) for field in required_query_fields},
            "record_count": inventory["record_count"],
        },
        "record_count": len(queue),
        "candidate_record_count": sum(bool(item["candidate_claim_ids"]) for item in queue),
        "records": queue,
    }


def build_600340_manifest_from_sse_records(
    records: Iterable[dict[str, Any]],
    *,
    period_start: str = "2018-01-01",
) -> dict[str, Any]:
    """Overlay the pre-registered annual-report version rules on full SSE rows."""
    catalog = build_600340_source_manifest()
    catalog_by_url = {
        _sse_url(item.get("url")): _source_without_persisted_admission(item)
        for item in catalog["inventory"]
    }
    normalized_records = [deepcopy(item) for item in records]
    record_urls = {_sse_url(item.get("url")) for item in normalized_records}
    missing_catalog_urls = sorted(set(catalog_by_url) - record_urls)
    if missing_catalog_urls:
        raise SSEAnnouncementQueryError("SSE inventory is missing pre-registered primary documents")
    merged: list[dict[str, Any]] = []
    for record in normalized_records:
        source = deepcopy(record)
        catalog_source = catalog_by_url.get(_sse_url(source.get("url")))
        if catalog_source is not None:
            if source.get("published_at") != catalog_source.get("published_at"):
                raise SSEAnnouncementQueryError("SSE primary-document date differs from pre-registered catalog")
            source.update(catalog_source)
        merged.append(source)
    return enumerate_sse_announcements(merged, cutoff_at=DEFAULT_CUTOFF_AT, period_start=period_start)


def fetch_600340_sse_manifest(
    *,
    page_size: int = 100,
    request: Callable[[dict[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a complete 600340 source manifest only after SSE bounds verify."""
    acquisition = fetch_sse_announcement_records(page_size=page_size, request=request)
    manifest = build_600340_manifest_from_sse_records(
        acquisition["records"],
        period_start=acquisition["begin_date"],
    )
    manifest["acquisition_status"] = "SSE_FULL_ENUMERATION_DATE_FILTER_VERIFIED"
    manifest["sse_query"] = {
        key: acquisition[key]
        for key in (
            "provider", "endpoint", "company_code", "begin_date", "end_date",
            "security_types", "report_type", "requested_page_size", "page_count", "record_count",
        )
    }
    return manifest


def _decode_sse_response(response: Any) -> bytes:
    content = response.read()
    content_encoding = response.headers.get("Content-Encoding", "")
    if any(encoding.strip().lower() == "gzip" for encoding in content_encoding.split(",")):
        try:
            content = gzip.decompress(content)
        except (OSError, EOFError) as exc:
            raise SSEAnnouncementQueryError("SSE PDF gzip response is invalid") from exc
    return content


def _sse_bot_challenge_cookie(content: bytes) -> str | None:
    """Solve the supported static SSE ``acw_sc__v2`` challenge without JS."""
    try:
        html = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "document.location.reload" not in html or "posList" not in html:
        return None
    arg1_match = re.search(r"var\s+arg1\s*=\s*['\"]([0-9A-Fa-f]+)['\"]", html)
    positions_match = re.search(r"var\s+posList\s*=\s*\[([^]]+)\]", html)
    table_match = re.search(r"var\s+_0x3e9e\s*=\s*\[(.*?)\]", html, flags=re.DOTALL)
    if arg1_match is None or positions_match is None or table_match is None:
        raise SSEAnnouncementQueryError("SSE bot challenge format is unsupported")
    arg1 = arg1_match.group(1)
    try:
        positions = [int(token.strip(), 16) for token in positions_match.group(1).split(",")]
    except ValueError as exc:
        raise SSEAnnouncementQueryError("SSE bot challenge positions are invalid") from exc
    if len(arg1) != len(positions) or len(arg1) % 2:
        raise SSEAnnouncementQueryError("SSE bot challenge length is invalid")
    mask: str | None = None
    for encoded in re.findall(r"['\"]([^'\"]+)['\"]", table_match.group(1)):
        try:
            decoded = base64.b64decode(encoded, validate=True).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            continue
        if len(decoded) == len(arg1) and re.fullmatch(r"[0-9]+", decoded):
            mask = decoded
            break
    if mask is None:
        raise SSEAnnouncementQueryError("SSE bot challenge mask is missing")
    try:
        reordered = "".join(arg1[position - 1] for position in positions)
        cookie_value = "".join(
            f"{int(reordered[index:index + 2], 16) ^ int(mask[index:index + 2], 16):02x}"
            for index in range(0, len(reordered), 2)
        )
    except (IndexError, ValueError) as exc:
        raise SSEAnnouncementQueryError("SSE bot challenge values are invalid") from exc
    return f"acw_sc__v2={cookie_value}"


def _download_sse_pdf(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "static.sse.com.cn":
        raise SSEAnnouncementQueryError("source PDF URL is outside the official SSE static host")

    def fetch(cookie: str | None = None) -> bytes:
        headers = {
            "Referer": "https://www.sse.com.cn/",
            "User-Agent": "Mozilla/5.0 (Phase10 PIT acquisition)",
            "Accept": "application/pdf",
        }
        if cookie:
            headers["Cookie"] = cookie
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=60) as response:
                return _decode_sse_response(response)
        except OSError as exc:
            raise SSEAnnouncementQueryError(f"SSE PDF download failed: {exc.__class__.__name__}") from exc

    content = fetch()
    if not content.startswith(b"%PDF"):
        challenge_cookie = _sse_bot_challenge_cookie(content)
        if challenge_cookie is not None:
            content = fetch(challenge_cookie)
        if not content.startswith(b"%PDF"):
            raise SSEAnnouncementQueryError("SSE PDF response does not start with the PDF signature")
    return content


def _package_stem(source_id: str, index: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_id).strip("_")
    return f"{index:04d}_{normalized or 'source'}"


def acquire_source_package(
    manifest: dict[str, Any],
    package_root: str | Path,
    *,
    downloader: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """Download admitted official PDFs and materialize their page text.

    Failures remain attached to the source row and keep the package status
    incomplete.  Existing destination files are never replaced.
    """
    result = deepcopy(manifest)
    root = Path(package_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    fetch_pdf = downloader or _download_sse_pdf
    by_id = {
        str(source.get("source_id")): source
        for source in result.get("inventory", [])
        if isinstance(source, dict) and source.get("source_id")
    }
    selected = result.get("sources") if isinstance(result.get("sources"), list) else []
    failures: list[str] = []
    successful: list[str] = []
    for index, selected_source in enumerate(selected, start=1):
        if not isinstance(selected_source, dict):
            continue
        source_id = str(selected_source.get("source_id") or "")
        source = by_id.get(source_id)
        if source is None:
            failures.append(source_id or f"index:{index}")
            continue
        stem = _package_stem(source_id, index)
        package_path = Path("pdf") / f"{stem}.pdf"
        reader_path = Path("reader") / f"{stem}.pages.md"
        enriched = _copy_record(
            source,
            package_path=package_path.as_posix(),
            content_representation=PDF_PAGE_MARKDOWN,
            reader_text_path=reader_path.as_posix(),
        )
        destination = _resolve_package_path(root, package_path.as_posix(), field="source.package_path")
        reader_destination = _resolve_package_path(root, reader_path.as_posix(), field="source.reader_text_path")
        if (
            source.get("package_acquisition_status") == "ADMITTED_PACKAGE"
            and destination.is_file()
            and reader_destination.is_file()
        ):
            successful.append(source_id)
            by_id[source_id] = enriched
            continue
        try:
            if not (source.get("package_acquisition_status") == "FAILED" and destination.is_file()):
                content = fetch_pdf(str(source.get("url") or ""))
                if not content.startswith(b"%PDF"):
                    raise SSEAnnouncementQueryError("downloaded source does not start with the PDF signature")
                if destination.exists():
                    raise FileExistsError(f"source package file already exists: {package_path}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix + ".part")
                if temporary.exists():
                    raise FileExistsError(f"partial source package file already exists: {temporary.name}")
                try:
                    temporary.write_bytes(content)
                    os.replace(temporary, destination)
                finally:
                    if temporary.exists():
                        temporary.unlink()
            enriched = materialize_pdf_page_markdown(
                enriched,
                root,
                reader_text_path=reader_path.as_posix(),
                allow_ocr=True,
            )
            enriched["package_acquisition_status"] = "ADMITTED_PACKAGE"
            successful.append(source_id)
        except (FileExistsError, OSError, SSEAnnouncementQueryError, ValueError) as exc:
            enriched["package_acquisition_status"] = "FAILED"
            enriched["package_acquisition_error"] = f"{exc.__class__.__name__}: {exc}"
            failures.append(source_id)
        by_id[source_id] = enriched

    updated_inventory: list[dict[str, Any]] = []
    for source in result.get("inventory", []):
        source_id = str(source.get("source_id") or "") if isinstance(source, dict) else ""
        updated_inventory.append(by_id.get(source_id, source))
    result["inventory"] = updated_inventory
    result["sources"] = [
        by_id.get(str(source.get("source_id") or ""), source)
        for source in selected
    ]
    result["package_root"] = str(package_root)
    result["source_package"] = {
        "status": "COMPLETE" if not failures else "INCOMPLETE",
        "selected_count": len(selected),
        "successful_count": len(successful),
        "failed_count": len(failures),
        "failed_source_ids": failures,
    }
    result["acquisition_status"] = (
        "SOURCE_PACKAGE_COMPLETE" if not failures else "SOURCE_PACKAGE_INCOMPLETE"
    )
    return result


def _source_without_persisted_admission(source: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(source)
    result.pop("admissible", None)
    result.pop("admission_status", None)
    return result


def validate_source_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate a persisted manifest without contacting the network.

    Admission and selected sources are recomputed from the retained inventory.
    Persisted ``admissible`` flags are review evidence, not an authority that
    can turn a post-cutoff or current-restated record into a usable source.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    cutoff = _timestamp(manifest.get("cutoff_at"))
    if cutoff is None:
        invalid.append("cutoff_at_invalid")
        cutoff = _timestamp(DEFAULT_CUTOFF_AT)

    has_inventory = isinstance(manifest.get("inventory"), list)
    inventory = manifest.get("inventory") if has_inventory else manifest.get("sources")
    if not isinstance(inventory, list) or not inventory:
        incomplete.append("inventory_missing")
        inventory = []
    if manifest.get("enumeration_complete") is not True:
        incomplete.append("sse_enumeration_incomplete")

    ids: set[str] = set()
    inventory_is_valid_shape = True
    for index, source in enumerate(inventory):
        if not isinstance(source, dict):
            invalid.append(f"inventory[{index}]:not_object")
            inventory_is_valid_shape = False
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id:
            invalid.append(f"inventory[{index}]:source_id_missing")
            inventory_is_valid_shape = False
        elif source_id in ids:
            invalid.append(f"inventory[{index}]:duplicate_source_id:{source_id}")
            inventory_is_valid_shape = False
        ids.add(source_id)

    expected_decisions: list[dict[str, Any]] = []
    if inventory_is_valid_shape:
        recomputed = admit_source_manifest(
            [_source_without_persisted_admission(source) for source in inventory],
            cutoff_at=cutoff.isoformat(),
            company_code=str(manifest.get("company_code") or DEFAULT_COMPANY_CODE),
        )
        expected_decisions = recomputed["sources"]
        for index, (stored, expected) in enumerate(zip(inventory, expected_decisions)):
            stored_decision = (stored.get("admissible"), stored.get("admission_status"))
            expected_decision = (expected.get("admissible"), expected.get("admission_status"))
            if stored_decision != expected_decision:
                invalid.append(f"inventory[{index}]:admission_decision_mismatch")

    expected_admitted_ids = [
        str(source["source_id"])
        for source in expected_decisions
        if source.get("admissible") is True
    ]
    expected_rejected_ids = [
        str(source.get("source_id") or "")
        for source in expected_decisions
        if source.get("admissible") is not True
    ]
    expected_selected_sources = [
        source for source in expected_decisions if source.get("admissible") is True
    ]
    if manifest.get("admitted_source_ids") != expected_admitted_ids:
        invalid.append("admitted_source_ids_mismatch")
    if manifest.get("rejected_source_ids") != expected_rejected_ids:
        invalid.append("rejected_source_ids_mismatch")
    if manifest.get("admitted_count") != len(expected_admitted_ids):
        invalid.append("admitted_count_mismatch")
    if manifest.get("rejected_count") != len(expected_rejected_ids):
        invalid.append("rejected_count_mismatch")

    if has_inventory:
        selected_sources = manifest.get("sources")
        if not isinstance(selected_sources, list):
            invalid.append("selected_sources_invalid")
        elif selected_sources != expected_selected_sources:
            invalid.append("selected_sources_mismatch")
            expected_by_id = {str(source["source_id"]): source for source in expected_selected_sources}
            for selected in selected_sources:
                if not isinstance(selected, dict):
                    invalid.append("selected_source_not_object")
                    continue
                source_id = str(selected.get("source_id") or "")
                expected = expected_by_id.get(source_id)
                if expected is None:
                    invalid.append(f"selected_source_not_admitted:{source_id}")
                elif selected != expected:
                    invalid.append(f"selected_source_payload_mismatch:{source_id}")

    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def build_600340_source_manifest() -> dict[str, Any]:
    """Build the offline catalog of known pre-cutoff primary documents.

    This is a catalog, not a claim that PDFs have been downloaded.  The SSE
    announcement inventory is intentionally empty/incomplete until a complete
    export is supplied to :func:`enumerate_sse_announcements`.
    """
    documents = [
        {
            "source_id": "SSE:600340:AR2019:ORIGINAL",
            "source_version": "annual-report-2019-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2019 年年度报告",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2020-04-25/600340_20200425_22.pdf",
            "published_at": "2020-04-25",
            "data_as_of": "2019-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2018:ORIGINAL",
            "source_version": "annual-report-2018-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2018 年年度报告",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2019-04-20/600340_2018_n.pdf",
            "published_at": "2019-04-20",
            "data_as_of": "2018-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:ORIGINAL",
            "source_version": "annual-report-2017-original",
            "source_type": "ANNUAL_REPORT",
            "title": "2017 年年度报告（原始版）",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-03-30/600340_2017_n.pdf",
            "published_at": "2018-03-30",
            "data_as_of": "2017-12-31",
            "revision_policy": "ORIGINAL_VINTAGE",
            "version_group": "SSE:600340:AR2017",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:REVISED",
            "source_version": "annual-report-2017-revised-2018-04-21",
            "source_type": "ANNUAL_REPORT",
            "title": "2017 年年度报告（修订版）",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-04-21/600340_2017_nB.pdf",
            "published_at": "2018-04-21",
            "data_as_of": "2017-12-31",
            "revision_policy": "HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF",
            "version_group": "SSE:600340:AR2017",
            "supersedes": ["SSE:600340:AR2017:ORIGINAL"],
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:INQUIRY_LETTER",
            "source_version": "annual-report-inquiry-letter-2018-04-14",
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "title": "关于对华夏幸福基业股份有限公司2017年年度报告的事后审核问询函",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-04-14/600340_20180414_1.pdf",
            "published_at": "2018-04-14",
            "data_as_of": "2017-12-31",
            "revision_policy": "HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF",
            "admissible": True,
        },
        {
            "source_id": "SSE:600340:AR2017:INQUIRY_REPLY",
            "source_version": "annual-report-inquiry-reply-2018-04-21",
            "source_type": "EXCHANGE_ANNOUNCEMENT",
            "title": "2017 年报问询回复",
            "url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2018-04-21/600340_20180421_9.pdf",
            "published_at": "2018-04-21",
            "data_as_of": "2017-12-31",
            "revision_policy": "HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF",
            "admissible": True,
        },
    ]
    manifest = admit_source_manifest(documents, company_code=DEFAULT_COMPANY_CODE)
    manifest["inventory_kind"] = "KNOWN_PRIMARY_DOCUMENT_CATALOG"
    manifest["enumeration_complete"] = False
    manifest["inventory"] = manifest.pop("sources")
    manifest["sources"] = [item for item in manifest["inventory"] if item.get("admissible") is True]
    manifest["acquisition_status"] = "CATALOG_ONLY_NO_NETWORK_FETCH"
    manifest["announcement_inventory"] = {
        "inventory_kind": "SSE_ANNOUNCEMENT_FULL_ENUMERATION",
        "period_start": "2018-01-01",
        "period_end": "2020-04-27",
        "enumeration_complete": False,
        "records": [],
    }
    return manifest


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["catalog", "validate", "enumerate", "fetch-sse", "fetch-sse-records", "queue-settlement", "download-package"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--company-code", default="600340")
    parser.add_argument("--begin-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()
    if args.command == "catalog":
        payload = build_600340_source_manifest()
    elif args.command == "fetch-sse":
        payload = fetch_600340_sse_manifest(page_size=args.page_size)
    elif args.command == "fetch-sse-records":
        if not args.begin_date or not args.end_date:
            parser.error("--begin-date and --end-date are required for fetch-sse-records")
        payload = fetch_sse_announcement_records(
            company_code=args.company_code,
            begin_date=args.begin_date,
            end_date=args.end_date,
            page_size=args.page_size,
        )
    elif args.command == "download-package":
        if args.input is None:
            parser.error("--input is required for download-package")
        if args.manifest_output is None:
            parser.error("--manifest-output is required for download-package")
        payload = acquire_source_package(
            json.loads(args.input.read_text(encoding="utf-8")),
            args.output,
        )
        _write(args.manifest_output, payload)
        print(json.dumps({
            "written": str(args.manifest_output),
            "package_root": str(args.output),
            "status": payload["source_package"]["status"],
            "successful_count": payload["source_package"]["successful_count"],
            "failed_count": payload["source_package"]["failed_count"],
        }, ensure_ascii=False))
        return 0 if payload["source_package"]["status"] == "COMPLETE" else 2
    else:
        if args.input is None:
            parser.error("--input is required for validate/enumerate/queue-settlement")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if args.command == "validate":
            result = validate_source_manifest(payload)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["state"] == "REVIEWABLE" else 1
        if args.command == "queue-settlement":
            payload = build_post_cutoff_reading_queue(payload)
        else:
            records = payload.get("records") if isinstance(payload, dict) else payload
            payload = enumerate_sse_announcements(records or [])
    _write(args.output, payload)
    count = payload.get("admitted_count", payload.get("record_count", 0))
    print(json.dumps({"written": str(args.output), "record_count": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
