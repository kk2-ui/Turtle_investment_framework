#!/usr/bin/env python3
"""Turtle Investment Framework - PDF Preprocessor (Phase 2A).

Scans annual report PDFs for 9 target sections using keyword matching
and outputs structured JSON for Agent fine-extraction.

Target sections:
    P2: Restricted cash (受限资产)
    P3: AR aging (应收账款账龄)
    P4: Related party transactions (关联方交易)
    P6: Contingent liabilities (或有负债)
    P13: Non-recurring items (非经常性损益)
    MDA: Management Discussion & Analysis (管理层讨论与分析)
    SUB: Subsidiary holdings (主要控股参股公司)
    STMT: Financial statements (财务报表 — 合并+母公司三表, multi_page模式)
    DAN: Depreciation & Amortization (折旧与摊销 — 现金流量表附表间接法)
    SEG: Segment revenue breakdown (主营业务构成)

Usage:
    python3 scripts/pdf_preprocessor.py --pdf report.pdf
    python3 scripts/pdf_preprocessor.py --pdf report.pdf --output output/sections.json
    python3 scripts/pdf_preprocessor.py --pdf report.pdf --verbose --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pdfplumber


# ---------------------------------------------------------------------------
# Feature #38: SECTION_KEYWORDS for 5 target sections
# Feature #43: Traditional Chinese keyword support
# ---------------------------------------------------------------------------

SECTION_KEYWORDS: Dict[str, List[str]] = {
    "P2": [
        # Simplified Chinese
        "所有权或使用权受限资产",
        "受限资产",
        "使用受限的资产",
        "所有权受限",
        "使用权受到限制",
        "受限的货币资金",
        "受到限制的资产",
        # Traditional Chinese (HK reports)
        "所有權或使用權受限資產",
        "受限資產",
        "使用受限的資產",
        # English (HK annual reports)
        "restricted bank deposits",
        "restricted cash",
        "assets pledged",
        "assets with restricted title",
    ],
    "P3": [
        # Simplified Chinese
        "应收账款账龄",
        "应收账款的账龄",
        "账龄分析",
        "应收账款按账龄披露",
        "应收账款按账龄列示",
        "应收款项账龄",
        # Traditional Chinese
        "應收賬款賬齡",
        "應收賬款的賬齡",
        "賬齡分析",
        # English (HK annual reports)
        "trade receivables",
        "ageing analysis of trade receivables",
        "trade receivables and contract assets",
    ],
    "P4": [
        # Financial-note-specific keywords (NOT generic "关联交易" which matches everywhere)
        # Simplified Chinese — notes section only
        "重大关联方交易",
        "关联方交易附注",
        "关联交易附注",
        # Traditional Chinese — notes section only
        "重大關聯方交易",
        "關聯方交易附註",
        "關聯交易附註",
        # English (HK annual reports) — notes section only
        "CONTINUING CONNECTED TRANSACTIONS",
        "Continuing Connected Transactions",
        "CONNECTED TRANSACTIONS",
        "Connected Transactions",
        "RELATED PARTY TRANSACTIONS",
        "Related Party Transactions",
        "MATERIAL RELATED PARTY TRANSACTIONS",
    ],
    "P6": [
        # Simplified Chinese
        "或有负债",
        "或有事项",
        "未决诉讼",
        "重大诉讼",
        "对外担保",
        "承诺及或有事项",
        "承诺和或有负债",
        # Traditional Chinese
        "或有負債",
        "或有事項",
        "未決訴訟",
        "承諾及或有事項",
        # English (HK annual reports)
        "contingent liabilities",
        "contingent liability",
        "commitments",
        "commitments and contingencies",
    ],
    "P13": [
        # Simplified Chinese - specific (prefer these for supplement zone)
        "非经常性损益项目及金额",
        "非经常性损益合计",
        # Simplified Chinese - general
        "非经常性损益",
        "非经常性损益明细",
        "非经常性损益项目",
        "扣除非经常性损益",
        "非经常性损益的项目和金额",
        # Traditional Chinese
        "非經常性損益",
        "非經常性損益明細",
        "非經常性損益項目及金額",
        # English (rare in HK, kept for compatibility)
        "non-recurring",
        "exceptional items",
    ],
    "MDA": [
        # Simplified Chinese
        "管理层讨论与分析",
        "经营情况讨论与分析",
        "经营情况的讨论与分析",
        "管理层分析与讨论",
        "董事会报告",
        # Traditional Chinese
        "管理層討論與分析",
        "經營情況討論與分析",
        "董事會報告",
        # English (HK annual reports)
        "MANAGEMENT DISCUSSION AND ANALYSIS",
        "Management Discussion and Analysis",
        "Business Review",
        "Financial Review",
        "Principal Risk Management Strategies",
        "Chairman's Statement",
        # HK Dividend declaration (often in Chairman's Statement / Directors' Report)
        "Final Dividend",
        "末 期 股 息",
        "末期股息",
        "Dividend per Share",
        "每股股息",
    ],
    "STMT": [
        # HK consolidated income statement
        "综合损益表",
        "综合收益及其他全面收益表",
        "综合损益及其他全面收益表",
        "Consolidated Statement of Profit or Loss",
        "Consolidated Income Statement",
        "Consolidated Statement of Financial Position",
        "Consolidated Statement of Cash Flows",
        # v2.33: HK BS standalone keywords (non-consolidated)
        "STATEMENT OF FINANCIAL POSITION",
        "Statement of Financial Position",
        "STATEMENT OF PROFIT OR LOSS",
        "Statement of Profit or Loss",
        "STATEMENT OF CASH FLOWS",
        "Statement of Cash Flows",
        "STATEMENT OF COMPREHENSIVE INCOME",
        "Statement of Comprehensive Income",
        "綜合財務狀況表",
        "綜合損益表",
        "綜合收益及其他全面收益表",
        "綜合損益及其他全面收益表",
        "綜合現金流量表",
        "綜合權益變動表",
        # HK report financial section markers
        "FINANCIAL STATEMENTS",
        "Financial Statements",
        "財務報表",
        # Traditional Chinese
        "綜合損益表",
        "綜合收益及其他全面收益表",
        "綜合損益及其他全面收益表",
        # A-share — all 3 consolidated statements
        "合并资产负债表",
        "合并利润表",
        "合并损益表",
        "合并现金流量表",
        # A-share — parent company statements (§3P/§4P)
        "母公司资产负债表",
        "母公司利润表",
        "母公司损益表",
        "母公司现金流量表",
        # A-share — statement zone markers (removed "财务报表"/"财务报告" — too broad, matches every notes page)
        # HK EPS note — contains profit attributable figure
        "Profit for the year attributable to owners",
        "earnings per share attributable",
        "本公司擁有人應佔本年度溢利",
        "每股基本盈利",
        # HK D&A in CF/PPE notes
        "Depreciation of property, plant and equipment (note",
        "物業、廠房及設備折舊（附註",
        "Depreciation of property, plant 物業、廠房及設備折舊",
        "物業、廠房及設備折舊",
        "Depreciation of property, plant",
        # Traditional Chinese A-share style (A+H dual-listed; removed "財務報表"/"財務報告" — too broad)
        "合併資產負債表",
        "合併利潤表",
        "合併現金流量表",
        "合併損益表",
        "合併收益表",
        "合併綜合收益表",
        "母公司資產負債表",
        "母公司利潤表",
        "母公司現金流量表",
    ],
    "SUB": [
        # 高特异性 — 主匹配
        "主要控股参股公司分析",
        "主要子公司及对公司净利润的影响",
        "主要控股参股公司情况",
        "控股子公司情况",
        # 中特异性
        "在子公司中的权益",
        "在其他主体中的权益",
        "纳入合并范围的主体",
        "合并范围的变化",
        # 删除: "长期股权投资" (歧义太大，匹配到 Note #17)
        # 新增: 更具体的变体
        "长期股权投资——对子公司",
        "长期股权投资——联营企业",
        # 繁体
        "主要控股參股公司分析",
        "在子公司中的權益",
        "在其他主體中的權益",
        "長期股權投資——對子公司",
        # English (HK annual reports)
        "particulars of principal subsidiaries",
        "principal subsidiaries",
        "segment information",
        "breakdown of the group's revenue",
    ],
    "DAN": [
        # A-share indirect method cash flow supplement
        "现金流量表补充资料",
        "合并现金流量表补充资料",
        "现金流量表附表",
        "现金流量表附注",
        # Sub-keywords for supplement location
        "固定资产折旧、油气资产折耗、生产性生物资产折旧",
        "固定資產折舊",
        "将净利润调节为经营活动现金流量",
        "將淨利潤調節為經營活動現金流量",
        "间接法编制的经营活动现金流量",
        "間接法",
        "间接法",
        # Traditional Chinese A+H — cash flow supplement
        "現金流量表補充資料",
        "合併現金流量表補充資料",
        # HK/English — cash flow notes (Notes to CF statement)
        "NOTES TO THE CONSOLIDATED STATEMENT OF CASH FLOWS",
        "NOTES TO THE CASH FLOW STATEMENT",
        "notes to the consolidated statement of cash flows",
        "notes to the cash flow statement",
        "Reconciliation of profit before taxation to net cash",
        "Reconciliation of profit before tax to net cash",
        # HK/English — D&A line items (for supplement zone location)
        "depreciation of property, plant and equipment",
        # v2.25: HK CF notes — note numbers from the CF statement body
        "NOTES TO THE CASH FLOW STATEMENT",
        "現金流量表附註",
        "合併現金流量表附註",
        "NET CASH FROM OPERATING ACTIVITIES",
        "depreciation of right-of-use assets",
        "amortisation of intangible assets",
        "depreciation and amortisation",
    ],
    "SEG": [
        # A-share revenue segment disclosure (§9 主营业务构成)
        "营业收入构成",
        "主营业务分行业",
        "主营业务分产品",
        "主营业务分地区",
        "营业收入及成本",
        "分部报告",
        "分部信息",
        # Traditional Chinese
        "營業收入構成",
        "主營業務分行業",
        "分部資料",
        "分部業績",
        "業務分部",
        "經營分部",
        "收入及分部",
        "按業務劃分",
        # English / HK — specific segment revenue data first
        "segment revenue and results",
        "segment revenue",
        "revenue by segment",
        "revenue breakdown",
        "segment information for the year",
        # Lower-priority (may match accounting policy notes)
        "operating segment",
        "segment information",
    ],
}

# Per-section extraction parameters (overrides defaults)
SECTION_EXTRACT_CONFIG: Dict[str, Dict[str, int]] = {
    "MDA":  {"buffer_pages": 12, "max_chars": 24000},
    "SUB":  {"buffer_pages": 2, "max_chars": 6000},
    "STMT": {"buffer_pages": 20, "max_chars": 160000, "multi_page": True},  # v2.33: 12→20 pages for HK report BS/IS/CF separation
    "P2":   {"buffer_pages": 3, "max_chars": 6000},    # v2.34: 1→3 pages, restricted assets
    "P3":   {"buffer_pages": 3, "max_chars": 6000},    # v2.34: 1→3 pages, AR aging
    "P4":   {"buffer_pages": 8, "max_chars": 12000},   # v2.34: 1→8 pages, related party notes deep in FS
    "P6":   {"buffer_pages": 3, "max_chars": 6000},    # v2.34: 1→3 pages, contingent liabilities
    "DAN":  {"buffer_pages": 4, "max_chars": 8000},    # v2.25: 2→4 pages to capture CF supplement notes
    "SEG":  {"buffer_pages": 2, "max_chars": 5000},    # 2-3 pages revenue segment tables
}
DEFAULT_BUFFER_PAGES = 1
DEFAULT_MAX_CHARS = 4000

# ---------------------------------------------------------------------------
# Zone detection markers for A-share annual reports (CSRC format)
# ---------------------------------------------------------------------------

ZONE_MARKERS: List[Tuple[str, str]] = [
    (r"第[一二三四五六七八九十百]+节\s*重要提示", "INTRO_ZONE"),
    (r"第[一二三四五六七八九十百]+节\s*公司简介", "INTRO_ZONE"),
    (r"第[一二三四五六七八九十百]+节\s*管理层讨论与分析", "MDA_ZONE"),
    (r"第[一二三四五六七八九十百]+节\s*经营情况讨论与分析", "MDA_ZONE"),
    (r"第[一二三四五六七八九十百]+节\s*公司治理", "GOVERNANCE_ZONE"),
    (r"第[一二三四五六七八九十百]+节\s*财务报告", "FIN_ZONE"),
    (r"第[一二三四五六七八九十百]+节\s*会计数据", "FIN_ZONE"),
    # Traditional Chinese A-share style zone markers (A+H dual-listed)
    (r"第[一二三四五六七八九十百]+節\s*財務報告", "FIN_ZONE"),
    (r"第[一二三四五六七八九十百]+節\s*會計數據", "FIN_ZONE"),
    (r"第[一二三四五六七八九十百]+節\s*重要提示", "INTRO_ZONE"),
    (r"第[一二三四五六七八九十百]+節\s*公司簡介", "INTRO_ZONE"),
    (r"第[一二三四五六七八九十百]+節\s*管理層討論與分析", "MDA_ZONE"),
    # Sub-zones within financial report
    (r"[四五六]\s*[、.．]\s*重要会计政策", "POLICY_ZONE"),
    (r"七\s*[、.．]\s*合并财务报表项目注释", "NOTES_ZONE"),
    (r"[一二三四五六七八九十]+[、.．]\s*补充资料", "SUPPLEMENT_ZONE"),

    # === v2.33: HK annual report zone markers (no "第X节" prefix) ===
    # HK reports use English/Traditional Chinese section titles without numeric prefixes
    # ⚠️ ORDER MATTERS: first match wins. GOV must come BEFORE NOTES
    # because "董事會報告" pages may contain cross-refs to "財務報表附註"
    # HK report: Governance (must be before NOTES/FIN patterns)
    (r"CORPORATE\s+GOVERNANCE\s+(?:REPORT|STATEMENT)", "GOVERNANCE_ZONE"),
    (r"Corporate\s+Governance\s+(?:Report|Statement)", "GOVERNANCE_ZONE"),
    (r"企業管治報告", "GOVERNANCE_ZONE"),
    (r"企业管治报告", "GOVERNANCE_ZONE"),
    (r"主席報告|主席报告|Chairman'?s?\s*Statement", "GOVERNANCE_ZONE"),
    (r"董事會報告(?:書|（續）)?\s*$|董事会报告(?:书|（续）)?|DIRECTORS'?\s*REPORT", "GOVERNANCE_ZONE"),
    (r"董事會報告\s", "GOVERNANCE_ZONE"),  # catches bare "董事會報告 董事欣然提呈..."
    # ESG
    (r"ENVIRONMENTAL[,\s]+SOCIAL\s+AND\s+GOVERNANCE", "GOVERNANCE_ZONE"),
    (r"Environmental[,\s]+Social\s+and\s+Governance", "GOVERNANCE_ZONE"),
    (r"環境[、,\s]*社會及管治", "GOVERNANCE_ZONE"),
    (r"环境[、,\s]*社会及管治", "GOVERNANCE_ZONE"),
    (r"ESG\s*報告|ESG\s*报告|ESG\s*REPORT", "GOVERNANCE_ZONE"),
    # NOTES_ZONE must come before FIN_ZONE
    # because "綜合財務報表附註" would otherwise match "綜合財務報表"→FIN_ZONE
    # HK report: Notes to FS (must be before FIN_ZONE patterns)
    (r"NOTES\s+TO\s+THE\s+(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS", "NOTES_ZONE"),
    (r"Notes\s+to\s+the\s+(?:Consolidated\s+)?Financial\s+Statements", "NOTES_ZONE"),
    (r"綜合財務報表附註", "NOTES_ZONE"),
    (r"财务报表附注", "NOTES_ZONE"),
    # Financial statements zone (FIN_ZONE) — after NOTES patterns
    (r"CONSOLIDATED\s+(?:STATEMENT|INCOME|BALANCE|CASH)", "FIN_ZONE"),
    (r"Consolidated\s+(?:Statement|Income|Balance|Cash)", "FIN_ZONE"),
    (r"STATEMENT\s+OF\s+(?:FINANCIAL\s+POSITION|PROFIT\s+OR\s+LOSS|COMPREHENSIVE\s+INCOME|CASH\s+FLOWS|CHANGES\s+IN\s+EQUITY)", "FIN_ZONE"),
    (r"Statement\s+of\s+(?:Financial\s+Position|Profit\s+or\s+Loss|Comprehensive\s+Income|Cash\s+Flows|Changes\s+in\s+Equity)", "FIN_ZONE"),
    (r"綜合財務報表", "FIN_ZONE"),
    (r"合併財務報表", "FIN_ZONE"),
    # HK report: Notes to FS
    (r"NOTES\s+TO\s+THE\s+(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS", "NOTES_ZONE"),
    (r"Notes\s+to\s+the\s+(?:Consolidated\s+)?Financial\s+Statements", "NOTES_ZONE"),
    # HK report: Independent auditor's report
    (r"INDEPENDENT\s+AUDITOR'?S?\s+REPORT", "AUDIT_ZONE"),
    (r"Independent\s+Auditor'?s?\s+Report", "AUDIT_ZONE"),
    (r"獨立核數師報告", "AUDIT_ZONE"),
    (r"独立核数师报告", "AUDIT_ZONE"),
    # HK report: Management Discussion
    (r"MANAGEMENT\s+DISCUSSION\s+AND\s+ANALYSIS", "MDA_ZONE"),
    (r"Management\s+Discussion\s+and\s+Analysis", "MDA_ZONE"),
    (r"管理層討論與分析", "MDA_ZONE"),
    # HK report: Directors' Report
    (r"DIRECTORS'?\s+REPORT", "MDA_ZONE"),
    # HK report: Policy/Accounting policies
    (r"SIGNIFICANT\s+ACCOUNTING\s+POLIC", "POLICY_ZONE"),
    (r"Significant\s+Accounting\s+Polic", "POLICY_ZONE"),
    (r"主要會計政策", "POLICY_ZONE"),
    (r"重要会计政策", "POLICY_ZONE"),

    # v2.33: Financial statement TABLE headers (table pages have no section-level zone markers)
    (r"綜合損益表(?!\s*附註)", "FIN_ZONE"),
    (r"綜合財務狀況表(?!\s*附註)", "FIN_ZONE"),
    (r"綜合現金流量表(?!\s*附註)", "FIN_ZONE"),
    (r"綜合權益變動表", "FIN_ZONE"),
    (r"綜合損益及其他全面收益表", "FIN_ZONE"),
    (r"合併資產負債表", "FIN_ZONE"),
    (r"合併利潤表", "FIN_ZONE"),
    (r"合併現金流量表", "FIN_ZONE"),
]

SECTION_ZONE_PREFERENCES: Dict[str, Dict[str, List[str]]] = {
    "P2":  {"prefer": ["NOTES_ZONE"], "avoid": ["POLICY_ZONE"]},
    "P3":  {"prefer": ["NOTES_ZONE"], "avoid": ["POLICY_ZONE"]},
    "P4":  {"prefer": ["NOTES_ZONE"], "avoid": ["POLICY_ZONE", "GOVERNANCE_ZONE", "MDA_ZONE"]},
    "P6":  {"prefer": ["NOTES_ZONE"], "avoid": ["POLICY_ZONE"]},
    "P13": {"prefer": ["SUPPLEMENT_ZONE", "NOTES_ZONE"], "avoid": ["POLICY_ZONE"]},
    "MDA":  {"prefer": ["MDA_ZONE"], "avoid": ["NOTES_ZONE", "FIN_ZONE", "POLICY_ZONE", "SUPPLEMENT_ZONE"]},
    "SUB":  {"prefer": ["NOTES_ZONE"], "avoid": ["POLICY_ZONE"]},
    "STMT": {"prefer": ["FIN_ZONE"], "avoid": ["NOTES_ZONE", "POLICY_ZONE", "SUPPLEMENT_ZONE", "GOVERNANCE_ZONE", "AUDIT_ZONE", "MDA_ZONE"]},
    "DAN":  {"prefer": ["SUPPLEMENT_ZONE", "NOTES_ZONE"], "avoid": ["POLICY_ZONE", "MDA_ZONE"]},
    "SEG":  {"prefer": ["MDA_ZONE", "NOTES_ZONE"], "avoid": ["POLICY_ZONE", "GOVERNANCE_ZONE"]},
}


# ---------------------------------------------------------------------------
# Feature #37: PDF text extraction with pdfplumber
# Feature #44: PyMuPDF fallback for garbled text
# Feature #45: Table-aware extraction
# ---------------------------------------------------------------------------

def _count_cjk_dup_pairs(text: str) -> int:
    """Count pairs of consecutive identical CJK (Unified/Extension A) characters.

    This detects the pdfplumber bug where each CJK glyph is extracted twice:
        "金茂服務" → "金金茂茂服服務務"
    Each duplicate pair contributes 1 to the count.
    """
    dup = 0
    for i in range(len(text) - 1):
        a, b = text[i], text[i + 1]
        if a != b:
            continue
        ca, cb = ord(a), ord(b)
        if ((0x4E00 <= ca <= 0x9FFF or 0x3400 <= ca <= 0x4DBF)
                and (0x4E00 <= cb <= 0x9FFF or 0x3400 <= cb <= 0x4DBF)):
            dup += 1
    return dup


def is_garbled(text: str, threshold: float = 0.30,
               cjk_dup_threshold: float = 0.05) -> bool:
    """Detect garbled text: >threshold fraction of non-CJK/ASCII/common-punct chars,
    OR CJK character duplication rate > cjk_dup_threshold (pdfplumber CFF font bug).

    The CJK duplication check catches the known pdfplumber issue where certain
    embedded fonts cause every CJK glyph to appear twice in extracted text.
    """
    if not text:
        return True

    # Check 1: CJK character duplication (pdfplumber CFF font bug)
    if len(text) >= 50:
        cjk_dup_pairs = _count_cjk_dup_pairs(text)
        cjk_dup_ratio = cjk_dup_pairs / len(text)
        if cjk_dup_ratio > cjk_dup_threshold:
            return True

    # Check 2: Non-normal character ratio (legacy check)
    normal = 0
    for ch in text:
        cp = ord(ch)
        if (
            0x20 <= cp <= 0x7E  # ASCII printable
            or 0x4E00 <= cp <= 0x9FFF  # CJK Unified Ideographs
            or 0x3400 <= cp <= 0x4DBF  # CJK Extension A
            or 0x3000 <= cp <= 0x303F  # CJK Punctuation
            or 0xFF00 <= cp <= 0xFFEF  # Fullwidth Forms
            or ch in "\n\r\t"
        ):
            normal += 1
    ratio = normal / len(text)
    return ratio < (1 - threshold)


def _tables_to_markdown(tables: list) -> str:
    """Convert pdfplumber tables to markdown format."""
    parts = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        # Clean cells
        cleaned = []
        for row in table:
            cleaned.append([
                (cell or "").replace("\n", " ").strip()
                for cell in row
            ])
        # Build markdown table
        header = cleaned[0]
        md = "| " + " | ".join(header) + " |\n"
        md += "| " + " | ".join(["---"] * len(header)) + " |\n"
        for row in cleaned[1:]:
            # Pad row if shorter than header
            while len(row) < len(header):
                row.append("")
            md += "| " + " | ".join(row[:len(header)]) + " |\n"
        parts.append(md)
    return "\n".join(parts)


def extract_all_pages(pdf_path: str, verbose: bool = False) -> List[Tuple[int, str]]:
    """Extract text from all pages of a PDF using pdfplumber.

    Falls back to PyMuPDF if pdfplumber produces garbled text.

    Args:
        pdf_path: Path to the PDF file.
        verbose: Print progress messages.

    Returns:
        List of (page_number_1indexed, text) tuples.

    Raises:
        FileNotFoundError: If the PDF file doesn't exist.
        RuntimeError: If the PDF cannot be opened or is encrypted.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages_text: List[Tuple[int, str]] = []
    garbled_count = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            if verbose:
                print(f"Extracting {total} pages with pdfplumber...")

            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                text = page.extract_text() or ""

                # Feature #45: table-aware extraction
                tables = page.extract_tables()
                if tables:
                    table_md = _tables_to_markdown(tables)
                    if table_md:
                        text = text + "\n\n[TABLE]\n" + table_md

                if is_garbled(text) and len(text) > 50:
                    garbled_count += 1

                pages_text.append((page_num, text))

                if verbose and page_num % 50 == 0:
                    print(f"  ...page {page_num}/{total}")

    except Exception as e:
        err_msg = str(e).lower()
        if "encrypt" in err_msg or "password" in err_msg:
            raise RuntimeError(f"PDF is encrypted: {pdf_path}") from e
        raise RuntimeError(f"Cannot open PDF: {pdf_path}: {e}") from e

    # Feature #44: PyMuPDF fallback if >30% pages are garbled
    if total > 0 and garbled_count / total > 0.30:
        if verbose:
            print(f"Garbled text detected ({garbled_count}/{total} pages), trying PyMuPDF...")
        fallback = fallback_extract_pymupdf(pdf_path, verbose=verbose)
        if fallback:
            return fallback

    return pages_text


def fallback_extract_pymupdf(pdf_path: str, verbose: bool = False) -> Optional[List[Tuple[int, str]]]:
    """Fallback extraction using PyMuPDF (fitz).

    Returns None if PyMuPDF is not installed.
    """
    try:
        import fitz
    except ImportError:
        if verbose:
            print("PyMuPDF not installed, skipping fallback.")
        return None

    pages_text: List[Tuple[int, str]] = []
    try:
        doc = fitz.open(pdf_path)
        total = len(doc)
        if verbose:
            print(f"Extracting {total} pages with PyMuPDF...")
        for i in range(total):
            page = doc[i]
            text = page.get_text() if hasattr(page, 'get_text') else page.getText()
            pages_text.append((i + 1, text or ""))
        doc.close()
    except Exception as e:
        if verbose:
            print(f"PyMuPDF fallback failed: {e}")
        return None

    return pages_text


# ---------------------------------------------------------------------------
# Zone detection for A-share annual report structure
# ---------------------------------------------------------------------------

def detect_zones(pages_text: List[Tuple[int, str]]) -> Dict[int, str]:
    """Detect report structure zones by scanning for section markers.

    Returns:
        Dict mapping page_number -> zone_name. Pages without a detected
        zone inherit from the most recent zone marker before them.
        Returns empty dict if no zone markers are found.
    """
    zone_transitions: List[Tuple[int, str]] = []

    for page_num, text in pages_text:
        if not text:
            continue
        for pattern, zone_name in ZONE_MARKERS:
            if re.search(pattern, text):
                zone_transitions.append((page_num, zone_name))
                break  # first matching marker per page

    if not zone_transitions:
        return {}

    # Build page->zone mapping (each page inherits from last marker)
    zone_transitions.sort(key=lambda x: x[0])
    page_zones: Dict[int, str] = {}
    current_zone = None
    transition_idx = 0

    for page_num, _ in pages_text:
        while transition_idx < len(zone_transitions) and zone_transitions[transition_idx][0] <= page_num:
            current_zone = zone_transitions[transition_idx][1]
            transition_idx += 1
        if current_zone:
            page_zones[page_num] = current_zone

    return page_zones


# ---------------------------------------------------------------------------
# Feature #39: Keyword matching to locate sections
# Feature #46: Section priority scoring
# ---------------------------------------------------------------------------

def _score_match(
    page_num: int, total_pages: int, text: str, keyword: str,
    zone: Optional[str] = None, section_id: Optional[str] = None,
) -> float:
    """Score a keyword match: prefer correct report zone over TOC.

    Scoring:
        +1.0 base for a match
        +2.0 if page is in a preferred zone for this section
        -2.0 if page is in an avoided zone for this section
        +0.5 fallback position bonus if no zone info available
        -0.5 if page looks like TOC (contains "目录" or "目 录")
        +0.3 if keyword appears in a heading-like context (numbered section)
        -0.3 if keyword only appears as a cross-reference ("详见")
    """
    score = 1.0

    # Zone-aware scoring (replaces position bonus when zone info available)
    if zone and section_id and section_id in SECTION_ZONE_PREFERENCES:
        prefs = SECTION_ZONE_PREFERENCES[section_id]
        # v2.33: Hard exclusion — GOVERNANCE_ZONE pages must NOT appear in any financial section
        # HK reports often have ESG/企业管治 sections before the financial statements
        if zone == "GOVERNANCE_ZONE":
            return -100.0  # Hard reject — ESG/管治 pages must not enter any financial section
        # v2.33: Hard reject NOTES_ZONE for STMT (90+ pages of FS notes are noise for extraction)
        if zone == "NOTES_ZONE" and section_id == "STMT":
            return -100.0  # Hard reject — Notes pages belong in P2-P6, not STMT
        if zone in prefs.get("prefer", []):
            score += 2.0
        elif zone in prefs.get("avoid", []):
            score -= 2.0
    elif total_pages > 0:
        # Fallback: position-based scoring when no zone info
        if page_num / total_pages > 0.30:
            score += 0.5

    # Penalize TOC pages
    if "目录" in text or "目 录" in text:
        score -= 0.5

    # Penalize cross-references ("详见注释七'31、所有权或使用权受限资产'")
    kw_pos = text.find(keyword)
    if kw_pos > 0:
        before = text[max(0, kw_pos - 30):kw_pos]
        if "详见" in before or "参见" in before or "参照" in before:
            score -= 0.3

        # v2.35: Cross-reference penalty — "載於綜合財務報表附註30「重大關聯方交易」"
        # These are NOT the actual section — they're pointers to it. Force skip.
        xref_patterns = [r'載[於于].*?附註\d+', r'载[于於].*?附注\d+', r'(?:see|refer to)\s+note\s+\d+']
        for xp in xref_patterns:
            if re.search(xp, text[max(0,kw_pos-100):kw_pos+50], re.IGNORECASE):
                score -= 2.0  # Significant penalty for cross-references
                break

    # SUB context scoring: penalize accounting detail, reward subsidiary operating data
    if section_id == "SUB" and kw_pos >= 0:
        context_window = text[max(0, kw_pos - 200):min(len(text), kw_pos + 200)]
        # Penalize: accounting detail context
        acct = ["权益法", "账面余额", "减值准备", "成本法", "账面价值"]
        if sum(1 for a in acct if a in context_window) >= 2:
            score -= 1.5
        # Reward: subsidiary operating data context
        subs = ["主营业务", "营业收入", "净利润", "注册资本", "持股比例"]
        if sum(1 for s in subs if s in context_window) >= 2:
            score += 1.0

    # DAN context scoring: penalize accounting policy, reward supplement table context
    if section_id == "DAN" and kw_pos >= 0:
        context_window = text[max(0, kw_pos - 200):min(len(text), kw_pos + 200)]
        # Penalize: accounting policy context
        policy_signals = ["会计政策", "会计估计", "折旧方法", "摊销方法", "折旧年限", "残值率"]
        if sum(1 for p in policy_signals if p in context_window) >= 1:
            score -= 2.0
        # Reward: supplement table context (indirect method)
        supplement_signals = [
            "补充资料", "间接法", "调节为经营活动现金流量",
            "净利润", "经营活动产生的现金流量净额",
            "固定资产折旧、油气资产折耗",
        ]
        if sum(1 for s in supplement_signals if s in context_window) >= 2:
            score += 2.0
        # Bonus: near "固定资产折旧、油气资产折耗、生产性生物资产折旧" (the exact line item)
        if "固定资产折旧、油气资产折耗" in context_window:
            score += 1.5

    # P3 context scoring: penalize non-AR aging (prepayments, other payables)
    if section_id == "P3" and kw_pos >= 0:
        context_window = text[max(0, kw_pos - 200):min(len(text), kw_pos + 200)]
        non_ar = ["预付款项", "预付账款", "预付", "应付账款", "应付票据", "其他应付"]
        if any(term in context_window for term in non_ar):
            score -= 2.0

    # Bonus: keyword appears near a numbered heading pattern
    # e.g., "31、所有权或使用权受限资产" or "十四、关联方及关联交易"
    heading_patterns = [
        r"\d+[、.．]\s*" + re.escape(keyword),
        r"[一二三四五六七八九十]+[、.．]\s*" + re.escape(keyword),
    ]
    for pat in heading_patterns:
        if re.search(pat, text):
            score += 0.3
            break

    if section_id == "MDA":
        kw_norm = keyword.lower()
        if kw_norm in {"management discussion and analysis", "管理层讨论与分析", "管理層討論與分析"}:
            score += 4.0
        elif kw_norm in {"business review", "financial review"}:
            score += 1.5
        elif kw_norm in {"chairman's statement", "principal risk management strategies"}:
            score -= 1.0

    return score


def find_section_pages(
    pages_text: List[Tuple[int, str]],
    section_keywords: Dict[str, List[str]] = None,
) -> Dict[str, List[int]]:
    """Locate sections by scanning all pages for keywords.

    Args:
        pages_text: List of (page_number, text) tuples.
        section_keywords: Keyword dict (default: SECTION_KEYWORDS).

    Returns:
        Dict mapping section_id -> [page_numbers] sorted by priority score (best first).
    """
    if section_keywords is None:
        section_keywords = SECTION_KEYWORDS

    total_pages = len(pages_text)
    results: Dict[str, List[int]] = {}

    # Detect zones for scoring
    page_zones = detect_zones(pages_text)

    for section_id, keywords in section_keywords.items():
        # Collect (score, page_num) for all matches
        scored_matches: List[Tuple[float, int]] = []

        for page_num, text in pages_text:
            if not text:
                continue
            for kw in keywords:
                if kw in text:
                    zone = page_zones.get(page_num)
                    score = _score_match(page_num, total_pages, text, kw,
                                         zone=zone, section_id=section_id)
                    scored_matches.append((score, page_num))
                    break  # one keyword per page is enough

        # Sort by score descending, then by page number ascending as tiebreak
        scored_matches.sort(key=lambda x: (-x[0], x[1]))

        # v2.35: Zone-aware filtering — reject matches on avoided zones (score < 0)
        # This prevents P4 from capturing "关联交易" mentions in the board report
        # and forces the algorithm to find the actual financial notes pages instead.
        # If a section has zone preferences and ALL matches are in avoided zones,
        # the section gets no pages — which is the honest outcome.
        has_prefs = section_id in SECTION_ZONE_PREFERENCES
        if has_prefs and scored_matches and scored_matches[0][0] >= 0:
            # Keep only positive-scored matches (in preferred zone or unzoned)
            scored_matches = [(s, pn) for s, pn in scored_matches if s >= 0]
        elif has_prefs and scored_matches and scored_matches[0][0] < 0:
            # All matches are in avoided zones — section gets nothing
            scored_matches = []

        # Deduplicate page numbers while preserving order
        seen = set()
        ordered_pages = []
        for _, pn in scored_matches:
            if pn not in seen:
                seen.add(pn)
                ordered_pages.append(pn)

        results[section_id] = ordered_pages

    return results


# ---------------------------------------------------------------------------
# Feature #40: Context extraction with page buffer
# ---------------------------------------------------------------------------

def extract_section_context(
    pages_text: List[Tuple[int, str]],
    section_pages: Dict[str, List[int]],
    section_keywords: Dict[str, List[str]] = None,
    buffer_pages: int = 1,
    max_chars: int = 4000,
    page_zones: Dict[int, str] = None,
) -> Dict[str, Optional[str]]:
    """Extract context text for each section using best-match page +/- buffer.

    Centers the extraction around the first keyword match position on the
    target page to maximize relevance.

    Args:
        pages_text: List of (page_number, text) tuples.
        section_pages: Output from find_section_pages.
        section_keywords: Keywords dict for locating match position.
        buffer_pages: Number of pages before/after to include.
        max_chars: Maximum characters per section.

    Returns:
        Dict mapping section_id -> extracted text or None if not found.
    """
    if section_keywords is None:
        section_keywords = SECTION_KEYWORDS

    # Build a lookup: page_num -> text
    page_lookup: Dict[int, str] = {pn: text for pn, text in pages_text}

    contexts: Dict[str, Optional[str]] = {}

    for section_id, matched_pages in section_pages.items():
        if not matched_pages:
            contexts[section_id] = None
            continue

        # Per-section config overrides function defaults
        cfg = SECTION_EXTRACT_CONFIG.get(section_id, {})
        sect_buffer = cfg.get("buffer_pages", buffer_pages)
        sect_max = cfg.get("max_chars", max_chars)
        multi_page = cfg.get("multi_page", False)

        if multi_page:
            # Multi-page mode: extract from ALL matched pages (±buffer each),
            # deduplicate by page number, **keep in score-priority order** (best
            # matches first). Do NOT sort by page number.
            # v2.33: Skip pages in avoided zones for this section
            avoid_zones = SECTION_ZONE_PREFERENCES.get(section_id, {}).get("avoid", [])
            extracted_pages = set()
            parts = []
            for mp in matched_pages[:8]:  # limit to top 8 matched pages (score order)
                for offset in range(-sect_buffer, sect_buffer + 1):
                    target = mp + offset
                    if target in page_lookup and target not in extracted_pages:
                        # v2.33: skip pages tagged with avoided zones
                        page_zone = (page_zones or {}).get(target, "")
                        if page_zone in avoid_zones:
                            continue
                        extracted_pages.add(target)
                        text = page_lookup[target]
                        if text:
                            parts.append((target, f"--- p.{target} ---\n{text}"))
            # Keep in score-priority order — do NOT sort by page number
            combined = "\n\n".join(p[1] for p in parts)
        else:
            # Single-page mode (default): center around best match
            best_page = matched_pages[0]
            if section_id == "MDA":
                early_candidates = [
                    pn for pn in matched_pages
                    if 20 <= pn <= max(60, int(len(pages_text) * 0.35))
                ]
                if early_candidates:
                    best_page = min(early_candidates)

            # Collect text from (best - buffer) to (best + buffer)
            parts = []
            for offset in range(-sect_buffer, sect_buffer + 1):
                target = best_page + offset
                if target in page_lookup:
                    text = page_lookup[target]
                    if text:
                        parts.append(f"--- p.{target} ---\n{text}")

            combined = "\n\n".join(parts)

        # If too long, try to center around the keyword match
        if len(combined) > sect_max:
            keywords = section_keywords.get(section_id, [])
            combined = _center_truncate(combined, keywords, sect_max)

        contexts[section_id] = combined

    return contexts


def _center_truncate(text: str, keywords: list, max_chars: int) -> str:
    """Truncate text centered around the first keyword match."""
    # Find the first keyword position
    match_pos = len(text)
    for kw in keywords:
        pos = text.find(kw)
        if pos >= 0 and pos < match_pos:
            match_pos = pos

    if match_pos == len(text):
        # No keyword found, fall back to simple truncation
        return _truncate_at_boundary(text, max_chars)

    # Center the window around the match
    half = max_chars // 2
    start = max(0, match_pos - half // 2)  # More text after match than before
    end = min(len(text), start + max_chars)
    start = max(0, end - max_chars)

    result = text[start:end]

    # Clean up: try to start at a page boundary or line boundary
    if start > 0:
        newline_pos = result.find("\n")
        if newline_pos >= 0 and newline_pos < 200:
            result = result[newline_pos + 1:]

    return _truncate_at_boundary(result, max_chars)


def _truncate_at_boundary(text: str, max_chars: int) -> str:
    """Truncate text at the last sentence boundary before max_chars."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    # Try to find last Chinese period, question mark, or newline
    for sep in ["。", "\n", "；", ".", "!", "！"]:
        last_pos = truncated.rfind(sep)
        if last_pos > max_chars * 0.5:  # Don't cut too aggressively
            return truncated[:last_pos + 1]

    return truncated


# ---------------------------------------------------------------------------
# Feature #41: JSON output writer
# ---------------------------------------------------------------------------
# Feature #47: Structured financial value extraction from STMT/DAN text
# ---------------------------------------------------------------------------

# Regex patterns for key financial statement line items.
# Bilingual: Simplified Chinese + Traditional Chinese + English (HK reports).
# Amounts are in original units, convert to 百万元 by dividing by 1e6.
# For HK stocks reporting in 千元 (RMB'000), adjust to /1000.
_FIN_PATTERNS = [
    # === Balance Sheet (合并资产负债表 / 綜合財務狀況表) ===
    ("货币资金", r"(?:货币资金|現金及現金等價物|銀行結存及現金|Cash and cash equivalents|銀行結餘及現金)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("应收账款", r"(?:应收账款|應收賬款|應收款項|貿易應收款|Trade receivables|貿易應收款項及應收票據)[^账龄票据融资]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("存货", r"(?:存货|存貨|Inventories|庫存)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("流动资产合计", r"(?:流动资产合?计|流動資產合?計|流動資產總額|Total current assets)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("固定资产", r"(?:固定资产|固定資產|物業、廠房及設備|Property, plant and equipment)[^清减折旧累]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("资产总计", r"(?:资产总?计|資產總[值計]|總資產|Total assets)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("短期借款", r"(?:短期借款|短期銀行貸款|Short-term borrowings|短期借貸)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("应付账款", r"(?:应付账款|應付賬款|應付款項|貿易應付款|Trade payables|貿易應付款項)[^票据]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("合同负债", r"(?:合同负债|合約負債|合約負債|Contract liabilities)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("流动负债合计", r"(?:流动负债合?计|流動負債合?計|流動負債總額|Total current liabilities)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("长期借款", r"(?:长期借款|長期借款|長期銀行貸款|Long-term borrowings|非流動銀行貸款)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("负债合计", r"(?:负债总?计|负债合?计|負債總[值計]|負債合?計|Total liabilities)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("归母权益", r"(?:归属于母公司[所股]|归母|本公司擁有人應佔權益|Equity attributable to owners|歸屬母公司權益|母公司權益持有人).*?(?:权益|權益|equity)[合计]?[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),

    # === Cash Flow Statement (合并现金流量表 / 綜合現金流量表) ===
    ("经营活动CF", r"(?:Net cash(?: flows)? (?:from|generated from) operating activities|经营活动(?:产生|的).*?现金流量净额|經營活動(?:所得|產生).*?現金流量淨額|經營業務.*?現金淨額|Net cash from operating)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("投资活动CF", r"(?:投资活动(?:产生|的).*?现金流量净额|投資活動.*?現金流量淨額|NET CASH (?:FROM|USED IN) INVESTING|USED IN INVESTING|投資活動.*?現金淨額)[\s\S]{0,80}?(\(?[\d,]{7,}\)?)"),
    ("筹资活动CF", r"(?:筹资活动(?:产生|的).*?现金流量净额|籌資活動.*?現金流量淨額|融資活動.*?現金流量淨額|NET CASH (?:FROM|USED IN) FINANCING)[\s\S]{0,80}?(\(?[\d,]{7,}\)?)"),  # parens = negative
    # Capex: 购建固定资产 (A-share) / 購置物業、廠房及設備 (HK) / Purchase of PPE (HK)
    ("Capex", r"(?:Purchase of (?:items of )?property, plant|Payments (?:for|of) property, plant|購置物業[、,]?\s*廠房及設備|购建固定资产|購買物業|購入固定資產|購建固定資產).*?([\d,]{5,}(?:\.\d+)?)"),
    ("处置固定资产收回", r"(?:处置固定资产|處置固定資產|出售物業[、,]?\s*廠房及設備|Proceeds from disposal of property, plant and equipment)[\s\S]{0,120}?([\d,]{7,}(?:\.\d+)?)"),

    # === Income Statement (合并利润表 / 綜合損益表) ===
    ("营业收入", r"(?:REVENUE|营业总?收入|營業總收入|營業收入|營業額|Revenue)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("营业成本", r"(?:Direct operating expenses|营业总?成本|營業成本|銷售成本|Cost of sales|Cost of goods sold)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("归母净利润", r"(?:PROFIT FOR THE YEAR|归属于母公司[股]|归母|歸屬於母公司股東的淨利潤|歸屬於母公司所有者的淨利潤|本公司擁有人應佔(?:本年度)?溢利|Profit (?:for the year )?attributable.*?owners|母公司權益持有人應佔溢利|Owners of the Company.*?本公司擁有人)[\s\S]{0,200}?([\d,]{7,}(?:\.\d+)?)"),

    # === D&A (from DAN / Cash Flow Notes) ===
    # v2.19: Match "Depreciation of PPE" followed by a 6-digit number within 50 chars.
    # Must NOT be in policy context ("is calculated", "straight-line", "estimated").
    ("固定资产折旧", r"(?:固定资产折旧|固定資產折舊|物業[、,]?\s*廠房及設備折舊|Depreciation of property, plant(?:.*?and equipment)?)[\s\S]{0,120}?([\d,]{6,}(?:\.\d+)?)"),
    ("无形资产摊销", r"(?:无形资产摊销|無形資產攤銷|Amorti[sz]ation of intangible assets(?!\s+is\s))(?:[^)]{0,50}?)([\d,]{6,}(?:\.\d+)?)"),
    ("长期待摊费用摊销", r"(?:长期待摊费用摊销|長期待攤費用攤銷|Amorti[sz]ation of deferred expenses).*?([\d,]{6,}(?:\.\d+)?)"),

    # === Supplementary HK fields (v2.16: fill 15→23 field gap) ===
    ("应收款项融资", r"(?:应收款项融资|應收款項融資|應收票據|Bills receivable)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("应付票据", r"(?:应付票据|應付票據|Bills payable)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("合同负债", r"(?:合同负债|合約負債|Contract liabilities|遞延收益)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("投资收益", r"(?:投资收益|投資收益|Investment income|其他收入)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    ("政府补贴", r"(?:政府(?:补助|補助|补贴|補貼)|Government grants|政府資助)[\s\S]{0,80}?([\d,]{6,}(?:\.\d+)?)"),
    ("股本", r"(?:股本|已發行股本|Share capital|普通股股本)[\s\S]{0,80}?([\d,]{6,}(?:\.\d+)?)"),
    # Parent company BS (HK reports often don't separate parent BS, but try)
    ("母公司现金", r"(?:母公司|公司本身|Company level).*?(?:现金|現金|Cash)[\s\S]{0,80}?([\d,]{7,}(?:\.\d+)?)"),
    # === P&L supplementary fields (v2.25 — attempted; HK bilingual text often defeats regex) ===
    # Note: These patterns are best-effort deterministic extraction.
    # HK reports with dense bilingual text frequently fail regex matching.
    # Gaps are filled by Phase 2B Agent extraction (see phase2_PDF解析.md §STMT checklist).
    ("少数股东损益", r"(?:少数股东(?:损益|应?佔|应占).*?(?:溢利|利润|亏损)|非控股权益.*?溢利|Non-controlling interests.*?profit)[\s\S]{0,200}?([\d,]{6,}(?:\.\d+)?)"),
    ("税前利润", r"(?:税前(?:溢利|利润|盈利)|除所得税前|Profit before (?:income )?tax|Income before tax)[\s\S]{0,120}?([\d,]{6,}(?:\.\d+)?)"),
    ("所得税", r"(?:所得税(?:费用|開支|抵免)?|Income tax(?: expense| credit| benefit)?)[\s\S]{0,120}?(\(?[\d,]{6,}(?:\.\d+)?\)?)"),
    ("利息支出", r"(?:利息(?:支出|開支|费用|費用)|财务(?:费用|費用).*?利息|Finance costs|Interest expense)[\s\S]{0,120}?([\d,]{5,}(?:\.\d+)?)"),
    # === CF supplementary fields ===
    ("已付股息", r"(?:已付股息|股息(?:支付|分派|派付)|已?分[配派]股利|Dividends paid|dividends paid to)[\s\S]{0,200}?([\d,]{6,}(?:\.\d+)?)"),
    # === BS supplementary fields ===
    ("商誉", r"(?:商誉|商譽|Goodwill)[^减值摊]{0,120}?([\d,]{6,}(?:\.\d+)?)"),
    ("无形资产", r"(?:无形资产[^摊]|無形資產[^攤]|Intangible assets)[\s\S]{0,120}?([\d,]{6,}(?:\.\d+)?)"),
    ("使用权资产", r"(?:使用权资产|使用權資產|Right-of-use assets)[\s\S]{0,120}?([\d,]{6,}(?:\.\d+)?)"),
    ("租赁负债", r"(?:租赁负债|租賃負債|Lease liabilities)[\s\S]{0,120}?([\d,]{6,}(?:\.\d+)?)"),
    # v2.26: BS-contextualized — prefixed with equity/total terms to avoid matching P&L split line
    ("少数股东权益", r"(?:Total equity|權益總額|Total.*?equity|Equity attributable|本公司擁有人應佔|少数股东(?:权益|權益)|非控股.*?權益(?!\s*\d)|Non-controlling interests(?![\s\S]{0,50}?[Pp]rofit))(?:[\s\S]{0,200}?)([\d,]{6,}(?:\.\d+)?)"),
    ("递延税项资产", r"(?:递延税项资产|遞延稅項資產|Deferred tax assets)[\s\S]{0,80}?([\d,]{6,}(?:\.\d+)?)"),
    ("递延税项负债", r"(?:递延税项负债|遞延稅項負債|Deferred tax liabilities)[\s\S]{0,80}?([\d,]{6,}(?:\.\d+)?)"),
    # === Per-share / shares outstanding ===
    ("总股本", r"(?:已发行(?:普通)?股[份本]|總?股本|普通股股[份本]|Number of (?:ordinary )?shares|Shares outstanding)[\s\S]{0,200}?([\d,]{7,}(?:\.\d+)?)"),
    # === DPS & dividend total ===
    ("每股股息", r"(?:每股股息|每股(?:末期|中期|全年)股息|Dividend per share|DPS|末期股息.*?每股|Final dividend.*?per share|末期股息.*?(?:人民币|港幣|港元|HK).*?(?:分|cents?)|末.?期.?股.?息.*?(?:RMB|HK|港).*?(?:分|cents?)).*?([\d,]+\.?\d*)"),
    ("股息总额", r"(?:宣派.*?股息|Declared.*?dividend|股息总额|Total dividend|dividends.*?paid).*?([\d,]{6,}(?:\.\d+)?)"),
]


def extract_financial_values(contexts: Dict[str, Optional[str]]) -> Dict[str, float]:
    """Extract structured financial values from STMT and DAN raw text.

    Uses regex to find key line items (Capex, OCF, BS科目) that Phase 2B
    Agent would otherwise miss. This is deterministic extraction — no LLM needed.

    Auto-detects report unit (元 vs 千元 vs 百万) and converts accordingly.

    Returns:
        Dict mapping field_name -> value_in_millions (百万元).
        Fields not found are excluded from the dict.
    """
    results = {}

    # Combine STMT + DAN text for searching
    # Combine all section text for searching
    text_parts = []
    for section in ["STMT", "DAN"]:
        txt = contexts.get(section)
        if txt:
            clean = re.sub(r'--- p\.\d+ ---\n', '', txt)
            text_parts.append(clean)
    combined = "\n".join(text_parts)

    # Auto-detect unit from report headers
    # A-share: 人民币元 → /1,000,000
    # HK: 人民币千元 / RMB'000 → /1,000
    # HK: 百万元 / million → /1
    unit_divisor = 1_000_000  # default: 元→百万
    if re.search(r'(?:人民币|人民幣|港元|港幣|RMB|HKD)\s*[千仟]元|(?:RMB|HKD).?000', combined):
        unit_divisor = 1_000  # 千元→百万
    elif re.search(r'(?:百万|百萬|million)\s*(?:元|港元|人民币|港幣)', combined, re.IGNORECASE):
        unit_divisor = 1  # already in millions
    else:
        # v4.5: heuristic — if most numbers are 7-8 digits, it is 千元 not 元
        nums = re.findall(r'[\d,]{7,8}', combined)
        if len(nums) > 10:
            unit_divisor = 1_000  # 千元→百万
    if re.search(r'(?:人民币|人民幣|RMB)\s*[千仟]元|RMB\s*[\'′]\s*000', combined):
        unit_divisor = 1_000  # 千元→百万
    elif re.search(r'(?:百万|百萬|million)\s*(?:元|港元|人民币|港幣)', combined, re.IGNORECASE):
        unit_divisor = 1  # already in millions

    # v2.19: Table fallback — when regex fails, try [TABLE] blocks
    # Used for HK income statements where pdfplumber strips row labels
    _table_fallback_fields = {'营业收入', '资产总计'}  # these are reliably the largest number

    for field_name, pattern in _FIN_PATTERNS:
        # v2.19: Use unified combined text for all fields.
        # D&A false positives (accounting policy matches) are caught by the sanity check below.
        match = re.search(pattern, combined, re.MULTILINE | re.DOTALL)
        if match:
            try:
                raw = match.group(1).replace(",", "")
                is_neg = raw.startswith("(") and raw.endswith(")")
                if is_neg: raw = raw[1:-1]
                value = float(raw)
                if is_neg: value = -value
                value_m = value / unit_divisor
                results[field_name] = round(value_m, 2)
            except (ValueError, IndexError):
                continue
        elif field_name in _table_fallback_fields:
            # Fallback: search [TABLE] blocks for the largest number
            # (Revenue and Total Assets are always the max in their respective tables)
            all_tables = re.findall(r'\[TABLE\](.*?)(?=\[TABLE\]|\n\n--- p\.|\Z)', combined, re.DOTALL)
            for tbl in all_tables:
                nums = re.findall(r'([\d,]{7,})', tbl)
                if nums:
                    vals = sorted([int(n.replace(',','')) for n in nums], reverse=True)
                    # Revenue/TA should be 7-8 digits and plausibly large
                    if vals[0] > 1_000_000:  # >1M in raw units = >1B RMB in '000s
                        results[field_name] = round(vals[0] / unit_divisor, 2)
                        break  # use the first plausible table

    # v2.19: Post-extraction sanity — if Revenue < NP, regex picked wrong line
    # Revenue is the largest number that appears EXACTLY TWICE in tables
    # (once in IS, once in segment note). Share count is the true max but excluded.
    rev = results.get('营业收入', 0) or 0
    npat = results.get('归母净利润', 0) or 0

    # v2.19: D&A sanity — if depreciation/amortization > Revenue*0.3, it's
    # accumulated BS value, not annual P&L charge. Zero it out.
    dep = results.get('固定资产折旧', 0) or 0
    amort = results.get('无形资产摊销', 0) or 0
    if rev > 0:
        if dep > rev * 0.3:
            results['固定资产折旧'] = 0
        if amort > rev * 0.3:
            results['无形资产摊销'] = 0

    if rev > 0 and npat > 0 and rev < npat * 1.5:
        all_tables = re.findall(r'\[TABLE\](.*?)(?=\[TABLE\]|\n\n--- p\.|\Z)', combined, re.DOTALL)
        freq = {}
        for tbl in all_tables:
            seen=set()
            for n in re.findall(r'([\d,]{7,})', tbl):
                v=int(n.replace(',',''))
                if v not in seen: freq[v]=freq.get(v,0)+1; seen.add(v)
        # Revenue: max number appearing exactly 2x (IS + segment note)
        rev2x = [v for v,c in freq.items() if c==2 and v<2_000_000_000]
        if rev2x:
            results['营业收入'] = round(max(rev2x) / unit_divisor, 2)

    # Sanity for 资产总计: must be > 归母权益. Use 2x frequency rule.
    ta = results.get('资产总计', 0) or 0
    eq = results.get('归母权益', 0) or 0
    if ta > 0 and eq > 0 and ta < eq:
        results['资产总计'] = 0  # clearly wrong, recalc below
    if (results.get('资产总计', 0) or 0) == 0 and eq > 0:
        # Total Assets: max number appearing 2-3x and > equity
        all_tables = re.findall(r'\[TABLE\](.*?)(?=\[TABLE\]|\n\n--- p\.|\Z)', combined, re.DOTALL)
        freq = {}
        for tbl in all_tables:
            seen=set()
            for n in re.findall(r'([\d,]{7,})', tbl):
                v=int(n.replace(',',''))
                if v not in seen: freq[v]=freq.get(v,0)+1; seen.add(v)
        ta_candidates = [v for v,c in freq.items() if c in (2,3) and v > eq/unit_divisor*1_000_000 and v<2_000_000_000]
        if ta_candidates:
            results['资产总计'] = round(max(ta_candidates) / unit_divisor, 2)

    # v2.19: Last-resort fallback for D&A
    if (results.get("固定资产折旧", 0) or 0) == 0:
        m = re.search(r"(?:Depreciation of property, plant|物業[、,]?s*廠房及設備折舊)[sS]{0,120}?(d[d,]{5,})", combined, re.DOTALL)
        if m:
            try:
                v = float(m.group(1).replace(",","")) / unit_divisor
                if v < (results.get("营业收入", 0) or 999999) * 0.3:
                    results["固定资产折旧"] = round(v, 2)
            except: pass

    return results


# ---------------------------------------------------------------------------

def write_output(
    contexts: Dict[str, Optional[str]],
    pdf_path: str,
    total_pages: int,
    output_path: str,
) -> dict:
    """Write pdf_sections.json with sections + metadata + structured financial values.

    Returns the output dict for inspection.
    """
    found_count = sum(1 for v in contexts.values() if v is not None)

    # Structured financial value extraction (v2.6 / v2.25 enhanced)
    fin_values = extract_financial_values(contexts)

    # Coverage report (v2.25)
    total_patterns = len(_FIN_PATTERNS)
    extracted_fields = list(fin_values.keys())
    missed_fields = [f for f, _ in _FIN_PATTERNS if f not in fin_values]
    coverage_pct = round(len(extracted_fields) / total_patterns * 100, 1) if total_patterns > 0 else 0

    output = {
        "metadata": {
            "pdf_file": os.path.basename(pdf_path),
            "total_pages": total_pages,
            "extract_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sections_found": found_count,
            "sections_total": len(contexts),
            "financials_coverage": {
                "extracted": len(extracted_fields),
                "total_patterns": total_patterns,
                "coverage_pct": coverage_pct,
                "extracted_fields": sorted(extracted_fields),
                "missed_fields": sorted(missed_fields),
            },
        },
        "financials": fin_values,  # structured key-value pairs in 百万元
    }

    for section_id in ["P2", "P3", "P4", "P6", "P13", "MDA", "SUB", "STMT", "DAN", "SEG"]:
        output[section_id] = contexts.get(section_id)

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output


# ---------------------------------------------------------------------------
# Feature #42: Main pipeline
# ---------------------------------------------------------------------------

def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Extract target sections from annual report PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --pdf 伊利股份_2024_年报.pdf
  %(prog)s --pdf report.pdf --output output/pdf_sections.json --verbose
        """,
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the annual report PDF file",
    )
    parser.add_argument(
        "--output",
        default="output/pdf_sections.json",
        help="Output JSON file path (default: output/pdf_sections.json)",
    )
    parser.add_argument(
        "--hints",
        default=None,
        help="Path to toc_hints.json (optional, from Phase 2A.5 TOC analysis)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress messages during extraction",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print parsed arguments and exit without processing",
    )
    return parser.parse_args(args)


def _load_hints(hints_path: Optional[str]) -> Dict[str, dict]:
    """Load TOC hints from JSON file.

    Args:
        hints_path: Path to toc_hints.json or None.

    Returns:
        Dict mapping section_id -> {"page": int, "title": str} or empty dict.
    """
    if not hints_path or not os.path.exists(hints_path):
        return {}
    try:
        with open(hints_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load hints file '{hints_path}': {e}", file=sys.stderr)
        return {}


def run_pipeline(pdf_path: str, output_path: str, verbose: bool = False,
                 hints_path: Optional[str] = None) -> dict:
    """Run the full extraction pipeline.

    Args:
        pdf_path: Path to the PDF.
        output_path: Path for JSON output.
        verbose: Print progress.
        hints_path: Optional path to toc_hints.json for TOC-based page overrides.

    Returns:
        The output dict written to JSON.

    Raises:
        FileNotFoundError: If PDF not found.
        RuntimeError: If PDF cannot be opened or is too small.
    """
    try:
        from scripts.config import validate_pdf
    except ModuleNotFoundError:
        from config import validate_pdf

    # Validate PDF
    is_valid, reason = validate_pdf(pdf_path)
    if not is_valid:
        raise RuntimeError(f"Invalid PDF: {reason}")

    # Step 1: Extract all pages
    print(f"[1/4] Extracting pages from {pdf_path}...")
    pages_text = extract_all_pages(pdf_path, verbose=verbose)
    total_pages = len(pages_text)

    if total_pages == 0:
        raise RuntimeError("PDF has no extractable pages")

    print(f"  Extracted {total_pages} pages")

    # Load TOC hints (Phase 2A.5)
    hints = _load_hints(hints_path)
    if hints and verbose:
        print(f"  Loaded TOC hints for: {list(hints.keys())}")

    # Step 2: Find section pages via keyword matching
    print("[2/4] Scanning for target sections...")
    section_pages = find_section_pages(pages_text)

    # Apply hints: override keyword-matched pages with TOC hint pages
    for sid, hint in hints.items():
        if sid in section_pages and "page" in hint:
            hint_page = hint["page"]
            if 1 <= hint_page <= total_pages:
                section_pages[sid] = [hint_page]
                if verbose:
                    print(f"  {sid}: overridden by hint → page {hint_page}")

    if verbose:
        for sid, pages in section_pages.items():
            if pages:
                print(f"  {sid}: found on pages {pages[:5]}")
            else:
                print(f"  {sid}: not found")

    # Step 3: Extract context around best matches
    print("[3/4] Extracting section context...")
    page_zones = detect_zones(pages_text)  # v2.33: zone detection for page filtering
    contexts = extract_section_context(pages_text, section_pages, page_zones=page_zones)

    # Step 4: Write output
    print(f"[4/4] Writing output to {output_path}...")
    result = write_output(contexts, pdf_path, total_pages, output_path)

    found = result["metadata"]["sections_found"]
    total = result["metadata"]["sections_total"]
    print(f"Done: {found}/{total} sections found")

    return result


def main():
    args = parse_args()

    if args.dry_run:
        print("=== Dry Run ===")
        print(f"  PDF: {args.pdf}")
        print(f"  Output: {args.output}")
        print(f"  Hints: {args.hints}")
        print(f"  Verbose: {args.verbose}")
        return

    try:
        result = run_pipeline(args.pdf, args.output, verbose=args.verbose,
                              hints_path=args.hints)
        found = result["metadata"]["sections_found"]
        total = result["metadata"]["sections_total"]
        print(f"Extracted {found}/{total} sections -> {args.output}")
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
