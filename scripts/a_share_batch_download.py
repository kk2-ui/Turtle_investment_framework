#!/usr/bin/env python3
"""A-share batch financial data downloader — rate-limit-aware edition.

Mirrors hk_financials/ structure. Single-threaded, precise rate limiting
(150 calls/min max), incremental CSV writes every N stocks to bound memory.

Usage:
    python3 scripts/a_share_batch_download.py
    python3 scripts/a_share_batch_download.py --year-start 2020 --year-end 2025
    python3 scripts/a_share_batch_download.py --api income,balancesheet
    python3 scripts/a_share_batch_download.py --codes 600519.SH,000858.SZ
"""

import argparse
import os
import sys
import time

import pandas as pd
import tushare as ts

sys.path.insert(0, os.path.dirname(__file__))
from config import get_token, get_api_url

# ── Config ─────────────────────────────────────────────────────────────────

OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "a_financials")

# Rate limit: 150 calls/min → call_interval = 60/150 = 0.4s
# Use slightly more conservative 0.45s to be safe
CALL_INTERVAL = 0.45  # seconds between API calls
FLUSH_INTERVAL = 300  # flush to disk every N stocks
COOLDOWN_ON_EMPTY = 120  # seconds to wait if API returns empty
MAX_RETRIES = 3

AVAILABLE_APIS = {
    "income": {
        "func": "income",
        "fields": ("ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,"
                   "revenue,oper_cost,biz_tax_surchg,sell_exp,admin_exp,rd_exp,"
                   "fin_exp,assets_impair_loss,credit_impa_loss,"
                   "fv_value_chg_gain,invest_income,asset_disp_income,"
                   "operate_profit,non_oper_income,non_oper_exp,"
                   "total_profit,income_tax,n_income,n_income_attr_p,minority_gain,"
                   "basic_eps,diluted_eps"),
    },
    "balancesheet": {
        "func": "balancesheet",
        "fields": ("ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,"
                   "money_cap,trad_asset,notes_receiv,accounts_receiv,oth_receiv,"
                   "inventories,oth_cur_assets,total_cur_assets,"
                   "lt_eqt_invest,fix_assets,cip,intan_assets,goodwill,"
                   "total_assets,st_borr,notes_payable,acct_payable,"
                   "contract_liab,adv_receipts,non_cur_liab_due_1y,"
                   "oth_cur_liab,total_cur_liab,lt_borr,bond_payable,"
                   "total_liab,defer_tax_assets,defer_tax_liab,"
                   "total_hldr_eqy_exc_min_int,minority_int"),
    },
    "cashflow": {
        "func": "cashflow",
        "fields": ("ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,"
                   "n_cashflow_act,n_cashflow_inv_act,n_cash_flows_fnc_act,"
                   "c_pay_acq_const_fiolta,c_paid_for_taxes,"
                   "n_recp_disp_fiolta,c_recp_return_invest,"
                   "c_pay_dist_dpcp_int_exp,"
                   "depr_fa_coga_dpba,amort_intang_assets,lt_amort_deferred_exp"),
    },
    "fina_indicator": {
        "func": "fina_indicator",
        "fields": ("ts_code,ann_date,end_date,"
                   "roe,roe_waa,grossprofit_margin,netprofit_margin,"
                   "rd_exp,current_ratio,quick_ratio,assets_turn,debt_to_assets,"
                   "or_yoy,netprofit_yoy,ocfps,bps,profit_dedt,"
                   "ebitda,fcff,netdebt,interestdebt"),
    },
    "dividend": {
        "func": "dividend",
        "fields": ("ts_code,end_date,ann_date,div_proc,"
                   "stk_div,cash_div_tax,record_date,ex_date,base_share"),
    },
    "fina_audit": {
        "func": "fina_audit",
        "fields": ("ts_code,end_date,ann_date,audit_result,"
                   "audit_agency,audit_fees"),
    },
    "fina_mainbz": {
        "func": "fina_mainbz",
        "fields": ("ts_code,end_date,bz_item,bz_sales,bz_profit,bz_cost"),
        "params": {"type": "P"},
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────

def extract_year(end_date) -> str | None:
    s = str(end_date).strip()
    if len(s) == 8 and s.endswith("1231"):
        return s[:4]
    return None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ── CSV append writer (thread-safe for single-thread use) ──────────────────

class IncrementalWriter:
    """Write financial data incrementally to per-year CSV files."""

    def __init__(self, output_root: str, stock_df: pd.DataFrame):
        self.output_root = output_root
        self.stock_df = stock_df
        self._seen_years: set[str] = set()   # years with data written
        self._inited_years: set[str] = set()  # years where stock_basic was written

    def write_stock(self, year: str, api_key: str, df: pd.DataFrame) -> None:
        """Append one stock's annual data to the year's CSV."""
        self._seen_years.add(year)
        year_dir = os.path.join(self.output_root, f"a_financials_{year}")
        ensure_dir(year_dir)
        csv_path = os.path.join(year_dir, f"a_{api_key}_{year}.csv")

        file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 1
        df.to_csv(csv_path, mode="a", index=False, header=not file_exists)

    def write_stock_basic_for_year(self, year: str) -> None:
        """Write stock_basic CSV for a year (only once per year)."""
        if year in self._inited_years:
            return
        self._inited_years.add(year)

        year_dir = os.path.join(self.output_root, f"a_financials_{year}")
        ensure_dir(year_dir)
        csv_path = os.path.join(year_dir, f"a_stock_basic_{year}.csv")

        year_int = int(year)
        year_end = f"{year_int}1231"
        mask = self.stock_df["list_date"].astype(str) <= year_end
        st_df = self.stock_df[mask].copy()
        st_df.to_csv(csv_path, index=False)

    def get_seen_years(self) -> set[str]:
        return self._seen_years


# ── Main download logic ────────────────────────────────────────────────────

def download_all(token: str, api_url: str | None,
                 stock_df: pd.DataFrame, apis: list[str],
                 output_root: str) -> None:
    """Single-threaded, rate-limited download of all stocks."""

    pro = ts.pro_api(token=token, timeout=30)
    if api_url:
        pro._DataApi__token = token
        pro._DataApi__http_url = api_url

    writer = IncrementalWriter(output_root, stock_df)
    ts_codes = stock_df["ts_code"].tolist()
    total = len(ts_codes)
    n_apis = len(apis)

    # Stats
    stocks_done = 0
    stocks_with_data = 0
    calls_made = 0
    empty_streak = 0  # consecutive empty API responses
    start_time = time.time()
    last_flush = 0

    print(f"\n📊 {total} stocks × {n_apis} APIs = {total * n_apis:,} calls")
    print(f"   Rate limit: {60/CALL_INTERVAL:.0f} calls/min (interval={CALL_INTERVAL}s)")
    print(f"   Est. minimum time: {total * n_apis * CALL_INTERVAL / 60:.0f} min")
    print(f"   Flush: every {FLUSH_INTERVAL} stocks")
    print()

    for i, ts_code in enumerate(ts_codes):
        stock_has_data = False

        for api_key in apis:
            cfg = AVAILABLE_APIS[api_key]
            func = getattr(pro, cfg["func"])
            df = pd.DataFrame()

            extra_params = cfg.get("params", {})
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    df = func(ts_code=ts_code, limit=500, fields=cfg["fields"],
                              **extra_params)
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES:
                        print(f"  [retry {attempt}] {ts_code}/{api_key}: {e}")
                        time.sleep(5 * attempt)
                    else:
                        print(f"  [skip] {ts_code}/{api_key}: {e}")

            calls_made += 1

            # Check for rate limiting (empty DataFrame)
            if df is None or df.empty:
                empty_streak += 1
            else:
                empty_streak = 0
                if api_key == "dividend":
                    # Dividend: filter for implemented (completed) dividends only.
                    # Use end_date[:4] instead of extract_year() because dividend
                    # events include both interim (e.g. 20240630) and final (20241231).
                    df = df[df["div_proc"] == "实施"].copy()
                    df["_year"] = df["end_date"].astype(str).str[:4]
                    df = df[df["_year"].notna()]
                else:
                    # Financial statements: filter to annual reports only
                    df["_year"] = df["end_date"].apply(extract_year)
                    df = df[df["_year"].notna()]
                if not df.empty:
                    stock_has_data = True
                    for year, group in df.groupby("_year"):
                        clean = group.drop(columns=["_year"])
                        writer.write_stock(str(year), api_key, clean)

            # If many consecutive empty responses, we're probably rate-limited
            if empty_streak >= 20:
                print(f"\n  ⚠️  {empty_streak} consecutive empty responses — "
                      f"cooling down {COOLDOWN_ON_EMPTY}s...")
                time.sleep(COOLDOWN_ON_EMPTY)
                empty_streak = 0
                # Re-create API client
                pro = ts.pro_api(token=token, timeout=30)
                if api_url:
                    pro._DataApi__token = token
                    pro._DataApi__http_url = api_url

            # Rate limit
            time.sleep(CALL_INTERVAL)

        if stock_has_data:
            stocks_with_data += 1
        stocks_done += 1

        # Progress
        if stocks_done % 50 == 0 or stocks_done == total:
            elapsed = time.time() - start_time
            rate = stocks_done / elapsed if elapsed > 0 else 0
            calls_rate = calls_made / elapsed if elapsed > 0 else 0
            eta = (total - stocks_done) / rate if rate > 0 else 0
            print(f"  📈 {stocks_done}/{total} ({stocks_done/total*100:.1f}%) | "
                  f"{rate:.2f} stk/s | {calls_rate:.0f} calls/min | "
                  f"ETA {eta/60:.0f}m | data:{stocks_with_data}",
                  flush=True)

        # Flush stock_basic after each stock (first time per year only)
        # We don't know which years until data comes in, so do it lazily

        # Periodic stock_basic write for discovered years
        if stocks_done - last_flush >= FLUSH_INTERVAL:
            for year in writer.get_seen_years():
                writer.write_stock_basic_for_year(year)
            last_flush = stocks_done
            print(f"  💾 Flushed at {stocks_done} stocks", flush=True)

    # Final flush
    for year in writer.get_seen_years():
        writer.write_stock_basic_for_year(year)

    elapsed = time.time() - start_time
    print(f"\n✅ Download complete!")
    print(f"   Time: {elapsed/60:.0f} min")
    print(f"   Stocks with data: {stocks_with_data}/{total}")
    print(f"   API calls: {calls_made}")


# ── Post-processing: CSV → Parquet ─────────────────────────────────────────

def convert_to_parquet(output_root: str) -> None:
    """Convert all CSV files to Parquet format."""
    print("\n📦 Converting CSVs to Parquet...")
    converted = 0
    for root, dirs, files in os.walk(output_root):
        for f in files:
            if f.endswith(".csv"):
                csv_path = os.path.join(root, f)
                pq_path = csv_path.replace(".csv", ".parquet")
                try:
                    df = pd.read_csv(csv_path, low_memory=False)
                    df.to_parquet(pq_path, index=False)
                    converted += 1
                except Exception as e:
                    print(f"  ⚠️ {f}: {e}")
    print(f"  ✅ {converted} files converted")


# ── Summary ────────────────────────────────────────────────────────────────

def print_summary(output_root: str) -> None:
    """Print download summary."""
    year_dirs = sorted([d for d in os.listdir(output_root)
                        if os.path.isdir(os.path.join(output_root, d))])
    total_size = 0
    total_files = 0
    for root, dirs, files in os.walk(output_root):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))
            total_files += 1

    print(f"\n{'='*60}")
    print(f"📊 A-Share Financial Data Summary")
    print(f"   Year directories: {len(year_dirs)} ({year_dirs[0]} – {year_dirs[-1]})")
    print(f"   Total files: {total_files}")
    print(f"   Total size: {total_size / 1024 / 1024:.0f} MB")
    print(f"   Output: {output_root}")
    print(f"{'='*60}")


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="A-share financial data batch downloader (rate-limit-aware)")
    parser.add_argument("--api", type=str,
                        help="Comma-separated APIs: income,balancesheet,cashflow,fina_indicator")
    parser.add_argument("--codes", type=str,
                        help="Comma-separated stock codes (default: all A-share)")
    parser.add_argument("--output", type=str, default=OUTPUT_ROOT,
                        help="Output root directory")
    parser.add_argument("--interval", type=float, default=CALL_INTERVAL,
                        help=f"Seconds between API calls (default: {CALL_INTERVAL})")
    parser.add_argument("--no-parquet", action="store_true",
                        help="Skip Parquet conversion")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without downloading")
    return parser.parse_args()


def main():
    args = parse_args()
    apis = [a.strip() for a in args.api.split(",")] if args.api else list(AVAILABLE_APIS.keys())
    global CALL_INTERVAL
    CALL_INTERVAL = args.interval

    token = get_token()
    api_url = get_api_url()

    # ── Load stock list ─────────────────────────────────────────────────
    print("📋 Loading A-share stock list...", flush=True)
    pro = ts.pro_api(token=token, timeout=30)
    if api_url:
        pro._DataApi__token = token
        pro._DataApi__http_url = api_url

    # stock_basic with full field list - test each field
    stock_fields = ("ts_code,symbol,name,area,industry,market,"
                    "exchange,list_date,fullname,enname")
    df = pro.stock_basic(exchange="", list_status="L",
                         fields=stock_fields)
    if df is None or df.empty:
        print("❌ stock_basic returned empty — API may be rate-limited. Try again later.")
        sys.exit(1)

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",")]
        df = df[df["ts_code"].isin(codes)]

    n_stocks = len(df)
    n_calls = n_stocks * len(apis)
    print(f"   {n_stocks} stocks × {len(apis)} APIs = {n_calls:,} API calls")
    print(f"   Rate limit: {60/CALL_INTERVAL:.0f} calls/min")

    if args.dry_run:
        est_min = n_calls * CALL_INTERVAL / 60
        print(f"   Est. time: {est_min:.0f} min")
        print(f"   Output: {args.output}")
        return

    # ── Download ────────────────────────────────────────────────────────
    ensure_dir(args.output)
    download_all(token, api_url, df, apis, args.output)

    # ── Post-process ────────────────────────────────────────────────────
    if not args.no_parquet:
        convert_to_parquet(args.output)

    print_summary(args.output)


if __name__ == "__main__":
    main()
