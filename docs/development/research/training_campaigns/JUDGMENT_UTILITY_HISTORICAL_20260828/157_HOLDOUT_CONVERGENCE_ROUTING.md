# Holdout 收敛发现：停止重复配对，回到真实反馈驱动的训练

## 发现

V4（范围一致的 composite metric）与 V5（两张 Teaching mechanism card）在公平的实际 Baseline 上都没有产生材料性经济处理差异。两次都没有读取目标 FY2024 结果。其正确含义不是“没有训练价值”，而是当前的普通 judgment-first Baseline 已经会：

- 不把活动、门店、客户或平台规模自动计入正常盈利、owner cash 或资本回收；
- 把局部边界、cohort 或现金桥问题局部化；
- 在恢复未被证明时保留条件性而非把单项 UNKNOWN 扩大为公司拒绝。

因此，规则和 generic Teaching card 在这些案例中只是重述了既有能力。拿结果去比较两份实质相同的处理会制造虚假的方法效用，不能继续。

## 路由改变

下一训练动作不是再选择一个“更可能让 Baseline 出错”的 Holdout，也不是把 Baseline 写弱。它是一个新的、结果隔离的 Blind episode：先让 Agent 对真实经营矛盾作出完整判断，随后从结果反馈中识别**实际材料性推理误差**或实际改变下一公司处理的行为。

只有出现下列真实信号之一，才把它转成下一轮 paired Holdout intervention：

1. 反馈显示 Baseline/现有 judgment 在正常盈利、owner cash、永久损失、估值方向或 rank-one research action 上的处理被具体事实推翻；或
2. 一条反馈导出的研究行为已在另一未知公司的结果前判断中实际改变了上述处理。

这不是新的 admission gate。Blind 继续可以运行、UNKNOWN 仍只局部化、公司判断仍必须完成。它只是避免把没有差异的 prompt/memory pair 反复包装为训练。

## 当前权限与结论

CN300059 与 CN601933 的 FY2024 均保持 sealed。V4/V5 都没有 `METHOD_VALIDATED`、`TRANSFER_CANDIDATE_CREATED` 或 `TRANSFER_VALIDATED`。不授予 CJO、正式估值、BuyBand、报告或投资权限。
