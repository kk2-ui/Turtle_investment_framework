#!/usr/bin/env python3
"""build_financial_trends.py — Zone A: 从 DB 提取结构化财务趋势数据

Output: output/{code}_{name}/financial_trends.json
Usage: python3 scripts/build_financial_trends.py --code 01502.HK
"""

import argparse, json, os, sqlite3, sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

def sf(v, default=None):
    try: return float(v) if v is not None else default
    except: return default

def cagr(start, end, n):
    if start and end and start > 0 and n > 0:
        return round(((end/start)**(1/n)-1)*100, 1)
    return None

def build(ts_code, years=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    stock = dict(conn.execute("SELECT * FROM stocks WHERE ts_code=?", (ts_code,)).fetchone())
    af = conn.execute("SELECT * FROM annual_financials WHERE ts_code=? ORDER BY fiscal_year", (ts_code,)).fetchall()
    if not af: return {"error": f"no_data"}
    if years: af = af[-years:]
    fys = [r["fiscal_year"] for r in af]

    income = []
    for r in af:
        rev, npv, gp, gm = sf(r["revenue"]), sf(r["n_income_attr_p"]), sf(r["gross_profit"]), sf(r["gross_margin"])
        pretax, tax, da = sf(r["pretax_profit"]), sf(r["income_tax"]), sf(r["d_a"])
        income.append({"fiscal_year": r["fiscal_year"], "revenue": rev, "gross_profit": gp,
                       "gross_margin": gm, "n_income_attr_p": npv, "pretax_profit": pretax,
                       "income_tax": tax, "d_a": da,
                       "effective_tax_rate": round(tax/pretax*100,1) if tax is not None and pretax and pretax>0 else None})
    for i, inc in enumerate(income):
        if i > 0:
            p = income[i-1]
            if p["revenue"]: inc["revenue_yoy"] = round((inc["revenue"]-p["revenue"])/p["revenue"]*100,1)
            if p["n_income_attr_p"]: inc["np_yoy"] = round((inc["n_income_attr_p"]-p["n_income_attr_p"])/p["n_income_attr_p"]*100,1)

    bs_trend = []
    for r in af:
        ta, tl, eq = sf(r["total_assets"]), sf(r["total_liab"]), sf(r["total_hldr_eqy_exc_min_int"])
        cash = sf(r["money_cap"])
        ar = sf(r["accounts_receiv"]); ap = sf(r["acct_payable"]); cl = sf(r["contract_liab"])
        goodwill = sf(r["goodwill"])
        bs_trend.append({"fiscal_year": r["fiscal_year"], "total_assets": ta, "total_liab": tl,
                         "total_equity": eq, "money_cap": cash,
                         "accounts_receiv": ar, "acct_payable": ap, "contract_liab": cl,
                         "goodwill": goodwill,
                         "net_cash": round(cash-tl,2) if cash and tl else None,
                         "debt_ratio": round(tl/ta*100,1) if ta and tl else None,
                         "equity_ratio": round(eq/ta*100,1) if ta and eq else None})

    cf_trend = []
    for r in af:
        ocf, capex, fcf = sf(r["n_cashflow_act"]), sf(r["c_pay_acq_const_fiolta"]), sf(r["fcf"])
        div = sf(r["dividends_paid"]); npv = sf(r["n_income_attr_p"]); rev = sf(r["revenue"])
        cf_trend.append({"fiscal_year": r["fiscal_year"], "operating_cf": ocf, "capex": capex,
                         "free_cash_flow": fcf, "dividends_paid": div,
                         "ocf_np_ratio": round(ocf/npv,2) if ocf and npv else None,
                         "capex_rev_pct": round(capex/rev*100,2) if capex and rev else None})

    per_share = [{"fiscal_year": r["fiscal_year"], "eps": sf(r["eps"]), "dps": sf(r["dps"])} for r in af]

    profitability = []
    for i, inc in enumerate(income):
        bs = bs_trend[i] if i < len(bs_trend) else {}
        npv, eq, ta, rev = inc["n_income_attr_p"], bs.get("total_equity"), bs.get("total_assets"), inc["revenue"]
        profitability.append({"fiscal_year": inc["fiscal_year"],
            "roe": round(npv/eq*100,1) if npv and eq else None,
            "roa": round(npv/ta*100,1) if npv and ta else None,
            "net_margin": round(npv/rev*100,1) if npv and rev else None,
            "gross_margin": inc["gross_margin"]})

    n = len(fys)
    rev_all = [i["revenue"] for i in income if i["revenue"]]
    np_all = [i["n_income_attr_p"] for i in income if i["n_income_attr_p"]]
    growth = {
        "revenue_cagr": {"3y": cagr(rev_all[-4] if len(rev_all)>=4 else None, rev_all[-1], 3),
                         "5y": cagr(rev_all[-6] if len(rev_all)>=6 else None, rev_all[-1], 5),
                         "all": cagr(rev_all[0], rev_all[-1], n-1) if n>=2 else None},
        "np_cagr": {"3y": cagr(np_all[-4] if len(np_all)>=4 else None, np_all[-1], 3),
                    "5y": cagr(np_all[-6] if len(np_all)>=6 else None, np_all[-1], 5),
                    "all": cagr(np_all[0], np_all[-1], n-1) if n>=2 else None},
        "margin_trend": "declining" if income[-1]["gross_margin"] and income[0]["gross_margin"] and income[-1]["gross_margin"] < income[0]["gross_margin"] else "stable",
    }

    conn.close()
    return {"code": ts_code, "name_cn": stock.get("name_cn",""), "name_en": stock.get("name_en",""),
            "market": stock.get("market",""), "currency": stock.get("currency","HKD"),
            "shares_m": stock.get("shares_m"), "fiscal_years": fys, "n_years": len(fys),
            "income_trend": income, "balance_sheet_trend": bs_trend,
            "cashflow_trend": cf_trend, "per_share_trend": per_share,
            "profitability_ratios": profitability, "growth_analysis": growth}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code", required=True)
    p.add_argument("--years", type=int)
    p.add_argument("--output", type=str, help="Output directory (auto-detected if omitted)")
    a = p.parse_args()
    r = build(a.code, a.years)
    if "error" in r: print(f"ERROR: {r['error']}", file=sys.stderr); return 1
    # Use --output if provided, else auto-detect
    if a.output:
        sd = a.output
        os.makedirs(sd, exist_ok=True)
    else:
        for e in os.listdir(OUTPUT_DIR):
            if e.startswith(a.code.replace(".","_")):
                sd = os.path.join(OUTPUT_DIR, e)
                if os.path.isdir(sd): break
        else: sd = os.path.join(OUTPUT_DIR, f"{a.code.replace('.HK','').replace('.SH','').replace('.SZ','')}_{r['name_cn']}"); os.makedirs(sd, exist_ok=True)
    out = os.path.join(sd, "financial_trends.json")
    with open(out, "w") as f: json.dump(r, f, indent=2, ensure_ascii=False, default=str)
    g = r["growth_analysis"]
    print(f"✅ financial_trends.json ({r['n_years']}y, {r['fiscal_years'][0]}-{r['fiscal_years'][-1]})")
    print(f"   Rev CAGR: 3y={g['revenue_cagr']['3y']}% 5y={g['revenue_cagr']['5y']}% all={g['revenue_cagr']['all']}%")
    print(f"   NP CAGR:  3y={g['np_cagr']['3y']}% 5y={g['np_cagr']['5y']}% all={g['np_cagr']['all']}%")
    return 0

if __name__ == "__main__": sys.exit(main())
