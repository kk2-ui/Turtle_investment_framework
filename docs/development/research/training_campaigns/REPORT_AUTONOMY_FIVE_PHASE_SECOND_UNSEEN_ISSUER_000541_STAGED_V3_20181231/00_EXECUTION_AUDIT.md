# CN:000541 分阶段协议执行审计

状态：`INTERFACE_VALIDATED / COHORT_NOT_STARTED / OUTCOME_SEALED`

这组工件记录协议实现前后的失败边界，不是训练效用结果：

1. 初始 `STAGE5` cohort 要求 fresh Agent 一次输出完整 `EnterpriseUnderwritingEpisode v2`；A00、A01、A11 曾完成或触及一次性响应，A10 因 route-role 绑定冲突被拒绝。四臂不齐，未开 outcome。
2. 后续 `STAGE5R` 仍采用完整 Episode 一次性生成；该路线已停止，不计为重试或能力比较。
3. `STAGE7/8` 的 J0 试运行暴露任务提示问题：一次输出了旧整账本，一次 `economic_scope` 使用自然语言，一次 J1 claims 使用对象而非数组。原始响应保留，均不手改、不重试。
4. 本实现加入 `scripts/staged_judgment_training.py` 与 `scripts/multi_agent_consistency.py` 后，分阶段任务明确为 J0/J1/J2 独立 schema；后续阶段只接受已验证的前一阶段。生产协作另用窄 proposal 与唯一 canonical owner 冻结，不与四臂答案统一。

当前尚未执行完整 `STAGE9` 或更晚 cohort 的 J1/J2，也没有四臂 Episode、匿名预结果审阅、outcome 结算或 holdout 迁移结论。因此不得把本文件标记为 `TRANSFER_CANDIDATE`、`LIMITED_METHOD_RELEASE` 或投资能力提升。

所有实验仍使用相同 cutoff、source allowlist、组件词汇和编译器；行业/专家记忆不能进入目标公司 evidence。失败根因按协议分为 `MODEL/REASONING`（一次性接口和 route/shape 误用）与 `WRITING`（proposal/ledger JSON 形状不符）；不将 `EPISODE_INVALID` 当作最差投资判断。

本轮实现没有新增 hash、SHA、fingerprint、checksum 或 digest 机制。
