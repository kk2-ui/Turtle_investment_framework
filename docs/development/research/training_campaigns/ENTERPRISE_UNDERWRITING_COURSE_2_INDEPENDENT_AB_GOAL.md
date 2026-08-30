# Goal: 企业承保课程二期 - 行业经验准备与独立 A/B 效用验证

> 状态：`COURSE_2A_READY / COURSE_2B_WAITING_FOR_TRAINING_READY_PACK / METHOD_NOT_VALIDATED`
>
> 前置结论：[课程一期完成审计](ENTERPRISE_UNDERWRITING_COURSE_1_20260829/14_COURSE_1_COMPLETION_AUDIT.md)
>
> 目标：先形成一个可迭代的 `TRAINING_READY` 行业经验包，再验证它与课程方法是否会让未见公司和未见时期的**投资处理**更好，而不是增加研究材料、字段或文字。

## 1. 要回答的投资问题

课程一期已经训练出一条完整的研究顺序，但顺丰的公平 A/B 显示 Enhanced 曾把“增长资本回报尚未证明”错误地下推为“维护后 owner cash 接近零或为负”。同时，课程一期很多 Blind source package 仍偏单家公司，`IndustryFutureThesis` 虽然存在，却未必建立在多公司、多时期行业经验上。因此，课程二期回答两个连续问题：

1. 多公司、多时期行业经验能否形成一个有主路径、反方、异质公司路径、结算来源和下一样本决策的 `TRAINING_READY` Pack？
2. 在相同的历史时点、相同的一手资料和相近研究预算下，使用该 Pack 的训练后研究能否更合理地判断行业未来，以及一家新公司的正常盈利、owner cash、永久损失或价值路线？

这不是预测股价命中率测试，也不是要求 Enhanced 必须更乐观或更保守。`NO_MATERIAL_UTILITY` 与 `ENHANCED_WORSE` 都是有效、可学习的结果。

## 2. Course 2A：先建立行业经验层

Course 2A 先选择一个已有多公司基础的行业，按[行业经验层 V1 设计](../TURTLE_INDUSTRY_EXPERIENCE_LAYER_V1_DESIGN.md)形成版本化 `Industry Experience Pack`：

```text
官方行业与公司证据
  -> IndustryLearningBlock
  -> Industry Experience Pack
  -> 目标公司、目标 cutoff 的 IndustryUnderwritingContext
```

Pack 不复制事实，只引用现有 block、官方行业 observation、机制、worked case、失败/near miss 和反馈。必须通过：

```bash
.venv/bin/python scripts/industry_experience_pack.py <pack.json>
```

并由验证器派生为 `TRAINING_READY`，不得手工填写状态绕过缺口。水泥离线回放目前是合法 `DRAFT`：它证明多公司边界和 archetype 已存在，但缺少同 cutoff 的官方供需、价格、利用率和共同冲击下公司分化，不能直接启动 Course 2B。

Course 2A 的进度不是公司或文件数量。每轮新增样本必须说明它要区分行业主路径与哪个反方、结果 A/B 分别如何改变 Pack，以及哪些判断不受影响。只增加同行、文字或字段而不改变判断和下一样本，不算完成。

## 3. Course 2B：实验对象与角色

只有一个 Pack 达到 `TRAINING_READY` 后，Coordinator 才选择一家**未参与该 Pack 形成、未参加课程一期**、且与顺丰具有不同经济机制的公司和一个历史 cutoff。另预留一个 Pack 冻结后的未见时期。优先选择能同时呈现行业利润池、公司位置、资本/现金责任与竞争或客户响应的案例；不得为了容易结算而只选择单一财务字段。

Coordinator 向两臂提供同一份 cutoff-before 行业与公司一手资料包，并在两份 Episode 都冻结前封存行业结果和公司结果。资料包可以有局部缺口；缺口只限制相应主张，不取消全公司承保。Baseline 直接使用这些原始资料；Enhanced 额外读取由同一资料和冻结 Pack 编译出的 `IndustryUnderwritingContext`。Context 是待检验的方法输出，不是额外事实。

| 角色 | 可见内容 | 不可见内容 |
| --- | --- | --- |
| Baseline Agent | 原始行业与公司资料、通用 `EnterpriseUnderwritingEpisode` 任务定义 | Pack、Context、课程一期工件、训练记忆、Enhanced、结果期资料 |
| Enhanced Agent | 同一原始资料、冻结 Pack 派生的 Context、同一任务定义、下方通用训练记忆 | 课程一期的公司结论、Baseline、结果期资料 |
| Custodian | 两份已冻结 Episode 后的行业与公司结果资料 | 两臂生成过程与任何事后修改 |
| Fresh Reviewer | 两份匿名 Episode、原始资料、冻结 Pack/Context、分层结果反馈 | 先验偏好、作者身份；先独立判断，后读取结果 |

两臂使用同一模型版本、同一工具权限、相近时间/来源预算和相同输出模板；必须在独立、零上下文的会话中运行。两个生成 Agent 不得互相看到产物。每个 Agent 从其任务开始时干净的本地 `main` 建立 linked worktree，只记录该任务的 commit snapshot，不建立另一条长期基线。

## 4. Enhanced 唯一可用的训练记忆

Enhanced 只能额外获得以下通用方法，不获得任何目标公司或课程一期的事实、结论、结果、公司名单或原文：

```text
先写行业利润池和公司位置，再把它们连接到生存、正常盈利、owner cash、
永久损失和价值路线。把成熟核心、增长 cohort 与融资/普通股权利边界分开。

对现金至少区分三件事：
1. OCF 减经济维护资本，代表正常 owner cash；
2. OCF 减全部长期资本投入，代表当前融资/资本配置压力；
3. 增长资本随后产生的回报，决定增长是否应进入价值。

第三项尚未证明，不等于第一项为零或为负。边界、口径或单项数据未知时，
仅降低该项主张的确定性；仍须给最佳当前判断、最强反方、投资处理和翻转事实。
```

该记忆允许改变问题顺序、证据需求、范围和价值路线，但不能充当当前公司的证据或替代一手资料。

## 5. 两臂必须冻结的共同产物

两臂各自输出一个完整 `EnterpriseUnderwritingEpisode` 及不超过两页的投资者读本，至少回答：

1. 行业处于何种结构/周期阶段，利润池怎样变化；
2. 公司在哪个 arena 竞争，真正的客户、成本、渠道、资产或资本责任是什么；
3. 公司为何能或不能生存、适应；
4. 什么可以作为正常盈利和 owner cash 的合理范围，哪些增长不进入基准；
5. 最可能的永久损失路径、最强反方和会翻转判断的事实；
6. 应采用或排除哪种价值路线，以及价格前的投资处理。

`UNKNOWN`、边界不连续或无法唯一映射的字段必须局部表达；不得把它们改写成整家公司 `NO_JUDGMENT`。也不得把收入、投产、并购或一个 OCF 数字直接写成行动成功、客户吸收或普通股 owner cash。

## 6. 结果后审阅与裁决

两份产物冻结后，Custodian 才可读取预先封存的结果资料，并给出两份不能混合的反馈：

1. **行业层**：需求、供给、竞争、价格、成本、监管和利润池，以及不同 archetype 是否按预期分化；
2. **公司传导层**：目标公司的暴露、适应、盈利、现金、资本回报、永久损失与价值路线。

单家公司结果不能结算行业主张。Fresh Reviewer 先比较两臂在 cutoff 时的证据与推理，再分别裁决行业路径和公司传导，最后裁决整体投资处理：

- `ENHANCED_MATERIALLY_BETTER`：Enhanced 对正常盈利、owner cash、永久损失或价值路线至少一项作出**有证据的材料性改善**，例如正确排除了不可持续收益、避免把普通股不可得现金当 owner cash、或在不牺牲核心风险识别下收窄同口径经济范围；
- `NO_MATERIAL_UTILITY`：只有信息量、同行数量、措辞或不影响投资处理的差异；
- `ENHANCED_WORSE`：Enhanced 引入了不被资料支持的乐观/悲观推断，遗漏更强的永久损失机制，或把局部未知扩大为错误的公司级结论；
- `INCONCLUSIVE_DATA`：结果资料无法区分两臂，且该缺口可能改变投资处理。

评审必须说明经济影响、缺失事实、禁止的假设、可执行的改进和下一轮接受条件；根因归类为 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL` 或 `WRITING`。更多文字、字段、收据或更谨慎的语气一律不构成效用。

一次未见公司 `ENHANCED_MATERIALLY_BETTER` 只使 Pack 达到 `TRANSFER_CANDIDATE`。还必须在 Pack 冻结后的未见时期取得独立材料性效用，才可讨论 `RELEASED`；之后仍需不同机制复制，才能讨论更一般的方法能力。任何裁决均不自动产生 CJO、正式估值、BuyBand、黄金报告发布或投资权限。

## 7. 交付与停止条件

本 Goal 的交付仅包括：

- Course 2A 的 Pack manifest、验证结果、独立准备度审阅和下一样本决策；
- coordinator 的 cutoff-before 行业/公司资料包与双层结果封存说明；
- 两份冻结 Episode 和投资者读本；
- custodian 的行业结果与公司传导结果反馈；
- fresh reviewer 的匿名 A/B 裁决与一页投资者读出；
- 一份只记录材料性方法修订的简短学习说明。

除一个只引用现有对象的 Pack manifest 外，除非实验暴露现有 `IndustryLearningBlock`、`IndustryUnderwritingContext` 或 `EnterpriseUnderwritingEpisode` 无法表达某项材料性投资判断，否则不新增事实库、控制层、字段采集框架、比较准入或报告流水线。若 Pack 因 `DATA_COVERAGE` 或 `ACQUISITION_MODULE` 保持 `DRAFT`，先修复可复用行业采集和样本覆盖；若 Course 2B 为 `NO_MATERIAL_UTILITY` 或 `ENHANCED_WORSE`，停止扩样，先修正被指出的 `REASONING` 或 `MODEL`。
