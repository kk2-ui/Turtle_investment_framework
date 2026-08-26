# 中国水泥 H1：首个 Enterprise Judgment V2 真实训练读出

> 状态：`REAL_SAMPLE_CREATED + REAL_FEEDBACK_TURN_COMPLETED`
> 边界：真实历史公司与官方年报；`E0/E1 + J2 Teaching`，不是 Comparative、估值或投资建议。

## 这轮产生了什么

行业块冻结了五家 H1 公司（海螺 `CN:600585`、华新 `CN:600801`、冀东
`CN:000401`、青松建化 `CN:600425`、福建水泥 `CN:600802`）和六个按披露日期
生成的 PIT cutoff。所有五家公司在每个快照都保留在风险集中；这只表示静态官方材料
可观察，**不是**幸存、经营质量或投资适格结论。

在这个完整 E0 背景之上，冻结了一个 E0 context episode 和三个 E1 enterprise
reconstruction episode，并以 20 条全量公司—cutoff 转换名单固定了后续样本顺序。
两条与已完成 E1 精确绑定的转移组成最小 outcome 队列。缺 H2、完整同行、公司级行动
或 Comparative 没有阻断这些工作。

名单的有序 projection 还以 `04_pre_outcome_roster_freeze.json` 绑定到 pre-outcome
commit。任何在结算时的重排、即使重新编号为连续 rank，也不能通过 outcome validator；
这避免后来结果改变首先被揭示的 transition。

## 投资者此刻能学到的东西

| 企业/层次 | 可保留的判断 | 不能提升为的结论 |
|---|---|---|
| 行业 E0 | 五家都是不同区域交付市场中的上市公司合并口径水泥对象；区域、控制与报告边界的差异必须保留。 | 统一价格周期、统一客户反应，或任何一家公司是另一家的对照组。 |
| 海螺 E1 | FY2016 的产品/经营与审计现金流量表可在相同 listed-consolidated 边界下重建；其后 FY2017 经营现金净额由独立 custodian 按合同观察。 | owner cash、管理层行动效果、资本配置优劣或永久损失概率。 |
| 华新 E1 | FY2016 年报披露的 15 家工厂收购批准使“跨期合并口径是否连续”成为首要测量问题。 | 将后续合并口径的变化当成持续经营改善、收购效果或管理层能力。 |
| 冀东 E0 archetype | 重组与金隅合资使报告范围本身成为后续比较的条件。 | 把它从风险集中删除，或用重组前后总量直接比较经营质量。 |
| 青松建化 E0 | 报告所述区域产能/竞争压力是行业背景；产品、销售和 D3/D4 有清晰会计边界。 | 用区域背景推出客户、定价、竞争优势或行动因果。 |
| 福建水泥 E0 archetype | 福建区域生产和销售字段可保留为公司状态背景。 | 对渠道、客户黏性、适应能力或资本回报作无来源判断。 |

## 已揭示的反馈，以及它怎样改变下一次研究

1. 华新 `2017-04-12 → 2018-04-22`：独立 outcome custodian 在 FY2017 官方年报
   第 125 页发现本期获得控制权的合并范围变化。因此唯一目标 cell 被结算为
   `MEASUREMENT_MISMATCH`，而不是好或坏的经营结果。下一 cutoff 的新增要求是：先分别
   定义收购前、收购后的 listed-consolidated 经营边界，再寻求连续性判断。该 mismatch
   只把关联的 perimeter 与 operating claims 降为 `RESEARCH_AGENDA`；同 episode 的 cash
   claim 保持其原有会计边界权限。
2. 按冻结队列继续到海螺 `2017-04-12 → 2018-04-22`：custodian 在 FY2017 官方年报
   第 84 页记录合并经营活动产生的现金流量净额为 `RMB 17,363,026,840`。这只观察到
   同一会计边界的现金字段；下一 cutoff 的工作顺序因而改为先检查审计合并现金流量表，
   再看任何非合并口径的现金披露。

这两个反馈分别说明了训练闭环的两个行为：测量不匹配被保留、没有被删样本或伪造成负面
结果；可直接测量的会计现金字段被保留、但没有扩写成 owner cash 或管理评价。

## 仍然未知，且保持未知

- 五家公司都没有从此 H1 年报包中重建出“方案—承诺—执行—适应”的完整管理层决策序列；
  因而全为 `INSUFFICIENT_EVIDENCE`，而不是“没有行动”。
- 客户订单、留存、价格/数量/组合分解、同行反事实、资本回报归因、杠杆承受力，以及普通股
  永久损失路径均未由本 block 建立。
- 华新和冀东的 perimeter bridge 尚未获得；任何经营、现金或竞争比较都须先受这一条件限制。

## 权限状态

本样本只产生 `INDUSTRY_CONTEXT`、企业状态重建、`TEACHING_ONLY` 机制视图和下一期
`RESEARCH_AGENDA`。它没有 H2 action-first Comparative、最终同行 panel、方法冻结、
R-61/R-103、CJO、估值、黄金报告或投资授权；所有 read model 都明确输出
`investment_authorization = NOT_AUTHORIZED`。
