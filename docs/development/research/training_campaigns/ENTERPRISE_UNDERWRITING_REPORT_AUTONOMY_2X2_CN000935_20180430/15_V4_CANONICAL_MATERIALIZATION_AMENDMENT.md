# V4 canonical Episode：结果前执行修正

> 状态：`FROZEN_BEFORE_V4_ARM_EXECUTION / OUTCOME_SEALED`

V4 是一个新的、唯一可用于四臂比较的执行版本。公司、cutoff、共同源、E/I 输入、模型、调用次数、字数上限、匿名规则、估计量和结果开封条件继续遵守 `00_EXPERIMENT_PREREGISTRATION.md` 与 `01_FROZEN_SAMPLE_AND_FAIRNESS_REGISTER.json`。

唯一变化是 raw Agent response 先经 deterministic canonical materialization 才进入现有严格 validator：

- compiler-owned `component_decision_summary` 和 `economic_derivation_summary` 由 runner 派生；
- 若一个 sensitivity 的 delta 是 `UNKNOWN`，该 axis 的 transmission canonical 状态为 `UNKNOWN`；
- 仅有 `SCENARIO_ONLY`、`EXCLUDED`、`UNRESOLVED` 或 `NOT_APPLICABLE` 绑定、且尚未注册为其他角色的路线，登记到 `excluded_routes`，表示不进入当前价值输入。

这一过程不补写公司事实或经济结论，不解决角色冲突，不生成数字，也不放宽任何 validator。任务包明确这一边界，Agent 仍须完整表达证据、组件判断、路线 requirement、桥和敏感性逻辑。V4 必须由四个新 `fork_turns=none` context 各生成一次原始 response；四份 canonical Episode 全部成功绑定，才可生成首次报告与进行匿名审阅。

V4 使用 `contracts_v4/`、`tasks_v4/`、`raw_agent_responses_v4/`、`episodes_v4/`、`reader_briefs_v4/`、`reader_reports_v4/` 和新的匿名 custody `16_ANONYMOUS_LABEL_CUSTODY_V4.json`。
