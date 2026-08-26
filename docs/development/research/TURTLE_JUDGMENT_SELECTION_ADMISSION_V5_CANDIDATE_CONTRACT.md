# Turtle V5 企业判断选择训练：Candidate / Admission Contract

> 状态：`DRAFT / DESIGN_ONLY / NO_IMPLEMENTATION_AUTHORITY`
>
> 上位设计：[PIT 企业判断训练：原语与准入模型](TURTLE_PIT_TRAINING_PRIMITIVES_AND_ADMISSION_MODEL.md)
>
> 适用方法 epoch：`JUDGMENT_SELECTION_ADMISSION_V5_2_COMPARATOR_PANEL`
>
> 本文只定义未来的 candidate / admission 语义和 synthetic acceptance 形状；它不修改 V4、legacy、R-104、R-103、数据库、JSON schema 或任何执行器。

## 1. 目的、边界与规范用语

V5 的 candidate 不是“一则看起来有意义的公告”，也不是事后能够讲通的案例。它是一个在
`research_cutoff_at` 前已经绑定下列对象、而 outcome 仍未被研究端访问的可结算判断试验：

```text
已实施的可选择行动
  ──authority / implementation──> economic carrier
  ──typed scope bridge───────────> accounting perimeter
  ──metric identity──────────────> D3 与 D4 的独立计量

economic carrier ──mechanism──> competitive arena
competitive arena ──role-specific evidence──> counterfactual panel
```

本文中的 **必须**、**不得**、**仅** 是实现和独立审阅的硬约束；**可** 表示已经被本版本明确允许的分支。未列出的分支不是“让实现者自由解释”，而是 `NO_PRIMARY` 或等待新的 method epoch。

V5 只支持经营选择训练：

| `mechanism_topology` | 允许的 D2 身份 | V5 是否允许 |
|---|---|---|
| `CUSTOMER_RESPONSE` | `CENTRAL_VOTER` | 是 |
| `COST_RESTRUCTURING` | `DIAGNOSTIC_NON_VOTER` 或在机制明确要求时 `CENTRAL_VOTER` | 是 |
| `PRODUCT_OR_INNOVATION` | — | 否；需要独立 product / feedback contract。 |
| `CAPITAL_ALLOCATION_OR_INTEGRATION` | — | 否；需要独立 capital-allocation contract。 |

V5 不估计严格处理效应、显著性、胜率、概率、选股收益或组合回报。相对同行只用于约束“是否只是共同环境变化”；它不能替代行动—载体—计量的因果链。

## 2. 顶层对象与不可变身份

实现时，一个 pre-outcome candidate 必须拥有下列顶层对象。属性名、枚举和对象关系是规范性的；具体 JSON schema 可以在本文被接受后另行实现。

```text
candidate_id
method_epoch_id = JUDGMENT_SELECTION_ADMISSION_V5_2_COMPARATOR_PANEL
cohort_snapshot
action_scope
mechanism_contract
scope_bridge
competitive_arena
external_driver_reference
counterfactual_panel
measurement_contracts = { D3, D4 }
time_contract
materiality_and_resolution_contract
source_manifest
independent_pre_outcome_review
selection_freeze
```

| 对象 | 必须回答的问题 | 不得由什么替代 |
|---|---|---|
| `cohort_snapshot` | 行动被发现前，是否已有不依赖 outcome 的可行性样本与字段身份？ | 最终 peer、行动标题、后来存活者。 |
| `action_scope` | 谁作出何种已实施、可替代的选择，实际作用于哪个 carrier？ | 计划、项目预测、设计产能、仅董事会意向。 |
| `scope_bridge` | carrier 为什么能以此会计边界、且仅以此结论范围，被 D3/D4 观察？ | 集团叙事、合并 OCF、"占大头"。 |
| `competitive_arena` | 本机制在哪个客户/成本/竞争场域结算，共同驱动是什么？ | `industry_id`、总部、同省/同国文字。 |
| `counterfactual_panel` | 哪些成员是共同冲击 comparator，哪些是行动的均衡响应或反方？ | 一份无角色的同业名单或事后中位数。 |
| `measurement_contracts` | D3 与 D4 各是什么、由哪些原始字段算出、边界/期间是否可比？ | 一个方便的收入、利润、OCF 或事后指标。 |
| `time_contract` | 研究者当时知道什么、行动何时生效、哪段经济期间才是主结果？ | 仅一个 cutoff 或仅凭公告发布日期。 |
| `materiality_and_resolution_contract` | 何种变化能区分命题，何种结果只能 UNKNOWN/MIXED？ | 预测 IRR、任意百分比、结果期补写的阈值。 |

所有 ID 在一次 `selection_freeze_id` 中必须不可变。行动、carrier、bridge、arena、panel、metric identity、阈值或主结果窗口任一材料变化，必须创建新的 candidate / `selection_freeze_id`，并重新经过独立 pre-outcome review；不得原地 amendment、继承旧 freeze 的 outcome access，或以“修正措辞”保留结果。

## 3. Stage 0 到 ActionScope 的准入阶段

Stage 0 解决“这个 arena 能否在行动前形成可工作的披露面板”；它**不**选择 action、final peer 或赢家。行动可见后才进入 `ACTION_SCOPE`，不得倒序用醒目公告倒补 Stage 0。

| 阶段 | 固定输入 | 允许产出 | 明确不允许 | 失败处置 |
|---|---|---|---|---|
| `STAGE0_COHORT_FEASIBILITY` | `cohort_eligibility_as_of` 前的 arena family、至少三家控制权独立的上市控制发行人、carrier/控制权、按 topology 所需的三期候选 D2 **或**成本字段身份、五期候选 D3/D4 字段身份 | `COHORT_SNAPSHOT_FROZEN` | action、最终 peer、最终共同驱动、outcome 值、赢家筛选 | `STAGE0_REJECTED`；不读 action/outcome。 |
| `ACTION_SCOPE` | 预声明 cutoff-before static official PDF package 中的已实施决策、替代方案、实施证据、decision authority、carrier、经济权利和会计边界 | `ACTION_SCOPE_BOUND` | 把公告计划、在建工程、预计效益、项目 ROI 当实施或 D3/D4 | `NO_PRIMARY_ACTION_SCOPE`。 |
| `ACTION_SPECIFIC_ARENA_AND_PANEL` | 机制、arena dimensions、共同驱动、逐成员 exposure 和 causal role、final exclusion ledger | `ARENA_PANEL_BOUND` | 因 outcome 替换同行、把 direct rival 自动作 control、用行业标签证明共同冲击 | `NO_PRIMARY_ARENA_OR_PANEL`。 |
| `MEASUREMENT_AND_TIME` | D3/D4 独立 metric identity、历史基线、raw fields、time partition、结果矩阵、阈值/结算规则 | `MEASUREMENT_TIME_BOUND` | D3 替 D4、不同 perimeter 拼接、以报告晚于 cutoff 代替经济暴露 | `NO_PRIMARY_MEASUREMENT_OR_TIME`。 |
| `SELECTION_FREEZE` | 前述全部身份、H-A/H-B、source manifest 与独立审阅 | `SELECTION_ADMITTED` + `PIT_OUTCOME_SEALED` | 结果访问、补搜 outcome、修改成员/字段/窗口 | `NOT_ADMITTED`。 |

`STAGE0_COHORT_FEASIBILITY` 的至少三家只保证“一个 target 加两个可能 comparator”的最低披露容量；它不是完整行业全集，也不是最终 panel。它冻结的是字段身份和可采集性，不是五期历史数值、最终 peer、最终共同驱动或行动特定 D2 结论。最终 eligible-peer universe、排除原因与 member order 必须在 `ACTION_SPECIFIC_ARENA_AND_PANEL` 中冻结，且所有 target / peer 都必须来自 Stage 0 snapshot；若行动后才发现某公司，应创建新的、行动前形成的 cohort snapshot，而不是把它补进旧 snapshot。

## 4. `ACTION_SCOPE`：行动、载体、会计权利与可选替代

### 4.1 必填形状

`action_scope` 至少应实现为以下字段组：

| 字段 | 允许值 / 约束 |
|---|---|
| `action_id`、`focal_issuer_id`、`decision_scope_id` | 非空且在 source manifest 中有 cutoff-before 身份来源。 |
| `mechanism_topology` | 仅 `CUSTOMER_RESPONSE` 或 `COST_RESTRUCTURING`。 |
| `decision_authority` | `ISSUER_MANAGEMENT`、`ISSUER_BOARD`、`REPORTABLE_SEGMENT_MANAGEMENT`；必须描述实际选择权和最强可行 H-B，而非只写发布者。 |
| `implementation_status` | 仅 `IMPLEMENTED` 可进入 V5 selection。`ANNOUNCED`、`APPROVED_NOT_IMPLEMENTED`、`CONSTRUCTION_OR_CIP`、`IRREVOCABLY_INCURRED_WITHOUT_OPERATING_EFFECT` 都不是 D1 已实施，返回 `NO_PRIMARY_ACTION_SCOPE`。 |
| `action_effective_window` | 有 `start`；若 rollout，必须有 `end_or_ongoing_status`、覆盖 carrier 集合及每个载体的实施证据。公告日不得自动写成 start。 |
| `decision_description` | 增量、实际执行的资源/网络/成本/客户取舍；不得含结果期利润或现金结论。 |
| `h_a`、`h_b` | 各有可证伪机制、最强可行替代及对 D3/D4 的不同预登记结果；二者若在所有可结算中心终点不分叉，返回 `NO_PRIMARY_HYPOTHESIS`。 |
| `economic_carriers` | 每个 carrier 有 `carrier_id`、功能类型、法律/经营归属、受影响的 action exposure、行动前基线和 implementation source。 |

`ECONOMIC_CARRIER` 是受行动改变、在机制中实际承担收入、成本、交付、资本或营运资本后果的单元；它可以是经营网络、报告分部、产品线、渠道或资产组合。它不得只写“上市公司整体”，除非官方来源也能把实际实施范围直接绑定为全发行人。

### 4.2 会计边界与经济权利

每个候选必须声明一个或多个 `accounting_perimeter`。每个 perimeter 至少有：

```text
perimeter_id
legal_reporting_entity
reporting_basis = CONSOLIDATED_ISSUER | REPORTABLE_SEGMENT
economic_rights_type = FULLY_CONSOLIDATED | CONSOLIDATED_WITH_NCI | REPORTABLE_SEGMENT_OF_CONSOLIDATED_ISSUER | EQUITY_METHOD | UNCONSOLIDATED
reporting_currency_and_unit
source_ids
```

`EQUITY_METHOD` 与 `UNCONSOLIDATED` carrier 不得使用发行人 D3/D4 结算。`CONSOLIDATED_WITH_NCI` 可进入经营选择训练，但 `measurement_contract` 必须声明 NCI/少数权益处理；结论不得越过其 `conclusion_ceiling` 宣称普通股股东可得现金。会计上的并表不能自动证明行动在经济上覆盖整个 perimeter。

## 5. Typed scope bridge

`scope_bridge` 连接 action carrier 与每个 D3/D4 的 accounting perimeter。每一个 metric 都必须引用恰好一个 `scope_bridge_id`，且桥的 `permitted_conclusion_scope` 不得宽于该 metric 的结论。

### 5.1 唯一允许的 bridge types

| `bridge_type` | 何时允许 | 必须有的冻结事实 | 结论上限 |
|---|---|---|---|
| `IDENTITY` | 受行动的 carrier 与 metric 的完整 accounting perimeter 相同 | 两者同一 `perimeter_id`、同一报告基础、实施范围的官方证据 | 该 perimeter 的经营/现金机制。 |
| `SEGMENT_MATCH` | carrier 与正式 reportable segment 相同，且 D3 与 D4 都由同一 segment 口径直接观察 | segment 定义、各 metric 的 segment field、行动作用于该 segment、重分类政策 | 该 segment；不得推及发行人。 |
| `QUANTIFIED_ISSUER_AGGREGATION` | carrier 比 issuer perimeter 窄，但行动是已实施的发行人资源配置/网络政策，且可用冻结来源量化 carrier 对 issuer 度量的覆盖与排除 | decision→carrier、carrier→issuer 经济权利、channel-matched coverage numerator/denominator、遗漏 material businesses/transactions、行动相关现金、其他已知 material changes | “该发行人网络/资源配置是否改变发行人经济”；不得推断单厂/单项目 ROI。 |

所有 bridge 都须具备下面的 identity 字段：

```text
scope_bridge_id
bridge_type
decision_to_carrier_source_ids
carrier_to_perimeter_source_ids
carrier_perimeter_ids
metric_perimeter_ids
economic_rights_type
action_cash_boundary
permitted_conclusion_scope
```

`IDENTITY` 还必须证明 action implementation scope、economic rights、reporting basis 与完整 metric perimeter 相同；它的 `coverage_basis=NOT_APPLICABLE_FULL_PERIMETER`，不得伪造 100% numerator/denominator。`SEGMENT_MATCH` 还必须证明正式 reportable segment identity、连续性和 action 作用范围；它同样不需要 issuer coverage 比例。只有 `QUANTIFIED_ISSUER_AGGREGATION` 必须补充下列字段：

```text
coverage_basis
coverage_as_of
coverage_numerator
coverage_denominator
known_omitted_material_items
known_other_material_changes
```

其 `coverage_basis` 必须与机制的传导通道相同：产能/关闭网络使用可交付产能、资产或固定成本覆盖；渠道行动使用适用销售、门店/渠道或客户覆盖；不得为了提高比例挑选不相干的分母。`coverage_numerator` 和 `coverage_denominator` 必须指向同一数据期、同一单位和 source IDs；没有可观察的合适 coverage basis，即使管理层称“核心业务”，仍为 `NO_PRIMARY_SCOPE_BRIDGE`。

`known_other_material_changes` 是已经在有限的、冻结 source package 内观察到的事项清单，不是“世界上没有别的变化”的断言。结果期发现该清单不足以维持 bridge 或 metric comparability 时，不得回填 pre-outcome 证据；按第 10 节结算为 `BOUNDARY_CAPTURED(boundary_kind=MEASUREMENT|SCOPE)` 或 `NOT_DIAGNOSTIC`。

## 6. `COMPETITIVE_ARENA`：机制维度而非地理字符串

每个 candidate 有一个 `competitive_arena`，每个 peer 有一个对该 arena 的 `arena_membership`。共同的行业代码、总部、上市板块、"全国"或"出口"文字都不能单独成为 membership 证据。

```text
competitive_arena_id
market_scope_type = NATIONAL | REGIONAL | EXPORT | SEGMENT | MULTI_REGION_PORTFOLIO
market_clearing_description
product_or_service_scope
customer_choice_or_cost_driver
required_overlap_dimensions[]
```

`competitive_arena` 描述 target 的行动在哪个客户、成本或竞争场域发生；它不等同于 D3/D4 相对 baseline 的共同环境。后者由独立的 `external_driver_reference` 描述：

```text
external_driver_reference_id
driver_description
required_exposure_dimensions[]
target_driver_exposure_source_ids
permitted_comparator_relation
```

这两个对象可以重合，例如全国性家电面对同一全国需求/投入冲击；但区域网络重构通常不同。区域内直接 rival 是 `competitive_arena` 的成员，却可能受 target 行动外溢，因而只能成为 witness。处于场域外、但面对同一燃料或监管冲击且没有材料性外溢的发行人，可以满足 `external_driver_reference` 并进入相对 baseline。

每个 `competitive_arena.required_overlap_dimensions[]` 或 `external_driver_reference.required_exposure_dimensions[]` 条目必须包含：

```text
dimension = PRODUCT | CUSTOMER_TASK | COST_DRIVER | GEOGRAPHIC_MARKET | DESTINATION_MARKET | CURRENCY | REGULATION | TECHNOLOGY_OR_CERTIFICATION
relation = REQUIRED_EQUAL | REQUIRED_OVERLAP | REQUIRED_EXPOSURE | NOT_REQUIRED
rationale_from_mechanism
target_evidence_source_ids
peer_evidence_source_ids
```

`relation` 是逐机制指定的，不是由 `market_scope_type` 自动生成：

- `REQUIRED_EQUAL` 表示 target/peer 有同一个具名市场、客户任务、成本驱动或监管对象；
- `REQUIRED_OVERLAP` 要求有可解释的实际重叠（例如交付半径、同一价格区、同一目的地市场），不能以两个地名字符串相等替代；
- `REQUIRED_EXPOSURE` 表示面对同一驱动及同一传导方向，但不要求经营地点相同；
- `NOT_REQUIRED` 必须写明该维度为何不在本机制的传导链中，不能只留空。

### 6.1 scope type 的硬规则

| `market_scope_type` | 必须证明 | 默认不要求 | 何时地理成为硬门 |
|---|---|---|---|
| `NATIONAL` | 同一全国性产品/客户选择或成本传导、全国竞争/需求暴露 | 工厂、总部、各省网络或销售占比相同 | 仅当该 action / H-A 明确依赖特定区域网络。 |
| `REGIONAL` | 具名市场的实际竞争或成本传导 | 总部、全国行业标签 | 必须：`GEOGRAPHIC_MARKET = REQUIRED_OVERLAP`，例如相同/实质相交的运输半径、价格区或需求区。 |
| `EXPORT` | 出口业务和机制相关的客户/驱动暴露 | 国内销售地域、相同全部出口目的地 | 仅当机制是某目的地关税、监管或需求冲击时，`DESTINATION_MARKET = REQUIRED_OVERLAP`；汇率/全球原料机制可用 `CURRENCY`/`COST_DRIVER = REQUIRED_EXPOSURE`。 |
| `SEGMENT` | 同一客户任务、替代关系、认证/切换或技术约束 | 宽泛一级行业、地理描述 | 仅当客户任务/认证/监管以地域定义。 |
| `MULTI_REGION_PORTFOLIO` | 一个具名主导 sub-arena，或所有预声明的 material sub-arenas 的逐一 arena contract | “覆盖多个地区”本身 | 每个被机制声明为必要的 sub-arena 都按其真实机制决定；没有主导/逐一证据时拒绝。 |

因此，V5 明确允许全国性家电同行拥有不同地区网络；明确拒绝仅因同省/同行业就将水泥公司配入 panel；也明确不把所有出口商强制到同一目的地。唯一硬门来自这个 episode 已冻结的传导机制。

## 7. `COUNTERFACTUAL_PANEL`：角色先于中位数

一个 member 在一个 candidate 的 outcome 前只能有一个 `causal_role`：

| `causal_role` | 可用于什么 | 必填状态 | 不得用于什么 |
|---|---|---|---|
| `EXTERNAL_SHOCK_COMPARATOR` | D3/D4 相对基线 | `shared_driver_exposure = PROVEN`，`parallel_action = BOUNDED_ABSENT`，`target_action_spillover = BOUNDED_NONINTERFERENCE` | 观察目标行动对其造成的竞争响应。 |
| `EQUILIBRIUM_RESPONSE_WITNESS` | 价格、供给、客户或竞争反应的 diagnostic/boundary evidence | `target_action_spillover = MATERIAL_RISK` 或行动影响被机制预期 | D3/D4 peer median、共同冲击 control。 |
| `FALSIFIER` | H-A/H-B 必要条件、反方或失效边界 | 有意改变一个预登记关键条件，且该差异来源可证 | 共同环境代表或 peer median。 |

`parallel_action` 只允许 `DISCLOSED`、`BOUNDED_ABSENT`、`UNKNOWN`；`target_action_spillover` 只允许 `MATERIAL_RISK`、`BOUNDED_NONINTERFERENCE`、`UNKNOWN`。`BOUNDED_*` 的含义严格限于冻结前、预声明 static source package 和本机制的材料性范围；它不是“证明现实世界没有任何行动/外溢”。

只有 `EXTERNAL_SHOCK_COMPARATOR` 组成的、预冻结且有序的 2–7 名 peer 可进入 D3/D4 相对基线。`EQUILIBRIUM_RESPONSE_WITNESS` 和 `FALSIFIER` 可为零或多名，不能写入 median、MAD 或 threshold。缺少两个可用 comparator 时为 `NO_PRIMARY_ARENA_OR_PANEL`，不能用 witness 或行业中位数补足。

每个 peer entry 必须有：

```text
member_id / issuer_id / control_group_id
causal_role
mechanism_arena_membership and every required-overlap source
external_driver_reference_membership and every required-exposure source
shared_driver_exposure and source
parallel_action state and bounded-source basis
target_action_spillover state and mechanism rationale
eligible_for_relative_baseline (true only for EXTERNAL_SHOCK_COMPARATOR)
pre-freeze exclusion or non-replacement rule
```

`EQUILIBRIUM_RESPONSE_WITNESS` 必须证明 mechanism-arena membership，但不承担 relative raw matrix 或 baseline 义务。`EXTERNAL_SHOCK_COMPARATOR` 必须证明 external-driver membership；只有当该 driver 本身按 mechanism 需要地理/客户/产品 overlap 时，才额外证明对应的 arena dimension。`FALSIFIER` 只证明其预登记的反证条件。同行、同地或常识不可填补缺口。区域水泥的直接 rival 若会因 target 减产而改变价格/利用率，通常是 `EQUILIBRIUM_RESPONSE_WITNESS`；它很有价值，但不是 target owner-cash 的未处理 baseline。若结果期的正式材料表明一个 comparator 实际存在 parallel action、材料性外溢或度量漂移，不能用新 peer 替换它，必须是 `BOUNDARY_CAPTURED(boundary_kind=PANEL|MEASUREMENT)`。

## 8. D3 与 D4 的独立 metric identity

V5 选择训练必须有一个 `D3` 和一个 `D4` primary metric contract；两者分别可复算、分别结算、分别具有材料性锚和相对 baseline。D3 改善不得填补 D4 缺失，D4 也不得反向验证 D3。

### 8.1 所有 metric 的公共字段

```text
metric_id
clock = D3 | D4
economic_construct
accounting_perimeter_id
carrier_or_segment_id
scope_bridge_id
currency_and_unit
period_basis = FISCAL_YEAR | QUARTER | TRAILING_PERIOD
gross_or_net_definition
formula_id
formula_and_ordered_raw_fields
raw_field_source_locators
restatement_or_reclassification_policy
baseline_observation_matrix
primary_outcome_matrix
source_available_at_policy
allowed_conclusion_scope
```

`accounting_perimeter_id`、`carrier_or_segment_id`、`scope_bridge_id` 必须相互一致。不同 segment、不同并表范围、单位/币种、累计与单季、毛额与净额或重分类口径不能静默拼接。若原件重述历史期，contract 必须事先写明只取 initial filing、只取 restated series、或什么条件下 `BOUNDARY_CAPTURED(boundary_kind=MEASUREMENT)`；不得在结算后挑取有利版本。

### 8.2 D3

`D3.economic_construct` 必须是已声明 carrier/perimeter 的 operating contribution，且 formula 的分子和任何销量、收入、单位成本分母属于同一会计/经济边界。允许的识别模式只能是：

```text
OPERATING_CONTRIBUTION_AMOUNT
OPERATING_CONTRIBUTION_MARGIN
UNIT_ECONOMICS_FROM_SAME_PERIMETER_FIELDS
```

使用全公司利润除单产品销量、用合并收入支持无 bridge 的分部利润、或把预测产能当实际 contribution，一律 `NO_PRIMARY_D3_IDENTITY`。

### 8.3 D4

`D4.economic_construct` 是由同一 perimeter 和 scope bridge 支持的保守 owner-cash proxy。V5 的默认可结算公式为：

```text
cash_from_operating_activities
− cash_paid_for_all_long_lived_asset_purchases
− max(beginning_cash_working_capital − ending_cash_working_capital, 0)
```

其中“全部长期资产”必须使用同一 cash-flow statement 上涵盖固定资产、无形资产和其他长期资产购建的现金字段；不得只扣有利的一类 capex。公式必须同时冻结 OCF、long-lived asset cash、期初/期末 cash working capital 的 raw-field locator、符号、单位、NCI/少数权益处理和行动相关重组现金的处理。若可观察字段不能在 scope bridge 允许的 perimeter 上形成该公式，返回 `NO_PRIMARY_D4_IDENTITY`，而不是让 D3 替代。

`cash working capital` 在本 epoch 固定为：应收、预付和存货，减应付与合同负债/预收；不得把现金、借款、非经营投资或未声明项目混入。每个 D4 contract 还必须有 `restructuring_cash_treatment`，且只能为 `IN_OCF_NO_ADDITIONAL_DEDUCTION`、`SEPARATE_OPERATING_CASH_DEDUCTION` 或 `OUT_OF_PERIMETER_CANNOT_SETTLE`。材料性重组现金无法被归入其中之一时，D4 为 `NO_PRIMARY_D4_IDENTITY`。更换任一 cash-WC component 或 treatment 都是新的 metric identity。

V5 可以在未来 method epoch 增加另一种 D4 formula；在该 epoch 实施前，任何未列公式都是 `NO_PRIMARY_D4_IDENTITY`。

## 9. 时间、材料性与 outcome contract

### 9.1 时间对象

每个 candidate 必须固定以下对象：

```text
cohort_eligibility_as_of
action_effective_window { start, end_or_ongoing_status }
decision_observable_at
research_cutoff_at
metric_economic_period for D3 and D4 { start, end }
source_available_at for every source { timestamp_or_date, precision = INTRADAY | DATE_ONLY }
outcome_window_id
fiscal_calendar_bridge (if target and comparator periods differ)
minimum_decision_exposure_rule
```

硬不变量：

```text
cohort_eligibility_as_of < action_effective_window.start
cohort_eligibility_as_of < decision_observable_at
action_effective_window.start <= research_cutoff_at
decision_observable_at <= research_cutoff_at
every pre-outcome source_available_at <= research_cutoff_at
every primary-outcome raw source_available_at > research_cutoff_at
primary metric_economic_period.start > action_effective_window.start
```

只有日期、没有时刻的来源是 `DATE_ONLY`；发布日期与 cutoff 同日时必须视为非 cutoff-before。行动在年末实施而全年指标大多未受行动影响时，该年度只能是 `EARLY_ARROW_NON_VOTER`，不得结算主 D3/D4。报告在 cutoff 后发布不等于其经济期间符合 outcome contract。

### 9.2 材料性与结算

`materiality_and_resolution_contract` 必须将三种问题分开：

| 对象 | 必须冻结 | 禁止替代 |
|---|---|---|
| `decision_materiality` | 已承担真实经济暴露、carrier coverage 与适用 conclusion ceiling | 预测 IRR、设计产能、任意“预计五年回收”。 |
| `d3_outcome_discriminability` | D3 自身历史波动、相对 comparator 噪声、primary/rival threshold | D4 波动或另一指标阈值。 |
| `d4_outcome_discriminability` | D4 自身历史波动、相对 comparator 噪声、primary/rival threshold | D3 阈值或利润增长。 |
| `investor_materiality` | `status=SUPPORTED|UNKNOWN|REFUTED`，以及对正常 owner cash、永久损失、资本回报或黄金报告中心论点的预声明影响路径 | 仅因统计上有变化就宣称投资意义。`UNKNOWN` 不阻断技术 A/B 的独立 learning review，但禁止行业知识或报告使用；`REFUTED` 禁止将技术结果升级为投资意义。 |

`outcome_contract` 必须列出完整且有序的：

```text
target and every EXTERNAL_SHOCK_COMPARATOR
× D3 and D4
× every raw field
× baseline period and primary outcome period
× source document class / allowed locator
```

它还必须冻结 `joint_verdict_map`：只有 D3、D4 都取得完整矩阵且按照其各自规则指向同一 H-A 或 H-B，才是 `A_ONLY` 或 `B_ONLY`；两个已完整、却相反方向的中心终点才是 `MIXED`。该 map 不能让 D2、witness、falsifier 或非主期替代中心终点。

## 10. Freeze 前拒绝与 freeze 后结果，绝不倒灌

| 时点 | 状态 | 含义与动作 |
|---|---|---|
| pre-freeze | `STAGE0_REJECTED` | cohort 未在行动前形成或字段可行性不成立；停止该 snapshot。 |
| pre-freeze | `NO_PRIMARY_*` | 已实施行动、bridge、arena/panel、D3/D4 identity、时间或 hypothesis 任一主门缺证；不创建 episode，不读取 outcome，不以更多结果资料补洞。 |
| pre-freeze | `NOT_ADMITTED` | 独立 reviewer 未接受或 source manifest / freeze identity 不完整；修订任何材料对象必须新建 freeze。 |
| post-freeze | `UNKNOWN` | outcome custodian 无法取得已登记 member × metric × raw-field × period 矩阵中的任一必需单元；不得换字段、peer、时间窗或报告版本。 |
| post-freeze | `NOT_DIAGNOSTIC` | 完整数据但预登记 fiscal bridge、主期可比性或 outcome discriminability 无法得出可比较方向；只记录不可判定。 |
| post-freeze | `BOUNDARY_CAPTURED` | 结果期事实显示预冻的 bridge、metric、scope、panel 或机制不能承载原结论；必须写 `boundary_kind=MEASUREMENT|SCOPE|PANEL|MECHANISM`，改进 acquisition/contract，不产生方向 learning。 |
| post-freeze | `MIXED` | D3、D4 都完整但依据 `joint_verdict_map` 指向相反命题；不产生方向 learning。 |
| post-freeze | `A_ONLY` / `B_ONLY` | 仅在完整且同向的 joint verdict；可以申请独立 learning review，绝不直接进入报告或方法冻结。 |

`UNKNOWN` 是后果期的诚实缺口，不能回溯伪造为“当初样本不合格”；`NO_PRIMARY` 则是在结果未读时已经不能合理结算的候选。两者必须分表存储，不能让 outcome 质量决定 action admission。

## 11. Synthetic acceptance 形状

以下不是公司案例、数据或投资结论；是 V5 实现必须覆盖的形状。每个正形状仍须通过全部对象和 source contract，不是自动 admission。

### 11.1 全国性家电：通过与拒绝

**可通过的形状：** 目标是全国性品牌的已实施全发行人渠道/成本网络行动；carrier 与合并 perimeter 为 `IDENTITY`，或有合格的 `QUANTIFIED_ISSUER_AGGREGATION`。机制把 `PRODUCT`、`CUSTOMER_TASK` 和全国需求/投入 `COST_DRIVER` 声明为 required；各 comparator 用 cutoff-before 来源证明全国竞争暴露、无 parallel action、bounded noninterference。同行的省级销售、工厂和渠道组织不同仍可通过，因为这些维度被登记为 `NOT_REQUIRED`。

**必须拒绝的形状：** 仅因四家公司同属家电 industry code 或都写“全国销售”就建 median；或行动实际只在一个省/一个产品实施、却没有 carrier→issuer bridge。前者为 `NO_PRIMARY_ARENA_OR_PANEL`，后者为 `NO_PRIMARY_SCOPE_BRIDGE`。

### 11.2 区域水泥：通过与拒绝

**可通过的形状：** 已实施的 issuer-level 生产网络重构有量化 issuer aggregation bridge；target arena 将 `GEOGRAPHIC_MARKET = REQUIRED_OVERLAP` 定义为同一价格区/实质重叠交付半径，并有当地需求、供给或监管共同驱动来源。直接受目标减产影响的 rival 明确为 `EQUILIBRIUM_RESPONSE_WITNESS`；只有满足独立 `external_driver_reference`、不受目标行动材料外溢的成员可作 comparator。

**必须拒绝的形状：** 两家公司总部在同省或同属水泥行业、却无交付半径/价格区重叠；或把会受 target 关产影响的 rival 塞进 peer median。这分别是 `NO_PRIMARY_ARENA_OR_PANEL` 与 `BOUNDARY_CAPTURED(PANEL)`（若污染在结果期才发现）。

### 11.3 出口制造：通过与拒绝

**可通过的形状：** 出口制造商的已实施成本重构，机制的共同驱动是同一结算货币或全球原料成本；`CURRENCY` / `COST_DRIVER = REQUIRED_EXPOSURE`，国内地域与完全相同的目的地均为 `NOT_REQUIRED`。每个 comparator 有来源证明相关出口及该驱动暴露。

**必须拒绝的形状：** H-A 的核心是某一进口国关税或当地客户需求，panel 却只证明“都是出口商”，没有被影响目的地/客户市场的 `REQUIRED_OVERLAP`。这不是 geography 字段宽松，而是关键机制缺证，返回 `NO_PRIMARY_ARENA_OR_PANEL`。

### 11.4 局部行动到发行人计量：通过与拒绝

**可通过的形状：** 发行人已实施整个网络的资源配置政策；单个工厂是 carrier 集合的一部分，且冻结来源能把受影响产能/固定成本/渠道覆盖与完整 issuer perimeter 以同一机制分母量化，列出未覆盖业务、NCI/现金边界和其他已知 material changes。D3/D4 的结论严格是发行人网络政策对发行人经营/现金的影响，绝不是该工厂 ROI。

**必须拒绝的形状：** 一家子公司或单一厂的停线，只能提供集团收入/OCF，且没有 legal/economic-rights link、channel-matched coverage 或同边界 metric。不得因“核心资产”“董事会决定”或集团规模合理而放行；返回 `NO_PRIMARY_SCOPE_BRIDGE`，最多是 `TEACHING_ONLY` / `QUESTION_ONLY`。

## 12. 实施接受标准

在创建 V5 schema、validator、reviewer 或真实 candidate 前，设计审阅必须确认：

1. 实现能独立拒绝 action 未实施、action→carrier 不清、carrier→perimeter 无 typed bridge、或 D3/D4 任一 metric identity 漂移；
2. `market_scope_type` 不再以 geographic string exact equality 作为通用校验，required overlap 由 mechanism contract 逐维度、逐成员、带 source 验证；
3. 只有 2–7 名 `EXTERNAL_SHOCK_COMPARATOR` 可参与相对基线；witness/falsifier 永不进入 median 或 threshold；
4. Stage 0 的 cohort 可行性和 ActionScope 的行动特定判断保持单向，Stage 0 不含 final peer/action/outcome；
5. D3/D4 各自有 complete raw-field matrix、期间/口径/重述和 NCI 处理，且 joint verdict 对 `UNKNOWN`、`NOT_DIAGNOSTIC`、`MIXED` 不产生方向 learning；
6. 合成测试至少包含第 11 节四个正反形状，以及结果期 comparator 污染、同年跨 action 的 early-arrow、单位/segment 重分类和 R-104/R-103 不能成为 V5 输入的反例；
7. 任一材料修订创建新 `selection_freeze_id`，不改写 V4、legacy、R-104 或 R-103。

通过上述接受标准之后，下一步才是把本契约转写为独立的 V5 schema、candidate validator、reviewer 和 synthetic fixtures；在那之前不得恢复真实候选 discovery 或结果访问。
