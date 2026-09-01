RETURN

# 家电 8 公司报告自主性 2×2 盲测预注册复审

## 结论

本次修复没有实质满足 arm 盲审。唯一阻断项的根因是 `MODEL`：公开可得的生成器本身保存了完整的 `case × arm → anonymous_label` 对照表。一个拿到公开预注册和该生成器的审阅者无需接触 custodian 文件、执行产物或任何 outcome，即可还原全部 32 个匿名条目的 arm。

这会使匿名首稿审阅可被处理组知识影响，从而破坏行业记忆、人工纠偏原则及其交互项的效用归因。它不直接改变任一公司的估值或投资结论，但足以让“哪种报告自主性训练改善了投资研究判断”的中心实验结论失真，因此本预注册不得进入执行。

本复审未读取 cutoff 后 outcome、价格、回报、估值、既有目标报告或投资结论，也未调用外部模型 API。

## 阻断项：公开代码可精确还原匿名 arm

`scripts/report_autonomy_appliance_cohort_prereg_generator.py` 的 `_OPAQUE_LABELS_BY_CASE_AND_ARM`（109--142 行）逐项保存所有 32 个关系；生成 reviewer manifest 时（450--453 行）和生成 custodian map 时（553 行）均直接使用该表。实测以公开 JSON 的 reviewer manifest 与这个公开模块相连，可恢复 `32 / 32` 个 case--arm--label 关系。

这不是 label 排序是否巧妙的问题：label 本身虽然为无数字的 `ANON_*` 词，且每 case 的 arm 到 label 列表不是字典序，但公开常量提供了精确解码器。当前测试仅确认 manifest 字符串中没有 `arm_id`，以及映射顺序不等于字典序；这些断言会在完整解码器仍公开时通过，因而不能证明盲审。

此外，`custody/01_CUSTODIAN_ARM_MAPPING.json` 位于普通项目文档树中。`visibility: CUSTODIAN_ONLY` 是数据字段而不是交付边界；若该目录和生成器随普通仓库材料交付，审阅者仍会取得 map 或其等价物。公开 JSON 当前没有直接引用该文件名是正确的，但不足以形成 custodian-only 隔离。

不得作出的假设是：

- JSON 内未嵌 mapping 就等于 reviewer 无法取得 mapping；
- 无数字 label、无 arm 字符串的匿名路径或非字典序足以抵消公开反向表；
- `CUSTODIAN_ONLY` 字段能替代独立的文件/交付边界。

可执行修复：从所有会交付给 reviewer 的源代码、测试夹具、生成输入和文档中移除 `_OPAQUE_LABELS_BY_CASE_AND_ARM` 及任何等价 case--arm--label 对照；公共生成器只能消费已冻结的无序 opaque reviewer manifest，不能生成或导入 custodian map。把完整 map 和能从它导出 map 的生成逻辑放到 reviewer 交付物之外的 custodian-only 存储/执行环境。custodian 环境再以 private validator 将该 map 与公开 manifest、32 个 arm cell 和匿名 artifact bridge 做一对一验证；map 内容或其路径均不可回写到公共 preregistration。

验收标准：

1. 从一个 fresh、仅含 reviewer 可见文件的环境，不能导入、读取或由任何公共生成器/夹具派生 case--arm--label 对照；公开 manifest 只含需要审阅的匿名 label 与匿名 artifact 引用。
2. 一个私有 custodian 测试仍能验证 8 × 4 的完整双射、每项的 source/artifact bridge，以及它与公开 manifest 的精确覆盖；该测试及其 fixture 不进入 reviewer 交付物。
3. 新负测试必须在（a）公共模块或 fixture 含任一 arm--label 对照、（b）匿名路径含 arm 标识或位置式 label、（c）custodian map/path 出现在公共交付物时失败；正测试必须证明隔离环境可审阅 32 条 manifest 但没有上述对照。

## 其余审阅范围

| 项目 | 结果 | 证据与限制 |
| --- | --- | --- |
| 13 → 8 冻结及排除追溯 | 通过 | 输入和公开登记保留 13 个候选、8 个 `ELIGIBLE`、5 个具名排除理由；选择器验证 quota、无 replacement、并要求选中项为固定 stratum 的前八个 eligible rank。A/B/C cutoff-only audits 与候选证据引用对应。 |
| 32 个 v2 未执行合同及共同事实 | 通过 | 登记包含恰好 32 cell，均为 `NOT_STARTED`、两类 attempts 均为 0；每个 contract 通过当前 v2 training validator。多公司 validator 对每 case 比较相同的 `PRE_CUTOFF` sources 和完整的非记忆 contract projection。 |
| 四臂的恰当记忆增量 | 通过 | `A00` 无训练记忆，`A01` 仅行业记忆，`A10` 仅纠偏原则，`A11` 两者；validator 比较实际 `TRAINING_MEMORY` sources 与 arm 声明的精确集合。单次 episode/report 预算、无重试重写和禁止 outcome/价格/网络/仓库/父级/同级访问也已登记。 |
| training memory 的 company-free 边界 | 通过 | 两份 memory 都明确为训练记忆/问题与原则而非目标证据；当前 8 个 target 的代码和名称在两份 memory 中无命中。schema 同时要求 `company_free: true` 与 `target_company_evidence_allowed: false`。这只验证输入边界，不把 memory 的任何概括变成目标公司事实。 |
| private map 的双射和公共 JSON 引用 | 部分通过，但被阻断项覆盖 | private validator 对现存 map 返回 `REVIEWABLE`，并验证完整 32 条 case×arm 双射和 artifact bridge；公共 JSON 不含 `01_CUSTODIAN_ARM_MAPPING.json` 文件名。不过该 map 的等价公开常量及普通目录存放使“custodian-only”没有成立。 |
| outcome gate | 通过（限预执行状态） | `outcome_access_authorized` 为 `false`，状态为 `BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN`，并列出全部 8 个 case freeze receipt 要求。此时尚无执行 receipt，故没有把 gate 的未来开启当作已验证。 |
| 新增正/负测试 | 部分通过 | 正测试有效覆盖 13→8、32 contract、共同 source、四臂记忆、无 retry 和 private map 双射；负测试有效拒绝显式 mapping 字段、`ANON_01`、匿名路径 `A00`、交叉 arm source drift 与提前 outcome access。它们没有攻击“公共生成器含完整映射”或“custody 文件随公共材料交付”这两个实际失败模式。 |

## 运行的检查

运行 21 项相关定向测试：两份 preregistration 模块测试 `12 passed`；另运行 9 项 training-contract / blind-replay / sealed-source / company-free-memory / outcome-payload 定向测试，`9 passed`。合计 `21 passed`。使用 `PYTHONDONTWRITEBYTECODE=1` 及 `-p no:cacheprovider`，没有进行全仓库回归。

另外以公开 preregistration、现存 custodian map 和 validators 进行只读结构检查：公共登记与 private map 各自返回 `REVIEWABLE`，公共 JSON 不直接提及 custodian map 文件名；但公开生成器仍恢复完整 `32 / 32` 映射。这说明现有通过的测试证明了结构一致性，不能证明盲审隔离。
