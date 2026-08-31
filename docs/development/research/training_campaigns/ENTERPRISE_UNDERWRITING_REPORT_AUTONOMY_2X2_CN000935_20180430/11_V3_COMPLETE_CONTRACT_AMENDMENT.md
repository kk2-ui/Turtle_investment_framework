# V3 完整 Episode 合同：结果前执行修正

> 状态：`FROZEN_BEFORE_V3_ARM_EXECUTION / OUTCOME_SEALED`

V3 是新执行版本，而非 V1/V2 的补写、重跑或替换。继承 `00_EXPERIMENT_PREREGISTRATION.md` 与 `01_FROZEN_SAMPLE_AND_FAIRNESS_REGISTER.json` 的公司、cutoff、共同来源、E/I 输入、四臂矩阵、调用次数、字数上限、匿名规则、估计量与开封条件。

唯一变化是 task delivery：完整 Schema 现在覆盖正式 Episode validator 所需的对象字段、required 和 `additionalProperties`；任务包还含全部跨字段语义规则，包括来源许可、行业未来命题的 exact 派生、组件决策/路线一致性、普通盈利桥全覆盖和敏感性传导一致性。任何由 runner 确定性生成的 summary 均不要求 Agent 输出。修复在未读取 FY2018+、结果、价格或市场资料时完成。

V3 合同 ID 以 `:V3` 结尾，分别保存在 `contracts_v3/`、`tasks_v3/`、`raw_agent_responses_v3/`、`episodes_v3/`、`reader_briefs_v3/` 和 `reader_reports_v3/`。每臂一个新 fresh context、一次 Episode、一次仅在 Episode 合同绑定成功后的首份读者报告 follow-up；不得浏览仓库或网络，不能读取 V1、V2、其他 arm、结果或匿名映射。

V3 匿名映射保存在 `12_ANONYMOUS_LABEL_CUSTODY_V3.json`。匿名 reviewer 只接触匿名输出、共同源包和预注册评审要求；不得读取映射、合同目录、E/I 内容或 outcome。
