"""SEC EDGAR 美股财报下载器。

使用 SEC EDGAR API 下载美股财报（主文档 HTML）。
支持 10-K/10-Q/20-F/6-K/8-K 等表单类型，
按表单类型自动回溯对应年份窗口。

设计原则：
- 仅依赖 ``requests``，同步风格。
- SEC 限制 ≤10 req/s，内置进程内速率限制。
- 下载主 HTML 文档（非 PDF），不包含 XBRL/exhibits。
- 不引入 6-K 分类规则、SC13 过滤等复杂逻辑。
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests

# ---------------------------------------------------------------------------
# SEC API 常量
# ---------------------------------------------------------------------------

SEC_TICKER_MAP_URL: str = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL: str = (
    "https://data.sec.gov/submissions/CIK{cik10}.json"
)
ARCHIVES_BASE: str = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/"
)
ARCHIVES_INDEX_JSON: str = ARCHIVES_BASE + "index.json"

DEFAULT_USER_AGENT: str = "DayuAgent/1.0 unconfigured@example.com"
DEFAULT_REQUEST_TIMEOUT: float = 30.0
DEFAULT_SLEEP_SECONDS: float = 0.15   # SEC: ≤10 req/s
DEFAULT_MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 0.8
_SEC_MIN_INTERVAL: float = 0.12

# ---------------------------------------------------------------------------
# 表单类型 → 默认回溯年数
# ---------------------------------------------------------------------------

_FORM_LOOKBACK_YEARS: dict[str, int] = {
    "10-K": 5,
    "10-K/A": 5,
    "20-F": 3,
    "20-F/A": 3,
    "10-Q": 2,
    "10-Q/A": 2,
    "6-K": 1,
    "6-K/A": 1,
    "8-K": 1,
    "8-K/A": 1,
    "DEF 14A": 3,
}

# 报表类型 → SEC 表单 types
_REPORT_TYPE_TO_SEC_FORMS: dict[str, list[str]] = {
    "年报": ["10-K", "20-F"],
    "annual": ["10-K", "20-F"],
    "中报": ["10-Q", "6-K"],
    "interim": ["10-Q", "6-K"],
    "半年报": ["10-Q", "6-K"],
    "一季报": ["10-Q"],
    "q1": ["10-Q"],
    "三季报": ["10-Q"],
    "q3": ["10-Q"],
}

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _normalize_ticker(ticker: str) -> str:
    """规范化美股 ticker 为大写。

    ``brk.b`` → ``BRK-B``, ``AAPL`` → ``AAPL``。

    Args:
        ticker: 原始股票代码。

    Returns:
        大写 ticker，点号替换为横杠。
    """
    raw = ticker.strip().upper()
    # 类股分隔符统一为横杠
    if "." in raw and not raw.startswith("."):
        raw = raw.replace(".", "-")
    return raw


def _accession_to_no_dash(accession: str) -> str:
    """移除 accession number 中的连字符。

    ``0000320193-24-000123`` → ``000032019324000123``。

    Args:
        accession: 带连字符的 accession number。

    Returns:
        无连字符形式。
    """
    return accession.replace("-", "")


def _select_primary_from_index_items(
    items: list[dict[str, Any]], form_type: str
) -> str | None:
    """从 index.json 文件列表中选出主文档。

    优先选择与 form_type 同型的主文档，回退到第一个 HTML 文件。

    Args:
        items: index.json 中的 ``directory.item`` 列表。
        form_type: 表单类型（如 ``10-K``）。

    Returns:
        主文档文件名，找不到返回 ``None``。
    """
    normalized_form = form_type.strip().upper()
    html_files: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        if not name.lower().endswith((".htm", ".html")):
            continue
        html_files.append(name)
        doc_type = str(item.get("type", "")).strip().upper()
        if doc_type == normalized_form:
            return name
    # 回退：返回第一个 HTML 文件
    if html_files:
        # 优先选不含 "ex" 的文件名（更可能是主文档）
        for name in html_files:
            if "ex" not in name.lower():
                return name
        return html_files[0]
    return None


# ---------------------------------------------------------------------------
# SecDownloader
# ---------------------------------------------------------------------------

class SecDownloader:
    """SEC EDGAR 财报下载客户端。

    同步、requests-based，简化自 Dayu 的 async SecDownloader。
    仅下载主 HTML 文档（不包含 XBRL/exhibits/6-K 分类）。

    Args:
        session: 可选 requests.Session。
        user_agent: SEC 要求的 User-Agent（含联系信息）。
        request_timeout: HTTP 请求超时秒数。
        max_retries: 最大重试次数。
        sleep_seconds: 请求间隔秒数。
    """

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    ) -> None:
        if not user_agent or user_agent == DEFAULT_USER_AGENT:
            raise ValueError(
                "SEC 要求有效的 User-Agent（含联系信息）。"
                "请设置 SEC_USER_AGENT 环境变量或传入 user_agent 参数。"
            )
        self._session: requests.Session = session or requests.Session()
        self._user_agent: str = user_agent
        self._request_timeout: float = request_timeout
        self._max_retries: int = max_retries
        self._sleep_seconds: float = sleep_seconds
        self._last_request_at: float = 0.0
        self._headers: dict[str, str] = {"User-Agent": self._user_agent}

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """SEC 速率限制：请求间 ≥0.12s 间隔。"""
        now = time.monotonic()
        if self._last_request_at > 0:
            elapsed = now - self._last_request_at
            remaining = _SEC_MIN_INTERVAL - elapsed
            if remaining > 0:
                time.sleep(remaining)
        # 额外按配置间隔
        if self._sleep_seconds > 0 and self._last_request_at > 0:
            pass  # _SEC_MIN_INTERVAL 已足够

    def _http_get_json(self, url: str) -> dict[str, Any]:
        """GET JSON，带重试与速率限制。"""
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._throttle()
                resp = self._session.get(
                    url,
                    timeout=self._request_timeout,
                    headers=self._headers,
                )
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                return resp.json()  # type: ignore[no-any-return]
            except Exception as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                if attempt < self._max_retries:
                    backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    time.sleep(backoff)
        raise RuntimeError(f"SEC HTTP GET {url} 失败: {last_error}")

    def _http_get_bytes(self, url: str) -> bytes:
        """GET 字节内容，带重试。"""
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._throttle()
                resp = self._session.get(
                    url,
                    timeout=self._request_timeout,
                    headers=self._headers,
                )
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                return resp.content
            except Exception as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                if attempt < self._max_retries:
                    time.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
        raise RuntimeError(f"SEC HTTP GET {url} 失败: {last_error}")

    # ------------------------------------------------------------------
    # resolve_company
    # ------------------------------------------------------------------

    def resolve_company(self, ticker: str) -> dict[str, str]:
        """ticker → CIK + 公司名。

        从 ``company_tickers.json`` 全量映射中查找。

        Args:
            ticker: 美股股票代码（如 ``AAPL``, ``BRK-B``）。

        Returns:
            ``{"cik": str, "cik10": str, "company_name": str}``。

        Raises:
            RuntimeError: API 不可达时抛出。
            ValueError: ticker 不在 SEC 映射表中时抛出。
        """
        normalized = _normalize_ticker(ticker)
        mapping = self._http_get_json(SEC_TICKER_MAP_URL)
        for row in mapping.values():
            if not isinstance(row, dict):
                continue
            entry_ticker = str(row.get("ticker", "")).strip().upper()
            if entry_ticker == normalized:
                cik_str = str(row.get("cik_str", "")).strip()
                company_name = str(row.get("title", "")).strip()
                if cik_str.isdigit():
                    cik = str(int(cik_str))
                    cik10 = cik.zfill(10)
                    return {
                        "cik": cik,
                        "cik10": cik10,
                        "company_name": company_name,
                    }
        raise ValueError(f"ticker={normalized} 不在 SEC company_tickers.json 中")

    # ------------------------------------------------------------------
    # _fetch_submissions
    # ------------------------------------------------------------------

    def _fetch_submissions(self, cik10: str) -> dict[str, Any]:
        """拉取 submissions JSON。

        Args:
            cik10: 10 位 CIK 字符串。

        Returns:
            submissions JSON dict。
        """
        url = SEC_SUBMISSIONS_URL.format(cik10=cik10)
        return self._http_get_json(url)

    # ------------------------------------------------------------------
    # list_filings
    # ------------------------------------------------------------------

    def list_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        years: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """列出符合条件的 SEC filings。

        从 submissions JSON 的 ``filings.recent`` 中筛选
        匹配的表单类型和日期范围。

        Args:
            ticker: 美股 stock ticker。
            form_types: 目标表单类型列表（如 ``["10-K", "10-Q"]``）。
            years: 目标财年范围（若为 ``None``，按默认回溯窗口）。

        Returns:
            filing 描述列表：
            ``[{form_type, filing_date, accession_number, cik, ...}]``。

        Raises:
            RuntimeError: API 不可达时抛出。
            ValueError: ticker 解析失败时抛出。
        """
        company = self.resolve_company(ticker)
        submissions = self._fetch_submissions(company["cik10"])
        filings_recent: list[dict[str, Any]] = submissions.get("filings", {}).get("recent", [])
        if not filings_recent:
            return []

        # 确定回溯窗口
        if years:
            target_years = set(years)
        elif form_types:
            max_lookback = max(
                _FORM_LOOKBACK_YEARS.get(ft, 3) for ft in form_types
            )
            current_year = time.localtime().tm_year
            target_years = set(range(current_year - max_lookback, current_year + 1))
        else:
            current_year = time.localtime().tm_year
            target_years = set(range(current_year - 5, current_year + 1))

        # 确定目标表单
        target_forms: set[str] = set()
        if form_types:
            target_forms = {ft.upper() for ft in form_types}

        results: list[dict[str, Any]] = []
        for i, form in enumerate(filings_recent.get("form", []) or []):
            if not isinstance(form, str):
                continue
            if target_forms and form.upper() not in target_forms:
                continue
            # 日期过滤
            filing_date_str = ""
            dates = filings_recent.get("filingDate", [])
            if isinstance(dates, list) and i < len(dates):
                filing_date_str = str(dates[i])
            if filing_date_str:
                fy = int(filing_date_str[:4])
                if fy not in target_years:
                    continue
            # 构建记录
            record: dict[str, Any] = {"form_type": form}
            for field in (
                "filingDate", "accessionNumber", "primaryDocument",
                "reportDate", "cik",
            ):
                values = filings_recent.get(field, [])
                if isinstance(values, list) and i < len(values):
                    record[field] = values[i]
            results.append(record)
        return results

    # ------------------------------------------------------------------
    # resolve_primary_document
    # ------------------------------------------------------------------

    def resolve_primary_document(
        self,
        cik: str,
        accession_no_dash: str,
        form_type: str,
    ) -> str:
        """从 index.json 解析主文档文件名。

        Args:
            cik: CIK（无前导零）。
            accession_no_dash: 无连字符 accession number。
            form_type: 表单类型。

        Returns:
            主文档文件名（如 ``aapl-20240928_10k.htm``）。

        Raises:
            RuntimeError: API 不可达或无法解析时抛出。
        """
        index_url = ARCHIVES_INDEX_JSON.format(
            cik=str(int(cik)), accession_no_dash=accession_no_dash
        )
        index_json = self._http_get_json(index_url)
        items: list[dict[str, Any]] = index_json.get("directory", {}).get("item", []) or []
        primary = _select_primary_from_index_items(items, form_type)
        if primary:
            return primary
        raise RuntimeError(
            f"无法从 index.json 解析 primary_document: "
            f"cik={cik} accession={accession_no_dash} form={form_type}"
        )

    # ------------------------------------------------------------------
    # download_filing — 下载单个 filing
    # ------------------------------------------------------------------

    def download_filing(
        self,
        ticker: str,
        form_type: str,
        cik: str,
        accession_number: str,
        save_dir: str,
    ) -> dict[str, Any] | None:
        """下载单个 SEC filing 的主文档。

        Args:
            ticker: 股票代码。
            form_type: 表单类型。
            cik: CIK（无前导零）。
            accession_number: accession number（含连字符）。
            save_dir: 保存目录。

        Returns:
            ``{"filepath": str, "filesize": int, ...}``
            或 ``None``（下载失败）。

        Raises:
            RuntimeError: index.json 解析失败时抛出。
        """
        accession_no_dash = _accession_to_no_dash(accession_number)
        try:
            primary_doc = self.resolve_primary_document(
                cik=cik,
                accession_no_dash=accession_no_dash,
                form_type=form_type,
            )
        except RuntimeError:
            return None

        archive_base = ARCHIVES_BASE.format(
            cik=str(int(cik)), accession_no_dash=accession_no_dash
        )
        file_url = archive_base + primary_doc

        # 构建文件名
        normalized_ticker = _normalize_ticker(ticker)
        fiscal_year = accession_number.split("-")[1][:4] if "-" in accession_number else ""
        safe_form = form_type.replace("/", "-")
        filename = f"{normalized_ticker}_{fiscal_year}_{safe_form}.html"
        filepath = os.path.join(save_dir, filename)

        try:
            content = self._http_get_bytes(file_url)
        except RuntimeError:
            return None

        if not content:
            return None

        os.makedirs(save_dir, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(content)

        return {
            "filepath": os.path.abspath(filepath),
            "filesize": len(content),
            "url": file_url,
            "form_type": form_type,
            "accession_number": accession_number,
            "primary_document": primary_doc,
        }

    # ------------------------------------------------------------------
    # search_report — 主搜索入口
    # ------------------------------------------------------------------

    def search_report(
        self,
        ticker: str,
        year: int,
        report_type: str = "年报",
        *,
        save_dir: str = ".",
    ) -> dict[str, Any] | None:
        """搜索并下载最佳匹配的美股财报。

        自动推断对应的 SEC 表单类型，按默认回溯窗口筛选，
        选择最近一个匹配的 filing 并下载主文档。

        Args:
            ticker: 美股 ticker（如 ``AAPL``, ``BRK-B``）。
            year: 目标财年。
            report_type: Turtle 财报类型（年报/中报/q1/q3）。
            save_dir: 保存目录。

        Returns:
            ``{"url": str, "title": str, "date": str, "filepath": str, ...}``
            或 ``None``。

        Raises:
            RuntimeError: API 不可达时抛出。
            ValueError: ticker 解析失败或 User-Agent 未设置时抛出。
        """
        form_types = _REPORT_TYPE_TO_SEC_FORMS.get(report_type.lower(), ["10-K"])
        company = self.resolve_company(ticker)

        filings = self.list_filings(
            ticker=ticker,
            form_types=form_types,
            years=[year],
        )
        if not filings:
            return None

        # 选择最近日期的 filing
        filings.sort(
            key=lambda f: str(f.get("filingDate", "")),
            reverse=True,
        )
        best = filings[0]

        result = self.download_filing(
            ticker=ticker,
            form_type=best["form_type"],
            cik=company["cik"],
            accession_number=best.get("accessionNumber", ""),
            save_dir=save_dir,
        )
        if result is None:
            return None

        return {
            "url": result["url"],
            "title": f"{_normalize_ticker(ticker)} {best['form_type']} FY{year}",
            "date": str(best.get("filingDate", "")),
            "filepath": result["filepath"],
            "filesize": result["filesize"],
            "form_type": best["form_type"],
        }
