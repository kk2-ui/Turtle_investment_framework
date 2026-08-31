# 阶段 5：八家公司报告自主性 2×2 结果前设计审计

## 结论

阶段 5 可以公平地检验一个**冻结 cohort 内**的报告自主性信号，但现在还不能直接开跑八家公司版本。现有单公司 2×2 的 `enterprise-underwriting-training-contract.v2`、fresh task、逐 arm Episode 绑定、组件读者 bridge、匿名标签 custody 和结果后官方字段结算，都是正确的可复用底座；它们没有形成一个能冻结 **8 个 case × 4 个 arm** 的共同对象。

最小补充不是新评分器或第二个报告 writer，而是一个 cohort preregistration bundle 及其静态 validator。它必须把样本、每格允许输入、执行顺序、无重试/无替换处置、匿名映射和每 case 的结果测量契约在任何 arm 启动前连接起来。没有这一层，八份单公司设计可以各自有效，却仍会允许跨公司样本替换、输入不对称或 attrition 被事后解释，从而材料性削弱因子比较。

本审计是 outcome-blind：未读取任何结果、settlement、历史输出、市场价格或回报，也不对任何方法效用作判断。即使该 cohort 完整通过，它最多提供预注册 panel 中的可复现性证据，**不证明**一般性 utility、模型能力或投资效用。

## 可直接复用的底座

| 现有对象 | 在多公司研究中的责任 | 不应改变的边界 |
| --- | --- | --- |
| `enterprise-underwriting-training-contract.v2` + `render-subagent-task`/`run --agent-response` | 每一格的 company/cutoff、允许来源、完整 Episode、组件决策和经济推导绑定；fresh response 成功后才持久化。 | 新 cohort 使用当前 v2 derivation interface；不把单公司 V4 的冻结旧 derivation 例外复制成新执行路径。 |
| `validate_training_episode` / fresh-response materialization | 拒绝不在 contract 内的证据、把 `TRAINING_MEMORY` 当作公司证据、价格/回报/结果 payload，以及不完整的组件经济。 | 只验证一格，不能代替 cohort 或对照公平性检查。 |
| `enterprise_underwriting_component_reader_bridge.v1` + completion gate | 从 arm 自己已验证 Episode 派生并约束其首次完整读者报告；不得让 report writer 重算经济。 | bridge 不是教师材料、目标公司事实或另一份报告。 |
| 单公司 preregistration、匿名 custody、outcome custody/seal | 提供四臂、无网络/无 sibling、先匿名审阅再开封、官方字段级结算的正确顺序。 | 单公司 arm mapping 和个案结果字段不能被当成八公司选择依据。 |

## 必须冻结的最小 bundle

所有下列对象作为同一 `REPORT_AUTONOMY_2X2_MULTICOMPANY:<version>` preregistration bundle 冻结；路径可按 campaign 目录命名，但不得按每个 case 临时另定规则。

1. `00_MULTICOMPANY_PREREGISTRATION.md`
   - 写明问题、四臂、允许的 case-local 推断、禁止的一般性 utility claim、执行日历、attrition 规则、四个预注册 estimand 和组合交互的定性解释。
   - 固定当前 Codex 账户继承的 model/reasoning、每格一次 Episode + 一次首次 reader-report follow-up、相同字数/时间上限、无网络/工具/仓库浏览、无 sibling/parent/outcome/price access。

2. `01_CUTOFF_ONLY_COHORT_REGISTER.json`
   - 记录完整候选 universe、资格/排除理由、预声明 strata、确定性排序、八个 `case_id`、公司身份、cutoff、共同 source-package ref、行业 memory ref、专家 memory ref、预先定义的结果时钟和 arm-contract matrix。
   - 每个 case 的条目必须同时列出其独立 source packet 与 arm 可见性，而不是让运行器从目录扫描“看起来匹配”的文件。

3. `02_COHORT_EXECUTION_AND_FAIRNESS_REGISTER.json`
   - 列出 32 个 `(case_id, arm_id)` cell 的 contract、rendered task、raw response、canonical Episode、reader bridge、首次 reader report 和 freeze receipt 的预定路径；以及固定运行顺序和每格的单次预算。
   - 这个 register 只记录结果前状态，如 `NOT_STARTED`、`EPISODE_INVALID`、`FROZEN` 或 `PAIRED_TEST_INVALID`；不记录判断质量、结果或任何价格字段。

4. `03_ANONYMOUS_REVIEW_CUSTODY.json` 与 reviewer packet manifest
   - custodian-only 的 `(case_id, arm_id) -> anonymous_label` mapping；同一 case 的四个标签只能关联其共同 source packet，不能暴露 arm、E/I source id、任务路径或调用顺序。
   - reviewer manifest 只交付匿名 Episode、bridge、首次 reader report、该 case 的共同 cutoff source packet 和预注册 rubric。公司名称可为审阅证据而保留；必须隐藏的是 treatment/arm mapping，不是公司事实。

5. `04_OUTCOME_CUSTODY_AND_MEASUREMENT_PROTOCOL.md` 及八份 outcome-measurement matrix
   - 每 case 在 arm 前只冻结未来观察的期间、官方来源类别、首份完整年度报告规则、字段/责任边界、连续性/MISMATCH 规则和 `SUPPORTED`/`WEAKENED_OR_FALSIFIED`/`INCONCLUSIVE_DATA`/`NON_DISCRIMINATING` 处置；不读取或列出结果内容。
   - outcome observation、settlement 和 feedback 仅可在开封后由 custodian 新建在隔离目录；它们不是上述 preregistration bundle 的输入。

6. `05_COHORT_PREOUTCOME_REVIEW_PROTOCOL.md`
   - 定义 reviewer 的比较性、材料性、反方/翻转条件、条件项不得升格和 case-local difference 判断；继续采用 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL`、`WRITING` 根因语汇。它不含 arm mapping 或结算资料。

## 样本与替换规则

1. 在冻结前，先从预声明的官方、cutoff-only issuer universe 建完整候选 ledger。资格为：公司和 cutoff 身份明确；至少三份连续、版本无歧义的 cutoff 前官方披露；能由同一 cutoff 包构造核心业务组件和一项材料的现金/资本责任问题；以及能获得 company-free 的预先冻结 industry decision memory。筛选不得查看 cutoff 后经营披露、结果/settlement、价格、回报、估值、投资行动或预期 arm 表现。
2. 为避免用某个行业或单一公司挑结果，先写明行业 strata 及各 strata 的名额（例如四个有合格 company-free industry memory 的 strata 各两家），在 strata 内按固定、cutoff-visible identifier 顺序选前两名。strata、排序字段、全部候选与每项排除原因都写入 register；不得在可用性确认后改为“更有故事性”的公司。
3. 选择前使用仅含身份和用途的 contamination/exposure register 排除任何已经是 teacher、industry pack/company projection、holdout、campaign 或 outcome object 的公司/同一重组经济主体。register 不携带结果、价格、结算方向或历史 report 文本。行业 memory 本身还须独立通过 company-free、无目标公司事实/来源/结果的验证。
4. 所有八家公司在 `COHORT_FROZEN` 前完成其 source-package 与 contract 资格检查。冻结后**没有 reserve replacement**：发现 source 缺失、contract/arm 无效、agent 失败或结果字段不可比较时，保留原 `case_id`，标为预注册处置（通常 `PAIRED_TEST_INVALID` 或 `INCONCLUSIVE_DATA`），绝不换公司、cutoff、source version、memory 或结果窗口。
5. 候选 rank 9+ 只能在 cohort freeze 前、且八个已选 case 尚未获得 task/contract/arm output 时，用已记录的纯资格失败理由补位并重新冻结整个 register。它不是 arm 后补洞机制。

这使“八家公司”成为一个冻结研究对象，而不是八次直到出现漂亮比较的尝试。

## 四臂与 fresh-agent 执行顺序

每个 case 使用完全相同的 v2 Episode contract、共同 cutoff source text、schema、tool boundary、调用次数与输出上限；差异仅为预先列出的 company-free `E` expert-correction memory 和/或 `I` compact industry memory：

| Arm | E | I |
| --- | --- | --- |
| A00 | 否 | 否 |
| A01 | 否 | 是 |
| A10 | 是 | 否 |
| A11 | 是 | 是 |

在任何 fresh Agent 启动前，cohort validator 应 render 32 个 task 并直接比较同一 case 的共同 source block、schema、cutoff、预算、tool prohibition 和 output contract；仅预注册 E/I block、相应 arm label 和无关路径名可以不同。不要以额外 hash/checksum 文件替代这种直接比较。

执行采取固定的四位置轮换，既避免 coordinator 临场选择，也不让一个 arm 总处于较早或较晚的调用位置。case 依 selection rank 1--8 进行；Episode arm order 对 rank `(1,5)` 为 `A00,A01,A10,A11`，`(2,6)` 为 `A01,A10,A11,A00`，`(3,7)` 为 `A10,A11,A00,A01`，`(4,8)` 为 `A11,A00,A01,A10`。reader-report follow-up 使用同一 case order 但将该行左移两格。每个 arm 因而在八个 Episode 与八个 report call 中各出现两次于每个位置。

对每一格依次执行：

1. coordinator 仅以该格 rendered task 启动一个 `fork_turns=none` fresh arm；它只能写一个 Episode JSON，不能读取 parent、sibling、仓库其他对象、工具、sealed outcome 或 price/return。
2. 用现有 `run --agent-response` materialize、validate 并持久化 arm 自己的 complete Episode；派生该 arm 自己的 reader bridge。验证失败不重试、不修改 prompt/源包，也不允许该 arm 读取任何其他输出。
3. 对已完成 Episode 的同一 arm session，只发一次首次 reader-report follow-up。其可见内容限于原 rendered task、该 arm 的 frozen Episode/bridge 和既有 report contract；不得引入新来源或另一 arm。报告完成后立即冻结 raw response、Episode、bridge、report 与 receipt。
4. 每 case 的四个单次尝试都要完成记录，即使某一格无效；无效 case 不会触发重跑或换公司。所有八 case 的 32 格完成/无效状态冻结后，才产生匿名 reviewer packet，且在此之前不打开任何结果源。

## 匿名审阅与隔离结算

1. **结果前匿名审阅。** custodian 以 sealed mapping 生成每 case 四个匿名包，并运行 leakage validator：reviewer packet 不得含 `A00/A01/A10/A11`、E/I 名称或 source id、task/contract 路径、调用顺序、outcome/price/return 字段。审阅者先确认共同事实/预算/时间边界是否可比，再判断连续的行业—公司—生存/适应—正常化—现金—永久损失—价值路线推理、材料组件桥、最强反方与翻转条件。它只输出 `PREOUTCOME_COMPARABILITY_PASS`、`PAIRED_TEST_INVALID` 或有完整根因/经济影响/禁止假设/修复/验收条件的 `MATERIAL_PREOUTCOME_DIFFERENCE_CANDIDATE`。
2. **custodian-only outcome acquisition.** 只有所有 reviewer decisions 已冻结且没有宣布相应 case 的 paired test 无效时，独立 outcome custodian 才可读取每 case measurement matrix 所允许的官方 cutoff 后资料，按首份完整报告及固定责任边界写字段级 observation。custodian 不读取 arm output、匿名 mapping 或 reviewer preference，也不能编辑任何结果前工件。
3. **mapping 仍密封的结算。** outcome reviewer 先将各匿名 arm 的冻结判断与该 case 的字段级 observation 对照，保持 arm mapping 密封，逐项给出预注册结果状态。缺失、口径变化或无法归属时保留 `INCONCLUSIVE_DATA`/`SOURCE_MISMATCH`，而不是换窗口、换指标或用市场材料填补。
4. **最后才揭示 mapping。** mapping custodian 在结果前审阅和匿名结算都完成后揭示 32 格 mapping。独立比较者才计算四个预注册配对：`A10-A00`、`A01-A00`、`A11-A01`、`A11-A10`；交互只作相同预注册的定性比较。任何结果只能写入 outcome/feedback 工件，绝不倒流改写 arm、source packet、memory、review 或 selection register。

## 所需 cohort validator 与验收

现有单格 validators 继续原样复用；新增一个小的 `validate-report-autonomy-multicompany-prereg` 即足够。它应拒绝以下会改变比较含义的失败：

| Validator 检查 | 发现后处置 | 为什么是材料性 |
| --- | --- | --- |
| 恰好 8 个唯一 case，完整 universe/rank/strata/资格/排除记录，且无冻结后 replacement | preregistration 不可启动 | 不然选择可随预期结果漂移（`DATA_COVERAGE`）。 |
| 每个 case 恰好 4 个 arm，32 份 current v2 contract/task 的 company、cutoff、schema、预算和共同 source blocks 相同，仅许可 E/I 不同 | 阻断执行 | 不对称 evidence 或预算会伪装为 treatment 效果（`ACQUISITION_MODULE`）。 |
| 每个 memory 被标作 `TRAINING_MEMORY`、在 target evidence trace 禁用、且通过 company-free/exposure register 检查 | 阻断受影响 cell | 教师/目标泄漏会把已知事实误作研究自主性（`REASONING`）。 |
| 固定 schedule、每格一 Episode/一 report、无 retry/rewrite，以及所有 invalid/attrition case 保留 | 阻断开封；不能补样 | 结果导向重复尝试会选择幸运 realization（`MODEL`）。 |
| custody mapping 为 32 个一一映射，reviewer manifest 无 arm/treatment/schedule leakage | 阻断匿名审阅 | reviewer 若知道 arm，结果前质量判断不能隔离（`WRITING`）。 |
| 每 case 都有结果前 measurement matrix，且 outcome access 被 reviewer-freeze receipt 闸住 | 阻断 outcome access | 事后改字段、期间或责任边界会扭曲正常盈利、现金或永久损失结论（`DATA_COVERAGE + REASONING`）。 |

验收时用纯 synthetic cohort fixture 覆盖：重复公司、跨 arm source 不等、错误 memory role、冻结后 replacement、缺失/重复 anonymous label、非法 retry、提前 outcome-access、以及 measurement matrix 与 case/cutoff 不匹配。通过 fixture 只证明控制面；不构成真实公司、方法或投资效用证据。

## 结果解释边界

每家公司先只保留 case-local paired difference。一个 factor 的 cohort-level表述必须预先限制为：八个原始 case 均保留、四格均冻结且可比、方向在八个 case 中一致、没有新增材料错误，并经独立工程复核。任何 `PAIRED_TEST_INVALID`、`INCONCLUSIVE_DATA` 或相反的材料性结果都必须随结果一同保留，不能被替换、平均掉或归为“未观察”。即使满足这些条件，正确结论仍是“该冻结 panel 中出现可复现的预注册信号”，不是 utility 已被证明，更不是估值、价格或投资行动授权。

## 审计边界

本审计只检查当前 training contract/validator、五阶段实施设计、单公司 2×2 preregistration 及其匿名/结果 custody 协议。未运行 Agent、训练、报告、网络或 API；未读取 outcome、settlement、历史 response/review、市场价格、回报或外部模型 API。

## 控制面实现

`scripts/report_autonomy_multicompany_prereg.py` 现将上述最小 bundle 作为一个
`report-autonomy-multicompany-preregistration.v1` 对象校验。它直接调用现有 v2
training-contract 与 fresh-task renderer；本身不创建 company、来源、任务、报告或
outcome 工件。它拒绝八家/三十二格不完整、跨 arm 的共同来源或合约漂移、非
`TRAINING_MEMORY` 的 E/I 输入、冻结后替换/重试、匿名 manifest 泄露、未覆盖的
measurement 以及提前 outcome access。

合成回归位于 `tests/test_report_autonomy_multicompany_prereg.py`，覆盖完整可运行
fixture、重复公司/替换、共同来源漂移、错误 memory role/重试、匿名泄露/提前开封和
measurement cutoff 漂移。它只验证控制面，仍不构成真实 cohort 或方法效用证据。
