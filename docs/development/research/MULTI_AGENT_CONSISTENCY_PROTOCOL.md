# 多 Agent 企业判断一致性协议

版本：`multi-agent-consistency-protocol.v1`  
状态：`CURRENT / EXECUTION_PROTOCOL`

## 1. 目的

本协议解决的问题不是让多个 Agent 写出相似的文章，而是保证多个 Agent
处理的是同一个经济对象，并且每个进入估值或投资结论的字段都能回到同一组
截止日前证据。

此前一次性要求单个 Agent 同时完成公司判断、行业判断、组件权限、正常盈利、
owner cash、永久损失、价值路线、敏感性和严格 Episode JSON，造成大量
`EPISODE_INVALID`。这类失败把判断能力和接口承载能力混在了一起。本协议将
协作拆成窄职责提案、单一裁决和确定性编译三层。

## 2. 核心原则

### 2.1 一主多辅，不是多主共写

多 Agent 可以并行取证、提出机制解释和挑战假设，但只能有一个
`canonical judgment owner` 负责冻结最终判断账本。Agent 数量、相互投票或
文本相似度都不能产生事实或投资结论。

### 2.2 一致性不等于结论相同

必须一致的内容包括：

- 公司身份、责任实体和 information cutoff；
- 共同来源包、证据 ID、字段含义和单位；
- 组件 ID、经济责任边界和允许的处理枚举；
- 正常盈利、owner cash、融资压力、永久损失和价值路线的传导语义；
- 下游 Episode、projection 和 reader bridge 的来源关系。

可以不同、且应保留不同的内容包括：

- 行业主路径和最强反方的相对权重；
- 公司传导是否足够支持 `UNDERWRITE` 或只能 `CONDITIONAL`；
- 哪些证据足以改变当前处理；
- `UNKNOWN` 的范围及其对投资判断的影响。

如果多 Agent 的实质结论被提前统一，系统会失去发现错误和测量训练增益的能力。

## 3. 权限分工

| 角色 | 可提交 | 不可提交 |
| --- | --- | --- |
| Evidence owner | 官方来源、PIT 时间、责任实体、evidence ID/locator | 公司判断、估值参数、行动 |
| Industry analyst | 行业机制、利润池路径、最强反方、公司传导问题 | 把行业观察当成公司事实 |
| Company economist | 组件划分、组件处理、正常盈利/owner cash/永久损失方向、路线绑定、反转条件 | 未有证据的精确幅度、价格、回报、仓位 |
| Challenger | 针对已有主张提出最强竞争解释和可证伪观察 | 重写证据或替换主张 |
| Thesis synthesizer | 基于已接纳判断组织中心路径和监测叙事 | 新增未经接纳的公司事实或经济处理 |
| Canonical owner | 解决冲突、接纳/降级判断、冻结 canonical ledger | 用多数票、文风或方便编译替代证据裁决 |
| Deterministic compiler | 身份/来源/字段/路线检查，生成 Episode、projection 和 reader bridge | 选择组件、补证据、猜敏感性、把 `UNKNOWN` 变成零、生成价格或行动 |

下游对象只能读取冻结的 canonical ledger 或其确定性投影，不能读取各 Agent 的
自由文本草稿作为事实来源。

## 4. 分阶段交付

每个 Agent 提交窄小、可定位的 proposal；同一字段不得由多个 Agent 直接写入
canonical 对象。

```text
共同 case packet
  → J0：身份、组件、问题、证据引用
  → J1：组件经济处理、现金/损失方向、路线、UNKNOWN
  → J2：中心路径、最强反方、监测与反转
  → canonical owner 冻结 judgment ledger
  → deterministic compiler 生成 Episode / projections
```

最小 proposal 只需表达目标字段、建议值、证据和理由：

```json
{
  "target": "components.CORE.normal_earnings_use",
  "proposed_value": "CONDITIONAL_RANGE",
  "evidence_ids": ["E12", "E18"],
  "reason": "核心业务连续，但维护资本口径未闭合"
}
```

Canonical owner 合并时遵循三种处置：

1. 证据支持一方：接纳该值，并保留另一方为被拒绝提案；
2. 证据支持范围而非点结论：接纳 `CONDITIONAL` 或局部 `UNKNOWN`，写明原因、保守处理和下一观察；
3. 身份、cutoff、责任边界或证据权限无法解决：停止该字段的下游投影，输出诊断，不自行猜测。

无需新增一套复杂状态机；使用现有 ledger 状态和结构化 diagnostics 即可记录
`owner`、经济影响、禁止假设、修复动作和验收条件。

## 5. 生产协作与四臂实验的区别

### 5.1 生产协作

生产案例采用“一主多辅”：主 Agent 接收各角色 proposal，维护全局问题树，
完成冲突裁决并冻结唯一 ledger。审阅者检查主张是否由证据和经济传导支持，
但不直接编辑 canonical 对象。

### 5.2 四臂训练

四臂实验采用“四个独立主 Agent”，每个 arm 各自拥有自己的 ledger，但必须
共享完全相同的 cutoff、common source、组件词汇、J0/J1/J2 schema、编译器、
模型和预算。行业记忆与专家纠偏只能改变问题顺序、反方和验证条件，不能带入
目标公司事实或额外字段。

四臂之间禁止在匿名首审前互相看结果、人工对齐结论或用 reviewer 改写某一臂。
实验要比较的是处理差异；必须统一的是协议，不是答案。

## 6. 冲突和失败处理

- **身份冲突**：`MODEL` / material，不能编译；先解决公司、实体或 cutoff。
- **证据冲突或缺失**：`DATA_COVERAGE` / material；局部降级为 `UNKNOWN`，不得补零或引用训练记忆。
- **路线/组件不兼容**：`MODEL` / material；由 compiler 诊断，Agent 重新提交经济语义。
- **JSON 截断或字段格式错误**：`WRITING` / interface failure；保留原始响应，不手拼、不把失败臂改成成功。
- **主张互相矛盾但证据都存在**：由 canonical owner 裁决；无法裁决时保留条件性结论，不做投票。

`EPISODE_INVALID` 只表示当前对象无法进入下游，不表示该 Agent 的投资判断最差。
实验报告必须把结构完成率、诊断归因和实质判断质量分开统计。

## 7. 一致性验收

一个案例只有同时满足以下条件，才可称为“协作一致”：

1. 所有下游对象绑定同一公司、cutoff、sample identity 和 canonical ledger；
2. 每个材料组件只有一个最终处理，或被明确标成局部 `UNKNOWN`；
3. 每条材料 claim 都有允许的 evidence ID、最强反方和反转观察；
4. 正常盈利、owner cash、永久损失和价值路线的组件权限不互相冲突；
5. 同一 ledger 重编译得到相同 Episode/projection；
6. reader bridge 只来自已冻结 Episode，不反向修改判断账本。

这些是经济一致性和可追溯性的最低要求，不是对文风、篇幅或章节数量的要求。

## 8. 与现有实现的关系

本协议使用现有的：

- `scripts/staged_judgment_ledger.py`：ledger 边界、证据、组件和路线验证，以及确定性编译；
- `scripts/report_autonomy_bridge.py`：从 Episode 派生组件 reader bridge；
- `scripts/report_completion.py`：检查 bridge、Episode 和 reader surface 的连续性；
- `EnterpriseUnderwritingEpisode` 及其训练合同：公司的统一经济对象和 cutoff 约束。

本协议不授权真实模型运行、不打开 outcome、不改变估值或投资动作权限。它只规定
多 Agent 如何提交、裁决、冻结和消费判断。

## 9. CN:000541 执行口径

CN:000541 四臂实验执行时：

1. 先冻结一份共同 case packet 和 source index；
2. 每个 arm 依次产生 J0、J1、J2 proposal/ledger，不读取其他 arm；
3. 每个 arm 的 ledger 独立编译并冻结，任何失败留下原始响应和 diagnostics；
4. 第三个 fresh reviewer 只看匿名 compiled outputs，先完成结果前审阅；
5. 在匿名审阅冻结前不读取 outcome，也不人工统一四臂答案；
6. 结果结算和第二个未见公司/时间 holdout 单独验证方法是否真的改善投资判断。

成功标准是“相同协议下可以比较不同判断，并且判断能经结果和 holdout 复验”，
不是“所有 Agent 最后写成同一个答案”。
