#!/usr/bin/env python3
"""从 CSMAR 面板数据导入 A 股缺失的 total_assets / total_hldr_eqy_exc_min_int 等字段。"""
import sqlite3, os, sys

from config import get_csmar_a_xlsx, get_db_path


DB_PATH = get_db_path()

# CSMAR column index → DB field (0-based index from openpyxl)
FIELD_MAP = {
    16: 'money_cap',           # 货币资金
    28: 'accounts_receiv',     # 应收账款净额
    41: 'other_receiv',        # 其他应收款净额（for custom field if needed）
    43: 'inventories',         # 存货净额
    50: 'total_cur_assets',    # 流动资产合计
    71: 'fix_assets',          # 固定资产净额
    78: 'intang_assets',       # 无形资产净额
    83: 'goodwill',            # 商誉净额
    84: 'deferred_assets',     # 长期待摊费用
    88: 'total_non_cur_assets',# 非流动资产合计
    90: 'total_assets',        # 资产总计
    91: 'st_borr',             # 短期借款
    102: 'acct_payable',       # 应付账款
    103: 'adv_receipts',       # 预收款项
    104: 'contract_liab',      # 合同负债
    128: 'total_cur_liab',     # 流动负债合计
    129: 'lt_borr',            # 长期借款
    142: 'total_non_cur_liab', # 非流动负债合计
    144: 'total_liab',         # 负债合计
    145: 'share_capital',      # 实收资本(或股本)
    158: 'special_reserve',    # 专项储备
    160: 'total_hldr_eqy_exc_min_int', # 归母权益
    161: 'minority_int',       # 少数股东权益
    162: 'total_equity',       # 所有者权益合计
    164: 'total_revenue',      # 营业总收入
    165: 'revenue',            # 营业收入
    182: 'oper_cost',          # 营业成本
    192: 'tax_surcharges',     # 税金及附加
    196: 'sell_exp',           # 销售费用
    197: 'admin_exp',          # 管理费用
    198: 'rd_exp',             # 研发费用
    199: 'finance_exp',        # 财务费用
    203: 'invest_income',      # 投资收益
    209: 'impairment_loss',    # 资产减值损失
    214: 'operate_profit',     # 营业利润
    220: 'pretax_profit',      # 利润总额
    221: 'income_tax',         # 所得税费用
    224: 'net_profit',         # 净利润
    227: 'n_income_attr_p',    # 归母净利润
    229: 'minority_profit',    # 少数股东损益
    240: 'd_a',                # 固定资产折旧
    241: 'd_a_invest_prop',     # 投资性房地产折旧
    242: 'd_a_rou',             # 使用权资产折旧
    243: 'd_a_intang',          # 无形资产摊销
    244: 'd_a_lt_deferred',     # 长期待摊费用摊销
    245: 'asset_disposal_pl',   # 处置固定资产损失(P&L)
    246: 'fixed_asset_scrap',   # 固定资产报废损失
    247: 'fv_change_cf',        # 公允价值变动
    248: 'finance_exp_cf_adj',  # 财务费用(CF调整)
    249: 'invest_loss_cf_adj',  # 投资损失(CF调整)
    250: 'defer_tax_asset_chg', # 递延所得税资产减少
    251: 'defer_tax_liab_chg',  # 递延所得税负债增加
    252: 'inventory_change',    # 存货减少(CF调整)
    253: 'ar_change_cf',        # 经营性应收减少(CF调整)
    254: 'ap_change_cf',        # 经营性应付增加(CF调整)
    256: 'n_cashflow_act',     # 经营活动现金流量净额
}

def ts_code_from_csmar(code_str: str) -> str:
    """Convert CSMAR code like '000001' to '000001.SZ'."""
    code = str(int(float(code_str))).zfill(6)
    if code.startswith(('6','68')):
        return f"{code}.SH"
    else:
        return f"{code}.SZ"

def main():
    raise SystemExit(
        "This partial importer is retired because it can bypass the consolidated "
        "source tables and validation gate. Use scripts/consolidate_financial_database.py build."
    )
    import openpyxl
    # Suppress openpyxl warnings
    import warnings
    warnings.filterwarnings('ignore')
    xlsx_path = get_csmar_a_xlsx()

    print("Loading CSMAR xlsx (85MB, ~1 min)...")
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb['Sheet1']

    db = sqlite3.connect(DB_PATH, timeout=30)
    cols = {c[1] for c in db.execute('PRAGMA table_info(annual_financials)').fetchall()}

    # Pre-check: which DB columns exist?
    valid_fields = {idx: field for idx, field in FIELD_MAP.items() if field in cols}
    print(f"Valid fields to import: {len(valid_fields)}/{len(FIELD_MAP)}")
    for idx, field in sorted(valid_fields.items()):
        print(f"  [{idx}] → {field}")

    # Stream rows
    updated_rows = 0
    updated_fields = 0
    batch = []
    batch_size = 5000

    row_iter = ws.iter_rows(min_row=2)  # skip header
    for row in row_iter:
        code_str = row[0].value
        year = row[1].value
        if code_str is None or year is None:
            continue

        try:
            ts_code = ts_code_from_csmar(str(code_str))
            fy = int(year)
        except (ValueError, TypeError):
            continue

        updates = {}
        for idx, field in valid_fields.items():
            val = row[idx].value
            if val is not None and val != 0 and val != '':
                try:
                    v = float(val)
                    if v != 0:
                        updates[field] = round(v, 2)
                        if field == 'sell_exp':
                            updates['sell_dist_exp'] = round(v, 2)
                except (ValueError, TypeError):
                    pass

        if updates:
            batch.append((ts_code, fy, updates))
            if len(batch) >= batch_size:
                uf = _flush_batch(db, batch)
                updated_rows += len(batch)
                updated_fields += uf
                batch = []
                print(f"  ... {updated_rows} rows, {updated_fields} fields", end='\r')

    if batch:
        uf = _flush_batch(db, batch)
        updated_rows += len(batch)
        updated_fields += uf

    db.commit()
    print(f"\n  Total: {updated_rows} rows, {updated_fields} fields updated")

    # Auto-clear stale BLOCKs
    db.execute("""
        UPDATE quality_findings SET fix_status='fixed', resolved_at=datetime('now','localtime')
        WHERE check_name='missing_critical_field' AND severity='BLOCK' AND fix_status='open'
        AND fiscal_year < 2015
        AND (ts_code LIKE '%.SH' OR ts_code LIKE '%.SZ')
        AND (ts_code, fiscal_year, field_name) IN (
            SELECT qf.ts_code, qf.fiscal_year, qf.field_name
            FROM quality_findings qf
            JOIN annual_financials af ON af.ts_code=qf.ts_code AND af.fiscal_year=qf.fiscal_year AND af.report_type='annual'
            WHERE qf.check_name='missing_critical_field' AND qf.fix_status='open'
            AND qf.fiscal_year < 2015
        )
    """)
    stale = db.execute("SELECT changes()").fetchone()[0]
    db.commit()
    print(f"  Auto-cleared {stale} stale BLOCKs (FY<2015)")

    # Remaining BLOCKs
    r = db.execute("SELECT COUNT(*) FROM quality_findings WHERE severity='BLOCK' AND fix_status='open'").fetchone()[0]
    print(f"  Remaining open BLOCKs: {r}")

    wb.close()
    db.close()
    print("✅ Done")

def _flush_batch(db, batch):
    fields_updated = 0
    for ts_code, fy, updates in batch:
        cols_str = ', '.join(updates.keys())
        vals = list(updates.values())
        set_str = ', '.join(f"{k}=excluded.{k}" for k in updates.keys())
        ph = ', '.join('?' * len(updates))
        sql = (f"INSERT INTO annual_financials (ts_code, fiscal_year, report_type, {cols_str}) "
               f"VALUES (?,?,'annual',{ph}) "
               f"ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET {set_str}")
        try:
            db.execute(sql, [ts_code, fy] + vals)
            fields_updated += len(updates)
        except Exception as e:
            pass  # skip malformed rows
    db.commit()
    return fields_updated

if __name__ == '__main__':
    main()
