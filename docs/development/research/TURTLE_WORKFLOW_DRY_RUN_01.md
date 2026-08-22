# 研究流程干跑 01：噪声资料会不会被误升级为判断？

状态：`METHOD_PREPARATION_TEST / SYNTHETIC / NO_COMPANY_RESEARCH`  
目的：测试当前研究模板是否能在数据不完整时停止，而不是将方向性资料伪装成竞争机制的验证。

## 1. 虚拟输入

设想一家成熟耐用消费品公司，cutoff 为 T：

- 公司年报转引一家市场供应商：线上零售额份额由 26% 降至 23%，但没有 release、query、品牌映射或修订资料；
- 年报：国内收入 -9%，产品毛利率 +0.5pct；
- 行业文章称国内“内销”+1%，未说明是 shipment、sell-in 还是 sell-out；
- 经营现金流上升，但附注显示一项经营相关保证金到期收回；
- 没有全渠道份额、品牌 ASP、经销库存或同口径返利/现金支付。

虚拟输入刻意同时包含公司事实、供应商转述、跨交易点行业数和现金一次性项目；它不代表任何真实公司。

## 2. 研究问题与竞争机制

问题：线上相对位置下行是渠道/价格带重配，还是更广竞争恶化的早期表现？

| 共同事实 | H-A：渠道/价格带重配 | H-B：广泛竞争恶化 |
|---|---|---|
| 线上份额下降、收入弱、毛利暂稳 | 低价线上或渠道组合变化，其他渠道/价格带未必弱。 | 线上弱势会扩散，毛利暂稳由组合/费用/时间错配掩盖。 |

两方都能解释现有材料。合格的早期分歧本应是同一 provider 的全渠道/线下/价格带相对位置，或公司同口径量价费用与现金的联合顺序。

## 3. 旧流程干跑：暴露的问题

旧的来源观察卡能将供应商转述标作 `SENSOR`，机制实验也能写出 H-A/H-B；但两者之间没有强制的“证据上限”字段。研究者仍可能把 26% → 23% 写成 H-B 的早期 FJ，或者将“行业内销 +1%”与公司收入 -9% 计算为公司份额变化。

这会产生两种材料性误判：

1. `SENSOR` 被误升为可结算竞争证据；
2. `UNKNOWN` 混合了“缺原始数据”“口径不可比”“机制尚无分歧”和“未来尚未到期”，使下一步可能继续写叙事而非取得正确资料。

根因：`REASONING + ACQUISITION_MODULE`。经济影响是渠道竞争、normal owner cash 和永久损失判断会在证据不足时被错误收窄。

## 4. 流程修改

新增两项约束：

1. 每份来源和每个机制观察都要声明 `evidence_ceiling`：`CONTEXT_ONLY`、`MECHANISM_DISCOVERY`、`COMPARATIVE_CANDIDATE` 或 `SETTLEMENT_ELIGIBLE`；低于最后一级不得进入冻结 FJ 或结算。
2. 所有未知必须标出原因：`MISSING_OBSERVATION`、`MEASUREMENT_MISMATCH`、`MECHANISM_NONDIAGNOSTIC`、`NOT_YET_DUE` 或 `PIT_BLOCKED`。不同原因对应不同下一步，而不是统称 UNKNOWN。

## 5. 修改后复跑

| 观察 | 身份 | 证据上限 | 未知原因/下一步 | 对 H-A/H-B 的作用 |
|---|---|---|---|---|
| 线上零售额份额转述 | `SENSOR` | `MECHANISM_DISCOVERY` | `PIT_BLOCKED`：需要原始 provider release/query。 | 仅提示要检查渠道/价格带；不支持任一方。 |
| 行业“内销”+1% | `SENSOR` | `CONTEXT_ONLY` | `MEASUREMENT_MISMATCH`：先确认 transaction point。 | 不可与公司收入相除，也不裁决。 |
| 公司收入和毛利 | `FACT` | `COMPARATIVE_CANDIDATE` | `MECHANISM_NONDIAGNOSTIC`：缺同分类量价/费用边界。 | 双方共有事实。 |
| 表观 OCF 上升 | `FACT` | `MECHANISM_DISCOVERY` | `MISSING_OBSERVATION`：保证金、回款和维持投入尚未同池。 | 不能进入 owner-cash 结论。 |

复跑的正确输出为：`UNDIFFERENTIATED / ACQUISITION_REQUIRED`。流程没有产生概率、报告、估值、股价解释或正式公司判断；下一步只是一项明确的原始行业面板/公司 bridge 请求。

## 6. 迭代裁决

`MODIFY → RETEST_PASSED`：修改后的模板迫使每项材料说明能支持到哪一层，也把不同类型的未知转成不同研究动作。该干跑只证明流程在一个合成压力情境中不易误升级；尚未证明它在真实 PIT episode 中能提高判断准确性。
