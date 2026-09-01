#!/usr/bin/env python3
"""技术分析工具集 — MA / RSI / MACD / Bollinger。

默认用于阶段 9 的可选技术面附录：
- 允许直接传 prices_json 做纯本地计算
- 若未传 prices_json，则尝试根据 ts_code/output_dir 从 Tushare 拉取行情
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

_scripts_dir = os.path.join(os.path.dirname(__file__), '..', '..')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

_ANALY_DIR = os.path.normpath(os.path.join(_scripts_dir, "..", ".."))
_STOCK_SDK_BRIDGE = os.path.join(
    _ANALY_DIR,
    "_niangao",
    "niangao",
    "infra",
    "market_data",
    "providers",
    "stock_sdk_bridge.mjs",
)


def _read_json(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_ts_code(output_dir: str = '.', ts_code: str = '') -> str:
    if ts_code:
        return ts_code
    contract = _read_json(os.path.join(output_dir, 'analysis_contract.json'))
    if contract and contract.get('ts_code'):
        return str(contract['ts_code'])
    base = os.path.basename(os.path.abspath(output_dir))
    code = base.split('_', 1)[0] if '_' in base else base
    if '.' in code:
        return code
    if len(code) <= 5 and code.startswith('0'):
        return code + '.HK'
    if code.startswith('6'):
        return code + '.SH'
    if code.startswith('0') or code.startswith('3'):
        return code + '.SZ'
    return code


def _is_hk_code(ts_code: str) -> bool:
    return str(ts_code or "").upper().endswith(".HK")


def _load_stock_sdk_price_frame(ts_code: str, window: str, lookback: int) -> pd.DataFrame:
    if not _is_hk_code(ts_code):
        raise ValueError("stock-sdk fallback currently enabled for HK codes only")
    if not os.path.exists(_STOCK_SDK_BRIDGE):
        raise ValueError(f"stock-sdk bridge not found: {_STOCK_SDK_BRIDGE}")
    period = "weekly" if window == "weekly" else "daily"
    proc = subprocess.run(
        [
            "node",
            _STOCK_SDK_BRIDGE,
            "kline",
            ts_code,
            "--period",
            period,
            "--limit",
            str(max(lookback, 60)),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0 or not str(proc.stdout or "").strip():
        raise ValueError("stock-sdk kline bridge returned no stdout")
    payload = json.loads(proc.stdout)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        error_text = payload.get("error") if isinstance(payload, dict) else "empty data"
        raise ValueError(f"stock-sdk kline bridge empty: {error_text}")
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("stock-sdk kline dataframe empty")
    if "trade_date" not in df.columns or "close" not in df.columns:
        raise ValueError("stock-sdk kline missing trade_date/close")
    return df


def _load_price_frame(
    output_dir: str = '.',
    ts_code: str = '',
    prices_json: str = '',
    window: str = 'weekly',
    lookback: int = 260,
) -> pd.DataFrame:
    if prices_json:
        raw = json.loads(prices_json) if isinstance(prices_json, str) else prices_json
        if not isinstance(raw, list):
            raise ValueError('prices_json 必须是数组 JSON')
        df = pd.DataFrame(raw)
    else:
        code = _resolve_ts_code(output_dir, ts_code)
        if not code:
            raise ValueError('无法确定 ts_code，请传 ts_code 或 output_dir')
        df = pd.DataFrame()
        if _is_hk_code(code):
            try:
                df = _load_stock_sdk_price_frame(code, window, lookback)
            except Exception:
                df = pd.DataFrame()
        if df.empty:
            from config import get_token, get_api_url
            import tushare as ts
            pro = ts.pro_api(token=get_token(), timeout=30)
            api_url = get_api_url()
            if api_url and hasattr(pro, '_DataApi__http_url'):
                pro._DataApi__http_url = api_url
            end = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=max(lookback * 7, 400))).strftime('%Y%m%d')
            api_name = 'weekly' if window == 'weekly' else 'daily'
            api_func = getattr(pro, api_name)
            df = api_func(ts_code=code, start_date=start, end_date=end, fields='trade_date,close,vol,amount')

    if df.empty:
        raise ValueError('价格数据为空')
    if 'trade_date' not in df.columns or 'close' not in df.columns:
        raise ValueError('价格数据必须包含 trade_date 和 close 列')
    df = df.copy()
    df['trade_date'] = df['trade_date'].astype(str)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df = df.dropna(subset=['close']).sort_values('trade_date').reset_index(drop=True)
    if len(df) < 5:
        raise ValueError('价格样本不足，至少需要 5 个点')
    return df.tail(lookback).reset_index(drop=True)


def calc_ma(
    output_dir: str = '.',
    ts_code: str = '',
    prices_json: str = '',
    window: str = 'weekly',
    short_period: int = 20,
    long_period: int = 60,
    lookback: int = 260,
) -> dict[str, Any]:
    df = _load_price_frame(output_dir, ts_code, prices_json, window, lookback)
    if len(df) < max(short_period, long_period):
        raise ValueError('价格样本不足以计算均线')
    df['ma_short'] = df['close'].rolling(short_period).mean()
    df['ma_long'] = df['close'].rolling(long_period).mean()
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    crossover = 'none'
    if prev['ma_short'] <= prev['ma_long'] and latest['ma_short'] > latest['ma_long']:
        crossover = 'golden_cross'
    elif prev['ma_short'] >= prev['ma_long'] and latest['ma_short'] < latest['ma_long']:
        crossover = 'death_cross'
    trend = 'bullish' if latest['ma_short'] > latest['ma_long'] else 'bearish'
    return {
        'ts_code': _resolve_ts_code(output_dir, ts_code),
        'window': window,
        'latest_trade_date': latest['trade_date'],
        'latest_close': round(float(latest['close']), 4),
        'ma_short': round(float(latest['ma_short']), 4),
        'ma_long': round(float(latest['ma_long']), 4),
        'trend': trend,
        'crossover': crossover,
        'sample_size': len(df),
    }


def calc_rsi(
    output_dir: str = '.',
    ts_code: str = '',
    prices_json: str = '',
    window: str = 'daily',
    period: int = 14,
    lookback: int = 120,
) -> dict[str, Any]:
    df = _load_price_frame(output_dir, ts_code, prices_json, window, lookback)
    if len(df) < period + 2:
        raise ValueError('价格样本不足以计算 RSI')
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    latest = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
    signal = 'overbought' if latest >= 70 else 'oversold' if latest <= 30 else 'neutral'
    return {
        'ts_code': _resolve_ts_code(output_dir, ts_code),
        'window': window,
        'period': period,
        'latest_trade_date': df.iloc[-1]['trade_date'],
        'latest_rsi': round(latest, 4),
        'signal': signal,
        'sample_size': len(df),
    }


def calc_macd(
    output_dir: str = '.',
    ts_code: str = '',
    prices_json: str = '',
    window: str = 'daily',
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    lookback: int = 180,
) -> dict[str, Any]:
    df = _load_price_frame(output_dir, ts_code, prices_json, window, lookback)
    if len(df) < slow_period + signal_period:
        raise ValueError('价格样本不足以计算 MACD')
    ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    hist = macd_line - signal_line
    latest_idx = len(df) - 1
    macd_value = float(macd_line.iloc[latest_idx])
    signal_value = float(signal_line.iloc[latest_idx])
    hist_value = float(hist.iloc[latest_idx])
    trend = 'bullish' if macd_value > signal_value and hist_value >= 0 else 'bearish'
    return {
        'ts_code': _resolve_ts_code(output_dir, ts_code),
        'window': window,
        'latest_trade_date': df.iloc[-1]['trade_date'],
        'macd': round(macd_value, 6),
        'signal': round(signal_value, 6),
        'histogram': round(hist_value, 6),
        'trend': trend,
        'sample_size': len(df),
    }


def calc_bollinger(
    output_dir: str = '.',
    ts_code: str = '',
    prices_json: str = '',
    window: str = 'daily',
    period: int = 20,
    num_std: float = 2.0,
    lookback: int = 120,
) -> dict[str, Any]:
    df = _load_price_frame(output_dir, ts_code, prices_json, window, lookback)
    if len(df) < period:
        raise ValueError('价格样本不足以计算布林带')
    mid = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    latest = df.iloc[-1]
    mid_v = float(mid.iloc[-1])
    upper_v = float(upper.iloc[-1])
    lower_v = float(lower.iloc[-1])
    close_v = float(latest['close'])
    bandwidth = (upper_v - lower_v) / mid_v * 100 if mid_v else 0.0
    position = 'upper_breakout' if close_v > upper_v else 'lower_breakdown' if close_v < lower_v else 'inside_band'
    return {
        'ts_code': _resolve_ts_code(output_dir, ts_code),
        'window': window,
        'period': period,
        'latest_trade_date': latest['trade_date'],
        'latest_close': round(close_v, 4),
        'mid_band': round(mid_v, 4),
        'upper_band': round(upper_v, 4),
        'lower_band': round(lower_v, 4),
        'bandwidth_pct': round(bandwidth, 4),
        'position': position,
        'sample_size': len(df),
    }


calc_ma._tool_meta = {
    'name': 'calc_ma',
    'description': '计算移动均线并判断多空趋势/金叉死叉。支持 prices_json 本地输入或按 ts_code 拉取行情。',
    'parameters': {
        'output_dir': {'type': 'string', 'description': '股票输出目录', 'optional': True},
        'ts_code': {'type': 'string', 'description': '股票代码', 'optional': True},
        'prices_json': {'type': 'string', 'description': '价格数组 JSON', 'optional': True},
        'window': {'type': 'string', 'description': 'daily 或 weekly', 'optional': True},
        'short_period': {'type': 'integer', 'description': '短均线周期', 'optional': True},
        'long_period': {'type': 'integer', 'description': '长均线周期', 'optional': True},
    },
}
calc_rsi._tool_meta = {
    'name': 'calc_rsi',
    'description': '计算 RSI 并输出超买/超卖信号。',
    'parameters': {
        'output_dir': {'type': 'string', 'description': '股票输出目录', 'optional': True},
        'ts_code': {'type': 'string', 'description': '股票代码', 'optional': True},
        'prices_json': {'type': 'string', 'description': '价格数组 JSON', 'optional': True},
        'window': {'type': 'string', 'description': 'daily 或 weekly', 'optional': True},
        'period': {'type': 'integer', 'description': 'RSI 周期', 'optional': True},
    },
}
calc_macd._tool_meta = {
    'name': 'calc_macd',
    'description': '计算 MACD、Signal、Histogram，并判断动量方向。',
    'parameters': {
        'output_dir': {'type': 'string', 'description': '股票输出目录', 'optional': True},
        'ts_code': {'type': 'string', 'description': '股票代码', 'optional': True},
        'prices_json': {'type': 'string', 'description': '价格数组 JSON', 'optional': True},
        'window': {'type': 'string', 'description': 'daily 或 weekly', 'optional': True},
        'fast_period': {'type': 'integer', 'description': '快线周期', 'optional': True},
        'slow_period': {'type': 'integer', 'description': '慢线周期', 'optional': True},
        'signal_period': {'type': 'integer', 'description': '信号线周期', 'optional': True},
    },
}
calc_bollinger._tool_meta = {
    'name': 'calc_bollinger',
    'description': '计算布林带上下轨、带宽与价格位置。',
    'parameters': {
        'output_dir': {'type': 'string', 'description': '股票输出目录', 'optional': True},
        'ts_code': {'type': 'string', 'description': '股票代码', 'optional': True},
        'prices_json': {'type': 'string', 'description': '价格数组 JSON', 'optional': True},
        'window': {'type': 'string', 'description': 'daily 或 weekly', 'optional': True},
        'period': {'type': 'integer', 'description': '布林带周期', 'optional': True},
        'num_std': {'type': 'number', 'description': '标准差倍数', 'optional': True},
    },
}


def build_technical_snapshot(
    output_dir: str = '.',
    ts_code: str = '',
    prices_json: str = '',
) -> dict[str, Any]:
    """Build technical snapshot JSON + Markdown appendix for report assembly."""
    resolved = _resolve_ts_code(output_dir, ts_code)
    snapshot: dict[str, Any] = {
        'ts_code': resolved,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'signals': {},
        'status': 'ok',
    }
    errors: list[str] = []

    try:
        snapshot['signals']['ma_weekly'] = calc_ma(output_dir=output_dir, ts_code=resolved, prices_json=prices_json, window='weekly', short_period=5, long_period=20)
    except Exception as exc:
        errors.append(f'ma_weekly: {exc}')
    try:
        snapshot['signals']['rsi_daily'] = calc_rsi(output_dir=output_dir, ts_code=resolved, prices_json=prices_json, window='daily', period=14)
    except Exception as exc:
        errors.append(f'rsi_daily: {exc}')
    try:
        snapshot['signals']['macd_daily'] = calc_macd(output_dir=output_dir, ts_code=resolved, prices_json=prices_json, window='daily')
    except Exception as exc:
        errors.append(f'macd_daily: {exc}')
    try:
        snapshot['signals']['bollinger_daily'] = calc_bollinger(output_dir=output_dir, ts_code=resolved, prices_json=prices_json, window='daily')
    except Exception as exc:
        errors.append(f'bollinger_daily: {exc}')

    if errors:
        snapshot['errors'] = errors
        if not snapshot['signals']:
            snapshot['status'] = 'degraded'

    json_path = os.path.join(output_dir, '_technical_snapshot.json')
    os.makedirs(output_dir, exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)

    lines = [
        '## 技术分析附录',
        '',
        f"- 技术快照状态：`{snapshot['status']}`，生成时间 {snapshot['generated_at']} [source: _technical_snapshot.json]",
    ]
    if snapshot['signals'].get('ma_weekly'):
        ma = snapshot['signals']['ma_weekly']
        lines.append(f"- 周线均线：收盘价 {ma['latest_close']}，短均线 {ma['ma_short']}，长均线 {ma['ma_long']}，趋势 `{ma['trend']}`，交叉 `{ma['crossover']}` [source: _technical_snapshot.json]")
    if snapshot['signals'].get('rsi_daily'):
        rsi = snapshot['signals']['rsi_daily']
        lines.append(f"- RSI：{rsi['latest_rsi']}，信号 `{rsi['signal']}`，窗口 `{rsi['window']}` [source: _technical_snapshot.json]")
    if snapshot['signals'].get('macd_daily'):
        macd = snapshot['signals']['macd_daily']
        lines.append(f"- MACD：macd={macd['macd']}，signal={macd['signal']}，hist={macd['histogram']}，趋势 `{macd['trend']}` [source: _technical_snapshot.json]")
    if snapshot['signals'].get('bollinger_daily'):
        bb = snapshot['signals']['bollinger_daily']
        lines.append(f"- 布林带：上轨 {bb['upper_band']} / 中轨 {bb['mid_band']} / 下轨 {bb['lower_band']}，位置 `{bb['position']}`，带宽 {bb['bandwidth_pct']}% [source: _technical_snapshot.json]")
    if errors:
        lines.extend(['', '### 技术信号缺口', ''])
        for err in errors:
            lines.append(f'- {err} [source: _technical_snapshot.json]')

    md_path = os.path.join(output_dir, '_technical_appendix.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).strip() + '\n')


    return {
        'ok': True,
        'status': snapshot['status'],
        'json_path': json_path,
        'markdown_path': md_path,
        'signals': list(snapshot['signals'].keys()),
        'errors': errors,
    }


build_technical_snapshot._tool_meta = {
    'name': 'build_technical_snapshot',
    'description': '生成技术分析快照 JSON 与 Markdown 附录文件，供最终报告拼接。',
    'parameters': {
        'output_dir': {'type': 'string', 'description': '股票输出目录'},
        'ts_code': {'type': 'string', 'description': '股票代码', 'optional': True},
        'prices_json': {'type': 'string', 'description': '价格数组 JSON', 'optional': True},
    },
}
