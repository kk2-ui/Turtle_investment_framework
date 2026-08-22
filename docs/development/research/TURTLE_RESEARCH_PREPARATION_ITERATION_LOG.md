# 研究前准备：方法与流程迭代日志

状态：`PREPARATION_COMPLETED / METHOD_EXPERIMENTS_ACTIVE / P01-P77`  
目的：记录流程本身如何被发现、检验和修改。这里不记录公司结论，也不把格力作为正式研究对象。

## 迭代 P-01：研究是否被报告生产牵引？

### 原始问题

此前资料、CJO 和回测接口较多，容易让“能否完成报告/冻结”取代“是否形成更好的经营判断”。这会使研究者优先补字段、补格式和补可发布性，而不是寻找竞争机制的分歧。

### 干跑检验

将当前流程从一个未知公司开始推演：若一开始缺行业数据、没有估值和没有结论，研究能否仍输出有价值的下一步？原流程的许多语言会把重点拉回报告、黄金状态和 CJO。

### 修改

- 设立研究优先的方法大纲和操作流程；
- 将行业机制图、公司状态编年、竞争机制实验、分歧地图、类比和学习记录定义为研究主产物；
- 将报告、估值、价格和行动明确后置；
- 将旧的前瞻研究日志标为历史发现，避免它在后续检索中重新把工作拉回报告。

### 结论

`RETAIN_WITH_BOUNDARY`：冻结工具仍有用，但只在判断形成后保护事前记录，不能排在研究之前。

## 迭代 P-02：持续深挖一家公司是否会被误称为“迭代”？

### 原始问题

公司资料天然没有尽头。若每次新年报、新闻或旁证都能继续添加，研究会积累故事但不积累可迁移能力。

### 干跑检验

用格力作为压力测试：即使继续取得更多渠道、现金或管理层材料，若它们不能改变方法、机制边界或可观察顺序，研究仍会无限扩张。

### 修改

- 定义迭代最小单位为“方法假设的有界实验”，而不是一个公司或一批报告；
- 强制每轮填写停止条件和跨对象复验；
- 设置 `REPLICATION_PENDING` 生命周期；
- 在项目登记簿中将格力设为 `PAUSED_AS_METHOD_TEST_BENCH`。

### 结论

`RETAIN`：当前规则把“多读同一公司”与“方法更新”分开；只有未来迁移复验才能把发现升级为方法。

## 迭代 P-03：流程是否真的在训练判断力？

### 原始问题

“有机制图、有反方”不自动意味着判断能力提高。若没有事前/事后的验证，流程只是在制造更精致的研究语言。

### 干跑检验

问一个直接问题：若两份研究都写得流畅，流程如何判断哪份在未来更有用？此前答案过于依赖回测引擎或报告完成状态，未区分经营机制判断和投资回报。

### 修改

- 明确五种判断能力：问题界定、机制辨别、测量辨别、校正和迁移；
- 每张迭代卡必须指定本轮训练哪一种能力，以及能新增作出的区分；
- 建立判断回测：PIT 冻结竞争机制 → 早期经营信号 → 终局经营结果 → 跨对象复验；
- 明确股价/回报只结算独立投资层，不能证明公司判断正确。

### 结论

`RETAIN_WITH_FUTURE_TEST`：方法现在有可验证路径，但尚无独立 episode，不能声称已经提升了判断力。

## 迭代 P-04：论文是否被正确转化为训练，而非书单？

### 原始问题

引用论文容易变成权威装饰；不同学科的实验结论也不自动适用于公司研究。

### 干跑检验

对每条论文命题追问：它具体训练哪种判断能力？在 Turtle 中可做的最小实验是什么？若无效时如何认定？

### 修改

建立[判断力训练实验](TURTLE_JUDGMENT_TRAINING_EXPERIMENTS.md)，将多重解释、过程追踪、快速反馈、冻结预测、结构化类比和结果偏见防护逐一对应到小实验、结算与失败条件。

### 结论

`RETAIN_WITH_SCOPE_LIMIT`：论文只提供方法假设；必须在历史 PIT 回放与真实前瞻观察中检验，不能从地缘政治、心理实验或其他行业直接外推有效性。

## 迭代 P-05：最小流程干跑

### 假设情境（非真实公司）

一家成熟耐用消费品公司出现“单一渠道相对位置走弱、产品毛利稳定、第三方数据口径不完整”的组合。研究者只有公司年报、两份未带 query 的行业转述和一个历史案例。

### 按流程推演

1. 迭代卡要求先选目标能力：机制辨别和测量辨别，而不是“判断公司好坏”。
2. 来源观察卡把年报科目列为 `FACT`，行业转述列为 `SENSOR`，案例列为 `HYPOTHESIS`；没有任何材料自动变成结论。
3. 机制实验要求“渠道重配”和“竞争恶化”都解释共同事实，并各自写不同的后续观察。
4. 红队发现全渠道、价格带、交易点和库存都未知；两方仍无法分辨。
5. 学习复盘的正确输出是 `INSUFFICIENT_TEST`：新增一个原始行业面板的资料请求，并停止继续写公司故事。

### 审阅结果

干跑没有生成报告、概率、估值或股价解释，且能在数据不足时给出停止与下一项资料请求。这符合中心目标。

### 剩余风险

模板数量可能让探索变得行政化。操作流程因此规定：每个会话只做一种工作、每次实验最多改变一个主要方法部件；探索材料可只用来源观察卡，只有被选入实验的材料才需要完整档案。

## 当前准备状态

| 项目 | 状态 | 尚不声称 |
|---|---|---|
| 研究优先的目标与边界 | `READY` | 已形成任何公司结论 |
| 有界迭代、停止和迁移复验 | `READY` | 已完成跨公司方法验证 |
| 判断力的定义与经营回测 | `READY` | 已提高准确率或校准 |
| 论文→实验→失败条件 | `READY` | 论文命题已适用于投资 |
| 正式研究选样与执行 | `ACTIVE` | 判断方法已普遍有效、已形成公司结论或准确率 |

## 迭代 P-06：历史回放会不会仍被后见之明污染？

### 原始问题

有了冻结和回测语言仍不够：如果研究者在选择样本、写反方或设计信号前已经知道后续经营/价格结果，方法会被悄悄调成“解释已知结局”。

### 干跑检验

以一个已广为人知的历史成功或失败案例推演。若流程没有要求结果防火墙，研究者仍可用后来的事实选择机制、阈值和类比，随后把结算误写为预测验证。

### 修改

- 操作流程新增 `cutoff 前 source package → frozen research card → cutoff 后 outcome package` 的信息隔离；
- 迭代卡新增结果防火墙与公平基线字段；
- 已知结果的对象降为 `OUTCOME_SELECTED_TRAINING_ONLY`，只可练模板或生成反例。

### 结论

`RETAIN`：这不是额外审计，而是判断回测能否成立的最小条件。若无法隔离信息，正确输出是 `INSUFFICIENT_TEST`，而不是漂亮复盘。

## 迭代 P-07：流程会不会反而变成研究官僚主义？

### 原始问题

研究准备新增了迭代卡、来源卡、机制实验和复盘。若每读一条材料都必须填完整表，研究者会把精力花在表格而不是判断上。

### 干跑检验

以一个新问题开始推演：研究者是否能在没有公司结论、没有完整数据的情况下，用最少步骤识别“应继续还是停止”？若不能，流程就是负担而非训练。

### 修改

- 操作流程新增六步最小闭环；
- 探索材料只需来源观察卡，只有被选入实验的材料才进入完整档案；
- 迭代卡新增“经济边界”和“失败后下一步”，防止抽象方法实验脱离判断目标；
- 机制实验新增共同终局/时间尺度及非嵌套分歧要求，防止形式化的伪反方。

### 结论

`RETAIN_WITH_MINIMALISM`：流程的复杂度只服务于产生新判断、阻止误判或决定停止。不能做到其中之一的字段将来应删除，而不是继续增加。

## 迭代 P-08：案例阅读会不会只增加熟悉感，而不增加公司经验？

### 原始问题

书籍和历史公司案例极其有价值，但若只记住成功公司、名家结论或故事终局，经验会变成“见过很多案例”的错觉，不能迁移到未知公司。

### 干跑检验

将一本案例或一份历史报告直接放入未来公司判断，发现它没有强制要求当时状态、竞争机制、结果防火墙、断裂条件或近失效案例；这会把结果已知的故事错当训练样本。

### 修改

建立[公司经验积累协议](TURTLE_COMPANY_EXPERIENCE_ACCUMULATION_PROTOCOL.md)：将探索笔记、episode 候选、合格学习 episode 和结果已知教学案例分开，并规定经验只能迁移状态向量、机制条件、断裂条件和信号顺序。

### 结论

`RETAIN_WITH_SLOW_ACCUMULATION`：公司经验会慢于报告阅读，但能保留失败案例和真正的迁移条件；样本不足时不输出概率。

## 迭代 P-09：噪声资料会不会被误升级为判断？

### 原始问题

即使流程把来源标为 `SENSOR`，若没有声明其最多能支持到哪一层，研究者仍可能把供应商转述、跨交易点行业数或一次性现金变化写成竞争机制的早期验证。

### 干跑与发现

用[干跑 01](TURTLE_WORKFLOW_DRY_RUN_01.md)的合成耐用消费品情境测试。旧模板无法阻止把无原始 release 的线上份额转述、未定义的行业“内销”或受限资金释放升级为 H-A/H-B 或 owner-cash 信号。

### 修改

- 来源卡和机制实验新增 `evidence_ceiling`；
- 将未知拆为五种有行动含义的原因；
- 操作流程明确只有 `SETTLEMENT_ELIGIBLE` 能进入冻结信号。

### 复跑结论

修改后正确输出为 `UNDIFFERENTIATED / ACQUISITION_REQUIRED`，而不是概率、中心路径或公司叙事。`MODIFY → RETEST_PASSED`；仍需在真实但结果隔离的 PIT episode 中复验。

## 迭代 P-10：不同措辞会不会伪装成竞争判断？

### 原始问题

主/反方即使数值不同，也可能在大多数结果区间同时成立。若不显式列出何种结果只支持一方，历史结算会沦为事后选择解释。

### 干跑与发现

用[干跑 02](TURTLE_WORKFLOW_DRY_RUN_02.md)测试主方 `≥ -5%`、反方 `≤ -3%` 的预测。在 -4% 情况下两方都成立；旧模板没有迫使研究者承认它是非诊断结果。

### 修改

- 机制实验新增 `A_ONLY / B_ONLY / MIXED / NEITHER` 结果区域；
- 没有 A-only 与 B-only 的信号禁止冻结；
- 操作流程补上五种未知原因对应的具体研究动作。

### 复跑结论

干跑中 -4% 必须结算为 `MIXED`，不为任一机制加分。`MODIFY → RETEST_PASSED`；该逻辑约束将来还需接受真实 PIT 资料的可操作性检验。

## 迭代 P-11：经典案例会不会伪装成可迁移经验？

### 原始问题

书籍案例即使已避免直接迁移估值和结局，若没有明确 source case 的结果可见性、结构匹配、断裂条件和近失效反例，仍会被用作目标公司的叙事背书。

### 干跑与发现

用[干跑 03](TURTLE_WORKFLOW_DRY_RUN_03.md)测试“高端品牌+服务网络”的著名成功案例。旧流程没有最小卡片来阻止它直接支持一个有相似表象、但渠道交易点和竞争结构未知的目标公司。

### 修改

- 增加结构化类比与近失效卡；
- 强制声明 source case 的结果可见性、机制层匹配、断裂条件和近失效案例；
- 结果已知案例只能生成问题，不可代替目标公司的机制观察。

### 复跑结论

合成目标公司的正确输出为 `ANALOGY_NOT_TRANSFERRED / ACQUISITION_OR_MECHANISM_TEST_REQUIRED`。`MODIFY → RETEST_PASSED`；其迁移效力仍待真实、结果隔离 episode 验证。

## 迭代 P-12：稀疏经验会不会被伪装成精确概率？

### 原始问题

判断训练需要不确定性表达，但小样本、书籍案例或主观信心不能提供可校准概率的含义。若流程不设入口，研究者会以 60%/40% 取代尚未分辨的机制。

### 干跑与发现

用[干跑 04](TURTLE_WORKFLOW_DRY_RUN_04.md)测试只有教学案例和行业转述的新问题。旧迭代卡没有要求概率来源，仍可能允许一次结果后报告看似量化的 Brier score。

### 修改

- 迭代卡新增 `DIRECTION_ONLY / RANGE / PROBABILITY / NO_FORECAST` 的选择；
- 概率强制说明独立样本/频率、事件定义和校准计划；
- 验证协议和操作流程明确单一 outcome 不结算概率校准。

### 复跑结论

合成问题只能输出 `NO_PROBABILITY` 和竞争信号设计。`MODIFY → RETEST_PASSED`；未来若形成合格 episode 队列，才研究概率是否有增量价值。

## 迭代 P-13：多来源/多 agent 会不会伪造独立证据？

### 原始问题

并行阅读可以提高效率，却可能让同一供应商图、同一公司披露或同一访谈被以多份报告、不同页码和多人意见的形式重复计数。

### 干跑与发现

用[干跑 05](TURTLE_WORKFLOW_DRY_RUN_05.md)测试三份共享供应商图的报告、两次同年报阅读与一项交易点不同的行业摘要。旧模板没有强制 lineage identity，容易被误读为五项支持。

### 修改

- 来源卡新增 `lineage_id`、最原始来源和独立性依据；
- 机制实验要求列明独立来源谱系和未解决依赖；
- 操作流程明确多 agent 不投票、不平均、不提高概率。

### 复跑结论

三份转述折叠为一个 `MECHANISM_DISCOVERY` 观察，输出为 `UNRESOLVED_DEPENDENCE / UNDIFFERENTIATED`。`MODIFY → RETEST_PASSED`；后续真实协作需检验来源谱系记录的可复原性。

## 迭代 P-14：动作后出现结果，会不会被误读为因果？

### 原始问题

公司研究最容易将“管理层做了动作，之后收入/利润改善，以及管理层解释该动作有效”压缩为因果结论。这会跳过共同冲击和替代机制。

### 干跑与发现

用[干跑 06](TURTLE_WORKFLOW_DRY_RUN_06.md)测试渠道数字化后收入恢复、同时存在补贴与供给冲击的情境。旧来源卡不能标明动作、结果和归因各自的机制角色。

### 修改

- 来源观察卡新增 `STATE / ACTION / OUTCOME / CAUSAL_ATTRIBUTION / FORECAST`；
- 新增对 A/B 的诊断性身份；
- 操作流程明确行动链、因果解释和 outcome sequence 的不同地位。

### 复跑结论

动作仅结算为 `ACTION_COMPLETE`，因果机制仍为 `UNVERIFIED`。`MODIFY → RETEST_PASSED`；真实 PIT 回放将检验该分离是否降低事后因果幻觉。

## 迭代 P-15：证据不足时，方法成功会不会被误读为公司结论？

### 原始问题

一项研究方法可以成功阻止错误推断，但研究对象本身仍然不可判别。若复盘只写一个“裁决”，研究者可能把 `RETAIN` 误读为“公司判断已经形成”。

### 干跑与发现

用[端到端干跑 07](TURTLE_WORKFLOW_DRY_RUN_07_END_TO_END_INSUFFICIENT.md)串联迭代卡、来源观察、机制实验、红队和复盘。方法 B 成功阻止了跨口径推断，但没有取得任何可结算的 A-only/B-only 信号。

### 修改

- 学习复盘拆分“方法裁决”和“对象研究状态”；
- 操作流程明确两者不能互相推出；
- `ACQUISITION_REQUIRED` 时只能给一项最高信息价值的资料请求并停止。

### 复跑结论

方法为 `RETAIN`，对象为 `UNDIFFERENTIATED / ACQUISITION_REQUIRED / NO_COMPANY_CONCLUSION`。`MODIFY → RETEST_PASSED`：流程奖励正确停止，不奖励无依据的公司结论。

## 迭代 P-16：合格的早期信号会不会被过度解读？

### 原始问题

流程不仅要能在证据不足时停止，也要能在来源和竞争信号合格时正确冻结、结算；但一个早期信号支持某条箭头，不等于公司终局或投资结论已经成立。

### 干跑与发现

用[端到端干跑 08](TURTLE_WORKFLOW_DRY_RUN_08_END_TO_END_ELIGIBLE.md)模拟同 provider、同定义、结果隔离的全渠道价格带信号。旧状态没有表达“早期已结算、终局仍未到期”的中间阶段。

### 修改

- 学习复盘新增 `EARLY_SIGNAL_SETTLED / TERMINAL_PENDING`；
- 操作流程明确早期胜负只更新一个机制箭头，不能升格为公司终局、估值或投资结论。

### 复跑结论

早期信号可结算为 `SUPPORTS_PRIMARY`，对象仍为 `EARLY_SIGNAL_SETTLED / TERMINAL_PENDING / NO_COMPANY_CONCLUSION`。`MODIFY → RETEST_PASSED`：流程在证据不足和合格早期信号两端均避免过度结论。

## 迭代 P-17：完整公司工件会不会吞没有界机制实验？

### 原始问题

完整 `COMPANY_JUDGMENT_ONLY` 路径适合成熟的公司研究：它要求竞争、单位经济、现金转换和资本配置四层同时存在。若把一个只训练“客户频次是否延续”的真实前瞻实验也塞入该路径，研究者会为尚未研究的现金、资本配置或报告章节创建无关对象，甚至诱发伪精确的公司判断。

### 真实压力测试

R-05 的 Starbucks 北美候选已经有一个清楚、结果未知的经营问题、同口径公司 KPI、竞争机制和 6/12 月结果窗口。将它推进完整公司工件会改变研究问题：工作量从“交易量持续性”转为补全全公司 driver，且这些补项不能提高本轮对 H-A/H-B 的判别力。

### 修改

- 增加[研究前瞻冻结附件](../../../templates/research_forward_freeze.md)，只冻结有界方法实验所需的当前事实、竞争机制、A-only/B-only 信号、来源和结算规则；
- 附件必须建立在已物化的截止日前 source package 之上，结果只能追加到 `07_settlement.md`；
- 明确附件不产生公司总判断、正常盈利/现金、估值或投资动作；完整公司研究仍保留原有 CJO 路径。

### 复跑结论

R-05 已用此附件冻结为真实前瞻 episode，未虚构现金、资本配置、价值或价格结论。`RETAIN_WITH_DUAL_LANE`：研究的最小单位可以比公司报告窄，但不能比可结算机制问题更宽。下一步等待真实结果，并用非餐饮连锁对象复验；不得用更多 Starbucks 或格力阅读替代反馈。

## 迭代 P-18：同期的名家原件会不会仍被误收为可训练案例？

### 原始问题

P-08 已经把书籍和结果已知案例降为路由/教学，但仍有一个危险捷径：一份确实来自当时、作者也确实作过投资决定的原件，容易被误当成带有可结算机制判断的外部 episode。

### 控制筛查

以 Berkshire 的 1988 Coca-Cola 持仓披露为压力对象，只读取[当年标记的董事长信](https://www.berkshirehathaway.com/letters/1988.html)，不读取任何后续经营结果。原件足以显示真实持仓与长期持有意图，但页面未给出可核验发表日，且没有目标公司的经营机制、最强反方、指标、方向或窗口。

### 修改

- 新增 [R-03 外部历史判断档案 intake](R03_ARCHIVED_EXTERNAL_EPISODE_INTAKE.md) 与类比卡中的原始判断/独立结果字段；
- `ARCHIVED_EX_ANTE_EXTERNAL` 必须同时有时间边界、原作者公司机制、可结算谓词和独立结果链；缺一项即降为 `TEACHING_ONLY`；
- 若原件在机制/指标门已失败，不再为了已知结局继续采集结果资料；这避免用结果修补原判断。

### 复跑结论

该控制对象被裁决为 `TEACHING_ONLY / NOT_ARCHIVED_EX_ANTE_EXTERNAL`。根因是 `REASONING + DATA_COVERAGE`：原件证明行动但不证明可结算的公司判断。若放宽该门，经济影响是会把知名投资者的持仓和终局成功伪装成品牌持续性、竞争持续期或现金质量的经验，从而虚增未来公司判断的确信度。

`RETAIN_WITH_STRICT_INTAKE`：外部档案仍可帮助发现结构条件，但它必须先经受“是否真的写下可被结果否定的经营判断”的筛查。下一步仅筛选有原始机制/谓词的候选；没有则保留 `QUESTION_ONLY`，不以增加案例数替代。

## 迭代 P-19：单条 learning note 会不会被写完即遗忘？

### 原始问题

现有结算反馈已经要求每条到期信号写 `next_research_change`、根因和失败位置，但这些 note 是逐条保存的。没有跨实验、跨公司簇的复盘入口，系统会“记录教训”却无法判断同一类取证、机制或传导错误是否反复出现，也无法安排下一轮迁移复验。

### 工件审查

`judgment_learning.py` 能建立并 append-only 保存单条 note，但此前没有读取一组 note 的方法复盘产物。这个缺口属于 `MODEL + REASONING`，不是数据量不足：继续读格力或增添报告只会产生更多孤立笔记。

### 修改

- learning note 现在强制写入 `experiment_id` 和 `company_cluster_id`；
- 新增 `build_method_feedback_review(...)`，按失败位置汇集原 note 的实验、公司簇、根因与已承诺的下一步改变；
- 单公司簇只能得到 `SINGLE_COMPANY_ACTION_ONLY`；至少两个公司簇才开启人工 `MULTI_COMPANY_METHOD_REVIEW_REQUIRED`；二者都不计算准确率、概率或总分。

### 结论与后续验证

`MODIFY / TESTED_ON_FIXTURES`：定向测试覆盖单公司不泛化、跨公司簇只触发复盘而不评分，以及缺失实验/公司簇身份的 note 被拒绝。它让未来 R-05/R-06 到期时能形成可执行的研究队列，而不是仅写一段复盘。尚无真实到期前瞻 note，故不能声称该汇总已经提高判断力；届时要检验的是它是否真的导致下一轮方法/模板/样本选择发生可追溯改变。

## 迭代 P-20：source package “可读”是否会掩盖研究者其实没读过冻结依据？

### 原始问题

R-05/R-06 的截止日前 source package 均已物化并通过 `REVIEWABLE` admission，但早期 attestation 的 `read_count=0`。这能证明来源可以被读取，不能证明冻结附件实际依赖的原件已经在 PIT 边界内被读取；若不补此差异，后续的“冻结”会只是资料包冻结，而不是研究判断冻结。

### 干跑与发现

PIT runner 此前没有命令行入口将某一个允许的 source ID 写入正式读取审计。于是研究者只能手工读取文件，而 attestation 对“本轮研究实际读了哪些一手原件”保持空白。根因是 `ACQUISITION_MODULE + REASONING`，不是资料页数或公司覆盖不足。

### 修改

- PIT runner 新增可重复的 `--read-source SOURCE_ID`；它在写 attestation 前读取指定的截止日前、已允许来源，并记录 `ALLOW` 或 `DENY`；
- 前瞻冻结协议改为：附件所引 source ID 必须逐一出现在 attestation 的 `ALLOW` 记录中，`read_count` 与引用集合相符；
- R-05 的两份 Starbucks 原件、R-06 的 Walmart HTML/PDF 均已按该方式重跑，分别得到 `read_count=2`、两个 `ALLOW`、零越界读取和零拒绝。

### 结论与后续验证

`MODIFY / RETEST_PASSED`：定向测试覆盖明确允许来源的读取与未来/未允许来源的拒绝，R-05/R-06 已通过真实包复跑。它提升的是“事前证据边界可复查性”，不提高任何机制命题的真值，也不把两项 `NO_PRIMARY` 探针升级为公司判断。未来每个结果期 source package 也须先通过相同读取审计，才能写入 `07_settlement.md`。

## 迭代 P-21：可结算的信号会不会被误称为“当时选对了机制”？

### 原始问题

R-05/R-06 已经能让 H-A/H-B 对未来交易量给出不同的结果区域，但它们没有 cutoff 前的方向性证据使研究者合理选择任一主路径。若未来交易量与 H-A 一致，研究者很容易把“信号支持一条箭头”写成“我们当时判断正确”；这会把诊断能力和选择能力混为一谈。

### 控制干跑

以 R-05 做不读取结果的拟升级控制。Q3 正交易量是双方共同事实；Investor Day 是 H-A 的候选归因，不是 H-A 相对 H-B 的方向性事实；Q3 利润率又同时受多个共同因素影响。即使强行选择 H-A，它对下一期交易量 `>0%` 的预测也和朴素延续基线完全相同。因此没有合格选择依据，也没有公平的预测差异。

### 修改

- 前瞻冻结模板先冻结实际考虑过的候选机制集合及合并/排除理由，再将选择依据改为逐行的事实/谱系/方向性/失真降级表；不再允许一个自由文本“我为什么选它”，也不允许结果期补称未列出的旧机制；
- 选择 episode 强制写出基线的输入、预测区域和与主路径的差异；无法产生差异即退回 `MECHANISM_SIGNAL_PROBE / NO_PRIMARY`；
- 新增 R-05 [选择升级控制](experiments/R-05_prospective_operating_feedback/08_selection_upgrade_control.md)，明确拒绝其升级而不读取结果。

### 结论与后续验证

`RETAIN_WITH_SELECTION_GATE`：这道门防止把事后连续性误认作事前机制选择力。根因是 `REASONING + MODEL`；若忽略它，经济影响是会虚构对客户持续性、竞争持续期和正常盈利的因果把握，进而过早影响公司判断。该控制不是证明方法提高了选择准确性；它只证明流程能拒绝一次没有依据的选择。下一次 selection episode 必须在冻结前具备不重复共同事实、对 H-A/H-B 有方向性含义的证据，以及非同向基线；冻结时只验收 `SELECTION_ADMITTED / NO_PRIMARY`，结果到期后才单独记录该案支持所选/反方/混合/不具诊断性。多个独立、同定义且有事前评分规则的案例之前，禁止输出选择准确率或方法优越。

## 迭代 P-22：严格的外部档案 intake 会不会只剩“名家全拒绝”，无法积累结构经验？

### 原始问题

P-18 的 Berkshire/Coca-Cola 控制正确拒绝了只有持仓和长期意图的名家原件，但一个准入门若只能拒绝，仍没有证明它能区分可用与不可用的历史经验。

### 结果隔离筛查

只读取 2015 年 4 月的两份 SEC 原件：Trian 对杜邦的投资者陈述明确了成本冗余、增长/利润率弱与 Q2–Q4 核心经营利润约需增长 `29%` 的条件桥；杜邦同期原件提供规模、研发、客户关系、运营重构与拆分协同损失的反方。两者均早于潜在 2015 经营结果。此轮未读取任何 Q2/Q3/全年业绩、企业重组或证券结果。

### 修改

- 新增 [Trian/杜邦 pre-outcome intake](experiments/R-03_archived_external_intake/01_trian_dupont_2015_preoutcome_intake.md)，记录原作者的短窗口谓词、反方、`UNKNOWN` 与结果防火墙；
- 2015 Q2/Q3/全年公司一手主件已封装为独立的 raw-only outcome package（无 reader text、无数值提取），结果链仍被限制在这三个短窗口披露；日后先验证“核心经营利润”、成本节约与业务口径可比性；
- 杜邦的 2020 长期收入目标不进入本轮，因为之后实体重组会构成 `MEASUREMENT_MISMATCH`，不能用长终点为任何机制背书。

### 结论与后续验证

`RETAIN_WITH_METRIC_RECONSTRUCTION_GATE`：准入门能接纳带有机制、同期反方和可读短窗口谓词的档案，而不是把名声当门槛；但结果期进一步证明，原作者的谓词本身也必须在**读取结果前**映射到连续的官方指标、调整和禁止替代项。Trian 的约 `29%` 条件桥无法以 Q2/Q3/FY 不同 PTOI/segment operating earnings 口径重建，故为 `MEASUREMENT_MISMATCH`；成本节约只是共享前提，农业弱势仅局部支持一条理由。根因是 `DATA_COVERAGE + REASONING`：若强行把片段拼成完整机制，会材料性扭曲正常盈利、资本配置以及整合/拆分的结构经验。该外部对象关闭为 `NO_COMPANY_CONCLUSION`，只沉淀 metric-reconstruction contract；它不是 Turtle 判断能力证据。

## 迭代 P-23：计量重建合同是否只适用于外部档案，而遗漏真实前瞻实验？

### 原始问题

R-03 已将“原作者谓词 → 官方结果指标”的映射写入档案 intake，但如果实时前瞻实验只冻结指标名称、阈值和来源域名，研究者仍可能在结果期发现原定义未披露，转而用收入、利润或管理层解释代替。那会使外部历史材料反而比 Turtle 自己的前瞻实验更严格。

### 干跑与发现

R-05/R-06 已冻结为 legacy experiment，不能事后添加字段或回写其判断；它们原本直接指定同口径的公司 `Transactions`，并已有定义变更即停止的规则。真正缺口在于未来实验模板没有要求研究者在冻结前明确“哪份官方披露、哪一标签、允许何种转换、绝不允许什么替代”。这属于 `REASONING + ACQUISITION_MODULE`，不是再读更多公司的问题。

### 修改

- [研究前瞻冻结附件](../../../templates/research_forward_freeze.md)新增每条 signal 的结果期计量连续性合同：冻结谓词、预期官方标签/文件、允许转换、禁止代理与口径变化的停止动作；
- 操作流程与判断验证协议将该合同列为未来前瞻冻结的必要内容；
- R-05/R-06 保持原冻结字节和 legacy 身份，不用后来发现的规则补写或重判。

### 结论与后续验证

`RETAIN_FOR_FUTURE_EXPERIMENTS`：从下一项新实验起，未来结果即使方向看似相符，也只有满足原映射才能结算。若缺映射，正确结果是 `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`，不是“换个相近 KPI”。经济影响是防止将不可比经营数据误传为持续性、正常盈利或资本配置判断；这并不表示 R-05/R-06 已经通过了新门，二者仍只按冻结时的规则等待真实结果。

随后发现：仅有模板仍会让完整 CJO 的 R-07 选择学习绕过该门。故最小生产修复已加入：仅 `SELECTION_ADMITTED.selection_forward_judgment_ids` 必须携带可核验的 `metric_reconstruction_contract`；Phase 10 再次校验，结算 observation 的官方标签/locator/文件范围必须匹配，定义漂移在 feedback 中固定为 `NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH`。普通 CJO、`NO_PRIMARY` 和历史冻结不追溯阻断。定向直接回归覆盖缺合同、相近 KPI、label/locator 不符及漂移分轨；均通过。这个改动让飞轮的“冻结 → 结算”不再依赖研究者事后的文字自律。

## 迭代 P-24：不同的基线阈值会不会凭空制造“主机制选择力”？

### 原始问题

R-07 的实时官方筛查刻意没有冻结任何对象。Lululemon 的北美全价销售环比改善、Target 的跨渠道/跨品类增长都初看支持“修复/组合改善”，但最强反方同样能够预期这些观察；把下一期可比销售写成 `>-6%` 或 `>+3.8%`，只会先制造一个不同于延续基线的数字，再倒推它表示机制。Nike 的批发增长/Direct 下滑也同样不能区分“渠道重置”与“需求弱化/渠道转移”。

### 红队审查

现有 `SELECTION_ADMITTED` 已检查来源谱系、共同事实排除、主/反场景和不同基线，但仍可能让一条表面支持主方的事实与无关的终局 FJ 或单边阈值并列出现。根因是 `REASONING + ACQUISITION_MODULE`：生产链没有要求形成可解析的 `当前证据 → 主机制已验证箭头 → 主/反双方都可赢的早期 FJ → 同一竞争测试阈值` 链。若忽略它，后来命中的延续或任意阈值会被错误归因为研究者理解了竞争持续期，继而污染对正常盈利、单位经济和资本配置的后续学习样本。

### 修改

- 选择证据必须引用其对应的入选前瞻判断、主路径的已验证因果箭头和该 FJ 的领先阈值；
- 该阈值必须同时属于主/反机制链，并以该 pair 的竞争测试为判别对象；入选 FJ 必须是这个 pair 的 `EARLY_MECHANISM` 分叉，而不是一个无关终局预测；
- 每个入选 FJ 至少由一条上述选择证据支撑。模板保留“为什么不是任意设定”的主研究者论证，但不新增只能验证非空的 `threshold_derivation` 自由文本字段。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：生产 gate 已实施并覆盖移除箭头证据、引用未验证主箭头、选择终局 FJ、双方没有共同 `TESTABLE` 早期信号和阈值仅属于一方等失败路径；普通 CJO 与 `NO_PRIMARY` 回归保持通过。它不是试图让程序裁决经济因果；它只阻断无关证据、无关终局、单边阈值和跨 pair 阈值被包装成选择学习。主研究者仍须判断箭头的经济意义，不能把引用图或不同预测本身视为机制导出。R-07 的三个 `NO_PRIMARY` 案例与 P-23 的结果期计量结算不受影响。只有通过这一冻结时门后，未来结果才有资格进入“选择学习”；它仍不构成一次准确率或方法优越证据。

## 迭代 P-25：如何防止“同一家公司还可以再读”取代跨对象的判断训练？

### 原始问题

格力与任何资料丰富的公司都能无限产生新材料。若研究对象按材料量、熟悉度或已知精彩结局进入，得到的是便利样本：同一公司内相互相关的事实会被误当成机制外部效度，近失效反例也可能在看到结果后才被挑选出来。

### 文献与设计

小样本选案必须先服务于明确的推断任务，而非资料可得性（[Seawright & Gerring, 2008](https://journals.sagepub.com/doi/10.1177/1065912907313077)；[Beach & Pedersen, 2012](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2108908)）；理论抽样与复验提供机制信息量，但不产生频率结论（[Eisenhardt, 1989](https://journals.aom.org/doi/abs/10.5465/amr.1989.4308385)）；按已知 outcome 选案会扭曲推断（[Geddes, 1990](https://www.cambridge.org/core/journals/political-analysis/article/how-the-cases-you-choose-affect-the-answers-you-get-selection-bias-in-comparative-politics/05E854AA55C1BF090B56CEC73ACEFC6B)）。据此，Turtle 将一轮最小化为 `1 + 1 + 1`：一个填补空白机制状态格的主对象、一个只反转上游中介而保持其余状态相同的近失效对象、一个保持机制叉而只改变外部边界条件的复验对象。

### 修改

- 在既有 `case_selection_register` 加入显式 opt-in 的 `judgment_flywheel_sampling`，而不新建平行案例库；
- 一个 batch 必须恰有 `FOCAL / NEAR_MISS / BOUNDARY_REPLICATION` 三个角色、三家不同公司，且都为 `PIT_PRE_OUTCOME + INCLUDED`；
- 近失效与 focal 在所有已声明状态向量中只允许 `upstream_mediator` 不同且须声明 `OPPOSITE`（九项基础维度只是最低集合）；边界复验也与 focal 保持其余所有已声明状态相同、只改变 `boundary_condition`；价格、回报、实际结果和资料可得性评分被拒绝为抽样字段；
- 每家公司默认只持有一个 active episode ticket；新资料只有进入未覆盖的机制域 × 状态 × 竞争叉、并有新预测、反方、基线和同口径结果合同，才可重开。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：完整三对象批次可冻结；缺角色、同公司、非 PIT 前 entry、近失效的任一非中介（包括额外声明）状态不同、边界复验的任一非边界状态不同、未链接 focal 或边界条件未变均被拒绝。根因是 `REASONING + DATA_COVERAGE`；若不这样做，会把同一公司深描和便利选案误传为对需求、竞争、现金转化或资本配置机制的可迁移经验。该门不声称近失效构成天然因果对照，也不判断“不同 mediator 文本”在经济上必然相反；它只保留可审查的比较结构，实质方向仍由主研究者审查。下一轮若三角配不齐，正确状态是 `BLOCKED / NO_PAIR`，而不是继续扩读格力或计算判断准确率。

## 迭代 P-26：学习 note 会不会被写完即遗忘，而不是改变下一轮复验？

### 原始问题

现有 `judgment_learning` 已将 immutable feedback 写为 append-only note，并按公司簇和失败位置生成方法复盘议程；但没有任何下一张迭代卡、前瞻冻结或样本准入工件消费 `next_research_change`。若就此宣称飞轮闭合，学习只是在记录结果，不能保证相同的机制、取证或测量错误不会在下一家公司重演。

### 审查与裁决

根因是 `MODEL + REASONING`，不是数据量或采集缺口。该问题对当前公司结论并非即时阻断，因为尚无真实到期的跨公司 note；但对“方法已经通过反馈提高判断力”的主张是材料性阻断。刻意练习要求后续任务按改进目的重新设计（[Ericsson, Krampe & Tesch-Römer, 1993](https://psycnet.apa.org/record/1993-40718-001)），而双环学习要求改变支配行动的规则，而非仅记录错误（[Argyris & Schön, 1978](https://books.google.com/books/about/Organizational_Learning.html?id=2aYOAQAAMAAJ)）。这些来源支持回写纪律，不证明 Turtle 已形成判断优势。

### 修改

不在零真实 note 时新建自动注入/评分模块。改为在下一份迭代卡增加人工可审查的 `learning application` 表：相关的 `LNOTE → method review decision → 新卡冻结前实际字段` 必须有完整 ID 链，并由独立 reviewer 判为 `APPLIED / NARROWED / INAPPLICABLE`。`APPLIED` 必须指向 source gate、状态向量、机制分叉、信号或 metric contract 的实际变动；只写“更谨慎”不成立。所有相关 note 必须在不同公司中显式处置；未处置的对象不能称为 replication。

### 结论与后续验证

`DESIGN_READY_NOT_LIVE_TESTED`：当前没有真实 `MULTI_COMPANY_METHOD_REVIEW_REQUIRED`，所以不能以 fixture 或历史改写伪造闭环 PASS。真实验收的次序是：已结算 claim → 合格 `LNOTE` → 跨公司 review decision → 不同公司新卡的 application table → reviewer 确认冻结前字段确实变化。若前两次真实应用不断暴露同一种结构性遗漏，再只针对“链接的 note 未指向实际字段”“同一公司冒充复验”“字段在 freeze 后补写”三个失败模式结构化/验证器化；此前不加自动选样、评分、价格或回报接口。

## 迭代 P-27：噪声行业来源会不会在结果期被平均，或被事后换源来裁决机制？

### 原始问题

行业 provider 的交易点、渠道、品牌/分母映射与误差边界常不相同；公司自身也未必观察得到同一对象。正确方法不是把奥维、公司和其他来源平均成“真值”，也不是因缺一块面板就停止提出机制问题。审查发现当前方向性传感器和 `UNKNOWN` 分轨已经做到这点，但数值 FJ 仅冻结 source type 与指标口径，尚未冻结“哪一个连续行业序列”——结果期仍可能从 provider A 换到 provider B，或换同 provider 的渠道/分母切片。

### 修改

仅对使用 `LICENSED_INDUSTRY_DATA` 的新冻结 FJ，加入 `licensed_industry_series_contract`：冻结 cutoff 前 source、provider/dataset、metric/semantic、geography 与产品/渠道/品牌/分母映射。它刻意**不**冻结未来 release/version/query，因此同一面板的后续发布仍可结算；不同 tuple 则为 `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`，可留下为机制压力测试，不得判主/反方胜负或取平均。`DIRECTIONAL_SENSOR_ONLY` 仍可生成问题和反方，但不能数值结算；现金、资本、价格和回报路径未放松。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：同一 AVC panel 的后续 release 即使 version/query 变化也可结算；provider、channel、brand 等 tuple 变化会被拒绝或降为非诊断；新冻结缺合同失败，旧冻结不被追溯阻断。根因是 `REASONING + ACQUISITION_MODULE`；若不修复，竞争强弱或单位经济的假阳性会污染正常盈利与永久损失学习。测量不确定性必须连同方法假设报告，而不是用来源数消除（[NIST TN 1297](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-7-reporting-uncertainty)）；不足以唯一识别的证据不应被压成一点估计（[Imbens & Manski, 2004](https://onlinelibrary.wiley.com/doi/pdf/10.1111/j.1468-0262.2004.00555.x)）。真实 R-04 仍 `BLOCKED_ON_VERSIONED_PANEL`：必须取得同一序列的原始 pre/post release 才能测试这道门，网页转述与跨供应商数字均不替代。

## 迭代 P-28：无频率依据时，系统会不会逼出伪概率？

### 原始问题

方法大纲已规定：没有独立 episode 或外部频率时只能使用 `NO_PROBABILITY`。但生产 CJO 仍继承投资路径的概率账本，强制概率集合、权重和“最高概率”中心路径；这会让研究者把尚未校准的机制判断伪装为 60/40 的量化结论。

### 修改

- CJO 新增 `NO_PROBABILITY / QUALIFIED_PROBABILITY` 两种模式；投资路径与 legacy 冻结不变；
- 前者禁止任何概率字段和“最高概率”措辞。`NO_PRIMARY` 无中心路径；选择准入已成立的对象可用 P-24 链与定性 `selection_basis` 冻结主路径；
- 后者才保留数值概率，并要求事件定义、校准计划，以及至少两个独立已结算 episode 或可追溯的外部频率；主观权重、同一公司材料、价格/回报不得充数；
- 不论模式，H-A/H-B、双边 FJ、rival/discriminator/threshold、来源、FDB 和 metric contract 都保持强制；snapshot 明记模式，避免结算时回填伪概率。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：CJO 的 `NO_PRIMARY` 与 `SELECTION_ADMITTED` 无概率路径均可冻结和投影；概率字段会被拒绝；缺资格证据或仅主观权重的 `QUALIFIED_PROBABILITY` 会失败，合格外部频率路径可通过。共 189 项定向回归通过。根因是 `REASONING + MODEL`；若不修复，虚假的信念强度会污染对竞争持续期、正常盈利和后续研究优先级的判断。此门不能自动裁决外部频率在经济上是否真正可比，主研究者仍须审阅独立性、事件定义和适用边界；在此之前坚持 `NO_PROBABILITY`。

## 迭代 P-29：行业架构的“已验证”会不会只是作者自己贴的来源标签？

### 原始问题

H7 行业架构卡已经要求五项结构要素导向 pair 的未来信号，但 `VERIFIED` 要素过去只校验 `evidence_id` 存在和 `source_class` 文本合法；作者仍可将公司自述、网点或排名写成“竞争对手披露”或“持牌行业数据”。另一个断链是卡能指向其他 pair 的信号，或指向本 pair 的终局 owner-cash 信号，令行业结构看似进入机制、实际未检验接口/价值攫取。

### 修改

- 行业架构卡现在只能连接其 `target_pair_id` 的 `EARLY_MECHANISM / INDUSTRY_STRUCTURE` FJ，以及同 pair、同 signal 的 `TESTABLE` 因果箭头；
- 对新 CJO 行业架构冻结，`VERIFIED` 要素逐项绑定 `evidence_id → raw fact source_id → document_manifest DOC`；来源类别由文档类型/权威性推导，不能自报；
- `LICENSED_INDUSTRY_DATA` 另强制绑定 PIT 文档的 canonical provider `source_id/source_version/revision_policy`；`UNKNOWN` 不受阻，普通/legacy CJO 不追溯扩张。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：跨 pair、错误阶段、无可检验箭头、伪造来源类别、DOC source ID 或 provider source ID 均被拒绝；合法持牌 source 与全 `UNKNOWN` 路径均通过。根因是 `MODEL + REASONING + ACQUISITION_MODULE`；若不修复，接口控制与价值攫取的伪证据会污染竞争持续期、正常盈利、owner cash 和永久损失判断。**本段关于三类外部发布者无法分类的当时限制，已由 P-33 的 source-role provenance contract 替代。** 未满足 P-33 的发布者实体、角色、scope、一阶 basis 与 PIT→DOC 一致性时，仍必须保持 `UNKNOWN`，不能把公司名称、关系推断或写作标签当证明。

## 迭代 P-30：行业竞争会不会被静态份额与公司动作替代？

### 原始问题

即使行业架构证据可追溯，行业分析仍可能停在“公司推出动作、行业份额变化”的静态描述，遗漏竞争机制中最有诊断力的一段：对手是否察觉该行动、是否有动机和能力在同一 arena 做有针对性的回应，以及这种回应怎样改变租金落点。

### 修改

- 新增[竞争回应机制实验协议](TURTLE_COMPETITIVE_RESPONSE_EPISODE_PROTOCOL.md)，复用既有 `rival_hypothesis_pair / causal_trace / EARLY_MECHANISM / TERMINAL_OPERATING`，不新增评分或平行账本；
- 冻结单元是 `行动 → 对手 awareness/motivation/capability → 回应对象/类别/时滞 → 同 arena 租金与经营后果`；行动发生只确认共同事实，不能支持任一机制；
- 对手沉默只有在来源覆盖了预先定义的回应载体时才能成为 outcome；来源不足为 `MISSING_OBSERVATION`，宏观共同冲击、公告和泛行业降价只能是 `NOT_DIAGNOSTIC`。

### 结论与后续验证

`DESIGN_READY_NOT_LIVE_TESTED`：Chen、Su & Tsai (2007) 与 Chen & Miller (2012) 支持把竞争动作/回应的对象、类型和时滞作为机制分析单位；Teece (1986) 支持观察租金实际落点，而非以创新、份额或垂直整合代替价值攫取；Langley (1999) 支持按过程顺序结算。这些是方法设计依据，不是公司参数。下一次 R-08 只在行动、arena、双方不同回应预测、早期回应来源和终局同边界经营来源都能于 cutoff 前冻结时启动；否则保持 `NO_ELIGIBLE_ECONOMIC_FJ`，不得因资料多而回到格力深挖。

## 迭代 P-31：近失效反例是否真的处于机制可能发生的共同条件内？

### 原始问题

P-25 已要求 near miss 除 `upstream_mediator` 外与 focal 保持相同状态向量，但相同文本、非空 `universe.source_ids` 并不能证明这些共同条件在三家公司 cutoff 前都成立。资料缺失、同一转述或结果期事实因而可能伪装为负例。

### 修改

- 为显式三对象批次增加冻结 `possibility_condition_evidence`，只索引既有 `claim_evidence.raw_facts → fact_observations → document_manifest`，不复制事实或另建案例库；
- 每个 `COMMON` 条件需要 focal、near miss、boundary 三方各自 cutoff 前的已验证一阶事实，且对应同一状态向量值；共同宏观/行业条件可引用同一权威 DOC，但不得复用同一 EVD/OBS 或以同一转述记录冒充三条条件链；
- 唯一 `MEDIATOR_EXCEPTION` 只能是 near miss 的 `upstream_mediator`，也必须有其自身事实链；placeholder、不可解析 source、cutoff 后、结果期、非直接/不精确证据均拒绝；普通/legacy register 不受影响。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：完整条件映射通过；output 事后证据、placeholder、cutoff 后、单边缺失、伪共同条件、同一 EVD/OBS 复用和 near-mediator 缺映射均被拒绝。共同权威行业/宏观 DOC 的复用经微复核应当允许：它不等于公司事实独立性，三方仍须有独立、直接的 EVD/OBS 映射。根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`；若忽略它，不具备机制前提的公司会被误当成近失效，污染机制可迁移性、FJ 边界与长期判断训练。可能性条件仍不是天然因果对照，也不产生频率或胜率；条件无法由一手证据闭合时，正确输出是 `NO_QUALIFIED_NEGATIVE_CASE`。Mahoney & Goertz (2004) 的 possibility principle 提供这一设计依据，不替代公司的条件事实。

## 迭代 P-32：早期信号会不会被复制成“终局结算”，伪造判断反馈？

### 原始问题

pair verdict 虽由双预测自动派生，但基础历史回测只确认 discriminator 的 claim ID 存在，未确认它与声明的 FJ 同一，也未要求早期和终局使用不同 FJ、claim 与窗口。直接 case 因而能把一条 6–12 个月的早期观察复制为 terminal，制造似乎完整的 `SUPPORTS_PRIMARY/RIVAL` verdict。

### 修改

- 带 rival pair 的 v2 case 强制每个 discriminator 的 `forward_judgment_id` 映射唯一且同一冻结 calibration claim；
- 每对必须含不同的 `EARLY_MECHANISM` 与 `TERMINAL_OPERATING` FJ/claim，早期 due 和观察窗口都须早于终局，且窗口不得相同；
- 保留早期 `SUPPORTS_PRIMARY / SUPPORTS_RIVAL / MIXED / NOT_YET_DUE` 的 provisional learning；`BOTH_MET / NEITHER_MET` 仍只产生 `NOT_DIAGNOSTIC`，不碰价格或投资路径。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：FJ↔claim 错配、复制 early 为 terminal、同一窗口、早期晚于终局均被拒绝；合法早期 provisional feedback 与既有 adapter 投影保留。根因是 `MODEL + REASONING`；若不修复，短期巧合会被当作竞争持续期、正常盈利和 owner-cash 路径的学习证据，飞轮会用错误反馈训练直觉。行业架构 P29 的删 causal trace 测试也同步改为正确的 `INVALID` 期望。验证覆盖 Stage14 87/87、Stage36 19/19、case-selection 14/14、feedback 8/8、learning 13/13、adapter projection 3/3；这些是契约回归，不是任何真实公司机制已被证明。

## 迭代 P-33：外部发布者角色会不会由名称、域名或作者标签伪造？

### 原始问题

P-29 已把 `VERIFIED` 行业架构要素连回 `evidence → DOC`，但普通 DOC 的 `issuer` 是报告目标公司，`OTHER_OFFICIAL` 同时容纳公司 IR 与其他官方页面，claim evidence 也没有发布者—目标公司关系。故 `COMPETITOR_DISCLOSURE`、`SUPPLIER_OR_CUSTOMER_DISCLOSURE`、`REGULATORY_DISCLOSURE` 只能写在卡里，不能由 canonical metadata 证明；若按文件名、域名、公司名称或叙述推断，会把公司自述或无关公告伪装成竞争响应、渠道权力或监管约束。

### 修改

- 仅当 source package 明确冻结 `source_role_provenance` 才允许这三类外部角色：发布者/目标方的稳定实体 ID（legal name 只供人工复读）、相对角色、产品/地区/期间 scope，以及指向同一 PIT package 内已准入一阶来源的 locator/basis kind；不从任何自由文本字段推导角色；
- PIT 只在该 source 已 `ALLOW` 读取后，把契约原样写进 DOC，并写出仅含 source identity 与角色契约的 provenance projection；角色依据来源也必须已投影为 DOC，未读或未投影则不能使用；
- P29 对新 architecture provenance CJO 才从 `DOC identity + DOC role contract + PIT projection` 三者完全一致的契约推导 external source class。缺实体、scope、role basis、投影、或任一字段被篡改都不能成为 `VERIFIED`；official statistics、licensed industry data、legacy 与 `UNKNOWN` 分支维持原有语义。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：COMPETITOR、SUPPLIER_OR_CUSTOMER、REGULATORY 三个完整、可读、同一投影的角色可通过；缺发布者实体、role basis 或 scope、DOC identity/contract 被改写、角色互换，以及没有角色契约的自家 `OTHER_OFFICIAL` IR 冒充监管均被拒绝。根因是 `ACQUISITION_MODULE + MODEL`；若不修复，外部关系的伪证据会直接污染竞争回应、价值攫取、正常盈利与 owner-cash 的机制判断。契约只证明角色取证链存在和一致，**不**自动证明发布者陈述为真、关系在 scope 外仍成立、或经济影响大小；这些仍由 pair、FJ 与后续结算处理。没有原始角色依据时正确输出仍是 `UNKNOWN`，不因资料数量、格力名称或报告写作完整度降低门槛。

## 迭代 P-34：结果期能否用手填观察或选择性来源把机制写成胜利？

### 原始问题

P-32 已让 pair winner 从冻结的双边谓词机械导出，但它继承的 `actual_sources.content_access=BODY_READ` 与 `actual_outcomes.value` 曾是作者自填字段。`operating_source_timeline` 也只检查提交进来的来源；即使规定 `INITIAL_DISCLOSURE`，研究者仍可不提交更早或不利的合格披露。R-05/R-06 的 `07_settlement.md` 原本只是可编辑 Markdown 表，因此同样不能证明读过原件或从原件得到数值。

### 修改

- 新增 `outcome_acquisition.py`：结果期首先保存一个有明确查询 identity 的完整候选源 inventory，再保存 raw/reader package、对每个 selected source 的读取审计和逐字 extraction；raw/reader 不是当前事实，也不回写冻结；
- extraction 的 source、发布时间窗口、指标/单位/口径/期间、发布者域名和预先冻结的 label/file-scope/locator 均在进入 HBT 前检查。数值必须与 extraction 中的原文数值 token 一致；
- 生产 CJO rival pair settlement 必须绑定 `package_root + manifest + read attestation + extraction`，实际 source 和 observation 必须等于该生成物。HBT 继续只负责从同一 observation 推导主/反 verdict；
- `judgment_feedback` 对非 `TEST_FIXTURE` case 重放 strict settlement validation，不能用 feedback/learning 入口绕过上述 P-34 outcome binding；
- R-05/R-06 在真实到期前新增执行契约，明确 `07_settlement.md` 仅为 extraction 的展示层。没有该结果链时状态保持 `NOT_YET_DUE / INCOMPLETE`，不是用叙事或相近 KPI 补结算；
- 新的前瞻冻结模板现在强制同目录的机器可读 `08_outcome_acquisition_contract.json`；它只能复述已经冻结的来源/口径/窗口/定位，任何实际值、价格、回报、概率或 winner 字段均拒绝，避免 P-34 只成为 R-05/R-06 的一次性补丁；
- 每条新 contract 还必须冻结 `INITIAL_DISCLOSURE / LATEST_OFFICIAL_AS_OF_EVALUATION`，而结果 inventory 的每个 source 必须登记它可服务的 `claim_id`；候选集还须同时满足该 claim 已冻结的 source type、发行方域名和观察窗口。extraction 只能选中这个合格候选集里政策要求的版本，不能让窗口外或错误域名的 archive 条目改变“首版”，也不能在同口径的后续 revision 中挑一个方便数值；
- 同一已计算 observation/source 在 subsequent CJO settlement 被静默改写的路径已同步拒绝。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：手改 extraction 数值但不改 reader 原文、手改 settlement value、缺 package/read audit、窗口/域名/label/locator 或 source payload 不一致均不能成为可审查的经营结算。定向直接回归覆盖 raw/reader→audit→extraction→settlement 绑定，历史 CJO series 的 observation/source rewrite 回归共 68 项已通过；另用纯合成 reader 对 R-05、R-06 的原冻结 outcome contract 做了到期日演练，两个合约均只接受各自的域名、窗口和 Transactions 指标，替换成同店销售或窗口外 release 均被拒绝。根因是 `ACQUISITION_MODULE + MODEL`；不修复会把选择性结果来源伪装为机制辨别，从而污染竞争持续期、正常盈利、owner cash 与永久损失的学习。该门不要求多角色审批，也不声称官方查询枚举能证明网站的宇宙完备性：它只把所声称的 bounded query、所有返回记录和选择理由保留下来。没有合格 query/export、reader 原文或同口径定义时，正确结果仍是 `INCOMPLETE / MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`。真实验收在 R-05 FY2027 Q1 或 R-06 FY2027 Q4 首次到期时执行；此前不得读取结果期正文或声称闭环有效。

### P-34.1：同一结果稿内的错误 KPI 行会不会仍被贴成冻结指标？

### 原始问题

P-34 原先证明 `reported_text` 出现在 reader、`reported_value_text` 可解析且与写入 value 相同，却没有证明该**同一片段**也含冻结的 `reported_label`。一份结果稿常同时列交易量、销售额、客单价、利润率等数值；作者可以把另一行的原文和值填入 extraction，同时保留目标指标的 label/locator 字段，绕过“全文中存在”检查。

### 修改

对可比较 observation，冻结标签与值文本现在都必须出现于同一个 `reported_text` 片段，才可进入 settlement；对 `MEASUREMENT_MISMATCH / NOT_DISCLOSED`，实际观察到的替代/缺失标签也必须出现在其原文片段。该检查仅规范化表格的空白和标点，不推断表格结构、不把相近 KPI 视作相同指标。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`。合成 reader 同时含“owner cash `0.18`”与“revenue `0.30`”时，后者即使是确实存在的原文和值，也不能被贴成 owner-cash extraction；真实的定义变化仍可落为 `MEASUREMENT_MISMATCH`，R-05/R-06 的冻结合约与 P-34/P-35 结算回归保持通过。根因是 `ACQUISITION_MODULE + MODEL`；否则错误 KPI 行会材料性改变竞争机制、正常盈利、现金转换乃至永久损失的反馈方向。缺失的是机器可证实的**同片段语义绑定**，不是更多报告。禁止以“全文中也提到了该 label”“值看起来合理”或相近指标替代该绑定。验收条件是任何 extracted number 必须同时有同片段的冻结 label/value/source/window，无法形成该片段时正确降级为 `INCOMPLETE` 或 `MEASUREMENT_MISMATCH`；它不自动证明公司自报指标经济上真实或跨期可比，后者仍由冻结 metric contract 与人工机制审阅承担。

### P-34.2：同一 KPI 的比较期间列会不会被误作目标季度？

### 原始问题

P-34.1 已把 label 和 value 绑回同一 reader 片段，但季报表通常在同一行同时列本期与去年同期。`measurement_period` 只是 extraction 中的冻结字段，不能单独证明其数值来自哪一列。Walmart FY2027 Q2 的已读 PDF 已可见 `Q2 FY27 / Q2 FY26` 与 `Transactions` 同行；没有期间锚点时，后一列仍能在 label/value 检查中伪装为目标季度。

### 修改

R-05 与 R-06 的结果执行合同仅复写其冻结目标期间，并以各自截止日前已读的一手格式冻结 `reported_period_anchor`：Starbucks 的 `Q1/Q3 Fiscal Year 2027` 延续其 FY2026 Q3 release 标题格式，Walmart 的 `Q4 FY27 / Q2 FY28` 延续其 FY2027 Q2 官方 PDF 表头格式。未来 extraction 必须在同一片段中同时提供该 anchor、指标 label 和 value；`Comparative period`、`Qx FY26` 等邻列即使含相同标签和值也不能结算。没有符合锚点的当前列时，只能 `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`。两个真实实时合同均通过，并且包含目标与比较列的合成结果包在把 `reported_period_text` 改为比较期后被机械拒绝；原有 label/value、版本、窗口及 signal-settlement 回归仍通过。根因是 `ACQUISITION_MODULE + MODEL`；若不修复，上一期交易量可能反向改变本期持续性箭头，从而错误训练行业/公司判断。缺失的是预先冻结的列/期间身份，非更多公司材料。禁止将文件发布日期、表中任一同名 KPI、或未来管理层叙事当作当前季度列的替代。验收条件是 extraction 对每条可比较 live signal 同时给出 reader 中的目标期间、label 和 value；不同格式不能机械对齐时降级。此项只覆盖带 `reported_period_anchor` 的实时执行合同；既有 legacy CJO 若没有一个结果前锚点，不能声称已有同等期间列保护，必须在新的冻结/准入中补足而非事后解释。

## 迭代 P-35：轻量前瞻实验会不会在 extraction 后又退回人工宣布机制胜负？

### 原始问题

P-34 已让 R-05/R-06 的结果数值来自可回放的原件链，但两项实验有意不走完整 `COMPANY_JUDGMENT_ONLY` case：它们是 `NO_PRIMARY` 的机制信号探针。若此时只在 `07_settlement.md` 写 “A_ONLY/B_ONLY”，信号仍会由作者的 Markdown 裁决，且无法可靠接入 append-only learning note。

### 修改

- 每个轻量前瞻合约增加仅复述 `06_forward_freeze.md` 的 `mechanism_signal_pair`：两条 H-A/H-B、两次 claim、阈值谓词、early/continuation 阶段和原冻结 locator；同一 signal 的 A/B 谓词必须是同阈值、互补的数值分区，不能留一个边界空档或重叠后再解释；early 的窗口必须在 continuation 开窗前关闭，不能用同窗/倒序结果伪造序列；它明确为 `NO_PRIMARY`，没有价格、回报、概率、中心路径或公司结论字段；
- 新增 `live_forward_signal_settlement`。它先重跑结果包/reader/extraction 验证，再从数值机械导出单条 `A_ONLY / B_ONLY / NOT_DIAGNOSTIC / NOT_YET_DUE` 和两期 `SUPPORTS_HYPOTHESIS_A / SUPPORTS_HYPOTHESIS_B / MIXED / NOT_DIAGNOSTIC`；不得由调用者输入 winner；
- 该结算可投影为 `judgment-feedback-card.v2`，但基线固定 `BASELINE_NONDISCRIMINATING`、选择状态固定 `NO_PRIMARY`。learning note 因而只能保留/停用**信号设计**，不能声称研究者选对公司路径。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：R-05/R-06 的纯合成、已读 reader 包可完整导出一正一负的 `MIXED` 信号结算，并产生可被现有 append-only learning-note 工具消费的反馈；同一冻结 H-B 谓词若被改成 H-A 的副本，合约拒绝。根因是 `MODEL + ACQUISITION_MODULE`；不修复会让未来的机制支持由人工文字决定，或者将 `NO_PRIMARY` 探针夸大为主路径选择，从而污染跨公司判断训练。真实验收仍仅在各自的结果窗口发生后执行；当前合成演练不代表 Starbucks、Walmart、零售或方法有效。

## 迭代 P-36：同一公司会不会被 learning note 的自由簇标签伪装成跨公司经验？

### 原始问题

`judgment_learning` 需要 `experiment_id` 和 `company_cluster_id` 才能拒绝把同一公司多季材料当作独立样本，但轻量 R-05/R-06 的 feedback 原先没有冻结这两个身份。作者可以在写 note 时把 Starbucks 或 Walmart 改写成一个新簇，令后续 `MULTI_COMPANY_METHOD_REVIEW_REQUIRED` 产生假的跨对象基础。

### 修改

`mechanism_signal_pair` 存在时，live-forward 合约强制 `research_identity.experiment_id / company_cluster_id`。机械 settlement 与 feedback 原样投影这两个字段；learning note 若对带身份的 feedback 填写不同实验或公司簇，验证器拒绝。此改动只固定样本身份，不自动裁定公司独立性、不改变 CJO/legacy 的人工复核边界，也不生成胜率或概率。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：R-05/R-06 两份冻结合约均可生成绑定身份的 feedback；将 R-05 note 填为 R-06/Walmart 被拒绝。根因是 `MODEL + REASONING`；不修复会把相关公司的重复信号误放大为迁移学习，从而错误提升对竞争持续性、正常盈利和现金判断的确信。缺失的不是更多公司报告，而是未来真的具有不同业务边界、状态与证据链的复验；因此现阶段仍不可输出方法准确率、成功率或概率。

## 迭代 P-37：竞争回应实验会不会由一个泛竞争故事或价格动作启动？

### 原始问题

R-08 的动作—回应—租金落点协议已经存在，但若候选筛选将网页搜索命中的降价、发布、行业竞争叙述或“未见回应”直接当作行动/回应，研究会回到静态份额故事；代码再严格也无法补出另一方同 arena 的事实与未来观察。

### 初筛与裁决

本轮只做候选发现，不建立公司材料包或读取结果期披露。初筛结果没有一项同时具备行动方一手事实、回应方可覆盖的同 arena 观察、H-A/H-B 不同的回应对象/类别/时滞，以及同 arena 的未来经营结果 contract。详见 [R-08 初筛记录](R08_COMPETITIVE_RESPONSE_INITIAL_SCREEN_20260821.md)。

裁决为 `NO_ADMISSION`，不是“市场没有竞争”或“R-08 被否证”。根因是 `DATA_COVERAGE + ACQUISITION_MODULE`；若错误准入，会把普通价格或产品动作误传为对手有针对性回应，材料性污染竞争持续期、价格实现、正常盈利和 owner cash 判断。不得以搜索摘要、宏观降价、管理层泛称、另一方全公司业绩、份额或股价补足。

### 下一步接纳标准

下一候选须先以 cutoff 前的行动方与回应方一手目录证明 action / arena / coverage，再冻结 A/B 回应时滞和同 arena 结果合同。任一项缺失，保持 `NO_ELIGIBLE_ECONOMIC_FJ`；不以继续读取格力或扩大某一家公司的报告数量替代。

## 迭代 P-38：流程门通过会不会被误传为“判断力已经提升”？

### 原始问题

P01–P37 已经提高了研究输入、冻结、结果采集与结算的纪律，但这些都是防止坏反馈进入飞轮的条件，不是公司判断正确的证据。若不区分层级，定向回归通过、source package 完整、一次 A-only 信号，甚至 `NO_PRIMARY` 的正确拒绝，都可能被叙述成“方法已经提高准确率”。这恰好会重现 outcome bias：结果或流程好看，倒灌为对当时理解更强的错觉。

### 干跑与裁决

R-07 是直接反例：Lululemon 的全价销售环比改善、Target 的跨渠道增长和 Nike 的 wholesale/direct 组合都可以被最强反方解释；为了让中心路径看起来更强而人为设定高于当期的阈值，会制造与简单延续基线的虚假差异。正确输出是 `NO_PRIMARY`，并非一个未被奖励的选择命中。R-03 也说明即使有同期机制、反方和后续官方结果，一旦结果口径不能重建，就只能是 `MEASUREMENT_MISMATCH`。R-05/R-06 则仅完成了未来的来源和信号结算准备，真实经营结果尚未到期。

这表明当前可验证的是飞轮的**完整性**，不是它的总体判断表现。根因是 `REASONING + MODEL + WRITING`；若混淆，经济影响是把对竞争持续期、正常盈利、现金转换与永久损失的主观确信，错误建立在报告数量、代码回归或事后表现上。缺失的是独立、到期、同定义的经营结算和它们驱动下一对象实际改变的记录；价格、回报、管理层事后归因、单公司多季和测试 fixture 都不能补足。

### 修改

- 在[判断力飞轮](TURTLE_JUDGMENT_FLYWHEEL.md)加入 `L0–L5` 验证阶梯，明确区分流程完整性、结果采集、单箭头诊断、主路径选择、跨公司迁移及多 episode 的相对表现；
- 在[研究迭代卡](../../../templates/research_iteration_card.md)新增“本轮验证等级 / 能声称的最高等级 / 升级仍缺什么”三项。它们要求研究者在读材料前写出边界，而不是用一张事后评分表判断自己；
- 新实验、复盘和对外表述都必须保留所有 `NO_PRIMARY`、`MIXED`、`NOT_DIAGNOSTIC` 与 `MEASUREMENT_MISMATCH` 分母。没有预先登记的独立 `L3` selection episode，不讨论准确率、概率或方法优越性。

### 结论与后续验证

`RETAIN_WITH_EVIDENCE_LADDER`：这次改动不创造新的公司结论，也不把 P01–P37 伪装成一场回测。它把下一步的验收顺序固定为：R-05/R-06 首次真实 `L1` 结果采集 → 结算为 `L2` 的单箭头反馈；出现真正 `SELECTION_ADMITTED` 对象后才可能测试 `L3`；两个不同公司簇均有真实 note 后才启动 `L4` learning application；只有多个独立、完整登记的 `L3` 后才讨论 `L5`。不允许以任何低级证据越级。该次序与 [Kahneman & Klein (2009)](https://doi.org/10.1037/a0016755) 对有效反馈环境的条件、[Hirt & Markman (1995)](https://doi.org/10.1037/0022-3514.69.6.1069) 的多重解释、[Baron & Hershey (1988)](https://doi.org/10.1037/0022-3514.54.4.569) 的 outcome bias 及 [Ericsson et al. (1993)](https://doi.org/10.1037/0033-295X.100.3.363) 的后续任务重设计相容；论文提供方法依据，不构成 Turtle 已有判断优势的证据。

## 迭代 P-39：飞轮样本会不会只留下“最后看起来值得入选”的公司？

### 原始问题

`case_selection_register` 已经有 universe 和 `INCLUDED / EXCLUDED` entry，也能阻止已知 outcome 挑选进入 batch；但显式 `judgment_flywheel_sampling` 没有要求 universe 中每家公司都有 entry。研究者可以在 freeze 前列出一个候选池、只为最终三家建 entry，而没有记录其余候选为何退出。结果并不立刻改变单家公司的机制结算，却会在未来 `L5` 比较时隐藏筛选分母，夸大选择方法相对简单基线的表现。

### 修改

- 仅在显式 `judgment_flywheel_sampling.enabled=true` 时，要求 universe 的每个 `candidate_company_id` 与 entry 中的公司集合完全一致；每个对象因而必须在 cutoff 前有 `INCLUDED` 或 `EXCLUDED` 及理由，entry 也不得从 universe 外悄然加入；
- `EXCLUDED` 继续不进入 FOCAL/NEAR_MISS/BOUNDARY 比较，不被计作预测失败或方法胜利；它只保存当时筛过而未入场的边界；
- 普通 register、探索、`NO_PRIMARY` 与 legacy workflow 不变，不把这个小 batch 纪律扩张成全市场收录或资料可得性评分。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：隐藏的 universe 候选和 universe 外的 entry 都必须在启用飞轮 batch 时失败；完整三对象 batch 与普通 register 保持原行为。根因是 `REASONING + MODEL`，不是数据量：缺失的是一条预先的筛选处置记录，而不是更多年报。若不修复，未来会把便利筛选误认成跨公司判断优势，材料性扭曲竞争持续期、正常盈利、现金转换和永久损失的训练证据。禁止以后续经营、价格、回报或结果期“更有代表性”理由补写 `EXCLUDED`。真正验收仍须等待不同公司、同定义的 `L3` episode；这道门只保证届时分母没有在研究中消失。其目的与 [Nosek et al. (2018)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5856500/) 的预注册透明性、[White (2000)](https://onlinelibrary.wiley.com/doi/10.1111/1468-0262.00152) 对 data-snooping 的警示，以及 [Seawright & Gerring (2008)](https://journals.sagepub.com/doi/10.1177/1065912907313077) 的目的性选案纪律一致；这些来源不证明 Turtle 的实际选择表现。

## 迭代 P-40：同一家公司会不会靠“还有新资料”无限延长研究？

### 原始问题

P-25 已规定一个公司默认只有一个 active episode ticket，避免把格力或任何资料丰富公司误当经验库；但[研究迭代卡](../../../templates/research_iteration_card.md)没有要求立项时检索同公司已有 ticket、说明本卡的机制格或证明新的前瞻结算对象。原则因而容易在“又有一份年报/电话会”“再多读一层”的合理化中失效。

### 修改

- 迭代卡新增“同公司重入”段落：必须列出既有 ticket、`机制域 × 当前状态 × 竞争叉`、真正的新机制格、以及新 H-A/H-B、FJ、基线与同口径结果合同；
- 缺任何一项时，输出固定为 `EXPLORATION_ONLY` 并停止扩读该公司，改选空白格、近失效或边界复验；新材料、chronology、重复来源与 agent 数量被明确排除为重入理由；
- 不以全局目录扫描或公司名称匹配做自动阻断。是否形成新的机制格需要经济判断；把它伪装成文件 identity 校验，只会增加脚手架而不能改善研究选择。已冻结旧卡不追溯回填。

### 结论与后续验证

`RETAIN_WITH_SEMANTIC_REENTRY_GATE`：根因是 `REASONING + WRITING`，而非 `DATA_COVERAGE`。若不修复，研究会在同一公司堆积解释性材料，却缺跨行业、近失效和边界复验；由此高估对竞争持续期、正常盈利、现金转换与永久损失的把握。缺失的不是又一份格力报告，而是一个新的、可被后续同定义观察结算的经济分歧。禁止用资料量、叙事更完整、管理层新措辞、结果期信息、价格或回报宣布新 episode。接纳条件是下一张同公司卡在读取材料前明确通过上述四项；不能通过就保持探索而不进入正式研究队列。这与目的性理论抽样和理论饱和优先扩展机制边界、而不是在便利对象中加深细节的原则一致（[Eisenhardt, 1989](https://journals.aom.org/doi/abs/10.5465/amr.1989.4308385)；[Seawright & Gerring, 2008](https://journals.sagepub.com/doi/10.1177/1065912907313077)），但不把单次 company screen 误作外部效度证明。

## 迭代 P-41：外部档案会不会因材料丰富和案例知名而绕过可结算谓词？

### 原始问题

R-03 已因 Trian/杜邦的约 `29%` 条件桥无法与官方结果口径连续重建而收紧 metric-reconstruction gate；但若这个门只在已经下载结果期材料后才发挥作用，研究者仍会耗费时间读大量有名的 proxy contest，并倾向把后来销售、现金或行动结果接到早期宽泛愿景上。

### 复筛与修改

本轮仅阅读 P&G/Trian 2017 与 Darden/Starboard 2014 的同期 SEC 原件，未打开任何后续经营、价格或回报结果。两组材料都有可运行的组织/运营争论，却都没有原作者指标、比较对象、窗口与可由公司官方结果重建的 mapping；详见 [R-03 外部候选复筛](R03_ARCHIVED_EXTERNAL_CANDIDATE_SCREEN_20260821.md)。因此它们在 intake 阶段即为 `NO_ADMISSION`，不建立 outcome package，不把“销售、利润、现金流更好”改写为可以任择的未来 KPI。

### 结论与后续验证

`RETAIN_FAIL_FAST_METRIC_GATE`：根因是 `DATA_COVERAGE + REASONING`。若放松，会把 proxy contest、管理层愿景或著名案例结局误传为组织、渠道或运营机制的外部经验，材料性污染正常盈利、现金转换与资本配置判断。缺失的是结果前可复写的经营谓词，而不是更多原件；禁止用行动、董事会变化、单期报表、价格或回报替代。接纳条件是 outcome 尚未读取时，独立审阅者已经能从预期官方 source 重建同一 metric/window/adjustment/prohibited-substitute contract；否则停止。该复筛是对 R-03 拒绝规则的迁移检查，不是 Turtle 历史命中、方法回测或公司结论；它与 [Collier (2011)](https://doi.org/10.1017/S1049096511001429) 的诊断性过程证据要求及 [Baron & Hershey (1988)](https://doi.org/10.1037/0022-3514.54.4.569) 的结果偏见防护相符。

## 迭代 P-42：冻结的前瞻实验会不会因未被触发而永远停留在 `NOT_YET_DUE`？

### 原始问题

P-34 已使到期后的数值必须从结果源枚举、raw/reader、读取审计和 extraction 进入结算；但 R-05/R-06 的 `07_settlement.md` 仍是静态的 `NOT_YET_DUE` 展示。没有一个只读、可重跑的到期判定，研究会话可以无限继续做准备工作而错过应启动的采集，或者在窗口关闭后把迟来的采集伪装成及时反馈。

### 修改

- `outcome_acquisition assess_live_forward_acquisition_due` 只读取冻结的 outcome contract 和显式 `as_of`，逐 claim 机械输出 `NOT_YET_DUE`、`DUE_FOR_ACQUISITION` 或 `OVERDUE_FOR_ACQUISITION`；不访问网站、不读取结果、更不生成 value、winner、概率或公司结论；
- CLI `outcome_acquisition execution-status CONTRACT --as-of ...` 让每次会话先确认正确动作。`DUE` / `OVERDUE` 的唯一研究动作都是启动 P-34 原冻结结果采集链；不能补读当前公司材料、修改阈值，或在 Markdown 中手写结算；
- R-05/R-06 的真实合约在 2026-08-21 仍都返回 `NOT_YET_DUE`。这只是运行状态，不是结果或 `L1` 证据。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：两份真实冻结合约分别演练了窗口前、开窗中和窗口关闭后三种状态；12 项定向回归通过。根因是 `REASONING + ACQUISITION_MODULE`：没有触发接缝，结果反馈即使被严密定义也可能根本不进入飞轮，延误会使竞争持续期、正常盈利与 owner cash 的学习停留在叙事准备阶段。缺失的不是更多报告或现在的结果；R-05/R-06 的正确下一步仍是等待相应窗口。禁止假设检查到期等于已取得观察、逾期等于机制失败，或以价格/回报代替结果源采集。验收条件是到期时用同一命令先转为 `DUE`，再以 P-34 的完整结果链得到唯一可结算的 observation；该观察才可能升级为 `L1`，其机制诊断性仍另行按 P-35 结算。

## 迭代 P-43：有明确数值的外部争论会不会仍缺真正的结果通道？

### 原始问题

P-41 已拒绝没有指标/窗口的 P&G 与 Darden 档案，但这仍留下一个更隐蔽的绕过：外部判断可能给出同一数值、基准和期限，而该数值只在一次性 proxy 或 investor deck 中出现；研究者随后会以一个不同定义的 GAAP 或 non-GAAP KPI“结算”它。

### 结果前复筛

只读 ADP 的 2017-09 至 2017-10 SEC 原件及 2017-08-04 FY2017 10-K，未打开 FY2020 或任何后续经营、价格、回报材料。ADP 表示到 FY2020 增加 500bp `net operational margin`，Pershing Square 的当时反方称计划实际只代表约 300bp；表面上已经满足同指标、不同机制和时间窗口。但 ADP 的 cutoff 前 FY2017 10-K 没有 `net operational margin`、`operational margin` 或 `adjusted EBIT` 作为连续结果指标，管理层 proxy 材料中的 reconciliation 也不能证明将来同一官方文件会重复此口径。详见 [R-03 候选复筛](R03_ARCHIVED_EXTERNAL_CANDIDATE_SCREEN_20260821.md)。

### 修改与裁决

- R-03 `metric-reconstruction contract` 新增“重复结果通道证明”：结果前必须有既有的常规官方披露 locator、未来文件类型和披露节奏，证明原指标或完整的预注册 GAAP 重建在结果窗口可重复；
- 结构化类比与近失效卡同步要求逐项填写该通道、重建规则、禁止替代和定义变更动作，避免 P-43 只停在 intake 文档而未约束实际登记入口；
- 此门不要求事先知道结果值，也不将没有通道解释为任何一方机制失败；它只拒绝让一次性 campaign metric 在结果期换成更方便的 KPI；
- ADP/Pershing 标为 `PRE_OUTCOME_ONLY / NO_ADMISSION / NO_OUTCOME_OPENED`，不建立 outcome package。

`MODIFY / RESULT_CHANNEL_GATE_RETAINED`：根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。不修复会将管理层/激进股东对效率、利润或现金的争论，在结果期任择拼接为 GAAP margin、adjusted EBIT、EPS、价格或回报，材料性扭曲对正常盈利、现金转换和资本配置机制的外部经验。缺失的是预先证明的同口径 endpoint，而非更多 campaign 幻灯片。禁止用 FY2020 后的披露来证明该通道、用一次 reconciliation 推定持续披露，或把不同 KPI 当等价；接纳条件是 outcome 未读时，独立审阅者已能从既有常规披露复写同一结果指标/调整/窗口。该迭代只提高档案准入纪律，仍不是 Turtle 的历史命中或判断力验证。

## 迭代 P-44：非结算的中间业绩会不会先污染研究者、再影响真正的结算？

### 原始问题

R-05 在冻结时把 FY2026 Q4 北美交易量写成“非结算脉冲”，真正的早期与延续 claim 却是 FY2027 Q1/Q3。Q4 不会按任何冻结谓词改变动作，也不进入结果期 extraction；若先读到它，研究者仍可能在 Q1/Q3 到期时用它解释、维护或弱化 H-A/H-B。P-42 的 `NOT_YET_DUE` 原本要求等待，但没有明确排除这类“背景脉冲”。

### 修改

- 迭代卡与前瞻冻结模板现在明确：只可读取已到 `DUE_FOR_ACQUISITION` 的冻结 claim 所选 source body；任何非 claim 的 post-cutoff 业绩、相近 KPI 或预先标为非诊断的脉冲均为 `UNREAD`；
- 结果期执行协议禁止将这些材料放入 inventory、raw/reader package、红队或学习复盘。若已读，登记 `OUTCOME_EXPOSURE_BREACH`，该 episode 只可作为管线训练，不能成为判断力 feedback、learning note 或迁移复验；
- 未改写 R-05 的冻结 H-A/H-B、`0%` 阈值、Q1/Q3 窗口或其 source contract；仅在结果发生前收紧执行边界。R-05 增加独立执行说明，明定 Q4 不采集、不阅读。

### 结论与后续验证

`MODIFY / PRE_OUTCOME_EXECUTION_BOUNDARY`：根因是 `REASONING + ACQUISITION_MODULE + WRITING`。若不修复，一个没有预先承诺动作、也不能被机械结算的中间结果会制造后见锚点，材料性污染随后对竞争持续期、正常盈利和现金转换箭头的解释；它不会自动改变数值 verdict，却会污染飞轮把 verdict 变成下一次研究设计的那一步。缺失的不是更多数据，而是无偏暴露边界。禁止假设“只叫它脉冲/不写入 Markdown”就不会影响判断，或让 Q4 结果替代 Q1/Q3 的冻结结果。验收是：Q4 到期时执行状态仍为 `NOT_YET_DUE`、不产生 source package/read audit/extraction；若发生暴露，状态降为 `OUTCOME_EXPOSED_TRAINING_ONLY`，而非产生 learning note。该迭代只保护未来 `L1/L2` 的有效性，不构成公司结论或判断力提升。

## 迭代 P-45：暴露边界会不会只是一句无法改变反馈的声明？

### 原始问题

P-44 已规定非 claim 的中间结果未读、暴露后不能进入 learning。但轻量 `live_forward_signal_settlement` 原先只校验 outcome package、reader、extraction 和冻结阈值；它不知道 `OUTCOME_EXPOSURE_BREACH`，所以即使研究者已读 R-05 的 Q4 结果，仍可生成 feedback card 与 learning note。这让正确的文字规则在唯一会影响下一次研究的接口失效。

### 修改

- 结算前新增 `turtle-live-forward-exposure-attestation.v1`：它绑定 case、freeze、settlement 时点与实际 read audit 的 source IDs，并在 `NO_NONCLAIM_RESULT_EXPOSURE` 与 `OUTCOME_EXPOSURE_BREACH` 两种状态之间明确选择；
- 正常状态照常产出机械 `A_ONLY/B_ONLY/MIXED/NOT_DIAGNOSTIC` 与可学习 feedback。breach 仍保留同一机械 settlement，避免掩盖流程事实，却强制 `learning_eligibility=OUTCOME_EXPOSED_TRAINING_ONLY`，feedback card 为空，因而不能写 learning note 或进入迁移复验；
- 缺失证明、case/freeze/时点不一致、read source IDs 与 read audit 不一致，均使 settlement 不可用。该证明是研究者对 pipeline 之外可见结果的明确披露，不假装能由程序读心；程序能验证的是披露与已读 source 的一致性及其后果。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：正常无暴露路径、源清单错配与已暴露路径均已覆盖；已暴露路径可计算机制 verdict，但不能产出 learning cards。根因是 `MODEL + REASONING + ACQUISITION_MODULE`。若不修复，后见结果可在不改变任何 frozen 数字的情况下进入下一次方法设计，材料性污染对竞争持续期、正常盈利和现金转换的学习。缺失的不是另一份报告，而是把暴露事实接到 feedback 的行为边界。禁止将“没有读到”当成自动可验证事实，或因机械 settlement 正常便称该 episode 仍是有效的判断力样本。验收条件是 settlement 只接受与 read audit 一致的 exposure artifact；breach 必能阻止 `build_live_forward_judgment_feedback` 生成可传入 `judgment_learning` 的 card。该改动不增加价格、回报、概率、公司结论或主路径选择。

## 迭代 P-46：未来 L5 会不会在结果到来后才挑 cohort、指标或分母？

### 原始问题

逐案 feedback 已经能把一个 `SELECTION_ADMITTED` 的 terminal signal 与简单 baseline 比较，但系统没有一个冻结的跨案聚合对象。等多个结果到来后，研究者可以只拿支持主路径的公司、只留基线落后的 FJ，或把 `NOT_DIAGNOSTIC` 与 `NO_PRIMARY` 从记忆里删掉，再说方法“相对更好”。这不是单家公司的结算错误，却会在飞轮最终把经验提升为总体判断时重新引入 data snooping。

### 修改

- 新增 `judgment-method-evaluation-plan.v1` 与 `judgment_method_evaluation`：它在任何入选结果窗口开启前，冻结一个有限 cohort、`case_selection_register` 的完整 screen-entry 处置，以及每个入选公司唯一的 terminal FJ/claim/freeze identity；register 中每条 entry 都必须有 `INCLUDED_SELECTION_EPISODE / EXCLUDED_NO_PRIMARY / EXCLUDED_NONCOMPARABLE` 理由，不能静默消失；
- 计划只接受 `COMPANY_JUDGMENT_ONLY`、非价格经营结果、`NO_PROBABILITY`、每个独立公司簇一个 selected `TERMINAL_OPERATING` FJ；计划指纹会拒绝事后改 cohort，`outcome_not_before` 会拒绝在该 FJ 结果窗口已开启后才冻结；
- 聚合只接受计划中逐一列出的 feedback card，拒绝漏 unit 或把 early signal 冒充 terminal。它保留支持主方、支持反方、不可判定、基线无区分和未到期的全体计数，以及已冻结谓词对简单基线的三种直接比较计数；不计算百分比、概率、胜率、综合分或投资/价格表现。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：完整 register + 三个独立 terminal unit 可通过；隐藏 screen entry、窗口开启后 freeze、非 terminal FJ、价格/概率/score 字段、漏反馈 unit 与将 early 反馈当 L5 均被拒绝；主方胜、反方胜和不可判定三类都仍留在输出中。根因是 `REASONING + MODEL`，而非 `DATA_COVERAGE`：当前缺少的是结果前的聚合边界，不是更多公司材料。若不修复，研究者会高估竞争持续期、正常盈利、现金转换与永久损失判断的可迁移可靠性。禁止用报告数量、同一公司多季、价格/回报、事后案例、测试 fixture 或隐藏的 `NO_PRIMARY` 替代独立经营 episode。真正验收仍等待多个真实、不同公司、同定义的 `SELECTION_ADMITTED` terminal outcome；在那之前输出只能是 cohort 准备和计数规则，不是方法优越性。这个设计落实 [Nosek et al. (2018)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5856500/) 的结果前确认、[White (2000)](https://onlinelibrary.wiley.com/doi/10.1111/1468-0262.00152) 对 data-snooping 的警示，以及 [Diebold & Mariano (1995)](https://doi.org/10.1080/07350015.1995.10524599) 对多期、预先定义损失比较的要求；这些文献不证明 Turtle 已有相对优势。

## 迭代 P-47：同一公司能否靠自由 cluster 标签重复进入 L5？

### 原始问题

P-46 要求不同 `company_cluster_id`，但这一字段原本来自 evaluation plan 自填，未绑定 selection register 的公司身份。若同一家公司在不同期间进入多个 entry，研究者可以为每个 entry 写一个不同 cluster 字符串；cohort 形式上满足最小簇数，实质上仍只有一个相关公司样本。

### 修改

- L5 plan 现在同时要求 `company_id` 和 `company_cluster_id` 全 cohort 唯一；
- 单元的 `company_id` 仍须与 `selection_entry_id` 对应 register entry 一致，`company_cluster_id` 进一步必须等于该 entry frozen `cluster.company_id`；不接受自由命名的第二 cluster；
- 没有改变普通 case register、同公司在不同机制格的探索或日后研究资格；它只阻止这些相关材料在 L5 被计作多个独立比较单元。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：同一 `COMPANY:alpha` 被放进多个 selection entry、再给出不同 cluster 标签时，L5 validation 同时报 company 重复与 cluster identity mismatch；正常三公司 cohort 仍可通过，相关回归共 46 项通过。根因是 `MODEL + REASONING`，不是样本量或资料量。若不修复，会把一个公司的重复经营周期夸大为多家公司都支持该方法，材料性高估竞争持续性、正常盈利、现金转换与永久损失判断的可迁移性。缺失的仍是未来真实不同公司 outcome，而非更多同公司报告。禁止将不同财年、FJ、case ID 或自由 cluster 名称视为独立公司；只有 frozen register 的 canonical company identity 才可决定 L5 独立性。验收条件是未来真实 cohort 既能通过该绑定，又在每个不同公司上保留一个 terminal result；这仍不构成概率、胜率或一般方法优越性。

## 迭代 P-48：冻结 case 能否在结果后被重新挂到另一条 selection entry？

### 原始问题

P-47 已把 L5 的 company identity 锁到 register，但 `SELECTION_ADMITTED` 的 frozen case 本身只保存主/反机制、FJ 与选择证据，不保存它来自哪一条 `CSRSEL:` entry。只靠 cohort plan 的自填 `selection_entry_id`，仍可以将同一家公司另一个机制格、另一个 FJ 或较晚 case 接到当初的 entry，再用它的结果参与 L5。

### 修改

- CJO 的 `selection_admission` 新增可选 `selection_register_binding`：`register_id / register_fingerprint / selection_entry_id / company_id / company_cluster_id`。它只在为 L5 准备的 `SELECTION_ADMITTED` case 使用；普通 CJO、`NO_PRIMARY`、legacy 和投资路径都没有新增强制项；
- thesis gate 校验该 receipt 的完整性、ID 格式和冻结 fingerprint 形状，writer/schema 提供同一对象，Phase10 按原 selection admission 投影；
- `freeze_method_evaluation_plan` 在真正写入 L5 plan 前读取 frozen case，要求 case receipt、plan unit 和 frozen register 逐字段一致，同时继续确认它是 selected pair 的 terminal FJ。结果期改 entry、case、claim、cluster 或 register fingerprint，都会阻止 cohort freeze。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：有效 CJO binding 可通过 thesis gate 并经 Phase10 原样投影；不完整/非法 fingerprint 被拒；L5 freeze 可消费三条一致的 frozen case receipt，之后将其中一条改挂到另一 `CSRSEL:` 即失败。152 项 Stage14、adapter、L5 plan、feedback 与 register 定向回归通过。根因是 `MODEL + REASONING`：缺的不是公司数据，而是选择时点与未来比较单元之间的 frozen identity。若不修复，结果更有利的不同机制判断可能被误记为原先选择能力，材料性夸大对竞争持续期、正常盈利、现金转换与永久损失判断的跨对象可靠性。禁止将同公司、不同 FJ、不同 case 或人工 entry 对应视为天然同一 selection episode；也禁止因为普通 `SELECTION_ADMITTED` 没填 register receipt 就降级其自身机制研究。验收条件是未来 L5 cohort 只能由带同一 receipt 的真实 terminal results 构成；这仍只是比较准备，不是方法胜率、概率或优越性证明。

## 迭代 P-49：方法会不会通过不断 `NO_PRIMARY` 而显得“更准”？

### 原始问题

P-46 至 P-48 已固定哪些 `SELECTION_ADMITTED` terminal FJ 可以进入 L5，但方向比较仍只发生在入选单元上。若困难对象总被标为 `NO_PRIMARY`、而报告只展示入选后 `SUPPORTS_SELECTED` 的计数，研究者可以用更低覆盖换取更好看的条件表现，却把它表述成整体判断力提高。反过来，不能因为后来某路径有结果就把当时谨慎的 `NO_PRIMARY` 改判成“错过”或“正确弃权”：那会再度以后见之明评价当时证据。

### 修改

- L5 plan 现在要求每一条 `INCLUDED_SELECTION_EPISODE` 都有一个 terminal evaluation unit；有入选 screen entry 却没有 unit 会在 freeze 前失败；
- 聚合输出新增冻结 screen 的三类计数：`INCLUDED_SELECTION_EPISODE / EXCLUDED_NO_PRIMARY / EXCLUDED_NONCOMPARABLE`，并明确方向/基线比较仅条件于第一类；
- `NO_PRIMARY` 只表示 cutoff 前不足以选择路径，既不记作方向胜利，也不记作方向失败；`NONCOMPARABLE` 也保留为研究边界。输出禁止把这三类压成覆盖率、准确率、风险—覆盖曲线、胜率或单一方法分数。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：已验证，已标入选但未生成 terminal unit 时 cohort 被拒；一个额外 `EXCLUDED_NO_PRIMARY` screen entry 会与三个入选 unit 同时出现在输出的 coverage accounting 中，但不进入 `SUPPORTS_SELECTED` 分子。相关 L5、feedback、learning 与 selection-register 回归共 49 项通过。根因是 `REASONING + MODEL`，不是数据覆盖：缺失的是把“选择方向”与“选择是否弃权”并列透明化的研究边界。若不修复，研究者会高估对竞争持续期、正常盈利、现金转换和永久损失的机制选择能力。禁止将少量入选 episode 的条件表现推广为总体优势，或用后续经营、价格/回报把当时 `NO_PRIMARY` 标成正确/错误。验收条件是未来真实 L5 输出同时呈现完整预先冻结 screen 和入选终局结果，并保持两条轴不可合并。选择性预测文献把这种问题表述为风险—覆盖权衡；其“拒绝/弃权会改变被评估样本”的结论支持这里的透明性要求，但不授权用机器学习风险指标评价投资研究（[El-Yaniv & Wiener, 2010](https://jmlr.csail.mit.edu/papers/v11/el-yaniv10a.html); [Geifman & El-Yaniv, 2019](https://proceedings.mlr.press/v97/geifman19a.html)）。预注册关于完整报告而非事后挑结果的原则亦提供边界（[Nosek et al., 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC5856500/)）。这些来源不证明 Turtle 已有判断优势。

## 迭代 P-50：`NO_PRIMARY` 会不会只是结果后写入的筛除理由？

### 原始问题

P-49 已把 `EXCLUDED_NO_PRIMARY` 展示为与入选方向表现并列的选择边界，但 plan 的 screen entry 只需一段理由，不需要一个真正的冻结 case。研究者仍可在看到结果后，将未做 CJO 的对象或不利对象叫作“当时谨慎弃权”，使 coverage accounting 看似完整却没有原始判断工件。

### 修改

- `EXCLUDED_NO_PRIMARY` 现在必须登记 `no_primary_case_id / no_primary_freeze_id`；L5 freeze 读取该 case，要求其 `selection_admission.status=NO_PRIMARY`；
- `NO_PRIMARY` CJO 可选地使用与 `SELECTION_ADMITTED` 相同的 `selection_register_binding`。L5 逐字段核对 register ID/fingerprint、entry、company 与 canonical cluster；普通 `NO_PRIMARY` 探针仍可省略 binding，不被强迫进入 L5；
- `NO_PRIMARY` receipt 缺失、case/freeze 不一致、status 被改为 selection admitted、或 binding 与 screen entry 不一致，均不计为弃权；该对象只能诚实保留为 `EXCLUDED_NONCOMPARABLE`。

### 结论与后续验证

`MODIFY / TARGETED_REGRESSION_PASSED`：一个完整的 delta `NO_PRIMARY` case 可与三个 selected terminal case 一起冻结 L5 plan；将 delta case 的 status 改为 `SELECTION_ADMITTED` 会被拒。CJO gate 同时确认 `NO_PRIMARY` receipt 可保留 canonical binding。169 项 L5、Stage14、adapter、feedback、learning 和 register 定向回归通过。根因是 `MODEL + REASONING`，不是缺少第三方数据。若不修复，会把事后筛除包装成对竞争持续性、正常盈利、现金转换和永久损失的“谨慎判断”，虚增方法覆盖质量。禁止以后续经营、价格、回报、报告篇幅或手写 reason 补出弃权；也禁止把真正 `NO_PRIMARY` 当方向胜负。验收条件是未来每一个 L5 弃权都能回读到同一 cutoff 的 case/freeze/register receipt；它仍只衡量研究边界透明度，不说明弃权本身优于选择、也不生成方法分数或投资结论。

## 迭代 P-51：要求写“为什么像”会不会反而把类比带回故事？

### 原始问题

现有结构化类比卡虽要求匹配维度、断裂与近失效，却让 source、target 和“真正匹配”的理由同时出现。对公司研究而言，品牌、行业、规模、著名管理者和已知结局比因果角色更容易被说清楚；研究者可能先感到“像”，再把该感觉翻译为 `driver → intermediate → operating observation`。这会将书籍案例或格力相似点错误迁移到竞争持续性、正常盈利、owner cash 或永久损失。

### 修改

- 类比卡新增 `STRUCTURE_FIRST` 两阶段输入：先写 target-only、再写 source-only 的状态与因果骨架，只有两份草图都保留才允许做结构对齐、理由、断裂和近失效；
- target pass 禁止出现 source 公司的品牌、行业、管理层、结局、估值或回报；若在开始前已无法隔离 source context，诚实标 `CONTEXT_SEPARATION_NOT_ASSURED`，只能作问题路由，不声称检验了该干预；
- 对齐必须显式排除表面相似，并产生一个 target-only 草图原本没有的、可结算的断裂观察。结果期只结算该观察，不以 target 后来好坏、股价或回报替代；
- 公司经验协议、方法大纲与论文训练表同步采用该顺序。

### 结论与后续验证

`MODIFY / L0_SYNTHETIC_RETEST_PASSED / DESIGN_NOT_LIVE_TESTED`：同一“高端品牌 + 服务网络”的合成输入在旧顺序下会允许故事式支持；在 [干跑 03 的 P-51 复测](TURTLE_WORKFLOW_DRY_RUN_03.md#6-p-51-再测试先写理由会不会让这张卡重新变成故事) 中，Pass A 先保留 B 的 H-A/H-B 与未知，Pass B 才定位 A 的 uptime/续约因果链，最终因 B 缺该结构而输出 `NOT_TRANSFERRED`。这证明模板会在这个设计输入中把不合格迁移退回问题，不是对任何公司机制的裁决。Sieck、Quinn 与 Schooler的受控类比实验发现，要求受试者为类比作理由会提高匹配判断，并降低对结构相似与表面相似的辨别（[1999](https://doi.org/10.3758/BF03198537)）；它支持把“理由”从结构发现阶段后移，但不证明该心理学结果会直接提高投资研究。根因是 `REASONING + WRITING`：早期叙事使易语言化的共有特征替代可迁移机制。缺失的不是更多案例或报告，而是一个 source/target context 真能隔离、并有独立 target 结果合同的合格 episode。禁止把一次完整卡、著名案例、源案例结局、价格/回报或研究者的主观“更深刻”当作成功。验收需要至少两个不同 target：每次可复读的独立 Pass A/B、对齐后新增的不同断裂观察、其冻结的经营结算，以及 learning review 对表面迁移是否减少/诊断性是否增加的保守比较；此前不报告类比方法胜率、校准或优越性。

## 迭代 P-52：两阶段类比会不会只在模板上分离、实际阅读时仍互相污染？

### 原始问题

P-51 把 source/target 的因果骨架分为两段，但没有规定材料由谁读、什么能交给 integration、以及谁确认 Pass A/B 未被回写。多人或多 agent 若在原始阅读中互相传递 source 故事、结果或“应得结论”，`STRUCTURE_FIRST` 会退化为一份更长的事后理由表。此缺口属于 `ACQUISITION_MODULE + MODEL + REASONING`，不是缺少案例数量。

### 修改

- 类比卡新增最小交接收据：`target mapper` 只读 target cutoff 前 packet，`source mapper` 只读 source cutoff 前 packet，`integration lead` 只能对齐两份冻结草图，`reviewer` 只核对 packet/locator/顺序；
- 每一角色的允许输入、输出与禁止项写入同一张表；integration 的新事实必须退回 mapper，不能以协调者常识补写；
- 同一模型/会话已含另一侧材料、结果或旧结论时，必须标 `CONTEXT_SEPARATION_NOT_ASSURED`。这是可审计的限制，不是声称已实现模型记忆隔离；多 agent 也不构成独立样本或投票。

### 结论与后续验证

`MODIFY / L0_SYNTHETIC_HANDOFF_PASSED / DESIGN_NOT_LIVE_TESTED`：在 [干跑 03 的 P-52 交接复测](TURTLE_WORKFLOW_DRY_RUN_03.md#7-p-52-再测试角色分离能否让两阶段输入真的可执行) 中，target mapper 只得到 B 的未知与机制叉，source mapper 只得到 A 的 uptime/续约结构，integration 因 B 缺关键结构而只能输出 `NOT_TRANSFERRED`。若任何角色出现另一侧事实或 integration 加入新事实，reviewer 必须降级 context 状态。经济影响是阻止 source 的著名成功、竞争持续性叙事或结果倒灌为 target 的正常盈利、owner cash 或永久损失判断。缺失仍是两个真实、可隔离 packet 的 target 与未来经营结算；禁止把角色数、文档数、流程通过、源案例结局、价格或回报当成判断改善。验收是未来真实卡可以回读四个 packet/输出边界，且至少两个独立 target 的断裂观察按原合同结算；此前 P-52 只证明输入纪律能运行。

## 迭代 P-53：最强反方会不会因假设空间遗漏而成为伪二分？

### 原始问题

现有 H-A/H-B pair 能要求共同事实、双边因果链、可达的 A-only/B-only 预测，并在结果期将 `NEITHER_MET` 导向机制或测量重开；但冻结前 `candidate_scenario_ids` 只核验候选名称存在，并不要求研究者记录每个实质候选为何被配对、合并、暂缓或排除。于是一个仍能解释共同事实、会材料性改变正常盈利、现金转换、资本配置或永久损失的第三机制，可以在挑选“最强反方”时静默消失；之后的二元结算即使机械正确，也无法证明原选择覆盖了真正的竞争空间。

这是 `REASONING + MODEL` 缺口，不是 `DATA_COVERAGE`：更多格力报告或再添加一个情景名称都不能说明其因果顺序是否不同、是否真的被排除，或是否应令研究者放弃中心路径。

### 文献与边界

Hirt 与 Markman 的[多重解释实验](https://doi.org/10.1037/0022-3514.69.6.1069)检验的是要求生成**可信替代**如何扩大备选解释，而不是“列越多情景越好”。Platt 的[*Strong Inference*](https://doi.org/10.1126/science.146.3642.347)将进步归于可运行的替代假说和能排除其中一部分的关键观察。这两者支持“先生成、再筛选、再让一对最有信息量的机制结算”的次序；它们不证明公司世界可以被两个机制穷尽，也不授权把没有未来区分的第三机制伪装成已排除。

### 修改

- 机制实验卡新增冻结前的“假设空间筛选”表：每个 material candidate 必须连接共同事实的因果链、不同箭头/顺序、可分叉观察，以及 `PAIR_PRIMARY / PAIR_RIVAL / MERGE / DEFER_NO_PRIMARY / EXCLUDE` 之一；
- `MERGE` 必须是因果顺序与结果区域相同，`EXCLUDE` 必须是 cutoff 前事实直接矛盾；资料不足、研究者偏好或后续结果不构成排除；
- 一个仍可信但没有合格分叉观察的候选固定为 `DEFER_NO_PRIMARY`：允许保留 H-A/H-B 作纯机制信号探针，但禁止将任何一方升为 `JUDGMENT_SELECTION_EPISODE`；
- 前瞻冻结附件、迭代卡、操作流程、方法大纲与飞轮同步引用该筛选；`NEITHER` 只能回读冻结清单或登记新机制，不能事后改称“旧反方”。

### 合成复测、裁决与验收

在[干跑 03 的 P-53 复测](TURTLE_WORKFLOW_DRY_RUN_03.md#8-p-53-再测试h-ah-b-会不会静默漏掉仍然可信的第三机制)中，耐用品公司 B 的 H-A（履约修复）与 H-B（竞争侵蚀）均能就下一期交易量给不同预测；H-C（外部可达性冲击）同样解释当前“交易量下降、完成率改善”，但在允许材料中没有可分叉的官方观察。旧流程会静默删去 H-C 并容许选 H-A；新表将 H-C 标为 `DEFER_NO_PRIMARY`，输出降为 `MECHANISM_SIGNAL_PROBE / NO_PRIMARY`。复测没有读取结果，也没有判断 H-C 是否真实，故只说明输入规则在这个反例中阻止了伪二分。

`MODIFY / L0_SYNTHETIC_RETEST_PASSED / DESIGN_NOT_LIVE_TESTED`。经济影响是防止以遗漏的天气、渠道、会计边界、行业需求或其他共同原因，误写成公司特异竞争持续性、正常盈利或 owner-cash 的中心判断。禁止以“已写最强反方”“两个谓词均可结算”“后来结果符合 H-A”、报告数量、价格或回报声称候选空间已完整。真实验收需至少一个 cutoff 前可复读的三候选机制集合：每项有可审查处置；若存在 material `DEFER_NO_PRIMARY`，选择资格被拒；其 H-A/H-B 信号仍可按原合同结算；跨不同对象后才可研究这种筛选是否减少假二分且没有机械地扩大弃权。此前 P-53 不产生公司结论、方法准确率或概率。

## 迭代 P-54：假设空间筛选会不会把无关担忧变成过度弃权？

### 原始问题

P-53 正确要求保留仍可信、会材料性改变当前问题的第三机制；但“material”若只是一句自然语言，研究者也可以把任何宏观、成本、会计或治理担忧放进同一个 H-A/H-B 问题，令 `DEFER_NO_PRIMARY` 无限扩大。这同样会损害判断力：不是伪造中心路径，而是把本可结算的客户、竞争或渠道机制拖入无边界弃权。

根因是 `REASONING`，次要为 `WRITING`；不是 `DATA_COVERAGE`。缺的不是更多报告，而是候选若为真时究竟会令**本轮**哪个经济边界、机制箭头、FJ、来源任务或选择资格不同的位移说明。

### 修改

- 假设空间表新增“若为真会位移的当前经济边界 / FJ / acquisition 动作”列。material candidate 必须同时解释共同事实、有不同因果顺序，并造成至少一项可定位位移；
- 新增 `OUT_OF_SCOPE`：不解释共同事实或不位移本轮问题的事项不会被判假，也不会触发 `NO_PRIMARY`；它必须留下另一条独立问题或资料任务；
- `OUT_OF_SCOPE` 不可作为 `EXCLUDE` 的替代，也不可删去一个实际会改变本轮 FJ 的候选；仍可信且有位移、但没有分叉观察的候选继续是 `DEFER_NO_PRIMARY`；
- 前瞻冻结、迭代卡、操作流程、方法大纲、飞轮均同步这条位移定义。

### 合成复测、裁决与验收

[干跑 03 的 P-54 复测](TURTLE_WORKFLOW_DRY_RUN_03.md#9-p-54-再测试会不会把与当前问题无关的担忧也变成第三机制)在“交易量下降与完成率改善”的合成问题中加入 H-D（大宗商品套保到期可能压低报告毛利）。H-D 可形成独立的毛利/现金转换研究问题，却不能解释当前共同事实，也不位移交易量 FJ 或该 pair 的选择资格，故固定为 `OUT_OF_SCOPE` 而非 `DEFER_NO_PRIMARY`。这与 P-53 的 H-C 形成对照：H-C 能解释共同事实且会位移交易机制，才足以阻止中心路径。

`MODIFY / L0_SYNTHETIC_RETEST_PASSED / DESIGN_NOT_LIVE_TESTED`。经济影响是防止以无关成本、会计、宏观或治理担忧伪造“研究更谨慎”，从而延误对竞争持续性、正常盈利与现金转换的真正可结算判断。禁止将 `OUT_OF_SCOPE` 解释为该事项不真实/不重要，或将“它令人担心”当成当前 pair 的 material displacement；也禁止用 `DEFER_NO_PRIMARY` 的数量、价格或回报来评价研究。真实验收是一个 cutoff 前机制筛选卡：reviewer 能指出一项无位移候选被错误标 material，或一项有位移候选被错误标范围外；不同对象的随后 FJ 结算才可检验该边界是否既减少伪二分又未机械扩大弃权。此前 P-54 不产生公司结论、准确率、概率或方法优越性。

## 迭代 P-55：环境变化会不会成为事后免责，或把正常波动误判为断裂？

### 原始问题

公司与行业机制本来依赖制度、渠道、监管和竞争环境；若结果不符，研究者很容易说“环境变了”。现有 `critical_assumptions` 能验证必要前提，且 learning note 有 `STATE_REPRESENTATION`，但研究工件没有要求环境适用条件、可观察断裂和触发动作的完整链。环境因而要么成为无边界的事后免责，要么真实的制度断裂又被机械结算为旧 H-A/H-B 输赢。

根因是 `REASONING + WRITING`，而非 `DATA_COVERAGE`。经济影响是会材料性错误判断竞争持续性、正常盈利、现金转换与资本配置：正常需求/价格/利率波动会被拿来掩盖机制错误；真正改变交易点或指标含义的政策/制度事件则会污染原环境下的学习样本。

### 方法依据与修改

Kahneman 与 Klein 的[判断专长边界](https://doi.org/10.1037/a0016755)强调反馈必须来自有足够规律与可辨识性的环境；Remus、O’Connor 与 Griggs 的结构反馈研究说明，只给结果而不指出任务结构变化，不能可靠改进判断。这些来源支持让环境条件成为事前可检查的状态边界；它们不支持把任何未预测冲击都解释为研究免责。

- 机制实验卡与前瞻冻结附件新增“适用环境与 regime break”：cutoff 状态/一手来源、被约束的 pair 箭头/FJ/assumption、预定义 break observation/允许来源/窗口，以及 `CONTINUE_AS_IN_SCOPE / CLOSE_AND_REFREEZE_NEW_EPISODE`；
- 只有会改变 H-A/H-B 因果顺序、指标含义或双方可比较性的条件可进入此表。正常周期、需求、价格、竞争和利率变化仍是 pair 的共同状态；
- 合格 break 触发时保留 trigger 与 raw outcome，却不将该 outcome 用作旧 regime 下的主路径选择、迁移或 L3–L5 证据；新环境必须用新 cutoff 重建 episode。没有冻结 condition 的“环境变化”只可开启新问题；
- learning review 复用既有 `STATE_REPRESENTATION`，但只有 condition ID、break observation 与预注册 close/refreeze action 齐全时才能写 `ENVIRONMENT_REGIME_BREAK`。不新增事后 taxonomy、环境分数或自动解释器。

### 合成复测、边界与验收

[干跑 03 的 P-55 复测](TURTLE_WORKFLOW_DRY_RUN_03.md#10-p-55-再测试环境条件会不会在结果后才成为借口)冻结了“许可仍允许 app 销售”条件与监管禁令这一 break。正常促销或同业价格变化继续由 H-A/H-B 结算；监管禁令则关闭旧 episode、保留 raw source、重建新 cutoff。未被预注册的禁令不能回写成旧 pair 的既有环境条件。该合成输入未读取公司结果、也不声称程序能自动语义识别触发。

`MODIFY / L0_SYNTHETIC_RETEST_PASSED / DESIGN_READY_NOT_LIVE_TESTED`。禁止以一般宏观波动、管理层归因、价格或回报替代 break；也禁止因真实 break 而删除 raw observation 或称任一旧机制“被证明正确”。当前 production case/feedback 尚无该环境契约字段，故真实首次使用前仍需把 frozen condition → outcome source → feedback learning exclusion 接到同一可复查对象；在此之前不得把模板通过说成自动执行完成。验收是一个新前瞻 episode 的一手 trigger 在结果期被独立 reviewer 回读，且旧 episode 不进入 L3–L5 / learning note，新 episode 使用新的 cutoff 冻结。

## 迭代 P-56：状态相似的公司能否直接组成判断飞轮？

### 原始问题

此前 R-07 已拒绝 Lululemon、Target 与 Nike 的选择资格，但仍可能出现另一种便利抽样：看到多个公司“销售改善却交易/客流有歧义”，就把它们并列为 focal、near miss 与 boundary，仿佛相近的行业名称或 KPI 已经提供了可迁移的判断样本。这会把报告数量或页面上的数字相似性重新伪装成公司经验。

### 状态优先复筛

在不读取任何结果期材料的前提下，本轮只读三份截至 `2026-08-21` 的 SEC Exhibit 99.1：Chipotle Q2 的 comps `+2.2%`（check `+1.2%`、transactions `+1.0%`）、McDonald's U.S. comp `+0.8%`（正 check/mix、负 comparable guest counts）和 Domino's U.S. same-store sales `+0.1%`（company-owned `+2.1%`、franchise `0.0%`）。完整边界见 [R-07 状态优先 universe](experiments/R-07_selection_admission/01_state_first_candidate_universe_20260821.md)。

这三者都落在“表面销售改善而客户交易机制仍有歧义”的入口格，但没有一家公司出现只支持 H-A、同时反对 H-B 的 cutoff 前选择事实。更关键的是它们的后续候选指标分别为 company-defined transactions、comparable guest counts 与 same-store sales；最后一项还不能被 food-basket pricing 代替。因此既没有中心路径，也没有相同结果变量，不能形成 `1 + 1 + 1`。

### 裁决与后续验证

`RETAIN / REAL_PRE_OUTCOME_SCREEN / NO_SELECTION_CANDIDATE / NOT_A_FLYWHEEL_BATCH`。根因是 `DATA_COVERAGE + REASONING`，不是资料总量：缺的是每一候选在当时对同一机制叉有方向性含义的事实，以及跨对象可比的、冻结后再观察的经营结果定义。若错误把这些公司组成 batch，会把 check/mix、客流、交易和特许端的不同经济身份混成需求持续性，从而材料性误判竞争持续性、正常盈利、现金转换与永久损失。

禁止将连续改善、loyalty 增长、自营/特许分叉、同店销售、food-basket price、之后的业绩、价格或回报改称为选择依据或跨公司 replication。下一次只在新的 cutoff 前同时得到同一共同事实、A-only/B-only 当前观察、由此推出的不同同口径谓词及官方结果 contract 时才可重开；其后才可寻找有各自可能性条件证据链的 near miss 与 boundary。当前不建立 case register、FJ、source package 或 outcome package，也不声称判断力已经提高。

## 迭代 P-57：已拒绝的历史叙事会不会因“材料更多”而被重复打开？

### 原始问题

R-03 已有 [P&G/Trian、Darden/Starboard 与 ADP/Pershing 的结果前拒绝登记](R03_ARCHIVED_EXTERNAL_CANDIDATE_SCREEN_20260821.md)，但项目登记簿没有直接路由到它。一次新的外部档案探索因而可能再次把 Darden/Starboard 当作候选，仅因能找到不同的当时材料。复读其 2014-07-15 和 2014-09-09 SEC 原件后确认，它们仍只表达“改善执行/成本/餐厅表现”的广义愿景；没有原作者承诺的同口径经营指标、比较对象与窗口。本轮没有打开、下载或提取任何后续经营、价格或回报结果。

### 修改

- R-03 项目登记簿现在直链候选拒绝登记，并明确 P&G/Trian 2017、Darden/Starboard 2014 与 ADP/Pershing 2017 的 `NO_ADMISSION` 状态；
- R-03 intake 在任何新的原件阅读前先查该登记，并以 `entity / actor / cutoff / question` 识别同一争论；
- 已拒绝对象只能由此前未读、结果前且直接补足“原作者谓词 / 窗口 / 常规官方结果通道”之一的原件重开。更多 proxy 材料、估值、治理讨论或任何结果期资料不构成重开理由。

### 结论与后续验证

`MODIFY / REAL_PRE_OUTCOME_REENTRY_BLOCKED`。根因是 `REASONING + ACQUISITION_MODULE`：缺失的是一个把既有拒绝裁决送回下一次候选路由的最小接缝，而不是更多案例材料。若不修复，研究会反复选择材料丰富、名气大的公司，最终可能把宽泛行动叙事错误沉淀为组织、竞争、正常盈利、现金转换或资本配置的可迁移经验。禁止把重新检索到的当时材料、代理权之争结果、董事会变化、后续 KPI、价格或回报解释为新的可结算谓词。接纳条件是下一次 R-03 候选在读取原件前可定位已有 disposition；若为重开，登记必须给出此前未读的结果前原件及其逐项补足的合同字段，否则维持 `NO_ADMISSION`。这只降低重复探索，不构成外部档案的成功、Turtle 盲测、公司结论或判断力提升。

## 迭代 P-58：研究准备会不会自己变成无终点的“研究”？

### 原始问题

P-01 至 P-57 已建立了问题、反方、冻结、结果采集、结算、反馈和跨对象选择的 L0 链；R-05/R-06 也已在真实未来结果前冻结。但在没有新的到期 observation、合格 selection candidate 或运行失效时，仍可以无限加入抽象模板、schema 和历史材料。这会重演用户指出的“一个公司没有尽头”：对象从格力换成研究框架，实质仍是逃避反馈。

### 修改

- 操作流程新增 `L0_READY_TO_WAIT_FOR_REAL_FEEDBACK` 停止状态；
- 新的 L0 方法改动只接受三种触发：冻结 signal 到期、通过准入的新对象，或真实运行中已定位的材料性失效；
- P-55 的环境断裂生产接线保留为首次出现冻结 condition 的正式 CJO episode 的准入条件。当前没有此类对象，不为它创建平行 schema 或假装已完成真实验收。

### 结论与后续验证

`RETAIN / PREPARATION_STOP_RULE_ACTIVE`。根因是 `REASONING + MODEL`，不是 `DATA_COVERAGE`：缺失的是把“方法已可运行”切换为“等待外部经营反馈”的行动规则。若不设此门，研究资源会从最快产生校正的结果期采集转移到无验证的框架复杂度；长期会延迟对竞争持续性、正常盈利、现金转换和资本配置判断的真正纠错。禁止把更多报告、更多历史故事、更多 agent、更多 gate 或价格/回报当作这三类触发的替代。接纳条件是下一项 P-xx 能明确指向一个到期 claim、一个已准入的新 episode，或一条已有运行日志中的材料性 failure；否则保持等待，不称其为新的方法进展。该规则不表示判断力已被证明，只保证下一轮开始于能让飞轮转动的外部输入。

## 迭代 P-59：等待真实前瞻结果，会不会被误作停止判断训练？

### 原始问题

P-58 的字面“等待外部经营反馈”容易被执行成整个研究停止：R-05/R-06 的未来经营 observation 尚未到期，似乎就不应再做任何训练。但这把两项不同工作混为一谈：无触发地扩张 L0 schema/模板，和用既有、可结算的 archive case 反复练习机制分叉、测量辨别与错因复盘。前者确实会逃避反馈；后者正是让反馈频率高于数年终局的必要条件。

### 修改

- 将 `L0_READY_TO_WAIT_FOR_REAL_FEEDBACK` 明确定义为“架构停止状态”，而非研究或训练停止状态；
- archive exercise 只要使用既有准入、outcome firewall、冻结和结算合同，就可在真实前瞻等待期间运行；它必须标为 `HISTORICAL_SELF_REPLAY` 或 `ARCHIVED_EX_ANTE_EXTERNAL`，不进入 Turtle 自身准确率；
- 中国作为核心 archive 训练域；美国等海外案例只承担共同机制原语的边界/近失效检验，必须显式写出渠道、监管、集中度、分销、会计或资本强度等断裂条件，不能证明中国公司的参数。

### 结论与后续验证

`MODIFY / TRAINING_AND_VALIDATION_CLOCKS_SEPARATED`。根因是 `REASONING + MODEL + WRITING`：此前缺少“训练的快速历史反馈”和“能力的未知结果验证”之间的运行分工。经济影响是双向的：错误停摆会使研究者只等少量慢反馈；错误合并又会把已知历史包装成实时能力，二者都会扭曲对竞争持续性、正常盈利和 owner cash 的判断信心。缺失的不是更多美国报告或格力 chronology，而是一批按中国机制状态、结果前材料和独立结果合同筛选的 archive episode。禁止将海外案例直接迁移为中国参数，也禁止将 `HISTORICAL_SELF_REPLAY` 写为 Turtle 命中、准确率或校准。接纳条件是先以一项中国 archive candidate 通过既有 outcome firewall/metric-reconstruction gate，完成冻结与独立结果结算，再验证其 learning note 是否在下一家中国公司的冻结字段中留下可审查的改变；真实前瞻仍单独负责外部有效性。

## 迭代 P-60：完整结算门会不会使判断训练过少、过慢？

### 原始问题

现有完整迭代卡同时容纳 L0–L5、CJO、PIT、结果采集和 cohort 约束。它适合正式 episode，却会让每一次历史练习在产生 H-A/H-B 前先承担完整生产研究的负担。若研究者因此改为随意读案例，训练失去冻结和反馈；若干脆不练，则只剩少量真实前瞻结果，无法形成刻意练习。另一个风险是先读管理层解释，再把它翻写为自己的机制，造成确认偏误。

### 修改

- 新增一张不产生公司结论的机制判断微演练卡：只要求一个经济问题、共同事实、独立的 H-A/H-B、一条非嵌套观察和结果合同；
- 强制“两遍”：先只读事实并写自己的机制，后读管理层/原作者解释并攻击它；
- 没有结果合同、隔离或双方分歧的卡只能 `QUESTION_ONLY / UNDIFFERENTIATED`，不能因轻量而放松；完整来源/隔离/独立性到位时才升级正式 episode；
- 中国为微演练的核心队列，海外只能标作边界/近失效，且必须写明不同的结构条件和受影响箭头；报告期结束后的业绩预告不构成事前经营训练样本。

### 结论与后续验证

`MODIFY / TWO_TIER_PRACTICE_DESIGN_READY`。根因是 `REASONING + WRITING`：完整结算纪律被误作每次训练的入口，且没有明确的“先判断、再读解释”顺序。经济影响是研究者要么把管理层叙事误当判断，要么因流程过重而以报告阅读代替可纠错练习，长期削弱对竞争持续性、正常盈利、现金转换和 owner cash 的辨别。缺失的是一次中国 archive 微演练从预结果冻结到结果复盘、再到不同中国对象字段改变的实际运行证据；不是更多模板或美国案例。禁止将微演练记为 Turtle 命中、让结果已知的教学案例升级、用结果后业绩预告冒充预测，或把海外结论迁移为中国参数。验收条件是第一张中国微演练在不读 outcome 的情况下完成 H-A/H-B 与同口径合同；结果后要么机械形成 verdict，要么明确 `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`，并将 learning change 定位到下一张中国卡。

### P-60.1：网页/表格结构会不会让“先读事实”仍泄漏公司解释？

首次以 NIO 2023 Q1 原始 HTML 试读时，表格节点同时含有季度交付、车辆毛利等数值与“主要由于”等归因段落。若将“table”机械当成事实层，研究者会在写 H-A/H-B 前已读到公司的机制解释，两个阶段只剩形式。

修复：微演练现在要求第一遍事实包的精确 locator 与准备方式；`INDEPENDENT_CURATOR` 或 `FROZEN_STRUCTURAL_EXTRACT` 才可以作为两遍干预的合格输入。混有归因/预期的 HTML table、PDF 同页或直接阅读均为 `CONTEXT_SEPARATION_NOT_ASSURED`，只作流程教学。根因是 `ACQUISITION_MODULE + REASONING`，经济影响是管理层叙事会被误记为研究者独立机制，污染后续竞争、利润率和现金传导学习。缺失的是事实/解释可分离的源片段，而不是更多公司材料；禁止用页面标签、事后记忆或“我会忽略解释”替代切片。下一张未读中国候选必须证明事实包不含归因，才可验收 P-60 的两遍训练。

### P-60.2：排除整段归因，是否会反而丢掉真正的量价成本变量？

R-10 的中通 Q1 原件把“单件价格下降 3.7%、单位运输成本下降 10.6%、单位分拨成本下降 11.1%”等可计量事实与公司对其原因的文字放在相邻或同一叙述段。若把含 `due to` 的整段一律排除，第一遍只能以“总收入/件”替代单件价格，混入附件和其他收入，机制输入会变宽、甚至失真。

修复：新增 `FROZEN_METRIC_SLICE`。独立 curator 或固定抽取器可在研究者见到原文前仅交付 `指标标签、数值、单位、期间、locator`，将同段归因隔离到第二遍；研究者若已经见到完整段落，必须仍标 `CONTEXT_SEPARATION_NOT_ASSURED`。根因是 `ACQUISITION_MODULE + REASONING`；经济影响是把真实的价格—单位成本分叉误写为宽口径收入变化，错误判断网络效率、正常利润和竞争压力。缺失的是可复读的事实切片而非更多报告；禁止把公司归因当事实、也禁止用总收入/件自动等同于单件价格。验收是下一张未读中国卡的第一遍能引用至少一条这个格式的量/价/成本切片，而第二遍才出现相邻归因；若做不到，只能降为 `CONTEXT_SEPARATION_NOT_ASSURED / NO_PRIMARY`。

### P-60.3：结果合同能否只靠“预计某日附近的 filing”定位？

R-10 预先登记了 2023-08-17 的 SEC 附件为 Q2 结果期材料；结果揭示后才确认中通的 Q2 业绩事件实际由公司在 2023-08-29 发布。两个文件日期相近不构成同一结果事件。若把刚看到的正式业绩替换进旧卡，任何“同口径 B/A 结果”都会带有事后挑选来源的问题。

修复：微演练的结果合同现在必须在 cutoff 前冻结 `publisher + result event + expected window + pre-locatable calendar/URL metadata + same-metric label`，而非仅猜测 SEC/HKEX 提交日。根因是 `ACQUISITION_MODULE + REASONING`；经济影响是结果源的事后替换可把本不存在的机制结算写成有效反馈，污染对单位经济、正常盈利和竞争持续性的学习。缺失的是发行人预告/连续披露链对结果事件的明确定位，不是更多结果数据；禁止用结果公布后发现的公司页面、新闻、价格或回报追补旧 locator。验收是下一张中国卡在 cutoff 前已登记可复读的公司公告日历或连续结果页，结果期只打开该事件；若实际事件不符，标 `OUTCOME_SOURCE_CONTRACT_MISMATCH` 并关闭，不改卡。

### P-60.4：关键词黑名单能证明第一遍没有读到叙事吗？

腾讯音乐候选的静态抽取虽屏蔽了常见归因词，却仍从一个表格节点输出了“Emerging Force Program”的项目介绍及其目标。它不是数值事实，而是管理层对行动/机制的叙事；HTML 的 `<tr>` 边界和关键词黑名单都不能保证“先事实、后解释”。该候选因而只保留为 exposure 记录，不进入冻结卡。

修复：`FROZEN_METRIC_SLICE` 改为 allow-list：冻结前明确允许的精确指标标签，抽取器只能交付这些标签的数值、单位、期间和 locator；任何不匹配的叙事段一律留给第二遍。根因是 `ACQUISITION_MODULE + REASONING`；经济影响是研究者会在写机制前不自觉吸收公司项目叙事，后续的 H-A/H-B、利润和竞争判断看似独立实为锚定。缺失的是标签级事实边界，而不是更多报告；禁止以“没有出现某几个词”“页面在表格中”或研究者自称忽略为无泄漏证据。验收是下一未暴露中国候选的第一遍输出仅含预列标签/数值/单位/期间/locator；任一项目说明、预测、归因或管理层引语出现即停止该卡，不在结果期结算。

## 迭代 P-61：现有飞轮会不会只训练“研究解释”，却遗漏经营者的决策判断？

### 原始问题

现有方法已要求状态、竞争机制、结果合同、结算和迁移，但“管理层作出什么可行选择、付出什么资源、面对什么组织约束、相对于什么替代方案”并不是每张训练卡的强制中心。于是研究者可能形成一条完整的 H-A/H-B 解释，却仍把实际战略当成既定背景，无法训练企业家式的行动判断；行业反应和长期资本后果也容易被拆成附录。

### 修改

- 新增[企业经营判断训练方案](TURTLE_ENTERPRISE_JUDGMENT_TRAINING_BLUEPRINT.md)，以“状态 → 决策 → 外部反应 → 经营传导 → 资本后果 → 下一题改变”为总对象；
- 新增[企业经营判断卡](../../../templates/research_enterprise_judgment_card.md)，在同一页强制列出实际决策、可行替代方案、维持原状、资源/组织/激励、竞争回应与资本传导；
- 明确区分当时的**决策质量**与结果期的**经济效果**。没有可比对照时只能写 `CONTRIBUTORY / INSUFFICIENT_ATTRIBUTION`，不能把后果自动归因于管理层；
- 既有 PIT、事实/解释两遍、H-A/H-B、结果隔离、学习应用和中国主训练域保持不变。不新增 schema、概率模型、报告要求或格力材料任务。

### 结论与后续验证

`MODIFY / PRE_RESEARCH_BLUEPRINT_READY / DESIGN_NOT_LIVE_TESTED`。根因是 `REASONING + MODEL`：缺失的是把企业家、行业专家与长期所有者放进同一因果单元的训练语法，而不是更多公司数据、更多报告或更复杂的回测代码。若不修复，agent 可能把事后正确的行业叙事误当作可执行的管理判断，进而错误归因正常盈利、现金转换、资本配置和永久损失。禁止将交割完成、短期业绩、管理层愿景、名家声誉、价格或回报替代替代方案、资源约束、竞争回应和同口径经营结算。

接纳条件是：先用两张不同中国 archive 微演练运行判断卡；每张在结果前均能写出实际/替代/不作为三项、双方非嵌套观察及结果合同。结果后必须把错误定位在 `STATE / DECISION / MEASUREMENT / MECHANISM / TRANSMISSION / ENVIRONMENT` 之一，并让第一张的 learning note 在第二张不同对象的冻结前字段中留下可审查改变。此前只能称方案已就绪，不称 agent 已获得企业家、行业专家或投资者判断力。

## 迭代 P-62：中国早期家电竞争能否作为训练域，而不退化为“三家幸存者”故事？

### 原始问题

用户提出中国早期家电竞争拥有丰富素材，且希望同时学习通用机制与历史特定条件。若直接以今天常说的海尔、美的、格力“三家幸存者”为样本，会在结果已知后挑选赢家，把不同产品 arena、产权、渠道、地区和周期混为单一管理能力；这会使所谓企业家判断退化为成功者叙事。

### 修改

- 新建[中国家电竞争史训练地图](CHINA_APPLIANCE_COMPETITION_TRAINING_MAP.md)，先以产业状态、产品 arena 和实际决策 episode 建立候选宇宙；
- 将问题改为“不同约束下，哪些决策机制在何时有效、何时断裂”，而不是“谁做对了”；
- 1990 年代家电由政策/计划安排转向市场竞争、并经历产能过剩和外资进入，只作为共同环境；1996 年的行业参与者列表只用来反对预选三家，并不作为公司质量证据；
- 先在同品类 arena 内选择一项决策，再寻找只翻转关键中介的近失效和只改变外部条件的边界复验；后续结果继续隔离。

### 结论与后续验证

`RETAIN / TRAINING_UNIVERSE_DISCOVERY_OPEN / NO_EPISODE_FROZEN`。根因是 `REASONING + DATA_COVERAGE`：当前缺的不是更多成功者资料，而是每个 arena 的同期一手决策材料、可行替代方案和同口径结果合同。若不做上述拆分，可能把行业从卖方转买方、外资进入、产品差异和资本边界误归因于企业能力，材料性污染正常盈利、现金转换、资本配置和永久损失判断。禁止用今天是否存续、后来的规模、书籍声誉、后来的利润、价格或回报选择案例或裁决机制。

接纳条件是：第一张中国家电卡必须在一个明确产品 arena 和 cutoff 前，同时写出共同状态、实际/替代/不作为三项、H-A/H-B 的不同观察，以及可独立打开的同口径结果包；若任一项不能取得，保持 `QUESTION_ONLY` 并切换 arena。该训练域目前只证明候选结构已更诚实，不证明任何公司、通用机制或 agent 判断力。

### P-62.1：房间空调 1995–1997 的首次 intake 会不会把结果摘要倒灌成“渠道判断”？

已定位到格力 1996 年年度报告摘要，但检索摘要本身已经暴露了当年产量、收入、利润及公司对质量/服务的自述；春兰同窗口的完整原始决策和同口径结果合同仍未定位。故该题材当前标记为 `RESULT_KNOWN_TEACHING_ONLY / NO_ADMISSION`，不作为盲练或学习样本。

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`：缺少的是同一 cutoff 前的竞争双方原始决策、共同产品事实和独立结果包，而不是格力的更多历史材料。若继续把这份摘要扩写为成功解释，会将结果、公司自述和后来存续地位误归因于渠道、质量或管理能力，材料性污染竞争持续性、正常盈利、现金转换和资本配置判断。禁止用总收入、利润、上市主体信息、今天的品牌地位或行业综述补足产品级机制。修复动作是切换到尚未暴露的同品类候选，或将本题仅作反向教学；正式重开条件已写入训练地图 §9。

### P-62.2：能否把“质量、技术、渠道”直接当作家电竞争的通用成功机制？

不能。1995–1996 的同期行业材料一方面显示质量、品牌、价格和服务均被消费者/市场视为重要；另一方面，春兰的同期报道也记录了其质量、技术、规模和研发动作，春兰与华宝还都在维护渠道价格纪律。它们是**共同竞争动作**，而非自动解释企业后来差异的充分条件。

裁决为 `MODIFY / DEEPER_MECHANISM_REQUIRED`。根因是 `REASONING`：若把动作名词直接等同于能力，会忽略是否存在客户交易—渠道激励—组织执行—现金回收的闭环，也会掩盖产品结构、产能、融资和组织边界的历史条件。经济影响是将短期销量、市场份额或宣传性质量主张错误升级为竞争持续性、正常盈利和 owner-cash 判断。缺失的是同产品、同期间的价格实现、渠道库存/回款、服务成本、资本占用与实际组织安排；禁止以“研发多、服务好、规模大”、后来的品牌地位、价格或回报填补。接纳条件是下一张卡让 H-A/H-B 对上述至少两项经营变量给出非嵌套顺序，并使用 pre-cutoff 原件与结果合同结算；否则本轮只保留为问题升级，不作公司结论。

### P-62.3：历史材料若暂时没有完整结果合同，是否就不能训练企业判断？

不能把它们计作严格回测，但也不应丢弃。1996 年 10 月的同期《人民日报》记录格兰仕在国内微波炉厂商已逾 80 家、外资同时进入的状态下，对两款主销机型降价 40%；文中还明确出现“技术、服务不足以应对竞争”的当时公司解释。这是一个真实、可复读的经营动作和行业约束，但目前没有同一预先定位、可独立读取的产品级量价—现金结果合同。

若以“历史故事很多”为由把它直接计成成功案例，根因是 `REASONING + DATA_COVERAGE`：缺的不是再多一份格兰仕叙事，而是降价后真实消费、价格实现、成本/利用率、库存/回款与竞争跟随的同口径观察。经济上，销量或后来地位可能掩盖单位经济、现金转换和行业租金的损失，继而误判价格战、规模和资本投入。禁止以管理层归因、后来的龙头身份、市场份额或品牌名气替代这些结果。

但将其完全排除同样会浪费高价值训练。流程新增三层材料身份：`STATE_REPERTOIRE` 用于学习在何种状态下有哪些可行行动；`RESULT_KNOWN_TEACHING` 用于用已知历史训练替代方案与错误归因；只有 `OUTCOME_CONTRACTED_EPISODE` 才用于冻结—结算—迁移的判断反馈。格兰仕降价目前处于第一层，可用于实际/替代/不作为与 H-A/H-B 的预演，但不结算任何公司质量或 agent 表现。

`MODIFY / HISTORICAL_MATERIAL_LAYERS_DEFINED / NO_COMPANY_CONCLUSION`。下一步是为微波炉降价寻找独立、同品类且能在冻结前预定位的结果来源；若无法取得，则将它保留为高质量教学对象，并转向有公开披露链的另一 arena。只有找到量价、成本/现金或明确的测量错配后，才可升级为正式 episode；不因资料生动而降低门槛。

### P-62.4：同样是“降价”，能否当作同一种竞争机制迁移？

不能。1996 年同期材料记录两种表面相同、经济身份不同的价格事件：格兰仕作为制造商针对主销微波炉主动降价 40%，在“80 多家国内厂商 + 外资进入”的品类状态中声称要扩大份额、推动集中；同年空调市场中，春兰与华宝面对的是经销商先行降价，并以区域价格、待遇/制裁和渠道秩序回应。后者的报道同时也包含消费者欢迎低价的观点。

根因是 `REASONING`：若只把两者写成“价格战”或“渠道控制”，就抹掉了行动者、毛利承担者、产品采用阶段、对手成本位置、区域渠道边界与库存/回款约束。经济影响是会将暂时销量、渠道压货或区域套利误判为需求扩张、成本优势与可分配现金改善，进而误判竞争持续性和永久损失。缺失的是每个事件的终端量/价、库存或应收、单位经济/现金以及竞争者跟随的同口径观察；禁止以“消费者欢迎降价”、管理层整合叙事、品牌排名或后来存续填补。

修复是将价格问题改为五项冻结前查询：`谁降价且谁承担毛利 / 降价解决何种状态问题 / 对手能否以相近资源跟随 / 渠道合同与库存回款如何变化 / 至少哪两项量价、库存应收、单位经济现金指标会先分叉`。任一项未知，卡保留 `UNKNOWN`。`MODIFY / CONDITIONAL_PRICE_MECHANISM_ADDED / NO_COMPANY_CONCLUSION`；验收是下一张价格 episode 在读结果前写出上述五项，并让 H-A/H-B 对至少两项后续变量给出相反顺序。它仍不证明格兰仕、春兰或华宝的历史结果，更不产生通用参数。

### P-62.5：早年披露在今天的标准检索入口查不到，能否直接判为历史数据缺失？

不能。对巨潮当前标准全文索引的定向检查未返回 1995–1998 年间相关早年证券代码的记录；这只能说明该入口不提供这组历史全文，不说明当年的法定披露、行业统计或可定位报刊原件不存在。

根因是 `ACQUISITION_MODULE`，不是公司证据本身的 `DATA_COVERAGE`。若把检索 miss 改写成“没有证据”，会错误排除拥有原始档案链的 company/arena；若反过来用今日公司简介、结果摘要或后来的回顾填洞，又会泄漏结果，材料性扭曲行动、正常盈利、现金与资本配置判断。禁止从现行全文搜索、搜索引擎摘要或当前 IR 页面推断历史文件不存在。

修复是为每张早年卡在立项时明确四条 source route：法定历史静态文件/公司档案、同期产业状态源、同期竞争事件源、冻结前已定位的结果源。普通检索 miss 仅将路线一标为 `ACQUISITION_PENDING`；仍可作为状态或教学材料，不能提高或降低任何企业结论。验收是下一候选同时列出 source type、cutoff、locator 与该材料在事实/解释/结果三包中的位置；没有结果合同则按材料层级降级，而不是编造缺失。

### P-62.6：技术引进或合资交割，能否直接证明企业经营能力/长期价值提升？

不能。1996 年同期报道显示，扬子为获得合资资金和技术，让合资企业在冰箱、冰柜上使用“扬子”商标 50 年，并列出对价。它是可定位的产权与经营边界动作，但报道对资产增值、技术水平和未来竞争力的描述仍属于当时的公司/报道主张。

根因是 `REASONING + DATA_COVERAGE`：把技术、一次性对价、净资产重估或交割完成当作长期 owner outcome，会漏掉品牌与治理权转移、后续资本投入、产品成本、可得现金及控制权之间的传导。经济影响是高估“引进技术”的竞争持续性与资本回报，低估把未来租金让渡出去的风险。缺失的是交易条款、持续投资、产品/成本、权益现金流及治理权的同口径结果；禁止用无氟技术宣传、资产评估或后来公司命运补足。

修复是增加“技术/资本/品牌权利”作为独立决策域：每张卡强制问企业付出了什么经济权利、保留什么控制和现金权利、技术怎样进入产品和成本、以及失败时最早在哪一项出现。`MODIFY / CAPITAL_RIGHTS_MECHANISM_ADDED / NO_COMPANY_CONCLUSION`；验收是下一项技术或合资 episode 在结果前同时写出这些权利与传导，并以非嵌套的后续经营/现金观察结算。它不说明扬子的交易已经成功或失败。

## 迭代 P-63：第一轮中国家电教学复盘，是否真的改变了下一题？

### 原始问题

P-61/P-62 只证明训练语法和候选宇宙已设计好。若每个历史案例仍独立地被写成公司故事，所谓“飞轮”只是文件顺序，而不是上一案的失败改变下一案的输入。

### 实际运行

第一轮未从幸存者公司史开始，而是连续读取四种不同的经营动作：

1. [R-14 格兰仕 1996 降价](experiments/R-14_china_appliance_price_teaching/00_galanz_1996_price_learning_review.md)：后续材料同时出现规模扩张与持续进入，迫使价格案例新增 `entry_response`，禁止将份额/产能写为进入壁垒或 owner cash；
2. [R-15 春兰/华宝渠道价格](experiments/R-15_air_conditioner_channel_price_teaching/00_chunlan_huabao_1996_channel_price_review.md)：把“控价”还原为维修资格、费用结算和奖励的合同杠杆；后续只足以观察架构，不能裁决渠道经济，迫使下一案分开权利、组织与现金；
3. [R-16 扬子—博西西门子合资](experiments/R-16_yangzi_bosch_siemens_joint_venture_teaching/00_yangzi_1996_brand_and_control_review.md)：同一交易必须拆开出资、控股、品牌、营销、人员和现金权利；后来的逆风叙事不足以归因，因而不将对价/资产重估写成成功；
4. [R-17 海尔—红星组织整合](experiments/R-17_haier_redstar_integration_screen/00_1995_redstar_integration_screen.md)：已有“三个月扭亏”和年度产量的教学观察，但缺同主体的现金、库存、应收、质量和重组成本序列；它只能训练“短期扭亏不等于可迁移管理能力”。

每一案的 learning change 被写入下一案的 action/readiness 字段，且对象、品类或决策域发生变化。这完成了**教学层**的四次“结果 → 输入约束”迭代；它没有完成正式 PIT 回放，更没有提供 Turtle 自己的预测准确率。

### 结论与后续验证

`MODIFY / CHINA_TEACHING_FLYWHEEL_RUNNING / FORMAL_REPLAY_NOT_YET_STARTED`。

根因是 `REASONING + DATA_COVERAGE + ACQUISITION_MODULE`：早年中国案例的同期行动材料通常可定位，而可归因的经营结果多停留在后来回顾、统计片段或叙事中。若将这类材料全部排除，训练会退回等待未来；若把它们算成管理能力已验证，又会把幸存者叙事、宏观变化和会计口径混入正常盈利、现金转换、资本配置和永久损失判断。

因此保留三层：本轮作为 `RESULT_KNOWN_TEACHING`；只有补齐结果前事实包与同口径 outcome package 的案例可升为 `HISTORICAL_SELF_REPLAY`；只有真实未知结果才验证 Turtle 自己的判断。禁止用四案的结局、后来的行业地位、公司宣传、价格或回报计算方法胜率、概率或“agent 已具备企业家判断力”。

下一动作不是继续累积家电故事，而是按 [中国早期家电 episode 队列](CHINA_APPLIANCE_DECISION_EPISODE_BACKLOG.md) 只为一个具备原始/统计来源路线的候选建立行动前事实包与结果包。验收条件是：同一经营主体、明确 cutoff、H-A/H-B、非嵌套早期和终局指标，以及隔离结果包全部就位；若任何一项缺失，保留教学层并换 arena，不以更多叙事补洞。

## 迭代 P-64：组织能力训练会不会仍把集团增长误当作分权的结果？

### 原始问题

R-17 已经要求组织整合拆开控制权、人员与现金承接；但这还不足以处理多品类集团的组织变革。美的 1997 年事业部制的材料显示：同一公司会同时出现上市公司审计收入、集团口径销售额、产品公司与后续品牌叙事。若没有责任单元和主体边界，研究者仍可能以“改革后规模增长”跳过组织动作真正改变了谁的决策、谁的损益和谁的营运资本。

### 实际发现与修改

R-18 取得了两类相互不能直接相加的材料：1997 年上市公司经审计合并报表，及公司官网对 1998 年全球营收的时间线。二者的主体边界不同；公司本身 1999 年报列示的 1998 上市公司主营收入又是另一可比口径。因此，这不是销售增长的验证，而是一次成功识别出的 `MEASUREMENT_MISMATCH`。

组织类训练自此将 `operating_control` 细化为：`decision_right`、`accountability_unit`、`incentive_and_exit` 和 `boundary_consistency`。进入正式回放的最低门槛变为：行动前至少两项权责字段 + 结果期同一责任单元的两期经营与营运资本/现金观察。没有这些字段，历史材料可教学，但不能裁决分权、收购整合或管理系统的经济效果。

### 结论与后续验证

`MODIFY / ORGANIZATION_BOUNDARY_GATE_ADDED / NO_COMPANY_CONCLUSION`。

根因是 `REASONING + DATA_COVERAGE + ACQUISITION_MODULE`：不是缺一个更漂亮的美的成功故事，而是行动、责任单元与结果数据没有落在同一主体。经济影响是会将并表范围、扩产、周期或渠道投入造成的收入变化，误归因于组织能力，进而高估正常盈利、owner cash 与资本配置质量。禁止从集团销售额、品牌排名、后来的职业经理人、股价或回报推断 1997 年分权成功。

下一次组织类候选必须在读结果前指定责任单元和同一主体结果合同；若旧案例无法补齐，继续保持 `RESULT_KNOWN_TEACHING` 并换 arena。验收不是“查到更多美的资料”，而是下一张冻结卡能让 H-A/H-B 对同一责任单元的经营和现金观察给出不同顺序。

## 迭代 P-65：危机并购能否成为第一张有结果合同的企业判断训练卡？

### 原始问题

第一轮 1990 年代教学案例分别暴露了价格、渠道、权利交易和组织整合的归因难题，但缺同主体的法定经营结果。若因此只继续找更精彩的早年故事，训练仍停在“知道应该谨慎”。

### 实际发现与修改

R-19 找到一个不同形状的中国白电对象：2005 年科龙董事会收购文件同时包含危机状态、控制权安排、预付款、代理费、价格权与营销费用责任；2006、2007 年同一上市公司的法定年报也可定位。由此，危机收购可不再只写“买了品牌”，而被拆为 `信用/供货/渠道/生产恢复` 与 `补贴/重述/营运资本/owner cash` 两条可竞争的机制。

当前主研究者已经在检索中看到 2006 年收入、净利、补贴与保留意见摘要，因此本轮不伪称完成盲测；它只登记了一条可由未接触结果包的流程执行的 `HISTORICAL_SELF_REPLAY` 路线。

### 结论与后续验证

`MODIFY / CRISIS_ACQUISITION_OUTCOME_ROUTE_IDENTIFIED / BLIND_REPLAY_NOT_YET_RUN`。

根因：`ACQUISITION_MODULE + REASONING`。早期案例并非没有历史结果，而是没有把行动文件与同主体、同口径的后续年报预先连成结果合同；一旦补上，真正风险立刻从“资料不足”转为“补贴、重述和账面利润是否掩盖 owner cash”。经济影响是若跳过这一步，危机收购的收入恢复会被误当作竞争力与资本配置成功，低估营运资本、供应商信用和遗留负债的永久损失风险。

教学结算已按 2006→2007 同口径完成：R-19 出现的是 `EARLY_MECHANISM = MIXED` 与 `TERMINAL_OPERATING_SELF_SUSTAINABILITY = SUPPORTS_RIVAL`，不是交易总成败。当前研究者已接触结果且缺 cutoff 前的具体年报事件预告，故仍不是严格盲回放。真正的下一动作是把该 learning note 应用到**不同中国对象**的危机/整合 card：冻结 `bridge_funding_terms / recurring_earnings_bridge / cash_conversion_bridge / two_period_persistence` 四项；验收是这四项确实先于结果被写进下一卡，而不是事后复述科龙。仍不计算准确率，不用价格或回报，也不以“最终活下来”替代结算。

## 迭代 P-66：R-19 的危机整合教训能否在不同市场状态中改变结论？

### 原始问题

R-19 已把危机接管从“收入/净利恢复”改为资金桥、经常性盈利、现金转换和两期持续性的组合问题。但若下一案仍是同一类国内白电危机，方法可能只是在重复熟悉的会计形状，尚未证明这套问题能处理技术、渠道和组织结构都发生变化的整合决策。

### 实际应用

R-20 选择 TCL—汤姆逊：它是不同公司、不同产品 arena 和跨境边界案例，但仍是中国耐用电子企业承接亏损业务的资本配置/组织问题。冻结卡在读 2005–2006 年报前，已逐项写入 R-19 的四项字段，而不是只写“18 个月扭亏”：

1. 交易/融资的适用边界，禁止把集团过桥融资自动归于 TTE；
2. 欧美地域经营结果与 TTE 持续经营结果、重组和利息项目的分离；
3. OCF 与存货、应收、应付、融资的现金转换桥；
4. 2005–2006 两期持续性；
5. 新增 `operating_control_completeness`：销售、营销、售后等商业职能是否真的与资产一同转入控制。

结果没有被压缩成“销量大而失败”：2005 欧美收入和销量高但经营亏损，且商业控制仍在交接；2006 出现正 OCF，但同时为巨额持续经营亏损、重组和应收/存货释放。由此，教学结算为 `EARLY = MIXED_WITH_RIVAL_SIGNAL`、`TERMINAL = SUPPORTS_RIVAL_FOR_ORIGINAL_INTEGRATION_PATH`、`CASH = NOT_DIAGNOSTIC_AS_OWNER_CASH`，并保持交易总价值 `UNKNOWN`。

### 结论与后续验证

`RETAIN_AND_NARROW / LEARNING_APPLIED_TO_DIFFERENT_COMPANY / NOT_GENERALIZED`。

根因：`REASONING + DATA_COVERAGE`。若忽略经营控制的完整度，就会把一纸资产/股权合并当作完整机制已经执行；若忽略营运资本桥，就会把正 OCF 当作经营自立。经济影响是高估整合后正常盈利和 owner cash，低估技术转换、渠道控制、重组与流动性释放导致的永久损失。缺失的是 TTE 内原汤姆逊业务逐项现金和营运资本归属，以及无合并反事实；禁止从总体销量、规模、年末现金、后来品牌位置、价格或回报补足。

下一张不同中国对象必须先填五项字段；若行动本身未将产品、采购、销售、营销、售后、定价和渠道控制中的至少一项从原方移交，就不能以“整合协同”作为中心机制。验收是卡中所有 H-A 箭头都指向一个已发生或有明确交割时点的控制权转移，并且结果期的 OCF 同时列示营运资本变化。仍不把两张历史教学卡当作 agent 准确率、概率或跨行业规律。

## 迭代 P-67：渠道增长是否能训练“客户关系”而不是训练事后收缩？

### 原始问题

R-19/R-20 已将整合决策拆成控制、经常性盈利、现金转换与持续性，但它们仍是资产接收题。若没有渠道信用案例，agent 仍可能在“销量、收入、品牌/重点客户”上把商业关系误认成现金能力；反过来，连续选择失败案例又会把训练变成事后厌恶扩张。

### 实际应用

R-21 以长虹 2002 年报为 cutoff：海外收入高速增长，但 APEX 应收 4.627 亿美元、经营现金流 -29.74 亿元、短借大幅上升同时可见；公司下一年仍公开提出深耕北美等国际市场。2003/2004 结果分别显示应收继续增加、OCF仍负，以及后来的大额减值和停止业务。

它的有效结论不是“出口错误”，而是：在既有 AR、OCF、现金和短借已经反向时，必须把客户信用视为经营决策的一部分。由于没有找到 cutoff 前关于 APEX 信用限额、担保、停发货权或责任人的一手文件，R-21 保持 `NO_PRIMARY`，不评价具体管理者的选择。

### 结论与后续验证

`MODIFY / CREDIT_GOVERNANCE_VISIBILITY_ADDED / POSITIVE_NEAR_MISS_REQUIRED`。

根因：`REASONING + DATA_COVERAGE`。若把收入、出口额、期后托收票据或客户名气视作渠道能力，会错过信用成本和营运资本已经吸收现金的信号；若以终局坏账反过来禁止一切海外赊销，则又会把单一失败机制误当作通用法则。经济影响是前者高估正常盈利和 owner cash，后者错误放弃有正回报的客户/渠道投资。缺失的是客户信用合同、限额、保险/保理、终端 sell-through 和内部责任人；禁止用后来坏账、诉讼、价格或回报填补。

下一步不继续查长虹的追债细节，而是在不同中国公司筛选一个 `high-growth + customer concentration` 但拥有可见信用治理、并能以同口径现金结果复盘的近失效或正例。验收是两案都在结果前冻结 `credit_governance_visibility`，且未来观察能区分“客户关系带来现金”与“客户关系消耗现金”；在找到对称样本前，不从 R-21 输出“扩张应收一定差”的规律。

## 迭代 P-68：信用保险与低集中度，能否被误学为“现金已安全”？

### 原始问题

R-21 的长虹案例揭示了单一客户应收、负 OCF 与后续大额信用损失，但它不能授权“所有海外赊销都坏”。下一步原本需要一个高增长、可见信用治理且现金结果不同的正/近失效对象。若把公开出现“出口信用保险”或低前五客户比例的公司直接当正例，训练只会从“厌恶客户集中”摆到“相信保险工具”，仍没有理解现金如何穿过渠道。

### 实际应用

R-22 以康佳 2004 年报为 cutoff：海外销售增长 80%，新增海外客户应收中的大部分已投保出口信用保险，全公司前五销售商仅占 6.92%；但同年 OCF 已为 -3.74 亿元。2005 海外收入仍增长 17.05%、OCF仍负；2006 OCF转正为 1.81 亿元，却同时有应收和存货增加分别占用 7.41、2.01 亿元现金，而经营性应付增加 7.26 亿元。

这不是长虹的“成功反例”，也不是康佳信用治理的裁决：海外单独客户集中度、保额、免赔、理赔、信用额度、停发货权及逐客户回款都没有公开。它只能作为一个真正改变规则的边界复验——风险转移和客户分散可能影响损失暴露，却不自动解释收款速度或经营现金流来源。

### 结论与后续验证

`RETAIN_AND_NARROW / BOUNDARY_REPLICATION_APPLIED / POSITIVE_OR_NEAR_MISS_STILL_REQUIRED`。

R-21 的 `credit_governance_visibility` 现拆为：`loss_protection / collection_speed / funding_effect / shipment_authority`。未来卡必须按这四项登记工具的适用应收、触发条件、现金到账时点和责任人；只写“保险、信用证、票据或保理”时，其余三项均为 `UNKNOWN`。同时，OCF必须列出应收、库存、应付和融资的方向，不能以正负号结算。

根因：`REASONING + DATA_COVERAGE`。如果把保险、低集中度或单年正 OCF当成可收现金，会高估正常盈利和 owner cash；若反过来把本案两年现金不佳写成保险无效或海外扩张错误，也会越过缺失的合同/客户事实。禁止用未见巨额坏账、年末现金、价格或回报填补。验收是下一张真正可选择的信用卡同时具备：cutoff 前的客户/额度或停发货一手证据、工具条款与同口径两期 AR/库存/AP/OCF结果；否则继续把对象停在边界教学层，而不输出扩张或收缩规律。

## 迭代 P-69：把信用治理写得很完整，是否就已经有了回款控制？

### 原始问题

R-22 已说明保险和低集中度不能直接推出现金；但若研究者在下一案看见了保险、保理、共管账户、信用证、订单与知名终端的完整流程，仍可能把流程复杂度误判为经营控制。那会让 agent 从“迷信一个指标”升级为“迷信一套流程图”，依然不是企业家式判断。

### 实际应用

R-23 在中国消费电子出口链中找到一个更严格的反向试验。宏盛科技 2005 年业务收入增长、前五客户与供应商占比分别达 99.47% 与 99.40%，并于 cutoff 前披露信用保险、保理、四方共管账户、L/C 融资和最终 P/O 的链条。它同时披露零售预测可以改变、最终绑定订单较晚，且 2005 OCF仅为 638 万元。

2006 年结果没有沿着“纸面控制 → 现金可收回”发展：OCF为负，前五客户/供应商集中度仍约为全部交易，年末 13.59 亿元境外应收超过合同期未收回，审计师无法取得充分适当证据判断可收回程度并出具保留意见。这里保留意见只让资产价值和工具效果降为 `UNKNOWN`；它仍足以否定“回款已经被锁定”这一更窄的主张。

### 结论与后续验证

`RETAIN_AND_NARROW / MECHANISM_SELECTION_APPLIED / POSITIVE_REPLICATION_STILL_REQUIRED`。

信用链必须按 `counterparty_chain_identity → contractual_control → realized_collection → independent_verification → cash_conversion` 逐段通过。公司自己对流程、保险、终端和授信的说明最多进入第二段；它不允许跳到已实现回款、独立验证或 owner cash。这个改变同时保留 R-21 的集中度、R-22 的工具/流动性拆分，并把它们放入同一链条。

根因：`REASONING + DATA_COVERAGE`。若将流程或终端品牌当作可收回应收，会高估正常盈利和 owner cash；若因保留意见直接断言所有应收为零、所有保险无效或个人不诚信，则会把不确定性夸大成事实。缺失的是逐订单 P/O、保单/保理权利、共管账户流水、实际回款及审计替代证据；禁止用后续叙事、价格或回报填补。验收是下一张正/近失效样本在 cutoff 前列出链条、在结果期以第三方/审计或可复读回款证据逐段结算；否则不能产出“信用治理有效”的规律。

## 迭代 P-70：为了反对“信用链失效”，会不会错过真实的经营现金修复？

### 原始问题

R-21 到 R-23 连续显示了单一客户暴露、保险/低集中度不等于现金、以及复杂流程也不等于可收回性。如果接下来只继续找失败样本，agent 会把“应收、票据、海外扩张”本身当作错误，而不是寻找现金究竟由何种经营动作改善。

### 实际应用

R-24 以海信电器 2005 年报为 cutoff：海外收入增长、票据结算比重上升和库存增加使 OCF转负。2006 年海外收入仍增长，OCF转为正；存货下降带来 3.91 亿元现金，同时经营性应付减少 4.72 亿元，故不能把现金修复归为供应商延期付款。应收账款仍增、票据仅小幅下降，因此结果没有支持“客户信用已恢复”。

### 结论与后续验证

`RETAIN_AND_NARROW / POSITIVE_OPERATING_BOUNDARY_APPLIED / CREDIT_POSITIVE_REPLICATION_STILL_REQUIRED`。

现金桥固定分为 `collection_cash / inventory_cash / supplier_finance / external_financing`。R-24 只支持其中的 `inventory_cash`；它不推翻 R-21–R-23 对客户信用穿透的要求，也不构成具体管理者正确的选择样本。

根因：`REASONING + DATA_COVERAGE`。若把正 OCF直接写成客户回款、海外扩张成功或管理能力已验证，会高估 owner cash；若因应收仍增而否定库存释放的真实现金改善，又会把训练锁成失败叙事。缺失的是逐客户收款、库存责任单元及 cutoff 前周转硬授权；禁止用公司归因、价格或回报填补。验收是下一张可选择现金卡在结果期先完成四来源拆分，再评渠道信用和管理效果。

## 迭代 P-71：四张信用—现金卡是否已变成一个可复用的判断机制？

### 跨案收敛

R-21 长虹显示：收入增长、重点客户和部分期后托收不能覆盖单一客户应收、负 OCF与短借压力。R-22 康佳显示：出口信用保险与较低的全公司客户集中度，不会自动让 OCF成为客户现金。R-23 宏盛显示：即使公司披露保险、保理、共管、L/C和 P/O 的完整流程，逾期应收与审计保留意见仍可使“回款已锁定”失败。R-24 海信则提供必要的正向边界：海外收入继续增长时，存货周转可改善 OCF，且不必依赖供应商拖延付款；但这依然不证明客户信用已经改善。

四案的共同学习不是“海外扩张好/坏”“保险有用/无用”或“OCF应看/不看”，而是两条固定链：

`counterparty_chain_identity → contractual_control → realized_collection → independent_verification → cash_conversion`

以及

`collection_cash / inventory_cash / supplier_finance / external_financing`。

### 修改

该双链已写入[判断力飞轮](TURTLE_JUDGMENT_FLYWHEEL.md)、[企业经营判断训练方案](TURTLE_ENTERPRISE_JUDGMENT_TRAINING_BLUEPRINT.md)和[判断卡模板](../../../templates/research_enterprise_judgment_card.md)。它不是新评分或新并行账本：只有卡实际声称渠道/营运资本/现金传导时才启用；无条款、收款或审计事实则保留 `UNKNOWN`。

### 结论与后续验证

`RETAIN / CROSS_CASE_RULE_NARROWED / POSITIVE_CREDIT_CONTROL_REPLICATION_STILL_REQUIRED`。

根因：`REASONING + DATA_COVERAGE`。过去若把公司流程主张、保险、票据、终端名或 OCF 单值直接升为现金能力，会高估正常盈利、owner cash和资产负债表韧性；若只看失败案例则会误弃真实的库存/运营周转改善。缺失的是同一信用链的逐订单权利、收款、理赔和独立证据；禁止用年末现金、未发生的大额坏账、后来的价格/回报或公司解释补足。验收是下一张具有可见正向信用治理的不同公司卡，能在结果期逐段穿过第一条链、并在第二条链中分解现金来源；若不满足，只能贡献一个边界或 `NO_PRIMARY`，不输出信用治理的通用结论。

## 迭代 P-72：产能、销量与纵向一体化会不会又被压成一个“规模成功”的故事？

### 原始问题

R-21–R-24 已经把渠道信用和 OCF 拆开，但这条线不能训练企业家最常面对的另一类资源选择：需求尚未完全明朗时，是否建设工厂、增加关键部件能力，或把部件纳入自身体系。若直接从“中国家电最后剩三家”倒推“大产能/垂直一体化就是正确”，训练会重演幸存者叙事。

### 实际应用

R-25 以 2004 年美的年报为 cutoff。可读的实际承诺包括武汉、林港、顺德、芜湖及商用空调项目，以及美芝压缩机与东芝开利的投资；而且多个项目在 cutoff 时刚完工、尚未产生效益。2005–2006 的同一公司结果展示了一个必须保留的混合形状：空调产能对应的销量/收入继续增长，但压缩机销量增长并未防止收入与毛利经济性承压；两年 OCF又分别受业务剥离、存货/应收/应付影响。

### 修改

产能和纵向一体化卡今后不再问“规模是否成功”，而强制按顺序写：

`资源承诺 → output_absorption → unit_economics → working_capital_cash → capital_return`。

前一箭头成立不授权后一箭头成立。尤其是内部部件销量、技术合作、总 OCF和行业集中度，均不能替代部件外部经济性、项目现金回报或资本配置优劣。R-25 的训练身份是 `ACTUAL_RESOURCE_COMMITMENT_VISIBLE / NO_OPTIMAL_MANAGER_RANKING`：行动清楚，但可行的分期/外购方案、项目级资本预算和回报均未见。

### 结论与后续验证

`RETAIN_AND_NARROW / DIFFERENT_DECISION_DOMAIN / FORMAL_CAPACITY_REPLAY_NOT_YET_READY`。

根因：`REASONING + DATA_COVERAGE`。如果用产能、销量或企业总 OCF替代单位经济和资本回报，会高估成熟期扩张带来的正常盈利和 owner cash，低估供给过剩、内部转移定价与营运资本占用的永久损失；反过来，仅因部件毛利恶化就否定整机的需求吸收，也会错过真实的经营优势。缺失的是项目级资本支出/利用率、整机与部件的责任单元利润现金、外购反事实和两期资产回报；禁止用幸存者地位、后来品牌、价格或回报补足。

下一张产能/制造候选只有在结果前能定位同一主体的四个指标和真实分期/外购替代时，才可升为 `HISTORICAL_SELF_REPLAY`；否则保持教学卡并转向产品、质量或组织责任单元，而不是继续补美的公司史。

## 迭代 P-73：产品创新材料很多时，能否仍保持“先行动、后结果”的研究纪律？

### 原始问题

中国小家电有大量“创造品类”的成功叙事。它们看起来最适合训练企业家式产品判断，但也最容易把今天已经知道的品类地位、销量和品牌反投回当年的产品决策。

### 实际应用

R-26 筛到九阳商用豆浆机：2008 年招股书可追述其 2005 推出、2006 加大营销和 2005–2007 的连续产销量。正是资料十分完整，暴露了一个更危险的问题：同一后验文本把行动、结果、技术能力和成功叙事同时交给研究者。它不能构成结果前卡，也不能改造成“2005 年我会预测新品被接受”的盲测。

### 修改

新品进入训练前，强制拆成：

`用户痛点与替代 → 资源承诺 → 早期采用 → 单位经济 → 营运资本/资本回报`。

每一项必须来自时间上适当的原件；后验招股书最多进入候选索引，不能给出 cutoff、实际选择、H-A/H-B 或结果合同。`资料多`只能降低下一轮检索成本，绝不增加判断样本权重。

### 结论与后续验证

`RETAIN / PRODUCT_INNOVATION_SOURCE_GATE_ADDED / NO_PRODUCT_CONCLUSION`。

根因：`ACQUISITION_MODULE + REASONING + DATA_COVERAGE`。将后验招股书同时用作行动和结果来源，会在卡写下前就泄露结果，并把产品销量误认为用户价值、单位经济和现金都成立。经济影响是过度自信于新品扩张、错误判断正常盈利和资本占用。缺失的是同期产品/预算/试点、客户采用和单品经济的独立材料；禁止用专利、奖项、市场份额、总收入、价格或回报填补。

验收是下一张产品或质量卡在开读结果前已有两份分离来源：一份当期行动/用户问题原件，以及一份预先定位的同口径采用与单位经济/现金结果链。若没有，就公开记录 `NO_PRIMARY` 并切换候选，而不是为著名公司补长篇传记。

## 迭代 P-74：质量和服务承诺能否只用收入、毛利与品牌来结算？

### 原始问题

早期家电竞争常被概括为“质量和服务取胜”。若这个短语直接进入训练，agent 会把保修期限、认证、维修网点、总收入或后来品牌位置，误当作产品可靠性和客户经济性的因果证据。

### 实际应用

R-27 以格力 2005 年六年免费包修为压力测试。动作有同期报道和公司年报确认；2005–2006 的空调收入、毛利与合并 OCF亦可读。但同一资料没有给出同定义故障/返修率、每台保修成本、服务准备/费用的连续口径，或客户、渠道为什么选择与是否复购的观察。后出的市场评论虽提示同行跟随，仍不是同口径客户和成本结果。

### 修改

质量/服务机制固定拆成两臂：

`承诺 → field_reliability_or_service_demand → per_unit_service_cost_or_liability`

与

`承诺 → customer_or_channel_choice → price_realization_or_retention`。

两臂才共同进入现金与资本回报。收入/毛利只可作为末端背景；竞争者跟随首先是“共同成本或机制分界”的候选，而不是自动支持或反驳质量能力。

### 结论与后续验证

`RETAIN / QUALITY_SERVICE_TWO_ARM_GATE_ADDED / NO_GREE_CONCLUSION`。

根因：`DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。缺失质量和客户侧中间变量时，以总财务或品牌归因会高估服务投资带来的正常盈利，或把长保修的风险夸大为已发生的负债。禁止用认证、奖项、收入、总维修费、后来市场集中度、价格或回报填补。验收是下一张质量/服务候选在 cutoff 前有明确承诺，结果期有至少一个可靠性/服务需求指标、同定义每台服务成本或责任指标，以及客户/渠道选择或价格实现指标；缺一项则保持 `NO_PRIMARY`，不扩读格力。

## 迭代 P-75：产品高端化的毛利改善，是否已经等于公司经济质量改善？

### 原始问题

R-26 证明后验产品成功故事不能入场，R-27 证明质量/服务只有承诺和总财务仍不可结算。下一步需要一个行动原件与同产品结果能分开读取、但又足够复杂以测试“产品收入/毛利”会不会被误当 owner cash 的对象。

### 实际应用

R-28 以华帝 2005 年年报为 cutoff：公司在原料上涨、低端价格战和高端需求仍待培育的状态下，已实际实施中高端产品结构调整，并有两项中高端募投项目的后续投产安排。2006 年报则给出灶具、烟机、热水器各自的收入、成本和毛利率，以及销售费用、营运资本、投资现金流和项目状态。

结果是典型的分段混合：三类产品毛利率均改善，总体主营利润增长快于收入；但 KA渠道、出口、采购/SAP、自产替代和工艺改进同时发生，故不能把改善唯一归给高端结构。净利润下降，OCF的一部分又来自经营性应付增加，同时募投现金流出扩大，因而不能说产品毛利已经转为 owner cash 或项目资本回报。

### 修改

产品/质量卡固定增加：

`gross_margin_bridge = price_or_mix / unit_cost / channel_and_service_cost / working_capital_cash / capital_return`。

它与 R-25 的能力链相接：产品动作可先赢在一段，但须经销售费用、现金来源与资本占用后才谈长期经济质量。高端份额只有在产品定义和分母跨期不变时才可比较；否则 `MEASUREMENT_MISMATCH`。

### 结论与后续验证

`RETAIN_AND_NARROW / FIRST_PRODUCT_ECONOMICS_ROUTE / NO_OPTIMAL_MANAGER_VERDICT`。

根因：`REASONING + DATA_COVERAGE`。若将产品毛利改善直接归因于高端化，就会高估产品战略的正常盈利；若因净利下降就否定产品经济，又会漏掉真实的量价/成本改善。缺失的是客户选择、同定义高端份额、产品单元销售/服务成本、项目资本回收和竞争者反事实；禁止用公司归因、项目投产、品牌排名、价格或回报补足。验收是下一张不同公司的产品/质量卡在读结果前冻结上述五段桥，且早期产品经济和终局现金/资本回报使用不同的结果指标与窗口；否则只能贡献 source screen 或教学边界。

## 迭代 P-76：不同公司的“产品成功”能否检验单一产品机制？

### 原始问题

R-28 已发现华帝的产品毛利改善同时混入渠道、采购、自制和销售投入。若下一张不同公司也出现毛利改善，研究者很容易把它当作“高端化/创新已跨公司验证”，把两个事后相似结局误当成机制复验。

### 实际应用

R-29 以苏泊尔 2005 年产品差异化、厨房品类扩张和多基地制造为 cutoff。2006 年炊具、电器及四个核心产品都出现收入快于成本、毛利率改善；但公司同期明确列出新品/高端结构、部分提价、产能释放和单位成本下降。OCF 增加时，存货仍占用现金、经营性应付增加提供现金，且固定资产等投资支出继续很大。

它是有价值的不同公司边界：产品级单位经济可以在原料压力下改善；但它不是产品创新的 near miss，也不是单一产品机制的 replication，因为多项中介同时改变。

### 修改

跨公司训练对象按其信息角色重新命名：

- 只有共同条件被证实、且仅一个上游/中介条件以相反方向变化时，才是 `NEAR_MISS`；
- 只改变外部/组织条件、但多项中介并发时，是 `BOUNDARY_REPLICATION`；它只能收紧适用条件；
- 结果期新增一个没有在 cutoff 前分离的重大行动时，保留为 `MIXED_ATTRIBUTION`，不得拿来给原动作记功。

产品卡也追加“后续干预扫描”：读取结果后先枚举重大价格、渠道、制造、资本和会计边界变化；扫描发现多项并发时，优先升级归因边界，而不是升级机制确信。

### 结论与后续验证

`RETAIN_AND_NARROW / BOUNDARY_REPLICATION_COMPLETED / SINGLE_MEDIATOR_PRODUCT_TEST_STILL_REQUIRED`。

根因：`REASONING + DATA_COVERAGE`。将两家公司的共同毛利修复写成“产品创新跨公司有效”，会高估产品判断的可迁移性、错判正常盈利和 owner cash；反过来因无法独立归因而丢弃产品单位经济的可观察改善，也会错过真实学习。缺失的是单品客户采用、价格/折扣、渠道费用、制造成本和项目现金回收的责任单元序列；禁止用发行人解释、总 OCF、项目进度、后来品牌、价格或回报补足。验收是下一张产品/质量候选在 cutoff 前预注册每个中介的来源和窗口；结果若只出现其中一个中介的变化，才可形成 `NEAR_MISS`，否则仍只是一张边界卡。

## 迭代 P-77：丰富的质量/服务披露，能否直接变成质量护城河训练？

### 实际应用

R-30 的海尔电器材料提供了罕见的完整碎片：2011 年售后网络收购、服务中心/站点投入、保修准备金、实际动用、服务收入、第三方服务客户和费用方向。它因此比格力六年保修更接近质量/服务双臂。

但收购属于共同控制下合并，前期合并数被重述；服务收入混入电商或关联方交易；保修准备同时反映销量、安装、维修、退货和管理估计；产品客户的价格、留存与同产品可靠性率没有出现。材料多并没有消除同一经济主体和同一计量口径的缺失。

### 修改

质量/服务候选新增两个硬门：

1. **经济主体连续性**：收购、重述或新并表时，必须先识别是否存在不受并表改变影响的同一责任单元序列；没有则不得做 before/after。
2. **服务收入与产品质量分轨**：服务网络可以训练一个独立服务业务的客户选择；要训练“产品质量护城河”，还必须有同产品可靠性和客户选择，不能从服务收入跨越过去。

### 结论与后续验证

`RETAIN_AND_NARROW / QUALITY_SERVICE_SOURCE_ROUTE_STRENGTHENED / QUALIFIED_PRODUCT_QUALITY_CASE_STILL_REQUIRED`。

根因：`DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。若把服务平台的丰富披露拼为质量护城河，会把会计边界、服务收入和产品可靠性混成一个因果，进而高估正常盈利、现金和资本回报。缺失的是同产品故障/返修率、每台服务成本/实际支付、价格/复购/留存以及未重述责任单元；禁止用网点数、满意度奖项、准备金、总收入、公司解释、价格或回报填补。验收是下一张卡在 cutoff 前明确经济主体并在结果期分别结算质量臂与服务客户臂；否则停在 source screen，不扩读同一公司。

## 迭代 P-78：责任书、内部审计和法人财务表同时存在时，组织能力是否已经可结算？

### 实际应用

R-31 筛到 TCL 2000 年 KPI 制度。2004 年的监管招股书具体回顾了被考核事业部/子公司、总裁与经理签订的责任书、销售/利润/周转指标、月度排名、中期述职、审计与薪酬挂钩；同一文件还提供了若干制造、销售子公司 2000–2002 年的财务资料。它是比“实行事业部制”更强的组织制度原件。

但该文件在结果期后发布，且未把具体责任书、负责人、价格/采购/信用/预算等决策权，与某个制造或销售法人的损益、营运资本和现金一一连接。制造与销售单位本身又是不同经济环节。因此，它不能把“制度存在”和“单位经济后果”拼成同一因果卡。

### 修改

组织责任单元增加一项桥接，不再只检查四个权责字段是否出现：

`责任书/考核对象 → 至少两项可核查的决策权 → 同名责任单元的损益与营运资本/现金口径 → 两期可比结果`。

内部审计、KPI 和法人利润分别只能证明流程、考核和法人结果；名称近似不能代替这条映射。行动来源若晚于拟结算结果，也只能当作资料索引或 `RESULT_KNOWN_TEACHING`，不能倒建冻结前判断。

### 结论与后续验证

`RETAIN_AND_NARROW / RESPONSIBILITY_TO_ECONOMICS_BRIDGE_ADDED / NO_TCL_CONCLUSION`。

根因：`DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。若把可审计的制度流程和子公司利润直接连接，会把周期、产品、销售/制造分工或会计边界造成的变化误归给管理系统，进而高估正常盈利、现金转换和资本效率。缺失的是负责人—责任书—决策权—公开/可审计结果的一一映射；禁止用 KPI、审计、后来的规模、股价或回报填补。验收是下一张组织候选在行动前取得该映射，并用同一责任单元的两期经营与现金观察来结算 H-A/H-B；否则继续转向更可观察的产品采用或创新能力，而不是累积组织术语。

## 迭代 P-79：客户转换和续费可见时，能否已经称为创新能力？

### 实际应用

R-32 以广联达 2015 年平台/云服务转型为边界复验。行动前公司原件明确了平台化方向及围绕用户学习、提问的服务选择；2016 年官方年报披露云计价在年费转型地区的平均用户转换比例，2017 年官方年报又披露试点地区的转换、续费、合同、当期确认和预收金额。这让“客户是否开始接受服务”首次拥有较强的公开结果观察。

但 2016/2017 的地区集合与 cohort 没有被披露成相同分母，SaaS 的收入由一次性确认改为服务期确认；工程造价分部含传统与多种新产品，合并 OCF 更不能归给云计价。更关键的是，公开材料没有把某次可量化客户反馈和随后一项扩大/修正/停止的资源选择逐项接上。

### 修改

创新/平台训练分为三层，禁止越级：

1. `ADOPTION_OBSERVED`：同一客户定义的转换、活跃、续费、复购或停止可见；
2. `PRODUCT_ECONOMICS_OBSERVED`：采用之外，同产品/服务的价格、折扣、交付/维护成本和合同现金可比；
3. `CAPABILITY_OBSERVED`：前两层之外，存在 `feedback → next resource choice`，且第二条预先独立的产品/客户链按相同经济边界结算。

### 结论与后续验证

`RETAIN_AND_NARROW / ADOPTION_ROUTE_CONFIRMED / CAPABILITY_AND_OWNER_CASH_UNKNOWN`。

根因：`DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。若把转换率、续费率或预收增长直接写成能力与 owner cash，会忽略 cohort、价格、服务成本、收入递延和竞争跟随，误判长期经济质量；反过来用收入确认变化否定客户采用，也会丢掉有诊断性的早期信号。缺失的是同一 customer cohort 的单位经济、现金与反馈后的实际选择；禁止以总收入、总 OCF、研发、专利、预收、股价或回报代替。验收是下一张创新卡在 action 前冻结三层中的目标层级及所需指标；缺失就止于较低层，不伪造“能力”。

## 迭代 P-80：总客户数与云收入能否替代“客户采用”这个早期信号？

### 实际应用

R-33 以用友 2016 年进入企业互联网服务 3.0 阶段为不同企业边界复验。2017 年年报提供了云收入、金融服务收入和数百万云服务客户的公司层观察，看起来比 R-32 的试点数据更大、更有说服力。

但客户身份、去重、免费/付费、转换、续费、流失、合同现金和服务成本均未按同一 cohort 披露；云服务与金融服务的经济边界也不同。因此“393 万客户”不是广联达式转换/续费的替代指标，而是不可直接用来支持 H-A 或 H-B 的市场覆盖背景。

### 修改

平台、会员和 SaaS 研究的 `ADOPTION_OBSERVED` 增加最小定义：`entity/product boundary + customer identity/deduplication + free/trial/paid/renewed state + contract/cash event + service-cost boundary`。任一缺失，客户数只标为 `MARKET_REACH_BACKGROUND`。

### 结论与后续验证

`RETAIN_AND_NARROW / CUSTOMER_METRIC_GATE_ADDED / NO_YONYOU_CONCLUSION`。

根因：`DATA_COVERAGE + REASONING`。若把总客户数、云收入和金融收入合成客户价值，会把业务混合、免费触达、金融交易和服务经济性混为一谈，错误推断长期盈利、现金和可迁移能力。禁止以客户数量、总收入、市场排名、股价或回报填补。验收是下一张服务化候选在 cutoff 前已定义客户状态和现金事件，并能对同一 cohort 结算；缺失时停止在 source screen。

## 迭代 P-81：变量收费、ARPU 与产品毛利改善，能否替代客户留存或创新能力？

### 实际应用

R-35 以中国有赞 2019 年7月起对超出合同免费订单数的 SaaS 交易收取 cloud service fee 为行动。2019 年报已说明该收费规则、1–3 年预付的订阅合同、服务器托管责任和渠道佣金；2020 年报则在同一“订阅解决方案”口径下给出付费商户年末存量、每商户平均收入和毛利率的同步改善。

这个结果比 R-32/R-33 更靠近产品经济：它不是把公司总收入或总客户数塞进一张云服务卡，而是能看见一条具体货币化规则和该产品类别的价格/成本结果。但它仍无法辨认已有商户是否续约、客户自身是否因该服务获益、疫情和商户构成是否主导变化，以及哪一项反馈改变了下一次资源选择。

### 修改

服务化/订阅研究新增一个中间层：

`PRODUCT_MONETIZATION_MECHANICS_OBSERVED`。

它只要求 `pricing/contract rule → paid-customer state or ARPU → same-product gross-margin/cost boundary`；它明确低于 `ADOPTION_OBSERVED`、`PRODUCT_ECONOMICS_OBSERVED` 与 `CAPABILITY_OBSERVED`，并且不能由自身升级为后三者。以后每张定价/收费卡必须把 `price capture`、`customer retention`、`customer value`、`cash conversion` 和 `learning response` 分项结算。

### 结论与后续验证

`RETAIN_AND_NARROW / PRODUCT_MONETIZATION_LAYER_ADDED / NO_YOUZAN_CAPABILITY_CONCLUSION`。

根因：`DATA_COVERAGE + REASONING`。若把变量收费后的 ARPU、产品毛利或期末付费商户数写成留存、客户价值或创新能力，会高估价格权、长期正常盈利和资本回报。缺失的是同 cohort 的续约/流失、收费与服务/获客成本的完整现金边界，以及反馈后的实际资源选择；禁止以 GMV、总 OCF、合同负债、产品毛利、股价或回报填补。验收是下一张订阅卡能同时以同一 cohort 结算收费接受/续约，并单列该服务的履约/获客现金和后续选择；否则最多停在此中间层。

## 迭代 P-82：行业状态急变时，ARPU、覆盖和留存给出相反信号，哪一项应当获胜？

### 实际应用

R-36 以明源云 CRM Cloud 为边界复验。2021年下半年开发商营销压力上升时，公司推出智慧销讲和智慧工牌等功能；2022年，同产品下的售楼处覆盖约降26%、客户账户留存由88%降至82%，但单售楼处平均收入升20.4%。

这不是证明功能无效，也不是 ARPU 上升的胜利。它只显示行业客户状态改变后，同一产品的三个常用指标可以彼此冲突；不先拆分项目/客户构成、收费、使用、成本和需求，任何单一方向的公司解释都不具诊断性。

### 修改

所有服务化、渠道和客户经营卡增加 `state-conditioned metric divergence` 规则：当 `coverage`、`retention`、`ARPU/price` 中至少两项反向时，默认结果为 `MIXED / NOT_DIAGNOSTIC`。研究者必须列出会使它们分叉的外部状态和内部构成变化，并预注册同 cohort 的价格、使用、成本及现金观察；不能只选对主论有利的一项。

### 结论与后续验证

`RETAIN_AND_NARROW / STATE_CONDITIONED_DIVERGENCE_RULE_ADDED / NO_MINGYUAN_CONCLUSION`。

根因：`DATA_COVERAGE + REASONING`。将留存、覆盖或 ARPU 任一项直接当产品价值，会把行业景气、客户构成和定价变化误归为公司能力，材料性地影响正常盈利、竞争持续性和资本回报判断。缺失的是同 cohort 的合同/使用、产品成本与行业状态的可比观察；禁止以公司合并毛利、OCF、单项 KPI、管理层解释、股价或回报补足。验收是下一张客户经营卡在 cutoff 前写出三个指标的联合方向和环境断裂条件；若结果发生分叉而缺同 cohort 映射，则固定为 `MIXED / NOT_DIAGNOSTIC`。

## 迭代 P-83：完整 CJO 的结果结算是否真的已经像轻量前瞻 probe 一样不可手填？

### 实际应用

审查先以 `validate_settlement()` 的默认测试模式构造了手填 `actual_sources.content_access=BODY_READ` 与 `actual_outcomes` 数值，并得到一个合成 verdict。复核生产调用后发现：完整 CJO 的工程结算和 Phase10/反馈路径都显式传入 `allow_test_fixtures=False`；只有此时才会强制 outcome acquisition 的结果源 inventory、raw/reader、读取审计和 extraction 与 settlement payload 完全一致。默认模式只服务单元测试的合成 fixture，不能产出生产反馈。

### 修改

保留 P-34 的生产使用纪律：以冻结的发行方/域名、文件类型、窗口、指标标签和版本策略先枚举候选结果源；下载 raw/reader 并留下读取审计；只允许由同片段 label/value/期间定位生成 observation。已结算 observation/source 在后续条目中静默改写的路径也被拒绝。测试 fixture 的可手填性必须永远以 `allow_test_fixtures=True` 显式表达，且不得进入 Phase10 production 或 feedback/learning 路径。

### 结论与后续验证

`RETAIN / PRODUCTION_CJO_OUTCOME_BINDING_CONFIRMED / HISTORICAL_TRAINING_UNBLOCKED`。

根因审阅为 `MODEL + REASONING` 的**测试/生产边界确认**，不是生产数据缺口：若把 fixture 模式误当生产模式，会错误报告不存在的缺口；反过来若生产调用未传 `False`，手填输入才会材料性污染竞争持续性、正常盈利、现金转换和永久损失判断。缺失事实：无。禁止以直接函数默认值、R-05/R-06 的结果方向、价格/回报或手工确认评估生产结算。验收是：生产路径下篡改值、遗漏首个合格 release、标签/定位/期间/版本不符均不能生成 `REVIEWABLE` 或 pair verdict；合格官方 HTML/PDF 与持牌行业数据仍能结算。这个确认**不阻断**结果已知的教学案例或状态训练。

## 迭代 P-84：真实的质量/服务机会成本，能否已经代表长期经营质量？

### 实际应用

R-37 以 1980 年代冰箱的三个管理切片作结果已知教学：青岛把技术引进扩展到标准、关键部件、持续交流和质量反馈；北京雪花在旺销期主动停线技改、把进口压缩机优先用于维修并投资服务中心；万宝在质量危机后停产整顿和补充技术人才。雪花的原始报道甚至列出了少生产、少利润和服务资本投入，说明这些不是一句“重视用户”的口号。

但后续可读材料同时显示，竞争引入后功能/单位成本约束变得显性，雪花又经历产品滞销、改组和产品组合重置。现有公开报道没有同产品的可靠性、客户选择、价格实现、服务成本和现金连续链。因而既不能把后续重置判为 1987 质量/服务选择失败，也不能把早期投入升级为永久护城河。

### 修改

质量、服务与技术吸收卡从两臂链扩展为状态条件链：

`质量/服务或技术资源承诺 → 可靠性/响应 → 客户或渠道选择与价格实现 → 服务成本/营运资本/现金转换 → 产品组合仍匹配新市场状态`。

最后一段不是附加赞美语，而是独立门槛：当产品功能、价格制度、渠道或需求状态改变时，可靠性/服务能力只能是互补项。新卡必须把 `product-market-state fit` 与 `quality/service execution` 分开写；没有同产品现金边界时，最多命名为 `STATE_REPERTOIRE`。

### 结论与后续验证

`RETAIN_AND_NARROW / STATE_CONDITIONED_QUALITY_SERVICE_CHAIN_ADDED / NO_REFRIGERATOR_SURVIVOR_CONCLUSION`。

根因：`DATA_COVERAGE + REASONING`。若把有机会成本的质量、服务或技术投入自动提升为长期经营质量，会遗漏产品状态与现金链，错误判断正常盈利、竞争持续性和资本回报。缺失的是同产品的故障/维修、客户/渠道选择、服务成本、营运资本及产品状态的连续口径；禁止用后来品牌、企业存续、媒体赞誉、总产值、短期销售、股价或回报填补。验收是下一张质量/服务/技术吸收候选在行动前指定这些桥的来源与窗口，结果期至少能结算一个中间桥和一个现金/产品状态桥；否则保持教学状态并换对象。

## 迭代 P-85：跨境项目的资本开支与合并损益，能否裁决经营选择？

### 实际应用

R-38 以福耀 2014 年在美国同时建设汽车玻璃与上游浮法能力的资源承诺为教学材料。2015 年报能明确看到美国两个项目的资本性支出与在建工程大幅增加，集团存货天数也因美国浮法投产带来的较长存货而上升；2016 年报则显示若干美国实体以合并税务口径亏损。

这些不是无用信息：它们让研究者看到不可逆资本、吸收期和营运资本结构。但它们既不提供项目/工厂级的客户认证、交付、产能利用、单位成本和现金，也不能把税务合并亏损等同于某条生产线的经营损益。若据此宣布海外本地化成功或失败，判断就会从真实会计观察跳到未观察的经济因果。

### 修改

资本配置与跨境制造卡增加 `project attribution × economic stage` 双门：

1. 每项资本、在建工程、存货或融资观察必须标明是 **commitment / conversion / customer absorption / cash realization** 的哪一阶段；
2. 只有项目或同一责任单元的收入、成本、营运资本和现金才可进入项目效果。集团口径、资产持有实体、贸易实体及税务合并只能做状态或资金压力观察，不能代替项目级利润/现金。

### 结论与后续验证

`RETAIN_AND_NARROW / PROJECT_ATTRIBUTION_AND_STAGE_GATE_ADDED / NO_FUYAO_VERDICT`。

根因：`DATA_COVERAGE + REASONING`。若用资本开支、CIP、集团周转或税务合并亏损给项目打分，会材料性误判项目现金回收、资产负债表韧性和永久损失；反过来忽略这些观察，又会错过资本承诺早于经济吸收出现的预警。缺失的是同一工厂/项目的客户认证、产能、单位成本、营运资本和现金序列；禁止以跨境故事、集团 OCF、ROE、海外收入、媒体冲突、价格或回报补足。验收是下一张重资产/海外本地化卡在 cutoff 前写明每个指标的实体和阶段，并在结果期取得至少一个项目级吸收信号与一个项目级现金/资本信号。

## 迭代 P-86：真实前瞻里，管理动作与集团改善能否已经构成主判断？

### 实际应用

R-39 将海尔 2026Q1 大暖通整合作为真实前瞻筛查，而不是把它延展成一份报告。截止日的一手季报提供集团收入、利润与现金，官网材料也明确描述整合动作及国内经营改善。但两类材料没有共同构成“中国大暖通”这个责任单元的连续结果：集团改善可能来自任何业务组合、费用或地域；整合叙述本身又是发行人对自身行动的解释。

因此，H-A“整合已形成真实客户/渠道协同”和 H-B“改善主要来自其他组合，整合尚未形成可分离效果”都能容纳当期事实。研究没有为 H-A 填入一个靠集团利润支撑的方向性预测；也没有读取后续业绩来证明这种克制是对的。

### 修改

真实前瞻的入场门增加一条：**行动来源不能同时充当选择证据**。每一个被选择的主路径还须在冻结前拥有：

1. 被评价的同一责任单元及其基线；
2. 至少一个对 H-A/H-B 有相反含义的非共同经营事实；
3. 同标签、同期间、同单位的官方未来结果合同，至少跨 `customer absorption / unit economics` 和 `cash or capital realization` 两段。

集团利润、收入、OCF、行业转述和管理层行动叙述可以保留为状态或假设来源，但不能填补上述三项。条件不足的输出写为 `LIVE / NO_PRIMARY`，并明确后续结果不属于该卡的结算。

### 结论与后续验证

`RETAIN_AND_NARROW / ACTION_SOURCE_IS_NOT_SELECTION_EVIDENCE / LIVE_NO_PRIMARY_IS_A_VALID_OUTPUT`。

根因：`DATA_COVERAGE + REASONING`。若把组织动作与集团改善直接连成效果，会把不可分配的利润、组合变化或费用变化误记为业务协同，材料性扭曲正常盈利、资本回报和长期竞争判断。缺失的是同一责任单元的连续基线、客户吸收、单位经济和现金/资本观察；禁止以管理层叙述、集团指标、后续业绩、股价或回报替代。验收是 R-39 不产生选择入场或 FJ；下一张类似真实前瞻卡只有在冻结前满足责任单元、非共同证据与同口径结果合同后，才允许进入正式结算。

## 迭代 P-87：共同技术平台能否解释后续经营分化？

### 实际应用

R-40 使用九家同源阿里斯顿冰箱平台的 1987–1993 横截面。行业由热销转为供给过剩后，报道所列资本效率和资金周转从高正值到负值、从数十天到逾千天。它否定了“引进线/外来品牌/早期热销本身就是能力”的偷懒解释，也把产品适配和核心资本配置列为真正待检验的分叉。

但报道叙述的个别失败企业没有全部命名，也没有提供每一家可对照的动作、量价、成本、营运资本和现金序列。因此，这不是九个独立案例，更不是可以由文章的事后语言裁决的 company pair。

### 修改

从共同技术或共同政策状态发掘案例时，先把材料定义为 `COHORT_LEVEL_MECHANISM`。只有各对象分别拥有命名的责任单元、行动、可行替代、至少两个同口径后续经济观察，才允许拆成 focal、near-miss 或 boundary。共同平台只能固定外部状态，不能替代双方机制证据。

### 结论与后续验证

`RETAIN_AND_NARROW / COMMON_PLATFORM_IS_NOT_MECHANISM / NAMED_UNIT_AND_OUTCOME_CHAIN_REQUIRED`。

根因：`REASONING + DATA_COVERAGE`。若把共同引进、热销、奖项或后来行业集中当成解释，会漏掉客户问题翻译、核心资本配置和周转的分叉，材料性误判正常盈利、现金韧性与竞争持续性。缺失的是每个命名主体的独立行动、同口径经营和现金链；禁止从事后综合报道推断个人/公司因果效应，或把未点名对象伪装成 near-miss。验收是下一张来自该群体的卡满足“命名单位—行动—反方—同口径结果合同”；否则机制只保留为选案假设。

## 迭代 P-88：市场疲软是需求消失，还是产品没有解决使用问题？

### 实际应用

R-41 从 R-40 的同平台分化中选取一个有当期行动记录的产品切片：1989 年美菱遇到库存后，没有把行业转冷直接等同于家庭需求消失，而是把冷冻室容量不足当作可检验的使用约束，推出大冷冻室产品。报道中的实物检测与跨地区早期接受使“规格—客户选择”得到部分支持。

但早期采用和集团产量/利税仍不能分别排除价格、渠道、质量或一般需求恢复，更没有走到服务成本、周转或现金。因此本轮只训练识别客户问题和产品取舍，绝不把它扩为“产品创新成功”或“优秀企业家”的结论。

### 修改

产品决策卡的首段必须改写为 `使用约束 → 规格取舍 → 可识别客户选择`，并显式列出“维持旧规格/价格或渠道动作/另一种功能改型”至少一个替代。任何早期接受还须再连接一段同规格经济或现金观察；缺该段只允许 `PARTIAL_MECHANISM_SUPPORT`。

### 结论与后续验证

`RETAIN_AND_NARROW / CUSTOMER_PROBLEM_TO_SPECIFICATION_TO_CHOICE / EARLY_SIGNAL_NOT_FULL_ECONOMICS`。

根因：`REASONING + DATA_COVERAGE`。把库存直接解释成总需求消失，会错过产品—使用情景错配；把早期热销直接解释成长期能力，则会把价格、渠道、质量和现金的共同变化误归因于一个规格。经济影响是错误判断正常销量、产品毛利、营运资本与资本回收。缺失的是同规格竞争对照、量价、服务成本、周转与现金；禁止用集团数据、获奖、后来份额、股价或回报补足。验收是下一张产品卡在冻结前包含至少四段链，并在结果期结算一项客户选择和一项经济/现金信号。

## 迭代 P-89：产品洞察一旦成为行业标配，还能代表企业判断力吗？

### 实际应用

R-41 在早期采用外，再读到 1990 年当期行业报道：大冷冻室容积很快已由约 40 升向 70–90 升扩散，且后进入者若没有其他特点可能难以打开市场。这不改变美菱早期“使用约束—规格—选择”链的局部支持，却阻止研究把它固化为长期优势。

### 修改

产品卡必须写入 `diffusion/standardization trigger`：何时原本非共同的规格、工艺或服务变成行业共同条件；一旦触发，原主机制不能再沿用到下一窗口，下一轮必须寻找新的客户选择、成本、渠道或服务分叉。行业扩散报道可用作状态边界，不能替代任一公司的同口径经济结果。

### 结论与后续验证

`RETAIN_AND_NARROW / EARLY_SIGNAL_DECAYS_WITH_DIFFUSION / REOPEN_MECHANISM_AFTER_STANDARDIZATION`。

根因：`REASONING + DATA_COVERAGE`。若把一次产品洞察当作永久能力，会遗漏竞争跟进和客户标准上移，材料性高估后续销量、价格实现、资本回报和竞争持续性。缺失的是规格扩散后的公司级量价、成本、客户选择与现金资料；禁止用早期热销、后来企业存续、行业普及率、股价或回报续写原机制。验收是在下一张产品卡中预先指定标配化触发及触发后的重新入场指标；没有新分叉就停止沿用旧结论。

## 迭代 P-90：细分产品销量与集团利润同步改善，能否判为产品经济成立？

### 实际应用

R-42 将 P-89 的“标配化后需寻找新分叉”迁到不同公司与客户状态。新飞为农村客户同时选择了功能简化、约 400 元降价和宽温度/电压/湿度适应；经济型产品达到约 40% 销量，集团利税也上升。但同期原材料、零配件价格下降约 5%，且存在总体采购、管理和渠道变化。

这使客户采用成为有方向的早期支持，却把产品级经济结果固定在 `MIXED`：没有产品级成本、服务、渠道和现金，就不能回答每台产品的降价是否被吸收。

### 修改

细分产品机制从“客户约束—规格—选择”进一步扩成：

`客户支付/使用约束 → 功能取舍与价格 → 产品级成本/服务替代 → 渠道与回款 → 营运资本/现金`。

集团利润、利税或 OCF 只有在能与产品成本桥对应时才能进入最后两段；采购成本下降、品牌、渠道或管理共同变化必须留在反方，不得作为主机制的收益证据。

### 结论与后续验证

`RETAIN_AND_NARROW / SEGMENT_CONSTRAINT_TO_PRODUCT_COST / ADOPTION_IS_NOT_PRODUCT_RETURN`。

根因：`REASONING + DATA_COVERAGE`。若把产品销量占比与集团利税同步改善直接归给产品，会忽略采购成本、总体管理、渠道与其他产品变化，材料性误判单位经济、现金转换和资本回收；若只看降价，也会漏掉产品在特定使用环境下的真实客户价值。缺失的是产品级量价、成本/保修、渠道/回款、营运资本与资本占用；禁止用总利税、品牌、后来份额、股价或回报补足。验收是下一张细分产品卡在冻结前定位客户约束、功能取舍、价格、产品级成本和现金观察；否则只结算客户采用。

## 迭代 P-91：政策推动的订单增长，能否作为产品/企业能力的证据？

### 实际应用

R-43 将训练从家电的客户细分迁到新能源客车。宇通 2014 年在客车总需求承压时的新能源销量增长很快，且公司称产品得到市场认可；但公交推广与新能源政策正是该需求状态的重要组成。2015 年后续材料又显示，新能源增长伴随延期质保相关服务准备增加。

这使“订单/销量增长”和“产品/服务经济成立”成为不同箭头：前者可以是政策窗口内的真实交付，后者仍需价格、成本、故障/服务、回款与资本的独立观察。

### 修改

中国政策驱动制造卡增加四分法：`policy eligibility → delivery → service liability → customer cash/capital realization`。政策资格和销量只允许更新前两段；服务准备是风险信号，不自动判质量失败；只有责任单元的产品经济与回款才能更新最后两段。

### 结论与后续验证

`RETAIN_AND_NARROW / POLICY_DEMAND_IS_NOT_ENTERPRISE_ECONOMICS / SERVICE_LIABILITY_MUST_FOLLOW_DELIVERY`。

根因：`REASONING + DATA_COVERAGE`。若把政策环境下的销量、收入或份额直接写为公司竞争力，会材料性高估正常盈利、服务负担、现金转换和资本回收；反过来把服务准备增加直接写为质量失败，也会错判正在增长的合同义务。缺失的是产品级价格、成本、故障/实际服务支出、客户回款、营运资本和资本占用；禁止以政策标签、管理层叙述、总利润、总 OCF、补贴、股价或回报补足。验收是下一张政策驱动制造卡在行动前冻结政策资格、非共同经营证据、服务信号和现金信号四者；缺一项只做状态教学。

## 迭代 P-92：跨境并购后的国际收入，能否代表协同和资本配置正确？

### 实际应用

R-44 将 R-38 的“项目归属 × 经济阶段”迁到收购普茨迈斯特。交易完成后，三一的国际收入、资产和应收均发生变化；公司还称被收购企业销售和利润改善。但公开年报没有给出被收购实体的独立经营和现金表。2013 年混凝土机械整体毛利承压、财务费用上升，同时应收增加明确含并表和销售方式影响。

因此，合并范围和国际化规模是可观察事实；协同、交易回报和 owner cash 则仍未知。这个结论不是保守修辞，而是不同经济对象的边界。

### 修改

并购训练链新增独立的会计中间层：

`transaction/control → consolidation perimeter → entity operating economics → entity cash/capital return`。

`consolidation perimeter` 的变化只能证明控制权和报表边界变化；任何协同结论必须跨过实体级客户/产品/服务与现金两段。融资、汇率、行业周期和销售方式必须作为主机制的替代解释冻结。

### 结论与后续验证

`RETAIN_AND_NARROW / CONSOLIDATION_IS_NOT_SYNERGY / ENTITY_CASH_REQUIRED_FOR_DEAL_JUDGMENT`。

根因：`DATA_COVERAGE + REASONING`。若把海外收入、全球排名、合并资产或管理层对利润改善的叙述当作协同，会材料性误判交易的正常盈利、现金承受力和资本回报；若把整体毛利下降或利息增加直接判作交易失败，也会把行业下行与融资环境误归给并购。缺失的是被收购实体的连续收入、单位经济、服务、应收/库存、现金和资本占用；禁止以并表规模、品牌声誉、公司目标、总 OCF、价格或回报补足。验收是下一张跨境并购卡拥有实体级收购前后经营与现金合同，否则只结算合并边界。

## 迭代 P-93：公开目标集团年报，能否解决跨境交易的实体归属问题？

### 实际应用

R-45 将 P-92 带到潍柴—凯傲/林德液压交易。它看似优于三一—普茨迈斯特：凯傲有公开、连续的集团年报。但交易条款表明潍柴只持有凯傲 25%少数股权，却控制被 carve-out 的林德液压 70%；凯傲 2012–2013 的现金又受出售液压业务、IPO 与债务再融资显著影响。

因此凯傲集团年报是高质量的**集团背景和资本结构**资料，却不是潍柴受控实体/合作项目的经营或现金回报表。公开程度不改变责任单元。

### 修改

跨境并购卡将准入顺序前移为：

`控制权地图 → 受评实体 → 同一实体的结果合同 → 再读结果`。

少数持股集团、控股 carve-out、项目合作和买方本体必须是不同对象。结果期先读到的集团表只能标作背景；若没有受评实体的连续经营和现金表，立即 `NO_PRIMARY`，不因公开资料多而扩展研究。

### 结论与后续验证

`RETAIN_AND_NARROW / PUBLIC_TARGET_REPORT_IS_NOT_ENTITY_ECONOMICS / CONTROL_MAP_PRECEDES_OUTCOME_READING`。

根因：`REASONING + DATA_COVERAGE`。若把目标集团的现金、融资或业务规模等同于中国买方的资本配置结果，会材料性误判正常盈利、现金承受力与资本回收。缺失的是受控实体/可隔离合作项目的连续收入、单位经济、营运资本和经营现金；禁止以集团年报、出售所得、供应往来、IPO/债务、品牌、价格或回报补足。验收是下一项不同交易先锁控制图，再取得相同受评实体的前后经营与现金资料；否则训练只收获正确的边界判断。

## 迭代 P-94：控制权与实体级财报已齐备时，怎样判断收购是否改善经营？

### 实际应用

R-46 在美的—库卡满足了 P-93 的前置门槛：美的自 2017 年初控制库卡 94.55%，库卡的收入、利润、营运资本及现金流可以连续读取。2017 年库卡收入增长，但利润率下降、自由现金流仍为负；直接关联交易也很小，而全球机器人行业增长与库卡收入同向。

这不是资料又不够，而是实体报表本身不能分开买方协同、行业需求、收购前订单、投资和项目执行。控制权解决“谁的数字”，不回答“数字为什么变化”。

### 修改

在跨境交易链中，控制图和实体财务后新增强制的客户/项目归因层：

`买方投入/治理/技术/渠道动作 → 目标实体客户/项目或产品服务 → 单位经济/服务 → 现金`。

整体收入、利润或现金只能更新经营状态；只有第一、二段的非共同连接可选择协同机制。关联交易很小只削弱直接交易桥，不能自动否定间接组织或渠道影响。

### 结论与后续验证

`RETAIN_AND_NARROW / ENTITY_ACCOUNTING_IS_NECESSARY_NOT_SUFFICIENT / CUSTOMER_BRIDGE_BEFORE_SYNERGY`。

根因：`REASONING + DATA_COVERAGE`。把受控实体增长/现金直接归给买方会材料性错判正常盈利、现金承受力和资本回收；把暂时走弱直接归给交易也会漏掉行业、项目和投资原因。缺失的是买方投入通往目标客户/项目、单位经济与现金的连续同口径资料；禁止以控制比例、实体总表、行业增长、关联交易、价格或回报补足。验收是在下一项不同的受控实体中，四段链在冻结前均有结果合同；否则保留经营状态而不作协同结论。

## 迭代 P-95：早期家电的技术/质量投入，是不是“后来幸存者”独有的原因？

### 实际应用

R-47 回到用户提出的早期家电竞争问题，但不从已知存续名单入场。1984–1991 的同期报道显示，青岛的利勃海尔标准、上菱的三菱电脑控制线、扬子的先进自动线及工人训练、万宝的质量整顿都真实存在，且各自伴随质量或效益叙述。

因此，“引进先进技术/重视质量”是 S2 需要认真对待的能力前提，却并非可由后来名单选中的单一解释；新闻中的返修率、利润和增速也不是横向同口径合同。

### 修改

S2 研究卡先把技术引进、质量标准和卖方市场写为共同/广泛可得状态条件。仅在 S3 找到不同于共同条件的产品使用价值、服务责任、渠道信用或现金约束，才允许选择一家公司/机制。研究入口从“英雄企业做对什么”改为“何种共同条件不再能解释分叉”。

### 结论与后续验证

`RETAIN_AND_NARROW / QUALITY_IMPORT_IS_NOT_A_SURVIVOR_EXPLANATION / STATE_BEFORE_HERO_STORY`。

根因：`REASONING + DATA_COVERAGE`。把后来存续倒灌为早期技术/质量判断的证明，会材料性错判客户选择、服务负担、营运资本和资本回收；把这些投入完全忽略也会遗漏必要条件。缺失的是同定义的可靠性/服务成本、客户选择、渠道回款与 S3 现金表现；禁止用后来品牌、媒体赞誉、不可比经营数、价格或回报补足。验收是下一张 S3 卡在冻结前指明已共同化的 S2 条件及新的非共同客户或现金分叉。

## 迭代 P-96：服务在客户选择中重要，能否就代表企业服务能力和现金？

### 实际应用

R-48 以消费者投诉和 14 城抽样调查将售后服务放入 S3 的需求状态：在质量基本相同时，消费者会因服务而改变选择；实际维修责任又常与期望不一致。这使服务成为与产品规格、价格同等需要研究的客户变量。

### 修改

服务不再仅是质量的附属风险项。S3 案先把“服务影响选择”作为共同需求状态；公司级主机制另需可观察的履约/客户选择，再以服务/保修成本或现金完成第二段结算。只有满意度、网点或热线的对象不再进入深读。

### 结论与后续验证

`RETAIN_AND_NARROW / SERVICE_IS_A_CUSTOMER_VARIABLE_NOT_A_MOAT / SERVICE_COST_AND_CASH_REQUIRED`。

根因：`REASONING + DATA_COVERAGE`。把服务偏好、投诉或网络直接写成护城河，会材料性误判价格实现、服务负担、回款和现金；忽略服务又会错过客户选择的变化。缺失的是同一企业的履约、成本、渠道责任与现金。禁止用满意度、网点、奖项、品牌、后来存续、价格或回报补足。验收是在下一家取得“服务履约/客户选择 + 服务成本或现金”的同口径对；否则保留状态而不作企业结论。

## 迭代 P-97：服务网络很大，是否就证明服务的企业经济？

### 实际应用

R-49 将 P-96 应用于新飞 1997 年绿色通道。同期可确认 24 小时服务安排；随后采访也可确认数百专职、数千非专职服务人员，却明确暴露全网履约不可见。没有服务响应/修复、客户选择、每台成本、渠道责任或现金资料。

### 修改

`服务行动 + 服务规模` 从此只能进入状态/行动层。服务卡的入场门改成双合同：一个客户/履约观察和一个服务成本/现金观察。缺其一直接 `NO_PRIMARY`，不为资料丰富或品牌知名延长阅读。

### 结论与后续验证

`RETAIN_AND_NARROW / SERVICE_SCALE_IS_NOT_SERVICE_ECONOMICS / NO_PRIMARY_IS_CORRECT`。

根因：`DATA_COVERAGE + REASONING`。若把热线、网点或人数当作企业服务经济，会材料性误判服务负担、价格实现、营运资本和现金；用销量/利税补足则会把产品、环保和行业共同变化错归服务。缺失的是履约、客户选择、每台成本、责任分担和现金。禁止用网络、人数、品牌、销量、利税、后来存续、价格或回报补足。验收是下一不同企业的服务卡有冻结前的履约/客户和成本/现金双合同，否则不升级。

## 迭代 P-98：怎样避免每个新案例都重复同一种“从背景跳到结论”的错误？

### 实际应用

R-44–R-49 分别暴露了同一结构问题：并表范围、控制权、实体财务、服务网络和消费者偏好都是真实信息，却分别属于不同的经济层，不能互相替代。若每张卡只写自己的禁止项，研究者仍会在下一行业重复同一跳跃。

### 修改

训练总纲现统一采用五层归因顺序：`状态 → 行动与控制 → 责任单元结果 → 客户/项目桥 → 单位经济与现金`。每张卡先标出最高已达层；结论只能停在该层允许的范围。它同时规定下一步：补下一层的结果合同，或在资料不可得时停止/换案，而不是再增加背景材料。

### 结论与后续验证

`RETAIN_AND_GENERALIZE / EVIDENCE_LAYER_PRECEDES_CONCLUSION / UNKNOWN_IS_A_ROUTING_SIGNAL`。

根因：`REASONING + DATA_COVERAGE`。若将低层事实升级为高层经营结论，会材料性误判客户价值、正常盈利、现金与资本回收；若用更多背景掩盖缺层，会浪费研究容量并制造伪判断。缺失事实由各卡的下一层定义；禁止用行业状态、资源承诺、集团结果、网络规模、价格或回报跨层填补。验收是下一张卡在开读前标明当前最高层及要取得的下一层合同；无法取得时必须 `NO_PRIMARY` 或换对象。

## 迭代 P-99：产品/品牌聚焦下的销量增长，怎样避免既归因过度也错过真实产品信号？

### 实际应用

R-50 在长城—哈弗将品牌独立、网络调整、既有产品口碑、新车型投放与 SUV 行业增长并列为同时存在的机制。2014 年 SUV 和核心车型仍增长，轿车急降；集团收入增长而净利和经营现金流下滑，且现金含存货、应收及应付共同变化。

### 修改

产品/品牌卡新增三层分轨：`品牌/组织动作`、`特定产品客户选择`、`业务单元经济与现金`。产品销量可更新第二层的部分方向；集团利润/现金只反映状态，不能补品牌因果或资本回报。现金结论必须先分解存货、应收与应付。

### 结论与后续验证

`RETAIN_AND_NARROW / PRODUCT_FOCUS_DIFFERS_FROM_BRAND_CAUSALITY / CASH_SOURCE_BEFORE_CAPITAL_JUDGMENT`。

根因：`REASONING + DATA_COVERAGE`。若将品类销量、独立品牌或集团收入直接归给组织选择，会材料性错判客户价值、正常盈利与资本回收；若将利润/OCF 回落直接归给聚焦失败，则会错判产品投放和营运资本。缺失的是业务单元价格/渠道、成本、资本占用及现金，以及可比反方路径；禁止用行业增长、公司叙述、集团数、后来品牌、价格或回报补足。验收是在不同聚焦决策中冻结产品客户和单元经济/现金的成对合同；否则止于经营状态。

## 迭代 P-100：同周期、同品类增长的另一家公司，是否天然是近失效反例？

### 实际应用

R-51 筛查长安 2014 年自主乘用车增长，作为 R-50 的潜在边界对象。它与长城同处中国汽车产品结构变化期，却混有不同品牌/产品/渠道和合资、联营经济单元；年报还明确其利润增长包含长安福特投资收益。

### 修改

`共同宏观/行业状态` 只允许进入三对象批次的共同条件，不能单独产生 near-miss。近失效还须有相同的实际行动和可比责任单元、产品/客户结果与现金合同；缺一项标 `NO_PAIR`，不再因“也是自主 SUV”继续深读。

### 结论与后续验证

`RETAIN_AND_NARROW / SAME_CYCLE_IS_NOT_SAME_MECHANISM / NO_PAIR_IS_A_VALID_SELECTION_RESULT`。

根因：`REASONING + DATA_COVERAGE`。用同周期总销量或集团利润强拼反例，会材料性误判机制、正常盈利和现金，并把合资/联营收益错归产品策略。缺失的是同一行动、责任单元、同口径客户/经济/现金链；禁止用市场增长、总数、排名、价格或回报补足。验收是下一候选只翻转一个上游中介并保存完整可比合同；否则仍为单卡教学，不声称跨案复验。

## 迭代 P-101：价格下行中，产能扩张何时有产品经济含义、何时仍不能谈资本回收？

### 实际应用

R-52 将 R-25 的成熟空调扩产换到 2015–2016 年单晶技术路线转换。隆基在 cutoff 前已披露硅片/组件扩产、下游延伸、组织重构和成本下降；结果期的价格却下行。2016 年两个产品都有高产销、收入和毛利改善，同时合并现金流中经营性应收大幅占用、固定资产投资和外部融资也很大。

### 修改

扩产卡不再只问“是否被吸收”，还必须先写 `价格方向 × 产品单位经济 × 现金来源 × 资本占用`。在价格下降时，产品毛利改善可以结算成本/性能和经营吸收的窄箭头；它既不消除行业/组合归因，也不越过产品/项目现金和替代路径去评价资本配置。

### 结论与后续验证

`RETAIN_AND_CONDITION / PRODUCT_ECONOMICS_CAN_IMPROVE_DURING_PRICE_DECLINE / CASH_AND_CAPITAL_REMAIN_SEPARATE`。

根因：`REASONING + DATA_COVERAGE`。若用出货、毛利或正 OCF 直接认可扩产，就会材料性高估正常盈利和资本回收；若用产品降价直接否定扩产，则会错过成本、性能和客户采用形成的经营链。缺失的是项目/责任单元资本、客户/产品价格、独立营运资本和可行替代；禁止用行业热度、集团数、后来规模、价格或回报补足。验收是在下一对象预先冻结产品级产销、单位经济、四类现金来源和资本回收合同，并在不同主体上复验状态条件，而不把 R-52 变成光伏/扩产成功模板。

## 迭代 P-102：怎样避免从两张扩产卡学出相反的口号？

### 实际应用

R-25 的成熟空调扩产显示出货吸收不足以保护部件经济；R-52 的单晶扩产则显示价格下行中产品毛利仍可改善。若只按阅读顺序记忆，agent 可能从前者学到“扩产危险”，也可能从后者学到“技术领先即可扩产”。

### 修改

新增 [R-25/R-52 条件对比练习](experiments/R-25_R-52_capacity_conditional_contrast/00_capacity_condition_contrast_drill.md)：两张卡先保持独立，再只比较共同因果问题、不变量和状态调节项。下一不同公司的扩产卡须在 cutoff 前做 A（单卡基线）/B（条件对比训练）双版机制与结果合同；B 必须明确需求/有效供给、产品价格—成本、产品级吸收、四类现金来源与资本回收缺口。

### 结论与后续验证

`RETAIN_AS_CONDITIONAL_CONTRAST_DRILL / DESIGN_READY_NOT_LIVE_TESTED`。

根因：`REASONING + MODEL`。不做条件对比会把事后案例压成互相矛盾的管理格言，材料性误判扩产后的正常盈利、现金转换和资本回收。缺失的是第三家不同公司的结果前 A/B 冻结及后续同定义经营结算；禁止让后一案例回写前一案例、用行业名/结局/价格/回报做对比，或把两个案例当作方法优越性。验收是 B 在新对象中真实改变至少一条可结算观察，并由后续结果表明其是诊断性或正确保留了 `UNKNOWN`。

## 迭代 P-103：单机制卡怎样不再把企业切碎？

### 发现

现有卡已经把客户、产品、竞争、组织、现金和资本逐一拆开，能阻止大量错误归因；但它们缺少一个公司层的因果总图。若把单卡直接当作公司判断，会落入新的 `REASONING + MODEL` 错误：要么从局部正/负结果得出企业整体结论，要么累积很多局部卡却看不出产品、渠道、制造、营运资本和再投资如何相互反馈。

### 修改

新增[企业经营系统图](../../../templates/research_enterprise_operating_system_map.md)。新公司必须先用同一 cutoff 把 `客户/行业 → 价值捕获 → 活动/组织 → 单位经济/竞争回应 → 现金/资本 → 下一次资源选择` 画成一张图，只保留 2–3 条 material feedback loop。H-A/H-B 均须覆盖客户、价值、活动/竞争、现金/资本四面；每张 decision card 回链其中一条箭头，结果后只追加系统重组，不重写原图。

### 结论与后续验证

`MODIFY / ENTERPRISE_SYSTEM_FIRST / NO_WHOLE_COMPANY_VERDICT_YET`。

根因：`REASONING + MODEL`。若从单一机制直接推出公司结论，或把许多卡不加重组地堆叠，会材料性错判竞争持续性、正常盈利、现金转换与资本配置。缺失的是同一公司的系统级 H-A/H-B、关键回路和跨系统结果合同；禁止用公司史、指标清单、行业排名、管理层光环、价格或回报补足。验收是下一家公司的系统图先于任何 decision card 冻结，且其后至少一张卡真的改变一个 map arrow / next-card priority；否则系统图只是写作外壳，不可称为经营判断。
