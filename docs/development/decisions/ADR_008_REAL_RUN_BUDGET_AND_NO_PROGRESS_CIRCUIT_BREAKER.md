# ADR-008：真实运行预算与无进展熔断

- 状态：Accepted
- 日期：2026-08-03
- 范围：自动 unified 报告生成与修复

## 背景

真实报告曾在框架缺陷尚未定位时反复调用模型。修复轮虽然是 fresh context，但缺少运行前成本上界、无进展检测和综合轮写入隔离，导致同一阻断可反复消耗调用与上下文。字符数和旧式多 Agent 规则还会放大冗长，而不保证投资判断质量。

## 决策

1. 真实运行是已完成框架修复的验收手段，不是在线调试循环。
2. 首次付费调用前生成 `run_budget_preflight.json`。超过调用、时间或重复实跑阈值时必须由操作者显式传入 `--approve-expensive-run`。
3. 显式批准只跨过预检，不取消硬限制：最长墙钟时间、总调用数、未缓存输入 token 和输出 token 仍然 fail closed。
4. 连续两轮阻断集合完全不变即停止。产物与断点保留，下一步必须先离线修框架并通过回归测试。
5. 普通章节轮不得写决策/证据/估值/论点账本或组装报告；结构化综合轮不得重写已经通过的章节。
6. 每个开发阶段最多进行一次未经再次批准的长真实基线。发现首个框架性缺陷后停止，不以重复实跑探索修复。
7. 后台运行按里程碑检查，不做高频轮询。
8. 结构化账本按`claim → valuation → thesis/findings → insight → review`硬依赖执行；前置账本未到`DECISION_READY/MONITORING`时，后续写工具不得运行。
9. 账本先以未冻结状态通过结构验证，再由程序向声明章节追加canonical引用块并重新验证、冻结。模型不得为了补机器身份而重写已经通过的分析正文。
10. 同一结构化写工具连续两次返回完全相同的阻断集合时，立即结束真实运行；不得依靠提示词重复碰运气。
11. 所有结构化写工具（包括决定性问题 findings）必须同时具备三项能力：写入前可读取精确嵌套契约及当前合法 ID、失败时返回并持久化最近一次验证结果、连续同错时进入统一熔断。只在工具描述中列字段名不构成有效契约。
12. 依赖守卫必须绑定“产物 gate”而不是同阶段的“计划 gate”。例如 insight 的前置条件是 `decisive_question_findings_validation.json=DECISION_READY`；`decisive_question_validation.json=REVIEWABLE`只表示问题计划可执行，不能替代研究完成状态。每条依赖必须有“正确产物放行”和“仅有计划仍阻断”两向测试。
13. 单任务研究在任一时刻最多只有一个`active_task_id`。完成工具缺失task ID时，只允许从持久化执行账本中安全补全这个唯一ACTIVE身份；显式冲突ID仍须拒绝。完成提交也进入统一同错熔断，且复杂finding必须用完整嵌套schema约束，不能只靠提示词描述。
14. repairable completion 跨 fresh context 恢复时，必须注入上次验证错误、可用机器source ID及其工具/参数、上次finding和实际mutation diff。只保存错误而不向下一上下文披露等同于丢失断点；恢复轮必须基于旧finding逐项修正，禁止重新猜测。
15. 工具级同错熔断必须穿透fresh-context orchestrator，属于非重试错误；外层不得把它降级为普通上下文耗尽。若provider漏掉可由结构化finding唯一确定的控制字段，可作保守确定性映射（如resolution→outcome）并记录`*_inferred`；无法唯一映射时仍须拒绝。
16. 有界研究写回章节后必须立即运行该章canonical decision binding检查，并把自由关键值、错误ID和值不匹配作为repairable completion阻断；不得拖到最终assembly才暴露。decisive plan输入指纹刷新时，只有全部question/signal/explanation/evidence语义身份仍通过验证，才可确定性重绑findings；语义改变必须拒绝并重新研究。
17. 当剩余阻断仅为`Decision ledger/Decision compiler`身份错误及其派生的quality-hard失败时，必须进入binding-only最小修复：关闭来源深化和计算，工具层只开放合同、现有章节、审计及章节写回；不得改变数值、结论、参数、仓位或触发器。该模式必须允许修复Ch0/Ch14正文，不能误路由成“结构化综合只读轮”。
18. `write_chapter`返回`passed=false`或decision binding为`INVALID`时，该章不得进入本轮passed集合，即使传统audit/depth已经通过；外层不得因此继续下一研究型pass。
19. 即时章节binding必须同时覆盖两类错误：自由关键值，以及`[decision: D-id]`附着到错误值/含义。只检查compiler、不检查decision ledger引用关系会产生假通过。
20. binding-only目标全部通过或写入预算耗尽后必须立即结束当前context；纯文本响应不得回落到综合账本提示。`read_structured_ledger_contract`在该模式下参数级只允许`decision_binding`，且schema收窄不得污染共享tool registry。
21. 能唯一判断的错误D-id删除与canonical补绑属于确定性文书工作，必须在模型调用前执行；不得为了几个锚点让模型重输整章。只有非canonical情景/模型身份无法唯一确定时才进入有界模型修复。
22. binding-only不得初始化或覆盖`research_execution.json`。已完成completion但上一次进程被中断时，允许新的repair-only运行进行零模型幂等validation-only组装，以新run manifest诚实记录`COMPLETED/VALIDATED_NOT_PUBLISHED`；禁止篡改旧INCOMPLETE manifest。

## 后果

- 自动化仍保留：小型运行直接执行，已明确批准的长运行可一次跑完。
- 预算从“事后观察”变成“事前协议 + 运行中熔断”。
- 报告可能更早停在 `INCOMPLETE/BLOCKED`，但不会用高调用量掩盖框架无进展。
- 质量门、证据门和决策一致性门不因节省 token 而降级。
- 路由中明确拒绝的模型使用`status=rejected`及`role=rejected`身份；活动模型仍只允许primary/corroborative/stress，避免拒绝路线与活动模型角色混淆。
- 最近一次 findings 尝试的验证结果独立保存，不覆盖已通过的 canonical gate；这样既能诊断失败，也不会让无效尝试污染正式状态。
