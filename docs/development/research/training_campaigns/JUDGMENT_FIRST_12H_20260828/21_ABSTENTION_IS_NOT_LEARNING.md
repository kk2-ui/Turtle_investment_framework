# 弃权不是学习成果

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> 裁决：`ABSTENTION_REMAINS_LOCAL / NO_FEEDBACK_CREDIT_WITHOUT_OBSERVED_MISMATCH`

## 被纠正的奖励错位

旧 Forecast 路径允许把结果前 cell 标为 `EVIDENCE_INELIGIBLE / ABSTAIN`，不提交概率；结果结算
只回显同一状态后，系统却可以授予 `COVERAGE / FORECAST_POLICY_DIRECT`。全维度弃权时甚至可能在
`0/18` 个 cell 可评分、没有一项结果观察的情况下获得活跃学习政策。

这会奖励最安全的策略：不作可反驳预测，却把“我没有预测”记成方法反馈。

## 当前语义

- 缺少合格证据的 cell 仍可诚实 `ABSTAIN`；不强迫编造概率。
- 全部弃权或全部结果未知仍可完成局部结算，但为 `NOT_DIAGNOSTIC / NONE`。
- 局部弃权不污染其他已经观察的 cell；其余 cell 仍正常接受 calibration 反馈。
- `EVIDENCE_INELIGIBLE` 是结果前证据状态，不是结果后发现，不产生 coverage 学习。
- 只有实际采集后，由独立 custodian receipt 记录为 `MEASUREMENT_MISMATCH`，且 settlement、cell、
  冻结 measurement rule 和官方来源相符，才允许 `COVERAGE / FORECAST_POLICY_DIRECT`。

```text
结果前放弃预测
    -> cell 保持局部 EVIDENCE_INELIGIBLE
    -> 反馈效用 NONE

结果前作出合格预测，结果采集发现冻结口径无法匹配
    -> MEASUREMENT_MISMATCH
    -> 可形成局部 COVERAGE 方法反馈
```

Control plane 从已注册数据库对象读取 settlement、observation receipt、measurement contract 和
acquisition scope；调用方不能在 attribution 文案中替换这些事实。Coverage 政策只改变以后如何
定义或采集测量，不得改写企业判断，也不授予 CJO、报告、估值或投资权限。

## 对判断优先训练的意义

局部未知仍是必要边界，但它的机会成本现在是真实的：该 cell 不获得误差反馈，也不能给方法加分。
系统因此不会强迫无证据预测，同时也不再把拒绝判断包装成训练进步。能获得学习信用的，是结果后
新发现的测量失败或可评分预测误差，不是结果前已经知道的证据不足。
