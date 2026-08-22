# R-78｜Ford 2006 Way Forward：多层时钟结果教学结算

状态：`ARCHIVED_EX_ANTE_TEACHING / OUTCOME_RESOLVED_WITH_BOUNDARY_LIMITS / NO_PRIMARY / NO_SELECTION_SCORE / NO_COMPANY_CONCLUSION`。

本文件在 [01 pre-outcome enterprise-system freeze](01_pre_outcome_enterprise_system_freeze.md) 完成后才读取其中预登记的 SEC 结果来源。它只结算已冻结的 D1--D5，不能把后续公众对 Ford 的总体印象、股票价格、回报或未登记年份补进来。

## 1. 读取边界与来源

| source | 服务的预登记时钟 | 读取内容 | 未读取／未使用 |
|---|---|---|---|
| [2006 Q1 Form 10-Q](https://www.sec.gov/Archives/edgar/data/37996/000003799606000043/body10q050806.htm)，filed 2006-05-08，`0000037996-06-000043` | D1 的早期实施；D2--D4 的早期方向 | Note 4、North America results、Automotive operating-related cash reconciliation。 | 任何价格、回报或后续报道。 |
| [FY2008 Form 10-K](https://www.sec.gov/Archives/edgar/data/37996/000114036109005071/form10k.htm)，filed 2009-02-26，`0001140361-09-005071` | D2--D4 的计划时点终局窗口 | U.S. combined market-share table、Ford North America result bridge、Automotive cash reconciliation、segment scope/impairment note。 | 2009 以后恢复、股价、回报及“谁最终胜出”叙事。 |

两个来源均为 Ford 向 SEC 提交的一手披露。它们不自动提供因果识别：每一条结算仍受冻结的同口径、责任单元与禁止代理规则约束。

## 2. 分层结算

| 时钟／claim | 可观察结果 | 结算 | 为什么不能外推 |
|---|---|---|---|
| **D1** `R78-D1-EXIT-IMPLEMENTATION` | Q1 10-Q 记载 St. Louis Assembly 已在该季度闲置，Atlanta 计划于 2006Q4 闲置；Twin Cities 与 Norfolk 计划于 2008 闲置。FY2008 10-K 记载北美雇员由 2007 年的 9.4 万降至 2008 年的 7.9 万，已关闭的设施不再计入运营设施。 | `IMPLEMENTATION_OBSERVED / FULL_PLAN_NOT_DUE`。 | 14 个设施及 2012 人员目标尚未全部到期；实施不是客户、利润或现金恢复。 |
| **D2** `R78-D2-CUSTOMER-COMPETITION` | Q1 10-Q 说北美销量／份额较弱。FY2008 10-K 的 Ford/Lincoln/Mercury 美国车卡合并份额为 14.2%，低于 2006 年 16.0%和 2005 年 17.0%；但同一披露明确该表含 retail 与 fleet，且 2008 fleet 下滑部分是公司计划减少日租车销售。 | `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`。 | 合并份额下降不能区分终端客户接受恶化与预期的 fleet 渠道退出；它不能裁决 H-A 或 H-B。 |
| **D3** `R78-D3-UNIT-ECONOMICS` | Q1 的 North America decline 包含 Way Forward 退出项目、较高 incentive／leasing-fleet mix、较低份额与加速折旧，同时也有部分人员／产能调整节约。FY2008 10-K 将北美结果的恶化同时归于不利 volume/mix、$5.3bn 固定资产减值、较低净价格，部分由约 $3.5bn 有利成本变化抵消；披露还说明燃油偏好转换、需求下滑、商品成本和信贷危机改变了现金流预期。 | `MIXED / H-C_MATERIAL / NOT_DIAGNOSTIC`。 | 这说明成本削减并未自行穿透 volume/mix 与价格，但不能把 2008 宏观冲击、产品偏好变化和会计减值净化为“2006 退出行动”的单独因果结果。 |
| **D4** `R78-D4-CASH-ORIGIN` | Q1 Automotive operating-related cash flow 为 -$0.7bn（2005Q1 +$0.9bn），其中应收、存货与应付变动 -$0.4bn，人员／Jobs Bank 现金影响 -$0.4bn。FY2008 Automotive operating-related cash flow -$19.5bn（2007 +$0.4bn；2006 -$5.6bn），表中又同时有全球 Automotive 的营运资本 -$2.9bn、Ford Credit upfront payments -$2.9bn、人员计划现金 -$0.7bn、出售/融资与其他变化。 | `RESPONSIBILITY_SCOPE_MISMATCH / NOT_DIAGNOSTIC`。 | 该表已把 Ford Credit 和某些其他项目区分出来，却仍是全球 Automotive 而非 Ford North America 退出单元；不能由它判断该退出动作的现金转换或 owner cash。 |
| **D5** `R78-D5-CAPITAL-RETURN` | 关闭、人员与资产减值成本可见；北美退出责任单元的税后增量现金、维持资本及可行替代仍无预冻结可比合同。 | `CAPITAL_RETURN_UNKNOWN`。 | 计划盈利目标、总公司流动性和后来的经营叙事都不能补这个反事实。 |

## 3. 竞争机制的实际信息量

```text
D1 观察到部分实施
  ├─ 不能推出 D2
  ├─ 不能推出 D3
  └─ 不能推出 D4 或 D5

D2 合并份额（含 fleet） ── 渠道定义混合 ──> 不可诊断
D3 成本变化 + volume/mix/价格/宏观共同作用 ──> H-C 材料性 ──> 不可诊断
D4 全球 Automotive 现金 ── 责任单元不符 ──> 不可诊断
D5 缺反事实资本边界 ──> UNKNOWN
```

因此，本案不产生 `SUPPORTS_PRIMARY`、`SUPPORTS_RIVAL` 或“管理层正确／错误”结论。唯一可保留的是更窄的企业判断：**被确认的退出实施和成本行动，仍不足以证明客户恢复、正常单位经济、现金转换或资本回收。**

## 4. 复盘：产生了什么可迁移的训练约束

根因：`REASONING + DATA_COVERAGE`。冻结虽避免了总利润和总现金代理，却仍把会受渠道策略影响的合并份额用于客户时钟，并允许全球 Automotive 现金承担北美退出单元的 D4。

- **经济影响：** 若把这些口径直接读成“客户失败”或“退出现金恶化”，会材料性误判正常盈利、owner cash 与管理决策质量。
- **缺失事实：** 同定义的 retail 与 fleet 分拆客户指标；北美退出责任单元的营运资本／现金桥；足以把成本、价格、volume/mix 与宏观冲击区分开的预登记观察。
- **禁止假设：** 合并市场份额等于终端客户接受；成本削减等于经济重置；全球 Automotive 现金等于北美退出现金；D1 实施等于 D2--D5；后来结果能够填补 D5。
- **可执行处置：** 将本案的三项约束写入 [03 learning review](03_learning_review.md)，下一家不同公司的冻结必须在结果读取前实际采用它们；否则该卡不计为 R-78 的 replication。
- **验收：** 下一卡需 (1) 把 D2 的 retail／渠道退出 cohort 分开，(2) 同时冻结 `volume_or_utilization / price_or_mix / unit_cost / channel_cost`，(3) 证明 D4 source scope 等于 D1 责任单元，或预注册 D4 为 `UNKNOWN`。三项中任一缺失，即不得由单一结果宣布机制成立。
