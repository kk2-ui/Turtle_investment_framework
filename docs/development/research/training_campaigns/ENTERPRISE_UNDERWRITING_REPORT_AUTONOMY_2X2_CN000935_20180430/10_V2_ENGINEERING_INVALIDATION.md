# V2 工程失效裁决

> 状态：`PAIRED_TEST_INVALID / OUTCOME_REMAINS_SEALED`

V2 在 V1 的完整 JSON Schema 交付修复后启动。`A00_BASELINE`、`A10_EXPERT_ONLY` 和 `A01_INDUSTRY_ONLY` 均各自完成一次原始 Episode 并由正式 `run --agent-response` 合同绑定；三份均为 `INVALID`。`A11_COMBINED` 在平台中断前未产生原始响应，不得补跑 V2。V2 因而没有读者报告、匿名比较或结果开封。

| Arm | 原始响应 | 正式绑定结果 |
| --- | --- | --- |
| `A00_BASELINE` | `raw_agent_responses_v2/A00_BASELINE_EPISODE_RESPONSE.json` | `INVALID` |
| `A10_EXPERT_ONLY` | `raw_agent_responses_v2/A10_EXPERT_ONLY_EPISODE_RESPONSE.json` | `INVALID` |
| `A01_INDUSTRY_ONLY` | `raw_agent_responses_v2/A01_INDUSTRY_ONLY_EPISODE_RESPONSE.json` | `INVALID` |
| `A11_COMBINED` | 未产生；执行被中断 | `NOT_EXECUTED` |

## 根因和经济影响

根因仍是 `ACQUISITION_MODULE / MODEL`，不是四臂投资推理。V2 的 JSON Schema 已给出大部分嵌套结构，却未完整表达正式 validator 的字段要求和跨字段经济连续性：证据的 `locator/scope/used_for`，既有对象的 `kind/role`，监控字段，行业未来命题与顶层/承保命题的 exact rival/reversal 派生，组件—路线绑定，桥对所有普通盈利组件的覆盖，以及敏感性状态与路线角色相容性。不同臂触发的具体项不同，正说明它们在不完整合同下仍在猜测未交付规则。

这组缺口可以材料性改变“能否完成完整承保”的判定，却不能被解释为专家纠偏或行业经验的效用。V2 原始响应保留为工程证据；严禁人工修补、单臂重试、根据失败文本调整 E/I、或把中断臂替换进 V2。

## V3 的唯一修复及接受条件

V3 把 validator 的完整字段契约补进 Schema，并把无法由 JSON Schema 表达的跨字段规则直接写入每一份 fresh task；组件/经济推导 summaries 明确为 runner 的确定性派生字段，可由 Agent 省略。V3 不放宽 validator，不改 V2 输出，也不变更样本、来源、E/I、模型、预算、估计量或结果封存。

只有四个新 `fork_turns=none` context 各生成一次 Episode，且四份均通过正式合同绑定后，才可机械生成 reader brief 并要求同一 Agent 生成一次首份读者报告。否则不进入匿名审阅或 outcome 结算。
