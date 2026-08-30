# Course 2B 上峰水泥公司轴：完成审计

> 审计结论：`COMPANY_HOLDOUT_COMPLETE / NO_MATERIAL_UTILITY / PACK_TRAINING_READY / MODEL_INTERFACE_REVISED / METHOD_NOT_VALIDATED`
>
> 开发基线：本地 `main@9376038a9c20acd6e15b745e4f3b685287a1cc0b`
>
> 样本：`CN:000672` 上峰水泥，cutoff `2018-04-30T23:59:59+08:00`

## 结论先行

Course 2B 已完成未见公司轴的公平 A/B，但没有证明 Enhanced 相对 Baseline 带来材料性投资判断效用。两臂都正确识别了价格主导且周期条件化的水泥利润池、华东成熟核心、正常 owner cash 与当期资本吸收的区别、增长/房地产资本边界和组合式永久损失路径；FY2018--FY2020 结果没有显示 Enhanced 独有地改变正常盈利、owner cash、永久损失或价格前价值路线。

因此最终裁决保持：行业路径与公司传导均为 `NO_MATERIAL_DIFFERENCE`，整体为 `NO_MATERIAL_UTILITY`。水泥 Pack 维持 `TRAINING_READY`，不升 `TRANSFER_CANDIDATE`；方法、迁移、时间轴和发布均未验证。这个负结果是诚实的能力边界，不用更多样本、文字或状态标签覆盖。

## 实验完整性与冻结裁决

| 要求 | 审计证据 | 裁决 |
| --- | --- | --- |
| 未见公司与 cutoff 预注册 | `00_EXPERIMENT_PREREGISTRATION.md` 与 `01_FROZEN_SAMPLE_AND_FAIRNESS_REGISTER.json` 固定上峰及 cutoff | `COMPLETED` |
| 同证据、同合同、认知隔离双臂 | 两个 `fork_turns=none` fresh Codex 子 Agent 分别完成 Baseline 与 Enhanced；两份 Episode 均由正式 `run --agent-response` 绑定并保存 | `COMPLETED` |
| 独立匿名审阅 | 第三个 fresh Reviewer 依次完成结果前、结果后与映射揭示审阅 | `COMPLETED` |
| 冻结最终映射 | `13_FRESH_REVIEW_FINAL_MAPPING_ADJUDICATION.md`：Arm A=Enhanced，Arm B=Baseline；双层均无材料差异 | `FROZEN` |
| Pack 状态 | 追加 `COMPANY_HOLDOUT / NO_MATERIAL_UTILITY` 后，validator 仍派生 `TRAINING_READY` 且无 findings | `REVIEWABLE` |

`00`--`13` 的实验、双臂 Episode、stored bundle、readout 和审阅裁决均未因后续代码修订而回填或改写。当前代码重放两份冻结 v1 Episode 时，bundle 与 readout 分别与存档对象完全相等。

## 失败归因与可执行修订

### `MODEL`：组件标签没有唯一决定下游经济用途

原接口允许不同组件结构最终收敛到相同价值路线，甚至可让一个无关 primary 组件掩盖被排除成熟核心仍进入 EPV。未来 v2 合同现要求：

- 每个组件显式决定正常盈利、owner cash、融资压力、永久损失与估值用途；
- 每条估值路线绑定具体组件及 route-specific use；
- 每条路线声明必需组件和可选组件；必需组件被排除时，无关组件不能以同名路线替代；
- 可选组件被排除不使合法路线整体失效；
- 五条经济路线由 compiler 确定性派生，并由 CJO、valuation、report handoff 与 reader brief 消费。

历史 v1 不可借 schema 降级绕过：只允许与显式登记仓库合同完整 JSON 相同的 `validate-episode / compile-bundle` 冻结回放，不能 render 或 run 新 Agent。

该修订关闭的是本轮暴露的模型接口缺陷，**不等于方法已经有效**。它仍须由未来新的、重新预注册且认知隔离的实验验证，不能反向改变本轮 `NO_MATERIAL_UTILITY`。

### `DATA_COVERAGE`：未来新实验的 acquisition 前提

本轮结果仍不能唯一拆出经济维护资本、规范化营运资本、房地产 OCF、全部长期投入、逐 cohort 回报和连续区域量价/利用率。按负结果停止条件，本轮没有新增样本、年份、字段或时间轴。

若未来另行授权新实验，应先改进可复用 acquisition 与同责任边界资本桥，再交给两臂；不得用机械 `OCF - 长期资产购建`、全国量价或更长文字代替这些数据。此项是未来前提，不是当前 completion blocker。

## 工程与独立验收

- 定向回归：`69 passed`，覆盖训练合同、完整 Episode、行业经验 Pack 与 IndustryUnderwritingContext。
- Pack validator：`REVIEWABLE / declared TRAINING_READY / derived TRAINING_READY / findings=[]`。
- legacy 回放：任意新建、改 ID、改 payload 或 v2 降级的 v1 均失败；冻结 v1 只可验证和编译回放。
- 组件变异：正常盈利、owner cash、融资压力、永久损失和估值用途分别改变对应下游结构；被排除核心不能保留 EPV 主路线。
- required/optional 依赖：同名 route 重新绑给无关组件仍为 `INVALID`；合法 optional exclusion 保持 `REVIEWABLE`。
- 原 fresh 独立代码 Reviewer 经三轮材料性 RETURN 与修复后最终 `PASS`；两个 `MODEL` blocker 均关闭。
- 未调用 Anthropic、OpenAI、DeepSeek 或其他外部模型 API。

## 权限与下一状态

```text
COURSE_2B_COMPANY_HOLDOUT = COMPLETE
OVERALL_UTILITY = NO_MATERIAL_UTILITY
PACK_STATE = TRAINING_READY
MODEL_INTERFACE_REVISED = YES
METHOD_VALIDATED = NO
TRANSFER_VALIDATED = NO
TIME_AXIS_VALIDATED = NO
RELEASED = NO
```

本轮不产生估值、BuyBand、CJO freeze、黄金报告发布、投资权限或新训练样本。Course 2B 至此收口；若以后继续，应以新的 Goal 和预注册实验验证修订后的接口，而不是继续修改本轮冻结答案。
