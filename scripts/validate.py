#!/usr/bin/env python3
"""validate.py — 统一验证入口 v3.1

从 quality_findings + curation_decisions + annual_financials 生成 analysis contract。
存在 open BLOCK → BLOCKED，compute_bundle 应拒绝运行。

Usage:
    python3 scripts/validate.py --code 01502.HK
    python3 scripts/validate.py --code 01502.HK --json --save-contract
    python3 scripts/validate.py --all
"""

import argparse, json, os, sqlite3, sys, uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")


def assess_stock(conn: sqlite3.Connection, ts_code: str) -> dict:
    """从 quality_findings + financials 生成完整 readiness 报告。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Data completeness
    comp = conn.execute("SELECT * FROM v_data_completeness WHERE ts_code=?", (ts_code,)).fetchone()
    if not comp:
        return _insufficient(ts_code, now, "数据库无此标的的财务记录")

    years = conn.execute("SELECT fiscal_year FROM annual_financials WHERE ts_code=? ORDER BY fiscal_year", (ts_code,)).fetchall()
    usable_years = [y[0] for y in years]

    # Quality findings summary
    open_blocks = conn.execute("""
        SELECT check_name, field_name, fiscal_year, message FROM quality_findings
        WHERE ts_code=? AND severity='BLOCK' AND fix_status='open'
        ORDER BY fiscal_year, field_name
    """, (ts_code,)).fetchall()

    open_warns = conn.execute("""
        SELECT check_name, field_name, fiscal_year, message FROM quality_findings
        WHERE ts_code=? AND severity='WARN' AND fix_status='open'
        ORDER BY fiscal_year, field_name
    """, (ts_code,)).fetchall()

    # Curation info
    curation_n = conn.execute("SELECT COUNT(*) FROM curation_decisions WHERE ts_code=?", (ts_code,)).fetchone()[0]

    # Determine readiness
    has_block = len(open_blocks) > 0
    usable_pct = comp["usable_pct"] if comp else 0
    shares_ok = conn.execute("SELECT shares_m FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
    shares_missing = not shares_ok or not shares_ok[0]
    # Check DPS availability
    dps_pct = comp["dps_pct"] if comp else 0
    dps_ok = dps_pct >= 60 if dps_pct is not None else False
    # Check minimum years (framework needs 3yr for mean, trend, stability)
    min_years_ok = len(usable_years) >= 3

    if has_block or usable_pct < 40 or not min_years_ok:
        readiness = "BLOCKED"
    elif usable_pct < 80 or shares_missing or len(open_warns) > 3:
        readiness = "DEGRADED"
    else:
        readiness = "READY"

    # Analysis scope
    ddm_ok = not shares_missing and dps_ok  # DDM needs both shares and DPS
    valuation_ok = usable_pct >= 60 and min_years_ok
    position_ok = valuation_ok and not shares_missing

    # Compute readiness score (0-100)
    score = usable_pct
    if shares_missing: score -= 20
    score -= len(open_blocks) * 10
    score -= len(open_warns) * 2
    score = max(0, min(100, score))

    # Build contract
    contract = {
        "contract_id": f"ac_{uuid.uuid4().hex[:12]}",
        "ts_code": ts_code,
        "generated_at": now,
        "readiness_status": readiness,
        "readiness_score": score,
        "usable_years": usable_years,
        "missing_core": [],
        "degraded_fields": [],
        "block_reasons": [{"check": b[0], "field": b[1], "year": b[2], "message": b[3]} for b in open_blocks],
        "warn_reasons": [{"check": w[0], "field": w[1], "year": w[2], "message": w[3]} for w in open_warns],
        "analysis_scope": {
            "full_analysis_allowed": readiness == "READY",
            "valuation_allowed": valuation_ok,
            "ddm_allowed": ddm_ok,
            "position_sizing_allowed": position_ok,
        },
        "data_completeness": {
            "usable_pct": usable_pct,
            "financial_years": len(usable_years),
            "bs_deviation_pct": comp["bs_deviation_pct"] if comp else None,
            "open_blocks": len(open_blocks),
            "open_warns": len(open_warns),
            "curation_decisions": curation_n,
        },
        "compute_confidence": {
            "shares_source": "db" if not shares_missing else "override_or_default",
            "overall": "high" if readiness == "READY" else "medium" if readiness == "DEGRADED" else "low",
        },
        "recommended_action": _action(readiness, has_block, shares_missing, len(open_blocks), len(open_warns)),
    }

    return contract


def _insufficient(ts_code: str, now: str, reason: str) -> dict:
    return {
        "contract_id": f"ac_{uuid.uuid4().hex[:12]}",
        "ts_code": ts_code, "generated_at": now,
        "readiness_status": "BLOCKED", "readiness_score": 0,
        "usable_years": [], "missing_core": ["all"], "degraded_fields": [],
        "block_reasons": [{"check": "no_data", "field": "", "year": 0, "message": reason}],
        "warn_reasons": [],
        "analysis_scope": {"full_analysis_allowed": False, "valuation_allowed": False, "ddm_allowed": False, "position_sizing_allowed": False},
        "data_completeness": {"usable_pct": 0, "financial_years": 0, "bs_deviation_pct": None, "open_blocks": 1, "open_warns": 0, "curation_decisions": 0},
        "compute_confidence": {"shares_source": "unknown", "overall": "low"},
        "recommended_action": reason,
    }


def _action(readiness: str, has_block: bool, shares_missing: bool, n_block: int, n_warn: int) -> str:
    if readiness == "BLOCKED":
        parts = []
        if has_block: parts.append(f"{n_block}个 BLOCK 需修复")
        if shares_missing: parts.append("shares_m 缺失")
        return f"❌ 禁止分析 — {', '.join(parts)}"
    elif readiness == "DEGRADED":
        return f"⚠️ 降级分析 — {n_warn}个 WARN，部分模型将禁用"
    return "✅ 完整分析 — 所有核心字段可用，无 BLOCK"


def save_contract(conn: sqlite3.Connection, contract: dict):
    """将 contract 写入 analysis_contracts 表。"""
    conn.execute("""INSERT OR REPLACE INTO analysis_contracts
        (contract_id, ts_code, generated_at, readiness_status, readiness_score,
         usable_years_json, missing_core_json, degraded_fields_json,
         block_reasons_json, warn_reasons_json, analysis_scope_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (contract["contract_id"], contract["ts_code"], contract["generated_at"],
         contract["readiness_status"], contract["readiness_score"],
         json.dumps(contract["usable_years"]),
         json.dumps(contract["missing_core"]),
         json.dumps(contract["degraded_fields"]),
         json.dumps(contract["block_reasons"], ensure_ascii=False),
         json.dumps(contract["warn_reasons"], ensure_ascii=False),
         json.dumps(contract["analysis_scope"])))


def assess_all(conn) -> list:
    stocks = conn.execute("SELECT ts_code FROM stocks ORDER BY ts_code").fetchall()
    return [assess_stock(conn, s[0]) for s in stocks]


# ── CLI ──

def main():
    p = argparse.ArgumentParser(description="validate.py v3.1 — analysis contract 生成器")
    p.add_argument("--code", type=str)
    p.add_argument("--all", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--save-contract", action="store_true", help="写入 analysis_contracts 表")
    args = p.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.all:
        results = assess_all(conn)
    elif args.code:
        results = [assess_stock(conn, args.code)]
    else:
        print("ERROR: --code or --all required", file=sys.stderr)
        conn.close()
        return 1

    if args.save_contract:
        for r in results:
            save_contract(conn, r)
        conn.commit()

    conn.close()

    if args.json:
        print(json.dumps(results if args.all else results[0], indent=2, ensure_ascii=False, default=str))
    else:
        for r in results:
            _print(r)

    return 0


def _print(c: dict):
    bar = "─" * 55
    print(f"\n{bar}")
    print(f"  {c['ts_code']} 分析就绪度: {c['readiness_status']}")
    print(bar)
    d = c["data_completeness"]
    print(f"  可用年份: {d['financial_years']}年 | 字段覆盖率: {d['usable_pct']}% | BS偏差: {d['bs_deviation_pct']}%")
    print(f"  BLOCK: {d['open_blocks']} | WARN: {d['open_warns']} | 策展决策: {d['curation_decisions']}")
    if c["block_reasons"]:
        print(f"  🚫 BLOCK原因:")
        for b in c["block_reasons"][:3]:
            print(f"     [{b['check']}] {b['message'][:80]}")
    scope = c["analysis_scope"]
    print(f"  估值:{'✅' if scope['valuation_allowed'] else '❌'} | DDM:{'✅' if scope['ddm_allowed'] else '❌'} | 仓位:{'✅' if scope['position_sizing_allowed'] else '❌'}")
    print(f"  → {c['recommended_action']}")
    print(bar)


if __name__ == "__main__":
    sys.exit(main())
