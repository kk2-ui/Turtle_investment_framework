#!/usr/bin/env python3
"""Bridge: populate hk_report_fallback.json from pdf_sections_*.json financials.

When Tushare HK endpoints return empty data, tushare_collector.py falls back to
reading hk_report_fallback.json. This script generates that file from the
financial data already extracted by pdf_preprocessor.py (Phase 2A) into
pdf_sections_YYYY.json.

Usage:
    python3 scripts/populate_hk_fallback.py --output output/00506_中国食品
    python3 scripts/populate_hk_fallback.py --output output/00506_中国食品 --code 00506.HK
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ── Field mappings: pdf_sections Chinese → hk_report_fallback English ──

# Which category each Chinese field belongs to
INCOME_FIELDS_CN = {
    "营业收入", "营业成本", "归母净利润",
    "投资收益", "政府补贴",
    "固定资产折旧", "无形资产摊销",
}

BALANCE_FIELDS_CN = {
    "货币资金", "应收账款", "存货", "固定资产",
    "资产总计", "应付账款", "合同负债", "归母权益",
    "流动资产合计", "流动负债合计", "负债合计",
    # v2.26: extended BS fields from STMT text extraction
    "少数股东权益", "商誉", "无形资产", "使用权资产",
    "租赁负债", "短期借款", "长期借款",
    "递延税项资产", "递延税项负债",
}

CASHFLOW_FIELDS_CN = {
    "经营活动CF", "投资活动CF", "筹资活动CF",
    "Capex", "处置固定资产收回",
}

# v2.26: P&L supplementary fields (ASSET_CORE)
INCOME_SUPP_FIELDS_CN = {
    "税前利润", "所得税", "少数股东损益", "毛利",
}

# v2.26: CF supplementary fields
CF_SUPP_FIELDS_CN = {
    "已付股息",
}

DIVIDEND_FIELDS_CN = {
    "股息总额", "每股股息", "股本",
}

# Direct name mapping
FIELD_NAME_MAP = {
    # income statement
    "营业收入": "revenue",
    "营业成本": "oper_cost",
    "归母净利润": "n_income_attr_p",
    "投资收益": "invest_income",
    "政府补贴": "gov_subsidy",
    # balance sheet
    "货币资金": "money_cap",
    "应收账款": "accounts_receiv",
    "存货": "inventories",
    "固定资产": "fix_assets",
    "资产总计": "total_assets",
    "应付账款": "acct_payable",
    "合同负债": "contract_liab",
    "归母权益": "total_hldr_eqy_exc_min_int",
    "流动资产合计": "total_cur_assets",
    "流动负债合计": "total_cur_liab",
    "负债合计": "total_liab",
    # cashflow
    "经营活动CF": "n_cashflow_act",
    "投资活动CF": "n_cashflow_inv_act",
    "筹资活动CF": "n_cash_flows_fnc_act",
    "Capex": "c_pay_acq_const_fiolta",
    "处置固定资产收回": "c_pay_dist_dpcp_int_exp",  # rough proxy
    # depreciation (goes to both income and cashflow notes)
    "固定资产折旧": "depr_fa_coga_dpba",
    "无形资产摊销": "amort_intang_assets",
    # dividend
    "股息总额": "cash_div_tax",
    "每股股息": "dps_hkd",
    "股本": "base_share",
    # v2.26: extended BS fields
    "少数股东权益": "minority_int",
    "商誉": "goodwill",
    "无形资产": "intang_assets",
    "使用权资产": "rou_assets",
    "租赁负债": "lease_liab",
    "短期借款": "st_borr",
    "长期借款": "lt_borr",
    "递延税项资产": "defer_tax_assets",
    "递延税项负债": "defer_tax_liab",
    # v2.26: P&L supplementary
    "税前利润": "total_profit",
    "所得税": "income_tax",
    "少数股东损益": "minority_gain",
    "毛利": "gross_profit",
    # v2.26: CF supplementary
    "已付股息": "dividends_paid",
}


def extract_year(filename: str) -> int | None:
    """Extract fiscal year from pdf_sections_YYYY.json filename."""
    m = re.search(r"pdf_sections_(\d{4})\.json", filename)
    return int(m.group(1)) if m else None


def load_pdf_sections(output_dir: str) -> tuple[dict[int, dict], dict[int, str]]:
    """Load all pdf_sections_YYYY.json, returning (financials, stmt_texts) keyed by fiscal year."""
    data: dict[int, dict] = {}
    stmts: dict[int, str] = {}
    out = Path(output_dir)
    for fp in sorted(out.glob("pdf_sections_*.json")):
        if "interim" in fp.name:
            continue
        year = extract_year(fp.name)
        if year is None:
            continue
        try:
            sections = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        fin = sections.get("financials", {})
        if isinstance(fin, dict) and fin:
            data[year] = fin
        stmt = sections.get("STMT", "") or ""
        if stmt:
            stmts[year] = stmt
    return data, stmts


def _v(raw_value, multiplier: float = 1_000_000.0) -> float | None:
    """Convert pdf_sections value (百万元) to raw units compatible with
    hk_report_fallback schema. Returns None for missing/zero values that
    should be omitted."""
    if raw_value is None:
        return None
    try:
        v = float(raw_value)
    except (TypeError, ValueError):
        return None
    if v == 0.0:
        return None
    return round(v * multiplier, 2)


def extract_from_stmt(stmt_text: str, field_cn: str) -> float | None:
    """Extract a value from STMT raw text using section-scoped regex.

    BS fields search within STATEMENT OF FINANCIAL POSITION section.
    IS fields search within STATEMENT OF PROFIT OR LOSS section.
    CF fields search within STATEMENT OF CASH FLOWS section.
    """
    patterns = {
        # BS fields — v2.26
        "少数股东权益": r"Non-controlling interests\s+非\s*控股權益\s+([\d,]{6,})",
        "商誉": r"Goodwill\s+商譽\s+([\d,]{6,})",
        "无形资产": r"Intangible assets\s+無形資產\s+\d+\s+([\d,]{6,})",
        "使用权资产": r"Right-of-use assets\s+使用權資產\s+\d+\s+([\d,]{6,})",
        "租赁负债": r"Lease liabilities\s+租賃負債\s+\d+\s+([\d,]{6,})",
        "短期借款": r"(?:Short-term borrowings|Bank borrowings)\s+.*?\s+([\d,]{5,})",
        "长期借款": r"(?:Long-term borrowings|非流動銀行貸款)\s+.*?\s+([\d,]{5,})",
        "递延税项资产": r"Deferred tax assets\s+遞延稅項資產\s+\d+\s+([\d,]{6,})",
        "递延税项负债": r"Deferred tax liabilities\s+遞延稅項負債\s+\d+\s+([\d,]{6,})",
        # IS fields — v2.26: P&L extraction from income statement
        "税前利润": r"Profit before (?:income )?tax\s+稅\s*前\s*溢\s*利\s+.*?([\d,]{6,})",
        "所得税": r"Income tax (?:expense|credit|benefit)\s+所\s*得\s*稅\s*(?:支出|開支)\s+.*?(\(?[\d,]{5,}\)?)",
        "少数股东损益": r"(?:Owners of the Company|本公司擁有人).*?\n\s*(?:–|－)\s*(?:Non-controlling|非控股).*?([\d,]{5,})",
        "毛利": r"Gross profit\s+毛利\s+([\d,]{6,})",
        # CF fields — v2.26
        "已付股息": r"(?:Dividends paid|已付股息|股息支付|股息分派)\s+.*?(\(?[\d,]{5,}\)?)",
    }
    pattern = patterns.get(field_cn)
    if not pattern:
        return None

    # Determine section scope
    IS_FIELDS = {'税前利润', '所得税', '少数股东损益', '毛利'}
    CF_FIELDS = {'已付股息'}

    section_marker = None
    section_len = 40000
    if field_cn in IS_FIELDS:
        section_marker = r'(?:STATEMENT OF PROFIT OR LOSS|CONSOLIDATED STATEMENT OF PROFIT|綜合損益表|合并利润表)'
        section_len = 25000
    elif field_cn in CF_FIELDS:
        section_marker = r'(?:STATEMENT OF CASH FLOWS|CONSOLIDATED STATEMENT OF CASH FLOWS|綜合現金流量表|合并现金流量表)'
        section_len = 30000
    else:
        section_marker = r'(?:STATEMENT OF FINANCIAL POSITION|綜合財務狀況表|CONSOLIDATED STATEMENT OF FINANCIAL POSITION)'
        section_len = 50000

    search_text = stmt_text
    marker_match = re.search(section_marker, stmt_text)
    if marker_match:
        sec_start = marker_match.start()
        sec_end = min(len(stmt_text), sec_start + section_len)
        search_text = stmt_text[sec_start:sec_end]

    match = re.search(pattern, search_text)
    if not match:
        # Fallback: search full text
        match = re.search(pattern, stmt_text)
    if match:
        try:
            raw = match.group(1).replace(",", "")
            # Handle parenthesized negative numbers: (443,827) → -443827
            is_neg = raw.startswith("(") and raw.endswith(")")
            if is_neg:
                raw = raw[1:-1]
            value = float(raw)
            if is_neg:
                value = -value
            return value
        except (ValueError, IndexError):
            pass
    return None


def build_fallback(
    output_dir: str,
    ts_code: str = "",
    currency: str = "RMB",
) -> dict:
    """Build hk_report_fallback.json payload from pdf_sections financials + STMT text."""
    yearly, stmts = load_pdf_sections(output_dir)
    if not yearly:
        print(f"[populate_hk_fallback] WARNING: No pdf_sections_*.json with financials found in {output_dir}",
              file=sys.stderr)
        return {}

    income_rows: list[dict] = []
    balance_rows: list[dict] = []
    cashflow_rows: list[dict] = []
    dividend_rows: list[dict] = []
    indicator_rows: list[dict] = []
    record_rows: list[dict] = []

    for year in sorted(yearly.keys()):
        fin = yearly[year]
        end_date = f"{year}1231"

        # ── Income ──
        inc: dict = {"ts_code": ts_code, "end_date": end_date}
        for cn, en in FIELD_NAME_MAP.items():
            if cn in INCOME_FIELDS_CN and cn in fin:
                inc[en] = _v(fin[cn])
        income_rows.append(inc)

        # ── Balance ──
        bal: dict = {"ts_code": ts_code, "end_date": end_date}
        stmt = stmts.get(year, "")
        for cn, en in FIELD_NAME_MAP.items():
            if cn in BALANCE_FIELDS_CN:
                if cn in fin:
                    bal[en] = _v(fin[cn])
                elif stmt:
                    # v2.26: fallback — extract from STMT raw text
                    # STMT text uses RMB'000; convert to raw 元 to match _v() output
                    raw = extract_from_stmt(stmt, cn)
                    if raw is not None:
                        bal[en] = round(raw * 1000, 2)  # 千元 → 元
        balance_rows.append(bal)

        # ── Cashflow ──
        cf: dict = {"ts_code": ts_code, "end_date": end_date}
        for cn, en in FIELD_NAME_MAP.items():
            if cn in CASHFLOW_FIELDS_CN and cn in fin:
                cf[en] = _v(fin[cn])
        # Also include depreciation/amortization in cashflow for D&A notes
        if "固定资产折旧" in fin:
            cf["depr_fa_coga_dpba"] = _v(fin["固定资产折旧"])
        if "无形资产摊销" in fin:
            cf["amort_intang_assets"] = _v(fin["无形资产摊销"])
        # v2.26: CF supplementary fields from STMT
        for cn, en in FIELD_NAME_MAP.items():
            if cn in CF_SUPP_FIELDS_CN:
                if cn in fin:
                    cf[en] = _v(fin[cn])
                elif stmt:
                    raw = extract_from_stmt(stmt, cn)
                    if raw is not None:
                        cf[en] = round(raw * 1000, 2)
        cashflow_rows.append(cf)

        # ── Income Supplementary (v2.26) ──
        # Append P&L fields to income record from financials + STMT extraction
        for cn, en in FIELD_NAME_MAP.items():
            if cn in INCOME_SUPP_FIELDS_CN:
                if cn in fin:
                    inc[en] = _v(fin[cn])
                elif stmt:
                    raw = extract_from_stmt(stmt, cn)
                    if raw is not None:
                        inc[en] = round(raw * 1000, 2)

        # ── Dividends ──
        div: dict = {"ts_code": ts_code, "end_date": end_date}
        if "每股股息" in fin and fin.get("每股股息", 0) != 0:
            div["dps_hkd"] = fin["每股股息"]
        if "股息总额" in fin:
            div["cash_div_tax"] = _v(fin["股息总额"])
        if "股本" in fin:
            div["base_share"] = _v(fin["股本"], multiplier=1.0)  # shares count, don't multiply
        if len(div) > 2:  # has actual dividend data beyond ts_code+end_date
            dividend_rows.append(div)

        # ── Fina Indicators (derived) ──
        ind: dict = {"ts_code": ts_code, "end_date": end_date}
        rev = fin.get("营业收入")
        np_attr = fin.get("归母净利润")
        equity = fin.get("归母权益")
        total_assets = fin.get("资产总计")
        total_liab = fin.get("负债合计")
        if rev and np_attr and rev > 0:
            ind["net_profit_ratio"] = round(np_attr / rev * 100, 2)
        if np_attr and equity and equity > 0:
            ind["roe_avg"] = round(np_attr / equity * 100, 1)
        if total_liab and total_assets and total_assets > 0:
            ind["debt_asset_ratio"] = round(total_liab / total_assets * 100, 1)
        indicator_rows.append(ind)

        # ── Records (metadata per year) ──
        rec: dict = {
            "year": year,
            "end_date": end_date,
            "statement_currency": currency,
            "source_pdf": f"pdf_sections_{year}.json",
            "fields": {FIELD_NAME_MAP.get(k, k): _v(v) for k, v in fin.items()
                       if k in FIELD_NAME_MAP},
        }
        record_rows.append(rec)

    # ── Assemble ──
    fallback: dict = {
        "ts_code": ts_code,
        "currency": currency,
        "income": income_rows,
        "balance_sheet": balance_rows,
        "cashflow": cashflow_rows,
        "dividends": dividend_rows,
        "fina_indicators": indicator_rows,
        "holders": [],
        "board_and_management": [],
        "audit": [],
        "repurchase": [],
        "records": record_rows,
    }
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate hk_report_fallback.json from pdf_sections_*.json financials"
    )
    parser.add_argument("--output", required=True,
                        help="Output directory (e.g. output/00506_中国食品)")
    parser.add_argument("--code", default="",
                        help="Stock code (e.g. 00506.HK)")
    parser.add_argument("--currency", default="RMB",
                        help="Statement currency (default: RMB)")
    args = parser.parse_args()

    out_dir = args.output
    if not os.path.isdir(out_dir):
        print(f"ERROR: output directory not found: {out_dir}", file=sys.stderr)
        sys.exit(1)

    # Auto-detect code from directory name if not provided
    ts_code = args.code
    if not ts_code:
        dirname = os.path.basename(out_dir.rstrip("/"))
        m = re.match(r"(\d{4,6})_", dirname)
        if m:
            digits = m.group(1)
            ts_code = f"{digits}.HK" if len(digits) == 5 else f"{digits}.SH"

    fallback = build_fallback(out_dir, ts_code, args.currency)
    if not fallback:
        sys.exit(1)

    # v2.26: Write STMT-extracted BS fields back to pdf_sections financials
    # so data_gate.py L1b ASSET can see them.
    records = fallback.get("records", [])
    enriched_count = 0
    for rec in records:
        year = rec.get("year")
        if not year:
            continue
        fp = Path(out_dir) / f"pdf_sections_{year}.json"
        if not fp.exists():
            continue
        try:
            sections = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        fin = sections.get("financials", {})
        if not isinstance(fin, dict):
            fin = {}
        # Map back from English hk_report_fallback fields → Chinese financials keys
        ALL_CN_FIELDS = BALANCE_FIELDS_CN | INCOME_SUPP_FIELDS_CN | CF_SUPP_FIELDS_CN
        REVERSE_MAP = {v: k for k, v in FIELD_NAME_MAP.items() if k in ALL_CN_FIELDS}

        # Write back BS fields
        bs_rec = None
        for b in fallback.get("balance_sheet", []):
            if b.get("end_date", "").startswith(str(year)):
                bs_rec = b
                break
        if bs_rec:
            for en_key, cn_key in REVERSE_MAP.items():
                if cn_key in BALANCE_FIELDS_CN and cn_key not in fin and en_key in bs_rec and bs_rec[en_key] is not None:
                    raw = bs_rec[en_key]
                    if isinstance(raw, (int, float)) and raw > 0:
                        fin[cn_key] = round(raw / 1_000_000, 2)
                        enriched_count += 1

        # Write back IS supplementary fields
        inc_rec = None
        for inc in fallback.get("income", []):
            if inc.get("end_date", "").startswith(str(year)):
                inc_rec = inc
                break
        if inc_rec:
            for en_key, cn_key in REVERSE_MAP.items():
                if cn_key in INCOME_SUPP_FIELDS_CN and cn_key not in fin and en_key in inc_rec and inc_rec[en_key] is not None:
                    raw = inc_rec[en_key]
                    if isinstance(raw, (int, float)) and raw > 0:
                        fin[cn_key] = round(raw / 1_000_000, 2)
                        enriched_count += 1

        # Write back CF supplementary fields
        cf_rec = None
        for c in fallback.get("cashflow", []):
            if c.get("end_date", "").startswith(str(year)):
                cf_rec = c
                break
        if cf_rec:
            for en_key, cn_key in REVERSE_MAP.items():
                if cn_key in CF_SUPP_FIELDS_CN and cn_key not in fin and en_key in cf_rec and cf_rec[en_key] is not None:
                    raw = cf_rec[en_key]
                    if isinstance(raw, (int, float)) and raw > 0:
                        fin[cn_key] = round(raw / 1_000_000, 2)
                        enriched_count += 1

        if bs_rec or inc_rec or cf_rec:
            sections["financials"] = fin
            fp.write_text(json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8")

    if enriched_count > 0:
        print(f"  Enriched {enriched_count} BS fields across pdf_sections_*.json")

    out_path = os.path.join(out_dir, "hk_report_fallback.json")
    # If existing file, merge rather than overwrite (preserve holders/board/audit etc.)
    existing = {}
    if os.path.exists(out_path):
        try:
            existing = json.loads(Path(out_path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Merge: new financial data overwrites, but preserve non-financial sections from existing
    for key in ("holders", "board_and_management", "audit", "repurchase"):
        if key in existing and existing[key] and (not fallback.get(key)):
            fallback[key] = existing[key]

    Path(out_path).write_text(
        json.dumps(fallback, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    n_years = len(fallback.get("records", []))
    n_income = len(fallback.get("income", []))
    print(f"[populate_hk_fallback] Written {out_path}")
    print(f"  {n_years} years, {n_income} income records, "
          f"{len(fallback.get('balance_sheet',[]))} balance records, "
          f"{len(fallback.get('cashflow',[]))} cashflow records")


if __name__ == "__main__":
    main()
