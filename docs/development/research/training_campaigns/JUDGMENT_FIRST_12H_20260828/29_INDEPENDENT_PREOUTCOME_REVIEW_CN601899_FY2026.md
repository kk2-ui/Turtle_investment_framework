# CN601899 FY2026 future holdout：独立结果前审阅

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> holdout：`FUTURE_HOLDOUT:CN601899:20260501:FY2026:V1`
>
> reviewer：`/root/unknown_escape_runtime_review`
>
> reviewed freeze commit：`04a08c5`
>
> 最终裁决：`ACCEPT`

## 审阅范围与隔离

本审阅只读取并核对冻结提交中的以下两个结果前工件：

- `27_FROZEN_FUTURE_HOLDOUT_CN601899_FY2026.json`；
- `28_CN601899_PREOUTCOME_INVESTOR_JUDGMENT.md`。

审阅者没有读取 FY2026 中报、FY2026 其他经营材料、FY2026 完整年报、证券价格、回报、旧派生报告或其他新增材料。审阅只判断选择与冻结逻辑、三个 outcome cell、企业判断及权限边界，不预判 FY2026 结果。

## 首轮 RETURN：三个材料问题

首轮裁决为 `RETURN`，根因均为 `MODEL + REASONING`，不是要求补充更多结果前材料。

### 1. 经营 cell 可能把口径变化当作经济吸收

原规则没有强制方向性分类以 `COMPARABLE` 或 `BRIDGED` perimeter 为前提。并购扩表后，即使合并产量、成本和毛利表面改善，只要责任边界没有桥接，也可能被误判为同口径经济吸收。另一个问题是 `CORE_VOLUME_AXIS_IS_NOT_UP_BOTH` 会把 `UNKNOWN` 包含在内，使“产量未知、单位经济改善”先进入方向性分类，而不是保留局部未知。

经济影响是高估经营执行和 normalized earnings，并把并购范围变化误作矿山经济改善。

要求的修复是：`UNBRIDGED` 先结算为 `MEASUREMENT_MISMATCH`；所有方向分类只接受 `COMPARABLE|BRIDGED`；`NOT_UP_BOTH` 收窄为已观察的 `DOWN_BOTH|MIXED`。

### 2. 现金 cell 可能把 allocation/NCI 后负现金称为 parent owner cash

原规则只要求 group post-organic-capex proxy 为正及 maintenance、parent access、NCI scope 闭合，却没有消费已经冻结的 acquisition cash 和 NCI distributions 后现金桥。

反例为：group proxy `+100`、acquisition cash `120`、NCI distributions `20`，所有 scope 均 closed。原规则会进入 `NORMALIZED_PARENT_OWNER_CASH_SUPPORTED`，但 post-allocation view 实际为 `-40`。

经济影响是高估普通股可得现金、低估并购与少数股东资金负担，并可能错误上修 owner-cash 估值。

要求的修复是分列 post-NCI claim 与 post-allocation burden；NCI claims 消耗 group proxy 时不得升级 owner cash，收购使 post-allocation 不为正时只形成局部资本配置负担，不自动传播为永久损失。

### 3. 永久损失 cell 会让改善轴抵消未覆盖资金风险

原 `MIXED_CARRIERS` 位于 `PERMANENT_LOSS_RISK_UP` 之前。若 near-term liquidity 已经 `DETERIORATED_OR_UNFUNDED`，而 asset-loss carrier 改善，规则会先写成 mixed，弱化真实的到期与被迫行动风险。

经济影响是低估 distress discount 和永久损失风险。

要求的修复是：任一 liquidity unfunded、asset risk-up 或 provision eroded 必须优先结算 `PERMANENT_LOSS_RISK_UP`；一个载体改善不能替另一 adverse carrier 投票。

## 第二轮 RETURN：两个穷尽性缺口

第一轮三个方向性错误修正后，第二轮机械复验仍发现两个同轴缺口，裁决继续为 `RETURN`。

### 1. 披露缺值与 measurement mismatch 仍然重叠

当 perimeter 已可比或已桥接、unit economics 可观察但 core volume 未披露时，宽泛的“cannot match”仍可能先触发 `MEASUREMENT_MISMATCH`。这会把普通披露缺口误作测量定义失败，并可能错误产生 coverage 学习信用。

要求的修复是明确分开：只有已经披露的定义、期间或责任边界与冻结定义冲突且无法桥接，才是 mismatch；框架可比但值缺失或方向不明，必须是局部 `UNKNOWN`。

### 2. 现金 cell 没有覆盖下游代理未知

当 group proxy 为正，但 NCI distributions 未披露使 post-NCI proxy 未知，或 post-NCI 为正但 acquisition cash 未披露使 post-allocation 未知时，原修订没有任何 first-match 可命中。

经济影响是局部披露缺口再次使整个现金 cell 停止，而不是继续形成公司判断。

要求的修复是增加 `POSITIVE_GROUP_PROXY_SCOPE_OPEN`：明确覆盖 post-NCI unknown、post-allocation unknown，以及 maintenance、parent access 或 NCI scope open/unknown；该结果只能限制 owner cash 与资本配置轴，不能传播到永久损失。

## 最终机械反例复验

在冻结提交 `04a08c5` 上，审阅者重放了原三项和新增两项反例，结果如下：

| 反例 | 冻结 first-match 结果 | 裁决 |
| --- | --- | --- |
| perimeter unbridged，表面产量和单位经济改善 | `MEASUREMENT_MISMATCH` | 通过；并购扩表不能冒充经济吸收 |
| perimeter comparable/bridged，volume unknown、unit economics preserved | `UNKNOWN` | 通过；缺值不冒充 mismatch，也不由另一轴替代 |
| group `+100`、NCI `20`、acquisition `120`、所有 scope closed | `POSITIVE_POST_NCI_CLAIM_WITH_ALLOCATION_BURDEN_ADVERSE` | 通过；不进入 normalized owner cash，不跨轴传播 |
| group proxy 正但 post-NCI proxy 不为正 | `POSITIVE_GROUP_PROXY_CONSUMED_BY_NCI_CLAIMS` | 通过；已知 claim 方向不会被未知擦除 |
| group proxy 正但 post-NCI unknown | `POSITIVE_GROUP_PROXY_SCOPE_OPEN` | 通过；未知只限制现金轴 |
| post-NCI 正但 post-allocation unknown | `POSITIVE_GROUP_PROXY_SCOPE_OPEN` | 通过；不补造收购金额或现金方向 |
| liquidity unfunded、asset-loss risk down | `PERMANENT_LOSS_RISK_UP` | 通过；资金 adverse carrier 优先 |
| liquidity improved、asset-loss risk up | `PERMANENT_LOSS_RISK_UP` | 通过；资产损失不能被流动性改善抵消 |

三个 outcome cell 的 first-match 已能对材料状态作唯一、穷尽的处理。已观察的 adverse carrier 优先保留，`UNKNOWN` 只限制依赖它的经营、owner-cash 或永久损失局部主张，不取消其他已经支持的公司判断。

## 为什么 28 不是防御性写作

`28_CN601899_PREOUTCOME_INVESTOR_JUDGMENT.md` 没有把证据边界当作公司结论，也没有因 maintenance、parent access、NCI、项目级利用率或未来地缘事件未知而停止判断。它明确给出：

1. 生产部署和多项目执行强，但经济吸收仍需同口径产量与单位经济共同验证；
2. 集团内部融资能力真实增强，但 normalized parent owner cash 尚未闭合；
3. 当前不支持迫近流动性危机，永久损失仍为 `LOW_TO_MEDIUM_CONDITIONAL`，由期限、矿权、停产、减值和复垦载体分别更新。

每项判断均包含经济机制、最强反方和会翻转判断的 FY2026 事实。文档同时给出乐观、基准、悲观三种经营情景和不带价格的估值方向，没有用伪精确概率或模板完整度冒充判断。局部未知只决定是否升级 owner cash、资本配置或永久损失折价，不撤回生产执行、集团现金能力和当前流动性位置。

## 最终裁决与权限

最终裁决为 `ACCEPT`。该裁决只确认结果前选择、企业判断和三个 outcome cell 已足以进入未来结算；它不确认任何 FY2026 结果，也不证明训练方法有效。

当前状态保持：

```text
outcome_access             SEALED
current_feedback_credit    NONE
learning_authorization     NONE
transfer_candidate         NONE
transfer_validated         NONE
method_freeze              NONE
Comparative                NONE
CJO                        NONE
formal_valuation           NONE
BuyBand                    NONE
report_publication         NONE
investment_action          NONE
```

只有完整 FY2026 官方年报存在后，才可另行授权独立 custodian 按 27 中已冻结的三个 cell 做局部结算。在此之前不得读取中报或其他 outcome 资料，不得重选公司、cell、阈值或 first-match，也不得把本次 `ACCEPT` 计作第七轮反馈。
