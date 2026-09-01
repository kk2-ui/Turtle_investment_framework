# Course 2C 水泥未见公司认知隔离 A/B 预注册

> 状态：`FROZEN_BEFORE_ARM_EXECUTION`
>
> 公司 / cutoff：`CN:600720` 祁连山 / `2018-04-30T23:59:59+08:00`
>
> 检验对象：水泥 Pack V3 的多公司行业经验及其派生 Context，能否在经 Course 2B 修订的组件决策接口下，改善未见公司的行业前景、正常盈利、owner cash、永久损失和价值路线判断。

## 样本与问题

祁连山不属于 Pack V3 的五家公司，也未参加 Course 1 或 Course 2B。它是西北区域水泥/商品混凝土经营者，包含一个运行中的成熟网络、已完成收购和已投产生产线、尚未投产或终止项目，以及酒钢宏达的合并边界变化。这样可以检验行业利润池判断是否会被正确传导到公司，而不是只考察一个公司级财务字段。

两臂要在 cutoff 当时回答：

1. 价格与有效供给纪律驱动的全国利润池恢复，是否比“低基数/区域扰动的短暂反弹”更能解释下一阶段；
2. 西北 delivered market 的量、价、成本、营运资本和债务，能否把该行业路径传导为可重复的正常盈利与 owner cash；
3. 成熟核心、具名收购/投产 cohort、未投产或终止项目和会计并表边界，应各自怎样进入融资压力、永久损失与价值路线；
4. 在缺项目级销量、OCF、维护资本和独立投入资本时，哪些资本回报主张必须保持 conditional 或 excluded；
5. 最强反方和会使价格前研究处理翻转的观察是什么。

明确排除：Pack 五家公司、Course 1/2B 的公司结论、FY2018 及以后年报/结果、市场价格、回报、估值数值和投资动作。

## 公平性与效用标准

Baseline 与 Enhanced 使用相同公司、cutoff、共同源包、Episode schema、模型、reasoning 配置、任务预算和反馈时钟。Enhanced 仅额外读取 Pack V3 派生的 `IndustryUnderwritingContext` 与通用训练记忆；二者均为 `TRAINING_MEMORY`，不能被当作祁连山事实写入 `evidence_trace` 或 `existing_object_refs`。

Enhanced 仅在以下至少一项以目标公司证据实现材料改善时可能胜出：

- 区分全国价格/供给路径与西北 delivered market 的真实传导，而不是把全国价格当公司售价；
- 在名义产能稳定而利润率波动的资料中，把价格/成本周期与扩产增长分开；
- 对成熟核心形成有边界的正常 owner-cash 处理，同时不把全部长期资产支出或未知增长回报机械等同维护资本；
- 把具名收购/投产 cohort、未投产/终止项目和会计并表边界分开，避免把责任单元利润当成增量项目 ROIC；
- 使 component_decisions 实际改变正常盈利、owner cash、融资压力、永久损失或价值路线，而不只是增加条目或语句。

更多字段、文字、同行、`UNKNOWN` 或更谨慎的措辞不构成效用。无证据地承保价格恢复、把责任单元利润升级为项目回报、将局部不可测量扩大成公司级拒判、或把会计边界当资本配置，均可导致 `ENHANCED_WORSE`。

## 开封与裁决

两份完整 Episode 均通过 v2 合同绑定并被冻结后，隔离 Custodian 才可读取 FY2018—FY2022 官方结果并分成行业路径与公司传导两层反馈。Fresh Reviewer 先匿名比较两臂的 cutoff 推理，后读取结果，最后揭示 arm 映射。裁决仅可为：

- `ENHANCED_MATERIALLY_BETTER`
- `NO_MATERIAL_UTILITY`
- `ENHANCED_WORSE`
- `INCONCLUSIVE_DATA`

单一正结果最高把水泥 Pack 推进到 `TRANSFER_CANDIDATE`；本实验不产生估值、BuyBand、CJO、黄金报告或投资权限。
