# R-56｜晶科 2010 一体化扩产：多层机制实验与结果前冻结

状态：`FROZEN_MECHANISM_SIGNAL_PROBE / NO_PRIMARY / OUTCOME_BODY_UNREAD`。

## 1. 冻结身份与共同事实

- freeze ID：`R-56:JINKOSOLAR:INTEGRATED_EXPANSION:20100513`。
- cutoff：`2010-05-13T23:59:59-04:00`。
- 允许源：仅 [JinkoSolar Form 424B4](https://www.sec.gov/Archives/edgar/data/1481513/000119312510120053/d424b4.htm)，filed/prospectus date 2010-05-13。
- 结果期禁止读取：FY2010 Form 20-F 的正文、表格、XBRL、任何后续披露、新闻、行业回顾、证券价格和回报。
- 判断等级：`MECHANISM_SIGNAL_PROBE`。选择状态：`NO_PRIMARY`；无 selection baseline，也不得输出“研究者选对 H-A/H-B”。

双方必须解释的共同事实：

1. 需求在 2009 年中以后恢复，但售价仍显著低于危机前，补贴缩减可能压低需求；
2. 公司称截至 2009-12-31 已有 440 多个硅片、电池片和组件客户，并继续扩海外销售；
3. 公司计划到 2010 年末将 wafer/module 各增至约 500MW、cell 增至约 400MW；IPO 预计净募资约 5,480 万美元，其中约 4,500 万用于全链设备/厂房、约 500 万用于研发；
4. 2009 OCF 为负；公司在 MD&A 中将主要拖累列为第三方应收增加 1.436 亿元、第三方客户预收减少 1.396 亿元和预付等增加，部分被应付增加抵消；同期设备、借款和融资活动均大幅存在。

这些不是 H-B 已胜的证据：H-A 可以把它们解释成危机后扩张过渡，H-C 可以把需求吸收解释为复苏/补贴环境。故不强选主路径。

## 2. 完整企业系统与三条竞争解释

```text
客户融资、补贴与产品价格状态
  → 管理层全链产能 / 研发 / 销售网络承诺
  → 实际产品能力与客户交付、竞争中的价格实现
  → 价格 × 成本 × 组合的单位经济
  → AR、库存、客户预收、应付的现金转换
  → CAPEX、债务/股权融资与资本吸收
```

| 机制 | 对同一共同事实的解释 | 最关键的可反驳后果 |
|---|---|---|
| H-A：低成本整合逐步自我供血 | 回收材料、一体化和客户覆盖让新增能力转成可交付产品；即使售价不高，产品成本/质量和客户覆盖使现金转换逐渐闭合。 | OCF 转正，且 AR 上升与第三方客户预收减少不再共同吞噬经营现金；产品交付与成本/毛利的关系不恶化。 |
| H-B：信用与资本占用先到 | 客户/需求恢复可伴随赊销、预收下降、库存与设备投入；产能/收入增长并不先变成可支配现金。 | OCF 仍为负，且 AR 上升与第三方客户预收下降继续构成净现金压力；融资覆盖经营/资本缺口。 |
| H-C：外部需求/补贴吸收 | 复苏与政策可以令出货或毛利改善，即使一体化未形成独立优势、现金约束也未解除。 | 任何仅有容量、出货、收入或合并毛利的改善均不能裁决 H-A/H-B；必须降为共同背景或 `NOT_DIAGNOSTIC`。 |

## 3. 分层时钟：每层结算不同问题

| 时钟 | 冻结观察与同口径定义 | H-A / H-B 分歧 | H-C 与结算边界 |
|---|---|---|---|
| D1 实施 | wafer、cell、module 年产能，MW；同一公司披露的三产品能力。 | 两方都可能预期扩产完成。 | 仅结算行动/能力，不裁决机制。 |
| D2 客户/竞争 | 同一披露中产品 shipment/sales quantity，按产品及单位连续。 | H-A 预期能力转为客户交付；H-B 允许交付增长但受信用/库存约束。 | H-C 也可解释交付增长；无产品级客户/库存边界即 `NOT_DIAGNOSTIC`。 |
| D3 单位经济 | 同产品价格/成本或明确产品级毛利；不得用合并净利。 | H-A 需要交付与成本/毛利在价格压力下共同不恶化；H-B 允许出货增长但单位经济不穿透。 | 总毛利或行业 ASP 只能是背景；H-C 未排除时不能归因给一体化。 |
| D4 现金转换 | 合并 OCF；第三方 AR、第三方客户预收、库存、AP 的同定义现金流调节/余额。 | 见下方唯一方向性 cash-arrow 合同。 | 结果只结算现金箭头，不能选择全局 H-A/H-B。 |
| D5 资本吸收 | PPE/CAPEX、债务/股权融资与 OCF。 | 两方均可能看到融资。 | 只能约束“资本回收未知”；无责任单元资本与替代路径，永不判企业家决策正确。 |

### D4 唯一可方向结算的局部箭头

指标为：`OCF`（RMB thousand）及一组来源同定义的现金转换方向：

```text
working-capital cash strain = Δ third-party AR − Δ third-party customer advances
```

它只使用公司在 2009 MD&A 已明确的两个现金流方向；库存、AP 与预付仍必须同时记录，不能在结果期从公式中消失。

| 结果区域 | 冻结解释 | 不可写成 |
|---|---|---|
| `OCF >= 0` 且 `working-capital cash strain <= 0` | `SUPPORTS_H-A_FOR_CASH_ARROW`：只说明此一现金箭头没有继续恶化。 | H-A 全胜、产能决策成功、资本回收成立。 |
| `OCF < 0` 且 `working-capital cash strain > 0` | `SUPPORTS_H-B_FOR_CASH_ARROW`：只说明信用/客户预收压力仍未闭合。 | H-B 全胜、行业需求不存在、公司失败。 |
| 其余组合、任一字段未按同定义披露、或 H-C 不能被产品级观察限制 | `MIXED / MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`。 | 用收入、现金余额、融资或价格替代。 |

## 4. 结果期计量连续性合同（正文仍未读）

唯一允许的结果文件身份是：JinkoSolar FY2010 Form 20-F，report date 2010-12-31，filed 2011-04-25，SEC accession `0001193125-11-107730`，primary document `d20f.htm`。本冻结只登记元数据；不得在此阶段打开正文。

| signal | 结果期预期标签/范围 | 允许转换 | 禁止替代 | 定义变化动作 |
|---|---|---|---|---|
| D1 | `production capacity`；MD&A/Business 中 wafer/cell/module 各自 MW。 | 无；产品层级必须一一保留。 | IPO 募资额、PPE 总额、新闻稿。 | 缺任一产品或单位变更：`MEASUREMENT_MISMATCH`。 |
| D2 | `sales volume`、`shipments` 或同义的产品数量表；明确对象/单位/期间。 | 仅可从披露的片数转换为 MW，且报告给出转换规则。 | 总收入、客户数、行业装机。 | 未连续披露产品数量：`NOT_DIAGNOSTIC`。 |
| D3 | 同产品价格/成本/毛利的官方表或 MD&A；与 D2 同产品、同期间。 | 无跨产品或合并口径转换。 | 合并净利、行业 ASP、管理层说法。 | 无产品级成本/毛利：只保留 D2，不结算单位经济。 |
| D4 | `net cash (used in)/provided by operating activities`；MD&A 的 `accounts receivable`、`advances from third party customers` 现金流方向与余额表。 | 仅符号统一：AR 增加与客户预收减少均为 cash strain。 | 年末现金、融资现金、净利润、相关方应收/预收。 | 标签、对象或现金流归属改变：`MEASUREMENT_MISMATCH`。 |
| D5 | `capital expenditures` / PPE、借款、股权或债务融资、OCF。 | 只作并列边界。 | 市值、股价、融资成功、总资产。 | 永久保持 `CAPITAL_RETURN_UNKNOWN`，除非另有责任单元资本与替代路径合同。 |

## 5. 结果开启与停止

打开结果包后，先读取 D1–D5 的准入标签和同定义字段；只有 D4 完整时才计算上表 cash strain。D1/D2/D3/D5 的实际值不得先于各自合同进入红队。若结果源、定义或原文读取链失败，关闭为相应 `UNKNOWN`，而不是补读后续年份。

本冻结的终局裁决只能是：

```text
cash-arrow supports H-A / cash-arrow supports H-B / mixed / measurement mismatch
; output absorption status / product economics status / capital return unknown
```

它绝不合成为“晶科扩产成功/失败”或任何投资结论。
