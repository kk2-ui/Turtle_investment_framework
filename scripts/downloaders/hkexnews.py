"""披露易 HKEX 财报下载器。

使用 ``titleSearchServlet.do`` API 代替日期 URL 穷举扫描，
支持 FY/H1/Q1-Q4 全部财期，通过标题文本区分季度类型。

设计原则：
- 仅依赖 ``requests``，同步风格。
- 返回纯 dict（兼容 Turtle 格式）。
- 不写 workspace、不调 docling、不生成 document_id。
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
import re
import time
from typing import Any

import requests

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

HKEXNEWS_BASE_URL: str = "https://www1.hkexnews.hk"
HKEXNEWS_ACTIVE_STOCK_ZH_URL: str = (
    f"{HKEXNEWS_BASE_URL}/ncms/script/eds/activestock_sehk_c.json"
)
HKEXNEWS_INACTIVE_STOCK_ZH_URL: str = (
    f"{HKEXNEWS_BASE_URL}/ncms/script/eds/inactivestock_sehk_c.json"
)
HKEXNEWS_TITLE_SEARCH_URL: str = (
    f"{HKEXNEWS_BASE_URL}/search/titleSearchServlet.do"
)

DEFAULT_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEFAULT_REQUEST_TIMEOUT: float = 30.0
DEFAULT_SLEEP_SECONDS: float = 0.3
DEFAULT_MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 0.8

PDF_MAGIC_BYTES: bytes = b"%PDF-"
PDF_MIN_BYTES: int = 1024

# ---------------------------------------------------------------------------
# 披露易分类映射
# ---------------------------------------------------------------------------

class _HkCategorySpec:
    """披露易 t1code/t2code 分类规格。"""

    __slots__ = ("t1code", "t2_group_code", "t2code")

    def __init__(self, t1code: str, t2_group_code: str, t2code: str) -> None:
        self.t1code = t1code
        self.t2_group_code = t2_group_code
        self.t2code = t2code

    def __hash__(self) -> int:
        return hash((self.t1code, self.t2_group_code, self.t2code))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _HkCategorySpec):
            return NotImplemented
        return (
            self.t1code == other.t1code
            and self.t2_group_code == other.t2_group_code
            and self.t2code == other.t2code
        )


# 财期 → 披露易分类规格
_PERIOD_TO_CATEGORY_SPEC: dict[str, _HkCategorySpec] = {
    "FY": _HkCategorySpec(t1code="40000", t2_group_code="-2", t2code="40100"),
    "H1": _HkCategorySpec(t1code="40000", t2_group_code="-2", t2code="40200"),
    "Q1": _HkCategorySpec(t1code="10000", t2_group_code="3", t2code="13600"),
    "Q2": _HkCategorySpec(t1code="10000", t2_group_code="3", t2code="13600"),
    "Q3": _HkCategorySpec(t1code="10000", t2_group_code="3", t2code="13600"),
    "Q4": _HkCategorySpec(t1code="10000", t2_group_code="3", t2code="13600"),
}

_HKEXNEWS_CATEGORY_ZERO: str = "0"
_HKEXNEWS_CATEGORY_MARKET: str = "SEHK"
_HKEXNEWS_SEARCH_TYPE_BY_STOCK: str = "1"
_HKEXNEWS_DOCUMENT_TYPE_ALL: str = "-1"
_HKEXNEWS_ROW_RANGE: str = "100"
_HKEXNEWS_SORT_BY_DATETIME: str = "0"
_HKEXNEWS_SORT_DIR_DESC: str = "1"
_HKEXNEWS_FILE_TYPE_PDF: str = "PDF"

# ---------------------------------------------------------------------------
# 财期推断关键词
# ---------------------------------------------------------------------------

_PERIOD_INFERENCE_TOKENS: dict[str, tuple[str, ...]] = {
    "FY": (
        "ANNUAL REPORT", "年報", "年报", "年度報告", "年度报告",
        "ANNUAL RESULTS", "全年業績", "全年业绩",
    ),
    "H1": (
        "INTERIM REPORT", "HALF-YEAR", "中期報告", "中期报告",
        "半年報", "半年报", "INTERIM RESULTS",
    ),
    "Q1": (
        "FIRST QUARTER", "FIRST QUARTERLY", "第一季度", "一季",
        "三個月", "三个月", "1ST QUARTER", "Q1",
    ),
    "Q2": (
        "SECOND QUARTER", "SECOND QUARTERLY", "第二季度",
        "六個月", "六个月", "半年", "2ND QUARTER", "Q2",
    ),
    "Q3": (
        "THIRD QUARTER", "THIRD QUARTERLY", "第三季度", "三季",
        "九個月", "九个月", "3RD QUARTER", "Q3",
    ),
    "Q4": (
        "FOURTH QUARTER", "FOURTH QUARTERLY", "第四季度",
        "十二個月", "十二个月", "全年", "4TH QUARTER", "Q4",
    ),
}

# 英文财报标题关键词（用于排除）
_ENGLISH_REPORT_TITLE_TOKENS: tuple[str, ...] = (
    "ANNUAL REPORT",
    "INTERIM REPORT",
    "ANNUAL RESULTS",
    "INTERIM RESULTS",
    "FINANCIAL STATEMENTS",
    "QUARTERLY REPORT",
    "QUARTERLY RESULTS",
    "FIRST QUARTER",
    "THIRD QUARTER",
)

# 修订版本检测关键词
_TITLE_AMENDED_TOKENS_HK: tuple[str, ...] = (
    "更正", "修訂", "修订", "補充", "补充",
    "REVISED", "SUPPLEMENTAL", "AMENDED",
)

# 披露易日期正则
_TITLE_YEAR_PATTERN: re.Pattern[str] = re.compile(r"(20\d{2}|19\d{2})")
_TITLE_CHINESE_YEAR_PATTERN: re.Pattern[str] = re.compile(
    r"(二零|二〇)?([一二三四五六七八九零〇]{2})年"
)
_BR_PATTERN: re.Pattern[str] = re.compile(r"<br\s*/?>", re.IGNORECASE)

# 中文数字映射
_CHINESE_DIGIT_MAP: dict[str, int] = {
    "零": 0, "〇": 0,
    "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


# ---------------------------------------------------------------------------
# 纯函数工具（来自 Dayu hkexnews_downloader.py 中无 I/O 依赖的部分）
# ---------------------------------------------------------------------------

def _to_hkex_stock_code(raw: str) -> str:
    """规范化港股代码为 5 位零补齐格式。

    ``0700``, ``00700``, ``700`` → ``00700``。

    Args:
        raw: 原始代码字符串。

    Returns:
        5 位零补齐代码。

    Raises:
        ValueError: 无法提取有效数字时抛出。
    """
    digits = re.sub(r"\D", "", raw.strip())
    if raw.strip().upper().endswith(".HK") and len(digits) > 5:
        digits = digits[:-2]
    if not digits:
        raise ValueError(f"无法从 {raw!r} 提取有效港股代码")
    if len(digits) <= 4:
        return digits.zfill(5)
    if len(digits) == 5:
        return digits
    raise ValueError(f"港股代码过长: {digits}")


def _first_text(obj: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """尝试从多个可能的 key 中读取第一个非空字符串值。

    Args:
        obj: JSON 对象。
        keys: 候选 key 元组。

    Returns:
        第一个非空字符串值，全空返回 ``None``。
    """
    for key in keys:
        val = obj.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _contains_cjk(text: str) -> bool:
    """检测文本是否包含 CJK 字符。

    Args:
        text: 待检测文本。

    Returns:
        包含 CJK 字符返回 ``True``。
    """
    for ch in text:
        cp = ord(ch)
        if (
            (0x4E00 <= cp <= 0x9FFF)      # CJK Unified
            or (0x3400 <= cp <= 0x4DBF)    # CJK Extension A
            or (0x2E80 <= cp <= 0x2FDF)    # Kangxi Radicals
            or (0xF900 <= cp <= 0xFAFF)    # CJK Compat
        ):
            return True
    return False


def _looks_like_english_report_text(text: str) -> bool:
    """检测文本是否看起来像英文财报标题。

    Args:
        text: 待检测文本。

    Returns:
        命中英文财报关键词返回 ``True``。
    """
    upper = text.upper()
    return any(token in upper for token in _ENGLISH_REPORT_TITLE_TOKENS)


def _is_english_announcement(
    title: str,
    language: str | None = None,
    category_text: str = "",
) -> bool:
    """判断公告是否应被当作英文财报排除。

    规则：
    1. lang 字段为 ``en`` → 排除。
    2. 标题包含英文财报关键词且不含 CJK → 排除。
    3. 分类文本包含英文财报关键词且标题无 CJK → 排除。

    Args:
        title: 公告标题。
        language: 语言字段（``zh``/``en``）。
        category_text: 披露易分类描述文本。

    Returns:
        应排除则返回 ``True``。
    """
    if language and language.lower() == "en":
        return True
    if _looks_like_english_report_text(title):
        if not _contains_cjk(title):
            return True
    if (
        not _contains_cjk(title)
        and category_text
        and _looks_like_english_report_text(category_text)
    ):
        return True
    return False


def _is_amended_title(title: str) -> bool:
    """检测标题是否为修订版本。

    Args:
        title: 公告标题。

    Returns:
        修订版本返回 ``True``。
    """
    return any(token.upper() in title.upper() for token in _TITLE_AMENDED_TOKENS_HK)


def _infer_fiscal_year_from_text(
    title: str, filing_date: str = ""
) -> int | None:
    """从标题或申报日期推断财年。

    优先匹配标题中的 4 位年份（20xx/19xx），
    回退到中文数字年份，最后回退到申报日期年份。

    Args:
        title: 公告标题。
        filing_date: 申报日期（``YYYY-MM-DD``）。

    Returns:
        财年整数，无法推断返回 ``None``。
    """
    matched = _TITLE_YEAR_PATTERN.search(title)
    if matched:
        return int(matched.group(1))
    cn_matched = _TITLE_CHINESE_YEAR_PATTERN.search(title)
    if cn_matched:
        return _parse_chinese_digit_year_hk(cn_matched.group(0))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", filing_date):
        return int(filing_date[:4])
    return None


def _parse_chinese_digit_year_hk(text: str) -> int | None:
    """将中文年份转为阿拉伯数字。

    如 ``二零二四`` → ``2024``。

    Args:
        text: 中文年份文本。

    Returns:
        年份整数，失败返回 ``None``。
    """
    digits: list[int] = []
    for ch in text:
        if ch in _CHINESE_DIGIT_MAP:
            digits.append(_CHINESE_DIGIT_MAP[ch])
    if not digits:
        return None
    num = sum(d * (10 ** (len(digits) - 1 - i)) for i, d in enumerate(digits))
    if num < 100:
        num += 2000
    if 2000 <= num <= 2099:
        return num
    return None


def _infer_fiscal_period_from_text(
    *, title: str, category_text: str = ""
) -> str | None:
    """从标题和分类文本推断财期。

    先用类别文本判断是财务报表还是季度公告，
    再用 ``_PERIOD_INFERENCE_TOKENS`` 匹配具体财期。

    Args:
        title: 公告标题。
        category_text: 披露易分类描述。

    Returns:
        财期代码（FY/H1/Q1/Q2/Q3/Q4），无法判断返回 ``None``。
    """
    combined = f"{title} {category_text}".upper()
    normalized_category = category_text.upper()

    # 季度公告类
    if "季度" in category_text or "QUARTER" in normalized_category:
        order = ("Q4", "Q3", "Q2", "Q1", "H1", "FY")
    else:
        # 财务报表类（年报/半年报）
        order = ("H1", "FY", "Q4", "Q3", "Q2", "Q1")

    for period in order:
        tokens = _PERIOD_INFERENCE_TOKENS.get(period, ())
        if any(token.upper() in combined for token in tokens):
            return period
    return None


def _pick_best_announcement_hk(
    items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """从同财期候选集中选出最佳公告。

    排序规则：
    1. 非修订版优先（``is_amended=False`` 排前面）。
    2. 申报日期最近优先。

    Args:
        items: 候选公告列表。

    Returns:
        最佳候选，空列表返回 ``None``。
    """
    if not items:
        return None

    def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
        amended = _is_amended_title(item.get("title", ""))
        return (1 if amended else 0, item.get("filing_date", ""))

    return min(items, key=_sort_key)


def _split_stock_code_tokens(stock_code_field: str) -> set[str]:
    """拆分披露易 ``STOCK_CODE`` 字段中的多代码。

    ``STOCK_CODE`` 可能以 ``<br/>`` 分隔多个代码。

    Args:
        stock_code_field: 原始 ``STOCK_CODE`` 字符串。

    Returns:
        5 位零补齐代码集合。
    """
    text = _BR_PATTERN.sub(",", stock_code_field)
    tokens: set[str] = set()
    for raw in re.split(r"[,;，\s]+", text):
        digits = re.sub(r"\D", "", raw)
        if not digits:
            continue
        if len(digits) <= 4:
            tokens.add(digits.zfill(5))
        elif len(digits) == 5:
            tokens.add(digits)
    return tokens


def _strip_html_tags(text: str) -> str:
    """移除 HTML 标签。

    Args:
        text: 带 HTML 标签的文本。

    Returns:
        纯文本。
    """
    return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# HkexnewsDownloader
# ---------------------------------------------------------------------------

class HkexnewsDownloader:
    """披露易 HKEX 财报搜索与下载客户端。

    使用 ``titleSearchServlet.do`` API 按分类搜索财报，
    支持 FY/H1/Q1-Q4 财期，通过标题文本区分季度公告。

    Args:
        session: 可选 requests.Session。
        request_timeout: HTTP 请求超时秒数。
        max_retries: 最大重试次数。
        sleep_seconds: 请求间隔秒数。
        pdf_dir: PDF 下载目录（下载功能使用）。
    """

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        pdf_dir: str = ".",
    ) -> None:
        self._session: requests.Session = session or requests.Session()
        self._request_timeout: float = request_timeout
        self._max_retries: int = max_retries
        self._sleep_seconds: float = sleep_seconds
        self._last_request_at: float = 0.0
        self.pdf_dir: str = pdf_dir
        # 缓存 stock list 映射
        self._stock_mapping_cache: dict[str, dict[str, str]] | None = None

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """请求间隔限速。"""
        now = time.monotonic()
        if self._sleep_seconds > 0 and self._last_request_at > 0:
            elapsed = now - self._last_request_at
            remaining = self._sleep_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def _http_get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """GET JSON，带重试。"""
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._throttle()
                resp = self._session.get(
                    url,
                    timeout=self._request_timeout,
                    headers={"User-Agent": DEFAULT_USER_AGENT},
                    **kwargs,
                )
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                # 披露易有些端点返回 text/html 包裹的 JSON
                text = resp.text.strip()
                data: dict[str, Any] = json.loads(text)
                return data
            except Exception as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                if attempt < self._max_retries:
                    time.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
        raise RuntimeError(f"HTTP GET {url} 失败: {last_error}")

    def _http_get_bytes(self, url: str, **kwargs: Any) -> bytes:
        """GET 字节内容，带重试。"""
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._throttle()
                resp = self._session.get(
                    url,
                    timeout=self._request_timeout,
                    headers={"User-Agent": DEFAULT_USER_AGENT,
                             "Referer": "https://www.hkexnews.hk/"},
                    **kwargs,
                )
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                return resp.content
            except Exception as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                if attempt < self._max_retries:
                    time.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
        raise RuntimeError(f"HTTP GET {url} 失败: {last_error}")

    # ------------------------------------------------------------------
    # Stock mapping
    # ------------------------------------------------------------------

    def _fetch_stock_mapping(self) -> dict[str, dict[str, str]]:
        """从披露易拉取 active + inactive 股票列表并缓存。

        Returns:
            ``{stock_code: {stock_id, stock_name}}``。

        Raises:
            RuntimeError: 列表拉取失败时抛出。
        """
        if self._stock_mapping_cache is not None:
            return self._stock_mapping_cache

        mapping: dict[str, dict[str, str]] = {}
        for list_url in (HKEXNEWS_ACTIVE_STOCK_ZH_URL, HKEXNEWS_INACTIVE_STOCK_ZH_URL):
            try:
                payload = self._http_get_json(list_url)
            except RuntimeError:
                continue
            rows = _extract_json_rows(payload)
            for row in rows:
                entry = _parse_stock_mapping_entry(row)
                if entry is not None:
                    mapping.setdefault(
                        entry["stock_code"],
                        {
                            "stock_id": entry["stock_id"],
                            "stock_name": entry.get("stock_name", ""),
                        },
                    )
        self._stock_mapping_cache = mapping
        return mapping

    # ------------------------------------------------------------------
    # resolve_company
    # ------------------------------------------------------------------

    def resolve_company(self, ticker: str) -> dict[str, str]:
        """解析港股代码 → stockId + 公司名称。

        Args:
            ticker: 港股代码（``00700``, ``700``, ``0700.HK``）。

        Returns:
            ``{"stock_id": str, "stock_code": str, "stock_name": str}``。

        Raises:
            ValueError: 代码不在披露易列表中时抛出。
            RuntimeError: 列表拉取失败时抛出。
        """
        normalized = _to_hkex_stock_code(ticker)
        mapping = self._fetch_stock_mapping()
        if normalized in mapping:
            entry = mapping[normalized]
            return {
                "stock_id": entry["stock_id"],
                "stock_code": normalized,
                "stock_name": entry.get("stock_name", ""),
            }
        raise ValueError(f"港股代码 {normalized} 不在披露易 stock list 中")

    # ------------------------------------------------------------------
    # titleSearchServlet.do 查询
    # ------------------------------------------------------------------

    def _search_title(
        self,
        stock_id: str,
        category_spec: _HkCategorySpec,
        start_date: str,
        end_date: str,
        language: str = "zh",
    ) -> list[dict[str, Any]]:
        """调用 ``titleSearchServlet.do`` 搜索公告。

        Args:
            stock_id: 披露易内部 stockId。
            category_spec: 分类规格。
            start_date: 起始日期（``YYYYMMDD``）。
            end_date: 截止日期（``YYYYMMDD``）。
            language: 语言（``zh`` / ``en``）。

        Returns:
            解析后的公告列表。

        Raises:
            RuntimeError: API 不可达时抛出。
        """
        lang_param = "0" if language == "zh" else "1"
        payload = self._http_get_json(
            HKEXNEWS_TITLE_SEARCH_URL,
            params={
                "lang": lang_param,
                "category": _HKEXNEWS_CATEGORY_ZERO,
                "market": _HKEXNEWS_CATEGORY_MARKET,
                "stockId": stock_id,
                "searchType": _HKEXNEWS_SEARCH_TYPE_BY_STOCK,
                "documentType": _HKEXNEWS_DOCUMENT_TYPE_ALL,
                "t1code": category_spec.t1code,
                "t2Gcode": category_spec.t2_group_code,
                "t2code": category_spec.t2code,
                "fromDate": start_date,
                "toDate": end_date,
                "rowRange": _HKEXNEWS_ROW_RANGE,
                "sortByOptions": _HKEXNEWS_SORT_BY_DATETIME,
                "sortDir": _HKEXNEWS_SORT_DIR_DESC,
            },
        )
        rows = _extract_json_rows(payload)
        announcements: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for row in rows:
            ann = _parse_announcement(row)
            if ann is None:
                continue
            # 过滤英文财报
            if _is_english_announcement(
                title=ann["title"],
                language=ann.get("language"),
                category_text=ann.get("category_text", ""),
            ):
                continue
            if ann["file_url"] in seen_urls:
                continue
            seen_urls.add(ann["file_url"])
            announcements.append(ann)
        return announcements

    # ------------------------------------------------------------------
    # search_report — 主搜索入口
    # ------------------------------------------------------------------

    def search_report(
        self,
        ticker: str,
        year: int,
        report_type: str = "年报",
        *,
        stock_id: str | None = None,
    ) -> dict[str, Any] | None:
        """搜索最佳匹配的港股财报 PDF。

        按分类规格调用 ``titleSearchServlet.do``，
        通过标题文本推断财期，经修订版优先排序后返回最佳候选。

        Args:
            ticker: 港股代码。
            year: 财年。
            report_type: 财报类型。
            stock_id: 可选 stockId（已解析时复用）。

        Returns:
            ``{"url": str, "title": str, "date": str}`` 或 ``None``。

        Raises:
            RuntimeError: API 不可达时抛出。
            ValueError: ticker 解析失败时抛出。
        """
        # 1) 财期映射
        period = _report_type_to_hk_period(report_type)
        if period is None:
            return None
        category_spec = _PERIOD_TO_CATEGORY_SPEC.get(period)
        if category_spec is None:
            return None

        # 2) 解析公司
        if stock_id:
            stock_id_val = stock_id
        else:
            company = self.resolve_company(ticker)
            stock_id_val = company["stock_id"]

        # 3) 日期窗口
        start_date = f"{year - 1}0101"
        end_date = f"{year + 1}1231"

        # 4) 查询
        raw_announcements = self._search_title(
            stock_id=stock_id_val,
            category_spec=category_spec,
            start_date=start_date,
            end_date=end_date,
            language="zh",
        )

        # 5) 财年/财期过滤 + 分组
        grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for ann in raw_announcements:
            # 财年过滤
            fy = _infer_fiscal_year_from_text(
                ann["title"], ann.get("filing_date", "")
            )
            if fy is not None and fy != year:
                continue
            # 财期推断
            inf_period = _infer_fiscal_period_from_text(
                title=ann["title"],
                category_text=ann.get("category_text", ""),
            )
            if inf_period is None:
                inf_period = period  # 回退到目标财期
            if inf_period != period:
                continue

            key = (inf_period, fy or year)
            grouped.setdefault(key, []).append(ann)

        # 6) 每分组选最佳
        best_group: dict[str, Any] | None = None
        for key, items in grouped.items():
            best = _pick_best_announcement_hk(items)
            if best is None:
                continue
            best["fiscal_period"] = key[0]
            best["fiscal_year"] = key[1]
            if best_group is None or best["filing_date"] > best_group["filing_date"]:
                best_group = best

        if best_group is None:
            return None

        return {
            "url": best_group["file_url"],
            "title": best_group["title"],
            "date": best_group["filing_date"],
        }

    # ------------------------------------------------------------------
    # download_pdf
    # ------------------------------------------------------------------

    def download_pdf(
        self, url: str, save_path: str, max_retries: int = DEFAULT_MAX_RETRIES
    ) -> tuple[bool, str, int]:
        """下载并校验 PDF 文件。

        Args:
            url: PDF 文件 URL。
            save_path: 本地保存路径。
            max_retries: 最大重试次数。

        Returns:
            ``(success, message, filesize)``。
        """
        last_error: str = ""
        for attempt in range(1, max_retries + 1):
            try:
                content = self._http_get_bytes(url)
                if not content:
                    last_error = "下载内容为空"
                    if attempt < max_retries:
                        time.sleep(RETRY_BACKOFF_BASE * attempt)
                    continue

                if not content[:5].startswith(PDF_MAGIC_BYTES):
                    last_error = "文件不以 %PDF- 开头，不是有效的 PDF"
                    if attempt < max_retries:
                        time.sleep(RETRY_BACKOFF_BASE * attempt)
                    continue

                if len(content) < PDF_MIN_BYTES:
                    last_error = f"PDF 文件过小 ({len(content)} bytes)"
                    if attempt < max_retries:
                        time.sleep(RETRY_BACKOFF_BASE * attempt)
                    continue

                os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(content)
                return True, "下载成功", len(content)

            except RuntimeError as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    time.sleep(RETRY_BACKOFF_BASE * attempt)

        return False, f"下载失败（重试{max_retries}次）: {last_error}", 0


# ---------------------------------------------------------------------------
# 披露易 JSON 解析辅助函数
# ---------------------------------------------------------------------------

def _extract_json_rows(payload: Any) -> list[dict[str, Any]]:
    """从披露易 JSON 响应中提取行数据。

    披露易的 JSON 结构可能将数据包装在多层嵌套中，
    也可能是直接返回的数组。``result`` 字段有时是
    JSON 字符串而非数组，需额外解析。

    Args:
        payload: 原始 JSON 响应（可能是 dict 或 list）。

    Returns:
        行数据列表。
    """
    # 直接是列表的情况（如 activestock_sehk_c.json）
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("result", "records", "data", "rows", "list", "stockInfo"):
            val = payload.get(key)
            if isinstance(val, list):
                return val
            # result 可能是 JSON 字符串 "[]"
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass
    return []


def _parse_stock_mapping_entry(raw: dict[str, Any]) -> dict[str, str] | None:
    """解析披露易 stock list 中的单条记录。

    披露易 active/inactive stock JSON 使用简写字段名：
    ``c`` = stock code, ``n`` = stock name, ``s`` = stockId。

    Args:
        raw: 单条原始记录。

    Returns:
        ``{"stock_code": str, "stock_id": str, "stock_name": str}``
        或 ``None``（字段缺失时）。
    """
    # 披露易简写字段名
    stock_code = _first_text(raw, ("c", "stockCode", "STOCK_CODE", "code"))
    stock_id = _first_text(raw, ("s", "stockId", "STOCK_ID", "id", "i"))
    stock_name = _first_text(raw, ("n", "stockName", "STOCK_NAME", "name", "shortName"))
    if stock_code and stock_id:
        return {
            "stock_code": _to_hkex_stock_code(stock_code),
            "stock_id": stock_id,
            "stock_name": stock_name or "",
        }
    return None


def _parse_announcement(raw: dict[str, Any]) -> dict[str, Any] | None:
    """解析披露易公告搜索结果中的单条记录。

    仅保留 PDF 文档，剔除非 PDF 条目。

    Args:
        raw: 单条原始搜索结果。

    Returns:
        标准化公告 dict，不满足条件返回 ``None``。
    """
    file_type = _first_text(raw, ("FILE_TYPE", "fileType", "file_type"))
    if file_type is not None and file_type.upper() != _HKEXNEWS_FILE_TYPE_PDF:
        return None

    title = _strip_html_tags(
        _first_text(raw, ("TITLE", "title", "TITLE_TC", "TITLE_SC")) or ""
    )
    if not title:
        return None

    file_link = _first_text(raw, ("FILE_LINK", "fileLink", "FILE_LINK_TC")) or ""
    if not file_link:
        return None

    filing_date = _first_text(raw, ("DATE_TIME", "dateTime", "FILING_DATE")) or ""
    file_size = _first_text(raw, ("FILE_SIZE", "fileSize"))
    language = _first_text(raw, ("LANGUAGE", "language"))
    category_text = _strip_html_tags(
        _first_text(raw, ("CATEGORY", "category", "CATEGORY_NAME")) or ""
    )

    # 构建绝对 URL
    if file_link.startswith("http"):
        file_url = file_link
    else:
        file_url = HKEXNEWS_BASE_URL + file_link if file_link.startswith("/") else file_link

    return {
        "title": title,
        "file_url": file_url,
        "filing_date": _normalize_hk_date(filing_date),
        "file_size": file_size,
        "language": language,
        "category_text": category_text,
    }


def _normalize_hk_date(raw: str) -> str:
    """规范化披露易日期为 ``YYYY-MM-DD``。

    支持 ``2024/03/15``, ``2024-03-15``, ``20240315`` 格式。

    Args:
        raw: 原始日期字符串。

    Returns:
        ``YYYY-MM-DD`` 格式的日期。
    """
    raw = raw.strip()
    # YYYY/MM/DD
    m = re.match(r"(\d{4})/(\d{2})/(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    # YYYYMMDD
    m = re.match(r"(\d{4})(\d{2})(\d{2})", raw)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return raw


# ---------------------------------------------------------------------------
# 财期映射
# ---------------------------------------------------------------------------

_RT_TO_HK_PERIOD: dict[str, str] = {
    "年报": "FY",
    "annual": "FY",
    "中报": "H1",
    "interim": "H1",
    "半年报": "H1",
    "一季报": "Q1",
    "q1": "Q1",
    "三季报": "Q3",
    "q3": "Q3",
}


def _report_type_to_hk_period(report_type: str) -> str | None:
    """将 Turtle 财报类型映射为财期。

    Args:
        report_type: 财报类型字符串。

    Returns:
        财期代码，未知返回 ``None``。
    """
    return _RT_TO_HK_PERIOD.get(report_type.lower())
