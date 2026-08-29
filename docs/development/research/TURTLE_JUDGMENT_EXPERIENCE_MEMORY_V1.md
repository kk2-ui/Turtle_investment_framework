# Turtle 企业判断经验调用闭环 V1

> 状态：`IMPLEMENTED_ON_MAIN / ONE_PREOUTCOME_INVOCATION_FROZEN / FEEDBACK_PENDING`
>
> 日期：2026-08-29
>
> 设计基线：`feat/judgment-first-training-iteration-12h@08c8620`
>
> 当前实现基线：`main@5d64b91b354d`

本文不重写四轨课程、八维问题骨架、Blind feedback、Comparative、PIT、CJO
或方法迁移控制。它只补最新训练基线尚未闭合的一段：让真实反馈形成的经营经验，能在
普通新公司研究中被结构化调用，并在结果回来后更新适用边界。

### 当前实现说明

`scripts/judgment_experience_memory.py` 已实现 source-side record、retrieval pack、结果前 invocation、target analogy projection 和受独立授权约束的 feedback update。`CN601865@2024-04-01` 已完成一次结果前调用并保留 FY2024 outcome sealed；当前只能说明隆基经验材料性改变了福莱特的研究问题、证据顺序、反方和新增产能的保守现金处理，不能说明经验被结果支持或方法已验证。

2026-08-29 起，本对象作为[企业投资承保系统 V1](TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md)的经验层继续使用。后续 record 优先从完整 `EnterpriseUnderwritingEpisode` 投影处境、承保路线、near miss、正常化、永久损失和价值路由边界；不另建经验卡。

## 0. 投资者结论

当前系统已经会：

- 对一家公司形成结果前判断；
- 在结果后结算判断、生成 feedback 和 learning note；
- 用人工策展的同机制 Teaching card 与 near miss 做一次 Holdout；
- 用 `analogy_transfer_cards` 在当前公司中冻结结构类比；
- 证明某条 learning note 确实改变了另一家公司的冻结字段。

但这些能力还没有变成日常研究飞轮。断点是：

```text
真实反馈或 Teaching 案例
  -> 临时文档、learning note 或手工 memory pack
  -> 需要专门 Agent 知道它在哪里并手工挑选
  -> 普通公司研究不会稳定检索、应用和回写
```

所以系统能证明“某次做过学习实验”，却还不能稳定做到：

> 研究新公司时，自动找到结构上相近的经营经验和最重要的反例；判断哪些部分可迁移；
> 把实际改变的研究处理在结果前冻结；结果回来后保留、收窄或废弃这条经验。

V1 的产品目标不是更多卡片，而是更早识别企业机制、少犯可迁移的判断错误，并最终改善
正常利润、owner cash、永久损失、估值区间和买点处理。

## 1. 最新基线已经有什么

下列对象必须直接复用，禁止另造同义系统：

| 已有对象 | 已有能力 | V1 处理 |
|---|---|---|
| `judgment_training_curriculum.py` | Teaching、Blind、Holdout、Prospective 路由 | 不修改课程语义 |
| `judgment_feedback.py` | 从冻结判断与结算生成 feedback | 作为经验来源 |
| `judgment_learning.py` | learning note、跨公司 application receipt | 保留方法学习语义 |
| `judgment_feedback_control.py` | append-only feedback/learning/application 控制 | 追加经验反馈事件，不改旧事件 |
| `149_V5_MEMORY_RETRIEVAL_PACK.json` | 同机制 card + near miss 的真实手工检索包 | 作为 retrieval pack 的现有原型 |
| `analogy_transfer_cards` | 当前 target 的结构映射、差异、失效条件和 near miss | 继续作为 target-side 冻结对象 |
| `ConditionalMechanismSynthesis` | moderator、break condition、证据上限 | 作为经验编译输入 |
| `EnterpriseSystemModel` / `ManagementDecisionLedger` | 当前公司的事实和管理行动 | 经验层只引用，不复制 |
| Frozen CJO、估值、报告 handoff | 当前公司判断向投资处理传播 | 不接受历史经验直接写值 |

### 1.1 `08c8620` 之后不应再重复的设计

`b76683d` 与 `7574161` 已经证明“规则提示”应转向“Teaching 机制记忆”，并完成过
同机制 card、near miss、结果前双臂输出与材料性差异审阅。`2939376` 与 `08c8620`
又完成了招商银行和隆基的真实 Blind feedback。

因此 V1 不再新增第二套 `ExperienceCard`。现有 Teaching mechanism card 和
`analogy_transfer_cards` 的经济内容已经足够。真正缺失的是：

1. **source-side registry**：哪些现有经验可供检索，目前没有统一登记和版本边界；
2. **runtime retrieval**：普通研究运行时没有稳定的结构检索入口；
3. **invocation receipt**：没有统一记录“检索后实际采用了什么、拒绝了什么”；
4. **feedback update**：target 结果回来后，没有把应用结果回写到经验适用边界。

## 2. 一个经验，两种投影，三种权限

### 2.1 Source、target 和 method 必须分开

```text
source-side JudgmentExperienceRecord
  描述过去案例可复用的条件化经验

target-side analogy_transfer_card
  描述这条经验在当前公司如何映射、哪里不匹配、如何失效

method-side LearningNote / learning application receipt
  描述是否要改变跨案例研究政策
```

这三者不可互相替代：

- 一个经验可以帮助当前公司提问，但尚不足以改变通用方法；
- 一个 target 类比必须重新验证当前公司的结构，不能继承 source 的结论；
- 只有已有 learning 控制确认的材料性跨公司变化，才进入方法候选。

### 2.2 权限单向流动

```text
feedback / Teaching / ConditionalMechanismSynthesis
  -> JudgmentExperienceRecord
  -> ExperienceRetrievalPack
  -> ExperienceInvocationReceipt
  -> existing target analogy_transfer_card (only when actually applied)
  -> current-company evidence and Frozen CJO
  -> normal earnings / owner cash / value / BuyBand
```

经验记录本身没有当前公司事实、概率、估值或买点权限。

## 3. 新增对象一：`JudgmentExperienceRecord`

它是 source-side 的可检索派生记录，不是新事实库，也不叫 Card，以免与已有 target-side
`analogy_transfer_cards` 混淆。

```text
JudgmentExperienceRecord
  - record_id / version / status
  - source_kind / source_refs / review_refs
  - evidence_ceiling
  - proposition
  - structural_key
      - mechanism_kind
      - industry_epoch / lifecycle
      - competitive_arena
      - responsibility_boundary
      - company_constraints
  - decision_or_no_action
  - mechanism_chain
  - observable_signals
  - strongest_rival
  - apply_when
  - do_not_apply_when
  - investor_relevance
  - feedback_event_refs
```

### 3.1 允许来源

- 已审阅的 Teaching lesson；
- 已完成的 Blind judgment feedback；
- 已接纳的 `LearningNote`；
- `ConditionalMechanismSynthesis`；
- 仅在自身 estimand 内的 Comparative feedback。

记录只能引用已有 source、feedback、review 和 case identity。它不能从结果倒推原案例
没有冻结过的管理行动、阈值、因果关系或当前公司结论。

### 3.2 经验状态

```text
DRAFT
  来源可追溯，但条件、反方或边界不完整；不进入运行时检索

RETRIEVAL_READY
  结构条件、反方、不可迁移边界和证据上限已审阅

BOUNDED
  后续应用暴露了更窄的适用条件；仍可检索

RETIRED
  重复误用或直接反例表明继续调用会误导；只保留历史审计
```

状态不是能力分数。调用次数不能自动升级证据权限。

### 3.3 反馈根因不可混为“更谨慎”

经验编译必须保留实际根因：

```text
STATE          企业状态或责任范围认错
DECISION       管理选择或替代方案认错
MEASUREMENT    数据口径、并表或结果测量问题
MECHANISM      客户、竞争或单位经济传导认错
TRANSMISSION   利润、现金、资本或普通股归属传导认错
ENVIRONMENT    周期、政策、价格、汇率或竞争环境变化
```

例如，年报版本无法唯一定位只能形成 `MEASUREMENT` 经验；不能被编译为企业失败或管理层
能力差。集团现金增加但普通股不可达属于 `TRANSMISSION`，不能降级客户需求。

## 4. 新增对象二：`ExperienceRetrievalPack`

该对象把现有手工 `V5_MEMORY_RETRIEVAL_PACK` 固化为普通研究可调用的只读接口。

### 4.1 检索时点

只在当前公司完成 `FRAME / SCOPE / HYPOTHESES` 之后、最终 judgment freeze 之前检索。
输入仅来自 cutoff 前当前公司状态：

- 主问题和机制；
- 生命周期和竞争 arena；
- 企业约束与责任边界；
- 当前基准解释和最强反方；
- 本次任务允许的 evidence ceiling。

不得读取当前 target 的 outcome、价格、估值结果或未来报告。

### 4.2 两阶段检索

第一阶段按结构过滤：

```text
mechanism_kind
-> lifecycle / industry_epoch
-> competitive_arena
-> company_constraints
-> responsibility_boundary
-> evidence_ceiling
```

第二阶段才做语义排序。公司名、行业名或结局方向相似不能单独触发推荐。

一次最多返回三种角色：

```text
PRIMARY_ANALOG
  当前结构最相近的经验

STRONGEST_NEAR_MISS
  表面相近但关键中介不同的反例

BOUNDARY_RECORD
  最可能导致迁移断裂的责任或测量边界
```

不是每次都必须凑齐三张。无适用记录时返回 `NO_APPLICABLE_EXPERIENCE`，当前公司研究继续。

### 4.3 检索输出是问题，不是答案

向 Judgment Owner 展示：

- 为什么可能适用；
- 哪些结构差异必须重新验证；
- 原案例哪部分不得迁移；
- 必须同时检查的反方；
- 哪个当前公司信号能区分二者；
- 验证失败时，哪项盈利、现金、风险或估值处理不应被承保。

不展示“当前公司也会成功/失败”的结论。

## 5. 新增对象三：`ExperienceInvocationReceipt`

已有 learning application receipt 是 method-side 对象，要求 learning note、方法审阅和冻结
字段变化。不能改写它来承载普通经验调用。V1 新增一个更窄、无方法权限的 invocation
receipt：

```text
ExperienceInvocationReceipt
  - invocation_id
  - retrieval_pack_id
  - record_id / version
  - target_case_id / company_cluster_id / cutoff
  - structural_match
  - mismatch_dimensions
  - accepted_transfer
  - rejected_transfer
  - changed_question_refs
  - changed_evidence_priority
  - changed_rival_or_discriminator_refs
  - changed_investor_treatment
  - projected_analogy_transfer_card_id
  - frozen_at / outcome_access_state
```

### 5.1 应用状态

```text
RETRIEVED_NOT_APPLIED
  看过经验，但没有改变当前研究行为；不计学习

APPLIED_PREOUTCOME
  在结果前改变了问题、证据顺序、反方、判别信号或投资处理

REJECTED_AS_MISMATCH
  关键结构不匹配；保留拒绝理由，防止未来重复误用
```

### 5.2 与现有 `analogy_transfer_cards` 的关系

当且仅当经验实际用于当前公司的机制判断时，由 adapter 把 source record 和 target
mapping 编译成现有 `analogy_transfer_card`：

- `source_case_id` 来自 experience source；
- `target_state_vector` 来自当前公司证据；
- `structural_mapping`、`mismatch_dimensions` 和 `invalidation_conditions` 来自本次调用；
- `strongest_near_miss` 来自 retrieval pack；
- `linked_discriminator_ids` 必须是当前 target 的判别信号。

禁止新建另一套 target card schema。`RETRIEVED_NOT_APPLIED` 和
`REJECTED_AS_MISMATCH` 不生成 `analogy_transfer_card`。

## 6. 结果后反馈

target outcome 经现有 custodian 和 judgment review 结算后，追加
`EXPERIENCE_FEEDBACK_RECORDED` 事件：

| 状态 | 含义 | 对 registry 的处理 |
|---|---|---|
| `SUPPORTED` | 调用帮助识别了实际机制或避免了材料错误 | 保留当前边界 |
| `BOUNDARY_EXPOSED` | 部分适用，但 moderator 造成分叉 | 新版本收窄 `apply_when` |
| `MISAPPLIED` | 表面相似，关键结构不匹配 | 记录反例；必要时 `BOUNDED` |
| `NOT_DIAGNOSTIC` | 结果不能区分经验与反方 | 不授予迁移信用 |
| `MEASUREMENT_BLOCKED` | 结果口径无法结算 | 不解释为企业失败 |
| `RETIRED` | 重复误导或直接反馈否定经验 | 停止运行时检索 |

反馈采用追加式版本。旧 record、invocation 和 target 判断不被改写。

只有当反馈实际改变了跨案例研究政策，才按现有流程生成或更新 `LearningNote`，并继续使用
现有 `record_learning_application`。普通经验反馈不能自动升级为方法、CJO 或生产规则。

## 7. 日常研究和训练的统一运行方式

```text
1. 当前公司先独立形成状态、主问题和最强反方
2. 结构化检索最多三条历史经验
3. Agent 明确接受和拒绝的迁移部分
4. 若研究处理发生变化，冻结 invocation 和现有 analogy_transfer_card
5. 继续使用当前公司证据形成 CJO
6. 结果回来后独立结算经验调用
7. 更新 registry 边界；必要时再进入现有 LearningNote 流程
```

### 7.1 不把经验层变成新 gate

- 没有可用经验，仍须完成公司判断；
- 经验缺字段，只影响该经验是否可检索；
- `MEASUREMENT_BLOCKED` 只影响对应反馈；
- 不要求每家公司产生 invocation；
- 不要求每次 invocation 都进入方法实验；
- 不为证明经验有用而制造弱 Baseline；
- 不因一次无材料差异继续重复配对实验。

## 8. 与投资判断、估值和黄金报告的边界

经验允许改变：

- 当前研究问题与证据顺序；
- 当前最强反方和判别信号；
- 哪些增长、利润或现金暂不进入基准；
- 乐观、基准、悲观情景的条件；
- 永久损失调查和估值敏感项的优先级。

最终仍必须回到当前公司：

```text
JudgmentExperienceRecord
  -> current-company question and evidence
  -> target analogy_transfer_card
  -> Frozen CJO
  -> normal earnings / owner cash / permanent loss
  -> valuation / BuyBand
```

经验记录禁止直接成为：

- 当前公司事实或管理层评价；
- 当前公司概率；
- 正常利润、owner cash 或估值数值；
- 目标价、BuyBand 或投资动作。

## 9. 验收：证明“经验被用对”，不是“系统记得多”

### 9.1 四层指标

1. **Retrieval fit**：推荐是否结构匹配，并同时暴露 near miss；
2. **Invocation fidelity**：结果前收据是否反映 Agent 真正采用或拒绝的部分；
3. **Feedback quality**：结果后能否区分支持、边界、误用和不可诊断；
4. **Investor materiality**：是否改变机制、owner cash、永久损失、正常利润、估值方向或首要研究行动。

同时记录：

- `false_transfer`：因公司名、行业名或结果相似而错误迁移；
- `memory_overreach`：把历史经验写成当前事实、概率或估值；
- `passive_retrieval`：检索后没有任何材料处理变化。

### 9.2 何时需要 A/B

普通经验调用不要求每次都做 Baseline/Enhanced 配对。配对只在系统声称“这类经验检索比
当前合理 Baseline 更有效”时进行，而且必须冻结材料性处理差异。

V1 首先验证纵向闭环：

```text
一个真实反馈来源
  -> 一个 RETRIEVAL_READY record
  -> 一个不同公司的 sealed target
  -> 结果前 invocation
  -> 独立 outcome / judgment feedback
  -> record 保留、收窄或退休
```

这避免把训练预算继续消耗在没有材料差异的配对实验上。

## 10. 最小实施工作包

### M0：复用审计与 schema freeze

先写一份对象映射测试，证明没有复制 `LearningNote`、learning application receipt、
V5 Teaching card 或 `analogy_transfer_cards` 的既有权限。随后新增：

- `judgment-experience-record.v1`；
- `experience-retrieval-pack.v1`；
- `experience-invocation-receipt.v1`；
- `experience-feedback-event.v1`。

### M1：Registry compiler

从现有 Teaching、Blind feedback、LearningNote 和
`ConditionalMechanismSynthesis` 编译 source-side record。V1 使用仓库内 JSON read model
或现有 control-plane projection 即可，不建立新的事实数据库、向量数据库或迁移框架。

### M2：结构检索

先做确定性结构过滤和可解释排序。V1 不需要 embedding 服务；当结构候选过多时，语义排序
可以作为后续优化，不得成为可用性的前提。

### M3：结果前调用与 target 投影

在 Blind/E1/E2 的 judgment freeze 前接入 retrieval pack；记录 invocation。实际应用时
只生成现有 `analogy_transfer_card`，不修改当前公司的 source packet。

### M4：结果后反馈

在现有 settlement 和 independent post-outcome review 后追加 experience feedback event，
生成 record 新版本或退休状态。需要方法变化时，再调用现有 learning 流程。

### M5：最小真实纵向验证

优先使用已完成且有材料 judgment delta 的真实 feedback 编译一条 record，再选一个不同公司、
结果仍封存的 target。不要先扩行业 roster、重做 Comparative 或建立大规模卡库。

## 11. 基线 Agent 实施 Goal

```text
Goal: Implement Judgment Experience Invocation Loop V1 on
feat/judgment-first-training-iteration-12h@08c8620.

Purpose:
Turn existing Teaching/Blind feedback into reusable, condition-bound enterprise
experience that can change a different company's pre-outcome research treatment
and be revised after outcome feedback.

Do not redesign or change the semantics of the four-track curriculum, eight
dimensions, Comparative, PIT, CJO, LearningNote, record_learning_application,
or existing analogy_transfer_cards.

Required vertical slice:
1. Add source-side JudgmentExperienceRecord, ExperienceRetrievalPack,
   ExperienceInvocationReceipt, and ExperienceFeedbackEvent validators.
2. Compile at least one RETRIEVAL_READY record from an existing reviewed
   Teaching or completed Blind feedback artifact.
3. Retrieve by mechanism/lifecycle/arena/company constraints/responsibility
   boundary before any semantic ranking. Return a primary analog plus a near
   miss or boundary when one is applicable; never force a match.
4. Freeze, before target outcome access, what was accepted, rejected, and what
   material question/evidence order/rival/discriminator/investor treatment changed.
5. When applied, project into the existing target-side analogy_transfer_card;
   do not create a second target card system.
6. After existing outcome settlement and independent judgment review, append
   SUPPORTED / BOUNDARY_EXPOSED / MISAPPLIED / NOT_DIAGNOSTIC /
   MEASUREMENT_BLOCKED / RETIRED feedback and version the source record.
7. Experience may affect research questions and current-company CJO formation,
   but may not write current facts, probabilities, valuation inputs, BuyBand,
   report authority, or investment actions.
8. No applicable experience, no material application, or a measurement block
   must remain local and must not stop the company judgment.

Focused tests:
- existing-object overlap test;
- structural match positive case;
- same-industry but responsibility-mismatched rejection;
- near-miss/boundary retrieval;
- result leakage rejection;
- source and target company identity separation;
- retrieved-not-applied produces no transfer credit or analogy card;
- applied invocation projects exactly one existing analogy_transfer_card;
- measurement block cannot become enterprise failure;
- experience cannot write current facts, CJO values, valuation or BuyBand;
- append-only feedback versions preserve the original invocation.

Real acceptance:
- one reviewed real source record;
- one different-company sealed pre-outcome invocation;
- one concrete material research-treatment change;
- one independent post-outcome experience feedback when a lawful target result
  is available; otherwise report engineering completion only and leave the
  real transfer claim ungranted;
- focused, adjacent, full project tests and merge-check pass;
- investor readout states what judgment improved, what remains uncertain, and
  whether the record was retained, narrowed, misapplied, or not diagnostic.
```

## 12. 设计成功标准

这层最终只看五件事：

1. 新公司研究能找到真正相关的历史经营经验和反例；
2. Agent 能说明哪里适用、哪里不适用；
3. 经验在结果前改变了一项材料研究处理，而不是增加背景文字；
4. 结果后适用边界能够更新；
5. 变化最终通过当前公司的 CJO 改善企业判断、永久损失、估值或买点。

一句话：

> **最新基线已经会做反馈实验；V1 只负责让反馈成为下一家公司能调用、能拒绝、能复验、
> 能更新边界的经营经验。**
