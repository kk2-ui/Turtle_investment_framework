"""Configuration and utility functions for Turtle Investment Framework."""

from __future__ import annotations

import os
import re
import glob
from typing import Optional


def _load_env_file() -> None:
    """Load .env file from project root if it exists."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value


def get_token() -> str:
    """Get Tushare Pro API token from environment or .env file.

    Returns:
        str: The Tushare API token.

    Raises:
        RuntimeError: If TUSHARE_TOKEN is not set.
    """
    _load_env_file()
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise RuntimeError(
            "TUSHARE_TOKEN is not set.\n"
            "Option 1: Copy .env.sample to .env and fill in your token\n"
            "Option 2: export TUSHARE_TOKEN='your_token_here'\n"
            "Get a token at: https://tushare.pro/register"
        )
    return token


def get_api_url() -> Optional[str]:
    """Return custom Tushare API URL from supported environment variables.

    When a broker API URL is configured, TushareClient will route all calls
    through it and auto-upgrade to VIP endpoints for better rate limits.
    """
    _load_env_file()
    return (
        os.environ.get("TUSHARE_API_URL")
        or os.environ.get("TUSHARE_HTTP_URL")
        or os.environ.get("API_URL")
        or None
    )


def get_vip_mode() -> bool:
    """Return whether VIP endpoint auto-upgrade is enabled.

    Default True (backward compatible). Set VIP_MODE=false in .env to disable
    for broker/proxy APIs that don't support _vip endpoints.
    """
    _load_env_file()
    val = os.environ.get("VIP_MODE", "true").strip().lower()
    return val not in ("false", "0", "no", "off")


def validate_stock_code(code: str) -> str:
    """Validate and normalize a stock code to Tushare format.

    Supports:
        - A-share: 600887.SH, 000858.SZ, 300750.SZ
        - HK: 00700.HK, 09988.HK (1-5 digits, zero-padded to 5)
        - Plain codes: 600887 -> 600887.SH, 000858 -> 000858.SZ
        - Plain 1-5 digit codes -> HK (e.g., 696 -> 00696.HK)

    Args:
        code: Stock code string.

    Returns:
        str: Normalized Tushare-format code (e.g., '600887.SH').

    Raises:
        ValueError: If the code format is not recognized.
    """
    code = code.strip().upper()

    # Already in Tushare format
    if re.match(r"^\d{6}\.(SH|SZ)$", code):
        return code
    m = re.match(r"^(\d{1,5})\.HK$", code)
    if m:
        return f"{m.group(1).zfill(5)}.HK"

    # Plain 6-digit A-share code
    if re.match(r"^\d{6}$", code):
        if code.startswith("6"):
            return f"{code}.SH"
        elif code.startswith(("0", "3")):
            return f"{code}.SZ"
        else:
            raise ValueError(
                f"Unrecognized A-share code prefix: {code}. "
                "Expected 6xxxxx (SH), 0xxxxx or 3xxxxx (SZ)."
            )

    # Plain 1-5 digit HK code
    if re.match(r"^\d{1,5}$", code):
        return f"{code.zfill(5)}.HK"

    # Already in US format: AAPL.US
    if re.match(r"^[A-Z]{1,5}\.US$", code):
        return code

    # Plain alphabetic ticker → US stock
    if re.match(r"^[A-Z]{1,5}$", code):
        return f"{code}.US"

    raise ValueError(
        f"Unrecognized stock code format: '{code}'. "
        "Expected: 600887.SH, 000858.SZ, 00700.HK, AAPL.US, or plain digits."
    )


def check_local_pdf(stock_code: str, year: int, search_dir: str = ".",
                    report_type: str = "年报") -> Optional[str]:
    """Check if a report PDF exists locally.

    Args:
        stock_code: Stock code (e.g., '600887' or '600887.SH').
        year: Fiscal year to look for.
        search_dir: Directory to search in.
        report_type: Type of report to search for ('年报' or '中报').

    Returns:
        Path to the PDF if found, None otherwise.
    """
    # Extract numeric part of code
    numeric_code = stock_code.split(".")[0]

    if report_type == "中报":
        patterns = [
            f"*{numeric_code}*{year}*中报*.pdf",
            f"*{numeric_code}*{year}*半年*.pdf",
            f"*{numeric_code}*{year}*interim*.pdf",
            f"*{numeric_code}*{year}*H1*.pdf",
            f"{numeric_code}_{year}_中报.pdf",
        ]
    else:
        patterns = [
            f"*{numeric_code}*{year}*.pdf",
            f"*{numeric_code}*{year}*年报*.pdf",
            f"{numeric_code}_{year}_*.pdf",
        ]

    for pattern in patterns:
        matches = glob.glob(os.path.join(search_dir, pattern))
        if matches:
            return matches[0]

    return None


def validate_pdf(filepath: str) -> "tuple[bool, str]":
    """Validate that a file is a real PDF.

    Args:
        filepath: Path to the file.

    Returns:
        Tuple of (is_valid, reason).
    """
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"

    size = os.path.getsize(filepath)
    if size < 100 * 1024:  # 100KB minimum
        return False, f"File too small ({size} bytes), likely not a real annual report"

    with open(filepath, "rb") as f:
        magic = f.read(20)
        if b"%PDF-" not in magic:
            return False, "File does not start with %PDF- magic bytes"

    return True, "Valid PDF"


def normalize_holding_channel(channel: Optional[str]) -> str:
    """Normalize user-provided holding-channel text into internal categories."""
    if not channel:
        return ""
    raw = str(channel).strip().lower()
    if not raw:
        return ""

    if raw in {"southbound", "hk_local_direct", "hk_local_direct_tax0", "hk_local_direct_tax10", "us_broker", "direct"}:
        return raw
    if any(k in raw for k in ("港股通", "southbound", "southbound connect")):
        return "southbound"
    if any(k in raw for k in ("香港", "hk local", "hong kong local", "香港券商", "本地直投")):
        if "10%" in raw or "10％" in raw or "tax10" in raw:
            return "hk_local_direct_tax10"
        if "0%" in raw or "0％" in raw or "tax0" in raw:
            return "hk_local_direct_tax0"
        return "hk_local_direct"
    if any(k in raw for k in ("w-8ben", "美股券商", "us broker")):
        return "us_broker"
    if any(k in raw for k in ("直接", "direct")):
        return "direct"
    return raw


def infer_listing_structure(ts_code: str, basic_info: Optional[dict] = None) -> str:
    """Best-effort listing-structure inference for tax handling."""
    code = (ts_code or "").upper()
    if code.endswith(".HK"):
        market = str((basic_info or {}).get("market", "")).strip()
        fullname = str((basic_info or {}).get("fullname", "")).strip().lower()
        enname = str((basic_info or {}).get("enname", "")).strip().lower()
        name_blob = " ".join(part for part in [market, fullname, enname] if part).lower()
        if "cayman" in name_blob or "开曼" in name_blob:
            return "red_chip_cayman"
        if "bermuda" in name_blob or "百慕大" in name_blob:
            return "red_chip_bermuda"
        return "hk"
    if code.endswith(".US"):
        return "us"
    if code.endswith(".SH") or code.endswith(".SZ"):
        return "a_share"
    return ""


def resolve_shareholder_dividend_tax_rate(
    ts_code: str,
    holding_channel: Optional[str] = None,
    listing_structure: Optional[str] = None,
) -> tuple[Optional[float], str]:
    """Resolve shareholder-level dividend tax rate for throughput-return analysis.

    Returns:
        (tax_rate_decimal_or_none, explanation)
    """
    code = (ts_code or "").upper()
    channel = normalize_holding_channel(holding_channel)
    structure = (listing_structure or "").strip().lower()
    override = os.environ.get("DIVIDEND_TAX_RATE", "").strip()
    if override:
        raw = override.replace("%", "")
        try:
            value = float(raw)
            rate = value / 100.0 if value > 1 else value
            if 0.0 <= rate <= 0.5:
                return rate, f"DIVIDEND_TAX_RATE 显式覆盖为 {rate * 100:.2f}%"
        except ValueError:
            pass

    if code.endswith(".SH") or code.endswith(".SZ"):
        return 0.0, "A股默认长期持有，股东层面股息税率 0%"

    if code.endswith(".US"):
        if channel == "us_broker":
            return 0.10, "美股 W-8BEN 口径，股东层面股息税率 10%"
        return 0.30, "美股默认非协定口径，股东层面股息税率 30%"

    if code.endswith(".HK"):
        if channel == "southbound":
            return 0.20, "港股通（内地个人）口径，股东层面股息税率 20%"
        if channel == "hk_local_direct_tax0":
            return 0.0, "香港券商直投，用户显式指定股东层面股息税率 0%"
        if channel == "hk_local_direct_tax10":
            return 0.10, "香港券商直投，用户显式指定股东层面股息税率 10%"

        if structure in {"red_chip_cayman", "red_chip_bermuda", "red_chip"}:
            if channel == "hk_local_direct":
                return None, "红筹/离岸架构 + 香港券商直投需确认实际预扣安排；不可默认 0%，建议列示 0%/10% 情景"
            if channel in {"direct", ""}:
                return None, "红筹/离岸架构直接持有需按税务居民身份确认，不能默认 20%"

        if structure in {"h_share", "hk"} and channel in {"direct", "hk_local_direct"}:
            return None, "港股直接持有税率依赖税务居民身份和发行人安排，需个案确认"

        return None, "港股股东层面股息税率需结合上市结构与持有人身份确认"

    return None, "未知市场，无法解析股东层面股息税率"
