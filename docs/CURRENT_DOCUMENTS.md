# Turtle 当前文档清单

> 状态：`CURRENT / AUTHORITATIVE_NAVIGATION`
>
> 更新：2026-08-29

本文件只解决一件事：告诉后续 Agent 哪些文档可以决定当前状态、执行顺序和产品标准。`docs/History/` 中的文件只用于追溯，不能成为恢复入口、当前状态或实施授权。

## 2026-08-29 唯一训练集成基线

当前唯一集成入口是[训练系统统一基线](development/research/TURTLE_CONSOLIDATED_TRAINING_BASELINE_20260829.md)。
它以 `08c8620` 为能力底座，已吸收投资者判断学习 read model、家电 Minimal 真实结算、家电
四阶段训练和企业判断经验调用设计；该统一基线已通过验收，后续 Agent 只从 `main` 开工。旧功能
分支只用于追溯，不能再覆盖当前状态。下方日期更早的段落用于解释演进；与本节冲突时以本节
和统一基线清单为准。

## 2026-08-29 企业判断经验调用设计

最新训练设计增量是[企业判断经验调用闭环 V1](development/research/TURTLE_JUDGMENT_EXPERIENCE_MEMORY_V1.md)。
它最初以 `feat/judgment-first-training-iteration-12h@08c8620` 为设计基线，现已进入统一
集成分支。设计复用已有 Teaching
mechanism card、Blind feedback、LearningNote、`analogy_transfer_cards` 和 CJO；不再
新增第二套经验卡。当前缺口被收敛为 source-side 经验登记、普通研究运行时结构检索、结果前
调用收据和结果后边界更新。该设计尚未实现，不授予方法、估值、报告或投资权限，也不能覆盖
下方已完成训练事实。

## 2026-08-27 当前训练裁决

企业训练的标准问题骨架现为八维：初始条件、已实施管理行动、执行、客户/竞争响应、单位经济、营运资本/现金/资本、适应/永久损失和最强反方。八维不是评分表，也不是八道全局硬门；每维可以独立保持 `UNKNOWN / EVIDENCE_INELIGIBLE / NOT_APPLICABLE`，只限制依赖它的主张。

水泥已完成真实多公司、多 cutoff block 和多轮字段级反馈。快递 Round 8 已在预结果提交 `5613b36` 后读取预声明 FY2019 官方静态年报，并完成 15 个结果单元的局部结算。每个可评分原始数值现经官方 PDF 页级 token 重算，评价从 canonical settlement 复演并强制绑定独立 acceptance。由于 Baseline 已共享八维问题、owner-cash 边界和主要反方，两种方法又没有预冻结各自的 resolution rule，加上全国行业字段绑定错公司边界、投诉单位错误、FY2019 flow 跨越 cutoff，本轮结论是 `REAL_FEEDBACK_COMPLETED / NO_MATERIAL_METHOD_ADVANTAGE_PROVED / ARCHITECTURE_REVISION_REQUIRED`，不授予 `AVOIDED_ERROR`、方法发布或能力胜出。

当前顶层真源是 [训练系统顶层架构](development/research/TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md)、[企业判断路线图](development/research/TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md)和[真实训练 Goal](development/research/TURTLE_ENTERPRISE_JUDGMENT_V2_REAL_TRAINING_GOAL.md)。下方较早 Round 5、H2 或 Minimal lane 状态只解释历史演进，不得覆盖本节。当前仍无 `TRANSFER_VALIDATED`、严格 Comparative 方向性方法 release、canonical CJO、估值、黄金报告或投资授权。

## EnterpriseJudgmentEpisode v2 当前实现状态

`J0 CONTRACT + J1 RECONSTRUCTION` 已实现为独立、cutoff-safe 的新训练入口；它不等待水泥 H2、五家公司 panel、Comparative、R-103、估值或 BuyBand。首个真实、结果封存样本是 [孚日股份 `CN:002083 × 2019-05-01`](development/research/episodes/EJE_CN002083_20190501/README.md)：五份 cutoff 前官方年报经日期精度 receipt、同一上市公司合并责任边界、空决策账本与 `INSUFFICIENT_EVIDENCE` 决策观察，编译为 E1 read model；该 J1 已登记到 canonical main DB，默认 resolver 可在 linked worktree 只读回读。它只证明企业状态/有限现金桥的可审计重建；管理行动、客户反应、竞争因果、永久损失、Forecast、Comparative、迁移、方法冻结、估值和投资授权均未启动或保持未知。后续顺序是从该 J1 选择局部机制进入 J2，随后按需要进入 J3 或 J4；旧 action-first Comparative 生产线不能反向阻断此入口。

`J2 THREADS + J3 FORECAST PROJECTION + J4 COMPARATIVE PROJECTION` 的离线工程通路已实现并完成 synthetic 回归：J2 将企业重建拆为一个 primary 与二至四个 supporting 局部线程，并以完整 J1 编译输入重放验证其来源；J3/J4 生产公共入口只接受 Frozen J1 identity，由固定控制层回读 canonical reconstruction 与 inputs，不接受调用者自带的 registry。J3 先内部重编译 J2，再只把已解析且明确可预测的 cell 转为现有 Forecast 语义的概率、区间或弃权请求；J4 同样先内部重编译 J2，只让已解析且明确声明 `RELATIVE_CAUSAL / E3_COMPARATIVE_LAB` 的单一线程进入现有 V5 准入，并要求该线程已在 J2 source 内预冻结同一机制、逐 cell 完整测量合同和来源链，防止合法 V5 静默回答另一问题。V5 或该映射不通过只影响该线程。调用者不能提交手工拼接的 J2 read model、同步篡改的 J1 read model、替换整张登记册，或在 J4 调用时临时补 bridge 绕过这两层。三层均不创建第二套事实库、Forecast 或 Comparative 引擎，也不授予 CJO、估值、报告或投资权限。这里的完成只代表 engineering adapter 可用；尚未产生真实水泥 J3/J4 对象、真实 Forecast 结算或真实 Comparative admission，真实 feedback 与迁移状态以当前水泥 block 工件为准。

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

当前状态是 `G1_CANDIDATE_MATURATION + G1-T_ENTERPRISE_JUDGMENT_V2 / REAL_SAMPLE_CREATED + REAL_FEEDBACK_TURN_COMPLETED / TRANSFER_VALIDATED_PERIMETER_FIRST_ONLY / ROUND4_CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY / ROUND5_CANONICAL_PREOUTCOME_FROZEN / ROUND5_ENTERPRISE_V3_PUBLIC_ADAPTER_PREFLIGHT / FORECAST_EPOCH_IMPLEMENTED / MINIMAL_HISTORICAL_EPISODE_ONE_INDEPENDENT_MECHANICAL_SETTLEMENT / MINIMAL_LANE_BOUNDED_CLOSED / CN600802_CN600425_CN002003_CN002404_PROTECTIVE_MEASUREMENT_MISMATCH / COMPARATIVE_E3_PARALLEL_ONLY / FORECAST_LEARNING_CONTROL_IMPLEMENTED / DECISION_CONTRACT_GATE_IMPLEMENTED / CJO_TEACHING_MIRROR_VALIDATED / CJO_VALUATION_SETTLEMENT_VALIDATED / DECISION_UTILITY_CONTROL_IMPLEMENTED / REGISTRY_AWARE_ADMISSION_IMPLEMENTED / CEMENT_H2_NO_PRIMARY_ACTION_SCOPE`。顶层训练单位已经改为多维 `EnterpriseJudgmentEpisode`，外层以 `IndustryLearningBlock` 编排行业时期、公司 archetype、生命周期、多个 cutoff 和条件化机制综合；固定公司数量只约束特定 Comparative topology。水泥 H1 已完成首个真实 block：五家公司和六个 cutoff 均保留在 E0 风险集；四个真实 E0/E1 episode、一个 J2 state-transmission teaching probe、20 条冻结公司-cutoff roster，以及两条独立 feedback settlement 位于 `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/`。首条华新反馈是保留的 `MEASUREMENT_MISMATCH`，已按冻结顺序继续到海螺的审计合并经营现金 observation；两者都只改变局部研究议程。perimeter-first 已取得窄范围 `TRANSFER_VALIDATED / PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY`，不代表企业判断或管理行动学习已验证。福建水泥 `2014-04-16 → 2015-04-15` 的机制结算因 outcome 已读、J1 未进 canonical 生产链、复合 measurement cells 不可机械唯一结算且选择使用自报 completed companies，已由 superseding adjudication 永久降为 `CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY`；其原始官方数值只可进入 `POST_OUTCOME_TEACHING / DATA_COVERAGE / RESEARCH_AGENDA`。非追溯修复后，五份正式 receipts 均经完整 production validator 与 immutable roster 绑定，并机械选择 rank 18 `CN:600802 / 2015-04-15 → 2016-04-27`。`26/27` 仅为被 `28` supersede 的历史对象；活动链为 `29/30/31/32`。14 个原子 outcome cell、31 个 raw inputs、完整责任边界和 sibling-local mismatch 规则已冻结，完整 J1 已登记 canonical registry，J2/J3 仅由 Frozen J1 identity 经公共 API 投影；既有 public acquisition/submission/settlement adapter 已通过 synthetic 14-cell preflight，不需要 Forecast 伪对象。该 preflight 不是企业反馈：真实 FY2015 outcome 的 authorized、content_read、custodian_started、settlement_created 仍全部为 false，尚无企业学习或投资结论。H2 的 `NO_PRIMARY_ACTION_SCOPE` 只终止水泥 action-first Comparative 候选，不阻断 E0-E2。当前 R-62/R-69 均为 `NO_PRIMARY / NOT_FROZEN` 的结果前筛查，不能登记为 selection learning；R-61 仍是 outcome-sealed 预留留出。R-102 只保留 `MEASUREMENT_BOUNDARY`，R-104 的 D3/D4 `MIXED` 只保留无权利边界。CN:600585 的 Forecast/Minimal 历史对象只证明各自受限管线；CN:600802、CN:600425、CN:002003 与 CN:002404 的 Minimal mismatch 不是企业表现结论。只有明确提出相对因果 estimand 时才启动 E3 Comparative；该支线失败不得阻断 G1-T。当前仍无真实 `SELECTION_METHOD_ELIGIBLE` 样本、无企业判断方法 release、无 `MECHANISM_READY`、CJO、估值、报告或投资授权实例；格力仍为 `PRE_FREEZE / NO_PRIMARY / NOT_FROZEN`，G1.5 仍为 `PLANNED`。

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
| `docs/development/research/TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md` | 企业承保判断为中心的顶层真源：八维判断格架、IndustryLearningBlock、多维 EnterpriseJudgmentEpisode、局部证据/因果权限和 Investment Overlay 边界 |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_V2_REAL_TRAINING_GOAL.md` | J0/J1/J1A/J2 与 Rounds 5-8 真实反馈记录；八维已采用，Round 8 因责任边界和 mixed-clock 问题保持 architecture revision required |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/08_investor_readout.md` | 首个真实水泥 V2 block 的投资者可读读出、feedback 与权限边界；底层 JSON 是该读出的可验证工件 |
| `docs/development/research/industry_learning_blocks/CN_FRANCHISE_EXPRESS_2018_2019/13_investor_readout.md` | 快递 Round 8 的投资者读出：记录 6/6/3 字段结算、无方法优势裁决、页级数值核验和下一次八维 A/B 的修订条件 |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_EPISODE_J0_IMPLEMENTATION.md` | `EnterpriseJudgmentEpisode` J0 的 read-only manifest、逐 claim/cell 权限矩阵与非追溯边界 |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_RECONSTRUCTION_J1_IMPLEMENTATION.md` | J1 的日期精度 SourcePacketReceipt、同一责任边界企业重建、局部证据状态、无材料行动路线与 J0 精确绑定 |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_MECHANISM_J2_IMPLEMENTATION.md` | J2 局部机制线程、逐 claim 权限和 J3/J4 明示路由；线程失败不升级为企业或行业全局失败 |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_FORECAST_J3_IMPLEMENTATION.md` | J3 对现有 Forecast 语义的 request-only 投影、逐 cell coverage 与错误归因权限；不生成预测、因果或 CJO |
| `docs/development/research/TURTLE_ENTERPRISE_JUDGMENT_COMPARATIVE_J4_IMPLEMENTATION.md` | J4 对现有 V5 的单线程准入投影；必须绑定已解析 J2 view，失败不阻断 E0-E2、其他线程或 IndustryLearningBlock |
| `docs/development/research/episodes/EJE_CN002083_20190501/README.md` | 孚日股份单公司 E0/E1 工程样本：可复用其 source/DecisionContract/重建/J0 绑定，但它不是 V2 水泥 IndustryLearningBlock 主线 |
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

## Round 5 Enterprise V3 当前边界

活动链仍为 `29/30/31/32`，`26/27` 只由 `28` 标记为 superseded。Enterprise
结果采集的生产协议是 custodian 提交已定位的 field records；本轮不宣称自动
解析 PDF。14 个 cell、31 个 raw input 的 synthetic preflight 已覆盖公共
acquisition、canonical persistence/replay、重复提交幂等、篡改拒绝、PIT clock
和 sibling-local mismatch；不需要 Forecast 伪对象。真实 FY2015 的
`authorized/content_read/custodian_started/settlement_created` 仍全部为 `false`，
不产生训练、企业判断、CJO、估值、报告或投资权限。

## 6. History使用规则

`docs/History/` 保存被替代的交接、旧状态日志、V12入口、迁移规划和历史设计。使用规则：

1. 默认检索和新会话恢复不读取 History；
2. 只有追溯设计原因、旧失败或审计历史时才读取；
3. History中的“当前、下一步、已接受、已启动、唯一入口”全部按历史时点解释；
4. History不能覆盖 `AGENTS.md`、`GOALS.md`、当前路线图、当前阶段规范、当前schema或代码；
5. 若从历史文件吸收方法，必须在当前文档或实现中重新裁决，不能直接恢复旧状态。

仓库不再维护“当前handoff文档”。中断恢复统一读取 `GOALS.md`、本清单和当前阶段规范。
