# Turtle Agent 企业判断系统总设计

> 状态：`OFFLINE_CONTROL_IMPLEMENTED / SYNTHETIC_VALIDATED / PIT_FORECAST_EPOCH_ADOPTED / REAL_CAUSAL_PIT_AND_CANONICAL_ADOPTION_PENDING`
>
> 日期：2026-08-25
>
> 本文是面向中心目标的上层设计。它不替代 PIT 样本准入、来源包、结果结算、估值模型或报告质量契约；这些模块必须在本文定义的对象、方向和权限内实现。

## 0. 当前实施事实与不变边界

`73e318d` 已实现 V3 离线控制层的 EnterpriseSystemModel、ManagementDecisionLedger、ResponsibilityUnit、CompetitiveArena、DecisionEpisode、LearningTransfer、状态/权限、局部 delta、scope bridge、TransportContract 和 CJO→normal earnings→owner cash→ExpectationGap→BuyBand synthetic propagation。`f53a200` 已将 V5 的独立 pre-outcome review、designer/reviewer/custodian 角色分离和 seal binding 纳入 canonical selection lifecycle；`aa37c61` 与 `49b6c4d` 已建立严格 Stage-0 static-PDF intake。

这些是离线、synthetic-validated 控制能力，不是第一条真实训练样本，更不等于已将 V3 的 `cjo` 接管既有 Golden Report、ResearchBundle 或生产 canonical CJO。真实 PIT、跨公司迁移、方法冻结、R-103 留出和报告使用仍未获授权。正式 Stage-0 只接收独立 curator 提供的、cutoff-before、offline static CNINFO PDF package；Agent 不得用 CNINFO UI、全文检索、issuer/stock/detail 页面补查候选、行动或结果。

### 0.1 Forecast epoch amendment

`PITCompanyStateForecast` 是日常训练与校准工具，不是 Turtle 的产品中心，也不是 V5 action trial 的简化版。它冻结 `company × cutoff` 当时可得的企业状态及未来 1/3/5 年六维轨迹：正常利润、ROIC/经营利润率、现金转换与资本开支、杠杆与财务韧性、竞争位置、永久损失风险。其最小来源是已冻结的 Industry Risk Set/H1 static packet；不需要公告行动、time zero、反事实控制组或 H2。

新的 `Forecast V2` 只能在一个已冻结的 `Decision Contract` 后创建。该 contract 固定公司、cutoff、持有时域、永久损失约束、会翻转判断的问题、唯一 H1 evidence budget 与 Judgment Owner/Challenger/Custodian 角色，并显式禁止 price、机会成本与 outcome access。现有水泥 V1 forecast 不可追溯补挂；它保留为 `MODEL_MEMORY_MITIGATED` 流程验证，不能被伪装成 contract-first replay。

已实现的 `HistoricalCJOTrainingMirror` 只在 V2 forecast、同一 contract 和一个 `ENTERPRISE_MODEL / FROZEN / TEACHING_ONLY` V3 CJO 之间做离线一致性校验：模型的 issuer/as-of 必须等于 forecast issuer/cutoff；六个 forecast 维度逐一成为 CJO 的 review question 或 unknown guardrail；mirror 的唯一下游是 `CJO_TRAINING_MIRROR / RESEARCH_AGENDA`。它显式关闭 normal earnings、owner cash、ExpectationGap、BuyBand、investment input 与 report use，也不把 V3 offline CJO 复制或升级为 production canonical object。因而该接线完成历史 replay 的经营判断镜像边界，不构成 Investment Overlay。

`RelativeTrajectoryTournament` 只将同一 cutoff 的多个 forecast 逐维并列为参照轨迹。它不得声称同行是未处理控制组，不假设无外溢或无平行动作，也不得合成“总冠军”。`ForecastSettlement` 由独立 custodian 在结果公开后逐维结算；它输出 proper score、coverage 和错误归因，而不是单一胜率。独立 challenger 审阅的 `ForecastErrorAttribution` 只可直接形成 calibration、coverage、状态定义、不确定性与 baseline-performance 的下一 cutoff policy；evidence priority 与 rival-hypothesis method 必须停在 paired-ablation + 双轴 holdout candidate。

`CAUSAL_ACTION_EPISODE` 仍由 H2/V5 负责，但被降为独立、低频高级 lane：它只回答“这项已实施行动是否导致结果”。Forecast epoch 不改变 V5 的 action、time zero、scope、D3/D4、source firewall、custodian 或 review 契约。

### 0.2 Forecast permissions and unknowns

`EVIDENCE_INELIGIBLE` 是 acquisition coverage：来源不足以支撑该维度，系统不预测；`MODEL_UNCERTAIN` 是资料合格但未来本来不确定，系统必须给相对 cutoff baseline 的概率分布。两者不能混写为 `NO_PRIMARY`，也不能以只评主动回答部分来虚增准确率。

每个 forecast、tournament、shadow 和 settlement 的输出权限都限于 `FORECAST_EVALUATION_ONLY / RESEARCH_AGENDA`。它们不得直接升级 CJO、normal earnings、owner cash、ExpectationGap、BuyBand、报告或投资输入。只有独立审阅的 `ForecastErrorAttribution` 能以 `FORECAST_POLICY_ONLY` 输出上述受限方法 policy；它不能输出公司事实、因果箭头、估值或 BuyBand。只有在另一个显式估值 epoch 中，冻结 CJO 才能消费已授权的公司状态判断。

当前水泥 pilot 保留五份 `Forecast V1` 作为 `MODEL_MEMORY_MITIGATED` 的流程验证；该对象不可追溯升级。新的五份 `Forecast V2` 与三家 reference tournament 已在隔离 namespace 按 contract-first 顺序冻结：每份 V2 均绑定同一已登记 H1 static receipt、同公司/issuer/cutoff 的 Decision Contract 及指定 outcome custodian。五份 V2 已可纯投影为 `MIXED / TEACHING_ONLY` CJO training mirror；该投影不写第二份 canonical CJO，全部 overlay 均为 `NOT_AUTHORIZED`。独立 custodian 已完成 V2 的 access authorization 和逐 cell settlement：48 个冻结的 `EVIDENCE_INELIGIBLE` 保持不变，42 个有官方年报但不能唯一映射的 cells 是 `MEASUREMENT_MISMATCH`；没有 `OBSERVED`、分数、校准或公司结论。这是保护性结算，说明 V2 仍缺 Outcome Measurement Contract，不能以资料“相关”替代标签映射。

新的 `Forecast V3` 以 `Decision Contract → Outcome Measurement Contract → Forecast → outcome access → custodian observation receipt → settlement` 作为唯一顺序。Measurement Contract 是 custodian 可独立读取的静态对象：每个 cell 预先定义公司/责任边界、结果期、单位、允许官方年报 field identity、ordinal thresholds 或 binary event definition、标签顺序和 mismatch rules；它不含预测概率、理由、同行排序、价格或结果。V3 forecast/H1/risk-set cutoff 必须一致且 measurement contract 必须先冻结；custodian 将实际来源页、字段、期间、责任边界、单位和值写入不可变 observation receipt，V3 `OBSERVED` 只可引用字段映射精确匹配的 receipt，`MEASUREMENT_MISMATCH` 也必须引用 receipt 且其原因必须在合同中预先冻结。它只允许新的 cutoff/company 使用，不能补救或升级 V2；V1/V2 不得评分或生成 active learning policy。`R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821` 的 2027 两个已冻结经营信号另登记为 `MECHANISM_SIGNAL_PROBE` shadow；它只等待外部结果，不能进入 CJO、causal lane、learning 或报告。

`Forecast V4` 在上述 V3 时钟之前加入一个 acquisition-only gate：`same H1 static receipt → independent curator field extraction → frozen preforecast evidence receipt → V4 forecast`。它不是补写 V3，也不扩大 H1 的 artifact 集；curator 只能逐页摘录原已声明 static PDF 中的 cutoff-visible 数值、单位和责任边界，control plane 随后将 closed extraction 编译为不可变 receipt。V4 的 `MODEL_UNCERTAIN` 维度必须逐一引用 receipt 内的 exact `source_id × field_id`，使预测对象不再把“年报可取得”误作“已有可用原始字段”。该 receipt 仍是 evidence-only：不含 forecast 概率、结果、价格、CJO 或报告权限；V4 仍须在同一 Decision Contract 和 Outcome Measurement Contract 后冻结，并沿用 custodian-only observation/settlement 边界。

## 1. 中心目标

Turtle 的中心目标不是生成更多报告，也不是让模型记住更多案例，而是让 Agent 更可靠地回答两个连续问题：

1. **企业判断**：公司靠什么经营机制创造或毁灭长期普通股经济价值，管理层已经实施的关键决策会如何传导到客户、竞争、单位经济、现金和资本回报？
2. **投资决策**：在企业判断冻结后，当前价格隐含了什么，正常利润和 owner cash 能支持什么价值，什么价格才提供足够的 3/5 年预期回报与永久损失保护？

第二个问题必须消费第一个问题的结果，不能反过来改写第一个问题。

系统训练的不是基础模型权重，而是一套能被复核、能改变下一家公司研究行为、能在未知结果环境中保持纪律的研究系统：

```text
公司与行业状态
  -> 持续企业系统模型与管理层决策序列
  -> 管理层已实施的经营决策
  -> 竞争经济体与责任边界
  -> 客户/竞争 -> 单位经济 -> 现金 -> 资本回报
  -> 企业判断与可证伪前瞻路径
  -> 正常利润 / owner cash / 价值 / 价格隐含预期
  -> 3/5 年回报与买入价格
```

### 1.1 成功的定义

系统成熟的可观察证据是：

- Agent 在结果揭示前，能先说清楚公司、责任单元、竞争经济体和关键决策，而不是先寻找一个“好案例”；
- Agent 能维护公司经营系统随时间的状态变化，而不是用一个 episode 或一份报告代表整家公司；
- Agent 能把同一经营机制拆成可检验的箭头，并主动保留最强反方和 `UNKNOWN`；
- Agent 能区分管理层在当时信息下的决策质量、执行质量、外部冲击和事后结果，不用一次成败给管理层贴标签；
- Agent 不再把投产、销量、收入、毛利、正 OCF 或存活直接当作长期价值成立；
- 一个学习结果能改变另一家公司冻结前的字段、证据顺序、机制分叉或停止规则，并由 reviewer 复核；
- 企业判断冻结后，关键经营驱动仍能穿透正常利润、普通股现金、价值、回报和买点；
- 在未见公司或未知结果的部署哨兵中，系统会正确停下，而不是用流畅叙事补齐未知。

报告数量、Token、调用量、案例卡数量、Agent 投票数和单一公司深挖深度都不能作为判断力的替代指标。

### 1.2 非目标

本系统当前不承诺：

- 用历史回放证明未来股价预测准确或组合收益优于基准；
- 让历史结果已知的案例伪装成实时预测样本；
- 用行业标签、同省份或同一公告类型自动证明同行可比；
- 用更多 validator 阻止所有不确定性；
- 用黄金报告的写作质量替代企业机制证据；
- 自动交易、自动调整真实账户或把 Turtle 记忆作为投资事实真源。

## 2. 产品形态：两条相连但不倒灌的轨

系统由四层组成：

```text
证据层 Evidence Plane
  官方来源、截止日、责任边界、可观察测量面
        |
        v
判断层 Judgment Plane
  企业系统图、竞争场域、决策 episode、反方、UNKNOWN、CJO
        |
        v
投资层 Investment Plane
  正常利润、owner cash、资本配置、价值、价格、回报、买点
        |
        v
交付层 Delivery Plane
  黄金报告、技术附录、ResearchBundle、用户可审阅结论
```

横向的 `Learning Plane` 读取历史训练的冻结对象和结果，但只能把经审阅的窄方法改变写回下一家公司的**冻结前研究输入**。它不能把事后结论写成当前事实，也不能绕过 CJO 冻结直接修改投资结论。

### 2.0 M1–M10：唯一职责、写入边界与读取方向

四层是阅读方向；M1–M10 是实施责任，不能再以另一套平行对象替代。

| 模块 | 唯一 writer / 当前实现 | 允许读取者与边界 |
|---|---|---|
| M1 官方证据与 PIT 围栏 | curator static package、source contract；H1 strict intake | M2–M5 只读 cutoff-before identity；不得由研究 Agent UI 补查 |
| M2 企业经营系统图 | V3 `EnterpriseSystemModel` 的局部版本/delta | M3/M4/M6；episode 不能升级公司整体结论 |
| M3 竞争机制与反方 | V3 arena、HypothesisRegistry、diagnostic matrix | M4/M5；行业或地理标签不授予 comparability |
| M4 公司判断与前瞻合约 | V3 CJO/ledger/episode offline artifact | M5/M9 仅在未来 canonical binding 授权后读取 |
| M5 结果采集与分层结算 | V5 custodian receipt 与 derived resolution | M6 只读；研究者/reviewer 不读取 raw outcome |
| M6 诊断与学习应用 | LearningTransfer、review receipt | 只能改另一家公司冻结前字段，不回写已结算事实 |
| M7 行业经验工厂 | 未来经接纳的多案例机制资产 | M3/M4/M9；单一案例不得升格行业规律 |
| M8 宏观综合 | 未来跨行业共同变量与暴露投影 | M3/M4；不得代替企业责任边界 |
| M9 黄金报告编译与验收 | 既有 Golden Report service 的只读投影 | 只消费获授权 canonical read model，不反写判断/结果 |
| M10 判断反馈控制面 | V5 freeze/event append-only control plane | 证明身份、时间、顺序与权限；不解释经济机制 |

### 2.1 Company Judgment Object（CJO）

CJO 是企业判断轨的唯一冻结边界。它至少包含：

- 公司在观察时点的 `EnterpriseSystemModel` 及其关键 stocks、flows、反馈和瓶颈；
- 责任单元与合并/分部范围；
- 竞争经济体及其机制定义；
- 已实施的关键经营决策及 `ManagementDecisionLedger` 的纵向模式；
- `HypothesisRegistry`、竞争解释和 hypothesis-evidence diagnostic matrix；
- 关键因果箭头、最强反方、简单基线与禁止替代；
- 每个箭头的证据、观察时钟、测量合同和 `UNKNOWN`；
- 管理层质量、资本配置和普通股索取权的判断；
- 对正常利润、owner cash、永久损失和价值的传播方向；
- 结论、置信边界、翻转条件及下一披露节点。

CJO 生命周期是 `DRAFT / EVIDENCE_OPEN / REVIEW_READY / FROZEN / REOPENED / RETIRED`；`NO_PRIMARY / MIXED / SELECTIVE_SUPPORT / A_ONLY / B_ONLY / UNKNOWN` 是独立的认识结论，不能混入生命周期。`SELECTIVE_SUPPORT` 是多假设问题的通用表达，`A_ONLY/B_ONLY` 只是二元 episode 的兼容投影。`FROZEN` 不是“公司一定会按主路径发展”，而是“在指定 cutoff 的证据、认识结论和未知项下，当前版本已经停止变动，并获得相应的下游权限”。其中只有满足投资层入口契约的冻结 CJO 才能进入生产买点。

### 2.2 Investment Overlay（投资叠加层）

投资层只消费冻结的 CJO、经核实财务数据和价格快照，形成：

```text
CJO 中心路径
  -> 正常化收入 / 单位经济 / 经营成本
  -> 正常税后经营利润
  -> owner cash / FCFF / 普通股可达现金
  -> 资本配置、债务、NCI、现金可达性
  -> NAV / EPV / GG / DDM / DCF 等适用价值身份
  -> 当前价格隐含的经营要求与 CJO 可行范围
  -> 预期差、3/5 年回报分布与永久损失情景
  -> 条件化买入区间、仓位和翻转条件
```

估值方法按公司价值状态和现金归属选择，不能把 NAV、EPV、GG、DDM、成长价值机械平均成一个数字。每个价格结论必须说明：价值身份、回报路径、终值规则、要求回报、资本需求、现金可达性和最强反方。

价格可以产生一个新的研究问题，例如“市场是否已经定价渠道修复”，但不能反向把渠道修复写成已成立，也不能改写 CJO 的 `H-A / H-B`、竞争场域或公司责任边界。

当前 `CJOValuationReturnSnapshot` / `CJOValuationReturnSettlement` 是 G6 的 synthetic 结算边界：snapshot 仅消费 `FROZEN / INVESTMENT_INPUT` CJO 与封闭 financial contract；settlement 由独立 custodian 分开验证 normal earnings、owner cash、由 actual owner cash 重算的 valuation identity、逐年现金流 IRR 和永久损失状态。任何 operating、valuation、market 或 `CENSORED / UNKNOWN` 结果都不回写 CJO，且单个 settlement 只形成 `CANDIDATE_ONLY` 估值/买点 policy；它不等同 production canonical overlay、真实 outcome access 或报告授权。

## 3. 六个核心对象

### 3.1 `EnterpriseSystemModel`：公司作为持续经营系统

企业判断的主对象不是一串互不相干的公告或 episode，而是公司在指定 cutoff 下的持续经营系统。`EnterpriseSystemModel` 至少回答：

| 组成 | 要回答的问题 |
|---|---|
| 客户任务与需求形成 | 客户为什么买、用什么替代、购买频率和转换成本如何变化？ |
| 产品与价值交付 | 公司以什么产品、渠道、服务和交付网络完成客户任务？ |
| 关键资源与能力 | 客户、渠道、人才、技术、产能、数据、品牌和供应关系中，哪些是会积累或流失的经济存量？ |
| 瓶颈与反馈 | 哪个约束限制增长或现金转化，哪些强化/抑制回路会放大或逆转结果？ |
| 价值获取与议价 | 客户、供应商、员工、渠道、监管者和资本提供者如何分配价值？ |
| 再投资引擎 | 增量资本投向哪里、回报来自什么、需要多久、何时耗尽或转坏？ |
| 治理与普通股索取权 | 决策权、激励、资本配置和现金归属如何影响普通股？ |
| 财务传播 | 单位经济、固定成本、营运资本、资本开支和融资如何进入 owner cash？ |

模型只保留会改变经营质量、永久损失、价值或买点的 material stocks、flows 和关系；不要求为所有公司建立大型仿真。它可以直接实现为带版本的 JSON/关系表，并投影到现有 `MechanismGraph`，不新增第四张图。

企业模型不强制只有一个客户、一条价值链或一个竞争场域。实现必须允许一个公司模型下存在多个 `ResponsibilityUnit`、`CompetitiveArena` 和 measurement scope；关系边至少能声明参与者一侧、交互接口、跨侧反馈和观察边界。多边平台、控股公司和多分部制造企业因此仍使用同一对象，只是拥有多个有边界的局部系统。不能把多个 side 的总用户、总收入或总毛利压成单一客户/单位经济字段。

每个 `DecisionEpisode` 必须声明它打算改变或检验模型中的哪些节点、边和状态；结算后只更新这些局部位置。单个 episode 不能自动升级为“公司质量”或“管理层质量”的整体结论。

### 3.2 `ManagementDecisionLedger`：管理层质量来自纵向决策序列

管理层质量不能从一次结果、一次访谈或一项成功并购推出。账本按当时可得信息记录经营、产品/渠道、产能、资本配置、治理和激励决策，并把以下身份分开：

```text
decision context / cutoff
  -> 当时目标、约束、可行替代与已知 UNKNOWN
  -> 预期机制、投入资本、可逆性、停止条件和利益冲突
  -> ex-ante decision quality: SOUND / WEAK / INDETERMINATE
  -> execution observation
  -> mechanism outcome / owner-cash outcome
  -> external shock and luck attribution
  -> lesson and subsequent management adaptation
```

`ex-ante decision quality` 只评价当时的框架、替代方案、信息、权衡、推理和承诺，不因后来偶然成功而重写；`outcome` 只记录结果，不因结果好就证明过程好。只有跨多个时期和至少两个决策类别出现重复模式，CJO 才能形成有限的管理层判断；否则保持 `INSUFFICIENT_HISTORY`。

### 3.3 `ResponsibilityUnit`：谁负责、谁记账、谁承载经济

企业判断中的“公司”必须拆成四个范围，不能用上市公司名称代替：

| 范围 | 要回答的问题 | 常见错误 |
|---|---|---|
| `ACCOUNTING_PERIMETER` | D3/D4/D5 属于哪个法律/合并实体，谁的报表能观察它？ | 用集团收入证明某子业务的现金回收 |
| `DECISION_SCOPE` | 管理层实际实施了什么决策，责任在哪个管理边界？ | 用计划、设计产能或宣传替代已实施行动 |
| `ECONOMIC_CARRIER` | 决策影响哪个产线、网络、产品、客户任务或资产组合？ | 把集团层叙事直接套到一个产品 |
| `MEASUREMENT_SURFACE` | 官方资料实际观察到哪些指标，口径和期间是什么？ | 看到总毛利就声称产品单位经济改善 |

一个责任单元可以跨地域，也可以只覆盖集团内一个分部。若责任单元无法与 D3 经营结果和 D4 普通股现金分别对应，必须降为 `UNKNOWN` 或 `NO_PRIMARY`。

一个企业可以同时拥有多个责任单元和多个竞争场域；`CompetitiveArena` 不是上市公司级的单值标签。对于平台或生态系统，arena 内的参与者一侧和接口必须单独登记，跨侧反馈必须作为关系而非公司总量推断；对于多业务集团，不同客户任务、替代集合或价格形成机制应拆为不同 arena 或 measurement scope。

### 3.4 `CompetitiveArena`：在哪里发生竞争

共同市场不是行政区字段，而是**由机制定义的共同竞争经济体**。一个 arena 只有在以下问题得到回答后才成立：

- 客户正在完成什么任务？
- 哪些产品或服务在客户眼中可替代？
- 竞争者通过什么接口争夺订单、价格、渠道、运力、产能或留存？
- 共同经济状态或冲击如何同时作用于成员？
- 竞争和传导的时间窗口是什么？
- 哪些维度必须相等、必须重叠、只需暴露相似条件，哪些维度不要求一致？

地理只是一个条件变量：

- 区域价格、运力、本地渠道和服务半径是机制时，地理可能是 `REQUIRED_EQUAL` 或 `REQUIRED_OVERLAP`；
- 全国价格体系、全国品牌和全国渠道时，省份通常只是暴露结构，不是硬门；
- 出口制造业在全球细分产品和客户任务上竞争时，国内省份可以是 `NOT_REQUIRED`；
- 跨行业公司只有在客户任务、竞争接口和经济冲击真正重叠时才可比较。

`industry_id` 只能负责路由、发现和先验整理，不能单独证明 arena。同行成员也必须声明角色：

- `EXTERNAL_SHOCK_COMPARATOR`：承受共同冲击，用于识别共同环境；
- `EQUILIBRIUM_RESPONSE_WITNESS`：观察竞争系统对相似动作或状态的反应；
- `FALSIFIER`：专门挑战主路径，而非为了凑数量；
- `NOT_COMPARABLE`：保留在筛选记录中，但不能进入因果面板。

同行的任务不是替代目标公司的事实，而是帮助区分“公司做得好”与“行业一起变好”。

### 3.5 `DecisionEpisode`：训练的最小变化单位

训练的最小变化单位是“公司在 cutoff 前已经实施的一项经营决策及其经济传导”，不是公司、行业或公告本身；企业整体判断单位仍是持续的 `EnterpriseSystemModel`。一个 episode 至少包括：

```text
cutoff / PIT 时间身份
  -> 已实施动作与决策目的
  -> responsibility unit
  -> competitive arena
  -> EnterpriseSystemModel 的 pre-state / intended delta
  -> 机制拓扑
  -> HypothesisRegistry / 最强反方 / 共同机制
  -> D1 决策 -> D2 客户/竞争 -> D3 经营 -> D4 owner cash -> D5 资本回报
  -> 各层独立测量合同与结果期
  -> 结算：A_ONLY / B_ONLY / MIXED / UNKNOWN / NOT_DIAGNOSTIC
```

机制拓扑先于字段采集：

1. `CUSTOMER_RESPONSE`：决策改变客户价值或竞争位置，先观察客户/竞争，再看经营和现金；
2. `COST_RESTRUCTURING`：决策改变成本、利用率或交付网络；默认以成本/利用率/交付字段作 `DIAGNOSTIC_NON_VOTER`，但在 action 明确具有客户传导、并有三期 source-bound D2 observation 时才可采用 `CENTRAL_VOTER` D2；两条路径都必须有独立 D3/D4 结果；
3. `PRODUCT_OR_INNOVATION`：决策改变采用、服务负荷或产品单位经济，必须把产品经济与集团财务分开；
4. `CAPITAL_ALLOCATION_OR_INTEGRATION`：并购、参股、整合和资本配置另立契约，不强行塞入经营竞争 episode。

一个 episode 可以因资料不足而不能进入正式方向性训练，但仍可作为机制实验或边界教学。这样“第一个正式样本未出现”不会阻断企业系统建模、管理决策复盘或整个训练系统。

### 3.6 `LearningTransfer`：结果怎样改变下一家公司

学习不是“写了一份复盘”，而是一个可追踪的迁移事件：

```text
结果/边界失败
  -> 经济影响
  -> 根因分类
  -> 禁止的替代解释
  -> 可执行的方法改变
  -> 下一家不同公司的冻结前字段改变
  -> 独立 reviewer 确认迁移确实发生
```

每个 learning transfer 必须回答：

- 这次失败是 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL` 还是 `WRITING`？
- 缺少什么事实或身份，导致什么经济判断可能错误？
- 哪个假设不能再默认？
- 下一个对象的哪一个冻结前字段、取证顺序、测量合同或停止规则会改变？
- 该改变在哪个不同公司或时期被复核？

每个 transfer 还必须内嵌一个 `TransportContract`：来源机制中哪些关系预计保持不变、目标对象有哪些差异、哪些 moderator 会改变方向或强度、需要先观察什么、什么条件一出现就停止迁移。同行、行业、地区或公司规模相似都不能单独授予迁移权限。

只有改变下一对象并经过复核的学习，才进入可复用方法；不能用 learning note 数量或 reviewer 票数作为能力分数。

## 4. 训练体系：渐进保真度，而非单一高门

```text
Enterprise Model Lab / Management Decision Lab
  -> Mechanism Lab
  -> Boundary Learning
  -> PIT Selection Episode
  -> Cross-Company Transfer
  -> Historical Holdout
  -> CJO -> Quant
  -> Golden Report / Investment Decision
  -> Live Sentinel Calibration
```

### 4.1 `Enterprise Model Lab`

目的：先训练 Agent 解释公司如何持续创造、获取和再投资经济价值，再进入某个单次决策。

允许：用当前年报、结果已知历史材料和合成 fixture 建立 material stocks、flows、瓶颈、反馈、议价和 owner-cash 传播。

禁止：为完整而罗列所有业务字段，或把模型草图当作已证实因果模型。

产物：版本化 `EnterpriseSystemModel`、material node/edge 证据状态和待验证的关键反馈。

### 4.2 `Management Decision Lab`

目的：训练 Agent 按决策当时可得信息评价管理层，而不是 outcome bias。

允许：使用结果已知材料，但必须先重建当时 framing、alternatives、information、trade-offs、reasoning 和 commitment，再单独读取执行与结果。

禁止：用一次成功/失败或管理层叙述直接形成长期质量标签。

产物：`ManagementDecisionLedger` entry、外部冲击/运气分离和后续适应记录。

### 4.3 `Mechanism Lab`

目的：低成本训练 Agent 识别经营决策、责任单元、竞争场域、机制箭头、反方和未知项。

允许：使用结果已知材料，使用合成边界 fixture，复盘历史失败。

禁止：把结果已知案例计为方向性选择成绩，把报告写作流畅度当作经济判断正确。

产物：机制草图、范围桥、近失效、禁止替代、测量合同和边界学习条目。

### 4.4 `Boundary Learning`

目的：训练系统在真实复杂资料中适时停下，识别 D3/D4 分化、集团/分部错配、同行不可比、共同冲击、归因不足和 `MIXED`。

允许：使用官方历史资料和已知结果来检验边界；可以改 schema、采集器和 validator 的通用能力。

禁止：为让案例升级为 A/B 而删除未知项、放松截止日、把动态网页当静态 PIT 来源、把 D3 改善当 D4 现金。

产物：边界失败诊断、可复用采集模块改进、明确的 `NO_PRIMARY` 或 `MIXED`。

### 4.5 `PIT Selection Episode`

目的：少量、昂贵且严格的信息围栏下，测试 Agent 在结果未知前能否选择一个明确经营路径。

硬门：

- cutoff 前预先登记的官方静态来源包；
- 已实施经营决策，不是计划、设计产能、预测或后来补写的行动；
- 责任单元、竞争 arena 和同行角色冻结；
- competing/joint hypotheses、反方、简单基线、diagnostic matrix 和结果期在揭盲前冻结；
- D3 与 D4 有独立、可复算、同一责任边界的材料性锚；
- 结果读取与训练判断隔离，支持 `UNKNOWN` / `NOT_DIAGNOSTIC`；
- 独立 reviewer 和失败根因记录。

这些门是正式方向性样本的门，不是所有机制实验的入口门。

### 4.6 `Cross-Company Transfer`

目的：证明 learning 真的改变了下一家公司，而不是只让原案例的解释更漂亮。

退出条件：`TransportContract` 说明 source structure、invariants、target differences、moderators 和 break conditions；不同公司或公司簇中，冻结前的 arena、责任边界、hypothesis、来源顺序、结果合同或停止规则发生可核查变化；并有独立审阅确认这项变化不是文字改名。

### 4.7 `Historical Holdout`

目的：在方法版本冻结后，揭盲未参与方法形成的公司轴/时间轴留出。

留出只评价冻结版本，不产生该版本的 learning，不允许看结果后修订再称为留出。结果已知教学样本只能用于边界，不进入留出分母或方向性成绩。

### 4.8 `Live Sentinel`

目的：在未知未来结果环境中，验证部署纪律、到期采集、信息围栏和未知处理。

实时哨兵等待外部披露时，历史训练继续进行。`LIVE_SENTINEL = WAITING_EXTERNAL` 不是系统 blocked。

## 5. 状态和权限

系统不再用一个 `status` 同时表达所有含义。至少分为四个正交维度：

| 维度 | 示例 | 回答的问题 |
|---|---|---|
| `lane` | `ENTERPRISE_MODEL / MANAGEMENT_DECISION / MECHANISM_LAB / BOUNDARY / PIT / HOLDOUT / LIVE` | 这项工作属于什么训练/运行通道？ |
| `lifecycle` | `DRAFT / EVIDENCE_OPEN / REVIEW_READY / FROZEN / REOPENED` | 对象目前走到哪个过程阶段？ |
| `resolution` | `UNKNOWN / NO_PRIMARY / MIXED / SELECTIVE_SUPPORT / A_ONLY / B_ONLY / NOT_DIAGNOSTIC` | 证据对假设实际说明了什么？ |
| `permission` | `TEACHING_ONLY / LEARNING_ELIGIBLE / EVALUATION_ONLY / INVESTMENT_INPUT` | 这个对象可以被哪个下游消费？ |

例如 `lane=BOUNDARY, lifecycle=FROZEN, resolution=MIXED, permission=TEACHING_ONLY` 是完整、合法而且有价值的状态，不应被系统误认为“未完成”。

| 状态 | 真实含义 | 可以做什么 | 不能做什么 |
|---|---|---|---|
| `UNKNOWN` | 关键事实或传导未被证实 | 保留问题、保守区间、停止或请求数据 | 写成正向或负向事实 |
| `NO_PRIMARY` | 没有足够证据在主路径之间选择 | 做机制/边界训练，保留弃权纪律 | 计为方向性样本或方法命中 |
| `MIXED` | 不同层或不同证据方向分化 | 训练边界，分别结算 D1-D5 | 压成 A/B 或“略偏 A” |
| `SELECTIVE_SUPPORT` | 多假设中一项或一组解释获得相对区分性支持 | 保留被支持、被排除和未决假设的明确集合 | 改写成“证明唯一真因” |
| `A_ONLY/B_ONLY` | 冻结谓词下只有一条路径得到支持 | 进入正式 episode 结算和有限 learning | 单个 episode 推导普遍能力或概率 |
| `NOT_DIAGNOSTIC` | 结果不区分假设，或共同冲击无法拆分 | 记录测量设计失败并改进合同 | 把结果当机制验证 |
| `PIT_BLOCKED` | 来源、时间、范围或结果围栏破坏 | 修复 acquisition/schema 或终止候选 | 通过叙事绕过信息边界 |
| `FROZEN_CJO` | 公司判断已在 cutoff 下冻结 | 进入估值、回报和报告 | 让价格倒灌经营判断 |
| `INVESTMENT_READY` | CJO 与投资层均通过各自质量门 | 给出研究价格、回报和动作条件 | 自动交易或覆盖 UNKNOWN |

状态是权限，不是评分。特别是 `MIXED` 是有价值的边界学习结果，不是失败的 A/B 样本。

### 5.1 V5 canonical selection lifecycle

V5 的生产级选择链只有以下单向生命周期：

```text
COHORT_FEASIBILITY
  → CANDIDATE_DECISION_SCREEN
  → SELECTION_ADMITTED_PRE_OUTCOME
  → OUTCOME_SETTLED
  → LEARNING_TRANSFERRED
```

Stage-0 只冻结 arena family、field identities、control independence 和 static source identity，绝不创建
episode、final panel、action target、outcome access 或 learning 权利。H1 成功后，独立 curator 才能一次性
提交闭合的 H2 action-screen static-PDF extension：它精确绑定 H1 `cohort_id` 和 curator 身份，自带且仅使用
cutoff-before `static.cninfo.com.cn/finalpage/...PDF` 行动来源、逐页 field refs、issuer/RU/perimeter/unit
identity 与 source-firewall receipt；可以增加行动原件但不得增加 cohort company，screen 开始后不得追加或
替换来源。H2 的 action、hypothesis、D2/cost 与事实必须全部引用 H1+H2 的明确 allowlist，不能另由调用者
交一个 legacy manifest。进入 V4 内层准入后，target/peer 的 raw D3/D4、control、market/panel、comparability、cash-history/bridge 与 materiality anchors 也只可引用该闭合 map：H1 承载多成员年报历史，H2 只承载一次 action screen 的行动/事实/D2/cost 原件；V4 不得追加或替换来源。候选还必须逐页复现 H2 的 action statement、implementation/bridge/specificity/exposure 证据、cutoff facts，以及每期 D2/cost observation；价格行动的 price delta 与 pre-action units field identity 也不得漂移。V5 只支持 `CUSTOMER_RESPONSE` 与
`COST_RESTRUCTURING`；前者要求中心 D2，后者默认采用 `DIAGNOSTIC_NON_VOTER` cost path，只有 action
明示客户传导且有三期 source-bound D2 observations 时才可采用 `CENTRAL_VOTER` D2 path。`selection_bundle`
是 validator→seal→resolver 的唯一 canonical root：独立
review 在 seal 前逐字段比对，actual outcome source 只能由 authorized custodian 在 seal 后登记、读取和
提取。`UNKNOWN`、`MIXED`、`NOT_DIAGNOSTIC`、`BOUNDARY_CAPTURED` 与 `EXPOSURE_EXCLUDED` 都不产生方向性迁移。

当前已有一个 curator 提供的水泥 H1 static package 通过 strict preflight，并已登记为 `H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1@1`；它仅证明来源接收，不授予 final panel 或 episode。G2 最小 immutable receipt registry 已将 strict H1/H2 validator 接到 V5 control plane：H1 以 receipt id/version 和 cohort/time/curator 自然键登记，H2 必须只引用已登记 H1 并从表内 payload 重跑 H2 validator；相同 ID/version 的内容替换与相同自然键的第二份 receipt 均被拒绝。首个真实 V5 seal 前，single-root canonical contract 必须携带已登记 H1/H2 `source_provenance` ref 和 snapshot；seal 在写入前解析 H1→H2 parent，并要求 source manifest 仅使用其 H1∪H2 static-PDF map。该 binding 不复制 V3 数据、不创建 V5 wrapper，也不允许 bare V5 real-selection bundle 绕过 H1/H2。

该 registry 已在 temporary SQLite synthetic fixture 中验收，水泥 H1 也已手工登记到隔离开发 namespace；真实 H2 现可由 curator 绑定该 receipt 接收。并且该 cohort 中两名成员已有 scope/control break，剩余三名 disclosure-only pending 成员不足任何 target 加三名 `EXTERNAL_SHOCK_COMPARATOR` 的 V5 final panel；H2 对该 cohort 的上限是严格 `NO_PRIMARY_ARENA_OR_PANEL`，不能用 H2 补公司或恢复 break 成员。

## 6. Agent 与服务分工

Agent 可以并行，但不以投票替代主研究判断。建议责任链如下：

| 角色 | 交付物 | 独立性要求 |
|---|---|---|
| Source Curator | cutoff 前来源清单、来源身份、可读包、缺口 | 不看结果包，不作经济结论 |
| Scope Mapper | responsibility unit、competitive arena、同行角色 | 不以行业标签或地理相等代替机制 |
| Mechanism Analyst | EnterpriseSystemModel、假设 registry、箭头、反方、停止条件 | 在结果揭示前冻结 |
| Management Analyst | ManagementDecisionLedger、当时替代方案、执行与结果分离 | 不用结果倒推当时决策质量 |
| Outcome Reader | 只读预登记结果包，逐层提取观察 | 不回看选择结论以改写谓词 |
| Settlement Agent | 机械结算和诊断 | 不替 reviewer 做解释性升级 |
| Transfer Reviewer | learning root cause、下一家公司字段变化 | 必须检查真实迁移 |
| Valuation Agent | 正常利润、owner cash、价值、回报、价格 | 只读取冻结 CJO |
| Report Assembler | 连续读者报告和技术附录 | 不创造新事实或模型输入 |
| Independent Reviewer | 内容、数字、边界和迁移审阅 | 不能以生成者身份自签 |

主 Agent 维护问题树、证据标准和最终判断。并行 Agent 的结果只能作为受约束的子工件进入统一交接，不得通过“多数票”形成投资结论。

记忆服务只保存工作方法、失败经验和 canonical 对象导航；证据、当前状态、估值、价格和交易事实仍以仓库与数据库的 canonical read model 为准。

## 7. CJO 到买点的单向契约

### 7.1 企业判断输出

CJO 必须给出以下可消费对象：

- 当前经营系统与关键价值驱动；
- 管理层已实施行动、纵向决策模式及其责任边界；
- 客户/竞争/成本/产品/资本配置的机制路径；
- material stocks、flows、瓶颈、反馈和再投资约束；
- 竞争假设、证据鉴别力和仍未被排除的解释；
- 正常状态、压力状态和最强反方；
- `UNKNOWN` 与不可归因处；
- 对正常利润、owner cash、资本需求和永久损失的方向性影响；
- 未来 1—3 个披露节点的证伪指标。

### 7.2 投资层的传播要求

每个关键经营驱动都必须继续传播到适用的：

```text
正常利润
  -> owner cash / FCFF
  -> 普通股可达现金
  -> 价值身份
  -> 期末现金或价值
  -> 主要回报
  -> 主要研究价格 / 买入区间
```

如果某个驱动只出现在正文或敏感性表中，却没有进入正常利润和普通股现金，它不能被称为估值已经反映该驱动。若现金的法律归属、NCI、资本需求或可分配能力未知，估值必须保留保守身份，不得用总现金替代普通股现金。

### 7.3 预期差与买点输出

投资层不能只给一个“内在价值点”。它必须先反解当前价格要求公司实现的收入、利润率、再投资、竞争优势持续期和普通股现金路径，再与冻结 CJO 的可行范围比较，形成 `ExpectationGap`：

```text
price snapshot
  -> price-implied operating requirements
  -> CJO feasible / stress / reversal ranges
  -> expectation gap and decisive driver
  -> return distribution under explicit holding periods
  -> conditional BuyBand
```

`BuyBand` 是满足指定回报与永久损失约束的条件化价格集合，不是单一目标价。它必须分别显示：

- 企业经营和正常利润不确定性；
- 债务、资本需求、现金归属和普通股生存性；
- 估值身份、终值与持有期不确定性；
- 市场价格波动。

价格波动不能替代永久损失；保守价值区间也不能自动变成仓位。若价格隐含要求无法由当前模型唯一反解，输出 `EXPECTATION_GAP_UNKNOWN`，而不是选择一个顺眼的参数组合。

### 7.4 投资结论的权限

- CJO 未冻结：可以继续企业研究，不能输出正式买点；
- CJO 为 `NO_PRIMARY`/`MIXED`：可以给观察、估值范围和需验证的问题，不能假装有单一路径；
- CJO 已冻结但 D4/owner cash 未闭合：可以输出经营判断，投资动作保持受限或 `UNKNOWN`；
- CJO、D4、价值、回报和反方均通过：才可输出研究价格、仓位建议和翻转条件；
- 任何阶段都不自动执行真实交易。

## 8. 系统整合度判断

当前系统不是“没有设计”，而是**局部模块较成熟、跨层闭环尚未完成**。应按以下层级判断：

| 层 | 当前判断 | 关键缺口 |
|---|---|---|
| 官方来源与 PIT 防泄漏 | `ONE_H1_RECEIPT_REGISTERED / G2_RUNTIME_IMPLEMENTED / H2_PENDING` | 水泥 H1 包已登记 immutable provenance；其 final panel 容量不足，须保持 H2/`NO_PRIMARY` 边界或接收新 cohort |
| 企业整体表示 | `OFFLINE_CONTROL_IMPLEMENTED` | 仍未接入生产 canonical CJO 或真实 episode |
| 机制/边界训练 | `SYNTHETIC_VALIDATED` | 真实 PIT 与跨公司 application receipt 尚未形成 |
| 正式 PIT 选择 | `GATE_READY / NO_DIRECTIONAL_SAMPLE` | 第一条 A/B episode 尚未形成；不能为凑样本放松门槛 |
| 学习迁移 | `CONTROL_DESIGNED / NOT_PROVEN` | 尚无带 TransportContract 且经 reviewer 接纳的跨公司改变 |
| 历史留出 | `NOT_OPEN` | 必须先冻结方法版本 |
| CJO 到估值/买点 | `OFFLINE_DIRECTIONALITY_VALIDATED / PRODUCTION_PENDING` | 需要获授权 canonical frozen CJO、D4 与正式单向输入 |
| 黄金报告 | `DELIVERY_EXISTING / NOT_TRAINING_ORACLE` | 报告是输出层，不应反向定义训练正确答案 |
| 记忆服务 | `AUXILIARY_ONLY` | 只能导航和沉淀工作方法，不能成为事实真源 |

因此整体结论是：**离线控制完整度高于真实运行闭环完整度；研究交付能力高于可证明的企业判断与泛化能力。** V3 已补上企业持续模型、管理层纵向判断、证据鉴别、迁移条件和预期差买点的 synthetic control；当前主要阻断不在“再找一家公司”，而在收到符合 H1 契约的静态来源包后，才让这些对象成为真实 episode 和定量模块可以消费的共同接口。

## 9. 禁止的倒灌与常见退化

以下行为直接破坏中心目标：

1. 先找到候选，再不断追加同行、市场、公告和字段硬门，让案例反向设计架构；
2. 把同省份、同 `industry_id`、同公告标题或同产品名当作共同市场证明；
3. 用集团层收入、利润、OCF 替代决策责任单元的 D3/D4 结果；
4. 用投产、设计产能、销量、正 OCF 或市场份额替代客户吸收、单位经济和 owner cash；
5. 把 `MIXED`、`NO_PRIMARY` 或 `NOT_DIAGNOSTIC` 改写成方向性结论；
6. 看到结果后修改 cutoff、假设、指标或来源包；
7. 用价格、股价结果或估值吸引力反向选择企业机制；
8. 用更多文本、更多评审票、更多敏感性或更多模型掩盖关键未知；
9. 把记忆、旧报告、旧 dashboard 或动态搜索页面当作当前证据；
10. 在同一问题上反复加门，却不先判断根因属于数据覆盖、采集模块、推理、模型还是写作。

遇到阻断时的默认处理顺序是：

```text
确认经济影响
  -> 定位根因类型
  -> 先修复可复用 acquisition/schema/validator（若为数据或采集问题）
  -> 若机制本身不可判，保留 UNKNOWN/NO_PRIMARY/MIXED
  -> 转入 Mechanism Lab 或 Boundary Learning
  -> 只有满足正式门时才回到 PIT Selection
```

## 10. 设计冻结出口

其他 Agent 开始实现前，必须先接受以下架构不变量：

1. 企业判断的持续对象是 `EnterpriseSystemModel`；训练的最小变化单位是 `DecisionEpisode`，不是公司、行业或报告；
2. `CompetitiveArena` 按机制定义竞争经济体，地理不是默认硬门；
3. `ResponsibilityUnit` 将会计、决策、经济载体和测量面分开；
4. 机制训练、边界训练、正式 PIT、历史留出和实时哨兵是不同 lane；
5. `UNKNOWN`、`NO_PRIMARY`、`MIXED` 具备明确权限，不为凑方向性样本降级；
6. CJO 先冻结，Investment Overlay 后运行，价格和回报不能倒灌 CJO；
7. D3 经营贡献与 D4 owner cash 必须独立、有来源、可复算；
8. learning 必须带 `TransportContract`、改变另一家公司冻结前字段并经独立审阅；
9. 黄金报告是交付层，不是训练目标或训练真相；
10. 仓库、数据库和 canonical read model 是证据与状态真源，记忆服务只作辅助导航。

11. 证据、机制和投资传播分别有 typed graph；`OBSERVED`、`INFERRED`、`UNKNOWN`、`CONTRADICTED` 不能靠正文语气区分。
12. `DecisionEpisode` 必须显式登记 time zero、干预/行动、比较对象、结果、跟踪窗口、共同干扰和溢出；缺失这些身份时只能降级。
13. 研究 Agent 的下一次检索由“决定性问题的预期信息价值”路由，而不是由字段完整率或搜索结果数量路由。
14. 评价拆成流程完整性、认识质量、经济传播和迁移/留出四层；不使用一个总分让不同失败互相补偿。
15. 管理层质量来自纵向 `ManagementDecisionLedger`；当时决策质量、执行、外部冲击和事后结果不能混成一个标签。
16. 多假设问题使用 `HypothesisRegistry` 和 diagnostic matrix；支持条数、来源条数和 Agent 票数不能替代鉴别力。
17. 买点必须先比较价格隐含经营要求与 CJO 可行范围，并输出条件化 `BuyBand`；单点目标价和价格波动不能掩盖永久损失。

只有在这些不变量稳定后，才实施更细的 market schema、validator、cohort admission 或真实训练执行器。

## 11. 设计依据与现有文档关系

本设计吸收但不复制以下现有契约：

- [历史优先的企业判断训练架构](./TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md)：历史训练、留出、教学和实时哨兵分轨；
- [判断飞轮](./TURTLE_JUDGMENT_FLYWHEEL.md)：learning 必须改变下一家公司；
- [判断训练实验](./TURTLE_JUDGMENT_TRAINING_EXPERIMENTS.md)：机制、反方、结果合同和 `UNKNOWN` 的实验边界；
- [判断验证协议](./TURTLE_JUDGMENT_VALIDATION_PROTOCOL.md)：PIT 信息围栏和结果结算；
- [Golden Report 双向研究路线](../GOLDEN_REPORT_BIDIRECTIONAL_RESEARCH_ROADMAP.md)：公司、行业、宏观与报告层的关系。

外部方法上的两个基本依据是：相关市场应按产品/服务的可替代性和竞争条件定义，而不是机械按行政区相等；单一干预的比较组应关注干预前特征、共同冲击、趋势和溢出，而不是地理身份本身。这与 [EUR-Lex relevant market](https://eur-lex.europa.eu/EN/legal-content/summary/definition-of-relevant-market.html) 和 [Synthetic Control Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC8634614/) 的一般原则一致。

## 12. 外部研究与开源系统的借鉴

外部系统提供的是可迁移的设计机制，不是 Turtle 的证据、投资结论或质量保证。研究后得到的判断如下：

| 来源 | 已验证的设计经验 | Turtle 应采用 | Turtle 不应照搬 |
|---|---|---|---|
| [STORM](https://arxiv.org/abs/2402.14207) / [GitHub](https://github.com/stanford-oval/storm) | 先发现多视角，再通过模拟追问收集资料，最后生成结构；Co-STORM 维护共享 mind map | 研究问题规划器、视角/反方发现、共享 evidence map | 互联网文章生成流程；搜索到的叙事不能直接变成 CJO |
| [ReAct](https://arxiv.org/abs/2210.03629) | 推理与行动交替，让行动结果更新计划并处理例外 | 每次检索必须绑定当前未决问题和下一状态 | 让自由文本 reasoning trace 成为事实或审计证据 |
| [Reflexion](https://arxiv.org/abs/2303.11366) | 通过外部反馈形成可复用的文字反思，不必更新模型权重 | 把结果诊断压缩成窄的 learning transfer，并要求改变下一家公司 | 把自我反思当作真实 reviewer 或事实来源 |
| [DSPy](https://arxiv.org/abs/2310.03714) / [GitHub](https://github.com/stanfordnlp/dspy) | 将 LLM 流程写成可组合的程序，用明确 metric 离线优化 | 把研究流程模块化，针对 typed process/economic metrics 做离线优化 | 用报告流畅度、LLM judge 分数或样本数量优化完整系统 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | durable execution、人工介入、状态恢复、运行轨迹和长期/短期记忆分工 | 保留可恢复状态机、人工决策点和运行事件；可以由现有 DB 实现 | 为了使用框架而重写已有控制面 |
| [Temporal](https://github.com/temporalio/temporal) | 将长任务拆为可重试、可恢复的 workflow/activity | 外部来源等待、结果到期和 reviewer 任务使用持久事件 | 为研究问题引入重量级基础设施，除非现有 DB 无法满足恢复需求 |
| [FinRobot](https://arxiv.org/abs/2405.14767) / [GitHub](https://github.com/AI4Finance-Foundation/FinRobot) | 确定性数值计算与 LLM 叙述分离，多角色流水线和数值溯源 | CJO、估值计算、报告写作和 provenance 分层 | 多 Agent debate 或“金融专用”标签本身不能证明判断质量 |
| [FinMem](https://arxiv.org/abs/2311.13743) | profile、分层 memory、decision 三层组合，强调上下文选择 | 只将方法经验和已接纳的对象指针分层保存，并有 PIT/生命周期边界 | 把交易记忆、价格或历史报告直接注入当前公司判断 |
| [AgentBench](https://arxiv.org/abs/2308.03688) / [GAIA](https://arxiv.org/abs/2311.12983) | Agent 失败来自长期规划、决策、工具使用和指令遵循，不能用单任务问答代表 | 建立跨阶段、工具、信息围栏和状态恢复的任务级评估 | 用单个总榜、单次报告或模型投票代表生产可靠性 |
| [FinanceBench](https://github.com/patronus-ai/financebench) / [FinQA](https://github.com/czyssrs/FinQA) | 财报问答必须绑定 evidence span；数值任务需要可执行 reasoning program，检索器会成为主要错误源 | 建立来源定位、口径选择、确定性计算和拒答 micro-benchmark | 财报 QA 或算术正确不能证明企业机制判断 |
| [DeepResearchBench](https://github.com/Ayanami0730/deep_research_bench) / [LiveResearchBench](https://github.com/SalesforceAIResearch/LiveResearchBench) | 深度研究需分别评价覆盖、分析深度、指令、可读性、事实和引用，而非单一总分 | 借用分层、任务特定 criteria 和 citation association 测试 | LLM judge 分数不能授予 CJO、PIT 或投资权限 |
| [DRBench](https://github.com/ServiceNow/drbench) | 企业研究要跨内部/外部多源环境提取关键 insight，并把 insight 与 citation 配对 | 为公司研究建立 claim-citation、关键洞见召回和混合来源 fixture | 洞见召回不能证明因果、owner cash 或永久损失判断 |
| [FActScore](https://github.com/shmsw25/FActScore) / [Ragas](https://github.com/vibrantlabsai/ragas) | 长文可以拆成 atomic claim 检查事实支持，RAG 评价要使用生产对齐样本 | 报告发布前做 material atomic-claim 与引用关联检查 | 自动 factuality 或 RAG 分数不能替代独立经济审阅 |
| [W3C PROV](https://www.w3.org/TR/prov-overview/) / [OpenLineage](https://github.com/OpenLineage/OpenLineage) | 用 entity/activity/agent 和 run/job/dataset 表达数据来源与处理过程 | 为 source package、抽取、判断、计算和报告建立统一 provenance 事件 | 无目的地为所有文件增加 hash；只有会改变后续动作的身份才进入控制面 |
| [Heuer, Psychology of Intelligence Analysis](https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/) | ACH 要求同时比较多个解释，优先寻找不一致和真正有鉴别力的证据 | `HypothesisRegistry` 和定性 diagnostic matrix；共同支持所有假设的证据不增加选择权 | 机械统计一致/不一致数量，或假装假设集合已经穷尽 |
| [Collier, Understanding Process Tracing](https://www.cambridge.org/core/journals/ps-political-science-and-politics/article/understanding-process-tracing/183A057AD6A36783E678CB37440346D1) | 定性证据的推断力取决于它在因果序列中的位置以及必要性/充分性，而非证据条数 | 用 `STRAW / HOOP / SMOKING_GUN / DOUBLY_DECISIVE` 作可选的证据角色注释 | 把启发式检验变成加权总分或自动因果证明 |
| [Pearl & Bareinboim, Transportability](https://arxiv.org/abs/1503.01603) | 迁移要显式表达来源和目标的共同点、差异及需要补充的目标观察 | `TransportContract` 的 invariants、moderators、target differences 和 break conditions | 因行业、规模、地域或表面相似就复制规则 |
| [Gentner, Structure-Mapping](https://groups.psych.northwestern.edu/gentner/papers/Gentner83.pdf) | 有效类比优先映射对象之间的关系系统，而不是对象属性 | 按机制拓扑和高阶关系选择跨公司迁移 | 按产品名、行业标签或公司画像做表面类比 |
| [Society of Decision Professionals, Decision Quality](https://www.decisionprofessionals.com/who-we-are/decision-quality) | 决策质量由 framing、alternatives、information、values/trade-offs、reasoning 和 commitment 共同约束 | `ManagementDecisionLedger` 在决策当时记录过程，再与执行和结果分开 | 用一次好结果倒推管理层当时判断优秀 |
| [Strategy Dynamics](https://strategydynamics.com/free/assets/The%20Dynamics%20of%20Strategy%2C%202016.pdf) | 企业表现来自资源存量、流入/流出、时滞和反馈的共同演化 | `EnterpriseSystemModel` 只保留 material stocks、flows、bottlenecks 和 feedback | 强制每家公司建立大规模系统动力学仿真 |
| [Expectations Investing](https://www.expectationsinvesting.com/) | 从价格反解经营预期，再用竞争战略和价值驱动判断预期修订，而不只做正向目标价 | 价格隐含经营要求、`ExpectationGap` 和条件化 `BuyBand` | 让市场价格倒灌 CJO，或把 reverse DCF 的一组解当作市场唯一信念 |

这些系统也暴露了两个实际教训：`open_deep_research` 已在 2026-08-22 归档，AutoGen README 已明确进入 maintenance mode 并引导新用户迁移到 Microsoft Agent Framework。Turtle 因此应把“typed artifact、状态、权限和证据身份”作为自己的长期接口，任何 LangGraph、Temporal、DSPy 或其他框架只能是可替换的运行实现。

## 13. 设计升级 V2：从对象管线到研究图

六个核心对象定义责任，三张图负责导航和传播。V2 增加的图仍然保留；它们不是第三套事实库，而是同一 canonical 对象的不同投影。第一版不需要图数据库：关系表、JSON typed artifact 或可重建 view 已足够，只有查询和迁移成本证明值得时才更换存储实现。

### 13.1 `EvidenceGraph`

节点包括 `SourcePackage`、document、page/span、issuer/entity、period、metric 和 extracted observation；边包括 `supports`、`contradicts`、`same_definition_as`、`belongs_to_scope`、`available_at_cutoff` 和 `derived_by`。

每条 material claim 必须能沿图回到：

```text
claim -> observation/extraction -> source span -> document -> source package -> cutoff
```

没有这条路径的内容只能是 `INFERRED` 或 `UNKNOWN`，不能在正文中伪装成观察事实。只有未来另行授权的 non-PIT discovery 才可把动态网页、搜索摘要和记忆命中作为 discovery 节点；当前 H1 不读取这类资料，它们也永远不能直接连接到 PIT claim。

来源还必须分别记录 `temporal_eligibility / authority / directness / independence_cluster`。三篇转载同一公司稿件只算一个来源家族，管理层归因是重要证据但不是独立验证；来源数量和 Agent 数量都不能投票产生事实。这用于处理 STORM 研究指出的 source bias transfer，而不是建立机械来源分数。

### 13.2 `MechanismGraph`

节点包括 decision、customer task、competitor response、capacity/cost、unit economics、working capital、owner cash、capital allocation 和 risk；边包括 `causes`、`requires`、`mediates`、`falsifies`、`co-moves_with` 和 `not_diagnostic_of`。

它强制区分三件事：

- 经济上认为会发生什么；
- 官方资料实际观察到了什么；
- 哪个观察可以区分当前 active hypotheses。

同一观察可以支持一个上游节点，却不能自动支持下游节点。例如收入增长可以支持“销售发生”，不能自动支持客户价值、单位经济、owner cash 或资本回报。

### 13.3 `InvestmentGraph`

节点包括 CJO driver、normalized earnings、owner cash、ordinary-share access、valuation identity、price-implied expectation、return path 和 buy price；每条边都带有计算身份、输入来源、情景和可逆性。

这样报告、估值和训练共享同一传播图，但不会让报告正文成为模型输入。图上的断边必须显示为 `UNKNOWN`、`NOT_PROPAGATED` 或保守身份，而不是由 writer 补句子。

## 14. DecisionEpisode 的 target-trial 约束

因果推断的可借鉴处不是把企业资料强行变成随机实验，而是要求在行动发生前把问题定义完整。每个正式 episode 追加以下字段：

| 字段 | 企业研究含义 |
|---|---|
| `eligibility` | cutoff 时为什么公司/单位进入候选宇宙，后来结果不能参与资格判断 |
| `time_zero` | 决策真正开始影响经济系统的时间，而不是公告发布日期自动代替 |
| `intervention` | 管理层已实施的经营动作及其强度、范围和责任人 |
| `comparator` | 同一竞争经济体中的外部冲击参照、见证者或 falsifier |
| `outcomes` | D1/D2/D3/D4/D5 分层结果及各自定义 |
| `follow_up` | 每一层结果何时到期、允许读取哪些资料 |
| `censoring` | 停产、并购、退市、披露中断、口径改变等导致的观察中止 |
| `co_intervention` | 同期价格、政策、并购、产能、汇率或渠道动作，不能默认为不存在 |
| `interference` | 同行回应、供应链溢出、区域价格和客户转移是否污染 comparator |
| `estimand` | 此 episode 实际想判断的是哪条机制/哪种结果，不扩大成“公司整体能力” |

这张表不是统计估计器，也不是要求每个企业问题都得到因果识别。它的作用是让 Agent 在没有随机实验时显式写出不可检验假设、共同干扰和结果边界。缺失 `time_zero`、`estimand` 或干扰审阅时，最多进入 Mechanism Lab/Boundary Learning。

## 15. 主动研究：按预期信息价值选择下一步

当前流程容易把“找更多资料”误认为进展。V2 增加一个 research policy：每次下一步动作都必须针对一个未决、材料性问题。

概念优先级可以写成：

```text
research_priority
  = materiality
  × current_uncertainty
  × ability_to_discriminate_active_hypotheses
  ÷ acquisition_cost
```

这里优先级只用于排序，不产生伪精确概率。实现上使用 `HIGH / MEDIUM / LOW / STOP` 足够：

- `HIGH`：若答案改变 CJO、D3/D4、永久损失或买点，且存在可取得的区分性来源；
- `MEDIUM`：有助于完善机制或范围，但不会改变当前权限；
- `LOW`：只增加背景，不改变下一步；
- `STOP`：资料不可得、观察不具诊断性或成本高于决策价值。

Agent 每次检索前需写出：要区分的假设、期望观察、可能的下一状态。检索后若没有改变状态或减少关键不确定性，就不能仅凭资料数量继续扩张。

这借鉴 [Active Learning Literature Survey](https://minds.wisc.edu/items/37538f44-36ae-413e-8967-e6c831e17a8e) 中“在标注昂贵时主动选择最有价值查询”的思想，但 Turtle 选择的是企业研究动作，不把模型不确定性直接当作经济不确定性，也不把人工/结果反馈当作廉价标签。

## 16. 训练课程与样本选择

第一个样本不应由“最容易取得的公司”决定，而应由当前系统最需要学习的机制和边界决定。下一 episode 的选择优先考虑：

1. 能覆盖当前未覆盖的机制拓扑；
2. 能挑战上一轮的最强错误替代；
3. 与已有案例在机制上可迁移、但公司和来源不重复；
4. 结果字段和共同市场具有可诊断性；
5. 取证成本合理，不需要为一个案例发明专用采集器。

这形成“机制课程”而非“公司排行榜”：先练决策—客户回应，再练成本重构，再练产品采用和资本配置；每个阶段都保留 near miss、falsifier 和 `NO_PRIMARY`。

## 17. 评价体系：不再用一个分数压平不同失败

系统评价拆成五个正交层：

| 层 | 检验什么 | 失败后改什么 |
|---|---|---|
| `PROCESS` | PIT、来源、时间、权限和状态转移是否正确 | 控制面/validator/acquisition |
| `EPISTEMIC` | claim 是否有来源，推断是否标注，反方和 UNKNOWN 是否保留 | evidence/mechanism graph、推理流程 |
| `ECONOMIC` | D1→D5 是否有同边界、同定义、可复算的传导 | topology、measurement contract、量化桥 |
| `TRANSFER` | learning 是否改变下一公司冻结前字段，holdout 是否保持封存 | curriculum、review、method freeze |
| `DECISION_UTILITY` | Agent 是否发现材料性未知、阻止范围/因果错误并改善用户可采取的判断 | 问题框架、研究排序、用户交付 |

LLM judge、人工审阅和自动测试都只能提供某一层的证据，不能跨层补偿。例如一篇语言优秀的报告不能抵消 `ECONOMIC` 断链；一个回归通过不能证明 `TRANSFER` 成立。

外部 benchmark 只覆盖其中一部分。Turtle 的评价栈应由低到高分层：

```text
L0 source/evidence retrieval     FinanceBench-like claim -> page/span
L1 deterministic numeracy       FinQA-like program -> result
L2 report factuality/citation    atomic claims, citation association, contradiction
L3 enterprise insight research   multi-source insight recall and task-specific coverage
L4 Turtle mechanism judgment     arena/scope/hypotheses/D1-D5/UNKNOWN/PIT
L5 Turtle economic propagation   CJO -> owner cash -> value -> return -> buy point
L6 Turtle transfer/holdout       next-company field change and frozen holdout
L7 decision-support utility      material unknown discovery and wrong-conclusion prevention
```

L0-L3 可以借用公开数据或方法，L4-L7 必须由 Turtle 的历史 episode、边界 fixture、跨公司迁移、留出和用户判断任务构造。任何低层 PASS 都不能自动升级高层权限。

## 18. 研究结论：应优先优化什么

按中心目标排序：

1. **最高优先级**：`EnterpriseSystemModel + HypothesisRegistry + EvidenceGraph/MechanismGraph`。它们决定 Agent 是否理解整家公司并寻找真正有鉴别力的证据。
2. **第二优先级**：`ManagementDecisionLedger + target-trial DecisionEpisode + UNKNOWN 权限`。它们把管理判断、执行、结果和外部冲击分开。
3. **第三优先级**：主动研究 policy、`TransportContract` 和课程选择。它们决定第一个样本卡住时，系统是否继续产生可迁移学习。
4. **第四优先级**：`InvestmentGraph + ExpectationGap + BuyBand`，确保企业判断真的改善买点，而不是另起一个估值故事。
5. **第五优先级**：持久运行、人工高价值介入、事件审计和可恢复 due inbox。它们决定长任务能否稳定运行。
6. **最后才做**：更换模型、扩大多 Agent 数量、训练基础模型权重、增加报告章节或引入更大的 web 搜索范围。

在没有第一条方向性 episode 时，前五项仍可用合成 fixture、边界案例和已知结果教学验证；但只有正式 PIT、纵向决策记录和跨公司迁移才能证明更强的判断能力。

## 19. 深度企业研究模式

Turtle 应提供一个明确的 `DEEP_ENTERPRISE_RESEARCH` 模式，但“深度”定义为研究控制协议，不是更高 Token、更长报告或更多 Agent。

### 19.1 进入条件

以下任一条件满足时进入深度模式：

- 用户要判断企业长期经营质量、管理决策或永久损失；
- 当前 CJO 存在会改变投资结论的 `UNKNOWN`；
- 竞争 arena、责任单元或 D3/D4 传导尚未闭合；
- 估值对某个经营驱动高度敏感；
- 普通快速研究只能提供背景，不能区分主要假设。

不满足时可以使用 `QUICK_RESEARCH` 只做发现和问题路由；快速研究不得输出正式 CJO、生产买点或 PIT 训练结果。

### 19.2 深度模式的八个阶段

```text
1. FRAME       明确用户要判断的企业问题、时点、普通股后果和管理决策
2. SCOPE       建立 EnterpriseSystemModel，冻结责任单元、竞争经济体和观察窗口
3. HYPOTHESES  登记多项竞争/共同机制、预期观察、最强反方和不可检验项
4. PLAN        从 diagnostic matrix 缺口生成 HIGH 信息价值取证队列
5. ACQUIRE     并行取得官方资料，抽取 source span，不直接写结论
6. ADJUDICATE  更新系统状态与三张图，裁决证据鉴别力、反方、共同冲击和测量边界
7. FREEZE      冻结 CJO、管理层账本判断、UNKNOWN、翻转条件和下一披露节点
8. INVEST      只有冻结后比较价格隐含要求，编译 InvestmentGraph、回报和 BuyBand
```

每个阶段只消费上游已接纳的 typed artifact。并行 Agent 可以分别取证、做反方或复核计算，但主 Agent 通过统一图和状态机收口，不通过票数收口。

### 19.3 四种运行模式必须隔离

| 模式 | 资料权限 | 结果权限 | 允许输出 |
|---|---|---|---|
| `DISCOVERY`（当前 H1） | 不读取真实公司/PIT 资料；只接收 curator 交付的 cutoff-before static-PDF identity package | 不读历史 outcome 包 | Stage-0 feasibility、来源缺口；不产生 PIT candidate/action/arena |
| `PIT_REPLAY` | 只读预登记 cutoff 前静态包 | 结果按 sealed package 延迟揭示 | 历史 CJO、episode、机制结算 |
| `LIVE_INVESTMENT` | 可用当前官方资料和价格快照 | 未知结果保持未知 | 冻结 CJO、定量价值、研究价格和翻转条件 |
| `HOLDOUT_EVALUATION` | 只读方法冻结前封存对象 | 只能评价，不能学习回写 | 留出评价和失败诊断 |

当前 H1 的 `DISCOVERY` 不拥有搜索或补齐历史 PIT 候选的权限：任何 PIT candidate/action/arena 的入口都必须来自 curator package，随后才可进入 `CANDIDATE_DECISION_SCREEN`。未来若单列 non-PIT discovery，也不得把动态网页或其候选投影为 `PIT_REPLAY` 事实；`PIT_REPLAY` 的已知结果不能进入 `LIVE_INVESTMENT` 的当前判断；`HOLDOUT_EVALUATION` 不能产生同一方法版本的 learning transfer。

### 19.4 深度模式的用户体验

用户不应该被要求逐段审批 Agent 的中间文本。系统应只在三个节点请求用户关注：

1. 当前最高信息价值问题会改变公司判断，但需要用户确认研究取向；
2. 资料冲突或责任边界无法由公开证据解决，继续搜索的边际价值很低；
3. CJO 已冻结，定量结果产生了需要用户理解的价值/回报分歧。

其余过程显示结构化进度：当前假设、关键未知、下一步取证、停止原因和哪些结论尚未获得权限。

### 19.5 深度模式的完成条件

深度模式不是“搜完所有资料”才完成，而是在以下条件满足时停止：

- 每个材料性结论都回到 evidence span 或显式标记为 inference；
- 关键竞争假设至少有一组区分性观察，或明确 `NO_PRIMARY`；
- 最强反方、共同冲击、co-intervention 和 scope mismatch 已审阅；
- D3 与 D4 的状态分别明确；
- CJO 的关键驱动能继续传播到 InvestmentGraph，或断点已标注；
- 下一项取证为 `LOW`/`STOP`，或新增资料不再改变权限。

因此，深度模式的核心产物不是一篇更长的报告，而是一组能约束报告、估值和买点的可复核中间对象。

## 20. V3 研究控制契约

### 20.1 `HypothesisRegistry` 与证据鉴别矩阵

企业问题不能默认只有 H-A/H-B。每个 material question 可以登记两到五个竞争解释，也允许 `JOINT_MECHANISM` 和 `OTHER_UNRESOLVED`。每个假设至少记录：

- 适用 scope、因果机制和与简单基线的差异；
- 如果成立，D1-D5 各层应该观察到什么；
- 哪个观察与其矛盾，哪个关键观察缺失；
- 与其他假设共享什么预测，因此哪些证据不具鉴别力；
- `ACTIVE / COMBINED / DISPLACED / UNRESOLVED` 状态及变更理由。

证据以行为行、假设为列形成 qualitative matrix。单元格只使用 `EXPECTED / COMPATIBLE / CONTRADICTORY / NOT_APPLICABLE / UNKNOWN`；每行另标记：

```text
diagnosticity = DISCRIMINATING / COMMON / CONTRADICTORY / NONDIAGNOSTIC
process_role  = STRAW / HOOP / SMOKING_GUN / DOUBLY_DECISIVE / NOT_CLASSIFIED
```

这些标签帮助 reviewer 判断，不相加、不加权、不投票。可靠但所有假设都预期会出现的证据仍可能是 `COMMON`；一条高鉴别力证据也不能在来源不可靠或 scope 不匹配时获得权限。假设可以在 `FREEZE` 前新增、合并或 displacement，但每次变更必须保留版本和原因；揭示 outcome 后不得回写 PIT 的原始 registry。

一个假设只有在材料性预期观察被矛盾证据击中，或另一解释对区分性观察提供更完整且边界一致的解释时，才能标为 `DISPLACED`；“支持材料较少”本身不构成 displacement。registry 不宣称穷尽所有真实机制，`OTHER_UNRESOLVED` 在 freeze 时仍可保留。

### 20.2 Episode 只更新企业系统的局部状态

正式 episode 的完整语义是：

```text
EnterpriseSystemModel@t0
  -> management decision and committed resources
  -> expected state transition under each active hypothesis
  -> observed D1-D5 transition
  -> local settlement
  -> EnterpriseSystemModel@t1 delta
  -> longitudinal ManagementDecisionLedger update
```

如果结果只观察到收入但没有单位经济或 owner cash，就只能更新对应节点；不能把整张企业系统图涂成正向。若一个 episode 与另一个 episode 共享产能、客户、资本或管理动作，必须登记 interference，不能把两项结果当独立票数。

### 20.3 `TransportContract`

跨公司学习只迁移关系，不迁移整篇结论。contract 至少包含：

| 字段 | 含义 |
|---|---|
| `source_structure` | 来源 episode 中被接纳的机制节点与高阶关系 |
| `invariants` | 在目标对象中预计仍成立的关系及理由 |
| `target_differences` | 客户任务、议价、成本结构、资本强度、治理和时间尺度差异 |
| `moderators` | 会改变方向、强度、时滞或可观察面的条件 |
| `required_target_observations` | 迁移前必须取得的目标公司事实 |
| `break_conditions` | 一旦出现就停止或降级迁移的条件 |
| `permitted_change` | 允许改变的冻结前字段、取证顺序或停止规则 |
| `application_receipt` | 目标 episode 是否实际采用、结果和 reviewer 裁决 |

contract 不闭合时，learning 最多是 `TEACHING_ONLY`。contract 闭合也只授予研究方法迁移，不授予目标公司的事实、因果结论或投资权限。

### 20.4 决策辅助效用

系统最终服务用户判断，因此评价不能停在报告分数或历史 outcome。每个重要研究任务应保存一个简短的 decision-support receipt，比较 Agent 介入前后的：

- 是否发现原先遗漏且会改变结论的 material unknown；
- 是否阻止 scope、PIT、共同冲击、因果或普通股归属错误；
- 是否把模糊争论变成可区分假设和可执行下一披露节点；
- 是否改变企业判断、价值范围、买点区间或“暂不判断”的理由；
- 新增研究成本是否换来了不同的决策，而不是更多文字。

正确保留 `UNKNOWN`、缩宽错误置信区间或阻止一次错误结论可以是正效用；一次股价上涨或报告获高分不能单独证明效用。评价可用 paired fixture、独立 reviewer 和用户最终采用情况，但不合成为一个产品总分。

### 20.5 最小实现映射

V3 不新增基础设施层：

| V3 概念 | 最小实现 |
|---|---|
| `EnterpriseSystemModel` | 版本化 JSON/关系表，投影到现有 `MechanismGraph` |
| `ManagementDecisionLedger` | 按 cutoff 追加的 decision rows 与 outcome overlay |
| `HypothesisRegistry` / matrix | typed artifact 加一个可重建 matrix view |
| `TransportContract` | `LearningTransfer` 的必填子对象 |
| `ExpectationGap` / `BuyBand` | 现有 `InvestmentGraph` 的输出节点和计算工件 |
| decision-support receipt | 任务级审阅工件，不写入投资事实记忆 |

因此本轮设计不会创建第四张图、新 memory snapshot、`RUN_CONTEXT` 或框架专用 canonical 对象。现有三张图、状态和权限仍是实现边界。
