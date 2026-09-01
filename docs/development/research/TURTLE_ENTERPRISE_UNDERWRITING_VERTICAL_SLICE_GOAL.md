# Goal：企业投资承保纵向切片 V1

> 状态：`IMPLEMENTATION_COMPLETE / PENDING_INTEGRATION`
>
> 实现基线：`main@542bec1`
>
> 上位设计：[Turtle 企业投资承保系统 V1](TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md)

## 1. Goal

已从干净 `main@542bec1` 创建 linked worktree，实现一条可由投资者直接阅读的麦格纳式企业承保纵向切片：

```text
处境与行业周期/结构
-> 公司位置与适应
-> 生存和融资
-> 正常盈利与 owner cash
-> 永久损失
-> 价值路线
-> 价格前研究处理
-> CJO / valuation / Golden Report 同源投影
```

本 Goal 的完成物不是新控制平面，而是一条真实、连续、公司特定的投资判断。

U1 已交付 Magna 与 CN600585 worked cases、CN600585 投资者读本、同源 CJO candidate／valuation-route request／Golden Report handoff、定向测试和独立产品审阅。它仍只提供 `RESULT_KNOWN_TEACHING_ONLY / WORKED_CASE` 证据：不授予盲测、迁移、当前估值、BuyBand、发布或投资权限。

## 2. 固定范围

### 2.1 两个切片

1. **Magna worked fixture**：只验证困境周期型的推理结构。使用仓库书籍笔记中已经整理的麦格纳材料，不补写新的公司事实，不把书籍案例当中国公司证据。
2. **CN600585 海螺水泥 worked vertical slice**：复用当前仓库的 `TC_CN600585_CYCLE_CAPITAL_CASH_V1.md`、现有官方年报引用、EnterpriseSystemModel/CJO/valuation 能读取的既有对象，形成公司特定承保读本。

海螺切片是 `RESULT_KNOWN_TEACHING_ONLY`，可以训练完整推理和报告消费，不能冒充 Blind Replay、方法迁移、当前估值或买入建议。

### 2.2 允许新增

- 一个最小 `enterprise-underwriting-episode.v1` schema 或等价 typed model；
- 一个组合/编译 adapter，例如 `scripts/enterprise_underwriting_episode.py`；
- Magna 和 CN600585 的 fixture/read model；
- 同源的 CJO candidate、valuation-route request、Golden Report underwriting handoff；
- 定向测试和一份投资者读本；
- 必要的当前文档状态更新。

### 2.3 必须复用

- 现有 source/evidence 与 PIT 语义；
- `EnterpriseSystemModel`；
- `ManagementDecisionLedger`；
- `JudgmentExperienceRecord` / retrieval/invocation；
- Frozen CJO v1 或当前 CJO compiler；
- 当前 valuation routing / overlay；
- 当前 judgment-generation handoff。

禁止复制事实、另建经验卡、另建估值引擎或重写当前 CJO。

## 3. 实现要求

### 3.1 Episode 内容

实现对象必须能表达：

- `decision_frame`；
- `underwriting_route` 与替代路线；
- `situation_model` 及宏观/行业到公司的具名传导；
- `business_position`；
- `survival_case`；
- `adaptation_case`；
- `normalization_case`；
- `permanent_loss_map`；
- `value_route` 及不适用路线；
- `strongest_rival` 与 reversal observations；
- `component_treatments`：`UNDERWRITE / CONDITIONALLY_UNDERWRITE / SCENARIO_ONLY / EXCLUDE_FROM_BASE / CANNOT_BOUND`；
- `existing_object_refs` 与材料证据 trace；
- 价格前 `UnderwritingThesis` 与价格后 `InvestmentTreatment` 的单向边界。

字段名可以按现有代码风格调整，但经济内容不能被状态码和 ID 替代。

### 3.2 同源投影

同一 Episode 必须确定性生成或绑定：

1. 人读优先的 underwriting readout；
2. Frozen CJO candidate 所需的 central path、normal earnings、owner cash、permanent loss、counterargument 和 monitoring；
3. valuation route request，只说明应该用什么路线以及哪些输入可/不可进入，不制造当前价值数字；
4. Golden Report underwriting handoff，报告 writer 不得重新选择一条不同企业故事。

若某现有下游 schema 暂时无法无损表达，输出一个具名 compatibility gap 和最小 adapter 建议；不要新增全局 gate。

已知必查 gap 是现有 numeric `INVESTMENT_ENRICHMENT` 对全局 `SELECTION_ADMITTED` 的要求。U1 不修改该生产权限、不伪造 admission，只验证 valuation-route request 能在无 Comparative 时表达价值路线；若数值 overlay 仍被旧入口拒绝，应把它登记为 U4 的 claim-local admission 改造项，而不是把纵向切片判为失败。

### 3.3 投资者读本验收

CN600585 读本必须直接回答：

- 水泥下行是周期压力、结构毁灭还是二者混合；
- 海螺是否存在即时生存风险，真正长期风险是什么；
- 国内与海外资产、成本改善和扩产怎样影响公司位置；
- 哪些盈利可以正常化，哪些新增资产不能取得信用；
- owner cash 为什么仍需范围处理；
- 哪条路径会造成永久损失；
- 为什么采用资产/EPV/资本回报交叉路线，而不是为产能增长付费；
- 哪些事实会使当前处理上调或下调。

宏观内容只有存在水泥需求、价格、信用或资本传导时才出现。禁止单独写一章泛化 GDP 背景。

## 4. 明确禁止

- 不新增第二套事实数据库、CJO、经验卡、估值引擎或报告流水线；
- 不扩展 E0--E3、J0--J4、H1/H2/V5 或 Comparative 控制；
- 不要求八维全部 observed，不生成八维总分；
- 不把静态 PDF、receipt、validator、字段数量或测试数量写成投资者成果；
- 不以 `UNKNOWN / NO_PRIMARY / MEASUREMENT_MISMATCH` 作为整份读本结论；
- 不输出海螺当前价格、真实 BuyBand、仓位或交易建议；
- 不把 outcome-known worked slice 宣称为能力、迁移或收益验证；
- 不为理论上的输入异常增加 feature flag、迁移框架或兼容包装层。

## 5. 验收标准

### 产品验收

- 独立投资者 reviewer 能用不超过一页复述海螺的处境、生存、正常化、永久损失和价值路线；
- readout 的中心结论不是字段缺口，而是当前最合理的条件性承保处理；
- Magna 与海螺展示同属周期/重资产但结构不同的 near miss，不能把 Magna 结论复制给海螺；
- CJO、valuation request 和 report handoff 不出现互相矛盾的中心路径；
- reader-facing 内容不出现内部 gate、schema、receipt 或权限墙。

### 工程验收

- 输入只引用现有 canonical/read-model 对象或具名研究 fixture；
- 相同输入重复编译结果稳定；
- 价格不能改写 UnderwritingThesis；
- 一个局部 `CANNOT_BOUND` 不会删除其他已承保组件；
- 经验调用只能改变问题、路径或处理，不能成为当前公司事实；
- 定向和相邻回归通过；
- `.venv/bin/python scripts/project_guard.py verify full` 通过；
- `merge-check` 为 READY。

## 6. 交付

至少提交：

- 实现代码和 schema/typed model；
- Magna fixture；
- CN600585 Episode fixture；
- CN600585 投资者 readout；
- CJO / valuation / report 三个同源投影样例；
- 定向测试；
- 实现说明，明确哪些旧对象被复用、哪些只是 compatibility projection；
- 一个独立产品审阅 artifact。

## 7. 完成后下一步

完成 U1 后不要继续扩基础设施。下一 Goal 从五类承保路线中建立 12--20 个 worked case 的课程种子，并选择一个未参与设计的公司/cutoff 运行首个完整 Blind Replay。Blind Replay 结算的是完整承保主张，不是再挑一个容易机械评分的字段。
