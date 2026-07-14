#!/usr/bin/env python3
"""build_full_text.py — Smart qualitative-focused PDF text assembler for Zone C.

Extracts VALUABLE qualitative content from annual reports across 5 years:
- Skips pure numeric tables (already in DB/JSON)
- Strips boilerplate headers and repetitive note prefixes
- Scores paragraphs by information density — keeps analysis, filters boilerplate
- For cyclical stocks, marks peak/trough years

Usage:
    python3 scripts/build_full_text.py --code 02669.HK
    python3 scripts/build_full_text.py --code 02669.HK --years 5 --max-chars 80000
"""

import argparse, json, os, re, sys
from datetime import datetime
from statistics import mean, stdev

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

SECTION_LABELS = {
    "MDA": "管理层讨论与分析", "SEG": "分部报告",
    "P3": "应收账款与减值", "P4": "关联方交易",
    "P6": "或有事项与流动性", "P13": "非经常性损益",
    "DAN": "折旧摊销与现金流补充", "SUB": "主要子公司",
    "STMT": "财务报表与附注",
}

# Keywords indicating valuable qualitative analysis (keep these paragraphs)
ANALYSIS_KEYWORDS = [
    "因为", "由于", "导致", "原因", "主要", "增长", "下降", "减少", "增加",
    "策略", "战略", "展望", "计划", "目标", "预期", "预计", "估计",
    "风险", "不确定", "挑战", "压力", "竞争", "市场份额",
    "管理层", "董事会", "我们认为", "公司认为",
    "调整", "变化", "变动", "重大", "显著", "重要",
    "due to", "because", "as a result", "driven by", "attributable",
    "strategy", "outlook", "expect", "anticipate", "estimate",
    "risk", "uncertainty", "challenge", "competition", "market share",
    "management", "the Group", "the Company",
]

# Boilerplate patterns to strip (repeated on every page, no analytical value)
BOILERPLATE_PATTERNS = [
    r'(?:NOTES\s+TO\s+THE\s+(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS\s*(?:\(Continued\))?\s*\n?)',
    r'(?:綜合財務報表附註\s*(?:（續）)?\s*\n?)',
    r'(?:财务报表附注\s*(?:（续）)?\s*\n?)',
    r'China Overseas Property Holdings Limited\s*[–-]\s*Annual Report \d{4}\s*\n?',
    r'CORPORATE OVERVIEW\s*\|\s*GOVERNANCE\s*\|\s*FINANCIAL INFORMATION\s*\n?',
    r'\d{3}\s*\n\s*(?:China|CORPORATE).*?\n',
    r'For the year ended 31 December \d{4}\s*\n',
    r'截至\d{4}年12月31日止年度\s*\n',
]

# Pure numeric table indicators (skip lines matching these)
NUMERIC_TABLE_PATTERNS = [
    r'^\s*[\d,\s\.\(\)\-]+%\s*$',          # line of just numbers and %
    r'^\s*(?:RMB|HK)\$?[\'」]?\d{3}',        # currency amounts
    r'^\s*\d{1,3}(?:,\d{3})*\s+\d',          # line starting with a number followed by more numbers
    r'\[TABLE\]',                              # markdown table markers
    r'^\s*---\s*$',                           # markdown table separators
]


def strip_boilerplate(text: str) -> str:
    """Remove boilerplate headers and page markers."""
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)
    # Collapse multiple blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


def is_numeric_table_line(line: str) -> bool:
    """Check if a line is primarily numeric (table data, not analysis)."""
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return False
    for pattern in NUMERIC_TABLE_PATTERNS:
        if re.match(pattern, stripped):
            return True
    # Heuristic: if >60% of characters are digits/commas/dots/parens/percent/spaces
    alpha_chars = sum(1 for c in stripped if c.isalpha())
    if len(stripped) > 20 and alpha_chars < len(stripped) * 0.15:
        return True
    return False


def score_paragraph(para: str) -> float:
    """Score a paragraph by qualitative information density (0-10). Higher = keep."""
    if len(para.strip()) < 30:
        return 0.0

    lines = para.split('\n')
    # Penalize if mostly numeric table lines
    numeric_lines = sum(1 for l in lines if is_numeric_table_line(l))
    if numeric_lines > len(lines) * 0.5:
        return 0.0

    # Reward for analysis keywords
    keyword_hits = sum(1 for kw in ANALYSIS_KEYWORDS if kw.lower() in para.lower())
    keyword_score = min(keyword_hits * 1.5, 6.0)

    # Reward for length (longer paragraphs tend to have more substance)
    length_score = min(len(para) / 200, 3.0)

    # Penalize for being too repetitive (same line repeated)
    unique_lines = len(set(l.strip() for l in lines if l.strip()))
    variety_score = min(unique_lines / max(len(lines), 1) * 2, 2.0)

    return keyword_score + length_score + variety_score


def smart_extract(text: str, max_chars: int = 12000) -> str:
    """Extract valuable qualitative content, filtering numeric boilerplate.

    Strategy:
    1. Split into paragraphs
    2. Score each paragraph by information density
    3. Keep top-scoring paragraphs up to max_chars
    4. Strip boilerplate headers
    """
    text = strip_boilerplate(text)

    # Split into paragraphs (separated by 2+ newlines or explicit page breaks)
    paragraphs = re.split(r'\n\s*\n|--- p\.\d+ ---', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return ""

    # Score and sort
    scored = [(score_paragraph(p), p) for p in paragraphs]
    # Keep paragraphs with score >= 1.5 (at least some qualitative value)
    valuable = [(s, p) for s, p in scored if s >= 1.5]
    # Sort by score descending
    valuable.sort(key=lambda x: -x[0])

    # Build output up to max_chars
    result_parts = []
    total = 0
    kept_original_order = [(i, s, p) for i, (s, p) in enumerate(scored) if s >= 1.5]
    kept_original_order.sort(key=lambda x: x[0])  # sort by original position

    for _, score, para in kept_original_order:
        if total + len(para) > max_chars:
            break
        result_parts.append(para)
        total += len(para) + 2

    return "\n\n".join(result_parts)


def detect_cyclicality(stock_dir: str, ts_code: str) -> dict:
    """Detect if a stock is cyclical from revenue volatility and industry signals."""
    result = {"is_cyclical": False, "peak_year": None, "trough_year": None, "revenue_volatility": None}

    # Try reading financial_trends.json for revenue volatility
    trends_path = os.path.join(stock_dir, "financial_trends.json")
    if not os.path.exists(trends_path):
        return result

    try:
        with open(trends_path) as f:
            trends = json.load(f)
    except Exception:
        return result

    income = trends.get("income_trend", [])
    if len(income) < 5:
        return result

    # Get revenue for last 5 years
    recent = [(r["fiscal_year"], r.get("revenue")) for r in income[-5:]
              if r.get("revenue") and r["revenue"] > 0]
    if len(recent) < 5:
        return result

    revenues = [r[1] for r in recent]
    try:
        cv = stdev(revenues) / mean(revenues)  # coefficient of variation
    except Exception:
        return result

    result["revenue_volatility"] = round(cv, 3)

    # Cyclical if revenue CV > 0.15 (15% variation)
    if cv > 0.15:
        result["is_cyclical"] = True
        peak_year = max(recent, key=lambda x: x[1])[0]
        trough_year = min(recent, key=lambda x: x[1])[0]
        result["peak_year"] = peak_year
        result["trough_year"] = trough_year

    # Also check industry_context signals
    ctx_path = os.path.join(stock_dir, "industry_context.json")
    if os.path.exists(ctx_path):
        try:
            with open(ctx_path) as f:
                ctx = json.load(f)
            signals = ctx.get("signals", [])
            for s in signals:
                if "cyclical" in str(s).lower() or "周期" in str(s):
                    result["is_cyclical"] = True
        except Exception:
            pass

    return result


def build_full_text(stock_dir: str, ts_code: str,
                    num_years: int = 5, max_chars_per_section: int = 12000) -> dict:
    """Assemble multi-year pdf_sections with qualitative-focused extraction."""

    section_files = sorted([f for f in os.listdir(stock_dir)
                            if f.startswith("pdf_sections_") and f.endswith(".json")
                            and not f.startswith("pdf_sections_interim_")])
    if not section_files:
        return {"error": "no_pdf_sections"}

    section_files = section_files[-num_years:]
    cyclical_info = detect_cyclicality(stock_dir, ts_code)

    years_data = {}
    total_chars = 0

    for fname in section_files:
        ym = re.search(r'pdf_sections_(\d{4})', fname)
        year = ym.group(1) if ym else "unknown"

        filepath = os.path.join(stock_dir, fname)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        year_sections = {}
        year_chars = 0
        # Add one-line financial snapshot for context
        fin = data.get("financials", {})
        fin_header = ""
        rev = fin.get("营业收入")
        np_val = fin.get("归母净利润")
        if rev or np_val:
            fin_header = f"[FY{year}: 营收={rev or '?'}M, 净利={np_val or '?'}M] "

        for key, label in SECTION_LABELS.items():
            content = data.get(key, "")
            if not content or not isinstance(content, str) or len(content.strip()) < 100:
                continue

            extracted = smart_extract(content, max_chars=max_chars_per_section)
            char_count = len(extracted)

            section_label = label
            if cyclical_info["is_cyclical"]:
                if int(year) == cyclical_info["peak_year"]:
                    section_label = f"🔺{label} [高峰]"
                elif int(year) == cyclical_info["trough_year"]:
                    section_label = f"🔻{label} [低谷]"

            year_sections[key] = {
                "label": section_label,
                "char_count": char_count,
                "text": fin_header + extracted,
            }
            year_chars += char_count

        if year_sections:
            years_data[year] = {"sections": year_sections, "total_chars": year_chars}
            total_chars += year_chars

    return {
        "_provenance": {
            "generated_at": datetime.now().isoformat(),
            "script": "build_full_text.py", "ts_code": ts_code,
            "years_covered": sorted(years_data.keys()),
            "total_chars": total_chars,
            "extraction_method": "scored_qualitative_filtering",
        },
        "cyclical_info": cyclical_info,
        "years": years_data,
    }


def main():
    p = argparse.ArgumentParser(description="build_full_text.py — Smart multi-year PDF text assembler")
    p.add_argument("--code", type=str, required=True, help="Stock code (e.g. 02669.HK)")
    p.add_argument("--output", type=str, help="Output directory (auto-detected if omitted)")
    p.add_argument("--years", type=int, default=5, help="Number of years (default 5)")
    p.add_argument("--max-chars", type=int, default=12000, help="Max chars per section (default 12000)")
    args = p.parse_args()

    ts_code = args.code
    if args.output:
        stock_dir = args.output
    else:
        code_prefix = ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        candidates = sorted([d for d in os.listdir(OUTPUT_BASE) if d.startswith(code_prefix)],
                           key=lambda x: ("_HK_" in x, x))
        if candidates:
            stock_dir = os.path.join(OUTPUT_BASE, candidates[0])
        else:
            print(f"ERROR: No output directory found for {ts_code}", file=sys.stderr)
            return 1

    result = build_full_text(stock_dir, ts_code, args.years, args.max_chars)
    out_path = os.path.join(stock_dir, "pdf_full_text.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    cyc = result.get("cyclical_info", {})
    print(f"✅ pdf_full_text.json → {out_path}")
    print(f"   Years: {result['_provenance']['years_covered']}")
    print(f"   Sections/year: ~{len(SECTION_LABELS)}")
    print(f"   Total chars: {result['_provenance']['total_chars']:,}")
    if cyc.get("is_cyclical"):
        print(f"   🔄 周期性股票: peak={cyc['peak_year']}, trough={cyc['trough_year']} (CV={cyc['revenue_volatility']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
