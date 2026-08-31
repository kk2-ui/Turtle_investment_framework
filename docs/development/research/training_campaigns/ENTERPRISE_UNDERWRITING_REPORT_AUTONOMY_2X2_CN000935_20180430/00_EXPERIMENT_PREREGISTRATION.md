# 四川双马报告自治 2×2：结果前预注册

> 状态：`FROZEN_BEFORE_ARM_EXECUTION / OUTCOME_SEALED`
>
> 目标公司 / cutoff：`CN:000935` 四川双马水泥股份有限公司 / `2018-04-30T23:59:59+08:00`
>
> 权限：`RESEARCH_TRAINING_ONLY / NO_OUTCOME_ACCESS / NO_PRICE_VALUATION_BUYBAND_OR_INVESTMENT_AUTHORITY`

## 问题与样本选择

本实验检验两种**通用、非公司事实**输入能否在相同证据、模型和预算下，材料性改善一份完整
`EnterpriseUnderwritingEpisode` 及其首次读者报告：

1. 专家纠偏记忆（`E`）：仅提供通用的错误预防顺序；不含四川双马或水泥行业事实、结论、结果或数值。
2. 精简行业决策记忆（`I`）：仅提供截止日已冻结的水泥行业主路径、最强反方、异质公司参考类、需由目标公司验证的问题和翻转观察；不作为目标公司事实。

四川双马在 2015--2017 三份 cutoff 前官方年报中以水泥业务为主，但在 cutoff 前已经完成两家重要水泥子公司的出售，并同时出现基金投资管理和体育培训组件。这个已知转型边界能够检验研究是否把持续水泥核心、被出售盈利、出售收款、可选组件和资本/现金责任分开，而不是把行业恢复、历史合并总量或单一 OCF 直接写成公司结论。该描述只界定研究问题，不构成对正常盈利、owner cash、价值路线或后续结果的判断。

样本从中国证监会在 cutoff 前发布的 2017 年第四季度行业分类开始：枚举行业 30“非金属矿物制品业”中的深圳 A 股，利用各发行人 cutoff 前年报只保留主营业务包含熟料或水泥生产的对象；再排除已进入 Cement Pack、Course、episode/outcome 的发行人，以及年报在 cutoff 前发生取消/更新版本转换的对象；要求 FY2015--FY2017 三份年报具有单一无歧义版本，最后按证券代码升序。`CN:000546` 金圆股份因 2018-04-17 版 FY2017 年报被取消、2018-04-27 才由更新版替代，与 `CN:000789` 一并按同一来源版本规则排除。逐代码候选、主营业务筛选、官方来源与排除理由已冻结在 `04_CUTOFF_ONLY_CANDIDATE_LEDGER.json`；该账直接推出 `CN:000935` 为首个剩余候选。选择未使用任何 cutoff 后经营资料、市场价格、回报、结果裁决或预期方法效果。

## 2×2 设计

| Arm | Expert correction memory (`E`) | Compact industry decision memory (`I`) | 允许读取 |
| --- | --- | --- | --- |
| `A00_BASELINE` | 否 | 否 | 共同 cutoff-only 源包、共同 Episode 合同 |
| `A10_EXPERT_ONLY` | 是 | 否 | 共同源包、共同合同、`E` |
| `A01_INDUSTRY_ONLY` | 否 | 是 | 共同源包、共同合同、`I` |
| `A11_COMBINED` | 是 | 是 | 共同源包、共同合同、`E`、`I` |

四臂由当前 Codex 账户生成，均不覆盖模型或 reasoning 设置；每臂在 `fork_turns=none` 的 fresh
context 中独立运行。协作运行时不暴露数值 token cap，因此不虚构 token 数；可执行相等约束是：每臂
恰好一次 Episode 生成、同一 arm 恰好一次首次读者报告 follow-up、不得重试或改写，每次编排上限
900 秒，Episode 最多 60,000 Unicode 字符，报告最多 14,000 个 CJK 字符。四臂只有预注册的 `E/I`
内容有差异，共同来源文字、任务、cutoff、schema、工具权限和输出要求相同。任何 arm 不得联网、浏览
仓库、调用工具或读取其他 arm、历史公司 episode、结果材料、价格、回报、估值、投资动作或本次
reviewer 的身份映射。完整执行字段见 `01_FROZEN_SAMPLE_AND_FAIRNESS_REGISTER.json`。

四份合同和两项训练输入在执行前固定为以下精确路径：

- 合同：`contracts/CN000935_A00_BASELINE_CONTRACT.json`、`contracts/CN000935_A10_EXPERT_ONLY_CONTRACT.json`、`contracts/CN000935_A01_INDUSTRY_ONLY_CONTRACT.json`、`contracts/CN000935_A11_COMBINED_CONTRACT.json`；
- `E`：`docs/development/research/training_campaigns/EXPERT_CORRECTION_CN02669_20260831/02_COMPILED_TRAINING_MEMORY.md`；
- `I`：`docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/69_compact_industry_decision_memory_v1.md`。

## 结果前共同任务

四臂均须在 cutoff 当时回答，但不得把下列问题预先回答为某一方向：

- 水泥成熟核心的业务、区域市场、客户/渠道、单位经济与现金责任；
- 2015 年收购/并表、cutoff 前完成的两家重要水泥子公司出售，以及 FY2016--FY2017 新增子公司和基金投资，哪些可以进入持续经营比较，哪些必须隔离；
- 非水泥或投资管理/体育培训组件是已观察的组成部分、条件性组件还是不可归因对象；
- OCF、应收、存货、长期资产投入、借款和到期负债分别能说明什么，且什么仍未披露；
- 最强反方、材料性 UNKNOWN、价格前研究处理及可翻转的后续观察。

共同源包只能提供可定位事实与披露缺口，不能提供 normal earnings、owner cash、永久损失、估值或价值路线答案。目标公司的证据必须逐项写入 `evidence_trace`；`E` 和 `I` 均不得进入该字段。

## 匿名结果前审阅

独立 reviewer 先接收四份匿名 Episode/读者报告和共同源包，且不知道 arm 映射。审阅按以下顺序：

1. 共同事实、时间边界、责任边界与来源预算是否可比；
2. 每臂是否给出连续的行业—公司位置—生存/适应—正常化—现金—永久损失—价值路线判断，而非以 UNKNOWN 终止全案；
3. 对成熟核心、资产/控制边界、非水泥组件和现金/资本责任的处理是否有目标公司证据支持；
4. 两个输入各自及其交互是否改变至少一项材料性研究处理，而不是仅改变篇幅、字段数、谨慎程度或形容词；
5. 最强反方和翻转观察是否能真正改变被声称改善的处理。

更多文字、更长列表、更悲观或更乐观的语气、更多 UNKNOWN、或未改变同口径正常化/现金/永久损失/价值路线处理的差异，一律不是提升。无证据地把行业价格恢复归于目标公司、把投资/并表边界混入水泥成熟核心、或把 OCF 减全部资本开支称为 owner cash，均可构成较差处理。

匿名 reviewer 只可给出 `PREOUTCOME_COMPARABILITY_PASS`、`PAIRED_TEST_INVALID` 或一项
`MATERIAL_PREOUTCOME_DIFFERENCE_CANDIDATE`；后两者必须说明根因（`DATA_COVERAGE`、
`ACQUISITION_MODULE`、`REASONING`、`MODEL` 或 `WRITING`）、经济影响、禁止假设、可执行修复和接受条件。

预注册的对比分别是：`E` 主效应 `A10-A00`；`I` 主效应 `A01-A00`；已有 `I` 时的 `E` 效应
`A11-A01`；已有 `E` 时的 `I` 效应 `A11-A10`。交互只比较前两组成对差异是否同向、是否材料性改变
研究处理，不制造数值总分。每格只有一次冻结实现，因此任何结论只适用于本次四川双马四份输出，
不得外推为一般模型能力或训练方法已被普遍验证。

## 开封与权限边界

仅当四份 Episode 和首次读者报告均冻结、共同事实包通过 source-bound 审阅、匿名 reviewer 完成
结果前可比性判断后，独立 custodian 才能按 [outcome custody and seal](03_OUTCOME_CUSTODY_AND_SEAL.md)
读取预先锁定的官方结果源。结果不得回流改写任何 arm 的事实、判断、读者报告、输入或 arm 映射。

本实验最多生成研究训练的效用证据；不产生 CJO、正式估值、BuyBand、报告发布、投资结论或投资行动权限。
