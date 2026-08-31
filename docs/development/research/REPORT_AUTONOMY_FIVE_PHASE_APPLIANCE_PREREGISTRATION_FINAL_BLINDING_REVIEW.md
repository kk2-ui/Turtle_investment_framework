RETURN

# 家电 8 公司报告自主性 2×2 预注册最终盲审

## 决定

本次预注册暂不准执行。根因分类为 `MODEL`：公开生成器把“opaque label”实现为仅匹配 `ANON_[A-Z]{4,}`，没有排除可直接表达处理臂或处理顺序的词。它因此会接受 `ANON_BASELINE`、`ANON_INDUSTRY`、`ANON_EXPERT`、`ANON_COMBINED`。这类标签一旦由隔离 custodian 与相应 arm 配对，匿名审阅者可以从标签本身恢复处理信息。

这会破坏首轮读者报告的 arm blindness，使审阅文字或评分可能受预期影响，进而使随后关于行业记忆、人工纠偏原则及其联合效用的因果归因失真。它目前不改变任一公司的业务或投资结论，但会让研究方法的“自主性增益”结论失去可信的盲审基础，并可能错误地影响后续研究方法采用。

当前登记实际使用的是中性标签，且未发现实际 case×arm→label 映射泄露；这不足以替代生成器对其公开输入面所作的 opaque-label 保证。不得假设未来登记维护者、custodian 或审阅者会把“全大写字母”自动理解为中性，也不得把缺少 `A00`/`A01`/`A10`/`A11` 字面量等同于不可从标签识别 arm。

## 必须修复

1. 将公开输入和 `validate_multicompany_preregistration` 的标签规则收紧为真正不携带处理语义或位置语义的 opaque token 格式；至少拒绝 baseline/control、industry、expert/correction、combined/both/none，以及 first/second/third/fourth 等 arm 与顺序别名。更稳妥的实现是采用文档化的无语义随机 token 格式。
2. 加入生成器和公共登记验证的负向回归测试：上述语义标签与任何 arm/排序提示都必须被拒绝；原有四组中性标签仍须保持无序，重排输入不得改变公开登记。
3. 重新生成公开 `00_MULTICOMPANY_PREREGISTRATION.json`，并证明 reviewer manifest 仍只含 case、四个无序 opaque label、共同来源和以 label 命名的匿名路径；不得包含实际 mapping、arm identifier 或可反推 arm 的路径/排列。
4. 保留并复跑 custodian-only 外部 mapping 校验：它必须仅在运行时接收 private mapping，核对完整 8×4 case×arm 双射、manifest 标签集合和来源 artifact bridge；public repository 不保存该 mapping。

## 已通过的非阻塞核验

- 当前公开登记与从当前输入重新生成的登记完全一致；候选宇宙为 13、入选为固定 8、执行 cell 为 32，全部 `NOT_STARTED` 且两类 attempt 均为 0。
- 所有 32 份合同为 v2 `BLIND_REPLAY` 合同；每个 case 的四个 arm 共享完全相同的 PRE_CUTOFF 来源，差异仅为预先声明的 `TRAINING_MEMORY`。case memory 标记为 `company_free: true` 和 `target_company_evidence_allowed: false`，Episode 绑定禁止将 training memory 用作公司证据。
- 当前 reviewer manifest 只有 `reviewer_manifest` 字段；32 项恰为每 case 四项，未含 arm token，三类 reviewer 路径均仅以匿名 label 命名。重排每个 selection rank 的四个当前标签不会改变生成后的公开登记。
- outcome gate 仍为 `BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN`，且 `outcome_access_authorized` 为 `false`。
- 在内存中构造、未写入仓库的 private mapping 可被 custodian validator 接受；将其中一个 case×arm 条目重复后被正确拒绝。

## 运行的定向测试

` .venv/bin/python -m pytest -q tests/test_report_autonomy_cohort_exposure_ledger.py tests/test_report_autonomy_appliance_cohort_prereg_generator.py tests/test_report_autonomy_multicompany_prereg.py `：`21 passed`。

另运行实际公开登记的结构核验（13→8、32 v2 未执行 cell、发布物等于新生成物、manifest 字段/路径/无序性、outcome gate）及 custodian-only 外部 mapping 双射反例。该反例确认 private mapping 验证正确，但也确认 `ANON_BASELINE` 等 arm 语义标签目前会被公开生成器接受，构成本次 RETURN 的可执行复现。

本审阅未读取 cutoff 后 outcome、价格、回报、估值、既有目标报告或投资结论，亦未调用外部模型 API。
