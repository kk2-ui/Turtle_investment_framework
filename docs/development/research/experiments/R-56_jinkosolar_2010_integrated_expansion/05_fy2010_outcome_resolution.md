# R-56｜晶科 2010 一体化扩产：FY2010 结果期分层结算

状态：`ARCHIVED_EX_ANTE_EXTERNAL / OUTCOME_RESOLVED / MECHANISM_SIGNAL_PROBE / NO_PRIMARY`。

这是一份历史教学结算：冻结时未读结果，而本次只读取冻结时唯一预登记的 FY2010 Form 20-F。它不表示 Turtle 在 2010 年作出了预测，不进入选择准确率、概率校准、估值、证券价格或回报研究。

## 读取范围与口径先行

唯一结果源为 [JinkoSolar FY2010 Form 20-F](https://www.sec.gov/Archives/edgar/data/1481513/000119312511107730/d20f.htm)，report date `2010-12-31`、filed `2011-04-25`、SEC accession `0001193125-11-107730`、primary document `d20f.htm`。本次只读：

- Business / Strategies 印刷 p.32：2010 年末各环节产能与合并 gross margin；
- MD&A 印刷 p.51：产品销量与各产品 approximate average selling price；
- Liquidity and Capital Resources 印刷 p.63：经营、投资和融资现金流及经营现金的逐项桥；
- 合并现金流量表：确认上列经营现金流方向与列报口径。

未读 FY2011 及以后文件、新闻、行业回顾、证券价格、回报或任何未列入 D1–D5 的结果叙事。没有在本地保存新的原始副本；引用的是可直接复读的 SEC 原件和上述 locator。这个 archival read receipt 足够支持本教学结算，但不是 production PIT source package 的替代品。

## 分层观察与结算

| 时钟 | FY2010 同定义观察 | 合同裁决 | 为什么不能越界 |
|---|---|---|---|
| D1 实施 | wafer、cell、module 产能在 2010-12-31 均为 `600 MW`；高于冻结时分别约 `500 / 400 / 500 MW` 的年末计划。 | `IMPLEMENTATION_OBSERVED`。 | 产能达成只说明资源承诺已实施，不说明客户吸收、成本优势或资本回收。 |
| D2 客户/竞争 | 产品销量从 2009 的 wafer `180.4 MW`、cell `27.3 MW`、module `14.4 MW`，变为 2010 的 `157.2 / 55.1 / 265.4 MW`。公司还称已终止长期 wafer 销售合同，以把更多 wafer 用于自身后续工序。 | `DOWNSTREAM_MIX_SHIFT_OBSERVED / NOT_DIAGNOSTIC`。 | module 销量上升既可来自 H-A 的整合，也可来自 H-C 的需求/补贴吸收；wafer 外销下降又包含内部转移，不能用作独立客户反应或竞争胜负。 |
| D3 单位经济 | wafer、cell、module 的平均售价分别从 `RMB6.1 / 8.3 / 12.7` 每 watt 降至 `5.8 / 7.9 / 12.2`；公司披露合并 gross margin `29.2%`。 | `PRODUCT_PRICE_PRESSURE_OBSERVED / PRODUCT_ECONOMICS_MEASUREMENT_MISMATCH`。 | 没有与同产品销量匹配的产品级成本或产品级毛利。合并 gross margin 不能替代该缺口，也不能把价格下降归因为一体化成功或失败。 |
| D4 现金转换 | OCF 从 2009 `-RMB76.3m` 转为 2010 `+RMB230.4m`。2010 AR 增加 `RMB374.0m`，第三方客户预收增加 `RMB128.4m`；同时库存增加 `RMB603.9m`、预付及其他流动资产增加 `RMB282.5m`，而 AP 增加 `RMB282.5m`、其他应付/计提增加 `RMB161.9m`。 | `MIXED`，见下方局部 cash-arrow。 | OCF 转正不是客户信用/营运资本压力已消失；两个冻结变量仍产生正现金压力，且其他流动资产和负债项对总 OCF 有材料性影响。 |
| D5 资本吸收 | 2010 投资现金流 `-RMB1,552.6m`（其中 PPE/land-use-rights `-RMB1,345.5m`）；融资现金流 `+RMB1,696.8m`，OCF `+RMB230.4m`。 | `CAPITAL_ABSORPTION_OBSERVED / CAPITAL_RETURN_UNKNOWN`。 | 集团融资流入与 CAPEX 并存，并不识别增量资本的责任单元、替代路径、税后回报或寿命，不能评价企业家资本配置。 |

### D4 的冻结公式：结果为 `MIXED`

冻结公式是：

```text
working-capital cash strain = increase in third-party AR − increase in advances from third-party customers
                              = RMB374.0m − RMB128.4m
                              = +RMB245.6m
```

它仍为正，故不满足 H-A 所需的 `OCF >= 0` **且** `cash strain <= 0`；但 OCF 已转正，故也不满足 H-B 所需的 `OCF < 0` **且** `cash strain > 0`。正确结论是 `MIXED`，不是用一项“经营现金流为正”或“应收继续增加”选一方。

## 企业系统结论：没有全局胜方

这份结果说明，产能实施、下游产品组合和总 OCF 可以同时改善，而产品价格仍下行、营运资本资产仍大量吸收现金、融资与大额投资仍并存。它恰好证实冻结时为何必须保留 H-C：任何单独的出货、收入、毛利或 OCF 改善，都不足以归因于一体化本身。

因此本案的完整裁决为：

```text
D1 implementation: observed
D2 customer/competition: downstream mix observed, not diagnostic
D3 product economics: measurement mismatch
D4 cash arrow: mixed
D5 capital return: unknown
global H-A / H-B: not adjudicated
```

根因分类：`DATA_COVERAGE + REASONING`，不是“公司资料不足便停止”。产品级成本与外部客户吸收无法由可读字段重建；若强行用合并毛利、收入、融资或后来行业知识补足，会材料性误判正常盈利、owner cash、资本配置与永久损失。

## 关闭条件与下一步

R-56 关闭为 `OUTCOME_RESOLVED / NO_COMPANY_CONCLUSION / REPLICATION_REQUIRED`。不再补读后续年份来寻找结局，也不从本案导出方法胜率。下一张近失效或边界卡必须在结果前冻结：

1. 产品级交付是否是外部客户吸收，而非内部工序转移；
2. 同一产品的价格、成本与毛利，或明确保留 `PRODUCT_ECONOMICS_UNKNOWN`；
3. 全部营运资本桥项，而不是只用 OCF 或单一 AR 项；
4. 独立的责任单元资本回收合同；若没有，D5 始终为 `UNKNOWN`。
