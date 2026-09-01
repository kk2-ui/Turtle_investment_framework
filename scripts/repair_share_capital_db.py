#!/usr/bin/env python3
"""Repair share-capital / base-share / shares_m from authoritative raw workbooks.

Authoritative sources:
- cn_financials_panel_raw/上市公司-财务报表年度面板数据.xlsx (A shares)
- hk_new_financials/HK上市披露指标/HK_STK_DiscloseIndex.xlsx (HK shares)
- A-share annual report PDFs under output/<code>_<name>/<code>_<year>_年报.pdf (override for anomalies)

Rules:
- A shares: read CSMAR raw `实收资本(或股本)` and normalize it to million shares.
  The workbook is not perfectly uniform, so use a magnitude heuristic:
    - raw > 100000 → treat as thousand shares and divide by 1000
    - otherwise → treat as already in million shares
- HK shares: raw `IssueCapPE` is annual issued share count in shares; convert to million shares via /1_000_000.
- A-share annual reports, when they contain an explicit year-end share count, override CSMAR for that stock-year.
  This catches stale or year-shifted CSMAR rows like 002027.SZ / 600295.SH.

The script is idempotent and can be re-run.
"""

from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sqlite3
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from typing import DefaultDict, Dict, List, Optional, Tuple

from config import (
    get_csmar_a_xlsx,
    get_db_path,
    get_hk_new_financials_dir,
    get_output_dir,
)


ROOT = os.path.dirname(os.path.dirname(__file__))

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
A_REPORT_PATTERNS = [
    r"以\s*([\d,]{8,})\s*股为基数",
    r"截至报告期末(?:公司)?总股本\s*[为：:]?\s*([\d,]{8,})\s*股",
    r"累计发行股本总数\s*([\d,]{8,})\s*股",
    r"注册资本为\s*([\d,]{8,}(?:\.\d+)?)\s*元",
]


def _shared_strings(z: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out: List[str] = []
    for si in root.findall(f"{NS}si"):
        texts = [t.text or "" for t in si.iterfind(f".//{NS}t")]
        out.append("".join(texts))
    return out


def _sheet_target(z: zipfile.ZipFile, sheet_index: int = 0) -> str:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall(f"{REL_NS}Relationship")}
    sheets = wb.findall(f"{NS}sheets/{NS}sheet")
    rid = sheets[sheet_index].attrib[OFFICE_REL]
    return "xl/" + relmap[rid]


def _cell_value(cell: ET.Element, shared_strings: List[str]) -> str:
    t = cell.attrib.get("t")
    if t == "inlineStr":
        isel = cell.find(f"{NS}is")
        if isel is None:
            return ""
        return "".join(tn.text or "" for tn in isel.iterfind(f".//{NS}t"))
    v = cell.find(f"{NS}v")
    if v is None or v.text is None:
        return ""
    if t == "s":
        idx = int(v.text)
        return shared_strings[idx] if idx < len(shared_strings) else ""
    return v.text


def _forward_fill(pairs: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
    out: List[Tuple[int, float]] = []
    last: Optional[float] = None
    for year, val in sorted(pairs):
        if val and val > 0:
            last = val
        if last is not None:
            out.append((year, last))
    return out


def _normalize_a_share(raw: float) -> float:
    return raw / 1000.0 if raw > 100000 else raw


def _read_a_shares(path: str) -> Dict[str, List[Tuple[int, float]]]:
    by_code: DefaultDict[str, List[Tuple[int, float]]] = collections.defaultdict(list)
    with zipfile.ZipFile(path) as z:
        shared_strings = _shared_strings(z)
        target = _sheet_target(z, sheet_index=0)
        root = ET.fromstring(z.read(target))
        rows = root.findall(f".//{NS}sheetData/{NS}row")
        for row in rows[1:]:
            cells = row.findall(f"{NS}c")
            if len(cells) <= 145:
                continue
            code = _cell_value(cells[0], shared_strings).strip()
            year_raw = _cell_value(cells[1], shared_strings).strip()
            if not code or not year_raw:
                continue
            try:
                year = int(float(year_raw))
                raw = float(_cell_value(cells[145], shared_strings) or 0)
            except ValueError:
                continue
            if raw <= 0:
                continue
            ts_code = f"{str(int(float(code))).zfill(6)}.SH" if code.startswith(("6", "68")) else f"{str(int(float(code))).zfill(6)}.SZ"
            by_code[ts_code].append((year, _normalize_a_share(raw)))
    return by_code


def _read_hk_shares(path: str) -> Dict[str, List[Tuple[int, float]]]:
    by_code: DefaultDict[str, List[Tuple[int, float]]] = collections.defaultdict(list)
    with zipfile.ZipFile(path) as z:
        shared_strings = _shared_strings(z)
        target = _sheet_target(z, sheet_index=0)
        root = ET.fromstring(z.read(target))
        rows = root.findall(f".//{NS}sheetData/{NS}row")
        for row in rows[2:]:
            cells = row.findall(f"{NS}c")
            if len(cells) <= 10:
                continue
            code = _cell_value(cells[0], shared_strings).strip()
            end_date = _cell_value(cells[1], shared_strings).strip()
            if not code or len(end_date) < 8 or not code.isdigit():
                continue
            try:
                year = int(end_date[:4])
                month = int(end_date[5:7])
                raw = float(_cell_value(cells[10], shared_strings) or 0)
            except ValueError:
                continue
            if month != 12 or raw <= 0:
                continue
            by_code[f"{code.zfill(5)}.HK"].append((year, raw / 1_000_000.0))
    return by_code


def _extract_report_share_count_m(pdf_path: str) -> Optional[float]:
    txt_path = "/tmp/claude_share_audit.txt"
    try:
        subprocess.run(["pdftotext", pdf_path, txt_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        text = open(txt_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        return None

    candidates: List[int] = []
    for pat in A_REPORT_PATTERNS:
        for m in re.finditer(pat, text):
            try:
                candidates.append(int(m.group(1).replace(",", "")))
            except Exception:
                continue
    if not candidates:
        return None
    # Prefer the last explicit year-end style count from the report.
    shares = candidates[-1]
    if shares < 1_000_000:
        return None
    return shares / 1_000_000.0


def _read_a_report_shares(output_dir: str) -> Dict[str, List[Tuple[int, float]]]:
    by_code: DefaultDict[str, List[Tuple[int, float]]] = collections.defaultdict(list)
    for pdf_path in glob.glob(os.path.join(output_dir, "*_*", "*_年报.pdf")):
        base = os.path.basename(pdf_path)
        m = re.match(r"(\d{6})_(\d{4})_年报\.pdf$", base)
        if not m:
            continue
        code, year = m.group(1), int(m.group(2))
        ts_code = f"{code}.SH" if code.startswith(("6", "68")) else f"{code}.SZ"
        shares_m = _extract_report_share_count_m(pdf_path)
        if shares_m and shares_m > 0:
            by_code[ts_code].append((year, shares_m))
    return by_code


def _merge_a_sources(
    csmar_data: Dict[str, List[Tuple[int, float]]],
    report_data: Dict[str, List[Tuple[int, float]]],
) -> Dict[str, List[Tuple[int, float, str]]]:
    merged: Dict[str, List[Tuple[int, float, str]]] = {}
    codes = set(csmar_data) | set(report_data)
    for code in codes:
        csmar_map = {year: val for year, val in csmar_data.get(code, [])}
        report_map = {year: val for year, val in report_data.get(code, [])}
        years = sorted(set(csmar_map) | set(report_map))
        rows: List[Tuple[int, float, str]] = []
        last_report: Optional[float] = None
        for year in years:
            if year in report_map:
                val = report_map[year]
                source = "annual_report"
                last_report = val
            elif year in csmar_map:
                val = csmar_map[year]
                source = "csmar"
                # If adjacent year has an explicit report count and differs materially, keep csmar for now.
                # The audit output will surface it; auto-overrides only happen when report data exists for same year.
            elif last_report is not None:
                val = last_report
                source = "report_carry"
            else:
                continue
            rows.append((year, val, source))
        merged[code] = rows
    return merged


def repair_a(
    db: sqlite3.Connection,
    source: str,
    output_dir: str,
    dry_run: bool = False,
    print_audit: bool = False,
) -> int:
    csmar_data = _read_a_shares(source)
    report_data = _read_a_report_shares(output_dir)
    merged = _merge_a_sources(csmar_data, report_data)
    total = 0
    audit_rows: List[str] = []
    for ts_code, rows in merged.items():
        for year, shares_m, src in rows:
            csmar_val = next((v for y, v in csmar_data.get(ts_code, []) if y == year), None)
            report_val = next((v for y, v in report_data.get(ts_code, []) if y == year), None)
            if print_audit and report_val and csmar_val:
                ratio = max(report_val, csmar_val) / max(1e-9, min(report_val, csmar_val))
                if ratio >= 1.2:
                    audit_rows.append(
                        f"{ts_code} FY{year}: report={report_val:.6f}M vs csmar={csmar_val:.6f}M ({ratio:.1f}x)"
                    )
            if dry_run:
                continue
            db.execute(
                """
                INSERT INTO annual_financials (ts_code, fiscal_year, report_type, share_capital, base_share)
                VALUES (?, ?, 'annual', ?, ?)
                ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET
                    share_capital=excluded.share_capital,
                    base_share=excluded.base_share
                """,
                (ts_code, year, round(shares_m, 6), round(shares_m, 6)),
            )
            total += 1
    if print_audit and audit_rows:
        print("A-share report-vs-CSMAR anomalies:")
        for line in sorted(audit_rows)[:50]:
            print("  ", line)
    if not dry_run:
        db.execute(
            """
            UPDATE stocks
            SET shares_m = (
                SELECT af.base_share
                FROM annual_financials af
                WHERE af.ts_code = stocks.ts_code
                  AND af.report_type = 'annual'
                  AND af.base_share IS NOT NULL
                  AND af.base_share > 0
                ORDER BY af.fiscal_year DESC
                LIMIT 1
            ),
            updated_at = datetime('now','localtime')
            WHERE ts_code LIKE '%.SZ' OR ts_code LIKE '%.SH'
            """
        )
    return total


def repair_hk(db: sqlite3.Connection, source: str, dry_run: bool = False) -> int:
    data = _read_hk_shares(source)
    total = 0
    for ts_code, pairs in data.items():
        for year, shares_m in _forward_fill(pairs):
            if dry_run:
                continue
            db.execute(
                """
                INSERT INTO annual_financials (ts_code, fiscal_year, report_type, base_share)
                VALUES (?, ?, 'annual', ?)
                ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET
                    base_share=excluded.base_share
                """,
                (ts_code, year, round(shares_m, 6)),
            )
            total += 1
    if not dry_run:
        db.execute(
            """
            UPDATE stocks
            SET shares_m = (
                SELECT af.base_share
                FROM annual_financials af
                WHERE af.ts_code = stocks.ts_code
                  AND af.report_type = 'annual'
                  AND af.base_share IS NOT NULL
                  AND af.base_share > 0
                ORDER BY af.fiscal_year DESC
                LIMIT 1
            ),
            updated_at = datetime('now','localtime')
            WHERE ts_code LIKE '%.HK'
            """
        )
    return total


def sanity_report(db: sqlite3.Connection, code: str) -> None:
    row = db.execute("SELECT shares_m FROM stocks WHERE ts_code=?", (code,)).fetchone()
    if row:
        print(f"stocks {code}: shares_m={row['shares_m']}")
    for r in db.execute(
        "SELECT fiscal_year, share_capital, base_share FROM annual_financials WHERE ts_code=? AND report_type='annual' ORDER BY fiscal_year DESC LIMIT 5",
        (code,),
    ).fetchall():
        print(dict(r))


def main() -> int:
    default_db = get_db_path()
    default_output_dir = get_output_dir()
    default_a_xlsx = get_csmar_a_xlsx()
    default_hk_xlsx = os.path.join(get_hk_new_financials_dir(), "HK上市披露指标", "HK_STK_DiscloseIndex.xlsx")

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--print-audit", action="store_true")
    ap.add_argument("--a-xlsx", default=default_a_xlsx)
    ap.add_argument("--hk-xlsx", default=default_hk_xlsx)
    ap.add_argument("--db", default=default_db)
    ap.add_argument("--output-dir", default=default_output_dir)
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    try:
        print("Repairing A-share share capital...")
        a_rows = repair_a(db, args.a_xlsx, args.output_dir, dry_run=args.dry_run, print_audit=args.print_audit)
        print(f"  updated annual rows: {a_rows}")
        print("Repairing HK share capital...")
        hk_rows = repair_hk(db, args.hk_xlsx, dry_run=args.dry_run)
        print(f"  updated annual rows: {hk_rows}")
        if not args.dry_run:
            db.commit()
            print("\nSanity checks:")
            for code in ["002027.SZ", "000651.SZ", "600295.SH", "600690.SH", "00506.HK"]:
                sanity_report(db, code)
        else:
            db.rollback()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
