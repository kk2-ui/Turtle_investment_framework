#!/usr/bin/env python3
"""report_assembler.py — Zone C: 组装报告上下文

将 Zone A (compute_bundle.json + financial_trends.json) 和
Zone B (mda/segments/risks/governance/audit.json) 组装成
LLM 写报告的完整上下文包。

Usage:
  python3 scripts/report_assembler.py --code 01502.HK
  python3 scripts/report_assembler.py --code 01502.HK --section factor2
"""

import argparse, json, os, sys

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

SECTIONS = {
    "meta": "报告元信息",
    "executive_summary": "Executive Summary",
    "assumptions": "关键假设汇总",
    "financial_trends": "财务趋势速览",
    "factor1a": "因子1A：五分钟快筛",
    "factor1b": "因子1B：深度定性分析",
    "factor1c": "因子1C：增量增长检验",
    "factor2": "因子2：穿透回报率粗算",
    "factor3": "因子3：穿透回报率精算",
    "factor4": "因子4：DDM阶梯买入估值",
    "verdict": "最终综合输出",
    "risks": "风险提示与数据来源",
}

def find_stock_dir(ts_code):
    for e in os.listdir(OUTPUT_DIR):
        if e.startswith(ts_code.replace(".","_")) or e.startswith(ts_code.split(".")[0]+"_") and os.path.isdir(os.path.join(OUTPUT_DIR, e)):
            return os.path.join(OUTPUT_DIR, e)
    return None

def load_json(path):
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return None

def assemble_context(ts_code, section=None):
    """Assemble context package for report writing."""
    stock_dir = find_stock_dir(ts_code)
    if not stock_dir:
        return {"error": f"output dir not found for {ts_code}"}

    # Load all available data
    bundle = load_json(os.path.join(stock_dir, "compute_bundle.json"))
    trends = load_json(os.path.join(stock_dir, "financial_trends.json"))
    mda = load_json(os.path.join(stock_dir, "mda.json"))
    segments = load_json(os.path.join(stock_dir, "segments.json"))
    risks = load_json(os.path.join(stock_dir, "risks.json"))
    governance = load_json(os.path.join(stock_dir, "governance.json"))
    audit = load_json(os.path.join(stock_dir, "audit.json"))

    # Build section-specific context
    context = {
        "code": ts_code,
        "name_cn": trends.get("name_cn", "") if trends else "",
        "stock_dir": stock_dir,
        "available_data": {
            "compute_bundle": bundle is not None,
            "financial_trends": trends is not None,
            "mda": mda is not None,
            "segments": segments is not None,
            "risks": risks is not None,
            "governance": governance is not None,
            "audit": audit is not None,
        }
    }

    if bundle:
        context["compute_bundle"] = {
            "meta": bundle.get("meta", {}),
            "market": bundle.get("market", {}),
            "params": bundle.get("params", {}),
            "factor2": {k: v for k, v in bundle.get("factor2", {}).items() if k != "rejection"},
            "factor2_rejection": bundle.get("factor2", {}).get("rejection", {}),
            "factor3": {k: v for k, v in bundle.get("factor3", {}).items() if k not in ["_income_raw", "rejection"]},
            "factor3_rejection": bundle.get("factor3", {}).get("rejection", {}),
            "factor4": {k: v for k, v in bundle.get("factor4", {}).items() if k != "rejection"},
            "factor4_rejection": bundle.get("factor4", {}).get("rejection", {}),
            "rejection_summary": bundle.get("rejection_summary", {}),
        }

    if trends:
        context["financial_trends"] = {
            "n_years": trends.get("n_years"),
            "fiscal_years": trends.get("fiscal_years"),
            "growth_analysis": trends.get("growth_analysis"),
            "income_trend": trends.get("income_trend"),
            "balance_sheet_trend": trends.get("balance_sheet_trend"),
            "cashflow_trend": trends.get("cashflow_trend"),
            "per_share_trend": trends.get("per_share_trend"),
            "profitability_ratios": trends.get("profitability_ratios"),
        }

    # Zone B data
    for name, data in [("mda", mda), ("segments", segments), ("risks", risks),
                        ("governance", governance), ("audit", audit)]:
        if data:
            context[f"zone_b_{name}"] = data

    # If a specific section is requested, add section-specific guidance
    if section:
        context["section_guidance"] = {
            "section": section,
            "title": SECTIONS.get(section, section),
            "data_to_use": get_section_data_mapping(section),
        }

    return context

def get_section_data_mapping(section):
    """Map report sections to the data they need."""
    mapping = {
        "meta": ["compute_bundle.meta", "compute_bundle.market", "compute_bundle.params", "financial_trends.name_cn"],
        "executive_summary": ["compute_bundle.factor2", "compute_bundle.factor3.gg", "compute_bundle.factor4.ddm_v_hkd", "compute_bundle.rejection_summary", "financial_trends.growth_analysis"],
        "assumptions": ["compute_bundle.params"],
        "financial_trends": ["financial_trends.income_trend", "financial_trends.balance_sheet_trend", "financial_trends.cashflow_trend", "financial_trends.profitability_ratios"],
        "factor1a": ["financial_trends.income_trend", "financial_trends.cashflow_trend", "compute_bundle.factor2.fcf_positive_5y"],
        "factor1b": ["zone_b_mda", "zone_b_segments", "zone_b_risks", "zone_b_governance", "compute_bundle.factor3"],
        "factor1c": ["financial_trends.income_trend", "financial_trends.cashflow_trend", "compute_bundle.factor3.aa"],
        "factor2": ["compute_bundle.factor2", "compute_bundle.factor2_rejection"],
        "factor3": ["compute_bundle.factor3", "compute_bundle.factor3_rejection"],
        "factor4": ["compute_bundle.factor4", "compute_bundle.factor4_rejection"],
        "verdict": ["compute_bundle.rejection_summary", "compute_bundle.factor4.position", "compute_bundle.factor4.value_trap"],
        "risks": ["zone_b_risks", "compute_bundle.factor4.stop_loss"],
    }
    return mapping.get(section, [])

def main():
    p = argparse.ArgumentParser(description="report_assembler.py — Zone C")
    p.add_argument("--code", required=True)
    p.add_argument("--section", choices=list(SECTIONS.keys()), help="Assemble context for specific section")
    p.add_argument("--all-sections", action="store_true", help="Generate all section prompts")
    args = p.parse_args()

    if args.all_sections:
        for sec in SECTIONS:
            ctx = assemble_context(args.code, sec)
            if "error" in ctx:
                print(f"ERROR: {ctx['error']}")
                return 1
            stock_dir = ctx["stock_dir"]
            prompt_path = os.path.join(stock_dir, f"zone_c_prompt_{sec}.json")
            with open(prompt_path, "w") as f:
                json.dump(ctx, f, indent=2, ensure_ascii=False, default=str)
            print(f"✅ {sec}")
        print(f"\nAll {len(SECTIONS)} section prompts saved to {stock_dir}/zone_c_prompt_*.json")
    else:
        ctx = assemble_context(args.code, args.section)
        if "error" in ctx:
            print(f"ERROR: {ctx['error']}", file=sys.stderr)
            return 1

        stock_dir = ctx["stock_dir"]
        sec = args.section or "full"
        out_path = os.path.join(stock_dir, f"zone_c_context_{sec}.json")
        with open(out_path, "w") as f:
            json.dump(ctx, f, indent=2, ensure_ascii=False, default=str)
        print(f"✅ Context assembled → {out_path}")
        print(f"   Available data: {json.dumps(ctx['available_data'], indent=2)}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
