# 前瞻判断研究循环日志

> 状态：`HISTORICAL_FINDINGS / METHOD_PREPARATION_ACTIVE`
> 启动：2026-08-20（Asia/Shanghai）
> 当前范围：本文件保留此前的论文、架构与格力实验发现；当前执行方向以“提升公司判断力”为中心，不以黄金报告生产为中心。研究准备期间不选新公司、不补格力事实、不写报告、不生成估值或投资结论。
> 当前真源：[研究方法大纲](TURTLE_RESEARCH_METHOD_OUTLINE.md)、[研究操作流程](TURTLE_RESEARCH_OPERATING_PROTOCOL.md)、[方法研究项目登记簿](TURTLE_RESEARCH_PROGRAM_REGISTER.md)、[判断力训练实验](TURTLE_JUDGMENT_TRAINING_EXPERIMENTS.md)和[判断力验证与回测协议](TURTLE_JUDGMENT_VALIDATION_PROTOCOL.md)。
> 关联：`GOALS.md` 的 `G1-J_JUDGMENT_CONTRACT`。
> 历史补充：[`ITER-100 owner-cash 正常化`](ITER_100_OWNER_CASH_NORMALIZATION.md)；[`ITER-101 诊断性深度`](ITER_101_DIAGNOSTIC_DEPTH_NOT_REPORT_VOLUME.md)；[`ITER-102 行业架构的诊断边界`](ITER_102_INDUSTRY_ARCHITECTURE_AS_DIAGNOSTIC.md)；[`ITER-103 因果信号顺序`](ITER_103_CAUSAL_SIGNAL_ORDER.md)；[`ITER-104 CJO 先于投资轨`](ITER_104_CJO_BEFORE_INVESTMENT.md)；[`ITER-105 先公司、后市场`](ITER_105_BLIND_COMPANY_FIRST_JUDGMENT.md)；[`ITER-106 结构化类比`](ITER_106_STRUCTURED_ANALOGY_WITHOUT_FALSE_SAMPLES.md)；[`ITER-107 CJO→投资 lineage`](ITER_107_CJO_TO_INVESTMENT_LINEAGE.md)。

## 0. 研究问题与判定原则

研究问题不是“怎样让报告更像有洞见”，而是：在当时可得的信息下，哪些方法能更好地选择中心路径、区分最强替代解释，并把判断传播到正常利润、普通股现金、价值与回报。

一个候选方法只有在下列至少一项有可复核改善时才保留：

1. 提高冻结预测的校准、区分度或区间覆盖；
2. 新增会改变投资结论、永久损失判断、估值或回报的因果证据；
3. 发现并阻止价格循环论证、错误类比、错误财务外推或不可结算的叙事。

不能因篇幅增加、章节更多、敏感性更多或主观评分更高而保留。论文在其他国家、行业或预测领域的结果只能形成待检验假设，不能直接证明适用于中国家电研究。

## 1. 冻结基线（ITER-00）

### 对象

- 格力当前候选：`output/000651_格力电器_phase08_20260803/`（主工作区只读）。
- 既有书籍方法案例卡：`config/insight_case_benchmark.json`。
- 既有基准率候选：`output/.base_rate_library/cases.jsonl`。

### 已复现实验

以当前 `thesis_test.json`、全部候选章节和 `forward_judgment_required=true` 调用现有 `validate_thesis_test_ledger`，不写入任何候选文件。

结果：`INCOMPLETE`。

- 未选择 `central_path`；
- 无 `forward_judgments`；
- 正常利润、owner cash、估值、预期回报四条传播均未覆盖；
- 没有指向主价值结论和预期回报的前瞻判断决策链接。

该失败确认 G1-J 面对的是实质性研究缺口，而非格式缺口。现有“周期扰动 / 结构衰退 / 渠道或会计扰动”三种情景，尚未给出哪条3/5年路径更可能，也未使当前结论可被未来结果反驳。

### 当前限制

- 9 个基准率对象均为 `CANDIDATE`，没有 `ELIGIBLE` 结果样本；不得输出经验频率。
- 格力候选中“周期”与“结构”被写成互斥情景，但在经济上可以短期共存：需求周期回升与中期份额/资本配置恶化并不矛盾。这是待验证的 `REASONING` 风险。
- 市场价格接近研究价值不能作为“市场正确”的证据；它至多是待解释的隐含预期。

## 2. 预注册方法假设

| ID | 方法假设 | 首要测试 | 保留条件 |
|---|---|---|---|
| H1 | 相似状态参考类可降低单一公司、少数熟悉案例带来的可得性偏差 | 把报告版本和跨公司状态拆为可结算 episode，检查参考类是否在PIT下可定义且不泄漏 | 参考类规则可复现、结果分布可用，且不会把同一叙事的重复报告伪装成独立样本 |
| H2 | 机制过程追踪可让“周期还是结构”从口号变为有区分力的因果竞争 | 为每条主机制列出中间环节、替代机制的相反预测与观察窗口 | 每个材料性机制至少有一项会改变后验概率的观察，而非只有支持主张的证据 |
| H3 | 价格隐含预期与独立经营预测的封闭双轨可消除价格循环论证 | 先生成不见价格的经营路径，再单独反解价格隐含路径，最后比较 | 两条路径的差异能定位到收入、利润率、再投资或持续期，并改变研究问题或结论 |
| H4 | 利润率、周转、应计可靠性和现金转换的状态转移分解比单点盈利外推更能约束未来正常利润 | 将行业判断逐层传到收入、利润率、周转、营运资本、维护投入和 owner cash | 每个前瞻判断都能指出其改变的财务状态和模型输入；不能只写“收入恢复” |
| H5 | 冻结、结算和任务信息反馈能区分真正改善与更漂亮的事后叙事 | 对历史报告版本只追加结果事件，记录方向、区间、机制、驱动链和时效 | 不改写冻结预测；样本不足时只报告计数与不确定性，不宣称已校准 |
| H6 | 管理层承诺与资本配置履历能提供比访谈语气更可靠的治理先验 | 将承诺、资源投入和随后可观察结果形成时间序列 | 只使用可回溯行动；不把“暂未发现改善”写成“必然不会改善” |
| H7 | 行业架构图能让行业分析定位价值实际被哪个接口攫取，而不止并列份额与毛利 | 对同一 pair 冻结分工、接口控制、互补资产、要素流动性与价值攫取节点；检查是否生成新且可区分的观察 | 不能由垂直整合、公司自述或渠道排名推断价值攫取；不能生成新信号则撤销 |
| H8 | 存量—流量—时滞图可防止把补库/去库、出货或单期收入误当长期竞争机制 | 对两个竞争机制预先冻结可观察存量、流量与先后顺序，并由后续经营资料结算 | 不是参数化仿真；缺同口径库存、sell-out 或产能事实时保持 `UNKNOWN` |
| H9 | 有审计边界的关键经营决策 episode 可暴露公开文件中没有写出的线索、目标和被排除方案 | 对材料性机制采集一个发生在 cutoff 前的困难决策时间线，并要求它导出一条原先没有的、可被独立经营资料结算的区分信号 | 访谈不是公司事实、不是 PIT 历史证据的替代，也不能由轶事、关系或语气提高中心路径置信度 |

## 3. 文献与书籍登记

| 方法 | 来源 | 可迁移命题 | 迁移边界 |
|---|---|---|---|
| H1 | Lovallo、Clarke、Camerer（2012），[Robust analogizing and the outside view](https://authors.library.caltech.edu/records/ayatf-66x08)；Theising、Wied、Ziggel（2023），[Reference class selection in similarity-based forecasting](https://ideas.repec.org/a/wly/jforec/v42y2023i5p1069-1085.html) | 参考类和相似度加权可优于少数熟悉类比；后者在公司销售分布预测上做了样本外检验 | 不能把美国样本的变量系数、阈值或分位数直接移植到中国家电 |
| H2 | Bennett、Checkel 编，[Process Tracing](https://www.cambridge.org/core/books/process-tracing/5BBC24CBF2E89114817741D0476C07A9) | 用中间因果过程检验竞争解释，并处理多因一果 | 不是把每个叙事环节都形式化；只追踪会改变结论的机制 |
| H3 | Mauboussin、Rappaport，[Expectations Investing](https://cup.columbia.edu/book/expectations-investing/9780231203043/) | 从当前价格反解经营预期，再判断预期修正的可能性 | 价格隐含路径是比较对象，不是公司事实或结论证明 |
| H4 | Fama、French，[Forecasting Profitability and Earnings](https://ideas.repec.org/a/ucp/jnlbus/v73y2000i2p161-75.html)；Richardson、Sloan、Soliman、Tuna，[Accrual Reliability, Earnings Persistence and Stock Prices](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=521062)；Armstrong、Collopy、Yokum，[Decomposition by causal forces](https://doi.org/10.1016/j.ijforecast.2004.05.001) | 盈利存在非线性均值回归，应计可靠性影响持续性；当驱动力冲突且分项可预测时，先分解再加总可能优于直接外推 | 只作为正常化与现金质量的先验；只有分项数据、基线和可加总关系齐备才允许分解，不机械套用估计系数 |
| H5 | Mellers 等（2014），[Psychological Strategies for Winning a Geopolitical Forecasting Tournament](https://www.psychologicalscience.org/journals/psychological-science/0956797614524255/)；Hauenstein 等（2025）的[复核](https://www.psychologicalscience.org/journals/psychological-science/09567976241266481/)；Remus、O’Connor、Griggs，[Does Feedback Improve the Accuracy of Recurrent Judgmental Forecasts?](https://www.sciencedirect.com/science/article/pii/S0749597896900357) | 训练、追踪、概率与反馈可能改善预测；在结构不稳定任务中，任务结构反馈优于单纯结果反馈；原研究中团队/训练的因果效应存在后续争议 | Turtle检验的是冻结和反馈闭环，不声称复制地缘预测锦标赛的全部因果结论，也不把实验室效应直接外推为投资收益 |
| H6 | Aschauer、Preussner（2022），[Management earnings forecast review](https://onlinelibrary.wiley.com/doi/10.1111/1911-3838.12294)；Sutton，[Sunk Costs and Market Structure](https://mitpress.mit.edu/9780262693585/sunk-costs-and-market-structure/) | 管理层预测误差可跨期持续；行业结构研究应结合理论、跨案例和历史事实 | 管理层承诺不是投资结论；沉没成本理论不提供格力的直接参数 |
| H7 | Jacobides、Knudsen、Augier，[Benefiting from Innovation: Value Creation, Value Appropriation and the Role of Industry Architectures](https://doi.org/10.1016/j.respol.2006.09.005) | 行业分工、接口、互补资产与要素流动性共同决定价值可被谁攫取，不能只看企业是否垂直整合 | 论文给出战略机制，不提供格力的接口控制或利润池数据 |
| H8 | Sterman、Repenning、Kofman，[Unanticipated Side Effects of Successful Quality Programs](https://doi.org/10.1287/mnsc.43.4.503) | 受反馈与时滞连接的存量、流量可能让短期财务表现和长期经济机制背离 | 这是动态机制的取证框架，不授权对空调行业套参数模拟或把任意库存归因 |
| H9 | Klein、Calderwood、MacGregor，[Critical decision method for eliciting knowledge](https://doi.org/10.1109/21.31053)；Crandall、Klein、Hoffman，[Working Minds](https://mitpress.mit.edu/9780262033510/working-minds/)；Klein，[Performing a Project Premortem](https://hbr.org/2007/09/performing-a-project-premortem) | 围绕具体困难决策追问时间线、关键线索、目标、备选方案和预期后果，可让隐性经营判断转为可检验的机制问题；预演失败可让反方更早表达 | 这些方法用于生成和挑战机制，不能验证受访者陈述，不能把现在的回忆倒灌为历史 PIT 事实，也不应替代持牌行业数据或公司披露 |

## 4. 下一轮

`ITER-01` 将测试 H2+H4：对格力现有“周期 / 结构 / 渠道”叙事重写为非伪MECE的时间分层机制，并检查每条链是否能生成可观察前导指标和财务传播。研究对象先在隔离实验工件中运行；若失败，先修研究输入/schema，而不修饰报告文字。

## 5. ITER-01 — 时间分层过程追踪与财务状态传导（2026-08-20）

### 假设与实验设计

检验 H2 + H4：现有概率集把“周期扰动”“结构性衰退”和“会计/渠道口径扰动”当作三个互斥终局。若其中任两项可以同时为真，或其中一项只是传导过程，则概率相加虽等于 1，经济含义却不成立，进而可能错误影响 `lambda`、`v_final` 和 `expected_return`。

实验只使用冻结 `thesis_test.json` 与 `judgment_review.json` 已列出的证据，不补写事实、不重估格力。

### 观察

1. **互斥性失败。** “短期渠道去库存后营收反弹”与“中期线上份额流失、资本配置拖累持续”可以同时为真；二者的预测窗口不同，不能作为同一层级的备选终局。
2. **层级错误。** `SC:accounting_channel` 的证据（合同负债的 U 型、经销商激励）描述的是销售确认和渠道库存的传导机制，不是独立的 3/5 年经营结果。它可出现在任何一个终局之内。
3. **现有真正有区分力的信号不足。** 年度线上份额可约束中期竞争地位，但不能单独判断短期收入反弹的现金质量；单期收入转正也不能区分信用放宽、补库存和需求恢复。评审已明确要求将 H1 收入与 OCF 同时观察，而非仅观察营收。
4. **财务传播没有被锁定。** 当前阈值能改变动作，却没有把“收入/份额/现金转换/资本配置”分别传播到正常利润、owner cash、终值折价和预期回报。因此它不能检验中心路径，而只是监控清单。

### 通过过程追踪后的候选结构（仅研究原型，非格力新结论）

概率集应只包含同一 3/5 年尺度、彼此互斥的**经营终局**；渠道和会计指标降为每一终局内的中间机制。初步可检验的三种终局为：

| 终局原型 | 短期机制（非终局） | 可冻结的前导观察 | 必须传导的财务状态 | 当前缺口 |
|---|---|---|---|---|
| A：短周期修复、但中期竞争和资本配置拖累仍在（混合路径） | 去库存/补库存、渠道激励 | 收入相对行业、线上份额、销售回款与 OCF 是否同步恢复 | 收入→毛利率/费用率→正常利润；现金转换/营运资本→owner cash；份额与资本配置→持续期/`lambda` | 同口径行业销量和份额时序；H1 现金与收入共同结果；非主业投入的分部回报 |
| B：竞争地位加速恶化 | 渠道调整无法抵消份额下降 | 收入持续落后行业、份额下降、毛利率或周转恶化、现金转换走弱 | 收入和单位经济性→正常利润；营运资本和维护投入→owner cash；护城河衰减→价值与回报 | 原始市场份额来源、可比对手时序、渠道库存/应收口径 |
| C：战略重置成功 | 渠道重整和产品/渠道升级转为可验证的竞争改善 | 份额止跌、毛利率/周转不以放宽信用为代价，非主业投入的损失收敛或退出 | 收入/毛利率/周转→正常利润；再投资回报→owner cash；资本纪律改善→终值折价缩小 | 格力钛独立损益和现金占用、盾安协同披露、管理层承诺—资源—结果序列 |

此结构不主张 A、B、C 的概率或当前哪个为中心路径。因为参考类尚无合格结果样本，且上述关键观测尚未补齐；在此时填入更精细的主观概率会制造精确性幻觉。

### 对“20 多份格力/同行报告”的隔离检验

工作区内未发现一套可直接读取的“20 多份格力外部研究报告”原始文件；当前路线图中能核对到的是 **G1 完成后** 才可启动的 G1.5 预注册实验：6 家公司 × 3 个历史时点的 18 份公司 PIT 黄金报告，加上 6 份行业/宏观/格力 V2 工件，共 24 份。它尚未解锁，也不能以当前生成的同质报告代替独立样本。

这批报告对判断能力**可能有用，但用途是检验而不是灌输**。有效单位不是“报告一篇”，而是一个满足下列条件的 PIT 机制 episode：

1. 截止日可得的公司、行业、价格和管理层行动被冻住；
2. 上表的终局、相反预测、观察窗口及财务传播在结果已知前写下；
3. 同一公司不同年份和不同公司相似状态分别结算，不能重复引用同一事后叙事；
4. 结果按收入相对行业、份额/单位经济性、现金转换和价值/回报四层结算，并保留失败案例。

若只把 20 多篇当前报告再写得更长、让同一模型互评，预期只会增加资料覆盖和语言流畅度，**不会**产生可信的行业先验或未来判断校准。这一风险的根因是 `REASONING + DATA_COVERAGE`；修复首先是历史 PIT 数据与结算 schema，其次才是报告生产。

### 结果与下一步

**结论：H2+H4 暂获结构性支持，尚未获得预测效力验证。** 它发现了一个会实质改变期望回报判断的建模错误：把过程因素作为互斥终局，会掩盖“短期回暖但长期竞争力下降”的混合路径。失败原因分类：`REASONING`（错误的事件层级）、`DATA_COVERAGE`（缺行业/渠道/分部现金时序）、`ACQUISITION_MODULE`（尚未能按 PIT 取到这些字段）。

下一轮 `ITER-02` 先审计现有 G1-J schema 是否能显式表达“终局—机制—指标—财务输入—决策”链；若不能，提出最小字段与验证规则。只有在 schema 可表达、字段可取得后，才对 G1.5 的 24 个 PIT 工件预注册并测试 H1/H5。

## 6. ITER-02 — 案例卡、参考类与 schema 的能力边界（2026-08-20）

### 已核对的存量能力

用户的判断正确：案例卡已经做了。`config/insight_case_benchmark.json` 有 8 个方法原型；其中 `operating_transition` 已明确要求锁定异常、给出最强竞争解释、区分性观察和动作更新。它是合格的**研究动作路由器**，不是公司事实、预测样本或行业基准率。

`output/.base_rate_library/cases.jsonl` 有 9 条候选案例，均为 2026-08-02 的当前报告捕获，预测状态为 `NOT_ASSIGNED`。以格力的 `cycle_structure_or_accounting_disturbance` 和 `mature_consumer_manufacturing` 查询，实际返回 `eligible_sample_size=0`、`empirical_base_rate=null`、`sample_too_small:0<5`。

因此，案例卡无需重建；应补的是从卡片到可结算、相似状态 episode 的采集和结算。把这些 `CANDIDATE` 条目或同一份报告的多个问题当作独立历史样本，都会制造伪样本量。

### Schema 反例测试

在临时目录中以 `tests/test_stage14_thesis_test_gate.py` 的完整、可通过前瞻判断工件为底稿，只把主情景重命名为“渠道/会计口径扰动（过程因素，不是3年终局）”，并同步所有引用 ID 与冻结指纹。

现行 `validate_thesis_test_ledger(... forward_judgment_required=True)` 仍返回：

```text
state=DECISION_READY
forward_judgment_state=DECISION_READY
invalid_findings=[]
incomplete_findings=[]
```

这个反例不是说验证器应当从自然语言猜测真伪，而是证明它目前只检查概率和 ID 一致，不要求作者声明“这是终局还是过程”。所以它不能阻止本轮发现的伪 MECE。

### 最小修订原型（待下一轮编码验证）

不另建预测系统，在现有 thesis ledger 增加一个小的、可审阅的层级：

1. `probability_sets.outcome_scope`：只允许被中心路径选择的集合声明为 `TERMINAL_OPERATING_OUTCOME`，并给出统一的 `horizon_years` 与 `outcome_space_definition`；
2. `mechanism_chains[]`：每条链必须绑定一个 `scenario_id`，写明过程因素、至少一个既有阈值、以及它进入 `normalized_earnings`、`owner_cash`、`valuation`、`expected_return` 的具体输入说明；
3. `forward_judgments[].mechanism_chain_ids`：前瞻判断必须指向这些链；中心路径所选情景至少有一条链，且每条链的阈值/判断/决策 ID 必须能解析。

验证器只做可机械验证的部分：角色枚举、时间尺度、ID 连通性和四个财务传播出口；“是否真是终局”仍由研究者在链条、反证和独立评审中负责。这比让验证器伪装成语义裁判更诚实，也足以使“渠道扰动”必须写成机制而不能悄悄占据一个概率桶。

### 结果与下一步

**H1 目前不成立为可用基准率工具；H2 的 schema 支撑不充分。** 根因分别是 `DATA_COVERAGE + ACQUISITION_MODULE`（无 PIT 结果样本）及 `REASONING + MODEL`（schema 没有过程层，验证器只能验证形式 MECE）。

`ITER-03` 先实现并回归测试上述最小 schema 原型；验收条件是：过程因素被显式标为 `MECHANISM` 时不能作为中心路径概率情景，而完整的“终局—机制—指标—传导—决策”工件仍可通过。此后再以一个历史 PIT 样本检查 H3 的“先独立经营路径，后看价格隐含路径”是否能产生新的、可行动研究问题。

## 7. ITER-03 — 最小终局/机制契约原型（2026-08-20）

### 实现

在隔离研究 worktree 中扩展既有 `thesis_test_ledger`，不创建平行预测系统：

- 中心路径选用的概率集合新增 `outcome_scope=TERMINAL_OPERATING_OUTCOME`、`horizon_years`、`outcome_space_definition`；集合中的情景新增显式 `scenario_role`；
- 新增 `mechanism_chains[]`，要求链接概率集合和终局情景、领先阈值、四段传导及决策 ID；
- 每项 `forward_judgment` 新增 `mechanism_chain_ids`，且必须与其概率集合和情景身份匹配；
- 写入工具的嵌套 schema 与运行指引同步暴露这些字段，避免实现了验证却未让研究者看到契约。

### 回归结果

目标测试是检出两类此前会静默通过、并可能改变价值和回报判断的失败：

| 工件 | 旧验证结果 | 新验证结果 | 若失败后的动作 |
|---|---|---|---|
| 将 `scenario_role=MECHANISM` 的“渠道/会计扰动”选作中心路径 | `DECISION_READY` | `INVALID`，`scenario_role_not_terminal_outcome` | 改为机制链，重建同尺度经营终局，再选择中心路径 |
| 从一项前瞻判断移除 `mechanism_chain_ids` | `DECISION_READY` | `INCOMPLETE`，`mechanism_chain_ids_missing` | 补其通向财务输入和决策的因果链，或删除不材料的判断 |
| 完整终局—机制—指标—传导—决策夹具 | `DECISION_READY` | 仍为 `DECISION_READY` | 可作为后续真实报告的结构模板，而非公司结论 |

已对变更文件执行 Python 编译检查及上述目标 smoke test。当前 shell 没有 `pytest`，因此没有把“pytest 未安装”误报为产品回归；待项目测试环境可用时，应执行 `tests/test_stage14_thesis_test_gate.py` 的完整集合。

### 边界与结论

该原型通过的是**表达和阻断能力**，不是对格力未来的预测验证。它不能自动判断研究者把文字错误标成 `TERMINAL_OUTCOME` 的经济真伪；这仍须由过程链、反方、独立审阅及 PIT 结算约束。当前格力冻结候选没有中心路径和前瞻判断，故不改写、不重新冻结它。

**H2 的必要产品条件通过；H1/H3/H4/H5/H6 的效果仍未验证。** 下一轮 `ITER-04` 测试 H3：在一个严格的历史 PIT 对象上，先遮蔽价格构建独立经营路径，再以同一模型反解价格隐含路径；只有两条路径的差异能导出新增的、可结算决定性问题时，才保留该双轨方法。若找不到合格 PIT 输入，根因应先记为 `DATA_COVERAGE + ACQUISITION_MODULE`，而不是从当前格力价格倒推叙事。

## 8. ITER-04 — 价格盲的经营路径与隐含预期双轨（2026-08-20）

### 可用性测试

本轮先检索现有 PIT 工件，而非从当前格力价格构造一个伪历史实验。结果：

- `config/historical_backtest_pilot.v1.json` 将格力及其余候选均登记为 `INELIGIBLE_NO_HISTORICAL_VINTAGE`，原因包括缺可验证的历史报告版本、逐源发布时间和当时市场数据；
- 唯一较完整的 `600340` PIT 工程案例的冻结身份是 `FROZEN_WITH_QUALITY_FAILURE / PIT_ENGINEERING`，其 `inputs=[]`，未冻结普通股现金预测，明确禁止产出可执行估值、回报和选股结论；
- 现有 `insight_ledger.reverse_expectations` 已要求价格、反解方法、隐含经营路径、假设和翻转条件，但没有“经营路径在价格可见前冻结”的执行身份。

因此不存在可用于 H3 的合格历史样本。用华夏幸福工程草案补一个目标价或从结果期价格反向拟合，都会违反 PIT 围栏并错误地把 `ACQUISITION_MODULE` 缺口包装成 `REASONING` 成功。

### 保留的研究设计（尚未实施）

H3 只在下列双轨流程下进入 G1.5 的预注册包：

1. **经营盲轨**：源包不提供股票价格、PE/PB、市值、目标价或事后结果；先冻结销量/价格/组合、毛利/费用、营运资本/维护投入、正常利润和 owner cash 的路径及其机制链；
2. **市场隐含轨**：冻结经营盲轨后才读取同一 cutoff 的价格身份，用同一估值路线反解价格所需的收入、利润率、再投资和持续期；
3. **差异审阅**：只记录二者在经济驱动上的差异，并生成新的决定性问题（例如“市场要求份额持久回升，而盲轨仅支持现金回收”）；价格本身不得反向覆盖公司事实或中心路径；
4. **可审计隔离**：必须由 source allowlist 和运行记录证明盲轨未读价格。仅由作者自述的“我没有看价格”不算验证。

### 结果

**H3 目前不能保留为已证实方法，保留为有理论支持的预注册假设。** 根因是 `DATA_COVERAGE + ACQUISITION_MODULE`，并有一个 `MODEL` 缺口（现有 reverse-expectations schema 未记录盲轨身份）。经济影响是避免研究用“市场已定价/未定价”掩盖独立经营判断尚未形成。

`ITER-05` 转向 H4/H6 的可测试部分：检查现有格力候选能否把收入、竞争地位、现金转换和资本配置分别映射到模型输入；若只有自然语言传播，就把字段/采集缺口列为 G1-J 和 G1.5 的前置，不把它误称为已完成的行业深度。

## 9. ITER-05 — 财务状态转移与资本配置履历（2026-08-20）

### 对格力冻结候选的结构检查

当前候选确实有丰富的财务历史：三年 `OCF/NP=1.49`、AA/Capex/D&A 窗口、合同负债、短期借款、线上份额和格力钛减值等。问题不在“没有数字”，而在它们未成为可验证的未来模型输入链：

1. `valuation_model.json` 的主 EPV 只结构化保存折现率、零增长、终值和结果；`financial_trends.json` 的 AA/Capex 是历史聚合。两者之间没有收入、单位经济性、营运资本、维护投入或资本配置到正常 owner cash 的具名输入绑定。
2. `thesis_test.json` 只有阈值和动作，没有中心路径、前瞻判断或机制链；因此收入、份额、OCF 与资本配置不能被分别结算并改写正常利润/owner cash/`lambda`/价值/回报。
3. 报告正文虽写“营收 + OCF + 线上份额”的联合观察，却又把 `lambda=0.625` 叙述为“约 37.5% 留存利润被消耗”。`lambda` 是估值折价/兑现参数，当前没有逐笔资本去向和回报账本，不能直接解释为现金被消耗的比例。这是会夸大资本错配确定性的 `REASONING` 问题。
4. 正文将市价接近低估值锚描述成市场对“周期回暖+治理改善”约 30% 的综合概率；现有工件没有价格反解模型或盲轨身份，故该数值属于不允许的 `MODEL + REASONING` 推断，不能作为前瞻证据。
5. 格力钛独立损益/现金占用、盾安协同回报、短期借款和 617 亿元投资现金流的实际用途均被现有判断研究计划列为未知。它们恰是资本配置能否改变 owner cash 和永久损失的材料变量。

### H4/H6 所需的最小可复用采集对象

在继续生成 G1.5 报告前，应先为每个公司—时点建立一个可由官方披露回填的 `financial_driver_bridge`，不是新增叙事章节。每行至少需要：

| 驱动层 | 必需字段 | 传导目的 |
|---|---|---|
| 竞争/需求 | 同口径销量或收入、相对行业/份额、ASP/组合、来源和观察期 | 判断收入是周期、份额还是产品组合变化 |
| 单位经济性 | 分部毛利、费用率、产能/周转或可得代理、口径变化 | 传导至正常利润，而非把收入直接外推成利润 |
| 现金转换 | 销售回款、应收/存货/合同负债、OCF/利润、维护性资本开支 | 传导至 owner cash，并区分信用宽松、去库存和真实需求 |
| 资本配置 | 每笔非核心并购/投入/担保/退出/回购/分红的日期、金额、资金来源、管理层预期、后续实际结果 | 决定 `lambda`、永久损失边界和资本纪律是否可改善 |
| 模型绑定 | 该驱动影响的模型输入、敏感性方向、判断/阈值/决策 ID | 使“行业深度”能改写价值与回报，而非停在解释层 |

每个字段若缺失，必须显示 `UNKNOWN` 与保守处理；不得用格力年报中的泛化战略表述、媒体二次份额或“低 PE”补齐。管理层叙事可进入 H6 的事件账本，但只有资源投入和后续可观察结果能提升其权重。Malmendier、Tate（2015）显示管理者过度自信会影响投资决策，支持把管理层资本配置视为要逐项验证的经济变量，而不是人格评价；它不为格力提供参数或结论。[Behavioral CEOs: The Role of Managerial Overconfidence](https://pubs.aeaweb.org/doi/abs/10.1257/jep.29.4.37)

### 结果

**H4/H6 尚未通过；根因优先是 `ACQUISITION_MODULE + DATA_COVERAGE`，其次是 `MODEL + REASONING`。** 经济影响直接作用于格力的正常利润、owner cash、`lambda`、内在价值和“避开”结论。修复顺序是先建设上述桥接采集/schema 和 `UNKNOWN` 验证，再让报告或模型选择中心路径；不应用更长的行业综述或更多报告掩盖缺字段。

`ITER-06` 将把这项发现写入 G1-J/G1.5 的明确前置与验收条件，并评估 24 份报告的合理角色：它们应产生独立 PIT 机制 episode 和结果结算，而非被当作提高判断力的阅读数量指标。

## 10. ITER-06 — 24 份报告的学习单位与伪样本防线（2026-08-20）

### 假设

“格力加 5 家同行、3 个结构时点”的 18 份公司—时点报告，加 6 份综合/V2 工件，能否提高判断力，取决于它们是否形成可结算、可比较的机制 episode，而不是产物总数是否达到 24。

### 研究判断

1. 书籍案例卡的价值是给每份报告提出更好的问题和禁止捷径，不是为结论投票；现有 8 张卡已足以承担这项职责。
2. 18 份公司—时点报告的价值在于**纵向反例与状态变化**：同一公司不同阶段可观察机制是否变形，职责不同的同行可检查格力的解释是否只是一家公司的特殊叙事。过程追踪可与跨案例比较结合，但不能把单案解释自动外推为一般规律。[Process Tracing](https://www.cambridge.org/core/books/process-tracing/5BBC24CBF2E89114817741D0476C07A9)
3. 它们不能直接产出可靠的经验基准率：同一公司跨时点相关、同行按理论职责而非随机抽样选取、每种机制的有效数量还会小于 18。参考类研究的实证结果支持相似状态和样本外检验的方向，但不支持把小型、相关的中国家电矩阵伪装成大样本频率估计。[Reference class selection in similarity-based forecasting](https://ideas.repec.org/a/wly/jforec/v42y2023i5p1069-1085.html)
4. 因此 24 份的首要验收不是“平均报告评分上升”，而是每个 PIT 公司—时点都能冻结一个机制 episode，并在开放结果后判断中心路径、领先信号、财务状态和行动是否正确。综合报告/V2 不计入参考类分母。

### 预注册的 episode 身份

每份 18 个公司—时点报告至少记录：

- `company_id / cutoff / industry-regime / source-package`；
- `mechanism_family`、终局空间、中心路径和最强替代解释；
- `financial_driver_bridge` 的输入版本及 `UNKNOWN`；
- 3—5 个判断及其结果测量；
- 结果开放后的方向、区间、机制、时效和投资动作结算；
- 聚类身份（公司、时期、机制）。

在 G1.5 内只能报告覆盖数、可结算数、错误类型与跨案例一致/反例；只有同机制、PIT、独立资格和结果事件均闭合的案例，才可按现有 `ELIGIBLE` 契约进入基准率查询。行业机制的升格也必须保留至少一个反例和适用边界。

### 结果

**“24 份报告”方法被有条件保留，且路线图已有正确骨架；不应增加到更多同质报告。** 它可以提高行业分析深度和判断的可证伪性，但现阶段不能证明“判断更准”。关键新增前置是 episode 身份、PIT 围栏、财务驱动桥、双轨价格隔离与追加结算。若任一前置缺失，根因分别按 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING` 或 `MODEL` 记录，不允许通过叙事润色补偿。

下一轮 `ITER-07` 将检验 H5 的结算和反馈闭环是否已足够区分“预测失败”“机制判断失败”“数据不可得”和“写作没有表达出来”；该闭环才是让 Turtle 从格雷厄姆/巴菲特案例的学习方式中真正获得判断能力的部件。

## 11. ITER-07 — 冻结、结算和错误归因闭环（2026-08-20）

### 现有能力测试

`historical_backtest` 已有比当前 G1-J 更成熟的结算逻辑。以其标准夹具作隔离 smoke test，验证器：

- 对完整冻结案例把 `REPORT_COVERAGE`、`MODEL_FORECAST_ERROR`、`INVESTMENT_RETURN_OUTCOME` 分开并返回 `REVIEWABLE`；
- 拒绝把三者混成一个总分（`combined_score_forbidden`）；
- 拒绝结算时改写冻结预测值；
- 要求每一个冻结预测和 `UNKNOWN` 都有显式结果状态，不能把可比观察静默丢弃。

这正符合 H5 的目的：报告写得好、经营预测对、投资回报好是不同问题，不能互相抵消。历史案例和结算状态还可区分 `PREDICTION` 的 `CALCULATED/PARTIAL/NOT_CALCULABLE` 与 `UNKNOWN` 的已解决/未解决状态。

### 尚未接通的断点

`phase10_backtest_case_adapter` 当前只把 PIT 生产报告的“thesis_test 已通过”作为 snapshot gate；它不会把 `forward_judgments`、终局/机制链和测量规则自动投影成 `historical_backtest.calibration_ledger.claims`。其设计还明确保持价格、路由和投资行动 `UNKNOWN`，以防制造回报结果。

所以 H5 的**结算引擎本身可用**，但 G1-J → 历史结算的对象适配尚未完成。若不修这一点，24 份报告仍可能各自有前瞻账本，却无法用同一结构逐项反馈学习。

### 接线规则（预注册，不现在运行历史回测）

1. 每个 `forward_judgment` 一对一生成一个冻结 claim，复用其 prediction、官方测量规则、源类型、结算版本政策和 `mechanism_chain_ids`；
2. 终局/机制结算单列为 claim 结果，而不是从股价或报告评分反推；
3. `financial_driver_bridge` 的每项可比后续观察以独立 observation 追加，标注 `COMPARABLE / SCOPE_OR_ACCOUNTING_DRIFT / NOT_DISCLOSED`；
4. 写作问题只通过冻结时的 claim coverage 和链接完整性判定，不得在结果期以文章更顺畅为由改写机制；
5. G1.5 只能报告诊断性结算；任何经验概率或参数校准仍遵守既有模型记忆、样本和 Phase 边界。

### 结果

**H5 的结算方法保留，集成状态为 `INCOMPLETE`。** 根因是 `MODEL + ACQUISITION_MODULE`（对象适配和后续 observations 尚未实现），不是 `WRITING`。这项接线应进入 G1.5 R0/R3.5 作为报告生产前置；否则 24 份产物无法真正形成反馈学习闭环。

## 12. ITER-08 — 前瞻判断到结算 claim 的语义保真测试（2026-08-20）

### 具体测试与结果

本轮只检验一个会改变下一步的失败：当前 `thesis_test.forward_judgments` 允许有意义的区间预测（例如 `owner_cash_index=95—105`），而 `historical_backtest.calibration_ledger` 是否能原样冻结并在未来结算。

以同一来源身份、测量口径、报告期、观察窗口、官方来源类型、反方和翻转条件构造两条最小 claim：

| 输入预测 | `historical_backtest._validate_calibration_ledger` | 含义 | 下一步 |
|---|---|---|---|
| `RANGE, range_low=95, range_high=105` | `INCOMPLETE: prediction:missing:value` | 当前结算 schema 只承认一个 `value`，不能保留上下界 | 扩展结算 contract 与 interval settlement；在此之前明确阻断投影 |
| `AT_LEAST, value=95` | 无 `INVALID` 或 `INCOMPLETE` finding | 点预测可在补足来源、阈值和观察窗口后进入现有结算账本 | 用作 adapter 的最小正例，不从价格推断行动 |

这不是“区间难以评分”的理由，而是已有 schema 的可定位边界。把 95—105 取为 100 写入 `value` 会让后来人无法区分“区间命中”与“恰好命中中点”，也会夸大误差；因此严格禁止。

### 文献交叉检验

预测研究的可学习对象是事前声明与事后结果的对应关系，而非事后的好故事。Tetlock 的专家判断研究聚焦怎样评估专家在未来事件上的判断；后续研究也把 past performance 和可观察的 forecast-updating 行为作为后续准确性的输入，而非以文章流畅度替代结算。[Expert Political Judgment（出版社目录）](https://assets.press.princeton.edu/catalogs/polisci17.pdf) [Forecasting forecaster accuracy](https://www.cambridge.org/core/journals/judgment-and-decision-making/article/forecasting-forecaster-accuracy-contributions-of-past-performance-and-individual-differences/914F973B8C6A9CDCD3F1EA7CF17048D2)

Penman 的“以可观察会计基本面锚定价值”同样支持保留原始经营量纲，而不是为了让估值或结算器易用而改变预测定义；它不支持为格力或任何公司填入区间中点。[Accounting for Value](https://cup.columbia.edu/book/accounting-for-value/9780231151184/)

### 结论、根因与可执行修复

**H5 的适配结论从“尚未接通”收紧为：点预测可适配，区间预测当前不可无损适配。** 根因是 `MODEL`（冻结/结算 schema 只定义点值与单点 `forecast_value`），并牵连 `ACQUISITION_MODULE`（每项判断尚未保存可回填的 PIT 来源身份、阈值和观察窗口）。经济影响在于：若把区间压为中点，会扭曲对正常利润、owner cash、估值和预期回报判断的命中/偏差，进而给 24 个 episode 制造虚假的校准改善。

缺失的不是更多格力报告或文笔，而是每项判断的投影字段：`calibration_claim_id`、PIT `source_ids`、historical materiality、同指标的阈值及后果、观察窗口，以及对 `RANGE` 的上下界/命中规则。禁止假设：区间中点等于预测、领先阈值自动等于结果阈值、`evidence_id` 自动等于 PIT source ID、或好的经营预测必然等于好的投资回报。

可执行修复顺序：

1. 在 G1-J 的前瞻判断 schema 中登记上述投影字段，并在写入时验证其完整性；
2. 为 `historical_backtest` 增加区间预测及其 `inside_range / below_range / above_range` 结算身份，同时保持现有点预测夹具兼容；
3. 以一个历史 PIT 公司—时点完成点值和区间各一条端到端冻结—追加结算；只在二者均无损、来源可审计且独立审阅冻结后，才允许 R0 退出。

验收标准：范围预测不能被转换成点值而通过；有完整上下界、实际观察和合格来源的范围预测能返回明确的区间结算；任何缺少来源、阈值或观察窗口的前瞻判断被标为 `INCOMPLETE`，而非由 adapter 填空。

### 区间结算原型结果

该修复已在同一 research worktree 实现：`historical_backtest` 现接受 `RANGE + range_low/range_high`，结算指标必须保留两端并登记 `WITHIN_RANGE / BELOW_RANGE / ABOVE_RANGE`。定向测试结果为：范围 claim 与实际值 0.18 在 0.15—0.25 内时，案例与结算均为 `REVIEWABLE`；额外填入 0.20 的 `forecast_value`（中点替换）被判 `INVALID: range_prediction_cannot_carry_point_forecast_value`。点预测既有夹具保持通过。

因此 ITER-08 的区间 `MODEL` 缺口已缩小；未完成的是 `forward_judgment → calibration_ledger` 的无人工重抄 adapter、真实 PIT 采集和独立审阅，不能把这个 schema smoke test 当作格力或 24 个 episode 的预测表现。

### 投影器原型结果

在 `phase10_backtest_case_adapter` 中补入纯投影函数：它从完整 `thesis_test` 读取前瞻判断和竞争解释，并要求每项判断的 `settlement_contract` 已冻结 `HBTCLM:` claim ID、PIT `source_ids`、材料性、同指标阈值及观察窗口。它只复制主预测（包括 `RANGE` 上下界）、结果测量规则、反方、反证、中心路径/机制链/基线身份；不会补来源、取区间中点、读取后续结果、制造价格或行动。

定向测试中，3 条前瞻判断无人工重抄地生成 3 条可被 v2 settlement validator 接受的 claim；其中 `owner_cash_index` 的 `95—105` 区间原样保留。把 admitted PIT source 集置空，投影器以 `settlement source_ids are not admitted PIT sources` 拒绝。该结果使“对象投影”从 `INCOMPLETE` 进展为可用研究原型；真实生产 adapter、审阅合同和格力 PIT 源包仍未接通。

## 13. ITER-09 — 行业机制判断是否胜过简单基线（2026-08-20）

### 研究问题

即使 24 份报告都冻结且结算，仍不能只看“预测是否正确”。家电需求、份额、现金转换和利润率存在趋势、均值回归和共同宏观冲击；复杂行业叙事如果不超过同 cutoff 的简单预测，便没有证明自己提供了增量判断力。

这是对“计算准确但没有未来判断”的直接测试，不是以一个线性模型替代投资研究。Dawes 的经典综述表明，简单且透明的规则可作为对临床式直觉判断的强挑战；预测组合研究也一再把简单规则作为复杂方法的基准，而不是把复杂度本身当作准确性的证据。[Dawes, *The Robust Beauty of Improper Linear Models*](https://web.stanford.edu/~knutson/jdm/dawes79.pdf) [Forecast combinations: an over 50-year review](https://www.sciencedirect.com/science/article/pii/S0169207022001480)

### 现有能力与缺口

现行 `forward_judgment` 契约有预测、机制、反方、阈值与结果口径，却没有：

- `baseline_id`、方法和同 cutoff 输入；
- 基线本身的点值/区间输出及适用条件；
- 机制判断与基线在同一指标、单位、期间和披露版本上的相对结算；
- 将相关 company×time episode 按公司、时期、机制聚类后再看结果的规则。

因此目前无法回答“格力的行业深度比收入持续、行业调整持续或一条透明驱动规则多带来了什么”，也不能事后挑一个失败基线来衬托报告。这是 `MODEL + ACQUISITION_MODULE` 缺口，不是 `WRITING`。

### 最小预注册方法

对于每项**可量化**前瞻判断，报告冻结前选择且只选择一个适合其量纲的简单基线：

| 预测对象 | 允许的简单基线示例 | 禁止的捷径 |
|---|---|---|
| 同口径收入/销量/份额 | 最近可见同口径值持续；或相对官方行业增速不变 | 用后验行业销量、当前价格或同业事后报告调基线 |
| 毛利、费用率、现金转换 | 最近完整年度/TTM 的同口径持续，明确一次性项目处理 | 把管理层愿景或对手结果写成“基线” |
| 资本配置结果 | 已披露承诺/资金占用的零改善或保守兑现规则 | 用事后减值、退出或股价表现倒填 |
| 区间预测 | 基线也冻结上下界及相同结算口径 | 把机制区间压成点值后才比较 |

中心路径只能由证据、竞争解释和机制链选择；基线不参与投票。结果期只追加相对误差、区间命中和能够改变决策的反例。因为 18 个 company×time episode 高度相关，G1.5 仅报告覆盖、聚类和方向性诊断；不以一次胜负优化权重、概率或 `lambda`。

### 结论、修复与验收

**H1 获得更严格的可测试形式，但尚未有数据验证。** 经济价值是把行业研究从“解释更多”提升为“比透明替代方案多预测了什么”；若无法胜过基线，结论应降级为解释性研究，而非被用于提高概率或估值确信度。

修复顺序：先在前瞻判断/结算 schema 增加基线身份和同口径输出，再让 `financial_driver_bridge` 提供其 PIT 输入，最后在一个真实历史 episode 做机制预测与基线的双结算。验收标准：基线与机制预测均在结果前冻结；二者共享指标、单位、期间、来源版本与区间语义；任何无基线、不可比或读取价格/后验结果的比较被标为 `INCOMPLETE`；小样本结果只输出诊断，不自动校准模型参数。

### 契约原型与定向验证

研究 worktree 已在现有 `thesis_test` 的每项 `forward_judgment` 内增加一个最小 `baseline` 对象，而非另建预测系统。它要求唯一 ID、三种透明方法之一、声明和适用边界、截止日前证据 ID，以及与主判断完全同指标/单位/期限/到期日的点值或区间输出。

定向 smoke test 的结果：

- 完整前瞻判断 + 基线：`REVIEWABLE / DECISION_READY`；
- 删除基线：`INCOMPLETE / INCOMPLETE`，含 `fj.retention:baseline_missing`；
- 把基线单位由 `%` 改为 `RMB/share`：`INVALID / INVALID`，含 `baseline_prediction_unit_does_not_match_judgment`。

这验证的是**可比性和冻结边界**，不是基线已经赢过或输给机制判断。点值/区间的历史 settlement 仍受 ITER-08 的区间缺口约束；当前格力候选也仍缺中心路径、前瞻判断和真实 PIT 版本，不能拿本夹具宣称具有回测表现。

## 14. ITER-10 — 从“多报告”到可比较的机制 episode（2026-08-20）

### 文献复核后的研究方法

1. **Structured-focused comparison。** 18 个公司—时点对象必须回答同一组、由机制理论决定的问题；否则只是 18 篇文章，不能累积比较。George 与 Bennett 将这类方法定义为对跨案例可累积的、结构化的相同问题，而不是统一文风或表格。[Case Studies and Theory Development](https://mitpress.mit.edu/9780262572224/case-studies-and-theory-development-in-the-social-sciences/)
2. **过程追踪 + 反例。** 单个公司中的“渠道、价格或会计异常”只能是终局之间的机制/证据质量问题。每条机制链需有起始条件、中间机制、可观察信号、财务驱动、替代解释和最终结果；单案不能证明一般因果，必须与跨案例反例共同使用。[Process Tracing](https://www.cambridge.org/core/books/process-tracing/5BBC24CBF2E89114817741D0476C07A9)
3. **外部视角的参考类。** 参考类先冻结预测对象、期限、截止日可见状态变量、候选宇宙、排除规则和独立簇，才允许输出分位数。相似状态的样本外参考类是公司预测的可行方向，但“几篇熟悉类比”或相关小样本不是经验频率。[Lovallo, Clarke & Camerer](https://sms.onlinelibrary.wiley.com/doi/10.1002/smj.962) [Theising, Wied & Ziggel](https://onlinelibrary.wiley.com/doi/10.1002/for.2927)
4. **资本配置结果追踪。** 不把 `lambda` 或管理层气质当事实。每一项材料资本配置应留下金额、资金来源、承诺、兑现期和后续现金/减值/退出观察，才有资格影响 owner cash 或永久损失。管理层过度自信与投资决策的文献只支持做事件追踪，不为格力贴标签或提供参数。[Malmendier & Tate](https://www.nber.org/papers/w10807)

### 对格力与 24 个产物的可执行含义

这批产物的有效单位是 `mechanism_episode`，不是报告：`company / cutoff / industry regime / source package / common question set / terminal outcome / mechanism chain / strongest alternative / financial driver bridge / forward judgments / baseline / eventual settlement / company-period-mechanism cluster`。综合报告不进入参考类分母；同公司跨期、同一市场冲击或相互影响的卖方材料不能被当作独立成功次数。

对格力的即时影响是：格力钛、盾安协同、短期借款及投资现金流用途不能再被一个参数折减或一段叙述替代。每一个可能改变 `lambda`、normal owner cash、价值或永久损失的资本事项先成为 `allocation_event`；官方资料不足时为 `UNKNOWN`，不得用 20 份报告里的相同主张补齐。

### 结论与验收

**20+ 份报告的方法有条件保留，但不扩容。** 根因仍是 `REASONING + DATA_COVERAGE + ACQUISITION_MODULE`：当前缺可比的 episode、历史源包和资本配置实际结果，而不是缺更多写作或计算。新增验收为：每份 PIT 报告回答共同机制问题、登记独立簇和反例；每个参考类先有冻结 spec 或 `UNKNOWN`；每笔影响资本纪律的事项有事件账或 `UNKNOWN`；最终只报告覆盖/反例/逐项结算，直到合格独立样本数满足既有 `ELIGIBLE` 契约。

## 15. ITER-11 — 格力现金转换与资本配置的可采集驱动桥（2026-08-20）

### 要检验的失败

格力现行报告把 2025 年经营现金流、投资现金流和 `lambda` 放进了估值/回报叙述，但关键组成没有结构化、没有模型输入绑定。要检验的具体失败是：一次性受限资金释放会不会被当作常态 owner cash；金融产品滚动会不会被当作经营外价值毁损；格力钛减值会不会只被一段文字带过而不影响永久损失判断。

### 只读官方年报结果

新规则在格力 2025 年报上取得了以下 VERIFIED 字段（单位：亿元，四舍五入）：

| 字段 | 2025 年报观察 | 对模型的正确作用 |
|---|---:|---|
| 经营现金流 | 463.83 | 不能直接等同常态 owner cash |
| 经营相关受限资金净减少 | 156.67 | 作为一次性释放从 owner-cash 正常化中剔除；粗略差额为 307.16 |
| 金融产品/大额存单等申购 | 616.61 | 首先归为流动性管理待检验，不能自动当作经营再投资或价值毁损 |
| 同类产品赎回 | 284.55 | 与申购、定存和期限共同解释，不能孤立取一笔投资现金流 |
| 定期存款净增加 | 249.12 | 说明投资现金流的金融资产滚动部分 |
| 格力钛在建工程减值 | 11.42 | 材料性资本配置事件，影响永久损失/资本纪律；独立现金流、追加投入和退出路径仍为 `UNKNOWN` |
| 利息收入 / 利息费用 | 58.85 / 19.65 | 不支持仅凭短期借款就断言负利差或资金错配 |

这是一条**会改变估值解释**的发现，但不是新投资结论：307.16 亿元也不是已完成的正常化 owner cash，它仍需结合营运资本、维持资本开支、税项和跨期口径。禁止假设：OCF/净利润比直接表示收款质量；线上份额变化代表全渠道结构恶化；金融产品申购等于错误资本配置；或 `lambda=.625` 等于已经损失的 37.5% 利润。

### 可执行修复与验证

新增 `financial_driver_bridge.v1`，每一层（竞争/需求、单位经济性、现金转换、资本配置）均需有状态、观察期、VERIFIED observation、模型输入绑定和决策条目；`UNKNOWN` 必须保留原因和保守处理。资本事件另登记类型、日期、分类依据、兑现窗口和官方 observation。定向测试确认：候选 observation 不能冒充经济证据；缺少任一层或 `UNKNOWN` 的保守处理会被阻断；无 policy 的遗留报告保持 `SKIP`，新启用的运行缺桥则 `INCOMPLETE`。

同时在 `evidence_facts` 增加通用的现金转换和金融产品规则，并以格力年报只读执行验证：提取值覆盖 OCF、客户收款、受限资金释放、金融产品申购/赎回、定存、AR、库存、AP、短借、利息收支和格力钛减值。该修复先处理 `ACQUISITION_MODULE + DATA_COVERAGE`，才允许后续 `REASONING + MODEL` 决定 normal owner cash、资本配置折减和价值区间。

### 验收与下一步

格力 V1 仍不能冻结：必须把这些新 observation 纳入正式冻结源包，为四层驱动写入实际模型 input/决策绑定，补全竞争和单位经济性证据，明确格力钛的保守处理，然后使中心路径、基线和前瞻判断全部结算可追踪。通过后的报告才可进入 R2；本轮 extractor 和 synthetic bridge 测试不能代替该验收。

## 16. ITER-12 — 机制 episode 是否需要另一套案例库（2026-08-20）

### 审核结果

已有资产的职责没有重叠：8 张书籍方法案例卡校准“问什么、做什么、禁止什么”；`base-rate-case` 已有历史截止日、可见证据、预测空间、追加结果和独立资格审阅。它们不能替代彼此，但也不需要再造一个“案例卡/episode 库”。

现有 case 缺少的是让 18 个公司—时点报告可做结构化比较的身份：共同问题、终局经营结果、机制链、最强替代解释、财务驱动桥、同口径基线、以及公司/时期/机制相关性簇。缺这组字段时，库只能在结果后查询机制名，无法判断“这 20 多份报告是否真的回答同一问题、是否把相关观察伪装成独立样本”。

### 修复

将 `episode` 作为原 `base-rate-case.v1` 的可选扩展，而非新库。其最小字段为 `MEP:` 身份、行业阶段、共同问题、终局范围、机制链、替代解释、驱动桥（绑定或诚实 `UNKNOWN`）、前瞻判断 ID、基线 ID、三维 cluster 与结算状态。策略可在 G1.5 启用 `require_episode_identity`；启用后，任何进入参考类上下文的 `ELIGIBLE` case 缺 episode 即为 `INCOMPLETE`。未启用时，旧 9 个候选只收到 warning，保持原有状态和不可变历史。

定向测试确认：完整 episode 可随原 case 通过；缺 cluster、驱动桥或基线不通过 episode 要求；原库仍按 append-only case 与 post-cutoff event 管理结果。这个设计直接满足 structured-focused comparison 的“同问题、可累积比较”要求，又不把公司×时间相关性偷换成经验频率。

### 影响

20+ 份格力/同行报告的方法现在有一条可执行的数据路径，但尚无任何新增 `ELIGIBLE` 基准率。根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`：需要实际 PIT source package、共同问题和后续观察，不能用 schema、篇幅或同一卖方观点的重复来制造判断能力。G1.5 预注册时才打开该 policy；此刻路线图维持 G1-J `IN_PROGRESS`。

## 17. ITER-13 — “读过案例”与“形成判断能力”不是一件事（2026-08-20）

### 文献判断

Kahneman 与 Klein 的边界条件很适合这项路线：主观上觉得熟悉案例，不能证明已经获得专家直觉；要有相对稳定的可预测结构，以及反复、及时而清晰的结果反馈。[Conditions for Intuitive Expertise](https://kahneman.scholar.princeton.edu/publications) 这意味着家电研究不能把“报告读得多”或“股价后来上涨”当作训练信号。

投资研究中存在两类不同任务：

| 任务 | 可学习性 | 合格反馈 |
|---|---|---|
| 披露口径、现金转换、渠道/份额、库存与资本配置事件 | 相对高：事实与短期经营结果可重复观察 | 与冻结口径相同的官方后续观察、机制与基线结算 |
| 3—5 年终局、估值与投资回报 | 较低：噪声、共同时期冲击和价格反身性更强 | 终局/机制/经营预测/回报四项拆分结算，加独立簇和 holdout |

关于股票概率预测的实验研究也表明，只有简单结果通知不够；按任务口径给出结果、并提供总体校准与表现反馈时，技能指标才改善。[Effects of feedback on probabilistic forecasts of stock prices](https://www.sciencedirect.com/science/article/pii/016920709400572T) 因而 Turtle 已有的“冻结—追加结果”方向正确，但还需把错误回顾做成可执行训练，而不是年后写一段复盘。

### 新增训练闭环：episode 预测场，而非阅读清单

每个公司—时点 episode 采用两步：

1. **盲重建。** 研究者只能读取 cutoff 前源包，先冻结终局、3—5 项判断、机制、基线与 action threshold；不读取未来财报或价格路径。
2. **结构化反馈。** 打开结果后，对每项观察显示原判断、简单基线、实际、区间命中、机制归因、口径漂移和投资回报（如可计算）。先判失败类型，再允许写复盘。报告得分、文采和整体股价不能抵销经营预测错误。

每个季度增加一次跨 episode 的校准回顾：按驱动层和聚类报告覆盖、方向/区间结果、基线增量、`UNKNOWN` 解析率和根因；小样本只诊断，不重估 `lambda`、概率或仓位。此设计把 24 份报告用作“有相同题目、真实反馈、反例和基线”的训练场。

### 影响与验收

这条方法解决的是 `REASONING + MODEL`，前提是 `DATA_COVERAGE + ACQUISITION_MODULE` 已提供同口径的结果。它不会承诺 18 个相关历史点足以建立稳健的长期投资直觉；反而要求把长期判断降级为带不确定性的学习对象。验收标准是每个可结算 episode 都产生任务格式的反馈记录，并在至少一个未参与规则形成的公司/时期 holdout 上重复；否则“行业深度提升”只能停留在解释质量，不得提高估值确信度。

## 18. ITER-14 — 股价最重要也是最不重要（2026-08-20）

用户明确的第一性原则改变的是排序，而不是删除价格：公司经验（冻结时的公司事实、机制、资本配置判断及其后续结算）是训练判断力的根本；股价决定安全边际、预期回报和是否行动，因而对投资不可缺少。但价格不是公司经营真相，也不能由市场共识反向选择中心路径。

落地为双轨约束：先在经营盲源包中完成 `company evidence → terminal outcome → mechanism → financial driver bridge → value condition`；随后才读取同 cutoff 的市价，计算市场隐含路径及条件回报。二者冲突时只产生待研究问题，例如“市场是否预期竞争恶化超过公司证据所支持的程度”，绝不以价格替代证据、提高概率或改写原判断。结果期同样分开结算经营、机制、估值和回报；一次赚钱不能洗白错误的公司判断，一次股价不动也不能自动否定正确但尚未兑现的经营诊断。

这把 24 个 episode 明确定位为公司经验工厂，而非价格预测竞赛。根因分类也随之清楚：公司事实不足先归 `DATA_COVERAGE/ACQUISITION_MODULE`，解释与因果错误归 `REASONING`，从公司驱动到价值/回报的传导错误归 `MODEL`，而不是用市场结果或写作质量混淆责任。

## 19. ITER-15 — 经营驱动桥必须穿过 PIT 冻结（2026-08-20）

### 要检验的失败

`financial_driver_bridge` 若只在普通报告完成门中出现，而不进入发布快照和 PIT production adapter，系统仍可能把“经营、现金转换与资本配置没有连接到价值/动作”的报告冻结为可回放案例。那会使格力的 2025 年 OCF 一次性释放、金融产品滚动和格力钛减值重新退化为漂亮但不可结算的文字。

这属于 `ACQUISITION_MODULE + MODEL`：前者没有把四层事实作为冻结对象传到 snapshot，后者没有把它作为“可回放”的必要经济关系。经济影响是错误 normal owner cash 或资本纪律判断会被带入 EPV、预期回报和永久损失评估，却在历史训练中显示为一个貌似合格的 episode。它不是 `WRITING` 问题。

### 实现与验证

新运行会启用经营驱动桥 policy；代理先读取 `financial_driver` 精确契约，再写四层驱动及资本事件，且只能把 VERIFIED observation 绑定至已有估值模型输入和决策条目。PIT production writer 也有同一受限入口。`publication_snapshot` 现在显式记录 `financial_driver_bridge_required`；若 policy 启用而桥未达 `REVIEWABLE`，快照不写入；即使人为构造 snapshot，Phase 10 adapter 也会拒绝该冻结。

定向验证结果：

- 代理 writer + contract 可写入四层 bridge，并明确“价格不是经营驱动证据”；
- bridge 缺失时 completion 为 `INCOMPLETE`；
- bridge 未完成时 PIT snapshot 拒绝；
- snapshot 声明 bridge 必需但没有该门状态时 PIT adapter 拒绝；
- PIT production 的已绑定工具集包含该 writer；
- 修复了前瞻基线 tool schema 中小写 JSON `true` 造成的 Python 加载错误。

这不表示格力 V1 已经具备 bridge：实际候选还未将新抽取的官方 observation 写入正式 PIT 源包、估值模型或决策账本。禁止假设合成测试的 `REVIEWABLE` 等于格力的经济结论成立，或一个合格价格回报能代替桥的经营结算。

### 下一步与验收

下一步只允许在真实格力冻结源包内补齐四层 bridge：竞争/需求和单位经济性要由同一 cutoff 的官方证据闭合；受限资金释放需成为 normal owner cash 的明确排除/敏感性；金融资产滚动与格力钛各自保留分类依据和保守处理。然后写中心路径、基线和 3—5 项前瞻判断，才可申请真实 PIT freeze。验收是 `financial_driver_bridge_validation=REVIEWABLE`、publication snapshot 已写入且所有来源可见、adapter 无人工补字段通过；否则继续保留 `INCOMPLETE`，不进入回测或参考类分母。

## 20. ITER-16 — 格力四层 bridge 的隔离真实样本实验（2026-08-20）

### 假设

若 2025 年报已含公司竞争、单位经济、现金转换和资本配置的原文，真正阻塞格力 V1 的应是“这些事实没有成为同一 cutoff、带身份、可连接模型/动作的对象”，而不是还需要再读 20 份相似报告。该假设可由不改写现行候选的隔离副本检验。

### 实验

以单一 2025 年报建立临时 source manifest，重新运行通用 `evidence_facts`；复制既有 `valuation_model` 和 `decision_ledger` 仅用于验证已有 ID 的绑定。新采集规则分别提取：家用空调线上零售额占比 24.31%、消费电器毛利率 35.28%、OCF 463.83 亿元、经营相关受限资金释放 156.67 亿元、金融产品申购/赎回/定存净增以及格力钛工程减值 11.42 亿元。全部保留原文页码和 observation 身份。

桥的经济设计没有使用股价：

- 线上份额只做渠道竞争的 sensitivity，禁止外推为全渠道份额；
- 消费电器毛利率只做核心产品单元经济的边界，禁止充当合并利润率或未来点值；
- 受限资金释放以 `NORMALIZATION_ADJUSTMENT` 从 normal owner cash 排除；
- 金融资产滚动为 `UNRESOLVED`，不计入 owner cash，也不给予经营资产或可分配现金信用；
- 格力钛减值为 `VALUE_DESTRUCTIVE_CANDIDATE`，其独立现金流和退出路径继续为 `UNKNOWN`。

结果：四层 bridge 通过 `REVIEWABLE`。这证明 `ACQUISITION_MODULE` 已能形成一个真实、可审阅的公司经验对象；不证明现行格力报告已完成，因为该报告没有把新 observation 纳入自己的冻结源包、正文和后续判断。

### 根因更新与验收

格力当前最重要的缺口已从“是否能取得四层事实”转为 `REASONING + MODEL`：需要以同一 2025 cutoff 选择 3/5 年经营终局，明确周期/结构竞争解释，写 3—5 条带基线与结果合同的前瞻判断，并将 bridge 对 EPV/DDM 的 normal owner cash、资本纪律和价值区间影响重算。禁止把 2026 年后披露、现价或这次临时 `REVIEWABLE` 回填进 2025 年判断。

下个验收实验必须在真实 PIT source package 完成同一 bridge，并通过 snapshot/adapter；随后才可打开后续披露去结算，而不是立刻把这份样本计入参考类或宣称行业判断能力已经提升。

## 21. ITER-17 — 前瞻判断必须从冻结账本进入生产回放（2026-08-20）

### 要检验的失败

此前虽然有 `forward_judgment → calibration_ledger` 的纯投影器，但 production adapter 仍只接收调用者提供的 ledger。调用者可以在报告冻结后重写预测、删去不利判断，或把区间暗中改为点值，再把“回测”误称为原研究的结算。这是 `ACQUISITION_MODULE + MODEL` 的断裂：PIT 报告有判断，回放 case 却不必是同一判断。经济影响是经营预测的好坏无法归因，20 多份报告会变成不可比较的叙述材料，而不是公司经验。

### 修复与实验

production adapter 新增唯一显式模式 `{"source": "FROZEN_FORWARD_JUDGMENTS"}`。进入该模式时，它：

1. 读取 production output 内的 `thesis_test.json`；
2. 比较原始字节的 SHA-256 与 `publication_snapshot.ledger_sha256.thesis_test`；
3. 仅以 snapshot 已准入的 PIT source IDs 投影每条前瞻判断；
4. 将投影后的 ledger 放入待独立审阅的 frozen contract；
5. 仍强制价格身份和投资动作为 `UNKNOWN`，因此只结算经营判断，不伪造投资回报。

定向测试覆盖五种会改变下一步的失败：正常投影、未准入来源、完整生产冻结到独立审阅、ledger 哈希不匹配、启用但不合格的财务驱动桥。五项均通过；哈希不匹配被明确阻断。这也修正了首次测试暴露的真实缺口：投影 claim 必须实际出现在冻结报告中，且独立审阅逐条覆盖，不能只存在于 JSON。

### 结论与边界

这一轮关闭的是“手写平行结算账本”的工程断点，不是格力 V1 的研究判断。格力当前仍没有真实 PIT source package、正式 `thesis_test`、独立审阅或可冻结的中心路径；因此不得把 adapter 测试、价格变化或隔离 bridge 的 `REVIEWABLE` 当作格力的未来判断已完成。下一实验仍是用真实格力源包走完 bridge → 公司终局/机制/基线 → 哈希快照 → 独立审阅，之后才允许追加结果。

## 22. ITER-18 — 结果结算必须反馈“哪条公司判断错了”（2026-08-20）

### 新的文献检验

仅把结果、回报或总分展示给研究者，未必提高下一次的判断。Remus、O’Connor 与 Griggs 在有结构不稳定性的判断预测实验中发现，提示时间序列的任务结构与输入信息优于只告知上次预测准不准；Benson 与 Önkal 的实验也显示校准反馈比简单结果通知更有效。[Does Feedback Improve the Accuracy of Recurrent Judgmental Forecasts?](https://www.sciencedirect.com/science/article/pii/S0749597896900357) [The effects of feedback and training on the performance of probability forecasters](https://www.sciencedirect.com/science/article/abs/pii/016920709290066I)

这与 Turtle 的目标直接相关：如果格力的“周期修复”判断失败，研究者需要看到的是当时哪项渠道、单位经济、现金转换或资本配置传导被证伪，而不是只看到股价、XIRR 或一条“判断错误”。否则公司经验无法累积，价格会重新吞没第一性研究。

### 路线修订

R3.5 的每个已结算或诚实 `UNRESOLVED` 判断新增一个**任务信息反馈卡**，最小内容是：

1. 原始中心终局、竞争解释、机制链和前瞻判断；
2. 实际结果、同口径简单基线与区间/方向身份；
3. 竞争/需求、单位经济、现金转换、资本配置四层中哪一层有可观察反证或仍缺数据；
4. 受影响的 normal earnings、owner cash、估值与回报输入；
5. 一个且仅一个主要根因，或显式保留多重/未知；价格回报单独列示、不得作为经营根因。

这不是增加一个总评分表，也不让事后写作重构历史。它只能读取冻结的 claim、bridge、基线与追加 observation；不能修改原报告、替换模型参数或用排名决定中心路径。

实现审计同时发现：production adapter 原先只保留 `baseline_id`，导致日后无法从冻结 case 比较“机制判断”与当时的简单挑战者。现已将完整 frozen `baseline` 和四段 `transmission` 与 claim 一起投影，并以 production snapshot→独立审阅夹具回归验证；它们不参与结果期计算，也不引入任何事后字段。

最小反馈模块 `judgment_feedback` 已以 v2 冻结 case 和官方 outcome fixture 验证：当 owner-cash 判断失败而同口径 carry-forward baseline 成功时，卡片返回 `BASELINE_BETTER`，同时保留机制链、传导和待人工判定的根因；它不输出投资回报数值。缺失 frozen baseline 会拒绝生成卡片，不能在结果期重造一个基线。

## 23. ITER-19 — 简单基线不能只是“一个自称简单的数字”（2026-08-20）

### 要检验的失败

此前 `baseline` 有方法名、输入 evidence ID 和预测输出，却没有可复算的数值输入或公式。研究者可以把复杂判断的同一个数重新命名为 `CARRY_FORWARD`，再在结果期宣称行业机制“优于基线”。这会直接破坏 H5 的增量信息检验，根因是 `MODEL + REASONING`，不是写作问题。

### 修复与测试

三类允许的简单基线现在各有唯一可验证公式：

- `CARRY_FORWARD → LAST_OBSERVED_VALUE`：一个同口径、带 evidence ID 的最近观察；点预测必须相等，区间预测必须是该点的零宽区间；
- `INDUSTRY_ADJUSTED_CARRY_FORWARD → COMPANY_LEVEL_PLUS_INDUSTRY_DELTA`：公司前值加同口径行业变化；
- `EQUAL_WEIGHT_DRIVER_RULE → EQUAL_WEIGHT_NUMERIC_DRIVERS`：至少两个同单位驱动的等权平均。

验证器同时检查每个输入的 evidence 身份、单位、角色和公式输出。定向回归中，完整前瞻判断仍为 `DECISION_READY`；将 carry-forward 输入从 90 改为 80 而不改预测输出，明确返回 `baseline_carry_forward_value_does_not_match_input`。writer schema 和运行指引也要求代理先提交该计算合同。

### 边界与验收

基线仍是**挑战者**，不是中心路径投票器，更不是行业参数估计器；三个规则不能涵盖有非线性或口径变化的所有经营问题，不能表达时应登记 `UNKNOWN` 或先扩充公共规则。首个真实格力 PIT judgment 只有在基线输入来自同 cutoff 的官方 evidence、公式可重算、结果期与机制判断使用同一 observation 时，才可报告“相对基线增量”。

## 24. ITER-20 — 格力旧完成状态与新判断门的边界（2026-08-20）

### 只读审计

现有格力候选的 `thesis_test_validation=DECISION_READY` 与 `completion_report=COMPLETE` 容易造成错误乐观。回读原始工件后，旧 policy 是 `thesis-test-policy.v1`，不含 `forward_judgment_required`；其 ledger 只有竞争测试、阈值和概率集，缺少新合约的中心路径、机制链和 3—5 个结算判断。其 2025 年报文件虽已缓存，但 document manifest 的 `published_at`、`source_url`、PIT `source_id` 都为空，且不存在 driver-bridge policy。

这说明旧结果没有“冒充通过”；它只是在旧审阅范围内通过。真正错误会发生在把这个旧范围结果外推为当前研究质量、PIT source package 或行业经验。根因分类为 `ACQUISITION_MODULE + REASONING + MODEL`：来源身份无法形成时点围栏，判断没有冻结对象，财务驱动无法进入价值传导。

### 可执行结果

格力 V1 不做原地修补或重标。应建立新的、隔离的 source package：完整法定披露公告清单先于 source 选择；每项来源有发布日期、数据期、原始版本和可读 representation；随后重走 official facts → bridge → 经营盲轨终局/机制/可计算基线 → 前瞻判断 → snapshot/独立审阅。当前目录继续保留为旧候选与反例，避免把 2026 年之后资料或新规则回填为“2025 当时的判断”。

## 25. ITER-21 — 深交所/巨潮披露清单的 PIT 入口（2026-08-20）

### 假设

若格力不能进入真实 PIT，不应假设原因只是缺少报告内容；首先要验证通用 acquisition 模块能否忠实接受深交所法定披露清单。否则即使取得了完整清单，系统也会把它降级为手工文件，继续无法冻结时点。

### 实现与结果

新增离线 `CNINFO` 规范化入口，输入是已经导出的官方公告行，而不是实时搜索网页。每一行必须有证券代码、公告标题、公告 ID、法定附件 URL 与发布日期；定期报告标题会生成数据期，其他公告默认以公告日为数据期。完整清单进入原有 admission 规则，所有 cutoff 后行仍保留并标记 `REJECTED_FUTURE_PUBLISHED_AT`。

以格力 2025 年报的标题/日期语义构造一条 CNINFO 格式年报行并加入未来公告做隔离测试：年报被规范成 `ANNUAL_REPORT / data_as_of=2025-12-31`，未来公告被拒绝，完整 manifest 为 `REVIEWABLE`；缺 URL 的行被拒绝。该测试修复的是 `ACQUISITION_MODULE` 的交易所覆盖缺口，而非验证某一真实公告 ID。

### 边界与下一步

这不是“格力 PIT package 已完成”。完整性只能由实际导出中每页/总数/日期范围的官方清单证明；此处的单行和未来行只证明规范化和 admission 语义。下一步需要保存一份指定 cutoff 的完整 CNINFO/深交所导出，再下载/物化其已选择的 PDF，才能让 runner 读取公司证据并生成真正的 V1。

### 验收与边界

首个真实 PIT episode 开放结果时，抽取一条失败、成功或 `UNRESOLVED` 的判断，独立审阅者能从反馈卡追到冻结合同和官方后续 observation，并能区分“机制错”“模型传导错”“数据当时不可得”与“未结算”。若只能展示收益或文采评分，H5 仍为 `INCOMPLETE`。

## 26. ITER-22 — 区分信号必须有真实的诊断性（2026-08-20）

### 要检验的失败

原合约只要求主解释和反方对同一观察写出两句不同的预测。两句措辞即使不同，也可能代表相同的预期，或某个观察在两种解释下都很常见；此时它不能帮助研究者在新披露出现后更新公司判断。根因是 `REASONING + MODEL`：报告看似有“反方”和“监控”，但不能区分周期、竞争、渠道或会计等并存过程机制。经济影响是中心路径可以被叙事保护，格力及后续 20 多份报告只能累积材料、不能累积可纠错的公司经验。

### 文献与最小修复

过程追踪的核心不是为故事补充更多事实，而是用观察在竞争解释间的可区分性来更新判断；Bennett 与 Checkel 的方法论专著将替代解释和证据的诊断性作为过程追踪的中心问题。[Process Tracing: From Metaphor to Analytic Tool](https://www.cambridge.org/core/books/process-tracing/5BBC24CBF2E89114817741D0476C07A9) 这不授权在小样本公司研究中伪造精确贝叶斯因子。

因此每个前瞻判断所依赖的区分观察现在必须冻结：主解释下的 `LOW` / `MEDIUM` / `HIGH` 可能性、最强反方下的同一等级，以及说明经济机制的理由；两个等级必须不同。它是粗粒度诊断性检查，不是新评分表、概率估计器或由价格/回报反推的标签。

### 实验与验收

定向回归保留一个可通过的主/反方非对称样本；把反方可能性改成与主方相同，验证器将返回 `diagnosticity_not_asymmetric`，并使前瞻判断门为 `INVALID`。缺少对象、等级或理由也会留下可执行的 `INCOMPLETE` finding。writer schema 与生产提示同步要求该字段，因此新报告无法仅靠不同措辞绕过。

边界：该规则不证明某项观察真的会发生，也不证明中心路径正确；它只排除“无信息增量却被称为区分信号”的写法。真实格力 V1 仍须先建立 PIT source package 和冻结 bridge，才能将渠道份额、毛利、受限资金释放、资本配置等候选观察写入并接受独立审阅。

## 27. ITER-23 — 反馈必须回到冻结的公司驱动层，而非事后重写（2026-08-20）

### 要检验的失败

上一轮反馈卡已保留机制链、基线和四段财务传导，但没有保存四层 `financial_driver_bridge` 本身。结果出现后，研究者仍可能用新披露重写“当初究竟依赖了渠道、单位经济、现金转换还是资本配置的哪项事实”。这是 `REASONING + MODEL` 的时间泄漏：复盘看似细致，却无法辨别最初的公司经验、模型传导和后验解释。

### 修复与实验

当 PIT snapshot 启用 financial-driver bridge，production adapter 现在只接受快照中 SHA-256 一致的 `financial_driver_bridge.json`，把四层 driver、allocation events 和 ledger identity 作为 `frozen-financial-driver-bridge.v1` 放入 case，并纳入独立审阅的 frozen contract。每条 forward judgment 同时必须列出其依赖的 `financial_driver_ids`；缺失或引用桥中不存在的 ID 时 adapter 拒绝投影，不能让结果期补连。

反馈卡只读取这份经独立审阅的副本，并按竞争/需求、单位经济、现金转换、资本配置四层回显 drivers、与该判断的链接和 allocation events。没有 bridge 的旧 case 仍可结算，但明确标为 `NOT_PRESENT_IN_LEGACY_FROZEN_CASE`；它不能伪装为四层归因。卡片继续把 investment return 排除在公司经营根因之外。

定向回归覆盖：相同 snapshot hash 的 bridge 被保留；修改任何 bridge 字节后被拒绝；启用 bridge 却未给 forward judgment driver link 被拒绝；反馈卡显示所有四层和特定 cash-conversion link。此处不根据价格或结果估计驱动权重，也不把全桥强行归因给每一条判断。

## 28. ITER-24 — 20 份报告不能以“报告数”进入经验概率（2026-08-20）

### 重新核对现有 episode 实现

项目已经有 `mechanism_episode`，并已要求共同问题集、终局范围、机制/判断/基线身份、driver bridge 和公司/时期/机制 cluster；因此不需要新建第三套案例卡。实查却发现 query 仍将每个 `ELIGIBLE` case 逐条计入 `eligible_sample_size` 和经验频率，完全没有使用现成 `cluster.company_id`。六份同一公司不同时点报告会被当成六个独立观测，这是 `MODEL + REASONING`，会把“增加格力报告”误写成已校准的 base rate。

### 方法与修复

structured-focused comparison 的价值来自以共同问题比较案例，而不是把同一组织的多篇叙述相加；公司×时点 episode 仍可提供机制覆盖、反例和预测结算，但独立性必须单列。[Case Studies and Theory Development in the Social Sciences](https://mitpress.mit.edu/9780262572224/case-studies-and-theory-development-in-the-social-sciences/) 因此 query 现在同时返回原始 `eligible_sample_size`、`independent_company_sample_size` 和 `independence_qualified`：只有每条引用都有冻结 company cluster、且每家公司只有一个 episode 时，才生成 empirical base rate。没有预注册的公司内聚合规则，多个时期不被任意挑选、平均或投票。

六个同公司已结算 episode 的定向实验保留 coverage=6，却只给 independent company sample=1、`empirical_base_rate=null` 和明确相关性 warning；五个不同公司、同机制 episode 仍产生 `0.4 / 0.6` 的频率。任何在 thesis 中标作 `base_rate` 的 case refs 还会被复核：缺少 episode company cluster 或多个 refs 属于同一公司，验证器拒绝它们。

### 对格力 20 多份报告的结论

它们有价值的前提是分别留下冻结预测、机制、基线、结果和反例；这样可以加深格力的公司经验和机制覆盖。它们**不能**单独增加经验概率分母，也不能取代跨公司同行比较。只有在事前规定公司内怎样把多个时期聚合成一个独立比较单位、并在未见结果的公司/时期继续验证后，才讨论更复杂的层级统计；当前正确输出仍是逐条误差、反例和 `UNKNOWN`，不是“20 个样本的概率”。

## 29. ITER-25 — 同机制也必须回答同一问题，才可形成参考类（2026-08-20）

### 要检验的失败

`mechanism_episode` 虽已记录 `common_question_set_id` 和 `terminal_outcome_scope`，旧 query 却只按 mechanism key 查询。这样“线上份额是否代表结构性流失”“受限资金释放是否可持续”“金融资产滚动是否损害资本效率”即使都被笼统贴为同一机制，也会被混成一个频率。根因是 `REASONING + MODEL`：相同词不是相同预测对象，混合终局和混合问题会令所谓行业分析只剩事后类比。

### 修复与验收

参考类 query 现在同时回显共同问题集和终局范围；只有每条 episode 都有这两项身份、且全部一致，才可能产生 empirical base rate。五个不同公司的同机制案例若被分成两个问题集，原始覆盖仍为 5、独立公司数仍为 5，但 `independence_qualified=false`、频率为空并给出 `mixed_common_question_sets_prevent_base_rate`。thesis 若强行把混合来源标为 `base_rate`，验证器同样拒绝。

这把 structured-focused comparison 落到可执行边界：比较的是同一个事前问题和同一个终局空间下的机制 episode，而不是看上去相似的公司故事。它不要求今天定义完整的统计模型；没有预注册 `reference_class_spec` 时，正确结果只是公司证据、机制反例和主观/宽区间判断。

## 30. ITER-26 — 当前格力目录不是“20 多份独立报告”的样本库（2026-08-20）

### 只读核对

在当前 canonical `phase08_20260803` 目录，`document_manifest` 有 13 份缓存披露：8 份年报和 5 份中报等原始材料；13 份的 `published_at` 与 `source_url` 都为空。`reports/` 下三个非草稿发布名（“最新”“最新年报”“2025 年报”）内容相同，因此是同一报告的别名而不是三次独立研究。目录没有可用的 `publication_snapshot.json`；completion 内只保留 dry-run snapshot，且其中仍有未解析来源。

这说明这批材料对事实与历史机制重建有价值，却尚不能作为 PIT episode，更不是 13 或 20 多个独立判断样本。旧 `thesis-test-policy.v1` 只有一个竞争测试/概率集/阈值，缺中心路径、机制链和 forward judgments；它的 `DECISION_READY` 只在旧合约范围内成立。

### 处理

将材料按用途拆开：年报/中报先进入带发布日期和法定 URL 的完整 source package；每个指定 cutoff 再产生**一份**冻结的公司×时点报告、3—5 条判断与一个 mechanism episode。重复发布名只保留作为报告版本身份，绝不计数。若用户所说的 20 多份是该目录之外的卖方/历史研究，下一步应先为每份登记原始发布日期、作者/来源、当时预测、共同问题、终局空间、PIT 证据和后续结果；不满足这些字段的材料仍可做争议主张索引，不能进入校准或参考类。

## 31. ITER-27 — 失败预演应作为反方生成动作，而不是新增评分层（2026-08-20）

### 文献检验

Klein 的 premortem 要求在启动前假定项目已经失败，再倒推最可能的失败原因；它的用途是让原本不易表达的保留意见进入计划。[Performing a Project Premortem](https://hbr.org/2007/09/performing-a-project-premortem) “consider-the-opposite”在某些专家判断场景有减少确认偏误的证据，但 APA 对系统综述的转述也明确指出可验证的去偏见干预很少，不能外推成对投资研究必然有效。[APA systematic-review summary](https://www.apa.org/pubs/highlights/spotlight/issue-235)

### Turtle 的处理

因此不新增 premortem 分数、模型参数或平行风险账本。现有 strongest alternative、机制链、区分观察、阈值与翻转行动已经是正确的可结算落点；缺的是在写出中心路径前强迫研究者生成失败机制。生产提示与 G1-J 现在把失败预演设为一个前置研究动作：每个材料性失败原因必须进入反方、机制、领先阈值或 `UNKNOWN`，否则不保留为漂亮但不可验证的风险段落。

这条方法对格力尤其适用，但不能替代证据：例如“渠道份额继续滑落”“受限资金释放不可重复”“格力钛再减值/追加资本”可以成为需验证的失败机制；短借、金融产品滚动或股价下跌本身不能自动成为失败原因。其价值是提高反方问题的发现率，是否提升未来判断仍由冻结后的结果反馈检验。

这条方法优先解决 `REASONING + MODEL`，但以 `ACQUISITION_MODULE` 的可比后续 observation 为前提；没有结果数据时，正确的卡片是 `UNRESOLVED`，不是编造失败归因。

## 32. ITER-28 — 概率校准要分解错误来源，不能只看一个 Brier 数

### 要检验的失败

现有 monitoring dashboard 会在二元概率判断结算后给出 Brier score 和标准误，但一个平均误差不能区分三件不同的事：研究者的概率是否系统性过高/过低、判断是否真正区分了不同情境、以及事件本身是否高度不可预测。若只比较一个分数，很容易把“预测了很少发生的事”“永远报接近平均概率”与“公司机制确有增量信息”混为一谈。这是 `REASONING + MODEL` 风险；经济影响是后来可能把错误的概率语言当成公司洞见，或把正确的公司判断误判为纯随机。

### 文献与裁决

Murphy 的 [A New Vector Partition of the Probability Score](https://doi.org/10.1175/1520-0450(1973)012%3C0595:ANVPOT%3E2.0.CO;2) 将概率评分分解为可靠性、区分能力与事件固有不确定性。因此后续历史结算对**已经冻结的二元概率判断**应按预先定义、可重复的置信档位同时展示这些部分，而不只报告一个 Brier 平均数。

这不是要求把所有前瞻判断都改成精确概率。格力的经营点值、范围和机制判断仍按原合同结算；为了得到看似完整的统计表而把它们映射成 0.3/0.6/0.8 是禁止的。当前真实格力没有 PIT 冻结的概率判断，更没有足以支持分解的重复档位；现阶段输出只能是 `UNKNOWN / INSUFFICIENT_CALIBRATION_COVERAGE`，而不是写入新分数或声称校准。

### 路线影响与验收

R3.5 已补充该条件性出口。实现时必须保留每个原始 prediction ID、同一档位的样本数和结果频率；若档位内覆盖不足，只报告个案 Brier 与不足原因。可靠性、区分能力或 Brier 均不得选择中心路径、覆盖 driver bridge、抵销经营/机制错误，或作为买卖信号。通过标准是：面对同样 Brier 的两组预测，反馈能指出一组是系统性过度自信、另一组是缺少区分能力；面对格力当前样本，系统明确拒绝产出这些推断。

## 33. ITER-29 — 多 agent 应用于反证与独立审阅，不应用于假装群体智慧

### 要检验的失败

把同一模型、同一公司材料、同一提示词或已经看过候选报告的多个 agent 的结论做投票，既不会制造独立样本，也不能提高中心路径的可信度。它最可能重复相同的可得性偏差与叙事惯性；在格力场景中，会把“更多文字”误称为“更多公司经验”。根因是 `REASONING`：错误的独立性假设会直接改变机制概率、估值区间或行动置信。

### 实际核对与文献边界

现有运行器已经把全文上下文交给新鲜的定向研究任务，并要求随后由 `independent_synthesis_context` 综合结构化 finding；PIT case adapter 还要求 reviewer 声明 `did_not_generate_candidate`、`no_prior_review_seen`、`reviewer_context_isolated` 和 `generator_identity_disjoint`。这足以支持“提出反证、审阅冻结合同”，但不是两个互相独立的公司预测器，更没有可验证的误差相关性估计。

Mellers 等关于预测锦标赛的研究提示训练、更新与团队协作可能改善预测，但后续复核也对其中团队/训练效应的归因提出限制；因此不能把该结果外推成“多开几个 agent 就会提升投资判断”。参见 [Mellers et al.](https://www.psychologicalscience.org/journals/psychological-science/0956797614524255/) 与 [Hauenstein et al.](https://www.psychologicalscience.org/journals/psychological-science/09567976241266481/)。

### Turtle 的裁决

保留并行 agent 调度，但任务角色限定为：一条主线生成初始经营路径；隔离的定向任务寻找证据、替代机制与缺失事实；独立综合者裁决是否有理由改变路径。禁止多数投票、概率平均、以 agent 数量提高置信或把同源 finding 计成多个支持。只有未来有预先隔离的信息集、方法和结果记录，且在留出公司/时期上验证出增量，才研究 forecast combination；当前以独立审阅和结果反馈检验其价值。

## 34. ITER-30 — 书中案例的行业深度来自客户替代与市场边界，不是更长的案例卡（2026-08-20）

### 书籍对照

本地《从格雷厄姆到巴菲特》笔记显示，WD-40 案并非只给出“品牌强”结论：它从低单价、替代品节约额、试错损失、购买频率和技术变化慢这些客户选择条件推出锁定机制，并把不同买入时点与回报另行比较。Intel 案也不是“份额高=护城河”，而是把技术代际风险、客户锁定和规模经济放在同一行业机制中，再把好公司与高价买入的差异分开结算。它们的深度单位是“客户替代—相对竞争位置—财务传播—价格隐含路径”，不是字数或案例卡数量。

### 实验与修复

原 `financial_driver_bridge` 只要求一项 `COMPETITION_DEMAND` driver 有 VERIFIED observation、模型绑定和决策绑定。它允许“公司线上份额”在没有市场定义、替代选择或范围限制时通过；这是 `REASONING + DATA_COVERAGE` 缺口，可能把局部渠道信号写成全渠道护城河，进而错误支撑格力的利润持续期或终值。

现在已观察到的竞争/需求 driver 必须额外冻结 `competitive_context`：市场定义、客户替代选项、比较 observation IDs 和范围边界。缺失上下文为 `INCOMPLETE`；比较 observation 未经 VERIFIED 身份支持为 `INVALID`；若公开资料不足，driver 应改为 `UNKNOWN` 并说明保守处理，而不是写一条空泛行业结论。回归以格力式“线上份额是竞争信号、但不外推为全渠道”为通过样本，并确认缺 context 与伪造 comparison observation 分别被拒绝。

### 边界

这不是强迫每个公司拿到完整同行数据库，也不把单个 peer KPI 误作行业真相。它只要求研究者精确说明“相对谁、在哪个市场、客户能换成什么、此证据不能说明什么”。多个报告只有在各自冻结这种上下文和后续结果时，才增加格力的公司经验；跨公司行业判断仍需 R1/R3 的完整同行—时点报告与反例审阅。

## 35. ITER-31 — 多年公司材料应形成状态转换编年表，而非把现金流平均成“经验”（2026-08-20）

### 可得性核对

对 canonical 格力目录的只读核对显示，2018—2025 八份年报都能定位合并经营现金流和购建长期资产支付的现金，足以开始统一口径的现金转换时间序列；“票据、保函保证金等经营活动有关受限资金净减少”只能在 2024、2025 年原文中一致定位。2025 年的 156.67 亿元释放尤其说明，报表 OCF 的跨年变化可能包含资金限制到期，而不是客户需求、单位经济性或常态 owner cash 的改善。

这意味着八年的材料对于公司经验很有价值，但其价值不是“八个独立样本”也不是简单求 OCF/NP 或 FCF 的均值。现金、资本开支、渠道和业务结构的含义会随着行业状态、营运资本、资金限制和会计披露口径改变；未能把这些变化分段，会把一次性释放平滑为公司能力，并可能错误抬高正常 owner cash、终值和下行保护。

### 方法裁决

Pettigrew 的纵向研究强调时间、资料选择和复杂性处理是研究设计本身；Langley 则指出过程资料需要以多种分析策略连接事件与理论，而不会由一条长序列自动推出理论。两者支持 Turtle 把多年材料写成一个结构化的**状态转换编年表**，而不是把报告数量输入概率或估值参数。[Longitudinal Field Research on Change: Theory and Practice](https://pubsonline.informs.org/doi/abs/10.1287/orsc.1.3.267?journalCode=orsc) [Strategies for Theorizing from Process Data](https://journals.aom.org/doi/abs/10.5465/amr.1999.2553248)

每个预先定义的结构时期只回答同一组问题：

1. 客户替代和相对竞争位置发生了什么变化；
2. 这种变化如何传到收入、单位经济性与现金转换；
3. 哪一项资本配置/管理层承诺改变了 owner cash 或永久损失边界，后来有什么观察支持或反驳它；
4. 哪些金额因会计口径、一次性营运资本或披露缺失而不能横向比较。

公司×cutoff 仍只产生一份冻结报告和一个可结算 episode；同公司多期材料作为这一判断的前史、反例和结果追踪，不能计入 reference-class 独立分母。跨公司比较仍须对所有公司问同一问题、使用同一终局范围，符合 structured-focused comparison 的用法。[Case Studies and Theory Development in the Social Sciences](https://mitpress.mit.edu/9780262572224/case-studies-and-theory-development-in-the-social-sciences/)

### 根因、行动与验收

根因是 `DATA_COVERAGE + REASONING`：当前文本能覆盖 OCF/Capex，但受限资金和其它一次性现金项不能在全八年以同一规则完整定位；把它们平均则是被禁止的经济假设。其影响会传导到 normal owner cash、价值区间、永久损失和中心路径，而不是单纯报告写作问题。

执行修复是把状态转换编年表列入 R1 预注册：每段冻结四层 driver、可比性说明、管理层承诺与后续 observation；拿不到的字段保留 `UNKNOWN` 和保守处理。验收不是补齐漂亮图表，而是独立审阅者能从任一“正常化”输入追到所属时期、原始观察和不可比项，并能明确说明为何 2025 年受限资金释放不被当作常态 owner cash。当前 canonical 仍缺 PIT source identity，因此它只能作为公司研究的可追溯材料，不能倒填为历史冻结 episode。

## 36. ITER-32 — 格力 PIT 缺口已从“未知来源”收缩为“尚未保存完整官方清单”（2026-08-20）

### 实测

在巨潮格力公司公告页以 `000651 / gssz0000651` 查询 2025-01-01 至 2026-08-02，页面返回 177 条、6 页官方公告。页面中可直接定位 `2025 年年度报告`：公告 ID `1225250396`，发布日期 2026-04-29，法定附件为 [`1225250396.PDF`](https://static.cninfo.com.cn/finalpage/2026-04-29/1225250396.PDF)。这与本轮采集模块要求的证券代码、公告 ID、URL、发布日期和报告数据期身份逐项对应。

### 裁决

这是 `ACQUISITION_MODULE` 的实质进展：旧目录的年报并非无法追溯，真实官方入口已确认，且不是靠二手链接或记忆补造。但这还不能解除 PIT 围栏。页面的 177 条只证明查询范围和总数；若只摘年报一条，会遗漏同 cutoff 下可能材料性的业绩说明、回购/员工持股、关联金融业务、董事会和补充公告。任意挑选文档会改变资本配置、治理或现金可达性的结论。

### 后续与验收

下一步必须让采集模块将六页公告逐页导出为不可变的 input，再以预注册选择规则物化所需 PDF/可读文本，并把 cutoff 后条目显式保留为拒绝记录。验收条件是独立审阅者能够从新 package 的每个 `source_id` 回到公告 ID、URL、发布日期和原始附件，并能将清单总数与查询范围核对；在完成前，格力 V1 仍是 `NOT_FREEZABLE`，不据此写任何新的经营结论或价格判断。

## 37. ITER-33 — CNINFO 路径必须从“能读清单”闭合到“能物化官方源包”（2026-08-20）

### 发现与修复

静态审阅揭示 `ACQUISITION_MODULE` 的一个真实不对称：CNINFO adapter 能把已导出的公告行规范为带发布日期、ID 和 URL 的 manifest，但 `acquire_source_package` 的默认下载器只接受 `static.sse.com.cn`。因此真实格力清单即使完整，默认生产路径仍会在下载阶段失败；这会把采集缺口错误地留给研究者手工下载和写作补洞。

现在默认下载器按 manifest 中已列出的官方 host 路由：保留原上交所逻辑，新增只接受 `https://static.cninfo.com.cn/...` 的 CNINFO PDF 下载；其它 host 会被拒绝。`enumerate-cninfo --begin-date --cutoff-at` 同时接入命令入口，使完整离线 export 能进入同一 manifest/下载工作流。以实际年报 `1225250396.PDF` 的 URL 形状、mocked 官方 PDF 和页级文本提取做定向 smoke：附件写入隔离 package、生成 reader text，状态为 `COMPLETE`。

### 边界与验收

这关闭的是“完整清单已给定时不能下载”的模块缺口，并不声称已得到那 177 条清单，也不允许从网页搜索结果偷偷跳过预注册选择。剩余根因是 `DATA_COVERAGE`（完整 export 尚未落地）；经济影响仍在现金、治理与资本配置材料可能遗漏。下一验收要求完整 6 页 export 作为输入、manifest 保留全部行及 cutoff 决定、仅从 admitted sources 物化文件，并由独立审阅逐条追溯；否则格力 V1 的状态不变。

## 38. ITER-34 — 真实 CNINFO 全页枚举已通过；旧格力仍缺可审计的观察时刻（2026-08-20）

### 实测结果

新增的 `fetch_cninfo_announcement_records` 以官方 `hisAnnouncement/query` 端点实际跑完 2025-01-01 至 2026-08-02 的六页：`record_count=177`，每行的证券代码、组织 ID、发布日期、公告 ID、标题和附件路径均通过校验，未出现跨页重复。随后 `fetch_cninfo_manifest` 在内存中生成 `CNINFO_FULL_ENUMERATION_DATE_FILTER_VERIFIED`，177 项全数为 admitted，`validate_source_manifest=REVIEWABLE`；2025 年报已解析为 `CNINFO:000651:ANN:20260429:1225250396`、2026-04-29、2025-12-31 与法定 PDF URL。

这直接关闭 `ACQUISITION_MODULE` 的“CNINFO 是否能完整分页、是否能进入 source manifest”的问题。它不形成公司结论，不下载或筛选 177 份正文，也不允许以公告标题替代事实。

### 新暴露的材料性边界

旧格力目录把市价写作 `as_of_2026-08-03`，但没有精确观察时刻、独立价格来源身份，且 manifest、valuation、thesis 和 completion 的生成时间并不一致。把本次 2026-08-02 研究查询、任一旧文件生成时间或事后可见的价格选作 V1 cutoff，都会造成无法审阅的信息围栏。这是 `REASONING + DATA_COVERAGE`，不是格式问题；它会影响允许读到哪些公告、市场隐含轨、条件回报与行动，而不应回写经营盲轨。

### 可执行出口

下一份真正的 V1 必须先冻结本地 cutoff 时刻和独立价格时间，再保存同一边界的完整 CNINFO manifest；然后预注册从 177 项中物化哪些附件，建立四层 bridge 和经营盲轨。验收条件是审阅者能够重跑同一边界得到同样的总数/rows，且价格身份只能在经营路径冻结后读取。此前，当前验证只证明采集模块就绪，格力 V1 仍为 `NOT_FREEZABLE`。

## 39. ITER-35 — 先补齐八年 cash Capex，才能判断现金状态是否可比（2026-08-20）

### 发现

格力八份年报原文均有“购建固定资产、无形资产和其他长期资产支付的现金”，但公共 `evidence_facts` 没有对应事实规则。这会让现金转换/资本配置 bridge 能看见 OCF 却看不见最低限度的现金 Capex，属于 `ACQUISITION_MODULE` 缺口；用 Tushare 或报告正文中的另一个聚合数字补上，会破坏同一官方文件、同一口径的可追溯性。

新增 `cash_capex_rmb_m` 规则并以单表夹具和格力 2018—2025 八份原文回归。八年均能同时提取 OCF/现金 Capex（亿元，四舍五入）：2018 `269.4/38.4`，2019 `77.3/47.1`，2020 `192.4/45.3`，2021 `18.9/57.3`，2022 `286.7/60.4`，2023 `564.0/54.3`，2024 `293.7/33.0`，2025 `463.8/17.2`。这不是 owner cash 序列：2025 OCF 包含 156.67 亿元经营性受限资金释放，且其它年份的营运资本、业务结构和一次性项尚未完全归一。

### 经济裁决与验收

这些数字足以拒绝“取八年平均 OCF 或 OCF-Capex 即常态能力”的做法；那会错误传导到 normal owner cash、EPV、终值和永久损失。正确用途是为状态转换编年表提供每段现金检查点，再由具体的受限资金、应收/存货/合同负债、维护性/增长性资本和资本配置事件解释变化。

此轮关闭 `ACQUISITION_MODULE`，但保留 `DATA_COVERAGE + REASONING`：缺少逐期一次性现金和维持性 Capex 的判断。下一验收不是再加历史平均，而是每个结构时期都有现金变化的机制解释、可比性边界和保守处理；解释不了的期间保留 `UNKNOWN`。

## 40. ITER-36 — 完整公告 inventory 不等于必须全文下载，也不能允许事后挑文档（2026-08-20）

### 要检验的失败

真实格力 CNINFO inventory 有 177 条。旧 acquisition contract 将全部 admitted 行同时作为待下载 `sources`：若全量物化，研究负担会淹没决定性问题；若研究者临时手挑，清单虽在却没有可审阅的选择边界。前者诱发“报告数量=深度”，后者允许确认偏误遗漏治理、回购或关联金融业务，根因是 `ACQUISITION_MODULE + REASONING`。

### 最小修复

新增 `source_package_selection`，独立于 full inventory：它只含 schema、选择 policy、选择理由、admitted `source_id` 子集以及可核对的 inventory/admitted 数量。`acquire_source_package` 有该对象时仅下载此子集，却继续保存所有 admitted sources 和 inventory；无该对象时保留旧的全量物化语义。选择 ID 重复、非 admitted、数量不匹配、缺 policy 或原因都会在 validation/acquisition 阶段被拒绝。

定向回归以两个 admitted 官方附件和一个被冻结的 source ID 运行：只发生一笔下载，package 显示 `selected_count=1`，而 manifest 仍保留两项并为 `REVIEWABLE`。这证明选择不会悄悄改写 PIT 准入，也不把标题当事实。

### 格力与验收

格力的选择计划应由中心路径与四层 bridge 推出，而非反过来：例如定期报告服务现金/单位经济，金融产品/格力钛/回购和治理公告服务资本配置，渠道或经营披露服务竞争判断。哪个 source ID 尚未选中就尚未阅读、不能进入写作。验收条件是选择在正文阅读前写入 source package，独立审阅者能从每个已读事实回到 source ID，并能看见 177 条中哪些项被保留而未物化；在此之前，这不是格力 V1 的内容完成。

## 41. ITER-37 — 日期精度不能伪装为同日时点的 PIT 可得性（2026-08-20）

### 失败假设

交易所和巨潮公告清单通常只给出 `YYYY-MM-DD` 的法定发布日期。旧解析把这种日期当作当地零点；因此一个 `18:00` 的 cutoff 会自动放行同日公告，虽然公开记录并未证明正文在收市前已经可得。若该公告包含业绩、回购、资本配置或重大减值，这会让经营路径、市场隐含轨和回报结算发生真实的前视。根因是 `ACQUISITION_MODULE + REASONING`，不是格式瑕疵。

### 最小修复与验证

source admission 现在区分显式时间戳和日期精度：日期精度来源只有在早于 cutoff 日时才准入；同日来源得到 `REJECTED_PUBLISHED_AT_TIME_UNKNOWN_AT_CUTOFF`，同日修订得到 `REJECTED_REVISION_TIME_UNKNOWN_AT_CUTOFF`。带精确 `2020-04-27T18:00:00+08:00` 时间的来源仍可准入，前一天的日期来源仍可准入。定向回归覆盖这四种情况，避免用“把一切同日公告拒绝”替代真正的时间精度规则。

格力官方端点在新规则下以 `2026-08-03T18:00:00+08:00` 只读重跑仍为 177 条、177 项 `ADMITTED`、`REVIEWABLE`；清单中最晚公告日为 2026-07-16。因此新规则没有人为缩窄该候选的公司信息集，而是证明该边界没有同日日期来源需要假装成盘中可得。

### 对格力和价格的裁决

这条规则让“公司先、价格后”可以严格实现：若使用旧候选附近的市场观察日，格力盲轨只可使用 2026-08-02 及更早的日期精度公告；市场价格应在之后作为带来源和观察时刻的独立市场轨附着。价格轨的较晚时刻不能回填经营盲轨，只能说明市场当时隐含了什么以及由此产生什么决定性问题。

这仍不等于格力 V1 已冻结：价格来源/时刻、完整 inventory 的保存和选择计划仍未完成。验收是新的 manifest 让同日日期公告明确拒绝而不是静默准入，且独立审阅可分别追溯盲轨最后允许的公司来源与价格观测身份。

## 42. ITER-38 — “20 多份报告”只有在逐源服务公司问题时才增加深度（2026-08-20）

### 元数据实验

把格力官方清单向前扩至 2018-01-01，候选边界内有 889 条公告。其中 64 条标题包含定期报告，但它们含摘要、英文版、取消/更正以及同一报告的正文/全文重复；标题数量不能成为研究深度，更不能成为独立经验样本。只用日期、ID、标题和法定 URL（不读正文）按预注册规则选择，得到 41 个待物化来源：15 份非摘要年度/半年度报告，8 份财务公司存贷专项，10 份回购主行动，4 份非主业投资主行动，4 份利润分配预案。

### 裁决

这 41 项的价值不是让模型“多看 41 次格力”，而是让一个公司×时点报告能重建跨期状态、现金可得性、资本配置承诺及后来观察。每项在 `source_package_selection.v2` 中都必须有自己的选择理由和预注册问题 ID；全局一句“资本配置材料”不再足以允许静默挑证据。选择计划已保存为 [GREE_V1_SOURCE_SELECTION_PLAN.md](GREE_V1_SOURCE_SELECTION_PLAN.md)，仍是元数据预注册，尚未下载正文。

它直接回答用户的原问题：20+ 格力材料在这个形式下**有用**，因为它们覆盖同一公司的不同机制、时期和反例；如果只是卖方报告/摘要/重复版本的堆叠，则没有用，甚至会放大既有叙事。无论 41 还是更多，它们仍只支撑一个公司的一个 PIT episode，不能成为行业概率或参考类样本。行业判断还要用同一问题和同一冻结尺度的同行/官方行业来源来检查客户替代和相对位置。

### 验收与剩余风险

此轮关闭“怎样从 889 项里不靠事后结论挑正文”的 `ACQUISITION_MODULE` 缺口，但未关闭 `DATA_COVERAGE`：计划不含同行份额、客户替代或行业销量的独立来源。经济影响是，若把格力自身渠道/KPI 写成行业护城河，仍会错误影响持续期和价值。下一验收是以重跑的完整 manifest 验证 41 个 ID、逐源物化并让四层 driver bridge 显式保留竞争边界；若同行数据仍缺失，就把竞争层保留为 `UNKNOWN`，不以报告数量补空。

## 43. ITER-39 — 历史市场价也必须是冻结的观察，不是旧 ledger 的标签（2026-08-20）

### 核对

项目中的 `quote_fetcher` 与年糕 market snapshot 只获取当前实时行情；它们能够为当前报告形成来源、抓取时刻和快照身份，但不能回溯某个历史交易日。技术工具有 Tushare 日线调用路径，但当前环境未配置可用 token/API；因此本轮没有取得格力候选边界的历史收盘价，也没有把旧 `as_of_2026-08-03` 字段误升级成价格证据。

### 裁决

根因是 `ACQUISITION_MODULE`。它的经济影响是材料性的，但边界明确：阻断价格隐含预期、条件回报和行动，**不阻断**公司经营盲轨、现金正常化、机制链或前瞻经营判断。以当前价、价格网页的事后显示值或一条无原始响应的 ledger 条目补空，会同时破坏 PIT 和“公司经验优先”。

后续合格观察至少保存交易代码、币种、未复权/复权口径、交易日与市场收市时刻、价格字段、提供者/原始响应身份及取得时刻。拿不到时市场轨应为 `UNKNOWN`，不能让“没有价格”变成不研究公司，也不能让“有价格”替代公司判断。验收是该对象可被独立重读和区分于当前 market snapshot；到此之前格力 V1 仍不可产出任何条件回报或动作结论。

## 44. ITER-40 — source selection 必须同时约束下载和 PIT 阅读（2026-08-20）

### 真实集成失败

41 项选择、下载和 manifest validation 均已通过后，首次以完整格力 package 初始化 PIT runner 仍发现不一致：acquisition 正确保留 889 条 admitted `sources` 供审计，而 runner 原先把所有 admitted 条目都注册为 allowlist。未下载的 848 项因此会显示为“package path missing”，更严重的是若未来意外存在同名文件，writer 有机会读取不在选择计划内的来源。这是 `ACQUISITION_MODULE` 的材料性断点，会破坏预注册的证据范围。

### 修复与验收

runner 现在在存在 `source_package_selection` 时只以 `selected_source_ids` 建立注册表/allowlist；没有选择对象的旧包仍保留全部 admitted 语义。定向回归构造两个同样 admitted 来源、只物化其一：runner 为 `REVIEWABLE`，仅允许已选 source，且拒绝另一个 admitted 但未选的 source。

对真实格力，2018-01-01 至 `2026-08-03T18:00:00+08:00` 的 889 条 inventory 已保存；41 个逐源理由的 PDF/页级表示（3,228 页）下载完成、零失败；manifest validation 与 PIT runner 均为 `REVIEWABLE`，runner allowlist 恰为 41 项。它关闭了公司盲轨的 `ACQUISITION_MODULE` 阻断，但不改变任何公司事实或投资结论。

### 下一边界

下一步只可从这个 allowlist 提取事实，建立状态转换编年表和四层 driver bridge。竞争层仍缺同行客户替代/行业销量，市场轨仍没有可审计历史价格；两者分别作为 `DATA_COVERAGE` 与 `ACQUISITION_MODULE` 留在报告的 `UNKNOWN`，不可由 3,228 页公司文本替代。

## 45. ITER-41 — “带页码 VERIFIED”仍可能是错的经济口径（2026-08-20）

### 失败实验

把格力 41 项已允许读取的官方正文投影为事实账本后，初始输出有 174 条 `VERIFIED` 观察。交叉检查 2019 年报时发现，应收、存货、应付和短借规则只取全文首次同名行：它们落在南京华新收购的资产负债表（第 22—23 页），而非格力合并资产负债表（第 83—84 页）。因此 `VERIFIED`、来源 ID 和页码并不足以保证“集团合并口径”。

### 根因与可执行修复

根因是 `ACQUISITION_MODULE`；若不修，会把营运资本、融资与现金转换错传到 normal owner cash、估值和永久损失。规则现要求页面含“合并资产负债表”，并支持附注列及三期比较列；回归把先出现的收购表和后续合并三列表放入同一文件，只接受后者。真实源包重建后，2019 的四项回到 85.13/240.85/416.57/159.44 亿元，2023/2024 也仍分别定位合并报表页，账本为 `REVIEWABLE`、162 条 `VERIFIED`。

### 学习边界与验收

这一轮不产生关于格力现金质量或价值的新增结论；错误修复前的营运资本/短借行一律不得用于状态划分或模型输入。下次遇到“同名财务行”时，采集计划先验证**报表范围、期间、列定义**，再给出观察身份。验收是：收购子公司表在前、合并表在后的夹具必须通过；真实合并表行可复现；无法确认的行保持 `UNKNOWN`，不能因有页码而升级。

## 46. ITER-42 — 行业深度先补成同口径观察，不先写行业结论（2026-08-20）

### 失败假设

格力已选择的年报正文含产业在线、奥维和公司销量/渠道资料，但事实账本最初只提取到 2024–25 的消费电器毛利率和 2025 的线上份额。这会诱使写作者用收入、一个线上份额或一段行业文字解释竞争位置；根因是 `ACQUISITION_MODULE + DATA_COVERAGE`，经济影响是错误传导到竞争持续期、正常利润和 owner cash。

### 最小采集修复与实测

新增并回归以下不同 basis 的观察，禁止把它们混同：产业在线家用空调内销单位/同比、公司披露的家用空调内销单位/同比，以及奥维口径的家用空调**线上零售额**份额。真实重建得到行业内销 2020 `8,028 万台/-12.9%`、2021 `8,470 万台/+5.5%`、2023 `9,959.7 万台/+13.8%`、2025 `10,521 万台/+0.7%`；公司只在 2023 披露 `2,979 万台/+4.05%`；同定义线上零售额份额为 2023 `28.15%`、2024 `25.40%`、2025 `24.31%`。同轮还把 2018H1—2023 的“空调”产品收入/毛利与 2024–25 的“消费电器”产品收入/毛利分开投影，禁止跨分类机械串联。账本重建为 `REVIEWABLE`、210 条 `VERIFIED`。

这支持写入“线上相对位置两年走弱、仍为第一”及“行业与公司销售增速之间有待解释差异”，不支持计算全渠道份额或证明价格权。2023 的行业内销出货与公司内销的 sell-in/sell-out 边界未披露，2024–25 仍缺公司销量、ASP、返利、渠道库存和竞争对手同口径份额。

### 接纳

形成的 [格力状态转换编年](GREE_V1_STATE_TRANSITION_CHRONOLOGY.md) 把第三方年报转引、公司陈述和合并财务观察分列。任何跨年趋势只有在品类、渠道、地域、销售额/销量和期间定义一致时才允许计算；否则保留为 `UNKNOWN` 或仅做定性检查点。下一步不是扩大报告数，而是建立主/竞争机制的区分信号和四层 driver bridge。

## 47. ITER-43 — 公司经验要通过反例和可区分信号累积（2026-08-20）

### 研究裁决

类比可迁移的是关系结构而不是“龙头、低估值、周期底部”等表面标签；每个支持类比都应预选一个表面近似、但机制或结果相反的反例。结构映射与组织类比研究支持这种限制，但不证明一个历史故事可以给格力赋予概率。[Gentner (1983)](https://onlinelibrary.wiley.com/doi/10.1207/s15516709cog0702_3) [Gavetti, Levinthal & Rivkin (2005)](https://sms.onlinelibrary.wiley.com/doi/10.1002/smj.475)；只观察成功/存活案例还会系统性低估失败。[Denrell (2003)](https://pubsonline.informs.org/doi/10.1287/orsc.14.2.227.15164)

因此新增的最小研究对象是 `analogy_transfer_card` 与 `rival_hypothesis_pair`，而非新的案例卡库。每个 pair 的主/竞争机制必须同样解释当前事实，并产生不同的 6–12 月领先信号、财务传导和失败条件；证据按能否区分两者而不是报告目录顺序收集。这与 process tracing 的诊断证据原则一致。[Bennett](https://www.cambridge.org/core/books/case-for-case-studies/process-tracing-for-program-evaluation/3282EBD903031583252019931E5C3BB9) [Collier (2011)](https://doi.org/10.1017/S1049096511001429)

### 反馈设计

公司直觉只会在具有可学习规律、及时反馈且结果噪声可管理的环境中积累；3–5 年终局回报太慢且受价格路径干扰，不能充当唯一训练标签。[Kahneman & Klein (2009)](https://pubmed.ncbi.nlm.nih.gov/19739881/) 所以同一冻结 episode 要先结算 6–12 月机制/经营信号，再结算 3–5 年终局经营与资本配置；投资回报完全分轨。反馈只允许人工归因到状态表征、机制、证据获取、财务传导或估值/决策，避免 outcome bias。[Baron & Hershey (1988)](https://doi.org/10.1037/0022-3514.54.4.569)

### 验收

已有书籍方法案例卡只新增适用状态、最强近似反例、诊断信号和不可推断边界；不重建卡片，也不把公司重复快照计入基准率。若一个类比不能解释其不匹配维度，或主/竞争假设没有可区分的预注册信号，该类比不得影响中心路径或概率；报告应明确承认未判别。

## 48. ITER-44 — 行业和同行材料必须各自有 PIT 用途边界（2026-08-20）

### 外部行业源审查

对 2020–2025 可公开获得的一手/官方材料筛选后，国家统计局、工信部、海关、商务部/发改委可以支持空调生产、广义家电零售、CPI/PPI 价格环境、出口量值、以旧换新、房地产/工程和整体渠道迁移。它们不能提供连续的全国空调内销台数、国内 ASP、品牌份额、线上份额或价格战强度；国家数据的当前修订值也不能回填旧 PIT。因此行业环境包被预注册为 `CONTEXT_ONLY`，逐条保存当期发布物与 release date，且这些宏观/行业变量不能互相替代或直接变成格力数值输入。完整字段、来源和禁止推断见[官方行业环境包设计](CHINA_HOME_APPLIANCE_OFFICIAL_CONTEXT_PACKAGE_DESIGN.md)。

### 同行边界

现有同行比较工具读取当前数据库/实时网页且可能引入 PE/PB，故不能进入格力经营盲轨。预注册的[同行竞争对照包](PEER_COMPARISON_EVIDENCE_PACKAGE_DESIGN.md)规定：每个同行独立完成同 cutoff 的官方 inventory、选择和 PIT package；事实以只读 `PCOBS:` 交给格力 competition context，永不复制为格力 `OBS:`；用途只限竞争机制对照，禁止估值、价格、基线、FJ outcome、动作、case/episode 与基准率。无合格包时格力竞争层是 `UNKNOWN`，但公司盲轨不停止。

### 经济含义与验收

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。如果将官方生产/社零冒充内销份额，或把当前同行数据冒充历史竞争证据，都会改变格力竞争持续期、正常利润与价值判断。验收是：外部每条 observation 具有原始发布身份/当期可得性/不可推断边界；同行每条引用具有独立 package 和可比性合同；两种包的 `independent_sample_increment=0`。在实物化、独立审阅前，它们不产生任何格力结论。

## 49. ITER-45 — 既有回测可用于公司经验，但须剥离收益率并支持早期结算（2026-08-20）

### 失败复现

以真实 v2 结算契约构造一个无价格的公司判断 case：第一条 operating claim 已在 2022 年官方年报窗口到期，第二条 claim 的观察窗口到 2026 年才关闭。改动前 case 本身可审阅，但 settlement 同时报出 `observation_window_closes_after_settlement` 和 `frozen_investment_decision_required_for_return_settlement`；即使早期经营事实已经可读，也被迫等待终局并要求一个不存在的收益率。这会把公司经验训练误做成行情回看，根因是 `MODEL + REASONING`。

### 最小实现与验证

v2 新增 `COMPANY_JUDGMENT_ONLY` purpose：冻结时必须没有价格 identity、投资动作或投资 decision；结算的 return ledger 固定为 `NOT_APPLICABLE`，并拒绝市场源、收益、现金流、基准或执行。对这类 case，窗口尚未关闭的预测只能以无 observation 的 `PARTIAL` 保留；任何提前填入 actual 会被拒绝。`settlement_series_id`、连续序号、前序 ID 和 `validate_settlement_series` 使后续结算只可追加，且已经 `CALCULATED` 的 claim/observation 不可重写。

针对性 smoke 已验证：无价格 case 可以结算到期 operating claim 并保持未来 claim `PARTIAL`；提前给未来 claim 写结果会被拒绝；两份连续 settlement 通过，而错误前序 ID 被拒绝。旧 v1、v2 期间窗口和区间预测 smoke 仍通过；同时修复 settlement schema 仍强制 range 预测携带 `forecast_value` 的不一致，区间继续保留上下界与 `WITHIN_RANGE / BELOW_RANGE / ABOVE_RANGE`，不允许中点替代。该实现没有读取格力未来资料、没有新增 case 样本，也没有使格力 V1 可冻结。

### 接纳边界

这关闭的是 `COMPANY_JUDGMENT_ONLY` 反馈引擎缺口，不是 `DATA_COVERAGE` 缺口。格力在生成实际 FDB、模型绑定、决策 ledger 和 3–5 条可结算 FJ 前，仍没有 production case。下一验收是用真正冻结的公司报告进入该路径，先以官方经营 observation 追加早期机制信号；市场轨和投资回报必须继续独立。

## 50. ITER-46 — “以后观察什么”必须成为 bridge 的可执行字段（2026-08-20）

### 失败复现

原 `financial_driver_bridge` 能冻结四层事实、模型输入和决策条目，却把后续观察留在 driver 之外，把资本事项的兑现期保留为自由文本 `realization_window`。这使一份报告可以在冻结时说“以后看渠道、现金或格力钛”，但一年后仍可随结果改变 metric、口径、允许来源或终局时间。根因是 `MODEL + REASONING`，而非写作：这种事后重选观察会错误增强 H-A/H-B 的任一方、误判 normal owner cash 或资本配置兑现，并污染公司经验反馈。

### 最小修复与验证

bridge 现在要求每个 driver 提交唯一 `FDBMON:` monitoring contract：关联的 FJ、metric/unit/measurement basis、可比性规则、预测期间、允许的官方来源类别和观察窗口。每个 allocation event 还须提交唯一 `FDBREAL:` realization contract，内含分别唯一的 early-signal 与 terminal-outcome monitoring contracts；终局期间必须晚于早期信号。缺 driver/event 合同返回 `INCOMPLETE`，重复监测 ID 或倒置期间返回 `INVALID`。

受限 writer 的 `read_structured_ledger_contract(financial_driver)` 同步公开该嵌套契约，避免模型仅按旧自由文本写入。直接 smoke 覆盖四层合格 bridge、缺两个合同、重复 nested contract、竞争上下文、未知 driver 的保守处理、completion/snapshot gate 与 agent writer；所有检查通过。此修复未创建格力 FDB、模型、决策或 FJ，也未读取后续公司信息。

### 接纳边界

格力的四个合同仍是设计模板，而不是已冻结的判断。下一步必须用同一 PIT source package 中真实的模型/决策对象和可比较的后续观察填入；无法取得全渠道/线下、量价费用或现金 adjustment bridge 时相应 FJ 保持 `UNKNOWN` 或 `NOT_EVALUATED`。验收是正式 bridge 的每个 driver/event 都有可执行合同，早期与终局结算只能沿冻结合同追加，而不允许用事后文字改写问题。

## 51. ITER-47 — 官方行业环境能排除误因，但不能替代竞争证据（2026-08-20）

### 小型 source pilot

为格力 V1 定位了八项截至 cutoff 已发布的一手背景观察：2020/2024/2025 规上房间空调产量、2024H2 与 2025 以旧换新政策、2025 广义家电/线上零售、耐用消费品 PPI 与房地产环境。每项都保存了当期官方 URL、发布时点、指标定义、所服务的 H-A/H-B 背景问题和禁止推断，详见[官方行业环境包设计](CHINA_HOME_APPLIANCE_OFFICIAL_CONTEXT_PACKAGE_DESIGN.md)。

### 结论与边界

它们的增量信息是：公司收入、渠道或毛利的变化不能在忽略生产节奏、政策、广义零售、价格环境和工程需求背景下直接归因于竞争。它们的**非增量**同样重要：没有一条给出空调内销 sell-out、国内 ASP、品牌/渠道份额、返利/费用或格力调整后现金。因此它们不能区分“渠道/价格带重配”与“广泛竞争恶化”，不能接入估值、FJ outcome、投资动作或基准率。

根因仍是 `DATA_COVERAGE + ACQUISITION_MODULE`；经济影响是若把宏观产量或 PPI 填充为公司竞争指标，持续期、正常利润和永久损失判断都会被伪精确化。下一验收是将每一条 pilot 的原始响应与定位物化为 `CONTEXT_ONLY` package；即使完成，格力竞争层仍需同行或同口径公司—行业观察才可升级。

## 52. ITER-48 — 现金判断的缺字段先修采集器，而不是用 OCF 叙事补齐（2026-08-20）

### 失败复现

格力的 2025 年 OCF 已抽取到 463.83 亿元及 156.67 亿元经营相关受限资金释放，但 `contract_liabilities` 尚未被结构化。它会遗漏经销商预收货款这条营运资本状态，使“OCF 改善”可能被误写为客户需求、现金转换或可分配现金。根因是 `ACQUISITION_MODULE`，经济影响是 normal owner cash、分红安全和资本纪律都会出现方向性误判；禁止以 OCF、OCF–Capex 或期末余额直接补出答案。

### 最小修复与验证

通用事实采集器新增 `contract_liabilities_rmb_m`：只在标有“合并资产负债表”的页面提取，并沿用可比期间的首列口径。回归同时放入收购子公司表和后续合并表，确认只接受合并行。格力允许来源重建后，facts 从 210 条 `VERIFIED` 增至 215 条；合同负债已得到 2021–25 年连续的 155.05/149.72/135.89/124.91/152.07 亿元观察，2025 销售收现、应收、存货、应付、短借、利息和受限资金也均已有 page-level identity。

### 接纳边界

这是 cash bridge 的**输入覆盖**改进，不是 normal owner cash 的计算或关于格力需求的结论。五项期末数仍缺与利润、票据融资、金融业务、维持性 Capex 和一次性受限资金的逐期统一 adjustment bridge；因此现金层仍不具备实际 FDB/model binding。下一验收是把每项现金传导明确为冻结 FJ 的 measurement basis 与保守处理，而不是因字段变多就降低估值折减。

## 53. ITER-49 — 行业量价与库存背景可用，但品牌竞争层仍不可得（2026-08-20）

### source materialization

原先“没有公开行业竞争资料”的表述过宽。中国家用电器协会《电器》2025 年第 9 期封面载明 2025-09-08 出版，原 PDF 已物化；其 AVC 署名的第 25–26 印刷页可冻结 2025 冷年（2024-08 至 2025-07）行业资料：内销出货 1.02 亿台（+8.7%）、全渠道零售量/额 8,059 万台/2,572 亿元（+17.6%/+17.1%）、线上/线下拆分、冷年中期逾 5,000 万台行业库存、以及线上 1.5HP 挂机均价 2,536→2,101 元和低价带份额上升。6 条 `INDCTX:` 已以 `CONTEXT_ONLY` policy 写入格力候选的 context manifest。

### 裁决

这提供的是有价值的**反证背景**：2025 年格力产品毛利未塌陷，不能独自排除行业线上低价、库存和渠道结构压力；行业全渠道零售增长，也让“格力收入收缩仅是行业需求差”成为须验证而非可直接成立的解释。根因的改善是 `ACQUISITION_MODULE`，但公司竞争结论仍受 `DATA_COVERAGE` 阻断：冷年与自然年、厂家出货与零售、行业与品牌均不相同，无法由这些表计算格力的全渠道份额、线下份额、品牌 ASP、返利或经销库存。

### 接纳边界

这不是把协会刊物或 AVC 归因为官方统计，也不是将它复制成格力 `OBS:`。当前 bridge 只能把它作为明确的 qualitative guardrail；它不可进入估值、owner cash、FJ outcome、行动或基准率。若要判别 H-A/H-B，下一获取对象必须是同一自然期、同一品牌定义下的渠道/销量/ASP/价格带版本冻结数据，或承认 `UNKNOWN`。这比用宏观生产或一条公司线上份额硬填竞争结论更有信息量，但仍不能代替公司层证据。

## 54. ITER-50 — 主/反机制与案例反例进入冻结、投影和无价格结算（2026-08-20）

### 失败复现

既有 `competitive_tests` 已能保存主解释、最强反方和文字化区分观察，但 production adapter 只把主路径投影为一个 `HBTCLM:`，反方只残留为 `counter_thesis` 字符串；`analogy_transfer_card` 则只存在于路线图。结果期即使主判断落空，也无法区分“竞争机制被支持”与“该信号本身不具诊断性”，书籍案例容易重新沦为叙事背书。根因是 `MODEL + REASONING`；经济影响是错误的渠道/竞争/现金机制会被记成公司经验，进而影响正常利润、owner cash 与持续期判断。

### 最小实现

`thesis_test` 现可冻结 `rival_hypothesis_pairs`：同一当前事实、主/反两条不同的四段 mechanism chain、至少一条 6–12 月 `EARLY_MECHANISM` 和一条 `TERMINAL_OPERATING` 的有序 discriminator。每条 discriminator 绑定一个既有 FJ/HBT claim，并要求主预测等于该 FJ 的冻结预测、反预测使用同一 metric/unit/horizon/due 但确实不同。每个 FJ 反向链接 pair/signal，避免结果期另找“更好的反方”。

`analogy_transfer_cards` 只复用 `insight_case_benchmark.json` 的既有案例原型：必须有至少三个目标状态维度、驱动→中间变量→经营结果映射、结构不匹配、信号化失效条件和一个 `strongest_near_miss`；禁止 `price`、`valuation`、`probability` 或 `return` 输入，且结论只能从 pair signal 派生。它没有新建案例库，也没有把成功故事变成频率样本。

snapshot-hashed adapter 将 pair、card 和同一 FJ claim 无损投影到 CJO case。`historical_backtest` 只从该 claim 的官方 operating observation 派生 `SUPPORTS_PRIMARY / SUPPORTS_RIVAL / MIXED / NOT_YET_DUE`，并拒绝在 settlement 手写 verdict；反馈卡回显派生结果且继续将投资回报排除在外。

### 验收与边界

定向 smoke 覆盖：合法 pair/card 可冻结；缺共同事实、相同预测、缺早期或终局信号、无近失效反例、或 card 的直接估值字段会被阻断；adapter 不能接受与 FJ 不同的 pair 主预测；同一官方实际满足主而不满足反时自动为 `SUPPORTS_PRIMARY`，人工填写相反 verdict 被拒绝。由于当前 shell 没有 `pytest`，采用这些直接函数 smoke 与 Python 编译检查，不把测试环境缺包误报为产品失败。

格力 V1 仍没有公司层全渠道份额、品牌 ASP、返利或经销库存，因而 H-A/H-B 仍是 `UNDISCRIMINATED`。禁止把新对象、协会行业背景、20 多份报告或未来股价当作这些缺失事实的替代。下一可改变结论的获取是版本冻结的品牌×渠道×销量/额×ASP 数据，或维持 `UNKNOWN`；下一系统验收是用真实 PIT 报告而非测试夹具冻结首个 pair/card/FJ episode。

## 55. ITER-51 — CJO 的上游投资门冲突（2026-08-20）

### 审计发现

`COMPANY_JUDGMENT_ONLY` case 与 settlement 已正确禁止价格、投资动作和收益率；但它之前的 `financial_driver_bridge` 仍要求每个 driver 绑定 `valuation_model` 与 `decision_entry`，`thesis_test` 仍要求每条机制/FJ 覆盖 valuation/expected return、`valuation.v_final`、`return.gg.*` 和 flip 后仓位/动作，发布快照又无条件要求 decision/valuation gates。因此一个真实的“先学公司、暂不作交易”的格力 episode 仍会被迫伪造估值/回报/仓位，或无法冻结。

根因是 `MODEL + REASONING`，不是 `DATA_COVERAGE`。经济影响是公司经验训练会被股价/交易物件污染，恰好违反“公司第一性原理优先、价格另列”的路线。禁止的假修复是只放松 FDB 或只让 adapter 忽略 gate：其余上游仍会强制伪投资对象，且会让冻结目的在中途丢失。

### 已收敛的修复边界

下一实现应引入从 FDB、thesis、snapshot 到 Phase10 case 一致的显式 `analysis_purpose`：

- `INVESTMENT_DECISION` 保持现有模型、价值、回报、仓位和决策门完全不变；
- `COMPANY_JUDGMENT_ONLY` 仍强制四层事实、竞争范围、`FDBMON`/`FDBREAL`、中心路径、3–5 个可结算 FJ、主/反 pair、案例近失效反例、官方结算和独立审阅；但禁止任何价格、价值模型、回报、仓位或交易动作字段；
- FDB 用 monitoring contract 的 FJ ID 形成 driver↔FJ 绑定，adapter 必须核验二者一致；snapshot purpose 与 case purpose 不同即拒绝；CJO 的发布 profile 仍要求官方证据、claim evidence、FDB、thesis、insight、PIT 和审阅，唯独不把 decision/valuation 当作条件。

### 接纳标准

CJO 无 model/decision binding 且四层 monitoring 完整时可冻结；若夹带 valuation/action/return、少任一经济层、少 FJ↔driver 绑定、或 snapshot/case purpose 不一致则拒绝。现有投资模式的 regression 必须原样通过。这是解除首个真实格力公司判断 episode 的系统前置；它仍不会消除品牌×渠道×量价数据缺口，后者继续以 `UNKNOWN` 和保守处理保留。

## 56. ITER-52 — CJO 已在 driver bridge 与 thesis 层去除伪投资绑定（2026-08-20）

### 最小实现

`analysis_purpose` 已进入 `financial_driver_bridge` 与 `thesis_test`。`INVESTMENT_DECISION` 的既有契约未放松：四段 transmission、估值模型、价值/回报决策链接、翻转后的估值/仓位/动作仍为必填。`COMPANY_JUDGMENT_ONLY` 则保留四层经济事实、竞争范围、`FDBMON`/`FDBREAL`、中心路径、3–5 条 FJ、机制链、主/反 pair 与案例近失效反例；但只允许 `normalized_earnings` 与 `owner_cash` 传导，拒绝任意 valuation/return/model/decision/action/position 字段。

这把“公司机制先行”落实为一条有严格证据和结算合同的路径，而不是让 CJO 变成松散的研究笔记。CJO 的 FJ 仍必须有冻结预测、同口径简单基线、官方可接受来源、观察窗口与终局经营结果；早期信号只结算相应箭头，不裁决总投资结果。

### 验证与边界

定向 smoke 已证明：四层 CJO bridge 在删除模型/交易绑定、保留监测合同后可审阅；夹带模型绑定会被拒绝。CJO thesis 在删除投资字段、使用纯经营预测后可审阅；保留任一 flip 后投资字段、机制 decision 或 FJ valuation/decision binding 会被拒绝。原投资模式关于估值模型、价值与回报 decision link 的回归仍通过。

根因解决的是 `MODEL + REASONING`；公司判断不再因缺少价格结论而被迫造出交易对象。它不改变格力的 `DATA_COVERAGE` 结论：品牌×渠道×销量/额×ASP、返利和经销库存尚未获得，故 H-A/H-B 继续 `UNDISCRIMINATED`；下一步仍是将同一 purpose 贯通 publication snapshot 与 production adapter，并取得可冻结的公司竞争观察。

## 57. ITER-53 — CJO 的结构化冻结与结算中下游已贯通；PIT writer 仍是上游阻塞（2026-08-20）

### 失败复现与修复

仅在 FDB/thesis 放松投资字段仍不足：`completion` 会要求 decision manifest 与 GG 推导，snapshot 会要求 valuation/decision，Phase10 adapter 也会因 snapshot purpose 与 case purpose 不一致拒绝真实 case。根因仍为 `MODEL + REASONING`；其经济后果是“公司经验优先”停留在文档，真实 episode 无法从 PIT 证据进入早期经营结算。

现在 `analysis_contract.analysis_purpose` 是全链冻结身份。CJO completion 跳过 decision manifest、GG 与估值/交易 gates；snapshot 只要求官方证据、claim evidence、FDB、thesis 与 insight，并把相同 purpose 写入 snapshot；正式接纳增加同一 CJO profile；Phase10 要求 snapshot、case、FDB 和 thesis 目的相同。CJO adapter 保留 FDB 的监测/资本兑现合同，并强制每个 FJ 的 driver 引用与相应 `forward_judgment_ids` 双向存在；case 继续强制 `UNKNOWN` price 和无 investment decision。

### 验收与非结论

定向 smoke 覆盖 CJO bridge/thesis 的正反例、investment regression、completion 的无 decision/GG profile、snapshot purpose mismatch 和 adapter 的无损 FJ/driver 投影；Python 编译及 diff check 通过。对投资用途，既有 valuation、return、action、position 和 decision gates 未被削弱。

这解除的是**已结构化 CJO ledger** 从 completion 到 snapshot、正式接纳与 Phase10 结算的中下游 `MODEL + REASONING` 阻塞；它不等同于当前 PIT production writer 已能生成 CJO。后续反向审计发现，writer 没有 `analysis_purpose` 入口，初始化、可用 writer、结构化 ledger contract、claim/insight/judgment review、报告组装、章节审计和读者覆盖仍无条件要求模型、D-id、价值、价格、回报或动作。根因是 `MODEL + REASONING + WRITING`：若不修复，真实公司研究只能伪造投资字段，或根本无法生产冻结。

因此禁止把空 D-id、占位估值、价格、回报或交易动作当作 CJO 修复。可执行修复是为 PIT runner/CLI、AgentConfig 和初始化显式传递 `analysis_purpose`；CJO writer facade 不暴露估值/决策写入；为 claim、insight、judgment review 以及组装/章节/reader coverage 提供仅含经营事实、机制、FJ 和反馈的 CJO contract；最后以一个真实 PIT CJO fixture 从 source selection 跑到 snapshot、acceptance 和无价格 Phase10 settlement。验收是该 fixture 在没有任何 model/D-id/price/value/return/action 的情况下完成所有 CJO 必需门，并且同一 fixture 切回 `INVESTMENT_DECISION` 后仍严格要求原有投资门。

真实格力 CJO 同时仍由 `DATA_COVERAGE + ACQUISITION_MODULE` 阻断：同定义品牌×渠道、量价费用、adjusted owner cash 和资本配置兑现尚不能产生 3–5 条数值可结算 FJ。允许的下一步只有获取冻结数据切片或以 `UNKNOWN` 保留 H-A/H-B；不得以 20 多份报告、行业背景或股价替代。

## 58. ITER-54 — CJO PIT writer 的用途、工具与账本合同开始贯通（2026-08-20）

### 真实失败与修复

此前即使 CJO 的 FDB、thesis、snapshot 和 Phase10 已经支持无价格结算，PIT runner 仍会把所有生产运行初始化为投资报告，并把决策、估值、D-id、价格、回报和动作 writer 暴露给模型；claim、insight、judgment 的 writer schema 也会把这些字段作为必填。这是 `MODEL + REASONING + WRITING` 的材料性问题：公司研究者若为通过机器门填充占位投资字段，会污染日后“公司机制是否被验证”的训练样本；若拒绝伪造，CJO 无法产出生产冻结。

现在 runner/CLI、`AgentConfig`、`analysis_contract` 与 PIT writer facade 都传递枚举化 `analysis_purpose`。`COMPANY_JUDGMENT_ONLY` 仅能由受限 `--pit-production-freeze` 入口启动：初始化只启用官方证据、claim、FDB、thesis 和 insight policy；工具集移除 decision manifest/ledger、估值 model 和决定性问题 writer；CJO 报告合同使用专用 15 章模板，章节、组装和 reader coverage 均拒绝证券价格、估值、回报、仓位和交易动作。claim/insight/judgment 统一改为“事实→机制→正常化盈利或 owner cash→监控/FJ”的对象；投资用途原有字段仍保持必需。

### 一个真实的顺序问题

CJO 的 FJ 同时需要被 claim（说明该判断为什么重要）和 thesis（定义预测及结算）引用，不能假装二者不存在依赖。修复不是删掉其中一个绑定，而是允许**未冻结**的 CJO claim 以计划 FJ ID 作为 `INCOMPLETE` bootstrap：先有 claim identity，随后 FDB 与 thesis 冻结实际 FJ，最后同一 claim 才可 promotion。最终冻结时 FJ 不存在仍是 `INVALID`。这保留双向可追溯性，也不允许用空 ID 过门。

### 当前验收与剩余边界

定向回归包括 CJO runner/tool facade、CJO report/structured-contract reader、CJO claim bootstrap 及 claim/insight/judgment 的 46 项模块测试；Python 编译和 diff 检查通过。接受标准尚未完成：仍须用一个真实 PIT source package 跑到 CJO report、completion、snapshot、独立接纳与无价格 Phase10 settlement，证明所有 writer 输出与冻结对象的 purpose 相同。

格力的材料性数据边界不因此改变：品牌×渠道×销量/额×ASP、返利、经销库存、调整后 owner cash 和资本兑现仍缺。禁止把这次工程闭环、20 多份报告、行业背景、网页行情或未来股价说成已判别 H-A/H-B；它们只能让已取得的公司事实在将来形成更快、更诚实的学习回路。

## 59. ITER-55 — 机制区分与置信校准须走两条反馈回路（2026-08-20）

### 文献复核

Stone 与 Opel 的随机实验将判断训练拆为两种不同反馈：关于判断是否命中的 performance feedback 会改变过度自信，而关于环境线索的 feedback 会提高对情境的区分；两者并不会自动互相改善。[Stone & Opel (2000)](https://doi.org/10.1006/obhd.2000.2910) 这与公司研究的实际困难相符：一个机制信号即使事后支持 H-A，也不证明研究者对所有公司、所有环境的置信程度已经校准；反过来，长期正确的置信档位也不能代替本期 H-A/H-B 的因果证据。

### Turtle 裁决

现有 `rival_hypothesis_pair` 已是**区分回路**：主/反预测必须同 metric、unit、horizon 和 due，以同一官方 observation 派生 `SUPPORTS_PRIMARY / SUPPORTS_RIVAL / MIXED`。它回答“这个信号有无把两条机制分开”，并将无诊断性的结果保留为 `MIXED`，不把一次命中升级为经验。

概率校准必须是另一条、样本门槛更高的回路：只接收预先冻结的二元概率判断，按独立公司/时期/机制簇的重复置信档位报告可靠性和区分能力。当前没有合格独立样本，故其输出为 `UNKNOWN`；不得把 point/range FJ、pair verdict、20 多份同公司报告、或股价回报强行折成概率得分。Kahneman 与 Klein 对可学习环境和及时明确反馈的条件仍是这里的上位限制。[Kahneman & Klein (2009)](https://pubmed.ncbi.nlm.nih.gov/19739881/)

### 经济影响、禁止项与验收

根因是 `REASONING`，并在样本不足时同时是 `DATA_COVERAGE`。若把 pair 的一次胜负记作总体自信，或让概率分数裁决格力当前路径，会伪造竞争持续期、normal owner cash 和永久损失判断的确定性。禁止新增一个“综合判断分”或用报告数量填概率分母。

验收为：每份 CJO 只报告其冻结 pair/FJ 的机制区分结果与 `NOT_EVALUATED` 边界；只有独立资格、同一二元问题、PIT cutoff 和 outcome 均完整的 episode 才能进入单列 calibration cohort。格力 V1 目前两者均未达到，H-A/H-B 继续为 `UNDISCRIMINATED`。

## 60. ITER-56 — 已选格力 PIT 观察没有遗漏可判别竞争数据（2026-08-20）

### 数据覆盖复核

对 `company_blind_track/fact_observations.json` 中 41 份已选 PIT 源的结构化原文，按全渠道、线下份额、品牌份额、ASP/平均售价、返利/佣金、经销库存、sell-in/sell-out、终端零售和销量检索。可定位的只有：产业在线的 2020/2021/2025 行业总销量/内销数，以及奥维云网转引的 2023/2024/2025 格力品牌**线上零售额**份额。不存在同一品牌的全渠道或线下份额、品牌销量/ASP、返利/佣金、经销库存，或 sell-in/sell-out 的结构化观察。

这不是对全网公开资料的断言，而是对当前可审计的 41 源 PIT source package 的覆盖结论；未来引入任何新资料仍须按同一 cutoff、版本和定义独立冻结。

### 裁决与下一步

根因是 `DATA_COVERAGE + ACQUISITION_MODULE`。若把行业内销总量与格力收入相除、用线上份额外推线下/全渠道，或把单期产品毛利当 ASP/返利，就会错误选择 H-A 或 H-B，并影响竞争持续期、normal owner cash 与永久损失判断。上述推断均被禁止。

唯一可改变竞争裁决的采集模块目标是：同一自然期、同一品牌定义下的渠道×销量/销售额×ASP/价格带版本切片，并明确 sell-in/sell-out；若使用经销库存、返利或费用，则还要有公司边界、口径和披露期。验收是这些字段能与 2025 已冻结同口径起点形成 FDBMON/FJ 双预测；取不到时，CJO 只冻结 `UNKNOWN / UNDISCRIMINATED`，而不是产生中心路径。

## 61. ITER-57 — 因果力分解有条件地深化财务传导，不能替代缺失的分项事实（2026-08-20）

### 文献与方法假设

Armstrong、Collopy 与 Yokum 所说的 causal forces 是研究者基于领域知识对未来趋势方向和函数形式的判断，**不是因果识别，也不证明 H-A 或 H-B 为真**。其分解方法仅在四个条件同时较强时主张使用：总量不确定、研究者能拆成受不同方向力量影响且有经济恒等关系的可观测分项、这些力量方向不同、并且在事前模拟中分项比总量更可预测（短序列可使用预注册的相对波动代理）。原试验是 12 条年度序列、1–10 年窗口，实证对象是乘法分解；作者后续更正为符合条件的序列几何平均 `MdRAE` 降低 64%，不是 “MdAPE 降低超过一半”。不满足条件时结果高度异质、包括显著变差，因此不得以偶然事后改善采用该方法。[Armstrong, Collopy & Yokum 原文](https://repository.upenn.edu/bitstreams/cbec1013-046d-453f-b6e6-eae86e3d3ccc/download)；[Armstrong 后续方法说明](https://repository.upenn.edu/bitstreams/d3a8532e-f8d1-4b24-9b62-c2c0e8595056/download)

### 格力小型适用性测试

格力满足前 3 项的候选条件：竞争状态高度不确定；可提出渠道/价格带重配（H-A）与广泛竞争/价格实现恶化（H-B）的不同趋势假设；行业全渠道零售增长、线上低价压力与格力国内收入收缩/产品毛利未塌陷的方向也并不一致。第四项失败：当前 PIT package 没有品牌×渠道销量/销售额、ASP/价格带、返利/佣金、sell-in/sell-out 或经销库存，不能定义乘法 component identity，更不能在 cutoff 前比较“分项预测 vs 总量预测”；现金端也没有 normal owner cash adjustment bridge。故将总收入机械拆成“量×价×组合”，或将表观 OCF 机械拆成 owner cash，都是不可检验的叙事，而不是因果分解。

### 既有资产映射

- `operating_transition` 案例卡只负责指定是否存在“需求/份额/价格带/渠道”相互冲突的状态转换；它不提供任何格力分项数值。
- `franchise_customer_lockin` 是 H-A 的价格实现与高端/线下留存条件；`technology_transition` 是 H-B 的替代与渠道失效条件；`mature_cash_return` 检验收入分解最后是否落入调整后现金与资本配置。四张卡都只能生成 FDB/FJ 取证问题。
- G1-J 的 `financial_driver_bridge` 是分解后的经济解释与后续财务传导边界，但当前 schema 尚没有 component identity、重构公式及 “component-vs-global” 事前判胜规则；在一个真实 PIT episode 验证前，不能声称 FDB 已实现因果力分解。`thesis_test` 只可接收通过预检且与同口径 FJ 绑定的 parent prediction。
- PIT 回放可复用现有 FJ→claim→HBT 路径逐项结算已冻结的 parent 与 component 预测，并与同口径总量基线比较；但须先物化 component identity、重构和比较对象。绝不由后来收入总额倒推当初应有的分项，亦不把同一公司多期拆分计作独立样本。

### 路线修订与验收

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING + MODEL + WRITING`。错误分解会把行业需求或线上份额错误归为品牌份额、ASP 或价格权，进而材料性改变正常利润、owner cash、持续期与永久损失。禁止利用产品毛利、行业总量或管理层叙述补出任何一个分项；禁止把收入分解自动延伸为费用、现金或 owner cash；禁止引用论文中的误差改善率为格力预测准确率、概率或估值确信度。

先在一个**非格力**真实 PIT episode 为一个 parent metric 冻结总量基线、分项基线、历史训练窗、扩展窗口、预测期、数据版本与重构公式；仅当预注册的分项预测性门和重构门均通过，才让它进入 FJ。费用、营运资本、Capex 与 owner cash 仍由现有四层 FDB 另行取证与传导。格力在取得上述数据并通过预检前只保留 H-A/H-B 和 aggregate `UNKNOWN`；该方法不形成中心路径，也不新增模型或评分器。

## 62. ITER-58 — 格力竞争数据的采集目标可以收敛为两条不能混用的轨道（2026-08-20）

### 供应方字段核查

奥维云网的官方数据产品说明明确称其家电零售监测覆盖线上、线下、抖音和下沉等渠道，并可按品牌、品类规模、市场地位、产品价格、产品属性、渠道和区域分析；其产品介绍亦列示线上家居的销售额、销量、均价和型号维度。[奥维云网：数据产品](https://www.avc-mr.com/product/content?type=data) 这只是**能力证据**：当前格力 PIT package 仍只有 CNInfo 公司文件，年报中转引的 AVC/产业在线数字不是独立行业源包。只有获得带历史版本、数据字典与定义的授权切片后，AVC 才是检验 H-A/H-B **零售端**所缺“品牌×渠道×销量/额×价格/产品”的合适候选。它不自动提供格力经销商返利、库存或公司的营运资本/受限现金调整。

产业在线官方的历史公开材料至少表明其曾统计品牌口径的空调内销销量和份额；这类数据应被视为**出货候选轨**，而不是自动命名为 `sell_in`：只有源方的交易点定义明确确认时才可使用该标签，否则必须记录 `SHIPMENT_SEMANTICS_UNRESOLVED`。自然期、冷年映射、品牌边界、版本与修订政策同样须由源方确认。[产业在线：2020 空调内销品牌口径说明](https://www.chinaiol.com/News/Content/202102/21_27071.html) 不得把它与 AVC 零售/sell-out 相除或无标记拼接。券商图表、新闻转述和动态网页只可帮助定位供应方，不能成为 PIT 事实源。

### 最小采购 / 物化合同

每个新数据切片须固定：数据集/产品 ID、覆盖自然期、发布日期/取得日、供应方版本、数据截至日、查询/下载身份、修订政策、空调品类与品牌/集团映射、渠道及排除渠道、零售还是出货、销量与销售额、ASP 或可复算均价、价格带/产品维度、对手集合、行业分母、地域和表/字段身份。AVC 的结果只写 `PCOBS:` 或经审核的 comparison observation，不复制成格力公司事实；产业在线轨仅在交易点定义明确时标记 `sell_in`。返利/佣金、经销库存、销售回款、受限资金、维持性 Capex 和资本事项继续只从公司披露与附注构建。

### 失败边界与验收

根因是 `ACQUISITION_MODULE + DATA_COVERAGE`。若把一家供应方的静态当前页面、行业均价或单一渠道报告冒充可回放品牌机制数据，H-A/H-B、normal owner cash 和持续期都会被伪精确化。禁止先写中心路径、再按支持结论挑选周期或渠道。

验收是：同一 cutoff 的零售轨与出货轨各自可复现，口径不混同；`FJ:GREE:competitive_position` 至少有一条完整轨的格力/主要对手/行业分母 t0/t1 面板。AVC 可结算 H-A/H-B 的零售端渠道与价格带相对位置；出货轨至多是 H-B 的早期信号，两轨背离只能触发库存、回款、返利和收入确认的公司披露任务，不能自行判胜。`FJ:GREE:revenue_margin_transmission` 还须有公司同分类销量/收入、毛利、销售费用、返利/佣金与经营利润 bridge；现金和资本配置 driver 仍以独立 official facts 通过。授权数据不可得时维持 `UNKNOWN`，不以公开摘要降级替代。

## 63. ITER-59 — pair/card 必须成为新 G1-J 冻结门，不能只在写了时校验（2026-08-20）

### 失败复现与根因

独立审阅复现：旧 `thesis_test` 在 `forward_judgment_required=true` 时，如完全省略 `rival_hypothesis_pairs` 与 `analogy_transfer_cards`，仍给出 `REVIEWABLE`；只有调用者主动提交对象时才验证其完整性。因而一份报告可拥有中心路径、FJ 和回放 claim，却没有同粒度反方预测或案例迁移边界。

根因是 `REASONING + MODEL + WRITING`。经济影响是“最强反方”可能退化为散文，或研究者只声称读过案例卡，却没有让它产生可结算的竞争信号；这会错误增强竞争持续期、normal owner cash 和永久损失判断。禁止把 `competitive_tests`、普通反方段落或提示词当作 pair/card 的等价物。

### 最小修复与验证

`thesis-test-policy.v3` 增加 `rival_hypothesis_pair_required`。新 PIT/G1-J 初始化设置该字段；policy 为真且 pair/card 均缺时，冻结返回 `INCOMPLETE`。旧 policy 默认 false，不追溯重写或否定已冻结 ledger；一旦新 policy 提交 pair，仍沿用原有的共同事实、双预测、6–12 月早期信号、终局信号、FJ 反向链接和每 pair 一卡的严格验证。投资和 CJO 的 PIT prompt/受限 writer 都明确要求这些对象。

定向回归覆盖：legacy FJ ledger 没有 pair/card 仍为 `REVIEWABLE`；新 policy 的同一 ledger 变为 `INCOMPLETE` 并逐项报告 pair/card 缺口；完整 pair/card 通过。随后加入 near-miss 两态约束后，PIT CJO/投资工具与 thesis migration 回归合计 78 项通过；报告输出和 reader coverage 的联合回归另有 73 项通过。

### 反例边界的收口

同轮修复将 `strongest_near_miss` 划为两种明确状态：`VERIFIED_EPISODE` 必须给出 `CASE:`、`MEP:`、`CASEEV:` identity、结构断裂和来源参考；`UNKNOWN_NO_QUALIFIED_EPISODE` 必须说明原因与保守处理，并强制 card 为 `QUESTION_ONLY`，不能支持中心路径。新 policy 下再填一个书籍方法卡名字、未核验案例名或自由 reference 会被拒绝；legacy card 维持旧字段兼容，不能冒充 G1-J 覆盖。

这关闭的是 `MODEL + WRITING` 的自由字段缺口，仍不凭空创建格力反例。`DATA_COVERAGE + REASONING` 的剩余边界是当前没有同机制、PIT、已结算的近失效 `MEP:`；因此格力只能将案例卡作为取证问题，而不能以它支持 H-A/H-B。没有合格反例时必须诚实保留 `UNKNOWN`，不新建平行案例库。

## 64. ITER-60 — 行业架构与存量—流量时滞只作为可证伪的取证试验（2026-08-20）

### 文献问题与可迁移命题

Jacobides、Knudsen 与 Augier 将行业架构定义为塑造分工的行业模板：接口、互补资产和要素流动性决定价值怎样被创造和攫取，而非“公司是否垂直整合”一项事实。[发表版原文](https://doi.org/10.1016/j.respol.2006.09.005) 因而行业分析若只并列市场份额、毛利和渠道数量，仍遗漏“利润最后停在哪个接口”的机制。Sterman、Repenning 与 Kofman 的企业动态研究则显示，反馈、存量和时滞可以使短期财务观察与长期经济机制背离；该文支持把动态链拆成可观察存量与流量，不支持无数据的行业仿真。[原文](https://doi.org/10.1287/mnsc.43.4.503)

### 格力的失败复现与最小设计

当前格力 H-A/H-B 对已经有渠道、量价、费用、现金的相反预期，但还无法回答两个更深的问题：低价线上份额变化后，安装/售后/经销/高价格带等接口是否仍保留价值；以及出货、终端 sell-out、渠道库存、回款和利润本应以怎样的先后顺序变动。把线下网点、仍为第一的排名、产业出货或表观 OCF补作答案，会直接把渠道重配误判成护城河，或把库存腾挪误判成结构恶化。

故新增的不是模型或分数，而是两个可撤销的 pilot：

1. 对一张已有 `analogy_transfer_card` 的状态向量补写五项**有来源或 UNKNOWN**字段：`division_of_labour`、`interface_control`、`co_specialized_assets`、`factor_mobility`、`appropriation_node`。每个材料 pair 必须从中推出至少一个原先没有、主/反预测不同的接口观察和一项最小外部查询；做不到即撤销该图。
2. 对一个具有同口径数据的历史 PIT episode，至多冻结四项存量及其单位、期初/变动/期末、相关流量、时滞和两条反馈链。H-A/H-B 必须预先给出不同的先后顺序，结果只能以许可或官方经营资料结算。没有可定义存量，或两条机制仍得到同一序列，即不进入 G1-J 硬门。

### 根因、边界与验收

根因是 `REASONING + DATA_COVERAGE`，不是缺少更多格力报告。经济影响是错误的接口或库存解释会材料性改变竞争持续期、正常利润、owner cash 与永久损失判断。禁止把公司自述、垂直整合、线上份额、单期出货、收入、OCF或股价当作接口控制、存量或时滞证据；也禁止从研究论文移植参数或预期回报。

格力当前两种图均为 `UNKNOWN`：缺品牌×渠道×销量/额×ASP/价格带、经销激励/库存、sell-in/sell-out 与服务接口资料。采集到这些资料前，保持现有 H-A/H-B pair 与 `UNDISCRIMINATED`；若取得资料，只先在单个历史 PIT episode 验证“是否导出新的、可结算的序列”，绝不由一次通过宣称预测能力或经验概率。

## 65. ITER-61 — 持牌行业数据必须穿透 PIT 生产链，但不能污染公司事实（2026-08-20）

### 失败复现与根因

底层 HBT 已能以 `LICENSED_INDUSTRY_DATA` 结算预注册的竞争/单位经济 FJ，但首次链路审查发现该类型仍会在 FDB、thesis/writer、PIT source projection 或 production adapter 的某一环被拒绝、丢失 `official=false` / `industry_data_contract`，或被误标为公司公告。相反，若只把字符串加入全局 allowlist，又会允许它被现金转换、资本配置或投资回报 FJ 使用。

这是 `ACQUISITION_MODULE + REASONING + MODEL` 的材料性问题，不是报告文风问题。前一种失败令真实 AVC/产业在线历史版本即使已取得也无法进入可结算格力机制学习；后一种失败会把行业份额或零售 ASP 伪装为回款、受限资金、资本纪律或 owner cash 证据，进而错误改变永久损失判断。

### 最小修复与验收

已将该来源限定为 `COMPETITION_DEMAND` 与 `UNIT_ECONOMICS` 的 `FDBMON`：现金转换、资本配置和所有 `FDBREAL` 仍拒绝它。FJ 的 outcome source type 必须与其所有已冻结 FDB monitoring contract 的共同允许集相交；一旦使用持牌行业数据，其 metric、unit、measurement basis、period 与 observation window 也必须逐项相同，禁止在同一 provider label 下换分母、渠道或期间。production adapter 同时保留非官方标记与完整行业数据契约。PIT workspace 允许已读取的 CSV/导出文件以其自身作为 reader view，并在 document manifest 明示 `licensed_industry_data / industry_data`，而非 company filing；`verify_official_fact` 也明确拒绝把它提升为 VERIFIED 公司事实。旧 v1/v2 public schema 同步暴露该 source type，避免 writer/runtime drift。

定向回归（150 项）实际检查了三类会改变下一步动作的失败：真实持牌 CSV 能否从 allow-read 投影到冻结 case 并保留 `official=false` 与 contract；它能否绕过现金 driver 或官方事实验证；以及同一来源类型下是否可偷换 metric/period。全部通过。验收尚未等于格力数据已具备：下一步仍须取得原始、历史版本的 AVC/ChinaIOL release，建立同口径 FDBMON/FJ，再以既有 HBT 结算；在此之前 H-A/H-B 仍为 `UNDISCRIMINATED`。

## 66. ITER-62 — 同行 cohort 要按机制复制逻辑选取，不能事后挑“成功/失败案例”（2026-08-20）

### 文献与失败复现

Seawright 与 Gerring 将小样本 case selection 区分为 typical、diverse、extreme、deviant、influential、most-similar 与 most-different；不同选择策略服务于不同的组内因果分析，不能把小样本当随机样本。[Seawright & Gerring (2008)](https://doi.org/10.1177/1065912907313077) Eisenhardt 的多案例研究进一步强调，每个 case 是独立的分析实验，应以 literal replication、theoretical extension 或 contradiction 的逻辑比较，而不是把案例数当统计 n。[Eisenhardt (1989)](https://doi.org/10.5465/amr.1989.4308385)；[Eisenhardt & Graebner (2007)](https://doi.org/10.5465/amj.2007.24160888)

路线原来规定了“直接竞争者、不同战略路线、国际可比和失败反例”，但没有要求在每个 PIT cutoff 前记录选择规则。尤其“失败反例”若由后来结局入选，会把已知答案偷偷带回报告 cohort，并偏向 H-B 或资本配置悲观解释。

### 最小研究设计

R1 的 5 家同行 × 3 时点在读取正文前新增一个轻量 `case_selection_register`，不新建案例卡或评分器。每条记录：共同机制问题、截止日前可得的 universe 与状态字段、选择模式、case role（`LITERAL_REPLICATION` / `THEORETICAL_EXTENSION` / `DEVIANT_TEST`）、预期能区分哪条 mechanism arrow、排除规则、公司/时期/机制 cluster 与结果隔离声明。格力可分别选 most-similar 的国内直接对照、不同渠道/产品结构的 diverse 或 most-different 对照、以及在 cutoff 当时已呈现压力信号的 deviant test；它们都仍须在未来结果未读时完成 PIT 报告。

已知后验失败若只想用于教学或生成反方问题，必须标记 `OUTCOME_SELECTED_RESEARCH_ONLY`：可进入书籍方法卡的取证提示或候选 near-miss，不得进入盲 PIT 报告的 evidence、中心路径、FJ 对错评估、独立性 cohort 或经验概率分母。

### 根因、边界与验收

根因是 `REASONING + MODEL + WRITING`。经济影响是结果导向的 peer 选择会使行业竞争持续期、normal owner cash 和永久损失看似被“经验”证实，实则是在挑选答案。禁止按后来股价、终局经营、资本损失或名人叙事选择同一批用于预测检验的公司。

验收为：每个进入 18 份报告的公司—时点都能回溯到 cutoff 前 state vector 与选择模式；至少一例 literal replication 和一例 theoretical extension/contradiction 对同一机制产生不同预期；任何 outcome-selected 对象均被 runtime/审阅排除在 PIT result label 和 calibration cohort 外。格力当前只保留角色设计，尚未选择或冻结同行，故不增加任何 case 数或置信度。

## 67. ITER-63 — 公司公告包与持牌行业 release 必须组合为同一 PIT 信息集（2026-08-20）

### 失败复现与根因

公司 41 源盲轨与独立行业数据各自都可被 PIT runner 读取，但实际格力 CJO 需要在**同一个** attestation、snapshot 与 production case 中同时引用两类来源。此前没有合并入口；若手改 JSON，原完整公司 inventory、冻结的 source selection 或行业 release 的 rationale 很容易丢失，且通用 PDF acquisition 会错误尝试下载持牌 CSV。

根因是 `ACQUISITION_MODULE + MODEL`。经济影响不是数据多一份少一份，而是可能使竞争 FJ 与公司现金/资本 FJ 被拆到不同信息集，无法审阅同一 H-A/H-B 机制链；或诱导使用未被允许读取的行业文件。禁止把独立 manifest 当作公司 source package 的替代，也禁止通过通用 downloader 访问供应商数据库。

### 最小修复与验收

新增 `compose_company_manifest_with_independent_industry_sources(...)`：保留完整法定公告 inventory，仅追加已声明、可在 cutoff 准入的 `LICENSED_INDUSTRY_DATA`，并以新的 selection policy/reason 和逐源 research rationale 重建 selection；旧 manifest 不被修改。`acquire_source_package(...)` 对该类型只检查操作者已放入 package root 的导出文件，记录 `LICENSED_EXPORT_PRESENT`，绝不联网下载或伪造 PDF/page markdown。随后的 PIT workspace/adapter 再按既有 contract 投影与结算。

164 项定向回归覆盖组合后 inventory/selection 的完整性、输入 manifest 不被改写、持牌 CSV 不触发 downloader、CSV projection、非官方身份、driver 边界与 FJ 口径匹配。通过不代表已有格力 vendor release；真实接纳仍需原始历史导出文件、release/query/revision 字段和对应的 H-A/H-B FJ。未取得时保持 `UNDISCRIMINATED`。

## 68. ITER-64 — 公司经验须以关键决策 episode 获取，且不得污染 PIT 或事实账本（2026-08-20）

### 文献与问题

Klein、Calderwood 和 MacGregor 的 Critical Decision Method 以一段具体、困难的决策为对象，回溯时间线并追问决策者使用的线索、目标、备选方案和判断过程，而不是收集泛泛观点。[原始论文](https://doi.org/10.1109/21.31053) Crandall、Klein、Hoffman 的 *Working Minds* 将这类 cognitive task analysis 用于提取心智模型、关键线索与推理策略。[MIT Press 原书](https://mitpress.mit.edu/9780262033510/working-minds/) Klein 的 premortem 则要求在行动前假设其已经失败，以更早暴露团队不愿提出的反方路径。[原文](https://hbr.org/2007/09/performing-a-project-premortem)

这正好回答“公司经验”何时有用：它可以发现公开年报没有表达的渠道、安装/售后、供应链或产品组合决策约束；但它不能让一位受访者的确信、关系或叙事成为事实，更不能把今天知道结果后的回忆倒灌进旧 PIT 报告。

### 最小采集设计

只有取得合格授权和一手决策材料时，才创建一个轻量 `operating_decision_episode`，而非新的案例库。其最小字段为：角色与利益相关方类别（不保存不必要的个人身份）、发生日期/地点/业务范围、事件触发、按时间排序的关键线索、当时目标和约束、被认真考虑但未选的替代方案、采取动作、当时预期的经营后果、与 H-A/H-B 的机制箭头链接、以及一个在访谈前写下的“如果该解释错误会先看到什么”的独立 FJ。研究者随后写一份短 premortem：假设这套解释已经失败，列出可观测的失败链；它必须与对立机制产生不同信号，不能只再写一遍风险清单。

结算仍只使用允许的公司官方或持牌独立行业观察。访谈可以提出 `MECHANISM_DISCOVERY`，不能生成 `VERIFIED` 公司 observation、行业份额、库存、返利、现金或资本配置事实。对历史 PIT，只有在 cutoff 前已经存在、可定位的同期记录才能进入 source package；截止日后的访谈即使谈的是旧事件，也标记 `OUTCOME_SELECTED_RESEARCH_ONLY`，只能帮助发现反方问题或候选验证任务。

### 根因、边界与验收

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`：格力公开资料缺全渠道量价、库存和渠道激励机制，而把管理层访谈、经销商传言或研究者直觉当成补洞会产生不可结算的叙事。经济影响是会虚增 H-A 的服务/渠道护城河，或虚增 H-B 的竞争恶化，从而错误改变竞争持续期、normal owner cash 和永久损失判断。禁止将受访者身份、语气、所谓“行业共识”、后验回忆或单个案例作为中心路径证据；也禁止以访谈取代 AVC/ChinaIOL release 或公司披露。

验收不是“完成若干访谈”，而是每一个准入 episode 均导出一项此前不存在、可明确削弱主/反机制之一的经营观察；至少一条独立后续 observation 能结算它，且反方 premortem 也有同等的可结算路径。若没有真实、授权的一手材料，或新 episode 没有产生不同的 FJ，则不创建对象、格力继续 `UNKNOWN / UNDISCRIMINATED`。当前没有任何格力 operator episode 被准入。

## 69. ITER-65 — 同行选择与真实行业数据入口必须能在生产路径被强制执行（2026-08-20）

### 失败复现与根因

路线图已规定 cohort 不得按后验结果选择，也已规定公司公告和行业 release 必须在同一 PIT package；但此前前者只是一段文字，后者只提供 Python helper。结果是未来研究者仍能将事后挑出的“失败案例”写进 PIT 报告/基准率候选，或需要手写脚本才能把一个合法 release 接进格力 CJO。

根因是 `ACQUISITION_MODULE + REASONING + MODEL`。经济影响是后验选择会伪造反例、污染对竞争持续期和 normal owner cash 的经验学习；入口不可达则会诱导以 CHEAA 转述、年报转引或假数据代替原始 industry release。禁止把同一公司的多个时期视为自然独立，也禁止把已知结果选择的对象或行业上下文 PDF 升格为 PIT 证据。

### 最小修复与验收

`case_selection_register` 现冻结共同机制问题、cutoff 前 universe/state vector、选择模式、复制角色、预期区分的 mechanism arrow、排除规则和 company/period/mechanism cluster。只有 `PIT_PRE_OUTCOME + INCLUDED` entry 可进入预注册 cohort；`OUTCOME_SELECTED_RESEARCH_ONLY` 被 claim evidence、thesis central/FJ 与 calibration candidate 三条生产路径明确拒绝。它不新建案例库，不创建 case，也不增加独立样本或经验概率。

行业通道新增 `enumerate-industry` 与 `compose-industry` CLI：前者验证授权历史 release 的 contract，后者要求 company code/cutoff 相同、行业 manifest 为 `REVIEWABLE`、以及每个新 source 有选择理由；`download-package` 对本地 CSV 只做注册。用真实格力 889 inventory/41 selected package 与临时合格 release 已实际跑通 `enumerate → compose → package → PIT runner → workspace document manifest`：42/42 selected `COMPLETE`，runner 和含年报/industry data 的 document manifest 均 `REVIEWABLE`。临时 release 不写入格力事实或冻结报告。

本轮 215 项定向回归覆盖 cohort outcome-isolation、claim/thesis/base-rate 拦截、compose CLI、source package、CJO、FDB、FJ、HBT 与官方事实边界。真实接纳仍需一份原始、历史、带 query/revision/范围身份的 AVC 或 ChinaIOL export；取得前格力没有 cohort、没有 CJO completion/snapshot/attestation，也没有 H-A/H-B 的胜负或投资结论。

## 70. ITER-66 — owner-cash 采集先保留现金流方向，不能把保证金变化一概加回（2026-08-20）

### 失败复现与根因

跨期补取 2023–25 格力年报时，原采集规则把 FY2024“票据、保函保证金等经营活动有关受限资金**净增加** 9.51 亿元”误归为受限资金释放；FY2025 又同时披露净减少 156.67 亿元和净增加 9.51 亿元。若只保存一个正数“受限资金变化”，2024 的现金流出会被错加回 owner cash，2025 两条不同方向、未证明同一资金池的项目也会被机械轧差。

根因是 `ACQUISITION_MODULE + REASONING`。经济影响是 normal owner cash、分红安全边际、金融资产可得性和资本配置判断均可能被材料性高估。禁止把 OCF–Capex、货币资金、现金等价物、交易性金融资产或保证金净变化直接称为普通股可分配现金。

### 修复、边界与验收

采集层改为两个分方向字段：`operating_restricted_funds_release_rmb_m` 与 `operating_restricted_funds_addition_rmb_m`。官方 `CASH_STATE` 序列现覆盖现金及等价物、非等价物定存、受限存款、交易性金融资产、OCF、Capex、销售收现、营运资本及上述分方向保证金：FY2023 净减少 6.30 亿元，FY2024 净增加 9.51 亿元，FY2025 同时为 156.67 亿元净减少和 9.51 亿元净增加。格力 fact ledger 重建为 `REVIEWABLE / 257 VERIFIED`，22 项定向采集回归通过。

这只满足 `CASH_STATE`，不满足 `NORMAL_OWNER_CASH`：保证金池跨年定义、金融子公司监管资本与现金归属、定存/交易性金融资产期限及质押、维持性 Capex、逐期营运资本贡献和真实普通股分配现金仍缺。接纳条件是每项 adjustment 有同一资金池/口径证明、重复性判断和冻结 FDB monitoring contract；未满足时只能 `UNKNOWN / UNRESOLVED`，CJO 不得生成估值、回报或行动。

## 71. ITER-67 — 供应方产品页可定义采购范围，不能替代历史 release（2026-08-20）

### 原始来源检索

[奥维云网的数据产品页](https://www.avc-mr.com/product/content?type=data) 明示家电零售监测覆盖线上、线下、抖音和下沉渠道，并支持品牌、价格、产品属性、渠道、区域与竞争对比；它说明 AVC 是 H-A/H-B 零售端的合适候选，但不是任何历史时点的可用 observation。[产业在线的月度家用空调报告目录](https://www.chinaiol.com/Report/202005/9_797.html) 明示其为 Excel，包含企业产销存、品牌按内销量格局、重点企业以及内外销对比；这使其成为出货/库存轨的合适候选。产业在线还公开说明 C 端细分品牌报告在内销出货基础上新增细分品牌、OEM/OBM 拆分，但公开文章同样只是产品能力线索。

### 结论与执行边界

根因仍是 `DATA_COVERAGE + ACQUISITION_MODULE`：公开产品页回答“应索取哪些字段”，不能证明某个历史 release 的版本、query、分母或交易点定义，更不能给出格力的全渠道/价格带面板。经济影响是若把能力页、新闻或年报转引升级为数据，H-A/H-B 会被没有相同口径的数字伪裁决。禁止把 AVC 或产业在线的当前网页、报告目录、摘要图表或二手转述写进 company fact ledger 或直接结算 FJ。

因此已将最小请求固化为 [格力 V1 独立行业 release 最小交付单](GREE_V1_INDUSTRY_RELEASE_ACQUISITION_SPEC.md)：AVC 请求 retail sell-out 的品牌×渠道×量/额×ASP/价格带；产业在线请求品牌/企业的生产、内销、出口与库存，并在供应方交易点定义缺失时保持 `SHIPMENT_SEMANTICS_UNRESOLVED`。接纳条件仍是原始历史 export 加 release/query/revision/范围合同，经 composite PIT package 进入 FDB/FJ。当前没有合格 release，格力不增加任何判断置信度。

## 72. ITER-68 — 资本配置必须冻结“启动承诺→后续 movement→兑现”，不能从余额或减值倒推（2026-08-20）

### 文献、失败复现与根因

资源配置不是在单一董事会时点完成的静态选择。Noda 与 Bower 将战略过程描述为上下行相互作用中的持续资源配置；Burgelman 进一步说明中层推动的战略行动会在资源承诺、选择与保留中逐步显形。[Noda & Bower (1996)](https://doi.org/10.1002/smj.4250171011) [Burgelman (1983), Academy of Management Review](https://doi.org/10.5465/amr.1983.4287661) [Burgelman (1983), Management Science](https://doi.org/10.1287/mnsc.29.12.1349) 因此，用一次减值、期末金融资产余额或一笔投资现金流直接判断“资本毁损”或“流动性管理”，会跳过真正决定永久损失的启动资金、追加/收缩以及经营兑现链。

此前 `allocation_event` 已有分类、日期、自由文本兑现期与 `FDBREAL:`，却未强制记录启动承诺和随后资源 movement。一份报告因此可能以格力钛减值写出资本毁损，或以金融产品余额写出流动性管理，却没有可审计证据说明累计投入、资金来源、后来是否追加/撤退以及应由哪一个后续观察结算。根因是 `ACQUISITION_MODULE + REASONING + MODEL`，不是报告篇幅。

经济影响是资本配置会被错误传到 normal owner cash、再投资回报、永久损失与（仅投资用途的）价值区间。禁止用股价、回报、一次减值、期末理财/交易性金融资产余额或“管理层一贯谨慎”的叙事补齐启动金额、资金来源或后续资源变化。

### 最小修复与格力边界

新初始化的 `financial-driver-bridge-policy.v2` 只为新生产运行增加窄约束，不重写遗留冻结对象。每一个 material `allocation_event` 必须冻结：

- `initial_commitment`：已披露金额须带币种与 VERIFIED observation；资金来源已经披露时一并冻结，未逐笔披露时可填 `funding_source=UNKNOWN`，但必须给出 unknown reason 与 conservative treatment；金额本身未披露时才允许 `amount=UNKNOWN`。两种未知都不能编造资金来源；
- `commitment_movement`：启动日期以后最早可观察的 `ESCALATE`、`MAINTAIN`、`DEESCALATE` 或明确 `UNKNOWN`，并带已验证 observation，或在 UNKNOWN 时保留原因与保守处理；`MAINTAIN` 还须是来源明确披露的继续决策/授权，静态持股或余额不能替代；
- movement 必须精确指向该 event 的 `FDBREAL:`，以及其早期或终局 `FDBMON:`，从而使“资源动作”与后续 FJ 结果采用同一冻结 metric、来源、窗口和可比性规则。

这不是新的案例库、概率模型或资本配置评分。它也不判断 event 是好是坏；它只使未来“为什么如此判断、接下来什么事实能推翻它”可被结算。`COMPANY_JUDGMENT_ONLY` 同样适用，但仍禁止价格、估值、回报和交易动作。

格力的金融产品滚动与格力钛在建工程减值都未具备完整启动投入/资金来源与后续 movement 的官方链。因此它们当前只能登记为 `UNRESOLVED`：前者不能称作可分配现金、稳健流动性或价值毁损；后者不能称作已证实的累计资本毁损、退出或继续加码。格力钛的**股权承诺**则不能继续笼统称为金额未知：2021 控制权司法拍卖成交价与 2023 增持少数股权对价均可从现有官方源包验证，它们构成“启动→加码”的已知部分；但实际资金来源、2023 后新增/撤回资源和经营兑现仍未闭合。契约允许把这些缺口留为字段级 `UNKNOWN`，但不能通过 CJO 冻结来制造资本配置质量结论。

### 验收

定向 `financial_driver_bridge` 回归 18 项通过：缺启动承诺、将 movement 接到错误 monitoring contract、CJO 缺可验证 movement observation 都不能通过；历史 v1 policy 保持可读；金额未知、或金额已知而资金来源未知但有明确原因/保守处理时，都不再强迫虚构字段。格力的接纳条件仍是每个材料 event 有正式 source ID、日期、可验证启动承诺或诚实 UNKNOWN、冻结后的 6–12 月 movement 与 3–5 年 outcome contract。未达到前，资本配置只作为需要继续采集的机制，不进入中心路径、normal owner cash 或投资结论。

## 73. ITER-69 — 现有格力源包已能验证股权承诺金额；未知应落在资金来源和兑现，而非整个事件（2026-08-20）

### 事实试验

以已允许读取的 CNINFO 原件逐页复核并写入 exact-quote facts，而不使用新闻或二手交易摘要。2021-10-30 的交易进展公告确认格力以 18.282751 亿元取得银隆新能源（后称格力钛）30.47%控制权；2023 年经审计年报确认，当年受让 24.54%少数股权作价 10.153284 亿元、直接持股升至 55.01%，并将该子公司的投资成本滚动列为 28.443861 亿元。四项 observation 均从现有 PIT source package 的相应页面回验，fact ledger 为 `REVIEWABLE / 257 VERIFIED`。

这推翻了上一轮“格力钛启动投入未知”的过宽结论，但不推翻资本配置质量仍未裁决。2021 司法拍卖价与 2023 年报中期初投资成本有小额差异；没有交易费用或会计处理 bridge 时，不能互相替代或机械求和。更关键的是，公告没有把两次收购的实际资金来源逐笔归因，也没有给出 2023 后追加运营资本、减资/退出、独立现金流或完整可回收价值链。

### 根因、修复与验收

根因是 `ACQUISITION_MODULE + REASONING + MODEL`：旧采集已经拥有公告，却没有把“收购对价、权益增持和成本滚动”转成 allocation-event 的可冻结输入；随后又把“金额已知但资金来源未知”错误等同于“整个启动承诺未知”。经济影响是前者会遗漏至少已披露的资本承诺，后者则会诱导研究者以一次减值、现金余额或股价补写错误的资金故事，材料性改变永久损失和 owner-cash 判断。

修复没有再增加一套资本评分器。exact-quote verifier 直接生成可回查的官方 observation；bridge policy 允许数值金额与 `funding_source=UNKNOWN` 共存，但强制该未知的原因和保守处理。禁止把 28.44 亿元账面投资成本称为已实现损失、普通股可分配现金、格力钛全生命周期投资或退出价值；也禁止以 2023 后持股不变倒推“没有继续资源投入”。

接纳条件是将 2021 acquisition 与 2023 increase 分别写成 source-bound event：前者的后续 `ESCALATE` 可引用 2023 交易，后者仍须冻结一个 2024–26 的可观察 movement 或诚实 `UNKNOWN`；二者各有 FDBREAL/FDBMON/FJ 的 6–12 月行为和 3–5 年经营兑现合同。金融产品滚动仍需独立的期限、底层资产、质押、收益和资金来源资料。满足这些条件前，格力只升级为“已知部分资本承诺、资本配置质量 `UNRESOLVED`”，不升级为中心路径、估值或行动。

## 74. ITER-70 — 外部格力报告是分歧发现器，不是判断的投票箱（2026-08-20）

### 假设与试验

用户提出的“20 多份格力报告”可能扩大研究者对渠道、价格带、库存、经销商激励和资本配置的候选解释；但若把报告数、作者声望、目标价或一致结论当成证据，重复叙事会被错误放大，反而削弱第一性原理判断。现有工作区没有可逐篇读取的这批外部报告原件，因此本轮只为它们定义进入既有 PIT/反方回路的最小使用法，不能虚构已覆盖的公司经验。

本轮复核了 Richards J. Heuer, Jr. 的原始专著 [*Psychology of Intelligence Analysis*（CIA 公开版，1999）](https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/)。可迁移的窄原则是：把不同解释显式摆在同一个待解释事实之前，并优先寻找能让解释分叉的证据；不迁移“对材料打总分”的做法。对 Turtle 而言，现有 `rival_hypothesis_pair` 已承担前者；再叠一张报告一致性评分表只会混淆来源质量、独立性与诊断性。

### 可执行方法

每份报告首次出现时仅创建一条“分歧—验证”记录：`as_of / cutoff_status`、报告声称的机制箭头、它支持或挑战的 H-A/H-B、它与其他材料的不一致之处、它引用而尚未进入源包的原始资料、一个独立验证任务、以及该任务应使哪一项 pair signal 分叉。报告可以帮助发现遗漏变量和更强反方，却不能直接写入 VERIFIED fact、financial driver、FJ outcome、案例样本或中心路径。

同一论点被二十份报告重复，只产生**一个**待验证机制箭头；不同论点才产生不同验证任务。凡是在 PIT cutoff 后发表、或借已知经营/股价结果重述旧故事的报告，均为 `OUTCOME_SELECTED_RESEARCH_ONLY`：保留作反方提问，不能进入当时证据或历史结算。目标价、估值倍数和股票回报一律不进入该记录。

### 根因、经济影响与验收

这不是报告数量不足，而是 `REASONING + DATA_COVERAGE + ACQUISITION_MODULE` 的边界问题。缺少的是能把“线上份额下降究竟是渠道重配还是全渠道恶化”等分歧裁开的同口径全渠道 sell-out、品牌/渠道份额、价格带、库存和经销商激励观察；将卖方报告的转述升格为这些事实，会材料性地误判竞争持续期、normal owner cash、永久损失和（仅投资用途的）价值区间。

禁止以报告共识、报告篇数、重复图表、目标价、股价表现或单期毛利/OCF判 H-A 或 H-B。修复路径是：先由报告提出机制问题，再获取官方公司披露或有版本、查询和口径合同的授权行业 release；只有后者可以结算预注册 FJ。验收不是“读完 20 份”，而是每个外部论点均被合并、验证或明确保留为 `UNKNOWN`，且任何进入 H-A/H-B 的事实都能回到允许来源；直到原始持牌行业 release 到位，格力的竞争机制仍为 `UNDISCRIMINATED`。

## 75. ITER-71 — 行业“背景已物化”不等于官方行业包已完成（2026-08-21）

### 状态复核

只读复核格力目录后确认，当前实际存在的是一份 2025-09-08 出版的中国家用电器协会刊物 PDF，以及其中明确归因于 AVC 的六条 `INDCTX:` 背景观察；manifest 自身状态为 `MATERIALIZED_CONTEXT_ONLY_MANUAL_REVIEW`。此前官方行业环境设计中的八条 NBS/发改委 pilot 仍只有已定位的当期 URL 与预注册字段，并无逐条原始发布物，因此不应把整包描述为已物化。

根因是 `ACQUISITION_MODULE + WRITING`，不是新出现的公司基本面。若把协会转引或设计表误称为完整官方包，会高估外部需求/价格/政策背景的证据等级，并可能错误缓解格力竞争持续期和 normal owner cash 的不确定性。修复是将状态拆为“官方 pilot 未物化”与“协会补充已物化但仅背景”；禁止把后者当品牌份额、公司 ASP、返利、渠道库存或 FJ outcome。

接纳条件不变：每条官方背景序列必须保留当期原始发布物、可得日、指标定义、值、定位与禁止推断，才可成为 `REVIEWABLE` 的 `CONTEXT_ONLY` 环境包。即使通过，也不裁决 H-A/H-B；后者仍等待有历史版本和查询合同的品牌×渠道行业 release。

## 76. ITER-72 — 部分识别能约束单一事实，不能把未判别机制伪装成区间（2026-08-21）

### 文献与候选命题

Charles F. Manski 的 [*Identification for Prediction and Decision*（Harvard University Press，2008）](https://www.hup.harvard.edu/books/9780674026537) 把缺失或不完整数据下“数据实际告诉我们什么”置于预测和决策之前；[ *Public Policy in an Uncertain World*（Harvard University Press，2013）](https://www.hup.harvard.edu/books/9780674066892) 则直接反对以貌似精确的分析掩盖不可避免的不确定性。可迁移到 Turtle 的不是统计区间本身，而是顺序：先定义被识别的窄命题和所有可行值，再判断结论是否在整个可行集合内不变。

### 格力反例试验

将 H-A 与 H-B 强行写成“格力 normal owner cash 的低/高区间”失败：两条机制的量价、费用、营运资本和资本配置传导都缺同口径约束，且它们是竞争解释，不是一个金额的上下限。以二者作为 range 端点会违反路线图“中心路径不能由多个情景或有利边界替代”的规则；`forward_judgment` 的 `RANGE` 也只表达一个未来可观测 metric 的预测区间，不能承载当前未知机制。

同一测试分别落到四类格力命题：线上零售额份额 2023–25 的下降是已验证事实，不需要部分识别；H-A/H-B 的全渠道竞争位置为 `UNIDENTIFIED`；受限资金、营运资本与维持性 Capex 未有相同资金池/经济归属链，故 normal owner cash 没有可来源化的非平凡数值边界；格力钛已知 2021/2023 股权对价，但资金来源、后续投入和独立兑现未知，资本配置质量同样 `UNIDENTIFIED`。此处诚实的 `UNKNOWN` 比人为宽区间更有信息量。

### 采用边界、根因与验收

本方法以窄形式**采用**：每个材料性 `UNKNOWN` 都应被审阅为“是否存在一个单一 metric 的非平凡硬边界”；若有，冻结 `metric / lower / upper / formula / input evidence / PIT cutoff / forbidden inference`，并只报告该命题在边界内是 `ROBUSTLY_TRUE`、`ROBUSTLY_FALSE` 还是 `UNIDENTIFIED`。若没有，保留既有 `UNKNOWN + conservative_treatment`，不建新的评分器、概率层、参数或 CJO ledger。

根因是 `REASONING + MODEL`，不是写作不够细。把机制分歧、股价、估值敏感性或乐观/悲观情景伪装成“上下界”，会材料性地掩盖 normal owner cash、竞争持续期和永久损失的未知，并可能使投资结论看似稳健。禁止用结果期数据收窄边界，禁止把机制分歧写成数值端点，禁止由区间绕过中心路径或 FJ 结算。

验收条件是：任一边界的端点可由冻结的同单位、同范围、同期间事实和公式独立重算；它必须改变一个已声明的研究选择或明确证明“不足以改变选择”；审阅者能验证 range 不是情景集合。格力当前只有这一后者结论，因此不新增 CJO 参数，也不改变 H-A/H-B、owner cash 或资本配置质量的 `UNKNOWN`。

## 77. ITER-73 — 对称零售状态分解可提升竞争诊断，不能替代机制判断（2026-08-21）

### 文献、假设与实现

Anthony F. Shorrocks 的 [*Decomposition procedures for distributional analysis: a unified framework based on the Shapley value*（Journal of Economic Inequality，Springer）](https://link.springer.com/article/10.1007/s10888-011-9214-z) 给出的可迁移原则是：当一个结果由多个状态因子以恒等式共同决定时，对全部变动顺序取平均，避免研究者任意选择基期/变动顺序而左右各因子的记账贡献。这里迁移的是**对称记账**，不是因果识别或预测优势。

据此新增 `scripts/industry_retail_state_decomposition.py`：它只接受具有完整 provider/release/query/metric/scope contract 的 `LICENSED_INDUSTRY_DATA`、`RETAIL_SELL_OUT`、两期稳定 brand × category cell 面板；用行业规模 × category mix × 格内格力份额分别重构格力零售量和零售额，再以六种顺序的 Shapley 平均报告三项贡献。输出明确为 `COMPETITION_DIAGNOSTIC_ONLY`，不进入 cash、资本、估值或价格路径。

### 合成反例试验

以四个渠道×价格带 cell 的合成 AVC 风格面板测试，量和额的三项贡献均精确加总回格力零售变动；倒置输入 cell 顺序，贡献不变。测试同时拒绝 shipment 来源、跨期缺失 category cell 和试图把用途写成公司收入/估值的输入。连同原行业来源、thesis gate 与 adapter 的回归共 `123 passed`。因此模块解决的是“已有合格 retail 面板后如何避免结构混合掩盖格内份额变化”，不解决“为什么份额变化”或“公司经济后果是什么”。

### 格力边界、根因与验收

格力目前没有可使用的原始 AVC historical release；现有协会刊物中归因 AVC 的摘要仅为背景，不能组成双期品牌×channel×category 面板。因此本轮没有数值结果，H-A/H-B 仍是 `UNDISCRIMINATED`。

根因是 `DATA_COVERAGE + ACQUISITION_MODULE`，并有必须严格限制的 `REASONING` 风险：若拿 ChinaIOL shipment、线上份额或单期行业总量填补 retail cell，会把 sell-in/sell-out 和结构变化混为一谈，材料性地误判竞争持续期，继而污染 normal owner cash 与永久损失判断。禁止由分解直接推出公司收入、返利、库存、现金、资本配置、估值、股价或回报。

验收条件是取得同一历史版本、同一 query、完整映射的授权 AVC sell-out 面板；两期 cell 完整稳定、源契约和 PIT 时间边界通过；模块重构误差为零；其结果只被登记为 H-A/H-B 的一个预冻结 FJ 观察，并同官方公司资料共同结算。未满足任一项则保持 `UNKNOWN`，不以报告数量或市场摘要替代。

## 78. ITER-74 — 预注册的规格审阅能阻止“最有利渠道切分”，不能制造行业证据（2026-08-21）

### 文献与判断

Simonsohn、Simmons 与 Nelson 的 [*Specification curve analysis*（Nature Human Behaviour，2020）](https://www.nature.com/articles/s41562-020-0912-z) 指出，经验结论常依赖具有合理性的分析选择；其方法先列出理论上正当、统计有效且不冗余的规格，再展示全部结果，而不是只呈现叙事所偏好的一个。论文原方法的 joint inference 服务于实证研究；Turtle 不具备同类独立样本，不能照搬。

对格力采用更窄的“规格审阅”：在看到持牌 AVC 面板值前，冻结同一 release/query 中可由供应方字典支持的有限 `PANEL_SPECIFICATION` 视图（全渠道、线上/线下、稳定价格带、产品/冷量和品牌组映射）。每一视图按相同的完整 cell 规则运行零售状态分解，并逐项报告方向稳定性和改变结论的确切口径边界。它检验的是“观察是否依赖研究者挑选的切分”，不是“哪条机制概率更高”。

### 格力试验边界

当前不存在原始 AVC historical release，故没有可运行的视图、没有图表、更没有跨口径稳定性结论。为缺失的 cell 构造多个规格，只会把同一缺口重复多次。已有线上份额摘要也不满足此方法：它既无完整 category cells，也不能与线下或品牌映射做同口径比较。

根因是 `DATA_COVERAGE + ACQUISITION_MODULE`，潜在错误是 `REASONING`：挑一个对 H-A 或 H-B 最有利的渠道、价格带或品牌合并口径，会材料性地扭曲竞争持续期并污染现金质量和永久损失判断。禁止以规格数量、显示精美的曲线或小样本 joint inference当作证据；禁止在读取 release 后追加/删除视图，也禁止用缺失 cell 填补。

验收条件是：视图清单、切分理由、source contract 和可接受 cell 规则先于数值冻结；每个保留视图均可复算且显式报告，剔除的视图有口径/完整性理由；结论只说“跨视图稳定”或“依赖哪项边界”，仍须用 H-A/H-B 的其他 FJ 结算。达不到则不生成稳健性宣称，格力保持 `UNDISCRIMINATED`。

## 79. ITER-75 — 案例 ID 的形状不是公司经验；近失效必须回到已结算 episode（2026-08-21）

### 审计发现与修复

现有 8 张书籍方法卡确实已存在，且 `analogy_transfer_card` 已要求一个 `strongest_near_miss`。但初版验证只检查 `CASE:`、`MEP:`、`CASEEV:` 前缀，未核对它们是否在 append-only 案例登记簿中指向同一公司×时点的实际 episode、已记录 outcome 与独立 eligibility review。这会让一张迁移卡把格式正确的虚构 ID 当成“已验证反例”。

现已在 `base_rate_case_library.validate_verified_episode_reference` 中要求：案例存在且 episode ID 精确匹配；指定事件是该案例的可审阅 outcome；同案有可审阅的独立 eligibility review；案例与 episode 可审阅且整体状态为 `ELIGIBLE`。`thesis_test` 对所有声称 `VERIFIED_EPISODE` 的 near-miss 调用此解析；任一不符即不能冻结为 primary support。定向测试覆盖真实已结算 reference、episode 不匹配与仅有格式正确但不存在的 ID；`77 passed`。

### 经济边界

根因是 `MODEL + REASONING`，不是案例卡数量或写作。没有这条解析，表面相似的“巴菲特式案例”会被叙述升级为格力机制的证据，材料性地高估竞争持续期、现金质量和永久损失判断的可信度。修复也不把单个已结算反例变成基准率：它仅说明哪一个结构断裂值得让 H-A/H-B 生成更强的区分信号。

禁止以案例名、书中结论、ID 前缀、事后成功/失败、估值倍数或股票回报代替同一 frozen episode/outcome。验收条件是每个 `PRIMARY_SUPPORT` near-miss 都能解析为上述四项一致的登记簿记录；没有合格 episode 时，卡只能 `UNKNOWN_NO_QUALIFIED_EPISODE + QUESTION_ONLY`。格力当前属于后者，继续保持 `UNDISCRIMINATED`，不以新增 20 份报告填补。

## 80. ITER-76 — 旧报告的症结是把状态描述写成了判断和动作（2026-08-21）

### 实物复读

复读 `quality_references/000651_gree_v13` 的 Ch3、Ch4、Ch14 后，问题具体而非抽象：Ch3 从消费电器毛利率稳定直接推出定价权、全渠道护城河及 20–25 年持续期；Ch4 把 2025 年 OCF 463.8 亿元和 OCF/NP 写作盈利质量“再确认”；Ch14 以单一内销营收阈值选择“周期性低谷”60%主情景，并输出 Cautious Watch、2%建仓及价格动作。它们没有完成上述跳跃各自所需的同口径品牌×渠道量价、现金调整 bridge、对立机制/FJ 结算和可审计市场时点。

新事实使其中两条跳跃直接不成立：2025 OCF 含 156.67 亿元经营相关受限资金释放；2023 空调和 2024–25 消费电器产品分类不连续，且线上零售额份额由 2023 的 28.15% 降至 2025 的 24.31%。这些不是 H-B 的证明，却足以否定“毛利稳定/OCF 高，因此护城河和现金质量已验证”的写法。

根因是 `REASONING + MODEL + ACQUISITION_MODULE`，写作的高确定性语气属于 `WRITING` 放大器。经济影响会作用于持续期、normal owner cash、价值陷阱和仓位，故旧 Cautious Watch/2%不是可继承结论。禁止由报告完成标签、单期毛利、OCF/NP、线上份额、当前股价或后验表现恢复它。

修复与验收：把旧文作为明确标记的 legacy hypothesis；CJO 只冻结可验证公司状态和 H-A/H-B 的 `UNKNOWN`，先等同口径 FJ；只有竞争、量价费用和调整后现金的预注册观察共同结算，才选择公司中心路径。投资价格和动作独立后置。届时审阅者必须能指出每一条从事实到机制、到经营、到现金的箭头及其反方；否则报告仍只是计算准确的叙事。

## 81. ITER-77 — 关键假设必须成为机制冻结门，而不是报告里的自我提示（2026-08-21）

### 文献、假设与失败试验

CIA 分析中心的 [Ask Molly: SATs Advice](https://www.cia.gov/stories/story/ask-molly-sats-advice/) 将 Key Assumptions Check 解释为：列出并挑战支撑判断、且若不成立会使判断失效的最重要前提；同页也将 signposts/indicators 限定为可观察、可跟踪的未来事件。Heuer 的 [*Psychology of Intelligence Analysis*（CIA 公开版）](https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/) 提供了相容的反方原则：比较解释时应找能令解释分叉的证据，而不是加总支持材料。迁移到 Turtle 的结论很窄：关键假设不是“风险清单”或信心分数，而是每条竞争机制走向中心路径所必需的事实或可结算未来观察。

审计原有 pair contract 后发现，它虽已要求共同当前事实、双向 prediction、机制链和 FJ，却允许“线上份额下降 → 全渠道护城河仍在”或“OCF 高 → normal owner cash 稳定”这种箭头以自由文本 basis 存在。也就是说，报告可写出反方和阈值，却从未声明该跳跃必须依赖的全渠道位置、价格实现或现金 bridge。这正是旧格力报告三条跳跃能穿透冻结门的原因。

### 实现与格力边界

现将 `critical_assumptions` 写入 `rival_hypothesis_pair` 并同 snapshot—adapter 投影到回放 case：每条指定 `PRIMARY` 或 `RIVAL`，说明为何必要，并且仅能为三态之一。`VERIFIED` 要求当期 evidence；`TESTABLE` 要链接本 pair 的已预注册 discriminator；`UNKNOWN` 必须给出保守处理，不能同时伪装为已证实或可结算。新 G1-J pair 要双方均有至少一项假设；若中心路径选择的一方仍存在必要 `UNKNOWN`，thesis 只能是 `INCOMPLETE`。case adapter 保留 frozen assumptions，故事后不能在 HBT 回放时删除困难前提。

格力的四条必要前提已经单列在 `GREE_V1_RIVAL_HYPOTHESIS_DESIGN.md`：H-A 需要真实的跨渠道抵消和正常化现金转换；H-B 需要线上弱势确实外溢至全渠道、且毛利稳定确由组合/费用遮蔽。它们目前均为 `UNKNOWN`，并非任一机制已被反证。这一结果阻断旧报告把单期毛利或表观 OCF 升格为定价权/owner-cash 结论，也阻断把线上份额直接当 H-B 的证明。

### 根因、经济影响与验收

根因是 `MODEL + REASONING`，由 `WRITING` 的高确定性语言放大，不是少读几份格力报告。若不把必要前提冻结，研究者会把渠道位置、现金质量和利润池保留的未知藏在平滑的叙事里，材料性地误判竞争持续期、normal owner cash、永久损失以及后续（仅投资用途的）价值区间。

禁止把“关键假设”写成不可证伪的宏观判断、主观概率、估值假设、股价或行动理由；禁止用结果期观察回写为当期 VERIFIED。验收是：缺 assumptions、缺任一机制侧、VERIFIED 无 evidence、TESTABLE 未连本 pair 信号、或中心路径一侧仍 `UNKNOWN` 都不能冻结；合法对象必须原样进入 snapshot—Phase10 case。定向 thesis、CJO 输出与 adapter 回归覆盖这五类失败，格力在拥有合格行业 release、公司量价/费用和现金 bridge 前维持 `UNDISCRIMINATED`。

## 82. ITER-78 — 多重解释的单位是可结算 pair，不是把世界硬压成二元（2026-08-21）

### 文献、试验与结论

Hirt 与 Markman 的原始实验 [*Multiple explanation: A consider-an-alternative strategy for debiasing judgments*（JPSP，1995）](https://doi.org/10.1037/0022-3514.69.6.1069) 的可迁移发现是：要求解释一个可信的替代结果，而不只是“相反结果”，会促使更多备选解释进入判断；替代解释是否可信是作用条件。它不证明多列几个情景会提高投资收益，也不授权研究者凭空穷举机制。

用第三个“产品组合主导”终局对现有合同作冻结试验：它与原主路径同属一个互斥终局集，但有独立 mechanism chain、两条独有 FJ、第二个 `rival_hypothesis_pair`、双方关键假设和第二张迁移卡。五条 FJ 的总数仍在 3–5 范围；所有 pair signal 仍一一映射到同一 frozen FJ，合法工件可成为 `DECISION_READY`。因此不新建“多重解释评分器”或平行假设库：现有 pair/card 是可扩展的比较图，第二个 material alternative 只是第二个完整 pair。

### 格力边界、根因与验收

当前不应为格力机械添加 H-C。消费电器分类变化、产品组合与经营受限资金是重要的测量/现金边界，但没有一条在当前同口径下能解释 H-A/H-B 所面对的整组事实，并产生与两者不同、可结算的未来序列；它们应继续降低结论强度，而非假装成竞争机制。若未来获得的材料使一个第三机制同时解释共同事实、并会改变 normal owner cash 或竞争持续期，则必须作为同一终局空间的一条独立 chain，给出两个不同于既有信号的 FJ 与新 pair/card；否则保留 `UNKNOWN`。

根因是 `REASONING + MODEL`：只选一个温和反方会遗漏材料机制，强行罗列许多弱解释又会让 FJ 失去诊断性。两者都会错误影响竞争持续期、owner cash 和永久损失。禁止用报告篇数、同义改写、股价结果或“风险清单”充当第三解释；禁止让第三机制复用原 pair 的 FJ 后宣称独立验证。验收是第三机制必须共享当前事实、处于同一终局空间、拥有独有的 6–12 月/终局信号及完整关键假设/卡片；新增 regression 已验证两个 pair、五条 FJ 可以共同冻结，而不将二元对立误当作穷尽性。

## 83. ITER-79 — 已有八张案例卡是研究语法，不是已积累的八个公司经验（2026-08-21）

### 对账事实

直接复读 `config/insight_case_benchmark.json` 后确认，当前资产共有八个 archetype：`asset_catalyst`、`distressed_survival`、`franchise_customer_lockin`、`technology_transition`、`mature_cash_return`、`compounder_reinvestment`、`regulated_financial` 和 `operating_transition`。每张均含 case pattern、决定性问题、required moves 与 forbidden shortcuts；这正是格雷厄姆到巴菲特案例分析最有价值的可迁移部分——知道该问什么、什么推论不可跳过。

但该文件没有公司—时点、PIT source、`MEP:` episode、`CASEEV:` outcome 或独立 eligibility review；现有 historical pilot 里的候选公司也多是 `INELIGIBLE_NO_HISTORICAL_VINTAGE`。所以“案例卡已经做了”是对的，但它们还不是能够向格力 H-A/H-B 提供 primary support、反例或参考频率的案例库。此前把 archetype 说成“公司经验”会夸大当前学习存量。

### 经济边界与下一步

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`：缺的是按当时可得信息冻结、随后能以经营结果结算的 company×period episode，而不是卡片数或报告文风。若把 WD-40、Intel 等模式名、书中终局或格力报告的相似段落直接当作格力证据，会材料性地高估竞争持续期、现金质量和永久损失判断。

修复不新建第二套案例库：继续使用现有 append-only `base_rate_case` / `MEP` / `CASEEV` 登记簿。每个首批 episode 必须有预结果 cutoff、共同机制问题、状态向量、主/反机制、FJ、随后 outcome 与 independent eligibility；在此之前，八张 archetype 卡只可通过 `QUESTION_ONLY` transfer card 生成问题与区分信号。验收是任一宣称 `VERIFIED_EPISODE` 的 near-miss 都能解析回这一整条登记簿链；否则保留 `UNKNOWN_NO_QUALIFIED_EPISODE`。格力当前仍是后者。

## 84. ITER-80 — 回测功能已经有用，但现存 600340 工件不能充当“公司经验”（2026-08-21）

### 实物审阅

复读 `HBTCASE:600340:20200427` 与其 2021-04-27 settlement 后，结论需要精确区分。它的价值是工程验证：PIT cutoff、受限来源、冻结、独立复审和无价格的 `UNKNOWN` claim 可以被回放，因此证明“冻结后结算”这条管道不必依赖股价。它不是一份可学习的历史公司判断：报告身份为 `PIT_ENGINEERING / FROZEN_WITH_QUALITY_FAILURE`，credibility 为 `EXPLORATORY / model_memory_control=UNCONTROLLED`；四条 claim 的 prediction 都为 `null`，独立复审只保留 `UNKNOWN`；用于结算的后续公告还标为 `METADATA_ONLY_BODY_NOT_READ`。

因此回测功能**用得上**，但用途是把未来真实格力或同行的 FJ 结算为机制学习，而不是把现有工程 fixture 计入案例经验、近失效或频率。把它写成第一个成功回测案例，会等同于以未读结果、无预测的诊断草稿替代公司判断。

### 根因、影响与可执行修复

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + MODEL`：缺完整可读的结果来源、生产级公司机制/FJ 和可信的独立资格，而不是缺少一个“回测分数”。经济影响是若误入案例库，系统会错误相信自己已验证过现金可得性、应收回收、再融资或担保恢复，扭曲格力的永久损失和 owner-cash 判断。

禁止把 `UNKNOWN` disposition、元数据公告、后验债务事件、市场价格或工程 reviewer 结论补成 episode outcome；禁止由此给八张 archetype 卡升级为经验样本。可执行修复是选择一条与格力关键机制可比、但结果已公开的真实公司×时点，先物化 cutoff 前公司/行业资料，写主/反机制与 3–5 个无价格 FJ，读取合格 6–12 月和终局官方结果，再经独立 eligibility 将其写入同一个 `base_rate_case`。验收必须同时具备 `MEP:`、`CASEEV:`、实际 prediction、已读官方 outcome、PIT/来源边界和独立 review；届时 HBT 才能为公司经验加一条有效 observation，而非一个回测演示。

## 85. ITER-81 — 格力钛可以成为首个“自己公司的历史 episode”，但目前还不是（2026-08-21）

### 候选事实与可学习问题

现有官方源包恰好给出一个比工程 fixture 更接近真实公司经验的候选：2021-10-30 公告称格力以 182,827.51 万元竞得银隆新能源 30.47% 股权，并合计控制 47.93% 表决权；2023 年年报记录 2023 年 12 月再受让 24.54%、作价 101,532.84 万元、直接持股升至 55.01%；2025 年年报记录格力钛工程当期减值 99,597.01 万元、累计减值 114,216.53 万元，理由为部分工程不再建设且不再有预期经济利益流入。

这允许提出窄的资本配置竞争机制：H-A 是控制权取得后保持有界整合并形成可观察经营兑现；H-B 是追加资本承诺或工程减值在兑现前显性化。2023 的权益增持和 2025 的工程减值是 H-B 的材料观察，却不足以称整个收购、所有后续资金、经济回报或退出价值已经失败；这种克制正是 episode 应训练的判断，而不是再做一个“格力钛很差”的故事。

### 为什么本轮不把它硬写进案例库

根因仍是 `ACQUISITION_MODULE + DATA_COVERAGE + REASONING`：虽然有起点与后续观察，却还没有一个只含 2021-10-30 前信息的独立 PIT package、预结果 FJ、完整终局 contract 或 independent eligibility。2022H1（收购后约十个月）其实已经给出早期公开读数：格力钛收入 11.67 亿元、净亏损 6.58 亿元、经营现金流 -1.50 亿元，并披露总担保 65.37 亿元。它说明“没有早期资料”是错误表述，却不能直接做 pair signal：2021 收购公告的 1–7 月数据与 2022H1 不同期间，而“增强盈利能力”只是方向性表述，不是可结算的整合承诺或预注册阈值；初始亏损与存量担保亦可被 H-A/H-B 同时解释。因此它只能结算为 `MIXED / NOT_DIAGNOSTIC` 候选观察，不能被写作 H-B 已获证明。公告未出现某笔追加投入也不能证明“没有追加”；用它补早期信号会把无证据当作 H-A 支持。将今天已知的 2023/2025 结果倒写成 2021 预测，同样是后见之明。

所以状态是 `CANDIDATE / NOT_A_CASE / NOT_A_BASE_RATE`。下一步是对 2021 cutoff 建独立 source selection，先写这两条机制和各自的早期/终局无价格 FJ，再逐页物化 2022–25 outcome；若 2022H1 观察无法在只读 2021 资料下形成不同预测，就必须诚实把它结算为 `MIXED / NOT_DIAGNOSTIC`，而非因已看到 2025 减值绕过 6–12 月学习。验收后它可成为格力自身资本配置的一条历史 episode，但仍只是一家公司一个时期，不能作为空调渠道问题的基准率或近失效案例。

## 86. ITER-82 — 早期披露不等于早期可结算判断：格力钛准入试验（2026-08-21）

### 只读 2021 材料与随后 outcome 的分界

对候选进行第二次准入测试时，发现“没有早期 outcome”这个理由过宽。2021 年的收购公告在控制权取得前已经披露 1–7 月收入 10.58 亿元、净亏损 7.63 亿元和经营现金流 13.85 亿元，并称整合将提升产能利用率、竞争力和盈利能力，同时明确协同需要时间、存在整合风险。它还没有定量承诺。结果期的 2021 年报（2022-04 披露）则记录购买日至年末收入 6.94 亿元、净亏损 4.17 亿元，并称业务关系已理顺、已取得初步成果；2022 年半年度报告记录格力钛收入 11.67 亿元、净亏损 6.58 亿元、经营现金流 -1.50 亿元和总担保 65.37 亿元。

这些数字可以读作结果，不能被倒灌成 2021 年的 FJ。收购前 1–7 月、购买日至年末和 2022H1 是三个不同长度/边界的期间；即使把收入或亏损按月年化，也会伪造可比性。更根本的是，“提升盈利能力”并没有规定在何时、相对哪一基线、以什么指标达到何种程度，H-A 的“有界整合”与 H-B 的“兑现前继续承诺／损失显性化”均不必对首个半年报给出唯一的收入、亏损或经营现金预测。2021 年报的“初步成果”也是结果期管理层文字，不能被当成独立的 H-A 证据。

### 结论、根因与执行规则

本轮结论不是把候选降为没有价值，而是把它准确定位为 `CANDIDATE_OUTCOME_RICH / FJ_NOT_YET_DESIGNABLE / NOT_A_CASE`。根因主要是 `REASONING`：没有两条从 cutoff 自然推出不同谓词的预测，后见的公开数字再多也不能生成判别力；`ACQUISITION_MODULE` 的剩余任务是建立只含 cutoff 前材料的 source selection，并把随后文件隔离为 outcome。它**不是**以“报告数量不足”为由要求再采 20 份格力材料。

经济影响是若把任何事后财报或管理层自评当作早期信号，系统会把叙事确认偏误训练成公司经验，错误裁决资本配置、normal owner cash 与永久损失。禁止：用公告未披露的追加投入证明 H-A；把 2023 加码或 2025 减值写回 2021 预测；以不同期间的收入/亏损/OCF 构造未经预注册的阈值；或把管理层的“初步成果”当作独立外部验证。可执行补救是只用 2021 cutoff 文件先写 `metric / comparator / prediction / observation window / allowed source`；若其无法让 H-A/H-B 分叉，就在该时点拒绝 episode，而不是制造 FJ。接纳条件是存在至少一条有不同主/反预测的 6–12 月经营或资本动作 signal、一个终局 signal、独立 PIT eligibility 与已读官方 outcome；否则它永远不进入 `MEP:`、`CASEEV:` 或基准率分母。

## 87. ITER-83 — “刻意练习”不另造评分器；缺的是把结算变成下一次可执行的研究改变（2026-08-21）

### 文献筛选与现有能力测试

本轮回到 [Ericsson、Krampe 与 Tesch-Römer（1993）《The role of deliberate practice in the acquisition of expert performance》](https://doi.org/10.1037/0033-295X.100.3.363) 及 [Kahneman 与 Klein（2009）《Conditions for intuitive expertise》](https://doi.org/10.1037/a0016755) 的原始出版记录。前者讨论长期、有针对性的改进努力，后者把可靠直觉的边界放在环境的规律性与可获得的学习反馈；两者都不支持把阅读量、报告评分或最后股价当作能力本身。

与现有实现逐项比对后，训练对象已经不是缺失的模块：冻结 FJ/pair 把任务拆为可观察的公司问题，`historical_backtest` 可以先结算 6–12 月机制信号，`judgment_feedback` 会回显冻结预测、简单基线、机制链、四层 driver 与后续经营 observation，并将价格回报隔离。这已经是比“读二十份报告再总结”更接近刻意练习的结构。它不应再加一个专家分、复盘分或概率自动更新器。

### 唯一新增动作与边界

真正尚未产品化的是反馈后的**处置**：当前 feedback 卡正确地把根因留给人工 review，但若 review 不明确改变下一次的取证/FJ 设计，学习会停在“看过结果”。路线因此新增 append-only `learning_note` 规则：每条已审反馈只选择 `RETAIN`、`RETIRE` 或 `INSUFFICIENT_EVIDENCE`，写清适用状态、口径和下次改动；它引用 frozen case/settlement，绝不回写原报告、阈值、机制、基线、估值或行动，也不自动把一次命中升级为经验。

根因是 `MODEL + WRITING`，不是 `DATA_COVERAGE`：现有反馈的信息足够，但还没有一条受约束的“这会如何改变下一次问题”的输出。经济影响是没有该处置，研究者可能每年重复用同一个无诊断性信号解释格力渠道、现金或资本事件，从而把熟悉感误当判断力。验收条件不是增加任何分数：以一条真实、无价格 PIT settlement 生成 feedback 后，追加一份能回指其 frozen inputs 的 learning note；note 若试图改写旧判断、借价格裁决经营、或把单个 episode 变为基准率，应被拒绝。实际 writer/schema 的实现必须等真实 CJO case 出现后与该 case 一起验收，当前不以 fixture 伪称闭环完成。

## 88. ITER-84 — 本地没有“20 多份格力外部报告”可纳入；不要把官方 41 源包误数为它们（2026-08-21）

### 现场核对

按文件名核对当前工作树及工作区中、排除 Turtle 各 worktree 后的本地材料：可用于格力 V1 的是 889 条 CNINFO inventory 中预注册的 41 项官方正文（15 项年报/中报、其余为现金、回购、资本配置和分配事件公告）。工作区外层只发现一份格力估值模型表格，没有可读取的 20 多份券商/第三方格力报告。旧 `phase08` 的多份“分析报告”只是同一内部报告的版本或发布别名，也不能计作外部材料或独立样本。

这不否定用户的设想，而是界定当前可执行状态：这些报告尚未作为本工作树可读取、可版本化的输入出现，因此不能假装已经由它们形成了行业深度或反方。41 项官方文件的纵向价值是构建同一公司的状态转换，不是 41 次独立公司经验；它们更不是外部研究投票。

### 根因、用途与接纳

根因是 `DATA_COVERAGE`，不是采集器故障；经济影响仅限于机制发现与反方的广度，不能因此降低官方事实或 CJO 的标准。禁止把“20 多份”当共识票数、独立样本、事实/估值输入或 H-A/H-B 的概率。若报告加入，每份只先登记发布者、发布日期/当时可得性、其机制箭头、与既有证据的具体分歧和一项可由官方或授权行业数据验证的任务；之后身份为 `MECHANISM_DISCOVERY`，而非公司 `VERIFIED` fact。接纳条件是原文件被放入受控 source package、同 cutoff 可得性可审、每份都映射一个可区分 FJ 或明确被拒绝；否则继续以当前官方 41 源包为事实边界，不用篇数营造深度。

## 89. ITER-85 — learning note 已成为受约束的 append-only 学习动作，而非复盘散文（2026-08-21）

### 实现与可检验边界

本轮以 [Ericsson、Krampe 与 Tesch-Römer（1993）](https://doi.org/10.1037/0033-295X.100.3.363) 和 [Kahneman 与 Klein（2009）](https://doi.org/10.1037/a0016755) 的出版社原始记录复核了 ITER-83 的方向：前者讨论长期、有针对性的改进努力；后者的结论是判断质量取决于环境可预测性与学习机会，而不是主观熟悉感。两者都支持“将结果转成下一次可执行的任务”，却不支持从一个结果自动重估能力、概率或估值。

因此新增 `scripts/judgment_learning.py`。它读取既有 `judgment-feedback-card.v2` 的 case/freeze/settlement/claim 身份，生成独立的 `judgment-learning-note.v1`：`RETAIN`、`RETIRE` 或 `INSUFFICIENT_EVIDENCE`，适用状态、计量口径、复盘依据及下一次研究改动。`RETAIN/RETIRE` 仅在关联 claim 已为 `CALCULATED` 时允许；尚未到期或部分结算只能标 `INSUFFICIENT_EVIDENCE`。note 不包含新的 prediction、baseline、actual observation、mechanism chain、传导、阈值、概率、价格、估值、回报、交易或决策字段；若试图带入这些字段，validator 拒绝。持久化按 note ID append-only，不能用同一 ID 覆盖旧 note。

### 结论、失败模式与接纳

这关闭的是 `MODEL + REASONING` 缺口：此前 feedback 虽可正确回显冻结材料，却没有一个机器可审阅的出口让人明确“下次保留什么、淘汰什么、补什么”。经济影响是没有这个出口，同一种非诊断性渠道、现金或资本信号会被反复使用，阅读量和熟悉感容易被误当经验。它不是 `DATA_COVERAGE` 的替代，不能让格力 H-A/H-B 在缺行业 release 时获得裁决，也不能把单一 episode 变为校准样本。

定向测试覆盖：合格 note 与 frozen feedback 的精确链接；未结算 signal 不得 `RETAIN/RETIRE`；试图塞回预测字段必须失败；同一 note ID 不得覆盖。验收仍需在首个**真实** CJO PIT case 完成早期 settlement 后，人工写入一条 note 并检查其下一次数据选择/FJ设计确有改变。在此之前，这只是通路可用，不声称格力已经学习完成。

## 90. ITER-86 — 行业出货、零售与库存须作为一条有边界的存量—流量链，而非三个“需求指标”（2026-08-21）

### 原始研究与格力映射

Lee、Padmanabhan 与 Whang 在 MIT Sloan Management Review 的[《The Bullwhip Effect in Supply Chains》](https://sloanreview.mit.edu/article/the-bullwhip-effect-in-supply-chains/)用零售销售、经销订单与上游订单逐级放大的例子说明：渠道订单的波动不等于终端消费波动，失真会带来库存、产能、服务和成本的错误配置。它不证明中国空调或格力一定存在该效应；它只要求研究者先问清每个数字位于哪个交易点、对应哪个库存边界和时滞。

格力正有一个高风险的现实触发器：协会刊物中的 AVC 材料同时给出 2025 冷年内销 shipment 1.02 亿台、全渠道 retail sell-out 8,059 万台，以及“冷年中期总库存超过 5,000 万台”。这三项的产品、地域、渠道、品牌分母、期间、流量交易点和库存归属没有被同一 release 定义为一个可对账系统。直接相减得到“约 2,141 万台补库存”既忽略期间/口径，也可能混入库存变化、进口出口、产品范围或统计覆盖，属于伪精确。

### 新的最小规则与验收

因此将行业链的最小单位改为 `stock-flow boundary`：只有同一 provider release 为 sell-out、shipment/sell-in 与 inventory 同时保存上述共同边界及 definition locator 时，才允许核对 `shipment − sell-out` 是否与库存变动相容；缺一项就标 `NOT_RECONCILABLE`。背离只能提出“订单、补货、促销或库存可能扭曲需求信号”的机制问题，不能直接裁决格力需求、份额、返利、现金、H-A/H-B 或投资结论。

根因是 `DATA_COVERAGE + REASONING`：当前数据确实不覆盖可对账的库存系统，而旧报告最容易把可见的行业量放大为公司判断。经济影响是错把 shipment 当 sell-out、或从差额虚构库存，会错误延长/缩短竞争持续期，并污染 normal owner cash 的渠道压力推断。可执行补救是在 AVC/产业在线 release 请求中补入库存归属与共同交易点定义；若不能取得，保留 `CONTEXT_ONLY / NOT_RECONCILABLE`。验收是来源包逐项含共同边界和定义，且一个历史 PIT case 的主/反机制对**序列先后**给出不同预期；不能只凭同一年度三个总量通过。

## 91. ITER-87 — 不能只复盘错误：命中信号同样要检验是否优于基线、是否真有诊断性（2026-08-21）

### 原始研究与产品修正

Ellis 与 Davidi 的 [《After-Event Reviews: Drawing Lessons From Successful and Failed Experience》](https://doi.org/10.1037/0021-9010.90.5.857) 报告的准现场实验比较了只复盘失败与同时复盘成功、失败；后者的连续任务表现改善更大，且成功事件在未复盘时的心智模型更贫乏。它不是投资准确率的直接证据，也不支持把一次命中升级为专业能力；它只否定“正确所以无需分析”的学习流程。

R3.5 原先将任务信息反馈重点写为错判/未决，容易让命中的格力 FJ 自动留存，即使它只是 carry-forward 基线、两个竞争机制都会出现的共同信号，或恰好碰到的结果。现改为：每一个已结算 judgment 都生成 feedback；`RETAIN` 也必须人工说明相对冻结简单基线的增量和相对 H-A/H-B 的诊断价值。`judgment_learning.py` 已可针对任意 `CALCULATED` claim 产生 note，本轮新增命中且优于基线的 `RETAIN` 测试；未结算仍只能 `INSUFFICIENT_EVIDENCE`。

根因是 `REASONING + WRITING`，不是新增数据不足。经济影响是若只记录失败，系统会把偶然命中的线上份额、毛利或 OCF 信号保留为“经验”，日后重复误导渠道持续期与现金判断。禁止将 `MET`、`SUPPORTS_PRIMARY` 或后来股价上涨自动等同于 `RETAIN`；也禁止因命中而回写旧机制或概率。验收是每条计算完成的 FJ 都有可读 feedback，`RETAIN` 明确基线增量和区分性，`RETIRE/INSUFFICIENT_EVIDENCE` 也说明下一次改变；实际格力仍无可结算 FJ，故不声称任何格力信号已被保留。

## 92. ITER-88 — 案例卡确有八张，但只有四张是具名书中案例；其余是研究原型（2026-08-21）

### 资产复读与来源身份

复读当前 `config/insight_case_benchmark.json`，以及另一工作树中仅作阅读导航、尚未成为本工作树 canonical source 的《价值投资：从格雷厄姆到巴菲特（第2版）》整理笔记后，结论应更精确。现有八张卡中，`asset_catalyst / distressed_survival / franchise_customer_lockin / technology_transition` 分别以 Hudson General、Magna International、WD-40、Intel 为具名书中案例路由；`mature_cash_return / compounder_reinvestment / regulated_financial / operating_transition` 是 Turtle 为研究路由构造的综合模式，不是另四个具名公司案例。

因此给每张卡补入 `case_provenance`，只允许 `NAMED_BOOK_CASE` 或 `SYNTHESIS_PATTERN`，并在 `insight_research` 的输出中一同传递。两类的 scope 都固定为 `ROUTING_ONLY_NOT_COMPANY_EPISODE`：它们提出问题、必做推理和禁止捷径，绝不成为格力证据、近失效案例、`MEP:` / `CASEEV:`、概率或历史样本。定向测试验证 Intel 路由明确标记为具名书中案例，而成熟现金路由明确标记为综合模式。

根因是 `WRITING + REASONING`：此前“8 张书籍方法案例卡”的简称容易被理解为八个已经读取、可回放的历史公司案例。经济影响是若将综合模式冒充案例，会虚增公司经验和类比强度，尤其会诱使报告把成熟现金、受监管资产或经营转型的通用问题误写成格力的历史反证。禁止从这四张具名卡的名称、或另一个 worktree 的笔记，直接转移事实、估值倍数、终局回报或机制支持。可执行补救是：若未来需要书中案例的更深结构迁移，先把用户授权/可读的原书章节以版权合规的定位与摘要物化为受控 `MECHANISM_DISCOVERY` source；当前只保留 provenance 标签。验收是所有 router brief 都显示卡片来源身份，且没有任何卡能绕过正式 episode eligibility 进入 HBT、base-rate 或中心路径支持。

## 93. ITER-89 — 官方行业环境必须先有原始当期来源，再谈宏观传导（2026-08-21）

### 采集试验与结果

本轮没有再增加格力报告篇数，而是把已预注册的官方背景入口变成可复用的原始来源包。新增 `industry_context_acquisition.py`：目录先验证公司、cutoff、官方 host、发布时间/数据时点、原始载体路径和 `CONTEXT_ONLY` 权限；再归档原始 HTML/PDF。它拒绝同日无发布时间的 PIT 可得性、非官方 host/跳转和路径逃逸；已存在的原始文件不会覆盖。原始包成功的状态刻意仅为 `RAW_COMPLETE_PENDING_OBSERVATION_REVIEW`，不能被误称为公司事实。

格力 V1 的 6 个官方网页和 1 个 2024 年政策 PDF 附件均已物化。后者修正了一个真实来源错误：通知网页只能证明文件发布，空调属于八类、二级及以上能效 15% 补贴等具体规则在其官方 PDF 附件第 6 页；不能把网页标题替代附件内容。随后将 8 条预注册观察写入独立 observation ledger，逐项指向 HTML 表/段或 PDF 页，并验证为 `REVIEWABLE_CONTEXT_ONLY`。它们覆盖 2020/2024/2025 房间空调生产、2024H2/2025 以旧换新、2025 广义家电/线上零售、耐用消费品 PPI 与房地产背景。

### 权限与下一步

根因是 `ACQUISITION_MODULE + DATA_COVERAGE`：此前宏观/行业数值虽已定位，却没有原始当期响应和可重读 locator；若直接写入报告，容易用当前网页、搜索摘要或政策标题替代当时证据。经济影响是这种偷换会将宏观生产、政策或房地产状态伪装成格力竞争事实，材料性地误判渠道持续期、价格实现、owner cash 与永久损失。

禁止把这 8 条观察用于格力销量、品牌/渠道份额、ASP、返利、经销库存、工程订单/回款、owner cash、H-A/H-B verdict、估值、回报或动作；生产/零售/价格/地产并非同一交易点，也不能组合成品牌份额。它们只能作为 `COMPETITION_DEMAND` 的 qualitative guardrail，要求进一步取证而不是提供答案。接纳条件已实际满足的是：原始来源、PIT 日期、指标定义、页/段定位和禁止推断均可回读；尚未满足且仍阻断竞争裁决的是同口径的品牌全渠道份额、量价/返利、渠道库存和调整后现金。下一步应请求合格的历史 AVC/产业在线 release，并仅在其定义保存后作为 `LICENSED_INDUSTRY_DATA` 结算竞争/单位经济 FJ；不能再用宏观材料增加“样本数”。

## 94. ITER-90 — 截止日后还没有新的经营 outcome；回购事件也不能替代竞争或现金结算（2026-08-21）

### 只读结果

对巨潮 `000651 / gssz0000651` 在 2026-08-03 至 2026-08-21 18:00 的完整日期范围做了只读枚举。5 条原始公告中，3 条因早于 cutoff 日获准读取：8 月 4 日回购进展、8 月 19 日首次回购暨进展、8 月 20 日员工持股计划非交易过户；两条 8 月 21 日权益分派/回购价上限调整因只提供日期、没有发布时间，按同日 PIT 规则被拒绝。范围内没有 2026H1、业绩预告、经营快报或其他可比较的公司经营披露。

这既不表示格力经营没有变化，也不代表当前 8 月的回购支持 H-A 或 H-B。回购是资本配置行为，只有在 pre-freeze 已有相应 event/FJ、资金来源、规模、比较对象、观察窗和经营兑现 contract 时，才可在其自身轨上结算；当前格力 V1 尚未冻结这样的 CJO claim。它绝不能替代全渠道相对位置、量价/费用或调整后现金的早期观察。

### 根因、边界与接纳

根因是 `DATA_COVERAGE + REASONING`，并非采集器失灵：截至该时点，公开经营结果尚未发布，且回购公告的经济对象与未冻结的竞争/现金机制不同。若把回购、员工持股或同日分派当作“后续验证”，会材料性地把管理层资本动作误当竞争持续期或 owner-cash 的证据，从而错误选择中心路径。

禁止将公告缺席解释为无恶化/无追加投入；禁止让 8 月 21 日无时间戳的文件越过日内 cutoff；禁止因随后回购倒写为 8 月 3 日的判断正确。下一个有效结算点必须是：在正式 CJO 冻结后，出现满足已注册 FJ 的 2026H1/年度公司披露或同定义持牌行业 release；此前状态仍为 `UNRESOLVED / UNDISCRIMINATED`，而不是“等待中的正确”。

## 95. ITER-91 — 行业架构图只有导向独立 FJ 时才保留（2026-08-21）

### 方法落实

复读 Jacobides、Knudsen 与 Augier 的 [《Benefiting from Innovation: Value Creation, Value Appropriation and the Role of Industry Architectures》](https://doi.org/10.1016/j.respol.2006.09.005) 后，H7 的实用含义不是再加一张供应商—公司—消费者图，而是让“谁控制接口、谁拥有互补资产、价值实际在哪里被攫取”产生主/反机制不同的未来观察。此前路线图已有这项要求，但 transfer card 没有相应字段；研究者仍可把行业架构写成不影响 FJ 的报告段落。

因此 `analogy_transfer_card.industry_architecture` 现成为可选的窄实验契约。只要填写，五项结构要素——分工、接口控制、互补资产、要素流动性、价值攫取节点——都必须是带外部来源类别和 evidence ID 的 `VERIFIED`，或带原因与保守处理的 `UNKNOWN`。它还必须指定 card 自己已链接的 `RHPSIG`、该信号所分辨的机制箭头，以及一项最小外部查询；未知结构项时 card 只能 `QUESTION_ONLY`。公司自述、垂直整合事实、线下网点或线上排名都不是合格的接口控制/价值攫取替代品。

定向测试发现并修正了一个真正的引用漂移：第三种机制的 card 从既有卡复制后，若其行业架构仍链接旧 pair 的 signal，validator 会拒绝；只有把它改为新 pair 的早期 FJ 才重新通过。`thesis_test` 与 Phase10 adapter 的定向回归共 86 项通过，证明字段会随冻结 ledger 进入 case，而不是只留在 writer 提示中。

### 格力边界与接纳

根因是 `MODEL + REASONING`：原先缺少可冻结对象会让行业深度退化为叙述，进而可能把渠道排名或公司话术错误升级为护城河/利润池判断。经济影响是错误识别接口控制，会材料性地误判格力渠道压力可否传导为 ASP、费用、owner cash 与永久损失。它不是“再收二十份报告”就会自动解决的数据量问题。

格力当前五项均为 `UNKNOWN`，原因是尚无同口径品牌×渠道×量价、经销激励、服务接口和利润池资料；因此没有创建虚假的格力 transfer card，也没有改变 H-A/H-B 的 `UNDISCRIMINATED` 状态。禁止以线上第一、网点、垂直整合、单期毛利或表观 OCF 填入该卡。实际接纳条件是：每个已验证结构项都有可复读的外部来源与 PIT evidence，最小查询能生成现有 FJ 之外、同时削弱一方机制的观测，并在真实 CJO source package 中通过冻结；否则撤销 H7 对该报告的使用，保留 `UNKNOWN`。

## 96. ITER-92 — 把存量—流量边界变成来源合同，而不是报告中的提醒（2026-08-21）

### 实现与测试

H8 的 Lee、Padmanabhan 与 Whang 原始研究提醒我们，订单、出货与终端销售的放大关系取决于库存和交易点；它不授权从三个行业总量自动推出补库。此前 Turtle 只在格力说明中写了这个边界，持牌行业数据 source contract 仍无法机器地区分“同一 release 下可核对的三条轨”与“看似相关的三张图”。

因此独立行业数据契约增加 `INVENTORY_STOCK` 语义及可选 `stock_flow_boundary`。`validate_stock_flow_reconciliation(...)` 仅在一份同 provider/dataset/release/version 的三项 export 分别覆盖 `RETAIL_SELL_OUT`、有 provider 定义的 `SHIPMENT` 和 `INVENTORY_STOCK`，且产品、地域、渠道、品牌、分母、期间、库存归属和 definition locator 完全一致时返回 `RECONCILABLE`。它不做算术、不创建 FJ、不推断公司库存或现金；任一边界缺失、版本不同或 sell-in 未解析时只返回 `NOT_RECONCILABLE`。定向回归 51 项通过，其中明确覆盖合格三轨、sell-in 未定义和期间边界不一致三种情形。

### 格力边界与接纳

根因是 `ACQUISITION_MODULE + REASONING`：没有这层合同，未来很容易把 AVC retail、产业在线 shipment 和协会库存描述当作同一系统。经济影响是会把渠道补库/去库错当品牌需求或价格权，继而污染竞争持续期、adjusted owner cash 与永久损失判断。禁止用当前 1.02 亿台 shipment、8,059 万台 retail 与“库存超过 5,000 万台”相减，也禁止将跨 provider 或不同冷年/自然期图表带入该 validator。

真实格力仍没有合格的三轨 release，故未运行任何数值核对，状态仍为 `NOT_RECONCILABLE / CONTEXT_ONLY`。接纳条件是已授权的原始历史 export 在同一 release 中保存三个 provider definition 与共同 boundary，通过 validator 后，再由一个预注册 pair 对库存—flow 的先后顺序给出不同经营信号；即便通过，也只生成机制取证，不能直接裁决格力收入、现金、资本配置、估值或投资动作。

## 97. ITER-93 — 类比卡必须写迁移规则，而不只写相似与反例（2026-08-21）

### 原始研究与最小修复

Richland 与 McDonough 的 [《Learning by analogy: Discriminating between potential analogs》](https://doi.org/10.1016/j.cedpsych.2009.09.001) 在两个数学情境的实验中发现，能显式提示比较关系的教学类比，比只给出相同案例和解法，更能帮助后续区分相关类比与误导性的表面相似。这不是投资研究的直接因果证据，也不说明案例越多越好；它恰好解释了为什么“格雷厄姆—巴菲特书中有一个类似公司”常会停留在公司名联想。

现有 transfer card 已有状态向量、驱动链、mismatch、near-miss 和 FJ，但缺一个强制输出说明这些条件何时足以迁移机制、何时必须停止。因此新增 `application_rule.when_to_apply / when_not_to_apply`。它不能写价格、概率、估值或终局回报，不能替代 pair signal；它只要求研究者把结构相似与结构断裂并排写出。删去该规则的卡会在 `thesis_test` 保持 `INCOMPLETE`；包含该规则的 pair/card/adapter 定向回归 87 项通过。

### 格力边界与接纳

根因是 `REASONING + WRITING`：没有迁移边界，案例卡会把现有八张研究路由伪装为格力事实或支持力度。经济影响是错误把 WD-40、Intel 或综合模式的表面特征迁移到格力渠道、现金或资本配置，可能改变竞争持续期与永久损失判断。禁止将任何案例的估值倍数、收益率、最终股价或“成功/失败”写进 rule，禁止因对象同属家电或品牌而自动适用。

格力当前卡仍仅是 `ROUTING_ONLY_NOT_COMPANY_EPISODE`，不能生成真实 `application_rule` 的支持性结论；在实际 H-A/H-B pair 出现前，规则只能用来提出“需有同口径渠道、客户替代与现金传导”的取证条件。接纳条件是未来 card 能在真实 PIT episode 中把预先写好的适用/不适用条件与 pair FJ 结算对应起来；否则继续 `QUESTION_ONLY`，不增加格力结论置信度。

## 98. ITER-94 — 过程追踪必须冻结逐箭头证据，而不是保留一段机制叙述（2026-08-21）

### 原始方法与对抗性试验

Collier 将 process tracing 定义为在因果时间序列中系统检查有诊断力的证据；它要求研究者区分“这一观察是否检验某条传导箭头”与“这一观察最终看起来是否支持故事”。[Collier (2011)](https://doi.org/10.1017/S1049096511001429) 既有 Turtle pair 已有主/反机制、必要前提和有序 FJ，但 `mechanism_chain.mechanism` 仍是一段文本：一个后续信号可以被泛称为“支持这条链”，而不能识别它究竟检验了渠道、单位经济性还是现金转换。

因此在新 G1-J `rival_hypothesis_pair` 中增加 `causal_trace`：PRIMARY/RIVAL 各至少两条 `from_state → to_state` 箭头；每条绑定本方 mechanism chain、诊断理由以及 `VERIFIED` evidence、`TESTABLE` pair signal 或带保守处理的 `UNKNOWN`。双方各必须有一条连到 6–12 月 `EARLY_MECHANISM` signal；中心路径一方留有 `UNKNOWN` 箭头即不能冻结。这不新增概率、评分或估值层，也不替代 `critical_assumptions`：前者是传导步骤，后者是必要前提。

对抗性 fixture 的第三种“产品组合”解释最初复制了已有 pair；它错误保留了原 `RHPSIG` 与 rival mechanism chain，按旧规则仍可作为完整第三 pair。新验证器将此识别为 `mechanism_chain_side_mismatch` 和 `unknown_or_cross_pair_discriminator`；为第三机制重写四条箭头并改接其自身 early/terminal signals 后，目标 thesis 测试 64 项通过。

### 格力边界与接纳

根因是 `MODEL + REASONING`：没有逐箭头身份，行业叙述可将一个终局收入、毛利或 OCF 结果回填为所有中间机制均成立。经济影响是把线上份额、毛利暂稳或表观 OCF 误判为渠道接口、价格实现和现金转换都已获证，从而材料性地错误选择 H-A/H-B、owner cash 与永久损失路径。当前缺的事实是同口径品牌×渠道/价格带 sell-out、ASP/返利/费用、库存/回款以及剔除经营受限资金的现金 bridge。

禁止把管理层回忆、年报事后文字、单期毛利、线上第一或后来利润/现金填进旧 PIT arrow；也禁止为了通过字段而捏造格力 `causal_trace`。接纳条件是获得合格持牌 release 与公司 bridge 后，H-A/H-B 各形成至少两条有来源的箭头、各自 early signal、共同事实和同口径双谓词，并在 CJO source package 中冻结。到那之前格力仍为 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`，而不是“已支持但尚未写完”。

## 99. ITER-95 — 回测能训练冻结后的公司判断，不能把已知格力历史倒造为预测（2026-08-21）

### 可用性核对

现有 `historical_backtest.v2` 对公司判断的边界是合适的：它只在 source 先于 `simulation_cutoff`、claim 的 observation window 在 cutoff 后、且后续 source 处于冻结窗口内时结算经营 FJ；CJO 保持价格 `UNKNOWN` 和无投资动作。它也已把模型记忆分为 `CONTROLLED / MITIGATED / UNCONTROLLED`：后者只能是 `EXPLORATORY / ENGINEERING_DIAGNOSTIC_ONLY`，不得进入 calibration candidate 或经验频率。

这意味着已收集的 2021 格力钛收购、2023 增持和 2025 工程减值很适合建立“启动承诺 → 加码 → 后续兑现”的官方事实时间线，却**不能**在现在被倒写成一份 2021 年真实形成的预测并计入训练成绩：研究者和模型已经看过后续材料。即使把 `simulation_cutoff` 设为 2021、只读当时 source，这仍只是机制演练，不能消除已知结果或模型记忆。

### 根因、边界与下一步

根因是 `MODEL + REASONING`，不是回测功能不足：把 hindsight reconstruction 当作预测反馈，会让格力钛的后续增持、减值或任何已知经营结果伪造“公司判断准确率”。经济影响是错误提高资本配置直觉、normal owner cash 与永久损失判断的确信度。禁止伪造早期 `frozen_at`、把后来公告藏在 source package 外、或用一次减值定义资本配置终局。

可执行路径只有两条：一是对当前格力在未读后续经营结果前，先冻结 CJO H-A/H-B 与资本配置 FJ，然后在 6–12 月和 3–5 年窗口用官方/授权 source 结算；二是用户提供当时原始、带发布日期和明确预测的历史格力研究报告，按报告当时已写下的 FJ 结算，并保持 `UNCONTROLLED` 除非有独立模型记忆控制证据。接纳标准不是获得一个漂亮历史命中率，而是每条进入学习集合的 claim 都能证明“预测先冻结、结果后可读、来源与窗口同定义”；否则只保留机制发现和事实编年价值。

## 100. ITER-96 — 公司判断成稿必须露出关键机制箭头及其证据边界（2026-08-21）

### 发现与最小修复

ITER-94 已将 Collier 的过程追踪落实为可冻结的 `causal_trace`，但 CJO 摘要此前只输出主/竞争机制段落和 FJ 列表。读者看不到“当前结论具体经过哪条传导”“这条传导已由当期证据支持、正在等哪项信号，还是仍须保守处理”；机制纪律因而停留在后台。

现将每个冻结 pair 的 PRIMARY/RIVAL 关键前提与关键箭头写入 CJO 的竞争机制摘要：前提写明它为何必要，箭头写为 `起点 → 结果` 与诊断理由，两者都使用自然语言三类边界。`VERIFIED` 写为“当期证据已核实”，`TESTABLE` 写出相连 FJ 的实际判断，`UNKNOWN` 写出既有保守处理。它只读取 frozen thesis，不能生成新的观察、改变 pair verdict 或把工程 ID/status 原样堆到正文；CJO 对证券价格、估值、回报、仓位和交易动作的禁令保持不变。报告模板的 Ch11 同步要求回答双方关键传导和三种边界。

定向回归 72 项通过，覆盖带 `TESTABLE` 与 `UNKNOWN` 前提/箭头的 CJO 摘要、现有 CJO 输出和 `thesis_test` 的 causal-trace 契约。它会发现前提或箭头漏呈现、错误把未知写成已证实、或在 CJO 输出中重新引入价格/估值语义；若出现，下一步是修正 reader renderer 或冻结字段映射，而非把问题交给文风润色。

### 格力边界与接纳

根因是 `WRITING + REASONING`：若读者只能看结论和 FJ 标题，线上份额、毛利或 OCF 等不同层级的材料会被误解为整个 H-A/H-B 链条均已获证。经济影响是可能材料性地过早确认渠道重配或广泛竞争恶化，并污染 adjusted owner cash 与永久损失判断。

格力缺的仍是同口径全渠道份额/价格带 sell-out、ASP 与返利、渠道库存/回款以及剔除受限资金影响的现金 bridge；禁止因新增呈现层而宣称任何 H-A/H-B 箭头已验证，也禁止用编号、状态词或漂亮图表替代这些事实。接纳条件是未来真实 CJO 能从 frozen pair 渲染全部关键箭头，每条都明确对应当期证据、已注册 FJ 或保守 `UNKNOWN`，并继续保持 `PRE_FREEZE / UNDISCRIMATED / NO_PROBABILITY` 直至数据闭合。

## 101. ITER-97 — 公开的 provider 文章可收窄取数请求，不能替代 release 级竞争证据（2026-08-21）

### 原始来源核对

检索到一篇标署“奥维云网 25-08-15”的[公开文章](https://m.cheaa.com/n_detail/w_648808.html)。其原文称采用 2025 年 7 月“全渠道（涵盖线上与线下）”空调销售数据，列示美的 29%、格力 17%、海尔 15%，并称格力同比下降 2 个百分点。这是此前“没有公开全渠道品牌线索”表述的收紧：至少存在一条由 provider 公开发布、且明确全渠道覆盖的品牌级线索。

不过文章未写明市场占有率的单位（销量或销额）、产品和地域边界、零售交易点定义、行业分母、品牌/子品牌映射、release/version、data-as-of、revision 或原始查询导出。它既没有可重读的面板，也不能同格力年报中自然年线上**零售额**份额直接相连。因此它不满足 `LICENSED_INDUSTRY_DATA` 的历史版本、查询身份和指标语义合同；按现行规则仅可作 `MECHANISM_DISCOVERY_ONLY`，把“请提供 2025-07 全渠道品牌零售的原始历史 release 和定义”加入 AVC P0 请求。

### 根因、边界与接纳

根因是 `DATA_COVERAGE + ACQUISITION_MODULE`，不是分析文笔：公开摘要只给出一个可能重要的方向，却没有让两条机制共享同一 metric/unit/period/denominator 的结算对象。若将 17%/−2pct 直接纳入 H-B，经济影响会是把一条指标含义不明的单月信息误作广泛渠道流失，材料性地压低竞争持续期、owner-cash 与永久损失判断；反向地，忽略该线索则会让数据请求错过最可能的全渠道查询入口。

禁止把该网页升级为公司 VERIFIED fact、官方来源、licensed export、sell-out 定义或历史基准率；禁止与 24.31% 线上零售额份额做横向比较，禁止从单月同比推出价格实现、返利、库存、现金或 H-A/H-B verdict。接纳条件仍是同一 provider 的原始历史 release，含品牌×渠道×产品/价格带×销量/销额/ASP、完整定义和版本/查询/修订身份；在此之前格力状态不变：`PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`。

## 102. ITER-98 — 只有真正区分竞争机制的结果，才可形成“保留/淘汰”经验（2026-08-21）

### 原始研究与缺口

[Kahneman 与 Klein（2009）](https://pubmed.ncbi.nlm.nih.gov/19739881/) 的结论不是“有经验就有直觉”，而是判断环境必须有可学习规律，并向研究者提供足以辨认规律的反馈。已有 `judgment_learning` 只要求 claim 数值已经 `CALCULATED`；这仍允许一个同时符合 H-A/H-B 的 `MIXED` signal 被人工写为 `RETAIN` 或 `RETIRE`，将无区分力的结果误学成公司经验。

最小修复没有增加分数、概率或自动化归因。production adapter 现把 FJ 的冻结 `rival_hypothesis_pair_id / rival_signal_id` 一并投影到 claim；feedback card 从同一 frozen pair 的派生 signal outcome 回填该身份与 verdict。`RETAIN/RETIRE` 除已结算外，若 case 已有 pair，必须是该 claim 的唯一、派生 `SUPPORTS_PRIMARY` 或 `SUPPORTS_RIVAL` signal；`MIXED`、`NOT_YET_DUE` 或 pair 已在而 claim 未绑定，都只能 `INSUFFICIENT_EVIDENCE`。整体 pair 尚未到 terminal 并不阻断一个已区分双方的 `EARLY_MECHANISM` signal，因为它只能改变下一次取证设计，不能宣布终局机制胜负。

### 影响、边界与接纳

根因是 `REASONING + MODEL`，不是 `DATA_COVERAGE`：系统已有对立机制和结算器，但没有把“是否真分辨双方”带到学习处置。经济影响是若不修复，恰好命中的线上份额、毛利或 OCF 数字会被当作可复用的格力渠道/现金判断，材料性地污染竞争持续期、owner cash 与永久损失的后续研究。

禁止因单个 claim `MET/MISSED`、总 pair narrative、后来股价或人工确信直接保留/淘汰信号；也禁止将 `MIXED` 写成“双方都部分正确”后当作一条可迁移经验。接纳测试为：adapter 保留 pair/signal 身份；feedback 只能由冻结 pair outcome 解析该身份；`MIXED` FJ 的 `RETAIN/RETIRE` 必失败，`SUPPORTS_PRIMARY/RIVAL` 的已结算 signal 可追加 note，旧无 pair 的历史 case 仍只作为 legacy feedback，不能伪称覆盖 G1-J 训练。格力尚无真实冻结 pair 或到期 outcome，故没有任何格力信号被保留或淘汰，状态仍是 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`。

## 103. ITER-99 — 复盘必须定位下一轮要改的任务环节，不能只留下宽泛“根因”（2026-08-21）

### 原始研究与缺口

[Remus、O’Connor 与 Griggs（1996）](https://www.sciencedirect.com/science/article/pii/S0749597896900357) 在结构不稳定的判断预测实验中发现，提示任务结构的反馈优于只通知上次表现。路线图早已要求将错误区分为状态表征、机制、取证、财务传导或估值/决策，但 `judgment_learning_note` 的实现此前只接受宽泛项目标签，且可留空；“REASONING”因而可能既指机制没想对，也指资料没拿到，无法使下一轮的 source 选择或 FJ 设计真正不同。

最小修复是新增必填的 `failure_loci`，可选项仅为 `STATE_REPRESENTATION`、`MECHANISM`、`EVIDENCE_ACQUISITION`、`FINANCIAL_TRANSMISSION`、`VALUATION_DECISION`；同时 `root_cause_classes` 不再可为空。它们不是事后自动归因：研究者仍人工判断、可标多个环节，并以现有 `next_research_change` 说明要改什么。它们也不重写冻结 FJ、观察、pair verdict、概率或任何价格/投资字段。

### 影响、边界与接纳

根因是 `REASONING + WRITING`：过程文档承诺了任务信息反馈，实际学习卡却只留下结果与泛化标签。经济影响是相同的格力“毛利未降/OCF 很高”信号下次会被再次读取，却没有说明该补全渠道数据、改写 H-A/H-B 的传导，还是只应修现金 bridge；这会把报告篇幅误当作公司经验。

禁止用 `MET/MISSED`、股价、终局好坏或“加强谨慎”替代 failure locus；也禁止以 `VALUATION_DECISION` 回填 CJO 的无价格经营判断。接纳测试为：空的 root cause 或 locus、以及未定义的 locus 均被拒绝；合格 note 保留宽泛根因、具体任务环节与下一次研究改动；原有冻结/结算不受改写。格力尚无到期的真实 CJO FJ，因此这只是让未来反馈更有信息量，不改变 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`。

## 104. ITER-100 — 预演失败可提高反方质量，但不能再造一张风险清单（2026-08-21）

### 候选方法与契约试验

Mitchell、Russo 与 Pennington 的[《Back to the future》](https://doi.org/10.1002/bdm.3960020103)把 prospective hindsight 定义为先把未来事件当作已经发生、再解释其原因；Klein 的[项目预演失败](https://hbr.org/2007/09/performing-a-project-premortem)将这一思路用于在承诺前暴露原本不易说出的失败原因。它们不能证明这种练习会提高投资收益，也不能把想象出来的风险升级为公司事实；可迁移的窄用途是让研究者在选择中心路径前，主动生成一条能与当前解释竞争的失败因果链。

将该方法映射到既有 G1-J 契约后，结论是**不新增 premortem 表或风险分数**。现有 `rival_hypothesis_pair` 已要求同一当期事实的替代解释，`critical_assumptions` 已要求写出“若中心路径错误，必须在哪个前提失效”，`causal_trace` 已要求该失效经过可观察箭头并连接 early discriminator。新对象只会把同一失败想象复制为一张文本风险清单，既不增加信息，也容易让没有预测含义的担忧混入报告。

### 最小工作法与验收

在每次真正的 CJO freeze 前，可进行一次短的预演失败：假定主机制在 12 个月内被证明错误，只产出候选原因。每个候选只有满足“解释同一共同事实 → 形成不同机制箭头或必要前提 → 导致一个既有或新增 FJ 的不同可结算谓词”时，才能进入 pair；不能满足就保留为 `UNKNOWN` 或删除。格力 H-A/H-B 的具体应用是：不能只写“渠道竞争可能更激烈”，而要指出全渠道 sell-out/ASP/返利/库存/回款中哪一个先出现、为何会同 H-A 的渠道重配序列不同、以及哪一种合格来源可以裁决。

根因是 `REASONING + WRITING`，不是少一份报告：没有预演时，反方容易退化为泛泛风险；若另建风险表，又会把想象当作证据。经济影响是前者会过早确认线上份额、毛利或 OCF 所支持的竞争机制，后者会用“风险很多”替代可检验判断，二者都可能扭曲 owner cash 与永久损失评估。禁止把预演内容当事实、概率、价格/估值输入或事后解释；也禁止用它绕过 `UNKNOWN` 的保守处理。接纳条件是未来每个被冻结中心路径至少有一条由预演触发、却已被 pair/critical-assumption/causal-trace/FJ 完整吸收的失败链；没有新分叉观察的候选不得留在正式报告中。格力因缺同口径竞争与现金资料，当前只能完成问题生成，不能据此冻结 H-A 或 H-B。

## 105. ITER-101 — 多份报告不能直接做“预测平均”；先证明它们预测同一个、可结算的对象（2026-08-21）

### 文献反例与现场试验

[Bates 与 Granger（1969）](https://doi.org/10.1057/jors.1969.103)及 Clemen 的[综述（1989）](https://doi.org/10.1016/0169-2070(89)90012-5)确实发现：对同一对象的多个前瞻预测进行组合，可能降低均方误差；但它们讨论的是可定义目标、误差历史与可比较预测的组合，而不是把多篇研究叙事、目标价或相同图表取平均。Timmermann 的[综述章节（2006）](https://doi.org/10.1016/S1574-0706(05)01004-9)也强调组合收益取决于预测误差相关性和模型不稳定性，不能从预测数量本身推出。

以这些前提反查当前格力材料，结果是组合条件一个也未满足：本地没有可读的二十多份外部研究原件；已选 41 份是同一公司跨期的法定披露；8 张案例卡是路由原型而非同一指标的预先预测；主输出目录的 9 条 `base_rate` case 也全为 `CANDIDATE / NOT_ASSIGNED`，尚无误差记录。因而“给二十份报告加权／取共识／让模型汇总”没有统计或第一性原理依据，且会把共同依赖的公司披露、行业数据库和卖方叙事重复计数。

### 可执行边界

外部报告进入后仍按 `MECHANISM_DISCOVERY` 逐篇解析，而不是赋权：将每一份的预测性内容归并到已存在的共同机制箭头；相同箭头只保留一个待验证任务，新增报告只在提出不同 arrow、不同交易点定义或能使 H-A/H-B 给出不同 FJ 谓词时才新增研究价值。目标价、估值倍数、评级和股价回报永不参与这个归并。

只有在将来同时具备**同一 metric/unit/denominator/horizon、报告当时可得性、逐篇已写下的前瞻谓词、独立结果 observation 与按 PIT 追加的误差记录**时，才允许把“外部预测组合”作为单独实验；即便那时，也先以等权平均作为对 Turtle 自己冻结 FJ 的外部 benchmark，而非中心路径、事实来源或投资结论。若报告共享同一 provider release、公司管理层引述或相同发布日期，则其相关性未知，必须先按共同证据谱系折叠，不能声称独立多数。

根因是 `REASONING + DATA_COVERAGE`，不是模型尚未会加权。经济影响是虚假的共识会材料性地抬高对竞争持续期、normal owner cash 和永久损失的确信度；反过来，完全忽略外部异议又会错失数据请求和最强反方。禁止以报告篇数、机构名气、目标价分散度或后来收益率替代这些条件。接纳条件是每一个拟组合的预测能通过共同目标与 PIT 误差审阅，且组合相对单一冻结 FJ 的增量在留出 episode 中可见；在此之前，20 多份报告的价值仅是发现不同机制，不是获得“更准的平均答案”。

## 106. ITER-102 — 逐次预测评估已适配 CJO；不要让投资监控替代经营学习（2026-08-21）

### 文献与现有链路核对

Dawid 的[prequential 方法](https://doi.org/10.2307/2981683)把评价对象限定为预测实际作出后的序列与随后观察到的结果，而非事后重述的模型参数或故事。这与 Turtle 所需的“先冻结 FJ，再追加公司经营 observation”完全一致；它也不要求现在给格力编造概率。概率校准是另一个、需要重复独立二元问题的统计任务，不能因逐次结算已可运行就被提前开启。

代码路径核对表明，`historical_backtest.v2` 的 `COMPANY_JUDGMENT_ONLY` 已是合适的 prequential 容器：生产 adapter 从冻结 thesis 投影 claim、保留 pair/signal 身份；后续 settlement 只能追加，CJO 强制 `price=UNKNOWN`、无投资动作，早期机制信号可以在终局经营结果到期前单独结算。`judgment_feedback → judgment_learning_note` 又把已结算且真正区分 pair 的结果转换为下一轮可执行的 `RETAIN/RETIRE/INSUFFICIENT_EVIDENCE`。这比等年报后凭印象复盘更快，也不会把早期信号偷换成终局胜负。

反而旧 `research_monitoring` 的 snapshot/threshold/decision-review 语义面向已发布的投资研究；若把它作为 CJO 的反馈引擎，会重新引入阈值触发、决策审阅甚至回报事件的投资对象。这是 `MODEL + REASONING` 的边界错误，不能以“监控更实时”绕过无价格公司判断。CJO 只能走 FJ→production case→HBT settlement→feedback/learning 的逐次链路；投资研究在公司判断完成后另走自己的监控轨。

### 格力试验、边界与接纳

对真实格力 `company_blind_track` 的当前目录检查，只存在 `document_manifest.json` 与 257 条 `VERIFIED` 的 `fact_observations.json`；没有正式 FDB、`thesis_test.json`、中心路径、CJO snapshot 或 calibration case。因此无法合法生成第一项逐次预测，也不能把 2021 格力钛、2025 年报或 8 月回购公告回写成“已经结算”。阻断是 `DATA_COVERAGE + REASONING`：P0 同口径竞争 release、现金正常化和资本兑现仍不能使 H-A/H-B 两方给出可冻结的不同谓词。

接纳条件是未来真实 CJO 的每个 FJ 都有冻结前 source、同定义基线、窗口和 pair signal；到期 source 只追加在 settlement series；学习 note 只针对已 `CALCULATED`、且派生 verdict 为 `SUPPORTS_PRIMARY` 或 `SUPPORTS_RIVAL` 的信号。禁止以价格、总回报、报告篇数、后来管理层文字或 `MIXED` signal 做保留/淘汰。格力在此之前保持 `PRE_FREEZE / UNDISCRIMATED / NO_PROBABILITY`；本轮不加新的实时仪表盘、概率分数或“预警”层。

## 107. ITER-103 — 行业、品牌份额与价格带预测须先满足层级恒等式，不能靠“上/下”叙事拼接（2026-08-21）

### 候选方法与已有实现试验

[Hyndman、Ahmed、Athanasopoulos 与 Shang（2011）](https://doi.org/10.1016/j.csda.2011.03.006)讨论层级时间序列时强调：独立生成的上、下层预测可能彼此不相加，必须按实际层级关系协调。其最小可迁移部分不是给格力做最小方差组合，也不是从数据不完整的层级中补点；而是先把同一零售 release 内的恒等式守住——品牌零售量/额由全市场量/额与格内品牌份额共同决定，ASP 由额与量共同决定。

对现有 `industry_retail_state_decomposition` 的实际检验显示，它正采用这个窄原则：同一 `RETAIL_SELL_OUT` source 的每个稳定 `channel × product × price-band` cell 同时保存 market 与格力 units/value，份额由二者相除，跨期的市场规模、类别 mix 与格内份额贡献精确回加到格力零售变动；若 cell 缺失、shipment 混入或公司量超过市场量，验证器拒绝。它不是因果模型，也不会“修正”预测数值，更不会把 retail sell-out 与格力收入、返利、库存或 owner cash 当作同一个层级。

### 格力的采用边界

这为 H-A/H-B 提供的改进很具体：未来 P0 AVC release 到位后，任何“格力全渠道/线下/价格带份额稳定或恶化”的 FJ 必须由同一 source 的 market×Gree cells 派生；不能同时引用一条品牌份额、另一条行业销量、第三条公司收入，再用方向词把它们拼成竞争判断。若行业份额、品牌份额、量和额不在同一 release、region、product、channel、brand mapping、denominator、period 与 transaction point，正确结果是 `NOT_RECONCILABLE / UNKNOWN`，而不是选择一个方向更好看的图表。

根因是 `DATA_COVERAGE + REASONING`：格力现在没有可用 P0 原始面板，且旧报告容易把年报线上销额份额、行业出货和公司收入混为一个层级。经济影响是这种拼接会材料性地误判渠道重配是否维持品牌位置，继而过度推断 ASP、现金转换和竞争持续期。禁止把层级恒等式误称为因果证明、以补全/插值修复缺 cell、或由 retail 层级推导公司会计收入和 owner cash。接纳条件是经过原始 release 合同与完整 cell 验证的诊断输出，再作为一个 pair discriminator 连至官方公司的量价、费用和现金 FJ；格力当前不产生数值或中心路径。

## 108. ITER-104 — 无价格公司判断的完成门必须同样无价格，才有真正的逐次学习链（2026-08-21）

### 生产链复核

ITER-102 确认 CJO 应走 `FJ → case → settlement → feedback/learning`，但端到端复核还发现 `report_completion` 沿用投资报告的章节 11 `GG` 推导和 `decision_manifest` 要求。即使 FDB、thesis、snapshot 和 Phase10 adapter 已支持 `COMPANY_JUDGMENT_ONLY`，这道最后的完成门仍会强迫研究者伪造估值、仓位或交易对象，或者根本无法冻结可结算的公司判断。

现将完成契约也按冻结的 `analysis_contract.analysis_purpose` 分流：CJO 仍严格检查章节、官方证据、四层 FDB、claim、thesis、insight、独立判断审阅与绝对质量；但跳过 `GG`、估值路线、市场刷新、base-rate 投资门、决策账本/compiler/reliability 和 decision manifest。`INVESTMENT_DECISION` 的现有门不变。回归同时检验 CJO 不会被证券结论阻断，且投资轨仍继续要求原有对象；完成门的定向 73 项、与 FDB、thesis、snapshot、接纳、adapter、HBT、learning 和持牌行业边界的跨模块 289 项均通过。

### 经济边界与接纳

根因是 `MODEL + REASONING`：系统把“可发布的投资报告”错误等同于“一切可学习的公司判断”。经济影响是研究会为通过机器门而产生虚假的价值、回报或行动，从而用股价语言污染渠道、现金和资本配置的第一性原理判断；这会削弱而非增加格力的未来判断能力。

禁止把缺估值/价格/仓位称为 CJO 的不完整，也禁止为了走投资门替当前格力补造中心路径。接纳条件是一个真实（非结构化 fixture）的格力或同行 CJO，以无价格 source package 通过 completion、snapshot、独立接纳、Phase10 case 与后续经营 settlement；届时再检验 feedback 是否只改变下一次的取证/FJ，而未回写原结论。格力当前仍缺 P0 同口径竞争 release、现金正常化与资本兑现资料，故保持 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`。

## 109. ITER-105 — 情景规划可扩大可想象的竞争路径，但不能替代竞争机制的可结算设计（2026-08-21）

### 文献筛选与映射

Wack 的[情景规划原文](https://hbr.org/1985/09/scenarios-uncharted-waters-ahead)针对的是环境剧变下单一路径预测的脆弱性；Schoemaker 的[《Scenario Planning: A Tool for Strategic Thinking》](https://www.researchgate.net/publication/220042263_Scenario_Planning_A_Tool_for_Strategic_Thinking)将其窄用途描述为识别基本趋势与关键不确定性、以对立而内部一致的未来路径克服过度自信和隧道视野。两者支持先拓展机制空间，**不**支持把叙事数、情景名或管理层偏好的“base case”当作预测质量。

映射到 Turtle 后无需再加 scenario 模板。现有 `rival_hypothesis_pair` 已要求双方解释同一当期事实、产生不同的机制箭头及有序的 6–12 月信号；`probability_sets` 允许第三个终局，但路线图已规定当它真能解释共同事实且有自身传导/FJ 时，必须形成自己的 pair/card，而不能塞进模糊风险。场景的唯一新增工作法是 CJO freeze 前问一次：是否还存在一条会改变竞争持续期、现金或资本配置结论、却未被 H-A/H-B 覆盖的结构性路径？若无共同事实或不同可观察序列，正确身份仍为 `UNKNOWN`，而不是为了“完整情景集”编一条中性路径。

### 格力边界与验收

根因是 `REASONING + WRITING`：把行业的不确定性写成多个生动情景，很容易掩盖每条是否能被未来经营事实推翻。经济影响是一个无谓的“基准情景”可能在没有全渠道份额、ASP/返利、库存/回款和现金 bridge 时，把线上份额下降、毛利暂稳或表观 OCF 合成为虚假的中心路径，材料性影响竞争持续期与 normal owner cash。

禁止为格力现在设定情景概率、以行业总量/股价挑选情景，或把 scenario narrative 当成 FJ 证据。接纳条件是未来每个新增格力情景都能（1）解释同一当期事实，（2）列出不同于既有机制的关键箭头/必要前提，（3）给出至少一项同口径、预注册、可结算的经营 FJ；做不到就不新增。故情景规划被接纳为 CJO freeze 的一次反方检查，而不是一个新评分、图表或报告章节；当前格力状态不变。

## 110. ITER-106 — 案例可以按结构匹配来生成问题，不能在零合格 episode 时被“相似度加权”（2026-08-21）

### 原始理论反查

Gilboa 与 Schmeidler 的[《Case-Based Decision Theory》](https://doi.org/10.2307/2946694)形式化了一个朴素但重要的事实：不确定性下的判断会参考相似历史案例；其模型中的行动表现由相似案例的结果加权。它为“从格雷厄姆到巴菲特的案例为何有启发”提供了一个严谨解释，却也直接暴露 Turtle 不能照搬其数值聚合的一面：权重需要可定义相似性，结果需要可比，且历史 case 必须已实际结算。

当前八张书籍卡仅是 `ROUTING_ONLY_NOT_COMPANY_EPISODE`，主输出的九条 `base_rate` case 均为 `CANDIDATE / NOT_ASSIGNED`；格力的 41 份官方文件也属于同一公司的事实编年而非已知结果下的独立 decision case。因此没有合格的 outcome、独立性或误差历史可估相似性权重。把“技术转型”“客户锁定”或书中最终收益塞进 weighted average，只会将作者叙事和当前研究者的主观相似感双重计数。

### 保留的工作法与边界

Turtle 只采纳该理论的非数值部分：`analogy_transfer_card` 显式列出目标状态向量、可迁移的 driver → intermediate → operating consequence、结构不匹配/失效条件和 `strongest_near_miss`。这正把“相似”拆成可反驳字段；既有 `QUESTION_ONLY` 的 near-miss 在没有合格 episode 时只能提出一个 FJ 或数据请求。只有将来至少有按同一问题、同一终局空间、独立公司 cluster、PIT freeze 与读过 outcome 审核过的 episode，才可研究相似度是否可用；即便如此，先比较迁移的机制顺序/失效条件，不能直接权重目标价、估值倍数、股价或终局总回报。

根因是 `DATA_COVERAGE + REASONING`，不是缺少案例卡数量。经济影响是把不合格类比当作可加权经验，会在渠道位置、现金质量或资本配置上形成虚假先验，材料性影响格力的竞争持续期、normal owner cash 与永久损失判断。接纳条件是每张引用的 card 都保留至少三项结构匹配、一项断裂和一个可结算 signal；无实际 episode 时保持 `UNKNOWN_NO_QUALIFIED_EPISODE`，而不是赋予相似度分数或概率。格力当前状态不变。

## 111. ITER-107 — 多份卖方报告的共同来源和从众动机必须先折叠，才谈得上“不同观点”（2026-08-21）

### 原始研究与报告输入边界

Scharfstein 与 Stein 的[《Herd Behavior and Investment》](https://stein.scholars.harvard.edu/publications/herd-behavior-and-investment)给出一个声誉关切可使理性主体模仿彼此、忽略私人信息的模型；Hong、Kubik 与 Solomon 的[分析师预测研究](https://www.columbia.edu/~hh2679/rje-analyst.pdf)则在控制预测准确度后，观察到资浅分析师较少偏离共识、修改更频繁。这些文献不是关于格力或中国卖方报告，不能预断任何作者在从众；但足以否定“二十位分析师 = 二十份独立信息”的默认假设。

因此 `MECHANISM_DISCOVERY` 的逐份报告登记除当时可得性、机制箭头、分歧和 FJ 任务外，还必须写它宣称依赖的**原始来源谱系**：公司披露、同一 provider/release/query、渠道访谈、公开统计或未披露。相同谱系的同向说法折叠为一项机制发现/取证任务，不增加证据数、不增加类比覆盖，也不增加组合权重；未披露谱系只能保留为 `UNRESOLVED_DEPENDENCE` 的问题来源。只有存在可读、不同且能独立结算的前瞻谓词时，才可能在未来成为外部 benchmark 的独立输入。

### 格力边界与验收

根因是 `REASONING + DATA_COVERAGE`：报告标题、机构数和措辞差异不能识别信息是否独立。经济影响是把同一公司年报、AVC 图表或管理层表述的多次转述投票化，会虚增对渠道重配/竞争恶化、现金质量和永久损失结论的确信度；相反，真正不同的渠道交易点或数据定义若未登记，又会被表面共识掩盖。

禁止依据机构声望、目标价分散度、评级或后续股价给报告加权，也禁止反向指控某一报告从众。接纳条件是未来每份外部格力报告均可映射到来源谱系；共享谱系的输入在进入 pair 前已折叠，未披露谱系不计入任何样本或组合，且每个保留下来的分歧都产生一项同口径 FJ/来源请求。当前没有这些报告原件，因此不新建空 schema，格力状态不变。

## 112. ITER-108 — 已找到产业在线的精确月度产品目录；它收窄 P0 请求，但不是可直接使用的数据（2026-08-21）

### 可获取性复核

产业在线公开的[《中国家用空调行业生产计划及规模预测月度研究报告》](https://www.chinaiol.com/Report/202005/9_875.html)说明其交付格式为 Excel、按月提供，并列出行业/品牌库存推算、格力等企业产销、生产计划与预测吻合追踪。结合路线图已登记的[《中国家用空调行业产销月度研究报告》](https://www.chinaiol.com/Report/202005/9_797.html)，这将原先笼统的“产业在线数据”请求收窄为两类有明确字段方向的历史月度产品：前者优先补库存/企业轨，后者补企业产销/内外销轨。

这不是 P0 已取得：公开目录没有交付 2023–26 cutoff 前的历史 Excel、具体 release/query/version、品牌映射、内销交易点、库存归属、data-as-of 或修订身份。公开新闻中的单月生产/销售/库存数字同样没有替代这些合约字段。故目录只能作为 acquisition query 的能力证据；它不能成为 `LICENSED_INDUSTRY_DATA`、公司事实、stock-flow reconciliation 输入或 H-A/H-B 结算。

根因是 `DATA_COVERAGE + ACQUISITION_MODULE`。经济影响是若误把产品目录/新闻数字当作连续版本化 panel，可能把行业生产、内销 shipment 与终端 sell-out 拼接成假库存/需求结论，材料性误判竞争持续期和 cash-conversion 风险。修复已写入 P0 请求正文：要求上述两类产品的历史原始 Excel 与 release/query/metric/scope/revision definitions，并明确它们只同 AVC sell-out 并列，除共同 stock-flow boundary 外不相减。接纳条件仍是收到可保存的原始 export 后通过行业来源契约；格力当前保持 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`。

## 113. ITER-109 — CJO 必须在历史 case 的最后一关仍保持无价格（2026-08-21）

### 端到端反例与修复

将 production fixture 从“CJO case spec + 投资报告快照”改为真正的无价格 CJO 后，Phase10 adapter 虽已按 `analysis_purpose` 选择 CJO gate，`historical_backtest.v2` 的最终 production-origin 验证却仍无条件要求 snapshot 的 `decision`、`valuation` 已就绪，并要求报告包含 `## Valuation` 与 `## Decision`。这意味着一份已经通过无价格 completion、snapshot 和 independent review 的公司判断，仍会在生成可追加 settlement 的 case 时被拒绝；或更糟，研究者会补写虚假的估值、回报和动作以通过机器门。

修复只在 `COMPANY_JUDGMENT_ONLY + PRODUCTION_PIPELINE` 分支选择 CJO 的六个报告章节（公司判断摘要、经营驱动、财务与资本、竞争机制与信号、监测与再研究、结论与数据边界）及相应 snapshot gates：官方证据/FDB 可为 `REVIEWABLE`，claim/thesis/insight 必须已就绪。投资用途仍要求原有 decision、valuation 和投资报告章节。adapter 同时按 case purpose 写入正确 section markers；测试夹具的 FDB、FJ monitoring contract 与独立 review 冻结同一份 bridge，避免把“无价格”误解成“没有公司驱动”。

### 经济边界与接纳

根因是 `MODEL + REASONING`：终端回测验证仍把公司判断误建模为投资研究。经济影响是渠道份额、现金正常化和资本配置这些本应由事实与未来经营结果裁决的判断，会被价格语言污染；并会使以 FJ 训练公司经验的反馈链在最后一步断裂。

禁止把本次 00506 production fixture 当作格力 episode、以 empty bridge 代替真实四层 FDB，或因为 CJO 不要求估值就允许无 FJ—driver monitoring link。接纳条件是 CJO production fixture 以 snapshot-hashed FDB、FJ、独立 review 和 CJO report sections 通过 adapter 与 HBT v2；同时 investment regression 仍拒绝缺失 valuation/decision 的投资 case。本轮 75 项定向 Phase10 adapter/HBT v2/completion/acceptance 回归与 289 项跨模块回归均通过。格力仍没有真实 FDB、CJO snapshot 或到期 observation，状态不变。

## 114. ITER-110 — 对立协作的价值是共同约定“谁能赢”的测试，不是扩张评审层（2026-08-21）

### 文献筛选与现有对象核对

Mellers、Hertwig 与 Kahneman 的[对立协作实验](https://doi.org/10.1111/1467-9280.00350)把有效分歧处理收窄为：相持的解释方共同约定能裁决分歧的经验测试，并由仲裁者执行；不要求事前理论一致，也不以辩论的文采或多数票决定胜负。这个思想适合“行业分析不足”的问题：格力的 H-A/H-B 不能靠更长的双方论述赢，而必须先约定同一市场事实、双方不同的可观察顺序与允许来源。

现有 G1-J `rival_hypothesis_pair` 已具备实质骨架：共同当期事实、双方机制链、critical assumptions、至少两条有序 causal trace、同 metric/unit/horizon 的主/反 FJ 谓词和 append-only verdict；`judgment_review` 也已经是 `independent_challenger`，而 production case 的独立 review 必须复核完全相同的 frozen contract。因而不新增“仲裁委员会”、评分表或一张新的审阅账本。把研究者、红队和 reviewer 的人数做成质量指标，会重演报告数量/共识票数的错误。

### 最小工作法与验收

每次真正 CJO freeze 前，作者与独立 challenger 只需完成一个短的对立协作问题：`若 H-A 与 H-B 都承认当前线上份额下行、收入弱而毛利未塌陷，未来 6–12 月哪一项同口径观察会让其中一方明显更难成立？` 提出的答案必须已经落入 pair 的 FJ/discriminator、其 FDB monitoring contract 和允许 source；不能落入者只能变成 acquisition task 或 `UNKNOWN`。reviewer 不必同意中心路径，却必须能用冻结 contract 复现双方何时输赢。

根因是 `REASONING + WRITING`：若把对立协作降为“写反方意见”，行业信息会继续在双方都能解释的层面堆积。经济影响是线上份额、毛利、行业总量或 OCF 等非诊断信号可能被事后选作任一方的支持，从而虚增对竞争持续期、normal owner cash 与永久损失的确信。禁止用投票、模型间的所谓独立性、目标价或后续股价裁决；也禁止把独立审阅的存在当作 CJO 已具有 P0 行业事实。接纳条件是每个真实 pair 的 challenger 所列裁决问题能逐项指向已冻结 FJ/FDBMON；不能指向的结论降为背景。格力尚缺 P0 release，所以目前只能生成此问题，不能签发 H-A/H-B 胜负。

## 115. ITER-111 — 只有能暴露自身错误的行业信号，才可作为机制支持（2026-08-21）

### 严格测试原则的映射

Mayo 的[《Statistical Inference as Severe Testing》](https://www.cambridge.org/core/books/statistical-inference-as-severe-testing/D9DF409EF568090F3F60407FF2B973B2)及其较早的[Novel Evidence and Severe Tests](https://doi.org/10.1086/289639)共同强调的可迁移原则是：若取证过程几乎不可能发现一个命题的错误，即使结果看似符合，也不应把它当作强证据。这里不移植其统计概率公式，也不把投资研究伪装成受控实验；只保留“支持必须是带风险的、对竞争解释有区分度的后验观察”。

对格力，这给出清晰裁决。2023–25 的线上销额份额下行、2025 消费电器收入走弱、毛利率未塌陷与表观 OCF 很高，都可触发研究，却不能各自确认 H-A 或 H-B：两条机制都允许线上弱与短期组合毛利稳定，OCF 又含材料性受限资金释放。只有同一 release 的全渠道/线下/价格带相对位置、再加公司费用/回款/调整后现金的预注册序列，才可能让其中一方承受真正失败风险。

现有 pair/FJ 契约已经实现了这一最小化版本：主/反 prediction 必须同 metric/unit/horizon/due，`SUPPORTS_PRIMARY / SUPPORTS_RIVAL / MIXED` 由结果 observation 派生，且 `MIXED` 不能被写成中心路径胜利。故不新增“证据权重”、severity 分数或 Bayesian 概率；那会制造精确性幻觉并与单一公司的少量事件不相称。实施上只把所有双方都可预测的行业数、管理层文字和单期会计比率标为 `CONTEXT_ONLY`，直到它们转换为 pair discriminator。

根因是 `REASONING + DATA_COVERAGE`：不足在于缺可使反机制失败的同口径观察，而不是缺少正面论据。经济影响是若将非诊断的线上份额、行业总量、毛利或 OCF 计作多条“支持”，会材料性夸大格力竞争持续期、normal owner cash 和永久损失判断的把握。禁止在 outcome 已见后挑选一个更有利的信号、以 signal 数量代替严重性，或把 `MIXED` 升格为任一方确认。接纳条件是未来每个结论性行业信号都可说明：H-A 与 H-B 对它为何给出不同预测、反方若真会如何被发现、以及数据 contract 是否允许该结算；否则只写背景。格力状态不变。

## 116. ITER-112 — 区间预测可保留真实不确定性，但 pair 不能让反方在逻辑上永远赢不了（2026-08-21）

### 文献、漏洞与最小修复

Gneiting 与 Raftery 的[proper scoring rules 综述](https://doi.org/10.1198/016214506000001437)说明区间/分布预测不能只看覆盖率：有效评估还需同时考虑校准和 sharpness，才能避免无信息的宽范围总是“正确”。Winkler 的[区间估计决策理论](https://doi.org/10.1080/01621459.1972.10481224)同样将区间宽度纳入损失。它们适用于有足够重复 episode 的预测比较；格力目前没有这样的样本，故不能从文献借来一个任意“最大宽度”、伪造置信水平或给单个 CJO 打分。

但实际契约审计发现一个无需统计假设的逻辑漏洞：原 validator 只拒绝主/反 prediction 完全相同，允许主方 `AT_LEAST 90`、反方 `AT_LEAST 95` 一类嵌套谓词。任何满足反方的 outcome 同时满足主方，settlement 因而不可能给 `SUPPORTS_RIVAL`；作者可以保留一个形式反方却让其没有获胜空间。宽区间包住反方所有可能结果时也会产生相同问题。

修复不计算宽度分数，而是让 validator 在两个 predicate 的阈值及相邻 truth-region 上检验：主方必须有至少一个“主真/反假”的可能 outcome，反方也必须有至少一个“反真/主假”的可能 outcome。真实的重叠区仍允许并会结算为 `MIXED`；不重叠也不被强制。该规则同时进入 thesis freeze 和 HBT v2 case validation，因此不能由手写 production case 绕开。

### 经济边界与接纳

根因是 `REASONING + MODEL`：系统把“不同表述”误作“可竞争预测”。经济影响是 H-A/H-B 或任何公司 pair 可被主方写成不可证伪的宽区间/嵌套阈值，长期只积累对主方的表面支持，虚增对竞争持续期、现金转换和资本配置的判断能力。

禁止把本规则解释为要求格力此刻提供精确区间、概率或最大宽度；P0 未取得时仍应使用 `UNKNOWN / UNDISCRIMINATED`。接纳条件是嵌套 predicate 在 thesis 与 case 两道门均被拒绝，而原有不重叠及有重叠但双方都能赢的 pair 仍可冻结和结算。本轮新增两项拒绝回归，连同 thesis、HBT v2、adapter 和 feedback 的 110 项定向测试，以及 291 项跨模块回归均通过。

## 117. ITER-113 — 强推断要求“这个观察会排除谁”，不要求再建一张 ACH 矩阵（2026-08-21）

### 原始方法与现有契约核对

Platt 的 [*Strong Inference*](https://doi.org/10.1126/science.146.3642.347) 将快速积累的工作法收为反复四步：列出替代假设、设计有不同可能结果的关键检验、取得干净结果、再把剩余假设细化为下一轮子假设。Heuer 的 CIA 原著 [*Psychology of Intelligence Analysis*](https://www.cia.gov/resources/csi/static/Pyschology-of-Intelligence-Analysis.pdf) 对同一问题的实务化提醒更直接：不要分别问每条证据是否支持最喜欢的解释；应同时考察可行解释、证据的诊断性，并预先说明什么新观察会使判断改变。两者都反对“再找更多资料”替代排除测试。

Turtle 已经有刚好足够的实现，而不是缺一张 ACH 矩阵：`rival_hypothesis_pair` 要求双方解释同一当期事实；`critical_assumptions` 和 `causal_trace` 使必要前提与中间箭头可见；每个 `RHPSIG` 对同一 metric/unit/horizon/due 写两边 predicate；settlement 只派生 `SUPPORTS_PRIMARY / SUPPORTS_RIVAL / MIXED`；早期机制 signal 先于终局经营 signal，feedback 只能改写下一轮研究设计。ITER-112 还排除了让一方在逻辑上永远不能获胜的嵌套 predicate。这已回答 Platt 的核心问题：**这个观察会排除哪一条解释？**

### 边界、格力应用与接纳

强推断不是要求每个公司观察像实验室实验一样二元或绝对排除。行业资料会有噪声、两条机制也可能同时部分成立；此时 `MIXED`、`UNKNOWN` 或新增第三条可运行机制才是诚实输出。也不因 ACH 有八步就新建 evidence-matrix、投票、权重或“反方数量”评分：它们会把当前已有的冻结 contract 复制成静态表格，却不能多产生一个可结算观察。

格力的操作问题因而保持极窄：全渠道同口径 sell-out、渠道/价格带 ASP、返利/费用、库存和调整后现金中，哪一项会先出现，且为什么它会让 H-A「渠道/价格带重配」或 H-B「广泛份额与价格实现恶化」之一承受失败风险？目前没有 P0 合格 release，故不能把线上销额份额、行业总量、单期毛利或含受限资金释放的 OCF 伪称为关键检验。

根因是 `REASONING + DATA_COVERAGE`，不是少 20 份格力报告。经济影响是若缺少“排除谁”的问题，报告会把大量相互依赖的材料都算作支持，材料性高估竞争持续期、normal owner cash 与永久损失判断。禁止把无结果、未到期或双方都允许的信号硬裁为胜负，也禁止把未观察到证据误称反方已被推翻。接纳条件是每条正式 pair signal 都能回答“若 primary/rival 为真各会看到什么，以及该 observation 至少会使谁受损”；不能回答即停留在 `CONTEXT_ONLY`。格力状态不变：`PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`。

## 118. ITER-114 — 跨模块集成通过，但不能把工程通路误写为格力判断已完成（2026-08-21）

### 集成假设与测试

本轮不是重复单元测试：新合流的三类修改可能在同一 CJO 生产路径上互相冲突——现金事实的“受限资金增加/释放”方向修正、资本配置的“启动承诺→后续动作→兑现”链、以及无价格的 pair/FJ→snapshot→HBT settlement。若它们不兼容，研究者会在现金正常化、资本配置或竞争机制处被迫补造估值/交易对象，或将含受限资金释放的 OCF 又错误恢复为 normal owner cash。

实际运行 `test_evidence_facts_financial_driver_patterns`、`test_financial_driver_bridge`、thesis/snapshot/completion/CJO output/acceptance、Phase10 adapter、HBT v2、learning 与 acquisition 的组合回归，结果为 **244 passed**；相关脚本 `py_compile` 与补丁格式检查也通过。该回归会捕捉跨期现金方向被提取器再次混同、CJO 被投资 gate 阻断、FJ—FDB contract 丢失、持牌行业 source 越权进入现金/资本路径，或 case 在最终结算处重新要求价格/估值。

### 经济边界与下一步

通过只说明生产约束已经同向：CJO 可以在不读价格的前提下冻结公司机制，竞争/单位经济 FJ 将来可以接合格的持牌行业 release，现金/资本判断仍不放松为非官方资料。它不增加格力的事实数量，也不证明 2025 年表观 OCF 可分配、格力钛全周期成败、H-A/H-B 任一方正确，或八张案例卡已经变成有效经验 episode。

未完成的根因是 `DATA_COVERAGE`，并有相应 `ACQUISITION_MODULE` 的实物输入缺口：当前格力 source package 没有版本化、query-identified 的 AVC/ChinaIOL historical release，也没有 normal owner-cash adjustment bridge 或资本事件的全部兑现资料。经济影响是这些缺口可材料性改变竞争持续期、可分配现金和永久损失判断。禁止用 CHEAA 转述、线上销额份额、单期毛利、`OCF - Capex`、货币资金余额或模拟 release 填补。下一轮的接纳条件仍是实际 release 通过 `enumerate-industry → compose-industry`，形成真实 CJO 的四层 FDB、pair/FJ 与独立 review；到期经营 observation 才能让 HBT 结算，之后才可产生学习 note。

## 119. ITER-115 — 合成对照可评估外生事件，不能代替竞争机制研究（2026-08-21）

### 方法适用性检验

Abadie、Diamond 与 Hainmueller 的 [Synthetic Control Methods](https://doi.org/10.1198/jasa.2009.ap08746) 估计的是一个已经明确的 aggregate intervention（其原例为加州控烟计划）对处理单位的反事实影响；方法用未受处理单位的加权组合拟合处理前轨迹，再比较处理后偏离。它适合回答“某项具体政策/规则/渠道准入变化造成了什么增量”，不适合从一组同行份额、收入和利润数据反推“格力竞争力为何变化”。

格力 H-A/H-B 当前的待解释对象正是竞争状态和渠道重配，没有一个由公司外部决定、时点清晰、只作用于一组单位而可证实未作用于另一组单位的处理。即使未来拿到 AVC/ChinaIOL 面板，直接对格力跑合成控制也会把品牌策略、产品、渠道、宏观需求与竞品反应全部塞进一个系数，既不识别价格实现、渠道权力还是库存机制，也不能为 owner cash 或资本配置提供因果证据。

### 保留的窄入口与禁令

因此不新建 regression/synthetic-control 模块，也不让统计显著性裁决 H-A/H-B。只有未来存在已在 cutoff 前登记的外生制度或渠道事件、可解释的 treated/untreated universe、足够长的同定义处理前面板、无处理组确实未受该事件影响的证据，以及预先指定的单一 outcome，才可另写一项**事件效应**研究；它的结果只能成为 causal trace 的一个 observation，仍须经过 pair/FJ 与公司现金/资本的独立传导。

根因是 `REASONING + DATA_COVERAGE`：面板数据的可得性容易诱导研究者给相关性套上因果语言。经济影响是这种误用会把公司相对位置、行业周期和管理动作误归因给一个“处理效应”，从而材料性扭曲竞争持续期和永久损失判断。禁止把合成权重、显著性、事后挑选的同业组或未证实的平行趋势当作 H-A/H-B、normal owner cash 或投资结论；也禁止因暂时没有合成控制就降低现有 FJ/PIT 的证据标准。接纳条件是上述外生事件设计在出现前都不启用；在此之前，行业深度仍靠同口径状态面板、竞争机制和可结算分叉观察，而非回归系数。 

## 120. ITER-116 — 库存—出货—零售的计算必须先被边界拒绝测试约束（2026-08-21）

### 待验证的产品行为

格力的行业背景同时出现过冷年 shipment、retail sell-out、行业库存和线上价格，但它们不是同一 provider/version、自然期/冷年、品牌分母、交易点或库存归属。这里最危险的“分析加深”是把它们代数相减，给出补库/去库或渠道压力的看似精确结论。正确的可复用方法不是先算，而是先问三条轨能否被视为同一库存—流量系统。

本轮实际运行 `test_phase10_acquisition` 与 `test_industry_retail_state_decomposition`，共 **44 passed**，另对 acquisition/decomposition 脚本完成语法检查。测试覆盖共同 provider/dataset/release/version、完整 `stock_flow_boundary`、`RETAIL_SELL_OUT` 与 `SHIPMENT` 语义分离、缺定义 shipment 保持未解析、以及零售状态分解须使用同一来源完整的 market×brand cells。边界不齐、缺 cell 或品牌量超过行业分母时，系统给出 `NOT_RECONCILABLE` / 拒绝，不产生方向结论。

### 经济边界与接纳

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`：当前没有可对账的三轨 release；若采集/验证不先锁定边界，研究者就会让不同报表的数字替自己回答渠道库存问题。经济影响是错误的补库/去库叙事会材料性影响对竞争持续期、价格实现和现金转换的判断。

禁止由 1.02 亿台 industry shipment、8,059 万台 retail 或“库存超过 5,000 万台”的不同公开口径计算格力库存、收入、返利、owner cash 或 H-A/H-B 胜负；也禁止用 retail 状态分解代替公司会计收入/现金 bridge。接纳条件是未来真实 release 同时保存共同边界和 provider definitions，通过 reconciliation validator 后，只先生成一个有序 pair discriminator；即便如此，仍须经公司费用、回款和现金 FJ 独立结算。当前格力保持 `NOT_RECONCILABLE / CONTEXT_ONLY / UNDISCRIMINATED`。

## 121. ITER-117 — 书籍案例与结果丰富的历史故事必须先通过 episode 资格门（2026-08-21）

### 要验证的失败

用户所说“从格雷厄姆到巴菲特的案例分析水平”很容易被误译为“找更多已知结局的名家故事”。那会让案例卡看似丰满，却把成功/失败答案带回 selection。Eisenhardt 的[多案例理论构建方法](https://doi.org/10.5465/amr.1989.4308385)支持以 replication logic 选择会预期相同或可解释地相反的案例，不支持按后来结果堆样本；这与 Turtle 的 literal replication / theoretical extension / deviant test 角色一致。

本轮运行 `test_case_selection_register`、`test_stage27_base_rate_case_library`、claim evidence 与 thesis gate 的交叉回归，共 **116 passed**，并完成 case-selection/base-rate 脚本语法检查。它实际检验：`OUTCOME_SELECTED_RESEARCH_ONLY` entry 会被 claim、thesis 与 calibration candidate 同时拒绝；只有 cutoff 前 state vector、共同机制问题、选择模式和结果隔离完整的 `PIT_PRE_OUTCOME + INCLUDED` case 才可能进入后续 episode 链；案例卡本身不会因 ID 或书名而取得经验样本资格。

### 经济边界与接纳

根因是 `REASONING + MODEL`，不是案例卡数量。经济影响是若让后来挑选的失败案例作为格力 H-B 的“经验”，或成功案例作为 H-A 的“证据”，竞争持续期、normal owner cash 与永久损失判断会被已知结局材料性地污染。

禁止把八张 routing card、格力钛的现有事后编年、工程 fixture 或名人案例直接升格为 `MEP:` / `CASEEV:`、near miss、参考类频率或中心路径支持。接纳条件仍是每个首批历史 episode 都先有 cutoff 前源包、主/反机制、不同 FJ 和冻结身份，随后才读取 official outcome 并经独立资格审阅；在此之前案例只可生成问题。格力当前 `QUESTION_ONLY / UNKNOWN_NO_QUALIFIED_EPISODE` 的边界不变。

## 122. ITER-118 — 机制判断要显示其相对朴素基线的增量，不能只凭叙事“命中”（2026-08-21）

### 文献与实际链路

Meehl 的 [*Clinical versus Statistical Prediction*](https://meehl.umn.edu/lane-practice) 与 Grove 等的[后续元分析](https://doi.org/10.1037/1040-3590.12.1.19)研究的不是公司投资，不能外推其准确率比例；可迁移的纪律是：复杂、经验性的解释应和一个明确的机械基线比较，而非和“没有分析”比较。对 Turtle，这个基线不是替代机制或自动选股，而是防止长报告在普通趋势延续已经足够时虚称自己的判断带来信息增量。

本轮运行 thesis gate、Phase10 adapter、HBT v2、feedback 与 learning 的联合回归，共 **121 passed**，并完成五个核心脚本语法检查。它检查 simple baseline 的冻结身份与 FJ/pair/claim 一致性、case 投影不丢基线、结算与反馈回显不把一次 `MET` 等同为能力、以及 CJO 无价格边界仍成立。若基线身份或 FJ—pair 链丢失，下一步是修 adapter/feedback 映射，而非用“研究者认为机制更好”补过。

### 格力边界与接纳

根因是 `REASONING + MODEL`：没有可比较基线，任何线上份额、毛利或 OCF 的事后命中都可能只是 carry-forward、行业趋势或偶然。经济影响是会把普通量价/现金延续误认成格力渠道与 owner-cash 的专有判断，进而材料性夸大竞争持续期。

禁止把当前缺 P0 面板的格力强行拟合统计预测器，或把基线误作中心路径、概率、估值和投资动作。接纳条件是未来每项可量化 CJO FJ 在 cutoff 前冻结一个仅使用已允许经营事实的可复算朴素基线；`RETAIN` 还须说明它相对该基线和反机制的增量。没有 P0 与现金 bridge 时，基线也不允许填补 `UNKNOWN`，当前格力状态不变。

## 123. ITER-119 — `MIXED` 必须区分“共同命中”与“共同失败”（2026-08-21）

### 漏洞与最小修复

Platt 的 [*Strong Inference*](https://doi.org/10.1126/science.146.3642.347) 要求关键观察能排除某些可运行解释；Heuer 的 [*Psychology of Intelligence Analysis*](https://www.cia.gov/resources/csi/static/Pyschology-of-Intelligence-Analysis.pdf) 也要求分析者分辨证据究竟能区分假设，还是只要求重新审视问题。对现有 pair settlement 的核查发现，派生 verdict `MIXED` 原来同时覆盖两种经济含义相反的结果：主/反谓词**都成立**，以及主/反谓词**都不成立**。

前者表示该冻结信号落在两方共同允许的区域，因而不具诊断性；后者表示当前观察同时违背两方对该箭头的预期，可能是两个机制都不足、measurement boundary 漂移，或需要提出能解释共同当期事实且有不同可观察序列的第三机制。若都只显示为 `MIXED`，反馈虽不会错误宣布任一方获胜，却会丢失下一轮取证应当重写“信号”还是“机制”的信息。

修复保留既有 append-only verdict 与 API：`SUPPORTS_PRIMARY / SUPPORTS_RIVAL / MIXED / NOT_YET_DUE` 不变，绝不让结果期手写 winner。每个派生 signal 新增 `comparison_state = PRIMARY_ONLY / RIVAL_ONLY / BOTH_MET / NEITHER_MET / NOT_YET_DUE`；pair 另派生 terminal comparison state。反馈卡据此显示 `BOTH_MET → NON_DIAGNOSTIC_SHARED_PREDICTION_REVIEW`，`NEITHER_MET → MECHANISM_OR_MEASUREMENT_RESEARCH_REDIRECT`。它不自动制造第三假设，也不把共同失败直接裁为反方胜利；第三机制仍只有在能解释同一事实并生成新顺序信号时才建立。

### 验收与格力边界

本轮新增回归以相同实际经营 observation 分别构造“主 `AT_LEAST 0.18`、反 `AT_MOST 0.20`”的共同命中，和实际 `0.175`、反 `AT_MOST 0.17` 的共同失败；两者均保持 `MIXED` verdict，却分别稳定派生 `BOTH_MET` 与 `NEITHER_MET`。HBT v2、feedback 与 learning 定向回归 **28 passed**，语法与补丁格式检查通过。

根因是 `MODEL + REASONING`，不是缺少篇数。经济影响是将共同失败误作普通“非诊断”会延迟对渠道重配/广泛竞争恶化之外机制、或行业数据口径漂移的再研究，材料性影响竞争持续期、正常 owner cash 与永久损失判断。禁止将 `BOTH_MET` 当作双重支持、将 `NEITHER_MET` 当作任一方胜利，或仅为了消除 `MIXED` 而新增宽泛第三情景。接纳条件是格力未来每个实际 pair settlement 均保留此细分，`NEITHER_MET` 只能触发有证据的机制或计量边界复核；在 P0 release、现金 bridge 和资本兑现材料到位前，格力状态仍为 `PRE_FREEZE / UNDISCRIMINATED / NO_PROBABILITY`。

### 补充：数据缺失与供应商误差应限制推断，不应中止机制研究（2026-08-21）

NIST 对[测量不确定性](https://www.nist.gov/itl/sed/topic-areas/measurement-uncertainty)和[不确定性报告](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-7-reporting-uncertainty)的原则可迁移为一条纪律：先说明测量对象、边界与不确定性，再说明结果能支持什么；这不把行业面板伪装成物理测量，也不授权一个“准确率分数”。Imbens 与 Manski 的[部分识别](https://doi.org/10.1111/j.1468-0262.2004.00555.x)提供更贴近本任务的警示：当观测不足以点识别时，正确产出可以是受约束的结论或未识别，而不是任取一个点估计。

因此 AVC/产业在线类 release 现在必须随 `measurement_profile` 冻结：方法披露及 locator、误差是已声明边界还是未量化、最大允许推断、已知局限及分歧处理。`DIRECTIONAL_SENSOR_ONLY` 只能生成机制问题；`WITHIN_PROVIDER_RELATIVE_CHANGE` 可在 provider/dataset/release family 与品牌、产品、渠道、分母 mapping 冻结后检验相对变化；`LEVEL_WITH_STATED_LIMITS` 还必须有供应商的可定位误差界。任何供应商之间的冲突固定为 `DO_NOT_AVERAGE_REOPEN_MECHANISM`，而不是按篇数、声望或平均值裁决 H-A/H-B。

已把这项边界接入行业 source validator、thesis FJ、Phase10 settlement 和 retail-state decomposition：方向传感器不能结算数值 FJ，也不能进入份额归因；冻结 FJ 声明的推断层级必须与结果期实际 release 完全一致。定向测试覆盖缺失/不合格 measurement profile、方向传感器误入结算、以及其误入状态分解，**164 passed**。

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`，而非报告篇数。经济影响是把不稳定的行业水平值误作格力的全渠道竞争事实，会材料性错误改变竞争持续期、正常 owner cash 和永久损失；反过来，因不确定而停止机制研究会使研究只能重复财报故事。禁止把版本化历史身份误写成准确性、把公开转述升为 provider release、把供应商数字变成公司收入/现金，或以跨源平均填平矛盾。接纳条件是：真实 release 声明的 `measurement_profile` 与预注册 FJ 匹配，外部相对变化随后由预先指定的公司官方传导检查；若无，则保留 `TENTATIVE_WORKING_PATH / UNKNOWN`，不生成中心路径、概率、估值或动作。

## 124. ITER-120 — 终局 FJ 也必须落在主、反两条因果链上（2026-08-21）

### 过程追踪检验

Collier 的[过程追踪定义](https://doi.org/10.1017/S1049096511001429)要求在因果时间序列中审查有诊断性的证据；不是在一段机制叙述后另放一个“终局指标”。核查现有 pair contract 发现，它已要求双方各至少一条 `EARLY_MECHANISM` signal 连接 causal trace，但允许某个 `TERMINAL_OPERATING` FJ 仅在 pair 中出现、没有对应主方或反方箭头。于是收入、owner cash 或终局经营事实即使后来结算，也可能只是一个与机制故事并列的数字，不能回答究竟哪段传导被检验。

最小修复不新建因果评分、图数据库或第二份机制账本。对新 G1-J pair，现要求**每个** frozen discriminator 都至少连接 PRIMARY 和 RIVAL 各一条 `TESTABLE` causal-trace edge；原有“每方至少两条箭头且有早期 signal”仍保留。故一条终局 owner-cash FJ 必须写明：在 H-A 中它是哪一段正向传导的观察，在 H-B 中它又是哪一段负向传导的观察。当前 `VERIFIED` 历史箭头仍可存在，但不能冒充未来 signal 的 link。

### 验收与格力边界

### 非数值结算边界（ITER-121）

量化 FJ 的 predicate 只对可比较的数值 observation 有意义。核查 HBT v2 时发现 range prediction 已拒绝非数值 `actual_value`，但 point prediction 尚未如此要求；同一个字符串占位符若同时写入 observation 与 metric，能通过两者一致性校验，并在 pair derivation 中被 `_number` 解析失败后落为 `NEITHER_MET`。这把“没有可结算数据”错误翻译为“主、反机制都错”。

修复将所有被冻结的 quantitative operating observation 与 point/range metric 的 actual value 都要求为数值；非数值结果使 settlement `INVALID`，不会产生可供 feedback/learning 使用的 verdict。这里没有新增缺失值填补、默认阈值或统计模型：来源未披露、不可比、口径漂移仍分别留在 source/observation contract 的 `UNKNOWN`、`NOT_CALCULABLE` 或 comparability 状态中。

以 `"not disclosed"` 同时替换冻结 observation 与 point metric 的 actual 值后，HBT v2 明确报告 `value_must_be_numeric_for_quantitative_prediction` 与 `actual_value_must_be_numeric_for_point_prediction`，不再允许进入 pair winner/feedback；pilot、V2、adapter、feedback 与 learning 回归 **88 passed**。根因是 `ACQUISITION_MODULE + MODEL`：非数值或不可比行业/公司数据不能被伪装为主、反两种竞争机制同时失效。禁止把“未披露”、空格、单位文字或来源摘要转成 `0`、阈值边界或 `NEITHER_MET`；格力任一未来 P0 observation 缺数值或可比性时仍为 `UNKNOWN / NOT_CALCULABLE`，不改变 `PRE_FREEZE / UNDISCRIMATED / NO_PROBABILITY`。

### 报告输入的来源依赖（ITER-122）

Asquith、Mikhail 与 Au 的[分析师报告研究](https://doi.org/10.3386/w9246)表明报告正文可含有摘要意见之外的信息；所以“拒绝按篇数计票”不是“拒绝阅读”。但 Welch 的[分析师从众研究](https://doi.org/10.1016/S0304-405X(00)00076-3)发现近期推荐会影响后续推荐，而共识影响并不因其事后更准确而更强。这支持既有的 source-genealogy 规则：每份格力报告只拆成机制箭头、可追溯原始来源、与 H-A/H-B 的分歧及独立验证任务；共享来源的转述折叠，未披露来源谱系只生成问题。

根因是 `REASONING + DATA_COVERAGE`。经济影响是若把二十多份可能依赖同一公司公告、同一 provider 图表或同一渠道传言的报告当作二十个样本，会材料性高估对竞争持续期、价格实现和正常 owner cash 的把握。禁止用机构声望、评级、目标价、后续股价或所谓共识给它们加权。接纳条件是每份实际导入报告有原件、PIT 可得性与来源谱系；目前工作区没有该批第三方报告原件，故格力当前状态不变。

### 因果链验收

本轮故意移除两边 trace 对 `RHPSIG:fj.owner_cash` 的连接，gate 以分别可定位的 `primary_signal_unlinked` 与 `rival_signal_unlinked` 拒绝；主/反两条完整 trace、第三机制的第二 pair、adapter、HBT settlement、feedback/learning 联合回归 **123 passed**。测试若失败，下一步是修 FJ→trace mapping，而不是把 terminal owner cash 写为“支持整体判断”。

进一步的性质测试枚举 `AT_LEAST`、`AT_MOST`、`EQUALS` 的点预测及全部有效区间预测，以端点、相邻浮点数和区间中点穷尽可达观测区域；thesis gate 与 HBT settlement 都只在主、反预测各有至少一个独立成立区域时接受 pair（**110 passed**）。因此，重叠、相同或一方逻辑上不可达的谓词不能借由“写了反方”通过冻结；若未来新增 predicate 形状，这个测试失败时应修其可达区域语义，而不能放宽 pair gate。

文献复核没有支持再给每条证据贴“hoop/smoking-gun”等主观等级。Bennett 与 Checkel 的[过程追踪专著](https://doi.org/10.1017/CBO9781139858472)强调的是先于检验的机制与等结果性处理；对 Turtle 而言，已经落成的共同当期事实、两条完整 trace、双边可达 predicate、规定观察窗与 `PRIMARY_ONLY / RIVAL_ONLY / BOTH_MET / NEITHER_MET` 结算，才会改变下一步研究。额外标签既不新增 observation，也不改变结算，反而会变成事后叙事评分，故不纳入路线图。

根因是 `REASONING + MODEL`。经济影响是终局经营数字可被事后拿来给任何机制背书，材料性夸大渠道、价格实现向 normal owner cash 的传导证据。禁止用单期收入、毛利、OCF 或股价作为未连接的“终局验证”，也不因 pair 两边都链接终局就认定格力任一方获胜；它仍受同 metric、同窗口、可结算 predicates 和 `comparison_state` 约束。接纳条件是格力获得 P0 industry release、现金 bridge 后，每一个真实早期/终局 signal 均可在两条链上定位；此前仍为 `PRE_FREEZE / UNDISCRIMATED / NO_PROBABILITY`。
