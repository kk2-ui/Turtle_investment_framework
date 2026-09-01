# 中国中免渠道责任实验：课程读出

> 状态：`FRESH_CODEX_PAIR_COMPLETED / ENHANCED_WORSE`
>
> 总方法状态：`METHOD_NOT_VALIDATED / TRANSFER_NOT_VALIDATED`
>
> 权限：无 CJO、正式估值、BuyBand、黄金报告发布或投资权限。

## 投资者学到了什么

中国中免的 cutoff 前最佳当前判断不是“免税高毛利所以是永久特许权”，也不是“机场租金和库存
增长所以公司不可承保”。两臂都形成了更有用的中间结论：公司已有三亚、首都机场和上海机场等
真实经营入口，采购整合、商品运营和政策执行构成可观察的适应能力；但经营权期限、租金与保底、
客流到购物转化、库存周转、维护投入和少数股东索取权决定利润能否变成普通股现金。

局部缺口没有吞掉公司判断。两臂都判断近期生存较强，识别成熟渠道、新并表渠道和建设项目，
保留经营权丧失/重定价、客流与政策冲击、库存跌价、商誉与建设资本无法回收等永久损失路径。
这说明 judgment-first Baseline 已能完成非防御性的完整 Episode；它没有因为 owner cash 不能精确
拆分而拒绝判断整家公司。

## 训练干预为何产生负效用

本次 Enhanced memory 没有改善投资处理。Baseline 已自行完成渠道期限、消费者吸收、租金、库存、
少数股东和普通股现金的责任匹配；Enhanced 的额外结构主要重复这些内容。更糟的是，Enhanced 在
缺少跨期吸收、渠道租金和责任后现金证据时，把 `mature_existing_channels` 从 Baseline 的
`CONDITIONALLY_UNDERWRITE` 提升为 `UNDERWRITE`，并写入正常化基准。

这是有经济后果的提前给信用，不是“更果断”的优点，也不能由更多 caveat 抵销。因此正式公平
配对裁为 `ENHANCED_WORSE / REASONING`。这说明该显式渠道 memory 没有增量价值且可能诱发过度
纳入；它不说明完整 Episode 或判断优先宪法无效。Baseline 已经内生掌握该处理，继续重复注入
只是在测试共同能力。

## 正式运行状态

Baseline 与 Enhanced 分别由两个 `fork_turns=none` fresh Codex 子 Agent 生成，第三个 fresh-context
reviewer 在结果封存状态下比较。两份原始响应均通过完整合同绑定，并经默认 Codex 子 Agent 入口
固化为 `TRAINING_EPISODE_COMPLETED / CODEX_FRESH_SUBAGENT`。

此前一次显式 Anthropic API 尝试收到 401；它只证明该可选 provider 凭据不可用，不是训练阻断，
也不否定已经完成的 fresh Codex 配对。后续 Turtle 训练默认不再探测或调用外部 API；只有用户
明确指定 provider 时才走该路径。

## 方法处置与下一轮研究行为

1. 退休 `01_CHANNEL_CONTRACT_AND_CASH_RESPONSIBILITY_TREATMENT.md` 作为本轮增量 Training Memory。
   其正确要求已被 Baseline 掌握；负效用来自 Enhanced 没有遵守其中的跨期吸收与现金条件，
   不是规则文本要求把单期规模升级为基准。
2. 不读取本案 outcome 为 Enhanced 寻找事后理由；本轮没有结果前正向材料候选。
3. 停止用“当前 judgment-first Baseline + 通用风险 memory”验证整体训练。该比较只测 memory 的
   边际价值，而 Baseline 本身已经消费判断优先宪法和完整 Episode 目标。
4. 下一阶段验证整体训练时，预先冻结普通企业研究 Baseline 与 judgment-first 完整 Episode 方法；
   两臂使用同一中性事实、cutoff 和相近预算，只看是否纠正材料性企业判断。
5. 新课程不再增加通用 memory。只有真实 Blind 反馈暴露当前 Baseline 的材料错误时，才把该错误
   写成对称推理练习：既说明何时降级，也说明什么正面经营载体足以获得条件信用。

## 防御性写作裁决

- `UNKNOWN` 没有扩散为整家公司拒答；这一严重问题继续保持已修复状态。
- Baseline 的条件性处理不是机械悲观：它承认成熟渠道和适应能力，同时不预支未拆分现金。
- Enhanced 的问题不是不够保守，而是用 `UNDERWRITE` 提前承认证据尚未支持的基准资格。
- 后续不得把更低盈利、更长风险清单或更多条件计作进步；真正进步必须改变同口径正常盈利、
  owner cash、永久损失或价值路线，并由目标公司事实支持。

## 当前冻结状态

```text
FRESH_CODEX_PAIR = COMPLETED
PREOUTCOME_MATERIALITY = ENHANCED_WORSE
ROOT_CAUSE = REASONING
CHANNEL_RESPONSIBILITY_MEMORY = RETIRED_AS_INCREMENTAL_TREATMENT
OUTCOME_READ_AUTHORIZED = NO
METHOD_VALIDATED = NO
TRANSFER_VALIDATED = NO
```
