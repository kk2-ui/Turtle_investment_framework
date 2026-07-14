"""BM25F 段落检索排序器（从 Dayu bm25f_scorer.py 提取）。

核心能力：对已检索到的文档段落进行字段加权重排序。

字段权重方案（针对财报文档调优）:
- title: 3.0x (b=0.35) — 章节标题，信号极强
- item:  2.0x (b=0.20) — Item 编号，强信号
- topic: 2.0x (b=0.20) — 语义类型，强信号
- path:  2.0x (b=0.35) — 层级路径，中等信号
- preview: 1.0x (b=0.75) — 段落预览，标准信号
- content: 1.0x (b=0.75) — 段落正文，标准信号

零外部依赖（仅 math + re + collections），可直接用于
Turtle Phase 3 对年报文档关键词搜索结果的重排序。

Usage::

    from scripts.bm25f_scorer import build_section_index, score_entry

    sections = [
        {"ref": "s1", "title": "Risk Factors", "item": "1A", ...},
        {"ref": "s2", "title": "MD&A", "item": "7", ...},
    ]
    index = build_section_index(sections)

    entry = {"section_ref": "s1", "snippet": "competition risk ..."}
    score = score_entry(entry=entry, query="competition risk", index=index)
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_FIELD_WEIGHTS: dict[str, float] = {
    "title": 3.0,
    "item": 2.0,
    "topic": 2.0,
    "path": 2.0,
    "preview": 1.0,
    "content": 1.0,
}

_FIELD_B: dict[str, float] = {
    "title": 0.35,
    "item": 0.20,
    "topic": 0.20,
    "path": 0.35,
    "preview": 0.75,
    "content": 0.75,
}

_K1: float = 1.2

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BM25FSectionProfile:
    """单个 section 的词法字段画像。

    Args:
        section_ref: section 唯一标识。
        field_tokens: 各字段对应的 token 序列。
    """

    section_ref: str
    field_tokens: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class BM25FSectionIndex:
    """BM25F 风格 section 级检索索引。

    Args:
        profiles: ``section_ref → BM25FSectionProfile`` 映射。
        document_frequency: token 的 section 级文档频次 (df)。
        avg_field_lengths: 各字段平均长度。
        avg_content_length: content 字段平均长度。
        document_count: section 总数 (N)。
    """

    profiles: dict[str, BM25FSectionProfile]
    document_frequency: dict[str, int]
    avg_field_lengths: dict[str, float]
    avg_content_length: float
    document_count: int


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def build_section_index(
    sections: Sequence[Mapping[str, Any]],
) -> BM25FSectionIndex:
    """从 section 摘要列表构建 BM25F 索引。

    sections 需包含 ``ref / title / item / topic / path / preview`` 字段。

    Args:
        sections: section 摘要序列（通常来自文档 section 列表）。

    Returns:
        预构建的 ``BM25FSectionIndex``。

    Example:
        >>> sections = [
        ...     {"ref": "s1", "title": "Risk Factors", "item": "1A",
        ...      "topic": "risk_factors", "path": "Part I > Item 1A",
        ...      "preview": "The company faces various risks..."},
        ... ]
        >>> index = build_section_index(sections)
    """
    profiles: dict[str, BM25FSectionProfile] = {}
    document_frequency: Counter[str] = Counter()
    total_field_lengths: Counter[str] = Counter()

    for section in sections:
        section_ref = str(section.get("ref") or "").strip()
        if not section_ref:
            continue

        field_texts = {
            "title": _normalize_text(section.get("title")),
            "item": _normalize_text(section.get("item")),
            "topic": _normalize_text(section.get("topic")),
            "path": _normalize_text(section.get("path")),
            "preview": _normalize_text(section.get("preview")),
        }
        field_tokens = {
            field_name: tuple(_tokenize(text))
            for field_name, text in field_texts.items()
        }
        profiles[section_ref] = BM25FSectionProfile(
            section_ref=section_ref,
            field_tokens=field_tokens,
        )
        seen_terms: set[str] = set()
        for fname, tokens in field_tokens.items():
            total_field_lengths[fname] += len(tokens)
            seen_terms.update(tokens)
        document_frequency.update(seen_terms)

    document_count = len(profiles)
    avg_field_lengths: dict[str, float] = {}
    for field_name in ("title", "item", "topic", "path", "preview"):
        avg_field_lengths[field_name] = (
            total_field_lengths[field_name] / document_count
            if document_count > 0
            else 0.0
        )

    return BM25FSectionIndex(
        profiles=profiles,
        document_frequency=dict(document_frequency),
        avg_field_lengths=avg_field_lengths,
        avg_content_length=avg_field_lengths.get("preview", 0.0),
        document_count=document_count,
    )


def score_entry(
    *,
    entry: Mapping[str, Any],
    query: str,
    index: BM25FSectionIndex,
) -> float:
    """计算单条搜索命中的 BM25F 风格分数。

    使用预构建索引中的 IDF 和字段统计量，
    对命中的各字段加权词频求和。

    Args:
        entry: 搜索命中条目，需包含 ``section_ref`` 和正文内容。
        query: 搜索查询字符串。
        index: 预构建的 BM25F 索引。

    Returns:
        BM25F 得分；无法计算时返回 ``0.0``。

    Example:
        >>> entry = {"section_ref": "s1", "snippet": "competition in market..."}
        >>> score = score_entry(entry=entry, query="competition", index=index)
    """
    query_terms = _tokenize(query)
    if not query_terms or index.document_count <= 0:
        return 0.0

    section_ref = str(entry.get("section_ref") or "").strip()
    if not section_ref:
        return 0.0

    profile = index.profiles.get(section_ref)
    if profile is None:
        return 0.0

    # 构建 content 字段 token
    content_tokens = tuple(
        _tokenize(_extract_entry_content_text(entry))
    )

    field_counters: dict[str, Counter[str]] = {
        field_name: Counter(tokens)
        for field_name, tokens in profile.field_tokens.items()
    }
    field_counters["content"] = Counter(content_tokens)

    avg_field_lengths = dict(index.avg_field_lengths)
    avg_field_lengths["content"] = index.avg_content_length

    score = 0.0
    for term in query_terms:
        term_df = index.document_frequency.get(term, 0)
        if term_df <= 0:
            continue
        idf = math.log(
            1.0 + ((index.document_count - term_df + 0.5) / (term_df + 0.5))
        )
        weighted_tf = 0.0
        for field_name, weight in _FIELD_WEIGHTS.items():
            counter = field_counters.get(field_name)
            if counter is None:
                continue
            tf = counter.get(term, 0)
            if tf <= 0:
                continue
            field_length = sum(counter.values())
            avg_length = avg_field_lengths.get(field_name, 0.0)
            normalized_tf = _normalize_tf(
                tf=tf,
                field_length=field_length,
                avg_field_length=avg_length,
                b=_FIELD_B.get(field_name, 0.75),
            )
            weighted_tf += weight * normalized_tf
        if weighted_tf <= 0:
            continue
        score += idf * (
            ((_K1 + 1.0) * weighted_tf) / (_K1 + weighted_tf)
        )
    return round(score, 6)


def score_entries(
    *,
    entries: Sequence[Mapping[str, Any]],
    query: str,
    index: BM25FSectionIndex,
) -> list[tuple[int, float]]:
    """批量计算搜索命中条目的 BM25F 分数。

    返回 (原始索引, 分数) 列表，按分数降序排列。

    Args:
        entries: 搜索命中条目序列。
        query: 搜索查询字符串。
        index: 预构建的 BM25F 索引。

    Returns:
        ``[(original_idx, score), ...]`` 按分数降序。
    """
    scored = [
        (i, score_entry(entry=entry, query=query, index=index))
        for i, entry in enumerate(entries)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _normalize_tf(
    *,
    tf: int,
    field_length: int,
    avg_field_length: float,
    b: float,
) -> float:
    """按 BM25F 公式标准化字段内词频。

    ``tf / (1 - b + b * (len / avg_len))``
    """
    if tf <= 0:
        return 0.0
    if field_length <= 0 or avg_field_length <= 0:
        return float(tf)
    denominator = 1.0 - b + b * (field_length / avg_field_length)
    if denominator <= 0:
        return float(tf)
    return float(tf) / denominator


def _extract_entry_content_text(entry: Mapping[str, Any]) -> str:
    """提取搜索命中的正文内容。"""
    evidence = entry.get("evidence")
    if isinstance(evidence, Mapping):
        context = _normalize_text(evidence.get("context"))
        if context:
            return context
        matched = _normalize_text(evidence.get("matched_text"))
        if matched:
            return matched
    return _normalize_text(entry.get("snippet"))


def _normalize_text(value: Any) -> str:
    """规整文本为可分词字符串。"""
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def _tokenize(text: str) -> list[str]:
    """提取 ASCII token（英文词法分词）。"""
    return _TOKEN_PATTERN.findall(text)
