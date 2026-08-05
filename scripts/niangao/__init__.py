"""年糕投资系统 — 统一入口

分层架构：
  db.py       — 数据层（portfolio.db 的 schema、CRUD、迁移）
  sync.py     — 同步层（invest 备份同步 → watchlist）
  quotes.py   — 行情层（多市场实时价格抓取）
  metrics.py  — 指标层（组合GG、回测、重分析建议）
  dashboard.py — 展示层（HTML 仪表盘生成）

外部入口：
  agent_loop.py  ──→ db.upsert_analysis()  （分析完成自动写入）
  batch_analyze.py ─→ turtle_agent.run     （批量分析调度）
"""

from niangao.db import (
    get_db, upsert_analysis, get_all_analyses, get_analysis_history,
    get_rerun_suggestions, extract_from_bundle, migrate_from_files,
    _normalize_invest_code, _turtle_to_invest_code,
)
from niangao.sync import sync_watchlist, sync_holdings
from niangao.quotes import fetch_all_prices
from niangao.metrics import run_backtest, compute_portfolio_gg, classify_decision
from niangao.dashboard import generate_dashboard, export_invest_json
