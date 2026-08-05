"""niangao.api_models — FastAPI response models for the read-only web API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str
    dashboard: str
    export_json: str


class OverviewResponse(BaseModel):
    updated_at: str
    total_rows: int
    analyzed_total: int
    holding_count: int
    analyzed_holding: int
    unanalyzed_holding: int
    stale_count: int
    decisions: dict[str, int]
    portfolio_gg: dict[str, Any]
    assets: dict[str, Any]


class HoldingRow(BaseModel):
    ts_code: str
    invest_code: str | None = None
    name: str = ""
    market: str = ""
    holding: int = 0
    avg_cost: float | None = None
    live_price: float | None = None
    gg: float | None = None
    ii: float | None = None
    buy_price: float | None = None
    buy_star: int | None = None
    upside_pct: float | None = None
    decision: str | None = None
    position_pct: float | None = None
    analyzed_at: str | None = None
    row_type: str = ""
    has_analysis: bool = False


class HoldingsResponse(BaseModel):
    count: int
    rows: list[HoldingRow]


class AlertsResponse(BaseModel):
    active_count: int
    triggered_count: int
    active: list[dict[str, Any]]
    triggered: list[dict[str, Any]]
    action_cards: list[dict[str, Any]] = Field(default_factory=list)
    triggered_cards: list[dict[str, Any]] = Field(default_factory=list)
    pending_alerts: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class TransactionsResponse(BaseModel):
    count: int
    rows: list[dict[str, Any]]


class AccountsResponse(BaseModel):
    accounts: list[dict[str, Any]]
    cash: list[dict[str, Any]]


class ReturnsResponse(BaseModel):
    returns: dict[str, Any]
    position_pnl: list[dict[str, Any]] = Field(default_factory=list)
    realized_pnl: list[dict[str, Any]] = Field(default_factory=list)
    dividends: list[dict[str, Any]] = Field(default_factory=list)


class ExportResponse(BaseModel):
    cash: dict[str, Any]
    stocks: list[dict[str, Any]]


class ReconcileResponse(BaseModel):
    status: str
    invest_db: str
    portfolio_db: str
    checks: list[dict[str, Any]]


# ── Write API request models ──────────────────────────────────────────

class StockUpsertRequest(BaseModel):
    ts_code: str
    name: str = ""
    market: str = ""
    invest_code: str = ""
    invest_status: str = "WATCHING"
    current_hold: int = 0
    avg_cost: float = 0.0
    hold_limit_pct: float = 0.05
    annual_div_per_share: float = 0.0
    invest_logic: str = ""
    my_valuation: float = 0.0
    turtle_valuation: float = 0.0
    live_price: float = 0.0
    sector: str = ""
    stock_type: str = ""
    pe: float | None = None
    pb: float | None = None
    debt_ratio: float | None = None
    fcf_yield: float | None = None
    mth_enabled: bool = False
    mth_cycle: int = 1
    lock_reserve: bool = True
    cumulative_div: float = 0.0
    dividend_tax_rate: float = 0.0
    account_id: int = 1


class ValuationUpdateRequest(BaseModel):
    ts_code: str
    my_valuation: float | None = None
    turtle_valuation: float | None = None
    invest_logic: str | None = None


class StatusUpdateRequest(BaseModel):
    ts_code: str
    invest_status: str


class LivePriceUpdateRequest(BaseModel):
    ts_code: str
    live_price: float


class BatchPriceUpdateRequest(BaseModel):
    prices: dict[str, float]  # {ts_code: price}


class AlertCreateRequest(BaseModel):
    stock_code: str
    alert_type: str
    target_price: float | None = None
    stock_name: str = ""


class AlertTriggerRequest(BaseModel):
    alert_id: int
    current_price: float


class AlertEvaluateRequest(BaseModel):
    stock_code: str
    current_price: float


class DepositRequest(BaseModel):
    amount: float
    currency: str = "CNY"
    account_id: int = 1
    note: str = ""


class WithdrawRequest(BaseModel):
    amount: float
    currency: str = "CNY"
    account_id: int = 1
    note: str = ""
    allow_overdraft: bool = False


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float
    currency: str = "CNY"
    note: str = ""


class TradeBuyRequest(BaseModel):
    ts_code: str
    name: str = ""
    price: float
    shares: int
    amount_cny: float
    commission_cny: float = 0.0
    note: str | None = None
    account_id: int = 1
    confirm: bool = False  # Must be explicitly True for high-risk operations


class TradeSellRequest(BaseModel):
    ts_code: str
    name: str = ""
    price: float
    shares: int
    amount_cny: float
    commission_cny: float = 0.0
    note: str | None = None
    account_id: int = 1
    confirm: bool = False


class DividendRequest(BaseModel):
    ts_code: str
    amount_cny: float
    div_per_share: float = 0.0
    dividend_year: int | None = None
    note: str | None = None
    account_id: int = 1
    confirm: bool = False


class WriteResponse(BaseModel):
    status: str = "ok"
    message: str = ""
    backup_id: str | None = None
    reconcile_warnings: list[str] = []
    details: dict[str, Any] = Field(default_factory=dict)


# ── Strategy API request models ──────────────────────────────────────

class GridSellRequest(BaseModel):
    ts_code: str
    sell_price: float
    sell_shares: int
    sell_proceeds_cny: float
    planned_buy_price: float | None = None
    account_id: int | None = None
    confirm: bool = False


class GridBuyRequest(BaseModel):
    cycle_id: int
    buy_price: float
    buy_shares: int
    account_id: int | None = None
    confirm: bool = False


class MthToggleRequest(BaseModel):
    ts_code: str


class MthAdvanceRequest(BaseModel):
    ts_code: str
