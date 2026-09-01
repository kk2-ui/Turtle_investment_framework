# Turtle Enterprise Judgment Core v1 implementation

> 状态：`CANONICAL_CONTRACT_IMPLEMENTED / SYNTHETIC_ACCEPTED / NO_REAL_COMPANY_CJO_FROZEN`
>
> 日期：2026-08-25

## 1. 实现结论

本实现把既有 V3 离线企业判断控制面提升为一条具名的 canonical 写入链：

```text
bounded source package
  -> EnterpriseSystemModel
  -> append-only ManagementDecisionLedger
  -> REVIEW_READY CJO candidate
  -> independent review receipt
  -> Frozen CJO
  -> read-only JUDGMENT_SYNTHESIS / report / synthetic quantitative views
```

V3 的 arena、责任边界、scope bridge 和 synthetic directionality 仍可作为离线设计基础；它不因本实现自动成为生产 CJO，也不能绕过新 freeze boundary。

当前没有接纳真实公司资料、真实估值、真实 BuyBand 或真实报告授权。`synthetic accepted` 只表示这条对象和权限链通过 fixture 验证。

## 2. 三个 canonical 对象

### 2.1 EnterpriseSystemModel

`scripts/enterprise_judgment_core.py` 的 `validate_enterprise_system_model` 要求同一模型同时保留：

- 公司、集团、母公司、子公司和业务单元的责任边界与父子关系；
- 产品/服务范围、客户任务、竞争机制和 arena；
- 可观察经营变量；
- 管理决策连接的经营机制；
- normal earnings、owner cash 和 permanent loss 三类独立财务传导；
- cutoff 前经营状态与状态变化；
- 每个对象引用的 bounded source package。

价格、估值、回报、训练分数、结果结算和组合动作不属于 EnterpriseSystemModel。

### 2.2 ManagementDecisionLedger

决策账本采用 `EVENT_SUFFIX_ONLY`：

```text
DECISION_RECORDED
  -> STATUS_CHANGED
  -> EVIDENCE_ATTACHED
```

`append_management_decision_event` 只返回追加一个 suffix event 的新对象；`validate_ledger_extension` 直接比较历史事件前缀，任何修改、删除或重排旧事件都会失败。

状态分开保存：

```text
PLANNED
COMMITTED
IMPLEMENTED
EXPOSED
REALIZED
CANCELLED
INSUFFICIENT_EVIDENCE
```

计划不会因进入账本自动成为已实施或已兑现。账本事件同时保存责任人、问题、arena、预期机制、最强反方、观察信号、三类财务传导和仍未证实部分。

### 2.3 Frozen CJO

`compile_cjo_candidate` 只能生成 `REVIEW_READY / canonical=false` candidate。`freeze_cjo` 还要求：

- reviewer 与 judgment owner 不同；
- review identity 与 company/cutoff/method version/candidate 完全一致；
- review 明确接受 traceability、UNKNOWN、反方、财务传导、PIT 和权限边界；
- 没有未关闭的材料性 finding。

Frozen CJO 保存：

- `PRIMARY / NO_PRIMARY / MIXED / UNKNOWN`；
- 中心路径或空对象；
- 3–5 个前瞻判断；
- 关键经营驱动；
- normal earnings、owner cash 和永久损失传导；
- 最强反方；
- UNKNOWN、保守处理与关闭证据；
- monitoring contract；
- cutoff、method version、source package；
- source → responsibility boundary → mechanism → observation/inference → financial transmission trace；
- 当时可见的 management ledger snapshot 与独立 review receipt。

Frozen CJO 明确允许报告和定量层只读，但始终保持：

```text
training_write_allowed = false
price_write_allowed = false
valuation_write_allowed = false
investment_authorization = false
```

## 3. 状态与保守传播

- 中心 trace 使用 `EVIDENCE_INELIGIBLE` 来源时，编译器降级为 `NO_PRIMARY`，不会写成企业表现差。
- `MODEL_UNCERTAIN` 或 `EVIDENCE_INELIGIBLE` 的前瞻判断必须保持 `status=UNKNOWN` 和 `direction=UNKNOWN`。
- normal earnings 改善而 owner cash 未同向改善时，编译器保留 `MIXED`。
- `NO_PRIMARY` 仍可冻结并保存 3–5 个未来可观察判断，但没有方向性投资权限。
- 所有 source `available_at`、模型状态和 ledger snapshot 均受 cutoff 约束；post-cutoff source 不能进入历史 CJO。

## 4. 下游只读接线

### JUDGMENT_SYNTHESIS 与报告

`scripts/judgment_generation_handoff.py` 新增显式 `frozen_cjo_path` / `--frozen-cjo` 输入。只有 `validate_frozen_cjo` 通过后，才将 CJO 投影为既有 `JUDGMENT_SYNTHESIS` 形状。

旧报告在未提供 Frozen CJO 时继续读取原 report-local ledgers，保持兼容；提供 Frozen CJO 时，报告 handoff 不再从正文或价格反推企业判断。

`build_report_handoff` 另提供不依赖报告目录的只读投影，固定返回：

```text
report_use = REPORT_USE_NOT_RELEASED
publication_authorization = false
investment_authorization = false
```

### Synthetic quantitative adapter

`scripts/enterprise_judgment_quantitative_adapter.py` 分开接收：

1. Frozen CJO；
2. synthetic earnings/cash/price assumptions。

价格只改变 `price_overlay`，不能改变 `cjo_ref` 或 `enterprise_case`。`MIXED`、`NO_PRIMARY` 和 `UNKNOWN` 不生成强方向性投资结论。所有结果都是 `synthetic_only`，不授予真实 BuyBand、报告发布或投资动作。

专用的 [CJO-to-Quantitative Investment Overlay v1](TURTLE_CJO_QUANTITATIVE_INVESTMENT_OVERLAY_V1_IMPLEMENTATION.md) 在同一只读边界上增加三种价值身份、价格隐含经营要求、`ExpectationGap`、D4/现金可达性/永久损失关闭规则、条件化 BuyBand 和 `INVESTMENT_ENRICHMENT` report projection。它仍为 `CANDIDATE_ONLY / PRODUCTION_PENDING`，不改变本 Core 的 canonical truth 或真实公司授权状态。

### Forecast / training

`compile_candidate_amendment` 只生成 `CANDIDATE_ONLY` amendment，引用 base Frozen CJO。它没有 apply 或 mutate 权；任何变化必须回到新的 EnterpriseSystemModel/ledger event、形成新 candidate，并再次独立审阅。

## 5. Schema 与实现文件

- `schemas/enterprise_system_model_v1.schema.json`
- `schemas/management_decision_ledger_v1.schema.json`
- `schemas/frozen_cjo_v1.schema.json`
- `scripts/enterprise_judgment_core.py`
- `scripts/enterprise_judgment_quantitative_adapter.py`
- `scripts/judgment_generation_handoff.py`
- `tests/test_enterprise_judgment_core.py`

## 6. Synthetic acceptance

focused tests 覆盖：

1. EnterpriseSystemModel + ledger 可编译并经独立 review 冻结；
2. 中心判断完整 trace；
3. `UNKNOWN / NO_PRIMARY` 保留；
4. operating improvement 与 owner cash deterioration 保留 `MIXED`；
5. 两个价格只改变 overlay；
6. Forecast/training 只能写 candidate amendment；
7. 同一 Frozen CJO 被 `JUDGMENT_SYNTHESIS`、report handoff 和 synthetic quantitative adapter 只读消费；
8. post-cutoff evidence 和 enterprise-truth 内的价格/估值字段被拒绝；
9. 作者不能自签冻结；
10. legacy V3、PIT knowledge isolation 和 golden regression 不退化。

这些测试是工程接受，不是现实世界公司判断、训练增量、正式估值、黄金报告或投资授权。
