# Turtle Judgment-First × Decision-Focused Enterprise Judgment 统一设计

> 状态：`RUNTIME_CONSTITUTION_IMPLEMENTED / PAIRED_RUNTIME_NO_MATERIAL_DIFFERENCE / PROSPECTIVE_FEEDBACK_MATERIAL_DELTA_COMPLETED / NARROW_TRANSFER_VALIDATED`
>
> 日期：2026-08-27（Asia/Shanghai）
>
> 下一动作：停止扩建 gate；在自然出现的后续公司 episode 中继续复验两条候选规则，不冻结方法
>
> 权限：不授予 Comparative、CJO、正式估值、BuyBand、报告发布或投资动作

## 1. 统一裁决

Turtle 只保留一个最高目标：

> **在证据、PIT、结果隔离和权限约束内，最大化企业判断与投资决策效用。**

两份现有设计不是竞争方案，而是同一个目标的不同执行层：

| 层级 | 正式对象 | 解决的问题 | 当前状态 |
| --- | --- | --- | --- |
| 运行时行为 | [Judgment-First Agent Constitution](TURTLE_JUDGMENT_FIRST_AGENT_CONSTITUTION.md)、`AGENTS.md`、`agent_loop.py` | Agent 在每次研究、综合、报告和审阅中必须怎样判断 | 已实现；R-62 paired 未证明提示块的增量效用 |
| 训练与评价 | [Decision-Focused Enterprise Judgment Training Architecture](TURTLE_DECISION_FOCUSED_ENTERPRISE_JUDGMENT_TRAINING_ARCHITECTURE.md) | episode 训练什么、怎样结算判断、何时算跨公司学习 | 两条规则已完成一次独立跨公司前瞻验证；方法尚未冻结 |
| 证据底座 | PIT、source、responsibility boundary、outcome custodian、lifecycle | 哪些事实、比较和归因可以进入判断 | 继续保留，不再作为训练产品 |

因此不新建训练 lane、不新增全局 gate，也不要求把两份详细文档压成一个巨大运行时提示词。运行时只注入紧凑宪法；完整训练 episode 才消费八项企业判断和反馈合同。

## 2. 一个目标，三种责任

### 2.1 证据底座负责“不能说什么”

以下仍是硬约束：

- cutoff 后材料不能进入 cutoff 前判断；
- 结果不能在判断冻结前暴露；
- 来源、公司、责任单元、合并范围、期间和单位必须真实；
- `MEASUREMENT_MISMATCH`、`EVIDENCE_INELIGIBLE`、`NO_PRIMARY` 和 `UNKNOWN` 限制依赖它们的主张；
- 退出、失败、并购、退市和生命周期变化不得因样本不方便而删除；
- Comparative 只为它所授权的局部因果主张服务。

通过这些约束以后，不因新增 receipt、validator、状态码或 UNKNOWN 获得训练信用。

### 2.2 运行时宪法负责“仍然必须说什么”

每个有综合责任的 Agent 必须返回：

1. 当前最合理的方向性或条件性判断；
2. 决定性事实与经济机制；
3. 最强竞争解释；
4. 权限内的投资含义；
5. 置信边界、材料性未知和翻转条件。

缺少因果权限，只限制因果语言；缺少精确字段，只限制该字段。它们不能把整家公司判断压缩成“无法冻结”。

### 2.3 训练架构负责“怎样证明判断变好了”

训练成功必须在后续未见公司或时期中表现为至少一项材料变化：

- 避免一个会改变投资结论的错误；
- 更早识别关键企业机制；
- 更合理地排序经营情景；
- 改变管理层经济信用；
- 改变 owner-cash 范围或永久损失处理；
- 改变估值方向、折扣或研究/进入处理；
- 用更低研究成本达到相同质量的判断。

更长文字、更多维度、更多 UNKNOWN、更多字段结算或更完整审计都不能单独证明学习。

## 3. 统一研究流程

现有 `DEEP_ENTERPRISE_RESEARCH` 流程保留，但各阶段重新解释为判断服务：

```text
FRAME
  投资者真正需要回答的材料问题是什么？

SCOPE
  哪个公司、责任单元、arena、cutoff 和期限决定该问题？

HYPOTHESES
  当前最佳解释和最强反方分别是什么？

PLAN / ACQUIRE
  哪一项新信息最可能改变判断或投资处理？

ADJUDICATE
  在现有证据下选择基准解释，局部保留未知。

FREEZE
  冻结判断、反方、情景、现金/风险/估值后果和翻转条件。

SETTLE
  custodian 结算原子结果，独立 reviewer 结算企业判断。

LEARN / APPLY
  只把实际改变处理的规则应用到不同公司。
```

当同一获取或测量阻断重复两次，下一步只能是：

- 具名交给更可能解决问题的角色或来源，并明确交付物及会改变的判断；或
- 对不确定性作保守范围处理，继续其余企业判断。

不得以无接收者的 `NEEDS_CURATOR`、重复搜索或新增全局 gate 延后判断。

## 4. 不同角色的输出边界

### 4.1 完整公司 episode / 全文报告综合

必须形成三项最材料的企业判断，并完整覆盖：机制、支持证据、最强反方、乐观/基准/悲观情景、管理层决策与执行、owner cash、永久损失、翻转条件和估值影响。

三项判断属于完整公司产品，不机械下放给每个窄任务。

### 4.2 定向研究 Agent

不拥有整家公司结论，但其局部返回不能只是缺口清单。至少说明：

- 本 finding 的局部经济含义；
- 最强替代解释；
- 最能区分两者的下一观察；
- 它可能改变哪个企业判断或投资处理。

### 4.3 独立综合 Agent

必须选择当前最佳解释并说明翻转条件。它可以因材料性事实或推理错误退回，不得因局部缺口要求全局停机。

### 4.4 PIT-only、custodian 与纯工程角色

继续保持信息与权限隔离：

- PIT-only 角色不得接触结果或进行投资综合；
- custodian 只结算合同字段；
- 纯工程任务说明其材料相关性即可，不需要伪造公司判断；
- 没有综合权限的角色不得因 Judgment-First 宪法越权输出正式估值或投资动作。

## 5. 不确定性与概率的统一语义

### 5.1 UNKNOWN 不是免费出口

材料性未知必须至少转成一项：

- 保守区间；
- 乐观/基准/悲观情景；
- 条件性结论；
- 管理层信用折扣；
- owner-cash、永久损失或估值后果；
- 能区分解释的下一证据；
- 明确的“不承保、不支付溢价或停止研究”处理。

### 5.2 不强迫编造概率

证据置信度与经营结果概率是不同对象。没有基准率、明确事件定义或校准基础时：

- 使用 `LOW / MEDIUM / HIGH`、相对排序或概率区间；
- 说明基准情景为什么优先；
- 不为满足形式要求制造合计 100% 的虚假精确数字。

只有可观察、定义匹配、事前冻结的预测才进入 proper scoring。

### 5.3 估值含义必答，数值权限不自动授予

完整企业判断至少要说明：

- 哪些盈利不能进入正常盈利；
- owner cash 应采用什么方向或范围；
- 哪项未知提高永久损失折扣；
- 这些变化使价值区间或最高可接受买价上调、下调还是保持。

只有既有 calculation/valuation contract 允许时才输出数值区间。Judgment-First 不绕过 CJO、估值、BuyBand 或投资权限。

## 6. 已完成的 paired runtime diagnosis

### 6.1 测试对象

使用现有 [R-62 鹏鼎控股汽车 PCB 扩产旧阻断案例](experiments/R-62_pengding_automotive_pcb_2023_screen/01_pre_outcome_admission_screen.md)。它具有真实 cutoff 前证据，也已经暴露典型失败：项目主体、投资和建设计划可见，既有车载板认证/量产入口可定位，但项目专属客户吸收、产品单位经济、现金桥和实际资本回收不足，旧处理停在 `NO_PRIMARY / NOT_FROZEN`。

本轮只验证 prompt behavior，不读取新 outcome、价格或回报，不把该对象重新认定为未见训练样本。

### 6.2 两个 arm

```text
Baseline
  = 当前整合代码与当前上下文，只移除 88bf30e 新增的
    Judgment-First prompt block

Enhanced
  = 同一代码与上下文，保留 88bf30e 注入的
    Judgment-First prompt block
```

Baseline 不运行整份旧分支，也不回退其他采集、研究或 Round 10 代码；否则无法把差异归因到提示词。测试可从 `88bf30e^` 读取三个原始 prompt section 形成一次性快照，但不得为此增加长期 feature flag、兼容层或新运行模式。

两个 arm 必须保持一致：

- 公司、cutoff 和 source packet；
- 可调用工具与路径；
- 模型及推理设置；
- call、token 与研究时间上限；
- 不提供对方输出、事后结果或价格；
- 各运行一次，不通过 repair loop 反复调到满意。

本轮不为 paired test 新建 schema 或控制平面。用一个冻结的自然语言运行说明、两个原始输出和一个独立盲审记录即可。

### 6.3 必须观察的处理差异

Enhanced 若有效，应在不虚构事实的情况下形成类似以下经济处理：

```text
汽车 PCB 是有现实客户/量产入口、但尚未被项目专属客户吸收、
单位经济和现金证据承保的增长选择权。

基准 owner cash 不计入该增长；这不等于项目价值为零或必然失败。
客户吸收、利用率、单位经济和现金转换是升级条件。
```

文字可以不同。关键是旧证据状态被局部保留，同时出现明确的基准处理、选择权情景和翻转条件。

### 6.4 独立盲审

reviewer 不知道哪个输出来自旧提示词，只回答：

1. 哪个输出更清楚地给出当前最佳判断；
2. 哪个输出具有更完整、但不过度声称因果的经济机制；
3. 哪个输出提出更强的竞争解释；
4. 哪个输出把未知转成更有用的 owner-cash、永久损失、估值方向或研究处理；
5. 哪个输出给出真正能翻转判断的观察；
6. 两者是否同样遵守证据、PIT 和权限边界。

不使用总分，也不以长度、语气自信、字段数或免责声明数量决定胜负。

### 6.5 接受与拒绝

只有同时满足以下条件才接受运行时修复：

- Enhanced 没有新增材料性事实错误、越界归因或虚假精度；
- 至少一个材料企业判断或投资处理比 Baseline 更清楚、更可反驳且更有用；
- 改善来自 Judgment-First 指令，而不是更多证据、更多工具或更长预算；
- reviewer 能指出具体 decision delta，而不只是“写得更好”。

以下结果必须拒绝：

- 只是把 `UNKNOWN` 改写成更自信的措辞；
- 把汽车/服务器混合项目全部归为汽车 PCB；
- 把认证、规划或在建工程当成客户吸收、盈利或现金兑现；
- 为了显得果断编造成功概率、owner cash 或数值价值；
- 新旧输出的投资处理实质相同；
- 改善来自额外证据或额外运行预算。

### 6.6 本轮能够和不能证明什么

通过只能标记：

```text
JUDGMENT_FIRST_RUNTIME_PAIRED_ACCEPTED
```

它证明相同证据预算下，运行时宪法改善了当前判断表达和投资处理。它不能标记：

- `REAL_FEEDBACK_TURN_COMPLETED`；
- `TRANSFER_CANDIDATE_CREATED`；
- `TRANSFER_VALIDATED`；
- 方法冻结；
- CJO、正式估值、BuyBand、报告发布或投资权限。

### 6.7 2026-08-27 实际结果

R-62 已按冻结合同完成两次主调用和一次独立盲审。Baseline 与 Enhanced 都把汽车/服务器 PCB 扩产处理为“已有产业入口、但客户吸收、单位经济和现金回收未获承保的资本密集型增长选择权”；两者都不把项目 IRR、成熟利润或增长溢价放入基准情景，并给出相同的升级证据。

Enhanced 更明确写出最强乐观反方、融资来源不改变资本成本和产能闲置的永久损失机制；Baseline 对“计划投资不等于已经支付”略严谨。独立结论为 `NO_MATERIAL_DIFFERENCE`，因此不得标记 `JUDGMENT_FIRST_RUNTIME_PAIRED_ACCEPTED`。完整工件位于 [R-62 paired runtime v1](experiments/R-62_pengding_automotive_pcb_2023_screen/judgment_first_paired_runtime_v1/04_COMPLETION_RECEIPT.md)。

这个结果只否定“新增提示块已经证明增量效用”。它不否定两臂都已达到判断优先的行为底线，也不应成为真实企业训练的新全局门槛。共同任务已经明确要求当前、可反驳、投资有用的判断，说明任务合同本身可能比重复宪法更接近有效干预。

## 7. Paired acceptance 之后的训练顺序

paired test 决定能否把增量效用归功于新增提示块，不决定真实企业训练是否可以继续。只要实际输出已经形成有边界的当前判断，且没有材料性越界，即可进入一条 outcome 未读的开发公司/cutoff：

1. 结果前冻结三项企业判断、最强反方和三种经营情景；
2. 冻结管理层信用、owner-cash、永久损失和估值方向；
3. 只选择最能区分解释的 1--3 个结果观察；
4. 独立 custodian 结算原子字段；
5. 独立 judgment reviewer 结算 `SUPPORTED / WEAKENED / REFUTED / UNRESOLVED`；
6. 只把实际改变处理的 learning delta 应用于不同公司；
7. 再用未见 outcome 评价是否改善判断。

如果连续三个未污染 episode 仍然只产生更多 UNKNOWN、更多边界检查或更多 research agenda，而没有企业判断、现金、永久损失、估值或研究行动变化，停止扩建训练基础设施，重新审视 Agent 能力、案例选择和输入上下文。

## 8. 当前完成状态

已完成：

- Judgment-First 规则进入 `AGENTS.md`；
- 全文报告、定向研究和独立综合活跃提示词已注入紧凑宪法；
- PIT-only 角色保持隔离；
- 决策导向 episode、UNKNOWN、反馈和 transfer 语义已经设计；
- Round 6--10 已作为奖励错位的真实诊断证据。
- CN:002394 × 2019-05-01 结果未读开发 episode 已完成 FY2019 独立结算；管理层执行信用、owner-cash 金额判断和下一 cutoff 研究问题发生材料性变化。
- CN:002042 × 2018-05-01 已在 FY2018 结果读取前冻结合理 baseline 与 enhanced 字段；独立 custodian 和 reviewer 确认，同定义产销存比较与建成后经济吸收链把资本配置从方向未决收窄为已有材料性负面证据，并改变永久损失机制、情景排序、估值折扣和研究动作。
- `LR:CN002394:ECONOMIC_ABSORPTION_AFTER_BUILD` 与 `LR:CN002394:TREND_REQUIRES_COMPARABLE_BASE` 获得一次有界 `TRANSFER_VALIDATED`；共同使用的 perimeter-first 只是一项测量修正，未被计作企业洞察。

尚未完成：

- 任何可归因于新增 prompt block 的 paired runtime acceptance；
- 任何方法冻结或投资权限。

因此当前最准确结论是：

> **目标函数和运行时行为已经纠偏；R-62 仍未证明新增提示块的独立增益，但 CN:002394 的真实反馈已在 CN:002042 的未读结果 episode 中产生材料性的跨公司判断改善。当前应停止扩建训练门槛，把“趋势主张冻结可比基期”和“建成后转查经济吸收”作为有界候选规则继续自然复验；一次迁移验证不等于方法冻结或投资授权。**
