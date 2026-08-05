#!/usr/bin/env python3
"""从 CSMAR HK 利润表导入归母净利润(直接覆盖 n_income_attr_p)、EPS。"""
import sqlite3, pandas as pd, os, warnings
warnings.filterwarnings('ignore')

from config import get_db_path, get_hk_new_financials_dir


DB_PATH = get_db_path()

def main():
    income_xlsx = os.path.join(get_hk_new_financials_dir(), "HK利润表(非金融)", "HK_STK_Income.xlsx")
    db = sqlite3.connect(DB_PATH, timeout=30)

    df = pd.read_excel(income_xlsx, header=None)
    df.columns = df.iloc[0]
    df = df.iloc[3:]  # skip 3 header rows

    # Filter: 合并报表(A) + 年报(12) + HK stocks
    df = df[df['StateTypeCode'] == 'A']
    df = df[df['CoverPeriod'].astype(str) == '12']
    df['Symbol'] = df['Symbol'].astype(str).str.strip()
    df = df[df['Symbol'].str.match(r'^\d{5}$')]  # 5-digit HK codes
    df['ts_code'] = df['Symbol'] + '.HK'
    df['fiscal_year'] = pd.to_datetime(df['EndDate']).dt.year

    updated = 0
    for _, r in df.iterrows():
        ts = r['ts_code']
        fy = r['fiscal_year']
        if pd.isna(fy): continue

        updates = {}
        # B0024 = 归属于母公司所有者的净利润 → n_income_attr_p
        parent_np = r.get('B0024')
        if pd.notna(parent_np) and parent_np != 0:
            updates['n_income_attr_p'] = round(float(parent_np) / 1_000_000, 2)

        # B002 = 净利润(合并) → as reference
        total_np = r.get('B002')
        if pd.notna(total_np) and total_np != 0:
            updates['net_profit_consolidated'] = round(float(total_np) / 1_000_000, 2)

        # B0025 = 少数股东损益
        minority = r.get('B0025')
        if pd.notna(minority):
            updates['minority_profit'] = round(float(minority) / 1_000_000, 2)

        # B003 = 基本每股收益
        eps = r.get('B003')
        if pd.notna(eps) and eps != 0:
            updates['eps'] = round(float(eps), 3)

        # B001101 = 营业收入
        rev = r.get('B001101')
        if pd.notna(rev) and rev != 0:
            updates['revenue'] = round(float(rev) / 1_000_000, 2)

        if not updates:
            continue

        # UPSERT
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

    # Verify 00506.HK
    for r in db.execute("""
        SELECT fiscal_year, n_income_attr_p, net_profit_consolidated, minority_profit, eps, revenue
        FROM annual_financials WHERE ts_code='00506.HK' AND report_type='annual' AND fiscal_year>=2021
        ORDER BY fiscal_year
    """).fetchall():
        print(f"  FY{r[0]}: parent_NP={r[1]:.0f}M total_NP={r[2]:.0f}M minority={r[3]:.0f}M eps={r[4]} rev={r[5]:.0f}M")

    # Coverage stats
    hk_total = db.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND report_type='annual'").fetchone()[0]
    np_ok = db.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND report_type='annual' AND n_income_attr_p > 0").fetchone()[0]
    print(f"\nHK NP coverage: {np_ok}/{hk_total} ({np_ok/hk_total*100:.1f}%)")
    print(f"Total rows updated: {updated}")

    db.close()
    print("✅ Done")

if __name__ == '__main__':
    main()
