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

import argparse, json, os, re, sys

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
    # V12.6 新增: 员工与薪酬
    "employee_benefit_expense_m": "number|null — 员工成本/薪酬总额(百万元), 搜索'员工成本''雇员福利''staff cost'",
    "labor_by_function": "object|null — 职工薪酬按职能拆分。{production: 生产/运营/服务人员薪酬(百万元), sales: 销售人员薪酬(百万元), admin: 管理/行政人员薪酬(百万元), rd: 研发人员薪酬(百万元), total: 合计(百万元), quote: 原文完整句子或表头行, note_basis: 一句话说明取自哪张附注表, source_pages: [页码整数, ...]}。搜索'职工薪酬''按职能分类''生产人员''销售人员''管理人员''行政人员''研发费用''staff cost by function''employee benefit expense by function'，以及利润表附注里“员工成本/僱員福利開支 — 计入销售及服务成本/服务成本/直接运营开支/行政开支”这类按费用归属披露。若年报仅披露销售/管理/研发人工，也照实填入；production 缺失可填 null。若完全无拆分，填null。",
    "sbc_expense_m": "number|null — 股权激励费用(百万元), 搜索'share option''RSU''share award''购股权''以股份为基础'",
    # V12.6 新增: 资本化利息
    "capitalized_interest_m": "number|null — 资本化利息(百万元), 搜索'capitalized''capitalised''资本化''借款费用资本化金额'",
    # V12.6 新增: 受限现金
    "restricted_cash_breakdown": [{
        "type": "string (定期存款/质押存款/受限存款/保证金/其他)",
        "amount_m": "number|null",
        "maturity": "string (1年内/1年以上/无固定期限)",
        "quote": "string"
    }],
    # V12.6 新增: 存放集团财务公司
    "cash_in_group_finance_m": "number|null — 存放集团财务公司款项(百万元), 搜索'财务公司''集团资金''资金池''treasury center'",
    # V12.9 新增: Spec Step2 AR核查 + Step5 X2研发资本化 + Step6 资本承诺
    "ar_provision_policy": "string|null — 应收账款坏账准备计提政策(ECL模型/账龄法/个别计提), 搜索'坏账准备''provision policy''expected credit loss''ECL'",
    "rd_capitalized_m": "number|null — 研发费用资本化金额(百万元), 搜索'研发资本化''capitalised development''development costs capitalised''资本化研发'",
    "capital_commitments_m": "number|null — 资本承诺金额(百万元), 搜索'资本承诺''capital commitments''contracted but not provided''已签约但未拨备'",
    # V12.11 新增: 准则差异 + 现金上游障碍 + 分红政策
    "accounting_standards_notes": "string|null — 会计准则差异说明(CAS vs HKFRS: 收入确认激进性/ECL充足性/HKFRS16表外负债/VIE合并范围), 搜索'HKFRS''CAS''会计准则''basis of preparation''编制基础'",
    "parent_vs_consolidated_cash": "object|null — {parent_cash_m: 母公司层面现金(百万元), consolidated_cash_m: 合并层面现金(百万元), upstream_barrier_pct: (合并-母公司)/合并×100}。港股年报通常在附注中披露母公司报表。搜索'母公司''parent company''公司层面''company level'。若无母公司报表则填null",
    "dividend_policy_stated": "string|null — 公司明确披露的分红政策原文(如'派息率不低于30%'或'维持稳定增长的派息政策'), 搜索'dividend policy''股息政策''分红政策''派息政策''payout policy'。若无明确政策声明则填null",
    # V12.15 新增: 少数股东治理张力提取
    "minority_shareholder_structure": "object|null — 少数股东结构。{minority_name: 少数股东名称, stake_pct: 持股比例%, board_seats: 董事会席位数量, dual_role: 双重身份描述(如'浓缩液供应商'/'技术授权方'/'控股股东关联方'/null)}。搜索年报'股东''shareholder''主要股东''substantial shareholder''股本''share capital'章节。若无显著少数股东则填null",
    "dual_role_shareholders": ["object|null — 具有双重身份的股东。{name: 股东名称, role1: 第一身份(如'35%少数股东'), role2: 第二身份(如'浓缩液供应商'/'关联方客户'), conflict_description: 潜在利益冲突描述(如'浓缩液定价越高→供应商利润越大→装瓶商利润越小→少数股东分红与浓缩液收入存在此消彼长'), related_party_amount_m: 关联交易金额(百万元, 如浓缩液采购金额)}。搜索关联交易章节+'connected transaction''continuing connected transaction''关联交易''持续关联交易'"],
    "dividend_decision_history": "object|null — 分红决策历史。{policy_changes: [{year: 年份, change: 变化描述, reason: 原因, quote: 原文引用}], minority_approval_required: 少数股东是否可以否决分红方案(true/false/null), voting_threshold: 表决权门槛描述(如'重大事项需>2/3表决权')}。搜索年报'股息''dividend''分红''利润分配'' appropriation'及关联交易章节中的分红相关条款",
    "governance_tension_indicators": ["string — 治理张力信号。从年报中提取可能暗示控股vs少数股东利益不一致的信号。示例:'派息率连续5年未变，尽管自由现金流充裕''控股股东关联交易占比>10%''少数股东同时是关键供应商''年报未披露分红政策决策机制''独立董事从未在关联交易投票中反对'"],
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
        "risk_evolution": "string (风险如何演变)",
        "restricted_cash_summary": "V12.6: 受限现金汇总(定期存款/质押/保证金)"
    },
    "governance.json": {
        "related_party_transactions": "5年关联交易去重列表",
        "governance_timeline": "管理层/董事会/审计师变动时间线",
        "transparency_assessment": "string (关联交易透明度评估)",
        "employee_benefit_trend": "V12.6: 多年员工成本趋势",
        "related_party_deposits": "V12.6: 存放集团财务公司款项",
        "minority_shareholder_structure": "V12.15: 少数股东结构(身份/持股/董事会席位/双重身份)",
        "dual_role_shareholders": "V12.15: 双重身份股东识别+利益冲突描述+关联交易金额",
        "dividend_decision_history": "V12.15: 分红政策变化历史+少数股东否决权限",
        "governance_tension_indicators": "V12.15: 控股vs少数股东利益不一致信号",
        "parent_cash_upstream_barrier": "V12.11: 归母vs合并层面现金差额",
        "dividend_policy_stated": "V12.11: 公司披露的分红政策原文",
        "total_related_party_revenue_m": "关联交易总收入金额(百万元)",
        "related_party_revenue_pct": "关联交易收入占总收入比例(%)"
    },
    "audit.json": {
        "auditor_history": "5年审计师列表",
        "audit_opinion_history": "5年审计意见列表",
        "key_audit_matters": "5年KAM去重列表",
        "non_recurring_summary": "5年非经常项目汇总+分类(保留/扣除)",
        "accounting_policy_changes": "会计政策变更时间线",
        "sbc_summary": "V12.6: 多年SBC/股权激励费用汇总",
        "capitalized_interest_summary": "V12.6: 多年资本化利息汇总"
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
    # Build context: prioritize audit-critical sections (STMT has auditor report)
    # Reorder: MDA → STMT → SEG → GOV → RISK → others → then truncate
    priority_order = ["MDA", "STMT", "SEG", "GOV", "AUDIT", "P3", "P4", "P6", "P2", "P13", "DAN", "SUB"]
    ordered_sections = [(k, sections[k]) for k in priority_order if k in sections]
    # Also include any remaining sections not in priority list
    for k, v in sections.items():
        if k not in priority_order:
            ordered_sections.append((k, v))

    context_parts = []
    for sec_name, sec_content in ordered_sections:
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

    # 从 DB 获取定量数据上下文（不需要 LLM 从 PDF 重新提取数字）
    db_fin = full_text.get("_db_financials", {})
    db_row = db_fin.get(year, {})
    db_context = ""
    if db_row:
        items = []
        for k, v in db_row.items():
            if v is not None and k in ("revenue", "n_income_attr_p", "n_cashflow_act",
                                        "total_assets", "total_liab", "total_hldr_eqy_exc_min_int",
                                        "gross_margin", "d_a", "dividends_paid", "eps", "dps", "goodwill"):
                if isinstance(v, float):
                    items.append(f"  {k}: {v:,.2f}")
                else:
                    items.append(f"  {k}: {v}")
        if items:
            db_context = f"""
【定量数据 — stock_analysis.db (已校验,无需从PDF提取)】
{chr(10).join(items)}
"""

    prompt = f"""你是数据提取器。从以下港股公司 FY{year} 年报全文中提取结构化数据。
{db_context}
【年报全文 — FY{year}】
{context}"""

    # 后续规则接在 prompt 后面
    prompt += f"""

【提取Schema — 请输出以下JSON】
{json.dumps(YEAR_SCHEMA, indent=2, ensure_ascii=False)}

【强制规则】
1. 每个数字字段必须附带 "quote": "原文中包含该数字的完整句子"。无quote的字段填null。
2. 只提取FY{year}的数据。若原文同时提到去年和今年，只取今年。
3. 在所有section中搜索。年报章节标签可能不准，内容可能跨节。
4. 优先从 score>=8 的段落中提取，但不要遗漏低分段落中的重要数据。
5. 缺失字段填null，不编造，不推断。
6. _extracted数组: 选取10-15段最有价值的原文(score>=7优先)，完整verbatim，不截断。
7. 金额统一为百万元RMB（原文用千元->除以1000；原文用亿元->乘以100）。
8. **定量数据（营收/NP/OCF等）已在上方【定量数据】中提供，来自数据库。你只需专注提取定性洞察：管理层叙事、战略变化、风险描述、分部经营分析、审计意见。不要重复提取已有数字。**
9. **audit_info 必须在 STMT 章节中查找**：审计师名称和签字会计师在 INDEPENDENT AUDITOR'S REPORT 末尾（通常在 "Certified Public Accountants" 或 "執業會計師" 后面）。审计意见类型在报告开头（"in our opinion...give a true and fair view"=无保留意见）。务必提取！
10. **related_party_transactions 必须在 P4 章节中查找**：关联方交易通常标注为 "RELATED PARTY TRANSACTIONS" 或 "關聯方交易"（附注编号通常为 34-36）。提取关联方名称（如中粮集团/COFCO/Coca-Cola）、交易类型、金额、定价基准。
11. **goodwill 数据在 STMT 和 P6 章节**：商誉减值评估通常是 Key Audit Matter（关键审计事项），在 INDEPENDENT AUDITOR'S REPORT 中有详细描述。goodwill_balance_m 和 goodwill_impairment_m 从这里提取。
12. **non_recurring_items 在 STMT 和 MDA 章节**：非经常性损益包括政府补助、资产处置收益、重组费用等。搜索 "exceptional" "non-recurring" "一次性" "政府补助" 等关键词。
13. **contingent_liabilities 在 P6 章节**：或有负债通常标注为 "CONTINGENT LIABILITIES" 或 "或有負債"（附注编号通常为 35-38）。
14. **ar_aging 和 ar_total_m**：港股年报通常不披露应收账款账龄明细表。若各章节均未找到，直接填 null，不要编造。
15. **forward_guidance 在 MDA 章节末尾**：搜索 "展望" "outlook" "预计" "expect" "guidance" "策略" "计划" "来年" "明年"。提取管理层对未来一年的具体指引（收入目标、利润预期、资本开支计划）。
16. **segment_data 在 SEG 章节**：每个品类提取 name（产品/业务线名称）、revenue_m（如有）、revenue_yoy_pct（如有）。保留 quote 原文引用。港股通常不披露分部绝对收入，此时只填 name 和定性描述。
17. **key_operations_metrics 在 MDA 财务摘要部分**：提取 EBITDA、经营利润率、ROE、净负债率等关键运营指标。从 MDA 开头的财务摘要表或 "Financial Highlights" 部分提取。
18. **governance_events 在 MDA 章节**：搜索管理层变动（"董事" "director" "appointment" "resignation" "委任" "辞任"）、董事会变动、股权激励（"share option" "购股权" "RSU"）、股份回购（"share buyback" "回购"）。港股年报通常无独立公司治理章节，信息散落在 MDA 和董事会报告中。
19. **employee_benefit_expense_m 在损益表附注中**：搜索"员工成本""雇员福利""staff cost""employee benefit expense""僱員福利"。取 FY{year} 总额（百万元）。港股通常在附注8-10披露。
20. **labor_by_function 在职工薪酬附注表中**：搜索"按职能分类""生产人员""销售人员""管理人员""行政人员""研发费用""staff cost by function""employee benefit expense by function""僱員福利開支按職能分類"。另一个常见港股模式是利润表附注直接写“员工成本/僱員福利開支 — 计入销售及服务成本 / 服务成本 / 直接运营开支 / 行政开支”，此时可将“销售及服务成本/服务成本/直接运营开支”映射为 production，“行政开支/销管费用”映射为 admin。若找到表格或费用附注，提取 production / sales / admin / rd / total 五个数字（百万元）。production 可对应生产/运营/服务/项目执行人员；admin 可对应管理/行政/总部人员；rd 对应研发费用中的职工薪酬。若年报只披露销售/管理/研发人工，也照实填入，production 可为 null。务必保留 quote 原文，并在 note_basis 说明口径。若完全无拆分，填 null，不要猜。
21. **sbc_expense_m 在损益表附注/股份支付附注中**：搜索"以股份为基础""share-based""equity-settled""股份支付""购股权""share award""RSU"。港股附注通常在员工成本明细或独立股份支付附注。提取当期确认为费用的金额（非授予金额）。若无单独披露则填 null。
22. **capitalized_interest_m 在借款费用附注中**：搜索"资本化""capitalised""capitalized""借款费用资本化金额""borrowing costs capitalised"。港股附注通常在借款/融资成本部分。提取当期资本化利息金额。若无披露则填 null。
23. **restricted_cash_breakdown 在货币资金附注中**：搜索"抵押""质押""受限""restricted""pledged""所有权受限"。港股附注通常在现金及现金等价物明细中。区分定期存款(有到期日但未必有法律限制)和质押存款(有法律质押/抵押)。若无明细则填空数组[]。
24. **cash_in_group_finance_m 在关联交易/其他应收款附注中**：搜索"财务公司""集团资金""资金池""财务有限公司""treasury""cash pool""group finance"。若关联交易附注(P4)或其他应收款附注中披露存放于集团财务公司的款项，提取金额。若无则填 null。
25. **ar_provision_policy 在应收账款附注中**：搜索"坏账准备""provision policy""expected credit loss""ECL""计提政策""损失准备"。提取计提方法描述（如"预期信用损失模型按账龄分组计提"）和关键参数（如账龄分组比例）。港股附注通常在 AR/金融工具部分。若无明确描述则填 null。
26. **rd_capitalized_m 在无形资产/研发附注中**：搜索"研发资本化""capitalised development""development costs capitalised""资本化研发支出""资本化开发"。港股附注通常在无形资产/开发成本部分。提取当期资本化金额（百万元）。若无披露则填 null。
27. **capital_commitments_m 在承诺事项附注中**：搜索"资本承诺""capital commitments""contracted but not provided""已签约但未拨备""已订约但未拨备"。港股附注通常在"Commitments"或"承担"部分（附注编号通常为 32-35）。提取已签约但尚未拨备的资本支出金额（百万元）。若无则填 null。
28. **accounting_standards_notes 在编制基础附注中**：搜索"HKFRS""CAS""会计准则""accounting standards""basis of preparation""编制基础"。提取关于会计准则的关键说明，尤其关注：收入确认政策是否激进、ECL模型充足性、HKFRS16租赁负债表外风险、VIE/SPV合并范围。港股附注通常在附注1-3（主要会计政策）。若无关键差异则填"无重大准则差异"。
29. **parent_vs_consolidated_cash 在母公司财务报表附注中**：港股年报通常附有母公司层面资产负债表。搜索"母公司""parent company""公司层面""company level""statement of financial position of the company"。提取母公司货币资金 vs 合并货币资金。计算upstream_barrier_pct = (合并-母公司)/合并×100（即有多少现金不在上市主体而在子公司/关联方）。若无母公司报表则填null。
30. **dividend_policy_stated 在董事会报告/MDA中**：搜索"dividend policy""股息政策""分红政策""派息政策""派息率""payout ratio""dividend payout"。若公司有明确的分红承诺或政策声明（如"每年派息率不低于可供分配利润的30%"），提取原文。注意区分"历史分红记录"和"未来分红政策承诺"——只有后者才应提取。若无明确政策承诺则填null。

输出纯JSON，不含markdown fence。"""
    return prompt


def _clean_garbled_items(items: list, min_len: int = 5) -> list:
    """过滤列表中的乱码项：过短字符串、纯空白、纯emoji、纯标点。"""
    if not items:
        return []
    cleaned = []
    for item in items:
        if not isinstance(item, str):
            cleaned.append(item)
            continue
        s = item.strip()
        if len(s) < min_len:
            continue
        # 必须有实质内容（中英文字母数字）
        has_content = any(
            c.isalpha() or c.isdigit() or ('一' <= c <= '鿿')
            for c in s
        )
        if not has_content:
            continue
        # 不能是纯数字/符号
        text_chars = sum(1 for c in s if c.isalpha() or '一' <= c <= '鿿')
        if text_chars < 3:
            continue
        cleaned.append(item)
    return cleaned


def _validate_zone_b(data: dict, zone_name: str, partials: dict = None) -> dict:
    """校验并清理 Zone B JSON，用 partial 数据补充缺口。"""
    if not isinstance(data, dict):
        return {}

    # 1) 清理 year_highlights 中的乱码
    for key in list(data.keys()):
        if key.endswith("_highlights") and isinstance(data[key], dict):
            for yr in list(data[key].keys()):
                hl = data[key][yr]
                if isinstance(hl, list):
                    data[key][yr] = _clean_garbled_items(hl)
                    if not data[key][yr]:
                        del data[key][yr]  # 全乱码 → 删除该年
        # 清理列表中的乱码字符串
        elif isinstance(data[key], list):
            if all(isinstance(x, str) for x in data[key]):
                data[key] = _clean_garbled_items(data[key])

    # 2) 用 partial 数据补全缺失年份
    if partials and zone_name == "mda.json":
        for yr, partial in partials.items():
            if yr not in data.get("year_highlights", {}):
                yr_hl = partial.get("revenue_highlights", [])
                yr_mgmt = partial.get("mgmt_explanations", [])
                highlights = []
                for h in yr_hl[:4]:
                    if isinstance(h, dict):
                        highlights.append(h.get("item", str(h)))
                    else:
                        highlights.append(str(h))
                if highlights:
                    data.setdefault("year_highlights", {})[yr] = highlights
                if yr_mgmt and yr not in data.get("mgmt_explanations", {}):
                    data.setdefault("mgmt_explanations", {})[yr] = [
                        m.get("explanation", str(m)) if isinstance(m, dict) else str(m)
                        for m in yr_mgmt[:3]
                    ]

    # 3) 若 master 未输出 mda_key_financials，标记为从 DB 获取
    if zone_name == "mda.json" and not data.get("mda_key_financials"):
        data["mda_key_financials"] = {"_source": "stock_analysis.db (定量数据请从 compute_bundle.json 获取)"}

    # 4) audit.json & governance.json 直接从 partials 补全（master 常遗漏）
    if partials:
        if zone_name == "audit.json":
            auditors, opinions, kams = [], [], []
            for yr in sorted(partials.keys()):
                ai = partials[yr].get("audit_info") or {}
                auditor = ai.get("auditor")
                if auditor and "⚠️" not in str(auditor):
                    auditors.append(f"FY{yr}: {auditor}")
                opinion = ai.get("opinion", ai.get("audit_opinion"))
                if opinion and "⚠️" not in str(opinion):
                    opinions.append(f"FY{yr}: {opinion}")
                kam_list = ai.get("key_audit_matters") or []
                for k in kam_list:
                    if k not in kams:
                        kams.append(k)
            if auditors and ("⚠️" in str(data.get("auditor_history", "")) or not data.get("auditor_history")):
                data["auditor_history"] = auditors
            if opinions and ("⚠️" in str(data.get("audit_opinion_history", "")) or not data.get("audit_opinion_history")):
                data["audit_opinion_history"] = opinions
            if kams and ("⚠️" in str(data.get("key_audit_matters", "")) or not data.get("key_audit_matters")):
                data["key_audit_matters"] = kams

        if zone_name == "governance.json":
            all_rpt = []
            for yr in sorted(partials.keys()):
                rpt_list = partials[yr].get("related_party_transactions") or []
                for r in rpt_list[:3]:
                    if isinstance(r, dict):
                        r["year"] = yr
                    all_rpt.append(r)
            if all_rpt and ("⚠️" in str(data.get("related_party_transactions", "")) or not data.get("related_party_transactions")):
                data["related_party_transactions"] = all_rpt

    if partials and zone_name == "segments.json":
        for yr, partial in partials.items():
            if yr not in data.get("segments", {}):
                seg_data = partial.get("segment_data", [])
                if seg_data:
                    data.setdefault("segments", {})[yr] = seg_data

    return data


def _copy_quotes_from_partials(data: dict, zone_name: str, partials: dict) -> dict:
    """从 partials 补回 quote 字段到 master 输出中的对应条目。

    master 汇总时丢失了原文引用——此函数按年份+名称匹配，把 partial 里的 quote 复制回来。
    """
    if not partials:
        return data

    if zone_name == "segments.json":
        master_segments = data.get("segments", {})
        for yr, partial in partials.items():
            partial_segs = partial.get("segment_data", [])
            if not partial_segs:
                continue
            master_yr_segs = master_segments.get(yr, [])
            if not master_yr_segs:
                continue
            # 按名称匹配
            partial_by_name = {}
            for s in partial_segs:
                if isinstance(s, dict) and s.get("name"):
                    partial_by_name[s["name"].lower()] = s
            for ms in master_yr_segs:
                if not isinstance(ms, dict):
                    continue
                name = ms.get("name", "").lower()
                # 模糊匹配：包含关系
                best_match = None
                for pname, ps in partial_by_name.items():
                    if name in pname or pname in name:
                        best_match = ps
                        break
                if not best_match and partial_by_name:
                    # 取第一个有 quote 的
                    for ps in partial_by_name.values():
                        if ps.get("quote"):
                            best_match = ps
                            break
                if best_match:
                    # 补 quote
                    if not ms.get("quote") and best_match.get("quote"):
                        ms["quote"] = best_match["quote"]
                    # 补数字（如果有）
                    for f in ["revenue_m", "revenue_pct", "revenue_yoy_pct", "gross_margin_pct"]:
                        if ms.get(f) is None and best_match.get(f) is not None:
                            ms[f] = best_match[f]

    if zone_name == "mda.json":
        master_hl = data.get("year_highlights", {})
        for yr, partial in partials.items():
            if yr not in master_hl:
                continue
            partial_hl = partial.get("revenue_highlights", [])
            # 把 partial 的 quote 挂到最匹配的 highlight 上
            for i, hl in enumerate(master_hl[yr]):
                if isinstance(hl, dict) and hl.get("quote"):
                    continue  # 已有 quote，跳过
                # 找 partial 中最匹配的 item
                hl_text = hl.get("item", hl) if isinstance(hl, dict) else hl
                for ph in partial_hl:
                    if isinstance(ph, dict) and ph.get("quote"):
                        # 简单匹配：quote 和 highlight 共享关键词
                        if any(w in (ph.get("item", "") + ph.get("quote", ""))
                               for w in hl_text[:10].split() if len(w) >= 2):
                            if isinstance(master_hl[yr][i], dict):
                                master_hl[yr][i]["quote"] = ph["quote"]
                            break

    return data


def aggregate_partials_to_zone_b(partials: dict, stock_dir: str = "", db_fin: dict = None) -> dict:
    """V8.3: 纯 Python 聚合 5 年 partial JSON → 5 个 Zone B 文件。

    替代 LLM master 汇总——结构化数据合并用代码零信息丢失。
    仅在 trend_analysis 保留 1 次 LLM 调用（跨年趋势判断）。
    """
    if db_fin is None:
        db_fin = {}
        ft_path = os.path.join(stock_dir, "pdf_full_text.json")
        if os.path.exists(ft_path):
            with open(ft_path) as f:
                db_fin = json.load(f).get("_db_financials", {})

    years = sorted(partials.keys())
    output = {}

    # ── mda.json ──
    mda = {"year_highlights": {}, "mgmt_explanations": {}, "forward_guidance": [],
           "strategy_changes": [], "key_operations_metrics": [], "mda_key_financials": {},
           "trend_analysis": {}}
    for yr in years:
        p = partials[yr]
        # highlights: 从多个字段构建完整叙事句
        hl_items = []
        # 1) revenue_highlights: 标签 + 数值 + 变化
        for h in (p.get("revenue_highlights") or [])[:5]:
            if isinstance(h, dict):
                item = h.get("item", "") or ""
                amt = h.get("amount_m")
                pct = h.get("change_pct")
                parts = [item.strip()] if item.strip() else []
                if amt is not None:
                    parts.append(f"{amt:,.0f}M" if isinstance(amt, (int, float)) else str(amt))
                if pct is not None:
                    sign = "+" if (isinstance(pct, (int, float)) and pct > 0) else ""
                    parts.append(f"({sign}{pct}%)" if isinstance(pct, (int, float)) else f"({pct})")
                sentence = " ".join(parts)
            else:
                sentence = str(h)
            if sentence.strip() and len(sentence.strip()) >= 8:
                hl_items.append(sentence)
        # 2) 从 mgmt_explanations 补充（管理层解释常含核心叙事）
        for m in (p.get("mgmt_explanations") or []):
            if len(hl_items) >= 5:
                break
            exp = m.get("explanation", "") if isinstance(m, dict) else str(m)
            if exp.strip() and len(exp.strip()) >= 15 and exp.strip() not in " ".join(hl_items):
                hl_items.append(exp.strip()[:200])
        # 3) 从 key_operations_metrics 补充（关键运营指标）
        for m in (p.get("key_operations_metrics") or []):
            if len(hl_items) >= 5:
                break
            if isinstance(m, dict):
                name = m.get("name", m.get("metric", ""))
                val = m.get("value")
                yoy = m.get("yoy_change_pct")
                parts = [name.strip()] if name.strip() else []
                if val is not None:
                    parts.append(f"{val:,.1f}" if isinstance(val, float) else str(val))
                if yoy is not None:
                    sign = "+" if (isinstance(yoy, (int, float)) and yoy > 0) else ""
                    parts.append(f"({sign}{yoy}%)" if isinstance(yoy, (int, float)) else f"({yoy})")
                sentence = " ".join(parts)
                if sentence.strip() and len(sentence.strip()) >= 8:
                    hl_items.append(sentence)
        # 4) 过滤纯标签（没有数字且 < 20 字符的短句）
        hl_items = [h for h in hl_items
                    if any(c.isdigit() for c in h) or len(h) >= 20]
        if hl_items:
            mda["year_highlights"][yr] = hl_items
        # mgmt_explanations
        mgmt = []
        for m in (p.get("mgmt_explanations") or [])[:4]:
            if isinstance(m, dict):
                exp = {"topic": m.get("topic", ""), "explanation": m.get("explanation", ""),
                       "quote": m.get("quote", "")}
            else:
                exp = {"explanation": str(m)}
            if exp.get("explanation", "").strip():
                mgmt.append(exp)
        if mgmt:
            mda["mgmt_explanations"][yr] = mgmt
        # forward_guidance: 合并
        for g in (p.get("forward_guidance") or []):
            if isinstance(g, dict):
                g["year"] = yr
                mda["forward_guidance"].append(g)
            elif isinstance(g, str) and g.strip():
                mda["forward_guidance"].append({"year": yr, "guidance": g})
        # strategy_changes: 合并
        for s in (p.get("strategy_changes") or []):
            if isinstance(s, dict):
                s["year"] = yr
                mda["strategy_changes"].append(s)
            elif isinstance(s, str) and s.strip():
                mda["strategy_changes"].append({"year": yr, "detail": s})
        # key_operations_metrics: 合并
        for m in (p.get("key_operations_metrics") or []):
            if isinstance(m, dict):
                m["year"] = yr
                mda["key_operations_metrics"].append(m)
    # mda_key_financials: 从 DB 构建 5 年汇总表
    if db_fin:
        mda["mda_key_financials"] = {"_source": "stock_analysis.db", "years": {}}
        for yr in years:
            row = db_fin.get(yr, {})
            if row:
                mda["mda_key_financials"]["years"][yr] = {
                    "revenue": row.get("revenue"), "n_income_attr_p": row.get("n_income_attr_p"),
                    "n_cashflow_act": row.get("n_cashflow_act"),
                    "total_assets": row.get("total_assets"),
                    "total_hldr_eqy_exc_min_int": row.get("total_hldr_eqy_exc_min_int"),
                    "gross_margin": row.get("gross_margin"), "dps": row.get("dps"),
                }
    # trend_analysis: 从 DB + highlights 自动生成（纯 Python，无需 LLM）
    ta = {}
    # 毛利率趋势
    gm_vals = {yr: db_fin.get(yr, {}).get("gross_margin") for yr in years if db_fin.get(yr, {}).get("gross_margin") is not None}
    if len(gm_vals) >= 2:
        yrs_sorted = sorted(gm_vals.keys())
        ta["gross_margin_trend"] = " → ".join(f"FY{y}: {gm_vals[y]:.1f}%" for y in yrs_sorted[-5:])
    # 营收增长质量
    rev_vals = {yr: db_fin.get(yr, {}).get("revenue") for yr in years if db_fin.get(yr, {}).get("revenue") is not None}
    np_vals = {yr: db_fin.get(yr, {}).get("n_income_attr_p") for yr in years if db_fin.get(yr, {}).get("n_income_attr_p") is not None}
    if len(rev_vals) >= 2:
        rev_growth = [(int(y), (rev_vals[y] - rev_vals.get(str(int(y)-1), rev_vals[y])) / max(rev_vals.get(str(int(y)-1), 1), 1) * 100)
                      for y in sorted(rev_vals.keys())[-4:]]
        ta["revenue_growth_quality"] = " | ".join(f"FY{y}: {g:+.1f}%" for y, g in rev_growth)
    # 管理层战略演变
    all_strategies = [s.get("detail", s.get("item", str(s))) if isinstance(s, dict) else str(s)
                      for s in mda.get("strategy_changes", [])[:8]]
    if all_strategies:
        ta["strategic_execution"] = "; ".join(all_strategies[:5])
    if ta:
        mda["trend_analysis"] = ta

    output["mda.json"] = mda

    # ── segments.json ──
    seg = {"segments": {}, "revenue_structure_evolution": "", "margin_by_segment_trend": ""}
    all_seg_names = set()
    for yr in years:
        seg_data = partials[yr].get("segment_data") or []
        seg_items = []
        for s in seg_data:
            if isinstance(s, dict):
                item = {"name": s.get("name", ""), "revenue_m": s.get("revenue_m"),
                        "revenue_pct": s.get("revenue_pct"), "revenue_yoy_pct": s.get("revenue_yoy_pct"),
                        "gross_margin_pct": s.get("gross_margin_pct"), "quote": s.get("quote", ""),
                        "highlight": s.get("highlight", s.get("description", ""))}
            else:
                item = {"name": str(s)}
            if item.get("name", "").strip():
                seg_items.append(item)
                all_seg_names.add(item["name"])
        if seg_items:
            seg["segments"][yr] = seg_items
    # revenue_structure_evolution: 从分部名称 + DB 推断（去重）
    if all_seg_names:
        # 标准化去重：英文名和中文名可能重复
        unique_names = []
        seen_lower = set()
        for n in sorted(all_seg_names):
            nl = n.lower().strip()
            # 跳过太泛的名称
            if nl in ("其他", "others", "other", "其他饮料", "other beverages"):
                continue
            if nl not in seen_lower:
                seen_lower.add(nl)
                unique_names.append(n)
        # 检测"单一经营分部"——LLM 未能拆分品类的信号
        if len(unique_names) <= 2 and any("单一" in n or "single" in n.lower() for n in unique_names):
            seg["revenue_structure_evolution"] = "⚠️ 年度 LLM 未能拆分品类（仅提取到单一经营分部）。请用 read_section 从 SEG 章节手工提取。"
        else:
            seg["revenue_structure_evolution"] = f"披露{len(unique_names)}个品类: {', '.join(unique_names[:10])}。港股未披露分部收入绝对数，仅披露相对变化方向。"
    # margin_by_segment_trend: 从 DB 综合毛利率 + 分部定性描述推断
    gm_vals = {yr: db_fin.get(yr, {}).get("gross_margin") for yr in years
               if db_fin.get(yr, {}).get("gross_margin") is not None}
    if len(gm_vals) >= 2:
        seg["margin_by_segment_trend"] = "综合毛利率趋势: " + " → ".join(
            f"FY{y}: {gm_vals[y]:.1f}%" for y in sorted(gm_vals.keys())[-5:]
        ) + "。分部毛利率未经单独披露。"
    output["segments.json"] = seg

    # ── risks.json ──
    risks = {"principal_risks": [], "risk_evolution": "", "goodwill_trend": "",
             "contingent_liabilities": [], "ar_aging": "", "restricted_cash_summary": ""}  # V12.6
    # ar_aging: 先检查 partial 是否有数据
    ar_data = []
    for yr in years:
        p_ar = partials[yr].get("ar_aging")
        if p_ar and isinstance(p_ar, list) and len(p_ar) > 0:
            ar_data.append((yr, p_ar))
    if ar_data:
        risks["ar_aging"] = json.dumps({yr: data for yr, data in ar_data}, ensure_ascii=False)
    else:
        risks["ar_aging"] = "港股年报未披露应收账款账龄明细表"
    seen_risks = set()
    for yr in years:
        p = partials[yr]
        for r in (p.get("risk_items") or []):
            if isinstance(r, dict):
                desc = r.get("description", str(r))
                if desc and desc not in seen_risks:
                    seen_risks.add(desc)
                    risks["principal_risks"].append({"year": yr, "description": desc,
                        "category": r.get("category", ""), "severity": r.get("severity", ""),
                        "mitigation": r.get("mitigation", ""), "quote": r.get("quote", "")})
        for cl in (p.get("contingent_liabilities") or []):
            if isinstance(cl, dict):
                cl["year"] = yr
                risks["contingent_liabilities"].append(cl)
    # goodwill_trend
    gw_vals = {}
    for yr in years:
        p = partials[yr]
        bal = p.get("goodwill_balance_m")
        imp = p.get("goodwill_impairment_m")
        if bal is not None or imp is not None:
            gw_vals[yr] = f"余额={bal}M, 减值={imp}M" if imp else f"余额={bal}M"
    if gw_vals:
        risks["goodwill_trend"] = " → ".join(f"FY{y}: {v}" for y, v in sorted(gw_vals.items()))
    else:
        risks["goodwill_trend"] = "⚠️ 无提取数据"
    # risk_evolution: 从 principal_risks 的年份序列自动生成
    if risks["principal_risks"]:
        risk_by_year = {}
        for r in risks["principal_risks"]:
            yr = r.get("year", "?")
            risk_by_year.setdefault(yr, []).append(r.get("description", "")[:80])
        risk_evolution_parts = []
        for yr in sorted(risk_by_year.keys()):
            risk_evolution_parts.append(f"FY{yr}: {', '.join(risk_by_year[yr][:3])}")
        risks["risk_evolution"] = " | ".join(risk_evolution_parts)
    else:
        risks["risk_evolution"] = "⚠️ 无提取数据"
    # V12.6: 受限现金汇总
    restricted_cash_parts = []
    for yr in years:
        p = partials[yr]
        for rc in (p.get("restricted_cash_breakdown") or []):
            if isinstance(rc, dict) and rc.get("amount_m"):
                restricted_cash_parts.append(
                    f"FY{yr}: {rc.get('type','?')} {rc['amount_m']}M ({rc.get('maturity','?')})"
                )
    risks["restricted_cash_summary"] = "; ".join(restricted_cash_parts) if restricted_cash_parts else "⚠️ 无受限现金提取数据"
    # V12.9: 资本承诺聚合
    cap_commit_parts = []
    for yr in years:
        p = partials[yr]
        cc = p.get("capital_commitments_m")
        if cc is not None and cc > 0:
            cap_commit_parts.append(f"FY{yr}: {cc}M")
    risks["capital_commitments_summary"] = "; ".join(cap_commit_parts) if cap_commit_parts else "⚠️ 无资本承诺提取数据"
    output["risks.json"] = risks

    # ── governance.json ──
    gov = {"related_party_transactions": [], "governance_timeline": "", "transparency_assessment": "",
           "employee_benefit_trend": "", "related_party_deposits": ""}  # V12.6 新增
    emp_years = []  # V12.6
    rp_deposit_years = []  # V12.6
    for yr in years:
        p = partials[yr]
        for rpt in (p.get("related_party_transactions") or []):
            if isinstance(rpt, dict):
                rpt["year"] = yr
                gov["related_party_transactions"].append(rpt)
        # V12.6: 员工成本 和 集团财务公司存款 聚合
        emp = p.get("employee_benefit_expense_m")
        if emp is not None and emp > 0:
            emp_years.append(f"FY{yr}: {emp}M")
        cgf = p.get("cash_in_group_finance_m")
        if cgf is not None and cgf > 0:
            rp_deposit_years.append(f"FY{yr}: {cgf}M")
        for ge in (p.get("governance_events") or []):
            if isinstance(ge, dict):
                ge["year"] = yr
    # governance_timeline: 从 governance_events + strategy_changes 拼接
    timeline_events = []
    for yr in years:
        p = partials[yr]
        for ge in (p.get("governance_events") or []):
            if isinstance(ge, dict) and ge.get("detail"):
                timeline_events.append(f"FY{yr}: {ge.get('detail','')[:120]}")
    if timeline_events:
        gov["governance_timeline"] = "; ".join(timeline_events[:10])
    else:
        gov["governance_timeline"] = "⚠️ 无提取数据（港股年报通常不设独立公司治理章节）"
    # V12.6: 员工成本趋势 和 关联方存款 汇总
    gov["employee_benefit_trend"] = "; ".join(emp_years) if emp_years else "⚠️ 无员工成本提取数据"
    gov["related_party_deposits"] = "; ".join(rp_deposit_years) if rp_deposit_years else (
        "未发现存放集团财务公司款项" if emp_years else "⚠️ 无提取数据")
    # V12.11: 现金上游障碍 + 分红政策 聚合
    parent_cash_parts = []
    div_policy_parts = []
    for yr in years:
        p = partials[yr]
        pc = p.get("parent_vs_consolidated_cash", {}) or {}
        if isinstance(pc, dict) and pc.get("upstream_barrier_pct") is not None:
            parent_cash_parts.append(f"FY{yr}: 上游障碍={pc['upstream_barrier_pct']}% (母公司{pc.get('parent_cash_m','?')}M / 合并{pc.get('consolidated_cash_m','?')}M)")
        dp = p.get("dividend_policy_stated", "")
        if dp and "⚠️" not in str(dp):
            div_policy_parts.append(f"FY{yr}: {str(dp)[:200]}")
    gov["parent_cash_upstream_barrier"] = "; ".join(parent_cash_parts) if parent_cash_parts else "⚠️ 无母公司现金提取数据（年报可能未附母公司报表）"
    gov["dividend_policy_stated"] = "; ".join(div_policy_parts[:1]) if div_policy_parts else "⚠️ 无明确分红政策声明（公司可能未公开承诺具体派息率）"
    output["governance.json"] = gov

    # ── audit.json ──
    audit = {"auditor_history": [], "audit_opinion_history": [], "key_audit_matters": [],
             "non_recurring_summary": "", "accounting_policy_changes": "",
             "sbc_summary": "", "capitalized_interest_summary": ""}  # V12.6 新增
    sbc_years = []  # V12.6
    capint_years = []  # V12.6
    audit_kams = set()
    for yr in years:
        p = partials[yr]
        ai = p.get("audit_info") or {}
        auditor = ai.get("auditor", "")
        if auditor and "⚠️" not in str(auditor) and "?" not in str(auditor):
            audit["auditor_history"].append(f"FY{yr}: {auditor}")
        opinion = ai.get("opinion", ai.get("audit_opinion", ""))
        if opinion and "⚠️" not in str(opinion):
            audit["audit_opinion_history"].append(f"FY{yr}: {opinion}")
        for kam in (ai.get("key_audit_matters") or []):
            if kam and kam not in audit_kams:
                audit_kams.add(kam)
                audit["key_audit_matters"].append(kam)
        for nr in (p.get("non_recurring_items") or []):
            if isinstance(nr, dict):
                nr["year"] = yr
        # V12.6: SBC 和 资本化利息 聚合
        sbc = p.get("sbc_expense_m")
        if sbc is not None and sbc > 0:
            sbc_years.append(f"FY{yr}: {sbc}M")
        capint = p.get("capitalized_interest_m")
        if capint is not None and capint > 0:
            capint_years.append(f"FY{yr}: {capint}M")
    if not audit["auditor_history"]:
        audit["auditor_history"] = ["⚠️ 无提取数据"]
    if not audit["audit_opinion_history"]:
        audit["audit_opinion_history"] = ["⚠️ 无提取数据"]
    # transparency_assessment: 基于关联交易和治理事件丰富度
    if not gov.get("transparency_assessment"):
        rpt_count = len(gov.get("related_party_transactions", []))
        timeline = gov.get("governance_timeline", "")
        if rpt_count == 0 and "⚠️" in timeline:
            gov["transparency_assessment"] = "⚠️ 关联交易和治理事件均无提取数据。港股年报通常不设独立公司治理章节，信息散落在董事会报告和 MDA 中。"
        elif rpt_count <= 1:
            gov["transparency_assessment"] = f"关联交易披露有限（{rpt_count}条）。港股年报的关联交易通常在 P4 章节（附注34-36），需从 PDF 直接阅读补充。"
        else:
            gov["transparency_assessment"] = f"关联交易{rpt_count}条已提取。治理事件时间线{len(timeline)}字符。"

    if not audit["key_audit_matters"]:
        audit["key_audit_matters"] = ["⚠️ 无提取数据"]
    if not audit["non_recurring_summary"]:
        audit["non_recurring_summary"] = "⚠️ 无提取数据"
    # accounting_policy_changes: 从 partials 聚合
    policy_changes = []
    for yr in years:
        p = partials[yr]
        ai = p.get("audit_info") or {}
        if isinstance(ai, dict):
            apc = ai.get("accounting_policy_changes", "")
            if apc and "⚠️" not in str(apc):
                policy_changes.append(f"FY{yr}: {apc}")
    if policy_changes:
        audit["accounting_policy_changes"] = "; ".join(policy_changes)
    elif not audit.get("accounting_policy_changes"):
        audit["accounting_policy_changes"] = "⚠️ 无提取数据"
    # V12.6: SBC 和 资本化利息 汇总
    audit["sbc_summary"] = "; ".join(sbc_years) if sbc_years else "⚠️ 无SBC提取数据"
    audit["capitalized_interest_summary"] = "; ".join(capint_years) if capint_years else "⚠️ 无资本化利息提取数据"
    # V12.9: AR计提政策 + 研发资本化 聚合
    ar_policy_parts = []
    rd_cap_parts = []
    for yr in years:
        p = partials[yr]
        ap = p.get("ar_provision_policy", "")
        if ap and "⚠️" not in str(ap):
            ar_policy_parts.append(f"FY{yr}: {str(ap)[:200]}")
        rd = p.get("rd_capitalized_m")
        if rd is not None and rd > 0:
            rd_cap_parts.append(f"FY{yr}: {rd}M")
    audit["ar_provision_policy"] = "; ".join(ar_policy_parts) if ar_policy_parts else "⚠️ 无计提政策提取数据"
    audit["rd_capitalized_summary"] = "; ".join(rd_cap_parts) if rd_cap_parts else "⚠️ 无研发资本化提取数据"
    # V12.11: 准则差异聚合
    acct_std_parts = []
    for yr in years:
        p = partials[yr]
        an = p.get("accounting_standards_notes", "")
        if an and "⚠️" not in str(an):
            acct_std_parts.append(f"FY{yr}: {str(an)[:200]}")
    audit["accounting_standards_notes"] = "; ".join(acct_std_parts) if acct_std_parts else "⚠️ 无准则差异提取数据"
    output["audit.json"] = audit

    return output


def _parse_million_amount(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = str(raw).replace(",", "").strip()
    if not cleaned:
        return None
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.replace("—", "").replace("-", "").strip()
    try:
        value = float(cleaned) / 1000.0
        return round(abs(value), 3)
    except ValueError:
        return None


def _parse_report_million_amount(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = str(raw).replace(",", "").strip()
    if not cleaned:
        return None
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.replace("—", "").replace("-", "").strip()
    try:
        return round(abs(float(cleaned)), 3)
    except ValueError:
        return None


def _load_report_md_text(stock_dir: str, year: str) -> str | None:
    path = os.path.join(stock_dir, f"{year}_年报.md")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _context_window(lines: list[str], markers: tuple[str, ...], width: int = 14) -> list[str]:
    for idx, line in enumerate(lines):
        if any(marker in line for marker in markers):
            return lines[idx: idx + width]
    return []


def _detect_local_amount_parser(lines: list[str], anchor_idx: int, lookback: int = 6):
    start = max(0, anchor_idx - lookback)
    end = min(len(lines), anchor_idx + 1)
    window = lines[start:end]
    for line in window:
        lowered = line.lower()
        if any(token in line for token in ("千元", "千港元", "人民幣千元", "人民币千元", "港幣千元", "港币千元")):
            return _parse_million_amount
        if "rmb’000" in lowered or "rmb'000" in lowered or "hk$'000" in lowered or "thousand" in lowered:
            return _parse_million_amount
        if any(token in line for token in ("百萬元", "百万元", "百萬港元", "百万港元", "人民幣百萬元", "人民币百万元")):
            return _parse_report_million_amount
        if "million" in lowered:
            return _parse_report_million_amount
    return _parse_million_amount


def _strip_year_comparison_parentheticals(text: str) -> str:
    """Remove parenthetical comparison periods like '(2024: ...)' while preserving other text."""
    result = []
    stack = []
    for ch in text:
        if ch == "(":
            stack.append([])
            continue
        if ch == ")":
            if not stack:
                result.append(ch)
                continue
            segment = "".join(stack.pop())
            if re.search(r"\b20\d{2}\s*:", segment):
                continue
            wrapped = f"({segment})"
            if stack:
                stack[-1].append(wrapped)
            else:
                result.append(wrapped)
            continue
        if stack:
            stack[-1].append(ch)
        else:
            result.append(ch)
    while stack:
        segment = "".join(stack.pop())
        if stack:
            stack[-1].append(f"({segment}")
        else:
            result.append(f"({segment}")
    return "".join(result)


def _extract_labor_by_function_from_report_md(stock_dir: str, year: str, partial: dict | None = None) -> dict | None:
    """Deterministic fallback for HK reports that disclose labor by expense destination."""
    text = _load_report_md_text(stock_dir, year)
    if not text:
        return None
    normalized_text = _strip_year_comparison_parentheticals(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    patterns = [
        r"total staff costs.*?RMB\s*([0-9,]+(?:\.\d+)?)\s*million.*?"
        r"of which,\s*RMB\s*([0-9,]+(?:\.\d+)?)\s*million(?:\s*\([^)]*\))?\s*"
        r"and\s*RMB\s*([0-9,]+(?:\.\d+)?)\s*million(?:\s*\([^)]*\))?\s*"
        r"(?:was|were)\s+(?:recognised|recognized)\s*"
        r"in direct operating expenses and selling and administrative expenses respectively",
        r"total staff costs.*?RMB\s*([0-9,]+(?:\.\d+)?)\s*million.*?"
        r"of which,\s*RMB\s*([0-9,]+(?:\.\d+)?)\s*million.*?"
        r"RMB\s*([0-9,]+(?:\.\d+)?)\s*million.*?"
        r"direct operating expenses and selling and administrative expenses respectively",
        r"(?:員工成本|员工成本)\s*[—\-]\s*包括(?:董事薪酬|董事酬金).*?"
        r"[—\-]\s*計入(?:銷售及服務成本|销售及服务成本|服務成本|服务成本|直接運營開支|直接运营开支)\s+([0-9,]+(?:\.\d+)?)"
        r".*?[—\-]\s*計入(?:行政開支|行政开支)\s+([0-9,]+(?:\.\d+)?)",
        r"(?:員工成本|员工成本)\s*[—\-]\s*包括(?:董事薪酬|董事酬金).*?"
        r"[—\-]\s*计入(?:销售及服务成本|服务成本|直接运营开支)\s+([0-9,]+(?:\.\d+)?)"
        r".*?[—\-]\s*计入(?:行政开支)\s+([0-9,]+(?:\.\d+)?)",
        r"員工成本（?包括.*?）?:\s*[\r\n]+(?:—|\-)\s*計入(?:銷售及服務成本|销售及服务成本|服務成本|服务成本|直接經營開支|直接经营开支)\s+([0-9,]+(?:\.\d+)?)"
        r"[\r\n]+(?:—|\-)\s*計入(?:行政開支|行政开支)\s+([0-9,]+(?:\.\d+)?)",
    ]

    match = None
    for pattern in patterns:
        match = re.search(pattern, normalized_text, flags=re.S)
        if match:
            break
    if not match:
        return _extract_labor_split_table_from_report_md(stock_dir, year)

    if len(match.groups()) >= 3 and "direct operating expenses and selling and administrative expenses respectively" in match.re.pattern:
        total = _parse_report_million_amount(match.group(1))
        production = _parse_report_million_amount(match.group(2))
        admin = _parse_report_million_amount(match.group(3))
    else:
        production = _parse_million_amount(match.group(1))
        admin = _parse_million_amount(match.group(2))
        total = None
    if production is None and admin is None:
        return None

    quote_lines = [line.strip() for line in match.group(0).splitlines() if line.strip()]
    quote = " ".join(quote_lines[:3]) if quote_lines else match.group(0).strip()
    if total is None and isinstance(partial, dict):
        total = partial.get("employee_benefit_expense_m")
    if total is None:
        total_lines = _context_window(
            lines,
            ("員工成本", "员工成本", "僱員福利開支", "Employee benefit expenses", "Staff costs", "staff costs"),
        )
        for line in total_lines:
            m = re.search(r"(?:總計|总计|Total)\s*([0-9,]+(?:\.\d+)?)", line, flags=re.I)
            if m:
                total = _parse_million_amount(m.group(1))
                if total is not None:
                    break
        if total is None:
            m = re.search(
                r"(?:員工成本總額|员工成本总额|total staff costs[^。\n]{0,80}?RMB\s*[0-9,]+(?:\.\d+)?\s*million)",
                text,
                flags=re.I | re.S,
            )
            if m:
                amount_match = re.search(r"([0-9,]+(?:\.\d+)?)", m.group(0))
                if amount_match:
                    total = _parse_million_amount(amount_match.group(1))
    if total is None and production is not None and admin is not None:
        total = round(production + admin, 3)

    return {
        "production": production,
        "sales": None,
        "admin": admin,
        "rd": None,
        "total": total,
        "quote": quote,
        "note_basis": "年报利润表附注“员工成本/僱員福利開支—计入销售及服务成本/行政开支”按费用归属回填",
        "source_pages": [],
    }


def _extract_employee_benefit_total_from_report_md(stock_dir: str, year: str) -> float | None:
    """Extract total employee benefit expense when only the aggregate is disclosed."""
    text = _load_report_md_text(stock_dir, year)
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    direct_patterns = [
        r"員工成本總額約為(?:人民幣|人民币)?\s*([0-9,\.]+)\s*(億元|百萬元|百万港元|百萬港元)",
        r"员工成本总额约为(?:人民币)?\s*([0-9,\.]+)\s*(亿元|百万元|百万港元|百萬港元)",
        r"員工成本總額(?:為|约為|約為)(?:人民幣|人民币)?\s*([0-9,\.]+)\s*(億元|百萬元|百万港元|百萬港元)",
        r"员工成本总额(?:为|约为|約為)(?:人民币)?\s*([0-9,\.]+)\s*(亿元|百万元|百万港元|百萬港元)",
        r"total staff costs[^。\n]{0,160}?RMB\s*([0-9,\.]+)\s*million",
        r"^\s*employee benefit expenses[^。\n]{0,160}?RMB\s*([0-9,\.]+)\s*million",
        r"^\s*staff costs[^。\n]{0,160}?RMB\s*([0-9,\.]+)\s*million",
        r"^\s*(?:Employee benefit expenses(?: \(note \d+\))?|Employee benefit expense(?: \(note \d+\))?|僱員福利開支(?:（附註\d+）)?|员工成本(?:（附註\d+）)?|員工成本(?:（附註\d+）)?)[^\n]{0,100}?\s([0-9,]+(?:\.\d+)?)\s+[0-9,]+(?:\.\d+)?",
    ]
    for pattern in direct_patterns:
        m = re.search(pattern, text, flags=re.I | re.S | re.M)
        if m:
            if len(m.groups()) >= 2:
                value = _parse_report_million_amount(m.group(1))
                unit = m.group(2)
                if value is None:
                    continue
                if "億" in unit or "亿" in unit:
                    return round(value * 100.0, 3)
                return value
            match_line = m.group(0).strip()
            for idx, line in enumerate(lines):
                if match_line and match_line in line:
                    parser = _detect_local_amount_parser(lines, idx)
                    value = parser(m.group(1))
                    if value is not None:
                        return value
                    break
            value = _parse_report_million_amount(m.group(1))
            if value is not None:
                return value

    context_markers = [
        ("(b) 員工成本", "员工成本（", "員工成本（", "僱員福利開支（", "Employee benefit expenses", "Staff costs"),
        ("員工成本總額", "员工成本总额", "員工成本", "员工成本", "僱員福利開支", "employee benefit expenses", "staff costs"),
    ]
    for markers in context_markers:
        context = _context_window(lines, markers)
        saw_component_lines = False
        for idx, line in enumerate(context):
            m = re.search(r"(?:總計|总计|Total)\s*([0-9,]+(?:\.\d+)?)", line, flags=re.I)
            if m:
                parser = _detect_local_amount_parser(context, idx)
                return parser(m.group(1))
            m = re.search(
                r"^\s*(?:Employee benefit expenses(?: \(note \d+\))?|Employee benefit expense(?: \(note \d+\))?|僱員福利開支(?:（附註\d+）)?|员工成本(?:（附註\d+）)?|員工成本(?:（附註\d+）)?)[^\n]{0,100}?\s([0-9,]+(?:\.\d+)?)\s+[0-9,]+(?:\.\d+)?",
                line,
                flags=re.I,
            )
            if m:
                parser = _detect_local_amount_parser(context, idx)
                return parser(m.group(1))
            if any(
                token in line
                for token in (
                    "工資及薪金",
                    "工资及薪金",
                    "退休金計劃供款",
                    "退休福利計劃供款",
                    "Pension scheme contributions",
                    "Wages and salaries",
                    "權益結算股份支付開支",
                    "share-based",
                )
            ):
                saw_component_lines = True
        if saw_component_lines:
            for offset, line in reversed(list(enumerate(context))):
                if re.fullmatch(r"[0-9,]+(?:\.\d+)?(?:\s+[0-9,]+(?:\.\d+)?)+", line):
                    parser = _detect_local_amount_parser(context, offset)
                    return parser(line.split()[0])

    patterns = [
        r"(?:員工成本總額|员工成本总额)\s*([0-9,]+(?:\.\d+)?)",
        r"(?:僱員福利開支|员工成本|員工成本)[^\n]{0,120}?總計\s*([0-9,]+(?:\.\d+)?)",
        r"(?:Employee benefit expenses?|Staff costs?)\s*[^\n]{0,160}?\btotal\b\s*([0-9,]+(?:\.\d+)?)",
        r"total staff costs[^。\n]{0,120}?RMB\s*([0-9,]+(?:\.\d+)?)\s*million",
        r"員工成本總額約為人民幣\s*([0-9,]+(?:\.\d+)?)\s*百萬元",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            match_line = m.group(0).strip()
            for idx, line in enumerate(lines):
                if match_line and match_line in line:
                    parser = _detect_local_amount_parser(lines, idx)
                    return parser(m.group(1))
            return _parse_million_amount(m.group(1))
    return None


def _extract_labor_split_table_from_report_md(stock_dir: str, year: str) -> dict | None:
    """Extract labor split from employee-cost allocation tables."""
    text = _load_report_md_text(stock_dir, year)
    if not text:
        return None
    text = _strip_year_comparison_parentheticals(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    marker_groups = [
        ("計入員工成本", "计入员工成本", "分配員工成本", "分配员工成本"),
        ("僱員福利開支", "员工成本", "Employee benefit expenses", "Staff costs", "staff costs"),
        ("按性質劃分的開支", "按性质划分的开支", "費用分析如下", "费用分析如下"),
    ]
    contexts: list[list[str]] = []
    for markers in marker_groups:
        for idx, line in enumerate(lines):
            if any(marker in line for marker in markers):
                contexts.append(lines[idx: idx + 14])
                break

    if not contexts:
        return None

    label_patterns = [
        (
            "production",
            r"^\s*(?:\|?\s*)?(?:銷售成本|销售成本|銷售及服務成本|销售及服务成本|服務成本|服务成本|已售存貨成本|已售存货成本|direct operating expenses|cost of sales)(?:\s|[:：|])",
        ),
        (
            "sales",
            r"^\s*(?:\|?\s*)?(?:分銷及銷售開支|分销及销售开支|銷售及營銷開支|销售及营销开支|selling and marketing expenses|selling and distribution expenses|selling expenses)(?:\s|[:：|])",
        ),
        (
            "admin",
            r"^\s*(?:\|?\s*)?(?:行政開支|行政开支|管理開支|管理开支|一般及行政開支|一般及行政开支|selling and administrative expenses|administrative expenses|general and administrative expenses)(?:\s|[:：|])",
        ),
        (
            "rd",
            r"^\s*(?:\|?\s*)?(?:研發開支|研发开支|研究開支|研究开支|research and development expenses|research expenses)(?:\s|[:：|])",
        ),
    ]

    def _first_amount(line: str, parser) -> float | None:
        nums = re.findall(r"([0-9][0-9,]*(?:\.\d+)?)", line)
        if not nums:
            return None
        first = nums[0]
        idx = 1
        # OCR occasionally breaks "2,104" into "2,10 4".
        while "," in first and len(first.split(",")[-1]) < 3 and idx < len(nums):
            first += nums[idx]
            idx += 1
        return parser(first)

    for context in contexts:
        production = sales = admin = rd = total = None
        quote_lines = []
        saw_employee_block = False
        explicit_table_marker = False
        parse_amount = _parse_report_million_amount
        if any(("千元" in line or "千余元" in line or "thousand" in line.lower()) for line in context):
            parse_amount = _parse_million_amount
        for line in context:
            if any(
                marker in line
                for marker in (
                    "計入員工成本",
                    "计入员工成本",
                    "分配員工成本",
                    "分配员工成本",
                    "僱員福利開支",
                    "员工成本",
                    "Employee benefit",
                    "Staff costs",
                    "staff costs",
                    "按性質劃分的開支",
                    "按性质划分的开支",
                    "費用分析如下",
                    "费用分析如下",
                )
            ):
                saw_employee_block = True
                quote_lines.append(line)
            if any(marker in line for marker in ("計入員工成本", "计入员工成本", "分配員工成本", "分配员工成本")):
                explicit_table_marker = True

            matched_field = None
            for field, pattern in label_patterns:
                if re.search(pattern, line, flags=re.I):
                    matched_field = field
                    value = _first_amount(line, parse_amount)
                    if value is None:
                        continue
                    if field == "production" and production is None:
                        production = value
                    elif field == "sales" and sales is None:
                        sales = value
                    elif field == "admin" and admin is None:
                        admin = value
                    elif field == "rd" and rd is None:
                        rd = value
                    quote_lines.append(line)
                    break

            if matched_field is None and saw_employee_block:
                if re.fullmatch(r"[\d,]+(?:\.\d+)?\s+[\d,]+(?:\.\d+)?", line):
                    value = _first_amount(line, parse_amount)
                    if total is None and value is not None:
                        total = value
                        quote_lines.append(line)

        if total is None:
            known = [v for v in (production, sales, admin, rd) if v is not None]
            if known:
                total = round(sum(known), 3)

        category_count = sum(v is not None for v in (production, sales, admin, rd))
        if category_count and (explicit_table_marker or category_count >= 2):
            quote = " ".join(dict.fromkeys(quote_lines[:5])) if quote_lines else "员工成本分配表"
            return {
                "production": production,
                "sales": sales,
                "admin": admin,
                "rd": rd,
                "total": total,
                "quote": quote,
                "note_basis": "年报员工成本按销售/分销/行政/研发费用分配表回填",
                "source_pages": [],
            }

    return None


def build_gg_override_from_partials(partials: dict, stock_dir: str | None = None) -> dict | None:
    """Build gg_override.json from Zone B year partials.

    Producer boundary:
    - Reads only structured note-extraction facts from partials
    - Emits standalone compute-facing override artifact
    - Does not mix GG conclusion into Zone B narrative JSONs
    """
    years_payload = {}
    for yr in sorted(partials.keys()):
        partial = partials.get(yr) or {}
        labor = partial.get("labor_by_function")
        if not isinstance(labor, dict) and stock_dir:
            labor = _extract_labor_by_function_from_report_md(stock_dir, str(yr), partial)
            if labor is None:
                total_only = _extract_employee_benefit_total_from_report_md(stock_dir, str(yr))
                if total_only is not None:
                    partial["employee_benefit_expense_m"] = total_only
            if labor:
                partial["labor_by_function"] = labor
        if not isinstance(labor, dict):
            continue

        production = labor.get("production")
        admin = labor.get("admin")
        sales = labor.get("sales")
        rd = labor.get("rd")
        total = labor.get("total")
        if all(v is None for v in [production, admin, sales, rd, total]):
            continue
        if production is None and admin is None and sales is None and rd is None:
            continue

        entry = {
            "direct_labor_cost": production,
            "admin_labor_cost": admin,
            "sales_labor_cost": sales,
            "rd_labor_cost": rd,
            "total_labor_cost": total,
            "outsourced_service_cost": None,
            "notes_basis": labor.get("note_basis") or "职工薪酬附注按职能拆分提取",
            "confidence": "high" if production is not None and all(v is not None for v in [admin, sales, rd, total]) else "medium",
            "source_year": str(yr),
            "source_pages": labor.get("source_pages") if isinstance(labor.get("source_pages"), list) else [],
            "quote": labor.get("quote"),
        }
        known_components = [v for v in [production, admin, sales, rd] if v is not None]
        if total is not None and known_components:
            residual = total - sum(known_components)
            entry["outsourced_service_cost"] = round(max(residual, 0.0), 2)
        years_payload[str(yr)] = entry

    if not years_payload:
        return None

    return {
        "years": years_payload,
        "meta": {
            "source": "zone_b_partials",
            "purpose": "compute_bundle direct labor override",
        },
    }


def write_zone_b_jsons(master_output: dict, stock_dir: str, partials: dict = None):
    """V8.2: Write master agent output as 5 Zone B JSON files with validation + fallback.

    Also emits optional gg_override.json when year partials contain
    labor_by_function note extraction.
    """
    if partials is None:
        partials = {}
        for year in ["2021", "2022", "2023", "2024", "2025"]:
            path = os.path.join(stock_dir, f"zone_b_{year}_partial.json")
            if os.path.exists(path):
                with open(path) as f:
                    partials[year] = json.load(f)

    files = ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"]
    for fname in files:
        if fname in master_output:
            raw = master_output[fname]
            # 校验清理
            cleaned = _validate_zone_b(raw, fname, partials)
            # 从 partials 补回 master 丢失的 quote
            cleaned = _copy_quotes_from_partials(cleaned, fname, partials)
            path = os.path.join(stock_dir, fname)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=2, ensure_ascii=False)
            size = os.path.getsize(path)
            # 质量标记
            hl_count = sum(len(v) if isinstance(v, list) else 0
                          for v in cleaned.get("year_highlights", {}).values())
            print(f"  ✅ {fname} ({size:,}B, {hl_count} highlights)")
        else:
            print(f"  ⚠️ {fname}: 未在 master 输出中找到")
    missing = [f for f in files if f not in master_output]
    if missing:
        print(f"  ⚠️ Missing: {missing}")

    gg_override = build_gg_override_from_partials(partials, stock_dir=stock_dir)
    gg_path = os.path.join(stock_dir, "gg_override.json")
    if gg_override:
        with open(gg_path, "w", encoding="utf-8") as f:
            json.dump(gg_override, f, indent=2, ensure_ascii=False)
        print(f"  ✅ gg_override.json ({len(gg_override.get('years', {}))} years)")
    elif os.path.exists(gg_path):
        # Keep producer output honest: no stale override when current extraction lacks data.
        os.remove(gg_path)
        print("  🧹 gg_override.json removed (no labor_by_function extracted)")


def build_master_prompt(ts_code: str, stock_dir: str) -> str:
    """Build consolidation prompt for the master agent."""
    # Load all partial JSONs (dynamic year detection)
    partials = {}
    for fname in sorted(os.listdir(stock_dir)):
        if fname.startswith("zone_b_") and fname.endswith("_partial.json"):
            yr = fname.replace("zone_b_", "").replace("_partial.json", "")
            path = os.path.join(stock_dir, fname)
            with open(path) as f:
                partials[yr] = json.load(f)

    if not partials:
        return None

    years = sorted(partials.keys())

    # Load compute_bundle for cross-validation
    cb_path = os.path.join(stock_dir, "compute_bundle.json")
    cb = {}
    if os.path.exists(cb_path):
        with open(cb_path) as f:
            cb = json.load(f)

    # Load DB financials from pdf_full_text.json
    ft_path = os.path.join(stock_dir, "pdf_full_text.json")
    db_fin = {}
    if os.path.exists(ft_path):
        with open(ft_path) as f:
            ft = json.load(f)
        db_fin = ft.get("_db_financials", {})

    # Build compact per-year summary (avoids truncating full partials)
    year_summaries = []
    for yr in years:
        p = partials[yr]
        rev_items = [h if isinstance(h, str) else h.get("item", str(h))
                     for h in p.get("revenue_highlights", [])[:4]]
        seg_items = [s.get("name", str(s)) if isinstance(s, dict) else str(s)
                     for s in p.get("segment_data", [])[:4]]
        risk_items = [r.get("description", str(r)) if isinstance(r, dict) else str(r)
                      for r in p.get("risk_items", [])[:3]]
        strategy_items = [s.get("detail", str(s)) if isinstance(s, dict) else str(s)
                          for s in p.get("strategy_changes", [])[:3]]
        mgmt_items = [m.get("explanation", str(m)) if isinstance(m, dict) else str(m)
                      for m in p.get("mgmt_explanations", [])[:4]]

        # DB financial snapshot
        db_row = db_fin.get(yr, {})
        fin_snap = ""
        if db_row:
            fin_snap = (f"营收={db_row.get('revenue','?')}M, "
                        f"NP={db_row.get('n_income_attr_p','?')}M, "
                        f"OCF={db_row.get('n_cashflow_act','?')}M")

        # 审计 & 治理核心字段
        audit = p.get("audit_info", {}) or {}
        auditor = audit.get("auditor", "?")
        opinion = audit.get("opinion", audit.get("audit_opinion", "?"))
        kam = audit.get("key_audit_matters", []) or []
        gw = f"商誉={p.get('goodwill_balance_m','?')}M/减值={p.get('goodwill_impairment_m','?')}M"
        rpt_count = len(p.get("related_party_transactions") or [])
        cl_count = len(p.get("contingent_liabilities") or [])
        nr_count = len(p.get("non_recurring_items") or [])
        gov_count = len(p.get("governance_events") or [])

        year_summaries.append(f"""FY{yr} [{fin_snap}]
  审计师: {auditor} | 意见: {opinion} | KAM({len(kam)}): {json.dumps(kam[:2], ensure_ascii=False)}
  {gw} | 关联交易({rpt_count}) | 或有事项({cl_count}) | 非经常({nr_count}) | 治理事件({gov_count})
  业务亮点: {json.dumps(rev_items, ensure_ascii=False)}
  分部({len(seg_items)}): {json.dumps(seg_items, ensure_ascii=False)}
  管理层解释({len(mgmt_items)}): {json.dumps(mgmt_items, ensure_ascii=False)}
  战略({len(strategy_items)}): {json.dumps(strategy_items, ensure_ascii=False)}
  风险({len(risk_items)}): {json.dumps(risk_items, ensure_ascii=False)}""")

    year_context = "\n".join(year_summaries)

    prompt = f"""你是 Zone B 汇总分析师。基于{years[0]}-{years[-1]}共{len(years)}年的结构化提取结果，完成跨年趋势分析和最终 Zone B JSON 输出。

【{len(years)}年提取摘要（完整数据见各 zone_b_*_partial.json）】
{year_context}

【compute_bundle 交叉验证参考】
{json.dumps({
    "market": cb.get("market", {}),
    "factor2_avg": {k: cb.get("factor2", {}).get(k) for k in ["np_avg_3y","np_avg_5y","ocf_np_ratio"] if k in cb.get("factor2", {})},
    "gg": cb.get("factor3", {}).get("gg", {}),
}, indent=2, ensure_ascii=False)}

【任务】
1. 跨年趋势（每项1-2句，标注年份区间）:
   a. 毛利率方向+幅度
   b. 营收增长质量
   c. 管理层战略变化
   d. 风险演变

2. 输出最终 Zone B JSON。**year_highlights 中每条必须是中文完整句子（≥10字），不要输出单字或符号。**

3. 数字以 compute_bundle / DB 为准。缺失标注"⚠️ 不可用"。

输出纯JSON（不含markdown fence），格式如下:
{{
  "mda.json": {{"year_highlights": {{"2021": ["...", "..."], ...}}, "trend_analysis": {{...}}, "strategy_changes": [...], "mgmt_explanations": {{...}}, "forward_guidance": [...]}},
  "segments.json": {{"segments": {{"2021": [...], ...}}, "revenue_structure_evolution": "...", "margin_by_segment_trend": "..."}},
  "risks.json": {{"principal_risks": [...], "risk_evolution": "...", "goodwill_trend": "...", "contingent_liabilities": "...", "ar_aging": "...", "restricted_cash_summary": "..."}},
  "governance.json": {{"related_party_transactions": [...], "governance_timeline": "...", "transparency_assessment": "...", "employee_benefit_trend": "...", "related_party_deposits": "..."}},
  "audit.json": {{"auditor_history": [...], "audit_opinion_history": [...], "key_audit_matters": [...], "non_recurring_summary": "...", "accounting_policy_changes": "...", "sbc_summary": "...", "capitalized_interest_summary": "..."}}
}}

【强制规则】
1. year_highlights 每条 ≥10 个中文字符，完整叙事句。严禁输出单字如"不""⚠""️"。
2. 覆盖所有{len(years)}年({', '.join(years)})，某年无数据标注"⚠️ 无提取数据"
3. segments 必须包含品类名称(name)、定性描述(highlight)、原文引用(quote)。quote 从 partial 的 segment_data[].quote 逐字复制，不要改写。
4. year_highlights 和 mgmt_explanations 每条必须附带 quote 字段（从对应 partial 逐字复制原文）
5. 金额统一百万元RMB"""
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
