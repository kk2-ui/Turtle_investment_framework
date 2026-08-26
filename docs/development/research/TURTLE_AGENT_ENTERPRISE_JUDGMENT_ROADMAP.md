# Turtle Agent 企业判断系统路线图

> 状态：`TOP_LEVEL_DECISION_ARCHITECTURE_ADOPTED / PIT_FORECAST_LEARNING_CONTROL_IMPLEMENTED / REGISTRY_AWARE_ADMISSION_IMPLEMENTED / REAL_H1_CARRIER_REGISTRY_OPEN / CEMENT_H2_NO_PRIMARY_ACTION_SCOPE`
>
> 日期：2026-08-26
>
> 配套设计：[训练系统顶层架构](./TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md)、[Turtle Agent 企业判断系统总设计](./TURTLE_AGENT_ENTERPRISE_JUDGMENT_SYSTEM_DESIGN.md)、[历史训练体系重构](./TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md)

## 1. 路线图的唯一目的

这条路线服务一个中心目标：让 Agent 更好地辅助用户判断企业经营质量、管理决策的长期经济影响，并在公司判断冻结后，给出更可靠的正常利润、价值、预期回报和买入价格输入。

路线图不以“尽快产生第一个样本”为唯一进度指标。第一个正式方向性样本当然重要，但如果为它临时改变共同市场、公告、责任边界或结果口径，系统会得到一个无法迁移的样本，反而离中心目标更远。

路线图采用一个以 `Decision Contract -> CJO -> Investment Overlay` 为中心的持续判断底座、一个行业生命周期底仓、一条日常预测校准主链和一条低频因果高级 lane。Forecast 改善方法，不能替代 CJO 或成为产品中心：

```text
持续判断底座：EnterpriseSystemModel -> ManagementDecisionLedger -> Frozen CJO
行业历史底仓：Industry History Universe -> Lifecycle Ledger -> Research Agenda
教学/边界路径：Evidence Carriers -> Teaching/Lifecycle Case -> Boundary Assets
预测校准主链：PIT Company State Forecast -> Relative Trajectory Tournament -> Forecast Settlement
                                                        |
                                                        v
                              Error Attribution -> limited Forecast Policy -> Prequential Feedback
正式因果路径：Causal Action Comparative Episode -> Learning Transfer -> Method Freeze -> R-103 Holdout
                                                        |
                                                        v
                                       Frozen CJO -> Quantitative Investment Track
                                                        |
                                                        v
                                               Golden Report -> Forward Calibration
```

行业史、教学/边界和正式选择可以并行；Comparator 不足只阻断相对因果主张，不删除行业史、已消失公司或单案训练。低权限对象也不能冒充正式选择完成。

## 2. 当前起点（2026-08-25）

当前必须以已验收的离线控制事实为准：

- V3 control plane 已实现企业系统/责任单元/arena、状态权限、局部 delta、scope bridge、TransportContract 和 CJO-to-BuyBand synthetic propagation；
- V5 已实现 canonical selection bundle 的 admission、独立 pre-outcome review、seal、custodian-only outcome receipt 与 derived resolution；
- 正式 PIT 只接受独立 curator 交付的、预先声明 cutoff 前的 offline static CNINFO PDF package；Agent 不得通过 CNINFO UI、全文检索或 issuer/detail 页面补查候选、行动或结果；
- 新水泥 H1 static package 已通过 strict preflight 并登记 `STAGE0_FEASIBILITY_REVIEWABLE`：五家公司和 25 份 static PDF 可作 risk set/evidence carriers；三家为 pending，两家有 scope/control break；独立 curator 对既有 H1 PDF 返回 `H2_NO_PRIMARY_ACTION_SCOPE`，只暂停 causal lane；
- 旧设计已确认存在上层建模错误：H1 receipt、公司 roster、行业宇宙和最终 comparator panel 被错误绑成同一个关闭对象；新分层、registry-aware epoch 与 industry-history runner 已实现，真实 comparative admission 仍须等待 H2；
- `R-104 = MIXED` 仅可作边界学习；方向性训练样本仍为 `0`，方法冻结、`R-103` 留出、生产 canonical CJO 绑定和黄金报告使用授权均未开始。

因此当前不是“全系统停摆”，而是：

```text
行业史/生命周期：schema、validator、carrier-control 与 multi-cutoff runner 已实现；水泥 H1 已生成 six-cutoff history series，退出/删失只由 synthetic lifecycle 回归验证，未对真实公司推断 lifecycle 结论
机制/边界设计：已有资产可继续运行
企业整体模型/管理层纵向账本：离线控制与 synthetic fixture 已实现，尚未成为生产 canonical truth
正式 PIT 入口：已有一个水泥 H1 receipt、五 carrier 的隔离开发 registry、claim-specific/carrier-registry control foundation 和 registry-aware comparative epoch；等待 curator H2 action screen
跨公司迁移：契约与 synthetic 反例已实现，真实迁移尚未证明
方法冻结：未开始
定量买点接线：离线 directionality 已验收；生产授权仍要求 canonical 冻结 CJO 与 D4 闭合
```

### 2.1 当前执行顺序：H0–H10

H0–H10 是本仓当前执行状态；下方 G0–G8 只保留能力依赖视图，不能覆盖本表。

| 阶段 | 当前状态 | 下一退出事实 |
|---|---|---|
| H0 合成控制接纳 | `COMPLETE` | V3/V5 offline control 与 legacy 回归已通过 |
| H1 Industry History Universe | `MULTI_CUTOFF_RUNNER_IMPLEMENTED / CEMENT_H1_SIX_CUTOFF_SERIES_VALIDATED / SYNTHETIC_LIFECYCLE_VALIDATED` | 后续真实 lifecycle 事实须由独立 cutoff-visible source receipt 接入；不阻断 H2 |
| H2 Teaching/Lifecycle runner | `LIFECYCLE_TEACHING_SYNTHETIC_ACCEPTED / R104_BOUNDARY_TEACHING_PROJECTED / REAL_HUAXIN_PERIMETER_CASE_ACCEPTED` | 单公司和消失公司可训练，且不会获得选择权限 |
| H2A PIT Company Forecast | `CEMENT_2018_FIVE_COMPANY_FORECAST_FROZEN / THREE_COMPANY_REFERENCE_TOURNAMENT_FROZEN / MINIMAL_HISTORICAL_EPISODE_CN600585_MECHANICALLY_SETTLED / CN600802_MINIMAL_EPISODE_MEASUREMENT_MISMATCH / FORECAST_LEARNING_CONTROL_IMPLEMENTED / R05_PROSPECTIVE_SIGNAL_SHADOW_REGISTERED` | 历史 pilot 只作 `MODEL_MEMORY_MITIGATED` 流程/反馈验证；独立 custodian 才能结算。另一个单公司、单指标 Minimal Episode 已证明 contract→blind observation→mechanical settlement 管线，CN:600802 的同类对象则因结果期官方静态来源未能唯一页级映射而无标签；二者均无 learning 或方法权利。结算可直接改校准/coverage/状态定义/不确定性 policy；证据与反方方法仍仅为 pair+holdout candidate，且不读 H2/R-103/outcome |
| H3 Comparative intake | `ONE_CEMENT_H1_RECEIPT / REAL_H1_CARRIER_REGISTRY_OPEN / REGISTRY_AWARE_ADMISSION_IMPLEMENTED / H2_NO_PRIMARY_ACTION_SCOPE` | 等待另一条合格 H2 action screen 后，冻结 predicate 与静态 peer batch |
| H4 第一条真实 Comparative Episode | `NOT_STARTED / NOT_GLOBAL_BLOCKER` | final panel、行动、反方和 outcome contract 独立冻结 |
| H5 第一次真实结算与 learning | `NOT_STARTED` | 方向性结算改变不同公司冻结前字段 |
| H6 方法冻结与 R-103 留出 | `LOCKED` | H5 后的隔离 evaluator 结算 |
| H7 报告使用授权 | `LOCKED` | holdout 与身份、范围、审阅完整 |
| H8 同 cutoff 黄金报告 A/B | `LOCKED` | 获授权方法带来材料性判断改善 |
| H9 定量买点评价 | `DESIGN_ONLY` | 经营兑现、价值和价格分层的预注册评价 |
| H10 真实前瞻部署哨兵 | `FUTURE` | 历史主循环成熟后的外部校准 |

## 3. 总体阶段表

| 阶段 | 名称 | 目标 | 当前状态 | 依赖 |
|---|---|---|---|---|
| `G0` | `ARCHITECTURE_FREEZE` | 冻结中心目标、企业持续对象、研究控制、lane 和权限 | `LAYERED_DESIGN_COMPLETE / CONTROL_IMPLEMENTED` | 无 |
| `G1` | `TRAINING_LANES` | 让 Industry Universe、生命周期、教学、边界、PIT forecast 和 causal PIT 分轨运行 | `FORECAST_EPOCH_IMPLEMENTING / REGISTRY_AWARE_ADMISSION_IMPLEMENTED / CEMENT_H2_NO_PRIMARY_ACTION_SCOPE` | G0 |
| `G2` | `PIT_EPISODE_ENGINE` | 把 claim-specific admission、carrier registry、arena、scope 和静态来源包接到 Comparative 入口 | `REGISTRY_EPOCH_SYNTHETIC_ACCEPTED / REAL_H1_CARRIER_REGISTRY_OPEN / REAL_H2_INTAKE_NOT_STARTED` | G0；可与 G1 并行 |
| `G3` | `FIRST_DIRECTIONAL_EPISODE` | 取得第一条真实 `A_ONLY/B_ONLY/SELECTIVE_SUPPORT` Comparative Episode | `NOT_STARTED / NOT_GLOBAL_BLOCKER` | G1、G2 |
| `G4` | `CROSS_COMPANY_TRANSFER` | 用 TransportContract 证明 learning 改变另一家公司冻结前研究字段 | `NOT_STARTED` | 至少一条合格训练结果 |
| `G5` | `R103_HOLDOUT` | 冻结方法后揭盲 `R-103`，评价未见对象泛化 | `LOCKED` | G4、方法冻结 |
| `G6` | `CJO_TO_QUANT` | 将冻结公司判断传到价格隐含要求、价值、回报和条件化买点 | `SYNTHETIC_VALIDATED / PRODUCTION_PENDING` | canonical frozen CJO；可用 fixture 提前开发 |
| `G7` | `GOLDEN_REPORT` | 生成完整黄金报告并独立验收 | `NOT_AUTHORIZED` | G6、报告质量门 |
| `G8` | `FORWARD_CALIBRATION` | 以少量未知结果哨兵校准部署纪律 | `FUTURE` | G5、G7 |

## 4. 阶段设计

### G0 `ARCHITECTURE_FREEZE`

**目标**：在继续取证前，冻结“企业作为怎样的持续系统、什么是管理层质量、什么是训练样本、怎样区分解释、什么可以跨公司迁移、买点怎样消费企业判断”。

**必须产出**：

- 企业判断系统总设计；
- `EnterpriseSystemModel`、`ManagementDecisionLedger`、`ResponsibilityUnit`、`CompetitiveArena`、`DecisionEpisode`、`LearningTransfer` 定义；
- `HypothesisRegistry`、diagnostic matrix、`TransportContract`、`ExpectationGap` 和 `BuyBand` 契约；
- `UNKNOWN`、`NO_PRIMARY`、`MIXED`、`SELECTIVE_SUPPORT`、`A_ONLY`、`B_ONLY`、`NOT_DIAGNOSTIC` 和 `PIT_BLOCKED` 权限；
- 训练 lane 与生产 CJO/投资轨的边界；
- 现有 V5/PIT、Golden Report、历史训练和反馈控制面之间的映射表；
- 阻断处理规则：发现重复阻断时先定位 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL` 或 `WRITING` 根因。

**允许**：离线设计、现有文档交叉检查、合成 fixture 和边界案例整理。

**禁止**：继续用真实候选探索来决定顶层字段；为某一个公司添加专用门；修改主仓协调状态以宣称新阶段已完成。

**退出标准**：另一位实现 Agent 可以据此说明企业持续状态、管理层纵向判断、训练变化单位、市场边界、证据鉴别、正式 PIT 门、迁移条件和买点输入，不需要通过实际案例补齐定义；设计中不存在“上一层门是下一层门理由”的循环。

**当前状态**：离线架构和 synthetic fixture 已实现并进入当前文档体系；这不自动授予真实 PIT、canonical CJO 或报告使用权限。

### G1 `TRAINING_LANES`

**目标**：先让系统有持续可运行的训练活动，不把所有训练压在第一条昂贵的方向性样本上。

**实施包**：

1. `Industry History Lab`：按 company-time risk set 建行业结构、进入退出和覆盖边界，不只保留幸存者；
2. `Lifecycle Lab`：分开收购、合并/perimeter 转移、退市但经营、失败、业务退出和资料删失；
3. `Enterprise Model Lab`：用年报和已知案例建立 material stocks、flows、瓶颈、反馈、再投资和普通股传播；
4. `Management Decision Lab`：按当时信息复盘决策质量、执行、外部冲击和结果，不用 outcome 倒推；
5. `Mechanism Lab`：结果已知案例、合成 fixture、动作—客户—单位经济—现金箭头；
6. `Boundary Learning`：范围错配、共同冲击、D3/D4 分化、`MIXED` 和 `NO_PRIMARY`；
7. `Historical Teaching`：生成问题、near miss、禁止替代和测量边界，不生成方法成绩；
8. `PIT Selection`：接收 G2 产生的正式 Comparative candidate；
9. `Live Sentinel`：只建立未知结果的到期时钟，不阻断历史训练；
10. `Research Policy`：按材料性、当前不确定性、鉴别能力、决策影响和取证成本选择下一步。

**允许**：使用 R-104 的 `MIXED` 结果做边界学习；把已消失公司纳入行业史和 Lifecycle/Teaching Case；用已知结果验证系统是否会拒绝错误解释；修复通用的采集器、schema、结果合同和 reviewer 工具。

**禁止**：把 R-104 算作方向性样本；把案例数、通过数或学习笔记数汇总成胜率；在不同 lane 之间复用结果权限。

**退出标准**：Industry Universe 不因成员退出或 comparator 不足而删除对象；每个 lane 都能产生自己的状态和工件；同一输入在 `TEACHING`、`LIFECYCLE`、`BOUNDARY` 和 `PIT` 下不会获得相同权限；episode 能局部更新 EnterpriseSystemModel，管理层账本能分开 decision/execution/outcome；系统能明确说明“为什么不能进入正式样本，以及降级后仍能做什么”。

**并行性**：G1 可以与 G2 的离线入口实现并行，不需要等待第一个正式样本。

### G2 `PIT_EPISODE_ENGINE`

**目标**：在 Industry History Universe 与 Evidence Carrier Registry 已建立竞争范围和覆盖边界后，对 `RELATIVE_CAUSAL` 主张冻结具体决策的生产入口，并把证据、机制和投资传播接到同一组 typed artifact 上。

**入口顺序**：

```text
1. 从 Industry History Universe 选择本轮 `claim_class=RELATIVE_CAUSAL` 与 competitive arena
2. 接收一个或多个不可变 SourcePacketReceipt，并按预声明规则追加到 Evidence Carrier Registry
3. 冻结 EnterpriseSystemModel@t0 的 material state 与本次 intended delta
4. 拆分 accounting / decision / economic carrier / measurement scope
5. 确认已实施的经营决策，并写入当时信息下的 ManagementDecisionLedger
6. 登记多项竞争/共同假设及各自 expected/contradictory observations
7. 冻结 comparator eligibility predicate，再按角色枚举 comparator / context peer / mechanism witness / falsifier
8. 选择机制 topology 和各层结果字段
9. 建立 EvidenceGraph、MechanismGraph 和 InvestmentGraph 的节点/边身份
10. 在 panel freeze 前闭合官方 static PDF map，覆盖 action/D2/cost 以及 target/peer raw D3/D4、control、comparability、cash bridge 和 materiality 的所有 pre-outcome 引文
11. 按 target-trial 约束登记 time zero、intervention、comparator、outcomes、follow-up、censoring、co-intervention 和 interference
12. 冻结最终 target、comparators、排除、顺序、hypothesis-evidence matrix、反方、结果期和结算谓词
13. 通过独立 admission 后关闭 carrier registry，才允许进入结果读取
```

**实现边界**：

- 地理只有在它确实承载竞争机制时才作为硬门；
- `industry_id` 只作路由标签；
- 固定公司数不作用于 Industry Universe 或 Teaching/Lifecycle Case；V5 的 panel 容量仍只在该 topology 上生效；
- 计划、预测、设计产能、动态检索和截止日后页面不提供 PIT 事实；
- 不要求所有 topology 都有相同的 D2；但所有进入正式方向性样本的成员必须满足该 topology 所需的 D3/D4 结算合同；
- D3 经营改善不能替代 D4 owner cash。
- 证据条数和来源数量不参与投票；只有相对竞争假设具有鉴别力的观察才能推动选择；
- episode 结算只更新预登记的 EnterpriseSystemModel 节点和 ManagementDecisionLedger outcome overlay。

**退出标准**：用合成和拒绝 fixture 证明入口能拒绝未来信息泄露、地理误配、责任边界错配、D3/D4 混淆和结果期错位；至少能生成一个 `PIT_BLOCKED` 或 `NO_PRIMARY` 的完整返回，而不需要手工补丁。

**当前实现缺口**：水泥 H1 static package 已登记 immutable receipt，五家公司都可作 universe/carrier seed；两家 `KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK` 只是不具当前 comparator 权限，三家 pending 可进入 H2。现有代码把 H1 roster 提前关闭，无法在 H2 action 出现后按冻结 eligibility predicate 追加整批 peers。这是 `ACQUISITION_MODULE + MODEL` 缺口，不是水泥行业没有训练价值。迁移前继续服从旧 validator；迁移后允许独立 curator 在 outcome 读取和 Comparative Panel Freeze 前追加 static peer-recruitment batch，仍禁止动态页面、自由挑选、结果后补源和把 break 成员放回 panel。

### G3 `FIRST_DIRECTIONAL_EPISODE`

**目标**：取得第一条真正的方向性训练样本，验证一次局部状态变化的研究闭环，但不把它扩大成整家公司或管理层质量结论。

**正确筛选方式（仅在已登记 Evidence Carrier Registry 内）**：

- 先按机制定义局部共同市场或竞争经济体，而不是先按行政区筛公司；
- 先做行业/公司 × cutoff 的 pre-outcome 面板，再从已实施的公司整体经营决策中定位 episode；
- 让成员包含共同冲击参照、近失效和真正的 falsifier，而不是只选资料最多的成功者；
- 冻结 episode 前后的企业状态 delta，而不是只登记一组结果字段；
- 用 diagnostic matrix 检查证据是否真的区分假设，而不是累计支持材料；
- 只有预登记的静态官方 PDF 包能进入 PIT 选择判断；
- 结果期和 D3/D4 结算合同在结果揭示前冻结；
- claim、observation、inference、mechanism edge 和 investment propagation 不能由 writer 自由连接。

**成功定义**：得到一条 `A_ONLY`、`B_ONLY` 或通用 `SELECTIVE_SUPPORT`，并且 enterprise pre-state/delta、责任边界、arena、动作、假设、鉴别证据、来源、结果期、反方、测量合同和独立审阅均闭合。

**失败定义**：资料不足、范围不闭合、结果不诊断或只能得到 `MIXED`。失败时按已有证据降级为 Teaching/Lifecycle/Boundary 对象，保留行业史和诊断价值，转回 G1/G2；禁止把候选叙事改造成通过样本。

**当前状态**：方向性样本为 0；R-104 为 `MIXED`，不能作为 G3 完成证据。

### G4 `CROSS_COMPANY_TRANSFER`

**目标**：把第一条训练结果转成另一家公司的研究行为变化。

**传递对象只能是窄改变**：

- arena 的一项维度要求；
- responsibility unit 的一座 scope bridge；
- 一个被禁止的代理指标；
- 一个新的 D3/D4 结果合同；
- 一个 hypothesis 分叉、共同机制或反方；
- 一条停止规则或来源获取顺序。

每次迁移先写 `TransportContract`：`source_structure / invariants / target_differences / moderators / required_target_observations / break_conditions / permitted_change`。不要把一整篇事后结论复制给下一家公司，也不要因行业、规模或地理相似直接迁移。

**退出标准**：下一家不同公司在结果揭示前取得 contract 要求的目标事实，并确实出现可核查的字段或研究流程改变；独立 reviewer 能说明哪些关系可迁移、哪些差异限制迁移以及改变为何对应上一轮经济失败；下一案仍保留其自身 `UNKNOWN`。

### G5 `R103_HOLDOUT`

**目标**：方法冻结后揭盲 `R-103`，评价冻结方法是否能迁移到未参与方法形成的公司/时期。

**顺序**：

```text
G4 transfer receipt 接纳
  -> 冻结 method version
  -> 封存方法和规则
  -> 打开 R-103 cutoff packet
  -> 独立运行 CJO/PIT 入口
  -> 读取结果并机械结算
  -> 只生成 evaluation report
```

**禁止**：看见 R-103 结果后修改方法再称为 holdout；把结果已知教学案例、价格回报或样本筛除计入留出成绩；用一个留出样本宣称一般性能力。

**退出标准**：R-103 的样本身份、方法版本、来源包、结果包和审阅工件均可追溯，并给出“支持、失败或不可判定”的有限结论。

### G6 `CJO_TO_QUANT`

**目标**：让公司判断真正改善后续定量买点，而不是让估值模块自行生成一个脱离经营机制的价格。

**生产接口**：

```text
FROZEN_CJO
  -> driver register
  -> normalized earnings contract
  -> owner cash / FCFF bridge
  -> capital allocation and access bridge
  -> valuation route selection
  -> price-implied operating requirements
  -> expectation gap against CJO ranges
  -> 3/5-year return distribution
  -> conditional BuyBand / position rule / reversal condition
```

**实施要求**：

- 先用 fixture 做 adapter 和传播测试，可以与 G3/G4 并行；
- 生产计算必须读取冻结 CJO，不能读取未审阅的研究草稿；
- 每个决定性经营驱动要么传播到正常利润和普通股现金，要么显式标为尚未进入估值；
- 现金、少数股东、债务、资本开支、营运资本、法律归属和母公司可分配能力分开；
- 价值身份不机械平均；固定终值回报与候选价格重新进入价格函数的路径分开命名；
- 反解当前价格要求的收入、利润率、再投资和竞争优势持续期，并明确 reverse valuation 的多解性；
- 分开企业经营不确定性、普通股生存/可达性、估值身份和市场价格波动；
- 买点输出是满足回报和永久损失约束的条件化区间，不是单点目标价；
- 估值结果改变企业判断时，只能生成新的研究问题，不能静默覆盖 CJO。

**退出标准**：对经营驱动做方向性扰动时，正常利润、owner cash、价格隐含要求、预期差、价值、回报和 BuyBand 按经济方向变化；无法唯一反解时输出 `EXPECTATION_GAP_UNKNOWN`；CJO 未冻结时生产买点接口关闭。

已增加闭合的 synthetic `CJOValuationReturnSnapshot` 与 `CJOValuationReturnSettlement`：snapshot 只接受 frozen `INVESTMENT_INPUT` CJO 和 finite-horizon financial contract；settlement 分开对照 operating normal earnings、owner cash、owner-cash valuation identity、永久损失与逐年现金流市场 IRR，并拒绝 early source、混合缺失 outcome 或非独立 custodian。它的唯一 learning authorization 是 `CANDIDATE_ONLY`，不能改写 CJO、成为 report/portfolio action，亦未读取任何真实 outcome；production canonical overlay 仍须在独立工作包实现。

### G7 `GOLDEN_REPORT`

**目标**：生成可直接用于企业判断和投资审阅的完整黄金报告。

黄金报告的定位是交付层和回归对象，不是训练正确答案。它必须同时包含：

- 公司经营系统和关键机制；
- 责任边界、竞争 arena 和 `UNKNOWN`；
- 管理层纵向决策质量、执行、外部冲击、资本配置和普通股索取权；
- competing hypotheses、区分性证据和仍未排除的解释；
- 正常利润、owner cash、资产/盈利/回报等适用价值视角；
- 当前价格隐含经营要求、预期差、条件化 BuyBand、3/5 年回报、永久损失路径和翻转条件；
- CJO 到定量结果的单向传播证据；
- 独立内容、数字、边界和冷读审阅。

**禁止**：用报告篇幅、工程状态码或模型数量制造质量；用报告正文反推事实或模型；把黄金报告改成每个行业同一模板的填空题。

**退出标准**：完整报告在读者层可读，在技术层可复算，且企业判断与定量买点的连接能被独立 reviewer 复核；报告生成不改变 CJO。

### G8 `FORWARD_CALIBRATION`

**目标**：在历史训练和留出之后，用少量最新、结果未知的真实哨兵验证部署纪律。

**允许**：冻结新的实时 CJO、记录待验证判断、到期后按原契约收集结果、标记未知和口径断裂。

**禁止**：等待外部披露时暂停历史训练；把单次前瞻结果写成准确率；在结果揭示前改变假设或价格；自动调仓或自动交易。

**退出标准**：多个真实哨兵在同一定义下完成结果采集，能够区分采集失败、测量不诊断、机制失败和投资回报偏离；系统只在有足够独立结果后讨论有限校准，不宣称普遍投资优势。

## 5. 依赖与并行安排

```text
G0
 |
 +--> G1 训练 lane 与教学/边界 fixture
 |
 +--> G2 PIT 入口、scope bridge、arena、静态 source package
          |
          +--> G3 第一条方向性 episode
                         |
                         +--> G4 跨公司迁移
                                      |
                                      +--> G5 方法冻结与 R-103 留出

G0 + fixture ----------------------------------> G6 CJO -> quant adapter
                                                   |
                                                   +--> G7 Golden Report

G5 + G7 ---------------------------------------> G8 Forward Calibration
```

可以并行做的工作：

- G1 的机制实验和边界教学；
- G2 的离线入口、拒绝 fixture、静态来源包读取；
- G6 的 fixture 传播、估值接口和回报扰动测试；
- G7 的报告消费契约和渲染层整理。

不能提前做的工作：

- G3 未完成时，不把任意 `MIXED` 升为方向性样本；
- G4 未完成时，不冻结方法；
- G5 未完成时，不把 R-103 称为留出结果；
- CJO 未冻结时，不输出生产买点；
- G7 未完成时，不把某个报告称为黄金训练标准；
- G8 未完成时，不以历史回放冒充真实前瞻校准。

## 6. 交付给实现 Agent 的工作包

### WP-R0 分层历史训练迁移

先实施[历史训练体系重构](TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md)的 WP-R1--R4：增加 IndustryHistoryUniverseSnapshot、LifecycleEvent、EvidenceCarrierRegistry、`claim_class/object_class/allowed_outputs`；移除非比较对象上的全局固定公司数量门；保留 V5 topology-specific target/peer/D3/D4 门；实现 Comparative freeze 前按 eligibility predicate 追加 static batch、freeze 后关闭。水泥 H1 receipt 原样保留并投影为 universe/carrier seed，R-62/R-69/R-102/R-104 不追溯升级，R-103 继续 sealed。

WP-R0 的离线控制基础和 registry-aware comparative epoch 已完成 synthetic 验收；legacy H1/H2 validator 继续 roster-closed，只有 registry epoch 的新 seal 入口可消费持久化 H1/H2、冻结 predicate、immutable static batch、完整 disposition ledger 和独立 review。水泥 H1 receipt 已登记且 registry 为 `OPEN`；causal lane 的下一原子工作包仍是独立 curator H2 action screen，随后才可冻结 predicate 与 peer recruitment。它不阻断 forecast 主链。

### WP-F0 PIT Company Forecast epoch

实现 `PITCompanyStateForecast`、`RelativeTrajectoryTournament`、`ForecastSettlement` 与 `ProspectiveShadowEpisode` 的 closed schema、纯 validator 和隔离 control-plane namespace。每个 forecast 只可消费同一 `company × cutoff` risk-set/H1 static PDF 证据，冻结 1/3/5 年六维概率；`EVIDENCE_INELIGIBLE` 记录 coverage 而不伪造预测，`MODEL_UNCERTAIN` 必须给 ordered-state 的完整分布或可结算 binary-event 概率。tournament 逐维排序，不构造总冠军或因果 control；只有具有冻结 Outcome Measurement Contract 的 V3 forecast 才可由独立 custodian 逐维产生 Brier/RPS、coverage 与错误归因，禁止综合 0--100 分、因果、CJO、report 和 investment 权限。`ForecastErrorAttribution` 可在独立 challenger 审阅后直接形成 calibration/coverage/state-definition/uncertainty/baseline-performance policy；evidence priority 与 rival-hypothesis method 必须经 outcome 前 pairing、逐 cell ablation 和公司+时间 holdout，且只能留在 candidate。已结算事实只能在真实公开时间不晚于下一 cutoff 时进入 prequential feedback；holdout 必须按公司与时间双轴切分。首个水泥 pilot 只使用现有 H1 risk set，必须标记 `MODEL_MEMORY_MITIGATED`，不读取 H2、R-103、价格或 outcome。

该工作包保留了首轮 `Forecast V1` 的 `MODEL_MEMORY_MITIGATED` 流程验证，并已在同一隔离 namespace 创建新的 contract-first `Forecast V2`：五份 Decision Contract 先冻结并精确绑定已登记 H1 static receipt，随后冻结五家公司 forecast 和一份三家 pending 的逐维 reference tournament；两家 lifecycle/boundary 公司只保留 coverage gaps。V1 未被改写。V2 的独立 custodian 已按先授权、后来源的顺序写入五份 immutable access authorization 和五份 settlement；结果为 48 个冻结的 `EVIDENCE_INELIGIBLE` 与 42 个 `MEASUREMENT_MISMATCH`，没有 `OBSERVED`、评分、模型胜负或投资输出。这证明公开年报可取得不等于可结算：V2 没有 custodian 可单独读取的、将责任边界/期间/单位/字段映射到标签的 Measurement Contract，因而不得回填。

下一轮使用新的 `Forecast V3`。它在 `Decision Contract → Outcome Measurement Contract → Forecast → outcome-access authorization → custodian observation receipt → settlement` 顺序中运行：Measurement Contract 在 forecast 前冻结每个 `dimension × 1/3/5 年` 的责任边界、期间、单位、官方年报字段身份、阈值/二元标签映射和 mismatch 规则；V3 forecast 必须精确引用它及当时已生效的 direct forecast policy。V3 custodian 不读取概率、理由或排名，只凭该 contract 与分页官方披露写入 immutable observation receipt；`OBSERVED` receipt 固定原始字段和值，`MEASUREMENT_MISMATCH` receipt 固定来源页和合同内的 mismatch rule，settlement 只能引用其一，control plane 才确定性推导标签。字段、单位、period、contract、source-field 或阈值不匹配一律不得成为 `OBSERVED`。V1/V2 绝不允许事后补绑该合同、产生 `OBSERVED` 分数或投影 active policy；既有 V2 settlement/attribution 仅保留为不可变 coverage 审计事实。

`Forecast V4` 是另一个新 epoch，而非对 V1--V3 的 retrofit：在 forecast 前，独立 curator 只能从同一已登记 H1 static-PDF packet 提交 closed、逐字段、逐页的 cutoff-visible extraction；control plane 将它编译并冻结为 evidence-only receipt。H1 仍是唯一 artifact allowlist，不得新增 PDF 或动态来源；receipt 的页码把既有官方 PDF 的具体原始字段、单位、责任边界和数值固定下来，但不授予 outcome、CJO、价格、报告或投资权限。V4 的每个 `MODEL_UNCERTAIN` 维度必须引用该 receipt 中精确的 `source_id × field_id`，receipt、Decision Contract、Measurement Contract 与 forecast 都须在 freeze 前同公司/issuer/cutoff/H1 ref 一致。另将既有 `R-05:SBUX:NA_TRANSACTION_DURABILITY:20260821` 的两个 2027 signal windows 登记为 current `MECHANISM_SIGNAL_PROBE` shadow；它只证明 prequential 时钟正在运行，不是 state-forecast holdout、因果样本、CJO 或报告授权。

CN:600585 的 2018 `Forecast V4` 已在隔离开发 namespace 完成 contract-first 的独立 settlement。此处不记录预测或结果方向：可复用的唯一后续对象是 coverage / direct forecast policy，且只输出 `FORECAST_POLICY_ONLY + RESEARCH_AGENDA`。该 V4 在 outcome access 前没有冻结 Method Pairing 或 Decision-Utility Pairing；因此不得事后补冻，且永久不能作为 baseline-performance、evidence-priority、rival-hypothesis transfer、decision utility、method release、CJO、估值或报告授权证据。下一份可主张这些问题的对象必须是尚未 outcome-access 的新 V6：它须先冻结同一 source、Decision、Measurement、evidence 与 scope 合同，再在 outcome access 前精确冻结所需 pairing；真实 source package 仍是该前向对象的 acquisition blocker。

### WP-F0A Minimal Historical Episode

`Minimal Historical Episode v1` 是与 Forecast V1--V6、Comparative/V5 和教学 CJO 分离的窄管线验收 lane。它只接受一个公司、一个 cutoff、一个可由静态官方字段唯一测量的指标，并严格执行 `Decision Contract → Measurement Contract → cutoff-before static evidence → blind prediction → contract-only custodian access → value-free OutcomeSourceInventoryReceipt → official observation → mechanical settlement`。CN:600585 2018 已在隔离开发 namespace 完成这一链；登记只保留对象与链路身份，不记录预测、观测或机械结算方向。CN:600802 2018 的同类对象已停止在 contract-only access：允许入口不能唯一定位 FY2018 官方 static-PDF 的页级字段，因而正确保留 `MEASUREMENT_MISMATCH`，没有 observation 或 settlement。对下一份新对象，source inventory gate 只允许一个 contract-bound、outcome-period 的官方 static-finalpage annual-report 来源和一个可解析 PDF 页；它先于观察值和数字/引文读取，`MEASUREMENT_MISMATCH` 会停止后续结算。该 gate 只改善可复用 acquisition/measurement 边界，不回填既有对象。该 lane 的全部对象固定 `MECHANICAL_SETTLEMENT_ONLY + NO_METHOD_TRANSFER_RIGHTS`：它不能生成 Brier/RPS、learning、method pairing、Comparative 结论、CJO、估值、报告或投资权限。其价值是证明最小历史训练管线可在不先证明同行因果或方法泛化的条件下无泄漏运行；下一份 object 若要主张任何方法或决策效用，仍须走已冻结的 pairing、holdout 和独立审阅门。

下一份新 Minimal object 必须使用 `Measurement Contract v2`，在 forecast 前冻结 `CNINFO provider/version × security code × organization id × fulltext annual-report category × bounded query dates/page size × static-finalpage policy`。custodian 的 inventory adapter 只能从 stored contract 导出这一路由，不能接受 caller supplied code、org、日期或 route。没有 cutoff-before official metadata 所绑定的 organization ID 时，contract 在 pre-outcome 阶段即无效；不得先授权再猜测路由。既有 v1 artifacts 仅可作 historical read/replay，不能 upgrade 或发起新的 custody flow。详见 [Outcome Acquisition Route v2](MINIMAL_HISTORICAL_EPISODE_V2_OUTCOME_ROUTE_IMPLEMENTATION.md)。

### WP-D0 Decision Contract gate

`DecisionContract` 已作为 Forecast V2 的 forecast-first 前置门：它在 forecast 前冻结 `company × cutoff`、持有时域、永久损失约束、翻转问题、唯一 H1 source packet、三个独立角色，并禁止价格、机会成本和 outcome access。V2 forecast 必须引用 DB 中同公司/issuer/cutoff/source packet 的 contract，且 contract freeze 必须早于 forecast freeze；V1 不允许补挂。该门使历史 replay 不再只有预测对象。

### WP-D1 Teaching CJO mirror boundary

`HistoricalCJOTrainingMirror` 已实现为纯离线 validator：它将 contract-first V2 forecast 绑定至同 issuer、同 cutoff、frozen `TEACHING_ONLY` 的 V3 CJO，并将每个 `MODEL_UNCERTAIN` forecast 维度保留为 CJO review question、每个 `EVIDENCE_INELIGIBLE` 维度保留为 unknown guardrail。它拒绝 V1 retrofit、CJO investment permission、model/cutoff/role drift 和任何 overlay authorization。该对象不写第二份 canonical CJO、不建立生产入口，唯一输出为 `CJO_TRAINING_MIRROR / RESEARCH_AGENDA`；normal earnings、owner cash、ExpectationGap、BuyBand、report 和投资权限仍明确关闭。下一原子是独立、可结算的 CJO-to-valuation overlay epoch，而不是将本 teaching mirror 直接升级。

### WP-F0 Same-contract decision utility pairing

`DecisionUtilityPairing` / `DecisionUtilityEvaluation` 已作为纯离线配对评估：baseline 与 enhanced 必须复用同一 `DecisionContract`、唯一 H1 evidence budget 和 cutoff；独立 reviewer 在已登记 outcome settlement 后，对 permanent loss、owner-cash access、关键未知和研究成本逐项判断。没有综合分、单案 release、report 或投资授权；公司与时间双轴 holdout 未满足时只能拒绝。

### WP-1 架构与状态

实现六个核心对象、typed artifact、状态事件和权限映射。`EnterpriseSystemModel` 用版本化 JSON/关系表并投影到 MechanismGraph；`ManagementDecisionLedger` 使用追加式 decision/outcome rows。模型必须支持一对多责任单元、竞争场域和 measurement scope，并在关系边保存 `actor_side`、`interface`、`cross_side_effect` 等信息。不得新增第四张图或与现有 V5/PIT 重复的字段。验收是状态转移、局部 delta、来源时序、lane 权限和多 side/multi-arena fixture 测试。

### WP-2 竞争场域与范围桥

实现按机制声明 `REQUIRED_EQUAL / REQUIRED_OVERLAP / REQUIRED_EXPOSURE / NOT_REQUIRED` 的 arena；实现 accounting、decision、carrier、measurement 和 counterfactual 之间的桥，并投影出 EvidenceGraph/MechanismGraph/InvestmentGraph。arena 不得被实现为公司级单值字段；平台的参与者一侧、接口和跨侧反馈必须可独立标记。验收是全国市场、区域市场、全球细分市场、跨分部边界和多边平台的合成 fixture。

### WP-3 机制与边界训练器

把 R-104、结果已知教学案例和合成近失效接入 `Enterprise Model Lab`、`Management Decision Lab`、`Mechanism Lab` 和 `Boundary Learning`；输出必须保留 `MIXED`、`NO_PRIMARY` 和 `UNKNOWN`，不能污染 PIT 成绩。实现 `HypothesisRegistry` 和不计分的 diagnostic matrix；Research Policy 只为高材料性、可能改变决策且有鉴别能力的问题取证。

### WP-4 PIT Episode Engine

实现 enterprise pre-state/delta、cohort-first screening、curator 预登记静态官方 PDF package 的只读消费、cutoff 冻结、结果包隔离、topology 路由、target-trial episode contract、独立 D3/D4 contract、diagnostic settlement 和局部状态更新。先用拒绝 fixture 和已有回归，不以新候选取证作为调试循环。

### WP-5 Transfer 与 Holdout

实现 learning note、`TransportContract`、目标事实检查、application receipt、reviewer 接纳、课程选择、method freeze 和 R-103 留出揭盲。留出对象在冻结前不能泄露给方法形成。

### WP-6 CJO/估值接口

实现冻结 CJO 到 driver register、正常利润、owner cash、价格隐含经营要求、`ExpectationGap`、价值、回报和条件化 `BuyBand` 的单向编译；加入 InvestmentGraph、经营输入扰动、多解标记、身份对账和断边保守处理测试。

### WP-7 Golden Report Adapter

让黄金报告消费 CJO 和定量 canonical ledgers；报告正文、HTML 和技术附录只渲染，不反推事实或结果；增加独立审阅工件。

### WP-8 决策辅助评价

建立 paired fixture 和 task-level decision-support receipt，检查 Agent 是否发现材料性未知、阻止 scope/因果/普通股归属错误、产生可执行下一步并实质改变判断或区间。`UNKNOWN` 的正确保留可以通过；报告分数、样本数量和单次股价结果不能替代此评价。

## 7. 每次阻断的处理规则

当“第一个样本又出问题”时，先回答下面五件事，才决定是否改代码：

1. 失败是否可能改变经营质量、永久损失、估值或买点结论？如果不会，不升级为产品阻断。
2. 根因属于 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL` 还是 `WRITING`？
3. 缺口能否通过可复用来源包、schema、validator 或 scope bridge 修复？如果能，先修模块再找下一个样本。
4. 如果事实本身不可得或机制不可归因，是否应保留 `UNKNOWN`、`NO_PRIMARY` 或 `MIXED`？如果是，不用叙事补齐。
5. 修复后，下一步的不同动作是什么：继续该 lane、转入边界学习、终止候选，还是重新注册 episode？

禁止的修复方式是：为单个候选追加硬门、把地理一致性重新当万能标准、改写历史 cutoff、引入动态页面、让 D3 代替 D4、或把“资料更丰富”当作“机制更可比”。

## 8. 验收与可观察进度

每个阶段至少记录以下事实，而不是只记录完成百分比：

- 当前 `object_class / claim_class / allowed_outputs`；
- Industry Universe 的 cutoff、覆盖边界和退出对象是否保留；
- lifecycle event 的 `effective_at / known_at / source_available_at` 与 `OBSERVED/CENSORED/UNKNOWN`；
- 当前 lane 和方法版本；
- 输入来源是否在 cutoff 前且静态；
- 责任单元和 competitive arena 的证据状态；
- EnterpriseSystemModel 的版本、material state 和本次局部 delta；
- ManagementDecisionLedger 是否把当时判断、执行、外部冲击和结果分开；
- active hypotheses 中哪些被区分、哪些仍是共同解释；
- 当前 CJO 状态及 `UNKNOWN`；
- D3/D4 是否独立闭合；
- 该结果是否有资格生成 learning；
- learning 的 TransportContract 是否闭合，是否改变下一家公司冻结前字段；
- CJO 是否允许进入定量轨；
- 定量驱动是否穿透到 owner cash、价格隐含要求、预期差、价值、回报和 BuyBand；
- Agent 是否发现 material unknown 或阻止会改变投资结论的错误；
- 独立审阅指出的经济影响和剩余风险。

不能用单一总分替代这些观察。系统处于 `G1_ACTIVE / G3_WAITING` 时仍是活跃状态，不应被记为项目 blocked。

## 9. 路线图出口

路线图完成的不是“找到一个能通过的样本”，而是形成以下可重复闭环：

```text
Industry History Universe + Lifecycle Ledger
  -> Evidence Carrier Registry
       +-> Teaching/Lifecycle Case -> research agenda 与 boundary assets
       +-> Comparative Episode -> 结果揭示与错误诊断
             -> 带 TransportContract 的 learning 改变下一家公司
             -> 方法冻结 -> R-103 历史留出 -> report-use release
持续 EnterpriseSystemModel + ManagementDecisionLedger + Frozen CJO
  -> 正常利润 / owner cash / 价格隐含要求 / 预期差 / 价值 / 回报 / BuyBand
  -> 黄金报告 A/B -> 买点评价 -> 真实前瞻校准
```

只要这条链中任一处仍然靠人工叙事跨过去，系统就应明确标注尚未完成，而不是继续扩展样本数量。对中心目标而言，少量真正可迁移的判断变化，优先于大量无法解释为何成立的报告或样本。

## 10. 与现有路线图的关系

本文是面向 Agent 企业判断和买点辅助的上层路线，不替换项目当前的 `GOALS.md`、`LONG_TERM_ROADMAP.md` 或 Golden Set 执行状态。实现时应把本文的 G0-G8 映射到现有协调目标：现有的 `G1-T_HISTORICAL_TRAINING` 分为 Industry/Lifecycle、Teaching/Boundary 和 Comparative 三条子线；现有 V5/PIT 文档只属于 G2 的 Comparative 下层契约；Golden Set 属于 G7 的交付验收层。

如果现有阶段名称与本文发生冲突，先更新协调映射，再开始实现；不要让两个文档各自维护一套“当前已完成”状态。

## 11. 研究驱动的优化方向

外部研究不会增加一条“论文验收门”，而是改变实现优先级。具体方向如下：

### 11.1 证据图、机制图和投资图

六个核心对象定义了责任，但 Agent 仍可能在正文中把观察、推断、机制和估值连接得过于自由。先实现三图的最小投影：

```text
EvidenceGraph
  -> MechanismGraph
  -> CJO
  -> InvestmentGraph
  -> Golden Report
```

每条边都应能回答“来自哪段 cutoff 前材料、属于哪个责任边界、是观察还是推断、能否区分假设、是否传到普通股现金”。这比继续增加章节或字段更直接地改善企业判断。

### 11.2 主动研究和预期信息价值

Agent 每轮只处理一个高材料性未决问题，并在检索前写出：

- 目前 active 的竞争/共同假设是什么；
- 哪类官方资料可能区分它们；
- 结果可能怎样改变 CJO、D3/D4 或买点；
- 找不到资料时是否应停止。

研究排序使用 `HIGH / MEDIUM / LOW / STOP`，不引入伪精确的概率。这样可以直接识别“资料更多但决策不变”的低价值工作，并避免为单个样本不断加门。

### 11.3 生命周期与反幸存者偏差

先实现 company-time risk set 和 lifecycle event ledger，分开收购、合并/perimeter 转移、退市但经营、失败、业务退出和 `DATA_CENSORED`。`effective_at / known_at / source_available_at` 三个时钟不能合并；退出对象不从历史宇宙删除，结果缺失也不自动判输。当前只建设事件与删失兼容的数据结构，不在少量样本上拟合 hazard 或 competing-risk 模型。

### 11.4 Target-trial 式 episode 冻结

G2 的 episode contract 必须显式记录 `eligibility / time_zero / intervention / comparator / outcomes / follow_up / censoring / co_intervention / interference / estimand`。它借鉴的是问题定义纪律，不意味着从年报观察中自动获得因果识别。

### 11.5 机制课程和迁移优先级

下一案例按“当前最缺的机制、最有价值的边界、最有可能迁移且可获取”的组合选择，而不是按资料最容易取得选择。每次 learning 先完成 `TransportContract`，只改变下一家公司的一项冻结前字段，独立 reviewer 检查目标差异、break conditions 和这项实际变化。

### 11.6 持久运行和框架解耦

长任务需要可恢复状态、due inbox、人工接管点和完整运行事件；可以使用现有数据库实现，也可以未来接入 LangGraph/Temporal。不要让框架对象成为 canonical 研究对象，避免开源框架进入 maintenance/archive 后迫使 Turtle 重建研究契约。

### 11.7 分层评价

所有实现和后续论文/模型实验都分别报告 `PROCESS / EPISTEMIC / ECONOMIC / TRANSFER / DECISION_UTILITY`。不得用报告可读性补偿证据断链，不得用算术回归通过补偿迁移未证明，也不得用一次留出或一次买点表现宣称投资优势。

评价实现按能力阶梯建设：

1. FinanceBench-like 来源定位和 evidence span；
2. FinQA-like 确定性计算程序；
3. atomic claim 事实、引用关联和报告矛盾；
4. DRBench/DeepResearchBench-like 企业洞见、覆盖和深度；
5. Turtle 专有的 arena/scope/机制/D1-D5/PIT fixture；
6. CJO-to-quant 扰动、跨公司 transfer 和 R-103 holdout。
7. material unknown 发现、错误结论阻断和用户判断变化的 paired task。

前四层可以比较模型和研究 Agent，后面三层才评价 Turtle 是否接近中心目标。

### 11.8 企业整体表示

先实现 `EnterpriseSystemModel` 的最小版本：客户任务、价值交付、material resources、瓶颈、反馈、议价、再投资、治理和 owner-cash 传播。episode 只登记 `pre-state -> intended delta -> observed delta`，不重写整家公司。模型复用现有 MechanismGraph，不建立大型仿真或新图数据库。

### 11.9 管理层纵向判断

`ManagementDecisionLedger` 先覆盖两类不同决策和多个时点。每条记录在 cutoff 下分开 framing/alternatives/information/trade-offs/reasoning/commitment、执行、外部冲击和结果。单次成功最多评价一个 decision，不授予“优秀管理层”结论。

### 11.10 多假设与证据鉴别

`HypothesisRegistry` 允许二到五项竞争解释、共同机制和 `OTHER_UNRESOLVED`。hypothesis-evidence matrix 只记录 `EXPECTED / COMPATIBLE / CONTRADICTORY / NOT_APPLICABLE / UNKNOWN` 与 `DISCRIMINATING / COMMON / NONDIAGNOSTIC`，不加权、不计分。实现 Agent 必须证明共同支持所有解释的证据不会推动方向性 settlement，且“支持较少”不会单独 displacement 一个假设。

### 11.11 跨公司迁移

Transfer fixture 要同时包含表面相似但机制不同、表面不同但机制结构相同的对象。只有后者在取得目标事实并通过 moderator/break-condition 检查后才可应用 learning；行业标签、地域和规模不直接参与授权。

### 11.12 预期差与买点区间

定量 fixture 同时执行正向 CJO 估值和反向价格隐含要求。测试至少覆盖：多组参数都能解释同一价格、市场要求超出 CJO 可行范围、永久损失风险高但价格波动低、CJO 较好但价格已充分反映四类情形。输出为条件化 `BuyBand`，不能只保留一个目标价。

### 11.13 决策辅助效用

用 paired task 比较无 Agent/旧流程与 V3 流程：是否多发现一个材料性 unknown、少犯一个 scope/因果/归属错误、形成更可执行的下一步或改变价值/买点区间。正确停止是有效结果；更长报告不是。

## 12. 借鉴清单

- [STORM paper](https://arxiv.org/abs/2402.14207) 与 [STORM GitHub](https://github.com/stanford-oval/storm)：多视角问题发现、模拟追问、共享 mind map；
- [ReAct](https://arxiv.org/abs/2210.03629)：检索行动与计划更新交替；
- [Reflexion](https://arxiv.org/abs/2303.11366)：反馈转成窄的 episodic learning，但不能替代独立审阅；
- [DSPy](https://arxiv.org/abs/2310.03714) 与 [DSPy GitHub](https://github.com/stanfordnlp/dspy)：将 Agent 流程写成可优化程序；
- [FinRobot paper](https://arxiv.org/abs/2405.14767) 与 [FinRobot GitHub](https://github.com/AI4Finance-Foundation/FinRobot)：确定性金融计算、LLM 叙述和 provenance 分离；
- [FinMem](https://arxiv.org/abs/2311.13743)：分层 memory 的启发与 PIT 污染风险；
- [AgentBench](https://arxiv.org/abs/2308.03688) 与 [GAIA](https://arxiv.org/abs/2311.12983)：任务级、多维度 agent 评价；
- [FinanceBench](https://github.com/patronus-ai/financebench) 与 [FinQA](https://github.com/czyssrs/FinQA)：财报 evidence QA 和可执行数值推理；
- [DeepResearchBench](https://github.com/Ayanami0730/deep_research_bench)、[LiveResearchBench](https://github.com/SalesforceAIResearch/LiveResearchBench) 与 [DRBench](https://github.com/ServiceNow/drbench)：开放式和企业深度研究的分层评价；
- [FActScore](https://github.com/shmsw25/FActScore) 与 [Ragas](https://github.com/vibrantlabsai/ragas)：atomic factuality、citation 和生产对齐 eval；
- [Active Learning Literature Survey](https://minds.wisc.edu/items/37538f44-36ae-413e-8967-e6c831e17a8e)：昂贵反馈条件下选择高价值查询的启发；
- [Heuer / CIA, Psychology of Intelligence Analysis](https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/)：竞争假设、反证优先和证据鉴别力；
- [Collier, Understanding Process Tracing](https://www.cambridge.org/core/journals/ps-political-science-and-politics/article/understanding-process-tracing/183A057AD6A36783E678CB37440346D1)：因果序列、diagnostic evidence 及 straw/hoop/smoking-gun/doubly-decisive 检验；
- [Pearl & Bareinboim, Transportability](https://arxiv.org/abs/1503.01603)：显式表示来源/目标共同点、差异及迁移所需观察；
- [Gentner, Structure-Mapping](https://groups.psych.northwestern.edu/gentner/papers/Gentner83.pdf)：迁移关系系统而不是表面属性；
- [Society of Decision Professionals, Decision Quality](https://www.decisionprofessionals.com/who-we-are/decision-quality)：决策框架、替代方案、信息、价值权衡、推理和行动承诺；
- [Strategy Dynamics](https://strategydynamics.com/free/assets/The%20Dynamics%20of%20Strategy%2C%202016.pdf)：资源存量、流量、时滞与反馈的企业表示；
- [Expectations Investing](https://www.expectationsinvesting.com/)：从价格反解经营预期、判断预期修订和安全边际；
- [Causal Inference / CAUSALab](https://hsph.harvard.edu/profile/miguel-hernan/)：先定义可比较的干预问题和不可检验假设；
- [Synthetic Control tutorial](https://pmc.ncbi.nlm.nih.gov/articles/PMC8634614/)：比较组依赖干预前特征和趋势，不是地理身份；
- [Shumway, Delisting Bias](https://doi.org/10.1111/j.1540-6261.1997.tb03818.x) 与 [Brown et al., Survivorship Bias](https://doi.org/10.1093/rfs/5.4.553)：退出结果缺失和幸存者截断会制造系统性偏差；
- [Putter et al., Competing Risks and Multi-State Models](https://doi.org/10.1002/sim.2712) 与 [lifelines](https://github.com/CamDavidsonPilon/lifelines)：事件类型、状态转移与 censoring 的数据表示；
- [DoWhy](https://github.com/py-why/dowhy)：`model -> identify -> estimate -> refute` 的因果工作流，先暴露识别假设再选择估计器；
- [synthdid](https://github.com/synth-inference/synthdid)：面板比较的实现经验；不能修复错误 scope、差的 pre-period 或受污染 donor pool；
- [Aamodt & Plaza, Case-Based Reasoning](https://doi.org/10.3233/AIC-1994-7104)：`Retrieve -> Reuse -> Revise -> Retain` 可作为教学案例库流程，但 retain 不等于正式 learning；
- [W3C PROV](https://www.w3.org/TR/prov-overview/) 与 [OpenLineage](https://github.com/OpenLineage/OpenLineage)：可互操作的 provenance 与运行 lineage；
- [LangGraph](https://github.com/langchain-ai/langgraph) 与 [Temporal](https://github.com/temporalio/temporal)：持久执行和人工介入的运行经验；
- [AutoGen](https://github.com/microsoft/autogen) 与 [Open Deep Research](https://github.com/langchain-ai/open_deep_research)：框架生命周期变化说明核心契约必须与实现解耦。

这些材料支撑设计选择，不构成 Turtle 的投资证据，也不自动证明某个外部系统有效。

## 13. 深度研究模式的实施顺序

深度模式应作为上层运行协议实现，不应先做一个“更强提示词”或增加 Agent 数量。最小版本按以下顺序：

1. `FRAME`：明确企业问题、普通股后果和待评估的管理决策；
2. `SCOPE`：建立 EnterpriseSystemModel 草图、责任单元和 competitive arena；
3. `HYPOTHESES`：登记竞争/共同机制、预期观察、反方和 estimand；
4. `PLAN`：从 diagnostic matrix 与 EvidenceGraph 缺口生成 `HIGH/MEDIUM/LOW/STOP` 队列；
5. `ACQUIRE`：并行 source curator，只交付 source span 和 extraction；
6. `ADJUDICATE`：更新 enterprise state、management ledger、diagnostic matrix 和三张图；
7. `FREEZE`：reviewer 接纳 CJO 或明确 `NO_PRIMARY/MIXED`；
8. `INVEST`：估值 Agent 比较价格隐含要求与 CJO 范围，输出 ExpectationGap/BuyBand；报告 Agent 只消费 canonical ledgers。

四种模式 `DISCOVERY / PIT_REPLAY / LIVE_INVESTMENT / HOLDOUT_EVALUATION` 必须在控制面上有独立权限。深度模式完成的条件是关键假设已被区分或诚实降级，不能用搜索数量、报告长度或 Agent 数量作出口。

这条协议优先于引入 LangGraph、Temporal、AutoGen 或其他编排框架；框架只负责恢复、重试和可视化，不能定义 Turtle 的事实、判断和训练权限。
