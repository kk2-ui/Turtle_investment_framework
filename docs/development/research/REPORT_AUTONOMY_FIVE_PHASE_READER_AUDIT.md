# 五阶段报告自主性：组件经济账本到完整读者报告审计

## 结论

**当前尚未具备生产接缝。** 已有可靠的上游组件经济账本、价外 Episode 投影、读者版净化与完成门；但没有一条受身份绑定、可验证且被正式报告组装器消费的路径，将 `component_decisions` 与 `economic_derivation` 送入完整读者报告。因此，现有代码能产出“带组件桥的独立 Episode 读本”，也能产出“从技术稿清理控制语法的读者报告”，却不能证明后者保留了前者的组件—正常盈利—普通股现金—永久损失—价值路线经济链。

这不是文案润色缺口，而是 `ACQUISITION_MODULE + REASONING` 的生产集成缺口：读者版可能通过标题、来源、数值槽位和一般读者覆盖检查，同时丢失某个组件的纳入权限、条件性处理、责任边界或对价值路线的影响。

## 已存在且可复用的能力

| 层 | 已有能力 | 审计判断 |
| --- | --- | --- |
| `enterprise_underwriting_training.py` | v2 合同可要求每个 `component_treatments` 项均有 `component_decisions`；运行器只派生 `component_decision_summary`、`economic_derivation_summary` 并持久化完整 Episode 及下游 bundle。 | 组件经济账本是可追溯、非自由补写的上游真源。 |
| `enterprise_underwriting_episode.py`（被 training 调用） | 组件决策覆盖正常盈利、普通股现金、融资压力、永久损失和逐路线估值用途；经济推导要求正常盈利桥、证据、责任边界、敏感性及翻转条件相互解析。`compile_golden_report_reader_brief` 已能生成组件判断和“正常盈利组件桥/关键敏感性”读者段落。 | 最接近所需读者桥，且不应重造另一套经济分类。 |
| `judgment_generation_handoff.py` | 从报告本地 canonical artifacts 生成只读、同公司/同截止日检查的 `JUDGMENT_SYNTHESIS` 与 `INVESTMENT_ENRICHMENT` 视图；绑定 Episode CJO 时可传递企业判断、正常盈利、普通股现金、永久损失及估值路线的高层投影。 | 有安全的生产读模型边界，但未显式投影完整组件决策、经济推导行及其读者版覆盖义务。 |
| `reader_report_surface.py` | 对已写成的技术叙事做确定性投影，去除控制 ID/绑定语法，保留全部叙事 H2；校验受编译器拥有的数值槽只在技术稿和读者稿各出现一次，且不落入执行备忘录。 | 是“保留既有叙事”的表面层，不是“从组件账本补齐读者桥”的编译器。 |
| `report_completion.py` | 对 Episode 绑定前驱做身份及 CJO admission 检查；对当前 archetype 输出执行读者覆盖检查。 | 完成门验证前驱有效与读者语义覆盖，但没有验证读者稿消费组件经济账本。对于 Episode 路径，它还明确跳过旧 `financial_driver_bridge`，不能由该旧门替代新桥。 |
| 02669 专家纠偏蒸馏资产 | 教师包明确要求读者可重建“业务组件→正常盈利→可实现现金→价值/行动层级”的桥，并把来源近接、局部未知与路线身份列为材料纠偏。README 同时明确它仅是 `TRAINING_MEMORY`，不是下一家公司或生产报告的证据。 | 提供了正确的验收语义和训练边界；不应把源快照或教师公司事实接入运行时报告。 |

## 真实缺失

1. **没有 canonical 的读者组件桥投影。** `compile_golden_report_reader_brief` 仅由 `compile-reader-brief` 命令手工输出；仓库内没有正式报告 writer、`judgment_generation_handoff` 或 `report_completion` 对该 brief 的输入绑定或消费。该函数的存在不能保证主报告有这几段内容。
2. **handoff 丢失组件级可审计语义。** 现有 handoff 传的是高层企业判断和路线；读者 writer 无法从其中确定每个材料组件是基准、条件、压力、排除或未解决，也不能重建 normal-earnings bridge 行、责任边界、敏感性到路线的归属和翻转证据。
3. **reader surface 只减不增。** 它从 `reader_projection_source_text` 删除控制信息后保存原 H2；若技术叙事本来未写组件桥，它既不会生成桥，也不会报错。数值槽的基数检查不能替代“每个材料组件的经济去向可读”。
4. **completion 没有组件—读者一致性门。** 当前完成只把 reader coverage 作为语义门，并未比较读者稿与 Episode component ids / economic derivation / route bindings；缺一个组件、把条件组件写成基准，或删除敏感性归属，均没有本模块级的阻断证据。
5. **蒸馏资产未被安全地落入运行时接口。** 02669 已定义验收所需的可挑战经济桥，但其正确权限是训练记忆。当前没有把该抽象规则落实为独立于教师事实的 production schema/validator；直接把教师包或 `source_snapshots` 接到报告会违反其自身隔离边界。

## 最小可复用实现

不新建证据库、不复制估值器，也不让 writer 自行解释组件账本。沿用 Episode 的现有派生物，新增一个**报告本地、只读、版本化**投影，例如 `enterprise_underwriting_reader_bridge.v1`：

1. 在既有 Episode/CJO→报告 handoff 编译处派生该投影，并以 `episode_id`、`underwriting_thesis_id`、公司和截止日绑定。每个材料组件只携带：读者名称/经济理由、五个既有经济用途、晋级/失效检验、已解析的正常盈利桥行、普通股现金/永久损失处理、路线绑定、敏感性与翻转观察，以及允许显示的来源锚点。保留“不适用/未解决/条件性”原状态，绝不把未知转为零或基准。
2. `judgment_generation_handoff.py` 在已绑定 Frozen CJO 的报告路径中把此投影作为一个明确字段和 `source_ref` 暴露给 writer；它仍是 read model，事实引用和修改仍返回 canonical artifact。
3. 正式章节 writer/`assemble_report` 消费该字段，在完整读者稿中渲染一个短而完整的“组件经济桥”段落：业务组件→正常盈利→普通股现金→永久损失→价值路线，以及仅材料性敏感性的路线归属与翻转证据。估值器拥有的数字继续只经已有 reader slots 进入，避免第二套数值渲染。
4. `reader_report_surface.py` 继续只负责去除技术控制语法；为该新增桥增加“叙事段必须保留、控制 ID 不得泄漏”的校验，不让其承担经济重新计算。
5. `report_completion.py` 在 Episode-bound 且 reader contract 已激活的运行中强制 `component_reader_bridge` validator：所有材料组件必须出现一次，显示的五项用途与 canonical summary 一致；每条材料推导/敏感性有其责任边界、路线和翻转处理；条件、压力、排除和未解决项目没有被提升。缺失或不一致即 `BLOCKED`。

这是一条最小的单向链：

```text
Episode component_decisions + economic_derivation
  -> bound reader_bridge (derived, price-free)
  -> judgment_generation_handoff
  -> chapter writer / assemble_report
  -> reader_report_surface
  -> component_reader_bridge completion validator
```

## 经济影响

若不补此接缝，读者无法独立挑战最可能改变企业判断的地方：某项业务或现金是否进入基准正常盈利、普通股现金是否可实现、局部未知是否被限定在正确组件、以及同一组件为何只能进入特定价值路线。结果会造成两类相反但同样材料性的失真：把条件性组件悄然升级为基准，或因一个局部未知而错误抹去独立可承保的成熟经济。仅有清晰摘要、完整章节或精确数值槽都不能弥补这一决策可挑战性损失。

## 验收测试

1. **正向端到端。** 构造一个有基准、条件和排除组件，且含一条材料敏感性的合法 v2 Episode；走正式 handoff、章节组装和读者 surface。断言 reader bridge 的组件、五类用途、经济桥、路线归属、翻转条件与 canonical Episode 完全一致；读者稿保留其叙事，不含控制 ID。
2. **提升权限阻断。** 将一个条件/压力/排除/未解决组件在 reader bridge 或读者稿中改写为基准或主要路线输入。完成门必须 `BLOCKED`，finding 指明 component id、原用途和错误用途。
3. **删除桥阻断。** 在技术叙事中删除一个材料组件、normal-earnings bridge 行或材料敏感性归属，再运行 reader projection。不得仅因 H2 和数值槽通过；`component_reader_bridge` 必须阻断并指出缺失对象。
4. **数值所有权回归。** 带 valuation reader slots 的端到端样本仍只允许编译器拥有的句子进入技术稿和读者稿各一次，执行备忘录为零次；新增组件桥不得自行重渲染这些数值。
5. **训练资产隔离。** 以 02669 蒸馏记忆作为训练输入时，生成的 bridge 只能引用新 Episode 的允许来源；若 bridge 指向教师包、source snapshot 或教师公司事实，验证失败。该测试验证规则迁移，而非复用结果。

## 审计边界

本审计只读取本 worktree 的指定脚本、其直接 Episode 读模型/报告组装调用点，以及 02669 专家纠偏蒸馏资产；未运行网络、API、训练或报告生成，也未读取 History 或其他 worktree。未作任何投资、价格或结果判断。
