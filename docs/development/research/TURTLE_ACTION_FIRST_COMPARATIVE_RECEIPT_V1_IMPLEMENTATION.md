# Action-First Comparative Receipt V1

## 投资者意义

这层只回答一个比完整比较研究更早的问题：一项历史经营行动是否已经在当时真正落地，因而值得由另一位、未见行动细节的 curator 去招募可能的机制相容 comparator。它不回答行动是否成功、哪家公司更好或股票是否值得买。

这使候选发现与后续“阅卷”分开：行动 curator 提供截止日前的已实施行动和两种可反驳解释；接纳系统只冻结收据；独立 comparator curator 仅收到不含行动、来源、假设或结果的 brief。没有人可以一边挑题、一边按后来结果挑同行。

## 已实现对象

- `schemas/judgment_selection_action_first_candidate_receipt.schema.json`：关闭的 `judgment-selection-action-first-candidate-receipt.v1` 形状。
- `scripts/judgment_selection_action_first.py`：纯 validator 与确定性 `build_comparator_recruitment_brief()`。
- `scripts/judgment_action_first_control_plane.py`：只有一张 SQLite 追加式 receipt 表；支持幂等登记、精确 replay 和 brief 加载。

一份 A1 receipt 必须同时固定 `candidate/company/issuer/RU/perimeter/cutoff`、行动 ID 与实施时点、材料性已实施行动、H-A、H-B、最强反方、topology，以及逐页官方 static CNINFO finalpage PDF 来源。来源要求有时区的可用时间、严格早于 cutoff，并且 URL 日期、发行方、RU、perimeter 和页面身份一致。

行动的 source 引用必须实际声明 `IMPLEMENTATION` 与 `MATERIALITY` 支持；H-A/H-B 的引用必须有 `HYPOTHESIS` 支持，最强反方的引用必须有 `RIVAL` 支持。因而一页只证明“行动发生了”的 PDF 不能被偷换为竞争机制或反方证据。

`PLANNED`、动态 URL、date-only 来源、cutoff 当日或之后的来源、身份/类型错误都被拒绝。closed receipt 还拒绝 outcome、价格、回报、估值、H2、peer/panel、CJO、报告、learning、investment、method 或 R-103 字段。

## 唯一输出与盲化边界

receipt 的 `allowed_outputs` 固定为：

```text
COMPARATOR_RECRUITMENT_BRIEF
```

brief 只含 cutoff、arena family、topology、没有 target 标签的 issuer/RU/perimeter carrier identity，以及 static-evidence、D2-or-cost、D3/D4 与 control 条件。它刻意不含 candidate ID、行动、来源 ID/URL、H-A/H-B、反方文本、结果、价格或最终 peer/panel。

因此 A1 不创建 H1/H2、Comparator Panel、outcome access、settlement、method transfer、CJO、报告、估值或投资权限。既有 H1/H2/V5 validator 和 seal path 完全未修改；后续只有独立 curator 按 brief 完成 action-blind intake 后，才可能进入已有 Comparative 流程。

## 验证

Focused checks:

```bash
.venv/bin/python -m pytest -q tests/test_judgment_selection_action_first.py
.venv/bin/python -m pytest -q tests/test_judgment_selection_v5.py tests/test_judgment_selection_v5_registry_epoch.py
```

项目接纳门：

```bash
.venv/bin/python scripts/project_guard.py verify full
.venv/bin/python scripts/project_guard.py merge-check
```

测试覆盖唯一 brief、无行动泄露、计划/动态/时间/来源身份/类型拒绝、禁止下游字段、实施与材料性来源要求，以及 SQLite immutable registration 与精确 replay。
