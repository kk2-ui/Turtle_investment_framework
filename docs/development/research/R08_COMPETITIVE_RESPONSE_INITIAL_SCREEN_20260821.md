# R-08 竞争回应过程：初筛记录

状态：`INITIAL_SCREEN / NO_ADMISSION / NOT_A_COMPANY_RESEARCH`  
screen as-of：`2026-08-21`

## 筛选的目标

本轮只问：是否已经存在一个可以启动 R-08 的**候选入口**。它必须在读取公司深层材料前同时具有：

1. 行动方的一手、已发生行动事实；
2. 对手方同一 arena 的一手回应事实或在 cutoff 前可冻结、覆盖明确的回应结果来源；
3. H-A/H-B 对回应对象、类别和最大时滞给出不同预测；
4. 一个与该 arena 相同边界、可在后续结算的经营结果；
5. 清楚的停止条件，不把“没有看到回应”当作回应不存在。

这些是 R-08 的准入条件，不是“行业竞争激烈”的筛选标签。

## 本轮观察与裁决

以公开网页检索只做候选发现，未将任何搜索摘要、新闻、价格变化或二手转述读入 Turtle 证据链。初步命中的泛价格调整、产品发布和竞争叙述均缺少至少一项关键要素：另一方在同一产品/渠道/地区/客户边界的可定位回应，或两方可预注册的后续同 arena 经营观察。

因此不建立公司 source package、PIT 资料卡、竞争 pair、FJ 或任何公司结论；R-08 保持 `DESIGN_READY_NOT_LIVE_TESTED / INITIAL_SCREEN_NO_ADMISSION`。

## 为什么不准入

- 根因：`DATA_COVERAGE + ACQUISITION_MODULE`。候选发现阶段只有宽泛、不可结算的竞争信息；没有同时满足一手行动、对手回应范围和结果期来源的最小 source contract。
- 经济影响：若把一次降价、产品公告、市场份额变化或未被观察到的回应写成“竞争回应”，会错误判断竞争强度、价格实现、正常盈利和 owner cash 的持续性。
- 缺失事实：行动对象/地区/客户的精确边界；对手是否知悉、具备动机/能力并作出**针对性**回应；同 arena 后续量价或现金观察的定义与来源窗口。
- 禁止假设：新闻搜索结果、公司管理层泛称的“竞争”、宏观价格调整、另一方全公司业绩或对手沉默，等于已发生的目标回应；不得以股价、回报或事后份额填补。

## 下一次可执行的筛选动作

只在一手 issuer/监管/交易场所来源先满足行动事实后，分别取得行动方与回应方的官方目录；对每个候选预先填写 [竞争回应机制实验协议](TURTLE_COMPETITIVE_RESPONSE_EPISODE_PROTOCOL.md) 的 arena、response-source coverage、A/B 时滞与终局 outcome contract。任一格不能填入，候选仍为 `NO_ELIGIBLE_ECONOMIC_FJ`，不进入正式研究。

## 接纳标准

候选只有在以下全部可由 cutoff 前一手 source package 证明时才进入 R-08：

```text
已发生行动
+ 同 arena 对手回应的可观测定义与来源覆盖
+ H-A/H-B 不同的对象 / 类别 / 最大时滞
+ 同 arena、同口径的后续经营结果 contract
+ 对缺覆盖与定义漂移的 NOT_DIAGNOSTIC 停止规则
```

此筛选记录不证明任何公司、行业或方法结论；它只防止“资料很多”或“竞争故事很强”取代可学习的机制实验。

## 有界复筛：Novo Nordisk / Hims & Hers 的 GLP-1 渠道冲突

状态：`NO_ADMISSION / NO_OUTCOME_READ`。

这是一条看似很强、但不应被硬塞进 R-08 的候选。候选发现材料指向 Novo Nordisk 在 2025-06-23 发布的、标题为“terminates collaboration with Hims & Hers”的 issuer-distributed wire release（[candidate locator](https://www.prnewswire.com/news-releases/novo-nordisk-terminates-collaboration-with-hims--hers-health-inc-due-to-concerns-about-their-illegal-mass-compounding-and-deceptive-marketing-302488189.html)）；它足以提出“品牌 GLP-1 供给/渠道摩擦可能引发 Hims 的替代、谈判或退出回应”的问题，但这份 wire 本身不是已准入的 Novo 一手 source package，不能充当 R-08 的行动事实。

本轮实际阅读的截止日前公司一手材料只有 [Hims Q2 2026 results](https://investors.hims.com/news/news-details/2026/Hims--Hers-Health-Inc--Reports-Second-Quarter-2026-Financial-Results/default.aspx)（2026-08-10）。它披露总收入、总订阅者、美国/海外收入与总利润/现金项目，却没有可持续、同定义的 Novo 品牌 GLP-1、复配 GLP-1、减重订单或相应客户留存序列。它也不能把全公司订阅者或总收入与这一个渠道冲突相连。

因此即使日后能构造 H-A“行动促成 Hims 的针对性替代、渠道留存”和 H-B“冲突只造成短期/广泛供给扰动”，当前仍缺两件不可替代的东西：Hims 一手、同 arena 的可定位回应及其最大时滞；以及未来可由公司或监管常规披露、同口径结算的 GLP-1 渠道经营结果。总收入、总订阅者、管理层指引、PR 争执、价格或股票回报都不是替代项。

- 根因：`DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。冲突标题不等于双方都已形成可观察的竞争过程，平台总 KPI 也不等于特定药品渠道的结果。
- 经济影响：若以总收入/订阅者结算该案，会把国际扩张、其他治疗领域和平台定价混入渠道反应，虚构供应商行动对竞争持续性、正常盈利和 owner cash 的影响。
- 禁止假设：supplier/partner 冲突天然等于 peer competition；后来重启谈判、任一全公司业绩变化或沉默已证明某一回应机制。
- 重新准入条件：在一个新的 cutoff 前，须同时取得 Novo 的可准入行动原件、Hims 的明确同 arena 回应原件、双方/单方可按固定来源和期间结算的品牌或渠道级经营指标；并冻结“针对性回应”和“没有可辨别回应”各自不同的对象、类别与最大时滞。缺一项仍为 `NO_ELIGIBLE_ECONOMIC_FJ`。

本轮未读取任何 2026-08-21 后的经营结果，未形成公司、药品、竞争强度或投资结论。
