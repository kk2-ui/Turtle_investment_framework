# Claude / Agent 兼容入口

本仓库的当前工作规则统一由 `AGENTS.md` 管理。旧V12 Claude指令已经归档到 `docs/History/v12/CLAUDE_V12.md`，不得作为当前执行入口。

新会话按以下顺序恢复：

1. `AGENTS.md`
2. `GOALS.md`
3. `docs/CURRENT_DOCUMENTS.md`
4. `docs/development/LONG_TERM_ROADMAP.md`
5. 当前任务对应的阶段或产品规范

当前阶段为 Phase 08 `G1_CANDIDATE_MATURATION / IN_PROGRESS`。G1.5双向层级研究已规划但未激活。不要从 `docs/History/`、旧handoff、旧dashboard记录、V12手册或Graham迁移计划恢复状态。

普通分析入口和工具说明见 `AGENTS.md`；真实运行边界见 `docs/RUNTIME_OPERATIONS.md`；黄金报告内容契约见 `GOALS.md`。
