# 判断反馈控制面：M10.1 登记契约

> 状态：`IMPLEMENTED / R&D_CANDIDATE / M10.1_ONLY`  
> 代码入口：`scripts/judgment_feedback_control.py`  
> 不代表：结果采集、机械结算、诊断或真实判断训练已经完成

本契约只解决长期等待中的一个问题：已冻结的判断及其不同反馈时钟可以在同一数据库中被明确登记、恢复和按时唤醒。它不从 Markdown 推测判断，不读取未到期结果，也不重新计算任何竞争机制的胜负。

## 使用方式

实验目录必须显式提供 `judgment_feedback_control.json`。每一个 `claim_id + stage_id` 是一个独立反馈项目；S1 与 S2 不会相互覆盖。

```json
{
  "schema_version": "judgment-feedback-control-registration.v1",
  "episode_id": "R-XX",
  "company_id": "CN:000000",
  "frozen_at": "2026-08-22T12:00:00+08:00",
  "claims": [
    {
      "claim_id": "FJ:CUSTOMER_RESPONSE",
      "stages": [
        {
          "stage_id": "S1_CUSTOMER_COMPETITION",
          "source_kind": "OFFICIAL_COMPANY_DISCLOSURE",
          "source_ref": "official:future-Q3-release",
          "eligible_at": "2026-10-31T23:59:59+08:00",
          "overdue_at": "2026-11-30T23:59:59+08:00",
          "settlement_version_policy": "INITIAL_DISCLOSURE",
          "frozen_artifact_ref": "thesis_test.json",
          "source_contract_ref": "08_outcome_acquisition_contract.json#/stages/S1",
          "measurement_contract_ref": "08_outcome_acquisition_contract.json#/stages/S1/measurement"
        }
      ]
    }
  ]
}
```

三个 artifact reference 相对实验目录解析，并且必须指向已经存在的文件；JSON pointer 只描述文件中的定位，不会复制其正文到 SQLite。`register-experiment` 成功后为每个项目追加一条系统生成的 `CLAIM_REGISTERED` 事件。

```bash
.venv/bin/python scripts/judgment_feedback_control.py init --db stock_analysis.db
.venv/bin/python scripts/judgment_feedback_control.py register-experiment \
  --db stock_analysis.db --experiment-dir docs/development/research/experiments/R-XX
.venv/bin/python scripts/judgment_feedback_control.py inbox \
  --db stock_analysis.db --as-of 2026-10-31T23:59:59+08:00
```

## 当前强制的控制语义

- 采集、结果包、读取证明、提取和结算必须按顺序发生，且不得早于 `eligible_at`；
- `INITIAL_DISCLOSURE` 只允许一次结算；`LATEST_OFFICIAL_AS_OF_EVALUATION` 要求连续版本和前一事件引用；
- `NOT_DIAGNOSTIC` 与 `MEASUREMENT_MISMATCH` 不得创建方法学习；
- 诊断必须同时记录认识论位置（`STATE` 至 `ENVIRONMENT`）和生产根因（`DATA_COVERAGE` 至 `WRITING`），两轴不混用；
- `METHOD_TRANSFER` 只能指向不同公司，且必须记录目标冻结工件、实际改变字段、改变前后含义、目标作者与独立 reviewer；
- 结果暴露违规会阻断 learning note 与 learning application。

`reconcile` 与 `inbox` 均为只读派生操作；持久状态来自 `stock_analysis.db` 的 `judgment_feedback_claims` 与 `judgment_feedback_events`。

## 当前执行边界

R05/R06、`outcome_acquisition.py`、`live_forward_signal_settlement.py` 与
`judgment_learning.py` 已接入控制面适配器。`OUTCOME_PACKAGE_READY`、读取、
提取、结算和 learning 事件只会在下层模块产生实际结果包、读取回执、提取验证、
机械结算或 learning receipt 后追加；采集失败则显式留在 `BLOCKED/P1`。不能再用
`artifact:fixture` 或事件名称伪造推进。

这不等于已经验证了真实中国企业选择判断：R54 是 `NO_PRIMARY` 的机制探针，
只能完成机制结算，不能进入选择准确性、方法学习或跨案例复制。只有未来具备
`SELECTION_ADMITTED`、非共同方向性证据、公平基线及同口径结果合同的中国
episode，才能走 selection/method-learning 分支。
