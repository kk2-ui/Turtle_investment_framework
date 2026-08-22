# 结构化类比与近失效卡

状态：`QUESTION_ONLY / ARCHIVE_INTAKE / TRANSFER_CANDIDATE / NOT_TRANSFERRED`

## 两阶段纪律：先结构，后理由

默认使用 `STRUCTURE_FIRST`，而不是一开始就把 source 的故事、目标公司的故事和“为何相似”写在一起。研究者先分别抽取 target 与 source 的因果角色，再允许比较；理由写作只发生在二者对齐之后。这样做是为了降低品牌、行业名、规模或著名结局等容易叙述的表面相似压过 `driver → intermediate → operating observation` 结构的风险。

这是一项待检验的研究干预，不是已经证明会提高 Turtle 判断的规则。若同一研究者/模型在 target pass 前已知 source 的详细材料或结局，必须标 `CONTEXT_SEPARATION_NOT_ASSURED`：该卡仍可用于问题设计，但不能作为这项干预的干净验证。

### Pass A：target-only 结构草图（先完成，未打开 source 正文）

- target 的 PIT source package / cutoff：
- source 可见状态：`NOT_OPENED / CONTEXT_SEPARATED / CONTEXT_SEPARATION_NOT_ASSURED`。
- target 决定性问题、时间尺度与当前状态向量：
- target `driver → intermediate → operating observation` 的最小因果骨架：
- target 的 H-A/H-B 与各自需要分叉的未来观察：
- 当前未知的结构约束、可能断裂条件与禁止推断：

本段不得出现 source 公司名、行业名、管理层、结果、估值倍数、股价或回报；也不得以“像某案例”替代 target 自身机制。

### Pass B：source-only 结构草图（独立于 Pass A 的 source 原件）

- source 的当时状态、cutoff 与可用性身份：
- source `driver → intermediate → operating observation` 的最小因果骨架：
- source 的已知断裂条件、结果可见性与禁止迁移项：
- 若 source 没有同期机制/结果链：只写 `QUESTION_ONLY_ROUTING_CARD`，不填结构性支持结论。

只有 Pass A、Pass B 都保留后，才可进入下列“结构匹配与断裂”。任何在 Pass A 后补写 target 草图的行为，都要在裁决中记录为 `CONTEXT_CONTAMINATED / NOT_TRANSFERRED`，不能伪装成独立结构抽取。

### 最小交接收据（仅当要把 `STRUCTURE_FIRST` 当作干预测试时填写）

| 阶段 | 允许的输入 | 冻结后输出 | 不得接收或补写 |
|---|---|---|---|
| target mapper | target 的 cutoff 前 source IDs、目标问题和 target 时间边界。 | Pass A 的状态、H-A/H-B、因果骨架、未知与候选断裂。 | source 的实体、行业/品牌叙事、结果、匹配理由、目标价或回报。 |
| source mapper | source 的 cutoff 前原件 IDs、source cutoff 与结果可见性身份。 | Pass B 的当时状态、因果骨架、已知断裂和禁止迁移项。 | target 的实体、当前事实、H-A/H-B、目标结果或想要匹配的答案。 |
| integration lead | 已冻结的 Pass A/B、各自 source ID 清单和本卡裁决字段。 | 因果角色对齐、排除的表面相似、近失效与新增断裂观察。 | 新的公司事实、结果期材料、将 source 的结局写成 target 支持，或回写 Pass A/B。 |
| reviewer | 两份输入清单、Pass A/B locator、integration 输出与时间顺序。 | `CONTEXT_SEPARATED / CONTEXT_SEPARATION_NOT_ASSURED / CONTEXT_CONTAMINATED`。 | 判断 target 公司好坏、结果期胜负、估值、价格或回报。 |

- 同一研究员可顺序承担这些角色；同一模型/会话已含另一侧材料、source 结果或既有类比结论时，必须写 `CONTEXT_SEPARATION_NOT_ASSURED`。这不是失败，但该卡不能检验输入顺序的去偏作用。
- 使用多 agent 时，只交付本表所列 source IDs/问题和相应 packet，不把其他角色的草稿、总结或“应得结论”转发。多个 agent 也不构成独立样本，不能投票。
- integration 的任何新增事实必须退回各自 mapper 按原边界重做；不能以“协调者常识”补入。

## 问题与边界

- 目标公司的决定性问题和时间尺度：
- source case：
- source case 身份：`QUESTION_ONLY_ROUTING_CARD / ARCHIVED_EX_ANTE_EXTERNAL / ELIGIBLE_LEARNING_EPISODE / OUTCOME_SELECTED_TEACHING_CASE / OTHER`
- source case 的结果在类比形成时是否可见：
- 不允许迁移：结局、估值倍数、目标价、股价回报、管理层声望。

### 外部历史判断链（仅当身份为 `ARCHIVED_EX_ANTE_EXTERNAL` 时必填）

这部分的用途是把**他人当时的判断**与后来事实分开保存，以形成可检查的结构经验；它不是 Turtle 自己在未知结果下的预测。

- 原始判断作者/机构及其与目标公司的关系：
- 原始判断发表日与该判断的 cutoff：
- 原始判断的原件 source package / locator（不得用后来的书籍摘要、访谈转述或回顾性文章替代）：
- 原作者在当时选择的机制、对立机制及选择理由（原文未表达的部分写 `UNKNOWN`，不得代填）：
- 原作者预期的指标、方向、口径与窗口（缺任一项则只能作 `OUTCOME_SELECTED_TEACHING_CASE`）：
- 结果前重复官方通道证明：既有常规披露的 source/locator、同一指标或完整预注册 GAAP 重建、未来结果文件类型与披露节奏（一次性 proxy / investor deck / reconciliation 不足）：
- 指标重建规则、允许转换、禁止替代和定义变更时的停止动作：
- 后续结果的独立 source package / locator，以及它与原判断是否来源独立：
- 当前研究者对结果的熟悉度：`KNOWN_AFTER_ARCHIVE_INTAKE`；不得声称为 Turtle 的盲测：

`QUESTION_ONLY_ROUTING_CARD`（包括现有书籍案例卡）没有以上两条来源链时，只能提出问题和候选断裂；它不能升级为外部 episode、近失效证据、基准率或 Turtle 准确率。

## 可迁移的机制命题

```text
source driver → source intermediate variable → source operating observation
target driver → target intermediate variable → target observable sequence
```

## 结构匹配与断裂

| 机制层维度 | source case | target case | 真正匹配 / 不匹配 |
|---|---|---|---|
| 客户替代/支付意愿 |  |  |  |
| 渠道交易点/接口控制 |  |  |  |
| 服务、互补资产或成本结构 |  |  |  |
| 资本/治理/监管约束 |  |  |  |

- 至少三个支持迁移的匹配维度：
- 最强结构断裂条件：
- 若断裂成立，目标机制会怎样失效：
- 明确排除的表面相似（品牌、行业名、规模、叙事、已知结局等）：
- 对齐后新增、且 target-only 草图原本没有的可证伪观察：

## 近失效案例

- 表面相近的案例：
- 身份与来源链：`QUESTION_ONLY_ROUTING_CARD / ARCHIVED_EX_ANTE_EXTERNAL / OUTCOME_SELECTED_TEACHING_CASE / OTHER`；若声称为外部 episode，按上节完整填写其原始判断与独立结果链：
- 与 source/target 的关键断裂：
- 它给目标公司提出的不同后续观察：

## 裁决

- 目标公司上可验证的 `A_ONLY / B_ONLY` 观察：
- 证据上限与可接受结果来源：
- 这次迁移只沉淀什么条件、断裂与信号顺序：
- 不得由此替代的目标公司证据：
- 当前裁决：`QUESTION_ONLY / ARCHIVE_INTAKE / TRANSFER_CANDIDATE / NOT_TRANSFERRED`
- 下一步：

### 干预验证（不以公司终局替代过程证据）

- Pass A/B 是否在对齐前各自可读、且没有另一侧的叙事或结果泄漏：`PASS / CONTEXT_SEPARATION_NOT_ASSURED / CONTEXT_CONTAMINATED`。
- 对齐是否只依赖因果角色而非已排除的表面相似：`PASS / FAIL`。
- 类比是否新增一个不同于 target-only H-A/H-B 的、可在目标公司结算的断裂观察：`PASS / NOT_DIAGNOSTIC`。
- 结果期只结算该预注册断裂观察及其来源合同；它不因 target 后来好/坏、价格或回报自动“成立”。
- 跨至少两个独立 target 后，才可在 learning review 问：`STRUCTURE_FIRST` 是否减少了表面迁移或增加了可结算断裂；此前不报告方法胜率或优越性。
