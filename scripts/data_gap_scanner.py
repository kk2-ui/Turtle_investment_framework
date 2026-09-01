#!/usr/bin/env python3
"""data_gap_scanner.py — V9.3: Scan report for ⚠️ markers and classify gaps.

Outputs data_gaps.json with categorized missing data and suggested fixes.
Zone C coordinator should run this after report generation.
"""
import argparse, json, os, re, sys
from datetime import datetime

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

DB_FIXABLE = False  # DB gaps need manual data import
ZONEB_FIXABLE = ["回购", "关联交易", "非经常", "审计师", "KAM", "D&A", "折旧", "摊销", "管理层变动"]
ZONEJ_FIXABLE = ["data_discount", "earnings_quality", "moat_assessment", "capex"]


def scan_report(text: str) -> dict:
    gaps = {"db": [], "zone_b": [], "zone_j": [], "other": []}
    for line in text.split("\n"):
        if "⚠️" not in line:
            continue
        gap = {"line": line.strip()[:120], "raw": line.strip()}
        # Classify
        if any(kw in line for kw in ["DB缺失", "DB中", "financial_trends中BS", "shares_m=NULL"]):
            gaps["db"].append(gap)
        elif any(kw in line for kw in ZONEB_FIXABLE):
            gaps["zone_b"].append(gap)
        elif any(kw in line for kw in ZONEJ_FIXABLE):
            gaps["zone_j"].append(gap)
        else:
            gaps["other"].append(gap)
    return gaps


def find_stock_dir(ts_code: str) -> str:
    code_base = ts_code.split(".")[0]
    for name in os.listdir(OUTPUT_BASE):
        if name.startswith(code_base) and os.path.isdir(os.path.join(OUTPUT_BASE, name)):
            return os.path.join(OUTPUT_BASE, name)
    return OUTPUT_BASE


def main():
    p = argparse.ArgumentParser(description="V9.3: Scan report for data gaps")
    p.add_argument("--code", required=True)
    p.add_argument("--report", help="Report path (auto-detected if omitted)")
    p.add_argument("--output", help="Output JSON path")
    args = p.parse_args()

    stock_dir = find_stock_dir(args.code)
    report_path = args.report
    if not report_path:
        for f in os.listdir(stock_dir):
            if "分析报告" in f and f.endswith(".md"):
                report_path = os.path.join(stock_dir, f)
                break
    if not report_path or not os.path.exists(report_path):
        print(f"ERROR: Report not found", file=sys.stderr)
        return 1

    with open(report_path) as f:
        text = f.read()
    gaps = scan_report(text)

    total = sum(len(v) for v in gaps.values())
    print(f"🔍 Data Gap Scan: {total} issues found")
    print(f"   DB层 (需人工补数据): {len(gaps['db'])}")
    print(f"   Zone B (可重新提取): {len(gaps['zone_b'])}")
    print(f"   Zone J (可重跑agent): {len(gaps['zone_j'])}")
    print(f"   其他: {len(gaps['other'])}")

    out = {
        "_meta": {"ts_code": args.code, "scanned_at": datetime.now().isoformat(), "total_gaps": total},
        "gaps": gaps,
        "suggestions": {
            "db": "检查 hk_financials/ CSV 是否有对应字段，运行 rebuild_hk_data.py 或 import_csmar_hk_full.py 重导",
            "zone_b": f"可自动重提取的字段: {ZONEB_FIXABLE}。用 --retry 触发协调器重调 Zone B sub-agent",
            "zone_j": f"可重跑的agent: {ZONEJ_FIXABLE}。运行 zone_j_agent.py --agent <name> --save-prompt",
        },
    }
    out_path = args.output or os.path.join(stock_dir, "data_gaps.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"✅ data_gaps.json → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
