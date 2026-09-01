# CN:000541 J0→J1→J2 四臂可行性 cohort

状态：`PREREGISTERED / PREOUTCOME / STAGED_AGENT_AUTHORING`

上一替代 cohort 仍要求 Agent 一次输出完整 Episode，已停止且不计为结果。随后
一次 J0 试运行又显示任务提示对 `economic_scope` 枚举不够明确，Agent 输出了旧
的整账本并被拒绝；该响应不重写、不重试。本 cohort 在此协议事件后使用新合同 ID
（`STAGE7`），并明确每一阶段的允许键和枚举。

每个 arm 严格执行三次隔离阶段：

```text
fresh J0 Agent → J0 ledger → deterministic J0 validator
fresh J1 Agent（只读 accepted J0）→ J1 ledger → deterministic J1 validator
fresh J2 Agent（只读 accepted J0/J1）→ J2 ledger → deterministic J2 validator
                                                ↓
                                   deterministic staged compiler
                                                ↓
                              EnterpriseUnderwritingEpisode v2
```

四臂的唯一差异仍是训练记忆：A00 无记忆，A01 仅行业经验，A10 仅专家纠偏，A11
两者联合。每阶段只允许一次 fresh Codex 响应；任一阶段失败，该 arm 在本 cohort
终止，不手工修答、不 retry。全部四臂完成 Episode 与首次 reader projection 后，
另用 fresh reviewer 做匿名预结果审阅；审阅冻结前不读取 outcome。

编译器只绑定身份、来源、组件 ID、route 角色、覆盖和投影，不选择组件、不补证据、
不把 UNKNOWN 变成零、不猜敏感性、不生成价格/行动。四臂能否形成合法账本是第一层
验收；匿名投资者审阅是第二层；结果结算与第二个未知公司/时间 holdout 才能证明
训练记忆提高投资判断，前两层均不构成能力提升。
