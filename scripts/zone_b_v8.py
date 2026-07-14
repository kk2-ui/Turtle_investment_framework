#!/usr/bin/env python3
"""zone_b_v8.py — Zone B V8: 全文多Agent提取引擎

V8 replaces the old zone_b_extractor.py (single-year, keyword-based section mapping).
Key improvements:
  1. Uses pdf_full_text.json (5 years of scored paragraphs) instead of pdf_sections
  2. One Agent per year (parallel), extracting ALL 5 domains from full text
  3. Master Agent consolidates 5 years → cross-year trends + cross-validation
  4. Coordinator directly schedules agents (no manual .txt → LLM → .json step)

Architecture:
  Stage 1: 5 parallel year agents → zone_b_{year}_partial.json
  Stage 2: 1 master agent → mda/segments/risks/governance/audit.json

Usage:
  python3 scripts/zone_b_v8.py --code 02669.HK --stage year --year 2025 --save-prompt
  python3 scripts/zone_b_v8.py --code 02669.HK --stage master --save-prompt
"""

import argparse, json, os, sys

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

# ── Unified year-agent extraction schema ──
YEAR_SCHEMA = {
    "fiscal_year": "string",
    "revenue_highlights": [{
        "item": "string", "amount_m": "number|null", "unit": "string",
        "change_pct": "number|null", "quote": "string", "section": "string (MDA/SEG/STMT etc.)"
    }],
    "key_operations_metrics": [{
        "name": "string", "value": "number|null", "unit": "string",
        "yoy_change_pct": "number|null", "quote": "string"
    }],
    "mgmt_explanations": [{
        "topic": "string (revenue/cost/margin/profit/other)",
        "explanation": "string", "quote": "string"
    }],
    "forward_guidance": [{"item": "string", "detail": "string", "quote": "string"}],
    "strategy_changes": [{"item": "string", "detail": "string", "quote": "string"}],
    "segment_data": [{
        "name": "string", "revenue_m": "number|null", "revenue_pct": "number|null",
        "revenue_yoy_pct": "number|null", "gross_margin_pct": "number|null",
        "quote": "string"
    }],
    "risk_items": [{
        "category": "string (market/operational/financial/regulatory/other)",
        "description": "string", "severity": "string (high/medium/low)",
        "mitigation": "string", "quote": "string"
    }],
    "ar_aging": [{
        "bucket_label": "string (1年内/1-2年/2-3年/3年以上)",
        "amount_m": "number|null", "pct_of_total": "number|null",
        "provision_pct": "number|null", "quote": "string"
    }],
    "ar_total_m": "number|null",
    "goodwill_balance_m": "number|null",
    "goodwill_impairment_m": "number|null",
    "contingent_liabilities": [{
        "type": "string", "counterparty": "string",
        "amount_m": "number|null", "status": "string", "quote": "string"
    }],
    "related_party_transactions": [{
        "party_name": "string", "relationship": "string",
        "transaction_type": "string", "amount_m": "number|null",
        "pricing_basis": "string", "quote": "string"
    }],
    "audit_info": {
        "auditor": "string|null", "audit_opinion": "string|null",
        "key_audit_matters": ["string"],
        "going_concern_paragraph": "boolean|null",
        "report_date": "string|null", "quote": "string"
    },
    "non_recurring_items": [{
        "description": "string", "amount_m": "number|null",
        "nature": "string (经常/一次性)", "should_exclude": "boolean|null",
        "reason": "string", "quote": "string"
    }],
    "governance_events": [{
        "event": "string (管理层变动/董事会变动/回购/股权激励/关联交易变化)",
        "detail": "string", "year": "string", "quote": "string"
    }],
    "_extracted": [{
        "score": "number (1-10)", "topic": "string",
        "relevance": "string", "text": "string (原文verbatim)"
    }]
}

MASTER_SCHEMA = {
    "mda.json": {
        "year_highlights": "合并5年,每年3-5条",
        "key_operations_metrics": "合并5年,标注趋势",
        "mgmt_explanations": "合并5年,标注管理层口径变化",
        "forward_guidance": "合并5年,标注兑现情况",
        "strategy_changes": "合并5年,标注执行进度",
        "mda_key_financials": "5年汇总表(营收/NP/Capex/现金)",
        "trend_analysis": {"gross_margin_trend": "string", "revenue_growth_quality": "string",
                          "mgmt_credibility": "string", "strategic_execution": "string"}
    },
    "segments.json": {
        "segments": "5年分部数据,标注结构变化",
        "revenue_structure_evolution": "string (收入结构如何变化)",
        "margin_by_segment_trend": "string (各分部毛利率趋势)"
    },
    "risks.json": {
        "ar_aging": "5年账龄趋势",
        "principal_risks": "去重合并5年风险清单",
        "goodwill_trend": "商誉余额+减值趋势",
        "contingent_liabilities": "汇总5年或有事项",
        "risk_evolution": "string (风险如何演变)"
    },
    "governance.json": {
        "related_party_transactions": "5年关联交易去重列表",
        "governance_timeline": "管理层/董事会/审计师变动时间线",
        "transparency_assessment": "string (关联交易透明度评估)"
    },
    "audit.json": {
        "auditor_history": "5年审计师列表",
        "audit_opinion_history": "5年审计意见列表",
        "key_audit_matters": "5年KAM去重列表",
        "non_recurring_summary": "5年非经常项目汇总+分类(保留/扣除)",
        "accounting_policy_changes": "会计政策变更时间线"
    }
}


def find_stock_dir(ts_code):
    """V8.1: prefer non-_HK_ directories (e.g., 00882_天津发展 over 00882_HK_天津发展)."""
    code_base = ts_code.split(".")[0]
    candidates = []
    for e in os.listdir(OUTPUT_BASE):
        full = os.path.join(OUTPUT_BASE, e)
        if os.path.isdir(full) and e.startswith(code_base):
            candidates.append(e)
    if not candidates:
        return None
    # Prefer exact match or non-_HK_ variant
    candidates.sort(key=lambda x: ("_HK_" in x, x))
    return os.path.join(OUTPUT_BASE, candidates[0])


def load_pdf_full_text(stock_dir):
    path = os.path.join(stock_dir, "pdf_full_text.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def build_year_prompt(year: str, full_text: dict) -> str:
    """Build extraction prompt for a single fiscal year."""
    year_data = full_text.get("years", {}).get(year, {})
    if not year_data:
        return None

    sections = year_data.get("sections", {})
    # Build context: handle both formats (scored paragraphs list OR plain text dict)
    context_parts = []
    for sec_name, sec_content in sections.items():
        if isinstance(sec_content, list):
            # Format 1: [{score, text}, ...] — scored paragraphs
            sorted_paras = sorted(sec_content, key=lambda p: p.get("score", 0), reverse=True)
            sec_text = "\n".join(
                f"[score={p.get('score',0)}] {p.get('text','')}"
                for p in sorted_paras
            )
        elif isinstance(sec_content, dict) and "text" in sec_content:
            # Format 2: {label, char_count, text} — plain text
            sec_text = sec_content["text"]
        elif isinstance(sec_content, str):
            sec_text = sec_content
        else:
            continue
        if sec_text.strip():
            context_parts.append(f"=== {sec_name} ===\n{sec_text}")

    context = "\n\n".join(context_parts)

    prompt = f"""你是数据提取器。从以下港股公司 FY{year} 年报全文中提取结构化数据。

【年报全文 — FY{year}】
{context[:50000]}  {{{{…全文约{year_data.get('total_chars',0)}字,已按score排序}}}}

【提取Schema — 请输出以下JSON】
{json.dumps(YEAR_SCHEMA, indent=2, ensure_ascii=False)}

【强制规则】
1. 每个数字字段必须附带 "quote": "原文中包含该数字的完整句子"。无quote的字段填null。
2. 只提取FY{year}的数据。若原文同时提到去年和今年，只取今年。
3. 在所有section中搜索。年报章节标签可能不准，内容可能跨节。
4. 优先从 score≥8 的段落中提取，但不要遗漏低分段落中的重要数据。
5. 缺失字段填null，不编造，不推断。
6. _extracted数组: 选取10-15段最有价值的原文(score≥7优先)，完整verbatim，不截断。
7. 金额统一为百万元RMB（原文用千元→÷1000；原文用亿元→×100）。

输出纯JSON，不含markdown fence。"""
    return prompt


def write_zone_b_jsons(master_output: dict, stock_dir: str):
    """V8.1: Write master agent output as 5 Zone B JSON files."""
    files = ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"]
    for fname in files:
        if fname in master_output:
            path = os.path.join(stock_dir, fname)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(master_output[fname], f, indent=2, ensure_ascii=False)
            print(f"  ✅ {fname} ({os.path.getsize(path):,}b)")
    missing = [f for f in files if f not in master_output]
    if missing:
        print(f"  ⚠️ Missing: {missing}")


def build_master_prompt(ts_code: str, stock_dir: str) -> str:
    """Build consolidation prompt for the master agent."""
    # Load all 5 partial JSONs
    partials = {}
    for year in ["2021", "2022", "2023", "2024", "2025"]:
        path = os.path.join(stock_dir, f"zone_b_{year}_partial.json")
        if os.path.exists(path):
            with open(path) as f:
                partials[year] = json.load(f)

    if not partials:
        return None

    # Load compute_bundle for cross-validation
    cb_path = os.path.join(stock_dir, "compute_bundle.json")
    cb = {}
    if os.path.exists(cb_path):
        with open(cb_path) as f:
            cb = json.load(f)

    prompt = f"""你是 Zone B 汇总分析师。你有5年的结构化提取结果，需要：(1)识别跨年趋势 (2)交叉验证数字 (3)输出最终Zone B JSON。

【5年提取结果】
{json.dumps({y: {k: v for k, v in d.items() if k != '_extracted'} for y, d in partials.items()}, indent=2, ensure_ascii=False)[:30000]}

【财务数字交叉验证参考 (compute_bundle.json)】
{json.dumps({
    "market": cb.get("market", {}),
    "factor2": {k: cb.get("factor2", {}).get(k) for k in ["np_avg_3y","np_avg_5y","ocf_np_ratio"] if k in cb.get("factor2", {})},
    "factor3": {"aa": cb.get("factor3", {}).get("aa", {})},
}, indent=2, ensure_ascii=False)}

【任务】
1. 跨年趋势识别（每个趋势 1-2 句）:
   a. 毛利率方向+幅度 (5年序列)
   b. 营收增长质量 (是否增收不增利)
   c. 管理层变动/审计师更换
   d. 减值趋势 (应收/商誉)
   e. 关联交易变化
   f. 战略方向变化

2. 数字交叉验证:
   - 对比各年提取的营收/NP vs compute_bundle.json 中的 aa/true_revenue 序列
   - 偏差>5% → 标注 WARN，以 compute_bundle 为准
   - 若某年数据缺失，标注并尝试从相邻年差值推算

3. 输出以下 JSON（直接写文件内容，不要 markdown fence）:

```json
{{
  "mda.json": {json.dumps(MASTER_SCHEMA['mda.json'], indent=4, ensure_ascii=False)},
  "segments.json": {json.dumps(MASTER_SCHEMA['segments.json'], indent=4, ensure_ascii=False)},
  "risks.json": {json.dumps(MASTER_SCHEMA['risks.json'], indent=4, ensure_ascii=False)},
  "governance.json": {json.dumps(MASTER_SCHEMA['governance.json'], indent=4, ensure_ascii=False)},
  "audit.json": {json.dumps(MASTER_SCHEMA['audit.json'], indent=4, ensure_ascii=False)}
}}
```

【规则】
1. 所有金额: 百万元 RMB
2. 5年数据用表格展示,每年一行
3. 趋势判断必须有数据支撑,标注"FY20XX→FY20YY: 从X到Y"
4. 交叉验证标注: "✅一致(<5%)" 或 "⚠️偏差X%(年报=A vs compute=B,以compute为准)"
5. 缺失数据标注 "⚠️ 不可用",不编造"""
    return prompt


def main():
    p = argparse.ArgumentParser(description="zone_b_v8.py — Zone B V8 全文多Agent提取")
    p.add_argument("--code", required=True)
    p.add_argument("--stage", choices=["year", "master"], required=True,
                   help="year: 年度提取 | master: 汇总")
    p.add_argument("--year", help="财年 (仅 --stage year)")
    p.add_argument("--save-prompt", action="store_true", help="保存prompt到文件")
    p.add_argument("--auto", action="store_true", help="自动模式(添加降级提示:数据不足时引用financial_trends)")
    p.add_argument("--write", action="store_true", help="Master Agent: 写入5个Zone B JSON而非打印prompt")
    args = p.parse_args()

    stock_dir = find_stock_dir(args.code)
    if not stock_dir:
        print(f"ERROR: output dir not found for {args.code}", file=sys.stderr)
        return 1

    if args.stage == "year":
        if not args.year:
            print("ERROR: --year required for stage=year", file=sys.stderr)
            return 1

        full_text = load_pdf_full_text(stock_dir)
        if not full_text:
            print(f"ERROR: pdf_full_text.json not found in {stock_dir}", file=sys.stderr)
            print("  Run: python3 scripts/build_full_text.py --code " + args.code)
            return 1

        prompt = build_year_prompt(args.year, full_text)
        if not prompt:
            print(f"ERROR: FY{args.year} not found in pdf_full_text", file=sys.stderr)
            return 1

        if args.auto:
            prompt += "\n\n【自动模式】如果以上全文数据不足以提取某字段,标注⚠️并从financial_trends.json引用定量数据(营收/NP/OCF/Capex)。尽量用原文填充定性字段,定量可回退到financial_trends。"

        if args.save_prompt:
            path = os.path.join(stock_dir, f"zone_b_v8_{args.year}_prompt.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(prompt)
            print(f"✅ Year prompt → {path}")
            print(f"   📊 {len(prompt):,} chars {'(auto)' if args.auto else ''}")
        else:
            print(prompt)

    elif args.stage == "master":
        prompt = build_master_prompt(args.code, stock_dir)
        if not prompt:
            print("ERROR: no zone_b_*_partial.json files found. Run --stage year first.", file=sys.stderr)
            return 1

        if args.save_prompt:
            path = os.path.join(stock_dir, "zone_b_v8_master_prompt.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(prompt)
            print(f"✅ Master prompt → {path}")
            print(f"   📊 {len(prompt):,} chars")
            print(f"💡 协调器: 读取此prompt → LLM汇总 → 输出5个Zone B JSON")
        else:
            print(prompt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
