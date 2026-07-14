#!/usr/bin/env python3
"""db_init.py — 创建和初始化 stock_analysis.db 统一数据库。

Usage:
    python3 scripts/db_init.py                    # 创建数据库（如不存在）
    python3 scripts/db_init.py --force            # 删除已有数据库并重建
    python3 scripts/db_init.py --query "SQL"      # 执行查询

数据库位置: Turtle_investment_framework/stock_analysis.db
所有金额统一为百万元 RMB。
"""

import argparse, json, os, sqlite3, sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")

SCHEMA = """
-- 1. 标的基础信息
CREATE TABLE IF NOT EXISTS stocks (
    ts_code TEXT PRIMARY KEY,
    name_cn TEXT,
    name_en TEXT,
    market TEXT,                    -- HK / A / US
    industry TEXT,
    listing_date TEXT,
    shares_m REAL,                  -- 总股本（百万股）
    currency TEXT DEFAULT 'RMB',
    is_soe INTEGER DEFAULT 0,
    has_interest_bearing_debt INTEGER DEFAULT 0,
    holding_channel TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 2. 年度财务数据（核心表）
CREATE TABLE IF NOT EXISTS annual_financials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    report_type TEXT DEFAULT 'annual',   -- annual / interim
    -- 利润表
    revenue REAL,                       -- 营业收入
    oper_cost REAL,                     -- 营业成本
    gross_profit REAL,                  -- 毛利
    gross_margin REAL,                  -- 毛利率 %
    n_income_attr_p REAL,              -- 归母净利润
    minority_profit REAL,               -- 少数股东损益
    pretax_profit REAL,                 -- 税前利润
    income_tax REAL,                    -- 所得税
    d_a REAL,                           -- 折旧摊销合计
    -- 资产负债表
    money_cap REAL,                     -- 货币资金
    cash_broad REAL,                    -- 广义现金（含定期存款、受限资金）
    accounts_receiv REAL,              -- 应收账款
    acct_payable REAL,                  -- 应付账款
    contract_liab REAL,                 -- 合同负债
    total_assets REAL,                  -- 资产总计
    total_liab REAL,                    -- 负债总计
    total_hldr_eqy_exc_min_int REAL,   -- 归母权益
    minority_int REAL,                  -- 少数股东权益
    goodwill REAL,                      -- 商誉
    st_borr REAL,                       -- 短期借款
    lt_borr REAL,                       -- 长期借款
    -- 现金流量表
    n_cashflow_act REAL,               -- 经营活动现金流 OCF
    c_pay_acq_const_fiolta REAL,       -- 资本支出 Capex（绝对值）
    fcf REAL,                           -- 自由现金流 = OCF - Capex
    dividends_paid REAL,                -- 已付股息总额
    -- 每股数据
    eps REAL,                           -- 每股收益
    dps REAL,                           -- 每股股息
    -- 审计
    audit_opinion TEXT,
    auditor TEXT,
    -- 元数据
    data_source TEXT,                   -- tushare / pdf_extract / manual
    data_quality TEXT,                  -- verified / estimated / fallback / suspect
    UNIQUE(ts_code, fiscal_year, report_type)
    -- Note: DB-level CHECK constraints removed in v3.1.
    -- Validation is handled by db_gate.py → quality_findings table.
    -- Hard CHECK constraints block legitimate partial data (e.g. income-only records)
    -- and make debugging curation issues difficult.
);

-- 3. 门槛参数
CREATE TABLE IF NOT EXISTS thresholds (
    ts_code TEXT PRIMARY KEY,
    II REAL,                            -- 买入门槛 %
    star_5 REAL,
    star_4 REAL,
    star_3 REAL,
    category TEXT,
    rationale TEXT,
    evidence TEXT,                      -- JSON array
    adjustments TEXT,                   -- JSON array
    computed_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 4. 定量计算结果
CREATE TABLE IF NOT EXISTS computed_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    -- Factor 2
    r_np REAL,
    r_oe REAL,
    oe_avg_3y REAL,
    M_payout REAL,                      -- 派息率
    distribution_pass INTEGER,          -- 分配能力 0/1
    -- Factor 3
    aa_avg_3y REAL,
    aa_avg_5y REAL,
    gg_pessimistic REAL,
    gg_base REAL,
    gg_optimistic REAL,
    gg_discounted_base REAL,
    g_base REAL,
    g_adj REAL,
    b_penalty REAL,
    ap_excess_financing INTEGER,
    lambda_conservative REAL,
    lambda_neutral REAL,
    -- Factor 4
    ddm_v_hkd REAL,
    ddm_v_rmb REAL,
    dps_yield_after_tax REAL,
    value_trap_score INTEGER,
    position_conservative TEXT,
    position_neutral TEXT,
    position_optimistic TEXT,
    position_recommended TEXT,
    stop_loss_hard_hkd REAL,
    -- 汇总
    rejection_overall TEXT,
    rejection_warnings TEXT,            -- JSON array
    -- 元数据
    compute_version TEXT DEFAULT 'v3.0',
    UNIQUE(ts_code, computed_at)
);

-- 5. 否决门检查记录
CREATE TABLE IF NOT EXISTS rejection_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    gate TEXT NOT NULL,                 -- factor1a.audit, factor2.s4_1...
    status TEXT NOT NULL,               -- pass / fail / warn
    detail TEXT,
    UNIQUE(ts_code, computed_at, gate)
);

-- 6. 数据质量日志
CREATE TABLE IF NOT EXISTS data_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    check_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    layer TEXT,
    verdict TEXT,                       -- PASS / WARN / BLOCK
    blocks TEXT,                        -- JSON array
    warns TEXT,                         -- JSON array
    missing_critical TEXT,              -- JSON array
    missing_asset TEXT                  -- JSON array
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_af_ts_code ON annual_financials(ts_code);
CREATE INDEX IF NOT EXISTS idx_af_year ON annual_financials(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_cm_ts_code ON computed_metrics(ts_code);
CREATE INDEX IF NOT EXISTS idx_rc_ts_code ON rejection_checks(ts_code);
CREATE INDEX IF NOT EXISTS idx_dq_ts_code ON data_quality_log(ts_code);

-- 视图：最新计算结果
CREATE VIEW IF NOT EXISTS v_latest_metrics AS
SELECT cm.* FROM computed_metrics cm
JOIN (
    SELECT ts_code, MAX(computed_at) as latest
    FROM computed_metrics GROUP BY ts_code
) latest ON cm.ts_code = latest.ts_code AND cm.computed_at = latest.latest;

-- 视图：完整的标的分析快照
CREATE VIEW IF NOT EXISTS v_stock_snapshot AS
SELECT
    s.ts_code, s.name_cn, s.market, s.industry, s.shares_m,
    th.II, th.category as threshold_category,
    lm.gg_base, lm.gg_discounted_base, lm.ddm_v_hkd,
    lm.dps_yield_after_tax, lm.value_trap_score,
    lm.position_recommended, lm.rejection_overall
FROM stocks s
LEFT JOIN thresholds th ON s.ts_code = th.ts_code
LEFT JOIN v_latest_metrics lm ON s.ts_code = lm.ts_code;

-- 7. 入库审计日志
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    fiscal_year INTEGER,
    action TEXT NOT NULL,               -- INSERT / UPDATE / DELETE / BLOCKED
    changed_at TEXT DEFAULT (datetime('now','localtime')),
    detail TEXT                         -- JSON: {reason, field_values...}
);

-- 视图：数据完整性评分
CREATE VIEW IF NOT EXISTS v_data_completeness AS
SELECT
    ts_code,
    COUNT(*) as years,
    ROUND(100.0 * COUNT(revenue) / COUNT(*)) as rev_pct,
    ROUND(100.0 * COUNT(n_income_attr_p) / COUNT(*)) as np_pct,
    ROUND(100.0 * COUNT(n_cashflow_act) / COUNT(*)) as ocf_pct,
    ROUND(100.0 * COUNT(total_assets) / COUNT(*)) as assets_pct,
    ROUND(100.0 * COUNT(total_hldr_eqy_exc_min_int) / COUNT(*)) as equity_pct,
    ROUND(100.0 * COUNT(total_liab) / COUNT(*)) as liab_pct,
    ROUND(100.0 * COUNT(dps) / COUNT(*)) as dps_pct,
    ROUND(100.0 * COUNT(acct_payable) / COUNT(*)) as ap_pct,
    ROUND(100.0 * COUNT(accounts_receiv) / COUNT(*)) as ar_pct,
    ROUND(100.0 * COUNT(c_pay_acq_const_fiolta) / COUNT(*)) as capex_pct,
    ROUND(100.0 * COUNT(d_a) / COUNT(*)) as d_a_pct,
    ROUND(100.0 * SUM(CASE WHEN revenue IS NOT NULL AND n_income_attr_p IS NOT NULL
        AND n_cashflow_act IS NOT NULL AND total_assets IS NOT NULL
        AND total_hldr_eqy_exc_min_int IS NOT NULL AND d_a IS NOT NULL
        THEN 1 ELSE 0 END) / COUNT(*)) as usable_pct,
    ROUND(AVG(CASE WHEN total_assets > 0 AND total_hldr_eqy_exc_min_int IS NOT NULL
        AND total_liab IS NOT NULL
        THEN ABS(total_assets - total_hldr_eqy_exc_min_int - COALESCE(minority_int,0) - total_liab) / total_assets * 100
        ELSE NULL END), 1) as bs_deviation_pct
FROM annual_financials
GROUP BY ts_code;

-- ============================================================
-- v3.1 新增：候选层表 (Section 6 of DATABASE_DESIGN.md)
-- ============================================================

-- 8. raw_import_batches — 导入批次
CREATE TABLE IF NOT EXISTS raw_import_batches (
    batch_id TEXT PRIMARY KEY,
    ts_code TEXT NOT NULL,
    fiscal_year INTEGER,
    source_type TEXT NOT NULL,      -- pdf_extract / tushare / input_data / manual_fix / threshold
    source_path TEXT,
    source_hash TEXT,
    importer_version TEXT DEFAULT 'v3.1',
    imported_at TEXT DEFAULT (datetime('now','localtime')),
    status TEXT DEFAULT 'imported', -- imported / validated / blocked / curated
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_rib_ts_code ON raw_import_batches(ts_code);

-- 9. financial_observations — 字段级候选值（一字段一记录）
CREATE TABLE IF NOT EXISTS financial_observations (
    observation_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    report_type TEXT DEFAULT 'annual',
    statement_type TEXT,            -- income / balance_sheet / cashflow / per_share
    field_name TEXT NOT NULL,       -- Tushare 英文字段名
    raw_value TEXT,
    normalized_value REAL,
    unit TEXT DEFAULT 'RMB_million',
    source_type TEXT,               -- pdf_extract / tushare / input_data / manual_fix / legacy_db
    source_priority INTEGER DEFAULT 100,
    confidence REAL DEFAULT 0.5,
    status TEXT DEFAULT 'candidate', -- candidate / accepted / rejected / superseded
    rejection_reason TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (batch_id) REFERENCES raw_import_batches(batch_id)
);
CREATE INDEX IF NOT EXISTS idx_fo_ts_code ON financial_observations(ts_code, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_fo_field ON financial_observations(ts_code, fiscal_year, field_name);
CREATE INDEX IF NOT EXISTS idx_fo_batch ON financial_observations(batch_id);

-- 10. field_evidence — 字段级证据
CREATE TABLE IF NOT EXISTS field_evidence (
    evidence_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    document_path TEXT,
    page_no INTEGER,
    table_name TEXT,
    row_label TEXT,
    raw_text TEXT,
    normalization_rule TEXT,
    unit_detected TEXT,
    unit_multiplier REAL,
    extractor_version TEXT,
    confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (observation_id) REFERENCES financial_observations(observation_id)
);
CREATE INDEX IF NOT EXISTS idx_fe_obs ON field_evidence(observation_id);

-- 11. quality_findings — 统一质量问题表（承接 db_gate + data_gate）
CREATE TABLE IF NOT EXISTS quality_findings (
    finding_id TEXT PRIMARY KEY,
    batch_id TEXT,
    ts_code TEXT NOT NULL,
    fiscal_year INTEGER,
    field_name TEXT,
    observation_id TEXT,
    check_name TEXT NOT NULL,        -- e.g. 'unit_detect', 'field_swap', 'bs_identity'
    severity TEXT NOT NULL,          -- BLOCK / WARN / INFO
    scope TEXT DEFAULT 'field',      -- field / row / year / stock / cross_source
    expected TEXT,
    actual TEXT,
    message TEXT NOT NULL,
    fix_status TEXT DEFAULT 'open',  -- open / accepted_risk / fixed / false_positive
    fix_observation_id TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    resolved_at TEXT,
    FOREIGN KEY (observation_id) REFERENCES financial_observations(observation_id)
);
CREATE INDEX IF NOT EXISTS idx_qf_ts_code ON quality_findings(ts_code, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_qf_severity ON quality_findings(severity, fix_status);

-- 12. curation_decisions — 字段采用决策
CREATE TABLE IF NOT EXISTS curation_decisions (
    decision_id TEXT PRIMARY KEY,
    ts_code TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    accepted_observation_id TEXT,
    previous_observation_id TEXT,
    decision_type TEXT NOT NULL,     -- auto_accept / manual_override / reject_all / accept_with_warning
    decision_reason TEXT,
    decided_by TEXT DEFAULT 'system',
    decided_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (accepted_observation_id) REFERENCES financial_observations(observation_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cd_unique ON curation_decisions(ts_code, fiscal_year, field_name);
CREATE INDEX IF NOT EXISTS idx_cd_ts_code ON curation_decisions(ts_code, fiscal_year);

-- 13. analysis_contracts — 分析前契约
CREATE TABLE IF NOT EXISTS analysis_contracts (
    contract_id TEXT PRIMARY KEY,
    ts_code TEXT NOT NULL,
    generated_at TEXT DEFAULT (datetime('now','localtime')),
    readiness_status TEXT NOT NULL,  -- READY / DEGRADED / BLOCKED
    readiness_score REAL,
    usable_years_json TEXT,          -- JSON: [2021,2022,2023,2024,2025]
    missing_core_json TEXT,          -- JSON: ["shares_m","dps"]
    degraded_fields_json TEXT,       -- JSON: ["d_a","dividends_paid"]
    block_reasons_json TEXT,         -- JSON: [{check, field, message}]
    warn_reasons_json TEXT,
    analysis_scope_json TEXT,        -- JSON: {valuation_allowed, ddm_allowed, ...}
    data_snapshot_hash TEXT,
    UNIQUE(ts_code, generated_at)
);

-- ============================================================
-- v3.1 新增视图 (Section 9 of DATABASE_DESIGN.md)
-- ============================================================

-- 字段级质量总览
CREATE VIEW IF NOT EXISTS v_field_quality_summary AS
SELECT
    fo.ts_code, fo.fiscal_year, fo.field_name,
    fo.normalized_value as accepted_value,
    fo.source_type, fo.confidence,
    COUNT(DISTINCT fe.evidence_id) as evidence_count,
    SUM(CASE WHEN qf.severity='BLOCK' AND qf.fix_status='open' THEN 1 ELSE 0 END) as open_block_count,
    SUM(CASE WHEN qf.severity='WARN' AND qf.fix_status='open' THEN 1 ELSE 0 END) as open_warn_count,
    cd.decision_type, cd.decided_by
FROM financial_observations fo
LEFT JOIN field_evidence fe ON fo.observation_id = fe.observation_id
LEFT JOIN quality_findings qf ON fo.observation_id = qf.observation_id
LEFT JOIN curation_decisions cd ON fo.ts_code = cd.ts_code
    AND fo.fiscal_year = cd.fiscal_year
    AND fo.field_name = cd.field_name
WHERE fo.status = 'accepted'
GROUP BY fo.ts_code, fo.fiscal_year, fo.field_name;

-- 跨源冲突视图
CREATE VIEW IF NOT EXISTS v_source_conflicts AS
SELECT
    a.ts_code, a.fiscal_year, a.field_name,
    a.source_type as source_a, a.normalized_value as value_a,
    b.source_type as source_b, b.normalized_value as value_b,
    CASE WHEN b.normalized_value > 0
        THEN ROUND(ABS(a.normalized_value - b.normalized_value) / ABS(b.normalized_value) * 100, 1)
        ELSE NULL END as relative_diff_pct,
    CASE WHEN b.normalized_value > 0
        AND ABS(a.normalized_value - b.normalized_value) / ABS(b.normalized_value) > 0.05
        THEN 'BLOCK'
        WHEN b.normalized_value > 0
        AND ABS(a.normalized_value - b.normalized_value) / ABS(b.normalized_value) > 0.01
        THEN 'WARN'
        ELSE 'INFO' END as severity
FROM financial_observations a
JOIN financial_observations b
    ON a.ts_code = b.ts_code
    AND a.fiscal_year = b.fiscal_year
    AND a.field_name = b.field_name
    AND a.source_type < b.source_type
WHERE a.status = 'candidate' AND b.status = 'candidate'
  AND a.normalized_value IS NOT NULL AND b.normalized_value IS NOT NULL
  AND a.field_name IN ('revenue','n_income_attr_p','total_assets','total_hldr_eqy_exc_min_int','n_cashflow_act');

-- 就绪度视图（整合候选层质量）
CREATE VIEW IF NOT EXISTS v_analysis_readiness AS
SELECT
    s.ts_code,
    COALESCE((SELECT COUNT(DISTINCT fiscal_year) FROM annual_financials af WHERE af.ts_code = s.ts_code), 0) as usable_years,
    (SELECT COUNT(*) FROM quality_findings qf
     WHERE qf.ts_code = s.ts_code AND qf.severity = 'BLOCK' AND qf.fix_status = 'open') as open_blocks,
    (SELECT COUNT(*) FROM quality_findings qf
     WHERE qf.ts_code = s.ts_code AND qf.severity = 'WARN' AND qf.fix_status = 'open') as open_warns,
    CASE
        WHEN (SELECT COUNT(*) FROM quality_findings qf
              WHERE qf.ts_code = s.ts_code AND qf.severity = 'BLOCK' AND qf.fix_status = 'open') > 0 THEN 'BLOCKED'
        WHEN COALESCE((SELECT usable_pct FROM v_data_completeness v WHERE v.ts_code = s.ts_code), 0) < 40 THEN 'BLOCKED'
        WHEN COALESCE((SELECT usable_pct FROM v_data_completeness v WHERE v.ts_code = s.ts_code), 0) < 80 THEN 'DEGRADED'
        WHEN (SELECT COUNT(*) FROM quality_findings qf
              WHERE qf.ts_code = s.ts_code AND qf.severity = 'WARN' AND qf.fix_status = 'open') > 0 THEN 'DEGRADED'
        ELSE 'READY'
    END as readiness_status
FROM stocks s;
"""


def init_db(force: bool = False):
    """Create database and tables."""
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"🗑️  Deleted existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    # Verify
    conn = sqlite3.connect(DB_PATH)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    views = conn.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name").fetchall()
    conn.close()

    print(f"✅ Database created: {DB_PATH}")
    print(f"   Tables ({len(tables)}): {', '.join(t[0] for t in tables)}")
    print(f"   Views ({len(views)}): {', '.join(v[0] for v in views)}")


def query_db(sql: str):
    """Execute a query and print results."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql).fetchall()
    if rows:
        cols = rows[0].keys()
        print(" | ".join(cols))
        print("-" * 60)
        for row in rows:
            print(" | ".join(str(row[c]) for c in cols))
    else:
        print("(no results)")
    print(f"\n{len(rows)} row(s)")
    conn.close()


def main():
    p = argparse.ArgumentParser(description="stock_analysis.db 初始化")
    p.add_argument("--force", action="store_true", help="删除已有数据库重建")
    p.add_argument("--query", type=str, help="执行 SQL 查询")
    args = p.parse_args()

    if args.query:
        if not os.path.exists(DB_PATH):
            print(f"ERROR: {DB_PATH} not found. Run db_init.py first.", file=sys.stderr)
            return 1
        query_db(args.query)
        return 0

    init_db(force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
