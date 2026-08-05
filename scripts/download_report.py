#!/usr/bin/env python3
"""
财报PDF下载工具 (Financial Report PDF Downloader)

支持两种模式：
1. --url 模式：直接下载指定 URL 的 PDF
2. --auto 模式：自动搜索 cninfo API 并下载最佳匹配 PDF（推荐）

A股通过巨潮资讯网 (cninfo.com.cn) API 搜索，港股通过 hkexnews.hk。

Usage:
    # auto mode (recommended for A-shares):
    python3 scripts/download_report.py \\
        --stock-code SZ000651 \\
        --report-type 年报 \\
        --year 2024 \\
        --save-dir . \\
        --auto

    # with company name for better search:
    python3 scripts/download_report.py \\
        --stock-code SZ000651 \\
        --report-type 年报 \\
        --year 2024 \\
        --company-name 格力电器 \\
        --save-dir . \\
        --auto

    # url mode (existing):
    python3 scripts/download_report.py \\
        --url "https://static.cninfo.com.cn/.../report.pdf" \\
        --stock-code SH600887 \\
        --report-type 年报 \\
        --year 2024 \\
        --save-dir .
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

from downloaders.cninfo import CninfoDownloader
from downloaders.hkexnews import HkexnewsDownloader
from downloaders.sec import SecDownloader

# Exit codes
EXIT_SUCCESS = 0
EXIT_NETWORK_FAILURE = 1
EXIT_PDF_VALIDATION_FAILURE = 2
EXIT_BAD_ARGUMENTS = 3

# Constants
PDF_MAGIC_BYTES = b"%PDF-"
MIN_FILE_SIZE_WARNING = 100 * 1024  # 100KB
DOWNLOAD_TIMEOUT = 120
DEFAULT_MAX_RETRIES = 3
BACKOFF_BASE = 3  # seconds

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

URL_PATTERN = re.compile(
    r"^https?://(stockn\.xueqiu\.com|[\w.-]*10jqka\.com\.cn|[\w.-]*cninfo\.com\.cn|(?:www1?\.)?hkexnews\.hk)/.+\.pdf$",
    re.IGNORECASE,
)


# --- cninfo API search ---

CNINFO_SEARCH_URL = "https://www.cninfo.com.cn/new/fulltextSearch/full"
CNINFO_PDF_BASE = "https://static.cninfo.com.cn/"
CNINFO_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.cninfo.com.cn/",
}

REPORT_KEYWORD_MAP = {
    "年报": "年度报告",
    "annual": "年度报告",
    "中报": "半年度报告",
    "interim": "半年度报告",
    "一季报": "第一季度报告",
    "q1": "第一季度报告",
    "三季报": "第三季度报告",
    "q3": "第三季度报告",
}

# Titles containing these keywords will be EXCLUDED from search results
CNINFO_EXCLUDE_KEYWORDS = [
    "摘要", "英文", "审计报告", "审计", "制度", "更正", "补充",
    "责任追究", "工作制度", "已取消", "更新后", "公告",
    "ESG", "环境", "社会及公司治理", "内部控制",
    # v2.32: HK stock circular keywords — these bundle AGM docs with annual reports
    "董事会报告", "监事会报告", "股东周年大会", "通函", "修订公司章程",
    "经审核综合财务报表", "利润分配方案", "续聘", "财务预算",
    # v10: notification letters masquerading as annual reports
    "通知信函", "通知函", "申请表格", "回条",
    "刊发通知", "非登记股东", "登记股东之通知",
]

# Minimum file size for a valid annual report PDF (2MB). Notification letters are typically < 1MB.
MIN_ANNUAL_REPORT_SIZE = 2_000_000  # 2MB


def search_cninfo(stock_code, report_type, year, company_name=None):
    """搜索巨潮 API 获取最佳匹配财报 PDF。

    委托给 ``CninfoDownloader.search_report()``（分类 API）
    保持向后兼容的 ``{url, title, date, file_id}`` 返回格式。

    Args:
        stock_code: 格式化的股票代码（如 ``SZ000651``, ``SH600887``）。
        report_type: 财报类型（年报/中报/一季报/三季报）。
        year: 财年（如 ``2024``）。
        company_name: 可选公司名（新实现中通过 szse_stock.json 自动获取）。

    Returns:
        ``{url, title, date, file_id}`` 或 ``None``。
    """
    # 提取裸 ticker
    code = re.sub(r"^(SH|SZ)", "", stock_code, flags=re.IGNORECASE)
    print(f"Searching cninfo: {code} {report_type} FY{year} ...", file=sys.stderr)

    try:
        downloader = CninfoDownloader()
        result = downloader.search_report(code, year, report_type)
    except (RuntimeError, ValueError) as exc:
        print(f"cninfo API request failed: {exc}", file=sys.stderr)
        return None

    if result is None:
        print(
            f"cninfo: no matching {report_type} found for FY{year}",
            file=sys.stderr,
        )
        return None

    print(
        f"cninfo: best match → {result['title'][:80]} ({result['date']})",
        file=sys.stderr,
    )
    return result


def get_headers(url):
    """Return headers with Referer matching the URL domain."""
    headers = dict(BASE_HEADERS)
    if "cninfo.com.cn" in url:
        headers["Referer"] = "https://www.cninfo.com.cn/"
    elif "10jqka.com.cn" in url:
        headers["Referer"] = "https://10jqka.com.cn/"
    elif "hkexnews.hk" in url:
        headers["Referer"] = "https://www.hkexnews.hk/"
    else:
        headers["Referer"] = "https://xueqiu.com/"
    return headers


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Download financial report PDF. "
        "Use --url for direct URL download, or --auto for cninfo API search + download."
    )

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--url",
        help="PDF URL from cninfo.com.cn, stockn.xueqiu.com, 10jqka.com.cn, or hkexnews.hk",
    )
    mode_group.add_argument(
        "--auto",
        action="store_true",
        help="Auto-search cninfo API and download the best matching report (A-share only)",
    )
    mode_group.add_argument(
        "--hk",
        action="store_true",
        help="Auto-download from hkexnews.hk for HK stocks (scans filing dates)",
    )
    mode_group.add_argument(
        "--market",
        choices=["US"],
        help="Auto-download for US stocks via SEC EDGAR (e.g. --market US). "
        "Supports 年报/中报/一季报/三季报 mapping to 10-K/10-Q/20-F/6-K.",
    )
    mode_group.add_argument(
        "--check",
        action="store_true",
        help="Check report completeness: verify PDFs exist for all effective years in analysis_contract.json",
    )

    # Common args
    parser.add_argument(
        "--stock-code",
        required=True,
        help="Stock code (e.g. SZ000651, SH600887, 00700)",
    )
    parser.add_argument(
        "--report-type",
        required=True,
        help="Report type (年报/中报/一季报/三季报/annual/interim)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=0,
        help="Fiscal year (e.g. 2024)",
    )
    parser.add_argument(
        "--save-dir",
        default=".",
        help="Directory to save the PDF (default: .)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Max download retries (default: {DEFAULT_MAX_RETRIES})",
    )
    parser.add_argument(
        "--company-name",
        help="Company name for better cninfo search results (optional, --auto mode only)",
    )
    parser.add_argument(
        "--all-years",
        action="store_true",
        help="Download all effective years from analysis_contract.json (requires --save-dir with contract)",
    )

    return parser.parse_args(argv)


def validate_url(url):
    """Validate that the URL points to a supported source and ends with .pdf."""
    if not URL_PATTERN.match(url):
        return False, (
            f"Invalid URL: {url}\n"
            "URL must be a .pdf link from cninfo.com.cn, stockn.xueqiu.com, 10jqka.com.cn, or hkexnews.hk"
        )
    return True, ""


def build_filename(stock_code, report_type, year):
    """Build output filename: {code}_{year}_{report_type}.pdf

    Strips SH/SZ prefix from stock_code to match coordinator.md convention
    (e.g. 600887_2024_年报.pdf).
    """
    # Normalize report type
    type_map = {
        "annual": "年报",
        "interim": "中报",
        "q1": "一季报",
        "q3": "三季报",
    }
    normalized = type_map.get(report_type.lower(), report_type)
    # Strip exchange prefix for filename
    code = re.sub(r"^(SH|SZ)", "", stock_code, flags=re.IGNORECASE)
    return f"{code}_{year}_{normalized}.pdf"


def download_annual_report(url, save_path, max_retries=DEFAULT_MAX_RETRIES):
    """
    Download PDF with retry and validation.

    Returns:
        tuple: (success: bool, message: str, filesize: int)
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            print(
                f"Downloading (attempt {attempt}/{max_retries}): {url}",
                file=sys.stderr,
            )

            response = requests.get(
                url,
                headers=get_headers(url),
                timeout=DOWNLOAD_TIMEOUT,
                stream=True,
            )
            response.raise_for_status()

            # Check Content-Type
            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
                print(
                    f"Warning: Content-Type is '{content_type}', expected PDF",
                    file=sys.stderr,
                )

            # Download to temporary path first, then rename
            tmp_path = save_path + ".tmp"
            total_size = 0
            first_chunk = True

            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        # Validate PDF magic bytes on first chunk
                        if first_chunk:
                            if not chunk[:5].startswith(PDF_MAGIC_BYTES):
                                os.remove(tmp_path)
                                return (
                                    False,
                                    "PDF validation failed: file does not start with %PDF- magic bytes",
                                    0,
                                )
                            first_chunk = False
                        f.write(chunk)
                        total_size += len(chunk)

            # Rename tmp to final
            if os.path.exists(save_path):
                os.remove(save_path)
            os.rename(tmp_path, save_path)

            # Size warning
            if total_size < MIN_FILE_SIZE_WARNING:
                print(
                    f"Warning: file size ({total_size} bytes) is smaller than expected (<100KB)",
                    file=sys.stderr,
                )

            return True, "Download successful", total_size

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            print(
                f"Attempt {attempt} failed: {last_error}", file=sys.stderr
            )
            # Clean up partial download
            tmp_path = save_path + ".tmp"
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            if attempt < max_retries:
                wait_time = BACKOFF_BASE * attempt  # 3s, 6s, 9s
                print(f"Retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)

    return False, f"Download failed after {max_retries} attempts: {last_error}", 0


def print_result(success, filepath="", filesize=0, url="", stock_code="",
                 report_type="", year="", message=""):
    """Print structured result block for Claude to parse."""
    status = "SUCCESS" if success else "FAILED"
    print("\n---RESULT---")
    print(f"status: {status}")
    print(f"filepath: {filepath}")
    print(f"filesize: {filesize}")
    print(f"url: {url}")
    print(f"stock_code: {stock_code}")
    print(f"report_type: {report_type}")
    print(f"year: {year}")
    print(f"message: {message}")
    print("---END---")


def record_document_source(
    save_dir: str,
    filename: str,
    *,
    url: str,
    published_at: str | None = None,
    title: str = "",
    provider: str = "",
) -> None:
    """Persist acquisition provenance for the Phase 01 document manifest."""
    path = os.path.join(save_dir, "document_sources.json")
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        payload = {"schema_version": "document-sources.v1", "documents": {}}
    if not isinstance(payload, dict):
        payload = {"schema_version": "document-sources.v1", "documents": {}}
    documents = payload.setdefault("documents", {})
    if not isinstance(documents, dict):
        documents = {}
        payload["documents"] = documents
    documents[str(filename)] = {
        "source_url": str(url or "") or None,
        "published_at": str(published_at or "") or None,
        "title": str(title or ""),
        "provider": str(provider or ""),
        "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def download_from_cre8ir(stock_code: str, year: int, save_dir: str) -> str | None:
    """Download HK stock annual report from cre8ir.com IR portal (v2.32).

    cre8ir.com hosts IR pages for many HK-listed companies.
    Returns local file path on success, None on failure.
    """
    code_short = stock_code.lstrip("0") if stock_code.isdigit() else stock_code
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    year_cn = {2021: "二零二一年", 2022: "二零二二年", 2023: "二零二三年",
               2024: "二零二四年", 2025: "二零二五年"}.get(year, str(year))
    for page in [1, 2]:
        try:
            r = s.get(f"http://www.cre8ir.com/cn/{code_short}/reports.html?page={page}", timeout=15)
            if r.status_code != 200: break
        except Exception: break
        pdfs = re.findall(r'href="(/static/pdf/[^"]+\.pdf)"[^>]*>([^<]*)</a>', r.text)
        for pdf_path, title in pdfs:
            if year_cn in title or f"{year}年" in title:
                url = f"https://www.cre8ir.com{pdf_path}"
                fname = f"{stock_code}_{year}_年报.pdf"
                fpath = os.path.join(save_dir, fname)
                print(f"下载 {fname} (cre8ir)...", file=sys.stderr)
                try:
                    r2 = s.get(url, timeout=60)
                    with open(fpath, 'wb') as f: f.write(r2.content)
                    if os.path.getsize(fpath) > 100000:
                        print(f"  已保存: {fpath} ({os.path.getsize(fpath):,} bytes)", file=sys.stderr)
                        record_document_source(save_dir, fname, url=url, title=title, provider="cre8ir")
                        return fpath
                except Exception as e: print(f"  cre8ir error: {e}", file=sys.stderr)
    return None


def _count_cjk_dup_pairs(text: str) -> int:
    """Count consecutive identical CJK character pairs (pdfplumber CFF font bug)."""
    dup = 0
    for i in range(len(text) - 1):
        a, b = text[i], text[i + 1]
        if a != b:
            continue
        ca, cb = ord(a), ord(b)
        if ((0x4E00 <= ca <= 0x9FFF or 0x3400 <= ca <= 0x4DBF)
                and (0x4E00 <= cb <= 0x9FFF or 0x3400 <= cb <= 0x4DBF)):
            dup += 1
    return dup


def _is_valid_annual_report(pdf_path: str) -> tuple[bool, str]:
    """Validate that a downloaded PDF is an actual annual report, not a notification letter.

    Checks:
      1. File size >= MIN_ANNUAL_REPORT_SIZE (2MB)
      2. PDF starts with %PDF- magic bytes
      3. Quick text scan: must contain 年报/年度报告 keywords in first few pages

    Args:
        pdf_path: Path to the downloaded PDF.

    Returns:
        (is_valid, reason) tuple.
    """
    if not os.path.exists(pdf_path):
        return False, "文件不存在"

    size = os.path.getsize(pdf_path)
    if size < MIN_ANNUAL_REPORT_SIZE:
        return False, f"文件过小 ({size//1024}KB < {MIN_ANNUAL_REPORT_SIZE//1_000_000}MB)，可能为通知信函而非完整年报"

    # Check PDF magic bytes
    with open(pdf_path, "rb") as f:
        header = f.read(10)
    if not header.startswith(b"%PDF-"):
        return False, "不是有效的 PDF 文件"

    # Quick text scan: check for annual report keywords in first 10 pages
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_check = min(10, len(pdf.pages))
            text_samples = []
            for i in range(pages_to_check):
                t = pdf.pages[i].extract_text() or ""
                text_samples.append(t)
            combined = "".join(text_samples)
            has_report_keywords = any(
                kw in combined for kw in ["年度报告", "年报", "Annual Report", "年報",
                                           "管理层讨论", "董事会报告", "财务报表", "合并报表",
                                           "综合损益", "财务状况表", "现金流量表",
                                           "独立核数师", "独立审计师", "审计意见"])
            if not has_report_keywords:
                return False, "PDF 内容不含年报关键术语，可能为通知信函或摘要"
    except ImportError:
        pass  # pdfplumber not available, skip content check
    except Exception as e:
        print(f"  ⚠️ PDF content validation skipped: {e}", file=sys.stderr)

    return True, "OK"


def _retry_download_with_next_match(
    stock_code: str, year: int, save_dir: str, skip_urls: set[str],
    report_type: str = "年报", company_name: str | None = None,
    is_hk: bool = False,
) -> str | None:
    """Retry download after a validation failure, skipping previously tried URLs.

    Re-calls search_cninfo (which now has updated exclusion keywords) and
    filters out previously-failed URLs. Falls back to hkexnews for HK stocks.

    Args:
        stock_code: Stock code.
        year: Fiscal year.
        save_dir: Save directory.
        skip_urls: Set of URLs to skip (from previous failed attempts).
        report_type: Report type.
        company_name: Optional company name.
        is_hk: Whether this is an HK stock.

    Returns:
        Path to valid downloaded PDF, or None if all options exhausted.
    """
    print(f"  🔄 验证失败，排除已尝试URL后重试 cninfo...", file=sys.stderr)

    # Re-call search_cninfo — updated exclusion keywords should skip notification letters
    result = search_cninfo(stock_code, report_type, year, company_name)
    if result and result.get("url", "") not in skip_urls:
        fname = build_filename(stock_code, report_type, year)
        fpath = os.path.join(save_dir, fname)
        print(f"  重试URL: {result.get('title', '')[:80]}", file=sys.stderr)
        success, msg, size = download_annual_report(result["url"], fpath, max_retries=2)
        if success:
            valid, reason = _is_valid_annual_report(fpath)
            if valid:
                record_document_source(
                    save_dir, fname, url=result["url"],
                    published_at=result.get("date"), title=result.get("title", ""), provider="cninfo",
                )
                return fpath
            else:
                print(f"  ⚠️ 重试下载仍无效 ({reason})", file=sys.stderr)
                skip_urls.add(result["url"])
                if os.path.exists(fpath):
                    os.remove(fpath)

    # HK fallback: try hkexnews multi-strategy
    if is_hk:
        print(f"  🔄 cninfo重试耗尽，回退到hkexnews多策略下载...", file=sys.stderr)
        return download_hk(stock_code, year, save_dir, skip_cninfo=True)

    return None


def ocr_pdf_if_needed(pdf_path: str, max_pages: int = 15) -> str | None:
    """V8.4: Auto-detect image PDFs and OCR to text using Vision LLM.

    Detection now uses 3 signals instead of just char count:
      1. CJK character duplication rate (pdfplumber CFF font bug)
      2. Blank/short page ratio (typical of image-based PDFs)
      3. Total extractable chars (legacy check, kept as fallback)

    Returns path to _ocr.txt, or None if the PDF is text-based.
    """
    try:
        import pdfplumber
    except ImportError:
        return None

    # Step 1: Multi-signal image PDF detection
    text_chars = 0
    cjk_dup_pages = 0
    blank_pages = 0
    sampled = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            sample_pages = min(max_pages, total_pages)
            for page in pdf.pages[:sample_pages]:
                t = page.extract_text() or ""
                sampled += 1
                text_chars += len(t)

                # Signal 1: CJK duplication (pdfplumber CFF bug)
                if len(t) >= 50:
                    cjk_dups = _count_cjk_dup_pairs(t)
                    if cjk_dups / len(t) > 0.05:
                        cjk_dup_pages += 1

                # Signal 2: Blank / very short pages (image-based PDFs)
                if len(t.strip()) < 100:
                    blank_pages += 1
    except Exception:
        pass

    if sampled == 0:
        return None

    cjk_dup_ratio = cjk_dup_pages / sampled
    blank_ratio = blank_pages / sampled

    # Decision: image PDF if ANY of:
    #   (a) >20% of sampled pages have CJK duplication
    #   (b) >50% of sampled pages are blank/short AND total chars < 2000
    #   (c) total chars < 500 (legacy: genuinely empty text layer)
    is_image_pdf = (
        cjk_dup_ratio > 0.20
        or (blank_ratio > 0.50 and text_chars < 2000)
        or text_chars <= 500
    )

    if not is_image_pdf:
        print(f"  ✅ Text PDF detected ({text_chars} chars, "
              f"dup={cjk_dup_ratio:.0%}, blank={blank_ratio:.0%}) — skip OCR",
              file=sys.stderr)
        return None

    reason = ("CJK duplication" if cjk_dup_ratio > 0.20
              else "blank pages" if blank_ratio > 0.50
              else "no extractable text")
    print(f"  🔍 Image PDF detected ({reason}, "
          f"chars={text_chars}, dup={cjk_dup_ratio:.0%}, blank={blank_ratio:.0%})",
          file=sys.stderr)

    # Step 2: Tesseract OCR (only when image PDF detected)
    ocr_path = pdf_path.replace(".pdf", "_ocr.txt").replace(".PDF", "_ocr.txt")

    try:
        import pytesseract
        from pdf2image import convert_from_path
        from PIL import Image
    except ImportError as e:
        print(f"  ⚠️ OCR skipped (missing dependency: {e})", file=sys.stderr)
        return None

    print(f"  🔍 Starting tesseract OCR...", file=sys.stderr)
    try:
        images = convert_from_path(pdf_path, first_page=1,
                                    last_page=min(max_pages, 200), dpi=200)
        all_text = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            all_text.append(f"=== Page {i+1} ===\n{text}")
            if (i + 1) % 10 == 0:
                print(f"    OCR progress: {i+1}/{len(images)} pages", file=sys.stderr)

        with open(ocr_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(all_text))

        total_chars = sum(len(t) for t in all_text)
        print(f"  ✅ OCR complete: {ocr_path} ({total_chars:,} chars, {len(images)} pages)",
              file=sys.stderr)
        return ocr_path
    except Exception as e:
        print(f"  ⚠️ OCR failed: {e}", file=sys.stderr)
        return None


def download_hk(stock_code: str, year: int, save_dir: str, skip_cninfo: bool = False) -> str | None:
    """Download HK stock annual report. Strategies (in order):
    1. cre8ir.com IR portal (many HK stocks use this)
    2. hkexnews titleSearchServlet API (disclosure via HkexnewsDownloader)
    3. cninfo API (A+H dual-listed)
    4. hkexnews.hk date scanning (legacy fallback)
    """
    # Strategy 1: cre8ir.com
    result = download_from_cre8ir(stock_code, year, save_dir)
    if result:
        return result

    # Strategy 2: hkexnews titleSearchServlet API (new — from Dayu)
    try:
        downloader = HkexnewsDownloader()
        search_result = downloader.search_report(stock_code, year, "年报")
        if search_result:
            fname = f"{stock_code}_{year}_年报.pdf"
            fpath = os.path.join(save_dir, fname)
            print(f"下载 {fname} (hkexnews API)...", file=sys.stderr)
            success, _, _ = downloader.download_pdf(search_result["url"], fpath)
            if success and os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
                print(f"  已保存: {fpath} ({os.path.getsize(fpath):,} bytes)", file=sys.stderr)
                record_document_source(
                    save_dir, fname, url=search_result["url"],
                    published_at=search_result.get("date"), title=search_result.get("title", ""), provider="hkexnews",
                )
                return fpath
    except (RuntimeError, ValueError) as exc:
        print(f"  hkexnews API skipped: {exc}", file=sys.stderr)

    # Strategy 3: cninfo API (some HK stocks dual-list and file there)
    import concurrent.futures

    file_year = year + 1
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
    })

    if not skip_cninfo:
        try:
            result = search_cninfo(stock_code=stock_code, report_type="年报", year=year)
            if result:
                url = result["url"]
                fname = f"{stock_code}_{year}_年报.pdf"
                fpath = os.path.join(save_dir, fname)
                print(f"下载 {fname} (cninfo static)...", file=sys.stderr)
                download_annual_report(url, fpath, max_retries=2)
                if os.path.getsize(fpath) > 100000:
                    print(f"  已保存: {fpath} ({os.path.getsize(fpath):,} bytes)", file=sys.stderr)
                    record_document_source(
                        save_dir, fname, url=url, published_at=result.get("date"),
                        title=result.get("title", ""), provider="cninfo",
                    )
                    return fpath
                adj = result.get("adjunct_url", "") or result.get("adjunctUrl", "") or url.replace("https://static.cninfo.com.cn/", "")
                if adj:
                    webchat_url = f'http://webchat.cninfo.com.cn/pdf/?obj=%7B%22docUrl%22%3A%22{adj}%22%7D'
                    print(f"下载 {fname} (cninfo webchat)...", file=sys.stderr)
                    download_annual_report(webchat_url, fpath, max_retries=2)
                    if os.path.getsize(fpath) > 100000:
                        print(f"  已保存: {fpath} ({os.path.getsize(fpath):,} bytes)", file=sys.stderr)
                        record_document_source(
                            save_dir, fname, url=webchat_url, published_at=result.get("date"),
                            title=result.get("title", ""), provider="cninfo_webchat",
                        )
                        return fpath
        except Exception:
            pass

    # Strategy 4: Legacy hkexnews date scanning (last resort)
    date_patterns = [(4, 28), (4, 25), (4, 26), (4, 29), (4, 27), (4, 24), (3, 31), (3, 28)]
    s.headers["Referer"] = "https://www.hkexnews.hk/"

    def try_date(month, day, n):
        date_str = f"{file_year}{month:02d}{day:02d}"
        url = f"https://www1.hkexnews.hk/listedco/listconews/sehk/{file_year}/{month:02d}{day:02d}/{date_str}{n:04d}.pdf"
        try:
            r = s.head(url, timeout=3)
            if r.status_code == 200 and int(r.headers.get('content-length', 0)) > 500000:
                return url
        except Exception:
            pass
        return None

    found_url = None
    total_attempts = 0
    max_attempts = 60

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {}
        for month, day in date_patterns:
            if total_attempts >= max_attempts:
                break
            for n in range(1, 80):
                if total_attempts >= max_attempts:
                    break
                futures[ex.submit(try_date, month, day, n)] = None
                total_attempts += 1
        for f in concurrent.futures.as_completed(futures):
            url = f.result()
            if url:
                found_url = url
                for remaining in futures:
                    remaining.cancel()
                break
            if len([ff for ff in futures if ff.done()]) >= 20:
                done_results = [ff.result() for ff in futures if ff.done()]
                if all(r is None for r in done_results):
                    print("  hkexnews appears to be blocking (all attempts failed) — skipping", file=sys.stderr)
                    for remaining in futures:
                        remaining.cancel()
                    break

    if not found_url:
        return None

    fname = f"{stock_code}_{year}_年报.pdf"
    fpath = os.path.join(save_dir, fname)
    print(f"下载 {fname} (hkexnews)...", file=sys.stderr)
    r = s.get(found_url, timeout=60)
    with open(fpath, 'wb') as f:
        f.write(r.content)
    print(f"  已保存: {fpath} ({len(r.content):,} bytes)", file=sys.stderr)
    record_document_source(save_dir, fname, url=found_url, provider="hkexnews_legacy")
    return fpath


def main(argv=None):
    args = parse_args(argv)

    # --check: verify PDF completeness against analysis_contract.json
    if args.check:
        contract_path = os.path.join(args.save_dir, "analysis_contract.json")
        if not os.path.exists(contract_path):
            print(f"Error: analysis_contract.json not found in {args.save_dir}. Run Phase 0 first.",
                  file=sys.stderr)
            sys.exit(EXIT_BAD_ARGUMENTS)
        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)
        years = contract.get("effective_years", [])
        if not years:
            print("Error: no effective_years in analysis_contract.json", file=sys.stderr)
            sys.exit(EXIT_BAD_ARGUMENTS)

        code = re.sub(r"^(SH|SZ)", "", args.stock_code, flags=re.IGNORECASE)
        missing: list[int] = []
        found: list[int] = []
        for yr in years:
            fname = build_filename(args.stock_code, args.report_type, yr)
            fpath = os.path.join(args.save_dir, fname)
            if os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
                found.append(yr)
            else:
                missing.append(yr)

        print(f"📋 {code} 年报完整性检查 ({args.report_type}):", file=sys.stderr)
        print(f"   有效年份: {years}", file=sys.stderr)
        print(f"   已下载:   {found if found else '无'}", file=sys.stderr)
        if missing:
            print(f"   ❌ 缺失: {missing}", file=sys.stderr)
            print(f"   运行下载补全: python3 scripts/download_report.py --auto --stock-code {args.stock_code} --report-type {args.report_type} --all-years --save-dir {args.save_dir}",
                  file=sys.stderr)
            sys.exit(EXIT_NETWORK_FAILURE)
        else:
            print(f"   ✅ 完整", file=sys.stderr)
            sys.exit(EXIT_SUCCESS)

    # --market US: SEC EDGAR download (NEW)
    if args.market == "US":
        print(f"Downloading via SEC EDGAR: {args.stock_code} {args.report_type} FY{args.year} ...",
              file=sys.stderr)
        try:
            user_agent = os.environ.get("SEC_USER_AGENT", "")
            if not user_agent:
                print(
                    "Error: SEC 要求有效的 User-Agent（含联系信息）。"
                    "请设置 SEC_USER_AGENT 环境变量。",
                    file=sys.stderr,
                )
                sys.exit(EXIT_BAD_ARGUMENTS)
            downloader = SecDownloader(user_agent=user_agent)
            result = downloader.search_report(
                args.stock_code, args.year, args.report_type,
                save_dir=args.save_dir,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(EXIT_BAD_ARGUMENTS)
        except RuntimeError as exc:
            print(f"Error: SEC API request failed: {exc}", file=sys.stderr)
            sys.exit(EXIT_NETWORK_FAILURE)

        if result is None:
            msg = (
                f"No matching {args.report_type} found on SEC EDGAR for "
                f"{args.stock_code} FY{args.year}"
            )
            print(f"Error: {msg}", file=sys.stderr)
            print_result(
                success=False,
                url="", stock_code=args.stock_code,
                report_type=args.report_type, year=str(args.year),
                message=msg,
            )
            sys.exit(EXIT_NETWORK_FAILURE)

        print_result(
            success=True,
            filepath=result.get("filepath", ""),
            filesize=result.get("filesize", 0),
            url=result["url"],
            stock_code=args.stock_code,
            report_type=args.report_type,
            year=str(args.year),
            message=f"Downloaded {result.get('form_type', '')} from SEC EDGAR",
        )
        sys.exit(EXIT_SUCCESS)

    # --all-years mode: download all effective years from analysis_contract.json
    if args.all_years:
        contract_path = os.path.join(args.save_dir, "analysis_contract.json")
        if not os.path.exists(contract_path):
            print(f"Error: analysis_contract.json not found in {args.save_dir}. Run Phase 0 first.",
                  file=sys.stderr)
            sys.exit(EXIT_BAD_ARGUMENTS)
        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)
        years = contract.get("effective_years", [])
        if not years:
            print("Error: no effective_years in analysis_contract.json", file=sys.stderr)
            sys.exit(EXIT_BAD_ARGUMENTS)
        print(f"📅 批量下载 {len(years)} 年: {years}", file=sys.stderr)
        success_count = 0
        skip_urls_per_year: dict[int, set[str]] = {yr: set() for yr in years}
        for yr in years:
            print(f"\n--- FY{yr} ---", file=sys.stderr)
            skip_urls = skip_urls_per_year[yr]
            result_path = None

            if args.hk:
                result_path = download_hk(args.stock_code, yr, args.save_dir, skip_cninfo=False)
            elif args.auto:
                result = search_cninfo(args.stock_code, args.report_type, yr, args.company_name)
                if result:
                    fname = build_filename(args.stock_code, args.report_type, yr)
                    fpath = os.path.join(args.save_dir, fname)
                    success, msg, size = download_annual_report(result["url"], fpath, max_retries=args.max_retries)
                    result_path = fpath if success else None
                    if success:
                        record_document_source(
                            args.save_dir, fname, url=result["url"],
                            published_at=result.get("date"), title=result.get("title", ""), provider="cninfo",
                        )
                else:
                    # V12.19: HK stocks — fallback to hkexnews when cninfo fails
                    is_hk = (len(args.stock_code) == 5 and args.stock_code.isdigit() and args.stock_code.startswith('0'))
                    if is_hk and args.report_type in ("年报", "annual"):
                        print(f"  🔄 cninfo无结果，回退到hkexnews...", file=sys.stderr)
                        result_path = download_hk(args.stock_code, yr, args.save_dir, skip_cninfo=True)
                    else:
                        result_path = None
            else:
                result_path = None

            # Post-download validation: verify it's an actual annual report
            if result_path:
                valid, reason = _is_valid_annual_report(result_path)
                if valid:
                    success_count += 1
                    print(f"  ✅ FY{yr}: {os.path.basename(result_path)} ({os.path.getsize(result_path)//1024}KB)", file=sys.stderr)
                    ocr_pdf_if_needed(result_path)
                else:
                    print(f"  ⚠️ FY{yr}: 下载文件验证失败 ({reason})，尝试重新下载...", file=sys.stderr)
                    skip_urls.add(result_path)  # won't re-use this match
                    if os.path.exists(result_path):
                        bad_path = result_path + ".bad"
                        os.rename(result_path, bad_path)
                        print(f"  已标记为无效: {os.path.basename(bad_path)}", file=sys.stderr)

                    # Retry with next cninfo match
                    is_hk = bool(args.hk)
                    retry_path = _retry_download_with_next_match(
                        args.stock_code, yr, args.save_dir, skip_urls,
                        report_type=args.report_type, company_name=args.company_name,
                        is_hk=is_hk,
                    )
                    if retry_path:
                        valid2, _ = _is_valid_annual_report(retry_path)
                        if valid2:
                            success_count += 1
                            print(f"  ✅ FY{yr} (重试): {os.path.basename(retry_path)} ({os.path.getsize(retry_path)//1024}KB)", file=sys.stderr)
                            ocr_pdf_if_needed(retry_path)
                        else:
                            print(f"  ❌ FY{yr}: 重试后仍无效", file=sys.stderr)
                    else:
                        print(f"  ❌ FY{yr}: 所有来源已耗尽，下载失败", file=sys.stderr)
            else:
                print(f"  ❌ FY{yr}: 下载失败", file=sys.stderr)

        print(f"\n📊 批量下载完成: {success_count}/{len(years)} 成功", file=sys.stderr)
        if success_count < 3:
            print(f"⚠️ 仅 {success_count} 年可用，Zone B 定性提取将受限", file=sys.stderr)
        sys.exit(0 if success_count >= 3 else EXIT_NETWORK_FAILURE)

    # --hk mode: download HK stock annual report with multi-strategy fallback
    # Strategies (in order): cre8ir → hkexnews API → cninfo (A+H dual-listed) → legacy hkexnews scan
    if args.hk:
        result_path = download_hk(args.stock_code, args.year, args.save_dir, skip_cninfo=False)
        if not result_path:
            strategies_tried = "cre8ir → hkexnews API → cninfo → hkexnews legacy scan"
            print(f"Error: All strategies exhausted ({strategies_tried}). "
                  f"Could not find {args.year} annual report for {args.stock_code}.",
                  file=sys.stderr)
            sys.exit(EXIT_NETWORK_FAILURE)
        print_result(success=True, url="hk auto multi-strategy", stock_code=args.stock_code,
                     report_type=args.report_type, year=str(args.year),
                     message=f"Downloaded to {result_path}")
        # V8.4: Auto-OCR/Vision for image PDFs
        ocr_pdf_if_needed(result_path)
        return

    # --auto mode: search cninfo API first
    if args.auto:
        result = search_cninfo(
            stock_code=args.stock_code,
            report_type=args.report_type,
            year=args.year,
            company_name=args.company_name,
        )
        if result is None:
            # v2.32: HK stocks — fallback to hkexnews when cninfo fails
            is_hk = (len(args.stock_code) == 5 and args.stock_code.isdigit() and args.stock_code.startswith('0'))
            if is_hk and args.report_type in ("年报", "annual"):
                print(f"cninfo: no match, trying hkexnews...", file=sys.stderr)
                result_path = download_hk(args.stock_code, args.year, args.save_dir, skip_cninfo=True)
                if result_path:
                    print_result(success=True, url="hkexnews.hk auto", stock_code=args.stock_code,
                                 report_type=args.report_type, year=str(args.year),
                                 message=f"Downloaded from hkexnews to {result_path}")
                    # V8.4: Auto-OCR/Vision for HK image PDFs
                    ocr_pdf_if_needed(result_path)
                    return
            msg = (
                f"No matching {args.report_type} found on cninfo for "
                f"{args.stock_code} FY{args.year}"
            )
            print(f"Error: {msg}", file=sys.stderr)
            print_result(
                success=False,
                url="",
                stock_code=args.stock_code,
                report_type=args.report_type,
                year=str(args.year),
                message=msg,
            )
            sys.exit(EXIT_NETWORK_FAILURE)

        pdf_url = result["url"]
        title = result["title"]
        print(f"Found: {title} ({result['date']})", file=sys.stderr)
    else:
        pdf_url = args.url

    # Validate URL
    valid, err_msg = validate_url(pdf_url)
    if not valid:
        print(f"Error: {err_msg}", file=sys.stderr)
        print_result(
            success=False,
            url=pdf_url,
            stock_code=args.stock_code,
            report_type=args.report_type,
            year=str(args.year),
            message=err_msg,
        )
        sys.exit(EXIT_BAD_ARGUMENTS)

    # Ensure save directory exists
    os.makedirs(args.save_dir, exist_ok=True)

    # Build filename and full path
    filename = build_filename(args.stock_code, args.report_type, args.year)
    save_path = os.path.join(args.save_dir, filename)

    # Download
    success, message, filesize = download_annual_report(
        url=pdf_url,
        save_path=save_path,
        max_retries=args.max_retries,
    )

    # Print result
    print_result(
        success=success,
        filepath=os.path.abspath(save_path) if success else "",
        filesize=filesize,
        url=pdf_url,
        stock_code=args.stock_code,
        report_type=args.report_type,
        year=str(args.year),
        message=message,
    )

    if not success:
        if "validation" in message.lower():
            sys.exit(EXIT_PDF_VALIDATION_FAILURE)
        else:
            sys.exit(EXIT_NETWORK_FAILURE)

    record_document_source(
        args.save_dir,
        filename,
        url=pdf_url,
        published_at=result.get("date") if args.auto and isinstance(result, dict) else None,
        title=result.get("title", "") if args.auto and isinstance(result, dict) else "",
        provider="cninfo" if args.auto else "explicit_url",
    )

    # V8.3: Auto-OCR image PDFs after successful download
    ocr_pdf_if_needed(save_path)

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
