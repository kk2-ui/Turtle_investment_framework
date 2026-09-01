#!/usr/bin/env python3
"""zone_b_extractor.py — Zone B: LLM 结构化提取编排器

从 PDF 提取 → LLM 处理 → 5 个结构化 JSON:
  mda.json        — MD&A 管理层讨论与分析
  segments.json   — 分部报告
  risks.json      — 风险因素
  governance.json — 公司治理
  audit.json      — 审计意见

Usage:
  python3 scripts/zone_b_extractor.py --code 01502.HK --extractor mda --save-prompt
  python3 scripts/zone_b_extractor.py --code 01502.HK --extractor mda --result result.json
  python3 scripts/zone_b_extractor.py --code 01502.HK --all --save-prompts
"""

import re

import argparse, json, os, sys

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
SCRIPTS_DIR = os.path.dirname(__file__)

# ── Extraction schemas (V7.2 — aligned with boundary_validator + actual outputs + downstream consumers) ──
SCHEMAS = {
    "mda": {
        "description": "管理层讨论与分析 (MD&A)",
        "schema": {
            "year_highlights": [{"item": "string", "amount_m": "number|null", "change_pct": "number|null", "quote": "string"}],
            "key_operations_metrics": [{"name": "string", "value": "number|null", "unit": "string", "yoy_change_pct": "number|null"}],
            "mgmt_explanations": [{"topic": "string", "explanation": "string", "quote": "string"}],
            "forward_guidance": [{"item": "string", "detail": "string", "quote": "string"}],
            "strategy_changes": [{"item": "string", "detail": "string", "quote": "string"}],
            "mda_key_financials": {"total_revenue_m": "number|null", "total_revenue_yoy_pct": "number|null",
                "operating_profit_m": "number|null", "net_profit_attributable_m": "number|null",
                "capex_m": "number|null", "cash_and_bank_m": "number|null"},
        }
    },
    "segments": {
        "description": "分部报告",
        "schema": {
            "segments": [{
                "name": "string", "revenue_m": "number|null", "revenue_pct": "number|null",
                "revenue_yoy_pct": "number|null", "gross_margin_pct": "number|null", "note": "string",
            }],
            "total_revenue_m": "number|null", "total_revenue_yoy_pct": "number|null",
            "property_mgmt_weighted_gross_margin": "number|null",
            "gfa_under_management_m_sqm": "number|null", "gfa_yoy_pct": "number|null",
            "gfa_source_independent_pct": "number|null",
        }
    },
    "risks": {
        "description": "风险因素",
        "schema": {
            "ar_aging": [{"bucket_label": "string", "amount_m": "number|null", "pct_of_total": "number|null"}],
            "ar_total_m": "number|null",
            "goodwill_balance_m": "number|null", "goodwill_impairment_m": "number|null",
            "contingent_liabilities": [{"type": "string", "counterparty": "string", "amount_m": "number|null", "status": "string"}],
            "capital_commitments_m": "number|null",
            "principal_risks": [{"category": "string", "description": "string", "severity": "string", "mitigation": "string"}],
        }
    },
    "governance": {
        "description": "公司治理",
        "schema": {
            "related_party_transactions": [{"party_name": "string", "relationship": "string",
                "transaction_type": "string", "amount_m": "number|null", "pricing_basis": "string", "quote": "string"}],
            "total_related_party_revenue_m": "number|null", "related_party_revenue_pct": "number|null",
            "transparency_flag": "string — clean|elevated|high",
            "controlling_shareholder": "string", "governance_red_flags": ["string"],
            "board_structure": {"note": "string"}, "governance_highlights": ["string"],
        }
    },
    "audit": {
        "description": "审计意见",
        "schema": {
            "auditor": "string", "audit_opinion": "string — unqualified|qualified|adverse|disclaimer",
            "report_date": "string", "going_concern_paragraph": "boolean",
            "key_audit_matters": [{"matter": "string", "quote": "string"}],
            "auditor_change": "boolean", "material_weakness": "boolean",
            "non_recurring_items": [{"description": "string", "amount_m": "number|null", "nature": "string", "quote": "string"}],
            "non_recurring_total_m": "number|null",
            "accounting_policy_changes": ["string"],
        }
    },
}

def find_stock_dir(ts_code):
    """Find output directory for a stock code. Prefers exact matches over _HK_ variants."""
    code_base = ts_code.split(".")[0]
    candidates = []
    for e in os.listdir(OUTPUT_DIR):
        full = os.path.join(OUTPUT_DIR, e)
        if not os.path.isdir(full): continue
        if e.startswith(code_base + "_") and not e.startswith(code_base + "_HK_"):
            candidates.append((full, 0))  # exact match: 01502_金融街物业
        elif e.startswith(code_base + "_HK_"):
            candidates.append((full, 1))  # backup: 01502_HK_金融街物业
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0] if candidates else None

def detect_language(text: str) -> str:
    """Detect whether text is primarily Chinese or English. Returns 'zh' or 'en'."""
    if not text: return 'en'
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    total_chars = len(text.strip())
    return 'zh' if (chinese_chars / max(total_chars, 1)) > 0.15 else 'en'


def generate_prompt(ts_code, extractor_name):
    """Generate LLM prompt for extracting structured data from PDF sections.
    Auto-detects language and uses bilingual prompts."""
    schema_info = SCHEMAS[extractor_name]
    stock_dir = find_stock_dir(ts_code)
    if not stock_dir:
        return None, f"output dir not found for {ts_code}"

    # Find PDF sections (latest year first, annual preferred over interim)
    pdf_sections = None
    pdf_year = None
    # V7.2: Accept both pdf_sections_2025.json (new) and pdf_sections.json (legacy)
    pdf_files = [f for f in os.listdir(stock_dir)
                 if (f.startswith("pdf_sections_") or f == "pdf_sections.json") and f.endswith(".json")]
    # V7.2 sort: annual > interim, higher year > lower, non-FORMATTED > _FORMATTED, legacy last
    pdf_files.sort(key=lambda x: (
        x.startswith("pdf_sections_interim_"),
        x == "pdf_sections.json",
        "_FORMATTED" in x,  # prefer non-FORMATTED when same year
        -int(re.search(r'pdf_sections_(\d{4})', x).group(1)) if re.search(r'pdf_sections_(\d{4})', x) else 0
    ))
    if pdf_files:
        f = pdf_files[0]
        with open(os.path.join(stock_dir, f)) as fh:
            pdf_sections = json.load(fh)
        ym = re.search(r'pdf_sections_(\d{4})', f)
        if ym: pdf_year = ym.group(1)

    context = ""
    if pdf_sections:
        # V7.2: Refined mapping — removed irrelevant SUB from mda, added P2/P13
        # Section key reference:
        #   MDA=管理层讨论与分析  SEG=分部报告  P2=受限资产  P3=应收账龄
        #   P4=关联方交易  P6=或有事项  P13=非经常性损益  STMT=财务报表(含附注)
        #   DAN=董事及高管+关联方明细(pdf_preprocessor标签)  SUB=子公司注册信息(不用于提取)
        mapping = {
            "mda":        {"sections": ["MDA", "SEG"], "max_chars": 30000},
            "segments":   {"sections": ["MDA", "SEG"], "max_chars": 25000},
            "risks":      {"sections": ["MDA", "P3", "P6", "P2"], "max_chars": 25000},
            "governance": {"sections": ["MDA", "P4", "DAN"], "max_chars": 25000},
            "audit":      {"sections": ["MDA", "STMT", "P13"], "max_chars": 30000},
        }
        cfg = mapping.get(extractor_name)
        if cfg:
            parts = []
            for key in cfg["sections"]:
                content = pdf_sections.get(key, "")
                if content and isinstance(content, str) and len(content.strip()) > 0:
                    parts.append((key, content))
            # V7.2: proportional budget allocation — prevent MDA from eating all budget
            if parts:
                budget_per = max(2000, cfg["max_chars"] // len(parts))
                truncated_parts = []
                for key, content in parts:
                    truncated_parts.append(f"=== {key} ===\n{content[:budget_per]}")
                context = "\n\n---\n\n".join(truncated_parts)
            else:
                context = ""

    lang = detect_language(context)
    year_hint = f" ({pdf_year} annual report)" if pdf_year else ""

    if lang == 'zh':
        prompt = f"""你是数据提取器。从以下港股公司年报段落中提取结构化数据，输出JSON。

公司: {ts_code}{year_hint}
提取目标: {schema_info['description']}

年报原文:
{context if context else '(未找到PDF段落。请使用你对这家公司的了解。) '}

输出JSON schema:
```json
{json.dumps(schema_info['schema'], indent=2, ensure_ascii=False)}
```

规则:
1. 只输出JSON对象，不要任何解释
2. 无法确定的字段填null
3. 数字用数值类型，不要字符串
4. 金额统一为百万元RMB（千元÷1000,万元÷100,亿元×100）
5. 如原文为英文，提取关键数字和事实即可

【字段级提取要求——来自旧框架Phase2精提取规则】

P2-受限现金:提取受限现金总额+明细(质押/保证金/冻结/监管/其他各金额+用途)。占货币资金比例。
P3-应收账款:提取AR总额+账龄分布(1年内/1-2年/2-3年/3年以上各金额+占比)+坏账准备+计提政策摘要+关联方应收占比。
P4-关联交易:提取重大关联交易(前5大:关联方名称/关系/交易性质/金额/定价基础)+关联交易总额+占收入成本比例。8项完整性自检(关联方名称/关系/交易性质/定价基础/金额/占比/独立估值/期末余额),缺失项≤2。
P6-或有负债:提取对外担保(担保对象/金额/是否关联方)+重大诉讼(案件/金额/进展)+资本承诺+经营租赁承诺。
P13-非经常性损益:提取7类(资产处置/政府补贴/公允价值变动/汇兑损益/保险赔款/投资收益/其他)各金额+性质+非经常合计+占税前利润比例。
STMT-财务报表:提取完整IS(营收/成本/毛利/经营利润/税前利润/所得税/归母NP/EPS)+BS(现金/AR/总资产/总负债/归母权益)+CF(OCF/D&A/Capex)。26字段覆盖自检:🔴核心(营收/归母NP/现金/总资产/归母权益/OCF/Capex)≥6个可用否则标注降级。

【提取失败协议】
≥2个🔴核心字段缺失→标注"⚠️关键数据缺失,转入降级模式"
null处理:若章节为null→对应JSON中标注"⚠️PDF未找到相关章节"

【_quality 自检报告——每个JSON必须输出,Zone C依赖此字段判断数据可信度】
在JSON末尾追加 `_quality` 对象:
- sections_searched: [列出搜索了哪些section,如"MDA+P3+P6"]
- sections_found: [列出实际包含有效内容的section]
- content_mismatch: true/false — 章节内容是否与提取目标错配(如risks section实际是董事会报告)
- completeness_score: 1-10 — 提取字段的完整度
- key_missing: [列出重要缺失字段]
- recommendation: "Zone C建议:该Extractor数据可信度[高/中/低]"
6. ⚠️ 质量要求：每个数组字段至少2-5条；每条文本字段至少50字符；每条数字字段必须附quote原文

【你的角色：资深金融分析师 + 行业专家】

你拿到的是年报的多个章节（可能包含 MDA/SEG/P3/P4/P6/STMT 中的若干个，以 === XXX === 标注）。
你的任务是在这些章节中搜索与你的提取目标相关的所有段落，然后做两件事：
① 按 schema 提取结构化字段（数字+事实+quote）——从所有章节中找
② 从所有章节中精选投资分析价值最高的段落，完整 verbatim 保留

⚠️ 关键：pdf_preprocessor 可能把内容放错章节（比如管理层讨论放在了治理报告section）。
你要主动在所有提供的章节中搜索相关内容，不被章节标签限制。

【_extracted 字段规则——必须输出，这是 Zone C 的核心定性输入】
- 从原文中选出 8-15 段最有投资分析价值的段落
- 每段包含：
  score(1-10分,段落对投资判断的重要性)
  topic(话题标签,如"竞争格局""管理层对增速的解释""行业政策风险")
  relevance(为什么这段对分析重要,一句话)
  text(原文verbatim完整段落,不截断,不改写,不总结)
- score ≥8 的段落必须全部包含
- 排序：score 从高到低
- _extracted 总字符数应占输出的 60% 以上。目标输出总计 8-15KB"""
    else:
        prompt = f"""You are extracting structured data from a Hong Kong-listed company's annual report.

COMPANY: {ts_code}{year_hint}
EXTRACTION TARGET: {schema_info['description']}

CONTEXT FROM ANNUAL REPORT:
{context if context else '(No PDF sections found. Use your knowledge of this company.)'}

OUTPUT SCHEMA (JSON only, no markdown):
```json
{json.dumps(schema_info['schema'], indent=2, ensure_ascii=False)}
```

RULES:
1. Output ONLY the JSON object — no explanations, no markdown fences
2. If a field cannot be determined, use null
3. Numbers should be numeric, not strings
4. All amounts in 百万元 RMB unless specified otherwise (千元÷1000, 万元÷100, 亿元×100)
5. If text is mixed Chinese/English, extract from whichever language has the data

【FIELD-LEVEL EXTRACTION — from legacy Phase2】
P2-Restricted Cash: Total + breakdown (pledge/margin/frozen/regulatory/other × amount+purpose). % of total cash.
P3-AR Aging: Total AR + aging (within 1yr/1-2yr/2-3yr/3yr+ × amount+%) + bad debt provision + policy summary + related party AR%.
P4-Related Party: Top 5 RPTs (name/relationship/nature/amount/pricing) + total RPT + % of revenue. 8-item completeness check.
P6-Contingent: Guarantees + litigation + capital commitments + lease commitments.
P13-Non-recurring: 7 categories (disposal/subsidies/FV/FX/insurance/investment/other) × amount+nature + % of pretax profit.
STMT: Full IS+BS+CF. 26-field matrix — 🔴CORE(revenue/NP/cash/TA/equity/OCF/Capex) ≥6 available else degraded.
【_quality SELF-REPORT — MANDATORY, Zone C depends on this】
Append `_quality` object to JSON output:
- sections_searched: [list sections searched]
- sections_found: [list sections with valid content]
- content_mismatch: true/false — is section content misaligned with extraction target?
- completeness_score: 1-10
- key_missing: [list important missing fields]
- recommendation: "Zone C: data confidence [high/medium/low]"
【FAILURE】≥2 🔴CORE missing → "⚠️ critical data missing, degraded mode".
6. ⚠️ QUALITY: Each array field ≥2 items; text fields ≥50 chars; numeric fields must include verbatim quote

【YOUR ROLE: Senior Financial Analyst + Industry Expert】

You are reading MULTIPLE sections of an annual report (marked with === SECTION_NAME ===).
Your job: search across ALL provided sections for content relevant to your extraction target, then:
① Extract structured fields per the schema (numbers + facts + quotes) — search ALL sections
② Select the most investment-analysis-valuable paragraphs and preserve them VERBATIM

⚠️ CRITICAL: The pdf_preprocessor may have placed content in the wrong sections
(e.g. management discussion appearing in governance report). You must actively search
across ALL provided sections — do not limit yourself to what the section label suggests.

【_extracted field rules — MANDATORY, this is Zone C's core qualitative input】
- Select 8-15 paragraphs with the highest investment analysis value
- Each entry contains:
  score (1-10, how important this paragraph is for investment judgment)
  topic (topic tag, e.g. "competitive moat", "management on growth slowdown", "regulatory risk")
  relevance (one sentence on why this matters for analysis)
  text (original paragraph VERBATIM — no truncation, no rewriting, no summarization)
- All paragraphs scoring ≥8 MUST be included
- Sort: highest score first
- _extracted should account for ≥60% of total output. Target total output: 8-15KB"""
    return prompt, None

def validate_result(extractor_name, result_json):
    """Validate LLM output against schema. Returns (is_valid, errors)."""
    schema = SCHEMAS[extractor_name]["schema"]
    errors = []

    if not isinstance(result_json, dict):
        return False, ["Result is not a JSON object"]

    # Check all top-level keys exist + basic type validation (V7.2)
    for key, spec in schema.items():
        if key not in result_json or result_json[key] is None:
            errors.append(f"Missing key: {key}")
            continue
        val = result_json[key]
        if isinstance(spec, list):
            if not isinstance(val, list):
                errors.append(f"Type mismatch: {key} expected list, got {type(val).__name__}")
        elif isinstance(spec, dict):
            if not isinstance(val, dict):
                errors.append(f"Type mismatch: {key} expected dict, got {type(val).__name__}")
        elif isinstance(spec, str):
            if "number" in spec and not isinstance(val, (int, float)):
                errors.append(f"Type mismatch: {key} expected number, got {type(val).__name__}")

    # V7.2: Check for _extracted array (critical for Zone C depth)
    if "_extracted" not in result_json or not isinstance(result_json.get("_extracted"), list):
        errors.append("Missing _extracted array (required for Zone C qualitative depth)")
    elif len(result_json.get("_extracted", [])) < 3:
        errors.append(f"_extracted has only {len(result_json['_extracted'])} items (min 3)")

    return len(errors) == 0, errors

def main():
    p = argparse.ArgumentParser(description="zone_b_extractor.py — Zone B")
    p.add_argument("--code", required=True)
    p.add_argument("--extractor", choices=list(SCHEMAS.keys()))
    p.add_argument("--all", action="store_true", help="Generate all prompts")
    p.add_argument("--save-prompt", action="store_true", help="Save prompt to file")
    p.add_argument("--result", type=str, help="Validate LLM result JSON")
    args = p.parse_args()

    stock_dir = find_stock_dir(args.code)
    if not stock_dir:
        print(f"ERROR: output dir not found for {args.code}", file=sys.stderr)
        return 1

    extractors = list(SCHEMAS.keys()) if args.all else [args.extractor]

    for ext_name in extractors:
        if not ext_name: continue

        if args.result:
            # Validation mode
            with open(args.result) as f:
                result = json.load(f)
            valid, errors = validate_result(ext_name, result)
            if valid:
                # Save to stock dir
                out_path = os.path.join(stock_dir, f"{ext_name}.json")
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"✅ {ext_name}.json validated and saved")
            else:
                print(f"❌ {ext_name} validation errors: {errors}")
        else:
            # Prompt generation mode
            prompt, err = generate_prompt(args.code, ext_name)
            if err:
                print(f"ERROR {ext_name}: {err}")
                continue

            if args.save_prompt:
                prompt_path = os.path.join(stock_dir, f"zone_b_prompt_{ext_name}.txt")
                with open(prompt_path, "w") as f:
                    f.write(prompt)
                print(f"✅ Prompt saved: {prompt_path}")
            else:
                print(f"=== PROMPT for {ext_name} ===\n{prompt}\n")

    return 0

if __name__ == "__main__":
    sys.exit(main())
