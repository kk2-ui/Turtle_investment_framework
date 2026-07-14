"""日期与期间解析器（从 Dayu html_financial_statement_common.py 提取）。

核心能力：
- 多格式日期提取：YYYY-MM-DD / MM/DD/YYYY / DD/MM/YYYY / "Sep 30, 2024" / 中文日期
- 财期推断：Q1-Q4 / FY / H1-H2 / 9M / 6M
- 多语月份映射：英/西/葡/法
- 粘连 token 修复："endedSep 2025" → "ended Sep 2025"

零外部依赖（仅 re + datetime + calendar），可直接用于从
PDF/HTML 财报表格中提取期间结束日期。

Usage::

    from scripts.parsers.date_parser import extract_date, extract_fiscal_period

    extract_date("September 30, 2024")   # → date(2024, 9, 30)
    extract_date("2024-09-30")           # → date(2024, 9, 30)
    extract_fiscal_period("Q1 2024")     # → ("Q1", 2024)
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from typing import Optional

# ---------------------------------------------------------------------------
# 预编译正则
# ---------------------------------------------------------------------------

# ISO/美式/欧式日期：YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY
_ISO_DATE_RE = re.compile(
    r"\b(19\d{2}|20\d{2}|2100)[/-](\d{1,2})[/-](\d{1,2})\b"
)

# 文本日期：Sep 30, 2024 / 30 September 2024
_TEXTUAL_DATE_WITH_DASH_RE = re.compile(
    r"\b(\d{1,2})\s*[-–—]\s*"
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|"
    r"Ene(?:ro)?|Feb(?:rero)?|Mar(?:zo)?|Abr(?:il)?|May(?:o)?|Jun(?:io)?|"
    r"Jul(?:io)?|Ago(?:sto)?|Sep(?:tiembre)?|Oct(?:ubre)?|Nov(?:iembre)?|Dic(?:iembre)?|"
    r"Janv(?:ier)?|F[eé]vr(?:ier)?|Mars|Avr(?:il)?|Mai|Juin|Juil(?:let)?|"
    r"Ao[uû]t|Sept(?:embre)?|Oct(?:obre)?|Nov(?:embre)?|D[eé]c(?:embre)?|"
    r"Jan(?:eiro)?|Fev(?:ereiro)?|Mar(?:[çc]o)?|Abr(?:il)?|Mai(?:o)?|Jun(?:ho)?|"
    r"Jul(?:ho)?|Ago(?:sto)?|Set(?:embro)?|Out(?:ubro)?|Nov(?:embro)?|Dez(?:embro)?"
    r")\s*[-–—]?\s*"
    r"(19\d{2}|20\d{2}|2100)",
    re.IGNORECASE,
)

# 财期推断正则
_FISCAL_PERIOD_YEAR_RE = re.compile(
    r"(?i)\b("
    r"Q[1-4]|"
    r"FY|FISCAL\s*YEAR|FULL\s*YEAR|"
    r"H[1-2]|HALF\s*[1-2]|"
    r"9M|NINE\s*MONTHS?|"
    r"6M|SIX\s*MONTHS?|"
    r"FIRST\s*QUARTER|SECOND\s*QUARTER|THIRD\s*QUARTER|FOURTH\s*QUARTER|"
    r"1ST\s*QUARTER|2ND\s*QUARTER|3RD\s*QUARTER|4TH\s*QUARTER|"
    r"一季度?|二季度?|三季度?|四季度?|"
    r"第一季度|第二季度|第三季度|第四季度|"
    r"上半年|下半年|"
    r"全年|年度"
    r")\b\s*"
    r"(19\d{2}|20\d{2}|2100)?"
)

# Year extraction
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|2100)\b")

# "ended Sep 2025" → 修复粘连 token
_FUSED_PERIOD_TOKEN_RE = re.compile(
    r"(ended|for|as\s+of|as\s+at)\s*"
    r"([A-Z][a-z]{2,8})\s*"
    r"(\d{4})",
    re.IGNORECASE,
)

# "12 months ended" / "year ended" / "fiscal year"
_PERIOD_SCOPE_RE = re.compile(
    r"(?i)\b("
    r"twelve\s*months?\s*ended|"
    r"year\s*ended|"
    r"fiscal\s*year|"
    r"three\s*months?\s*ended|"
    r"six\s*months?\s*ended|"
    r"nine\s*months?\s*ended|"
    r"quarter\s*ended|"
    r"as\s*of|as\s*at"
    r")\b"
)

# Month names → numbers
_MONTH_MAP: dict[str, int] = {
    # English
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
    # Spanish
    "ene": 1, "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abr": 4, "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "ago": 8, "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "dic": 12, "diciembre": 12,
    # Portuguese
    "janv": 1, "janeiro": 1,
    "fev": 2, "fevereiro": 2,
    "marco": 3, "março": 3,
    "mai": 5, "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "set": 9, "setembro": 9,
    "out": 10, "outubro": 10,
    "novembro": 11,
    "dez": 12, "dezembro": 12,
    # French
    "janvier": 1,
    "fevr": 2, "février": 2, "fevrier": 2,
    "mars": 3,
    "avr": 4, "avril": 4,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "aout": 8, "août": 8,
    "sept": 9, "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "dec": 12, "décembre": 12, "decembre": 12,
}

# 财期 → (month, day) 期间结束
_FISCAL_PERIOD_ENDS: dict[str, tuple[int, int]] = {
    "Q1": (3, 31),
    "Q2": (6, 30),
    "Q3": (9, 30),
    "Q4": (12, 31),
    "FY": (12, 31),
    "H1": (6, 30),
    "H2": (12, 31),
    "6M": (6, 30),
    "9M": (9, 30),
}

# 中文月份（简写）
_CHINESE_MONTH_MAP: dict[str, int] = {
    "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8,
    "九": 9, "十": 10, "十一": 11, "十二": 12,
}


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def extract_date(text: str) -> dt.date | None:
    """从文本中提取首个有效日期。

    支持 ISO (2024-09-30)、美式 (09/30/2024)、
    文本 (Sep 30, 2024 / 30 September 2024) 等格式。

    Args:
        text: 待解析文本。

    Returns:
        ``datetime.date``；无法识别时返回 ``None``。
    """
    normalized = _normalize_date_text(text)
    if not normalized:
        return None

    # 1) ISO/美式/欧式：YYYY-MM-DD / MM/DD/YYYY
    for match in _ISO_DATE_RE.finditer(normalized):
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        candidate = _safe_date(year=year, month=month, day=day)
        if candidate is not None:
            return candidate

    # 2) 文本日期（月日年，逗号分隔）：September 30, 2024
    mdy_match = re.search(
        r"\b("
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
        r")\s+"
        r"(\d{1,2})\s*,?\s*"
        r"(19\d{2}|20\d{2}|2100)",
        normalized,
        re.IGNORECASE,
    )
    if mdy_match:
        month = _resolve_month_token(mdy_match.group(1))
        if month is not None:
            day = int(mdy_match.group(2))
            year = _normalize_year_token(mdy_match.group(3))
            candidate = _safe_date(year=year, month=month, day=day)
            if candidate is not None:
                return candidate

    # 3) 文本日期（日月年，横线分隔）：30-Sep-2024
    for match in _TEXTUAL_DATE_WITH_DASH_RE.finditer(normalized):
        day = int(match.group(1))
        month = _resolve_month_token(match.group(2))
        if month is None:
            continue
        year = _normalize_year_token(match.group(3))
        candidate = _safe_date(year=year, month=month, day=day)
        if candidate is not None:
            return candidate

    # 4) 中文日期：2024年9月30日
    chinese_match = re.search(
        r"(19\d{2}|20\d{2}|2100)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        normalized,
    )
    if chinese_match:
        year = int(chinese_match.group(1))
        month = int(chinese_match.group(2))
        day = int(chinese_match.group(3))
        candidate = _safe_date(year=year, month=month, day=day)
        if candidate is not None:
            return candidate

    return None


def extract_fiscal_period(text: str) -> tuple[str, int] | None:
    """从文本中提取财期和财年。

    识别 Q1-Q4 / FY / H1-H2 / 9M / 6M 等财期标识
    及其关联年份。

    Args:
        text: 待解析文本。

    Returns:
        ``(period, year)``，如 ``("Q3", 2024)``；
        无法识别时返回 ``None``。
    """
    normalized = _normalize_date_text(text)
    match = _FISCAL_PERIOD_YEAR_RE.search(normalized)
    if not match:
        return None

    period_raw = match.group(1).strip().upper()
    year_raw = match.group(2)

    # 规范化财期
    period = _normalize_fiscal_period_token(period_raw)
    if period is None:
        return None

    # 解析年份
    if year_raw:
        year = int(year_raw)
    else:
        years = _extract_years(normalized)
        year = years[0] if years else dt.date.today().year

    return period, year


def resolve_period_end(period: str, year: int) -> dt.date | None:
    """根据财期和财年计算期间结束日期。

    Args:
        period: 财期代码（Q1-Q4 / FY / H1-H2 / 6M / 9M）。
        year: 财年。

    Returns:
        期间结束日期。
    """
    ends = _FISCAL_PERIOD_ENDS.get(period.upper())
    if ends is None:
        return None
    month, day = ends
    return _safe_date(year=year, month=month, day=day)


def extract_years(text: str) -> list[int]:
    """从文本中提取所有四位年份。

    Args:
        text: 待解析文本。

    Returns:
        年份列表（按出现顺序）。
    """
    return [int(m.group(0)) for m in _YEAR_RE.finditer(text)]


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _normalize_date_text(text: str) -> str:
    """预处理日期文本：修复粘连 token，空白归一化。"""
    normalized = " ".join(str(text or "").split())
    # 修复 "endedSep 2025" → "ended Sep 2025"
    normalized = _FUSED_PERIOD_TOKEN_RE.sub(
        lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}",
        normalized,
    )
    return normalized


def _resolve_month_token(token: str) -> int | None:
    """将月份名称（英/西/葡/法）映射为月份数字。"""
    cleaned = token.strip().lower()
    return _MONTH_MAP.get(cleaned)


def _normalize_year_token(raw: str) -> int:
    """规范化年份 token。两位数年份转四位数。"""
    year = int(raw.strip())
    if year < 100:
        year += 2000 if year < 70 else 1900
    return year


def _safe_date(*, year: int, month: int, day: int) -> dt.date | None:
    """安全构建 date 对象。"""
    try:
        return dt.date(year, month, day)
    except (ValueError, OverflowError):
        # 尝试月份最后一天
        try:
            last_day = calendar.monthrange(year, month)[1]
            return dt.date(year, month, min(day, last_day))
        except (ValueError, OverflowError):
            return None


def _normalize_fiscal_period_token(raw: str) -> str | None:
    """将财期文本规范化为标准代码。"""
    upper = raw.upper().strip()
    mapping: dict[str, str] = {
        "Q1": "Q1", "Q2": "Q2", "Q3": "Q3", "Q4": "Q4",
        "FY": "FY", "FISCAL YEAR": "FY", "FULL YEAR": "FY",
        "全年": "FY", "年度": "FY",
        "H1": "H1", "HALF 1": "H1", "上半年": "H1",
        "H2": "H2", "HALF 2": "H2", "下半年": "H2",
        "6M": "6M", "SIX MONTHS": "6M",
        "9M": "9M", "NINE MONTHS": "9M",
        "FIRST QUARTER": "Q1", "1ST QUARTER": "Q1",
        "一季度": "Q1", "第一季度": "Q1",
        "SECOND QUARTER": "Q2", "2ND QUARTER": "Q2",
        "二季度": "Q2", "第二季度": "Q2",
        "THIRD QUARTER": "Q3", "3RD QUARTER": "Q3",
        "三季度": "Q3", "第三季度": "Q3",
        "FOURTH QUARTER": "Q4", "4TH QUARTER": "Q4",
        "四季度": "Q4", "第四季度": "Q4",
    }
    return mapping.get(upper)


def _extract_years(text: str) -> list[int]:
    """从文本中提取所有四位年份。"""
    return [int(m.group(0)) for m in _YEAR_RE.finditer(text)]
