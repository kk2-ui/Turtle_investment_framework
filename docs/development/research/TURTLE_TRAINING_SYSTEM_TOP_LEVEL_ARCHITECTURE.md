# Turtle 企业判断与训练系统顶层架构

> 状态：`TOP_LEVEL_DESIGN_DECISION / FORECAST_LEARNING_CONTROL_IMPLEMENTED / DECISION_CONTRACT_GATE_IMPLEMENTED / CJO_TEACHING_MIRROR_VALIDATED / CJO_VALUATION_SETTLEMENT_VALIDATED / DECISION_UTILITY_PAIRING_VALIDATED / CONTRACT_FIRST_PROSPECTIVE_SHADOW_GATE_VALIDATED`
>
> 日期：2026-08-25
>
> 本文裁决顶层目标、系统边界、学习闭环和路线优先级。现有 Forecast epoch、H1/H2/V5、schema、validator 和控制面仍由各自实施文档管理。2026-08-25 已按用户授权完成 C（Forecast Learning 与逐层错误归因）、D 的 contract-first CJO teaching mirror，及 E 的 synthetic valuation/return settlement：经营兑现、owner-cash valuation identity 和市场回报已各自结算且不回写 CJO。它们不创建 canonical CJO、不读取真实结果，也不授予 report 或投资动作；决策效用、真实独立结算和前瞻验证仍须独立工作包和验收，不能提前宣称已闭环。

> 已新增一条 synthetic 顶层整合回归：`DecisionContract → Forecast V2 → contract-first prospective shadow`、teaching-only CJO mirror、investment-only valuation settlement 与 candidate-only decision-utility evaluation 必须保持单向权限。它通过不代表全仓回归已恢复：当前全量 pytest 另被缺失的 `prompts/coordinator.md` 和未冻结的香港 risk-free-rate fixture 阻断，均不属于上述 Turtle contract 的修改面。

## 1. 总裁决

Turtle 的中心不是训练样本、预测榜单或黄金报告，而是：

> **在不确定性下持续形成更好的企业承保判断，并把该判断可靠地传播到正常利润、owner cash、预期差和条件化买点。**

因此，Turtle 的主系统应是**企业承保与投资决策闭环**。生产研究负责当前判断；训练系统负责发现这套判断流程在哪里稳定出错，并以受限方式改善下一次判断；黄金报告只是某个 cutoff 下的可读编译快照。

`PIT Company State Forecast` 作为高频训练主线的当前实现应继续。它解决了“必须先找到稀有公司行动，训练才可开始”的错误。但 Forecast 不是新的产品中心，严格 `Causal Action` 也不是全局入口。

```text
Decision Contract
  -> Outside View: industry structure, cycle, qualified base rates
  -> Inside View: longitudinal enterprise operating system
  -> Relative Reference: economics, cash, risk and expectations
  -> Management / capital allocation / adaptation
  -> Frozen Company Judgment Object (CJO)
  -> Normal earnings / owner cash / value identities
  -> Price-implied expectations / ExpectationGap / BuyBand
  -> Monitoring / revision / decision attribution
  -> Bounded learning policy
  -> Next unseen company and time
```

历史训练必须镜像这条生产研究链，并在 cutoff 后隐藏结果进行评价；不再建立一套与生产研究分离的 episode 工厂。

### 1.1 当前整合度

当前系统是**工程整合强、能力闭环弱**：PIT、来源、冻结、结果隔离、CJO/估值边界和报告接线已有较完整设计；Forecast 已具有限 learning control，但尚无真实独立结算、双轴 holdout 或配对决策效用证据，训练也尚未完整镜像生产决策。因此不能用控制面测试通过率宣称企业判断已经改善。

### 1.2 材料性审计结论

| 根因 | 为什么低于目标 | 经济影响 | 修复与接受条件 |
|---|---|---|---|
| `MODEL` | 训练对象和门禁曾高于用户决策任务 | 优化样本与流程，却仍可能看错企业和买点 | Decision Contract 成为入口；同 cutoff 配对证明材料决策增量 |
| `MODEL / REASONING` | Forecast 可评分却缺少有限 learning 权 | 主线变成记分板，错误不能改善下一家公司 | 直接学习只限校准、coverage、状态定义和不确定性；证据/反方方法须消融及双轴复核 |
| `MODEL / WRITING` | 训练、生产研究和报告授权仍容易混成一条长门链 | 一个等待中的 lane 阻断当前研究，或历史结局倒灌当前判断 | 历史训练镜像生产链；报告只编译同 cutoff CJO；三者分别验收 |
| `ACQUISITION_MODULE` | H1/H2/V5 曾在顶层充当训练入口，而非特定主张的来源/识别合同 | 没有稀有行动公告就没有样本 | 单公司 Forecast、Teaching 和 Industry History 不要求 H2；H2 只服务因果支线 |
| `DATA_COVERAGE` | 历史 PIT 无法消除基础模型记忆污染 | 历史分数可能高估真实能力 | 持续 unresolved prospective shadow；历史回放只标记 `MODEL_MEMORY_MITIGATED` |

禁止假设“可追溯就会判断”“预测分数高就改善买点”“一条因果样本可解锁完整报告”或“静态 PDF 能消除模型参数中的历史记忆”。

## 2. 主系统的七层

### 2.1 Decision Contract

研究开始前先说明要辅助什么决策：研究用途、cutoff、持有时域、永久损失约束、允许的输出、会改变判断的证据，以及投资用途下的价格和机会成本。没有 Decision Contract，就无法判断多一项研究是否真正有用。

Turtle 可以输出 `PASS / WATCH / RESEARCH / CONDITIONAL_BUYBAND` 等研究状态，但不拥有真实仓位、计划或交易；这些仍由年糕和用户决定。

### 2.2 Outside View

行业史、生命周期和退出对象首先用于建立 `QUALITATIVE_REFERENCE_CLASS`：在不同的行业阶段、资本强度、竞争结构、周期位置、资产负债表和治理条件下，哪些改善、衰退或失败路径值得优先检查。

只有预声明 risk set、分母、期间、覆盖状态、删失和竞争事件均成立时，系统才可以生成 `EMPIRICAL_BASE_RATE`。其他 Outside View 只能提供参考类别、问题、失败路径和定性先验约束，不能进入数值概率、估值参数，也不能把其他公司的结局写成本公司事实。

### 2.3 Inside View

单公司纵向经营系统是企业判断骨架。它连接客户任务、产品和活动、竞争反应、单位经济、组织能力、营运资本、资本开支、融资、资本回报和普通股现金。

行业标签、公告或单期财务数字都不能代替这张纵向系统图。

### 2.4 Relative Reference

横向公司比较通常是参考系，不是未处理控制组。它分别比较单位经济、再投资空间、现金转换、资本结构、永久损失和市场隐含预期，不输出一个“总冠军”。只有明确提出因果主张时，才进入严格 comparator 设计。

### 2.5 Management And Adaptation

管理层质量来自纵向决策序列：当时如何定义问题、有哪些备选、承诺了什么资源、怎样执行、怎样面对新信息调整，以及资本最终如何配置。单次好结果或坏结果不能直接决定管理层质量。

### 2.6 CJO And Investment Overlay

CJO 是指定 cutoff 下企业判断的冻结快照。经营判断必须单向传播到正常利润、owner cash、资本需求、普通股可达性和永久损失；投资层随后才计算价值身份、价格隐含要求、预期差、回报和 BuyBand。

价格可以提出新问题，但不能反写企业事实、机制或中心路径。

### 2.7 Monitoring And Attribution

后续披露不是只给预测打分。系统必须分别回答：当时过程是否合理、企业状态后来怎样、价值判断是否正确、买点是否合理、外部冲击和运气贡献了什么。只有定位到可修改环节，结果才能形成 learning。

## 3. 训练课程按决策任务组织

课程不再以 `Teaching / Lifecycle / Forecast / Causal` 为主轴。这些是资料与反馈形态，不是要培养的能力。

训练应围绕六类决策任务：

1. 企业如何赚钱、竞争、占用资本并形成普通股现金；
2. 行业、周期的定性参考类别和合格经验基准率怎样约束本公司判断；
3. 当前最材料性的未知是什么，什么证据能区分竞争解释；
4. 未来经营状态、资本回报和永久损失怎样变化；
5. 管理层决策、执行、适应、外部冲击和资本配置怎样分开评价；
6. 冻结经营判断怎样进入正常利润、owner cash、预期差和买点。

一个任务可以使用多种 episode；一个 episode 也可以训练多个任务。公司消失、没有明确行动公告或 comparator 不足，都不再使该公司失去训练价值。

## 4. 三种速度的训练与一种最终验证

| 回路 | 主要作用 | 可以学习什么 | 不能授予什么 |
|---|---|---|---|
| `Teaching / Industry / Lifecycle` | 高频、低成本练习 | 问题、边界、near miss、禁止替代、取证顺序 | 预测优势、因果结论、经验概率 |
| `PIT Company State Forecast` | 常规能力训练和结算 | 直接学习校准、coverage、状态定义、不确定性和基线表现；其他只形成待验证候选 | 行动因果、公司事实、自动买点 |
| `Causal Action Lab` | 低频机制识别 | 特定行动的因果箭头和适用边界 | 日常训练产量、全行业规律、完整投资能力 |
| `Prospective Shadow` | 答案尚不存在时的部署验证 | 无历史结果污染的可靠性和校准证据 | 单次结果证明普遍优势 |

Teaching 负责快速学习边界，Forecast 负责常规能力改善，Causal Lab 增强少数关键机制的识别可信度。任何一条等待外部材料，都不能把其他回路标记为 blocked。

## 5. Learning Policy Router

当前设计最需要补足的不是更多状态，而是**学习权路由**。不同反馈只能修改与其识别强度相符的对象：

```text
Teaching result
  -> questions / scope / prohibited proxy / acquisition order

Forecast settlement
  -> direct: calibration / coverage / state definition /
     baseline performance / uncertainty policy
  -> candidate only: evidence priority / rival-hypothesis method

Causal settlement
  -> causal mechanism candidate / boundary / transport condition

Valuation and return settlement
  -> normalization / owner-cash bridge / expectation-gap /
     BuyBand and decision policy
```

Forecast 必须拥有合法但有限的 learning 通道，否则高频主线只是记分系统。结算可直接修改校准、coverage、状态定义和不确定性表达；它不能仅凭相关的结果误差判定哪项证据或机制是原因。证据优先级和反方方法只能成为 candidate，必须有已冻结的对照方法、配对消融、可识别 failure locus，并在未见公司和时期复现；否则结算为 `NOT_DIAGNOSTIC`。Forecast 不能生成因果结论，也不能把历史结局注入当前公司。

同理，价格或收益结果只能改变投资层，不得改写 CJO。单个案例只产生候选改变；方法进入生产默认项前，仍需不同公司或时期复核。

已实现的 `CJOValuationReturnSnapshot` 只接收 `FROZEN / INVESTMENT_INPUT` CJO，并沿用同一 finite-horizon BuyBand identity 生成 normal earnings、owner cash、价格隐含 owner cash、ExpectationGap 和条件 BuyBand。相应 `CJOValuationReturnSettlement` 由独立 custodian 分开记录 operating realization、由实际 owner cash 导出的 valuation identity 与带逐年现金流的市场 IRR；`CENSORED / UNKNOWN` 保留为显式未结算，不用价格或最后交易值填零。其学习输出仍只是 `CANDIDATE_ONLY`，价格结果不得回写 CJO，且这一 synthetic validator 不是 production overlay、报告或真实结果库。

`DecisionUtilityPairing` 已把同一 Decision Contract、cutoff 和 frozen evidence budget 下的 baseline/enhanced 决策摘要并列；`DecisionUtilityEvaluation` 逐项记录 permanent-loss guardrail、owner-cash access、关键未知发现与研究成本，不生成综合 0--100 分或自动方法 release。它要求公司和时间双轴 holdout、独立 reviewer 与既有 outcome-settlement reference，唯一输出仍是 `CANDIDATE_ONLY`。

对仍未发生的结果，`ProspectiveShadowEpisode V2` 现要求冻结 Forecast V2 的同一 Decision Contract 已持久化且早于 shadow 注册。它只保存未决 1/3/5 年结果时钟，闭合形状拒绝 outcome、价格、估值和报告字段；既有 V1 forecast/signal shadow 不可被追溯升级。

通过上述配对消融及公司轴、时间轴复核的 Forecast learning 可以进入下一份报告的 `RESEARCH_AGENDA`，但不能作为 `JUDGMENT_SYNTHESIS` 的公司事实或 `INVESTMENT_ENRICHMENT` 的数值参数。它不需要先等待一条 Causal Action 样本；因果主张仍必须走 Causal Lab 自己的识别门。

## 6. 决策过程与结果分开评价

每次冻结保留两套账：

- `ExAnte Decision Record`：当时可选路径、证据、概率或区间、关键未知、最强反方、翻转条件和选择理由；
- `ExPost Realization And Attribution`：实际经营、现金、价值、价格、外部冲击和口径变化。

好决策可能遇到坏结果，坏决策也可能因运气得到好结果。结果不能重写当时决策质量，否则系统只会学习追逐事后赢家。

错误归因至少分开：

```text
evidence coverage
scope / state recognition
operating mechanism
probability calibration
management adaptation
external shock / luck
outcome measurement
normal earnings / owner cash propagation
valuation / expectation gap
timing / downstream portfolio decision
```

## 7. 能力评价

### 7.1 同 cutoff 配对

正式能力评价使用同一 Decision Contract、同一 cutoff 和同一证据预算，比较：

```text
simple baseline research
vs
training-enhanced research
```

判断增强是否：

1. 发现会翻转结论的关键未知或反方；
2. 避免责任边界、现金归属、因果和永久损失错误；
3. 材料性改变 `PASS / WATCH / RESEARCH / BuyBand`，而非只增加文字；
4. 相对简单策略降低可避免的决策损失或机会成本；
5. 以合理的研究时间和证据成本取得改进。

### 7.2 分层指标

- 概率和区间：Brier、RPS、WIS/CRPS 等 claim-specific proper scores；
- 弃权：risk-coverage，分开 `EVIDENCE_INELIGIBLE` 与 `MODEL_UNCERTAIN`；
- 排序：逐维 pairwise concordance，不做综合冠军；
- 决策效用：材料结论变化、避免的错误、机会成本和研究成本；
- 泛化：公司轴和时间轴双 holdout；同公司重叠窗口不当作独立样本；
- 最终可信度：持续 unresolved prospective shadow，而非历史回放单独证明。

这些指标不压成一个 0--100 分。样本数、流程通过率、报告长度、单次命中、股价上涨和单案收益率都不是能力代理。

### 7.3 复杂组件的消融

任何拟成为必经层的 Graph、Memory、多 Agent 或额外工具，都必须在固定模型、cutoff、证据、工具权限和研究预算下，做最小系统到增强系统的配对消融。不能证明其改善材料决策质量或重复运行可靠性的组件，只能作为可选运行便利，不得成为全局门或系统成熟度指标。

## 8. 系统组件降级

### 8.1 Episode

主训练单位是 `公司 x cutoff x 判断任务 x 时域`。`DecisionEpisode` 只保留为行动因果研究对象，不再定义全系统训练。

### 8.2 Graph

Evidence、Mechanism 和 Investment graph 是同一 canonical 判断状态的派生视图。顶层只强制两条可追溯链：

```text
claim -> evidence
judgment -> investment consequence
```

图数量本身不代表判断能力。

### 8.3 Agent

多 Agent 是执行方式，不是认识论投票。顶层只保留三种独立权威：

1. `Judgment Owner`：维护问题树并形成最终 CJO；
2. `Evidence / Outcome Custodian`：维护 cutoff 和结果隔离；
3. `Independent Challenger`：审查反方、数字、边界和学习归因。

其他 Source、Scope、Mechanism、Valuation、Report Agent 都是任务角色。共享模型和共享信息的多数票不能产生投资结论。

### 8.4 Memory

记忆保存方法教训、失败经验和 canonical 导航；不得直接贡献公司事实、概率、估值、价格或动作。PIT 回放只能称为 `MODEL_MEMORY_MITIGATED`，因为基础模型可能已记住历史结果。

### 8.5 Golden Report

黄金报告是 CJO 与 Investment Overlay 的完整、可读、可复算编译结果，也是回归对象；它不是训练正确答案，也不是长期状态真源。长期对象是持续版本化的企业承保状态。

## 9. 训练与生产研究边界

- 当前生产研究不必等待某条历史方法获得训练授权，才可以依据本公司证据形成判断；
- 未通过留出的 training learning 只能作为待验证问题或方法提示，不能注入事实、概率或估值参数；
- 历史结局永远不能成为当前公司证据；
- 训练系统证明的是方法是否改善未见决策任务，报告系统决定该方法是否适合正式交付；
- Turtle 交付企业判断、价值边界和研究 BuyBand，年糕与用户拥有机会集合、组合约束、计划、仓位和真实动作。

## 10. 路线图优先级

| 顺序 | 顶层目标 | 与当前工作的关系 |
|---|---|---|
| P0 | 持续注册 unresolved prospective shadow | 立即与所有历史工作并行启动；等待结果不阻断开发 |
| A | 冻结本文的主系统、课程主轴和 learning router | 本文完成设计裁决，不授权代码变更 |
| B | 完成 Company State Forecast pilot | 当前 Agent 的既有 Goal 继续，不扩成全系统 |
| C | 建立 Forecast Learning 与逐层错误归因 | 使预测主线从记分变成学习 |
| D | 让历史回放完整镜像生产 Decision Contract -> CJO -> Overlay | 消除训练/生产双系统 |
| E | 完成 CJO -> normal earnings -> owner cash -> ExpectationGap -> BuyBand 的独立结算 | 单独评价经营、价值和价格错误 |
| F | 做同 cutoff baseline/enhanced 决策效用 A/B | 证明对用户判断有材料增量 |
| G | 到期后结算 prospective shadow | 最终能力结论必须依赖该无污染证据 |

`Causal Action Lab` 与 B--G 并行、按机会运行。第一条严格因果样本何时出现，不再决定整个路线是否前进。

## 11. 立即停止的错误优化

- 不再以 H2、公告、固定公司数量或 comparator 作为全局训练入口；
- 不再用一条因果样本解锁完整黄金报告或买点能力；
- 不再让 Forecast 只能评分而不能合法改善下一轮方法；
- 不再按 episode 类型组织整个课程；
- 不再把 Agent 数、图数量、schema 完整度或门禁通过率称为系统整合度；
- 不再把报告评分、股价表现或单案收益当作企业判断能力；
- 不再为等待一个 lane 而把全系统标记为 blocked。

现有文档中的对象、schema 和运行合同继续有效，但顶层含义按本文收口：`DecisionEpisode` 仅属于 Causal Lab；H1/H2/V5 仅属于适用的来源和因果准入；Forecast 是常规训练工具；黄金报告是 CJO/Overlay 的交付编译；任何“下一步只能取得 H2”的表述只适用于 Causal lane，不能代表整个 Turtle。

## 12. 架构成功标准

顶层架构成功不是“第一条样本终于通过”，而是系统能够反复证明：

1. 在当时可得信息下形成明确、诚实且可证伪的企业判断；
2. 结果揭示后能定位具体错误，而不是写出更漂亮的事后故事；
3. 学习改变了下一家未见公司的真实研究行为；
4. 该改变在未见公司和时期相对简单基线仍有增量；
5. 企业判断能单向、可复算地改善正常利润、owner cash、预期差和条件化买点；
6. 用户得到更少的重大遗漏、更清楚的未知和更可执行的判断，而不是更多流程工件。

## 13. 研究依据

- [Dawid, The Prequential Approach](https://doi.org/10.2307/2981683)：按真实时间顺序冻结、结算和更新。
- [Gneiting and Raftery, Strictly Proper Scoring Rules](https://doi.org/10.1198/016214506000001437)：概率预测应按适当评分评价，但分数不等于决策效用。
- [El-Yaniv and Wiener, Selective Prediction](https://jmlr.org/papers/v11/el-yaniv10a.html)：弃权必须与覆盖率共同评价。
- [Kahneman and Klein, Conditions for Intuitive Expertise](https://doi.org/10.1037/a0016755)：专业直觉需要可预测环境和可学习反馈。
- [Baron and Hershey, Outcome Bias](https://doi.org/10.1037/0022-3514.54.4.569)：决策质量不能由事后结果倒推。
- [Forecast evaluation pitfalls](https://pmc.ncbi.nlm.nih.gov/articles/PMC9718476/)：时间序列评价需要时间顺序、合理分割、基线和防泄漏。
- [ForecastBench](https://arxiv.org/abs/2409.19839) 与 [AutoCast](https://arxiv.org/abs/2206.15474)：动态未决问题和按日期信息集用于降低污染；预测榜单不代表企业判断。
- [Decision-Focused Learning survey](https://arxiv.org/abs/2307.13565)：预测误差与下游决策损失不是同一目标。
- [Blaskowitz and Herwartz, Economic Evaluation of Directional Forecasts](https://ideas.repec.org/a/eee/intfor/v27y2011i4p1058-1065.html)：预测价值还要按其改善的经济决策评价。
- [Selling Fast and Buying Slow](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3301277)：研究、买入和卖出能力必须分开归因。
- [ForecastBench GitHub](https://github.com/forecastingresearch/forecastbench)、[FinRobot](https://github.com/AI4Finance-Foundation/FinRobot)、[Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai)：借鉴动态评价、确定性计算与叙述分离、task/solver/scorer/log 边界；不借鉴多 Agent 数量或交易回报作为判断能力证明。

这些依据只支持系统设计，不构成任何公司、行业、估值或买点的投资证据。
