# Turtle EnterpriseJudgmentEpisode J0 契约实现

> 状态：`IMPLEMENTED / READ_ONLY_COMPOSITION / SYNTHETIC_REGRESSION_VERIFIED`
>
> 日期：2026-08-26
>
> 顶层语义：[企业判断与训练系统顶层架构](TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md) §3.1、§3.2、§8.1、§10.1。

## 1. 交付物

J0 新增 `EnterpriseJudgmentEpisode` 的组合 read model，不新增企业事实、结果、估值或投资真源：

- schema：`schemas/enterprise_judgment_episode_manifest.schema.json`；
- validator/compiler：`scripts/enterprise_judgment_episode.py`；
- 定向回归：`tests/test_enterprise_judgment_episode.py`。

manifest 只保存一个 `company × cutoff` 的既有 artifact 引用、3--5 个公司级问题、claim、机制线程和独立 outcome cell 的状态。实际 outcome 数值、价格、估值、BuyBand、仓位或投资指令在 schema 与运行时均被拒绝。

## 2. 权限与降级语义

每个 claim 有自己的 `cell_status` 和 `dependent_outcome_cell_ids`。compiler 只为未被阻断的 claim 投影该 claim 所属层级的输出：

| 层级 | 可投影视图 |
|---|---|
| `E0_CONTEXT` | `STATE_VIEW`、`RESEARCH_AGENDA` |
| `E1_RECONSTRUCTION` | `STATE_VIEW`、`DECISION_VIEW`、`CJO_TRAINING_MIRROR`、`RESEARCH_AGENDA` |
| `E2_MECHANISM_PROBE` | `MECHANISM_VIEW`、`TEACHING_ONLY`、`RESEARCH_AGENDA` |
| `E3_COMPARATIVE_LAB` | `COMPARATIVE_VIEW`、`COMPARATIVE_CANDIDATE`、`RESEARCH_AGENDA` |
| `E4_TRANSFER_AND_UTILITY` | `TRANSFER_CANDIDATE`、`DECISION_UTILITY_EVALUATION`、`RESEARCH_AGENDA` |

`UNKNOWN`、`EVIDENCE_INELIGIBLE`、`NOT_APPLICABLE` 与 `MEASUREMENT_MISMATCH` 只令依赖该 cell 的 claim 降为 `RESEARCH_AGENDA`。它们不会改变同一 episode 中其他 claim 的输出，也不会将 episode 伪装成全局 `PASS/FAIL`。无论输入层级，J0 的整体输出始终为 `EPISODE_READ_MODEL + RESEARCH_AGENDA`，并明确 `investment_authorization=NOT_AUTHORIZED`。

## 3. 既有真源的绑定

J0 能可选地把 manifest 绑定到当前 `DecisionContract` 与 `enterprise-judgment-v3` bundle；也能绑定 J1 的 `SourcePackage + EnterpriseSystemModel + ManagementDecisionLedger + Reconstruction`。后一条路径会重新编译 J1，逐项验证 company、issuer、cutoff、source packet、component refs、角色和 reconstruction 内容；同一次绑定不能混用 V3 bundle 与 J1 reconstruction。J1 若有日期精度或局部 evidence/decision-observation 限制，E1 claim 也必须继承其局部状态。所有 component reference 都强制 `read_only=true`，compiler 返回深拷贝的 read model，不写入、不升级既有 Forecast、CJO、Comparative、settlement 或 learning artifact。

`E1` 必须已有 `EnterpriseSystemModel` 和 `ManagementDecisionLedger` 引用。`E2` 和 `E3` 的 claim 必须进入一个包含 H-A/H-B、观察时钟与 outcome cell 的线程；只有精确的 `E3` claim 才要求 Comparative 引用。`E4` 的 Forecast/效用迁移路径只要求自己的 Forecast 引用，不被错误强制通过 Comparative。

## 4. 非追溯边界

J0 不读取、不转换或升级现有真实样本、Comparative/V5 freeze、method 状态、CJO、CJO valuation 或 CJO report authority。它只为**新建 manifest**定义组合语义。现有 artifact 仍由原 validator 和 control plane 管理。

## 5. 验收

定向回归覆盖：

1. `MEASUREMENT_MISMATCH` 的 claim 级阻断，不影响同一 E1 operating reconstruction；
2. E2 的 primary + 2--4 supporting threads、H-A/H-B 和 outcome-cell 绑定；
3. E3 只对 Comparative claim 要求自己的引用；
4. E4 可以经 Forecast/utility 路径而不错误依赖 Comparative；
5. schema 闭合、禁止 outcome/price payload，以及现有 bundle 的不可变性。
