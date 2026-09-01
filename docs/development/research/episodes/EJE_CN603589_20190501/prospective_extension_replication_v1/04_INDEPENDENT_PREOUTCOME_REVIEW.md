# 口子窖 direct judgment calibration：独立结果前审阅

> reviewer：独立于 judgment owner 与未来 outcome custodian
>
> reviewed freeze：commit `d6d9f11`
>
> FY2019 outcome：`UNREAD`
>
> 最终裁决：`ACCEPT`

## 首轮退回

首轮裁决为 `RETURN`，根因为 `REASONING`，次要为 `WRITING`，不是 `DATA_COVERAGE` 或
`ACQUISITION_MODULE`。退回不源于缺少终端动销、经销商库存或陈化 cohort ROIC，而源于原
冻结合同可能让非材料噪声、安徽核心遗漏和毛债机械改变投资结论。

## 六项修复验收

### 1. 高档产品与安徽核心共同结算

`J1_HIGH_END_AND_ANHUI_CORE` 现同时使用高档白酒与安徽省内各自的收入、销量、毛利率。安徽
核心实质走弱时不能再由集团高档产品趋势替代，因此成熟安徽品牌 normal earnings、区域集中
和永久损失判断具有匹配的结果载体。

### 2. 分类互斥穷尽并设置材料区间

三棵分类树均按 `material negative → positive → otherwise` 的固定顺序结算，互斥且穷尽。

高档与安徽核心需要材料性收入、销量和稳定毛利共同支持；省外 breadth 需要至少 `5%` 收入、
`3%` 销量增长和不低于 `-1pp` 的毛利变化。小幅正负波动进入 mixed，不再被命名为 material
reversal 或 joint absorption。

### 3. 净债务和现金缓冲

资金压力改用：

```text
net debt = interest-bearing debt - cash and cash equivalents
```

毛债若被更大的现金余额覆盖，不会单独触发 funding stress。只有 OCF 转负、材料性 adjusted
cash deficit 同时伴随净债务，或净债务超过 OCF 的 50%，才构成资金压力。

### 4. 重大事件具有优先级

正式披露的重大产品安全、召回、停产停销、品牌真实性或重大存货减值/毁损事件位于 cash tree
第一顺位。即使收入、现金和库存匹配条件均为正，也必须结算为
`FUNDING_OR_CORE_ABSORPTION_STRESS`。

### 5. 九类结果均有五维事前更新

三个 cells 的九个 outcome classes 均预先冻结 management、owner cash、permanent loss、
scenario 和 valuation direction。Reviewer 不得在看到结果后重新发明这些更新，也不得把正确
分类或字段完整度当作训练有效。

### 6. 概率与现金语义明确

`judgment_confidence_probability` 是 cutoff 时对当前结构性企业判断的信心，不参与 FY2019
事件评分；categorical probability 是 FY2019 互斥结果分布，用于 Brier-style score。每项结果
已映射为 `SUPPORT / PARTIAL / REFUTE` 或上下方向反驳。

所有 cell 概率与情景概率均合计 `1.00`。Working-capital 字段已改为 `cash_contribution`，并
明确负数表示 working capital used cash，正数表示 working capital supported cash。

## 边界验算

| 边界 | 预期结果 | 验算 |
| --- | --- | --- |
| 高档与安徽指标仅 `-0.01%` | `MIXED_CORE_ABSORPTION` | PASS |
| 高档与安徽指标仅 `+0.01%` | `MIXED_CORE_ABSORPTION` | PASS |
| 省外收入、销量仅 `±0.01%` | `STRUCTURE_LED_OR_MIXED` | PASS |
| adjusted cash 仅为 `±RMB 1`，仍为净现金 | middle/mixed cell | PASS |
| OCF RMB1bn、post-WC cash RMB200m、债务 RMB500m、现金 RMB1bn | 非 funding stress | PASS |
| 其他条件全正但发生重大品牌/安全/存货事件 | funding/core stress | PASS |

## Outcome custodian 最小合同

Custodian 只可读取一份截至 `2020-05-01` 发布的发行人官方 FY2019 完整年报，并只结算 03
冻结的经营、渠道、库存和现金字段及其直接计算。

没有披露终端动销、经销商库存或 cohort ROIC 不得阻断已有字段，也不得把整家公司结算为
UNKNOWN。单个字段口径不匹配只局部标记。

Custodian 不得判断管理层质量、normalized owner cash、永久损失、情景、估值方向或训练有效性；
这些由 fresh reviewer 使用冻结的五维映射完成。

## 权限

本裁决只允许提交 outcome access authorization。`TRANSFER_VALIDATED`、method freeze、
Comparative、CJO、正式估值、BuyBand、报告发布和投资权限均不授予。
