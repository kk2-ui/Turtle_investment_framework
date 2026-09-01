"""niangao.sync — 同步层：从 invest app 备份同步持仓数据到 watchlist"""

from __future__ import annotations

import glob as _glob
import os
import sqlite3
import tempfile
import zipfile
from typing import Any

from niangao.db import _load_json, _normalize_invest_code, get_db, _DB_PATH

_DEFAULT_INVEST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "invest")


def sync_watchlist(invest_path: str = "", backup_path: str = "", db_path: str = _DB_PATH) -> int:
    """从 invest app 实时数据同步 watchlist。优先 backup_path，其次自动查找最新备份。"""
    db = get_db(db_path)
    invest_db = _find_invest_db(invest_path, backup_path)
    if invest_db:
        count = _sync_from_invest_db(db, invest_db)
        if count > 0: db.commit(); db.close(); return count

    # fallback: stocks_import.json
    path = invest_path or _DEFAULT_INVEST_PATH
    imp = _load_json(os.path.join(path, "stocks_import.json"))
    if imp:
        count = 0
        for s in imp.get("stocks", []):
            ts = _normalize_invest_code(s.get("code", ""))
            if not ts or "." not in ts: continue
            db.execute("""INSERT OR REPLACE INTO watchlist (ts_code, invest_code, name, market, in_invest, invest_status, current_hold, avg_cost, hold_limit_pct, annual_div_per_share, invest_logic, my_valuation, updated_at) VALUES (?,?,?,?,1,?,?,?,?,?,?,?,datetime('now'))""",
                       (ts, s.get("code"), s.get("name"), s.get("market"), s.get("status","WATCHING"), s.get("currentHold",0), s.get("avgCost",0), s.get("holdLimitPct",0), s.get("annualDivPerShare",0), s.get("investLogic",""), s.get("myValuation",0)))
            count += 1
        db.commit(); db.close(); return count

    db.close(); return 0


def sync_holdings(invest_path: str = "", db_path: str = _DB_PATH) -> int:
    path = invest_path or _DEFAULT_INVEST_PATH
    db = get_db(db_path)
    imp = _load_json(os.path.join(path, "stocks_import.json"))
    if not imp: db.close(); return 0
    now = __import__('datetime').datetime.now().isoformat()
    count = 0
    for s in imp.get("stocks", []):
        ts = _normalize_invest_code(s.get("code", ""))
        if not ts or "." not in ts: continue
        db.execute("INSERT OR IGNORE INTO holding_sync (ts_code, sync_at, current_hold, avg_cost, status) VALUES (?,?,?,?,?)",
                   (ts, now, s.get("currentHold",0), s.get("avgCost",0), s.get("status","")))
        count += 1
    db.commit(); db.close()
    return count


def _find_invest_db(invest_path: str = "", backup_path: str = "") -> str | None:
    # Priority 0: Try ADB pull from connected phone (most up-to-date)
    adb_db = _try_adb_pull()
    if adb_db:
        return adb_db

    if backup_path and os.path.exists(backup_path):
        return _extract_invest_db(backup_path) if backup_path.endswith(".zip") else backup_path
    base = invest_path or _DEFAULT_INVEST_PATH
    # Search: /tmp/ for extracted DB or zip, then base/backups/, then base/investor.db
    for d in ["/tmp/invest_extract", "/tmp"]:
        if os.path.isfile(os.path.join(d, "investor.db")):
            return os.path.join(d, "investor.db")
    for search_dir in ["/tmp", os.path.join(base, "backups")]:
        if os.path.isdir(search_dir):
            for z in sorted(_glob.glob(os.path.join(search_dir, "investor_backup_*.zip")), reverse=True):
                db = _extract_invest_db(z)
                if db: return db
    direct = os.path.join(base, "investor.db")
    return direct if os.path.exists(direct) else None


def _try_adb_pull() -> str | None:
    """Try to pull investor.db from a connected phone via ADB.

    Returns path to the pulled DB on success, None on any failure.
    Failures are silent — the caller falls back to file-based search.
    """
    try:
        import shutil
        import subprocess

        adb = os.environ.get("ADB") or shutil.which("adb")
        if not adb:
            from pathlib import Path
            default_adb = str(Path("~/Library/Android/sdk/platform-tools/adb").expanduser())
            if Path(default_adb).exists():
                adb = default_adb
        if not adb:
            return None

        # Pull directly from the running app (adb devices check is too fragile, just try)
        tmp_db = os.path.join(tempfile.gettempdir(), "investor.db")
        result = subprocess.run(
            [adb, "exec-out", "run-as", "com.niangao.investor", "cat", "databases/investor.db"],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0 or len(result.stdout) < 1024:
            return None

        with open(tmp_db, "wb") as f:
            f.write(result.stdout)
        return tmp_db
    except Exception:
        return None


def _extract_invest_db(zip_path: str) -> str | None:
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
    if not os.path.exists(invest_db_path): return 0
    idb = sqlite3.connect(invest_db_path, timeout=5)
    idb.row_factory = sqlite3.Row
    count = 0
    for s_raw in idb.execute("SELECT * FROM stock").fetchall():
        s = dict(s_raw)
        code = s["code"]; ts = _normalize_invest_code(code)
        if not ts or "." not in ts: continue
        market = "H" if code.startswith("hk") else "A" if code.startswith("sz") or code.startswith("sh") else "DE" if "DE" in code.upper() else "?"
        db.execute("""INSERT OR REPLACE INTO watchlist (ts_code, invest_code, name, market, in_invest, invest_status, current_hold, avg_cost, hold_limit_pct, annual_div_per_share, invest_logic, my_valuation, live_price, sector, stock_type, pe, pb, debt_ratio, fcf_yield, mth_enabled, mth_cycle, lock_reserve, cumulative_div, dividend_tax_rate, account_id, updated_at) VALUES (?,?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                   (ts, code, s["name"], market, s["status"], s["currentHold"], s["avgCost"], s["holdLimitPct"], s["annualDivPerShare"], s["investLogic"] or "", s["myValuation"], s["currentPrice"], s["sector"], s["stockType"], s.get("pe"), s.get("pb"), s.get("debtRatio"), s.get("fcfYield"), s.get("mthEnabled",0), s.get("mthCurrentCycle",1), s.get("lockReserveEnabled",1), s.get("cumulativeDivPerShare",0), s.get("dividendTaxRate",0), s.get("accountId",1)))
        count += 1
    idb.close()
    return count



def _compute_position_pnl(pdb, idb):
    """从 invest DB 和 trade_record 计算持仓盈亏，写入 position_pnl。"""
    from niangao.db import _normalize_invest_code, _turtle_to_invest_code
    import sqlite3 as _sql3
    # Get all current holdings from invest DB
    stocks = [dict(r) for r in idb.execute("SELECT * FROM stock WHERE currentHold > 0").fetchall()]
    # Get trade_record dividend data per stock
    import sqlite3 as _sql3
    div_data = {}
    for r in pdb.execute("SELECT stock_code, SUM(amount) as div_amt FROM trade_record WHERE trade_type='DIVIDEND' GROUP BY stock_code").fetchall():
        div_data[r[0]] = r[1] or 0

    for s in stocks:
        code = s["code"]  # invest format like sz000651
        ts = _normalize_invest_code(code)
        hold = s["currentHold"]
        cost = s["avgCost"]
        price = s["currentPrice"]
        mv = hold * price
        cb = hold * cost
        unrealized = mv - cb if cb > 0 else 0
        div_est = s["annualDivPerShare"] * hold if s.get("annualDivPerShare") else 0
        total_ret = unrealized + div_est
        pct = (total_ret / cb * 100) if cb > 0 else 0
        pdb.execute("""INSERT OR REPLACE INTO position_pnl (ts_code, invest_code, name, current_hold, avg_cost, live_price, market_value, unrealized_pnl, dividend_est, total_return, total_return_pct, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (ts, code, s["name"], hold, cost, price, mv, unrealized, div_est, total_ret, pct))
    pdb.commit()
    return len(stocks)


def _compute_realized_pnl(pdb, idb):
    """只计算完全清仓的股票（currentHold=0 且有 SELL 记录）。"""
    # Get stocks with currentHold=0 that have SELL trades
    sold_codes = {r[0] for r in pdb.execute(
        "SELECT DISTINCT stock_code FROM trade_record WHERE trade_type='SELL'"
    ).fetchall()}
    # Get currently held codes
    held_codes = {r["code"] for r in idb.execute(
        "SELECT code FROM stock WHERE currentHold > 0"
    ).fetchall()}
    # Only fully liquidated
    liquidated = sold_codes - held_codes

    count = 0
    for code in liquidated:
        sell = pdb.execute(
            "SELECT SUM(amount) FROM trade_record WHERE trade_type='SELL' AND stock_code=?", (code,)
        ).fetchone()
        buy = pdb.execute(
            "SELECT SUM(amount) FROM trade_record WHERE trade_type='BUY' AND stock_code=?", (code,)
        ).fetchone()
        sell_amt = sell[0] or 0; buy_amt = buy[0] or 0
        pnl = sell_amt - buy_amt
        name = pdb.execute("SELECT stock_name FROM trade_record WHERE stock_code=? LIMIT 1", (code,)).fetchone()
        pdb.execute("""INSERT OR REPLACE INTO realized_pnl (stock_code, stock_name, total_buy_amt, total_sell_amt, realized_pnl, updated_at)
            VALUES (?,?,?,?,?,datetime('now'))""",
            (code, name[0] if name else "", buy_amt, sell_amt, pnl))
        count += 1
    pdb.commit()
    return count

def sync_all_from_invest() -> dict[str, int]:
    """从 invest DB 全量同步到 portfolio.db。
    返回各表同步行数：{snapshots, annual, alerts, trades, cash_flows}"""
    invest_db_path = _find_invest_db()
    if not invest_db_path or not os.path.exists(invest_db_path):
        return {"error": "invest DB not found"}

    # Ensure portfolio.db schema is up to date
    get_db(_DB_PATH)
    idb = sqlite3.connect(invest_db_path, timeout=5)
    idb.row_factory = sqlite3.Row
    pdb = sqlite3.connect(_DB_PATH)
    counts: dict[str, int] = {}

    try:
        # 1. Wealth snapshots (incremental)
        existing = {r[0] for r in pdb.execute("SELECT snapshot_at FROM wealth_snapshot").fetchall()}
        rows = idb.execute("SELECT * FROM portfolio_snapshot ORDER BY timestamp").fetchall()
        new_count = 0
        for r in rows:
            ts = r["timestamp"]
            if ts not in existing:
                pdb.execute("INSERT OR IGNORE INTO wealth_snapshot (snapshot_at, total_wealth_cny, stock_value_cny, cash_value_cny, event_type) VALUES (?,?,?,?,?)",
                            (ts, r["totalWealthCny"], r["stockValueCny"], r["cashValueCny"], r["eventType"]))
                new_count += 1
        pdb.commit()
        counts["snapshots"] = new_count

        # 2. Annual summary (overwrite)
        rows = idb.execute("SELECT * FROM portfolio_year_snapshot").fetchall()
        for r in rows:
            d = dict(r)
            pdb.execute("INSERT OR REPLACE INTO annual_summary (year, market_value_cny, cumulative_pnl_cny, dividend_cny, pnl_offset_cny) VALUES (?,?,?,?,?)",
                        (d["year"], d["marketValueCny"], d.get("manualCumulativePnlCny"), d.get("manualDividendCny"), d.get("manualCumulativePnlOffsetCny")))
        pdb.commit()
        counts["annual"] = len(rows)

        # 3. Alerts (full replace: delete old, insert new)
        pdb.execute("DELETE FROM alert_snapshot")
        rows = idb.execute("SELECT a.*, s.code, s.name, s.currentPrice as phonePrice FROM alert a JOIN stock s ON a.stockId=s.id WHERE a.isActive=1").fetchall()
        for r in rows:
            pdb.execute("INSERT INTO alert_snapshot (stock_code, stock_name, alert_type, target_price, is_active, is_triggered, current_price) VALUES (?,?,?,?,?,?,?)",
                        (r["code"], r["name"], r["alertType"], r["targetPrice"], r["isActive"], r["isTriggered"], r["phonePrice"]))
        pdb.commit()
        counts["alerts"] = len(rows)

        # 4. Trades (incremental)
        existing_trade_ids = {r[0] for r in pdb.execute("SELECT id FROM trade_record").fetchall()}
        rows = idb.execute("SELECT t.*, s.code, s.name FROM 'transaction' t JOIN stock s ON t.stockId=s.id ORDER BY t.id").fetchall()
        new_trades = 0
        for r in rows:
            if r["id"] not in existing_trade_ids:
                pdb.execute("INSERT OR IGNORE INTO trade_record (id, stock_code, stock_name, trade_type, price, shares, amount, trade_at, dividend_year, commission) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (r["id"], r["code"], r["name"], r["type"], r["price"], r["shares"], r["amount"], r["timestamp"], r["dividendYear"], r["commissionCNY"]))
                new_trades += 1
        pdb.commit()
        counts["trades"] = new_trades

        # 5. Cash flows (incremental)
        existing_cf_ids = {r[0] for r in pdb.execute("SELECT id FROM cash_flow").fetchall()}
        rows = idb.execute("SELECT * FROM external_cash_flow ORDER BY id").fetchall()
        new_cf = 0
        for r in rows:
            if r["id"] not in existing_cf_ids:
                pdb.execute("INSERT OR IGNORE INTO cash_flow (id, account_id, currency, delta_amount, delta_cny, note, flow_at) VALUES (?,?,?,?,?,?,?)",
                            (r["id"], r["accountId"], r["currency"], r["deltaAmount"], r["deltaCny"], r["note"], r["timestamp"]))
                new_cf += 1
        pdb.commit()
        counts["cash_flows"] = new_cf

        # 6. Account
        pdb.execute("DELETE FROM account")
        for r in idb.execute("SELECT * FROM account").fetchall():
            r = dict(r)
            pdb.execute("INSERT INTO account VALUES (?,?,?,?,?,?,datetime('now'))",
                (r["id"], r["name"], r["ownershipPct"], r.get("cumulativePnlBaselineYear"),
                 r.get("cumulativePnlBaselineRaw"), r.get("cumulativePnlBaselineTarget")))
        pdb.commit()
        counts["accounts"] = pdb.execute("SELECT COUNT(*) FROM account").fetchone()[0]

        # 7. Cash
        pdb.execute("DELETE FROM cash")
        for r in idb.execute("SELECT * FROM cash").fetchall():
            r = dict(r)
            pdb.execute("INSERT INTO cash VALUES (?,?,?,?,datetime('now'))",
                (r["currency"], r["accountId"], r["amount"], r["lastUpdated"]))
        pdb.commit()
        counts["cash"] = pdb.execute("SELECT COUNT(*) FROM cash").fetchone()[0]

        # 8. Price history (incremental by stock_id + trade_date)
        existing_ph = {(r[0], r[1]) for r in pdb.execute("SELECT stock_id, trade_date FROM price_history").fetchall()}
        new_ph = 0
        for r in idb.execute("SELECT * FROM price_history").fetchall():
            r = dict(r)
            if (r["stockId"], r["tradeDate"]) not in existing_ph:
                pdb.execute("INSERT INTO price_history VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                    (r["stockId"], r["tradeDate"], r["closePrice"], r["highPrice"], r["lowPrice"],
                     r.get("openPrice",0), r.get("prevClosePrice",0), r.get("volume",0), r["updatedAt"]))
                new_ph += 1
        pdb.commit()
        counts["price_history"] = new_ph

        # 9. Fundamentals history
        pdb.execute("DELETE FROM fundamentals_history")
        for r in idb.execute("SELECT * FROM fundamentals_history").fetchall():
            r = dict(r)
            pdb.execute("INSERT INTO fundamentals_history (stock_id, year, pe, pb, debt_ratio, ev, ebitda, fcf_yield, pe_source, pb_source, debt_ratio_source, ev_source, fcf_yield_source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["stockId"], r["year"], r.get("pe"), r.get("pb"), r.get("debtRatio"),
                 r.get("ev"), r.get("ebitda"), r.get("fcfYield"),
                 r.get("peSource"), r.get("pbSource"), r.get("debtRatioSource"),
                 r.get("evSource"), r.get("fcfYieldSource")))
        pdb.commit()
        counts["fundamentals_history"] = pdb.execute("SELECT COUNT(*) FROM fundamentals_history").fetchone()[0]

        # 10. Month end price
        pdb.execute("DELETE FROM month_end_price")
        for r in idb.execute("SELECT * FROM month_end_price").fetchall():
            r = dict(r)
            pdb.execute("INSERT INTO month_end_price VALUES (?,?,?,?,?,datetime('now'))",
                (r["stockId"], r["yearMonth"], r["tradeDate"], r["closePrice"], r["updatedAt"]))
        pdb.commit()
        counts["month_end_price"] = pdb.execute("SELECT COUNT(*) FROM month_end_price").fetchone()[0]

        # 11. Month end exchange rate
        pdb.execute("DELETE FROM month_end_exchange_rate")
        for r in idb.execute("SELECT * FROM month_end_exchange_rate").fetchall():
            r = dict(r)
            pdb.execute("INSERT INTO month_end_exchange_rate VALUES (?,?,?,?,?,datetime('now'))",
                (r["yearMonth"], r["hkdRate"], r["usdRate"], r["eurRate"], r["updatedAt"]))
        pdb.commit()
        counts["month_end_exchange_rate"] = pdb.execute("SELECT COUNT(*) FROM month_end_exchange_rate").fetchone()[0]

        # 12. Alert settlement
        pdb.execute("DELETE FROM alert_settlement")
        for r in idb.execute("SELECT * FROM alert_settlement").fetchall():
            r = dict(r)
            pdb.execute("INSERT INTO alert_settlement VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))",
                (r["id"], r["alertId"], r["stockId"], r["transactionId"],
                 r["alertType"], r.get("targetPriceSnapshot"), r.get("settledPrice"),
                 r.get("settledShares"), r.get("settledAmountCny"), r.get("source")))
        pdb.commit()
        counts["alert_settlement"] = pdb.execute("SELECT COUNT(*) FROM alert_settlement").fetchone()[0]

        # 13. Account portfolio snapshot (incremental)
        existing_aps = {(r[0], r[1]) for r in pdb.execute("SELECT snapshot_at, account_id FROM account_portfolio_snapshot").fetchall()}
        new_aps = 0
        for r in idb.execute("SELECT * FROM account_portfolio_snapshot").fetchall():
            r = dict(r)
            if (r["timestamp"], r["accountId"]) not in existing_aps:
                pdb.execute("INSERT INTO account_portfolio_snapshot VALUES (?,?,?,?,?,?,datetime('now'))",
                    (r["timestamp"], r["accountId"], r["totalWealthCny"], r["stockValueCny"], r["cashValueCny"], r["eventType"]))
                new_aps += 1
        pdb.commit()
        counts["account_snapshots"] = new_aps

        # 14. Compute position PnL
        counts["position_pnl"] = _compute_position_pnl(pdb, idb)
        # 7. Compute realized PnL (fully closed only)
        counts["realized_pnl"] = _compute_realized_pnl(pdb, idb)

    finally:
        idb.close()
        pdb.close()
    return counts
