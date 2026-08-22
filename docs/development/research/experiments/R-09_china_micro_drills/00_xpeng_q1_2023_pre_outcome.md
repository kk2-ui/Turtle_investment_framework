# R-09 中国机制判断微演练：XPeng Q1 2023 车辆毛利

状态：`FROZEN_FOR_REVIEW / HISTORICAL_SELF_REPLAY / NO_PRIMARY / OUTCOME_UNREAD`  
训练模板：[机制判断微演练](../../../../../templates/research_mechanism_micro_drill.md)

这是一条中国市场的单箭头训练卡，不是 XPeng 的公司结论、估值、价格、回报或 Turtle 命中。当前研究者/模型无法排除外部记忆，故最多检验流程与判断动作，不进入准确率或校准。

## 1｜训练边界

- drill ID：`R09-XPEV-2023Q1-VEHICLE-MARGIN`。
- 核心训练域：`CHINA`；角色：`FOCAL / STANDALONE`。
- 机制域 × 当前状态 × 竞争叉：`UNIT_ECONOMICS × margin compression × temporary operating reset / persistent demand-price stress`。
- cutoff：`2023-06-09T23:59:59-04:00`。
- 唯一结果前原件：[XPeng 2023 Q1 Form 6-K exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1810997/000119312523152920/d489409dex991.htm)，随同 2023-05-24 Form 6-K 提交；公司在中国经营并同时在 SEC/HKEX 披露。
- 第一遍事实包 locator：该 exhibit 中仅下列不含归因/指引理由的经营和财务表行：`Key Operating Data` 的 `2023Q1...Total deliveries`；`Total deliveries were 18,230`；`Total revenues were RMB4.03bn`；`Vehicle sales were RMB3.51bn`；`Gross margin was 1.7%`；`Vehicle margin ... was negative 2.5%`；`Total deliveries were 7,079 vehicles in April 2023`。
- 事实包准备方式：`FROZEN_STRUCTURAL_EXTRACT`。抽取规则预先排除含 `primarily / mainly / due to / expect / guidance / believe / comment / said / announce / launch / because / attribute` 的行；本卡不使用被排除的行。
- 结果期 source metadata（已登记、未打开）：SEC 2023-08-18 Form 6-K `0001193125-23-215945`，其档案索引仅登记 `d528791d6k.htm`、`d528791dex991.htm`、`d528791dex992.htm`；Q2 result body、exhibit 内容、数字与管理层解释均 `UNREAD`。
- 训练等级：`HISTORICAL_SELF_REPLAY / CONTEXT_SEPARATION_NOT_ASSURED`（不能排除模型的外部记忆）；不产生 Turtle 命中。

## 2｜第一遍：事实层机制

**决定性问题**：2023 Q1 车辆毛利已为负，而交付、车辆销售收入与总收入均环比下降；下一季度这种负的单位经济是短期经营/产品过渡，还是竞争与需求压力的持续表现？

**共同事实**：Q1 交付 18,230、环比 -17.9%；车辆销售收入环比 -24.6%；车辆毛利 -2.5%，低于 Q4 2022 的 5.7%；4 月交付 7,079。双方都须解释“量和单位经济同时走弱”的状态。

| 机制 | 状态 → driver → 中间变量 → 经营后果 | 该机制最怕的观察 | 首先分叉的观察 |
|---|---|---|---|
| H-A：短期经营/产品过渡 | 当前量与产品/生产衔接短期失衡 → Q2 交付恢复、固定成本/组合被吸收 → 单车经济恢复 → 车辆毛利回正。 | 交付改善但车辆毛利仍为负，或交付继续低迷。 | Q2 车辆毛利是否至少为 `0%`。 |
| H-B：持续需求—价格压力 | 弱需求/竞争定价 → 量价不能覆盖成本 → 即使交付短期波动，单位经济仍受压 → 车辆毛利保持负。 | 在没有凭借一次性会计或口径变化的情况下，车辆毛利回到非负。 | Q2 车辆毛利是否仍低于 `0%`。 |

本卡没有 cutoff 前、对两方有方向性含义的独立选择证据，故为 `NO_PRIMARY`；`0%` 只是“车辆销售不再产生毛亏”的非嵌套经济阈值，不是对下一季数字的任意乐观预测。

## 3｜第二遍：原件解释攻击（已执行，结果仍未打开）

见[第二遍记录](01_xpeng_q1_2023_second_pass.md)。此前排除的管理层评论、成本/组合归因与 Q2 指引均已逐项攻击、但没有改变第 2 节冻结的 H-A/H-B 或结果合同。它们不能新增一个可结算分歧，故本卡保持 `NO_PRIMARY` 的机制探针，绝不升级为主路径选择。

## 4｜冻结结果合同

- 主观察：Q2 2023 `Vehicle margin`，定义为 vehicle sales 的 gross profit/loss percentage。
- H-A 区域：`vehicle margin >= 0%`。
- H-B 区域：`vehicle margin < 0%`。
- 预期结果期一手来源：上列 2023-08-18 Form 6-K 的 result exhibit；只接受同一发行人披露的 `Vehicle margin` 标签及公式/定义。
- 禁止替代：总收入、交付量、总毛利、non-GAAP 利润、价格、回报、管理层解释或之后季度指标。
- 若未披露相同定义/公式：`MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`。
- 允许打开结果包的前置动作：先完成本卡第二遍解释攻击并冻结；结果期只读取上述 source body，以原文片段结算。

## 5｜预先承诺的复盘动作

| 结果 | 本卡记录 | 下一张中国微演练的改变 |
|---|---|---|
| `A_ONLY` | 仅支持“单位经济可在交付恢复前后修复”的这条箭头；不判公司总机制。 | 下一题把交付与车辆毛利的时序拆开，避免以销量替代单位经济。 |
| `B_ONLY` | 仅支持“负单位经济持续”的这条箭头。 | 下一题在冻结前增加价格/组合或成本的同口径观察，避免将低毛利笼统称为需求问题。 |
| `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC` | 不裁决任一机制。 | 仅修订结果合同或停用 `vehicle margin`；不得用收入/交付代理。 |
