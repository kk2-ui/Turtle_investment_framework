"""niangao.assets — 资产层：从 invest 备份读取资产总览、行业分类、账户分布"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any

from niangao.sync import _find_invest_db
from niangao.db import _normalize_invest_code


def load_asset_overview(invest_path: str = "", backup_path: str = "") -> dict[str, Any]:
    """从 invest 备份读取完整资产数据。"""
    db_path = _find_invest_db(invest_path, backup_path)
    if not db_path or not os.path.exists(db_path):
        return {"error": "invest DB not found"}

    idb = sqlite3.connect(db_path, timeout=5)
    idb.row_factory = sqlite3.Row

    # ── Accounts ──
    accounts = {}
    for r in idb.execute("SELECT * FROM account").fetchall():
        accounts[r["id"]] = dict(r)

    # ── Cash ──
    cash = {"CNY": 0, "HKD": 0, "USD": 0}
    for r in idb.execute("SELECT * FROM cash").fetchall():
        d = dict(r)
        cash[d["currency"]] = cash.get(d["currency"], 0) + d["amount"]

    # Ownership-weighted cash (matches invest App snapshot calculation)
    cash_weighted = {"CNY": 0, "HKD": 0, "USD": 0}
    for r in idb.execute("SELECT * FROM cash").fetchall():
        d = dict(r)
        acct = accounts.get(d["accountId"], {})
        ownership = acct.get("ownershipPct", 1.0)
        cash_weighted[d["currency"]] = cash_weighted.get(d["currency"], 0) + d["amount"] * ownership

    # ── Portfolio Snapshots (wealth history) ──
    snapshots = [dict(r) for r in idb.execute(
        "SELECT * FROM portfolio_snapshot ORDER BY timestamp DESC LIMIT 90").fetchall()]
    snapshots.reverse()
    latest_snapshot = snapshots[-1] if snapshots else None

    # ── External cash flows (Phase 1.3) ──
    cash_flows = [dict(r) for r in idb.execute(
        "SELECT * FROM external_cash_flow ORDER BY timestamp DESC LIMIT 10").fetchall()]

    # ── Recent transactions (Phase 2.2, pre-load) ──
    transactions = [dict(r) for r in idb.execute("""
        SELECT t.*, s.name, s.code FROM 'transaction' t
        JOIN stock s ON t.stockId = s.id
        ORDER BY t.timestamp DESC LIMIT 10
    """).fetchall()]

    # ── Pending alerts (Phase 2.1, pre-load) ──
    alerts = [dict(r) for r in idb.execute("""
        SELECT a.*, s.name, s.code, s.currentPrice
        FROM alert a JOIN stock s ON a.stockId = s.id
        WHERE a.isActive = 1 AND a.isTriggered = 0
        ORDER BY a.alertType, a.targetPrice DESC
    """).fetchall()]

    # Also fetch triggered (already hit) alerts
    triggered_alerts = [dict(r) for r in idb.execute("""
        SELECT a.*, s.name, s.code, s.currentPrice
        FROM alert a JOIN stock s ON a.stockId = s.id
        WHERE a.isActive = 1 AND a.isTriggered = 1
        ORDER BY a.alertType, a.targetPrice DESC
    """).fetchall()]

    # ── Stock breakdown ──
    stocks = [dict(r) for r in idb.execute("SELECT * FROM stock").fetchall()]
    total_stock_value_raw = sum(s["currentHold"] * s["currentPrice"] for s in stocks)
    # Use snapshot's CNY-converted stock value when available (avoids mixing currencies)
    total_stock_value = (latest_snapshot["stockValueCny"] if latest_snapshot and latest_snapshot.get("stockValueCny")
                        else total_stock_value_raw)
    holding_stocks = [s for s in stocks if s["currentHold"] > 0]
    watching_stocks = [s for s in stocks if s["currentHold"] == 0 and s["status"] == "WATCHING"]

    # Market breakdown
    by_market: dict[str, dict] = {}
    for s in stocks:
        m = s["market"]
        if m not in by_market: by_market[m] = {"value": 0, "count": 0}
        by_market[m]["value"] += s["currentHold"] * s["currentPrice"]
        by_market[m]["count"] += 1

    # Stock type breakdown
    by_type: dict[str, dict] = {}
    type_stocks: dict[str, list[dict]] = {}
    for s in stocks:
        t = s["stockType"]
        if t not in by_type: by_type[t] = {"value": 0, "count": 0}
        by_type[t]["value"] += s["currentHold"] * s["currentPrice"]
        by_type[t]["count"] += 1
        if t not in type_stocks:
            type_stocks[t] = []
        type_stocks[t].append({
            "code": s["code"], "name": s["name"],
            "value": s["currentHold"] * s["currentPrice"],
            "hold": s["currentHold"], "price": s["currentPrice"]
        })
    for t in type_stocks:
        type_stocks[t].sort(key=lambda x: x["value"], reverse=True)

    # Sector breakdown
    by_sector: dict[str, float] = {}
    sector_stocks: dict[str, list[dict]] = {}  # sector → individual stocks
    for s in holding_stocks:
        sec = s["sector"] or "未分类"
        by_sector[sec] = by_sector.get(sec, 0) + s["currentHold"] * s["currentPrice"]
        if sec not in sector_stocks:
            sector_stocks[sec] = []
        sector_stocks[sec].append({
            "code": s["code"], "name": s["name"],
            "value": s["currentHold"] * s["currentPrice"],
            "hold": s["currentHold"], "price": s["currentPrice"]
        })
    # Sort stocks within each sector by value desc
    for sec in sector_stocks:
        sector_stocks[sec].sort(key=lambda x: x["value"], reverse=True)
    top_sectors = sorted(by_sector.items(), key=lambda x: x[1], reverse=True)[:8]

    # Account breakdown
    by_account: dict[int, dict] = {}
    for s in stocks:
        aid = s["accountId"]
        if aid not in by_account: by_account[aid] = {"value": 0, "count": 0}
        by_account[aid]["value"] += s["currentHold"] * s["currentPrice"]
        by_account[aid]["count"] += 1

    # Fundamentals summary
    with_pe = [s for s in holding_stocks if s.get("pe") and s["pe"] > 0]
    with_pb = [s for s in holding_stocks if s.get("pb") and s["pb"] > 0]
    with_div = [s for s in holding_stocks if s.get("annualDivPerShare") and s["annualDivPerShare"] > 0]

    # Dividend summary (Phase 2.3)
    total_div_received = sum(t["amount"] for t in transactions if t["type"] == "DIVIDEND")
    annual_div_expected = sum(s["currentHold"] * s["annualDivPerShare"] for s in holding_stocks)

    # Phase 3.1: Concentration risk
    holding_values = [(s, s["currentHold"] * s["currentPrice"]) for s in holding_stocks]
    holding_values.sort(key=lambda x: x[1], reverse=True)
    top5_value = sum(v for _, v in holding_values[:5])
    concentration_pct = top5_value / total_stock_value * 100 if total_stock_value > 0 else 0
    top_holdings_detail = [{"code": s["code"], "name": s["name"], "value": v,
                            "pct": v / total_stock_value * 100 if total_stock_value > 0 else 0}
                           for s, v in holding_values[:5]]

    # Phase 3.2: Price history sparklines for top holdings
    price_sparklines = {}
    for s, v in holding_values[:5]:
        code = s["code"]
        ph = idb.execute(
            "SELECT closePrice FROM price_history WHERE stockId=? ORDER BY tradeDate LIMIT 60",
            (s["id"],)
        ).fetchall()
        if len(ph) > 5:
            price_sparklines[code] = [r["closePrice"] for r in ph]

    # ── Returns / Performance ──
    # Try portfolio.db first (persisted), fall back to invest DB
    try:
        from niangao.db import _DB_PATH as local_db_path
        ldb = sqlite3.connect(local_db_path)
        ldb.row_factory = sqlite3.Row

        # Wealth snapshots from local DB
        local_snapshots = [dict(r) for r in ldb.execute(
            "SELECT * FROM wealth_snapshot ORDER BY snapshot_at ASC").fetchall()]

        # Annual summaries from local DB
        year_snapshots_list = [dict(r) for r in ldb.execute(
            "SELECT * FROM annual_summary ORDER BY year").fetchall()]

        # Dividends from local trade records
        total_div_received_cny = sum(
            r["amount"] for r in ldb.execute(
                "SELECT amount FROM trade_record WHERE trade_type='DIVIDEND' AND amount IS NOT NULL"
            ).fetchall()
        )

        # Cash inflow from local DB
        total_inflow = sum(
            r["delta_cny"] for r in ldb.execute(
                "SELECT delta_cny FROM cash_flow"
            ).fetchall()
        ) or sum(f["deltaCny"] for f in cash_flows)  # fallback

        ldb.close()

        use_local = len(local_snapshots) >= 2
        if use_local:
            all_snapshots = local_snapshots
        else:
            # Fallback: read from invest DB
            all_snapshots = [dict(r) for r in idb.execute(
                "SELECT * FROM portfolio_snapshot ORDER BY timestamp ASC").fetchall()]
            if not year_snapshots_list:
                year_snapshots_list = [dict(r) for r in idb.execute(
                    "SELECT * FROM portfolio_year_snapshot ORDER BY year").fetchall()]
    except Exception:
        # Fallback to invest DB
        all_snapshots = [dict(r) for r in idb.execute(
            "SELECT * FROM portfolio_snapshot ORDER BY timestamp ASC").fetchall()]
        year_snapshots_list = [dict(r) for r in idb.execute(
            "SELECT * FROM portfolio_year_snapshot ORDER BY year").fetchall()]
        total_div_received_cny = sum(
            t["amount"] for t in transactions
            if t["type"] == "DIVIDEND" and t.get("amount")
        )
        total_inflow = sum(f["deltaCny"] for f in cash_flows) if cash_flows else 0

    # Wealth metrics from snapshot history
    if all_snapshots and len(all_snapshots) >= 2:
        start = all_snapshots[0]
        end = all_snapshots[-1]
        # Handle both column naming conventions
        start_wealth = start.get("totalWealthCny") or start.get("total_wealth_cny", 0)
        latest_wealth = end.get("totalWealthCny") or end.get("total_wealth_cny", 0)
        # Subtract net cash inflow — deposits are not investment returns
        net_cash = total_inflow
        investment_return = latest_wealth - start_wealth - net_cash
        total_return_pct = (investment_return / (start_wealth + net_cash) * 100) if (start_wealth + net_cash) > 0 else 0
        # YTD: first snapshot of current year
        current_year = datetime.now().year
        ts_field = "timestamp" if "timestamp" in start else "snapshot_at"
        ytd_snapshots = [s for s in all_snapshots
                         if datetime.fromtimestamp(s[ts_field]/1000).year == current_year]
        ytd_start = ytd_snapshots[0].get("totalWealthCny") or ytd_snapshots[0].get("total_wealth_cny", 0) if ytd_snapshots else start_wealth
        # YTD should also exclude cash flows within this year
        ytd_cash_in = sum(
            f.get("deltaCny") or f.get("delta_cny", 0) for f in cash_flows
            if datetime.fromtimestamp((f.get("timestamp") or f.get("flow_at", 0))/1000).year == current_year
        ) if cash_flows and ytd_snapshots else 0
        ytd_invest_return = latest_wealth - ytd_start - ytd_cash_in
        ytd_pct = (ytd_invest_return / (ytd_start + ytd_cash_in) * 100) if (ytd_start + ytd_cash_in) > 0 else 0
        # Days tracked
        first_ts = start.get("timestamp") or start.get("snapshot_at", 0)
        last_ts = end.get("timestamp") or end.get("snapshot_at", 0)
        days_tracked = max(1, (last_ts - first_ts) / 1000 / 86400)
        years_tracked = days_tracked / 365.25
        annualized_pct = ((latest_wealth / start_wealth) ** (1 / years_tracked) - 1) * 100 if years_tracked > 0 and start_wealth > 0 else 0
    else:
        start_wealth = 0; latest_wealth = 0; total_return_pct = 0
        ytd_pct = 0; days_tracked = 0; annualized_pct = 0

    returns = {
        "current_wealth": latest_wealth,
        "start_wealth": start_wealth,
        "total_return": investment_return,
        "total_return_pct": total_return_pct,
        "ytd_return_pct": ytd_pct,
        "annualized_pct": annualized_pct,
        "total_dividends": total_div_received_cny,
        "total_inflow": total_inflow,
        "days_tracked": int(days_tracked),
        "years": [{
            "year": s["year"],
            "marketValueCny": s.get("marketValueCny") or s.get("market_value_cny", 0),
            "cumulativePnlCny": s.get("manualCumulativePnlCny") or s.get("cumulative_pnl_cny"),
            "dividendCny": s.get("manualDividendCny") or s.get("dividend_cny"),
            "pnlOffsetCny": s.get("manualCumulativePnlOffsetCny") or s.get("pnl_offset_cny"),
        } for s in year_snapshots_list],
    }

    idb.close()

    return {
        "accounts": accounts,
        "cash": cash,
        "total_cash_cny": cash_weighted.get("CNY", 0) + cash_weighted.get("HKD", 0) * 0.93 + cash_weighted.get("USD", 0) * 7.2,
        "total_stock_value": total_stock_value,
        "total_wealth": (latest_snapshot["totalWealthCny"] if latest_snapshot else total_stock_value + cash.get("CNY", 0)),
        "latest_snapshot": latest_snapshot,
        "snapshots": snapshots,
        "cash_flows": cash_flows,
        "transactions": transactions,
        "alerts": alerts,
        "triggered_alerts": triggered_alerts,
        "returns": returns,
        "stock_count": len(stocks),
        "holding_count": len(holding_stocks),
        "watching_count": len(watching_stocks),
        "cleared_count": sum(1 for s in stocks if s["status"] == "CLEARED"),
        "by_market": by_market,
        "by_type": by_type,
        "type_stocks": type_stocks,
        "by_sector": top_sectors,
        "sector_stocks": sector_stocks,
        "by_account": by_account,
        "fundamentals": {
            "avg_pe": round(sum(s["pe"] for s in with_pe) / len(with_pe), 1) if with_pe else None,
            "avg_pb": round(sum(s["pb"] for s in with_pb) / len(with_pb), 1) if with_pb else None,
            "with_pe_count": len(with_pe),
            "avg_div_yield_pct": round(sum(s["annualDivPerShare"] / s["currentPrice"] * 100 for s in with_div if s["currentPrice"] > 0) / len(with_div), 1) if with_div else None,
            "with_div_count": len(with_div),
        },
        "dividends": {
            "received": round(total_div_received, 0),
            "expected_annual": round(annual_div_expected, 0),
        },
        "concentration": {
            "top5_pct": round(concentration_pct, 1),
            "top_holdings": top_holdings_detail,
            "sector_warning": "房地产" if any("房地产" in (s["sector"] or "") for s in holding_stocks) else None,
        },
        "price_sparklines": price_sparklines,
    }


def _render_asset_html(assets: dict) -> str:
    """渲染资产总览 HTML。Phase 1: 财富趋势 + 账户拆分 + 现金流。Phase 2: 提醒 + 交易 + 股息。"""
    if "error" in assets:
        return f'<div class="callout">⚠️ {assets["error"]}</div>'

    a = assets
    cash_cny = a["total_cash_cny"]
    stock_val = a["total_stock_value"]
    total = cash_cny + stock_val
    stock_pct = stock_val / total * 100 if total > 0 else 0

    # ── Phase 1.1: wealth trend SVG sparkline ──
    wealth_chart = _render_sparkline(a.get("snapshots", []))

    # ── Phase 1.2: account breakdown ──
    accts = a.get("accounts", {})
    acct_str = ""
    for aid, acc in accts.items():
        name = acc.get("name", f"账户{aid}")
        pct = acc.get("ownershipPct", 1) * 100
        acct_str += f'{name}({pct:.0f}%) · '

    # ── Phase 1.3: cash flows ──
    flows = a.get("cash_flows", [])
    cf_str = ""
    if flows:
        net = sum(f["deltaCny"] for f in flows)
        cf_str = f'近10笔净{"流入" if net>=0 else "流出"}: {abs(net)/1e4:.1f}万'

    # Market bars
    market_bars = ""
    for m, d in sorted(a["by_market"].items(), key=lambda x: x[1]["value"], reverse=True):
        pct = d["value"] / stock_val * 100 if stock_val > 0 else 0
        if pct > 0.5:
            bar_w = max(pct, 2)
            market_bars += f'<span style="display:inline-block;width:{bar_w}%;background:var(--accent);height:4px;margin-right:1px" title="{m}:{pct:.0f}%"></span>'

    sector_items = " · ".join(f'{sec}({val/1e4:.1f}万)' for sec, val in a["by_sector"][:6])
    type_labels = {"A": "价值股", "B": "困境股", "C": "套利股"}
    type_items = " · ".join(f'{type_labels.get(t, t)}:{d["count"]}只' for t, d in sorted(a["by_type"].items()))

    f = a["fundamentals"]
    fund_str = ""
    if f["avg_pe"]: fund_str += f'PE {f["avg_pe"]} · '
    if f["avg_pb"]: fund_str += f'PB {f["avg_pb"]} · '
    if f["avg_div_yield_pct"]: fund_str += f'股息率 {f["avg_div_yield_pct"]}%'

    # ── Phase 2.1: alerts ──
    alert_str = ""
    alert_list = a.get("alerts", [])
    if alert_list:
        alert_items = []
        for al in alert_list[:8]:
            atype = al["alertType"]
            price = al["targetPrice"]
            cur = al.get("currentPrice") or price
            diff = (cur / price - 1) * 100 if price > 0 else 0
            icon = "🔴" if atype == "BUY1" else ("🟡" if atype == "BUY2" else "🟢")
            alert_items.append(f'{icon} {al["code"]} {atype}@{price:.2f} <small>({diff:+.0f}%)</small>')
        alert_str = f"""<div class="callout" style="border-left-color: var(--yellow);">
  <strong>📡 待触发提醒</strong> — {' · '.join(alert_items[:4])}
  {'<br>' + ' · '.join(alert_items[4:]) if len(alert_items) > 4 else ''}
</div>"""

    # ── Phase 2.2: transactions ──
    txn_str = ""
    txns = a.get("transactions", [])[:5]
    if txns:
        items = []
        for t in txns:
            icon = "🟢" if t["type"] == "BUY" else ("🔴" if t["type"] == "SELL" else "💵")
            items.append(f'{icon} {t["name"]} {t["type"]} {t["shares"]}股 @{t["price"]:.2f}')
        txn_str = " · ".join(items)

    # ── Phase 2.3: dividends ──
    div = a.get("dividends", {})
    div_str = ""
    if div.get("expected_annual", 0) > 0:
        div_str = f'已收 ¥{div.get("received",0):,.0f} · 预计年 ¥{div.get("expected_annual",0):,.0f}'

    # Phase 3.1: concentration
    conc = a.get("concentration", {})
    conc_items = " · ".join(f'{h["code"]} {h["name"]} {h["pct"]:.0f}%' for h in conc.get("top_holdings", [])[:5])
    conc_warn = ""
    if conc.get("sector_warning"):
        conc_warn = f' <span style="color:var(--red)">⚠️{conc["sector_warning"]}集中</span>'
    conc_str = f"""<div class="asset-card asset-wide">
    <div class="asset-label">持仓集中度{conc_warn}</div>
    <div class="asset-value" style="font-size:0.85em">TOP5占比 {conc.get('top5_pct',0):.0f}%</div>
    <div class="asset-sub">{conc_items}</div>
  </div>"""

    return f"""<div class="asset-overview">
<div class="asset-row">
  <div class="asset-card asset-primary">
    <div class="asset-label">总资产</div>
    <div class="asset-value">{total/1e4:.1f}万</div>
    <div class="asset-sub">股票 {stock_val/1e4:.1f}万({stock_pct:.0f}%) · 现金 {cash_cny/1e4:.1f}万({100-stock_pct:.0f}%)</div>
    <div class="asset-sub">{acct_str}</div>
    {wealth_chart}
  </div>
  <div class="asset-card">
    <div class="asset-label">持仓</div>
    <div class="asset-value">{a['holding_count']}只</div>
    <div class="asset-sub">观察 {a['watching_count']}只 · 已清 {a['cleared_count']}只</div>
    <div class="asset-sub" style="margin-top:0.5em">{cf_str}</div>
  </div>
  <div class="asset-card">
    <div class="asset-label">股息</div>
    <div class="asset-value" style="font-size:1.1em">{div_str or '--'}</div>
  </div>
</div>
</div>
<script>
document.querySelectorAll('.sparkline-bar').forEach(function(el) {{
  var vals = el.dataset.prices.split(',').map(Number);
  if (vals.length < 2) return;
  var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals) || mn+1;
  var w = 60, h = 12, html = '';
  vals.forEach(function(v, i) {{
    var x = (i/(vals.length-1))*w, barH = Math.max(1, ((v-mn)/(mx-mn))*h);
    html += '<rect x="'+x+'" y="'+(h-barH)+'" width="1" height="'+barH+'" fill="'+(v>=vals[0]?'var(--green)':'var(--red)')+'"/>';
  }});
  el.innerHTML = '<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none" style="width:60px;height:12px">'+html+'</svg>';
}});
</script>"""


def _render_sparkline(snapshots: list[dict]) -> str:
    """Phase 1.1: 用 SVG 渲染财富趋势迷你图。"""
    if len(snapshots) < 5: return ""
    # Sample to ~60 points max
    step = max(1, len(snapshots) // 60)
    pts = snapshots[::step]
    if len(pts) < 3: return ""

    values = [s["totalWealthCny"] for s in pts]
    mn, mx = min(values), max(values)
    if mx == mn: mx = mn + 1
    w, h = 100, 30  # percentage-based
    path_parts = []
    for i, v in enumerate(values):
        x = i / (len(values) - 1) * w
        y = (1 - (v - mn) / (mx - mn)) * h
        path_parts.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")

    color = "#2d7a3a" if values[-1] >= values[0] else "#8b0000"
    change = (values[-1] / values[0] - 1) * 100
    return f"""<svg class="sparkline" viewBox="0 0 {w} {h}" preserveAspectRatio="none">
  <polyline points="{' '.join(p.replace('L','').replace('M','').replace(',',' ') for p in path_parts)}"
    fill="none" stroke="{color}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>
</svg>
<div style="font-size:0.7em;color:{color}">{change:+.1f}%</div>"""