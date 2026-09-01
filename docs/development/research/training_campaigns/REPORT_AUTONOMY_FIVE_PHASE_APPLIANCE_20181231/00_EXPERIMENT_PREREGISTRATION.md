# 报告自主性五阶段：家电 8 公司 2×2 盲测预注册

**状态：** `COHORT_FROZEN / ARM_MAPPING_CUSTODIAN_ONLY / OUTCOME_BLOCKED / CELLS_NOT_STARTED`  
**截止时点：** `2018-12-31T23:59:59+08:00`  
**机器可验证登记：** [00_MULTICOMPANY_PREREGISTRATION.json](00_MULTICOMPANY_PREREGISTRATION.json)

## 目的与边界

这是第五阶段的效用检验，不是投资研究或估值流程。它固定八个此前未用于本阶段训练的家电发行人，用同一份截止日前公司共同来源包，分别比较：基础系统、仅行业经验、仅人工纠偏原则、以及二者联合。每个 cell 只能生成一次 Episode 与一次首稿读者报告；先匿名审阅首稿，再允许隔离 custodian 打开结果字段。

本登记不产生价格、估值、买入建议、行动授权或“已证明有用”的结论。通过与否须在后续 outcome 结算后才可判断。

## 固定样本与排除记录

选择规则为 `CUTOFF_ONLY_FIXED_STRATUM_RANK`，不允许冻结后替换。八个已入选发行人为：

- `CN:000016` 康佳集团
- `CN:000404` 华意压缩机
- `CN:002403` 爱仕达
- `CN:002543` 万和电气
- `CN:002614` 奥佳华
- `CN:002676` 顺威股份
- `CN:002705` 新宝股份
- `CN:603355` 莱克电气

候选宇宙也固定保留五个经 cutoff-only 审计后未入选的发行人与理由：`CN:000521` 的 A/B 股发行人映射尚未闭合；`CN:002035`、`CN:002508` 已有 Round10 campaign 暴露；`CN:603515` 缺 FY2015 年报且 metadata firewall 曾触发；`CN:603868` 缺 FY2015 年报。每项的审计来源、排序、身份与排除理由均写入机器登记，不能在结果出现后增删或换样本。

三份候选来源审计为：

- [Audit A](../../REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_TEST_COHORT_SOURCES_A_AUDIT.md)
- [Audit B](../../REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_TEST_COHORT_SOURCES_B_AUDIT.md)
- [Audit C](../../REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_TEST_COHORT_SOURCES_C_AUDIT.md)

## 四个固定处理

| Arm | 行业经验记忆 | 人工纠偏原则记忆 |
| --- | --- | --- |
| `A00` | 无 | 无 |
| `A01` | 仅家电行业决策记忆 | 无 |
| `A10` | 无 | 仅 02669 原则记忆 |
| `A11` | 两者 | 两者 |

四臂拥有同一公司共同来源、同一截止时点、同一任务合同、同一推导接口和同一一次性预算。行业记忆与原则记忆都明确是 `TRAINING_MEMORY`，不得作为目标公司的事实来源。行业记忆只能提出假设与取证问题；共同来源包不包含正常盈利、owner cash、永久损失、估值或投资结论。

## 执行与结算顺序

1. 使用冻结合同为每个 case × arm 渲染 fresh 任务，禁止访问网络、仓库、父级上下文、其他 cell 或结果。
2. 完整保存每个 Episode、reader bridge 和首份读者报告；不允许重试、改写或事后补证。
3. Public preregistration 只冻结每个 case 的四个无序匿名标签，既不保存、也不生成 arm 对应关系。标签必须是 12 位无元音 token，不能使用 `BASELINE`、`INDUSTRY` 等可读处理词。实际执行开始时，Custodian 在公开仓库之外一次性提供并验证 private arm mapping；第三方 fresh Agent 只获得匿名 manifest 与匿名包，不能取得映射、arm 顺序或能反推 arm 的路径。其冻结审阅回执在八个 case 齐备前，outcome gate 保持关闭。
4. 隔离 custodian 仅在 gate 打开后，从截止后官方审计年报提取预注册结果字段，并按已注册规则判为支持、削弱、证伪、数据不足或无区分度。
5. 最后分别检验行业记忆、原则记忆及其联合是否对报告自主性产生可复现增益；不把单一案例或文风变化当作效用证明。

共同来源包的独立审阅已通过：[source-package review](../../REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_COMMON_SOURCE_PACKAGES_INDEPENDENT_REVIEW.md)。本预注册本身仍须经独立工程审阅后，才能执行第 1 步。
