#!/usr/bin/env python3
"""CSMAR HK 全量导入：利润表 + 资产负债表 + 现金流量表 + 披露指标。"""
import sqlite3, pandas as pd, os, warnings, glob
warnings.filterwarnings('ignore')

from config import get_db_path, get_hk_new_financials_dir


DB = get_db_path()
SCALE = 1_000_000  # CSMAR values are in 元 → DB uses 百万元

# ── Field mappings ──
INCOME_FIELDS = {
    'B001101': 'revenue',           # 营业收入
    'B001201': 'oper_cost',         # 营业成本
    'B001209': 'sell_exp',          # 销售费用
    'B001210': 'admin_exp',         # 管理费用
    'B001211': 'finance_exp',       # 财务费用
    'B001302': 'invest_income',     # 投资收益
    'B0013': 'operate_profit',      # 营业利润
    'B001': 'pretax_profit',        # 利润总额
    'B0021': 'income_tax',          # 所得税
    'B002': 'net_profit_consolidated',  # 合并净利润
    'B0024': 'n_income_attr_p',     # 归母净利润 ★ 覆盖
    'B0025': 'minority_profit',     # 少数股东损益
    'B003': 'eps',                  # 基本每股收益
    'B004': 'eps_diluted',          # 稀释每股收益
}

BS_FIELDS = {
    'A001101': 'money_cap',         # 货币资金
    'A001107': 'trading_fin_assets',# 交易性金融资产
    'A001111': 'accounts_receiv',   # 应收账款
    'A001112': 'prepayments',       # 预付款项
    'A001121': 'other_receiv',      # 其他应收款
    'A001123': 'inventories',       # 存货
    'A0011': 'total_cur_assets',    # 流动资产合计
    'A0012': 'total_non_cur_assets',# 非流动资产合计
    'A001': 'total_assets',         # 资产总计 (FIX: was A001212=固定资产净额)
    'A001212': 'fix_assets',        # 固定资产净额 (FIX: was A001217=油气资产)
    'A001205': 'lt_eqt_invest',     # 长期股权投资
    'A001220': 'goodwill',          # 商誉净额 (FIX: was A001213=在建工程净额)
    'A001218': 'intang_assets',     # 无形资产净额
    'A002101': 'st_borr',           # 短期借款
    'A002108': 'acct_payable',      # 应付账款 (FIX: was A002113=应交税费)
    'A002109': 'adv_receipts',      # 预收款项 (FIX: was A002117=不存在)
    # 注: CSMAR HK 无专用合同负债字段(A002115=应付股利不可用)，contract_liab 从缺
    'A0021': 'total_cur_liab',      # 流动负债合计
    'A002201': 'lt_borr',           # 长期借款
    'A0022': 'total_non_cur_liab',  # 非流动负债合计
    'A002': 'total_liab',           # 负债合计
    'A003101': 'share_capital',     # 实收资本
    'A0031': 'total_hldr_eqy_exc_min_int',  # 归母权益
    'A0032': 'minority_int',        # 少数股东权益
    'A003': 'total_equity',         # 所有者权益合计
}

CF_FIELDS = {
    'C001': 'n_cashflow_act',       # OCF (经营活动CF净额)
    'C002006': 'c_pay_acq_const_fiolta',  # Capex (全额!) ★
    'C001020': 'cash_paid_employees', # 支付给职工现金(现金制!) ★
    'C001021': 'tax_paid',          # 支付的各项税费
    'C002002': 'invest_income_cf',  # 取得投资收益收到的现金
    'C002003': 'asset_disposal_cf', # 处置固定资产收回的现金
    'C002': 'n_cashflow_inv_act',   # 投资活动CF净额 (FIX: was C0021=现金流入小计)
    'C003': 'n_cash_flows_fnc_act', # 筹资活动CF净额 (FIX: was C0031=现金流入小计)
    # 间接法调整项
    'C001014': 'cash_paid_suppliers', # 购买商品接受劳务支付的现金
}

DISC_FIELDS = {
    'DPS': 'dps',                   # 每股派息(元/股, 不需除SCALE)
    'IssueCapPE': 'base_share',     # 发行股数(年度) ★ 需除SCALE→百万股
    'Deprec': 'd_a',                # 折旧(总额,元, 需除SCALE)
    'TotalDividend': 'dividends_paid', # 股息总额(元, 需除SCALE)
    'TurnoverGrowth': 'revenue_growth_pct',  # 营收增长率(%)
    'NPGrowth': 'np_growth_pct',    # NP增长率(%)
    'TaxRate': 'tax_rate_pct',      # 税率(%)
}

# Fields that should NOT be divided by SCALE (per-share or percentage data)
PER_SHARE_FIELDS = {'eps', 'eps_diluted', 'dps', 'revenue_growth_pct', 'np_growth_pct', 'tax_rate_pct'}


def read_csmar(xlsx_path):
    """Read CSMAR STATA-export xlsx, return DataFrame with English headers."""
    df = pd.read_excel(xlsx_path, header=None)
    df.columns = df.iloc[0]
    df = df.iloc[3:]
    df['Symbol'] = df['Symbol'].astype(str).str.strip()
    df = df[df['Symbol'].str.match(r'^\d{5}$')]
    df['ts_code'] = df['Symbol'] + '.HK'
    df['fiscal_year'] = pd.to_datetime(df['EndDate']).dt.year
    return df


def import_sheet(db, df, field_map, label):
    """Import fields from CSMAR dataframe to annual_financials."""
    # Filter: 合并报表(A) + 年报(12) — if these columns exist
    if 'StateTypeCode' in df.columns:
        df = df[df['StateTypeCode'] == 'A']
    if 'CoverPeriod' in df.columns:
        df = df[df['CoverPeriod'].astype(str) == '12']

    updated = 0
    for _, r in df.iterrows():
        ts = r['ts_code']
        fy = r['fiscal_year']
        if pd.isna(fy): continue

        updates = {}
        for csmar_col, db_col in field_map.items():
            val = r.get(csmar_col)
            if pd.isna(val) or val == 0: continue
            if db_col in PER_SHARE_FIELDS:
                updates[db_col] = round(float(val), 3)  # 每股/百分比，不除SCALE
            elif db_col == 'base_share':
                updates[db_col] = round(float(val) / SCALE, 2)  # 股数→百万股
            else:
                updates[db_col] = round(float(val) / SCALE, 2)  # 金额元→百万元
            if db_col == 'sell_exp':
                updates['sell_dist_exp'] = updates[db_col]

        if not updates: continue

        cols = list(updates.keys())
        vals = list(updates.values())
        db.execute(f"""
            INSERT INTO annual_financials (ts_code, fiscal_year, report_type, {', '.join(cols)})
            VALUES (?, ?, 'annual', {', '.join('?' * len(cols))})
            ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET
            {', '.join(f'{c}=excluded.{c}' for c in cols)}
        """, [ts, fy] + vals)
        updated += 1

    db.commit()
    print(f"  {label}: {updated} rows")
    return updated


def ensure_columns(db, field_map):
    existing = {c[1] for c in db.execute('PRAGMA table_info(annual_financials)').fetchall()}
    for db_col in field_map.values():
        if db_col not in existing:
            try:
                db.execute(f'ALTER TABLE annual_financials ADD COLUMN {db_col} REAL')
                print(f"    Added column: {db_col}")
            except sqlite3.OperationalError:
                pass


def main():
    base_dir = get_hk_new_financials_dir()
    db = sqlite3.connect(DB, timeout=30)

    # ── Income Statement ──
    print("=== Income Statement ===")
    ensure_columns(db, INCOME_FIELDS)
    for xlsx in sorted(glob.glob(f'{base_dir}/HK利润表*/*.xlsx')):
        df = read_csmar(xlsx)
        import_sheet(db, df, INCOME_FIELDS, os.path.basename(xlsx))

    # ── Balance Sheet ──
    print("\n=== Balance Sheet ===")
    ensure_columns(db, BS_FIELDS)
    for xlsx in sorted(glob.glob(f'{base_dir}/HK资产负债表*/*.xlsx')):
        df = read_csmar(xlsx)
        import_sheet(db, df, BS_FIELDS, os.path.basename(xlsx))

    # ── Cash Flow ──
    print("\n=== Cash Flow ===")
    ensure_columns(db, CF_FIELDS)
    for xlsx in sorted(glob.glob(f'{base_dir}/HK现金流量表/*.xlsx')):
        df = read_csmar(xlsx)
        import_sheet(db, df, CF_FIELDS, os.path.basename(xlsx))

    # ── Disclosure Index ──
    print("\n=== Disclosure Index ===")
    ensure_columns(db, DISC_FIELDS)
    for xlsx in sorted(glob.glob(f'{base_dir}/HK上市披露指标/*.xlsx')):
        df = read_csmar(xlsx)
        import_sheet(db, df, DISC_FIELDS, os.path.basename(xlsx))

    # ── Verify ──
    print("\n=== Verification ===")
    total = db.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND report_type='annual'").fetchone()[0]
    for col, label in [('n_income_attr_p','归母NP'),('n_cashflow_act','OCF'),
                        ('c_pay_acq_const_fiolta','Capex'),('base_share','股本'),
                        ('dps','DPS'),('d_a','折旧'),('total_assets','总资产')]:
        ok = db.execute(f"SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND report_type='annual' AND {col} > 0").fetchone()[0]
        print(f"  {label:8s} ({col}): {ok}/{total} ({ok/total*100:.1f}%)")

    # 00506.HK spot check
    print("\n=== 00506.HK ===")
    for r in db.execute("""
        SELECT fiscal_year, n_income_attr_p, minority_profit, n_cashflow_act,
               c_pay_acq_const_fiolta, base_share, dps, cash_paid_employees
        FROM annual_financials WHERE ts_code='00506.HK' AND report_type='annual'
        AND fiscal_year>=2022 ORDER BY fiscal_year
    """).fetchall():
        print(f"  FY{r[0]}: NP={r[1]:.0f}M minority={r[2]:.0f}M OCF={r[3]:.0f}M capex={r[4]:.0f}M shares={r[5]:.0f}M dps={r[6]} emp_pay={r[7]}")

    db.close()
    print("\n✅ All done")


if __name__ == '__main__':
    main()
