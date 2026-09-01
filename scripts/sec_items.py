"""SEC Filing Item 语义映射表（从 Dayu section_semantic.py 提取）。

覆盖 SEC 三大表单的 Item 编号到语义类型的完整映射：
- 10-K (Annual Report) — 15 个 Items
- 10-Q (Quarterly Report) — Part I + Part II 各 4-6 个 Items
- 20-F (Foreign Private Issuer Annual Report) — 19 个 Items

可提取 Item 编号、解析章节语义、构建层级路径。

零外部依赖（仅 re），可直接用于美股 10-K/10-Q/20-F 年报的章节导航。

Usage::

    from scripts.sec_items import extract_item_number, resolve_section_semantic

    item = extract_item_number("Item 1A. Risk Factors")  # → "1A"

    item_no, title, topic = resolve_section_semantic(
        title="Item 7. MD&A", form_type="10-K"
    )
    # → ("7", "Management's Discussion and Analysis", "mda")
"""

from __future__ import annotations

import re
from enum import Enum

# ---------------------------------------------------------------------------
# SectionType 枚举（内联替代 Dayu domain.tool_models.SectionType）
# ---------------------------------------------------------------------------


class SectionType(str, Enum):
    """SEC 章节语义类型。"""

    BUSINESS = "business"
    RISK_FACTORS = "risk_factors"
    UNRESOLVED_STAFF_COMMENTS = "unresolved_staff_comments"
    CYBERSECURITY = "cybersecurity"
    PROPERTIES = "properties"
    LEGAL_PROCEEDINGS = "legal_proceedings"
    MINE_SAFETY = "mine_safety"
    MARKET_FOR_EQUITY = "market_for_equity"
    SELECTED_FINANCIAL_DATA = "selected_financial_data"
    MDA = "mda"
    QUANTITATIVE_DISCLOSURES = "quantitative_disclosures"
    FINANCIAL_STATEMENTS = "financial_statements"
    FINANCIAL_INFORMATION = "financial_information"
    CHANGES_DISAGREEMENTS = "changes_disagreements"
    CONTROLS_PROCEDURES = "controls_procedures"
    OTHER_INFORMATION = "other_information"
    DIRECTORS = "directors"
    DIRECTORS_EMPLOYEES = "directors_employees"
    EXECUTIVE_COMPENSATION = "executive_compensation"
    SECURITY_OWNERSHIP = "security_ownership"
    CERTAIN_RELATIONSHIPS = "certain_relationships"
    PRINCIPAL_ACCOUNTANT = "principal_accountant"
    EXHIBITS = "exhibits"
    KEY_INFORMATION = "key_information"
    COMPANY_INFORMATION = "company_information"
    OPERATING_REVIEW = "operating_review"
    OFFER_LISTING = "offer_listing"
    ADDITIONAL_INFORMATION = "additional_information"
    MARKET_RISK = "market_risk"
    SECURITIES_DESCRIPTION = "securities_description"
    DEFAULTS_ARREARAGES = "defaults_arrearages"
    MATERIAL_MODIFICATIONS = "material_modifications"
    GOVERNANCE = "governance"
    MAJOR_SHAREHOLDERS = "major_shareholders"
    SIGNATURE = "signature"


# ---------------------------------------------------------------------------
# Item 编号提取正则
# ---------------------------------------------------------------------------
# 匹配 "Item 1A. Risk Factors"、"ITEM 7A — Quantitative..."、
# "Part I - Item 1A" 等格式

_ITEM_NUMBER_PATTERN = re.compile(
    r"(?i)\bitem\s+(16[A-J]|[1-9][0-9]?[A-C]?)\b"
)

# ---------------------------------------------------------------------------
# 10-K Item → (canonical_title, SectionType)
# 参考 SEC Form 10-K, Regulation S-K
# ---------------------------------------------------------------------------

TEN_K_ITEM_MAP: dict[str, tuple[str, SectionType]] = {
    "1": ("Business", SectionType.BUSINESS),
    "1A": ("Risk Factors", SectionType.RISK_FACTORS),
    "1B": ("Unresolved Staff Comments", SectionType.UNRESOLVED_STAFF_COMMENTS),
    "1C": ("Cybersecurity", SectionType.CYBERSECURITY),
    "2": ("Properties", SectionType.PROPERTIES),
    "3": ("Legal Proceedings", SectionType.LEGAL_PROCEEDINGS),
    "4": ("Mine Safety Disclosures", SectionType.MINE_SAFETY),
    "5": ("Market for Registrant's Common Equity", SectionType.MARKET_FOR_EQUITY),
    "6": ("[Reserved]", SectionType.SELECTED_FINANCIAL_DATA),
    "7": ("Management's Discussion and Analysis", SectionType.MDA),
    "7A": (
        "Quantitative and Qualitative Disclosures About Market Risk",
        SectionType.QUANTITATIVE_DISCLOSURES,
    ),
    "8": (
        "Financial Statements and Supplementary Data",
        SectionType.FINANCIAL_STATEMENTS,
    ),
    "9": (
        "Changes in and Disagreements With Accountants",
        SectionType.CHANGES_DISAGREEMENTS,
    ),
    "9A": ("Controls and Procedures", SectionType.CONTROLS_PROCEDURES),
    "9B": ("Other Information", SectionType.OTHER_INFORMATION),
    "9C": (
        "Disclosure Regarding Foreign Jurisdictions",
        SectionType.OTHER_INFORMATION,
    ),
    "10": (
        "Directors, Executive Officers and Corporate Governance",
        SectionType.DIRECTORS,
    ),
    "11": ("Executive Compensation", SectionType.EXECUTIVE_COMPENSATION),
    "12": (
        "Security Ownership of Certain Beneficial Owners",
        SectionType.SECURITY_OWNERSHIP,
    ),
    "13": (
        "Certain Relationships and Related Transactions",
        SectionType.CERTAIN_RELATIONSHIPS,
    ),
    "14": (
        "Principal Accountant Fees and Services",
        SectionType.PRINCIPAL_ACCOUNTANT,
    ),
    "15": (
        "Exhibits and Financial Statement Schedules",
        SectionType.EXHIBITS,
    ),
}

# 10-K Part → Item 范围
TEN_K_PART_MAP: dict[str, str] = {
    "1": "I", "1A": "I", "1B": "I", "1C": "I",
    "2": "I", "3": "I", "4": "I",
    "5": "II", "6": "II", "7": "II", "7A": "II",
    "8": "II", "9": "II", "9A": "II", "9B": "II", "9C": "II",
    "10": "III", "11": "III", "12": "III", "13": "III", "14": "III",
    "15": "IV",
}

# ---------------------------------------------------------------------------
# 10-Q Item → SectionType
# 注意：Part I 和 Part II 的 Item 编号有重叠，需通过 parent_title 消歧
# ---------------------------------------------------------------------------

TEN_Q_PART_I_ITEM_MAP: dict[str, tuple[str, SectionType]] = {
    "1": ("Financial Statements", SectionType.FINANCIAL_STATEMENTS),
    "2": ("Management's Discussion and Analysis", SectionType.MDA),
    "3": (
        "Quantitative and Qualitative Disclosures About Market Risk",
        SectionType.QUANTITATIVE_DISCLOSURES,
    ),
    "4": ("Controls and Procedures", SectionType.CONTROLS_PROCEDURES),
}

TEN_Q_PART_II_ITEM_MAP: dict[str, tuple[str, SectionType]] = {
    "1": ("Legal Proceedings", SectionType.LEGAL_PROCEEDINGS),
    "1A": ("Risk Factors", SectionType.RISK_FACTORS),
    "2": (
        "Unregistered Sales of Equity Securities",
        SectionType.OTHER_INFORMATION,
    ),
    "3": ("Defaults Upon Senior Securities", SectionType.OTHER_INFORMATION),
    "4": ("Mine Safety Disclosures", SectionType.MINE_SAFETY),
    "5": ("Other Information", SectionType.OTHER_INFORMATION),
    "6": ("Exhibits", SectionType.EXHIBITS),
}

# ---------------------------------------------------------------------------
# 20-F Item → SectionType
# 参考 SEC Form 20-F General Instructions
# ---------------------------------------------------------------------------

TWENTY_F_ITEM_MAP: dict[str, tuple[str, SectionType]] = {
    "1": (
        "Identity of Directors, Senior Management and Advisers",
        SectionType.DIRECTORS,
    ),
    "2": ("Offer Statistics and Expected Timetable", SectionType.OFFER_LISTING),
    "3": ("Key Information", SectionType.KEY_INFORMATION),
    "4": ("Information on the Company", SectionType.COMPANY_INFORMATION),
    "4A": ("Unresolved Staff Comments", SectionType.UNRESOLVED_STAFF_COMMENTS),
    "5": (
        "Operating and Financial Review and Prospects",
        SectionType.OPERATING_REVIEW,
    ),
    "6": (
        "Directors, Senior Management and Employees",
        SectionType.DIRECTORS_EMPLOYEES,
    ),
    "7": (
        "Major Shareholders and Related Party Transactions",
        SectionType.MAJOR_SHAREHOLDERS,
    ),
    "8": ("Financial Information", SectionType.FINANCIAL_INFORMATION),
    "9": ("The Offer and Listing", SectionType.OFFER_LISTING),
    "10": ("Additional Information", SectionType.ADDITIONAL_INFORMATION),
    "11": (
        "Quantitative and Qualitative Disclosures About Market Risk",
        SectionType.MARKET_RISK,
    ),
    "12": (
        "Description of Securities Other Than Equity Securities",
        SectionType.SECURITIES_DESCRIPTION,
    ),
    "13": (
        "Defaults, Dividend Arrearages and Delinquencies",
        SectionType.DEFAULTS_ARREARAGES,
    ),
    "14": (
        "Material Modifications to the Rights of Security Holders",
        SectionType.MATERIAL_MODIFICATIONS,
    ),
    "15": ("Controls and Procedures", SectionType.CONTROLS_PROCEDURES),
    "16A": ("Audit Committee Financial Expert", SectionType.GOVERNANCE),
    "16B": ("Code of Ethics", SectionType.GOVERNANCE),
    "16C": (
        "Principal Accountant Fees and Services",
        SectionType.GOVERNANCE,
    ),
    "16D": (
        "Exemptions from the Listing Standards for Audit Committees",
        SectionType.GOVERNANCE,
    ),
    "16E": (
        "Purchases of Equity Securities by the Issuer",
        SectionType.GOVERNANCE,
    ),
    "16F": (
        "Change in Registrant's Certifying Accountant",
        SectionType.GOVERNANCE,
    ),
    "16G": ("Corporate Governance", SectionType.GOVERNANCE),
    "16H": ("Mine Safety Disclosure", SectionType.GOVERNANCE),
    "16I": (
        "Disclosure Regarding Foreign Jurisdictions",
        SectionType.GOVERNANCE,
    ),
    "16J": ("Insider Trading Policies", SectionType.GOVERNANCE),
    "17": ("Financial Statements", SectionType.FINANCIAL_STATEMENTS),
    "18": ("Financial Statements", SectionType.FINANCIAL_STATEMENTS),
    "19": ("Exhibits", SectionType.EXHIBITS),
}

TWENTY_F_PART_MAP: dict[str, str] = {
    "1": "I", "2": "I", "3": "I", "4": "I", "4A": "I",
    "5": "II", "6": "II", "7": "II", "8": "II",
    "9": "II", "10": "II", "11": "II", "12": "II",
    "13": "III", "14": "III", "15": "III", "16": "III",
    "16A": "III", "16B": "III", "16C": "III", "16D": "III",
    "16E": "III", "16F": "III", "16G": "III", "16H": "III",
    "16I": "III", "16J": "III",
    "17": "IV", "18": "IV", "19": "IV",
}

# form_type → item_map 路由
_FORM_ITEM_MAPS: dict[str, dict[str, tuple[str, SectionType]]] = {
    "10-K": TEN_K_ITEM_MAP,
    "10-K/A": TEN_K_ITEM_MAP,
    "20-F": TWENTY_F_ITEM_MAP,
    "20-F/A": TWENTY_F_ITEM_MAP,
}

_FORM_PART_MAPS: dict[str, dict[str, str]] = {
    "10-K": TEN_K_PART_MAP,
    "10-K/A": TEN_K_PART_MAP,
    "20-F": TWENTY_F_PART_MAP,
    "20-F/A": TWENTY_F_PART_MAP,
}

# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def extract_item_number(title: str | None) -> str | None:
    """从章节标题中提取 SEC Item 编号。

    支持 "Item 1A. Risk Factors"、"ITEM 7A — Quantitative..."、
    "Part I - Item 1A" 等格式。

    Args:
        title: 章节标题文本。

    Returns:
        Item 编号字符串（如 ``"1A"``），无法提取时返回 ``None``。
    """
    if not title:
        return None
    m = _ITEM_NUMBER_PATTERN.search(title.strip())
    if m:
        return m.group(1).upper()
    return None


def resolve_section_semantic(
    *,
    title: str | None,
    form_type: str | None,
    parent_title: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """解析 SEC 章节的语义信息。

    根据章节标题和 form_type，解析出 Item 编号、法定标题和语义类型。

    Args:
        title: 章节标题（如 ``"Item 7. MD&A"``）。
        form_type: 表单类型（如 ``"10-K"``）。
        parent_title: 父章节标题（用于 10-Q Part I/II 消歧）。

    Returns:
        ``(item_number, canonical_title, topic)`` 三元组。
        任一字段无法确定时为 ``None``。
    """
    item_number = extract_item_number(title)
    if item_number is None:
        # SIGNATURES 章节回退
        if title and re.search(r"(?i)\bsignatures?\b", title):
            return None, "Signatures", SectionType.SIGNATURE.value
        return None, None, None

    normalized_form = (form_type or "").strip().upper()

    # 10-Q 特殊处理：Part I vs Part II 消歧
    if normalized_form in ("10-Q", "10-Q/A"):
        return _resolve_ten_q_semantic(item_number, parent_title or title)

    # 10-K / 20-F 通用路径
    item_map = _FORM_ITEM_MAPS.get(normalized_form)
    if item_map is None:
        return item_number, None, None

    entry = item_map.get(item_number)
    if entry is None:
        return item_number, None, None

    canonical_title, section_type = entry
    return item_number, canonical_title, section_type.value


def build_section_path(
    *,
    form_type: str | None,
    item_number: str | None,
    canonical_title: str | None,
    section_title: str | None,
    parent_titles: list[str] | None = None,
) -> list[str]:
    """构建 SEC 章节层级路径。

    路径从根到叶，包含 Part 前缀（如有）、Item 编号、章节标题。

    Args:
        form_type: 表单类型。
        item_number: Item 编号。
        canonical_title: 法定标题。
        section_title: 原始章节标题。
        parent_titles: 上溯父章节标题列表（从直接父到根）。

    Returns:
        层级路径列表（如 ``["Part I", "Item 1A", "Risk Factors"]``）。
    """
    path: list[str] = []
    titles = parent_titles or []

    # 添加 Part 前缀
    if item_number and form_type:
        normalized_form = (form_type or "").strip().upper()
        part_map = _FORM_PART_MAPS.get(normalized_form)
        if part_map:
            part = part_map.get(item_number)
            if part:
                path.append(f"Part {part}")

    # 添加父章节标题（倒序→正序）
    for pt in reversed(titles):
        if pt and not re.match(r"(?i)^\s*part\s+", pt):
            path.append(pt)

    # 添加 Item 标识
    if item_number:
        path.append(f"Item {item_number}")

    # 添加标题
    display_title = canonical_title or section_title
    if display_title:
        if not path or display_title not in path[-1]:
            path.append(display_title)

    return path


# ---------------------------------------------------------------------------
# 10-Q Part 消歧
# ---------------------------------------------------------------------------


def _resolve_ten_q_semantic(
    item_number: str,
    parent_title: str | None,
) -> tuple[str | None, str | None, str | None]:
    """解析 10-Q 章节语义（Part I/II 消歧）。"""
    part = _infer_ten_q_part(parent_title)

    if part == "II":
        entry = TEN_Q_PART_II_ITEM_MAP.get(item_number)
    elif part == "I":
        entry = TEN_Q_PART_I_ITEM_MAP.get(item_number)
    else:
        entry = TEN_Q_PART_I_ITEM_MAP.get(item_number) or TEN_Q_PART_II_ITEM_MAP.get(
            item_number
        )

    if entry is None:
        return item_number, None, None

    canonical_title, section_type = entry
    return item_number, canonical_title, section_type.value


def _infer_ten_q_part(parent_title: str | None) -> str | None:
    """从父章节标题推断 10-Q Part 编号。"""
    if not parent_title:
        return None
    upper = parent_title.upper().strip()
    if re.search(r"\bPART\s+I\b(?!\s*I)", upper):
        return "I"
    if re.search(r"\bPART\s+II\b", upper):
        return "II"
    return None
