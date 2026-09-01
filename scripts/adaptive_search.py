"""自适应搜索管线（从 Dayu search_engine.py 核心算法提取）。

实现完整的财报文档搜索流水线：

1. **查询诊断** — 歧义度评分 + 意图分类
2. **自适应搜索计划** — 高歧义query分两阶段，低歧义一次执行
3. **查询扩展** — 短语变体 → 同义词 → 词级token（三层回退）
4. **意图过滤** — 按语义桶过滤 + 噪声惩罚 + 支持上下文
5. **排序** — 策略优先级 → 意图一致性 → BM25F → 邻近度

设计原则：
- 搜索执行通过 ``SearchBackend`` 协议抽象，不依赖具体 processor。
- 所有算法函数为纯函数，可独立测试。
- 依赖已移植的 ``financial_synonyms.py`` 常量。

Usage::

    from scripts.adaptive_search import (
        SearchPipeline, SearchBackend, SearchResult,
        diagnose_query, expand_query, rank_results,
    )

    class MyBackend(SearchBackend):
        def search(self, query: str, within_ref: str | None) -> list[dict]:
            return [...]  # 你的搜索实现

    pipeline = SearchPipeline(backend=MyBackend(), sections=doc_sections)
    results = pipeline.search("revenue growth by segment", mode="auto")
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Protocol

from financial_synonyms import (
    SEARCH_SYNONYM_GROUPS,
    GENERIC_AMBIGUOUS_TOKENS,
    INTENT_KEYWORDS,
    NOISE_CONTEXT_TOKENS_BY_INTENT,
    SUPPORT_CONTEXT_TOKENS_BY_INTENT,
    TOKEN_STOP_WORDS,
    TOPIC_TO_BUCKET,
    BUCKET_KEYWORD_SIGNALS,
    EXPECTED_BUCKETS_BY_INTENT,
    SEARCH_MODE_AUTO,
    SEARCH_MODE_EXACT,
    SEARCH_MODE_KEYWORD,
    SEARCH_MODE_SEMANTIC,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_VALID_SEARCH_MODES: frozenset[str] = frozenset({
    SEARCH_MODE_AUTO, SEARCH_MODE_EXACT,
    SEARCH_MODE_KEYWORD, SEARCH_MODE_SEMANTIC,
})

_STRATEGY_EXACT: str = "exact"
_STRATEGY_PHRASE_VARIANT: str = "phrase_variant"
_STRATEGY_SYNONYM: str = "synonym"
_STRATEGY_TOKEN: str = "token"

_STRATEGY_PRIORITY: dict[str, int] = {
    _STRATEGY_EXACT: 0,
    _STRATEGY_PHRASE_VARIANT: 1,
    _STRATEGY_SYNONYM: 2,
    _STRATEGY_TOKEN: 3,
}

_WORD_SPLIT_RE = re.compile(r"[a-z0-9]+")
_SPACE_RE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryDiagnosis:
    """查询诊断结果。

    Args:
        query: 标准化查询文本。
        tokens: 查询 token 元组。
        ambiguity_score: 0~1 歧义度评分。
        is_high_ambiguity: 是否高歧义（≥0.62）。
        intent: 查询意图分类。
        allow_direct_token_fallback: 是否允许直接 token 回退。
    """

    query: str = ""
    tokens: tuple[str, ...] = ()
    ambiguity_score: float = 0.0
    is_high_ambiguity: bool = False
    intent: str = "general"
    allow_direct_token_fallback: bool = True


@dataclass(frozen=True)
class SectionProfile:
    """章节语义画像。

    Args:
        section_ref: 章节唯一标识。
        topic: 章节语义 topic。
        bucket: 归一化语义桶 (business/risk/financial/governance/people/legal/other)。
        lexical_tokens: 章节可检索 token 元组。
    """

    section_ref: str = ""
    topic: str = ""
    bucket: str = "other"
    lexical_tokens: tuple[str, ...] = ()


@dataclass
class SearchPlan:
    """自适应搜索执行计划。

    Args:
        run_exact: 是否执行精确匹配阶段。
        expansion_phases: 扩展阶段列表，每阶段包含多个 (query, strategy) 对。
        fallback_gated: 是否启用 token 回退门控。
    """

    run_exact: bool = True
    expansion_phases: tuple[tuple[dict[str, str], ...], ...] = ()
    fallback_gated: bool = False


@dataclass
class SearchResult:
    """单条搜索结果。

    Args:
        section_ref: 章节标识。
        section_title: 章节标题。
        page_no: 页码（可选）。
        snippet: 命中摘要。
        strategy: 命中策略（exact/phrase_variant/synonym/token）。
        priority: 策略优先级（越小越优先）。
        bm25f_score: BM25F 得分。
        intent_alignment: 意图一致性得分 (0~1)。
        noise_penalty: 噪声惩罚分。
        query: 产生该命中的查询词。
        evidence: 证据上下文（可选）。
    """

    section_ref: str = ""
    section_title: str = ""
    page_no: int | None = None
    snippet: str = ""
    strategy: str = _STRATEGY_EXACT
    priority: int = 0
    bm25f_score: float = 0.0
    intent_alignment: float = 0.0
    noise_penalty: float = 0.0
    query: str = ""
    evidence: dict[str, str] | None = None


@dataclass
class SearchOutcome:
    """搜索完整结果。

    Args:
        query: 原始查询。
        mode: 搜索模式。
        diagnosis: 查询诊断。
        results: 排序后的搜索结果列表。
        strategy_hit_counts: 各策略命中统计。
        expansion_queries: 实际执行的扩展查询。
    """

    query: str = ""
    mode: str = SEARCH_MODE_AUTO
    diagnosis: QueryDiagnosis = field(default_factory=QueryDiagnosis)
    results: list[SearchResult] = field(default_factory=list)
    strategy_hit_counts: dict[str, int] = field(default_factory=dict)
    expansion_queries: list[dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SearchBackend 协议 — 抽象搜索执行
# ---------------------------------------------------------------------------


class SearchBackend(Protocol):
    """搜索后端协议。

    使用者只需实现 ``search(query, within_ref)`` 方法，
    返回命中列表即可接入自适应搜索管线。
    """

    def search(
        self, query: str, within_ref: str | None = None
    ) -> list[dict[str, Any]]:
        """执行文本搜索。

        Args:
            query: 搜索查询字符串。
            within_ref: 可选章节范围（section ref）。

        Returns:
            命中列表，每项至少包含 ``section_ref``, ``snippet`` 字段。
        """
        ...


# ---------------------------------------------------------------------------
# SearchPipeline — 对外主入口
# ---------------------------------------------------------------------------


class SearchPipeline:
    """自适应搜索管线。

    封装完整的查询诊断 → 计划生成 → 扩展执行 → 排序流程。
    通过 ``SearchBackend`` 协议与具体搜索实现解耦。

    Args:
        backend: 搜索后端实现。
        sections: 文档章节摘要列表（用于语义画像和 BM25F）。
    """

    def __init__(
        self,
        backend: SearchBackend,
        sections: list[dict[str, Any]] | None = None,
    ) -> None:
        self._backend: SearchBackend = backend
        self._sections: list[dict[str, Any]] = sections or []
        self._profiles: dict[str, SectionProfile] = {}
        self._term_df: dict[str, int] = {}
        if self._sections:
            self._profiles, self._term_df = _build_section_profiles(self._sections)

    @property
    def section_count(self) -> int:
        """文档章节总数。"""
        return len(self._profiles)

    def search(
        self,
        query: str,
        *,
        mode: str = SEARCH_MODE_AUTO,
        within_ref: str | None = None,
    ) -> SearchOutcome:
        """执行自适应搜索。

        完整流程：诊断 → 计划 → 精确匹配 → 扩展 → 去重 → 排序。

        Args:
            query: 搜索查询字符串。
            mode: 搜索模式 (auto/exact/keyword/semantic)。
            within_ref: 可选章节范围。

        Returns:
            包含完整诊断和排序结果的 ``SearchOutcome``。
        """
        normalized_mode = _resolve_mode(mode)
        query_clean = " ".join(query.split())

        # 1) 诊断
        diagnosis = diagnose_query(
            query=query_clean,
            term_df=self._term_df,
            document_count=self.section_count,
            mode=normalized_mode,
        )

        # 2) 执行搜索
        ranked, hit_counts, expansions = _execute_search(
            backend=self._backend,
            query=query_clean,
            within_ref=within_ref,
            mode=normalized_mode,
            diagnosis=diagnosis,
            profiles=self._profiles,
        )

        # 3) 去重 + 排序
        deduped = _deduplicate(ranked)
        sorted_entries = _sort_entries(
            entries=deduped,
            diagnosis=diagnosis,
            profiles=self._profiles,
        )

        # 4) 构建结果
        results = [_entry_to_result(e) for e in sorted_entries]

        return SearchOutcome(
            query=query_clean,
            mode=normalized_mode,
            diagnosis=diagnosis,
            results=results,
            strategy_hit_counts=hit_counts,
            expansion_queries=expansions,
        )


# ===================================================================
# 纯函数算法（可独立使用）
# ===================================================================


def diagnose_query(
    *,
    query: str,
    term_df: dict[str, int],
    document_count: int,
    mode: str = SEARCH_MODE_AUTO,
) -> QueryDiagnosis:
    """诊断搜索查询的歧义度和意图。

    歧义度 = (通用token比例 + 文档频率饱和度 + 短查询惩罚) / 3
    ≥0.62 判定为高歧义。

    Args:
        query: 标准化查询词。
        term_df: 词项→文档频次映射。
        document_count: 文档章节总数。
        mode: 搜索模式。

    Returns:
        ``QueryDiagnosis`` 结构体。
    """
    tokens = tuple(_extract_tokens(query.lower()))
    if not tokens:
        return QueryDiagnosis(query=query)

    # 通用词比例
    generic_hits = sum(1 for t in tokens if t in GENERIC_AMBIGUOUS_TOKENS)
    generic_ratio = generic_hits / len(tokens)

    # 文档频率饱和度
    df_ratio = 0.0
    for t in tokens:
        tf = term_df.get(t, 0)
        if document_count > 0:
            df_ratio += min(1.0, tf / document_count)
    df_ratio = df_ratio / len(tokens)

    # 短查询惩罚
    short_factor = 1.0 if len(tokens) <= 2 else 0.0

    ambiguity = round((generic_ratio + df_ratio + short_factor) / 3.0, 4)
    is_high = ambiguity >= 0.62
    intent = classify_intent(tokens)
    allow_fallback = not (mode == SEARCH_MODE_AUTO and is_high)

    return QueryDiagnosis(
        query=query,
        tokens=tokens,
        ambiguity_score=ambiguity,
        is_high_ambiguity=is_high,
        intent=intent,
        allow_direct_token_fallback=allow_fallback,
    )


def classify_intent(tokens: tuple[str, ...]) -> str:
    """根据 token 分类查询意图。

    Args:
        tokens: 查询 token 元组。

    Returns:
        意图标签 (business_competition/financial/governance/people/risk/general)。
    """
    if not tokens:
        return "general"
    token_set = set(tokens)
    best, best_score = "general", 0
    for intent, keywords in INTENT_KEYWORDS.items():
        score = len(token_set & keywords)
        if score > best_score:
            best, best_score = intent, score
    return best


def expand_query(
    query: str, *, mode: str = SEARCH_MODE_AUTO
) -> list[dict[str, str]]:
    """为查询生成三层扩展：短语变体 → 同义词 → token 拆分。

    Args:
        query: 原始查询词。
        mode: 搜索模式（keyword 模式仅生成 token 拆分）。

    Returns:
        扩展查询列表，每项含 ``{"query": str, "strategy": str}``。
    """
    expansions: list[dict[str, str]] = []
    seen: set[str] = {_normalize_key(query)}

    if mode != SEARCH_MODE_KEYWORD:
        # 短语变体
        for variant in _build_phrase_variants(query):
            _add_expansion(expansions, seen, variant, _STRATEGY_PHRASE_VARIANT)
        # 同义词
        for syn in _build_synonyms(query):
            _add_expansion(expansions, seen, syn, _STRATEGY_SYNONYM)

    # Token 拆分
    for token_q in _build_token_queries(query):
        _add_expansion(expansions, seen, token_q, _STRATEGY_TOKEN)

    return expansions


# ===================================================================
# 内部实现
# ===================================================================


def _resolve_mode(mode: str | None) -> str:
    """校验并规范化搜索模式。"""
    if not mode:
        return SEARCH_MODE_AUTO
    m = mode.strip().lower()
    return m if m in _VALID_SEARCH_MODES else SEARCH_MODE_AUTO


def _normalize_key(query: str) -> str:
    """标准化查询词用于去重键。"""
    return _SPACE_RE.sub(" ", (query or "").strip().lower())


def _extract_tokens(text: str) -> list[str]:
    """提取 ASCII token。"""
    return _WORD_SPLIT_RE.findall(text or "")


def _add_expansion(
    expansions: list[dict[str, str]],
    seen: set[str],
    query: str,
    strategy: str,
) -> None:
    """向扩展列表添加去重后的查询项。"""
    key = _normalize_key(query)
    if key and key not in seen:
        seen.add(key)
        expansions.append({"query": query.strip(), "strategy": strategy})


def _build_phrase_variants(query: str) -> list[str]:
    """生成短语变体（连字符/斜杠替换 + 词形变化）。"""
    clean = " ".join(query.split())
    variants: set[str] = set()
    if "-" in clean:
        variants.add(clean.replace("-", " "))
    if "/" in clean:
        variants.add(clean.replace("/", " "))

    tokens = _extract_tokens(clean.lower())
    if tokens:
        for i, token in enumerate(tokens):
            for infl in _inflections(token):
                replaced = list(tokens)
                replaced[i] = infl
                variants.add(" ".join(replaced))

    base = _normalize_key(clean)
    return sorted(v for v in variants if _normalize_key(v) != base)


def _inflections(token: str) -> list[str]:
    """英文词形变体 (ies→y, es→, s↔)。"""
    t = token.strip().lower()
    result: set[str] = set()
    if len(t) < 3:
        return []
    if t.endswith("ies") and len(t) > 4:
        result.add(t[:-3] + "y")
    if t.endswith("es") and len(t) > 3:
        result.add(t[:-2])
    if t.endswith("s") and len(t) > 3:
        result.add(t[:-1])
    else:
        result.add(t + "s")
    result.discard(t)
    return sorted(result)


def _build_synonyms(query: str) -> list[str]:
    """从同义词组生成替换查询（按 token 匹配）。"""
    tokens = _extract_tokens(query.lower())
    if not tokens:
        return []
    synonyms: set[str] = set()
    for group in SEARCH_SYNONYM_GROUPS:
        group_keys = {_normalize_key(item): item for item in group}
        for token in tokens:
            if token in group_keys:
                for gk, gv in group_keys.items():
                    if gk != token:
                        # 替换单个 token
                        synonyms.add(query.lower().replace(token, gv))
    return sorted(synonyms)


def _build_token_queries(query: str) -> list[str]:
    """生成 token 级查询（≥3字符 + 去停用词）。"""
    tokens = _extract_tokens(query.lower())
    return [t for t in tokens if len(t) >= 3 and t not in TOKEN_STOP_WORDS]


def _build_section_profiles(
    sections: list[dict[str, Any]],
) -> tuple[dict[str, SectionProfile], dict[str, int]]:
    """构建章节语义画像与词项文档频次。

    Args:
        sections: 章节摘要列表（需含 ref/topic/path/title/item/preview）。

    Returns:
        ``(profiles, term_df)`` 元组。
    """
    profiles: dict[str, SectionProfile] = {}
    term_df: Counter[str] = Counter()
    for sec in sections:
        ref = str(sec.get("ref") or "").strip()
        if not ref:
            continue
        topic = str(sec.get("topic") or "").strip().lower()
        path = str(sec.get("path") or "").strip()
        title = str(sec.get("title") or "").strip()
        item = str(sec.get("item") or "").strip()
        bucket = _resolve_bucket(topic=topic, path=path, title=title, item=item)
        lexical = " ".join([title, item, topic, path]).lower()
        tokens = tuple(_extract_tokens(lexical))
        profiles[ref] = SectionProfile(
            section_ref=ref, topic=topic, bucket=bucket, lexical_tokens=tokens,
        )
        term_df.update(set(tokens))
    return profiles, dict(term_df)


def _resolve_bucket(
    *, topic: str, path: str, title: str, item: str
) -> str:
    """两级语义桶判定：topic直连 → 关键词评分fallback。"""
    # 一级：topic 直连
    bucket = TOPIC_TO_BUCKET.get(topic)
    if bucket:
        return bucket
    # 二级：关键词评分
    text = f"{path} {title} {item}".lower()
    words = frozenset(_WORD_SPLIT_RE.findall(text))
    best, best_score = "other", 0
    for candidate, keywords in BUCKET_KEYWORD_SIGNALS.items():
        score = len(words & keywords)
        if score > best_score:
            best, best_score = candidate, score
    return best


def _build_adaptive_plan(
    *, mode: str, diagnosis: QueryDiagnosis
) -> SearchPlan:
    """生成自适应搜索执行计划。"""
    if mode == SEARCH_MODE_EXACT:
        return SearchPlan(run_exact=True)

    expansions = expand_query(diagnosis.query, mode=mode)

    if mode == SEARCH_MODE_KEYWORD:
        return SearchPlan(
            run_exact=False,
            expansion_phases=(tuple(expansions),),
        )

    if mode == SEARCH_MODE_AUTO and diagnosis.is_high_ambiguity:
        non_token = [
            e for e in expansions
            if e.get("strategy") != _STRATEGY_TOKEN
        ]
        token_only = [
            e for e in expansions
            if e.get("strategy") == _STRATEGY_TOKEN
        ]
        phases: list[tuple[dict[str, str], ...]] = []
        if non_token:
            phases.append(tuple(non_token))
        if token_only:
            phases.append(tuple(token_only))
        return SearchPlan(
            run_exact=True,
            expansion_phases=tuple(phases),
            fallback_gated=True,
        )

    return SearchPlan(
        run_exact=(mode != SEARCH_MODE_SEMANTIC),
        expansion_phases=(tuple(expansions),),
    )


def _execute_search(
    *,
    backend: SearchBackend,
    query: str,
    within_ref: str | None,
    mode: str,
    diagnosis: QueryDiagnosis,
    profiles: dict[str, SectionProfile],
) -> tuple[
    list[dict[str, Any]], dict[str, int], list[dict[str, str]]
]:
    """执行搜索计划：精确匹配→扩展→意图过滤。"""
    hit_counts: dict[str, int] = {
        _STRATEGY_EXACT: 0,
        _STRATEGY_PHRASE_VARIANT: 0,
        _STRATEGY_SYNONYM: 0,
        _STRATEGY_TOKEN: 0,
    }
    ranked: list[dict[str, Any]] = []
    expansions_log: list[dict[str, str]] = []

    plan = _build_adaptive_plan(mode=mode, diagnosis=diagnosis)

    # 精确匹配
    if plan.run_exact:
        exact_raw = backend.search(
            query.replace('"', '').strip() or query,
            within_ref,
        )
        exact_matches = [m for m in exact_raw if m.get("section_ref")]
        if exact_matches:
            hit_counts[_STRATEGY_EXACT] = len(exact_matches)
            for m in exact_matches:
                m["_strategy"] = _STRATEGY_EXACT
                m["_priority"] = _STRATEGY_PRIORITY[_STRATEGY_EXACT]
                m["_query"] = query
            ranked.extend(exact_matches)

    # 扩展（仅在 auto 模式下无精确命中时执行）
    should_expand = bool(plan.expansion_phases) and (
        mode != SEARCH_MODE_AUTO or not ranked
    )
    if should_expand:
        for phase_idx, phase in enumerate(plan.expansion_phases):
            for expansion in phase:
                eq = expansion["query"]
                strat = expansion["strategy"]
                expansions_log.append({"query": eq, "strategy": strat})

                raw = backend.search(eq, within_ref)
                matches = [m for m in raw if m.get("section_ref")]
                if not matches:
                    continue

                # 意图过滤（高歧义 query 的 token 阶段）
                if diagnosis.intent != "general" and plan.fallback_gated:
                    token_phase = strat == _STRATEGY_TOKEN
                    strict = token_phase and phase_idx > 0
                    filtered = _filter_by_intent(matches, diagnosis, profiles)
                    if filtered:
                        matches = filtered
                    elif strict:
                        for m in matches:
                            m["_token_fallback_opened"] = True

                if not matches:
                    continue
                hit_counts[strat] = hit_counts.get(strat, 0) + len(matches)
                for m in matches:
                    m["_strategy"] = strat
                    m["_priority"] = _STRATEGY_PRIORITY.get(strat, 999)
                    m["_query"] = eq
                ranked.extend(matches)

    return ranked, hit_counts, expansions_log


def _filter_by_intent(
    matches: list[dict[str, Any]],
    diagnosis: QueryDiagnosis,
    profiles: dict[str, SectionProfile],
) -> list[dict[str, Any]]:
    """按查询意图过滤命中（只保留期望语义桶内的结果）。"""
    expected = EXPECTED_BUCKETS_BY_INTENT.get(diagnosis.intent)
    if not expected:
        return []
    result: list[dict[str, Any]] = []
    for m in matches:
        ref = str(m.get("section_ref") or "")
        profile = profiles.get(ref)
        if profile and profile.bucket in expected:
            result.append(m)
    return result


def _deduplicate(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按 (section_ref, snippet, page_no) 去重，保留高优先级。"""
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for e in entries:
        ref = str(e.get("section_ref") or "")
        snippet = str(e.get("snippet") or "")
        page = str(e.get("page_no") or "")
        key = (ref, snippet, page)
        cur = selected.get(key)
        if cur is None:
            selected[key] = e
        elif int(e.get("_priority", 999)) < int(cur.get("_priority", 999)):
            selected[key] = e
    return list(selected.values())


def _compute_noise_penalty(
    entry: dict[str, Any], diagnosis: QueryDiagnosis | None
) -> float:
    """计算上下文噪声惩罚分（意图不匹配时加分=排序靠后）。"""
    if diagnosis is None or diagnosis.intent == "general":
        return 0.0
    noise_tokens = NOISE_CONTEXT_TOKENS_BY_INTENT.get(diagnosis.intent)
    support_tokens = SUPPORT_CONTEXT_TOKENS_BY_INTENT.get(diagnosis.intent)
    if not noise_tokens:
        return 0.0

    snippet = str(entry.get("snippet") or "").lower()
    snippet_tokens = set(_WORD_SPLIT_RE.findall(snippet))
    noise_hits = len(snippet_tokens & noise_tokens)
    support_hits = len(snippet_tokens & (support_tokens or frozenset()))
    # 每噪声token +1.0，每支持token -0.3
    return max(0.0, noise_hits * 1.0 - support_hits * 0.3)


def _sort_entries(
    *,
    entries: list[dict[str, Any]],
    diagnosis: QueryDiagnosis | None = None,
    profiles: dict[str, SectionProfile] | None = None,
) -> list[dict[str, Any]]:
    """多轴排序：策略优先级 → 意图 → 噪声 → section → page → snippet。"""
    profiles = profiles or {}
    for item in entries:
        item["_intent_align"] = _compute_intent_align(item, diagnosis, profiles)
        item["_noise"] = _compute_noise_penalty(item, diagnosis)

    return sorted(
        entries,
        key=lambda item: (
            int(item.get("_priority", 999)),
            -float(item.get("_intent_align", 0.0)),
            float(item.get("_noise", 0.0)),
            str(item.get("section_ref") or ""),
            int(item.get("page_no") or 0),
            str(item.get("snippet") or ""),
        ),
    )


def _compute_intent_align(
    entry: dict[str, Any],
    diagnosis: QueryDiagnosis | None,
    profiles: dict[str, SectionProfile],
) -> float:
    """计算命中与查询意图的一致性得分 (0~1)。"""
    if diagnosis is None or diagnosis.intent == "general":
        return 0.0
    expected = EXPECTED_BUCKETS_BY_INTENT.get(diagnosis.intent)
    if not expected:
        return 0.0
    ref = str(entry.get("section_ref") or "")
    profile = profiles.get(ref)
    if profile and profile.bucket in expected:
        return 1.0
    return 0.0


def _entry_to_result(entry: dict[str, Any]) -> SearchResult:
    """将内部条目转为 SearchResult。"""
    return SearchResult(
        section_ref=str(entry.get("section_ref") or ""),
        section_title=str(entry.get("section_title") or ""),
        page_no=entry.get("page_no") if isinstance(entry.get("page_no"), int) else None,
        snippet=str(entry.get("snippet") or ""),
        strategy=str(entry.get("_strategy", "")),
        priority=int(entry.get("_priority", 999)),
        bm25f_score=float(entry.get("_bm25f_score", 0.0)),
        intent_alignment=float(entry.get("_intent_align", 0.0)),
        noise_penalty=float(entry.get("_noise", 0.0)),
        query=str(entry.get("_query", "")),
        evidence=entry.get("evidence") if isinstance(entry.get("evidence"), dict) else None,
    )
