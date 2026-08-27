#!/usr/bin/env python3
"""zone_j_agent.py — Zone J: Hybrid Judgment Layer (V7 → V12.15)

5 independent agents that transform "hardcoded defaults" into "reasoned parameters".
Each agent reads its designated Zone A/B JSON inputs + optional V12 qualitative_summary.json.
Zone J is NOT computation — it outputs parameters + rationale for Python to consume.

V12: 新增 --qualitative-summary 标志，允许代理读取 Dayu 定性分析的
structured summary 作为额外的输入上下文，提升参数估计精度。
V12.15: 新增 governance_tension 代理，评估少数股东治理张力。

Usage:
    python3 scripts/zone_j_agent.py --code 01502.HK --agent moat --save-prompt output/01502_金融街物业/zone_j_prompt_moat.txt
    python3 scripts/zone_j_agent.py --code 01502.HK --agent moat --result result.json
    python3 scripts/zone_j_agent.py --code 01502.HK --agent moat --qualitative-summary output/XXXX/qualitative_summary.json

Agents: moat | capex | earnings_quality | data_quality | governance_tension
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
SHARED_QUALITATIVE_BASE = Path(__file__).resolve().parent.parent / "shared" / "qualitative"
DATA_DISCOUNT_BASIS = "observed_economic_carrier_v1"

AGENTS = {
    "moat": {
        "output_file": "moat_assessment.json",
        "description": "段永平视角：护城河证据提取 + B类参数 + g_base参数",
        "role_name": "duan",
        "allowed_inputs": ["segments.json", "financial_trends.json", "mda.json", "qualitative_summary.json"],
        "prompt_template_file": "zone_j/zone_j_duan.md",
    },
    "capex": {
        "output_file": "capex_classification.json",
        "description": "巴菲特视角：Capex 分类 + 增长类型 + 增量ROIC",
        "role_name": "buffett",
        "allowed_inputs": ["financial_trends.json", "mda.json", "qualitative_summary.json"],
        "prompt_template_file": "zone_j/zone_j_buffett.md",
    },
    "earnings_quality": {
        "output_file": "earnings_quality.json",
        "description": "芒格视角：AR收款检查 + AP超额融资 + 非经常项分类",
        "role_name": "munger",
        "allowed_inputs": ["financial_trends.json", "risks.json", "audit.json", "qualitative_summary.json"],
        "prompt_template_file": "zone_j/zone_j_munger.md",
    },
    "data_quality": {
        "output_file": "data_discount.json",
        "description": "李录视角：信息质量、经济折价 + 10年确定性",
        "role_name": "lilu",
        "allowed_inputs": ["financial_trends.json", "audit.json", "qualitative_summary.json"],
        "prompt_template_file": "zone_j/zone_j_lilu.md",
    },
    "governance_tension": {
        "output_file": "governance_tension.json",
        "description": "治理专家视角：少数股东治理张力 + 额外治理折价",
        "role_name": "governance_specialist",
        "allowed_inputs": ["governance.json", "audit.json", "mda.json", "qualitative_summary.json"],
        "prompt_template_file": "zone_j/zone_j_governance.md",
    },
}

VALIDATE_FIELDS = {
    "moat": ["b_penalty_final", "g_base"],
    "data_quality": ["total_discount_pct"],
    "governance_tension": ["governance_discount"],
}


def load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate_param_wrapper(data: dict, field: str) -> list[str]:
    errors: list[str] = []
    val = data.get(field)
    if val is None:
        errors.append(f"MISSING: {field}")
        return errors
    if isinstance(val, (int, float)):
        return errors
    if not isinstance(val, dict):
        errors.append(f"FORMAT: {field} is {type(val).__name__}, expected dict with {{value, rationale, evidence_ref, confidence}}")
        return errors

    for sub in ["value", "rationale", "evidence_ref", "confidence"]:
        if sub not in val:
            errors.append(f"MISSING: {field}.{sub}")
    if "evidence_ref" in val and (not isinstance(val["evidence_ref"], list) or len(val["evidence_ref"]) == 0):
        errors.append(f"EMPTY: {field}.evidence_ref")
    if "confidence" in val and val.get("confidence") not in {"high", "medium", "low"}:
        errors.append(f"INVALID: {field}.confidence")
    return errors




def _derive_company_name(stock_dir: str) -> str:
    base = os.path.basename(os.path.normpath(stock_dir))
    if "_" in base:
        return base.split("_", 1)[1]
    return base or "未知公司"


def _load_prompt_template(rel_path: str) -> str:
    path = SHARED_QUALITATIVE_BASE / rel_path
    if not path.exists():
        raise FileNotFoundError(f"Zone J prompt template missing: {path}")
    return path.read_text(encoding="utf-8")

def build_context(agent_name: str, stock_dir: str, ts_code: str, qualitative_summary_path: str | None = None) -> dict:
    """Load allowed input files and build context for the agent.

    V12: 支持加载 qualitative_summary.json 作为额外的定性上下文。
    """
    agent = AGENTS[agent_name]
    context: dict[str, Any] = {"ts_code": ts_code, "company_name": _derive_company_name(stock_dir)}
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

    # Missing inputs constrain the affected claim; they do not have a fixed
    # economic sign.  In particular, data_quality must not convert absence of
    # disclosure into an automatic valuation haircut.
    if missing:
        if agent_name == "data_quality":
            hint = (
                f"以下输入文件不可用: {missing}。降低相关主张置信度并扩大估值区间；"
                "不要仅因缺失降低估值中枢。若没有已观察、责任匹配的经济损失载体，"
                "total_discount_pct.value=0；非零折价必须引用该经济载体及其传导。"
            )
        else:
            hint = (
                f"以下输入文件不可用: {missing}。使用有界估计并标注confidence='low'。"
                "g_base默认2.0%, b_penalty默认0.25, mcapex_split_pct默认0.80。"
            )
        context["_degraded"] = {
            "missing_inputs": missing,
            "hint": hint,
        }

    return context


def build_prompt(agent_name: str, context: dict, qualitative_summary: dict | None = None) -> str:
    """Build the Zone J agent prompt.

    V12: 支持注入定性分析摘要文本。
    """
    agent = AGENTS[agent_name]
    qual_text = _format_qualitative_context(qualitative_summary)
    template = _load_prompt_template(agent["prompt_template_file"])
    return template.format(
        company_name=context.get("company_name", "未知公司"),
        code=context.get("ts_code", ""),
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

        errors = []
        for field in VALIDATE_FIELDS.get(args.agent, []):
            errors.extend(_validate_param_wrapper(data, field))

        if errors:
            print(f"❌ VALIDATION FAILED ({len(errors)} issues):")
            for e in errors:
                print(f"   {e}")
            return 1
        else:
            checked = ", ".join(VALIDATE_FIELDS.get(args.agent, [])) or "no wrapper fields"
            print(f"✅ VALIDATION PASSED: {checked}")
            return 0

    # Status
    print(f"Zone J Agent: {args.agent} — {agent['description']}")
    print(f"Allowed inputs: {agent['allowed_inputs']}")
    print(f"Output: {agent['output_file']}")
    print(f"\nUse --save-prompt to generate prompt, or --result to validate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
