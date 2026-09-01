#!/usr/bin/env python3
"""pdf_page_locator.py — Section page-number locator for HK/A-share annual reports.

Identifies which pages contain each target section using TOC parsing + keyword
matching on page headers. Designed to help the V8.3 coordinator (Claude agent)
know exactly which pages to Read for each section.

For HK annual reports, the key challenge is that financial notes (often 60+
pages) contain 8+ distinct Zone B sections. This module scans within the notes
range for numbered note headers and maps them to the correct section_id.

Usage:
    python3 scripts/pdf_page_locator.py --pdf report.pdf
    python3 scripts/pdf_page_locator.py --pdf report.pdf --output page_map.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import pdfplumber

# Reuse section keyword definitions and zone detection from pdf_preprocessor
try:
    from scripts.pdf_preprocessor import (
        SECTION_KEYWORDS,
        SECTION_ZONE_PREFERENCES,
        _score_match,
        detect_zones,
    )
except ImportError:
    from pdf_preprocessor import (  # type: ignore[no-redef]
        SECTION_KEYWORDS,
        SECTION_ZONE_PREFERENCES,
        _score_match,
        detect_zones,
    )

# ── HK financial notes → Zone B section mapping ──────────────────────────────
# Maps note titles (Chinese/English) to section_ids.
# Each mapping is (pattern, section_id) — first match wins.

HK_NOTE_TO_SECTION: List[Tuple[str, str]] = [
    # P2: Restricted assets / 受限资产
    (r"受限制.*(?:現金|存款|資產|现金)", "P2"),
    (r"(?:已抵押|已质押).*資產", "P2"),
    (r"restricted\s+(?:cash|bank|deposit|asset)", "P2"),
    (r"assets?\s+pledged", "P2"),

    # P3: AR aging / 应收账款
    (r"貿易應收款[項項]", "P3"),
    (r"应收账款", "P3"),
    (r"應收賬款", "P3"),
    (r"trade\s+receivable", "P3"),
    (r"應收款項.*賬齡|应收款项.*账龄", "P3"),

    # P4: Related party transactions / 关联方交易
    (r"關聯方交易|關連人士交易|关联方交易", "P4"),
    (r"connected\s+transaction|related\s+party\s+transaction", "P4"),

    # P6: Contingent liabilities / 或有负债
    (r"或有(?:負債|负债|事項|事项)", "P6"),
    (r"contingent\s+liabilit", "P6"),
    (r"(?:未決|未决)訴訟", "P6"),
    (r"承擔.*(?:資本|經營|资本|经营)", "P6"),
    (r"capital\s+commitment", "P6"),

    # P13: Non-recurring items / 非经常性损益
    (r"非經常性損益|非经常性损益", "P13"),
    (r"non[\s-]recurring", "P13"),
    (r"exceptional\s+item", "P13"),

    # DAN: Depreciation & Amortization / 折旧摊销
    (r"物業.*廠房.*設備(?!.*附註)", "DAN"),
    (r"物业.*厂房.*设备", "DAN"),
    (r"depreciation.*property.*plant", "DAN"),
    (r"現金流量表附註|现金流量表附注", "DAN"),
    (r"notes?\s+to\s+(?:the\s+)?cash\s+flow\s+statement", "DAN"),
    (r"綜合現金流量表附註|合并现金流量表附注", "DAN"),
    (r"(?:固定資產|固定资产)折舊|折旧", "DAN"),
    (r"無形資產(?:攤銷|摊销)", "DAN"),
    (r"amorti[sz]ation\s+of\s+intangible", "DAN"),

    # SUB: Subsidiaries / 主要子公司
    (r"主要附屬公司|主要子公司", "SUB"),
    (r"於附屬公司的.*(?:投資|權益|权益)", "SUB"),
    (r"principal\s+subsidiar", "SUB"),
    (r"investment\s+in\s+subsidiar", "SUB"),
    (r"公司及集團資料|公司及集团资料", "SUB"),  # Note 1 usually lists subsidiaries

    # SEG: Segment information / 分部报告
    (r"經營分部|经营分部|分部資料|分部资料|分部信息|分部報告|分部报告", "SEG"),
    (r"operating\s+segment|segment\s+information|segment\s+revenue", "SEG"),
]

# ── TOC section name → section_id mapping ────────────────────────────────────
TOC_SECTION_PATTERNS: List[Tuple[str, str]] = [
    (r"管理[層层]討論與分析", "MDA"),
    (r"Management\s+Discussion\s+(?:and|&)\s+Analysis", "MDA"),
    (r"主席報告|主席报告", "MDA"),
    (r"Chairman'?s?\s+Statement", "MDA"),
    (r"Business\s+Review", "MDA"),
    (r"財務摘要|财务摘要", "MDA"),
    (r"Financial\s+Highlights?", "MDA"),

    (r"企業管治報告|企业管治报告", "GOV"),
    (r"Corporate\s+Governance", "GOV"),
    (r"董事[會会]報告", "GOV"),
    (r"Directors'?\s+Report", "GOV"),

    (r"獨立核數師報告|独立核数师报告", "AUDIT"),
    (r"Independent\s+Auditor'?s?\s+Report", "AUDIT"),

    (r"綜合損益表|合并利润表|综合收益表", "STMT"),
    (r"綜合財務狀況表|合并资产负债表", "STMT"),
    (r"綜合現金流量表|合并现金流量表", "STMT"),
    (r"綜合權益變動表|合并权益变动表", "STMT"),
    (r"Consolidated\s+Statement\s+of", "STMT"),
    (r"Consolidated\s+Income\s+Statement", "STMT"),
    (r"Consolidated\s+Balance\s+Sheet", "STMT"),

    (r"財務報表附註|财务报表附注", "NOTES"),
    (r"Notes\s+to\s+the\s+(?:Consolidated\s+)?Financial\s+Statements", "NOTES"),
]

# Per-section page count estimates (conservative — for when no TOC boundary)
SECTION_PAGE_ESTIMATES: Dict[str, int] = {
    "MDA": 8, "STMT": 8, "GOV": 12, "AUDIT": 5,
    "P2": 3, "P3": 3, "P4": 6, "P6": 3, "P13": 3,
    "DAN": 5, "SUB": 5, "SEG": 3, "NOTES": 50,
}


def _parse_toc_entries(pdf_path: str) -> List[Tuple[int, str]]:
    """Parse the Table of Contents from the first pages.

    HK annual reports typically use a two-column TOC layout:
        "02 公司概覽      40 企業管治報告"
        "04 2025年大事記    57 董事會報告"
    Each line contains TWO entries, each with a page number prefix.

    Returns:
        List of (page_number, section_title) pairs, sorted by page_number.
    """
    toc_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:6]:
                t = page.extract_text() or ""
                toc_text += t + "\n"
    except Exception:
        return []

    if not toc_text:
        return []

    # Clean up: remove header/footer lines, page markers, decorative text
    toc_text = re.sub(r'目\s*錄|目\s*录|TABLE\s+OF\s+CONTENTS', '', toc_text, flags=re.I)
    toc_text = re.sub(r'\b\d{4}\s*年報\b', '', toc_text)  # "二零二五年年報"
    toc_text = re.sub(r'[二三四五六七八九零]{2,}\s*年', '', toc_text)  # Chinese year

    entries: List[Tuple[int, str]] = []

    # Simple approach: find all "number whitespace text" pairs in order.
    # HK TOC format: "02 公司概覽 40 企業管治報告" (two entries per line).
    # Strategy: iterate through all (number, next_text) matches in order.
    matches = list(re.finditer(r'(\d{1,3})\s+', toc_text))
    for i, m in enumerate(matches):
        try:
            page_num = int(m.group(1))
        except ValueError:
            continue
        if not (1 <= page_num <= 500):
            continue

        # Title = text from after this number to the next number match
        title_start = m.end()
        if i + 1 < len(matches):
            title_end = matches[i + 1].start()
        else:
            title_end = len(toc_text)
        title = toc_text[title_start:title_end].strip()

        # Clean title: remove trailing lines, trim to first 60 chars
        title = title.split('\n')[0].strip() if '\n' in title else title
        title = title[:60].strip()

        # Filter noise
        if len(title) < 2:
            continue
        if re.match(r'^[\d\s\.\-/]+$', title):
            continue  # pure numbers/symbols
        if re.match(r'^[一-鿿]{1,2}$', title):
            continue  # single/double CJK char (probably noise)

        entries.append((page_num, title))

    # Deduplicate by page number (keep longest title)
    seen_pages: Dict[int, str] = {}
    for pg, title in sorted(entries, key=lambda x: x[0]):
        pg = int(pg)  # handle "02" → 2
        if 1 <= pg <= 500:
            if pg not in seen_pages or len(title) > len(seen_pages[pg]):
                seen_pages[pg] = title
    return sorted([(pg, title) for pg, title in seen_pages.items()])


def _classify_toc_entry(title: str) -> Optional[str]:
    """Map a TOC section title to a section_id."""
    for pattern, section_id in TOC_SECTION_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return section_id
    return None


def _scan_notes_for_subsections(pdf_path: str, notes_start: int,
                                 notes_end: int) -> Dict[str, List[int]]:
    """Scan financial notes pages for numbered note headers mapped to Zone B sections.

    Returns dict of section_id → [page_numbers].
    """
    results: Dict[str, List[int]] = {}

    # Detect accounting policy zone (Note 2, typically first 15-25 pages of NOTES)
    # Keywords in this zone are POLICY descriptions, not actual data.
    policy_zone_end = notes_start + 15  # default
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for pg in range(notes_start, min(notes_start + 30, notes_end + 1)):
                text = pdf.pages[pg - 1].extract_text() or ""
                # Look for the end of Note 2 (accounting policies)
                if re.search(r'(?:^|\n)\s*3\.\s+', text[:500]):
                    policy_zone_end = pg
                    break
    except Exception:
        pass

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for pg in range(notes_start, notes_end + 1):
                if pg > len(pdf.pages):
                    break
                text = pdf.pages[pg - 1].extract_text() or ""

                # Skip accounting policy zone for data sections
                # (P3/DAN/SEG keywords here are generic, not actual data tables)
                in_policy_zone = (pg <= policy_zone_end)

                # Find all numbered note headers on this page
                # Pattern: "XX. TITLE" where XX is note number
                for m in re.finditer(
                    r'(?:^|\n)\s*(\d{1,2})\.\s+(.{2,80}?)(?:\n|$)',
                    text[:800]
                ):
                    title = m.group(2).strip()
                    # Map note title to section_id
                    for pattern, section_id in HK_NOTE_TO_SECTION:
                        if re.search(pattern, title, re.IGNORECASE):
                            if section_id not in results:
                                results[section_id] = []
                            if pg not in results[section_id]:
                                results[section_id].append(pg)
                            break  # first match per note

                # Also check for section keywords in the full page text
                # (some sections span multiple pages without repeated headers)
                # Skip policy zone for data-heavy sections
                skip_in_policy = {"P3", "DAN", "SEG", "P4", "P6", "P13", "P2"}
                for pattern, section_id in HK_NOTE_TO_SECTION:
                    if in_policy_zone and section_id in skip_in_policy:
                        continue
                    if section_id not in results or pg not in results[section_id]:
                        if re.search(pattern, text[:500], re.IGNORECASE):
                            if section_id not in results:
                                results[section_id] = []
                            if pg not in results[section_id]:
                                results[section_id].append(pg)
    except Exception:
        pass

    return results


def locate_sections(pdf_path: str) -> Dict[str, List[int]]:
    """Locate target sections in a PDF, returning section_id → [page_numbers].

    Strategy:
      1. Parse TOC → get top-level section page ranges
      2. Scan financial notes pages for numbered sub-section headers
      3. Combine and expand page ranges using TOC boundaries

    Args:
        pdf_path: Path to the annual report PDF.

    Returns:
        Dict mapping section_id (str) to list of 1-indexed page numbers.
        Empty list means the section was not found.
    """
    total_pages = 0
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception:
        return {}

    # ── Step 1: Parse TOC ──
    toc_entries = _parse_toc_entries(pdf_path)

    # Build ordered list of (section_id, start_page) from TOC
    toc_sections: List[Tuple[str, int]] = []
    for pg, title in toc_entries:
        section_id = _classify_toc_entry(title)
        if section_id:
            # Avoid duplicates (keep first occurrence = correct start page)
            if not any(s[0] == section_id for s in toc_sections):
                toc_sections.append((section_id, pg))

    # Sort by page number
    toc_sections.sort(key=lambda x: x[1])

    # Build page ranges using TOC boundaries
    # Each section goes from its start_page to (next_section.start_page - 1)
    section_ranges: Dict[str, List[int]] = {}
    for i, (sid, start_pg) in enumerate(toc_sections):
        if i + 1 < len(toc_sections):
            next_pg = toc_sections[i + 1][1]
            end_pg = min(next_pg, total_pages + 1)
        else:
            end_pg = total_pages + 1
        section_ranges[sid] = list(range(start_pg, end_pg))

    # ── Step 2: Scan financial notes for sub-sections ──
    notes_range = section_ranges.get("NOTES", [])
    if notes_range:
        notes_start = min(notes_range)
        notes_end = max(notes_range)
        sub_sections = _scan_notes_for_subsections(
            pdf_path, notes_start, notes_end
        )

        # Expand sub-section pages (each hit covers ~2 pages)
        for sid, pages in sub_sections.items():
            expanded = set()
            for pg in pages:
                for offset in range(-1, 3):  # -1 before, +2 after
                    if notes_start <= pg + offset <= notes_end:
                        expanded.add(pg + offset)
            section_ranges[sid] = sorted(expanded)

    # ── Step 3: Keyword matching fallback for sections not found ──
    all_keywords = dict(SECTION_KEYWORDS)
    missing = [s for s in ["MDA", "SEG", "P2", "P3", "P4", "P6", "P13", "DAN", "SUB"]
                if s not in section_ranges or not section_ranges.get(s)]

    if missing:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_zones: Dict[int, str] = {}
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    for pattern, zone_name in [  # minimal zone detection
                        (r"管理[層层]討論與分析", "MDA_ZONE"),
                        (r"財務報表附註", "NOTES_ZONE"),
                        (r"企業管治報告", "GOVERNANCE_ZONE"),
                        (r"獨立核數師報告", "AUDIT_ZONE"),
                    ]:
                        if re.search(pattern, text[:300]):
                            page_zones[i + 1] = zone_name
                            break

                for section_id in missing:
                    keywords = all_keywords.get(section_id, [])
                    if not keywords:
                        continue
                    found_pages = []
                    for i, page in enumerate(pdf.pages[:total_pages]):
                        text = page.extract_text() or ""
                        head = text[:500]
                        for kw in keywords:
                            if kw in head:
                                found_pages.append(i + 1)
                                break
                    if found_pages:
                        section_ranges[section_id] = found_pages
        except Exception:
            pass

    # ── Step 4: For sections still empty, apply page estimates from first hit ──
    for sid in list(section_ranges.keys()):
        pages = section_ranges.get(sid, [])
        if pages and len(pages) == 1:
            # Single page hit → expand using estimate
            estimate = SECTION_PAGE_ESTIMATES.get(sid, 3)
            start = max(1, pages[0])
            end = min(total_pages + 1, start + estimate)
            section_ranges[sid] = list(range(start, end))

    return section_ranges, total_pages


def main():
    p = argparse.ArgumentParser(
        description="Locate target section page numbers in annual report PDFs"
    )
    p.add_argument("--pdf", required=True, help="Path to annual report PDF")
    p.add_argument("--output", help="Output JSON file path (default: stdout)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Print page ranges for each section")
    p.add_argument("--export-chapters", action="store_true",
                   help="Export PDF chapter fragments based on page_map (P3: automation)")
    p.add_argument("--export-dir", help="Directory for exported chapter PDFs")
    args = p.parse_args()

    page_map, total_pages = locate_sections(args.pdf)

    # ── Summary ──
    total = len(page_map)
    found = sum(1 for v in page_map.values() if v)
    if args.verbose:
        print(f"Sections located: {found}/{total}", file=sys.stderr)
        section_order = ["MDA", "SEG", "STMT", "GOV", "AUDIT",
                          "P2", "P3", "P4", "P6", "P13", "DAN", "SUB", "NOTES"]
        for sid in section_order:
            pages = page_map.get(sid, [])
            if pages:
                print(f"  {sid:5s}: pages {pages[0]}-{pages[-1]} ({len(pages)} pages)",
                      file=sys.stderr)
            elif sid in page_map:
                print(f"  {sid:5s}: NOT FOUND", file=sys.stderr)

    output = {
        "pdf_file": os.path.basename(args.pdf),
        "sections": page_map,
    }

    # ── P3: Export chapter fragments ──
    if args.export_chapters:
        export_dir = args.export_dir or os.path.join(
            os.path.dirname(args.output) if args.output else ".", "chapters"
        )
        os.makedirs(export_dir, exist_ok=True)

        try:
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            try:
                from pypdf import PdfReader, PdfWriter
            except ImportError:
                print("⚠️ PyPDF2/pypdf not installed — skipping chapter export",
                      file=sys.stderr)
                args.export_chapters = False

    if args.export_chapters and page_map:
        section_order = ["MDA", "SEG", "STMT", "GOV", "AUDIT",
                          "P2", "P3", "P4", "P6", "P13", "DAN", "SUB"]
        for sid in section_order:
            pages = page_map.get(sid, [])
            if not pages:
                continue
            # ±1 page buffer to handle TOC offset
            start = max(1, min(pages) - 1)
            end = min(total_pages, max(pages) + 1)
            try:
                reader = PdfReader(args.pdf)
                writer = PdfWriter()
                for pg in range(start - 1, end):
                    if pg < len(reader.pages):
                        writer.add_page(reader.pages[pg])
                out_path = os.path.join(export_dir, f"chapter_{sid}.pdf")
                with open(out_path, "wb") as f:
                    writer.write(f)
                print(f"  📄 {sid}: pages {start}-{end} → {out_path} "
                      f"({end - start + 1}p)", file=sys.stderr)
            except Exception as e:
                print(f"  ⚠️ {sid} export failed: {e}", file=sys.stderr)
        print(f"→ {export_dir}/", file=sys.stderr)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"→ {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
