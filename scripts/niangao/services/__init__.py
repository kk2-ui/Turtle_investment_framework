"""Formal service layer package for Niangao Web.

Services are the write-side boundary for replacing the Android invest app.
Each module mirrors a key Android service:

- trade_ledger: BUY / SELL / DIVIDEND (port of TradeLedgerService.kt)
- accounts: deposit / withdraw / transfer (port of CashRepository)
- alerts: create / trigger / evaluate (port of AlertRepository)
- stocks: watchlist CRUD / position / valuation (port of StockDao)
- stats: portfolio analytics (port of StatsViewModel)
- audit: backup / audit log / reconcile hooks (Phase 4 safety layer)

Write API endpoints are exposed in server.py with audit/backup/reconcile
hooks. High-risk operations (buy/sell/dividend) require explicit confirmation.
"""

from niangao.services.trade_ledger import (  # noqa: F401
    record_buy,
    record_sell,
    record_dividend,
    get_trades_for_stock,
    project_from_trades,
    PositionProjection,
    LedgerResult,
    TradeLedgerError,
)

from niangao.services.accounts import (  # noqa: F401
    deposit,
    withdraw,
    transfer,
    get_balance,
    list_balances,
    list_accounts,
    get_cash_flow_history,
    CashResult,
    AccountsError,
)

from niangao.services.alerts import (  # noqa: F401
    create_alert,
    trigger_alert,
    deactivate_alert,
    reactivate_alert,
    delete_alert,
    list_alerts,
    evaluate_triggers,
    evaluate_all_triggers,
    get_alert_summary,
    AlertResult,
    AlertError,
)

from niangao.services.stocks import (  # noqa: F401
    upsert_stock,
    get_stock,
    find_by_invest_code,
    update_status,
    update_live_price,
    batch_update_prices,
    update_valuation,
    list_watchlist,
    remove_from_watchlist,
    get_holding_summary,
    StockSnapshot,
    StockError,
)

from niangao.services.stats import (  # noqa: F401
    recompute_all,
    recompute_position_pnl,
    recompute_realized_pnl,
    dividend_summary,
    sector_breakdown,
    account_breakdown,
    portfolio_returns,
    stock_performance,
)

from niangao.services.audit import (  # noqa: F401
    backup_db,
    latest_backup,
    record_audit,
    list_audit_logs,
    quick_reconcile_check,
)
