"""网络搜索工具 — web_search + web_fetch。

给 Agent 补充 DB/PDF/Zone B 覆盖不到的外部信息：
- 行业新闻、重大事件、竞争对手动态
- 公司官网、监管披露的最新版本
- DB 中缺失的定性上下文

可信度标注：
- 来自公司官网/港交所/证监会 → medium
- 来自新闻媒体/第三方网站 → low
"""

from __future__ import annotations

import html as html_lib
import os
import re
import sys
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

# 保底 user-agent
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "TurtleAgent/1.0 (investment research)"
)

_LOW_AUTHORITY_HOSTS = (
    "weixin.qq.com", "mp.weixin.qq.com", "sogou.com", "baijiahao.baidu.com",
    "toutiao.com", "xueqiu.com",
)
_PRIMARY_AUTHORITY_HOSTS = (
    "gov.cn", "stats.gov.cn", "cninfo.com.cn", "sse.com.cn", "szse.cn",
    "hkexnews.hk", "hkex.com.hk", "sec.gov",
)


def _classify_web_authority(url: str) -> str:
    """Coarse deterministic tier for whether a fetched body can pass the web gate.

    This is intentionally conservative only at the bottom: social/search relay
    pages cannot be the sole external body. Unknown direct domains remain
    reviewable because company and industry official domains are open-ended.
    """
    host = (urlparse(str(url or "")).hostname or "").lower().removeprefix("www.")
    if any(host == item or host.endswith("." + item) for item in _LOW_AUTHORITY_HOSTS):
        return "LOW"
    if any(host == item or host.endswith("." + item) for item in _PRIMARY_AUTHORITY_HOSTS):
        return "PRIMARY"
    return "STANDARD"


# ── HTML to text ──

class _TextExtractor(HTMLParser):
    """Strip HTML tags, keep meaningful text."""

    def __init__(self):
        super().__init__()
        self._text: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr"):
            self._text.append("\n")

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._text.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self._text)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ── Tools ──


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_lib.unescape(value))).strip()


def _search_sogou(client: httpx.Client, query: str, max_results: int) -> list[dict[str, str]]:
    """Use the currently reachable Chinese search endpoint.

    Relative redirect URLs are kept resolvable through Sogou; ``web_fetch``
    follows the redirect and records the final URL/content.
    """
    url = f"https://www.sogou.com/web?query={quote(query)}"
    resp = client.get(url, headers={"User-Agent": UA}, timeout=8.0)
    resp.raise_for_status()
    blocks = re.findall(
        r'<div[^>]*class="[^"]*vrwrap[^"]*"[^>]*>(.*?)(?=<div[^>]*class="[^"]*vrwrap|\Z)',
        resp.text, re.DOTALL,
    )
    results: list[dict[str, str]] = []
    for block in blocks:
        title_match = re.search(
            r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h3>',
            block, re.DOTALL,
        )
        if not title_match:
            continue
        href, title = title_match.groups()
        snippet_match = re.search(
            r'<(?:p|div)[^>]*class="[^"]*(?:str_info|text-layout|ft)[^"]*"[^>]*>(.*?)</(?:p|div)>',
            block, re.DOTALL,
        )
        real_url = urljoin("https://www.sogou.com", html_lib.unescape(href))
        if not real_url.startswith(("http://", "https://")):
            continue
        results.append({
            "title": _clean_html(title) or real_url[:60],
            "url": real_url,
            "snippet": _clean_html(snippet_match.group(1) if snippet_match else "")[:500],
        })
        if len(results) >= max_results:
            break
    return results


def _search_duckduckgo(client: httpx.Client, query: str, max_results: int) -> list[dict[str, str]]:
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    # DuckDuckGo is blocked by TLS middleboxes on some networks. Keep this
    # fallback on a short leash so one unreachable provider cannot consume an
    # entire research-task call budget or stall the agent loop.
    resp = client.get(url, headers={"User-Agent": UA}, timeout=5.0)
    resp.raise_for_status()
    result_blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        resp.text, re.DOTALL,
    )
    if not result_blocks:
        links = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL,
        )
        snippets = re.findall(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL,
        )
        result_blocks = [
            (href, title, snippets[i] if i < len(snippets) else "")
            for i, (href, title) in enumerate(links[:max_results])
        ]
    results: list[dict[str, str]] = []
    for href, title, snippet in result_blocks[:max_results]:
        real_url = html_lib.unescape(href)
        if "uddg=" in real_url:
            match = re.search(r"uddg=(https?%3A[^&'\"]+)", real_url)
            if match:
                from urllib.parse import unquote
                real_url = unquote(match.group(1))
        if real_url.startswith("//"):
            real_url = "https:" + real_url
        if not real_url.startswith(("http://", "https://")):
            continue
        results.append({
            "title": _clean_html(title) or real_url[:60],
            "url": real_url,
            "snippet": _clean_html(snippet)[:500],
        })
    return results


_SEARCH_PROVIDERS = {
    "sogou": _search_sogou,
    "duckduckgo": _search_duckduckgo,
}


def web_search(
    query: str = "",
    max_results: int = 5,
    offset: int = 0,
    research_for_chapters: list[int] | None = None,
) -> dict[str, Any]:
    """搜索网络信息（使用 DuckDuckGo HTML 搜索，无需 API key）。

    返回标题、URL、摘要。用于补充 DB/年报中不可用的外部上下文。

    Args:
        query: 搜索关键词（中英文均可）。
        max_results: 最多返回结果数（默认 5，最大 10）。
        research_for_chapters: 本次检索明确服务的报告章节；仅用于审计归因。

    Returns:
        ``{query, results: [{title, url, snippet}], source: "web_search"}``。
    """
    if not query.strip():
        return {"error": "需要 query 参数", "results": []}

    max_results = min(max(max_results, 1), 10)
    configured = os.environ.get("TURTLE_WEB_SEARCH_PROVIDERS", "sogou,duckduckgo")
    provider_names = [name.strip().lower() for name in configured.split(",") if name.strip()]
    provider_errors: list[dict[str, str]] = []
    results: list[dict[str, str]] = []
    used_provider = ""
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for name in provider_names:
            provider = _SEARCH_PROVIDERS.get(name)
            if provider is None:
                provider_errors.append({"provider": name, "error": "unknown_provider"})
                continue
            try:
                results = provider(client, query, max_results + offset)
                if results:
                    used_provider = name
                    break
                provider_errors.append({"provider": name, "error": "no_results"})
            except Exception as exc:
                provider_errors.append({"provider": name, "error": f"{type(exc).__name__}: {exc}"[:300]})

    if not results:
        return {
            "query": query,
            "results": [],
            "source": "web_search",
            "provider": None,
            "provider_errors": provider_errors,
            "error": "all_search_providers_failed",
        }

    window = results[offset:offset + max_results]
    next_cursor = offset + len(window)
    return {
        "query": query,
        "results": window,
        "source": "web_search",
        "provider": used_provider,
        "provider_errors": provider_errors,
        "total": len(results),
        "offset": offset,
        "has_more": next_cursor < len(results),
        "next_cursor": next_cursor if next_cursor < len(results) else None,
    }


def web_fetch(
    url: str = "",
    max_chars: int = 8000,
    start_char: int = 0,
    research_for_chapters: list[int] | None = None,
) -> dict[str, Any]:
    """抓取网页内容并提取纯文本。

    用于获取搜索结果中某篇具体文章/页面的详细内容。

    Args:
        url: 网页 URL（必须是 http/https）。
        max_chars: 最大返回字符数（默认 8000，最大 20000）。
        research_for_chapters: 本次正文读取明确服务的报告章节；仅用于审计归因。

    Returns:
        ``{url, text, char_count, status_code, source: "web_fetch"}``。
    """
    if not url or not url.startswith(("http://", "https://")):
        return {"error": "需要有效的 http/https URL", "text": ""}

    max_chars = min(max(max_chars, 500), 20000)

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": UA})
            if resp.status_code != 200:
                return {
                    "url": url,
                    "text": "",
                    "char_count": 0,
                    "status_code": resp.status_code,
                    "error": f"HTTP {resp.status_code}",
                }

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                # Not HTML/text — return metadata only
                return {
                    "url": url,
                    "text": f"[非文本内容: {content_type}, {len(resp.content)} bytes]",
                    "char_count": 0,
                    "status_code": 200,
                }

            # Auto-detect encoding
            resp.encoding = resp.encoding or "utf-8"
            text = resp.text

            if "text/html" in content_type:
                text = _html_to_text(text)

            original_len = len(text)
            sliced = text[start_char:start_char + max_chars]
            next_cursor = start_char + len(sliced)

            return {
                "url": url,
                "final_url": str(resp.url),
                "text": sliced,
                "char_count": len(sliced),
                "status_code": 200,
                "source": "web_fetch",
                "source_domain": (urlparse(str(resp.url)).hostname or "").lower(),
                "source_authority": _classify_web_authority(str(resp.url)),
                "original_char_count": original_len,
                "returned_char_count": len(sliced),
                "start_char": start_char,
                "end_char": start_char + len(sliced),
                "truncated": original_len > start_char + len(sliced),
                "has_more": original_len > start_char + len(sliced),
                "next_cursor": next_cursor if original_len > start_char + len(sliced) else None,
            }

    except Exception as exc:
        return {
            "url": url,
            "text": "",
            "error": f"抓取失败: {exc}",
        }


# ── 工具元数据（供 auto_discover 使用）─-─

_WEB_SEARCH_META = {
    "name": "web_search",
    "description": (
        "搜索网络信息（DuckDuckGo，免费无 API key）。"
        "返回标题+URL+摘要。用于补充 DB/年报覆盖不到的行业新闻、竞争动态、最新事件。"
        "可信度：来自官网/监管机构→中等，新闻媒体→低。"
    ),
    "parameters": {
        "query": {"type": "string", "description": "搜索关键词（中英文均可）"},
        "max_results": {
            "type": "integer",
            "description": "最多返回结果数（默认5，最大10）",
            "optional": True,
        },
        "offset": {
            "type": "integer",
            "description": "搜索结果续读 offset",
            "optional": True,
        },
        "research_for_chapters": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "本次检索服务的章节编号，如 [2] 或 [2,8]；来源深化时必填",
            "optional": True,
        },
    },
}

_WEB_FETCH_META = {
    "name": "web_fetch",
    "description": (
        "抓取网页内容并提取纯文本（HTML→text）。"
        "用于读取 web_search 返回结果中某篇具体文章的详细内容。"
    ),
    "parameters": {
        "url": {"type": "string", "description": "网页 URL（http/https）"},
        "max_chars": {
            "type": "integer",
            "description": "最大返回字符数（默认8000，最大20000）",
            "optional": True,
        },
        "start_char": {
            "type": "integer",
            "description": "网页正文续读起始字符，使用上次 next_cursor",
            "optional": True,
        },
        "research_for_chapters": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "本次网页正文服务的章节编号，如 [2] 或 [2,8]；来源深化时必填",
            "optional": True,
        },
    },
}

web_search._tool_meta = _WEB_SEARCH_META  # type: ignore[attr-defined]
web_fetch._tool_meta = _WEB_FETCH_META  # type: ignore[attr-defined]
