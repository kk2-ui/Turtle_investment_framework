"""SEC EDGAR HTML 预处理规则（从 Dayu sec_html_rules.py 提取）。

核心能力：
- SGML 信封剥离：移除 EDGAR 的 ``<DOCUMENT><TEXT>`` 包装
- SEC 封面页检测：关键词 + checkbox 密度双重判定
- Section 标题横线表识别：``Item7 ━━━━`` 等目录格式
- 版式表格分类：组合 heading 表 + 少行封面表判断

零外部依赖（仅 re），可直接用于 SEC filing HTML 的预处理。

Usage::

    from scripts.sec_html_rules import (
        strip_edgar_sgml_envelope,
        is_sec_cover_page_table,
        is_sec_section_heading_table,
    )

    clean_html = strip_edgar_sgml_envelope(raw_html)
    if is_sec_cover_page_table(table_text):
        skip_table()
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 正则与常量
# ---------------------------------------------------------------------------

_SECTION_HEADING_TABLE_PATTERN = re.compile(
    r"Item\s+\d+[A-Z]?\b.*[━──\-]{4,}", re.IGNORECASE
)

_SEC_COVER_KEYWORDS: frozenset[str] = frozenset({
    "annual report pursuant",
    "transition report pursuant",
    "section 13 or 15(d)",
    "securities exchange act",
    "commission file number",
})

_EDGAR_HTML_START_PATTERN = re.compile(r"<html[\s>]", re.IGNORECASE)
_EDGAR_SGML_SUFFIX_PATTERN = re.compile(
    r"</TEXT>\s*</DOCUMENT>\s*$", re.IGNORECASE
)

_WHITESPACE_RE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _normalize_whitespace(text: str) -> str:
    """将连续空白归一化为单个空格。"""
    return _WHITESPACE_RE.sub(" ", (text or "").replace("　", " ")).strip()


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def strip_edgar_sgml_envelope(content: str) -> str:
    """剥离 EDGAR SGML 信封标签。

    SEC EDGAR 的 exhibit HTML 可能被 ``<DOCUMENT>``、``<TEXT>``
    等 SGML 元数据包裹。该函数截取真正的 HTML 起始位置，
    并移除尾部 SGML 关闭标签。

    Args:
        content: 原始 HTML 文件内容。

    Returns:
        去除 SGML 信封后的 HTML 内容；若未检测到信封则原样返回。

    Example:
        >>> raw = "<SEC-DOCUMENT>...<DOCUMENT><TEXT><html>...</html></TEXT></DOCUMENT>"
        >>> clean = strip_edgar_sgml_envelope(raw)
        >>> clean.startswith("<html>")
        True
    """
    html_start = _EDGAR_HTML_START_PATTERN.search(content)
    if html_start and html_start.start() > 0:
        content = content[html_start.start():]
        content = _EDGAR_SGML_SUFFIX_PATTERN.sub("", content)
    return content


def is_sec_section_heading_table(text: str) -> bool:
    """判断文本是否命中 SEC 章节横线表。

    识别形如 ``Item 7. Management Discussion ----`` 的目录/标题表格。
    这类表格属于版式噪声，非数据表。

    Args:
        text: 表格文本。

    Returns:
        是否命中 SEC 章节横线表模式。
    """
    return bool(_SECTION_HEADING_TABLE_PATTERN.search(text))


def is_sec_cover_page_table(text: str) -> bool:
    """判断表格文本是否为 SEC 封面页元数据。

    规则覆盖两类低价值封面表：
    1. 法律声明、注册信息等封面关键词。
    2. 勾选框（☒/☐）密集的封面表。

    Args:
        text: 表格文本。

    Returns:
        是否为 SEC 封面页元数据表。
    """
    normalized_text = _normalize_whitespace(text)
    lowered = normalized_text.lower()

    # 规则 1：封面关键词
    if any(keyword in lowered for keyword in _SEC_COVER_KEYWORDS):
        return True

    # 规则 2：checkbox 密度
    checkbox_count = normalized_text.count("☒") + normalized_text.count("☐")
    word_count = max(len(normalized_text.split()), 1)
    if checkbox_count >= 2 and checkbox_count / word_count > 0.1:
        return True

    return False


def is_sec_layout_table(row_count: int, text: str) -> bool:
    """判断表格是否应按 SEC 版式噪声处理。

    组合判断：
    - 章节横线表 → 噪声
    - ≤5 行且为封面表 → 噪声

    Args:
        row_count: 表格行数。
        text: 表格文本。

    Returns:
        是否应作为版式噪声过滤。
    """
    normalized_text = _normalize_whitespace(text)
    if is_sec_section_heading_table(normalized_text):
        return True
    if row_count <= 5 and is_sec_cover_page_table(normalized_text):
        return True
    return False


def is_edgar_sgml_wrapped(content: str) -> bool:
    """快速检测 HTML 内容是否被 EDGAR SGML 信封包裹。

    Args:
        content: HTML 文件内容。

    Returns:
        如果检测到 SGML 信封标签，返回 ``True``。
    """
    return "<DOCUMENT>" in content.upper() or "<TEXT>" in content.upper()
