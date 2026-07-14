"""数字单元格解析器（从 Dayu html_financial_statement_common.py 提取）。

核心能力：
- 括号转负号：``(123)`` → ``-123``
- 货币符号剥离：$ / € / ¥ / HK$ / RMB / BRL 等
- 欧式分隔符规范化：``1.234,56`` → ``1234.56``
- N/A / NaN / NM 等非数字值识别
- Unicode 减号/长破折号统一

零外部依赖（仅 re），可直接用于从 PDF/HTML 表格中解析结构化财务数据。

Usage::

    from scripts.parsers.num_parser import parse_numeric, normalize_numeric_separators

    parse_numeric("(1,234.56)")   # → -1234.56
    parse_numeric("HK$ 5,000")    # → 5000.0
    parse_numeric("1.234,56")     # → 1234.56 (EU format)
    parse_numeric("N/A")          # → None
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# 正则常量
# ---------------------------------------------------------------------------

# 数值前缀（正负号引导）
_NUMERIC_PREFIX_RE = re.compile(r"^[\s()*\-–—−+]*")

# 数值后缀（百分号、bps、倍数字）
_NUMERIC_SUFFIX_RE = re.compile(
    r"(?i)[\s]*"
    r"(?:%|bps|bp|"
    r"basis\s*points|"
    r"times|"
    r"x|×|"
    r"(?:\-?[%bpsx×]))"
    r"[\s]*$"
)

# 货币符号（前缀）
_CURRENCY_PREFIX_RE = re.compile(
    r"(?i)^\s*[$€¥£₩₹]+\s*"
)

# 货币代码（前缀格式：HK$ / USD / RMB 等）
_CURRENCY_CODE_RE = re.compile(
    r"(?i)^[\s]*(?:"
    r"us\$|hk\$|nt\$|r\$|ps\.?|cop|"
    r"usd|eur|gbp|cny|rmb|ars|brl|mxn|chf|jpy|krw|"
    r"hkd|sgd|aud|cad|inr|nok|sek|dkk|zar|try|thb|"
    r"myr|idr|php|vnd|twd"
    r")[\$]?[\s]*"
)

# 非数字哨兵值
_NON_NUMERIC_VALUES: frozenset[str] = frozenset({
    "nan", "none", "nat", "n/a", "na", "nm",
    "nil", "null", "n.a.", "n.m.", "n.a", "n/m",
    "—", "-", "--", "－",
})


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def parse_numeric(value: Any) -> float | None:
    """将单元格值解析为可选数值。

    处理括号负数、货币符号、千分位分隔符、非数字哨兵值。

    Args:
        value: 输入值（字符串或数字）。

    Returns:
        浮点数；无法解析时返回 ``None``。

    Examples:
        >>> parse_numeric("1,234.56")
        1234.56
        >>> parse_numeric("(500)")
        -500.0
        >>> parse_numeric("HK$ 1,000")
        1000.0
        >>> parse_numeric("N/A")
        None
    """
    text = " ".join(str(value or "").split())
    if not text:
        return None

    lowered = text.lower()
    if lowered in _NON_NUMERIC_VALUES:
        return None

    # 统一 Unicode 减号/破折号
    normalized = text.replace("−", "-").replace("–", "-").replace("—", "-")

    # 检测括号负数
    negative = normalized.startswith("(") and normalized.endswith(")")
    # 检测 Unicode 减号/破折号前缀负数
    if not negative and normalized.startswith(("−", "–", "—", "-")):
        negative = True
        normalized = normalized.lstrip("−–—-")
    normalized = normalized.replace("(", "").replace(")", "").strip()

    # 剥离前缀/后缀噪声
    normalized = _NUMERIC_PREFIX_RE.sub("", normalized)
    normalized = _NUMERIC_SUFFIX_RE.sub("", normalized)

    # 剥离货币代码（先处理复合代码如 HK$ ，再处理裸货币符号）
    normalized = _CURRENCY_CODE_RE.sub("", normalized)
    normalized = re.sub(r"[$€¥£₩₹]", "", normalized)

    # 剥离单引号千分位
    normalized = normalized.replace("'", "").replace(" ", "").strip()

    if normalized in {"", "-", "--"}:
        return None

    # 规范化欧式分隔符
    normalized = normalize_numeric_separators(normalized)
    if normalized in {"", "-", "--"}:
        return None

    try:
        numeric = float(normalized)
    except ValueError:
        return None

    if numeric != numeric:  # NaN check without pandas
        return None

    return -numeric if negative else numeric


def normalize_numeric_separators(value: str) -> str:
    """规范化数字中的千分位与小数分隔符。

    支持英语格式（``1,234.56``）和欧式格式（``1.234,56``）。

    Args:
        value: 原始数字字符串（已剥离货币/噪声前缀）。

    Returns:
        规范化后的数字字符串（``1234.56`` 格式）。

    Examples:
        >>> normalize_numeric_separators("1,234.56")
        '1234.56'
        >>> normalize_numeric_separators("1.234,56")
        '1234.56'
        >>> normalize_numeric_separators("1000")
        '1000'
    """
    cleaned = value.strip()

    # 同时有 . 和 ,  → 判断哪个是小数分隔符
    if "." in cleaned and "," in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # 逗号在最后 → 欧式：1.234,56
            return cleaned.replace(".", "").replace(",", ".")
        # 句点在最后 → 美式：1,234.56
        return cleaned.replace(",", "")

    # 只有逗号
    if "," in cleaned:
        comma_parts = cleaned.split(",")
        # 最后一段 1-2 位 → 小数分隔符：1234,56
        if len(comma_parts) == 2 and 1 <= len(comma_parts[1]) <= 2:
            return cleaned.replace(",", ".")
        # 多位 → 千分位：1,234,567
        return cleaned.replace(",", "")

    return cleaned


def is_non_numeric(value: Any) -> bool:
    """快速判断单元格是否为非数字哨兵值。

    Args:
        value: 输入值。

    Returns:
        True 如果值为 nan / N/A / 空 / 横杠等哨兵值。
    """
    text = " ".join(str(value or "").split()).strip().lower()
    if not text:
        return True
    if text in _NON_NUMERIC_VALUES:
        return True
    return False
