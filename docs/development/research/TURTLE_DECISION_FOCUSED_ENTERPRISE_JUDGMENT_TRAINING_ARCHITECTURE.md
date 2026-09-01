# Turtle 决策导向企业判断训练架构

> 状态：`INTEGRATED_DESIGN_COMPANION / RUNTIME_CONSTITUTION_IMPLEMENTED / TRAINING_ACCEPTANCE_PENDING`
>
> 日期：2026-08-27（Asia/Shanghai）
>
> 适用对象：`EnterpriseJudgmentEpisode`、真实历史反馈、跨公司学习应用与投资者读出
>
> 核心裁决：保留 PIT、结果隔离、责任边界、独立 custodian、生命周期与退出公司；停止把合规完整度当作训练效用。训练的首要产出改为在证据不完美时形成当前最合理、可反驳、可更新并能传播到 owner cash、永久损失和估值的企业判断。

> 统一入口：[Turtle Judgment-First × Decision-Focused Enterprise Judgment Integrated Design](TURTLE_JUDGMENT_FIRST_DECISION_FOCUSED_INTEGRATED_DESIGN.md)。本文负责 episode、反馈与 transfer 语义；[Judgment-First Agent Constitution](TURTLE_JUDGMENT_FIRST_AGENT_CONSTITUTION.md)负责 Agent 行为和活跃运行时提示词。

本文提出训练系统上层目标与验收逻辑的修订方案。它建立在现有[训练顶层架构](TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md)、[Enterprise Judgment V2 真实训练 Goal](TURTLE_ENTERPRISE_JUDGMENT_V2_REAL_TRAINING_GOAL.md)以及 Round 6--10 的真实运行结果之上。

本文不是现行权限授予文件，不追溯改变既有 episode、settlement、method review 或 completion receipt 的状态，不修改 J2/J3/J4 adapter，也不自动授予 Comparative、CJO、正式估值、BuyBand、报告或投资权限。它描述下一版顶层架构应当优化什么，以及如何用新的真实 episode 证明改造有效。

---

## 1. 执行摘要

当前系统已经较好地解决了三类问题：

1. 不使用 cutoff 后信息；
2. 不把不匹配的字段、主体或期间误标为观察；
3. 能把获取、结算、审阅和权限留在可追溯责任链中。

但现有训练奖励主要仍落在这些控制结果上。Agent 最安全的策略因而是缩小主张、增加门槛、扩大 `UNKNOWN`，并证明自己没有越界。这种策略可以提高审计安全，却不必形成更好的企业理解或投资决策。

Round 6--10 显示，这不是抽象风险，而是已经发生的系统行为：

- Round 6 证明更细的提问结构能在相同证据成本下发现关键未知并避免把审批进展写成发行人已经控制、合并的经营能力；但 owner cash、永久损失和企业质量仍不可诊断。
- Round 8 完成了真实多维反馈，却诚实裁决 `NO_MATERIAL_METHOD_ADVANTAGE_PROVED`；八维更多证明研究覆盖，没有证明比合理 Baseline 产生更好的投资处理。
- Round 9 得到真实企业结果，但方法比较因冻结解析器错误而失效；它证明控制层能拒绝不合法的学习宣称。
- Round 10 在三家公司中完成两个机械结算、保留一个局部 measurement mismatch，最终独立裁决 `NO_MATERIAL_UTILITY`：更多维度、更多解释、更多 UNKNOWN 和更多覆盖均不能单独证明投资效用。

因此系统目前更准确的身份是：

> **高纪律的企业研究与反馈控制系统，而不是已经有效的企业判断训练系统。**

下一版不应继续扩大控制层，而应重写训练目标：

> **在 PIT、来源真实性和经济责任边界约束下，最大化企业判断的区分力、可反驳性、可校准性，以及对资本决策的边际价值。**

实现上采用两层非对称结构：

```text
底层完整性约束：决定哪些事实和归因不能使用
                    ↓
上层判断义务：决定在剩余不确定性下仍然必须形成什么判断
                    ↓
投资传播：竞争地位 → 单位经济 → owner cash → 永久损失 → 估值/最高买价
                    ↓
前瞻反馈：冻结 → 揭示 → 判断结算 → 方法更新 → 不同公司应用
```

底层约束通过以后，增加 validator、状态字段或 UNKNOWN 不获得训练奖励。训练成功必须表现为判断、情景、管理层信用、现金范围、永久损失、估值或研究行动中的材料性改善。

---

## 2. 真实运行已经证明和没有证明的部分

### 2.1 Round 6：证明问题分解有用，没有证明企业判断有效

Round 6 的 Baseline 和 Enhanced 使用相同 FY2015 source packet。Enhanced 把一个笼统的收购进展问题拆成正式进展、发行人控制、产品参与、合并范围和客户响应。结果显示正式进展为 `YES`，但发行人控制和合并为 `NO`，产品参与和客户响应仍是 `UNKNOWN`。

这项变化具有真实研究价值：它阻止研究者把审批和服务支持提前写成发行人拥有的产能、盈利和整合成果。独立评审因此给出 `ENHANCED_IMPROVED_KEY_UNKNOWN`。但是评审同时记录：经营现金上升和现金资本开支下降不能证明 owner-cash access，单一年报也不能判断永久损失；该轮受 repository history 污染，只具有 `DEVELOPMENT_TRANSFER_UTILITY_ONLY` 身份。

依据：

- [Round 6 顶层记录](TURTLE_ENTERPRISE_JUDGMENT_V2_REAL_TRAINING_GOAL.md#14-2026-08-27-round-6-cross-company-transfer-utility)
- [Round 6 独立 paired utility review](industry_learning_blocks/CN_CEMENT_2014_2018/43_round6_independent_paired_utility_review.json)
- [Round 6 completion receipt](industry_learning_blocks/CN_CEMENT_2014_2018/44_round6_completion_receipt.json)

正确解释是：Round 6 证明了 **question-structure utility**，没有证明 enterprise judgment、method transfer 或 investment utility。

### 2.2 Round 8：真实结算能够局部推进，但八维没有形成可归因优势

Round 8 对韵达股份结算 15 个结果单元，得到 `6 OBSERVED / 6 MEASUREMENT_MISMATCH / 3 UNKNOWN`。它成功区分了公司合并现金、加盟网络经济、客户忠诚、单位经济和管理行动时钟，且没有让局部错配拖停整个 episode。

但 Baseline 本身已经保留了价格竞争、平台流量、客户结构、总部现金与加盟商现金等关键反方；两种方法也没有在结果前分别冻结 resolution rule。因此不能事后把谨慎解释归功于 Enhanced。最终状态是：

```text
REAL_FEEDBACK_COMPLETED
NO_MATERIAL_METHOD_ADVANTAGE_PROVED
ARCHITECTURE_REVISION_REQUIRED
```

依据：[Round 8 投资者读出](industry_learning_blocks/CN_FRANCHISE_EXPRESS_2018_2019/13_investor_readout.md)。

Round 8 的教训不是“八维无用”，而是：

> 研究覆盖更完整，不等于判断更好；发现更多缺口，不等于改变了投资处理。

### 2.3 Round 9：控制系统能拒绝错误学习，但企业学习没有发生

Round 9 对四川长虹取得了真实企业结果：集团收入上升，核心白电收入同比下降，毛利率略升，经营现金较 FY2018 明显下降，工业园全面投产，同时合并组合发生变化。

这些结果本可以用于挑战“集团增长代表核心产品增强”“建设完成代表客户和资本回报兑现”等判断。然而事前解析器把已实施行动错误输出为 tuple，结果揭示后工作树一度修正该错误，破坏方法比较的盲测边界。系统最终把方法比较裁决为 `MODEL_ERROR`。

依据：[Round 9 投资者读出](industry_learning_blocks/CN_APPLIANCE_CHANGHONG_2018_2019_ROUND9/20_investor_readout.md)。

这一轮证明审计纪律有效，却没有让 Agent 获得可迁移的企业判断。它是必要的失败拒绝，不是训练成效。

### 2.4 Round 10：机械结算扩大，投资效用仍为零

Round 10 使用新的方法 epoch，在华帝、老板电器和浙江美大上进行批次测试。华帝和浙江美大的发行人合并收入、经营现金和总资产完成机械结算；老板电器因年报版本族不能唯一解析而局部保持 `MEASUREMENT_MISMATCH`。

Enhanced 要求先补 owner-cash 和责任边界证据，但 Baseline 已经禁止把发行人收入或现金直接升级为客户响应、行动效果、单位经济或普通股 owner cash。因此独立外部评审没有接受任何 treatment delta，结论为 `NO_MATERIAL_UTILITY`。

依据：

- [Round 10 外部方法评审](industry_learning_blocks/CN_APPLIANCE_ROUND10_V2_POSTOUTCOME/02_external_method_review.json)
- [Round 10 投资者读出](industry_learning_blocks/CN_APPLIANCE_ROUND10_V2_POSTOUTCOME/04_investor_readout.md)

### 2.5 总结性诊断

Round 6--10 共同证明：

- PIT、局部降级、结果隔离、边界和独立审阅正在工作；
- 系统已经能识别“不能从这些证据推出什么”；
- 系统尚未稳定形成“在这些限制下当前最应该相信什么”；
- 系统尚未证明方法变化能改变另一家公司结果揭示前的材料性投资判断；
- 测试数、结算字段数、UNKNOWN 数量和审阅完整度都不能替代训练效用。

---

## 3. 根因：四类不确定性被压成了同一个停止状态

当前系统倾向把下列四类问题都转成 `UNKNOWN` 或前置 gate：

| 问题类型 | 示例 | 正确处理 | 是否应全局阻断 |
|---|---|---|---|
| 证据完整性 | cutoff 后材料、虚构引用、结果泄漏 | 拒绝事实或污染 episode | 是，若污染全局对象 |
| 测量不确定性 | 单位不一致、责任边界不同、期间不匹配 | 局部 mismatch，禁止机械比较 | 否 |
| 企业模型不确定性 | 价格、产品、行业、管理层谁主导结果 | 竞争解释、情景权重、区分信号 | 否 |
| 投资决策不确定性 | owner cash、永久损失、估值无法单点确定 | 区间、折扣、买价上限和研究行动 | 否 |

只有第一类属于不可妥协的真实性问题。第二类限制具体比较。第三和第四类正是企业判断训练的对象。

旧逻辑经常执行：

```text
证据不足
  → 判断 UNKNOWN
  → 投资传播 NOT_AUTHORIZED
  → episode 只留下 research agenda
```

新逻辑必须执行：

```text
证据不足
  → 区分事实未知、机制未知和决策未知
  → 选择当前最合理的基准解释
  → 扩大情景范围或降低管理层信用
  → 对 owner cash、永久损失和估值施加明确折扣
  → 只获取可能改变该处理的新证据
```

核心原则是：

> **事实可以是 `UNKNOWN`；投资者在当前信息下怎样处理这个 UNKNOWN，不能是空白。**

---

## 4. 研究依据与对 Turtle 的含义

### 4.1 决策导向学习：不能把局部正确当作最终效用

Elmachtoub 与 Grigas 的 Smart Predict-then-Optimize 以及 Wilder、Dilkina、Tambe 的 decision-focused learning 都指出：普通预测准确度可能与下游决策目标错位；模型应根据预测进入最终决策后的损失训练，而不是只优化中间指标。

对 Turtle 的含义是：字段结算正确率、边界违规率和审阅通过率只能评价底层可靠性，不能成为训练主目标。上层训练必须观察研究方法是否改变了企业判断和投资处理。

### 4.2 Calibration 与 sharpness：诚实还不够，还要有区分力

Gneiting、Balabdaoui 与 Raftery提出，概率预测应在保持 calibration 的前提下追求 sharpness。一个永远给极宽范围的系统可能很少犯错，但没有信息价值。

对 Turtle 的含义是：

- PIT、边界与 proper scoring 负责 calibration；
- 当前最合理判断、有依据的概率或范围、以及情景分化负责 sharpness；没有校准基础时使用定性置信与相对可能性，不为显得果断而制造百分比；
- `UNKNOWN` 不能成为零成本弃权；
- 系统应奖励有证据约束的更窄范围，而不是无条件奖励更保守的措辞。

### 4.3 Selective prediction：弃权必须同时评价 coverage

Selective classification 把拒绝回答明确建模为 risk-coverage trade-off。只压低错误率而不约束覆盖率，会诱导系统拒绝处理困难样本。

对 Turtle 的含义不是禁止 UNKNOWN，而是要求每个材料性 UNKNOWN 都承担决策处理：它降低哪个情景权重、扩大哪个现金范围、增加哪条永久损失路径、压低多少估值或触发什么研究行动。

### 4.4 信息价值：不是每个缺失字段都值得补

Howard 的 Information Value Theory 把信息价值定义在其改善决策的能力上。信息本身不是目标。

对 Turtle 的含义是：下一研究问题不得按“哪个字段为空”排序，而应按“哪个新事实最可能改变情景排序、owner-cash 范围、永久损失、估值上限或研究停止决定”排序。

### 4.5 Outcome bias：结果好坏不能替代当时判断质量

Baron 与 Hershey 的实验表明，人们会因为事后结果不同而系统性改变对同一决策过程的评价。

对 Turtle 的含义是：

- 事前推理质量与事后结果必须分开评价；
- 好结果不自动证明管理层决策好或 Agent 判断正确；
- 坏结果也不自动证明当时判断不合理；
- 只能用冻结的概率、机制、区分信号和结果映射规则进行结算。

### 4.6 Prequential evaluation：真正的训练必须顺序发生

Dawid 的 prequential 思路强调先对未来可观察量作预测，再按时间顺序揭示和更新。Round 6--10 已经具备这条基础设施的一部分，但结算对象主要仍是字段和方法边界。

下一版必须把顺序评价扩展到企业判断本身：先冻结当前最佳解释、情景权重和投资传播，再揭示下一时期，最后评价哪些判断被支持、削弱或推翻。

### 4.7 Reward hacking：当前防御性写作是目标函数的理性结果

Amodei 等人把 reward hacking 描述为系统通过字面满足代理目标而偏离设计者真实意图。Turtle 当前的代理目标是低越界、低误标和可审计；Agent 通过减少主张和增加门槛可以持续提高这些指标。

因此，要求 Agent “大胆一点”不能解决问题。必须改变验收函数，并取消通过增加控制层获得的正向训练信用。

---

## 5. 新的顶层目标函数

### 5.1 目标陈述

Turtle 企业判断训练的首要目标改为：

> **在 cutoff 时点可获得且责任边界正确的证据下，形成当前最合理的企业经营解释；显式表达不确定性、最强反方与可推翻事实；把判断传播到长期 owner cash、永久损失和估值；并通过顺序结果与跨公司应用减少未来投资决策遗憾。**

简写为：

```text
maximize:
  judgment sharpness
  + causal discrimination
  + investor decision utility
  + prospective learning

subject to:
  PIT integrity
  + source truthfulness
  + responsibility-boundary integrity
  + outcome isolation
  + lifecycle completeness
```

这里不引入一个可被继续博弈的总分。系统采用先约束、后比较的非对称验收：

1. 违反底层真实性约束时拒绝；
2. 通过以后，在相同证据与成本下比较哪种方法产生更有区分力、更可反驳、更能改变投资处理的判断。

### 5.2 不再给予训练信用的事项

下列事项仍可以是必要工程工作，但本身不再构成训练成效：

- 新增 schema、validator、receipt 或状态码；
- 测试数增加；
- 结算更多字段；
- 保留更多 UNKNOWN；
- 写出更长的风险清单；
- 证明没有授予 CJO、估值或投资权限；
- 对合理 Baseline 已经避免的错误再次声明 Enhanced 避免了错误；
- 只改变 research agenda，却没有改变问题优先级或投资处理。

### 5.3 什么才获得训练信用

方法变化必须在结果揭示前实际改变至少一项：

- 三项核心企业判断的内容或排序；
- 乐观、基准、悲观情景的相对可能性、有依据的概率或范围；
- 管理层决策、执行或适应信用；
- 正常盈利或 owner-cash 范围；
- 永久损失路径及其权重；
- 估值区间或最高可接受买价；
- `继续研究 / 暂停研究 / 排除 / 等待指定证据` 的研究行动；
- 下一项信息获取的优先级，并且该优先级具有更高预期决策价值。

只发现一个更精确的 UNKNOWN，只有在它进一步改变上述至少一项时，才获得材料性效用信用。

---

## 6. 上层架构：证据底座与判断主线分离

### 6.1 证据底座继续存在，但不再主导训练叙事

以下边界完整保留：

- point-in-time cutoff；
- outcome firewall 与独立 custodian；
- source identity、可回读引用和禁止虚构；
- 同一公司、issuer、责任单元、competitive arena 和 perimeter；
- lifecycle、退出、并购、退市与失败公司；
- `MEASUREMENT_MISMATCH`、`EVIDENCE_INELIGIBLE` 和 `UNKNOWN` 的局部传播；
- Comparative 的 target-trial time zero、行动、对照、结果和删失纪律。

这些约束的作用是防止错误事实进入判断，不负责替 Agent 完成判断。

新增全局硬门只允许满足以下条件：

1. 失败路径来自项目真实支持的用法；
2. 已经发生，或有明确材料证据表明可能改变企业结论、永久损失、估值或投资动作；
3. 局部降级无法充分隔离；
4. 修复不能用更简单的事实、范围或审阅规则完成。

否则不得为了理论完整性继续扩大控制层。

### 6.2 判断主线成为 episode 的必交产品

`EnterpriseJudgmentEpisode` 继续作为训练基本单位，但其完成定义从“重建对象存在”升级为“完整企业判断存在”：

```text
EnterpriseJudgmentEpisode
  = company × cutoff
  × industry/company state
  × management alternatives and decisions
  × execution/customer/competition mechanisms
  × scenario distribution
  × owner-cash/permanent-loss consequences
  × valuation consequence
  × falsifiers and next evidence
```

E0--E4 不再表示一条必须逐级通关的主管线，而表示当前 episode 中不同主张的证据能力：

- E0/E1 足以形成企业状态和暂定判断；
- E2 用于挑战一条机制；
- E3 Comparative 只加强局部因果识别；
- E4 评价跨公司迁移和决策效用。

E2、E3、E4 的缺失不得阻断 E1 判断综合。E1 的判断也不得冒充 E3 因果证明。

### 6.3 投资传播成为必需层，而不是最终奖励层

当前流程往往在 owner cash、永久损失或估值之前停止。新架构要求每项材料判断都完成方向性传播：

```text
企业状态/管理行动
  → 客户选择与竞争反应
  → 价格、数量、产品组合和成本
  → 利润率、营运资本与再投资
  → owner cash
  → 永久损失路径
  → 正常盈利、估值区间与最高买价
```

证据不足可以扩大范围或采用保守处理，不能删除传播。

---

## 7. 每个真实 episode 的八项强制输出

### 7.1 当前最重要的三项企业判断

必须恰好选择三项最材料判断，防止用大量次要事实稀释责任。每项判断必须满足：若其方向改变，至少会改变正常盈利、owner cash、永久损失、估值或研究行动中的一项。

每项判断采用以下最小结构：

```text
当前最佳判断：
判断期限：
主观概率/区间（有校准基础时）或定性置信：
经济材料性：
```

禁止把“收入上升”“年报披露项目投产”之类事实直接当作企业判断。

### 7.2 因果机制

每项判断必须写出从初始条件到经济结果的可检查链条：

```text
公司状态/约束
  → 管理选择或 no-action
  → 执行
  → 客户/竞争反应
  → 单位经济
  → 现金/资本结果
```

若某一环节未知，保留该环节的未知和替代路径，不得用公司总收入或总现金跨越机制空洞。

### 7.3 支持证据与最强反证

每项判断只保留能够区分解释的主要证据，同时写出最强竞争解释。最强反方不得是容易驳倒的稻草人，也不得只是通用风险清单。

至少回答：

- 在主解释为真时，什么事实更可能出现；
- 在最强反方为真时，什么事实更可能出现；
- 当前哪个解释更合理，为什么；
- 哪一项观察最能区分两者。

### 7.4 乐观、基准、悲观三种经营情景

三种情景必须处于相同期限，并明确当前相对可能性。只有具备可解释基准率、可观察结果定义或足够校准基础时，才冻结合计为 100% 的概率或概率区间；否则使用有顺序的定性置信，并说明为何基准情景优先。禁止用虚假精度掩盖证据不足。

每种情景至少传播：

- 收入的价格、数量与组合来源；
- 单位利润或利润率；
- 营运资本；
- 维持性与增长性资本投入；
- owner cash；
- 永久损失路径；
- 正常盈利和估值影响。

情景不是三组任意敏感性。基准情景必须说明为什么当前比另外两种更可能。

### 7.5 管理层决策与执行能力评价

不使用一个笼统管理层分数。必须分别评价：

1. 决策质量：是否针对正确经营矛盾；
2. 执行证据：是否真正实施，而不是只公告或规划；
3. 客户与竞争反馈：市场是否验证；
4. 适应能力：外部变化后是否调整；
5. 资本纪律：是否改善长期每股 owner cash，而非只扩大规模。

各项事实可以未知，但 episode 必须决定基准情景给予管理层多少经济信用：`NONE / PARTIAL / SUBSTANTIAL`，并说明改变信用所需的证据。

### 7.6 对长期 owner cash 和永久损失的影响

必须区分：

- 集团经营现金；
- 维持性资本支出后的企业自由现金；
- 受债务、NCI、受限现金、子公司和再投资约束后的普通股 owner cash；
- 一次性营运资本释放；
- 通过低回报扩张形成的报表改善。

永久损失必须描述具体不可逆机制，如持续低回报再投资、控制权和索取权恶化、债务再融资、客户网络破坏、技术替代或资本配置失控，不得用一般波动替代。

### 7.7 推翻判断的新事实

每项核心判断至少冻结一个可观察的翻转条件，包括：

- 观察窗口；
- 责任边界；
- 指标或定性事件；
- 主解释与反方下的预期差异；
- 触发后应怎样调整情景、管理层信用或估值。

“需要更多资料”不是翻转条件。

### 7.8 对估值区间和最高可接受买价的方向性影响

未来 episode 必须产出不越过当前任务权限的 `ValuationConsequence`，至少说明：

- 哪部分盈利可以进入正常盈利，哪部分应剔除；
- owner-cash 转化采用什么范围；
- 再投资、竞争衰减和永久损失怎样改变资本化或折现要求；
- 乐观、基准、悲观情景怎样改变价值区间；
- 关键 UNKNOWN 使最高可接受买价相对证据完整情形上调、下调或保持，以及原因。

`ValuationConsequence` 是企业判断训练的一部分，不等于正式估值、BuyBand 或投资授权。方向、折扣机制和需要的估值输入必须表达；数值价值区间或最高买价只有在既有 calculation/valuation 权限允许时才可生成。当前市场价格可以继续隔离，企业经济判断不得由价格反向选择。

如果现行权限尚不允许数值区间，最低也必须冻结方向、折扣机制和未来数值化所需输入。是否需要独立的 training-only 数值权限，只能在 paired test 证明方向性传播不足后另行裁决；本文不预设新权限或新 gate。

---

## 8. UNKNOWN 的新语义：允许事实未知，不允许决策逃逸

### 8.1 材料性 UNKNOWN 的五项义务

每个材料性 UNKNOWN 必须同时记录：

1. **经济暴露**：它影响客户、单位经济、现金、永久损失还是估值；
2. **当前默认处理**：基准情景按什么保守解释处理；
3. **范围后果**：它使哪个区间扩大、哪个情景相对可能性下降，或在有校准基础时使哪个概率下降；
4. **区分证据**：什么新事实最可能改变处理；
5. **停止规则**：若公开证据不可得或不会改变决策，何时停止继续获取。

缺少这五项时，UNKNOWN 只是弃权，不是判断。

### 8.2 UNKNOWN 不应受到机械惩罚

新架构不以 UNKNOWN 数量越少越好。错误填满事实会制造过度自信。

真正受到负面评价的是：

- 明明可以作范围判断却完全弃权；
- UNKNOWN 没有传播到现金、风险或价格；
- 对不影响决策的 UNKNOWN 无限研究；
- 把 UNKNOWN 当成否定证据；
- 为避免出现 UNKNOWN 而跨越责任边界或使用事后结果。

### 8.3 无法区分时仍须形成决策判断

如果主解释与反方确实无法区分，企业事实可以保持未决，但 episode 仍须说明：

- 两种解释各自权重；
- 基准情景采用哪一项经济处理；
- 为什么该不确定性要求更低管理层信用、更宽 owner-cash 区间或更低最高买价；
- 在什么条件下应暂停研究或直接排除该公司。

---

## 9. 研究计划改为信息价值排序

### 9.1 决定性问题优先于字段完整

每个 proposed acquisition 必须先回答：

> 如果得到这个结果，是否可能改变三项核心判断之一、情景排序、管理层信用、owner-cash、永久损失、估值上限或研究行动？

若答案是否定的，就不应仅为了填字段而获取。

### 9.2 最小可执行信息价值判断

无需构建复杂 EVSI 数值模型。每项候选研究动作只需进行以下实质裁决：

```text
可能结果 A 会怎样改变投资处理？
可能结果 B 会怎样改变投资处理？
若两者都不改变处理，停止获取。
若会改变，哪项证据最便宜、最直接、责任边界最匹配？
```

这是一项研究者判断，不再新增评分表。

### 9.3 Research agenda 的完成标准

高质量 research agenda 不是列出更多缺失字段，而是：

- 删除不会改变决策的问题；
- 把最能区分主解释和反方的问题排在第一；
- 明确可能结果对应的判断更新；
- 明确何时已有信息足够作出保守判断并停止研究。

---

## 10. 结果反馈：从 cell settlement 升级到 judgment settlement

### 10.1 原子字段结算继续由独立 custodian 执行

custodian 继续只读取合同允许的 outcome window 和字段，不接收投资论点、情景权重、估值或作者期待。它只返回：

- `OBSERVED`；
- `UNKNOWN`；
- `MEASUREMENT_MISMATCH`；
- `EVIDENCE_INELIGIBLE`；
- 以及合同允许的原始值和方向。

### 10.2 独立 judgment adjudication

字段结算后，由独立判断审阅者按事前冻结的映射规则，对三项企业判断分别给出：

- `SUPPORTED`：结果更符合主解释；
- `WEAKENED`：反方的相对解释力上升；
- `REFUTED`：冻结的关键预测失败并触发翻转条件；
- `UNRESOLVED`：结果不能区分解释。

`SUPPORTED` 不等于行动产生因果效果，除非对应机制达到所需识别层级。`UNRESOLVED` 不阻止其他判断结算。

### 10.3 概率结算

对结果期可观察、定义匹配且事前冻结了概率的离散或方向性预测使用 proper scoring rule。评分只评价冻结概率与真实结果，不评价叙事长度；只有定性置信的判断不伪装成可评分预测。

定性长期判断尚未到期时，不强行评分；只结算到期的领先指标和机制单元。

### 10.4 分开评价过程、结果与更新

每轮反馈分别回答：

1. **事前过程质量**：当时是否使用正确证据并考虑最强反方；
2. **预测质量**：冻结概率和范围是否与结果一致；
3. **因果解释质量**：新增证据是否真正区分主解释与反方；
4. **更新质量**：Agent 是否按证据强度改变判断，既不过度更新也不拒绝更新；
5. **投资处理变化**：owner cash、永久损失、估值或研究行动是否改变。

这样可以避免把好运气奖励为高质量判断，也避免把坏运气惩罚为错误过程。

---

## 11. 学习必须改变可观察的研究政策

### 11.1 什么叫真正的 learning delta

每轮反馈只允许沉淀少量、可复述、带适用边界的 `JudgmentPolicyDelta`：

```text
旧处理：
失败或低效原因：
新处理：
适用企业状态：
它改变哪些判断/情景/现金/风险/估值字段：
什么反例会使本规则失效：
```

如果新处理只增加一个检查，却没有改变任何判断或投资后果，应标记为 `MEASUREMENT_METHOD_CORRECTION`，不得冒充 enterprise learning。

### 11.2 Baseline 必须是真正可用的简单方法

未来 Baseline 不得被设计成会犯明显错误的稻草人。它应代表一个合理、简单、未使用待检验规则的研究方法。

Baseline 与 Enhanced 必须在结果前分别冻结：

- 三项核心判断；
- 情景、相对可能性，以及有校准基础时的概率；
- 管理层信用；
- owner-cash、永久损失和估值后果；
- outcome resolution rule。

如果两者在这些字段上没有差异，本轮从一开始就不具备验证材料性方法效用的能力，不应等到结果揭示后才发现。

### 11.3 同一证据成本的 paired review

优先采用相同 cutoff、相同 source budget、相同研究时间预算的 Baseline/Enhanced 比较。独立 reviewer 只回答：

> Enhanced 是否在结果前形成了一个 Baseline 没有的材料性投资处理，并且结果说明该变化更合理？

有效变化包括：

- 避免方向性错误；
- 更合理地排序情景；
- 更准确地分配管理层信用；
- 缩小或正确扩大 owner-cash/估值范围；
- 更早识别永久损失路径；
- 用更少证据达到同样判断；
- 停止一个低价值研究方向并转向高信息价值问题。

下列变化单独不计效用：更多解释、更多维度、更多 UNKNOWN、更多字段覆盖、更多控制工件。

---

## 12. 重新解释现有成功状态

为了避免再建一套平行状态机，保留现有四个高层状态名称，但修订未来 episode 的实质门槛。既有工件不追溯升级或降级。

### 12.1 `REAL_SAMPLE_CREATED`

未来只有同时满足以下条件才可创建：

- 真实公司与真实 cutoff；
- 完成企业状态和管理选择重建；
- 冻结三项材料判断；
- 冻结机制、最强反方和三种经营情景；
- 明确管理层经济信用；
- 完成 owner-cash、永久损失和 valuation consequence；
- 冻结翻转条件和高信息价值 research agenda。

只有 source packet、reconstruction 或字段合同，不再足以构成真实判断样本。

### 12.2 `REAL_FEEDBACK_TURN_COMPLETED`

必须至少有一项到期企业判断被 `SUPPORTED / WEAKENED / REFUTED`，或有足够的 `UNRESOLVED` 结果触发明确的保守投资处理变化；同时形成下一 cutoff 的判断或研究政策变化。

只有机械 cell settlement，没有 judgment settlement，不足以完成这一状态。

### 12.3 `TRANSFER_CANDIDATE_CREATED`

必须在不同公司、结果揭示前，把已审 learning delta 应用于新的 episode，并材料性改变至少一项判断、情景、管理层信用、owner-cash、永久损失、估值或研究行动。

边界检查被复制到另一家公司但没有改变投资处理，只能是 method application receipt，不能成为 transfer candidate。

### 12.4 `TRANSFER_VALIDATED`

必须在真正未污染的公司轴或时间轴上前瞻验证，并由独立 reviewer 证明相对合理 Baseline 改善了判断或投资决策效用。

单家公司、开发期 memory-mitigated 比较、更多 UNKNOWN、更多审计覆盖或一次好运结果都不足以授予该状态。

---

## 13. 验收逻辑：技术正确但没有判断，也应退回

### 13.1 底层硬失败

以下仍然直接退回：

- cutoff 后证据进入事前判断；
- 来源虚构、错引或无法回读；
- 结果在冻结前泄漏；
- 责任主体、合并范围或单位错配被当成同口径事实；
- custodian 与预测/判断作者不独立；
- 生命周期或退出公司被删除，导致幸存者偏差；
- 事后重写冻结判断或 resolution rule。

### 13.2 判断产品硬失败

即使所有技术检查通过，出现以下任何材料问题也必须退回：

- 没有三项材料企业判断；
- 只罗列事实，没有当前最佳解释；
- 只有主解释，没有最强反方；
- 三种情景只是敏感性表，没有相对可能性和经济机制；
- 管理层评价没有区分决策、执行、客户反馈与资本纪律；
- owner cash 被集团 OCF 替代；
- 永久损失只写一般风险；
- UNKNOWN 没有默认处理和估值后果；
- 没有明确什么事实会推翻判断；
- 没有 valuation consequence 或最高买价方向；
- research agenda 不能说明新信息将怎样改变决策。

这些是产品缺陷，不得用测试数、schema PASS 或权限保守来补偿。

### 13.3 独立 reviewer 的核心问题

reviewer 不使用总分表，只回答五个材料问题：

1. 这是当前证据下最合理的解释，还是仅仅最安全的措辞？
2. 最强反方是否足以挑战中心判断？
3. 不确定性是否真实传播到现金、永久损失和估值？
4. 什么结果会使研究者真正改变看法？
5. 与合理 Baseline 相比，它是否会使投资者在结果揭示前采取不同且更合理的研究或资本处理？

---

## 14. 最小迁移方案：不重写控制层

### 14.1 立即冻结的工程范围

在新的真实样本证明判断效用以前：

- 不新增全局 evidence admission level；
- 不新增 J2/J3/J4 adapter；
- 不扩大 Comparative；
- 不为 UNKNOWN 再建一套平行状态机；
- 不追溯改写 Round 6--10；
- 不以 full-suite 测试数量作为进度；
- 不把正式 CJO、报告、BuyBand 或交易权限提前混入训练。

### 14.2 只新增一个人读优先的 Judgment Snapshot

最小实现只需要一个 episode-level `Judgment Snapshot`，先以 Markdown 或简单结构化对象表达第 7 节八项输出。它消费现有 reconstruction、mechanism threads、source refs 和 outcome contracts，不复制事实库。

Snapshot 必须让投资者在三分钟内回答：

- 这家公司当前最重要的三个判断是什么；
- 哪个判断最容易错；
- 错了会损失多少长期现金或价值；
- 什么证据最值得下一步获取；
- 当前应给出怎样的最高买价折扣。

先用两个真实 episode 证明这一对象有用，再决定是否值得 schema 化。禁止先为所有未来可能字段建设完整控制平面。

### 14.3 第一轮：Judgment-First 运行时 paired acceptance

第一轮不再泛化为重写 Round 10。使用 R-62 鹏鼎汽车 PCB 旧阻断案例，按[统一设计](TURTLE_JUDGMENT_FIRST_DECISION_FOCUSED_INTEGRATED_DESIGN.md)冻结一次同 cutoff、同 evidence budget 的旧提示词与新提示词 paired run。它只检验活跃运行时是否从“不能冻结”改善为诚实、有边界且具投资含义的当前判断。

该对象已参与规则形成，且本轮不揭示新 outcome，因此只能授予 runtime prompt acceptance。它不计 prospective training 成绩，不授 `REAL_FEEDBACK_TURN_COMPLETED`、transfer candidate 或任何投资权限。

### 14.4 第二轮：新的未污染公司/cutoff

选择一个结果仍密封、但 E1 证据足以形成完整判断的公司/cutoff。结果前必须完成：

1. 三项核心企业判断；
2. 三种情景及相对可能性，在有校准基础时再给概率；
3. 管理层信用；
4. owner-cash 与永久损失范围；
5. 权限内的 valuation consequence（至少方向与折扣机制）；
6. 最强反方和翻转条件；
7. Baseline/Enhanced 各自 resolution rule；
8. 最高信息价值的 1--3 项 outcome contract。

结果揭示后，先结算字段，再结算判断，最后评价投资处理变化。

### 14.5 第三轮：不同公司前瞻应用

只把第二轮真正产生材料性判断变化的 `JudgmentPolicyDelta` 应用于不同公司。必须在结果前显示该规则具体改变了哪个判断、相对可能性或概率、现金范围、损失路径、估值或研究行动。

若没有变化，诚实结论应是“规则在该公司不具材料性”，而不是新增更多字段寻找胜利。

### 14.6 停止规则

完成三个真正未污染 episode 后，如果新架构仍只能产生：

- 更多 UNKNOWN；
- 更多边界检查；
- 更多研究问题；
- 没有 owner-cash、永久损失或估值变化；
- 没有相对 Baseline 的处理差异；

则应停止继续扩建训练基础设施，重新审视案例选择、Agent 能力、输入上下文或训练方式。不得再用新 schema 延后产品失败的裁决。

---

## 15. 下一真实 episode 的最小验收示例

以下示例说明“证据不足时仍作判断”的语义，不代表任何真实公司结论。

### 核心判断 1

```text
当前最佳判断：收入恢复主要由行业价格改善驱动，企业自身份额优势尚未证明。
相对可能性：基准解释最高，企业份额增强次之，需求重新恶化最低；若存在可解释基准率，再冻结概率范围。
机制：供给约束 → 行业价格 → 收入/毛利；公司行动不是必要条件。
最强反方：渠道和产品升级已经带来结构性份额提升。
翻转事实：同区域、同产品、同期间的销量/价格/份额联合数据持续优于同行。
投资传播：基准情景不把本轮利润全部计入正常盈利，最高买价低于“结构性改善”情形。
```

### 核心判断 2

```text
当前最佳判断：管理层行动已实施，但客户兑现和单位经济改善仍未证明。
管理层信用：决策 PARTIAL，执行 PARTIAL，客户反馈 NONE。
默认处理：不把扩产、收购或渠道投入产生的预期收入计入正常 owner cash。
翻转事实：责任边界一致的客户留存、量价、毛利和资本投入回收同时改善。
投资传播：增长资本按较低回报处理，提高永久损失折扣。
```

### 核心判断 3

```text
当前最佳判断：经营现金改善含有营运资本释放，不能全额视为可持续 owner cash。
最强反方：回款和库存效率形成了结构性现金转换优势。
翻转事实：跨周期现金转换改善，同时未依赖应付扩张、库存压降或资本开支推迟。
投资传播：基准 owner-cash 采用多年范围下半部，并降低最高可接受买价。
```

这个 episode 即使有多个事实 UNKNOWN，仍然完成了当前判断、替代解释、管理层信用、现金和价格处理。未来结果可以明确改变它，而不是只能确认字段是否存在。

---

## 16. 架构成功的最终判据

下一版架构成功，不以文档、测试或 episode 数量定义，而以以下可观察行为定义：

1. Agent 面对不完整证据时能够明确说出当前最合理的企业解释，而不是只列限制；
2. Agent 能把最强反方写到足以推翻自己，而不是用风险清单装饰中心判断；
3. UNKNOWN 会机械或明确地扩大现金/价值范围、降低管理层信用或改变研究行动；
4. 结果揭示后，Agent 能区分好运、企业能力、管理行动和外部行业作用；
5. 学习在另一家公司结果揭示前改变了材料性判断，而不只是改变了提问格式；
6. 相对合理 Baseline，方法提高判断区分力或降低投资决策遗憾；
7. 证据纪律继续工作，但研究报告的中心重新回到企业、管理层、现金与价格。

最重要的架构原则是：

> **证据纪律决定我们不能说什么；企业判断训练决定在剩余不确定性下，我们仍然必须说什么、为什么，以及应当付什么价格。**

---

## 17. 研究来源

1. Adam N. Elmachtoub and Paul Grigas, [Smart “Predict, then Optimize”](https://doi.org/10.1287/mnsc.2020.3922), *Management Science*, 2022.
2. Bryan Wilder, Bistra Dilkina, and Milind Tambe, [Melding the Data-Decisions Pipeline: Decision-Focused Learning for Combinatorial Optimization](https://doi.org/10.1609/aaai.v33i01.33011658), AAAI, 2019.
3. Tilmann Gneiting and Adrian E. Raftery, [Strictly Proper Scoring Rules, Prediction, and Estimation](https://doi.org/10.1198/016214506000001437), *JASA*, 2007.
4. Tilmann Gneiting, Fadoua Balabdaoui, and Adrian E. Raftery, [Probabilistic Forecasts, Calibration and Sharpness](https://doi.org/10.1111/j.1467-9868.2007.00587.x), *JRSS B*, 2007.
5. Ran El-Yaniv and Yair Wiener, [On the Foundations of Noise-Free Selective Classification](https://jmlr.csail.mit.edu/papers/v11/el-yaniv10a.html), *JMLR*, 2010.
6. Ronald A. Howard, [Information Value Theory](https://doi.org/10.1109/TSSC.1966.300074), *IEEE Transactions on Systems Science and Cybernetics*, 1966.
7. Jonathan Baron and John C. Hershey, [Outcome Bias in Decision Evaluation](https://doi.org/10.1037/0022-3514.54.4.569), *Journal of Personality and Social Psychology*, 1988.
8. A. P. Dawid, [The Prequential Approach](https://www.jstor.org/stable/2981683), *Journal of the Royal Statistical Society A*, 1984.
9. Dario Amodei et al., [Concrete Problems in AI Safety](https://arxiv.org/abs/1606.06565), 2016.
