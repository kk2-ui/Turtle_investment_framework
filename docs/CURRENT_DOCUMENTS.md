# Turtle 当前文档清单

> 状态：`CURRENT / AUTHORITATIVE_NAVIGATION`
>
> 更新：2026-08-23

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

当前状态是 `G1_CANDIDATE_MATURATION / IN_PROGRESS`，当前内部前置门为 `G1-J_JUDGMENT_CONTRACT`：复用已有书籍方法案例卡与基准率候选，把中心路径、可证伪前瞻判断和追加式结果结算接入黄金接纳契约。G1.5 已进入正式路线但仍为 `PLANNED`；路线落库不等于已启动24份报告生产。

截至 2026-08-23，G1-J 的结构化契约、运行时验证、黄金机器门和独立盲评维度已经接通；报告生成另已具备 `RESEARCH_AGENDA / JUDGMENT_SYNTHESIS / INVESTMENT_ENRICHMENT` 三个派生只读视图，普通合同包和 PIT CJO/投资工具面可以消费受控行业问题、正式 feedback/control-event 谱系准入的候选方法提示及同 cutoff 公司判断前置物。PIT 在没有逐条 cutoff-safe 快照前禁用全局行业 prior 与经验基准率，并以 refresh generation 的读取收据阻止模型忽略 handoff。现行报告仍须冻结 3—5 项可结算判断；有方向性证据时才可选择中心路径，无方向性证据必须保留 `NO_PRIMARY`。`NO_PRIMARY` 可以是完整 CJO，但不能成为投资增强前置物。该工程接线不等于内容或训练效果通过：当前格力仍是 `PRE_FREEZE / NO_PRIMARY / NOT_FROZEN`，须在不读取未来结果的条件下完成全链路生成与独立复核；仓库仍无真实 V1/V2 配对黄金报告、真实未来经营结算、`MECHANISM_READY` 实例或 L1–L5 能力优势结论。

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
- Phase 10 只有P10-A基础设施处于实现/工程诊断范围；实际多公司走步回测、参数校准、外部执行结算和组合结论仍被锁定；
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
