#!/usr/bin/env python3
"""Build one self-contained Turtle financial database from external datasets.

The builder never mutates the active database.  It copies the current schema to
a staging database, clears stale financial/derived rows, imports source tables,
rebuilds the canonical ``stocks`` and ``annual_financials`` read models, and
then runs material data checks.  Promotion and source deletion are deliberately
separate commands so raw files are removed only after a validated database is
in place.

Amounts in ``annual_financials`` are millions of the statement currency.
Per-share values and percentages are never scaled.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Iterable, Mapping

import pandas as pd


SCHEMA_VERSION = "turtle-financial-database.v1"
MILLION = 1_000_000.0
CURRENT_YEAR = dt.date.today().year

SOURCE_DIR_NAMES = (
    "a_financials",
    "hk_financials",
    "hk_new_financials",
    "cn_financials_panel_raw",
)

# This export has a stable 265-column contract, while XLSX and Stata sanitize
# several Chinese headers differently.  The expected header is checked at the
# identity columns, then financial facts are mapped by the documented ordinal.
CSMAR_A_POSITION_FIELDS = {
    16: "money_cap", 28: "accounts_receiv", 41: "other_receiv",
    43: "inventories", 50: "total_cur_assets", 71: "fix_assets",
    78: "intang_assets", 83: "goodwill", 84: "deferred_assets",
    88: "total_non_cur_assets", 90: "total_assets", 91: "st_borr",
    102: "acct_payable", 103: "adv_receipts", 104: "contract_liab",
    128: "total_cur_liab", 129: "lt_borr", 142: "total_non_cur_liab",
    144: "total_liab", 145: "share_capital", 158: "special_reserve",
    160: "total_hldr_eqy_exc_min_int", 161: "minority_int", 162: "total_equity",
    164: "total_revenue", 165: "revenue", 182: "oper_cost",
    192: "tax_surcharges", 196: "sell_exp", 197: "admin_exp",
    198: "rd_exp", 199: "finance_exp", 203: "invest_income",
    209: "impairment", 214: "operate_profit", 220: "total_profit",
    221: "income_tax", 224: "net_profit_consolidated",
    227: "n_income_attr_p", 229: "minority_profit", 230: "eps",
    231: "eps_diluted", 240: "depr_fa_coga_dpba",
    241: "d_a_invest_prop", 242: "d_a_rou", 243: "d_a_intang",
    244: "d_a_lt_deferred", 245: "asset_disposal_pl",
    246: "fixed_asset_scrap", 247: "fv_change_cf",
    248: "finance_exp_cf_adj", 249: "invest_loss_cf_adj",
    250: "defer_tax_asset_chg", 251: "defer_tax_liab_chg",
    252: "inventory_change", 253: "ar_change_cf", 254: "ap_change_cf",
    256: "n_cashflow_act",
}

A_TUSHARE_FIELDS: dict[str, dict[str, str]] = {
    "income": {
        "revenue": "revenue", "oper_cost": "oper_cost",
        "sell_exp": "sell_exp", "admin_exp": "admin_exp",
        "rd_exp": "rd_exp", "fin_exp": "finance_exp",
        "invest_income": "invest_income", "operate_profit": "operate_profit",
        "total_profit": "total_profit", "income_tax": "income_tax",
        "n_income": "net_profit_consolidated",
        "n_income_attr_p": "n_income_attr_p", "minority_gain": "minority_profit",
        "basic_eps": "eps", "diluted_eps": "eps_diluted",
    },
    "balancesheet": {
        "money_cap": "money_cap", "accounts_receiv": "accounts_receiv",
        "oth_receiv": "other_receiv", "inventories": "inventories",
        "total_cur_assets": "total_cur_assets", "fix_assets": "fix_assets",
        "intan_assets": "intang_assets", "goodwill": "goodwill",
        "total_assets": "total_assets", "st_borr": "st_borr",
        "notes_payable": "notes_payable", "acct_payable": "acct_payable",
        "contract_liab": "contract_liab", "adv_receipts": "adv_receipts",
        "non_cur_liab_due_1y": "non_cur_liab_due_1y",
        "total_cur_liab": "total_cur_liab", "lt_borr": "lt_borr",
        "bond_payable": "bond_payable", "total_liab": "total_liab",
        "defer_tax_assets": "defer_tax_assets", "defer_tax_liab": "defer_tax_liab",
        "total_hldr_eqy_exc_min_int": "total_hldr_eqy_exc_min_int",
        "minority_int": "minority_int",
    },
    "cashflow": {
        "n_cashflow_act": "n_cashflow_act",
        "n_cashflow_inv_act": "n_cashflow_inv_act",
        "n_cash_flows_fnc_act": "n_cash_flows_fnc_act",
        "c_pay_acq_const_fiolta": "c_pay_acq_const_fiolta",
        "c_paid_for_taxes": "tax_paid",
        "c_recp_return_invest": "cf_invest_recall",
        "c_pay_dist_dpcp_int_exp": "c_pay_dist_dpcp_int_exp",
        "depr_fa_coga_dpba": "depr_fa_coga_dpba",
        "amort_intang_assets": "amort_intang_assets",
        "lt_amort_deferred_exp": "amort_lt_deferred",
    },
    "fina_indicator": {
        "roe": "roe", "grossprofit_margin": "gross_margin",
        "netprofit_margin": "net_margin", "rd_exp": "rd_exp",
        "current_ratio": "current_ratio", "assets_turn": "asset_turnover_days",
        "debt_to_assets": "debt_ratio", "or_yoy": "revenue_growth_pct",
        "netprofit_yoy": "np_growth_pct", "bps": "bps",
    },
}

HK_INCOME_FIELDS = {
    "营业额": "revenue", "营业收入": "revenue", "收益": "revenue",
    "revenue": "revenue", "销售成本": "oper_cost", "营业成本": "oper_cost",
    "营运支出": "oper_cost", "毛利": "gross_profit",
    "股东应占溢利": "n_income_attr_p", "本公司拥有人应占全面收益总额": "n_income_attr_p",
    "除税后溢利": "n_income_attr_p", "持续经营业务税后利润": "n_income_attr_p",
    "税前利润": "pretax_profit", "除税前溢利": "pretax_profit",
    "税项": "income_tax", "所得税": "income_tax",
    "员工成本": "employee_cost", "薪金福利支出": "employee_cost",
    "僱員福利支出": "employee_cost", "雇员福利支出": "employee_cost",
    "员工薪酬": "employee_cost", "职工薪酬": "employee_cost",
    "staff cost": "employee_cost", "staff costs": "employee_cost",
    "employee benefit expense": "employee_cost", "employee benefits expense": "employee_cost",
    "折旧与摊销": "d_a", "折旧及摊销": "d_a", "折旧摊销": "d_a",
    "利息收入": "int_income", "利息支出": "interest_expense",
    "融资成本": "finance_exp", "财务费用": "finance_exp",
    "销售及分销费用": "sell_exp", "行政开支": "admin_exp",
    "研发费用": "rd_exp", "其他收入": "other_income", "其他收益": "other_income",
    "政府补助": "gov_subsidy", "政府补贴": "gov_subsidy", "投资收益": "invest_income",
}

HK_BALANCE_FIELDS = {
    "总资产": "total_assets", "资产总计": "total_assets",
    "总负债": "total_liab", "负债总计": "total_liab",
    "总权益": "total_hldr_eqy_exc_min_int", "股东权益": "total_hldr_eqy_exc_min_int",
    "净资产": "total_hldr_eqy_exc_min_int", "本公司拥有人应占权益": "total_hldr_eqy_exc_min_int",
    "归属于母公司股东权益": "total_hldr_eqy_exc_min_int",
    "少数股东权益": "minority_int", "非控股权益": "minority_int",
    "非控股股东权益": "minority_int", "现金及等价物": "money_cap",
    "现金及现金等价物": "money_cap", "受限制存款及现金": "cash_broad",
    "短期存款": "short_term_deposits", "定期存款": "time_deposits",
    "中长期存款": "time_deposits", "短期投资": "short_term_investments",
    "应收账款及票据": "accounts_receiv", "应收帐款": "accounts_receiv",
    "应付账款及票据": "acct_payable", "应付帐款": "acct_payable",
    "合同负债": "contract_liab", "递延收入(流动)": "contract_liab",
    "存货": "inventories", "商誉": "goodwill", "固定资产": "fix_assets",
    "物业厂房及设备": "fix_assets", "无形资产": "intang_assets",
    "短期贷款": "st_borr", "短期借款": "st_borr",
    "长期贷款": "lt_borr", "长期借款": "lt_borr",
    "长期待摊费用": "deferred_assets", "遞延資產": "deferred_assets",
    "流动资产合计": "total_cur_assets", "流动负债合计": "total_cur_liab",
}

HK_CASHFLOW_FIELDS = {
    "经营业务现金净额": "n_cashflow_act",
    "已付税项": "tax_paid", "已付利息(经营)": "interest_paid",
    "折旧与摊销": "d_a", "折旧及摊销": "d_a",
    "投资业务现金净额": "n_cashflow_inv_act",
    "融资业务现金净额": "n_cash_flows_fnc_act",
}

HK_CSMAR_INCOME = {
    "B001101": "revenue", "B001201": "oper_cost", "B001209": "sell_exp",
    "B001210": "admin_exp", "B001211": "finance_exp", "B001302": "invest_income",
    "B0013": "operate_profit", "B001": "pretax_profit", "B0021": "income_tax",
    "B002": "net_profit_consolidated", "B0024": "n_income_attr_p",
    "B0025": "minority_profit", "B003": "eps", "B004": "eps_diluted",
}

HK_CSMAR_BALANCE = {
    "A001101": "money_cap", "A001107": "trading_fin_assets",
    "A001111": "accounts_receiv", "A001112": "prepayments",
    "A001121": "other_receiv", "A001123": "inventories",
    "A0011": "total_cur_assets", "A0012": "total_non_cur_assets",
    "A001": "total_assets", "A001212": "fix_assets", "A001205": "lt_eqt_invest",
    "A001220": "goodwill", "A001218": "intang_assets", "A002101": "st_borr",
    "A002108": "acct_payable", "A002109": "adv_receipts",
    "A0021": "total_cur_liab", "A002201": "lt_borr",
    "A0022": "total_non_cur_liab", "A002": "total_liab",
    "A003101": "share_capital", "A0031": "total_hldr_eqy_exc_min_int",
    "A0032": "minority_int", "A003": "total_equity",
}

HK_CSMAR_CASHFLOW = {
    "C001": "n_cashflow_act", "C002006": "c_pay_acq_const_fiolta",
    "C001020": "cash_paid_employees", "C001021": "tax_paid",
    "C002002": "invest_income_cf", "C002003": "asset_disposal_cf",
    "C002": "n_cashflow_inv_act", "C003": "n_cash_flows_fnc_act",
    "C001014": "cash_paid_suppliers",
}

HK_CSMAR_DISCLOSURE = {
    "DPS": "dps", "IssueCapPE": "base_share", "Deprec": "d_a",
    "TotalDividend": "dividends_paid", "TurnoverGrowth": "revenue_growth_pct",
    "NPGrowth": "np_growth_pct", "TaxRate": "tax_rate_pct",
}

PER_SHARE_OR_RATIO = {
    "eps", "eps_diluted", "dps", "dps_hkd", "bps", "pe_ttm", "pb_ttm",
    "payout_ratio", "roe", "roa", "gross_margin", "net_margin", "debt_ratio",
    "current_ratio", "ocf_sales_ratio", "inventory_turnover_days",
    "ar_turnover_days", "asset_turnover_days", "revenue_growth_pct",
    "np_growth_pct", "tax_rate_pct",
}

GREE_2024_EXPECTED = {
    "revenue": 189_163.65406464,
    "n_income_attr_p": 32_184.57037228,
    "n_cashflow_act": 29_369.25057066,
    "total_assets": 368_031.70452286,
    "total_liab": 226_518.00957489,
    "total_hldr_eqy_exc_min_int": 137_416.89894639,
    "base_share": 5_601.405741,
    "dps": 3.0,
}


def normalize_a_code(value: object) -> str:
    text = str(value).strip()
    if text.endswith((".SH", ".SZ", ".BJ")):
        return text
    try:
        code = str(int(float(text))).zfill(6)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid A-share code: {value!r}") from exc
    if code.startswith(("4", "8", "92")):
        suffix = "BJ"
    elif code.startswith(("6", "9")):
        suffix = "SH"
    else:
        suffix = "SZ"
    return f"{code}.{suffix}"


def _to_number(series: pd.Series, *, scale: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values / MILLION if scale else values


def _clean_frame_for_sql(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for col in result.select_dtypes(include=["datetime", "datetimetz"]).columns:
        result[col] = result[col].dt.strftime("%Y-%m-%d")
    return result.where(pd.notna(result), None)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _ensure_annual_columns(conn: sqlite3.Connection, columns: Iterable[str]) -> None:
    existing = _table_columns(conn, "annual_financials")
    for column in sorted(set(columns) - existing):
        conn.execute(f'ALTER TABLE annual_financials ADD COLUMN "{column}" REAL')


def _upsert_frame(
    conn: sqlite3.Connection,
    frame: pd.DataFrame,
    *,
    source_name: str,
) -> int:
    if frame.empty:
        return 0
    frame = frame.copy()
    years = pd.to_numeric(frame["fiscal_year"], errors="coerce")
    allowed = years.between(1900, CURRENT_YEAR)
    allowed &= ~(
        frame["report_type"].astype(str).eq("annual")
        & years.gt(CURRENT_YEAR - 1)
    )
    frame = frame.loc[allowed].copy()
    frame["fiscal_year"] = years.loc[frame.index].astype(int)
    if frame.empty:
        return 0
    frame["data_source"] = source_name
    frame["data_quality"] = "normalized"
    keys = ["ts_code", "fiscal_year", "report_type"]
    values = [c for c in frame.columns if c not in keys]
    _ensure_annual_columns(conn, [c for c in values if c not in {"data_source", "data_quality"}])
    temp = "_incoming_financials"
    conn.execute(f'DROP TABLE IF EXISTS "{temp}"')
    _clean_frame_for_sql(frame).to_sql(temp, conn, index=False, if_exists="replace")
    cols = keys + values
    quoted = ", ".join(f'"{c}"' for c in cols)
    selected = ", ".join(f's."{c}"' for c in cols)
    updates = ", ".join(
        f'"{c}"=COALESCE(excluded."{c}", annual_financials."{c}")'
        for c in values
    )
    conn.execute(
        f'INSERT INTO annual_financials ({quoted}) '
        f'SELECT {selected} FROM "{temp}" s WHERE 1 '
        f'ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET {updates}'
    )
    conn.execute(f'DROP TABLE "{temp}"')
    return len(frame)


def _archive_frame(
    conn: sqlite3.Connection,
    table: str,
    frame: pd.DataFrame,
    *,
    replace: bool,
) -> int:
    if frame.empty:
        return 0
    _clean_frame_for_sql(frame).to_sql(
        table,
        conn,
        index=False,
        if_exists="replace" if replace else "append",
        chunksize=1000,
    )
    return len(frame)


def _record_import(
    conn: sqlite3.Connection,
    dataset: str,
    source: str,
    table: str,
    rows: int,
    notes: str = "",
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO source_imports
        (dataset, logical_source, database_table, row_count, status, notes)
        VALUES (?, ?, ?, ?, 'IMPORTED', ?)
        """,
        (dataset, source, table, int(rows), notes),
    )


def _create_consolidation_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS database_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_imports (
            dataset TEXT PRIMARY KEY,
            logical_source TEXT NOT NULL,
            database_table TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            imported_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS database_validation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT DEFAULT (datetime('now','localtime')),
            status TEXT NOT NULL,
            findings_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_file_archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            logical_path TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            content BLOB NOT NULL,
            imported_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO database_metadata(key,value) VALUES('schema_version',?)",
        (SCHEMA_VERSION,),
    )


def _archive_file_blob(
    conn: sqlite3.Connection,
    path: Path,
    *,
    data_root: Path,
    role: str,
) -> None:
    size = path.stat().st_size
    logical = str(path.relative_to(data_root))
    conn.execute("DELETE FROM source_file_archives WHERE logical_path=?", (logical,))
    cursor = conn.execute(
        "INSERT INTO source_file_archives(logical_path,role,size_bytes,content) "
        "VALUES(?,?,?,zeroblob(?))",
        (logical, role, size, size),
    )
    rowid = cursor.lastrowid
    with conn.blobopen("source_file_archives", "content", rowid, readonly=False) as blob:
        with path.open("rb") as source:
            while chunk := source.read(8 * 1024 * 1024):
                blob.write(chunk)
    _record_import(
        conn,
        f"file_archive:{logical}",
        logical,
        "source_file_archives",
        1,
        f"Exact {role} retained as a database BLOB.",
    )


def archive_unique_source_files(conn: sqlite3.Connection, data_root: Path) -> None:
    patterns = (
        ("cn_financials_panel_raw/raw_data/*.zip", "compressed_source_workbook"),
        ("cn_financials_panel_raw/*.pdf", "source_documentation"),
        ("cn_financials_panel_raw/指标一览（用于搜索）.xlsx", "source_dictionary"),
        ("hk_new_financials/**/*.txt", "source_dictionary"),
        ("hk_new_financials/*.pdf", "source_documentation"),
        ("hk_new_financials/*.docx", "source_documentation"),
    )
    seen: set[Path] = set()
    for pattern, role in patterns:
        for path in sorted(data_root.glob(pattern)):
            if path.is_file() and path not in seen:
                _archive_file_blob(conn, path, data_root=data_root, role=role)
                seen.add(path)


def _reset_database(conn: sqlite3.Connection) -> None:
    derived = (
        "analysis_contracts", "computed_metrics", "rejection_checks",
        "data_quality_log", "audit_log", "raw_import_batches",
        "financial_observations", "field_evidence", "curation_decisions",
        "quality_findings", "annual_financials",
    )
    conn.execute("PRAGMA foreign_keys=OFF")
    for table in derived:
        if table in {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }:
            conn.execute(f'DELETE FROM "{table}"')
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'source_%'"
    ).fetchall():
        conn.execute(f'DROP TABLE "{name}"')
    conn.execute("DROP TABLE IF EXISTS database_metadata")
    conn.execute("DROP TABLE IF EXISTS database_validation_runs")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='annual_financials'")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_consolidation_schema(conn)


def _prepare_csmar_a(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"证券代码", "年份"}
    if not required.issubset(frame.columns):
        raise ValueError(f"A-share panel missing columns: {sorted(required - set(frame.columns))}")
    result = pd.DataFrame()
    result["ts_code"] = frame["证券代码"].map(normalize_a_code)
    result["fiscal_year"] = pd.to_numeric(frame["年份"], errors="raise").astype(int)
    result["report_type"] = "annual"
    if len(frame.columns) <= max(CSMAR_A_POSITION_FIELDS):
        raise ValueError(f"A-share panel has only {len(frame.columns)} columns")
    for position, target in CSMAR_A_POSITION_FIELDS.items():
        result[target] = _to_number(
            frame.iloc[:, position], scale=target not in PER_SHARE_OR_RATIO
        )
    if "depr_fa_coga_dpba" in result:
        parts = [
            result.get("depr_fa_coga_dpba"), result.get("d_a_invest_prop"),
            result.get("d_a_rou"), result.get("d_a_intang"), result.get("d_a_lt_deferred"),
        ]
        result["d_a"] = pd.concat(parts, axis=1).sum(axis=1, min_count=1)
    if "share_capital" in result:
        result["base_share"] = result["share_capital"]
    return result


def _upsert_stocks(conn: sqlite3.Connection, frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    columns = _table_columns(conn, "stocks")
    usable = [c for c in frame.columns if c in columns]
    temp = "_incoming_stocks"
    conn.execute(f'DROP TABLE IF EXISTS "{temp}"')
    _clean_frame_for_sql(frame[usable]).to_sql(temp, conn, index=False, if_exists="replace")
    values = [c for c in usable if c != "ts_code"]
    quoted = ", ".join(f'"{c}"' for c in usable)
    selected = ", ".join(f's."{c}"' for c in usable)
    updates = ", ".join(
        f'"{c}"=COALESCE(stocks."{c}", excluded."{c}")' for c in values
    )
    conn.execute(
        f'INSERT INTO stocks ({quoted}) SELECT {selected} FROM "{temp}" s WHERE 1 '
        f'ON CONFLICT(ts_code) DO UPDATE SET {updates}'
    )
    conn.execute(f'DROP TABLE "{temp}"')
    return len(frame)


def import_csmar_a(conn: sqlite3.Connection, data_root: Path, *, archive: bool) -> int:
    source_dir = data_root / "cn_financials_panel_raw"
    dta = source_dir / "上市公司-财务报表年度面板数据.dta"
    xlsx = source_dir / "上市公司-财务报表年度面板数据.xlsx"
    if dta.exists():
        frame = pd.read_stata(dta, convert_categoricals=False)
        logical = "cn_financials_panel_raw/上市公司-财务报表年度面板数据.dta"
    elif xlsx.exists():
        frame = pd.read_excel(xlsx)
        logical = "cn_financials_panel_raw/上市公司-财务报表年度面板数据.xlsx"
    else:
        raise FileNotFoundError("CSMAR A-share annual panel not found")
    table = "source_csmar_a_annual_panel"
    archived = _archive_frame(conn, table, frame, replace=True) if archive else 0
    _record_import(
        conn, "csmar_a_annual_panel", logical, table, len(frame),
        "DTA/XLSX are duplicate representations; one structured table retained.",
    )
    canonical = _prepare_csmar_a(frame)
    _upsert_frame(conn, canonical, source_name="csmar_a_annual_panel")

    latest = frame.copy()
    latest["_year"] = pd.to_numeric(latest["年份"], errors="coerce")
    latest = latest.sort_values("_year").drop_duplicates("证券代码", keep="last")
    stocks = pd.DataFrame({
        "ts_code": latest["证券代码"].map(normalize_a_code),
        "name_cn": latest.get("股票简称"),
        "industry": latest.get("行业名称"),
        "market": "A",
        "currency": "RMB",
    })
    if "实收资本或股本" in latest:
        stocks["shares_m"] = _to_number(latest["实收资本或股本"], scale=True)
    elif "实收资本(或股本)" in latest:
        stocks["shares_m"] = _to_number(latest["实收资本(或股本)"], scale=True)
    _upsert_stocks(conn, stocks)
    return archived or len(frame)


def _annual_tushare_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if "end_date" not in frame:
        return frame.iloc[0:0]
    result = frame.copy()
    end = result["end_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    result = result[end.str.match(r"^(?:19|20)\d{2}1231$")]
    result["_fy"] = pd.to_numeric(end.loc[result.index].str[:4], errors="coerce")
    sort_col = "f_ann_date" if "f_ann_date" in result else "ann_date" if "ann_date" in result else None
    if sort_col:
        result = result.sort_values(sort_col)
    return result.drop_duplicates("ts_code", keep="last")


def import_tushare_a(conn: sqlite3.Connection, data_root: Path, *, archive: bool) -> int:
    root = data_root / "a_financials"
    if not root.is_dir():
        raise FileNotFoundError(root)
    total = 0
    first_by_table: set[str] = set()
    rows_by_table: dict[str, int] = {}
    dividends: list[pd.DataFrame] = []
    stock_frames: list[pd.DataFrame] = []
    for path in sorted(root.glob("a_financials_*/*.parquet")):
        kind = path.stem.removeprefix("a_").rsplit("_", 1)[0]
        frame = pd.read_parquet(path)
        table = f"source_tushare_a_{kind}"
        rows_by_table[table] = rows_by_table.get(table, 0) + len(frame)
        if archive:
            _archive_frame(conn, table, frame, replace=table not in first_by_table)
            first_by_table.add(table)
        total += len(frame)
        if frame.empty or len(frame.columns) == 0:
            continue
        if kind == "stock_basic":
            stock_frames.append(frame)
            continue
        if kind == "dividend":
            dividends.append(frame)
            continue
        mapping = A_TUSHARE_FIELDS.get(kind)
        if not mapping:
            continue
        annual = _annual_tushare_rows(frame)
        incoming = pd.DataFrame({
            "ts_code": annual["ts_code"].astype(str),
            "fiscal_year": annual["_fy"].astype(int),
            "report_type": "annual",
        })
        for source, target in mapping.items():
            if source in annual:
                incoming[target] = _to_number(
                    annual[source], scale=target not in PER_SHARE_OR_RATIO
                ).values
        _upsert_frame(conn, incoming, source_name="tushare_a_fallback")

    if dividends:
        frame = pd.concat(dividends, ignore_index=True)
        end = frame["end_date"].astype(str).str.replace(r"\.0$", "", regex=True)
        frame = frame[end.str.match(r"^(?:19|20)\d{2}(?:1231|0630)$")]
        if "div_proc" in frame:
            frame = frame[frame["div_proc"].astype(str).eq("实施")]
        frame["fiscal_year"] = pd.to_numeric(end.loc[frame.index].str[:4], errors="coerce")
        frame["dps"] = pd.to_numeric(frame["cash_div_tax"], errors="coerce")
        dps = frame.groupby(["ts_code", "fiscal_year"], as_index=False)["dps"].sum(min_count=1)
        dps["report_type"] = "annual"
        _upsert_frame(conn, dps, source_name="tushare_a_dividend")

    if stock_frames:
        stocks = pd.concat(stock_frames, ignore_index=True).drop_duplicates("ts_code", keep="last")
        incoming = pd.DataFrame({
            "ts_code": stocks["ts_code"].astype(str),
            "name_cn": stocks.get("name"), "name_en": stocks.get("enname"),
            "industry": stocks.get("industry"), "listing_date": stocks.get("list_date"),
            "market": "A", "currency": "RMB",
        })
        _upsert_stocks(conn, incoming)
    for table, rows in sorted(rows_by_table.items()):
        if archive:
            rows = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        _record_import(conn, table, f"a_financials/{table.removeprefix('source_tushare_a_')}/*.parquet", table, rows,
                       "Parquet retained in SQLite; duplicate CSV representation omitted."
                       if archive else "Diagnostic build without embedded source tables.")
    return total


def _report_type_from_end_date(series: pd.Series) -> pd.Series:
    end = series.astype(str).str.replace(r"\.0$", "", regex=True)
    return end.str[4:6].map({"12": "annual", "06": "semiannual"})


def _prepare_hk_indicator(frame: pd.DataFrame) -> pd.DataFrame:
    end = frame["end_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    report_type = _report_type_from_end_date(frame["end_date"])
    valid = report_type.notna() & end.str.match(r"^(?:19|20)\d{6}$")
    source = frame.loc[valid].copy()
    result = pd.DataFrame({
        "ts_code": source["ts_code"].astype(str),
        "fiscal_year": pd.to_numeric(end.loc[source.index].str[:4], errors="coerce").astype(int),
        "report_type": report_type.loc[source.index],
    })
    mapping = {
        "holder_profit": "n_income_attr_p", "operate_income": "revenue",
        "netcash_operate": "n_cashflow_act", "operate_profit": "operate_profit",
        "pretax_profit": "pretax_profit", "total_assets": "total_assets",
        "total_liabilities": "total_liab", "total_parent_equity": "total_hldr_eqy_exc_min_int",
        "gross_profit": "gross_profit", "end_cash": "money_cap",
        "issued_common_shares": "base_share", "basic_eps": "eps",
        "diluted_eps": "eps_diluted", "dps_hkd": "dps",
        "bps": "bps", "divi_ratio": "payout_ratio", "pe_ttm": "pe_ttm",
        "pb_ttm": "pb_ttm", "roe_avg": "roe", "roa": "roa",
        "gross_profit_ratio": "gross_margin", "net_profit_ratio": "net_margin",
        "debt_asset_ratio": "debt_ratio", "current_ratio": "current_ratio",
        "ocf_sales": "ocf_sales_ratio", "inventory_tdays": "inventory_turnover_days",
        "accounts_rece_tdays": "ar_turnover_days", "total_assets_tdays": "asset_turnover_days",
        "net_interest_income": "net_interest_income", "premium_income": "premium_income",
    }
    for source_col, target in mapping.items():
        if source_col in source:
            scale = target not in PER_SHARE_OR_RATIO
            if target == "base_share":
                scale = True
            result[target] = _to_number(source[source_col], scale=scale).values
    if "dps" in result:
        result["dps_hkd"] = result["dps"]
    return result.drop_duplicates(["ts_code", "fiscal_year", "report_type"], keep="last")


def _prepare_hk_long(frame: pd.DataFrame, mapping: Mapping[str, str], kind: str) -> pd.DataFrame:
    end = frame["end_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    report_type = _report_type_from_end_date(frame["end_date"])
    valid = report_type.notna() & end.str.match(r"^(?:19|20)\d{6}$")
    source = frame.loc[valid, ["ts_code", "end_date", "ind_name", "ind_value"]].copy()
    source["field"] = source["ind_name"].astype(str).str.strip().str.lower().map(mapping)
    source = source[source["field"].notna()]
    source["value"] = pd.to_numeric(source["ind_value"], errors="coerce") / MILLION
    source["fiscal_year"] = pd.to_numeric(end.loc[source.index].str[:4], errors="coerce")
    source["report_type"] = report_type.loc[source.index]
    source = source[["ts_code", "fiscal_year", "report_type", "field", "value"]]
    if kind == "cashflow":
        capex_names = {
            "购建固定资产", "购建无形资产及其他资产",
        }
        capex = frame.loc[valid & frame["ind_name"].astype(str).str.strip().isin(capex_names)].copy()
        if not capex.empty:
            capex_end = capex["end_date"].astype(str).str.replace(r"\.0$", "", regex=True)
            capex["fiscal_year"] = pd.to_numeric(capex_end.str[:4], errors="coerce")
            capex["report_type"] = _report_type_from_end_date(capex["end_date"])
            capex["value"] = pd.to_numeric(capex["ind_value"], errors="coerce").abs() / MILLION
            summed = capex.groupby(["ts_code", "fiscal_year", "report_type"], as_index=False)["value"].sum(min_count=1)
            summed["field"] = "c_pay_acq_const_fiolta"
            source = pd.concat([source, summed[source.columns]], ignore_index=True)
    if source.empty:
        return pd.DataFrame()
    pivot = source.pivot_table(
        index=["ts_code", "fiscal_year", "report_type"],
        columns="field", values="value", aggfunc="first",
    ).reset_index()
    pivot.columns.name = None
    return pivot


def import_tushare_hk(conn: sqlite3.Connection, data_root: Path, *, archive: bool) -> int:
    root = data_root / "hk_financials"
    if not root.is_dir():
        raise FileNotFoundError(root)
    total = 0
    first_by_table: set[str] = set()
    rows_by_table: dict[str, int] = {}
    stock_frames: list[pd.DataFrame] = []
    long_maps = {
        "income": {k.lower(): v for k, v in HK_INCOME_FIELDS.items()},
        "balancesheet": {k.lower(): v for k, v in HK_BALANCE_FIELDS.items()},
        "cashflow": {k.lower(): v for k, v in HK_CASHFLOW_FIELDS.items()},
    }
    for path in sorted(root.glob("hk_financials_*/*.parquet")):
        kind = path.stem.removeprefix("hk_").rsplit("_", 1)[0]
        frame = pd.read_parquet(path)
        table = f"source_tushare_hk_{kind}"
        rows_by_table[table] = rows_by_table.get(table, 0) + len(frame)
        if archive:
            _archive_frame(conn, table, frame, replace=table not in first_by_table)
            first_by_table.add(table)
        total += len(frame)
        if frame.empty or len(frame.columns) == 0:
            continue
        if kind == "basic":
            stock_frames.append(frame)
        elif kind == "fina_indicator":
            _upsert_frame(conn, _prepare_hk_indicator(frame), source_name="tushare_hk_indicator")
        elif kind in long_maps:
            incoming = _prepare_hk_long(frame, long_maps[kind], kind)
            _upsert_frame(conn, incoming, source_name=f"tushare_hk_{kind}")
    if stock_frames:
        stocks = pd.concat(stock_frames, ignore_index=True).drop_duplicates("ts_code", keep="last")
        incoming = pd.DataFrame({
            "ts_code": stocks["ts_code"].astype(str), "name_cn": stocks.get("name"),
            "name_en": stocks.get("enname"), "listing_date": stocks.get("list_date"),
            "market": "HK", "currency": "HKD",
        })
        _upsert_stocks(conn, incoming)
    for table, rows in sorted(rows_by_table.items()):
        if archive:
            rows = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        _record_import(conn, table, f"hk_financials/{table.removeprefix('source_tushare_hk_')}/*.parquet", table, rows,
                       "Parquet retained in SQLite; duplicate CSV representation omitted."
                       if archive else "Diagnostic build without embedded source tables.")
    return total


def _read_hk_csmar(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path, header=None)
    frame.columns = frame.iloc[0]
    return frame.iloc[3:].reset_index(drop=True)


def _prepare_hk_csmar(frame: pd.DataFrame, mapping: Mapping[str, str]) -> pd.DataFrame:
    source = frame.copy()
    source["Symbol"] = source["Symbol"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)
    source = source[source["Symbol"].str.match(r"^\d{5}$")]
    if "StateTypeCode" in source:
        source = source[source["StateTypeCode"].astype(str).eq("A")]
    if "CoverPeriod" in source:
        source = source[pd.to_numeric(source["CoverPeriod"], errors="coerce").eq(12)]
    years = pd.to_datetime(source["EndDate"], errors="coerce").dt.year
    valid = years.notna()
    source = source.loc[valid]
    result = pd.DataFrame({
        "ts_code": source["Symbol"] + ".HK",
        "fiscal_year": years.loc[source.index].astype(int),
        "report_type": "annual",
    })
    for source_col, target in mapping.items():
        if source_col not in source:
            continue
        scale = target not in PER_SHARE_OR_RATIO
        if target == "base_share":
            scale = True
        result[target] = _to_number(source[source_col], scale=scale).values
    if "dps" in result:
        result["dps_hkd"] = result["dps"]
    return result.drop_duplicates(["ts_code", "fiscal_year", "report_type"], keep="last")


def import_csmar_hk(conn: sqlite3.Connection, data_root: Path, *, archive: bool) -> int:
    root = data_root / "hk_new_financials"
    specs = (
        ("HK利润表(非金融)/HK_STK_Income.xlsx", "income_non_financial", HK_CSMAR_INCOME),
        ("HK利润表(金融)/HK_STK_IncomeFI.xlsx", "income_financial", HK_CSMAR_INCOME),
        ("HK资产负债表(非金融)/HK_STK_Balance.xlsx", "balance_non_financial", HK_CSMAR_BALANCE),
        ("HK资产负债表(金融)/HK_STK_BalanceFI.xlsx", "balance_financial", HK_CSMAR_BALANCE),
        ("HK现金流量表/HK_STK_CashFlow.xlsx", "cashflow", HK_CSMAR_CASHFLOW),
        ("HK上市披露指标/HK_STK_DiscloseIndex.xlsx", "disclosure", HK_CSMAR_DISCLOSURE),
    )
    total = 0
    for relative, label, mapping in specs:
        path = root / relative
        if not path.exists():
            raise FileNotFoundError(path)
        frame = _read_hk_csmar(path)
        table = f"source_csmar_hk_{label}"
        if archive:
            _archive_frame(conn, table, frame, replace=True)
        total += len(frame)
        _record_import(conn, table, f"hk_new_financials/{relative}", table, len(frame))
        _upsert_frame(conn, _prepare_hk_csmar(frame, mapping), source_name=f"csmar_hk_{label}")
    return total


def _derive_fields(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        UPDATE annual_financials
        SET gross_profit = revenue - oper_cost
        WHERE gross_profit IS NULL AND revenue IS NOT NULL AND oper_cost IS NOT NULL;
        UPDATE annual_financials
        SET fcf = n_cashflow_act - ABS(c_pay_acq_const_fiolta)
        WHERE n_cashflow_act IS NOT NULL AND c_pay_acq_const_fiolta IS NOT NULL;
        UPDATE annual_financials
        SET base_share = share_capital
        WHERE base_share IS NULL AND share_capital IS NOT NULL;
        UPDATE stocks
        SET shares_m = (
            SELECT af.base_share FROM annual_financials af
            WHERE af.ts_code=stocks.ts_code AND af.report_type='annual' AND af.base_share>0
            ORDER BY af.fiscal_year DESC LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM annual_financials af
            WHERE af.ts_code=stocks.ts_code AND af.report_type='annual' AND af.base_share>0
        );
        UPDATE annual_financials
        SET data_quality='suspect_balance_sheet_identity'
        WHERE total_assets IS NOT NULL AND total_liab IS NOT NULL
          AND total_hldr_eqy_exc_min_int IS NOT NULL
          AND ABS(total_assets-total_liab-total_hldr_eqy_exc_min_int-COALESCE(minority_int,0))
              / MAX(ABS(total_assets),1) > 0.05;
        UPDATE annual_financials
        SET data_quality='suspect_extreme_unit_ratio'
        WHERE total_assets > 0 AND (
          ABS(COALESCE(total_hldr_eqy_exc_min_int,0)) > total_assets * 10
          OR ABS(COALESCE(total_liab,0)) > total_assets * 10
          OR ABS(COALESCE(money_cap,0)) > total_assets * 2
        );
        """
    )


def validate_database(conn: sqlite3.Connection) -> dict:
    findings: list[str] = []
    warnings: list[str] = []
    quick = conn.execute("PRAGMA quick_check").fetchone()[0]
    if quick != "ok":
        findings.append(f"sqlite_quick_check:{quick}")
    invalid_years = conn.execute(
        """
        SELECT COUNT(*) FROM annual_financials
        WHERE fiscal_year < 1900 OR fiscal_year > ?
           OR (report_type='annual' AND fiscal_year > ?)
        """,
        (CURRENT_YEAR, CURRENT_YEAR - 1),
    ).fetchone()[0]
    if invalid_years:
        findings.append(f"invalid_fiscal_year_rows:{invalid_years}")
    duplicate_rows = conn.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT ts_code,fiscal_year,report_type,COUNT(*) n
          FROM annual_financials GROUP BY 1,2,3 HAVING n>1
        )
        """
    ).fetchone()[0]
    if duplicate_rows:
        findings.append(f"duplicate_financial_keys:{duplicate_rows}")
    hard_unit_rows = conn.execute(
        """
        SELECT COUNT(*) FROM annual_financials
        WHERE total_assets > 0
        AND ABS(total_assets-total_liab-total_hldr_eqy_exc_min_int-COALESCE(minority_int,0))
              / MAX(ABS(total_assets),1) > 0.05
        AND (
          ABS(COALESCE(total_hldr_eqy_exc_min_int,0)) > total_assets * 10000
          OR ABS(COALESCE(total_liab,0)) > total_assets * 10000
          OR ABS(COALESCE(money_cap,0)) > total_assets * 10000
        )
        """
    ).fetchone()[0]
    if hard_unit_rows:
        findings.append(f"hard_unit_violation_rows:{hard_unit_rows}")
    suspect_rows = conn.execute(
        "SELECT COUNT(*) FROM annual_financials WHERE data_quality LIKE 'suspect_%'"
    ).fetchone()[0]
    if suspect_rows:
        warnings.append(f"source_rows_downgraded_to_suspect:{suspect_rows}")
    gree_cols = ",".join(GREE_2024_EXPECTED)
    row = conn.execute(
        f"SELECT {gree_cols} FROM annual_financials "
        "WHERE ts_code='000651.SZ' AND fiscal_year=2024 AND report_type='annual'"
    ).fetchone()
    if row is None:
        findings.append("gree_2024_missing")
    else:
        for field, expected in GREE_2024_EXPECTED.items():
            actual = row[field]
            tolerance = max(0.01, abs(expected) * 1e-8)
            if actual is None or not math.isclose(float(actual), expected, abs_tol=tolerance):
                findings.append(f"gree_2024_{field}:expected={expected}:actual={actual}")
    if "data_source_code" in _table_columns(conn, "stocks"):
        satellite = conn.execute(
            "SELECT market,currency,data_source_code FROM stocks WHERE ts_code='900936.SH'"
        ).fetchone()
        if satellite is None:
            findings.append("ordos_b_satellite_identity_missing")
        elif tuple(satellite) != ("B", "USD", "600295.SH"):
            findings.append(
                "ordos_b_satellite_identity_invalid:"
                f"{satellite['market']}:{satellite['currency']}:{satellite['data_source_code']}"
            )
    source_count = conn.execute(
        "SELECT COUNT(*) FROM source_imports WHERE status='IMPORTED' AND row_count>0"
    ).fetchone()[0]
    if source_count < 10:
        findings.append(f"source_dataset_coverage_too_small:{source_count}")
    archive_row = conn.execute(
        "SELECT value FROM database_metadata WHERE key='archive_sources'"
    ).fetchone()
    archive_sources = bool(archive_row and archive_row[0] == "true")
    if archive_sources:
        source_tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'source_%' AND name!='source_imports'"
        ).fetchone()[0]
        blob_stats = conn.execute(
            "SELECT COUNT(*),COALESCE(SUM(size_bytes),0) FROM source_file_archives"
        ).fetchone()
        if source_tables < 10:
            findings.append(f"embedded_source_tables_too_small:{source_tables}")
        if blob_stats[0] < 5 or blob_stats[1] < 500_000_000:
            findings.append(
                f"embedded_unique_source_files_incomplete:{blob_stats[0]}:{blob_stats[1]}"
            )
    status = "PASS" if not findings else "FAIL"
    payload = {
        "schema_version": "database-validation.v1",
        "status": status,
        "findings": findings,
        "warnings": warnings,
        "counts": {
            "stocks": conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0],
            "annual_financials": conn.execute("SELECT COUNT(*) FROM annual_financials").fetchone()[0],
            "source_datasets": source_count,
            "embedded_source_files": conn.execute(
                "SELECT COUNT(*) FROM source_file_archives"
            ).fetchone()[0],
        },
        "spot_check": {"company": "000651.SZ", "fiscal_year": 2024, "source": "2024 annual report"},
    }
    conn.execute(
        "INSERT INTO database_validation_runs(status,findings_json) VALUES(?,?)",
        (status, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
    )
    return payload


def build_database(args: argparse.Namespace) -> int:
    template = Path(args.template_db).resolve()
    output = Path(args.output_db).resolve()
    data_root = Path(args.data_root).resolve()
    if not template.is_file():
        raise FileNotFoundError(template)
    if output.exists():
        raise FileExistsError(f"staging database already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(f"file:{template}?mode=ro", uri=True)
    conn = sqlite3.connect(output)
    try:
        source_conn.backup(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA temp_store=MEMORY")
        _reset_database(conn)
        conn.execute(
            "INSERT OR REPLACE INTO database_metadata(key,value) VALUES('archive_sources',?)",
            ("true" if args.archive_sources else "false",),
        )
        import_tushare_a(conn, data_root, archive=args.archive_sources)
        import_tushare_hk(conn, data_root, archive=args.archive_sources)
        import_csmar_a(conn, data_root, archive=args.archive_sources)
        import_csmar_hk(conn, data_root, archive=args.archive_sources)
        if args.archive_sources:
            archive_unique_source_files(conn, data_root)
        _derive_fields(conn)
        conn.execute("ANALYZE")
        result = validate_database(conn)
        conn.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] != "PASS":
            return 2
    finally:
        source_conn.close()
        conn.close()
    return 0


def validate_command(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(Path(args.db).resolve())
    conn.row_factory = sqlite3.Row
    try:
        result = validate_database(conn)
        conn.commit()
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


def promote_database(args: argparse.Namespace) -> int:
    staging = Path(args.staging_db).resolve()
    active = Path(args.active_db).resolve()
    if not staging.is_file() or not active.is_file():
        raise FileNotFoundError("both staging and active databases must exist")
    conn = sqlite3.connect(staging)
    conn.row_factory = sqlite3.Row
    try:
        latest = conn.execute(
            "SELECT status FROM database_validation_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None or latest["status"] != "PASS":
            raise RuntimeError("staging database has no current PASS validation")
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("staging database failed quick_check")
    finally:
        conn.close()
    previous = active.with_suffix(active.suffix + ".pre_consolidation")
    if previous.exists():
        raise FileExistsError(previous)
    active.replace(previous)
    try:
        staging.replace(active)
    except Exception:
        previous.replace(active)
        raise
    previous.unlink()
    print(f"promoted={active}")
    return 0


def purge_sources(args: argparse.Namespace) -> int:
    db = Path(args.db).resolve()
    data_root = Path(args.data_root).resolve()
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        latest = conn.execute(
            "SELECT status FROM database_validation_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None or latest["status"] != "PASS":
            raise RuntimeError("active database has no PASS validation; source purge refused")
        source_count = conn.execute(
            "SELECT COUNT(*) FROM source_imports WHERE status='IMPORTED' AND row_count>0"
        ).fetchone()[0]
        if source_count < 10:
            raise RuntimeError("source import manifest is incomplete; source purge refused")
        archive_mode = conn.execute(
            "SELECT value FROM database_metadata WHERE key='archive_sources'"
        ).fetchone()
        if archive_mode is None or archive_mode[0] != "true":
            raise RuntimeError("database does not embed source tables; source purge refused")
        blob_stats = conn.execute(
            "SELECT COUNT(*),COALESCE(SUM(size_bytes),0) FROM source_file_archives"
        ).fetchone()
        if blob_stats[0] < 5 or blob_stats[1] < 500_000_000:
            raise RuntimeError("unique source file archive is incomplete; source purge refused")
    finally:
        conn.close()
    targets = [data_root / name for name in SOURCE_DIR_NAMES]
    missing = [str(path) for path in targets if not path.is_dir()]
    if missing:
        raise FileNotFoundError(f"expected source directories missing: {missing}")
    for target in targets:
        shutil.rmtree(target)
        print(f"removed={target}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="build and validate an isolated staging database")
    build.add_argument("--template-db", required=True)
    build.add_argument("--output-db", required=True)
    build.add_argument("--data-root", required=True)
    build.add_argument("--archive-sources", action=argparse.BooleanOptionalAction, default=True)
    build.set_defaults(func=build_database)
    validate = sub.add_parser("validate", help="validate an existing consolidated database")
    validate.add_argument("--db", required=True)
    validate.set_defaults(func=validate_command)
    promote = sub.add_parser("promote", help="atomically replace the active database")
    promote.add_argument("--staging-db", required=True)
    promote.add_argument("--active-db", required=True)
    promote.set_defaults(func=promote_database)
    purge = sub.add_parser("purge-sources", help="remove imported external source directories")
    purge.add_argument("--db", required=True)
    purge.add_argument("--data-root", required=True)
    purge.set_defaults(func=purge_sources)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
