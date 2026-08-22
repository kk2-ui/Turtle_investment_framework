# Phase 10 经营预测与年报走步结算设计

> 状态：`V1_ENGINEERING_DIAGNOSTIC_FROZEN / V2_SUCCESSOR_CONTRACT_IMPLEMENTED`
> 日期：2026-08-16（Asia/Shanghai）
> 适用：每个已冻结的 `case-vintage`；首案 600340 也适用，但其
> `PURPOSEFUL_STRESS_CASE` 标签不变。

本文补充[Phase 10 回测路线图与模型行为契约](PHASE10_BACKTEST_ROADMAP.md)和[收益与选股评估契约](PHASE10_RETURN_SELECTION_EVALUATION.md)。它规定黄金报告对经营的判断如何在后续年报、半年报和公告中被逐份结算。v1 保留首个工程诊断的原始冻结语义；v2 将财务计量期间与事后阅读窗口显式分离，供后继 production case 使用。v2 契约存在不等于已经创建新的 600340 case、读取其后续正文或完成校准。

## 1. 结算的对象和边界

要回答的是：“冻结时，报告对公司经营、现金、资本结构和永久损失路径的理解，后来被官方披露怎样支持、反驳或保留为未知？”这与“股价后来涨跌多少？”是两道不同的问题。

- 只有冻结 `calibration_ledger.claims` 中的材料性项目可以结算。不得在看到年报后把平淡但有利的指标补进冻结报告，也不得删除原先的反方条件。
- 每个可量化预测必须对应预注册的 `prediction` 和 `observable_outcome`。当前 v1 已冻结指标、单位、计量口径、经济期间、允许来源和 `settlement_version_policy`；更细的 `forecast_spec` 可以作为报告附页，但不能绕过这些已执行字段。
- 当前 v1 无法严格表达的经营判断，必须在冻结时写为具体、可观察的 `UNKNOWN`，或降级为不进入预测误差统计的解释性文字。不能把“经营将改善”这类没有指标、期限和比较口径的句子事后称为预测。
- 后续披露只进入 `MODEL_FORECAST_ERROR` 和 `actual_outcomes.operating_observations`。它绝不回写报告的事实基础、估值输入、行动价或冻结动作。

## 2. 冻结时怎样预注册经营指标

### 2.1 每一条材料性预测的最小定义

一条 `PREDICTION` 除现有 `claim_id`、数值、运算符、单位、期限、阈值、反方和翻转条件外，应在冻结报告的经营预测附页逐项写明：

| 字段 | 必须明确的内容 | 目的 |
|---|---|---|
| `economic_driver` | 影响价值的因果环节，例如项目签约到结算回款、价格/销量/单位成本、营运资本、债务再融资或普通股现金上游 | 防止只预测会计科目却没有经济含义 |
| `metric_identity` | 规范指标名、流量/存量/比率、合并范围、归属口径、毛额/净额、币种和每股/绝对值 | 决定后来数值是否真的可比 |
| `measurement_rule` | 年报哪张表、哪项附注或哪份官方公告取数；若为派生指标，列出公式和每一个输入来源 | 让审阅者可以复算，而不是按叙事挑数 |
| `target_period` | 被预测的经济期间和预计首次可观察的披露期，例如 `FY2020`、`FY2020 annual report` | 将经营期间与年报发布时间分开 |
| `comparison_basis` | 与上一年、预算、阈值或绝对目标相比；增长率的分母、现金转化率的分子/分母均须固定 | 避免事后更换基数 |
| `scope_baseline` | 冻结时的合并实体、分部定义、会计准则和报告货币 | 识别合并范围和会计口径漂移 |
| `settlement_version_policy` | `INITIAL_DISCLOSURE` 或 `LATEST_OFFICIAL_AS_OF_EVALUATION`；首个工程阶段默认前者，同时展示后来更正 | 避免年报修订时静默改写预测误差 |

数值预测仍使用当前契约的 `AT_LEAST`、`AT_MOST` 或 `EQUALS`。若投资结论同时依赖方向和幅度，必须把它们拆为两个 claim，例如“收入不低于 X”与“经营现金转换率不低于 Y”；不得把多个失败可能性塞进一个漂亮的综合指标。

### 2.2 指标由经济机制决定，而非全公司统一模板

每个 case 至少选择能覆盖其核心价值桥、现金/债务约束和永久损失触发器的少数材料性指标。以下是选择地图，不是要求每家公司机械填满的评分表：

| 经济问题 | 合适的预注册指标示例 | 不能替代它的表面指标 |
|---|---|---|
| 销量、价格和单位经济性是否成立 | 销量、实现售价、单吨/单件现金成本、毛利率，及明确的分部范围 | 只看合并收入增长 |
| 项目从签约到可用现金是否闭合 | 项目结算/回款、应收或合同资产周转、经营现金流、受限现金变化 | 合同销售或预收款的单独增长 |
| 正常盈利是否转成普通股现金 | 税后经营现金、维护资本、利息、少数股东/上游限制后的 owner cash | 归母净利润或账面 NAV |
| 债务和融资是否破坏普通股路径 | 一年内到期债务、可用现金、受限比例、再融资/展期的官方状态、利息覆盖 | 现金余额或总债务的单项静态数值 |
| 永久损失的反方是否发生 | 已预注册的违约、契约、现金上游、项目回款或资产减值阈值 | 事后挑选的新闻标题 |

首案 600340 的冻结附页应至少覆盖项目销售/结算回款与资本占用、受限现金、短期债务覆盖、担保或关联方资金占用、普通股可得现金、融资阈值和永久损失触发器。每项只可使用截止日前已准入的一手披露，且不得预填 2020 年一季报、2020 年报或后续债务事件的结果。

### 2.3 `UNKNOWN` 是可结算的边界，不是零值预测

当公司没有披露可比的分部现金、担保风险、现金上游或维护资本，冻结报告必须登记 `UNKNOWN`，同时说明：

1. 这个未知会使哪个 `owner cash`、普通股价值、价格身份或动作不成立；
2. 哪个未来官方文件、附注或事件可能解决它；
3. 在解决前采取的估值/动作约束，例如主价格保持 `UNKNOWN`、不允许 `BUY`，或只给条件范围。

后续结算把未知显示为下列互斥状态之一：

| 状态 | 含义 | 对预测误差的处理 |
|---|---|---|
| `UNRESOLVED_AS_OF_SETTLEMENT` | 到结算日仍没有足以定义该指标的官方披露 | 不计入命中率或误差分母 |
| `PARTIALLY_RESOLVED` | 只解决了时间、范围或数值的一部分 | 不与完整预测混合；保留剩余缺口 |
| `RESOLVED_MATERIAL` | 后续披露已提供可用事实，且会影响当时的价值/动作 | 记录为“冻结时未知后来被解决”，不是模型命中 |
| `RESOLVED_IMMATERIAL` | 后续披露没有改变其预注册经济影响 | 同样不是模型命中；只支持未知管理的审阅 |

`UNKNOWN` 后来揭示坏消息也不能倒扣为“预测失误”；相反，若报告在未知存在时仍给出无条件正面价格或动作，这是 `REPORT_COVERAGE`/`REASONING` 问题。`UNKNOWN` 后来揭示好消息也不能把当时保守动作记成漏掉的模型收益。

## 3. 年报和公告如何按发布时间走步结算

### 3.1 可见信息时钟

走步的排序键是来源的真实 `published_at`，不是其经济期间 `data_as_of`。每个后续来源都同时保留这两个时间：一份在 cutoff 后发布、但覆盖 cutoff 前季度的定期报告，仍是冻结后才可见的结算来源，不能倒灌进冻结输入。

对每个 case，结算者先预注册结算日和所需来源类别，再按以下顺序运行：

1. **锁定起点**：读取冻结 case、冻结报告和其来源清单；确认 `report_status`。此时不改变 claim、数值、阈值、单位或来源版本。
2. **建立发布时间线**：枚举 cutoff 后至 `settlement_as_of` 的官方年报、半年报、季报、交易所公告和公司行动；记录 `published_at`、`data_as_of`、版本和是否修订。枚举应完整，筛选理由应可读。
3. **逐份打开**：严格按 `published_at` 从早到晚读取。一份来源只结算其已预注册的相关 claim；未覆盖某指标时记录 `NOT_DISCLOSED_IN_THIS_RELEASE`，不能借用下一年报的值填回本步。
4. **记录当步观察**：每个观察都写入 claim id、指标、值、单位、经济期间、发布时间、来源版本、可比状态和引用。达到预测期后，按冻结的比较规则标记阈值是否触发。
5. **发布后版本处理**：若后续公告修订先前数字，追加新观察和修订原因；保留原始披露，不覆盖旧值。最终读者视图同时展示原始披露、修订披露和它们的差异。
6. **到期收口**：到 `settlement_as_of`，每条 claim 为 `CALCULATED`、`PARTIAL`、`NOT_CALCULABLE` 或仍为对应的 UNKNOWN 状态。没有可比且准入的官方观察时，不能为便于汇总而估算一个 actual。

一份披露只能在它发表后影响读者可见的“后来发生了什么”。因此，累计三年结算不是先读三年年报再写一张总结，而是保存每一个发表时点的可观察结论序列。

### 3.2 年报重述和版本替代

后续年报有两种不同角色，必须区分：

- **新的经营观察**：例如 FY2021 年报披露 FY2021 的收入和现金流；它按 FY2022 的真实发布时间进入走步序列。
- **对旧期间的修订**：例如 FY2020 年报修订已发布的 FY2019 数字；它是新的披露事件，不是回到 FY2019 静默更换历史。

每条预测在冻结时选择一个 `settlement_version_policy`：

- `INITIAL_DISCLOSURE`：用目标期间第一次可准入的官方披露评估当时可见的经营结果。首轮工程 case 采用这一口径，最符合“按发布时间走步”。
- `LATEST_OFFICIAL_AS_OF_EVALUATION`：用结算日之前的最新官方更正值评估经济数值；必须同时保留并展示首次披露值与差异。

两种口径可以并排报告以研究会计质量和数据稳定性，但不能混成一个误差数字，也不能在出现更有利版本后替换已展示的历史结果。修订本身应标记 `RESTATEMENT_OR_RECLASSIFICATION`，并按其影响归入 `DATA_COVERAGE`、`ACQUISITION_MODULE` 或报告期的会计可比性说明；除非冻结报告依赖了错误版本，否则它不是 writer 的事后过失。

### 3.3 当前可执行字段

冻结 case 的每个 `observable_outcome` 必须携带 `settlement_version_policy`。结算记录则必须：

- 将每个冻结 claim 写入 `model_forecast_error.claim_settlements`；预测使用
  `CALCULATED`、`PARTIAL` 或 `NOT_CALCULABLE`，未知使用明确的解决状态；不允许遗漏后仍标为 `REVIEWABLE`；
- 用 `operating_source_timeline` 声明已枚举的经营来源及其完整性，并让观察引用该时间线中的官方来源；
- 为每个经营观察写入 `comparability_status`，只有 `COMPARABLE` 或已预注册换算规则的观察可以成为预测误差的 actual；
- `CONVERTIBLE_WITH_PREREGISTERED_RULE` 在当前 v1 只支持可复算的固定单位换算：冻结时必须写入 `conversion_rule`（原始单位、目标单位和正乘数），结算时必须保留原始值并复算换算值。动态汇率、范围变更或叙事性换算仍是 `NOT_COMPARABLE`，直到有独立的结构化规则；
- 每个与冻结定义匹配且可比的观察都必须登记到该 claim 的结算中。预测不能在已有可比 actual 时标为 `NOT_CALCULABLE` 或 `PARTIAL`，未知也不能在已有可比 actual 时继续标为 `UNRESOLVED_AS_OF_SETTLEMENT`；
- 由 `INITIAL_DISCLOSURE` 强制选用同一 claim、指标、口径和经济期间的首次可见可比观察；选择后续重述会被 validator 拒绝。`LATEST_OFFICIAL_AS_OF_EVALUATION` 则在已枚举时间线中选择结算日以前的最后可见观察，已枚举的首次披露不会被覆盖。

所有 `published_at`、冻结 cutoff 和结算时点按完整时间戳比较。只有日期的资料在 cutoff 当日、或在同一 claim 的首次/最新披露选择中无法证明版本先后时，会使该 case 保持 `INCOMPLETE`，而不是被当作已知的盘中时刻。

### 3.4 v2 successor contract

v1 的 `period_start` / `period_end` 在首个工程冻结中被错误用于
2020-04-28 至 2021-04-27 的公告阅读窗口，导致真实 FY2020 年报的
`data_as_of=2020-12-31` 无法成为可比观察。该 v1 工件保持冻结，不作
事后迁移。

后继 production case 使用 `historical-backtest-case.v2` 与
`historical-backtest-settlement.v2`：

- 每个 frozen `observable_outcome.measurement_period` 记录 `kind`
  (`REPORTING_PERIOD` 或 `EVENT_WINDOW`)、`start` 和 `end`；
- `observation_window.opens_after` 与 `closes_at` 记录后续官方披露可被
  阅读的完整时间范围；
- 结算 observation 复述 `measurement_period`，而不复述阅读窗口；
- `EVENT_WINDOW` observation 还须登记实际 `event_period`，并完全落在
  冻结 measurement period 内；
- v2 的每条 `actual_source` 声明 `content_access`。只有
  `BODY_READ` 来源可支持 actual observation，元数据库存不能作为经营事实；
- 对 `REPORTING_PERIOD`，年报/中报 `data_as_of` 必须等于 measurement
  period 的 `end`；对 `EVENT_WINDOW`，证据来源仍须在阅读窗口内，且其
  event period 必须被正文支持，但不强制年报/中报 `data_as_of` 等于事件日。

价格/投资目的的 v2 settlement 仍会拒绝阅读窗口结束晚于 `settlement_as_of` 的 claim，并按
`INITIAL_DISCLOSURE` 或 `LATEST_OFFICIAL_AS_OF_EVALUATION` 仅在可比观察中
选择版本。`COMPANY_JUDGMENT_ONLY` 则可在同一 immutable case 的早期追加结算中保留这类未来
claim 为无 observation 的 `PARTIAL`；它必须携带连续的 `settlement_series_id`、序号和前序 ID，
series 审阅会拒绝改写已经结算的 claim。它不能让旧 v1 质量失败工件变为 production case。

## 4. 口径漂移、缺失和不可比

经营结算先判断“是否是同一指标”，再计算方向、阈值或误差。可自动换算的数量级（元到万元、绝对值到每股）只有在冻结时写明公式和股份口径时才可换算，并保留原始值。以下情况不能靠叙事或估算强行连续：

| 可比状态 | 典型原因 | 结算要求 |
|---|---|---|
| `COMPARABLE` | 相同口径、范围、期间和单位 | 可按冻结预测计算误差/阈值 |
| `CONVERTIBLE_WITH_PREREGISTERED_RULE` | 仅为已登记的单位或币种换算 | 展示原始值、换算规则和换算后值 |
| `PERIOD_MISMATCH` | 财年变更、报告期长短不同或目标期间尚未结束 | 不计算原预测误差；保留观察和缺口 |
| `SCOPE_OR_ACCOUNTING_DRIFT` | 合并范围、分部定义、收入总额/净额、会计政策或归属口径改变 | 状态为 `NOT_COMPARABLE`，并说明经济影响 |
| `NOT_DISCLOSED` | 后续报告不再披露被冻结所需的明细 | 不以零、上一期值或分析师估计补齐 |
| `RESTATEMENT_OR_RECLASSIFICATION` | 官方后来更正或重分类旧数 | 追加版本化观察，按预注册版本政策展示 |

若口径漂移本身使原投资判断无法检验，读者应看到它是材料性信息缺失，而不是一条被压缩进“预测不准”的残差。只有冻结时已明确的可比桥接公式可以用于模型误差；走步后为了得到一个答案临时发明的桥接，只能作为下一轮研究假设，不能回填本 case 的分数。

## 5. 三本账给读者的输出

每个已冻结 case 至少输出以下三个并排区块，不生成总分或用一个区块抵消另一个区块：

| 账本 | 读者要回答的问题 | 必须展示的核心内容 | 不得据此推导 |
|---|---|---|---|
| `REPORT_COVERAGE` | 冻结时的报告有没有足够证据、保留未知并闭合价值桥？ | 冻结报告状态、材料性 claim、来源版本、支持/缺口、UNKNOWN 的经济约束和独立审阅结果 | 后来的股价或年报反过来证明冻结时写得对 |
| `MODEL_FORECAST_ERROR` | 冻结的经营判断后来怎样发展？ | 每条 claim 的冻结预测/UNKNOWN、指标定义、目标期间、逐次发布时间线、实际值、可比状态、阈值结果、版本政策和后续官方来源 | 将 UNKNOWN 记为命中/失误，或用不可比数值计算精确误差 |
| `INVESTMENT_RETURN_OUTCOME` | 按当时已注册的动作和执行规则，股东实际拿到了什么？ | action、成交/未成交、原始价格、公司行动、净现金流、费用税费、基准、回撤、状态和缺口 | 以经营正确取代可执行回报，或用回报掩盖永续风险 |

面向读者的单条经营结算行应采用下列顺序，而不是只报“预测正确率”：

```text
冻结主张与经济影响
  -> 冻结预测或 UNKNOWN，以及指标/单位/期间/口径
  -> 第一份可见后续披露（发布时间、经济期间、版本、实际值）
  -> 后续修订或下一期观察（如有）
  -> 可比状态、阈值/翻转条件状态和未解决缺口
  -> 这影响 REPORT_COVERAGE、MODEL_FORECAST_ERROR 或 INVESTMENT_OUTCOME 的哪一栏
```

案例摘要必须显式写出三句独立结论：冻结报告是否可审、经营预测可结算的比例及关键反例、投资结果是否可复算。示例：`报告覆盖 PARTIAL；7 条经营判断中 4 条可比结算、2 条仍 UNKNOWN、1 条口径漂移；投资结果 INCOMPLETE，因公司行动未闭合。` 这不是总评，也不能被浓缩为“回测通过”。

## 6. 用这些结算结果改进黄金报告

跨 case 复盘时，先按失败根因归类，再决定是否允许改变报告规范：

| 观察到的问题 | 根因 | 可执行改进 | 不能做的事 |
|---|---|---|---|
| 未来年报多次显示冻结时遗漏的材料性资料 | `DATA_COVERAGE` 或 `ACQUISITION_MODULE` | 补全可复用公告枚举、来源版本准入或必读附注 | 只降低覆盖门或用叙事弥补 |
| 指标有来源却没有单位、期间或可比口径 | `REASONING` 或 `WRITING` | 把 `forecast_spec` 的定义纳入报告质量门 | 事后按最有利口径重算 |
| 已注册、可比的经营阈值持续失效 | `MODEL` | 在设计集提出机制/阈值修正，并以留出 case 验证 | 由单一案例直接修改 `q`、回报率或买点 |
| 经营判断成立但收益无法执行 | `INVESTMENT_RETURN_OUTCOME` 的执行/公司行动缺口 | 完善结算账本、动作和可交易性规则 | 把经营正确宣称为选股成功 |

只有当 `REPORT_COVERAGE` 不退化、可比经营预测在留出集改善、且涉及买点或选股时收益账也完成相应验证，才允许升级生产报告规范。首案只验证这条链路能否诚实运行；它不提供任何参数校准或成功率结论。
