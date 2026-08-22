# ITER-106 — 结构化类比能约束案例使用，但不能凭空补出公司经验

日期：2026-08-21

[Green 与 Armstrong（2007）](https://www.sciencedirect.com/science/article/pii/S0169207007000696) 的结构化类比研究要求专家列出类比、判断相似性，并把历史结果对应到目标情景；相较非结构化判断，实验结果更好。但研究对象是八个冲突预测情景，作者也明确要求后续复核，不能外推成“多列类比必然提升投资回报”或精确概率。

对 Turtle 的可用部分已由 `analogy_transfer_card` 承担：目标状态向量、可迁移的 driver→中间变量→经营结果、结构断裂条件和一个最强近失效例，均需连回冻结 pair signal。新增一叠书籍公司名、把 20 份格力年报拆为二十个类比，或对没有 outcome 的候选案例做相似度打分，都不会增加可迁移经验，反而制造伪样本。

根因是 `REASONING + DATA_COVERAGE`。当前格力没有合格的 `MEP:/CASEEV:` episode，所以 transfer card 必须是 `UNKNOWN_NO_QUALIFIED_EPISODE + QUESTION_ONLY`：它可以规定下一步问哪些问题，却不能支持 H-A/H-B、概率或估值。接纳条件是至少一个独立、冻结后结算的真实 episode 存在，类比才可升级为 `VERIFIED_EPISODE`；即便届时也只迁移机制与失效信号，不迁移终局收益率、估值倍数或股价表现。
