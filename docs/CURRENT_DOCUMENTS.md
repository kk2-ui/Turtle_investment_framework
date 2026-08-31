# Turtle 当前文档清单

> 状态：`CURRENT / AUTHORITATIVE_NAVIGATION`
>
> 更新：2026-08-31

本文件只解决一件事：告诉后续 Agent 哪些文档可以决定当前状态、执行顺序和产品标准。`docs/History/` 中的文件只用于追溯，不能成为恢复入口、当前状态或实施授权。

## 2026-08-29 企业投资承保顶层重构

当前企业判断、训练、估值与黄金报告的最高层对象改为[企业投资承保系统 V1](development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md)中的 `EnterpriseUnderwritingEpisode`。它把宏观/行业处境、周期与结构、公司位置和适应、生存、正常化、owner cash、永久损失、价值路线及价格处理连接成一条连续投资主张。

现有八维 `EnterpriseJudgmentEpisode`、E0--E3、J0--J4、Forecast、Comparative 和各类 receipt 继续作为底层证据、局部反馈和兼容投影，不能再作为投资者可见的主流程或顶层进度。[企业投资承保纵向切片 V1 Goal](development/research/TURTLE_ENTERPRISE_UNDERWRITING_VERTICAL_SLICE_GOAL.md) 的 U1 与 kernel 接线已实现：Episode v2 内置 `IndustryFutureThesis`；唯一训练入口只认可完整 Episode；同一价格前主张可穿过 current-company CJO、Frozen CJO report handoff、valuation runtime 和现有经验 registry。海螺仍是 `RESULT_KNOWN_TEACHING_ONLY / WORKED_CASE`。课程一期已完成 12 个 worked case、4 个完整 Blind Replay 和一轮公平 A/B；其唯一认知隔离 A/B 为 `ENHANCED_WORSE`。Course 2A 的水泥行业经验资产达到 `TRAINING_READY`；Course 2B 的上峰水泥公司轴为 `NO_MATERIAL_UTILITY`。随后 Course 2C 以 fresh Codex、独立 custodian 与独立 reviewer 在祁连山完成未见公司检验：行业路径仍为 `NO_MATERIAL_DIFFERENCE`，但公司传导与整体效用为 `ENHANCED_MATERIALLY_BETTER`，方法最高进入 `TRANSFER_CANDIDATE`。这不授予行业预测能力、方法 release、估值、BuyBand、时间轴或投资权限。完整课程状态和历史训练资产的当前处置以[训练基线对齐](development/research/TURTLE_TRAINING_BASELINE_ALIGNMENT_20260831.md)为准。

## 2026-08-29 唯一训练集成基线

当前唯一集成入口是任务开始时干净的本地 `main`；精确 commit 只记录该任务的冻结起点，不能成为第二条长期基线。后续 Agent 只从当前本地 `main` 开工。已合入功能分支与历史 worktree 只用于追溯，不能覆盖当前状态；未合入旧分支必须先保留已提交增量，再迁移到新的当前 main worktree。下方日期更早的段落用于解释演进；与本节冲突时以本节和当前本地 main 为准。

## 2026-08-31 专家纠偏蒸馏与报告自治训练

当前训练增加一条窄的 teacher-memory 接口：[专家纠偏蒸馏与报告自治训练 V1](development/research/TURTLE_EXPERT_CORRECTION_DISTILLATION_V1.md)。它不新建 Episode、训练 runtime 或 outcome 控制面，而是把结果已知高质量报告中被接受的人工纠偏拆成经济对象、责任边界、错误机制、投资影响、反向条件和下一证据，再编译为不含教师公司事实、价格和估值数值的 `TRAINING_MEMORY`。后续仍由现有 `enterprise-underwriting-training-contract.v2`、fresh Codex 双臂、独立 reviewer 与 cutoff feedback 链验证。

首个中海物业教师包已达到 `TRAINING_READY`，包含八项材料纠偏和七张格雷厄姆到巴菲特条件化原则。该状态只证明教师材料可迁移输入已就绪；尚无未见公司 A/B、cutoff 结算、跨公司应用或报告自治验证，方法仍为 `METHOD_NOT_VALIDATED`。目标是让人工从主动纠偏者退到最终批准者；验收要求首次报告无 `OPEN / MATERIAL` 的黄金报告审阅 finding，而不是增加篇幅、字段或谨慎措辞。

## 2026-08-30 行业经验层与课程二期

行业前景训练改为明确的上游闭环：`IndustryLearningBlock -> Industry Experience Pack -> IndustryUnderwritingContext -> EnterpriseUnderwritingEpisode.IndustryFutureThesis`。Pack 是引用现有行业 block、官方 observation、机制、案例、反例和反馈的版本化 manifest，不是新事实库；公司结果只结算公司传导，行业方向必须由官方行业资料和多家公司共同结果结算。

manifest schema、机械验证器和官方行业 acquisition 已经实现。水泥 V1 离线回放继续保留为合法 `DRAFT`；V3 以独立 issuer catalog 修正 `CN:600425` 的青松建化身份，并保持 Pack 为 `TRAINING_READY`。中心路径仍是需求量近乎横盘下的价格/供给纪律驱动利润池恢复，最强反方是低基数、阶段性错峰和未解决过剩令恢复不可持续。Course 2B 上峰水泥的行业路径与公司传导均无材料差异；Course 2C 祁连山的行业路径仍无材料差异，但结果期区分了成熟核心、会计控制边界、生命周期 cohort 与资本责任的公司传导，整体为 `ENHANCED_MATERIALLY_BETTER / TRANSFER_CANDIDATE`。训练 runtime 已为 v2 合同增加显式组件决策接口；行业 Enhanced arm 现在默认读取由 Pack 与目标 cutoff Context 编译的五段 company-fact-free 精简记忆，而不是整份目标 Context。该改动只收窄输入、强化目标证据边界；尚未验证时间轴或 Agent 行业前景判断能力。当前状态以[行业经验层设计](development/research/TURTLE_INDUSTRY_EXPERIENCE_LAYER_V1_DESIGN.md)、[Course 2C 最终效用裁决](development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2C_CN600720_20180430/10_COURSE2C_FINAL_UTILITY_REVIEW.md)与[训练基线对齐](development/research/TURTLE_TRAINING_BASELINE_ALIGNMENT_20260831.md)为准。

## 2026-08-29 企业判断经验调用设计

企业判断经验调用闭环最初由[企业判断经验调用闭环 V1](development/research/TURTLE_JUDGMENT_EXPERIENCE_MEMORY_V1.md)设计，现已在 `main` 实现 source-side 经验登记、结构检索、结果前调用收据与结果后边界更新。福莱特 `CN601865@2024-04-01` 已完成一次 outcome-sealed 经验调用及 FY2024 独立结果复审：正向现金资本开支屏幕改变了“新增产能必然吞噬现金”的基准，但客户吸收、利用率、价差、维护/增长资本和可回收性仍未结算，故裁决为 `NOT_DIAGNOSTIC`，不产生迁移或方法验证。

该实现继续复用 Teaching mechanism card、Blind feedback、LearningNote、`analogy_transfer_cards` 和 CJO；没有第二套事实或 target card。当前实现状态以本地 `main`、`scripts/judgment_experience_memory.py`、`docs/development/research/experience_applications/CN601865_20240401/` 与[训练基线对齐](development/research/TURTLE_TRAINING_BASELINE_ALIGNMENT_20260831.md)为准。

## 2026-08-27 V2 训练裁决（兼容历史）

V2 企业训练采用八维问题骨架：初始条件、已实施管理行动、执行、客户/竞争响应、单位经济、营运资本/现金/资本、适应/永久损失和最强反方。八维不是评分表，也不是八道全局硬门；每维可以独立保持 `UNKNOWN / EVIDENCE_INELIGIBLE / NOT_APPLICABLE`，只限制依赖它的主张。2026-08-29 起，八维已降为 `EnterpriseUnderwritingEpisode` 的证据覆盖镜头，不再是顶层产品或训练顺序。

水泥已完成真实多公司、多 cutoff block 和多轮字段级反馈。快递 Round 8 已在预结果提交 `5613b36` 后读取预声明 FY2019 官方静态年报，并完成 15 个结果单元的局部结算。每个可评分原始数值现经官方 PDF 页级 token 重算，评价从 canonical settlement 复演并强制绑定独立 acceptance。由于 Baseline 已共享八维问题、owner-cash 边界和主要反方，两种方法又没有预冻结各自的 resolution rule，加上全国行业字段绑定错公司边界、投诉单位错误、FY2019 flow 跨越 cutoff，本轮结论是 `REAL_FEEDBACK_COMPLETED / NO_MATERIAL_METHOD_ADVANTAGE_PROVED / ARCHITECTURE_REVISION_REQUIRED`，不授予 `AVOIDED_ERROR`、方法发布或能力胜出。

该轮状态的实现来源是[训练系统顶层架构](development/research/TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md)、[企业判断路线图](development/research/TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md)和[真实训练 Goal](development/research/TURTLE_ENTERPRISE_JUDGMENT_V2_REAL_TRAINING_GOAL.md)。它们保留 V2 能力和历史结算事实；当前上位裁决改由企业投资承保系统 V1 与 G1-U Goal 决定。当前仍无完整承保方法迁移、真实公司 canonical CJO、真实估值、BuyBand 或投资授权。

## EnterpriseJudgmentEpisode v2 兼容实现状态

`J0 CONTRACT + J1 RECONSTRUCTION` 已实现为独立、cutoff-safe 的新训练入口；它不等待水泥 H2、五家公司 panel、Comparative、R-103、估值或 BuyBand。首个真实、结果封存样本是 [孚日股份 `CN:002083 × 2019-05-01`](development/research/episodes/EJE_CN002083_20190501/README.md)：五份 cutoff 前官方年报经日期精度 receipt、同一上市公司合并责任边界、空决策账本与 `INSUFFICIENT_EVIDENCE` 决策观察，编译为 E1 read model；该 J1 已登记到 canonical main DB，默认 resolver 可在 linked worktree 只读回读。它只证明企业状态/有限现金桥的可审计重建；管理行动、客户反应、竞争因果、永久损失、Forecast、Comparative、迁移、方法冻结、估值和投资授权均未启动或保持未知。后续顺序是从该 J1 选择局部机制进入 J2，随后按需要进入 J3 或 J4；旧 action-first Comparative 生产线不能反向阻断此入口。

`J2 THREADS + J3 FORECAST PROJECTION + J4 COMPARATIVE PROJECTION` 的离线工程通路已实现并完成 synthetic 回归：J2 将企业重建拆为一个 primary 与二至四个 supporting 局部线程，并以完整 J1 编译输入重放验证其来源；J3/J4 生产公共入口只接受 Frozen J1 identity，由固定控制层回读 canonical reconstruction 与 inputs，不接受调用者自带的 registry。J3 先内部重编译 J2，再只把已解析且明确可预测的 cell 转为现有 Forecast 语义的概率、区间或弃权请求；J4 同样先内部重编译 J2，只让已解析且明确声明 `RELATIVE_CAUSAL / E3_COMPARATIVE_LAB` 的单一线程进入现有 V5 准入，并要求该线程已在 J2 source 内预冻结同一机制、逐 cell 完整测量合同和来源链，防止合法 V5 静默回答另一问题。V5 或该映射不通过只影响该线程。调用者不能提交手工拼接的 J2 read model、同步篡改的 J1 read model、替换整张登记册，或在 J4 调用时临时补 bridge 绕过这两层。三层均不创建第二套事实库、Forecast 或 Comparative 引擎，也不授予 CJO、估值、报告或投资权限。这里的完成只代表 engineering adapter 可用；尚未产生真实水泥 J3/J4 对象、真实 Forecast 结算或真实 Comparative admission，真实 feedback 与迁移状态以当前水泥 block 工件为准。

## 1. 新会话固定读取顺序

1. 仓库根 `AGENTS.md`：工作方式、隔离开发、真实运行和报告生成规则；
2. 仓库根 `GOALS.md`：当前唯一执行顺序、里程碑状态和下一合法阶段；
3. 本文件：确认当前文档真源与历史边界；
4. `docs/development/LONG_TERM_ROADMAP.md`：长期阶段关系和跨系统边界；
5. 当前阶段文档 `docs/development/stages/08_REAL_REPORT_ACCEPTANCE_AND_QUALITY_CALIBRATION.md`；
6. 企业判断、训练、估值或报告任务再读 `docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md`；
7. 当前任务直接适用的产品、数据、模型或运行规范。

`progress-dashboard.html` 是便于人读的派生视图。它必须与 `GOALS.md` 一致，但不能覆盖 `GOALS.md`。

## 2. 当前项目与路线真源

| 文档 | 当前权限 |
|---|---|
| `GOALS.md` | 当前协调状态、G1/G1-U 顺序、案例范围和完成出口 |
| `docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md` | 企业判断、训练、CJO、估值和黄金报告的当前最高层对象、反馈与 U0--U5 路线 |
| `docs/development/research/TURTLE_INDUSTRY_EXPERIENCE_LAYER_V1_DESIGN.md` | 行业经验上游闭环、Pack 成熟状态、样本选择、双层结算和课程二期 2A/2B 顺序 |
| `docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_VERTICAL_SLICE_GOAL.md` | 当前 G1-U 实施范围、Magna/CN600585 纵向切片与验收出口 |
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

V2 兼容状态是 `G1_CANDIDATE_MATURATION + G1-T_ENTERPRISE_JUDGMENT_V2 / REAL_SAMPLE_CREATED + REAL_FEEDBACK_TURN_COMPLETED / TRANSFER_VALIDATED_PERIMETER_FIRST_ONLY / ROUND4_CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY / ROUND5_CANONICAL_PREOUTCOME_FROZEN / ROUND5_ENTERPRISE_V3_PUBLIC_ADAPTER_PREFLIGHT / FORECAST_EPOCH_IMPLEMENTED / MINIMAL_HISTORICAL_EPISODE_ONE_INDEPENDENT_MECHANICAL_SETTLEMENT / MINIMAL_LANE_BOUNDED_CLOSED / CN600802_CN600425_CN002003_CN002404_PROTECTIVE_MEASUREMENT_MISMATCH / COMPARATIVE_E3_PARALLEL_ONLY / FORECAST_LEARNING_CONTROL_IMPLEMENTED / DECISION_CONTRACT_GATE_IMPLEMENTED / CJO_TEACHING_MIRROR_VALIDATED / CJO_VALUATION_SETTLEMENT_VALIDATED / DECISION_UTILITY_CONTROL_IMPLEMENTED / REGISTRY_AWARE_ADMISSION_IMPLEMENTED / CEMENT_H2_NO_PRIMARY_ACTION_SCOPE`。V2 的综合训练单位为多维 `EnterpriseJudgmentEpisode`，外层以 `IndustryLearningBlock` 编排行业时期、公司 archetype、生命周期、多个 cutoff 和条件化机制综合；它们现在是 `EnterpriseUnderwritingEpisode` 的支持视图，固定公司数量只约束特定 Comparative topology。水泥 H1 已完成首个真实 block：五家公司和六个 cutoff 均保留在 E0 风险集；四个真实 E0/E1 episode、一个 J2 state-transmission teaching probe、20 条冻结公司-cutoff roster，以及两条独立 feedback settlement 位于 `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/`。首条华新反馈是保留的 `MEASUREMENT_MISMATCH`，已按冻结顺序继续到海螺的审计合并经营现金 observation；两者都只改变局部研究议程。perimeter-first 已取得窄范围 `TRANSFER_VALIDATED / PERIMETER_FIRST_MEASUREMENT_METHOD_ONLY`，不代表企业判断或管理行动学习已验证。福建水泥 `2014-04-16 → 2015-04-15` 的机制结算因 outcome 已读、J1 未进 canonical 生产链、复合 measurement cells 不可机械唯一结算且选择使用自报 completed companies，已由 superseding adjudication 永久降为 `CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY`；其原始官方数值只可进入 `POST_OUTCOME_TEACHING / DATA_COVERAGE / RESEARCH_AGENDA`。非追溯修复后，五份正式 receipts 均经完整 production validator 与 immutable roster 绑定，并机械选择 rank 18 `CN:600802 / 2015-04-15 → 2016-04-27`。`26/27` 仅为被 `28` supersede 的历史对象；活动链为 `29/30/31/32`。14 个原子 outcome cell、31 个 raw inputs、完整责任边界和 sibling-local mismatch 规则已冻结，完整 J1 已登记 canonical registry，J2/J3 仅由 Frozen J1 identity 经公共 API 投影；既有 public acquisition/submission/settlement adapter 已通过 synthetic 14-cell preflight，不需要 Forecast 伪对象。该 preflight 不是企业反馈：真实 FY2015 outcome 的 authorized、content_read、custodian_started、settlement_created 仍全部为 false，尚无企业学习或投资结论。H2 的 `NO_PRIMARY_ACTION_SCOPE` 只终止水泥 action-first Comparative 候选，不阻断 E0-E2。当前 R-62/R-69 均为 `NO_PRIMARY / NOT_FROZEN` 的结果前筛查，不能登记为 selection learning；R-61 仍是 outcome-sealed 预留留出。R-102 只保留 `MEASUREMENT_BOUNDARY`，R-104 的 D3/D4 `MIXED` 只保留无权利边界。CN:600585 的 Forecast/Minimal 历史对象只证明各自受限管线；CN:600802、CN:600425、CN:002003 与 CN:002404 的 Minimal mismatch 不是企业表现结论。只有明确提出相对因果 estimand 时才启动 E3 Comparative；该支线失败不得阻断 G1-T。当前仍无真实 `SELECTION_METHOD_ELIGIBLE` 样本、无企业判断方法 release、无 `MECHANISM_READY`、CJO、估值、报告或投资授权实例；格力仍为 `PRE_FREEZE / NO_PRIMARY / NOT_FROZEN`，G1.5 仍为 `PLANNED`。

截至 2026-08-30，G1-J 的结构化契约、运行时验证、黄金机器门和独立盲评维度已经接通；报告生成具备 `RESEARCH_AGENDA / JUDGMENT_SYNTHESIS / INVESTMENT_ENRICHMENT` 三个派生只读视图。若分析合同声明 canonical CJO/Overlay，它是生产读取、read receipt 与报告装配的唯一引用。Kernel 已让 source-bound、独立复核的完整 Episode 取得 current-company `PRIMARY_ADMITTED`，不再要求整家公司先有 `SELECTION_ADMITTED`；Comparative 只约束真正依赖选择/相对因果方法的局部 claim。Frozen CJO 的完整投影会进入 `JUDGMENT_SYNTHESIS`，valuation runtime 会自动消费其路线和现金/损失处理。课程一期已经提供完整承保 Blind feedback，但没有能力优势结论：唯一公平 A/B 的 Enhanced arm 过度悲观，方法仍待新的认知隔离 A/B 验证。真实数值估值和 BuyBand 仍须通过当前公司 CJO、估值与价格合同。服务定位与三视图边界以[企业投资承保系统 V1](development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md)、[训练反馈到黄金报告的服务定位设计](development/research/TURTLE_GOLDEN_REPORT_SERVICE_DESIGN.md)、[current-company CJO admission v1](development/research/TURTLE_CURRENT_COMPANY_CJO_ADMISSION_V1_IMPLEMENTATION.md)和[canonical CJO report binding v1](development/research/TURTLE_CANONICAL_CJO_REPORT_BINDING_V1_IMPLEMENTATION.md)为准。

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
| `docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md` | 企业投资承保顶层真源：处境、生存、正常化、owner cash、永久损失、价值路线与价格处理的统一对象 |
| `docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_VERTICAL_SLICE_GOAL.md` | 从当前 main 实现 Magna + CN600585 完整承保读模型及 CJO/valuation/report 同源投影 |
| `scripts/enterprise_underwriting_training.py` | 完整 Episode 的唯一正式训练编排入口；默认由当前 Codex 用 `render-subagent-task` 编译合同绑定任务、启动 `fork_turns=none` fresh 子 Agent，再由 `run --agent-response` 完成绑定校验与原子落盘；外部 provider 只有用户明确指定时才启用。未来 v2 合同要求每个组件显式传播到正常盈利、owner cash、融资压力、永久损失和价值路线，每条主/交叉/压力/排除估值路线再绑定具体组件，并确定性接入 CJO、valuation 与 report；旧 v1 只允许与显式登记仓库合同完整 JSON 相同的 `validate-episode / compile-bundle` 冻结回放，不能启动新训练。单独 validator、旧课程轨道和局部 inventory 不能完成训练 |
| `docs/development/research/enterprise_underwriting_episodes/CN600585_20240501_TRAINING_CONTRACT_V1.json` | 首个 checked-in WORKED_CASE 训练合同；只证明完整 Episode 入口可运行，不构成 Blind 或能力成绩 |
| `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/14_COURSE_1_COMPLETION_AUDIT.md` | 已完成企业承保课程一期的投资者读出：12 个 worked case、4 个 Blind Replay、顺丰公平 A/B 的 `ENHANCED_WORSE` 与下一轮认知隔离 A/B 要求 |
| `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2_INDEPENDENT_AB_GOAL.md` | 课程二期执行与状态真源：2A 已形成 TRAINING_READY Pack；2B 上峰公司轴为 NO_MATERIAL_UTILITY，停止扩样、时间轴未启动、方法未验证 |
| `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2B_CN000672_20180430/13_FRESH_REVIEW_FINAL_MAPPING_ADJUDICATION.md` | fresh Reviewer 的冻结映射与双层结果裁决；Arm A=Enhanced、Arm B=Baseline，整体 NO_MATERIAL_UTILITY |
| `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2B_CN000672_20180430/14_COURSE_2B_LEARNING_NOTE.md` | 负结果的材料性 MODEL 修订、DATA_COVERAGE 前提及不得扩样/回填的边界 |
| `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2B_CN000672_20180430/15_COURSE_2B_COMPLETION_AUDIT.md` | Course 2B 的最终收口：冻结裁决、Pack 状态、route required/optional 组件修订、legacy 回放边界、测试与 fresh 独立代码复审 |
| `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2C_CN600720_20180430/10_COURSE2C_FINAL_UTILITY_REVIEW.md` | Course 2C 的正式双层裁决：行业路径无材料差异，公司传导与整体效用为 Enhanced materially better，方法仅为 transfer candidate |
| `docs/development/research/TURTLE_TRAINING_BASELINE_ALIGNMENT_20260831.md` | 当前训练基线总索引：统一 main、Course 1/2B/2C、经验调用反馈，以及历史课程结论的保留与非合并边界 |
| `docs/development/research/TURTLE_EXPERT_CORRECTION_DISTILLATION_V1.md` | 把被接受的人工报告纠偏与条件化投资原则编译成 company-free TRAINING_MEMORY，并以未见公司/时间 A/B、cutoff feedback 和首次成稿材料审阅检验报告自治；首包 training-ready，方法未验证 |
| `docs/development/research/training_campaigns/EXPERT_CORRECTION_CN02669_20260831/00_README.md` | 中海物业首个结果已知教师包、来源快照、使用边界和验证入口；只有编译记忆可进入 Enhanced arm |
| `scripts/expert_correction_training.py` | 验证 ExpertCorrectionTeacherPackage 并编译不含教师公司身份、价格、事实和来源的 TRAINING_MEMORY；不生成公司判断、结算或投资权限 |
| `scripts/industry_experience_pack.py` | 验证 Pack 引用、时间角色、角色覆盖、行业/公司分层结算和成熟状态；并将 TRAINING_READY Pack + 目标 cutoff Context 编译为五段 company-fact-free 精简行业决策记忆 |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/56_industry_experience_pack_replay_v1.json` | 首个行业经验层离线回放；状态为 DRAFT，只验证工作流，不计能力 |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/60_official_industry_context_observations_v1.json` | cutoff-safe 工信部/国务院行业观察 ledger；绑定已物化 raw package、经济解释和禁止外推边界 |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/62_industry_underwriting_context_training_v2.json` | 由官方观察、多公司 block 和竞争 arena 编译的 `READY` 水泥 Context |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/63_industry_experience_pack_training_v2.json` | 水泥 V2 Pack；已追加公司轴 NO_MATERIAL_UTILITY review，声明和派生仍为 `TRAINING_READY`，不代表能力验证 |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/64_industry_experience_training_ready_review.md` | 水泥 V2 行业方向、最强反方、五家公司异质响应、修复裁决和 Course 2B 停止点 |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/69_compact_industry_decision_memory_v1.md` | 精简行业决策记忆受控样例：只保留主路径、反方、分化机制、目标验证问题与反转观察，不含目标或同行公司身份和事实；能力状态仍为 hypothesis/question only |
| `docs/development/research/TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md` | V2 组件与 V3 映射：八维、IndustryLearningBlock、多维 EnterpriseJudgmentEpisode、局部证据/因果权限和 Investment Overlay 边界 |
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
| `docs/development/research/TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md` | V2 历史训练、历史留出、结果已知教学与真实前瞻哨兵的兼容架构；不覆盖企业投资承保 V1 |
| `docs/development/research/HISTORICAL_PIT_TRAINING_COHORT_REGISTER.md` | 第一批历史训练、留出与教学对象的人读队列 |
| `docs/development/research/TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md` | 企业判断 M1–M10、V3/V5 边界和 canonical read-model 权限 |
| `docs/development/research/TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md` | 当前 U0--U5 企业承保路线；下方 H0--H10 只保留为兼容能力与历史依赖 |
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
