# 激成投资：独立结果前审阅

> company：`HK:00184 / 激成投资`
>
> episode：`EJE_HK00184_20220501 / FY2022`
>
> reviewed freeze commit：`8652fca`
>
> review decision：`ACCEPT`
>
> outcome access：`SEALED`

## 独立性与结果隔离

本审阅只复核 reviewed freeze commit `8652fca` 中的结果前工件 `00`--`03`，并只以 FY2020、
FY2021 两份白名单发行人官方年报验证 cutoff 前事实与口径。审阅人未打开、搜索、摘录或推断 FY2022
年报正文，也未读取旧派生报告、价格或回报。

本文件是结果前合同的独立验收，不是 outcome authorization。它只允许下一步另行签署 authorization；
在 authorization 正式存在以前，FY2022 继续封存。

## 首轮 RETURN

首轮独立审阅曾因以下四项材料问题返回：

1. `H2_HOTEL_RECURRING_ECONOMICS` 没有机械剥离融资、税项、联营结果及减值消失，可能把非经营变化
   冒充酒店执行改善。
2. `C1_CONSOLIDATED_POST_CAPEX_CASH_PROXY` 对“维护资本不足”或“母公司现金取得受阻”没有穷尽
   类别，也没有在正向集团代理之后处理 OCF 外现金利息和 NCI 现金 claim。
3. `P1_MACAU_RECURRING_PROPERTY_AND_MONETIZATION` 对“出售、账面值和净现金均已结算，但所得款用途
   未披露”的真实处置没有类别。
4. `R1_PERMANENT_LOSS_SIGNAL` 可能把滚动契约豁免或仅承诺、尚未完成的再融资误判为风险缓解，且
   没有结算一至两年债务期限覆盖。

这些问题会分别错误改变管理层执行、正常盈利、parent owner cash、永久损失和估值方向，因此在修复前
不得开放结果。

## 修复验收

### H2：经常性酒店经营桥

修订后已冻结两条显式桥：

- `CONTROLLED_HOTEL_RECURRING_EBIT_HKD_THOUSAND`；
- `CONTROLLED_HOTEL_RECURRING_PRE_D_AND_A_HKD_THOUSAND`。

融资成本、税项抵免或开支、联营酒店结果、减值及拨回、处置、公允价值和其他已披露非经常项分别对账；
联营结果独立结算，不能升级受控酒店经营。只有可比酒店收入、受控酒店 recurring EBIT 和 pre-D&A
三者共同改善，才允许升级酒店经营执行。FY2020 减值不再重复、税项变化、融资变化或联营变化单独出现，
均不能制造经营恢复。

### C1：集团现金、维护资本与母公司取得

修订后的 first-match 顺序为：

1. 同一集团边界无法结算；
2. reported post-capex proxy 非正；
3. reported proxy 为正但现金利息或 NCI claim 未结算；
4. 扣除 OCF 外现金利息及 NCI claim 后非正；
5. 集团现金为正但维护资本不足；
6. 集团现金为正但 parent access 受阻；
7. 维护资本充足且 parent access 有证据支持；
8. 其余维护资本或 parent access 局部未知。

这覆盖 OCF/proxy 正负、现金 claim、维护资本 `ADEQUATE / UNDERFUNDED / UNKNOWN` 与 parent access
`EVIDENCED / BLOCKED / UNKNOWN` 的组合。现金利息仅在列于 OCF 外时扣除，避免重复扣减；正向集团现金
不能自动成为 parent owner cash。所有 C1 类别均禁止直接改变永久损失，现金信号只交给 R1 结算。

### P1：租赁、公允价值与实际处置

租赁经营、公允价值和物业处置继续分轴。匹配物业只要已经完成出售，且净现金所得与账面值可以定位，便结算
`CASH_DISPOSAL_REALIZED`；所得款用途可以为 `UNKNOWN`。用途未知只阻止资本再配置或偿债执行信用，
不抹去一次性现金和资产实现价值，也不把处置写成经常性 owner cash。

### R1：契约、期限与永久损失

修订后单列：

- 一年内及累计两年内银行债务；
- 可用现金、受限现金和有约束力的未动用额度；
- 一年及两年期限的可用流动性覆盖；
- 契约偏离、豁免期限和依赖；
- 已完成或有合同约束力的延长期限，与仅计划或承诺但未完成的融资。

新材料酒店减值或被迫低于账面值出售优先结算；未获豁免的违约、加速偿还或未获完成融资覆盖的一年期
流动性缺口升级风险。滚动十二个月豁免及仅承诺、尚未完成的融资只能维持依赖。只有契约依赖因重新合规而
解除，或再融资已经完成/形成合同约束并实质延长期限，同时相关一至两年覆盖改善，才允许把近端资金风险
局部下调一步。没有新增减值不能证明经营或资产价值恢复。

## 17/17 结果前反例

审阅人按 `03` 中各 cell 的既定顺序机械执行 17 个结果前反例。17 个 case id 均唯一，每个预期类别都存在，
且每例恰好命中一个首个类别：

| 组别 | 反例 | 首个结算类别 | 验收 |
| --- | --- | --- | --- |
| H2 | impairment 消失、收入上升、recurring EBIT/pre-D&A 不变 | `DEMAND_WITHOUT_ECONOMICS` | PASS |
| H2 | 收入、recurring EBIT、pre-D&A 同时改善 | `REVENUE_AND_ECONOMICS_RECOVER` | PASS |
| H2 | 仅联营、税项或融资使 reported contribution 改善 | `MIXED_OR_STABLE` | PASS |
| C1 | reported proxy 非正、现金 claim 未知 | `NONPOSITIVE_REPORTED_PROXY` | PASS |
| C1 | reported proxy 为正、现金利息或 NCI claim 未知 | `POSITIVE_REPORTED_PROXY_CASH_CLAIMS_UNKNOWN` | PASS |
| C1 | 正向 reported proxy 被现金利息及 NCI claim 耗尽 | `NONPOSITIVE_AFTER_INTEREST_AND_NCI_CLAIMS` | PASS |
| C1 | 扣 claim 后为正、维护资本不足 | `POSITIVE_GROUP_CASH_MAINTENANCE_UNDERFUNDED` | PASS |
| C1 | 扣 claim 后为正、parent access 受阻 | `POSITIVE_GROUP_CASH_PARENT_BLOCKED` | PASS |
| C1 | 扣 claim 后为正、维护充足、parent access 有证据 | `PARENT_OWNER_CASH_SUPPORT` | PASS |
| C1 | 扣 claim 后为正、维护或 parent access 仍未知 | `POSITIVE_GROUP_CASH_SCOPE_UNKNOWN` | PASS |
| P1 | 处置、净款及账面值已结算，用途未知 | `CASH_DISPOSAL_REALIZED` | PASS |
| P1 | 只有公允价值增加，无处置或租赁支持 | `FAIR_VALUE_ONLY_OR_NO_OPERATING_SUPPORT` | PASS |
| R1 | 新材料减值与再融资进展同时出现 | `LOSS_CRYSTALLIZATION` | PASS |
| R1 | 未获豁免违约、加速偿还或一年期覆盖缺口 | `RISK_ESCALATION` | PASS |
| R1 | 继续依赖十二个月豁免 | `REFINANCING_OR_WAIVER_DEPENDENCY_PERSISTS` | PASS |
| R1 | 再融资仅承诺或计划、尚未完成 | `REFINANCING_OR_WAIVER_DEPENDENCY_PERSISTS` | PASS |
| R1 | 依赖解除或融资完成/具约束力，且期限覆盖改善 | `RISK_EASING_LOCAL_NOT_PROVED_AWAY` | PASS |

机械结果：`17 / 17 PASS`。

## Baseline 公平性与真实增量

公平 baseline 不是稻草人。它获得全部 FY2020、FY2021 普通事实，知道：

- reopening、入住率和报告亏损变化不等于经济恢复；
- OCF 减 reported capex 只是一期集团代理，不是 parent owner cash；
- OCF 外现金利息和 NCI 现金 claim 必须处理；
- maintenance capex 和 parent access 未闭合只能局部限制；
- 租赁、公允价值、处置、减值、契约和抵押具有不同经济含义。

结果结算采用 baseline 与 enhanced settlement fields 的并集，两臂获得同一份事实预算。Enhanced 的真实
增量只包括：固定八酒店的物业级 absorption vector、单轴不自动传播，以及对酒店经营、物业、现金、NCI、
维护资本和再融资的结果前分范围结算。

这些增量存在改变两臂处理的真实可能，例如：总体酒店收入改善但物业向量混合；集团现金为正但 parent
access 受阻；公允价值上升但租赁或处置没有支持；现金改善但继续依赖滚动契约豁免。不过，本审阅不预判
Enhanced 有效。若两臂最终达到相同投资或研究处理，或 Enhanced 只增加字段、结构、清晰度与规则语言，
效用必须记为零。

## 局部 UNKNOWN 与防御性写作

任一酒店缺少可比 ADR/RevPAR，只限制该物业的客户吸收结论；H2 组件不足只限制酒店 recurring economics；
处置用途未知只限制资本再配置；maintenance 或 parent access 未知只限制 normalized parent owner cash；
期限或契约口径不匹配只保留原有永久损失判断。上述 UNKNOWN 或 mismatch 均不得取消其他已结算 cell，
不得撤回当前酒店、物业、管理层、现金、永久损失、情景或方向性估值判断。

## 最小 outcome fact budget

下一步 authorization 只能允许独立 outcome custodian 从一份白名单发行人官方 FY2022 年报提取以下事实并
机械结算：

1. **H1**：固定八家酒店的 ownership/perimeter、开业/关闭/重开期间、occupancy、ADR、reported
   RevPAR；未报告 RevPAR 时，只能在同物业、本币内使用 `occupancy × ADR`；酒店或客房收入如有披露。
2. **H2**：hotel segment revenue/contribution；受控酒店 depreciation、finance、associate、tax；
   impairment/reversal、disposal、FV 及其他明确非经常项；按冻结公式派生 recurring EBIT 与 pre-D&A。
3. **P1**：澳门租赁收入、住宅与办公室出租率、物业分部收入与结果、投资物业公允价值；匹配处置的物业、
   账面值、净现金所得和用途，其中用途允许 `UNKNOWN`。
4. **C1**：综合 OCF、现金 PPE 购买、现金利息金额及其是否位于 OCF、NCI distributions/claim
   payments、资本承诺、maintenance adequacy 和 parent access；未披露的后两项保留局部 `UNKNOWN`。
5. **R1**：酒店减值或处置；银行债务总额及一至两年期限；可用/受限现金和有约束力的未动用额度；契约、
   waiver expiry/dependency、acceleration；再融资为完成/具约束力或仅承诺；抵押资产。

不得为了闭合某一局部字段扩大到旧派生报告、价格、回报、其他 outcome 材料或额外公司。

## 裁决与权限

最终裁决：`ACCEPT`。

该 ACCEPT 只确认 reviewed freeze commit `8652fca` 的结果前合同达到签署下一步 authorization 的条件。
当前权限为：

- `authorization_signing_next_step = ALLOWED`；
- `FY2022_outcome_content_access = SEALED_UNTIL_SEPARATE_AUTHORIZATION`；
- `outcome_fact_extraction = NOT_YET_AUTHORIZED`；
- `learning_and_utility = NONE`；
- `transfer_validation = NONE`；
- `method_freeze = NONE`；
- `Comparative = NONE`；
- `CJO = NONE`；
- `formal_valuation / BuyBand / report / investment_action = NONE`。

下一步 authorization 必须绑定 `8652fca`、独立 custodian、唯一 FY2022 官方年报白名单、上述最小 fact
budget、禁止来源及局部 mismatch 规则。签署后也只能开放事实提取与 cell settlement；两臂差异、学习效用
和任何后续权限仍须在结果结算后独立审阅。
