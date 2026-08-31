RETURN — anonymous first-review blinding is not protected; do not execute any cell or open the outcome gate.

# 家电 8 公司报告自主性 2×2 盲测：预注册独立工程／研究协议审阅

**审阅范围：** `REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231` 的本地、截止前协议控制面。未读取 cutoff 后 outcome、价格、回报、估值、既有目标报告或投资结论；未调用外部模型 API。

## 决定

除匿名性外，预注册的样本冻结、四臂合同、训练记忆边界、执行前状态与 outcome gate 都满足本审阅的协议要求。但匿名 manifest 不能支持真正的匿名首审，因此本次结果为 `RETURN`，并阻断第 1 步 cell 执行。

## 通过的控制

### 1. 候选宇宙、选择与追溯

- 机器登记固定 13 个候选、单一 `CN_APPLIANCE_LISTED:20181231` stratum、配额 8、`CUTOFF_ONLY_FIXED_STRATUM_RANK` 和 `NO_REPLACEMENTS_AFTER_COHORT_FREEZE`。
- 8 个 `ELIGIBLE` 的排序选择与 case 一致：`CN:000016`、`CN:000404`、`CN:002403`、`CN:002543`、`CN:002614`、`CN:002676`、`CN:002705`、`CN:603355`；它们恰为按 rank 排列后的前 8 个 eligible 候选。
- 5 个排除均保留可定位的审核来源与明确理由：`CN:000521`（A/B 双证券身份映射未闭合）、`CN:002035` 与 `CN:002508`（既有 Round10 campaign exposure）、`CN:603515`（FY2015 年报缺失且 cutoff metadata firewall breach）、`CN:603868`（FY2015 年报缺失）。对应证据分别回链到家电候选来源／身份审计 A、B、C；没有结果导向替换路径。

### 2. 32 个合同与共同事实

- 全部 32 个 cell 的合同均为 `enterprise-underwriting-training-contract.v2`，均为 `NOT_STARTED`，attempts 均为 `{episode: 0, reader_report: 0}`。
- 对每一 case，剔除预期不同的 `contract_id` 和 `TRAINING_MEMORY` 来源后，四臂的完整合同内容与 `PRE_CUTOFF` common source 完全相同。每组 memory 增量正确：A00 无、A01 仅行业、A10 仅人工纠偏、A11 两者。
- 8 个共享 source package 均指向本地 cutoff-only 原始事实包。包内保留合并口径和 component allocation 的 `UNKNOWN`，没有把 group fact 提升为 component fact；既有独立 package review 的这一结论与本次抽查一致。

### 3. Training memory 边界

- 行业记忆和人工纠偏记忆在每个 case 都明确为 `TRAINING_MEMORY`、`company_free: true` 和 `target_company_evidence_allowed: false`。
- 实际文本是可迁移的研究问题、反转观察和方法规则，不是 8 个目标公司的事实。合同 system prompt 也禁止把 `TRAINING_MEMORY` 引为 target-company evidence trace。
- 身份复取证审阅仅作为历史 issuer identity／训练素材边界的证据；本次没有把它的公司事实迁入 target cases。

### 4. 执行与 outcome 门

- 32 个 cell 均未开始；工作树中不存在登记约定的 `stage5_report_autonomy_appliance_20181231` 执行 artifact root。
- outcome gate 为 `BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN`，`outcome_access_authorized` 为 `false`，并要求全部 8 个 case 的 reviewer-freeze receipt。

### 5. 已验证的防错能力

实际登记可由 fixture 经 generator CLI 逐字节语义等价地重建，标准 validator 返回 `REVIEWABLE`。定向内存篡改检查也确认 validator 会拒绝：

- 某 arm 的 common-source drift；
- A00 获得未声明的 training memory；
- 无一次 episode／report 却标为 `FROZEN`；
- 预 outcome 的 outcome-access authorization。

这些检查适合阻止会改变 arms 对比基础、一次性执行纪律或 outcome 隔离结论的错误。

## 返回项：匿名 manifest 可逆地暴露 arm

**根因分类：** `MODEL`

`00_MULTICOMPANY_PREREGISTRATION.json` 的公开 `anonymous_review_custody.mapping` 在同一机器登记中直接保存每个 `anonymous_label → arm_id` 对应。即使假定 reviewer 只看 `reviewer_manifest`，generator 仍以固定顺序生成标签：每个 case 的 `ANON_01…ANON_04`、`ANON_05…ANON_08` 等，按 `A00, A01, A10, A11` 循环。故 label 的序号对 4 取模即可恢复 arm；匿名目录序号也相同。

现有 validator 仅检查 manifest 文本中没有字面 `A00`、`A01`、`A10` 或 `A11`，并不检查公开登记是否包含 mapping，也不检查标签／路径序号是否编码固定 arm 顺序。因此当前冻结登记仍被标准 validator 判为 `REVIEWABLE`，但该判定不能代表匿名首审是盲的。

**实验影响：** 这是材料性问题。能识别 treatment 的 reviewer 可有意或无意以“应有的训练记忆”影响首稿质量评价；随后任何 A00/A01/A10/A11 的差异都不能归因于处理，而会损害行业记忆、人工纠偏记忆及交互项的效用结论。

**缺失事实与禁止假设：**

- 未证明 reviewer 无法读取公开机器登记或从 label／path 序号推断 arm。
- 不得假设 reviewer 不会察觉每四个标签的固定 arm 排列。
- 不得把“manifest 中没有字面 arm_id”当作匿名性成立的证据。

**可执行修复：**

1. 将 arm mapping 移出公开预注册和 reviewer 可读目录，改为独立 custodian-only artifact；公开登记只保留不会还原 arm 的 reviewer manifest。
2. 由 custodian 在冻结时对每个 case 的四个 items 做非固定置换，并使用与 arm 顺序、case 序号和 artifact path 均无位置对应的 opaque labels／paths；reviewer artifact 中不含可恢复 mapping。
3. 修改 generator，使 public register 不生成或写入 `mapping`，并修改 validator：检查 public/reviewer manifest 无 arm field、无公开 mapping 引用、无通过 label/path 序号的固定 `A00/A01/A10/A11` 对应；custodian mapping 仅在隔离接口上进行一对一完整性验证。
4. 增加定向负测：给定 reviewer 可见的公开登记、manifest 和路径，任何 label-to-arm lookup 或固定序列编码均必须被拒绝。保留现有 common-source、memory、execution-state 和 outcome-gate 负测。

**验收标准：** 一名 fresh reviewer 仅获得 reviewer-visible materials 时，不能从公开预注册、label、case id 或 artifact path 恢复 arm；custodian 在不向 reviewer 暴露 mapping 的条件下仍能证明 32 个 case×arm 项的一一覆盖；新 generator／validator 的正测和上述匿名负测通过，且仍确认 13→8 selection、32 个 v2 未执行 contracts 与关闭的 outcome gate。随后需要一份新的独立盲测协议审阅 `PASS`，才可执行 cell。

## 实际运行的定向检查

1. 运行 generator CLI 到临时目录，并与冻结登记及直接 generator 输出比较：通过（精确相等）。
2. 对冻结登记运行 `validate_multicompany_preregistration`：返回 `REVIEWABLE`；该结果暴露了本 RETURN 所述 validator 缺口，而非匿名性通过。
3. 运行 13→8、32 cell/v2、共同合同、memory 边界、未开始状态和 outcome-gate 的只读断言：通过。
4. 运行四项协议负测（source drift、A00 memory 注入、无产物冻结、提前 outcome access）：全部被拒绝。
5. 尝试运行两份相关 pytest 模块；环境的 Python 3.14 未安装 `pytest`，所以未运行全套 pytest。未安装依赖，也未做全仓库回归；上述 stdlib 定向检查覆盖了本审阅所需协议路径。

