# ITER-103 — 信号的先后关系必须可冻结，不能以终局结果倒写早期机制

日期：2026-08-21

[Collier（2011）](https://doi.org/10.1017/S1049096511001429) 将诊断证据置于因果时间序列中，而不是只比较某个终局变量是否命中。Turtle 的 H-A/H-B 也同样需要“渠道/量价等早期机制信号 → 现金与终局经营”这一可反驳顺序。只写 signal 的 `sequence=1,2` 而不冻结到期关系，不能形成这种证据。

审查发现，旧 pair validator 只要求 sequence 连续，允许 `TERMINAL_OPERATING` 与 `EARLY_MECHANISM` 同日甚至更早到期。这样研究者可以在终局经营结果已知时，给同一个 mechanism pair 补写一个名为“早期”的 observation；单项 claim 仍可 `CALCULATED`，反馈会把它当作经验。

最小修复只约束真正的机制先后：所有 early signal 必须排在 terminal signal 前，且其最晚 `resolution_due` 严格早于第一个 terminal signal；同一终局窗口内的多个经营结果可并列。它不要求每一个终局指标人为错开日期，也不计算因果概率。thesis gate 现拒绝违序 pair，定向回归覆盖有效序列、重复编号、缺 early/terminal 以及 early/terminal 同日的失败形状。

根因是 `REASONING + MODEL`；经济影响是若终局结果能倒写早期验证，渠道重配、价格实现和 normal owner cash 的判断会被事后偏见污染，进而虚假提升竞争持续期与永久损失判断的信心。禁止以后来毛利、OCF、减值或股价补设早期 FJ；接纳条件是冻结前存在不同于终局经营结果的 6–12 月 signal，并在同一 pair 中有明确更早到期日。格力当前尚没有可冻结 H-A/H-B pair，故本修复只保护未来研究，不改变其 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY` 状态。
