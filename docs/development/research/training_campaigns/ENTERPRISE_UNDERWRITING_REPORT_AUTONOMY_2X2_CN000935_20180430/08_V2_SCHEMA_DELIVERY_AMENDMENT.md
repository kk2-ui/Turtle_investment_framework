# V2 结果前执行修正

> 状态：`FROZEN_BEFORE_V2_ARM_EXECUTION / OUTCOME_SEALED`

V2 是一个新的结果前执行版本，不是对 V1 响应的补写或隐藏重试。它继承 `00_EXPERIMENT_PREREGISTRATION.md` 和 `01_FROZEN_SAMPLE_AND_FAIRNESS_REGISTER.json` 的公司、cutoff、共同源、E/I 输入、四格设计、调用次数、字符上限、匿名规则、估计量和结果开封条件。

唯一允许的变化是 `render-subagent-task` 现在在每份任务包的 `response_contract.episode_json_schema` 中内嵌同一个完整冻结 Schema，并明确遵守其 required、enum、const、additionalProperties 和嵌套结构。该修复在未读取任何 FY2018+ 或结果材料时完成。

V2 使用新合同 ID 后缀 `:V2`、`contracts_v2/`、`tasks_v2/`、`raw_agent_responses_v2/`、`episodes_v2/` 和 `reader_reports_v2/`，从而与 V1 证据链分离。四个 Agent 必须重新以 `fork_turns=none` 启动；不得读取 V1 响应、兄弟臂、仓库或网络。若任何 V2 Episode 不通过现行 validator，四臂比较仍不得开始。

V2 匿名映射保存在 `09_ANONYMOUS_LABEL_CUSTODY_V2.json`；pre-outcome reviewer 只接触匿名输出，不读取映射。
