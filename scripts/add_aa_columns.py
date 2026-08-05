#!/usr/bin/env python3
"""add_aa_columns.py — 为 AA 7 步计算添加 DB 列。

从 hk_financials 的 cashflow/income/balancesheet CSV 中提取细项，
补充到 annual_financials 表。
"""

import sqlite3
import os
import csv
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stock_analysis.db")
HK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "hk_financials")

# ── 新列定义 ──
NEW_COLUMNS = [
    # Step 3: V1-V5 非经常性分类 (来源: cashflow CSV)
    ("asset_disposal", "REAL", "处置固定资产/无形资产现金流入 (V1)"),        # 处置固定资产 + 出售附属公司
    ("interest_received", "REAL", "已收投资利息 (V5b)"),                     # 已收利息(投资) + 已收股息
    ("tax_paid", "REAL", "已付税项 (W3)"),                                   # 已付税项
    ("interest_paid", "REAL", "已付利息经营 (W4)"),                          # 已付利息(经营)
    ("inventory_change", "REAL", "存货变动 (增加为负)"),                      # 存货(增加)减少
    ("ar_change_cf", "REAL", "应收帐款变动 (增加为负)"),                     # 应收帐款减少
    ("ap_change_cf", "REAL", "应付帐款变动 (增加为正)"),                     # 应付帐款增加(减少)
    ("contract_change_cf", "REAL", "预收/合同负债变动"),                     # 预收账款变动 + 递延收入变动
    ("intangible_purchase", "REAL", "购建无形资产 (X1 部分)"),               # 购建无形资产及其他资产
    ("gain_asset_sale", "REAL", "出售资产之溢利 (非现金,从OCF扣除)"),       # 减:出售资产之溢利
    ("impairment_cf", "REAL", "减值及拨备 (非现金加回)"),                    # 加:减值及拨备

    # Step 4: 经营支出 (来源: income CSV)
    ("sell_dist_exp", "REAL", "销售及分销费用 (W2 部分)"),                   # 销售及分销费用
    ("admin_exp", "REAL", "行政开支 (W2 部分)"),                             # 行政开支
    ("other_income", "REAL", "其他收入 (V5)"),                               # 其他收入

    # Step 5: 资产明细 (来源: balancesheet CSV)
    ("fix_assets_gross", "REAL", "物业厂房及设备原值"),
    ("intang_assets_gross", "REAL", "无形资产原值"),
    ("restricted_cash", "REAL", "受限制存款及现金 (CC)"),
    ("inventories", "REAL", "存货"),
    ("related_party_payable", "REAL", "应付关联方款项"),
    ("related_party_receivable", "REAL", "应收关联方款项"),
]

# ── CSV 行名 → DB 列名映射 ──
# (csv_filename_pattern, ind_name_keyword, db_column, is_cashflow_style)
CSV_MAPPINGS = [
    # Cashflow items
    ("cashflow", "处置固定资产", "asset_disposal", "sum"),
    ("cashflow", "出售附属公司", "asset_disposal", "add"),
    ("cashflow", "已收利息(投资)", "interest_received", "add"),
    ("cashflow", "已收股息(投资)", "interest_received", "add"),
    ("cashflow", "已付税项", "tax_paid", "single"),
    ("cashflow", "已付利息(经营)", "interest_paid", "single"),
    ("cashflow", "存货(增加)减少", "inventory_change", "single"),
    ("cashflow", "应收帐款减少", "ar_change_cf", "single"),
    ("cashflow", "应付帐款及应计费用增加(减少)", "ap_change_cf", "single"),
    ("cashflow", "预收账款、按金及其他应付款增加(减少)", "contract_change_cf", "single"),
    ("cashflow", "递延收入(增加)减少", "contract_change_cf", "add"),
    ("cashflow", "购建固定资产", "c_pay_acq_const_fiolta", "set_abs"),  # 绝对值
    ("cashflow", "购建无形资产及其他资产", "intangible_purchase", "single"),
    ("cashflow", "减:出售资产之溢利", "gain_asset_sale", "single"),
    ("cashflow", "加:减值及拨备", "impairment_cf", "single"),

    # Income items
    ("income", "销售及分销费用", "sell_dist_exp", "single"),
    ("income", "行政开支", "admin_exp", "single"),
    ("income", "其他收入", "other_income", "single"),
    ("income", "销售成本", "oper_cost", "single"),

    # Balance Sheet items
    ("balancesheet", "物业厂房及设备", "fix_assets_gross", "single"),
    ("balancesheet", "无形资产", "intang_assets_gross", "single"),
    ("balancesheet", "受限制存款及现金", "restricted_cash", "single"),
    ("balancesheet", "存货", "inventories", "single"),
    ("balancesheet", "应付关联方款项(流动)", "related_party_payable", "single"),
    ("balancesheet", "应收关联方款项(流动)", "related_party_receivable", "single"),
]


def add_columns(conn):
    """添加新列到 annual_financials。"""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(annual_financials)")}
    for col_name, col_type, _ in NEW_COLUMNS:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE annual_financials ADD COLUMN {col_name} {col_type}")
            print(f"  + {col_name} ({col_type})")
        else:
            print(f"  = {col_name} 已存在, 跳过")


def load_csv_items(ts_code, year, csv_type):
    """从 CSV 加载某公司某年某类型的细项数据。返回 {ind_name: ind_value}。"""
    year_dir = os.path.join(HK_DATA_DIR, f"hk_financials_{year}")
    if not os.path.isdir(year_dir):
        # 尝试项目根目录下的 hk_financials
        alt_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "hk_financials", f"hk_financials_{year}")
        if os.path.isdir(alt_dir):
            year_dir = alt_dir
        if not os.path.isdir(year_dir):
            return {}

    csv_path = os.path.join(year_dir, f"hk_{csv_type}_{year}.csv")
    if not os.path.exists(csv_path):
        return {}

    items = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if len(header) < 5:
            return {}
        # 检测列顺序: cashflow/income: ts_code,end_date,name,ind_name,ind_value
        #              balancesheet:       ts_code,name,end_date,ind_name,ind_value
        col_ts = 0
        col_date = 1 if "end_date" == header[1].strip().lower() else 2
        col_name = 1 if col_date == 2 else 2  # name column position
        col_item = 3
        col_val = 4
        for row in reader:
            if len(row) < 5:
                continue
            code = row[col_ts].strip()
            end_date = row[col_date].strip()
            ind_name = row[col_item].strip()
            try:
                ind_value = float(row[col_val]) if row[col_val].strip() else 0.0
            except (ValueError, IndexError):
                continue

            # 匹配：ts_code 前缀匹配 且 年末数据 (1231)
            code_base = ts_code.split(".")[0]
            if code.startswith(code_base) and end_date.endswith("1231"):
                # CSV 单位是元，DB 单位是百万元 → 除以 1,000,000
                items[ind_name] = items.get(ind_name, 0.0) + ind_value / 1_000_000

    return items


def populate(conn, ts_codes=None):
    """为指定股票填充新列数据。"""
    if ts_codes is None:
        rows = conn.execute("SELECT DISTINCT ts_code FROM annual_financials WHERE report_type='annual'").fetchall()
        ts_codes = [r[0] for r in rows]

    # 获取可用年份范围
    year_rows = conn.execute("SELECT DISTINCT fiscal_year FROM annual_financials ORDER BY fiscal_year").fetchall()
    years = [r[0] for r in year_rows if r[0] and r[0] >= 2019]

    updated = 0
    for ts_code in ts_codes:
        for year in years:
            items = {}
            for csv_type in ["cashflow", "income", "balancesheet"]:
                items.update(load_csv_items(ts_code, year, csv_type))

            if not items:
                continue

            # 按映射规则填充列值
            updates = {}
            for csv_type, keyword, col, mode in CSV_MAPPINGS:
                val = items.get(keyword)
                if val is None:
                    continue

                if mode == "single":
                    updates[col] = val
                elif mode == "sum":
                    updates[col] = updates.get(col, 0) + val
                elif mode == "add":
                    updates[col] = updates.get(col, 0) + abs(val) if col == "asset_disposal" else updates.get(col, 0) + val
                elif mode == "set_abs":
                    # 以绝对值存储 (DB convention for capex)
                    updates[col] = abs(val) if updates.get(col) is None else updates[col]
                elif mode == "abs":
                    updates[col] = abs(val)

            if updates:
                set_clauses = ", ".join(f"{k}=?" for k in updates.keys())
                values = list(updates.values()) + [ts_code, year]
                conn.execute(
                    f"UPDATE annual_financials SET {set_clauses} WHERE ts_code=? AND fiscal_year=? AND report_type='annual'",
                    values
                )
                updated += 1

        if updated % 100 == 0:
            print(f"  ... {updated} rows updated", end="\r")

    print(f"  ✅ {updated} rows updated total")


def main():
    conn = sqlite3.connect(DB_PATH)
    print("1. 添加新列...")
    add_columns(conn)

    print("\n2. 填充数据...")
    populate(conn)

    conn.commit()
    conn.close()
    print("\n✅ Done")


if __name__ == "__main__":
    main()
