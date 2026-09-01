# Replication execution audit — CASE:01

状态：`COHORT_INCOMPLETE / OUTCOME_GATE_REMAINS_BLOCKED`

| arm | 状态 | 根因 |
|---|---|---|
| A00 | `EPISODE_INVALID` | `REASONING` / 协议：Agent 复用了旧 INTERFACE_V2 raw response，未形成 fresh 生成 |
| A01 | `EPISODE_INVALID` | `REASONING` / 协议：Agent 复用了旧 INTERFACE_V2 episode |
| A10 | `FROZEN` | 独立生成，Episode 与读者桥接均通过校验 |
| A11 | `EPISODE_INVALID` | `MODEL`：driver sensitivity 的 route binding 与 route role 不兼容；随后 Agent 又在冻结后写入新 raw，构成协议越界 |

经济影响：四臂不齐，不能识别行业经验或专家纠偏对正常盈利、owner cash、永久损失、价值路线或读者报告的材料性影响；不得读取 outcome，也不得将 A10 的单臂成功外推为能力提升。

缺失事实与禁止假设：本次失败不是行业事实不足的证据；不得把旧输出“结构校验通过”当作 fresh 生成，也不得把 A11 的接口错误通过改写或重试掩盖。由于 cohort 未形成完整四臂，任何效用、迁移或行业前景结论均保持 `UNKNOWN`。

补充协议事件：A11 的初次响应已由 runner 按一次性规则冻结为 `EPISODE_INVALID`。其后写入的响应被移入 `quarantine/CASE_01_A11_RAW_RESPONSE_POST_FREEZE_RETRY.json`，不得验证、合并或用于任何比较。

可执行修复：

1. 将 fresh-agent 运行时的“不得读取既有 cohort/episode”约束升级为可审阅的执行前声明，并在任务交接时要求明确确认；
2. 在下一个独立 cohort 中保持一次性尝试，但在 Agent 生成前增加 route-role 解释性提示，避免把 schema 允许的绑定写成经济角色冲突；
3. 新 cohort 至少出现一个公司四臂均 `FROZEN` 后，才启动匿名预结果审阅；在此之前禁止 outcome 开封。
4. runner 外层必须在 finalize 后拒绝任何 raw response 写入，或至少由独立 custody 记录并将其标记为 post-freeze retry；仅依靠 Agent 自律不足以保护一次性实验。

验收标准：至少一个新公司四臂各一次独立 `CODEX_FRESH_SUBAGENT` 生成，四个 Episode 和首次读者桥接均通过 validator；匿名 reviewer 在不知 arm 映射下给出 `PREOUTCOME_COMPARABILITY_PASS`；随后才允许建立 outcome contract 的开封申请。
