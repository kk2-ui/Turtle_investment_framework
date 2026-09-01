#!/usr/bin/env python3
"""quote_fetcher.py — 实时行情抓取 (移植自 invest App)

多市场、多数据源、自动兜底：
  - A/H/B/US: 腾讯财经(主) → 新浪财经(兜底)
  - DE (德国): Yahoo Finance(主) → Digrin(兜底)
  - 汇率: 新浪 fx_shkdcny / fx_susdcny

Usage:
  python scripts/quote_fetcher.py              # 更新 watchlist 所有股票的 live_price
  python scripts/quote_fetcher.py --dry-run    # 预览模式
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from typing import Any

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.join(_FRAMEWORK_DIR, "scripts")
sys.path.insert(0, _SCRIPTS_DIR)

# ── query code mapping ──────────────────────────────────────────────

def _to_query_codes(codes: list[str]) -> dict[str, str]:
    """Turtle code → market-specific query code.
    Returns {turtle_code: query_code}. DE stocks returned separately.
    """
    result = {}
    for c in codes:
        c = c.strip()
        if not c: continue
        if ".HK" in c:
            result[c] = f"hk{c.replace('.HK','')}"
        elif ".SZ" in c:
            result[c] = f"sz{c.replace('.SZ','')}"
        elif ".SH" in c:
            result[c] = f"sh{c.replace('.SH','')}"
        elif ".DE" in c:
            # 690D.DE → 690D.DE (Yahoo)
            result[c] = c.upper()
        elif c.endswith(".US"):
            result[c] = f"us{c.replace('.US','').upper()}"
        else:
            result[c] = c
    return result


# ── Tencent Finance (main for A/H/B) ────────────────────────────────

def _fetch_tencent(query_codes: dict[str, str]) -> dict[str, float]:
    """腾讯财经 https://qt.gtimg.cn/q=sh600519,hk00700

    返回格式 (~ 分隔): v_sh600519="1~茅台~600519~1768.00~..."
    字段 [3] = 当前价
    """
    if not query_codes: return {}
    qlist = list(query_codes.values())
    url = f"https://qt.gtimg.cn/q={','.join(qlist)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk", errors="replace")
    except Exception:
        return {}

    prices = {}
    for line in raw.split(";"):
        line = line.strip()
        if not line or "=" not in line: continue
        key, _, content = line.partition("=")
        qcode = key.replace("v_", "").strip().lower()
        content = content.strip().strip('"')
        if not content: continue
        fields = content.split("~")
        try:
            price = float(fields[3])
            if price > 0:
                # reverse map: qcode → turtle_code
                for tc, qc in query_codes.items():
                    if qc.lower() == qcode:
                        prices[tc] = price
                        break
        except (ValueError, IndexError):
            continue
    return prices


# ── Sina Finance (fallback for A/H/B) ───────────────────────────────

def _fetch_sina(query_codes: dict[str, str]) -> dict[str, float]:
    """新浪财经 https://hq.sinajs.cn/list=sh600519,hk00700

    返回格式 (, 分隔): var hq_str_sh600519="茅台,1750.00,..."
    A/B: 字段 [3] = 当前价
    H:   字段 [6] = 当前价
    """
    if not query_codes: return {}
    qlist = list(query_codes.values())
    url = f"https://hq.sinajs.cn/list={','.join(qlist)}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk", errors="replace")
    except Exception:
        return {}

    prices = {}
    for line in raw.split(";"):
        line = line.strip()
        if not line or "=" not in line: continue
        key, _, content = line.partition("=")
        qcode = key.replace("var hq_str_", "").strip().lower()
        content = content.strip().strip('"')
        if not content: continue
        fields = content.split(",")
        try:
            # Determine price index based on market prefix
            if qcode.startswith("hk"):
                price = float(fields[6]) if len(fields) > 6 else 0
            else:
                price = float(fields[3]) if len(fields) > 3 else 0
            if price > 0:
                for tc, qc in query_codes.items():
                    if qc.lower() == qcode:
                        prices[tc] = price
                        break
        except (ValueError, IndexError):
            continue
    return prices


# ── Yahoo Finance (for DE stocks) ────────────────────────────────────

def _fetch_yahoo(symbols: list[str]) -> dict[str, float]:
    """Yahoo Finance API for DE stocks.
    https://query2.finance.yahoo.com/v7/finance/quote?symbols=690D.DE
    """
    if not symbols: return {}
    url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={','.join(symbols)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return {}

    prices = {}
    results = data.get("quoteResponse", {}).get("result", [])
    for r in results:
        symbol = r.get("symbol", "").upper()
        price = r.get("regularMarketPrice")
        if price and price > 0:
            prices[symbol] = price
    return prices


# ── Digrin (fallback for DE) ─────────────────────────────────────────

def _fetch_digrin(symbol: str) -> float | None:
    """Digrin 页面抓取 DE 股价。https://www.digrin.com/stocks/detail/690D.DE/price"""
    import re
    url = f"https://www.digrin.com/stocks/detail/{symbol.upper()}/price"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None

    # Extract latest price from chart data
    chart_match = re.findall(r'\{ x: new Date\("[^"]+"\), y: ([\d.]+) \}', html)
    if chart_match:
        try:
            return float(chart_match[-1])
        except ValueError:
            pass
    return None


# ── Exchange Rates ──────────────────────────────────────────────────

def _fetch_exchange_rates() -> dict[str, float]:
    """新浪汇率: fx_shkdcny (港币/人民币), fx_susdcny (美元/人民币)"""
    url = "https://hq.sinajs.cn/list=fx_shkdcny,fx_susdcny"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk", errors="replace")
    except Exception:
        return {"hkd_cny": 0.93, "usd_cny": 7.25}

    rates = {}
    for line in raw.split(";"):
        line = line.strip()
        if "fx_shkdcny" in line:
            try:
                fields = line.split('"')[1].split(",")
                rates["hkd_cny"] = float(fields[7]) if len(fields) > 7 else 0.93
            except (ValueError, IndexError):
                rates["hkd_cny"] = 0.93
        elif "fx_susdcny" in line:
            try:
                fields = line.split('"')[1].split(",")
                rates["usd_cny"] = float(fields[7]) if len(fields) > 7 else 7.25
            except (ValueError, IndexError):
                rates["usd_cny"] = 7.25
    return rates


# ── Main ─────────────────────────────────────────────────────────────

def fetch_all_prices(dry_run: bool = False) -> dict[str, Any]:
    """获取 watchlist 所有股票的实时价格，更新 portfolio.db。"""
    from portfolio_db import get_db

    db = get_db()
    stocks = db.execute("SELECT ts_code, invest_code, market, current_hold FROM watchlist WHERE in_invest=1").fetchall()
    db.close()

    codes = [s["ts_code"] for s in stocks]
    query_map = _to_query_codes(codes)

    # Split by market
    cn_codes = {tc: qc for tc, qc in query_map.items() if not tc.endswith(".DE") and not tc.endswith(".US")}
    de_codes = {tc: qc for tc, qc in query_map.items() if tc.endswith(".DE")}

    if dry_run:
        print(f"CN stocks: {len(cn_codes)} — {list(cn_codes.keys())[:5]}...")
        print(f"DE stocks: {len(de_codes)} — {list(de_codes.keys())}")
        return {"cn": len(cn_codes), "de": len(de_codes), "dry_run": True}

    all_prices = {}

    # A/H/B: Tencent → Sina fallback
    print(f"  腾讯财经: {len(cn_codes)} 只...")
    prices = _fetch_tencent(cn_codes)
    all_prices.update(prices)
    missed = {tc: qc for tc, qc in cn_codes.items() if tc not in prices}
    if missed:
        print(f"  新浪兜底: {len(missed)} 只...")
        prices2 = _fetch_sina(missed)
        all_prices.update(prices2)

    # DE: Yahoo → Digrin fallback
    if de_codes:
        print(f"  Yahoo: {len(de_codes)} 只...")
        yahoo_symbols = list(de_codes.values())
        de_prices = _fetch_yahoo(yahoo_symbols)
        for tc, qc in de_codes.items():
            if qc.upper() in de_prices:
                all_prices[tc] = de_prices[qc.upper()]
            else:
                print(f"  Digrin兜底: {tc}...")
                p = _fetch_digrin(qc)
                if p: all_prices[tc] = p

    # Update DB
    db = get_db()
    updated = 0
    for s in stocks:
        tc = s["ts_code"]
        if tc in all_prices:
            db.execute("UPDATE watchlist SET live_price=?, updated_at=datetime('now') WHERE ts_code=?",
                       (all_prices[tc], tc))
            updated += 1
    db.commit()
    db.close()

    # Exchange rates (for reference)
    rates = _fetch_exchange_rates()

    print(f"  ✅ 更新 {updated}/{len(codes)} 只 | HKD/CNY={rates.get('hkd_cny',0):.4f} USD/CNY={rates.get('usd_cny',0):.2f}")
    return {"updated": updated, "total": len(codes), "rates": rates}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="实时行情抓取")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("📡 抓取实时行情...")
    result = fetch_all_prices(dry_run=args.dry_run)
    if not args.dry_run:
        print(f"   已更新到 portfolio.db → 运行 portfolio_dashboard.py 刷新仪表盘")


if __name__ == "__main__":
    main()
