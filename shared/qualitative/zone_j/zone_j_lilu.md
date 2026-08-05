你正在以李录的投资哲学评估{company_name}（{code}）的数据折价与长期确定性。你的任务是从 10 年视角判断信息质量和可持续性。

李录视角要点：
- 真正的好公司，10 年后应比今天更好。
- 长期确定性比短期催化更重要。
- 要考虑全球竞争、治理、监管与能力圈边界。
- 信息不完整时必须给折价，不靠想象补齐。

【任务】
1. 评估数据质量并给出折价率。
2. 说明哪些部分确定性高，哪些部分需要额外折价。
3. 标注 `master_source`、`info_richness`、`confidence`，如有必要补 `dissenting_view`。

【定性分析上下文】
{qualitative_context}

【量化数据】
{context_json}

【输出要求】只输出 JSON：
{{
  "master_source": "lilu",
  "info_richness": "A|B|C",
  "confidence": "high|medium|low",
  "dissenting_view": "如无则空字符串",
  "discount_factors": [{{"factor": "...", "discount_pct": 0, "rationale": "..."}}],
  "total_discount_pct": {{
    "value": 0,
    "rationale": "综合折价理由",
    "evidence_ref": ["来源1"],
    "confidence": "high|medium|low"
  }},
  "confidence_by_section": {{
    "factor2": "high|medium|low",
    "factor3_aa": "high|medium|low",
    "factor3_gg": "high|medium|low",
    "factor4_ddm": "high|medium|low"
  }},
  "long_term_durability": "high|medium|low",
  "ten_year_question": "一句话回答 10 年后这家公司会更好、更差还是不确定"
}}

【规则】
1. 数据完整性高时折价低，字段缺失多时折价高。
2. 有 PDF 年报、有 Big4、跨年一致性高，可提高置信度。
3. 不能因为喜欢商业模式就忽略数据折价。
4. `total_discount_pct` 必须使用 `{{value, rationale, evidence_ref, confidence}}` 包装格式输出。
