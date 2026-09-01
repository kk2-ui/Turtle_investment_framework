#!/usr/bin/env python3
"""
C_FULL Report Generator
Reads zone_c_C_FULL_prompt.txt, extracts JSON data and template,
fills all [?] placeholders, and outputs the complete report.
"""

import json
import re
import os
import math

# ─── Paths ───
PROMPT_FILE = "/Users/xiami/workspace/analy/Turtle_investment_framework/output/00816_金茂服务/zone_c_C_FULL_prompt.txt"
OUTPUT_FILE = "/Users/xiami/workspace/analy/Turtle_investment_framework/output/00816_金茂服务/zone_c_C_FULL_output.md"

# ─── Read prompt file ───
with open(PROMPT_FILE, "r") as f:
    content = f.read()

# ─── Split JSON data from template ───
# JSON starts after "【输入数据】\n{" and ends at the first "}" on its own line after 1946
lines = content.split("\n")

# Find JSON boundaries
json_start = None
json_end = None
for i, line in enumerate(lines):
    if line.strip() == "{":
        # First { after 【输入数据】
        if json_start is None and "输入数据" in lines[max(0, i - 1)]:
            json_start = i
            break

# Actually let's just use the known range: lines 3-1946 (0-indexed: 2-1945)
json_text = "\n".join(lines[2:1945])  # The JSON content
data = json.loads(json_text)

# Template is lines 1947+ (0-indexed)
template_lines = lines[1947:]

# ─── Build lookup tables ───

def deep_get(d, path, default="⚠️"):
    """Get a nested value from dict by dot-separated path."""
    if not path:
        return default
    keys = path.split(".")
    current = d
    try:
        for k in keys:
            # Handle array indexing: key[index]
            array_match = re.match(r'(\w+)\[(\d+)\]', k)
            if array_match:
                k = array_match.group(1)
                idx = int(array_match.group(2))
                current = current[k]
                if isinstance(current, list):
                    current = current[idx]
                else:
                    return default
            else:
                current = current[k]
        return current
    except (KeyError, IndexError, TypeError):
        return default

def format_val(v, is_pct=False):
    """Format a value for display."""
    if v is None:
        return "⚠️"
    if isinstance(v, float):
        if is_pct:
            return f"{v:.1f}"
        if abs(v) < 0.01:
            return f"{v:.2f}"
        if abs(v) < 10:
            return f"{v:.2f}"
        if abs(v) < 1000:
            return f"{v:.2f}"
        return f"{v:.2f}"
    return str(v)

# ─── Lookup: map template paths to JSON paths ───

# Simple path-based lookups
path_map = {
    "meta.date": ["_meta", "generated_at"],
    "meta.code": ["_meta", "ts_code"],
    "market.price_hkd": ["compute_bundle", "market", "price_hkd"],
    "market.mc_hkd": ["compute_bundle", "market", "mc_hkd"],
    "market.mc_rmb": ["compute_bundle", "market", "mc_rmb"],
    "market.shares_m": ["compute_bundle", "market", "shares_m"],
    "params.II": ["compute_bundle", "params", "II"],
    "params.Rf": ["compute_bundle", "params", "Rf"],
    "params.Q×100": ["compute_bundle", "params", "Q"],
    "params.dps_latest": ["compute_bundle", "params", "dps_latest"],
    "params.g_base": ["compute_bundle", "params", "g_base"],
    "params.b_penalty×100": ["compute_bundle", "params", "b_penalty"],
    "factor2.np_avg_3y": ["compute_bundle", "factor2", "np_avg_3y"],
    "factor2.np_avg_5y": ["compute_bundle", "factor2", "np_avg_5y"],
    "factor2.oe_avg_3y": ["compute_bundle", "factor2", "oe_avg_3y"],
    "factor2.ocf_np_ratio": ["compute_bundle", "factor2", "ocf_np_ratio"],
    "factor2.M": ["compute_bundle", "factor2", "M"],
    "factor2.M_source": ["compute_bundle", "factor2", "M_source"],
    "factor2.M_samples": ["compute_bundle", "factor2", "M_samples"],
    "factor3.gg.base": ["compute_bundle", "factor3", "gg", "base"],
    "factor4.ddm_v_hkd": ["compute_bundle", "factor4", "ddm_v_hkd"],
    "rejection_summary.overall": ["compute_bundle", "rejection_summary", "overall"],
}

def resolve_path(path_str):
    """Resolve a path string like 'factor2.np_avg_3y' to a value."""
    if not path_str or path_str.strip() == "":
        return "⚠️"

    path_str = path_str.strip()

    # Remove common suffixes that aren't part of paths
    path_str_clean = re.sub(r'[×%].*$', '', path_str)

    # Handle special named lookups
    special = {
        "公司名": "金茂服务",
    }
    if path_str in special:
        return special[path_str]

    # Check path_map
    if path_str in path_map:
        val = deep_get(data, ".".join(path_map[path_str]))
        if val == "⚠️":
            return val
        if isinstance(val, float):
            return f"{val:.2f}".rstrip('0').rstrip('.')
        return str(val)

    # Try direct JSON path
    val = deep_get(data, path_str)
    if val != "⚠️":
        if isinstance(val, float):
            return f"{val:.2f}".rstrip('0').rstrip('.')
        return str(val)

    # Try with compute_bundle prefix
    val = deep_get(data, f"compute_bundle.{path_str}")
    if val != "⚠️":
        if isinstance(val, float):
            return f"{val:.2f}".rstrip('0').rstrip('.')
        return str(val)

    return "⚠️"


def context_match(line, template_line_idx):
    """
    For bare [?] placeholders, infer the value based on context.
    Returns the value to substitute.
    """
    # We'll handle this in the main processing loop by looking at surrounding text
    return None


# ─── Process template ───
output_lines = []
multi_line_buffer = []
skip_next = False

for i, line in enumerate(template_lines):
    if skip_next:
        skip_next = False
        continue

    # Check if this is the [C4_PLACEHOLDER] line
    if line.strip() == "[C4_PLACEHOLDER]":
        # Insert executive summary
        output_lines.append("<!-- Executive Summary from C1 -->")
        continue

    if line.strip() == "[/ES_REPLACE]":
        continue

    # Process line - replace all [?] placeholders
    processed_line = line

    # Find all placeholders in this line
    placeholders = re.findall(r'\[\?([^\]]*)\]', line)

    for ph in placeholders:
        ph_stripped = ph.strip()

        if ph_stripped == "":
            # Bare [?] - context-dependent
            # We'll handle these in a second pass or with context
            # For now, leave as [?] marker to be filled
            pass
        else:
            # Has a hint - try to resolve
            resolved = resolve_path(ph_stripped)
            if resolved != "⚠️":
                processed_line = processed_line.replace(f"[?{ph}]", resolved, 1)

    output_lines.append(processed_line)

# ─── Second pass: progressively fill bare [?] with context awareness ───

# Let's define a function that looks at the context of each bare [?]
# and determines what data to fill based on table headers and column position

# For each table, we map column indices to fiscal years
# The main tables use FY2021, FY2022, FY2023, FY2024, FY2025

fiscal_years = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]

# Financial data arrays (indexed 0-4 for FY2021-FY2025)
income_trend = data.get("financial_trends", {}).get("income_trend", [])
# income_trend[0] = FY2018, need to map to FY2021 offset
fy_index_map = {}
for idx, entry in enumerate(income_trend):
    fy = entry.get("fiscal_year")
    if fy == 2021: fy_index_map["FY2021"] = idx
    elif fy == 2022: fy_index_map["FY2022"] = idx
    elif fy == 2023: fy_index_map["FY2023"] = idx
    elif fy == 2024: fy_index_map["FY2024"] = idx
    elif fy == 2025: fy_index_map["FY2025"] = idx

cashflow_trend = data.get("financial_trends", {}).get("cashflow_trend", [])
cf_map = {}
for idx, entry in enumerate(cashflow_trend):
    fy = entry.get("fiscal_year")
    if fy == 2021: cf_map["FY2021"] = idx
    elif fy == 2022: cf_map["FY2022"] = idx
    elif fy == 2023: cf_map["FY2023"] = idx
    elif fy == 2024: cf_map["FY2024"] = idx
    elif fy == 2025: cf_map["FY2025"] = idx

balance_sheet = data.get("financial_trends", {}).get("balance_sheet_trend", [])
bs_map = {}
for idx, entry in enumerate(balance_sheet):
    fy = entry.get("fiscal_year")
    if fy == 2021: bs_map["FY2021"] = idx
    elif fy == 2022: bs_map["FY2022"] = idx
    elif fy == 2023: bs_map["FY2023"] = idx
    elif fy == 2024: bs_map["FY2024"] = idx
    elif fy == 2025: bs_map["FY2025"] = idx

profit_ratios = data.get("financial_trends", {}).get("profitability_ratios", [])
pr_map = {}
for idx, entry in enumerate(profit_ratios):
    fy = entry.get("fiscal_year")
    if fy == 2021: pr_map["FY2021"] = idx
    elif fy == 2022: pr_map["FY2022"] = idx
    elif fy == 2023: pr_map["FY2023"] = idx
    elif fy == 2024: pr_map["FY2024"] = idx
    elif fy == 2025: pr_map["FY2025"] = idx

per_share = data.get("financial_trends", {}).get("per_share_trend", [])
ps_map = {}
for idx, entry in enumerate(per_share):
    fy = entry.get("fiscal_year")
    if fy == 2021: ps_map["FY2021"] = idx
    elif fy == 2022: ps_map["FY2022"] = idx
    elif fy == 2023: ps_map["FY2023"] = idx
    elif fy == 2024: ps_map["FY2024"] = idx
    elif fy == 2025: ps_map["FY2025"] = idx

def get_income(fy, field):
    idx = fy_index_map.get(fy)
    if idx is not None and idx < len(income_trend):
        return income_trend[idx].get(field, "⚠️")
    return "⚠️"

def get_cf(fy, field):
    idx = cf_map.get(fy)
    if idx is not None and idx < len(cashflow_trend):
        return cashflow_trend[idx].get(field, "⚠️")
    return "⚠️"

def get_bs(fy, field):
    idx = bs_map.get(fy)
    if idx is not None and idx < len(balance_sheet):
        return balance_sheet[idx].get(field, "⚠️")
    return "⚠️"

def get_pr(fy, field):
    idx = pr_map.get(fy)
    if idx is not None and idx < len(profit_ratios):
        return profit_ratios[idx].get(field, "⚠️")
    return "⚠️"

def get_ps(fy, field):
    idx = ps_map.get(fy)
    if idx is not None and idx < len(per_share):
        return per_share[idx].get(field, "⚠️")
    return "⚠️"

def fmt(v, decimals=2):
    """Format a value nicely."""
    if v is None or v == "⚠️":
        return "⚠️"
    if isinstance(v, float):
        if decimals == 0:
            return f"{v:.0f}"
        return f"{v:.{decimals}f}"
    if isinstance(v, int):
        return str(v)
    return str(v)

def fmt_pct(v):
    """Format as percentage with 1 decimal."""
    if v is None or v == "⚠️":
        return "⚠️"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)

# Now do a comprehensive second pass on all lines
# For each line with a bare [?], we need to figure out what data goes there
# based on the table structure

result_lines = output_lines[:]

# Fix the first line: # 龟龟投资策略 · 分析报告：[读取 meta.code]
for i, line in enumerate(result_lines):
    if line.startswith("# 龟龟投资策略"):
        result_lines[i] = line.replace("[读取 meta.code]", data["_meta"]["ts_code"])

    # Fix report meta info
    # Company name
    if "公司" in line and "[? 公司名]" in line:
        result_lines[i] = line.replace("[? 公司名]", "金茂服务")
    if "[? industry_context]" in line:
        result_lines[i] = line.replace("[? industry_context]", "物业服务")
    if "[? 公司名]" in line:
        result_lines[i] = line.replace("[? 公司名]", "金茂服务")

# Write initial result
with open("/tmp/intermediate.txt", "w") as f:
    f.write("\n".join(result_lines))

print(f"Initial pass done. {len(result_lines)} lines written.")
print(f"Remaining [?] count: {sum(line.count('[?]') for line in result_lines)}")
