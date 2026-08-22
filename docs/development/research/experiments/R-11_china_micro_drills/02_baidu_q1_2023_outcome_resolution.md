# R-11 结果结算：Baidu Q1 2023 变现结构分化

状态：`OUTCOME_REVEALED / B_ONLY / HISTORICAL_SELF_REPLAY / NO_COMPANY_CONCLUSION`

这是对 [R-11 冻结卡](00_baidu_q1_2023_pre_outcome.md) 的只追加结算；冻结卡与[第二遍解释攻击](01_baidu_q1_2023_second_pass.md)不回写。

## 1｜来源合同与机械结算

结果期来源是 [Baidu 2023 Q2 Form 6-K exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1329099/000119312523217413/d502468dex991.htm)，于 2023-08-22 发布，落在冻结的 `2023-08-21–2023-08-31` 事件窗口，并使用同一发行人的 `Baidu Core online marketing revenue`、`Baidu Core non-online marketing revenue` 标签。

- Q2 online marketing revenue：同比 `+15%`；
- Q2 non-online marketing revenue：同比 `+12%`；
- 冻结的 H-A 条件为 non-online 增速 `>` online-marketing 增速，未满足；H-B 条件为 `<=`，满足。

因此机械 verdict 为 `B_ONLY`。结果来源通过了 R-11 的发布者、结果事件、窗口与双标签合同；不使用同一公告内的 Managed Page、利润、管理层说明、电话会、价格或后续资料。

## 2｜机制边界

`B_ONLY` 只支持“Q1 的非广告收入较快增长没有在 Q2 保持相对领先”这一短期箭头。它**不**支持下列更大的说法：

- AI/ERNIE 没有长期商业价值；
- 广告业务永远主导 Baidu Core；
- Baidu 的利润、现金流、内在价值或股票回报应如何判断。

原因是本卡刻意没有预注册 AI 产品使用、客户转化、云服务毛利、收入份额变化或更长时期的指标；相对增长率只裁决本季度的分叉，不能替代完整变现机制。

## 3｜学习记录

| 学到的限制 | 根因 | 对判断的经济影响 | 下一张不同中国对象的冻结前改变 |
|---|---|---|---|
| 单季“小分部增速高于大分部”本身不等于结构性变现转折。 | `REASONING` | 容易把短期低基数/组成波动写成增长引擎，进而高估正常收入与利润的持续性。 | 除相对增速外，预先加入一项结构量：收入份额的同口径变化、绝对收入贡献，或能区分客户/使用/单位经济的前导指标。 |
| 有结果后才确认真实公告来源的风险在 R-10 已出现；本卡则按结果前公告冻结了事件。 | `ACQUISITION_MODULE` | 否则可在答案出现后换来源，产生伪反馈。 | 保留 `publisher + event + window + calendar/URL metadata + label` 五元组；任何一项失配即关闭。 |

本例是 `HISTORICAL_SELF_REPLAY`，不能排除外部历史记忆；不计入准确率、概率、校准或 Turtle 命中。它的有效产出是：下一条训练不能再只依赖一个相对收入增速。
