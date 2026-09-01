# Phase 06：监控与校准

> 状态：COMPLETE ｜ 优先级：P1 ｜ 依赖：Phase 04、05 ｜ 完成日期：2026-08-02

## 1. 要解决的问题

当前报告发布后缺少统一的预测、触发器和新披露更新机制，难以判断论点是否按预期发展，也无法客观改进概率和阈值质量。

## 2. 目标与非目标

- 将发布时的论点、概率、触发器和动作冻结为可复核快照。
- 新公告和定期报告到达后，只追加观察和修订，不重写历史。
- 评价触发器的可观察性、区分力、依据和动作映射。
- 将过程校准与投资结果分开，避免用单一收益率评分研究。

## 3. 核心接口

追加式 `monitoring_events.jsonl` 记录披露、事实更新、触发命中、预测结算和决策修订。通过 `report_id`、`question_id`、`fact_id`、`trigger_id`、`decision_id` 与发布快照连接。

### 3.1 发布与计划

- 正式发布自动生成`monitoring_plan.json`，锁定发布快照字节哈希、snapshot fingerprint、阈值、预测到期日和案例审核任务。
- 新unified run若检测到旧发布快照，会在官方证据平台完成后尝试处理最新披露；缺少披露日期或VERIFIED事实时产生可恢复告警，不猜日期、不静默跳过。
- 新概率集合必须给出晚于预测as-of的`resolution_due`；旧policy保持兼容。

### 3.2 严格事件契约

`research-monitoring-event.v2`要求每项事件绑定原报告、发布快照、观察时间和来源证据。来源保存文件哈希、披露时间、数据截止日和权威性。事件在文件锁内幂等追加，ID相同但内容不同直接冲突。

事件分为：

- `disclosure_observed`、`fact_observation`；
- `trigger_evaluation`、`trigger_event`；
- `prediction_resolution`；
- `decision_review`、`decision_revision`；
- `return_observation`、`process_observation`、`thesis_action`和`monitoring_failure`。

### 3.3 阈值执行

- 执行时必须与发布时unit和accounting definition一致；事实basis不匹配即无效。
- 支持单期、滚动均值、连续期和累计窗口；连续期不足返回`NOT_DUE`。
- 各披露频率有显式`late_data_tolerance_days`；容忍期后仍无观察才告警，避免把正常披露延迟误判成研究失败。
- 标记为异常值且没有第二来源确认时返回`NEEDS_CONFIRMATION`。
- 命中阈值只生成`REASSESS`任务；监控事件无权交易。决策修订必须先有独立`decision_review`。

### 3.4 校准分层

- 过程：数据错误率、参数冲突率及各自分母。
- 预测：已结算数量、Brier score和标准误；`n<5`明确禁止声称已校准。
- 触发器：评估、确认、命中、复核覆盖率。
- 决策：修订次数、预期/实际回报偏差；收益只评价决策校准，不单独证明研究真伪。
- 案例：展示`CANDIDATE/REVIEWABLE/RESOLVED/ELIGIBLE`任务，禁止自动晋级。

## 4. 实施工作包

1. 定义观察、触发、结算和修订事件schema。
2. 监测最新官方披露并复用Phase 01证据平台。
3. 对阈值实现窗口、口径、迟滞和异常值规则。
4. 触发后先重估，不机械执行清仓或加仓。
5. 输出Brier score、覆盖率、冲突率、修订及时性和预期/实际偏差。
6. 建立定期监控运行和失败告警。

## 5. 质量门

- `INVALID`：历史快照被修改；触发器口径与报告不一致；未来数据进入旧预测。
- `INCOMPLETE`：必要披露未取得或观察窗口未到。
- `WARN`：样本量不足、价格结果受外部因素主导或阈值区分力弱。

## 6. 完成标准

- [x] 发布、观察、结算和修订全链路可追溯。
- [x] 最新披露能自动生成事实差异和待复核决策差异。
- [x] 触发器不再只凭任意精确数字得分。
- [x] 至少一个完整披露周期的真实样本演练通过。
- [x] 校准面板同时展示样本量和不确定性。

## 7. 实施结果

- 核心实现：[research_monitoring.py](../../../scripts/research_monitoring.py)，并保留`research_calibration.py`旧接口兼容。
- 新机器契约：`monitoring_plan.schema.json`、`monitoring_event.schema.json`和`calibration_dashboard.schema.json`。
- unified在发布时自动建立计划，并在后续运行中尝试摄取新官方披露。
- 提供`plan/audit/cycle/scan/replay`命令；`scan`汇总过期、完整性失败和待复核任务。
- 金融街物业真实历史演练使用FY2024审计年报（2025-03-27发布）和FY2025审计年报（2026-03-26发布）：识别整体毛利率14.42%→14.19%，完成披露、事实差异和阈值评估3个事件，状态`MONITORING`、0 invalid。因没有当时真实Turtle决策，`calibration_eligible=false`，不倒灌成绩。
- 当前真实发布快照`01502_金融街物业_phase_k_20260802`已建立监控计划并通过完整性审计；5项缺口作为WARN保留，包括旧概率无到期日和高频价格阈值无迟滞区间。
- 阶段与既有主干回归：`326 passed`。

## 8. 剩余限制

真正的前瞻Brier和触发器有效性仍需等待未来披露，历史演练不能代替。部分旧文档的`published_at`为空；系统会告警并等待补全，不以董事会日期自动冒充交易所披露时间。该阶段提供研究反馈，不构成自动交易系统；任何外部交易动作需独立授权。
