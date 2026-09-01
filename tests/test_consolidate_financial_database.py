from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from scripts.consolidate_financial_database import (
    GREE_2024_EXPECTED,
    _create_consolidation_schema,
    _prepare_csmar_a,
    _upsert_stocks,
    _upsert_frame,
    normalize_a_code,
    validate_database,
)


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE stocks (
          ts_code TEXT PRIMARY KEY, name_cn TEXT, market TEXT, currency TEXT,
          shares_m REAL
        );
        CREATE TABLE annual_financials (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts_code TEXT NOT NULL,
          fiscal_year INTEGER NOT NULL,
          report_type TEXT NOT NULL,
          revenue REAL,
          total_assets REAL,
          total_liab REAL,
          total_hldr_eqy_exc_min_int REAL,
          minority_int REAL,
          money_cap REAL,
          n_income_attr_p REAL,
          n_cashflow_act REAL,
          base_share REAL,
          dps REAL,
          data_source TEXT,
          data_quality TEXT,
          UNIQUE(ts_code,fiscal_year,report_type)
        );
        """
    )
    _create_consolidation_schema(conn)
    return conn


def test_normalize_a_code_handles_all_supported_exchanges():
    assert normalize_a_code("000651") == "000651.SZ"
    assert normalize_a_code("600585") == "600585.SH"
    assert normalize_a_code("900936") == "900936.SH"
    assert normalize_a_code("430047") == "430047.BJ"


def test_csmar_a_values_are_scaled_from_yuan_to_millions():
    columns = [f"c{i}" for i in range(265)]
    columns[0] = "证券代码"
    columns[1] = "年份"
    row = [None] * 265
    row[0] = "000651"
    row[1] = "2024"
    row[90] = 368_031_704_522.86
    row[160] = 137_416_898_946.39
    row[165] = 189_163_654_064.64
    row[227] = 32_184_570_372.28
    row[230] = 5.83
    row[256] = 29_369_250_570.66
    result = _prepare_csmar_a(pd.DataFrame([row], columns=columns)).iloc[0]
    assert result["ts_code"] == "000651.SZ"
    assert result["fiscal_year"] == 2024
    assert result["total_assets"] == pytest.approx(368_031.70452286)
    assert result["total_hldr_eqy_exc_min_int"] == pytest.approx(137_416.89894639)
    assert result["revenue"] == pytest.approx(189_163.65406464)
    assert result["n_income_attr_p"] == pytest.approx(32_184.57037228)
    assert result["eps"] == 5.83
    assert result["n_cashflow_act"] == pytest.approx(29_369.25057066)


def test_later_authoritative_source_overwrites_value_but_not_with_null():
    conn = _database()
    _upsert_frame(
        conn,
        pd.DataFrame([{
            "ts_code": "000651.SZ", "fiscal_year": 2024, "report_type": "annual",
            "revenue": 1.0, "n_income_attr_p": 2.0,
        }]),
        source_name="fallback",
    )
    _upsert_frame(
        conn,
        pd.DataFrame([{
            "ts_code": "000651.SZ", "fiscal_year": 2024, "report_type": "annual",
            "revenue": 189_163.65406464, "n_income_attr_p": None,
        }]),
        source_name="authoritative",
    )
    row = conn.execute(
        "SELECT revenue,n_income_attr_p FROM annual_financials"
    ).fetchone()
    assert row["revenue"] == 189_163.65406464
    assert row["n_income_attr_p"] == 2.0


def test_source_stock_metadata_does_not_overwrite_curated_satellite_identity():
    conn = _database()
    conn.execute("ALTER TABLE stocks ADD COLUMN data_source_code TEXT")
    conn.execute(
        "INSERT INTO stocks(ts_code,name_cn,market,currency,shares_m,data_source_code) "
        "VALUES('900936.SH','鄂尔多斯B','B','USD',2798.776254,'600295.SH')"
    )
    _upsert_stocks(
        conn,
        pd.DataFrame([{
            "ts_code": "900936.SH", "name_cn": "鄂绒B股",
            "market": "A", "currency": "RMB",
        }]),
    )
    row = conn.execute("SELECT * FROM stocks WHERE ts_code='900936.SH'").fetchone()
    assert row["name_cn"] == "鄂尔多斯B"
    assert row["market"] == "B"
    assert row["currency"] == "USD"
    assert row["data_source_code"] == "600295.SH"


def test_validation_accepts_annual_report_spot_check_and_rejects_bad_year():
    conn = _database()
    fields = {
        "ts_code": "000651.SZ", "fiscal_year": 2024, "report_type": "annual",
        **GREE_2024_EXPECTED,
    }
    _upsert_frame(conn, pd.DataFrame([fields]), source_name="csmar_a_annual_panel")
    for index in range(10):
        conn.execute(
            "INSERT INTO source_imports(dataset,logical_source,database_table,row_count,status) "
            "VALUES(?,?,?,?, 'IMPORTED')",
            (f"source_{index}", f"source/{index}", f"table_{index}", 1),
        )
    assert validate_database(conn)["status"] == "PASS"
    conn.execute(
        "INSERT INTO annual_financials(ts_code,fiscal_year,report_type,total_assets) "
        "VALUES('00001.HK',1,'annual',100)"
    )
    result = validate_database(conn)
    assert result["status"] == "FAIL"
    assert "invalid_fiscal_year_rows:1" in result["findings"]
