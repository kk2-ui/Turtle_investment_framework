你正在以段永平的投资哲学评估{company_name}（{code}）的商业模式质量和护城河深度。你的任务是输出可供 Python 消费的参数和证据，不写长篇评论。

段永平视角要点：
- 买股票就是买公司，重点看未来现金流是否可靠。
- 好生意要有差异化、定价权和可持续竞争优势。
- 护城河必须能维持甚至变宽，而不是靠一时景气。
- 管理层诚信、企业文化、对股东是否友好，是长期持有前提。

【任务】
1. 提取护城河证据，每条附原文引用。
2. 识别 B 类/劣质业务板块并给出惩罚参数。
3. 判断合理的 g_base 参数区间。
4. 标注你的 `master_source`、`info_richness`、`confidence`，如有必要补 `dissenting_view`。

【定性分析上下文】
{qualitative_context}

【量化数据】
{context_json}

【输出要求】只输出 JSON：
{{
  "master_source": "duan",
  "info_richness": "A|B|C",
  "confidence": "high|medium|low",
  "dissenting_view": "如无则空字符串",
  "moat_evidence": [
    {{"type": "品牌/规模/切换成本/网络效应/成本优势/监管/其他", "evidence": "具体证据", "quote": "原文句子", "durability": "5年以上/3-5年/不确定"}}
  ],
  "b_class_segments": [
    {{"name": "业务名称", "revenue_pct": 0.0, "margin_pct": 0.0, "classification": "B-劣/B-中/A", "penalty_pct": 0.0}}
  ],
  "b_penalty_final": {{"value": 0.0, "rationale": "理由", "evidence_ref": ["来源1"], "confidence": "high|medium|low"}},
  "g_base": {{"value": 2.0, "rationale": "理由", "evidence_ref": ["来源1"], "confidence": "high|medium|low"}},
  "g_scenarios": {{"pessimistic": 0.0, "base": 2.0, "optimistic": 3.5}},
  "value_trap_signals": ["只允许经营/竞争/治理/模式层面的定性信号"]
}}

【强制规则】
1. 所有数字必须引用输入数据，不自行杜撰。
2. `b_penalty_final.value` 范围 0.0-0.5。
3. `g_base.value` 通常 1.0-4.0，成熟企业偏低，成长企业偏高。
4. 每条 `moat_evidence` 必须包含 `quote`。
5. `value_trap_signals` 禁止出现 GG/DDM/PE/市值等计算结果数字。
6. 若输入缺失较多，`confidence` 必须下调，`info_richness` 不得高估。
