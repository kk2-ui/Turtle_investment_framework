# Phase 08 Q1.1-F 02669 revision judgment content review

> 日期：2026-08-11（Asia/Shanghai）
> reviewer：`/root/q1_02669_revision_content_reviewer`
> 结论：`JUDGMENT_CONTENT_REVIEW_PASS`
> 独立内容审查状态：`JUDGMENTS_CONTENT_ACCEPTED`

## 1. 接受对象与边界

- `research/02669/q1_1_f_revision_20260811/numeric_inputs.json`
- `schemas/q1_02669_revision_numeric_inputs.schema.json`
- 已独立接受且供上述判断使用的新增 facts

本工件接受上述判断内容进入 calculation 阶段，不接受未来 `numeric_results.json`、报告数值、买入价或报告正文。本 reviewer 未修改 inputs、schema、results 或正文。

## 2. 内容判断接受

- **公司特定 EPV 桥。** `1828.109 - 136.365 + 69.217 - 120.233` 后按 25% 税率形成 `1230.546` 百万元税后经营盈利。该桥从中海物业 FY2025 的收入规模、15% 毛利率、正向其他收益、折旧摊销及资本投入逐项构造，并保留 ECL 与公允价值损失，没有用行业模板或目标价格反推经营分子。
- **维护投入。** 在发行人没有披露 maintenance/growth split、且模型不给有机增长或积极再投资价值信用时，以 PPE 与无形资产 additions 合计 `120.233` 百万元作为维护投入上沿是具名且保守的选择；`69.217` 百万元折旧摊销仅为下沿诊断，不与上沿重复扣减。
- **ROU 与 lease。** ROU 折旧留在经营利润，ROU additions 不再进入维护投入，lease liability 仅在普通股权益桥作为 senior claim 扣一次，不存在 ROU 经营成本、资本投入与融资索取权的重复消费。
- **NCI。** EPV 分子保持 consolidated 口径，不再扣 NCI profit；NCI claim 以 `10.730 / 12%` 资本化后在 ordinary-common bridge 扣一次，账面 NCI 只作诊断，不与资本化 claim 双扣。
- **风险归宿。** 利润率与 ECL 已归入经营盈利重置，营运资本和现金可实现性归入 70% owner-cash conversion，剩余 duration、续约、担保及治理风险归入 12% 资本成本；同一核心风险未同时通过多个主参数重复惩罚。正式零衰减也避免在已经重置经营盈利后再次扣同一历史恶化，进一步恶化保留为反情景。
- **现金三层诊断。** 主 EPV cash addback 为零；上市公司现金 `27.854` 百万元及集团现金扣受限现金 `6257.898` 百万元均只作可达性诊断，不平均、不进入 terminal，也不冒充普通股可分配现金。
- **分配与留存。** 年度主分配 `550` 百万元由 HKD0.19 DPS、股数、RMB/HKD 0.90 及 2.06% haircut 支撑，并同时通过 FY2025 与 normalized owner cash coverage 检查；`410.0337` 百万元仅是 30% payout 的下压情景，不进入主 XIRR。`1230.546 x 70% = 550 + 311.3822` 的现金归宿闭合，未分配部分不获 terminal cash credit。
- **税费与摩擦。** 25% 经营税率、20% 股息税、10% 正资本利得税、买卖费用与印花税、换汇价差、股息收取摩擦及逐次费用均被具名纳入；经营税与投资者层税费作用于不同层次，没有重复扣减。
- **反目标拟合。** 旧结果或旧价格没有进入 EPV 分子、分配、资本成本、市场确认、税费或 XIRR 的输入选择。10% 仅作为完成正式现金流后反解最高买入价的 hurdle。结果接近旧 `2.27` 本身不构成拟合证据；相近结果可以由同一公司的零增长、约 550 百万元分配及 12% 成本等经济约束自然产生。

因此，EPV 主路由、NAV 诊断、GG `UNKNOWN_DIAGNOSTIC`、零增长与零积极再投资信用，以及正式 3/5 年回报所需的判断边界，在内容上可以进入独立计算。

## 3. 非阻断 P2

允许 judgment owner 仅同步以下状态措辞，不改变任何值、公式、范围、来源或判断：

- `CAPITAL_COST_SELECTED` rationale 中的 “If the EPV numerator is later closed” 和 “currently blocked EPV” 应同步为 EPV 已闭合且可计算的当前状态。
- `DISTRIBUTION_LOW_PRESSURE` rationale 中的 “not admitted to the blocked main XIRR” 应改为 “stress not admitted to the main XIRR”。

这两处是陈旧状态文字，不构成 P1，不影响 `JUDGMENTS_CONTENT_ACCEPTED`，无需再次内容复审。
