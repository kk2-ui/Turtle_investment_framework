# R-07 状态优先候选 universe：美国餐饮交易恢复（2026-08-21）

状态：`SCREEN_ONLY / NO_SELECTION_CANDIDATE / NOT_A_FLYWHEEL_BATCH / NO_OUTCOME_READ`

本文件只记录截至 `2026-08-21` 可见的一手结果披露如何被筛掉。它不是三家公司的横向研究、行业结论、前瞻冻结或投资结论；未读取任何此后业绩、价格、回报、电话会或二手材料。

## 1. 先定状态格，再读最小原件

本轮空白格不是“餐饮公司”或“资料足够的公司”，而是：

```text
机制域：客户交易 / 需求持续性
当前状态：同店或可比销售转正（或接近转正），但交易量、客流、渠道或特许经营端仍有歧义
竞争叉：可持续的客户交易修复  vs. 由 check、组合、单一渠道或暂时执行因素支撑的表面销售改善
需要的结果：同一公司、同一定义的下一期客户交易 / 客流；不是收入、利润、指引、股价或回报
```

候选 universe 仅由下列截至 cutoff 的三份 SEC 备案 Exhibit 99.1 构成。它不是市场穷尽清单，也不是正式 `judgment_flywheel_sampling` universe：后者必须在 freeze 前有共同、可比较的结果指标与三对象的可能性条件事实链。

| 候选 | cutoff 前的最小一手原件 | 触发的当前状态 | 不读什么 |
|---|---|---|---|
| Chipotle (`CMG`) | [2026-07-29 8-K Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1058090/000105809026000063/cmg-20260729xex991.htm) | Q2 comparable restaurant sales `+2.2%`，由 average check `+1.2%` 与 transactions `+1.0%` 构成；原件称为连续第二季交易量改善。 | 后续季度、指引兑现、价格和回报。 |
| McDonald's (`MCD`) | [2026-08-04 8-K Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/63908/000006390826000067/exhibit991-6302026.htm) | U.S. comparable sales `+0.8%`，由正的 check growth（含 product mix）推动、部分被负的 comparable guest counts 抵消。 | 后续季度、管理层叙事的事后验证、价格和回报。 |
| Domino's (`DPZ`) | [2026-07-20 8-K Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1286681/000128668126000034/dpz-ex99_1.htm) | U.S. same-store sales `+0.1%`，其中 company-owned `+2.1%`、franchise `0.0%`；原件同时给出 supply-chain food-basket pricing `+2.2%`。 | 后续季度、特许经营者结果、价格和回报。 |

这些数字只是该次公司官方披露的描述，不是跨公司同口径事实，尤其不能把 Domino's 的 same-store sales 或 supply-chain food-basket price 改称为顾客交易量。

## 2. 逐项选择筛查

| 候选 | 可运行的竞争机制（仅供筛查） | 看似支持主方的事实 | 为什么仍然没有主路径选择依据 | 裁决 |
|---|---|---|---|---|
| CMG | H-A：交易改善反映可持续的顾客可达性/执行修复；H-B：有限交易回升仍可能是暂时产品、促销或组合变化。 | 第二季交易量继续改善。 | 两方都可在短期内预期连续改善；披露没有一条对 H-A 支持、但对 H-B 方向相反的当前经营事实，也没有由该事实推出的非任意下一期阈值。 | `NO_PRIMARY` |
| MCD | H-A：客流下滑是可修复的执行/可负担性问题；H-B：check/mix 增长掩盖更持续的顾客流失。 | loyalty 销售与活跃用户增长。 | loyalty 指标是跨 70 个市场的聚合，并不等同于 U.S. comparable guest counts；它可与两条机制并存，不能选择 H-A。 | `NO_PRIMARY` |
| DPZ | H-A：company-owned 门店的改善会传导到更广泛的系统交易改善；H-B：公司自营/特许端的分叉反映局部运营差异，顾客需求并未普遍修复。 | company-owned same-store sales 高于 franchise。 | 原件没有相同边界的交易或客流指标，也没有让两方对同一后续指标作相反预测的一手事实；food-basket price 是供给链成本/价格资料，不能冒充顾客需求证据。 | `NO_PRIMARY / NONCOMPARABLE` |

## 3. 为什么它们不能组成 `1 + 1 + 1`

`CMG` 的可结算候选是公司定义的 comparable restaurant transactions，`MCD` 是 comparable guest counts，`DPZ` 此原件只有 U.S. same-store sales。三个名称看起来接近，却没有证明相同的人群、渠道、纳入门店、定义或未来结果 source contract；也没有一个 focal 的已选主路径可供 near miss 与 boundary replication 围绕。

因此本轮不得创建 `case_selection_register` 飞轮 batch、近失效案例、前瞻判断或 outcome package。将三家并列只能帮助发现“销售转正 ≠ 交易机制已经辨别”的入口限制，不能制造跨公司证据、方法胜率或判断训练样本。

## 4. 方法裁决与下一步

- 裁决：`RETAIN / R-07 SCREEN CLOSED / NO_SELECTION_CANDIDATE`。本轮保留“先定状态格、再看选择依据”的顺序；没有提高判断准确率的主张。
- 根因：`DATA_COVERAGE + REASONING`。缺的不是第三方报告数量，而是同一当前事实下真正只支持一方的经营观察、以及可由它推出的同定义未来顺序。
- 经济影响：若把正的 comparable sales、连续改善、loyalty 增长或自营/特许分叉直接写成需求恢复，会高估竞争持续性与正常盈利，继而错误推断现金转换和永久损失边界。
- 禁止假设：不得把 company-specific KPI 名称视为同一结果变量；不得用 check、平均客单、food-basket price、全公司收入、管理层指引、后续表现、价格或回报补足交易机制。
- 可执行的重开条件：下一**新** cutoff 前，一家公司必须同时具有（1）同一状态格的共同事实，（2）可定位的 A-only/B-only 当前经营事实，（3）该事实导出的不同、同口径未来谓词，和（4）冻结的官方结果 label/locator/window。已有 cutoff 后出现的资料只能启动新 episode，不能回写本轮选择依据。
- 飞轮准入条件：在一个已选 focal 后，再以同一冻结结果指标和各自 cutoff 前可能性条件事实链寻找 near miss 与 boundary replication；其中任何一项不足，保留 `NO_QUALIFIED_NEGATIVE_CASE`，不以同一公司更多报告补齐。
