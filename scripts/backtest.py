#!/usr/bin/env python3
"""backtest.py — 年糕投资系统 回测验证 (Phase 4)

验证 Turtle 分析准确度：
  - 价格命中率：当前价是否已跌到 Turtle 买入价以下？
  - 模拟收益：如果按 Turtle 买入价成交，当前浮盈多少？

Usage:
  python scripts/backtest.py                    # 回测所有已分析股票
  python scripts/backtest.py --code 00506.HK    # 单只
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.join(_FRAMEWORK_DIR, "scripts")
sys.path.insert(0, _SCRIPTS_DIR)
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")


def run_backtest(codes: list[str] | None = None) -> list[dict[str, Any]]:
    """回测所有已分析股票。"""
    from portfolio_db import get_db
    db = get_db()

    query = """
        SELECT a.*, w.current_hold, w.my_valuation AS inv_valuation
        FROM analysis a LEFT JOIN watchlist w ON a.ts_code = w.ts_code
        WHERE a.gg_ok = 1
    """
    params: list = []
    if codes:
        placeholders = ",".join("?" * len(codes))
        query += f" AND a.ts_code IN ({placeholders})"
        params = codes

    rows = db.execute(query, params).fetchall()
    db.close()

    results = []
    for r in rows:
        r = dict(r)
        buy_price = r.get("buy_price") or 0
        p_base = r.get("p_base_hkd") or 0
        current_price = r.get("price") or 0
        ii = r.get("ii") or 0
        gg = r.get("gg_discounted") or r.get("gg_base") or 0
        decision = r.get("decision", "?")

        # 价格命中：当前价 ≤ 买入价？
        if buy_price > 0 and current_price > 0:
            hit = current_price <= buy_price
            discount = (1 - current_price / buy_price) * 100 if buy_price > 0 else 0
        else:
            hit = None
            discount = 0

        # 模拟收益：如果按买入价成交
        if hit and buy_price > 0:
            sim_return = (current_price / buy_price - 1) * 100
        elif p_base > 0 and current_price > 0:
            sim_return = (current_price / p_base - 1) * 100
        else:
            sim_return = None

        # Turtle 估值 vs 当前价偏离
        if p_base > 0 and current_price > 0:
            valuation_gap = (current_price / p_base - 1) * 100
        else:
            valuation_gap = None

        # 评分
        score = _compute_score(gg, ii, hit, sim_return, decision)

        results.append({
            "ts_code": r["ts_code"],
            "name": r.get("name", r["ts_code"]),
            "decision": decision,
            "gg": gg, "ii": ii,
            "buy_price": buy_price,
            "p_base": p_base,
            "current_price": current_price,
            "hit": hit, "discount": round(discount, 1),
            "sim_return": round(sim_return, 1) if sim_return is not None else None,
            "valuation_gap": round(valuation_gap, 1) if valuation_gap is not None else None,
            "score": score,
            "analyzed_at": r.get("analyzed_at", "")[:10],
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


def _compute_score(gg, ii, hit, sim_return, decision):
    """综合评分 0-100。"""
    score = 50
    if gg and ii and ii > 0:
        score += min((gg / ii - 1) * 100, 30)  # GG 超额
    if hit:
        score += 20  # 价格已到位，验证了分析
    if sim_return is not None and sim_return > 0:
        score += min(sim_return / 2, 15)  # 正收益加成
    if decision == "Strong Buy":
        score += 5
    return round(min(max(score, 0), 100))


def print_report(results: list[dict]):
    """打印回测报告。"""
    total = len(results)
    hit_count = sum(1 for r in results if r["hit"])
    buy_count = sum(1 for r in results if r["decision"] in ("Strong Buy", "Buy"))
    avg_score = sum(r["score"] for r in results) / total if total else 0

    print(f"\n{'='*70}")
    print(f"🏮 年糕回测报告 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   已分析: {total} 只 | 价格已到位: {hit_count} 只 | 平均分: {avg_score:.0f}")
    print(f"{'='*70}\n")

    print(f"{'代码':12s} {'名称':8s} {'决策':12s} {'GG':>6s} {'II':>5s} {'买入价':>8s} {'现价':>8s} {'命中':4s} {'折扣':>6s} {'模拟收益':>8s} {'评分':>4s}")
    print("-" * 95)
    for r in results:
        hit_str = "✅" if r["hit"] else ("—" if r["hit"] is None else "❌")
        sim_str = f'{r["sim_return"]:+.1f}%' if r["sim_return"] is not None else "—"
        discount_str = f'{r["discount"]:.1f}%' if r["discount"] != 0 else "—"
        score_bar = "█" * (r["score"] // 10)
        print(f"{r['ts_code']:12s} {r['name']:8s} {r['decision']:12s} "
              f"{r['gg']:>5.1f}% {r['ii']:>4.1f}% "
              f"{r['buy_price']:>7.2f} {r['current_price']:>7.2f} "
              f"{hit_str:4s} {discount_str:>6s} {sim_str:>8s} "
              f"{r['score']:>3d} {score_bar}")

    print(f"\n💡 价格到位 = 当前价已低于 Turtle 建议买入价，可考虑建仓")
    print(f"💡 模拟收益 = 假设按买入价成交后当前浮盈")
    print(f"💡 评分 = GG超额 + 价格到位 + 正收益 + 信号强度\n")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="年糕回测验证")
    ap.add_argument("--code", nargs="*", help="指定股票代码")
    args = ap.parse_args()

    results = run_backtest(codes=args.code)
    print_report(results)


if __name__ == "__main__":
    main()
