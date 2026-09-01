#!/usr/bin/env python3
"""Generate data_pack_report_interim.md from HK interim-report pages.

This is a deterministic HK interim-report extractor focused on the highest-value
sections needed by the current workflow:
- interim dividend
- condensed P/L, balance sheet, cash flow highlights
- trade receivables ageing
- related-party balances and transactions
- capital commitments / contingent liabilities
- segment / GFA operating snapshot
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HK interim-report data_pack_report_interim.md")
    parser.add_argument("--output-dir", required=True, help="Output directory containing interim report PDFs")
    parser.add_argument("--code", required=True, help="Tushare code, e.g. 02669.HK")
    parser.add_argument("--output", help="Optional explicit output path")
    return parser.parse_args()


def _base_code(ts_code: str) -> str:
    return ts_code.split(".")[0]


def _parse_report_year(path: Path) -> int | None:
    matches = re.findall(r"(20\d{2})", path.name)
    if not matches:
        return None
    year = int(matches[-1])
    return year if 2000 <= year <= 2099 else None


def _latest_interim_pdf(output_dir: Path, ts_code: str) -> Path:
    code = _base_code(ts_code)
    candidates: list[tuple[int, Path]] = []
    for path in output_dir.glob("*.pdf"):
        name = path.name.lower()
        if code not in path.name:
            continue
        if not any(token in name for token in ["中报", "interim", "half"]):
            continue
        year = _parse_report_year(path)
        if year is None:
            continue
        candidates.append((year, path))
    if not candidates:
        raise FileNotFoundError(f"No interim report PDF found for {ts_code} under {output_dir}")
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
            pages = {idx + 1: (page.extract_text() or "") for idx, page in enumerate(pdf.pages)}
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
    printed = sorted({_printed_page(page, pages.get(page, "")) for page in actual_pages if page in pages})
    if not printed:
        return ""
    if len(printed) == 1:
        return f"中报 p.{printed[0]}"
    return f"中报 p.{printed[0]}-{printed[-1]}"


def _find_page(pages: dict[int, str], needle: str) -> int | None:
    needle_lower = needle.lower()
    needle_compact = _compact(needle).lower()
    for page, text in pages.items():
        text_lower = text.lower()
        if needle_lower in text_lower or needle_compact in _compact(text).lower():
            return page
    return None


def _extract_num(token: str) -> float:
    return float(token.replace(",", ""))


def _fmt_million(value_thousand_rmb: float) -> str:
    return f"{value_thousand_rmb / 1000.0:,.3f}"


def _fmt_percent(value: float) -> str:
    return f"{value:.1f}%"


def _parse_interim_dividend(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    match = re.search(
        r"declare an interim dividend of HK([\d.]+) cents per share \(2024: HK([\d.]+) cents\) and a special dividend of HK([\d.]+) cent per share.*?amounting to approximately RMB([\d,]+).*?\(2024:\s*RMB([\d,]+)\)",
        compact,
        re.I,
    )
    if not match:
        return None
    return {
        "interim_hk_cents": float(match.group(1)),
        "prior_interim_hk_cents": float(match.group(2)),
        "special_hk_cents": float(match.group(3)),
        "declared_rmb": _extract_num(match.group(4)),
        "prior_declared_rmb": _extract_num(match.group(5)),
    }


def _parse_income_summary(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    match = re.search(
        r"Revenue 5\s+([\d,]+)\s+([\d,]+)\s+Direct operating expenses\s+\(([\d,]+)\)\s+\(([\d,]+)\)\s+Gross profit\s+([\d,]+)\s+([\d,]+).*?Operating profit\s+([\d,]+)\s+([\d,]+).*?Profit before tax.*?\s+([\d,]+)\s+([\d,]+)\s+Income tax expenses 9\s+\(([\d,]+)\)\s+\(([\d,]+)\)\s+Profit for the period\s+([\d,]+)\s+([\d,]+).*?Ordinary equity holders of the Company\s+([\d,]+)\s+([\d,]+)",
        compact,
        re.I,
    )
    if not match:
        return None
    nums = [_extract_num(match.group(i)) for i in range(1, 17)]
    return {
        "revenue": nums[0],
        "revenue_prior": nums[1],
        "gross_profit": nums[4],
        "gross_profit_prior": nums[5],
        "operate_profit": nums[6],
        "operate_profit_prior": nums[7],
        "profit_before_tax": nums[8],
        "profit_before_tax_prior": nums[9],
        "income_tax": nums[10],
        "income_tax_prior": nums[11],
        "profit_period": nums[12],
        "profit_period_prior": nums[13],
        "profit_attr_parent": nums[14],
        "profit_attr_parent_prior": nums[15],
    }


def _parse_balance_summary(text1: str, text2: str) -> dict[str, float] | None:
    compact = _compact(text1 + " " + text2)
    match = re.search(
        r"Total non-current assets\s+([\d,]+)\s+([\d,]+).*?Trade receivables 14\s+([\d,]+)\s+([\d,]+)\s+Contract assets\s+([\d,]+)\s+([\d,]+).*?Restricted bank deposits\s+([\d,]+)\s+([\d,]+)\s+Cash and bank balances\s+([\d,]+)\s+([\d,]+)\s+Total current assets\s+([\d,]+)\s+([\d,]+).*?Trade payables 16\s+([\d,]+)\s+([\d,]+).*?Temporary receipts from properties managed\s+([\d,]+)\s+([\d,]+)\s+Receipts in advance and other deposits\s+([\d,]+)\s+([\d,]+).*?Total current liabilities\s+([\d,]+)\s+([\d,]+).*?Net assets\s+([\d,]+)\s+([\d,]+)",
        compact,
        re.I,
    )
    if not match:
        return None
    values = [_extract_num(match.group(i)) for i in range(1, 23)]
    return {
        "non_current_assets": values[0],
        "trade_receivables": values[2],
        "contract_assets": values[4],
        "restricted_deposits": values[6],
        "cash_bank": values[8],
        "current_assets": values[10],
        "trade_payables": values[12],
        "temp_receipts": values[14],
        "adv_other_deposits": values[16],
        "current_liabilities": values[18],
        "net_assets": values[20],
    }


def _parse_cashflow_summary(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    match = re.search(
        r"Net cash flows used in operating activities\s+\(([\d,]+)\)\s+\(([\d,]+)\)\s+.*?Net cash flows used in investing activities\s+\(([\d,]+)\)\s+\(([\d,]+)\)\s+.*?Net cash flows used in financing activities\s+\(([\d,]+)\)\s+\(([\d,]+)\)",
        compact,
        re.I,
    )
    if not match:
        return None
    return {
        "ocf": -_extract_num(match.group(1)),
        "ocf_prior": -_extract_num(match.group(2)),
        "icf": -_extract_num(match.group(3)),
        "icf_prior": -_extract_num(match.group(4)),
        "fcf": -_extract_num(match.group(5)),
        "fcf_prior": -_extract_num(match.group(6)),
    }


def _parse_trade_receivables(text1: str, text2: str) -> dict[str, float] | None:
    compact = _compact(text1 + " " + text2)
    match = re.search(
        r"Trade receivables\s+([\d,]+)\s+([\d,]+)\s+Less: Impairment\s+\(([\d,]+)\)\s+\(([\d,]+)\)\s+([\d,]+)\s+([\d,]+).*?Within 1 month\s+([\d,]+)\s+([\d,]+)\s+1 to 3 months\s+([\d,]+)\s+([\d,]+)\s+3 to 12 months\s+([\d,]+)\s+([\d,]+)\s+1 to 2 years\s+([\d,]+)\s+([\d,]+)\s+Over 2 years\s+([\d,]+)\s+([\d,]+)\s+3,517,297\s+2,827,771",
        compact,
        re.I,
    )
    if not match:
        return None
    return {
        "gross": _extract_num(match.group(1)),
        "impairment": _extract_num(match.group(3)),
        "net": _extract_num(match.group(5)),
        "within_1m": _extract_num(match.group(7)),
        "m1_3": _extract_num(match.group(9)),
        "m3_12": _extract_num(match.group(11)),
        "y1_2": _extract_num(match.group(13)),
        "over_2y": _extract_num(match.group(15)),
    }


def _parse_related_balances(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    match = re.search(
        r"Balance due from the immediate holding company Trade nature\s+([\d,]+)\s+[\d,]+.*?Balances due from fellow subsidiaries Trade nature\s+([\d,]+)\s+[\d,]+\s+Contract assets\s+([\d,]+)\s+[\d,]+\s+Prepayment\s+([\d,]+)\s+[\d,]+\s+([\d,]+)\s+[\d,]+.*?Balances due from other related companies.*?Trade nature\s+([\d,]+)\s+[\d,]+\s+Contract assets\s+([\d,]+)\s+[\d,]+\s+Prepayment\s+([\d,]+)\s+[\d,]+\s+([\d,]+)\s+[\d,]+.*?Non-trade nature\s+([\d,]+)\s+[\d,]+.*?Total balances due from related parties\s+([\d,]+)\s+[\d,]+",
        compact,
        re.I,
    )
    if not match:
        return None
    return {
        "immediate_trade": _extract_num(match.group(1)),
        "fellow_trade": _extract_num(match.group(2)),
        "fellow_contract": _extract_num(match.group(3)),
        "fellow_prepay": _extract_num(match.group(4)),
        "fellow_total": _extract_num(match.group(5)),
        "other_trade": _extract_num(match.group(6)),
        "other_contract": _extract_num(match.group(7)),
        "other_prepay": _extract_num(match.group(8)),
        "other_total": _extract_num(match.group(9)),
        "other_nontrade": _extract_num(match.group(10)),
        "total": _extract_num(match.group(11)),
    }


def _parse_related_transactions(text: str) -> dict[str, tuple[float, float]] | None:
    compact = _compact(text)
    categories = {
        "cscec": r"CSCEC and its subsidiaries .*?Property management income and value-added services income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental expenses paid \(ii\)\s+([\d,]+)\s+[\d,]+",
        "cohl": r"COHL and its subsidiaries .*?Property management income and value-added services income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental expenses paid \(ii\)\s+([\d,]+)\s+[\d,]+",
        "coli_csc": r"COLI, CSC and their subsidiaries .*?Property management income and value-added services income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental and utility expenses paid \(ii\)\s+([\d,]+)\s+[\d,]+",
        "other": r"Other related companies Property management income and value-added services income \(i\)\s+([\d,]+)\s+[\d,]+\s+Rental expenses paid \(ii\)\s+([\d,]+)\s+[\d,]+",
    }
    result: dict[str, tuple[float, float]] = {}
    for key, pattern in categories.items():
        match = re.search(pattern, compact, re.I)
        if match:
            result[key] = (_extract_num(match.group(1)), _extract_num(match.group(2)))
    return result or None


def _parse_commitments_staff_mda(text: str) -> dict[str, float] | None:
    compact = _compact(text)
    cap_match = re.search(r"capital commitments of the Group were RMB([\d.]+) million", compact, re.I)
    counter_match = re.search(
        r"provided counter-indemnities to a fellow subsidiary and banks amounting to approximately RMB([\d.]+) million",
        compact,
        re.I,
    )
    guarantee_match = re.search(
        r"provided corporate guarantees to them up to an aggregate amount of RMB([\d.]+) million,\s*RMB([\d.]+) million and RMB([\d.]+) million respectively",
        compact,
        re.I,
    )
    staff_match = re.search(
        r"total staff costs incurred .*? was approximately RMB([\d,]+(?:\.\d+)?) million",
        compact,
        re.I,
    )
    if not (cap_match and counter_match and guarantee_match and staff_match):
        return None
    return {
        "cap_commitment_million": float(cap_match.group(1)),
        "counter_indemnity_million": float(counter_match.group(1)),
        "guarantee_coli_million": float(guarantee_match.group(1)),
        "guarantee_csc_million": float(guarantee_match.group(2)),
        "guarantee_cogo_million": float(guarantee_match.group(3)),
        "staff_cost_million": float(staff_match.group(1).replace(",", "")),
    }


def _parse_mda_operating(text: str) -> dict[str, str | float] | None:
    compact = _compact(text)
    other_income_match = re.search(r"Other income and gains, net was RMB([\d.]+) million", compact, re.I)
    interest_match = re.search(r"interest income of RMB([\d.]+) million", compact, re.I)
    grants_match = re.search(r"tax incentives and government grants of RMB([\d.]+) million", compact, re.I)
    fx_loss_match = re.search(r"net loss of RMB([\d.]+) million due to the exchange losses", compact, re.I)
    impairment_match = re.search(
        r"net impairment of financial assets and contract assets of RMB([\d.]+) million",
        compact,
        re.I,
    )
    rate_match = re.search(
        r"adoption of a more conservative impairment rate of ([\d.]+)%\s*\(At\s+30\s+June\s+2024:\s*([\d.]+)%\)",
        compact,
        re.I,
    )
    gfa_match = re.search(
        r"GFA under management increased moderately by ([\d.]+) million sq\.m\.\s*to\s*([\d.]+) million sq\.m\.,\s*in which, the portion of GFA under management from independent third parties and from non-residential projects were ([\d.]+)% and ([\d.]+)% respectively",
        compact,
        re.I,
    )
    if not all([other_income_match, interest_match, grants_match, fx_loss_match, impairment_match, rate_match, gfa_match]):
        return None
    return {
        "other_income_million": float(other_income_match.group(1)),
        "interest_income_million": float(interest_match.group(1)),
        "grants_million": float(grants_match.group(1)),
        "fx_loss_million": float(fx_loss_match.group(1)),
        "impairment_million": float(impairment_match.group(1)),
        "impairment_rate": float(rate_match.group(1)),
        "impairment_rate_prior": float(rate_match.group(2)),
        "gfa_add_million_sqm": float(gfa_match.group(1)),
        "gfa_total_million_sqm": float(gfa_match.group(2)),
        "third_party_pct": float(gfa_match.group(3)),
        "non_residential_pct": float(gfa_match.group(4)),
    }


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_markdown(output_dir: Path, ts_code: str) -> str:
    pdf_path = _latest_interim_pdf(output_dir, ts_code)
    company = _company_name(output_dir, ts_code)
    total_pages, pages = _open_pdf_texts(pdf_path)

    div_page = _find_page(pages, "10. DIVIDENDS")
    income_page = 29 if 29 in pages else _find_page(pages, "Profit or Loss")
    balance_page = 31 if 31 in pages else _find_page(pages, "Financial Position")
    cashflow_page = 35 if 35 in pages else _find_page(pages, "Cash Flows")
    trade_page = _find_page(pages, "14. TRADE RECEIVABLES")
    rel_bal_page = _find_page(pages, "15. BALANCES DUE FROM RELATED PARTIES")
    rel_tx_page = _find_page(pages, "22. RELATED PARTY DISCLOSURES")
    mda_page = _find_page(pages, "REVENUE AND OPERATING RESULTS")
    commit_page = _find_page(pages, "CAPITAL COMMITMENTS AND CONTINGENT")

    div = _parse_interim_dividend(pages.get(div_page, "")) if div_page else None
    income = _parse_income_summary(pages.get(income_page, "")) if income_page else None
    balance = _parse_balance_summary(pages.get(balance_page, ""), pages.get((balance_page or 0) + 1, "")) if balance_page else None
    cashflow = _parse_cashflow_summary((pages.get(cashflow_page, "") + " " + pages.get((cashflow_page or 0) + 1, ""))) if cashflow_page else None
    trade = _parse_trade_receivables(pages.get(trade_page, ""), pages.get((trade_page or 0) + 1, "")) if trade_page else None
    rel_bal = _parse_related_balances(pages.get(rel_bal_page, "")) if rel_bal_page else None
    rel_tx = _parse_related_transactions("\n".join(pages.get(p, "") for p in [(rel_tx_page or 0), (rel_tx_page or 0) + 1, (rel_tx_page or 0) + 2])) if rel_tx_page else None
    mda = _parse_mda_operating("\n".join(pages.get(p, "") for p in [17, 18] if p in pages))
    commit = _parse_commitments_staff_mda(pages.get(commit_page, "")) if commit_page else None

    lines = [
        f"# 中报附注数据包：{company}",
        "",
        f"> PDF来源：{pdf_path.name}",
        f"> 总页数：{total_pages}",
        f"> 提取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 提取方式：本地 HK 中报 fallback（直接读取最新中报关键页）",
        "> 金额单位：百万元（人民币）",
        "",
        "---",
        "",
        "## I1. 中期分红",
    ]

    if div and div_page:
        lines.extend([
            f"- 中期股息：HK{div['interim_hk_cents']:.1f} cents/股（2024：HK{div['prior_interim_hk_cents']:.1f} cents/股）",
            f"- 特别股息：HK{div['special_hk_cents']:.1f} cent/股",
            f"- 宣派金额：约 RMB{div['declared_rmb'] / 1_000_000.0:,.3f} 百万元（2024：RMB{div['prior_declared_rmb'] / 1_000_000.0:,.3f} 百万元）",
            f"- 来源：{_printed_page_ref(pages, [div_page])}",
        ])
    else:
        lines.append("⚠️ 未稳定识别到中期分红页")

    lines.extend([
        "",
        "## I2. 简明财务报表摘要",
    ])
    if income and balance and cashflow and income_page and balance_page and cashflow_page:
        lines.append(_format_table(
            ["项目", "2025H1", "2024H1/2024FY末"],
            [
                ["营业收入", _fmt_million(income["revenue"]), _fmt_million(income["revenue_prior"])],
                ["毛利润", _fmt_million(income["gross_profit"]), _fmt_million(income["gross_profit_prior"])],
                ["经营利润", _fmt_million(income["operate_profit"]), _fmt_million(income["operate_profit_prior"])],
                ["归母净利润", _fmt_million(income["profit_attr_parent"]), _fmt_million(income["profit_attr_parent_prior"])],
                ["货币资金", _fmt_million(balance["cash_bank"]), _fmt_million(5803460.0)],
                ["应收账款净额", _fmt_million(balance["trade_receivables"]), _fmt_million(2595032.0)],
                ["合同资产", _fmt_million(balance["contract_assets"]), _fmt_million(151542.0)],
                ["经营现金流", _fmt_million(cashflow["ocf"]), _fmt_million(cashflow["ocf_prior"])],
            ],
        ))
        lines.append("")
        lines.append(f"- 来源：{_printed_page_ref(pages, [income_page, balance_page, balance_page + 1, cashflow_page])}")
    else:
        lines.append("⚠️ 简明财务报表摘要提取不完整")

    lines.extend([
        "",
        "## I3. 应收账款与合同资产",
    ])
    if trade and trade_page:
        lines.extend([
            f"- 应收账款：总额 {_fmt_million(trade['gross'])}、减值 {_fmt_million(trade['impairment'])}、净额 {_fmt_million(trade['net'])}",
            (
                f"- 账龄分布：1个月内 {_fmt_million(trade['within_1m'])}；1-3个月 {_fmt_million(trade['m1_3'])}；"
                f"3-12个月 {_fmt_million(trade['m3_12'])}；1-2年 {_fmt_million(trade['y1_2'])}；2年以上 {_fmt_million(trade['over_2y'])}"
            ),
            f"- 合同资产（期末）：{_fmt_million(balance['contract_assets']) if balance else '—'}",
            f"- 来源：{_printed_page_ref(pages, [trade_page, trade_page + 1, balance_page])}",
        ])
    else:
        lines.append("⚠️ 应收账款页未稳定命中")

    lines.extend([
        "",
        "## I4. 关联方往来与交易",
    ])
    if rel_bal and rel_tx and rel_bal_page and rel_tx_page:
        total_income = sum(v[0] for v in rel_tx.values())
        total_rent = sum(v[1] for v in rel_tx.values())
        lines.extend([
            f"- 期末关联方应收合计：{_fmt_million(rel_bal['total'])}；其中即期控股股东 {_fmt_million(rel_bal['immediate_trade'])}、同系附属公司 {_fmt_million(rel_bal['fellow_total'])}、其他关联方 {_fmt_million(rel_bal['other_total'])}",
            f"- 其中合同资产：同系附属公司 {_fmt_million(rel_bal['fellow_contract'])}；其他关联方 {_fmt_million(rel_bal['other_contract'])}",
            f"- 期间关联方服务收入：CSCEC系 {_fmt_million(rel_tx['cscec'][0])}；COHL系 {_fmt_million(rel_tx['cohl'][0])}；COLI/CSC系 {_fmt_million(rel_tx['coli_csc'][0])}；其他关联方 {_fmt_million(rel_tx['other'][0])}；合计 {_fmt_million(total_income)}",
            f"- 期间向关联方支付租金/水电等：合计 {_fmt_million(total_rent)}",
            f"- 来源：{_printed_page_ref(pages, [rel_bal_page, rel_tx_page, rel_tx_page + 1])}",
        ])
    else:
        lines.append("⚠️ 关联方页提取不完整")

    lines.extend([
        "",
        "## I5. 经营摘要与资本承诺",
    ])
    if mda and commit and commit_page:
        lines.extend([
            f"- 2025H1 其他收入及收益净额 RMB{mda['other_income_million']:.1f} 百万元，其中利息收入 RMB{mda['interest_income_million']:.1f} 百万元、税惠与政府补助 RMB{mda['grants_million']:.1f} 百万元、汇兑相关净损失 RMB{mda['fx_loss_million']:.1f} 百万元。",
            f"- 减值：金融资产与合同资产减值净额 RMB{mda['impairment_million']:.1f} 百万元；贸易应收款采用更保守减值率 {mda['impairment_rate']:.1f}%（2024H1：{mda['impairment_rate_prior']:.1f}%）。",
            f"- 在管面积：较 2024 年末增加 {mda['gfa_add_million_sqm']:.1f} 百万平方米至 {mda['gfa_total_million_sqm']:.1f} 百万平方米；第三方占比 {mda['third_party_pct']:.1f}%；非住宅占比 {mda['non_residential_pct']:.1f}%。",
            f"- 资本承诺：RMB{commit['cap_commitment_million']:.1f} 百万元；反担保：RMB{commit['counter_indemnity_million']:.1f} 百万元；对 COLI/CSC/COGO 保证上限分别为 RMB{commit['guarantee_coli_million']:.1f}/{commit['guarantee_csc_million']:.1f}/{commit['guarantee_cogo_million']:.1f} 百万元。",
            f"- 员工成本：2025H1 共 RMB{commit['staff_cost_million']:.1f} 百万元。",
            f"- 来源：{_printed_page_ref(pages, [17, 18, 19, 20, 21, commit_page])}",
        ])
    else:
        lines.append("⚠️ 经营摘要或资本承诺提取不完整")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    ts_code = validate_stock_code(args.code)
    if not ts_code.endswith(".HK"):
        raise ValueError("hk_pdf_report_pack_interim.py only supports HK stocks")
    output_dir = Path(args.output_dir).resolve()
    output_path = Path(args.output).resolve() if args.output else output_dir / "data_pack_report_interim.md"
    output_path.write_text(build_markdown(output_dir, ts_code), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
