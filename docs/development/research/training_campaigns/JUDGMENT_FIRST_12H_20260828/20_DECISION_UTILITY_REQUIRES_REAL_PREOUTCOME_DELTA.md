# 决策效用必须来自真实的结果前变化

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 裁决：`REVIEWER_LABEL_IS_NOT_UTILITY / CURRENT_SCHEMA_HAS_NO_POSITIVE_TREATMENT_CARRIER`
>
> 当前状态：本文早先把“新增 outcome dependency + OBSERVED 结果”误当成足够的处理变化；
> 该正向授权已在本轮后续复审中撤回。以下内容为当前有效语义。

## 问题

旧的 decision-utility 路径允许独立 reviewer 把某一维写成
`MATERIAL_IMPROVEMENT`，再引用一个存在的结果 cell，就产生
`CANDIDATE_ONLY`。即使 baseline 和 enhanced 的企业判断、机制、结果依赖和投资处理完全相同，
这个标签仍可能被当作方法有效。

这奖励的是 reviewer 文案，而不是判断改善。它与本轮四次 `NO_MATERIAL_UTILITY` 的真实经验直接
冲突：结构更完整、解释更清楚、规则正常运行，都不能自动算作投资效用。

## 当前机械边界

结果前 pairing 只冻结比较对象，始终保持：

```text
artifact_status = FROZEN
authority_ceiling = NONE
learning_authorization = NONE
```

当前 Episode / pairing schema 能冻结 outcome dependency、证据和 Forecast 差异，却没有冻结一组
可直接比较的材料投资处理：管理层评价、owner cash 处理、永久损失处理、估值方向或下一研究动作。
因此新增 outcome dependency、匹配 `OBSERVED` 结果、概率不同或 reviewer 的积极裁决，均不足以证明
decision utility。现行 validator 对这些组合统一返回 `NOT_DIAGNOSTIC / NONE`。

这不是说未来永远不能产生正向效用；而是当前载荷没有证明它的事实。以后只有在结果前直接冻结、
同轴比较上述材料处理，并由相关结果支持时，才可以重新开放 `CANDIDATE_ONLY`。不能用 Brier 改善、
字段数量或 reviewer 文案替代该载体。

## 明确不给效用的变化

- episode、claim、method 或文件 ID 变化；
- statement 措辞、格式、字段数量或解释清晰度变化；
- 两臂结论相同，但 reviewer 自报 `MATERIAL_IMPROVEMENT`；
- 新增 outcome dependency，即使相关结果已经 `OBSERVED`；
- 两臂概率不同或 enhanced Brier 更好、相同或更差；
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

新增 dependency / 概率差异 / OBSERVED 结果 + reviewer 积极标签
    -> NOT_DIAGNOSTIC / NONE
```

这里没有分数、字段数或“命中几个维度”的阈值。八个写得很完整但没有可机械比较的判断处理
变化，仍然是零。Forecast 的同维、同期限局部错误归因继续走自己的机械路径，不被 decision utility
的正向关闭影响。

## 权限与历史工件

当前 schema 不产生正向 `CANDIDATE_ONLY`。`HARMFUL / NONE`、`NO_MATERIAL_UTILITY / NONE` 和
历史 V1/V2/V3 只读语义保持不变；不授予 transfer validated、Comparative、CJO、正式估值、
BuyBand、报告发布或投资权限。

这项修复改变的是训练奖励：系统不再问“reviewer 是否写得像有效”，而是问“结果前到底改变了
什么，当前结构是否真的记录了这项材料处理”。记录不了时不冒充有效。
