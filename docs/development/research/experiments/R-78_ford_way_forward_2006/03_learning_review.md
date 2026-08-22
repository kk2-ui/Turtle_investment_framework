# R-78｜学习复盘：把多层时钟从“有字段”变成“字段可判别”

状态：`TEACHING_LEARNING_NOTE / NEXT_DIFFERENT_COMPANY_REQUIRED / NOT_A_FORMAL_LAPP / INDEPENDENT_REVIEW_PENDING`。

本复盘只从 R-78 已冻结并已结算的边界中提取下一轮规则。它不把 Ford 的历史结果变成方法胜率、概率、管理评分、价格或投资结论。

## 有效保留的规则

| learning constraint | R-78 中暴露的失效 | 下一不同公司冻结前必须改变的字段 | 不满足时的处置 |
|---|---|---|---|
| `D2_CHANNEL_COHORT_SPLIT` | 含 fleet 的合并市场份额同时包含终端客户反应和公司主动减少租赁销售，不能识别客户机制。 | 写明 retail／直营／经销／工程／fleet 等渠道 cohort；D2 只使用未被本次行动主动缩小的 customer outcome，或将被主动退出的 cohort 另列。 | `D2 = NOT_DIAGNOSTIC`；不得以公司级份额、收入或总销量替代。 |
| `D3_THROUGHPUT_COST_BRIDGE` | 成本下降可与不利 volume/mix、净价格、激励、产品转换和一次性项目并存。 | 同时冻结 `volume_or_utilization`、`price_or_mix`、`unit_cost`、`channel_or_service_cost`，并定义一次性退出项目如何排除。 | 只记录成本行动或毛利变化；不得称单位经济改善。 |
| `D4_DECISION_UNIT_SCOPE_GATE` | Automotive 现金虽拆除了部分 Ford Credit 交易，仍不是北美退出责任单元。 | D1 的决策责任单元与 D4 cash source 必须同一范围；若只能拿集团／跨区域现金，D4 在冻结时即为 `CAPITAL_OR_CASH_UNKNOWN`。 | 不从总 CFO、集团现金、融资或相邻分部现金做归因。 |
| `D1_DUE_DATE_SPLIT` | 一个 2012 完成的计划在 2006Q1 只可能观察局部设施与人员实施。 | 将已经到期的离散行动、尚未到期的总目标和每项允许来源分开。 | 只结算 `IMPLEMENTATION_OBSERVED`，不把计划全额标为完成或失败。 |

## 下一轮应用收据（待产生）

```text
LNOTE:R78-MULTICLOCK-BOUNDARY
    → 下一不同公司的预冻结卡
        → D2 cohort 字段、D3 四因子桥、D4 单元范围、D1 到期拆分的逐行 locator
            → 独立 reviewer：APPLIED / NARROWED / INAPPLICABLE
                → 仅在该新卡按其 own outcome contract 结算后讨论 learning application
```

目前不存在这个收据，故 R-78 不是正式 `LAPP:`，更不是中国选择判断的复制验证。下一卡必须是不同公司；同一 Ford 文件、更多年份或补充叙事都不能充当应用。

## 选择规则没有改变的部分

- R-78 仍是 `NO_PRIMARY`：H-C 的宏观／金融渠道没有在 cutoff 前得到独立、同口径的排除合同。
- 因此它只能训练测量边界和机制时钟，不能评价“研究者是否选对” H-A/H-B。
- 只有结果前存在非共同方向性依据、不同于公平基线、可结算反方与本地 D1--D4 口径的中国案例，才有资格进入 `SELECTION_ADMITTED`。

这次复盘的价值不是给 Ford 下结论，而是强迫下一张卡把“销量／份额”“成本下降”“现金改善”分解成会随管理决策和渠道结构改变含义的变量。
