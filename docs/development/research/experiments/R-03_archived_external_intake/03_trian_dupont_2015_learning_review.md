# R-03 研究学习复盘：Trian / DuPont（2015）

## 原始实验

- experiment ID：`R03:TRIAN_DUPONT:2015`
- 方法假设：一份当时外部判断、一个同期强反方和一组后来官方经营披露，可以训练“机制—观察—断裂”的迁移能力。
- 实验边界：只处理 Trian 的 `$0.40/股` 成本节约假设、`2015 Q2–Q4` 约 `29%` 核心经营利润必要增长和其农业疲弱理由。
- 反馈等级：`ARCHIVED_EX_ANTE_EXTERNAL`。
- 冻结时预先承诺的学习动作：验证核心经营利润、成本节约和农业口径能否在独立官方结果链中连续读出；不能时保留 `MEASUREMENT_MISMATCH`。

## 结算记录（只追加）

- 合格结果来源与窗口：2015 Q2/Q3/FY 杜邦 SEC 10-Q/10-K，详见 [outcome resolution](02_trian_dupont_2015_outcome_resolution.md)。
- 冻结指标/定义与实际观察：成本节约前提可匹配；农业方向可读；`Q2–Q4` core 经营利润桥不能按同一官方定义读出。
- signal 结算：成本节约 `NOT_DIAGNOSTIC`；农业 `A_ONLY`（仅该箭头）；核心桥 `MEASUREMENT_MISMATCH`。
- 是否已读取或改写冻结文本：`NO`。结果源与冻结卡物理分离，冻结卡未改写。
- 案例结果：`NOT_DIAGNOSTIC`，不得报告方法胜利、选择准确率或胜率。

## 发现

- 真正改变研究的事实：官方 Q2、Q3、FY 分别使用 PTOI、窗口内变更后的 PTOI、以及另有额外排除项的 segment operating earnings。一个“看似明确”的经营谓词，仍可能没有可连续结算的官方计量对象。
- 有诊断力的材料：公司对成本节约的同期进度披露和农业业务的连续经营观察；它们可以分开判断“共同前提”和“局部机制”。
- 没有诊断力的材料：累计/全年分部利润对 Trian 的 core bridge；用它们倒推 Q4 会引入未冻结的分类与调整。
- 结论受限的 `UNKNOWN`：Trian 的 core/normalized 桥与公司每一期公开指标的完整调整表及重新分类映射。
- 本轮新增区分：**实现了成本节约** 不等于 **满足核心经营利润桥**；两者必须分别具有冻结定义和连续结果计量。

## 方法裁决

- 方法裁决：`MODIFY`。
- 根因：`DATA_COVERAGE / REASONING`。
- failure loci：`STATE_REPRESENTATION / EVIDENCE_ACQUISITION`。
- 若不调整方法，可能造成的经济错误：将成本节约和局部农业弱势拼接成对公司正常盈利、资本配置或拆分/整合优劣的虚假确定结论。
- 对工作流的实际修改：R-03 intake 现要求在打开 outcome package 前冻结 `metric-reconstruction contract`：原作者指标定义、允许的官方结果指标、调整项、跨期口径连续性和禁止替代项。缺任一项，完整谓词只能结算为 `MEASUREMENT_MISMATCH`。
- append-only learning note ID：`R03:TRIAN_DUPONT:2015:LEARNING:001`。
- 下一轮可执行的 research change：只接纳能够在结果前就写出同一官方指标/调整映射的外部判断；优先寻找报告期内指标定义不变的案例。
- 与冻结承诺一致：`YES`；这正是冻结时预设的“不能同口径即停止”路径。

## 对象研究状态

- 当前状态：`CLOSED`。
- 当前对象可作出的最强经济判断：`NO_COMPANY_CONCLUSION`；仅记录农业弱势和成本节约作为彼此不同的机制观察。
- 不允许由方法裁决推出的公司结论：Trian 或杜邦正确、拆分/整合较优、价值变化、任何证券行动。

## 迁移与停止

- 下一轮应复验的对象/规则：在 pre-outcome 原件中已经以公司官方分部指标和连续期间定义表达的经营判断。
- 当前对象是否停止：`YES`。
- 重开条件：只有发现一份**结果前原始材料**，已把 Trian core bridge 的定义、调整和 Q2–Q4 官方连续序列逐项锁定，才可重开；不得为此读取更晚的公司材料。
- 多公司簇方法复盘状态：`NOT_YET_APPLICABLE`。
