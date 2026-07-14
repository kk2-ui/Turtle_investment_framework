#!/usr/bin/env python3
"""import_hk_bulk.py — 批量导入港股 Tushare CSV 数据到 stock_analysis.db

从 hk_financials/ 目录读取 2005-2026 年度 CSV 数据，将 LONG 格式的
income/balancesheet/cashflow 表 Pivot 为 WIDE 格式，与 fina_indicator
合并后，通过 migrate_to_db 的 import_source() 管道写入数据库。

Usage:
    python3 scripts/import_hk_bulk.py --code 00700.HK                  # 导入单只
    python3 scripts/import_hk_bulk.py --code 00700.HK --code 09988.HK  # 导入多只
    python3 scripts/import_hk_bulk.py --code 00700.HK --year 2015-2025 # 指定年份
    python3 scripts/import_hk_bulk.py --code 00700.HK --annual-only    # 仅年度数据
    python3 scripts/import_hk_bulk.py --code 00700.HK --dry-run        # 预览模式
    python3 scripts/import_hk_bulk.py --stocks-only                    # 仅导入 stocks 表
    python3 scripts/import_hk_bulk.py --list-stocks 00700.HK           # 列出某股票在各年的数据
"""

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from migrate_to_db import (
    create_batch,
    write_observations_from_dict,
    import_source,
    auto_curate,
    safe_float,
)
from db_gate import QualityFinding, CORE_FIELDS, MONETARY_FIELDS, detect_and_fix_unit, validate_row
from tushare_modules.constants import (
    HK_INCOME_NAME_TO_FIELD,
    HK_BS_NAME_TO_FIELD,
    HK_CF_NAME_TO_FIELD,
    FI_COLUMN_TO_FIELD,
)

# ── Config ──

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "hk_financials")
SOURCE_TYPE = "tushare_hk_bulk"
SOURCE_PRIORITY = 15  # Between tushare(10) and tushare_hk_fallback(20)

# Fields that are percentages (no /1e6 conversion)
PCT_FIELDS = {"gross_margin", "roe", "roa", "debt_ratio", "tax_rate", "ocf_to_sales",
              "revenue_yoy", "np_yoy", "gp_yoy", "current_ratio"}

# Fields that are per-share values (no /1e6 conversion)
PER_SHARE_FIELDS = {"eps", "eps_diluted", "dps", "ocf_per_share",
                    "operate_income_per_share", "book_value_per_share"}


# ── Helpers ──

def to_millions(value, field_name=""):
    """Convert yuan to millions for monetary fields. Returns None for non-numeric input."""
    v = safe_float(value)
    if v is None:
        return None
    if field_name in PCT_FIELDS or field_name in PER_SHARE_FIELDS:
        return round(v, 4)
    if abs(v) < 1e-6:
        return 0.0
    return round(v / 1_000_000, 2)


def infer_fiscal_year(end_date: str, fiscal_month: Optional[int] = None) -> int:
    """Determine fiscal year from end_date.

    Most HK companies have December fiscal year-end.
    For non-December companies, use fiscal_month to adjust.

    Examples:
        20241231, fiscal_month=12 → 2024
        20250331, fiscal_month=3  → 2024 (FY2024 ending Mar 2025)
    """
    if not end_date or len(end_date) < 8:
        return 0
    y = int(end_date[:4])
    if fiscal_month is None:
        return y  # default: calendar year = fiscal year
    m = int(end_date[4:6])
    if m == fiscal_month:
        return y
    elif m < fiscal_month:
        return y - 1
    return y


def is_year_end(end_date: str, fiscal_month: int = 12) -> bool:
    """Check if end_date represents a fiscal year-end (not interim)."""
    if not end_date or len(end_date) < 8:
        return False
    m = int(end_date[4:6])
    return m == fiscal_month


def resolve_fiscal_month(fi_rows: list, ts_code: str) -> int:
    """Determine fiscal month from fina_indicator's fiscal_year field for a stock.

    fi_fiscal_year is a float like 12.0 (December), 3.0 (March), etc.
    Returns 12 as default.
    """
    if fi_rows:
        fy_vals = [safe_float(r.get("fiscal_year")) for r in fi_rows if r.get("fiscal_year")]
        fy_vals = [v for v in fy_vals if v is not None]
        if fy_vals:
            # Use the most common value
            most_common = Counter(fy_vals).most_common(1)[0][0]
            return int(most_common)
    return 12  # default


# ── Pivot & Mapping ──

def pivot_long_to_wide(rows: list, mapping: dict) -> dict:
    """Convert LONG format rows to WIDE format, grouped by end_date.

    Input: [{ts_code, name, end_date, ind_name, ind_value}, ...]
    Output: {end_date: {field1: value1_millions, field2: value2_millions, ...}}

    Only keeps fields that appear in the mapping.
    """
    result = defaultdict(dict)
    unmapped = Counter()

    for r in rows:
        ind_name = r.get("ind_name", "").strip()
        end_date = r.get("end_date", "").strip()
        raw_value = r.get("ind_value", "").strip()

        if not ind_name or not end_date or not raw_value:
            continue

        field = mapping.get(ind_name)
        if not field:
            unmapped[ind_name] += 1
            continue

        try:
            val = float(raw_value)
        except (ValueError, TypeError):
            continue

        # Convert to millions (except per-share and pct fields)
        val_m = to_millions(val, field)
        if val_m is not None:
            result[end_date][field] = val_m

    return dict(result), unmapped


def map_fina_indicator(fi_rows: list) -> dict:
    """Map fina_indicator WIDE rows to DB field names.

    Input: list of CSV dict rows
    Output: {end_date: {field1: value1_millions, field2: ..., _report_type: ..., _fiscal_year: ...}}
    """
    result = {}
    for r in fi_rows:
        end_date = r.get("end_date", "").strip()
        if not end_date:
            continue

        record = {
            "_report_type": r.get("report_type", "").strip(),
            "_fiscal_year": safe_float(r.get("fiscal_year")),
            "_currency": r.get("currency", "").strip(),
        }

        for csv_col, db_field in FI_COLUMN_TO_FIELD.items():
            raw = r.get(csv_col, "").strip()
            if raw:
                val = safe_float(raw)
                if val is not None:
                    # DPS: prefer dps_hkd_ly (last year's full-year dividend) for annual data
                    # Store both, let curation pick by priority
                    val_m = to_millions(val, db_field)
                    if val_m is not None:
                        record[db_field] = val_m

        result[end_date] = record

    return result


# ── Data Loading ──

def load_csv_rows(data_dir: str, year: int, table: str) -> list:
    """Load all rows from a specific year/table CSV."""
    csv_path = os.path.join(data_dir, f"hk_financials_{year}", f"hk_{table}_{year}.csv")
    if not os.path.exists(csv_path):
        return []
    if os.path.getsize(csv_path) < 100:  # empty file
        return []

    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_stock_data(data_dir: str, ts_code: str, year: int):
    """Load all financial data for one stock in one year.

    Returns:
        income_by_date: {end_date: {field: value, ...}}
        bs_by_date:     {end_date: {field: value, ...}}
        cf_by_date:     {end_date: {field: value, ...}}
        fi_by_date:     {end_date: {field: value, ...}}
        unmapped_all:   Counter of unmapped ind_names
        fiscal_month:   inferred fiscal year-end month
    """
    unmapped_all = Counter()

    # Load and pivot income
    inc_rows = load_csv_rows(data_dir, year, "income")
    inc_stock = [r for r in inc_rows if r.get("ts_code", "").strip() == ts_code]
    inc_by_date, inc_unmapped = pivot_long_to_wide(inc_stock, HK_INCOME_NAME_TO_FIELD)
    unmapped_all.update(inc_unmapped)

    # Load and pivot balance sheet
    bs_rows = load_csv_rows(data_dir, year, "balancesheet")
    bs_stock = [r for r in bs_rows if r.get("ts_code", "").strip() == ts_code]
    bs_by_date, bs_unmapped = pivot_long_to_wide(bs_stock, HK_BS_NAME_TO_FIELD)
    unmapped_all.update(bs_unmapped)

    # Load and pivot cash flow
    cf_rows = load_csv_rows(data_dir, year, "cashflow")
    cf_stock = [r for r in cf_rows if r.get("ts_code", "").strip() == ts_code]
    cf_by_date, cf_unmapped = pivot_long_to_wide(cf_stock, HK_CF_NAME_TO_FIELD)
    unmapped_all.update(cf_unmapped)

    # Load and map fina_indicator
    fi_rows = load_csv_rows(data_dir, year, "fina_indicator")
    fi_stock = [r for r in fi_rows if r.get("ts_code", "").strip() == ts_code]
    fi_by_date = map_fina_indicator(fi_stock)

    # Determine fiscal month
    fiscal_month = resolve_fiscal_month(fi_stock, ts_code)

    return inc_by_date, bs_by_date, cf_by_date, fi_by_date, unmapped_all, fiscal_month


# ── Record Building ──

def build_records(inc_by_date, bs_by_date, cf_by_date, fi_by_date,
                  ts_code: str, annual_only: bool, fiscal_month: int) -> list:
    """Merge income, BS, CF, and FI data into unified records.

    Priority for overlapping fields: income/BS/CF > fina_indicator.
    """
    # Collect all end_dates
    all_dates = set()
    all_dates.update(inc_by_date.keys())
    all_dates.update(bs_by_date.keys())
    all_dates.update(cf_by_date.keys())
    all_dates.update(fi_by_date.keys())

    # Build interim DPS lookup: calendar_year → interim_dps_hkd (for annual DPS correction)
    interim_dps = {}
    for end_date in sorted(all_dates):
        if is_year_end(end_date, fiscal_month):
            continue  # only interested in non-year-end (interim) dates
        fi_data = fi_by_date.get(end_date, {})
        cal_year = int(end_date[:4])  # calendar year matches annual report year
        dps_val = fi_data.get("dps")
        if dps_val is not None:
            interim_dps[cal_year] = interim_dps.get(cal_year, 0) + dps_val

    records = []
    for end_date in sorted(all_dates):
        if annual_only and not is_year_end(end_date, fiscal_month):
            continue

        fy = infer_fiscal_year(end_date, fiscal_month)
        cal_year = int(end_date[:4])

        # Start with FI data (lower priority)
        record = {"end_date": end_date, "fiscal_year": fy, "ts_code": ts_code}
        fi_data = fi_by_date.get(end_date, {})
        report_type = fi_data.pop("_report_type", "")
        fi_fiscal_year = fi_data.pop("_fiscal_year", None)

        # Override fiscal_year if FI provides it
        if fi_fiscal_year is not None:
            record["fiscal_year"] = int(fi_fiscal_year)

        record["report_type"] = report_type if report_type else ("annual" if is_year_end(end_date, fiscal_month) else "interim")

        # Add FI fields first (will be overridden by income/BS/CF)
        for field, value in fi_data.items():
            record[field] = value

        # Fix DPS: add interim DPS to annual DPS (HK stocks with semi-annual dividends)
        if cal_year in interim_dps:
            annual_dps = record.get("dps") or 0
            record["dps"] = round(annual_dps + interim_dps[cal_year], 4)

        # Override with income data
        inc_data = inc_by_date.get(end_date, {})
        for field, value in inc_data.items():
            record[field] = value

        # Override with BS data
        bs_data = bs_by_date.get(end_date, {})
        for field, value in bs_data.items():
            record[field] = value

        # Override with CF data
        cf_data = cf_by_date.get(end_date, {})
        for field, value in cf_data.items():
            record[field] = value

        # Compute FCF
        ocf = record.get("n_cashflow_act")
        capex = record.get("c_pay_acq_const_fiolta")
        if ocf is not None and capex is not None:
            record["fcf"] = round(abs(ocf) - abs(capex), 2)

        # Fallback: d_a from income may be missing (HK companies often include
        # D&A within operating expenses). Use CF's d_a_cf as fallback.
        if not record.get("d_a") and record.get("d_a_cf"):
            record["d_a"] = record["d_a_cf"]

        # Compute gross_margin if missing
        if not record.get("gross_margin"):
            rev = record.get("revenue")
            gp = record.get("gross_profit")
            if rev and gp and rev > 0:
                record["gross_margin"] = round(gp / rev * 100, 2)

        records.append(record)

    return records


# ── Stock Import ──

def import_stock(conn, ts_code: str, data_dir: str, years: list = None,
                 annual_only: bool = True, dry_run: bool = False):
    """Import a single stock's data across all available years."""
    if years is None:
        years = list(range(2005, 2027))

    total_records = 0
    total_unmapped = Counter()
    fiscal_month = 12  # default, will be updated from FI data

    for year in years:
        # Load data for this stock in this year
        inc_by_date, bs_by_date, cf_by_date, fi_by_date, unmapped, fm = \
            load_stock_data(data_dir, ts_code, year)

        total_unmapped.update(unmapped)
        if fm != 12:
            fiscal_month = fm  # use non-default fiscal month if found

        if not any([inc_by_date, bs_by_date, cf_by_date, fi_by_date]):
            continue  # stock not in this year

        # Build merged records
        records = build_records(inc_by_date, bs_by_date, cf_by_date, fi_by_date,
                                ts_code, annual_only, fiscal_month)

        if not records:
            continue

        # Print year summary
        n_annual = sum(1 for r in records if is_year_end(r["end_date"], fiscal_month))
        if not dry_run:
            print(f"  {year}: {len(records)} records ({n_annual} annual)", end="")
        else:
            print(f"  {year}: {len(records)} records ({n_annual} annual) [DRY RUN]", end="")

        # Feed to import_source pipeline
        if not dry_run:
            source_path = os.path.join(data_dir, f"hk_financials_{year}")
            n = import_source(conn, ts_code, SOURCE_TYPE, source_path,
                              records, dry_run=False, priority=SOURCE_PRIORITY)
            print(f" → {n} observations")
        else:
            # Dry run: show what would be imported
            for rec in records[:2]:  # first 2 records as sample
                fy = rec.get("fiscal_year", "?")
                rev = rec.get("revenue", "?")
                np_val = rec.get("n_income_attr_p", "?")
                print(f"    FY{fy}: revenue={rev}, n_income={np_val}")
            if len(records) > 2:
                print(f"    ... and {len(records)-2} more records")
            print()

        total_records += len(records)

    # Report unmapped indicators
    if total_unmapped:
        print(f"\n  ⚠️  Unmapped indicators (top 10):")
        for name, count in total_unmapped.most_common(10):
            print(f"    {name}: {count}×")

    return total_records


# ── Stocks Table ──

def import_stocks_table(conn, data_dir: str, dry_run: bool = False):
    """Import all stocks from hk_basic_*.csv across all years into the stocks table."""
    all_stocks = {}  # ts_code → {name_cn, name_en, market, listing_date, currency}

    for year in range(2005, 2027):
        rows = load_csv_rows(data_dir, year, "basic")
        for r in rows:
            code = r.get("ts_code", "").strip()
            if not code:
                continue
            # Use the most recent year's data
            all_stocks[code] = {
                "ts_code": code,
                "name_cn": r.get("name", "").strip(),
                "name_en": r.get("enname", "").strip(),
                "market": "HK",
                "listing_date": r.get("list_date", "").strip() or None,
                "currency": r.get("curr_type", "HKD").strip(),
            }

    if dry_run:
        print(f"Would import {len(all_stocks)} stocks into stocks table")
        # Show sample
        for code in sorted(all_stocks)[:5]:
            s = all_stocks[code]
            print(f"  {code} | {s['name_cn']} | {s['name_en']} | {s['currency']}")
        return 0

    count = 0
    for code, s in all_stocks.items():
        conn.execute("""INSERT OR REPLACE INTO stocks
            (ts_code, name_cn, name_en, market, listing_date, currency, updated_at)
            VALUES (?,?,?,?,?,?,datetime('now','localtime'))""",
            (s["ts_code"], s["name_cn"], s["name_en"], s["market"],
             s["listing_date"], s["currency"]))
        count += 1

    print(f"✅ Imported {count} stocks into stocks table")
    return count


# ── Stock Info ──

def list_stock_info(data_dir: str, ts_code: str):
    """Display available data years for a stock."""
    print(f"=== {ts_code} ===\n")

    # Stock basic info
    basic_info = None
    for year in range(2005, 2027):
        rows = load_csv_rows(data_dir, year, "basic")
        for r in rows:
            if r.get("ts_code", "").strip() == ts_code:
                basic_info = r
                break
        if basic_info:
            break

    if basic_info:
        print(f"  Name: {basic_info.get('name', '?')}")
        print(f"  EN:   {basic_info.get('enname', '?')}")
        print(f"  Market: {basic_info.get('market', '?')}")
        print(f"  Listed: {basic_info.get('list_date', '?')}")
        print(f"  Currency: {basic_info.get('curr_type', '?')}")

    # Year-by-year availability
    print(f"\n{'Year':<6} {'Income':>8} {'BS':>8} {'CF':>8} {'FI':>8}  FI periods")
    print("-" * 65)

    for year in range(2005, 2027):
        inc = load_csv_rows(data_dir, year, "income")
        bs = load_csv_rows(data_dir, year, "balancesheet")
        cf = load_csv_rows(data_dir, year, "cashflow")
        fi = load_csv_rows(data_dir, year, "fina_indicator")

        inc_n = len([r for r in inc if r.get("ts_code") == ts_code])
        bs_n = len([r for r in bs if r.get("ts_code") == ts_code])
        cf_n = len([r for r in cf if r.get("ts_code") == ts_code])
        fi_rows = [r for r in fi if r.get("ts_code") == ts_code]
        fi_n = len(fi_rows)

        if inc_n == 0 and bs_n == 0 and cf_n == 0 and fi_n == 0:
            continue

        # Show FI report types
        fi_types = [r.get("report_type", "?") for r in fi_rows]
        fi_types_str = ", ".join(fi_types[:3])
        if len(fi_types) > 3:
            fi_types_str += f" ...({len(fi_types)})"

        inc_s = f"{inc_n}r" if inc_n > 0 else "-"
        bs_s = f"{bs_n}r" if bs_n > 0 else "-"
        cf_s = f"{cf_n}r" if cf_n > 0 else "-"
        fi_s = f"{fi_n}r" if fi_n > 0 else "-"

        print(f"{year:<6} {inc_s:>8} {bs_s:>8} {cf_s:>8} {fi_s:>8}  {fi_types_str}")


# ── Bulk Import (All Stocks) ──

def discover_all_stocks(data_dir: str, years: list) -> list:
    """Discover all unique stock codes across the specified years."""
    all_codes = set()
    for year in years:
        basic_rows = load_csv_rows(data_dir, year, "basic")
        for r in basic_rows:
            code = r.get("ts_code", "").strip()
            if code:
                all_codes.add(code)
    return sorted(all_codes)


def import_all_stocks(conn, data_dir: str, years: list = None,
                      annual_only: bool = True, dry_run: bool = False,
                      skip_existing: bool = True):
    """Import all stocks across all years. Processes year-by-year for efficiency.

    For each year, loads all CSVs once and processes all stocks found in that year.
    """
    if years is None:
        years = list(range(2005, 2027))

    # Phase 1: Import stocks table
    if not dry_run:
        print("Phase 1: Importing stocks table...")
        import_stocks_table(conn, data_dir, dry_run=False)
        print()

    total_observations = 0
    total_stocks_imported = 0
    global_unmapped = Counter()

    for year in years:
        print(f"{'🔍' if dry_run else '📥'} Year {year}...", end=" ", flush=True)

        # Quick check: are there any CSVs for this year?
        income_rows = load_csv_rows(data_dir, year, "income")
        bs_rows = load_csv_rows(data_dir, year, "balancesheet")
        cf_rows = load_csv_rows(data_dir, year, "cashflow")
        fi_rows = load_csv_rows(data_dir, year, "fina_indicator")

        if not any([income_rows, bs_rows, cf_rows, fi_rows]):
            print("(no data)")
            continue

        # Group by stock code
        stock_codes = set()
        for rows in [income_rows, bs_rows, cf_rows, fi_rows]:
            for r in rows:
                code = r.get("ts_code", "").strip()
                if code:
                    stock_codes.add(code)

        print(f"{len(stock_codes)} stocks...", end=" ", flush=True)

        # Pre-pivot all stocks from LONG to WIDE
        # Index: {ts_code: {end_date: {field: value}}}
        income_index = _pivot_all_stocks(income_rows, HK_INCOME_NAME_TO_FIELD, year, global_unmapped)
        bs_index = _pivot_all_stocks(bs_rows, HK_BS_NAME_TO_FIELD, year, global_unmapped)
        cf_index = _pivot_all_stocks(cf_rows, HK_CF_NAME_TO_FIELD, year, global_unmapped)
        fi_index = _map_all_fi(fi_rows)

        year_obs = 0
        year_stocks = 0

        for ts_code in sorted(stock_codes):
            inc_by_date = income_index.get(ts_code, {})
            bs_by_date = bs_index.get(ts_code, {})
            cf_by_date = cf_index.get(ts_code, {})
            fi_by_date = fi_index.get(ts_code, {})

            if not any([inc_by_date, bs_by_date, cf_by_date, fi_by_date]):
                continue

            # Determine fiscal month from FI data
            fi_stock_rows = [r for r in fi_rows if r.get("ts_code", "").strip() == ts_code]
            fiscal_month = resolve_fiscal_month(fi_stock_rows, ts_code)

            # Build records
            records = build_records(inc_by_date, bs_by_date, cf_by_date, fi_by_date,
                                    ts_code, annual_only, fiscal_month)

            if not records:
                continue

            if not dry_run:
                source_path = os.path.join(data_dir, f"hk_financials_{year}")
                n = import_source(conn, ts_code, SOURCE_TYPE, source_path,
                                  records, dry_run=False, priority=SOURCE_PRIORITY)
                year_obs += n
                year_stocks += 1
            else:
                year_stocks += 1

        if dry_run:
            print(f"→ {year_stocks} stocks would be imported")
        else:
            print(f"→ {year_stocks} stocks, {year_obs} obs")
            total_observations += year_obs
            total_stocks_imported += year_stocks

    # Report unmapped
    if global_unmapped:
        print(f"\n⚠️  Global unmapped indicators (top 15):")
        for name, count in global_unmapped.most_common(15):
            print(f"  {count:>10,}×  {name}")

    if not dry_run:
        print(f"\n✅ Imported {total_stocks_imported} stock-years, {total_observations} observations")

    return total_observations


def _pivot_all_stocks(rows: list, mapping: dict, year: int, unmapped_counter: Counter) -> dict:
    """Pivot LONG format rows for ALL stocks at once.

    Returns: {ts_code: {end_date: {field: value_millions}}}
    """
    result = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        ts_code = r.get("ts_code", "").strip()
        ind_name = r.get("ind_name", "").strip()
        end_date = r.get("end_date", "").strip()
        raw_value = r.get("ind_value", "").strip()

        if not all([ts_code, ind_name, end_date, raw_value]):
            continue

        field = mapping.get(ind_name)
        if not field:
            unmapped_counter[ind_name] += 1
            continue

        try:
            val = float(raw_value)
        except (ValueError, TypeError):
            continue

        val_m = to_millions(val, field)
        if val_m is not None:
            result[ts_code][end_date][field] = val_m

    # Convert defaultdict to regular dict
    return {code: dict(dates) for code, dates in result.items()}


def _map_all_fi(rows: list) -> dict:
    """Map fina_indicator WIDE rows for ALL stocks at once.

    Returns: {ts_code: {end_date: {field: value_millions}}}
    """
    result = defaultdict(dict)
    for r in rows:
        ts_code = r.get("ts_code", "").strip()
        end_date = r.get("end_date", "").strip()
        if not ts_code or not end_date:
            continue

        record = {
            "_report_type": r.get("report_type", "").strip(),
            "_fiscal_year": safe_float(r.get("fiscal_year")),
            "_currency": r.get("currency", "").strip(),
        }

        for csv_col, db_field in FI_COLUMN_TO_FIELD.items():
            raw = r.get(csv_col, "").strip()
            if raw:
                val = safe_float(raw)
                if val is not None:
                    val_m = to_millions(val, db_field)
                    if val_m is not None:
                        record[db_field] = val_m

        result[ts_code][end_date] = record

    return dict(result)


# ── CLI ──

def main():
    p = argparse.ArgumentParser(
        description="import_hk_bulk.py — 批量导入港股 CSV 数据到 stock_analysis.db")
    p.add_argument("--code", type=str, action="append", default=[],
                   help="Stock code(s) to import (e.g., 00700.HK)")
    p.add_argument("--all", action="store_true",
                   help="Import ALL stocks across all years (bulk mode)")
    p.add_argument("--file", type=str,
                   help="File with stock codes (one per line)")
    p.add_argument("--stocks-only", action="store_true",
                   help="Only import stocks table (all ~3,500 HK stocks)")
    p.add_argument("--list-stocks", type=str,
                   help="Show available data years for a stock, then exit")
    p.add_argument("--year", type=str,
                   help="Year range (e.g., '2015-2025' or single '2024')")
    p.add_argument("--annual-only", action="store_true", default=True,
                   help="Only import year-end data (default: True)")
    p.add_argument("--all-periods", action="store_true",
                   help="Import all periods (Q1, H1, Q3, FY) not just year-end")
    p.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR,
                   help=f"Data directory (default: {DEFAULT_DATA_DIR})")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview mode — no database writes")

    args = p.parse_args()

    # Validate data dir
    if not os.path.isdir(args.data_dir):
        print(f"ERROR: Data directory not found: {args.data_dir}")
        return 1

    # List mode
    if args.list_stocks:
        list_stock_info(args.data_dir, args.list_stocks)
        return 0

    # Parse years
    years = None
    if args.year:
        if "-" in args.year:
            parts = args.year.split("-")
            years = list(range(int(parts[0]), int(parts[1]) + 1))
        else:
            years = [int(args.year)]

    annual_only = not args.all_periods  # --annual-only is default True

    # Collect stock codes
    codes = list(args.code) if args.code else []
    if args.file:
        with open(args.file) as f:
            for line in f:
                code = line.strip()
                if code and not code.startswith("#"):
                    codes.append(code)

    # Connect to DB
    import sqlite3
    conn = None if args.dry_run else sqlite3.connect(DB_PATH)
    if conn:
        conn.row_factory = sqlite3.Row

    mode = "🔍 DRY RUN" if args.dry_run else "📥 IMPORTING"
    print(f"{mode} — data dir: {args.data_dir}")
    print(f"DB: {DB_PATH}\n")

    # Stocks-only mode
    if args.stocks_only:
        import_stocks_table(conn, args.data_dir, args.dry_run)
        if conn:
            conn.commit()
            conn.close()
        return 0

    # Import stocks table first (always)
    if not args.dry_run:
        print("Phase 1: Importing stocks table...")
        import_stocks_table(conn, args.data_dir, dry_run=False)
        print()
    else:
        import_stocks_table(conn, args.data_dir, dry_run=True)
        print()

    # Import all stocks (bulk mode)
    if args.all:
        print("Phase 1: Importing stocks table...")
        if not args.dry_run:
            import_stocks_table(conn, args.data_dir, dry_run=False)
        else:
            import_stocks_table(conn, args.data_dir, dry_run=True)
        print()

        print("Phase 2: Bulk importing ALL stocks...")
        import_all_stocks(conn, args.data_dir, years, annual_only, args.dry_run)

        if conn:
            conn.commit()
            obs_n = conn.execute("SELECT COUNT(*) FROM financial_observations WHERE source_type=?",
                                 (SOURCE_TYPE,)).fetchone()[0]
            af_n = conn.execute("""SELECT COUNT(DISTINCT ts_code) FROM annual_financials af
                WHERE EXISTS (SELECT 1 FROM financial_observations fo
                    WHERE fo.ts_code=af.ts_code AND fo.source_type=?)""",
                (SOURCE_TYPE,)).fetchone()[0]
            print(f"\n✅ Total: {obs_n} observations | {af_n} stocks in annual_financials")
            conn.close()
        return 0

    # No specific stocks requested — just done
    if not codes:
        if args.dry_run:
            print("No --code specified. Use --code 00700.HK to import a stock.")
        else:
            print("No --code specified. Stocks table imported. Use --code to import financial data.")
        if conn:
            conn.commit()
            conn.close()
        return 0

    # Import each stock
    for code in codes:
        print(f"Phase 2: Importing {code}...")
        n = import_stock(conn, code, args.data_dir, years, annual_only, args.dry_run)
        if n == 0:
            print(f"  ⚠️  No data found for {code}")
        else:
            print(f"  ✅ {code}: {n} total records")
        print()

    if conn:
        conn.commit()
        # Print summary stats
        obs_n = conn.execute("SELECT COUNT(*) FROM financial_observations WHERE source_type=?",
                             (SOURCE_TYPE,)).fetchone()[0]
        af_n = conn.execute("""SELECT COUNT(*) FROM annual_financials af
            JOIN financial_observations fo ON af.ts_code=fo.ts_code AND af.fiscal_year=fo.fiscal_year
            WHERE fo.source_type=?""", (SOURCE_TYPE,)).fetchone()[0]
        print(f"✅ Observations: {obs_n} | Annual financials: {af_n}")
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
