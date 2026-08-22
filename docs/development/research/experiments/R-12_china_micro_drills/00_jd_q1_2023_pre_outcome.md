# R-12 中国机制判断微演练：JD Q1 2023 服务收入结构

状态：`FROZEN_FOR_REVIEW / HISTORICAL_SELF_REPLAY / NO_PRIMARY / OUTCOME_UNREAD`

训练模板：[机制判断微演练](../../../../../templates/research_mechanism_micro_drill.md)。本卡将 [R-11 学习记录](../R-11_china_micro_drills/02_baidu_q1_2023_outcome_resolution.md) 应用于不同中国对象：主结果不再只是分部相对增速，而是“绝对服务收入 + 服务收入份额”两项共同成立。它不是京东的公司、估值、价格、回报或投资结论。

## 1｜训练边界

- drill ID：`R12-JD-2023Q1-SERVICE-REVENUE-MIX`。
- 核心训练域：`CHINA`；角色：`FOCAL / STANDALONE`；机制域为 `DEMAND_AND_MONETIZATION × product-sales / service-revenue mix`。
- cutoff：`2023-08-14T23:59:59-04:00`。
- 第一遍原件：[JD Q1 2023 Form 6-K exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1549802/000119312523141315/d340916dex991.htm)，2023-05-11 提交。
- 第一遍事实包 locator：原件结果/分部表的 `Net revenues`、`Net product revenues`、`Net service revenues`、`JD Retail operating margin before unallocated items`。抽取时不交付含 `primarily / mainly / due to / expect / guidance / believe / comment / said / announce / launch / because / attribute` 的归因文本。
- 事实包准备方式：`FROZEN_STRUCTURAL_EXTRACT / CONTEXT_SEPARATION_NOT_ASSURED`；只作 `HISTORICAL_SELF_REPLAY` 练习。
- 结果事件合同（cutoff 前）：[JD 2023-08-04 board-meeting announcement](https://www.sec.gov/Archives/edgar/data/1549802/000119312523203346/d542883dex991.htm) 明示董事会于 2023-08-15 审议截至 2023-06-30 的季度及中期业绩；发布者 `JD.com, Inc.`；结果事件 `2023 Interim Results Announcement`；允许结果窗口 `2023-08-15–2023-08-25`；预期标签 `Net revenues`、`Net product revenues`、`Net service revenues`。
- 已隔离、不得在冻结前读取：上述 Q2/interim results announcement 的正文、数字、归因、电话会、价格和回报。

## 2｜第一遍：事实层机制

**决定性问题**：Q1 的服务收入既绝对增加、又在总收入中取得更大份额，而产品收入下降；这代表服务化变现开始改变收入结构，还是商品需求走弱造成的暂时组合效果？

**冻结事实**：总收入 RMB243.0bn、同比 +1.4%；产品收入从 RMB204.4bn 降至 RMB195.6bn；服务收入从 RMB35.2bn 升至 RMB47.4bn、同比 +34.5%。服务收入的总收入份额由约 `14.7%` 升至约 `19.5%`，绝对增加约 RMB12.2bn；JD Retail unallocated-items-before operating margin 为 4.6%，上年为 3.6%。双方均须解释“服务份额增加与商品收入下降同时发生”。

| 机制 | 状态 → driver → 中间变量 → 经营后果 | 最怕的观察 | 未来首先分叉的观察 |
|---|---|---|---|
| H-A：服务化变现正在变得更重要 | 服务/物流/平台收入扩张 → 服务收入保持绝对增长并继续获取份额 → 收入结构更少依赖商品销售。 | Q2 服务收入不增长，或在总收入中不再获得份额。 | Q2 服务收入同比增长为正，且服务收入/总收入高于 Q2 2022 的同口径份额。 |
| H-B：商品疲弱造成短期组合抬升 | 产品销售下降 → 服务份额被动上升 → 份额变化未构成持续的服务化变现。 | Q2 服务收入继续绝对增长且份额同比增加。 | Q2 服务收入同比不增长，或服务收入/总收入不高于 Q2 2022 同口径份额。 |

`NO_PRIMARY`：服务收入增长、份额变化与 JD Retail 利润率都是当前结果；截至 cutoff 没有能把“服务需求自身更强”与“商品疲弱造成的混合效应”分离的独立前导事实。两条机制都保留为可结算，不以 Q1 的漂亮组合变化选择 H-A。

## 3｜冻结结果合同

- 主结果组：Q2 2023 同表 `Net service revenues`、`Net revenues` 与 Q2 2022 的对应数。
- H-A 区域：`service revenue YoY growth > 0` **且** `Q2 service-revenue share > Q2 2022 service-revenue share`。
- H-B 区域：`service revenue YoY growth <= 0` **或** `Q2 service-revenue share <= Q2 2022 service-revenue share`。
- 接受来源：第 1 节预登记的 JD Q2/interim results announcement；三行标签与分部范围必须同一口径。
- 禁止替代：总收入增长、产品/服务任一单项金额、JD Retail 利润、用户数、管理层解释、业务发布、价格、回报或之后季度资料。
- 若分部范围、净额/总额或收入标签变动，或任一行缺失：`MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`，不得用 GMV、物流订单或第三方零售数据代替。

## 4｜第二遍待执行：解释攻击

冻结后才可读 Q1 原件中关于服务收入、商品需求、供应链/物流与利润率的归因；它们只能被分类为 H-A compatible、H-B compatible、共同或不具诊断性，不得改写双条件结果合同或 `NO_PRIMARY`。

## 5｜预先承诺的复盘动作

| 结果形状 | 本卡记录 | 下一张不同中国对象的改变 |
|---|---|---|
| 两个 H-A 条件均成立 | 仅支持“短窗服务绝对增长且份额增加”。 | 增加服务收入的客户/单位经济前导信号，避免把组合结果等同于持续利润。 |
| 任一 H-B 条件成立 | 只支持“服务化结构在短窗未同时保持绝对与相对改善”。 | 将商品需求与服务需求拆为独立状态，而不是把份额解释为单一机制。 |
| 口径失配 | `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`。 | 下一题优先选择分部定义连续的发行人。 |
