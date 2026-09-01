# 激成投资：独立结果后配对审阅

> company：`HK:00184 / 激成投资`
>
> cutoff：`2022-05-01T00:00:00+08:00`
>
> outcome period：`FY2022`
>
> settlement commit：`2a7b746`
>
> paired utility decision：`NO_MATERIAL_UTILITY`

## 独立性与读取边界

本审阅由独立于 curator 和 outcome custodian 的 fresh reviewer 完成。输入严格限于本 episode 的
`01_PREOUTCOME_EVIDENCE_AND_JUDGMENT_FREEZE.md`、
`02_FAIR_BASELINE_BEFORE_LEARNING_CONTRACT.json`、
`03_ENHANCED_AFTER_LEARNING_AND_OUTCOME_CELLS.json`，以及 settlement commit `2a7b746` 中的
`06_CUSTODIAN_OUTCOME_SETTLEMENT.json`。

审阅人没有读取价格、回报、旧派生报告或其他材料。Baseline 与 Enhanced 使用同一份 06 settlement
facts；本裁决不给字段数量、结构完整、文字清晰或规则遵守本身任何效用信用。

## 机械结果复核

### H1：客户吸收向量

八家固定酒店中：

- 西贡喜来登、帆船、大阪、旧金山 W、渥太华喜来登和多伦多机场 Delta 六家酒店同时实现 occupancy、
  ADR 与同物业本币 implied RevPAR 上升，结算为 `PRICE_AND_VOLUME_ABSORPTION`；
- 武汉入住率由 `45.6%` 上升至 `51.1%`，但 ADR 由 `CNY397` 降至 `CNY305`，implied RevPAR
  由约 `CNY181.0` 降至 `CNY155.9`，结算为 `VOLUME_LED_RATE_DILUTION`；
- 纽约索菲特 FY2021 仅自 11 月重开，全年比较不合格，结算为 `REOPENING_ONLY`。

向量保留物业、币种、所有权与重开边界，没有把六家正向酒店机械变成分数，也没有用纽约的重开低基数制造
吸收结果。

### H2：经常性酒店经济

酒店分部收入由 `HK$380.351m` 上升至 `HK$1,331.028m`。按冻结桥接：

- controlled recurring EBIT：`-HK$238.802m → HK$100.197m`；
- controlled recurring pre-D&A：`-HK$88.574m → HK$245.001m`；
- associate hotel result 独立保留：`-HK$11.627m → HK$14.073m`。

三条核心经营方向共同改善，结算为 `REVENUE_AND_ECONOMICS_RECOVER`。该改善不是由 FY2020 减值消失、
税项抵免、融资成本或联营结果单独制造。未能把集团 PPE 处置收益分配到酒店分部是局部未知；它不改变收入、
recurring EBIT 和 pre-D&A 三者均改善的方向。

### P1：澳门物业

FY2022 没有物业出售。租金收入 `HK$85.8m → HK$82.0m`、住宅出租率 `79% → 72%`、物业分部收入
`HK$100.620m → HK$96.346m`；办公室出租率 `93% → 100%`，物业分部结果
`HK$58.946m → HK$61.550m`。投资物业公允价值增加 `HK$3.9m`，但没有现金兑现。

经常性信号冲突，结算为 `HOLD_WITH_RENTAL_SUPPORT_MIXED_OR_STABLE`。公允价值、租赁经营和处置继续
分开，没有把估值增加写成现金或管理层资本配置成功。

### C1：集团现金

FY2022 综合 OCF 为 `HK$311.791m`，现金 PPE 购买为 `HK$21.653m`，reported post-capex group
proxy 为 `HK$290.138m`。进一步扣除 OCF 外现金利息 `HK$41.290m` 与 NCI 股息 `HK$57.096m` 后，
集团一期方向代理仍为正 `HK$191.752m`。

maintenance adequacy、资本承诺的维护/增长属性和 parent access 均未闭合，因此结算为
`POSITIVE_GROUP_CASH_SCOPE_UNKNOWN`。当前集团现金恢复得到承认，但不能升级 normalized parent owner
cash，也不能由 C1 直接降低永久损失。

### R1：永久损失

银行贷款为 `HK$1,435.804m`，其中 `HK$1,359.323m` 在一年内或按要求偿还。存款及现金总额
`HK$1,341.269m`，但可用与受限现金未拆分；总现金与一年内银行债务的非合格背景比例约 `0.987x`。
两笔附属公司贷款仍有契约比率偏离，豁免覆盖至 2023 年 10 月到期；没有披露已完成或有合同约束力的
再融资。没有披露被迫处置或未获豁免的违约。

因此结算为 `REFINANCING_OR_WAIVER_DEPENDENCY_PERSISTS`。正向集团现金不能消除期限集中、抵押与滚动
豁免风险；没有新增酒店减值也不能证明资产经济价值恢复。

## 公平 Baseline 结果后处理

公平 Baseline 不是一个只看 reported profit 的稻草人。它事先知道 reopening 不是经济吸收、ADR 与
partial-year 可比性必须处理、OCF-capex 不是 parent owner cash、现金利息和 NCI claim 不能遗漏、
maintenance 与 parent access 是局部边界，也知道公允价值、处置、减值和契约具有不同经济含义。

在同一 settlement facts 下，公平 Baseline 会形成以下结果后处理：

1. 六家同物业出现价量共振，武汉是量升价降，纽约只是重开；结合酒店分部收入大幅恢复，酒店客户需求已经
   从“重开选择权”升级为“广泛但仍不完全一致的真实吸收”。
2. 即使不使用 Enhanced 的类别名称，普通的分部对账也会看到 recurring EBIT 与 pre-D&A 从负转正，
   因而升级酒店经营执行，而不是把 reported contribution 或减值消失当作恢复。
3. 澳门租赁信号混合、没有出售、公允价值只是非现金范围输入，因此继续把物业视为经常性缓冲而非已兑现
   安全垫。
4. 集团现金代理已从负转正，但 maintenance 与 parent access 未闭合，故只承认集团现金恢复，不承认
   normalized parent owner cash。
5. 一年内债务集中、可用现金不明且继续依赖契约豁免，因此保留材料的再融资与永久损失折价，不因现金转正
   把风险降为低。

Baseline 的管理层、owner cash、永久损失、情景和方向性估值处理，与下述 Enhanced 处理在材料上相同。

## Enhanced 结果后处理

Enhanced 机械得到：

- `H1 = 6 × PRICE_AND_VOLUME_ABSORPTION + 1 × VOLUME_LED_RATE_DILUTION + 1 × REOPENING_ONLY`；
- `H2 = REVENUE_AND_ECONOMICS_RECOVER`；
- `P1 = HOLD_WITH_RENTAL_SUPPORT_MIXED_OR_STABLE`；
- `C1 = POSITIVE_GROUP_CASH_SCOPE_UNKNOWN`；
- `R1 = REFINANCING_OR_WAIVER_DEPENDENCY_PERSISTS`。

它更清楚地标出物业、经营、现金和资金风险的责任轴，但最终仍是：升级酒店经营；保留澳门物业缓冲；承认
集团现金恢复但不承认 normalized parent owner cash；维持中等、条件性的永久损失风险和再融资折价。

## 两臂材料差异

| 判断维度 | 公平 Baseline | Enhanced | 材料差异 |
| --- | --- | --- | --- |
| 酒店客户与经营 | 广泛真实恢复，武汉/纽约局部保留 | H1 向量 + H2 经常性恢复 | 无 |
| 管理层 | 升级酒店经营执行；资本与融资仍条件性 | 同左，责任轴更明确 | 无 |
| 澳门物业 | 经常性缓冲，经营混合，未兑现 | P1 mixed/stable | 无 |
| Owner cash | 集团一期现金转正；parent normalized 未证 | C1 scope unknown | 无 |
| 永久损失 | 现金改善但期限/豁免依赖仍在，维持条件性风险 | R1 dependency persists | 无 |
| 情景 | 上修酒店基准路径，保留资金悲观分支 | 同左 | 无 |
| 方向性估值 | 上修酒店恢复范围，不给完整正常化；保留折价 | 同左 | 无 |
| 下一研究动作 | 维护资本、parent access、再融资为首要缺口 | 同左 | 无 |

特别结论：六家 price-and-volume、H2 recurring 恢复、C1 正但 scope unknown、R1 waiver 持续，都改变了
公司判断，但没有让 Enhanced 得出公平 Baseline 不会得出的材料投资处理。

## Paired utility 裁决

最终裁决：`NO_MATERIAL_UTILITY`。

理由不是本案例“没有学到公司事实”，而是结果信号足够强且边界足够明显：

- 六家酒店价量同升与 H2 两条经常性经营桥共同指向真正恢复，公平 Baseline 也会升级酒店经营；
- Baseline 已预先知道 positive group proxy 不能跨过 maintenance、NCI 和 parent access，因此不会把
  C1 写成 parent owner cash；
- Baseline 已预先知道契约豁免、抵押和流动性属于永久损失证据，因此不会因现金转正消除 R1 风险；
- P1 的租赁、公允价值和处置分离也是公平 Baseline 的普通能力。

Enhanced 的固定向量和 first-match 分类提高了可审计性与解释清晰度，但没有改变管理层评价、owner cash、
永久损失、情景排序、估值方向或下一项材料研究行动。按结果前合同，这些改进只能记为零效用，不能把结构
更细事后改写成训练有效。

该结果不是 `HARMFUL`：Enhanced 没有抹去支持性判断，也没有让局部 UNKNOWN 跨轴降级。它也不是
`NOT_DIAGNOSTIC`：五个 cell 均有可用结果，足以比较两臂；比较结果明确为相同处理。

## 当前最重要的三项企业判断

### 1. 酒店恢复已从重开升级为真实经营恢复，但尚不能直接当作正常周期盈利

机制：`旅行、商务与会议需求恢复 → occupancy 与 ADR/RevPAR 同升 → 收入恢复 → 固定成本吸收 →
recurring EBIT 与 pre-D&A 转正`。

六家酒店有价量共振，酒店分部收入、controlled recurring EBIT 和 pre-D&A 同时改善，证明恢复不只是
开门或会计表象。最强反方是比较基数极低、各物业运营天数未披露、纽约仍不可比、武汉 RevPAR 下降，而且
只有一个恢复年度，尚不足以承保正常周期利润率。

当前判断：`BROAD_HOTEL_ECONOMIC_RECOVERY_OBSERVED / NORMALIZED_EARNINGS_NOT_YET_PROVEN`。

### 2. 集团已经恢复正向现金生成，但 parent owner cash 仍是有条件的

机制：`酒店经常性经营恢复 + 澳门物业缓冲 → OCF → reported capex → OCF 外利息与 NCI claim →
可供母公司股东使用的现金`。

扣除 reported capex、OCF 外现金利息和 NCI 股息后，集团一期代理仍为正约 `HK$191.8m`，这是材料改善。
最强反方是 maintenance adequacy、资本承诺性质和 parent access 未披露；当前现金可能包含不能自由上游的
子公司或 NCI 经济权益，一年结果也不是 normalized cash。

当前判断：`POSITIVE_CURRENT_GROUP_CASH / NORMALIZED_PARENT_OWNER_CASH_UNDERWRITTEN`。

### 3. 经营风险下降，但永久损失仍由再融资期限与契约依赖主导

机制：`正向经营现金 → 降低烧钱速度`，但同时存在
`一年内债务集中 + 可用现金边界未知 + 抵押资产 + waiver dependency → 再融资/被迫行动风险`。

经营恢复和低净债务提供实质缓冲。最强反方是约 `HK$1,359.3m` 银行债务一年内到期或按要求偿还，披露
现金总额也略低于该数，且其中受限部分不明；契约偏离只由截至到期日的豁免覆盖，没有完成或具约束力的
再融资。

当前判断：`OPERATING_LOSS_RISK_DOWN / REFINANCING_DEPENDENCY_PERSISTS /
PERMANENT_LOSS_MEDIUM_CONDITIONAL`。

## 管理层与执行评价

管理层在酒店经营上的评价应上修：按地域重开、成本控制和客群恢复已经穿过收入与经常性经营结果，不再只是
“自适应但经济恢复未证”。六家酒店价量同升说明客户与定价执行具有广度。

但资本配置与资产负债表执行仍只能评为条件性：澳门待售物业未兑现，maintenance adequacy 未闭合，parent
access 未证，两笔贷款继续依赖豁免且没有完成再融资。综合评价为：

`HOTEL_OPERATING_EXECUTION_UPGRADED / CAPITAL_MAINTENANCE_AND_REFINANCING_EXECUTION_CONDITIONAL`。

## Owner cash 与永久损失

- 承认 `HK$191.752m` 是扣除 reported capex、OCF 外利息和已观察 NCI 股息后的正向集团一期代理；
- 不把它称为 normalized parent owner cash；
- 不以公允价值、借款、存款重分类或处置款创造经营现金；
- maintenance 和 parent access 的 UNKNOWN 只限制 owner-cash 升级，不撤回酒店经营或集团现金判断；
- 不因没有新增减值就降低资产风险；
- 永久损失维持中等、条件性，核心翻转点是到期覆盖和契约依赖，而非利润表符号。

## 下一期经营情景

不赋伪精确概率。当前仍以基准情景优先，但基准路径较结果前明显上修；乐观路径变得更可信，悲观路径的核心
从“酒店持续关停”转为“恢复不能覆盖维护与再融资”。

### 乐观

六家酒店的价量共振延续，武汉恢复 rate/RevPAR，纽约形成完整可比年度；controlled recurring EBIT 与
pre-D&A 保持正向。维护资本得到覆盖，parent access 有证据支持，贷款完成再融资或形成有约束力的期限延长，
澳门租赁稳定。

### 基准

酒店收入和经常性经营保持恢复，但增速从低基数回落，物业间继续分化。集团现金保持正向，maintenance 和
parent access 仍需保守处理；澳门物业继续提供混合但正向的经营缓冲。管理层通过豁免或临近到期安排维持
流动性，但再融资风险尚未完全解除。

### 悲观

价量恢复反转或 rate dilution 扩散，recurring EBIT/pre-D&A 再次走弱；维护与翻新需求上升，使集团现金
代理不能转成 parent owner cash。契约豁免到期前没有完成融资，出现加速偿还、昂贵再融资、减值或被迫资产
处置；澳门住宅租赁继续恶化。

## 方向性估值处理

本审阅不使用价格，也不生成正式估值或最高买价。方向上：

- 酒店从“未承保恢复选择权”上修为“已有经营与现金支持的恢复资产范围”，但只给恢复区间，不直接使用完整
  正常周期利润率或倍数；
- 澳门物业继续以经常性租金和保守资产范围估值，公允价值增加只作范围输入，保留实现折价；
- 集团正向现金支持提高酒店范围下限，但 maintenance 与 parent access 未闭合，不能使用 parent cash multiple；
- 净债务、NCI、抵押和一年期再融资风险单列，继续保留融资与永久损失折价；
- 只有完成再融资或有约束力延长期限并改善覆盖，才允许降低近端 distress discount。

## 会翻转当前判断的新事实

向上翻转：

- 下一期同物业价量继续改善，武汉 RevPAR 恢复，纽约获得完整可比经营数据；
- controlled recurring EBIT 与 pre-D&A 在非低基数年度仍为正；
- maintenance adequacy 和 parent cash access 得到直接证据支持；
- 完成或形成有约束力的再融资，且一至两年可用流动性覆盖改善；
- 澳门租金、住宅出租率及分部收入共同改善。

向下翻转：

- 六家价量共振消失，收入、recurring EBIT 或 pre-D&A 恶化；
- 维护、翻新或资本承诺使扣 claim 后集团现金转负；
- parent access 被明确阻断；
- 契约豁免失效、债务加速、惩罚性再融资、材料减值或被迫低价处置；
- 澳门租金、住宅出租率与物业分部结果共同下行。

## 下一公司研究行为变化

本案例不支持冻结 Enhanced 方法，因为两臂处理相同。下一公司应改变的是实验选择与比较方式，而不是增加
gate：

1. 优先选择结果轴真正冲突的 episode，例如 deployment/occupancy 上升但 rate、recurring economics、
   cash 或 covenant 恶化；强同向恢复案例无法检验局部化是否改善投资处理。
2. 在 outcome 前不仅冻结 baseline 能力，还应冻结 baseline 的材料处理与下一研究动作，避免结果后把普通
   判断差异误写成方法效用。
3. 继续要求经营桥剥离融资、税、联营和减值，现金桥处理 OCF 外利息、NCI、maintenance 与 parent access，
   期限风险处理完成融资与仅承诺融资；这些已证明是形成公司判断所需的普通能力，但本案例没有证明 Enhanced
   相对 baseline 的迁移优势。
4. 若下一案例两臂仍得到相同管理层、owner cash、永久损失、估值和研究动作，应再次记录零效用，不因结构
   更细增加奖励。

## 权限

- `outcome_fact_extraction_and_cell_settlement = COMPLETED`；
- `paired_utility = NO_MATERIAL_UTILITY`；
- `learning_permission = NONE`；
- `transfer_validated = NONE`；
- `method_frozen = NONE`；
- `Comparative / CJO / formal_valuation / BuyBand / report / investment_action = NONE`。

本裁决只关闭 HK00184 的结果后 paired review；不得把酒店恢复本身或本文件的完整度当成 Enhanced 方法有效
或跨公司迁移成立。
