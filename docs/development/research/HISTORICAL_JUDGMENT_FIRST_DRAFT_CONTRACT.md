# 历史训练的判断优先第一稿合同

> 当前裁决：`JUDGMENT_BEFORE_CELLS / UNKNOWN_IS_NOT_DETERIORATION / LOCAL_EVIDENCE_HAS_LOCAL_FORCE`

## 为什么优先修第一稿

系统已经能阻止 `UNKNOWN` 吞掉整家公司，也不再把字段、gate 和审计工件本身当作训练成果。但这还不够。
此前 fresh forecaster 的真实输入只要求“形成最佳判断并局部化未知”，没有约束第一稿如何把局部结果映射到
管理层、正常盈利、owner cash、永久损失和估值方向。结果是 reviewer 虽然最终能纠正错误，第一稿仍容易：

- 先设计很多 cell，再从 cell 拼企业结论；
- 把 `ELSE`、未披露或不可比误写成经营恶化；
- 一个经营或现金 cell 同时下调多个无直接证据的投资轴；
- 结果真实改变 owner cash 或下一研究动作后，又被一个笼统的 `NO_MATERIAL` 抹掉。

这不是证据量不足，而是第一稿生成契约缺少经济语义。继续增加样本只会重复消耗 reviewer。

## 第一稿必须先交付什么

fresh forecaster 在 outcome 封存时先交付：

1. 一段当前整体企业判断；
2. 最重要的三项判断，每项包含机制、最强反方、投资含义和翻转事实；
3. 六轴当前处理：管理层执行、正常盈利、owner cash、永久损失、估值方向和 rank-1 研究行动；
4. 最后才设计少量 outcome cell 检验最重要的不确定性。

三项判断是优先级约束，不是字段分数。写满字段而没有当前立场仍是不合格第一稿。

`UNKNOWN` 不是六轴处理代码。证据不够时也必须说清当前怎么做，例如：

- 该现金流暂不计入 parent owner cash；
- 该新业务只计已实现利润，不计成长溢价；
- 维持永久损失约束，不因未披露而自动收紧；
- 估值方向暂缓，但企业经营判断继续。

因此，过度保守也会留下可由历史结果反驳的处理记录，不能靠 `UNKNOWN` 免费退出。

## Outcome cell 的局部权力

每个 cell 在结果前必须声明 `direct_axes`。它只能更新这些轴；其余轴是精确的
`preserved_axes`，不能重复抄一遍六轴后悄悄改变。

输入先分三类：

```text
LOCAL_UNKNOWN
MEASUREMENT_MISMATCH
VALID_OBSERVATION
```

前两类都只形成局部研究任务，`axis_updates={}`。它们不是负面经营事实，也不授权 coverage 学习。

在有效且可比的输入中：

- `ADVERSE` 必须列出已经观察到的负面经济载体；
- `ADVERSE` 不得是 `ELSE`；
- 数值条件的剩余补集只能是 `NEUTRAL` 或 `MIXED`；
- 一个轴改善不自动改善其他轴，一个轴未知也不取消其他已观察判断。

局部化也不能变成拒绝传导。每个 direct axis 都要写出从该 cell 到投资处理的经济链，每个 preserved axis
也要说明为什么本 cell 没有资格更新它。轴不是越少越安全：收入、毛利、持续费用和经常经营利润若共同
检验管理层与正常盈利，就应预先列入这些轴；只有收入和毛利时，不得把它们当作 normal earnings 的完整替代。

现金链另有一条硬语义：`合并 OCF－合并资本开支` 只能称 `GROUP_CASH_PROXY`。NCI 归属与现金上划能力
未闭合时，最多 `COUNT_CONDITIONALLY`，不能因为数值为正就升级成 parent owner cash。

但“局部”不是“永不传导”。单年、可逆的营运资金波动只更新 owner cash；若必要维持性资本连续吞噬
现金，或主要现金受到材料且结构性的长期上划限制，这已经是普通股股东的永久损失载体。对应 cell 必须
用材料性、持续性和可逆性测试区分 severe 分支，severe 才能同时 `DO_NOT_COUNT + TIGHTEN_CONSTRAINT`。

`valuation_direction` 指相对共同参考状态的内在价值方向，不是正式估值或市场买价。没有价格可以继续判断
经营改善使内在价值向上、向下或不变；缺价格本身不能成为 `WITHHELD` 的理由。

这不是新全局 gate。某个 cell 不合格只要求在 outcome access 前修订该 cell；不会取消公司 episode、其他
判断或其他 cell。

## 结果后必须分开回答三件事

结果后不得再用一个“有用/没用”覆盖所有层级：

1. `REAL_FEEDBACK_TURN`：冻结的经营问题是否得到真实、合同匹配的反馈；
2. `ENTERPRISE_INVESTMENT_TREATMENT`：企业处理是否材料改变；
3. `METHOD_LEARNING_UTILITY`：这种改变是否能归因于一个与公平 baseline 比较过的方法。

owner cash 等五个处理代码发生变化，或 rank-1 研究行动的 `action_family / target_scope / decision_axis`
发生变化，属于材料处理变化。查询措辞、指标精度或文档长度变化不算。

单臂 discovery 可以同时得到：

```text
REAL_FEEDBACK_TURN=COMPLETED
ENTERPRISE_INVESTMENT_TREATMENT=MATERIAL_UPDATE_BOUNDED
METHOD_LEARNING_UTILITY=NOT_APPLICABLE
```

这正是 CN603195 FY2024 的正确语义：owner cash 从直接计入改为条件计入，rank-1 研究资源从新能源转到
核心终端动销；企业处理确实变了，但没有公平 baseline/enhanced，不能声称方法有效。

## 运行时落点

- `scripts/historical_role_isolation.py` 把全文合同写入每个 fresh forecaster packet；
- `scripts/historical_judgment_first_draft.py` 校验第一稿的局部传播边界，并机械编译结果后的三层 verdict；
- 该合同不修改 J2/J3/J4，不授予 CJO、正式估值、BuyBand、报告或投资权限；
- reviewer 继续负责经济判断，但不能用积极或消极措辞覆盖机械可见的处理变化。

下一步验收不是再造一份 synthetic 表格，而是让无父上下文的 fresh forecaster 只读真实 cutoff 前盲包，检查
它的第一稿是否直接避开 `UNKNOWN→负面`、`ELSE→恶化` 和单轴跨轴传播。
