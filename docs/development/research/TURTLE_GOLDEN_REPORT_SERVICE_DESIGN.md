# Turtle 训练反馈到黄金报告的服务定位设计

> 状态：`ENTERPRISE_UNDERWRITING_CONSUMER_DESIGN / VERTICAL_SLICE_PENDING`
>
> 日期：2026-08-29
>
> 上位路线：[黄金报告驱动的双向层级研究路线图](../GOLDEN_REPORT_BIDIRECTIONAL_RESEARCH_ROADMAP.md)
>
> 本文件回答一个问题：训练反馈系统在 Turtle 中究竟为黄金报告生成提供什么服务。它是产品和模块边界设计，不是训练效果证明，也不授权提前生产 G1.5 的 24 份报告。

## 0. 2026-08-29 顶层更新

黄金报告不再从八维状态、训练 lane、CJO 状态码和 valuation handoff 中重新拼装一条公司故事。当前设计以[企业投资承保系统 V1](TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md)为上位真源：报告、CJO 和估值必须消费同一个 `EnterpriseUnderwritingEpisode`。

```text
UnderwritingThesis（价格前）
  -> Frozen CJO compatibility projection
  -> 正常盈利 / owner cash / permanent-loss / value-route inputs

InvestmentTreatment（价格后）
  -> 市场隐含要求 / 安全边际 / BuyBand 或研究处理

同一 Episode
  -> Golden Report reader narrative
```

这不是新增第四个数据库。Episode 只引用现有 evidence、EnterpriseSystemModel、ManagementDecisionLedger、Judgment Experience、Frozen CJO 和 valuation objects。其作用是让一个中心判断拥有从处境到价格的完整语义，并防止报告 writer、CJO compiler 和估值层各自选择不同故事。

### 0.1 报告首先回答什么

一份黄金报告的第一屏和中心论证必须先让投资者理解：

1. 公司处在怎样的宏观/行业阶段，当前压力是周期还是结构；
2. 公司是否能活下来，真正的融资和索取权风险是什么；
3. 公司竞争位置和管理层适应能力怎样；
4. 正常情况下可持续盈利和 owner cash 在什么范围；
5. 哪些路径会造成永久损失；
6. 为什么使用当前价值路线，哪些成长或资产不能计价；
7. 当前价格要求什么，安全边际和最高可接受处理怎样；
8. 最强反方和会翻转结论的观察是什么。

其中第 1 项必须形成 `IndustryFutureThesis`，不能停在宏观/行业事实罗列：报告要在适当
时域内选择最可能的行业 regime，说明利润池怎样迁移、公司怎样暴露和适应，并把结果传
到正常盈利、owner cash、永久损失、价值路线与价格处理。该主张属于同一 Episode 的
`Situation Model`，不建立平行行业账本。

宏观只在存在行业和公司传导时出现。十五章仍可作为导航，但不再作为十五个并列任务；所有章节都是同一承保主张的展开。

### 0.2 UNKNOWN 和权限怎样呈现

内部 `UNKNOWN / NO_PRIMARY / MEASUREMENT_MISMATCH / EVIDENCE_INELIGIBLE` 继续限制对应 claim。读者正文把它们翻译成：可进入基准、条件性进入、只保留情景、从基准排除或暂时无法形成范围。技术状态、schema、receipt 和权限说明进入附录，不能挡在企业判断之前。

无法形成数值 BuyBand 时，报告仍须说明“不为哪项未来付费、什么事实会允许定价”。这不绕过计算权限，也不把整份报告降成控制状态说明。

## 1. 一句话定位

Turtle 的训练反馈系统是**研究质量控制面与方法记忆编译器**：它把经过 PIT 隔离、结果结算、错误诊断和跨公司复核的窄方法改变，编译成下一份报告的研究议程和判断前置物；它不把旧报告、事后结论或行业故事直接塞进模型上下文。

正式的产品名称沿用：**黄金报告驱动的双向层级研究系统**（Golden-Report-Driven Bidirectional Hierarchical Research System）。它不是蜂群投票、Agent 共识或报告摘要库。多个 Agent 可以并行取证、提出反方和复核，但中心判断必须由同一信息集下的公司证据、竞争机制和独立审阅共同决定。

## 2. 它解决什么，不能解决什么

### 2.1 要解决的问题

- 每家公司从零开始，重复犯同一类行业、客户、单位经济和现金传导错误；
- 训练结果停留在复盘文字，无法改变下一家公司的冻结前字段；
- 行业知识与公司事实混在一起，导致类比被误写成证据；
- 报告只写经营叙事或只做估值，不能把中心判断传播到正常利润、普通股现金、价值和回报；
- 结果已知材料被误当作选择能力、留出证据或经验概率。

### 2.2 明确不解决的问题

- 不训练基础模型权重，不承诺模型“像资深投资者”；
- 不用报告数量、Token 数、Agent 数、投票或篇幅衡量判断力；
- 不从一家公司或一份报告直接升格行业规律；
- 不用行业先验、基准率、股价或事后回报填补本公司 `UNKNOWN`；
- 不输出未经独立验证的概率、胜率、选股收益或组合结论；
- 不替代公司研究、确定性模型、黄金报告验收或投资决策。

## 3. 服务在 Turtle 中的位置

```text
官方证据 / PIT 信息围栏
        |
        v
公司经营系统图 + H-A/H-B + 最强反方
        |
        v
公司判断冻结（CJO）+ 前瞻判断（FJ）+ 财务驱动桥
        |                         \
        |                          \ 同 cutoff 投资增强（仅投资用途）
        v                           v
反馈控制面：到期、采集、结算、诊断、学习应用       黄金报告编译与发布
        |
        v
方法规则 / 行业机制快照 / 迁移约束
        |
        +----> RESEARCH_AGENDA（下一份报告先问什么）
        +----> JUDGMENT_SYNTHESIS（本公司判断如何闭合）
        +----> INVESTMENT_ENRICHMENT（判断完成后才估值、回报、动作）
```

报告生成读取的不是训练数据库的“结论全文”，而是 `judgment-generation-handoff.v1` 的派生只读视图。视图只携带最小、带来源指针和时间身份的内容；事实、结果、模型和学习仍以各自 canonical artifact 为真源。

## 4. 十个模块与责任边界

| 模块 | 责任 | 主要产物 | 不得越权 |
|---|---|---|---|
| M1 官方证据与 PIT 围栏 | 枚举、选择、读取和版本化 cutoff 前资料 | evidence package、source selection、读取审计 | 不用后验资料补写当时事实 |
| M2 企业经营系统图 | 连接客户/行业、产品/活动、组织、竞争、现金和资本 | operating system map、状态向量 | 不把系统图当公司事实或完整结论 |
| M3 竞争机制与反方 | 对同一当前事实形成 H-A/H-B、最强反方和断裂条件 | mechanism pair、alternative set | 不以多数 Agent 选择中心路径 |
| M4 公司判断与前瞻合约 | 冻结中心路径（或 `NO_PRIMARY`）、3–5 个 FJ、简单基线和财务驱动桥 | CJO、thesis test、FJ、FDB | 不把敏感性表当作中心预测 |
| M5 结果采集与分层结算 | 按冻结来源、窗口和口径逐箭头结算 | extraction、settlement、observation | 不换 KPI、不手填实际值、不用股价替代经营结果 |
| M6 诊断与学习应用 | 双正交 failure locus、learning note、方法复盘和跨公司 receipt | diagnosis、LNOTE、LAPP | 不以“更谨慎”或事后故事冒充学习 |
| M7 行业经验工厂 | 从已接纳报告形成机制候选，保留反例、边界和可用时间 | industry mechanism snapshot | 未达升格门时不得注入先验 |
| M8 宏观综合 | 由多个行业共同变量向上归纳，再按暴露向下传播 | macro scenario、transmission map | 不由单一行业直接宣布宏观或覆盖公司证据 |
| M9 黄金报告编译与验收 | 读取三视图，生成连续报告、模型、HTML 和独立审阅包 | report package、publication receipt | 不在 HTML 或正文另造事实、模型或结论 |
| M10 判断反馈控制面 | 持久登记、事件顺序、到期 inbox、权限、reconcile 和恢复 | claims/events/read model | 不复制 M1–M9 的专业语义，不把“已接线”说成效果已验证 |

M10 是控制面，不是第 11 个研究大脑。它只保证“谁在什么时间、依据什么冻结对象、允许做哪一步”；具体的行业、公司、财务和报告判断仍归 M1–M9。

## 5. 训练反馈如何服务一份黄金报告

### 5.0 报告前先建立行业承保上下文

公司报告不能只读取两三家同业的横截面数字，再把本公司年报扩写成行业判断。正式研究在
进入公司中心路径前，应先把现有行业资产编译为同一 `Situation Model` 内的
`IndustryUnderwritingContext`。它是派生读模型，不是新的行业事实库，至少覆盖：

- 客户任务、价值链、收入与资本形成方式；
- 当前结构 epoch，以及需求、供给、竞争、监管、融资和技术怎样移动利润池；
- 不同公司 archetype 的约束、适应路径、失败路径和生命周期差异；
- 按机制角色选择的参照公司与 near miss，包括成本参照、客户参照、资本参照、失败参照
  和边界参照；数量由问题决定，不固定为两三家，也不要求把全部公司写入正文；
- 行业主路径、最强竞争解释、可用时域和会使判断翻转的观察；
- 仍须由目标公司一手证据验证的暴露、适应、单位经济、现金和资本字段。

这个上下文可以引用已接纳的 `IndustryLearningBlock`、行业机制、官方行业观察、完整 worked
case 和反例，但不得把它们写成目标公司事实。知识不完整时，编译器输出有边界的上下文和
缺失部分，报告继续研究；不能因为缺少某张机制卡或固定数量同行而停止公司判断。

训练系统在这里承担两项不同责任：一是积累并更新行业 reference class，避免每家公司从
零开始；二是保存“行业知识怎样在不同公司失效”的 near miss，避免行业平均替代公司判断。
前台最终使用的仍是 `IndustryFutureThesis`：从行业上下文选择最可能路径，再用本公司证据
完成暴露、适应和经济后果的承保。

行业上下文的效用只在离线 A/B 中验收，不增加新的报告阻断门。冻结同公司、同 cutoff 的
基础处理与上下文处理后，只比较行业路径、目标暴露、owner cash、永久损失及估值路线/
决定性证据。至少一项投资处理发生材料变化，或同口径关键经济区间严格收窄，才算
`MATERIAL_UTILITY`；只增加行业段落、同行数量或解释维度一律是 `NO_MATERIAL_UTILITY`。
局部 `UNKNOWN` 和 `BOUNDED` 不影响其他维度继续形成当前最佳判断。

### 5.1 报告前：把经验编译为研究议程

1. 由报告用途（`COMPANY_JUDGMENT_ONLY` 或 `INVESTMENT_DECISION`）、公司、信息截止日和报告 ID 建立合同。
2. 刷新 handoff generation，读取 `RESEARCH_AGENDA`。它可以包含官方证据范围、紧凑的 `IndustryUnderwritingContext`、最多三个公司决定性问题、已升格但仍需本公司验证的机制提示、正式准入的窄方法提示和停止规则。三个决定性问题约束本公司深挖重点，不是行业认知容量上限。
3. 逐条验证来源、责任单元、客户/竞争响应、单位经济、现金转换和资本边界。行业机制若只有 `NOT_EVIDENCED`，只能产生取证任务，不能成为公司事实、中心路径或估值参数。
4. 若方法学习改变了本轮的 source gate、状态向量、反方、信号、计量合同或停止规则，必须在冻结前记录实际新值，并由独立 reviewer 复读；没有真实字段改变则不能称为迁移。

### 5.2 报告中：先公司判断，再投资增强

`JUDGMENT_SYNTHESIS` 只允许读取本公司、同一 cutoff 的正式判断内核：账本状态、FJ、财务驱动桥、资本配置事件、中心判断、洞察和反方审阅。它不能读取结果、价格、仓位或投资动作。

公司判断必须沿以下传播链闭合，缺任何一段都保留 `UNKNOWN` 或降低结论范围：

```text
行业/客户状态
  -> 竞争与产品机制
  -> 销量、价格、组合、成本和组织执行
  -> 营运资本、资本开支、融资与现金来源
  -> 正常盈利、owner cash、资本回报和永久损失
```

有边界的 `EnterpriseUnderwritingEpisode` 可以先生成 `valuation-route request` 和研究处理：说明应采用哪种价值路线、哪些能力可进入基准、哪些只进入情景或不应付费。这不要求 Comparative 或 `SELECTION_ADMITTED`，也不产生当前价值数字。

数值 `INVESTMENT_ENRICHMENT` 仍须绑定同公司、同 cutoff 的 current-company CJO admission、可用估值输入和当前估值合同。Kernel 已允许 source-bound、独立复核的完整 Episode 取得 current-company `PRIMARY_ADMITTED`，并让 valuation runtime 消费同一价格前路线；不再把 `SELECTION_ADMITTED` 当作整家公司前提。只有当具体主张来自相对因果或选择方法时，该主张才额外要求 `SELECTION_ADMITTED` 及相应方法权限。无论哪条路径，投资增强都不能反过来改写公司判断或选择中心路径。

### 5.3 报告后：把结果变成下一轮约束

结果按 `决策实施 -> 客户/竞争 -> 单位经济 -> 营运资本/现金 -> 资本回报` 分层到期。每一层只更新它所绑定的箭头。结算之后：

1. 原冻结判断保持不可变；
2. 记录企业经济链和研究设计链的双正交 failure locus；
3. learning 权限按主张和样本身份处理：选择/相对因果方法仍要求 `SELECTION_ADMITTED`；可观察 Forecast 只更新校准；完整 Blind Replay 或 Prospective Episode 经独立审阅后可收窄承保经验；Worked Case 不计能力或方法信用；
4. 局部 `NO_PRIMARY` 可训练弃权与测量纪律，但不能关闭其他已承保主张，也不能单独生成路径选择 learning；
5. `HISTORICAL_TEACHING` 只能形成边界，`HISTORICAL_HOLDOUT` 只能评价，`LIVE_SENTINEL` 只能提供未知结果环境的部署校准；
6. 通过 `LNOTE -> method review -> LAPP receipt -> 下一家公司冻结字段` 返回 M4/M7，而不是把旧报告正文复制到下一份报告。

## 6. 三个 handoff 视图的严格契约

| 视图 | 面向报告阶段 | 可以带入 | 必须禁止 |
|---|---|---|---|
| `RESEARCH_AGENDA` | 取证和研究计划 | cutoff-safe 官方证据范围、决定性问题、待验证机制、已准入窄方法提示、缺口和停止条件 | 结果、价格、估值、动作；行业提示不能被写成公司事实 |
| `JUDGMENT_SYNTHESIS` | 公司判断正文和判断审阅 | 本公司 FJ、H-A/H-B、财务驱动桥、资本配置、`UNKNOWN`、反方、诊断边界 | 任何后验 settlement、市场价格、仓位或投资动作 |
| `INVESTMENT_ENRICHMENT` | 判断完成后的投资层 | 公司判断 predecessor、估值路线、价格隐含预期、回报和动作条件 | 无合格 CJO 时启用；用估值反向选择经营路径 |

三个视图都是读取时投影，不是第二份数据库。writer 必须在同一 generation 读取所需视图并保存 receipt；读取后若 prerequisite refresh，必须重新读取。publication completion 再复核视图、CJO 身份、黄金标准和输出目录的绑定。

### 6.1 审阅返回与 reader writer 的隔离

报告审阅后的修复链使用专用 `golden-report-review-return.v1`。它保存完整根因、经济影响、缺失事实、禁止假设、可执行修复和验收标准，并绑定被审候选；dispatcher 依 `DATA_COVERAGE -> acquisition/schema`、`ACQUISITION_MODULE -> acquisition implementation`、`REASONING -> UnderwritingThesis`、`MODEL -> deterministic model`、`WRITING -> reader writer` 路由。开放的材料性上游问题不产生章节目标。

reader writer 不读取该审阅对象。它只读取 `golden-report-reader-brief.v1`：同一 Episode 已经形成的公司判断、已验收确定性结果及普通投资语言的 reader consequence。即使上游修复完成，也只能把验收后的经济结论投影进 brief，不能把原始 finding、状态、schema、对象 ID 或验收面板复制进正文。这样一次审阅首先改变责任模块和经济结论，最后才改变表达。

## 7. 自下而上与自上而下的可行路径

### 7.1 自下而上：公司 -> 行业 -> 宏观

单家公司只产生公司事实和机制候选。行业机制至少要满足现行知识库契约：

- 两个独立 `corporate_group_id` 的支持，或在高度集中且有明确限制时三个独立报告期；
- 至少两个独立公司集团的已结算支持 episode；
- 至少一个 `CONTRADICTS` 或 `BOUNDARY` 已结算 episode；
- 机制陈述、适用条件、反例、必取字段和可用时间均经非作者独立审阅。

升格前的候选只进入下一份报告的“待验证问题包”，状态为 `NOT_EVIDENCED`，不进入模型、概率或价格。只有多个暴露不同的行业共同观察到同一可解释变量，才可形成宏观候选；宏观报告仍必须保留行业异质性和未知边界。

### 7.2 自上而下：宏观 -> 行业 -> 公司

允许的唯一传播路径是：

```text
宏观变量
  -> 行业需求/供给/价格/成本/信用/监管机制
  -> 目标公司具体业务、地区、客户和资本结构暴露
  -> 量价组合、单位经济、营运资本和资本开支
  -> 正常利润、owner cash、价值、回报和永久损失
```

宏观只改变研究问题和情景约束，不覆盖公司一手证据。宏观与公司证据冲突时，输出新的决定性问题或 `UNKNOWN`，不能强迫公司服从宏观叙事。

## 8. 黄金标准与服务效果的验收

所有公司、PIT、行业和宏观报告均按黄金标准验收；“行业摘要”“轻量案例卡”“机制卡”不是低成本替代物。服务效果只看可审计行为是否改善：

1. 是否更早识别责任单元和真正的机制分叉；
2. 是否减少把收入、销量、投产、正 OCF、存活或股价当作因果结果；
3. 是否在关键中间变量缺失时保留 `UNKNOWN`；
4. 是否让经营驱动继续传播到正常盈利、普通股现金、价值和回报；
5. 是否把一次反馈转成不同公司冻结前的真实字段变化；
6. 在盲留出中是否仍能提出可结算分叉，或在证据不足时正确弃权。

这些是过程与迁移指标，不是“报告质量分数”或投资胜率。没有真实成对的 `COMPANY_ONLY / INDUSTRY_MACRO_ENHANCED` 黄金报告、独立盲评和后续经营结果前，不得宣称行业增强产生材料增量；单一案例也不能证明方法有效。

## 9. 当前状态和下一动作

截至 2026-08-29：

- `judgment-generation-handoff.v1`、三视图、Frozen CJO、valuation overlay 和 publication refresh 已具备工程接线；
- Judgment Experience Invocation Loop 已进入 `main`，并完成福莱特结果前经验调用；FY2024 反馈尚未到期；
- 多轮真实训练已经产生局部企业判断和规则修正，但完整方法仍未证明相对公平 Baseline 的稳定材料优势；
- Frozen CJO 的完整 UnderwritingThesis 已进入 `JUDGMENT_SYNTHESIS` 和确定性公司判断读者工件，valuation runtime 也会消费同一对象；真实黄金候选的完整投资报告尚未完成同源产品验收；
- 格力、行业机制发布和正式 BuyBand 的原权限状态不因 V1 设计自动升级。

当前下一动作是选择未见公司运行首个完整 Blind Replay，并在合法 source package、ManagementDecisionLedger 和独立 CJO review 下冻结同一 Episode；随后让一份真实黄金候选消费它，检验报告是否出现材料投资判断改善。Magna 与 CN600585 worked slice 只作教学和 kernel 回归，不宣称 Blind learning。

## 10. 规范依据

- [历史优先的企业判断训练架构](TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md)
- [判断力飞轮](TURTLE_JUDGMENT_FLYWHEEL.md)
- [判断反馈控制面实施规格](../JUDGMENT_FEEDBACK_CONTROL_PLANE_IMPLEMENTATION_SPEC.md)
- [行业机制知识库](../INDUSTRY_KNOWLEDGE_BASE.md)
- [黄金报告双向层级研究路线图](../GOLDEN_REPORT_BIDIRECTIONAL_RESEARCH_ROADMAP.md)
- [黄金报告共同内容契约](../golden_set_v1/COMMON_CONTENT_CONTRACT.md)
