#!/usr/bin/env python3
"""Extract fallback HK financial statements from annual reports.

This module reconstructs a small, valuation-oriented structured dataset from
local annual reports when HK Tushare financial endpoints are empty.

Output values are normalized to raw HKD (not millions), matching the rest of
the repository's HK data path:
- statement monetary amounts: raw HKD
- EPS / DPS: HKD per share
- ratios: percentages
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pdfplumber


TITLE_INCOME = "CONSOLIDATED STATEMENT OF PROFIT OR LOSS"
TITLE_BALANCE = "CONSOLIDATED STATEMENT OF FINANCIAL POSITION"
TITLE_CASHFLOW = "CONSOLIDATED STATEMENT OF CASH FLOWS"
TITLE_HIGHLIGHTS = "BUSINESS AND FINANCIAL HIGHLIGHTS"

NUM_RE = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")
YEAR_RE = re.compile(r"\b(20\d{2})\b")

INCOME_ROWS = {
    "revenue": ["REVENUE"],
    "oper_cost": ["Direct operating expenses"],
    "gross_profit": ["GROSS PROFIT"],
    "admin_exp": ["Selling and administrative expenses"],
    "operate_profit": ["OPERATING PROFIT"],
    "finance_exp": ["Finance costs"],
    "total_profit": ["PROFIT BEFORE TAX"],
    "income_tax": ["Income tax expenses"],
    "n_income": ["PROFIT FOR THE YEAR"],
    "n_income_attr_p": [
        "Ordinary equity holders of the Company",
        "Shareholders of the Company",
    ],
    "minority_gain": ["Non-controlling interests"],
    "basic_eps_local_cents": ["Basic and diluted"],
    "diluted_eps_local_cents": ["Basic and diluted"],
    "_joint_profit": ["Share of profit of a joint venture"],
    "_associate_profit": ["Share of profit of an associate"],
}

BALANCE_ROWS = {
    "fix_assets": ["Property, plant and equipment"],
    "intang_assets": ["Intangible assets"],
    "defer_tax_assets": ["Deferred tax assets"],
    "inventories": ["Inventories"],
    "accounts_receiv": [
        "Trade receivables",
        "Trade and retention receivables",
        "Trade receivables, retention receivables and other contract assets",
    ],
    "money_cap": ["Cash and bank balances"],
    "total_cur_assets": ["Total current assets"],
    "_total_non_cur_assets": ["Total non-current assets"],
    "acct_payable": ["Trade payables"],
    "_temp_receipts": ["Temporary receipts from properties managed"],
    "_adv_other_deposits": ["Receipts in advance and other deposits"],
    "st_borr": ["Bank borrowings"],
    "total_cur_liab": ["Total current liabilities"],
    "_total_non_cur_liab": ["Total non-current liabilities"],
    "defer_tax_liab": ["Deferred tax liabilities"],
    "minority_int": ["Non-controlling interests"],
    "_total_equity": ["Total equity"],
    "total_assets": ["Total assets"],
    "total_liab": ["Total liabilities", "Total current liabilities and non-current liabilities"],
}

CASHFLOW_ROWS = {
    "n_cashflow_act": ["Net cash flows from operating activities"],
    "n_cashflow_inv_act": ["Net cash flows used in investing activities", "Net cash flows from/(used in) investing activities"],
    "n_cash_flows_fnc_act": ["Net cash flows used in financing activities"],
    "_dep_ppe": ["Depreciation of property, plant and equipment", "Depreciation of items of property, plant and equipment"],
    "_dep_rou": ["Depreciation of right-of-use assets"],
    "_amort_intang": ["Amortisation of intangible assets"],
    "_purchase_ppe": ["Purchase of items of property, plant and equipment"],
    "_purchase_inv_prop": ["Purchase of an investment property"],
    "_purchase_intang": ["Addition of intangible assets", "Purchase of intangible assets"],
    "_advance_capex": ["Advance payments for the purchase of items of property, plant and equipment and intangible assets"],
    "_tax_paid": ["Income taxes paid"],
    "_withholding_tax_paid": ["PRC withholding tax paid"],
    "_dividends_paid": ["Dividends paid to ordinary equity holders of the Company", "Dividends paid to shareholders of the Company"],
}

EMPLOYEE_BENEFIT_PATTERNS = {
    "wages_and_salaries": r"Wages and salaries\s+([\d,]+)\s+[\d,]+",
    "share_based_payments": r"Share-based payments .*?\s+(\(?[\d,]+\)?)\s+\(?[\d,]+\)?",
    "pension_contributions": r"Pension scheme contributions .*?\s+([\d,]+)\s+[\d,]+",
    "employee_total": r"Employee benefit expenses .*?[\r\n\s]+([\d,]+)\s+[\d,]+[\r\n\s]+Less: Included in direct operating expenses",
    "included_in_direct_opex": r"Less: Included in direct operating expenses\s+\(([\d,]+)\)\s+\([\d,]+\)",
    "employee_above_opex": r"Less: Included in direct operating expenses .*?[\r\n\s]+([\d,]+)\s+[\d,]+",
}

KNOWN_PAGE_HINTS = {
    "02669_2025_年报.pdf": {
        "highlights": 6, "income": 128, "balance": 130, "cashflow": 134,
        "corporate_info": 4, "management": 89, "directors_report": 92,
        "holders": 98, "audit_report": 123,
    },
    "02669_2024_年报.pdf": {"highlights": 6, "income": 122, "balance": 124, "cashflow": 128},
    "02669_2023_年报.pdf": {"highlights": 6, "income": 136, "balance": 138, "cashflow": 142},
    "02669_2022_年报.pdf": {"highlights": 6, "income": 116, "balance": 118, "cashflow": 122},
    "02669_2021_年报.pdf": {"highlights": 6, "income": 112, "balance": 114, "cashflow": 118},
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _to_number(token: str) -> float | None:
    token = token.strip()
    if not token:
        return None
    negative = token.startswith("(") and token.endswith(")")
    token = token.strip("()").replace(",", "")
    try:
        value = float(token)
    except ValueError:
        return None
    return -value if negative else value


def _extract_text(doc: pdfplumber.PDF, page_num: int | None) -> str:
    if page_num is None or page_num < 1 or page_num > len(doc.pages):
        return ""
    return doc.pages[page_num - 1].extract_text() or ""


def _find_pages(doc: pdfplumber.PDF, needle: str) -> list[int]:
    pages: list[int] = []
    for idx, page in enumerate(doc.pages, start=1):
        text = page.extract_text() or ""
        if needle.lower() in text.lower():
            pages.append(idx)
    return pages


def _find_statement_start(doc: pdfplumber.PDF, needle: str, pdf_name: str) -> int | None:
    hints = KNOWN_PAGE_HINTS.get(pdf_name, {})
    hint_key = {
        TITLE_INCOME: "income",
        TITLE_BALANCE: "balance",
        TITLE_CASHFLOW: "cashflow",
    }.get(needle)
    hinted = hints.get(hint_key) if hint_key else None
    if hinted:
        return hinted
    pages = _find_pages(doc, needle)
    if not pages:
        return None
    # The contents page often contains the title; the actual statement is the last hit.
    return pages[-1]


def _find_highlights_start(doc: pdfplumber.PDF, pdf_name: str) -> int | None:
    hinted = KNOWN_PAGE_HINTS.get(pdf_name, {}).get("highlights")
    if hinted:
        return hinted
    pages = _find_pages(doc, TITLE_HIGHLIGHTS)
    if not pages:
        return None
    return pages[0]


def _header_years(lines: list[str]) -> list[int]:
    candidates: list[list[int]] = []
    for line in lines[:16]:
        years = [int(y) for y in YEAR_RE.findall(line)]
        if len(years) >= 2:
            candidates.append(years)
    return candidates[-1] if candidates else []


def _statement_currency(text: str) -> str:
    if "RMB" in text:
        return "RMB"
    if "HK$" in text or "HKD" in text:
        return "HKD"
    return "HKD"


def _extract_row_values(lines: list[str], labels: list[str], total_cols: int) -> list[float] | None:
    normalized_labels = [_normalize(label) for label in labels]
    for idx in range(len(lines)):
        window = " ".join(lines[idx: idx + 3])
        window_norm = _normalize(window)
        if not any(label in window_norm for label in normalized_labels):
            continue
        values = [_to_number(tok) for tok in NUM_RE.findall(window)]
        values = [v for v in values if v is not None]
        if len(values) >= total_cols:
            statement_values = values[-total_cols:]
            return statement_values
    return None


def _extract_highlight_pair(text: str, pattern: str) -> tuple[float | None, float | None]:
    match = re.search(pattern, text, re.I)
    if not match:
        return None, None
    left = _to_number(match.group(1))
    right = _to_number(match.group(2))
    return left, right


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _scale_to_hkd_raw(value: float | None, currency: str, fx_to_hkd: float) -> float | None:
    if value is None:
        return None
    if currency == "RMB":
        return value * 1000.0 * fx_to_hkd
    return value * 1000.0


def _eps_to_hkd(local_cents: float | None, currency: str, fx_to_hkd: float) -> float | None:
    if local_cents is None:
        return None
    if currency == "RMB":
        return local_cents * fx_to_hkd / 100.0
    return local_cents / 100.0


def _extract_highlights(doc: pdfplumber.PDF, pdf_name: str) -> dict[int, dict]:
    page = _find_highlights_start(doc, pdf_name)
    if page is None:
        return {}
    text = "\n".join(
        part for part in (_extract_text(doc, page), _extract_text(doc, page + 1)) if part
    )
    compact = re.sub(r"\s+", " ", text)

    years = _header_years(text.splitlines())
    if len(years) < 2:
        # Fallback: infer from current report year in the continuation page.
        m = re.search(r"Formula\s+(20\d{2})\s+(20\d{2})", compact)
        years = [int(m.group(1)), int(m.group(2))] if m else []
    if len(years) < 2:
        return {}

    year0, year1 = years[0], years[1]

    dps0, dps1 = _extract_highlight_pair(
        compact,
        r"Dividends per share(?: \(HK cents\))?(?: \(excluding special dividend\))?\s+([\d.]+)\s+([\d.]+)",
    )
    payout0, payout1 = _extract_highlight_pair(
        compact,
        r"Payout ratio .*?\s+([\d.]+)%\s+([\d.]+)%",
    )
    roe0, roe1 = _extract_highlight_pair(
        compact,
        r"Average return on equity .*?\s+([\d.]+)%\s+([\d.]+)%",
    )
    debt0, debt1 = _extract_highlight_pair(
        compact,
        r"Debt-to-assets ratio .*?\s+([\d.]+)%\s+([\d.]+)%",
    )
    margin0, margin1 = _extract_highlight_pair(
        compact,
        r"Net Profit Margin .*?\s+([\d.]+)%\s+([\d.]+)%",
    )
    current_ratio0, current_ratio1 = _extract_highlight_pair(
        compact,
        r"Current ratio .*?\s+([\d.]+)\s+([\d.]+)",
    )
    eps_local0, eps_local1 = _extract_highlight_pair(
        compact,
        r"Earnings per share \((?:RMB|HK) cents\)\*?\s+([\d.]+)\s+([\d.]+)",
    )
    eps_hk0, eps_hk1 = _extract_highlight_pair(
        compact,
        r"\(equivalent to HK cents\)\s+\(?([\d.]+)\)?\s+\(?([\d.]+)\)?",
    )

    highlights = {
        year0: {
            "dps_hkd": dps0 / 100.0 if dps0 is not None else None,
            "divi_ratio": payout0,
            "roe_avg": roe0,
            "debt_asset_ratio": debt0,
            "net_profit_ratio": margin0,
            "current_ratio": current_ratio0,
            "_eps_local_cents": eps_local0,
            "_eps_hk_cents": eps_hk0,
        },
        year1: {
            "dps_hkd": dps1 / 100.0 if dps1 is not None else None,
            "divi_ratio": payout1,
            "roe_avg": roe1,
            "debt_asset_ratio": debt1,
            "net_profit_ratio": margin1,
            "current_ratio": current_ratio1,
            "_eps_local_cents": eps_local1,
            "_eps_hk_cents": eps_hk1,
        },
    }

    for year, row in highlights.items():
        local_cents = row.get("_eps_local_cents")
        hk_cents = row.get("_eps_hk_cents")
        if local_cents and hk_cents:
            row["fx_to_hkd"] = hk_cents / local_cents
        else:
            row["fx_to_hkd"] = 1.0
    return highlights


def _extract_corporate_text(doc: pdfplumber.PDF, pdf_name: str, key: str, pages: int = 1) -> str:
    start = KNOWN_PAGE_HINTS.get(pdf_name, {}).get(key)
    if not start:
        return ""
    parts = [_extract_text(doc, start + offset) for offset in range(pages)]
    return "\n".join(part for part in parts if part)


def _is_person_name(line: str) -> bool:
    line = line.strip()
    return bool(re.match(r"^(Mr|Ms|Mrs|Dr)\.\s+", line))


def _clean_role_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ,")


def _extract_board_from_report(report: str) -> list[dict]:
    lines = [line.strip() for line in report.splitlines() if line.strip()]
    results: list[dict] = []
    category = None
    title_override = None
    stop_markers = (
        "In accordance with",
        "Biographical details",
        "Directors’ service contracts",
    )
    category_map = {
        "Chairman and Executive Director": ("Executive Directors", "Chairman"),
        "Executive Directors": ("Executive Directors", None),
        "Non-executive Directors": ("Non-executive Directors", None),
        "Independent Non-executive Directors": ("Independent Non-executive Directors", None),
    }

    for line in lines:
        if any(line.startswith(marker) for marker in stop_markers):
            break
        mapped = category_map.get(line)
        if mapped:
            category, title_override = mapped
            continue
        if category and _is_person_name(line):
            entry = {"category": category, "name": line}
            title = title_override
            match = re.search(r"\(([^()]+)\)", line)
            if match:
                title = match.group(1).strip()
                entry["name"] = re.sub(r"\s*\([^()]+\)", "", line).strip()
            if title:
                entry["title"] = title
            results.append(entry)
    return results


def _extract_management(management: str) -> list[dict]:
    lines = [line.strip() for line in management.splitlines() if line.strip()]
    results: list[dict] = []
    seen_header = False
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if line == "Senior Management":
            seen_header = True
            idx += 1
            continue
        if not seen_header:
            idx += 1
            continue
        if _is_person_name(line):
            if idx + 1 < len(lines):
                title = lines[idx + 1]
                if (
                    not _is_person_name(title)
                    and not title.startswith("Aged ")
                    and len(title) <= 80
                    and not title.startswith("Directors and Senior Management")
                ):
                    results.append({
                        "category": "Senior Management",
                        "name": line,
                        "title": _clean_role_text(title),
                    })
                    idx += 2
                    continue
        idx += 1

    return results


def _extract_holders(holders: str) -> list[dict]:
    lines = [line.strip() for line in holders.splitlines() if line.strip()]
    table_started = False
    rows: list[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if "Long Positions in Shares of the Company" in line:
            table_started = True
            idx += 1
            continue
        if not table_started:
            idx += 1
            continue
        if line.startswith("Notes:") or line.startswith("Save as disclosed above"):
            break
        if line.startswith(("Number of", "Ordinary Percentage of", "Name of Shareholder", "Shares held Shares in Issue")):
            idx += 1
            continue
        if not re.search(r"\d", line):
            idx += 1
            continue

        row = line
        while idx + 1 < len(lines):
            next_line = lines[idx + 1]
            if next_line.startswith(("Notes:", "Save as disclosed above")):
                break
            if next_line.startswith(("Number of", "Ordinary Percentage of", "Name of Shareholder", "Shares held Shares in Issue")):
                idx += 1
                continue
            if next_line in {"corporation", "corporations"} or next_line.startswith(("Limited ", "(")):
                row = f"{row} {next_line}"
                idx += 1
                continue
            if next_line.startswith("Interest of controlled") and "Beneficial owner" in row:
                row = f"{row} {next_line}"
                idx += 1
                continue
            break
        rows.append(re.sub(r"\s+", " ", row).strip())
        idx += 1

    results: list[dict] = []
    seen: set[tuple[str, int, float]] = set()
    for row in rows:
        normalized = re.sub(r"\s+", " ", row)
        name_match = re.match(r"(.+?)\s+(Beneficial owner|Interest of controlled)", normalized)
        if not name_match:
            continue
        holder_name = name_match.group(1).strip()
        suffix_match = re.search(r"((?:Limited\s+)?[（(“\"].+?[”\")])\s+corporations?$", normalized)
        if suffix_match:
            suffix = suffix_match.group(1).strip()
            if suffix.startswith("Limited "):
                holder_name = f"{holder_name} {suffix}".strip()
            else:
                holder_name = f"{holder_name} {suffix}".strip()
        metric_matches = re.findall(r"([\d,]+)\s+(?:\d+\s+)?([\d.]+)%", normalized)
        if not metric_matches:
            continue
        parsed_metrics = [
            (int(shares.replace(",", "")), float(ratio))
            for shares, ratio in metric_matches
        ]
        shares, ratio = max(parsed_metrics, key=lambda item: item[0])
        capacity = "Beneficial owner" if "Beneficial owner" in normalized else "Interest of controlled corporations"
        key = (holder_name, shares, ratio)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "holder_name": holder_name,
            "capacity": capacity,
            "shares": shares,
            "hold_ratio": ratio,
        })
    return results


def _extract_governance(doc: pdfplumber.PDF, pdf_name: str) -> dict:
    corp = _extract_corporate_text(doc, pdf_name, "corporate_info", pages=2)
    management = _extract_corporate_text(doc, pdf_name, "management", pages=3)
    holders = _extract_corporate_text(doc, pdf_name, "holders", pages=2)
    report = _extract_corporate_text(doc, pdf_name, "directors_report", pages=5)
    audit = _extract_corporate_text(doc, pdf_name, "audit_report", pages=4)

    result = {
        "holders": [],
        "board_and_management": [],
        "audit": {},
        "repurchase": {},
    }

    result["board_and_management"].extend(_extract_board_from_report(report))
    result["board_and_management"].extend(_extract_management(management))
    result["holders"] = _extract_holders(holders)

    # Corporate information: auditor
    lines = [line.strip() for line in corp.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if line == "Independent Auditor":
            auditor_name = None
            for item in lines[idx + 1: idx + 6]:
                if "Ernst" in item or "KPMG" in item or "Deloitte" in item or "PwC" in item:
                    auditor_name = item
                    break
            if auditor_name:
                result["audit"]["audit_agency"] = auditor_name

    # Audit opinion
    audit_text = audit.replace("\u2019", "'")
    if "In our opinion" in audit_text and "true and fair view" in audit_text:
        result["audit"]["audit_result"] = "标准无保留意见"
    if not result["audit"].get("audit_agency"):
        m = re.search(r"INDEPENDENT AUDITOR.?S REPORT\s+([A-Za-z& ]+)", audit_text, re.I)
        if m:
            result["audit"]["audit_agency"] = m.group(1).strip()

    # Repurchase
    report_text = report.replace("\u2019", "'").lower()
    if (
        "had not redeemed any of its shares during the year" in report_text
        and "neither the company nor any of its subsidiaries purchased or sold any of the company's listed securities during the year" in report_text
    ):
        result["repurchase"] = {"has_repurchase": False, "summary": "年内无股份购回或赎回"}
    elif "purchased or sold any of the company's listed securities during the year" in report_text:
        result["repurchase"] = {"has_repurchase": False, "summary": "年内无股份购回或赎回"}

    return result


def _extract_statement_rows(
    lines: list[str],
    total_cols: int,
    row_map: dict[str, list[str]],
) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for field, labels in row_map.items():
        values = _extract_row_values(lines, labels, total_cols)
        if values:
            result[field] = values
    return result


def _extract_income(doc: pdfplumber.PDF, pdf_name: str) -> dict:
    page = _find_statement_start(doc, TITLE_INCOME, pdf_name)
    if page is None:
        return {}
    text = _extract_text(doc, page)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    years = _header_years(lines)
    if len(years) < 2:
        return {}
    total_cols = len(years)
    currency = _statement_currency(text)
    rows = _extract_statement_rows(lines, total_cols, INCOME_ROWS)
    return {
        "years": years[:2],
        "total_cols": total_cols,
        "currency": currency,
        "rows": rows,
    }


def _extract_balance(doc: pdfplumber.PDF, pdf_name: str) -> dict:
    page = _find_statement_start(doc, TITLE_BALANCE, pdf_name)
    if page is None:
        return {}
    text1 = _extract_text(doc, page)
    text2 = _extract_text(doc, page + 1)
    lines = [
        line.strip()
        for line in (text1 + "\n" + text2).splitlines()
        if line.strip()
    ]
    years = _header_years(text1.splitlines())
    if len(years) < 2:
        return {}
    total_cols = len(years)
    currency = _statement_currency(text1)
    rows = _extract_statement_rows(lines, total_cols, BALANCE_ROWS)
    return {
        "years": years[:2],
        "total_cols": total_cols,
        "currency": currency,
        "rows": rows,
    }


def _extract_cashflow(doc: pdfplumber.PDF, pdf_name: str) -> dict:
    page = _find_statement_start(doc, TITLE_CASHFLOW, pdf_name)
    if page is None:
        return {}
    text1 = _extract_text(doc, page)
    text2 = _extract_text(doc, page + 1)
    lines = [
        line.strip()
        for line in (text1 + "\n" + text2).splitlines()
        if line.strip()
    ]
    years = _header_years(text1.splitlines())
    if len(years) < 2:
        return {}
    total_cols = len(years)
    currency = _statement_currency(text1)
    rows = _extract_statement_rows(lines, total_cols, CASHFLOW_ROWS)
    return {
        "years": years[:2],
        "total_cols": total_cols,
        "currency": currency,
        "rows": rows,
    }


def _extract_profit_before_tax_text(doc: pdfplumber.PDF, pdf_name: str) -> str:
    income_start = _find_statement_start(doc, TITLE_INCOME, pdf_name)
    if income_start is None:
        return ""
    start_page = max(1, income_start + 52)
    end_page = min(len(doc.pages), income_start + 58)
    parts: list[str] = []
    for page_num in range(start_page, end_page + 1):
        text = _extract_text(doc, page_num)
        if "8. PROFIT BEFORE TAX" in text or "The Group’s profit before tax is arrived at" in text:
            parts.append(text)
        elif parts and "9. DIRECTORS’ REMUNERATION" not in text:
            parts.append(text)
        elif parts:
            break
    return "\n".join(part for part in parts if part)


def _extract_employee_benefit_proxy(doc: pdfplumber.PDF, pdf_name: str) -> dict[str, float] | None:
    text = _extract_profit_before_tax_text(doc, pdf_name)
    if not text:
        return None
    compact = re.sub(r"\s+", " ", text)
    result: dict[str, float] = {}
    for key, pattern in EMPLOYEE_BENEFIT_PATTERNS.items():
        match = re.search(pattern, compact, re.I)
        if not match:
            continue
        value = _to_number(match.group(1))
        if value is None:
            continue
        result[key] = abs(float(value))
    return result or None


def _report_file_year(pdf_path: Path) -> int:
    match = re.search(r"(20\d{2})", pdf_path.name)
    return int(match.group(1)) if match else 0


def _raw_year_records(pdf_path: Path) -> dict[int, dict]:
    with pdfplumber.open(str(pdf_path)) as doc:
        pdf_name = pdf_path.name
        highlights = _extract_highlights(doc, pdf_name)
        income = _extract_income(doc, pdf_name)
        balance = _extract_balance(doc, pdf_name)
        cashflow = _extract_cashflow(doc, pdf_name)
        employee_proxy = _extract_employee_benefit_proxy(doc, pdf_name)
        governance = _extract_governance(doc, pdf_name)

    if not income:
        return {}

    report_year = income["years"][0]
    years = income["years"]
    output: dict[int, dict] = {}
    for idx, year in enumerate(years[:2]):
        highlight = highlights.get(year, {})
        fx_to_hkd = highlight.get("fx_to_hkd", 1.0 if income["currency"] == "HKD" else None)
        if fx_to_hkd is None:
            fx_to_hkd = 1.1
        output[year] = {
            "source_pdf": pdf_path.name,
            "source_report_year": report_year,
            "statement_currency": income["currency"],
            "fx_to_hkd": fx_to_hkd,
            "income": {},
            "balance_sheet": {},
            "cashflow": {},
            "dividend": {},
            "fina_indicator": {},
            "employee_proxy": employee_proxy or {},
            "governance": governance,
        }

        rows = income["rows"]
        joint = rows.get("_joint_profit", [None, None])
        assoc = rows.get("_associate_profit", [None, None])
        invest_income = None
        if joint[idx] is not None or assoc[idx] is not None:
            invest_income = float(joint[idx] or 0.0) + float(assoc[idx] or 0.0)

        output[year]["income"] = {
            "revenue": rows.get("revenue", [None, None])[idx],
            "oper_cost": abs(rows.get("oper_cost", [None, None])[idx]) if rows.get("oper_cost") else None,
            "gross_profit": rows.get("gross_profit", [None, None])[idx],
            "admin_exp": abs(rows.get("admin_exp", [None, None])[idx]) if rows.get("admin_exp") else None,
            "operate_profit": rows.get("operate_profit", [None, None])[idx],
            "invest_income": invest_income,
            "finance_exp": abs(rows.get("finance_exp", [None, None])[idx]) if rows.get("finance_exp") else None,
            "total_profit": rows.get("total_profit", [None, None])[idx],
            "income_tax": abs(rows.get("income_tax", [None, None])[idx]) if rows.get("income_tax") else None,
            "n_income": rows.get("n_income", [None, None])[idx],
            "n_income_attr_p": rows.get("n_income_attr_p", [None, None])[idx],
            "minority_gain": rows.get("minority_gain", [None, None])[idx],
            "basic_eps_local_cents": rows.get("basic_eps_local_cents", [None, None])[idx],
            "diluted_eps_local_cents": rows.get("diluted_eps_local_cents", [None, None])[idx],
        }

        b_rows = balance.get("rows", {})
        cur_assets = b_rows.get("total_cur_assets", [None, None])[idx] if b_rows.get("total_cur_assets") else None
        non_cur_assets = b_rows.get("_total_non_cur_assets", [None, None])[idx] if b_rows.get("_total_non_cur_assets") else None
        total_assets = None
        if cur_assets is not None or non_cur_assets is not None:
            total_assets = float(cur_assets or 0.0) + float(non_cur_assets or 0.0)
        elif b_rows.get("total_assets"):
            total_assets = b_rows.get("total_assets", [None, None])[idx]

        total_liab = b_rows.get("total_liab", [None, None])[idx] if b_rows.get("total_liab") else None
        if total_liab is None:
            cur_liab = b_rows.get("total_cur_liab", [None, None])[idx] if b_rows.get("total_cur_liab") else None
            non_cur_liab = b_rows.get("_total_non_cur_liab", [None, None])[idx] if b_rows.get("_total_non_cur_liab") else None
            if cur_liab is not None or non_cur_liab is not None:
                total_liab = float(cur_liab or 0.0) + float(non_cur_liab or 0.0)

        total_equity = b_rows.get("_total_equity", [None, None])[idx] if b_rows.get("_total_equity") else None
        minority = b_rows.get("minority_int", [None, None])[idx] if b_rows.get("minority_int") else None
        holder_equity = None
        if total_equity is not None:
            holder_equity = float(total_equity) - float(minority or 0.0)

        output[year]["balance_sheet"] = {
            "money_cap": b_rows.get("money_cap", [None, None])[idx],
            "accounts_receiv": b_rows.get("accounts_receiv", [None, None])[idx],
            "inventories": b_rows.get("inventories", [None, None])[idx],
            "total_cur_assets": b_rows.get("total_cur_assets", [None, None])[idx],
            "fix_assets": b_rows.get("fix_assets", [None, None])[idx],
            "intang_assets": b_rows.get("intang_assets", [None, None])[idx],
            "defer_tax_assets": b_rows.get("defer_tax_assets", [None, None])[idx],
            "total_assets": total_assets,
            "acct_payable": b_rows.get("acct_payable", [None, None])[idx],
            # HK proxy for contract liabilities / customer prepayments:
            # property-management temporary receipts + receipts in advance and other deposits.
            "contract_liab": (
                float(b_rows.get("_temp_receipts", [0.0, 0.0])[idx] or 0.0)
                + float(b_rows.get("_adv_other_deposits", [0.0, 0.0])[idx] or 0.0)
            ) if (
                b_rows.get("_temp_receipts") or b_rows.get("_adv_other_deposits")
            ) else None,
            "adv_receipts": b_rows.get("_adv_other_deposits", [None, None])[idx],
            "_temp_receipts": b_rows.get("_temp_receipts", [None, None])[idx],
            "st_borr": b_rows.get("st_borr", [None, None])[idx],
            "total_cur_liab": b_rows.get("total_cur_liab", [None, None])[idx],
            "defer_tax_liab": b_rows.get("defer_tax_liab", [None, None])[idx],
            "total_liab": total_liab,
            "total_hldr_eqy_exc_min_int": holder_equity,
            "minority_int": minority,
        }

        c_rows = cashflow.get("rows", {})
        dep_ppe = c_rows.get("_dep_ppe", [None, None])[idx]
        dep_rou = c_rows.get("_dep_rou", [None, None])[idx]
        amort_intang = c_rows.get("_amort_intang", [None, None])[idx]
        da_total = None
        if any(v is not None for v in (dep_ppe, dep_rou, amort_intang)):
            da_total = float(dep_ppe or 0.0) + float(dep_rou or 0.0) + float(amort_intang or 0.0)

        capex_parts = [
            c_rows.get("_purchase_ppe", [None, None])[idx] if c_rows.get("_purchase_ppe") else None,
            c_rows.get("_purchase_inv_prop", [None, None])[idx] if c_rows.get("_purchase_inv_prop") else None,
            c_rows.get("_purchase_intang", [None, None])[idx] if c_rows.get("_purchase_intang") else None,
            c_rows.get("_advance_capex", [None, None])[idx] if c_rows.get("_advance_capex") else None,
        ]
        capex = None
        if any(v is not None for v in capex_parts):
            capex = sum(float(v or 0.0) for v in capex_parts)

        tax_paid = None
        if c_rows.get("_tax_paid") or c_rows.get("_withholding_tax_paid"):
            tax_paid = float((c_rows.get("_tax_paid", [0.0, 0.0])[idx] or 0.0)) + float(
                (c_rows.get("_withholding_tax_paid", [0.0, 0.0])[idx] or 0.0)
            )
        div_paid = c_rows.get("_dividends_paid", [None, None])[idx] if c_rows.get("_dividends_paid") else None

        output[year]["cashflow"] = {
            "n_cashflow_act": c_rows.get("n_cashflow_act", [None, None])[idx],
            "n_cashflow_inv_act": c_rows.get("n_cashflow_inv_act", [None, None])[idx],
            "n_cash_flows_fnc_act": c_rows.get("n_cash_flows_fnc_act", [None, None])[idx],
            "c_pay_to_staff": (
                float((employee_proxy or {}).get("employee_total"))
                if (employee_proxy or {}).get("employee_total") is not None
                else None
            ),
            "_c_pay_to_staff_is_proxy": (
                1.0 if (employee_proxy or {}).get("employee_total") is not None else None
            ),
            "_employee_benefit_total": (employee_proxy or {}).get("employee_total"),
            "_employee_direct_opex": (employee_proxy or {}).get("included_in_direct_opex"),
            "_employee_above_opex": (employee_proxy or {}).get("employee_above_opex"),
            "c_pay_acq_const_fiolta": capex,
            "depr_fa_coga_dpba": da_total,
            "c_paid_for_taxes": abs(tax_paid) if tax_paid is not None else None,
            "c_pay_dist_dpcp_int_exp": abs(div_paid) if div_paid is not None else None,
        }

        output[year]["dividend"] = {
            "dps_hkd": highlight.get("dps_hkd"),
            "divi_ratio": highlight.get("divi_ratio"),
        }
        output[year]["fina_indicator"] = {
            "roe_avg": highlight.get("roe_avg"),
            "debt_asset_ratio": highlight.get("debt_asset_ratio"),
            "net_profit_ratio": highlight.get("net_profit_ratio"),
            "current_ratio": highlight.get("current_ratio"),
        }
    return output


def _convert_record_to_hkd(year: int, record: dict) -> dict:
    currency = record["statement_currency"]
    fx_to_hkd = record["fx_to_hkd"] if currency == "RMB" else 1.0

    income_local = record["income"]
    balance_local = record["balance_sheet"]
    cashflow_local = record["cashflow"]

    income = {
        "ts_code": "",
        "end_date": f"{year}1231",
        "revenue": _scale_to_hkd_raw(income_local.get("revenue"), currency, fx_to_hkd),
        "oper_cost": _scale_to_hkd_raw(income_local.get("oper_cost"), currency, fx_to_hkd),
        "gross_profit": _scale_to_hkd_raw(income_local.get("gross_profit"), currency, fx_to_hkd),
        "admin_exp": _scale_to_hkd_raw(income_local.get("admin_exp"), currency, fx_to_hkd),
        "operate_profit": _scale_to_hkd_raw(income_local.get("operate_profit"), currency, fx_to_hkd),
        "invest_income": _scale_to_hkd_raw(income_local.get("invest_income"), currency, fx_to_hkd),
        "finance_exp": _scale_to_hkd_raw(income_local.get("finance_exp"), currency, fx_to_hkd),
        "total_profit": _scale_to_hkd_raw(income_local.get("total_profit"), currency, fx_to_hkd),
        "income_tax": _scale_to_hkd_raw(income_local.get("income_tax"), currency, fx_to_hkd),
        "n_income": _scale_to_hkd_raw(income_local.get("n_income"), currency, fx_to_hkd),
        "n_income_attr_p": _scale_to_hkd_raw(income_local.get("n_income_attr_p"), currency, fx_to_hkd),
        "minority_gain": _scale_to_hkd_raw(income_local.get("minority_gain"), currency, fx_to_hkd),
        "basic_eps": _eps_to_hkd(income_local.get("basic_eps_local_cents"), currency, fx_to_hkd),
        "diluted_eps": _eps_to_hkd(income_local.get("diluted_eps_local_cents"), currency, fx_to_hkd),
    }

    balance_sheet = {
        "ts_code": "",
        "end_date": f"{year}1231",
        "money_cap": _scale_to_hkd_raw(balance_local.get("money_cap"), currency, fx_to_hkd),
        "accounts_receiv": _scale_to_hkd_raw(balance_local.get("accounts_receiv"), currency, fx_to_hkd),
        "inventories": _scale_to_hkd_raw(balance_local.get("inventories"), currency, fx_to_hkd),
        "total_cur_assets": _scale_to_hkd_raw(balance_local.get("total_cur_assets"), currency, fx_to_hkd),
        "fix_assets": _scale_to_hkd_raw(balance_local.get("fix_assets"), currency, fx_to_hkd),
        "intang_assets": _scale_to_hkd_raw(balance_local.get("intang_assets"), currency, fx_to_hkd),
        "defer_tax_assets": _scale_to_hkd_raw(balance_local.get("defer_tax_assets"), currency, fx_to_hkd),
        "total_assets": _scale_to_hkd_raw(balance_local.get("total_assets"), currency, fx_to_hkd),
        "acct_payable": _scale_to_hkd_raw(balance_local.get("acct_payable"), currency, fx_to_hkd),
        "contract_liab": _scale_to_hkd_raw(balance_local.get("contract_liab"), currency, fx_to_hkd),
        "adv_receipts": _scale_to_hkd_raw(balance_local.get("adv_receipts"), currency, fx_to_hkd),
        "_temp_receipts": _scale_to_hkd_raw(balance_local.get("_temp_receipts"), currency, fx_to_hkd),
        "st_borr": _scale_to_hkd_raw(balance_local.get("st_borr"), currency, fx_to_hkd),
        "lt_borr": None,
        "total_cur_liab": _scale_to_hkd_raw(balance_local.get("total_cur_liab"), currency, fx_to_hkd),
        "defer_tax_liab": _scale_to_hkd_raw(balance_local.get("defer_tax_liab"), currency, fx_to_hkd),
        "total_liab": _scale_to_hkd_raw(balance_local.get("total_liab"), currency, fx_to_hkd),
        "total_hldr_eqy_exc_min_int": _scale_to_hkd_raw(balance_local.get("total_hldr_eqy_exc_min_int"), currency, fx_to_hkd),
        "minority_int": _scale_to_hkd_raw(balance_local.get("minority_int"), currency, fx_to_hkd),
    }

    cashflow = {
        "ts_code": "",
        "end_date": f"{year}1231",
        "n_cashflow_act": _scale_to_hkd_raw(cashflow_local.get("n_cashflow_act"), currency, fx_to_hkd),
        "n_cashflow_inv_act": _scale_to_hkd_raw(cashflow_local.get("n_cashflow_inv_act"), currency, fx_to_hkd),
        "n_cash_flows_fnc_act": _scale_to_hkd_raw(cashflow_local.get("n_cash_flows_fnc_act"), currency, fx_to_hkd),
        "c_pay_to_staff": _scale_to_hkd_raw(cashflow_local.get("c_pay_to_staff"), currency, fx_to_hkd),
        "_c_pay_to_staff_is_proxy": cashflow_local.get("_c_pay_to_staff_is_proxy"),
        "_employee_benefit_total": _scale_to_hkd_raw(cashflow_local.get("_employee_benefit_total"), currency, fx_to_hkd),
        "_employee_direct_opex": _scale_to_hkd_raw(cashflow_local.get("_employee_direct_opex"), currency, fx_to_hkd),
        "_employee_above_opex": _scale_to_hkd_raw(cashflow_local.get("_employee_above_opex"), currency, fx_to_hkd),
        "c_pay_acq_const_fiolta": _scale_to_hkd_raw(cashflow_local.get("c_pay_acq_const_fiolta"), currency, fx_to_hkd),
        "depr_fa_coga_dpba": _scale_to_hkd_raw(cashflow_local.get("depr_fa_coga_dpba"), currency, fx_to_hkd),
        "c_paid_for_taxes": _scale_to_hkd_raw(cashflow_local.get("c_paid_for_taxes"), currency, fx_to_hkd),
        "c_pay_dist_dpcp_int_exp": _scale_to_hkd_raw(cashflow_local.get("c_pay_dist_dpcp_int_exp"), currency, fx_to_hkd),
    }

    shares = None
    if income["n_income_attr_p"] and income["basic_eps"]:
        shares = income["n_income_attr_p"] / income["basic_eps"]

    gross_profit_ratio = _safe_div(income["gross_profit"], income["revenue"])
    if gross_profit_ratio is not None:
        gross_profit_ratio *= 100.0

    net_profit_ratio = _safe_div(income["n_income"], income["revenue"])
    if net_profit_ratio is not None:
        net_profit_ratio *= 100.0

    debt_asset_ratio = _safe_div(balance_sheet["total_liab"], balance_sheet["total_assets"])
    if debt_asset_ratio is not None:
        debt_asset_ratio *= 100.0

    dividend = {
        "ts_code": "",
        "end_date": f"{year}1231",
        "dps_hkd": record["dividend"].get("dps_hkd"),
        "divi_ratio": record["dividend"].get("divi_ratio"),
        "cash_div_tax": record["dividend"].get("dps_hkd"),
        "base_share": 1,
        "div_proc": "实施",
    }

    fina_indicator = {
        "ts_code": "",
        "end_date": f"{year}1231",
        "roe_avg": record["fina_indicator"].get("roe_avg"),
        "gross_profit_ratio": gross_profit_ratio,
        "net_profit_ratio": record["fina_indicator"].get("net_profit_ratio") or net_profit_ratio,
        "debt_asset_ratio": record["fina_indicator"].get("debt_asset_ratio") or debt_asset_ratio,
        "operate_income_yoy": None,
        "holder_profit_yoy": None,
        "current_ratio": record["fina_indicator"].get("current_ratio"),
        "bps": (
            balance_sheet["total_hldr_eqy_exc_min_int"] / shares
            if balance_sheet["total_hldr_eqy_exc_min_int"] is not None and shares
            else None
        ),
    }

    return {
        "end_date": f"{year}1231",
        "statement_currency": currency,
        "fx_to_hkd": fx_to_hkd,
        "source_pdf": record["source_pdf"],
        "source_report_year": record["source_report_year"],
        "income": income,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "dividend": dividend,
        "fina_indicator": fina_indicator,
    }


def build_fallback_dataset(output_dir: Path, ts_code: str) -> dict:
    pdfs = sorted(output_dir.glob("*.pdf"), key=_report_file_year)
    if not pdfs:
        return {"ts_code": ts_code, "income": [], "balance_sheet": [], "cashflow": [], "dividends": [], "fina_indicators": [], "records": []}

    by_year: dict[int, dict] = {}
    for pdf_path in pdfs:
        for year, candidate in _raw_year_records(pdf_path).items():
            existing = by_year.get(year)
            if existing is None or candidate["source_report_year"] > existing["source_report_year"]:
                by_year[year] = candidate

    selected_years = sorted(by_year.keys(), reverse=True)[:5]
    converted = [_convert_record_to_hkd(year, by_year[year]) for year in selected_years]

    income_rows = []
    balance_rows = []
    cashflow_rows = []
    dividend_rows = []
    indicator_rows = []
    governance_payload = {}

    for row in converted:
        income_row = dict(row["income"])
        balance_row = dict(row["balance_sheet"])
        cashflow_row = dict(row["cashflow"])
        dividend_row = dict(row["dividend"])
        indicator_row = dict(row["fina_indicator"])

        income_row["ts_code"] = ts_code
        balance_row["ts_code"] = ts_code
        cashflow_row["ts_code"] = ts_code
        dividend_row["ts_code"] = ts_code
        indicator_row["ts_code"] = ts_code

        income_rows.append(income_row)
        balance_rows.append(balance_row)
        cashflow_rows.append(cashflow_row)
        dividend_rows.append(dividend_row)
        indicator_rows.append(indicator_row)
        if not governance_payload:
            governance_payload = by_year[int(row["end_date"][:4])].get("governance", {})

    income_rows.sort(key=lambda x: x["end_date"], reverse=True)
    balance_rows.sort(key=lambda x: x["end_date"], reverse=True)
    cashflow_rows.sort(key=lambda x: x["end_date"], reverse=True)
    dividend_rows.sort(key=lambda x: x["end_date"], reverse=True)
    indicator_rows.sort(key=lambda x: x["end_date"], reverse=True)

    for idx, row in enumerate(indicator_rows):
        prev_income = income_rows[idx + 1] if idx + 1 < len(income_rows) else None
        curr_income = next((r for r in income_rows if r["end_date"] == row["end_date"]), None)
        if curr_income and prev_income:
            rev_growth = _safe_div(curr_income.get("revenue", 0.0) - prev_income.get("revenue", 0.0), prev_income.get("revenue"))
            np_growth = _safe_div(curr_income.get("n_income_attr_p", 0.0) - prev_income.get("n_income_attr_p", 0.0), prev_income.get("n_income_attr_p"))
            row["operate_income_yoy"] = rev_growth * 100.0 if rev_growth is not None else None
            row["holder_profit_yoy"] = np_growth * 100.0 if np_growth is not None else None

    records = [
        {
            "year": int(row["end_date"][:4]),
            "end_date": row["end_date"],
            "statement_currency": next(r["statement_currency"] for r in converted if r["end_date"] == row["end_date"]),
            "fx_to_hkd": next(r["fx_to_hkd"] for r in converted if r["end_date"] == row["end_date"]),
            "source_pdf": next(r["source_pdf"] for r in converted if r["end_date"] == row["end_date"]),
            "fields": {
                **{k: v for k, v in row.items() if k not in {"ts_code", "end_date"}},
                **{
                    k: v
                    for k, v in next(
                        b for b in balance_rows if b["end_date"] == row["end_date"]
                    ).items()
                    if k not in {"ts_code", "end_date"}
                },
                **{
                    k: v
                    for k, v in next(
                        c for c in cashflow_rows if c["end_date"] == row["end_date"]
                    ).items()
                    if k not in {"ts_code", "end_date"}
                },
            },
        }
        for row in income_rows
    ]

    return {
        "ts_code": ts_code,
        "currency": "HKD",
        "income": income_rows,
        "balance_sheet": balance_rows,
        "cashflow": cashflow_rows,
        "dividends": dividend_rows,
        "fina_indicators": indicator_rows,
        "holders": governance_payload.get("holders", []),
        "board_and_management": governance_payload.get("board_and_management", []),
        "audit": governance_payload.get("audit", {}),
        "repurchase": governance_payload.get("repurchase", {}),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract HK annual-report fallback financial data")
    parser.add_argument("--output-dir", required=True, help="Directory containing annual report PDFs")
    parser.add_argument("--code", required=True, help="Tushare code, e.g. 02669.HK")
    args = parser.parse_args()

    dataset = build_fallback_dataset(Path(args.output_dir), args.code)
    print(json.dumps(dataset, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
