# U1：完整企业承保纵向切片的实现说明

U1 没有新增事实库、CJO、估值引擎或报告流水线。它新增的是一个很窄的组合读模型：`EnterpriseUnderwritingEpisode` 将现有来源、企业状态、管理动作、现金边界和价值路线收束为一条可供下游消费的价格前 `UnderwritingThesis`。

## 已复用的对象

- 海螺的结果已知教学案例和 curriculum case 继续是公司事实与教学身份的来源；没有重抄年报或添加新公司事实。
- 水泥 block 中已有的 `EnterpriseSystemModel` 只提供合并责任边界，不能把早期合并现金写成 FY2024 项目回报。
- `scripts/enterprise_judgment_core.py:compile_cjo_candidate`、`scripts/valuation_routing.py:build_valuation_route` 和 `scripts/judgment_generation_handoff.py:build_judgment_generation_handoff` 继续是现有消费者。后续 kernel 接线在这些既有入口增加可选完整投影，没有建立第二套 CJO、估值或报告流水线。
- 海螺 FY2024 的策展教学材料没有兼容的 `ManagementDecisionLedger`。U1 不会为满足字段而新造 ledger；管理层的海外、低碳、产业链和效率选择仍由既有教学证据承载。未来真实 Blind Replay 有可用 ledger 时才会直接引用。

## 同源与边界

三个产物——CJO candidate projection、valuation-route request 和 Golden Report handoff——均由 `UWT:CN600585:20240501:V1` 确定性生成。它们共享中心路径、正常盈利、owner cash、永久损失和最强反方；测试拒绝任一投影静默换成另一家公司故事。

`InvestmentTreatment` 是价格后的单向层，不能重写 `UnderwritingThesis`。海螺为结果已知教学案例，故本次没有价格、当前价值、回报、BuyBand 或行动。后续 kernel 已允许 source-bound 完整 Blind/Prospective Episode 通过 current-company CJO admission 进入 valuation route，而无需全局 `SELECTION_ADMITTED`；worked case 仍固定为 Teaching，不能借该入口伪造 current-company admission。

## Kernel 接线后的运行边界

- `enterprise-underwriting-episode.v2` 把 `IndustryFutureThesis` 和 valuation model roles 纳入 Episode 本体；行业未来必须写清利润池、公司暴露与适应，以及向正常盈利、owner cash 和永久损失的传导。
- `scripts/enterprise_underwriting_training.py` 是新的训练主入口；checked-in 海螺 contract 只认可完整 Episode 为主产品。旧 curriculum 的 30 个 Teaching 和 11 个 Blind 数量仍可作局部 inventory，但不再被报告为完整承保训练完成数。
- 合法 Blind/Prospective Episode 的 evidence refs 必须属于同一 CJO source package；Frozen CJO 和独立 review receipt 固定完整价格前投影。
- `JUDGMENT_SYNTHESIS` 原样返回该投影，确定性公司判断读者工件优先渲染行业未来到永久损失的完整链；报告本地 thesis 不能覆盖。
- valuation runtime 若发现分析合同绑定的 Frozen CJO 含完整 Episode，会自动使用其 model roles、正常化、owner cash、永久损失和排除项；没有绑定的 legacy run 保持原路径。
- Judgment Experience Memory 复用现有 JER/registry，将完整 worked Episode 投影为 Teaching-only 条件化经验；不授予迁移信用。

## 对防御性写作的处理

`ORDINARY_SHARE_OWNER_CASH` 诚实保留为 `CANNOT_BOUND`，但没有吞掉公司结论：海螺的即时生存缓冲被承保，国内核心以中周期范围条件性承保，新增国内资产排除在基准外，海外/产业链保留为场景而非归零。读本先给出这条判断和其永久损失路径，再说明 owner-cash 的局部限制。

麦格纳是同属重资产周期、但结构不同的 near miss：它训练“先排除生存风险，再用资产/EPV、不给成长信用”；海螺不能继承其恢复结论，因为海螺的关键分叉是区域需求、资产吸收和项目现金回收，而非 OEM 破产后的订单恢复。
