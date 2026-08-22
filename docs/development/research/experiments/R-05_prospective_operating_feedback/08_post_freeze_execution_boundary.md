# R-05 结果期执行边界

状态：`PRE_OUTCOME_EXECUTION_CLARIFICATION / FREEZE_UNCHANGED`

本说明在 FY2026 Q4 结果发生前创建。它不修改 `06_forward_freeze.md` 的共同事实、H-A/H-B、阈值、窗口、结果来源合同或任何预测；它只把 P-42 的到期执行纪律明确用于 R-05。

## 允许读取的结果期材料

仅下列冻结 claim 在其窗口打开并由 `execution-status` 返回 `DUE_FOR_ACQUISITION` 或 `OVERDUE_FOR_ACQUISITION` 后，才可经完整 inventory、raw/reader、read audit 与 extraction 读取：

| claim | 允许窗口 | 可更新的唯一箭头 |
|---|---|---|
| `R05-S1` | FY2027 Q1 的 `2027-01-01T00:00:00-08:00` 至 `2027-03-31T23:59:59-07:00` | 当前交易改善是否延续到下一可比观察 |
| `R05-S2` | FY2027 Q3 的 `2027-07-01T00:00:00-07:00` 至 `2027-09-15T23:59:59-07:00` | 同一持续性箭头的较长窗口复验 |

## 明确排除的 FY2026 Q4 “脉冲”

FY2026 Q4 不属于 `R05-S1` 或 `R05-S2`，没有冻结的 A-only/B-only 区域、结果 source contract 或会改变的预先承诺动作。因此它保持 `UNREAD_NONCLAIM_RESULT`：不得下载、materialize、打开、摘要或带入红队、`07_settlement.md`、feedback 与 learning review。

Q4 的实际发布不会把 R-05 的 `execution-status` 变成 `DUE`；正确动作仍是等待 `R05-S1`。它既不是 H-A/H-B 的证据，也不是一个需要“记录但不使用”的背景事实。

## 暴露处置

每一次 R-05 结果期结算还必须在 `09_signal_settlement.json` 前保存 `11_outcome_exposure_attestation.json`：它绑定实际 read audit 的 source IDs，并登记 `NO_NONCLAIM_RESULT_EXPOSURE` 或 breach。结算器只在前者向 feedback 输出可学习 cards。

若任何研究者在 `R05-S1` 结算前已经阅读 FY2026 Q4 的结果 body、表格、数值或管理层结果归因，立刻以该 attestation 登记 `OUTCOME_EXPOSURE_BREACH`。R-05 可继续测试采集/结算管线，但对判断力验证降为 `OUTCOME_EXPOSED_TRAINING_ONLY`：不得产生可迁移 learning note、不得进入跨公司方法复盘、不得与 R-06 合并讨论信号诊断性。

这不是说 Q4 必然不重要；它只说明 R-05 没有在冻结前为 Q4 规定能改变什么的可结算任务。若将来要研究这样的中间信号，必须在另一张、结果未读的迭代卡中冻结独立的 H-A/H-B、谓词、窗口、来源与学习动作。
