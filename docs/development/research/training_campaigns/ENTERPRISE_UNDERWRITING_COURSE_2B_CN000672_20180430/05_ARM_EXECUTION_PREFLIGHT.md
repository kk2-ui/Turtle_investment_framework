# Course 2B 两臂原生子 Agent 运行预检

> 状态：`OFFLINE_PREFLIGHT_PASSED / NATIVE_SUBAGENT_RUN_AUTHORIZED`

- 默认执行链：当前 Codex 主 Agent → 两个 `fork_turns=none` fresh 子 Agent → `run --agent-response` 合同绑定并保存完整 Episode。`--provider` 不进入本实验。
- 两臂均继承当前 Codex 的同一模型和 reasoning 配置，不作单臂覆盖；各自只读取 `render-subagent-task` 生成的临时 task packet、共同 Episode schema 和同一 validator 实现，并只写一个 Episode JSON 响应。这两份共同输出合同不是公司证据。
- 正常上限为 2 个原生子 Agent turn、每臂 1 次正式 run；不允许 provider replay、API fallback、网页搜索、结果访问或由当前协调会话代写。
- Baseline 与 Enhanced 使用同一模型、系统 prompt、Episode schema、反馈时钟和两个共同源包。Enhanced 只多读目标 Context 与通用训练记忆，两者均不可作为公司证据。
- 认知隔离：除共同 Episode schema/validator 外，两臂不得读取父会话、另一臂目录、Pack 原文、Course 1 公司结论、task packet 以外的仓库资料或结果期资料。
- 离线门：目标 Context=`READY`；两份合同=`REVIEWABLE`；fresh-subagent 正式运行入口、Context 与 Episode 定向回归通过后才启动。
- 停止条件：任一合同/完整 Episode/来源绑定验证失败，或模型输出截断、混入价格/结果/投资动作；此时停止，不用另一臂或事后手改答案制造公平比较。
- 运行成功即冻结模型生成的完整 Episode；投资者读本只由冻结 Episode 通过现有确定性 renderer 生成。运行不发布报告，也不产生估值或投资权限。

此前 Anthropic 试跑在生成 Episode 前返回 401，未形成任何 arm 样本或训练产物；该路径已废弃。本实验不调用 `codex exec` 或任何外部模型 API，只使用编排器自身的原生子 Agent。
