# CN:000541 四臂可行性替代 cohort（修复后）

状态：`PREREGISTERED / PREOUTCOME / NO_RETRY_WITHIN_ARM`

本 cohort 由 `REPORT_AUTONOMY_FIVE_PHASE_SECOND_UNSEEN_ISSUER_000541_20181231`
的协议事件触发，但不是对任何已执行臂的重试。原 cohort 的 A10 一次执行因
route-role 绑定冲突被 validator 拒绝，未读取 outcome、未生成 reader projection，
也未产生可比较的四臂结果。其失败保留为 `REASONING/MODEL` 边界事件；本目录使用
新的合同 ID（`STAGE5R`）和新的执行目录，在离线澄清 route 角色后重新预注册。

公司仍是此前未见训练对象 `CN:000541`；四个 fresh Agent 只读取各自 task packet，
不能读取本目录之外的 Episode、兄弟输出、结果、价格或外部模型 API。每个 arm 只
允许一次响应和一次 `run --agent-response`，不允许修补、重试或回填。四臂全部通过
Episode validator 和首次 reader projection 后，才可交给独立 fresh reviewer 做匿名
预结果审阅；在审阅冻结前 outcome 保持封存。

本 cohort 的离线修复仅是把 primary、corroborative、stress、excluded 的 route
角色互斥关系写入训练任务提示，不放宽 validator，不新增 hash、fingerprint 或
其他校验脚手架。
