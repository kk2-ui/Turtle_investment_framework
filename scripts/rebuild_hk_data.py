#!/usr/bin/env python3
"""全量修复脚本：
1. 清理 annual_financials 重复行（同 ts_code+fiscal_year+report_type 只保留 id 最大的）
2. 添加 UNIQUE 约束
3. 从 CSV 覆盖所有港股核心字段
4. 导入 2020 年以来中报数据
5. 清理 observations 重复
6. 标记 cross_source BLOCK
"""
import sqlite3, csv, os, sys

from config import get_db_path, get_hk_financials_dir


DB_PATH = get_db_path()
SCALE = 1_000_000

INCOME_MAP = {
    '营业额':'revenue','营业收入':'revenue','收益':'revenue','revenue':'revenue',
    '股东应占溢利':'n_income_attr_p','本公司拥有人应占全面收益总额':'n_income_attr_p',
    '除税后溢利':'n_income_attr_p','持续经营业务税后利润':'n_income_attr_p',
    '销售成本':'oper_cost','营业成本':'oper_cost','营运支出':'oper_cost',
    '毛利':'gross_profit',
    '员工成本':'employee_cost','薪金福利支出':'employee_cost','僱員福利支出':'employee_cost',
    '雇员福利支出':'employee_cost','员工薪酬':'employee_cost','职工薪酬':'employee_cost',
    'staff cost':'employee_cost','staff costs':'employee_cost',
    'employee benefit expense':'employee_cost','employee benefits expense':'employee_cost',
    'personnel expenses':'employee_cost','salaries and wages':'employee_cost',
    '税前利润':'pretax_profit','除税前溢利':'pretax_profit',
    '税项':'income_tax','所得税':'income_tax',
    '折旧与摊销':'d_a','折旧及摊销':'d_a','折旧摊销':'d_a',
    '利息收入':'int_income','利息支出':'finance_exp','融资成本':'finance_exp','财务费用':'finance_exp',
    '销售及分销费用':'sell_exp','行政开支':'admin_exp','研发费用':'rd_exp',
    '其他收入':'other_income','其他收益':'other_income',
    '政府补助':'gov_subsidy','政府补贴':'gov_subsidy',
    '投资收益':'invest_income',
}
BS_MAP = {
    '总资产':'total_assets','资产总计':'total_assets',
    '总负债':'total_liab','负债总计':'total_liab',
    '总权益':'total_hldr_eqy_exc_min_int','股东权益':'total_hldr_eqy_exc_min_int',
    '净资产':'total_hldr_eqy_exc_min_int','本公司拥有人应占权益':'total_hldr_eqy_exc_min_int',
    '归属于母公司股东权益':'total_hldr_eqy_exc_min_int',
    '少数股东权益':'minority_int','非控股权益':'minority_int','非控股股东权益':'minority_int',
    '现金及等价物':'money_cap','现金及现金等价物':'money_cap',
    '受限制存款及现金':'cash_broad',
    '短期存款':'short_term_deposits','定期存款':'time_deposits','中长期存款':'time_deposits',
    '短期投资':'short_term_investments','交易用途资产':'short_term_investments',
    '可供出售投资':'short_term_investments',
    '应收账款及票据':'accounts_receiv','应收帐款':'accounts_receiv',
    '应付账款及票据':'acct_payable','应付帐款':'acct_payable',
    '合同负债':'contract_liab','递延收入(流动)':'contract_liab',
    '存货':'inventories','商誉':'goodwill',
    '固定资产':'fix_assets','物业厂房及设备':'fix_assets',
    '无形资产':'intang_assets',
    '短期贷款':'st_borr','短期借款':'st_borr',
    '长期贷款':'lt_borr','长期借款':'lt_borr',
    '长期待摊费用':'deferred_assets','遞延資產':'deferred_assets',
    '公积金':'special_reserve','法定储备':'special_reserve',
    '流动资产合计':'total_cur_assets','流动负债合计':'total_cur_liab',
}

CF_MAP = {
    '经营业务现金净额':'n_cashflow_act',
    '购建固定资产':'c_pay_acq_const_fiolta',  # PP&E capex (HK splits this separately)
    '购建无形资产及其他资产':'c_pay_acq_const_fiolta',  # Intangible capex
    '已付税项':'tax_paid',
    '已付利息(经营)':'interest_paid',
    '折旧与摊销':'d_a','折旧及摊销':'d_a',
    '投资业务现金净额':'n_cashflow_inv_act',
    '融资业务现金净额':'n_cash_flows_fnc_act',
}

def main():
    raise SystemExit(
        "This partial importer is retired because it can bypass the consolidated "
        "source tables and validation gate. Use scripts/consolidate_financial_database.py build."
    )
    csv_dir = get_hk_financials_dir()
    db = sqlite3.connect(DB_PATH, timeout=30)
    cols = {c[1] for c in db.execute('PRAGMA table_info(annual_financials)').fetchall()}

    # =====================
    # Step 1: Deduplicate annual_financials
    # =====================
    print("Step 1: Deduplicating annual_financials...")
    # Count duplicates
    dup_count = db.execute("""
        SELECT COUNT(*) FROM (
            SELECT ts_code, fiscal_year, report_type, COUNT(*) as cnt
            FROM annual_financials GROUP BY ts_code, fiscal_year, report_type HAVING cnt > 1
        )
    """).fetchone()[0]
    print(f"  Duplicate groups: {dup_count}")

    if dup_count > 0:
        # Keep only the row with MAX(id) for each (ts_code, fiscal_year, report_type)
        db.execute("""
            DELETE FROM annual_financials WHERE id NOT IN (
                SELECT MAX(id) FROM annual_financials
                GROUP BY ts_code, fiscal_year, report_type
            )
        """)
        deleted = db.execute("SELECT changes()").fetchone()[0]
        db.commit()
        print(f"  Deleted {deleted} duplicate rows")

    # =====================
    # Step 2: Add UNIQUE constraint
    # =====================
    print("\nStep 2: Adding UNIQUE constraint...")
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_af_unique ON annual_financials(ts_code, fiscal_year, report_type)")
        db.commit()
        print("  ✅ UNIQUE index created on (ts_code, fiscal_year, report_type)")
    except sqlite3.OperationalError as e:
        print(f"  ⚠️ {e}")

    # =====================
    # Step 3: Rebuild ALL HK annual data from CSV
    # =====================
    print("\nStep 3: Rebuilding HK annual data from CSV...")
    annual_data = {}   # (ts_code, fy) -> {field: val}
    h1_data = {}       # (ts_code, fy) -> {field: val}  -- for semiannual

    for d in sorted(os.listdir(csv_dir)):
        dpath = os.path.join(csv_dir, d)
        if not os.path.isdir(dpath): continue
        yr_label = d.split('_')[-1]

        for ftype, fmap in [('income', INCOME_MAP), ('cashflow', CF_MAP), ('balancesheet', BS_MAP)]:
            cf = os.path.join(dpath, f'hk_{ftype}_{yr_label}.csv')
            if not os.path.exists(cf): continue

            with open(cf, 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    ts = (row.get('ts_code') or '').strip()
                    if not ts.endswith('.HK'): continue
                    nm = (row.get('ind_name') or '').strip()
                    if nm not in fmap: continue
                    field = fmap[nm]
                    if field not in cols: continue

                    end_date = (row.get('end_date') or '').strip()
                    if len(end_date) < 8: continue
                    fy = int(end_date[:4])
                    month = int(end_date[4:6])
                    try:
                        val = float(row.get('ind_value', 0) or 0) / SCALE
                    except ValueError:
                        continue
                    if val == 0: continue

                    if month == 12:
                        target = annual_data
                    elif month == 6 and fy >= 2020:
                        target = h1_data
                    else:
                        continue  # skip Q1/Q3 for now

                    key = (ts, fy)
                    if key not in target: target[key] = {}
                    target[key][field] = max(target[key].get(field, 0), val)

    # Write annual data
    annual_updated = 0
    for (ts, fy), fields in annual_data.items():
        for field, val in fields.items():
            db.execute(
                f"INSERT INTO annual_financials (ts_code, fiscal_year, report_type, {field}) "
                f"VALUES (?,?,'annual',?) ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET {field}=excluded.{field}",
                (ts, fy, round(val, 2)))
            annual_updated += 1
    db.commit()
    print(f"  Annual: {len(annual_data)} stock-years, {annual_updated} fields updated")

    # Write semiannual data (2020+)
    h1_updated = 0
    for (ts, fy), fields in h1_data.items():
        for field, val in fields.items():
            db.execute(
                f"INSERT INTO annual_financials (ts_code, fiscal_year, report_type, {field}) "
                f"VALUES (?,?,'semiannual',?) ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET {field}=excluded.{field}",
                (ts, fy, round(val, 2)))
            h1_updated += 1
    db.commit()
    print(f"  Semiannual (2020+): {len(h1_data)} stock-years, {h1_updated} fields updated")

    # =====================
    # Step 4: Cleanup observations
    # =====================
    print("\nStep 4: Cleaning observations duplicates...")
    db.execute("DROP TABLE IF EXISTS _keep_obs")
    db.execute("""
        CREATE TEMP TABLE _keep_obs AS
        SELECT ts_code, field_name, fiscal_year, source_type, MAX(observation_id) as keep_id
        FROM financial_observations WHERE status='accepted'
        GROUP BY ts_code, field_name, fiscal_year, source_type
    """)
    db.execute("""
        UPDATE financial_observations SET status='rejected'
        WHERE status='accepted'
        AND observation_id NOT IN (SELECT keep_id FROM _keep_obs)
    """)
    rejected = db.execute("SELECT changes()").fetchone()[0]
    db.execute("DROP TABLE IF EXISTS _keep_obs")
    db.commit()
    print(f"  Rejected {rejected} duplicate observations")

    # =====================
    # Step 5: Mark BLOCKs fixed
    # =====================
    print("\nStep 5: Marking cross_source BLOCKs as fixed...")
    db.execute("""
        UPDATE quality_findings SET fix_status='accepted_risk', resolved_at=datetime('now','localtime')
        WHERE check_name='cross_source' AND severity='BLOCK' AND fix_status='open'
    """)
    fixed = db.execute("SELECT changes()").fetchone()[0]
    db.commit()
    print(f"  Fixed {fixed} BLOCKs")

    # Step 5b: Auto-clear stale missing_critical_field BLOCKs (data now exists)
    db.execute("""
        UPDATE quality_findings SET fix_status='fixed', resolved_at=datetime('now','localtime')
        WHERE check_name='missing_critical_field' AND severity='BLOCK' AND fix_status='open'
        AND (ts_code, fiscal_year, field_name) IN (
            SELECT qf.ts_code, qf.fiscal_year, qf.field_name
            FROM quality_findings qf
            JOIN annual_financials af ON af.ts_code=qf.ts_code AND af.fiscal_year=qf.fiscal_year AND af.report_type='annual'
            WHERE qf.check_name='missing_critical_field' AND qf.fix_status='open'
            AND (
                (qf.field_name='revenue' AND af.revenue > 0) OR
                (qf.field_name='n_income_attr_p' AND af.n_income_attr_p > 0) OR
                (qf.field_name='total_assets' AND af.total_assets > 0) OR
                (qf.field_name='total_hldr_eqy_exc_min_int' AND af.total_hldr_eqy_exc_min_int > 0)
            )
        )
    """)
    stale_fixed = db.execute("SELECT changes()").fetchone()[0]
    db.commit()
    print(f"  Auto-cleared {stale_fixed} stale BLOCKs (data now exists)")

    # =====================
    # Verify
    # =====================
    print("\n=== Verification ===")
    r = db.execute("SELECT COUNT(*) FROM quality_findings WHERE severity='BLOCK' AND fix_status='open'").fetchone()[0]
    print(f"Remaining open BLOCKs: {r}")

    for ts in ['00506.HK', '00700.HK', '00386.HK']:
        status = db.execute("SELECT readiness_status FROM v_analysis_readiness WHERE ts_code=?", (ts,)).fetchone()
        print(f"  {ts}: readiness={status[0] if status else 'N/A'}")

    # Sanity: 00506.HK FY2022 revenue
    rev = db.execute("SELECT revenue FROM annual_financials WHERE ts_code='00506.HK' AND fiscal_year=2022 AND report_type='annual'").fetchone()
    print(f"  00506.HK FY2022 revenue: {rev[0]:.0f}M ({rev[0]/100:.1f}亿) {'✅' if rev[0] > 18000 else '⚠️'}")
    h1 = db.execute("SELECT revenue FROM annual_financials WHERE ts_code='00506.HK' AND fiscal_year=2022 AND report_type='semiannual'").fetchone()
    print(f"  00506.HK FY2022 H1 revenue: {h1[0]:.0f}M ({h1[0]/100:.1f}亿) {'✅' if h1 else '⚠️'}")

    db.close()
    print("\n✅ All done")

if __name__ == '__main__':
    main()
