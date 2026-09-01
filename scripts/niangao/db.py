"""niangao.db — 数据层：portfolio.db 的 schema、CRUD、迁移、分析成果存取"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")
# 年糕系统数据放在 analy/ 根目录，与 Turtle output 分离
_ANALY_DIR = os.path.dirname(_FRAMEWORK_DIR)  # analy/
_NIANGAO_DIR = os.path.join(_ANALY_DIR, "_niangao")

import sys as _sys
_scripts_dir = os.path.join(_FRAMEWORK_DIR, "scripts")
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)
try:
    from turtle_agent._version import REPORT_VERSION, CHAPTERS_SUBDIR, REPORTS_SUBDIR
except ImportError:
    REPORT_VERSION  = "v13"
    CHAPTERS_SUBDIR = "chapters"
    REPORTS_SUBDIR  = "reports"
_DB_PATH = os.path.join(_NIANGAO_DIR, "portfolio.db")
_DEFAULT_INVEST_PATH = os.path.join(_ANALY_DIR, "invest")

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis (
    ts_code TEXT PRIMARY KEY, name TEXT, market TEXT, analyzed_at TEXT,
    price REAL, price_rmb REAL, mc_rmb REAL,
    gg_base REAL, gg_discounted REAL, gg_fcfe REAL, ii REAL, aa_3y REAL, dps REAL,
    p_base_hkd REAL, p_base_rmb REAL, p_fcfe_hkd REAL,
    upside_pct REAL, buy_price REAL, buy_star INTEGER, buy_upside REAL,
    pos_pct REAL, decision TEXT,
    parent_ratio REAL, net_cash_pct_mc REAL, extrap_overall TEXT,
    vt_excluded INTEGER, gg_ok INTEGER,
    stock_dir TEXT, report_html TEXT,
    sources_json TEXT, updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL, analyzed_at TEXT NOT NULL,
    gg_base REAL, gg_discounted REAL, ii REAL, p_base_hkd REAL, upside_pct REAL,
    decision TEXT, pos_pct REAL, stock_dir TEXT, notes TEXT,
    UNIQUE(ts_code, analyzed_at)
);

CREATE TABLE IF NOT EXISTS watchlist (
    ts_code TEXT PRIMARY KEY, invest_code TEXT, name TEXT, market TEXT,
    in_invest INTEGER DEFAULT 0, invest_status TEXT,
    current_hold INTEGER DEFAULT 0, avg_cost REAL, hold_limit_pct REAL,
    annual_div_per_share REAL, invest_logic TEXT,
    my_valuation REAL, turtle_valuation REAL, live_price REAL,
    sector TEXT, stock_type TEXT, pe REAL, pb REAL, debt_ratio REAL, fcf_yield REAL,
    mth_enabled INTEGER DEFAULT 0, mth_cycle INTEGER DEFAULT 1,
    lock_reserve INTEGER DEFAULT 1, cumulative_div REAL DEFAULT 0,
    dividend_tax_rate REAL DEFAULT 0, account_id INTEGER DEFAULT 1,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS holding_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL, sync_at TEXT NOT NULL,
    current_hold INTEGER, avg_cost REAL, status TEXT,
    UNIQUE(ts_code, sync_at)
);

CREATE TABLE IF NOT EXISTS investment_plan (
    ts_code TEXT PRIMARY KEY,
    stop_loss_hkd REAL,
    stop_loss_conditions TEXT,
    batch_buy_json TEXT,
    observation_signals TEXT,
    core_thesis TEXT,
    conviction TEXT,
    position_pct REAL,
    position_rationale TEXT,
    re_eval_triggers TEXT,
    business_model TEXT,
    recent_changes TEXT,
    core_tension TEXT,
    analyzed_at TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_history_ts_code ON analysis_history(ts_code);
CREATE INDEX IF NOT EXISTS idx_history_at ON analysis_history(analyzed_at);

-- 财富快照（从 invest DB 同步，持久化历史）
CREATE TABLE IF NOT EXISTS wealth_snapshot (
    snapshot_at INTEGER PRIMARY KEY,
    total_wealth_cny REAL NOT NULL,
    stock_value_cny REAL,
    cash_value_cny REAL,
    event_type TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 年度摘要
CREATE TABLE IF NOT EXISTS annual_summary (
    year INTEGER PRIMARY KEY,
    market_value_cny REAL,
    cumulative_pnl_cny REAL,
    dividend_cny REAL,
    pnl_offset_cny REAL,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 提醒快照
CREATE TABLE IF NOT EXISTS alert_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    alert_type TEXT NOT NULL,
    target_price REAL,
    is_active INTEGER DEFAULT 1,
    is_triggered INTEGER DEFAULT 0,
    current_price REAL,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 交易记录
CREATE TABLE IF NOT EXISTS trade_record (
    id INTEGER PRIMARY KEY,
    stock_code TEXT,
    stock_name TEXT,
    trade_type TEXT,
    price REAL,
    shares INTEGER,
    amount REAL,
    trade_at INTEGER,
    dividend_year INTEGER,
    commission REAL DEFAULT 0,
    synced_at TEXT DEFAULT (datetime('now'))
);


-- 持仓盈亏快照（每次同步覆盖计算）
CREATE TABLE IF NOT EXISTS position_pnl (
    ts_code TEXT PRIMARY KEY,
    invest_code TEXT,
    name TEXT,
    current_hold INTEGER,
    avg_cost REAL,
    live_price REAL,
    market_value REAL,
    unrealized_pnl REAL,
    dividend_est REAL,
    total_return REAL,
    total_return_pct REAL,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 已清仓盈亏（完全卖出的股票，不含部分减持）
CREATE TABLE IF NOT EXISTS realized_pnl (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT,
    total_buy_amt REAL,
    total_sell_amt REAL,
    realized_pnl REAL,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 现金流

-- 账户信息（对飙 invest DB account 表）
CREATE TABLE IF NOT EXISTS account (
    id INTEGER PRIMARY KEY,
    name TEXT,
    ownership_pct REAL,
    pnl_baseline_year INTEGER,
    pnl_baseline_raw REAL,
    pnl_baseline_target REAL,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 现金（对飙 invest DB cash 表）
CREATE TABLE IF NOT EXISTS cash (
    currency TEXT,
    account_id INTEGER,
    amount REAL,
    last_updated INTEGER,
    synced_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (currency, account_id)
);

-- 价格历史（对飙 invest DB price_history 表）
CREATE TABLE IF NOT EXISTS price_history (
    stock_id INTEGER,
    trade_date TEXT,
    close_price REAL,
    high_price REAL,
    low_price REAL,
    open_price REAL,
    prev_close_price REAL,
    volume REAL,
    updated_at INTEGER,
    synced_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (stock_id, trade_date)
);

-- 基本面历史（对飙 invest DB fundamentals_history 表）
CREATE TABLE IF NOT EXISTS fundamentals_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    year INTEGER,
    pe REAL,
    pb REAL,
    debt_ratio REAL,
    ev REAL,
    ebitda REAL,
    fcf_yield REAL,
    pe_source TEXT,
    pb_source TEXT,
    debt_ratio_source TEXT,
    ev_source TEXT,
    fcf_yield_source TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 月底价格（对飙 invest DB month_end_price 表）
CREATE TABLE IF NOT EXISTS month_end_price (
    stock_id INTEGER,
    year_month TEXT,
    trade_date TEXT,
    close_price REAL,
    updated_at INTEGER,
    synced_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (stock_id, year_month)
);

-- 月底汇率（对飙 invest DB month_end_exchange_rate 表）
CREATE TABLE IF NOT EXISTS month_end_exchange_rate (
    year_month TEXT PRIMARY KEY,
    hkd_rate REAL,
    usd_rate REAL,
    eur_rate REAL,
    updated_at INTEGER,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 提醒结算（对飙 invest DB alert_settlement 表）
CREATE TABLE IF NOT EXISTS alert_settlement (
    id INTEGER PRIMARY KEY,
    alert_id INTEGER,
    stock_id INTEGER,
    transaction_id INTEGER,
    alert_type TEXT,
    target_price REAL,
    settled_price REAL,
    settled_shares INTEGER,
    settled_amount REAL,
    source TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 分账户快照（对飙 invest DB account_portfolio_snapshot 表）
CREATE TABLE IF NOT EXISTS account_portfolio_snapshot (
    snapshot_at INTEGER,
    account_id INTEGER,
    total_wealth_cny REAL,
    stock_value_cny REAL,
    cash_value_cny REAL,
    event_type TEXT,
    synced_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (snapshot_at, account_id)
);

CREATE TABLE IF NOT EXISTS cash_flow (
    id INTEGER PRIMARY KEY,
    account_id INTEGER,
    currency TEXT,
    delta_amount REAL,
    delta_cny REAL,
    note TEXT,
    flow_at INTEGER,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- 审计日志（Web 写入操作的不可变记录）
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    target_table TEXT,
    target_key TEXT,
    old_values TEXT,
    new_values TEXT,
    operator TEXT DEFAULT 'web',
    created_at TEXT DEFAULT (datetime('now'))
);

-- 系统设置 (key-value)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 分档建仓计划（对标 Android staged buy plan）
CREATE TABLE IF NOT EXISTS staged_buy_plan (
    ts_code TEXT PRIMARY KEY,
    base_price REAL NOT NULL,
    level_count INTEGER DEFAULT 6,
    levels_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 网格策略配置（对标 Android grid_strategy）
CREATE TABLE IF NOT EXISTS grid_strategy (
    ts_code TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 1,
    step_mode TEXT DEFAULT 'FIXED',
    grid_step REAL DEFAULT 0.05,
    trade_percent REAL DEFAULT 0.10,
    trade_mode TEXT DEFAULT 'FIXED',
    start_holding INTEGER DEFAULT 0,
    high_water_mark_price REAL DEFAULT 0,
    last_trade_price REAL DEFAULT 0,
    cumulative_profit REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 网格交易周期记录（对标 Android grid_cycle_record）
CREATE TABLE IF NOT EXISTS grid_cycle_record (
    id INTEGER PRIMARY KEY,
    stock_code TEXT NOT NULL,
    sell_price REAL NOT NULL,
    sell_shares INTEGER NOT NULL,
    sell_proceeds_cny REAL NOT NULL,
    planned_buy_price REAL,
    buy_price REAL,
    buy_shares INTEGER,
    profit REAL DEFAULT 0.0,
    is_success INTEGER DEFAULT 0,
    completed_at INTEGER,
    synced_at TEXT DEFAULT (datetime('now'))
);
"""


def _load_json(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path): return None
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return None


def _safe_get(d: dict, *keys: str, default=None):
    for k in keys:
        if isinstance(d, dict): d = d.get(k, default)
        else: return default
    return d


def _normalize_invest_code(code: str) -> str:
    """invest code → Turtle code. hk00506→00506.HK  sz000651→000651.SZ"""
    c = code.strip().lower()
    if c.startswith("hk") and len(c) == 7: return f"{c[2:]}.HK"
    if c.startswith("sz") and len(c) == 8: return f"{c[2:]}.SZ"
    if c.startswith("sh") and len(c) == 8: return f"{c[2:]}.SH"
    if c.isdigit() and len(c) <= 5: return f"{int(c):05d}.HK"
    return code


def _turtle_to_invest_code(ts_code: str) -> str:
    c = ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    if ".HK" in ts_code: return f"hk{c}"
    if ".SZ" in ts_code: return f"sz{c}"
    if ".SH" in ts_code: return f"sh{c}"
    return ts_code


def get_db(db_path: str = _DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = sqlite3.connect(db_path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    # Ensure schema_version table exists
    db.execute("""CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')),
        description TEXT
    )""")
    try: db.execute("INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, 'canonical baseline — Web replaces Android invest')")
    except sqlite3.OperationalError: pass
    try: db.execute("ALTER TABLE watchlist ADD COLUMN live_price REAL")
    except sqlite3.OperationalError: pass
    try: db.execute("ALTER TABLE trade_record ADD COLUMN dividend_year INTEGER")
    except sqlite3.OperationalError: pass
    try: db.execute("ALTER TABLE trade_record ADD COLUMN commission REAL DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: db.execute("ALTER TABLE trade_record ADD COLUMN settlement_ref TEXT")
    except sqlite3.OperationalError: pass
    try: db.execute("ALTER TABLE analysis ADD COLUMN sources_json TEXT")
    except sqlite3.OperationalError: pass
    for col in ["sector TEXT", "stock_type TEXT", "pe REAL", "pb REAL", "debt_ratio REAL", "fcf_yield REAL",
                "mth_enabled INTEGER DEFAULT 0", "mth_cycle INTEGER DEFAULT 1", "lock_reserve INTEGER DEFAULT 1",
                "cumulative_div REAL DEFAULT 0", "dividend_tax_rate REAL DEFAULT 0", "account_id INTEGER DEFAULT 1"]:
        try: db.execute(f"ALTER TABLE watchlist ADD COLUMN {col}")
        except sqlite3.OperationalError: pass
    return db


# ── extract from compute_bundle ─────────────────────────────────────


def _classify_decision(gg, ii, best_tier, vt):
    """根据 GG/II/上涨空间/价值陷阱 自动分类决策。"""
    if gg is None or gg <= 0:
        return "⚠️待重分析"
    upside = best_tier.get("upside_pct", 0) if best_tier else 0
    vt_excluded = vt.get("excluded", False) if isinstance(vt, dict) else False
    # 与 compute_bundle.py verdict 逻辑一致
    jj = gg - ii
    if gg > ii:
        if upside >= 30 and jj >= 2.0 and not vt_excluded:
            return "Strong Buy"
        elif upside > 0:
            return "Buy"
        else:
            return "Hold"
    elif gg >= ii - 1:
        return "Hold"
    else:
        return "Avoid"

def extract_from_bundle(cb_path: str, contract_path: str = "", stock_dir: str = "") -> dict[str, Any]:
    cb = _load_json(cb_path)
    if not cb: return {}
    contract = _load_json(contract_path)
    ts_code = _safe_get(cb, "meta", "code", default="?")
    market_flag = "H" if ".HK" in ts_code else "A" if (".SH" in ts_code or ".SZ" in ts_code) else "?"

    mkt = cb.get("market", {})
    price = mkt.get("price_hkd") or mkt.get("price") or 0
    price_rmb = mkt.get("price_rmb") or price
    mc = mkt.get("mc_hkd") or mkt.get("mc_rmb") or 0

    p = cb.get("params", {})
    II = p.get("II", 0); dps = p.get("dps_fy") or p.get("DPS") or 0

    f3 = cb.get("factor3", {})
    gg = f3.get("gg", {})
    gg_base = gg.get("base")
    gg_discounted = _safe_get(f3, "gg_discounted", "base")
    gg_fcfe = _safe_get(f3, "gg_fcfe", "base")
    aa_3y = _safe_get(f3, "aa_avg", "3y")
    minority = f3.get("minority_adjustment", {})

    f4 = cb.get("factor4", {})
    tiers = f4.get("tiers", [])
    p_base = f4.get("p_base", {})
    vt = f4.get("value_trap", {})
    position = f4.get("position", {})

    best_tier = None
    # Pick highest star with positive upside (deepest discount = best entry)
    for t in reversed(tiers or []):
        if t.get("upside_pct", -999) > 0:
            best_tier = t; break
    if not best_tier and tiers: best_tier = tiers[-1]  # fallback: 5-star (deepest discount)

    date_str = ""
    if contract: date_str = contract.get("generated_at", "")[:19]
    if not date_str: date_str = _safe_get(cb, "meta", "date", default="")[:19]
    if not date_str: date_str = datetime.now().isoformat()
    gg_ok = gg_base is not None and 0.01 < gg_base < 500

    report_html = ""
    if stock_dir:
        # Try multiple filename patterns (some have market suffix, some don't)
        code_clean = ts_code.replace(".", "_")          # 01502_HK
        code_short = ts_code.split(".")[0]              # 01502
        for name in (f"{code_clean}_分析报告_{REPORT_VERSION}.html", f"{code_short}_分析报告_{REPORT_VERSION}.html"):
            # v13+: reports/ subdir
            cand = os.path.join(stock_dir, REPORTS_SUBDIR, name)
            if os.path.exists(os.path.join(_OUTPUT_DIR, cand)):
                report_html = cand
                break
            # legacy v12 fallback at root
            cand_v12 = os.path.join(stock_dir, name.replace(f"_{REPORT_VERSION}.html", "_v12.html"))
            if os.path.exists(os.path.join(_OUTPUT_DIR, cand_v12)):
                report_html = cand_v12
                break

    # Extract Chinese name from stock_dir (e.g. "00506_中国食品" → "中国食品")
    _stock_name = stock_dir.split("_", 1)[1] if (stock_dir and "_" in stock_dir) else ""

    return {
        "ts_code": ts_code, "name": _stock_name, "market": market_flag,
        "analyzed_at": date_str, "price": price, "price_rmb": price_rmb, "mc_rmb": mc,
        "gg_base": gg_base, "gg_discounted": gg_discounted, "gg_fcfe": gg_fcfe,
        "ii": II, "aa_3y": aa_3y, "dps": dps,
        "p_base_hkd": p_base.get("price_hkd") if isinstance(p_base, dict) else None,
        "p_base_rmb": p_base.get("price_rmb") if isinstance(p_base, dict) else None,
        "p_fcfe_hkd": (p_base.get("p_fcfe", {}) or {}).get("price_hkd") if isinstance(p_base, dict) else None,
        "upside_pct": p_base.get("upside_pct") if isinstance(p_base, dict) else None,
        "buy_price": best_tier.get("price_hkd") if best_tier else None,
        "buy_star": best_tier.get("star") if best_tier else None,
        "buy_upside": best_tier.get("upside_pct") if best_tier else None,
        "pos_pct": position.get("base_pct") or position.get("capped_pct", 0) if isinstance(position, dict) else 0,
                "decision": _classify_decision(gg_base, II, best_tier, vt),
        "parent_ratio": minority.get("parent_ratio_3y"),
        "net_cash_pct_mc": f3.get("net_cash_pct_mc"),
        "extrap_overall": f3.get("extrapolation_rating", {}).get("overall", "?"),
        "vt_excluded": 1 if (vt.get("exclude", False) if isinstance(vt, dict) else False) else 0,
        "gg_ok": 1 if gg_ok else 0, "stock_dir": stock_dir, "report_html": report_html,
        "sources_json": json.dumps(extract_sources_from_chapters(stock_dir), ensure_ascii=False),
    }


# ── CRUD ─────────────────────────────────────────────────────────────

def upsert_analysis(data: dict[str, Any], db_path: str = _DB_PATH) -> None:
    db = get_db(db_path)
    cols = [k for k in data]
    db.execute(f"INSERT OR REPLACE INTO analysis ({', '.join(cols)}) VALUES ({', '.join('?'*len(cols))})",
               [data.get(k) for k in cols])
    hist_cols = ["ts_code", "analyzed_at", "gg_base", "gg_discounted", "ii",
                 "p_base_hkd", "upside_pct", "decision", "pos_pct", "stock_dir"]
    db.execute(f"INSERT OR IGNORE INTO analysis_history ({', '.join(hist_cols)}) VALUES ({', '.join('?'*len(hist_cols))})",
               [data.get(k) for k in hist_cols])
    db.commit(); db.close()


def upsert_investment_plan(ts_code: str, cb_path: str, stock_dir: str = "", db_path: str = _DB_PATH) -> dict | None:
    """从 compute_bundle.json + 定性章节 提取投资计划，写入 investment_plan 表。"""
    cb = _load_json(cb_path)
    if not cb: return None
    f4 = cb.get("factor4", {})
    f3 = cb.get("factor3", {})
    vt = f4.get("value_trap", {}) if isinstance(f4.get("value_trap"), dict) else {}

    # Extract qualitative from chapter files
    qual = extract_qualitative_from_chapters(stock_dir or os.path.basename(os.path.dirname(cb_path)))

    # Stop loss
    sl = f4.get("stop_loss", {}) if isinstance(f4.get("stop_loss"), dict) else {}
    sl_hkd = sl.get("hard_hkd")
    sl_conditions = ", ".join(filter(None, [
        sl.get("fundamental", ""), sl.get("time", ""), sl.get("event", "")
    ]))

    # Batch buy plan from tiers
    tiers = f4.get("tiers", [])
    batch_buy = []
    for t in tiers:
        batch_buy.append({
            "star": t.get("star"), "price_hkd": t.get("price_hkd"),
            "upside_pct": t.get("upside_pct"), "action": _action_for_star(t.get("star"))
        })

    # Observation signals
    signals = []
    if isinstance(vt, dict):
        for t in vt.get("triggers", []) or []: signals.append(f"⚠️{t}")
        for u in vt.get("unknown", []) or []: signals.append(f"?{u}")

    # Verdict layers
    verdict = f4.get("verdict", {}) if isinstance(f4.get("verdict"), dict) else {}
    gg_gate = (verdict.get("gg_layer", {}) or {}).get("gate", "?")
    ddm_gate = (verdict.get("ddm_layer", {}) or {}).get("gate", "?")

    # Position
    pos = f4.get("position", {}) if isinstance(f4.get("position"), dict) else {}

    plan = {
        "ts_code": ts_code,
        "stop_loss_hkd": sl_hkd,
        "stop_loss_conditions": sl_conditions[:200] if sl_conditions else None,
        "batch_buy_json": json.dumps(batch_buy, ensure_ascii=False) if batch_buy else None,
        "observation_signals": ", ".join(signals)[:300] if signals else None,
        "core_thesis": f"GG={f3.get('gg',{}).get('base','?')}% vs II={cb.get('params',{}).get('II','?')}% | {gg_gate}/{ddm_gate}",
        "conviction": "high" if gg_gate == "准入" and ddm_gate == "便宜" else "medium",
        "position_pct": pos.get("base_pct") or pos.get("capped_pct"),
        "position_rationale": str(pos.get("rationale", ""))[:200] if pos.get("rationale") else None,
        "re_eval_triggers": f"价格偏离>20% | 距分析>90天 | {sl.get('fundamental','')}",
        "business_model": qual.get("business_model", "")[:300] or None,
        "recent_changes": qual.get("recent_changes", "")[:300] or None,
        "core_tension": qual.get("core_tension", "")[:300] or None,
        "analyzed_at": cb.get("meta", {}).get("date", "") or _safe_get(cb, "meta", "date", default=""),
    }

    db = get_db(db_path)
    cols = list(plan.keys())
    db.execute(f"INSERT OR REPLACE INTO investment_plan ({', '.join(cols)}) VALUES ({', '.join('?'*len(cols))})",
               [plan[k] for k in cols])
    db.commit(); db.close()
    return plan


def extract_sources_from_chapters(stock_dir: str) -> list[dict]:
    """从所有 _ch*.md 章节文件中提取 [source: ...] 标注。

    返回结构化的来源列表，每个条目包含章节、来源文件和引用键。
    """
    import re
    sources = []
    if not stock_dir:
        return sources

    base = os.path.join(_OUTPUT_DIR, stock_dir)
    if not os.path.isdir(base):
        return sources

    # Match [source: filename key] or [source: filename]
    source_re = re.compile(r'\[source:\s*([^\]]+)\]')

    for ch_name in sorted(os.listdir(base)):
        if not ch_name.startswith("_ch") or not ch_name.endswith(".md"):
            continue
        ch_path = os.path.join(base, ch_name)
        try:
            with open(ch_path, encoding="utf-8") as f:
                text = f.read()
        except Exception:
            continue

        # Find section headings for context
        section = ""
        for line in text.split("\n"):
            if line.startswith("### ") or line.startswith("## "):
                section = line.lstrip("# ").strip()

            matches = source_re.findall(line)
            for m in matches:
                parts = m.strip().split(None, 1)
                source_file = parts[0] if parts else m.strip()
                source_key = parts[1] if len(parts) > 1 else ""

                # Deduplicate: same file+key in same chapter → skip
                dup = any(
                    s.get("chapter") == ch_name.replace("_ch", "").replace(".md", "")
                    and s.get("source_file") == source_file
                    and s.get("source_key") == source_key
                    for s in sources
                )
                if not dup:
                    sources.append({
                        "chapter": ch_name.replace("_ch", "").replace(".md", ""),
                        "section": section,
                        "source_file": source_file,
                        "source_key": source_key,
                    })

    return sources


def extract_qualitative_from_chapters(stock_dir: str) -> dict:
    """从 _ch*.md 章节文件中提取结论要点。"""
    import re
    result = {"business_model": "", "recent_changes": "", "core_tension": ""}
    if not stock_dir: return result

    ch_map = {"_ch01.md": "business_model", "_ch04.md": "recent_changes", "_ch09.md": "core_tension"}
    for ch_file, field in ch_map.items():
        # v13+: chapters/ subdir; fallback to root for legacy
        path_sub  = os.path.join(_OUTPUT_DIR, stock_dir, CHAPTERS_SUBDIR, ch_file)
        path_root = os.path.join(_OUTPUT_DIR, stock_dir, ch_file)
        path = path_sub if os.path.exists(path_sub) else path_root
        if not os.path.exists(path): continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            # Extract bullet points from 结论要点 section
            m = re.search(r'### 结论要点\s*\n(.*?)(?=### |$)', text, re.DOTALL)
            if m:
                content = m.group(1).strip()
                # 解析多行 bullet：收集每个 bullet 及其后续缩进行
                bullets = []
                current_bullet = ""
                for line in content.split("\n"):
                    if line.strip().startswith("- "):
                        if current_bullet:
                            bullets.append(current_bullet.strip())
                        current_bullet = line.strip()[2:]  # 去掉 "- "
                    elif current_bullet and (line.startswith("  ") or line.startswith("\t")):
                        current_bullet += " " + line.strip()  # 追加缩进行
                    else:
                        if current_bullet:
                            bullets.append(current_bullet.strip())
                            current_bullet = ""
                if current_bullet:
                    bullets.append(current_bullet.strip())
                result[field] = " | ".join(bullets[:3])[:300] if bullets else ""
        except Exception:
            pass
    return result


def _action_for_star(star):
    if star == 5: return "满仓买入(最深折扣)"
    if star == 4: return "重仓买入"
    if star == 3: return "标准仓位"
    if star == 2: return "轻仓试探"
    return "观察跟踪"


def get_investment_plan(ts_code: str, db_path: str = _DB_PATH) -> dict | None:
    db = get_db(db_path)
    r = db.execute("SELECT * FROM investment_plan WHERE ts_code=?", (ts_code,)).fetchone()
    db.close()
    if r: r = dict(r)
    return r


def get_all_analyses(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    db = get_db(db_path)
    rows = db.execute("""
        SELECT a.*, w.invest_code, w.invest_status, w.current_hold, w.avg_cost AS inv_avg_cost,
               w.hold_limit_pct AS inv_hold_limit_pct, w.annual_div_per_share AS inv_dps,
               w.invest_logic AS inv_logic, w.my_valuation AS inv_valuation, w.live_price,
               w.name AS wl_name
        FROM analysis a LEFT JOIN watchlist w ON a.ts_code = w.ts_code
        ORDER BY a.gg_discounted DESC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_unanalyzed_holdings(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """返回所有在 invest 关注但尚未分析的股票（含持有和观察）。"""
    db = get_db(db_path)
    analyzed = [r["ts_code"] for r in db.execute("SELECT ts_code FROM analysis").fetchall()]
    if not analyzed:
        rows = db.execute("SELECT * FROM watchlist WHERE in_invest = 1 ORDER BY current_hold DESC").fetchall()
    else:
        rows = db.execute(f"SELECT * FROM watchlist WHERE in_invest = 1 AND ts_code NOT IN ({','.join('?'*len(analyzed))}) ORDER BY current_hold DESC", analyzed).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_analysis_history(ts_code: str, db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    db = get_db(db_path)
    rows = db.execute("SELECT * FROM analysis_history WHERE ts_code=? ORDER BY analyzed_at DESC", (ts_code,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_rerun_suggestions(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    db = get_db(db_path)
    suggestions = []
    for r in db.execute("SELECT a.ts_code, w.name, '数据异常' AS reason, 1 AS priority FROM analysis a LEFT JOIN watchlist w ON a.ts_code=w.ts_code WHERE a.gg_ok=0").fetchall():
        suggestions.append(dict(r))
    for r in db.execute("SELECT a.ts_code, w.name, '超90天未更新' AS reason, 2 AS priority FROM analysis a LEFT JOIN watchlist w ON a.ts_code=w.ts_code WHERE a.gg_ok=1 AND a.analyzed_at<datetime('now','-90 days')").fetchall():
        suggestions.append(dict(r))
    for r in db.execute("SELECT a.ts_code, w.name, '超30天+持有中' AS reason, 3 AS priority FROM analysis a LEFT JOIN watchlist w ON a.ts_code=w.ts_code WHERE a.gg_ok=1 AND a.analyzed_at<datetime('now','-30 days') AND w.current_hold>0").fetchall():
        suggestions.append(dict(r))
    for r in db.execute("SELECT w.ts_code, w.name, '持仓未分析' AS reason, 4 AS priority FROM watchlist w WHERE w.current_hold>0 AND w.ts_code NOT IN (SELECT ts_code FROM analysis) ORDER BY w.current_hold DESC").fetchall():
        suggestions.append(dict(r))
    db.close()
    return sorted(suggestions, key=lambda s: (s["priority"], s.get("name", "")))


def migrate_from_files(db_path: str = _DB_PATH) -> int:
    db = get_db(db_path)
    count = 0
    if not os.path.isdir(_OUTPUT_DIR): return 0
    for entry in sorted(os.listdir(_OUTPUT_DIR)):
        stock_dir = os.path.join(_OUTPUT_DIR, entry)
        if not os.path.isdir(stock_dir) or entry.startswith("_"): continue
        cb_path = os.path.join(stock_dir, "compute_bundle.json")
        if not os.path.exists(cb_path): continue
        data = extract_from_bundle(cb_path, os.path.join(stock_dir, "analysis_contract.json"), entry)
        if not data.get("ts_code"): continue
        parts = entry.split("_", 1); data["name"] = parts[1] if len(parts) > 1 else data["ts_code"]
        cols = [k for k in data]
        db.execute(f"INSERT OR REPLACE INTO analysis ({', '.join(cols)}) VALUES ({', '.join('?'*len(cols))})", [data.get(k) for k in cols])
        hist_cols = ["ts_code", "analyzed_at", "gg_base", "gg_discounted", "ii", "p_base_hkd", "upside_pct", "decision", "pos_pct", "stock_dir"]
        db.execute(f"INSERT OR IGNORE INTO analysis_history ({', '.join(hist_cols)}) VALUES ({', '.join('?'*len(hist_cols))})", [data.get(k) for k in hist_cols])
        count += 1
    db.commit(); db.close()
    return count
