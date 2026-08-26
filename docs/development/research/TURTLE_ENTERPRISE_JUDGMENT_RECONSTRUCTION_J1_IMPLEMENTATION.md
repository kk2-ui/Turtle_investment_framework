# Turtle EnterpriseJudgmentEpisode J1 重建实现

> 状态：`IMPLEMENTED / CUTOFF_SAFE / READ_ONLY / SYNTHETIC_REGRESSION_VERIFIED`
>
> 日期：2026-08-26
>
> 顶层语义：[企业判断与训练系统顶层架构](TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md) §3.1、§3.2、§8.1、§10.1。

## 1. 交付物与唯一链路

J1 把一个 `company × cutoff` 的企业重建投影为只读 read model；它不生成结果、价格、估值、仓位、CJO freeze 或投资授权。

- 日期精度 source receipt：`schemas/enterprise_judgment_source_packet_receipt.schema.json`、`scripts/enterprise_judgment_source_packet.py`；
- J1 spec：`schemas/enterprise_judgment_reconstruction.schema.json`、`scripts/enterprise_judgment_reconstruction.py`；
- J0 binding：`scripts/enterprise_judgment_episode.py`；
- 回归：`tests/test_enterprise_judgment_source_packet.py`、`tests/test_enterprise_judgment_reconstruction.py`。

可执行链路为：

```text
SourcePacketReceipt
  -> conservative core SourcePackage
  -> EnterpriseSystemModel + append-only ManagementDecisionLedger
  -> J1 Reconstruction
  -> bound J0 EnterpriseJudgmentEpisode manifest
```

J1 只接受同一 `DecisionContract` 的公司、issuer、cutoff、source packet 和三角色。J0 在实际绑定时会重新编译 J1 并逐项比较 reconstruction、component refs、company/issuer/cutoff 与角色；不能用任意 ID、另一种 V3 bundle 或替换 custodian 冒充同一对象。

## 2. PIT 与责任边界

`SourcePacketReceipt` 不把只有发布日期的资料写成假精确时分秒。它保存 `published_on`、`available_on`、`availability_timezone`；转给 core 时使用该当地日的 `23:59:59` 作为**保守可得上界**，并在 read model 写明 `CONSERVATIVE_END_OF_STATED_DAY`。这不会声称实际发布时间，只保证 source 不会因早取而越过 cutoff。

每个 feedback loop 必须同时满足：

1. 变量、机制、传导和已观察的决策在同一个责任单元与 competitive arena；
2. loop 的 source、变量、机制、传导和决策 evidence 都覆盖该责任边界；
3. 已观察的决策必须同时存在于 cutoff 前 append-only ledger，且绑定 selected mechanism；
4. loop 只保留 2--3 条材料性传导，不把公司所有指标混入一个全局得分。

目前没有已实现的 scope bridge 形状；因此跨责任边界的 loop 直接拒绝，而不是暗中聚合。

## 3. 局部证据状态与无行动路线

compiler 为 variable、mechanism、financial transmission、decision 与 loop 输出 `evidence_coverage`。`EVIDENCE_INELIGIBLE`、`UNKNOWN` 只列为相应 component 的 `blocked_component_ids`；其他有合格直接支持的 loop/claim 仍可留在 E1。J0 的 bound manifest 还会拒绝用全是 `EVIDENCE_INELIGIBLE` 的 source 激活 `OBSERVED` 或 `INFERRED` 的 E1 claim。

空 ledger 是合法的中性容器，不自动等于“没有行动”。J1 的闭合 `decision_observation` 必须显式区分：

| 状态 | 可声明的范围 | 决策 ID |
|---|---|---|
| `MATERIAL_DECISION_OBSERVED` | cutoff 前、ledger-backed 的材料性行动 | 非空且与 loop union 相同 |
| `NO_MATERIAL_DECISION_OBSERVED` | 仅在 reviewed source refs 与 materiality scope 内未观察到行动 | 必须为空 |
| `INSUFFICIENT_EVIDENCE` | 资料不足，不能把沉默写成无行动 | 必须为空 |

后两条路线不得选择带有 `management_decision_ids` 的 mechanism。若 manifest 的 claim 明确依赖该 observation，J0 机械要求 `NO_MATERIAL... -> NOT_APPLICABLE`、`INSUFFICIENT... -> UNKNOWN`；企业状态 claim 不依赖它时仍可获得自己的 E1 输出。因此“没有已识别行动”不阻断企业全景重建，也不会被升级为 J2/E3。

## 4. 权限边界

J1 输出仅限 `RECONSTRUCTION_READ_MODEL + CJO_TRAINING_MIRROR + RESEARCH_AGENDA`，且永远标示 `investment_authorization=NOT_AUTHORIZED`。`CJO_TRAINING_MIRROR` 只是 J0 层级可消费的视图名，不是 CJO freeze、结果结算、方法学习或投资输入授权。

Comparative、同行 panel、Forecast、估值、BuyBand、价格、结果 value 和 settlement payload 都在 schema 与运行时拒绝。J1 不追溯更改现有 Comparative/V5、CJO、Forecast、method freeze 或真实样本的生命周期。

## 5. 验收覆盖

定向回归覆盖日期精度/PIT、post-cutoff source、同一责任边界、不可用现金证据的局部降级、cutoff 后 ledger event 排除、无材料行动与资料不足边界、DecisionContract/custodian/reconstruction 替换，以及 J1 到 J0 的真实绑定。 
