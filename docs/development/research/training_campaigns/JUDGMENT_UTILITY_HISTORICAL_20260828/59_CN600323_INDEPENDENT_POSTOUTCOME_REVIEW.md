# CN600323 paired historical holdout 独立 post-outcome 审阅

## 审阅结论

**ACCEPT。** FY2024 支持一个材料且有边界的企业更新：核心垃圾焚烧运营更强，集团资本开支后现金和同口径净债务改善，正常盈利与不含价格的内在价值方向应小幅上修；但往期电费/国补、集中回款、应收与总债务继续增长，以及未闭合的 parent/NCI bridge，要求 owner cash 继续条件计入、永久损失约束继续收紧。冻结两臂都没有因局部未知退出整案，settlement 也正确地把外部气价、政府付款和 parent access 未披露限制在责任匹配轴内。

方法效用裁决严格为 **`NO_MATERIAL_UTILITY`**。54 的 `material_preoutcome_differences=[]`，Baseline 与 Enhanced 冻结了相同的五轴处理代码和经济上相同的 rank-1 行动；因此 `axis_assessments=[]`。Enhanced 的 outcome cells 更会区分责任传播，是可保留的设计经验，但字段更多、分类更细或 reviewer 更偏好其解释，均不能回写为本 episode 的正向效用。

## FY2024 对两臂第一稿的检验

两臂共同抓住了企业的主要机制：固废/垃圾焚烧运营是最可靠的正常盈利底座；能源高点需要同口径采购、售价、销量和持续费用桥；应收、资本开支和债务是 owner cash 与永久损失的核心载体；parent access 未披露只能限制 owner cash，不能成为公司失败的替代证据。

FY2024 的结果比两臂机械分类更正面，但没有否定这套结构：

- 扣非归母利润增长 15.52% 至约 16.25 亿元；固废剔除工程与装备后的运营净利润增长 9.64% 至约 10.04 亿元；垃圾焚烧净利润增长 21.63% 至约 9.32 亿元。
- 垃圾焚烧利用率仍为 119%，吨垃圾发电和上网效率改善；但处理量仅增长 1.78%，收入说明包含往期及当期电费、可再生能源国补和供热增长，因此 21.63% 不能完整外推。
- 集团 OCF 约 32.73 亿元，减披露资本开支约 17.08 亿元后为正约 **15.65 亿元**。这是约 1.565 billion CNY，不是 15.65 billion CNY。现金购建口径的桥约为正 16.07 亿元，公司自行报告自由现金流 13.58 亿元。
- 应收账款加合同资产仍增长 8.26% 至 52.91 亿元，总有息债务增长 7.10% 至 168.35 亿元；但现金增加使同口径净有息债务下降 11.45% 至 125.87 亿元，覆盖能力改善且没有违约或结构性上划阻断。
- 母公司实际收到约 11.73 亿元投资收益现金，证明部分上划存在；NCI 权益占比 11.95%、母公司经营现金为负且重要子公司 post-capex/NCI/留存桥未闭合，所以不能把集团现金全部称为 parent owner cash。

机械 residual 与 local unknown 的使用本身成立，但只能限制各自 cell。Baseline 的固废剔工程利润 9.64% 因低于预设 10% 而进入 `EARNINGS_COMPLETE_RESIDUAL`；Enhanced 因 FY2023 同口径焚烧毛利率和能源价格/经常利润桥不完整而进入 `LOCAL_UNKNOWN`。这些状态不推翻已经观察到的集团扣非、固废运营、垃圾焚烧、现金与债务事实，也不阻止企业层面形成“小幅上修正常盈利与内在价值、继续收紧 owner-cash/permanent-loss 约束”的综合判断。

## Baseline 的校准

Baseline 是公平且强的基线，不是 strawman。它在结果前已经排除能源高点的完整正常化、把 owner cash 限于集团代理并把永久损失约束收紧，同时保留垃圾焚烧运营信用和资本开支退坡的反方。

其结果后校准有两点不足：

1. 双重 10% favorable 门槛过于离散。扣非归母增长 15.52%，固废剔工程运营利润增长 9.64%，后者只差 0.36 个百分点且披露本身按亿元四舍五入，机械 residual 令正常盈利和价值方向完全不更新，低估了连续事实的合力。
2. 若 favorable 真命中，Baseline 会把全企业管理层从条件信用直接升为正面信用；但 owner cash、融资和增量资本回报仍可能未闭合。这一传播偏宽。FY2024 最合理的处理是垃圾焚烧运营分轴正面、企业管理层综合仍为条件信用。

因此 Baseline 对企业经营强度和内在价值方向略偏保守，对 hypothetical favorable management 传播又略偏积极；两者都是局部校准问题，不改变其作为公平基线的有效性。

## Enhanced 的校准

Enhanced 正确拆开垃圾焚烧运营、能源采购/定价、外部政府付款、可控现金执行、融资和新增资本配置。FY2024 政府支持回款和采购成本下降没有被错误归责为无条件管理能力；垃圾焚烧强劲也没有擦除应收、债务和 parent access 风险。这是更合理的责任传播设计。

但 Enhanced 的结果 cell 也过度保守：favorable 分支把垃圾焚烧利润、毛利率、利用率、能源的完整价格/利润桥和集团持续费用捆绑在一起。能源精确桥缺失便使整个 recurring-economics cell 为 `LOCAL_UNKNOWN`，从而没有消费垃圾焚烧利润 +21.63%、固废剔工程运营利润 +9.64% 和集团扣非 +15.52% 对 normal earnings 的方向证据。更好的校准是把未知限制在能源耐久性和该部分管理归因，同时允许已观察的垃圾焚烧与集团利润对正常盈利作小幅上修；企业管理层仍保持条件信用。

这项责任传播优点应记录为设计经验，但两臂当前处理和 rank-1 行动相同，不能把“Enhanced 本可以写得更合理”计作已观察的 paired utility。

## 企业层面的 best-current judgment

- **管理层：** 垃圾焚烧运营为正面，能源采购/定价、回款、融资为条件信用，增量资本配置暂不升级；企业综合为 `CONDITIONAL_CREDIT`。
- **Normal earnings：** 相对 FY2023 的 14.07 亿元底座方向上小幅上移；不承保完整 16.25 亿元，也不把往期电费、国补或外部采购成本下降全部正常化。
- **Parent owner cash：** 集团资本开支后现金为正、母公司也有真实上游现金收入，但 NCI 与全量上划桥未闭合，继续 `COUNT_CONDITIONALLY`。
- **Permanent loss：** 即时风险边际缓和，但应收、总债务、受限资产和到期债务仍材料，维持 `TIGHTEN_CONSTRAINT`，不升级为 `THESIS_BLOCKING`。
- **内在价值方向：** 不使用价格、正式估值或 BuyBand；相对 FY2023 小幅 `UP`，上修被盈利与现金的时点性以及 parent access 未闭合限制。

乐观、基准、悲观路径以及翻转事实详见 `INVESTOR_READOUT.md`。下一 rank-1 行动应从已经结算的集团 OCF-capex 移开，聚焦重要子公司 post-capex 现金、NCI、必要留存、受限资金及实际向上市公司母公司分红/调度的逐家桥。

## 公平比较与效用裁决

54 已冻结：两臂均为 `CONDITIONAL_CREDIT / EXCLUDE_COMPONENT / COUNT_CONDITIONALLY / TIGHTEN_CONSTRAINT / UNCHANGED`，rank-1 都是集团现金转换与母公司可得性。`material_preoutcome_differences=[]` 是实质事实，不是 schema 偶然。

FY2024 结果令两臂都应形成同一个企业层面更新；没有一个冻结材料处理避免了另一臂的材料错误，也没有一个冻结处理改变正常盈利、owner cash、永久损失、内在价值方向或下一经济行动。Enhanced 更细的 outcome 分类及更好的责任归因只构成后续设计经验。依照公平合同：

- `axis_assessments=[]`；
- `overall_utility_verdict=NO_MATERIAL_UTILITY`；
- 本 episode 不验证方法包，不验证 transfer，不授予 CJO、正式估值、BuyBand、报告或投资行动权限；
- 方法包保留为候选但未验证，下一次必须在 outcome 解封前形成真实材料处理差异，才能检验 paired utility。

本轮没有会材料改变投资判断或效用裁决的剩余错误，因此结论为 **ACCEPT**，无 blocking return，也无需为非材料措辞、字段或机械状态发回。
