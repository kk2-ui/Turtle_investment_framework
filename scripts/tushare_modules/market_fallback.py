"""Turtle Investment Framework - MarketFallbackMixin.

HK/US market-data capability probing and lightweight external fallback helpers.
This layer does not assume any provider is always available; instead it records
what was attempted and what actually worked so downstream markdown can explain
why market sections are missing.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pandas as pd


class MarketFallbackMixin:
    """Mixin for probing market-data sources and fetching web fallbacks."""

    def _set_market_source_status(self, key: str, value) -> None:
        status = self._store.setdefault("_market_source_status", {})
        status[key] = value

    def _get_market_source_status(self) -> dict:
        return self._store.get("_market_source_status", {})

    def _mark_market_attempt(self, source: str, ok: bool, detail: str = "") -> None:
        attempts = self._store.setdefault("_market_source_attempts", [])
        attempts.append({
            "source": source,
            "ok": ok,
            "detail": detail,
        })

    def _get_market_attempts(self) -> list[dict]:
        return self._store.get("_market_source_attempts", [])

    def _probe_hk_tushare_market_capability(self, ts_code: str) -> dict:
        """Probe whether HK Tushare market endpoints actually return rows."""
        cache_key = f"_hk_market_capability::{ts_code}"
        cached = self._store.get(cache_key)
        if cached is not None:
            return cached

        capability = {
            "hk_daily": False,
            "hk_fina_indicator": False,
            "details": {},
        }

        try:
            daily = self._safe_call(
                "hk_daily",
                ts_code=ts_code,
                start_date=(pd.Timestamp.now() - pd.DateOffset(days=30)).strftime("%Y%m%d"),
                end_date=pd.Timestamp.now().strftime("%Y%m%d"),
                fields="ts_code,trade_date,open,high,low,close,vol,amount",
            )
            capability["hk_daily"] = not daily.empty
            capability["details"]["hk_daily_rows"] = len(daily)
        except Exception as e:
            capability["details"]["hk_daily_error"] = str(e)

        try:
            fina = self._safe_call(
                "hk_fina_indicator",
                ts_code=ts_code,
                fields="ts_code,end_date,pe_ttm,pb_ttm,total_market_cap,hksk_market_cap",
            )
            capability["hk_fina_indicator"] = not fina.empty
            capability["details"]["hk_fina_indicator_rows"] = len(fina)
        except Exception as e:
            capability["details"]["hk_fina_indicator_error"] = str(e)

        self._store[cache_key] = capability
        self._set_market_source_status("hk_tushare_market_capability", capability)
        return capability

    def _web_yahoo_chart(self, symbol: str, range_: str, interval: str) -> dict | None:
        """Fetch Yahoo chart JSON directly, best-effort only."""
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{symbol}?range={range_}&interval={interval}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as e:
            self._mark_market_attempt("yahoo_chart", False, f"HTTP {e.code}")
            return None
        except Exception as e:
            self._mark_market_attempt("yahoo_chart", False, str(e))
            return None

        result = ((payload or {}).get("chart") or {}).get("result") or []
        if not result:
            self._mark_market_attempt("yahoo_chart", False, "empty result")
            return None
        self._mark_market_attempt("yahoo_chart", True, f"{symbol} {range_} {interval}")
        return result[0]

    def _web_hk_market_snapshot(self, ts_code: str) -> dict | None:
        """Best-effort HK price snapshot from Yahoo chart meta."""
        symbol = self._yf_ticker(ts_code)
        payload = self._web_yahoo_chart(symbol, "1mo", "1d")
        if not payload:
            return None
        meta = payload.get("meta") or {}
        quote = ((payload.get("indicators") or {}).get("quote") or [{}])[0]
        closes = [v for v in (quote.get("close") or []) if v is not None]
        return {
            "close": meta.get("regularMarketPrice") or (closes[-1] if closes else None),
            "high_52w": meta.get("fiftyTwoWeekHigh") or meta.get("yearHigh"),
            "low_52w": meta.get("fiftyTwoWeekLow") or meta.get("yearLow"),
            "market_cap": meta.get("marketCap"),
            "currency": meta.get("currency"),
            "source": "yahoo_chart_web",
        }

    def _web_weekly_history(self, ts_code: str) -> pd.DataFrame:
        """Best-effort weekly history from Yahoo chart API."""
        symbol = self._yf_ticker(ts_code)
        payload = self._web_yahoo_chart(symbol, "10y", "1wk")
        if not payload:
            return pd.DataFrame()

        timestamps = payload.get("timestamp") or []
        quote = ((payload.get("indicators") or {}).get("quote") or [{}])[0]
        if not timestamps:
            return pd.DataFrame()

        df = pd.DataFrame({
            "trade_date": pd.to_datetime(timestamps, unit="s").strftime("%Y%m%d"),
            "open": quote.get("open") or [],
            "high": quote.get("high") or [],
            "low": quote.get("low") or [],
            "close": quote.get("close") or [],
            "vol": quote.get("volume") or [],
        })
        if df.empty:
            return df
        df["ts_code"] = ts_code
        return df[["ts_code", "trade_date", "open", "high", "low", "close", "vol"]].dropna(subset=["close"])

    def _hk_report_market_derived_fields(self, ts_code: str) -> dict:
        """Derive shares / EPS / BPS from HK annual-report fallback JSON."""
        payload = self._load_hk_report_fallback(ts_code) or {}
        income_rows = payload.get("income") or []
        indicator_rows = payload.get("fina_indicators") or []
        balance_rows = payload.get("balance_sheet") or []

        latest_income = income_rows[0] if income_rows else {}
        latest_indicator = indicator_rows[0] if indicator_rows else {}
        latest_balance = balance_rows[0] if balance_rows else {}

        def _f(val):
            try:
                num = float(val)
                return None if num != num else num
            except Exception:
                return None

        eps = _f(latest_income.get("basic_eps"))
        bps = _f(latest_indicator.get("bps"))
        np_attr = _f(latest_income.get("n_income_attr_p"))
        shares = None

        if eps and eps > 0 and np_attr and np_attr > 0:
            shares = np_attr / eps

        if (bps is None or bps <= 0) and shares and shares > 0:
            equity = _f(latest_balance.get("total_hldr_eqy_exc_min_int"))
            if equity is not None:
                bps = equity / shares

        return {
            "shares": shares,
            "eps": eps,
            "bps": bps,
            "end_date": latest_income.get("end_date") or latest_indicator.get("end_date"),
            "source": "hk_report_fallback",
        }
