#!/usr/bin/env python3
"""citation_verifier.py — Zone C: 报告数字验证器

从分析报告中提取数字引用，与 compute_bundle.json 和 DB 交叉验证。

Usage:
  python3 scripts/citation_verifier.py --code 01502.HK --report report.md
"""

import argparse, json, os, re, sqlite3, sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_analysis.db")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

def find_stock_dir(ts_code):
    for e in os.listdir(OUTPUT_DIR):
        if e.startswith(ts_code.replace(".","_")) or e.startswith(ts_code.split(".")[0]+"_") and os.path.isdir(os.path.join(OUTPUT_DIR, e)):
            return os.path.join(OUTPUT_DIR, e)
    return None

def extract_numbers_from_report(report_text):
    """Extract numeric claims from report text."""
    findings = []

    # Pattern: key_number pairs like "营业收入 1,999 百万元" or "R_NP 19.46%"
    patterns = [
        # Named metrics
        (r'R\(?NP\)?\s*[:：]?\s*([\d.]+)\s*%', 'R_NP', '%'),
        (r'R\(?OE\)?\s*[:：]?\s*([\d.]+)\s*%', 'R_OE', '%'),
        (r'GG.*?(?:基准|base).*?([\d.]+)\s*%', 'GG_base', '%'),
        (r'DDM.*?公允价.*?([\d.]+)\s*(?:HKD|港币)', 'DDM_v', 'HKD'),
        (r'OCF/NP.*?([\d.]+)', 'OCF_NP_ratio', 'ratio'),
        # Financial data
        (r'营业收入\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(?:百万|百万元)', 'revenue', '百万元'),
        (r'归母净利润\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(?:百万|百万元)', 'n_income_attr_p', '百万元'),
        (r'毛利率\s*[:：]?\s*([\d.]+)\s*%', 'gross_margin', '%'),
        (r'净现金\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(?:百万|百万元)', 'net_cash', '百万元'),
        (r'市值\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(?:百万|百万元)', 'market_cap', '百万元'),
    ]

    for pattern, metric_name, unit in patterns:
        for m in re.finditer(pattern, report_text, re.IGNORECASE):
            val_str = m.group(1).replace(",", "")
            try:
                val = float(val_str)
                findings.append({
                    "metric": metric_name,
                    "reported_value": val,
                    "unit": unit,
                    "position": m.start(),
                    "context": report_text[max(0,m.start()-30):m.end()+30],
                })
            except ValueError:
                pass

    return findings

def verify_findings(ts_code, findings):
    """Cross-reference extracted numbers against source data."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    stock_dir = find_stock_dir(ts_code)

    # Load source data
    bundle = None
    if stock_dir:
        bp = os.path.join(stock_dir, "compute_bundle.json")
        if os.path.exists(bp):
            with open(bp) as f: bundle = json.load(f)

    af_latest = conn.execute(
        "SELECT * FROM annual_financials WHERE ts_code=? ORDER BY fiscal_year DESC LIMIT 1",
        (ts_code,)).fetchone()
    conn.close()

    results = []
    for f in findings:
        metric = f["metric"]
        reported = f["reported_value"]
        source_val = None
        source_desc = ""

        if bundle:
            if metric == "R_NP":
                source_val = bundle.get("factor2", {}).get("r_np")
                source_desc = "compute_bundle.factor2.r_np"
            elif metric == "R_OE":
                source_val = bundle.get("factor2", {}).get("r_oe")
                source_desc = "compute_bundle.factor2.r_oe"
            elif metric == "GG_base":
                source_val = bundle.get("factor3", {}).get("gg", {}).get("base")
                source_desc = "compute_bundle.factor3.gg.base"
            elif metric == "DDM_v":
                source_val = bundle.get("factor4", {}).get("ddm_v_hkd")
                source_desc = "compute_bundle.factor4.ddm_v_hkd"
            elif metric == "OCF_NP_ratio":
                source_val = bundle.get("factor2", {}).get("ocf_np_ratio")
                source_desc = "compute_bundle.factor2.ocf_np_ratio"
            elif metric == "market_cap":
                source_val = bundle.get("market", {}).get("mc_rmb")
                source_desc = "compute_bundle.market.mc_rmb"
            elif metric == "net_cash":
                source_val = bundle.get("factor3", {}).get("net_cash")
                source_desc = "compute_bundle.factor3.net_cash"

        if af_latest:
            if metric == "revenue":
                source_val = af_latest["revenue"]
                source_desc = f"DB annual_financials FY{af_latest['fiscal_year']}.revenue"
            elif metric == "n_income_attr_p":
                source_val = af_latest["n_income_attr_p"]
                source_desc = f"DB annual_financials FY{af_latest['fiscal_year']}.n_income_attr_p"
            elif metric == "gross_margin":
                source_val = af_latest["gross_margin"]
                source_desc = f"DB annual_financials FY{af_latest['fiscal_year']}.gross_margin"

        if source_val is not None:
            diff_pct = abs(reported - source_val) / abs(source_val) * 100 if source_val != 0 else 0
            verdict = "PASS" if diff_pct < 2 else ("WARN" if diff_pct < 5 else "FAIL")
        else:
            diff_pct = None
            verdict = "UNVERIFIED"

        results.append({
            **f,
            "source_value": source_val,
            "source": source_desc,
            "diff_pct": round(diff_pct, 1) if diff_pct is not None else None,
            "verdict": verdict,
        })

    return results

def main():
    p = argparse.ArgumentParser(description="citation_verifier.py — Zone C (V10 enhanced)")
    p.add_argument("--code", required=True)
    p.add_argument("--report", help="Path to report markdown")
    p.add_argument("--evidence-only", action="store_true", help="仅运行证据引用验证（使用 EvidenceRegistry）")
    p.add_argument("--stock-dir", help="股票输出目录（用于证据验证时加载来源）")
    args = p.parse_args()

    if args.report:
        with open(args.report) as f:
            report_text = f.read()
    else:
        # Try to find report
        stock_dir = find_stock_dir(args.code)
        if not stock_dir:
            print(f"ERROR: output dir not found", file=sys.stderr); return 1
        reports = sorted([f for f in os.listdir(stock_dir) if f.endswith(".md") and "分析报告" in f])
        if not reports:
            print(f"ERROR: no report found in {stock_dir}", file=sys.stderr); return 1
        with open(os.path.join(stock_dir, reports[-1])) as f:
            report_text = f.read()

    if args.evidence_only:
        # V10: 使用 EvidenceRegistry 验证证据引用
        from evidence_citation import EvidenceRegistry, validate_evidence_coverage
        registry = EvidenceRegistry()
        sd = args.stock_dir or find_stock_dir(args.code)
        if sd:
            registry.register_from_output_dir(sd)
        coverage = validate_evidence_coverage(report_text, registry)
        print(f"V10 证据引用验证: {args.code}")
        print(f"  数字声明: {coverage['number_claims']}")
        print(f"  证据锚点: {coverage['evidence_anchors']}")
        print(f"  唯一来源: {coverage['unique_sources']}")
        print(f"  覆盖率: {coverage['coverage_ratio']:.0%}")
        print(f"  未知来源: {coverage['unknown_sources']}")
        print(f"  未引用关键源: {coverage['uncited_key_sources']}")
        print(f"  状态: {coverage['status']}")
        issues = registry.validate_anchors(report_text)
        if issues:
            print(f"\n  问题详情:")
            for i in issues:
                print(f"    - [{i['anchor']}] {i['issue']}")
        return 0 if coverage['status'] == 'PASS' else 1

    findings = extract_numbers_from_report(report_text)
    results = verify_findings(args.code, findings)

    # Print verification report
    print(f"Citation Verification: {args.code}")
    print(f"Numbers extracted: {len(findings)}")
    print(f"{'Metric':<20} {'Reported':>10} {'Source':>10} {'Diff%':>7} {'Verdict'}")
    print("-" * 65)
    passed = warned = failed = unverified = 0
    for r in results:
        src = f"{r['source_value']}"[:10] if r['source_value'] else "N/A"
        diff = f"{r['diff_pct']}%" if r['diff_pct'] is not None else "-"
        print(f"{r['metric']:<20} {r['reported_value']:>10} {src:>10} {diff:>7} {r['verdict']}")
        if r['verdict'] == 'PASS': passed += 1
        elif r['verdict'] == 'WARN': warned += 1
        elif r['verdict'] == 'FAIL': failed += 1
        else: unverified += 1

    print(f"\n✅ {passed} PASS | ⚠️ {warned} WARN | ❌ {failed} FAIL | ❓ {unverified} UNVERIFIED")

    # Save verification report
    stock_dir = find_stock_dir(args.code)
    if stock_dir:
        vp = os.path.join(stock_dir, "verification_report.json")
        with open(vp, "w") as f:
            json.dump({"code": args.code, "findings": results,
                       "summary": {"pass": passed, "warn": warned, "fail": failed, "unverified": unverified}},
                      f, indent=2, ensure_ascii=False)
        print(f"Report saved: {vp}")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
