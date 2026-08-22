# 研究迭代卡

状态：`DRAFT / SCOPED_EXPERIMENT / CLOSED`

## 方法假设

- 反馈等级：`LIVE_FORWARD / ARCHIVED_EX_ANTE_EXTERNAL / HISTORICAL_SELF_REPLAY / RESULT_KNOWN_REVIEW`。
- 结果熟悉度与泄漏风险：说明研究者/模型是否可能已知结果；若不能排除，历史样本只能测试流程，不计入自身判断力回测。

- 当前研究方法的盲点：
- 拟加入、删除或调整的方法步骤：
- 本轮训练的判断能力：`问题界定 / 机制辨别 / 测量辨别 / 校正 / 迁移`
- 本轮验证等级：`L0 流程完整性 / L1 结果采集完整性 / L2 单箭头诊断性 / L3 主路径选择 / L4 跨公司迁移 / L5 方法相对表现`。
- 本轮能够声称的最高等级，以及明确不能声称什么：
- 升到下一等级仍缺的结果、独立对象或预注册聚合规则：
- 若本轮会进入 `L5` cohort：冻结前的 `JMEPLAN:`、完整 screen-entry 处置、每公司一个 terminal FJ 与最小独立簇数；否则写 `NOT_APPLICABLE`。
- 实验完成后，研究者应能新增作出的区分：
- 预期避免的材料性经济错误：
- 该错误会影响的经济边界：`正常盈利 / 现金转换 / 资本配置 / 永久损失 / 其他`
- 不成立时应看到什么：

## 有界实验

- 实验对象（公司、时期、机制）：
- 决定性问题：
- 假设空间筛选工件（机制实验卡路径；逐项写 material displacement；若有 material `DEFER_NO_PRIMARY`，本轮只能为 `NO_PRIMARY`）：
- 允许材料与截止边界：
- 结果防火墙（哪些 outcome 在冻结前不可读；若已知则标注 `OUTCOME_SELECTED_TRAINING_ONLY`）：
- 冻结后的结果暴露边界：只有某一冻结 claim 已到 `DUE_FOR_ACQUISITION` 后、并由其结果期来源契约选中的 body 才可读取。未进入任何 claim 的中间业绩、"脉冲"或相近 KPI 一律 `UNREAD`；它们没有可改变的预先承诺动作，却会污染下一次结算的解释。若研究者已读，记录 `OUTCOME_EXPOSURE_BREACH`，该卡只可保留为管线训练，不能进入方法 learning note 或迁移复验。
- 明确不研究什么：
- 当前基线解释（不采用新方法时会怎样判断）：
- 基线为什么是公平对照：
- 新方法被拒绝或资料不足后，下一步将如何不同：

## 同公司重入（一个公司一个 active ticket）

- 本公司既有 active / closed ticket：`NONE` 或 `R-XX / episode ID`。
- 本卡所处的机制格：`机制域 × 当前状态 × 竞争叉`。
- 相对既有 ticket 的**新**机制格、而非新增资料细节：
- 必须新增的主/反方、前瞻判断、简单基线与同口径结果合同：
- 不能作为重入依据的新增材料：

若已有 active ticket 而本栏不能同时指出新的机制格和新的 FJ/基线/结果合同，本卡只能标
`EXPLORATION_ONLY`；停止继续阅读该公司，转向空白格、近失效或边界复验。新年报、电话会、
更长 chronology、重复来源或更多 agent 意见本身都不是重入理由。已冻结的旧卡不追溯补写本栏。

## 上一轮学习的应用（仅在存在相关 `MULTI_COMPANY_METHOD_REVIEW_REQUIRED` 后填写）

不能因写出一条 `LNOTE:` 就称为已学习。每一条与本实验状态/机制范围相关、且已进入跨公司方法复盘的 note，必须在**不同公司**的本轮实验中明确处置为 `APPLIED / NARROWED / INAPPLICABLE`；没有处置的对象不能称为该方法的 replication，可仅作为探索或 `NO_PRIMARY`。

| source `LNOTE:` / review decision | note 要求的改变 | 本轮冻结前实际改变的字段与 locator | 仍可能推翻该改变的反例/边界 | reviewer verdict |
|---|---|---|---|---|
|  |  |  |  | `APPLIED / NARROWED / INAPPLICABLE` |

- 若为 `NARROWED` 或 `INAPPLICABLE`：说明状态不匹配或为何缩小；不得沉默丢弃。
- reviewer 只核对 note → review → 本卡的字段改变是否在冻结前存在；不读取结果，不评价价格、回报或公司结论。
- 正式 `JUDGMENT_SELECTION_EPISODE` 必须另保存 append-only `LAPP:` application receipt：它逐项列出 source `LNOTE:`、review decision、目标公司簇/冻结 ID、目标 ledger 的 JSON pointer、旧规则与实际冻结的新值；不同身份 reviewer 以 `CONFIRMED_FIELD_CHANGE` 确认。仅有本表但无 receipt，不计为迁移复验。
- 当前没有相关跨公司 review：写 `NOT_YET_APPLICABLE`，不伪造一条应用记录。

## 前瞻表达（仅在实验需要时填写）

- 不确定性形式：`DIRECTION_ONLY / RANGE / PROBABILITY / NO_FORECAST`
- 若为 `RANGE`：上下界的经济约束与可接受结果来源：
- 若为 `PROBABILITY`：同定义独立 episode 或外部频率来源、事件定义、校准计划：

没有上述概率基础时，必须保留 `DIRECTION_ONLY`、`RANGE` 或 `NO_FORECAST`；主观信心不得写成概率。

## 对照与退出

- 最强替代机制或近失效反例：
- 预期会出现的不同观察：
- 停止继续深挖当前对象的条件：
- 可能的迁移复验对象/选择规则：

## 结果与方法裁决（实验结束后填写）

- 新方法实际改变了什么：
- 未能解决的边界：
- 裁决：`RETAIN / MODIFY / REJECT / INSUFFICIENT_TEST`
- 对方法、模板、研究队列或禁用项的具体更新：
- 下一轮迁移复验：
