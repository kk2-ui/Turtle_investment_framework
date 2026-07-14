#!/usr/bin/env python3
"""Turtle Investment Framework - Tushare Data Collector (Phase 1A).

Facade module: re-exports all public names and defines TushareClient
which inherits from mixin classes in tushare_modules/.

Collects 5 years of financial data from Tushare Pro API and outputs
a structured data_pack_market.md file.

Usage:
    python3 scripts/tushare_collector.py --code 600887.SH
    python3 scripts/tushare_collector.py --code 600887.SH --output output/data_pack.md
    python3 scripts/tushare_collector.py --code 600887.SH --dry-run
"""

import argparse
import functools
import os
import subprocess
import sys
import time

import pandas as pd
import tushare as ts

try:
    import yfinance as yf
    _yf_available = True
except ImportError:
    _yf_available = False

from config import (
    get_token,
    get_api_url,
    get_vip_mode,
    validate_stock_code,
    infer_listing_structure,
)
from format_utils import format_number, format_table, format_header

# Re-export all constants and mixin classes for backward compatibility.
# Tests and external code import these from tushare_collector directly:
#   from tushare_collector import TushareClient, WarningsCollector, rate_limit
#   from tushare_collector import _VIP_MAP, HK_INCOME_MAP, US_INCOME_MAP
from tushare_modules import (
    _VIP_MAP,
    HK_INCOME_MAP, HK_BALANCE_MAP, HK_CASHFLOW_MAP,
    US_INCOME_MAP, US_BALANCE_MAP, US_CASHFLOW_MAP,
    _YF_INCOME_MAP, _YF_BALANCE_MAP, _YF_CASHFLOW_MAP,
    InfrastructureMixin, MarketFallbackMixin, YFinanceMixin, FinancialsMixin,
    OtherDataMixin, DerivedMetricsMixin, AssemblyMixin,
    WarningsCollector,
)


def rate_limit(func):
    """Decorator to enforce 0.5s delay between Tushare API calls."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        time.sleep(0.5)
        return func(*args, **kwargs)
    return wrapper


class TushareClient(
    InfrastructureMixin,
    MarketFallbackMixin,
    YFinanceMixin,
    FinancialsMixin,
    OtherDataMixin,
    DerivedMetricsMixin,
    AssemblyMixin,
):
    """Client for Tushare Pro API with rate limiting and retry logic."""

    MAX_RETRIES = 5
    RETRY_DELAY = 2.0  # seconds between retries

    BASIC_CACHE_TTL = 7 * 86400  # 7 days in seconds

    def __init__(self, token: str):
        self.pro = ts.pro_api(token=token, timeout=30)
        self.token = token
        self._store = {}  # {key: pd.DataFrame} for derived metrics computation
        self._yf_available = _yf_available
        self._cache_dir = os.path.join("output", ".collector_cache")
        self._fy_end_month: int = 12  # default: calendar year
        self._currency: str = "CNY"
        self.holding_channel: str = os.environ.get("HOLDING_CHANNEL", "").strip()
        self.listing_structure: str = ""
        # Broker API support: route calls through custom URL
        api_url = get_api_url()
        self._vip_mode = get_vip_mode()
        if api_url:
            self.pro._DataApi__token = token
            self.pro._DataApi__http_url = api_url

    def _set_basic_info_context(self, ts_code: str, row_like) -> None:
        """Persist lightweight context used by downstream derived metrics."""
        basic = {}
        for key in ("market", "fullname", "enname", "name"):
            try:
                basic[key] = row_like.get(key)
            except Exception:
                basic[key] = None
        self.listing_structure = infer_listing_structure(ts_code, basic)

    @rate_limit
    def _safe_call(self, api_name: str, **kwargs) -> pd.DataFrame:
        """Call a Tushare API endpoint with retry logic.

        Auto-upgrades to VIP endpoints when broker is active.

        Args:
            api_name: The API endpoint name (e.g., 'stock_basic').
            **kwargs: Parameters passed to the API call.

        Returns:
            DataFrame with results.

        Raises:
            RuntimeError: After MAX_RETRIES failures.
        """
        # Auto-upgrade to VIP endpoint when broker is active
        effective_name = api_name
        if self._vip_mode and api_name in _VIP_MAP:
            effective_name = _VIP_MAP[api_name]

        last_err = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                api_func = getattr(self.pro, effective_name)
                df = api_func(**kwargs)
                return df
            except Exception as e:
                last_err = e
                err_text = str(e)
                permission_denied = "访问权限" in err_text or "无权限" in err_text or "permission" in err_text.lower()
                if permission_denied:
                    raise RuntimeError(f"Tushare API '{effective_name}' permission denied: {e}") from e
                if attempt < self.MAX_RETRIES:
                    is_conn_err = isinstance(e, (ConnectionError, OSError)) or \
                        "RemoteDisconnected" in type(e).__name__ or \
                        "ConnectionAborted" in str(e) or \
                        "RemoteDisconnected" in str(e)
                    if is_conn_err:
                        print(f"[retry {attempt}/{self.MAX_RETRIES}] {effective_name}: connection error, re-creating API client...", file=sys.stderr)
                        self.pro = ts.pro_api(token=self.token, timeout=30)
                        # Re-apply broker hacks after re-creating client
                        api_url = get_api_url()
                        if api_url:
                            self.pro._DataApi__token = self.token
                            self.pro._DataApi__http_url = api_url
                    else:
                        print(f"[retry {attempt}/{self.MAX_RETRIES}] {effective_name}: {e}", file=sys.stderr)
                    time.sleep(self.RETRY_DELAY * attempt)
        raise RuntimeError(
            f"Tushare API '{effective_name}' failed after {self.MAX_RETRIES} retries: {last_err}"
        )

    def _cached_basic_call(self, api_name: str, **kwargs) -> pd.DataFrame:
        """Call stock_basic/hk_basic with 7-day file cache."""
        ts_code = kwargs.get("ts_code", "all")
        cache_file = os.path.join(self._cache_dir, f"{api_name}_{ts_code}.json")
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            if time.time() - mtime < self.BASIC_CACHE_TTL:
                return pd.read_json(cache_file)
        df = self._safe_call(api_name, **kwargs)
        if not df.empty:
            os.makedirs(self._cache_dir, exist_ok=True)
            df.to_json(cache_file, orient="records", force_ascii=False)
        return df

    def _cached_us_daily(self, ts_code: str = None) -> pd.DataFrame:
        """Fetch us_daily with same-day file cache (bulk all-stock fetch).

        First call fetches ALL US stocks (limit=6000) and caches to Parquet.
        Subsequent same-day calls read from cache and filter by ts_code.
        """
        cache_file = os.path.join(self._cache_dir, "us_daily_all.parquet")
        today = pd.Timestamp.now().strftime("%Y%m%d")

        # Check cache: file exists AND was created today
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            cache_date = pd.Timestamp.fromtimestamp(mtime).strftime("%Y%m%d")
            if cache_date == today:
                df = pd.read_parquet(cache_file)
                if ts_code:
                    df = df[df["ts_code"] == ts_code]
                return df

        # Bulk fetch all US stocks
        df = self._safe_call("us_daily", limit=6000,
                             fields="ts_code,trade_date,open,high,low,close,"
                                    "vol,amount,pe,pb,total_mv")
        if not df.empty:
            os.makedirs(self._cache_dir, exist_ok=True)
            df.to_parquet(cache_file, index=False)

        if ts_code and not df.empty:
            df = df[df["ts_code"] == ts_code]
        return df


def ensure_hk_report_fallback(ts_code: str, output_dir: str) -> str | None:
    """Generate hk_report_fallback.json for HK stocks when missing.

    Returns the fallback file path when available, otherwise None.
    """
    if not ts_code.upper().endswith(".HK"):
        return None

    fallback_path = os.path.join(output_dir, "hk_report_fallback.json")
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "hk_report_fallback.py"),
        "--output-dir", output_dir,
        "--code", ts_code,
    ]
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        with open(fallback_path, "w", encoding="utf-8") as fh:
            fh.write(res.stdout)
        print(f"HK report fallback written to {fallback_path}")
        return fallback_path
    except Exception as e:
        print(f"⚠️ HK report fallback generation failed: {e}")
        return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect financial data from Tushare Pro API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --code 600887.SH
  %(prog)s --code 600887 --output output/data_pack_market.md
  %(prog)s --code 00700.HK --extra-fields balancesheet.defer_tax_assets
        """,
    )
    parser.add_argument(
        "--code",
        required=True,
        help="Stock code (e.g., 600887.SH, 000858.SZ, 00700.HK, or plain digits)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Tushare API token (defaults to TUSHARE_TOKEN env var)",
    )
    parser.add_argument(
        "--output",
        default="output/data_pack_market.md",
        help="Output file path (default: output/data_pack_market.md)",
    )
    parser.add_argument(
        "--extra-fields",
        nargs="*",
        help="Additional fields to fetch (format: endpoint.field_name)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print parsed arguments and exit without calling API",
    )
    parser.add_argument(
        "--refresh-market",
        action="store_true",
        help="Only refresh market-sensitive sections (§1/§2/§11/§14) in existing data pack",
    )
    parser.add_argument(
        "--hk-report-fallback",
        action="store_true",
        help="For HK stocks, extract fallback financial summaries from local annual reports into hk_report_fallback.json",
    )
    return parser.parse_args()


def _normalize_scale(md_content: str) -> str:
    """v2.25: Detect and fix year-to-year unit mismatches in Tushare HK data.

    Tushare HK APIs sometimes return revenue/profit in 元 for some years and
    千元 for others. This function detects values that jump >8x between adjacent
    years and divides the outlier by 1000.
    """
    import re

    # Find financial tables (§3/§4/§5) and extract numeric rows
    lines = md_content.split('\n')
    fixes = []
    fixed_lines = list(lines)

    # Pattern: | field_name | v2021 | v2022 | v2023 | v2024 | v2025 |
    year_cols = re.compile(r'^\|\s*(.+?)\s*\|\s*([\d,.\-—]+)\s*\|\s*([\d,.\-—]+)\s*\|\s*([\d,.\-—]+)\s*\|\s*([\d,.\-—]+)\s*\|\s*([\d,.\-—]+)\s*\|')

    for i, line in enumerate(lines):
        m = year_cols.match(line)
        if not m: continue

        field = m.group(1).strip()
        vals = []
        for g in range(2, 7):
            v = m.group(g).strip()
            if v in ('—', '-', ''):
                vals.append(None)
            else:
                try: vals.append(float(v.replace(',', '')))
                except: vals.append(None)

        # Detect outlier years: if most values are in range X and one is 1000*X
        numeric = [(j, v) for j, v in enumerate(vals) if v is not None and v > 0]
        if len(numeric) < 4: continue  # need enough data to judge

        # Sort by value to find clusters
        sorted_vals = sorted(numeric, key=lambda x: x[1])
        median_idx = len(sorted_vals) // 2
        median_v = sorted_vals[median_idx][1]

        for j, v in numeric:
            ratio = v / median_v if median_v > 0 else 1
            # If a value is >8x the median, it's likely in different units
            if ratio > 8:
                corrected = v / 1000
                vals[j] = corrected
                fixes.append(f'{field}: FY{2021+j} {v:,.0f}→{corrected:,.1f} (÷1000, unit mismatch)')
            elif ratio < 0.12 and v > 0:
                # Value is <1/8 of median — might be in 百万元 vs others in 千元
                corrected = v * 1000
                vals[j] = corrected
                fixes.append(f'{field}: FY{2021+j} {v:,.1f}→{corrected:,.0f} (×1000, unit mismatch)')

        # Rebuild the line with corrected values
        parts = [f'| {field} |']
        for v in vals:
            if v is None: parts.append(' — |')
            elif v == int(v): parts.append(f' {int(v):,} |')
            else: parts.append(f' {v:,.2f} |')
        fixed_lines[i] = ''.join(parts)

    all_fixes = list(fixes)
    current_lines = list(fixed_lines) if fixes else list(lines)

    # ── Phase 2: Cross-field BS identity check (always runs, v2.25) ──
    for i, line in enumerate(current_lines):
        m = year_cols.match(line)
        if not m: continue
        field = m.group(1).strip()
        vals = {}
        for g_idx, g in enumerate(range(2, 7)):
            v_str = m.group(g).strip()
            if v_str not in ('—', '-', ''):
                try: vals[g_idx] = float(v_str.replace(',', ''))
                except: pass
        if field not in ('负债合计', '流动负债合计'): continue
        if len(vals) < 3: continue

        # Scan nearby lines for 资产总计 and 归母权益
        ta_vals = {}; eq_vals = {}; mi_vals = {}
        for j, ol in enumerate(current_lines):
            om = year_cols.match(ol)
            if not om: continue
            of = om.group(1).strip()
            for g_idx, g in enumerate(range(2, 7)):
                vs = om.group(g).strip()
                if vs in ('—', '-', ''): continue
                try: v = float(vs.replace(',', ''))
                except: continue
                if of in ('资产总计', '总资产'): ta_vals[g_idx] = v
                if of in ('归母权益', '归属股东权益', '股东权益', '本公司拥有人应占权益'): eq_vals[g_idx] = v
                if of in ('少数股东权益', '非控股权益'): mi_vals[g_idx] = v

        suspect = 0
        for g_idx in vals:
            if g_idx in ta_vals and g_idx in eq_vals:
                a, e, l = ta_vals[g_idx], eq_vals[g_idx], vals[g_idx]
                mi = mi_vals.get(g_idx, 0)
                if a <= 0 or l <= 0 or e <= 0: continue
                # If L > A, L is clearly wrong (liabilities can't exceed assets)
                # Or if L ≫ A-E, unit mismatch
                if l > a * 1.5 or (a > 0 and abs(a - e - mi - l) > max(a, l) * 0.5):
                    suspect += 1

        if suspect >= 3:
            # Divide by 1000
            for g_idx in vals:
                vals[g_idx] = vals[g_idx] / 1000
            all_fixes.append(f'{field}: ÷1000 (BS恒等式校验, {suspect}年L与A/E不匹配)')
            parts = [f'| {field} |']
            for g_idx in range(5):
                v = vals.get(g_idx)
                if v is None: parts.append(' — |')
                elif v == int(v): parts.append(f' {int(v):,} |')
                else: parts.append(f' {v:,.2f} |')
            current_lines[i] = ''.join(parts)

    if all_fixes:
        fixed_content = '\n'.join(current_lines)
        fix_note = '\n'.join(f'  - {f}' for f in all_fixes)
        tag = '## 13. ⚠️ Warnings'
        if tag in fixed_content:
            fixed_content = fixed_content.replace(tag, f'{tag}\n\n### 13.1 自动检测警告\n\n[数据修正|中] Tushare尺度不一致，已自动修正（v2.25）：\n{fix_note}\n')
        else:
            fixed_content += f'\n\n{tag}\n\n### 13.1 自动检测警告\n\n[数据修正|中] Tushare尺度不一致，已自动修正（v2.25）：\n{fix_note}\n'
        print(f'  [scale fix] Corrected {len(all_fixes)} unit mismatch(es)')
        return fixed_content

    return md_content


def main():
    args = parse_args()

    # Validate and normalize stock code
    try:
        ts_code = validate_stock_code(args.code)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("=== Dry Run ===")
        print(f"  Stock code: {args.code} -> {ts_code}")
        print(f"  Token: {'provided via --token' if args.token else 'from TUSHARE_TOKEN env'}")
        print(f"  Output: {args.output}")
        print(f"  Extra fields: {args.extra_fields or 'none'}")
        return

    # Get token
    token = args.token or get_token()
    client = TushareClient(token)
    output_dir = os.path.dirname(os.path.abspath(args.output)) or "."
    client._store["_output_dir"] = output_dir

    if ts_code.endswith(".HK") and (args.hk_report_fallback or not os.path.exists(os.path.join(output_dir, "hk_report_fallback.json"))):
        ensure_hk_report_fallback(ts_code, output_dir)

    if args.refresh_market:
        from pathlib import Path
        output_path = Path(args.output)
        if not output_path.exists():
            print(f"⚠️ {output_path} does not exist, falling back to full collection")
            print(f"Collecting data for {ts_code}...")
            data_pack = client.assemble_data_pack(ts_code)
        else:
            existing = output_path.read_text(encoding="utf-8")
            age_days = client._check_staleness(existing)
            if age_days > 7:
                print(f"⚠️ Data pack is {age_days} days old, falling back to full collection")
                print(f"Collecting data for {ts_code}...")
                data_pack = client.assemble_data_pack(ts_code)
            else:
                print(f"Refreshing market data for {ts_code} (data pack is {age_days} day(s) old)...")
                data_pack = client.refresh_market_sections(ts_code, existing)
    else:
        print(f"Collecting data for {ts_code}...")
        data_pack = client.assemble_data_pack(ts_code)

    # Handle extra fields
    if args.extra_fields:
        extra_lines = ["\n", format_header(2, "附加字段"), ""]
        for field_spec in args.extra_fields:
            parts = field_spec.split(".", 1)
            if len(parts) != 2:
                extra_lines.append(f"- 无效字段格式: {field_spec} (应为 endpoint.field_name)")
                continue
            endpoint, field_name = parts
            try:
                df = client._safe_call(endpoint, ts_code=ts_code, fields=f"ts_code,end_date,{field_name}")
                if not df.empty:
                    extra_lines.append(f"**{endpoint}.{field_name}**:")
                    extra_lines.append(df.to_markdown(index=False))
                    extra_lines.append("")
                else:
                    extra_lines.append(f"- {endpoint}.{field_name}: 无数据")
            except Exception as e:
                extra_lines.append(f"- {endpoint}.{field_name}: 获取失败 ({e})")
        data_pack += "\n".join(extra_lines)

    # v2.25: Scale normalization — detect and correct unit mismatches across years
    data_pack = _normalize_scale(data_pack)

    # Write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(data_pack)
    print(f"Output written to {args.output}")
    print(f"File size: {os.path.getsize(args.output):,} bytes")

if __name__ == "__main__":
    main()
