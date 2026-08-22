# R-10 结果合同审查：中通 Q1 2023

状态：`CLOSED / OUTCOME_SOURCE_CONTRACT_MISMATCH / NO_MECHANISM_VERDICT`

冻结卡把 2023-08-17 的 SEC Form 6-K `0001104659-23-092818` 及其 exhibit 99.1 登记为 Q2 结果材料。开启后发现它并非约定的 Q2 业绩事件；真正 Q2 业绩由公司在 2023-08-29 发布。这个发现发生在结果期，不能用新发现的业绩页取代冻结 source。

## 审查结论

- 根因：`ACQUISITION_MODULE + REASONING`。此前以预期 filing 日期推断附件，而没有在 cutoff 前锚定发行人的 Q2 结果事件与发布日历。
- 经济影响：若把 8 月 29 日业绩的结果期数据补进来，会在已见结果后改变来源选择；即使指标相同，H-A/H-B 的看似有效结算也不能作为判断训练反馈。
- 缺失事实：cutoff 前可复读的发行人结果日历/公告 metadata，能够把发布者、Q2 事件、窗口与同口径 `revenues / gross profit / sorting-hub operating cost` 标签锁在一起。
- 禁止假设：日期相近的 SEC/HKEX 附件等同于下一季业绩；结果发现后更换链接不影响结算；实际 Q2 的任何利润、价格、回报或管理层解释能补足这个缺口。
- 可执行修复：[P-60.3](../../TURTLE_RESEARCH_PREPARATION_ITERATION_LOG.md) 已把 `publisher + event + window + calendar/URL metadata + label` 写入下一卡的冻结合同。
- 验收：下一张中国卡须在 cutoff 前已定位该五元组；结果期只开预登记事件。若事件不符，仍关闭而不替换。

本卡不产生 `A_ONLY / B_ONLY / MIXED`，不写 learning win/loss，也不构成中通的公司结论。已见到的结果期材料只说明本卡的来源合同为何失败，不能回填到第一遍或第二遍。
