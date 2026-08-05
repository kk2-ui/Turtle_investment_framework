# Phase 02：决定性问题引擎

> 状态：COMPLETE ｜ 优先级：P0 ｜ 依赖：Phase 01（COMPLETE） ｜ 最后更新：2026-08-02

## 1. 要解决的问题

现有报告能覆盖很多主题，但信息和推导密度不等于投资洞见。系统需要在写作前找出最可能改变内在价值、风险判断或仓位动作的少数问题，并用可区分证据检验它们。

## 2. 目标与非目标

- 每家公司生成最多三个决定性问题，并解释它们如何改变估值或动作。
- 将问题拆为竞争解释、可观察信号、研究任务和结论翻转路径。
- 按决策敏感性排序，不按关键词、段落长度或模型偏好排序。
- 本阶段不实现行业模型库和关键章节编译。

## 3. 输入、输出与排序

输入为Phase 01的 VERIFIED facts/gaps、当前估值敏感性、thesis/claim ledger和公司初步原型。输出 `decisive_question_plan.json`，包含稳定 `question_id`、竞争解释、价值影响、待取证任务、观察窗口、置信度和停止条件；研究完成后以 `decisive_question_findings.json` 固化区分信号、解释更新和决策变化。

排序因子：决策敏感性、证据区分力、基准率相关性、可观察性、时间价值；重复问题受惩罚。分数只用于排序，不能替代研究员式的完整竞争解释检查。

### 3.1 输入真源

- `report_context.json`：VERIFIED observation、显式缺口和冲突。
- `compute_bundle.json`：GG、II、估值区间、模型分歧、λ/误差传播、现金和分红可持续性。
- `analysis_contract.json`：周期性、行业分类、资产特征和有效分析窗口。
- 已存在时读取 decision、valuation、claim、thesis 和 insight ledger；不得把旧报告自由文本当参数真源。
- `insight_research_brief.json` 只提供初步公司原型假设，不能直接决定最终问题。

### 3.2 输出契约

`decisive_question_plan.json` 最少包含：

- 输入指纹、计划状态、最多三个 `selected_questions` 和完整 `rejected_candidates`。
- 稳定 `question_id`、`topic_family`、问题正文、候选来源和排序分解。
- 至少两个竞争解释；每个解释写明机制和目前支持/反对的 observation ID。
- 区分信号：可观测字段、两种解释下的方向、数据源、窗口和可获得时间。
- 决策连接：受影响的估值/回报/仓位身份、压力值、翻转条件和动作变化。
- 有界研究任务：路由、工具、年报章节、来源类型和停止条件。
- 工作置信度及其依据；这不是统计频率，不得伪装成精确概率。

`question_id` 由 `report_id + topic_family + 问题机制` 确定性生成。措辞变化不得产生新问题身份。

### 3.3 排序公式

```text
priority = 0.35 × decision_sensitivity
         + 0.25 × evidence_discriminability
         + 0.15 × observability
         + 0.15 × time_value
         + 0.10 × base_rate_relevance
         - redundancy_penalty
```

所有分项限定在0–1。排序只决定研究先后；任何选中问题仍必须通过竞争解释、区分信号和动作映射硬门。

## 4. 实施工作包

### WP1：契约与身份

定义schema、问题ID、输入指纹、状态、候选/入选/淘汰语义和向后兼容政策。

### WP2：候选问题生成

从模型分歧、GG安全余量、反向隐含路径、经营转折、现金可达性、治理兑现和关键证据缺口生成有限候选；每项生成必须有结构化触发事实。

### WP3：竞争解释和区分信号

为每项候选生成至少两个机制不同的解释，绑定已有VERIFIED evidence，并说明需要哪些新证据才能区分。没有可观察区分信号的候选不得入选。

### WP4：排序、去重与停止

实现分项评分、topic family去重和语义重叠惩罚；最多选择三项。被淘汰候选保留分数和原因，禁止只输出获胜问题。

### WP5：统一管线和账本约束

在报告写作前生成计划；合同包和读取工具暴露选中问题。insight ledger的决定性问题必须引用入选 `question_id`，后续定向研究沿用同一任务身份。

### WP6：验证与校准

主样本01502、000651、002027，控制样本02669；检查是否真正区分物业、成熟制造和轻资产媒体，而不是四家公司得到同一模板问题。

## 5. 质量门

- `INVALID`：问题与估值/动作无连接；竞争解释实为同义改写；引用未验证事实。
- `INCOMPLETE`：核心问题没有可观察区分信号或研究任务未完成。
- `WARN`：问题重要但短期不可观察，必须降低决策置信度。
- 不按问题数量、因果词数量或字符数评分。

`INVALID`还包括：未知/非VERIFIED observation、问题ID漂移、同topic重复入选、insight ledger绕开计划另造问题、决策连接只写“可能影响估值”而没有方向和翻转动作。

`INCOMPLETE`还包括：新运行没有计划、没有任何问题达到最低选择条件、研究任务缺来源或停止规则。

## 6. 完成标准

- [x] 输出schema、确定性ID和向后兼容策略完成。
- [x] 每个问题都有至少两个真实竞争解释和区分证据。
- [x] 每个问题明确对估值、概率或仓位的翻转影响。
- [x] 自动管线最多研究三项，未入选问题保留淘汰理由。
- [x] 单元、对抗、集成和四只真实样本验证通过。

## 7. 剩余限制

行业特定的题库、估值方法和基准率在Phase 03与Phase 05补齐。

## 8. 迁移与回滚

旧目录没有 `decisive_question_policy.json` 时保持SKIP。新unified run在写作前绑定政策并生成计划；生成失败只允许停止或标记INCOMPLETE，不得回退为“让模型自由挑问题”。

## 9. 阶段完成摘要

已实现确定性候选生成、动态冗余惩罚排序、最多三项选择、完整淘汰理由、竞争解释、区分信号、价值/仓位翻转路径和有界研究路由。统一管线在官方证据构建后、写作前自动生成计划；合同读取工具按章节暴露问题；insight ledger只能绑定入选ID及原文。

新增研究完成契约 `decisive_question_findings.json`：每个入选问题必须记录VERIFIED证据或公开资料不可得的实际尝试、区分信号结果、解释置信度更新及估值/仓位动作。未完成为`INCOMPLETE`，伪造观察ID、越过入选问题、无结论却提高置信度为`INVALID`。旧目录没有policy继续`SKIP`。

真实样本结果：

| 样本 | 排名前三的topic family | 首要问题特征 |
|---|---|---|
| 01502 金融街物业 | cash value / owner return / operating transition | 净现金达市值244.6%是否真正可达外部股东 |
| 000651 格力电器 | operating transition / model applicability / owner return | 经营收缩及46.05与122.40元估值分歧 |
| 002027 分众传媒 | owner return / operating transition / model applicability | 折价GG低于II且利润与收入背离 |
| 02669 中海物业（控制样本） | owner return / operating transition / cash value | 回报门槛、盈利转折与58.9%净现金兑现 |

验证基线：Phase 24新增11项测试；Stage 1–24、自动修复与完成契约合计`278 passed`。四份真实计划均为`REVIEWABLE`；正式新run在研究结论未提交前会被正确阻断，不会退回自由写作。写作前指纹作为可审计快照；同一run新增VERIFIED证据只产生警告，不会因完成取证而自我阻断。
