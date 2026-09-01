#!/usr/bin/env python3
"""Build comprehensive data_pack_report.md from pdf_sections JSON files.

Combines:
- Balance sheet (consolidated + parent) from STMT text
- Cash flow statement (consolidated + parent) from STMT text
- D&A from DAN section
- Income statement from Tushare (cross-referenced)
- Other sections: P2, P3, P4, P6, P13, SUB
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime

# Paths
BASE = "/Users/xiami/Desktop/analy/Turtle_investment_framework/output/600519_贵州茅台"
YEARS = [2021, 2022, 2023, 2024, 2025]

# Financial statement line items we want to extract with their regex patterns
# NOTE: All values in STMT are in raw yuan (元), we convert to 百万元 (/1,000,000)

BS_LINES_CONSOL = [
    # Assets
    ("货币资金", r'货币资金\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("拆出资金", r'拆出资金\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("交易性金融资产", r'交易性金融资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("应收票据", r'应收票据\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("应收账款", r'应收账款\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("应收款项融资", r'应收款项融资\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("预付款项", r'预付款项\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("其他应收款", r'其他应收款\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("存货", r'存货\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("一年内到期的非流动资产", r'一年内到期的非流动资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("其他流动资产", r'其他流动资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("流动资产合计", r'流动资产合[计\n]\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    # Non-current assets
    ("长期股权投资", r'长期股权投资\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("其他权益工具投资", r'其他权益工具投资\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("其他非流动金融资产", r'其他非流动金融资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("固定资产", r'固定资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("在建工程", r'在建工程\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("使用权资产", r'使用权资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("无形资产", r'无形资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("开发支出", r'开发支出\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("长期待摊费用", r'长期待摊费用\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("递延所得税资产", r'递延所得税资产\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("非流动资产合计", r'非流动资产合[计\n]\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("资产总计", r'资产[总计合][计]?\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    # Liabilities
    ("短期借款", r'(?<!一)短期借款\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("应付票据", r'应付票据\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("应付账款", r'应付账款\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("合同负债", r'合同负债\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("应付职工薪酬", r'应付职工薪酬\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("应交税费", r'应交税费\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("其他应付款", r'其他应付款\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("流动负债合计", r'流动负债合[计\n]\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("长期借款", r'(?<!一)长期借款\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("负债合计", r'负债[总计合][计]?\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    # Equity
    ("股本", r'股本\s+(?:\d+\s+)?([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("资本公积", r'资本公积\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("其他综合收益", r'其他综合收益\s+(-?[\d,\-]+(?:\.\d+)?)\s+(-?[\d,\-]+(?:\.\d+)?)'),
    ("盈余公积", r'盈余公积\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("未分配利润", r'未分配利润\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("归母权益合计", r'(?:归属于母公司|归母).*?合[计\n]\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
]

CF_LINES_CONSOL = [
    ("经营活动CF", r'经营活动(?:产生)?的?现金流量净额\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("投资活动CF", r'投资活动(?:产生)?的?现金流量净额\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("筹资活动CF", r'筹资活动(?:产生)?的?现金流量净额\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("现金净增加额", r'现金及现金等价物净增加额\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("期初现金", r'期初现金及现金等价物余额\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("期末现金", r'期末现金及现金等价物余额\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("销售商品收到的现金", r'销售商品.*?收到的现金\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("购买商品支付的现金", r'购买商品.*?支付的现金\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("支付给职工", r'支付给职工.*?支付的现金\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("支付的各项税费", r'支付的各项税费\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("购建固定资产", r'购建固定资产.*?支付的现金\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
    ("分配股利", r'分配股利.*?支付的现金\s+([\d,\-]+(?:\.\d+)?)\s+([\d,\-]+(?:\.\d+)?)'),
]

# More specific patterns for BS that handle the table structure better
BS_SPECIFIC = {
    "短期借款": [r'短期借款\s+[\d]*\s*(-?[\d,]+\.\d+)', r'短期借款\s+[\d]*\s*(-?[\d,]+\.\d+)'],
    "拆出资金": [r'拆出资金\s+[\d]*\s*(-?[\d,]+\.\d+)', r'拆出资金\s+[\d]*\s*(-?[\d,]+\.\d+)'],
    "发放贷款和垫款": [r'发放贷款和垫款\s+[\d]*\s*(-?[\d,]+\.\d+)', r'发放贷款和垫款\s+[\d]*\s*(-?[\d,]+\.\d+)'],
}


def parse_number(s):
    """Parse a number string that may contain commas and negative signs."""
    if not s or s.strip() == '':
        return None
    s = s.strip()
    # Handle negative numbers with parentheses
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    s = s.replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None


def yuan_to_millions(val):
    """Convert yuan to 百万元."""
    if val is None:
        return None
    return round(val / 1_000_000, 2)


def extract_between(text, start_marker, end_markers, include_start=True):
    """Extract text between start_marker and the first end_marker encountered."""
    start = text.find(start_marker)
    if start < 0:
        return ""
    if not include_start:
        start += len(start_marker)

    end = len(text)
    for marker in end_markers:
        pos = text.find(marker, start + 1)
        if pos > 0 and pos < end:
            end = pos

    return text[start:end]


def extract_bs_data(stmt_text, report_year):
    """Extract balance sheet line items from consolidated BS section."""
    bs_text = extract_between(stmt_text, "合并资产负债表",
                               ["合并利润表", "合并损益表", "母公司资产负债表"])
    if not bs_text:
        return {}

    result = {}

    # The BS has two columns: current year-end and prior year-end
    # We need to identify which column corresponds to which year
    # by reading the header line

    # Try to find header with year info
    header_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日.*?(\d{4})年(\d{1,2})月(\d{1,2})日', bs_text)
    if header_match:
        col1_year = int(header_match.group(1))
        col2_year = int(header_match.group(4))
    else:
        # If report_year is YYYY, the BS header is YYYY-12-31 and (YYYY-1)-12-31
        col1_year = report_year
        col2_year = report_year - 1

    # We want the current year column (col1 for this report year)
    target_year = report_year

    # Extract key lines with patterns
    # The BS has format: 项目名称 附注号 金额1 金额2
    # But the text may be split across lines

    # Clean the text: join continuation lines
    lines = bs_text.split('\n')

    # Parse table data line by line
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('---') or line_clean.startswith('|'):
            continue

        # Try to match: Chinese name + optional note number + amount1 + amount2
        # Pattern: (item_name) \s+ (note_num)? \s+ (amount1) \s+ (amount2)
        # Amounts are like 59,295,822,956.89 or -71,067,506,484.81

        # Try to find two numbers at the end of the line
        # Match the last two comma-formatted numbers
        nums = re.findall(r'(-?[\d,]+\.\d+)', line_clean)
        if len(nums) >= 2:
            # Get the item name (everything before the first number)
            first_num_pos = line_clean.find(nums[0])
            item_name = line_clean[:first_num_pos].strip()

            # Remove trailing note numbers (Chinese number patterns like "1", "40", "56(1)")
            item_name = re.sub(r'\s+\d+(?:\(\d+\))?$', '', item_name)

            if not item_name or len(item_name) > 40:
                continue

            val1 = parse_number(nums[-2])
            val2 = parse_number(nums[-1])

            if val1 is not None and val2 is not None:
                result[item_name] = {
                    col1_year: yuan_to_millions(val1),
                    col2_year: yuan_to_millions(val2),
                }

    return result


def extract_cf_data(stmt_text, report_year):
    """Extract cash flow data from consolidated CF section."""
    cf_text = extract_between(stmt_text, "合并现金流量表",
                               ["母公司现金流量表", "合并所有者权益变动表",
                                "母公司所有者权益变动表", "补充资料",
                                "合并资产负债表", "合并利润表"])
    if not cf_text:
        return {}

    result = {}

    # Determine columns
    # First year column is the report year (current year), second is prior year
    col1_year = report_year
    col2_year = report_year - 1

    lines = cf_text.split('\n')

    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('---') or line_clean.startswith('|'):
            continue

        nums = re.findall(r'(-?[\d,]+\.\d+)', line_clean)
        if len(nums) >= 2:
            first_num_pos = line_clean.find(nums[0])
            item_name = line_clean[:first_num_pos].strip()
            item_name = re.sub(r'\s+\d+(?:\(\d+\))?$', '', item_name)

            if not item_name or len(item_name) > 40:
                continue

            val1 = parse_number(nums[-2])
            val2 = parse_number(nums[-1])

            if val1 is not None and val2 is not None:
                result[item_name] = {
                    col1_year: yuan_to_millions(val1),
                    col2_year: yuan_to_millions(val2),
                }

    return result


def extract_is_from_stmt(stmt_text, report_year):
    """Extract income statement data from consolidated IS section."""
    is_text = extract_between(stmt_text, "合并利润表",
                               ["母公司利润表", "合并资产负债表", "合并现金流量表"])
    if not is_text:
        return {}

    result = {}

    col1_year = report_year
    col2_year = report_year - 1

    lines = is_text.split('\n')

    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('---') or line_clean.startswith('|'):
            continue

        nums = re.findall(r'(-?[\d,]+\.\d+)', line_clean)
        if len(nums) >= 2:
            first_num_pos = line_clean.find(nums[0])
            item_name = line_clean[:first_num_pos].strip()
            item_name = re.sub(r'\s+\d+(?:\(\d+\))?$', '', item_name)

            if not item_name or len(item_name) > 40:
                continue

            val1 = parse_number(nums[-2])
            val2 = parse_number(nums[-1])

            if val1 is not None and val2 is not None:
                result[item_name] = {
                    col1_year: yuan_to_millions(val1),
                    col2_year: yuan_to_millions(val2),
                }

    return result


def extract_dan_data(dan_text):
    """Extract D&A data from DAN section."""
    if not dan_text:
        return {}

    result = {}

    # Look for OCF <-> net profit reconciliation (间接法)
    # Extract: 净利润, 固定资产折旧, 无形资产摊销, 长期待摊费用摊销

    patterns = [
        ("净利润", r'净利润\s+([\d,]+\.\d+)'),
        ("固定资产折旧", r'固定资产折旧[^清减]*?([\d,]+\.\d+)'),
        ("油气资产折耗", r'油气资产折耗[^清减]*?([\d,]+\.\d+)'),
        ("使用权资产折旧", r'使用权资产折旧[^清减]*?([\d,]+\.\d+)'),
        ("无形资产摊销", r'无形资产摊销[^清减]*?([\d,]+\.\d+)'),
        ("长期待摊费用摊销", r'长期待摊费用摊销[^清减]*?([\d,]+\.\d+)'),
        ("处置固定资产损失", r'处置固定资产[^益]*?(?:损失|收益)[^清减]*?(-?[\d,]+\.\d+)'),
        ("固定资产报废损失", r'固定资产报废[^益]*?(?:损失|收益)[^清减]*?(-?[\d,]+\.\d+)'),
        ("公允价值变动损失", r'公允价值变动[^益]*?(?:损失|收益)[^清减]*?(-?[\d,]+\.\d+)'),
        ("财务费用", r'(?<!资本化)财务费用[^清减]*?([\d,]+\.\d+)'),
        ("投资损失", r'投资[^益]*?(?:损失|收益)[^清减]*?(-?[\d,]+\.\d+)'),
        ("递延所得税资产减少", r'递延所得税资产[^减]*?(?:减少|增加)[^清减]*?(-?[\d,]+\.\d+)'),
        ("存货减少", r'存货[^减]*?(?:减少|增加)[^清减]*?(-?[\d,]+\.\d+)'),
        ("经营性应收减少", r'经营性应收[^减]*?(?:减少|增加)[^清减]*?(-?[\d,]+\.\d+)'),
        ("经营性应付增加", r'经营性应付[^增]*?(?:增加|减少)[^清减]*?([\d,]+\.\d+)'),
        ("经营活动CF", r'经营活动[^产]*?(?:产生)?的?现金流量净额[^清减]*?([\d,]+\.\d+)'),
    ]

    for name, pat in patterns:
        match = re.search(pat, dan_text)
        if match:
            val = parse_number(match.group(1))
            if val is not None:
                result[name] = yuan_to_millions(val)

    return result


def load_pdf_sections(year):
    """Load pdf_sections JSON for a given year."""
    path = os.path.join(BASE, f"pdf_sections_{year}.json")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_section_text(data, section):
    """Get section text, handling None."""
    text = data.get(section)
    if text is None:
        return ""
    return text


def extract_parent_bs(stmt_text, report_year):
    """Extract parent company balance sheet data."""
    parent_text = extract_between(stmt_text, "母公司资产负债表",
                                   ["合并利润表", "合并现金流量表", "母公司利润表",
                                    "合并资产负债表"])
    if not parent_text:
        return {}
    return extract_bs_lines(parent_text, report_year)


def extract_parent_cf(stmt_text, report_year):
    """Extract parent company cash flow data."""
    parent_text = extract_between(stmt_text, "母公司现金流量表",
                                   ["合并资产负债表", "合并利润表",
                                    "母公司资产负债表", "补充资料"])
    if not parent_text:
        return {}
    return extract_cf_lines(parent_text, report_year)


def extract_bs_lines(text, report_year):
    """Extract BS line items from a specific BS text block."""
    if not text:
        return {}

    # Determine years
    col1_year = report_year
    col2_year = report_year - 1

    result = {}
    lines = text.split('\n')

    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('---') or line_clean.startswith('|'):
            continue

        nums = re.findall(r'(-?[\d,]+\.\d+)', line_clean)
        if len(nums) >= 2:
            first_num_pos = line_clean.find(nums[0])
            item_name = line_clean[:first_num_pos].strip()
            item_name = re.sub(r'\s+\d+(?:\(\d+\))?$', '', item_name)

            if not item_name or len(item_name) > 40:
                continue

            val1 = parse_number(nums[-2])
            val2 = parse_number(nums[-1])

            if val1 is not None and val2 is not None:
                result[item_name] = {
                    col1_year: yuan_to_millions(val1),
                    col2_year: yuan_to_millions(val2),
                }

    return result


def extract_cf_lines(text, report_year):
    """Extract CF line items from a specific CF text block."""
    if not text:
        return {}

    col1_year = report_year
    col2_year = report_year - 1

    result = {}
    lines = text.split('\n')

    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('---') or line_clean.startswith('|'):
            continue

        nums = re.findall(r'(-?[\d,]+\.\d+)', line_clean)
        if len(nums) >= 2:
            first_num_pos = line_clean.find(nums[0])
            item_name = line_clean[:first_num_pos].strip()
            item_name = re.sub(r'\s+\d+(?:\(\d+\))?$', '', item_name)

            if not item_name or len(item_name) > 40:
                continue

            val1 = parse_number(nums[-2])
            val2 = parse_number(nums[-1])

            if val1 is not None and val2 is not None:
                result[item_name] = {
                    col1_year: yuan_to_millions(val1),
                    col2_year: yuan_to_millions(val2),
                }

    return result


def build_year_data():
    """Build a dict of all years with extracted financial data."""
    all_data = {}

    for year in YEARS:
        data = load_pdf_sections(year)
        stmt_text = get_section_text(data, "STMT")
        dan_text = get_section_text(data, "DAN")

        year_data = {
            "metadata": data["metadata"],
            "financials_pdf": data.get("financials", {}),
        }

        # Extract consolidated BS
        bs_data = extract_bs_data(stmt_text, year)
        year_data["bs_consol"] = bs_data

        # Extract parent BS
        parent_bs = extract_parent_bs(stmt_text, year)
        year_data["bs_parent"] = parent_bs

        # Extract consolidated CF
        cf_data = extract_cf_data(stmt_text, year)
        year_data["cf_consol"] = cf_data

        # Extract parent CF
        parent_cf = extract_parent_cf(stmt_text, year)
        year_data["cf_parent"] = parent_cf

        # Extract IS from STMT
        is_data = extract_is_from_stmt(stmt_text, year)
        year_data["is_consol"] = is_data

        # Extract D&A from DAN
        dan_data = extract_dan_data(dan_text)
        year_data["dan"] = dan_data

        # Get section texts for qualitative data
        for sec in ["P2", "P3", "P4", "P6", "P13", "SUB"]:
            year_data[sec] = get_section_text(data, sec)

        all_data[year] = year_data

    return all_data


def build_consolidated_bs_table(all_data):
    """Build consolidated balance sheet table across all years."""
    # Key items we want to track
    key_items = [
        "货币资金", "拆出资金", "交易性金融资产", "应收票据", "应收账款",
        "应收款项融资", "预付款项", "其他应收款", "存货", "一年内到期的非流动资产",
        "其他流动资产", "流动资产合计",
        "长期股权投资", "其他非流动金融资产", "固定资产", "在建工程",
        "使用权资产", "无形资产", "开发支出", "长期待摊费用",
        "递延所得税资产", "非流动资产合计", "资产总计",
        "短期借款", "应付票据", "应付账款", "合同负债", "应付职工薪酬",
        "应交税费", "其他应付款", "流动负债合计",
        "长期借款", "负债合计",
        "股本", "资本公积", "其他综合收益", "盈余公积", "未分配利润",
        "归母权益合计",
    ]

    # Map item names from raw text to standard names
    item_aliases = {
        "归属于母公司所有者权益合计": "归母权益合计",
        "归属于母公司股东权益合计": "归母权益合计",
        "所有者权益（或股东权益）合计": "所有者权益合计",
        "负债和所有者权益（或股东权益）总计": "负债和所有者权益总计",
    }

    # Collect all unique item names
    all_items = set()
    for year, yd in all_data.items():
        for item in yd["bs_consol"]:
            all_items.add(item)

    # Build table: for each year and item, get the value
    tables = []

    # Group items by category
    current_assets = ["货币资金", "拆出资金", "交易性金融资产", "应收票据", "应收账款",
                      "应收款项融资", "预付款项", "其他应收款", "存货",
                      "一年内到期的非流动资产", "其他流动资产"]
    non_current_assets = ["长期股权投资", "其他非流动金融资产", "固定资产", "在建工程",
                          "使用权资产", "无形资产", "开发支出", "长期待摊费用",
                          "递延所得税资产"]
    current_liab = ["短期借款", "应付票据", "应付账款", "合同负债", "应付职工薪酬",
                    "应交税费", "其他应付款"]
    non_current_liab = ["长期借款"]
    equity = ["股本", "资本公积", "其他综合收益", "盈余公积", "未分配利润", "归母权益合计"]

    # Find which item names actually exist in data
    def find_item(items, candidates):
        for item in items:
            if item in candidates:
                return item
        return None

    # Build table rows
    def get_val(item_name, year):
        yd = all_data[year]["bs_consol"]
        if item_name in yd:
            return yd[item_name].get(year)  # current year value
        # Check aliases
        for alias, std in item_aliases.items():
            if std == item_name and alias in yd:
                return yd[alias].get(year)
        return None

    # Collect all item names present
    actual_items = []
    categories = [
        ("流动资产", current_assets),
        ("非流动资产", non_current_assets),
        ("流动负债", current_liab),
        ("非流动负债", non_current_liab),
        ("所有者权益", equity),
    ]

    for cat_name, cat_items in categories:
        actual_items.append((f"【{cat_name}】", None))
        for item in cat_items:
            # Look for exact match or alias
            found = False
            for year in YEARS:
                if item in all_data[year]["bs_consol"]:
                    found = True
                    break
                for alias, std in item_aliases.items():
                    if std == item and alias in all_data[year]["bs_consol"]:
                        found = True
                        break
                if found:
                    break
            if found:
                actual_items.append((item, item))
            else:
                # Try to find close match
                for year in YEARS:
                    for k in all_data[year]["bs_consol"]:
                        if item in k or k in item:
                            actual_items.append((k, k))
                            found = True
                            break
                    if found:
                        break
                if not found:
                    pass  # Skip items not found

    # Add subtotal items
    subtotals = ["流动资产合计", "非流动资产合计", "资产总计",
                 "流动负债合计", "负债合计", "所有者权益合计",
                 "负债和所有者权益总计", "归母权益合计"]

    for st in subtotals:
        found = False
        for year in YEARS:
            if st in all_data[year]["bs_consol"]:
                found = True
                break
        if found and st not in [x[0] for x in actual_items]:
            actual_items.append((st, st))

    return actual_items


def format_value(val):
    """Format a financial value for display."""
    if val is None:
        return "—"
    if val == 0 or abs(val) < 0.01:
        return "—"
    return f"{val:,.2f}"


def create_data_pack_report(all_data):
    """Create the comprehensive data_pack_report.md."""
    lines = []
    lines.append("# 数据包报告 — 600519.SH 贵州茅台")
    lines.append("")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"*生成时间: {now}*")
    lines.append(f"*数据来源: PDF年报 (pdf_sections) + Tushare cross-ref*")
    lines.append(f"*金额单位: 百万元 (除特殊标注)*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: PDF Metadata ----
    lines.append("## 0. PDF提取元数据")
    lines.append("")
    lines.append("| 年度 | 文件名 | 总页数 | 找到章节 | 总章节 |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for year in YEARS:
        m = all_data[year]["metadata"]
        lines.append(f"| {year} | {m['pdf_file']} | {m['total_pages']} | {m['sections_found']} | {m['sections_total']} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: 合并资产负债表 (Consolidated BS) ----
    lines.append("## 1. 合并资产负债表")
    lines.append("")
    lines.append(f"*单位: 百万元 (原始数据单位: 元 ÷ 1,000,000)*")
    lines.append("")

    # Define the line items to include
    bs_items = [
        ("流动资产：", None, True),
        ("    货币资金", "货币资金", False),
        ("    拆出资金", "拆出资金", False),
        ("    交易性金融资产", "交易性金融资产", False),
        ("    应收票据", "应收票据", False),
        ("    应收账款", "应收账款", False),
        ("    应收款项融资", "应收款项融资", False),
        ("    预付款项", "预付款项", False),
        ("    其他应收款", "其他应收款", False),
        ("    存货", "存货", False),
        ("    一年内到期的非流动资产", "一年内到期的非流动资产", False),
        ("    其他流动资产", "其他流动资产", False),
        ("    流动资产合计", "流动资产合计", False),
        ("非流动资产：", None, True),
        ("    长期股权投资", "长期股权投资", False),
        ("    其他非流动金融资产", "其他非流动金融资产", False),
        ("    投资性房地产", "投资性房地产", False),
        ("    固定资产", "固定资产", False),
        ("    在建工程", "在建工程", False),
        ("    使用权资产", "使用权资产", False),
        ("    无形资产", "无形资产", False),
        ("    开发支出", "开发支出", False),
        ("    长期待摊费用", "长期待摊费用", False),
        ("    递延所得税资产", "递延所得税资产", False),
        ("    非流动资产合计", "非流动资产合计", False),
        ("资产总计", "资产总计", False),
        ("流动负债：", None, True),
        ("    短期借款", "短期借款", False),
        ("    应付票据", "应付票据", False),
        ("    应付账款", "应付账款", False),
        ("    合同负债", "合同负债", False),
        ("    应付职工薪酬", "应付职工薪酬", False),
        ("    应交税费", "应交税费", False),
        ("    其他应付款", "其他应付款", False),
        ("    流动负债合计", "流动负债合计", False),
        ("非流动负债：", None, True),
        ("    长期借款", "长期借款", False),
        ("负债合计", "负债合计", False),
        ("所有者权益：", None, True),
        ("    股本", "股本", False),
        ("    资本公积", "资本公积", False),
        ("    其他综合收益", "其他综合收益", False),
        ("    盈余公积", "盈余公积", False),
        ("    未分配利润", "未分配利润", False),
        ("    归母权益合计", "归母权益合计", False),
    ]

    # Write BS header
    header = "| 项目 | " + " | ".join([str(y) for y in YEARS]) + " |"
    sep = "| --- " + " | ---:" * len(YEARS) + " |"
    lines.append(header)
    lines.append(sep)

    for display_name, data_key, is_category in bs_items:
        if is_category:
            lines.append(f"| **{display_name}** | " + " | ".join([" " for _ in YEARS]) + " |")
        elif data_key:
            vals = []
            for year in YEARS:
                v = None
                if data_key in all_data[year]["bs_consol"]:
                    v = all_data[year]["bs_consol"][data_key].get(year)
                if v is None:
                    # Try to find in prior year column
                    for prev_year in YEARS:
                        if prev_year < year and data_key in all_data[prev_year]["bs_consol"]:
                            v = all_data[prev_year]["bs_consol"][data_key].get(prev_year)
                            if v is not None:
                                break
                vals.append(format_value(v))
            lines.append(f"| {display_name} | " + " | ".join(vals) + " |")
        else:
            lines.append(f"| {display_name} | " + " | ".join([" " for _ in YEARS]) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: 合并现金流量表 (Consolidated CF) ----
    lines.append("## 2. 合并现金流量表")
    lines.append("")
    lines.append(f"*单位: 百万元 (原始数据单位: 元 ÷ 1,000,000)*")
    lines.append("")

    cf_items = [
        "经营活动产生的现金流量净额",
        "投资活动产生的现金流量净额",
        "筹资活动产生的现金流量净额",
        "现金及现金等价物净增加额",
        "期初现金及现金等价物余额",
        "期末现金及现金等价物余额",
    ]

    header = "| 项目 | " + " | ".join([str(y) for y in YEARS]) + " |"
    sep = "| --- " + " | ---:" * len(YEARS) + " |"
    lines.append(header)
    lines.append(sep)

    for item in cf_items:
        # Find the key in data
        actual_key = None
        for year in YEARS:
            for k in all_data[year]["cf_consol"]:
                if item in k or k in item:
                    if actual_key is None:
                        actual_key = k
                    break

        if actual_key is None:
            # Try with different matching
            for year in YEARS:
                for k in all_data[year]["cf_consol"]:
                    if item[:4] in k:
                        actual_key = k
                        break

        if actual_key:
            vals = []
            for year in YEARS:
                v = None
                if actual_key in all_data[year]["cf_consol"]:
                    v = all_data[year]["cf_consol"][actual_key].get(year)
                vals.append(format_value(v))
            lines.append(f"| {item} | " + " | ".join(vals) + " |")
        else:
            lines.append(f"| {item} | " + " | ".join(["—" for _ in YEARS]) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: 折旧与摊销 (D&A from DAN) ----
    lines.append("## 3. 折旧与摊销 (DAN补充资料)")
    lines.append("")
    lines.append(f"*单位: 百万元*")
    lines.append("")

    dan_items = ["净利润", "固定资产折旧", "无形资产摊销", "长期待摊费用摊销",
                 "处置固定资产损失", "投资损失", "财务费用",
                 "递延所得税资产减少", "存货减少",
                 "经营性应收减少", "经营性应付增加",
                 "经营活动CF"]

    header = "| 项目 | " + " | ".join([str(y) for y in YEARS]) + " |"
    sep = "| --- " + " | ---:" * len(YEARS) + " |"
    lines.append(header)
    lines.append(sep)

    for item in dan_items:
        vals = []
        for year in YEARS:
            v = all_data[year]["dan"].get(item)
            if v is not None and v != 0:
                vals.append(f"{v:,.2f}")
            else:
                vals.append("—")
        lines.append(f"| {item} | " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: 母公司资产负债表 (Parent BS) ----
    lines.append("## 4. 母公司资产负债表")
    lines.append("")
    lines.append(f"*单位: 百万元*")
    lines.append("")

    parent_bs_items = ["货币资金", "应收账款", "存货", "流动资产合计",
                       "长期股权投资", "固定资产", "无形资产", "非流动资产合计", "资产总计",
                       "短期借款", "应付账款", "合同负债", "应付职工薪酬",
                       "应交税费", "流动负债合计", "负债合计",
                       "股本", "资本公积", "盈余公积", "未分配利润",
                       "归母权益合计"]

    header = "| 项目 | " + " | ".join([str(y) for y in YEARS]) + " |"
    sep = "| --- " + " | ---:" * len(YEARS) + " |"
    lines.append(header)
    lines.append(sep)

    for item in parent_bs_items:
        found_key = None
        for year in YEARS:
            for k in all_data[year]["bs_parent"]:
                if item in k or k in item:
                    found_key = k
                    break

        if found_key:
            vals = []
            for year in YEARS:
                v = None
                if found_key in all_data[year]["bs_parent"]:
                    v = all_data[year]["bs_parent"][found_key].get(year)
                vals.append(format_value(v))
            lines.append(f"| {item} | " + " | ".join(vals) + " |")
        else:
            lines.append(f"| {item} | " + " | ".join(["—" for _ in YEARS]) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: 母公司现金流量表 ----
    lines.append("## 5. 母公司现金流量表")
    lines.append("")
    lines.append(f"*单位: 百万元*")
    lines.append("")

    parent_cf_items = ["经营活动产生的现金流量净额", "投资活动产生的现金流量净额",
                       "筹资活动产生的现金流量净额"]

    header = "| 项目 | " + " | ".join([str(y) for y in YEARS]) + " |"
    sep = "| --- " + " | ---:" * len(YEARS) + " |"
    lines.append(header)
    lines.append(sep)

    for item in parent_cf_items:
        found_key = None
        for year in YEARS:
            for k in all_data[year]["cf_parent"]:
                if item in k or k in item:
                    found_key = k
                    break

        if found_key:
            vals = []
            for year in YEARS:
                v = None
                if found_key in all_data[year]["cf_parent"]:
                    v = all_data[year]["cf_parent"][found_key].get(year)
                vals.append(format_value(v))
            lines.append(f"| {item} | " + " | ".join(vals) + " |")
        else:
            lines.append(f"| {item} | " + " | ".join(["—" for _ in YEARS]) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: PDF Financials (raw extracted) vs Tushare cross-ref ----
    lines.append("## 6. PDF金融数据 vs Tushare收入表交叉验证")
    lines.append("")
    lines.append("| 项目 | 数据源 | 2021 | 2022 | 2023 | 2024 | 2025 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")

    # Compare income items
    tushare_data = {
        "营业收入": {2021: 106190.15, 2022: 124099.84, 2023: 147693.60, 2024: 170899.15, 2025: 168838.10},
        "营业成本": {2021: 8983.38, 2022: 10093.47, 2023: 11867.27, 2024: 13789.48, 2025: 14892.28},
        "归母净利润": {2021: 52460.14, 2022: 62716.44, 2023: 74734.07, 2024: 86228.15, 2025: 82320.07},
    }

    for item_name, tushare_vals in tushare_data.items():
        # PDF extracted value (from pdf financials)
        lines.append(f"| {item_name} | Tushare | " + " | ".join([f"{tushare_vals[y]:,.2f}" if tushare_vals.get(y) else "—" for y in YEARS]) + " |")

        pdf_vals = []
        for year in YEARS:
            v = all_data[year]["financials_pdf"].get(item_name)
            if v is not None:
                pdf_vals.append(v)
            else:
                pdf_vals.append(None)

        pdf_strs = []
        for v in pdf_vals:
            if v is not None:
                pdf_strs.append(f"{v:,.2f}")
            else:
                pdf_strs.append("—")
        lines.append(f"| {item_name} | PDF提取 | " + " | ".join(pdf_strs) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section: Section data summaries (P2, P3, P4, P6, P13, SUB) ----
    lines.append("## 7. P2 受限资产")
    lines.append("")
    for year in YEARS:
        p2 = all_data[year].get("P2", "")
        if p2:
            # Show first 500 chars
            lines.append(f"**{year}年**:")
            lines.append("```")
            lines.append(p2[:1000])
            lines.append("```")
            lines.append("")
        else:
            lines.append(f"**{year}年**: 未找到数据")
            lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## 8. P3 应收账款账龄")
    lines.append("")
    for year in YEARS:
        p3 = all_data[year].get("P3", "")
        if p3:
            lines.append(f"**{year}年**:")
            lines.append("```")
            lines.append(p3[:1000])
            lines.append("```")
            lines.append("")
        else:
            lines.append(f"**{year}年**: 未找到数据")
            lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## 9. P4 关联方交易")
    lines.append("")
    for year in YEARS:
        p4 = all_data[year].get("P4", "")
        if p4:
            lines.append(f"**{year}年** (显示前1500字符):")
            lines.append("```")
            lines.append(p4[:1500])
            lines.append("```")
            lines.append("")
        else:
            lines.append(f"**{year}年**: 未找到数据")
            lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## 10. P6 或有负债")
    lines.append("")
    for year in YEARS:
        p6 = all_data[year].get("P6", "")
        if p6:
            lines.append(f"**{year}年** (显示前1000字符):")
            lines.append("```")
            lines.append(p6[:1000])
            lines.append("```")
            lines.append("")
        else:
            lines.append(f"**{year}年**: 未找到数据")
            lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## 11. P13 非经常性损益")
    lines.append("")
    for year in YEARS:
        p13 = all_data[year].get("P13", "")
        if p13:
            lines.append(f"**{year}年** (显示前1500字符):")
            lines.append("```")
            lines.append(p13[:1500])
            lines.append("```")
            lines.append("")
        else:
            lines.append(f"**{year}年**: 未找到数据")
            lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## 12. SUB 主要控股参股公司")
    lines.append("")
    for year in YEARS:
        sub = all_data[year].get("SUB", "")
        if sub:
            lines.append(f"**{year}年** (显示前2000字符):")
            lines.append("```")
            lines.append(sub[:2000])
            lines.append("```")
            lines.append("")
        else:
            lines.append(f"**{year}年**: 未找到数据")
            lines.append("")

    lines.append("---")
    lines.append("")

    # ---- Section: Accuracy Checks ----
    lines.append("## 13. 数据准确性检查")
    lines.append("")
    lines.append("### 13.1 会计等式验证 (资产 = 负债 + 权益)")
    lines.append("")
    lines.append("| 年度 | 资产总计 | 负债合计 | 所有者权益 | 负债+权益 | 差额 | 误差率 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    for year in YEARS:
        bs = all_data[year]["bs_consol"]
        total_assets = None
        total_liab = None
        total_equity = None

        for k in bs:
            if "资产总计" in k or "资产合" in k:
                total_assets = bs[k].get(year)
            if "负债合" in k and "所有者" not in k and "权益" not in k:
                total_liab = bs[k].get(year)

        for k in bs:
            if "归母权益" in k or "所有者权益合" in k:
                total_equity = bs[k].get(year)
            elif "权益合计" in k and k != "负债和所有者权益合计" and k != "负债和所有者权益（或股东权益）总计":
                if total_equity is None:
                    total_equity = bs[k].get(year)

        if total_assets and total_liab and total_equity:
            diff = abs(total_assets - (total_liab + total_equity))
            error_rate = diff / total_assets * 100 if total_assets > 0 else 0
            lines.append(f"| {year} | {total_assets:,.2f} | {total_liab:,.2f} | {total_equity:,.2f} | {total_liab+total_equity:,.2f} | {diff:,.2f} | {error_rate:.4f}% |")
        else:
            lines.append(f"| {year} | - | - | - | - | - | - |")

    lines.append("")
    lines.append("### 13.2 现金等价物勾稽验证")
    lines.append("")
    lines.append("| 年度 | 期初现金 | 经营活动CF | 投资活动CF | 筹资活动CF | 净增加额(计算) | 净增加额(报表) | 差额 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for year in YEARS:
        cf = all_data[year]["cf_consol"]
        ocf = None
        icf = None
        fcf = None
        net_inc = None
        period_start = None
        period_end = None

        for k in cf:
            if "经营活动" in k:
                ocf = cf[k].get(year)
            if "投资活动" in k:
                icf = cf[k].get(year)
            if "筹资活动" in k:
                fcf = cf[k].get(year)
            if "净增加额" in k:
                net_inc = cf[k].get(year)
            if "期初" in k:
                period_start = cf[k].get(year)
            if "期末" in k:
                period_end = cf[k].get(year)

        if ocf is not None and icf is not None and fcf is not None:
            calc_net = ocf + icf + fcf
            if net_inc is not None:
                diff = abs(calc_net - net_inc)
                lines.append(f"| {year} | {period_start or 0:,.2f} | {ocf:,.2f} | {icf:,.2f} | {fcf:,.2f} | {calc_net:,.2f} | {net_inc:,.2f} | {diff:,.2f} |")
            else:
                lines.append(f"| {year} | {period_start or 0:,.2f} | {ocf:,.2f} | {icf:,.2f} | {fcf:,.2f} | {calc_net:,.2f} | — | — |")
        else:
            lines.append(f"| {year} | - | - | - | - | - | - | - |")

    lines.append("")
    lines.append("### 13.3 PDF提取vs Tushare数据一致性")
    lines.append("")
    lines.append("| 项目 | 2021(Tushare) | 2021(PDF) | 偏差% | 2024(Tushare) | 2024(PDF) | 偏差% |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    check_items = ["营业收入", "营业成本", "归母净利润"]
    for item in check_items:
        for year in [2021, 2024]:
            t_val = tushare_data.get(item, {}).get(year)
            p_val = all_data[year]["financials_pdf"].get(item)

            # Actually from IS extract
            is_val = None
            for k, v in all_data[year]["is_consol"].items():
                if item in k:
                    is_val = v.get(year)
                    break

        t_2021 = tushare_data.get(item, {}).get(2021, 0)
        p_2021 = all_data[2021]["financials_pdf"].get(item, 0)
        t_2024 = tushare_data.get(item, {}).get(2024, 0)
        p_2024 = all_data[2024]["financials_pdf"].get(item, 0)

        dev_2021 = f"{abs(p_2021 - t_2021)/t_2021*100:.1f}%" if t_2021 and p_2021 else "N/A"
        dev_2024 = f"{abs(p_2024 - t_2024)/t_2024*100:.1f}%" if t_2024 and p_2024 else "N/A"

        lines.append(f"| {item} | {t_2021:,.2f} | {p_2021:,.2f} | {dev_2021} | {t_2024:,.2f} | {p_2024:,.2f} | {dev_2024} |")

    lines.append("")
    lines.append("### 13.4 PDF金融提取字段完整清单")
    lines.append("")
    lines.append("| 年度 | 字段数 | 字段列表 |")
    lines.append("| --- | ---: | --- |")
    for year in YEARS:
        fin = all_data[year]["financials_pdf"]
        fields = sorted(fin.keys())
        lines.append(f"| {year} | {len(fields)} | {', '.join(fields)} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Key Findings Summary ----
    lines.append("## 14. 已知问题与警告")
    lines.append("")
    lines.append("### 14.1 PDF提取的收入数据单位错误")
    lines.append("")
    lines.append("pdf_sections中提取的收入数据(营业收入、营业成本等)与正确值偏差很大，")
    lines.append('原因是regex在PDF文本中匹配到了错误的数字（例如仅匹配到"17.09"而非"170,899,152,276.34/1,000,000=170,899.15"）')
    lines.append("需要人工修正或用STMT文本重新提取。")
    lines.append("")
    lines.append("| 项目 | 2021 (STMT正确值) | 2021 (PDF提取错误值) | 2024 (STMT正确值) | 2024 (PDF提取错误值) |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")

    for item in ["营业收入", "营业成本", "归母净利润"]:
        # STMT correct values
        is_2021 = None
        is_2024 = None
        for k, v in all_data[2021]["is_consol"].items():
            if item in k:
                is_2021 = v.get(2021)
                break
        for k, v in all_data[2024]["is_consol"].items():
            if item in k:
                is_2024 = v.get(2024)
                break

        pdf_2021 = all_data[2021]["financials_pdf"].get(item)
        pdf_2024 = all_data[2024]["financials_pdf"].get(item)

        lines.append(f"| {item} | {format_value(is_2021)} | {format_value(pdf_2021)} | {format_value(is_2024)} | {format_value(pdf_2024)} |")

    lines.append("")
    lines.append("### 14.2 缺失数据")
    lines.append("")
    lines.append("- 2023年合并现金流量表在STMT中未捕获到（该年财报格式可能有差异，需要从PDF DAN/MDA区域额外提取）")
    lines.append("- Tushare原始数据中合并资产负债表和现金流量表缺失（已在data_pack_market.md中标注）")
    lines.append("")
    lines.append("### 14.3 审计师变更")
    lines.append("")
    lines.append("- 2023年及之前: 天职国际会计师事务所")
    lines.append("- 2024年及之后: 天健会计师事务所")
    lines.append("")

    # Done
    return "\n".join(lines)


def main():
    print("Building year data from pdf_sections...")
    all_data = build_year_data()

    # Print summary for verification
    for year in YEARS:
        yd = all_data[year]
        bs_count = len(yd["bs_consol"])
        cf_count = len(yd["cf_consol"])
        dan_count = len(yd["dan"])
        print(f"{year}: BS={bs_count} items, CF={cf_count} items, DAN={dan_count} items")

        # Check key figures
        for k, v in sorted(yd["bs_consol"].items()):
            if "资产总计" in k and v.get(year):
                print(f"  Total Assets ({year}): {v[year]:,.2f}")
            if "负债合" in k and "所有者" not in k and v.get(year):
                print(f"  Total Liab ({year}): {v[year]:,.2f}")
            if ("归母权益" in k or "所有者权益合" in k) and v.get(year):
                print(f"  Total Equity ({year}): {v[year]:,.2f}")

    print("\nGenerating data_pack_report.md...")
    report = create_data_pack_report(all_data)

    output_path = os.path.join(BASE, "data_pack_report.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written to {output_path}")
    print(f"File size: {len(report)} bytes")

    # Also dump a JSON summary
    summary = {}
    for year in YEARS:
        yd = all_data[year]
        summary[year] = {
            "bs_consol": {k: v for k, v in sorted(yd["bs_consol"].items())},
            "cf_consol": {k: v for k, v in sorted(yd["cf_consol"].items())},
            "dan": yd["dan"],
        }

    json_path = os.path.join(BASE, "extracted_financials.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"JSON summary written to {json_path}")


if __name__ == "__main__":
    main()
