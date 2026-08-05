#!/usr/bin/env python3
"""migrate_to_db.py — 数据迁移 v3.1（候选→门禁→策展→最终事实）

⚠️ V12.12: 管线已废弃。annual_financials 现在由直接导入脚本维护：
  - scripts/rebuild_hk_data.py       — Tushare HK CSV → annual_financials
  - scripts/import_csmar_hk_full.py   — CSMAR HK xlsx → annual_financials
  - scripts/import_csmar.py           — CSMAR A股 xlsx → annual_financials
  - scripts/import_hk_shares.py       — Tushare parquet → EPS/DPS/股本
  这些脚本直接 UPSERT annual_financials，绕过 observations/curation 管线。
  financial_observations / field_evidence / curation_decisions 表已清空。

仅保留 auto_curate() 的排序逻辑（年报优先）供未来增量导入使用。

旧流程:
  1. 创建 import batch
  2. JSON → financial_observations（候选值）
  3. 运行 db_gate 验证 → quality_findings
  4. 自动 curation → curation_decisions + annual_financials
  5. BLOCK 的字段不入 annual_financials

Usage:
    python3 scripts/migrate_to_db.py              # 迁移所有标的
    python3 scripts/migrate_to_db.py --dry-run    # 预览
    python3 scripts/migrate_to_db.py --code 01502.HK
"""

import argparse, hashlib, json, os, re, sqlite3, sys, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db_gate import (detect_and_fix_unit, validate_row, validate_stock_level,
                     validate_cross_source, QualityFinding, MONETARY_FIELDS, CORE_FIELDS)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


# ── helpers ──

def safe_float(v, default=None):
    if v is None: return default
    try: return float(v)
    except (ValueError, TypeError): return default


def uid(prefix="ob"):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def file_hash(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:16]
    except Exception:
        return "unknown"


# ── batch management ──

def create_batch(conn, ts_code: str, source_type: str, source_path: str = "",
                 fiscal_year: int = None) -> str:
    for _ in range(5):  # retry on collision
        batch_id = f"batch_{uuid.uuid4().hex[:16]}"
        try:
            conn.execute("""INSERT INTO raw_import_batches (batch_id, ts_code, fiscal_year, source_type, source_path, source_hash, status)
                VALUES (?,?,?,?,?,?,?)""",
                (batch_id, ts_code, fiscal_year, source_type, source_path,
                 file_hash(source_path) if source_path else "", "imported"))
            return batch_id
        except sqlite3.IntegrityError:
            continue  # UUID collision, retry
    raise RuntimeError("Failed to create unique batch_id after 5 retries")


# ── observation creation ──

FIELD_TO_STATEMENT = {
    "revenue": "income", "oper_cost": "income", "n_income_attr_p": "income",
    "minority_profit": "income", "pretax_profit": "income", "income_tax": "income",
    "d_a": "income", "gross_profit": "income", "gross_margin": "income",
    "money_cap": "balance_sheet", "cash_broad": "balance_sheet",
    "accounts_receiv": "balance_sheet", "acct_payable": "balance_sheet",
    "contract_liab": "balance_sheet", "total_assets": "balance_sheet",
    "total_liab": "balance_sheet", "total_hldr_eqy_exc_min_int": "balance_sheet",
    "minority_int": "balance_sheet", "goodwill": "balance_sheet",
    "st_borr": "balance_sheet", "lt_borr": "balance_sheet",
    "n_cashflow_act": "cashflow", "c_pay_acq_const_fiolta": "cashflow",
    "fcf": "cashflow", "dividends_paid": "cashflow",
    "eps": "per_share", "dps": "per_share",
}


def insert_observation(conn, batch_id: str, ts_code: str, fiscal_year: int,
                       field_name: str, raw_value, normalized_value: float,
                       source_type: str, source_priority: int = 100,
                       confidence: float = 0.5) -> str:
    obs_id = uid("ob")
    stmt = FIELD_TO_STATEMENT.get(field_name, "unknown")
    conn.execute("""INSERT OR IGNORE INTO financial_observations
        (observation_id, batch_id, ts_code, fiscal_year, statement_type,
         field_name, raw_value, normalized_value, unit, source_type, source_priority, confidence, status)
        VALUES (?,?,?,?,?,?,?,?,'RMB_million',?,?,?,'candidate')""",
        (obs_id, batch_id, ts_code, fiscal_year, stmt,
         field_name, str(raw_value) if raw_value is not None else None,
         round(normalized_value, 2) if normalized_value is not None else None,
         source_type, source_priority, confidence))
    return obs_id


# ── observation writing ──

def write_observations_from_dict(conn, batch_id: str, ts_code: str,
                                  fiscal_year: int, data: dict,
                                  source_type: str, priority: int = 100):
    """将一行财务数据的所有字段写入 financial_observations。"""
    for field_name, raw_val in data.items():
        if field_name in ("ts_code", "end_date", "report_type", "id",
                          "data_source", "data_quality", "audit_opinion", "auditor"):
            continue
        if field_name in ("fiscal_year",):
            continue
        norm = safe_float(raw_val)
        insert_observation(conn, batch_id, ts_code, fiscal_year,
                          field_name, raw_val, norm, source_type, priority,
                          confidence=0.8 if source_type == "pdf_verified" else 0.5)


# ── field evidence ──

def insert_evidence(conn, observation_id: str, doc_path: str = "",
                    page_no: int = None, table_name: str = "",
                    raw_text: str = "", norm_rule: str = "",
                    unit_detected: str = "", confidence: float = 0.5):
    ev_id = uid("ev")
    conn.execute("""INSERT INTO field_evidence
        (evidence_id, observation_id, document_path, page_no, table_name,
         raw_text, normalization_rule, unit_detected, confidence)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (ev_id, observation_id, doc_path, page_no, table_name,
         raw_text[:500] if raw_text else "", norm_rule, unit_detected, confidence))
    return ev_id


# ── quality findings ──

def write_quality_findings(conn, findings: list, batch_id: str = ""):
    for f in findings:
        row = f.to_row(batch_id)
        cols = ", ".join(row.keys())
        ph = ", ".join("?" for _ in row)
        conn.execute(f"INSERT OR IGNORE INTO quality_findings ({cols}) VALUES ({ph})", list(row.values()))


# ── curation ──

def auto_curate(conn, ts_code: str, fiscal_year: int) -> int:
    """自动策展：对每个字段，选优先级最高的非 BLOCK 候选为 accepted。返回策展字段数。"""
    # Priority: manual_fix (user overrides all) > pdf_verified > input_data > tushare > tushare_hk_fallback > legacy_db
    PRIORITY_ORDER = {"manual_fix": 0, "pdf_verified": 2, "input_data": 3,
                       "tushare": 10, "tushare_hk_fallback": 20, "legacy_db": 100}

    # Get candidate observations, excluding BLOCKed ones
    # Row-level BLOCKs (scope='row', observation_id IS NULL) must also exclude all observations for that year
    blocked_years = conn.execute("""
        SELECT DISTINCT fiscal_year FROM quality_findings
        WHERE ts_code=? AND severity='BLOCK' AND fix_status='open'
        AND scope='row' AND observation_id IS NULL
    """, (ts_code,)).fetchall()
    blocked_year_set = {r[0] for r in blocked_years}

    rows = conn.execute("""
        SELECT fo.* FROM financial_observations fo
        WHERE fo.ts_code=? AND fo.fiscal_year=? AND fo.status='candidate'
        AND fo.observation_id NOT IN (
            SELECT COALESCE(qf.observation_id, '') FROM quality_findings qf
            WHERE qf.ts_code=fo.ts_code AND qf.fiscal_year=fo.fiscal_year
            AND qf.severity='BLOCK' AND qf.fix_status='open'
            AND qf.observation_id IS NOT NULL
        )
        ORDER BY fo.field_name, fo.source_priority,
                 -- Prefer annual (month=12) over interim (month=6/9/3) within same priority
                 CASE WHEN CAST(SUBSTR(fo.end_date,5,2) AS INTEGER) = 12 THEN 0 ELSE 1 END,
                 fo.confidence DESC
    """, (ts_code, fiscal_year)).fetchall()

    # If this year has an open row-level BLOCK, reject all observations
    if fiscal_year in blocked_year_set:
        return 0  # Row-level BLOCK blocks entire year from curation

    curated = {}
    for r in rows:
        field = r["field_name"]
        if field in curated:
            continue  # already picked the best source for this field
        curated[field] = r

    # Write curation decisions and build annual_financials row
    af_row = {"ts_code": ts_code, "fiscal_year": fiscal_year, "report_type": "annual"}

    for field, obs in curated.items():
        if field not in CORE_FIELDS and field not in MONETARY_FIELDS \
           and field not in ("eps", "dps", "gross_margin"):
            continue
        decision_id = uid("dc")
        prev = conn.execute(
            "SELECT accepted_observation_id FROM curation_decisions WHERE ts_code=? AND fiscal_year=? AND field_name=?",
            (ts_code, fiscal_year, field)).fetchone()

        conn.execute("""INSERT OR REPLACE INTO curation_decisions
            (decision_id, ts_code, fiscal_year, field_name, accepted_observation_id,
             previous_observation_id, decision_type, decision_reason, decided_by)
            VALUES (?,?,?,?,?,?,'auto_accept','highest priority source', 'system')""",
            (decision_id, ts_code, fiscal_year, field, obs["observation_id"],
             prev["accepted_observation_id"] if prev else None))

        # Mark observation as accepted
        conn.execute("UPDATE financial_observations SET status='accepted' WHERE observation_id=?",
                     (obs["observation_id"],))

        # Close field-level BLOCK/WARN for this field from lower-priority sources
        # Only close if the accepted observation came from a higher-priority source
        conn.execute("""UPDATE quality_findings SET fix_status='fixed', resolved_at=datetime('now','localtime')
            WHERE ts_code=? AND fiscal_year=? AND field_name=?
            AND fix_status='open' AND scope='field'
            AND (observation_id IS NULL OR observation_id != ?)""",
            (ts_code, fiscal_year, field, obs["observation_id"]))
        # Close row-level BLOCKs when the conflicting fields are now accepted from higher-priority source
        conn.execute("""UPDATE quality_findings SET fix_status='fixed', resolved_at=datetime('now','localtime')
            WHERE ts_code=? AND fiscal_year=? AND scope='row'
            AND fix_status='open' AND severity='BLOCK'
            AND EXISTS (SELECT 1 FROM curation_decisions cd
                WHERE cd.ts_code=quality_findings.ts_code
                AND cd.fiscal_year=quality_findings.fiscal_year
                AND cd.decision_type='auto_accept'
                AND cd.accepted_observation_id != COALESCE(quality_findings.observation_id, ''))""",
            (ts_code, fiscal_year))

        # Map to annual_financials column
        norm_val = obs["normalized_value"]
        if field == "total_hldr_eqy_exc_min_int" or field == "equity":
            af_row["total_hldr_eqy_exc_min_int"] = norm_val
        elif field in MONETARY_FIELDS or field in ("eps", "dps", "gross_margin"):
            af_row[field] = norm_val

    if not af_row.get("revenue") and not af_row.get("n_income_attr_p"):
        return 0  # insufficient data

    # Upsert to annual_financials — UPDATE only changed columns, preserve existing data
    cols = [k for k in af_row.keys()]
    ph = ", ".join("?" for _ in cols)
    vals = [af_row[c] for c in cols]
    set_clause = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in ("ts_code", "fiscal_year", "report_type"))
    try:
        conn.execute(
            f"INSERT INTO annual_financials ({', '.join(cols)}) VALUES ({ph}) "
            f"ON CONFLICT(ts_code, fiscal_year, report_type) DO UPDATE SET {set_clause}",
            vals,
        )
    except sqlite3.IntegrityError as e:
        # Log but don't block — quality issues are in quality_findings
        conn.execute("""INSERT INTO data_quality_log (ts_code, check_time, layer, verdict, blocks, warns, missing_critical, missing_asset)
            VALUES (?,datetime('now','localtime'),'db_constraint','WARN',?,?,'[]','[]')""",
            (ts_code, json.dumps([str(e)]), json.dumps([f"{k}={af_row.get(k)}" for k in ["revenue","n_income_attr_p","total_assets","total_hldr_eqy_exc_min_int"] if k in af_row])))

    # Mark batch as curated
    conn.execute("""UPDATE raw_import_batches SET status='curated'
        WHERE ts_code=? AND (fiscal_year=? OR fiscal_year IS NULL) AND status='imported'""",
        (ts_code, fiscal_year))

    return len(curated)


# ── main import logic ──

def parse_markdown_table(text: str, section: str) -> list[dict]:
    """Parse a markdown financial table from data_pack_market.md. Returns list of {end_date, field: value}."""
    import re

    # Find the section
    pattern = rf'## {re.escape(section)}\. .*?\n(.*?)(?=\n## |\n---\n|\Z)'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return []

    table_text = m.group(1)
    lines = table_text.strip().split("\n")

    # Find header row with years
    header_line = ""
    year_cols = []
    for line in lines:
        if "|---" in line:
            continue
        line_clean = line.replace(",", "")
        if "|" in line_clean and any(y in line_clean for y in ["2021", "2022", "2023", "2024", "2025"]):
            header_line = line
            break

    if not header_line:
        return []

    # Parse years from header
    header_cols = [c.strip() for c in header_line.split("|")]
    year_map = {}  # col_idx → year
    for i, col in enumerate(header_cols):
        for token in col.split():
            token = token.strip().replace(",", "")  # handle "2,025" format
            if token.isdigit() and len(token) == 4 and 2000 <= int(token) <= 2030:
                year_map[i] = int(token)
                break

    if not year_map:
        return []

    # Parse data rows
    FIELD_MAP = {
        "营业收入": "revenue", "营业成本": "oper_cost",
        "归母净利润": "n_income_attr_p", "净利润": "n_income_attr_p",
        "少数股东损益": "minority_profit", "利润总额": "pretax_profit",
        "所得税费用": "income_tax", "基本EPS": "eps", "稀释EPS": "eps",
        "经营活动现金流量净额": "n_cashflow_act", "经营活动产生的现金流量净额": "n_cashflow_act",
        "购建固定资产、无形资产和其他长期资产支付的现金": "c_pay_acq_const_fiolta",
        "购建固定无形资产和其他长期资产支付的现金": "c_pay_acq_const_fiolta",
        "货币资金": "money_cap", "应收账款": "accounts_receiv",
        "应付账款": "acct_payable", "合同负债": "contract_liab",
        "资产总计": "total_assets", "负债合计": "total_liab",
        "归属母公司股东的权益": "total_hldr_eqy_exc_min_int",
        "归属于母公司所有者权益合计": "total_hldr_eqy_exc_min_int",
        "所有者权益合计": "total_hldr_eqy_exc_min_int",
        "少数股东权益": "minority_int", "商誉": "goodwill",
        "短期借款": "st_borr", "长期借款": "lt_borr",
        "固定资产折旧、油气资产折耗、生产性生物资产折旧": "d_a",
        "固定资产折旧": "d_a", "折旧与摊销": "d_a", "折旧摊销": "d_a",
        "分配股利、利润或偿付利息支付的现金": "dividends_paid",
        "无形资产摊销": "d_a_amort",
    }

    records = {}  # year → {field: value}
    for line in lines:
        if "|---" in line or not "|" in line:
            continue
        cols = [c.strip().replace(",", "").replace("—", "0") for c in line.split("|")]
        if len(cols) < 3:
            continue

        row_label = cols[1] if len(cols) > 1 else ""
        field_name = None
        for cn_name, en_name in FIELD_MAP.items():
            if cn_name in row_label:
                field_name = en_name
                break

        if not field_name:
            continue

        for col_idx, year in year_map.items():
            if col_idx >= len(cols):
                continue
            val_str = cols[col_idx]
            try:
                val = float(val_str)
            except ValueError:
                continue
            if year not in records:
                records[year] = {}
            records[year][field_name] = val

    return [{"end_date": str(y), **fields} for y, fields in sorted(records.items())]


def import_datapack_markdown(conn, ts_code: str, dp_path: str, dry_run: bool):
    """Import financial data from data_pack_market.md markdown tables (A-shares)."""
    if not os.path.exists(dp_path):
        return 0

    with open(dp_path) as f:
        text = f.read()

    all_records = []
    for section in ["3", "4", "5"]:  # income, balance sheet, cashflow
        records = parse_markdown_table(text, section)
        if records:
            all_records.extend(records)

    if not all_records:
        return 0

    # Merge records by year
    merged = {}
    for rec in all_records:
        y = rec["end_date"]
        if y not in merged:
            merged[y] = {"end_date": y}
        merged[y].update(rec)

    records = list(merged.values())
    records.sort(key=lambda r: r["end_date"])

    return import_source(conn, ts_code, "tushare", dp_path, records, dry_run, priority=10)


def import_source(conn, ts_code: str, source_type: str, source_path: str,
                  records: list, dry_run: bool, priority: int = 100) -> int:
    """导入一个来源的所有财务记录。返回 observation 数量。"""
    if not records:
        return 0

    count = 0
    batch_id = "" if dry_run else create_batch(conn, ts_code, source_type, source_path)
    prev_row = None

    for rec in records:
        fy_str = str(rec.get("end_date", rec.get("fiscal_year", "")))[:4]
        try:
            fy = int(fy_str)
        except ValueError:
            continue
        if fy < 2000:
            continue

        # ts_code and fiscal_year MUST be set before validation
        # (quality_findings require ts_code/fiscal_year for proper binding)
        rec["ts_code"] = ts_code
        rec["fiscal_year"] = fy

        # Unit detection
        fixed, unit_findings = detect_and_fix_unit(rec)
        if not dry_run:
            write_quality_findings(conn, unit_findings, batch_id)

        # Row validation
        row_findings = validate_row(fixed, prev_row)
        if not dry_run:
            write_quality_findings(conn, row_findings, batch_id)

        # Write observations for all non-NULL fields (even if some BLOCKs exist)
        # Partial records (e.g. income-only without BS) get observations; curation fills gaps
        if not dry_run:
            write_observations_from_dict(conn, batch_id, ts_code, fy, fixed, source_type, priority)

        # Row-level BLOCKs only block if ALL core fields are missing
        core_present = sum(1 for f in CORE_FIELDS if fixed.get(f) is not None)
        has_block = any(f.severity == "BLOCK" for f in row_findings + unit_findings)
        is_total_block = has_block and core_present == 0

        if not dry_run and not is_total_block:
            # Add basic evidence for all observations (not just first one)
            if source_type != "legacy_db":
                obs_rows = conn.execute(
                    "SELECT observation_id, field_name FROM financial_observations WHERE batch_id=? AND fiscal_year=?",
                    (batch_id, fy)).fetchall()
                for o in obs_rows:
                    insert_evidence(conn, o["observation_id"],
                                    doc_path=source_path,
                                    norm_rule=f"source={source_type}, priority={priority}")

        count += 1
        prev_row = fixed

    if not dry_run:
        # Auto-curate
        for rec in records:
            fy_str = str(rec.get("end_date", rec.get("fiscal_year", "")))[:4]
            try:
                fy = int(fy_str)
            except ValueError:
                continue
            if fy < 2000: continue
            n = auto_curate(conn, ts_code, fy)
            if n > 0:
                # Cross-source reconciliation for this year
                sources = conn.execute("""
                    SELECT DISTINCT source_type FROM financial_observations
                    WHERE ts_code=? AND fiscal_year=? AND status='candidate'
                """, (ts_code, fy)).fetchall()
                if len(sources) >= 2:
                    _reconcile_year(conn, ts_code, fy, batch_id)

    return count


def _reconcile_year(conn, ts_code: str, fiscal_year: int, batch_id: str):
    """跨源对账：对比同一字段不同来源的值（包括已 accepted 的来源）。"""
    for field in CORE_FIELDS + ["n_cashflow_act", "c_pay_acq_const_fiolta"]:
        obs = conn.execute("""
            SELECT * FROM financial_observations
            WHERE ts_code=? AND fiscal_year=? AND field_name=?
            AND status IN ('candidate','accepted')
            ORDER BY source_priority
        """, (ts_code, fiscal_year, field)).fetchall()
        if len(obs) < 2:
            continue
        finding = validate_cross_source(dict(obs[0]), dict(obs[1]))
        if finding:
            finding.observation_id = obs[0]["observation_id"]
            write_quality_findings(conn, [finding], batch_id)


# ── legacy import (keep backward compat) ──

def import_hk_fallback(conn, ts_code: str, data: dict, dry_run: bool):
    """Import from hk_report_fallback.json (legacy path → observations + curation)."""
    income_list = data.get("income", [])
    bs_list = data.get("balance_sheet", [])
    cf_list = data.get("cashflow", [])
    div_list = data.get("dividends", [])

    records = []
    for inc in income_list:
        year = int(str(inc.get("end_date", ""))[:4])
        if year < 2000: continue
        bs_rec = next((b for b in bs_list if str(b.get("end_date", ""))[:4] == str(year)), {})
        cf_rec = next((c for c in cf_list if str(c.get("end_date", ""))[:4] == str(year)), {})
        div_rec = next((d for d in div_list if str(d.get("end_date", ""))[:4] == str(year)), {})

        def u_float(key, d, default=None):
            v = safe_float(d.get(key), default)
            if v is not None and abs(v) > 100_000:  # Match detect_and_fix_unit threshold
                v = v / 1_000_000
            return v

        rec = {
            "end_date": str(year) + "1231",
            "revenue": u_float("revenue", inc),
            "oper_cost": u_float("oper_cost", inc),
            "n_income_attr_p": u_float("n_income_attr_p", inc),
            "d_a": (u_float("depr_fa_coga_dpba", inc, 0) or 0) + (u_float("amort_intang_assets", inc, 0) or 0),
            "money_cap": u_float("money_cap", bs_rec),
            "accounts_receiv": u_float("accounts_receiv", bs_rec),
            "acct_payable": u_float("acct_payable", bs_rec),
            "contract_liab": u_float("contract_liab", bs_rec),
            "total_assets": u_float("total_assets", bs_rec),
            "total_liab": u_float("total_liab", bs_rec),
            "total_hldr_eqy_exc_min_int": u_float("total_hldr_eqy_exc_min_int", bs_rec),
            "minority_int": u_float("minority_int", bs_rec),
            "goodwill": u_float("goodwill", bs_rec),
            "n_cashflow_act": u_float("n_cashflow_act", cf_rec),
            "c_pay_acq_const_fiolta": abs(u_float("c_pay_acq_const_fiolta", cf_rec, 0) or 0),
            "dividends_paid": u_float("dividends_paid", cf_rec) or u_float("cash_div_tax", div_rec),
        }
        records.append(rec)

    return import_source(conn, ts_code, "tushare_hk_fallback",
                        f"output/{ts_code.replace('.','_')}/hk_report_fallback.json",
                        records, dry_run, priority=20)


def import_input_data(conn, ts_code: str, data: dict, dry_run: bool):
    """Import from input_data.json (verified PDF data)."""
    years = data.get("years", [])
    n = len(years)

    def get_arr(key):
        return data.get(key, [None] * n)

    records = []
    for i, y in enumerate(years):
        if y.startswith("FY"): y = y[2:]
        try: fy = int(y)
        except ValueError: continue
        if fy < 2000: continue

        rec = {"end_date": str(fy) + "1231"}
        field_map = {
            "revenue": "revenue", "oper_cost": "oper_cost", "n_income_attr_p": "n_income_attr_p",
            "d_a": "d_a", "money_cap": "money_cap", "cash_broad": "cash_broad",
            "accounts_receiv": "accounts_receiv", "acct_payable": "acct_payable",
            "contract_liab": "contract_liab", "total_assets": "total_assets",
            "total_liab": "total_liab", "total_hldr_eqy_exc_min_int": "equity",
            "minority_int": "minority", "goodwill": "goodwill",
            "n_cashflow_act": "ocf", "c_pay_acq_const_fiolta": "capex",
            "fcf": "fcf", "dividends_paid": "dividend_total",
            "eps": "eps", "dps": "dps", "gross_margin": "gross_margin",
        }
        for db_field, json_key in field_map.items():
            vals = get_arr(json_key)
            if i < len(vals):
                rec[db_field] = safe_float(vals[i])
        records.append(rec)

    return import_source(conn, ts_code, "pdf_verified",
                        f"output/{ts_code.replace('.','_')}/input_data.json",
                        records, dry_run, priority=2)


# ── CLI ──

def migrate_stock(conn, ts_code: str, stock_dir: str, dry_run: bool):
    print(f"  📦 {ts_code}...", end=" ")
    count = 0

    # Extract shares from input_data.json (works for all stocks, with or without datapack)
    shares_m = None
    input_path = os.path.join(stock_dir, "input_data.json")
    if os.path.exists(input_path):
        with open(input_path) as f2:
            idata = json.load(f2)
        shares_m = idata.get("shares_m")

    # Stock basic info + A-share markdown import
    dp_path = os.path.join(stock_dir, "data_pack_market.md")
    if os.path.exists(dp_path):
        with open(dp_path) as f:
            text = f.read()
        m = re.search(r'公司名称\s*\|\s*(.+?)\s*\|', text)
        name_cn = m.group(1) if m else None
        market = "HK" if ts_code.endswith(".HK") else "A"

        # Extract shares from market cap / price (only if not already from input_data)
        if shares_m is None and market == "A":
            # A-share: 总市值 (万元) / 当前价格
            m_mc = re.search(r'总市值\s*\(万元\)\s*\|\s*([\d,.]+)', text)
            m_price = re.search(r'当前价格\s*\|\s*([\d,.]+)', text)
            if m_mc and m_price:
                mc_wan = float(m_mc.group(1).replace(",", ""))
                price = float(m_price.group(1).replace(",", ""))
                if price > 0:
                    shares_m = round(mc_wan / price / 100, 2)  # 万元/元/100 → 百万股
        # HK shares_m was already extracted from input_data.json above

        if not dry_run:
            conn.execute("""INSERT OR REPLACE INTO stocks (ts_code, name_cn, market, shares_m, updated_at)
                VALUES (?,?,?,?,datetime('now','localtime'))""",
                (ts_code, name_cn, market, shares_m))
        count += 1

        # For A-shares: parse markdown tables (no JSON fallback exists)
        if market == "A" and not os.path.exists(os.path.join(stock_dir, "hk_report_fallback.json")):
            n = import_datapack_markdown(conn, ts_code, dp_path, dry_run)
            if n > 0:
                print(f"markdown({n}y) ", end="")
                count += 1
    else:
        # No data_pack_market.md — still need to insert stock with shares if available
        market = "HK" if ts_code.endswith(".HK") else "A"
        if not dry_run:
            conn.execute("""INSERT OR REPLACE INTO stocks (ts_code, name_cn, market, shares_m, updated_at)
                VALUES (?,?,?,?,datetime('now','localtime'))""",
                (ts_code, None, market, shares_m))
        count += 1

    # hk_report_fallback
    hkfb = os.path.join(stock_dir, "hk_report_fallback.json")
    if os.path.exists(hkfb):
        with open(hkfb) as f:
            data = json.load(f)
            if data.get("income"):
                import_hk_fallback(conn, ts_code, data, dry_run)
                count += 1
                print("hk_fallback ", end="")

    # input_data (preferred)
    inp = os.path.join(stock_dir, "input_data.json")
    if os.path.exists(inp):
        with open(inp) as f:
            import_input_data(conn, ts_code, json.load(f), dry_run)
            count += 1
            print("input_data ", end="")

    # threshold
    th = os.path.join(stock_dir, "threshold.json")
    if os.path.exists(th):
        with open(th) as f:
            d = json.load(f)
            if not dry_run:
                conn.execute("""INSERT OR REPLACE INTO thresholds (ts_code, II, star_5, star_4, star_3, category, rationale, evidence, adjustments)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (ts_code, safe_float(d.get("II")), safe_float(d.get("star_5")), safe_float(d.get("star_4")),
                     safe_float(d.get("star_3")), d.get("category"), d.get("rationale"),
                     json.dumps(d.get("evidence",[])), json.dumps(d.get("adjustments",[]))))
            count += 1
            print("threshold ", end="")

    # fix_plan → data_quality_log
    fp = os.path.join(stock_dir, "fix_plan.json")
    if os.path.exists(fp):
        with open(fp) as f:
            d = json.load(f)
            if not dry_run:
                conn.execute("""INSERT INTO data_quality_log (ts_code, check_time, layer, verdict, blocks, warns, missing_critical, missing_asset)
                    VALUES (?,datetime('now','localtime'),'data_gate',?,?,?,?,?)""",
                    (ts_code, d.get("verdict"), json.dumps(d.get("blocks",[])), json.dumps(d.get("warns",[])),
                     json.dumps(d.get("missing_critical",[])), json.dumps(d.get("missing_asset",[]))))
            count += 1
            print("fix_plan ", end="")

    # Audit: log legacy data
    if not dry_run:
        fb_count = conn.execute("SELECT COUNT(*) FROM annual_financials WHERE ts_code=? AND data_source IS NULL", (ts_code,)).fetchone()[0]
        if fb_count > 0:
            conn.execute("""UPDATE annual_financials SET data_source='legacy_db', data_quality='legacy'
                WHERE ts_code=? AND data_source IS NULL""", (ts_code,))

    # Cross-source stats
    if not dry_run:
        fb = conn.execute("SELECT COUNT(*) FROM financial_observations WHERE ts_code=? AND source_type='tushare_hk_fallback'", (ts_code,)).fetchone()[0]
        vf = conn.execute("SELECT COUNT(*) FROM financial_observations WHERE ts_code=? AND source_type='pdf_verified'", (ts_code,)).fetchone()[0]
        if fb > 0 and vf > 0:
            print(f"dual({fb}fb+{vf}vf) ", end="")

    print(f"✅ ({count} sources)")


def main():
    p = argparse.ArgumentParser(description="migrate_to_db.py v3.1 — 候选→门禁→策展→事实")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--code", type=str)
    args = p.parse_args()

    if not os.path.exists(OUTPUT_DIR):
        print(f"ERROR: {OUTPUT_DIR} not found", file=sys.stderr)
        return 1

    conn = None if args.dry_run else sqlite3.connect(DB_PATH)
    if conn:
        conn.row_factory = sqlite3.Row

    stock_dirs = []
    for entry in sorted(os.listdir(OUTPUT_DIR)):
        full = os.path.join(OUTPUT_DIR, entry)
        if not os.path.isdir(full) or entry.startswith("."):
            continue
        parts = entry.split("_")
        code = parts[0]
        if "." not in code:
            if len(code) == 5 and code.isdigit():
                code += ".HK"
            elif len(code) == 6 and code.isdigit():
                if code.startswith("6") or code.startswith("68"):
                    code += ".SH"   # Shanghai
                else:
                    code += ".SZ"   # Shenzhen (000/001/002/003/300)
        if args.code and code != args.code:
            continue
        stock_dirs.append((code, full))

    mode = "🔍 DRY RUN" if args.dry_run else "📥 IMPORTING (v3.1 candidate→curation)"
    print(f"{mode} {len(stock_dirs)} stocks → {DB_PATH}\n")

    for code, sdir in stock_dirs:
        migrate_stock(conn, code, sdir, args.dry_run)

    if conn:
        conn.commit()
        # Stats
        obs_n = conn.execute("SELECT COUNT(*) FROM financial_observations").fetchone()[0]
        find_n = conn.execute("SELECT COUNT(*) FROM quality_findings").fetchone()[0]
        cur_n = conn.execute("SELECT COUNT(*) FROM curation_decisions").fetchone()[0]
        af_n = conn.execute("SELECT COUNT(*) FROM annual_financials").fetchone()[0]
        batch_n = conn.execute("SELECT COUNT(*) FROM raw_import_batches").fetchone()[0]
        conn.close()
        print(f"\n✅ observations: {obs_n} | quality_findings: {find_n} | curation: {cur_n} | financials: {af_n} | batches: {batch_n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
