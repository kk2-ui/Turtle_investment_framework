# Turtle V5：最小实现工作包

> 状态：`SLICE0_1_IMPLEMENTED / G2_RECEIPT_PROVENANCE_SYNTHETIC_VALIDATED / REAL_H1_REGISTRATION_PENDING`
>
> 日期：2026-08-24
>
> 目标：先让一条合成的、再让一条真实但未揭盲的历史判断 episode 能够按正确经济对象冻结与结算；不在实现前扩大案例枚举，也不把 V5 改造为又一套通用工作流平台。

## 1. 本轮已经作出的产品决定

V5 的首要问题是判断训练，不是公告分类。一个真实样本按以下五个状态推进，任何状态都不自动越过下一状态：

```text
COHORT_FEASIBILITY
  → CANDIDATE_DECISION_SCREEN
  → SELECTION_ADMITTED_PRE_OUTCOME
  → OUTCOME_SETTLED
  → LEARNING_TRANSFERRED
```

其中只有 `OUTCOME_SETTLED=A_ONLY|B_ONLY` 才能申请 learning review；`MIXED` 只记录机制边界，`NOT_DIAGNOSTIC` 与 `UNKNOWN` 只记录不可判定原因。R-104 已属于前者，不能算作方向性训练、方法冻结或报告使用证据。

首版只支持两种经营机制：

| topology | 中心路径 | D2 身份 |
|---|---|---|
| `CUSTOMER_RESPONSE` | D1 → D2 → D3 → D4 | `CENTRAL_VOTER` |
| `COST_RESTRUCTURING` | D1 → cost / utilization / delivery → D3 → D4 | `DIAGNOSTIC_NON_VOTER`，除非候选明示客户传导为中心 |

`PRODUCT_OR_INNOVATION` 和 `CAPITAL_ALLOCATION_OR_INTEGRATION` 保持拒绝；它们不是缺一个字段，而是需要各自的经济与反馈契约。

## 2. V5 的唯一语义真源

四份文档有明确分工，不得让旧 V4 文字或代码成为另一套 V5 定义：

| 真源 | 职责 |
|---|---|
| [原语与准入模型](TURTLE_PIT_TRAINING_PRIMITIVES_AND_ADMISSION_MODEL.md) | 经济对象、适用边界、行业知识到黄金报告的单向路径。 |
| [V5 Candidate / Admission Contract](TURTLE_JUDGMENT_SELECTION_ADMISSION_V5_CANDIDATE_CONTRACT.md) | 字段、状态、typed bridge、competitive arena、peer role、D3/D4、时间和结算语义。 |
| [V5 Synthetic Acceptance Matrix](TURTLE_JUDGMENT_SELECTION_ADMISSION_V5_SYNTHETIC_ACCEPTANCE_MATRIX.md) | 机器必须接受或拒绝的无真实结果 fixture。 |
| [V5 控制面迁移设计](TURTLE_V5_CONTROL_PLANE_MIGRATION_DESIGN.md) | V5 与 V4/R-104/R-103 的隔离和 PIT 访问顺序。 |

本工作包只对迁移设计作一个刻意的**最小化收口**：V5 必须保留不可变冻结、授权后才可读取 outcome、collision 防重和 R-103 只读留出；但不在首版实现通用 artifact 管理器、逐组件注册 CLI、第二套迁移框架或无业务价值的审计表。

## 3. 一条 candidate 的最小不可变对象

### 3.1 Stage 0：只证明“值得继续找”，不证明“已经有样本”

`cohort_snapshot` 是 action 尚未进入研究信息集时的静态快照。它只包括：

- `cohort_eligibility_as_of`；
- `arena_family` 与可能的责任单元；
- 至少三家控制权独立的发行人；
- 按 topology 所需的三期候选 D2 **或**成本字段身份；
- 五期候选 D3/D4 原始字段身份；
- cutoff-before 静态官方来源和控制权来源。

它不得含行动、focal target、最终 comparator、共同冲击结论、结果期来源或历史结果数值。三家是 target 加两名可能 comparator 的最低容量，不是行业全集，更不是“必须先取得五家全部数值”的要求。

### 3.2 Action screen：先判断行动，再花钱采集完整面板

行动屏幕只在既有 cohort 内工作，要求：

- `IMPLEMENTED` 的公司整体决策，或有 `IDENTITY`、`SEGMENT_MATCH`、`QUANTIFIED_ISSUER_AGGREGATION` 之一的 carrier→D3/D4 bridge；
- 可证伪的 H-A/H-B，二者在 D3/D4 至少一个中心终点分叉；
- 真实行动暴露、经济权利和最远结论范围；
- 最小、预声明的 static source package。

它不读取结果。局部工厂、子公司、单品行动没有 bridge 时是 `NO_PRIMARY_SCOPE_BRIDGE`，可留下问题卡但不创建 episode。

### 3.3 Competitive arena：关系由机制决定

每个 action screen 都冻结一个 `competitive_arena_contract`：

```text
arena_id
mechanism_topology
product_or_service_scope
customer_choice_or_cost_driver
competition_interface
required_overlap_dimensions[]
geography_role
responsibility_unit
member_exposure_mapping
action_scope_mapping
outcome_scope_mapping
exclusion_rule
```

这个 contract 还必须单列 `external_driver_reference`：它规定 target 与 `EXTERNAL_SHOCK_COMPARATOR` 为何共享一个外部驱动、哪些 exposure 维度必须相同。它不同于 target 与直接 rival 的 `competitive_arena`。区域水泥的本地 rival 可以满足 `competitive_arena` 并作为 witness；场域外但同受燃料/环保冲击、且没有 target spillover 的发行人可满足 `external_driver_reference` 并进入 relative baseline。两种成员关系不得混为一个 geography gate。

`required_overlap_dimensions[].relation` 只能是：

```text
REQUIRED_EQUAL | REQUIRED_OVERLAP | REQUIRED_EXPOSURE | NOT_REQUIRED
```

地理只是一项机制维度：全国性家电可以要求全国产品、客户任务、渠道/成本传导和共同需求，却将省份网络列为 `NOT_REQUIRED`；区域水泥应要求实际运输半径、价格区或需求区的 `REQUIRED_OVERLAP`；出口的目的地是否要求 overlap 取决于它是否正是关税/客户需求机制。

每个 peer 必须先被指定为 `EXTERNAL_SHOCK_COMPARATOR`、`EQUILIBRIUM_RESPONSE_WITNESS` 或 `FALSIFIER`。只有前三名以上的前者可进入 relative D3/D4 baseline；直接受 target 行动影响的 rival 是有价值的 witness，不能冒充未受处理 control。

### 3.4 Selection bundle：唯一需要 sealing 的经济包

一个 `selection_bundle` 嵌入下列不可变子对象，而不是为每个子对象先建立一个独立 CLI 生命周期：

```text
cohort_snapshot_ref
action_scope
competitive_arena_contract
counterfactual_panel
metric_contracts {D3, D4}
time_contract
materiality_and_resolution_contract
outcome_contract
independent_pre_outcome_review
source_firewall_receipt
source_provenance {H1 receipt snapshot, H2 receipt snapshot}
```

`metric_contracts` 的 D3、D4 各自有 perimeter、carrier、typed bridge、公式、ordered raw fields、重述政策、经济期间和材料性阈值。D4 首版只接受预定义的保守 owner-cash 公式：

```text
OCF − all long-lived asset purchase cash
    − max(beginning cash working capital − ending cash working capital, 0)
```

`D4_CONSERVATIVE_OWNER_CASH_V1` 固定 cash working capital 为同一 perimeter 的应收、预付和存货，减应付与合同负债/预收；不得把现金、借款、非经营投资或未声明项目混入。每个 contract 还必须以 `restructuring_cash_treatment` 指定下列唯一一种处理：`IN_OCF_NO_ADDITIONAL_DEDUCTION`、`SEPARATE_OPERATING_CASH_DEDUCTION`、`OUT_OF_PERIMETER_CANNOT_SETTLE`。第二种处理必须把 `restructuring_cash_paid` 作为第 13 个、可由 custodian 重算的 raw field；第一种处理不得额外扣除；第三种处理不得结算。材料性重组现金无法被这三种身份之一确认时，D4 不能结算。更换任一组成项或处理即为新的 metric identity。

`outcome_contract` 必须提供 target + 每个 `EXTERNAL_SHOCK_COMPARATOR` × D3/D4 × raw field × baseline/outcome period 的完整矩阵；不允许由 caller 输入相对 score 或 verdict。

### 3.4.1 Slice 0/1 canonical wire contract

同一份 root `selection_bundle` 必须依次交给 pre-outcome validator、control-plane seal 和 outcome resolver；禁止使用第二种 projection、adapter 或 V4 compatibility shape。除已列经济对象外，它在 root 增加：

```text
selection_freeze_id
episode_collision_key
sealed_at / recorded_at
```

`research_cutoff_at` 的唯一位置是 `time_contract`。`counterfactual_panel.target_issuer_id` 是 target，members 是只有 comparator/witness/falsifier 的发行人列表；outcome matrix 使用同一 issuer identity，不另建 `member_id` 或把 target 重复塞进 panel。

`measurement_contracts` 是恰好两项、以 `clock=D3|D4` 区分的 list。D3 除 formula ID 与 ordered raw fields 外，还必须冻结逐字段系数的 `outcome_formula`；D4 使用 `D4_CONSERVATIVE_OWNER_CASH_V1`。每项 metric 同时有 `baseline_period_id`、`primary_outcome_period_id` 和唯一的 `discriminability` 阈值对象；它只允许对由 raw matrix 重算的 `target_delta`/`relative_delta` 作预登记比较。不得另建平行的 `resolution_rules` 真源。

`outcome_contract.frozen_raw_matrix` 不带 actual outcome source identity，只列 target 与 comparator × metric × period × field 的 raw-cell identity、经济期间和允许 locator policy；`fiscal_calendar_bridge` 同时属于该对象。custodian 在授权后才补 actual source ID、availability 与 filing identity。任何第二套 `metric_contracts` map、独立 `selection_freeze` wrapper 或 duplicate panel member identity 都是 schema failure。

`investor_materiality_status` 与 selection admission 分离，只能为 `SUPPORTED`、`UNKNOWN` 或 `REFUTED`。D3/D4 的 selection hard gate 是 decision materiality 与各自 outcome discriminability；因此 `UNKNOWN` 可以进入 A/B 的独立 learning review，但不得生成可供报告/行业知识使用的结论。`REFUTED` 则不允许把技术 A/B 升格为投资意义或报告使用。

### 3.5 经济与信息时间必须分开

实现只接受以下七个时间身份，并验证它们的顺序：

```text
cohort_eligibility_as_of
action_effective_window
decision_observable_at
research_cutoff_at
metric_economic_period
source_available_at
outcome_window_id
```

`DATE_ONLY` 的同日文件不能变成 cutoff-before 输入。行动跨越财年但未达到最小暴露的年度只能写 `EARLY_ARROW_NON_VOTER`，不可替代 D3/D4 主结果。

## 4. 最小控制面

### 4.1 数据边界

V5 使用同一个开发 SQLite 数据库，但新 namespace 与旧表隔离。生产 DB 在 V5 合成闭环和独立代码审阅通过前不初始化。

Slice 0 是零 DB 的纯 validator；它先覆盖完整 synthetic matrix。G2 在 Slice 1 前增加一个仅保存 closed H1/H2 static-PDF receipt 的不可变表；它不创建 episode、outcome access 或任何真实资料副本。只有那些已 `SELECTION_ADMITTED` 且 source provenance 已解析的合成 bundle 才进入 freeze/event 表：

| 表 | 最小职责 |
|---|---|
| `judgment_v5_preselection_receipts` | H1 static cohort 与 H2 action screen 的原始 immutable payload；PK 是 `receipt_id + receipt_version`，H1 有 cohort/time/curator 自然唯一键，H2 有 parent H1 + screen 自然唯一键。 |
| `judgment_v5_selection_freezes` | 完整 nested selection bundle、freeze seal、collision key 和 predecessor 关系。 |
| `judgment_v5_events` | access、outcome receipt、resolution、void 与 breach 的追加事件。 |

contract/event JSON 可保存小型身份快照和 artifact ref，不能保存 PDF 全文或形成第二个资料库。状态只能由 freeze 与追加事件导出，不维护可被人工更新的 `status` 列。

H1 只能通过 strict H1 validator 登记；H2 只能引用已登记 H1，并从表内 H1 payload 重跑 H2 validator，不能由 caller 重新提交 H1 副本。`source_provenance` 在 pure root 中只保存两份 receipt ref 和 cohort/time/curator、parent/screen/cutoff snapshot；seal 在写 freeze 前解析 H1→H2 parent，并要求 `source_manifest` 的每个 source ID 属于 H1∪H2 static-PDF map。epoch policy、cohort snapshot、action、panel、metric 和 outcome contract 都嵌入 immutable selection bundle；它们不是靠“较晚写入数据库”证明在历史当时存在。R-103 只从第一天起作为禁入 identity；在方法 release 尚未真实需要前，不创建 reservation table、overlay 或任何包含 R-103 身份的 fixture。

### 4.2 首版命令与转换

Slice 1 只需要下列命令；所有底层 action/panel/metric/outcome 子对象由 `seal-freeze` 一次性验证并绑定：

```text
init
register-h1-receipt
register-h2-receipt
seal-freeze
authorize-outcome-access
append-control-receipt
resolve
void-pre-access-freeze
status
```

关键单向规则：

```text
registered H1 → registered H2 → sealed freeze → authorized outcome access → outcome receipt → resolved outcome
```

- authorize 只绑定 frozen member × metric × raw-field × period、allowed source class/locator policy 与 custodian；它不得包含实际 outcome source ID、标题、发布日期或 metadata。actual source inventory 只能在授权后由 custodian 的 outcome receipt 写入。
- outcome package、reader、extraction、missing-cell 与 `PIT_ACCESS_BREACH` 是 `append-control-receipt` 的枚举子类型；首版不将它们做成多条无额外经济状态的 CLI。研究端或 pre-outcome reviewer 实际看过 outcome body/metadata 时，必须追加 `PIT_ACCESS_BREACH`，使该 freeze 终态并拒绝后续 receipt、resolve 和下一 slice 的 learning。
- 同一 `episode_collision_key` 在 outcome access 后不可被另一个 training freeze 重用；尚未 access 的 freeze 只能 `VOIDED_PRE_ACCESS` 后生成 successor，不能修改原 freeze。
- H1/H2 registration 对同一 receipt id/version 只允许字节语义相同的 replay；同 ID 的不同 payload、同一 H1 cohort/time/curator 的第二个 receipt，以及同一 H1 下同一 H2 screen 的第二个 receipt 均为 conflict。registry 不自动登记任何真实 package；开发 namespace 的登记仍是单独、显式动作。

admission 与结果使用两张不互相倒灌的状态表：

| 层 | 合法状态 | 权利 |
|---|---|---|
| admission | `STAGE0_REJECTED`、`NO_PRIMARY_*`、`NOT_ADMITTED` | 不创建 selection freeze、不读 outcome。 |
| non-selection research | `TEACHING_ONLY`、`MECHANISM_OBSERVED` | 只保留问题/边界，不创建 selection freeze。 |
| resolution | `A_ONLY`、`B_ONLY`、`MIXED`、`UNKNOWN`、`NOT_DIAGNOSTIC`、`BOUNDARY_CAPTURED` | 仅 admitted + authorized freeze 可产生；只有 A/B 可在下一 slice 申请 learning。 |
| access invalidation | `EXPOSURE_EXCLUDED` | custodian 发现实际 primary source 在 cutoff 当日或更早可得时，freeze 不结算且不重选同案来源；只有研究端或 pre-outcome reviewer 实际看过该 source/body/metadata 才额外记录 `PIT_ACCESS_BREACH`。 |

`UNKNOWN` 表示合法冻结后缺一个 required raw cell；`NOT_DIAGNOSTIC` 表示完整数据却因 calendar/panel/可判别性无法比较；`BOUNDARY_CAPTURED` 表示结果揭示 bridge、metric、scope 或 panel 不再承载原命题。三个状态都不产生方向性 learning。

### 4.3 不实现的东西

本轮明确不实现：通用工作流引擎、通用 artifact/文件仓库、hash/checksum、可替换同行、概率/显著性/回报评分、产品/资本配置 topology、真实文件采集器、method release/R-103 overlay 或任何 V4 compatibility flag。

## 5. 实现模块和所有权

| 模块 | 责任 | 禁止 |
|---|---|---|
| `schemas/judgment_selection_admission_v5.schema.json` | V5 selection bundle 的静态结构。 | 引用 V4 schema 或放入真实结果。 |
| `schemas/judgment_v5_outcome_resolution.schema.json` | authorized outcome raw matrix 与 derived D3/D4/joint resolution receipt。 | caller 提供 verdict、score 或替代 peer。 |
| `scripts/judgment_selection_v5.py` | 纯 candidate/bundle、H1/H2 provenance snapshot、arena、scope bridge、metric/time/matrix 验证；从 raw outcome 重算 D3/D4 与 joint verdict。 | 导入 V4 validator、写 DB、访问网络。 |
| `scripts/judgment_v5_control_plane.py` | SQLite H1/H2 receipt registration、provenance resolution、sealing、access/event顺序、collision 和 event replay。 | 解释经济机制、访问资料、改写 legacy 或读取 R-103。 |
| `tests/test_judgment_selection_v5.py` | V5 经济契约与 synthetic matrix。 | 实际公司、真实 source 或 DB。 |
| `tests/test_judgment_v5_control_plane.py` | 临时 SQLite 的顺序、冻结、access、collision 与 breach tests。 | 生产 DB 或 R-103 内容。 |
| `tests/test_judgment_v5_end_to_end.py` | 合成 bundle 从 Stage0 至 resolution 的单向闭环。 | 外部 source、R-104/R-103 outcome。 |

V4/V3/legacy 文件、R-104、R-103 和生产数据库都不是本工作包的 writer target。

## 6. 先验测试与实现顺序

1. **Slice 0 — schema + pure candidate validator**：实现 matrix 的每一个 admission fixture（不只是五个理想正例）；先让所有 `NO_PRIMARY`、`TEACHING_ONLY`、legacy touch、Stage0/action leak 和 invalid mirror 通过。
2. **Slice 0 — outcome reconstruction**：从 sealed raw matrix 重算 target + comparator 的 D3/D4，验证 independent metrics、role-specific arena/driver membership、完整 comparator、fiscal bridge、early-arrow、source precision、restatement 与 `A_ONLY/B_ONLY/MIXED/UNKNOWN/NOT_DIAGNOSTIC/BOUNDARY_CAPTURED`。
3. **G2 + Slice 1 — temporary SQLite control plane**：先验证 strict H1 registration、H2 从已登记 parent H1 读取 payload、immutable/natural-key conflict、V5 source provenance 与 closed source map；再验证 admitted synthetic freeze 的 seal、authorized custodian access、actual outcome receipt、mutation successor、collision 与 breach。`NO_PRIMARY` 不得产生 freeze；R-103 身份不得出现在任何 Slice 0/1 input。
4. **Synthetic end-to-end**：至少一个 customer response 的 `A_ONLY` 和一个 cost restructuring 的 `A_ONLY` 可结算；`MIXED`、missing outcome、spillover 和 Stage0/action leak 必须被拒绝或降级，而不是靠替换同行/字段恢复成功。
5. **Independent code/design review**：确认 V5 与 V4/R-104/R-103 没有交叉写入，且 Slice 0/1 与既有 V3/V4 套件完整回归。此时才可申请开发 DB `init`。
6. **真实研究重启**：只接受 curator 提供的 cutoff-before static PDF package；先建立 Stage‑0，再开始 action screen。浏览器当前由用户接管时不取回使用权。
7. **Slice 2（首条真实 A/B 与跨公司迁移之后）**：才增加 post-outcome review、`method_release_policy`、method release 与 R-103 read-only overlay。epoch policy 必须在 Slice 2 前固定：首轮至少一条 `A_ONLY|B_ONLY` 的训练结算、一次不同 company/collision 的 sealed cross-company migration、迁移目标晚于 learning note、且独立 reviewer 接受；R-103 只能评价该 frozen release，永不回流学习。

## 7. V5 实现完成的验收定义

V5 implementation 完成仅代表系统具备正确尝试首样本的能力，不能称“判断力已经提高”。必须同时满足：

1. 全国性家电在不同省份网络下可按其 mechanism contract 通过；区域水泥缺实际 arena overlap 必拒；出口的目的地要求随机制变化；
2. `COST_RESTRUCTURING` 在 D2 非投票时可进入候选，`CUSTOMER_RESPONSE` 缺 D2 必拒；
3. 局部 action 没有 typed bridge 必拒，D3 与 D4 绝不互相代替；
4. Stage‑0 通过不创建 episode、不读 outcome、不授 learning；
5. H1/H2 必须以 immutable receipt/version 登记，H2 parent 与 root `source_provenance` 必须精确解析，且 V5 `source_manifest` 不得超出 H1∪H2 static source map；
6. outcome 只有由独立 custodian 在 seal 后读取，`MIXED`/`UNKNOWN`/`NOT_DIAGNOSTIC`/`BOUNDARY_CAPTURED` 不产生 migration；
7. R-104 不成为 V5 输入，R-103 从开始就是训练侧禁入 identity；仅在 Slice 2 的 frozen method release 后才可创建 evaluation-only overlay；
8. V5 synthetic suites 与现有 V3/V4 回归都通过。

通过这份验收后，下一步只是开始真实的 `COHORT_FEASIBILITY`，不是宣布第一条方向性样本已经存在。真正的第一条训练成果仍要等待一条真实、PIT sealed episode 结算为 `A_ONLY` 或 `B_ONLY`，且独立迁移审阅确认它改变另一家公司冻结前字段。
