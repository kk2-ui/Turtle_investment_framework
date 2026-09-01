# 研究学习复盘

## 原始实验

- 迭代卡：
- experiment ID：
- company cluster ID：
- 方法假设：
- 实验边界：
- 原始替代机制：
- 反馈等级（`LIVE_FORWARD / ARCHIVED_EX_ANTE_EXTERNAL / HISTORICAL_SELF_REPLAY / RESULT_KNOWN_REVIEW`）：
- 冻结时预先承诺的学习动作：

## 结算记录（只追加）

- 合格结果来源、发布日期与观察窗口：
- 冻结指标/定义与实际观察是否一致：
- 每个 signal 的 `A_ONLY / B_ONLY / MIXED / MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`：
- 该结果只更新的机制箭头：
- 是否已读取或改写冻结文本：`NO`（若不是，降级为 `RESULT_KNOWN_REVIEW`）。
- 若为选择 episode：冻结时的过程准入为 `SELECTION_ADMITTED / NO_PRIMARY`，当时考虑的候选机制集合及排除理由是否保留、选择依据是否逐项保留、最强反方是否保留、主路径与简单基线是否预测不同；若不同，分别如何结算；若相同，明确 `BASELINE_NONDISCRIMINATING`，不报告方法胜利。
- 若为选择 episode 且结果已到期：本案例为 `SUPPORTS_SELECTED / SUPPORTS_RIVAL / MIXED / NOT_DIAGNOSTIC` 中哪一项；这只是案例结算。除非已有多项独立、同定义的 out-of-sample episode 与预先冻结的损失/评分规则，否则不得报告选择准确率、胜率、统计显著性或方法优越。

## 发现

- 哪项事实、测量边界或反例真正改变了研究：
- 哪项材料没有诊断力，原因是什么：
- 结论受限于哪些 `UNKNOWN`：
- 本轮实际提升了哪一种判断能力；新增了什么区分：
- 若没有提升判断力，为什么这次实验仍应标为失败或资料不足：

## 方法裁决

- 方法裁决：`RETAIN / MODIFY / REJECT / INSUFFICIENT_TEST`
- 根因：`DATA_COVERAGE / ACQUISITION_MODULE / REASONING / MODEL / WRITING`
- 研究设计错误位置（`analysis_failure_loci`）：`STATE_REPRESENTATION / MECHANISM / EVIDENCE_ACQUISITION / FINANCIAL_TRANSMISSION / VALUATION_DECISION`。
- 企业经济错误位置（`economic_failure_loci`）：`STATE / DECISION / MEASUREMENT / MECHANISM / TRANSMISSION / ENVIRONMENT`。两组必须同时填写、分别解释：前者回答研究在哪一步失真，后者回答企业系统的哪一箭头未被正确判断；不得把它们混为同一列表。
- 若写 `STATE_REPRESENTATION` 与 `ENVIRONMENT` 的组合：必须回链到冻结前的 condition ID、其结果期 break observation 与 `CLOSE_AND_REFREEZE_NEW_EPISODE`；没有这三项，“环境变化”不能作为学习归因或原 pair 的免责理由。
- 若不调整方法，可能造成的经济错误：
- 对工作流/模板/禁用项的实际修改：
- append-only learning note ID：
- 下一轮可执行的 research change：
- 与冻结时承诺的学习动作是否一致；若不一致，为什么这是新发现而非事后合理化：

## 对象研究状态（与方法裁决分开）

- 当前状态：`UNDIFFERENTIATED / ACQUISITION_REQUIRED / READY_FOR_OBSERVATION / FROZEN_FOR_SETTLEMENT / EARLY_SIGNAL_SETTLED / TERMINAL_PENDING / CLOSED`
- 当前对象可作出的最强经济判断，或明确 `NO_COMPANY_CONCLUSION`：
- 不允许由方法裁决推出的公司结论：
- 若为 `ACQUISITION_REQUIRED`，唯一下一项资料请求：
- 若为 `EARLY_SIGNAL_SETTLED`，已支持/削弱的机制箭头与仍未到期的终局：

## 迁移与停止

- 下一轮应复验的不同对象或选择规则：
- 当前对象是否停止：`YES / NO`
- 若继续，只有什么新材料或新问题可以重开：
- 多公司簇方法复盘状态：`SINGLE_COMPANY_ACTION_ONLY / MULTI_COMPANY_METHOD_REVIEW_REQUIRED / NOT_YET_APPLICABLE`；不得由 note 数量计算准确率或胜率。
