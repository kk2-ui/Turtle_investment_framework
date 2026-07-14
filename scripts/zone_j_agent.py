#!/usr/bin/env python3
"""zone_j_agent.py — Zone J: Hybrid Judgment Layer (V7 → V12)

4 independent agents that transform "hardcoded defaults" into "reasoned parameters".
Each agent reads its designated Zone A/B JSON inputs + optional V12 qualitative_summary.json.
Zone J is NOT computation — it outputs parameters + rationale for Python to consume.

V12: 新增 --qualitative-summary 标志，允许四个代理读取 Dayu 定性分析的
structured summary 作为额外的输入上下文，提升参数估计精度。

Usage:
    python3 scripts/zone_j_agent.py --code 01502.HK --agent moat --save-prompt output/01502_金融街物业/zone_j_prompt_moat.txt
    python3 scripts/zone_j_agent.py --code 01502.HK --agent moat --result result.json
    python3 scripts/zone_j_agent.py --code 01502.HK --agent moat --qualitative-summary output/XXXX/qualitative_summary.json

Agents: moat | capex | earnings_quality | data_quality
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

AGENTS = {
    "moat": {
        "output_file": "moat_assessment.json",
        "description": "护城河证据提取 + B类参数 + g_base参数",
        "allowed_inputs": ["segments.json", "financial_trends.json", "mda.json", "qualitative_summary.json"],
        "prompt_template": """你是数据提取器和参数估算器，不是分析师。你的任务是把证据整理成结构化参数，不写结论。

【任务】基于以下结构化数据：(1)提取护城河证据（每条附原文引用），(2)识别B类/劣质业务板块并给出惩罚参数，(3)判断合理的g_base参数。

【定性分析上下文（V12新增）】
{qualitative_context}

【量化数据】
{context_json}

【输出要求】严格按以下JSON schema输出。只输出参数和证据，不输出评级、不输出叙事理由：

{{
  "moat_evidence": [
    {{"type": "品牌/规模/切换成本/网络效应/成本优势/监管/其他",
      "evidence": "从数据中找到的具体证据（引用数字）",
      "quote": "原文中包含该证据的句子",
      "durability": "5年以上/3-5年/不确定"}}
  ],
  "b_class_segments": [
    {{"name": "业务名称",
      "revenue_pct": 0.0,
      "margin_pct": 0.0,
      "classification": "B-劣/B-中/A",
      "penalty_pct": 0.0}}
  ],
  "b_penalty_final": 0.0,
  "g_base": 2.0,
  "g_scenarios": {{"pessimistic": 0.0, "base": 2.0, "optimistic": 3.5}},
  "value_trap_signals": ["仅从定性数据中观察到的价值陷阱信号。禁止引用:GG/DDM/s2/PE/市值/任何计算结果的数字。只准引用:毛利率趋势/竞争格局/管理层行为/行业趋势/商业模式/客户集中度等定性信号。"]

【强制规则】
1. 所有数字从输入数据中引用，不自行计算
2. b_penalty_final 是0.0-0.5之间的浮点数，附带 rationale 和 evidence_ref
3. g_base 通常1.0-4.0%，成熟企业偏低，成长企业偏高，附带 rationale 和 evidence_ref
4. 不要输出 moat_rating（评级）——这是 Zone C 的工作。但 rationale（判断理由）和 evidence_ref（证据引用）必须输出
5. moat_evidence 的每条必须附 quote（原文引用）
6. value_trap_signals 禁止包含: GG/DDM/R(NP)/PE/s2/市值/OCF/NP/ROE/任何计算数字
7. V9.2: b_penalty_final 和 g_base 输出为对象格式: {{"value": 数字, "rationale": "理由", "evidence_ref": ["来源1", "来源2"], "confidence": "high/medium/low"}}
8. V9.3 保守规则: 若 audit.json 中 data_gap:true 涉及金额 > NP 的 5%，强制 g_base.value 至少下调 0.5%，confidence 强制设为 "low"。理由: 未量化的一次性收益造成增长归因不确定性，估值参数必须反映此风险。"""
    },

    "capex": {
        "output_file": "capex_classification.json",
        "description": "Capex分类（维持性vs扩张性）+ 增长类型 + 增量ROIC",
        "allowed_inputs": ["financial_trends.json", "mda.json", "qualitative_summary.json"],
        "prompt_template": """你是投资分析助手。

【任务】分析该公司的资本支出结构，判断维持性vs扩张性Capex比例，评估增长质量。

【定性分析上下文（V12新增）】
{qualitative_context}

【量化数据】
{context_json}

【输出要求】：
{{
  "capex_type": "light_asset | heavy_asset | mixed",
  "mcapex_split_pct": 0.0,
  "mcapex_rationale": "为何维持性Capex占此比例",
  "growth_classification": {{
    "A_class_pct": 0.0,
    "B_class_pct": 0.0,
    "C_class_pct": 0.0,
    "rationale": "增长分类理由"
  }},
  "incremental_roic": [
    {{"period": "FY20XX-FY20XX", "delta_np_m": 0.0, "delta_invested_capital_m": 0.0, "roic_pct": 0.0, "classification": "A/B/C"}}
  ]
}}

【规则】
1. 维持性Capex = 维持现有运营必需的资本支出
2. 轻资产公司（物管/互联网）维持性Capex通常占70-90%
3. 增量ROIC = ΔNP / ΔInvestedCapital（NP变化/投入资本变化）
4. A类=主业扩产(ROIC>20%) B类=相关延伸(ROIC 10-20%) C类=非主业多元化(ROIC<10%)"""
    },

    "earnings_quality": {
        "output_file": "earnings_quality.json",
        "description": "收益质量：AR收款检查 + AP超额融资 + 非经常项分类",
        "allowed_inputs": ["financial_trends.json", "risks.json", "audit.json", "qualitative_summary.json"],
        "prompt_template": """你是投资分析助手。

【任务】评估该公司的收益质量，检查应收账款异常、应付账款融资、非经常项目。

【定性分析上下文（V12新增）】
{qualitative_context}

【量化数据】
{context_json}

【输出要求】：
{{
  "ar_quality": {{
    "collection_ratios": [
      {{"year": "FY20XX", "ratio": 0.0, "flag": "OK|WARN", "reason": "..."}}
    ],
    "ar_adjustment_needed": false,
    "adjustment_years": []
  }},
  "ap_excess_check": {{
    "dpo_by_year": [{{"year": "FY20XX", "dpo_days": 0}}],
    "excess_financing_flag": false,
    "rationale": "..."
  }},
  "non_recurring_items": {{
    "keep": [{{"item": "...", "reason": "持续性收入"}}],
    "exclude": [{{"item": "...", "amount_m": 0.0, "reason": "一次性"}}],
    "net_adjustment_m": 0.0
  }},
  "ocf_quality_flags": ["..."]
}}

【规则】
1. AR收款比率 = True Revenue / Revenue。如果AR增速>收入增速，标记WARN
2. DPO = AP / (Cost/365)。如果DPO显著拉长，可能超额融资
3. 非经常项：区分"保留"(持续性如利息收入)和"排除"(一次性如资产出售)"""
    },

    "data_quality": {
        "output_file": "data_discount.json",
        "description": "数据质量折价：来源评估 + 置信度 + 综合折价率",
        "allowed_inputs": ["financial_trends.json", "audit.json", "qualitative_summary.json"],
        "prompt_template": """你是投资分析助手。

【任务】评估数据质量，给出各因子置信度和综合折价率。

【定性分析上下文（V12新增）】
{qualitative_context}

【量化数据】
{context_json}

【输出要求】：
{{
  "discount_factors": [
    {{"factor": "...", "discount_pct": 0, "rationale": "..."}}
  ],
  "total_discount_pct": 0,
  "confidence_by_section": {{
    "factor2": "high|medium|low",
    "factor3_aa": "high|medium|low",
    "factor3_gg": "high|medium|low",
    "factor4_ddm": "high|medium|low"
  }}
}}

【规则】
1. 数据完整性高(所有DB字段可用)→折价5-10%。字段缺失多→15-25%
2. 审计质量(Big4→0-2%，非Big4持续无保留→2-5%)
3. 有PDF年报→置信度+1档；无PDF→-1档"""
    }
}


def load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_context(agent_name: str, stock_dir: str, ts_code: str, qualitative_summary_path: str | None = None) -> dict:
    """Load allowed input files and build context for the agent.

    V12: 支持加载 qualitative_summary.json 作为额外的定性上下文。
    """
    agent = AGENTS[agent_name]
    context: dict[str, Any] = {"ts_code": ts_code}
    missing: list[str] = []

    for fname in agent["allowed_inputs"]:
        # qualitative_summary.json 作为特殊输入，从指定路径加载
        if fname == "qualitative_summary.json" and qualitative_summary_path:
            path = qualitative_summary_path
        else:
            path = os.path.join(stock_dir, fname)
        data = load_json(path)
        if data:
            context[fname] = data
        else:
            if fname != "qualitative_summary.json":  # V12: qualitative context is optional
                context[fname] = {"_missing": True}
                missing.append(fname)

    # V7.2: Add degradation hint when inputs are missing
    if missing:
        context["_degraded"] = {
            "missing_inputs": missing,
            "hint": f"以下输入文件不可用: {missing}。使用你的行业知识做保守估计。所有估计值标注confidence='low'。g_base默认2.0%, b_penalty默认0.25, mcapex_split_pct默认0.80, total_discount_pct默认15%。"
        }

    return context


def build_prompt(agent_name: str, context: dict, qualitative_summary: dict | None = None) -> str:
    """Build the Zone J agent prompt.

    V12: 支持注入定性分析摘要文本。
    """
    agent = AGENTS[agent_name]
    # V12: 构建定性上下文文本
    qual_text = _format_qualitative_context(qualitative_summary)
    return agent["prompt_template"].format(
        context_json=json.dumps(context, indent=2, ensure_ascii=False),
        qualitative_context=qual_text,
    )


def _format_qualitative_context(qualitative_summary: dict | None) -> str:
    """将 qualitative_summary.json 格式化为 prompt 可用的文本。"""
    if not qualitative_summary:
        return "（未提供定性分析上下文，仅基于量化数据进行判断）"

    parts: list[str] = ["以下来自 Dayu 定性深度分析的结构化摘要，请优先参考这些定性判断：", ""]

    # 护城河相关
    ch3 = qualitative_summary.get("ch3_business_model", {})
    if ch3:
        parts.append("## 护城河与商业模式（来自定性Ch3）")
        parts.append(f"- 护城河评级: {ch3.get('moat_rating', 'N/A')}")
        parts.append(f"- 护城河来源: {', '.join(ch3.get('moat_sources', []))}")
        parts.append(f"- 护城河证据: {ch3.get('moat_evidence_summary', 'N/A')}")
        b_class = ch3.get("b_class_segments", [])
        if b_class:
            parts.append("- B类/劣质业务板块:")
            for seg in b_class:
                parts.append(f"  - {seg.get('name', '?')}: 收入占比{seg.get('revenue_pct', '?')}%, 分类={seg.get('classification', '?')}")
        parts.append(f"- b_penalty 证据: {ch3.get('b_penalty_evidence', 'N/A')}")
        parts.append(f"- g_base 上下文: {ch3.get('g_base_context', 'N/A')}")
        parts.append(f"- 关键约束: {', '.join(ch3.get('key_constraints', []))}")
        parts.append("")

    # 经营表现
    ch5 = qualitative_summary.get("ch5_operating_performance", {})
    if ch5:
        parts.append("## 经营表现（来自定性Ch5）")
        parts.append(f"- 增长质量: {ch5.get('growth_quality', 'N/A')}")
        parts.append(f"- 结构性vs周期性: {ch5.get('structural_vs_cyclical', 'N/A')}")
        parts.append(f"- 增量ROIC上下文: {ch5.get('incremental_roic_context', 'N/A')}")
        parts.append(f"- 数据可信度: {ch5.get('data_credibility_notes', 'N/A')}")
        parts.append("")

    # 财务表现
    ch6 = qualitative_summary.get("ch6_financial_performance", {})
    if ch6:
        parts.append("## 财务表现（来自定性Ch6）")
        parts.append(f"- 盈利质量: {ch6.get('earnings_quality', 'N/A')} — {ch6.get('earnings_quality_notes', '')}")
        parts.append(f"- 现金流质量: {ch6.get('cashflow_quality', 'N/A')}")
        parts.append(f"- 非经常项: {', '.join(ch6.get('non_recurring_items', []))}")
        parts.append(f"- 资本配置: {ch6.get('capital_allocation_quality', 'N/A')} — {ch6.get('capital_allocation_notes', '')}")
        parts.append("")

    # 治理
    ch8 = qualitative_summary.get("ch8_governance", {})
    if ch8:
        parts.append("## 治理（来自定性Ch8）")
        parts.append(f"- 治理评级: {ch8.get('governance_rating', 'N/A')}")
        parts.append(f"- 关键关注点: {', '.join(ch8.get('key_concerns', []))}")
        parts.append(f"- 数据折扣信号: {', '.join(ch8.get('data_discount_signals', []))}")
        parts.append("")

    # 风险
    ch9 = qualitative_summary.get("ch9_risks", {})
    if ch9:
        veto = ch9.get("veto_level_risks", [])
        if veto:
            parts.append("## 否决级风险（来自定性Ch9）")
            for v in veto:
                parts.append(f"- {v.get('risk', '?')}: 触发={v.get('trigger', '?')}, 影响={v.get('impact', '?')}")
            parts.append("")

    return "\n".join(parts)


def main():
    p = argparse.ArgumentParser(description="zone_j_agent.py — Zone J Hybrid Judgment Layer (V12)")
    p.add_argument("--code", type=str, required=True, help="Stock code")
    p.add_argument("--agent", type=str, required=True, choices=list(AGENTS.keys()))
    p.add_argument("--output", type=str, help="Output directory")
    p.add_argument("--save-prompt", type=str, help="Save LLM prompt to file")
    p.add_argument("--result", type=str, help="Path to LLM result JSON for validation")
    p.add_argument("--validate", type=str, help="Validate a Zone J output JSON (checks evidence_ref, confidence, etc.)")
    p.add_argument("--qualitative-summary", type=str, help="V12: Path to qualitative_summary.json (from Phase Q)")
    args = p.parse_args()

    # V12: 加载定性摘要
    qualitative_summary: dict | None = None
    if args.qualitative_summary:
        qualitative_summary = load_json(args.qualitative_summary)
        if qualitative_summary:
            print(f"📖 定性摘要已加载: {args.qualitative_summary}")
        else:
            print(f"⚠️ 定性摘要文件无法读取: {args.qualitative_summary}")

    # Find stock dir
    if args.output:
        stock_dir = args.output
    else:
        code_base = args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        candidates = [d for d in os.listdir(OUTPUT_BASE)
                      if os.path.isdir(os.path.join(OUTPUT_BASE, d)) and d.startswith(code_base)]
        if not candidates:
            print(f"ERROR: No output directory for {args.code}", file=sys.stderr)
            return 1
        # V8.1: prefer non-_HK_ directories
        candidates.sort(key=lambda x: ("_HK_" in x, x))
        stock_dir = os.path.join(OUTPUT_BASE, candidates[0])

    agent = AGENTS[args.agent]
    context = build_context(args.agent, stock_dir, args.code, qualitative_summary_path=args.qualitative_summary)

    if args.save_prompt:
        prompt = build_prompt(args.agent, context, qualitative_summary=qualitative_summary)
        prompt_path = args.save_prompt
        if not prompt_path.startswith("/") and "/" not in prompt_path:
            prompt_path = os.path.join(stock_dir, prompt_path)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        missing = [k for k, v in context.items() if isinstance(v, dict) and v.get("_missing")]
        print(f"✅ Zone J/{args.agent} prompt → {prompt_path}")
        print(f"   Context: {len(json.dumps(context)):,} chars | Missing inputs: {missing}")
        if qualitative_summary:
            print(f"   Qualitative context: YES ({len(json.dumps(qualitative_summary)):,} chars)")
        return 0

    if args.result:
        result_path = args.result
        if not result_path.startswith("/"):
            result_path = os.path.join(stock_dir, result_path)
        result = load_json(result_path)
        if not result:
            print(f"ERROR: Cannot read {result_path}", file=sys.stderr)
            return 1

        result["_provenance"] = {
            "generated_at": datetime.now().isoformat(),
            "agent": f"zone_j_{args.agent}",
            "context_files": agent["allowed_inputs"],
        }

        out_path = os.path.join(stock_dir, agent["output_file"])
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"✅ {agent['output_file']} written to {out_path}")
        return 0

    if args.validate:
        validate_path = args.validate
        if not validate_path.startswith("/"):
            validate_path = os.path.join(stock_dir, validate_path)
        data = load_json(validate_path)
        if not data:
            print(f"ERROR: Cannot read {validate_path}", file=sys.stderr)
            return 1

        # V9.2: Check required parameter audit fields
        errors = []
        param_fields = ["b_penalty_final", "g_base"]
        for field in param_fields:
            val = data.get(field)
            if val is None:
                errors.append(f"MISSING: {field}")
                continue
            if isinstance(val, dict):
                for sub in ["value", "evidence_ref", "confidence"]:
                    if sub not in val:
                        errors.append(f"MISSING: {field}.{sub}")
                if "evidence_ref" in val and (not val["evidence_ref"] or len(val["evidence_ref"]) == 0):
                    errors.append(f"EMPTY: {field}.evidence_ref")
            else:
                errors.append(f"FORMAT: {field} is {type(val).__name__}, expected dict with {{value, evidence_ref, confidence}}")

        if errors:
            print(f"❌ VALIDATION FAILED ({len(errors)} issues):")
            for e in errors:
                print(f"   {e}")
            return 1
        else:
            print(f"✅ VALIDATION PASSED: all parameters have evidence_ref + confidence")
            return 0

    # Status
    print(f"Zone J Agent: {args.agent} — {agent['description']}")
    print(f"Allowed inputs: {agent['allowed_inputs']}")
    print(f"Output: {agent['output_file']}")
    print(f"\nUse --save-prompt to generate prompt, or --result to validate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
