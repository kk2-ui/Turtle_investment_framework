"""niangao.dashboard — 展示层：HTML 仪表盘生成

纯渲染逻辑，数据来自 niangao.db + niangao.metrics + niangao.quotes
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

from niangao.db import (get_db, get_unanalyzed_holdings, get_analysis_history,
                         get_rerun_suggestions, _turtle_to_invest_code)
from niangao.metrics import classify_decision, compute_portfolio_gg, run_backtest, compute_rebalance
from niangao.sync import sync_watchlist, sync_holdings
from niangao.assets import load_asset_overview, _render_asset_html

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")
_NIANGAO_DIR = os.path.join(os.path.dirname(_FRAMEWORK_DIR), "_niangao")  # analy/_niangao/

import sys as _sys_dash
_scripts_dir_dash = os.path.join(_FRAMEWORK_DIR, "scripts")
if _scripts_dir_dash not in _sys_dash.path:
    _sys_dash.path.insert(0, _scripts_dir_dash)
try:
    from turtle_agent._version import REPORT_VERSION as _REPORT_VERSION, \
        REPORTS_SUBDIR as _REPORTS_SUBDIR
except ImportError:
    _REPORT_VERSION = "v13"
    _REPORTS_SUBDIR = "reports"

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
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; font-size: 14px; -webkit-font-smoothing: antialiased; }
  .container { max-width: 1160px; margin: 0 auto; padding: 1.5em 1.2em; }
  h1 { font-size: 1.3em; font-weight: 700; color: var(--heading); margin-bottom: 0.1em; }
  .subtitle { color: var(--text-light); font-size: 0.8em; margin-bottom: 1em; }

  /* ── Tab Navigation ── */
  .tab-nav { display: flex; gap: 0; border-bottom: 2px solid var(--border); margin-bottom: 1.2em; }
  .tab-btn { padding: 0.5em 1.2em; border: none; background: none; color: var(--text-light); cursor: pointer; font-size: 0.9em; font-family: inherit; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.15s; }
  .tab-btn:hover { color: var(--heading); }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
  .tab-badge { display: inline-block; background: var(--accent); color: #fff; border-radius: 10px; padding: 0 6px; font-size: 0.7em; margin-left: 4px; min-width: 18px; text-align: center; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  .ret-hidden { display: none; }
  .return-note { font-size: 0.72em; color: var(--text-light); margin-top: 0.4em; }
  .return-summary-bar { display: flex; gap: 1em; flex-wrap: wrap; align-items: center; margin: 0.8em 0 1.1em; padding: 0.65em 0.8em; background: var(--accent-light); border-radius: 6px; font-size: 0.85em; }
  .return-summary-bar span { white-space: nowrap; }
  .return-summary-bar .return-total { margin-left: auto; font-size: 1.1em; }
  .return-section-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1em; align-items: start; }
  .return-metric { font-variant-numeric: tabular-nums; }


  /* ── KPI Grid ── */
  .kpi-grid { display: flex; gap: 0.6em; margin-bottom: 1em; flex-wrap: wrap; }
  .kpi-card { flex: 1; min-width: 100px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; padding: 0.7em 0.8em; text-align: center; transition: all 0.15s; }
  .kpi-card.clickable { cursor: pointer; }
  .kpi-card.clickable:hover { border-color: var(--accent); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .kpi-card.clickable:active { transform: scale(0.97); }
  .kpi-card .kpi-num { font-size: 1.5em; font-weight: 700; color: var(--heading); }
  .kpi-card .kpi-label { font-size: 0.65em; color: var(--text-light); margin-top: 0.2em; letter-spacing: 0.04em; text-transform: uppercase; }
  .kpi-card.kpi-accent { border: 2px solid var(--accent); }

  /* ── Filters (in holdings tab) ── */
  .filters { display: flex; gap: 0.4em; margin-bottom: 1em; flex-wrap: wrap; }
  .filters button { padding: 0.3em 0.7em; border: 1px solid var(--border); border-radius: 4px; background: var(--bg); color: var(--text-light); cursor: pointer; font-size: 0.78em; font-family: inherit; transition: all 0.15s; }
  .filters button:hover { border-color: var(--accent); color: var(--accent); }
  .filters button.active { background: var(--accent); color: #fff; border-color: var(--accent); }

  /* ── Table ── */
  .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 6px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.82em; }
  thead { border-bottom: 2px solid var(--heading); position: sticky; top: 0; background: var(--bg); }
  th { padding: 8px 10px 6px; text-align: left; font-weight: 600; color: var(--heading); white-space: nowrap; font-size: 0.85em; letter-spacing: 0.03em; cursor: pointer; user-select: none; }
  th:hover { color: var(--accent); }
  td { padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:hover td { background: var(--accent-light); }
  tr.row-avoid td { opacity: 0.55; }
  tr.row-broken td { opacity: 0.4; }
  tr.row-stale td { background: var(--yellow-bg); }
  tr.buy-highlight td { background: var(--green-bg) !important; }
  tr.buy-highlight:hover td { background: #d4e8d6 !important; }

  .code-cell { font-weight: 600; white-space: nowrap; font-size: 0.9em; }
  .holding-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 3px; }
  .dot-holding { background: var(--green); } .dot-watching { background: var(--yellow); } .dot-none { background: var(--border); }
  .gg-good { color: var(--green); font-weight: 600; } .gg-bad { color: var(--red); }
  .upside-pos { color: var(--green); } .upside-neg { color: var(--red); }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 0.75em; font-weight: 700; letter-spacing: 0.04em; white-space: nowrap; }
  .badge-strong-buy { background: #1b5e33; color: #fff; } .badge-buy { background: var(--green); color: #fff; }
  .badge-hold { background: #7a6a1b; color: #fff; } .badge-avoid { background: #5c1a1a; color: #fff; }
  .badge-broken { background: #888; color: #fff; }
  .detail-row { display: none; } .detail-row.open { display: table-row; }
  .detail-row td { padding: 0; border-bottom: 2px solid var(--border); }
  .detail-panel { padding: 0.8em 1em; background: var(--accent-light); font-size: 0.9em; }
  .dt-tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 0.6em; }
  .dt-tab { padding: 0.3em 0.8em; border: none; background: none; color: var(--text-light); cursor: pointer; font-size: 0.85em; font-family: inherit; border-bottom: 2px solid transparent; margin-bottom: -1px; }
  .dt-tab:hover { color: var(--heading); }
  .dt-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
  .dt-body { display: none; }
  .dt-body.active { display: block; }
  .detail-section h4 { font-size: 0.8em; letter-spacing: 0.04em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.3em; }
  .detail-section p { margin: 0.15em 0; color: var(--text); font-size: 0.95em; }
  .detail-section .val { color: var(--heading); font-weight: 600; }
  .detail-section ul { margin: 0.2em 0 0.2em 1.2em; font-size: 0.9em; }
  .detail-section li { margin: 0.1em 0; }
  .detail-section table { font-size: 0.9em; width: 100%; }
  .detail-section table th, .detail-section table td { padding: 3px 8px; border-bottom: 1px solid var(--border); }
  .clickable { cursor: pointer; }
  .days-ok { color: var(--text-light); font-size: 0.8em; } .days-warn { color: var(--yellow); font-weight: 600; } .days-old { color: var(--red); font-weight: 600; }

  /* ── Callout / Alerts ── */
  .callout { background: var(--accent-light); border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0; padding: 0.5em 0.8em; margin-bottom: 0.6em; font-size: 0.82em; }
  .callout-note { font-size: 0.8em; color: var(--text-light); margin-left: 0.8em; }
  .priority-item { margin-right: 0.6em; white-space: nowrap; }

  /* ── Asset Cards (overview tab) ── */
  .asset-overview { margin-bottom: 1em; }
  .asset-row { display: flex; gap: 0.8em; flex-wrap: wrap; }
  .asset-card { flex: 1; min-width: 160px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; padding: 0.7em 0.8em; }
  .asset-card.asset-primary { border: 2px solid var(--accent); }
  .asset-card.asset-wide { flex: 2; min-width: 280px; }
  .asset-label { font-size: 0.65em; color: var(--text-light); letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 0.2em; }
  .asset-value { font-size: 1.3em; font-weight: 700; color: var(--heading); }
  .asset-sub { font-size: 0.72em; color: var(--text-light); margin-top: 0.2em; }
  .sparkline { margin-top: 0.4em; width: 100%; height: 32px; }

  /* ── Section (collapsible) ── */
  .section-header { display: flex; justify-content: space-between; align-items: center; padding: 0.5em 0.8em; border-bottom: 1px solid var(--border); margin-bottom: 0.3em; cursor: pointer; user-select: none; border-radius: 4px; }
  .section-header:hover { background: var(--accent-light); }
  .section-header h3 { font-size: 0.85em; font-weight: 600; color: var(--heading); margin:0; }
  .section-header .arrow { transition: transform 0.2s; color: var(--text-light); font-size:0.8em; }
  .section-header.open .arrow { transform: rotate(90deg); }
  .collapsible-body { display: none; }
  .collapsible-body.open { display: block; }

  /* ── Structure Tab: Charts ── */
  .chart-section { margin-bottom: 1.2em; }
  .chart-title { font-size: 0.8em; font-weight: 600; color: var(--heading); margin-bottom: 0.5em; letter-spacing: 0.04em; text-transform: uppercase; }
  .bar-row { display: flex; align-items: center; gap: 0.5em; margin-bottom: 0.3em; font-size: 0.78em; }
  .bar-label { min-width: 60px; text-align: right; color: var(--text); white-space: nowrap; }
  .bar-value { min-width: 45px; text-align: right; color: var(--text-light); font-size: 0.85em; }
  .bar-track { flex: 1; height: 14px; background: var(--accent-light); border-radius: 3px; overflow: hidden; }
  .bar-fill { display: inline-block; height: 100%; border-radius: 3px; transition: width 0.3s; }

  /* ── Donut Chart ── */
  .donut-wrap { display: flex; align-items: center; gap: 1em; flex-wrap: wrap; }
  .donut-legend { font-size: 0.78em; }
  .donut-legend span { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }

  /* ── Alert Cards ── */
  .alert-grid { display: flex; flex-direction: column; gap: 0.5em; }
  .alert-card { display: flex; align-items: center; gap: 0.8em; background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px; padding: 0.6em 0.8em; font-size: 0.82em; }
  .alert-card:hover { border-color: var(--accent); }
  .alert-icon { font-size: 1.2em; flex-shrink: 0; }
  .alert-info { flex: 1; min-width: 0; }
  .alert-info .stock-code { font-weight: 600; color: var(--heading); }
  .alert-info .stock-meta { color: var(--text-light); font-size: 0.85em; margin-top: 0.1em; }
  .alert-price { text-align: right; flex-shrink: 0; }
  .alert-price .target { font-weight: 600; color: var(--heading); }
  .alert-price .diff { font-size: 0.85em; }
  .alert-gg { text-align: right; flex-shrink: 0; font-weight: 600; font-size: 0.9em; min-width: 45px; }

  /* ── Detail Card (independent panel above table) ── */
  #stock-detail-card { margin-bottom: 1em; }
  .detail-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .detail-card-header { display: flex; justify-content: space-between; align-items: center; padding: 0.6em 1em; background: var(--accent-light); border-bottom: 1px solid var(--border); }
  .detail-close { padding: 0.2em 0.6em; border: 1px solid var(--border); border-radius: 4px; background: var(--bg); color: var(--text-light); cursor: pointer; font-size: 0.8em; font-family: inherit; }
  .detail-close:hover { border-color: var(--accent); color: var(--accent); }
  .detail-card-body { padding: 1em 1.2em; font-size: 0.95em; }

  /* ── Doc Library ── */
  .doc-lib { display: flex; gap: 1em; }
  .doc-stock-list { display: flex; flex-direction: column; gap: 0.3em; min-width: 100px; max-width: 140px; }
  .doc-stock-btn { display: block; padding: 0.4em 0.6em; border: 1px solid var(--border); border-radius: 4px; cursor: pointer; font-size: 0.75em; text-align: center; line-height: 1.3; }
  .doc-stock-btn:hover { border-color: var(--accent); }
  .doc-stock-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .doc-content { flex: 1; }
  .doc-cat { margin-bottom: 0.8em; font-size: 0.82em; }
  .doc-cat strong { color: var(--heading); }
  .doc-cat a { color: var(--accent); text-decoration: none; }
  .doc-cat a:hover { text-decoration: underline; }
  @media (max-width: 600px) { .doc-lib { flex-direction: column; } .doc-stock-list { flex-direction: row; flex-wrap: wrap; max-width: 100%; } }

  /* ── Responsive ── */
  @media (max-width: 600px) {
    .container { padding: 0.8em 0.6em; }
    .kpi-card { min-width: 70px; padding: 0.5em; }
    .kpi-card .kpi-num { font-size: 1.2em; }
    .tab-btn { padding: 0.4em 0.6em; font-size: 0.8em; }
  }
  @media print { .tab-nav, .filters, .kpi-grid { display: none; } .tab-panel { display: block !important; } .detail-row { display: table-row !important; } }
"""

_JS = r"""
document.addEventListener('DOMContentLoaded',function(){
  // ── Tab switching ──
  document.querySelectorAll('.tab-nav > .tab-btn[data-tab]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.tab-nav > .tab-btn[data-tab]').forEach(function(x){x.classList.remove('active')});
      b.classList.add('active');
      document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.remove('active')});
      var panel=document.getElementById('panel-'+b.dataset.tab);
      if(panel)panel.classList.add('active');
    });
  });
  // ── KPI card click → switch to holdings tab + apply filter ──
  document.querySelectorAll('.kpi-card[data-filter]').forEach(function(c){
    c.addEventListener('click',function(){
      var f=c.dataset.filter;
      // Switch to holdings tab
      document.querySelectorAll('.tab-nav > .tab-btn[data-tab]').forEach(function(x){x.classList.remove('active')});
      var htab=document.querySelector('.tab-nav > .tab-btn[data-tab="holdings"]');
      if(htab)htab.classList.add('active');
      document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.remove('active')});
      var hp=document.getElementById('panel-holdings');
      if(hp)hp.classList.add('active');
      // Apply filter
      if(f&&f!=='all'){
        document.querySelectorAll('#panel-holdings .filters button').forEach(function(x){x.classList.remove('active')});
        var fb=document.querySelector('#panel-holdings .filters button[data-filter="'+f+'"]');
        if(fb)fb.classList.add('active');
      }
      applyFilter(f||'all');
      // Scroll to table
      var tw=document.querySelector('#panel-holdings .table-wrap');
      if(tw)tw.scrollIntoView({behavior:'smooth',block:'start'});
    });
  });
  // ── Filter function ──
  function applyFilter(f){
    document.querySelectorAll('#panel-holdings tbody tr.data-row').forEach(function(r){
      if(f==='Strong Buy'||f==='Buy'||f==='Hold'||f==='Avoid'){
        r.style.display=r.dataset.decision===f?'':'none';
      }else if(f==='holding'){
        r.style.display=r.dataset.holding==='true'?'':'none';
      }else if(f==='watching'){
        r.style.display=r.dataset.watching==='true'?'':'none';
      }else{
        r.style.display='';
      }
    });
  }
  // ── Holdings tab filter buttons ──
  document.querySelectorAll('#panel-holdings .filters button').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('#panel-holdings .filters button').forEach(function(x){x.classList.remove('active')});
      b.classList.add('active');
      applyFilter(b.dataset.filter);
    });
  });
  // ── Table sorting ──
  var rows=Array.from(document.querySelectorAll('#panel-holdings tbody tr.data-row'));
  var sortCol=-1,sortAsc=true;
  document.querySelectorAll('#panel-holdings th[data-sort]').forEach(function(th){
    th.addEventListener('click',function(){
      var col=th.dataset.sort;
      if(sortCol===col){sortAsc=!sortAsc}else{sortCol=col;sortAsc=true}
      document.querySelectorAll('#panel-holdings th').forEach(function(h){h.classList.remove('sorted')});
      th.classList.add('sorted');
      rows.sort(function(a,b){var va=a.dataset[col]||'',vb=b.dataset[col]||'',na=parseFloat(va),nb=parseFloat(vb);
        if(!isNaN(na)&&!isNaN(nb))return sortAsc?na-nb:nb-na;return sortAsc?va.localeCompare(vb):vb.localeCompare(va);});
      var tbody=document.querySelector('#panel-holdings tbody');
      rows.forEach(function(r){tbody.appendChild(r);tbody.appendChild(r.nextElementSibling);});
    });
  });
  // ── Detail mini-tab switching ──
  document.addEventListener('click',function(e){
    if(e.target.classList.contains('dt-tab')){
      var prefix=e.target.dataset.dt, idx=e.target.dataset.dtIdx;
      document.querySelectorAll('.dt-tab[data-dt="'+prefix+'"]').forEach(function(b){b.classList.remove('active')});
      e.target.classList.add('active');
      document.querySelectorAll('.dt-body[data-dt="'+prefix+'"]').forEach(function(b){b.classList.remove('active')});
      var body=document.querySelector('.dt-body[data-dt="'+prefix+'"][data-dt-idx="'+idx+'"]');
      if(body)body.classList.add('active');
    }
  });
  // ── Detail close button (delegated) ──
  document.addEventListener('click',function(e){
    if(e.target.classList.contains('detail-close')){
      document.getElementById('stock-detail-card').style.display='none';
    }
  });
  // ── Row click → show detail card ──
  document.querySelectorAll('#panel-holdings tr.data-row').forEach(function(tr){
    tr.addEventListener('click',function(e){
      if(e.target.tagName==='A')return;
      var card=document.getElementById('stock-detail-card');
      var code=tr.querySelector('.code-cell').textContent.replace(/[🔔●○ ]/g,'').trim();
      var name=tr.querySelector('.name-cell').textContent.trim();
      var decision=tr.dataset.decision;
      var detailRow=tr.nextElementSibling;
      var detailHTML='';
      if(detailRow&&detailRow.classList.contains('detail-row')){
        detailHTML=detailRow.querySelector('.detail-panel').innerHTML;
      }
      var badge='';
      if(decision==='Strong Buy')badge='<span class=\"badge badge-strong-buy\">Strong Buy</span>';
      else if(decision==='Buy')badge='<span class=\"badge badge-buy\">Buy</span>';
      else if(decision==='Hold')badge='<span class=\"badge badge-hold\">Hold</span>';
      else if(decision&&decision.indexOf('Avoid')>=0)badge='<span class=\"badge badge-avoid\">'+decision+'</span>';
      else if(decision&&decision.indexOf('待')>=0)badge='<span class=\"badge badge-broken\">'+decision+'</span>';
      card.innerHTML='<div class=\"detail-card\"><div class=\"detail-card-header\"><div><strong>'+code+'</strong> '+name+' '+badge+'</div><button class=\"detail-close\">✕ 关闭</button></div><div class=\"detail-card-body\">'+detailHTML+'</div></div>';
      card.style.display='block';
      card.scrollIntoView({behavior:'smooth',block:'start'});
    });
  });
  // ── Collapsible sections ──
  document.querySelectorAll('.section-header[data-toggle]').forEach(function(h){
    h.addEventListener('click',function(){
      h.classList.toggle('open');
      var body=document.getElementById(h.dataset.toggle);
      if(body)body.classList.toggle('open');
    });
  });
  // ── Sparkline bars ──
  document.querySelectorAll('.sparkline-bar').forEach(function(el){
    var vals=el.dataset.prices.split(',').map(Number);
    if(vals.length<2)return;
    var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals)||mn+1;
    var w=60,h=12,html='';
    vals.forEach(function(v,i){
      var x=(i/(vals.length-1))*w,barH=Math.max(1,((v-mn)/(mx-mn))*h);
      html+='<rect x="'+x+'" y="'+(h-barH)+'" width="1" height="'+barH+'" fill="'+(v>=vals[0]?'var(--green)':'var(--red)')+'"/>';
    });
    el.innerHTML='<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none" style="width:60px;height:12px">'+html+'</svg>';
  });
  // ── Doc library ──
  document.querySelectorAll('.doc-stock-btn').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.doc-stock-btn').forEach(function(x){x.classList.remove('active')});
      b.classList.add('active');
      document.querySelectorAll('.doc-panel').forEach(function(p){p.style.display='none'});
      var panel=document.getElementById('doc-'+b.dataset.doc);
      if(panel)panel.style.display='block';
    });
  });
  // Returns / structure sub-tab switching
  window.showStructTab=function(t,btn){
    document.querySelectorAll('#panel-structure [id^=struct-]').forEach(function(e){e.style.display='none'});
    var el=document.getElementById('struct-'+t); if(el)el.style.display='block';
    document.querySelectorAll('#panel-structure .tab-btn').forEach(function(b){b.classList.remove('active')});
    if(btn)btn.classList.add('active');
  };
  window.showRetTab=function(t,btn){
    try{
      var ids=['ret-overview','ret-pnl','ret-div'];
      for(var i=0;i<ids.length;i++){
        var el=document.getElementById(ids[i]);
        if(el)el.classList.add('ret-hidden');
      }
      var target=document.getElementById('ret-'+t);
      if(target)target.classList.remove('ret-hidden');
      var btns=document.querySelectorAll('#panel-returns > .tab-nav > .tab-btn');
      for(var j=0;j<btns.length;j++)btns[j].classList.remove('active');
      if(btn)btn.classList.add('active');
    }catch(e){}
  };
  window.showDivYear=function(y,btn){
    try{
      document.querySelectorAll('.div-year-panel').forEach(function(p){p.classList.add('ret-hidden')});
      var target=document.getElementById('div-year-'+y);
      if(target)target.classList.remove('ret-hidden');
      document.querySelectorAll('.div-year-btn').forEach(function(b){b.classList.remove('active')});
      if(btn)btn.classList.add('active');
    }catch(e){}
  };
  var firstDoc=document.querySelector('.doc-stock-btn');
  if(firstDoc)firstDoc.click();
});
"""


def _fmt(f, default="--"):
    return default if f is None else f


_OBS_CN = {
    "np_decline": "净利润下滑",
    "low_pb_roe": "低PB低ROE",
    "business_disrupted": "商业模式受冲击",
    "management_expropriation": "管理层侵占风险",
    "margin_irreversible": "利润率不可逆下滑",
    "price_new_lows": "股价持续新低",
    "no_value_convergence": "价值不收敛",
    "major_shareholder_sells_or_audit_change": "大股东减持或审计变更",
    "fy2026_h1_margin_lt_13pct": "FY2026H1利润率<13%",
    "2yr_no_value_convergence": "2年内无价值收敛",
}

def _translate_obs(text: str) -> str:
    """翻译观察信号中的英文术语为中文。"""
    for en, cn in _OBS_CN.items():
        text = text.replace(en, cn)
    # Clean prefixes: ? → 待确认: , ⚠️ → 警告:
    text = text.replace("⚠️", "⚠").replace("?", "").replace(",", " · ").replace("  ", " ")
    return text.strip(" ·")


def _build_action_summary(r: dict) -> str:
    """操作建议摘要：买入价/现价/仓位/止损/GG 一目了然。"""
    from niangao.db import get_investment_plan
    plan = get_investment_plan(r.get("ts_code", ""))
    parts = []
    bp = r.get("buy_price") or 0
    lp = r.get("live_price") or r.get("price") or 0
    if bp > 0 and lp > 0 and lp <= bp:
        parts.append(f"💰 可买 (现价{lp:.2f}≤买入价{bp:.2f})")
    elif bp > 0 and lp > 0:
        gap = (bp / lp - 1) * 100
        parts.append(f"买入价 {bp:.2f} (距现价{gap:+.0f}%)")
    gg = r.get("gg_base") or r.get("gg_discounted")
    if gg:
        parts.append(f"GG={gg:.1f}%")
    pp = r.get("pos_pct")
    if pp:
        parts.append(f"建议仓位 {pp:.1f}%")
    if plan and plan.get("stop_loss_hkd"):
        parts.append(f"止损 {plan['stop_loss_hkd']:.2f} HKD")
    if plan and plan.get("observation_signals"):
        obs = _translate_obs(plan["observation_signals"])
        if len(obs) > 60:
            obs = obs[:60] + "..."
        parts.append(f"观察: {obs}")
    return " · ".join(parts) if parts else ""


def _build_detail(r: dict) -> str:
    """个股详情面板。排序：定性摘要 → 投资计划 → GG/估值 → 历史对比 → 报告链接。"""
    from niangao.db import get_investment_plan, get_analysis_history as _gah, _OUTPUT_DIR
    import json as _json
    import os as _os

    sections = []
    ts = r.get("ts_code", "")
    plan = get_investment_plan(ts) if ts else None

    # ── 1. 定性摘要 ──
    if plan:
        for icon, label, key in [("🏢", "商业模式", "business_model"), ("🔄", "近期变化", "recent_changes"), ("⚡", "核心矛盾", "core_tension")]:
            v = plan.get(key)
            if v:
                sections.append(f'<div data-sec="0" class="detail-section"><h4>{icon} {label}</h4><p>{v}</p></div>')

    # ── 2. 投资计划 ──
    if plan:
        bb = []
        if plan.get("batch_buy_json"):
            try: bb = _json.loads(plan["batch_buy_json"])
            except Exception: pass
        # Use analysis GG data (not stale core_thesis)
        gg_val = r.get("gg_base") or r.get("gg_discounted")
        ii_val = r.get("ii")
        ph = '<div class="detail-section"><h4>📋 投资计划</h4>'
        # Conviction + GG summary from analysis
        conviction = plan.get("conviction", "")
        pos_p = plan.get("position_pct", "")
        gg_str = f'GG={gg_val:.1f}% vs II={ii_val:.1f}%' if gg_val and ii_val else ''
        thesis = plan.get("core_thesis", "")
        # Strip old GG data from thesis if present (it's now shown separately)
        thesis_clean = _os.path.basename(thesis) if thesis else ""  # keep only if short
        if thesis and len(thesis) < 200:
            thesis_clean = thesis
        else:
            thesis_clean = ""
        ph += f'<p>信心: <span class="val">{conviction}</span> | 仓位: <span class="val">{pos_p}%</span> | <span class="val">{gg_str}</span>'
        if thesis_clean:
            ph += f' | {thesis_clean[:80]}'
        ph += '</p>'
        if bb:
            ph += '<p>分批买入:</p><ul>'
            for b in bb[:4]:
                ph += f'<li>{b["star"]}★ {b["price_hkd"]:.2f} HKD ({b["upside_pct"]:+.0f}%) → {b["action"]}</li>'
            ph += '</ul>'
        if plan.get("stop_loss_hkd"):
            ph += f'<p>🛑 止损: <span class="val" style="color:var(--red)">{plan["stop_loss_hkd"]:.2f} HKD</span>'
            if plan.get("stop_loss_conditions"):
                conds = _translate_obs(plan["stop_loss_conditions"])
                ph += f' | {conds}'
            ph += '</p>'
        if plan.get("observation_signals"):
            obs = plan["observation_signals"]
            obs = _translate_obs(obs)
            ph += f'<p>🔍 观察: {obs}</p>'
        ph += '</div>'
        sections.append(ph.replace('<div class="detail-section">', '<div data-sec="1" class="detail-section">', 1))

    # ── 3. GG / 估值 ──
    gg_disc = _fmt(r.get("gg_discounted")); gg_fcfe = _fmt(r.get("gg_fcfe"))
    aa_3y = f"{r['aa_3y']:.1f}M" if r.get("aa_3y") else "--"; ii = _fmt(r.get("ii"))
    p_base_hkd = f"{r['p_base_hkd']:.2f}" if r.get("p_base_hkd") else "--"
    p_fcfe_hkd = f"{r['p_fcfe_hkd']:.2f}" if r.get("p_fcfe_hkd") else "--"
    upside = f"{r['upside_pct']:+.0f}%" if r.get("upside_pct") is not None else "--"
    pos = f"{r['pos_pct']:.1f}%" if r.get("pos_pct") else "--"

    gg_base_val = _fmt(r.get("gg_base"))
    buy_p = _fmt(r.get("buy_price"), "--")
    sections.append(f'<div data-sec="2" class="detail-section"><h4>📊 GG 推导</h4><p>GG: <span class="val">{gg_base_val}%</span> | GG(折价后): <span class="val">{gg_disc}%</span> | GG(FCFE): <span class="val">{gg_fcfe}%</span> | II: <span class="val">{ii}%</span></p><p>AA₃y: <span class="val">{aa_3y}</span> | 买入价: <span class="val">{buy_p}</span> HKD</p></div>')
    sections.append(f'<div data-sec="2" class="detail-section"><h4>💰 估值</h4><p>P_base: <span class="val">{p_base_hkd}</span> HKD | P_FCFE: <span class="val">{p_fcfe_hkd}</span> HKD | 上涨: <span class="val">{upside}</span> | 仓位: <span class="val">{pos}</span></p><p>价值陷阱: {"⚠️是" if r.get("vt_excluded") else "否"} | 外推: <span class="val">{r.get("extrap_overall") or "--"}</span></p></div>')

    # ── 4. 历史对比 ──
    hist = _gah(ts) if ts else []
    if len(hist) >= 2:
        latest = hist[0]; prev = hist[1]
        hh = '<div data-sec="3" class="detail-section"><h4>📜 历史对比</h4><table style="font-size:0.8em"><tr><th></th><th>本次</th><th>上次</th><th>变化</th></tr>'
        for label, key, fmt in [("GG", "gg_base", "%.1f%%"), ("决策", "decision", "%s"), ("仓位", "pos_pct", "%.1f%%")]:
            cur = latest.get(key); prv = prev.get(key)
            cur_s = fmt % cur if cur is not None else "--"; prv_s = fmt % prv if prv is not None else "--"
            if isinstance(cur, (int, float)) and isinstance(prv, (int, float)) and prv != 0:
                chg = cur - prv; arrow = "↑" if chg > 0 else "↓" if chg < 0 else "→"
                chg_s = f'<span class="{"gg-good" if chg>0 else "gg-bad"}">{arrow}{abs(chg):.1f}pp</span>'
            else: chg_s = "-"
            hh += f'<tr><td>{label}</td><td class="val">{cur_s}</td><td>{prv_s}</td><td>{chg_s}</td></tr>'
        hh += f'</table><p style="margin-top:0.3em">共 {len(hist)} 次分析</p></div>'
        sections.append(hh)

    # ── 5. 报告（带日期） ──
    hist_reports = _gah(ts) if ts else []
    all_reports = []
    # Current analysis report
    cur_report = r.get("report_html") or ""
    cur_date = (r.get("analyzed_at") or "")[:10]
    if cur_report:
        all_reports.append((cur_date, cur_report, "本次"))
    # Historical reports
    for h in hist_reports[1:]:  # skip latest (already added)
        h_date = (h.get("analyzed_at") or "")[:10]
        h_dir = h.get("stock_dir") or ""
        if h_dir and ts:
            code_s = ts.split(".")[0]
            for pat in (f"{ts.replace('.','_')}_分析报告_{_REPORT_VERSION}.html", f"{code_s}_分析报告_{_REPORT_VERSION}.html"):
                # v13+: reports/ subdir
                cand = _os.path.join(_OUTPUT_DIR, h_dir, _REPORTS_SUBDIR, pat)
                if _os.path.exists(cand):
                    all_reports.append((h_date, cand, f"{h_date}"))
                    break
                # legacy v12 fallback at root
                cand_v12 = _os.path.join(_OUTPUT_DIR, h_dir, pat.replace(f"_{_REPORT_VERSION}.html", "_v12.html"))
                if _os.path.exists(cand_v12):
                    all_reports.append((h_date, cand_v12, f"{h_date}"))
                    break
    if all_reports:
        rp = '<div data-sec="4" class="detail-section"><h4>📄 报告</h4>'
        for date, path, label in all_reports[:5]:
            rp += f'<p>📄 {date} <a href="file://{_OUTPUT_DIR}/{path}" target="_blank">{label}</a></p>'
        rp += '</div>'
        sections.append(rp)

    # Build detail panel with mini-tabs
    detail_id = f'detail-{r.get("ts_code","x").replace(".","-")}'
    tab_headers = []
    tab_bodies = []
    # Only show history tab if ≥2 records
    has_history = len(_gah(ts) if ts else []) >= 2
    tabs = [("定性", "🏢"), ("计划", "📋"), ("GG估值", "📊")]
    if has_history:
        tabs.append(("历史", "📜"))
    for i, (label, icon) in enumerate(tabs):
        active = "active" if i == 0 else ""
        tab_headers.append(f'<button class="dt-tab {active}" data-dt="{detail_id}" data-dt-idx="{i}">{icon} {label}</button>')
        # Filter sections by type
        body_parts = []
        for s in sections:
            if s.startswith(f'<div data-sec="{i}"'):
                body_parts.append(s)
        if not body_parts:
            body_parts.append('<div class="detail-section"><p style="color:var(--text-light)">暂无数据</p></div>')
        tab_bodies.append(f'<div class="dt-body {active}" data-dt="{detail_id}" data-dt-idx="{i}">{"".join(body_parts)}</div>')

    return f'''<div class="detail-panel">
  <div style="padding:0.4em 0;font-size:0.85em;color:var(--accent);border-bottom:1px solid var(--border);margin-bottom:0.4em">{_build_action_summary(r)}</div>
  <div class="dt-tabs">{"".join(tab_headers)}</div>
  {"".join(tab_bodies)}
</div>'''


def _build_doc_library(rows: list[dict]) -> str:
    """预渲染所有已分析股票的资料库 HTML。每个文件显示修改日期，按类别组织。"""
    from niangao.db import get_db, _OUTPUT_DIR
    import os as _os_lib
    from datetime import datetime as _dt
    db = get_db()
    stocks = db.execute(
        "SELECT ts_code, stock_dir, name FROM analysis WHERE stock_dir IS NOT NULL AND stock_dir != ''"
    ).fetchall()
    db.close()

    if not stocks:
        return '<p style="color:var(--text-light);text-align:center;">暂无已分析股票</p>'

    # Category definitions: (label, file_matcher_fn)
    _ANALYSIS_JSON = {"audit.json","mda.json","risks.json","governance.json",
        "moat_assessment.json","earnings_quality.json","financial_trends.json",
        "data_discount.json","capex_classification.json","governance_tension.json",
        "industry_context.json","segments.json"}

    all_html = ""
    stock_buttons = ""

    for s in stocks:
        ts_code = s["ts_code"]
        name = s["name"] or ts_code
        stock_dir = s["stock_dir"]
        full_dir = _os_lib.path.join(_OUTPUT_DIR, stock_dir)
        sid = ts_code.replace(".", "-")
        stock_buttons += f'<span class="doc-stock-btn" data-doc="{sid}">{name[:8]}<br><small>{ts_code}</small></span>'

        sections = ""
        if _os_lib.path.isdir(full_dir):
            files_list = sorted(_os_lib.listdir(full_dir))

            def _fdate(fn):
                try:
                    mt = _os_lib.path.getmtime(_os_lib.path.join(full_dir, fn))
                    return _dt.fromtimestamp(mt).strftime("%m-%d")
                except Exception:
                    return ""

            def _fitem(fn, icon):
                d = _fdate(fn)
                rel = f"{stock_dir}/{fn}"
                return f'<span style="display:inline-block;margin:2px 8px 2px 0;font-size:0.8em"><a href="file://{_OUTPUT_DIR}/{rel}" target="_blank">{icon}</a> <small style="color:var(--text-light)">{d}</small> <a href="file://{_OUTPUT_DIR}/{rel}" target="_blank">{fn}</a></span>'

            # v13+: scan reports/ subdir for HTML; legacy v12 at root
            _rep_subdir = _os_lib.path.join(full_dir, _REPORTS_SUBDIR)
            _rep_files = [
                f"{_REPORTS_SUBDIR}/{f}"
                for f in (sorted(_os_lib.listdir(_rep_subdir)) if _os_lib.path.isdir(_rep_subdir) else [])
                if '分析报告' in f and f.endswith('.html')
            ]
            _legacy_rep = [f for f in files_list if '分析报告_v12' in f and f.endswith('.html')]

            categories = [
                ("📄 分析报告", _rep_files + _legacy_rep, "🌐"),
                ("📊 核心数据", [f for f in ["compute_bundle.json"] if f in files_list], "📊"),
                ("📋 分析合约", [f for f in ["analysis_contract.json"] if f in files_list], "📋"),
                ("🔍 深度分析", sorted([f for f in files_list if f in _ANALYSIS_JSON]), "📊"),
                ("📕 年报 PDF", sorted([f for f in files_list if '_年报.pdf' in f]), "📕"),
            ]
            for cat_name, cat_files, icon in categories:
                if cat_files:
                    items = "".join(_fitem(f, icon) for f in cat_files)
                    sections += f'<div class="doc-cat"><strong>{cat_name}</strong><br>{items}</div>'

        if not sections:
            sections = '<p style="color:var(--text-light)">暂无文档</p>'
        all_html += f'<div class="doc-panel" id="doc-{sid}" style="display:none"><h3>{name} ({ts_code})</h3>{sections}</div>'

    return f'''<div class="doc-lib">
<div class="doc-stock-list">{stock_buttons}</div>
<div class="doc-content">{all_html}</div>
</div>'''


def _load_rows() -> list[dict[str, Any]]:
    """加载分析+watchlist+未分析持仓，补全计算字段。"""
    # Sync invest
    try:
        n = sync_watchlist()
        if n > 0: print(f"  🔄 invest同步: {n} 只")
    except Exception: pass

    # Quotes
    try:
        from niangao.quotes import fetch_all_prices
        fp = fetch_all_prices()
        print(f"  📡 实时行情: {fp.get('updated', 0)}/{fp.get('total', 0)} 只")
    except Exception as e: pass

    # Auto-refresh: re-import if compute_bundle.json is newer than DB
    try:
        from niangao.db import extract_from_bundle, upsert_analysis, _OUTPUT_DIR as _OD
        import os as _os_refresh
        check_db = get_db()
        stale = check_db.execute(
            "SELECT ts_code, stock_dir, analyzed_at FROM analysis WHERE stock_dir IS NOT NULL AND stock_dir != ''"
        ).fetchall()
        check_db.close()
        refreshed = 0
        for sr in stale:
            bundle = _os_refresh.path.join(_OD, sr["stock_dir"], "compute_bundle.json")
            if _os_refresh.path.exists(bundle):
                bundle_mtime = _os_refresh.path.getmtime(bundle)
                db_at = sr["analyzed_at"] or ""
                if db_at:
                    try:
                        db_ts = datetime.fromisoformat(db_at.replace("Z","+00:00").replace(" ","T")).timestamp()
                        if bundle_mtime > db_ts + 60:
                            data = extract_from_bundle(bundle, "", sr["stock_dir"])
                            if data.get("gg_base"):
                                upsert_analysis(data)
                                refreshed += 1
                    except Exception:
                        pass
        if refreshed:
            print(f"  🔄 自动刷新 {refreshed} 只分析数据")
    except Exception:
        pass

    db = get_db()
    rows = [dict(r) for r in db.execute("""
        SELECT a.*, w.invest_code, w.invest_status, w.current_hold, w.avg_cost AS inv_avg_cost,
               w.hold_limit_pct AS inv_hold_limit_pct, w.annual_div_per_share AS inv_dps,
               w.invest_logic AS inv_logic, w.my_valuation AS inv_valuation, w.live_price,
               w.name AS wl_name FROM analysis a LEFT JOIN watchlist w ON a.ts_code=w.ts_code
        ORDER BY a.gg_discounted DESC
    """).fetchall()]

    # Unanalyzed holdings
    unanalyzed = get_unanalyzed_holdings()
    analyzed_codes = {r["ts_code"] for r in rows}
    db.close()

    now = datetime.now()
    for r in rows:
        r["market"] = r.get("market", "?"); r["gg_val"] = r.get("gg_discounted") or r.get("gg_base")
        r["gg_ok"] = bool(r.get("gg_ok")); r["inv_holding"] = r.get("current_hold", 0) or 0
        r["inv_status"] = r.get("invest_status", "") or ""; r["_row_type"] = "analyzed"
        at = r.get("analyzed_at", "")
        try:
            ad = datetime.fromisoformat(at.replace("Z", "+00:00").replace(" ", "T"))
            r["_days_ago"] = (now - ad.replace(tzinfo=None)).days
        except Exception: r["_days_ago"] = 999
        r["_stale"] = r["_days_ago"] > 30

    for u in unanalyzed:
        u = dict(u); u.update({"gg_val": None, "gg_ok": False, "decision": "⚠️待分析", "inv_avg_cost": u.get("avg_cost", 0),
            "market": u.get("market", "?"), "inv_holding": u.get("current_hold", 0) or 0,
            "_row_type": "unanalyzed", "analyzed_at": ""})
        if u["ts_code"] not in analyzed_codes: rows.append(u)

    return rows


def generate_dashboard(rows: list | None = None, assets: dict | None = None) -> str:
    """生成 HTML 仪表盘，返回文件路径。rows=None 时自动加载。"""
    if rows is None:
        rows = _load_rows()
        print(f"   {len(rows)} 条记录")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Asset overview
    if assets is None:
        assets = load_asset_overview()
    asset_html = _render_asset_html(assets)

    # Phase 3.2: inject price sparklines into rows
    sparklines = assets.get("price_sparklines", {})
    for r in rows:
        spark = sparklines.get(r.get("invest_code", ""))
        if spark:
            r["_sparkline"] = ",".join(f"{v:.2f}" for v in spark)

    # Portfolio GG
    pf = compute_portfolio_gg(rows)
    pf_html = ""
    if pf["value"] > 0:
        gg_color = 'var(--green)' if pf["gg"] > 7 else "var(--heading)"
        pf_label_color = 'var(--green)' if pf["gg"] > 7 else ('var(--red)' if pf["gg"] < 4 else "var(--heading)")
        pf_html = f"""<div class="asset-overview">
  <div class="asset-row">
    <div class="asset-card asset-primary">
      <div class="asset-label">🏮 组合穿透GG</div>
      <div class="asset-value" style="color:{pf_label_color}">{pf['gg']:.1f}%</div>
      <div class="asset-sub">vs Rf超额 {pf['premium']:+.1f}%</div>
    </div>
    <div class="asset-card">
      <div class="asset-label">有分析持仓</div>
      <div class="asset-value">{pf['count']} 只</div>
      <div class="asset-sub">覆盖 {pf['value']/1e4:.0f} 万市值</div>
    </div>
  </div>
</div>"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass

    # Stats
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
    stale_count = sum(1 for r in rows if r.get("_stale") and r.get("_row_type") == "analyzed")

    # Callouts
    unanalyzed_rows = [r for r in rows if r.get("_row_type") == "unanalyzed"]
    priority_html = ""
    if unanalyzed_rows:
        items = [f'<span class="priority-item">🔔 {u["ts_code"]} {(u.get("wl_name") or u.get("name") or "")[:6]} ({(u.get("current_hold",0)):,}股)</span>' for u in unanalyzed_rows[:5]]
        priority_html = f"""<div class="callout"><strong>📋 持仓待分析 TOP{min(5,len(unanalyzed_rows))}</strong> — {' · '.join(items)}<span class="callout-note">共 {len(unanalyzed_rows)} 只</span></div>"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass

    suggestions = get_rerun_suggestions()[:8]
    suggest_html = ""
    if suggestions:
        items = [f'<span class="priority-item">📌 {s["ts_code"]} {(s.get("name") or "")[:6]} <small>({s["reason"]})</small></span>' for s in suggestions[:5]]
        suggest_html = f"""<div class="callout"><strong>🔄 建议重分析 TOP{len(suggestions)}</strong> — {' · '.join(items)}<br>{' · '.join([f'<span class="priority-item">📌 {s["ts_code"]} {(s.get("name") or "")[:6]}</span>' for s in suggestions[5:]]) if len(suggestions)>5 else ''}<div class="callout-note"><code>python scripts/batch_analyze.py --stale</code></div></div>"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass

    bt_results = run_backtest(rows)
    bt_html = ""
    if bt_results:
        hit_count = sum(1 for r in bt_results if r["hit"])
        avg_score = sum(r["score"] for r in bt_results) / len(bt_results) if bt_results else 0
        items = [f'<span class="priority-item">{"✅" if r["hit"] else ("❌" if r["hit"] is False else "—")} {r["ts_code"]} {r["score"]}</span>' for r in bt_results[:6]]
        bt_html = f"""<div class="callout" style="border-left-color: var(--green);"><strong>📊 回测</strong> — {hit_count}/{len(bt_results)} 价格到位  均分{avg_score:.0f}<br>{' · '.join(items)}</div>"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass

    can_buy = [r for r in rows if r.get("_can_buy_now")]
    buy_now_html = ""
    if can_buy:
        items = [f'<span class="priority-item">💰 {r["ts_code"]} {r.get("wl_name",r.get("name",""))[:6]} 现价{r.get("live_price") or r.get("price"):.2f}&lt;买价{r.get("buy_price"):.2f}</span>' for r in can_buy]
        buy_now_html = f"""<div class="callout" style="border-left-color: var(--green); background: var(--green-bg);"><strong>💰 当前可买 ({len(can_buy)} 只)</strong><br>{' · '.join(items)}</div>"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass

    # Rebalance suggestions
    rebalance_html = ""
    try:
        tw = assets.get("total_wealth", 0)
        reb = compute_rebalance(rows, tw)
        if reb:
            items = []
            for rb in reb[:6]:
                items.append(f'{rb["action"][:2]} {rb["ts_code"]} 实际{rb["actual_pct"]:.1f}%→建议{rb["turtle_pct"]:.1f}%({rb["diff"]:+.1f}pp)')
            rebalance_html = f'<div class="callout" style="border-left-color: var(--yellow);"><strong>⚖️ 再平衡建议</strong><br>{" · ".join(items)}</div>'
    except Exception:
        pass

    # Table rows
    table_rows = []
    for r in rows:
        is_unanalyzed = r.get("_row_type") == "unanalyzed"
        status = r.get("invest_status", ""); hold_shares = r["inv_holding"]

        if hold_shares > 0: dot = '<span class="holding-dot dot-holding"></span>'
        elif status == "WATCHING": dot = '<span class="holding-dot dot-watching"></span>'
        else: dot = '<span class="holding-dot dot-none"></span>'
        code_disp = f'{dot}{r["ts_code"]}'
        if is_unanalyzed: code_disp += ' 🔔'
        # Phase 3.2: price sparkline in name cell
        spark = r.get("_sparkline", "")
        spark_html = f'<span class="sparkline-bar" data-prices="{spark}"></span>' if spark else ""
        hold_str = f'{hold_shares:,}股' if hold_shares > 0 else ("观察" if status == "WATCHING" else "-")

        gg_val = r["gg_val"]; gg_str = f'{gg_val:.1f}%' if gg_val else '-'
        gg_cls = "gg-good" if (gg_val and r.get("ii") and gg_val > r["ii"]) else ("gg-bad" if gg_val else "")
        ii_str = f'{r.get("ii", 0):.1f}%' if r.get("ii") else '-'
        date_str = (r.get("analyzed_at") or "")[:10]

        live_price = r.get("live_price") or 0; analysis_price = r.get("price") or 0
        display_price = live_price if live_price > 0 else analysis_price
        price_str = f'{display_price:.2f}' if display_price else '-'
        if live_price > 0 and analysis_price > 0 and abs(live_price / analysis_price - 1) > 0.2:
            price_str += f' <span class="days-old">({(live_price/analysis_price-1)*100:+.0f}%)</span>'

        buy_upside = r.get("buy_upside"); buy_price_raw = r.get("buy_price") or 0
        p_base = r.get("p_base_hkd") or 0; p_fcfe = r.get("p_fcfe_hkd") or 0
        price_cur = live_price or analysis_price
        if buy_price_raw > 0 and price_cur > 0 and buy_price_raw < price_cur * 0.05:
            fallback = p_fcfe or p_base
            buy_str = f'<span title="DDM失效">{fallback:.2f}</span>' if fallback > 0 else 'DDM失效'
            buy_price_raw = fallback if fallback > 0 else 0
        else:
            buy_str = f'{buy_price_raw:.2f}' if buy_price_raw > 0 else "-"
        if buy_price_raw > 0 and price_cur > 0: buy_upside = (buy_price_raw / price_cur - 1) * 100
        if buy_upside is not None:
            up_str = f'{buy_upside:+.0f}%'; up_cls = "upside-pos" if buy_upside > 0 else "upside-neg"
        else: up_str, up_cls = "-", ""

        r["_can_buy_now"] = (live_price > 0 and buy_price_raw > 0 and live_price <= buy_price_raw
                             and r.get("decision") in ("Strong Buy", "Buy"))

        decision = r.get("decision", "?")
        is_stale = r.get("_stale", False)
        if is_unanalyzed: row_cls, badge_cls = "row-broken", "badge-broken"
        elif not r["gg_ok"]: row_cls, badge_cls = "row-broken", "badge-broken"
        elif is_stale and decision in ("Strong Buy", "Buy"): row_cls, badge_cls = "row-stale", "badge-buy"
        elif decision == "Strong Buy": row_cls, badge_cls = "", "badge-strong-buy"
        elif decision == "Buy": row_cls, badge_cls = "", "badge-buy"
        elif decision == "Hold": row_cls, badge_cls = "", "badge-hold"
        else: row_cls, badge_cls = "row-avoid", "badge-avoid"

        pos_pct = r.get("pos_pct") or 0; pos_str = f'{pos_pct:.1f}%' if pos_pct else "-"
        manual_val = r.get("inv_valuation") or 0; turtle_val = r.get("p_base_hkd") or r.get("buy_price") or 0
        if manual_val > 0 and turtle_val > 0:
            dp = (turtle_val / manual_val - 1) * 100
            val_str = f'{manual_val:.2f} <span class="val">{turtle_val:.2f}</span> <span class="{"upside-pos" if dp>0 else "upside-neg"}">{"↑" if dp>0 else "↓"}{abs(dp):.0f}%</span>'
        elif manual_val > 0: val_str = f'{manual_val:.2f}'
        else: val_str = "-"

        days_ago = r.get("_days_ago", 0) if not is_unanalyzed else 0
        if is_unanalyzed: days_str, days_cls = "-", ""
        elif days_ago > 90: days_str, days_cls = f'{days_ago}d ⚠', "days-old"
        elif days_ago > 30: days_str, days_cls = f'{days_ago}d', "days-warn"
        else: days_str, days_cls = f'{days_ago}d', "days-ok"

        detail = "" if is_unanalyzed else _build_detail(r)
        name = (r.get("wl_name") or r.get("name") or "?")[:8]
        sgg = str(gg_val) if gg_val else "0"; su = str(buy_upside if buy_upside is not None else -999)

        # Phase 6: stop loss badge
        from niangao.db import get_investment_plan
        plan = get_investment_plan(r["ts_code"]) if not is_unanalyzed else None
        sl_str = f'{plan["stop_loss_hkd"]:.2f}' if plan and plan.get("stop_loss_hkd") else "-"
        plan_icon = " 💼" if plan else ""
        mth_badge = ""
        mth_en = r.get("mth_enabled") or 0
        mth_cy = r.get("mth_cycle") or 1
        if mth_en and mth_cy > 1:
            mth_badge = f'<span style="font-size:0.6em;background:var(--accent);color:#fff;border-radius:3px;padding:0 2px" title="MTH第{mth_cy}档">M{mth_cy}</span>'

        table_rows.append(f"""<tr class="data-row clickable {row_cls} {("buy-highlight" if r.get("_can_buy_now") else "")}" data-decision="{decision}" data-gg="{sgg}" data-upside="{su}" data-holding="{'true' if hold_shares>0 else 'false'}" data-watching="{'true' if not is_unanalyzed and status=='WATCHING' else 'false'}">
  <td class="code-cell">{code_disp}{plan_icon} {mth_badge}</td><td class="name-cell" title="{name}">{name[:8]}{spark_html}</td><td>{hold_str}</td>
  <td>{price_str}</td><td class="{gg_cls}">{gg_str}</td>
  <td>{buy_str}<span class="{up_cls}">{up_str}</span></td><td><span class="badge {badge_cls}">{decision}</span></td>
  <td>{pos_str}</td></tr>""")
        if detail: table_rows.append(f'<tr class="detail-row"><td colspan="8">{detail}</td></tr>')

    # ── Phone alerts for alerts tab ──
    phone_alerts_html = ""
    alert_list = assets.get("alerts", [])
    if alert_list:
        alert_items = []
        for al in alert_list[:8]:
            atype = al["alertType"]
            price = al["targetPrice"]
            cur = al.get("currentPrice") or price
            diff = (cur / price - 1) * 100 if price > 0 else 0
            icon = "🔴" if atype == "BUY1" else ("🟡" if atype == "BUY2" else "🟢")
            alert_items.append(f'{icon} {al["code"]} {atype}@{price:.2f} <small>({diff:+.0f}%)</small>')
        phone_alerts_html = f"""<div class="callout" style="border-left-color: var(--yellow);">
<strong>📡 待触发提醒 ({len(alert_list)})</strong><br>{' · '.join(alert_items[:4])}
{'<br>' + ' · '.join(alert_items[4:]) if len(alert_items) > 4 else ''}</div>"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass
    callout_count = (1 if priority_html else 0) + (1 if suggest_html else 0) + (1 if bt_html else 0) + (1 if buy_now_html else 0) + (1 if rebalance_html else 0)

    # ── Weekly action summary ──
    action_items = []
    if can_buy:
        action_items.append(f'💰 {len(can_buy)} 只可买（现价低于买入价）')
    if unanalyzed_rows:
        action_items.append(f'🔔 {len(unanalyzed_rows)} 只持仓待分析')
    if suggestions:
        action_items.append(f'🔄 {len(suggestions)} 只建议重分析')
    # Stale analysis check
    stale_action = sum(1 for r in rows if r.get("_stale") and r.get("_row_type")=="analyzed")
    if stale_action:
        action_items.append(f'⏰ {stale_action} 只分析超30天')
    # Dividend estimate
    div_annual = assets.get("dividends", {}).get("expected_annual", 0)
    if div_annual > 0:
        action_items.append(f'💵 预计年股息 ¥{div_annual:,.0f}')
    action_html = ""
    if action_items:
        action_html = f'<div class="callout" style="border-left-color:var(--accent);font-size:0.85em"><strong>📋 行动摘要</strong>  {"  ·  ".join(action_items)}</div>'


    # ── Analysis freshness ──
    fresh_parts = []
    if stale_count:
        fresh_parts.append(f"⏰ {stale_count} 只超30天未更新")
    price_diverged = sum(1 for r in rows if r.get("_row_type")=="analyzed" and r.get("live_price") and r.get("price") and abs(r["live_price"]/r["price"]-1) > 0.2)
    if price_diverged:
        fresh_parts.append(f"📉 {price_diverged} 只价格偏离>20%")
    needs_rerun = len(suggestions) if suggestions else 0
    if needs_rerun:
        fresh_parts.append(f"🔄 {needs_rerun} 只建议重分析")
    freshness_html = ""
    if fresh_parts:
        freshness_html = f'<div class="callout" style="border-left-color:var(--yellow);font-size:0.82em"><strong>📊 分析新鲜度</strong>  {"  ·  ".join(fresh_parts)}  ·  <code>python scripts/batch_analyze.py --stale</code></div>'

    # ── KPI cards for overview tab ──
    def kpi(num, label, accent=False, filter_key=None):
        cls = "kpi-card" + (" kpi-accent" if accent else "") + (" clickable" if filter_key else "")
        filt = f' data-filter="{filter_key}"' if filter_key else ""
        return f'<div class="{cls}"{filt}><div class="kpi-num">{num}</div><div class="kpi-label">{label}</div></div>'

    overview_kpis = ""
    overview_kpis += kpi(f"{holding_count}只", "● 持仓", filter_key="holding")
    overview_kpis += kpi(f"{assets.get('watching_count', 0)}只", "○ 观察", filter_key="watching")
    overview_kpis += kpi(f"{analyzed_total}", "已分析")
    overview_kpis += kpi(f"{unanalyzed_holding}", "🔔待分析")
    overview_kpis += kpi(f"{strong_buy}只", "Strong Buy", accent=(strong_buy>0), filter_key="Strong Buy")
    overview_kpis += kpi(f"{buy}只", "Buy", filter_key="Buy")
    overview_kpis += kpi(f"{hold}只", "Hold", filter_key="Hold")
    overview_kpis += kpi(f"{avoid}只", "Avoid", filter_key="Avoid")

    # ── Alerts summary for overview tab ──
    alerts_summary = ""
    total_alerts = len(alert_list) + callout_count
    if total_alerts > 0:
        items = []
        if alert_list: items.append(f"📡 {len(alert_list)} 个待触发提醒")
        if priority_html: items.append(f"📋 {len(unanalyzed_rows)} 只持仓待分析")
        if suggest_html: items.append(f"🔄 {len(suggestions)} 只建议重分析")
        if bt_html: items.append("📊 回测")
        if buy_now_html: items.append(f"💰 {len(can_buy)} 只当前可买")
        if rebalance_html: items.append("⚖️ 再平衡建议")
        alerts_summary = f"""<div class="section-header" onclick="document.querySelector('.tab-btn[data-tab=alerts]').click()">
<h3>📡 提醒中心</h3><span class="arrow">→</span></div>
<div class="callout" style="font-size:0.82em">{' · '.join(items)}</div>"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass

    # ── Structure tab: charts ──
    donut_colors = ["var(--red)","#c77d4d","#5c9a62","#7a6a1b","#3d5a80","#b07040","#4a7c59","#8b6914"]
    sectors = assets.get("by_sector", [])
    sector_stocks = assets.get("sector_stocks", {})
    sector_html = ""
    if sectors:
        total_val = sum(v for _, v in sectors)
        max_val = max(v for _, v in sectors) if sectors else 1
        rows_html = ""
        for i, (sec, val) in enumerate(sectors[:8]):
            pct = val / max_val * 100
            share = val / total_val * 100 if total_val > 0 else 0
            color = donut_colors[i % len(donut_colors)]
            sec_id = f"sec-s{i}"
            stocks_in_sec = sector_stocks.get(sec, [])
            stock_rows = ""
            for s in stocks_in_sec[:10]:
                if (s["hold"] or 0) <= 0: continue
                stock_rows += f'<div style="font-size:0.78em;padding:2px 0 2px 1.5em;color:var(--text-light)">{s["code"]} {s["name"][:6]} {s["hold"]:,}股 @{s["price"]:.2f} · {s["value"]/1e4:.2f}万</div>'
            rows_html += f'<div class="section-header" data-toggle="{sec_id}" style="padding:0.2em 0"><span class="bar-label" style="font-weight:600;flex:none;min-width:60px">{sec}</span><span class="bar-track" style="height:14px;flex:1;margin:0 0.5em"><span class="bar-fill" style="width:{pct}%;background:{color}"></span></span><span class="bar-value" style="flex:none;min-width:45px">{share:.0f}%</span><span class="arrow" style="flex:none">▶</span></div><div class="collapsible-body" id="{sec_id}"><div class="alert-grid">{stock_rows}</div></div>'
        sector_html = f'<div class="chart-section"><div class="chart-title">🏭 行业分布（点击展开）</div>{rows_html}</div>'

    by_market = assets.get("by_market", {})
    mkt_html = ""
    if by_market:
        total_mkt = sum(d["value"] for d in by_market.values())
        if total_mkt > 0:
            mkt_bars = ""; legend = ""; ci = 0
            mkt_labels = {"H":"港股","A":"A股","B":"B股","DE":"德股"}
            for m, d in sorted(by_market.items(), key=lambda x: x[1]["value"], reverse=True):
                pct = d["value"] / total_mkt * 100
                color = donut_colors[ci % len(donut_colors)]; ci += 1
                mkt_bars += f'<span style="display:inline-block;width:{pct}%;background:{color};height:100%"></span>'
                legend += f'<span style="color:{color}">■</span> {mkt_labels.get(m,m)} {pct:.0f}% '
            mkt_html = f'<div class="chart-section"><div class="chart-title">🌍 市场分布</div><div style="height:24px;border-radius:4px;overflow:hidden;display:flex;margin-bottom:0.4em;">{mkt_bars}</div><div class="donut-legend">{legend}</div></div>'

    total_wealth = assets.get("total_wealth", 0)
    conc = assets.get("concentration", {})
    conc_html = ""
    if conc.get("top_holdings") and total_wealth > 0:
        # Recompute as % of total assets (not just stock value)
        top_holdings_pct_total = []
        for h in conc["top_holdings"][:8]:
            pct_total = h["value"] / total_wealth * 100
            top_holdings_pct_total.append((h, pct_total))
        max_pct = max(p for _, p in top_holdings_pct_total) if top_holdings_pct_total else 1
        rows_html = ""
        for ci, (h, pct_total) in enumerate(top_holdings_pct_total):
            bar_w = pct_total / max_pct * 100
            color = donut_colors[ci % len(donut_colors)]
            rows_html += f'<div class="bar-row"><span class="bar-label">{h["code"][-6:]} {h["name"][:4]}</span><span class="bar-track"><span class="bar-fill" style="width:{bar_w}%;background:{color}"></span></span><span class="bar-value">{pct_total:.1f}%</span></div>'
        top5_total = sum(p for _, p in top_holdings_pct_total[:5])
        warn = f' <span style="color:var(--red)">⚠️{conc["sector_warning"]}</span>' if conc.get("sector_warning") else ""
        conc_html = f'<div class="chart-section"><div class="chart-title">🎯 持仓集中度（占总资产）{warn}</div><div style="font-size:0.75em;color:var(--text-light);margin-bottom:0.4em;">TOP5占比 {top5_total:.0f}%</div>{rows_html}</div>'

        # Position limit warnings
        limit_warnings = []
        for r in rows:
            if r["inv_holding"] > 0:
                hold_val = r["inv_holding"] * (r.get("live_price") or r.get("price") or 0)
                actual_pct = hold_val / total_wealth * 100 if total_wealth > 0 else 0
                limit_pct = (r.get("inv_hold_limit_pct") or 0.05) * 100
                if actual_pct > limit_pct and limit_pct > 0:
                    name = (r.get("wl_name") or r.get("name") or "")[:6]
                    limit_warnings.append(f'{r["ts_code"]} {name} 实际{actual_pct:.1f}% &gt; 上限{limit_pct:.0f}%')
        if limit_warnings:
            conc_html += f'<div class="callout" style="margin-top:0.5em;border-left-color:var(--red)"><strong>⚠️ 仓位超限</strong><br>{" · ".join(limit_warnings[:5])}</div>'
    # Stock type distribution
    by_type = assets.get("by_type", {})
    type_stocks_data = assets.get("type_stocks", {})
    type_html = ""
    if by_type:
        type_labels = {"A": "价值股", "B": "困境股", "C": "套利股"}
        total_type_val = sum(d["value"] for d in by_type.values())
        type_rows = ""
        ci = 0
        for t, d in sorted(by_type.items(), key=lambda x: x[1]["value"], reverse=True):
            pct = d["value"] / total_type_val * 100 if total_type_val > 0 else 0
            color = donut_colors[ci % len(donut_colors)]; ci += 1
            label = type_labels.get(t, t)
            type_id = f"sec-type-{t}"
            stocks_in_type = type_stocks_data.get(t, [])
            stock_rows = ""
            for s in stocks_in_type[:10]:
                sp = s["value"] / d["value"] * 100 if d["value"] > 0 else 0
                if sp < 0.5: continue
                stock_rows += f'<div style="font-size:0.78em;padding:2px 0 2px 1.5em;color:var(--text-light)">{s["code"]} {s["name"][:6]} <span style="color:var(--heading)">{sp:.0f}%</span></div>'
            type_rows += f'<div class="section-header" data-toggle="{type_id}" style="padding:0.2em 0"><span class="bar-label" style="font-weight:600;flex:none;min-width:60px">{label}</span><span class="bar-track" style="height:14px;flex:1;margin:0 0.5em"><span class="bar-fill" style="width:{max(pct,2)}%;background:{color}"></span></span><span class="bar-value" style="flex:none;min-width:45px">{pct:.0f}%</span><span class="arrow" style="flex:none">▶</span></div><div class="collapsible-body" id="{type_id}"><div class="alert-grid">{stock_rows}</div></div>'
        type_html = f'<div class="chart-section"><div class="chart-title">📦 股票类型（点击展开）</div>{type_rows}</div>'

    # Fundamentals summary
    f = assets.get("fundamentals", {})
    fund_html = ""
    if f.get("avg_pe") or f.get("avg_pb") or f.get("avg_div_yield_pct"):
        items = []
        if f.get("avg_pe"): items.append(f"PE {f['avg_pe']}")
        if f.get("avg_pb"): items.append(f"PB {f['avg_pb']}")
        if f.get("avg_div_yield_pct"): items.append(f"股息率 {f['avg_div_yield_pct']}%")
        div = assets.get("dividends", {})
        if div.get("expected_annual", 0) > 0:
            items.append(f"预计年股息 ¥{div['expected_annual']:,.0f}")
        fund_html = f'<div class="asset-overview"><div class="asset-row"><div class="asset-card asset-primary"><div class="asset-label">📈 组合基本面</div><div class="asset-sub" style="font-size:0.85em">{" · ".join(items)}</div></div></div></div>'

    
    # === Latest year PE/PB ===
    fund_trend_html = ""
    try:
        from niangao.db import get_db as _gdb_ft
        _db_ft = _gdb_ft()
        latest = dict(_db_ft.execute("SELECT year, AVG(pe) as pe, AVG(pb) as pb FROM fundamentals_history WHERE year=(SELECT MAX(year) FROM fundamentals_history)").fetchone())
        prev = dict(_db_ft.execute("SELECT year, AVG(pe) as pe, AVG(pb) as pb FROM fundamentals_history WHERE year=(SELECT MAX(year)-1 FROM fundamentals_history)").fetchone()) if latest else {}
        _db_ft.close()
        if latest.get("pe"):
            pe_chg = ((latest["pe"] - prev["pe"]) / prev["pe"] * 100) if prev.get("pe") and prev["pe"] > 0 else 0
            pb_chg = ((latest["pb"] - prev["pb"]) / prev["pb"] * 100) if prev.get("pb") and prev["pb"] > 0 else 0
            pe_clr = 'var(--red)' if pe_chg > 0 else 'var(--green)'
            pb_clr = 'var(--red)' if pb_chg > 0 else 'var(--green)'
            fund_trend_html = f'<div class="asset-overview"><div class="asset-row"><div class="asset-card"><div class="asset-label">组合 PE ({latest["year"]})</div><div class="asset-value">{latest["pe"]:.1f}</div><div class="asset-sub" style="color:{pe_clr}">同比 {pe_chg:+.0f}%</div></div><div class="asset-card"><div class="asset-label">组合 PB ({latest["year"]})</div><div class="asset-value">{latest["pb"]:.1f}</div><div class="asset-sub" style="color:{pb_clr}">同比 {pb_chg:+.0f}%</div></div></div></div>'
    except Exception:
        pass

    
    structure_html = ""  # Content directly in template tabs or '<p style="color:var(--text-light);text-align:center;">暂无结构数据</p>'

    # ── Alerts tab: card-style ──
    alerts_cards = []
    for al in alert_list[:12]:
        atype = al["alertType"]; target = al["targetPrice"]
        cur = al.get("currentPrice") or target
        diff = (cur / target - 1) * 100 if target > 0 else 0
        diff_cls = "upside-pos" if diff > 0 else "upside-neg"
        icon = "🔴" if atype == "BUY1" else ("🟡" if atype == "BUY2" else "🟢")
        gg_str = ""
        code = al["code"]
        matched = [r for r in rows if _turtle_to_invest_code(r["ts_code"]) == code and r.get("_row_type")=="analyzed" and r.get("gg_ok")]
        if matched:
            m = matched[0]
            if m.get("gg_val"): gg_str = f'<span class="alert-gg" style="color:var(--green)">GG {m["gg_val"]:.1f}%</span>'
        alerts_cards.append(f'''<div class="alert-card"><span class="alert-icon">{icon}</span><div class="alert-info"><span class="stock-code">{al["code"]} {al.get("name","")[:6]}</span><div class="stock-meta">{atype} 目标价 {target:.2f}</div></div>{gg_str}<div class="alert-price"><div class="target">{target:.2f}</div><div class="diff {diff_cls}">现价 {cur:.2f} ({diff:+.0f}%)</div></div></div>''')
    phone_alerts_cards = f'<div class="section-header open" data-toggle="sec-phone-alerts"><h3>📡 待触发提醒 ({len(alert_list)})</h3><span class="arrow">▶</span></div><div class="collapsible-body open" id="sec-phone-alerts"><div class="alert-grid">{"".join(alerts_cards)}</div></div>' if alerts_cards else ""

    # Triggered alerts
    triggered_list = assets.get("triggered_alerts", [])
    triggered_cards = ""
    if triggered_list:
        tcards = []
        for al in triggered_list[:12]:
            atype = al["alertType"]; target = al["targetPrice"]
            cur = al.get("currentPrice") or target
            diff = (cur / target - 1) * 100 if target > 0 else 0
            diff_cls = "upside-pos" if diff > 0 else "upside-neg"
            tcards.append(f'<div class="alert-card" style="opacity:0.7"><span class="alert-icon">✅</span><div class="alert-info"><span class="stock-code">{al["code"]} {al.get("name","")[:6]}</span><div class="stock-meta">{atype} 目标价 {target:.2f} · 已触发</div></div><div class="alert-price"><div class="target">{target:.2f}</div><div class="diff {diff_cls}">现价 {cur:.2f} ({diff:+.0f}%)</div></div></div>')
        triggered_cards = f'<div class="section-header" data-toggle="sec-triggered"><h3>✅ 已触发提醒 ({len(triggered_list)})</h3><span class="arrow">▶</span></div><div class="collapsible-body" id="sec-triggered"><div class="alert-grid">{"".join(tcards)}</div></div>'

    unalyzed_cards = ""
    if unanalyzed_rows:
        cards = []
        for u in unanalyzed_rows[:8]:
            name = (u.get("wl_name") or u.get("name") or "")[:6]
            hold = u.get("current_hold", 0); avg = u.get("avg_cost", 0) or 0
            price = u.get("live_price", 0) or 0; dps = u.get("annual_div_per_share") or u.get("inv_dps") or 0
            div_yield = f" 股息率 {dps/price*100:.1f}%" if (dps > 0 and price > 0) else ""
            cards.append(f'<div class="alert-card"><span class="alert-icon">🔔</span><div class="alert-info"><span class="stock-code">{u["ts_code"]} {name}</span><div class="stock-meta">持仓 {hold:,}股 · 均价 {avg:.2f}{div_yield}</div></div><div class="alert-gg" style="color:var(--yellow)">待分析</div></div>')
        unalyzed_cards = f'<div class="section-header" data-toggle="sec-unanalyzed"><h3>📋 持仓待分析 ({len(unanalyzed_rows)}只)</h3><span class="arrow">▶</span></div><div class="collapsible-body" id="sec-unanalyzed"><div class="alert-grid">{"".join(cards)}</div></div>'

    buy_cards = ""
    if can_buy:
        cards = []
        for r in can_buy[:6]:
            name = (r.get("wl_name") or r.get("name") or "")[:6]
            price = r.get("live_price") or r.get("price") or 0; bp = r.get("buy_price") or 0
            gg = r.get("gg_val")
            dyn_gg = f"穿透 {gg*bp/price:.1f}%" if (gg and bp > 0 and price > 0) else (f"GG {gg:.1f}%" if gg else "")
            cards.append(f'<div class="alert-card" style="border-color:var(--green);background:var(--green-bg)"><span class="alert-icon">💰</span><div class="alert-info"><span class="stock-code">{r["ts_code"]} {name}</span><div class="stock-meta">现价 {price:.2f} &lt; 买入价 {bp:.2f} ({bp/price-1:+.0f}%)</div></div><span class="alert-gg" style="color:var(--green)">{dyn_gg}</span><span class="badge badge-strong-buy">{r.get("decision","")}</span></div>')
        buy_cards = f'<div class="section-header" data-toggle="sec-buy-now"><h3>💰 当前可买 ({len(can_buy)}只)</h3><span class="arrow">▶</span></div><div class="collapsible-body" id="sec-buy-now"><div class="alert-grid">{"".join(cards)}</div></div>'

    suggest_cards_html = ""
    if suggestions:
        cards = []
        for s in suggestions[:6]:
            cards.append(f'<div class="alert-card"><span class="alert-icon">📌</span><div class="alert-info"><span class="stock-code">{s["ts_code"]} {(s.get("name") or "")[:6]}</span><div class="stock-meta">{s.get("reason","")}</div></div></div>')
        suggest_cards_html = f'<div class="section-header" data-toggle="sec-rerun"><h3>🔄 建议重分析 ({len(suggestions)}只)</h3><span class="arrow">▶</span></div><div class="collapsible-body" id="sec-rerun"><div class="alert-grid">{"".join(cards)}</div></div>'

    bt_cards_html = ""
    if bt_results:
        cards = []
        hit_count = sum(1 for r in bt_results if r["hit"]); avg_score = sum(r["score"] for r in bt_results) / len(bt_results)
        for r in bt_results[:6]:
            icon = "✅" if r["hit"] else ("❌" if r["hit"] is False else "—")
            cards.append(f'<div class="alert-card"><span class="alert-icon">{icon}</span><div class="alert-info"><span class="stock-code">{r["ts_code"]}</span></div><span class="alert-gg">评分 {r["score"]}</span></div>')
        bt_cards_html = f'<div class="section-header" data-toggle="sec-backtest"><h3>📊 回测 ({hit_count}/{len(bt_results)} 到位 均分{avg_score:.0f})</h3><span class="arrow">▶</span></div><div class="collapsible-body" id="sec-backtest"><div class="alert-grid">{"".join(cards)}</div></div>'

    # ── Returns tab ──
    ret = assets.get("returns", {})
    returns_html = ""
    if ret.get("current_wealth", 0) > 0:
        total_ret = ret.get("total_return", 0)
        ret_color = 'var(--green)' if total_ret >= 0 else 'var(--red)'
        ret_sign = "+" if total_ret >= 0 else ""
        # Year table
        year_rows = ""
        for y in ret.get("years", []):
            mv = y.get("marketValueCny", 0) or 0
            pnl = y.get("cumulativePnlCny") or 0
            div = y.get("dividendCny") or 0
            year_rows += f'<tr><td style="text-align:center">{y["year"]}</td><td style="text-align:right">{mv/1e4:.1f}万</td><td style="text-align:right;color:{'var(--green)' if pnl>=0 else 'var(--red)'}">{pnl/1e4:+.1f}万</td><td style="text-align:right">{div/1e4:.2f}万</td></tr>' if pnl else f'<tr><td style="text-align:center">{y["year"]}</td><td style="text-align:right">{mv/1e4:.1f}万</td><td colspan="2" style="text-align:center;color:var(--text-light)">--</td></tr>'
        net_flow = ret.get('total_inflow', 0)
            # ── Dividend detail rows ──
    div_rows = ""
    for r in rows:
        if r["inv_holding"] > 0:
            dps = r.get("dps") or r.get("inv_dps") or 0
            hold = r["inv_holding"]
            name = (r.get("wl_name") or r.get("name") or "?")[:6]
            if dps > 0 and hold > 0:
                total = dps * hold
                div_rows += f'<tr><td>{r["ts_code"]} {name}</td><td style="text-align:right">{hold:,}</td><td style="text-align:right">{dps:.4f}</td><td style="text-align:right">{total:,.0f}</td></tr>'
    if not div_rows:
        div_rows = '<tr><td colspan="4" style="text-align:center;color:var(--text-light)">暂无股息数据</td></tr>'

    

    # === Unified P&L: holdings with dividend included ===
    pnl_rows = ""; total_cost = 0; total_mv = 0; total_pnl = 0; total_div_est = 0
    for r in rows:
        hold = r.get("inv_holding", 0) or 0
        if hold <= 0: continue
        price = r.get("live_price") or r.get("price") or 0
        cost = r.get("inv_avg_cost", 0) or 0
        if price <= 0: continue
        name = (r.get("wl_name") or r.get("name") or "?")[:6]
        mv = hold * price; cb = hold * cost if cost > 0 else 0
        total_cost += cb; total_mv += mv
        pnl = mv - cb
        dps = r.get("dps") or r.get("inv_dps") or 0
        div_est = dps * hold
        total_pnl += pnl; total_div_est += div_est
        total_ret = pnl + div_est; has_cost = cb > 0
        pnl_pct = (total_ret / cb * 100) if cb > 0 else 0
        clr = 'var(--green)' if total_ret >= 0 else 'var(--red)'
        pnl_rows += f'<tr><td>{name}</td><td style="text-align:right">{hold:,}</td><td style="text-align:right">{cost:.2f}</td><td style="text-align:right">{price:.2f}</td><td style="text-align:right">{mv/1e4:.2f}万</td><td style="text-align:right;color:{clr}">{pnl:+,.0f}</td><td style="text-align:right">{div_est:,.0f}</td><td style="text-align:right;color:{clr}">{total_ret:+,.0f}</td><td style="text-align:right;color:{clr}">{pnl_pct:+.1f}%</td></tr>'
    grand_total_ret = total_pnl + total_div_est
    total_clr = 'var(--green)' if grand_total_ret >= 0 else 'var(--red)'
    total_pnl_pct = (grand_total_ret/total_cost*100) if total_cost > 0 else 0
    if pnl_rows:
        pnl_rows += f'<tr style="font-weight:600;border-top:2px solid var(--heading)"><td>合计</td><td style="text-align:right"></td><td style="text-align:right">{total_cost/1e4:.1f}万</td><td style="text-align:right"></td><td style="text-align:right">{total_mv/1e4:.1f}万</td><td style="text-align:right;color:{total_clr}">{total_pnl:+,.0f}</td><td style="text-align:right">{total_div_est:,.0f}</td><td style="text-align:right;color:{total_clr}">{grand_total_ret:+,.0f}</td><td style="text-align:right;color:{total_clr}">{total_pnl_pct:+.1f}%</td></tr>'
    else:
        pnl_rows = '<tr><td colspan="9" style="text-align:center;color:var(--text-light)">暂无持仓</td></tr>'

    # === Realized P&L: read from persisted realized_pnl table ===
    total_real_pnl = 0; real_pnl_rows = ""
    try:
        from niangao.db import get_db as _gdb_r2
        _db_r2 = _gdb_r2()
        rpnl_data = [dict(r) for r in _db_r2.execute("SELECT * FROM realized_pnl ORDER BY realized_pnl DESC").fetchall()]
        _db_r2.close()
        for rp in rpnl_data:
            pnl = rp["realized_pnl"] or 0; total_real_pnl += pnl
            clr = 'var(--green)' if pnl >= 0 else 'var(--red)'
            real_pnl_rows += f'<tr><td>{rp["stock_code"]} {rp.get("stock_name","")[:6]}</td><td style="text-align:right">{rp["total_sell_amt"]:,.0f}</td><td style="text-align:right">{rp["total_buy_amt"]:,.0f}</td><td style="text-align:right;color:{clr}">{pnl:+,.0f}</td></tr>'
        if real_pnl_rows:
            tc = 'var(--green)' if total_real_pnl >= 0 else 'var(--red)'
            real_pnl_rows += f'<tr style="font-weight:600;border-top:2px solid var(--heading)"><td>合计</td><td></td><td></td><td style="text-align:right;color:{tc}">{total_real_pnl:+,.0f}</td></tr>'
    except Exception:
        pass
    if not real_pnl_rows:
        real_pnl_rows = '<tr><td colspan="4" style="text-align:center;color:var(--text-light)">暂无已清仓记录</td></tr>'

    # === Dividend: actual (from DIVIDEND trades) + estimated ===
    div_actual_html = ""; total_div_actual = 0
    try:
        from niangao.db import get_db as _gdb_r3
        _db_r3 = _gdb_r3()
        div_data = [dict(r) for r in _db_r3.execute("SELECT stock_code, stock_name, amount, dividend_year FROM trade_record WHERE trade_type='DIVIDEND' ORDER BY dividend_year DESC, stock_code").fetchall()]
        _db_r3.close()
        if div_data:
            by_year = {}
            for d in div_data:
                y = d.get("dividend_year") or 2026
                if y < 2026: y = 2026
                if y not in by_year: by_year[y] = []
                by_year[y].append(d); total_div_actual += d["amount"] or 0
            years = sorted([y for y in by_year.keys() if y >= 2026], reverse=True)
            if years:
                div_actual_html += '<div class="filters" style="margin-bottom:0.6em">'
                for i, y in enumerate(years):
                    yr_total = sum(d["amount"] or 0 for d in by_year[y])
                    div_actual_html += f'<button class="div-year-btn {"active" if i==0 else ""}" onclick="showDivYear({y},this)">{y} ¥{yr_total:,.0f}</button>'
                div_actual_html += '</div>'
                for i, y in enumerate(years):
                    yr_total = sum(d["amount"] or 0 for d in by_year[y])
                    rows_y = "".join(f'<tr><td>{d["stock_code"]} {d.get("stock_name","")[:6]}</td><td style="text-align:right">{d["amount"]:,.0f}</td></tr>' for d in by_year[y])
                    div_actual_html += f'<div id="div-year-{y}" class="div-year-panel {"" if i==0 else "ret-hidden"}"><div class="return-note" style="margin-bottom:0.5em">{y}年合计 ¥{yr_total:,.0f}</div><div class="table-wrap"><table><tbody>{rows_y}</tbody></table></div></div>'
    except Exception:
        pass
    if not div_actual_html:
        div_actual_html = '<p style="color:var(--text-light)">暂无已兑现股息记录</p>'

    # Estimated dividend table
    div_est_rows = ""
    for r in rows:
        hold = r.get("inv_holding", 0) or 0
        if hold <= 0: continue
        dps = r.get("dps") or r.get("inv_dps") or 0
        if dps <= 0: continue
        name = (r.get("wl_name") or r.get("name") or "?")[:6]
        est = dps * hold
        div_est_rows += f'<tr><td>{r["ts_code"]} {name}</td><td style="text-align:right">{hold:,}</td><td style="text-align:right">{dps:.4f}</td><td style="text-align:right">{est:,.0f}</td></tr>'
    if div_est_rows:
        div_est_rows += f'<tr style="font-weight:600;border-top:2px solid var(--heading)"><td>合计</td><td></td><td></td><td style="text-align:right">{total_div_est:,.0f}</td></tr>'

    # === Transaction log ===
    txn_rows = ""
    try:
        from niangao.db import get_db as _gdb_r4
        _db_r4 = _gdb_r4()
        txns = [dict(r) for r in _db_r4.execute("SELECT * FROM trade_record ORDER BY trade_at DESC LIMIT 30").fetchall()]
        _db_r4.close()
        from datetime import datetime as _dt2
        for tx in txns:
            ts = tx.get("trade_at", 0) or 0
            date_str = _dt2.fromtimestamp(ts/1000).strftime("%Y-%m-%d") if ts > 0 else ""
            icon = "🟢" if tx["trade_type"] == "BUY" else ("🔴" if tx["trade_type"] == "SELL" else "💵")
            txn_rows += f'<tr><td>{date_str}</td><td>{tx["stock_code"]} {tx.get("stock_name","")[:6]}</td><td>{icon} {tx["trade_type"]}</td><td style="text-align:right">{tx["price"]:.2f}</td><td style="text-align:right">{tx["shares"]:,}</td><td style="text-align:right">{tx["amount"]:,.0f}</td></tr>'
    except Exception:
        pass
    if not txn_rows:
        txn_rows = '<tr><td colspan="6" style="text-align:center;color:var(--text-light)">暂无交易记录</td></tr>'

    # Bottom summary
    net_inflow = ret.get("total_inflow", 0)
    grand_total = grand_total_ret + total_real_pnl + total_div_actual


    returns_html = f"""<div class="asset-overview">
  <div class="asset-row">
    <div class="asset-card asset-primary">
      <div class="asset-label">当前总资产</div>
      <div class="asset-value return-metric">{ret['current_wealth']/1e4:.1f}万</div>
      <div class="asset-sub">跟踪 {ret.get('days_tracked',0)} 天</div>
    </div>
    <div class="asset-card">
      <div class="asset-label">总增值（扣除入金）</div>
      <div class="asset-value return-metric" style="color:{ret_color}">{ret_sign}{total_ret/1e4:.1f}万</div>
      <div class="asset-sub" style="color:{ret_color}">{ret_sign}{ret.get('total_return_pct',0):.1f}%</div>
    </div>
    <div class="asset-card">
      <div class="asset-label">年初至今 YTD</div>
      <div class="asset-value return-metric" style="color:{'var(--green)' if ret.get('ytd_return_pct',0)>=0 else 'var(--red)'}">{ret.get('ytd_return_pct',0):+.1f}%</div>
      <div class="asset-sub">年化 {ret.get('annualized_pct',0):+.1f}%</div>
    </div>
    <div class="asset-card">
      <div class="asset-label">现金流 / 股息</div>
      <div class="asset-value return-metric">¥{ret.get('total_dividends',0):,.0f}</div>
      <div class="asset-sub">出入金净额 {net_flow/1e4:+.1f}万</div>
    </div>
  </div>
  <div class="return-note">※ 总增值已扣除出入金影响；股息明细已移到「股息」子页，避免和概览重复。</div>
</div>

"""

    # ── Rebalance suggestions ──
    rebalance_html = ""
    try:
        rb = compute_rebalance(rows)
        if rb and rb.get("actions"):
            rb_items = []
            for a in rb["actions"][:6]:
                icon = "📈" if a.get("action") == "buy" else "📉"
                rb_items.append(f'{icon} {a.get("ts_code","")} {a.get("name","")[:4]}: {a.get("current_pct",0):.1f}%→{a.get("target_pct",0):.1f}%')
            if rb_items:
                rebalance_html = f'<div class="callout" style="border-left-color:var(--green)"><strong>⚖️ 调仓建议</strong><br>{" · ".join(rb_items)}</div>'
    except Exception:
        pass

    # ── Doc library tab ──
    doc_lib_html = _build_doc_library(rows)

    alerts_cards_html = phone_alerts_cards + triggered_cards + unalyzed_cards + suggest_cards_html + bt_cards_html + buy_cards
    if not alerts_cards_html.strip():
        alerts_cards_html = '<p style="color:var(--text-light);font-size:0.8em;text-align:center;">暂无提醒</p>'

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>年糕投资仪表盘</title><style>{_CSS}</style></head><body><div class="container">
<h1>🏮 年糕投资仪表盘</h1><div class="subtitle">更新于 {now} · {analyzed_total} 只已分析 · {holding_count} 只持仓</div>

<!-- Tab Navigation -->
<div class="tab-nav">
  <button class="tab-btn active" data-tab="overview">📊 概览</button>
  <button class="tab-btn" data-tab="returns">📈 回报</button>
  <button class="tab-btn" data-tab="structure">📊 结构</button>
  <button class="tab-btn" data-tab="holdings">📋 持仓 <span class="tab-badge">{len(rows)}</span></button>
  <button class="tab-btn" data-tab="alerts">📡 提醒 <span class="tab-badge">{total_alerts}</span></button>
  <button class="tab-btn" data-tab="docs">📚 资料</button>
</div>

<!-- ═══════════ OVERVIEW TAB ═══════════ -->
<div class="tab-panel active" id="panel-overview">
  {action_html}
  {asset_html}
  {pf_html}
  {rebalance_html}
  <div class="kpi-grid">{overview_kpis}</div>
  {alerts_summary}
  <p style="color:var(--text-light);font-size:0.75em;text-align:center;margin-top:1em;">
    💡 点击上方数字卡片可跳转到持仓分析并自动筛选
</div>

<!-- ═══════════ RETURNS TAB ═══════════ -->
<div class="tab-panel" id="panel-returns">
  <div class="tab-nav" style="margin-bottom:0.8em"><button class="tab-btn active" onclick="showRetTab('overview',this)">概览</button><button class="tab-btn" onclick="showRetTab('pnl',this)">盈亏</button><button class="tab-btn" onclick="showRetTab('div',this)">股息</button></div>
  <div id="ret-overview">
    {returns_html}
  </div>
  <div id="ret-pnl" class="ret-hidden">
    <div class="return-summary-bar">
      <span>持仓浮盈 + 预计股息 <b style="color:{total_clr}">{grand_total_ret/1e4:+.1f}万</b></span>
      <span>已清仓 <b style="color:{'var(--green)' if total_real_pnl>=0 else 'var(--red)'}">{total_real_pnl/1e4:+.1f}万</b></span>
      <span class="return-total">盈亏合计 <b style="color:{'var(--green)' if (grand_total_ret + total_real_pnl)>=0 else 'var(--red)'}">{(grand_total_ret + total_real_pnl)/1e4:+.1f}万</b></span>
    </div>
    <div class="return-section-grid">
      <div class="chart-section"><div class="chart-title">持仓盈亏（含预计股息）</div><div class="table-wrap"><table><thead><tr><th>股票</th><th style="text-align:right">持仓</th><th style="text-align:right">成本</th><th style="text-align:right">现价</th><th style="text-align:right">市值</th><th style="text-align:right">浮盈</th><th style="text-align:right">股息</th><th style="text-align:right">总回报</th><th style="text-align:right">%</th></tr></thead><tbody>{pnl_rows}</tbody></table></div></div>
      <div class="chart-section"><div class="chart-title">已清仓盈亏</div><div class="table-wrap"><table><thead><tr><th>股票</th><th style="text-align:right">卖出总额</th><th style="text-align:right">买入成本</th><th style="text-align:right">盈亏</th></tr></thead><tbody>{real_pnl_rows}</tbody></table></div><div class="return-note">交易流水移出回报页，只保留盈亏结果，减少噪音。</div></div>
    </div>
  </div>
  <div id="ret-div" class="ret-hidden">
    <div class="return-summary-bar">
      <span>已兑现股息 <b>¥{total_div_actual:,.0f}</b></span>
      <span>预计年股息 <b>¥{total_div_est:,.0f}</b></span>
      <span class="return-total">合计参考 <b>¥{(total_div_actual + total_div_est):,.0f}</b></span>
    </div>
    <div class="return-section-grid">
      <div class="chart-section"><div class="chart-title">已兑现股息</div>{div_actual_html}</div>
      <div class="chart-section"><div class="chart-title">预计年股息</div><div class="table-wrap"><table><thead><tr><th>股票</th><th style="text-align:right">持仓</th><th style="text-align:right">每股股息</th><th style="text-align:right">预计股息</th></tr></thead><tbody>{div_est_rows if div_est_rows else '<tr><td colspan=4 style=text-align:center;color:var(--text-light)>暂无数据</td></tr>'}</tbody></table></div></div>
    </div>
  </div>
</div>

<!-- ═══════════ STRUCTURE TAB ═══════════ -->
<div class="tab-panel" id="panel-structure">
  <div class="tab-nav" style="margin-bottom:0.8em"><button class="tab-btn active" onclick="showStructTab('overview',this)">概览</button><button class="tab-btn" onclick="showStructTab('sector',this)">行业</button><button class="tab-btn" onclick="showStructTab('concentration',this)">集中度</button></div>
  <div id="struct-overview">{fund_trend_html}{fund_html}{mkt_html}{type_html}</div>
  <div id="struct-sector" style="display:none">{sector_html}</div>
  <div id="struct-concentration" style="display:none">{conc_html}</div>
</div>

<!-- ═══════════ HOLDINGS TAB ═══════════ -->
<div class="tab-panel" id="panel-holdings">
  <div id="stock-detail-card" style="display:none"></div>
  <div class="filters"><button class="active" data-filter="all">全部</button><button data-filter="holding">●已持有</button><button data-filter="watching">○观察中</button><button data-filter="Strong Buy">Strong Buy</button><button data-filter="Buy">Buy</button><button data-filter="Hold">Hold</button><button data-filter="Avoid">Avoid</button></div>
  <div class="table-wrap"><table><thead><tr><th data-sort="code">代码</th><th>名称</th><th>持仓</th><th>现价</th><th data-sort="gg" class="sorted">GG ▼</th><th data-sort="upside">买入价</th><th>决策</th><th>仓位</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>
  <p style="color:var(--text-light);font-size:0.72em;text-align:center;margin-top:0.8em;">●已持有 ○观察中 🔔待分析 · GG绿=超II · 点击表头排序 · 点击行展开详情</p>
</div>

<!-- ═══════════ ALERTS TAB ═══════════ -->
<div class="tab-panel" id="panel-alerts">
  {alerts_cards_html}
</div>

<!-- ═══════════ DOC LIBRARY TAB ═══════════ -->
<div class="tab-panel" id="panel-docs">
  {doc_lib_html}
</div>

</div><script>{_JS}</script></body></html>"""

    os.makedirs(_NIANGAO_DIR, exist_ok=True)
    html_path = os.path.join(_NIANGAO_DIR, "_portfolio.html")
    with open(html_path, "w", encoding="utf-8") as f: f.write(html)
    return html_path


def export_invest_json(rows: list[dict], assets: dict | None = None) -> str:
    """生成 invest App 可导入的完整 JSON。包含全部关注股票，含实时价格和 Turtle 估值。"""
    stocks_out = []
    for r in rows:
        inv_code = _turtle_to_invest_code(r["ts_code"])
        is_analyzed = r.get("_row_type") == "analyzed" and r.get("gg_ok")

        # 估值：优先 Turtle P_base，否则保留原手动估值
        turtle_val = r.get("p_base_rmb") or r.get("buy_price") or 0
        manual_val = r.get("inv_valuation") or 0
        valuation = turtle_val if (is_analyzed and turtle_val and turtle_val > 0) else manual_val

        # 价格：优先 live_price
        price = r.get("live_price") or r.get("price") or 0

        # investLogic
        if is_analyzed:
            logic = f"Turtle GG={r.get('gg_discounted')}% II={r.get('ii')}% {r.get('decision','')}"
        else:
            logic = r.get("inv_logic") or ""

        stocks_out.append({
            "code": inv_code, "name": r.get("wl_name") or r.get("name") or "",
            "market": r.get("market", "?"),
            "myValuation": round(valuation, 4) if valuation else 0,
            "multiplier2": 1.0, "sellMultiplier": 1.0,
            "holdLimitPct": max(min((r.get("pos_pct") or 5) / 100, 0.05), 0.01) if is_analyzed else (r.get("inv_hold_limit_pct") or 0.05),
            "currentHold": r.get("inv_holding", 0),
            "avgCost": r.get("inv_avg_cost", 0) or 0,
            "annualDivPerShare": r.get("dps") or r.get("inv_dps") or 0,
            "status": "HOLDING" if (r.get("inv_holding") or 0) > 0 else "WATCHING",
            "investLogic": logic,
            "currentPrice": price,  # 实时价格
            "turtleGG": round(r.get("gg_discounted"), 1) if (is_analyzed and r.get("gg_discounted")) else None,
            "_turtle": {
                "gg": r.get("gg_discounted"), "gg_fcfe": r.get("gg_fcfe"), "ii": r.get("ii"),
                "decision": r.get("decision"), "p_base_hkd": r.get("p_base_hkd"),
                "buy_price": r.get("buy_price"), "buy_star": r.get("buy_star"),
                "upside_pct": r.get("upside_pct"), "pos_pct": r.get("pos_pct"),
                "analyzed_at": r.get("analyzed_at", ""),
            } if is_analyzed else None,
        })
    cash_data = (assets.get("cash", {"CNY": 0, "HKD": 0, "USD": 0})
                 if (assets and "error" not in assets) else {"CNY": 0, "HKD": 0, "USD": 0})
    return json.dumps({"cash": cash_data, "stocks": stocks_out}, indent=2, ensure_ascii=False)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="年糕仪表盘")
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--sync-invest", action="store_true")
    args = ap.parse_args()

    if args.sync_invest:
        w = sync_watchlist(); h = sync_holdings()
        print(f"✅ 同步: watchlist={w} holdings={h}")

    rows = _load_rows()
    os.makedirs(_NIANGAO_DIR, exist_ok=True)

    # Load asset overview for cash data in JSON export
    assets = load_asset_overview()

    export_path = os.path.join(_NIANGAO_DIR, "_portfolio_export.json")
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(export_invest_json(rows, assets))
    print(f"📤 导出: {export_path}")

    if not args.export_only:
        html_path = generate_dashboard(rows, assets)
        print(f"✅ 仪表盘: {html_path}")


if __name__ == "__main__":
    main()
