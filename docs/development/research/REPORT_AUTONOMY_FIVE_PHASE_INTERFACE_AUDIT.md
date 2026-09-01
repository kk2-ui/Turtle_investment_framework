# REPORT_AUTONOMY_FIVE_PHASE：行业经验至公司取证接口审计

审计范围仅限 `industry_experience_acquisition.py`、`industry_underwriting_context.py`、`industry_evidence_source_binding.py` 与 `judgment_generation_handoff.py` 的静态接口及其直接报告接线；未运行网络/API，未形成任何投资结论。

## 结论

链路已经具备“行业经验 → 有边界的公司取证议程”的主体能力，也有把外部行业观察送入报告前所需的静态来源绑定与 Episode 公司一手证据配对门。但它目前是**研究议程可消费、报告最终链未闭环**：`judgment_generation_handoff` 只在 `RESEARCH_AGENDA` 投影行业上下文、计划、回执和 admission 摘要；最终写作前指定读取的 `JUDGMENT_SYNTHESIS` 视图不含这些已准入观察。故不能把当前实现称为“行业经验已被最终报告生成链可靠消费”。

## 已存在能力

- `industry_underwriting_context.py` 将 IndustryLearningBlock、行业机制、竞争 arena 及可用官方行业观察压缩为有截止日和公司身份的 `IndustryUnderwritingContext`。输出包括需求/供给/竞争/监管驱动、候选路径、同行/near miss、证据引用和 `company_verification_fields`；稀疏输入保持为 `BOUNDED`，不把缺口伪造成结论。
- `industry_experience_acquisition.py` 从该 context 按需求、供给竞争、量价成本、客户渠道、监管、公司传导至多生成一项角色任务。每项有问题、待验证的公司传导、口径边界、来源角色、停止规则及 context 引用；计划/回执同时限制公司事实、估值参数和行动的直接提升。
- 回执校验覆盖任务闭合、来源角色/类型、稳定引用、HTTPS URL、发表/可得时间、截止日与未知/反证状态。`build_episode_industry_evidence_binding` 明确外部观察只能作为 Episode trace 候选，仍需目标公司一手证据。
- `industry_evidence_source_binding.py` 可把回执中的每个观察绑定至已物化的 official-context 或 Phase10 来源包，并核对 URL、发表时间、角色和观察覆盖，避免仅保留不可复读的网页描述。
- `judgment_generation_handoff.py` 对 context/plan/receipt 做公司、截止日和 context 身份核验；若存在有效 binding 与 admission，会在 `RESEARCH_AGENDA` 给出来源绑定状态和 `report_admitted_observations`。运行时研究提示也要求先读该议程、完成回执，再用公司一手证据验证传导。

## 缺失接缝

1. **计划没有成为可执行的公司层研究队列。** 计划在 handoff 中是 `non_blocking` 的提示对象；没有到 `judgment_research_execution`/任务队列的 `task_id` 映射、完成回执要求或显式的未完成状态上卷。提示词要求执行，不能替代可复用执行契约。结果是某次报告可不读取/不完成该计划而仍进入后续写作。

2. **传导配对只证明“有一条公司一手 trace”，未证明它回答了该行业任务的传导问题。** report admission 会核对 observation、行业 trace、公司 trace、公司来源引用和状态，但不把 `observation.company_transmission` 或计划的 `company_verification_fields` 映射到特定 Episode 主张/trace 语义。无关的公司一手证据可被声明为配对，无法保证行业条件真的被公司暴露、单位经济或经营边界所验证/反证。

3. **最终报告视图不消费 admission。** `_VIEW_PROJECTION_KEYS` 仅允许 `industry_underwriting_context` 和 `industry_evidence_acquisition` 出现在 `RESEARCH_AGENDA`。`JUDGMENT_SYNTHESIS` 只投影账本、主张、财务驱动、thesis 等；最终写作流程明确在 assemble 前读取该视图。因此 admission 的“可给报告写作者”状态没有成为最终报告输入或可审计引用约束。

4. **报告组装没有已准入行业观察的引用完整性门。** 当前 handoff/admission 只返回标识和 transmission 状态；未见将报告中行业外部观察（如 `IEA:` trace）与 `report_admitted_observations` 比对的组装前校验。即使研究期正确完成，最后文本仍可能遗漏、误接或引用未准入的观察。

## 最小可复用实现

保留现有四个 artifact 和“行业观察不能直接升级为公司事实”的边界，只补三段小适配器：

1. 在 plan task 中增加稳定的 `transmission_requirement_id`，指向 context 的 `company_verification_field`（无对应字段时显式 `UNRESOLVED`）。把该 task 投影为既有 judgment research queue 的可选但可追踪工作项；完成条件为有效 receipt，或 `UNKNOWN`/`PUBLIC_INFO_UNAVAILABLE` 的完整回执。它不阻断整份报告，但其未完成状态必须留在研究/报告 readiness。

2. 扩展既有 admission pair，而不新建事实库：每个 pair 带 `task_id`、`transmission_requirement_id` 和 Episode 中的公司传导断言/trace ID。验证器要求该 ID 属于计划、该断言来自目标公司一手来源，且其显式标注为支持或反证该 requirement。这样把“来源存在”收紧为“来源回答了哪一个公司传导问题”。

3. 将**仅已通过 admission 的最小标识投影**加入 `JUDGMENT_SYNTHESIS`（及其 `source_refs`），并由 assemble 前的既有报告校验复用该清单：行业外部观察若进入正文/证据 trace，必须在 admission 清单中；没有 admission 的观察只能留在研究议程。保留完整事实在 canonical receipt、来源包和 Episode，避免复制数据或建立第二套报告链。

## 经济影响

这不是格式问题。若行业条件与无关公司证据错误配对，报告可能把行业层变化误写成公司层传导，从而材料性影响对正常化经营、现金可达性、永久损失条件及后续估值输入的判断。反过来，把 `UNKNOWN`、`PUBLIC_INFO_UNAVAILABLE` 和未准入观察继续限定在研究层，能防止把缺失证据当作正面公司证据。上述最小接线不要求行业计划成为整份报告的硬阻断，只要求其状态和可引用边界真实可见。

## 验收测试

1. 给定带 driver 和 `company_verification_fields` 的可审阅 context，编译计划后应生成角色任务；每项有稳定 transmission requirement、来源角色、边界及停止规则。公司身份、context ID 或截止日不匹配时 handoff 局部排除。

2. 将一个计划任务投影到既有研究队列后，队列必须显示相同 `task_id`；有效 receipt、`UNKNOWN` 与 `PUBLIC_INFO_UNAVAILABLE` 都能关闭该任务并保留状态，未回执则在 readiness 中可见但不阻断无关报告工作。

3. 有效来源包绑定后，用与该 transmission requirement 无关的目标公司 Episode trace 建 admission 必须失败；使用明确支持/反证同一 requirement 的目标公司一手 trace 必须通过。

4. admission 通过时，`JUDGMENT_SYNTHESIS` 必须出现只含 observation/行业 trace/公司 trace/传导状态的准入投影及对应 canonical source ref；无 admission 时该投影为空且不得伪装为已准入。

5. 报告组装前校验应拒绝引用未准入的行业观察，接受 admission 清单内观察；缺计划、无外部观察或 `UNKNOWN` 的情形仍可完成其他报告工作，但不得把它们写作已验证的行业或公司证据。
