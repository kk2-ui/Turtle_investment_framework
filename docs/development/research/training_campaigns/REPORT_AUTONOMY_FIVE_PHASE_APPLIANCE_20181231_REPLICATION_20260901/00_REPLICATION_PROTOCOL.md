# Report autonomy four-arm replication cohort — 2026-09-01

状态：`COHORT_FROZEN / PREOUTCOME_TASKS_MATERIALIZED`

这是一个独立于此前 `STAGE5` 和 `INTERFACE_V2` 工件的新四臂复制 cohort。它不修改、重试或读取旧 cohort 的任何 Episode、报告或结果；所有 32 个 cell 重新从冻结合同生成，初始执行次数为零。

本 cohort 使用同一截止日和同一公开源包，目的是先验证修复后的 staged judgment ledger、v2 经济推导接口和四臂控制面可以完整承载一次新执行。由于源包和行业记忆与此前 appliance 实验相同，本 cohort 不能单独承担未见公司迁移或行业经验普遍性结论；这些结论必须留给后续跨公司 holdout。

四臂定义保持不变：

- `A00`：无行业经验、无专家纠偏；
- `A01`：仅行业经验；
- `A10`：仅专家纠偏；
- `A11`：行业经验与专家纠偏。

执行规则：每个 cell 只允许一个 `fork_turns=none` fresh Codex 子 Agent、一次 Episode 和一次首次读者报告；禁止重试、改写、联网、读取价格/回报/后验结果或其他 arm 输出。全部匿名预结果审阅冻结前，`outcome_access_gate` 保持关闭。

当前已完成：预注册验证、八份 value-free outcome contract 物化、32 份 fresh task 物化。尚未执行任何 arm，也未读取任何 outcome。
