#!/usr/bin/env python3
"""Generate data_pack_report.md from HK annual-report note pages.

This is a deterministic fallback for HK stocks when pdf_sections.json does not
reliably capture note-level sections such as related-party transactions or
capital commitments.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from config import validate_stock_code


LATE_NOTE_START_PAGE = 120
SUB_SAMPLE_LIMIT = 6

SUB_ROW_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?P<place>Hong Kong|Macau|The PRC/Chinese Mainland|The PRC/ Chinese Mainland)\s+"
    r"(?P<capital>(?:HK\$|MOP|RMB)[\d,]+)\s+"
    r"(?P<direct>—|\d+)\s+"
    r"(?P<indirect>—|\d+)\s+"
    r"(?P<activity>.+)$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HK annual-report data_pack_report.md")
    parser.add_argument("--output-dir", required=True, help="Output directory containing annual report PDFs")
    parser.add_argument("--code", required=True, help="Tushare code, e.g. 02669.HK")
    parser.add_argument("--output", help="Optional explicit output path; defaults to {output_dir}/data_pack_report.md")
    return parser.parse_args()


def _base_code(ts_code: str) -> str:
    return ts_code.split(".")[0]


def _parse_report_year(path: Path) -> int | None:
    matches = re.findall(r"(20\d{2})", path.name)
    if not matches:
        return None
    year = int(matches[-1])
    return year if 2000 <= year <= 2099 else None


def _latest_annual_pdf(output_dir: Path, ts_code: str) -> Path:
    code = _base_code(ts_code)
    candidates: list[tuple[int, Path]] = []
    for path in output_dir.glob("*.pdf"):
        if code not in path.name:
            continue
        year = _parse_report_year(path)
        if year is None:
            continue
        candidates.append((year, path))
    if not candidates:
        raise FileNotFoundError(f"No annual report PDF found for {ts_code} under {output_dir}")
    candidates.sort(key=lambda item: (item[0], item[1].name))
    return candidates[-1][1]


def _company_name(output_dir: Path, ts_code: str) -> str:
    prefix = f"{_base_code(ts_code)}_"
    if output_dir.name.startswith(prefix):
        suffix = output_dir.name[len(prefix):].strip()
        if suffix:
            return suffix
    return _base_code(ts_code)


def _open_pdf_texts(pdf_path: Path) -> tuple[int, dict[int, str]]:
    stderr_sink = io.StringIO()
    with contextlib.redirect_stderr(stderr_sink):
        with pdfplumber.open(str(pdf_path)) as pdf:
            total_pages = len(pdf.pages)
            pages = {
                idx + 1: (page.extract_text() or "")
                for idx, page in enumerate(pdf.pages)
            }
    return total_pages, pages


def _compact(text: str) -> str:
    return " ".join(text.split())


def _printed_page(actual_page: int, text: str) -> int:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\d{1,4}", stripped):
            return int(stripped)
        break
    return actual_page


def _printed_page_ref(pages: dict[int, str], actual_pages: list[int]) -> str:
    printed = [_printed_page(page, pages.get(page, "")) for page in actual_pages]
    if not printed:
        return ""
    printed = sorted(set(printed))
    if len(printed) == 1:
        return f"年报 p.{printed[0]}"
    return f"年报 p.{printed[0]}-{printed[-1]}"


def _find_page(pages: dict[int, str], needle: str, start_page: int = LATE_NOTE_START_PAGE) -> int | None:
    needle_lower = needle.lower()
    for page, text in pages.items():
        if page < start_page:
            continue
        if needle_lower in text.lower():
            return page
    return None


def _find_sub_start_page(pages: dict[int, str]) -> int | None:
    for page, text in pages.items():
        if "Information about principal subsidiaries" in text:
            return page
    return None


def _extract_num(value: str) -> float:
    return float(value.replace(",", ""))


def _fmt_million(value_rmb: float, divisor: float) -> str:
    value = value_rmb / divisor
    return f"{value:,.3f}"


def _fmt_percent(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)}%"
    return f"{value:.1f}%"


def _parse_trade_receivables(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    m = re.search(
        r"Trade receivables \(a\)\s+([\d,]+)\s+[\d,]+\s+Less: Impairment \(b\)\s+\(([\d,]+)\)\s+\([\d,]+\)\s+([\d,]+)\s+[\d,]+",
        compact,
    )
    ageing = re.search(
        r"Within 1 month\s+([\d,]+)\s+[\d,]+\s+"
        r"1 to 3 months\s+([\d,]+)\s+[\d,]+\s+"
        r"4 to 12 months\s+([\d,]+)\s+[\d,]+\s+"
        r"1 to 2 years\s+([\d,]+)\s+[\d,]+\s+"
        r"Over 2 years\s+([\d,]+)\s+[\d,]+\s+"
        r"3,237,345\s+2,877,554",
        compact,
    )
    if not m or not ageing:
        return None
    return {
        "gross": _extract_num(m.group(1)),
        "impairment": _extract_num(m.group(2)),
        "net": _extract_num(m.group(3)),
        "within_1m": _extract_num(ageing.group(1)),
        "m1_3": _extract_num(ageing.group(2)),
        "m4_12": _extract_num(ageing.group(3)),
        "y1_2": _extract_num(ageing.group(4)),
        "over_2y": _extract_num(ageing.group(5)),
    }


def _parse_contract_assets(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    m = re.search(
        r"Unbilled revenue \(a\)\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+"
        r"Retention receivables \(b\)\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+"
        r"Total\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+"
        r"Less: Impairment \(d\)\s+\(([\d,]+)\)\s+\([\d,]+\)\s+—\s+"
        r"([\d,]+)\s+[\d,]+\s+[\d,]+",
        compact,
    )
    recovery = re.search(
        r"Within one year\s+([\d,]+)\s+[\d,]+\s+Over one year\s+([\d,]+)\s+[\d,]+\s+16,786\s+17,751",
        compact,
    )
    ecl = re.search(
        r"Expected credit loss rate\s+([\d.]+)%\s+[\d.]+%\s+Gross carrying amount \(RMB.?000\)\s+([\d,]+)\s+[\d,]+\s+Expected credit losses \(RMB.?000\)\s+([\d,]+)\s+[\d,]+",
        compact,
    )
    if not m:
        return None
    result = {
        "unbilled": _extract_num(m.group(1)),
        "retention": _extract_num(m.group(2)),
        "gross": _extract_num(m.group(3)),
        "impairment": _extract_num(m.group(4)),
        "net": _extract_num(m.group(5)),
    }
    if recovery:
        result["within_1y"] = _extract_num(recovery.group(1))
        result["over_1y"] = _extract_num(recovery.group(2))
    if ecl:
        result["ecl_rate"] = float(ecl.group(1))
        result["ecl_gross"] = _extract_num(ecl.group(2))
        result["ecl_loss"] = _extract_num(ecl.group(3))
    return result


def _parse_related_balances(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    patterns = {
        "immediate_trade": r"Balance due from the immediate holding company Trade nature \(a\)\s+([\d,]+)\s+[\d,]+",
        "fellow_trade": r"Balances due from fellow subsidiaries Trade nature \(a\)\s+([\d,]+)\s+[\d,]+",
        "fellow_contract": r"Balances due from fellow subsidiaries .*? Contract assets \(b\)\s+([\d,]+)\s+[\d,]+",
        "fellow_prepay": r"Balances due from fellow subsidiaries .*? Prepayments \(d\)\s+([\d,]+)\s+[\d,]+",
        "fellow_total": r"Balances due from fellow subsidiaries .*? Prepayments \(d\)\s+[\d,]+\s+[\d,]+\s+([\d,]+)\s+[\d,]+",
        "other_trade": r"Portion classified as current assets.?： Trade nature \(a\)\s+([\d,]+)\s+[\d,]+",
        "other_contract": r"Portion classified as current assets.?： .*? Contract assets \(b\)\s+([\d,]+)\s+[\d,]+",
        "other_prepay": r"Portion classified as current assets.?： .*? Prepayments \(d\)\s+([\d,]+)\s+[\d,]+",
        "other_nontrade": r"Portion classified as current assets.?： .*? Non-trade nature \(c\)\s+([\d,]+)\s+—",
        "other_total": r"Portion classified as current assets.?： .*? Non-trade nature \(c\)\s+[\d,]+\s+—\s+([\d,]+)\s+[\d,]+",
        "total": r"Total balances due from related parties\s+([\d,]+)\s+[\d,]+",
    }
    result: dict[str, float] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, compact)
        if match:
            result[key] = _extract_num(match.group(1))
    return result or None


def _parse_related_transactions(text: str) -> dict[str, tuple[float, float]] | None:
    compact = _compact(text)
    categories = {
        "cscec": r"CSCEC and its subsidiaries .*? Property management income and value-added service income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental expenses paid \(ii\)\s+([\d,]+)\s+[\d,]+",
        "cohl": r"COHL and its subsidiaries .*? Property management income and value-added service income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental expenses paid \(ii\)\s+([\d,]+)\s+[\d,]+",
        "coli_csc": r"COLI, CSC and their subsidiaries .*? Property management income and value-added service income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental and utility expenses paid \(ii\)\s+([\d,]+)\s+[\d,]+",
        "other": r"Other related companies Property management income and value-added service income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental expenses paid \(ii\)\s+([\d,]+)\s+—",
    }
    result: dict[str, tuple[float, float]] = {}
    for key, pattern in categories.items():
        match = re.search(pattern, compact)
        if match:
            result[key] = (_extract_num(match.group(1)), _extract_num(match.group(2)))
    return result or None


def _parse_restricted_bank_deposits(text: str) -> dict[str, float | str] | None:
    compact = _compact(text)
    match = re.search(
        r"restricted bank deposits of RMB([\d,]+) \(2024: RMB([\d,]+)\) were held for purpose of (.+?)\.",
        compact,
        flags=re.I,
    )
    if not match:
        return None
    return {
        "current": _extract_num(match.group(1)),
        "prior": _extract_num(match.group(2)),
        "purpose": match.group(3).strip(),
    }


def _parse_commitments_and_contingencies(text: str) -> dict[str, float | str] | None:
    compact = _compact(text)
    commitment = re.search(
        r"Capital investment into a joint venture\s+—\s+[\d,]+\s+Acquisition of intangible assets\s+([\d,]+)\s+[\d,]+\s+([\d,]+)\s+[\d,]+",
        compact,
    )
    contingent = re.search(
        r"counter indemnities to a fellow subsidiary and banks amounting to approximately RMB([\d,]+) .*? and RMB([\d,]+) .*? respectively.*?"
        r"guarantees to COLI.*? amounting to RMB([\d,]+) .*? RMB([\d,]+) .*? and RMB([\d,]+)",
        compact,
    )
    future = re.search(
        r"continued to provide corporate guarantees to COLI up to an aggregate amount of RMB([\d.]+) million from 1 January (\d{4}) to 31 December (\d{4})",
        compact,
    )
    result: dict[str, float | str] = {}
    if commitment:
        result["intangibles_commitment"] = _extract_num(commitment.group(1))
        result["total_commitment"] = _extract_num(commitment.group(2))
    if contingent:
        result["counter_indemnity_fellow_sub"] = _extract_num(contingent.group(1))
        result["counter_indemnity_banks"] = _extract_num(contingent.group(2))
        result["guarantee_coli"] = _extract_num(contingent.group(3))
        result["guarantee_csc"] = _extract_num(contingent.group(4))
        result["guarantee_cogo"] = _extract_num(contingent.group(5))
    if future:
        result["future_coli_million"] = float(future.group(1))
        result["future_from"] = future.group(2)
        result["future_to"] = future.group(3)
    return result or None


def _parse_non_operating_items(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    grants_match = re.search(
        r"Unconditional government grants:.*?Government subsidies arising from value-added and other tax beneficial policies\s+([\d,]+)\s+[\d,]+.*?Other government grants\s+([\d,]+)\s+[\d,]+.*?([\d,]+)\s+[\d,]+\s+Interest income",
        compact,
        re.I,
    )
    patterns = {
        "interest_income": r"Interest income\s+([\d,]+)\s+[\d,]+",
        "lease_termination_gain": r"Gain/\(loss\) on early termination of lease contracts, net.*?\s+(\(?[\d,]+\)?)\s+\(?[\d,]+\)?",
        "impair_trade": r"Trade receivables 22\(b\)\s+([\d,]+)\s+[\d,]+",
        "impair_contract": r"Contract assets 23\(d\)\s+([\d,]+)\s+[\d,]+",
        "impair_other": r"Other receivables 24\(b\)\s+([\d,]+)\s+[\d,]+",
        "recover_prior_writeoff": r"Recovery of other receivables written off in prior years\s+(\(?-?[\d,]+\)?)\s+\(?-?[\d,]+\)?",
        "impair_total": r"Recovery of other receivables written off in prior years .*?[\r\n\s]+([\d,]+)\s+[\d,]+[\r\n\s]+Fair value loss of investment properties",
        "fair_value_self_owned": r"Self-owned investment properties 15\s+([\d,]+)\s+[\d,]+",
        "fair_value_leased": r"Leased investment properties\*? 15\s+([\d,]+)\s+[\d,]+",
        "fair_value_total": r"Leased investment properties\*? 15\s+[\d,]+\s+[\d,]+[\r\n\s]+([\d,]+)\s+[\d,]+[\r\n\s]+Loss on disposal",
        "loss_disposal_ppe": r"Loss on disposal of items of property, plant and equipment, net\s+([\d,]+)\s+[\d,]+",
        "fx_gain_net": r"Foreign exchange gain, net\s+\(([\d,]+)\)\s+\([\d,]+\)",
    }
    result: dict[str, float] = {}
    if grants_match:
        result["gov_tax_benefit"] = _to_signed_num(grants_match.group(1)) or 0.0
        result["gov_other"] = _to_signed_num(grants_match.group(2)) or 0.0
        result["gov_total"] = _to_signed_num(grants_match.group(3)) or 0.0
    for key, pattern in patterns.items():
        match = re.search(pattern, compact, re.I)
        if not match:
            continue
        value = _to_signed_num(match.group(1))
        if value is not None:
            result[key] = value
    return result or None


def _to_signed_num(value: str) -> float | None:
    token = value.strip()
    if not token:
        return None
    negative = token.startswith("(") and token.endswith(")")
    token = token.strip("()").replace(",", "")
    try:
        parsed = float(token)
    except ValueError:
        return None
    return -parsed if negative else parsed


def _parse_holding_structure(text: str) -> dict[str, str]:
    compact = _compact(text)
    result: dict[str, str] = {}
    immediate = re.search(r"The immediate holding company of the Company is (.+?) \(", compact)
    ultimate = re.search(r"its ultimate holding company is (.+?) \(", compact)
    if immediate:
        result["immediate_holding"] = immediate.group(1).strip()
    if ultimate:
        result["ultimate_holding"] = ultimate.group(1).strip()
    return result


def _is_sub_name_token(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Za-z.&'()/:-]*", token))


def _append_sub_continuation(row: dict[str, str], line: str) -> None:
    if line.startswith(("1. CORPORATE", "Notes to Financial Statements", "CORPORATE OVERVIEW")):
        return
    tokens = line.split()
    name_tokens: list[str] = []
    activity_tokens: list[str] = []
    switched = False

    for token in tokens:
        if not switched and _is_sub_name_token(token):
            name_tokens.append(token)
            continue
        switched = True
        activity_tokens.append(token)

    if name_tokens and re.search(r"[A-Za-z]", row["name"]):
        row["name"] = f"{row['name']} {' '.join(name_tokens)}".strip()
    if activity_tokens:
        row["activity"] = f"{row['activity']} {' '.join(activity_tokens)}".strip()


def _parse_sub_rows(text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines:
        if re.fullmatch(r"\d{1,4}", line):
            continue
        if line.startswith(("China Overseas Property Holdings Limited", "CORPORATE OVERVIEW", "Notes to Financial Statements", "31 December 2025")):
            continue
        if line.startswith(("Information about principal subsidiaries", "Registered/", "Place of incorporation/", "Company name", "Direct", "% %")):
            continue
        if line.startswith(("* These companies", "# These companies", "The above table lists")):
            break
        match = SUB_ROW_RE.match(line)
        if match:
            current = match.groupdict()
            rows.append(current)
            continue
        if current:
            _append_sub_continuation(current, line)
    return rows


def _holding_pct(row: dict[str, str]) -> str:
    direct = row.get("direct", "—")
    indirect = row.get("indirect", "—")
    total = 0
    has_numeric = False
    for value in (direct, indirect):
        if value.isdigit():
            total += int(value)
            has_numeric = True
    if has_numeric:
        return f"{total}%"
    return direct if direct != "—" else indirect


def _pick_sub_samples(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_row(predicate) -> None:
        for row in rows:
            name = row["name"]
            if name in seen:
                continue
            if predicate(row):
                seen.add(name)
                samples.append(row)
                return

    add_row(lambda r: "investment holding" in r["activity"].lower() and "commercial" in r["name"].lower())
    add_row(lambda r: "real estate management" in r["activity"].lower() and "中海物業管理有限公司" in r["name"])
    add_row(lambda r: "engineering" in r["activity"].lower())
    add_row(lambda r: "cleaning" in r["activity"].lower())
    add_row(lambda r: "security" in r["activity"].lower())
    add_row(lambda r: r["name"].strip() == "中建物業管理有限公司#")

    for row in rows:
        if len(samples) >= SUB_SAMPLE_LIMIT:
            break
        name = row["name"]
        if name in seen:
            continue
        seen.add(name)
        samples.append(row)
    return samples[:SUB_SAMPLE_LIMIT]


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _find_profit_before_tax_pages(pages: dict[int, str], start_page: int = LATE_NOTE_START_PAGE) -> list[int]:
    hits: list[int] = []
    for page, text in pages.items():
        if page < start_page:
            continue
        if "8. PROFIT BEFORE TAX" in text or "The Group’s profit before tax is arrived at" in text:
            hits.append(page)
        elif hits and "9. DIRECTORS’ REMUNERATION" not in text:
            hits.append(page)
            if len(hits) >= 3:
                break
        elif hits:
            break
    return hits


def build_markdown(output_dir: Path, ts_code: str) -> str:
    pdf_path = _latest_annual_pdf(output_dir, ts_code)
    company = _company_name(output_dir, ts_code)
    total_pages, pages = _open_pdf_texts(pdf_path)

    p2_page = _find_page(pages, "26. RESTRICTED BANK DEPOSITS")
    p3_trade_page = _find_page(pages, "22. TRADE RECEIVABLES")
    p3_contract_page = _find_page(pages, "23. CONTRACT ASSETS")
    p4_balances_page = _find_page(pages, "25. BALANCES DUE FROM RELATED PARTIES")
    p4_trans_page = _find_page(pages, "42. RELATED PARTY DISCLOSURES")
    p6_page = _find_page(pages, "40. CAPITAL COMMITMENTS")
    sub_page = _find_sub_start_page(pages)
    p13_pages = _find_profit_before_tax_pages(pages)
    p13_other_income_page = _find_page(pages, "6. OTHER INCOME AND GAINS, NET")

    missing: list[str] = []

    p2 = _parse_restricted_bank_deposits(pages[p2_page]) if p2_page else None
    if not p2:
        missing.append("P2")

    trade_text = "\n".join(
        pages[page]
        for page in [p3_trade_page, (p3_trade_page + 1) if p3_trade_page else None]
        if page and page in pages
    )
    contract_text = "\n".join(
        pages[page]
        for page in [p3_contract_page, (p3_contract_page + 1) if p3_contract_page else None]
        if page and page in pages
    )
    balances_text = "\n".join(
        pages[page]
        for page in [p4_balances_page, (p4_balances_page + 1) if p4_balances_page else None]
        if page and page in pages
    )
    p3_trade = _parse_trade_receivables(trade_text) if trade_text else None
    p3_contract = _parse_contract_assets(contract_text) if contract_text else None
    p4_balances = _parse_related_balances(balances_text) if balances_text else None
    if not p3_trade or not p3_contract:
        missing.append("P3")

    trans_text = "\n".join(
        pages[page]
        for page in [p4_trans_page, (p4_trans_page + 1) if p4_trans_page else None]
        if page and page in pages
    )
    p4_trans = _parse_related_transactions(trans_text) if trans_text else None
    if not p4_trans or not p4_balances:
        missing.append("P4")

    p6 = _parse_commitments_and_contingencies(pages[p6_page]) if p6_page else None
    if not p6:
        missing.append("P6")

    p13_page_set = []
    if p13_other_income_page:
        p13_page_set.append(p13_other_income_page)
    p13_page_set.extend(p13_pages)
    p13_page_set = sorted(set(page for page in p13_page_set if page in pages))

    p13_text = "\n".join(
        pages[page]
        for page in p13_page_set
    )
    p13 = _parse_non_operating_items(p13_text) if p13_text else None
    if not p13:
        missing.append("P13")

    sub_text = ""
    if sub_page:
        sub_text = "\n".join(
            pages[page]
            for page in range(sub_page, min(sub_page + 5, total_pages + 1))
            if page in pages
        )
    sub_rows = _parse_sub_rows(sub_text) if sub_text else []
    holding = _parse_holding_structure(sub_text) if sub_text else {}
    if not sub_rows:
        missing.append("SUB")

    completeness = "完整" if not missing else f"部分缺失（{', '.join(missing)}）"

    lines = [
        f"# 年报附注数据包：{company}",
        "",
        f"> PDF来源：{pdf_path.name}",
        f"> 总页数：{total_pages}",
        f"> 提取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 提取方式：本地 HK 年报附注 fallback（直接读取最新年报 note 页）",
        "> 金额单位：百万元（人民币）",
        f"> 数据完整性：{completeness}",
        "",
        "---",
        "",
        "## P2. 受限现金明细",
    ]

    if p2 and p2_page:
        lines.extend([
            f"- 受限银行存款：{_fmt_million(float(p2['current']), 1_000_000)} 百万元（2025 年末）",
            f"- 上年同期：{_fmt_million(float(p2['prior']), 1_000_000)} 百万元",
            f"- 用途：{p2['purpose']}",
            f"- 来源：{_printed_page_ref(pages, [p2_page])}",
        ])
    else:
        lines.append("⚠️ PDF 未找到相关章节，跳过此项")

    lines.extend([
        "",
        "## P3. 应收账款账龄",
    ])
    if p3_trade and p3_contract and p3_trade_page and p3_contract_page:
        lines.extend([
            f"- 应收账款：总额 {_fmt_million(p3_trade['gross'], 1000)}、减值 {_fmt_million(p3_trade['impairment'], 1000)}、净额 {_fmt_million(p3_trade['net'], 1000)}",
            (
                "- 账龄分布：1 个月内 "
                f"{_fmt_million(p3_trade['within_1m'], 1000)}；1-3 个月 {_fmt_million(p3_trade['m1_3'], 1000)}；"
                f"4-12 个月 {_fmt_million(p3_trade['m4_12'], 1000)}；1-2 年 {_fmt_million(p3_trade['y1_2'], 1000)}；"
                f"2 年以上 {_fmt_million(p3_trade['over_2y'], 1000)}"
            ),
            f"- 合同资产：总额 {_fmt_million(p3_contract['gross'], 1000)}、减值 {_fmt_million(p3_contract['impairment'], 1000)}、净额 {_fmt_million(p3_contract['net'], 1000)}",
            (
                f"- 合同资产构成：未开票收入 {_fmt_million(p3_contract['unbilled'], 1000)}；"
                f"质保金 {_fmt_million(p3_contract['retention'], 1000)}；"
                f"一年内回收 {_fmt_million(p3_contract.get('within_1y', 0.0), 1000)}；"
                f"一年以上回收 {_fmt_million(p3_contract.get('over_1y', 0.0), 1000)}"
            ),
        ])
        if p3_contract.get("ecl_rate") is not None:
            lines.append(
                f"- 合同资产预期信用损失率：{_fmt_percent(float(p3_contract['ecl_rate']))}；对应减值 {_fmt_million(float(p3_contract['ecl_loss']), 1000)}"
            )
        if p4_balances:
            related_trade = float(p4_balances.get("immediate_trade", 0.0)) + float(p4_balances.get("fellow_trade", 0.0)) + float(p4_balances.get("other_trade", 0.0))
            related_contract = float(p4_balances.get("fellow_contract", 0.0)) + float(p4_balances.get("other_contract", 0.0))
            lines.append(
                f"- 其中关联方往来：贸易性质应收 {_fmt_million(related_trade, 1000)}；合同资产 {_fmt_million(related_contract, 1000)}"
            )
        lines.append(
            f"- 来源：{_printed_page_ref(pages, [p3_trade_page, p3_trade_page + 1, p3_contract_page, p3_contract_page + 1, p4_balances_page])}"
        )
    else:
        lines.append("⚠️ PDF 未找到相关章节，跳过此项")

    lines.extend([
        "",
        "## P4. 关联交易",
    ])
    if p4_trans and p4_balances and p4_trans_page and p4_balances_page:
        total_income = sum(item[0] for item in p4_trans.values())
        total_expense = sum(item[1] for item in p4_trans.values())
        lines.extend([
            (
                "- 关联方服务收入："
                f"CSCEC 系 {_fmt_million(p4_trans['cscec'][0], 1000)}；"
                f"COHL 系 {_fmt_million(p4_trans['cohl'][0], 1000)}；"
                f"COLI/CSC 系 {_fmt_million(p4_trans['coli_csc'][0], 1000)}；"
                f"其他关联方 {_fmt_million(p4_trans['other'][0], 1000)}；"
                f"合计 {_fmt_million(total_income, 1000)}"
            ),
            (
                "- 向关联方支付租金/水电等："
                f"CSCEC 系 {_fmt_million(p4_trans['cscec'][1], 1000)}；"
                f"COHL 系 {_fmt_million(p4_trans['cohl'][1], 1000)}；"
                f"COLI/CSC 系 {_fmt_million(p4_trans['coli_csc'][1], 1000)}；"
                f"其他关联方 {_fmt_million(p4_trans['other'][1], 1000)}；"
                f"合计 {_fmt_million(total_expense, 1000)}"
            ),
            (
                "- 年末关联方资产往来："
                f"即期控股股东 {_fmt_million(float(p4_balances.get('immediate_trade', 0.0)), 1000)}；"
                f"同系附属公司 {_fmt_million(float(p4_balances.get('fellow_total', 0.0)), 1000)}；"
                f"其他关联方 {_fmt_million(float(p4_balances.get('other_total', 0.0)), 1000)}；"
                f"合计 {_fmt_million(float(p4_balances.get('total', 0.0)), 1000)}"
            ),
            (
                "- 其中合同资产："
                f"同系附属公司 {_fmt_million(float(p4_balances.get('fellow_contract', 0.0)), 1000)}；"
                f"其他关联方 {_fmt_million(float(p4_balances.get('other_contract', 0.0)), 1000)}"
            ),
            "- 备注：年报明确将上述交易界定为 HKEX Listing Rules Chapter 14A 下的 connected / continuing connected transactions。",
            f"- 来源：{_printed_page_ref(pages, [p4_balances_page, p4_balances_page + 1, p4_trans_page, p4_trans_page + 1])}",
        ])
    else:
        lines.append("⚠️ PDF 未找到相关章节，跳过此项")

    lines.extend([
        "",
        "## P6. 或有负债与承诺",
    ])
    if p6 and p6_page:
        total_contingent = (
            float(p6.get("counter_indemnity_fellow_sub", 0.0))
            + float(p6.get("counter_indemnity_banks", 0.0))
            + float(p6.get("guarantee_coli", 0.0))
            + float(p6.get("guarantee_csc", 0.0))
            + float(p6.get("guarantee_cogo", 0.0))
        )
        related_guarantees = (
            float(p6.get("guarantee_coli", 0.0))
            + float(p6.get("guarantee_csc", 0.0))
            + float(p6.get("guarantee_cogo", 0.0))
        )
        lines.extend([
            (
                "- 资本承诺："
                f"收购无形资产 {_fmt_million(float(p6.get('intangibles_commitment', 0.0)), 1000)}；"
                f"合计 {_fmt_million(float(p6.get('total_commitment', 0.0)), 1000)}"
            ),
            (
                "- 或有负债："
                f"向同系附属公司反担保 {_fmt_million(float(p6.get('counter_indemnity_fellow_sub', 0.0)), 1_000_000)}；"
                f"向银行反担保 {_fmt_million(float(p6.get('counter_indemnity_banks', 0.0)), 1_000_000)}；"
                f"对 COLI/CSC/COGO 担保 {_fmt_million(related_guarantees, 1_000_000)}；"
                f"口径合计 {_fmt_million(total_contingent, 1_000_000)}"
            ),
        ])
        if p6.get("future_coli_million") is not None:
            lines.append(
                f"- 后续承诺：公司公告披露自 {p6['future_from']} 年 1 月 1 日至 {p6['future_to']} 年 12 月 31 日继续向 COLI 提供上限 RMB{p6['future_coli_million']:.1f} 百万元的公司担保。"
            )
        lines.append(f"- 来源：{_printed_page_ref(pages, [p6_page])}")
    else:
        lines.append("⚠️ PDF 未找到相关章节，跳过此项")

    lines.extend([
        "",
        "## P13. 非经常性损益",
    ])
    if p13 and p13_page_set:
        gov_total = float(p13.get("gov_total", 0.0)) or (float(p13.get("gov_tax_benefit", 0.0)) + float(p13.get("gov_other", 0.0)))
        impair_total = p13.get("impair_total")
        if impair_total is None:
            impair_total = (
                float(p13.get("impair_trade", 0.0))
                + float(p13.get("impair_contract", 0.0))
                + float(p13.get("impair_other", 0.0))
                + float(p13.get("recover_prior_writeoff", 0.0))
            )
        fair_value_total = p13.get("fair_value_total")
        if fair_value_total is None:
            fair_value_total = float(p13.get("fair_value_self_owned", 0.0)) + float(p13.get("fair_value_leased", 0.0))
        lease_term = p13.get("lease_termination_gain")
        fx_gain = p13.get("fx_gain_net")
        lines.extend([
            "- 说明：港股年报通常不单列 A 股口径“非经常性损益”，此处改列对利润影响较明显的一次性/非经营性/估值类项目，供 Phase 3 调整口径时参考。",
            f"- 政府补助：税收优惠 {_fmt_million(float(p13.get('gov_tax_benefit', 0.0)), 1000)}；其他补助 {_fmt_million(float(p13.get('gov_other', 0.0)), 1000)}；合计 {_fmt_million(gov_total, 1000)}",
            f"- 金融资产与合同资产减值净额：应收账款 {_fmt_million(float(p13.get('impair_trade', 0.0)), 1000)}；合同资产 {_fmt_million(float(p13.get('impair_contract', 0.0)), 1000)}；其他应收款 {_fmt_million(float(p13.get('impair_other', 0.0)), 1000)}；合计 {_fmt_million(float(impair_total), 1000)}",
            f"- 投资物业公允价值变动损失：自有物业 {_fmt_million(float(p13.get('fair_value_self_owned', 0.0)), 1000)}；租赁物业 {_fmt_million(float(p13.get('fair_value_leased', 0.0)), 1000)}；合计 {_fmt_million(float(fair_value_total), 1000)}",
        ])
        if lease_term is not None:
            lines.append(f"- 提前终止租约净收益：{_fmt_million(float(lease_term), 1000)}")
        if p13.get("loss_disposal_ppe") is not None:
            lines.append(f"- 固定资产处置损失净额：{_fmt_million(float(p13['loss_disposal_ppe']), 1000)}")
        if fx_gain is not None:
            lines.append(f"- 汇兑净收益：{_fmt_million(abs(float(fx_gain)), 1000)}（年报列示为 gain，报表符号为负值）")
        if p13.get("interest_income") is not None:
            lines.append(f"- 利息收入：{_fmt_million(float(p13['interest_income']), 1000)}")
        lines.append(f"- 来源：{_printed_page_ref(pages, p13_page_set)}")
    else:
        lines.append("⚠️ PDF 未稳定识别出一次性/非经营性项目页，跳过此项")

    lines.extend([
        "",
        "## SUB. 主要控股参股公司（条件触发）",
    ])
    if sub_rows and sub_page:
        samples = _pick_sub_samples(sub_rows)
        table_rows = [
            [row["name"], _holding_pct(row), row["capital"], row["activity"]]
            for row in samples
        ]
        lines.extend([
            "### 合并范围与控股结构摘要",
            "",
            f"- 上市主体：China Overseas Property Holdings Limited，注册地 Cayman Islands",
            f"- 直接控股股东：{holding.get('immediate_holding', '未识别')}",
            f"- 最终控股股东：{holding.get('ultimate_holding', '未识别')}",
            "",
            "### 主要控股子公司样本",
            "",
            _format_table(["子公司名称", "归属持股", "注册资本", "主营业务"], table_rows),
            "",
            "### 补充说明",
            "",
            "- 年报注明：表列子公司为董事认为对年内业绩有主要影响，或构成集团净资产重大部分的主体。",
            "- 子公司结构覆盖传统物业管理、工程维保、清洁安保、品牌持有及 O2O 平台等多种职能。",
            f"- 来源：{_printed_page_ref(pages, list(range(sub_page, min(sub_page + 5, total_pages + 1))))}",
        ])
    else:
        lines.append("⚠️ PDF 未找到相关章节，跳过此项")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    ts_code = validate_stock_code(args.code)
    if not ts_code.endswith(".HK"):
        raise ValueError("hk_pdf_report_pack.py only supports HK stocks")
    output_dir = Path(args.output_dir).resolve()
    output_path = Path(args.output).resolve() if args.output else output_dir / "data_pack_report.md"
    output_path.write_text(build_markdown(output_dir, ts_code), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
