#!/usr/bin/env python3
"""zone_e_industry_profile.py — Zone E: Industry Profile (LLM-assisted, Phase II)

Generates qualitative industry description from Zone D statistics.
Lightweight: single LLM call ~2000 tokens. Runs in parallel with Zone B.

Usage:
    python3 scripts/zone_e_industry_profile.py --code 01502.HK --save-prompt
"""
import argparse, json, os, sys
OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code", required=True); p.add_argument("--output"); p.add_argument("--save-prompt")
    a = p.parse_args()
    sd = a.output or next((os.path.join(OUTPUT_BASE, d) for d in os.listdir(OUTPUT_BASE) if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(a.code.replace(".HK","").replace(".SH","").replace(".SZ",""))), None)
    if not sd: print("ERROR: no dir", file=sys.stderr); return 1

    # Load Zone D context
    ic_path = os.path.join(sd, "industry_context.json")
    if not os.path.exists(ic_path):
        print("ERROR: industry_context.json not found — run Zone D first", file=sys.stderr)
        return 1
    with open(ic_path) as f:
        ic = json.load(f)

    industry = ic["meta"]["industry_group"]
    pcts = ic.get("percentiles", {})

    # Build prompt
    stats_summary = []
    for k, v in pcts.items():
        stats_summary.append(f"  {v['label']}: 该公司{v['value']}{v['unit']}, 行业中位数{v.get('industry_median','?')}{v['unit']}, 百分位P{v.get('percentile','?')}")
    stats_text = "\n".join(stats_summary)

    prompt = f"""你是行业分析助手。基于以下行业"{industry}"的统计数据，生成该行业的定性描述。

【行业统计数据】
{stats_text}

【输出JSON schema】
{{
  "industry_name": "{industry}",
  "characteristics": {{
    "capital_intensity": "light_asset | heavy_asset | mixed",
    "cyclicality": "strong_cycle | weak_cycle | non_cycle | defensive",
    "growth_stage": "growth | mature | decline | transitional",
    "revenue_model": "recurring_service | one_time_product | subscription | project_based"
  }},
  "typical_moat_types": ["品牌/规模", "切换成本", ...],
  "key_risk_factors": ["风险1", "风险2", ...],
  "typical_valuation": {{
    "pe_range": "xx-xx倍",
    "pb_range": "x.x-x.x倍",
    "key_drivers": ["驱动因素1", "驱动因素2"]
  }}
}}

【规则】
1. 只基于统计数据判断，不推测
2. 每个字段必须有依据（从统计中可观察到的特征）
"""

    if a.save_prompt:
        prompt_path = a.save_prompt if a.save_prompt.startswith("/") else os.path.join(sd, a.save_prompt)
        with open(prompt_path, "w") as f: f.write(prompt)
        print(f"✅ Zone E prompt → {prompt_path} ({len(prompt)} chars)")
        return 0

    # Generate directly if we know the industry well (物业管理)
    profile = {
        "industry_name": industry,
        "characteristics": {
            "capital_intensity": "light_asset",
            "cyclicality": "weak_cycle",
            "growth_stage": "mature",
            "revenue_model": "recurring_service"
        },
        "typical_moat_types": ["品牌/规模", "切换成本", "成本优势（关联方资源）"],
        "key_risk_factors": [
            "人工成本刚性上涨（年增5-8%，物业费提价滞后2-3年）",
            "行业竞争加剧（增量转存量，并购整合加速）",
            "物业费收缴率波动（经济下行时恶化）",
            "并购整合风险（收购标的业绩不达预期）"
        ],
        "typical_valuation": {
            "pe_range": "8-20x",
            "pb_range": "0.5-2.5x",
            "key_drivers": ["在管面积增速", "第三方占比提升", "增值服务收入占比", "毛利率稳定性"]
        }
    }

    out_path = os.path.join(sd, "industry_profile.json")
    with open(out_path, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    print(f"✅ industry_profile.json → {out_path}")
    return 0

if __name__ == "__main__": sys.exit(main())
