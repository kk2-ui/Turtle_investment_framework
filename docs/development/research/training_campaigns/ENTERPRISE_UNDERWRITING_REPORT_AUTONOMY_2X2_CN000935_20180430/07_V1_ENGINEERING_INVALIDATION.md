# V1 工程失效裁决

> 状态：`PAIRED_TEST_INVALID / OUTCOME_REMAINS_SEALED`

四个 `fork_turns=none` fresh Codex Agent 均按冻结的 V1 任务包完成了一次 Episode 响应；原始响应保存在 `raw_agent_responses/`，未作修改、补写或重试。四份响应经同一 `enterprise-underwriting-training-contract.v2` 校验后均为 `INVALID`，因此 V1 没有进入读者报告、匿名比较或结果开封。

| Arm | 原始响应 | 结果 |
| --- | --- | --- |
| `A00_BASELINE` | `raw_agent_responses/A00_BASELINE_EPISODE_RESPONSE.json` | `INVALID` |
| `A10_EXPERT_ONLY` | `raw_agent_responses/A10_EXPERT_ONLY_EPISODE_RESPONSE.json` | `INVALID` |
| `A01_INDUSTRY_ONLY` | `raw_agent_responses/A01_INDUSTRY_ONLY_EPISODE_RESPONSE.json` | `INVALID` |
| `A11_COMBINED` | `raw_agent_responses/A11_COMBINED_EPISODE_RESPONSE.json` | `INVALID` |

## 根因和经济影响

根因分类为 `ACQUISITION_MODULE / MODEL`：V1 渲染器只声明响应应为一个完整 Episode JSON，却未在 fresh 任务包内交付冻结的完整 JSON Schema。没有仓库读取权的四个 Agent 因而各自构造了替代字段层级，共同缺失或误写 `decision_frame`、`underwriting_route`、`situation_model`、生存/适应/正常化/永久损失叙述、`component_decisions` 权限字段及 `economic_derivation` 嵌套字段。

这意味着错误发生在投资推理进入正式合同之前。任何臂间差异都可能只是对未知结构的猜测，无法判断专家纠偏或行业经验是否改善了正常盈利、owner cash、永久损失或价值路线；把它解释成训练无效或有效都会产生错误的经济结论。

## 禁止假设与修复边界

禁止人工修补四份响应、让某一臂单独重试、依据后续结果改变样本或输入、以及把更长/更悲观的文本视为提升。可执行修复仅为：渲染器向所有四臂交付字节相同的完整 Episode Schema，并明确 `required`、`enum`、`const`、`additionalProperties` 和嵌套规则；其余实验条件保持不变。

V2 的接受条件是四份新合同、四个新 fresh context、每臂一次 Episode、四份均通过同一现行 validator，之后才可机械生成读者 brief 并进行一次首次报告 follow-up。V1 永久保留为无效工程运行，不以 V2 覆盖或改名。
