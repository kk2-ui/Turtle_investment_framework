"""财务搜索同义词组与意图词表（从 Dayu search_models.py 提取）。

30+ 组中英双语财务术语同义词，覆盖：
- 财务指标（收入、利润、现金流、负债、权益）
- 竞争分析（竞争对手、市场份额、护城河）
- 公司治理（董事会、高管薪酬、合规）
- 风险（不确定性、诉讼、网络安全）
- 研发、供应链、并购、股息

同时提供查询意图分类关键词和噪声/支持上下文词表。

零外部依赖（纯 Python 内置数据结构），可直接用于 Turtle Phase 3
中对年报关键词搜索和意图分类。

Usage::

    from scripts.financial_synonyms import (
        SEARCH_SYNONYM_GROUPS, INTENT_KEYWORDS, expand_query_synonyms,
    )

    # 扩展同义词
    expanded = expand_query_synonyms("revenue growth")
    # → ["revenue growth", "sales growth", "营业收入 growth", ...]

    # 分类查询意图
    from scripts.financial_synonyms import classify_query_intent
    intent = classify_query_intent(["revenue", "margin", "profit"])
    # → "financial"
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 搜索模式常量
# ---------------------------------------------------------------------------

SEARCH_MODE_AUTO: str = "auto"
SEARCH_MODE_EXACT: str = "exact"
SEARCH_MODE_KEYWORD: str = "keyword"
SEARCH_MODE_SEMANTIC: str = "semantic"

# ---------------------------------------------------------------------------
# Token 停用词 (英文)
# ---------------------------------------------------------------------------

TOKEN_STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "from", "into",
    "about", "this", "that", "have", "has", "had",
    "are", "was", "were", "or", "but",
})

# ---------------------------------------------------------------------------
# 同义词组（30+ 组，中英双语）
# ---------------------------------------------------------------------------

SEARCH_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    # ── 财务核心指标 ──
    ("revenue", "revenues", "sales", "营业收入", "營業收入"),
    ("net income", "net profit", "净利润", "淨利潤"),
    ("cash flow", "现金流", "現金流"),
    ("profit", "profitability", "margin", "earnings"),
    ("operating income", "operating profit", "ebit"),
    ("debt", "borrowing", "leverage", "liabilities"),
    ("equity", "shareholders equity", "stockholders equity"),
    # ── 风险 ──
    ("risk", "risks", "risk factors", "风险", "風險"),
    # ── 前瞻指引 ──
    ("guidance", "outlook", "指引", "展望"),
    # ── 资本运作 ──
    ("share repurchase", "repurchase", "buyback", "回购", "回購"),
    ("dividend", "dividends", "distribution", "payout"),
    ("acquisition", "merger", "deal", "buyout", "takeover"),
    # ── 公司治理 ──
    ("board of directors", "board", "董事会", "董事會"),
    ("management", "executive officers", "管理层", "管理層"),
    ("legal proceedings", "litigation", "诉讼", "訴訟"),
    ("regulation", "regulatory", "compliance"),
    # ── 竞争与市场 ──
    ("compete", "competition", "competitor", "competitive", "competitiveness"),
    ("market share", "market position", "market penetration"),
    ("monopoly", "dominant position", "market dominance"),
    # ── 产品与服务 ──
    ("product", "offering", "solution", "service", "platform"),
    # ── 威胁与挑战 ──
    ("threat", "headwind", "challenge", "pressure"),
    # ── 知识产权 ──
    ("intellectual property", "patent", "proprietary"),
    # ── 供应链 ──
    ("supply chain", "sourcing", "procurement", "vendor", "supplier"),
    # ── 客户留存 ──
    ("customer retention", "churn", "loyalty"),
    # ── 研发 ──
    ("research and development", "r&d", "innovation"),
)

# ---------------------------------------------------------------------------
# 高歧义 token（在财报语境下容易匹配过多无关段落）
# ---------------------------------------------------------------------------

GENERIC_AMBIGUOUS_TOKENS: frozenset[str] = frozenset({
    "competition", "competitor", "competitive",
    "market", "business", "strategy", "policy",
    "growth", "performance", "management",
    "risk", "compliance",
})

# ---------------------------------------------------------------------------
# 查询意图分类关键词
# ---------------------------------------------------------------------------

INTENT_KEYWORDS: dict[str, frozenset[str]] = {
    "business_competition": frozenset({
        "competitor", "competition", "competitive",
        "market", "marketshare", "share",
        "customer", "industry", "peer",
        "supplier", "product", "service",
        "lithography", "semiconductor",
    }),
    "financial": frozenset({
        "revenue", "income", "earnings", "cash",
        "margin", "asset", "liability", "equity",
        "guidance", "profit",
    }),
    "governance": frozenset({
        "board", "director", "governance",
        "compensation", "executive", "committee",
        "ethics", "compliance", "anti", "bribery",
    }),
    "people": frozenset({
        "employee", "talent", "hiring", "students",
        "competition", "league", "recruit",
        "workforce", "training", "employer",
    }),
    "risk": frozenset({
        "risk", "threat", "uncertainty", "vulnerability",
        "cybersecurity", "litigation", "exposure",
    }),
}

# ---------------------------------------------------------------------------
# 意图噪声/支持上下文词表
# ---------------------------------------------------------------------------

NOISE_CONTEXT_TOKENS_BY_INTENT: dict[str, frozenset[str]] = {
    "business_competition": frozenset({
        "antitrust", "compliance", "ethics",
        "students", "league", "robotics",
        "employer", "universum", "human", "rights",
    }),
}

SUPPORT_CONTEXT_TOKENS_BY_INTENT: dict[str, frozenset[str]] = {
    "business_competition": frozenset({
        "market", "industry", "customer", "supplier",
        "peer", "product", "service", "technology",
        "lithography", "semiconductor",
    }),
}

# ---------------------------------------------------------------------------
# Semantic bucket → topic 映射（Topic → Bucket）
# ---------------------------------------------------------------------------

TOPIC_TO_BUCKET: dict[str, str] = {
    "business": "business",
    "company_information": "business",
    "properties": "business",
    "operating_review": "business",
    "risk_factors": "risk",
    "market_risk": "risk",
    "cybersecurity": "risk",
    "mda": "financial",
    "financial_statements": "financial",
    "financial_information": "financial",
    "selected_financial_data": "financial",
    "quantitative_disclosures": "financial",
    "key_information": "financial",
    "market_for_equity": "financial",
    "directors": "governance",
    "governance": "governance",
    "executive_compensation": "governance",
    "security_ownership": "governance",
    "certain_relationships": "governance",
    "principal_accountant": "governance",
    "controls_procedures": "governance",
    "directors_employees": "people",
    "legal_proceedings": "legal",
    "exhibits": "other",
    "signature": "other",
    "mine_safety": "other",
    "other_information": "other",
    "unresolved_staff_comments": "other",
    "offer_listing": "other",
    "additional_information": "other",
    "securities_description": "other",
    "defaults_arrearages": "other",
    "material_modifications": "other",
    "changes_disagreements": "other",
    "major_shareholders": "governance",
}

# ── Bucket 关键词信号（fallback topic 分类）──

BUCKET_KEYWORD_SIGNALS: dict[str, frozenset[str]] = {
    "business": frozenset({
        "business", "operating", "market", "product", "service",
        "customer", "industry", "company", "overview", "operations",
    }),
    "risk": frozenset({
        "risk", "risks", "threat", "uncertainty", "cybersecurity",
    }),
    "financial": frozenset({
        "financial", "income", "revenue", "earnings", "assets",
        "liabilities", "equity", "cash", "mda", "discussion",
        "analysis", "quantitative",
    }),
    "governance": frozenset({
        "governance", "director", "directors", "compensation",
        "committee", "board", "audit", "shareholder", "ethics",
    }),
    "people": frozenset({
        "employee", "employees", "workforce", "personnel",
        "staff", "talent", "headcount",
    }),
    "legal": frozenset({
        "legal", "proceeding", "proceedings", "litigation",
        "lawsuit", "compliance",
    }),
}

# ── Intent → 期望 Bucket 集合 ──

EXPECTED_BUCKETS_BY_INTENT: dict[str, frozenset[str]] = {
    "business_competition": frozenset({"business", "risk", "financial"}),
    "financial": frozenset({"financial", "business"}),
    "governance": frozenset({"governance", "legal", "people"}),
    "people": frozenset({"people", "governance"}),
    "risk": frozenset({"risk", "legal", "business"}),
}

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def expand_query_synonyms(query: str) -> list[str]:
    """为查询文本生成同义词变体。

    对查询中的每个 token，查找匹配的同义词组，生成替换变体。
    原始查询始终排在第一位。

    Args:
        query: 原始查询文本（小写，已归一化）。

    Returns:
        含原始查询和所有同义词变体的列表。
    """
    results: list[str] = [query]
    tokens = query.lower().split()
    for group in SEARCH_SYNONYM_GROUPS:
        for token in tokens:
            if token in group:
                for synonym in group:
                    if synonym != token:
                        results.append(query.replace(token, synonym))
                break
    return results


def classify_query_intent(tokens: list[str]) -> str:
    """根据 token 列表分类查询意图。

    对各意图关键词集合做交集计数，返回得分最高的意图。

    Args:
        tokens: 小写 token 列表。

    Returns:
        意图标签（``"business_competition"`` / ``"financial"`` /
        ``"governance"`` / ``"people"`` / ``"risk"`` / ``"general"``）。
    """
    token_set = frozenset(tokens)
    best_intent = "general"
    best_score = 0
    for intent, keywords in INTENT_KEYWORDS.items():
        score = len(token_set & keywords)
        if score > best_score:
            best_score = score
            best_intent = intent
    return best_intent
