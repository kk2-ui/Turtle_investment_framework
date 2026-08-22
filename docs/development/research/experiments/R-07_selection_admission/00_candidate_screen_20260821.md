# R-07 实时主路径选择筛查（2026-08-21）

状态：`SCREEN_CLOSED / NO_SELECTION_CANDIDATE / NO_OUTCOME_READ`

目的：筛选可以进入 `JUDGMENT_SELECTION_EPISODE` 的实时对象；不是对任何公司的经营、价值、证券价格或投资回报结论。每个候选均只读截止日前公司官方原件；未读取未来业绩、价格、回报或二手材料。

## 筛查结论

| 候选 | 原始来源 | 初看似乎可选的证据 | 主研究裁决 | 原因 |
|---|---|---|---|---|
| Lululemon | [FY2026 Q1 results](https://corporate.lululemon.com/media/press-releases/2026/06-04-2026-210523775) | Americas constant-currency comparable sales `-6%`，公司同时称北美 full-price sales sequentially improved。 | `NO_PRIMARY` | H-A“商品/执行错配可修复”与 H-B“需求/品牌相关性持续走弱”均可出现短期全价销售环比改善；它不是对两者有相反含义的当前事实。将 Q2 Americas comp 设成 `>-6%` 只会任意制造与延续基线不同的阈值。 |
| Target | [FY2026 Q2 results](https://corporate.target.com/press/release/2026/08/target-corporation-reports-second-quarter-earnings) | Comparable sales `+3.8%`、traffic `+3.6%`，门店/数字/核心品类都增长。 | `NO_PRIMARY` | H-A“商品、门店和数字履约改善”可解释广度；但 H-B“价值价格/促销拉动的一次性流量”同样可以跨渠道、跨品类发生。`>+3.8%` 对 `=+3.8%` 的差异没有从已证实机制导出。 |
| Nike | [FY2026 Q4/FY results](https://investors.nike.com/investors/news-events-and-reports/investor-news/investor-news-details/2026/NIKE-Inc--Reports-Fiscal-2026-Fourth-Quarter-and-Full-Year-Results/default.aspx) | Wholesale constant-currency `+1%`、Direct `-9%`，北美 wholesale 增长。 | `NO_PRIMARY` | H-A“渠道重置成功”与 H-B“Direct/数字需求弱、批发只是渠道转移或清库存”均可解释当前组合；未见对两方有相反方向的官方 sell-through、折扣/价格、重复购买或库存/订单观察。 |

## 从筛查沉淀的规则

`SELECTION_ADMITTED` 不仅要求一条“看起来支持主方”的事实；该事实还必须导出一个**反方不能同样合理预期**的未来顺序。基线和阈值是这条顺序的表达，不能反过来制造选择资格。

因此本轮不建立 source package、不冻结 FJ、不读取任何后续结果。要重开任何候选，唯一条件是截止日前出现新的官方、同口径经营观察，使 H-A/H-B 对后续同一指标产生非任意的不同预测；否则保持 `NO_PRIMARY`。

## 状态优先 universe 补充筛查

同日另以“销售改善但客户交易机制未辨别”为状态格，筛查了 Chipotle、McDonald's 与 Domino's 的最小 SEC Exhibit 99.1 原件。三者均未形成 `SELECTION_ADMITTED`：当前事实仍可被最强反方解释，且三个公司没有相同、可冻结的结果指标，不能伪装成 focal / near miss / boundary 的飞轮 batch。详见[状态优先 candidate universe](01_state_first_candidate_universe_20260821.md)。

## 数字产品参与状态格补充筛查

| 候选 | 截止日前官方原件 | 初看似乎可选的证据 | 主研究裁决 | 原因 |
|---|---|---|---|---|
| Duolingo | [Q4 FY2025 shareholder letter](https://www.sec.gov/Archives/edgar/data/1562088/000162828026012246/q4fy25duolingo12-31x25shar.htm)、[Q1 FY2026 shareholder letter](https://www.sec.gov/Archives/edgar/data/1562088/000162828026029790/q1fy26duolingo3-31x26share.htm)、[Q2 FY2026 shareholder letter](https://www.sec.gov/Archives/edgar/data/1562088/000162828026053299/q2fy26duolingo6-30x26share.htm) | Q2 DAU 同比增速由 Q1 的 `+21%` 加速至 `+23%`；Q2 新披露 Current User Retention Rate（CURR）`84%`、约同比 `+1` 个百分点。 | `NO_PRIMARY` | Q2 同时把 DAU 加速归因于产品改动、营销影响和一次性“revive lost streaks”活动。即使 CURR 上升，三者都可合理造成短期回访改善；它不能在 H-A“产品留存机制实质改善”和 H-B“营销/一次性唤回主导”之间选择主方。Q4 与 Q1 有连续的 DAU/MAU/付费订阅者披露，但没有可与 Q2 `CURR` 配对的定量 CURR 历史序列，故也不存在已验证的重复结果通道。 |

这一拒绝的根因是 `DATA_COVERAGE + REASONING`：当前公司原件没有把产品留存、营销与一次性唤回的影响拆成对立、重复可测的前导指标；据单点 CURR 或管理层的全年 DAU 指引选择 H-A，会把联合结果误作机制证据。经济影响是可能把短期用户活跃度误写成可持续留存，从而污染后续对正常增长、经营杠杆与现金转化的判断。

因此不得假设 DAU 加速、CURR 上升或营销费用本身就是产品留存改善的证据；也不得以未来 DAU、收入、利润、价格或回报倒推这次选择。Q2 自身还提示这些经营指标并非独立第三方验证、计算方法可能变化，故相近指标不能替代同定义序列。本轮不建立 source package、不冻结 FJ、也不读取任何截止日后结果。

只有在未来一个新的截止日前筛查中，同时出现：(a) 至少两期同定义、可定位的官方留存/队列指标，(b) 能使产品机制与营销/一次性唤回机制方向相反的非共同当前事实，及 (c) 预先可指定的同定义官方结果窗口，才可作为新的候选重新筛查；否则保持 `NO_PRIMARY`。

## R-54 的结果前撤回（2026-08-22）

R-54 美的曾以“三个 ToB 业务方向分裂、集团扣非下降与非经常性损益”暂列为选择 episode；在结果窗口前的完整性复核中撤回。不同业务的周期差异本身仍可被 H-A“组合互补、工业技术局部波动”解释，集团扣非与非经常性项目又不能归属于 ToB；两者均不是仅支持 H-B 的方向性事实。故 R-54 保留为真实前瞻 `MECHANISM_SIGNAL_PROBE`，但不得进入选择学习或基线比较。[完整复核](../R-54_midea_core_growth_20260430/01_pre_outcome_selection_integrity_review.md)

这条撤回是本筛查的正例：即使已有一手源包、五层时钟和未来同口径结果窗口，只要当前事实仍由主/反机制共同预期，`NO_PRIMARY` 仍是正确输出。不得等到 H1 结果后再把其方向解释成当初选择依据。

## 单位经济/份额状态格补充筛查

| 候选 | 截止日前官方原件 | 当前可见的相反机制线索 | 主研究裁决 | 原因 |
|---|---|---|---|---|
| Altria 口含烟草 | [2026 Q2 results](https://investor.altria.com/press-releases/news-details/2026/Altria-Reports-2026-Second-Quarter-and-First-Half-Results-Narrows-2026-Full-Year-Earnings-Guidance/default.aspx) | 口含烟行业上半年估计量 `+6%`，公司调整后国内出货约 `-5.5%`、其口含烟份额同比 `-0.3pp`，支持“品类增长中竞争地位走弱”；但同一原件又披露其口含烟份额环比 `+0.8pp`、出货受 trade-inventory movements 影响，保留“短期去库存/修复”的解释。 | `NO_PRIMARY` | 这两组当前事实分别给 H-A“短期库存/近期份额修复”与 H-B“在增长品类中持续流失”提供材料，任何一方都不能据此取得方向性选择资格。把下一季份额高于、低于或等于当前值设为主路径阈值，只会由事后想象制造不同于延续基线的预测。 |

该案的根因是 `DATA_COVERAGE + REASONING`：公司原件给出了冲突的出货和份额信号，但没有结果前、只支持其中一条机制的品类内购买、渠道可得性或独立留存观察。若强行选择，会把库存时间差或单期份额波动误写成竞争能力变化，材料性污染对增长、正常盈利与 owner cash 的判断。不得以行业增长、一个环比份额变化、管理层解释、未来业绩、价格或回报充当选择证据。只有新的 cutoff 前出现可定位、对两机制含义相反的经营事实，并能导出同口径的官方结果合同，才可新建 episode；本轮不建立 source package、不冻结 FJ，也未读取任何结果期材料。
