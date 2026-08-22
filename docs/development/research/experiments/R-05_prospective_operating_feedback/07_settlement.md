# R-05 追加结算

状态：`NOT_YET_DUE`

本文件在结果到期前创建，但不预写结果。`06_forward_freeze.md` 中的共同事实、H-A/H-B、阈值、窗口和允许来源不可修改；每个到期结果须先按 [08 outcome acquisition contract](08_outcome_acquisition_contract.json) 完成结果源枚举、raw/reader、读取审计和逐字 extraction，再以事件唯一的 `settlement_id` 调用 `live_forward_signal_settlement settle --event-root <R-05 output>`。S1 与 S2 分别写入 `outcome_events/<settlement_id>/09_signal_settlement.json`，同一事件的 feedback 位于 `outcome_events/<settlement_id>/10_judgment_feedback.json`；CLI 拒绝同 ID 覆盖，故后续 S2 不会替换 S1。每个可比较 extraction 片段还必须同时含 `Q1/Q3 Fiscal Year 2027` 的冻结期间锚点、`North America Change in Transactions` 标签和数值；不得从同表的比较期间列取数。以下表格只按事件转录该生成物；没有该链时保持 `NOT_YET_DUE / INCOMPLETE`，不得手填值、手写机制胜负或挑选一个有利披露。

| signal | 结果 source package / source ID | 同口径原文与定位 | 实际值 | 定义比较 | 机械结果 | 对机制箭头的更新 | 不可回答的内容 |
|---|---|---|---:|---|---|---|---|
| `R05-S1` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | 服务动作因果归属、公司总判断、估值与回报 |
| `R05-S2` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | `NOT_YET_DUE` | 服务动作因果归属、公司总判断、估值与回报 |

## 预注册结算解释

- 单一信号结果：`> 0%` 且同定义 → 对该信号记 `SUPPORTS_PRIMARY`；`<= 0%` 且同定义 → 记 `SUPPORTS_RIVAL`；定义变更、源不合格或未披露 → `NOT_DIAGNOSTIC`。
- 合并结果：两次皆 primary → 仅将“持续客户频次”箭头记 `SUPPORTS_PRIMARY`；两次皆 rival → 记 `SUPPORTS_RIVAL`；方向相反、任一不可比或未到期 → `MIXED / NOT_DIAGNOSTIC / NOT_YET_DUE`，不宣布公司路径胜负。
- 误差归因顺序：先检查指标定义和来源边界，再检查共同因素是否使信号非诊断，最后才讨论机制假设。禁止用后来的管理层解释、盈利、现金、股价或回报回填本表。
