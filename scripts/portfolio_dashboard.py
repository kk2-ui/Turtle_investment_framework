#!/usr/bin/env python3
"""portfolio_dashboard.py — 投资组合仪表盘生成器 V2 (DB-backed)

从 portfolio.db 读取分析成果 + 关注列表，生成：
  - output/_portfolio.html      自包含 HTML 仪表盘
  - output/_portfolio_export.json  可导入 invest app 的 JSON

纯 Python，零 LLM 依赖。
Usage:
  python scripts/portfolio_dashboard.py                     # 生成仪表盘
  python scripts/portfolio_dashboard.py --export-only       # 仅导出 JSON
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")

# 把 scripts/ 加到 path 以 import portfolio_db
_SCRIPTS_DIR = os.path.join(_FRAMEWORK_DIR, "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _load_rows() -> list[dict[str, Any]]:
    """从 DB 读取分析 + watchlist 联表 + 未分析持仓。Phase 1.6: 自动同步最新 invest 备份。"""
    from portfolio_db import get_db, _DB_PATH, sync_watchlist

    # Phase 1.6: 自动检测最新 invest 备份并同步
    try:
        n = sync_watchlist()  # auto-find latest backup
        if n > 0:
            print(f"  🔄 自动同步 invest 持仓: {n} 只")
    except Exception:
        pass

    # Phase 5: 抓取实时行情
    try:
        from quote_fetcher import fetch_all_prices
        fp = fetch_all_prices()
        print(f"  📡 实时行情: {fp.get('updated',0)}/{fp.get('total',0)} 只")
    except Exception as e:
        pass

    dbi = get_db()
    rows_raw = dbi.execute("""
        SELECT a.*, w.invest_code, w.invest_status, w.current_hold, w.avg_cost AS inv_avg_cost,
               w.hold_limit_pct AS inv_hold_limit_pct, w.annual_div_per_share AS inv_dps,
               w.invest_logic AS inv_logic, w.my_valuation AS inv_valuation,
               w.name AS wl_name
        FROM analysis a
        LEFT JOIN watchlist w ON a.ts_code = w.ts_code
        ORDER BY a.gg_discounted DESC
    """).fetchall()
    rows = [dict(r) for r in rows_raw]

    # 补充：持仓但未分析的股票
    analyzed_codes = {r["ts_code"] for r in rows}
    unanalyzed = dbi.execute("""
        SELECT * FROM watchlist WHERE current_hold > 0 AND ts_code NOT IN ({})
        ORDER BY current_hold DESC
    """.format(",".join("?" * len(analyzed_codes)) if analyzed_codes else "''"),
        list(analyzed_codes)
    ).fetchall() if analyzed_codes else []

    dbi.close()

    now = datetime.now()
    for r in rows:
        r["market"] = r.get("market", "?")
        r["gg_val"] = r.get("gg_discounted") or r.get("gg_base")
        r["gg_ok"] = bool(r.get("gg_ok"))
        r["inv_holding"] = r.get("current_hold", 0) or 0
        r["inv_status"] = r.get("invest_status", "") or ""
        r["_row_type"] = "analyzed"
        # Phase 1.5: 分析时效 + 陈旧标记
        at = r.get("analyzed_at", "")
        try:
            ad = datetime.fromisoformat(at.replace("Z", "+00:00").replace(" ", "T"))
            r["_days_ago"] = (now - ad.replace(tzinfo=None)).days
        except Exception:
            r["_days_ago"] = 999
        r["_stale"] = r["_days_ago"] > 30

    # 追加未分析持仓
    for u in unanalyzed:
        u = dict(u)
        u.update({
            "gg_val": None, "gg_ok": False, "decision": "⚠️待分析",
            "market": u.get("market", "?"), "inv_holding": u.get("current_hold", 0) or 0,
            "_row_type": "unanalyzed", "analyzed_at": ""
        })
        rows.append(u)

    return rows


# ── HTML (CSS + JS same as V1) ──────────────────────────────────────

_CSS = r"""
  :root {
    --bg: #fffff8; --text: #333; --text-light: #888; --heading: #1a1a1a;
    --border: #e0d8cc; --accent: #8b0000; --accent-light: #faf5f0;
    --green: #2d7a3a; --green-bg: #edf7ee; --red: #8b0000; --red-bg: #faf5f0;
    --yellow: #7a6a1b; --yellow-bg: #faf8f0; --card-bg: #fff;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #1c1c1a; --text: #d4d0c8; --text-light: #999588; --heading: #e8e4d8;
      --border: #3d3830; --accent: #c77d4d; --accent-light: #2a2420;
      --green: #5c9a62; --green-bg: #1a2a1c; --red: #c77d4d; --red-bg: #2a2420;
      --yellow: #b8a040; --yellow-bg: #2a2820; --card-bg: #22201c;
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6; font-size: 14px;
    -webkit-font-smoothing: antialiased;
  }
  .container { max-width: 1160px; margin: 0 auto; padding: 2em 1.5em; }
  h1 { font-size: 1.5em; font-weight: 700; color: var(--heading); margin-bottom: 0.2em; }
  .subtitle { color: var(--text-light); font-size: 0.85em; margin-bottom: 1.5em; }
  .stats { display: flex; gap: 1em; margin-bottom: 1.8em; flex-wrap: wrap; }
  .stat-tile {
    flex: 1; min-width: 110px; background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 6px; padding: 1em 1em; text-align: center;
  }
  .stat-tile .num { font-size: 1.8em; font-weight: 700; color: var(--heading); }
  .stat-tile .label { font-size: 0.72em; color: var(--text-light); margin-top: 0.3em; letter-spacing: 0.04em; text-transform: uppercase; }
  .filters { display: flex; gap: 0.5em; margin-bottom: 1.2em; flex-wrap: wrap; }
  .filters button {
    padding: 0.35em 0.9em; border: 1px solid var(--border); border-radius: 4px;
    background: var(--bg); color: var(--text-light); cursor: pointer; font-size: 0.8em;
    font-family: inherit; transition: all 0.15s;
  }
  .filters button:hover { border-color: var(--accent); color: var(--accent); }
  .filters button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 6px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
  thead { border-bottom: 2px solid var(--heading); }
  th {
    padding: 10px 12px 8px; text-align: left; font-weight: 600; color: var(--heading);
    white-space: nowrap; font-size: 0.85em; letter-spacing: 0.03em; cursor: pointer;
    user-select: none;
  }
  th:hover { color: var(--accent); }
  th .sort-arrow { font-size: 0.7em; margin-left: 2px; opacity: 0.4; }
  th.sorted .sort-arrow { opacity: 1; }
  td { padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--accent-light); }
  tr.row-avoid td { opacity: 0.55; }
  tr.row-broken td { opacity: 0.4; }
  .code-cell { font-weight: 600; white-space: nowrap; }
  .name-cell { white-space: nowrap; }
  .holding-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 4px; }
  .dot-holding { background: var(--green); }
  .dot-watching { background: var(--yellow); }
  .dot-none { background: var(--border); }
  .gg-good { color: var(--green); font-weight: 600; }
  .gg-bad { color: var(--red); }
  .upside-pos { color: var(--green); }
  .upside-neg { color: var(--red); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.78em; font-weight: 700; letter-spacing: 0.04em; white-space: nowrap; }
  .badge-strong-buy { background: #1b5e33; color: #fff; }
  .badge-buy { background: #2d7a3a; color: #fff; }
  .badge-hold { background: #7a6a1b; color: #fff; }
  .badge-avoid { background: #5c1a1a; color: #fff; }
  .badge-broken { background: #888; color: #fff; }
  .detail-row { display: none; }
  .detail-row.open { display: table-row; }
  .detail-row td { padding: 0; border-bottom: 2px solid var(--border); }
  .detail-panel {
    padding: 1.2em 1.5em; background: var(--accent-light);
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1em; font-size: 0.85em;
  }
  .detail-section h4 { font-size: 0.8em; letter-spacing: 0.06em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.4em; }
  .detail-section p { margin: 0.15em 0; color: var(--text-light); }
  .detail-section .val { color: var(--heading); font-weight: 600; }
  .clickable { cursor: pointer; }
  .clickable:hover { background: var(--accent-light); }
  .history-link { font-size: 0.8em; color: var(--accent); text-decoration: none; margin-left: 0.5em; }
  .empty { text-align: center; padding: 3em; color: var(--text-light); }
  @media print {
    .filters, .stats { display: none; }
    .detail-row { display: table-row !important; }
    .detail-panel { font-size: 0.7em; }
  }
"""

_JS = r"""
document.addEventListener('DOMContentLoaded', function() {
  const rows = Array.from(document.querySelectorAll('tbody tr.data-row'));
  let sortCol = -1, sortAsc = true;
  document.querySelectorAll('.filters button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.filters button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var f = btn.dataset.filter;
      rows.forEach(function(r) {
        if (f === 'all') r.style.display = '';
        else if (r.dataset.decision === f) r.style.display = '';
        else if (f === 'holding' && r.dataset.holding === 'true') r.style.display = '';
        else if (f === 'watching' && r.dataset.watching === 'true') r.style.display = '';
        else r.style.display = 'none';
      });
    });
  });
  document.querySelectorAll('th[data-sort]').forEach(function(th) {
    th.addEventListener('click', function() {
      var col = th.dataset.sort;
      if (sortCol === col) { sortAsc = !sortAsc; } else { sortCol = col; sortAsc = true; }
      document.querySelectorAll('th').forEach(function(h) { h.classList.remove('sorted'); });
      th.classList.add('sorted');
      var tbody = document.querySelector('tbody');
      rows.sort(function(a, b) {
        var va = a.dataset[col] || '', vb = b.dataset[col] || '';
        var na = parseFloat(va), nb = parseFloat(vb);
        if (!isNaN(na) && !isNaN(nb)) return sortAsc ? na - nb : nb - na;
        return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      });
      rows.forEach(function(r) { tbody.appendChild(r); tbody.appendChild(r.nextElementSibling); });
    });
  });
  document.querySelectorAll('tr.data-row').forEach(function(tr) {
    tr.addEventListener('click', function() {
      var detail = tr.nextElementSibling;
      if (detail && detail.classList.contains('detail-row')) {
        detail.classList.toggle('open');
      }
    });
  });
});
"""


def _fmt(f, default="?"):
    if f is None: return default
    return f


def _build_html(rows: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    table_rows = []
    for r in rows:
        is_unanalyzed = r.get("_row_type") == "unanalyzed"
        status = r.get("invest_status", "")
        hold_shares = r["inv_holding"]

        # holding dot + code
        if hold_shares > 0:
            hold_dot = '<span class="holding-dot dot-holding"></span>'
        elif status == "WATCHING":
            hold_dot = '<span class="holding-dot dot-watching"></span>'
        else:
            hold_dot = '<span class="holding-dot dot-none"></span>'
        code_display = f'{hold_dot}{r["ts_code"]}'
        if is_unanalyzed:
            code_display += ' 🔔'

        # holding column
        if hold_shares > 0:
            hold_str = f'{hold_shares:,}股'
        elif status == "WATCHING":
            hold_str = '观察'
        else:
            hold_str = '-'

        # GG
        gg_val = r["gg_val"]
        gg_str = f'{gg_val:.1f}%' if gg_val else '-'
        gg_cls = "gg-good" if (gg_val and r.get("ii") and gg_val > r["ii"]) else ("gg-bad" if gg_val else "")

        ii_str = f'{r.get("ii", 0):.1f}%' if r.get("ii") else '-'
        date_str = (r.get("analyzed_at") or "")[:10]
        # Phase 1.4: live price from invest sync
        live_price = r.get("live_price") or 0
        analysis_price = r.get("price") or 0
        display_price = live_price if live_price > 0 else analysis_price
        price_str = f'{display_price:.2f}' if display_price else '-'
        # price deviation badge
        if live_price > 0 and analysis_price > 0:
            dev = (live_price / analysis_price - 1) * 100
            if abs(dev) > 20:
                price_str += f' <span class="days-old">({dev:+.0f}%)</span>'
        # Phase 1.4: flag stocks where live_price < buy_price and decision is Buy/Strong Buy
        # #5: use corrected buy price (DDM fallback already applied)
        r["_can_buy_now"] = (live_price > 0 and buy_price_raw > 0 and live_price <= buy_price_raw
                             and r.get("decision") in ("Strong Buy", "Buy"))

        # buy price — #5: DDM fallback detection
        buy_upside = r.get("buy_upside")
        buy_price_raw = r.get("buy_price") or 0
        p_base = r.get("p_base_hkd") or 0
        p_fcfe = r.get("p_fcfe_hkd") or 0
        price_cur = r.get("live_price") or r.get("price") or 0
        ddm_broken = False
        # DDM broken: buy_price < 5% of current price (e.g. Tencent 4.26 vs 469)
        if buy_price_raw > 0 and price_cur > 0 and buy_price_raw < price_cur * 0.05:
            ddm_broken = True
            # Use P_base (GG=II fair price) or FCFE P_base
            fallback = p_fcfe or p_base
            if fallback > 0:
                buy_str = f'<span title="DDM失效(零分红), 改用P_base">{fallback:.2f}</span>'
                buy_price_raw = fallback
            else:
                buy_str = 'DDM失效'
        else:
            buy_str = f'{buy_price_raw:.2f}' if buy_price_raw > 0 else "-"

        # upside calc
        if buy_price_raw > 0 and price_cur > 0:
            buy_upside = (buy_price_raw / price_cur - 1) * 100
        if buy_upside is not None:
            up_str = f'{buy_upside:+.0f}%'
            up_cls = "upside-pos" if buy_upside > 0 else "upside-neg"
        else:
            up_str, up_cls = "-", ""

        # decision badge + stale highlight
        decision = r.get("decision", "?")
        is_stale = r.get("_stale", False)
        if is_unanalyzed:
            row_cls, badge_cls = "row-broken", "badge-broken"
        elif not r["gg_ok"]:
            row_cls, badge_cls = "row-broken", "badge-broken"
        elif is_stale and decision in ("Strong Buy", "Buy"):
            row_cls, badge_cls = "row-stale", "badge-buy"  # stale but still good
        elif decision == "Strong Buy":
            row_cls, badge_cls = "", "badge-strong-buy"
        elif decision == "Buy":
            row_cls, badge_cls = "", "badge-buy"
        elif decision == "Hold":
            row_cls, badge_cls = "", "badge-hold"
        else:
            row_cls, badge_cls = "row-avoid", "badge-avoid"

        # position
        pos_pct = r.get("pos_pct") or 0
        pos_str = f'{pos_pct:.1f}%' if pos_pct else "-"

        # valuation comparison: manual vs Turtle
        manual_val = r.get("inv_valuation") or 0
        turtle_val = r.get("p_base_hkd") or r.get("buy_price") or 0
        if manual_val > 0 and turtle_val > 0:
            diff_pct = (turtle_val / manual_val - 1) * 100
            arrow = "↑" if diff_pct > 0 else "↓"
            val_str = f'{manual_val:.2f} <span class="val">{turtle_val:.2f}</span> <span class="{"upside-pos" if diff_pct > 0 else "upside-neg"}">{arrow}{abs(diff_pct):.0f}%</span>'
        elif manual_val > 0:
            val_str = f'{manual_val:.2f}'
        else:
            val_str = "-"

        # Phase 1.5: days ago
        days_ago = r.get("_days_ago", 0) if not is_unanalyzed else 0
        if is_unanalyzed:
            days_str = "-"
            days_cls = ""
        elif days_ago > 90:
            days_str = f'{days_ago}d ⚠'
            days_cls = "days-old"
        elif days_ago > 30:
            days_str = f'{days_ago}d'
            days_cls = "days-warn"
        else:
            days_str = f'{days_ago}d'
            days_cls = "days-ok"

        sort_gg = str(gg_val) if gg_val else "0"
        sort_upside = str(buy_upside if buy_upside is not None else -999)

        detail = "" if is_unanalyzed else _build_detail(r)
        name = (r.get("wl_name") or r.get("name") or "?")[:8]

        table_rows.append(f"""<tr class="data-row clickable {row_cls}" data-decision="{decision}" data-gg="{sort_gg}" data-upside="{sort_upside}" data-holding="{'true' if hold_shares > 0 else 'false'}" data-watching="{'true' if not is_unanalyzed and status == 'WATCHING' else 'false'}">
  <td class="code-cell">{code_display}</td>
  <td class="name-cell" title="{name}">{name}</td>
  <td>{hold_str}</td>
  <td>{date_str}</td>
  <td class="{days_cls}">{days_str}</td>
  <td>{price_str}</td>
  <td class="{gg_cls}">{gg_str}</td>
  <td>{ii_str}</td>
  <td>{buy_str}<span class="{up_cls}">{up_str}</span></td>
  <td><span class="badge {badge_cls}">{decision}</span></td>
  <td>{pos_str}</td>
  <td class="val-cell">{val_str}</td>
</tr>""")
        if detail:
            table_rows.append(f'<tr class="detail-row"><td colspan="12">{detail}</td></tr>')

    holding_count = sum(1 for r in rows if r["inv_holding"] > 0)
    analyzed_total = sum(1 for r in rows if r.get("_row_type") == "analyzed")
    analyzed_holding = sum(1 for r in rows if r["inv_holding"] > 0 and r.get("_row_type") == "analyzed" and r.get("gg_ok"))
    unanalyzed_holding = sum(1 for r in rows if r.get("_row_type") == "unanalyzed")
    strong_buy = sum(1 for r in rows if r.get("decision") == "Strong Buy")
    buy = sum(1 for r in rows if r.get("decision") == "Buy")
    hold = sum(1 for r in rows if r.get("decision") == "Hold")
    avoid = sum(1 for r in rows if r.get("decision") == "Avoid")
    broken = sum(1 for r in rows if r.get("decision") in ("⚠️待重分析", "⚠️待分析"))
    gg_gt_ii = sum(1 for r in rows if r["gg_val"] and r.get("ii") and r["gg_val"] > r["ii"])

    # Phase 1.3: priority callout for unanalyzed holdings
    unanalyzed_rows = [r for r in rows if r.get("_row_type") == "unanalyzed"]
    # Phase 5: 组合穿透回报率
    portfolio_gg = 0.0
    portfolio_total_value = 0.0
    holdings_with_gg = 0
    for r in rows:
        holding = r.get("inv_holding", 0) or 0
        price = r.get("live_price") or r.get("price") or 0
        mv = holding * price
        gg = r.get("gg_discounted") or r.get("gg_base") or 0
        if mv > 0 and gg > 0 and r.get("_row_type") == "analyzed" and r.get("gg_ok"):
            portfolio_gg += mv * gg
            portfolio_total_value += mv
            holdings_with_gg += 1
    if portfolio_total_value > 0:
        portfolio_gg /= portfolio_total_value  # weighted average

    portfolio_html = ""
    if portfolio_total_value > 0:
        rf = 4.0  # risk-free rate
        gg_premium = portfolio_gg - rf
        gg_color = "var(--green)" if portfolio_gg > 7 else "var(--heading)"
        portfolio_html = f"""<div class="stats" style="margin-bottom:0.8em">
  <div class="stat-tile" style="border:2px solid var(--accent)"><div class="num" style="color:{gg_color}">{portfolio_gg:.1f}%</div><div class="label">🏮 组合穿透GG</div></div>
  <div class="stat-tile"><div class="num">{holdings_with_gg}</div><div class="label">有分析持仓</div></div>
  <div class="stat-tile"><div class="num">{portfolio_total_value/1e4:.0f}万</div><div class="label">分析覆盖市值</div></div>
  <div class="stat-tile"><div class="num" style="color:{gg_color}">{gg_premium:+.1f}%</div><div class="label">vs Rf({rf}%)超额</div></div>
</div>"""

    priority_html = ""
    if unanalyzed_rows:
        items = []
        for u in unanalyzed_rows[:5]:
            code = u["ts_code"]
            name = (u.get("wl_name") or u.get("name") or code)[:8]
            sh = u.get("current_hold", 0)
            items.append(f'<span class="priority-item">🔔 {code} {name} ({sh:,}股)</span>')
        priority_html = f"""<div class="callout">
  <strong>📋 持仓待分析 TOP{min(5, len(unanalyzed_rows))}</strong> — {' · '.join(items)}
  <span class="callout-note">共 {len(unanalyzed_rows)} 只持仓未分析</span>
</div>"""

        stale_count = sum(1 for r in rows if r.get("_stale") and r.get("_row_type") == "analyzed")

    # Phase 1.4: buy-now callout
    can_buy = [r for r in rows if r.get("_can_buy_now")]
    buy_now_html = ""
    if can_buy:
        items = []
        for r in can_buy:
            lp = r.get("live_price") or 0
            bp = r.get("buy_price") or 0
            disc = (1 - lp / bp) * 100 if bp > 0 else 0
            items.append(f'<span class="priority-item">💰 {r["ts_code"]} {r.get("wl_name",r.get("name",""))[:6]} 现价{lp:.2f}<买价{bp:.2f}(-{disc:.0f}%)</span>')
        buy_now_html = f"""<div class="callout" style="border-left-color: var(--green); background: var(--green-bg);">
  <strong>💰 当前可买 ({len(can_buy)} 只)</strong> — 实时价已跌破 Turtle 建议买入价
  <br>{' · '.join(items)}
</div>"""

    # Phase 4: backtest embed
    from backtest import run_backtest as _bt
    bt_results = _bt()
    hit_count = sum(1 for r in bt_results if r["hit"])
    avg_score = sum(r["score"] for r in bt_results) / len(bt_results) if bt_results else 0
    backtest_html = ""
    if bt_results:
        bt_items = []
        for r in bt_results[:6]:
            hit_icon = "✅" if r["hit"] else ("❌" if r["hit"] is False else "—")
            bt_items.append(f'<span class="priority-item">{hit_icon} {r["ts_code"]} {r["decision"]} 评分{r["score"]}</span>')
        backtest_html = f"""<div class="callout" style="border-left-color: var(--green);">
  <strong>📊 Turtle 回测</strong> — {hit_count}/{len(bt_results)} 只价格到位 · 均分 {avg_score:.0f}
  <span class="callout-note">运行 <code>python scripts/backtest.py</code> 查看详情</span>
  <br>{' · '.join(bt_items)}
</div>"""

    # Phase 2.2: rerun suggestions
    from portfolio_db import get_rerun_suggestions
    suggestions = get_rerun_suggestions()[:8]
    suggest_html = ""
    if suggestions:
        items = []
        for s in suggestions:
            ts = s["ts_code"]
            name = (s.get("name") or ts)[:8]
            reason = s["reason"]
            items.append(f'<span class="priority-item">📌 {ts} {name} <small>({reason})</small></span>')
        suggest_html = f"""<div class="callout">
  <strong>🔄 建议重分析 TOP{len(suggestions)}</strong> — {' · '.join(items[:5])}
  {f'<br>{" · ".join(items[5:])}' if len(items) > 5 else ''}
  <div class="callout-note">运行 <code>python scripts/batch_analyze.py --stale</code> 一键重分析</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>年糕投资仪表盘</title>
<style>{_CSS}
  /* Phase 1 additions */
  .days-ok {{ color: var(--text-light); font-size: 0.8em; }}
  .days-warn {{ color: var(--yellow); font-weight: 600; }}
  .days-old {{ color: var(--red); font-weight: 600; }}
  tr.row-stale td {{ background: var(--yellow-bg); }}
  .callout {{
    background: var(--accent-light); border-left: 3px solid var(--accent);
    border-radius: 0 4px 4px 0; padding: 0.6em 1em; margin-bottom: 1em; font-size: 0.85em;
  }}
  .callout-note {{ font-size: 0.8em; color: var(--text-light); margin-left: 1em; }}
  .priority-item {{ margin-right: 0.8em; white-space: nowrap; }}
  .val-cell {{ font-size: 0.85em; }}
</style>
</head>
<body>
<div class="container">
<h1>🏮 年糕投资仪表盘</h1>
<div class="subtitle">更新于 {now} · {analyzed_total} 只已分析 · {holding_count} 只持仓 · 数据源: invest实时DB</div>

{portfolio_html}

<div class="stats">
  <div class="stat-tile"><div class="num">{analyzed_holding}/{holding_count}</div><div class="label">持仓已分析</div></div>
  <div class="stat-tile"><div class="num">{unanalyzed_holding}</div><div class="label">🔔持仓待分析</div></div>
  <div class="stat-tile"><div class="num">{strong_buy + buy}</div><div class="label">Buy 信号</div></div>
  <div class="stat-tile"><div class="num">{hold}</div><div class="label">Hold</div></div>
  <div class="stat-tile"><div class="num">{avoid}</div><div class="label">Avoid</div></div>
  <div class="stat-tile"><div class="num">{gg_gt_ii}</div><div class="label">GG &gt; II</div></div>
  <div class="stat-tile"><div class="num">{broken}</div><div class="label">⚠️待处理</div></div>
  <div class="stat-tile"><div class="num">{stale_count}</div><div class="label">⏰超30天</div></div>
</div>

<div class="filters">
  <button class="active" data-filter="all">全部</button>
  <button data-filter="holding">● 已持有</button>
  <button data-filter="watching">○ 观察中</button>
  <button data-filter="Strong Buy">Strong Buy</button>
  <button data-filter="Buy">Buy</button>
  <button data-filter="Hold">Hold</button>
  <button data-filter="Avoid">Avoid</button>
</div>

{priority_html}
{suggest_html}
{backtest_html}
{buy_now_html}

<div class="table-wrap">
<table>
<thead>
<tr>
  <th data-sort="code">代码</th>
  <th>名称</th>
  <th>持仓</th>
  <th>分析日期</th>
  <th>距今</th>
  <th>现价</th>
  <th data-sort="gg" class="sorted">GG ▼</th>
  <th>II</th>
  <th data-sort="upside">买入价</th>
  <th>决策</th>
  <th>仓位</th>
  <th>估值(手动→Turtle)</th>
</tr>
</thead>
<tbody>
{''.join(table_rows)}
</tbody>
</table>
</div>

<div class="subtitle" style="margin-top:1.5em;">
  ●已持有 ○观察中 🔔持仓待分析 ⏰超30天建议重分析 · GG绿色=超过门槛
</div>
</div>
<script>{_JS}</script>
</body>
</html>"""
    return html


def _build_detail(r: dict) -> str:
    parts = []
    gg_disc = _fmt(r.get("gg_discounted"))
    gg_fcfe = _fmt(r.get("gg_fcfe"))
    aa_3y = f"{r['aa_3y']:.1f}M" if r.get("aa_3y") else "?"
    ii = _fmt(r.get("ii"))
    p_base_hkd = f"{r['p_base_hkd']:.2f}" if r.get("p_base_hkd") else "?"
    p_fcfe_hkd = f"{r['p_fcfe_hkd']:.2f}" if r.get("p_fcfe_hkd") else "?"
    upside = f"{r['upside_pct']:+.0f}%" if r.get("upside_pct") is not None else "?"
    pos = f"{r['pos_pct']:.1f}%" if r.get("pos_pct") else "?"
    parent = f"归母: {r['parent_ratio']:.3f}" if r.get("parent_ratio") else ""
    net_cash = f"净现金/MC: {r['net_cash_pct_mc']:.0f}%" if r.get("net_cash_pct_mc") else ""

    parts.append(f"""<div class="detail-section">
<h4>GG 推导</h4>
<p>GG(折价后): <span class="val">{gg_disc}%</span></p>
<p>GG(FCFE): <span class="val">{gg_fcfe}%</span></p>
<p>AA₃y: <span class="val">{aa_3y}</span>  II: <span class="val">{ii}%</span></p>
<p>{parent}  {net_cash}</p>
</div>""")

    parts.append(f"""<div class="detail-section">
<h4>估值</h4>
<p>P_base(HKD): <span class="val">{p_base_hkd}</span></p>
<p>P_FCFE(HKD): <span class="val">{p_fcfe_hkd}</span></p>
<p>上涨空间: <span class="val">{upside}</span></p>
<p>建议仓位: <span class="val">{pos}</span></p>
</div>""")

    parts.append(f"""<div class="detail-section">
<h4>风险</h4>
<p>价值陷阱: {"⚠️是" if r.get('vt_excluded') else "否"}</p>
<p>外推可信度: <span class="val">{r.get('extrap_overall', '?')}</span></p>
</div>""")

    # Phase 3/7: GG trend from history
    ts = r.get("ts_code", "")
    if ts:
        from portfolio_db import get_analysis_history
        hist = get_analysis_history(ts)
        if len(hist) >= 2:
            prev = hist[1]  # second most recent
            prev_gg = prev.get("gg_discounted")
            curr_gg = r.get("gg_discounted")
            if prev_gg and curr_gg and prev_gg != 0:
                gg_change = curr_gg - prev_gg
                arrow = "↑" if gg_change > 0 else "↓" if gg_change < 0 else "→"
                parts.append(f"""<div class="detail-section">
<h4>GG 趋势</h4>
<p>上次: <span class="val">{prev_gg:.1f}%</span> ({prev.get('analyzed_at','')[:10]})</p>
<p>本次: <span class="val">{curr_gg:.1f}%</span> <span class="{'gg-good' if gg_change>0 else 'gg-bad'}">{arrow}{abs(gg_change):.1f}pp</span></p>
<p>上次决策: <span class="val">{prev.get('decision','?')}</span></p>
</div>""")

    report = r.get("report_html") or ""
    if report:
        parts.append(f"""<div class="detail-section">
<h4>完整报告</h4>
<p><a href="{report}" target="_blank">📄 打开分析报告</a></p>
</div>""")

    return f'<div class="detail-panel">{"".join(parts)}</div>'


# ── export ──────────────────────────────────────────────────────────

def export_invest_json(rows: list[dict]) -> str:
    """生成 invest app 可导入的 stocks_import.json。Phase 3: 含独立 Turtle 字段。"""
    from portfolio_db import _turtle_to_invest_code
    stocks_out = []
    for r in rows:
        if not r.get("gg_ok") and r.get("_row_type") == "analyzed":
            continue  # 跳过数据异常的
        inv_code = _turtle_to_invest_code(r["ts_code"])
        valuation = r.get("p_base_rmb") or ((r.get("buy_price") or 0) * 0.93)
        stocks_out.append({
            "code": inv_code,
            "name": r.get("wl_name") or r.get("name") or "",
            "market": r.get("market", "?"),
            "myValuation": round(valuation, 4) if valuation else 0,
            "multiplier2": 0.6,
            "holdLimitPct": max(min((r.get("pos_pct") or 5) / 100, 0.05), 0.01),
            "currentHold": r.get("inv_holding", 0),
            "avgCost": r.get("inv_avg_cost", 0) or 0,
            "annualDivPerShare": r.get("dps") or r.get("inv_dps") or 0,
            "status": "HOLDING" if (r.get("inv_holding") or 0) > 0 else "WATCHING",
            "investLogic": f"Turtle GG={r.get('gg_discounted')}% II={r.get('ii')}% {r.get('decision','')}",
            "sellMultiplier": 1.2,
            # Phase 3: Turtle 独立字段（供 invest App 未来直接读取）
            "_turtle": {
                "gg": r.get("gg_discounted"),
                "gg_fcfe": r.get("gg_fcfe"),
                "ii": r.get("ii"),
                "decision": r.get("decision"),
                "p_base_hkd": r.get("p_base_hkd"),
                "p_base_rmb": r.get("p_base_rmb"),
                "buy_price": r.get("buy_price"),
                "buy_star": r.get("buy_star"),
                "upside_pct": r.get("upside_pct"),
                "pos_pct": r.get("pos_pct"),
                "analyzed_at": r.get("analyzed_at", ""),
                "parent_ratio": r.get("parent_ratio"),
                "extrap_overall": r.get("extrap_overall"),
            }
        })
    return json.dumps({"cash": {"CNY": 0, "HKD": 0, "USD": 0}, "stocks": stocks_out}, indent=2, ensure_ascii=False)


# ── main ────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="投资组合仪表盘 V2 (DB-backed)")
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--sync-invest", action="store_true", help="先生成 DB，再同步 invest 数据，再刷新")
    args = ap.parse_args()

    if args.sync_invest:
        from portfolio_db import sync_watchlist, sync_holdings
        w = sync_watchlist()
        h = sync_holdings()
        print(f"✅ 同步完成: watchlist={w} holdings={h}")

    print("📊 读取 portfolio.db...")
    rows = _load_rows()
    print(f"   {len(rows)} 条分析记录")

    # Export
    export_path = os.path.join(_OUTPUT_DIR, "_portfolio_export.json")
    export_json = export_invest_json(rows)
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(export_json)
    print(f"📤 导出: {export_path}")

    if args.export_only:
        return

    # HTML
    html = _build_html(rows)
    html_path = os.path.join(_OUTPUT_DIR, "_portfolio.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 仪表盘: {html_path}")

    strong = sum(1 for r in rows if r.get("decision") == "Strong Buy")
    buy = sum(1 for r in rows if r.get("decision") == "Buy")
    hold = sum(1 for r in rows if r.get("decision") == "Hold")
    avoid = sum(1 for r in rows if r.get("decision") == "Avoid")
    broken = sum(1 for r in rows if not r.get("gg_ok"))
    print(f"\n📊 Strong Buy={strong} Buy={buy} Hold={hold} Avoid={avoid} ⚠️={broken}")


if __name__ == "__main__":
    main()
