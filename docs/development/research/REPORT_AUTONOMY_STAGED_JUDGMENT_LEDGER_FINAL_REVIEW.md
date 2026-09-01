# Staged Judgment Ledger v1 最终独立代码审阅

审阅对象：`scripts/staged_judgment_ledger.py`、`tests/test_staged_judgment_ledger.py`，以及其调用的 Episode/training validators（HEAD `3c87c41`）。本次只读本地代码和测试；未调用外部 API、未读取 outcome/后验资料、未改代码。

## 结论：PASS

实现已关闭此前大部分协议缺陷：compiler 现在要求 contract 与 canonical `source_index`，逐项检查 identity/cutoff/sample、source metadata 和 allowlist；按 contract `time_role` 隔离 `TRAINING_MEMORY`；保留 component 自有 evidence；拒绝重复 claim surface；只允许 FROZEN；编译 v2 derivation 并生成 deterministic summary；并在返回 Episode 前同时运行 generic Episode、contract-specific training 和 downstream projection validators。

最终验收通过：新增 11 个 staged-ledger 测试覆盖状态矩阵、memory role、v2 malformed、projection gate、JSON 往返、source mismatch、component evidence 和 duplicate compile；`WORKED_CASE` 现在同样强制 `PRE_CUTOFF.available_at <= cutoff_at`。定向 staged/training 测试共 53 passed；包含 staged、training、episode 的回归集合共 121 passed。

## 缺陷复核矩阵

| 检查项 | 结果 | 证据/剩余风险 |
| --- | --- | --- |
| contract identity、cutoff、sample、allowed source exact binding | PASS | identity、source_ref、available_at、time_role 与 allowlist 精确绑定；所有 track 的 PRE_CUTOFF 均执行 cutoff gate。 |
| `TRAINING_MEMORY` role 隔离 | PASS | contract/index/ledger 三层 role 均阻断；memory 不进入 Episode evidence surfaces。 |
| v2 economic_derivation bridge/sensitivity 映射和训练校验 | PASS | bridge、sensitivity、summary 确定性映射；malformed derivation fail-closed，并通过 training validator。 |
| 仅 FROZEN 状态 | PASS | 状态矩阵已测试；非 FROZEN 始终 `DIAGNOSTIC_ONLY` 且无 Episode。 |
| component evidence | PASS | 组件保留自身 evidence_ids，source mismatch/缺失引用 fail-closed。 |
| duplicate surfaces | PASS | 重复 surface 在编译前阻断，避免 last-write-wins。 |
| combined validator gate | PASS | generic Episode、training、projection 任一失败均 fail-closed；注入失败测试通过。 |
| 测试覆盖与产物连续性 | PASS | 11 个 staged 测试 + 关联 training/episode 回归共 121 passed；覆盖 JSON roundtrip、诊断 sidecar、状态、memory、v2 malformed、source mismatch、component evidence、duplicate compile、projection gate。 |

## 审阅记录（已关闭）

### `MODEL`：contract=None + derivation 异常（已修复）

经济影响：曾可能抛出异常并绕过统一诊断；现已由 contract 类型守卫和负测关闭。

缺失事实：无。对应负测已补齐并通过。

禁止假设：不得以 generic Episode `REVIEWABLE` 推定 v2 contract 合格；不得假设存在 `normal_earnings_bridge` 键就代表其 rows/quantification 有效；不得假设再次手工调用 training validator 会被所有调用方执行。

可执行修复：已增加类型守卫、状态/memory/v2/projection/JSON/source/component/duplicate 测试。

验收标准：已满足；负例无 episode 且不抛异常，正例 derivation/summary 逐字段一致，combined gate 全部 `REVIEWABLE`。

### `DATA_COVERAGE` + `ACQUISITION_MODULE`：合同来源边界（已关闭）

经济影响：source_ref、available_at、time_role 或 cutoff 错配会把后验/训练记忆材料当成目标公司证据，污染 evidence coverage 及 2×2 treatment effect。

缺失事实：无；source mismatch、metadata mismatch、memory role 和 cutoff 均有 fail-closed 覆盖。

禁止假设：不得把 shape-only validator（不传 index）当作编译验收；不得依赖调用者在 compiler 之后补跑 training validator。

可执行修复及验收：已完成；memory 不进入 claim/component evidence、Episode `evidence_trace` 或 `existing_object_refs`，PRE_CUTOFF cutoff gate 对所有 track 生效。

### 历史 RETURN：WORKED_CASE 的 PRE_CUTOFF 时点检查（已关闭）

此前审阅发现该检查只覆盖 BLIND/PROSPECTIVE。现已移至所有 training tracks 的统一路径，
并由合同负例与全量回归测试确认：任一 track 的 `PRE_CUTOFF` source 在
`available_at > cutoff_at` 时均 fail-closed；合法 cutoff 前 source 与 `RESULT_KNOWN` 规则保持不变。

## 已认可实现

- 输入 deep-copy 与确定性编译保持不变。
- 递归 price/action/return firewall、局部 UNKNOWN 结构和 component treatment/use 冲突检查方向正确。
- diagnostics 统一携带 root cause、经济影响、缺失事实、禁止假设、整改与验收字段。

本审阅范围内可标记为 `READY_FOR_PREREGISTRATION`；本结论不授权读取 outcome、跨公司迁移或生产发布。
