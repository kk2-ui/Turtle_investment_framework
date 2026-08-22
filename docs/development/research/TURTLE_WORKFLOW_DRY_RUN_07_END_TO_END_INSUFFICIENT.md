# 研究流程端到端干跑 07：证据不足时能否正确停止？

状态：`METHOD_PREPARATION_TEST / SYNTHETIC / NO_COMPANY_RESEARCH`  
范围：一次完整模拟，不使用真实公司、真实投资结论或真实行业数据。目标是检验模板能否共同把“无法判别”转化为明确停止与资料请求。

## 1. 迭代卡

| 字段 | 模拟填写 |
|---|---|
| 方法盲点 | 容易把供应商转述和跨交易点行业数直接升级为竞争结论。 |
| 训练能力 | 测量辨别 + 机制辨别。 |
| 新增区分 | 区分 `SENSOR`、可比较事实和可结算结果。 |
| 经济边界 | 竞争持续期、正常盈利与 owner cash。 |
| 实验边界 | 一个虚拟耐用消费品公司、一个历史 cutoff；不读结果期。 |
| 基线 A | 线上份额下行 + 收入弱于行业 = 广泛竞争恶化。 |
| 新方法 B | 先识别交易点、来源谱系、证据上限和 A/B 的独有结果区域。 |
| 退出条件 | 若没有 `SETTLEMENT_ELIGIBLE` 的 A-only/B-only 信号，停止公司分析并提出 acquisition task。 |
| 前瞻表达 | `NO_FORECAST / NO_PROBABILITY`。 |

## 2. 来源观察卡摘要

| `lineage_id` | 观察角色与身份 | 证据上限 | 未知原因 | 正确用途 |
|---|---|---|---|---|
| L1 | 公司年报转引的线上零售额份额：`SENSOR / STATE` | `MECHANISM_DISCOVERY` | `PIT_BLOCKED`：原始 provider release/query 不可得。 | 仅生成渠道/价格带问题。 |
| L2 | 公司年报的国内收入与毛利：`FACT / OUTCOME` | `COMPARATIVE_CANDIDATE` | `MECHANISM_NONDIAGNOSTIC`：双方均可解释。 | 共同当前事实。 |
| L3 | 行业文章的“内销 +1%”：`SENSOR / STATE` | `CONTEXT_ONLY` | `MEASUREMENT_MISMATCH`：未知 sell-in/sell-out/shipment。 | 不可与 L2 相除。 |
| L4 | OCF 上升及保证金到期收回：`FACT / OUTCOME` | `MECHANISM_DISCOVERY` | `MISSING_OBSERVATION`：回款、维持投入和营运资本未同池。 | 不进入 owner cash。 |

没有来源达到 `SETTLEMENT_ELIGIBLE`；不同文字若转引 L1，均折叠，不增加支持数量。

## 3. 机制实验

共同终局：未来三年内，国内竞争位置是否仍支持可持续的正常盈利与现金转换。

| 信号 | H-A：渠道/价格带重配 | H-B：广泛竞争恶化 | 证据上限 | 结果区域 |
|---|---|---|---|---|
| 当前线上份额转述 | 可相容 | 可相容 | `MECHANISM_DISCOVERY` | 无 A-only/B-only。 |
| 当前收入、毛利 | 可相容 | 可相容 | `COMPARATIVE_CANDIDATE` | `MIXED`。 |
| 当前行业内销数 | 不可比较 | 不可比较 | `CONTEXT_ONLY` | `NEITHER`。 |
| 未来同 provider 的全渠道/价格带相对位置 | 可成为 A-only 信号 | 可成为 B-only 信号 | `ACQUISITION_REQUIRED` | 只有取得原始面板后才可设计。 |

因此机制状态必须是 `UNDIFFERENTIATED`；没有 FJ、概率、估值或报告结论。

## 4. 红队

红队发现：

1. L1 可能只反映低价线上价格带，不能代表全渠道；
2. L3 与 L2 交易点、单位和期间不同；
3. L4 含一次性保证金变动，不能作 owner cash；
4. 任何“公司仍排名第一”或“毛利稳定”的补充文字仍处于双方共同区域。

红队没有选择 H-A 或 H-B；它只确认基线 A 是跨口径推断。

## 5. 复盘与退出

| 对象 | 正确裁决 |
|---|---|
| 方法 B（证据上限 + unknown taxonomy + result regions） | `RETAIN`：阻止了基线 A 的跨口径升级。 |
| 虚拟公司研究状态 | `UNDIFFERENTIATED / ACQUISITION_REQUIRED`。 |
| 资料请求 | 同 provider、同版本的品牌×渠道/价格带零售 panel，或公司同口径量价/费用/现金 bridge。 |
| 后续动作 | 停止该公司分析；不以更多同类转述替代资料请求。 |

## 6. 干跑发现的流程缺口与修订

旧学习复盘模板只有一个“裁决”字段，可能把“方法 B 有效”误写成“虚拟公司已得出结论”。因此模板和操作流程新增双层关闭：**方法裁决**与**对象研究状态**必须分开，后者可保持 `UNDIFFERENTIATED`。这保证流程奖励的是更好的停止，而不是更快的公司结论。

## 7. 复跑结论

`MODIFY → RETEST_PASSED`：在整个闭环中，所有材料都被降到其可支持的上限，且最终能明确停止。干跑只验证流程纪律，不验证任何公司判断或论文方法的真实预测效力。
