# Turtle 历史 PIT 训练与留出队列

状态：`ACTIVE / FIRST_COHORT_QUEUED / NO_REALTIME_ABILITY_CLAIM`  
更新：2026-08-23  
上位协议：[历史优先训练架构](TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md)、[判断力验证与回测协议](TURTLE_JUDGMENT_VALIDATION_PROTOCOL.md)、[研究操作流程](TURTLE_RESEARCH_OPERATING_PROTOCOL.md)

## 1. 目的

这个 register 把已有案例从“结果已知的文档集合”变成可运行的训练队列。机器真源为 `config/judgment_training_program_v1.json`，由 `judgment-training-program.v1` 管理通道、抽样、留出和状态上卷；本文件负责解释对象选择和经济训练职责。它不增加评分、概率或报告任务，也不另造结算语义。

历史案例足以训练研究动作：还原当时状态、构造竞争机制、写最强反方、冻结 D1--D5 时钟和结果合同、在揭盲后给出错误归因，并把一条具体约束迁移到下一家公司。它不能单独证明 Agent 在未知结果环境中已经具有投资或预测优势。

## 2. 两个正交维度

案例不能只按“历史/前瞻”一列管理。每项都必须有一个 `provenance_role` 和一个 `cohort_allocation`。

| 维度 | 可用值 | 约束 |
|---|---|---|
| `provenance_role` | `HISTORICAL_SELF_REPLAY`、`ARCHIVED_EX_ANTE_EXTERNAL`、`RESULT_KNOWN_TEACHING`、`REAL_FORWARD` | 决定结果能形成哪一种证据。`RESULT_KNOWN_REVIEW` 是已有文件的历史名称，在本 register 中归为 `RESULT_KNOWN_TEACHING`。 |
| `cohort_allocation` | `DEVELOPMENT`、`HOLDOUT`、`TEACHING_ONLY`、`INTAKE` | 决定何时可以看 outcome、能否改变规则。`HOLDOUT` 必须同时有 provenance_role，不能作为独立的能力标签。 |

`DEVELOPMENT` 可以产生一条被 reviewer 接纳的历史学习约束；在其规则版本冻结后，`HOLDOUT` 才能揭盲。任何 HOLDOUT 的公司集团、时间段和行业/机制结构都不能与同一规则的 development evidence 混同。`TEACHING_ONLY` 可训练反例和禁止替代，但不可作为本轮规则效果的分子或分母。

## 3. 第一队列

| register ID | 现有工件 | provenance_role | cohort_allocation | 允许做的工作 | 当前禁止事项与下一门 |
|---|---|---|---|---|---|
| `HPIT-01` | [R-62 鹏鼎 2023 cutoff screen](experiments/R-62_pengding_automotive_pcb_2023_screen/01_pre_outcome_admission_screen.md) | `HISTORICAL_SELF_REPLAY` | `DEVELOPMENT` | 以同一责任单元检查项目实施、客户吸收、产品单位经济、现金桥和资本边界；结果只在冻结后按官方窗口读取。 | 不把项目模型 IRR、认证、集团 OCF 或后续行业景气当作项目成功。完成前必须补齐 PIT case、结果合同和 reviewer outcome-read 权限。 |
| `HPIT-02` | [R-61 沪硅 2025 cutoff screen](experiments/R-61_shanghai_silicon_2025_minorities_screen/01_pre_outcome_admission_screen.md) | `HISTORICAL_SELF_REPLAY` | `HOLDOUT` | 在 HPIT-01 的正式 learning application 和方法版本冻结后，检验未参与规则形成的公司轴／时间轴对象是否仍能正确结算或保留 UNKNOWN。 | 这是当前唯一预留的干净留出：结果、诊断和派生规则未进入 HPIT-01；方法冻结前不得读取 outcome，任何提前读取永久使该对象失去 holdout 身份。R-56/R-58 已揭盲，只能作教学。 |
| `HPIT-03` | [R-25 美的 2004 扩产卡](experiments/R-25_midea_2004_capacity_chain_teaching/01_2004_pre_outcome_capacity_card.md)；[结果复盘](experiments/R-25_midea_2004_capacity_chain_teaching/02_2005_2006_outcome_resolution.md) | `RESULT_KNOWN_TEACHING` | `TEACHING_ONLY` | 训练“产能吸收、部件单位经济、现金转换、资本回收必须分开”的边界和反例。 | 不用于 HPIT-02 的规则生成、留出评价、选择准确率或管理层总评。 |
| `HPIT-04` | [R-21 长虹 APEX 信用卡](experiments/R-21_changhong_apex_credit_growth/01_2003_pre_outcome_enterprise_judgment_card.md) | `RESULT_KNOWN_TEACHING` | `TEACHING_ONLY` | 训练增长、单一客户信用、现金和继续扩张之间的非嵌套反方。 | 不以已知坏账判定当时授信管理的全部优劣；不可计入选对/选错。 |
| `HPIT-05` | [R-78 Ford Way Forward freeze](experiments/R-78_ford_way_forward_2006/01_pre_outcome_enterprise_system_freeze.md)；[结果结算](experiments/R-78_ford_way_forward_2006/02_outcome_resolution.md) | `RESULT_KNOWN_TEACHING` | `TEACHING_ONLY` | 作为中国制造训练规则的海外边界/近失效：退出实施不等于客户、单位经济、现金或资本回收已经改善。 | 不把美国汽车案例迁为中国参数，也不作为中国样本数量替代。 |
| `HPIT-06` | 梅花生物价格竞争 | `UNCLASSIFIED` | `INTAKE` | 先核实用户指向的具体时期、产品、公司实际动作、竞争者、cutoff 前原始来源和独立结果文件。 | 目前不能假定“价格战”指 2020、2021 或 2025 的任一轮价格变化，更不能据二手评论、后来利润或股价直接判断价格权/出清/管理能力。 |

本批次刻意不硬凑 `ARCHIVED_EX_ANTE_EXTERNAL`。现有文件若没有第三方在 cutoff 时留下、可定位且与结果隔离的判断，就保持 `HISTORICAL_SELF_REPLAY` 或 `RESULT_KNOWN_TEACHING`，而不是为了提高样本等级改写来源身份。

## 4. 运行顺序

1. curator 仅从 cutoff 前原件建立 `FROZEN_METRIC_SLICE` 和 source package；研究者先写 H-A/H-B、最强反方、简单基线、D1--D5 和停止条件。
2. reviewer 确认 outcome firewall、允许来源与计量合同后，才允许读取单一预登记 outcome package。
3. 结果只能追加到冻结卡，逐箭头结算为 `SUPPORTS_PRIMARY`、`SUPPORTS_RIVAL`、`MIXED`、`NOT_DIAGNOSTIC` 或 `MEASUREMENT_MISMATCH`；不得回写冻结机制或阈值。
4. 只有材料性诊断改变不同公司冻结字段且 reviewer 确认，才写 learning note。该约束须以版本号冻结后，才允许揭盲 HPIT-02。
5. HOLDOUT 若不支持规则，正确结果是收窄、修改或拒绝规则；不能再挑选已知结果案例补回“成功率”。

## 5. 当前成功定义

本队列的第一个完成标准不是“做了多少案例”，而是留下这条可审计链：

```text
R-62 PIT freeze
  -> independent outcome read and multi-clock settlement
  -> diagnosis with an explicit economic boundary
  -> rule version applied to a different company
  -> R-61 HOLDOUT reveal without rewriting that rule
```

这可以证明历史训练是否真正改变了下一次研究行为，以及该改变在一个预先隔离对象上是否仍有诊断性。它仍不能证明实时预测优势；R-54、R-93、R-94 等 `REAL_FORWARD` episode 继续在到期后按原合同提供部署校准。R-56 和 R-58 的历史结果已公开且曾参与规则形成，不能重新包装为留出。
