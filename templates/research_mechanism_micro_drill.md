# 机制判断微演练

状态：`DISCOVERY / FROZEN_FOR_REVIEW / OUTCOME_REVEALED / PROMOTED / CLOSED`

用途：用一个已界定的经营箭头，反复练习问题界定、竞争机制、测量辨别与错因校正。它不是公司报告、完整 CJO、估值或准确率记录。

一张卡只处理一个问题、两条机制和一项主要未来观察。它必须小到可在一次研究会话内完成；材料变多但没有新增分歧，不得扩写本卡。

## 1｜训练边界

- drill ID：
- 核心训练域：`CHINA / OTHER`；若为 `OTHER`，它的角色：`BOUNDARY / NEAR_MISS / QUESTION_ONLY`。
- 机制域 × 当前状态 × 竞争叉：
- 训练等级：`HISTORICAL_SELF_REPLAY / ARCHIVED_EX_ANTE_EXTERNAL / RESULT_KNOWN_TEACHING_ONLY`。
- cutoff：
- 允许的结果前原始材料（至多 3 份）：
- 第一遍事实包的精确 locator（只含状态、行动、量/价/成本/现金观察；不含归因、指引理由或结局）：
- 事实包的准备方式：`INDEPENDENT_CURATOR / FROZEN_METRIC_SLICE / FROZEN_STRUCTURAL_EXTRACT / SAME_RESEARCHER_DIRECT_READ`。
- 已隔离、不得在冻结前读取的结果材料（发布者、结果事件、预计发布/提交窗口、预先可定位的日历/URL metadata、同口径标签）：
- 当前对象在训练队列中的角色：`FOCAL / NEAR_MISS / BOUNDARY / STANDALONE`。
- 本卡不能声称：Turtle 自身预测命中、概率校准、公司总判断、估值、价格、回报或中国参数（若为海外对象）。

历史结果已知时，仍可写 `RESULT_KNOWN_TEACHING_ONLY` 来练习问题设计；它不得被提升为机制结算或 learning episode。只有 outcome 在冻结前未读、且有独立结果通道时，才可使用前两种等级。`SAME_RESEARCHER_DIRECT_READ` 或任何先读到公司归因的情形必须标 `CONTEXT_SEPARATION_NOT_ASSURED`：可作流程教学，不能作为“两遍顺序”干预的证据。

## 2｜第一遍：不读解释，先写自己的机制

此处只允许使用已冻结事实包中的状态/行动/经营事实；先不读管理层的因果归因、指引理由、第三方解读或后续结果。HTML 的 table、PDF 的同页或同一段若同时含“主要由于/归因于/预期/相信”等解释，并不因格式而自动成为事实包。

若关键数值与归因同处一个父段，允许 `FROZEN_METRIC_SLICE`：在读者接触原文前，由独立 curator 或固定抽取器只交付“指标标签、数值、单位、期间、原文 locator”，并明确标出其相邻归因文本已隔离、待第二遍读取。切片必须在读取前列出**允许的精确指标标签**，只返回这些标签及对应数值；不能仅靠屏蔽 `due to`、`expect` 等词来判定一段文字是事实。不得把切片中的数字连同归因句交付；研究者若已直接看过完整父段，仍是 `CONTEXT_SEPARATION_NOT_ASSURED`。这避免因排除整段而用宽口径代理替代真正的量/价/成本变量，也避免叙事穿透关键词过滤。

- 决定性经济问题：
- 共同事实（两种机制都须解释）：
- 当前的测量边界与 `UNKNOWN`：

| 机制 | 状态 → driver → 中间变量 → 经营后果 | 该机制最怕的当前/未来事实 | 未来会首先分叉的观察 |
|---|---|---|---|
| H-A |  |  |  |
| H-B |  |  |  |

- 若 H-A/H-B 对主要观察没有不同预测：写 `UNDIFFERENTIATED` 并关闭；不得填概率或选择主路径。

## 3｜第二遍：读取解释并进行攻击

现在才读取原件中公司的解释、预测或外部 archive 作者的判断；它是待检验的主张，不会自动成为 H-A。

- 原作者/管理层主张及 locator：
- 它支持 H-A、H-B，还是双方共同可见？为什么：
- 最强替代机制如何仍解释同一事实：
- 这一遍新增了哪一个**可结算的**分歧；若没有，关闭：

## 4｜冻结最小观察合同

- 主观察（指标、对象、单位、期间）：
- H-A 的非嵌套区域：
- H-B 的非嵌套区域：
- 预期结果期一手标签/文件与 locator：
- 禁止替代：
- 定义变化或未披露时：`MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`。
- 何时可以打开结果包：

只有主观察、双方不同区域和结果合同均可写出，才可标 `FROZEN_FOR_REVIEW`。否则正确产出是 `QUESTION_ONLY` 或 `UNDIFFERENTIATED`；它仍可训练问题界定，但不进入结算。

结果材料的 publisher/event/窗口必须在 cutoff 前通过公司日历、预先可见的结果页或连续披露链定位；不得只按“通常在某日期附近会有一份 SEC/HKEX 文件”猜测。结果开启后若发现冻结的发布者或事件不对，关闭为 `OUTCOME_SOURCE_CONTRACT_MISMATCH`，不得改指向刚发现的另一份结果材料。

## 5｜结果后复盘（只追加）

- 结果期观察及原文定位：
- `A_ONLY / B_ONLY / MIXED / MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`：
- 错误位置：`STATE / MECHANISM / MEASUREMENT / TRANSMISSION / ENVIRONMENT`。
- 与“只读管理层解释”这个简化基线相比，本卡新增避免了什么具体误读：
- 下一张**不同中国对象**的冻结前改变（问题、机制、信号或计量合同）：

## 6｜升级或停止

只有同时具备完整来源包、outcome firewall、同口径结果合同、独立性说明和可复用的 learning note 时，才可升级为正式 `ELIGIBLE_LEARNING_EPISODE` 或 [研究前瞻冻结附件](research_forward_freeze.md)。否则保持微演练：它训练过程，不产生样本量、胜率或参考类频率。
