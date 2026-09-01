# 五阶段完成验收：报告自治与行业经验 2×2（V4）

## 最终状态

本 campaign 的五阶段闭环已完成。正式实验版本为 **V4**；V1、V2、V3 均因工程和合同交付问题被明确作废并保留审计轨迹，不能与 V4 混合解读。

本文件记录的是研究流程、约束与效用结算，不构成价格、回报、估值或投资行动结论。

## 五阶段验收

| 阶段 | 交付物 | 状态 | 可接受的结论 |
|---|---|---|---|
| 1. acquisition 扩展 | ordinary-equity 现金可达区间、现金—价值桥、经济组件/敏感性约束及独立工程审阅 | `COMPLETED` | 现金和 bounded delta 不再能以自述或自由复制的数字进入价值桥；缺事实时保留 `UNKNOWN`/下限。 |
| 2. 未见样本冻结 | CN:000935（四川双马）截至 2018-04-30 的预注册、共同源包、官方 fact register 与独立样本审阅 | `COMPLETED` | 样本在结果读取前机械选择；共同源事实中性、cutoff-safe。 |
| 3. 2×2 执行 | Baseline、Expert-only、Industry-only、Combined 四个 `fork_turns=none` fresh Agent 的 V4 task、raw response、bound Episode 与首次 reader report | `COMPLETED` | 四臂证据和预算相同；仅 Enhanced 对应臂得到允许的派生方法资产。 |
| 4. 匿名审阅与结果结算 | V4 匿名 packet、结果前审阅、隔离 custodian 的官方字段级观察、结果后 2×2 裁决 | `COMPLETED` | 先盲审、后揭示映射、再结算；没有用价格或后验资料挑样。 |
| 5. 修复和独立复验 | cash/fact register binding、derivation-v2、anonymous-label 防泄露、定向测试和最终工程复审 | `COMPLETED` | 原工程审阅的三个材料阻断均已关闭。 |

## 正式 V4 的效用结算

结果后审阅的预注册 estimand 为：

| 比较 | 结算 |
|---|---|
| `A01 Industry-only − A00 Baseline` | `INCONCLUSIVE_DATA` |
| `A10 Expert-only − A00 Baseline` | `LEFT_MATERIALLY_WORSE` |
| `A11 Combined − A10 Expert-only` | `LEFT_MATERIALLY_BETTER` |
| `A11 Combined − A01 Industry-only` | `NO_MATERIAL_DIFFERENCE` |

实质原因不是收益预测的好坏，而是边界纪律：A10 在缺少目标责任边界 OCF、维护资本、营运资本、债务服务和普通股现金桥时，把 owner cash 从未决提升为条件性主要输入。官方结果窗口没有补足该桥。A11 保留了未决状态，因此相对 A10 更好；这不能被外推成“行业经验普遍提升”或“人工纠偏普遍提升”。

FY2020 的锁定首份完整年报已经取消。既定规则禁止用后续更新版替代，故该处为 `SOURCE_MISMATCH`；FY2021--2022 又发生法律实体和分部边界断裂。这些是本次行业路径无法强结算的 `DATA_COVERAGE` / `ACQUISITION_MODULE` 限制，不能用合并现金、出售收款或模型推断补齐。

权威裁决见 [结果后效用审阅](final_review_v4/01_POSTOUTCOME_2X2_UTILITY_REVIEW.md)；结果前匿名判断见 [匿名审阅](anonymous_review_v4/01_ANONYMOUS_PREOUTCOME_REVIEW.md)。

## 工程接受与测试

- 最终独立工程复审：`PASS`，见 [复审记录](engineering_review/03_INDEPENDENT_ENGINEERING_FINAL_REREVIEW.md)。
- 定向回归：**213 passed**。覆盖 canonical official fact binding、现金—权益桥、derivation-v2 sensitivity metadata、冻结 v1 replay/新执行拒绝和匿名 arm-token 泄露。
- 全仓回归在本次工作树运行结果为：3,964 passed、8 skipped、27 failed、13 errors。其失败集中还包含未跟踪提示词文件、PDF/行情采集和既有测试期望；其中与 underwriting teaching projection 相连的一项已在 `main` 原样失败。它们并非这次变更的接受依据，也不改变上述 213 项受影响模块的通过结论；未将全仓误报为绿色。
- `git diff --check` 通过。

## 运行约束确认

- 四个执行臂、匿名审阅和隔离 custodian 均为当前 Codex 工作流内的 fresh Agent；未调用 Anthropic、OpenAI、DeepSeek 或任何外部模型 API。
- V4 四臂完成、绑定和匿名审阅之后才开启 outcome custody。
- 只把可验证的流程和边界纪律视为结果；没有用篇幅、字段数、悲观程度或单个正例替代效用证据。

## 可复用的下一步

下一轮不应增加泛化“经验”文字，而应预先选择同时具备连续责任边界经营数据与普通股现金桥的样本。只有在同一预注册 2×2 中能结算公司传导、owner cash 与行动路线时，行业经验的独立增量才可能从 `INCONCLUSIVE_DATA` 变成可识别结论。
