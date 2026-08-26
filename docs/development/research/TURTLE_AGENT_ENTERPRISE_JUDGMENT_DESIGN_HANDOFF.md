# Turtle Agent 企业判断系统设计交接

> 状态：`HANDOFF_RECONCILED / TARGET_DESIGNS_CREATED / OFFLINE_V3_V5_SYNTHETIC_VALIDATED / ONE_H1_RECEIPT_REGISTERED / G2_PROVENANCE_IMPLEMENTED / H2_PENDING`
>
> 日期：2026-08-24
>
> 目标产物：`TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md` 与 `TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md`

## 0. 交接目的与使用边界

本文保留为交接与恢复索引。它所要求的两份顶层文档已经完成；下一位主 Agent 必须以它们和当前代码为准推进 H1 strict intake、H2 receipt 与后续真实训练，而不是重写顶层设计：

1. `TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md`：回答系统是什么、为什么这样分层、模块如何协作、状态和权利如何流动；
2. `TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md`：回答从当前真实状态到“可为黄金报告稳定服务”要按什么顺序建设，每一阶段凭什么算完成。

本文是任务交接，不是新的项目真源，也不授权修改已冻结实验、揭盲 R-103 或宣称判断力已经提升。发生冲突时，按以下顺序取真：

1. 仓库当前代码、schema、测试和 append-only 数据库记录；
2. [`GOALS.md`](../../../GOALS.md)；
3. [`CURRENT_DOCUMENTS.md`](../../CURRENT_DOCUMENTS.md)；
4. 当前设计权威与已接纳 review artifact；
5. 本交接文档；
6. Memory、旧路线图、旧 dashboard 和聊天摘要。

Memory 只用于恢复设计意图和已确认经验，不能成为训练结果、投资判断或当前状态的真源。

## 1. 北星没有改变

系统建设的唯一北星是：

```text
历史 PIT 刻意训练判断力
→ 形成可审计的方向性学习或边界知识
→ 在另一家公司结果封存时改变冻结判断
→ 用独立历史留出检验迁移
→ 通过后授权报告使用
→ 对黄金报告做同公司、同 cutoff 的 A/B
```

最终服务对象不是“多生成几份研究报告”，而是提高黄金报告之前的企业判断质量，尤其是：

- 能否辨认真正影响正常利润、owner cash 和永久损失的经营机制；
- 能否在结果未知时写出可证伪的 H-A/H-B；
- 能否区分公司能力、行业共振、周期、会计口径变化和一次性现金；
- 能否把学到的方法迁移到另一家公司，而不是复述旧案例；
- 能否让报告 Agent 只读取已获授权的判断方法、边界和研究议程。

不以股价、收益率、报告篇数、token 消耗或 Agent 共识代替企业判断能力。

## 2. 当前事实快照

| 对象 | 当前结论 | 已获得权利 | 明确未获得的权利 |
|---|---|---|---|
| R-61 | `PIT_OUTCOME_SEALED / HOLDOUT_RESERVED` | 公司轴／时间轴留出 | 仅在真实选择方法冻结后评价；不得提前读取或回写 |
| R-102 | D1/D3A/D3B=`MEASUREMENT_MISMATCH`，其余中心项为 `UNKNOWN`，联合 `NOT_DIAGNOSTIC` | `MEASUREMENT_BOUNDARY_CAPTURED` | 无方向性 learning、方法冻结、留出释放、报告使用 |
| R-104 | D3=`A_ONLY`、D4=`B_ONLY`，联合 `MIXED` | 无权利的机制边界：经营改善不自动成为 normal owner cash | 无方向性 learning、跨公司应用、方法冻结、R-103 解锁、报告使用 |
| R-103 | 当前公司轴历史留出，结果仍封存 | 未来评价冻结方法的资格 | 当前不得应用、揭盲或结算 |
| V5 Slice0/1 | 合成准入、冻结、结果重建与状态机已分别实现并有定向测试 | 可进入最终集成验收 | 尚非生产能力；未运行真实训练样本；未完成最终全套验收与独立 review |
| 黄金报告服务 | 三个只读交接视图和接纳/receipt 工程已存在 | 可消费未来获授权的方法资产 | 当前没有 selection method 可供发布；`REPORT_USE_NOT_RELEASED` |

当前必须使用的诚实表述是：

```text
TRAINING_ACTIVE
BOUNDARY_METHOD_NOT_ESTABLISHED
SELECTION_METHOD_NOT_ESTABLISHED
R103_OUTCOME_SEALED
REPORT_USE_NOT_RELEASED
```

不能宣称胜率、准确率、选股收益、判断力已经提高，或“模型已经学会选择”。R-104 有价值，但它证明的是一个边界，不是方向性能力。

## 3. 已形成的系统基础

### 3.1 十模块产品骨架

未来 `SYSTEM_DESIGN` 必须保留并清楚解释 M1–M10，而不是另起一套平行架构：

| 模块 | 责任 |
|---|---|
| M1 官方证据与 PIT 围栏 | 枚举、选择、读取和版本化 cutoff 前资料 |
| M2 企业经营系统图 | 连接客户、活动、组织、竞争、现金和资本 |
| M3 竞争机制与反方 | 形成 H-A/H-B、最强反方和断裂条件 |
| M4 公司判断与前瞻合约 | 冻结中心问题、FJ、简单基线和财务驱动桥 |
| M5 结果采集与分层结算 | 按冻结来源、窗口、口径逐层结算 |
| M6 诊断与学习应用 | failure locus、learning note、方法复盘和跨公司 receipt |
| M7 行业经验工厂 | 从已接纳案例形成带反例和边界的行业机制资产 |
| M8 宏观综合 | 从多个行业共同变量向上归纳，再按暴露向下传播 |
| M9 黄金报告编译与验收 | 读取获授权视图，生成报告、模型和独立审阅包 |
| M10 判断反馈控制面 | 登记、事件顺序、权限、reconcile、恢复和只读投影 |

关键边界：M10 不是第 11 个研究大脑。它只证明身份、时间、顺序和权限，不替代 M1–M9 的行业、公司、财务和写作判断。

### 3.2 历史训练优先，真实前瞻后置

正确的训练结构是：

```text
历史开发样本：形成问题、方法、边界和方向性 learning
历史独立留出：检验是否过拟合和是否可迁移
真实前瞻哨兵：系统成熟后的部署校准，不是训练前置条件
```

不得再因最新披露尚未到期而阻断历史训练，也不得把真实前瞻验证误写成整个飞轮的前提。

### 3.3 V5 五状态生命周期

V5 已把“寻找机会”和“正式选择 episode”拆开：

```text
COHORT_FEASIBILITY
→ CANDIDATE_DECISION_SCREEN
→ SELECTION_ADMITTED_PRE_OUTCOME
→ OUTCOME_SETTLED
→ LEARNING_TRANSFERRED
```

各状态的权利必须不可混淆：

- `COHORT_FEASIBILITY`：只证明竞争场和字段值得继续采集，不创建 episode；
- `CANDIDATE_DECISION_SCREEN`：验证真实已实施行动、责任边界和可检验机制，仍不读取结果；
- `SELECTION_ADMITTED_PRE_OUTCOME`：冻结 H-A/H-B、D3/D4、panel、时钟、阈值、来源类和 UNKNOWN 规则，才创建 selection freeze；
- `OUTCOME_SETTLED`：按冻结合同重建结果；
- `LEARNING_TRANSFERRED`：方向性 learning 被独立应用到另一家公司且改变其结果封存前的冻结字段。

`NO_PRIMARY`、`NOT_ADMITTED`、`STAGE0_REJECTED` 均不得产生 selection freeze 或结果访问权。

### 3.4 V5 机制拓扑

当前允许两种拓扑：

```text
CUSTOMER_RESPONSE_CHAIN
    D1 → D2 → D3 → D4 → D5
    D2 为中心可投票层。

COST_RESTRUCTURING_CHAIN
    D1 → cost driver → D3 → D4 → D5
    D2 只可为 DIAGNOSTIC_NON_VOTER，不能伪造客户吸收结论。
```

产品创新和资本配置机制仍需单独契约，不得为了尽快出现正样本而硬塞进上述拓扑。

### 3.5 竞争场不等于统一地理字段

V5 已纠正 V4 的重要模型错误：共同竞争经济体由机制定义，不是“同行业 + 同一省份”。

```text
competitive arena =
    可替代的产品或服务
  + 相同客户任务/终端市场
  + 相关竞争接口
  + 共同经济状态或冲击
  + 明确时间窗口
```

地理角色必须按机制声明：

- 区域性机制：实际重叠可以是硬门；
- 全国性机制：地理通常是暴露维度，不要求字符串相等；
- 出口机制：由汇率、目的地需求、关税或全球细分市场决定所需重叠；
- 多区域组合：必须预先定义子场域和暴露映射，不得事后挑选。

同时必须区分：

- `MECHANISM_MEMBER` / `EQUILIBRIUM_RESPONSE_WITNESS`：直接竞争与行动外溢的见证者；
- `EXTERNAL_SHOCK_COMPARATOR`：用于剔除共同驱动，必须证明没有同类重大处理和材料性 spillover；
- `FALSIFIER`：用于证伪机制，不自动进入相对基线。

直接竞争者不天然是未处理 control。

### 3.6 决策范围到结果范围必须有 typed bridge

局部行动不能直接嫁接集团 D3/D4。V5 仅允许三类桥：

- `IDENTITY`：行动、经济权利和完整会计边界本来就是同一发行人/责任单元；不要求伪造 100% coverage；
- `SEGMENT_MATCH`：正式、连续、同口径分部与行动载体一致；
- `QUANTIFIED_ISSUER_AGGREGATION`：以 cutoff 前来源量化覆盖率、遗漏重大项目、现金归属和结论最远范围。

“董事会层级高”“占大头”“主营单一”“集团 OCF 可取”都不能替代桥。

### 3.7 D3 与 D4 独立，D4 不能由 D3 换算

中心结算必须同时包含：

- D3：同边界的经营贡献或单位经济，使用冻结的明确公式和原始字段；
- D4：保守 owner cash，使用独立现金字段、现金营运资本构件、长期资产购建现金和已冻结的重组现金处理。

D3 通过不能补 D4 的 `UNKNOWN`，也不能以利润改善乘现金转换率生成 D4 结果。R-104 已经证明这条边界会改变结论。

### 3.8 结算状态和权限

唯一的结果决策树应写入两份目标文档：

| 结果 | 含义 | 最大权利 |
|---|---|---|
| `A_ONLY` / `B_ONLY` | D3、D4 按冻结合同给出同方向可区分结果 | 仅可进入独立 direction-learning review |
| `MIXED` | 中心机制冲突 | 形成机制边界；无方向性权利 |
| `UNKNOWN` | 必需 raw cell/source 缺失 | 记录缺口；无方向性权利 |
| `NOT_DIAGNOSTIC` | 数据齐全但时钟、判别力或比较结构不足 | 记录不可判定；无方向性权利 |
| `BOUNDARY_CAPTURED(kind)` | 结果期事实推翻 scope、metric、panel 或 mechanism 前提 | 形成相应边界；无方向性权利 |

任何结果都不自动产生方法冻结、holdout 释放或报告使用权。

## 4. V5 Slice0/1 当前实现状态

### 4.1 新增实现文件

以下 V5 Slice0/1 文件已进入当前历史分支；它们的 root 仍仅代表 offline/synthetic canonical contract，不能作为真实 H1/H2 provenance 的替代：

- `schemas/judgment_selection_admission_v5.schema.json`
- `schemas/judgment_v5_outcome_resolution.schema.json`
- `scripts/judgment_selection_v5.py`
- `scripts/judgment_selection_v5_outcome.py`
- `scripts/judgment_v5_control_plane.py`
- `tests/test_judgment_selection_v5.py`
- `tests/test_judgment_selection_v5_outcome.py`
- `tests/test_judgment_v5_control_plane.py`
- `tests/test_judgment_v5_end_to_end.py`

不要 reset、stash、checkout 或覆盖工作树；其中包含其他 Agent 和用户尚未提交的工作。

### 4.2 canonical wire contract

V5 Slice0/1 使用同一个 root bundle，禁止为 candidate、control 和 outcome 各建一套兼容形状。核心身份包括：

```text
schema_version
selection_freeze_id
episode_collision_key
sealed_at
recorded_at
time_contract.research_cutoff_at
counterfactual_panel
measurement_contracts[D3, D4]
outcome_contract.frozen_raw_matrix
outcome_contract.fiscal_calendar_bridge
```

关键约束：

- `measurement_contracts` 必须精确包含 D3 与 D4 两个中心 metric；
- D3 使用显式 `LINEAR_COMBINATION` 和有序 raw fields；
- D4 `IN_OCF` 使用冻结的 12 项；`SEPARATE_OPERATING_CASH_DEDUCTION` 还必须有第 13 项 `restructuring_cash_paid`；
- `OUT_OF_PERIMETER` 不允许作为 selection settlement；
- primary threshold operator 固定 `GTE`，rival 固定 `LTE`；阈值单位必须与 metric 单位一致；
- freeze 中只能写字段、期间、perimeter 和 locator 规则，不能提前写实际 outcome source id、标题、发布日期、数值或 metadata；
- custodian 获得授权后才登记 actual outcome source inventory 和 raw cells。

### 4.3 已知测试证据

当前已验证的 focused synthetic suite 为 `386 passed`，覆盖 discovery、selection control/feedback、training program、V5 admission、outcome、control plane 和 end-to-end；其中 E2E 覆盖两种 topology 的 `A_ONLY`、`B_ONLY`、`MIXED`、缺格 `UNKNOWN` 与 `NO_PRIMARY` 不得 seal。它证明离线 wire/state contract，不证明真实 selection capability 或报告使用权。

### 4.4 本轮已暴露的集成教训

以下经验必须进入 `SYSTEM_DESIGN` 的接口原则，而不是只留在测试历史：

1. candidate、outcome、control 各自单测全绿，仍可能使用互不兼容的 bundle；必须以同一 wire contract 做 E2E；
2. 自由文本 threshold operator 会让准入和结算语义分叉；必须使用枚举并绑定单位；
3. Stage-0、候选准入、freeze、结果授权、结算和 learning 是不同状态，不能用一个 `REVIEWABLE` 贯穿；
4. 预冻结只能锁 source class、字段和期间，不能先枚举结果期 PDF metadata；
5. 公开资料缺格应进入 `UNKNOWN` 或边界，不应通过新增代理字段、任意阈值或 prose 补洞；
6. 发现模块低召回不等于公开资料不足，更不等于需要放松正式 admission；发现与接纳必须分层。

## 5. 仍未完成的工作

下一位 Agent 不得把下列事项写成“已完成”：

1. 水泥的新 H1-only static package 已通过 preflight；旧 V4 feasibility cohort 仍被拒绝，且当前 H1 的两家 known break 不得计入 final panel；
2. 绑定已登记 H1 的 curator H2 extension；H1/H2 registry 与 V5 single-root provenance 已接线，不得用临时 V4 wrapper 或 bare V5 bundle 绕过；
3. 第一条真实、未揭盲、`SELECTION_ADMITTED_PRE_OUTCOME` 的 V5 episode；
4. 第一条真实 `A_ONLY/B_ONLY` 方向性结算；
5. 独立 post-outcome learning review；
6. 在另一家公司结果封存时改变冻结字段的跨公司应用；
7. selection method freeze；
8. R-103 的 post-freeze administrative overlay、方法应用、pre-reveal review 和结算；
9. `METHOD_RELEASED_FOR_REPORT_USE`；
10. 黄金报告同公司、同 cutoff 的 A/B；
11. 真实前瞻部署哨兵。

V5 Slice0/1 是合成能力，不是 selection capability 的证据。

## 6. 两份目标文档的分工

### 6.1 `TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md`

这是静态架构与运行语义真源。它应回答：

- 系统服务什么判断问题，明确不服务什么；
- M1–M10 的职责、输入、输出、禁止越权和数据所有权；
- 自下而上企业/行业学习如何与自上而下宏观暴露结合；
- 历史开发、历史留出、真实前瞻、报告 A/B 四条 lane 的关系；
- V5 五状态生命周期和每个状态的权利；
- 两种当前机制拓扑及未来拓扑扩展规则；
- competitive arena、external driver reference 和三种 causal role；
- typed scope bridge；
- D1–D5、normal profit、owner cash、capital return 和 permanent loss 的关系；
- D3/D4 独立计量与结果 taxonomy；
- PIT 来源围栏、custodian 授权和 outcome inventory 的时序；
- append-only 控制面、canonical read model 与 Memory 的非真源定位；
- 行业知识如何从案例候选升格，何时只能保留为边界；
- 黄金报告的三个只读视图及报告使用授权；
- V4 legacy 与 V5 新 episode 的版本边界；
- failure taxonomy：`DATA_COVERAGE / ACQUISITION_MODULE / REASONING / MODEL / WRITING`；
- 在没有公开证据时，何时用范围、`UNKNOWN`、降级或拒绝，而不是无限加门。

建议包含一张最小总图：

```text
公开官方材料 / 历史 PIT
        ↓
M1 证据围栏 → M2 企业系统图 → M3 机制与反方
        ↓
M4 V5 准入与冻结 → M5 custodian 结算
        ↓
M6 learning review / cross-company application
        ↓
历史留出 R-103
        ↓ 仅在支持后
M7/M8 获授权知识与宏观传播
        ↓
M9 黄金报告三视图与 A/B

M10 在全程管理身份、顺序、权限和恢复，但不制造研究结论
```

### 6.2 `TURTLE_AGENT_ENTERPRISE_JUDGMENT_ROADMAP.md`

这是从当前状态到可发布能力的执行路线图。它不得重复系统设计全文，也不得只写日期和任务清单。每一阶段必须包含：

- 目的；
- 前置依赖；
- 产物；
- 验收证据；
- 允许宣称什么；
- 禁止宣称什么；
- 失败后的合法去向；
- 是否解锁下一阶段。

路线图应以能力门而不是报告数量、token 或日历日期为进度。

## 7. 建议路线图阶段

### H0：V5 合成实现接纳

完成四套 V5 合并测试、legacy 回归和独立 review。修复实质接口或状态问题，不做命名/格式洁癖审计。

退出条件：同一 canonical bundle 可通过准入、seal、授权、receipt、resolve；六条 E2E 状态唯一；V3/V4 legacy 不被误伤。

### H1：真实数据入口与开发 namespace

只在开发数据库初始化 V5 namespace；建立 cutoff-before static source package 与 cohort feasibility 入口。不得覆盖主仓数据库，不得用会自动展示当前价格/公告的页面做 PIT discovery。

退出条件：至少一个 mechanism-defined cohort 有足够 target/comparator 容量、控制权独立、字段身份和 competitive arena 证据；Stage-0 仍不创建 episode。

### H2：第一条真实 V5 冻结

在 cohort 内选择已实施的公司行动，完成 typed scope bridge、H-A/H-B、D3/D4、panel、时钟、阈值和 outcome access scope，并由独立 reviewer 接纳。

退出条件：真实 `SELECTION_ADMITTED_PRE_OUTCOME`；研究端仍不知道结果 source metadata。

### H3：第一次真实结算

独立 custodian 在授权后采集结果期 official sources 和 raw cells，按冻结合同重建 D3/D4。

退出条件：唯一落入 `A_ONLY/B_ONLY/MIXED/UNKNOWN/NOT_DIAGNOSTIC/BOUNDARY_CAPTURED`。只有 A/B 可继续方向性 review；其他结果均终局但可形成边界或采集改进。

### H4：方向性 learning 与跨公司应用

独立 post-outcome reviewer 接纳 learning note；在另一家公司结果封存时，由独立 evaluator 将 learning 实际改变到冻结字段、阈值、反方、source contract 或 UNKNOWN 规则，并独立复核。

退出条件：存在不同 company/collision 的 accepted application receipt；同公司复述不算迁移。

### H5：selection method freeze candidate

根据预先冻结的 release policy 审查方向性结算和跨公司迁移。第一轮最小要求应明确为：至少一条真实 A/B、至少一次不同公司/碰撞且晚于 learning note 的 sealed migration、独立 review。

退出条件：形成版本化 method artifact、scope、freeze receipt 和独立 method review。没有这些证据不得用“规则看起来合理”冻结方法。

### H6：R-103 独立历史留出

方法冻结后再追加 R-103 的行政先决条件 overlay 和独立 review；随后由隔离 evaluator 应用冻结方法，独立 pre-reveal review，才授权 custodian 结算。

退出条件：R-103 给出独立 holdout acceptance 或明确拒绝。不得修改 sealed core，不得恢复 R-61。

### H7：报告使用授权

只有 holdout 支持且所有身份、scope、review 完整时，才允许 `METHOD_RELEASED_FOR_REPORT_USE`。

退出条件：报告层可以读取版本化 method/boundary assets，但仍不得把历史方向性结果变成收益预测或确定性投资结论。

### H8：黄金报告同 cutoff A/B

对同一家公司、同一 research cutoff 和同一证据包，比较不使用与使用获授权方法的黄金报告。盲审重点是中心论点、反方、normal profit/owner cash、永久损失和估值敏感性是否实质改善。

退出条件：独立报告 review 证明有材料改善；否则方法退回训练，不以文字更长或引用更多作为胜利。

### H9：行业知识与宏观飞轮

将多案例支持、边界清楚、可用时间明确的机制升格为行业知识；再从多个行业的共同变量归纳宏观状态，并按企业暴露向下传播。

退出条件：行业规则保留反例、适用边界、来源和版本；单个案例不得升格为通用企业规律。

### H10：真实前瞻部署哨兵

系统成熟后用少量最新披露验证部署迁移和时间稳定性。它是外部校准哨兵，不阻断历史训练主循环。

## 8. 后续 Agent 的第一组动作

按以下顺序进行，不要先找新公司：

1. 阅读本文第 11 节列出的当前真源；
2. 运行 V5 最小合并验收；
3. 运行与 V3/V4 相邻的 legacy 回归；
4. 对 V5 做一次独立、只针对材料性结论的实现 review；
5. 如发现实质问题，先修复 canonical contract/E2E，不扩展到真实样本；
6. 在实现状态被准确冻结后，起草 `SYSTEM_DESIGN`；
7. 用 `SYSTEM_DESIGN` 的能力依赖生成 `ROADMAP`；
8. 对两份文档做一次交叉一致性审阅，重点检查状态、权利、版本和报告释放门；
9. 更新 `CURRENT_DOCUMENTS.md` 的当前文档导航，但除非项目目标实际改变，不要重写 `GOALS.md`；
10. 两份文档接纳后再恢复第一条真实 V5 样本工作。

## 9. 最小验收命令

先运行四个 V5 文件的合并套件：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_judgment_selection_v5.py \
  tests/test_judgment_selection_v5_outcome.py \
  tests/test_judgment_v5_control_plane.py \
  tests/test_judgment_v5_end_to_end.py
```

通过后运行相关 legacy + V5 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_judgment_selection_discovery.py \
  tests/test_judgment_selection_control.py \
  tests/test_judgment_selection_feedback.py \
  tests/test_judgment_feedback_control.py \
  tests/test_judgment_training_program.py \
  tests/test_judgment_selection_post_outcome_review.py \
  tests/test_judgment_selection_v5.py \
  tests/test_judgment_selection_v5_outcome.py \
  tests/test_judgment_v5_control_plane.py \
  tests/test_judgment_v5_end_to_end.py
```

这些命令用于发现具体的 wire/state/legacy 失败；若失败，修复会改变系统行为。不要为了交接反复跑全仓、计算哈希或做无关身份审计。

## 10. 禁止的捷径

后续设计和路线图不得：

- 把 R-104 的 `MIXED` 写成选择方法已经成立；
- 以更多案例数量代替一条真实的方向性 settlement 和迁移 receipt；
- 因找不到首个正样本就继续增加无经济意义的硬门；
- 反过来为了出现正样本放松 PIT、scope bridge、D3/D4 独立性或独立 review；
- 把同行业自动等同共同竞争场，或把地理自动设为硬门；
- 把直接竞争对手自动作为未处理 comparator；
- 把计划、设计产能、管理层预测、项目 IRR 或公告标题当作已实施结果；
- 用集团 D3/D4 代替局部产品、厂区、项目或子公司的结果；
- 用 D3、收入、销量、利润或 cash-conversion proxy 补 D4；
- 在授权前枚举 outcome source id、标题、发布日期或当前价格；
- 用股价或未来收益结算经营判断；
- 静默修改已注册 program、sealed episode、R-103 core 或旧 rejection receipt；
- 让 Memory、聊天、旧 dashboard 或旧路线图覆盖当前仓库真源；
- 在 holdout 之前发布方法给黄金报告使用；
- 把“工程接线完成”写成“效果已验证”。

## 11. 必读顺序

下一位主 Agent 应按此顺序阅读，不要从旧 V4 文案单点恢复：

1. [`GOALS.md`](../../../GOALS.md)
2. [`CURRENT_DOCUMENTS.md`](../../CURRENT_DOCUMENTS.md)
3. [`TURTLE_GOLDEN_REPORT_SERVICE_DESIGN.md`](./TURTLE_GOLDEN_REPORT_SERVICE_DESIGN.md)
4. [`TURTLE_ENTERPRISE_JUDGMENT_TRAINING_BLUEPRINT.md`](./TURTLE_ENTERPRISE_JUDGMENT_TRAINING_BLUEPRINT.md)
5. [`TURTLE_JUDGMENT_FLYWHEEL.md`](./TURTLE_JUDGMENT_FLYWHEEL.md)
6. [`TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md`](./TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md)
7. [`TURTLE_PIT_TRAINING_PRIMITIVES_AND_ADMISSION_MODEL.md`](./TURTLE_PIT_TRAINING_PRIMITIVES_AND_ADMISSION_MODEL.md)
8. [`TURTLE_JUDGMENT_SELECTION_ADMISSION_V5_CANDIDATE_CONTRACT.md`](./TURTLE_JUDGMENT_SELECTION_ADMISSION_V5_CANDIDATE_CONTRACT.md)
9. [`TURTLE_JUDGMENT_SELECTION_ADMISSION_V5_SYNTHETIC_ACCEPTANCE_MATRIX.md`](./TURTLE_JUDGMENT_SELECTION_ADMISSION_V5_SYNTHETIC_ACCEPTANCE_MATRIX.md)
10. [`TURTLE_V5_MINIMAL_IMPLEMENTATION_WORK_PACKAGE.md`](./TURTLE_V5_MINIMAL_IMPLEMENTATION_WORK_PACKAGE.md)
11. [`TURTLE_V5_CONTROL_PLANE_MIGRATION_DESIGN.md`](./TURTLE_V5_CONTROL_PLANE_MIGRATION_DESIGN.md)（仅按其当前 frontmatter 读取；Slice0/1 被 work package 替代的旧章节不得重新实施）
12. V5 schema、实现和四个测试文件
13. R-102、R-104、R-103 的 canonical experiment/control artifacts

如果旧蓝图或 V4 协议仍写“下一条使用 V3/V4”，应在新设计中明确其历史地位和 V5 replacement，不要把两套当前语义混写。

## 12. 两份目标文档的共同验收问题

只有以下问题都能得到唯一、相互一致的答案，设计才算完成：

1. 现在系统处在哪个能力等级，为什么不是更高一级？
2. 什么状态可以创建 selection freeze，什么状态绝不能？
3. 谁可以在何时读取 outcome source metadata？
4. 客户响应和成本重构为何对 D2 要求不同？
5. 全国性家电、区域水泥和出口制造如何定义各自竞争场？
6. 直接竞争者何时只是 witness，何时可以进入 external-shock baseline？
7. 局部行动如何合法映射到发行人或分部 D3/D4？
8. D3 和 D4 冲突、缺格、不可比较或口径破裂分别落入什么唯一状态？
9. 一条 A/B 结果为什么仍不能冻结方法？
10. 跨公司迁移必须改变什么可审计对象才算发生？
11. R-103 在什么精确前置条件下才能解封？
12. 什么事件才授予黄金报告使用权？
13. 黄金报告 A/B 如何证明是判断质量改善，而不是篇幅、文风或引用数量变化？
14. 行业规则如何升格，如何保留反例、边界和可用时间？
15. 真实前瞻为何是最后的部署哨兵，而不是历史训练的阻断条件？

## 13. 交接结论

当前不是“第一条链路已经跑通”，也不是“一条不归路”。已经完成的是：把此前混在一起的发现、准入、冻结、结果访问、结算和 learning 权利拆开；完成 V3/V5 离线控制、strict H1 intake 与 H2 closed-extension synthetic contract，并将 V4 的所有 pre-outcome 引文（含 target/peer raw D3/D4、现金桥、control 和 comparability）闭合到 H1∪H2 static-PDF map，同时逐页绑定 H2 行动/事实/D2/cost screen 与价格行动字段 identity。水泥的新 H1-only static package 已通过 preflight 并登记 immutable receipt；它不恢复旧 V4 cohort，且两家 known break 使该固定 cohort 不足最终 panel。尚未完成的是：接收其 H2/`NO_PRIMARY` boundary 或容量合格新 cohort 的真实历史 PIT 样本，形成方向性结果、迁移到另一家公司、通过 R-103，并证明它确实改善黄金报告。

下一位 Agent 的任务不是直接扩大案例枚举或搜索行动。当前 H1/H2 receipt/provenance 已完成 H1 实例登记；下一输入是 curator 提交绑定当前 H1 receipt 的 H2 extension。水泥包可产生严格 H2/`NO_PRIMARY` 边界，但若要进入真实 V5 selection，必须另有容量合格的 H1 cohort。此后所有真实训练工作都必须按总设计与路线图进入同一条可审计链路。
