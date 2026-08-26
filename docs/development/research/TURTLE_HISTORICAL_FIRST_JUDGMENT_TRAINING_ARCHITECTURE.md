# Turtle 历史优先的企业判断训练架构

> 状态：`CURRENT / LAYERED_REDESIGN_ADOPTED / IMPLEMENTATION_PENDING / REPORT_USE_NOT_RELEASED`
>
> 日期：2026-08-25
>
> 目标：用历史 PIT 逐步回放训练企业判断，以冻结历史留出检验泛化，以少量真实前瞻 episode 校准部署纪律；外部披露等待不得阻断训练主线。

上层对象、生命周期、claim-specific admission 和迁移工作包以[历史训练体系重构](TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md)为准。本文保留历史 PIT 的执行架构与权限边界；V5 是 Comparative Episode 的严格 topology，不再是所有行业史和教学训练的总入口。

## 1. 产品定义

Turtle 的“训练”不是在本仓库中重新训练基础模型权重。它训练的是可持久、可复核并能改变下一份报告的研究系统：

```text
公司与行业状态表示
  -> 竞争机制和最强反方
  -> 决策—客户—单位经济—现金—资本回报判断
  -> 结果揭示与错误定位
  -> 方法约束和行业机制
  -> 下一家公司冻结前字段
  -> 黄金报告研究议程与判断前置物
```

一次案例只有在改变下一家不同公司的问题、证据门、H-A/H-B、信号、计量合同或停止规则，并由独立 reviewer 确认后，才形成正式系统 learning。Industry History 与 Teaching/Lifecycle 可以先形成课程和边界资产，但不能因此获得 method 权限。阅读更多材料、写出更好的事后故事或把案例导入数据库，都不是正式训练闭环。

## 2. 四条独立通道

| 通道 | 主要材料 | 是否改变当前方法 | 能证明什么 | 不能证明什么 |
|---|---|---:|---|---|
| `HISTORICAL_TRAINING` | cutoff 前事实与结果包严格隔离的历史 PIT episode | 是 | 历史条件下的刻意练习、错误诊断和跨公司迁移 | 实时预测优势、概率校准或投资收益 |
| `HISTORICAL_HOLDOUT` | 在方法版本冻结前预留的未揭盲公司和时期 | 否 | 冻结方法是否泛化到未参与规则形成的对象 | 见结果后继续修改同一版本仍算留出 |
| `HISTORICAL_TEACHING` | 研究者或模型已经知道结果的案例 | 只形成边界和禁止替代，不生成正式方法 learning | 反例、测量边界和常见因果错误 | 选对/选错、样本命中或方法优势 |
| `LIVE_SENTINEL` | 结果尚未发布的少量正式 episode | 结果到期后才允许 | 成熟系统在未知结果环境中的部署纪律和外部有效性 | 在等待期间阻断历史训练，或以单次结果证明完整能力 |

项目状态按通道投影。`LIVE_SENTINEL = WAITING_EXTERNAL` 与 `HISTORICAL_TRAINING = ACTIVE` 可以同时成立；此时系统总状态是 `ACTIVE`，不能标为 `blocked`。只有内部工件失效且没有其他可执行训练时，才进入 `NEEDS_REPAIR`。

旧边界 program 的 R-62/R-69 不能授予报告使用权。当前选择开发 program 的 `method_scope=SELECTION_AND_BOUNDARY`，但这只是训练权限，不是能力声明：R-102 的真实结算全部为 `MEASUREMENT_MISMATCH / UNKNOWN`，只产生 `MEASUREMENT_BOUNDARY`；它不能形成方向性 application 或冻结选择方法。选择能力仍须另一个真实、结果隔离且最终具诊断性的 `SELECTION_ADMITTED` 开发 episode，并通过 R-103 留出后才可释放给报告。

## 3. 行业训练单元

### 3.1 不是只研究最后的幸存者

行业 cohort 必须按历史 cutoff 时可见的资格形成，后来是否存活不得参与选择。训练宇宙应保留当时符合条件的：

- 后来持续经营者；
- 长期平庸或资本回报恶化者；
- 被收购、私有化或退出上市者；
- 财务危机、业务收缩或消失者；
- cutoff 后进入行业的新竞争者，作为后续时期的新成员而非回填到早期宇宙。

“存活”只是最末端观察之一，不是正确答案。企业可能存活却持续毁灭资本，也可能退出上市但完成了合理的资本回收。终局仍按决策实施、客户/竞争反应、单位经济、营运资本与现金、资本回报五层分别结算。

### 3.2 公司 × 时点，而不是报告篇数

同一家公司可切成多个滚动时点，但这些时点属于同一 `company_cluster_id`，不得冒充多个独立公司样本。Industry History Universe 的公司数由当时 risk set 决定，Teaching/Lifecycle Case 可以只有一家公司；只有 Comparative Episode 才按其 topology 要求 target、comparator、witness 或 falsifier。一个行业的建议首轮形态可以是理论抽样后的横纵面板，但关键不是固定数量，而是尽量包含：

- 一个 focal 公司；
- 至少一个只改变关键中介条件的 near miss；
- 至少一个改变行业状态或外部约束的 boundary；
- 相同交易点和可比较结果字段；
- 公司消失、披露中断和口径改变的保守处理。

每个时期只读取当时可得资料。下一时期可以看到上一时期已经结算的 learning，但不能看到本时期 cutoff 后的结果。

### 3.3 claim-specific admission 先于固定 cohort 门

系统先登记要回答的是行业结构、单案机制、生命周期还是相对因果。Industry History Universe 只要求 cutoff、竞争范围和覆盖边界；Teaching/Lifecycle Case 只要求可追溯过程和明确的结果时间角色；只有 `RELATIVE_CAUSAL` 才进入 V5 的 target/peer/D3/D4 严格门。

V5 仍不允许“先搜一条醒目的公告，再为它补有利同行”。但 Stage-0 static-PDF package 的身份改为 `EvidenceCarrierSet`：它证明这些文件和公司可被受控读取，不等于行业全集、关闭 roster 或最终 peer panel。每个 receipt 本身不可变；Comparative Episode freeze 前，独立 curator 可按预声明的成员规则追加新的 cutoff-before static official PDF batch。看到行动后只能按已冻结的 eligibility predicate 招募全部合格 comparator，不能自由选公司。target、最终 peers、排除理由、顺序和结果合同在 Comparative Panel Freeze 后才真正关闭，之后禁止新增、替换或重排。

每名 carrier 仍必须标记 `PENDING_ACTION_WINDOW_REVIEW` 或 `KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK`。后者可以进入行业史、生命周期或教学研究，但必须从不匹配的 comparator panel 排除；前者也不等于已可比。当前 V5 代码尚未实现 append-only carrier registry，迁移前继续服从旧 H1/H2 validator，禁止人工绕过。

PIT 浏览入口继续遵守[历史 PIT 发现入口政策](TURTLE_PIT_DISCOVERY_ENTRY_POLICY.md)：动态 CNINFO 搜索、个股页和公告 detail 页都不能成为历史 discovery 入口。后来资料只可标为 `POST_CUTOFF_CONTEXT` 或 `OUTCOME`，不能进入 pre-outcome packet。

## 4. 历史逐步回放

这套运行方式属于 walk-forward historical simulation / rolling-origin backtesting，并结合过程追踪和案例迁移。步骤先分流，再按权限加深：

1. **形成历史宇宙。** 在 cutoff 时按竞争机制建立 company-time risk set，后来退出或消失者仍保留；覆盖不足写 `BOUNDED_PARTIAL / UNKNOWN_COVERAGE`。
2. **声明主张并分流。** `DESCRIPTIVE_STRUCTURE / WITHIN_CASE_MECHANISM / LIFECYCLE_TRANSITION` 可进入行业史或教学；`RELATIVE_CAUSAL` 才继续比较准入。
3. **加深 evidence carriers。** discovery 只读取当前对象权限允许的材料；PIT candidate 必须继承 cutoff、安全来源和责任边界，不能在全量采集时改题。
4. **冻结比较对象。** 只有 Comparative Episode 固定 intervention、time zero、target、comparators、H-A/H-B、基线、阈值、结果源和五层观察时钟。
5. **分层揭示结果。** 结果 reader 只按预登记包读取下一窗口，允许 `CENSORED / UNKNOWN / NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH`；退出对象不得被静默删除或自动判输。
6. **双轴诊断。** 同时记录企业经济链错误位置与研究交付根因，说明经济影响、缺失事实、禁止假设、修复和接纳标准。
7. **按权限沉淀。** Teaching/Lifecycle 只产生课程资产和边界；方向性 Comparative Episode 才可申请跨公司 method learning。
8. **方法迁移与留出。** learning 只能改变另一份仍 outcome-sealed 的不同公司对象；方法冻结后才打开 R-103，留出只评价该版本。

同一历史可以产生多个滚动 episode，但前一时点的结果只有在真实时间上已进入下一时点信息集后，才能成为下一时点输入。

## 5. 数据与权限模型

训练计划使用五个正交身份，禁止再用一个 `episode_class` 同时表达所有含义：

| 维度 | 字段 | 例子 |
|---|---|---|
| 训练对象 | `object_class` | `INDUSTRY_UNIVERSE / EVIDENCE_CARRIER / TEACHING_CASE / LIFECYCLE_CASE / COMPARATIVE_EPISODE / LEARNING_EPISODE` |
| 主张强度 | `claim_class` | `DESCRIPTIVE_STRUCTURE / WITHIN_CASE_MECHANISM / LIFECYCLE_TRANSITION / RELATIVE_CAUSAL / METHOD_GENERALIZATION / INVESTMENT_DECISION_UTILITY` |
| 程序职责 | `lane` | `HISTORICAL_TRAINING / HISTORICAL_HOLDOUT / HISTORICAL_TEACHING / LIVE_SENTINEL` |
| 来源与结果隔离 | `provenance_role + outcome_access` | `HISTORICAL_SELF_REPLAY + PIT_OUTCOME_SEALED` |
| 后续权限 | `learning_eligibility` | `CONTEXT_ONLY / BOUNDARY_METHOD_ELIGIBLE / SELECTION_METHOD_ELIGIBLE / EVALUATION_ONLY / TEACHING_ONLY / MECHANISM_SETTLEMENT_ONLY` |

硬边界如下：

- `BOUNDARY_ONLY` 计划可在 PIT 结果隔离后，为 `NO_PRIMARY` 或 `NOT_DIAGNOSTIC` 结算生成边界方法 learning；这不等于选择方法 learning；
- 只有 `SELECTION_ADMITTED` 且结果具诊断性的历史训练，才可生成 `SELECTION_METHOD_ELIGIBLE` learning；
- `SELECTION_ADMITTED` 若结算为 `NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH`，只允许以 `INSUFFICIENT_EVIDENCE + MEASUREMENT_BOUNDARY` 保存准入设计教训；其权限仅限下一候选的可观测性和来源门，禁止 `LEARNING_APPLIED`、方法冻结、留出释放和报告使用；
- `NO_PRIMARY` 仍可结算机制和训练弃权纪律，但不能伪装为路径选择学习；
- 留出永远是 `EVALUATION_ONLY`，不得生成或应用同一方法版本的 learning note；
- 结果已知教学永远是 `TEACHING_ONLY`，不得进入选择成绩；
- 实时哨兵在结果未发布时只等待或执行到期采集，不提前解释，也不阻断其他通道。

### 5.1 V5 peer-panel 经营选择样本的可观测性门

新的 `JUDGMENT_SELECTION_ADMISSION_V4` 候选在独立预审前必须先通过以下经济门；它是在 V3 的客户吸收、现金传导门之上收紧的下一代准入契约。已封存的 R-104 仍按其旧契约结算，不能倒灌或重写。

1. 当 H-A 依赖客户吸收、需求反应或价格/组合兑现时，D2 必须是与行动机械分离的三期官方字段：实际销量、活跃客户、复购，或官方独立量价拆分。提价后的收入、公告/设计产能、发货和渠道库存不能充当客户吸收。
2. 当 H-A 主张经营改善会成为正常 owner cash 时，D3 经营贡献、D4 营运资本现金和 D4 资本/重组现金必须在同一责任单元、同一口径、三个 cutoff 前时期重复出现。D4 必须扣除所有长期资产购建现金和有利营运资本释放。
3. 行动必须是同一发行人范围、可由官方来源证明为自主且增量的经营决策；行动暴露只能是已实施或不可逆发生的真实现金、已确认资产风险，或已执行净价变化乘行动前实际量。维护替换、被动合规、小项目及项目 IRR/回收期不能借公司 D3/D4 获得例外；V4 只作发行人层机制判断。
4. target 需要五个 cutoff 前年度的独立 D3、D4 原始历史；每项阈值由各自历史的 `1.4826 × MAD` 与冻结基期机械推导。D3 阈值不能税后化、现金转换或任意摊薄后变成 D4 阈值。
5. 必须冻结三至七家非同一控制集团、同一可证实市场暴露的同行。每家都有至少三期同口径 D3/D4 官方重建记录，且成员、顺序、排除理由、基期与“不替换”规则在 outcome 前锁定。相对阈值取 target 自身材料性步长与固定同行面板 action 前相对变化噪声带的较大者；未来 D3/D4 只有绝对结果与相对同行中位变化同向且跨过该双重阈值时才可判为 `A_ONLY` 或 `B_ONLY`；缺一名同行或两者冲突即为 `NOT_DIAGNOSTIC` 或 `MIXED`。
6. target 五年窗口与每名同行三年窗口必须有 source-bearing comparability register：合并范围、会计列报和经营 perimeter 三项均连续；任何重大结构断裂必须移出选定窗口，而不是靠正文解释抹平。
7. D4 必须有完整 cash bridge：OCF、全部长期资产现金、现金营运资本与行动相关现金均逐项列出。正向营运资本释放和行动现金不可被静默当作 owner cash；存在未建模的材料现金项即 `NO_PRIMARY`。
8. 客户链与成本重构链是两种显式 topology。成本重构可将 D2 标为 `NON_VOTER`，但必须用三期同边界成本驱动、H-A/H-B 相反符号和独立 reviewer receipt 替代；它绝不产生“客户已经吸收”的结论。

任何一门失败都使当前 `RELATIVE_CAUSAL / V5_PEER_PANEL` 为 `NO_PRIMARY`，不是提示模型用收入、集团现金、项目预测、任意百分比阈值或事后挑选同行补空。若过程证据仍有价值，可降级为 Teaching/Lifecycle Case，但权限必须同步降低。D2 可以在纯成本型机制中被独立 reviewer 明确判定为非因果中心并保持非投票，但不能静默省略。详细字段、计算和审阅职责见[材料性与同行反事实协议](TURTLE_SELECTION_MATERIALITY_AND_PEER_COUNTERFACTUAL_PROTOCOL.md)。

V4 是发行人同边界的经营竞争机制契约：客户链使用 `CUSTOMER_ABSORPTION → UNIT_ECONOMICS → OWNER_CASH`；纯成本／网络重构链使用 `COST_DRIVER → UNIT_ECONOMICS → OWNER_CASH` 并把 D2 固定为非投票。两者都不是所有黄金报告判断的唯一拓扑。并购整合、资本配置或资本结构若要进入选择训练，必须另立不可与 V4 混用的 admission version：至少额外冻结法律完成／实际对价、交易 perimeter bridge、被购业务客户或交易对手履约、整合现金与每股资本回报桥。它不能通过把项目、子公司或交易后的集团 D3/D4 填入 V4 而获得例外；在独立拓扑被设计、实现和验证前，这类对象保持 `NO_PRIMARY` 或 `TEACHING_ONLY`。

## 6. 状态机与控制面

版本化计划契约包括已冻结的边界 program v1 与选择开发 program v2；未来选择 learning 只能在一份新的不可追加 program v3 内完成，不能向 v2 的 R-104 追加训练 episode。新 selection program 必须不可变地声明 `required_selection_admission_version=JUDGMENT_SELECTION_ADMISSION_V4`；control registration、candidate snapshot 和 transfer target 三处版本不完全一致即拒绝。schema 为 `schemas/judgment_training_program.schema.json`。入口为：

```bash
.venv/bin/python scripts/judgment_training_program.py validate config/judgment_training_program_v1.json
.venv/bin/python scripts/judgment_training_program.py register config/judgment_training_program_v1.json --db stock_analysis.db
.venv/bin/python scripts/judgment_training_program.py status JTP:turtle-historical-primary-v1 --db stock_analysis.db --as-of 2026-08-23T18:00:00+08:00
```

以上是候选计划的执行接口。边界 program v1 已在工作区 `stock_analysis.db` 登记并冻结；选择开发 v2 已登记 R-104 与 linked R-103，但 R-104 的 `MIXED` 结算不给予 learning 或方法冻结权。配置文件中的 `registered_at` 仍只是合同字段，最终状态以数据库和 `status` read model 为准。

方法训练完成且 application receipt 已由 reviewer 接纳后，使用一次性 `freeze-method` 锁定版本，之后才允许揭盲 holdout：

```bash
.venv/bin/python scripts/judgment_training_program.py freeze-method JTP:turtle-historical-primary-v1 --method-version enterprise-judgment-method-v1 --frozen-at <ISO-8601> --db stock_analysis.db
```

训练计划与 feedback claim 使用同一生产数据库，但职责不同：训练计划决定通道、抽样和是否允许学习；feedback control 保存每条冻结 claim 的到期、采集、结算、诊断和应用事件。现有 `historical_backtest`、`judgment_feedback`、`judgment_learning` 和报告 handoff 保持唯一语义实现，不另建平行结算器。

## 7. 如何进入黄金报告

训练反馈到黄金报告的模块职责、三视图 handoff、公司判断与投资增强顺序，见[训练反馈到黄金报告的服务定位设计](TURTLE_GOLDEN_REPORT_SERVICE_DESIGN.md)。本节只规定历史结果和 learning 的权限边界。

历史训练不会把整篇旧报告或事后结论塞入新报告上下文。只有以下三类产物可进入受控生成：

1. 经 feedback、诊断、learning note、method review、跨公司 application receipt 和 cutoff replay 接纳的窄方法改变；
2. 满足跨公司、跨期、反例和独立审阅门的行业机制，按其可用时间进入行业知识快照。PIT 报告只读取 `available_at <= cutoff` 且 promotion receipt 能回读候选原始观察、selection freeze、settlement 和独立 review 的机制；当前库、后来补写的机制和自由 `OBS/DOC` 不得倒灌。
3. 与报告 cutoff 相容的 Industry History Universe 摘要和 Lifecycle patterns，只进入 `RESEARCH_AGENDA` 生成问题、退出路径和禁止替代；它们不能直接进入本公司 `JUDGMENT_SYNTHESIS` 或定量模型。

新报告的 `RESEARCH_AGENDA` 接收这些问题、证据门、禁止替代和待验证机制；`JUDGMENT_SYNTHESIS` 仍只来自本公司、同 cutoff 的正式判断；`INVESTMENT_ENRICHMENT` 只能在公司判断完成后追加估值、价格和回报。历史结局不得直接成为当前公司事实或中心路径。

系统效果通过以下行为变化观察：

- 更早识别行业交易点和责任单元；
- 更少把收入、销量、投产、正 OCF 或存活当作机制成立；
- 更早保留材料性 `UNKNOWN`；
- 正常利润、owner cash、永久损失、价值和回报由同一经营驱动传播；
- 独立留出中仍能提出正确的分叉问题或正确弃权。

## 8. 当前计划与退出门

第一版计划契约已定义以下职责；只有在生产数据库执行 `register` 后，才可称为已登记：

- R-62 鹏鼎汽车／服务器 PCB 扩产：`HISTORICAL_TRAINING` 预注册对象，但当前筛查仍为 `NO_PRIMARY / NOT_FROZEN`；必须先完成 PIT case、责任单元结果合同和独立准入审阅，不能直接当作选择学习样本；
- R-69 联影激光 backlog／扩产时点：当前为 `NO_PRIMARY / NOT_FROZEN` 的 evidence carrier；订单和建设期不足以冻结客户吸收、现金或资本回收的比较判断；
- R-61 沪硅少数股权收购：`HISTORICAL_HOLDOUT`，已预留 cutoff 冻结文件，方法冻结前保持 `WAITING_FOR_METHOD_FREEZE`；
- R-102 华宏鑫泰：完成真实选择结算，联合结果和基线均为 `NOT_DIAGNOSTIC`；已登记非方向性的持续披露身份测量边界，不形成方法或报告权限；
- R-103 银轮新能源热管理：当前仍封存，作为选择方法冻结后的公司轴替代留出；
- R-104 重庆啤酒网络裁减：已完成独立 pre-outcome review、独立结果提取和 post-outcome review；D3 为 `A_ONLY`、D4 为 `B_ONLY`、联合为 `MIXED`。它只生成“D3 改善不自动传导到正常 owner cash”的无权利边界，不能冻结选择方法或释放 R-103；
- R-56 晶科与 R-58 美的—小天鹅：`HISTORICAL_TEACHING`，结果已知或曾参与规则形成，只训练边界，不能产生正式 method learning；
- R-25、R-21、R-78：`HISTORICAL_TEACHING`；
- R-54：已登记为 `LIVE_SENTINEL`，当前 `DUE_FOR_RESULT_ACQUISITION`；它只服务部署校准，不阻断历史训练或边界方法冻结。
- 水泥 H1：新 static package 已通过 `STAGE0_FEASIBILITY_REVIEWABLE`；五家公司可作为 2018 universe/evidence-carrier seed，三家 pending 可进入 H2 screen，两家 scope/control break 只排除不匹配 comparator，不删除其行业史和教学价值。

下一阶段不以案例数量或最新披露为出口，而以分层对象、权限和留出评价为出口。行业史/教学线与正式选择线并行：

```text
并行 A：Industry Universe -> Lifecycle/Teaching Case -> research agenda 与边界资产
并行 B：真实、结果隔离且 `SELECTION_ADMITTED` 的新 episode
       -> PIT Comparative Freeze -> 方向性结算
       -> 不同公司 application -> selection method freeze
       -> R-61 独立留出 -> report-use release
```

选择链未完成不再阻断行业史、消失公司或教学训练；这些对象也不能替代选择链完成。真实前瞻哨兵可提前冻结以启动时间钟，但它的正式能力验收位于历史训练、历史留出和黄金报告接线成熟之后。

## 9. 能力声明边界

| 已完成状态 | 允许声明 |
|---|---|
| 历史训练完成 | 方法在历史 PIT 条件下形成了可审计改变 |
| 历史留出完成 | 冻结方法在指定未见公司/时期表现出有限泛化或明确失败 |
| 黄金报告接线完成 | 历史学习确实改变了报告研究议程和经营—财务传播 |
| 多个真实哨兵结算 | 获得有限的部署外部有效性证据 |

以上任何单层都不能独自证明投资优势、准确率、经验概率、管理层普遍能力或组合收益。
