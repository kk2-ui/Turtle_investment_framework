Run a standalone Business Model & Moat Qualitative Analysis (商业模式与护城河定性分析) on stock: $ARGUMENTS

## Input Validation
- Stock code must be a valid A-share (e.g., 600887, 000858.SZ), HK stock (00700.HK), or US stock (AAPL)
- If $ARGUMENTS is empty or invalid, ask the user for a valid stock code before proceeding
- If only digits are given, the code will be normalized by scripts/config.py

## Execution Instructions

Read shared/qualitative/coordinator_v2.md for the full pipeline specification, then execute each step:

### Step 1: Data Collection (parallel)

**1A: Tushare structured data**
```bash
mkdir -p output/{code}_{company}
python3 scripts/tushare_collector.py --code $ARGUMENTS --output output/{code}_{company}/data_pack_market.md
```

**1B: PDF acquisition and loading**
- Determine the latest fiscal year: `latest_fiscal_year` = current calendar year − 1 (e.g., in 2026 → FY2025)
- Default annual-report target: latest 5 complete fiscal years (`latest_fiscal_year-4` through `latest_fiscal_year`).
- Minimum annual-report coverage: 3 complete annual reports. If fewer than 3 are available after download attempts, continue only in degraded mode and explicitly mark DPS CAGR, Capex/D&A, cash audit, governance trajectory, and management-history conclusions as sample-limited.
- For each target fiscal year, check if a PDF already exists in output/{code}_{company}/ using these globs in order:
  1. `*{year}*年报*.pdf` or `*{year}*年度报告*.pdf` or `*{year}*annual*.pdf`
  2. `*{year}*.pdf` (any PDF containing the fiscal year, e.g. `02669_2025_中海物业.pdf`)
  3. If only one `.pdf` exists for that year → use it regardless of filename
  - If found by any rule → use the existing PDF, skip download for that year
  - If multiple PDFs exist and none match rules 1-2 → ask user which to use
  - If a target year is missing → proceed to download that year's annual report
- If user provided a PDF path or URL → use it directly for the matching year, but still check the remaining target years.
- If a target-year PDF is missing and no PDF URL was provided → use `/download-annual-report {stock_code} {year} 年报` to search and download that annual report.
  - Download target: output/{code}_{company}/
  - If download fails after retries → record the missing year; if total annual reports < 3, fallback to WebSearch (Step 1C) and mark degraded mode
- Interim-report download is mandatory when `data_pack_market.md` contains a `YYYYH1` column:
  - Target interim year = the latest `YYYY` from `YYYYH1`
  - First check local files for `*{year}*中报*.pdf`, `*{year}*半年*.pdf`, `*{year}*interim*.pdf`, or `*{year}*H1*.pdf`
  - If missing → use `/download-annual-report {stock_code} {year} 中报` to search and download that interim report
  - Deterministic wrapper supports direct staging via `--interim-pdf` or direct download via `--interim-pdf-url`
  - If still missing, continue but mark latest operations, receivables, cash, dividends, and MD&A as timeliness-degraded
- Read PDF using Read tool: first read table of contents (pages 1-5), then read key sections by priority:
  - P0: Letter to shareholders (pp 5-8), MD&A (pp 16-60), Corporate governance (pp 61-85)
  - P1: Company overview & key financials (pp 10-15), Shareholder info (pp 101-108)
  - P2: Financial statement notes (pp 115+)
- Each Read call: max 20 pages, read by priority order

**1C: WebSearch fallback (only if PDF download failed)**
- Use WebSearch (via Agent) to supplement §7 (management/governance), §8 (industry/competition), §10 (MD&A)
- Read shared/qualitative/data_collection.md for WebSearch instructions
- Search queries must include "年报" or "全年" to prioritize full-year data over interim (H1/Q3) data
- Append results to data_pack_market.md
- Mark data source as WebSearch in report (lower confidence)

**1D: PDF Footnote + Financial Statement Extraction**
- Read strategies/turtle/phase2_PDF解析.md for extraction format spec
- For plain-text PDFs: Read footnote sections directly from PDF by page range (from TOC)
- For scanned PDFs: fallback to `python3 scripts/pdf_preprocessor.py` → pdf_sections.json → Agent extraction
- Extract: P2 (restricted cash), P3 (A/R aging), P4 (related party transactions),
  P6 (contingent liabilities), P13 (non-recurring items), SUB (subsidiaries, conditional)
- Output: output/{code}_{company}/data_pack_report.md (footnotes from latest PDF)
- This step can run in parallel with Step 2 — it serves downstream strategies (Turtle, etc.)
- If no PDF available: skip (downstream strategies use degraded mode)

**1D-HK: Multi-year Financial Statement Extraction (HK stocks only)**
- Trigger condition: stock is HK (.HK). Use every available target-year annual report from the latest 5-year window; require at least 3 for non-degraded trend conclusions.
- Collect target-year PDFs, parse fiscal year from each filename (pattern: `*{YYYY}*.pdf`)
- For each PDF (sorted by year ascending):
  ```bash
  python3 scripts/pdf_preprocessor.py --pdf output/{code}_{company}/{pdf_file} \
    --output output/{code}_{company}/pdf_sections_{year}.json
  ```
- For each resulting `pdf_sections_{year}.json`, read the STMT section and extract three statements
  per the STMT spec in strategies/turtle/phase2_PDF解析.md
- Merge extracted data into data_pack_market.md §3/§4/§5:
  - Add each year as a new column in the existing tables
  - Mark source as `[PDF]` to distinguish from Tushare data
  - Overwrite any `⚠️` placeholder values that are now filled
- If a PDF's STMT section is null (financial statement pages not found):
  - Fall back to reading PDF directly: use Read tool on the pages around the auditor's report
    (typically pages where "综合损益表" / "Consolidated Statement of Profit or Loss" appears)
  - If still not found: mark that year's data as `⚠️ STMT未提取` in §3/§4/§5

### Step 2: 6-Dimension Qualitative Analysis (single Agent, recommended)

Launch a single Agent with full context (Mode A — leverages 1M context for cross-dimension validation):

```
Agent(
  subagent_type = "general-purpose",
  prompt = """
  Read shared/qualitative/qualitative_assessment_v2.md for the complete analysis framework.

  Also load these reference files:
    - shared/qualitative/references/judgment_examples.md (judgment anchors)
    - shared/qualitative/references/framework_guide.md (framework definitions)
    - shared/qualitative/agents/writing_style.md (writing style)
    - shared/qualitative/references/output_schema.md (parameter output spec)
    [HK stocks] + shared/qualitative/references/market_rules_hk.md
    [US stocks] + shared/qualitative/references/market_rules_us.md

  Target company: {stock_code} ({company_name})

  Data files:
    - Tushare data: output/{code}_{company}/data_pack_market.md
    - Annual report PDF: loaded in context (if available)

  Follow the 6-dimension framework in qualitative_assessment_v2.md.
  Pay special attention to "revenue quality decomposition" and "cross-validation" sections.

  Write final report to: output/{code}_{company}/qualitative_report.md
  """,
  description = "6-dimension qualitative analysis"
)
```

### Step 3: Generate HTML Dashboard Report (optional — only when user requests)

**Skip this step by default.** Only execute if the user explicitly requests HTML output (e.g., "--html" in arguments, or mentions "HTML"/"网页"/"仪表盘").

```bash
# For local viewing (standalone, inline CSS):
python3 scripts/report_to_html.py --input output/{code}_{company}/qualitative_report.md --output output/{code}_{company}/qualitative_report.html --standalone

# For website deployment (external CSS, terancejiang.com):
python3 scripts/report_to_html.py --input output/{code}_{company}/qualitative_report.md --output ~/Projects/Teracnejiang.com/zh/stock/{slug}.html
```

## 6 Dimensions Covered
1. Business model & capital characteristics (商业模式与资本特征)
2. Competitive advantage & moat (竞争优势与护城河)
3. External environment (外部环境)
4. Management & governance (管理层与治理)
5. MD&A interpretation (MD&A 解读)
6. Holding structure analysis (控股结构分析, conditional)

## v2 Key Changes
- **PDF-first architecture**: Annual report PDF is the primary data source; Tushare provides supplementary historical series
- **Single Agent mode (recommended)**: Uses 1M context for all 6 dimensions with cross-dimension validation
- **No data pre-split**: Eliminated split_data_pack.py step; agent receives full data
- **WebSearch fallback**: Only used when no PDF is provided

## Error Recovery
- If PDF download fails → fallback to WebSearch
- If PDF is scanned → use python3 scripts/pdf_preprocessor.py
- If Tushare fails → use yfinance fallback
- If PDF and Tushare data conflict → trust PDF, note discrepancy
- If WebSearch returns no results → mark as "⚠️ 数据不可用" and degrade that dimension
- Always produce a final report even with partial data

## Output
- **MD report** (default): output/{code}_{company}/qualitative_report.md
  - Includes: Executive Summary + 6 Dimensions + Cross-Validation + Deep Conclusion + Structured Parameters
- **PDF footnote data** (if PDF available): output/{code}_{company}/data_pack_report.md
  - Structured extraction: P2/P3/P4/P6/P13/SUB — used by downstream strategies (Turtle, etc.)
- **HTML dashboard** (optional, only when requested): output/{code}_{company}/qualitative_report.html
  - For local viewing: `--standalone` flag embeds CSS inline
  - For website deployment: references external CSS from terancejiang.com

Usage: /business-analysis 600887 or /business-analysis 00700.HK or /business-analysis AAPL
