# 研究流程端到端干跑 08：合格早期信号会不会被过度解读？

状态：`METHOD_PREPARATION_TEST / SYNTHETIC / NO_COMPANY_RESEARCH`  
范围：完整模拟一个可冻结的早期经营信号；不代表真实公司、行业数据或投资结论。

## 1. cutoff 前的迭代卡

| 字段 | 模拟填写 |
|---|---|
| 决定性问题 | 单一线上份额下行是渠道/价格带重配，还是扩展为同一消费者集合的全渠道竞争恶化？ |
| 训练能力 | 机制辨别 + 校正能力。 |
| 同一终局 | 三年内国内竞争位置是否支持正常盈利与现金转换。 |
| H-A | 线上可下行，但同 provider 的全渠道高价格带相对位置稳定。 |
| H-B | 全渠道、线上与线下的同口径相对位置均明显下行。 |
| 概率 | `NO_PROBABILITY`；只有方向和非嵌套结果区域。 |
| cutoff 前来源 | 已冻结的 provider panel：品牌、渠道、价格带、分母、release/version、query、定义与修订政策完整；公司事实只作财务传导背景。 |
| 结果防火墙 | t1 provider release 及公司后续披露均不可读，直至机制卡冻结。 |

## 2. 可冻结的竞争信号

指标：同一 provider、同一品牌映射、同一全渠道零售额份额，高价格带；t1 相对 t0。

| 结果区域 | 预先冻结的定义 | 结算含义 |
|---|---|---|
| `A_ONLY` | 线上份额下降，但全渠道高价格带份额变化 `≥ -0.5pct`。 | 仅支持 H-A 的“渠道/价格带未扩散”箭头。 |
| `B_ONLY` | 全渠道高价格带份额变化 `≤ -1.5pct`，并与线上同方向。 | 仅支持 H-B 的“竞争扩散”箭头。 |
| `MIXED` | 变化在 -1.5pct 与 -0.5pct 之间，或渠道方向冲突。 | 不支持任一机制。 |
| `NEITHER` | provider 定义、品牌映射或渠道覆盖改变。 | 重开测量边界；不结算。 |

来源在 cutoff 前已是 `SETTLEMENT_ELIGIBLE`；t1 结果尚未到期，故此时状态是 `FROZEN_FOR_SETTLEMENT / NO_COMPANY_CONCLUSION`。

## 3. 结果期的受控打开

冻结后打开 t1 release：线上份额下降，全渠道高价格带份额为 -0.3pct，provider 的定义、品牌映射和覆盖未变。

早期信号应结算为 `SUPPORTS_PRIMARY`，但仅限 H-A 的一个竞争位置箭头。它不会自动证明：

- 三年终局成立；
- 价格实现、返利、营运资本或 owner cash 已稳定；
- 管理层能力、护城河或资本配置已经被验证；
- 任何价值、市场价格、投资回报或行动结论。

## 4. 端到端审阅

| 阶段 | 正确输出 |
|---|---|
| 来源卡 | `FACT`/`SETTLEMENT_ELIGIBLE`，具独立 `lineage_id` 与固定 provider 定义。 |
| 机制实验 | A-only/B-only/Mixed/Neither 完整，且两方不嵌套。 |
| 冻结前 | `NO_PROBABILITY / FROZEN_FOR_SETTLEMENT / NO_COMPANY_CONCLUSION`。 |
| 早期结算 | `SUPPORTS_PRIMARY`，只更新单一箭头。 |
| 终局 | 仍为 `NOT_YET_DUE`，保留竞争机制和财务传导的其他未知。 |
| 复盘 | 评估信号诊断性和来源稳定性；不得将结果回写 cutoff 卡。 |

## 5. 干跑发现的流程缺口与修订

旧对象状态只有 `FROZEN_FOR_SETTLEMENT`，不能描述“早期信号已结算、终局尚未到期”的中间状态；这会诱导研究者过早关闭 episode 或把单一早期胜负写成终局判断。

流程新增 `EARLY_SIGNAL_SETTLED / TERMINAL_PENDING`。该状态允许记录哪个箭头受到支持，但禁止写中心公司结论、估值或投资行动。

## 6. 复跑结论

`MODIFY → RETEST_PASSED`：流程在真正合格的来源与非嵌套信号下允许冻结和早期反馈，同时维持 `NO_COMPANY_CONCLUSION`。这证明流程两端都能工作；它仍不证明该阈值、provider 或方法在真实公司中有预测效力。
