# Course 2C 两臂原生子 Agent 运行预检

> 状态：`OFFLINE_PREFLIGHT_PASSED / NATIVE_SUBAGENT_RUNTIME_PENDING`

- 执行链固定为：当前 Codex 主 Agent → 两个 `fork_turns=none` fresh 子 Agent → `run --agent-response` 绑定完整 Episode → 第三个 fresh 子 Agent 匿名两阶段审阅。
- 不使用 `--provider`，不调用 Anthropic、OpenAI、DeepSeek 或其他外部模型 API；如果平台不能提供原生 fresh Codex 子 Agent，实验保持冻结且不以任何 provider fallback 代替。
- 两臂同模型、同 reasoning、同 task 预算、同 Episode schema 和同两个共同源包。Enhanced 只多看 Context 与训练记忆，且不能引用为公司证据。
- 每臂一次正式 run；若任何合同或 Episode 绑定失败、输出截断、读取非 allowlist、混入结果/价格/投资动作，停止本轮，不手改答案或重跑来制造公平比较。
- Context 是 `BOUNDED / REVIEWABLE`：它可提出行业与组件问题，但不能替代目标公司取证，也不能以 peers 缺失拒绝整家公司判断。
