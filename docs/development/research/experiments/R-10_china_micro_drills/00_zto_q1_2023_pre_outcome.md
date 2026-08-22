# R-10 中国机制判断微演练：ZTO Q1 2023 网络效率与单件收入

状态：`FROZEN_FOR_REVIEW / HISTORICAL_SELF_REPLAY / NO_PRIMARY / OUTCOME_UNREAD`

训练模板：[机制判断微演练](../../../../../templates/research_mechanism_micro_drill.md)；上一条训练的输入约束来自 [R-09 学习记录](../R-09_china_micro_drills/02_xpeng_q1_2023_outcome_resolution.md)。本卡只训练经营机制，不形成中通的公司、估值、价格、回报或投资结论。

## 1｜训练边界

- drill ID：`R10-ZTO-2023Q1-NETWORK-UNIT-ECONOMICS`。
- 核心训练域：`CHINA`；角色：`FOCAL / STANDALONE`；不同于 R-09 的机制域为 `UNIT_ECONOMICS × network-cost efficiency / revenue-yield pressure`。
- cutoff：`2023-08-16T23:59:59-04:00`。
- 唯一结果前原件：[ZTO Q1 2023 Form 6-K exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1677250/000110465923062034/tm2315927d1_ex99-1.htm)，2023-05-18 提交。
- 第一遍事实包 locator：该原件中的经营及财务表行 `Revenues`、`Gross profit`、`Parcel volume`、`Sorting hub operating cost`、`Total cost of revenues`。抽取规则排除含 `primarily / mainly / due to / expect / guidance / believe / comment / said / announce / launch / because / attribute` 的文本；不用被排除的管理层解释。
- 结果期 source metadata（已登记、未打开）：SEC 2023-08-17 Form 6-K `0001104659-23-092818`，档案索引只登记 `tm2324033d1_6k.htm`、`tm2324033d1_ex99-1.htm` 及图片附件；Q2 result body、数值和解释均 `UNREAD`。
- 训练等级：`HISTORICAL_SELF_REPLAY / CONTEXT_SEPARATION_NOT_ASSURED`；不得计入命中率、概率或校准。

## 2｜第一遍：事实层机制

**决定性问题**：在包裹量增长快于收入、单件收入下降的同时，Q1 成本收入比显著改善；这反映网络效率可抵御单件收入压力，还是一个不可持续的成本/价格组合？

**冻结事实（仅源表行）**：

- 收入 RMB8,983.2m，同比 +13.7%；包裹量 6,297m，同比 +20.5%；由这两个同表指标计算，收入/件约 RMB1.43，低于上年约 RMB1.51。
- 毛利 RMB2,523.4m，同比 +55.8%；同表计算毛利率约 `28.1%`，上年约 `20.5%`。
- 总成本/收入从 `79.5%` 降至 `71.9%`；sorting-hub operating cost/收入从 `23.8%` 降至 `22.4%`。

前导分叉已经存在但方向相反：**收入/件下降**是 H-B 的压力点；**成本收入比同步大幅改善**是 H-A 的压力点。这是 R-09 后刻意新增的、与主结果不同的单位经济观察。

| 机制 | 状态 → driver → 中间变量 → 经营后果 | 该机制最怕的观察 | 结果与前导合同 |
|---|---|---|---|
| H-A：网络效率可抵消单件收入下降 | 件量增长 → 枢纽/线路利用率和单位履约成本改善 → 成本收入比保持低位 → Q2 毛利率不低于 Q1。 | Q2 在件量继续扩张时成本收入比反弹、毛利率低于 Q1。 | Q2 `gross profit / revenues >= 28.1%`，且 `sorting-hub operating cost / revenues <= 22.4%`。 |
| H-B：单件收入压力及成本改善不可持续 | 单件收入下降反映价格/产品结构压力 → Q1 成本改善无法持续抵消 → 成本收入比反弹 → Q2 毛利率低于 Q1。 | Q2 单件收入仍受压但成本收入比继续改善，毛利率不低于 Q1。 | Q2 `gross profit / revenues < 28.1%`，或 `sorting-hub operating cost / revenues > 22.4%`。 |

`NO_PRIMARY`：当前两个方向性事实彼此冲突，且没有 cutoff 前、独立于公司叙事的观察能裁决“网络效率的持续性”与“单件收入压力的持续性”。这不是数据缺失的掩饰，而是对当前证据强度的判断。

## 3｜冻结结果合同

- 主结果：Q2 2023 `gross profit / revenues`；以公司同一 Q2 表内两项直接相除，按一位小数结算。
- 早期机制结果：Q2 2023 `sorting-hub operating cost / revenues`；同一表内直接相除，按一位小数结算。
- 接受来源：上列 Q2 官方 exhibit 中相同名称的两张/同张损益成本表；结果期必须保留 `revenues`、`gross profit`、`sorting hub operating cost` 三行的原文 locator。
- 不可替代：调整后利润、整体营运利润、包裹量、市场份额、股价、回报、管理层对市场价格的说法，或之后季度数据。
- 若任一分子/分母/口径未披露或名称定义改变：相应观察 `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`，不以相近费用项目补算。

## 4｜第二遍待执行：解释攻击

冻结后才读取 Q1 原件中此前排除的成本、价格、竞争归因与管理层展望。第二遍只能分类 H-A compatible、H-B compatible、共同或不具诊断性；不得改写第 2–3 节的阈值、指标准则或 `NO_PRIMARY`。

## 5｜预先承诺的复盘动作

| 结果形状 | 本卡记录 | 下一张改变 |
|---|---|---|
| 毛利率与枢纽成本同时支持 H-A | 仅支持网络效率这条经营箭头。 | 仍要求检查单件收入持续性，不能把规模效率外推为定价权。 |
| 毛利率与枢纽成本同时支持 H-B | 仅支持成本效率未抵消单件收入压力。 | 下一题把价格/件与成本/件拆开，避免只看毛利率。 |
| 两者分叉或任一口径失配 | `MIXED / NOT_DIAGNOSTIC`。 | 保留主/前导双观察；不凭一个利润率结论选择机制。 |
