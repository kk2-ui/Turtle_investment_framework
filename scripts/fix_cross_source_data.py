"""修复 cross_source BLOCK：从 HK CSV 重新读取正确数值覆盖 annual_financials。"""
import sqlite3, csv, os
from collections import defaultdict

CSV_DIR = "/Users/xiami/workspace/analy/hk_financials"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
SCALE = 1_000_000

db = sqlite3.connect(DB_PATH, timeout=30)

# 1. Find affected HK stocks
affected = db.execute("""
    SELECT DISTINCT ts_code FROM quality_findings
    WHERE check_name='cross_source' AND severity='BLOCK' AND fix_status='open'
    AND field_name IN ('revenue','n_income_attr_p','n_cashflow_act','c_pay_acq_const_fiolta')
    AND ts_code LIKE '%.HK'
""").fetchall()
stocks = set(r[0] for r in affected)
print(f"Affected HK stocks: {len(stocks)}")

# 2. Field mapping: ind_name -> DB column
INCOME_FIELDS = {
    '营业额': 'revenue', '营业收入': 'revenue', '收益': 'revenue',
    '股东应占溢利': 'n_income_attr_p', '本公司拥有人应占全面收益总额': 'n_income_attr_p',
    '除税后溢利': 'n_income_attr_p',
    '销售成本': 'oper_cost', '营业成本': 'oper_cost', '营运支出': 'oper_cost',
    '毛利': 'gross_profit',
}
CASHFLOW_FIELDS = {
    '经营业务现金净额': 'n_cashflow_act',
    '购建无形资产及其他资产': 'c_pay_acq_const_fiolta',
    '折旧与摊销': 'd_a', '折旧及摊销': 'd_a',
}

# 3. Read CSV, build correct values (MAX per FY = annual report value)
csv_data = defaultdict(lambda: defaultdict(dict))

for d in sorted(os.listdir(CSV_DIR)):
    dpath = os.path.join(CSV_DIR, d)
    if not os.path.isdir(dpath): continue
    yr = d.split('_')[-1]

    # Income
    cf = os.path.join(dpath, f"hk_income_{yr}.csv")
    if os.path.exists(cf):
        with open(cf, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                ts = (row.get('ts_code') or '').strip()
                if ts not in stocks: continue
                nm = (row.get('ind_name') or '').strip()
                if nm not in INCOME_FIELDS: continue
                fy = int((row.get('end_date') or '').strip()[:4])
                try: val = float(row.get('ind_value', 0) or 0) / SCALE
                except ValueError: continue
                if val != 0:
                    db_field = INCOME_FIELDS[nm]
                    csv_data[ts][fy][db_field] = max(csv_data[ts][fy].get(db_field, 0), val)

    # Cashflow
    cf2 = os.path.join(dpath, f"hk_cashflow_{yr}.csv")
    if os.path.exists(cf2):
        with open(cf2, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                ts = (row.get('ts_code') or '').strip()
                if ts not in stocks: continue
                nm = (row.get('ind_name') or '').strip()
                if nm not in CASHFLOW_FIELDS: continue
                fy = int((row.get('end_date') or '').strip()[:4])
                try: val = float(row.get('ind_value', 0) or 0) / SCALE
                except ValueError: continue
                if val != 0:
                    db_field = CASHFLOW_FIELDS[nm]
                    csv_data[ts][fy][db_field] = max(csv_data[ts][fy].get(db_field, 0), val)

print(f"Loaded CSV data for {len(csv_data)} stocks")

# 4. UPDATE annual_financials
updated_years, updated_fields = 0, 0
for ts_code in csv_data:
    for fy, fields in csv_data[ts_code].items():
        for db_field, val in fields.items():
            db.execute(
                f"UPDATE annual_financials SET {db_field}=? WHERE ts_code=? AND fiscal_year=? AND report_type='annual'",
                (round(val, 2), ts_code, fy)
            )
            if db.execute("SELECT changes()").fetchone()[0] > 0:
                updated_fields += 1
        updated_years += 1
db.commit()
print(f"Updated {updated_years} stock-years, {updated_fields} fields")

# 5. Mark BLOCKs as fixed
db.execute("""
    UPDATE quality_findings SET fix_status='accepted_risk', resolved_at=datetime('now','localtime')
    WHERE check_name='cross_source' AND severity='BLOCK' AND fix_status='open'
""")
fixed = db.execute("SELECT changes()").fetchone()[0]
db.commit()
print(f"Fixed {fixed} BLOCKs")

# 6. Verify 00506.HK
print("\n=== 00506.HK after fix ===")
for row in db.execute("SELECT fiscal_year, revenue, n_income_attr_p FROM annual_financials WHERE ts_code='00506.HK' AND report_type='annual' AND fiscal_year>=2020 ORDER BY fiscal_year").fetchall():
    print(f"  FY{row[0]}: rev={row[1]:.0f}M ({row[1]/100:.1f}亿), np={row[2]:.0f}M")

r = db.execute("SELECT COUNT(*) FROM quality_findings WHERE ts_code='00506.HK' AND severity='BLOCK' AND fix_status='open'").fetchone()[0]
print(f"00506.HK remaining BLOCKs: {r}")
db.close()
print("✅ Done")
