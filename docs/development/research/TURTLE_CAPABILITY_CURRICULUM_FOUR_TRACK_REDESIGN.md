# Turtle 企业判断能力课程：四轨历史训练重构

> 状态：`CURRICULUM_LAYER_IMPLEMENTED / INITIAL_LIBRARY_REGISTERED / CAPABILITY_NOT_YET_DEMONSTRATED`
>
> 日期：2026-08-28
>
> 中心目标：在证据、PIT 和权限约束内，持续提高企业判断与投资决策效用；不以字段、gate、工件数量或训练时长替代能力。

## 1. 裁决

此前的主要问题不是 PIT 太严格，而是让一条样本同时承担了教学、考试、迁移证明和方法发布。样本因此极其昂贵，每出现一个局部口径问题，整个训练就退回补合同。系统实际上优化的是“怎样安全通过验收”，不是“怎样通过大量有反馈的案例形成企业认知”。

新的顶层分工是：

```text
能力课程层
  Teaching：看懂案例、比较机制、积累反例
  Blind Judgment：结果前独立作出完整企业判断
  Historical Holdout：只考试冻结后的课程或方法
  Prospective：用真实未来校准现实稳定性

严格评价与发布控制面
  Decision utility / method freeze / report authority

局部 Comparative sidecar
  只有相对因果主张才启用
```

课程层解决“练习量和能力形成”，评价控制面解决“是否真的优于公平 baseline”。二者必须连接，但不得再由后者阻止前者启动。

## 2. 不是减少证据纪律，而是重新分配职责

以下硬边界继续保留：

- cutoff 前后的材料分离；
- outcome custodian 与结果前判断角色分离；
- 同一责任边界、期间、定义和单位；
- 退出、并购、删失和生命周期对象保留；
- `UNKNOWN / EVIDENCE_INELIGIBLE / MEASUREMENT_MISMATCH` 只限制依赖它的主张；
- 价格和结果不能回写企业事实或管理层行动。

改变的是奖励和样本用途：Teaching 可以公开结果，因为它的目的就是学习；Blind 才要求严格结果隔离；Holdout 不能参与形成被评价的方法；Prospective 不再承担早期训练产量。Comparative 只服务 `RELATIVE_CAUSAL_EFFECT`，不服务普通企业重建。

## 3. 四类样本

### 3.1 Teaching：高频机制学习

Teaching 使用结果已知的历史案例。它不是一篇事后故事，必须形成完整、可反驳的经济链：

```text
当时状态与约束
  -> 管理层选择或 no-action
  -> 客户、渠道、竞争或经营反应
  -> 责任单元利润与现金
  -> 资本配置和永久损失
  -> 当前投资处理
```

每个完成的 Teaching 还必须说明：

- 最强反方；
- 一个表面相似但机制不同的 near miss；
- 哪项局部未知仍然存在；
- 如果在另一家公司使用，首先要验证什么 transfer question。

Teaching 不需要假装结果未知，也不计方法优于 baseline。它的价值是建立结构表示、反例库和判断语言。

### 3.2 Blind Judgment：历史结果前检索练习

Blind 使用 fresh role，只给 cutoff 前资料。Agent 必须先形成当前最重要的企业判断、机制、最强反方、管理层、正常盈利、owner cash、永久损失、三情景、估值方向和翻转事实，再由独立 custodian 揭示结果。

Blind 评价两件事：

1. 判断是否被结果实质纠正；
2. 结果是否改变了下一家公司或下一 cutoff 的研究行为。

正确预测本身不是 policy learning，更多字段也不是效用。过度保守与过度乐观同样应被反馈纠正。

### 3.3 Historical Holdout：冻结后考试

Holdout 在训练中不可被读取或用于选规则。它按公司轴，必要时再按时间轴隔离。它只评价已经冻结的课程或方法能否迁移，不允许根据 holdout 结果修补同一版本后再声称通过。

Holdout 数量不必大，但必须独立。一个 holdout 通过也只形成有界证据；不能自动授予方法冻结、报告、估值或交易权限。

### 3.4 Prospective：现实校准

Prospective 在完整结果尚不存在时冻结，真实等待未来披露。中报只能局部更新相应经营轴，不能提前结算全年现金、资本回报或永久损失合同。

Prospective 是现实稳定性检验，不是早期训练主线。它等待一年，也不得阻止历史 Teaching 和 Blind 继续。

## 4. 能力单位：练什么，而不是完成多少字段

课程使用八个能力单元：

1. `BUSINESS_MODEL_ECONOMICS`：企业如何创造客户价值、收费和承担成本；
2. `CUSTOMER_ABSORPTION`：建设、开店、上线或重开以后，客户是否真实采用；
3. `COMPETITION_AND_PRICING`：量、价、份额、竞争反应和共同需求怎样区分；
4. `MANAGEMENT_DECISION_EXECUTION`：问题、可选方案、资源承诺、执行和适应；
5. `CAPITAL_ALLOCATION`：投入、并购、扩建、退出和再配置是否创造价值；
6. `OWNER_CASH_CONVERSION`：经营结果如何穿过营运资本、capex、NCI 和母公司可达性；
7. `PERMANENT_LOSS_AND_LIFECYCLE`：哪些资产、网络、信誉或普通股索取权可能不可逆损失；
8. `VALUATION_AND_ENTRY_TREATMENT`：冻结经营判断如何改变正常盈利、价值方向和最高可接受买价。

每个案例只聚焦一至两个 primary unit，但仍必须给出完整企业判断。能力覆盖按不同 `company_cluster_id` 计算；同一公司多个年份是纵向学习，不是多个独立公司。

## 5. 训练循环

课程采用下列循环，而不是“写 schema—补 gate—再审计”：

```text
Retrieve  取一个已冻结的机制问题和结构相异案例
Compare   与一个同构案例和一个 near miss 做结构比较
Judge     在当前证据下给出方向性企业与投资处理
Reveal    Teaching 直接读结果；Blind 由 custodian 揭示
Revise    说明判断哪里变、为什么变、下次研究动作怎样变
Retain    只保留可迁移的问题、反例和边界，不保留公司结局捷径
```

初始运行采用 `3 Teaching : 1 Blind` 交错节奏。这个比例用于防止两种失败：只看 worked examples 而不练结果前检索，或盲测太多但没有足够机制表示。它是可修订的运行政策，不是统计门槛。

一个学习周期建议使用三种结构关系：

- 同机制、不同表面行业：检验结构迁移；
- 同行业、不同生命周期或资产负债表：检验 moderator；
- 表面相似、机制不同的 near miss：防止套模板。

## 6. 本地候选池污染的处理

本地结果、旧报告或价格暴露是“角色 × 公司 × cutoff × outcome window”的事实，不是公司永久属性。

路由规则为：

```text
当前角色已见结果或派生结论
  -> TEACHING

当前角色只有 cutoff 前资料
  -> 可进入 Blind / Holdout

结果尚未发生
  -> 可进入 Prospective
```

同一公司的更早、且在新 cutoff 前已经公开的资料不构成新 episode 的结果污染。工作区存在结果文件也不等于角色读过它。Blind 的真实资格来自 one-shot fresh role 的实际输入收据，而不是目录干净、角色名写着 FRESH 或一段禁止搜索的 prompt。

这解决两种相反错误：

- 不再因为主 Agent 看过一个公司，就永久丢弃其全部历史教学价值；
- 不再因为复制了一个“盲包”，就假装 Agent 没有继承结果记忆。

## 7. 样本规模与计数

初始容量范围：

| 轨道 | 独立 company cluster 规划范围 | 作用 |
|---|---:|---|
| Teaching | 20--30 | 建立跨机制案例库 |
| Blind Judgment | 8--12 | 检查能力是否开始形成 |
| Historical Holdout | 4--6 | 独立迁移考试 |
| Prospective | 1--3 | 现实校准，不承担训练产量 |

这些数字是基于当前取证成本、行业覆盖和可执行反馈节奏的起始容量，不是研究文献给出的样本量下限。达到数量只说明课程有足够材料可运行，不说明 Agent 已具备能力。

计数规则：

- 同一 `company_cluster_id` 的多个 cutoff 只算一个独立公司；
- A/B/H 股或重复上市证券属于同一经济公司簇；
- 一个公司可有多个 episode，但不得把它们包装成多个跨公司迁移；
- teaching candidate 只算管线容量，不算完成案例，更不算能力证据；
- 字段、receipt、test、gate 和报告页数全部不计样本。

## 8. 当前真实基线

当前课程登记：

| 轨道 | 已完成/冻结 | 当前含义 |
|---|---:|---|
| Teaching | 6 个 curated company clusters | 已把六轮真实反馈转为机制课程资产 |
| Blind Judgment | 1 个 settled、1 个 registered | 公牛 FY2024 已结算；中国外运按冻结 roster rank 2 等待 fresh role 执行 |
| Historical Holdout | 0 | 尚无独立历史考试，不得声称迁移 |
| Prospective | 2 个 company clusters | 紫金冻结；民航信息有局部中期反馈但全年未结算 |
| Teaching candidates | 18 个独立 company clusters | 已知结果的本地池，只待策展，不计能力 |

6 个 curated Teaching 加 18 个候选，形成 24 个独立公司簇的教学管线。它解决“没有案例可练”的问题，但没有解决“能力是否形成”的问题。当前能力覆盖仍明显不足：管理决策执行和估值/买点尚无完成的 primary 教学公司簇，竞争定价也只有一个完成簇。

按 `3:1` 节奏，6 个 Teaching 和 1 个已结算 Blind 之后，第二个历史 Blind 已按原冻结顺序登记为中国外运。下一动作是执行其 fresh one-shot 结果前判断；随后继续策展异质 Teaching。不能为了尽快达到 20 个而连续生成十八篇事后总结，也不能因为 Holdout 为零而阻止课程运行。

## 9. 防御性写作的运行约束

课程不通过禁词、篇幅或字段完整度治理防御性写作，而通过“必须承担当前处理后果”治理：

1. `UNKNOWN` 不是结论。必须说明它限制哪项主张，以及当前因此怎么处理正常盈利、owner cash、永久损失或估值方向；
2. 局部资料不足不得撤回其他已支持的公司判断；
3. 第一稿先写三项企业判断、机制、反方与投资含义，再写 evidence cells；
4. Teaching 必须包含 near miss，防止把案例结局记成通用规则；
5. Blind 必须允许结果向上纠正，保守不是免费安全策略；
6. 更多字段、更长报告、更细分类、更高可审计性不计 utility；
7. 新 gate 只有在真实、材料且可重复的错误发生后才考虑，而且优先修 acquisition、model 或 reasoning，不增加全局准入；
8. 找不到材料时，使用有经济含义的范围、条件性处理或局部 UNKNOWN，然后继续完成企业判断。

第一稿验收不是“证据是否全”，而是：一个投资者能否知道这家公司现在最可能怎样赚钱或失去钱、管理层正在做什么、现金和永久损失怎样传导、什么事实会推翻判断。

## 10. Comparative 的新位置

默认企业判断和 `WITHIN_CASE_MECHANISM` 均为 `comparative_mode=NOT_REQUIRED`。只有明确主张下列内容时才进入严格 Comparative：

> 在同一 time zero、可比责任边界和结果合同下，行动 A 相对行动 B 或 no-action 更有效。

Comparative 的 target-trial、同行、干扰、删失和 estimand 边界全部保留，但只约束这条相对因果主张。它不阻止公司状态重建、客户吸收纵向判断、现金转换或 Teaching。

## 11. 能力与方法有效性的判定

四条事实必须分开：

- `CURRICULUM_CAPACITY_BUILT`：有足够不同公司与机制可训练；
- `BLIND_JUDGMENT_FEEDBACK_ACCUMULATING`：多个结果隔离案例能向上和向下纠正；
- `TRANSFER_CANDIDATE`：冻结方法在不同公司上改变了材料投资处理，并得到结果支持；
- `TRANSFER_VALIDATED`：独立 holdout 重复支持冻结方法。

当前只处于前两项的早期阶段。Teaching 数量、Blind 命中率、Brier 改善或 reviewer 的积极文字，都不能直接产生 `TRANSFER_CANDIDATE`。正向方法效用仍需要结果前冻结的材料处理差异，而不是新增 outcome cell 或更完整模板。

## 12. 实施边界

新增 `scripts/judgment_training_curriculum.py` 负责：

- 四轨课程验证和状态；
- 八类能力覆盖；
- company-cluster 独立计数；
- 已知结果候选的 Teaching 路由；
- Comparative 的 claim-scoped 约束；
- 下一训练动作建议。

现有组件分工不变：

- `historical_role_isolation.py` 负责 selector/forecaster packet 与真实 one-shot 输入收据；
- `historical_judgment_first_draft.py` 负责 Blind 第一稿的判断优先合同；
- `judgment_training_program.py` 负责严格评价、holdout、方法冻结和发布控制；
- J2/J3/J4 adapter 不因本课程重构而改变。

## 13. 下一阶段执行顺序

1. 执行已登记的中国外运 Blind：fresh role 只读 FY2021--FY2023，冻结完整第一稿后才向 custodian 开放 FY2024；
2. 以异质机制三联组策展 Teaching：一个同构案例、一个异行业迁移案例、一个 near miss；
3. 每完成 3 个新 Teaching，执行 1 个新的 historical Blind；
4. Blind 累积到 4--6 个后，从尚未参与训练的公司簇冻结第一批 4 个 Historical Holdout；
5. 达到 20 个 Teaching、8 个 Blind 前，不把精力转向新的 prospective 样本或大规模 Comparative；
6. 只有 Blind 暴露出材料、可重复的处理错误时，才提出窄规则；规则必须在 holdout 通过后才能谈迁移。

下一条实际工作不是再写架构，而是执行第二个 Blind，并同时策展下一组三个 Teaching。

## 14. 研究依据与适用边界

- [Ericsson, Krampe & Tesch-Römer (1993)](https://doi.org/10.1037/0033-295X.100.3.363) 支持以有目标、可反馈的练习改进具体表现；它不证明训练时长或案例数自动产生投资能力。
- [Gentner, Loewenstein & Thompson (2003)](https://doi.org/10.1037/0022-0663.95.2.393) 与 [Loewenstein, Thompson & Gentner (1999)](https://doi.org/10.3758/BF03212967) 支持通过结构比较抽象可迁移机制，而不是孤立记忆案例；谈判实验的效应量不能迁移为企业研究的成功率。
- [Kornell & Bjork (2008)](https://doi.org/10.1111/j.1467-9280.2008.02127.x) 支持交错不同范例促进类别归纳，并提醒主观流畅不等于学习；它不决定 Turtle 的 `3:1` 比例。
- [Karpicke & Roediger (2008)](https://doi.org/10.1126/science.1152408) 支持反复检索/测试优于只重复阅读，因此课程必须穿插 Blind，而不是连续阅读 worked examples。
- [Aamodt & Plaza (1994)](https://doi.org/10.3233/AIC-1994-7104) 的 `Retrieve -> Reuse -> Revise -> Retain` 支持案例库循环；Retain 只形成课程资产，不自动成为正式 learning policy。
- [Kahneman & Klein (2009)](https://doi.org/10.1037/a0016755) 强调专业直觉需要足够规律的环境和可学习反馈，支持把行业/公司机制和及时结果反馈放在课程中心；它同时限制了在低规律环境中夸大能力。
- [Baron & Hershey (1988)](https://doi.org/10.1037/0022-3514.54.4.569) 支持分开当时过程与事后结果，防止 Teaching 结果倒灌为当时可知事实。
- [Hernán & Robins (2016)](https://doi.org/10.1093/aje/kwv254) 支持 Comparative 的 time zero、intervention、comparator、outcome 和 follow-up 边界；这些条件只属于相对因果实验室。

这些研究支撑训练结构，不构成任何公司、行业、估值或买点的投资证据。20--30、8--12、4--6 和 `3:1` 都是当前工程与研究成本下的可修订起点，不是科学认证阈值。
