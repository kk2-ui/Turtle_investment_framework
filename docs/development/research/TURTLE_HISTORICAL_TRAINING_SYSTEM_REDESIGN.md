# Turtle 历史训练体系重构：分层、生命周期与权限

> 状态：`FOUR_TRACK_CAPABILITY_CURRICULUM_IMPLEMENTED / HISTORICAL_TEACHING_AND_BLIND_PRIMARY / COMPARATIVE_LOCAL_ONLY / TRANSFER_NOT_VALIDATED`
>
> 日期：2026-08-28
>
> 中心目标：让 Agent 更好地辅助用户判断企业经营、管理决策、永久损失与长期价值，并在公司判断冻结后改善正常利润、owner cash、预期差和买点；训练样本数量、报告数量和流程通过率都不是目标。

> 顶层关系：整体训练系统的 V2 语义以[`TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md`](TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md)的 `EnterpriseJudgmentEpisode`、E0--E4 准入和多视图权限为准。本文只负责历史训练、生命周期、source registry 和 claim-specific Comparative 的实现细节；若本文把某一历史 lane 写成全局入口，应按顶层 V2 解释为该 lane 的局部门。

## 1. 重构结论

第一条正式方向性 action 样本难，并不反常。它试图同时满足历史信息隔离、公司整体已实施行动、责任边界、竞争反事实、D3/D4 结果合同和独立审阅，本质上是在做一个小型历史准实验。真正的问题是旧路线把这套最昂贵的门误挂在了所有训练之前，导致：

- 行业史因凑不齐固定数量的披露丰富公司而停止；
- 单家公司和已经消失的公司无法贡献教学与失败经验；
- H1 source package 被误当成最终 comparator panel；
- 每遇到一个候选反例就继续增加全局硬门；
- “方向性样本为 0”被误报成“训练没有运行”。

重构不放松 PIT、结果隔离或正式选择学习，而是缩小这些门的适用范围。日常主问题不是“某行动是否造成结果”，而是：**在当时可得信息下，这家企业未来经营质量、现金形成与永久损失风险会怎样变化，为什么？** 因果 action 只回答一个更窄、低频的附加问题。

```text
Calendar-time Industry Risk Set
  -> PIT Company State Forecast
  -> Relative Trajectory Tournament
  -> Outcome / Competing-event Settlement
  -> Prequential Feedback
  -> Company + Time Holdout
  -> Frozen CJO -> valuation / buy-point evaluation

Causal Action V5 = independent advanced lane
```

新的总原则是：

> **先说明要训练哪一种判断，再按该主张需要的识别强度准入。**

```text
Industry History Universe
        |
        +--> Evidence Carrier Set
                  |
                  +--> Teaching / Lifecycle Case
                  |
                  +--> Comparative Episode
                              |
                              +--> Learning Episode
                                          |
                                          +--> Holdout / Report A-B / Live Sentinel
```

五家公司不是训练本体。公司数量只在特定比较 topology 中作为识别和稳健性条件出现。

## 2. 九类训练对象

| 对象 | 回答的问题 | 最小准入 | 允许产物 | 明确禁止 |
|---|---|---|---|---|
| `IndustryHistoryUniverse` | 当时谁在竞争，行业结构怎样进入、退出和变化？ | cutoff、竞争范围、成员覆盖边界 | 行业时间轴、risk set、结构断点、进入退出事实 | 选择方法、相对因果、胜率 |
| `EvidenceCarrierSet` | 哪些主体和文件能承载本次事实或机制重建？ | source identity、时间角色、实体/业务映射 | 可复用的 source packet 与字段覆盖 | 冒充行业全集或最终同行 |
| `TeachingCase` | 一个企业或决策怎样运作、失败，哪些替代指标危险？ | 可追溯事实与结果；允许结果已知 | 问题库、机制候选、禁止替代、失败模式 | 方向性 method learning |
| `LifecycleCase` | 企业如何从一个状态转入收购、合并、退市、失败或资料中断？ | 公司身份、事件类型、事件时钟、观察状态 | 生命周期模式、永久损失路径、censoring 边界 | 把“消失”统一当失败，或用结局倒推 cutoff 前选择 |
| `PITCompanyStateForecast` | 在 cutoff 当时，这家企业未来经营、现金、风险怎样变化？ | 单公司 × 固定 cutoff、H1/risk-set source packet、六个状态维度、结果/价格隔离 | 1/3/5 年概率分布或明确 coverage gap；结算后仅可形成受限 forecast policy | 因果结论、公司事实、报告或买点权限 |
| `RelativeTrajectoryTournament` | 同一 cutoff 下各公司状态轨迹谁更可能改善/恶化？ | 2+ 公司的已冻结 state forecast | 每个维度的参考排序与不确定性 | 把同行当未处理控制组、合成总冠军或行动归因 |
| `ForecastSettlement` | 冻结 forecast 在随后披露中是否兑现、删失或不可诊断？ | V3/V4 Measurement Contract、独立 custodian observation receipt、冻结 forecast；V4 另有 H1-bound preforecast field receipt | Brier/RPS、coverage、错误归因；校准/coverage/状态定义/不确定性的受限 policy；其他方法候选 | 综合 0--100 分、因果结论、公司事实、report 或 investment 授权；V1/V2 评分或 active policy |
| `ComparativeEpisode` | 在同一问题下，这项行动相对可信反方或比较对象是否更好？ | PIT-safe packet、干预、time zero、comparator、outcome contract、独立 freeze | `A_ONLY / B_ONLY / MIXED / NOT_DIAGNOSTIC` 等结算 | 见结果后换题、换同行、补阈值 |
| `LearningEpisode` | 哪一条经诊断的错误能改变下一家公司？ | 具诊断性的 Comparative Episode、独立 review、TransportContract、不同公司应用 | 窄方法改变、method candidate | 整案复制、以单例证明一般能力 |

`HISTORICAL_HOLDOUT` 与 `LIVE_SENTINEL` 不是新的研究内容类型，而是对 Comparative/Learning 对象施加的评价和部署权限。它们不参与形成被评价的方法。

这里的通用 `TeachingCase` 不再等同于现有 lifecycle-only runner。课程层允许任何结果已知的真实企业案例进入 Teaching，只要它能重建一条完整经济链：`公司状态/约束 -> 管理选择或 no-action -> 客户/经营反应 -> 现金/资本结果 -> 投资处理`，并写出最强反方、near miss 和迁移问题。生命周期事件只是其中一种教学主题，不是 Teaching 的全局准入条件。

历史样本用途分为 `TEACHING / BLIND_JUDGMENT / HISTORICAL_HOLDOUT`，另保留少量 `PROSPECTIVE`。这四类是样本在课程中的角色，不替代本节九类研究对象。已知结果与旧派生报告暴露只让当前角色把公司路由为 Teaching；不会把公司永久逐出候选池。Blind 和 Holdout 的污染判断必须绑定具体角色、公司、cutoff 与 outcome window。

## 3. 按主张准入，而不是按案例准入

同一批资料可以产生不同权限的对象。系统必须先登记 `claim_class`，再决定准入门。

| `claim_class` | 例子 | 需要 comparator | 需要 outcome seal | 可改变什么 |
|---|---|---:|---:|---|
| `DESCRIPTIVE_STRUCTURE` | 行业集中、产能迁移、进入退出 | 否 | 否；但必须区分当时可见与后来重建 | 行业背景与研究议程 |
| `WITHIN_CASE_MECHANISM` | 渠道信用怎样传到现金，扩产为何未形成回报 | 否 | 教学不需要；PIT 机制结算需要 | 问题、指标、边界；不产生相对选择权 |
| `LIFECYCLE_TRANSITION` | 被收购、退市但经营、破产、业务退出 | 否 | 只有评价 cutoff 前判断时需要 | 永久损失与退出模式 |
| `PROSPECTIVE_STATE_TRAJECTORY` | 一家公司在 1/3/5 年的经营、现金和风险状态怎样变化 | 否 | 仅在独立 custodian 结果后 | 冻结 forecast、coverage / selective risk、prequential feedback |
| `RELATIVE_TRAJECTORY_REFERENCE` | 多家公司状态预测的逐维参照排序 | 参照组，不是反事实 control | 仅在独立 custodian 结果后 | 维度 ranking；不得聚合冠军 |
| `PREQUENTIAL_FEEDBACK` | 已公开的前一 forecast 结算能否作为下一 cutoff 的输入 | 否 | 是 | 只更新可复用的校准/coverage；不得重写过去 forecast |
| `RELATIVE_CAUSAL` | 某行动相对没有行动或同行是否改善 D3/D4 | 是 | 是 | 方向性结算候选 |
| `METHOD_GENERALIZATION` | 冻结方法能否迁移到未见公司/时期 | 是，且预留 | 是 | 只评价冻结版本 |
| `INVESTMENT_DECISION_UTILITY` | 训练是否改善价值区间和买点 | 同 cutoff A/B 或预注册基线 | 是 | 报告/定量授权，不回写企业事实 |

由此得到三个重要结论：

1. 一家公司足以形成高价值 Teaching Case，但不能因此形成相对因果结论。
2. 一个行业只有三家可深度披露公司，仍可形成 Industry History Universe 和 Lifecycle Case；不足只阻断需要更大 comparator panel 的主张。
3. 已消失公司必须保留。删除它们会把“仍能找到资料”误写成“更好的企业”，同时制造幸存者偏差。

## 4. 行业历史宇宙

### 4.1 公司 × cutoff risk set

行业历史的基本行不是“今天仍上市的公司”，而是 `company_cluster_id × cutoff`。每个 cutoff 记录当时进入 risk set 的主体；后来退出不删除早期成员，后来进入者也不回填到早期宇宙。

宇宙覆盖状态使用：

- `ENUMERATED`：已能按冻结规则列出当时主要成员；
- `BOUNDED_PARTIAL`：覆盖边界明确，但并非完整全集；
- `UNKNOWN_COVERAGE`：无法判断遗漏规模。

只有依赖完整分母的市场份额、退出率或相对表现主张才会被后两者阻断。一般行业史和教学研究保留限定语后继续运行。

### 4.2 竞争范围按机制定义

`CompetitiveArena` 由客户选择、产品替代、交付半径、监管、渠道、平台 side 与成本传导共同定义。地理可以是：

- `REQUIRED_EQUAL`：运输半径或牌照使区域直接承载竞争；
- `REQUIRED_OVERLAP`：客户和渠道部分重叠；
- `REQUIRED_EXPOSURE`：共同暴露于全国或全球细分市场；
- `NOT_REQUIRED`：地理不决定本轮机制。

水泥通常偏区域，家电可为全国，出口制造可为全球细分市场。`industry_id` 与省份都不能自动决定 comparator。

## 5. 生命周期、退出与删失

### 5.1 退出类型不可合并

生命周期账本至少区分：

```text
SURVIVED
ACQUIRED
MERGED_OR_PERIMETER_TRANSFERRED
DELISTED_BUT_OPERATING
BANKRUPTCY_FILED
REORGANIZING
EMERGED_FROM_REORGANIZATION
RESTRUCTURING_FAILED
LIQUIDATED
EXITED_BUSINESS
DATA_CENSORED
```

证券消失、法律实体消失和经营业务消失是三件事。被收购可能是资本回收，也可能暴露经营失败；退市公司可能继续经营；破产申请、重组、股东永久损失和业务终止也不是同一时点。合并后原责任边界可能无法继续测量。系统不得从事件名称直接生成好坏判断。

身份层至少分开 `economic_entity / legal_entity / listed_security / reporting_perimeter / successor_entity`，映射带 `effective_from / effective_through`。ticker、证券代码或名称不能单独充当跨期公司身份。

### 5.2 三个时钟

每个 lifecycle event 分开保存：

- `effective_at`：经济或法律事件实际发生；
- `known_at`：市场或研究者何时可以知道；
- `source_available_at`：当前使用的文件何时公开。

PIT packet 只消费 `source_available_at <= cutoff` 的 `CUTOFF_VISIBLE` 资料。后来资料可以作为 `POST_CUTOFF_CONTEXT` 或 `OUTCOME` 重建事件，但绝不能倒灌到 cutoff 前判断。

企业经济起点、进入可观察数据库和进入本轮 risk set 也必须分开：`time_origin / observation_entry_at / risk_start_at`。只从上市或数据库覆盖日开始观察属于 delayed entry / left truncation；公司必须先存活到该日才会被看见，不能用当前上市公司反推更早行业的失败率。年度材料优先使用 `interval_start / interval_stop / covariate_as_of`，任何经营变量都必须在区间开始时已经可知。

`absorbing` 不是事件固有属性，而是相对分析单位定义。退市可终止证券但不终止经营；收购可终止独立控制但保留业务；吸收合并可把经营 perimeter 转给 successor。因此 lifecycle event 还要记录 `absorbing_for[] / successor_subject_id`，不能只写一个 `is_absorbing`。

### 5.3 观察状态

未取得 D3/D4 不等于没有结果。结果字段使用：

- `OBSERVED`：同责任边界结果可重建；
- `CENSORED`：观察因窗口结束、披露终止或身份转移而停止；
- `COMPETING_EVENT_OBSERVED`：已发生另一种排斥性退出，不是普通删失；
- `UNKNOWN`：当前没有足够证据判断；
- `NOT_DIAGNOSTIC`：已观察但不能区分冻结假设；
- `MEASUREMENT_MISMATCH`：结果存在但口径不能结算原合同。

`CENSORED` 不可自动判输，`UNKNOWN` 不可被保守零值替代，`ACQUIRED` 也不可自动判为成功。若并购后业务可按稳定 perimeter 延续，可以继续观察；否则在边界断点停止。

经营 outcome、普通股 owner-cash recovery 和证券 terminal return 分开结算。缺少退市收益不能用最后交易价或 `0` 替代，经营持续也不能证明原普通股没有永久损失。

当前样本规模不足以支持正式 hazard、competing-risk 或多状态统计估计。第一阶段只实现兼容这些方法的事件账本和 risk set；等跨行业事件量、时长和字段达到预注册门槛后再决定是否建模。

## 6. source package 与 cohort 的新关系

### 6.1 source receipt 不等于关闭公司名单

static PDF 的价值是复现历史信息集和阻止结果泄漏，不是把训练库永久固定为一个五公司文件。新设计分开：

- `SourcePacketReceipt`：一批已读文件的身份不可变；
- `EvidenceCarrierRegistry`：可在 Comparative Episode freeze 前追加新批次；
- `ComparativePanelFreeze`：target、comparators、排除、顺序、结果合同真正不可变。

追加批次必须仍由独立 curator 提供 cutoff-before static official PDF，并记录预声明的成员选择规则。已经看见某项行动后，只能按事前冻结的 eligibility predicate 招募全部合格 comparator，不能自由挑选“更像”的公司。任何 outcome exposure 立即失去 PIT 资格。

### 6.2 五家公司只属于 topology-specific 门

当前 V5 peer-panel topology 仍保留 target 加足够独立 peers、同一机制暴露、连续 D3/D4 和不替换规则。它的容量门没有被取消，但只约束 `RELATIVE_CAUSAL / V5_PEER_PANEL`。

未来若使用 within-company interrupted time series、matched event、synthetic control 或其他设计，必须建立单独的 admission version、识别假设和反例 fixture。不能为了绕过 V5 而给现有案例改名。

### 6.3 当前水泥 H1 的正确身份

[水泥 H1 static package](cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json) 已通过 strict preflight，并返回 `STAGE0_FEASIBILITY_REVIEWABLE`。它证明 25 份 cutoff-before static PDF 和五家 evidence carriers 可进入受控读取；其中三家为 `PENDING_ACTION_WINDOW_REVIEW`，两家为 `KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK`。

在新设计下：

- 五家公司都可进入 2018 cutoff 的 Industry History Universe；
- 两家 scope/control break 可继续承载行业史或 Lifecycle/Teaching Case，不得进入不匹配的 comparator panel；
- 三家 pending 可进行 H2 action screen；
- 若出现可训练行动，系统可在结果读取前按冻结 eligibility predicate 追加新的 static peer-recruitment package；
- 最终仍无法形成 comparator 时，该对象降级为 Teaching/Lifecycle Case，而不是整批资料作废。

当前代码仍执行“既有 H1 roster 关闭且 H2 不得新增公司”的旧契约。实现迁移完成前，上述追加能力只是设计，不得绕过现有 validator 手工执行。

## 7. learning 权限

训练对象沿以下权限梯度上升，不能跳级：

```text
INDUSTRY_CONTEXT
  -> TEACHING_ONLY / LIFECYCLE_ONLY
  -> BOUNDARY_METHOD_ELIGIBLE
  -> SELECTION_METHOD_ELIGIBLE
  -> METHOD_CANDIDATE
  -> HOLDOUT_EVALUATED
  -> REPORT_USE_AUTHORIZED
```

- 行业史改变 `RESEARCH_AGENDA`，不提供当前公司事实；
- Teaching/Lifecycle 产生问题库、反例、禁止替代和 permanent-loss patterns，不计方法表现；
- PIT 但不诊断的 episode 可形成窄的 measurement/boundary learning；
- 只有 outcome-sealed、方向性诊断且跨公司应用成功的 Comparative Episode 才能形成选择方法候选；
- Holdout 只评价冻结方法，不回写同一版本；
- 报告使用权必须由独立 holdout 和同 cutoff 报告 A/B 验收授予。

正式 learning 的变化单位不是“记住这家公司后来怎样”，而是下一对象的一项可核查变化，例如：新增一个反方、禁用一个 proxy、改变 source acquisition 顺序、增加一座 scope bridge 或收窄一条现金传导。

## 8. 更高效的运行体系

### 8.1 三段式取证

1. **Universe shallow pass**：低成本建立成员、状态和 lifecycle 时间轴，不要求每家公司所有 D2--D4。
2. **Carrier deep pass**：只对能回答材料性问题的主体重建 responsibility unit、机制和字段连续性。
3. **Comparative strict pass**：只有准备做相对因果主张时，才投入完整 peer panel、cash bridge、outcome seal 和独立审阅。

这使缺 comparator 只停止第三段，不再删除前两段产物。

### 8.2 可降级，不作废

```text
Comparative candidate
  -> comparator sufficient: freeze Comparative Episode
  -> action/process useful but comparator insufficient: Teaching/Lifecycle Case
  -> only source coverage useful: EvidenceCarrierSet
  -> coverage boundary known: IndustryHistoryUniverse
```

降级必须降低权限，不能改写事实。这样既避免为了凑样本放松因果门，也避免昂贵资料因一个字段缺失全部报废。

### 8.3 下一任务选择

Research Policy 不按“最容易通过”选择案例，而是判断：

- 会不会改变企业经营、永久损失、估值或买点；
- 当前最材料性的未知是什么；
- 哪个对象能区分竞争解释或补足缺失的 lifecycle/topology；
- 取得证据的成本是否值得；
- 找不到时应降级、停止还是修 acquisition module。

使用 `HIGH / MEDIUM / LOW / STOP` 做判断，不引入伪精确总分。

## 9. 对黄金报告和买点的接口

### 9.1 黄金报告

| 报告层 | 训练输入 | 权限边界 |
|---|---|---|
| `RESEARCH_AGENDA` | cutoff-safe 行业史、lifecycle patterns、已授权 method questions | 只决定问什么、找什么、哪些 proxy 禁用 |
| `JUDGMENT_SYNTHESIS` | 当前公司、当前 cutoff 的证据与冻结 CJO | 历史案例结局不能成为本公司事实 |
| `INVESTMENT_ENRICHMENT` | CJO driver ranges、owner-cash bridge、价值路线 | 只有 CJO 冻结后才计算 |
| `REPORT_A_B_EVALUATION` | 同 cutoff baseline 与训练增强版 | 评价材料性判断改善，不按篇幅或文风打分 |

行业史和消失公司对黄金报告的主要贡献，是让 Agent 更早识别行业进入退出、资本毁灭、perimeter 转移、管理层适应和永久损失路径；它们不直接提供“当前公司会有相同结局”的概率。

### 9.2 定量买点

买点训练是后续独立 lane：在同一 cutoff 冻结 CJO、估值身份、市场价格、`ExpectationGap`、`BuyBand`、反转条件和简单基线，再在 3/5 年窗口分别结算经营兑现、owner cash、价值变化和价格回报。

价格结果不能反向决定企业机制是否正确；经营判断正确也不代表买价合理。只有多个预注册对象相对基线显示决策效用，系统才可讨论买点能力。

## 10. 路线图

| 阶段 | 目标 | 当前状态 | 退出事实 |
|---|---|---|---|
| `T0 CONTROL` | 现有 V3/V5、PIT firewall、结果隔离 | `COMPLETE` | synthetic 与拒绝回归通过 |
| `T1 UNIVERSE` | 行业 risk set、lifecycle ledger、反幸存者偏差 | `MULTI_CUTOFF_RUNNER_IMPLEMENTED / CEMENT_H1_SIX_CUTOFF_SERIES_VALIDATED / SYNTHETIC_LIFECYCLE_VALIDATED` | 后续真实 lifecycle source receipt 只可补充历史对象，不授予比较权限 |
| `T2 TEACHING` | Teaching/Lifecycle runner 与课程资产 | `LIFECYCLE_TEACHING_ACCEPTED / R104_BOUNDARY_TEACHING_PROJECTED / REAL_HUAXIN_PERIMETER_CASE_ACCEPTED` | 单公司、已消失公司可运行且不会获得选择权限 |
| `T2A FORECAST` | PIT Company State Forecast、相对轨迹与 prequential settlement | `CEMENT_2018_FIVE_COMPANY_FORECAST_FROZEN / THREE_COMPANY_REFERENCE_TOURNAMENT_FROZEN / R05_PROSPECTIVE_SIGNAL_SHADOW_REGISTERED` | 单公司 forecast 不需 action/H2；历史 pilot 仅 `MODEL_MEMORY_MITIGATED`，结果只能由独立 custodian 结算 |
| `T3 COMPARATIVE_INTAKE` | append-only carrier registry、claim-specific admission、V5 panel freeze | `ONE_CEMENT_H1_RECEIPT / REGISTRY_AWARE_V5_EPOCH_SYNTHETIC_ACCEPTED / REAL_H1_CARRIER_REGISTRY_OPEN / H2_NO_PRIMARY_ACTION_SCOPE` | 新 H2 action scope 后，新增批次只在 freeze 前按规则追加 |
| `T4 FIRST_COMPARATIVE` | 第一条真实方向性 Comparative Episode | `NOT_STARTED` | outcome-sealed 结算为具诊断性方向结果 |
| `T5 LEARNING_TRANSFER` | learning 改变不同公司冻结前研究 | `NOT_STARTED` | independent application receipt |
| `T6 HOLDOUT` | 冻结方法并评价 R-103 | `LOCKED` | 独立 evaluator 完成有限结论 |
| `T7 GOLDEN_REPORT_AB` | 同 cutoff 报告决策效用 | `LOCKED` | 材料性结论或区间改善被独立确认 |
| `T8 BUY_POINT_EVAL` | CJO 到预期差/买点的历史评价 | `DESIGN_ONLY` | 多对象预注册、经营与价格分层结算 |
| `T9 FORWARD` | 少量真实未知结果哨兵 | `FUTURE` | 历史体系成熟后的外部校准 |

T1、T2 和 T3 可并行；T4 的困难不再阻断 T1/T2。T6 之前不得释放选择方法给报告，T7/T8 之前不得宣称训练改善投资结论或买点。

## 11. 最小实现工作包

### WP-R1 对象与 schema

- 新增 `IndustryHistoryUniverseSnapshot`、`LifecycleEvent`、`EvidenceCarrierRegistry`；
- 在案例上增加 `claim_class / object_class / allowed_outputs`；
- lifecycle 分开实体、证券、业务连续性及观察状态；
- lifecycle 保存 time origin、delayed entry、start/stop interval、`absorbing_for[]` 和 successor；
- 不重写现有 V5 bundle、feedback 或 learning 的 canonical 语义。

### WP-R2 validator 与权限

- 移除非比较对象上的全局固定公司数量门；
- 在 V5 peer-panel 上保留 topology-specific 容量和 D3/D4 门；
- 拒绝退出公司被静默删除、`CENSORED` 被判输、post-cutoff context 进入 PIT；
- Teaching/Lifecycle 永远不能解锁 method freeze、R-103 或 report use。

### WP-R3 source registry 迁移

- 保留现有 H1 receipt 不变；
- 实现 freeze 前 append-only static batch 与 eligibility predicate；
- episode freeze 后拒绝新增、替换或重排 target/comparator；
- 把水泥 H1 同时投影为 evidence carriers 和 2018 industry universe seed。

### Registry-aware comparative admission 的 epoch 边界

`JUDGMENT_SELECTION_ADMISSION_V5_2_COMPARATOR_PANEL` 是新的 canonical V5 method epoch：只将外部 comparator 下限从三名调整为两名；仍要求独立控制、共同驱动、非平行行动、非干扰、完整 D3/D4 与同一 outcome lifecycle。`JUDGMENT_SELECTION_ADMISSION_V5_REGISTRY_V1` 已以 synthetic fixture 验收为独立 comparative-admission epoch；它以原样 V5 economic selection bundle 作为唯一被冻结、结算与报告消费的经济根，并以 registry ID、pre-seal event sequence、target/panel carrier IDs、逐 carrier pre-outcome disposition 和独立 review 绑定该根。binding 不是第二份 selection bundle、不得复制 metric/outcome contract，也不得单独供 resolver、report 或 quant 消费。

seal 从持久化 H1、H2、FROZEN carrier registry 与 immutable static batch receipt 重建 identity/source map，随后原子写入 binding 与同一 V5 freeze。recruited carrier 的 cohort D2/D3/D4 field history 逐项匹配其 immutable `carrier_static_coverage`（carrier、period、field、source、PDF page）；stale registry state 会令整次 seal 回滚。任何新增 carrier 的静态 PDF 仍须具备 issuer/RU/perimeter/unit、page 与 fiscal-period identity，并严格早于沿用的 cohort/action cutoff；若要放宽这个时间合同，必须另开 epoch，不能借 recruitment 改写现行 V5 语义。legacy V5 root 与 seal 对追加 carrier 继续拒绝。

### WP-R4 runner 与迁移

- `build_industry_history_series_from_h1()` 已按 H1 static-PDF 可得日生成 company×cutoff snapshot：后披露公司不回填 earlier cutoff，只有带官方 static-PDF、发布时间与页码绑定的 `CUTOFF_VISIBLE` lifecycle 事实改变其后的 risk status；一旦经济实体/经营业务/perimeter/control 已退出，后续 `SURVIVED` 不能重开该 risk set；
- 水泥 H1 的 2013--2017 年报已生成六个 2014--2018 cutoff snapshot。`600801` 的 2017 perimeter break 已作为独立、teaching-only 的真实 lifecycle receipt 接纳；它不推广为整个水泥行业的退出、失败或可比性结论。其余退出与删失语义仍只由 synthetic fixture 验收；
- `admit_lifecycle_teaching_case()` 继续服务 lifecycle 专题；课程层另由 `judgment_training_curriculum.py` 登记通用 Teaching，不要求每个案例都有 lifecycle event。两者都不能生成 comparative、方法冻结、report 或 investment 权限；
- `project_mixed_boundary_episode_to_teaching_case()` 已将 R-104 的独立 post-outcome `MIXED_MECHANISM_BOUNDARY` 与其无 learning 权限投影成一个 Boundary Teaching Case；它只保留“D3 经营改善不能替代相反 D4 owner-cash”这一禁止替代项，不能改变方法或释放 R-103；
- 真实 Huaxin perimeter teaching receipt 已独立提交；不得把水泥 Industry History、该 receipt 或其已知 boundary 直接升格为 Comparative、方向 learning 或 report/investment 权限；
- 再把 current H1/H2/V5 映射为 Comparative lane；
- 现有 R-62/R-69/R-102/R-104 权限原样保留，不追溯升级；
- R-103 继续 sealed，不读取、不迁移结果。

### WP-C0 能力课程与案例库

- `judgment_training_curriculum.py` 已建立四轨课程合同、八类能力单元、company-cluster 计数和角色化候选路由；
- 初始容量范围是 Teaching 20--30、Blind 8--12、Holdout 4--6、Prospective 1--3，只用于安排工作，不自动授予能力或方法效用；
- 已知结果的本地资料池登记为 teaching candidate，不计已完成案例，也不计能力证据；
- 课程按初始三条 Teaching 后一条 Blind 的节奏交错，避免只读 worked examples 而不练结果前检索；
- `RELATIVE_CAUSAL` 之外的企业判断和单公司机制默认 `comparative_mode=NOT_REQUIRED`；
- 现有 `judgment_training_program.py` 保留为严格评价、方法冻结和发布控制面，不再充当 Teaching 的启动门。

### WP-F0 PIT Company Forecast epoch

- 新增 `PITCompanyStateForecast`：只绑定一个 `company × cutoff` risk-set member、H1 static source packet 与 1/3/5 年六维状态概率；`EVIDENCE_INELIGIBLE` 记录 acquisition coverage，`MODEL_UNCERTAIN` 必须给 ordered-state 的完整概率分布或一个可结算 binary-event 概率；
- 新增 `RelativeTrajectoryTournament`：逐 normal earnings、ROIC/经营利润率、现金转换/资本开支、杠杆、竞争位置和永久损失风险排序；参照组不是未处理 control，不得输出总冠军或行动因果；
- 新增 `ForecastSettlement`：只有 V3/V4 的独立 custodian observation receipt 与冻结 Measurement Contract 可按确定性标签逐维结算 Brier/RPS、coverage 与错误归因；V4 在预测前还要求 independent curator 从相同 H1 static-PDF packet 编译的逐字段/逐页 evidence-only receipt，任何 `MODEL_UNCERTAIN` 预测只能引用其中的确切 field identity。V1/V2 保留 audit coverage 而不可评分、不可发出 active policy；不生成综合分、因果结论、report 或 investment 权限；
- 已公开 settlement 只有在 `source_available_at <= next_cutoff` 时进入下一轮 prequential feedback；company 与 time holdout 必须双轴分离；
- 水泥 2018 pilot 复用 H1 risk-set，不读 H2/R-103/outcome；五家公司各有 forecast，三家 pending 形成 tournament，两家 known-break 只作 lifecycle/boundary；该 pilot 标记 `MODEL_MEMORY_MITIGATED`，不计最终无污染 holdout。
- 实现已冻结五份水泥 2018 binary-event state forecast 和一份三家 reference-only tournament；`600425` 的现金转换、所有 capex burden 和 leverage/resilience 缺口保留为 `EVIDENCE_INELIGIBLE`，不强行排序。R-05 的 2026 forward mechanism-signal freeze 已登记为 current `ProspectiveShadowEpisode`，结果窗口仍在 2027；它不等同于水泥 pilot、CJO 或因果结果。

### WP-F1 Forecast learning 与错误归因

- `ForecastErrorAttribution` 只绑定已冻结 forecast 与独立 settlement；direct policy 仅限 `CALIBRATION`、`COVERAGE`、`STATE_DEFINITION`、`UNCERTAINTY_POLICY` 和 `BASELINE_PERFORMANCE`，并由独立 challenger 在结果公开后审阅；
- `EVIDENCE_PRIORITY` 与 `RIVAL_HYPOTHESIS_METHOD` 永远先停在 candidate：必须有 outcome 前冻结的 simple baseline、逐 cell 配对 Brier 比较、明确 failure locus，以及公司轴和时间轴双 holdout；candidate 不会投影为 active policy；
- 新 policy 只能自下一 cutoff 起在 `RESEARCH_AGENDA` 中使用。它不能生成 CJO、估值、BuyBand、报告、因果箭头或把历史 outcome 注入下一家公司事实；
- method pairing、paired evaluation 和 attribution 使用 forecast control-plane 的独立 namespace，不能改写水泥 V1 frozen forecast 或既有 settlement。

### WP-R5 报告与定量接口

- `RESEARCH_AGENDA` 可消费 cutoff-safe universe/lifecycle 摘要与已授权方法；
- `JUDGMENT_SYNTHESIS` 仍只消费当前公司 CJO；
- 增加同 cutoff report A/B receipt；
- Buy-point lane 只先设计契约和 fixture，不在本轮声称能力。

## 12. 实现验收

最小回归必须证明：

1. 一个有完整过程证据但无 comparator 的公司可以成为 `TeachingCase`，结果为 `TEACHING_ONLY`；
2. 被收购、合并、退市或失败的公司仍留在其历史 cutoff risk set；
3. `DATA_CENSORED` 不被删除、不被判输，也不计为普通 `UNKNOWN`；竞争退出事件不被错误编码为 censoring；
4. delayed-entry 公司只从 `observation_entry_at` 进入 risk set，后见变量不能回填 earlier interval；
5. 退市、收购和合并按 `absorbing_for[]` 分开证券、控制权和业务连续性，并可指向 successor；
6. 三家可深度披露公司不会阻断 Industry History Universe、Company State Forecast 或两 comparator V5 panel；更高容量只在具体 causal topology 中单独判断；
7. 新 static batch 在 Comparative freeze 前可按冻结 eligibility predicate 追加，freeze 后追加被拒绝；
8. `POST_CUTOFF_CONTEXT` 和 outcome 文件不能进入 pre-outcome packet；
9. Teaching/Lifecycle 不能生成 selection learning、冻结方法、释放 R-103 或授权报告；
10. 当前 V5 target/peer/D3/D4 规则在迁移后保持原有拒绝能力；
11. 水泥 H1 的五家公司均可进入 universe，两个 scope/control break 不会被错误放入 comparator；
12. 现有回归通过，且无需重写 R-103 或读取其 outcome。
13. `MODEL_UNCERTAIN` 维度有完整 1/3/5 年概率；`EVIDENCE_INELIGIBLE` 维度没有伪造预测，二者分别进入 selective-risk/coverage；
14. tournament 只输出逐维排序；settlement 只输出逐维 proper scores，且已结算结果不能早于下一 cutoff 进入 feedback；
15. forecast、tournament、shadow 与 settlement 均不能取得 causal、method-learning、report 或 investment 权限。

## 13. 外部研究依据与迁移边界

- [Shumway, The Delisting Bias in CRSP Data (1997)](https://doi.org/10.1111/j.1540-6261.1997.tb03818.x)：负面退市回报经常缺失且幅度大，支持保留退出对象并显式记录缺失结果；不提供 Turtle 的公司失败概率。
- [Brown et al., Survivorship Bias in Performance Studies (1992)](https://doi.org/10.1093/rfs/5.4.553)：幸存者截断可制造虚假的可预测性，支持按历史 cutoff 建 risk set；不能把基金样本的效应量迁到企业研究。
- [Cox, Regression Models and Life-Tables (1972)](https://doi.org/10.1111/j.2517-6161.1972.tb00899.x)、[Putter et al., Competing Risks and Multi-State Models (2007)](https://doi.org/10.1002/sim.2712) 与 [Fine & Gray (1999)](https://doi.org/10.1080/01621459.1999.10474144)：支持分开事件类型、时间和 censoring；当前 Turtle 样本不足，不应立即拟合 hazard 模型。
- [Andersen & Gill (1982)](https://doi.org/10.1214/aos/1176345976) 的 start-stop counting-process 表示和 [Eurostat-OECD Business Demography Manual](https://doi.org/10.1787/9789264041882-en) 对 merger/takeover/restructuring 的分类，支持 delayed entry、时变状态及法人/业务连续性分离；它们不定义 Turtle 的投资损失。
- [Hernan & Robins, Emulating a Target Trial (2016)](https://doi.org/10.1093/aje/kwv254)：支持在比较问题中冻结 eligibility、time zero、intervention、comparator、outcome 和 follow-up；它不让年报观察自动获得因果识别。
- [Gneiting & Raftery, Strictly Proper Scoring Rules (2007)](https://doi.org/10.1198/016214506000001437) 与 [El-Yaniv & Wiener, On the Foundations of Noise-free Selective Classification (2010)](https://jmlr.org/papers/v11/el-yaniv10a.html)：支持用 Brier/RPS/区间分数与 risk-coverage 分开评价概率预测和弃权；它们不把分数变成企业机制、方法学习或投资授权。
- [ForecastBench (2024)](https://arxiv.org/abs/2409.19839) 与 [AutoCast (2022)](https://arxiv.org/abs/2206.15474)：支持按日期持续冻结问题并在后来结算；本项目只借用 prequential 时间纪律，不把语言模型历史记忆当无污染 holdout。
- [Abadie, Diamond & Hainmueller, Synthetic Control (2010)](https://doi.org/10.1198/jasa.2009.ap08746)、[Bertrand, Duflo & Mullainathan, Difference-in-Differences (2004)](https://doi.org/10.1162/003355304772839588) 与 [Callaway & Sant'Anna (2021)](https://doi.org/10.1016/j.jeconom.2020.12.001)：支持把 donor pool、干预前拟合、时间相关和处理时点当识别条件；不支持“有同行均值就有反事实”。
- [Kahneman & Klein (2009)](https://doi.org/10.1037/a0016755)、[Ericsson et al. (1993)](https://doi.org/10.1037/0033-295X.100.3.363)、[Hirt & Markman (1995)](https://doi.org/10.1037/0022-3514.69.6.1069) 与 [Baron & Hershey (1988)](https://doi.org/10.1037/0022-3514.54.4.569)：支持规律环境、清晰反馈、刻意练习、多重解释和过程/结果分离；不证明 Turtle 当前已经形成专家直觉。
- [Flyvbjerg, Five Misunderstandings About Case-Study Research (2006)](https://doi.org/10.1177/1077800405284363)：支持深度单案作为情境学习、范例和证伪来源；单案仍不能替代本项目的相对方法评价。
- [Aamodt & Plaza, Case-Based Reasoning (1994)](https://doi.org/10.3233/AIC-1994-7104) 的 `Retrieve -> Reuse -> Revise -> Retain` 与 [Gentner et al. (2003)](https://doi.org/10.1037/0022-0663.95.2.393) 的结构比较，支持 Teaching Case 配置结构同构案例和表面相似但机制不同的 near miss；`Retain` 仍只是课程资产，不自动成为 formal learning。
- [Macnamara et al. (2014)](https://doi.org/10.1177/0956797614535810) 显示刻意练习不能解释全部专业表现，进一步否定用训练时长或案例数量作能力代理。
- [DoWhy](https://github.com/py-why/dowhy) 的 `model -> identify -> estimate -> refute`、[lifelines](https://github.com/CamDavidsonPilon/lifelines) 的 event/censoring 表示、[synthdid](https://github.com/synth-inference/synthdid) 的 panel estimator 是实现经验。第一阶段只借鉴对象边界，不新增运行依赖或用库函数替代经济识别。

这些研究只支撑训练设计。它们不构成任何公司、行业、估值或买点的投资证据。
