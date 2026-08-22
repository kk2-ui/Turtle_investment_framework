# 格力 V1：公司驱动与前瞻判断冻结设计

状态：`PRE_FREEZE / COMPANY_JUDGMENT_ONLY_DESIGN / NO_CENTRAL_PATH`
截至：`2026-08-03T18:00:00+08:00`
不含：股价、市场隐含预期、估值、投资动作、中心路径概率或事后经营结果。

## 目的

本设计把已有的公司经验变成下一次可以被证明错误的判断，而不是把 20 多份格力报告叠加成更有说服力的叙事。它服务于公司判断学习闭环：先结算经营机制，再结算 3–5 年经营与资本配置；价格和投资回报保持单列轨道。

正式对象现在有两种严格但分离的用途。`INVESTMENT_DECISION` 必须绑定 `VERIFIED` observation、估值模型输入和决策条目；`COMPANY_JUDGMENT_ONLY` 则禁止这些交易物件，改以 `FDBMON`/`FDBREAL` 的 FJ ID 绑定四层事实和后续经营结算。当前 blind track 仍没有中心路径、冻结的 `thesis_test.json` 或完成的同口径竞争/现金事实，因此本文件仍只是**字段可得性和冻结模板**；但不再需要为了公司学习伪造模型或行动 ID。

### 有噪声行业数据的工作规则

格力与供应商都可能无法精确说明全渠道份额、价格或库存；这不是把噪声资料丢弃，也不是把它当真实值。研究阶段可用 `TENTATIVE_WORKING_PATH` 把 AVC/产业在线类资料分为三种角色：`DIRECTIONAL_SENSOR_ONLY` 只提示需要研究哪条箭头；`WITHIN_PROVIDER_RELATIVE_CHANGE` 只在同一 provider、范围、品牌/渠道/分母 mapping 冻结后比较相对变化；`LEVEL_WITH_STATED_LIMITS` 还要求供应商保留可定位的方法与误差边界。三类都不是公司会计事实，均不能直接推到收入、返利、owner cash 或资本配置。

正式 FJ 只允许后两类；方向传感器不能结算数值预测或做零售状态分解。资料互相矛盾时不取平均数，也不以“多数报告”决定 H-A/H-B：先保留分歧，重开可能失真的测量边界或机制箭头，再检查其后公司官方的量价、费用、营运资本和现金传导。当前已物化的行业背景仍是 `CONTEXT_ONLY`，故格力保持 `UNDISCRIMINATED`；工作路径仅决定下一步取证，不是中心路径的替身。

## 已观察的四层驱动

| 候选 driver ID | 层 | 已核实观察 | 目前可说的最窄结论 | 不能说的结论 / 保守处理 |
|---|---|---|---|---|
| `FDBDRV:gree:competition_position` | `COMPETITION_DEMAND` | 家用空调线上零售额份额 2023/24/25 为 28.15% / 25.40% / 24.31%（`OBS:afe647833fb1c5f3df93`、`OBS:9b3fb48255d08db857f7`、`OBS:b2613325a585bba977af`）。2025 年报转引的家用空调内销同比 +0.7%（`OBS:7f6b64365094c2a1e194`），公司内销主营收入同比 -10.67%（`OBS:5a7383ab14e876f00c9b`）。已物化的 AVC 冷年背景显示线上 1.5HP 挂机均价下行、低价带份额扩大及行业库存压力，但与格力自然年/品牌口径不同。 | 同定义的**线上零售额**相对位置两年下降；公司收入走弱值得解释，且单期毛利稳定不足以排除行业价格/库存压力。 | 不能由销量行业数与公司收入计算份额，不能把线上份额称作全渠道护城河或价格战；也不能由行业价格/库存推出格力 ASP、返利或品牌份额。正式 bridge 前，竞争持续期不延长。 |
| `FDBDRV:gree:unit_economics` | `UNIT_ECONOMICS` | 2025 消费电器收入同比 -10.44%（`OBS:6e9fa0bb0b9c76bc8274`）、毛利率 35.28%（`OBS:489cf20c9c3ccc2543c9`，同比 +0.37pct）。 | 收入收缩并未与该产品分类的毛利率同步塌陷。 | 不把一项产品毛利称作 ASP、定价权或促销压力不存在；2023 的“空调”与 2024–25 的“消费电器”分类不连续，禁止拼成长序列。 |
| `FDBDRV:gree:cash_conversion` | `CASH_CONVERSION` | 2025 合并 OCF 463.83 亿元（`OBS:c9a732c202adc08d3350`），其中经营相关受限资金净减少 156.67 亿元（`OBS:06d9c7acf334a24913f8`）；现金 Capex 17.17 亿元（`OBS:d834abd1c88a761a9e02`）。同年销售收现 1,801.53 亿元（`OBS:c09d404d87c512e0d119`）、应收/存货/应付/合同负债为 159.87/281.83/421.04/152.07 亿元（`OBS:1585b0e2a81056af0f28`、`OBS:545074a09a0e90b122c2`、`OBS:34cb49ea6449ce6194d5`、`OBS:c9bbe86c1541a2d8d43f`）。同一现金流补充表把期末货币资金拆为现金及等价物 275.66 亿元（`OBS:c8f796cfc3a51829a270`）、不属于现金等价物的定期存款及应计利息 724.09 亿元（`OBS:a6e2ae8095e6d463ba5d`）及受限存款 105.78 亿元（`OBS:44d9cae2dd28a368c055`）。 | 表观 OCF 包含材料性、可能不可重复的受限资金释放；工作资本和预收货款的期末状态已可观察。货币资金的流动性分类也已可观察：期末“货币资金”不能整体被当成现金等价物。 | 不能把期末余额的变化、OCF、OCF/NP、OCF–Capex 或 275.66 亿元现金等价物直接称作 normal owner cash/普通股可分配现金；定期存款的期限与处置、受限资金的释放、金融业务资本需要、维持/增长 Capex 及营运资本仍须逐项分开。 |
| `FDBDRV:gree:capital_allocation` | `CAPITAL_ALLOCATION` | 2025 期末交易性金融资产 313.36 亿元（`OBS:fce9e4eb11eaecdca85b`），金融产品申购/赎回 616.61/284.55 亿元（`OBS:be8663f7f2683bc84f72`、`OBS:0e871cca360f5055c6bc`）；短借 679.57 亿元（`OBS:68753e4c00f2fb28d2dd`）；利息收入/费用 58.85/19.65 亿元（`OBS:996148ecd722e81a9538`、`OBS:77619ee2bdd007802c8e`）；格力钛在建工程减值 11.42 亿元（`OBS:62ba23a075d218cf61ea`）。格力钛控制权取得的 2021 司法拍卖成交价为 18.282751 亿元（`OBS:eab8d278a544bd4e74b9`）；经审计的 2023 年报确认当年增持少数股权作价 10.153284 亿元、直接持股升至 55.01%（`OBS:c1c65251216dff2c43b0`、`OBS:1e2908fcda19b18e1091`），年末投资成本滚动为 28.443861 亿元（`OBS:51ccc70e521cbeb81fb1`）。 | 金融资产的存量和滚动、格力钛的两次股权承诺与后续减值都是须进入资本配置复核的材料事项；2021 启动、2023 加码已不再是金额未知。 | 不把交易性金融资产或金融产品申购直接称为可分配现金、流动性无风险或价值毁损，也不从一次减值或 28.44 亿元投资成本推断格力钛全生命周期损失、追加投入、资金来源或退出价值；2021 公告价与 2023 年报期初成本存在小额口径差异，未经交易费用/会计处理 bridge 不相互替代。金融资产期限、底层资产、质押、格力钛后续经营现金/资本 movement 和实际资金来源仍需拆分，相关 normal owner cash 和资本回报输入为 `UNKNOWN`/保守区间。 |

每条 observation 的完整来源身份在 `company_blind_track/fact_observations.json`，竞争机制和跨期口径见 [状态转换编年](GREE_V1_STATE_TRANSITION_CHRONOLOGY.md)。以上不是四个已经通过验证的 `financial_driver_bridge` driver；它们是同一桥在真正报告产生模型与决策对象前的预注册候选。

### 2023–2025 最小现金状态序列：足以排除错误捷径，不足以生成 normal owner cash

以下均为合并年报当前期数，单位为亿元、四舍五入到两位；原始 observation、精确数值和页码在 `company_blind_track/fact_observations.json`。对应法定来源分别为 FY2023 `CNINFO:000651:ANN:20240430:1219928418`（reader 第 114–115、117、208、212 页）、FY2024 `CNINFO:000651:ANN:20250428:1223330631`（第 111–112、114、203、206–207 页）和 FY2025 `CNINFO:000651:ANN:20260429:1225250396`（第 86–87、89、177、180 页）。

| 口径（全部合并） | FY2023 | FY2024 | FY2025 | 允许的读取 |
|---|---:|---:|---:|---|
| 现金及现金等价物 | 309.14 | 211.41 | 275.66 | 可用现金状态，不等于普通股可分配现金。 |
| 不属于现金等价物的定期存款及应计利息 | 567.46 | 566.14 | 724.09 | 与现金等价物分列；期限、可支配性及再投资收益仍未知。 |
| 使用受限的存款 | 364.45 | 361.45 | 105.78 | 受限状态可观察，解除限制的时间/经济归属不可由余额推定。 |
| 交易性金融资产 | 96.14 | 165.48 | 313.36 | 存量可观察，底层资产、期限、质押和流动性仍未知。 |
| 合并 OCF | 563.98 | 293.69 | 463.83 | 只是报表 OCF，不是 normal owner cash。 |
| 现金 Capex | 54.26 | 33.00 | 17.17 | 现金投资流出；维持/增长属性未知。 |
| 销售商品、提供劳务收到的现金 | 2,224.51 | 1,719.37 | 1,801.53 | 只是一项合并收现，不可代替同口径销售、销量或需求。 |
| 应收 / 存货 / 应付 / 合同负债 | 160.99 / 325.79 / 411.47 / 135.89 | 168.32 / 279.11 / 470.91 / 124.91 | 159.87 / 281.83 / 421.04 / 152.07 | 可作为营运资本状态，不可仅凭期末变动解释现金或需求。 |
| 经营相关保证金/受限资金净减少（现金流入） | 6.30 | `UNKNOWN` | 156.67 | 2023 的披露为“票据质押保证金、保函保证金等”，2025 为“票据、保函保证金等经营活动有关”；方向相同但组成范围尚未逐项核对。 |
| 经营相关保证金/受限资金净增加（现金流出） | `UNKNOWN` | 9.51 | 9.51 | 与“净减少”必须分列；不得以正数余额把现金流出写成释放。 |

这组来源**足以**建立 `CASH_STATE` 监测底座，也明确显示 2025 OCF 的上升不能直接归因于经营质量：同年含 156.67 亿元的受限资金净减少，另有 9.51 亿元同类资金净增加。它**不构成**一个可用于模型的 `NORMAL_OWNER_CASH` 序列：2023 的保证金文字范围与后两年未证明完全一致，且仍没有按期拆分的营运资本贡献、金融子公司现金/监管资本、定期存款和交易性金融资产的期限/质押/收益、维持性 Capex 与真实普通股分配现金。新生产 policy 要求 `CASH_CONVERSION` driver 明确记录 `cash_normalization_contract.state`；格力当前只能填 `UNKNOWN` 并写明“不将 OCF、货币资金或 OCF–Capex 用作 normal owner cash”，不能把这一事实表伪装成调整桥。

此前采集规则会把 FY2024 的 9.51 亿元“净增加”误标成“释放”。该 `ACQUISITION_MODULE + REASONING` 缺陷已改为 `operating_restricted_funds_addition_rmb_m` 与 `operating_restricted_funds_release_rmb_m` 两个分方向字段；两者可在同一年分别披露，未证明同一资金池前不得自动轧差。这防止将保证金占用错误地加回 normal owner cash。

## 对立机制怎样进入 bridge

竞争层不允许由公司自身的线上数直接升级为“市场份额” driver。正式 `COMPETITION_DEMAND` driver 至少还要冻结：市场定义、客户替代、公司与同行/行业的同口径 comparison observation、比较的销量/销售额与 sell-in/sell-out 边界，以及范围限制。缺任一项时，该层即使保留 `OBSERVED` 原始事实，也不得成为竞争优势年限或终局份额的直接模型输入。

| 机制 | 可观察的早期传导 | 最小反证 | 对四层 bridge 的含义 |
|---|---|---|---|
| H-A：渠道/价格带重配 | 线上可弱，线下/全渠道或较高价格带相对位置稳定；量价组合、费用与调整后现金未共同恶化。 | 同口径线下/全渠道也下降，且费用、回款/库存与调整后现金一起变弱。 | 竞争层可被限制性地维持；单位经济性、现金层仍须用同口径来源验证。 |
| H-B：广泛竞争/价格实现恶化 | 弱势从线上扩展到全渠道；公司量/收入持续弱于同口径行业，费用/返利或工作资本随后恶化。 | 线上下滑不扩散，且费用、调整后现金和较高价/线下位置稳定。 | 竞争持续期、正常利润和现金转换使用保守情景；不由单期产品毛利解除约束。 |

详细的 H-A/H-B 相反预期及不可判别边界见 [对立机制设计](GREE_V1_RIVAL_HYPOTHESIS_DESIGN.md)。当前状态是 `UNDISCRIMINATED`，不得先选 H-A 或 H-B 再为其挑选数据。

### 出货、零售与库存不是同一个竞争证据

行业背景目前同时有 AVC 署名的冷年 shipment、retail sell-out 与库存压力描述。它们揭示了一个要先排除的机制：终端销售、渠道订单与上游供给并不必然同步，库存、促销或补货节奏可能放大上游观察。这个存量—流量边界来自 Lee、Padmanabhan 与 Whang 的[供应链原始研究](https://sloanreview.mit.edu/article/the-bullwhip-effect-in-supply-chains/)，但不是把其消费品结论直接移植到空调。

格力当前只能把这三类数据用作 `CONTEXT_ONLY`：行业出货/库存压力使“毛利稳定=没有价格或渠道压力”的推断更不可成立，却不支持“格力正在补库/去库”“格力需求强/弱”或 H-A/H-B 的任一方。只有未来同一 provider release 明确锁定 product、地域、渠道、品牌/行业分母、期间、交易点和库存归属，才允许由 `validate_stock_flow_reconciliation(...)` 判为 `RECONCILABLE`，随后再由人工、同口径会计规则核对 `shipment − sell-out` 是否与库存变动相容；目前 1.02 亿台 shipment、8,059 万台 retail 与冷年中期库存下限缺这些共同边界，状态为 `NOT_RECONCILABLE`。它不进入 `FDBMON:gree:competition:2026` 的 outcome，也不触发 owner-cash 或资本配置处理。

## 既有案例卡的研究路由（不新建案例库）

现有 `config/insight_case_benchmark.json` 的 8 张书籍方法卡已经足够；格力不需要新增“案例卡”，更不能把书中成功案例变成概率。当前采用“一主、两辅、一结果审计”的路由：

| 卡 | 角色 | 对格力的唯一工作 | 禁止捷径 |
|---|---|---|---|
| `operating_transition` | 主路由 | 将线上份额回落、收入收缩和未塌陷毛利写成 H-A/H-B 都能解释的异常；预选同状态但结果相反的成熟制造商 episode，并收集全渠道/量价费用/调整后现金的区分观察。 | “仍是第一”或单期毛利稳定不能裁决两条机制。 |
| `franchise_customer_lockin` | H-A 条件检验 | 只检验高端、线下、安装和售后是否存在真实的搜索、切换或失败成本。 | 品牌、经销网络或高毛利本身不等于客户锁定；不得照搬 WD-40 的低客单价情境。 |
| `technology_transition` | H-B 条件检验 | 只有当渠道数字化、能效/产品迭代实际改变客户替代或竞争成本时，才检验旧优势是否失效。 | 线上化本身不能证明护城河丧失；不得把 Intel 的技术代际风险套入空调。 |
| `mature_cash_return` | 结果审计 | 以受限资金、营运资本、维持性 Capex 与资本配置兑现审计两机制的最终现金含义。 | 高股息、表观 OCF 或低 PE 不是安全性证据。 |

`compounder_reinvestment` 留待获得渠道/高端/新业务的增量投入和回报后才启用；`distressed_survival`、`asset_catalyst` 不适用于当前竞争问题。`regulated_financial` 也不会因为持有金融产品而自动启用：只有出现外部股东控制权、监管资本约束或关联方资金安排的独立事实时，才把它作为“现金归属/可分配性”的另一个问题；不得让它替代本次竞争或 owner-cash bridge。案例卡只产生取证问题；格力事实、行业机制、同行对照、参考类/概率和估值始终分层。

这里的八张卡是研究原型而非八个已结算公司案例：它们没有 `MEP:` / `CASEEV:` episode，故当前 transfer 一律是 `QUESTION_ONLY`，不能为 H-A/H-B 提供 primary support、反例证据或经验频率。既有 `HBTCASE:600340:20200427` 同样不可填补此缺口——它是 `PIT_ENGINEERING / FROZEN_WITH_QUALITY_FAILURE` 工程诊断，四条 claim 没有实际 prediction，后续来源未读；可复用的是回测能力，不能把该工件当公司经验。

### 回测使用边界

2021 年格力钛控制权取得、2023 年增持与 2025 年工程减值可用于补齐该资本事项的事实编年与未来 `allocation_event` 合同，但不能在已知后续结果的今天倒写为 2021 年前瞻判断后计入公司经验。现有 HBT 对这种重建只允许 `UNCONTROLLED / EXPLORATORY / ENGINEERING_DIAGNOSTIC_ONLY`，不进入 calibration 或参考类分母。真正可学习的回放必须是：先在 cutoff 当时冻结 FJ 与 source policy，再读取窗口后的 observation；或者直接结算当年已有、带预测身份的第三方原始报告。禁止伪造冻结时间、以格力钛一次减值定义全生命周期损失，或把事后材料当作 H-A/H-B 的早期信号。

## 冻结前必须生成的监测合同

真实 bridge 的每个材料 driver 应附一个 `monitoring_contract`；资本配置事件另附 `realization_contract`。这两个对象不能用“以后关注”或一个自由文本兑现期代替。现在的 bridge validator 已强制前者含 `FDBMON:` ID、关联 FJ、metric/unit/basis、可比性规则、起止期间、允许的官方来源类型与观察窗口；后者须有 `FDBREAL:` ID，并分别嵌入早期行为信号和终局经营兑现的两个监测合同。重复合同 ID 或终局期间不晚于早期信号都会被拒绝。

| 合同 ID | 要区分的问题与 FJ | 度量与可比性规则 | 允许的后续来源 | 窗口 / 结果规则 |
|---|---|---|---|---|
| `FDBMON:gree:competition:2026` | H-A 与 H-B；`FJ:GREE:competitive_position` | 同地域、同渠道、同一销量或销售额口径的全渠道/线下/价格带相对位置；单独标记 sell-in/sell-out。没有相同定义不合并。 | 公司定期报告、交易所公告；独立物化并具名的行业源包。年报转引数据须保留提供者、定义和页码。 | 首次冻结后 6–12 个月；若只有线上份额或排名，结果为 `NOT_EVALUATED`，不是对任一机制的支持。 |
| `FDBMON:gree:unit_economics:2026` | `FJ:GREE:revenue_margin_transmission` | 同一产品分类内的销量、ASP、返利/佣金、销售费用率和产品毛利；分类变化时只结算共同字段或按预注册转换规则处理。 | 公司中报/年报、业绩会正式文字记录、具定义的行业源。 | 6–12 个月。毛利稳定但费用、ASP、销量未知时只记录 `PARTIAL`；不能把它结算为定价权正确。 |
| `FDBMON:gree:cash:2026` | `FJ:GREE:normalized_cash_conversion` | OCF、受限资金变化、应收/存货/应付、客户回款、合同负债与 Capex；对每项使用合并口径并分开重复性判断。 | 合并财报及附注。 | 每次年中/年报披露；在逐期 adjustment bridge 闭合前，normal owner cash 只能结算为 `UNRESOLVED`。 |
| `FDBMON:gree:allocation:2026` | `FJ:GREE:capital_allocation_realization` | 金融资产期限/收益/质押和资金来源；格力钛新增投入、减值、退出/停建、经营现金或进一步损失。 | 合并年报、中报、交易所公告。 | 6–12 个月记录行为信号、3–5 年记录经营兑现；未披露不以零处理。 |

`realization_contract` 的每笔 event 至少包括决策日期、启动承诺、后续 movement、管理层声明的机制、6–12 月行为信号、3–5 年兑现 outcome、来源范围和不可获得时的保守处理。新 policy 下，已披露启动金额必须连同币种、资金来源和 VERIFIED observation 冻结；金额已披露而资金来源未逐笔披露时，允许 `funding_source=UNKNOWN`，但必须解释未知并采取保守处理；金额本身未披露才可为 `amount=UNKNOWN`。启动后要记录首次可观察的 `ESCALATE`、`MAINTAIN`、`DEESCALATE` 或 `UNKNOWN`，并精确连接本 event 的 `FDBREAL:` 和相应早期/终局 `FDBMON:`；不能从减值、金融资产余额、价格或回报倒推这条链。格力当前至少有三类候选：2021 年格力钛控制权取得、2023 年格力钛增持（它是前一事件可观察的 `ESCALATE`，但也是一笔独立承诺）、以及金融资产滚动/格力钛工程减值的后续观察。前两项的金额已核实，资金来源及 2023 后的经营/资本 movement 未闭合；后两项不能反推累计投入。因此资本配置质量仍为 `UNRESOLVED`，不能预先写成 `VALUE_DESTRUCTIVE_CANDIDATE` 或 `LIQUIDITY_MANAGEMENT`。

## 前瞻判断：只冻结模板，不填假精确数字

一个可结算的前瞻判断必须有同 cutoff 的预测、挑战基线、测量规则、反证、证据、机制与 financial driver。`INVESTMENT_DECISION` 另须连接模型和决策；`COMPANY_JUDGMENT_ONLY` 必须无这些字段，只传导至正常化盈利和 owner cash。当前缺少中心路径、正式 FDB/FJ 对象和足以制定数值阈值的同口径数据，故以下是 FJ **模板**，不是待冻结的判断。

| FJ 模板 | 核心内容 | 结算期限 | 简单基线 | 当前不能参数化的原因 |
|---|---|---|---|---|
| `FJ:GREE:competitive_position` | 同口径全渠道/线下相对位置是否稳定或继续下降，并能区分 H-A/H-B。 | 6–12 月领先信号，3 年终局经营复核。 | 只有在取得一个同定义起点后，才可用 `CARRY_FORWARD`；不得以 24.31% 的线上销售额份额挑战全渠道目标。 | 无同口径全渠道/线下起点、主要对手比较或一致销售边界。 |
| `FJ:GREE:revenue_margin_transmission` | 国内需求、公司量价、返利/费用与产品/经营利润的联合方向。 | 6–12 月。 | 同分类的最近已披露收入增速/毛利率；不能跨“空调”与“消费电器”分类。 | 无销量、ASP、返利/佣金和销售费用的共同边界。 |
| `FJ:GREE:normalized_cash_conversion` | 经受限资金、工作资本和 Capex 调整后的现金转换是否支持或反证已选机制。 | 每年，3 年复核。 | 最近已冻结的**调整后**现金转换；没有 adjustment bridge 就没有基线。 | 2025 高 OCF 含 156.67 亿元释放，维持性 Capex 与金融业务影响未拆。 |
| `FJ:GREE:capital_allocation_realization` | 资本配置事件是否在预注册窗口内出现可观察的经营兑现、减值、退出或继续投入。 | 6–12 月行为、3–5 年兑现。 | 事件发生后“不再追加可验证资金/损失”的明示基线只可在完整 event contract 后使用。 | 格力钛已知的 2021/2023 股权投入尚缺资金来源、2023 后的资源 movement 与经营兑现；金融资产期限、收益、质押和资金来源亦未闭合。 |

生成实际 FJ 时还必须：

1. 对 H-A 和 H-B 各写相反的、预先约定的结果序列，而不是一条“乐观”和一条“悲观”文字；
2. 每条 prediction 只针对一个 metric/unit/measurement period，指定允许来源、首次披露或修订版本政策、`resolution_due` 和可比性处理；
3. 把实际 FJ 的 `financial_driver_ids` 绑定至已通过的 bridge；投资用途再绑定实际 valuation model 与 decision entry，CJO 反而必须拒绝这些字段；没有市场轨时可冻结公司经营判断，但不能伪造 expected-return 结论；
4. 为可量化 FJ 保存不含价格、估值倍数和结果期信息的简单基线；若不存在可比起点，写 `UNKNOWN`，不造一个平均数；
5. 将未到期的 3–5 年 FJ 在 6–12 月结算中保持 `PARTIAL / NOT_EVALUATED`，不让它们阻断早期公司学习，也不向过去改写事实。

## 与现有回测的接法和当前缺口

现有 `historical_backtest` 已能保存冻结的预测、measurement rule、source provenance、区间预测和经营 observation；这正适合结算上述 FJ，而不适合用事后股价替代公司判断。实现前曾有两项会阻断真正的公司学习闭环的缺口：

1. V2 settlement 对所有 claim 都要求 `closes_at <= settlement_as_of`，所以一个同时含 6–12 月与 3–5 年 FJ 的 case 不能在早期得到 `REVIEWABLE` settlement；
2. settlement 无条件要求 `investment_return_outcome`。无价格、无动作的公司判断 case 因而不能成为生产可审阅结算。

该窄改动现已实现于 v2 historical backtest：`COMPANY_JUDGMENT_ONLY` case 强制未知 price identity、禁止投资动作、市场源和投资回报，return outcome 固定为 `NOT_APPLICABLE`；早期 settlement 只结算到期 claim，未来 claim 必须为无 observation 的 `PARTIAL`。同一 immutable case 用 `settlement_series_id`、连续序号和前序 settlement ID 追加；series validator 会拒绝改写已经 `CALCULATED` 的 claim 或其 observation。它不改变含价格 case 的严格 return 验证，也不把公司多个结算时点计作多个独立基准率样本。格力还没有一个 production V1 具备正式 FDB/FJ，故这证明学习回路可用，不是格力已经完成冻结。

回测的正确下一用法是：待格力或一个可比公司的主/反机制、无价格 FJ、来源和观察窗被冻结后，以 6–12 个月经营信号先结算机制，再在终局经营窗口结算传导；不是用已知股价或工程 fixture 为报告增加“案例”。

### 首个历史 episode 候选：2021 格力钛控制权取得（尚未准入）

完整的 cutoff、结果期材料、双机制和拒绝理由见[格力钛 2021 episode 准入审阅](GREE_TITANIUM_2021_EPISODE_ELIGIBILITY_REVIEW.md)。

这比把书中案例直接贴到格力更接近可学习的公司经验，但目前仍只是候选。2021-10-30 官方进展公告可作为 PIT 起点：格力以 182,827.51 万元竞得银隆新能源 30.47% 股权，并通过表决权安排合计控制 47.93%。其后官方年报提供了两个可读的结果节点：2023 年 12 月受让 24.54% 少数股权，作价 101,532.84 万元、直接持股升至 55.01%；2025 年年报则记载格力钛工程新增减值 99,597.01 万元、累计减值 114,216.53 万元，理由为部分项目不再建设且无法带来预期经济利益。

可检验的窄问题不是“格力钛是否已失败”，而是：在 2021 控制权取得时，**有界整合并产生可观察兑现**，与**继续资本承诺/工程减值在兑现前显性化**，哪一条更符合后续公开序列。2023 追加股权与 2025 工程减值是后一机制的材料观察，但不证明累计投入、总回报、所有项目价值或最终退出结果；也不能自动迁移到空调竞争 H-A/H-B。

它尚不能成为 `MEP:`：须先建立只包含 2021-10-30 前当时资料的独立 PIT source package，预注册两方链条、至少一项 6–12 月**有诊断性**的早期信号和一个终局经营/资本配置信号，并物化 2022–25 的已读官方 outcome。结果期材料其实不少：2022-04 披露的 2021 年报记录自 2021-10-31 取得控制至年末，格力钛收入 6.94 亿元、净亏损 4.17 亿元，并以“业务关系已理顺、取得初步成果”描述整合；2022 年**半年度报告**（收购后约十个月）又记录收入 11.67 亿元、净亏损 6.58 亿元、经营现金流 -1.50 亿元和总担保 65.37 亿元。它们是可读的早期 outcome，不等于可结算的 early FJ：2021 收购公告的 1–7 月数据不是与上述任一期间同口径的比较基线，而“增强盈利能力／协同将逐步释放”没有测量指标、期间或阈值；把后来的两期收入、亏损、现金或管理层自评反推出当时 H-A/H-B 的不同预测，都会把结果当设计。收购初期亏损、担保与“初步成果”也仍可与两条机制相容。因此现有早期材料只能登记为 `MIXED / NOT_DIAGNOSTIC` 的候选 outcome，不是 H-B 已被证明。

这一轮的准入结论是：缺口不是“再找一份早期报告”，而是 cutoff 当时缺少一个能让两方**作出不同、可度量、到期**预测的承诺或外部基线。只有先前材料已经指定 metric、比较对象、观察窗和允许来源时，管理层的整合语言才可进入 FJ；否则它只可作为 `MECHANISM_DISCOVERY`。剩余工作是独立 source selection、以只读 2021 材料设计至少一个真正分叉的 FJ，或诚实判定无此 FJ 并拒绝此 episode；“当年没有看到追加投资”同样不能由公告缺席推断。因此此候选的状态仍为 `CANDIDATE / NOT_A_CASE / NOT_A_BASE_RATE`。它是回测下一步应优先补的一个真实公司经验样本，不是对当前格力 V1 的资本配置定论。

## 阻断项、根因与接纳条件

| 根因 | 经济影响 | 缺失事实 / 禁止假设 | 可执行补救 | 允许冻结的接纳条件 |
|---|---|---|---|---|
| `DATA_COVERAGE` | 可能错判竞争持续期、normal owner cash、永久损失与价值区间。 | 缺全渠道/线下份额、量价费用、经销与调整后现金；不得把线上份额、单期毛利或 OCF 当替代品。 | 按四份 monitoring contract 物化后续官方/具名行业观察；无法取得即保留 `UNKNOWN`。 | 四层均有可用事实或明确 conservative treatment，且竞争比较同口径。 |
| `ACQUISITION_MODULE` | 逐期现金/资本事项不结构化会让错误口径进入模型。 | 缺从报表到 normal owner cash 的 adjustment bridge、金融资产期限、格力钛后续 event extraction，以及事件启动投入/资金来源与后续 movement。 | 扩展可复用采集字段与事件 contract，再重新提取。 | 每个材料 adjustment/event 有 source ID、时期、量纲、范围、启动/后续 movement 和结算窗口；无法取得时保留 `UNKNOWN`。 |
| `REASONING` | 可能把渠道重配认成护城河，或把组合毛利认成价格权。 | 禁止在 H-A/H-B 未判别前选中心路径或写精确概率。 | 保持对立机制，优先收集信息增益最高的同口径渠道/量价费用观察。 | 每个核心机制有相反预期、反证、4 段传导和可结算信号。 |
| `MODEL` | 可能把未正常化现金或未分类资本配置固化为 EPV/return，或让公司学习被伪交易对象污染。 | 禁止绑定虚构模型/决策 ID，禁止让价格回填公司判断。 | CJO 先以四层 FDB、monitoring contract 与经营 FJ 冻结；仅投资报告另建 valuation model 与 decision ledger。 | CJO 的 FDB/FJ 与官方事实、driver monitoring 和经营传导一致；投资用途另有实际模型输入与决策条目。 |
| `WRITING` | 更长报告会制造判断已形成的错觉。 | 禁止把模板、年报转引数据或 historical chronology 写成已验证判断。 | 正文明确 `UNDISCRIMINATED`、范围与 UNKNOWN，并展示将改变结论的信号。 | 报告区分已观察事实、机制、预测、基线和结算结果。 |

## 升级顺序

1. [官方行业环境包](CHINA_HOME_APPLIANCE_OFFICIAL_CONTEXT_PACKAGE_DESIGN.md)已物化为 7 份原始发布物和 8 条 `REVIEWABLE_CONTEXT_ONLY` 观察；它只补生产、广义零售、政策、出口、房地产与工程环境，不能假装补齐空调内销台数、国内 ASP、品牌或线上份额。
2. 获取/结构化四份监测合同中的决定性公司或具名行业观察，先验证口径可比性：零售端优先获取 AVC 一类的品牌×渠道×销量/额×ASP/价格带历史版本；出货端可另取产业在线一类的品牌内销轨，但只有 provider 自身定义保存于来源包时才可标记 `sell_in`，否则为 `SHIPMENT_SEMANTICS_UNRESOLVED`，不得与零售轨混算。返利/佣金、经销库存、销售回款、受限资金、维持性 Capex 与资本事项仍只由公司披露/附注补齐；执行字段、期间和接入顺序见[格力 V1 独立行业 release 最小交付单](GREE_V1_INDUSTRY_RELEASE_ACQUISITION_SPEC.md)及[独立行业数据 PIT 来源契约](INDEPENDENT_INDUSTRY_DATA_SOURCE_CONTRACT.md)。
3. 完成四层 `financial_driver_bridge` 和 allocation event contracts；CJO 只绑定 FJ monitoring，投资报告才追加 valuation model 与 decision ledger。
4. 只在 H-A/H-B 出现材料性区分后选择中心路径，冻结 3–5 条 FJ 与简单基线。
5. 用 `COMPANY_JUDGMENT_ONLY` 的追加式 settlement 先结算早期机制信号；价格轨、估值和投资结论仍是后续独立问题。
