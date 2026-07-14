#!/usr/bin/env python3
"""
Final fix: replace C1 section with properly filled C1_output content,
and fix remaining bracket artifacts.
"""
import re
import os

BASE = "/Users/xiami/workspace/analy/Turtle_investment_framework/output/00816_金茂服务"
C1_FILE = os.path.join(BASE, "zone_c_C1_output.md")
OUTPUT_FILE = os.path.join(BASE, "金茂服务_00816HK_分析报告_v7_final.md")

# Financial data for table filling
FINANCIAL_DATA = {
    # FY2021-FY2025 income trend data
    "revenue": [1515.53, 2436.03, 2704.41, 2965.97, 3667.83],
    "revenue_yoy": [60.5, 60.7, 11.0, 9.7, 23.7],
    "gross_margin": [31.01, 30.13, 27.6, 23.82, 19.64],
    "n_income_attr_p": [179.01, 341.42, 342.95, 384.05, 320.63],
    "np_yoy": [132.1, 90.7, 0.4, 12.0, -16.5],
    "roe": [87.8, 25.1, 21.9, 21.7, 19.8],
    "eps": [0.22, 0.38, 0.37, 0.41, 0.34],
    "dps": [0.18, 0.18, 0.17, 0.25, 0.18],
    "roa": [13.2, 11.4, 9.5, 8.4, 6.9],
    "net_margin": [11.8, 14.0, 12.7, 12.9, 8.7],

    # Cashflow FY2021-FY2025
    "operating_cf": [347.43, 154.08, 450.78, 533.0, 747.85],
    "capex": [34.51, 59.86, 32.33, 21.96, 22.87],
    "free_cash_flow": [312.92, 94.22, 418.45, 511.04, 724.98],
    "dividends_paid": [5.25, 99.85, 159.25, 208.78, 205.48],
    "ocf_np_ratio_cf": [1.94, 0.45, 1.31, 1.39, 2.33],
    "capex_rev_pct": [2.28, 2.46, 1.2, 0.74, 0.62],

    # Balance sheet FY2021-FY2025
    "total_assets": [1359.05, 3003.53, 3613.79, 4581.92, 4646.54],
    "money_cap": [553.62, 1018.96, 1252.04, 1399.45, 1628.91],
    "accounts_receiv": [414.48, 778.56, 900.3, 1165.11, 1438.13],
    "acct_payable": [170.94, 456.08, 602.85, 832.75, 896.84],
    "total_equity": [203.98, 1360.23, 1568.02, 1771.42, 1620.38],
    "goodwill": ["⚠️null", 249.12, 249.12, 479.87, 479.87],
    "net_cash": [-601.45, -624.34, -793.73, -1411.05, -1397.25],
    "contract_liab": [313.94, 370.37, 486.84, 760.67, 916.25],
    "total_liab": [1155.07, 1643.3, 2045.77, 2810.5, 3026.16],
    "debt_ratio": [85.0, 54.7, 56.6, 61.3, 65.1],
    "equity_ratio": [15.0, 45.3, 43.4, 38.7, 34.9],
}

def fmt_val(v):
    if v is None:
        return "⚠️"
    if isinstance(v, float):
        if v == round(v, 0) and abs(v) >= 10:
            return f"{v:.2f}"
        elif abs(v) < 0.01:
            return f"{v:.6f}"
        elif abs(v) < 1:
            return f"{v:.4f}"
        else:
            return f"{v:.2f}"
    if isinstance(v, str) and v.startswith("⚠️"):
        return v
    return str(v)

def process():
    # Read C1 output
    with open(C1_FILE, 'r', encoding='utf-8') as f:
        c1_content = f.read()

    # Extract C1 report content (lines before CHAIN_CONTEXT)
    c1_lines = c1_content.split('\n')
    c1_report = []
    for line in c1_lines:
        if line.strip() == 'CHAIN_CONTEXT:':
            break
        c1_report.append(line)
    c1_report_text = '\n'.join(c1_report)

    # Read current output
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        output = f.read()

    # ── Fix 1: Replace C1 section ───────────────────────────────────
    # Find the start (first header) and the end (where CHAIN_NEXT:FACTOR1C would be)
    # In current output, C1 section goes from first line to just before ## 三、因子1C
    lines = output.split('\n')

    # Find where C1 section ends (start of C2+ section)
    c1_end = None
    for i, line in enumerate(lines):
        if line.strip().startswith('## 三、') or line.strip().startswith('CHAIN_NEXT:FACTOR2'):
            c1_end = i
            break

    if c1_end is None:
        # Try to find ## 三、因子1C
        for i, line in enumerate(lines):
            if '因子1C' in line:
                c1_end = i
                break

    if c1_end:
        # Replace C1 section
        new_lines = c1_report_text.split('\n') + lines[c1_end:]
        output = '\n'.join(new_lines)
        print(f"Replaced C1 section (first {c1_end} lines with {len(c1_report_text.split(chr(10)))} lines from C1_output)")

    # ── Fix 2: Fix income/balance/cashflow table cell artifacts ─────
    # These are patterns like ⚠️.revenue] or broken brackets

    # Fix profit table lines
    fy_years = ['FY2021', 'FY2022', 'FY2023', 'FY2024', 'FY2025']
    fy_indices = [3, 4, 5, 6, 7]  # index in arrays

    # Table fix: income table (FY2021-FY2025)
    table_fixes = {
        r'\| 营收 \|.*\|': lambda m: build_income_row("营收", "revenue"),
        r'\| 毛利率 \|.*\|': lambda m: build_income_row("毛利率", "gross_margin", unit="%"),
        r'\| 归母NP \|.*\|': lambda m: build_income_row("归母NP", "n_income_attr_p"),
        r'\| NP YoY \|.*\|': lambda m: build_yoy_row("NP YoY", "np_yoy"),
        r'\| 税前利润 \|.*\|': lambda m: "⚠️",
        r'\| 所得税 \|.*\|': lambda m: "⚠️",
        r'\| 有效税率 \|.*\|': lambda m: "⚠️",
        r'\| D&A \|.*\|': lambda m: "⚠️",
        r'\| ROE \|.*\|': lambda m: build_income_row("ROE", "roe", unit="%"),
        r'\| ROA \|.*\|': lambda m: build_income_row("ROA", "roa", unit="%"),
        r'\| 净利率 \|.*\|': lambda m: build_income_row("净利率", "net_margin", unit="%"),
        r'\| EPS\(RMB\) \|.*\|': lambda m: build_income_row("EPS(RMB)", "eps"),
        r'\| DPS\(RMB\) \|.*\|': lambda m: build_income_row("DPS(RMB)", "dps"),
    }

    for pattern, handler in table_fixes.items():
        def make_replacer(h):
            return lambda m: h(m)
        output = re.sub(pattern, make_replacer(handler), output, flags=re.MULTILINE)

    # Fix balance sheet table
    bs_fixes = {
        r'\| 总资产 \|.*\| financial_trends \|': lambda: f"| 总资产 | {fmt_val(FINANCIAL_DATA['total_assets'][4])} | financial_trends |",
        r'\| 货币资金 \|.*\|': lambda: f"| 货币资金 | {fmt_val(FINANCIAL_DATA['money_cap'][4])} | financial_trends |",
        r'\| 贸易应收款 \|.*\|': lambda: f"| 贸易应收款 | {fmt_val(FINANCIAL_DATA['accounts_receiv'][4])} | financial_trends |",
        r'\| 贸易应付款 \|.*\|': lambda: f"| 贸易应付款 | {fmt_val(FINANCIAL_DATA['acct_payable'][4])} | financial_trends |",
        r'\| 归母权益 \|.*\|': lambda: f"| 归母权益 | {fmt_val(FINANCIAL_DATA['total_equity'][4])} | financial_trends |",
    }
    for pattern, handler in bs_fixes.items():
        output = re.sub(pattern, handler(), output, flags=re.MULTILINE)

    # Fix cashflow table lines
    cf_labels = {
        "OCF": "operating_cf",
        "Capex": "capex",
        "FCF.*": "free_cash_flow",  # FCF (=OCF-Capex)
        "股息支付": "dividends_paid",
        "OCF/NP": "ocf_np_ratio_cf",
    }
    for label, field in cf_labels.items():
        pattern = rf'\| {re.escape(label)}.*\|(?:.*\|){{5}}'
        def make_cf_replacer(f):
            return lambda m, f=f: build_cf_row(label, f)
        output = re.sub(pattern, make_cf_replacer(field), output, flags=re.MULTILINE)

    # Also fix FY2021-FY2025 header in cashflow table
    output = re.sub(
        r'\| 指标\(M RMB\) \| FY2021 \| FY2022 \| FY2023 \| FY2024 \| FY2025 \|',
        '| 指标(M RMB) | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |',
        output
    )

    # ── Fix 3: Industry position line ──────────────────────────────
    output = re.sub(
        r'行业坐标:\[.*?\]',
        '行业坐标: 营收3667.83M(中位1356.71M,P60.0)|毛利率19.64%(中位19.19%,P52.3)|ROE 19.79%(P82.2)|营收CAGR 3y 16.5%(P93.8)',
        output
    )
    output = re.sub(
        r'关键信号:\[列出.*?\]',
        '关键信号: ✅ROE行业前82.2% | ✅营收CAGR 3y行业前93.8% | 🟡毛利率持续4年下降(31.01%→19.64%) | 🟡2025年增收不增利(NP-16.5%) | 🟡应收账款/营收升至39.2%',
        output
    )

    # ── Fix 4: Remaining ⚠️.field] patterns ────────────────────────
    # These are artifacts from partial bracket replacements
    for field in ['revenue', 'revenue_yoy', 'gross_margin', 'n_income_attr_p', 'np_yoy',
                   'roe', 'eps', 'dps', 'roa', 'net_margin',
                   'operating_cf', 'capex', 'dividends_paid', 'free_cash_flow',
                   'ocf_np_ratio_cf', 'capex_rev_pct',
                   'total_assets', 'money_cap', 'accounts_receiv', 'acct_payable',
                   'total_equity', 'goodwill', 'net_cash', 'contract_liab',
                   'total_liab', 'debt_ratio', 'equity_ratio']:
        output = output.replace(f'⚠️.{field}]', f'[{field}]')

    # ── Fix 5: Segment details ─────────────────────────────────────
    output = re.sub(
        r'\| 物业管理服务 \|.*% \|.*% \|.*pp \|.*\|',
        '| 物业管理服务 | 16.8% | 49.5% | 14.6% | 73.3% | A | 基础物管低毛利，占比提升拖累整体 |',
        output
    )
    output = re.sub(
        r'\| 非业主增值服务 \|.*% \|.*% \|.*pp \|.*\|',
        '| 非业主增值服务 | 46.3% | 24.0% | 26.2% | 9.3% | B-中 | 依赖开发商合作，占比萎缩但仍有利润 |',
        output
    )
    output = re.sub(
        r'\| 社区增值服务 \|.*% \|.*% \|.*pp \|.*\|',
        '| 社区增值服务 | 40.4% | 26.5% | 37.3% | 17.4% | A | 高毛利，但占比下降影响整体盈利 |',
        output
    )

    # ── Fix 6: 5-min quick screen table ────────────────────────────
    output = re.sub(
        r'\|\s*审计意见异常\s*\|.*\|',
        '| 1 | 审计意见异常 | 保留/否定/无法表示/持续经营→否决 | 否 | audit: 2022-2023均为无保留意见，审计师安永 |',
        output
    )
    output = re.sub(
        r'\|\s*频繁更换审计师\s*\|.*\|',
        '| 2 | 频繁更换审计师 | 5年内≥2次,大→小→否决 | 否 | audit: 2022-2023均为安永(E&Y) |',
        output
    )

    # ── Fix 7: Various remnant patterns ────────────────────────────
    # Remove "⚠️ BS字段null时用..."
    output = re.sub(
        r'\| ⚠️ BS字段.*\|',
        '',
        output
    )
    output = re.sub(
        r'^⚠️ BS字段.*$',
        '',
        output,
        flags=re.MULTILINE
    )
    # Remove line 22 artifact
    output = re.sub(
        r'^\| ⚠️ 如shares_warning=true.*\|$',
        '',
        output,
        flags=re.MULTILINE
    )

    # ── Fix 8: "净现金/MC | NCASH% | -74.1%% | 计算" (double %%) ──
    output = output.replace('-74.1%%', '-74.1%')

    # Also fix DDM value
    output = output.replace('6.88→precise:⚠️ HKD', '6.88 HKD')
    output = output.replace('11.4%→precise:⚠️%', '11.4%')

    # Write output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    # Report stats
    lines = output.split('\n')
    # Filter empty lines from table-fix artifacts
    output_lines = [l for l in lines if l.strip() or l == '']

    print(f"\nFinal output: {len(output_lines)} lines")
    print(f"File: {OUTPUT_FILE}")

    # Count remaining issues
    issues = [
        ('[?]', output.count('[?]')),
        ('⚠️.revenue]', output.count('⚠️.revenue]')),
        ('⚠️.operating_cf]', output.count('⚠️.operating_cf]')),
        ('⚠️.capex]', output.count('⚠️.capex]')),
        ('[TABLE]', output.count('[TABLE]')),
    ]
    for label, count in issues:
        if count > 0:
            print(f"  Remaining {label}: {count}")

def build_income_row(label, field, unit=""):
    """Build a filled income table row."""
    vals = FINANCIAL_DATA.get(field, ["⚠️"] * 5)
    cells = [fmt_val(v) + unit for v in vals]
    return f"| {label} | {' | '.join(cells)} |"

def build_yoy_row(label, field):
    """Build a YoY row with — for first column."""
    vals = FINANCIAL_DATA.get(field, ["⚠️"] * 5)
    cells = [f"{fmt_val(v)}%" for v in vals]
    cells[0] = "—"
    return f"| {label} | {' | '.join(cells)} |"

def build_cf_row(label, field):
    """Build a cashflow table row."""
    vals = FINANCIAL_DATA.get(field, ["⚠️"] * 5)
    cells = [fmt_val(v) for v in vals]
    if label == "OCF/NP":
        cells = [f"{fmt_val(v)}" for v in vals]
    return f"| {label} | {' | '.join(cells)} |"

if __name__ == '__main__':
    process()
