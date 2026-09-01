# Staged Judgment Ledger v1 最终独立代码审阅

审阅对象：`scripts/staged_judgment_ledger.py`、`tests/test_staged_judgment_ledger.py`，以及其调用的 Episode/training validators（HEAD `81176a9`）。本次只读本地代码和测试；未调用外部 API、未读取 outcome/后验资料、未改代码。

## 结论：RETURN（未达到最终接纳）

实现已关闭此前大部分协议缺陷：compiler 现在要求 contract 与 canonical `source_index`，逐项检查 identity/cutoff/sample、source metadata 和 allowlist；按 contract `time_role` 隔离 `TRAINING_MEMORY`；保留 component 自有 evidence；拒绝重复 claim surface；只允许 FROZEN；编译 v2 derivation 并生成 deterministic summary；并在返回 Episode 前同时运行 generic Episode、contract-specific training 和 downstream projection validators。

但最终验收仍应 RETURN：新增 11 个 staged-ledger 测试已覆盖状态矩阵、memory role、v2 malformed、projection gate、JSON 往返、source mismatch、component evidence 和 duplicate compile；定向测试共 121 passed。仍发现材料性 cutoff 缺陷：training contract 对 `WORKED_CASE` 不强制 `PRE_CUTOFF.available_at <= cutoff_at`，因此过截止日的材料可被标记为可审阅。

## 缺陷复核矩阵

| 检查项 | 结果 | 证据/剩余风险 |
| --- | --- | --- |
| contract identity、cutoff、sample、allowed source exact binding | RETURN | identity/source metadata/allowlist 已绑定；但 `validate_training_contract` 只在 BLIND/PROSPECTIVE 分支检查 PRE_CUTOFF 的 available_at，WORKED_CASE 可接受明显晚于 cutoff 的 PRE_CUTOFF 来源。 |
| `TRAINING_MEMORY` role 隔离 | PASS（代码）/测试不足 | contract role、index provenance、ledger provenance 均会阻断；`_evidence_trace` 不把 memory 写入 Episode。缺少 claim/component/evidence_trace/existing_object_refs 四个表面及 A01/A10/A11 fixture。 |
| v2 economic_derivation bridge/sensitivity 映射和训练校验 | PASS（主路径）/测试不足 | ledger 字段映射到 Episode `economic_derivation` 并生成 summary，且调用 `validate_training_episode`；新增正例通过。仍缺 bridge/sensitivity 非法结构和 magnitude-evidence 负例。 |
| 仅 FROZEN 状态 | PASS（代码）/测试不足 | `LEDGER_NOT_FROZEN` 是 blocking，非 FROZEN 不生成 Episode；缺少 DRAFT/COMPILED/DIAGNOSTIC_ONLY/REJECTED 矩阵测试。 |
| component evidence | PASS（代码）/测试不足 | component treatment 使用各自 `evidence_ids`，不再复制 BUSINESS_POSITION evidence；Episode validator 检查引用存在。缺少多 component、跨 evidence 和缺失 evidence 负测。 |
| duplicate surfaces | PASS（代码）/测试不足 | surface set 在重复前检查，compiler 不再静默 last-write-wins；缺少重复 surface 编译阻断测试。 |
| combined validator gate | PASS（代码）/测试不足 | generic Episode、training episode、projection bundle 任一失败均不返回 episode；缺少专门 gate 失败断言。 |
| 测试覆盖与产物连续性 | PASS（当前范围） | `.venv/bin/python -m pytest -q tests/test_staged_judgment_ledger.py tests/test_enterprise_underwriting_training.py tests/test_enterprise_underwriting_episode.py`：`121 passed`；11 个 staged 测试含 JSON、状态、memory、v2 malformed、source mismatch、component evidence、duplicate compile 和 projection gate。 |

## 必须关闭的 RETURN（根因、影响与修复）

### `WRITING`：剩余测试收据不足以完成最终接纳

经济影响：当前实现和新增负测已证明无 contract + derivation 会 fail-closed；剩余问题是缺少对其他材料性拒绝路径的自动收据，可能让未来回归在进入 cohort 前未被发现。

缺失事实：derivation 非法结构、route/component 冲突、magnitude evidence 缺失、四种 memory arm、状态矩阵、projection gate 注入及 JSON sidecar 往返的 staged 负例。

禁止假设：不得以 generic Episode `REVIEWABLE` 推定 v2 contract 合格；不得假设存在 `normal_earnings_bridge` 键就代表其 rows/quantification 有效；不得假设再次手工调用 training validator 会被所有调用方执行。

可执行修复：补齐上述负测，逐项断言 `DIAGNOSTIC_ONLY`、无 episode、诊断字段完整；增加 JSON serialize/parse 往返及 projection gate 失败注入测试。

验收标准：所有上述负例均无可消费 `episode`、不抛异常；正例的 `economic_derivation` 和 deterministic summary 与输入逐字段一致，且 combined gate 三个 validator 全部 `REVIEWABLE`。

### `DATA_COVERAGE` + `ACQUISITION_MODULE`：合同来源边界尚无可执行收据

经济影响：source_ref、available_at、time_role 或 cutoff 错配会把后验/训练记忆材料当成目标公司证据，污染 evidence coverage 及 2×2 treatment effect。

缺失事实：每种 mismatch（identity、cutoff、sample、source_id、source_ref、available_at、time_role、未 allowlisted、TRAINING_MEMORY）对应的 blocking diagnostic/state。

禁止假设：不得把 shape-only validator（不传 index）当作编译验收；不得依赖调用者在 compiler 之后补跑 training validator。

可执行修复及验收：为四种 memory arm 和 PRE_CUTOFF/RESULT_KNOWN source 各建 fixture；逐项断言 `DIAGNOSTIC_ONLY`，且 memory 永不出现在 claim/component evidence、Episode `evidence_trace` 或 `existing_object_refs`。

### `DATA_COVERAGE`：WORKED_CASE 的 PRE_CUTOFF 时点检查缺失

经济影响：过 cutoff 的材料可进入 WORKED_CASE 的 allowlist，导致回看时使用未来信息，扭曲判断质量与训练臂比较。

缺失事实：`allowed_sources[].time_role == PRE_CUTOFF` 时必须满足 `available_at <= cutoff_at` 的统一规则。

禁止假设：不得因 WORKED_CASE 允许 `RESULT_KNOWN` 就放宽 PRE_CUTOFF 的时点约束；两种 time role 必须分别校验。

可执行修复：将 PRE_CUTOFF 时点检查移出 BLIND/PROSPECTIVE 条件，对所有 training tracks 生效；增加 WORKED_CASE 过 cutoff 负测并断言 contract/compile 均 `DIAGNOSTIC_ONLY`。

验收标准：任何 track 的 PRE_CUTOFF source 在 `available_at > cutoff_at` 时均被拒绝；合法 cutoff 前 source 保持通过，RESULT_KNOWN 仍按 track 规则处理。

## 已认可实现

- 输入 deep-copy 与确定性编译保持不变。
- 递归 price/action/return firewall、局部 UNKNOWN 结构和 component treatment/use 冲突检查方向正确。
- diagnostics 统一携带 root cause、经济影响、缺失事实、禁止假设、整改与验收字段。

在补齐上述测试收据前，状态应保持 `DESIGN_ONLY`/`PENDING_REVIEW`；不得用于 fresh cohort 冻结或 outcome gate。
