# ITER-100 — owner cash 必须是一条来源化调整桥，不是 OCF 的别名

日期：2026-08-21

巴菲特在 [1986 年 Berkshire 致股东信的 owner-earnings 附录](https://www.berkshirehathaway.com/letters/1986.html) 中把经济所有者收益写为报告利润加非现金费用，再减维持竞争地位与单位销量所需的资本支出和必要营运资本；他特别指出资本项是困难的判断，并警告制造业、零售业不能把通常的 cash flow 直接当所有者收益。其 [2006 年信](https://www.berkshirehathaway.com/letters/2006ltr.pdf) 在呈现每股投资时又特意剔除金融业务所持投资，因为它们大体被借款抵销。这不是把 Berkshire 结构套到格力，而是支持同一边界：合并现金/金融资产必须先判断可支配性，才能进入普通股 owner cash。格力事实正是这一问题：2025 合并 OCF 包含 156.67 亿元经营相关受限资金净减少，维持性 Capex、营运资本、金融子公司资本与可分配现金仍未闭合。

旧 FDB 虽记录现金层 observation，却未要求 writer 说明它已经形成 `NORMALIZED` owner-cash adjustment bridge，还是只看到了报表 OCF；一条含 normal owner cash 的模型 binding 仍可能只引用受限资金释放。这是 `ACQUISITION_MODULE + MODEL` 缺口，不能靠提高 OCF 计算精度解决。

`financial-driver-bridge-policy.v3` 对生产 `CASH_CONVERSION` driver 要求 `cash_normalization_contract`：`NORMALIZED` 需有来源化 reported cash、逐项调整、每项方向/重复性判断/处理，以及维持性 Capex、必要营运资本和资金可支配性的明确 treatment 和 VERIFIED observation ID；`UNKNOWN` 必须说明缺口与保守处理；`REPORTED_CASH_STATE_ONLY` 只可作为状态观察。production adapter 进一步拒绝冻结 material `owner_cash` transmission，除非其绑定至少一个 `NORMALIZED` 的 CASH_CONVERSION driver。它不计算自由现金流、不假定总 Capex 等于维持 Capex，也不把金融资产或现金余额变为可分配现金。

根因是 `ACQUISITION_MODULE + MODEL`；若用格力的 OCF、货币资金或 OCF–Capex 直接充作 owner cash，会材料性高估可分配现金、竞争持续期与永久损失承受力。禁止用一次受限资金释放、报表现金余额、金融产品申购赎回、单期 Capex 或股价补齐 adjustment component。接纳测试为：缺 contract 的新 production bridge 被阻断；保守 `UNKNOWN` 可冻结公司事实但不能承载 material owner-cash FJ；只有完整来源化 bridge 可让 owner-cash transmission 进入 case。格力当前仍只能为 `UNKNOWN`，不改变其 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY` 状态。
