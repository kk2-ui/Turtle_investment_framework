#!/usr/bin/env python3
"""build_data_pack.py — 将 Zone A/B/J JSON 转为 LLM 可读的 markdown 数据包。

替代 zone_c_chain.py 的 JSON 嵌入逻辑。Agent 读取本文件 + 指令文件,
不再需要在 300KB JSON 中搜索字段。

Usage:
    python3 scripts/build_data_pack.py --code 03658.HK
    python3 scripts/build_data_pack.py --code 03658.HK --output output/03658_新希望服务
"""

import argparse, json, os, sys

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

def safe(v, fmt=",.2f", default="—"):
    if v is None: return default
    if isinstance(v, float) and v != v: return default  # NaN
    try: return f"{v:{fmt}}" if fmt and isinstance(v, (int,float)) else str(v)
    except: return str(v)

def pct(v, default="—"):
    if v is None: return default
    try: return f"{float(v)*100:.1f}%"
    except: return default

def table(headers, rows):
    """Generate markdown table."""
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join([":" + "-"*(len(h)-2) + ":" if i>0 else ":" + "-"*(len(h)-2) for i,h in enumerate(headers)]) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) if c is not None else "—" for c in row) + " |")
    return "\n".join(lines)

def build_data_pack(stock_dir, ts_code):
    """Main function: read all JSONs, return markdown string."""

    def load(name):
        path = os.path.join(stock_dir, name)
        if os.path.exists(path):
            with open(path) as f: return json.load(f)
        return None

    cb = load("compute_bundle.json")
    cb_p = load("compute_bundle_precise.json")
    ft = load("financial_trends.json")
    moat = load("moat_assessment.json")
    ind = load("industry_context.json")
    seg = load("segments.json")
    mda = load("mda.json")
    risks = load("risks.json")
    gov = load("governance.json")
    audit = load("audit.json")
    eq = load("earnings_quality.json")
    dd = load("data_discount.json")
    capex = load("capex_classification.json")

    if not cb:
        return f"ERROR: compute_bundle.json not found in {stock_dir}"

    mkt = cb.get("market", {})
    params = cb.get("params", {})
    f2 = cb.get("factor2", {})
    f3 = cb.get("factor3", {})
    f4 = cb.get("factor4", {})

    lines = []
    h = lambda s: lines.extend([f"## {s}", ""])
    h2 = lambda s: lines.extend([f"### {s}", ""])

    # Header
    name_cn = ft.get("name_cn", ts_code) if ft else ts_code
    lines.append(f"# 数据包 — {name_cn}（{ts_code}）")
    lines.append(f"*生成时间: {cb.get('meta',{}).get('date','—')}*  *金额: 百万元 RMB*")
    lines.append("")
    h("§MKT 市场数据")
    native_currency = mkt.get("native_currency", "RMB")
    lines.append(table(
        ["项目", "值", "说明"],
        [[f"股价({native_currency})", mkt.get("price_native", mkt.get("price_hkd","—")), mkt.get("price_source","—")],
         ["股价(RMB)", mkt.get("price_rmb","—"), f"FX={mkt.get('fx','—')}"],
         ["总股本(M)", mkt.get("shares_m","—"), "⚠️DB缺失" if mkt.get("shares_warning") else ""],
         [f"市值(M {native_currency})", mkt.get("mc_native", mkt.get("mc_hkd","—")), "=P×S"],
         ["市值(M RMB)", mkt.get("mc_rmb","—"), "=P×S×FX"]]
    ))

    h("§PARAMS 关键参数")
    lines.append(table(
        ["参数", "符号", "值", "来源"],
        [["要求回报率", "II", f"{params.get('II','—')}%", "threshold.json"],
         ["无风险利率", "Rf", f"{params.get('Rf','—')}%", "设定"],
         ["股息税率", "Q", pct(params.get('Q')), "持股渠道"],
         ["基准永续增长", "g_base", f"{params.get('g_base','—')}%", "Zone J moat"],
         ["B类惩罚", "b_penalty", pct(params.get('b_penalty')), "Zone J moat"],
         [f"最新DPS({native_currency})", "DPS", params.get('dps_latest','—'), "DB"],
         ["组合上限", "CAP", f"{params.get('PORTFOLIO_CAP_PCT','—')}%", ".env"]]
    ))

    # Income statement
    if ft:
        h("§IS 利润表趋势")
        income = ft.get("income_trend", [])
        if income:
            years = [str(r.get("fiscal_year","")) for r in income]
            rows = []
            for label, key in [("营收", "revenue"), ("营收YoY", "revenue_yoy"),
                               ("毛利率", "gross_margin"), ("归母NP", "n_income_attr_p"),
                               ("NP YoY", "np_yoy"), ("税前利润", "pretax_profit"),
                               ("有效税率", "effective_tax_rate"), ("D&A", "d_a")]:
                vals = []
                for r in income:
                    v = r.get(key)
                    if key in ("revenue_yoy","np_yoy","gross_margin","effective_tax_rate"):
                        vals.append(f"{v:.1f}%" if v is not None else "—")
                    else:
                        vals.append(safe(v))
                rows.append([label] + vals)
            lines.append(table(["指标"] + years, rows))

        # Per share
        ps = ft.get("per_share_trend", [])
        if ps:
            lines.append("")
            for label, key in [("EPS(RMB)", "eps"), ("DPS(RMB)", "dps")]:
                vals = [f"{r.get(key):.2f}" if r.get(key) else "—" for r in ps]
                rows.append([label] + vals)

        # Profitability
        prof = ft.get("profitability_ratios", [])
        if prof:
            lines.append("")
            for label, key in [("ROE", "roe"), ("ROA", "roa")]:
                vals = [f"{r.get(key):.1f}%" if r.get(key) else "—" for r in prof]
                rows.append([label] + vals)

    # Balance Sheet
    if ft:
        h("§BS 资产负债表(FY2025)")
        bs_list = ft.get("balance_sheet_trend", [])
        bs = bs_list[-1] if bs_list else {}
        lines.append(table(
            ["指标", "值", "来源"],
            [["总资产", safe(bs.get("total_assets")), "financial_trends"],
             ["货币资金", safe(bs.get("money_cap")), ""],
             ["贸易应收款", safe(bs.get("accounts_receiv")), ""],
             ["贸易应付款", safe(bs.get("acct_payable")), ""],
             ["归母权益", safe(bs.get("total_equity")), ""],
             ["有息负债率", f"{bs.get('debt_ratio','—')}%", ""]]
        ))

    # Cashflow
    if ft:
        h("§CF 现金流量表趋势")
        cf_list = ft.get("cashflow_trend", [])
        if cf_list:
            years = [str(r.get("fiscal_year","")) for r in cf_list]
            rows = []
            for label, key in [("OCF", "operating_cf"), ("Capex", "capex"),
                               ("股息支付", "dividends_paid"), ("FCF", "fcf")]:
                vals = [safe(r.get(key)) for r in cf_list]
                rows.append([label] + vals)
            lines.append(table(["指标"] + years, rows))

    # Factor 2
    if f2:
        h("§F2 因子2·穿透回报率粗算")
        lines.append(table(
            ["指标", "符号", "3年均值", "5年均值"],
            [["归母净利润", "NP", safe(f2.get("np_avg_3y")), safe(f2.get("np_avg_5y"))],
             ["Owner Earnings", "OE", safe(f2.get("oe_avg_3y")), safe(f2.get("oe_avg_5y"))],
             ["OCF/NP比率", "—", f2.get("ocf_np_ratio","—"), ""],
             ["G系数(M)", "M", f"{f2.get('M','—')}({f2.get('M_source','—')},{f2.get('M_samples','—')}样)", ""]]
        ))
        lines.append(f"R(NP)税前={safe(f2.get('r_np'))}%  R(OE)税前={safe(f2.get('r_oe'))}%")
        rej = f2.get("rejection",{})
        lines.append(f"否决门: S2={rej.get('s2','—')} S4-1={rej.get('s4_1','—')} S4-2={rej.get('s4_2','—')}")

    # §GG 预计算网格 (核心——借鉴旧版 §17.11)
    if f3:
        h("§GG 穿透回报率网格")
        aa_data = f3.get("aa", {})
        aa_vals = {}
        for period, key in [("3y", "3y"), ("5y", "5y"), ("all", "all")]:
            avg = f3.get("aa_avg", {}).get(key)
            if avg:
                aa_vals[f"AA_{period}"] = avg

        M_val = f2.get("M", 0.5) if f2 else 0.5
        Q_vals = [0.0, 0.05, 0.1, 0.2]
        MC = mkt.get("mc_rmb", 1) or 1

        rows = []
        for aa_name, aa_v in aa_vals.items():
            for q in Q_vals:
                gg = (aa_v / MC * 100) * (1 - q) - params.get("g_base",2.0) * (1 - params.get("b_penalty",0.25))
                gg_ii = gg - params.get("II",5.5)
                target_price = mkt.get("price_hkd",0) * gg / params.get("II",5.5) if params.get("II") else 0
                label = "★ 默认" if q == 0.1 else ""
                rows.append([aa_name, f"M={M_val:.2f}", f"Q={q*100:.0f}%", f"{gg:.1f}%", f"{gg_ii:+.1f}pct", f"{target_price:.2f} HKD", label])

        lines.append(table(
            ["AA变体", "M", "Q", "GG", "GG-II", "目标买入价", "备注"],
            rows
        ))
        lines.append(f"> ★ = 默认组合 (Q=10%, M=近3年均值). LLM选行不计算.")

        # GG三档
        gg_dict = f3.get("gg", {})
        lines.append(f"GG三档: 悲观={safe(gg_dict.get('pessimistic'))}% | 基准={safe(gg_dict.get('base'))}% | 乐观={safe(gg_dict.get('optimistic'))}%")

    # G系数网格 (借鉴旧版 §17.12)
    if f2 and ft:
        h("§G G系数网格")
        income_list = ft.get("income_trend", [])
        avg_da = sum(r.get("d_a",0) or 0 for r in income_list[-5:]) / 5 if income_list else 0
        C = f2.get("np_avg_3y", 0) or 0
        rows = []
        for g_val in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8]:
            H = avg_da * g_val
            oe = C + avg_da - H
            band = "轻" if g_val <= 0.9 else ("轻中" if g_val <= 1.1 else ("中" if g_val <= 1.3 else "重"))
            rows.append([f"{g_val:.1f}", safe(H), safe(oe), band])
        lines.append(table(["G", "维持Capex H=D×G", "OE=C+D-H", "档位"], rows))
        lines.append(f"> F(Capex/D&A中位数)={f2.get('capex_ratio_avg','—')}. LLM选行不计算.")

    # Lambda
    if f3:
        lam = f3.get("lambda", {})
        if lam:
            h("§λ 经营杠杆")
            for k, v in lam.items():
                lines.append(f"- λ_{k} = {safe(v)} M RMB")

    # DDM
    if f4:
        h("§DDM 估值")
        ddm = f4.get("ddm_v_hkd") or f4.get("DDM")
        lines.append(f"DDM公允价(HKD)={safe(ddm)} (base) → precise={safe(cb_p.get('factor4',{}).get('ddm_v_hkd') if cb_p else None)}")

        tiers = f4.get("tiers", [])
        if tiers:
            t_rows = []
            for t in tiers:
                t_rows.append([t.get("label",""), safe(t.get("price_hkd")), f"{t.get('safety_margin_pct','—')}%", f"{t.get('suggested_position_pct','—')}%"])
            lines.append(table(["阶梯", "价格(HKD)", "安全边际", "仓位"], t_rows))

    # Industry context
    if ind:
        h("§IND 行业分位")
        pcts = ind.get("percentiles", {})
        i_rows = []
        for k in ["revenue","gross_margin","roe","n_income_attr_p","total_assets","revenue_cagr_3y"]:
            v = pcts.get(k, {})
            i_rows.append([v.get("label",k), safe(v.get("value")), safe(v.get("industry_median")), f"P{v.get('percentile','—')}"])
        lines.append(table(["指标", "值", "行业中位数", "百分位"], i_rows))

    # Segments
    if seg:
        h("§SEG 分部收入")
        segs = seg.get("segments", [])
        # V9: segments may be dict(year→list) or flat list
        if isinstance(segs, dict):
            latest_year = seg.get("fiscal_years", ["2025"])[-1]
            segs = segs.get(latest_year, [])
        s_rows = []
        for s in segs:
            s_rows.append([s.get("name", s.get("segment_name","")), safe(s.get("revenue_m")), f"{s.get('revenue_pct','—')}%", f"{s.get('revenue_yoy_pct','—')}%", f"{s.get('gross_margin_pct','—')}%"])
        lines.append(table(["分部", "收入(M)", "占比", "YoY", "毛利率"], s_rows))

    # Moat
    if moat:
        h("§MOAT 护城河证据")
        ev = moat.get("moat_evidence", [])
        if ev:
            m_rows = [[e.get("type",""), e.get("strength",""), e.get("proof","")[:120]] for e in ev]
            lines.append(table(["类型", "强度", "证据"], m_rows))

        b_segs = moat.get("b_class_segments", [])
        if b_segs:
            b_rows = [[b.get("name",""), f"{b.get('revenue_pct','—')}%", b.get("classification",""), f"{b.get('penalty_pct','—')}%"] for b in b_segs]
            lines.append(table(["B类业务", "占比", "分类", "惩罚"], b_rows))

        vt = moat.get("value_trap_signals", [])
        if vt:
            lines.append("**价值陷阱信号:**")
            for s in vt: lines.append(f"- {s}")

    # Risks
    if risks:
        h("§RISK 风险因素")
        r_list = risks.get("principal_risks", risks.get("risks", []))
        if not r_list:
            # Text format
            for k, v in risks.items():
                if isinstance(v, str) and len(v) < 200:
                    lines.append(f"- {k}: {v}")
        else:
            for r in r_list:
                lines.append(f"- [{r.get('severity','?')}] {r.get('description','')}")

    # Governance
    if gov:
        h("§GOV 治理")
        lines.append(f"控股股东: {gov.get('controlling_shareholder','—')}")
        lines.append(f"透明度: {gov.get('transparency_flag','—')}")
        rpt = gov.get("related_party_transactions", [])
        if rpt:
            lines.append(f"关联交易: {len(rpt)}笔")

    # Audit
    if audit:
        h("§AUDIT 审计")
        lines.append(f"审计师: {audit.get('auditor','—')}")
        lines.append(f"审计意见: {audit.get('audit_opinion','—')}")

    # Data quality
    if dd:
        h("§QUAL 数据质量")
        tdp = dd.get('total_discount_pct')
        tdp_val = tdp.get('value') if isinstance(tdp, dict) else tdp
        lines.append(f"综合折价: {tdp_val if tdp_val is not None else '—'}%")
        for d in dd.get("discount_factors", []):
            lines.append(f"- {d.get('factor','')}: {d.get('discount_pct','—')}%")

    # Earnings quality
    if eq:
        lines.append("")
        h("§EQ 收益质量")
        ar = eq.get("ar_quality", {})
        ap = eq.get("ap_excess_check", {})
        nr = eq.get("non_recurring_items", {})
        lines.append(f"AR调整需求: {ar.get('ar_adjustment_needed','—')}")
        lines.append(f"AP超额融资: {ap.get('excess_financing_flag','—')}")
        lines.append(f"非经常调整: {nr.get('net_adjustment_m','—')} M")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="build_data_pack.py — JSON→Markdown数据包")
    p.add_argument("--code", required=True)
    p.add_argument("--output", help="Output directory")
    args = p.parse_args()

    if args.output:
        stock_dir = args.output
    else:
        code_base = args.code.replace(".HK","").replace(".SH","").replace(".SZ","")
        candidates = [d for d in os.listdir(OUTPUT_BASE)
                      if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(code_base)]
        if not candidates:
            print(f"ERROR: No output dir for {args.code}", file=sys.stderr); return 1
        stock_dir = os.path.join(OUTPUT_BASE, candidates[0])

    md = build_data_pack(stock_dir, args.code)
    path = os.path.join(stock_dir, "data_pack_agent.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ data_pack_agent.md → {path}")
    print(f"   📊 {len(md):,} chars / {md.count(chr(10))} lines")
    return 0

if __name__ == "__main__":
    sys.exit(main())
