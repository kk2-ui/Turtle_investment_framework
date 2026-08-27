# 决策效用必须来自真实的结果前变化

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 裁决：`REVIEWER_LABEL_IS_NOT_UTILITY / STRUCTURED_PREOUTCOME_DELTA_REQUIRED`

## 问题

旧的 decision-utility 路径允许独立 reviewer 把某一维写成
`MATERIAL_IMPROVEMENT`，再引用一个存在的结果 cell，就产生
`CANDIDATE_ONLY`。即使 baseline 和 enhanced 的企业判断、机制、结果依赖和投资处理完全相同，
这个标签仍可能被当作方法有效。

这奖励的是 reviewer 文案，而不是判断改善。它与本轮三次 `NO_MATERIAL_UTILITY` 的真实经验直接
冲突：结构更完整、解释更清楚、规则正常运行，都不能自动算作投资效用。

## 当前机械边界

结果前 pairing 只冻结比较对象，始终保持：

```text
artifact_status = FROZEN
authority_ceiling = NONE
learning_authorization = NONE
```

普通 Episode 路径只有同时满足以下三项，才可能得到
`MATERIAL_UTILITY / CANDIDATE_ONLY`：

1. enhanced 在某一判断维度新增了 baseline 没有的
   `dependent_outcome_cell_ids`，即真实改变了结果前研究/结算处理；
2. 匹配的 settlement 将同一个 cell 结算为 `OBSERVED`；
3. 独立 reviewer 在同一维度裁决该变化避免了材料错误或形成材料改善。

Forecast control 路径还要求：新增依赖在结果前绑定预注册 Forecast cell、baseline 与 enhanced
冻结的概率分布确实不同，并由注册的 paired evaluation 和数据库中的 settlement 结算。概率数组
只是行序不同不算预测变化；比较按 `label -> probability` 内容进行。

## 明确不给效用的变化

- episode、claim、method 或文件 ID 变化；
- statement 措辞、格式、字段数量或解释清晰度变化；
- 两臂结论相同，但 reviewer 自报 `MATERIAL_IMPROVEMENT`；
- 新增结果依赖尚为 `UNKNOWN`，或引用了无关维度的结果；
- 两臂概率相同，只是 JSON 行顺序不同；
- 结果前没有结构化载体，却在结果后声称估值、最高买价或投资动作改善。

最后一项尤其重要：当前 Episode manifest 没有足够结构化的估值、买价和动作载体，系统不会从
自由文本推断这些变化。缺少载体时诚实结果是 `NOT_DIAGNOSTIC / NONE`，而不是让 reviewer
用更强语气补齐。

## 裁决语义

```text
enhanced = HARMFUL
    -> HARMFUL / NONE

reviewer 声称材料变化，但无冻结 delta 或无相关 OBSERVED 结果
    -> NOT_DIAGNOSTIC / NONE

两臂无材料差异
    -> NO_MATERIAL_UTILITY / NONE

冻结 delta + 相关 OBSERVED 结果 + 同维独立材料裁决
    -> MATERIAL_UTILITY / CANDIDATE_ONLY
```

这里没有分数、字段数或“命中几个维度”的阈值。一个真实、材料且被结果支持的变化可以成为
候选；八个写得很完整但没有改变判断处理的维度仍然是零。

## 权限与历史工件

`CANDIDATE_ONLY` 只允许把该变化带入下一家结果未见公司的前瞻复验，不等于 transfer
validated，更不授予 Comparative、CJO、正式估值、BuyBand、报告发布或投资权限。历史
V1/V2/V3 工件保持只读，不因新 validator 被追溯升级。

这项修复改变的是训练奖励：系统不再问“reviewer 是否写得像有效”，而是问“结果前到底改变了
什么，结果是否真的支持这项改变”。
