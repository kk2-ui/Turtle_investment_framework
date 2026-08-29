# U1：完整企业承保纵向切片的实现说明

U1 没有新增事实库、CJO、估值引擎或报告流水线。它新增的是一个很窄的组合读模型：`EnterpriseUnderwritingEpisode` 将现有来源、企业状态、管理动作、现金边界和价值路线收束为一条可供下游消费的价格前 `UnderwritingThesis`。

## 已复用的对象

- 海螺的结果已知教学案例和 curriculum case 继续是公司事实与教学身份的来源；没有重抄年报或添加新公司事实。
- 水泥 block 中已有的 `EnterpriseSystemModel` 只提供合并责任边界，不能把早期合并现金写成 FY2024 项目回报。
- `scripts/enterprise_judgment_core.py:compile_cjo_candidate`、`scripts/valuation_routing.py:build_valuation_route` 和 `scripts/judgment_generation_handoff.py:build_judgment_generation_handoff` 继续是现有消费者。本切片只投影它们所需要的同一主张，未修改任一控制层。
- 海螺 FY2024 的策展教学材料没有兼容的 `ManagementDecisionLedger`。U1 不会为满足字段而新造 ledger；管理层的海外、低碳、产业链和效率选择仍由既有教学证据承载。未来真实 Blind Replay 有可用 ledger 时才会直接引用。

## 同源与边界

三个产物——CJO candidate projection、valuation-route request 和 Golden Report handoff——均由 `UWT:CN600585:20240501:V1` 确定性生成。它们共享中心路径、正常盈利、owner cash、永久损失和最强反方；测试拒绝任一投影静默换成另一家公司故事。

`InvestmentTreatment` 是价格后的单向层，不能重写 `UnderwritingThesis`。海螺为结果已知教学案例，故本次没有价格、当前价值、回报、BuyBand 或行动。现有 numeric `INVESTMENT_ENRICHMENT` 对全局 `SELECTION_ADMITTED` 的依赖被登记为 U4 的局部兼容缺口：它不能阻止本次企业承保和价值路线请求，也不能被伪造 admission 绕过。

## 对防御性写作的处理

`ORDINARY_SHARE_OWNER_CASH` 诚实保留为 `CANNOT_BOUND`，但没有吞掉公司结论：海螺的即时生存缓冲被承保，国内核心以中周期范围条件性承保，新增国内资产排除在基准外，海外/产业链保留为场景而非归零。读本先给出这条判断和其永久损失路径，再说明 owner-cash 的局部限制。

麦格纳是同属重资产周期、但结构不同的 near miss：它训练“先排除生存风险，再用资产/EPV、不给成长信用”；海螺不能继承其恢复结论，因为海螺的关键分叉是区域需求、资产吸收和项目现金回收，而非 OEM 破产后的订单恢复。
