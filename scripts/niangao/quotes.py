"""niangao.quotes — 行情层：多市场、多数据源实时价格抓取

移植自 invest App (CnQuoteFetcher + DeQuoteFetcher + QuoteParser)

数据源：
  A/H/B/US: 腾讯财经(主) → 新浪财经(兜底)
  DE(德国): Yahoo Finance(主) → Digrin(兜底)
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from niangao.db import get_db, _DB_PATH


def fetch_all_prices(dry_run: bool = False) -> dict[str, Any]:
    db = get_db()
    stocks = db.execute("SELECT ts_code, invest_code, market FROM watchlist WHERE in_invest=1").fetchall()
    db.close()

    codes = [s["ts_code"] for s in stocks]
    query_map = _to_query_codes(codes)
    cn_codes = {tc: qc for tc, qc in query_map.items() if not tc.endswith(".DE") and not tc.endswith(".US")}
    de_codes = {tc: qc for tc, qc in query_map.items() if tc.endswith(".DE")}

    if dry_run:
        print(f"  CN: {len(cn_codes)} | DE: {len(de_codes)}")
        return {"cn": len(cn_codes), "de": len(de_codes), "dry_run": True}

    all_prices = {}

    # A/H/B: Tencent → Sina
    prices = _fetch_tencent(cn_codes)
    all_prices.update(prices)
    missed = {tc: qc for tc, qc in cn_codes.items() if tc not in prices}
    if missed:
        prices2 = _fetch_sina(missed)
        all_prices.update(prices2)

    # DE: Yahoo → Digrin
    if de_codes:
        yahoo_symbols = list(de_codes.values())
        de_prices = _fetch_yahoo(yahoo_symbols)
        for tc, qc in de_codes.items():
            if qc.upper() in de_prices:
                all_prices[tc] = de_prices[qc.upper()]
            else:
                p = _fetch_digrin(qc)
                if p: all_prices[tc] = p

    # Update DB
    db = get_db()
    updated = 0
    for s in stocks:
        tc = s["ts_code"]
        if tc in all_prices:
            db.execute("UPDATE watchlist SET live_price=?, updated_at=datetime('now') WHERE ts_code=?", (all_prices[tc], tc))
            updated += 1
    db.commit(); db.close()
    return {"updated": updated, "total": len(codes)}


# ── query code mapping ──────────────────────────────────────────────

def _to_query_codes(codes: list[str]) -> dict[str, str]:
    result = {}
    for c in codes:
        c = c.strip()
        if not c: continue
        if ".HK" in c: result[c] = f"hk{c.replace('.HK','')}"
        elif ".SZ" in c: result[c] = f"sz{c.replace('.SZ','')}"
        elif ".SH" in c: result[c] = f"sh{c.replace('.SH','')}"
        elif ".DE" in c: result[c] = c.upper()
        elif ".US" in c: result[c] = f"us{c.replace('.US','').upper()}"
        else: result[c] = c
    return result


# ── Tencent Finance ─────────────────────────────────────────────────

def _fetch_tencent(query_codes: dict[str, str]) -> dict[str, float]:
    if not query_codes: return {}
    qlist = list(query_codes.values())
    url = f"https://qt.gtimg.cn/q={','.join(qlist)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk", errors="replace")
    except Exception: return {}

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
                for tc, qc in query_codes.items():
                    if qc.lower() == qcode: prices[tc] = price; break
        except (ValueError, IndexError): continue
    return prices


# ── Sina Finance (fallback) ─────────────────────────────────────────

def _fetch_sina(query_codes: dict[str, str]) -> dict[str, float]:
    if not query_codes: return {}
    qlist = list(query_codes.values())
    url = f"https://hq.sinajs.cn/list={','.join(qlist)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk", errors="replace")
    except Exception: return {}

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
            idx = 6 if qcode.startswith("hk") else 3
            price = float(fields[idx]) if len(fields) > idx else 0
            if price > 0:
                for tc, qc in query_codes.items():
                    if qc.lower() == qcode: prices[tc] = price; break
        except (ValueError, IndexError): continue
    return prices


# ── Yahoo Finance (DE) ──────────────────────────────────────────────

def _fetch_yahoo(symbols: list[str]) -> dict[str, float]:
    if not symbols: return {}
    url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={','.join(symbols)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception: return {}
    prices = {}
    for r in data.get("quoteResponse", {}).get("result", []):
        p = r.get("regularMarketPrice")
        if p and p > 0: prices[r.get("symbol", "").upper()] = p
    return prices


# ── Digrin (DE fallback) ────────────────────────────────────────────

def _fetch_digrin(symbol: str) -> float | None:
    url = f"https://www.digrin.com/stocks/detail/{symbol.upper()}/price"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception: return None
    matches = re.findall(r'\{ x: new Date\("[^"]+"\), y: ([\d.]+) \}', html)
    if matches:
        try: return float(matches[-1])
        except ValueError: pass
    return None


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="实时行情抓取")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print("📡 抓取实时行情...")
    result = fetch_all_prices(dry_run=args.dry_run)
    if not args.dry_run:
        print(f"   ✅ {result['updated']}/{result['total']} 只 | 运行 dashboard 刷新仪表盘")

if __name__ == "__main__":
    main()
