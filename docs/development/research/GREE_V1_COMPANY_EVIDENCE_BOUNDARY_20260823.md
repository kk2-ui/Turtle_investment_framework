# 格力 V1 公司侧证据边界：2026-08-23

状态：`PREFREEZE_EVIDENCE_BOUNDARY / NO_PRIMARY / NOT_FROZEN`

本工件只记录重物化后的公司披露究竟能支持什么，及其不能支持什么。它不是
`financial_driver_bridge.v1`、不是 `thesis_test.json`、不是中心路径、不是
`SELECTION_ADMITTED`，也不含估值、价格、回报或投资动作。

## 可复现输入

- cutoff：`2026-08-03T18:00:00+08:00`；
- 巨潮完整 inventory：889 项，按冻结选择规则 materialize 41 项官方来源；
- PIT source package、41 次 allow-read 与 document manifest 均为 `REVIEWABLE`；
- 当前 package 投影出 187 条页级定位的 `VERIFIED` observation；
- 运行输出位于
  `output/research/gree_v1_company_bridge_20260823/company_blind_track/`，其当前
  FY2025 年报身份是
  `DOC:CN-SZ:000651:annual_report:2025-12-31:7cc972f2d199`。

这使下列 observation 可重读；不使它们自动成为独立样本、行业事实或判断正确性。

## 现金层：仅报表状态，不是 normal owner cash

| 已验证公司事实（2025，RMB_m） | 当前经济含义 | 明确禁止的推论 |
|---|---|---|
| OCF 46,383.11，`OBS:c8d46c93ce73ebd5ae90` | 报告期经营现金流为可观察事实。 | OCF 等于常态 owner cash。 |
| 经营相关受限资金净减少 15,667.16，`OBS:6e27887fa61091fb5323`；净增加 950.81，`OBS:cde104bdf2b566d95ed1` | 现金流中存在材料性受限资金项目。 | 用单年 OCF、OCF/利润或 OCF-Capex 判断现金持续性。 |
| 现金 Capex 1,717.31，`OBS:a5faf040b44deff57e05` | 已观察到总现金支出。 | 把总现金 Capex 当作维持性 Capex，或假设增长 Capex 为零。 |
| 客户收现 180,152.59，`OBS:84938078668847aa0e0f`；合同负债主要是经销商预收款，`OBS:2e5e14c3b6bcadac8084` | 销售回款与经销商预收的期末性质可观察。 | 从期末余额反推渠道库存、销量质量或未来营运资本释放。 |
| 现金及现金等价物 27,566.46，`OBS:8920e776a49267c1a562` | 报表现金等价物余额可观察。 | 将其与定期存款、受限资金或金融子公司资本合并为普通股可分配现金。 |

因此现金层的唯一诚实状态是
`REPORTED_CASH_STATE_ONLY`。维持性 Capex、必要营运资本、金融业务资本需要和普通股
可支配性尚未按同一口径闭合；不建立 normal owner cash 输入。

## 资本配置层：存在材料事项，质量仍未决

| 已验证公司事实（2025，RMB_m） | 当前经济含义 | 当前分类 |
|---|---|---|
| 金融产品申购 61,660.81，`OBS:110518056008ff0ba345`；赎回 28,454.98，`OBS:d6def9886b3c58db592a`；定期存款净增加 24,911.88，`OBS:e30115abc0db0ffa20c0` | 披露了金融产品和存款的资金滚动。 | `UNRESOLVED`，不把它称为经营再投资、可分配现金、流动性安全垫或价值毁损。 |
| 利息收入 671.10，`OBS:1dc7652c0e4f1e20c682` | 已观察到合并报表利息收入。 | 不据此推断金融资产期限、风险、质押或可自由处置性。 |
| 格力钛工程减值 1,142.17，`OBS:e5a626948b589599cdec` | 该项减值及披露的可收回金额假设可重读。 | 不据一次减值推断全生命周期投入、后续加码/撤退、退出价值或累计资本回报。 |
| 销售返利应付款 48,571.25，`OBS:e73a298fbb22c1ebb0e0` | 渠道相关负债状态可观察。 | 不把余额变化解释为返利政策、竞争强度或经销商经济性已经改善/恶化。 |

当前没有为这些事项建立 allocation event 的 `initial_commitment -> movement -> realization`
链。尤其不得从合并货币资金或期末余额倒填格力钛交易的实际资金来源，或把金融产品申购
当作已知的资本配置决策质量。

## 竞争与单位经济：保持 UNKNOWN

公司包没有同一 provider、同一产品/地域/渠道/品牌分母/交易点下的历史品牌量、额、ASP
和价格带资料。因此线上相对位置、公司收入或单期毛利都不能区分“渠道/价格带重配”和
“全渠道竞争及价格实现恶化”。竞争和单位经济两个 layer 保持 `UNKNOWN`，不能用公司
内部数据补成行业证据。

## 进入真实冻结的唯一顺序

1. 取得符合
   [独立行业 release 最小交付单](GREE_V1_INDUSTRY_RELEASE_ACQUISITION_SPEC.md) 的历史
   provider/release/version 包，完成竞争与单位经济的同口径对照；
2. 只在 H-A/H-B 出现可区分方向证据后，冻结中心路径、最强反方、简单基线和 3--5 条 FJ；
3. 将四层 driver 与 allocation event 的监测/兑现合同写入正式
   `financial_driver_bridge`；任何 `FDBMON`/`FDBREAL` 引用的 FJ 都必须存在于同一
   `thesis_test.json`，否则 bridge 在输出评估时为 `INVALID`；
4. 独立盲评通过后才登记 `SELECTION_ADMITTED`，再按多层经营时钟结算。

在第 1 步前，这一对象只能减少“公司材料能否重读”的不确定性；它没有提供主路径选择、
未来经营结果、学习 note 或判断能力证据。
