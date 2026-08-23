# Turtle 判断反馈控制面实施规格

> 文档状态：`IMPLEMENTATION_SPEC / READY_FOR_EXECUTION`  
> 模块名称：`Judgment Feedback Control Plane`  
> 中文名称：判断反馈控制面  
> 当前阶段边界：`G1-J_JUDGMENT_CONTRACT` 判断反馈基础设施  
> 编制日期：2026-08-22
> 能力验证层更新：2026-08-23

## 1. 目标与问题定义

Turtle 已具备中心路径、前瞻判断、结果采集、机械结算、错误反馈、学习记录和方法评价等组件，但目前仍主要是一组可单独调用的工具。系统尚不能保证一个冻结判断在数月或数年后仍会被正确唤醒、按原合同结算，并把诊断结果落实到下一次不同公司研究。

本模块要把这些组件连接成一套长期运行的反馈系统，使每个合法冻结判断满足：

1. 冻结时登记未来结果时钟、计量合同和允许来源；
2. 到期前禁止读取或接纳结果；
3. 到期后进入确定性的反馈收件箱；
4. 采集、读取证明、逐字提取、机械结算和诊断按合法顺序运行；
5. 所有结果和状态变化以追加事件保存，不覆盖历史阶段或版本；
6. 复盘只有在改变下一次冻结前字段并通过独立审阅后，才算完成学习应用；
7. 方法学习只有在不同公司应用并经过后续复制检验后，才可以升级为可复用经验。

整个体系可称为：

> 预注册、证据驱动的双环判断学习系统  
> `Preregistered Evidence-Grounded Double-Loop Judgment Learning System`

第 10 模块只负责控制、调度、状态恢复和权限边界，不替代各研究模块的专业语义。

## 2. 当前阶段与授权边界

本模块当前只作为 `G1-J` 判断反馈基础设施推进。它不得被解释为以下能力已经启动或完成：

- Phase 10 全面多公司走步回测；
- 参数校准或经验概率自动更新；
- 投资组合收益、成交、滑点和交易执行回测；
- 自动改变估值、仓位或行动；
- 真实前瞻判断力已经得到外部验证。

历史自回放可以用于验证控制面，但只能标记为：

```text
L0 / PIPELINE_REHEARSAL / HISTORICAL_SELF_REPLAY
```

只有未见结果的真实 `JUDGMENT_SELECTION_EPISODE` 完成未来结算，形成诊断并改变下一家不同公司的冻结卡，才开始形成真实判断训练证据。

## 3. 与当前 5 项修复的关系

负责实施本规格的 Agent 应先完成当前正在进行的 5 项底层修复。本模块消费这些能力，不重新实现它们。

| 底层修复 | 控制面的使用方式 |
|---|---|
| 真实 `JUDGMENT_SELECTION_EPISODE` | 作为可登记、可结算的正式 episode 输入 |
| 分层结果时钟 | 投影为同一 claim 下不同 `stage_id` 的反馈项目 |
| 可审计 learning application | 投影为 `LEARNING_APPLIED` 事件和 application receipt |
| 错误 taxonomy | 进入独立诊断事件的两个正交分类轴 |
| S1/S2 版本化结算与 due inbox | 由追加事件账本和派生收件箱统一编排 |

控制面不得复制或旁路底层模块中的冻结验证、结果采集、谓词结算、feedback、learning 和 method evaluation 逻辑。

## 4. 必须复用的现有组件

实施前按当前分支的实际文件和接口核对，优先复用：

- `scripts/outcome_acquisition.py`
- `scripts/live_forward_signal_settlement.py`
- `scripts/judgment_feedback.py`
- `scripts/judgment_learning.py`
- `scripts/judgment_method_evaluation.py`
- `scripts/base_rate_case_library.py`
- `scripts/thesis_test_gate.py`
- `thesis_test.json` 中的 `central_path` 与 `forward_judgments`
- R05、R06 的未来结果合同
- 已接纳的真实 `JUDGMENT_SELECTION_EPISODE`

若底层修复调整了文件名，以当前 canonical 接口为准，但必须保留本规格定义的控制面语义。

## 5. 设计原则

### 5.1 反馈必须具有诊断性

结果必须能够区分预先冻结的竞争解释、测量合同和因果箭头。无法区分时，正确状态是 `NOT_DIAGNOSTIC` 或 `MEASUREMENT_MISMATCH`，不能为形成学习记录而强制归因。

### 5.2 预测与事后解释分离

冻结判断、结果采集、机械结算和事后诊断必须使用不同工件和事件。结果永远不能反写原冻结判断。

### 5.3 结算箭头而不是故事

诊断对象应是具体链条：

```text
状态 → 决策 → 机制 → 传导 → 经营结果
```

公司最后表现好坏不能自动证明原中心路径正确或错误。

### 5.4 学习必须改变下一项任务

复盘文档本身不构成学习。学习必须落实到下一张冻结卡的明确字段，并由独立 reviewer 确认变化真实存在。

### 5.5 长期等待必须可恢复

判断可能等待数月或数年。系统重启、任务中断或错过一次调度都不能丢失到期项目。当前状态必须能够由持久登记和追加事件重新派生。

### 5.6 使用最小本地实现

第一版只吸收成熟系统的持久事件历史、长期计时、人工任务和工件谱系原则，不引入 Temporal、Camunda、MLflow 等重型服务。

## 6. 核心数据单位

调度和版本化的最小单位不是整份报告或整个 episode，而是：

```text
episode_id + claim_id + stage_id
```

为该组合生成稳定的 `feedback_item_id`。同一 claim 的 S1、S2 必须是两个不同反馈项目。

每个反馈项目至少包含：

```text
feedback_item_id
episode_id
claim_id
stage_id
company_id
source_kind
source_ref
frozen_at
eligible_at
overdue_at
settlement_version_policy
source_contract_ref
measurement_contract_ref
registered_at
```

`overdue_at` 允许为空。缺少明确逾期合同不得猜测日期。

工件引用指向现有文件，不复制报告、PDF、raw package 或大型 JSON 正文。

## 7. 持久化设计

### 7.1 单一数据库

生产控制数据进入现有 `stock_analysis.db`，不得新建第二个长期数据库。测试使用 `tmp_path` 下的临时 SQLite。

数据库只保存：

- 冻结反馈项目的最小登记信息；
- 追加式控制事件；
- 工件路径和版本引用；
- 执行角色、时间和结构化诊断元数据。

数据库不保存报告全文、PDF 正文、raw/reader package 副本，也不保存股价、持仓、成交或年糕账户真源。

### 7.2 最小表结构

至少建立：

```text
judgment_feedback_claims
judgment_feedback_events
```

建议字段：

```text
judgment_feedback_claims
  feedback_item_id TEXT PRIMARY KEY
  episode_id TEXT NOT NULL
  claim_id TEXT NOT NULL
  stage_id TEXT NOT NULL
  company_id TEXT NOT NULL
  source_kind TEXT NOT NULL
  source_ref TEXT NOT NULL
  frozen_at TEXT NOT NULL
  eligible_at TEXT NOT NULL
  overdue_at TEXT
  settlement_version_policy TEXT NOT NULL
  source_contract_ref TEXT NOT NULL
  measurement_contract_ref TEXT NOT NULL
  registered_at TEXT NOT NULL
  UNIQUE (episode_id, claim_id, stage_id)

judgment_feedback_events
  event_id TEXT PRIMARY KEY
  feedback_item_id TEXT NOT NULL
  event_type TEXT NOT NULL
  effective_at TEXT NOT NULL
  recorded_at TEXT NOT NULL
  actor_role TEXT NOT NULL
  actor_id TEXT NOT NULL
  idempotency_key TEXT NOT NULL UNIQUE
  artifact_refs_json TEXT NOT NULL
  payload_json TEXT NOT NULL
  FOREIGN KEY (feedback_item_id)
```

收件箱是派生 read model，不建立第二份 canonical 状态表。

### 7.3 追加与幂等语义

- claim 登记后不可原地修改；新窗口或新合同注册新的 `stage_id` 或 episode；
- event 只允许追加；
- 相同 `idempotency_key` 和完全相同内容重复提交，返回成功且 `idempotent=true`；
- 相同 `idempotency_key` 但内容不同，返回 conflict；
- 不增加新的 hash、checksum、指纹文件或迁移框架；
- 现有冻结工件的 fingerprint 可以作为来源身份引用。

## 8. 事件模型

第一版至少支持：

```text
CLAIM_REGISTERED
ACQUISITION_STARTED
ACQUISITION_BLOCKED
OUTCOME_PACKAGE_READY
READ_ATTESTED
OUTCOME_EXTRACTED
CLAIM_SETTLED
MEASUREMENT_MISMATCH
OPERATING_OUTCOME_RECORDED
OUTCOME_EXPOSURE_BREACH
DIAGNOSIS_ACCEPTED
LEARNING_NOTE_READY
LEARNING_APPLIED
REPLICATION_ACCEPTED
CLOSED
```

每个事件必须保存作用对象、业务生效时间、记录时间、actor role、actor id、幂等键、工件引用和最小结构化 payload。

## 9. 状态模型

禁止把所有状态压成一个巨型枚举。当前状态由四条正交轴派生。

### 9.1 时间状态

```text
WAITING / DUE / OVERDUE / CLOSED
```

- `as_of < eligible_at`：`WAITING`；
- `eligible_at <= as_of` 且未到 `overdue_at`：`DUE`；
- `overdue_at` 存在、`as_of > overdue_at` 且采集未完成：`OVERDUE`；
- 合法关闭后：`CLOSED`。

### 9.2 证据状态

```text
EMPTY / ACQUIRING / BLOCKED / PACKAGE_READY / READ_ATTESTED / EXTRACTED
```

### 9.3 结算状态

```text
UNSETTLED / A_ONLY / B_ONLY / MIXED / NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH
```

若底层结算使用其他 verdict，建立明确映射，不得重新计算胜负。

### 9.4 学习状态

```text
NONE / DIAGNOSIS_PENDING / NOTE_READY / APPLICATION_PENDING /
APPLIED / REPLICATION_PENDING / CLOSED
```

所有状态都由 claim 登记和事件历史派生。删除缓存、重启进程后，使用同一数据库和同一 `as_of` 必须得到相同 inbox。

## 10. 合法状态转移

必须执行：

1. `eligible_at` 前不得提交 acquisition、结果包、提取或结算；
2. `OUTCOME_PACKAGE_READY` 前必须存在 acquisition 事件；
3. `READ_ATTESTED` 前必须存在结果包；
4. `OUTCOME_EXTRACTED` 前必须存在读取证明；
5. `CLAIM_SETTLED` 前必须存在合格 extraction；
6. settlement 必须绑定当前 `stage_id` 和 `settlement_version`；
7. `DIAGNOSIS_ACCEPTED` 必须绑定具体 settlement event；
8. `LEARNING_NOTE_READY` 必须绑定具体 diagnosis event；
9. `LEARNING_APPLIED` 必须绑定 learning note 和下一张冻结卡；
10. `REPLICATION_ACCEPTED` 必须绑定 learning application 和后续独立结算；
11. exposure breach 不得生成有效方法学习；
12. `NOT_DIAGNOSTIC` 和 `MEASUREMENT_MISMATCH` 不得变成支持或反对中心假设。

## 11. 多阶段与结算版本

### 11.1 S1/S2 不得覆盖

S1、S2 使用不同 `stage_id` 和 `feedback_item_id`。每个阶段拥有独立的 observation window、extraction、settlement、diagnosis、feedback 和 learning 状态。

### 11.2 结算版本策略

`INITIAL_DISCLOSURE`：

- 同一 stage 只接受首个合法 settlement；
- 后续更正可以作为补充工件保留，但不得改写首个结算。

`LATEST_OFFICIAL_AS_OF_EVALUATION`：

- 新版本只能追加；
- `settlement_version` 必须递增；
- 新版本必须引用上一版本；
- 新 settlement 出现后重新进入 `DIAGNOSIS_PENDING`；
- 原诊断和原 learning application 保留历史身份。

## 12. Reconcile 与 feedback inbox

实现显式 `as_of`，支持真实运行和历史演练。

建议 CLI：

```bash
.venv/bin/python scripts/judgment_feedback_control.py init --db stock_analysis.db
.venv/bin/python scripts/judgment_feedback_control.py register-experiment --db stock_analysis.db --experiment-dir DIR
.venv/bin/python scripts/judgment_feedback_control.py reconcile --db stock_analysis.db --as-of 2026-08-22
.venv/bin/python scripts/judgment_feedback_control.py inbox --db stock_analysis.db --as-of 2026-08-22
.venv/bin/python scripts/judgment_feedback_control.py append-event --db stock_analysis.db --input EVENT.json
.venv/bin/python scripts/judgment_feedback_control.py show --db stock_analysis.db --feedback-item-id ITEM_ID
```

命令名可以调整，但必须提供等价能力。

确定性队列顺序：

1. `P0`：已逾期且采集未完成；
2. `P1`：已到期，等待采集或补充合格来源；
3. `P2`：证据包已完成，等待读取、提取或结算；
4. `P3`：结算完成，等待独立诊断；
5. `P4`：learning note 已形成但尚未应用；
6. `P5`：已应用但尚未跨案例复制；
7. `P6`：即将到期；
8. `DONE`：合法关闭。

不得根据结果是否支持原判断、是否正面、是否容易形成漂亮结论或公司热度调整优先级。

执行语义采用：

```text
at-least-once execution + idempotent transitions
```

不宣称难以证明的全链路 `exactly once`。

## 13. 自动化与人工权限

自动化负责：

- claim 和 stage 登记；
- 到期判断和 inbox；
- 合法转移验证；
- 结果采集模块调用；
- 读取证明和 extraction 路由；
- 冻结谓词机械结算调用；
- 工件版本和事件关系维护；
- 检查 learning 是否落到下一张卡。

人工或独立 Agent 负责：

- 判断结果是否具有机制诊断性；
- 区分原判断错误与环境结构变化；
- 决定修改测量、机制假设还是研究方法；
- 审阅跨公司迁移是否过度泛化；
- 确认 learning application 真实改变冻结前字段。

同一模型或研究者不得在看到结果后，自动完成“诊断—修改规则—宣布学习成功”的自闭环。

## 14. 错误诊断模型

保留两套正交分类，不得合并为单一枚举。

认识论错误位置：

```text
STATE / DECISION / MEASUREMENT / MECHANISM / TRANSMISSION / ENVIRONMENT
```

研究生产根因：

```text
DATA_COVERAGE / ACQUISITION_MODULE / REASONING / MODEL / WRITING
```

例如渠道库存数据不足可以同时标为：

```text
epistemic_failure_locus = STATE
delivery_root_cause = DATA_COVERAGE
```

每份失败或退回诊断必须包含：

```text
economic_impact
missing_facts
prohibited_assumptions
executable_remediation
acceptance_criteria
```

不能只返回“未通过”、标签列表或要求重新生成。

## 15. Learning application

`LEARNING_APPLIED` 必须绑定：

- learning note；
- 来源 episode 和 company；
- 目标 episode 和 company；
- 下一张冻结卡实际改变的字段；
- 改变前和改变后的方法含义；
- 改变理由；
- 独立 reviewer 和 reviewer acceptance。

应用范围分为：

```text
COMPANY_FOLLOWUP
METHOD_TRANSFER
```

- `COMPANY_FOLLOWUP` 可以用于同一公司下一观察期，但不能证明跨公司方法能力；
- `METHOD_TRANSFER` 必须应用到不同公司；
- 同公司不得伪装成 `METHOD_TRANSFER`；
- 后者只有在后续结算和复制审阅后，才可以进入方法评价。

## 16. 适配器边界

控制面应以适配器调用现有模块。建议至少提供等价能力：

```text
register_from_thesis_test(output_dir)
register_from_experiment(experiment_dir)
run_outcome_acquisition(feedback_item_id)
record_reader_attestation(feedback_item_id, artifact_ref)
record_outcome_extraction(feedback_item_id, artifact_ref)
run_signal_settlement(feedback_item_id)
run_judgment_feedback(feedback_item_id)
record_learning_note(feedback_item_id, artifact_ref)
record_learning_application(feedback_item_id, target_episode_ref)
run_method_evaluation(batch_ref)
```

`execute_due_claim(execution_request)` 将上述结果链编排为一个窄入口。它只读取
实验目录中显式提供的 `09_outcome_execution.json`：`feedback_item_id`、
`settlement_as_of`、冻结后的有界 outcome inventory、package/event 输出根，以及
可用时的 extraction 与 exposure attestation。缺 inventory 时不开始采集；缺
extraction 时只能推进到 `READ_ATTESTED / P2`；缺 exposure attestation 时不能
结算 A/B 信号。非方向性决策、现金和资本时钟以真实 extraction 生成
`OPERATING_OUTCOME_RECORDED / NOT_DIAGNOSTIC`，不能被遗忘也不能生成选择胜负。

CJO 入口只会扫描并运行**已明确落入 due inbox**的这种 request；没有该文件时
保留 P1 任务。因此“到期”不等于“自动读取公告”，更不等于“已结算”。

适配器必须遵守：

- `thesis_test.json` 只有冻结状态才能登记；
- observation window 不完整时不得猜测 `overdue_at`；
- UNKNOWN、NO_PRIMARY、NOT_DIAGNOSTIC 和 MEASUREMENT_MISMATCH 原样保留；
- 不从 Markdown 猜测结构化 verdict；
- 不从结果反推原 prediction。

## 17. Schema 建议

避免创建过多细碎 schema。第一版建议最多增加：

```text
schemas/judgment_feedback_claim.schema.json
schemas/judgment_feedback_event.schema.json
schemas/judgment_learning_application.schema.json
```

若底层修复已经拥有等价 schema，应扩展或复用，不得重复定义。

## 18. 最低测试矩阵

### 18.1 登记与时间

1. 以 `2026-08-22` 登记 R05/R06，均为 `WAITING / NOT_YET_DUE`；
2. `as_of` 进入 S1 窗口后，只出现一个对应到期项目；
3. S2 在自身窗口前仍保持 `WAITING`；
4. 没有 `overdue_at` 时不猜测逾期日期。

### 18.2 幂等与恢复

5. 重复 reconcile 不产生重复事件；
6. 重复提交相同幂等事件返回 `idempotent=true`；
7. 相同幂等键但内容不同返回 conflict；
8. 重新打开数据库后，inbox 状态完全一致。

### 18.3 信息围栏

9. 窗口前 acquisition 被拒绝；
10. 没有结果包时不能写读取证明；
11. 没有读取证明时不能 extraction；
12. 没有 extraction 时不能 settlement；
13. exposure breach 阻断 learning note 和 learning application。

### 18.4 多阶段与版本

14. S1、S2 同时保留，任一阶段结算不得覆盖另一阶段；
15. `INITIAL_DISCLOSURE` 拒绝第二个替代式 settlement；
16. `LATEST_OFFICIAL_AS_OF_EVALUATION` 允许递增版本并保留旧版本；
17. 新 settlement version 出现后重新进入 `DIAGNOSIS_PENDING`。

### 18.5 诊断与学习

18. `MEASUREMENT_MISMATCH` 保留 UNKNOWN，不生成伪方向结论；
19. `NOT_DIAGNOSTIC` 不得进入方法学习；
20. 失败诊断缺少经济影响、事实、禁止假设、修复或验收标准时拒绝；
21. learning application 必须列出下一张卡真实改变的字段；
22. `METHOD_TRANSFER` 指向同一公司时拒绝；
23. 没有独立 reviewer acceptance 时不得标记 `APPLIED`；
24. 未经后续复制结算不得标记方法已验证。

### 18.6 阶段边界

25. 历史 self-replay 跑通全链后只产生 `L0 / PIPELINE_REHEARSAL`；
26. 至少登记一个真实中国企业 `JUDGMENT_SELECTION_EPISODE`；
27. 真实 episode 未到期时保持等待，不用历史结果提前结算；
28. 控制面事件中不复制股价、持仓、组合收益或交易账本。

## 19. 分阶段实施顺序

### M10.0 控制契约

- 固定 feedback item、事件、四轴状态和权限边界；
- 对齐现有 5 项底层修复；
- 不新增平行研究模块。

### M10.1 持久登记与收件箱

- 建表；
- 实现 claim 注册、事件追加和幂等；
- 实现 `reconcile --as-of` 和 inbox；
- 登记 R05/R06 并验证当前等待状态。

### M10.2 结果链编排

- 接入 outcome acquisition、读取证明、extraction 和 settlement；
- 支持 S1/S2 和 settlement version。

### M10.3 诊断与学习应用

- 接入双 taxonomy、judgment feedback 和 learning note；
- 建立 learning application receipt；
- 强制不同公司方法迁移和独立审阅。

### M10.4 管线演练

- 使用历史 self-replay 验证完整恢复和转移；
- 明确标记 `L0`；
- 不把演练命中计入判断准确率。

### M10.5 真实前瞻闭环

- 登记一条真实中国企业 `JUDGMENT_SELECTION_EPISODE`；
- 等待合法未来窗口；
- 完成结果采集、结算和诊断；
- 将学习应用到下一家不同公司的冻结卡；
- 后续接受复制检验。

## 20. 完成出口

工程实现完成时必须交付：

1. 变更文件清单；
2. 数据表和事件转移说明；
3. CLI 使用示例；
4. R05/R06 当前 inbox 示例；
5. 定向测试结果；
6. 历史演练结果及其 `L0` 限制；
7. 真实 episode 的登记和等待状态；
8. 与原 5 项修复逐项对应的接口说明；
9. 当前仍未验证的真实反馈能力；
10. 独立 code review 和 roadmap audit 结果。

不得仅凭 schema、CLI、合成测试或历史自回放宣告判断训练系统已经验证完成。

真正的产品级验收是：

> 一条未见结果的真实 `JUDGMENT_SELECTION_EPISODE` 完成未来结算；错误得到可审计诊断；学习改变下一家不同公司的冻结卡；独立 reviewer 确认变化真实存在；该方法随后在新结果中接受复制检验。

## 21. 明确非目标

本模块不做：

- 自动选择中心假设；
- 在结果出来后修改冻结指标；
- 自动接受错误原因；
- 自动更新估值、概率、评级、仓位或行动；
- 以股价表现替代企业判断结算；
- 使用单一总分覆盖具体机制错误；
- 建立新案例库、第二事实库或第二结果真源；
- 引入重型分布式工作流平台；
- 为理论敌手增加防御性脚手架；
- 为审计完整性重复计算 hash、路径集合或文件身份。

## 22. 研究依据

本设计吸收以下思想，但这些理论不替 Turtle 证明任何公司判断：

- Kahneman 与 Klein：专家直觉需要可学习规律和有效反馈；
- Nosek 等：预注册分离预测与事后解释；
- Collier：过程追踪使用时间序列中的诊断性证据检验机制；
- Mellers 等：概率训练、持续追踪和协作审阅改善预测校准；
- Ericsson 等：刻意练习必须指向下一项任务的具体改进；
- Argyris：双环学习不仅修正行动，还检验底层规则；
- Temporal：追加事件历史和持久计时支持长期恢复；
- Camunda：人工任务具有受理人、到期时间和完成事件；
- MLflow：运行、元数据和工件之间保持可追踪谱系。

参考来源：

- <https://psycnet.apa.org/record/2009-13007-001>
- <https://www.pnas.org/doi/10.1073/pnas.1708274114>
- <https://www.cambridge.org/core/journals/ps-political-science-and-politics/article/understanding-process-tracing/183A057AD6A36783E678CB37440346D1>
- <https://pubmed.ncbi.nlm.nih.gov/24659192/>
- <https://psycnet.apa.org/record/1993-40718-001>
- <https://hbr.org/1977/09/double-loop-learning-in-organizations>
- <https://docs.temporal.io/workflow-execution/event>
- <https://docs.temporal.io/workflow-execution/timers-delays>
- <https://docs.camunda.io/docs/components/modeler/bpmn/user-tasks/>
- <https://mlflow.org/docs/latest/ml/tracking/>

## 23. 判断架构成对实验能力

控制面现增加一个独立的**能力验证层**，用于检验“公司单独研究”与“行业/宏观增强研究”在相同公司证据和相同黄金标准下是否产生材料增量。它不替代本规格的长期反馈登记、结果真源、结算、诊断或 learning application。

当前执行入口：

```text
scripts/judgment_architecture_experiment.py
schemas/judgment_architecture_experiment.schema.json
```

执行契约固定为：

1. `report_pair_id` 是盲评产品单位；每个 `report_pair_id` 可承载 3–5 个材料判断单位。判断单位影响 `NORMALIZED_EARNINGS / OWNER_CASH / PERMANENT_LOSS / CAPITAL_RETURN`，分别结算，但不得把同一报告的多项判断伪装成多个报告质量样本；
2. `COMPANY_ONLY` 与 `INDUSTRY_MACRO_ENHANCED` 使用同一 information cutoff、同一公司 evidence package、同一结果目标、同一简单基线和同一黄金报告标准；
3. 两臂使用不同 author agent 与不同 context，均声明在冻结前未读取另一臂；公司臂禁止行业/宏观机制引用，增强臂至少引用一项具名机制或宏观情景；
4. 计划必须先预注册，两臂必须分别在结果窗口前冻结；冻结后删除配对单位会导致 plan fingerprint 失配；
5. 报告质量只在 `BLIND_A / BLIND_B` 下审阅，提交后才允许揭盲；两份报告均须满足黄金标准，结论只允许 `MATERIAL_IMPROVEMENT / NO_MATERIAL_GAIN / WORSE`；
6. 经营结果只消费现有 `judgment-feedback-card.v2`，要求两臂指向同一官方 observation 和来源，并逐一匹配预注册的 observation ID、metric、unit、简单基线方法和冻结预测；保留简单基线增量、`PENDING` 与 `NOT_COMPARABLE`；
7. 聚合只保存六类成对结果计数、判断单位数量、独立公司簇和公司/时间留出覆盖，不生成胜率、概率、准确率或总分；未见公司与未见时间两个留出轴不得复用公司集团；
8. `DUAL_HOLDOUT_COMPARISON_READY` 只表示未见公司和未见时间两轴达到预注册的独立样本门，可提交独立方法审阅；它不自动授予一般优势或生产升格。

该模块同时收紧行业机制升格：`MECHANISM_READY` 除原有跨公司候选和独立审阅外，还必须有至少两个独立公司集团的已结算支持 episode，以及至少一个 `CONTRADICTS` 或 `BOUNDARY` episode；每项都须保存 outcome/review 指针并由非机制作者独立复核。`NOT_DIAGNOSTIC` 保留在证据账本，但不冒充支持或边界。

当前只有执行器、schema 和合成回归。尚未运行真实 V1/V2 配对黄金报告，尚无真实未来经营结果，也没有 L1-L5 能力优势结论。真实运行继续服从 G1/G1.5 激活顺序和昂贵运行边界。
