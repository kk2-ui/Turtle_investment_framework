#!/usr/bin/env python3
"""migrate_a_share_to_db.py — 将 a_financials/ 批量 CSV 导入 stock_analysis.db

读取 a_financials/a_financials_YYYY/ 下的 CSV 文件，合并 income+balancesheet+
cashflow+fina_indicator，转换为百万元 RMB，走 observations→curation→annual_financials 管道。

Usage:
    python3 scripts/migrate_a_share_to_db.py              # 导入所有年份
    python3 scripts/migrate_a_share_to_db.py --year 2025  # 单年
    python3 scripts/migrate_a_share_to_db.py --dry-run    # 预览
"""

import argparse
import os
import sys
import sqlite3
import uuid

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from migrate_to_db import (write_observations_from_dict,
                           write_quality_findings, auto_curate, insert_evidence,
                           import_source, file_hash)
from db_gate import detect_and_fix_unit, validate_row, MONETARY_FIELDS

# Fix: use full uuid to avoid collisions (original uses only 8 hex chars)
def create_batch_safe(conn, ts_code: str, source_type: str, source_path: str = "",
                      fiscal_year: int = None) -> str:
    batch_id = f"batch_{uuid.uuid4().hex[:20]}"
    conn.execute("""INSERT INTO raw_import_batches (batch_id, ts_code, fiscal_year, source_type, source_path, source_hash, status)
        VALUES (?,?,?,?,?,?,?)""",
        (batch_id, ts_code, fiscal_year, source_type, source_path,
         file_hash(source_path) if source_path else "", "imported"))
    return batch_id

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
A_FINANCIALS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "a_financials")

# ── A-share CSV column → annual_financials field mapping ──────────────────

# income fields
INCOME_MAP = {
    "revenue": "revenue",
    "oper_cost": "oper_cost",
    "sell_exp": "sell_exp",
    "admin_exp": "admin_exp",
    "rd_exp": "rd_exp",
    "fin_exp": "finance_exp",
    "operate_profit": "operate_profit",
    "invest_income": "invest_income",
    "total_profit": "total_profit",
    "income_tax": "income_tax",
    "n_income": "n_income",
    "n_income_attr_p": "n_income_attr_p",
    "minority_gain": "minority_profit",
    "basic_eps": "eps",
    "diluted_eps": "diluted_eps",
}

# balance sheet fields
BALANCE_MAP = {
    "money_cap": "money_cap",
    "accounts_receiv": "accounts_receiv",
    "inventories": "inventories",
    "total_cur_assets": "total_cur_assets",
    "fix_assets": "fix_assets",
    "total_assets": "total_assets",
    "acct_payable": "acct_payable",
    "notes_payable": "notes_payable",
    "contract_liab": "contract_liab",
    "total_cur_liab": "total_cur_liab",
    "total_liab": "total_liab",
    "st_borr": "st_borr",
    "lt_borr": "lt_borr",
    "total_hldr_eqy_exc_min_int": "total_hldr_eqy_exc_min_int",
    "minority_int": "minority_int",
    "goodwill": "goodwill",
    "trad_asset": "trad_asset",
}

# cashflow fields
CASHFLOW_MAP = {
    "n_cashflow_act": "n_cashflow_act",
    "n_cashflow_inv_act": "n_cashflow_inv_act",
    "n_cash_flows_fnc_act": "n_cash_flows_fnc_act",
    "c_pay_acq_const_fiolta": "c_pay_acq_const_fiolta",
    "c_paid_for_taxes": "c_paid_for_taxes",
    "c_recp_return_invest": "c_recp_return_invest",
    "c_pay_dist_dpcp_int_exp": "dividends_paid",
    "depr_fa_coga_dpba": "depr_fa_coga_dpba",
    "amort_intang_assets": "amort_intang_assets",
}

# ── Helpers ────────────────────────────────────────────────────────────────

def safe_float(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def yuan_to_million(val) -> float | None:
    """Convert raw yuan to 百万元 RMB."""
    f = safe_float(val)
    if f is None:
        return None
    return round(f / 1_000_000, 2)


def load_year_csv(year: int) -> dict[str, pd.DataFrame]:
    """Load all CSV files for a given year. Returns {api_key: DataFrame}."""
    year_dir = os.path.join(A_FINANCIALS_DIR, f"a_financials_{year}")
    result = {}
    for api_key in ["income", "balancesheet", "cashflow", "fina_indicator",
                    "dividend", "fina_audit", "fina_mainbz", "stock_basic"]:
        csv_path = os.path.join(year_dir, f"a_{api_key}_{year}.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, low_memory=False)
                result[api_key] = df
            except Exception as e:
                print(f"  ⚠️ Failed to read {csv_path}: {e}")
    return result


def build_records(year: int, data: dict[str, pd.DataFrame]) -> list[dict]:
    """Merge income + balancesheet + cashflow + fina_indicator by ts_code.

    Returns list of records, each with fields from all statements.
    Values are already converted to 百万元 RMB (except EPS which stays as 元/股).
    """
    # Start with income as base (has the most stocks)
    income = data.get("income", pd.DataFrame())
    if income.empty:
        return []

    # Index other DataFrames by ts_code
    bs = data.get("balancesheet", pd.DataFrame())
    cf = data.get("cashflow", pd.DataFrame())
    fi = data.get("fina_indicator", pd.DataFrame())

    bs_idx = {}
    if not bs.empty:
        for _, row in bs.iterrows():
            code = row.get("ts_code", "")
            # Take first occurrence (consolidated report_type=1 preferred)
            if code not in bs_idx:
                bs_idx[code] = row

    cf_idx = {}
    if not cf.empty:
        for _, row in cf.iterrows():
            code = row.get("ts_code", "")
            if code not in cf_idx:
                cf_idx[code] = row

    fi_idx = {}
    if not fi.empty:
        for _, row in fi.iterrows():
            code = row.get("ts_code", "")
            if code not in fi_idx:
                fi_idx[code] = row

    # Dividend data: aggregate multiple dividend events per stock into annual DPS
    div_df = data.get("dividend", pd.DataFrame())
    div_lookup: dict[str, float] = {}
    if not div_df.empty:
        # Re-filter for implemented dividends (belt-and-suspenders)
        div_impl = div_df[div_df.get("div_proc", "实施") == "实施"]
        if not div_impl.empty:
            div_agg = div_impl.groupby("ts_code")["cash_div_tax"].sum()
            div_lookup = div_agg.to_dict()

    records = []
    for _, inc_row in income.iterrows():
        ts_code = str(inc_row.get("ts_code", ""))
        if not ts_code or pd.isna(ts_code):
            continue

        rec = {"end_date": f"{year}1231", "ts_code": ts_code, "fiscal_year": year}

        # Income statement fields (yuan → 百万元)
        for csv_col, db_field in INCOME_MAP.items():
            val = inc_row.get(csv_col)
            if db_field in ("eps", "diluted_eps"):
                rec[db_field] = safe_float(val)  # EPS stays as 元/股
            else:
                rec[db_field] = yuan_to_million(val)

        # Balance sheet fields
        bs_row = bs_idx.get(ts_code)
        if bs_row is not None:
            for csv_col, db_field in BALANCE_MAP.items():
                rec[db_field] = yuan_to_million(bs_row.get(csv_col))

        # Cashflow fields
        cf_row = cf_idx.get(ts_code)
        if cf_row is not None:
            for csv_col, db_field in CASHFLOW_MAP.items():
                val = cf_row.get(csv_col)
                if db_field == "c_pay_acq_const_fiolta":
                    # Capex stored as absolute value
                    f = yuan_to_million(val)
                    rec[db_field] = abs(f) if f is not None else None
                else:
                    rec[db_field] = yuan_to_million(val)
            # FCF = OCF - |Capex|
            ocf = rec.get("n_cashflow_act")
            capex = rec.get("c_pay_acq_const_fiolta")
            if ocf is not None and capex is not None:
                rec["fcf"] = round(ocf - abs(capex), 2)

        # D&A = depr + amort
        depr = rec.pop("depr_fa_coga_dpba", None)
        amort = rec.pop("amort_intang_assets", None)
        if depr is not None or amort is not None:
            rec["d_a"] = round((depr or 0) + (amort or 0), 2)

        # DPS from dividend API (per-share value, NOT converted to millions)
        dps_val = div_lookup.get(ts_code)
        if dps_val is not None and not pd.isna(dps_val):
            rec["dps"] = safe_float(dps_val)

        records.append(rec)

    return records


# ── Import logic ───────────────────────────────────────────────────────────

def import_a_share_year(conn, year: int, dry_run: bool) -> dict:
    """Import one year of A-share data. Returns stats dict."""
    print(f"\n{'='*50}")
    print(f"📥 A-share FY{year} → stock_analysis.db")
    print(f"{'='*50}")

    # Load CSV data
    print("  Loading CSV files...")
    data = load_year_csv(year)

    if "income" not in data:
        print("  ❌ No income data for this year")
        return {"year": year, "stocks": 0, "observations": 0, "curated": 0}

    # Build merged records
    records = build_records(year, data)
    if not records:
        print("  ❌ No records built")
        return {"year": year, "stocks": 0, "observations": 0, "curated": 0}

    print(f"  {len(records)} merged records")

    # Insert stock basic info
    stock_basic = data.get("stock_basic", pd.DataFrame())
    stocks_inserted = 0
    if not stock_basic.empty and not dry_run:
        for _, row in stock_basic.iterrows():
            ts_code = str(row.get("ts_code", ""))
            if not ts_code:
                continue
            name = row.get("name", "") or ""
            market = "A"
            industry = row.get("industry", "") or ""
            listing_date = str(row.get("list_date", "")) or None
            conn.execute("""INSERT OR REPLACE INTO stocks
                (ts_code, name_cn, market, industry, listing_date, currency, updated_at)
                VALUES (?,?,?,?,?,'RMB',datetime('now','localtime'))""",
                (ts_code, name if pd.notna(name) else "",
                 market, industry if pd.notna(industry) else "",
                 listing_date if listing_date and listing_date != "nan" else None))
        stocks_inserted = len(stock_basic)
        print(f"  {stocks_inserted} stocks inserted/updated")

    if dry_run:
        sample = records[0]
        print(f"\n  🔍 DRY RUN — sample record:")
        for k, v in sorted(sample.items()):
            print(f"    {k}: {v}")
        return {"year": year, "stocks": len(records), "observations": 0, "curated": 0}

    # Import using existing pipeline
    total_obs = 0
    total_curated = 0

    for rec in records:
        ts_code = rec["ts_code"]
        fy = rec["fiscal_year"]

        # Create batch
        batch_id = create_batch_safe(conn, ts_code, "tushare",
                                f"a_financials/a_financials_{year}/",
                                fiscal_year=fy)

        # Unit detection & fix
        fixed, unit_findings = detect_and_fix_unit(rec)
        write_quality_findings(conn, unit_findings, batch_id)

        # Row validation
        row_findings = validate_row(fixed, None)
        write_quality_findings(conn, row_findings, batch_id)

        # Write observations
        write_observations_from_dict(conn, batch_id, ts_code, fy, fixed,
                                     "tushare", priority=10)

        # Evidence
        obs_rows = conn.execute(
            "SELECT observation_id, field_name FROM financial_observations "
            "WHERE batch_id=? AND fiscal_year=?",
            (batch_id, fy)).fetchall()
        for o in obs_rows:
            conn.execute("""INSERT OR IGNORE INTO field_evidence
                (evidence_id, observation_id, document_path, normalization_rule, confidence)
                VALUES (?,?,?,?,?)""",
                (f"ev_{batch_id}_{o['field_name']}",
                 o["observation_id"],
                 f"a_financials/a_financials_{year}/",
                 "yuan/1e6→RMB_million",
                 0.5))

        total_obs += len(obs_rows)

        # Auto-curate
        n = auto_curate(conn, ts_code, fy)
        if n > 0:
            total_curated += 1

    conn.commit()
    print(f"  ✅ {total_obs} observations, {total_curated} stocks curated")

    return {
        "year": year,
        "stocks": len(records),
        "observations": total_obs,
        "curated": total_curated,
    }


# ── Main ───────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Import A-share CSV data into stock_analysis.db")
    p.add_argument("--year", type=int, help="Import specific year only")
    p.add_argument("--start-year", type=int, default=1994, help="Start year (default: 1994)")
    p.add_argument("--end-year", type=int, default=2025, help="End year (default: 2025)")
    p.add_argument("--dry-run", action="store_true", help="Preview without importing")
    p.add_argument("--db", type=str, default=DB_PATH, help="Database path")
    return p.parse_args()


def main():
    args = parse_args()
    db_path = args.db

    if not os.path.exists(os.path.dirname(db_path)):
        print(f"❌ Database directory not found: {os.path.dirname(db_path)}")
        return 1

    # Determine years
    if args.year:
        years = [args.year]
    else:
        years = list(range(args.start_year, args.end_year + 1))

    # Filter to existing year directories
    available = []
    for y in years:
        ydir = os.path.join(A_FINANCIALS_DIR, f"a_financials_{y}")
        if os.path.isdir(ydir):
            available.append(y)

    if not available:
        print(f"❌ No a_financials directories found in {A_FINANCIALS_DIR}")
        return 1

    print(f"📥 Importing {len(available)} years ({available[0]}-{available[-1]})")
    print(f"   Database: {db_path}")
    if args.dry_run:
        print(f"   Mode: DRY RUN")

    conn = None if args.dry_run else sqlite3.connect(db_path)
    if conn:
        conn.row_factory = sqlite3.Row

    totals = {"stocks": 0, "observations": 0, "curated": 0}

    for year in available:
        stats = import_a_share_year(conn, year, args.dry_run)
        totals["stocks"] += stats["stocks"]
        totals["observations"] += stats["observations"]
        totals["curated"] += stats["curated"]

    if conn:
        # Final stats
        obs_n = conn.execute("SELECT COUNT(*) FROM financial_observations").fetchone()[0]
        af_n = conn.execute("SELECT COUNT(*) FROM annual_financials").fetchone()[0]
        stock_n = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        conn.close()

        print(f"\n{'='*60}")
        print(f"✅ A-Share Import Complete!")
        print(f"   Years processed: {len(available)}")
        print(f"   Stocks in DB: {stock_n}")
        print(f"   Total observations: {obs_n}")
        print(f"   Annual financials rows: {af_n}")
        print(f"   Database: {db_path}")
        print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
