# Turtle 公司经验积累协议

状态：`PRE_RESEARCH_METHOD_PREP / EPISODE_NOT_REPORT`  
目标：把“读过许多公司和书中案例”转成能训练未来公司判断的经验，而不是熟悉感、名家故事或报告数量。

## 1. 什么才是公司经验

公司经验的最小单位是一个有边界的**经营 episode**：

```text
当时状态
→ 管理层或竞争环境中的关键变化
→ 至少两条可运行的机制
→ 当时能定义的不同后续观察
→ 后来的经营结算与误差归因
```

一份年报、一篇报告、一个行业排名、一个著名投资案例或一次股价表现都不是 episode。它们只能提供 episode 的材料、问题或反例。

## 2. 四种经验对象不能混用

| 对象 | 用途 | 能否训练判断 | 不能做什么 |
|---|---|---|---|
| `EXPLORATION_NOTE` | 保存问题、原始材料和可能机制。 | 只能训练提问。 | 不作为事实、案例或概率依据。 |
| `EPISODE_CANDIDATE` | 已有明确状态和材料，等待建立 PIT 边界。 | 可用于设计研究。 | 不以已知结局挑选或评价。 |
| `ARCHIVED_EX_ANTE_EXTERNAL` | 他人在结果发生前留下可定位的原始机制判断，且另有独立后续结果链。 | 可沉淀状态、机制条件、断裂和信号顺序，供结构化类比使用。 | 不计入 Turtle 自己的命中、校准或方法胜率；原文未写的反方/阈值不得由结果倒填。 |
| `ELIGIBLE_LEARNING_EPISODE` | 有 cutoff、竞争机制、事前不同观察和后续经营结算。 | 可以训练校正、类比和参考类。 | 同一公司相邻年度不自动算独立样本。 |
| `OUTCOME_SELECTED_TEACHING_CASE` | 结果已知的成功/失败案例。 | 可训练机制识别、近失效反例和问题设计。 | 不进 PIT 回测、准确率、基准率或中心路径。 |

现有书籍案例卡属于研究路由器：它们提示该问哪些问题。它们没有原始判断与结果分离链时，不能因书名、作者或结局升级。`ARCHIVED_EX_ANTE_EXTERNAL` 可先形成外部结构经验；只有独立、可比较的 episode 才可能逐步形成参考类或频率材料。

## 3. 经验如何积累为判断能力

每个 episode 结束后，不记录“这家公司最后成功/失败”这一句结论，而只沉淀四个可迁移对象：

1. **状态向量**：哪些客户替代、行业结构、资产/资本约束、交易点和会计边界当时真正重要；
2. **机制条件**：什么条件下 driver 能通过中间变量传到经营结果；
3. **断裂条件**：哪一个结构差异让看似相同的机制失效；
4. **信号顺序**：哪个早期观察有诊断力，哪个只是共同背景或事后噪声。

下一家公司只能迁移这四项，不能迁移前一案例的结局、估值倍数、目标价、股价回报或管理层名声。

每次迁移前先用[结构化类比与近失效卡](../../../templates/research_analogy_transfer_note.md)记录匹配、断裂和不同的后续观察。卡片先完成 target-only 与 source-only 两份因果骨架，再允许写两者“为何相似”的理由；这防止容易语言化的品牌、行业名或成功故事先占据匹配。若同一研究者/模型不能诚实地隔离 source 详细材料，标为 `CONTEXT_SEPARATION_NOT_ASSURED`，只作问题设计，不能拿它检验该干预。若 source case 的结果已知，它只能作为 `OUTCOME_SELECTED_TEACHING_CASE`；即使 source case 是合格 episode，也不能在目标公司缺少自身可观察序列时替代目标公司的证据。

外部历史判断的准入、隔离与登记顺序见 [R-03 外部档案 intake](R03_ARCHIVED_EXTERNAL_EPISODE_INTAKE.md)。它解决的是“如何让书和案例提供可检查的机制经验”，不是把过去作者的正确结局转成当前研究者的能力。

## 4. 每个历史 episode 的研究顺序

1. 先用 cutoff 前材料重建状态，不读取后续结果；若原件是报告期结束后的业绩预告/盈利快报，它只能训练披露口径或对账，不能冒充事前经营判断。经营训练的原始主张必须在其结果期尚有实质经营过程未发生时作出，或明确标为外部作者当时的判断；
2. 写主/反机制和各自的早期/终局经营观察；
3. 冻结研究卡；
4. 再读结果期的公司与行业 observation，逐条结算；
5. 写 learning note：保留何种机制、废弃何种信号、为何类比成立或断裂；
6. 将 episode 与机制簇、公司/时期独立性和近失效案例一并登记；
7. 只有在下一不同对象复验时，才允许把它当作经验条件使用。

这是一条训练路径，不是为历史公司重写一份更完整的报告。

## 5. 防止伪经验

下列情况不会增加经验样本量：

- 同一公司多份报告或同一事件的多篇转述；
- 同一公司相邻年度、共享同一结构状态和后续结果的研究；
- 先知道结局，再选取“代表性”成功或失败案例；
- 多个研究者/agent 对同一材料的相同意见；
- 以股价或投资回报替代经营机制结算。

样本少时，经验库仍然有价值：它能积累条件、反例和信号顺序。但它不能输出经验频率、精确概率或统计意义。

## 6. 可选的三对象判断飞轮抽样

普通 `case_selection_register` 不需要组成固定 cohort。只有显式写入
`judgment_flywheel_sampling.enabled=true` 时，才启用以下更窄的抽样约束：每一批恰有
一项 `FOCAL`、一项链接 focal 的 `NEAR_MISS`、一项链接 focal 的
`BOUNDARY_REPLICATION`，且三家不同公司。

三项在 cutoff 前都必须为 `PIT_PRE_OUTCOME + INCLUDED`，并用完全相同的状态向量维度
比较：`mechanism_domain`、`current_state`、`competitive_fork`、`observable_symptom`、
`cycle_phase`、`business_boundary`、`result_metric`、`upstream_mediator`、
`boundary_condition`。近失效案例须在除 `upstream_mediator` 外的每一项已声明状态值（含
额外但共同声明的比较维度）与 focal 完全相同，并声明该 `upstream_mediator` 相反。边界复制在除
`boundary_condition` 外每一项已声明状态值均须与 focal 完全相同；它只能改变
`boundary_condition`。

飞轮 batch 的 universe 不是一句宽泛的“可研究公司池”。每个列入 `candidate_company_ids`
的公司都必须在同一冻结 register 有一条 entry，并在 cutoff 前以 `INCLUDED` 或 `EXCLUDED`
及其理由处置；反过来，entry 也不能来自 universe 之外。`EXCLUDED` 不进入三对象比较，
但必须保留，以防只把后来更像好案例的公司留在样本内。这个规则不把拒绝案例当作方法失败，
也不要求普通 research register 变成穷尽的市场数据库；它只使声称为飞轮 batch 的小 universe
可以复查。

这里的 `result_metric` 只是未来结算的同口径定义，不读取或填入实际结果。该对象没有、也
不得添加资料可得性评分、价格或回报字段；无法形成完整配对时，该批次不能被标为判断飞轮。

### 6.1 近失效的可能性条件必须有事实链

相同的状态向量文本不等于三家公司都曾具备目标机制发生的条件。启用三对象抽样时，
`possibility_condition_evidence` 必须逐项将 `FOCAL / NEAR_MISS / BOUNDARY_REPLICATION`
的共同条件映射到各自 cutoff 前的既有 `claim_evidence → OBS → DOC`；它只引用既有事实，
不复制事实或另建案例库。

- 每个 `COMMON` 条件须在三方都有各自的已验证一阶事实，且事实值确实支持同一状态向量字段；
  同一权威行业/宏观 DOC 可以正当地支撑共同条件，但三方不得复用同一个 `EVD` 或 `OBS`，也不能
  以同一转述记录冒充三条公司条件链。
- 唯一 `MEDIATOR_EXCEPTION` 只允许属于 `NEAR_MISS` 的 `upstream_mediator`，并必须有它自身
  cutoff 前事实。任何其他共同条件都不能借此改变。
- placeholder、不可解析来源、cutoff 后资料、结果期 observation、非直接/非精确证据都不得
  进入映射。

因此“近失效”只表示在共同可发生条件内，一个指定中介的差异测试机制边界；它不是天然因果
对照、也不产生频率或方法胜率。条件链配不齐时，正确状态为 `NO_QUALIFIED_NEGATIVE_CASE`。

## 7. 当前准备阶段的接纳标准

进入正式方法研究前，只需准备好每个 episode 的最小档案：

```text
state_vector
mechanism_A_and_B
pre-outcome observations and sources
outcome firewall
settlement plan
transfer conditions + strongest near miss
```

不要求立即建立案例库，也不预设格力会成为第一个合格 episode。首个对象应由方法实验的可复验性和信息隔离条件选择，而非重要性、熟悉度或投资吸引力选择。

## 8. 与判断验证的关系

公司经验的有效性最终由[判断力验证与回测协议](TURTLE_JUDGMENT_VALIDATION_PROTOCOL.md)结算：是否在当时形成了可区分的经营判断，是否更早识别错误，以及在不同对象中能否迁移。经验的积累速度可以慢，但它必须是这种慢而可复盘的积累，不能用报告数量加速伪造。

## 9. 方法依据与边界

`FOCAL / NEAR_MISS / BOUNDARY_REPLICATION` 是 Turtle 为机制学习设计的最小信息角色，不是统计抽样或“代表性”声明。它借用小样本目的性选案必须服务于明确推断任务的原则（[Seawright & Gerring, 2008](https://journals.sagepub.com/doi/10.1177/1065912907313077)），以及过程追踪应区分 theory-testing、theory-building 与 explaining-outcome 的任务边界（[Beach & Pedersen, 2012](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2108908)）。理论抽样、极端/对照类型和复验的价值来自机制信息量而非资料页数（[Eisenhardt, 1989](https://journals.aom.org/doi/abs/10.5465/amr.1989.4308385)）；按已知结果选案会扭曲推断（[Geddes, 1990](https://www.cambridge.org/core/journals/political-analysis/article/how-the-cases-you-choose-affect-the-answers-you-get-selection-bias-in-comparative-politics/05E854AA55C1BF090B56CEC73ACEFC6B)）。[Mahoney & Goertz (2004)](https://doi.org/10.1017/S0003055404041401) 的 possibility principle 进一步要求负例先落在机制可能发生的条件集合内；这支持上述条件证据链，但不使三对象批次成为自然实验。这些文献不证明 Turtle 判断正确；它们支持先确定推断任务与比较结构，再接纳材料的研究纪律。
