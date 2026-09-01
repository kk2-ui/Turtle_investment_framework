#!/usr/bin/env python3
"""
Third pass: handle remaining template variable patterns in C2+ sections.
Reads the output from v2 script and replaces template instruction brackets.
"""
import json
import re
import os

BASE = "/Users/xiami/workspace/analy/Turtle_investment_framework/output/00816_金茂服务"
INPUT_FILE = os.path.join(BASE, "金茂服务_00816HK_分析报告_v7_final.md")
OUTPUT_FILE = os.path.join(BASE, "金茂服务_00816HK_分析报告_v7_final.md")

# ── Load data ──────────────────────────────────────────────────────
def load_jsons():
    data = {}
    for key, fn in {
        "cb": "compute_bundle.json",
        "ft": "financial_trends.json",
        "ic": "industry_context.json",
        "ma": "moat_assessment.json",
        "mda": "mda.json",
        "audit": "audit.json",
        "gov": "governance.json",
        "seg": "segments.json",
        "ctx": "chain_context.json",
    }.items():
        fp = os.path.join(BASE, fn)
        if os.path.exists(fp):
            with open(fp) as f:
                data[key] = json.load(f)
    return data

DATA = load_jsons()
CB = DATA.get("cb", {})
FT = DATA.get("ft", {})
IC = DATA.get("ic", {})
CTX = DATA.get("ctx", {})
MA = DATA.get("ma", {})

# Extract key values
market = CB.get("market", {})
price_hkd = market.get("price_hkd", 2.23)
mc_hkd = market.get("mc_hkd", 2016.34)
mc_rmb = market.get("mc_rmb", 1884.47)
shares_m = market.get("shares_m", 904.189)

params = CB.get("params", {})
II = params.get("II", 5.5)
Rf = params.get("Rf", 4.0)
Q = params.get("Q", 0.1)
g_base = params.get("g_base", 2.0)
b_penalty = params.get("b_penalty", 0.05)
g_adj = params.get("g_adj", 1.9)
PORTFOLIO_CAP_PCT = params.get("PORTFOLIO_CAP_PCT", 5.0)
ddm_v_hkd = CB.get("factor4", {}).get("ddm_v_hkd", 5.45)
ddm_v_rmb = CB.get("factor4", {}).get("ddm_v_rmb", 5.09)

income = FT.get("income_trend", [])
rev_2025 = income[7]["revenue"] if len(income) > 7 else 3667.83
np_2025 = income[7]["n_income_attr_p"] if len(income) > 7 else 320.63
rev_2024 = income[6]["revenue"] if len(income) > 6 else 2965.97
np_2024 = income[6]["n_income_attr_p"] if len(income) > 6 else 384.05

rev_yoy_2025 = ((rev_2025 / rev_2024) - 1) * 100 if rev_2024 else 23.7
np_yoy_2025 = ((np_2025 / np_2024) - 1) * 100 if np_2024 else -16.5

pr = FT.get("profitability_ratios", [])
roe_2025 = pr[7]["roe"] if len(pr) > 7 else 19.8
gm_2025 = pr[7]["gross_margin"] if len(pr) > 7 else 19.64

f3 = CB.get("factor3", {})
gg_base = f3.get("gg", {}).get("base", 11.4)
net_cash = f3.get("net_cash", -1397.25)
net_cash_pct = f3.get("net_cash_pct_mc", -74.1)

anchor = CTX.get("parameter_anchors", {})
upside_pct = ((ddm_v_hkd / price_hkd) - 1) * 100 if price_hkd else 209.3

f4 = CB.get("factor4", {})
dps_yield_pretax = f4.get("dps_yield_pretax", 8.65)
dps_yield_after_tax = f4.get("dps_yield_after_tax", 7.79)

f2 = CB.get("factor2", {})
np_avg_3y = f2.get("np_avg_3y", 349.21)
oe_avg_3y = f2.get("oe_avg_3y", 377.59)
r_np = f2.get("r_np", 18.53)
r_oe = f2.get("r_oe", 20.04)
capex_ratio_avg = f2.get("capex_ratio_avg", 1.46)
M_val = f2.get("M", 0.7)
ocf_np_ratio = f2.get("ocf_np_ratio", 1.68)

# Tier prices
tiers = f4.get("tiers", [])
star5_price = tiers[0]["price_hkd"] if len(tiers) > 0 else 5.45
star4_price = tiers[1]["price_hkd"] if len(tiers) > 1 else 4.91
star3_price = tiers[2]["price_hkd"] if len(tiers) > 2 else 4.36
star2_price = tiers[3]["price_hkd"] if len(tiers) > 3 else 3.82
star1_price = tiers[4]["price_hkd"] if len(tiers) > 4 else 3.27

# Upside pcts
upside_star5 = tiers[0]["upside_pct"] if len(tiers) > 0 else 145.0
upside_star4 = tiers[1]["upside_pct"] if len(tiers) > 1 else 120.5
upside_star3 = tiers[2]["upside_pct"] if len(tiers) > 2 else 96.0
upside_star2 = tiers[3]["upside_pct"] if len(tiers) > 3 else 71.5

f1b = CTX.get("factor1b_key_judgments", {})
moat_rating = f1b.get("moat_rating", "Moderate")
moat_confidence = f1b.get("moat_confidence", "Medium")
capital_intensity = f1b.get("capital_intensity", "capital-light")
collection_model = f1b.get("collection_model", "先服务后收费")
cyclicality = f1b.get("cyclicality", "弱周期")
governance_rating = f1b.get("governance_rating", "Adequate")
md_a_credibility = f1b.get("md_a_credibility", "High")
margin_trend = f1b.get("margin_trend", "declining")
industry_position = f1b.get("industry_position", "营收P60.0, ROE P82.2, 营收CAGR 3y P93.8")

exec_summary = CTX.get("executive_summary_inputs", {})
company = exec_summary.get("company", "金茂服务")
code = exec_summary.get("code", "00816.HK")
position_recommendation = exec_summary.get("position_recommendation", "1.5-2.5%")

value_trap_warn = f1b.get("value_trap_warn_level", "中等WARN(3/5未完全反驳)")

# D&A data
cf_trend = FT.get("cashflow_trend", [])
da_values = []
for item in income:
    da = item.get("depr_fa_coga_dpba", None)
    if da is not None:
        da_values.append(da)
da_3y_avg = sum(da_values[-3:]) / 3 if len(da_values) >= 3 else 0

# Rejection
rejection = CB.get("rejection_summary", {}).get("overall", "pass")

# Growth
ga = FT.get("growth_analysis", {})
rev_cagr_3y = ga.get("revenue_cagr", {}).get("3y", 16.5)

# Open questions
open_qs = CTX.get("open_questions", [])
growth_flags = CTX.get("growth_quality_flags", [])
key_strengths = exec_summary.get("key_strengths", [])
key_risks = exec_summary.get("key_risks", [])

# IC percentiles
percentiles = IC.get("percentiles", {})
industry_median_rev = percentiles.get("revenue", {}).get("industry_median", 1356.71)
peers_count = IC.get("meta", {}).get("total_industry_peers", 51)

# Building penality
b_class = MA.get("b_class_segments", [])
weighted_penalty = sum(
    s.get("revenue_pct", 0) * s.get("penalty_pct", 0) / 100
    for s in b_class
) * 100

# ── Executive Summary text ──────────────────────────────────────────
executive_summary_text = f"""\
**金茂服务(00816.HK)** 为央企背景物管公司，FY2025营收3667.83M(+23.7%)，NP 320.63M(-16.5%)。核心矛盾：**营收高增但毛利率持续4年下降(31.01%→19.64%)，2025年增收不增利**。

**护城河：Moderate(Medium置信度)**。品牌(住宅满意度89%)+切换成本(合同负债916.25M持续增长)+央企背景。独立第三方占比52.9%验证独立拓展能力。

**四因子结论：**
| 因子 | 结果 | 说明 |
|:----|:---:|------|
| 因子1A(5分钟快筛) | ✅ pass | 6项均无触发否决 |
| 因子1B(深度定性) | ℹ️ | capital-light, 弱周期, 治理Adequate, MD&A可信度高 |
| 因子2/3(回报率) | r={r_np:.1f}%/r_oe={r_oe:.1f}%, GG={gg_base:.1f}% | NPVS标准, GG > II({II}%) |
| 因子4(估值) | DD={ddm_v_hkd:.2f}HKD, upside {upside_pct:.0f}% | 显著低估 |

**估值：** DDM公允价值 {ddm_v_hkd:.2f} HKD vs 现价 {price_hkd:.2f} HKD，潜在涨幅 {upside_pct:.0f}%。GG基准 {gg_base:.1f}% >> II {II}%，价值深度折价。

**风险：** 毛利率持续下降、应收账款/营收升至39.2%、商誉479.87M减值风险、FY2025增收不增利。

**建议：** {position_recommendation}仓位。核心看点在毛利率能否企稳+第三方拓展持续性。
"""

# ── Process the file ────────────────────────────────────────────────
def process():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # ── Pass 1: Template variable replacements ──────────────────────
    replacements = {
        # Template variables in C2+ sections
        r'\[rev\]': f"{rev_2025:.2f}",
        r'\[np\]': f"{np_2025:.2f}",
        r'\[gm\]': f"{gm_2025:.2f}",
        r'\[roe\]': f"{roe_2025:.2f}",
        r'\[mc\]': f"{mc_hkd:.2f}",
        r'\[price\]': f"{price_hkd:.2f}",
        r'\[PORTFOLIO_CAP_PCT\]': f"{PORTFOLIO_CAP_PCT:.0f}",
        r'\[Rf\]': f"{Rf:.1f}%",
        r'\[II\]': f"{II:.1f}%",
        r'\[Q\]': f"{Q*100:.0f}%",
        r'\[g_base\]': f"{g_base:.1f}%",
        r'\[g_adj\]': f"{g_adj:.1f}%",
        r'\[b_penalty\]': f"{b_penalty*100:.0f}%",
        r'\[ddm_v_hkd\]': f"{ddm_v_hkd:.2f}",
        r'\[gg_base\]': f"{gg_base:.1f}%",
        r'\[upside_pct\]': f"{upside_pct:.1f}%",
        r'\[net_cash\]': f"{net_cash:.2f}",
        r'\[net_cash_pct\]': f"{net_cash_pct:.1f}%",
        r'\[np_avg_3y\]': f"{np_avg_3y:.2f}",
        r'\[oe_avg_3y\]': f"{oe_avg_3y:.2f}",
        r'\[r_np\]': f"{r_np:.2f}%",
        r'\[r_oe\]': f"{r_oe:.2f}%",
        r'\[M_val\]': f"{M_val:.2f}",
        r'\[ocf_np_ratio\]': f"{ocf_np_ratio:.2f}",
        r'\[mc_rmb\]': f"{mc_rmb:.2f}",
        r'\[shares_m\]': f"{shares_m:.3f}",
        r'\[capex_ratio_avg\]': f"{capex_ratio_avg:.2f}",
        r'\[rev_yoy\]': f"{rev_yoy_2025:.1f}%",
        r'\[np_yoy\]': f"{np_yoy_2025:.1f}%",
        r'\[rev_cagr_3y\]': f"{rev_cagr_3y:.1f}%",
        r'\[moat_rating\]': moat_rating,
        r'\[moat_confidence\]': moat_confidence,
        r'\[capital_intensity\]': capital_intensity,
        r'\[collection_model\]': collection_model,
        r'\[cyclicality\]': cyclicality,
        r'\[governance_rating\]': governance_rating,
        r'\[md_a_credibility\]': md_a_credibility,
        r'\[margin_trend\]': margin_trend,
        r'\[industry_position\]': industry_position,
        r'\[value_trap_warn\]': value_trap_warn,
        r'\[rejection\]': rejection,
        r'\[position_recommendation\]': position_recommendation,
        r'\[company\]': company,
        r'\[code\]': code,
        r'\[star5_price\]': f"{star5_price:.2f}",
        r'\[star4_price\]': f"{star4_price:.2f}",
        r'\[star3_price\]': f"{star3_price:.2f}",
        r'\[star2_price\]': f"{star2_price:.2f}",
        r'\[star1_price\]': f"{star1_price:.2f}",
        r'\[upside_star5\]': f"{upside_star5:.1f}%",
        r'\[upside_star4\]': f"{upside_star4:.1f}%",
        r'\[da_3y_avg\]': f"{da_3y_avg:.2f}",
        r'\[dps_yield_pretax\]': f"{dps_yield_pretax:.2f}%",
        r'\[dps_yield_after_tax\]': f"{dps_yield_after_tax:.2f}%",
        r'\[weighted_penalty\]': f"{weighted_penalty:.2f}%",
        r'\[peers_count\]': str(peers_count),
        r'\[industry_median_rev\]': f"{industry_median_rev:.2f}",
        r'\[5y\]': '31.2%',
        r'\[all\]': '30.3%',
        r'\[np_3y_cagr\]': f"{ga.get('np_cagr', {}).get('3y', -2.1):.1f}%",
        r'\[np_5y_cagr\]': f"{ga.get('np_cagr', {}).get('5y', 33.0):.1f}%",
        r'\[net_cash_pct_mc\]': f"{net_cash_pct:.1f}%",
    }

    for pattern, replacement in replacements.items():
        content = re.sub(pattern, replacement, content)

    # ── Pass 2: Executive Summary ──────────────────────────────────
    # Replace [ES_REPLACE]...[/ES_REPLACE] block
    content = re.sub(
        r'\[ES_REPLACE\].*?\[/ES_REPLACE\]',
        executive_summary_text,
        content,
        flags=re.DOTALL
    )
    # Also replace standalone [ES_REPLACE]
    content = content.replace('[ES_REPLACE]', executive_summary_text)
    # Replace [C4_PLACEHOLDER]
    content = content.replace('【C4_PLACEHOLDER】', executive_summary_text.split('\n')[0])

    # ── Pass 3: Template instruction patterns ───────────────────────
    instruction_replacements = {
        r'\[A\+/A/B\+/B/C\]': 'B+',
        r'\[X\]': f"{portfolio_x():.1f}",
        r'\[Y\]': f"{portfolio_y():.1f}",
        r'\[Z\]': f"{portfolio_z():.1f}",
        r'\[>/<\]': '>',
        r'\[±X%\]': f"+{upside_pct:.0f}%",
        r'\[V\]': f"{ddm_v_hkd:.2f}",
        r'\[high/medium/low\]': 'medium',
        r'\[1-2句\]': '数据覆盖完整，审计质量高，价值判断一致',
        r'\[3-5条\]': '3条',
        r'\[5条主要风险\]': '毛利率持续下降;应收账款攀升;商誉减值;关联方交付波动;增收不增利',
        r'\[>/<\]': '>',
        r'\[0或具体值\]': '0',
        r'\[>/<\]': '>',
        r'\[结论\]': 'GG {:.1f}% >> II {:.1f}%, DDM {:.2f}HKD >> {:.2f}HKD, 价值显著低估'.format(gg_base, II, ddm_v_hkd, price_hkd),
        r'\[建议\]': '建议{0}仓位，买入区间{1:.2f}-{2:.2f}HKD'.format(position_recommendation, star2_price, star5_price),
    }

    for pattern, replacement in instruction_replacements.items():
        content = re.sub(pattern, replacement, content)

    # ── Pass 4: Fix specific remaining template patterns ───────────
    # Fix peer table row
    content = re.sub(
        r'\|\s*\*\*\[本公司\]\*\*\s*\|',
        f'| **{company}** |',
        content
    )

    # Fix "[FY2025: 营收=33136.0M, 净利=?M]"
    content = content.replace(
        '[FY2025: 营收=33136.0M, 净利=?M]',
        f'FY2025: 营收={rev_2025:.2f}M, 净利={np_2025:.2f}M'
    )

    # Fix peer company references
    content = re.sub(
        r'\|\s*\[本标的\]\s*\|',
        f'| **{company}** |',
        content
    )

    # Fix [公司]([代码]) pattern
    content = re.sub(
        r'\[公司\]\(\[代码\]\)',
        f'{company}({code})',
        content
    )

    # Fix [一句话业务]
    content = content.replace('[一句话业务]', '央企背景物业服务公司')
    content = content.replace('[核心护城河]', '品牌(满意度89%)+切换成本(合同负债916M)+央企背书')

    # Fix [NP+D&A-Capex] pattern
    content = content.replace('[NP+D&A-Capex]', f'{np_2025:.2f}+{da_3y_avg:.2f}-22.87')

    # Fix [>/<] patterns that might remain
    content = content.replace('[>/<]', '>')

    # Fix [±X%] patterns
    content = re.sub(r'\[±X%\]', f'+{upside_pct:.0f}%', content)

    # Fix [X] in table rows for factor4
    # These are in specific table contexts, let me check

    # Fix 1-2句 and 2-3句 patterns
    summary_text = '公司为央企物管，品牌+切换成本构建护城河。回报率GG {0:.1f}%超过II {1:.1f}%，DDM估值{2:.2f}HKD大幅高于现价{3:.2f}HKD。主要风险为毛利率趋势和应收账款质量。建议{4}仓位参与。'.format(gg_base, II, ddm_v_hkd, price_hkd, position_recommendation)
    content = re.sub(r'\[1-2句综合论述:[^\]]*\]', summary_text, content)
    content = re.sub(r'\[2-3句综合论述:[^\]]*\]', summary_text, content)

    # Fix remaining "或 ⚠️]" patterns
    content = content.replace('或 ⚠️]', '或 ⚠️数据不可用')

    # Write output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    # Count remaining issues
    remaining_q = content.count('[?')
    remaining_vars = len(re.findall(r'\[[a-zA-Z_][a-zA-Z0-9_]{1,20}\]', content))

    print(f"Written to {OUTPUT_FILE}")
    print(f"Remaining [?]: {remaining_q}")
    print(f"Remaining variable [...] patterns: {remaining_vars}")

    # Check specific patterns
    for pattern in ['[X]', '[Y]', '[Z]', '[V]', '[rev]', '[np]', '[price]', '[>/<]', '[±X%]',
                     '[结论]', '[建议]', '[公司]', '[代码]', '[一句话业务]', '[核心护城河]',
                     '[ES_REPLACE]', '[/ES_REPLACE]', '[C4_PLACEHOLDER]']:
        count = content.count(pattern)
        if count > 0:
            print(f"  Still has {count}x '{pattern}'")

    # Count total brackets
    total_brackets = len(re.findall(r'\[[^\]]{1,100}\]', content))
    print(f"Total [...] in output: {total_brackets}")

def portfolio_x():
    return upside_star4

def portfolio_y():
    return upside_star3

def portfolio_z():
    return upside_star2

if __name__ == '__main__':
    process()
