# R-03 外部档案 outcome resolution：Trian / DuPont（2015）

状态：`ARCHIVED_EX_ANTE_EXTERNAL / OUTCOME_RESOLVED_WITH_MEASUREMENT_MISMATCH / NOT_A_TURTLE_BACKTEST`

本文件是对 [pre-outcome intake](01_trian_dupont_2015_preoutcome_intake.md) 的追加结算记录。冻结卡没有被改写；结果期只读取了独立 [outcome package](01_trian_dupont_2015_outcome_package/outcome_manifest.json) 中的 2015 Q2、Q3 和 FY SEC 主件。它不评价股价、回报、2016 年或其后的结构事件，也不形成任何公司总体结论。

## 冻结对象与结果边界

Trian 的可结算表达不是“经营利润会增长 29%”，而是一个条件桥：**若** 2015 年实现 `$0.40/股` 成本节约，则核心业务在 `2015 Q2–Q4` 须实现约 `29%` 的经营利润增长，才能达到所述全年 EPS 指引低端。其当时理由包含农业疲弱。

同期杜邦材料只保留为冻结的相反机制：运营重构、规模/研发/客户关系的协同可改善经营，拆分将提高成本并削弱协同。本结算不把后来的任何公司叙述倒灌为该反方的证据，也不把短窗口观察推广为“整合”或“拆分”的胜负。

## 已读结果源与口径边界

| 结果源 | 已用 locator | 可读到的相关项目 | 口径问题 |
|---|---|---|---|
| [2015 Q2 Form 10-Q](01_trian_dupont_2015_outcome_package/raw/SEC_EIDP_2015Q2_10Q.html) | 印刷 p.25、p.29、p.34 | segment PTOI 定义；运营重构节约的期间进度；Agriculture 销售/PTOI 说明 | PTOI 是税前且剔除非经营养老金/OPEB、汇兑、公司费用和利息。 |
| [2015 Q3 Form 10-Q](01_trian_dupont_2015_outcome_package/raw/SEC_EIDP_2015Q3_10Q.html) | 印刷 p.30、p.33、p.37 | PTOI 定义及中途分类变化；运营重构节约的期间进度；Agriculture 说明 | 自 `2015-07-01` 起部分公司费用纳入 PTOI；即使前期比较数有重分类，这不是与 Q2 同一冻结序列的直接读数。 |
| [2015 Form 10-K](01_trian_dupont_2015_outcome_package/raw/SEC_EIDP_2015FY_10K.html) | 印刷 p.23–24、p.30–31 | 全年运营重构节约；全年 segment operating earnings 与 Agriculture 说明 | 年报改用 segment operating earnings，且另剔除 significant pre-tax benefits/charges；它不是 Q2/Q3 PTOI 的不加调整续表，也不是 Trian 的 core bridge。 |

## 结算

| 冻结 signal | 官方观察 | 与冻结谓词的关系 | 结算 |
|---|---|---|---|
| `$0.40/股` 成本节约假设 | Q2 将运营重构的全年预期表述为约 `$0.40/股`（p.29）；Q3 仍表述为约 `$0.40/股`（p.33）；FY 报告全年已实现约 `$0.40/股` 的增量节约（p.24）。 | 数字、每股单位和公司所称运营重构项目在结果源内连续。这验证了条件桥所假定的共同前提，但该前提并不区分 Trian 与杜邦的机制。 | `NOT_DIAGNOSTIC` |
| 农业疲弱 | Q2 的 Agriculture 销售与 PTOI 均较上年同期下降（p.34）；Q3 报告该业务需求进一步走弱（p.37）；FY 的 Agriculture 销售、经营利润与经营利润率均较上年下降（p.31）。 | 这是对 Trian 已写出的“农业疲弱”理由的同方向经营观察。公司材料同时把成本行动写作部分缓冲项，因此它不单独证明更广泛的成本结构或拆分机制。 | `A_ONLY`，仅限农业这一机制箭头 |
| `Q2–Q4` 核心业务约 `29%` 经营利润增长的必要条件 | Q2 报 `PTOI`，Q3 在窗口中改变公司费用归类，FY 用另一定义的 segment operating earnings。Trian 的桥还以其 own normalized/core 调整构造，并非任一官方定义的直接字段。 | 将全年或九月累计值倒推 Q4，或以公司 PTOI/全年 operating earnings 代替 Trian core，都会改变冻结对象。 | `MEASUREMENT_MISMATCH` |

### 严格裁决

`$0.40/股` 假设可按公司同名运营重构进度观察到；农业弱势也提供了一个同方向机制信号。然而，最关键的 `29%` 条件桥没有跨 Q2、Q3、FY 的**同定义、同窗口、官方直接结果字段**。因此不得把任何全年、累计或总分部利润数字替代为 Trian 的 core business bridge，也不得声明 Trian 或杜邦的完整机制在本案例中获胜。

本档案的身份仍是 `ARCHIVED_EX_ANTE_EXTERNAL`：它保留一份当时外部判断、同期反方和后续官方经营源之间的受控关系，供结构训练使用；它**不是** Turtle 在结果未知时的预测、盲测、准确率样本或概率基准。

## 可沉淀与不可沉淀

- 可沉淀：成本节约的实现与核心经营利润的改善是不同信号；农业局部经营信号可以支持或削弱一条机制箭头，但不能自动结算一条复杂的公司级盈利桥；口径在窗口中发生变化时，正确动作是停止重建。
- 不可沉淀：任何关于杜邦整体价值、拆分/整合优劣、后续重组、股价、回报或作者投资表现的结论。
- 结算停止：`YES`。除非取得一份在结果前已冻结、且能将 Trian 的 core 定义与连续官方 `Q2–Q4` 指标逐项对齐的映射材料，否则不再为本判断档案扩展结果源。
