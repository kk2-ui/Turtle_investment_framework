#!/usr/bin/env python3
"""从 hk_fina_indicator parquet 导入股本/EPS/DPS/BPS 到 stocks 和 annual_financials。"""
import sqlite3, os, sys
import pandas as pd

from config import get_db_path, get_hk_financials_dir


DB_PATH = get_db_path()
FX = 0.9346  # HKD → RMB

def ensure_columns(db):
    """Add missing columns to annual_financials."""
    existing = {c[1] for c in db.execute('PRAGMA table_info(annual_financials)').fetchall()}
    needed = ['bps','pe_ttm','pb_ttm','payout_ratio','roe','roa','gross_margin','net_margin',
              'debt_ratio','current_ratio','ocf_sales_ratio',
              'inventory_turnover_days','ar_turnover_days','asset_turnover_days']
    for col in needed:
        if col not in existing:
            try:
                db.execute(f'ALTER TABLE annual_financials ADD COLUMN {col} REAL')
                print(f"  Added column: {col}")
            except sqlite3.OperationalError:
                pass

def main():
    hk_dir = get_hk_financials_dir()
    db = sqlite3.connect(DB_PATH, timeout=30)
    ensure_columns(db)

    # Collect all parquet files
    pq_files = []
    for d in sorted(os.listdir(hk_dir)):
        dpath = os.path.join(hk_dir, d)
        if not os.path.isdir(dpath): continue
        yr = d.split('_')[-1]
        pq = os.path.join(dpath, f'hk_fina_indicator_{yr}.parquet')
        if os.path.exists(pq):
            pq_files.append(pq)

    print(f"Found {len(pq_files)} parquet files")

    # Process each file
    total_updated = 0
    total_stocks_updated = 0

    for pq in pq_files:
        df = pd.read_parquet(pq)
        yr = pq.split('_')[-1].replace('.parquet', '')

        # Map: fiscal_year is in 'fiscal_year' column
        if 'fiscal_year' not in df.columns:
            continue

        for _, row in df.iterrows():
            ts_code = str(row.get('ts_code', '')).strip()
            if not ts_code.endswith('.HK'):
                continue

            # fiscal_year in Tushare hk_fina_indicator = period MONTH (12=annual, 6=mid-year)
            # The actual calendar year is in end_date (e.g., "20241231")
            ed = str(row.get('end_date', ''))
            if len(ed) < 8:
                continue
            fy = int(ed[:4])
            period = int(ed[4:6])
            # Only import annual data (period=12), skip interim reports
            if period != 12:
                continue

            # Update stocks.shares_m (take the latest value)
            shares = row.get('issued_common_shares')
            if pd.notna(shares) and shares > 0:
                shares_m = float(shares) / 1_000_000  # shares → 百万股
                db.execute("""
                    UPDATE stocks SET shares_m = MAX(COALESCE(shares_m, 0), ?)
                    WHERE ts_code = ?
                """, (round(shares_m, 2), ts_code))
                if db.execute("SELECT changes()").fetchone()[0] > 0:
                    total_stocks_updated += 1

            # Build updates for annual_financials
            updates = {}

            # Core financials from parquet (fill gaps where CSV is missing)
            # holder_profit = 归母净利润, operate_income = 营业收入
            hp = row.get('holder_profit')
            if pd.notna(hp):
                updates['n_income_attr_p'] = round(float(hp) / 1_000_000, 2)
            oi = row.get('operate_income')
            if pd.notna(oi):
                updates['revenue'] = round(float(oi) / 1_000_000, 2)
            nco = row.get('netcash_operate')
            if pd.notna(nco):
                updates['n_cashflow_act'] = round(float(nco) / 1_000_000, 2)
            op = row.get('operate_profit')
            if pd.notna(op):
                updates['operate_profit'] = round(float(op) / 1_000_000, 2)
            ptp = row.get('pretax_profit')
            if pd.notna(ptp):
                updates['pretax_profit'] = round(float(ptp) / 1_000_000, 2)
            ta = row.get('total_assets')
            if pd.notna(ta):
                updates['total_assets'] = round(float(ta) / 1_000_000, 2)
            tl = row.get('total_liabilities')
            if pd.notna(tl):
                updates['total_liab'] = round(float(tl) / 1_000_000, 2)
            tpe = row.get('total_parent_equity')
            if pd.notna(tpe):
                updates['total_hldr_eqy_exc_min_int'] = round(float(tpe) / 1_000_000, 2)
            gp = row.get('gross_profit')
            if pd.notna(gp):
                updates['gross_profit'] = round(float(gp) / 1_000_000, 2)
            ec = row.get('end_cash')
            if pd.notna(ec):
                updates['money_cap'] = round(float(ec) / 1_000_000, 2)

            if pd.notna(shares) and shares > 0:
                updates['base_share'] = round(float(shares) / 1_000_000, 2)

            # EPS (basic_eps is in RMB)
            eps = row.get('basic_eps')
            if pd.notna(eps):
                updates['eps'] = round(float(eps), 3)

            # DPS (dps_hkd is in HKD, convert to RMB)
            dps_hkd = row.get('dps_hkd')
            if pd.notna(dps_hkd):
                updates['dps'] = round(float(dps_hkd) * FX, 3)

            # BPS (book value per share, in RMB)
            bps = row.get('bps')
            if pd.notna(bps):
                updates['bps'] = round(float(bps), 3)

            # Payout ratio (for reference)
            div_ratio = row.get('divi_ratio')
            if pd.notna(div_ratio):
                updates['payout_ratio'] = round(float(div_ratio), 3)

            # PE, PB
            pe = row.get('pe_ttm')
            if pd.notna(pe):
                updates['pe_ttm'] = round(float(pe), 2)
            pb = row.get('pb_ttm')
            if pd.notna(pb):
                updates['pb_ttm'] = round(float(pb), 2)

            # Profitability ratios
            roe = row.get('roe_avg')
            if pd.notna(roe):
                updates['roe'] = round(float(roe), 2)
            roa = row.get('roa')
            if pd.notna(roa):
                updates['roa'] = round(float(roa), 2)
            gm = row.get('gross_profit_ratio')
            if pd.notna(gm):
                updates['gross_margin'] = round(float(gm), 2)
            nm = row.get('net_profit_ratio')
            if pd.notna(nm):
                updates['net_margin'] = round(float(nm), 2)

            # Efficiency ratios
            debt_ratio = row.get('debt_asset_ratio')
            if pd.notna(debt_ratio):
                updates['debt_ratio'] = round(float(debt_ratio), 2)
            curr = row.get('current_ratio')
            if pd.notna(curr):
                updates['current_ratio'] = round(float(curr), 2)
            ocf_sales = row.get('ocf_sales')
            if pd.notna(ocf_sales):
                updates['ocf_sales_ratio'] = round(float(ocf_sales), 2)

            # Turnover days
            inv_days = row.get('inventory_tdays')
            if pd.notna(inv_days):
                updates['inventory_turnover_days'] = round(float(inv_days), 1)
            ar_days = row.get('accounts_rece_tdays')
            if pd.notna(ar_days):
                updates['ar_turnover_days'] = round(float(ar_days), 1)
            ta_days = row.get('total_assets_tdays')
            if pd.notna(ta_days):
                updates['asset_turnover_days'] = round(float(ta_days), 1)

            if not updates:
                continue

            # UPSERT into annual_financials
            # Find matching row (report_type='annual' with matching fiscal_year)
            # Try exact match first
            cols = list(updates.keys())
            set_clause = ', '.join(f"{c}=COALESCE(annual_financials.{c}, excluded.{c})" for c in cols)
            vals = list(updates.values())

            db.execute(f"""
                INSERT INTO annual_financials (ts_code, fiscal_year, report_type, {', '.join(cols)})
                VALUES (?, ?, 'annual', {', '.join('?' * len(cols))})
                ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET {set_clause}
            """, [ts_code, fy] + vals)
            total_updated += 1

    db.commit()

    # Verify
    stocks_fixed = db.execute("SELECT COUNT(*) FROM stocks WHERE ts_code LIKE '%.HK' AND shares_m > 0").fetchone()[0]
    total_hk = db.execute("SELECT COUNT(*) FROM stocks WHERE ts_code LIKE '%.HK'").fetchone()[0]

    eps_fixed = db.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND eps > 0 AND report_type='annual'").fetchone()[0]
    dps_fixed = db.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND dps > 0 AND report_type='annual'").fetchone()[0]
    bs_fixed = db.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND base_share > 0 AND report_type='annual'").fetchone()[0]
    total_af_hk = db.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code LIKE '%.HK' AND report_type='annual'").fetchone()[0]

    print(f"\n=== Results ===")
    print(f"  stocks.shares_m: {stocks_fixed}/{total_hk} ({stocks_fixed/total_hk*100:.1f}%)")
    print(f"  base_share: {bs_fixed}/{total_af_hk} ({bs_fixed/total_af_hk*100:.1f}%)")
    print(f"  eps: {eps_fixed}/{total_af_hk} ({eps_fixed/total_af_hk*100:.1f}%)")
    print(f"  dps: {dps_fixed}/{total_af_hk} ({dps_fixed/total_af_hk*100:.1f}%)")
    print(f"  Total rows updated: {total_updated}")

    # Verify 00506.HK
    print("\n=== 00506.HK verification ===")
    sm = db.execute("SELECT shares_m FROM stocks WHERE ts_code='00506.HK'").fetchone()
    print(f"  stocks.shares_m: {sm[0]}M")
    for r in db.execute("SELECT fiscal_year, base_share, eps, dps FROM annual_financials WHERE ts_code='00506.HK' AND report_type='annual' AND fiscal_year>=2019 ORDER BY fiscal_year").fetchall():
        print(f"  FY{r[0]}: shares={r[1]}M, eps={r[2]:.3f}, dps={r[3]:.3f}RMB")

    db.close()
    print("\n✅ Done")

if __name__ == '__main__':
    main()
