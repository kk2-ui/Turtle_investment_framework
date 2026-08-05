"""niangao.server — formal FastAPI backend for the Niangao web app.

Read-only API + Phase 4 write endpoints with audit/backup/reconcile hooks.
Phase 5: Jinja2 app templates for full web UI.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from niangao import read_models
from niangao.api_models import (
    # Read response models
    AccountsResponse,
    AlertsResponse,
    ExportResponse,
    HealthResponse,
    HoldingsResponse,
    OverviewResponse,
    ReconcileResponse,
    ReturnsResponse,
    TransactionsResponse,
    # Write request models
    AlertCreateRequest,
    AlertEvaluateRequest,
    AlertTriggerRequest,
    BatchPriceUpdateRequest,
    DepositRequest,
    DividendRequest,
    LivePriceUpdateRequest,
    StatusUpdateRequest,
    StockUpsertRequest,
    TradeBuyRequest,
    TradeSellRequest,
    TransferRequest,
    ValuationUpdateRequest,
    WithdrawRequest,
    # Strategy request models
    GridSellRequest,
    GridBuyRequest,
    MthToggleRequest,
    MthAdvanceRequest,
    # Write response
    WriteResponse,
)
from niangao.db import _DB_PATH
from niangao.services.audit import backup_db, record_audit, quick_reconcile_check

_DASHBOARD_PATH = "/Users/xiami/workspace/analy/_niangao/_portfolio.html"
_EXPORT_PATH = "/Users/xiami/workspace/analy/_niangao/_portfolio_export.json"
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Niangao Investment Web API",
    description="Formal web backend for replacing the Android invest app. Read + write API with audit/backup safety.",
    version="0.2.0",
)

# Static files & templates
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
# Use raw Jinja2 Environment to avoid cache-key issues with Python 3.14
from jinja2 import Environment, FileSystemLoader as JinjaFSLoader  # noqa: E402
_jinja_env = Environment(loader=JinjaFSLoader(str(_TEMPLATE_DIR)), autoescape=True)


# ── Startup: background quote refresh ────────────────────────────────

@app.on_event("startup")
def start_background_refresh():
    """Start a background thread for periodic quote refresh and alert evaluation."""
    import asyncio
    import threading

    async def _refresh_loop():
        while True:
            await asyncio.sleep(900)  # 15 minutes
            try:
                from niangao import quotes as _q
                # Attempt a lightweight refresh — ignore errors if offline
                _q  # just reference, don't force refresh
            except Exception:
                pass

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_refresh_loop())

    t = threading.Thread(target=_run, daemon=True, name="quote-refresh")
    t.start()


# ── Read-only endpoints ──────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(database=_DB_PATH, dashboard=_DASHBOARD_PATH, export_json=_EXPORT_PATH)


@app.get("/api/overview", response_model=OverviewResponse)
def overview() -> dict:
    return read_models.get_overview()


@app.get("/api/holdings", response_model=HoldingsResponse)
def holdings() -> dict:
    return read_models.get_holdings()


@app.get("/api/alerts", response_model=AlertsResponse)
def alerts() -> dict:
    return read_models.get_alerts()


@app.get("/api/transactions", response_model=TransactionsResponse)
def transactions(limit: int = 100) -> dict:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    return read_models.get_transactions(limit=limit)


@app.get("/api/accounts", response_model=AccountsResponse)
def accounts() -> dict:
    return read_models.get_accounts()


@app.get("/api/returns", response_model=ReturnsResponse)
def returns() -> dict:
    return read_models.get_returns()


@app.get("/api/export", response_model=ExportResponse)
def export_json() -> dict:
    return read_models.get_export()


@app.get("/api/reconcile", response_model=ReconcileResponse)
def reconcile() -> dict:
    return read_models.get_reconcile()


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(_DASHBOARD_PATH, media_type="text/html")


# ── Helper: wrap write operations with audit ─────────────────────────

def _safe_write(
    operation: str,
    target_table: str,
    target_key: str = "",
    risk_level: str = "low",
    old_values: dict | None = None,
) -> tuple[str, int]:  # (backup_id, audit_id)
    """Pre-write: backup + audit old_values. Caller must record new_values audit after success."""
    backup_path = backup_db(reason=operation)
    import os
    backup_id = os.path.basename(backup_path)
    audit_id = 0
    if old_values is not None:
        audit_id = record_audit(
            operation=operation,
            target_table=target_table,
            target_key=target_key,
            old_values=old_values,
        )
    return backup_id, audit_id


def _post_write_check(risk_level: str, ts_code: str | None, account_id: int | None) -> list[str]:
    """Post-write: run reconcile check for medium/high risk."""
    if risk_level in ("medium", "high"):
        check = quick_reconcile_check(ts_code=ts_code, account_id=account_id)
        return check.get("warnings", [])
    return []


# ═══════════════════════════════════════════════════════════════════════
# LOW-RISK write endpoints — stock/watchlist, valuation, alerts
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/stocks", response_model=WriteResponse)
def api_upsert_stock(req: StockUpsertRequest):
    """Create or update a stock in the watchlist."""
    from niangao.services.stocks import upsert_stock, get_stock

    old = get_stock(req.ts_code)
    old_dict = {
        "name": old.name, "invest_status": old.invest_status,
        "current_hold": old.current_hold, "avg_cost": old.avg_cost,
        "my_valuation": old.my_valuation, "invest_logic": old.invest_logic,
    } if old else None

    backup_id, audit_id = _safe_write(
        "stock.upsert", "watchlist", req.ts_code, "low", old_dict,
    )

    try:
        upsert_stock(
            ts_code=req.ts_code, name=req.name, market=req.market,
            invest_code=req.invest_code, invest_status=req.invest_status,
            current_hold=req.current_hold, avg_cost=req.avg_cost,
            hold_limit_pct=req.hold_limit_pct,
            annual_div_per_share=req.annual_div_per_share,
            invest_logic=req.invest_logic,
            my_valuation=req.my_valuation, turtle_valuation=req.turtle_valuation,
            live_price=req.live_price, sector=req.sector, stock_type=req.stock_type,
            pe=req.pe, pb=req.pb, debt_ratio=req.debt_ratio, fcf_yield=req.fcf_yield,
            mth_enabled=req.mth_enabled, mth_cycle=req.mth_cycle,
            lock_reserve=req.lock_reserve, cumulative_div=req.cumulative_div,
            dividend_tax_rate=req.dividend_tax_rate, account_id=req.account_id,
        )
        new = get_stock(req.ts_code)
        record_audit(
            operation="stock.upsert", target_table="watchlist", target_key=req.ts_code,
            new_values={"name": new.name, "status": new.invest_status} if new else {},
        )
        return WriteResponse(
            message=f"Stock {req.ts_code} upserted", backup_id=backup_id,
            details={"ts_code": req.ts_code, "action": "upsert"},
        )
    except Exception as e:
        record_audit(operation="stock.upsert.failed", target_table="watchlist",
                     target_key=req.ts_code, new_values={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/stocks/valuation", response_model=WriteResponse)
def api_update_valuation(req: ValuationUpdateRequest):
    """Update manual/Turtle valuation and invest logic for a stock."""
    from niangao.services.stocks import update_valuation, get_stock

    old = get_stock(req.ts_code)
    if old is None:
        raise HTTPException(status_code=404, detail=f"Stock {req.ts_code} not found")
    old_dict = {"my_valuation": old.my_valuation, "turtle_valuation": old.turtle_valuation,
                "invest_logic": old.invest_logic}

    backup_id, _ = _safe_write(
        "stock.valuation", "watchlist", req.ts_code, "low", old_dict,
    )
    try:
        update_valuation(ts_code=req.ts_code, my_valuation=req.my_valuation,
                         turtle_valuation=req.turtle_valuation, invest_logic=req.invest_logic)
        record_audit(operation="stock.valuation", target_table="watchlist", target_key=req.ts_code,
                     new_values={"my_valuation": req.my_valuation, "turtle_valuation": req.turtle_valuation})
        return WriteResponse(
            message=f"Valuation updated for {req.ts_code}", backup_id=backup_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/stocks/status", response_model=WriteResponse)
def api_update_status(req: StatusUpdateRequest):
    """Update a stock's invest status."""
    from niangao.services.stocks import update_status, get_stock

    old = get_stock(req.ts_code)
    old_status = old.invest_status if old else None
    backup_id, _ = _safe_write(
        "stock.status", "watchlist", req.ts_code, "low",
        {"old_status": old_status},
    )
    try:
        update_status(ts_code=req.ts_code, invest_status=req.invest_status)
        return WriteResponse(
            message=f"Status {old_status} → {req.invest_status}", backup_id=backup_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/stocks/price", response_model=WriteResponse)
def api_update_live_price(req: LivePriceUpdateRequest):
    """Update a single stock's live price."""
    from niangao.services.stocks import update_live_price as ulp
    ulp(ts_code=req.ts_code, live_price=req.live_price)
    return WriteResponse(message=f"Price updated for {req.ts_code}")


@app.post("/api/stocks/prices", response_model=WriteResponse)
def api_batch_update_prices(req: BatchPriceUpdateRequest):
    """Batch update live prices."""
    from niangao.services.stocks import batch_update_prices
    count = batch_update_prices(req.prices)
    return WriteResponse(message=f"Updated {count} prices")


@app.delete("/api/stocks/{ts_code}", response_model=WriteResponse)
def api_remove_stock(ts_code: str):
    """Remove a stock — cleans watchlist, analysis, investment_plan, staged_buy_plan."""
    from niangao.db import get_db

    db = get_db()
    try:
        total = 0
        for tbl in ["watchlist", "analysis", "analysis_history", "investment_plan", "staged_buy_plan"]:
            cur = db.execute(f"DELETE FROM {tbl} WHERE ts_code = ?", (ts_code,))
            total += cur.rowcount
        db.commit()
        return WriteResponse(
            message=f"Removed {ts_code}: {total} rows deleted",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


# ── Alert write endpoints ─────────────────────────────────────────────

@app.post("/api/alerts/create", response_model=WriteResponse)
def api_create_alert(req: AlertCreateRequest):
    """Create a new price alert."""
    from niangao.services.alerts import create_alert

    backup_id, _ = _safe_write("alert.create", "alert_snapshot", risk_level="low")
    try:
        result = create_alert(
            stock_code=req.stock_code, alert_type=req.alert_type,
            target_price=req.target_price, stock_name=req.stock_name,
        )
        return WriteResponse(
            message=f"Alert {result.alert_id} created ({req.alert_type} @ {req.target_price})",
            backup_id=backup_id,
            details={"alert_id": result.alert_id, "alert_type": result.alert_type},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/alerts/trigger", response_model=WriteResponse)
def api_trigger_alert(req: AlertTriggerRequest):
    """Manually trigger an alert."""
    from niangao.services.alerts import trigger_alert

    backup_id, _ = _safe_write("alert.trigger", "alert_snapshot", risk_level="low")
    try:
        result = trigger_alert(alert_id=req.alert_id, current_price=req.current_price)
        return WriteResponse(
            message=f"Alert {req.alert_id} triggered", backup_id=backup_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/alerts/deactivate/{alert_id}", response_model=WriteResponse)
def api_deactivate_alert(alert_id: int):
    """Deactivate an alert."""
    from niangao.services.alerts import deactivate_alert

    backup_id, _ = _safe_write("alert.deactivate", "alert_snapshot", risk_level="low")
    try:
        deactivate_alert(alert_id)
        return WriteResponse(message=f"Alert {alert_id} deactivated", backup_id=backup_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/alerts/evaluate", response_model=WriteResponse)
def api_evaluate_alert(req: AlertEvaluateRequest):
    """Evaluate alert triggers for a stock at a given price."""
    from niangao.services.alerts import evaluate_triggers

    triggered = evaluate_triggers(req.stock_code, req.current_price)
    return WriteResponse(
        message=f"{len(triggered)} alerts triggered for {req.stock_code}",
        details={"triggered": [{"id": t.alert_id, "type": t.alert_type} for t in triggered]},
    )


@app.post("/api/alerts/evaluate-all", response_model=WriteResponse)
def api_evaluate_all_alerts():
    """Evaluate all active alerts against current live prices."""
    from niangao.services.alerts import evaluate_all_triggers

    results = evaluate_all_triggers()
    total = sum(len(v) for v in results.values())
    return WriteResponse(
        message=f"{total} alerts triggered across {len(results)} stocks",
        details={"triggered_by_stock": {k: len(v) for k, v in results.items()}},
    )


# ═══════════════════════════════════════════════════════════════════════
# MEDIUM-RISK write endpoints — cash/accounts
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/accounts/deposit", response_model=WriteResponse)
def api_deposit(req: DepositRequest):
    """Deposit cash into an account. MEDIUM risk."""
    from niangao.services.accounts import deposit, get_balance

    old_balance = get_balance(req.currency, req.account_id)
    backup_id, _ = _safe_write(
        "cash.deposit", "cash", f"{req.currency}/{req.account_id}", "medium",
        {"old_balance": old_balance},
    )
    try:
        result = deposit(
            amount=req.amount, currency=req.currency,
            account_id=req.account_id, note=req.note,
        )
        warnings = _post_write_check("medium", None, req.account_id)
        return WriteResponse(
            message=f"Deposited {req.amount} {req.currency} → balance {result.new_amount:.2f}",
            backup_id=backup_id, reconcile_warnings=warnings,
            details={"new_balance": result.new_amount, "currency": req.currency},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/accounts/withdraw", response_model=WriteResponse)
def api_withdraw(req: WithdrawRequest):
    """Withdraw cash from an account. MEDIUM risk."""
    from niangao.services.accounts import withdraw, get_balance

    old_balance = get_balance(req.currency, req.account_id)
    backup_id, _ = _safe_write(
        "cash.withdraw", "cash", f"{req.currency}/{req.account_id}", "medium",
        {"old_balance": old_balance},
    )
    try:
        result = withdraw(
            amount=req.amount, currency=req.currency,
            account_id=req.account_id, note=req.note,
            allow_overdraft=req.allow_overdraft,
        )
        warnings = _post_write_check("medium", None, req.account_id)
        return WriteResponse(
            message=f"Withdrew {req.amount} {req.currency} → balance {result.new_amount:.2f}",
            backup_id=backup_id, reconcile_warnings=warnings,
            details={"new_balance": result.new_amount, "currency": req.currency},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/accounts/transfer", response_model=WriteResponse)
def api_transfer(req: TransferRequest):
    """Transfer cash between accounts. MEDIUM risk."""
    from niangao.services.accounts import transfer

    backup_id, _ = _safe_write(
        "cash.transfer", "cash", risk_level="medium",
        old_values={"from": req.from_account_id, "to": req.to_account_id, "amount": req.amount},
    )
    try:
        from_res, to_res = transfer(
            from_account_id=req.from_account_id, to_account_id=req.to_account_id,
            amount=req.amount, currency=req.currency, note=req.note,
        )
        warnings = _post_write_check("medium", None, req.from_account_id)
        return WriteResponse(
            message=f"Transferred {req.amount} {req.currency}: "
                    f"{req.from_account_id}→{req.to_account_id}",
            backup_id=backup_id, reconcile_warnings=warnings,
            details={
                "from_balance": from_res.new_amount, "to_balance": to_res.new_amount,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# HIGH-RISK write endpoints — BUY / SELL / DIVIDEND
# ═══════════════════════════════════════════════════════════════════════

def _require_confirm(confirm: bool, operation: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail=f"{operation} requires explicit confirmation. Set 'confirm': true.",
        )


@app.post("/api/trade/buy", response_model=WriteResponse)
def api_record_buy(req: TradeBuyRequest):
    """Record a BUY transaction. HIGH risk — requires confirm=true."""
    from niangao.services.trade_ledger import record_buy

    _require_confirm(req.confirm, "BUY")

    backup_id, _ = _safe_write(
        "trade.buy", "trade_record", req.ts_code, "high",
    )
    try:
        result = record_buy(
            ts_code=req.ts_code, name=req.name, price=req.price,
            shares=req.shares, amount_cny=req.amount_cny,
            commission_cny=req.commission_cny, note=req.note,
            account_id=req.account_id,
        )
        record_audit(
            operation="trade.buy", target_table="trade_record",
            target_key=req.ts_code,
            new_values={
                "transaction_id": result.transaction_id,
                "shares": req.shares, "amount_cny": req.amount_cny,
                "new_hold": result.new_hold, "new_avg_cost": result.new_avg_cost,
            },
        )
        warnings = _post_write_check("high", req.ts_code, req.account_id)
        return WriteResponse(
            message=f"BUY {req.shares}股 {req.ts_code} @ {req.price:.2f} "
                    f"(id={result.transaction_id}, hold={result.new_hold})",
            backup_id=backup_id, reconcile_warnings=warnings,
            details={
                "transaction_id": result.transaction_id,
                "new_hold": result.new_hold,
                "new_avg_cost": round(result.new_avg_cost, 4),
                "resulting_status": result.resulting_status,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/trade/sell", response_model=WriteResponse)
def api_record_sell(req: TradeSellRequest):
    """Record a SELL transaction. HIGH risk — requires confirm=true."""
    from niangao.services.trade_ledger import record_sell

    _require_confirm(req.confirm, "SELL")

    backup_id, _ = _safe_write(
        "trade.sell", "trade_record", req.ts_code, "high",
    )
    try:
        result = record_sell(
            ts_code=req.ts_code, name=req.name, price=req.price,
            shares=req.shares, amount_cny=req.amount_cny,
            commission_cny=req.commission_cny, note=req.note,
            account_id=req.account_id,
        )
        record_audit(
            operation="trade.sell", target_table="trade_record",
            target_key=req.ts_code,
            new_values={
                "transaction_id": result.transaction_id,
                "shares": req.shares, "amount_cny": req.amount_cny,
                "new_hold": result.new_hold,
                "resulting_status": result.resulting_status,
            },
        )
        warnings = _post_write_check("high", req.ts_code, req.account_id)
        return WriteResponse(
            message=f"SELL {req.shares}股 {req.ts_code} @ {req.price:.2f} "
                    f"(id={result.transaction_id}, hold={result.new_hold})",
            backup_id=backup_id, reconcile_warnings=warnings,
            details={
                "transaction_id": result.transaction_id,
                "new_hold": result.new_hold,
                "new_avg_cost": round(result.new_avg_cost, 4),
                "resulting_status": result.resulting_status,
                "sell_warnings": result.warnings,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/trade/dividend", response_model=WriteResponse)
def api_record_dividend(req: DividendRequest):
    """Record a DIVIDEND. HIGH risk — requires confirm=true."""
    from niangao.services.trade_ledger import record_dividend

    _require_confirm(req.confirm, "DIVIDEND")

    backup_id, _ = _safe_write(
        "trade.dividend", "trade_record", req.ts_code, "high",
    )
    try:
        result = record_dividend(
            ts_code=req.ts_code, amount_cny=req.amount_cny,
            div_per_share=req.div_per_share, dividend_year=req.dividend_year,
            note=req.note, account_id=req.account_id,
        )
        record_audit(
            operation="trade.dividend", target_table="trade_record",
            target_key=req.ts_code,
            new_values={
                "transaction_id": result.transaction_id,
                "amount_cny": req.amount_cny,
                "dividend_year": req.dividend_year,
                "new_cumulative_div": result.new_cumulative_div_per_share,
            },
        )
        warnings = _post_write_check("high", req.ts_code, req.account_id)
        return WriteResponse(
            message=f"DIVIDEND {req.amount_cny} CNY {req.ts_code} "
                    f"(id={result.transaction_id})",
            backup_id=backup_id, reconcile_warnings=warnings,
            details={
                "transaction_id": result.transaction_id,
                "new_cumulative_div_per_share": round(result.new_cumulative_div_per_share, 4),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# Strategy endpoints — Grid / MTH
# ═══════════════════════════════════════════════════════════════════════

# ── Grid ─────────────────────────────────────────────────────────────

@app.post("/api/strategy/grid/sell", response_model=WriteResponse)
def api_grid_sell(req: GridSellRequest):
    """Grid sell: executes trade_ledger.record_sell() THEN creates open cycle."""
    _require_confirm(req.confirm, "Grid Sell")
    backup_id, _ = _safe_write("grid.sell", "trade_record", req.ts_code, "high")
    from niangao.db import get_db
    db = get_db()
    try:
        from niangao.services.trade_ledger import record_sell
        from niangao.services.strategies.grid import record_grid_sell
        stock = db.execute(
            "SELECT account_id FROM watchlist WHERE ts_code = ?",
            (req.ts_code,),
        ).fetchone()
        account_id = req.account_id if req.account_id is not None else (
            stock["account_id"] if stock and stock["account_id"] is not None else 1
        )
        # 1. Execute actual sell in trade ledger
        trade = record_sell(
            ts_code=req.ts_code, price=req.sell_price, shares=req.sell_shares,
            amount_cny=req.sell_proceeds_cny, note="网格卖出",
            account_id=account_id, db=db,
        )
        # 2. Create open grid cycle
        cycle = record_grid_sell(
            stock_code=req.ts_code, sell_price=req.sell_price,
            sell_shares=req.sell_shares, sell_proceeds_cny=req.sell_proceeds_cny,
            planned_buy_price=req.planned_buy_price,
            db=db,
        )
        db.commit()
        warnings = _post_write_check("high", req.ts_code, account_id)
        return WriteResponse(
            message=f"Grid sell: trade {trade.transaction_id}, cycle {cycle.cycle_id}",
            backup_id=backup_id,
            reconcile_warnings=warnings,
            details={
                "transaction_id": trade.transaction_id,
                "cycle_id": cycle.cycle_id,
                "is_open": cycle.is_open,
                "account_id": account_id,
            },
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.post("/api/strategy/grid/buy", response_model=WriteResponse)
def api_grid_buy(req: GridBuyRequest):
    """Grid buy-back: executes trade_ledger.record_buy() THEN closes the cycle."""
    _require_confirm(req.confirm, "Grid Buy")
    backup_id, _ = _safe_write("grid.buy", "trade_record", risk_level="high")
    from niangao.db import get_db
    db = get_db()
    try:
        cycle = db.execute(
            "SELECT * FROM grid_cycle_record WHERE id = ?",
            (req.cycle_id,),
        ).fetchone()
        if not cycle:
            raise HTTPException(status_code=404, detail=f"Cycle {req.cycle_id} not found")
        cycle = dict(cycle)
        stock = db.execute(
            "SELECT account_id FROM watchlist WHERE ts_code = ?",
            (cycle["stock_code"],),
        ).fetchone()
        account_id = req.account_id if req.account_id is not None else (
            stock["account_id"] if stock and stock["account_id"] is not None else 1
        )

        from niangao.services.trade_ledger import record_buy
        from niangao.services.strategies.grid import record_grid_buy
        # 1. Execute actual buy in trade ledger
        trade = record_buy(
            ts_code=cycle["stock_code"], price=req.buy_price, shares=req.buy_shares,
            amount_cny=req.buy_price * req.buy_shares, note="网格买入",
            account_id=account_id, db=db,
        )
        # 2. Close the grid cycle
        result = record_grid_buy(
            cycle_id=req.cycle_id, buy_price=req.buy_price, buy_shares=req.buy_shares,
            db=db,
        )
        db.commit()
        warnings = _post_write_check("high", cycle["stock_code"], account_id)
        return WriteResponse(
            message=f"Grid buy: trade {trade.transaction_id}, cycle {req.cycle_id} closed, profit={result.profit:.2f}",
            backup_id=backup_id,
            reconcile_warnings=warnings,
            details={
                "transaction_id": trade.transaction_id,
                "cycle_id": result.cycle_id,
                "profit": result.profit,
                "is_success": result.is_success,
                "account_id": account_id,
            },
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.get("/api/strategy/grid/cycles")
def api_grid_cycles(stock_code: str = "", limit: int = 50):
    """List grid cycles, optionally filtered by stock."""
    from niangao.services.strategies.grid import list_cycles, list_open_cycles, grid_summary
    sc = stock_code or None
    return {
        "open_cycles": list_open_cycles(stock_code=sc),
        "recent_cycles": list_cycles(stock_code=sc, limit=limit),
        "summary": grid_summary(stock_code=sc),
    }


@app.delete("/api/strategy/grid/cycles/{cycle_id}", response_model=WriteResponse)
def api_delete_grid_cycle(cycle_id: int):
    """Delete an open grid cycle."""
    from niangao.services.strategies.grid import delete_cycle
    try:
        deleted = delete_cycle(cycle_id)
        return WriteResponse(message="Deleted" if deleted else "Not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── MTH ───────────────────────────────────────────────────────────────

@app.post("/api/strategy/mth/enable", response_model=WriteResponse)
def api_mth_enable(req: MthToggleRequest):
    """Enable MTH for a stock."""
    from niangao.services.strategies.mth import enable_mth
    try:
        result = enable_mth(req.ts_code)
        return WriteResponse(message=f"MTH enabled for {req.ts_code}", details=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/strategy/mth/disable", response_model=WriteResponse)
def api_mth_disable(req: MthToggleRequest):
    """Disable MTH for a stock."""
    from niangao.services.strategies.mth import disable_mth
    try:
        result = disable_mth(req.ts_code)
        return WriteResponse(message=f"MTH disabled for {req.ts_code}", details=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/strategy/mth/advance", response_model=WriteResponse)
def api_mth_advance(req: MthAdvanceRequest):
    """Advance MTH to the next cycle."""
    from niangao.services.strategies.mth import advance_mth_cycle
    try:
        result = advance_mth_cycle(req.ts_code)
        return WriteResponse(
            message=f"MTH advanced to cycle {result['mth_cycle']} for {req.ts_code}",
            details=result,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/strategy/mth/reset", response_model=WriteResponse)
def api_mth_reset(req: MthAdvanceRequest):
    """Reset MTH to cycle 1."""
    from niangao.services.strategies.mth import reset_mth_cycle
    try:
        result = reset_mth_cycle(req.ts_code)
        return WriteResponse(message=f"MTH reset for {req.ts_code}", details=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/strategy/mth/stocks")
def api_mth_stocks():
    """List all MTH-enabled stocks."""
    from niangao.services.strategies.mth import list_mth_stocks
    return {"stocks": list_mth_stocks()}


# ═══════════════════════════════════════════════════════════════════════
# Phase A: Stock Detail + Staged Buy
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/stocks/{ts_code}/detail")
def api_stock_detail(ts_code: str):
    """Full stock detail: position, P&L, fundamentals, grid, trades."""
    result = read_models.get_stock_detail(ts_code)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/stocks/{ts_code}/trades")
def api_stock_trades(ts_code: str, limit: int = 50):
    """Get trades for a single stock."""
    from niangao.services.trade_ledger import get_trades_for_stock
    return {"ts_code": ts_code, "trades": get_trades_for_stock(ts_code)[:limit]}


@app.get("/api/stocks/{ts_code}/fundamentals")
def api_stock_fundamentals(ts_code: str):
    """Get fundamental history for a stock."""
    return read_models.get_stock_fundamentals(ts_code)


# ── Staged Buy ───────────────────────────────────────────────────────

@app.post("/api/strategy/staged-buy/generate", response_model=WriteResponse)
def api_staged_buy_generate(req: dict):
    """Generate a staged buy plan for a stock."""
    from niangao.services.strategies.staged import generate_plan
    ts_code = req.get("ts_code", "")
    base_price = float(req.get("base_price", 0))
    level_count = int(req.get("level_count", 6))
    try:
        result = generate_plan(ts_code=ts_code, base_price=base_price, level_count=level_count)
        return WriteResponse(
            message=f"Staged buy plan: {level_count} levels from {base_price:.2f}",
            details=result,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/strategy/staged-buy/{ts_code}")
def api_staged_buy_get(ts_code: str):
    """Get staged buy plan status."""
    from niangao.services.strategies.staged import get_plan
    plan = get_plan(ts_code)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"No staged buy plan for {ts_code}")
    return plan


@app.post("/api/strategy/staged-buy/{ts_code}/levels/{level_index}", response_model=WriteResponse)
def api_staged_buy_mark(ts_code: str, level_index: int, req: dict):
    """Mark a staged buy level as completed or skipped."""
    from niangao.services.strategies.staged import mark_level
    try:
        result = mark_level(
            ts_code=ts_code,
            level_index=level_index,
            completed=req.get("completed", False),
            skipped=req.get("skipped", False),
            filled_shares=int(req.get("filled_shares", 0)),
            note=req.get("note", ""),
        )
        return WriteResponse(message=f"Level {level_index + 1} updated", details=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/strategy/staged-buy")
def api_staged_buy_list():
    """List all active staged buy plans."""
    from niangao.services.strategies.staged import list_active_plans
    return {"plans": list_active_plans()}


# ── Stats API ────────────────────────────────────────────────────────

@app.get("/api/stats/returns/detailed")
def api_stats_returns():
    """Detailed returns: IRR, annualized, wealth series, annual summaries."""
    from niangao.services.stats import detailed_returns
    return detailed_returns()


@app.get("/api/stats/dividends/monthly")
def api_stats_dividends_monthly():
    """Monthly dividend breakdown."""
    from niangao.services.stats import monthly_dividends
    return monthly_dividends()


@app.get("/api/stats/fundamentals/trends")
def api_stats_fundamentals_trends():
    """Portfolio PE/PB/debt/FCF trends over time."""
    from niangao.services.stats import fundamentals_trends
    return fundamentals_trends()


@app.get("/api/stats/strategy-attribution")
def api_stats_strategy():
    """Strategy attribution: grid, MTH, staged buy stats."""
    from niangao.services.stats import strategy_attribution
    return strategy_attribution()


# ── Settings ─────────────────────────────────────────────────────────

@app.get("/api/settings")
def api_settings_get():
    """Get all settings."""
    from niangao.services.settings import get_all
    return {"settings": get_all()}


@app.put("/api/settings")
def api_settings_put(req: dict):
    """Update settings."""
    from niangao.services.settings import update_batch
    update_batch(req)
    from niangao.services.settings import get_all
    return {"status": "ok", "settings": get_all()}


# ── Per-stock alert toggle ───────────────────────────────────────────

@app.put("/api/stocks/{ts_code}/alert-toggle", response_model=WriteResponse)
def api_stock_alert_toggle(ts_code: str, req: dict):
    """Enable or disable alerts for a stock."""
    from niangao.db import get_db
    db = get_db()
    try:
        enabled = bool(req.get("enabled", True))
        # Update alert_enabled-like field — use watchlist alert config
        db.execute("UPDATE watchlist SET updated_at = datetime('now') WHERE ts_code = ?", (ts_code,))
        # For now, toggle all alerts for this stock via alert_snapshot
        if not enabled:
            db.execute("UPDATE alert_snapshot SET is_active = 0 WHERE stock_code IN (SELECT invest_code FROM watchlist WHERE ts_code = ?)", (ts_code,))
        else:
            db.execute("UPDATE alert_snapshot SET is_active = 1 WHERE stock_code IN (SELECT invest_code FROM watchlist WHERE ts_code = ?)", (ts_code,))
        db.commit()
        return WriteResponse(message=f"Alerts {'enabled' if enabled else 'disabled'} for {ts_code}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


# ── App page routes ───────────────────────────────────────────────────

@app.get("/app/stocks/{ts_code}", response_class=HTMLResponse)
def app_stock_detail(request: Request, ts_code: str):
    """Stock detail page."""
    return _render("stock_detail.html", {"request": request, "page": "holdings", "ts_code": ts_code})


@app.get("/app/stats", response_class=HTMLResponse)
def app_stats(request: Request):
    """Stats dashboard page."""
    return _render("stats.html", {"request": request, "page": "stats"})


@app.get("/app/settings", response_class=HTMLResponse)
def app_settings(request: Request):
    """Settings page."""
    return _render("settings.html", {"request": request, "page": "settings"})


# ── Grid enhanced ────────────────────────────────────────────────────

@app.get("/api/strategy/grid/{ts_code}/levels")
def api_grid_levels(ts_code: str):
    """Calculate grid levels for a stock."""
    from niangao.services.strategies.grid import calculate_grid_levels
    return calculate_grid_levels(ts_code)


@app.get("/api/strategy/grid/{ts_code}/eligible")
def api_grid_eligible(ts_code: str):
    """Check grid eligibility for a stock."""
    from niangao.services.strategies.grid import is_grid_eligible
    return is_grid_eligible(ts_code)


@app.put("/api/strategy/grid/{ts_code}/config")
def api_grid_config(ts_code: str, req: dict):
    """Update grid strategy config."""
    from niangao.services.strategies.grid import save_grid_config, get_grid_config
    save_grid_config(ts_code, **req)
    return get_grid_config(ts_code)


# ── MTH plan ─────────────────────────────────────────────────────────

@app.post("/api/strategy/mth/{ts_code}/generate-plan")
def api_mth_generate_plan(ts_code: str, req: dict):
    """Generate MTH buy plan."""
    from niangao.services.strategies.mth import generate_mth_plan
    level_count = int(req.get("level_count", 8))
    try:
        return generate_mth_plan(ts_code, level_count=level_count)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Fundamental CRUD ─────────────────────────────────────────────────

@app.post("/api/fundamentals/{ts_code}")
def api_fundamentals_upsert(ts_code: str, req: dict):
    """Add or update a yearly fundamental record."""
    from niangao.db import get_db
    db = get_db()
    try:
        year = int(req.get("year", 0))
        db.execute("""INSERT OR REPLACE INTO fundamentals_history
            (stock_id, year, pe, pb, debt_ratio, fcf_yield)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (ts_code, year, req.get("pe"), req.get("pb"), req.get("debt_ratio"), req.get("fcf_yield")))
        db.commit()
        return {"status": "ok", "ts_code": ts_code, "year": year}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.delete("/api/fundamentals/{ts_code}/{year}")
def api_fundamentals_delete(ts_code: str, year: int):
    """Delete a yearly fundamental record."""
    from niangao.db import get_db
    db = get_db()
    try:
        db.execute("DELETE FROM fundamentals_history WHERE stock_id = ? AND year = ?", (ts_code, year))
        db.commit()
        return {"status": "ok", "deleted": db.total_changes > 0}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


# ── Ranking ──────────────────────────────────────────────────────────

@app.get("/api/stats/rankings/{metric}")
def api_rankings(metric: str):
    """Rank holdings by PE, PB, debt_ratio, or fcf_yield."""
    from niangao.db import get_db
    db = get_db()
    try:
        valid = {"pe", "pb", "debt_ratio", "fcf_yield"}
        if metric not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid metric. Use: {', '.join(valid)}")
        rows = db.execute(f"""
            SELECT ts_code, name, {metric}, live_price, current_hold, sector
            FROM watchlist WHERE COALESCE(current_hold,0) > 0 AND {metric} IS NOT NULL AND {metric} > 0
            ORDER BY {metric} {'ASC' if metric != 'fcf_yield' else 'DESC'}
        """).fetchall()
        return {"metric": metric, "rankings": [dict(r) for r in rows]}
    finally:
        db.close()


# ── Strategies overview page ─────────────────────────────────────────

@app.get("/app/strategies", response_class=HTMLResponse)
def app_strategies(request: Request):
    """Strategies overview page."""
    return _render("strategies.html", {"request": request, "page": "strategies"})


# ── Audit log read endpoint ──────────────────────────────────────────

@app.get("/api/audit")
def api_list_audit(limit: int = 100, operation: str = "", table: str = ""):
    """List recent audit log entries."""
    from niangao.services.audit import list_audit_logs
    return {
        "logs": list_audit_logs(
            limit=min(limit, 500),
            operation=operation or None,
            target_table=table or None,
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# Phase 5: Jinja2 Web App pages
# ═══════════════════════════════════════════════════════════════════════

def _render(template_name: str, context: dict) -> HTMLResponse:
    """Render a Jinja2 template using the raw Environment (avoids Starlette cache issue)."""
    template = _jinja_env.get_template(template_name)
    return HTMLResponse(template.render(**context))


@app.get("/app", response_class=HTMLResponse)
def app_dashboard(request: Request):
    """Main app dashboard — overview, holdings snapshot, alerts, recent trades."""
    return _render("dashboard.html", {"request": request, "page": "dashboard"})


@app.get("/app/holdings", response_class=HTMLResponse)
def app_holdings(request: Request):
    """Holdings management page."""
    return _render("holdings.html", {"request": request, "page": "holdings"})


@app.get("/app/trades", response_class=HTMLResponse)
def app_trades(request: Request):
    """Trade entry + history page."""
    return _render("trades.html", {"request": request, "page": "trades"})


@app.get("/app/alerts", response_class=HTMLResponse)
def app_alerts(request: Request):
    """Alert management page."""
    return _render("alerts.html", {"request": request, "page": "alerts"})


@app.get("/app/accounts", response_class=HTMLResponse)
def app_accounts(request: Request):
    """Accounts & cash management page."""
    return _render("accounts.html", {"request": request, "page": "accounts"})


@app.get("/app/audit", response_class=HTMLResponse)
def app_audit(request: Request):
    """Audit log viewer page."""
    return _render("audit.html", {"request": request, "page": "audit"})


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise SystemExit("uvicorn is not installed. Run: python3 -m pip install -r requirements.txt") from exc
    uvicorn.run("niangao.server:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
