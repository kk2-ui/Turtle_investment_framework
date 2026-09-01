"""niangao.metrics — 指标层：组合穿透GG、回测验证、决策分类"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def classify_decision(gg, II, upside, vt_excluded, gg_ok):
    """自动判断决策分类。"""
    if not gg_ok: return "⚠️待重分析"
    if gg is None or II is None or II == 0: return "?"
    if gg > II:
        if upside and upside > 30: return "Strong Buy" if not vt_excluded else "Buy"
        return "Buy" if upside and upside > 0 else "Hold"
    elif gg >= II - 1: return "Hold"
    else: return "Avoid"


def compute_portfolio_gg(rows: list[dict]) -> dict[str, Any]:
    """按持仓市值加权计算组合穿透回报率。"""
    total_gg = 0.0; total_value = 0.0; count = 0
    for r in rows:
        holding = r.get("current_hold", 0) or 0
        price = r.get("live_price") or r.get("price") or 0
        mv = holding * price
        gg = r.get("gg_discounted") or r.get("gg_base") or 0
        if mv > 0 and gg > 0 and r.get("gg_ok") and r.get("_row_type") == "analyzed":
            total_gg += mv * gg; total_value += mv; count += 1
    if total_value > 0: total_gg /= total_value
    return {"gg": round(total_gg, 1), "value": total_value, "count": count,
            "premium": round(total_gg - 4.0, 1) if total_gg > 0 else 0}


def run_backtest(rows: list[dict]) -> list[dict[str, Any]]:
    """回测：对比 Turtle 买入价 vs 当前价，计算命中率和模拟收益。"""
    results = []
    for r in rows:
        if not r.get("gg_ok") or r.get("_row_type") != "analyzed": continue
        buy_price = r.get("buy_price") or 0
        p_base = r.get("p_base_hkd") or 0
        current_price = r.get("live_price") or r.get("price") or 0
        ii = r.get("ii") or 0
        gg = r.get("gg_discounted") or r.get("gg_base") or 0
        decision = r.get("decision", "?")

        if buy_price > 0 and current_price > 0:
            hit = current_price <= buy_price
        else:
            hit = None

        if hit and buy_price > 0:
            sim_return = (current_price / buy_price - 1) * 100
        elif p_base > 0 and current_price > 0:
            sim_return = (current_price / p_base - 1) * 100
        else:
            sim_return = None

        score = 50
        if gg and ii and ii > 0: score += min((gg / ii - 1) * 100, 30)
        if hit: score += 20
        if sim_return is not None and sim_return > 0: score += min(sim_return / 2, 15)
        if decision == "Strong Buy": score += 5
        score = round(min(max(score, 0), 100))

        results.append({
            "ts_code": r["ts_code"], "name": r.get("wl_name", r.get("name", "")),
            "decision": decision, "gg": gg, "ii": ii,
            "buy_price": buy_price, "p_base": p_base, "current_price": current_price,
            "hit": hit, "sim_return": round(sim_return, 1) if sim_return else None,
            "score": score, "analyzed_at": (r.get("analyzed_at") or "")[:10],
        })
    return sorted(results, key=lambda x: x["score"], reverse=True)


# ── CLI ─────────────────────────────────────────────────────────────

def compute_rebalance(rows: list[dict], total_wealth: float) -> list[dict]:
    """再平衡分析：对比 Turtle 建议仓位 vs 实际仓位。"""
    suggestions = []
    for r in rows:
        if not r.get("gg_ok") or r.get("_row_type") != "analyzed": continue
        holding = r.get("current_hold", 0) or 0
        price = r.get("live_price") or r.get("price") or 0
        actual_value = holding * price
        actual_pct = actual_value / total_wealth * 100 if total_wealth > 0 else 0

        turtle_pct = r.get("pos_pct") or 0
        if turtle_pct <= 0: continue

        diff = actual_pct - turtle_pct
        if diff > turtle_pct * 0.5:  # >50% over
            action = "🔴 超配"
        elif diff < -turtle_pct * 0.5 and turtle_pct > 0:  # >50% under
            action = "🟢 低配"
        elif abs(diff) < 0.5:  # within 0.5pp
            action = "⚖️ 适中"
        else:
            action = "🟡 略" + ("高" if diff > 0 else "低")

        suggestions.append({
            "ts_code": r["ts_code"],
            "name": r.get("wl_name", r.get("name", "")),
            "actual_pct": round(actual_pct, 1), "turtle_pct": round(turtle_pct, 1),
            "diff": round(diff, 1), "action": action,
            "hold_value": round(actual_value, 0),
        })
    return sorted(suggestions, key=lambda x: abs(x["diff"]), reverse=True)


def main():
    import argparse
    from niangao.db import get_db
    ap = argparse.ArgumentParser(description="年糕回测验证")
    ap.add_argument("--code", nargs="*")
    args = ap.parse_args()

    db = get_db()
    rows = db.execute("SELECT * FROM analysis WHERE gg_ok=1").fetchall()
    db.close()
    rows = [dict(r) for r in rows]
    for r in rows: r["_row_type"] = "analyzed"

    if args.code:
        rows = [r for r in rows if r["ts_code"] in args.code]

    results = run_backtest(rows)
    total = len(results)
    hit_count = sum(1 for r in results if r["hit"])
    avg_score = sum(r["score"] for r in results) / total if total else 0

    print(f"\n{'='*70}")
    print(f"🏮 年糕回测报告 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   已分析: {total} 只 | 价格已到位: {hit_count} 只 | 平均分: {avg_score:.0f}")
    print(f"{'='*70}\n")
    print(f"{'代码':12s} {'名称':8s} {'GG':>5s} {'买入价':>7s} {'现价':>7s} {'命中':4s} {'模拟收益':>8s} {'评分':>4s}")
    for r in results:
        hit_str = "✅" if r["hit"] else ("—" if r["hit"] is None else "❌")
        sim_str = f'{r["sim_return"]:+.1f}%' if r["sim_return"] is not None else "—"
        bar = "█" * (r["score"] // 10)
        print(f"{r['ts_code']:12s} {r['name']:8s} {r['gg']:>4.1f}% {r['buy_price']:>6.2f} {r['current_price']:>6.2f} {hit_str:4s} {sim_str:>8s} {r['score']:>3d} {bar}")


if __name__ == "__main__":
    main()
