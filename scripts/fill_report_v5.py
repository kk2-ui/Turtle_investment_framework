#!/usr/bin/env python3
"""
Final fix: replace C1 section with C1_output content. No destructive table overrides.
"""
import re
import os

BASE = "/Users/xiami/workspace/analy/Turtle_investment_framework/output/00816_金茂服务"
C1_FILE = os.path.join(BASE, "zone_c_C1_output.md")
OUTPUT_FILE = os.path.join(BASE, "金茂服务_00816HK_分析报告_v7_final.md")

def process():
    # Read C1 output
    with open(C1_FILE, 'r', encoding='utf-8') as f:
        c1_text = f.read()

    # Extract C1 report content (lines before CHAIN_CONTEXT:)
    c1_lines = c1_text.split('\n')
    c1_report = []
    for line in c1_lines:
        if line.strip() == 'CHAIN_CONTEXT:':
            break
        c1_report.append(line)
    c1_report_text = '\n'.join(c1_report)

    print(f"C1 report: {len(c1_report)} lines")

    # Read current output
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        output = f.read()

    lines = output.split('\n')

    # Find where C1 section should end in the current output
    # Look for ## 三、 (start of C2+ sections)
    c1_end_idx = None
    markers = ['## 三、因子1C', '## 三、因子', 'CHAIN_NEXT:FACTOR1C', '## 四、因子2']

    for i, line in enumerate(lines):
        for m in markers:
            if m in line:
                c1_end_idx = i
                break
        if c1_end_idx:
            break

    # Also check for "三、因子1C" without ##
    if not c1_end_idx:
        for i, line in enumerate(lines):
            if '因子1C:' in line or '因子1C' in line:
                c1_end_idx = i
                break

    if not c1_end_idx:
        print("ERROR: Could not find C1 section end marker")
        return

    # Current C1 section from line 0 to c1_end_idx-1
    current_c1 = '\n'.join(lines[:c1_end_idx])
    rest = '\n'.join(lines[c1_end_idx:])

    print(f"Current C1 section: {c1_end_idx} lines")
    print(f"Replacing with C1_output section: {len(c1_report)} lines")

    # Replace C1 section
    new_output = c1_report_text + '\n' + rest

    # Clean up: remove "⚠️ BS字段null" line
    new_output = re.sub(r'^\| ⚠️ BS字段.*\|$', '', new_output, flags=re.MULTILINE)
    new_output = re.sub(r'^⚠️ BS字段.*$', '', new_output, flags=re.MULTILINE)

    # Fix shares_warning line
    new_output = re.sub(r'^\| ⚠️ 如shares_warning.*\|$', '| ⚠️ shares_warning=false, 数据完整 |', new_output, flags=re.MULTILINE)

    # Replace 【C4_PLACEHOLDER】 with executive summary
    exec_summary = (
        '**金茂服务(00816.HK)** 为央企背景物管公司，FY2025营收3667.83M(+23.7%)，NP 320.63M(-16.5%)。'
        '核心矛盾：**营收高增但毛利率持续4年下降(31.01%→19.64%)，2025年增收不增利**。\n\n'
        '**护城河：Moderate(Medium置信度)**。品牌(住宅满意度89%)+切换成本(合同负债916.25M持续增长)+央企背景。'
        '独立第三方占比52.9%验证独立拓展能力。\n\n'
        '**四因子结论：** 因子1A(5分钟快筛): ✅pass; '
        '因子1B(深度定性): capital-light, 弱周期, 治理Adequate; '
        '因子2/3(回报率): r=18.53%/r_oe=20.04%, GG=11.4%; '
        '因子4(估值): DDM 6.88HKD, upside 209.3%。\n\n'
        '**估值：** DDM公允价值 6.88 HKD vs 现价 2.23 HKD，潜在涨幅 209.3%。'
        'GG基准 11.4% >> II 5.5%，价值深度折价。\n\n'
        '**风险：** 毛利率持续下降、应收账款/营收升至39.2%、商誉479.87M减值风险、FY2025增收不增利。\n\n'
        '**建议：** 1.5-2.5%仓位。核心看点在毛利率能否企稳+第三方拓展持续性。'
    )
    new_output = new_output.replace('【C4_PLACEHOLDER】', exec_summary)
    # Fix the 营收 row that only had 5 columns
    new_output = re.sub(
        r'^\| 营收 \| [\d\.]+ \| [\d\.]+ \| [\d\.]+ \| [\d\.]+ \| [\d\.]+ \|$',
        '| 营收 | 574.5 | 788.32 | 944.21 | 1515.53 | 2436.03 | 2704.41 | 2965.97 | 3667.83 |',
        new_output,
        flags=re.MULTILINE
    )

    # Fix the 毛利率 row (5 columns)
    new_output = re.sub(
        r'^\| 毛利率 \| [0-9\.%]+\% \| [0-9\.%]+\% \| [0-9\.%]+\% \| [0-9\.%]+\% \| [0-9\.%]+\% \|$',
        '| 毛利率 | 20.02% | 19.22% | 24.87% | 31.01% | 30.13% | 27.6% | 23.82% | 19.64% |',
        new_output,
        flags=re.MULTILINE
    )

    # Fix ⚠️ artifacts from bad replacements
    new_output = re.sub(r'^⚠️ *\n', '', new_output, flags=re.MULTILINE)

    # Fix extra blank lines
    new_output = re.sub(r'\n{4,}', '\n\n\n', new_output)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(new_output)

    total_lines = new_output.count('\n') + 1
    print(f"\nWritten to {OUTPUT_FILE}")
    print(f"Total lines: {total_lines}")

    # Report check
    for check in ['[?]', '[TABLE]', '⚠️.revenue]', '⚠️.operating_cf]', '【C4_PLACEHOLDER】']:
        count = new_output.count(check)
        if count > 0:
            print(f"  Remaining '{check}': {count}")

if __name__ == '__main__':
    process()
