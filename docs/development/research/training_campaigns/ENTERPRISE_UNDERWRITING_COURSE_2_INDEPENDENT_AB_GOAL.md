# Goal: 企业承保课程二期 - 独立 A/B 效用验证

> 状态：`READY_TO_RUN / METHOD_NOT_VALIDATED`
>
> 前置结论：[课程一期完成审计](ENTERPRISE_UNDERWRITING_COURSE_1_20260829/14_COURSE_1_COMPLETION_AUDIT.md)
>
> 目标：验证训练是否会让下一家未见公司的**投资处理**更好，而不是增加研究材料、字段或文字。

## 1. 要回答的投资问题

课程一期已经训练出一条完整的研究顺序，但顺丰的公平 A/B 显示 Enhanced 曾把“增长资本回报尚未证明”错误地下推为“维护后 owner cash 接近零或为负”。因此，课程二期只回答一个问题：

> 在相同的历史时点、相同的一手资料和相近研究预算下，训练后的研究能否更合理地判断一家新公司的正常盈利、owner cash、永久损失或价值路线？

这不是预测股价命中率测试，也不是要求 Enhanced 必须更乐观或更保守。`NO_MATERIAL_UTILITY` 与 `ENHANCED_WORSE` 都是有效、可学习的结果。

## 2. 实验对象与角色

Coordinator 选择一家**未参加课程一期**、且与顺丰具有不同经济机制的公司和一个历史 cutoff。优先选择能同时呈现行业利润池、公司位置、资本/现金责任与竞争或客户响应的案例；不得为了容易结算而只选择单一财务字段。

Coordinator 向两臂提供同一份 cutoff-before 一手资料包，并在两份 Episode 都冻结前封存结果期资料。资料包可以有局部缺口；缺口只限制相应主张，不取消全公司承保。

| 角色 | 可见内容 | 不可见内容 |
| --- | --- | --- |
| Baseline Agent | 资料包、通用 `EnterpriseUnderwritingEpisode` 任务定义 | 课程一期工件、训练记忆、Enhanced、结果期资料 |
| Enhanced Agent | 同一资料包、同一任务定义、下方冻结的通用训练记忆 | 课程一期的公司结论、Baseline、结果期资料 |
| Custodian | 两份已冻结 Episode 后的结果期资料 | 两臂生成过程与任何事后修改 |
| Fresh Reviewer | 两份匿名 Episode、资料包、结果反馈 | 先验偏好、作者身份；先独立判断，后读取结果 |

两臂使用同一模型版本、同一工具权限、相近时间/来源预算和相同输出模板；必须在独立、零上下文的会话中运行。两个生成 Agent 不得互相看到产物。每个 Agent 从其任务开始时干净的本地 `main` 建立 linked worktree，只记录该任务的 commit snapshot，不建立另一条长期基线。

## 3. Enhanced 唯一可用的训练记忆

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

## 4. 两臂必须冻结的共同产物

两臂各自输出一个完整 `EnterpriseUnderwritingEpisode` 及不超过两页的投资者读本，至少回答：

1. 行业处于何种结构/周期阶段，利润池怎样变化；
2. 公司在哪个 arena 竞争，真正的客户、成本、渠道、资产或资本责任是什么；
3. 公司为何能或不能生存、适应；
4. 什么可以作为正常盈利和 owner cash 的合理范围，哪些增长不进入基准；
5. 最可能的永久损失路径、最强反方和会翻转判断的事实；
6. 应采用或排除哪种价值路线，以及价格前的投资处理。

`UNKNOWN`、边界不连续或无法唯一映射的字段必须局部表达；不得把它们改写成整家公司 `NO_JUDGMENT`。也不得把收入、投产、并购或一个 OCF 数字直接写成行动成功、客户吸收或普通股 owner cash。

## 5. 结果后审阅与裁决

两份产物冻结后，Custodian 才可读取预先封存的结果期资料，并按行业/公司位置、盈利、现金、资本回报、永久损失与价值路线给出事实反馈。Fresh Reviewer 先比较两臂在 cutoff 时的证据与推理，再用结果反馈裁决：

- `ENHANCED_MATERIALLY_BETTER`：Enhanced 对正常盈利、owner cash、永久损失或价值路线至少一项作出**有证据的材料性改善**，例如正确排除了不可持续收益、避免把普通股不可得现金当 owner cash、或在不牺牲核心风险识别下收窄同口径经济范围；
- `NO_MATERIAL_UTILITY`：只有信息量、同行数量、措辞或不影响投资处理的差异；
- `ENHANCED_WORSE`：Enhanced 引入了不被资料支持的乐观/悲观推断，遗漏更强的永久损失机制，或把局部未知扩大为错误的公司级结论；
- `INCONCLUSIVE_DATA`：结果资料无法区分两臂，且该缺口可能改变投资处理。

评审必须说明经济影响、缺失事实、禁止的假设、可执行的改进和下一轮接受条件；根因归类为 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL` 或 `WRITING`。更多文字、字段、收据或更谨慎的语气一律不构成效用。

一次 `ENHANCED_MATERIALLY_BETTER` 只产生 `INDEPENDENT_UTILITY_SIGNAL`，还需一个不同机制的复制案例才可讨论 `METHOD_VALIDATED`。任何裁决均不自动产生 CJO、正式估值、BuyBand、黄金报告发布或投资权限。

## 6. 交付与停止条件

本 Goal 的交付仅包括：

- coordinator 的 cutoff-before 资料包与结果封存说明；
- 两份冻结 Episode 和投资者读本；
- custodian 的结果反馈；
- fresh reviewer 的匿名 A/B 裁决与一页投资者读出；
- 一份只记录材料性方法修订的简短学习说明。

除非实验暴露出现有 `EnterpriseUnderwritingEpisode` 无法表达某项材料性投资判断，否则不新增 schema、控制层、字段采集框架、比较准入或报告流水线。若结果是 `NO_MATERIAL_UTILITY` 或 `ENHANCED_WORSE`，停止扩样；先修正被指出的 `REASONING` 或 `MODEL`，再选择下一轮验证。
