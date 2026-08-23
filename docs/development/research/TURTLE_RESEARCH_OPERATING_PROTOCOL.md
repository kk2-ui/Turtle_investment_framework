# Turtle 研究操作流程

状态：`PRE_RESEARCH_READY / RESEARCH_FIRST`  
上位方法：[研究方法大纲](TURTLE_RESEARCH_METHOD_OUTLINE.md)  
用途：规定研究如何开始、推进、停止、复验和沉淀。它服务于研究员形成判断，不服务于“尽快完成报告”。

本流程是[判断力飞轮](TURTLE_JUDGMENT_FLYWHEEL.md)的运行手册：每一环的输出必须成为下一环的输入，而不是孤立的报告、案例卡或数据任务。

当前方法实验队列和格力的暂停边界见[方法研究项目登记簿](TURTLE_RESEARCH_PROGRAM_REGISTER.md)。

本流程在进入正式研究前的自审和修改记录见[研究前准备迭代日志](TURTLE_RESEARCH_PREPARATION_ITERATION_LOG.md)。

## 1. 工作边界

研究阶段的对象是问题、机制、证据边界、反例与学习；产出可以是不确定性变得更清楚。以下工作明确后置：

- 报告正文、章节完整度与发布状态；
- 估值、市场价格、预期回报与投资动作；
- 以报告篇数、案例数、agent 数量或资料页数衡量研究深度。

这些对象只在一项研究已形成稳定、可复读且可反驳的公司判断后，作为冻结或应用层进入。研究期不因暂时无法写报告而停摆。

## 1.1 研究员的最小闭环

一次研究只需完成下面六步；任何额外阅读都必须服务于其中一步：

```text
选择一个判断能力盲点
  → 写有退出条件的迭代卡
  → 读有边界的原始材料并分类观察
  → 让竞争机制解释同一组事实
  → 红队攻击口径、传导与近失效案例
  → 裁决方法、指定迁移复验或停止
```

若在第三步后无法让机制分叉，正确输出是 `INSUFFICIENT_TEST` 和一项资料请求；不继续扩写公司故事。若在第六步没有形成方法更新或明确停止，也不称作一次迭代。

### 1.2 研究准备的停止规则

准备阶段也可能成为另一种无限深挖。现有流程、模板和结果期执行链已经能承载某项研究时，默认状态改为 `L0_READY_TO_WAIT_FOR_REAL_FEEDBACK`，而不是继续抽象地“完善框架”。此后只有三类输入可以开启新的方法迭代：

1. 已冻结 signal 到期，需要执行原结果采集合同；
2. 一个新对象通过 cutoff 前的研究准入，暴露现有流程无法处理的材料性问题；
3. 已运行的真实候选或结算出现可定位的流程失效。

没有这三类输入，新增 schema、validator、模板、案例材料或同一公司的更长 chronology 都不是研究进展。它们应被拒绝或留作明确的后续问题；不得以准备工作代替判断反馈。

这里的停止规则只暂停**L0 方法架构的无触发扩张**，不是暂停判断训练本身。研究者仍可在不改动 L0 架构的前提下运行一个已符合现有准入门的 archive exercise：先隔离 outcome、使用既有的机制/反方/指标合同冻结，再由结果包结算，并把 learning note 约束到下一题。它必须标明 `HISTORICAL_SELF_REPLAY` 或 `ARCHIVED_EX_ANTE_EXTERNAL`，不得算作 Turtle 的实时命中；但“真实前瞻尚未到期”绝不能成为停止这种训练的理由。相反，重读更多没有结果合同的旧材料、或为了练习而新增平行 schema，仍是本节所禁止的伪进展。

### 1.3｜训练层：先练判断动作，再升级为正式 episode

正式 CJO/前瞻冻结要求完整的 PIT 包、来源合同与结算工件；它们是结算门，不是每一次练习的入口。日常 archive 训练先使用[机制判断微演练](../../../templates/research_mechanism_micro_drill.md)：

1. 先由独立 curator 或冻结的结构化抽取建立精确 locator 的事实包；研究者只读至多三份原件中的状态、行动和经营事实，先独立写 H-A/H-B 与一条分歧观察。HTML table/PDF 页面中混有的原因解释不因格式而成为事实；若关键量/价/成本数字与归因同处，交付仅含指标、数值、单位、期间和 locator 的 `FROZEN_METRIC_SLICE`，将归因句隔离到第二遍，不能因排除整段而用宽口径代理替代。`FROZEN_METRIC_SLICE` 还须预列精确允许指标标签，只返回匹配标签的数值；关键词黑名单不能单独证明无叙事泄漏；
2. 再读取原作者/管理层的解释，把它作为待检验主张，而不是默认答案；
3. 没有非嵌套观察、同口径结果合同或严格 outcome 隔离时，关闭为 `QUESTION_ONLY / UNDIFFERENTIATED`；结果合同还须在 cutoff 前锚定发布者、结果事件、窗口、日历/URL metadata 与标签，不能仅按预计 filing 日期猜附件；
4. 有完整合同才冻结并读结果，复盘必须写出“下一张不同中国对象卡的哪个字段改变”。

微演练不产生样本量、胜率、概率或公司结论；它也不绕过正式 episode 的准入。其价值是把“读材料”转为可被未来观察纠正的判断动作。中国对象构成主训练队列；海外对象只可充当已声明的边界或近失效角色，必须写出与中国对象不同的结构条件和会被影响的机制箭头。

## 2. 研究组合，而非单公司待办清单

研究计划以**方法实验组合**管理。每个实验只检验一种研究方法是否真能减少材料性错误，并必须准备跨对象复验。公司只是实验台，不能成为无限深挖的目的。

进入队列的先后顺序：

1. 能材料性改变经营、现金、资本配置或永久损失判断；
2. 能让两种竞争机制出现不同观察；
3. 能暴露测量边界、错误类比或事后偏见；
4. 在不同公司/时期有复验可能；
5. 当前可合法取得的材料足以完成一个有界实验。

只满足“资料很多”或“容易写成故事”的主题不进入主动研究队列。

同一公司默认只有一个 active ticket。创建新迭代卡前，研究者须先在卡的“同公司重入”段落
定位该公司已有 active/closed ticket；只有新对象确实进入未覆盖的 `机制域 × 当前状态 × 竞争叉`，
并能写出不同的 H-A/H-B、FJ、简单基线和同口径结果合同，才可开第二张卡。新年报、电话会、
更长 chronology、同一来源的更多转述或更多研究者意见只提高叙事细节，不构成新 ticket；此时停在
`EXPLORATION_ONLY`，转向空白机制格、近失效或边界复验。这个判断含经济语义，故由研究者在立项
时明确，不以公司名称或目录扫描做机械替代。

需要积累跨公司经验时，采用[公司经验积累协议](TURTLE_COMPANY_EXPERIENCE_ACCUMULATION_PROTOCOL.md)的显式三对象批次：一项填补状态格的 `FOCAL`、一项只翻转上游中介的 `NEAR_MISS`、一项只改变外部条件的 `BOUNDARY_REPLICATION`。三者未在结果前同时成立时，不开深研，不用同一公司的更多材料补足“样本”。

## 3. 研究对象的生命周期

```text
QUESTION
  → SCOPED_EXPERIMENT
  → EVIDENCE_AND_MECHANISM_LAB
  → RED_TEAM_REVIEW
  → METHOD_DECISION
  → REPLICATION_PENDING
  → RETAINED / MODIFIED / REJECTED
```

- `QUESTION`：发现一个可能误导判断的盲点；还没有开始收集材料。
- `SCOPED_EXPERIMENT`：已写清方法假设、材料边界、反证与退出条件。
- `EVIDENCE_AND_MECHANISM_LAB`：读取和整理原始材料，但不得提前写中心结论。
- `RED_TEAM_REVIEW`：独立尝试用另一机制、另一测量边界或近失效案例推翻发现。
- `METHOD_DECISION`：只对方法作 `RETAIN / MODIFY / REJECT / INSUFFICIENT_TEST` 裁决。
- `REPLICATION_PENDING`：当前公司只作为一次发现；等待在不同对象复验。
- `RETAINED / MODIFIED / REJECTED`：沉淀为可迁移流程，或明确不再使用。

一家公司即使持续出现新资料，也不能绕过 `REPLICATION_PENDING` 直接把一次发现升级为通用方法。

## 4. 一轮研究的标准流程

### 0｜立项：先写迭代卡

在读新材料前填写[研究迭代卡模板](../../../templates/research_iteration_card.md)。必须有：

- 一个明确的方法盲点与方法假设；
- 本轮要训练的判断能力（问题界定、机制辨别、测量辨别、校正或迁移）；
- 一个有界的公司/时期/机制问题；
- 预计会避免的经济错误；
- 最强对照或反例；
- 不再继续深挖该对象的退出条件；
- 下一轮的迁移复验要求。

没有迭代卡的阅读只能算资料浏览，不能被记录为一次方法迭代。

### 1｜建立问题与基线

为实验写一条决定性问题，以及当前不使用该方法时会作出的最强旧解释。此处不选主结论，只明确“什么会被这个方法改变”。

例如：会计科目变化究竟是经济成本变化，还是列报边界变化？若不拆开，哪项渠道、现金或盈利判断会被污染？会计边界必须先归为 `PRESENTATION_ONLY`、`RECOGNITION_OR_MEASUREMENT` 或 `MIXED_OR_UNRESOLVED`：只有第一类的已量化映射可局部调整；第二类禁止跨旧/新口径同比，第三类保留未知。

基线必须同样有材料、问题和输出边界。例如“只按报表同比外推”“只采用单一主叙事”或“按行业名称寻找一个熟悉案例”，而不能用一个故意很弱的对照衬托新方法。

### 2｜按来源接纳，不按观点摘抄

每一份材料先填[来源观察卡](../../../templates/research_source_note.md)，强制分开：原文事实、测量边界、作者/管理层解释、可能机制、未回答的问题。

所有观察只可暂列为 `FACT`、`SENSOR`、`HYPOTHESIS` 或 `UNKNOWN`。重复转述共享同一来源谱系时合并为一次取证任务；不按出现次数增加信念。

每项观察还须标出证据上限：`CONTEXT_ONLY` 只给背景，`MECHANISM_DISCOVERY` 只生成问题，`COMPARATIVE_CANDIDATE` 等待口径/版本补齐，只有 `SETTLEMENT_ELIGIBLE` 才能成为冻结判断的结果来源。`UNKNOWN` 必须说明究竟是缺观测、口径错配、共同机制、未到期还是 PIT 不可得；不同原因必须导向不同的下一步，而不是继续补叙事。

未知原因与行动固定对应：`MISSING_OBSERVATION` 请求缺失观察；`MEASUREMENT_MISMATCH` 先统一交易点/单位/期间/分类，做不到则不比较；`MECHANISM_NONDIAGNOSTIC` 更换箭头或撤销信号；`NOT_YET_DUE` 等待而不提前解释；`PIT_BLOCKED` 从历史验证排除或寻找当时版本。

多人或多 agent 并行时，每张来源观察卡都必须登记 `lineage_id` 和独立性依据。相同 company filing、provider release/query、访谈样本、事件链或其转述折叠为一个 observation；不同文字、页码、机构或 agent 不增加样本数。多角色只为还原来源、构造反方和发现遗漏服务，不能投票、平均或提高任何机制概率；主研究者按来源谱系与诊断性作判断。

来源观察还要区分 `STATE / ACTION / OUTCOME / CAUSAL_ATTRIBUTION / FORECAST`：行动完成只结算行动，管理层或作者归因只生成竞争机制和资料请求；动作后出现结果不是因果证明。只有在竞争机制上具 `A_SPECIFIC` 或 `B_SPECIFIC` 诊断性的 outcome sequence 才能支持或削弱一条箭头。

### 2.1｜行动—经济判断准入门

对资本配置、产品、组织或渠道动作，先把行动命题与经济命题拆开。行动来源只可结算授权、条件、交割、付款、控制权或范围变化；它们对经济机制默认 `NONDIAGNOSTIC`。

只有在**行动前**已经写出以下六项，才可以冻结经济 FJ：

1. 对同一当前事实的 H-A/H-B；
2. 主/反机制各自的经营传导；
3. 同口径经营指标与比较基准；
4. 增量应归属于哪一业务/客户/项目的边界；
5. 早期或终局观察窗口；
6. 允许的、能在结果期取得的来源。

少一项即登记 `NO_ELIGIBLE_ECONOMIC_FJ`。可以继续结算动作，但对象输出保持 `NO_COMPANY_CONCLUSION`；不得由行动完成、并表、日后利润、新闻、减值或证券回报补写当时的机制。R-02 是这个门的首个真实训练验证，适用边界仍需迁移复验。

### 3｜构造竞争机制实验

使用[机制竞争实验模板](../../../templates/research_mechanism_lab.md)，令至少两种解释竞争同一组当前事实。每条机制须给出：

```text
已知状态 → 管理动作/激励 → 客户、渠道或产品传导 → 量价/费用 → 现金或资本后果
```

未知箭头必须显式留空。单一故事、风险清单或乐观/悲观措辞不构成机制竞争。

在固定 H-A/H-B 前，先在机制实验卡完成一轮“假设空间筛选”：所有能解释同一共同事实、并会材料性改变正常盈利、现金转换、资本配置或永久损失边界的候选，都必须留下 `PAIR_PRIMARY / PAIR_RIVAL / MERGE / DEFER_NO_PRIMARY / EXCLUDE / OUT_OF_SCOPE` 的 cutoff 前处置。material 不是形容词：研究者必须写明“若为真，哪一条本轮机制箭头、FJ、来源任务或选择资格会不同”。它不是第三份平行预测账本：`MERGE` 要求同一因果顺序，`EXCLUDE` 要求当时事实直接矛盾；`OUT_OF_SCOPE` 只适用于不解释共同事实或不位移本轮问题的事项，并须生成独立问题/资料任务，不能冒充已被证伪。一个仍可信、会造成上述位移、却没有可分叉观察的候选必须使中心路径降为 `NO_PRIMARY`，而非静默删除。H-A/H-B 因而是最有信息量的可结算 pair，不是对假设空间穷尽性的声称。结果期的 `NEITHER` 只会触发回读这份冻结筛选或提出新机制，绝不允许把新名称伪称为当时已考虑的反方。

每个候选信号还要预先列出 `A_ONLY / B_ONLY / MIXED / NEITHER` 四个结果区域；只在数值上略有差异、但结果逻辑嵌套的两条预测不是竞争机制。

若行业、政策、宏观或竞争结构的变化会让 H-A/H-B 的因果顺序、指标含义或可比较性失效，须在机制实验和前瞻冻结附件写成一个具体的适用条件：cutoff 时状态、一手来源、受约束的 pair 箭头/FJ、可观察 break、允许结果来源、窗口和 `CONTINUE_AS_IN_SCOPE / CLOSE_AND_REFREEZE_NEW_EPISODE` 动作。一般周期、需求、价格、竞争或利率波动仍是机制本身要解释的共同状态，不是 break。没有预注册 condition 的“环境变了”只能开始下一研究问题，不能改写原 verdict；有合格 break 时仍保留 raw observation，但不得把它作为原环境下的主路径选择、迁移或 L3–L5 证据，必须在新 cutoff 重建 episode。learning review 只能把这类已经冻结且触发的事件记为 `STATE_REPRESENTATION: ENVIRONMENT_REGIME_BREAK`，不新增事后免责分数。

前瞻表达默认使用方向、范围或 `NO_FORECAST`。CJO 的 `NO_PROBABILITY` 模式可冻结竞争机制、双边 FJ、信号与合同，但不能填写概率桶、权重、概率 ID 或“最高概率”中心路径；`NO_PRIMARY` 因而不设中心路径。只有选择准入已成立时，才可用定性 `selection_basis` 记录主路径。概率只有在迭代卡能列出同定义独立 episode/外部频率、事件定义和校准计划时才允许；缺任一项就保持 `NO_PROBABILITY`，不得把主观信心填成数字。机制对与主路径选择必须分开：没有 cutoff 前的方向性区分证据或合格外部经验时，实验只能标 `MECHANISM_SIGNAL_PROBE / NO_PRIMARY`，其结果只能验证信号，不得计入“选对公司路径”。

### 4｜红队：优先攻击测量和传导

红队按以下顺序反驳，而不是润色相反意见：

1. 观测的交易点、单位、期间、分类或样本是否不同？
2. 替代机制能否同样解释该事实？
3. 是否有结构相似但结果相反的近失效案例？
4. 当前发现是否仍能改变盈利、现金、资本配置或永久损失边界？

无法通过前三项的材料降为背景或 `UNKNOWN`；不以“多数资料同意”替代红队。

若使用历史书籍或公司案例，先填写[结构化类比与近失效卡](../../../templates/research_analogy_transfer_note.md)。结果已知的案例只可提出条件、反例和资料请求；它不得支持目标公司的中心机制，除非目标公司本身另有可结算的机制观察。

### 5｜方法裁决与更新

完成实验后，写[学习复盘模板](../../../templates/research_learning_review.md)。裁决对象是**方法**，不是公司好坏：

- `RETAIN`：新步骤明确防止了一个材料性误读，且未产生同等严重的新误读；
- `MODIFY`：发现有效，但适用条件、顺序或边界要收窄；
- `REJECT`：没有产生新的判别力，或增加的复杂度超过其信息价值；
- `INSUFFICIENT_TEST`：材料不足以辨别方法是否有效，不能把“看起来合理”升级为保留。

每次裁决必须修改方法大纲、模板、待办顺序或明确的禁用项之一；只写一段复盘文字不算更新。对前瞻实验，这个“下一次动作”必须在冻结附件中预先承诺：`A_ONLY / B_ONLY / MIXED / MEASUREMENT_MISMATCH` 各自会如何改变或停用信号。结果到来后只能执行或明确拒绝该承诺，不能临时发明一条看似合理的学习结论。

同时必须写清：这次方法是否让研究者作出一项此前不能作出的机制/测量区分，还是只增加了资料和叙事。后者不得被称为判断力提升。

学习复盘还必须单列**对象研究状态**。方法可被 `RETAIN`，而当前公司仍应是 `UNDIFFERENTIATED / ACQUISITION_REQUIRED`；两者不得互相推导。没有 `SETTLEMENT_ELIGIBLE` 的 A-only/B-only 信号时，最强且唯一诚实的公司输出是 `NO_COMPANY_CONCLUSION`。

即使一个早期信号结算为 `SUPPORTS_PRIMARY` 或 `SUPPORTS_RIVAL`，对象也只进入 `EARLY_SIGNAL_SETTLED / TERMINAL_PENDING`：它只更新对应机制箭头，仍不得生成三年终局、价值、价格或投资结论。只有全部预注册的终局经营观察到期后，才可单独复核公司判断。

判断产生的前瞻观察如何冻结、结算并与投资回报分轨，遵循[判断力验证与回测协议](TURTLE_JUDGMENT_VALIDATION_PROTOCOL.md)。

### 5.1｜把单条学习记录变成真正的下一轮方法改变

每条已结算的 forward judgment 都应生成一张 append-only learning note，至少连接到：`experiment_id`、`company_cluster_id`、失败位置、根因类别和下一次研究改变。没有这两个身份，后续无法知道某项“经验”究竟只属于一个公司，还是值得跨对象复验。

按期对这些 note 生成方法复盘议程，而不是求一个总分：

- 只有一个公司簇时，状态为 `SINGLE_COMPANY_ACTION_ONLY`。可执行针对该实验的下次改变，但不得声称方法一般有效；
- 出现多个公司簇时，状态为 `MULTI_COMPANY_METHOD_REVIEW_REQUIRED`。研究者逐项查看相同失败位置下的实验、边界和候选改变，决定保留、收窄、废弃或另做反例；
- 同一公司不同 case 仍是相关材料，不能因 note 数增加被当作独立样本；
- 这个议程只暴露重复的任务失败与待执行改变，禁止计算准确率、概率、胜率、价格或投资回报分数。

任何汇总后的方法决定仍须回写到方法大纲、模板、禁用项或下一个有界实验，并写明反例与迁移复验；汇总本身不产生方法结论。

第一份真实 `MULTI_COMPANY_METHOD_REVIEW_REQUIRED` 出现后，下一项不同公司的迭代卡必须使用“上一轮学习的应用”表：每条相关 note 只能被 `APPLIED / NARROWED / INAPPLICABLE` 之一处置，并定位到本轮冻结前实际改变的 source gate、状态向量、H-A/H-B 分叉、信号或 metric contract。正式选择 episode 还必须生成 append-only `LAPP:` application receipt：它把 `LNOTE → method review decision → B 公司 freeze ID → 实际 JSON pointer/new value → independent reviewer` 串成可验证链。validator 必须在目标冻结里复读新值，且 reviewer identity 不得等于制作者；若没有真实字段变化，该对象不能称为该方法的 replication。没有真实跨公司 review 时，正确状态是 `NOT_YET_APPLICABLE`，不为提前闭环而新增自动评分或空字段 validator。

### 5.2｜在结果出现前冻结 L5 的比较 cohort

`L5` 不是把已经结算的 cards 导入表格后再挑一个“合理”的统计口径。只有当多个不同公司簇都已形成 `SELECTION_ADMITTED`、且各自 terminal 经营 FJ 的结果窗口尚未打开时，才可以建立一个有限 cohort 的 [`judgment-method-evaluation-plan.v1`](../../../schemas/judgment_method_evaluation_plan.schema.json)。它绑定已冻结的 `case_selection_register`，并对 register 的**每一条** screen entry 写入 `INCLUDED_SELECTION_EPISODE / EXCLUDED_NO_PRIMARY / EXCLUDED_NONCOMPARABLE` 之一；这保留了筛过但没有资格形成比较预测的对象，而不把它们伪装为预测失败。

每个 `INCLUDED_SELECTION_EPISODE` 只能登记一个、来自 frozen rival pair 的 `TERMINAL_OPERATING` FJ，且每个公司只能计一次。`company_cluster_id` 必须等于其 `selection_entry_id` 在 frozen register 内的 `cluster.company_id`；自定义新标签不能把同一公司多期材料伪装为独立簇。入选 CJO 还必须在冻结时把相同 register ID/fingerprint、entry、company 和 cluster 写入 `selection_admission.selection_register_binding`；`freeze_method_evaluation_plan` 会逐字段复读该 receipt。普通 selection episode 可无此 receipt，但无 receipt 的 case 不可事后放进 L5。计划冻结 `case / freeze / claim / FJ / selection entry / cluster / outcome_not_before`，并在结果窗口打开前锁住全体入选单元、最小独立簇数和固定的非价格规则：`COMPANY_JUDGMENT_ONLY / NON_PRICE_OPERATING_ONLY / NO_PROBABILITY / BINARY_FROZEN_PREDICATE_LOSS / RETAIN_ALL_PLANNED_UNITS_AND_NONDIAGNOSTIC_OUTCOMES`。

到期后，聚合器只接收这些已冻结单元的 feedback，保留 `SUPPORTS_SELECTED`、`SUPPORTS_RIVAL`、`NOT_DIAGNOSTIC`、`BASELINE_NONDISCRIMATING` 与 `NOT_EVALUATED` 的完整计数，以及被冻结谓词相对简单基线的 `JUDGMENT_BETTER / BASELINE_BETTER / NO_DIRECTIONAL_INCREMENT_IDENTIFIED` 计数。这些方向计数只条件于 `INCLUDED_SELECTION_EPISODE`，所以同一输出必须并列给出完整 screen 的 `INCLUDED_SELECTION_EPISODE / EXCLUDED_NO_PRIMARY / EXCLUDED_NONCOMPARABLE` 计数。`NO_PRIMARY` 是当时的弃权/证据不足，不是路径选择胜利或失败；它还必须有同 register entry 的 frozen `NO_PRIMARY` case/freeze receipt，不能由结果期在 plan 中手写。没有该 receipt 的对象只能是 `NONCOMPARABLE`。三者不能合成一个方法分数。它不输出比例、胜率、概率、总分、价格、回报或“方法已优于基线”的结论。遗漏一个入选单元、重复公司簇、用 early signal 代替 terminal，或在窗口打开后才冻结，均不能进入该 cohort。

### 6｜迁移复验或停止

当前实验结束后，默认选择不同公司、行业、时期或机制做复验。仅在出现**新材料能直接改变原方法裁决**时，才回到同一公司。

停止当前对象研究的触发条件：

- 新材料不再改变方法、机制、测量边界或未来观察；
- 已知资料缺口无法通过同类公开阅读缩小；
- 当前方法已产生一次发现，下一价值在于寻找其断裂条件；
- 问题不再可能影响经济判断。

### 6.1｜有界研究的前瞻冻结附件

完整 `COMPANY_JUDGMENT_ONLY` 研究需要公司层面的证据、驱动与结算工件；但一个方法实验不应为了满足全公司的现金、资本配置或报告字段而制造无关判断。对于只训练一条经营机制箭头的真实前瞻实验，使用[研究前瞻冻结附件](../../../templates/research_forward_freeze.md)，并同时满足：

1. 截止日前 source package 已物化，且每一份冻结附件实际引用的 source ID 均须经 PIT runner 显式读取；attestation 必须列出这些 `ALLOW` 读取、`read_count` 与拒绝数。只有“包可读”但没有读取审计，不得冻结。结果期 source 的取得契约也须预先写明；
2. 冻结共同事实、H-A/H-B、同口径指标、A-only/B-only 阈值、观察窗口、结果期计量连续性合同与结算规则；该合同逐项指定未来官方指标/文件、允许转换、禁止代理和口径变化时的停止动作。若声称选择主路径，还必须写出每条选择证据的方向性和独立谱系，以及一个预测不同的简单基线，否则降为 `MECHANISM_SIGNAL_PROBE / NO_PRIMARY`；
3. 明确它只更新哪一条机制箭头，明确哪些公司结论仍不允许输出；
4. 每次研究会话先以带时区的 ISO-8601 `as_of`（如 `2026-08-21T18:00:00+08:00`）将所有 `00_candidate_condition_contract.json` 同步到唯一生产数据库，再运行 candidate-condition inbox；否则新登记的待批准候选会被错误地当作“不存在”。candidate item 到期时只枚举其预注册的官方条件来源，未达正式冻结门前不得读取正文、创建 outcome package 或调用结果结算。随后运行一次 `outcome_acquisition due-inbox <contracts-root>`，而不是逐份人工调用 `execution-status`：它列出全体冻结 contract 的 `DUE_FOR_ACQUISITION / OVERDUE_FOR_ACQUISITION` claim，主 CJO 运行入口也会在 Agent loop 前只读执行该检查。窗口未开则保持 `NOT_YET_DUE`；开窗即转为 `DUE_FOR_ACQUISITION`，关窗仍未采集则标记 `OVERDUE_FOR_ACQUISITION`。后两者必须先完成 bounded result-source inventory、selected raw/reader package、read audit 和逐字 extraction；每个结果事件以唯一 `settlement_id` 写入 `outcome_events/<settlement_id>/`，因此 S2 不得覆盖 S1。`07_settlement.md` 只显示这些事件 extraction，不能手填 value/source 或跳过更早合格披露，不改写冻结附件。任何不属于已到期 claim 的 post-cutoff 结果（包括先出现但预先标为非诊断的脉冲）均不得打开、下载或摘要；它不能改变当前动作，却会污染后续解释。若已读，登记 `OUTCOME_EXPOSURE_BREACH`，该实验只能保留为管线训练，不能进入判断力 feedback、learning note 或迁移复验；
5. 方法复盘仍须写入 `04_learning_review.md`，并指定跨对象复验。

这个附件不是平行估值/预测系统：它只保存研究卡原本已经要求、但需要跨时间结算的最小内容。任何要形成完整公司判断、现金判断、估值或行动的研究，仍必须走相应的公司研究工件与独立投资层。

## 4.1 历史回放的信息防火墙

历史 PIT 回放的唯一价值是让研究者在结果未知的条件下练习；若在分析期已读到结果，再精密的回测也只是事后解释。每个可用于判断验证的实验应按时间隔离：

```text
cutoff 前的 source package
          ↓（只允许这一侧进入研究）
问题、基线、竞争机制、早期/终局观察和方法裁决前版本
          ↓（冻结研究卡）
cutoff 后的 outcome package
          ↓
逐项结算与 learning note
```

- 样本选择不能以已知好/坏结果为依据；若结果已不可避免地被研究者知道，则标为 `OUTCOME_SELECTED_TRAINING_ONLY`，只能测试模板可用性或生成反例，不能测试判断准确性。
- 同一个 episode 的结果不得在红队阶段提前可见；红队攻击当时的事实、机制和测量边界。
- 结果期只允许新增 observation 与误差归因，不能修改旧问题、机制、阈值、区间或信心。
- 无法实现信息隔离时，保持 `REPLICATION_PENDING` 或 `INSUFFICIENT_TEST`，不将其记为成功回测。

## 5. 研究会话的节奏

每次研究会话只做一种工作，不混写：

| 会话类型 | 输入 | 输出 | 禁止事项 |
|---|---|---|---|
| 问题设计 | 旧发现、未知与反例 | 迭代卡、资料请求 | 先写结论或搜支持材料 |
| 原始材料阅读 | 有界来源包 | 来源观察卡 | 边读边把作者观点写成事实 |
| 机制实验 | 已整理观察 | 对立机制及分歧观察 | 以情绪化乐观/悲观代替机制 |
| 红队 | 当前机制图 | 反例、边界与撤销项 | 为主叙事补辩护 |
| 方法复盘 | 已到期或已审阅实验 | 方法裁决、迁移任务 | 用结果改写原问题 |

“阅读—摘抄—直接写报告”不属于许可的研究会话路径。

## 6. 角色分离

同一研究员可按顺序承担这些角色；若多人协作，角色之间不应在原始阅读阶段互相灌输结论：

| 角色 | 责任 | 不负责 |
|---|---|---|
| 主研究者 | 界定问题、判断材料性、作方法裁决 | 用投票替代判断 |
| 来源研究者 | 还原原始文字、版本、交易点和缺口 | 从来源数量推出结论 |
| 机制研究者 | 写传导、替代机制和可观察顺序 | 以叙事填补未知 |
| 红队/复验者 | 寻找口径错配、近失效案例和反证 | 在结果期重写原判断 |

角色独立降低遗漏与确认偏误，但不创造独立样本，也不自动提高置信度。

### 6.1｜结构化类比的 source/target 交接

类比使用 `STRUCTURE_FIRST` 时，普通“来源研究者 / 机制研究者 / 红队”角色还不够：source 的故事若在 target 因果骨架形成前传入，后续表格再完整也不能测试结构优先。此时采用[类比卡的最小交接收据](../../../templates/research_analogy_transfer_note.md#最小交接收据仅当要把-structure_first-当作干预测试时填写)：

1. `target mapper` 只接收 target 的 cutoff 前 source IDs 与问题，先冻结 Pass A；
2. `source mapper` 只接收 source 的 cutoff 前原件与 source 结果可见性，独立冻结 Pass B；
3. `integration lead` 只能在两份草图完成后接收它们，负责因果角色对齐、排除表面相似、近失效和一个新增的断裂观察；不得加新事实或改写草图；
4. `reviewer` 只核对输入清单、locator 和顺序，写 `CONTEXT_SEPARATED / CONTEXT_SEPARATION_NOT_ASSURED / CONTEXT_CONTAMINATED`，不评价公司、结果、价格或回报。

同一研究员可以顺序承担角色；同一模型/会话如果已包含另一侧详细材料、结果或既有类比结论，必须保守标为 `CONTEXT_SEPARATION_NOT_ASSURED`。这不是对模型记忆的绝对隔离承诺，而是让实际交接边界、失效原因和不能声称的东西可复查。多 agent 只能帮助分离阅读与发现遗漏；它们不得投票、平均或提高任何机制概率。

## 7. 研究档案的最小结构

每项活跃实验有一个目录或等价的文档集合：

```text
experiment/
  00_iteration_card.md
  01_source_notes/
  02_mechanism_lab.md
  03_red_team.md
  04_learning_review.md
  05_replication_plan.md
```

这是研究笔记的组织约定，不是新数据库、评分系统或发布门。探索性材料可留在 `01_source_notes`，未经裁决的内容不得升级到公司结论或投资输入。

## 8. 研究准备阶段的验收

进入任何新公司或行业研究前，必须已经具备：

1. 本操作流程和四种空白模板；
2. 一个按方法实验而非公司名称排序的研究组合；
3. 每轮的进入、停止和迁移复验规则；
4. `FACT / SENSOR / HYPOTHESIS / UNKNOWN` 的共同语言；
5. 报告、估值和市场价格明确后置的边界。

不要求事先拥有完整行业数据、结论、估值或报告。数据缺失会进入迭代设计：它决定实验能否完成、应如何保守使用传感器，而不是迫使研究者把资料缺口伪装成公司判断。
