PASS

# 家电 8 公司报告自主性 2×2 盲测：opaque label 匿名协议独立复审

审阅对象限于家电 cohort 的结果前预注册、公开生成器、匿名 packet builder、custodian mapping validator 与其定向测试。未读取 cutoff 后 outcome、价格、回报、估值、既有目标报告或投资结论；未调用外部模型 API。

## 结论

当前实现满足 opaque-label 盲测协议。先前会把 case×arm→label 映射公开保存的表面已移除：公开预注册只保留每个 case 的四个不带 arm 字段的 opaque label manifest 项；实际 case×arm 双射只能作为运行时的 custodian 输入传给独立 validator。没有发现可由 label、本 manifest 的路径或序列化顺序恢复 arm 的实现路径。

## 逐项复核

| 控制面 | 复核证据 | 结论 |
| --- | --- | --- |
| 公开 generator 不生成映射 | `reviewer_labels_by_selection_rank` 的 group 只有 `selection_rank` 与 `anonymous_labels`；生成器独立生成 32 个 arm cell，并独立按 label 排序生成 reviewer manifest，两者没有 join 或 case×arm→label 数据结构。将每组 labels 反序后，完整 manifest 与其他预注册内容均保持不变。 | PASS |
| public manifest 不泄露 arm | manifest 的严格字段仅为 `case_id`、`anonymous_label`、共同源引用及三条匿名 artifact path；无 `mapping` 或 `arm_id`。path 以 label 为根且不含 `A00/A01/A10/A11`；全局按 label 排序，不继承 arm cell 次序。validator 同时拒绝多余 `mapping` 字段与任一 manifest arm identifier。 | PASS |
| opaque token 规则 | generator、公开 prereg validator 和 packet builder 都使用同一严格形状 `ANON_[BCDFGHJKLMNPQRSTVWXYZ]{12}`：`ANON_` 后恰为 12 个大写辅音字母。语义标签（如 `ANON_BASELINEABCD`）、数字、元音、短 token 与 arm token 均不能通过。 | PASS |
| packet 匿名边界 | packet builder 在接收 arm material 前先校验四个唯一 opaque labels；随后替换 material 内 arm identifier，并对最终序列化 packet 扫描。共享 source content 含 `A00` 的负例会被拒绝，因而共同源不成为旁路。 | PASS |
| custodian-only 双射 | `validate_custodian_arm_mapping(preregistration, custodian_mapping)` 要求运行时对象为 `CUSTODIAN_ONLY`，覆盖精确 32 个 case×arm pair、精确匹配 public manifest 的 case×label pair，并将三条源 artifact reference 回绑到实际 cell。其返回仅为 validator 结果，不把 mapping 写回 public preregistration。家电 campaign 子树不存在已保存的 mapping JSON。 | PASS |
| 13→8 cohort freeze | 输入 candidate universe 为 13，生成器只接受声明的 8 个 eligible 公司、selection ranks 1–8、无 replacement records；输出为 8 个固定 case。 | PASS |
| 32 个未执行 v2 cells | 生成结果为 8×4=32 个当前 v2 training contract cell，全部 `NOT_STARTED`，且 `episode`/`reader_report` attempts 均为 0；validator 也限制每个 cell 至多一次并验证 freshly rendered task 与 frozen contract 精确一致。 | PASS |
| 共同 source 对称与 memory 边界 | 同一 case 的四个 contract 的 `PRE_CUTOFF` source projection 必须相同。memory 必须是 `TRAINING_MEMORY`、company-free、禁止作为 target-company evidence，并且仅按预声明 arm 分配；执行工具策略禁止 network、repository、parent/sibling context 以及 outcome/price/return access。 | PASS |
| outcome gate | gate 固定为 `BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN`，`outcome_access_authorized` 为 `false`，并要求全部 8 个 case 的 reviewer freeze receipt。 | PASS |

## 验证记录

对实际家电输入的独立结构运行得到：8 cases、32 cells（全为 `NOT_STARTED`）、32 个 manifest 项（每 case 4 个唯一 label）、manifest 无 arm field 或 arm token path，outcome gate 仍关闭，预注册 validator 返回 `REVIEWABLE`。

已运行定向协议回归：家电 prereg generator、multicompany prereg validator、anonymous packet、round10 appliance v2 与 control 五个测试模块。测试主题覆盖所列 26 项控制；参数化展开后命令实际执行 `30 passed`。

持续验收条件：custodian mapping 必须只在执行时作为外部私有输入传入 `validate_custodian_arm_mapping`，不得写入家电 campaign 的 tracked public artifact。若该条件被破坏，应按 `MODEL` 根因 RETURN：它会让 reviewer 直接恢复 arm，禁止假设 reviewer 不会读取公开映射；修复为移除该 artifact 并重新以外部 mapping 运行 validator，验收为 public manifest 仍无 mapping/arm 字段且 custodian validator 对外部双射返回 `REVIEWABLE`。
