# ITER-107 — 投资轨必须继承冻结公司判断，不能并行重写

日期：2026-08-21

此前 `COMPANY_JUDGMENT_ONLY` 已能在无价格状态下冻结，但投资 PIT production run 仍能从空白开始另写中心路径。这样即使 CJO 已存在，价格、估值或预期回报仍可能倒灌为一套不同的经营叙事。这个缺口与 [Remus、O’Connor 和 Griggs（1996）](https://www.sciencedirect.com/science/article/pii/S0167923695000097) 关于先独立准备判断、再整合额外信息的边界一致：该实验不是投资回报研究，却支持将初始判断和后续信息整合分成可审阅阶段。

现在所有 `INVESTMENT_DECISION` 的 PIT production freeze 必须提供同公司、同 cutoff、V3、已完成的 CJO `publication_snapshot.json`。入口验证其 purpose、公司、cutoff、完成状态与 frozen thesis hash；随后将中心路径、经营 FJ 和机制链冻结成 `company_judgment_predecessor.json`。投资 `thesis_test` policy 再要求它逐项保留 predecessor 的中心路径、经营 FJ、竞争 pair link 和 normalized-earnings / owner-cash 传导；唯一允许的新层是 valuation、expected-return 与 decision binding。任何经营对象的变化都必须先形成新的 CJO，不能在价格轨中解释为“更新”。

根因是 `MODEL + REASONING`。若没有这条 lineage，低估值、价格走势或目标回报会材料性地改变竞争持续期、owner-cash 与永久损失判断，却没有新增公司证据。禁止将旧工程 `HBTCASE`、未完成 CJO、不同 cutoff、不同公司或只写一段 CJO 摘要当作 predecessor。接纳测试：缺快照、purpose/company/cutoff/hash 不匹配时生产入口拒绝；改变任一继承的 central path、FJ 或经营 transmission 时 thesis gate 拒绝；仅增加 valuation/return/decision binding 的同一经营对象可通过。真实格力尚无完成 CJO，故这项修复阻断其直接进入投资轨，而不提高任何格力结论。
