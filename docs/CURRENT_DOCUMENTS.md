# Turtle 当前文档清单

> 状态：`CURRENT / AUTHORITATIVE_NAVIGATION`
>
> 更新：2026-08-26

本文件只解决一件事：告诉后续 Agent 哪些文档可以决定当前状态、执行顺序和产品标准。`docs/History/` 中的文件只用于追溯，不能成为恢复入口、当前状态或实施授权。

## 1. 新会话固定读取顺序

1. 仓库根 `AGENTS.md`：工作方式、隔离开发、真实运行和报告生成规则；
2. 仓库根 `GOALS.md`：当前唯一执行顺序、里程碑状态和下一合法阶段；
3. 本文件：确认当前文档真源与历史边界；
4. `docs/development/LONG_TERM_ROADMAP.md`：长期阶段关系和跨系统边界；
5. 当前阶段文档 `docs/development/stages/08_REAL_REPORT_ACCEPTANCE_AND_QUALITY_CALIBRATION.md`；
6. 当前任务直接适用的产品、数据、模型或运行规范。

`progress-dashboard.html` 是便于人读的派生视图。它必须与 `GOALS.md` 一致，但不能覆盖 `GOALS.md`。

## 2. 当前项目与路线真源

| 文档 | 当前权限 |
|---|---|
| `GOALS.md` | 当前协调状态、G0–G6 顺序、案例范围和完成出口 |
| `docs/development/LONG_TERM_ROADMAP.md` | 长期阶段、依赖、Turtle/年糕边界和Phase 10限制 |
| `docs/development/GOLDEN_REPORT_BIDIRECTIONAL_RESEARCH_ROADMAP.md` | G1.5及后续双向层级研究的正式路线 |
| `docs/development/stages/08_REAL_REPORT_ACCEPTANCE_AND_QUALITY_CALIBRATION.md` | 当前Phase 08产品与验收规范 |
| `progress-dashboard.html` | 当前状态的人读摘要；派生视图 |

当前 acquisition/measurement 状态：对后续新增的 Minimal Historical Episode，
`OutcomeSourceInventoryReceipt` 已成为 contract-only outcome access 与 numeric
observation 之间的必经控制。它只冻结唯一 official static-finalpage source 的
identity、availability precision 与 page locator，或保留 value-free
`MEASUREMENT_MISMATCH`；不追溯改写既有 episode，且不授予 learning、CJO、估值、
报告或投资权限。

对下一份新 Minimal object，Measurement Contract v2 还必须在 forecast 前冻结
CNINFO provider/version、security code、organization ID、annual-report category、
bounded query dates/page size 与 static-finalpage policy。该 organization ID 来自独立的
`TECHNICAL_ROUTE_IDENTITY`：它仅记录官方 stock-map 的 `code -> orgId`、resolver
endpoint/version 与观察时间，不含公司名称、公告、PDF 或任何 outcome，且必须精确绑定已冻结的
公司/issuer。custodian inventory 只能从 stored contract 导出该 route。缺少或不匹配该技术
路由身份时，不得授权 outcome access。既有 v1 artifacts 仅保留 history/readability，不能
retrofit 或发起新 custody flow。

当前状态是 `G1_CANDIDATE_MATURATION + G1-T_ENTERPRISE_JUDGMENT_V2 / REAL_SAMPLE_CREATED + REAL_FEEDBACK_TURN_COMPLETED / TRANSFER_NOT_VALIDATED / FORECAST_EPOCH_IMPLEMENTED / MINIMAL_HISTORICAL_EPISODE_ONE_INDEPENDENT_MECHANICAL_SETTLEMENT / MINIMAL_LANE_BOUNDED_CLOSED / CN600802_CN600425_CN002003_CN002404_PROTECTIVE_MEASUREMENT_MISMATCH / COMPARATIVE_E3_PARALLEL_ONLY / FORECAST_LEARNING_CONTROL_IMPLEMENTED / DECISION_CONTRACT_GATE_IMPLEMENTED / CJO_TEACHING_MIRROR_VALIDATED / CJO_VALUATION_SETTLEMENT_VALIDATED / DECISION_UTILITY_CONTROL_IMPLEMENTED / REGISTRY_AWARE_ADMISSION_IMPLEMENTED / CEMENT_H2_NO_PRIMARY_ACTION_SCOPE`。顶层训练单位已经改为多维 `EnterpriseJudgmentEpisode`，外层以 `IndustryLearningBlock` 编排行业时期、公司 archetype、生命周期、多个 cutoff 和条件化机制综合；固定公司数量只约束特定 Comparative topology。水泥 H1 已完成首个真实 block：五家公司和六个 cutoff 均保留在 E0 风险集；四个真实 E0/E1 episode、一个 J2 state-transmission teaching probe、20 条冻结公司-cutoff roster，以及两条独立 feedback settlement 位于 `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/`。首条华新反馈是保留的 `MEASUREMENT_MISMATCH`，已按冻结顺序继续到海螺的审计合并经营现金 observation；两者都只改变局部研究议程，不形成管理质量、方法、估值或投资结论。H2 的 `NO_PRIMARY_ACTION_SCOPE` 只终止水泥 action-first Comparative 候选，不阻断 E0/E1/Teaching。当前 R-62/R-69 均为 `NO_PRIMARY / NOT_FROZEN` 的结果前筛查，不能登记为 selection learning，但不阻断 E0/E1；R-61 仍是 outcome-sealed 预留留出，只有真实 `SELECTION_ADMITTED` E3 开发链完成、跨公司 application 复核并冻结方法后才可评价。R-102 只保留 `MEASUREMENT_BOUNDARY`，R-104 的 D3/D4 `MIXED` 只保留无权利边界。CN:600585 的 2018 `Forecast V4` 已在隔离开发控制面完成独立 settlement；唯一有效的后续产物是 coverage / direct forecast policy，且输出严格限于 `FORECAST_POLICY_ONLY + RESEARCH_AGENDA`。该对象在 outcome access 前没有冻结 method 或 decision-utility pairing，故不得回填，也不能证明方法提升、决策效用、跨公司迁移、method release、CJO、估值或报告使用。另一个独立的 CN:600585 `Minimal Historical Episode v1` 已完成一条 `Decision Contract → Measurement Contract → cutoff-before static evidence → blind prediction → contract-only custodian access → mechanical settlement`，只证明最小管线可闭合。CN:600802、CN:600425、CN:002003 与 CN:002404 的同类对象均在其授权边界内终止为 value-free `MEASUREMENT_MISMATCH`，没有 observation、settlement 或 outcome label；这分别保留了来源页、直接年报、技术路由或唯一映射的 acquisition/measurement 缺口，而非企业经营表现的负面结论。Minimal lane 已在当前验收点封口：除非发现新的可复用 acquisition-contract deficiency，不得再为追逐第二条结算扩展 schema、controller、adapter 或候选。所有 Minimal object 始终固定为 `MECHANICAL_SETTLEMENT_ONLY + NO_METHOD_TRANSFER_RIGHTS`。下一生产工作应是复用现有 V2 合同冻结另一真实 IndustryLearningBlock 或受控地扩大已冻结水泥 roster，不得倒退等待 H2、完整同行或 `SELECTION_ADMITTED`。只有明确提出相对因果 estimand 时才启动 E3 Comparative；该支线的失败或等待不得上卷为 G1-T blocked。Forecast、Measurement Contract、独立 settlement、paired evaluation、CJO core、Overlay 和报告只读 handoff 的工程控制已接通，但无真实 `SELECTION_METHOD_ELIGIBLE` 样本、无正式方法 release，也无 `MECHANISM_READY` 或投资授权实例。当前格力仍为 `PRE_FREEZE / NO_PRIMARY / NOT_FROZEN`；新前瞻只作为部署哨兵，G1.5 仍为 `PLANNED`。Agent 不得以结果后同行、价格或 outcome 资料补齐 PIT 缺口。

截至 2026-08-26，G1-J 的结构化契约、运行时验证、黄金机器门和独立盲评维度已经接通；报告生成具备 `RESEARCH_AGENDA / JUDGMENT_SYNTHESIS / INVESTMENT_ENRICHMENT` 三个派生只读视图。若分析合同声明 canonical CJO/Overlay，它是生产读取、read receipt 与报告装配的唯一引用；`INVESTMENT_ENRICHMENT` 还必须绑定 current-company `PRIMARY_ADMITTED` receipt，并让 admission、Frozen CJO 和 Overlay 精确复现 CJO 的 ID、公司、cutoff、方法与 resolution。裸 generic CJO、`NO_PRIMARY` 或 `MIXED` 可以被 synthesis 只读呈现，不能进入 Overlay。这只证明受控读取，不授予发布或交易权限。分层重构只允许 cutoff-safe Industry/Lifecycle 摘要进入 `RESEARCH_AGENDA`，历史结局不能成为当前公司事实；选择方法仍须经 Comparative Episode、跨公司 application 和 R-103 holdout 后授权。现行报告仍须冻结 3—5 项可结算判断；有方向性证据时才可选择中心路径，无方向性证据必须保留 `NO_PRIMARY`。该工程接线不等于内容或训练效果通过：当前格力仍是 `PRE_FREEZE / NO_PRIMARY / NOT_FROZEN`，仓库仍无真实 V1/V2 配对黄金报告、真实未来经营结算、`MECHANISM_READY` 实例或 L1–L5 能力优势结论。服务定位与三视图边界以[训练反馈到黄金报告的服务定位设计](development/research/TURTLE_GOLDEN_REPORT_SERVICE_DESIGN.md)、[current-company CJO admission v1](development/research/TURTLE_CURRENT_COMPANY_CJO_ADMISSION_V1_IMPLEMENTATION.md)和[canonical CJO report binding v1](development/research/TURTLE_CANONICAL_CJO_REPORT_BINDING_V1_IMPLEMENTATION.md)为准。

## 3. 当前产品与研究规范

| 文档 | 用途 |
|---|---|
| `docs/QUALITY_SCORECARD_V3_SPEC.md` | V3硬门、决策身份和重大主张—证据契约 |
| `docs/QUALITY_EVALUATION_V13.md` | 当前质量评估实现及V2诊断层边界 |
| `docs/READER_COVERAGE_GATE.md` | 完整读者报告覆盖门 |
| `docs/turtle_valuation_routing_and_investor_styles.md` | 估值路由与投资体系方法真源 |
| `docs/value_investing_from_graham_to_buffett_notes.md` | 书籍研究资料；不能单独覆盖现行模型契约 |
| `docs/development/INDUSTRY_KNOWLEDGE_BASE.md` | 行业机制知识库权限、升格和隔离规则 |
| `docs/development/JUDGMENT_FEEDBACK_CONTROL_PLANE_IMPLEMENTATION_SPEC.md` | 长期判断反馈、learning application 与 V1/V2 成对能力验证契约 |
| `docs/development/research/TURTLE_DECISION_UTILITY_CONTROL_V1_IMPLEMENTATION.md` | 已冻结 Forecast Pairing V2 与 paired evaluation 的候选性决策效用审阅控制；不授予方法、报告或投资权限 |
| `docs/development/research/TURTLE_GOLDEN_REPORT_SERVICE_DESIGN.md` | 训练反馈到黄金报告生成的服务定位、十模块边界与三视图 handoff 契约 |
| `docs/development/research/TURTLE_CANONICAL_CJO_REPORT_BINDING_V1_IMPLEMENTATION.md` | Frozen CJO/Overlay 的 analysis-contract 唯一引用、read receipt 与报告装配受控消费边界 |
| `docs/development/research/TURTLE_CURRENT_COMPANY_CJO_ADMISSION_V1_IMPLEMENTATION.md` | current-company PRIMARY 的 driver/cash/rival-thesis 审阅绑定，以及 Overlay/投资报告必经 admission receipt |
| `docs/development/research/TURTLE_SYSTEM_OVERVIEW_AND_INVESTMENT_PHILOSOPHY.md` | Turtle 面向投资者的总体架构、中心目标、训练分层、估值边界和 Turtle/年糕职责导航；不覆盖动态项目状态 |
| `docs/development/research/TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md` | 企业承保判断为中心的顶层真源：IndustryLearningBlock 编排多维 EnterpriseJudgmentEpisode；Forecast 为受限校准工具，V5 为低频局部因果实验室 |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_V2_REAL_TRAINING_GOAL.md` | 已完成的 J0/J1/J1A/J2 首个真实工作包及其完成记录；水泥真实多公司、多 cutoff block 不等待 H2 或 Comparative |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/08_investor_readout.md` | 首个真实水泥 V2 block 的投资者可读读出、feedback 与权限边界；底层 JSON 是该读出的可验证工件 |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_EPISODE_J0_IMPLEMENTATION.md` | `EnterpriseJudgmentEpisode` J0 的 read-only manifest、逐 claim/cell 权限矩阵与非追溯边界 |
| `docs/development/research/TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md` | claim-specific 分层训练、生命周期/退出、反幸存者偏差、source registry 与实现路线图 |
| `docs/development/research/TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md` | 历史训练、历史留出、结果已知教学与真实前瞻哨兵的当前顶层架构 |
| `docs/development/research/HISTORICAL_PIT_TRAINING_COHORT_REGISTER.md` | 第一批历史训练、留出与教学对象的人读队列 |
| `docs/development/research/TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md` | 企业判断 M1–M10、V3/V5 边界和 canonical read-model 权限 |
| `docs/development/research/TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md` | H0–H10 执行门；Universe/Teaching/Comparative/Quant 分轨与 WP-R0 迁移顺序 |
| `docs/development/research/TURTLE_AGENT_ENTERPRISE_JUDGMENT_V3_DESIGN_VALIDATION.md` | V3 offline synthetic 验收和真实 PIT/canonical adoption 边界 |
| `docs/development/research/TURTLE_STAGE0_STATIC_SOURCE_INTAKE_DESIGN.md` | curator-only strict Stage-0 static-PDF package 契约 |
| `docs/development/research/TURTLE_PIT_DISCOVERY_ENTRY_POLICY.md` | PIT source firewall 与禁止的 CNINFO 页面入口 |
| `docs/development/research/SELECTION_ADMISSION_DISCOVERY_LEDGER.md` | 已拒绝/暴露对象与 H1→H2 source-package 顺序 |
| `docs/development/research/TURTLE_SELECTION_MATERIALITY_AND_PEER_COUNTERFACTUAL_PROTOCOL.md` | 新 v3 program 的 V4 选择准入、独立材料性与固定同行反事实契约 |
| `docs/ANALYSIS_HORIZON.md` | 自适应分析时域设计 |

黄金报告的当前共同内容契约以 `GOALS.md` 第3、4节为准。质量评分、旧V12模板、旧盲评票、历史报告、敏感性完整或叙事流畅都不能单独授予黄金状态；G1-J完成后还必须通过中心路径和前瞻判断硬门。

## 4. 当前工程与运行规范

| 文档 | 用途 |
|---|---|
| `docs/RUNTIME_OPERATIONS.md` | 真实运行、模型调用、恢复和昂贵运行边界 |
| `docs/development/DEVELOPMENT_STANDARD.md` | 长任务、worktree和协作规范 |
| `docs/DB_SPEC.md` | 当前单库结构、来源优先级、重建/切换流程和数据验收门 |
| `docs/development/stages/01_OFFICIAL_EVIDENCE_PLATFORM.md` | 当前官方证据平台契约 |
| `docs/development/stages/02_DECISIVE_QUESTION_ENGINE.md` | 决定性问题契约 |
| `docs/development/stages/03_INDUSTRY_ARCHETYPES_AND_VALUATION.md` | 行业原型与估值路由契约 |
| `docs/development/stages/04_DECISION_COMPILER.md` | 决策编译与单向生成契约 |
| `docs/development/stages/05_BASE_RATE_CASE_LIBRARY.md` | 基准率案例库契约 |
| `docs/development/stages/06_MONITORING_AND_CALIBRATION.md` | 监控与后验校准契约 |
| `docs/development/stages/07_MODEL_ORCHESTRATION_AND_OPERATIONS.md` | 模型编排与运行治理契约 |

## 5. Phase 09与Phase 10边界

- Phase 09 仍为 `PLANNED`，不得因旧handoff或dashboard提前启动；
- Phase 10 只有P10-A基础设施处于实现/工程诊断范围；G1-T 可运行受限的企业判断历史开发回放和留出，但实际多公司投资回测、参数校准、外部执行结算和组合结论仍被锁定；
- G1.5 激活后登记的6公司×3时点PIT黄金报告是受限研究例外，不等于Phase 10全面启动；
- Phase 10现行契约位于 `docs/development/PHASE10_*.md` 与 `docs/development/HISTORICAL_BACKTEST_PILOT.md`；旧“启动交接”和未登记首案提案已归档。

## 6. History使用规则

`docs/History/` 保存被替代的交接、旧状态日志、V12入口、迁移规划和历史设计。使用规则：

1. 默认检索和新会话恢复不读取 History；
2. 只有追溯设计原因、旧失败或审计历史时才读取；
3. History中的“当前、下一步、已接受、已启动、唯一入口”全部按历史时点解释；
4. History不能覆盖 `AGENTS.md`、`GOALS.md`、当前路线图、当前阶段规范、当前schema或代码；
5. 若从历史文件吸收方法，必须在当前文档或实现中重新裁决，不能直接恢复旧状态。

仓库不再维护“当前handoff文档”。中断恢复统一读取 `GOALS.md`、本清单和当前阶段规范。
