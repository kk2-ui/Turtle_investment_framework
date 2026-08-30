# 中国中免渠道责任实验：课程读出

> 状态：`STANDARD_RUNTIME_NOT_COMPLETED / MANUAL_DIAGNOSTIC_ENHANCED_WORSE`
>
> 总方法状态：`METHOD_NOT_VALIDATED / TRANSFER_NOT_VALIDATED`
>
> 权限：无 CJO、正式估值、BuyBand、黄金报告发布或投资权限。

## 投资者学到了什么

中国中免的 cutoff 前最佳当前判断不是“免税高毛利所以是永久特许权”，也不是“机场租金和库存
增长所以公司不可承保”。两份 fresh 草案都能形成更有用的中间结论：公司已有三亚、首都机场和
上海机场等真实经营入口，采购整合、商品运营和政策执行构成可观察的适应能力；但经营权期限、
租金与保底、客流到购物转化、库存周转、维护投入和少数股东索取权决定利润能否变成普通股现金。

局部缺口没有吞掉公司判断。两臂都判断近期生存较强，识别了成熟渠道、新并表渠道和建设项目，
保留经营权丧失／重定价、客流与政策冲击、库存跌价、商誉与建设资本无法回收等永久损失路径。
这说明当前 judgment-first Baseline 已经会完成非防御性的完整 Episode；它没有因为 owner cash
不能精确拆分而拒绝判断整家公司。

## 训练没有带来什么

本次 Enhanced memory 没有改善投资处理。Baseline 已自行完成渠道期限、消费者吸收、租金、库存、
少数股东和普通股现金的责任匹配；Enhanced 的额外结构主要是重复这些内容。更糟的是，Enhanced
在缺少跨期吸收、渠道租金和责任后现金证据时，把 `mature_existing_channels` 从 Baseline 的
`CONDITIONALLY_UNDERWRITE` 提升为 `UNDERWRITE`，并写入正常化基准。这是有经济后果的提前给
信用，不是更果断的优点，也不能由更多 caveat 抵销。

因此本轮手工内容诊断为 `ENHANCED_WORSE / REASONING`。这只说明“渠道期限与现金责任”作为一份
显式增量 memory 没有价值且可能诱发过度纳入；它不说明当前完整 Episode 或判断优先宪法无效。
恰恰相反，Baseline 已经内生完成这项处理，表明继续用同类 memory 与现行 Baseline 比较是在重复
测试共同能力。

## 为什么标准 A/B 尚未完成

标准训练入口的两臂均在四次模型调用后收到同一个 `401 authentication_error: API key is invalid`，
没有产生 `TRAINING_EPISODE_COMPLETED`。两个 `fork_turns=none` Agent 随后生成的草案通过完整合同
绑定 validator，可用于审阅经济内容，但不能替代相同 provider、模型和 runtime 的标准配对。

根因是 `ACQUISITION_MODULE`：当前运行凭据不可用。缺失的是两个由标准入口实际生成的 Episode，
而不是更多公司事实。禁止把 validator 通过、相同 401 或手工草案包装成标准 A/B 已完成；也不为
解决凭据增加新 schema、gate 或 receipt。

## 方法处置与下一轮研究行为

1. 退休 `01_CHANNEL_CONTRACT_AND_CASH_RESPONSIBILITY_TREATMENT.md` 作为增量 Training Memory。
   它的正确部分已被 Baseline 掌握，错误部分会把单期规模提前升级为基准。
2. 不读取本案 outcome 为 Enhanced 寻找事后理由；本轮没有结果前正向材料候选。
3. 停止用“当前 judgment-first Baseline + 通用风险 memory”检验整体训练是否有效。该比较只测
   memory 的边际价值，而 Baseline 本身已经消费了判断优先宪法和完整 Episode 训练目标。
4. 下一阶段若验证整体训练，应预先冻结两个能力版本：公平的普通企业研究 Baseline，与当前
   judgment-first 完整 Episode 方法；两者使用同一中性事实、公司、cutoff 和预算。评分只看
   是否纠正材料性企业判断，不奖励篇幅、谨慎、`UNKNOWN` 或更多风险项。
5. 新课程不再增加通用 memory。只有真实 Blind 反馈暴露一条当前 Baseline 的材料错误时，才把
   该错误重写为对称的推理练习：既规定何时应降级，也规定什么正面经营载体足以获得条件信用。

## 防御性写作裁决

- `UNKNOWN` 没有扩散为整家公司拒答；这一严重问题继续保持已修复状态。
- Baseline 的条件性处理不是机械悲观：它承认成熟渠道和适应能力，同时不预支未拆分现金。
- Enhanced 的问题不是不够保守，而是用 `UNDERWRITE` 标签提前承认证据尚未支持的基准资格。
- 后续不得把“更低盈利、更长风险清单或更多条件”计作进步；真正进步必须改变同口径正常盈利、
  owner cash、永久损失或价值路线，并由目标公司事实支持。

## 当前冻结状态

```text
STANDARD_RUNTIME_PAIRED_TEST = NOT_COMPLETED
MANUAL_FRESH_DIAGNOSTIC = ENHANCED_WORSE
CHANNEL_RESPONSIBILITY_MEMORY = RETIRED_AS_INCREMENTAL_TREATMENT
METHOD_VALIDATED = NO
TRANSFER_VALIDATED = NO
```
