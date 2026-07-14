#!/usr/bin/env python3
"""zone_d_industry_context.py — Zone D: Industry Context (Phase I)

SQL-based industry comparison: percentiles, peers, valuation benchmarks.
Pure Python, zero LLM. Runs in parallel with Zone A.

Output: industry_context.json

Usage:
    python3 scripts/zone_d_industry_context.py --code 01502.HK
    python3 scripts/zone_d_industry_context.py --code 01502.HK --years 3
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def median(values: list) -> float:
    vals = sorted([v for v in values if v is not None])
    if not vals:
        return 0
    n = len(vals)
    if n % 2 == 1:
        return vals[n // 2]
    return (vals[n // 2 - 1] + vals[n // 2]) / 2


def percentile(values: list, pct: float) -> float:
    vals = sorted([v for v in values if v is not None])
    if not vals:
        return 0
    k = (len(vals) - 1) * pct / 100
    f = int(k)
    c = k - f
    if f + 1 < len(vals):
        return vals[f] + c * (vals[f + 1] - vals[f])
    return vals[f]


def compute_percentile_rank(value: float, peers: list) -> float:
    """What % of peers are BELOW this value? 100 = top, 0 = bottom."""
    below = sum(1 for v in peers if v is not None and v < value)
    total = sum(1 for v in peers if v is not None)
    return round(below / total * 100, 1) if total > 0 else 50.0


def build_industry_context(ts_code: str, num_years: int = 3) -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row

    # Step 1: Get this stock's industry
    ic = conn.execute(
        "SELECT industry_l1, industry_l2 FROM industry_classification WHERE ts_code=?",
        (ts_code,)
    ).fetchone()
    if not ic:
        conn.close()
        return {"error": f"no_industry_data_for_{ts_code}"}

    l1, l2 = ic["industry_l1"], ic["industry_l2"]
    # Use L2 for peer grouping (more granular), fall back to L1
    industry_group = l2 or l1

    # Step 2: Get latest fiscal years
    years_row = conn.execute(
        "SELECT MAX(fiscal_year) as latest FROM annual_financials WHERE ts_code=?",
        (ts_code,)
    ).fetchone()
    if not years_row or not years_row["latest"]:
        conn.close()
        return {"error": "no_financial_data"}

    latest_year = years_row["latest"]
    years = list(range(latest_year - num_years + 1, latest_year + 1))

    # Step 3: Get peer stocks in same industry
    peers = conn.execute("""
        SELECT ic.ts_code, s.name_cn, s.market
        FROM industry_classification ic
        JOIN stocks s ON ic.ts_code = s.ts_code
        WHERE ic.industry_l2 = ?
    """, (industry_group,)).fetchall()
    peer_codes = [p["ts_code"] for p in peers]

    if len(peer_codes) < 3:
        # Fall back to L1
        peers = conn.execute("""
            SELECT ic.ts_code, s.name_cn, s.market
            FROM industry_classification ic
            JOIN stocks s ON ic.ts_code = s.ts_code
            WHERE ic.industry_l1 = ?
        """, (l1,)).fetchall()
        peer_codes = [p["ts_code"] for p in peers]

    # Step 4: Compute percentiles for key metrics (latest year)
    latest_yr = years[-1]
    percentiles = {}

    metrics = [
        ("revenue", "营业收入", "百万元"),
        ("gross_margin", "毛利率", "%"),
        ("roe", "ROE", "%"),
        ("n_income_attr_p", "归母净利润", "百万元"),
        ("total_assets", "总资产", "百万元"),
    ]

    # Compute ROE on the fly: n_income_attr_p / total_hldr_eqy_exc_min_int * 100
    for field, label, unit in metrics:
        if field == "roe":
            peer_values = []
            for pc in peer_codes:
                r = conn.execute(
                    "SELECT n_income_attr_p, total_hldr_eqy_exc_min_int FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
                    (pc, latest_yr)
                ).fetchone()
                if r and r["n_income_attr_p"] and r["total_hldr_eqy_exc_min_int"] and r["total_hldr_eqy_exc_min_int"] > 0:
                    peer_values.append(r["n_income_attr_p"] / r["total_hldr_eqy_exc_min_int"] * 100)
            stock_r = conn.execute(
                "SELECT n_income_attr_p, total_hldr_eqy_exc_min_int FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
                (ts_code, latest_yr)
            ).fetchone()
            stock_val = (stock_r["n_income_attr_p"] / stock_r["total_hldr_eqy_exc_min_int"] * 100) if (
                stock_r and stock_r["n_income_attr_p"] and stock_r["total_hldr_eqy_exc_min_int"] and
                stock_r["total_hldr_eqy_exc_min_int"] > 0
            ) else None
        else:
            peer_values = []
            for pc in peer_codes:
                r = conn.execute(
                    f"SELECT {field} FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
                    (pc, latest_yr)
                ).fetchone()
                if r and r[field] is not None:
                    peer_values.append(r[field])
            stock_r = conn.execute(
                f"SELECT {field} FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
                (ts_code, latest_yr)
            ).fetchone()
            stock_val = stock_r[field] if stock_r else None

        if stock_val is not None and len(peer_values) >= 3:
            percentiles[field] = {
                "label": label,
                "unit": unit,
                "value": round(stock_val, 2),
                "industry_median": round(median(peer_values), 2),
                "industry_q1": round(percentile(peer_values, 25), 2),
                "industry_q3": round(percentile(peer_values, 75), 2),
                "percentile": round(compute_percentile_rank(stock_val, peer_values), 1),
                "peer_count": len(peer_values),
            }

    # Step 5: Revenue CAGR (3-year)
    rev_vals = conn.execute(
        "SELECT fiscal_year, revenue FROM annual_financials WHERE ts_code=? AND fiscal_year IN ({}) ORDER BY fiscal_year".format(
            ",".join("?" * len(years))),
        [ts_code] + years
    ).fetchall()
    if len(rev_vals) >= 2 and rev_vals[0]["revenue"] and rev_vals[-1]["revenue"] and rev_vals[0]["revenue"] > 0:
        rev_cagr = (rev_vals[-1]["revenue"] / rev_vals[0]["revenue"]) ** (1 / (len(rev_vals) - 1)) - 1
        peer_cagrs = []
        for pc in peer_codes:
            pr = conn.execute(
                "SELECT fiscal_year, revenue FROM annual_financials WHERE ts_code=? AND fiscal_year IN ({}) ORDER BY fiscal_year".format(
                    ",".join("?" * len(years))),
                [pc] + years
            ).fetchall()
            if len(pr) >= 2 and pr[0]["revenue"] and pr[-1]["revenue"] and pr[0]["revenue"] > 0:
                peer_cagrs.append((pr[-1]["revenue"] / pr[0]["revenue"]) ** (1 / (len(pr) - 1)) - 1)
        percentiles["revenue_cagr_3y"] = {
            "label": "营收CAGR(3年)",
            "unit": "%",
            "value": round(rev_cagr * 100, 1),
            "industry_median": round(median(peer_cagrs) * 100, 1) if peer_cagrs else None,
            "percentile": round(compute_percentile_rank(rev_cagr, peer_cagrs), 1) if peer_cagrs else None,
            "peer_count": len(peer_cagrs),
        }

    # Step 6: Comparable peers — select by market cap similarity + include financial metrics
    comparable = []

    # Collect peer data from annual_financials (reliable) + financial_observations (market data)
    peer_data = []
    for p in peers:
        if p["ts_code"] == ts_code:
            continue
        pc = p["ts_code"]
        # Get fundamental data from annual_financials (always available)
        af = conn.execute(
            "SELECT revenue, gross_margin, n_income_attr_p, total_assets, total_hldr_eqy_exc_min_int, dps, eps FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
            (pc, latest_yr)
        ).fetchone()
        if not af or af["revenue"] is None:
            continue  # skip peers with no data
        # Compute ROE
        roe_val = None
        if af["n_income_attr_p"] and af["total_hldr_eqy_exc_min_int"] and af["total_hldr_eqy_exc_min_int"] > 0:
            roe_val = round(af["n_income_attr_p"] / af["total_hldr_eqy_exc_min_int"] * 100, 2)
        # Get market data from financial_observations (may be partial)
        fo = conn.execute(
            "SELECT field_name, normalized_value FROM financial_observations WHERE ts_code=? AND fiscal_year=? AND field_name IN ('market_cap','pe','pb','dividend_yield')",
            (pc, latest_yr)
        ).fetchall()
        fo_dict = {r["field_name"]: r["normalized_value"] for r in fo}
        peer_data.append({
            "ts_code": pc, "name": p["name_cn"], "market": p["market"],
            "revenue": af["revenue"], "gross_margin": af["gross_margin"],
            "n_income_attr_p": af["n_income_attr_p"], "total_assets": af["total_assets"],
            "roe": roe_val, "dps": af["dps"], "eps": af["eps"],
            "market_cap": fo_dict.get("market_cap"), "pe": fo_dict.get("pe"),
            "pb": fo_dict.get("pb"), "dividend_yield": fo_dict.get("dividend_yield"),
        })

    # Get target stock data for similarity scoring
    stock_af = conn.execute(
        "SELECT revenue, gross_margin, n_income_attr_p, total_assets, total_hldr_eqy_exc_min_int, dps, eps FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
        (ts_code, latest_yr)
    ).fetchone()
    stock_rev = stock_af["revenue"] if stock_af else None

    # Score peers by revenue similarity (most reliable metric), then by total_assets
    if stock_rev and stock_rev > 0:
        for pd_item in peer_data:
            score = abs((pd_item.get("revenue") or 0) - stock_rev) / stock_rev
            pd_item["_similarity_score"] = score
        peer_data.sort(key=lambda x: x.get("_similarity_score", 999))

    # Select top 5 most similar peers
    for pd_item in peer_data[:5]:
        comparable.append({
            "ts_code": pd_item["ts_code"], "name": pd_item["name"], "market": pd_item["market"],
            "revenue": round(pd_item["revenue"], 2) if pd_item.get("revenue") else None,
            "gross_margin": round(pd_item["gross_margin"], 2) if pd_item.get("gross_margin") else None,
            "roe": round(pd_item["roe"], 2) if pd_item.get("roe") else None,
            "n_income_attr_p": round(pd_item["n_income_attr_p"], 2) if pd_item.get("n_income_attr_p") else None,
            "total_assets": round(pd_item["total_assets"], 2) if pd_item.get("total_assets") else None,
            "dps": round(pd_item["dps"], 4) if pd_item.get("dps") else None,
            "market_cap": round(pd_item["market_cap"], 2) if pd_item.get("market_cap") else None,
            "pe": round(pd_item["pe"], 2) if pd_item.get("pe") else None,
            "pb": round(pd_item["pb"], 2) if pd_item.get("pb") else None,
            "dividend_yield": round(pd_item["dividend_yield"], 2) if pd_item.get("dividend_yield") else None,
        })

    # Step 7: Signals from industry comparison
    signals = []
    for field, data in percentiles.items():
        if not data.get("percentile"):
            continue
        pct = data["percentile"]
        if pct >= 80:
            signals.append({"type": "STRENGTH", "field": field,
                           "detail": f"{data['label']}处于行业前{pct}%（vs中位数{data.get('industry_median','?')}{data['unit']}）"})
        elif pct <= 30:
            signals.append({"type": "WEAKNESS", "field": field,
                           "detail": f"{data['label']}处于行业后{100-pct}%（vs中位数{data.get('industry_median','?')}{data['unit']}）"})

    # Collect target company's own metrics for easy peer comparison table
    target_metrics = {}
    target_af = conn.execute(
        "SELECT revenue, gross_margin, n_income_attr_p, total_assets, total_hldr_eqy_exc_min_int, dps, eps FROM annual_financials WHERE ts_code=? AND fiscal_year=?",
        (ts_code, latest_yr)
    ).fetchone()
    if target_af:
        target_metrics["revenue"] = target_af["revenue"]
        target_metrics["gross_margin"] = target_af["gross_margin"]
        target_metrics["n_income_attr_p"] = target_af["n_income_attr_p"]
        target_metrics["total_assets"] = target_af["total_assets"]
        target_metrics["dps"] = target_af["dps"]
        target_metrics["eps"] = target_af["eps"]
        if target_af["n_income_attr_p"] and target_af["total_hldr_eqy_exc_min_int"] and target_af["total_hldr_eqy_exc_min_int"] > 0:
            target_metrics["roe"] = round(target_af["n_income_attr_p"] / target_af["total_hldr_eqy_exc_min_int"] * 100, 2)
    target_fo = conn.execute(
        "SELECT field_name, normalized_value FROM financial_observations WHERE ts_code=? AND fiscal_year=? AND field_name IN ('market_cap','pe','pb','dividend_yield')",
        (ts_code, latest_yr)
    ).fetchall()
    for r in target_fo:
        target_metrics[r["field_name"]] = r["normalized_value"]

    conn.close()

    return {
        "_provenance": {
            "generated_at": datetime.now().isoformat(),
            "script": "zone_d_industry_context.py",
            "inputs": {"db_path": DB_PATH, "ts_code": ts_code, "fiscal_years": years}
        },
        "meta": {
            "ts_code": ts_code,
            "industry_l1": l1,
            "industry_l2": l2,
            "industry_group": industry_group,
            "fiscal_year": latest_yr,
            "years": years,
            "total_industry_peers": len(peer_codes),
        },
        "target_metrics": target_metrics,
        "percentiles": percentiles,
        "comparable_peers": comparable,
        "signals": signals,
    }


def main():
    p = argparse.ArgumentParser(description="zone_d_industry_context.py — Zone D Industry Context")
    p.add_argument("--code", type=str, required=True, help="Stock code")
    p.add_argument("--years", type=int, default=3, help="Number of fiscal years for CAGR")
    p.add_argument("--output", type=str, help="Output directory")
    args = p.parse_args()

    if args.output:
        stock_dir = args.output
    else:
        code_base = args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        candidates = [d for d in os.listdir(OUTPUT_BASE)
                      if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(code_base)]
        if not candidates:
            print(f"ERROR: No output directory for {args.code}", file=sys.stderr)
            return 1
        stock_dir = os.path.join(OUTPUT_BASE, candidates[0])

    ctx = build_industry_context(args.code, args.years)
    if "error" in ctx:
        print(f"ERROR: {ctx['error']}", file=sys.stderr)
        return 1

    out_path = os.path.join(stock_dir, "industry_context.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False, default=str)

    m = ctx["meta"]
    pcts = ctx["percentiles"]
    sig = ctx["signals"]
    print(f"✅ industry_context.json → {out_path}")
    print(f"   Industry: {m['industry_group']} | Peers: {m['total_industry_peers']} | FY{m['fiscal_year']}")
    for k, v in pcts.items():
        pctl_str = f"P{v['percentile']}" if v.get('percentile') else "N/A"
        print(f"   {v['label']}: {v['value']}{v['unit']} (median: {v.get('industry_median','?')}{v['unit']}, {pctl_str})")
    if sig:
        print(f"   Signals: {len(sig)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
