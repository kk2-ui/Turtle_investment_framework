# Turtle PIT 企业判断训练：原语与准入模型

> 状态：`DRAFT / ARCHITECTURE_REVIEW_REQUIRED / EXTERNAL_CANDIDATE_ACQUISITION_PAUSED`
>
> 日期：2026-08-24
>
> 目的：在继续筛选真实历史样本前，统一定义训练对象、决策作用域、竞争场域、计量边界与同行反事实。本文通过后，才将其收敛为新的 admission version；不得再对 V4 逐个行业补例外。

## 1. 为什么暂停：当前问题不是资料，也不是模型

此前的 V4 把五件不同的事压进了 `common_boundary`、`industry_id` 和四个完全相同的 market 字符串：

1. 上市公司合并报表的会计边界；
2. 管理层决策真正影响的经营范围；
3. 客户与竞争发生的经济市场；
4. 可用于剔除共同冲击的同行集合；
5. 公开披露恰好能观察到的指标边界。

这会产生两类同样危险的错误：

- 将一个区域工厂、子公司项目或单品行动，偷换成整个发行人的 D3/D4；
- 因家电不是同一省、出口商不是同一国内市场而误拒真实竞争对手，或者用“国内市场”四字把不相关公司塞进同行中位数。

资料多并不能修复这个问题。先定义经济对象与允许的桥接关系，公开资料才知道该采什么、缺什么和何时应当 `UNKNOWN`。

## 2. 北星：训练的是判断方法，不是事件分类器

训练闭环仍然是：

```text
历史 PIT 状态
  → 决策与可行替代方案
  → 可证伪的竞争机制 H-A / H-B
  → 经营贡献与保守 owner cash 的独立结算
  → 条件化 learning
  → 不同公司的冻结前应用
  → 方法冻结
  → R-103 独立留出
  → 黄金报告研究议程
```

它不训练“见到关厂/提价/扩产公告就预测利润”的模式。一个 episode 的学习只能是带作用域和失效条件的判断约束，例如：

> 当某类网络重构在其适用竞争场内保持客户交付，且成本改善没有被重组现金、资本开支或营运资本释放伪造时，才允许把 D3 改善作为 D4 待验证信号；D3 本身不是现金结论。

## 3. 七个不可合并的经济原语

| 原语 | 回答的问题 | 不能替代它的东西 |
|---|---|---|
| `ACCOUNTING_PERIMETER` | 哪个法律/合并报表实体产生 D3、D4、D5？ | 产品名、集团叙事、总部所在地。 |
| `DECISION_SCOPE` | 谁作出什么自主、增量、可逆/不可逆的取舍？ | 项目计划、设计产能、管理层预测。 |
| `ECONOMIC_CARRIER` | 决策实际改变的产线、网络、分部、产品、渠道或资产组合是什么？ | 发行人总收入或总 OCF。 |
| `COMPETITIVE_ARENA` | 客户、竞争、价格、成本或监管在哪个经济场域相互作用？ | 行业代码、同省/同国文字。 |
| `MEASUREMENT_SURFACE` | 哪个可重复的官方字段能看到各箭头？ | 更方便但不同边界的财务指标。 |
| `COUNTERFACTUAL_PANEL` | 谁受到同一关键外部冲击，可帮助辨认共同变化？ | 任意同业公司、事后挑出的赢家。 |
| `CAUSAL_PANEL_ROLE` | 该成员是未受目标决策影响的环境 comparator、均衡响应 witness，还是反证者？ | 把直接受目标行动影响的竞争对手当作未处理 control。 |
| `TIME_PARTITION` | 截止时研究者知道什么，哪一段才是后续结果？ | 披露日期晚于 cutoff 就自动成为有效 outcome。 |

每个 episode 必须先画出这些对象及其关系。任何一项缺失都不是“以后补个字段”，而是明确写出本案只能训练哪条箭头、不能训练哪条箭头。

```text
Decision scope ──作用于──> Economic carrier
      │                         │
      │                         └──在 Competitive arena 中面对客户/成本/竞争回应
      │                                              │
      └────由 Measurement surface 观察────> D3、D4、D5

Counterfactual panel 只用于辨认 arena 的共同冲击，不能代替上述传导或制造因果归属；其中直接竞争者可能会受到目标决策的均衡外溢，因而只能作机制 witness，未必能进入相对基线。
```

## 4. 作用域桥：允许什么，禁止什么

“必须同一边界”应改为“必须有已声明、可验证的作用域桥”，而不是要求所有决策都是整家公司行动。

| 决策范围 | D3/D4 计量范围 | 能否进入选择训练 | 必须额外冻结的桥 |
|---|---|---|---|
| 发行人整体经营政策 | 发行人合并口径 | 可以 | 决策权、实施范围、全公司现金/资本影响。 |
| 业务分部/网络 | 同一分部/网络口径 | 可以 | 分部 P&L、现金/营运资本/capex 或保守的不可观测声明。 |
| 发行人整体政策 | 分部口径 | 可以，但结论仅限该分部 | 政策如何作用于该分部、其他分部是否成为反向来源。 |
| 局部单元行动 | 发行人合并口径 | 仅在行动被定义为发行人层资源配置/网络政策，且有量化 aggregation bridge 时可训练发行人层机制 | 单元覆盖率、其他 material 业务/交易排除、行动现金与 D3/D4 的边界；不能宣称单元项目 ROI。 |
| 局部单元行动 | 无匹配单元计量，也无 aggregation bridge | 不可作选择训练 | 可保留为 `TEACHING_ONLY` 或 `QUESTION_ONLY`。 |

`aggregation bridge` 不是“该业务看起来占大头”，也不要求研究者证明世界上不存在其他变化。它只允许三种有类型桥接：

| bridge 类型 | 允许关系 | 必须有的 cutoff 前事实 | 结论上限 |
|---|---|---|---|
| `IDENTITY` | 决策载体与 D3/D4 计量面完全相同 | 并表/经济权利、字段定义、现金归属。 | 该载体的经营与现金机制。 |
| `SEGMENT_MATCH` | 载体与持续披露分部相同 | 分部收入/成本/资本或明确 D4 不可观察、分部口径连续性。 | 分部机制；D4 缺失时不得 selection learning。 |
| `QUANTIFIED_ISSUER_AGGREGATION` | 发行人政策作用于若干载体，而 D3/D4 在发行人层计量 | 决策授权、受影响载体、量化覆盖/排除、已披露 material-break register、行动现金和其它可定位重大业务变化。 | 发行人层政策机制，不是单厂/单项目 ROI。 |

没有上述 bridge 时，局部行动不能借集团 D3/D4 进入选择训练。`material-break register` 记录能定位的已披露重大变化；它不能被偷换为“没有其他变化”的负事实证明。

## 5. 竞争场域：由机制决定，不由地理字符串决定

`COMPETITIVE_ARENA` 不是 `industry_id` 的别名，也不等于所有成员地理描述完全一致。它应包含：

```text
competitive_arena_id
market_scope_type = NATIONAL | REGIONAL | EXPORT | SEGMENT | MULTI_REGION_PORTFOLIO
product_or_service_scope
customer_choice_or_cost_driver
mechanism_required_overlap_dimensions
```

`market_scope_type` 只描述竞争场的形态，不能自行决定所有字段必须相同。机制契约应为每个 overlap 维度声明 `REQUIRED_EQUAL`、`REQUIRED_OVERLAP`、`REQUIRED_EXPOSURE` 或 `NOT_REQUIRED`；target 和每个 peer 再以 cutoff 前来源逐项证明。不同 topology 的要求不同：

| 竞争场域与机制 | 必需重叠 | 不应强制相同 |
|---|---|---|
| 全国性家电定价、渠道或产品竞争 | 品类/客户选择、全国竞争暴露、相关需求或投入冲击 | 每省销售占比、工厂所在地、渠道组织的逐字描述。 |
| 区域水泥的产能、运距或本地价格机制 | 同一或实质重叠的运输半径、当地需求/供给/监管冲击 | 总部所在地、全国行业名称。 |
| 出口制造 | 机制决定：汇率/原料机制要求相关风险暴露；特定关税或渠道机制才要求目的地/渠道 overlap | 国内销售地域或“出口”标签。 |
| B2B 细分产品 | 相同客户任务、认证/切换成本、产品/技术替代关系 | 宽泛一级行业代码。 |
| 成本重构 | 同一成本驱动及其传导暴露；若机制依赖需求竞争，再补客户/产品 overlap | 与成本驱动无关的地理或客户文字。 |

因此允许“全国性家电竞争场”的同行有不同区域网络，也允许“区域水泥场”只选实际竞争区域相交的公司。`MULTI_REGION_PORTFOLIO` 则必须预先列出行动相关子场域及非结果拟合的暴露权重/主导场域；权重只能来自 `DISCLOSED_REVENUE`、`DISCLOSED_CAPACITY`、`DISCLOSED_ASSET`、`SOURCE_SUPPORTED_DOMINANT_ARENA` 或 `UNKNOWN`。没有同口径权重时，禁止加权 relative baseline；只能收窄到单一可证实 arena、降为 witness，或 `TEACHING_ONLY`。只写“多区域”无效。禁止的只是：同业、同地、或“国内市场”字样本身自动被当成共同冲击。

`COMPETITIVE_ARENA` 与相对 baseline 的 `EXTERNAL_DRIVER_REFERENCE` 必须分开。前者定义 target 行动真正改变的客户、成本或竞争场；后者定义 target 与 comparator 共同面对、但不由 target 行动本身造成的外部驱动。两者可重合，但区域水泥的本地直接 rival 常只属于前者：它会受 target 关产/扩产外溢，因而是 witness；场域外但共同面对燃料或环保冲击、且有 bounded noninterference 证据的公司才可成为 comparator。不得以“同一成本冲击”把它们伪装成同一局部市场，也不得以“同一市场”忽略行动外溢。

### 5.1 同行不是同一种因果对象

每名 panel 成员在 outcome 前只能有一个被冻结的角色：

| causal role | 允许用途 | 必需约束 |
|---|---|---|
| `EXTERNAL_SHOCK_COMPARATOR` | 进入 D3/D4 相对基线 | 与 target 共享预声明外部驱动；在冻结的有限 source package 内 `PARALLEL_ACTION=BOUNDED_ABSENT` 且 `SPILLOVER=BOUNDED_NONINTERFERENCE`。 |
| `EQUILIBRIUM_RESPONSE_WITNESS` | 观察竞争、价格、供给或客户回应；不能进入相对基线 | 可以直接受目标行动影响，必须将其视为机制证据而非未处理 control。 |
| `FALSIFIER` | 检验 H-A/H-B 的必要条件与边界；不能进入相对基线 | 与命题有意只改变一个关键条件，且不宣称其代表共同环境。 |

`PARALLEL_ACTION` 只能取 `DISCLOSED`、`BOUNDED_ABSENT` 或 `UNKNOWN`；`SPILLOVER` 只能取 `MATERIAL_RISK`、`BOUNDED_NONINTERFERENCE` 或 `UNKNOWN`。这不是要求研究者证明世界上没有行动或外溢：`BOUNDED_*` 只对冻结的、预声明的静态来源包和机制范围成立。任一状态为 `UNKNOWN` 或有风险时，该成员降为 witness/falsifier，不能强行搜索更多公告来凑 control。区域水泥减产可能改变邻近竞争者的价格和利用率，因此那些竞争者通常是 `EQUILIBRIUM_RESPONSE_WITNESS`，不是相对 owner-cash 中位数的 control。全国性家电同行若在该有界包内无同类材料行动且共同面对全国需求/投入冲击，才可能是 `EXTERNAL_SHOCK_COMPARATOR`。不能把三种角色混进同一个 median。

同行的职责是对共同环境作约束，而不是估计严格因果处理效应：

```text
发行人绝对 D3 / D4 结果
  AND
相对于固定、机制可比 peers 的变化
  AND
原命题的作用域桥没有被结果期事实打破
```

任一项缺失时，结果是 `NOT_DIAGNOSTIC` 或 `MIXED`，不是靠更宽泛的“同行”补成方向性 learning。

### 5.2 Stage-0 先证明可行性，不偷带行动答案

Stage-0 必须发生在行动进入研究者信息集之前，因此只能冻结 `arena_family`、控制权、潜在经营载体、三期候选 D2/成本字段身份和五期 D3/D4 字段身份。它不要求已经证明行动特定 D2 非机械性、最终 common driver、最终 peer role 或最终 overlap；否则会逼研究者先找到醒目公告，再倒补 cohort。

行动可见后才形成 `ACTION_SCOPE` 与 `ACTION_SPECIFIC_ARENA_AND_PANEL`：行动、载体、bridge、mechanism-required overlaps、共同驱动假设、peer causal roles、最终排除和 source package 必须在 research cutoff 前同时冻结。共同驱动的场域背景可来自版本化公共原件（监管、统计、海关等）；每家公司的暴露仍须有 cutoff 前证据。公司年报或行业标签不能独自证明共同驱动。

## 6. 不再强制一种五层故事

五层时钟是观察层，而不是所有商业决策都必须经过的单一路径。每个 episode 先选择 topology；D1 是已实施决策，D3 与 D4 是选择学习的两个独立终点，其他层按机制决定为 central voter、diagnostic 或 `UNKNOWN`。

| topology | 中心链 | D2 的身份 | 当前准入版本 |
|---|---|---|---|
| `CUSTOMER_RESPONSE` | D1 → 客户吸收 → D3 → D4 | central voter | 可进入未来 V5。 |
| `COST_RESTRUCTURING` | D1 → 成本/利用率/交付 → D3 → D4 | 仅在需求传导是中心时投票，否则 diagnostic/non-voter | 可进入未来 V5。 |
| `PRODUCT_OR_INNOVATION` | D1 → 采用/服务负荷 → 单位经济 → D4 | central voter | 需独立的产品/反馈合约。 |
| `CAPITAL_ALLOCATION_OR_INTEGRATION` | D1 → 完成/整合/资本占用 → D3/D4 → D5 | 不一定适用 | 不可借用经营竞争契约；另立版本。 |

这意味着“没有 D2”既不自动判企业无竞争力，也不允许 D3/D4 自动证明客户接受。它只要求系统说清：本案到底在训练客户机制、成本机制、产品机制还是资本配置机制。

### 6.1 D3/D4 是两个独立的 measurement contract

每一个中心终点都必须冻结独立 `metric_identity`：

```text
metric_id
accounting_perimeter / segment_or_carrier
currency_and_unit
period_basis
gross_or_net_definition
formula_and_raw_fields
restatement_or_reclassification_policy
allowed_scope_bridge
source_document_class_and_locator
```

D3 与 D4 可以服务同一机制，但不得共用“通过权”：D3 改善不能验证 D4，D4 `UNKNOWN` 不能由 D3 替代。D4 还须单独冻结 OCF、全部长期资产现金、现金营运资本（应收、预付、存货减应付与合同负债/预收）、行动相关现金的唯一处理和重述政策；同一重组现金不得双扣或漏扣。`SELECTION_ADMITTED` 是 outcome 前的准入身份；`A_ONLY`、`B_ONLY`、`MIXED`、`UNKNOWN`、`NOT_DIAGNOSTIC` 与 `BOUNDARY_CAPTURED` 是 outcome 后结算，二者不能混成一个状态或文字结论。

## 7. 时间和结果：真正的 PIT 分割

每个样本必须冻结七个时间身份，而非只写一个 cutoff：

1. `cohort_eligibility_as_of`：独立于任何 focal action 的 Stage-0 可行性 cohort 形成时点；
2. `action_effective_window`：决策实际开始影响经营载体的实施/rollout 区间；公告日不自动等于此日期；
3. `decision_observable_at`：研究者从官方来源第一次足以区分已实施、可自由选择或被强制变化的时间；
4. `research_cutoff_at`：H-A/H-B、bridge、指标、阈值、panel 和 outcome contract 被冻结的时间；
5. `metric_economic_period`：每项 D3/D4/D5 指标的实际起止期与最小受决策影响暴露；
6. `source_available_at`：该指标原件对结果 custodian 可用的时间、初始/重述身份和时间精度（`INTRADAY` 或 `DATE_ONLY`）；
7. `outcome_window_id`：target/peer 共同使用的主结果窗口，或预先冻结的 fiscal-calendar bridge。

最小不变量是：

```text
cohort_eligibility_as_of < action_effective_window.start
cohort_eligibility_as_of < decision_observable_at
action_effective_window.start <= research_cutoff_at
decision_observable_at <= research_cutoff_at
all pre-outcome evidence.source_available_at <= research_cutoff_at
all primary-outcome raw sources.source_available_at > research_cutoff_at
primary metric_economic_period.start > action_effective_window.start
```

历史原件只有发布日期时可使用 `DATE_ONLY`：它只在发布日期严格早于 cutoff 日期时可作 cutoff 前证据；同日资料一律不用于该 cutoff 的 pre-outcome 依据。只有可审计的发布时间时才可用 `INTRADAY` 比较。

行动发生后的同一财年可以提供事实背景，但不能无区分地拿整个年度当结果。若决策在年末实施，首个完整后续年度才可能承担 D3/D4 的主要结算；跨越行动的期间只能预先标为 `EARLY_ARROW_NON_VOTER`。披露日晚于 cutoff 也不够：若经济期间没有达到预先冻结的最小暴露，不能作为主 D3/D4 outcome。

PIT source firewall 是执行层：它保障研究者未见结果；它不能替代经济上正确的 `outcome_window` 定义。

## 8. 材料性、噪声与结论层级

材料性有三种不同含义，必须分开：

1. `DECISION_MATERIALITY`：决策是否有足够的真实、已承担经济暴露，值得研究；不能用预测 IRR/设计产能/任意比例替代。
2. `OUTCOME_DISCRIMINABILITY`：D3 与 D4 是否超过各自的历史变化和同行共同冲击噪声；二者各自重建，不能互相转换。
3. `INVESTOR_MATERIALITY`：即使统计/会计变化存在，它是否足以影响正常 owner cash、永久损失、资本回报或黄金报告的中心论点。

行动金额不是未来利润或现金的“五年回收”假设。它只说明样本值得投入；D3/D4 阈值必须来自冻结的历史波动、会计口径、竞争场域和经济后果政策。若公开披露不能支撑任何一层，降级而非人为设定一个百分比。`INVESTOR_MATERIALITY=UNKNOWN` 不回写成 admission reject：它可让机制的 A/B 进入独立 learning review，但不得升级为报告使用或行业知识；`REFUTED` 则不得产生投资意义结论。

结论层级也必须固定：

| 结果 | 能获得的权限 |
|---|---|
| `MECHANISM_OBSERVED` | 仅本箭头的描述性事实。 |
| `BOUNDARY_CAPTURED` | 以 `MECHANISM`、`MEASUREMENT`、`SCOPE` 或 `PANEL` 明确失效边界；禁止替代、来源/计量改进；无方向性 selection learning。 |
| `SELECTION_ADMITTED` + 联合 `A_ONLY`/`B_ONLY` | 可申请独立 learning note。 |
| 已迁移、独立复核并冻结的方法 | 可进入 R-103 评价。 |
| R-103 支持 | 才能申请黄金报告研究议程使用权。 |

### 8.1 从训练到行业知识、再到黄金报告的单向路径

Stage-0 的行业面板先形成的是 `INDUSTRY_CONTEXT_AS_OF`：竞争场域、商业载体、可观测字段、可能的外部驱动与披露缺口。它不含任何之后的结果判断，也不能直接把“同行表现”写成 focal 公司事实。

真实 episode 只有在完成方向性结算、跨公司迁移、方法冻结并由 R-103 支持后，才可将窄的 `MECHANISM_CONSTRAINT` 提升为行业知识：适用 arena、decision/carrier/bridge 条件、必需证据、禁止替代、失效方向和 `available_at`。黄金报告只把它读取为 `RESEARCH_AGENDA` 的问题与证据门；公司当期的 `JUDGMENT_SYNTHESIS` 仍由该公司、该 cutoff 的事实和独立判断生成。

```text
Stage-0 industry context
  → V5 PIT episode and settlement
  → accepted cross-company constraint
  → method freeze + R-103 support
  → versioned industry knowledge
  → report research agenda
  → company-specific judgment and valuation
```

这条路径避免两种倒灌：用历史终局替代当前公司判断，或把一个未获留出支持的 training observation 伪装成黄金报告的通用知识。

## 9. 新 episode 前的架构判定，而非又一张表格

每一条真实候选必须先写一页 `mechanism admission memo`，由研究设计者和独立 reviewer 分别回答同一组经济问题：

1. 本案的决策、经济载体、会计计量分别是什么？结论最远允许推到哪里？
2. 最强可行替代方案和 H-B 是什么？它们在哪一条箭头与 H-A 分叉？
3. 本案的竞争场域是什么，为什么是全国/区域/出口/细分/多区域？关键共同冲击是什么？
4. 对每名 peer，哪些 overlap 是本机制必须的，官方来源如何证明？哪些差异反而是有效反方？
5. 选择的 topology 是什么，D2/D3/D4/D5 各自是 voter、diagnostic 还是 unknown，为什么？
6. D3 与 D4 各自如何被计量、在哪个窗口结算、哪些现金项会使其失真？
7. 哪个公开缺口会改变永久损失、价值或中心解释？缺失后结果应是降级还是拒绝？

这不是让作者勾选“通过”。它要求先写出一个别人能够反驳的经济设计；若 reviewer 只能看到字段相等、却看不出该公司到底在和谁竞争、决策影响什么，样本不得登记。

### 9.1 最小可采集来源包

为了不让 agent 先找公告、再倒补 cohort，来源包按时间和用途拆为四层：

| 层 | 只能回答什么 | 最小来源 | 不能提前声称 |
|---|---|---|---|
| `STAGE0_FEASIBILITY` | 可否构成训练 cohort | 至少四家独立控制发行人的 carrier/控制权、按 topology 所需的三期候选 D2 **或**成本字段身份、五期 D3/D4 原始报表身份、arena family。它只核验字段身份和可采集性，不取历史结果数值。 | 最终 peer、共同驱动、行动特定客户吸收。 |
| `ACTION_SCOPE` | 什么决策已发生、谁有选择权、影响哪个 carrier | 预声明 static official PDF package 中的决策/实施、真实经济暴露、scope bridge。 | 预测利润、项目 ROI、已经带来 D4。 |
| `ACTION_SPECIFIC_ARENA_AND_PANEL` | 本机制的 overlap、共同驱动和每个 peer 的 causal role | 公司 cutoff 前披露的暴露证据；必要时版本化公共原件说明驱动背景。 | 严格因果效应或未发生外溢。 |
| `PUBLIC_ARENA_CONTEXT` | 共同驱动的外部背景 | curator 交付的静态、版本化公共原件：发布者、URL/版本、发布日期与精度、数据期、表/字段、适用 arena、允许推论。 | 由研究者在识别公司/行动后上网搜索，或以公司叙事替代外部背景。 |
| `MEASUREMENT_AND_TIME` | D3/D4 能否独立结算 | 逐字段页码、metric identity、经济期间、source available time、D4 cash bridge 和结果期对齐。 | 以披露日晚于 cutoff 替代真实后续经济期。 |

公开资料缺失时的处置必须分开：**freeze 前** carrier/D3/D4 没有同边界 bridge、主结果期不足、或同行相对基线不可构成，拒绝 selection；**freeze 后** custodian 无法取得已登记 member × metric × raw-field × period 矩阵的任何单元，则该 metric 为 `UNKNOWN/NOT_DIAGNOSTIC`，不得换字段、换同业或换结果期。`MIXED` 只用于中心终点均已取得但方向相冲突。决策自主性、客户细节或共同驱动只得到部分支持时，可降级为某条 `MECHANISM_OBSERVED` 或 `TEACHING_ONLY`；无法判定投资意义则保持 `UNKNOWN`。不得以行业标签、公司 OCF、事后叙事、预测或“没有别的变化”补足来源包。

## 10. V5 的不可变身份图与单向状态机

V5 不能只靠一份 JSON 自称冻结。每次状态转换须绑定以下不可变身份；任何经济对象、panel、阈值、计量或结果窗口的材料变化都会创建新的 `selection_freeze_id`，不得原地 amendment 或继承 outcome access。

| identity | 最小绑定内容 |
|---|---|
| `method_epoch_id` | V5 原语、允许 topology、准入/结算政策版本。 |
| `cohort_snapshot_id` | `cohort_eligibility_as_of`、arena family、成员、字段身份与排除。 |
| `action_identity` | action、实施/可见时点、decision scope、carrier、bridge 与裁决范围。 |
| `counterfactual_panel_id` | 有序 target/peer、每人 causal role、arena binding、overlap 证据、排除与不替换规则。 |
| `measurement_contract_id` | D3/D4/D5 metric identity、bridge、公式、原始字段和允许来源。 |
| `outcome_contract_id` | `outcome_window_id`、完整 member × metric × raw-field × period 矩阵、目标/同行周期对齐、初始/重述政策和最小暴露规则。 |
| `selection_freeze_id` | 上述身份、H-A/H-B、阈值与独立 pre-outcome review 的不可变组合。 |
| `selection_freeze_seal_id` | 冻结时间、冻结内容、独立审阅与 research-side outcome-access=NONE 的回执。 |
| `outcome_access_authorization_id` | 只授予 custodian 的结果访问权；任何未授权 researcher/reviewer 结果访问使该 freeze `PIT_INVALID`。 |
| `r103_holdout_reservation_id` | R-103 的 sealed identity；在 `METHOD_FROZEN` 前禁止 body、metadata、派生产物和调参读取。 |
| `episode_collision_key` | 公司、action、carrier、scope bridge 与主结果窗口，防止同一处理重复进训练/迁移/holdout。 |

```text
METHOD_EPOCH_FROZEN
  → COHORT_SNAPSHOT_FROZEN
  → ACTION_OBSERVABLE_AND_BOUND
  → SELECTION_FREEZE_SEALED (selection_freeze_seal_id)
  → OUTCOME_ACCESS_AUTHORIZED
  → OUTCOME_RESOLVED
  → INDEPENDENT_LEARNING_REVIEW
  → METHOD_MIGRATION / METHOD_FROZEN
  → R-103_EVALUATION
```

`NO_PRIMARY` 与 `TEACHING_ONLY` 是 admission 前处置，绝不创建 `selection_freeze_id`；只有 `SELECTION_ADMITTED` 才可被 seal。`NOT_DIAGNOSTIC`、`MIXED`、`UNKNOWN` 与 `BOUNDARY_CAPTURED` 才是已授权 freeze 的 outcome 终态。`OUTCOME_ACCESS_AUTHORIZED` 只能在 seal 存在后发出；任何 researcher/reviewer 在该授权前读取 outcome body 或 metadata，使该 freeze `PIT_INVALID`，不能靠补写较早 cutoff 继续结算。R-104 仅为 `LEGACY_REFERENCE_ONLY` 的无权利边界，不能生成任何 V5 metric、threshold、panel 或 learning 输入；R-103 在 Slice 0/1 是训练侧禁入 identity，只有真正 `METHOD_FROZEN` 后才能作为 evaluation-only overlay 被读取，且不得参与任何 V5 调参、synthetic fixture 或 learning。每个 outcome contract 都须冻结完整的 target + `EXTERNAL_SHOCK_COMPARATOR` × metric × raw-field × period 矩阵：required raw cell 缺失是 `UNKNOWN`；完整数据却不能按预冻结日历或可判别性比较是 `NOT_DIAGNOSTIC`；结果期事实推翻 bridge、metric、scope、panel 或 mechanism premise 是 `BOUNDARY_CAPTURED`。

## 11. 收敛实施顺序

1. 本文由架构审阅接受或退回；在此之前停止 V4 的新候选和外部 source discovery。
2. 以本文为准建立 `JUDGMENT_SELECTION_ADMISSION_V5`，不把 V5 语义偷偷塞进 V4。
3. 先完成 V5 的 synthetic acceptance cases：全国性家电、区域水泥、出口制造、细分 B2B、成本重构，以及各自的反例；其中必须覆盖局部行动缺 bridge、直接 rival 受 spillover 只能 witness、跨行动年度不得当主 outcome、D3/D4 计量面漂移、以及 V5 不能引用 R-104/R-103。
4. 再迁移一份尚未揭盲的真实 historical candidate；R-104 保留旧契约和无权利 `MIXED` 结论，不重算、不回写。
5. V5 的第一条 `SELECTION_ADMITTED` 只有真实结算为联合 `A_ONLY` 或 `B_ONLY` 才能进入跨公司迁移；之后才谈方法冻结、R-103 与报告使用。

## 12. 本轮接受标准

本文只有在以下命题被明确接受后才可进入实现：

- 不同行业/商业机制可以有不同的竞争场域；地理只在机制需要时构成硬门；
- 决策范围、经济载体、会计口径可不同，但必须有 `IDENTITY`、`SEGMENT_MATCH` 或 `QUANTIFIED_ISSUER_AGGREGATION` 作用域桥和结论边界；
- D1--D5 是观察时钟，D3/D4 是经营选择学习的独立终点，不强迫所有机制有客户链；
- 同行必须先分为 external-shock comparator、equilibrium-response witness 或 falsifier；只有前者可进相对基线，不是行业标签或严格因果估计器；
- 材料性、可判别性与投资意义三者分离；
- PIT 防火墙是资料访问规则，不能替代 action window、metric economic period、source availability 和主结果窗口的定义；
- Stage-0 只冻结 arena family 与字段可行性；行动特定场域、D2 身份、peer roles 与共同驱动须在 action 可见后另行冻结；
- V5 identity graph 的每一次材料变更都形成新 `selection_freeze_id`，不重写 R-104、R-103 或既有 V4/legacy 事实；
- 新设计仅以 V5 新版本实施，不给 V4 或 legacy 开兼容捷径。

在这些命题得到独立审阅前，继续枚举公告、扩展 cohort、或追求“第一条合格样本”只会把采集成本压到未完成的概念模型上。
