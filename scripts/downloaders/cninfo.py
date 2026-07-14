"""巨潮 CNINFO 财报下载器。

使用巨潮分类查询 API（``hisAnnouncement/query``）代替全文搜索，
支持修订版本优先、财年正则推断、增强黑名单过滤。

设计原则：
- 仅依赖 ``requests``，同步风格，不引入 async/httpx。
- 返回纯 dict（兼容 Turtle 现有 ``{url, title, date, file_id}`` 格式）。
- 不写 workspace、不调 docling、不生成 document_id。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

CNINFO_BASE_URL: str = "http://www.cninfo.com.cn"
CNINFO_STOCK_JSON_URL: str = f"{CNINFO_BASE_URL}/new/data/szse_stock.json"
CNINFO_QUERY_URL: str = f"{CNINFO_BASE_URL}/new/hisAnnouncement/query"
CNINFO_FULLTEXT_URL: str = f"{CNINFO_BASE_URL}/new/fulltextSearch/full"
CNINFO_PDF_BASE: str = "http://static.cninfo.com.cn/"

DEFAULT_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEFAULT_REQUEST_TIMEOUT: float = 30.0
DEFAULT_SLEEP_SECONDS: float = 0.3
DEFAULT_MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 0.8
DEFAULT_PAGE_SIZE: int = 30
MAX_PAGES: int = 50

# ---------------------------------------------------------------------------
# CN 财期 -> 巨潮 category 映射
# ---------------------------------------------------------------------------

_PERIOD_TO_CATEGORY: dict[str, str] = {
    "FY": "category_ndbg_szsh;",   # 年报
    "H1": "category_bndbg_szsh;",  # 半年报
    "Q1": "category_yjdbg_szsh;",  # 一季报
    "Q3": "category_sjdbg_szsh;",  # 三季报
}
"""Q2/Q4 巨潮无独立分类，需在 workflow 层标记 skipped。"""

# ---------------------------------------------------------------------------
# Ticker 前缀 -> (column, plate) 映射
# ---------------------------------------------------------------------------

_TICKER_PREFIX_TO_MARKET: dict[str, tuple[str, str]] = {
    "000": ("szse", "sz"),
    "001": ("szse", "sz"),
    "002": ("szse", "sz"),
    "003": ("szse", "sz"),
    "300": ("szse", "sz"),
    "301": ("szse", "sz"),
    "600": ("sse", "sh"),
    "601": ("sse", "sh"),
    "603": ("sse", "sh"),
    "605": ("sse", "sh"),
    "688": ("sse", "sh"),
}

# ---------------------------------------------------------------------------
# 标题黑名单 — 比 Turtle 原始版本更精确
# ---------------------------------------------------------------------------

_TITLE_BLOCKLIST: tuple[str, ...] = (
    "摘要",
    "已取消",
    "已撤销",
    "撤回",
    "取消",
    "更正前",       # 排除旧版本（更正后优先）
    "募集说明书",
    "ESG",
    "可持续发展",
    "审计报告",
    "财务报表",     # 避免独立"财务报表"材料混入
    "意见",
    "（英文）",
    "(英文)",
    "英文)",
    "英文）",
    "英文版",
    "英文简版",
    "英文简本",
    "english",
    "港股公告",
    "h股公告",
    "h股",
    "社会责任",
    "内部控制",
)

# 财报正本标题关键词
_REPORT_TITLE_TOKENS: tuple[str, ...] = (
    "年度报告",
    "年报",
    "半年度报告",
    "半年报",
    "一季度报告",
    "第一季度报告",
    "三季度报告",
    "第三季度报告",
)

# 公告类标题关键词（"关于财报正本的公告"需要排除）
_REPORT_NOTICE_TITLE_TOKENS: tuple[str, ...] = (
    "公告",
    "提示性公告",
    "自愿性披露公告",
)

# 修订版本检测关键词 — 偏好修订版
_TITLE_AMENDED_TOKENS: tuple[str, ...] = (
    "更正",
    "更正后",
    "修订",
    "补充",
    "修正",
    "更新",
)

# ---------------------------------------------------------------------------
# 财年推断正则
# ---------------------------------------------------------------------------

_TITLE_FY_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s*年[年度]?\s*(年度报告|年报|半年度报告|半年报|一季度?报告|三季度?报告)"
)
_TITLE_FISCAL_YEAR_FALLBACK: re.Pattern[str] = re.compile(r"(\d{4})\s*年")

_CHINESE_DIGIT_MAP: dict[str, int] = {
    "零": 0, "〇": 0,
    "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 6, "六": 6, "七": 7, "八": 8, "九": 9,
}
_CHINESE_NUMERAL_PATTERN: re.Pattern[str] = re.compile(
    r"(二零|二〇)?([一二三四五六七八九零〇]{1,2})[年度]?"
)


# ---------------------------------------------------------------------------
# CninfoDownloader
# ---------------------------------------------------------------------------

class CninfoDownloader:
    """巨潮 CNINFO 财报搜索与下载客户端。

    使用分类 API（``hisAnnouncement/query``）替代全文搜索，
    提供修订版优先与财年正则推断能力。

    Args:
        session: 可选 requests.Session（用于连接复用）。
        request_timeout: HTTP 请求超时秒数。
        max_retries: 最大重试次数。
        sleep_seconds: 请求间隔秒数（速率限制）。
    """

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    ) -> None:
        self._session: requests.Session = session or requests.Session()
        self._request_timeout: float = request_timeout
        self._max_retries: int = max_retries
        self._sleep_seconds: float = sleep_seconds
        self._last_request_at: float = 0.0
        # 缓存 szse_stock.json 全量映射表
        self._stock_mapping_cache: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # 内部 HTTP helpers
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
        """GET JSON 请求，带重试。"""
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
                data: dict[str, Any] = resp.json()
                return data
            except Exception as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                if attempt < self._max_retries:
                    time.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
        raise RuntimeError(f"HTTP GET {url} 失败（重试{self._max_retries}次）: {last_error}")

    def _http_post_form(
        self, url: str, data: dict[str, str], **kwargs: Any
    ) -> dict[str, Any]:
        """POST 表单请求，带重试。"""
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._throttle()
                resp = self._session.post(
                    url,
                    data=data,
                    timeout=self._request_timeout,
                    headers={
                        "User-Agent": DEFAULT_USER_AGENT,
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "Referer": "https://www.cninfo.com.cn/",
                    },
                    **kwargs,
                )
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                result: dict[str, Any] = resp.json()
                return result
            except Exception as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                if attempt < self._max_retries:
                    time.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
        raise RuntimeError(f"HTTP POST {url} 失败（重试{self._max_retries}次）: {last_error}")

    # ------------------------------------------------------------------
    # 股票映射
    # ------------------------------------------------------------------

    def _fetch_stock_mapping(self) -> dict[str, dict[str, Any]]:
        """拉取并缓存 szse_stock.json 全量股票映射表。

        Returns:
            ``{code: {orgId, zwjc, ...}}`` 映射字典。

        Raises:
            RuntimeError: API 不可达时抛出。
        """
        if self._stock_mapping_cache is not None:
            return self._stock_mapping_cache
        payload = self._http_get_json(CNINFO_STOCK_JSON_URL)
        stock_list: list[dict[str, Any]] = payload.get("stockList", [])
        mapping: dict[str, dict[str, Any]] = {}
        for entry in stock_list:
            code = str(entry.get("code", "")).strip()
            if code:
                mapping[code] = entry
        self._stock_mapping_cache = mapping
        return mapping

    @staticmethod
    def _resolve_market_params(ticker: str) -> tuple[str, str]:
        """从 ticker 前缀推断 (column, plate)。

        Args:
            ticker: 6 位裸码（如 ``000651``, ``600887``）。

        Returns:
            ``(column, plate)``，例如 ``("szse", "sz")``。

        Raises:
            ValueError: ticker 前缀未知时抛出。
        """
        digits = re.sub(r"\D", "", ticker.strip())
        if len(digits) < 3:
            raise ValueError(f"无法识别 ticker 前缀: {ticker}")
        prefix = digits[:3]
        if prefix in _TICKER_PREFIX_TO_MARKET:
            return _TICKER_PREFIX_TO_MARKET[prefix]
        # 首位 0/3 → 深交所，6 → 上交所
        if prefix[0] in ("0", "3"):
            return ("szse", "sz")
        if prefix[0] == "6":
            return ("sse", "sh")
        raise ValueError(f"无法识别 ticker 前缀: {ticker}")

    # ------------------------------------------------------------------
    # resolve_company
    # ------------------------------------------------------------------

    def resolve_company(self, ticker: str) -> dict[str, Any]:
        """解析股票代码 -> orgId + 公司名称。

        从 ``szse_stock.json`` 查找，按前端前缀推断 column/plate。

        Args:
            ticker: 6 位裸码（如 ``000651``, ``600887``）。

        Returns:
            ``{"org_id": str, "company_name": str, "column": str, "plate": str}``。

        Raises:
            RuntimeError: API 不可达时抛出。
            ValueError: ticker 不在巨潮映射表中时抛出。
        """
        digits = re.sub(r"\D", "", ticker.strip())
        mapping = self._fetch_stock_mapping()
        if digits in mapping:
            entry = mapping[digits]
            org_id = str(entry.get("orgId", "")).strip()
            company_name = str(entry.get("zwjc", "")).strip()
            column, plate = self._resolve_market_params(digits)
            return {
                "org_id": org_id,
                "company_name": company_name,
                "column": column,
                "plate": plate,
            }
        # 尝试查找部分匹配（仅当长度匹配且后缀相同时，处理 SH/SZ 前缀场景）
        for code, entry in mapping.items():
            if len(code) == len(digits) and code.endswith(digits):
                org_id = str(entry.get("orgId", "")).strip()
                company_name = str(entry.get("zwjc", "")).strip()
                column, plate = self._resolve_market_params(code)
                return {
                    "org_id": org_id,
                    "company_name": company_name,
                    "column": column,
                    "plate": plate,
                }
        raise ValueError(f"ticker={ticker} 不在巨潮 szse_stock.json 映射表中")

    # ------------------------------------------------------------------
    # 公告查询与解析
    # ------------------------------------------------------------------

    def _query_announcements(
        self,
        ticker: str,
        org_id: str,
        column: str,
        plate: str,
        category: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """调用 ``hisAnnouncement/query`` 并自动翻页。

        Args:
            ticker: 6 位裸码。
            org_id: 巨潮 orgId。
            column: ``szse`` 或 ``sse``。
            plate: ``sz`` 或 ``sh``。
            category: 分类参数（如 ``category_ndbg_szsh;``）。
            start_date: 公告起始日期（YYYY-MM-DD）。
            end_date: 公告截止日期（YYYY-MM-DD）。

        Returns:
            原始公告 JSON 条目列表（全量翻页）。

        Raises:
            RuntimeError: API 不可达时抛出。
        """
        all_items: list[dict[str, Any]] = []
        for page_num in range(1, MAX_PAGES + 1):
            resp = self._http_post_form(
                CNINFO_QUERY_URL,
                data={
                    "pageNum": str(page_num),
                    "pageSize": str(DEFAULT_PAGE_SIZE),
                    "column": column,
                    "tabName": "fulltext",
                    "plate": plate,
                    "stock": f"{ticker},{org_id}",
                    "searchkey": "",
                    "category": category,
                    "seDate": f"{start_date}~{end_date}",
                    "sortName": "time",
                    "sortType": "desc",
                    "isHLtitle": "true",
                },
            )
            announcements = resp.get("announcements", [])
            if not announcements:
                break
            all_items.extend(announcements)
            has_more = resp.get("hasMore", False)
            if not has_more:
                break
        return all_items

    def _query_fulltext(
        self,
        ticker: str,
        year: int,
        report_type: str = "年报",
    ) -> list[dict[str, Any]]:
        """全文搜索回退（港股等非A股标的）。

        使用 ``fulltextSearch/full`` API，不依赖 orgId。

        Args:
            ticker: 股票代码。
            year: 财年。
            report_type: 财报类型。

        Returns:
            原始公告 JSON 条目列表。
        """
        # 构建搜索关键词
        keyword_map: dict[str, str] = {
            "年报": "年度报告", "annual": "年度报告",
            "中报": "半年度报告", "interim": "半年度报告",
            "半年报": "半年度报告",
            "一季报": "第一季度报告", "q1": "第一季度报告",
            "三季报": "第三季度报告", "q3": "第三季度报告",
        }
        keyword = keyword_map.get(report_type.lower(), report_type)
        searchkey = f"{ticker} {keyword}"

        try:
            resp = self._http_post_form(
                CNINFO_FULLTEXT_URL,
                data={
                    "searchkey": searchkey,
                    "sdate": "",
                    "edate": "",
                    "isfulltext": "false",
                    "sortName": "pubdate",
                    "sortType": "desc",
                    "pageNum": "1",
                    "pageSize": str(DEFAULT_PAGE_SIZE),
                },
            )
        except RuntimeError:
            return []
        return resp.get("announcements", []) or []

    @staticmethod
    def _parse_raw_announcement(raw: dict[str, Any]) -> dict[str, Any] | None:
        """将巨潮原始公告条目解析为标准化 dict。

        跳过非 PDF 类型（``adjunctType != "PDF"``）、
        无 ``adjunctUrl`` 或标题命中了黑名单的条目。

        Args:
            raw: 单条原始公告 JSON。

        Returns:
            解析后的 dict，不满足条件返回 ``None``。
        """
        adjunct_type = str(raw.get("adjunctType", "")).strip().upper()
        if adjunct_type != "PDF":
            return None
        url = str(raw.get("adjunctUrl", "")).strip()
        if not url:
            return None
        title = CninfoDownloader._clean_cninfo_text(
            str(raw.get("announcementTitle", ""))
        )
        if CninfoDownloader._is_title_blocked(title):
            return None
        sec_code = str(raw.get("secCode", "")).strip()
        announcement_id = str(raw.get("announcementId", "")).strip()
        # 解析日期
        ts = raw.get("announcementTime", 0)
        announcement_date = CninfoDownloader._format_announcement_date(ts)
        return {
            "url": url,
            "title": title,
            "announcement_date": announcement_date,
            "sec_code": sec_code,
            "announcement_id": announcement_id,
        }

    @staticmethod
    def _clean_cninfo_text(text: str) -> str:
        """清理巨潮标题中的 HTML 标签（``<em>`` 等）。

        Args:
            text: 原始标题字符串。

        Returns:
            清理后的纯文本标题。
        """
        return re.sub(r"<[^>]+>", "", text).strip()

    @staticmethod
    def _format_announcement_date(ts: Any) -> str:
        """将巨潮时间戳转为 ``YYYY-MM-DD``。

        支持毫秒时间戳（>10^10 时自动除 1000）和已格式化的日期字符串。

        Args:
            ts: 巨潮 announcementTime 字段（数字时间戳或日期字符串）。

        Returns:
            ``YYYY-MM-DD`` 格式的日期字符串。
        """
        if isinstance(ts, (int, float)) and ts > 0:
            if ts > 10_000_000_000:
                ts = ts / 1000.0
            try:
                return time.strftime("%Y-%m-%d", time.localtime(float(ts)))
            except (ValueError, OSError):
                pass
        raw = str(ts).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return raw
        return raw or "0000-00-00"

    # ------------------------------------------------------------------
    # 标题过滤
    # ------------------------------------------------------------------

    @staticmethod
    def _is_title_blocked(title: str) -> bool:
        """检查标题是否命中黑名单。

        规则：
        1. 命中 ``_TITLE_BLOCKLIST`` 中任一关键词 → 排除。
          但若标题已包含强财报关键词（年度报告/年报/半年度报告等），
          则"摘要/公告"类弱关键词不触发排除（处理港股全文中"年度报告及其摘要"等复合标题）。
        2. 同时包含财报关键词 AND 公告关键词 → 排除（如"关于年报的公告"）。

        Args:
            title: 公告标题。

        Returns:
            应排除则返回 ``True``。
        """
        # 规则 1：黑名单关键词
        for kw in _TITLE_BLOCKLIST:
            if kw not in title:
                continue
            # "摘要" 特殊处理：排除"年度报告摘要""年报摘要"这种纯摘要标题，
            # 但保留"年度报告及其摘要""年报及摘要"这种含完整报告的复合标题
            if kw == "摘要":
                if _is_summary_only_title(title):
                    return True
                continue
            return True
        # 规则 2：财报正本标题 + 公告关键词
        is_report = any(tok in title for tok in _REPORT_TITLE_TOKENS)
        is_notice = any(tok in title for tok in _REPORT_NOTICE_TITLE_TOKENS)
        if is_report and is_notice:
            return True
        return False

    @staticmethod
    def _is_amended(title: str) -> bool:
        """检测是否为修订版本。

        Args:
            title: 公告标题。

        Returns:
            修订版本则返回 ``True``。
        """
        return any(token in title for token in _TITLE_AMENDED_TOKENS)

    # ------------------------------------------------------------------
    # 财年推断
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_fiscal_year(title: str, announcement_date: str) -> int | None:
        """从标题推断财年。

        优先匹配 ``YYYY 年年度报告`` 模式，回退到 ``YYYY 年``，
        再回退到公告日期年份。

        Args:
            title: 公告标题。
            announcement_date: 公告日期（``YYYY-MM-DD``）。

        Returns:
            财年整数，无法推断则返回 ``None``。
        """
        # 1) "YYYY 年年度报告" 等强信号
        matched = _TITLE_FY_PATTERN.search(title)
        if matched:
            return int(matched.group(1))
        # 2) "二零二四年度报告" 等中文年份
        cn_matched = _CHINESE_NUMERAL_PATTERN.search(title)
        if cn_matched:
            year = CninfoDownloader._parse_chinese_digit_year(cn_matched.group(0))
            if year is not None:
                return year
        # 3) "YYYY 年" 弱回退
        fallback = _TITLE_FISCAL_YEAR_FALLBACK.search(title)
        if fallback:
            fy = int(fallback.group(1))
            # 排除过于久远或未来的年份（如 1998, 2099）
            if 2000 <= fy <= 2099:
                return fy
        # 4) 公告日期年份
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", announcement_date):
            return int(announcement_date[:4])
        return None

    @staticmethod
    def _parse_chinese_digit_year(text: str) -> int | None:
        """将中文年份文本转为阿拉伯数字。

        例如 ``二零二四`` → ``2024``, ``二四`` → ``2024``。

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

    # ------------------------------------------------------------------
    # 最佳公告选择
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_best_announcement(
        items: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """从同财期候选集中选出最佳公告。

        排序规则：
        1. 修订版本优先（``is_amended=True`` 排前面）。
        2. 公告日期最近优先。

        Args:
            items: 候选公告列表（由 ``_parse_raw_announcement`` 产生）。

        Returns:
            最佳候选，空列表返回 ``None``。
        """
        if not items:
            return None

        def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
            amended = CninfoDownloader._is_amended(item.get("title", ""))
            return (0 if amended else 1, item.get("announcement_date", ""))

        return min(items, key=_sort_key)

    # ------------------------------------------------------------------
    # search_report — 主搜索入口
    # ------------------------------------------------------------------

    def search_report(
        self,
        ticker: str,
        year: int,
        report_type: str = "年报",
        *,
        org_id: str | None = None,
    ) -> dict[str, Any] | None:
        """搜索最佳匹配的财报 PDF。

        使用分类 API（``hisAnnouncement/query``）按财期分类查询，
        候选人经黑名单过滤与修订版优先级排序后返回最佳匹配。

        Args:
            ticker: 6 位裸码（如 ``000651``）。
            year: 财年（如 ``2024``）。
            report_type: 财报类型（年报/中报/一季报/三季报）。
            org_id: 可选 orgId（已解析时复用，避免重复查 szse_stock.json）。

        Returns:
            ``{"url": str, "title": str, "date": str, "file_id": str}``
            或 ``None``（未找到）。

        Raises:
            RuntimeError: API 不可达时抛出。
            ValueError: ticker 无法解析时抛出。
        """
        # 1) 报-类型 → 财期 -> category
        period = _report_type_to_period(report_type)
        if period is None:
            return None
        category = _PERIOD_TO_CATEGORY.get(period)
        if category is None:
            return None

        # 2) 解析公司信息（A股走分类API，港股回退fulltext）
        digits = re.sub(r"\D", "", ticker.strip())
        # 港股特征：5位纯数字且首位为0（如 00700, 01858）
        is_hk = len(digits) == 5 and digits.isdigit() and digits[0] == "0"
        try:
            if org_id:
                column, plate = self._resolve_market_params(digits)
                company_info: dict[str, Any] | None = {
                    "org_id": org_id, "column": column, "plate": plate,
                }
            elif is_hk:
                # 港股直接走 fulltext 回退
                raise ValueError(f"港股代码 {digits}，跳过 A 股 szse 映射")
            else:
                company_info = self.resolve_company(digits)
        except ValueError:
            # 非A股（港股等），回退到全文搜索
            company_info = None

        # 3) 日期窗口
        start_date = f"{year}-01-01"
        end_date = f"{year + 1}-06-30"

        # 4) 查询
        if company_info is not None:
            # A股：分类 API
            raw_items = self._query_announcements(
                ticker=digits,
                org_id=company_info["org_id"],
                column=company_info["column"],
                plate=company_info["plate"],
                category=category,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            # 港股回退：全文搜索（cninfo 也索引港股公告）
            raw_items = self._query_fulltext(
                ticker=digits,
                year=year,
                report_type=report_type,
            )

        # 5) 解析 + 分组
        parsed: list[dict[str, Any]] = []
        for raw in raw_items:
            candidate = self._parse_raw_announcement(raw)
            if candidate is None:
                continue
            # 财年过滤
            fy = self._infer_fiscal_year(
                candidate["title"], candidate["announcement_date"]
            )
            if fy is not None and fy != year:
                continue
            # 财期过滤（fulltext 可能返回其他财期的结果）
            if not _title_matches_period(candidate["title"], period):
                continue
            # 黑名单过滤：排除通知信函、申请表格等非财报文件
            if _is_blacklisted_title(candidate["title"]):
                continue
            parsed.append(candidate)

        # 6) 选择最佳
        best = self._pick_best_announcement(parsed)
        if best is None:
            return None

        # 7) 构建 PDF URL
        raw_url = best["url"]
        if raw_url.startswith("http"):
            pdf_url = raw_url
        elif raw_url.startswith("/"):
            pdf_url = CNINFO_PDF_BASE.rstrip("/") + raw_url
        else:
            pdf_url = CNINFO_PDF_BASE + raw_url
        return {
            "url": pdf_url,
            "title": best["title"],
            "date": best["announcement_date"],
            "file_id": best.get("announcement_id", ""),
        }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

_REPORT_TYPE_TO_PERIOD_MAP: dict[str, str] = {
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


# 财期关键词（用于 fulltext 结果过滤）
_PERIOD_TITLE_TOKENS: dict[str, tuple[str, ...]] = {
    "FY": ("年度报告", "年报"),
    "H1": ("半年度报告", "半年报", "中报"),
    "Q1": ("一季度报告", "第一季度报告", "一季报"),
    "Q3": ("三季度报告", "第三季度报告", "三季报"),
}
# 排除关键词：匹配目标财期时，不能同时命中其他财期的关键词
_PERIOD_EXCLUDE_TOKENS: dict[str, tuple[str, ...]] = {
    "FY": ("半年度", "半年报", "一季度", "一季报", "三季度", "三季报"),
    "H1": ("一季度", "一季报", "三季度", "三季报"),
    "Q1": ("半年度", "半年报", "三季度", "三季报", "年度报告", "年报"),
    "Q3": ("半年度", "半年报", "一季度", "一季报", "年度报告", "年报"),
}


def _is_summary_only_title(title: str) -> bool:
    """判断标题是否为纯摘要文档（不含完整报告）。

    例如 ``年度报告摘要`` 是纯摘要，应排除；
    ``年度报告及其摘要`` 包含完整报告 + 摘要，应保留。

    Args:
        title: 公告标题。

    Returns:
        是纯摘要文档返回 ``True``。
    """
    # 复合标题模式：完整报告 + 摘要 → 非纯摘要
    _COMPOUND_PATTERNS = (
        "及其摘要", "及摘要", "和摘要",
        "及其概要", "及概要",
    )
    for pattern in _COMPOUND_PATTERNS:
        if pattern in title:
            return False
    # 纯摘要标题模式
    _SUMMARY_ONLY_PATTERNS = (
        "报告摘要", "年报摘要", "半年报摘要",
        "一季报摘要", "三季报摘要",
        "報告摘要", "年報摘要",
    )
    for pattern in _SUMMARY_ONLY_PATTERNS:
        if pattern in title:
            return True
    return False


def _title_matches_period(title: str, period: str) -> bool:
    """判断标题是否匹配目标财期。

    用于过滤 fulltext 搜索结果中的跨财期噪音
    （如搜索"年度报告"也可能匹配"半年度报告"）。

    Args:
        title: 公告标题。
        period: 目标财期代码（FY/H1/Q1/Q3）。

    Returns:
        匹配返回 ``True``。
    """
    include_tokens = _PERIOD_TITLE_TOKENS.get(period, ())
    exclude_tokens = _PERIOD_EXCLUDE_TOKENS.get(period, ())
    if not any(tok in title for tok in include_tokens):
        return False
    if any(tok in title for tok in exclude_tokens):
        return False
    return True


# 标题黑名单：这些关键词表明文件不是完整年报（通知信函、申请表、回条等）
_TITLE_BLACKLIST: tuple[str, ...] = (
    "通知信函", "通知函", "申请表格", "回条",
    "刊发通知", "非登记股东", "登记股东之通知",
    "致非登记股东", "致登记股东",
)


def _is_blacklisted_title(title: str) -> bool:
    """判断标题是否命中黑名单（通知信函等非财报文件）。

    Args:
        title: 公告标题。

    Returns:
        命中黑名单返回 ``True``。
    """
    return any(kw in title for kw in _TITLE_BLACKLIST)


def _report_type_to_period(report_type: str) -> str | None:
    """将 Turtle 财报类型映射为 Dayu 财期。

    Args:
        report_type: 财报类型字符串（年报/中报/q1/q3 等）。

    Returns:
        财期代码（FY/H1/Q1/Q3），未知返回 ``None``。
    """
    return _REPORT_TYPE_TO_PERIOD_MAP.get(report_type.lower())
