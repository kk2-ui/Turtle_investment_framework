#!/usr/bin/env python3
"""pre_analysis_phase.py — Phase 0: Adaptive Analysis Horizon Pre-Diagnosis (V9).

Scans full financial history from DB, detects structural breakpoints,
computes cyclicality classification via revenue CV, and outputs an
analysis_contract.json with dynamic year windows and three-track setup.

Usage:
    python3 scripts/pre_analysis_phase.py --code 00816.HK
    python3 scripts/pre_analysis_phase.py --code 00816.HK --output output/00816_金茂服务
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from statistics import mean, stdev
from typing import Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

# ── Dual-dimension cyclicality classification (V1.1) ───────────────────────────
# Supply volatility (CV) × Demand driver type → final classification + window N

# Demand driver keyword matching (based on industry name)
DEMAND_DRIVER_KEYWORDS = {
    "地产后周期": [
        "空调", "白电", "白色家电", "家电", "家用电器",
        "建材", "家居", "五金", "卫浴", "厨电", "照明",
    ],
    "大宗商品驱动": [
        "能源", "有色", "化工", "煤炭", "石油", "钢铁", "矿业",
        "天然气", "黄金", "铜", "铝", "锂",
    ],
    "资本开支驱动": [
        "工程机械", "工业设备", "机床", "重型", "船舶", "机车",
        "半导体设备", "自动化",
    ],
    "政策驱动": [
        "新能源车", "光伏", "风电", "锂电池", "储能", "充电桩",
    ],
}

# Classification matrix: (supply_cv_high, demand_driver) → (label, window_n)
# "high" CV = profit CV > 0.40 (same threshold as before)
CLASSIFICATION_MATRIX = {
    (True,  "大宗商品驱动"): ("强周期", 10),
    (True,  "资本开支驱动"): ("强周期", 10),
    (True,  "政策驱动"):     ("中周期偏强", 9),
    (True,  "地产后周期"):   ("中周期偏强", 8),
    (True,  "纯消费驱动"):   ("中周期偏弱", 7),
    (False, "大宗商品驱动"): ("中周期偏强", 8),
    (False, "资本开支驱动"): ("中周期偏弱", 7),
    (False, "政策驱动"):     ("中周期偏弱", 7),
    (False, "地产后周期"):   ("中周期偏弱", 7),
    (False, "纯消费驱动"):   ("弱周期", 5),
}

# Weight config by tier (for three-track analysis)
TIER_WEIGHTS = {
    "强周期":     {"weight_near": 0.40, "weight_far": 0.60, "near_years": 3},
    "中周期偏强":  {"weight_near": 0.45, "weight_far": 0.55, "near_years": 3},
    "中周期偏弱":  {"weight_near": 0.55, "weight_far": 0.45, "near_years": 3},
    "弱周期":     {"weight_near": 0.60, "weight_far": 0.40, "near_years": 3},
}

# Profit smoothing (P1: V9.2 resilience bonus replaces V1.1 downgrade)
SMOOTHING_RESILIENCE_THRESHOLD = 0.10  # >10% smooth = management resilience
SMOOTHING_SYNCHRONOUS_THRESHOLD = 0.05  # <5% = revenue and profit move together

# Growth override: if revenue_3y_cagr > 15%, force window_n=5
GROWTH_CAGR_THRESHOLD = 0.15
GROWTH_WINDOW_N = 5

# Structural break detection thresholds
GOODWILL_JUMP_THRESHOLD = 0.20   # goodwill change / prev total_assets
ASSET_JUMP_THRESHOLD = 0.50      # total_assets YoY change
REVENUE_DECOUPLING_RATIO = 0.30  # revenue growth must be < this when assets jump

# Always-keep marginal window (Factor 1C)
MARGINAL_WINDOW_N = 5


def _safe_float(val) -> float:
    """Return float value or 0.0 for None."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def load_financials(ts_code: str, db_path: str = DB_PATH
                     ) -> Tuple[List[dict], Optional[int], Optional[str]]:
    """Load all annual financial data for a stock, ordered by fiscal_year.

    Returns:
        (financials_list, listing_year, industry_l1)
    """
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT fiscal_year, revenue, n_income_attr_p, total_assets, total_liab,
                  total_hldr_eqy_exc_min_int, goodwill, n_cashflow_act,
                  c_pay_acq_const_fiolta, gross_margin, d_a, dividends_paid, eps, dps
           FROM annual_financials
           WHERE ts_code=? AND report_type='annual'
           ORDER BY fiscal_year""",
        (ts_code,)
    ).fetchall()

    # Get listing year
    listing_row = conn.execute(
        "SELECT listing_date FROM stocks WHERE ts_code=?", (ts_code,)
    ).fetchone()
    listing_year = None
    if listing_row and listing_row["listing_date"]:
        try:
            listing_year = int(str(listing_row["listing_date"])[:4])
        except (ValueError, IndexError):
            pass

    # Get industry
    ind_row = conn.execute(
        "SELECT industry_l1, industry_l2 FROM industry_classification WHERE ts_code=?",
        (ts_code,)
    ).fetchone()
    industry_l1 = ind_row["industry_l1"] if ind_row else None
    industry_l2 = ind_row["industry_l2"] if ind_row else None

    conn.close()

    financials = [
        {k: row[k] for k in row.keys()}
        for row in rows
    ]

    return financials, listing_year, industry_l1, industry_l2


def detect_structural_breaks(financials: List[dict]
                               ) -> Tuple[List[dict], int]:
    """Detect structural breakpoints in financial history.

    Returns:
        (breakpoints_list, analysis_start_year)
    """
    breaks: List[dict] = []
    if len(financials) < 2:
        return breaks, financials[0]["fiscal_year"] if financials else 0

    for i in range(1, len(financials)):
        prev, curr = financials[i - 1], financials[i]
        prev_ta = _safe_float(prev.get("total_assets"))
        curr_ta = _safe_float(curr.get("total_assets"))
        prev_gw = _safe_float(prev.get("goodwill"))
        curr_gw = _safe_float(curr.get("goodwill"))
        prev_rev = _safe_float(prev.get("revenue"))
        curr_rev = _safe_float(curr.get("revenue"))

        if prev_ta <= 0:
            continue

        # Check 1: Goodwill jump (M&A acquisition)
        gw_change = abs(curr_gw - prev_gw) / prev_ta
        if gw_change > GOODWILL_JUMP_THRESHOLD:
            breaks.append({
                "year": curr["fiscal_year"],
                "type": "goodwill_spike",
                "detail": f"商誉 {prev_gw:.0f}M→{curr_gw:.0f}M "
                          f"(变动幅度 {gw_change*100:.1f}% of 总资产)",
            })

        # Check 2: Asset jump without corresponding revenue growth
        ta_change = abs(curr_ta - prev_ta) / prev_ta
        rev_change = abs(curr_rev - prev_rev) / prev_rev if prev_rev > 0 else 0
        if ta_change > ASSET_JUMP_THRESHOLD and rev_change < REVENUE_DECOUPLING_RATIO:
            breaks.append({
                "year": curr["fiscal_year"],
                "type": "major_restructuring",
                "detail": f"总资产变动 {ta_change*100:.1f}%，但收入变动仅 {rev_change*100:.1f}%",
            })

    # Analysis start year = max(IPO year or earliest data, last_break_year + 1)
    earliest_year = financials[0]["fiscal_year"]
    last_break_year = max((b["year"] for b in breaks), default=0)
    start_year = max(earliest_year, last_break_year + 1)

    return breaks, start_year


def detect_segment_breaks(segment_data: Optional[List[dict]],
                           threshold: float = 0.50) -> List[dict]:
    """V9.2 V4: Detect structural breaks from segment revenue share changes.

    Uses RELATIVE change (not absolute pp): if a segment's revenue share
    changes by >threshold (default 50% relative), it flags a breakpoint.

    Examples:
      - 葡萄酒 30%→15%: relative_change = |15-30|/30 = 50% → triggers ✓
      - 饮料 75%→80%: relative_change = |80-75|/75 = 6.7% → no trigger

    Args:
        segment_data: List of per-year dicts, each with:
            {"fiscal_year": int, "segments": [{"name": str, "revenue_pct": float}]}
        threshold: Relative share change threshold (default 0.50 = 50%).

    Returns:
        List of breakpoint dicts.
    """
    if not segment_data or len(segment_data) < 2:
        return []

    # Sort by fiscal year
    sorted_data = sorted(segment_data, key=lambda d: d.get("fiscal_year", 0))
    breaks = []

    for i in range(1, len(sorted_data)):
        prev_year = sorted_data[i - 1]
        curr_year = sorted_data[i]
        prev_segments = {s.get("name", ""): s.get("revenue_pct", 0) or 0
                          for s in prev_year.get("segments", [])}
        curr_segments = {s.get("name", ""): s.get("revenue_pct", 0) or 0
                          for s in curr_year.get("segments", [])}

        if not prev_segments or not curr_segments:
            continue

        # Check each segment's RELATIVE share change
        all_names = set(prev_segments.keys()) | set(curr_segments.keys())
        for name in all_names:
            prev_pct = prev_segments.get(name, 0)
            curr_pct = curr_segments.get(name, 0)

            # Segment disappearing entirely (prev>0 → curr=0)
            if prev_pct > 0 and curr_pct == 0:
                breaks.append({
                    "year": curr_year["fiscal_year"],
                    "type": "segment_shift",
                    "detail": f"分部「{name}」完全剥离（{prev_pct:.0f}%→0%）",
                })
                break

            # Relative change
            if prev_pct > 0:
                rel_change = abs(curr_pct - prev_pct) / prev_pct
                if rel_change > threshold:
                    direction = "增加" if curr_pct > prev_pct else "下降"
                    breaks.append({
                        "year": curr_year["fiscal_year"],
                        "type": "segment_shift",
                        "detail": (f"分部「{name}」收入占比 {direction} "
                                   f"{rel_change*100:.0f}% "
                                   f"({prev_pct:.0f}%→{curr_pct:.0f}%)"),
                    })
                    break  # one break per year is enough

    return breaks


def classify_demand_driver(industry_l1: Optional[str],
                            industry_l2: Optional[str]) -> str:
    """Match stock to demand driver type via industry keyword matching.

    Scans L1 and L2 industry names against DEMAND_DRIVER_KEYWORDS.
    Returns '纯消费驱动' as default if no keywords match.
    """
    text = f"{industry_l1 or ''} {industry_l2 or ''}"
    for driver, keywords in DEMAND_DRIVER_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return driver
    return "纯消费驱动"


# ── P2: Multi-driver weighted voting (V9.2) ───────────────────────────────────
# Some industries span multiple demand drivers. Weighted voting adjusts the
# analysis window by each driver's influence, rather than picking a single label.

# Industry → {driver: weight} mapping for mixed industries
MULTI_DRIVER_RULES = {
    "家电":     {"地产后周期": 0.6, "纯消费驱动": 0.4},
    "白色家电":  {"地产后周期": 0.6, "纯消费驱动": 0.4},
    "家用电器":  {"地产后周期": 0.6, "纯消费驱动": 0.4},
    "建材":     {"地产后周期": 0.7, "资本开支驱动": 0.3},
    "家居":     {"地产后周期": 0.6, "纯消费驱动": 0.4},
    "五金":     {"地产后周期": 0.5, "资本开支驱动": 0.3, "纯消费驱动": 0.2},
    "工程机械":  {"地产后周期": 0.4, "资本开支驱动": 0.6},
    "汽车配件":  {"地产后周期": 0.3, "纯消费驱动": 0.4, "资本开支驱动": 0.3},
    "电气设备":  {"地产后周期": 0.3, "资本开支驱动": 0.5, "纯消费驱动": 0.2},
    "半导体":   {"资本开支驱动": 0.5, "纯消费驱动": 0.3, "政策驱动": 0.2},
    "软件服务":  {"纯消费驱动": 0.8, "资本开支驱动": 0.2},
}


def classify_demand_drivers_weighted(industry_l1: Optional[str],
                                       industry_l2: Optional[str]) -> dict:
    """V9.2: Weighted voting for demand drivers based on industry.

    Returns dict of {driver: weight} for portfolio-style window_n computation.
    If no multi-driver rule matches, returns {single_driver: 1.0}.
    """
    text = f"{industry_l1 or ''} {industry_l2 or ''}"

    # Check multi-driver rules first
    for industry, weights in MULTI_DRIVER_RULES.items():
        if industry in text:
            return dict(weights)

    # Fallback to single driver
    driver = classify_demand_driver(industry_l1, industry_l2)
    return {driver: 1.0}


def compute_weighted_window(demand_drivers: dict, profit_cv: float) -> float:
    """Compute weighted window_n from demand driver mix.

    For each driver, look up its window_n in CLASSIFICATION_MATRIX
    (using cv_high=True for conservative estimate), then weighted average.
    """
    cv_high = profit_cv > 0.40
    total_weight = sum(demand_drivers.values())
    if total_weight == 0:
        return 7.0

    weighted_n = 0.0
    for driver, weight in demand_drivers.items():
        key = (cv_high, driver)
        if key in CLASSIFICATION_MATRIX:
            _, wn = CLASSIFICATION_MATRIX[key]
        else:
            _, wn = CLASSIFICATION_MATRIX.get((cv_high, "纯消费驱动"), ("", 7))
        weighted_n += wn * weight

    return round(weighted_n / total_weight, 1)


def compute_profit_smoothing(financials: List[dict]) -> Optional[float]:
    """利润平滑系数 = mean(|Δ营收% - Δ利润%|) of last 5 years.

    High smoothing means the company can keep profits steady even when
    revenue fluctuates (e.g., via cost control, pricing power, inventory
    management). This indicates "cycle resilience" and may justify a
    lower cyclicality classification.

    Returns None if insufficient data.
    """
    rev_vals = []
    np_vals = []
    for r in financials[-6:]:  # need 6 rows for 5 deltas
        rev = _safe_float(r.get("revenue"))
        np_val = _safe_float(r.get("n_income_attr_p"))
        if rev > 0 and np_val != 0:
            rev_vals.append(rev)
            np_vals.append(np_val)

    if len(rev_vals) < 3:
        return None

    deltas = []
    for i in range(len(rev_vals) - 1):
        rev_chg = abs(rev_vals[i + 1] - rev_vals[i]) / rev_vals[i]
        np_chg = abs(np_vals[i + 1] - np_vals[i]) / abs(np_vals[i]) if np_vals[i] != 0 else 0
        deltas.append(abs(rev_chg - np_chg))

    if not deltas:
        return None
    return round(mean(deltas), 4)


def compute_cyclicality_profile(financials: List[dict],
                                  industry_l1: Optional[str] = None,
                                  industry_l2: Optional[str] = None) -> dict:
    """Compute dual-dimension cyclicality classification (V1.1).

    1. Compute profit CV (supply-side volatility)
    2. Classify demand driver type from industry keywords
    3. Look up classification matrix → label + window_n
    4. Compute profit smoothing coefficient
    5. Apply downgrade if smoothing > 10%
    6. Apply growth override if 3y revenue CAGR > 15%

    Returns dict with all classification details.
    """
    profits = [
        _safe_float(r.get("n_income_attr_p"))
        for r in financials
        if _safe_float(r.get("n_income_attr_p")) != 0
    ]
    revenues = [
        _safe_float(r.get("revenue"))
        for r in financials
        if _safe_float(r.get("revenue")) > 0
    ]

    if len(profits) < 3 or len(revenues) < 3:
        return {
            "revenue_cv": None,
            "profit_cv": None,
            "cv_tier": "insufficient_data",
            "label": "数据不足",
            "demand_driver": None,
            "demand_drivers": {},
            "window_n": max(len(financials), 3),
            "weight_near": 1.0, "weight_far": 0.0, "near_years": len(financials),
            "smoothing_coefficient": None,
            "resilience_bonus": False,
        }

    rev_cv = round(stdev(revenues) / mean(revenues), 3) if mean(revenues) > 0 else 0.0
    profit_cv = round(stdev(profits) / mean(profits), 3) if mean(profits) > 0 else 0.0

    # Check growth override first: revenue_3y_cagr > 15%
    if len(revenues) >= 3:
        rev_recent = revenues[-3:]
        if rev_recent[0] > 0:
            cagr_3y = (rev_recent[-1] / rev_recent[0]) ** (1 / 2) - 1
            if cagr_3y > GROWTH_CAGR_THRESHOLD:
                dd = classify_demand_driver(industry_l1, industry_l2)
                return {
                    "revenue_cv": rev_cv,
                    "profit_cv": profit_cv,
                    "cv_tier": "growth",
                    "label": "成长型（3年收入CAGR>15%）",
                    "demand_driver": dd,
                    "demand_drivers": {dd: 1.0},
                    "window_n": GROWTH_WINDOW_N,
                    "weight_near": 1.0, "weight_far": 0.0,
                    "near_years": GROWTH_WINDOW_N,
                    "smoothing_coefficient": None,
                    "resilience_bonus": False,
                    "revenue_3y_cagr": round(cagr_3y * 100, 1),
                }

    # Step 1: Demand driver classification
    demand_driver = classify_demand_driver(industry_l1, industry_l2)
    demand_drivers = classify_demand_drivers_weighted(industry_l1, industry_l2)

    # Step 2: CV threshold (high = profit CV > 0.40)
    cv_high = profit_cv > 0.40

    # Step 3: Look up matrix (primary driver)
    matrix_key = (cv_high, demand_driver)
    label, window_n = CLASSIFICATION_MATRIX.get(
        matrix_key, ("中周期偏弱", 7)  # fallback
    )

    # Step 3b: Weighted window if multi-driver (V9.2)
    window_n_weighted = compute_weighted_window(demand_drivers, profit_cv)
    if len(demand_drivers) > 1:
        window_n = round(window_n_weighted)  # use weighted average
        label = f"{label}（加权）"

    # Step 4: Profit smoothing → resilience bonus (V9.2)
    # 营收震荡但利润平稳 = 管理层熨平周期的能力强 → +1年观察窗口
    # 营收和利润同步共振 = 标准窗口
    smoothing = compute_profit_smoothing(financials)
    resilience_bonus = False
    if (smoothing is not None
            and smoothing > SMOOTHING_RESILIENCE_THRESHOLD
            and profit_cv < 1.0):
        window_n += 1  # longer observation window to verify resilience
        resilience_bonus = True

    # Step 5: Weight config
    weights = TIER_WEIGHTS.get(label.replace("（加权）", ""),
                                {"weight_near": 0.50, "weight_far": 0.50, "near_years": 3})

    return {
        "revenue_cv": rev_cv,
        "profit_cv": profit_cv,
        "cv_tier": label,
        "label": label,
        "demand_driver": demand_driver,
        "demand_drivers": demand_drivers,
        "window_n": window_n,
        "window_n_weighted": window_n_weighted if len(demand_drivers) > 1 else None,
        "weight_near": weights["weight_near"],
        "weight_far": weights["weight_far"],
        "near_years": weights["near_years"],
        "smoothing_coefficient": smoothing,
        "resilience_bonus": resilience_bonus,
    }


def detect_anomaly_years(financials: List[dict]) -> List[dict]:
    """Flag years with extreme values that may distort analysis.

    Currently flags: revenue decline > 30% YoY (COVID, crisis years).
    """
    anomalies = []
    for i in range(1, len(financials)):
        prev, curr = financials[i - 1], financials[i]
        prev_rev = _safe_float(prev.get("revenue"))
        curr_rev = _safe_float(curr.get("revenue"))
        if prev_rev > 0:
            change = (curr_rev - prev_rev) / prev_rev
            if change < -0.30:
                anomalies.append({
                    "year": curr["fiscal_year"],
                    "type": "revenue_crash",
                    "detail": f"收入同比下降 {abs(change)*100:.0f}%",
                })
    return anomalies


def load_segment_data(ts_code: str) -> Optional[List[dict]]:
    """Load multi-year segment data from stock output directory (Zone B output).

    Looks for segments.json which may contain either:
      - Single year: {"fiscal_year": 2025, "segments": [...]}
      - Multi-year: {"years": {"2024": {"segments": [...]}, "2025": {...}}}
    Returns list of per-year dicts, or None if no segment data available.
    """
    stock_dir = find_stock_dir(ts_code)
    if not stock_dir:
        return None

    seg_path = os.path.join(stock_dir, "segments.json")
    if not os.path.exists(seg_path):
        return None

    try:
        with open(seg_path) as f:
            data = json.load(f)
    except Exception:
        return None

    # Multi-year format
    if "years" in data:
        return [
            {"fiscal_year": int(yr), "segments": yr_data.get("segments", [])}
            for yr, yr_data in data["years"].items()
        ]

    # Single-year format
    if "segments" in data:
        fy = data.get("fiscal_year")
        if fy:
            return [{"fiscal_year": int(fy), "segments": data["segments"]}]

    return None


def build_analysis_contract(ts_code: str, db_path: str = DB_PATH,
                              segment_data: Optional[List[dict]] = None) -> dict:
    """Build the full analysis contract for a stock.

    This is the main entry point — called by CLI and by downstream scripts.

    Args:
        ts_code: Stock code.
        db_path: Path to SQLite database.
        segment_data: Optional pre-loaded segment data (for post-Zone-B re-run).
    """
    financials, listing_year, industry_l1, industry_l2 = load_financials(
        ts_code, db_path
    )
    if not financials:
        return {"error": f"no_financial_data_for_{ts_code}"}

    all_years = [r["fiscal_year"] for r in financials]
    breaks, start_year = detect_structural_breaks(financials)

    # V4: Segment-based break detection (requires Zone B segments.json)
    segment_data = segment_data or load_segment_data(ts_code)
    if segment_data:
        seg_breaks = detect_segment_breaks(segment_data)
        breaks.extend(seg_breaks)
        # Remove duplicate breaks (same year + type)
        seen = set()
        unique_breaks = []
        for b in breaks:
            key = (b["year"], b["type"])
            if key not in seen:
                seen.add(key)
                unique_breaks.append(b)
        breaks = unique_breaks
        # Recompute start_year if segment breaks push it forward
        last_break_year = max((b["year"] for b in breaks), default=0)
        start_year = max(start_year, last_break_year + 1)

    cyclicality = compute_cyclicality_profile(financials, industry_l1, industry_l2)
    anomalies = detect_anomaly_years(financials)

    # Effective years: from analysis_start_year to latest, capped by window_n
    window_n = cyclicality["window_n"]
    latest_year = all_years[-1] if all_years else 0

    # Apply start_year constraint
    constrained_years = [y for y in all_years if y >= start_year]

    effective_years = constrained_years[-window_n:] if len(constrained_years) > window_n else constrained_years

    # Three-track setup
    track_c_years = [y for y in all_years if y >= max(latest_year - MARGINAL_WINDOW_N + 1, all_years[0])]
    track_a_years = constrained_years  # all years after breakpoint
    track_b_years = effective_years

    contract = {
        "ts_code": ts_code,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "full_range": {
            "start": all_years[0] if all_years else None,
            "end": latest_year,
            "n_years": len(all_years),
        },
        "listing_year": listing_year,
        "structural_breakpoints": breaks,
        "analysis_start_year": start_year,
        "effective_years": effective_years,
        "cyclicality_profile": cyclicality,
        "three_track": {
            "track_a_long_term": {
                "years": track_a_years,
                "n": len(track_a_years),
                "weight": "equal",
                "description": "断点后全部年份，用于因子1B（护城河/ROE均值）",
            },
            "track_b_cycle": {
                "years": track_b_years,
                "n": len(track_b_years),
                "weight": f"near_{cyclicality['near_years']}y:{cyclicality['weight_near']*100:.0f}%_"
                         f"far_{len(track_b_years)-cyclicality['near_years']}y:{cyclicality['weight_far']*100:.0f}%",
                "description": "动态窗口，用于因子2（粗算估值锚/周期定位）",
            },
            "track_c_marginal": {
                "years": track_c_years,
                "n": MARGINAL_WINDOW_N,
                "weight": "equal",
                "description": "固定近5年（或可用年份），用于因子1C（增量ROIC）",
            },
        },
        "exclude_years": [],
        "anomaly_flags": anomalies,
        "industry_classification": {
            "l1": industry_l1,
            "l2": industry_l2,
            "peer_group": industry_l2 or industry_l1,
        },
    }

    return contract


def find_stock_dir(ts_code: str) -> Optional[str]:
    """Find output directory for a stock."""
    code_base = ts_code.split(".")[0]
    for name in os.listdir(OUTPUT_BASE):
        full = os.path.join(OUTPUT_BASE, name)
        if os.path.isdir(full) and name.startswith(code_base):
            return full
    return None


def main():
    p = argparse.ArgumentParser(
        description="Phase 0: Adaptive Analysis Horizon Pre-Diagnosis"
    )
    p.add_argument("--code", required=True, help="Stock code (e.g. 00816.HK)")
    p.add_argument("--output", help="Output directory (auto-detected if omitted)")
    p.add_argument("--verbose", "-v", action="store_true", help="Print contract summary")
    p.add_argument("--segment-data", help="Path to segments.json (V4: segment break detection)")
    args = p.parse_args()

    # V4: Load segment data for breakpoint detection
    segment_data = None
    if args.segment_data and os.path.exists(args.segment_data):
        with open(args.segment_data) as f:
            seg_raw = json.load(f)
        # Normalize to list of per-year dicts
        if "years" in seg_raw:
            segment_data = [
                {"fiscal_year": int(yr), "segments": yr_data.get("segments", [])}
                for yr, yr_data in seg_raw["years"].items()
            ]
        elif "segments" in seg_raw:
            fy = seg_raw.get("fiscal_year")
            segment_data = [{"fiscal_year": int(fy), "segments": seg_raw["segments"]}]

    contract = build_analysis_contract(args.code, segment_data=segment_data)

    if "error" in contract:
        print(f"ERROR: {contract['error']}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    out_dir = args.output or find_stock_dir(args.code) or OUTPUT_BASE
    out_path = os.path.join(out_dir, "analysis_contract.json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2, ensure_ascii=False, default=str)

    if args.verbose:
        cyc = contract["cyclicality_profile"]
        print(f"✅ analysis_contract.json → {out_path}")
        print(f"   TS: {contract['ts_code']}")
        print(f"   全量: {contract['full_range']['start']}-{contract['full_range']['end']} "
              f"({contract['full_range']['n_years']}年)")
        print(f"   断点: {len(contract['structural_breakpoints'])}个 "
              f"{[b['year'] for b in contract['structural_breakpoints']]}")
        print(f"   分析起点: {contract['analysis_start_year']}")
        print(f"   有效年份: {contract['effective_years']} "
              f"({len(contract['effective_years'])}年)")
        print(f"   周期分类: {cyc['label']} "
              f"(profit_cv={cyc['profit_cv']}, "
              f"demand={cyc.get('demand_driver','?')}, "
              f"window_n={cyc['window_n']})")
        if cyc.get('downgraded'):
            print(f"     ⚠️ 利润平滑降档: "
                  f"{cyc.get('original_label','?')} → {cyc['label']} "
                  f"(平滑系数={cyc.get('smoothing_coefficient','?')})")
        elif cyc.get('smoothing_coefficient') is not None:
            print(f"     平滑系数: {cyc['smoothing_coefficient']:.3f} "
                  f"({'强平滑' if cyc['smoothing_coefficient'] > 0.10 else '中等' if cyc['smoothing_coefficient'] > 0.05 else '弱'})")
        print(f"   轨道A(长期): {contract['three_track']['track_a_long_term']['n']}年")
        print(f"   轨道B(周期): {contract['three_track']['track_b_cycle']['n']}年")
        print(f"   轨道C(边际): {contract['three_track']['track_c_marginal']['n']}年")
        if contract["anomaly_flags"]:
            print(f"   ⚠️ 异常年份: {[a['year'] for a in contract['anomaly_flags']]}")
    else:
        print(f"✅ analysis_contract.json → {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
