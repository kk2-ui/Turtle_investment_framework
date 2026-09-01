# HK00696 FY2026 独立结果前审阅

> 审阅日期：`2026-08-28`
>
> 审阅角色：独立结果前 reviewer；未参与 30/31 的编写或修订
>
> 审阅结论：`ACCEPT`
>
> reviewed freeze commit：`250b476`。本审阅绑定该提交中的 30/31 内容；32 仅记录独立审阅，不追溯改变已经冻结的结果前判断。

## Reviewed files

- `30_FROZEN_FUTURE_HOLDOUT_HK00696_FY2026.json`
- `31_HK00696_PREOUTCOME_INVESTOR_JUDGMENT.md`

审阅没有读取 FY2026 中报、FY2026 完整年报、证券价格、回报、旧派生报告或 `_sources`，也没有重新读取 30/31 已冻结证据预算之外的公司材料。

## 审阅问题

本审阅只判断以下实质问题，不审格式、字段数量或文档长度：

1. selection 是否在 FY2026 完整结果出现前真实冻结，且没有按结果选择公司或 cell；
2. 三个 outcome cells 的 first-match 是否能在责任边界内唯一处理真实冲突、局部未知与不合格证据；
3. 正向交易量、报表现金或流动性是否被错误跨轴外推为定价、owner cash 或永久损失改善；
4. 31 是否给出明确、可反驳、对投资有用的当前判断，而不是用 `UNKNOWN`、口径或 first-match 代替判断。

## 首轮 RETURN

首轮审阅给出 `RETURN（MODEL / REASONING）`，仅发现两项足以改变投资判断的缺口：

### 1. 客户与 monetization 向量被过度压缩

原合同把 ETD 与 settlement 两条数量轴压成一个 `customer_volume`。因此，ETD 量增但 settlement 交易下降时没有确定结算；platform monetization 与 settlement monetization 一正一负时，前置的 `ANY ... DILUTED` 又会遮蔽本应表达服务分化的 `MIXED`。

经济影响是可能把两类服务不同的客户使用和变现趋势写成一个方向，错误上调或下调网络位置、正常盈利与管理层商业化评价。

### 2. pass-through 与 airport UNKNOWN 可以被正向现金分类越过

原 `OPERATING_ECONOMICS_AND_CASH_IMPROVED` 没有要求 `operating_cash_ex_pass_through=POSITIVE`，并以 `airport_project... IS_NOT_DETERIORATED` 代替显式正向状态。这样会让 reported OCF 中的客户结算代收代付，或尚未观察的机场项目经济，被误写成经营经济和现金改善。

经济影响直接落在 owner cash、平台单位经济、估值方向和管理层执行评价。

## 已完成的最小修复

修订没有增加新 gate，也没有要求更多公司材料：

- 将客户数量拆为 `etd_volume` 与 `settlement_volume`；
- 新增由已观察冲突确定的 `service_vector_conflict`，让服务量或 monetization 一正一负时先结算 `MIXED_SERVICE_VECTORS`；
- 只有两条服务数量均非负、至少一条增长、两项 monetization 均保持或改善且无不利 pricing event，才结算客户与定价吸收；
- 固定 cash bridge：reported OCF 减带符号的客户结算 pass-through 得到 `operating_cash_ex_pass_through`，再减系统长期资产现金投入和 NCI distributions 得到 `post_system_capex_and_nci_proxy`；
- 上游 ex-pass-through 为 `UNKNOWN` 时，下游 proxy 必须为 `UNKNOWN`；矛盾的上下游状态不可接纳；
- 经营经济与现金改善必须同时满足 ex-pass-through 为正、post-system proxy 为正、maintenance 充分，且 airport project economics and collection 明确为 `IMPROVED` 或 `MAINTAINED`；
- 31 同步把 FY2025 现金判断改为“reported OCF 的未调和算术改善真实，但冻结定义下的 ex-pass-through 与下游 proxy 尚为 UNKNOWN”，没有把局部未知扩展成整家公司拒绝判断。

## 六项机械重放

### 1. ETD 量增、settlement 交易下降

结果：`service_vector_conflict=TRUE`，优先结算 `MIXED_SERVICE_VECTORS`。不得进入 customer absorption，也不得只依据其中一条服务下调整家公司。

### 2. platform 与 settlement monetization 一正一负

结果：`MIXED_SERVICE_VECTORS`。如果另有必要轴未知，冲突分类只陈述已经观察到的服务分化，未知轴仍保持局部 `UNKNOWN`；它不把未知轴假定为已知方向。

### 3. platform economics 改善、post-system cash 为正，但 ex-pass-through cash 非正或未知

结果：不得结算经营经济与现金改善。ex-pass-through 为 `UNKNOWN` 会机械强制下游 proxy 为 `UNKNOWN`；ex-pass-through 非正却声称下游为正属于公式矛盾，不可接纳。

### 4. airport project axis 为 UNKNOWN

结果：不得结算 `OPERATING_ECONOMICS_AND_CASH_IMPROVED`。该分类只接受 airport project 明确 `IMPROVED` 或 `MAINTAINED`；否则保留相应局部未知或已观察到的其他局部方向。

### 5. reported cash 含 customer reserve

结果：客户备付金及其他受限资金必须从可用流动性和 owner cash 中剔除，common-equity access 保持局部未知；大额账面现金不能跨轴证明普通股东现金。

### 6. liquidity covered，资本进入 off-core，但尚无减值

结果：`CAPITAL_ALLOCATION_ADVERSE_LOCAL`，不是 `PERMANENT_LOSS_RISK_UP`。只有真实期限缺口或不可逆平台、客户、应收或资产损失载体才能上调永久损失。

## 新增反例复验

修订后的四个新增反例均通过：

1. 两条服务数量非负且至少一条增长、两项 monetization 都下降，只能结算 `VOLUME_WITH_MONETIZATION_DILUTION`；
2. ETD 上升、settlement 下降，只能先结算 `MIXED_SERVICE_VECTORS`；
3. 两项 monetization 一正一负，只能先结算 `MIXED_SERVICE_VECTORS`；
4. ex-pass-through 未知却由调用方提供正的 post-system proxy 时拒绝矛盾输入；airport project 未知也不能被解释为“没有恶化”。

原有折旧、客户备付金和 off-core allocation 反例仍保持：折旧下降不替代平台经济，客户资金不属于 owner cash，未减值的非核心配置不自动成为永久损失。

## 投资者效用与非防御性裁决

31 已形成清楚的结果前判断：

- 客户与交易网络位置强，但核心平台 monetization 仍有压力；
- reported 利润和现金改善存在，但在 pass-through、项目回款、maintenance 与普通股东可达性关闭前，不把它冒充 normalized owner cash；
- 近期债务压力低，永久损失主要来自平台失效、客户或监管损失，以及可能恶化的资本配置，而不是由大额账面现金一票消除。

每项判断均给出机制、最强反方、三种情景、方向性估值处理和可推翻事实。`UNKNOWN`、口径桥和 first-match 只限制依赖它们的局部主张，没有取代企业判断。管理层的系统运营与客户交付能力得到正向评价，但部署、项目验收或专利数量没有被等同于资本回报。

因此最终裁决为 `ACCEPT`。

## 状态与权限

- outcome：`SEALED`
- FY2026 outcome reader：`NONE`
- current feedback credit：`NONE`
- learning authorization：`NONE`
- transfer candidate / transfer validated：`NONE / NONE`
- method freeze：`NONE`
- Comparative / CJO / valuation / BuyBand：`NONE`
- report publication / investment action：`NONE / NONE`

本审阅只接纳结果前冻结判断与合同质量。它不计作真实反馈，不证明方法有效，也不授予任何投资权限。
