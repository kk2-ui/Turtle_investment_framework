# 五阶段报告自主性：writer 接线审计

## 结论

**最小接线点是既有 `JUDGMENT_SYNTHESIS` handoff，并由 `read_report_contract_pack` 在 writer 首次读取时一并交付。** 不应在 `run.py`、`agent_loop.py` 或 `assemble_report` 新建一条渲染链。

本 worktree 已经将经过 source binding 和 Episode 公司一手传导配对的行业观察，投影为 `JUDGMENT_SYNTHESIS.projection.report_admitted_industry_evidence`；普通 ledger 路径和 Frozen-CJO 路径都会填充它。因此“行业观察尚未到最终 handoff”的问题在当前代码中已不成立。

缺口在于 Enterprise Underwriting 的组件经济信息：`compile_underwriting_projections()` 已从完整 Episode 派生 `golden_report_underwriting_handoff`，其中含 `component_decisions`、组件经济用途及 `economic_derivation`；但当前 Frozen CJO、`canonical_judgment_refs` 和 `JUDGMENT_SYNTHESIS` 没有一个受绑定的 reader bridge 引用。writer 因而只能读到高层 thesis / normal-earnings / owner-cash / permanent-loss 投影，无法可靠区分每个材料组件的基准、条件、压力、排除和未解决处理。

根因分类为 **ACQUISITION_MODULE + REASONING**：生产 read model 丢失了已验证的组件经济语义，而不是 writer 缺少又一种报告模板。经济影响是材料组件可被静默升级为基准价值输入，或一个局部现金/量化未知被误扩展为整家公司不可承保；两者都会改变正常盈利、owner cash、永久损失和价值路线判断。

## 实际自动生成入口

| 层 | 实际入口与责任 | 审计判断 |
| --- | --- | --- |
| 常规全自动报告 | `scripts/turtle_agent/run.py:2231` 的 `run_full_pipeline()` 注册读写工具，并在正常/repair pass 中构造 `TurtleAgent`（`scripts/turtle_agent/run.py:3707`）。 | 主生产 writer 路径。它不应解释或渲染组件 bridge，只应让已有工具读取它。 |
| 自动收口 | `run.py:3621` 的 deterministic binding repair 与 `run.py:3716` 的定向研究完成后收口，都直接调用 `write_tools.assemble_report()`。 | 这是同一正式 assembler 的无模型重组，不是第二个 writer；新桥必须随同原 assembler 的 completion gate 生效。 |
| Agent 入口 | `scripts/turtle_agent/agent_loop.py:543` 的 `TurtleAgent.analyze()` 驱动章节 writer；其唯一常规组装出口为 `_assemble_report()`（`agent_loop.py:4285`）。系统提示要求首轮读取 `read_report_contract_pack`（约 `agent_loop.py:735`），且 `agent_loop.py:3682-3693` 会拒绝在该 pack 读取前写入章节；组装前再读取 `JUDGMENT_SYNTHESIS`（约 `agent_loop.py:2113`）。 | 这是 LLM 实际能获得 writer 输入的入口。只在最后读取 synthesis，已太晚以它指导前面的章节写作。 |
| 正式 assembler / 双层 reader 产物 | `scripts/turtle_agent/tools/write_tools.py:2720` 的 `assemble_report()` 先要求当前 `JUDGMENT_SYNTHESIS`（和投资路径的 `INVESTMENT_ENRICHMENT`）read receipt，随后在 `write_tools.py:3030-3058` 用现有 `reader_report_surface` 投影并调用 completion。 | 唯一正式 V13 组装与 reader-surface 入口；不得在这里追加一个“组件报告”或重新计算组件经济。 |
| PIT 生产冻结 | `run.py:2141` 的 `_run_pit_production_freeze()` 通过 `TurtleAgent`（`run.py:2200`）走受限完整 writer；`_initialize_pit_production_output()` 在 `run.py:1953-1961` 写入 Episode-bound `canonical_judgment_refs`。 | 当前唯一自动写入 Frozen-CJO / admission 引用的生产边界，适合把 bridge 的已解析引用一并绑定。 |
| PIT writer 草案 | `_run_pit_writer()`（`run.py:1826`）配置 `pit_mode` 的独立、受限 `pit_write_report` 流。 | 它是受限 PIT 草案，不调用 V13 `assemble_report`，不是本次“完整 reader 报告”接线的替代入口。 |
| 完成契约 | `scripts/report_completion.py:481` 的 `evaluate_report_completion()`。 | 不是 writer；它是防止 writer 忽略已交付 bridge 的唯一合适强制点。 |

直接调用 `write_tools.assemble_report()` 的测试和工具用户也会走同一 assembler，因此不能只在 `TurtleAgent` prompt 中解决问题。

## 已有接线与精确缺口

1. `scripts/enterprise_underwriting_episode.py:1821-1981` 已有单源派生：`golden_report_underwriting_handoff` 带完整的 `component_decisions`、`component_economic_routes`、`economic_derivation` 和 `economic_derivation_summary`。`compile_golden_report_reader_brief()`（约 `:2300`）也证明组件经济可被安全地转为读者语言，但它目前是训练/Golden reader 工具，不是生产 V13 writer 输入。

2. `scripts/judgment_generation_handoff.py:945-1008` 的 Frozen-CJO `JUDGMENT_SYNTHESIS` 已取回 `report_admitted_industry_evidence`；普通 ledger 路径也在 `:899-942` 交付同字段。它只包含 admission 后的 observation / industry trace / target-company trace / transmission 状态，且已有 source ref；这正是 writer 可用的最小行业输入。

3. `scripts/turtle_agent/tools/read_tools.py:451-607` 的 `read_report_contract_pack()` 首先读取 `RESEARCH_AGENDA`，但只在旧 `company_judgment_predecessor.json` 存在时附加 `INVESTMENT_ENRICHMENT`（`:589-592`）。当前 Episode-bound investment contract 只有 Frozen CJO 与 CJO admission 引用，通常不生成该旧 predecessor，所以首次章节 writer 不会从 contract pack 获得完整、receipt-bound `JUDGMENT_SYNTHESIS`。

4. `scripts/judgment_generation_handoff.py:71-72` 的 `canonical_judgment_refs` 白名单只有 Frozen CJO、overlay 和 admission；`run.py:1956-1961` 同样只写这两个 Episode-bound 引用。Frozen CJO 的 `underwriting_thesis_projection` 是高层、price-free thesis 投影，不保留完整组件账本或其 artifact ref，不能靠 `episode_id` 在训练目录中搜索并猜测来源。

5. `write_tools.assemble_report()` 只拼接 writer 已写章节，现有 `reader_report_surface.py` 只移除控制语法、保留正文 H2；`report_completion.py` 只验证 Episode predecessor、reader coverage 等。两者都没有组件 bridge 的身份/覆盖/用途一致性 validator。

## 最小实现建议

### 1. 在现有 Episode→CJO 绑定处派生并绑定数据桥

从 `golden_report_underwriting_handoff` 派生一个报告本地、只读、price-free 的 `enterprise_underwriting_component_reader_bridge.v1`。它是**数据投影，不是 Markdown renderer**，并且只允许包含：

- `episode_id`、`underwriting_thesis_id`、`company_id`、`cutoff_at`；
- 每个材料组件的 reader-safe 名称/经济理由、五个既有用途、promotion / invalidation 条件；
- 已解析的 normal-earnings bridge 行、owner-cash / financing-pressure / permanent-loss 处理、精确 route binding；
- 材料敏感性、责任边界、反转观察，以及允许给 writer 看的来源锚点；
- 原有 `CONDITIONAL`、`SCENARIO_ONLY`、`EXCLUDED`、`UNKNOWN` / 未解决语义，不得转成零、基准或主要路线。

将这个 bridge 的明确 artifact ref 加入 Episode-bound `analysis_contract.canonical_judgment_refs`；同一时点扩展 `run.py` 的 `_load_episode_bound_current_company_judgment()`、`_initialize_pit_production_output()`、handoff 的 `_canonical_judgment_refs()` 白名单和 `report_completion` 的 predecessor validator。要求它与 Frozen CJO、CJO admission 的公司、cutoff、episode 与 thesis 完全一致。**不得**根据 ID 扫描 `docs/development/research/training_campaigns/` 或选择某个看似匹配的 Episode。

### 2. 将 bridge 放进既有 `JUDGMENT_SYNTHESIS`

在 `judgment_generation_handoff` 的两个 synthesis builder 中，新增一个必需 projection 字段，例如 `enterprise_underwriting_component_reader_bridge`：

- 只在 Episode-bound investment contract 激活；缺 ref、不可读或 identity 不一致即让该 view `BLOCKED`；
- 和现有 `report_admitted_industry_evidence` 同级返回，并添加该 bridge 的 canonical source ref；
- 不改造 `RESEARCH_AGENDA`、不新增新 tool、不把外部行业 receipt 提升为公司事实。

这是最小的共同汇合点：同一个终态 handoff 已被 `assemble_report()` receipt 要求，也已经承载行业 admission。将两种输入置于这一 view，消除了“行业从 research view 取、组件从另一个 writer 取”的平行控制面。

### 3. 让首次章节 writer 必得该同一 view

在 `read_report_contract_pack()` 内，对 investment reports 无论是否存在 legacy predecessor，都读取 `JUDGMENT_SYNTHESIS` 和现有的 `INVESTMENT_ENRICHMENT`，并在现有 `judgment_generation_handoff` 返回对象中加入一个固定 `writer_underwriting_handoff` 字段。它包含前者的两个新/现有字段，以及后者既有的 price-facing enrichment：

- `enterprise_underwriting_component_reader_bridge`；
- `report_admitted_industry_evidence`。

这次工具内读取也生成现有 synthesis 与 enrichment receipt；因此 `assemble_report()` 仍用原有 receipt 机制确认当前 input，而无需新一次 LLM round trip。`agent_loop.py` 只需把 contract-pack 指令明确为：组件 bridge 是章节写作的固定约束，行业观察只有 admission 列表内者可作为外部行业证据；不需要新增 tool、AgentConfig 字段或另一 prompt path。

### 4. 保持 assembler 单一渲染职责，增加 completion 验证

`assemble_report()` 不渲染 bridge、不在章节尾部补写文本、也不调用 `compile_golden_report_reader_brief()`。它继续将技术叙事交给既有 `reader_report_surface` 的单向净化。

在 `report_completion.py` 对 Episode-bound investment 添加一个 `enterprise_underwriting_component_reader_bridge` validator，使用 contract-bound bridge 和实际 technical / reader text 检查：

- 每个材料组件的经济去向在技术叙事中可追溯，并且 reader surface 保留相应投资者语言；
- 条件、压力、排除及未知状态没有提升；normal-earnings 行、材料敏感性和 route / reversal 归属不丢失；
- 文本中作为外部行业证据使用的 observation 只能来自同一 `report_admitted_industry_evidence.observations`；空 admission 不要求凭空写行业事实。

这只是对同一 writer 输出的 validator，不是第二个 prose generator。`reader_report_surface` 最多扩展为移除新增的技术控制标记，并继续证明保留叙事；它不重新解释 Episode，也不拥有数值槽。

## 不应做的事

- 不让 `run.py` 在每个 pass 重新编译或向章节 append 组件文字；这会绕过 LLM writer、repair 流与 source attribution。
- 不将 `compile_golden_report_reader_brief()` 直接当成另一份正式报告，或由 `assemble_report()` 把它渲染后与章节拼接；这会形成平行 renderer，并重复现有 reader-surface 责任。
- 不把未配对的行业 context、plan、receipt 或 source binding 放入 reader evidence；它们仍只是研究议程。
- 不以 legacy `financial_driver_bridge` 代替 Episode component bridge；`report_completion.py` 已明确在 Episode-bound path 跳过该旧桥，因为二者不是同一经济对象。

## 直接测试接缝与验收

| 测试位置 | 需要覆盖的最小回归 |
| --- | --- |
| `tests/test_enterprise_underwriting_episode.py` | bridge 仅由现有 `golden_report_underwriting_handoff` 派生；组件用途、normal-earnings rows、route 与状态均不被改写，且不含 price / action / 内部控制泄漏。 |
| `tests/test_judgment_generation_handoff.py` | Episode-bound `JUDGMENT_SYNTHESIS` 同时给出 identity-bound component bridge 与现有 report-admitted industry observations；任一 ref 缺失、公司/cutoff/episode/thesis 不匹配时为 `BLOCKED`。 |
| `tests/test_turtle_agent_pit_production_mode.py` | production initialization 绑定第三个 bridge ref；首次 contract pack 对 Episode-bound investment 直接交付 `writer_underwriting_handoff`，不回退到 legacy predecessor。 |
| `tests/test_judgment_handoff_receipts.py` | bridge 或 admission 的有效输入变化会使 synthesis receipt 过期；重新读相同 handoff 后才能组装。 |
| `tests/test_reader_report_surface.py` | bridge 的读者段落被 surface 保留，技术 ID / 控制标记被清除；不新增长度或第二个输出文件。 |
| `tests/test_completion_contract_v13.py` | 删除材料组件、normal-earnings row、route/reversal 归属，或把条件/排除/未知写成基准，均使 Episode-bound report `BLOCKED`；legacy report 不因未启用 bridge 被重新分类。 |

`tests/test_turtle_agent_pit_writer.py` 应继续确认受限 PIT 草案不误入 V13 assembler；它不是本接线的正向 acceptance lane。现有 `tests/test_judgment_handoff_receipts.py` 和 `tests/test_turtle_agent_pit_production_mode.py` 已覆盖直接 assembler / production-route 行为，比只断言 system prompt 更能证明接线存在。

## 审计边界

本审计只读取本 worktree 的 `run.py`、`agent_loop.py`、`write_tools.py`、`report_completion.py`、其直接 handoff / Episode / reader-surface / industry-admission 接口及上述测试。未运行报告、训练、网络或 API；未修改代码。
