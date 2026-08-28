# CN603195 判断优先第一稿合同验收

> 裁决：`ACCEPT / FIRST_DRAFT_JUDGMENT_QUALITY_IMPROVED / METHOD_UTILITY_NOT_CLAIMED`

## 验收问题

本轮不增加训练样本，也不把字段、校验器或盲包计作训练效用。它只回答一个更靠前的问题：

> fresh forecaster 在结果仍封存、证据不完美的条件下，能否在第一稿直接形成明确、有限、可反驳的企业判断，而不是等 reviewer 事后把机械 cell 改写成投资判断？

验收对象为 `CN:603195 公牛集团 × 2024-05-01`，只使用 FY2021、FY2022、FY2023 三份 cutoff 前官方完整年报。FY2024 outcome、价格、回报和旧派生报告均未进入 forecaster 或 reviewer 输入。

## 真实退回与修复

第一次 blind draft 暴露了两项材料问题：

1. 正的合并 `OCF－长期资产购建现金` 被过早升级为母公司股东现金；
2. 收入和毛利率被用作 normal earnings 的替代，没有消费持续费用和经常经营利润。

因此第一稿合同增加了两条经济语义，而不是增加准入门：

- 合并现金只能称 `GROUP_CASH_PROXY`；NCI、母公司实际上划和维持性资本开支未闭合时，最多 `COUNT_CONDITIONALLY`；
- normal earnings 必须由同责任边界的收入或销量、持续费用负担和经常经营利润共同支撑。

第二次 blind draft 又暴露一项相反方向的材料问题：为了避免跨轴传播，现金 cell 把 permanent loss 永久保留，连持续且材料的维护性现金吞噬或结构性上划阻断也不能传播。这会低估真实永久损失。

因此合同进一步区分：

- 单年、可逆营运资本或一次性成长资本开支只更新 owner cash；
- 连续、材料、不可回避的维持性现金吞噬，或材料且结构性的现金上划阻断，可以同时触发 `DO_NOT_COUNT + TIGHTEN_CONSTRAINT`。

一次浏览器物化得到的 PDF 正文流损坏，相关 blind run 被作废，没有用常识补写或计入验收。盲包构建器现会在交给 forecaster 前确认 PDF 正文可提取；这只是 acquisition 修复，不产生训练信用。

## 最终第一稿的企业处理

最终 fresh draft 在 outcome 封存时直接给出：

- `management_execution=POSITIVE_CREDIT`：核心品类的收入、销量与费用后经营利润共同兑现；
- `normal_earnings=RAISE`：相对 FY2021 共同参考状态，收入、持续费用和经常经营利润三段桥共同改善；
- `owner_cash=COUNT_CONDITIONALLY`：三年 group cash proxy 为正，但不冒充 parent owner cash；
- `permanent_loss=MAINTAIN_CONSTRAINT`：没有把未披露当恶化，也没有因正集团现金自动放松约束；
- `valuation_direction=UP`：指内在价值相对参考状态的方向，不依赖市场价格，也不是 BuyBand；
- rank-1 研究行动转向闭合母公司现金、NCI 与维持性资本开支边界。

三个情景是不同经营路径，不是同一结论的高、中、低措辞。每项中心判断都有最强反方、投资含义和可观察翻转事实。`LOCAL_UNKNOWN` 与 `MEASUREMENT_MISMATCH` 只限制相应 cell，不能把未知改写成恶化，也不能撤回已经形成的公司判断。

## 独立裁决

独立 reviewer 复核三份 cutoff 前年报和最终第一稿后裁决 `ACCEPT`：

- 第一稿先判断，没有以 UNKNOWN、缺价格或资料边界退出；
- normal earnings 实际消费了持续费用与经常经营利润；
- group cash 与 parent owner cash 保持分离；
- 单年可逆现金与材料持续现金损失的传播距离正确；
- outcome cells 从属于企业判断，有限材料变化可以获得有限处理变化；
- 三情景、最强反方、投资含义和翻转事实可执行。

## 这次验收获得与未获得什么

已获得：`FIRST_DRAFT_CONTRACT_ACCEPTED_FOR_HISTORICAL_TRAINING`。下一条历史 episode 应先使用该合同形成第一稿，再由 outcome settlement 检验其判断，而不是继续先堆 cell。

未获得：新的真实 feedback turn、跨公司 method utility、`TRANSFER_VALIDATED`、CJO、正式估值、BuyBand、报告或投资权限。这个验收证明第一稿生成行为得到实质改善，不证明投资方法已经有效。

