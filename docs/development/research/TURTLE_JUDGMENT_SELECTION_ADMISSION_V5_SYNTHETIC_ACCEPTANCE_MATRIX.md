# Turtle V5 企业判断选择训练：Synthetic Acceptance Matrix

> 状态：`DRAFT / DESIGN_INPUT_ONLY / NO_CODE_OR_DATABASE_CHANGE`
>
> 日期：2026-08-24
>
> 上位设计：[V5 原语与准入模型](TURTLE_PIT_TRAINING_PRIMITIVES_AND_ADMISSION_MODEL.md)

## 1. 目的与非目标

这是一份 **实现前** 的验收矩阵。它把 V5 的经济边界变为一组无真实公司、无真实公告、无价格和无结果泄漏的合成输入。未来的 schema、validator、candidate binder、outcome custodian 与 reviewer 都必须对同一组 fixture 得出这里指定的状态。

它验证的是：系统会不会在错误输入时停止、降级或保持结果隔离；不验证任何行业、公司、模型、投资回报或方法胜率。`SELECTION_ADMITTED` 在本文中只表示一个合成对象可以进入结果前冻结，绝不表示方法已经有效。

本文不重跑 V4、R-104 或 R-103，也不把 V5 语义写回旧对象。

## 2. 共同 fixture 语言

每个 case 使用 `SYNV5:` 身份，且所有 source 都是预置的虚拟官方原件。实现时 fixture 至少应能表达下列字段；不能只传一个“通过/失败”布尔值：

```text
source_id, source_lane, publisher, official_artifact_id,
published_at_or_date, availability_precision,
economic_period, issuer_id, control_group_id,
accounting_perimeter, carrier_or_segment, field_locator,
permitted_role, outcome_visibility
```

来源 lane 只可为：

| lane | 用途 | 访问身份 |
|---|---|---|
| `STAGE0_STATIC` | cohort、控制权、carrier 与历史字段身份 | cutoff 前 curator supplied static package。 |
| `ACTION_STATIC` | 已实施决策、经济暴露和作用域桥 | 行动可见后、cutoff 前的预声明 static package。 |
| `PUBLIC_ARENA_CONTEXT` | 版本化监管/统计/海关的共同驱动背景 | curator supplied static public original；不允许研究 agent 搜索前端。 |
| `OUTCOME_SEALED` | 已冻结 D3/D4 原始结果字段 | 只有独立 custodian 在 `OUTCOME_ACCESS_AUTHORIZED` 后可读。 |

`availability_precision = DATE_ONLY` 时，来源只在发布日期**严格早于** cutoff 日期时可被当作 cutoff 前事实；同日来源不可虚构时分秒。所有 `OUTCOME_SEALED` 原始字段在 outcome access 前必须不可见。

### 2.1 共同状态语义

| 时间点 | 缺口或结论 | 正确状态 | 不授予的权利 |
|---|---|---|---|
| `SELECTION_FREEZE_SEALED` 前 | cohort、bridge、核心 panel 或主结果窗口不可构成 | `NO_PRIMARY` | outcome access、方向性 learning、方法冻结。 |
| `SELECTION_FREEZE_SEALED` 后 | 一个预登记的 required raw field 无法取得 | `UNKNOWN` | 方向性 learning、方法冻结、R-103 揭盲、报告使用。 |
| `SELECTION_FREEZE_SEALED` 后 | 完整数据但 fiscal window / 可判别性无法比较 | `NOT_DIAGNOSTIC` | 同上。 |
| `SELECTION_FREEZE_SEALED` 后 | 结果期正式事实推翻 bridge、metric identity、scope、panel 或机制前提 | `BOUNDARY_CAPTURED(kind)` | 同上；只沉淀 acquisition / contract 边界。 |
| outcome 已取得 | D3 与 D4 对 H-A/H-B 给出相反中心结论 | `MIXED` | 同上；只可记录机制边界。 |
| 仅观察到一条非中心箭头 | `MECHANISM_OBSERVED` 或 `TEACHING_ONLY` | selection learning。 |
| 结果完整且 D3/D4 同向 | `A_ONLY` 或 `B_ONLY` | 仍须独立 learning review；不能直接声称能力。 |

下表中的“预期结算”仅在该 case 已合法冻结、随后由独立 custodian 读取指定合成 raw fields 时才发生；它不是研究者在候选阶段可见的输入。

## 3. 核心行业与作用域 cases

| ID | 最小输入形状（全部为 cutoff 前虚拟静态来源，除 outcome） | 预期准入 / 结算 | 会拦截的错误 |
|---|---|---|---|
| `V5-S01-NATIONAL-APPLIANCE` | 五家独立控制的耐用消费品发行人；`market_scope_type=NATIONAL`，共同的品类、客户选择、全国渠道和需求/核心投入暴露均有来源。不同省份工厂和销售网络明确为 `NOT_REQUIRED`。target 的发行人级服务网络/价格政策已实施，D2 为三期独立实际销量或活跃用户，D3/D4 为同一合并口径五期字段；三名 comparator 有共同驱动，且由允许的 static package 得到 `parallel_action=BOUNDED_ABSENT`、`spillover=BOUNDED_NONINTERFERENCE`，而不是“未见披露”。H-A 预测 D2 保持、D3 与保守 D4 相对 peers 改善；H-B 预测无相对改善。sealed outcome 设为 D2、D3、D4 均只支持 H-A。 | `STAGE0_FEASIBILITY_REVIEWABLE → SELECTION_ADMITTED → A_ONLY`。 | 把“不同省份”误当成不同市场；或用行业代码、收入、公告标题替代 customer/driver/现金契约。 |
| `V5-S02-REGIONAL-CEMENT` | 五家控制独立的水泥发行人。target 的区域窑线/物流网络已经重构，`COST_RESTRUCTURING` topology，D2 是 `DIAGNOSTIC_NON_VOTER`；作用域为发行人级网络政策并有量化 aggregation bridge。target 与本地直接 rivals 的 `mechanism_arena` 要求运输半径/价格区 `REQUIRED_OVERLAP`，这些 rivals 被标为 `EQUILIBRIUM_RESPONSE_WITNESS`。relative baseline 只使用三个**不在目标运输半径内**、但由官方来源证明面对同一燃料/环保 `external_driver_reference`，且有 `parallel_action=BOUNDED_ABSENT` 与 `spillover=BOUNDED_NONINTERFERENCE` 的 `EXTERNAL_SHOCK_COMPARATOR`；它们不冒充区域竞争场成员。总部所在地不是门。outcome D3/D4 同向支持 H-A。 | `STAGE0_FEASIBILITY_REVIEWABLE → SELECTION_ADMITTED → A_ONLY`。 | 将区域直接竞争者错误混入 control median；把“全国水泥”或总部地理当成竞争场证明；强迫成本机制伪造客户 D2。 |
| `V5-S03-EXPORT-MANUFACTURING` | 五家独立出口制造商；行动前资料证明相关出口产品、目的地/客户任务、汇率和材料成本暴露。机制依赖目的地关税，故目的地 overlap 为 `REQUIRED_OVERLAP`；国内地域为 `NOT_REQUIRED`。target 已实施的供应链/产品认证决策与 D2（三期经认证实际交付）同 carrier；D3/D4 同口径。peers 共享关税/汇率冲击，并由静态包支持 `parallel_action=BOUNDED_ABSENT` 与 `spillover=BOUNDED_NONINTERFERENCE`。outcome 的 D3/D4 同向支持 H-B。 | `STAGE0_FEASIBILITY_REVIEWABLE → SELECTION_ADMITTED → B_ONLY`。 | 只因都标“出口”就制造同行；以国内地理不一致误拒有效 comparator；把事后汇率或出口额倒灌为 cutoff 前原因。 |
| `V5-S04-B2B-SEGMENT-CASH-UNKNOWN` | 细分 B2B 客户任务、认证和切换成本有来源，target 的行动只作用于一个持续披露分部。分部收入/成本连续，但不存在分部 OCF、capex、现金营运资本或可审计的 issuer aggregation bridge；D3 可观察，D4 只能标 `UNKNOWN`。 | `STAGE0_FEASIBILITY_REVIEWABLE → TEACHING_ONLY`；不得 `SELECTION_ADMITTED`，无 D3/D4 联合结算。 | 用集团 OCF 替代分部现金；因为 B2B 叙事很强就越过 D4 缺口。 |
| `V5-S05-COST-RESTRUCTURING-NONVOTER-D2` | 五家独立控制制造业发行人，成本驱动/交付约束和共同投入冲击有来源。target 的发行人级采购、产线或网络重构已实施，D1→成本/利用率→D3→D4 的两条相反符号已冻结；三期成本字段存在。没有客户吸收主张，D2 被明示为 `DIAGNOSTIC_NON_VOTER` 而非缺失。outcome 的 D3/D4 同向支持 H-A。 | `SELECTION_ADMITTED → A_ONLY`。 | 仍把五层时钟误读为所有案件必须有客户链；或用 D3 改善替代 owner cash。 |
| `V5-S06-LOCAL-ACTION-NO-BRIDGE` | 一家发行人的单厂关停或单品提价已实施，且可能很大；只有集团 D3/D4。没有 `IDENTITY`、`SEGMENT_MATCH` 或量化 issuer aggregation bridge，且行动覆盖率、其他 material 变化、行动现金边界不可审计。 | `NO_PRIMARY`；如行动事实有价值，最多 `TEACHING_ONLY / QUESTION_ONLY`。不创建 `selection_freeze_id`。 | 用“看起来占大头”、项目金额、减值或集团现金为局部行动制造 ROI/现金归因。 |

## 4. 同行、竞争场与 Stage-0 顺序 cases

| ID | 最小输入形状 | 预期准入 / 结算 | 会拦截的错误 |
|---|---|---|---|
| `V5-S07-PEER-SPILLOVER` | Stage-0 cohort 自身合格。行动可见后，target 与三名本地直接 rival 同处运输半径；公开行动范围显示 target 减产/扩张必然改变 rival 的价格、利用率或客户分配。三名 rival 均有 D3/D4，但只能标 `EQUILIBRIUM_RESPONSE_WITNESS`；没有另一个共同驱动且可界定不受行动外溢的 comparator。 | `NO_PRIMARY` for selection relative baseline；可留下 `MECHANISM_OBSERVED`，但不得读 outcome 来“证明”机制。 | 将被处理的直接 rival 当未处理 control；为证明“没有外溢/没有并行动作”而穷尽搜索公告。 |
| `V5-S08-COMPARATOR-UNKNOWN-PARALLEL-ACTION` | 有三个表面可比 peer，但仅有常规年报字段；没有静态来源能界定 peer 是否存在同类重大行动，或是否可能被 target 外溢。输入将二者标为 `UNKNOWN`，不是 `ABSENT`。 | 这些成员不能作 `EXTERNAL_SHOCK_COMPARATOR`，因此若没有足够替代成员则 `NO_PRIMARY`；可转为 witness，不得补查搜索页。 | 把“未看到披露”偷换成“未发生行动”，以此创建错误反事实。 |
| `V5-S09-STAGE0-ACTION-LEAK` | 声称是 `STAGE0_FEASIBILITY` 的输入中把 cohort 成员预先标为 `focal_target`，或包含行动标题、实施日期、行动金额、行动影响的 carrier 或最终 peer role；单纯列出 cohort 内所有发行人 identity 并不违规。即使 cohort 五家和字段身份齐全，也违反 Stage-0 信息集。 | 拒绝该 cohort snapshot：`NO_PRIMARY / STAGE0_ACTION_CONTAMINATED`；必须用行动不可见的 Stage-0 package 重新建立。 | 先发现醒目公告，再以同业资料倒补“cohort-first”。 |
| `V5-S10-STAGE0-CAPACITY-OR-CONTROL-BREAK` | H1 可以接收五家披露成员，其中两家有 `KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK`；H1 状态为 `FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE`，但该状态不授予最终同行 panel。剩余三家仅满足“一个 target 加两名 comparator”的容量下限，仍须通过 H2 行动、scope 与 arena 验证。 | `STAGE0_FEASIBILITY_REVIEWABLE`；H2 未给出完整行动时为 `NO_PRIMARY_ACTION_SCOPE`，不能以成员数量代替行动与机制证据。 | 把 disclosure-only 成员计入最终 comparator；把 H1 可接收误当控制独立、行动可比或 V5 panel 已就绪。 |

## 5. PIT 时间、来源精度与结果窗口矩阵

每一行都必须同时检查七个时间身份：`cohort_eligibility_as_of`、`action_effective_window`、`decision_observable_at`、`research_cutoff_at`、`metric_economic_period`、`source_available_at` 与 `outcome_window_id`。

| ID | 冻结的时间 / 来源形状 | 预期准入 / 结算 | 会拦截的错误 |
|---|---|---|---|
| `V5-T01-LATE-YEAR-ACTION` | action effective 于 FY0 年末；cutoff 在 FY0 年报发布前后，但 FY0 只含很短暴露。contract 预先将 FY0 标为 `EARLY_ARROW_NON_VOTER`，把 FY1 全年设为 primary window。outcome package 同时有 FY0 与 FY1 raw fields。 | 可 `SELECTION_ADMITTED`；FY0 只能作背景，不参与中央结算；只按 FY1 得出 `A_ONLY/B_ONLY/MIXED/NOT_DIAGNOSTIC`。 | “公告已发生”便把被行动前经营主导的全年利润/OCF当结果。 |
| `V5-T02-NOT-YET-IMPLEMENTED` | cutoff 前有董事会计划、投资/CIP 或设计产能，但 action effective window 在 cutoff 后，或实施事实不能区分已执行与拟议。 | `NO_PRIMARY / ACTION_NOT_IMPLEMENTED`。 | 把计划、贷款、CIP 或管理层预测当作 D1 和未来现金暴露。 |
| `V5-T03-DATE-ONLY-SAME-DAY-PREOUTCOME` | 关键行动/控制权/bridge 原件只有发布日期，且日期与 research cutoff 同日；无可审计时分秒。 | 该原件不能作 cutoff 前事实；若不可替代则 `NO_PRIMARY`。 | 为满足 cutoff 人工补成 00:00 或 23:59 的假时间。 |
| `V5-T04-OUTCOME-SOURCE-TOO-EARLY` | 本应由 custodian 才读的 primary D3/D4 原件 `source_available_at <= cutoff`，或其内容已进入 researcher 输入。 | `EXPOSURE_EXCLUDED`，不允许 freeze 或结算；不得仅删数值后继续同案。 | 以“结果文件早已公开”合理化研究者已经看到的 outcome。 |
| `V5-T05-FISCAL-CALENDAR-BRIDGE` | target 为自然年度，peer 为 4 月至次年 3 月财政年度；outcome contract 在 freeze 前列明 12 个月经济期、对齐规则、每个 raw field 的 period 与允许 bridge。 | `SELECTION_ADMITTED`；若 raw fields 到期且同口径则按已冻结 bridge 结算。 | 事后挑较好季度、用不重叠年度或仅因刊发日相近而比较。 |
| `V5-T06-FISCAL-BRIDGE-NOT-FROZEN` | 同上，但研究者只在 outcome 后发现 fiscal year 不同，未在 measurement/outcome contract 写 bridge。 | outcome 为 `NOT_DIAGNOSTIC`，不得补建 bridge 后重算同一 freeze。 | 见到结果后调整周期以取得方向性 verdict。 |
| `V5-T07-RESTATEMENT-POLICY` | primary outcome 初始年报与之后重述年报均存在；contract 明确 `INITIAL_ONLY` 或指定可接受的同口径重述政策。custodian 故意交付另一身份。 | 输出 `BOUNDARY_CAPTURED(MEASUREMENT)`；不允许混用数字。 | 用后来重述值改写 cutoff 前/冻结后的测量面，制造假改善。 |

## 6. 缺失、冲突与单向状态机 cases

| ID | 最小输入形状 | 预期准入 / 结算 | 会拦截的错误 |
|---|---|---|---|
| `V5-M01-PREFREEZE-MISSING-BRIDGE` | action 已实施，但 measurement contract 缺 D4 所需的 OCF、长期资产现金、现金营运资本或行动现金之一；问题在 freeze 前已知。 | `NO_PRIMARY`。 | 先登记再许诺日后补字段，或让 D3 代替 D4。 |
| `V5-M02A-POSTFREEZE-MISSING-RAW-OUTCOME` | 所有门在 freeze 前通过；custodian 后来无法取得一个预登记 peer 的 primary D4 raw field。 | `UNKNOWN`；保留 frozen contract，不替换 peer、不扩展窗口。 | 将真结果采集失败伪装成 pre-freeze `NO_PRIMARY`，或事后替换同业恢复 verdict。 |
| `V5-M02B-POSTFREEZE-PERIMETER-BREAK` | 所有门在 freeze 前通过；结果期正式事实显示 peer 发生契约定义的会计/经营 perimeter 断裂。 | `BOUNDARY_CAPTURED(PANEL|SCOPE|MEASUREMENT)`；保留 frozen contract，不替换 peer、不扩展窗口。 | 将已揭示的计量边界破裂含混为“数据缺失”或事后替换同业。 |
| `V5-M03-CENTRAL-AXES-CONFLICT` | outcome raw fields可复算：D3 仅支持 H-A、D4 仅支持 H-B；二者 metric identities 都完整。 | `MIXED`，可形成无权利的 mechanism boundary，不产生方向性 learning。 | 只挑利润层胜利、或把 D3 改善写成正常 owner cash。 |
| `V5-M04-INVESTOR-MATERIALITY-UNKNOWN` | D3/D4 结算技术上完整，但公开资料不足以判断其是否改变正常 owner cash、永久损失、资本回报或黄金报告中心论点。 | 投资意义保持 `UNKNOWN`；技术 A/B 可申请独立 learning review，但不得生成行业知识、报告使用或选股结论。 | 以统计/会计改善绕过投资材料性，或把投资意义未知误判为 admission 失败。 |
| `V5-M05-MATERIAL-FREEZE-MUTATION` | pre-outcome reviewer 之后改变一个 material object：carrier、scope bridge、peer role/member、阈值、D3/D4 formula 或 primary outcome window。 | 原 `selection_freeze_id` 不可继续；生成新的候选/新的 freeze，旧 outcome access 不继承。 | 在看见或接近结果时原地 amendment、继承 outcome access。 |

## 7. Legacy、holdout 与来源隔离 cases

| ID | 最小输入形状 | 预期准入 / 结算 | 会拦截的错误 |
|---|---|---|---|
| `V5-I01-LEGACY-R104-IMPORT` | 新 V5 candidate 引用 R-104 的 outcome、peer verdict、阈值、source package 或 `MIXED` 边界作为自己的预审输入，试图把旧 case 升级为 V5 正样本。 | 拒绝 `LEGACY_REFERENCE_ONLY`；不得创建 V5 episode，不得重算或回写 R-104。 | 以旧规则和已知结果填补 V5 设计的正样本缺口。 |
| `V5-I02-R103-HOLDOUT-TOUCH` | 任一 V5 synthetic fixture、discovery/candidate input 或 reviewer packet 含 R-103 公司、时期、source id、字段、结果或 derived artifact。 | 硬拒绝 `HOLDOUT_ISOLATION_BREACH`；V5 不得读取、复制、训练或调参，R-103 继续 outcome-sealed。 | 用留出对象设计 fixture、修改规则或提前获知其结果，令以后评价失效。 |
| `V5-I03-OUTCOME-IDENTITY-LEAK` | pre-outcome packet 包含 `OUTCOME_SEALED` source id、标题、发布日期之后的元数据、数值或派生 trend；即使不含正文也算泄露。 | `EXPOSURE_EXCLUDED`；不可换研究者后沿用相同对象。 | 将“只看标题/元数据”当作无害，导致 H-A/H-B 或阈值受到结果污染。 |

## 8. 实施验收顺序

1. 先把本矩阵转成不可访问真实对象的 fixture contract；source lane、时间精度和 `outcome_visibility` 必须可被机器检查。
2. 先实现所有 `NO_PRIMARY`、`TEACHING_ONLY`、`EXPOSURE_EXCLUDED`、`UNKNOWN`、`NOT_DIAGNOSTIC`、`BOUNDARY_CAPTURED` 与 `MIXED` case，再实现正向 `SELECTION_ADMITTED` case。这样可以先证明系统不会为了取得第一条正样本而放宽边界。
3. 每个正向 fixture 均须有一个只改一个 material 条件的反例：例如市场 overlap、scope bridge、spillover、时间窗或 D4 cash bridge。不得只测试“理想输入”。
4. 只有所有 synthetic case 的 admission、freeze、outcome access 与 settlement 都符合矩阵，才可迁移一条仍 outcome-sealed 的真实 historical candidate；通过 synthetic 不授予任何真实公司、方法、R-103 或黄金报告权限。

## 9. 完成定义

V5 的实现完成不是“所有绿色测试”本身，而是每项 fixture 都能回读：其最小来源身份、何时可见、作用域/竞争场/计量关系、预期状态和明确禁止的推断。任何合成 case 若必须依赖真实公告搜索、当前市场页面、结果期标题、人工填入的 outcome verdict 或自由文本“合理解释”才能通过，说明 acquisition 或模型契约仍不完整，应退回设计而非扩展真实样本。
