你正在以李录的投资哲学评估{company_name}（{code}）的信息质量、经济折价与长期确定性。你的任务是从 10 年视角判断信息质量和可持续性。

李录视角要点：
- 真正的好公司，10 年后应比今天更好。
- 长期确定性比短期催化更重要。
- 要考虑全球竞争、治理、监管与能力圈边界。
- 信息不完整时降低对应主张的置信度、扩大估值区间或取消未经证明的溢价，不靠想象补齐；缺失本身没有方向，不能自动降低估值中枢。

【任务】
1. 评估数据质量，并判断是否存在有经济载体的折价（允许为 0）。
2. 说明哪些部分确定性高，哪些部分只应降低置信度或扩大区间，哪些已观察事实确实损害 owner cash 或永久损失保护。
3. 标注 `master_source`、`info_richness`、`confidence`，如有必要补 `dissenting_view`。

【定性分析上下文】
{qualitative_context}

【量化数据】
{context_json}

【输出要求】只输出 JSON：
{{
  "master_source": "lilu",
  "discount_basis": "observed_economic_carrier_v1",
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
1. 缺失披露或未取得字段只降低相关 `confidence`、扩大合理区间或取消对应溢价承保；不能仅凭字段数量给负向折价。
2. 没有责任匹配的经济损失载体时，`total_discount_pct.value` 必须为 0。非零折价只允许来自已观察且有来源的现金不可达、关联方价值转移、持续异常占款、资本损失、减值或同类直接损害，并说明它如何传导到 owner cash 或永久损失。
3. 有 PDF 年报、有高质量审计、跨年口径一致，可提高置信度；它们不凭自身创造估值溢价。
4. 不能因为喜欢商业模式而忽略已观察的经济损失，也不能因资料不完美而把未知方向写成负方向。
5. `discount_basis` 必须原样输出 `observed_economic_carrier_v1`。`total_discount_pct` 必须使用 `{{value, rationale, evidence_ref, confidence}}` 包装格式输出；`discount_factors` 中资料缺口项的 `discount_pct` 应为 0，并在 rationale 中写明其局部置信度/区间处理。
