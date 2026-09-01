# Turtle 运行治理与恢复手册

> 适用版本：Phase 08 / `runtime-governance.v1` ｜ 更新：2026-08-29

## 1. 运行原则

统一管线仍由 `analyze.sh` 或 `python -m turtle_agent.run` 启动。模型治理不会为了节省费用静默降低关键研究质量：深度研究、挑战者、报告综合和修复都要求配置中的能力下限；预算不足、关键输出截断、身份不匹配或模型不可用时，运行应暂停、阻断或失败。

用户批准的本地密钥继续放在现有 `analyze.sh` / `.env`，读取方式不变。这两个文件必须被 `.gitignore` 隔离。运行日志、缓存、`_diagnostics.json` 和 `run_manifest.json` 不得保存密钥、请求头或完整环境变量。

## 2. 配置和真源

| 文件 | 作用 |
|---|---|
| `config/runtime_governance.v1.json` | 任务能力下限、重试、超时、限流、预算、缓存和保留策略 |
| `schemas/runtime_governance.schema.json` | 配置契约 |
| `schemas/run_manifest.schema.json` | 单次运行契约 |
| `schemas/runtime_cache_entry.schema.json` | 内容寻址缓存契约 |
| `schemas/runtime_retention_plan.schema.json` | 清理预览契约 |

模型价格不会硬编码成可能过期的数据。未配置价格时仍记录精确 token 和时延，并在 manifest 标记 `pricing_unconfigured:<model>`；若需要金额估计，应先审计价格再在 `pricing_usd_per_million_tokens` 中显式登记。

## 3. 每次运行会留下什么

- `run_manifest.json`：当前运行的原子更新视图。
- `run_manifests/{run_id}.json`：不会被下一次运行覆盖的归档记录。
- `_diagnostics.json`：兼容旧工具的脱敏诊断。
- `.runtime_cache/`：仅精确匹配、纯文本、无工具调用副作用的短期缓存。

manifest 记录代码、配置、prompt和输入指纹，以及步骤、模型等级、调用尝试、token、时延、成本状态、缓存、错误、产物哈希和发布状态。它不记录 prompt 或模型正文，因此既可审计又不会复制敏感研究上下文。

## 4. 失败语义

| 情况 | 行为 |
|---|---|
| 429、网络、超时、5xx | 按统一上限指数退避；每次尝试可见 |
| 认证、普通4xx、未知错误 | 不盲目重试，向外传播 |
| 关键任务 `max_tokens/context_window` | 拒绝该响应，不缓存、不继续当完整结论使用 |
| 关键任务能力等级不足 | `model_tier_violation`，禁止自动降级 |
| 关键任务预算不足 | `budget_exhausted`，进入 `INCOMPLETE`，不截短推理 |
| 缓存过期、损坏或身份不同 | 当作未命中并重新计算，不返回旧结果 |

一次调用的瞬时错误在统一重试后成功，属于已恢复事件；若外层 fresh-context 续跑成功，也可以正常完成。只有未恢复的管线结果才会落为 `FAILED/BLOCKED/INCOMPLETE`。

## 5. 自检与恢复

以下命令只读，不会发布报告：

```bash
.venv/bin/python scripts/runtime_governance.py secret-audit .
.venv/bin/python scripts/runtime_governance.py verify-manifest output/01502_金融街物业/run_manifest.json
.venv/bin/python scripts/runtime_governance.py recovery-advice output/01502_金融街物业
```

恢复建议只给出动作，不自动发布：

- `resume_judgment_queue_validation_only`：从定向研究账本断点续跑；
- `resume_repair_only_validation_only`：使用现有完成契约执行 `--repair-only --validation-only`；
- `rerun_validation_only_from_last_verified_inputs`：从已验证输入重新跑验证；
- `manual_audit_before_resume`：manifest 指纹或身份损坏，先人工审计。

恢复完成后必须重新通过完成契约和 manifest 验证；不得直接把旧草稿复制成正式报告。

### 5.1 Golden Report 审阅返回

材料性审阅先写成符合 `schemas/golden_report_review_return.schema.json` 的候选绑定对象，再从现有输出目录运行：

```bash
.venv/bin/python -m scripts.turtle_agent.run --code <代码> --output <输出目录> \
  --repair-only --review-return <review-return.json> --validation-only
```

入口会写出 `golden_report_feedback_routing.json`，且强制 `--validation-only`，只生成待复核候选，不发布。存在开放的采集、推理或模型问题时，运行以 upstream blocked 结束且不调用 reader writer，先按其中 owner 修复公共模块并取得验收证据；纯写作问题或上游已验收后，只有结构化 `reader_conclusion`（投资结论、成立依据、投资含义和已接纳来源）可触发一次限域读者修订。自由修复指令不再是接口字段。`--review-return` 不得与 `--repair-chapters` 联用。设 `--repair-passes 0` 时只生成并检查路由，不调用模型。

## 6. 缓存纪律

缓存身份同时包含公司、期间、任务类型、模型、prompt版本、代码版本和完整请求指纹。任何一项变化都必须未命中。带工具调用的响应不缓存，避免重复执行写章、冻结账本或发布动作。损坏和过期条目不自动删除，仅记录无效并重算，后续由保留策略处理。

## 7. 清理与回滚

清理始终先预览：

```bash
.venv/bin/python scripts/runtime_governance.py retention-preview output \
  --output output/runtime_retention_preview.json
```

计划会保护 PDF、官方证据、事实/决策/估值/论点/洞见账本、发布快照、监控计划、完成契约和运行 manifest。只有拿到预览指纹并明确确认后才能执行：

```bash
.venv/bin/python scripts/runtime_governance.py retention-apply \
  output/runtime_retention_preview.json \
  --confirm-fingerprint <plan_fingerprint>
```

执行不是永久删除，而是移动到 `output/.runtime_trash/<timestamp>/`，可按原相对路径恢复。本阶段的实际全库预览没有发现达到保留期限的候选，保护了271个正式证据或发布相关文件，因此未移动任何内容。

## 8. 故障演练验收

阶段测试覆盖：能力降级、预算耗尽、429/超时重试、关键截断、缓存跨公司/跨期污染、缓存篡改、密钥泄漏、manifest伪成功、清理误伤和主流程干跑。标准命令：

```bash
.venv/bin/python -m pytest -q tests/test_stage29_runtime_governance.py
.venv/bin/python -m pytest -q tests/test_stage*.py \
  tests/test_completion_contract_v13.py tests/test_auto_repair_pipeline.py
```

## 9. 当前操作授权与付费调用纪律

自2026-08-03起，仓库操作人已给予龟龟框架真实模型运行的持续授权，不再要求每个付费前沿单独询问。该授权只免除重复确认，不扩大任务范围，也不允许以消耗额度换取盲目试错。

每次真实运行仍必须：先完成离线测试并公布调用上限、禁用项和停点；优先复用同fingerprint恢复稿；结构化writer成功后立即停止；发现新框架缺陷时停止当前run，离线修复并通过阶段回归后才能重试；同一writer连续两次失败必须熔断；不得为省token降低证据、推理、估值或决策门。汇报必须列出调用数、未缓存输入token、搜索次数、provider重试及是否发布。
