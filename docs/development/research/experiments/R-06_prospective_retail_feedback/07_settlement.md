# R-06 结果期追加结算

状态：`NOT_YET_DUE`。

本文件只能在冻结后追加结果观察。不得回写 `00_iteration_card.md`、机制、阈值、窗口或结果来源政策。每项观察先经 [08 outcome acquisition contract](08_outcome_acquisition_contract.json) 的候选源枚举、raw/reader、读取审计和逐字 extraction，再以事件唯一的 `settlement_id` 调用 `live_forward_signal_settlement settle --event-root <R-06 output>`；不同到期时钟分别保存为 `outcome_events/<settlement_id>/09_signal_settlement.json`，同一事件的 feedback 为 `outcome_events/<settlement_id>/10_judgment_feedback.json`。CLI 拒绝同 ID 覆盖，S2 不会覆盖 S1。每个可比较 extraction 片段还必须同时含 `Q4 FY27` 或 `Q2 FY28` 的冻结期间锚点、`Walmart U.S. Transactions` 标签和数值，不能从同表 `FY26/FY27` 的比较期间列取数。缺任何一环时不结算，不能用手填值、手写机制胜负、替代 KPI 或有利版本补足。
