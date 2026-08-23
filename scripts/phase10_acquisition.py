#!/usr/bin/env python3
"""Point-in-time source acquisition primitives for the Phase 10 first case.

The module is deliberately an offline boundary layer.  A caller may feed it
records returned by an official exchange disclosure export (currently SSE or
CNINFO/SZSE) or an already downloaded source catalog; it never uses the
current web page as a proxy for a historical vintage.  Every discovered
announcement is retained, including rejected records, so later review can
distinguish an incomplete enumeration from an empty selection.
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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


MANIFEST_SCHEMA_VERSION = "phase10-source-manifest.v1"
SOURCE_PACKAGE_SELECTION_SCHEMA_VERSION = "phase10-source-package-selection.v2"
INDEPENDENT_INDUSTRY_DATA_CONTRACT_SCHEMA_VERSION = "phase10-independent-industry-data.v2"
SOURCE_ROLE_PROVENANCE_SCHEMA_VERSION = "phase10-source-role-provenance.v1"
LICENSED_INDUSTRY_DATA_SOURCE_TYPE = "LICENSED_INDUSTRY_DATA"
EXTERNAL_DISCLOSURE_RELATIVE_ROLES = {
    "COMPETITOR_DISCLOSURE",
    "SUPPLIER_OR_CUSTOMER_DISCLOSURE",
    "REGULATORY_DISCLOSURE",
}
SOURCE_ROLE_ENTITY_KINDS = {"OPERATING_ENTITY", "REGULATOR"}
SOURCE_ROLE_BASIS_KINDS = {
    "PUBLISHER_PRIMARY_DISCLOSURE",
    "OFFICIAL_REGISTRY_OR_FILING",
    "REGULATORY_PRIMARY_INSTRUMENT",
}
SOURCE_ROLE_BASIS_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "QUARTERLY_REPORT",
    "EXCHANGE_ANNOUNCEMENT", "OTHER_OFFICIAL",
}
_CANONICAL_ENTITY_ID = re.compile(
    r"^(?:ENTITY|LEI|SEC_CIK|CN_UNIFIED|EXCHANGE_SECURITY|REGULATOR):[A-Za-z0-9._:-]+$"
)
INDUSTRY_METRIC_SEMANTICS = {"RETAIL_SELL_OUT", "SHIPMENT", "INVENTORY_STOCK"}
STOCK_FLOW_SEMANTICS = {"RETAIL_SELL_OUT", "SHIPMENT", "INVENTORY_STOCK"}
MEASUREMENT_METHOD_DISCLOSURES = {
    "PROVIDER_METHOD_DOCUMENTED", "PROVIDER_METHOD_PARTIAL", "PROVIDER_METHOD_UNDISCLOSED",
}
MEASUREMENT_ERROR_STATUSES = {"PROVIDER_DECLARED_BOUND", "UNQUANTIFIED"}
MEASUREMENT_INFERENCE_MODES = {
    "DIRECTIONAL_SENSOR_ONLY", "WITHIN_PROVIDER_RELATIVE_CHANGE", "LEVEL_WITH_STATED_LIMITS",
}
MEASUREMENT_DISAGREEMENT_TREATMENTS = {"DO_NOT_AVERAGE_REOPEN_MECHANISM"}
LICENSED_INDUSTRY_SERIES_CONTRACT_FIELDS = (
    "pre_cutoff_source_id", "provider_id", "dataset_id", "metric_id", "semantic",
    "geography", "product_mapping_id", "channel_mapping_id", "brand_mapping_id",
    "denominator_mapping_id",
)
STOCK_FLOW_BOUNDARY_FIELDS = (
    "boundary_id", "geography", "product_mapping_id", "channel_mapping_id",
    "brand_mapping_id", "denominator_mapping_id", "period",
    "inventory_ownership", "definition_locator",
)
SHIPMENT_SELL_IN_STATUSES = {
    "NOT_APPLICABLE",
    "PROVIDER_DEFINED_SELL_IN",
    "SHIPMENT_SEMANTICS_UNRESOLVED",
}
INDUSTRY_RELEASE_STATUSES = {"ORIGINAL_HISTORICAL", "HISTORICAL_REVISION"}
DEFAULT_COMPANY_CODE = "600340.SH"
DEFAULT_CUTOFF_AT = "2020-04-27T18:00:00+08:00"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
PDF_PAGE_MARKDOWN = "PDF_PAGE_MARKDOWN"
WEB_PAGE_MARKDOWN = "WEB_PAGE_MARKDOWN"
OFFICIAL_WEB_RELEASE_ACQUISITION_KIND = "OFFICIAL_WEB_RELEASE"
OFFICIAL_IR_PDF_RELEASE_ACQUISITION_KIND = "OFFICIAL_IR_PDF_RELEASE"
OFFICIAL_ISSUER_RELEASE_ACQUISITION_KINDS = {
    OFFICIAL_WEB_RELEASE_ACQUISITION_KIND,
    OFFICIAL_IR_PDF_RELEASE_ACQUISITION_KIND,
}
OFFICIAL_WEB_RELEASE_SOURCE_TYPE = "OTHER_OFFICIAL"
PDF_PAGE_MARKDOWN_EXTRACTOR = "pdf_preprocessor.extract_all_pages"
PDF_PAGE_MARKDOWN_EXTRACTOR_VERSION = "phase10-pdf-page-markdown.v1"
PDF_TEXT_EXTRACTOR = "pdftotext -layout"
PDF_TEXT_EXTRACTOR_VERSION = "phase10-pdf-page-markdown-poppler.v1"
PDF_OCR_EXTRACTOR = "pdftoppm+tesseract"
PDF_OCR_EXTRACTOR_VERSION = "phase10-pdf-ocr-tesseract.v1"
SSE_BULLETIN_QUERY_URL = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"
SSE_STATIC_BASE_URL = "https://static.sse.com.cn"
SSE_SECURITY_TYPES = "0101,120100,020100,020200,120200"
CNINFO_ANNOUNCEMENT_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE_URL = "https://static.cninfo.com.cn/"
CNINFO_STATIC_HOST = "static.cninfo.com.cn"
# CNINFO's historical fulltext endpoint returns at most 30 records per page.
# Requesting more can make it repeat the first page, which invalidates a
# bounded announcement inventory rather than merely making acquisition slower.
CNINFO_MAX_PAGE_SIZE = 30
CNINFO_QUERY_TABS = frozenset({"fulltext", "relation"})
CNINFO_SSE_CODE_PREFIXES = ("600", "601", "603", "605", "688")
CNINFO_SZSE_CODE_PREFIXES = ("000", "001", "002", "003", "300", "301")

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
    "PUBLISHED_AT_TIME_UNKNOWN_AT_CUTOFF",
    "FUTURE_DATA_AS_OF",
    "FUTURE_REVISION",
    "REVISION_TIME_UNKNOWN_AT_CUTOFF",
    "CURRENT_RESTATED_ONLY",
    "SUPERSEDED_BEFORE_CUTOFF",
    "MISSING_IDENTITY",
    "DUPLICATE_SOURCE_ID",
    "MISSING_ANNOUNCEMENT_TITLE",
    "MISSING_ANNOUNCEMENT_DATE",
    "MISSING_VERSION_FAMILY",
    "INVALID_SUPERSEDES_REFERENCE",
    "INDEPENDENT_INDUSTRY_CONTRACT_INVALID",
    "INDEPENDENT_INDUSTRY_CONTRACT_INCOMPLETE",
    "OFFICIAL_WEB_RELEASE_CONTRACT_INVALID",
    "OFFICIAL_WEB_RELEASE_CONTRACT_INCOMPLETE",
    "SOURCE_ROLE_PROVENANCE_INVALID",
    "SOURCE_ROLE_PROVENANCE_INCOMPLETE",
}


class SSEAnnouncementQueryError(RuntimeError):
    """Raised when the official SSE response cannot prove a bounded inventory."""


class CNInfoAnnouncementExportError(RuntimeError):
    """Raised when an exported CNINFO/SZSE announcement row lacks identity."""


class CNInfoAnnouncementQueryError(RuntimeError):
    """Raised when the official CNINFO response cannot prove a bounded inventory."""


class OfficialWebReleaseError(RuntimeError):
    """Raised when a declared first-party web release cannot be frozen."""


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


def _is_date_precision(value: Any) -> bool:
    """Whether a disclosed date has no publication-time evidence.

    Exchange inventories commonly identify a statutory announcement by date
    only.  Treating that as midnight would quietly admit a disclosure that
    might have appeared after an intraday PIT cutoff.  A date is sufficient
    when it precedes the cutoff day; it is not evidence for availability
    inside that same day.
    """
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value or "").strip()))


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


def _extract_pdf_pages_with_pdftotext(pdf_path: Path) -> list[tuple[int, str]]:
    """Fast, page-preserving text extraction for registered reader copies.

    ``pdfplumber`` remains the fallback because it can help with unusual PDFs,
    but extracting tables from every page of a long annual report is needlessly
    slow for a page-marked reader copy.  The official PDF remains the source;
    this routine only creates the bounded reading representation.
    """
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    chunks = result.stdout.split("\f")
    if chunks and not chunks[-1].strip():
        chunks.pop()
    return [(page_number, text) for page_number, text in enumerate(chunks, start=1)]


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
        pages = _extract_pdf_pages_with_pdftotext(raw_path)
        reader_text_extractor = PDF_TEXT_EXTRACTOR
        reader_text_extractor_version = PDF_TEXT_EXTRACTOR_VERSION
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        try:
            from scripts.pdf_preprocessor import extract_all_pages
        except ModuleNotFoundError:
            from pdf_preprocessor import extract_all_pages
        pages = extract_all_pages(str(raw_path), verbose=False)
        reader_text_extractor = PDF_PAGE_MARKDOWN_EXTRACTOR
        reader_text_extractor_version = PDF_PAGE_MARKDOWN_EXTRACTOR_VERSION
    nonempty_pages = [(number, text.strip()) for number, text in pages if text and text.strip()]
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


class _ReleaseTextExtractor(HTMLParser):
    """Keep the readable text of a first-party release without browser state."""

    _block_tags = {"article", "br", "div", "h1", "h2", "h3", "h4", "li", "p", "section", "table", "td", "th", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in self._block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self._block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "\n".join(
            line.strip() for line in "".join(self.parts).splitlines() if line.strip()
        )).strip()


def materialize_web_page_markdown(
    source: dict[str, Any], package_root: str | Path, *, reader_text_path: str | None = None,
) -> dict[str, Any]:
    """Create a single-page, readable representation of a frozen web release.

    The original HTML stays in the package.  The registered reader copy is a
    rendering-free text extraction with an explicit single-page locator; this
    permits later exact-quote verification without treating a live page as the
    source of record.
    """
    root = Path(package_root).expanduser().resolve()
    raw_relative = _package_relative_path(source.get("package_path"))
    if raw_relative is None:
        raise ValueError("source.package_path must be a relative source-package path")
    raw_path = _resolve_package_path(root, raw_relative, field="source.package_path")
    if raw_path.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("materialize_web_page_markdown requires an HTML package_path")
    if not raw_path.is_file():
        raise FileNotFoundError(f"source HTML missing: {raw_relative}")
    try:
        raw_html = raw_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source HTML must be UTF-8") from exc
    extractor = _ReleaseTextExtractor()
    try:
        extractor.feed(raw_html)
        extractor.close()
    except Exception as exc:  # HTMLParser accepts imperfect HTML; malformed feeds are still unusable.
        raise ValueError("source HTML text extraction failed") from exc
    body = extractor.text()
    if not body:
        raise ValueError("source HTML has no readable text")

    chosen_reader_path = reader_text_path or source.get("reader_text_path")
    if not chosen_reader_path:
        chosen_reader_path = str(Path(raw_relative).with_suffix(".pages.md"))
    reader_relative = _package_relative_path(chosen_reader_path)
    if reader_relative is None:
        raise ValueError("reader_text_path must be a relative source-package path")
    destination = _resolve_package_path(root, reader_relative, field="source.reader_text_path")
    if destination.exists():
        raise FileExistsError("registered web reader path already exists: " + reader_relative)
    lines = [
        "# " + str(source.get("source_id") or ""),
        "",
        "- source_id: " + str(source.get("source_id") or ""),
        "- source_version: " + str(source.get("source_version") or ""),
        "- content_representation: " + WEB_PAGE_MARKDOWN,
        "",
        "## 第 1 页",
        "",
        body,
        "",
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return _copy_record(
        source,
        content_representation=WEB_PAGE_MARKDOWN,
        reader_text_path=reader_relative,
        reader_text_extractor="html.parser.HTMLParser",
        reader_text_extractor_version="phase10-web-page-markdown.v1",
        reader_text_page_count=1,
    )


def _source_identity_ok(source: dict[str, Any]) -> bool:
    required = ("source_id", "source_version", "source_type", "revision_policy")
    return all(str(source.get(field) or "").strip() for field in required)


def validate_official_web_release_source(source: dict[str, Any]) -> dict[str, list[str]]:
    """Validate the small contract for a first-party HTML or PDF release.

    The contract deliberately proves only a named publisher page frozen before
    the research cutoff.  It does not claim a complete historical archive or
    turn a current web page into a reconstructed historical vintage.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if source.get("acquisition_kind") not in OFFICIAL_ISSUER_RELEASE_ACQUISITION_KINDS:
        invalid.append("acquisition_kind_invalid")
    if source.get("source_type") != OFFICIAL_WEB_RELEASE_SOURCE_TYPE:
        invalid.append("source_type_must_be_other_official")
    if source.get("official") is not True:
        invalid.append("official_must_be_true")
    if source.get("revision_policy") != "ORIGINAL_VINTAGE":
        invalid.append("revision_policy_must_be_original_vintage")
    for field in ("title", "publisher_name", "official_publisher_domain", "release_id"):
        if not _contract_text(source.get(field)):
            incomplete.append(field + "_missing")
    url = str(source.get("url") or "").strip()
    parsed = urlparse(url)
    expected_domain = str(source.get("official_publisher_domain") or "").strip().casefold()
    if parsed.scheme != "https" or not parsed.netloc:
        invalid.append("url_must_be_https")
    elif expected_domain and parsed.netloc.casefold() != expected_domain:
        invalid.append("url_domain_does_not_match_declared_publisher")
    return {"invalid_findings": invalid, "incomplete_findings": incomplete}


def _contract_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _source_role_entity_findings(value: Any, *, prefix: str, required_kind: str | None = None) -> tuple[list[str], list[str]]:
    """Validate an identity record without using its display name as evidence.

    ``legal_name`` is retained for human review, but role classification is
    driven only by the stable entity identifier, declared kind, and a separate
    locatable primary basis.  This prevents domains, names, file paths and
    prose labels from becoming an implicit entity resolver.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(value, dict):
        return invalid, [prefix + "_missing"]
    entity_id = str(value.get("entity_id") or "").strip()
    if not entity_id:
        incomplete.append(prefix + ":entity_id_missing")
    elif not _CANONICAL_ENTITY_ID.fullmatch(entity_id):
        invalid.append(prefix + ":entity_id_not_canonical")
    if not _contract_text(value.get("legal_name")):
        incomplete.append(prefix + ":legal_name_missing")
    kind = str(value.get("entity_kind") or "").strip()
    if kind not in SOURCE_ROLE_ENTITY_KINDS:
        invalid.append(prefix + ":entity_kind_invalid")
    elif required_kind is not None and kind != required_kind:
        invalid.append(prefix + ":entity_kind_does_not_match_relative_role")
    return invalid, incomplete


def validate_source_role_provenance(
    source: dict[str, Any], *, source_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, list[str]]:
    """Validate an optional, source-bound external-publisher role contract.

    This validates *provenance shape and availability*, not the economics of a
    relationship.  A role becomes available to P29 only when the publisher,
    subject, bounded scope and a separately readable primary locator are all
    frozen in the source package.  It never infers a role from a URL, source
    type, title, company name or the free-text legal-name display field.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    contract = source.get("source_role_provenance")
    if contract in (None, "", [], {}):
        return {"invalid_findings": invalid, "incomplete_findings": incomplete}
    if not isinstance(contract, dict):
        return {"invalid_findings": ["source_role_provenance:not_object"], "incomplete_findings": incomplete}
    if contract.get("schema_version") != SOURCE_ROLE_PROVENANCE_SCHEMA_VERSION:
        invalid.append("source_role_provenance:schema_version_invalid")
    relative_role = str(contract.get("relative_role") or "").strip()
    if relative_role not in EXTERNAL_DISCLOSURE_RELATIVE_ROLES:
        invalid.append("source_role_provenance:relative_role_invalid")
    expected_publisher_kind = "REGULATOR" if relative_role == "REGULATORY_DISCLOSURE" else "OPERATING_ENTITY"
    entity_invalid, entity_incomplete = _source_role_entity_findings(
        contract.get("publisher_entity"),
        prefix="source_role_provenance:publisher_entity",
        required_kind=expected_publisher_kind if relative_role in EXTERNAL_DISCLOSURE_RELATIVE_ROLES else None,
    )
    invalid.extend(entity_invalid)
    incomplete.extend(entity_incomplete)
    entity_invalid, entity_incomplete = _source_role_entity_findings(
        contract.get("subject_entity"),
        prefix="source_role_provenance:subject_entity",
    )
    invalid.extend(entity_invalid)
    incomplete.extend(entity_incomplete)
    publisher = contract.get("publisher_entity") if isinstance(contract.get("publisher_entity"), dict) else {}
    subject = contract.get("subject_entity") if isinstance(contract.get("subject_entity"), dict) else {}
    publisher_id = str(publisher.get("entity_id") or "").strip()
    subject_id = str(subject.get("entity_id") or "").strip()
    if publisher_id and subject_id and publisher_id == subject_id:
        invalid.append("source_role_provenance:publisher_and_subject_must_differ")

    scope = contract.get("scope")
    if not isinstance(scope, dict):
        incomplete.append("source_role_provenance:scope_missing")
    else:
        for field in ("scope_id", "product_or_service", "geography", "period_start", "period_end"):
            if not _contract_text(scope.get(field)):
                incomplete.append("source_role_provenance:scope:" + field + "_missing")
        start = _timestamp(scope.get("period_start"))
        end = _timestamp(scope.get("period_end"))
        if _contract_text(scope.get("period_start")) and start is None:
            invalid.append("source_role_provenance:scope:period_start_invalid")
        if _contract_text(scope.get("period_end")) and end is None:
            invalid.append("source_role_provenance:scope:period_end_invalid")
        if start is not None and end is not None and start > end:
            invalid.append("source_role_provenance:scope:period_order_invalid")

    basis = contract.get("role_basis")
    if not isinstance(basis, dict):
        incomplete.append("source_role_provenance:role_basis_missing")
    else:
        basis_source_id = str(basis.get("source_id") or "").strip()
        if not basis_source_id:
            incomplete.append("source_role_provenance:role_basis:source_id_missing")
        if not _contract_text(basis.get("locator")):
            incomplete.append("source_role_provenance:role_basis:locator_missing")
        basis_kind = str(basis.get("basis_kind") or "").strip()
        if basis_kind not in SOURCE_ROLE_BASIS_KINDS:
            invalid.append("source_role_provenance:role_basis:basis_kind_invalid")
        elif relative_role == "REGULATORY_DISCLOSURE" and basis_kind != "REGULATORY_PRIMARY_INSTRUMENT":
            invalid.append("source_role_provenance:role_basis:regulatory_primary_instrument_required")
        elif relative_role in {"COMPETITOR_DISCLOSURE", "SUPPLIER_OR_CUSTOMER_DISCLOSURE"} and basis_kind == "REGULATORY_PRIMARY_INSTRUMENT":
            invalid.append("source_role_provenance:role_basis:operating_relationship_cannot_use_regulatory_instrument")
        if source_index is not None and basis_source_id:
            basis_source = source_index.get(basis_source_id)
            if basis_source is None:
                incomplete.append("source_role_provenance:role_basis:source_not_in_manifest")
            elif basis_source.get("admissible") is not True:
                incomplete.append("source_role_provenance:role_basis:source_not_admitted")
            elif str(basis_source.get("source_type") or "").strip() not in SOURCE_ROLE_BASIS_SOURCE_TYPES:
                invalid.append("source_role_provenance:role_basis:source_type_not_first_order")
    return {
        "invalid_findings": list(dict.fromkeys(invalid)),
        "incomplete_findings": list(dict.fromkeys(incomplete)),
    }


def _validate_contract_locator(value: Any, *, prefix: str, incomplete: list[str]) -> None:
    if not isinstance(value, dict):
        incomplete.append(prefix + ":missing_or_invalid")
        return
    for field in ("statement", "locator"):
        if not _contract_text(value.get(field)):
            incomplete.append(prefix + ":" + field + "_missing")


def _same_timestamp(left: Any, right: Any) -> bool:
    parsed_left = _timestamp(left)
    parsed_right = _timestamp(right)
    return parsed_left is not None and parsed_right is not None and parsed_left == parsed_right


def _validate_measurement_profile(profile: Any) -> tuple[list[str], list[str]]:
    """Bound what a provider series may say without assigning it a truth score.

    A versioned vendor export is still a measurement with coverage, sampling,
    mapping, and model-risk limits.  This contract records those limits and
    restricts the maximum inference: a directional sensor can open research,
    a stable provider series can support a within-provider change, and only a
    provider-declared error boundary permits a level claim.  It deliberately
    does not manufacture an accuracy probability or average disagreements.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(profile, dict):
        return invalid, ["measurement_profile_missing"]
    disclosure = profile.get("methodology_disclosure")
    if disclosure not in MEASUREMENT_METHOD_DISCLOSURES:
        invalid.append("measurement_profile:methodology_disclosure_invalid")
    elif disclosure != "PROVIDER_METHOD_UNDISCLOSED":
        _validate_contract_locator(
            profile.get("methodology_locator"),
            prefix="measurement_profile:methodology_locator", incomplete=incomplete,
        )
    elif profile.get("methodology_locator") not in (None, ""):
        invalid.append("measurement_profile:undisclosed_method_cannot_carry_locator")

    error_status = profile.get("error_status")
    if error_status not in MEASUREMENT_ERROR_STATUSES:
        invalid.append("measurement_profile:error_status_invalid")
    elif error_status == "PROVIDER_DECLARED_BOUND":
        _validate_contract_locator(
            profile.get("error_bound_locator"),
            prefix="measurement_profile:error_bound_locator", incomplete=incomplete,
        )
    elif profile.get("error_bound_locator") not in (None, ""):
        invalid.append("measurement_profile:unquantified_error_cannot_carry_bound_locator")
    inference_mode = profile.get("permitted_inference")
    if inference_mode not in MEASUREMENT_INFERENCE_MODES:
        invalid.append("measurement_profile:permitted_inference_invalid")
    elif disclosure == "PROVIDER_METHOD_UNDISCLOSED" and inference_mode != "DIRECTIONAL_SENSOR_ONLY":
        invalid.append("measurement_profile:undisclosed_method_requires_directional_sensor_only")
    elif error_status == "UNQUANTIFIED" and inference_mode == "LEVEL_WITH_STATED_LIMITS":
        invalid.append("measurement_profile:unquantified_error_cannot_support_level_inference")

    limitations = profile.get("known_limitations")
    if not isinstance(limitations, list) or not limitations:
        incomplete.append("measurement_profile:known_limitations_missing")
    else:
        for index, limitation in enumerate(limitations):
            prefix = f"measurement_profile:known_limitations[{index}]"
            if not isinstance(limitation, dict):
                invalid.append(prefix + ":not_object")
                continue
            for field in ("statement", "conservative_treatment"):
                if not _contract_text(limitation.get(field)):
                    incomplete.append(prefix + ":" + field + "_missing")
    if profile.get("disagreement_treatment") not in MEASUREMENT_DISAGREEMENT_TREATMENTS:
        invalid.append("measurement_profile:disagreement_treatment_invalid")
    return invalid, incomplete


def independent_industry_inference_mode(source: dict[str, Any]) -> str | None:
    """Return the provider-declared maximum inference, never a quality score."""
    contract = source.get("industry_data_contract") if isinstance(source, dict) else None
    profile = contract.get("measurement_profile") if isinstance(contract, dict) else None
    return str(profile.get("permitted_inference")) if isinstance(profile, dict) else None


def licensed_industry_series_identity(source: dict[str, Any]) -> dict[str, str] | None:
    """Return the release-independent identity of one licensed panel series.

    A later release must differ in release/version/query identity.  What must
    remain fixed for an outcome settlement is the provider, dataset, metric
    meaning and market-cell mappings.  This is deliberately not a source
    quality score and intentionally excludes release/version/query fields.
    """
    contract = source.get("industry_data_contract") if isinstance(source, dict) else None
    metric = contract.get("metric") if isinstance(contract, dict) else None
    scope = contract.get("scope") if isinstance(contract, dict) else None
    if not isinstance(contract, dict) or not isinstance(metric, dict) or not isinstance(scope, dict):
        return None
    mappings = {
        "product_mapping_id": scope.get("product_mapping"),
        "channel_mapping_id": scope.get("channel_mapping"),
        "brand_mapping_id": scope.get("brand_mapping"),
        "denominator_mapping_id": scope.get("denominator"),
    }
    identity = {
        "provider_id": contract.get("provider_id"),
        "dataset_id": contract.get("dataset_id"),
        "metric_id": metric.get("metric_id"),
        "semantic": metric.get("semantic"),
        "geography": scope.get("geography"),
    }
    for field, mapping in mappings.items():
        identity[field] = mapping.get("mapping_id") if isinstance(mapping, dict) else None
    if any(not _contract_text(value) for value in identity.values()):
        return None
    return {field: str(value) for field, value in identity.items()}


def licensed_industry_series_contract_findings(
    series_contract: Any, *, prefix: str, pre_cutoff_sources: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[str], list[str]]:
    """Validate a frozen licensed-series contract and, when available, resolve it.

    ``pre_cutoff_sources`` is supplied only at the production adapter/case
    boundary, where the admitted source manifest is available.  The thesis
    authoring gate can still require a complete contract before a new ledger
    is frozen without pretending it can read a manifest it was not given.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(series_contract, dict):
        return invalid, [prefix + ":licensed_industry_series_contract_missing"]
    for field in LICENSED_INDUSTRY_SERIES_CONTRACT_FIELDS:
        if not _contract_text(series_contract.get(field)):
            incomplete.append(prefix + ":" + field + "_missing")
    if incomplete or pre_cutoff_sources is None:
        return invalid, incomplete
    source_id = str(series_contract.get("pre_cutoff_source_id") or "")
    source = pre_cutoff_sources.get(source_id)
    if source is None:
        invalid.append(prefix + ":pre_cutoff_source_id_not_admitted")
        return invalid, incomplete
    if source.get("source_type") != LICENSED_INDUSTRY_DATA_SOURCE_TYPE:
        invalid.append(prefix + ":pre_cutoff_source_not_licensed_industry_data")
        return invalid, incomplete
    identity = licensed_industry_series_identity(source)
    if identity is None:
        invalid.append(prefix + ":pre_cutoff_source_series_identity_invalid")
        return invalid, incomplete
    for field, expected in identity.items():
        if series_contract.get(field) != expected:
            invalid.append(prefix + ":" + field + "_does_not_match_pre_cutoff_source")
    return invalid, incomplete


def licensed_industry_series_matches_source(
    series_contract: dict[str, Any], source: dict[str, Any],
) -> bool:
    """Return whether a later licensed release is the frozen panel series."""
    if source.get("source_type") != LICENSED_INDUSTRY_DATA_SOURCE_TYPE:
        return False
    identity = licensed_industry_series_identity(source)
    return identity is not None and all(
        series_contract.get(field) == value for field, value in identity.items()
    )


def validate_independent_industry_data_source(source: dict[str, Any]) -> dict[str, Any]:
    """Validate a licensed industry-data source without claiming the data exist.

    The contract intentionally verifies a *declared historical release* and
    the meaning of its market metric.  It never fetches a vendor portal or
    treats a current product page as a historical observation.  A shipment is
    not promoted to ``sell_in`` unless the provider's own definition is saved
    with a locator in the admitted source package.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    if source.get("source_type") != LICENSED_INDUSTRY_DATA_SOURCE_TYPE:
        invalid.append("source_type_invalid")
    if source.get("official") is not False:
        invalid.append("official_must_be_false_for_independent_industry_data")

    contract = source.get("industry_data_contract")
    if not isinstance(contract, dict):
        incomplete.append("industry_data_contract_missing")
        return {"state": "INCOMPLETE", "invalid_findings": invalid, "incomplete_findings": incomplete}
    if contract.get("schema_version") != INDEPENDENT_INDUSTRY_DATA_CONTRACT_SCHEMA_VERSION:
        invalid.append("schema_version_invalid")

    for field in ("provider_id", "dataset_id"):
        if not _contract_text(contract.get(field)):
            incomplete.append(field + "_missing")

    release = contract.get("release")
    if not isinstance(release, dict):
        incomplete.append("release_missing")
    else:
        for field in ("release_id", "version_id", "published_at", "data_as_of", "revision_status", "revision_id"):
            if not _contract_text(release.get(field)):
                incomplete.append("release:" + field + "_missing")
        revision_status = release.get("revision_status")
        if revision_status not in INDUSTRY_RELEASE_STATUSES:
            invalid.append("release:revision_status_invalid")
        release_published = _timestamp(release.get("published_at"))
        release_as_of = _timestamp(release.get("data_as_of"))
        if release_published is None:
            invalid.append("release:published_at_invalid")
        if release_as_of is None:
            invalid.append("release:data_as_of_invalid")
        if _contract_text(release.get("version_id")) and str(source.get("source_version") or "") != release.get("version_id"):
            invalid.append("release:version_id_does_not_match_source_version")
        if release.get("published_at") not in (None, "") and not _same_timestamp(release.get("published_at"), source.get("published_at")):
            invalid.append("release:published_at_does_not_match_source")
        if release.get("data_as_of") not in (None, "") and not _same_timestamp(release.get("data_as_of"), source.get("data_as_of")):
            invalid.append("release:data_as_of_does_not_match_source")
        revision_published_at = release.get("revision_published_at")
        if revision_status == "ORIGINAL_HISTORICAL":
            if source.get("revision_policy") != "ORIGINAL_VINTAGE":
                invalid.append("release:original_requires_original_vintage_policy")
            if revision_published_at not in (None, "") or source.get("revision_published_at") not in (None, ""):
                invalid.append("release:original_cannot_carry_revision_published_at")
        elif revision_status == "HISTORICAL_REVISION":
            if source.get("revision_policy") != "HISTORICAL_RESTATEMENT_PUBLISHED_BEFORE_CUTOFF":
                invalid.append("release:historical_revision_policy_invalid")
            if not _contract_text(revision_published_at) or _timestamp(revision_published_at) is None:
                incomplete.append("release:revision_published_at_missing_or_invalid")
            elif not _same_timestamp(revision_published_at, source.get("revision_published_at")):
                invalid.append("release:revision_published_at_does_not_match_source")

    query = contract.get("query_identity")
    if not isinstance(query, dict):
        incomplete.append("query_identity_missing")
    else:
        if not _contract_text(query.get("query_id")):
            incomplete.append("query_identity:query_id_missing")
        parameters = query.get("parameters")
        if not isinstance(parameters, dict) or not parameters:
            incomplete.append("query_identity:parameters_missing")

    measurement_invalid, measurement_incomplete = _validate_measurement_profile(
        contract.get("measurement_profile"),
    )
    invalid.extend(measurement_invalid)
    incomplete.extend(measurement_incomplete)

    metric = contract.get("metric")
    if not isinstance(metric, dict):
        incomplete.append("metric_missing")
    else:
        for field in ("metric_id", "unit"):
            if not _contract_text(metric.get(field)):
                incomplete.append("metric:" + field + "_missing")
        semantic = metric.get("semantic")
        if semantic not in INDUSTRY_METRIC_SEMANTICS:
            invalid.append("metric:semantic_invalid")
        _validate_contract_locator(metric.get("provider_definition"), prefix="metric:provider_definition", incomplete=incomplete)
        sell_in_status = metric.get("shipment_sell_in_status")
        if sell_in_status not in SHIPMENT_SELL_IN_STATUSES:
            invalid.append("metric:shipment_sell_in_status_invalid")
        elif semantic in {"RETAIL_SELL_OUT", "INVENTORY_STOCK"} and sell_in_status != "NOT_APPLICABLE":
            invalid.append("metric:non_shipment_cannot_be_labeled_sell_in")
        elif semantic == "SHIPMENT":
            if sell_in_status == "NOT_APPLICABLE":
                invalid.append("metric:shipment_requires_sell_in_status")
            elif sell_in_status == "PROVIDER_DEFINED_SELL_IN":
                _validate_contract_locator(
                    metric.get("provider_sell_in_definition"),
                    prefix="metric:provider_sell_in_definition",
                    incomplete=incomplete,
                )
            elif metric.get("provider_sell_in_definition") not in (None, ""):
                invalid.append("metric:unresolved_shipment_cannot_carry_sell_in_definition")

    scope = contract.get("scope")
    if not isinstance(scope, dict):
        incomplete.append("scope_missing")
    else:
        if not _contract_text(scope.get("geography")):
            incomplete.append("scope:geography_missing")
        for field in ("product_mapping", "channel_mapping", "brand_mapping", "denominator"):
            mapping = scope.get(field)
            prefix = "scope:" + field
            if not isinstance(mapping, dict):
                incomplete.append(prefix + "_missing")
                continue
            for required in ("mapping_id", "definition"):
                if not _contract_text(mapping.get(required)):
                    incomplete.append(prefix + ":" + required + "_missing")

    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"state": state, "invalid_findings": invalid, "incomplete_findings": incomplete}


def validate_stock_flow_reconciliation(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Decide whether three licensed metrics may be reconciled as one flow.

    This checks contracts only.  It deliberately performs no arithmetic and
    cannot infer a company's inventory, retail demand, revenue, or cash.  A
    result is ``RECONCILABLE`` only when one provider release explicitly
    supplies retail sell-out, shipment, and inventory stock under the same
    frozen product, geographic, channel, brand, denominator, period and
    inventory-ownership boundary.
    """
    invalid: list[str] = []
    non_reconcilable: list[str] = []
    by_semantic: dict[str, list[dict[str, Any]]] = {semantic: [] for semantic in STOCK_FLOW_SEMANTICS}
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            invalid.append(prefix + ":not_object")
            continue
        source_validation = validate_independent_industry_data_source(source)
        if source_validation["state"] != "REVIEWABLE":
            invalid.append(prefix + ":independent_industry_source_not_reviewable")
            continue
        contract = source["industry_data_contract"]
        metric = contract["metric"]
        semantic = metric.get("semantic")
        if semantic in by_semantic:
            by_semantic[str(semantic)].append(source)

    selected: list[dict[str, Any]] = []
    for semantic in sorted(STOCK_FLOW_SEMANTICS):
        matching = by_semantic[semantic]
        if len(matching) != 1:
            non_reconcilable.append(f"{semantic.lower()}_source_count_must_equal_one")
        else:
            selected.append(matching[0])
    if invalid:
        return {"state": "INVALID", "invalid_findings": invalid, "non_reconcilable_findings": non_reconcilable}
    if non_reconcilable:
        return {"state": "NOT_RECONCILABLE", "invalid_findings": [], "non_reconcilable_findings": non_reconcilable}

    releases = {
        (
            source["industry_data_contract"]["provider_id"],
            source["industry_data_contract"]["dataset_id"],
            source["industry_data_contract"]["release"]["release_id"],
            source["industry_data_contract"]["release"]["version_id"],
        )
        for source in selected
    }
    if len(releases) != 1:
        non_reconcilable.append("provider_release_or_version_not_shared")

    boundaries: list[dict[str, Any]] = []
    for source in selected:
        contract = source["industry_data_contract"]
        boundary = contract.get("stock_flow_boundary")
        semantic = str(contract["metric"].get("semantic") or "").lower()
        if not isinstance(boundary, dict):
            non_reconcilable.append(semantic + ":stock_flow_boundary_missing")
            continue
        missing = [field for field in STOCK_FLOW_BOUNDARY_FIELDS if not _contract_text(boundary.get(field))]
        if missing:
            non_reconcilable.append(semantic + ":stock_flow_boundary_fields_missing:" + ",".join(missing))
            continue
        scope = contract["scope"]
        expected_ids = {
            "product_mapping_id": scope["product_mapping"].get("mapping_id"),
            "channel_mapping_id": scope["channel_mapping"].get("mapping_id"),
            "brand_mapping_id": scope["brand_mapping"].get("mapping_id"),
            "denominator_mapping_id": scope["denominator"].get("mapping_id"),
            "geography": scope.get("geography"),
        }
        if any(boundary.get(field) != expected for field, expected in expected_ids.items()):
            non_reconcilable.append(semantic + ":stock_flow_boundary_does_not_match_source_scope")
        boundaries.append({field: boundary.get(field) for field in STOCK_FLOW_BOUNDARY_FIELDS})
        if contract["metric"].get("semantic") == "SHIPMENT" and contract["metric"].get("shipment_sell_in_status") != "PROVIDER_DEFINED_SELL_IN":
            non_reconcilable.append("shipment:provider_defined_sell_in_required")

    if len(boundaries) == 3 and any(boundary != boundaries[0] for boundary in boundaries[1:]):
        non_reconcilable.append("stock_flow_boundaries_not_identical")
    state = "NOT_RECONCILABLE" if non_reconcilable else "RECONCILABLE"
    return {"state": state, "invalid_findings": [], "non_reconcilable_findings": non_reconcilable}


def _reject(source: dict[str, Any], reason: str) -> dict[str, Any]:
    return _copy_record(source, admissible=False, admission_status=f"REJECTED_{reason}")


def _admit_one(source: dict[str, Any], cutoff: datetime) -> dict[str, Any]:
    if not _source_identity_ok(source):
        return _reject(source, "MISSING_IDENTITY")
    if source.get("source_type") == LICENSED_INDUSTRY_DATA_SOURCE_TYPE:
        industry_validation = validate_independent_industry_data_source(source)
        if industry_validation["invalid_findings"]:
            return _reject(source, "INDEPENDENT_INDUSTRY_CONTRACT_INVALID")
        if industry_validation["incomplete_findings"]:
            return _reject(source, "INDEPENDENT_INDUSTRY_CONTRACT_INCOMPLETE")
    if source.get("acquisition_kind") in OFFICIAL_ISSUER_RELEASE_ACQUISITION_KINDS:
        web_validation = validate_official_web_release_source(source)
        if web_validation["invalid_findings"]:
            return _reject(source, "OFFICIAL_WEB_RELEASE_CONTRACT_INVALID")
        if web_validation["incomplete_findings"]:
            return _reject(source, "OFFICIAL_WEB_RELEASE_CONTRACT_INCOMPLETE")
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
    if _is_date_precision(source.get("published_at")) and published.date() == cutoff.date():
        return _reject(source, "PUBLISHED_AT_TIME_UNKNOWN_AT_CUTOFF")
    if data_as_of is None:
        return _reject(source, "MISSING_IDENTITY")
    if data_as_of > cutoff:
        return _reject(source, "FUTURE_DATA_AS_OF")
    if revision_at and revision_at > cutoff:
        return _reject(source, "FUTURE_REVISION")
    if revision_at and _is_date_precision(source.get("revision_published_at")) and revision_at.date() == cutoff.date():
        return _reject(source, "REVISION_TIME_UNKNOWN_AT_CUTOFF")
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


def _apply_source_role_provenance_rules(decisions: list[dict[str, Any]]) -> None:
    """Reject only malformed role-declared sources after all PIT admission facts exist.

    The role basis may point at another admitted source, so it cannot be
    checked in ``_admit_one``.  Re-evaluate until a source whose basis was
    itself rejected is also removed; a normal source with no role contract is
    deliberately untouched.
    """
    for _ in range(len(decisions) + 1):
        changed = False
        source_index = {
            str(item.get("source_id") or ""): item
            for item in decisions
            if isinstance(item, dict) and str(item.get("source_id") or "")
        }
        for index, source in enumerate(decisions):
            if source.get("admissible") is not True or source.get("source_role_provenance") in (None, "", [], {}):
                continue
            role_validation = validate_source_role_provenance(source, source_index=source_index)
            reason = (
                "SOURCE_ROLE_PROVENANCE_INVALID" if role_validation["invalid_findings"]
                else "SOURCE_ROLE_PROVENANCE_INCOMPLETE" if role_validation["incomplete_findings"]
                else ""
            )
            if reason:
                decisions[index] = _reject(source, reason)
                changed = True
        if not changed:
            return


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
    _apply_source_role_provenance_rules(decisions)

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


def normalize_official_web_release_record(record: dict[str, Any], *, company_code: str) -> dict[str, Any]:
    """Normalize a declared first-party Investor Relations HTML or PDF release.

    The caller supplies the release identity and the publisher domain from the
    issuer's own IR page.  This is a bounded source set for a live, forward
    experiment; it must not be used to assert an exhaustive historical web
    archive.
    """
    release_id = str(record.get("release_id") or "").strip()
    if not release_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", release_id):
        raise OfficialWebReleaseError("official web release_id is missing or invalid")
    title = str(record.get("title") or "").strip()
    if not title:
        raise OfficialWebReleaseError("official web release title is missing")
    url = str(record.get("url") or "").strip()
    parsed = urlparse(url)
    domain = str(record.get("official_publisher_domain") or parsed.netloc).strip().casefold()
    if parsed.scheme != "https" or not parsed.netloc or parsed.netloc.casefold() != domain:
        raise OfficialWebReleaseError("official web release URL/domain is invalid")
    published_at = str(record.get("published_at") or "").strip()
    data_as_of = str(record.get("data_as_of") or "").strip()
    if _timestamp(published_at) is None or _timestamp(data_as_of) is None:
        raise OfficialWebReleaseError("official web release published_at or data_as_of is invalid")
    publisher_name = str(record.get("publisher_name") or "").strip()
    if not publisher_name:
        raise OfficialWebReleaseError("official web release publisher_name is missing")
    format_value = str(record.get("content_format") or "HTML").strip().upper()
    if format_value not in {"HTML", "PDF"}:
        raise OfficialWebReleaseError("official web release content_format must be HTML or PDF")
    return {
        "source_id": f"IR:{company_code}:{release_id}",
        "source_version": str(record.get("source_version") or f"official-ir-release:{release_id}"),
        "source_type": OFFICIAL_WEB_RELEASE_SOURCE_TYPE,
        "official": True,
        "title": title,
        "url": url,
        "published_at": published_at,
        "data_as_of": data_as_of,
        "revision_policy": "ORIGINAL_VINTAGE",
        "acquisition_kind": (
            OFFICIAL_WEB_RELEASE_ACQUISITION_KIND
            if format_value == "HTML"
            else OFFICIAL_IR_PDF_RELEASE_ACQUISITION_KIND
        ),
        "content_format": format_value,
        "release_id": release_id,
        "publisher_name": publisher_name,
        "official_publisher_domain": domain,
        "language": str(record.get("language") or "en"),
    }


def enumerate_official_web_releases(
    records: Iterable[dict[str, Any]], *, company_code: str, cutoff_at: str,
) -> dict[str, Any]:
    """Freeze a declared set of issuer IR pages/PDFs for a true-forward experiment.

    ``enumeration_complete`` refers only to the explicit release set selected
    for the stated research question.  It does not represent an assertion that
    an issuer's entire website or historical archive was captured.
    """
    normalized = [normalize_official_web_release_record(item, company_code=company_code) for item in records]
    normalized.sort(key=lambda item: (str(item["published_at"]), str(item["source_id"])))
    manifest = admit_source_manifest(normalized, cutoff_at=cutoff_at, company_code=company_code)
    manifest.update({
        "inventory_kind": "OFFICIAL_WEB_RELEASE_DECLARED_SET",
        "enumeration_scope": "DECLARED_RESEARCH_RELEASE_SET_ONLY",
        "enumeration_complete": True,
        "inventory_count": len(normalized),
        "inventory": manifest.pop("sources"),
        "acquisition_status": "OFFICIAL_WEB_RELEASE_SET_DECLARED",
    })
    manifest["sources"] = [item for item in manifest["inventory"] if item.get("admissible") is True]
    manifest["admitted_source_ids"] = [str(item["source_id"]) for item in manifest["sources"]]
    manifest["rejected_source_ids"] = [
        str(item.get("source_id") or "") for item in manifest["inventory"] if item.get("admissible") is not True
    ]
    manifest["admitted_count"] = len(manifest["sources"])
    manifest["rejected_count"] = len(manifest["inventory"]) - len(manifest["sources"])
    return manifest


def enumerate_independent_industry_sources(
    records: Iterable[dict[str, Any]], *, company_code: str, cutoff_at: str,
) -> dict[str, Any]:
    """Freeze a bounded, licensed industry-query result for PIT use.

    ``enumeration_complete`` means the declared provider query/export is fully
    retained in this source package.  It does *not* claim that the vendor's
    whole database is public, complete, or downloaded.  The caller supplies
    an already licensed historical release and its local package path later;
    this helper performs no vendor network access.
    """
    materialized = [deepcopy(item) for item in records]
    manifest = admit_source_manifest(
        materialized,
        cutoff_at=cutoff_at,
        company_code=company_code,
    )
    manifest.update({
        "inventory_kind": "LICENSED_INDUSTRY_DATA_DECLARED_QUERY",
        "enumeration_complete": True,
        "enumeration_basis": "DECLARED_LICENSED_QUERY_IDENTITY",
        "inventory_count": len(materialized),
        "inventory": manifest.pop("sources"),
        "acquisition_status": "LICENSED_INDUSTRY_QUERY_METADATA_FROZEN",
    })
    manifest["sources"] = [
        item for item in manifest["inventory"] if item.get("admissible") is True
    ]
    manifest["admitted_source_ids"] = [str(item["source_id"]) for item in manifest["sources"]]
    manifest["rejected_source_ids"] = [
        str(item.get("source_id") or "")
        for item in manifest["inventory"]
        if item.get("admissible") is not True
    ]
    manifest["admitted_count"] = len(manifest["sources"])
    manifest["rejected_count"] = len(manifest["inventory"]) - len(manifest["sources"])
    return manifest


def compose_company_manifest_with_independent_industry_sources(
    company_manifest: dict[str, Any],
    industry_sources: Iterable[dict[str, Any]],
    *,
    selection_policy_id: str,
    selection_reason: str,
    industry_source_research_rationales: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Add declared licensed exports to one complete company PIT manifest.

    The statutory-announcement inventory is preserved verbatim.  This only
    appends already-acquired, versioned industry releases and re-freezes the
    source selection with an explicit rationale for each new source; it never
    downloads a vendor database or mutates the input manifest.
    """
    validation = validate_source_manifest(company_manifest)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("company manifest must be reviewable before adding industry sources")
    inventory = company_manifest.get("inventory")
    selection = company_manifest.get("source_package_selection")
    if not isinstance(inventory, list) or not isinstance(selection, dict):
        raise ValueError("company manifest requires a complete inventory and frozen source selection")
    additions = [deepcopy(source) for source in industry_sources]
    if not additions or any(
        source.get("source_type") != LICENSED_INDUSTRY_DATA_SOURCE_TYPE for source in additions
    ):
        raise ValueError("only declared LICENSED_INDUSTRY_DATA sources may be composed")
    addition_ids = [str(source.get("source_id") or "").strip() for source in additions]
    existing_ids = {
        str(source.get("source_id") or "").strip()
        for source in inventory if isinstance(source, dict)
    }
    if any(not source_id for source_id in addition_ids) or len(set(addition_ids)) != len(addition_ids):
        raise ValueError("independent industry source IDs must be non-empty and unique")
    if set(addition_ids).intersection(existing_ids):
        raise ValueError("independent industry source ID already exists in the company inventory")

    recomputed = admit_source_manifest(
        [
            _source_without_persisted_admission(source)
            for source in [*inventory, *additions]
            if isinstance(source, dict)
        ],
        cutoff_at=str(company_manifest.get("cutoff_at") or ""),
        company_code=str(company_manifest.get("company_code") or DEFAULT_COMPANY_CODE),
    )
    result = deepcopy(company_manifest)
    result.update(recomputed)
    result["inventory"] = result.pop("sources")
    result["sources"] = [
        source for source in result["inventory"] if source.get("admissible") is True
    ]
    result["inventory_count"] = len(result["inventory"])
    result["inventory_kind"] = "COMPOSITE_COMPANY_AND_INDEPENDENT_INDUSTRY_SOURCE_PACKAGE"
    result["company_inventory_kind"] = company_manifest.get("inventory_kind")
    result["independent_industry_source_ids"] = addition_ids
    # Existing acquisition receipts cover only the old selection.  The new
    # export is checked at its registered path by PITSourcePackage.
    result.pop("source_package", None)
    result.pop("package_root", None)
    result["acquisition_status"] = "COMPOSITE_SOURCE_PACKAGE_METADATA_FROZEN"
    result.pop("source_package_selection", None)

    existing_selected = selection.get("selected_source_ids")
    existing_rationales = selection.get("source_research_rationales")
    if not isinstance(existing_selected, list) or not isinstance(existing_rationales, list):
        raise ValueError("company source selection is malformed")
    result["source_package_selection"] = build_source_package_selection(
        result,
        selection_policy_id=selection_policy_id,
        selection_reason=selection_reason,
        source_ids=[*existing_selected, *addition_ids],
        source_research_rationales=[*existing_rationales, *list(industry_source_research_rationales)],
    )
    composed_validation = validate_source_manifest(result)
    if composed_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "composed source manifest is invalid: "
            + ",".join([*composed_validation["invalid_findings"], *composed_validation["incomplete_findings"]])
        )
    return result


def enumerate_sse_announcements(
    records: Iterable[dict[str, Any]],
    *,
    cutoff_at: str = DEFAULT_CUTOFF_AT,
    period_start: str = "2018-01-01",
    company_code: str = DEFAULT_COMPANY_CODE,
) -> dict[str, Any]:
    """Preserve a full SSE announcement inventory before source selection.

    ``records`` is expected to be the complete result of an SSE page/export for
    the requested period.  The function does not silently discard a future or
    malformed row: each row becomes a source decision and remains reviewable.
    """
    normalized_company_code = str(company_code or "").strip()
    if not normalized_company_code:
        raise ValueError("company_code is required for an SSE announcement manifest")
    if "." not in normalized_company_code:
        normalized_company_code = normalized_company_code + ".SH"
    sse_code = normalized_company_code.split(".", 1)[0]
    materialized = [deepcopy(item) for item in records]
    normalized: list[dict[str, Any]] = []
    for item in materialized:
        title = str(item.get("title") or item.get("announcement_title") or "").strip()
        published_value = item.get("published_at") or item.get("announcement_date")
        published = _timestamp(published_value)
        source = _copy_record(
            item,
            source_id=item.get("source_id") or f"SSE:{sse_code}:ANN:{published_value}:{title}",
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
    manifest = admit_source_manifest(normalized, cutoff_at=cutoff_at, company_code=normalized_company_code)
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


def _cninfo_date(value: Any, *, field: str) -> date:
    """Read CNINFO's date string or millisecond timestamp as Shanghai date."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(float(value) / 1000, tz=LOCAL_TZ).date()
    text = str(value or "").strip()
    if text.isdigit() and len(text) >= 12:
        return datetime.fromtimestamp(float(text) / 1000, tz=LOCAL_TZ).date()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise CNInfoAnnouncementExportError(f"CNINFO {field} is not a date/timestamp: {text!r}") from exc


def _cninfo_source_type_and_period(title: str, published_at: date) -> tuple[str, str]:
    compact = re.sub(r"\s+", "", title)
    annual = re.search(r"(20\d{2})年年度报告", compact)
    if annual:
        return "ANNUAL_REPORT", annual.group(1) + "-12-31"
    interim = re.search(r"(20\d{2})年半年度报告", compact)
    if interim:
        return "INTERIM_REPORT", interim.group(1) + "-06-30"
    quarter = re.search(r"(20\d{2})年(?:第一季度|一季报)", compact)
    if quarter:
        return "EXCHANGE_ANNOUNCEMENT", quarter.group(1) + "-03-31"
    third = re.search(r"(20\d{2})年(?:第三季度|三季报)", compact)
    if third:
        return "EXCHANGE_ANNOUNCEMENT", third.group(1) + "-09-30"
    return "EXCHANGE_ANNOUNCEMENT", published_at.isoformat()


def normalize_cninfo_announcement_record(record: dict[str, Any], *, company_code: str) -> dict[str, Any]:
    """Normalize one row from an already exported CNINFO/SZSE announcement list.

    CNINFO is the statutory-disclosure service used by Shenzhen issuers.  This
    adapter deliberately accepts an offline export rather than treating today's
    search page as a substitute for a historic inventory.  Callers remain
    responsible for proving that their export covers the requested period.
    """
    security_code = str(record.get("secCode") or record.get("security_code") or record.get("company_code") or "").strip()
    if security_code != company_code:
        raise CNInfoAnnouncementExportError(f"CNINFO row security code mismatch: {security_code!r}")
    title = str(record.get("announcementTitle") or record.get("title") or "").strip()
    if not title:
        raise CNInfoAnnouncementExportError("CNINFO announcement title missing")
    published_at = _cninfo_date(record.get("announcementTime") or record.get("published_at"), field="announcementTime")
    raw_url = str(record.get("adjunctUrl") or record.get("url") or "").strip()
    if not raw_url:
        raise CNInfoAnnouncementExportError("CNINFO announcement URL missing")
    source_url = urljoin(CNINFO_STATIC_BASE_URL, raw_url)
    announcement_id = str(record.get("announcementId") or record.get("announcement_id") or "").strip()
    if not announcement_id:
        announcement_id = Path(urlparse(source_url).path).stem
    if not announcement_id:
        raise CNInfoAnnouncementExportError("CNINFO announcement identity missing")
    source_type, inferred_as_of = _cninfo_source_type_and_period(title, published_at)
    data_as_of = str(record.get("data_as_of") or inferred_as_of).strip()
    return {
        "source_id": f"CNINFO:{company_code}:ANN:{published_at.strftime('%Y%m%d')}:{announcement_id}",
        "source_version": f"cninfo-announcement-original:{announcement_id}",
        "source_type": source_type,
        "official": True,
        "title": title,
        "url": source_url,
        "published_at": published_at.isoformat(),
        "data_as_of": data_as_of,
        "revision_policy": "ORIGINAL_VINTAGE",
        "publisher_name": "CNINFO statutory disclosure service",
        "official_publisher_domain": urlparse(CNINFO_STATIC_BASE_URL).netloc,
        "cninfo_announcement_id": announcement_id,
    }


def enumerate_cninfo_announcements(
    records: Iterable[dict[str, Any]], *, company_code: str, cutoff_at: str,
    period_start: str,
) -> dict[str, Any]:
    """Admit a bounded, externally-exported CNINFO announcement inventory.

    The function makes no network call.  It retains every normalized row,
    including later/rejected disclosures, so a complete official export can be
    audited under the same PIT rules as the SSE path.
    """
    normalized = [normalize_cninfo_announcement_record(item, company_code=company_code) for item in records]
    normalized.sort(key=lambda item: (str(item.get("published_at") or ""), str(item.get("source_id") or "")))
    manifest = admit_source_manifest(normalized, cutoff_at=cutoff_at, company_code=company_code + ".SZ")
    manifest.update({
        "inventory_kind": "CNINFO_ANNOUNCEMENT_FULL_EXPORT",
        "period_start": str(period_start),
        "period_end": _timestamp(cutoff_at).date().isoformat() if _timestamp(cutoff_at) else str(cutoff_at)[:10],
        "enumeration_complete": True,
        "inventory_count": len(normalized),
        "inventory": manifest.pop("sources"),
        "acquisition_status": "CNINFO_FULL_EXPORT_DATE_FILTER_VERIFIED",
    })
    manifest["sources"] = [item for item in manifest["inventory"] if item.get("admissible") is True]
    manifest["admitted_source_ids"] = [str(item["source_id"]) for item in manifest["sources"]]
    manifest["rejected_source_ids"] = [str(item.get("source_id") or "") for item in manifest["inventory"] if item.get("admissible") is not True]
    manifest["admitted_count"] = len(manifest["sources"])
    manifest["rejected_count"] = len(manifest["inventory"]) - len(manifest["sources"])
    return manifest


def _default_cninfo_request(params: dict[str, str]) -> dict[str, Any]:
    request = Request(
        CNINFO_ANNOUNCEMENT_QUERY_URL,
        data=urlencode(params).encode("utf-8"),
        headers={
            "Referer": "https://www.cninfo.com.cn/",
            "User-Agent": "Mozilla/5.0 (Phase10 PIT acquisition)",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CNInfoAnnouncementQueryError(f"CNINFO query failed: {exc.__class__.__name__}") from exc
    if not isinstance(payload, dict):
        raise CNInfoAnnouncementQueryError("CNINFO query response is not an object")
    return payload


def _validate_cninfo_page(
    payload: dict[str, Any], *, company_code: str, org_id: str,
    begin_date: date, end_date: date, page_size: int,
) -> tuple[int, list[dict[str, Any]]]:
    total = payload.get("totalAnnouncement")
    records = payload.get("announcements")
    if type(total) is not int or total < 0:
        raise CNInfoAnnouncementQueryError("CNINFO response totalAnnouncement is invalid")
    # CNINFO returns `announcements: null` (rather than an empty array) for a
    # valid query with no matching disclosures.  That is a complete empty
    # enumeration, not a malformed response; treating it as an error prevents
    # a due contract from recording that the statutory source has not yet
    # published its result.
    if total == 0 and records is None:
        records = []
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise CNInfoAnnouncementQueryError("CNINFO response announcements are invalid")
    if len(records) > page_size:
        raise CNInfoAnnouncementQueryError("CNINFO response exceeded requested page size")
    for record in records:
        if str(record.get("secCode") or "").strip() != company_code:
            raise CNInfoAnnouncementQueryError("CNINFO response includes a different security code")
        if str(record.get("orgId") or "").strip() != org_id:
            raise CNInfoAnnouncementQueryError("CNINFO response includes a different organization")
        published_at = _cninfo_date(record.get("announcementTime"), field="announcementTime")
        if not begin_date <= published_at <= end_date:
            raise CNInfoAnnouncementQueryError("CNINFO response includes a row outside the requested dates")
        if not str(record.get("announcementId") or "").strip():
            raise CNInfoAnnouncementQueryError("CNINFO response announcement ID missing")
        if not str(record.get("announcementTitle") or "").strip():
            raise CNInfoAnnouncementQueryError("CNINFO response announcement title missing")
        if not str(record.get("adjunctUrl") or "").strip():
            raise CNInfoAnnouncementQueryError("CNINFO response announcement URL missing")
    return total, records


def _cninfo_query_market(company_code: str) -> tuple[str, str]:
    """Return the CNINFO exchange routing required by one supported A-share code."""
    code = str(company_code or "").strip()
    if code.startswith(CNINFO_SSE_CODE_PREFIXES):
        return "sse", "sh"
    if code.startswith(CNINFO_SZSE_CODE_PREFIXES):
        return "szse", "sz"
    raise ValueError("company_code must use a supported Shanghai or Shenzhen A-share prefix")


def fetch_cninfo_announcement_records(
    *, company_code: str, org_id: str, begin_date: str, end_date: str,
    page_size: int = 30, tab_name: str = "fulltext",
    request: Callable[[dict[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fetch every page of one bounded official CNINFO disclosure query.

    ``fulltext`` is the ordinary announcement inventory.  ``relation`` is
    CNINFO's separately enumerated investor-relations activity-record
    inventory; those records are official issuer disclosures rather than a
    current-page proxy.  A later source package still selects and downloads
    attachments from the frozen inventory; this function never infers company
    facts from titles or page presentation.
    """
    start = _cninfo_date(begin_date, field="begin_date")
    end = _cninfo_date(end_date, field="end_date")
    organization = str(org_id or "").strip()
    if start > end:
        raise ValueError("begin_date must not be after end_date")
    if not organization:
        raise ValueError("org_id is required")
    tab = str(tab_name or "").strip()
    if tab not in CNINFO_QUERY_TABS:
        allowed = ", ".join(sorted(CNINFO_QUERY_TABS))
        raise ValueError(f"tab_name must be one of: {allowed}")
    if type(page_size) is not int or page_size <= 0:
        raise ValueError("page_size must be a positive integer")
    if page_size > CNINFO_MAX_PAGE_SIZE:
        raise ValueError(f"CNINFO page_size must be at most {CNINFO_MAX_PAGE_SIZE}")
    column, plate = _cninfo_query_market(company_code)
    fetch_page = request or _default_cninfo_request
    records: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    expected_total: int | None = None
    page_no = 1
    while expected_total is None or len(records) < expected_total:
        params = {
            "stock": f"{company_code},{organization}",
            "tabName": tab,
            "pageSize": str(page_size),
            "pageNum": str(page_no),
            "column": column,
            "category": "",
            "plate": plate,
            "seDate": f"{start.isoformat()}~{end.isoformat()}",
            "searchkey": "",
            "secid": "",
            # CNINFO otherwise returns its first page for every pageNum on the
            # supported fulltext endpoint.  An explicit stable ordering is
            # therefore part of the acquisition query, not presentation.
            "sortName": "announcementTime",
            "sortType": "desc",
            "isHLtitle": "true",
        }
        payload = fetch_page(params)
        if not isinstance(payload, dict):
            raise CNInfoAnnouncementQueryError("CNINFO request adapter returned a non-object")
        total, page_records = _validate_cninfo_page(
            payload,
            company_code=company_code,
            org_id=organization,
            begin_date=start,
            end_date=end,
            page_size=page_size,
        )
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise CNInfoAnnouncementQueryError("CNINFO response total changed during pagination")
        if not page_records and len(records) < expected_total:
            raise CNInfoAnnouncementQueryError("CNINFO response ended before the declared total")
        for record in page_records:
            announcement_id = str(record["announcementId"])
            if announcement_id in source_ids:
                raise CNInfoAnnouncementQueryError("CNINFO response repeated an announcement across pages")
            source_ids.add(announcement_id)
        records.extend(deepcopy(page_records))
        if len(records) > expected_total:
            raise CNInfoAnnouncementQueryError("CNINFO response exceeded the declared total")
        page_no += 1
        if expected_total > 0 and page_no > expected_total + 1:
            raise CNInfoAnnouncementQueryError("CNINFO pagination exceeded the declared total")
    return {
        "provider": "CNINFO",
        "endpoint": CNINFO_ANNOUNCEMENT_QUERY_URL,
        "company_code": company_code,
        "org_id": organization,
        "tab_name": tab,
        "begin_date": start.isoformat(),
        "end_date": end.isoformat(),
        "requested_page_size": page_size,
        "page_count": page_no - 1,
        "record_count": len(records),
        "records": records,
    }


def fetch_cninfo_manifest(
    *, company_code: str, org_id: str, begin_date: str, cutoff_at: str,
    page_size: int = 30, tab_name: str = "fulltext",
    request: Callable[[dict[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a reviewable CNINFO manifest only after all bounded pages verify."""
    cutoff = _timestamp(cutoff_at)
    if cutoff is None:
        raise ValueError("cutoff_at is invalid")
    acquisition = fetch_cninfo_announcement_records(
        company_code=company_code,
        org_id=org_id,
        begin_date=begin_date,
        end_date=cutoff.date().isoformat(),
        page_size=page_size,
        tab_name=tab_name,
        request=request,
    )
    manifest = enumerate_cninfo_announcements(
        acquisition["records"],
        company_code=company_code,
        period_start=acquisition["begin_date"],
        cutoff_at=cutoff_at,
    )
    is_relation = acquisition["tab_name"] == "relation"
    if is_relation:
        manifest["inventory_kind"] = "CNINFO_RELATION_ACTIVITY_FULL_EXPORT"
        manifest["acquisition_status"] = "CNINFO_RELATION_FULL_ENUMERATION_DATE_FILTER_VERIFIED"
    else:
        manifest["acquisition_status"] = "CNINFO_FULL_ENUMERATION_DATE_FILTER_VERIFIED"
    manifest["cninfo_query"] = {
        key: acquisition[key]
        for key in (
            "provider", "endpoint", "company_code", "org_id", "begin_date", "end_date",
            "tab_name", "requested_page_size", "page_count", "record_count",
        )
    }
    return manifest


def build_source_package_selection(
    manifest: dict[str, Any], *, selection_policy_id: str, selection_reason: str,
    source_ids: Iterable[str], source_research_rationales: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze which admitted source bodies are needed from a full inventory.

    Admission answers whether a dated official row may be read at a cutoff;
    selection answers which admissible attachments a defined research question
    needs materialized.  The latter must never erase the complete inventory.
    """
    validation = validate_source_manifest(manifest)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("source package selection requires a reviewable full manifest")
    policy = str(selection_policy_id or "").strip()
    reason = str(selection_reason or "").strip()
    selected = [str(item or "").strip() for item in source_ids]
    if not policy or not reason or not selected or any(not item for item in selected):
        raise ValueError("source package selection requires policy, reason and non-empty source IDs")
    if len(set(selected)) != len(selected):
        raise ValueError("source package selection source IDs must be unique")
    admitted = set(str(item) for item in manifest.get("admitted_source_ids") or [])
    unknown = sorted(set(selected) - admitted)
    if unknown:
        raise ValueError("source package selection includes non-admitted source IDs: " + ",".join(unknown))
    raw_rationales = list(source_research_rationales)
    if len(raw_rationales) != len(selected) or any(not isinstance(item, dict) for item in raw_rationales):
        raise ValueError("source package selection requires one rationale per selected source")
    rationale_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_rationales:
        source_id = str(raw.get("source_id") or "").strip()
        source_reason = str(raw.get("selection_reason") or "").strip()
        question_ids = raw.get("research_question_ids")
        normalized_question_ids = [str(item or "").strip() for item in question_ids] if isinstance(question_ids, list) else []
        if (
            not source_id
            or not source_reason
            or not normalized_question_ids
            or any(not item for item in normalized_question_ids)
            or len(set(normalized_question_ids)) != len(normalized_question_ids)
            or source_id in rationale_by_id
        ):
            raise ValueError("source package selection rationale is invalid")
        rationale_by_id[source_id] = {
            "source_id": source_id,
            "selection_reason": source_reason,
            "research_question_ids": normalized_question_ids,
        }
    if set(rationale_by_id) != set(selected):
        raise ValueError("source package selection rationales must cover exactly the selected source IDs")
    return {
        "schema_version": SOURCE_PACKAGE_SELECTION_SCHEMA_VERSION,
        "selection_policy_id": policy,
        "selection_reason": reason,
        "inventory_count": int(manifest.get("inventory_count") or len(manifest.get("inventory") or [])),
        "admitted_source_count": len(admitted),
        "selected_source_ids": selected,
        "source_research_rationales": [rationale_by_id[source_id] for source_id in selected],
        "unselected_admitted_count": len(admitted) - len(selected),
    }


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


def _download_cninfo_pdf(url: str) -> bytes:
    """Download an official CNINFO attachment without treating the portal UI as evidence."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != CNINFO_STATIC_HOST:
        raise CNInfoAnnouncementExportError("source PDF URL is outside the official CNINFO static host")
    request = Request(
        url,
        headers={
            "Referer": "https://www.cninfo.com.cn/",
            "User-Agent": "Mozilla/5.0 (Phase10 PIT acquisition)",
            "Accept": "application/pdf",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            content = _decode_sse_response(response)
    except OSError as exc:
        raise CNInfoAnnouncementExportError(f"CNINFO PDF download failed: {exc.__class__.__name__}") from exc
    if not content.startswith(b"%PDF"):
        raise CNInfoAnnouncementExportError("CNINFO PDF response does not start with the PDF signature")
    return content


def _download_official_issuer_release(url: str, *, publisher_domain: str, accept: str) -> bytes:
    """Download one declared issuer release without browser/session fallback."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.netloc.casefold() != str(publisher_domain or "").strip().casefold()
    ):
        raise OfficialWebReleaseError("web release URL is outside the declared official publisher domain")
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Phase10 PIT acquisition)",
            "Accept": accept,
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            content = response.read()
    except OSError as exc:
        raise OfficialWebReleaseError(f"official web release download failed: {exc.__class__.__name__}") from exc
    if not content.strip():
        raise OfficialWebReleaseError("official web release response is empty")
    return content


def _download_official_web_release(url: str, *, publisher_domain: str) -> bytes:
    return _download_official_issuer_release(
        url,
        publisher_domain=publisher_domain,
        accept="text/html,application/xhtml+xml",
    )


def _download_official_ir_pdf_release(url: str, *, publisher_domain: str) -> bytes:
    content = _download_official_issuer_release(
        url,
        publisher_domain=publisher_domain,
        accept="application/pdf",
    )
    if not content.startswith(b"%PDF"):
        raise OfficialWebReleaseError("official issuer PDF response does not start with the PDF signature")
    return content


def _download_official_pdf(url: str) -> bytes:
    """Route a source-package attachment only to its enumerated official host."""
    host = urlparse(url).netloc.lower()
    if host == "static.sse.com.cn":
        return _download_sse_pdf(url)
    if host == CNINFO_STATIC_HOST:
        return _download_cninfo_pdf(url)
    raise ValueError("source PDF URL is outside supported official static hosts")


def _package_stem(source_id: str, index: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_id).strip("_")
    return f"{index:04d}_{normalized or 'source'}"


def acquire_source_package(
    manifest: dict[str, Any],
    package_root: str | Path,
    *,
    downloader: Callable[[str], bytes] | None = None,
) -> dict[str, Any]:
    """Materialize official filings and register pre-acquired licensed exports.

    Failures remain attached to the source row and keep the package status
    incomplete.  Existing destination files are never replaced.
    """
    result = deepcopy(manifest)
    root = Path(package_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    fetch_pdf = downloader or _download_official_pdf
    by_id = {
        str(source.get("source_id")): source
        for source in result.get("inventory", [])
        if isinstance(source, dict) and source.get("source_id")
    }
    admitted_sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    selection = result.get("source_package_selection")
    if selection is None:
        selected = admitted_sources
    else:
        selection_findings = [
            finding for finding in validate_source_manifest(result)["invalid_findings"]
            if finding.startswith("source_package_selection")
        ]
        if selection_findings:
            raise ValueError("source package selection is invalid: " + ",".join(selection_findings))
        requested_ids = selection.get("selected_source_ids") if isinstance(selection, dict) else []
        selected = [by_id[source_id] for source_id in requested_ids if source_id in by_id]
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
        if source.get("source_type") == LICENSED_INDUSTRY_DATA_SOURCE_TYPE:
            enriched = deepcopy(source)
            package_path = str(enriched.get("package_path") or "")
            try:
                if not package_path:
                    raise ValueError("licensed industry export package_path is missing")
                destination = _resolve_package_path(root, package_path, field="source.package_path")
                if not destination.is_file():
                    raise FileNotFoundError("licensed industry export is missing: " + package_path)
                enriched["package_acquisition_status"] = "LICENSED_EXPORT_PRESENT"
                successful.append(source_id)
            except (OSError, ValueError) as exc:
                enriched["package_acquisition_status"] = "FAILED"
                enriched["package_acquisition_error"] = f"{exc.__class__.__name__}: {exc}"
                failures.append(source_id)
            by_id[source_id] = enriched
            continue
        if source.get("acquisition_kind") == OFFICIAL_WEB_RELEASE_ACQUISITION_KIND:
            stem = _package_stem(source_id, index)
            package_path = Path("web") / f"{stem}.html"
            reader_path = Path("reader") / f"{stem}.pages.md"
            enriched = _copy_record(
                source,
                package_path=package_path.as_posix(),
                content_representation=WEB_PAGE_MARKDOWN,
                reader_text_path=reader_path.as_posix(),
            )
            destination = _resolve_package_path(root, package_path.as_posix(), field="source.package_path")
            reader_destination = _resolve_package_path(root, reader_path.as_posix(), field="source.reader_text_path")
            if destination.is_file() and reader_destination.is_file():
                enriched = _copy_record(
                    enriched,
                    reader_text_extractor="interrupted_acquisition_reader_resume",
                    reader_text_extractor_version="phase10-reader-resume.v1",
                    reader_text_page_count=1,
                    package_acquisition_status="ADMITTED_PACKAGE",
                )
                successful.append(source_id)
                by_id[source_id] = enriched
                continue
            try:
                if not destination.is_file():
                    content = (
                        downloader(str(source.get("url") or ""))
                        if downloader is not None
                        else _download_official_web_release(
                            str(source.get("url") or ""),
                            publisher_domain=str(source.get("official_publisher_domain") or ""),
                        )
                    )
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
                enriched = materialize_web_page_markdown(
                    enriched, root, reader_text_path=reader_path.as_posix(),
                )
                enriched["package_acquisition_status"] = "ADMITTED_PACKAGE"
                successful.append(source_id)
            except (FileExistsError, OSError, OfficialWebReleaseError, ValueError) as exc:
                enriched["package_acquisition_status"] = "FAILED"
                enriched["package_acquisition_error"] = f"{exc.__class__.__name__}: {exc}"
                failures.append(source_id)
            by_id[source_id] = enriched
            continue
        if source.get("acquisition_kind") == OFFICIAL_IR_PDF_RELEASE_ACQUISITION_KIND:
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
            if destination.is_file() and reader_destination.is_file():
                page_markers = re.findall(
                    r"^## 第 [0-9]+ 页$",
                    reader_destination.read_text(encoding="utf-8"),
                    flags=re.MULTILINE,
                )
                enriched = _copy_record(
                    enriched,
                    reader_text_extractor="interrupted_acquisition_reader_resume",
                    reader_text_extractor_version="phase10-reader-resume.v1",
                    reader_text_page_count=len(page_markers),
                    package_acquisition_status="ADMITTED_PACKAGE",
                )
                successful.append(source_id)
                by_id[source_id] = enriched
                continue
            try:
                if not destination.is_file():
                    content = (
                        downloader(str(source.get("url") or ""))
                        if downloader is not None
                        else _download_official_ir_pdf_release(
                            str(source.get("url") or ""),
                            publisher_domain=str(source.get("official_publisher_domain") or ""),
                        )
                    )
                    if not content.startswith(b"%PDF"):
                        raise OfficialWebReleaseError("official issuer PDF response does not start with the PDF signature")
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
            except (FileExistsError, OSError, OfficialWebReleaseError, ValueError) as exc:
                enriched["package_acquisition_status"] = "FAILED"
                enriched["package_acquisition_error"] = f"{exc.__class__.__name__}: {exc}"
                failures.append(source_id)
            by_id[source_id] = enriched
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
        if destination.is_file() and reader_destination.is_file():
            # The materializer can finish before a command interruption writes
            # the updated manifest.  The registered reader itself is checked
            # by the PIT runner; retain it and resume the manifest rather than
            # re-reading a 200+ page filing or treating a successful run as a
            # failed download.
            page_markers = re.findall(
                r"^## 第 [0-9]+ 页$",
                reader_destination.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            )
            enriched = _copy_record(
                enriched,
                reader_text_extractor="interrupted_acquisition_reader_resume",
                reader_text_extractor_version="phase10-reader-resume.v1",
                reader_text_page_count=len(page_markers),
            )
            successful.append(source_id)
            by_id[source_id] = enriched
            continue
        try:
            # A prior interrupted run may already have the immutable official
            # PDF but not its registered reader text.  Resume from that exact
            # source-id path instead of re-downloading or failing on existence.
            if not destination.is_file():
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
        except (FileExistsError, OSError, SSEAnnouncementQueryError, CNInfoAnnouncementExportError, ValueError) as exc:
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
        for source in admitted_sources
    ]
    result["package_root"] = str(package_root)
    result["source_package"] = {
        "status": "COMPLETE" if not failures else "INCOMPLETE",
        "selected_count": len(selected),
        "successful_count": len(successful),
        "failed_count": len(failures),
        "failed_source_ids": failures,
        "selection_policy_id": selection.get("selection_policy_id") if isinstance(selection, dict) else None,
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
        incomplete.append("announcement_enumeration_incomplete")

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

    selection = manifest.get("source_package_selection")
    if selection is not None:
        if not isinstance(selection, dict):
            invalid.append("source_package_selection_invalid")
        else:
            if selection.get("schema_version") != SOURCE_PACKAGE_SELECTION_SCHEMA_VERSION:
                invalid.append("source_package_selection_schema_version_invalid")
            if not str(selection.get("selection_policy_id") or "").strip():
                invalid.append("source_package_selection_policy_missing")
            if not str(selection.get("selection_reason") or "").strip():
                invalid.append("source_package_selection_reason_missing")
            selected_ids = selection.get("selected_source_ids")
            if not isinstance(selected_ids, list) or not selected_ids:
                invalid.append("source_package_selection_ids_missing")
            else:
                normalized_selected = [str(item or "").strip() for item in selected_ids]
                if any(not item for item in normalized_selected) or len(set(normalized_selected)) != len(normalized_selected):
                    invalid.append("source_package_selection_ids_invalid")
                unknown_selected = sorted(set(normalized_selected) - set(expected_admitted_ids))
                if unknown_selected:
                    invalid.append("source_package_selection_unknown_source_id:" + ",".join(unknown_selected))
            rationales = selection.get("source_research_rationales")
            if not isinstance(rationales, list) or len(rationales) != len(selected_ids or []):
                invalid.append("source_package_selection_rationales_missing_or_count_mismatch")
            else:
                rationale_ids: list[str] = []
                for index, rationale in enumerate(rationales):
                    if not isinstance(rationale, dict):
                        invalid.append(f"source_package_selection_rationale[{index}]:not_object")
                        continue
                    source_id = str(rationale.get("source_id") or "").strip()
                    rationale_ids.append(source_id)
                    if not source_id or not str(rationale.get("selection_reason") or "").strip():
                        invalid.append(f"source_package_selection_rationale[{index}]:source_id_or_reason_missing")
                    question_ids = rationale.get("research_question_ids")
                    if (
                        not isinstance(question_ids, list)
                        or not question_ids
                        or any(not str(item or "").strip() for item in question_ids)
                        or len({str(item or "").strip() for item in question_ids}) != len(question_ids)
                    ):
                        invalid.append(f"source_package_selection_rationale[{index}]:research_question_ids_invalid")
                normalized_selected = [str(item or "").strip() for item in selected_ids] if isinstance(selected_ids, list) else []
                if len(set(rationale_ids)) != len(rationale_ids) or set(rationale_ids) != set(normalized_selected):
                    invalid.append("source_package_selection_rationale_source_coverage_mismatch")
            if selection.get("inventory_count") != len(inventory):
                invalid.append("source_package_selection_inventory_count_mismatch")
            if selection.get("admitted_source_count") != len(expected_admitted_ids):
                invalid.append("source_package_selection_admitted_count_mismatch")
            selected_count = len(selection.get("selected_source_ids") or []) if isinstance(selection.get("selected_source_ids"), list) else 0
            if selection.get("unselected_admitted_count") != len(expected_admitted_ids) - selected_count:
                invalid.append("source_package_selection_unselected_count_mismatch")

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


def _records_from_payload(payload: Any, *, label: str) -> list[dict[str, Any]]:
    """Read the explicit record list used by a source-enumeration command."""
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError(label + " must contain a records array of objects")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["catalog", "validate", "enumerate", "enumerate-cninfo", "enumerate-web", "enumerate-industry", "compose-industry", "fetch-sse", "fetch-sse-records", "fetch-cninfo", "select-package", "queue-settlement", "download-package"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--industry-input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--selection-input", type=Path)
    parser.add_argument("--page-size", type=int, default=CNINFO_MAX_PAGE_SIZE)
    parser.add_argument("--company-code", default="600340")
    parser.add_argument("--org-id")
    parser.add_argument("--cninfo-tab", choices=sorted(CNINFO_QUERY_TABS), default="fulltext")
    parser.add_argument("--begin-date")
    parser.add_argument("--end-date")
    parser.add_argument("--cutoff-at")
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
    elif args.command == "fetch-cninfo":
        if not args.begin_date or not args.cutoff_at or not args.org_id:
            parser.error("--begin-date, --cutoff-at and --org-id are required for fetch-cninfo")
        payload = fetch_cninfo_manifest(
            company_code=args.company_code,
            org_id=args.org_id,
            begin_date=args.begin_date,
            cutoff_at=args.cutoff_at,
            page_size=args.page_size,
            tab_name=args.cninfo_tab,
        )
    elif args.command == "enumerate-web":
        if args.input is None or not args.cutoff_at:
            parser.error("--input and --cutoff-at are required for enumerate-web")
        payload = enumerate_official_web_releases(
            _records_from_payload(json.loads(args.input.read_text(encoding="utf-8")), label="official web release input"),
            company_code=args.company_code,
            cutoff_at=args.cutoff_at,
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
    elif args.command == "enumerate-industry":
        if args.input is None or not args.cutoff_at:
            parser.error("--input and --cutoff-at are required for enumerate-industry")
        try:
            records = _records_from_payload(
                json.loads(args.input.read_text(encoding="utf-8")),
                label="licensed industry input",
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        payload = enumerate_independent_industry_sources(
            records,
            company_code=args.company_code,
            cutoff_at=args.cutoff_at,
        )
        _write(args.output, payload)
        validation = validate_source_manifest(payload)
        print(json.dumps({
            "written": str(args.output),
            "admitted_count": payload["admitted_count"],
            "state": validation["state"],
        }, ensure_ascii=False))
        return 0 if validation["state"] == "REVIEWABLE" else 1
    elif args.command == "compose-industry":
        if args.input is None or args.industry_input is None or args.selection_input is None:
            parser.error("--input, --industry-input and --selection-input are required for compose-industry")
        try:
            company_manifest = json.loads(args.input.read_text(encoding="utf-8"))
            industry_manifest = json.loads(args.industry_input.read_text(encoding="utf-8"))
            selection_input = json.loads(args.selection_input.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        if not isinstance(industry_manifest, dict):
            parser.error("--industry-input must be an independent industry manifest object")
        if industry_manifest.get("inventory_kind") != "LICENSED_INDUSTRY_DATA_DECLARED_QUERY":
            parser.error("--industry-input must be produced by enumerate-industry")
        industry_validation = validate_source_manifest(industry_manifest)
        if industry_validation["state"] != "REVIEWABLE":
            parser.error("--industry-input is not reviewable: " + ",".join([
                *industry_validation["invalid_findings"], *industry_validation["incomplete_findings"],
            ]))
        if not isinstance(company_manifest, dict):
            parser.error("--input must be a company source manifest object")
        for field in ("company_code", "cutoff_at"):
            if industry_manifest.get(field) != company_manifest.get(field):
                parser.error("--industry-input " + field + " must match the company manifest")
        if not isinstance(selection_input, dict):
            parser.error("--selection-input must be a JSON object")
        rationales = selection_input.get("source_research_rationales")
        if not isinstance(rationales, list):
            parser.error("--selection-input requires source_research_rationales")
        try:
            payload = compose_company_manifest_with_independent_industry_sources(
                company_manifest,
                industry_manifest.get("sources") or [],
                selection_policy_id=str(selection_input.get("selection_policy_id") or ""),
                selection_reason=str(selection_input.get("selection_reason") or ""),
                industry_source_research_rationales=rationales,
            )
        except ValueError as exc:
            parser.error(str(exc))
        _write(args.output, payload)
        print(json.dumps({
            "written": str(args.output),
            "selected_count": len(payload["source_package_selection"]["selected_source_ids"]),
            "state": "REVIEWABLE",
        }, ensure_ascii=False))
        return 0
    elif args.command == "select-package":
        if args.input is None or args.selection_input is None:
            parser.error("--input and --selection-input are required for select-package")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        selection_input = json.loads(args.selection_input.read_text(encoding="utf-8"))
        if not isinstance(selection_input, dict):
            parser.error("--selection-input must be a JSON object")
        rationales = selection_input.get("source_research_rationales")
        if not isinstance(rationales, list):
            parser.error("--selection-input requires source_research_rationales")
        payload["source_package_selection"] = build_source_package_selection(
            payload,
            selection_policy_id=str(selection_input.get("selection_policy_id") or ""),
            selection_reason=str(selection_input.get("selection_reason") or ""),
            source_ids=[str(item.get("source_id") or "") for item in rationales if isinstance(item, dict)],
            source_research_rationales=rationales,
        )
        validation = validate_source_manifest(payload)
        _write(args.output, payload)
        print(json.dumps({
            "written": str(args.output),
            "selected_count": len(payload["source_package_selection"]["selected_source_ids"]),
            "state": validation["state"],
            "invalid_findings": validation["invalid_findings"],
        }, ensure_ascii=False))
        return 0 if validation["state"] == "REVIEWABLE" else 1
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
        elif args.command == "enumerate-cninfo":
            if not args.begin_date or not args.cutoff_at:
                parser.error("--begin-date and --cutoff-at are required for enumerate-cninfo")
            records = payload.get("records") if isinstance(payload, dict) else payload
            payload = enumerate_cninfo_announcements(
                records or [],
                company_code=args.company_code,
                period_start=args.begin_date,
                cutoff_at=args.cutoff_at,
            )
        else:
            records = payload.get("records") if isinstance(payload, dict) else payload
            record_company_code = str(payload.get("company_code") or "").strip() if isinstance(payload, dict) else ""
            requested_company_code = str(args.company_code or "").strip()
            if record_company_code and requested_company_code not in {"", "600340", record_company_code}:
                parser.error("--company-code does not match the SSE record inventory company_code")
            payload = enumerate_sse_announcements(
                records or [],
                cutoff_at=args.cutoff_at or DEFAULT_CUTOFF_AT,
                period_start=args.begin_date or "2018-01-01",
                company_code=record_company_code or requested_company_code,
            )
    _write(args.output, payload)
    count = payload.get("admitted_count", payload.get("record_count", 0))
    print(json.dumps({"written": str(args.output), "record_count": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
