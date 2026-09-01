#!/usr/bin/env python3
"""rule_engine.py — Declarative Financial Signal Detection Engine (P3)

Separates rule declarations from execution. Rules defined in rules/financial_signals.yaml.
This engine loads rules, evaluates them against DataFrames, and returns structured signals.

Usage:
    python3 scripts/rule_engine.py --code 01502.HK
    python3 scripts/rule_engine.py --code 01502.HK --rules rules/financial_signals.yaml
"""

import argparse
import json
import os
import sys
from typing import Optional

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

# ── Default rules (embedded; can be overridden by YAML file) ──
DEFAULT_RULES = [
    {
        "id": "gross_margin_decline",
        "severity": "warn",
        "fields": ["gross_margin"],
        "pattern": "consecutive_decline",
        "params": {"min_years": 3, "min_magnitude_pp": 3.0},
        "title": "毛利率连续下滑",
        "detail": "从 {start_year}的{from_val}%降至{end_year}的{to_val}%，累计压缩{delta}pp"
    },
    {
        "id": "zero_leverage",
        "severity": "positive",
        "fields": ["st_borr", "lt_borr"],
        "pattern": "all_zero",
        "params": {"min_years": 3},
        "title": "连续零有息负债",
        "detail": "连续{years}年无任何银行借款或债券融资"
    },
    {
        "id": "ar_deterioration",
        "severity": "warn",
        "fields": ["accounts_receiv", "revenue"],
        "pattern": "ratio_rising",
        "params": {"min_years": 3, "min_rise_pp": 5.0},
        "title": "应收/营收占比持续上升",
        "detail": "从{start_year}的{from_val}%升至{end_year}的{to_val}%，回款恶化"
    },
    {
        "id": "fcf_positive_streak",
        "severity": "positive",
        "fields": ["fcf"],
        "pattern": "all_positive",
        "params": {"min_years": 5},
        "title": "FCF持续为正",
        "detail": "自由现金流连续{years}年为正，分红和内生长均有保障"
    },
    {
        "id": "goodwill_jump",
        "severity": "warn",
        "fields": ["goodwill"],
        "pattern": "yoy_jump",
        "params": {"threshold_pct": 50},
        "title": "商誉跳变",
        "detail": "FY{year}商誉从{from_val}M变为{to_val}M（{pct}%变动），可能为并购或减值"
    },
    {
        "id": "revenue_up_np_down",
        "severity": "warn",
        "fields": ["revenue", "n_income_attr_p"],
        "pattern": "divergence",
        "params": {"min_years": 2},
        "title": "增收不增利",
        "detail": "营收CAGR {rev_cagr}%但归母净利CAGR {np_cagr}%，利润率侵蚀"
    },
    {
        "id": "dividend_sustainable",
        "severity": "positive",
        "fields": ["eps", "dps"],
        "pattern": "eps_gt_dps",
        "params": {"min_years": 5},
        "title": "分红可持续",
        "detail": "EPS始终大于DPS连续{years}年，分红政策有盈利支撑"
    },
    {
        "id": "net_cash",
        "severity": "positive",
        "fields": ["money_cap", "total_liab"],
        "pattern": "field_a_gt_field_b",
        "params": {},
        "title": "净现金状态",
        "detail": "货币资金{cash}M > 总负债{liab}M，净现金{net}M"
    },
    {
        "id": "roe_decline",
        "severity": "warn",
        "fields": ["total_hldr_eqy_exc_min_int", "n_income_attr_p"],
        "pattern": "consecutive_decline",
        "params": {"min_years": 3, "min_magnitude_pp": 3.0},
        "title": "ROE连续下滑",
        "detail": "从{start_year}的{from_val}%降至{end_year}的{to_val}%"
    },
    {
        "id": "dps_decline",
        "severity": "info",
        "fields": ["dps"],
        "pattern": "consecutive_decline",
        "params": {"min_years": 3, "min_magnitude_pp": 0},
        "title": "DPS连续下滑",
        "detail": "每股股息从{start_year}的{from_val}降至{end_year}的{to_val}"
    }
]


class RuleEngine:
    def __init__(self, rules: list = None):
        self.rules = rules or DEFAULT_RULES

    def evaluate(self, data: dict, years: list) -> list:
        """Evaluate all rules against data dict {field: [year_values]}.
        Returns list of signal dicts."""
        signals = []
        for rule in self.rules:
            pattern_func = getattr(self, f"_pattern_{rule['pattern']}", None)
            if not pattern_func:
                continue
            result = pattern_func(data, years, rule)
            if result:
                signals.append(self._format(rule, result))
        return signals

    def _format(self, rule: dict, result: dict) -> dict:
        """Format a matched rule into a signal output."""
        detail = rule["detail"].format(**{k: str(v)[:20] for k, v in result.items()})
        return {
            "type": rule["severity"].upper() if rule["severity"] != "info" else "INFO",
            "code": rule["id"].upper(),
            "title": rule["title"],
            "detail": detail,
            "evidence": result,
        }

    # ── Pattern matchers ──

    def _pattern_consecutive_decline(self, data, years, rule):
        field = rule["fields"][0]
        values = data.get(field, [])
        if len(values) < rule["params"]["min_years"]:
            return None
        # Count consecutive declines
        declines = sum(1 for i in range(1, len(values))
                       if values[i] is not None and values[i-1] is not None
                       and values[i] < values[i-1])
        total_drop = (values[0] or 0) - (values[-1] or 0)
        if declines >= rule["params"]["min_years"] - 1 and total_drop > rule["params"].get("min_magnitude_pp", 0):
            return {"years": declines + 1, "from_val": values[0], "to_val": values[-1],
                    "delta": round(total_drop, 2), "start_year": years[0], "end_year": years[-1]}
        return None

    def _pattern_all_zero(self, data, years, rule):
        fields = rule["fields"]
        zero_count = 0
        n = min(len(data.get(f, [])) for f in fields)
        for i in range(n):
            if all((data.get(f, [None]*n)[i] or 0) == 0 for f in fields):
                zero_count += 1
        if zero_count >= rule["params"]["min_years"]:
            return {"years": zero_count}
        return None

    def _pattern_ratio_rising(self, data, years, rule):
        f1, f2 = rule["fields"]
        vals1 = data.get(f1, [])
        vals2 = data.get(f2, [])
        n = min(len(vals1), len(vals2))
        if n < rule["params"]["min_years"]:
            return None
        ratios = [(vals1[i]/vals2[i]*100) if (vals1[i] and vals2[i] and vals2[i] != 0) else None for i in range(n)]
        ratios_clean = [(i, r) for i, r in enumerate(ratios) if r is not None]
        if len(ratios_clean) < 2:
            return None
        first_r, last_r = ratios_clean[0][1], ratios_clean[-1][1]
        if last_r - first_r > rule["params"]["min_rise_pp"]:
            return {"from_val": round(first_r, 1), "to_val": round(last_r, 1),
                    "start_year": years[ratios_clean[0][0]], "end_year": years[ratios_clean[-1][0]]}
        return None

    def _pattern_all_positive(self, data, years, rule):
        field = rule["fields"][0]
        values = data.get(field, [])
        positive = sum(1 for v in values if v is not None and v > 0)
        if positive >= rule["params"]["min_years"]:
            return {"years": positive}
        return None

    def _pattern_yoy_jump(self, data, years, rule):
        field = rule["fields"][0]
        values = data.get(field, [])
        for i in range(1, len(values)):
            if values[i-1] and values[i] and values[i-1] > 0:
                change = abs(values[i] - values[i-1]) / values[i-1] * 100
                if change > rule["params"]["threshold_pct"]:
                    return {"year": years[i], "from_val": values[i-1], "to_val": values[i],
                            "pct": round(change, 1)}
        return None

    def _pattern_divergence(self, data, years, rule):
        f1, f2 = rule["fields"]
        v1 = data.get(f1, [])
        v2 = data.get(f2, [])
        n = min(len(v1), len(v2))
        if n < rule["params"]["min_years"]:
            return None
        # Check if first field rises while second falls
        if v1[-1] and v1[0] and v1[-1] > v1[0] and v2[-1] and v2[0] and v2[-1] < v2[0]:
            rev_cagr = round(((v1[-1]/v1[0])**(1/(n-1)) - 1) * 100, 1) if v1[0] > 0 else 0
            np_cagr = round(((v2[-1]/v2[0])**(1/(n-1)) - 1) * 100, 1) if v2[0] > 0 else 0
            return {"rev_cagr": rev_cagr, "np_cagr": np_cagr}
        return None

    def _pattern_eps_gt_dps(self, data, years, rule):
        eps = data.get("eps", [])
        dps = data.get("dps", [])
        n = min(len(eps), len(dps))
        if n < rule["params"]["min_years"]:
            return None
        sustainable = sum(1 for i in range(n) if eps[i] and dps[i] and eps[i] > dps[i])
        if sustainable >= rule["params"]["min_years"]:
            return {"years": sustainable}
        return None

    def _pattern_field_a_gt_field_b(self, data, years, rule):
        f1, f2 = rule["fields"]
        v1 = data.get(f1, [None])[-1] or 0
        v2 = data.get(f2, [None])[-1] or 0
        if v1 > v2:
            return {"cash": round(v1, 0), "liab": round(v2, 0), "net": round(v1 - v2, 0)}
        return None


def main():
    p = argparse.ArgumentParser(description="rule_engine.py — Declarative Signal Engine")
    p.add_argument("--code", type=str, required=True)
    p.add_argument("--rules", type=str, help="YAML rules file (optional, uses defaults)")
    p.add_argument("--output", type=str)
    args = p.parse_args()

    # Simple: read from financial_trends.json if available, else from DB directly
    if args.output:
        stock_dir = args.output
    else:
        code_base = args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        candidates = [d for d in os.listdir(OUTPUT_BASE)
                      if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(code_base)]
        if not candidates:
            print(f"ERROR: No output directory for {args.code}", file=sys.stderr)
            return 1
        stock_dir = os.path.join(OUTPUT_BASE, candidates[0])

    # Load financial data from DB
    import sqlite3
    db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
    conn = sqlite3.connect(db, timeout=5)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM annual_financials WHERE ts_code=? ORDER BY fiscal_year
    """, (args.code,)).fetchall()
    conn.close()

    if len(rows) < 2:
        print(f"Insufficient data: {len(rows)} years")
        return 1

    years = [r["fiscal_year"] for r in rows]
    data = {}
    for key in rows[0].keys():
        data[key] = [r[key] for r in rows]

    engine = RuleEngine()
    signals = engine.evaluate(data, years)

    print(f"Rules evaluated: {len(engine.rules)}")
    print(f"Signals detected: {len(signals)}")
    for s in signals:
        icon = {"WARN": "⚠️", "POSITIVE": "✅", "INFO": "ℹ️"}.get(s["type"], "•")
        print(f"  {icon} [{s['type']}] {s['title']}: {s['detail'][:100]}")

    # Save
    out = os.path.join(stock_dir, "rule_engine_signals.json")
    with open(out, "w") as f:
        json.dump(signals, f, indent=2, ensure_ascii=False)
    print(f"\n✅ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
