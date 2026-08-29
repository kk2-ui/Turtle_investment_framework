# Turtle 企业判断与训练系统顶层架构

> 状态：`TOP_LEVEL_DESIGN_DECISION_V2 / MULTI_DIMENSIONAL_ENTERPRISE_EPISODE_DESIGNED / FORECAST_LEARNING_CONTROL_IMPLEMENTED / DECISION_CONTRACT_GATE_IMPLEMENTED / CJO_TEACHING_MIRROR_VALIDATED / CJO_VALUATION_SETTLEMENT_VALIDATED / DECISION_UTILITY_PAIRING_VALIDATED / CONTRACT_FIRST_PROSPECTIVE_SHADOW_GATE_VALIDATED`
>
> 日期：2026-08-26
>
> 本文裁决顶层目标、系统边界、学习闭环和路线优先级。现有 Forecast epoch、H1/H2/V5、schema、validator 和控制面仍由各自实施文档管理。2026-08-25 已按用户授权完成 C（Forecast Learning 与逐层错误归因）、D 的 contract-first CJO teaching mirror，及 E 的 synthetic valuation/return settlement：经营兑现、owner-cash valuation identity 和市场回报已各自结算且不回写 CJO。它们不创建 canonical CJO、不读取真实结果，也不授予 report 或投资动作；决策效用、真实独立结算和前瞻验证仍须独立工作包和验收，不能提前宣称已闭环。

> 已新增一条 synthetic 顶层整合回归：`DecisionContract → Forecast V2 → contract-first prospective shadow`、teaching-only CJO mirror、investment-only valuation settlement 与 candidate-only decision-utility evaluation 必须保持单向权限。它通过不代表全仓回归已恢复：当前全量 pytest 另被缺失的 `prompts/coordinator.md` 和未冻结的香港 risk-free-rate fixture 阻断，均不属于上述 Turtle contract 的修改面。

## 0. V2 重构裁决：从“训练轨道”回到“企业判断对象”

上一版设计已经正确解决了 PIT、防结果泄漏、生命周期、结果隔离和 Comparative 的因果识别边界，但仍有一个顶层缺口：实践中容易把 `PIT Company State Forecast` 或 `V5 Comparative Episode` 当成训练的主要入口。这样会产生两个相反问题：

1. 第一条训练样本被要求同时具备完整因果比较、同行、D3/D4 和现金结算，准入过重；
2. 公司经营被压缩成单公司、单指标或单一行动，无法承载客户、竞争、组织、资本配置和永久损失的共同判断。

V2 的核心对象改为：

> **`EnterpriseJudgmentEpisode = company × cutoff × enterprise state × decision sequence × mechanism threads × outcome vector`**

它不是第四张图，也不是替换现有 schema 的新数据库真源，而是对现有 `EnterpriseSystemModel`、`ManagementDecisionLedger`、Evidence/Mechanism/Investment Graph 和各类合同的**组合读模型**。一个 episode 可以有完整的公司全景、多个机制线程和多个结果单元；每个线程和结果单元拥有自己的证据上限与结算状态，不再用一个总门把整家公司压成 `PASS/FAIL`。

### 0.1 三个必须同时成立的设计原则

**企业判断是多维的。** 训练对象至少要能描述商业模式、客户与竞争、经营活动、组织能力、资本占用、现金可达性、管理层决策和永久损失边界。缺一个字段只能限制相应主张，不能抹掉其他已成立的判断。

**因果验证是局部的。** Comparative 是验证某条关键机制的低频实验室，不是认识整家公司的总入口。它需要 target trial 式的 eligibility、time zero、intervention、comparator、outcome、follow-up、censoring、interference 和 estimand，但这些条件只对 `RELATIVE_CAUSAL` 主张生效。

**投资授权是逐步的。** 全景重建可以先形成 `TEACHING / RESEARCH_AGENDA`；窄机制可以形成 `MECHANISM_CANDIDATE`；只有跨公司迁移、留出和决策效用验证后，才可进入 CJO、估值、报告或买点。低层证据不因不完整而作废，高层权限也不因叙事完整而自动获得。

### 0.2 V2 对现有轨道的重新定位

| 现有对象/轨道 | V2 中的职责 | 不再承担的职责 |
|---|---|---|
| Industry / Lifecycle | 建立公司 × cutoff 的风险集合、行业结构、进入退出和永久损失路径 | 不再等待 Comparative 才能产生训练价值 |
| Teaching / Boundary | 训练状态重建、管理决策、反方、测量边界和失败模式 | 不再被误报为选择能力或方向性 learning |
| PIT Company State Forecast | 对企业状态向量做概率、区间和弃权校准 | 不再代表完整企业判断，也不直接生成 CJO |
| Mechanism Probe | 对一个经营传导线程做过程和结果检查 | 不要求先凑完整同行 panel |
| Comparative / V5 | 在确有相对因果主张时冻结反事实和结果 | 不再是全系统的第一入口 |
| Learning Transfer | 把已诊断错误变成下一家公司冻结前的字段变化 | 不再把整家公司结论复制到下一家公司 |
| Investment Overlay | 读取冻结 CJO，传播到正常利润、owner cash、价值和价格 | 不得用价格结果回写企业事实 |

### 0.3 “完整”不等于“所有维度都硬结算”

每个 `EnterpriseJudgmentEpisode` 必须维护五种不同状态：

```text
OBSERVED         cutoff 前或结果后有同边界直接证据
INFERRED         有明确关系和来源，但仍不是直接观测
UNKNOWN          当前证据不足，下一步可继续研究或保守处理
EVIDENCE_INELIGIBLE  来源/口径不允许进入该判断单元
NOT_APPLICABLE   该公司、时期或问题不适用
```

`UNKNOWN` 和 `EVIDENCE_INELIGIBLE` 只阻断依赖它们的 claim；不会把公司全景、其他机制线程或行业史一起标成无效。相反，`MEASUREMENT_MISMATCH` 不得被解释成经营失败，`MIXED` 不得被压成支持或反对。这样既不会为凑样本放松证据，也不会因为一项指标缺失而丢掉公司的其他训练价值。

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

### 3.1 EnterpriseJudgmentEpisode：一个公司判断，多个证据线程

训练对象的最小综合单位不再是“公司 × 一个指标”，也不要求“公司 × 一个行动”承担整家公司结论。`EnterpriseJudgmentEpisode` 由以下部分组成：

```text
EnterpriseContextSnapshot
  + OperatingSystemModel
  + ManagementDecisionLedgerSlice
  + JudgmentQuestionSet
  + EvidenceCoverageMatrix
  + MechanismThread[]
  + ForecastBundle (optional)
  + OutcomeVector[] (cell-level)
  + ResolutionAndLearning
```

其中：

- `EnterpriseContextSnapshot` 描述 cutoff 时的商业模式、客户、竞争经济体、生命周期、责任边界和资本结构；
- `OperatingSystemModel` 保留 2--3 条最重要的客户、经营、竞争、现金和资本反馈回路，不建立与事实脱节的大型仿真；
- `ManagementDecisionLedgerSlice` 记录当时的问题、可行替代、不作为选项、资源承诺、执行、适应和资本配置；
- `JudgmentQuestionSet` 通常包含 3--5 个公司级问题，其中只有 1 个是本轮 primary question，其余是支持性问题或未知边界；
- `MechanismThread` 是一条可检验的局部传导，例如“渠道重构 → 回款质量 → 经营现金”，每条线程有自己的 H-A/H-B、证据上限和观察时钟；
- `OutcomeVector` 将客户、运营、竞争、现金、资本回报、杠杆和永久损失拆成独立结算单元，不生成无意义的总分；
- `ResolutionAndLearning` 记录哪些判断得到支持、被削弱、无法诊断，以及下一家公司具体改变了什么。

这使系统同时保留**公司全景**和**局部可证伪性**：公司可以在多个维度形成有边界的判断，但只有某条线程真正具备比较和结果合同，才获得相应的因果权限。单项 `UNKNOWN` 不得把整个 episode 降成 `NO_PRIMARY`；同样，多项局部支持也不得自动升级为“管理层优秀”或“企业整体高质量”。

### 3.2 四级准入：证据深度逐步增加，而不是一票否决

| 层级 | 研究问题 | 最小条件 | 允许产物 | 禁止升级 |
|---|---|---|---|---|
| `E0_CONTEXT` | 当时公司和行业是什么状态？ | cutoff、身份、来源时间角色 | 行业史、生命周期、企业画像、研究议程 | 经营效果、选择方法 |
| `E1_RECONSTRUCTION` | 公司如何赚钱、竞争、占用资本？ | 责任边界、经营系统图、决策账本、关键未知 | 多维企业判断练习、Teaching/CJO mirror | 因果归因、方法迁移 |
| `E2_MECHANISM_PROBE` | 一个关键行动或机制是否沿预写箭头传导？ | 行动/状态、H-A/H-B、至少一个可结算中介或终局结果 | 窄机制结算、边界 learning candidate | 整家公司因果结论 |
| `E3_COMPARATIVE_LAB` | 相对反方或同行是否更好？ | 仅针对该 estimand 的 target-trial 条件、独立结果和公平基线 | 方向性 Comparative candidate | 自动方法冻结、CJO、买点 |
| `E4_TRANSFER_AND_UTILITY` | 这条学习是否改善下一家公司和投资决策？ | 不同公司应用、公司/时间 holdout、决策效用 A/B | 方法候选、有限报告授权 | 以单案证明普遍能力 |

`E0/E1` 不需要等 H2 或完整同行；`E2` 只需为一个机制线程补齐相称证据；`E3` 才启用 V5 的严格 panel 和结果防火墙；`E4` 才讨论方法发布和报告消费。这个层级解决“第一个样本太严格”和“训练判断太单一”两个问题，但不放松 PIT 或结果隔离。

### 3.3 同一 episode 的六种训练视图

同一份冻结 episode 可以投影成不同训练视图，视图不复制经济事实，也不改变权限：

| 视图 | 训练对象 | 主要输出 |
|---|---|---|
| `STATE_VIEW` | 行业/生命周期/企业重建 | 当时的公司状态、进入退出、关键约束 |
| `DECISION_VIEW` | 管理层与经营者训练 | 可选方案、资源承诺、执行、适应和停止条件 |
| `MECHANISM_VIEW` | 机制线程/Teaching | H-A/H-B、反方、证据鉴别力、边界 |
| `FORECAST_VIEW` | 状态预测/轨迹参照 | 概率、区间、弃权、校准和 coverage |
| `COMPARATIVE_VIEW` | V5/因果实验室 | 单个 estimand 的相对结算 |
| `INVESTMENT_VIEW` | CJO/估值/买点 | 只有冻结 CJO 后的正常利润、owner cash、预期差和条件 BuyBand |

视图之间只沿权限方向流动。`STATE_VIEW` 可以产生研究问题，不能产生当前公司事实；`FORECAST_VIEW` 可以产生校准 policy，不能产生因果箭头；`COMPARATIVE_VIEW` 可以产生局部机制 candidate，不能跳过 transfer；`INVESTMENT_VIEW` 不能把价格结果反写到前面的状态或机制。

### 3.4 IndustryLearningBlock：行业认知的外层训练单位

单个 `EnterpriseJudgmentEpisode` 只能形成指定公司、cutoff 和问题下的判断。真实行业认知需要一个更外层的编排单位：

> **`IndustryLearningBlock = industry × mechanism-defined arena × structural epochs × company archetypes × longitudinal episodes`**

它同样是组合读模型，不新增平行事实库。它编排已有 `IndustryHistoryUniverse`、生命周期账本和多个 `EnterpriseJudgmentEpisode`，回答四个问题：

1. 行业的客户任务、价值链、供需约束、竞争规则和资本强度如何随时期改变；
2. 不同自身条件的公司在同一外部环境下为什么选择不同决策；
3. 决策质量、执行能力、适应能力、外部冲击和最终结果分别是什么；
4. 哪些关系可在条件成立时迁移，哪些只是单公司、单时期事实。

一个真实 block 至少包含以下结构，但不以固定公司数量作为全局门：

```text
IndustryEpochMap
  + cutoff-by-cutoff risk set and lifecycle
  + CompanyArchetypeMap
  + company × cutoff EnterpriseJudgmentEpisode[]
  + DecisionHeterogeneityMatrix
  + ConditionalMechanismSynthesis
  + unresolved questions and next sampling decision
```

`CompanyArchetypeMap` 按客户、成本/资本结构、渠道、资产负债表、控制与组织能力定义差异，不按“同省份”或表面行业标签自动分组。`DecisionHeterogeneityMatrix` 比较相似外部条件下的不同约束、可行选项、实际决策、资源承诺、执行和适应；它是参照系，不自动成为反事实 control。

`ConditionalMechanismSynthesis` 的最小表达是：

```text
WHEN <industry epoch + company state + constraints>
DECISION <action or no-action>
MAY OPERATE THROUGH <mechanism thread>
OBSERVED AS <customer / operating / cash / capital cells>
UNLESS <moderators and break conditions>
EVIDENCE CEILING <teaching / mechanism / comparative / transferred>
```

它禁止输出“扩产总是有效”“龙头管理层更优秀”或统一公司总分。公司差异和时期差异不是噪声，而是 `moderators / transport conditions / break conditions`。行业知识只有在不同公司或时期重现、保留反例并经独立审阅后，才可从 `RESEARCH_AGENDA` 升格为候选方法；否则只是一组有来源的条件化问题。

### 3.5 历史训练的纵横运行顺序

历史训练采用逐 cutoff 展开，而不是先阅读完整行业结局再回填：

```text
cutoff t: freeze IndustryEpoch + company risk set
  -> freeze each selected company E0/E1 reconstruction
  -> freeze 1 primary and 2--4 supporting questions
  -> optionally freeze forecasts or mechanism probes
  -> reveal only the next authorized disclosure window
  -> settle outcome cells independently
  -> compare company responses and update t+1 research questions
```

同一公司多个 cutoff 属于一个 `company_cluster_id`，用于学习适应和决策序列，不能冒充多个独立公司样本。行业 block 必须保留失败、退出、被收购和资料删失对象；不能只从幸存者中总结“成功经验”。历史回放标记 `MODEL_MEMORY_MITIGATED`，可以训练流程和条件化认识，但不能单独证明实时预测优势。

首个真实 block 优先复用已登记的中国水泥 H1：五家公司和六个 cutoff 用于行业/生命周期与 E0 重建，按预声明的材料性和字段覆盖选择纵向 E1 深挖；H2 的 `NO_PRIMARY_ACTION_SCOPE` 只关闭该 Comparative 候选，不影响 block、公司重建或局部机制探针。任何后续 outcome 仍须在相应 freeze 后由独立角色按授权窗口揭示。

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

主训练单位是 `EnterpriseJudgmentEpisode = 公司 x cutoff x 企业状态 x 决策序列 x 机制线程 x 结果向量`。它是现有 canonical artifacts 的组合读模型，不新增第四张图；`DecisionEpisode` 只保留为其中一条 `MechanismThread` 的行动因果研究对象。

因此，一个公司可以在同一个 cutoff 形成多维的企业重建，同时只有一条线程进入 `Comparative`；一个结果指标无法结算，也只影响对应 `OutcomeCell`，不会抹掉其他已具备证据的判断。实现上应优先提供 `episode_manifest`/read model 和 cell-level status，不应先建立全局综合评分。

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

### 10.1 V2 实施工作包

| 工作包 | 目标 | 主要产物 | 不做什么 |
|---|---|---|---|
| `J0 CONTRACT` | 固定 EnterpriseJudgmentEpisode 的组合语义和权限梯度 | episode manifest、claim/output matrix、cell status 语义 | 不追溯升级既有 episode |
| `J1 INDUSTRY BLOCK` | 让一个行业按时期、公司状态和生命周期形成纵横训练框架 | IndustryLearningBlock manifest、epoch/archetype/heterogeneity/synthesis views | 不把行业叙事变成基准率或公司事实 |
| `J1A RECONSTRUCTION` | 让一家公司在一个 cutoff 形成多维企业状态和决策序列 | `EnterpriseContextSnapshot`、OperatingSystemModel、DecisionLedger slice | 不要求同行或已实施行动 |
| `J2 THREADS` | 将全景判断拆成 1 个 primary + 2--4 个 supporting mechanism threads | H-A/H-B、证据鉴别矩阵、观察时钟、结果合同 | 不把所有线程设为硬门 |
| `J3 FORECAST` | 对状态向量做逐维概率、区间和弃权校准 | Forecast bundle、coverage、proper scores、error attribution | 不从 forecast 生成因果或 CJO |
| `J4 COMPARATIVE` | 只有相对因果主张出现时启用 V5/target-trial 约束 | panel freeze、独立 settlement、estimand resolution | 不以 Comparative 阻断 J1--J3 |
| `J5 TRANSFER` | 将一条已诊断学习改变不同公司的冻结前字段 | TransportContract、application receipt、review | 不复制整家公司结论 |
| `J6 INVESTMENT` | 将冻结 CJO 的关键线程传播到价值和价格 | normal earnings、owner cash、ExpectationGap、BuyBand | 不用价格结果改写企业判断 |
| `J7 DECISION_UTILITY` | 证明增强研究比简单基线更能改善用户判断 | same-cutoff paired receipt、holdout、materiality review | 不以报告长度或股价胜负评分 |

实施顺序是 `J0 → J1/J1A/J2/J3`，`J4` 与其并行但独立，`J5 → J6 → J7` 逐级解锁。当前已有控制层和 Forecast/报告接线可复用；真实 Comparative 仍是 `J4` 的未完成支线，不再是 `J1/J1A` 的前置条件。

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

### 12.1 V2 额外验收

1. 一个没有 comparator 的公司，可以完成 `E0_CONTEXT` 和 `E1_RECONSTRUCTION`，并产出多维状态、决策账本、关键未知和研究议程；
2. 一个结果指标的 `MEASUREMENT_MISMATCH` 不会让同一 episode 的其他证据线程被删除或获得伪造结论；
3. 一个缺少完整同行的行动，可以降级为 `E2_MECHANISM_PROBE / TEACHING_ONLY`，而不是被误报为全局训练阻塞；
4. `Comparative` 只冻结自身 estimand、panel 和 outcome contract，不改变 episode 的企业全景或其他线程；
5. `Forecast` 可以对多个企业维度逐项评分和弃权，但不产生“总冠军”、因果结论或投资授权；
6. 任何 learning transfer 都能指出下一家公司实际改变的字段、证据顺序、反方或停止规则，并由独立 reviewer 复核；
7. CJO、估值和 BuyBand 只消费达到相应证据上限的线程，并能列出未覆盖维度和翻转条件；
8. 同 cutoff、同证据预算下，增强研究相对简单基线的改进必须表现为材料未知、错误避免或判断区间变化，而不是文字增加。
9. 一个 IndustryLearningBlock 能按 cutoff 保留行业时期、公司 archetype、生命周期和决策差异，并输出带 moderators、break conditions 与证据上限的条件化综合；不得输出统一公司总分或无条件行业格言。

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
- [Hernán and Robins, Target Trial Emulation](https://doi.org/10.1093/aje/kwv254)：只在 Comparative 线程冻结 eligibility、time zero、intervention、comparator、outcome、follow-up 和 censoring；不把年报叙事自动变成因果识别。
- [Pearl and Bareinboim, Transportability](https://arxiv.org/abs/1503.01603)：跨公司迁移必须声明 invariants、moderators、目标差异和 break conditions；不迁移整案结论。
- [Collier, Understanding Process Tracing](https://www.cambridge.org/core/journals/ps-political-science-and-politics/article/understanding-process-tracing/183A057AD6A36783E678CB37440346D1) 与 [Heuer, Psychology of Intelligence Analysis](https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/)：支持竞争解释和证据鉴别矩阵，但不把证据条数加总为因果分数。
- [Shumway, The Delisting Bias in CRSP Data](https://doi.org/10.1111/j.1540-6261.1997.tb03818.x)：支持保留退出对象、显式处理删失和竞争事件；不提供企业失败概率。
- [Qlib](https://github.com/microsoft/qlib) 与 [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT)：分别借鉴数据集、时间切分、模型、回测/记录和金融语言模型工具的工程分层；它们不是企业因果判断或投资能力的证据。
- [FActScore](https://github.com/shmsw25/FActScore)：借鉴长报告拆成原子主张并关联证据的发布前检查；事实支持率不能替代经济机制和投资决策效用。

这些依据只支持系统设计，不构成任何公司、行业、估值或买点的投资证据。
