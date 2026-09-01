#!/usr/bin/env python3
"""portfolio_db.py — 分析成果数据库层

管理 portfolio.db（独立于 stock_analysis.db）：
  - analysis: 每只股票最新分析成果（UPSERT）
  - analysis_history: 历史记录（每次分析追加）
  - watchlist: 关注列表（来自 invest stocks.csv + stocks_import.json）
  - holding_sync: invest 持仓快照

Usage:
  python scripts/portfolio_db.py --migrate              # 首次迁移：扫描 output/ → DB
  python scripts/portfolio_db.py --sync-invest          # 同步 invest 数据到 watchlist
  python scripts/portfolio_db.py --upsert 00506.HK      # 手动更新单只股票
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")
_DB_PATH = os.path.join(_OUTPUT_DIR, "portfolio.db")
_DEFAULT_INVEST_PATH = os.path.join(os.path.dirname(_FRAMEWORK_DIR), "invest")

_scripts_dir = os.path.join(_FRAMEWORK_DIR, "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
try:
    from turtle_agent._version import REPORT_VERSION, REPORTS_SUBDIR
except ImportError:
    REPORT_VERSION = "v13"
    REPORTS_SUBDIR = "reports"

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis (
    ts_code TEXT PRIMARY KEY,
    name TEXT,
    market TEXT,
    analyzed_at TEXT,
    price REAL,
    price_rmb REAL,
    mc_rmb REAL,
    gg_base REAL,
    gg_discounted REAL,
    gg_fcfe REAL,
    ii REAL,
    aa_3y REAL,
    dps REAL,
    p_base_hkd REAL,
    p_base_rmb REAL,
    p_fcfe_hkd REAL,
    upside_pct REAL,
    buy_price REAL,
    buy_star INTEGER,
    buy_upside REAL,
    pos_pct REAL,
    decision TEXT,
    parent_ratio REAL,
    net_cash_pct_mc REAL,
    extrap_overall TEXT,
    vt_excluded INTEGER,
    gg_ok INTEGER,
    stock_dir TEXT,
    report_html TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    analyzed_at TEXT NOT NULL,
    gg_base REAL,
    gg_discounted REAL,
    ii REAL,
    p_base_hkd REAL,
    upside_pct REAL,
    decision TEXT,
    pos_pct REAL,
    stock_dir TEXT,
    notes TEXT,
    UNIQUE(ts_code, analyzed_at)
);

CREATE TABLE IF NOT EXISTS watchlist (
    ts_code TEXT PRIMARY KEY,
    invest_code TEXT,
    name TEXT,
    market TEXT,
    in_invest INTEGER DEFAULT 0,
    invest_status TEXT,
    current_hold INTEGER DEFAULT 0,
    avg_cost REAL,
    hold_limit_pct REAL,
    annual_div_per_share REAL,
    invest_logic TEXT,
    my_valuation REAL,
    turtle_valuation REAL,
    live_price REAL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS holding_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    sync_at TEXT NOT NULL,
    current_hold INTEGER,
    avg_cost REAL,
    status TEXT,
    UNIQUE(ts_code, sync_at)
);

CREATE INDEX IF NOT EXISTS idx_history_ts_code ON analysis_history(ts_code);
CREATE INDEX IF NOT EXISTS idx_history_at ON analysis_history(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_holding_ts_code ON holding_sync(ts_code);
"""


# ── helpers ─────────────────────────────────────────────────────────

def _load_json(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path): return None
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (json.JSONDecodeError, OSError): return None


def _safe_get(d: dict, *keys: str, default=None):
    for k in keys:
        if isinstance(d, dict): d = d.get(k, default)
        else: return default
    return d


def _normalize_invest_code(code: str) -> str:
    """invest 格式 → Turtle 格式。hk00506→00506.HK  sz000651→000651.SZ"""
    c = code.strip().lower()
    if c.startswith("hk") and len(c) == 7: return f"{c[2:]}.HK"
    if c.startswith("sz") and len(c) == 8: return f"{c[2:]}.SZ"
    if c.startswith("sh") and len(c) == 8: return f"{c[2:]}.SH"
    if c.isdigit() and len(c) <= 5: return f"{int(c):05d}.HK"
    return code


def _turtle_to_invest_code(ts_code: str) -> str:
    c = ts_code.replace(".HK","").replace(".SH","").replace(".SZ","")
    if ".HK" in ts_code: return f"hk{c}"
    if ".SZ" in ts_code: return f"sz{c}"
    if ".SH" in ts_code: return f"sh{c}"
    return ts_code


def _classify_decision(gg, II, upside, vt_excluded, gg_ok):
    if not gg_ok: return "⚠️待重分析"
    if gg is None or II is None or II == 0: return "?"
    if gg > II:
        if upside and upside > 30: return "Strong Buy" if not vt_excluded else "Buy"
        return "Buy" if upside and upside > 0 else "Hold"
    elif gg >= II - 1: return "Hold"
    else: return "Avoid"


# ── extract from compute_bundle ─────────────────────────────────────

def extract_from_bundle(cb_path: str, contract_path: str = "", stock_dir: str = "") -> dict[str, Any]:
    """从 compute_bundle.json 提取关键指标。返回 dict，key 对应 analysis 表列名。"""
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
    II = p.get("II", 0)
    dps = p.get("dps_fy") or p.get("DPS") or 0

    f3 = cb.get("factor3", {})
    gg = f3.get("gg", {})
    gg_base = gg.get("base")
    gg_discounted = _safe_get(f3, "gg_discounted", "base")
    gg_fcfe = _safe_get(f3, "gg_fcfe", "base")
    aa_3y = _safe_get(f3, "aa_avg", "3y")
    net_cash_pct_mc = f3.get("net_cash_pct_mc")
    minority = f3.get("minority_adjustment", {})
    parent_ratio = minority.get("parent_ratio_3y")
    extrap = f3.get("extrapolation_rating", {})
    extrap_overall = extrap.get("overall", "?")

    f4 = cb.get("factor4", {})
    tiers = f4.get("tiers", [])
    p_base = f4.get("p_base", {})
    p_base_hkd = p_base.get("price_hkd") if isinstance(p_base, dict) else None
    p_base_rmb = p_base.get("price_rmb") if isinstance(p_base, dict) else None
    p_fcfe = p_base.get("p_fcfe", {}) if isinstance(p_base, dict) else {}
    upside_pct = p_base.get("upside_pct") if isinstance(p_base, dict) else None
    position = f4.get("position", {})
    pos_pct = position.get("base_pct") or position.get("capped_pct", 0) if isinstance(position, dict) else 0
    vt = f4.get("value_trap", {})
    vt_excluded = vt.get("exclude", False) if isinstance(vt, dict) else False

    # best buy tier
    best_tier = None
    for t in (tiers or []):
        if t.get("upside_pct", -999) > 0: best_tier = t
        else: break
    if not best_tier and tiers: best_tier = tiers[0]
    buy_price = best_tier.get("price_hkd") if best_tier else None
    buy_star = best_tier.get("star") if best_tier else None
    buy_upside = best_tier.get("upside_pct") if best_tier else None

    # date
    date_str = ""
    if contract: date_str = contract.get("generated_at", "")[:19]
    if not date_str: date_str = _safe_get(cb, "meta", "date", default="")[:19]
    if not date_str: date_str = datetime.now().isoformat()

    gg_ok = gg_base is not None and 0.01 < gg_base < 500

    decision = _classify_decision(
        gg_discounted if gg_ok else None,
        II, upside_pct or buy_upside, vt_excluded, gg_ok
    )

    # report html path
    report_html = ""
    if stock_dir:
        code_clean = ts_code.replace(".", "_")
        # v13+: reports/ subdir; fallback to legacy v12 root
        cand = os.path.join(stock_dir, REPORTS_SUBDIR, f"{code_clean}_分析报告_{REPORT_VERSION}.html")
        if not os.path.exists(os.path.join(_OUTPUT_DIR, cand)):
            cand = os.path.join(stock_dir, f"{code_clean}_分析报告_v12.html")
        if os.path.exists(os.path.join(_OUTPUT_DIR, cand)):
            report_html = cand

    return {
        "ts_code": ts_code, "name": "", "market": market_flag,
        "analyzed_at": date_str, "price": price, "price_rmb": price_rmb, "mc_rmb": mc,
        "gg_base": gg_base, "gg_discounted": gg_discounted, "gg_fcfe": gg_fcfe,
        "ii": II, "aa_3y": aa_3y, "dps": dps,
        "p_base_hkd": p_base_hkd, "p_base_rmb": p_base_rmb, "p_fcfe_hkd": p_fcfe.get("price_hkd"),
        "upside_pct": upside_pct, "buy_price": buy_price, "buy_star": buy_star, "buy_upside": buy_upside,
        "pos_pct": pos_pct, "decision": decision,
        "parent_ratio": parent_ratio, "net_cash_pct_mc": net_cash_pct_mc,
        "extrap_overall": extrap_overall, "vt_excluded": 1 if vt_excluded else 0,
        "gg_ok": 1 if gg_ok else 0, "stock_dir": stock_dir, "report_html": report_html,
    }


# ── DB operations ───────────────────────────────────────────────────

def get_db(db_path: str = _DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = sqlite3.connect(db_path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    # Phase 1.4: migrate existing DBs that don't have live_price column
    try:
        db.execute("ALTER TABLE watchlist ADD COLUMN live_price REAL")
    except sqlite3.OperationalError:
        pass
    return db


def upsert_analysis(data: dict[str, Any], db_path: str = _DB_PATH) -> None:
    """写入/更新分析成果，同时追加 history。"""
    db = get_db(db_path)
    cols = [k for k in data if k not in ("name",)]
    placeholders = ", ".join("?" * len(cols))
    db.execute(
        f"INSERT OR REPLACE INTO analysis ({', '.join(cols)}) VALUES ({placeholders})",
        [data.get(k) for k in cols]
    )
    # history
    hist_cols = ["ts_code", "analyzed_at", "gg_base", "gg_discounted", "ii",
                 "p_base_hkd", "upside_pct", "decision", "pos_pct", "stock_dir"]
    db.execute(
        f"INSERT OR IGNORE INTO analysis_history ({', '.join(hist_cols)}) VALUES ({', '.join('?'*len(hist_cols))})",
        [data.get(k) for k in hist_cols]
    )
    db.commit()
    db.close()


def get_all_analyses(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """获取所有分析成果 + watchlist 联表。"""
    db = get_db(db_path)
    rows = db.execute("""
        SELECT a.*, w.invest_code, w.invest_status, w.current_hold, w.avg_cost AS inv_avg_cost,
               w.hold_limit_pct AS inv_hold_limit_pct, w.annual_div_per_share AS inv_dps,
               w.invest_logic AS inv_logic, w.my_valuation AS inv_valuation,
               w.name AS wl_name
        FROM analysis a
        LEFT JOIN watchlist w ON a.ts_code = w.ts_code
        ORDER BY a.gg_discounted DESC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_rerun_suggestions(db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    """Phase 2.2: 返回建议重分析的股票列表。按优先级排序。"""
    db = get_db(db_path)
    suggestions = []
    now = datetime.now().isoformat()

    # 1. 数据异常的（gg_ok=0）
    for r in db.execute("""
        SELECT a.ts_code, w.name, '数据异常' AS reason, 1 AS priority
        FROM analysis a LEFT JOIN watchlist w ON a.ts_code = w.ts_code
        WHERE a.gg_ok = 0
    """).fetchall():
        suggestions.append(dict(r))

    # 2. 超90天未更新的
    for r in db.execute("""
        SELECT a.ts_code, w.name, '超90天未更新' AS reason, 2 AS priority
        FROM analysis a LEFT JOIN watchlist w ON a.ts_code = w.ts_code
        WHERE a.gg_ok = 1 AND a.analyzed_at < datetime('now', '-90 days')
    """).fetchall():
        suggestions.append(dict(r))

    # 3. 超30天且持有中
    for r in db.execute("""
        SELECT a.ts_code, w.name, '超30天+持有中' AS reason, 3 AS priority
        FROM analysis a LEFT JOIN watchlist w ON a.ts_code = w.ts_code
        WHERE a.gg_ok = 1 AND a.analyzed_at < datetime('now', '-30 days')
        AND w.current_hold > 0
    """).fetchall():
        suggestions.append(dict(r))

    # 4. 持仓未分析
    for r in db.execute("""
        SELECT w.ts_code, w.name, '持仓未分析' AS reason, 4 AS priority
        FROM watchlist w
        WHERE w.current_hold > 0 AND w.ts_code NOT IN (SELECT ts_code FROM analysis)
        ORDER BY w.current_hold DESC
    """).fetchall():
        suggestions.append(dict(r))

    db.close()
    return sorted(suggestions, key=lambda s: (s["priority"], s.get("name", "")))


def get_analysis_history(ts_code: str, db_path: str = _DB_PATH) -> list[dict[str, Any]]:
    db = get_db(db_path)
    rows = db.execute(
        "SELECT * FROM analysis_history WHERE ts_code=? ORDER BY analyzed_at DESC", (ts_code,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def sync_watchlist(invest_path: str = "", db_path: str = _DB_PATH, backup_path: str = "") -> int:
    """从 invest app 实时数据同步 watchlist。

    优先读取 backup_path（investor.db 备份），其次自动查找 invest_path 下最新备份，
    最后回退到 stocks_import.json。
    """
    db = get_db(db_path)
    count = 0

    # 1. 尝试读取 invest DB 备份（优先，有完整实时数据）
    invest_db = _find_invest_db(invest_path, backup_path)
    if invest_db:
        count = _sync_from_invest_db(db, invest_db)
        if count > 0:
            db.commit()
            db.close()
            return count

    # 2. fallback: stocks_import.json
    path = invest_path or _DEFAULT_INVEST_PATH
    imp = _load_json(os.path.join(path, "stocks_import.json"))
    if imp:
        for s in imp.get("stocks", []):
            ts_code = _normalize_invest_code(s.get("code", ""))
            if not ts_code or "." not in ts_code: continue
            db.execute("""
                INSERT OR REPLACE INTO watchlist (ts_code, invest_code, name, market,
                    in_invest, invest_status, current_hold, avg_cost, hold_limit_pct,
                    annual_div_per_share, invest_logic, my_valuation, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (ts_code, s.get("code"), s.get("name"), s.get("market"),
                  s.get("status", "WATCHING"), s.get("currentHold", 0),
                  s.get("avgCost", 0), s.get("holdLimitPct", 0),
                  s.get("annualDivPerShare", 0), s.get("investLogic", ""),
                  s.get("myValuation", 0)))
            count += 1

    # 3. stocks.csv 补充
    csv_path = os.path.join(path, "stocks.csv")
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "," not in line: continue
                parts = line.split(",", 1)
                code = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else ""
                ts_code = _normalize_invest_code(code)
                if not ts_code or "." not in ts_code: continue
                existing = db.execute("SELECT 1 FROM watchlist WHERE ts_code=?", (ts_code,)).fetchone()
                if not existing:
                    db.execute(
                        "INSERT OR IGNORE INTO watchlist (ts_code, invest_code, name, market, in_invest) VALUES (?, ?, ?, ?, 0)",
                        (ts_code, code, name, "?"))
                    count += 1

    # 回填 name
    db.execute("UPDATE watchlist SET name = (SELECT a.name FROM analysis a WHERE a.ts_code = watchlist.ts_code) WHERE (name IS NULL OR name = '')")
    db.commit()
    db.close()
    return count


def _find_invest_db(invest_path: str = "", backup_path: str = "") -> str | None:
    """查找 invest DB：优先指定路径，其次 backups/ 下最新 zip，最后 investor.db。"""
    import glob as _glob
    # 指定路径
    if backup_path and os.path.exists(backup_path):
        if backup_path.endswith(".zip"):
            return _extract_invest_db(backup_path)
        return backup_path
    # 在 invest_path 下查找
    base = invest_path or _DEFAULT_INVEST_PATH
    # 最新备份 zip
    backups_dir = os.path.join(base, "backups")
    if os.path.isdir(backups_dir):
        zips = sorted(_glob.glob(os.path.join(backups_dir, "*.zip")), reverse=True)
        for z in zips:
            db_path = _extract_invest_db(z)
            if db_path:
                return db_path
    # 直接 investor.db
    direct = os.path.join(base, "investor.db")
    if os.path.exists(direct):
        return direct
    return None


def _extract_invest_db(zip_path: str) -> str | None:
    """从备份 zip 中提取 investor.db 到临时位置。"""
    import tempfile, zipfile
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            if 'investor.db' in zf.namelist():
                tmpdir = tempfile.gettempdir()
                zf.extract('investor.db', os.path.join(tmpdir, 'invest_backup_extract'))
                return os.path.join(tmpdir, 'invest_backup_extract', 'investor.db')
    except Exception:
        pass
    return None


def _sync_from_invest_db(db: sqlite3.Connection, invest_db_path: str) -> int:
    """从 invest app 的 SQLite DB 同步持仓数据。"""
    if not os.path.exists(invest_db_path):
        return 0
    idb = sqlite3.connect(invest_db_path, timeout=5)
    idb.row_factory = sqlite3.Row
    count = 0

    rows = idb.execute("SELECT * FROM stock").fetchall()
    for s in rows:
        code = s["code"]
        ts_code = _normalize_invest_code(code)
        if not ts_code or "." not in ts_code:
            continue

        market = "?"
        if code.startswith("hk"): market = "H"
        elif code.startswith("sz"): market = "A"
        elif code.startswith("sh"): market = "A"
        elif code.startswith("69") and "DE" in code: market = "DE"

        db.execute("""
            INSERT OR REPLACE INTO watchlist (
                ts_code, invest_code, name, market, in_invest,
                invest_status, current_hold, avg_cost, hold_limit_pct,
                annual_div_per_share, invest_logic, my_valuation, live_price, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            ts_code, code, s["name"], market,
            s["status"], s["currentHold"], s["avgCost"],
            s["holdLimitPct"], s["annualDivPerShare"],
            s["investLogic"] or "", s["myValuation"], s["currentPrice"]
        ))
        count += 1

    idb.close()
    return count


def sync_holdings(invest_path: str = "", db_path: str = _DB_PATH) -> int:
    """同步 invest 持仓快照到 holding_sync。"""
    path = invest_path or _DEFAULT_INVEST_PATH
    db = get_db(db_path)
    imp = _load_json(os.path.join(path, "stocks_import.json"))
    if not imp:
        db.close(); return 0

    now = datetime.now().isoformat()
    count = 0
    for s in imp.get("stocks", []):
        ts_code = _normalize_invest_code(s.get("code", ""))
        if not ts_code or "." not in ts_code: continue
        db.execute("""
            INSERT OR IGNORE INTO holding_sync (ts_code, sync_at, current_hold, avg_cost, status)
            VALUES (?, ?, ?, ?, ?)
        """, (ts_code, now, s.get("currentHold", 0), s.get("avgCost", 0), s.get("status", "")))
        count += 1

    db.commit()
    db.close()
    return count


# ── migration ───────────────────────────────────────────────────────

def migrate_from_files(db_path: str = _DB_PATH) -> int:
    """一次性：扫描所有 output/compute_bundle.json → DB。返回导入数。"""
    db = get_db(db_path)
    count = 0
    if not os.path.isdir(_OUTPUT_DIR): return 0

    for entry in sorted(os.listdir(_OUTPUT_DIR)):
        stock_dir = os.path.join(_OUTPUT_DIR, entry)
        if not os.path.isdir(stock_dir) or entry.startswith("_"): continue

        cb_path = os.path.join(stock_dir, "compute_bundle.json")
        if not os.path.exists(cb_path): continue

        contract_path = os.path.join(stock_dir, "analysis_contract.json")
        data = extract_from_bundle(cb_path, contract_path, entry)
        if not data or not data.get("ts_code"): continue

        # 从目录名取 name
        parts = entry.split("_", 1)
        data["name"] = parts[1] if len(parts) > 1 else data["ts_code"]

        cols = [k for k in data]
        db.execute(
            f"INSERT OR REPLACE INTO analysis ({', '.join(cols)}) VALUES ({', '.join('?'*len(cols))})",
            [data.get(k) for k in cols]
        )
        # 同时写入 history
        hist_cols = ["ts_code", "analyzed_at", "gg_base", "gg_discounted", "ii",
                     "p_base_hkd", "upside_pct", "decision", "pos_pct", "stock_dir"]
        db.execute(
            f"INSERT OR IGNORE INTO analysis_history ({', '.join(hist_cols)}) VALUES ({', '.join('?'*len(hist_cols))})",
            [data.get(k) for k in hist_cols]
        )
        count += 1

    db.commit()
    db.close()
    return count


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="portfolio_db.py — 分析成果数据库")
    ap.add_argument("--migrate", action="store_true", help="首次迁移：output/ → DB")
    ap.add_argument("--sync-invest", action="store_true", help="同步 invest 数据")
    ap.add_argument("--upsert", type=str, help="手动更新单只股票（ts_code）")
    ap.add_argument("--invest-path", default=_DEFAULT_INVEST_PATH)
    args = ap.parse_args()

    if args.migrate:
        n = migrate_from_files()
        print(f"✅ 迁移完成: {n} 条分析记录")
        w = sync_watchlist(args.invest_path)
        print(f"✅ watchlist: {w} 条")
        h = sync_holdings(args.invest_path)
        print(f"✅ holding_sync: {h} 条")
    elif args.sync_invest:
        w = sync_watchlist(args.invest_path)
        h = sync_holdings(args.invest_path)
        print(f"✅ watchlist 同步: {w} | holding_sync: {h}")
    elif args.upsert:
        # 从 output 目录找对应 stock
        ts = args.upsert
        code_base = ts.split(".")[0]
        found = False
        if os.path.isdir(_OUTPUT_DIR):
            for entry in os.listdir(_OUTPUT_DIR):
                if entry.startswith(code_base):
                    stock_dir = os.path.join(_OUTPUT_DIR, entry)
                    cb_path = os.path.join(stock_dir, "compute_bundle.json")
                    if os.path.exists(cb_path):
                        contract_path = os.path.join(stock_dir, "analysis_contract.json")
                        data = extract_from_bundle(cb_path, contract_path, entry)
                        parts = entry.split("_", 1)
                        data["name"] = parts[1] if len(parts) > 1 else ts
                        upsert_analysis(data)
                        print(f"✅ {ts} updated: GG={data['gg_discounted']}% decision={data['decision']}")
                        found = True
                        break  # V12.19 fix: only break when actually found
        if not found:
            print(f"❌ 未找到 {ts} 的 compute_bundle.json")
    else:
        # 显示统计
        db = get_db()
        ac = db.execute("SELECT COUNT(*) FROM analysis").fetchone()[0]
        wc = db.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        hc = db.execute("SELECT COUNT(*) FROM analysis_history").fetchone()[0]
        print(f"analysis: {ac} | watchlist: {wc} | history: {hc}")
        print()
        for r in db.execute("SELECT ts_code, name, decision, gg_discounted, analyzed_at FROM analysis ORDER BY gg_discounted DESC").fetchall():
            print(f"  {r['ts_code']:12s} {r['name'] or '?':8s} {r['decision']:12s} GG={r['gg_discounted']}%  {r['analyzed_at'][:10]}")
        db.close()


if __name__ == "__main__":
    main()
