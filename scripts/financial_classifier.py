"""财务报表类型分类器（从 Dayu financial_enhancer.py 提取）。

核心能力：不依赖 XBRL，仅从表格 caption/header/body 文本推断
该表是资产负债表、利润表还是现金流量表。

零外部依赖（仅 re + unicodedata），可直接用于 Turtle Phase 2
中从 PDF/HTML 表格识别三大表。

Usage::

    from scripts.financial_classifier import classify_table_text, is_financial_table

    # 判断是否为财务表
    if is_financial_table(caption="资产负债表", headers=["2023", "2024"], context=""):
        ...

    # 推断具体财务报表类型
    body_text = "流动资产 100 非流动资产 200 资产总计 300 ..."
    labels = match_statement_labels(body_text)
    # → ["资产负债表"]
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# 文本归一化（替代 Dayu text_utils 依赖）
# ---------------------------------------------------------------------------

_WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_whitespace(text: str) -> str:
    """将连续空白归一化为单个空格，去除首尾空白。

    Args:
        text: 原始文本。

    Returns:
        空白归一化后的文本。
    """
    return _WHITESPACE_PATTERN.sub(" ", (text or "").replace("　", " ")).strip()


def _normalize_optional_string(value: str | None) -> str | None:
    """归一化可选字符串，空串视为 None。

    Args:
        value: 可能为 None 的字符串。

    Returns:
        归一化后非空字符串，或 None。
    """
    if value is None:
        return None
    v = _normalize_whitespace(value)
    return v if v else None


# ---------------------------------------------------------------------------
# 财务关键词库
# ---------------------------------------------------------------------------

_FINANCIAL_KEYWORDS: tuple[str, ...] = (
    "balance sheet",
    "income statement",
    "cash flow",
    "statement of operations",
    "statement of cash flows",
    "financial position",
    "financial results",
    "total assets",
    "total liabilities",
    "net income",
    "net earnings",
    "revenue",
    "revenues",
    "earnings",
    "profit",
    "loss",
    "资产负债表",
    "利润表",
    "现金流量表",
    "現金流量表",
    "财务状况表",
    "財務狀況表",
    "財務狀況報表",
    "主要财务数据",
    "主要財務數據",
    "主要財務資料",
    "综合收益",
    "綜合收益",
    "营业收入",
    "營業收入",
    "净利润",
    "淨利潤",
)

# ---------------------------------------------------------------------------
# 四大财务报表证据组 (label, keywords_tuple, min_hits)
# ---------------------------------------------------------------------------

_FINANCIAL_STATEMENT_EVIDENCE_GROUPS: tuple[
    tuple[str, tuple[str, ...], int], ...
] = (
    (
        "利润表",
        (
            # ── 简体中文 ──
            "营业收入", "营业利润", "利润总额", "净利润", "净亏损",
            "综合收益总额", "总收入", "总销售成本", "销售成本",
            "毛利", "毛亏损", "经营开支", "经营亏损",
            "销售费用", "行政费用", "除所得税", "税后利润",
            "利息收入", "利息支出", "净利息收入", "手续费及佣金收入",
            # ── 繁体中文 ──
            "營業收入", "營業利潤", "利潤總額", "淨利潤", "淨虧損",
            "綜合收益總額", "總收入", "總銷售成本", "銷售成本",
            "毛虧損", "毛 （虧損） 溢利",
            "經營開支", "經營開⽀", "經營虧損",
            "銷售費用", "銷售費⽤", "分銷及銷售費用",
            "行政費用", "行政費⽤",
            "除所得稅", "稅後利潤",
            "利息支出", "利息⽀出", "淨利息收入",
            "手續費及佣金收入",
            "綜合虧損總額",
            "保險收益", "保險服務開支", "保險服務開⽀", "保險服務業績",
            "投資回報", "投資業績淨額",
            "稅後營運溢利", "純利",
        ),
        3,  # min_hits: ≥3 个关键词命中 → 判定为利润表
    ),
    (
        "资产负债表",
        (
            # ── 简体中文 ──
            "流动资产", "非流动资产", "资产总计", "资产总额", "资产总值",
            "流动负债", "非流动负债", "负债合计", "权益及负债",
            "所有者权益", "股东权益",
            "归属于母公司股东权益", "归属于上市公司股东的所有者权益",
            "负债和股东权益", "负债及股东权益",
            "现金及存放中央银行款项", "发放贷款和垫款",
            "客户贷款及垫款", "客户贷款和垫款",
            "吸收存款", "客户存款",
            # ── 繁体中文 ──
            "流動資產", "非流動資產", "資產總計", "資產總額", "資產總值",
            "流動負債", "非流動負債", "負債合計",
            "權益及負債", "所有者權益", "股東權益",
            "本公司權益持有人應佔權益",
            "負債總額", "總資產", "總權益", "權益總額", "權益及負債總額",
            "基金單位持有人應佔資產淨值", "非控制性權益",
            "負債和股東權益", "負債及股東權益",
            "現金及存放中央銀行款項", "發放貸款和墊款",
            "客戶貸款及墊款", "客戶貸款和墊款",
            "吸收存款", "客戶存款",
        ),
        4,  # min_hits: ≥4 个关键词命中 → 判定为资产负债表
    ),
    (
        "现金流量表",
        (
            # ── 简体中文 ──
            "经营活动产生的现金流量", "经营活动现金流量",
            "经营活动现金流入", "经营活动现金流出",
            "投资活动产生的现金流量", "投资活动现金流量",
            "筹资活动产生的现金流量", "筹资活动现金流量",
            "现金及现金等价物",
            # ── 繁体中文（HG/CN 多种变体，来自实际披露文档）──
            "經營活動產生的現金流量",
            "經營活動產生╱ （使用） 的現金流量",
            "經營活動產生╱（使用）的現金流量",
            "經營活動現金流量",
            "經營活動所得現金流量", "經營活動所得現金流量淨額",
            "經營活動產生的現金流量淨額",
            "經營業務之現金流量", "營運活動所得之現金",
            "經營活動現金流入", "經營活動現金流出",
            "投資活動產生的現金流量",
            "投資活動 （使用） ╱產生的現金流量",
            "投資活動（使用）╱產生的現金流量",
            "投資活動 （使用） ╱產生的現金流量淨額",
            "投資活動（使用）╱產生的現金流量淨額",
            "投資活動現金流量", "投資活動所用現金流量",
            "投資業務之現金流量",
            "籌資活動產生的現金流量", "籌資活動現金流量",
            "融資活動產生的現金流量", "融資活動產生的現金流量淨額",
            "融資活動現金流量", "融資活動所用現金流量",
            "現金及現金等價物增加", "現金及現金等價物減少",
            "現金及現金等價物",
            "主要業務活動之現金流量", "主要業務活動之現金流入淨額",
            "業務活動之現金流入淨額",
            "營業活動產生之現金淨額", "營業活動產生的現金淨額",
            "營業活動產生之現金净额",
            "投資活動之現金流量",
            "投資活動產生之現金淨額", "投資活動產生的現金淨額",
            "投資活動產生之現金净额",
            "財務活動之現金流量",
            "融資活動產生之現金淨額", "融資活動產生的現金淨額",
            "融資活動產生之現金净额",
            "現金流動",
        ),
        2,  # min_hits: ≥2 个关键词命中 → 判定为现金流量表
    ),
    (
        "主要财务数据",
        (
            # ── 简体中文 ──
            "营业收入", "收入", "收益", "EBITDA",
            "股东应占溢利", "普通股股东应占", "汽车销售收入",
            "毛利率", "净收益", "净亏损", "期内利润",
            "经调整利润净额", "经调整 EBITDA", "基本每股盈利",
            "資本開支", "除税前利润", "除税后利润", "净利润",
            "期内盈利", "本公司权益持有人应占盈利",
            "归属于上市公司股东", "归属于本行股东", "归属于",
            "每股收益", "每股盈利", "基本每股收益", "基本和稀释每股收益",
            "资产总额", "总资产",
            "经营活动产生的现金流量净额", "经营活动的现金流量净额",
            "现金流量净额", "加权平均净资产收益率",
            "年化加权平均净资产收益率",
            # ── 繁体中文 ──
            "營業收入", "收入及其他收益", "主要業務收入",
            "經營收入", "股東應佔溢利", "股東應佔盈利",
            "普通股股東應佔", "汽車銷售收入", "淨收益", "淨虧損",
            "期內利潤", "經調整利潤淨額", "經調整 EBITDA",
            "基本每股盈利", "資本開支",
            "除稅前利潤", "除稅後利潤", "淨利潤",
            "期內盈利", "本公司權益持有人應佔盈利",
            "歸屬於本行股東", "歸屬於",
            "每股收益", "每股盈利",
            "基本每股收益", "基本和稀释每股收益",
            "資產總額", "總資產",
            "經營活動產生的現金流量淨額",
            "經營活動產生的現金流 量淨額",
            "現金流 量淨額",
            "加权平均净资产收益率",
            "年化加權平均淨資產收益率",
        ),
        4,  # min_hits: ≥4 个关键词命中 → 判定为主要财务数据
    ),
)

_MAX_TABLE_BODY_EVIDENCE_CHARS: int = 6000


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def is_financial_table(
    caption: str | None,
    headers: list[str] | None,
    context_before: str = "",
) -> bool:
    """判断表格是否为财务表。

    将表格标题、表头和前文合并归一化后，匹配 60+ 中英双语财务关键词。

    Args:
        caption: 表格标题。
        headers: 表头列表。
        context_before: 表格前文（如段落文本）。

    Returns:
        命中金融关键词时返回 ``True``，否则返回 ``False``。
    """
    parts: list[str] = [str(caption or ""), str(context_before or "")]
    if headers:
        parts.extend(str(item or "") for item in headers)
    normalized_text = _normalize_whitespace(" ".join(parts)).lower()
    if not normalized_text:
        return False
    return any(keyword in normalized_text for keyword in _FINANCIAL_KEYWORDS)


def match_statement_labels(text: str) -> list[str]:
    """根据表体文本匹配三大财报标签。

    从表体文本（如表格 markdown 或 dataframe 导出）中统计
    四组证据关键词的命中数，达到阈值即判定为对应报表类型。

    Args:
        text: 表体文本（最多保留前 ``6000`` 字符）。

    Returns:
        命中的财报表标签列表（如 ``["资产负债表", "利润表"]``）。
    """
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return []
    labels: list[str] = []
    for label, keywords, minimum_hits in _FINANCIAL_STATEMENT_EVIDENCE_GROUPS:
        hit_count = sum(
            1
            for keyword in keywords
            if _normalize_for_match(keyword) in normalized_text
        )
        if hit_count >= minimum_hits:
            labels.append(label)
    return labels


def classify_table_text(
    text: str,
    *,
    caption: str | None = None,
    headers: list[str] | None = None,
    context_before: str = "",
) -> dict[str, object]:
    """综合分类表格文本，返回完整的分类结果。

    组合 ``is_financial_table`` 和 ``match_statement_labels``，
    提供一站式表格金融语义分类。

    Args:
        text: 表体文本（如从 PDF/HTML 表格提取的文本）。
        caption: 可选表格标题。
        headers: 可选表头列表。
        context_before: 可选表格前文。

    Returns:
        ``{"is_financial": bool, "statement_labels": list[str]}``。
    """
    is_fin = is_financial_table(
        caption=caption, headers=headers, context_before=context_before
    )
    labels = match_statement_labels(text) if is_fin else []
    return {"is_financial": is_fin, "statement_labels": labels}


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _normalize_for_match(text: str) -> str:
    """归一化用于金融语义匹配的文本。

    NFKC 正规化 + 空白归一化 + 大小写折叠。

    Args:
        text: 原始文本。

    Returns:
        归一化后的文本。
    """
    return _normalize_whitespace(
        unicodedata.normalize("NFKC", str(text or ""))
    ).casefold()
