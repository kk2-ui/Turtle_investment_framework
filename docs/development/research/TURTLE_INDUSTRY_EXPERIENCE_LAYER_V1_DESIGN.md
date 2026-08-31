# Turtle 行业经验层 V1 设计

> 状态：`IMPLEMENTED / CEMENT_PACK_TRAINING_READY / COURSE_2B_NO_MATERIAL_UTILITY / COURSE_2C_COMPANY_TRANSMISSION_MATERIALLY_BETTER / COMPACT_DECISION_MEMORY_IMPLEMENTED / TIME_AXIS_NOT_STARTED / INDUSTRY_PATH_CAPABILITY_NOT_VALIDATED`
>
> 目的：先把多公司、多时期的行业经验建成可迭代上游资产，再让公司训练样本调用、检验并反向修订它。
>
> 当前实现包含版本化 manifest、官方行业原始来源包、观察 ledger、Context 编译器和验证器；没有新增事实库，也没有把 Pack 接入正式训练 runtime。

## 1. 核心决定

行业前景判断不能在研究单家公司时临时生成。正确顺序是：

```text
官方行业与公司证据
  -> 多公司、多时期 IndustryLearningBlock
  -> 版本化 Industry Experience Pack
  -> 目标公司、目标 cutoff 的 IndustryUnderwritingContext
  -> EnterpriseUnderwritingEpisode 内的 IndustryFutureThesis
  -> 行业结果 + 公司分化结果
  -> 新样本选择与下一版 Industry Experience Pack
```

因此：

- `IndustryFutureThesis` 是一次公司承保任务的下游判断，不是行业经验库；
- 单家公司可以验证自身暴露、适应和经济传导，不能独自结算行业需求、供给、竞争或利润池；
- 行业经验先通过多公司和多个结构时期形成，再投影给公司；
- 新公司样本的价值在于检验已有行业认识在哪里成立、失效或需要新增 archetype；
- 结果反馈只追加新版本，不覆盖旧 cutoff 下的判断。

## 2. 五层对象只各做一件事

### L0：证据层

继续使用现有官方行业统计、监管和协会材料、公司披露、生命周期记录及已验证 observation。这里保存事实和可用时间，不保存跨公司结论。

### L1：IndustryLearningBlock——行业学习工作台

现有 `IndustryLearningBlock` 是行业经验的基础训练单位：

```text
industry × mechanism-defined arena × structural epochs
× company archetypes × longitudinal episodes
```

它负责保存：

- 客户任务、价值链、供需、竞争、资本和监管环境；
- cutoff-by-cutoff 的行业 epoch 与公司风险集；
- 不同公司 archetype、生命周期、失败、退出和 near miss；
- 同一外部环境下不同公司的选择、适应与结果差异；
- 条件化机制、break conditions、证据上限和下一样本问题。

它不直接给目标公司估值，也不把同行平均值写成目标公司事实。

### L2：Industry Experience Pack——行业经验的版本化发布清单

`Industry Experience Pack` 不新建事实库。它是一个版本化 manifest，引用已经存在的 `IndustryLearningBlock`、官方行业 observation、经审阅机制、worked case、反例和结果反馈。

每一版只回答：

1. 当前最可信的行业结构和利润池判断是什么；
2. 最强竞争解释是什么；
3. 哪些公司 archetype 走出了不同路径，原因是什么；
4. 哪些关系已被支持、只能条件化使用、已经被反例收窄或废弃；
5. 下一条最有信息价值的公司或时期样本是什么；
6. 本版的 `knowledge_cutoff_at`、适用范围和不能支持的主张是什么。

Pack 只保存引用、综合、边界和版本变化，不复制底层事实全文。G3 最终冻结的 `Industry Experience Pack v1` 是成熟发布版；训练阶段可以先存在 `DRAFT` 和 `TRAINING_READY` 版本，不必等到 G3 才开始积累。

### L3：IndustryUnderwritingContext——面向目标公司的截止日投影

现有 `IndustryUnderwritingContext` 从某一版 Pack 及其底层对象，按目标公司和 cutoff 编译：

- 客户任务和价值链；
- 结构 epoch；
- 需求、供给、竞争、监管及利润池迁移；
- 机制角色同行、异质公司路径和 near miss；
- 目标公司需要独立验证的暴露、适应、现金和资本问题；
- 行业主路径候选、最强反方和翻转观察。

它是只读上下文，不是目标公司结论。`BOUNDED` 可以继续公司研究，但不能冒充行业能力已经验证。

完整 Context 保留给编译器和研究者，不再默认整份交给 Enhanced Agent。训练输入先经 `scripts/industry_experience_pack.py` 压缩为 company-fact-free 的五段 `TRAINING_MEMORY`：行业主路径、最强反方、公司分化机制与参考类别、目标公司独立验证问题、反转观察。这样保留行业经验的决策价值，同时避免把目标公司事实、证据引用和重复候选路径当成“学习”。

### L4：IndustryFutureThesis——公司承保中的方向性判断

`EnterpriseUnderwritingEpisode` 在行业训练 arm 读取由冻结 Context 编译的精简记忆，再用目标公司一手证据选择最可能的行业 regime，并完成：

```text
行业利润池变化
  -> 目标公司的具体暴露与适应
  -> 正常盈利和 owner cash
  -> 永久损失与价值路线
```

同行事实只能支持 reference class，不能直接建立目标公司的客户、成本、现金或竞争事实。

## 3. Pack 的成熟状态

状态用于说明用途，不构成公司报告的全局阻断门。

| 状态 | 已经具备 | 可以做什么 | 不能宣称什么 |
|---|---|---|---|
| `DRAFT` | 初始价值链、epoch、公司风险集和待验证问题 | 指导采集和补样 | 行业方向或迁移能力 |
| `TRAINING_READY` | 四类独立公司路径、多时期证据、主路径、反方、near miss 与结果测量规则 | 生成训练用 Context，开展 Blind 公司训练 | 方法有效或行业能力已验证 |
| `TRANSFER_CANDIDATE` | 在未见公司或未见时期出现一次材料性效用信号 | 进入复制验证 | 稳定迁移或报告先验 |
| `RELEASED` | 不同公司轴和时间轴均完成独立复制，反例和适用边界保留 | 作为受控行业经验进入正式报告研究 | 覆盖目标公司证据或直接提供估值参数 |

`TRAINING_READY` 不按“文件数量”判定，而按经济角色覆盖：

- 至少一条行业中心路径；
- 至少一条不同经济结构的公司路径；
- 至少一条失败、退出、困境或明确 near miss 路径；
- 至少一组同一外部冲击下不少于四家公司的不同响应或责任边界，并同时绑定官方行业观察与公司证据；
- 至少两个结构时期或一个可结算的未来窗口；
- 主判断、最强反方、break conditions 和结果测量来源均已冻结。

同一公司多个 cutoff 可以贡献时间学习，但不能冒充多个独立公司路径。两三家方便取得的同行横截面不能自动满足以上角色。

## 4. 训练样本如何补充

不按随机公司数量扩充。每轮只选择最可能改变行业判断或公司处理的样本，优先级如下：

1. 能区分行业主路径与最强反方的公司或时期；
2. 当前缺失的 archetype、价值链位置、资本结构或客户结构；
3. 失败、退出、被收购和幸存者偏差反例；
4. 同一冲击下与现有样本反应不同的公司；
5. 能结算需求、供给、竞争、利润池或公司适应传导的后续窗口。

新增样本必须预先写明：它要区分什么、若结果 A/B 出现分别怎样修改 Pack、哪些旧判断不会因此改变。回答不了这三个问题的样本不进入本轮。

## 5. 一轮完整迭代

```text
IE0  FRAME
     定义客户任务、经济 arena、价值链和投资相关时域

IE1  BUILD
     冻结行业风险集、structural epochs、公司 archetypes、失败与 near miss

IE2  SYNTHESIZE
     形成 Pack vN：行业主路径、利润池、最强反方、break conditions、抽样议程

IE3  TRANSFER
     为未见目标公司编译 cutoff-safe Context，生成完整 EnterpriseUnderwritingEpisode

IE4  SETTLE
     分开结算行业 regime/利润池与目标公司的暴露/适应/经济传导

IE5  REVISE
     将反馈归为 SUPPORT、NARROW、BREAK、NEW_ARCHETYPE 或 ACQUISITION_GAP，发布 Pack vN+1

IE6  REPLICATE
     在不同公司或不同结构时期复验；不以当前 Agent self replay 代替认知隔离
```

每一轮必须改变至少一项：行业主判断、反方权重、适用条件、公司 archetype、研究问题、测量方式或下一样本选择。只有新增文字、同行或字段而没有判断变化，不算行业经验迭代。

## 6. 结果结算必须分两层

### 行业层结算

行业主张只能由行业统计和多家公司共同结果结算，包括：

- 需求和供给是否按预期变化；
- 竞争、价格、成本和监管如何移动利润池；
- 不同 archetype 是否出现预期分化；
- 主路径与最强反方哪一个获得更强支持。

单家公司年报不足时，状态是“行业层尚未结算”，不能把公司结果外推为行业正确或错误。

### 公司传导层结算

目标公司结果用于结算：

- 它是否真的暴露于该行业路径；
- 管理层适应是否被客户、单位经济和现金吸收；
- 正常盈利、owner cash、永久损失及价值路线处理是否合理。

公司传导正确不等于行业判断正确；行业判断正确也不等于目标公司一定受益。

## 7. 行业资产成熟与 Agent 能力验证不得混称

需要分别回答两个问题：

1. **行业经验资产是否成熟？** Pack 是否包含多公司、多时期、反例、主路径、最强反方、break conditions 和可追溯证据。
2. **Agent 是否学会使用它？** 面对未见公司和未见时期，使用 Pack 的 Agent 是否比同证据 Baseline 做出材料性更好的行业路径、公司暴露、正常盈利、owner cash、永久损失或价值路线判断。

最终能力验证需要两个正交轴：

- 公司轴：未见公司；
- 时间轴：冻结后未见时期。

只有 Context 更长、行业段落更多或同行数量增加，一律不构成能力提升。

## 8. 与现有系统的关系

本设计复用而不替代：

- `IndustryLearningBlock`：多公司、多时期学习工作台；
- `IndustryUnderwritingContext`：目标公司、目标 cutoff 的派生读模型；
- industry mechanism cards：经跨样本复验后可检索的条件化机制；
- `IndustryUnderwritingContext Utility Review`：判断上下文是否改变材料性投资处理；
- `EnterpriseUnderwritingEpisode / IndustryFutureThesis`：公司最终拥有的方向性判断；
- G3 `Industry Experience Pack v1`：经过双轴验证后的正式冻结版本。

不新建第二套事实数据库，不复制公司证据，不改变 J0--J4、Forecast 或 Comparative 的权限。Comparative 只在主张相对因果时使用，不阻断行业经验积累。

## 9. 对课程二期的建议调整

课程二期不应直接从“选择一家陌生公司做 A/B”开始。建议拆成两个连续阶段：

### Course 2A：行业经验层准备

选择一个已有多公司基础的行业，先把现有 block、行业 observation、机制、反例和结果反馈整理为 `TRAINING_READY` Pack，并由独立 reviewer 检查主路径、反方、公司异质性和时间边界。

水泥、家电或快递可以作为设计回放，但因为已有结果和模型记忆，只能验证对象关系和工作流，不能证明能力。

### Course 2B：认知隔离验证

选择未参与 Pack 形成的目标公司和后续时期：

- Baseline 使用相同原始 cutoff-before 行业与公司证据；
- Enhanced 额外读取由冻结 Pack 与目标 cutoff Context 编译的精简行业决策记忆；完整 Context 只作编译输入；
- 两臂使用相同模型、工具、预算和 Episode 输出；
- 结果后分别裁决行业路径和公司传导，再裁决投资处理是否材料性改善。

若 Enhanced 只复述 Pack、忽略目标公司反证或更加防御性，判为 `ENHANCED_WORSE`。若 Pack 只增加解释而不改变材料性判断，判为 `NO_MATERIAL_UTILITY`。

## 10. 实施顺序

1. 五层职责与 Pack 成熟状态已经冻结在本文；
2. `schemas/industry_experience_pack_v1.schema.json` 与 `scripts/industry_experience_pack.py` 已实现；
3. 水泥 V1 离线回放已经验证引用、时间角色、版本边界和反馈方向，并保留为 `DRAFT`；
4. Course 2A 已通过可复用官方行业 acquisition、五家公司共同冲击比较和机械 Context 编译形成水泥 V2 `TRAINING_READY` Pack；
5. Course 2B 已把冻结 Pack/Context 接入上峰水泥未见公司轴的认知隔离合同；结果为 `NO_MATERIAL_UTILITY`；
6. Course 2C 在祁连山得到公司传导 `ENHANCED_MATERIALLY_BETTER`，但行业路径仍为 `NO_MATERIAL_DIFFERENCE`，因此只构成公司组件方法的单样本 `TRANSFER_CANDIDATE`；
7. 已实现精简行业决策记忆编译器；它是下一轮公平 A/B 的受控输入，不回写 2B/2C 历史合同；
8. 只有行业路径在未见公司或未见时期出现材料性改善并完成复制，才讨论行业能力形成。

在 Pack 达到 `TRAINING_READY` 前，不修改正式训练 runtime，也不启动 Course 2B。

## 11. 当前水泥裁决

水泥 V1 `IEP:CN:CEMENT_LISTED:2014_2018:REPLAY:V1` 继续保留为声明和派生状态均为 `DRAFT` 的历史判断。它准确记录了当时的四项缺口，不因后续证据而被覆盖。

水泥 V2 `IEP:CN:CEMENT_LISTED:2014_2018:TRAINING:V2` 已补入：

- 工信部 2017 年上半年水泥产量、均价、收入、利润、利润率和过剩状态；
- 国务院新增熟料约束、错峰、联合重组和集中度政策机制；
- 海螺、天山、福建水泥的销量—利润—现金分化；
- 华新并购和冀东重组的责任边界断点；
- 重新编译的 `READY` Context、中心路径、最强反方、双层结算和下一样本决策。

验证器对 V2 派生 `TRAINING_READY` 且缺口为空。当前最可信方向是需求量近乎横盘下的价格/供给纪律驱动利润池恢复，最强反方是低基数、阶段性错峰和未解决过剩令恢复不可持续。详细证据、公司分化和权限边界见 `CN_CEMENT_2014_2018/64_industry_experience_training_ready_review.md`。

这完成的是 Course 2A 上游资产，不是 Agent 能力验证。Course 2B 的上峰水泥公司轴已经完成，但 Enhanced 与 Baseline 对行业路径和公司传导均无材料差异；Pack 追加独立 `COMPANY_HOLDOUT / NO_MATERIAL_UTILITY` review 后仍派生为 `TRAINING_READY`。行业路径的公司轴正结果、时间轴、`RELEASED` 与 Agent 行业判断能力均未验证。

Course 2C 的祁连山留出进一步表明：Enhanced 对成熟核心、会计控制边界、生命周期 cohort 与资本责任的公司传导显著更好，但两臂的行业主路径仍无材料差异。因此当前有效信号属于公司组件化承保，不等于行业前景判断能力。精简行业决策记忆正是针对这个分层结果：行业层只提供高密度先验和可证伪问题，目标公司层必须用组件证据穿透至正常盈利、owner cash、永久损失和价值路线。

本次负结果的 `MODEL` 修订只面向未来训练合同：Episode 组件必须显式说明是否进入基础/条件正常盈利与 owner-cash 范围、融资压力、永久损失和价值路线，并冻结晋级与撤销测试。`DATA_COVERAGE` 的维护资本、规范化营运资本、房地产 OCF、增长 cohort 和区域量价/利用率缺口留待未来重新预注册前先修可复用 acquisition；本轮不追加样本或时间轴。

## 12. 精简行业决策记忆 V1

编译命令：

```bash
.venv/bin/python scripts/industry_experience_pack.py PACK.json \
  --context TARGET_CUTOFF_CONTEXT.json \
  --decision-memory-output COMPACT_MEMORY.md
```

编译器只接受机械验证为 `TRAINING_READY` 或更高状态的 Pack，并要求 Pack 行业身份与 Context 一致、Pack 知识截止不晚于目标 cutoff。输出不包含目标公司身份、公司事实、同行身份、证据引用、估值参数或投资动作；`BOUNDED` Context 仍可编译，因为缺少可选同行不应阻断公司判断。

V1 解决的是输入结构和泄漏边界，不是效用证明。下一轮必须预注册一个未见公司或未见时期，让 Baseline 与 Enhanced 使用相同原始证据和预算；Enhanced 只额外读取这份精简记忆。只有它使行业主路径、最强反方、公司暴露或下游投资处理出现可复核的材料改善，才计为学习。
