# 仓库瘦身记录

> **ARCHIVED MAINTENANCE RECORD：**一次性清理记录，不是当前路线、状态或执行入口。

> 执行日期：2026-08-02 ｜ 策略：保守清理，未跟踪核心代码优先保护

## 执行结果

- 项目总占用：`2.9G → 1.6G`，释放约 `1.3G`。
- `.git`：`939M → 3.2M`；主要为Git确认的中断临时pack，不涉及有效提交。
- `output/`：`1.6G → 1.3G`；只删除下列失败、中间态和误生成目录。
- `.venv`：`209M → 168M`；只清理可再生Python字节码缓存。
- 删除的阶段产物不在废纸篓中，不能原地恢复，但都可由统一管线重跑；有效质量基线和正式目录仍在。
- 清理后主干定向回归：Stage 1–22为`216 passed`，自动修复与完成契约为`38 passed`，合计`254 passed`。
- 全仓收集仍有两个与本次清理无关的已知问题：环境未安装可选`tushare`包，嵌套`turtle_framework/tests`与根测试包同名。

## 原则

- 只删除可再生缓存、Git确认的临时垃圾、空误生成目录和明确失败/中间态输出。
- 正式公司输出、数据库、当前代码、prompt备份和嵌套旧仓库不在本轮删除范围。
- 保留金融街Phase K、分众Stage 6、格力Stage 7作为近期质量基线。
- 旧设计文档只重新分类，不因体积小而冒险删除。

## 本轮清理范围

1. `.git/objects/pack` 中Git报告的中断临时pack垃圾。
2. `.DS_Store`、pytest/Python缓存和两份`bak_pre_dedup`备份。
3. 空的帮助/错误代码输出目录与`output/test_comparison`。
4. 分众Stage 4、Stage 5及三个失败副本。
5. 金融街Phase G–J阶段副本；保留Phase K。
6. 招商积余`try_20260726`副本；保留正式目录。

实际删除的输出目录：

- `output/--help_分析`
- `output/02027_分析`
- `output/690D.DE_分析`
- `output/test_comparison`
- `output/002027_分众传媒_stage4_coldstart`
- `output/002027_分众传媒_stage5_context_ab`
- `output/002027_分众传媒_stage5_failed_attempt1`
- `output/002027_分众传媒_stage5_failed_attempt2`
- `output/002027_分众传媒_stage5_failed_attempt3`
- `output/01502_金融街物业_phase_g_20260802` 至 `phase_j_20260802`
- `output/001914_招商积余_try_20260726`

## 明确保留

- `output/01502_金融街物业_phase_k_20260802`
- `output/002027_分众传媒_stage6_evidence_density`
- `output/000651_格力电器_stage7_coldstart`
- `quality_references/000651_gree_v13`
- `backups/`：当前大量新代码尚未形成可恢复提交，暂不清理。
- `turtle_framework/`：仅5MB但内部有独立Git和未提交改动，需单独迁移审计。
- `.omc/`：体积很小，暂不触碰会话状态。

## 后续治理

- Phase 07建立输出保留策略：正式、gold reference、最近一次validation和临时失败四类生命周期。
- 核心开发成果形成可恢复版本后，再审计`backups/`和嵌套仓库。
- 不把大PDF复制进每个阶段目录；后续由Phase 01文档manifest共享同一官方文件身份。
