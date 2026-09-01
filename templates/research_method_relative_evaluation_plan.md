# 方法相对表现的冻结 cohort 计划

这份计划只在已有多个、`SELECTION_ADMITTED` 的不同公司终局经营 FJ，且**任何一个结果窗口尚未打开前**建立。它不是预测评分表，也不用于当前 `NO_PRIMARY` 信号探针。

机器可读对象使用 [`judgment-method-evaluation-plan.v1`](../schemas/judgment_method_evaluation_plan.schema.json)，由 `freeze_method_evaluation_plan` 在读取各 case 的 frozen `selection_register_binding` 后生成 freeze。它须绑定一个已冻结的 `case_selection_register`，并列出其中每一条 screen entry：

- `INCLUDED_SELECTION_EPISODE`：恰好进入一个独立公司簇的 terminal FJ；
- `EXCLUDED_NO_PRIMARY`：当时没有资格选主路径，保留理由但不假装它有可比较预测；
- `EXCLUDED_NONCOMPARABLE`：有研究对象但不具同口径、不同基线或终局结果合同，保留理由。

每个入选单元冻结：`case_id / freeze_id / claim_id / forward_judgment_id / selection_entry_id / company_cluster_id / outcome_not_before`。`company_cluster_id` 必须等于该 `selection_entry_id` 在 frozen register 中的 canonical `cluster.company_id`；公司、公司簇、case 或 claim 任一重复都不能计作独立样本。该 FJ 必须是 frozen pair 的 `TERMINAL_OPERATING` 信号。

入选 CJO 的 `selection_admission.selection_register_binding` 也必须逐字段指向同一 `register_id / fingerprint / selection_entry_id / company_id / company_cluster_id`。普通 `SELECTION_ADMITTED` 仍可没有该 binding；但没有 binding 的 case 不可被后续 L5 cohort 吸收。`EXCLUDED_NO_PRIMARY` 同样必须给出该 entry 对应的 `no_primary_case_id / no_primary_freeze_id`，并由同一 binding 的 frozen `NO_PRIMARY` receipt 证实；否则它只能标为 `EXCLUDED_NONCOMPARABLE`，不能被说成方法弃权。

固定比较规则：

```text
COMPANY_JUDGMENT_ONLY
NON_PRICE_OPERATING_ONLY
NO_PROBABILITY
ONE_SELECTED_TERMINAL_FJ_PER_INDEPENDENT_COMPANY_CLUSTER
BINARY_FROZEN_PREDICATE_LOSS
RETAIN_ALL_PLANNED_UNITS_AND_NONDIAGNOSTIC_OUTCOMES
```

到期后只能将每个入选单元既有的 feedback 放入 cohort。输出完整计数：`SUPPORTS_SELECTED / SUPPORTS_RIVAL / NOT_DIAGNOSTIC / BASELINE_NONDISCRIMINATING / NOT_EVALUATED`，以及 `JUDGMENT_BETTER / BASELINE_BETTER / NO_DIRECTIONAL_INCREMENT_IDENTIFIED`。它不输出准确率、概率、胜率、总分、价格、回报或“方法已证明更强”的结论。

这两组方向计数**只条件于** `INCLUDED_SELECTION_EPISODE`。同一输出必须并列显示完整 screen 的 `INCLUDED_SELECTION_EPISODE / EXCLUDED_NO_PRIMARY / EXCLUDED_NONCOMPARABLE` 计数；`NO_PRIMARY` 是当时不具足够方向性依据的弃权，不是路径选择正确或错误，`NONCOMPARABLE` 不是没有记录的预测。三类不能被合成为一个方法分数。每一条 `INCLUDED_SELECTION_EPISODE` 必须恰有一个 terminal unit；否则 cohort 不能冻结。

任何漏掉的入选单元、未登记的 screen entry、重复公司簇、结果窗口打开后才冻结、早期 FJ 冒充 terminal FJ、或价格/概率字段，都会使此 cohort 不能比较。
