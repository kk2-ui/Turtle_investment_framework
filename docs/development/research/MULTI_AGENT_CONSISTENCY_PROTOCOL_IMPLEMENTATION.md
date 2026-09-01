# 多 Agent 一致性协议实现记录

状态：`IMPLEMENTED / OFFLINE_VALIDATED / NO_OUTCOME_ACCESS`

本实现对应 `multi-agent-consistency-protocol.v1`，并与既有
`staged_judgment_ledger.py`、`report_autonomy_bridge.py` 和
`EnterpriseUnderwritingEpisode` 保持单向连接。

## 生产协作路径

`scripts/multi_agent_consistency.py` 提供窄接口：

1. `validate_proposal`：校验角色允许的 target、共同合同、source index、cutoff 和
   `TRAINING_MEMORY` 隔离；拒绝价格、收益、结果和动作字段。
2. `freeze_canonical_ledger`：由唯一 `canonical owner` 对每个 proposal 明确
   `ACCEPT / REJECT / CONDITIONAL / UNRESOLVED`，把 `final_value` 应用到复制的
   ledger，并把提案与裁决留在旁路 freeze record；不投票、不自动选值、不补证据。
3. `validate_freeze_record`：确认 owner、ledger identity、冻结状态、裁决覆盖、
   分区互斥，并重新运行 staged ledger validator，防止旁路篡改。
4. `validate_consistency_manifest`：区分生产的一主多辅与四臂独立模式，并强制
   common source、component vocabulary、compiler、同预算和封存 outcome。
5. `validate_three_layer_acceptance`：记录第一层账本、第二层匿名审阅、第三层
   outcome 结算和第二个未见公司/时间 holdout；只有全部通过且 outcome 已结算才
   能标记 `LIMITED_METHOD_RELEASE`。`COMPILED` 或 `SEALED` 不会自动放行。

CLI 示例：

```bash
.venv/bin/python scripts/multi_agent_consistency.py validate-proposal \
  proposal.json contract.json source_index.json --mode PRODUCTION_SINGLE_OWNER

.venv/bin/python scripts/multi_agent_consistency.py freeze \
  draft_ledger.json proposals.json decisions.json contract.json source_index.json \
  --owner-id owner:primary --output-dir out/canonical

.venv/bin/python scripts/multi_agent_consistency.py validate-acceptance \
  three_layer_acceptance.json
```

## 四臂训练路径

`scripts/staged_judgment_training.py` 将每个 arm 拆成三个独立 task：

```text
J0 context → J0 validator
J1 economics（只读 accepted J0）→ J1 validator
J2 thesis（只读 accepted J0/J1）→ J2 validator
→ staged_judgment_ledger.compile → EnterpriseUnderwritingEpisode / reader projection
```

J0/J1/J2 各自是窄账本，不要求 fresh Agent 一次生成完整 Episode。阶段失败时保留
原始响应和诊断，不重试、不手改；只有三阶段都通过后，确定性编译器才建立完整
Episode。四臂模式只比较各自 frozen ledger 的实质判断，不把答案预先统一。

## 三层验收边界

- 第一层：J0/J1/J2 合法、可复核并成功投影；这只证明接口承载判断。
- 第二层：匿名 reviewer 比较公司传导、owner cash、永久损失和最强反方的扎实度；
  这只证明预结果质量。
- 第三层：独立 outcome 结算，以及第二个未见公司/时间 holdout 的重复改善；只有
  这一层重复成立，才可把训练记忆标为提高投资判断。任何较早层级都不授予方法
  release、投资授权或自动买入价。

本实现没有新增 hash、SHA、fingerprint、checksum、digest 或类似防御性机制；既有
仓库中的版本/证据契约保持不变。
